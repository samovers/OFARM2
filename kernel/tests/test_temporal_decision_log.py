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
    assert entry["decisionCardPayload"]["decision"] == "PROMOTE_GOVERNED_INACTIVE"
    assert entry["decisionCardPayload"]["nonEffects"][-1] == "ISSUE_192_EFFECT"


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
        "card_decision",
        "card_key_removed",
        "subject_shape",
        "predecessor",
        "extra_field",
    ),
)
def test_temporal_decision_log_rejects_recanonicalized_unapproved_content(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
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
        "card_decision": lambda value: value["decisionCardPayload"].update(
            {"decision": "REFUSE_PROMOTION"}
        ),
        "card_key_removed": lambda value: value["decisionCardPayload"].pop(
            "decisionEffect"
        ),
        "subject_shape": lambda value: value["decisionCardPayload"].update(
            {"subjects": [1, 2, 3]}
        ),
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
    evidence_error = "decision-log evidence differs from approved decision"
    expected_errors = {
        "approval_role": evidence_error,
        "approval_reference": evidence_error,
        "decided_at": evidence_error,
        "promotion_reference": evidence_error,
        "review_evidence_order": evidence_error,
        "subject_digest": "approved decision-card digest differs",
        "card_decision": "decision-card differs from approved decision",
        "card_key_removed": "decision-card fields differ",
        "subject_shape": "decision-card subjects differ",
        "predecessor": evidence_error,
        "extra_field": "decision-log entry fields differ",
    }
    monkeypatch.setattr(
        decision_log,
        "ENTRY_DIGEST",
        candidate["entryDigest"],
    )
    monkeypatch.setattr(
        decision_log,
        "ENTRY_FILE_DIGEST",
        decision_log.digest_bytes(raw),
    )
    monkeypatch.setattr(
        decision_log,
        "FINAL_ENTRY_CANONICAL_BYTE_LENGTH",
        len(raw),
    )

    with pytest.raises(decision_log.TemporalDecisionLogError) as exc_info:
        decision_log.validate_entry(
            candidate,
            filename=filename,
            raw=raw,
        )
    assert str(exc_info.value) == expected_errors[mutation]


def test_temporal_decision_log_rejects_changed_entry_digest_pin():
    entry = _entry()
    entry["decidedAt"] = "2026-07-30T13:02:37.933Z"
    candidate, filename, raw = _refinalize(entry)

    with pytest.raises(decision_log.TemporalDecisionLogError) as exc_info:
        decision_log.validate_entry(
            candidate,
            filename=filename,
            raw=raw,
        )
    assert str(exc_info.value) == "decision-log entry digest differs"


def test_temporal_decision_log_rejects_claimed_pinned_digest_for_changed_body():
    entry = _entry()
    entry["decidedAt"] = "2026-07-30T13:02:37.933Z"
    raw = decision_log.canonical_json(entry)

    with pytest.raises(decision_log.TemporalDecisionLogError) as exc_info:
        decision_log.validate_entry(
            entry,
            filename=decision_log.ENTRY_PATH.name,
            raw=raw,
        )
    assert str(exc_info.value) == "decision-log entry digest differs"


def test_temporal_decision_log_rejects_changed_file_pin(
    monkeypatch: pytest.MonkeyPatch,
):
    entry = _entry()
    raw = decision_log.canonical_json(entry)
    monkeypatch.setattr(
        decision_log,
        "ENTRY_FILE_DIGEST",
        "sha256:" + ("0" * 64),
    )

    with pytest.raises(decision_log.TemporalDecisionLogError) as exc_info:
        decision_log.validate_entry(
            entry,
            filename=decision_log.ENTRY_PATH.name,
            raw=raw,
        )
    assert str(exc_info.value) == "decision-log entry file pin differs"


def test_temporal_decision_log_rejects_tampered_pinned_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    tampered_authority = tmp_path / "authority.md"
    tampered_authority.write_bytes(b"tampered")
    monkeypatch.setattr(
        decision_log,
        "PINNED_FILES",
        ((tampered_authority, decision_log.BASE_CONTRACT_DIGEST),),
    )

    with pytest.raises(decision_log.TemporalDecisionLogError) as exc_info:
        decision_log.validate_decision_log()
    assert str(exc_info.value) == "pinned authority differs: authority.md"


def test_temporal_decision_log_rejects_invalid_utf8_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    (tmp_path / decision_log.ENTRY_PATH.name).write_bytes(b"\xff")
    monkeypatch.setattr(decision_log, "PINNED_FILES", ())
    monkeypatch.setattr(decision_log, "LOG_PATH", tmp_path)

    assert decision_log.main() == 1
    assert capsys.readouterr().out == (
        "TEMPORAL DECISION LOG FAIL: decision-log entry is not UTF-8 JSON\n"
    )


@pytest.mark.parametrize("constant", ("NaN", "Infinity", "-Infinity"))
def test_temporal_decision_log_rejects_non_json_numeric_constants(
    constant: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    (tmp_path / decision_log.ENTRY_PATH.name).write_bytes(
        f'{{"value":{constant}}}'.encode()
    )
    monkeypatch.setattr(decision_log, "PINNED_FILES", ())

    with pytest.raises(decision_log.TemporalDecisionLogError) as exc_info:
        decision_log.validate_decision_log(tmp_path)
    assert str(exc_info.value) == (
        "decision-log entry contains non-JSON numeric constant"
    )


def test_temporal_decision_log_rejects_finite_syntax_numeric_overflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    raw = decision_log.ENTRY_PATH.read_bytes()
    raw = raw.replace(
        b'"decidedAt":"2026-07-30T13:02:37.932Z"',
        b'"decidedAt":1e309',
    )
    (tmp_path / decision_log.ENTRY_PATH.name).write_bytes(raw)
    monkeypatch.setattr(decision_log, "PINNED_FILES", ())
    monkeypatch.setattr(decision_log, "LOG_PATH", tmp_path)

    assert decision_log.main() == 1
    captured = capsys.readouterr()
    assert captured.out == (
        "TEMPORAL DECISION LOG FAIL: "
        "decision-log entry contains non-finite JSON number\n"
    )
    assert captured.err == ""


def test_temporal_decision_log_main_reports_pass(
    capsys: pytest.CaptureFixture[str],
):
    assert decision_log.main() == 0
    assert capsys.readouterr().out == "TEMPORAL DECISION LOG PASS\n"


def test_temporal_decision_log_approval_sentence_digest_constant_is_pinned():
    assert (
        decision_log.digest_bytes(decision_log.APPROVAL_SENTENCE.encode("utf-8"))
        == decision_log.APPROVAL_SENTENCE_DIGEST
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
