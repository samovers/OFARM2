from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from conformance import temporal_decision_log_check as decision_log


def _entry() -> dict:
    return json.loads(decision_log.ENTRY_PATH.read_bytes())


def _refinalize(value: dict) -> tuple[dict, str, bytes]:
    candidate = copy.deepcopy(value)
    candidate.pop("entryDigest", None)
    digest = decision_log.digest_bytes(decision_log.canonical_json(candidate))
    candidate["entryDigest"] = digest
    filename = f"{digest.removeprefix('sha256:')}.json"
    return candidate, filename, decision_log.canonical_json(candidate)


def test_approved_temporal_decision_log_entry_is_exact_and_currentness_closed():
    decision_log.validate_decision_log()

    entry = _entry()
    assert entry["decidedAt"] == "2026-07-30T13:02:37.932Z"
    assert entry["supersedesEntryDigest"] is None
    assert entry["currentnessTraceRef"] == {
        "decisionCardDigest": decision_log.DECISION_CARD_DIGEST,
        "mechanism": "CONTAINING_ENTRY_AND_EXPLICIT_PREDECESSOR_CHAIN",
        "supersedesEntryDigest": None,
    }
    assert entry["decisionCardPayload"]["decision"] == ("PROMOTE_GOVERNED_INACTIVE")
    assert entry["decisionCardPayload"]["nonEffects"][-1] == ("ISSUE_192_EFFECT")


def test_temporal_decision_log_entry_bytes_and_filename_are_canonical():
    raw = decision_log.ENTRY_PATH.read_bytes()
    entry = json.loads(raw)

    assert not raw.endswith(b"\n")
    assert raw == decision_log.canonical_json(entry)
    assert len(raw) == decision_log.FINAL_ENTRY_CANONICAL_BYTE_LENGTH
    assert decision_log.ENTRY_PATH.name == (
        f"{decision_log.ENTRY_DIGEST.removeprefix('sha256:')}.json"
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "approval_role",
        "approval_reference",
        "decided_at",
        "promotion_reference",
        "review_evidence_order",
        "subject_digest",
        "predecessor",
        "extra_field",
    ),
)
def test_temporal_decision_log_rejects_recanonicalized_unapproved_content(
    mutation: str,
):
    entry = _entry()
    mutations = {
        "approval_role": lambda value: value["approvalEvidence"].update(
            {"approvalMessageRole": "assistant"}
        ),
        "approval_reference": lambda value: (
            value["approvalEvidence"].update(
                {"approvalUserMessageIdOrStableRef": "another-turn"}
            ),
            value["humanPromotionAuthorityRef"].update(
                {"approvalUserMessageIdOrStableRef": "another-turn"}
            ),
        ),
        "decided_at": lambda value: value.update(
            {"decidedAt": "2026-07-30T13:02:37.933Z"}
        ),
        "promotion_reference": lambda value: value["promotionDecisionRef"].update(
            {"decisionCardDigest": "sha256:" + ("0" * 64)}
        ),
        "review_evidence_order": lambda value: value["reviewEvidenceRefs"].reverse(),
        "subject_digest": lambda value: value["decisionCardPayload"]["subjects"][
            0
        ].update({"repositoryFileDigest": "sha256:" + ("0" * 64)}),
        "predecessor": lambda value: (
            value.update({"supersedesEntryDigest": "sha256:" + ("0" * 64)}),
            value["currentnessTraceRef"].update(
                {"supersedesEntryDigest": "sha256:" + ("0" * 64)}
            ),
            value["decisionCardPayload"].update(
                {"supersedesEntryDigest": "sha256:" + ("0" * 64)}
            ),
        ),
        "extra_field": lambda value: value.update({"unexpected": True}),
    }
    mutations[mutation](entry)
    candidate, filename, raw = _refinalize(entry)

    with pytest.raises(
        decision_log.TemporalDecisionLogError,
        match="fields differ|differs from approved decision|digest differs",
    ):
        decision_log.validate_entry(
            candidate,
            filename=filename,
            raw=raw,
        )


def test_temporal_decision_log_rejects_noncanonical_entry_bytes():
    entry = _entry()

    with pytest.raises(
        decision_log.TemporalDecisionLogError,
        match="not exact canonical JSON",
    ):
        decision_log.validate_entry(
            entry,
            filename=decision_log.ENTRY_PATH.name,
            raw=decision_log.canonical_json(entry) + b"\n",
        )


def test_temporal_decision_log_rejects_filename_not_bound_to_entry_digest():
    entry = _entry()

    with pytest.raises(
        decision_log.TemporalDecisionLogError,
        match="filename differs",
    ):
        decision_log.validate_entry(
            entry,
            filename=f"{'0' * 64}.json",
            raw=decision_log.canonical_json(entry),
        )


@pytest.mark.parametrize("directory_state", ("empty", "second_entry", "other_file"))
def test_temporal_decision_log_rejects_non_closed_log_directory(
    directory_state: str,
    tmp_path: Path,
):
    raw = decision_log.ENTRY_PATH.read_bytes()
    if directory_state != "empty":
        (tmp_path / decision_log.ENTRY_PATH.name).write_bytes(raw)
    if directory_state == "second_entry":
        (tmp_path / f"{'0' * 64}.json").write_bytes(raw)
    if directory_state == "other_file":
        (tmp_path / "README.md").write_text("not governed", encoding="utf-8")

    with pytest.raises(
        decision_log.TemporalDecisionLogError,
        match="exactly one first entry",
    ):
        decision_log.validate_decision_log(tmp_path)
