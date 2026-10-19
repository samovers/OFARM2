#!/usr/bin/env python3
"""Audit consumed CI transition evidence; never activate or accept new work.

The independently retained journal and original-message references supply the
historical coordinates. Archived code is inspected as Git data, never imported
or executed. Offline integrity is not a fresh provider observation or approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conformance import ci_policy_transition_operator as operator
from conformance import evidence_publication_policy as evidence
from conformance import review_baseline_admission as ordinary

Json = dict[str, Any]
TICKET_NAME = "ci-policy-transition-ticket-v1"
RECEIPT_NAME = "ci-policy-transition-publication-receipt-v1"
RECEIPT_FILE = "ci-policy-transition-publication-receipt.json"
RECEIPT_SCHEMA = "ofarm.ci-policy-transition-publication.v1"
SOURCE_NAMES = (*ordinary.PROVISIONAL_ARTIFACT_NAMES, TICKET_NAME)
PUBLISHED_NAMES = ordinary.PUBLICATION_ARTIFACT_NAMES
LIMITS = {
    **evidence.PROVISIONAL_ARTIFACT_LIMITS,
    TICKET_NAME: 1_000_000,
    RECEIPT_NAME: 1_000_000,
    "review-baseline": 512_000_000,
    "platform-mvp-evidence": 32_000_000,
    "native-verifier-amd64": 1_650_000_000,
    "native-verifier-arm64": 1_650_000_000,
    "native-verifier-index": 32_000_000,
}


class TransitionAuditError(ValueError):
    """Historical evidence is missing or inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TransitionAuditError(message)


def canonical_json(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def digest(value):
    payload = value if isinstance(value, bytes) else canonical_json(value)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _object(value, label):
    if not isinstance(value, dict):
        raise TransitionAuditError(f"{label} must be an object")
    return value


def _keys(value, keys, label):
    _object(value, label)
    if set(value) != set(keys):
        raise TransitionAuditError(f"{label} has missing or unknown fields")
    return value


def _integer(value, label, minimum=1):
    if type(value) is not int or value < minimum:
        raise TransitionAuditError(f"{label} must be an integer >= {minimum}")
    return value


def _text(value, label, limit=512):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or any(ord(c) < 32 for c in value)
    ):
        raise TransitionAuditError(f"{label} must be bounded single-line text")
    return value


def verify_original_authority(projection, grant):
    """Check the retained original-message projection against the recorded grant.

    This is a historical consistency check, not fresh retrieval or independent
    human authentication. It can never approve a new operation.
    """
    names = (
        "decisionCard",
        "decisionApproval",
        "consumerCard",
        "consumerApproval",
        "activationPacket",
        "activationApproval",
    )
    _keys(
        projection,
        {"schemaVersion", "threadId", *names},
        "original authority projection",
    )
    if (
        projection["schemaVersion"]
        != "ofarm.ci-policy-transition-original-authority.v1"
        or projection["threadId"] != grant["decision"]["threadId"]
    ):
        raise TransitionAuditError("original authority task/schema differs")
    ids = set()
    for name in names:
        item = _keys(projection[name], {"id", "order", "role", "text"}, name)
        _text(item["id"], "original message reference")
        _integer(item["order"], "message order", 0)
        if item["id"] in ids or not isinstance(item["text"], str) or not item["text"]:
            raise TransitionAuditError("missing/duplicate original message")
        ids.add(item["id"])
        role = "user" if name.endswith("Approval") else "assistant"
        if item["role"] != role:
            raise TransitionAuditError("original message has the wrong author role")
    for prefix, decision, pr in (
        ("decision", grant["decision"], 417),
        ("consumer", grant["consumerDecision"], grant["consumerPr"]),
    ):
        card, approval = projection[prefix + "Card"], projection[prefix + "Approval"]
        if (
            card["id"] != decision["cardRef"]
            or approval["id"] != decision["approvalRef"]
            or card["order"] >= approval["order"]
        ):
            raise TransitionAuditError(
                "original card/approval ordering or binding differs"
            )
        expected = (
            f"I approve OFARM2 decision {decision['id']} version {decision['version']}."
        )
        if (
            approval["text"] != expected
            or decision["id"] not in card["text"]
            or f"#{pr}" not in card["text"]
        ):
            raise TransitionAuditError("original semantic approval/card does not match")
    packet, approval = projection["activationPacket"], projection["activationApproval"]
    if (
        packet["order"]
        <= max(
            projection["decisionApproval"]["order"],
            projection["consumerApproval"]["order"],
        )
        or approval["order"] <= packet["order"]
    ):
        raise TransitionAuditError("activation must follow both semantic approvals")
    for value in (
        grant["rootSha"],
        grant["headSha"],
        grant["baseSha"],
        grant["mergeSha"],
        grant["expiresAt"],
        grant["grantId"],
        digest(grant),
        grant["journal"]["genesisDigest"],
        grant["coverageDigest"],
    ):
        if value not in packet["text"]:
            raise TransitionAuditError("activation packet omits a frozen coordinate")
    packet_digest = digest(packet["text"].encode())
    expected = (
        f"I authorize OFARM2 CI transition grant {grant['grantId']} under packet {packet_digest} "
        f"using root {grant['rootSha']} for PR #{grant['consumerPr']} at head {grant['headSha']}, "
        f"base {grant['baseSha']} and merge {grant['mergeSha']}, until {grant['expiresAt']}, "
        "for one source and one publisher, attempt 1 only. Merge remains separate."
    )
    if approval["text"] != expected:
        raise TransitionAuditError("original exact-root activation approval differs")
    return {
        "purpose": "ORIGINAL_AUTHORITY_PROJECTION_CHECKED",
        "threadId": projection["threadId"],
        "messageRefs": {n: projection[n]["id"] for n in names},
        "grantDigest": digest(grant),
        "independentHumanAuthentication": False,
    }


def artifact_reference(document: Json, *, run_id: int, root_sha: str) -> Json:
    """Validate one provider artifact; provenance is the actual transition run."""
    name = document.get("name")
    _require(name in LIMITS, "artifact name is outside the transition inventory")
    artifact_id = ordinary._positive_int(document.get("id"), "artifact id")
    size = ordinary._positive_int(document.get("size_in_bytes"), "artifact size")
    digest = ordinary._sha256(document.get("digest"), "artifact digest")
    run = evidence._object(document.get("workflow_run"), "artifact workflow run")
    _require(
        run.get("id") == run_id and run.get("head_sha") == root_sha,
        "artifact belongs to a different transition run or root",
    )
    _require(document.get("expired") is False, "artifact has expired")
    _require(size <= LIMITS[name], "artifact exceeds its size limit")
    return {
        "name": name,
        "artifactId": artifact_id,
        "digest": digest,
        "size": size,
        "runId": run_id,
        "headSha": root_sha,
    }


def _single_document(root: Path, filename: str) -> Json:
    _require(
        evidence._regular_file_inventory(root) == frozenset({filename}),
        "ticket or receipt archive inventory is not exact",
    )
    return evidence._read_json_object(root / filename, filename)


def audit_consumed(
    *,
    journal: Any,
    archive_directory: Path,
    roots_directory: Path,
    root_manifest: Json,
    provider_reader: Any | None = None,
) -> Json:
    """Report historical byte integrity; this path has no live acceptance output."""

    state = journal.snapshot()
    _require(
        state["state"] == "RETIRED" and state.get("nativeMerge") is not None,
        "historical audit requires consumed acceptance and recorded native merge",
    )
    consumed = state["consumedTuple"]
    report = evidence._read_json_object(
        archive_directory / "acceptance.json", "archived acceptance"
    )
    _require(
        report.get("tuple") == consumed,
        "archived acceptance differs from the consumed tuple",
    )
    _require(
        operator.policy_closure_digest(report["closure"]) == consumed["closureDigest"],
        "archived closure differs from the consumed closure digest",
    )
    root_result = operator.verify_archived_closure(
        roots_directory, root_manifest, report["closure"], consumed
    )
    _require(
        any(
            item
            == {
                "rootSha": consumed["rootSha"],
                "rootTree": consumed["rootTree"],
                "baseSha": consumed["baseSha"],
            }
            for item in root_manifest["roots"]
        ),
        "archived roots omit the consumed root/tree/base",
    )
    # Receipt ZIP digest comes from the independent consumed journal, not this report.
    receipt_archive = (
        archive_directory / "archives" / f"{consumed['receiptArtifactId']}.zip"
    )
    _require(
        stat.S_ISREG(receipt_archive.stat(follow_symlinks=False).st_mode)
        and receipt_archive.stat().st_size <= LIMITS[RECEIPT_NAME],
        "historical receipt archive is not a bounded regular file",
    )
    _require(
        "sha256:" + evidence._sha256_hex_file(receipt_archive)
        == consumed["receiptDigest"],
        "historical receipt archive digest differs",
    )
    with tempfile.TemporaryDirectory(prefix="ofarm-transition-audit-") as directory:
        extracted = Path(directory).resolve()
        evidence._extract_verified_zip(receipt_archive, extracted, LIMITS[RECEIPT_NAME])
        receipt = _single_document(extracted, RECEIPT_FILE)
    _require(
        receipt.get("schemaVersion") == RECEIPT_SCHEMA,
        "historical archive does not contain a transition receipt",
    )
    authority = receipt["authority"]
    _require(
        all(
            authority.get(key) == consumed[key]
            for key in (
                "grantId",
                "rootSha",
                "rootTree",
                "closureDigest",
                "coverageDigest",
                "baseSha",
                "consumerPr",
                "headSha",
                "mergeSha",
            )
        ),
        "historical receipt authority differs from the consumed tuple",
    )
    _require(
        receipt["source"]["runId"] == consumed["sourceRunId"]
        and receipt["publisher"]["runId"] == consumed["publisherRunId"]
        and receipt["source"]["runAttempt"] == receipt["publisher"]["runAttempt"] == 1,
        "historical receipt run tuple differs",
    )
    refs = [*receipt["source"]["artifacts"], *receipt["artifacts"]]
    _require(
        [item["name"] for item in refs] == [*SOURCE_NAMES, *PUBLISHED_NAMES],
        "historical receipt inventories are incomplete",
    )
    ticket = refs[len(SOURCE_NAMES) - 1]
    _require(
        ticket["artifactId"] == consumed["ticketArtifactId"]
        and ticket["digest"] == consumed["ticketDigest"],
        "historical ticket differs from the consumed journal",
    )
    _require(
        digest(report["grant"]) == authority["grantDigest"],
        "archived grant differs from the receipt-bound grant",
    )
    verify_original_authority(report["originalAuthority"], report["grant"])
    expected_names = {f"{item['artifactId']}.zip" for item in refs} | {
        receipt_archive.name
    }
    _require(
        evidence._regular_file_inventory(archive_directory / "archives")
        == expected_names,
        "historical raw archive inventory is not exact",
    )
    provider_facts = []
    for ref in refs:
        path = archive_directory / "archives" / f"{ref['artifactId']}.zip"
        _require(
            path.stat().st_size == ref["size"]
            and path.stat().st_size <= LIMITS[ref["name"]],
            "historical artifact size differs",
        )
        _require(
            "sha256:" + evidence._sha256_hex_file(path) == ref["digest"],
            "historical artifact digest differs",
        )
        fact = {
            "artifactId": ref["artifactId"],
            "status": "unavailable",
            "reason": "no fresh provider reader supplied; archive bytes only",
        }
        if provider_reader is not None:
            try:
                observed = artifact_reference(
                    evidence._object(
                        provider_reader(
                            f"/repos/{state['coordinates']['repository']}/actions/artifacts/{ref['artifactId']}"
                        ),
                        "historical provider artifact",
                    ),
                    run_id=ref["runId"],
                    root_sha=ref["headSha"],
                )
                _require(
                    observed == ref, "historical provider artifact differs from archive"
                )
                fact = {"artifactId": ref["artifactId"], "status": "reauthenticated"}
            except TransitionAuditError as exc:
                fact["status"] = "mismatch"
                fact["reason"] = str(exc)
            except (OSError, ValueError, KeyError) as exc:
                fact["reason"] = str(exc)
        provider_facts.append(fact)
    return {
        "schemaVersion": "ofarm.ci-policy-transition-audit.v1",
        "purpose": "audit-consumed",
        "archiveIntegrity": True,
        "rootArchive": root_result,
        "tuple": consumed,
        "recordedNativeMerge": state["nativeMerge"],
        "originalAuthorityReferences": report["originalAuthority"],
        "providerFacts": provider_facts,
        "liveAcceptanceAuthority": False,
        "executionAuthority": False,
        "mergeAuthority": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", required=True, choices=("audit-consumed",))
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--journal-genesis", required=True)
    parser.add_argument("--archive-directory", type=Path, required=True)
    parser.add_argument("--roots-directory", type=Path, required=True)
    parser.add_argument("--roots-manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with operator.ConsumedJournal(
            args.journal, args.checkpoint, args.journal_genesis
        ) as journal:
            report = audit_consumed(
                journal=journal,
                archive_directory=args.archive_directory,
                roots_directory=args.roots_directory,
                root_manifest=evidence._read_json_object(
                    args.roots_manifest, "root archive manifest"
                ),
            )
        print(json.dumps(report, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError):
        print(
            "Historical CI transition audit refused; no authority output accepted",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
