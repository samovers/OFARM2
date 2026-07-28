#!/usr/bin/env python3
"""Validate the non-default temporal-coordinate candidate and its isolation."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable
from uuid import UUID


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_RELATIVE_PATH = (
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCoordinate_schema_v0_1.json"
)
SCHEMA_PATH = PACKAGE_ROOT / SCHEMA_RELATIVE_PATH
MANIFEST_PATH = PACKAGE_ROOT / "contracts/CONTRACTS_MANIFEST.json"
RFC_PATH = (
    PACKAGE_ROOT
    / "docs/rfcs/OFARM_Temporal_Coordinate_Candidate_RFC_v0_1.md"
)
ERRATA_PATH = PACKAGE_ROOT / "ERRATA.md"
RUNTIME_CATALOG_PATH = PACKAGE_ROOT / "kernel/runtime_bundle_components.json"
ACTIVE_ARTIFACT_SET_PATH = (
    PACKAGE_ROOT
    / "profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json"
)
CAPABILITY_MANIFEST_PATH = (
    PACKAGE_ROOT
    / "profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json"
)

CONTRACT_VERSION = "ofarm.temporal-coordinate.v0.1"
CONTRACT_ID = "https://ofarm.dev/schema/temporal-coordinate/v0.1"
MAX_KNOWLEDGE_POSITION = 9223372036854775807
NIL_TENANT_ID = "00000000-0000-0000-0000-000000000000"
WINDOW_MEANINGS = frozenset({"EVENT_OCCURRENCE", "STATE_OVERLAP"})
_UTC_INSTANT = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"(\.[0-9]{1,6})?Z$"
)
_CANONICAL_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}$"
)


class TemporalCandidateError(ValueError):
    """The candidate document differs from its approved temporal semantics."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TemporalCandidateError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TemporalCandidateError(f"{path} is not strict JSON") from exc
    if type(value) is not dict:
        raise TemporalCandidateError(f"{path} must contain one JSON object")
    return value


def _closed_object(
    value: object,
    *,
    label: str,
    allowed: frozenset[str],
    required: frozenset[str],
) -> dict[str, object]:
    if type(value) is not dict:
        raise TemporalCandidateError(f"{label} must be an object")
    fields = frozenset(value)
    if not required <= fields or not fields <= allowed:
        raise TemporalCandidateError(f"{label} has unknown or missing fields")
    return value


def canonical_utc_instant(value: object, label: str) -> datetime:
    if type(value) is not str or _UTC_INSTANT.fullmatch(value) is None:
        raise TemporalCandidateError(f"{label} is not canonical UTC")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TemporalCandidateError(f"{label} is not a real UTC instant") from exc
    return instant


def validate_valid_interval(value: object) -> None:
    interval = _closed_object(
        value,
        label="ValidInterval",
        allowed=frozenset({"validFrom", "validUntil"}),
        required=frozenset({"validFrom"}),
    )
    start = canonical_utc_instant(interval["validFrom"], "validFrom")
    if "validUntil" in interval:
        end = canonical_utc_instant(interval["validUntil"], "validUntil")
        if end <= start:
            raise TemporalCandidateError(
                "ValidInterval must be non-empty and half-open"
            )


def validate_valid_cut(value: object) -> None:
    if type(value) is not dict:
        raise TemporalCandidateError("ValidCut must be an object")
    cut_type = value.get("cutType")
    if cut_type == "POINT":
        point = _closed_object(
            value,
            label="POINT ValidCut",
            allowed=frozenset({"cutType", "validAt"}),
            required=frozenset({"cutType", "validAt"}),
        )
        canonical_utc_instant(point["validAt"], "validAt")
        return
    if cut_type == "WINDOW":
        window = _closed_object(
            value,
            label="WINDOW ValidCut",
            allowed=frozenset({"cutType", "windowStart", "windowEnd"}),
            required=frozenset({"cutType", "windowStart", "windowEnd"}),
        )
        start = canonical_utc_instant(window["windowStart"], "windowStart")
        end = canonical_utc_instant(window["windowEnd"], "windowEnd")
        if end <= start:
            raise TemporalCandidateError(
                "WINDOW ValidCut must be non-empty and half-open"
            )
        return
    raise TemporalCandidateError("ValidCut cutType must be POINT or WINDOW")


def validate_knowledge_cut(value: object) -> None:
    cut = _closed_object(
        value,
        label="KnowledgeCut",
        allowed=frozenset({"tenantId", "position"}),
        required=frozenset({"tenantId", "position"}),
    )
    tenant_id = cut["tenantId"]
    if type(tenant_id) is not str or _CANONICAL_UUID.fullmatch(tenant_id) is None:
        raise TemporalCandidateError("KnowledgeCut tenantId is not canonical")
    try:
        parsed_tenant_id = UUID(tenant_id)
    except ValueError as exc:
        raise TemporalCandidateError(
            "KnowledgeCut tenantId is not a UUID"
        ) from exc
    if tenant_id == NIL_TENANT_ID or str(parsed_tenant_id) != tenant_id:
        raise TemporalCandidateError("KnowledgeCut tenantId is not canonical")
    position = cut["position"]
    if (
        type(position) is not int
        or position < 0
        or position > MAX_KNOWLEDGE_POSITION
    ):
        raise TemporalCandidateError("KnowledgeCut position is outside int64")


def validate_window_meaning(value: object) -> None:
    if type(value) is not str or value not in WINDOW_MEANINGS:
        raise TemporalCandidateError("WindowMeaning is outside the closed vocabulary")


def validate_temporal_coordinate(value: object) -> None:
    coordinate = _closed_object(
        value,
        label="TemporalCoordinate",
        allowed=frozenset({"schemaVersion", "validCut", "knowledgeCut"}),
        required=frozenset({"schemaVersion", "validCut", "knowledgeCut"}),
    )
    if coordinate["schemaVersion"] != CONTRACT_VERSION:
        raise TemporalCandidateError("TemporalCoordinate version differs")
    validate_valid_cut(coordinate["validCut"])
    validate_knowledge_cut(coordinate["knowledgeCut"])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_candidate_governance() -> None:
    schema = _load_json(SCHEMA_PATH)
    if schema.get("$id") != CONTRACT_ID:
        raise TemporalCandidateError("candidate schema id differs")
    properties = schema.get("properties")
    if type(properties) is not dict:
        raise TemporalCandidateError("candidate schema properties are absent")
    version_property = properties.get("schemaVersion")
    if (
        type(version_property) is not dict
        or version_property.get("const") != CONTRACT_VERSION
    ):
        raise TemporalCandidateError("candidate schema version differs")
    comment = schema.get("$comment")
    if type(comment) is not str or "NEW_CANDIDATE" not in comment:
        raise TemporalCandidateError("candidate currentness is not explicit")
    definitions = schema.get("$defs")
    expected_definitions = {
        "canonicalUtcInstant",
        "validInterval",
        "pointValidCut",
        "windowValidCut",
        "validCut",
        "knowledgeCut",
        "windowMeaning",
    }
    if type(definitions) is not dict or set(definitions) != expected_definitions:
        raise TemporalCandidateError("candidate temporal definitions differ")
    instant_definition = definitions["canonicalUtcInstant"]
    knowledge_definition = definitions["knowledgeCut"]
    window_meaning_definition = definitions["windowMeaning"]
    if (
        type(instant_definition) is not dict
        or instant_definition.get("pattern") != _UTC_INSTANT.pattern
        or instant_definition.get("format") != "date-time"
    ):
        raise TemporalCandidateError("candidate UTC instant definition differs")
    knowledge_properties = (
        knowledge_definition.get("properties")
        if type(knowledge_definition) is dict
        else None
    )
    tenant_property = (
        knowledge_properties.get("tenantId")
        if type(knowledge_properties) is dict
        else None
    )
    position_property = (
        knowledge_properties.get("position")
        if type(knowledge_properties) is dict
        else None
    )
    if (
        type(tenant_property) is not dict
        or tenant_property.get("pattern") != _CANONICAL_UUID.pattern
        or tenant_property.get("not") != {"const": NIL_TENANT_ID}
        or type(position_property) is not dict
        or position_property.get("type") != "integer"
        or position_property.get("minimum") != 0
        or position_property.get("maximum") != MAX_KNOWLEDGE_POSITION
    ):
        raise TemporalCandidateError("candidate KnowledgeCut definition differs")
    if (
        type(window_meaning_definition) is not dict
        or window_meaning_definition.get("enum") != [
            "EVENT_OCCURRENCE",
            "STATE_OVERLAP",
        ]
    ):
        raise TemporalCandidateError("candidate WindowMeaning definition differs")

    manifest = _load_json(MANIFEST_PATH)
    entries = manifest.get("entries")
    if type(entries) is not list:
        raise TemporalCandidateError("contract manifest entries are absent")
    candidate_entries = [
        entry
        for entry in entries
        if type(entry) is dict
        and entry.get("packagePath") == SCHEMA_RELATIVE_PATH
    ]
    if len(candidate_entries) != 1:
        raise TemporalCandidateError("candidate manifest entry differs")
    entry = candidate_entries[0]
    expected_entry = {
        "packagePath": SCHEMA_RELATIVE_PATH,
        "sourcePath": None,
        "sha256": _sha256(SCHEMA_PATH),
        "status": "NEW_CANDIDATE",
        "promotionLadderStage": "CANDIDATE_ARTIFACT",
        "currentnessNote": (
            "Package-local candidate for issue #176; not active, promoted, "
            "or selected by the production RuntimeBundle."
        ),
        "lawBasis": (
            "ADR 0002 and "
            "docs/rfcs/OFARM_Temporal_Coordinate_Candidate_RFC_v0_1.md"
        ),
    }
    if entry != expected_entry:
        raise TemporalCandidateError("candidate manifest metadata differs")
    schema_digest = _sha256(SCHEMA_PATH)
    digest_marker = f"**Schema digest:** `sha256:{schema_digest}`"
    if RFC_PATH.read_text(encoding="utf-8").count(digest_marker) != 1:
        raise TemporalCandidateError("candidate RFC schema digest differs")
    errata = ERRATA_PATH.read_text(encoding="utf-8")
    if "| E-008 |" not in errata or CONTRACT_VERSION not in errata:
        raise TemporalCandidateError("candidate ERRATA governance record differs")

    runtime_catalog = _load_json(RUNTIME_CATALOG_PATH)
    contract_paths = runtime_catalog.get("contractSchemas")
    if type(contract_paths) is not list:
        raise TemporalCandidateError("runtime component catalog is malformed")
    if SCHEMA_RELATIVE_PATH in contract_paths:
        raise TemporalCandidateError("candidate entered the RuntimeBundle")

    for path, label in (
        (ACTIVE_ARTIFACT_SET_PATH, "ActiveArtifactSet"),
        (CAPABILITY_MANIFEST_PATH, "Capability Manifest"),
    ):
        if CONTRACT_VERSION in path.read_text(encoding="utf-8"):
            raise TemporalCandidateError(f"candidate entered the {label}")


def _must_refuse(
    validator: Callable[[object], None],
    value: object,
    label: str,
) -> None:
    try:
        validator(value)
    except TemporalCandidateError:
        return
    raise TemporalCandidateError(f"negative vector {label!r} was accepted")


def validate_semantic_vectors() -> None:
    point_coordinate = {
        "schemaVersion": CONTRACT_VERSION,
        "validCut": {
            "cutType": "POINT",
            "validAt": "2026-07-28T10:30:00.123456Z",
        },
        "knowledgeCut": {
            "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
            "position": 42,
        },
    }
    window_coordinate = {
        "schemaVersion": CONTRACT_VERSION,
        "validCut": {
            "cutType": "WINDOW",
            "windowStart": "2026-01-01T00:00:00Z",
            "windowEnd": "2027-01-01T00:00:00Z",
        },
        "knowledgeCut": {
            "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
            "position": 0,
        },
    }
    validate_temporal_coordinate(point_coordinate)
    validate_temporal_coordinate(window_coordinate)
    validate_valid_interval({"validFrom": "2026-01-01T00:00:00Z"})
    validate_valid_interval(
        {
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2027-01-01T00:00:00Z",
        }
    )
    for meaning in sorted(WINDOW_MEANINGS):
        validate_window_meaning(meaning)

    refusal_vectors: tuple[
        tuple[Callable[[object], None], object, str],
        ...,
    ] = (
        (
            validate_valid_cut,
            {"cutType": "POINT", "validAt": "2026-07-28T10:30:00"},
            "naive instant",
        ),
        (
            validate_valid_cut,
            {"cutType": "POINT", "validAt": "2026-02-30T10:30:00Z"},
            "non-real Gregorian instant",
        ),
        (
            validate_valid_cut,
            {
                "cutType": "WINDOW",
                "windowStart": "2026-01-01T00:00:00Z",
                "windowEnd": "2026-01-01T00:00:00Z",
            },
            "empty window",
        ),
        (
            validate_knowledge_cut,
            {
                "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
                "position": -1,
            },
            "negative knowledge position",
        ),
        (
            validate_knowledge_cut,
            {"tenantId": NIL_TENANT_ID, "position": 0},
            "nil tenant identifier",
        ),
        (
            validate_valid_interval,
            {
                "validFrom": "2026-01-01T00:00:00Z",
                "validUntil": "2026-01-01T00:00:00Z",
            },
            "empty valid interval",
        ),
        (
            validate_window_meaning,
            "QUERY_WIDE",
            "unknown window meaning",
        ),
    )
    for validator, value, label in refusal_vectors:
        _must_refuse(validator, value, label)


def main() -> int:
    try:
        validate_candidate_governance()
        validate_semantic_vectors()
    except (OSError, TemporalCandidateError) as exc:
        print(f"TEMPORAL CANDIDATE FAIL: {exc}")
        return 1
    print("TEMPORAL CANDIDATE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
