#!/usr/bin/env python3
"""Validate the inactive temporal-governance candidate package and isolation."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
COORDINATE_SCHEMA_RELATIVE_PATH = (
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCoordinate_schema_v0_1.json"
)
COORDINATE_SCHEMA_PATH = PACKAGE_ROOT / COORDINATE_SCHEMA_RELATIVE_PATH
CARRIER_SCHEMA_RELATIVE_PATH = (
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCarrierMatrix_schema_v0_1.json"
)
CARRIER_SCHEMA_PATH = PACKAGE_ROOT / CARRIER_SCHEMA_RELATIVE_PATH
CARRIER_MATRIX_RELATIVE_PATH = (
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCarrierMatrix_ADR0002_candidate_v0_1.json"
)
CARRIER_MATRIX_PATH = PACKAGE_ROOT / CARRIER_MATRIX_RELATIVE_PATH
SELECTION_SCHEMA_RELATIVE_PATH = (
    "contracts/candidates/temporal_carrier_selection/"
    "OFARM_TemporalCarrierSelectionBinding_schema_v0_1.json"
)
SELECTION_SCHEMA_PATH = PACKAGE_ROOT / SELECTION_SCHEMA_RELATIVE_PATH
SELECTION_BINDING_RELATIVE_PATH = (
    "contracts/candidates/temporal_carrier_selection/"
    "OFARM_InterventionValidTimeCarrierSelection_candidate_v0_1.json"
)
SELECTION_BINDING_PATH = PACKAGE_ROOT / SELECTION_BINDING_RELATIVE_PATH
CANDIDATE_RELATIVE_PATHS = frozenset(
    {
        COORDINATE_SCHEMA_RELATIVE_PATH,
        CARRIER_SCHEMA_RELATIVE_PATH,
        CARRIER_MATRIX_RELATIVE_PATH,
        SELECTION_SCHEMA_RELATIVE_PATH,
        SELECTION_BINDING_RELATIVE_PATH,
    }
)
MANIFEST_PATH = PACKAGE_ROOT / "contracts/CONTRACTS_MANIFEST.json"
RFC_PATH = (
    PACKAGE_ROOT
    / "docs/rfcs/OFARM_Temporal_Coordinate_Candidate_RFC_v0_1.md"
)
SELECTION_RFC_PATH = (
    PACKAGE_ROOT
    / "docs/rfcs/"
    "OFARM_Intervention_Valid_Time_Carrier_Selection_RFC_v0_1.md"
)
ADR_PATH = PACKAGE_ROOT / "docs/adr/0002-valid-time-and-knowledge-time.md"
ERRATA_PATH = PACKAGE_ROOT / "ERRATA.md"
ENVELOPE_SCHEMA_PATH = (
    PACKAGE_ROOT / "contracts/kernel/OFARM_SemanticEventEnvelope_schema_v0_1.json"
)
EXECUTION_SCHEMA_PATH = (
    PACKAGE_ROOT / "contracts/core/OFARM_ExecutionRecordPayload_schema_v0_1.json"
)
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
MAX_KNOWLEDGE_POSITION = 9007199254740991
NIL_TENANT_ID = "00000000-0000-0000-0000-000000000000"
CARRIER_SCHEMA_VERSION = "ofarm.temporal-carrier-matrix.v0.1"
CARRIER_SCHEMA_ID = "https://ofarm.dev/schema/temporal-carrier-matrix/v0.1"
CARRIER_MATRIX_ID = "ofarm.temporal-carrier-matrix.adr0002.v0.1"
CARRIER_MATRIX_STATUS = "CANDIDATE_INACTIVE"
CARRIER_EXECUTION_POSTURE = "CLASSIFICATION_ONLY_RUNTIME_UNSUPPORTED"
CARRIER_SOURCE_AUTHORITY = (
    "docs/adr/0002-valid-time-and-knowledge-time.md"
    "#governed-carrier-and-window-meaning-matrix"
)
SELECTION_SCHEMA_VERSION = (
    "ofarm.temporal-carrier-selection-binding.v0.1"
)
SELECTION_SCHEMA_ID = (
    "https://ofarm.dev/schema/temporal-carrier-selection-binding/v0.1"
)
SELECTION_BINDING_ID = (
    "ofarm.temporal-carrier-selection.intervention.v0.1"
)
SELECTION_STATUS = "CANDIDATE_INACTIVE"
SELECTION_EXECUTION_POSTURE = "PURE_LIBRARY_PRODUCTION_UNBOUND"
SELECTION_IDENTITY_AUTHORITY = (
    "REVIEWED_BINDING_ARTIFACT_NOT_CALLER_DATA"
)
SELECTION_ROW_ID = "INTERVENTION_EVENT"
ENVELOPE_SCHEMA_VERSION = "ofarm.semanticeventenvelope.v0.1"
EXECUTION_SCHEMA_VERSION = "ofarm.executionrecordpayload.v0.1"
CARRIER_ROW_IDS = (
    "STRUCTURE_EVENT",
    "OBSERVATION_EVENT",
    "OCCURRENCE_EVENT",
    "INTERVENTION_EVENT",
    "MATERIAL_EVENT",
    "EVIDENCE_EVENT",
    "GOVERNANCE_EVENT",
    "ASSERTION_RECORD",
    "ACCEPTED_EVENT_CONSEQUENCE",
    "REVIEW_AND_GOVERNANCE_RECORDS",
    "POINT_OBSERVATION_PAYLOADS",
    "PARTIAL_EXTENT_TEMPORAL_APPLICABILITY",
    "INTERVAL_STATE_OR_OBSERVATION",
    "PENDING_OR_DISPUTED_ANNEX_ENTRY",
    "EVIDENCE_SUFFICIENCY_CASE",
)
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


@dataclass(frozen=True)
class RefusalVector:
    """One named refusal shared by the package gate and pytest."""

    vector_id: str
    validator: Callable[[object], None]
    value: object
    expected_error: str
    schema_must_refuse: bool = False


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
    missing = required - fields
    if missing:
        raise TemporalCandidateError(
            f"{label} is missing fields: {', '.join(sorted(missing))}"
        )
    unknown = fields - allowed
    if unknown:
        raise TemporalCandidateError(
            f"{label} has unknown fields: {', '.join(sorted(unknown))}"
        )
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
    if tenant_id == NIL_TENANT_ID:
        raise TemporalCandidateError("KnowledgeCut tenantId is not canonical")
    position = cut["position"]
    if (
        type(position) is not int
        or position < 0
        or position > MAX_KNOWLEDGE_POSITION
    ):
        raise TemporalCandidateError(
            "KnowledgeCut position is outside the portable safe-integer range"
        )


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


def _schema_semantics(value: object) -> object:
    if type(value) is dict:
        return {
            key: _schema_semantics(item)
            for key, item in value.items()
            if key != "$comment"
        }
    if type(value) is list:
        return [_schema_semantics(item) for item in value]
    return value


def _expect_closed_schema_definition(
    definitions: dict[str, object],
    name: str,
    *,
    required: list[str],
    properties: dict[str, object],
) -> None:
    expected = {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }
    if _schema_semantics(definitions.get(name)) != expected:
        raise TemporalCandidateError(f"candidate {name} definition differs")


def validate_coordinate_schema_shape(schema: dict[str, object]) -> None:
    expected_root_keys = {
        "$schema",
        "$id",
        "title",
        "$comment",
        "type",
        "additionalProperties",
        "required",
        "properties",
        "$defs",
    }
    if set(schema) != expected_root_keys:
        raise TemporalCandidateError("candidate coordinate schema fields differ")
    if (
        schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("$id") != CONTRACT_ID
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or schema.get("required")
        != ["schemaVersion", "validCut", "knowledgeCut"]
        or _schema_semantics(schema.get("properties"))
        != {
            "schemaVersion": {"const": CONTRACT_VERSION},
            "validCut": {"$ref": "#/$defs/validCut"},
            "knowledgeCut": {"$ref": "#/$defs/knowledgeCut"},
        }
    ):
        raise TemporalCandidateError("candidate coordinate root shape differs")
    comment = schema.get("$comment")
    if type(comment) is not str or "NEW_CANDIDATE" not in comment:
        raise TemporalCandidateError("candidate currentness is not explicit")

    definitions = schema.get("$defs")
    expected_definition_names = {
        "canonicalUtcInstant",
        "validInterval",
        "pointValidCut",
        "windowValidCut",
        "validCut",
        "knowledgeCut",
        "windowMeaning",
    }
    if (
        type(definitions) is not dict
        or set(definitions) != expected_definition_names
    ):
        raise TemporalCandidateError("candidate temporal definitions differ")
    if _schema_semantics(definitions["canonicalUtcInstant"]) != {
        "type": "string",
        "format": "date-time",
        "pattern": _UTC_INSTANT.pattern,
    }:
        raise TemporalCandidateError("candidate UTC instant definition differs")
    _expect_closed_schema_definition(
        definitions,
        "validInterval",
        required=["validFrom"],
        properties={
            "validFrom": {"$ref": "#/$defs/canonicalUtcInstant"},
            "validUntil": {"$ref": "#/$defs/canonicalUtcInstant"},
        },
    )
    _expect_closed_schema_definition(
        definitions,
        "pointValidCut",
        required=["cutType", "validAt"],
        properties={
            "cutType": {"const": "POINT"},
            "validAt": {"$ref": "#/$defs/canonicalUtcInstant"},
        },
    )
    _expect_closed_schema_definition(
        definitions,
        "windowValidCut",
        required=["cutType", "windowStart", "windowEnd"],
        properties={
            "cutType": {"const": "WINDOW"},
            "windowStart": {"$ref": "#/$defs/canonicalUtcInstant"},
            "windowEnd": {"$ref": "#/$defs/canonicalUtcInstant"},
        },
    )
    if _schema_semantics(definitions["validCut"]) != {
        "oneOf": [
            {"$ref": "#/$defs/pointValidCut"},
            {"$ref": "#/$defs/windowValidCut"},
        ]
    }:
        raise TemporalCandidateError("candidate ValidCut definition differs")
    _expect_closed_schema_definition(
        definitions,
        "knowledgeCut",
        required=["tenantId", "position"],
        properties={
            "tenantId": {
                "type": "string",
                "pattern": _CANONICAL_UUID.pattern,
                "not": {"const": NIL_TENANT_ID},
            },
            "position": {
                "type": "integer",
                "minimum": 0,
                "maximum": MAX_KNOWLEDGE_POSITION,
            },
        },
    )
    if _schema_semantics(definitions["windowMeaning"]) != {
        "enum": ["EVENT_OCCURRENCE", "STATE_OVERLAP"]
    }:
        raise TemporalCandidateError("candidate WindowMeaning definition differs")


def validate_carrier_schema_shape(schema: dict[str, object]) -> None:
    expected_root_keys = {
        "$schema",
        "$id",
        "title",
        "$comment",
        "type",
        "additionalProperties",
        "required",
        "properties",
        "$defs",
    }
    if set(schema) != expected_root_keys:
        raise TemporalCandidateError("candidate carrier schema fields differ")
    if (
        schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("$id") != CARRIER_SCHEMA_ID
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or schema.get("required")
        != [
            "schemaVersion",
            "matrixId",
            "status",
            "executionPosture",
            "coordinateContract",
            "sourceAuthority",
            "rows",
        ]
    ):
        raise TemporalCandidateError("candidate carrier root shape differs")
    comment = schema.get("$comment")
    if type(comment) is not str or "NEW_CANDIDATE" not in comment:
        raise TemporalCandidateError("candidate carrier currentness differs")
    properties = schema.get("properties")
    if type(properties) is not dict:
        raise TemporalCandidateError("candidate carrier properties are absent")
    rows = properties.get("rows")
    if (
        _schema_semantics(properties.get("schemaVersion"))
        != {"const": CARRIER_SCHEMA_VERSION}
        or _schema_semantics(properties.get("matrixId"))
        != {"const": CARRIER_MATRIX_ID}
        or _schema_semantics(properties.get("status"))
        != {"const": CARRIER_MATRIX_STATUS}
        or _schema_semantics(properties.get("executionPosture"))
        != {"const": CARRIER_EXECUTION_POSTURE}
        or _schema_semantics(properties.get("sourceAuthority"))
        != {"const": CARRIER_SOURCE_AUTHORITY}
        or _schema_semantics(properties.get("coordinateContract"))
        != {
            "type": "object",
            "additionalProperties": False,
            "required": ["schemaVersion", "schemaDigest"],
            "properties": {
                "schemaVersion": {"const": CONTRACT_VERSION},
                "schemaDigest": {
                    "type": "string",
                    "pattern": "^sha256:[0-9a-f]{64}$",
                },
            },
        }
        or _schema_semantics(rows)
        != {
            "type": "array",
            "minItems": len(CARRIER_ROW_IDS),
            "maxItems": len(CARRIER_ROW_IDS),
            "uniqueItems": True,
            "items": {"$ref": "#/$defs/carrierMatrixRow"},
        }
        or set(properties)
        != {
            "schemaVersion",
            "matrixId",
            "status",
            "executionPosture",
            "coordinateContract",
            "sourceAuthority",
            "rows",
        }
    ):
        raise TemporalCandidateError("candidate carrier properties differ")
    definitions = schema.get("$defs")
    if type(definitions) is not dict or set(definitions) != {"carrierMatrixRow"}:
        raise TemporalCandidateError("candidate carrier definitions differ")
    _expect_closed_schema_definition(
        definitions,
        "carrierMatrixRow",
        required=[
            "rowId",
            "recordOrEventFamily",
            "authoritativeValidTimeCarrierRule",
            "allowedSecondaryTimeAndConsistencyRule",
            "windowAndRefusalRule",
        ],
        properties={
            "rowId": {"enum": list(CARRIER_ROW_IDS)},
            "recordOrEventFamily": {"type": "string", "minLength": 1},
            "authoritativeValidTimeCarrierRule": {
                "type": "string",
                "minLength": 1,
            },
            "allowedSecondaryTimeAndConsistencyRule": {
                "type": "string",
                "minLength": 1,
            },
            "windowAndRefusalRule": {"type": "string", "minLength": 1},
        },
    )


def validate_carrier_matrix(value: object) -> None:
    matrix = _closed_object(
        value,
        label="TemporalCarrierMatrix",
        allowed=frozenset(
            {
                "schemaVersion",
                "matrixId",
                "status",
                "executionPosture",
                "coordinateContract",
                "sourceAuthority",
                "rows",
            }
        ),
        required=frozenset(
            {
                "schemaVersion",
                "matrixId",
                "status",
                "executionPosture",
                "coordinateContract",
                "sourceAuthority",
                "rows",
            }
        ),
    )
    if (
        matrix["schemaVersion"] != CARRIER_SCHEMA_VERSION
        or matrix["matrixId"] != CARRIER_MATRIX_ID
        or matrix["status"] != CARRIER_MATRIX_STATUS
        or matrix["executionPosture"] != CARRIER_EXECUTION_POSTURE
        or matrix["sourceAuthority"] != CARRIER_SOURCE_AUTHORITY
    ):
        raise TemporalCandidateError("TemporalCarrierMatrix identity differs")
    coordinate_contract = _closed_object(
        matrix["coordinateContract"],
        label="TemporalCarrierMatrix coordinateContract",
        allowed=frozenset({"schemaVersion", "schemaDigest"}),
        required=frozenset({"schemaVersion", "schemaDigest"}),
    )
    if coordinate_contract != {
        "schemaVersion": CONTRACT_VERSION,
        "schemaDigest": f"sha256:{_sha256(COORDINATE_SCHEMA_PATH)}",
    }:
        raise TemporalCandidateError("carrier matrix coordinate binding differs")
    rows = matrix["rows"]
    if type(rows) is not list or len(rows) != len(CARRIER_ROW_IDS):
        raise TemporalCandidateError("carrier matrix row count differs")
    normalized_adr = ADR_PATH.read_text(encoding="utf-8").replace("`", "")
    observed_row_ids: list[str] = []
    text_fields = (
        "recordOrEventFamily",
        "authoritativeValidTimeCarrierRule",
        "allowedSecondaryTimeAndConsistencyRule",
        "windowAndRefusalRule",
    )
    for index, value_row in enumerate(rows):
        row = _closed_object(
            value_row,
            label=f"TemporalCarrierMatrix row {index}",
            allowed=frozenset({"rowId", *text_fields}),
            required=frozenset({"rowId", *text_fields}),
        )
        row_id = row["rowId"]
        if type(row_id) is not str:
            raise TemporalCandidateError("carrier matrix rowId is not text")
        observed_row_ids.append(row_id)
        for field in text_fields:
            rule = row[field]
            if type(rule) is not str or not rule:
                raise TemporalCandidateError(f"carrier matrix {field} is empty")
            if rule not in normalized_adr:
                raise TemporalCandidateError(
                    f"carrier matrix {row_id} {field} differs from ADR 0002"
                )
    if tuple(observed_row_ids) != CARRIER_ROW_IDS:
        raise TemporalCandidateError("carrier matrix row identities differ")


def validate_selection_schema_shape(schema: dict[str, object]) -> None:
    if (
        schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("$id") != SELECTION_SCHEMA_ID
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or schema.get("required")
        != [
            "schemaVersion",
            "bindingId",
            "status",
            "executionPosture",
            "identityAuthority",
            "coordinateContract",
            "carrierMatrix",
            "sourceContracts",
            "selectors",
            "unsupportedEnvelopeFields",
        ]
    ):
        raise TemporalCandidateError(
            "candidate carrier-selection schema root differs"
        )
    comment = schema.get("$comment")
    properties = schema.get("properties")
    if (
        type(comment) is not str
        or "NEW_CANDIDATE" not in comment
        or "caller data never selects" not in comment
        or type(properties) is not dict
    ):
        raise TemporalCandidateError(
            "candidate carrier-selection schema authority differs"
        )
    expected_constants = {
        "schemaVersion": SELECTION_SCHEMA_VERSION,
        "bindingId": SELECTION_BINDING_ID,
        "status": SELECTION_STATUS,
        "executionPosture": SELECTION_EXECUTION_POSTURE,
        "identityAuthority": SELECTION_IDENTITY_AUTHORITY,
    }
    for field, expected in expected_constants.items():
        if _schema_semantics(properties.get(field)) != {"const": expected}:
            raise TemporalCandidateError(
                f"candidate carrier-selection {field} differs"
            )
    expected_binding = _expected_selection_binding()
    for field in (
        "coordinateContract",
        "carrierMatrix",
        "sourceContracts",
        "selectors",
        "unsupportedEnvelopeFields",
    ):
        if _schema_semantics(properties.get(field)) != {
            "const": expected_binding[field]
        }:
            raise TemporalCandidateError(
                f"candidate carrier-selection {field} authority differs"
            )
    if "$defs" in schema:
        raise TemporalCandidateError(
            "candidate carrier-selection schema has unused definitions"
        )


def _expected_selection_binding() -> dict[str, object]:
    return {
        "schemaVersion": SELECTION_SCHEMA_VERSION,
        "bindingId": SELECTION_BINDING_ID,
        "status": SELECTION_STATUS,
        "executionPosture": SELECTION_EXECUTION_POSTURE,
        "identityAuthority": SELECTION_IDENTITY_AUTHORITY,
        "coordinateContract": {
            "schemaVersion": CONTRACT_VERSION,
            "schemaDigest": f"sha256:{_sha256(COORDINATE_SCHEMA_PATH)}",
        },
        "carrierMatrix": {
            "matrixId": CARRIER_MATRIX_ID,
            "matrixDigest": f"sha256:{_sha256(CARRIER_MATRIX_PATH)}",
            "rowId": SELECTION_ROW_ID,
        },
        "sourceContracts": [
            {
                "contractRole": "SEMANTIC_EVENT_ENVELOPE",
                "schemaVersion": ENVELOPE_SCHEMA_VERSION,
                "schemaDigest": f"sha256:{_sha256(ENVELOPE_SCHEMA_PATH)}",
                "discriminatorPath": "/primaryEventFamily",
                "discriminatorValue": "InterventionEvent",
            },
            {
                "contractRole": "EXECUTION_RECORD_PAYLOAD",
                "schemaVersion": EXECUTION_SCHEMA_VERSION,
                "schemaDigest": f"sha256:{_sha256(EXECUTION_SCHEMA_PATH)}",
                "discriminatorPath": "/recordClass",
                "discriminatorValue": "OPERATION_CLAIM",
            },
        ],
        "selectors": [
            {
                "selectorId": "INTERVENTION_OCCURRENCE",
                "sourceContractRole": "SEMANTIC_EVENT_ENVELOPE",
                "carrierShape": "POINT",
                "valuePath": "/timeSemantics/eventTime",
                "windowMeaning": "EVENT_OCCURRENCE",
            },
            {
                "selectorId": "INTERVENTION_EXECUTION_INTERVAL",
                "sourceContractRole": "EXECUTION_RECORD_PAYLOAD",
                "carrierShape": "BOUNDED_HALF_OPEN_INTERVAL",
                "startPath": "/effectiveTimeInterval/start",
                "endPath": "/effectiveTimeInterval/end",
                "timeBasisPath": "/effectiveTimeInterval/timeBasis",
                "requiredTimeBasis": "EXECUTION_INTERVAL",
                "windowMeaning": "STATE_OVERLAP",
            },
        ],
        "unsupportedEnvelopeFields": [
            "/timeSemantics/effectiveFrom",
            "/timeSemantics/effectiveUntil",
        ],
    }


def validate_selection_binding(value: object) -> None:
    if value != _expected_selection_binding():
        raise TemporalCandidateError(
            "intervention carrier-selection binding differs"
        )


def validate_runtime_selection_binding() -> None:
    package_root = str(PACKAGE_ROOT)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    from kernel import temporal_carriers

    identity = temporal_carriers.INTERVENTION_BINDING
    expected_identity = {
        "binding_schema_version": SELECTION_SCHEMA_VERSION,
        "binding_id": SELECTION_BINDING_ID,
        "binding_artifact_digest": (
            f"sha256:{_sha256(SELECTION_BINDING_PATH)}"
        ),
        "coordinate_schema_version": CONTRACT_VERSION,
        "coordinate_schema_digest": (
            f"sha256:{_sha256(COORDINATE_SCHEMA_PATH)}"
        ),
        "carrier_matrix_id": CARRIER_MATRIX_ID,
        "carrier_matrix_digest": f"sha256:{_sha256(CARRIER_MATRIX_PATH)}",
        "carrier_matrix_row_id": SELECTION_ROW_ID,
        "envelope_schema_version": ENVELOPE_SCHEMA_VERSION,
        "envelope_schema_digest": f"sha256:{_sha256(ENVELOPE_SCHEMA_PATH)}",
        "execution_schema_version": EXECUTION_SCHEMA_VERSION,
        "execution_schema_digest": f"sha256:{_sha256(EXECUTION_SCHEMA_PATH)}",
    }
    observed_identity = {
        field: getattr(identity, field) for field in expected_identity
    }
    if observed_identity != expected_identity:
        raise TemporalCandidateError(
            "runtime carrier-selection identity differs from its artifact"
        )


def validate_runtime_selection_isolation() -> None:
    package_root = str(PACKAGE_ROOT)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    from conformance import rewrite_architecture_check as architecture

    sources = architecture._module_sources(PACKAGE_ROOT)
    graph, _trees = architecture._import_graph(sources)
    for roots, label in (
        (architecture.PRODUCTION_IMPORT_ROOTS, "production"),
        (architecture.LEGACY_IMPORT_ROOTS, "legacy"),
    ):
        reachable = architecture._reachable_paths(graph, roots)
        if "kernel.temporal_carriers" in reachable:
            raise TemporalCandidateError(
                f"carrier selector entered the {label} import closure"
            )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_manifest_entry(
    path: str,
    artifact_path: Path,
    currentness_note: str,
    law_basis: str = (
        "ADR 0002 and "
        "docs/rfcs/OFARM_Temporal_Coordinate_Candidate_RFC_v0_1.md"
    ),
) -> dict[str, object]:
    return {
        "packagePath": path,
        "sourcePath": None,
        "sha256": _sha256(artifact_path),
        "status": "NEW_CANDIDATE",
        "promotionLadderStage": "CANDIDATE_ARTIFACT",
        "currentnessNote": currentness_note,
        "lawBasis": law_basis,
    }


def validate_non_activation(runtime_catalog: object) -> None:
    if type(runtime_catalog) is not dict:
        raise TemporalCandidateError("runtime component catalog is malformed")
    contract_paths = runtime_catalog.get("contractSchemas")
    components = runtime_catalog.get("components")
    if type(contract_paths) is not list or type(components) is not list:
        raise TemporalCandidateError("runtime component catalog is malformed")
    if CANDIDATE_RELATIVE_PATHS.intersection(contract_paths):
        raise TemporalCandidateError("candidate entered RuntimeBundle contracts")
    for component in components:
        if (
            type(component) is dict
            and component.get("relativePath") in CANDIDATE_RELATIVE_PATHS
        ):
            raise TemporalCandidateError("candidate entered a runtime component")


def validate_candidate_governance() -> None:
    coordinate_schema = _load_json(COORDINATE_SCHEMA_PATH)
    carrier_schema = _load_json(CARRIER_SCHEMA_PATH)
    carrier_matrix = _load_json(CARRIER_MATRIX_PATH)
    selection_schema = _load_json(SELECTION_SCHEMA_PATH)
    selection_binding = _load_json(SELECTION_BINDING_PATH)
    validate_coordinate_schema_shape(coordinate_schema)
    validate_carrier_schema_shape(carrier_schema)
    validate_carrier_matrix(carrier_matrix)
    validate_selection_schema_shape(selection_schema)
    validate_selection_binding(selection_binding)
    validate_runtime_selection_binding()
    validate_runtime_selection_isolation()

    manifest = _load_json(MANIFEST_PATH)
    entries = manifest.get("entries")
    if type(entries) is not list:
        raise TemporalCandidateError("contract manifest entries are absent")
    expected_entries = {
        COORDINATE_SCHEMA_RELATIVE_PATH: _expected_manifest_entry(
            COORDINATE_SCHEMA_RELATIVE_PATH,
            COORDINATE_SCHEMA_PATH,
            (
                "Package-local temporal-coordinate candidate for issue #176; "
                "not active, promoted, or selected by the production "
                "RuntimeBundle."
            ),
        ),
        CARRIER_SCHEMA_RELATIVE_PATH: _expected_manifest_entry(
            CARRIER_SCHEMA_RELATIVE_PATH,
            CARRIER_SCHEMA_PATH,
            (
                "Package-local temporal carrier-matrix schema candidate for "
                "issue #176; classification-only, inactive, and not selected "
                "by the production RuntimeBundle."
            ),
        ),
        CARRIER_MATRIX_RELATIVE_PATH: _expected_manifest_entry(
            CARRIER_MATRIX_RELATIVE_PATH,
            CARRIER_MATRIX_PATH,
            (
                "Package-local ADR 0002 carrier-matrix candidate for issue "
                "#176; classification-only, inactive, and not selected by "
                "the production RuntimeBundle."
            ),
        ),
        SELECTION_SCHEMA_RELATIVE_PATH: _expected_manifest_entry(
            SELECTION_SCHEMA_RELATIVE_PATH,
            SELECTION_SCHEMA_PATH,
            (
                "Package-local temporal carrier-selection binding schema "
                "candidate for issue #176; inactive, production-unbound, and "
                "not selected by the production RuntimeBundle."
            ),
            (
                "ADR 0002 and docs/rfcs/"
                "OFARM_Intervention_Valid_Time_Carrier_Selection_RFC_v0_1.md"
            ),
        ),
        SELECTION_BINDING_RELATIVE_PATH: _expected_manifest_entry(
            SELECTION_BINDING_RELATIVE_PATH,
            SELECTION_BINDING_PATH,
            (
                "Package-local intervention valid-time carrier-selection "
                "candidate for issue #176; executable only as an isolated "
                "pure library, inactive, and not selected by the production "
                "RuntimeBundle."
            ),
            (
                "ADR 0002 and docs/rfcs/"
                "OFARM_Intervention_Valid_Time_Carrier_Selection_RFC_v0_1.md"
            ),
        ),
    }
    candidate_entries = [
        entry
        for entry in entries
        if type(entry) is dict
        and entry.get("packagePath") in CANDIDATE_RELATIVE_PATHS
    ]
    observed_entries = {
        entry.get("packagePath"): entry for entry in candidate_entries
    }
    if (
        len(candidate_entries) != len(expected_entries)
        or observed_entries != expected_entries
    ):
        raise TemporalCandidateError("candidate manifest metadata differs")

    rfc = RFC_PATH.read_text(encoding="utf-8")
    digest_markers = (
        (
            "**Temporal coordinate schema digest:** "
            f"`sha256:{_sha256(COORDINATE_SCHEMA_PATH)}`"
        ),
        (
            "**Temporal carrier matrix schema digest:** "
            f"`sha256:{_sha256(CARRIER_SCHEMA_PATH)}`"
        ),
        (
            "**Temporal carrier matrix instance digest:** "
            f"`sha256:{_sha256(CARRIER_MATRIX_PATH)}`"
        ),
    )
    if any(rfc.count(marker) != 1 for marker in digest_markers):
        raise TemporalCandidateError("candidate RFC digest binding differs")
    required_rfc_markers = (
        "9007199254740991",
        "pre-promotion",
        "candidate revisions",
        "complete Draft",
        "2020-12 validation path",
        CARRIER_MATRIX_ID,
        CARRIER_EXECUTION_POSTURE,
    )
    if any(marker not in rfc for marker in required_rfc_markers):
        raise TemporalCandidateError("candidate RFC stop conditions differ")

    selection_rfc = SELECTION_RFC_PATH.read_text(encoding="utf-8")
    selection_digest_markers = (
        f"`sha256:{_sha256(SELECTION_SCHEMA_PATH)}`",
        f"`sha256:{_sha256(SELECTION_BINDING_PATH)}`",
    )
    if any(
        selection_rfc.count(marker) != 1
        for marker in selection_digest_markers
    ):
        raise TemporalCandidateError(
            "carrier-selection RFC digest binding differs"
        )
    required_selection_markers = (
        SELECTION_BINDING_ID,
        SELECTION_IDENTITY_AUTHORITY,
        "never taken from caller data",
        "INTERVENTION_EVENT",
        "OPERATION_CLAIM",
        "production-unbound",
    )
    if any(
        marker not in selection_rfc for marker in required_selection_markers
    ):
        raise TemporalCandidateError(
            "carrier-selection RFC authority or stop conditions differ"
        )

    errata = ERRATA_PATH.read_text(encoding="utf-8")
    if any(
        marker not in errata
        for marker in (
            "| E-008 |",
            CONTRACT_VERSION,
            CARRIER_MATRIX_ID,
            SELECTION_BINDING_ID,
        )
    ):
        raise TemporalCandidateError("candidate ERRATA governance record differs")

    runtime_catalog = _load_json(RUNTIME_CATALOG_PATH)
    validate_non_activation(runtime_catalog)
    activation_markers = (
        CONTRACT_VERSION,
        CARRIER_SCHEMA_VERSION,
        CARRIER_MATRIX_ID,
        SELECTION_SCHEMA_VERSION,
        SELECTION_BINDING_ID,
        SELECTION_EXECUTION_POSTURE,
        *CANDIDATE_RELATIVE_PATHS,
    )
    for path, label in (
        (ACTIVE_ARTIFACT_SET_PATH, "ActiveArtifactSet"),
        (CAPABILITY_MANIFEST_PATH, "Capability Manifest"),
    ):
        active_text = path.read_text(encoding="utf-8")
        if any(marker in active_text for marker in activation_markers):
            raise TemporalCandidateError(f"candidate entered the {label}")


def _coordinate_value(
    *,
    valid_cut: dict[str, object] | None = None,
    knowledge_cut: dict[str, object] | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "schemaVersion": CONTRACT_VERSION,
        "validCut": valid_cut
        or {
            "cutType": "POINT",
            "validAt": "2026-07-28T10:30:00.123456Z",
        },
        "knowledgeCut": knowledge_cut
        or {
            "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
            "position": 42,
        },
    }
    if extra:
        value.update(extra)
    return value


REFUSAL_VECTORS = (
    RefusalVector(
        "naive-time",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "POINT",
                "validAt": "2026-07-28T10:30:00",
            }
        ),
        "canonical UTC",
        True,
    ),
    RefusalVector(
        "leap-second",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "POINT",
                "validAt": "2026-12-31T23:59:60Z",
            }
        ),
        "canonical UTC",
        True,
    ),
    RefusalVector(
        "excess-fractional-precision",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "POINT",
                "validAt": "2026-07-28T10:30:00.1234567Z",
            }
        ),
        "canonical UTC",
        True,
    ),
    RefusalVector(
        "non-real-gregorian-instant",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "POINT",
                "validAt": "2026-02-30T10:30:00Z",
            }
        ),
        "not a real UTC instant",
    ),
    RefusalVector(
        "mixed-point-window",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "POINT",
                "validAt": "2026-07-28T10:30:00Z",
                "windowStart": "2026-01-01T00:00:00Z",
            }
        ),
        "unknown fields",
        True,
    ),
    RefusalVector(
        "open-query-window",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "WINDOW",
                "windowStart": "2026-01-01T00:00:00Z",
            }
        ),
        "missing fields",
        True,
    ),
    RefusalVector(
        "empty-query-window",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "WINDOW",
                "windowStart": "2026-01-01T00:00:00Z",
                "windowEnd": "2026-01-01T00:00:00Z",
            }
        ),
        "non-empty and half-open",
    ),
    RefusalVector(
        "reversed-query-window",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "WINDOW",
                "windowStart": "2027-01-01T00:00:00Z",
                "windowEnd": "2026-01-01T00:00:00Z",
            }
        ),
        "non-empty and half-open",
    ),
    RefusalVector(
        "negative-position",
        validate_temporal_coordinate,
        _coordinate_value(
            knowledge_cut={
                "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
                "position": -1,
            }
        ),
        "portable safe-integer range",
        True,
    ),
    RefusalVector(
        "boolean-position",
        validate_temporal_coordinate,
        _coordinate_value(
            knowledge_cut={
                "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
                "position": True,
            }
        ),
        "portable safe-integer range",
        True,
    ),
    RefusalVector(
        "unsafe-position",
        validate_temporal_coordinate,
        _coordinate_value(
            knowledge_cut={
                "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
                "position": MAX_KNOWLEDGE_POSITION + 1,
            }
        ),
        "portable safe-integer range",
        True,
    ),
    RefusalVector(
        "tenant-alias",
        validate_temporal_coordinate,
        _coordinate_value(
            knowledge_cut={"tenantId": "tenant:demo", "position": 0}
        ),
        "not canonical",
        True,
    ),
    RefusalVector(
        "nil-tenant",
        validate_temporal_coordinate,
        _coordinate_value(
            knowledge_cut={"tenantId": NIL_TENANT_ID, "position": 0}
        ),
        "not canonical",
        True,
    ),
    RefusalVector(
        "unknown-coordinate-field",
        validate_temporal_coordinate,
        _coordinate_value(extra={"asOf": "2026-07-28T10:30:00Z"}),
        "unknown fields",
        True,
    ),
    RefusalVector(
        "empty-valid-interval",
        validate_valid_interval,
        {
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-01-01T00:00:00Z",
        },
        "non-empty and half-open",
    ),
    RefusalVector(
        "reversed-valid-interval",
        validate_valid_interval,
        {
            "validFrom": "2027-01-01T00:00:00Z",
            "validUntil": "2026-01-01T00:00:00Z",
        },
        "non-empty and half-open",
    ),
    RefusalVector(
        "unknown-window-meaning",
        validate_window_meaning,
        "QUERY_WIDE",
        "closed vocabulary",
    ),
)


def _must_refuse(vector: RefusalVector) -> None:
    try:
        vector.validator(copy.deepcopy(vector.value))
    except TemporalCandidateError as exc:
        if re.search(vector.expected_error, str(exc)) is None:
            raise TemporalCandidateError(
                f"negative vector {vector.vector_id!r} returned the wrong refusal"
            ) from exc
        return
    except Exception as exc:
        raise TemporalCandidateError(
            f"negative vector {vector.vector_id!r} crashed"
        ) from exc
    raise TemporalCandidateError(
        f"negative vector {vector.vector_id!r} was accepted"
    )


def validate_semantic_vectors() -> None:
    validate_temporal_coordinate(_coordinate_value())
    validate_temporal_coordinate(
        _coordinate_value(
            valid_cut={
                "cutType": "WINDOW",
                "windowStart": "2026-01-01T00:00:00Z",
                "windowEnd": "2027-01-01T00:00:00Z",
            },
            knowledge_cut={
                "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
                "position": MAX_KNOWLEDGE_POSITION,
            },
        )
    )
    validate_valid_interval({"validFrom": "2026-01-01T00:00:00Z"})
    validate_valid_interval(
        {
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2027-01-01T00:00:00Z",
        }
    )
    for meaning in sorted(WINDOW_MEANINGS):
        validate_window_meaning(meaning)
    validate_carrier_matrix(_load_json(CARRIER_MATRIX_PATH))
    for vector in REFUSAL_VECTORS:
        _must_refuse(vector)


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
