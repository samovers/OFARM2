"""Observation eligibility O01–O07 through real HTTP, pipeline and PostgreSQL.

Only fictional records and function-isolated disposable databases are used.
Historical acceptance comes from the pinned unmodified base runtime, never
from a candidate guard exception or hand-created accepted record.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from kernel import demo
from kernel.contracts import sha256_of
from kernel.gates import GatePipeline
from kernel.legacy_m1.api import create_test_app
from kernel.tests.observation_history import (  # noqa: F401
    BASE_COMMIT,
    BASE_TREE,
    observation_history,
)
from kernel.tests.test_correction_authorization import (
    _acceptance_submission,
    _actor,
    _grant,
)
from kernel.tests.test_review_confirmation import (
    CONSEQUENCE_KIND,
    OMITTED,
    REVIEW_KIND,
    _assert_prior_records_unchanged,
    _assert_valid_replay,
    _commit,
    _post,
    _snapshot,
)
from kernel.tests.test_runtime_bundle_receipts import _second_store


DISABLED = ("HIGH_CONSEQUENCE_BLOCKED", "Observation acceptance disabled")


def _id(prefix):
    return f"{prefix}:observation-eligibility.{uuid4().hex[:12]}"


@pytest.fixture
def env(fresh_env):
    store, pipeline, outputs = fresh_env
    with TestClient(create_test_app(store, oidc=None)) as client:
        yield SimpleNamespace(store=store, pipeline=pipeline,
                              outputs=outputs, client=client)


def _observation(*, actor=demo.FARMER, confirmation=True, reviewer=None):
    submission = {
        "commitClass": "OBSERVATION_ASSERTION", "actingPartyRef": actor,
        "farmRef": demo.FARM, "subjectType": "FIELD", "subjectRef": demo.FIELD,
        "idempotencyKey": _id("observation"), "eventTime": "2026-06-10T09:00:00Z",
        "evidenceRefs": [demo.PHOTO_EVIDENCE],
        "requestedPromotionTarget": "ACCEPTED_OBSERVATION_OCCURRENCE_STATE",
    }
    if confirmation is not OMITTED:
        submission["confirmAccept"] = confirmation
    if reviewer is not OMITTED:
        submission["reviewerPartyRef"] = reviewer
    return submission


def _truth(store):
    return {row["record_id"]: row
            for kind in (REVIEW_KIND, CONSEQUENCE_KIND)
            for row in store.find_by_kind(kind)}


def _no_acceptance(store, result, before):
    assert not result.get("emittedReviewDecisionRefs"), result
    assert not result.get("emittedAcceptedConsequenceRefs"), result
    assert _truth(store) == before


def _diagnostic(result):
    return [(p["reasonCode"], p["title"]) for p in result["problems"]]


def _pending(env, result, truth, *, confirmed=True, actor=demo.FARMER):
    assert result["decisionOutcome"] == "RETAIN_DRAFT", result
    assert _diagnostic(result) == ([DISABLED] if confirmed else [])
    _no_acceptance(env.store, result, truth)
    assert len(result["emittedAssertionRecordRefs"]) == 1
    target = result["emittedAssertionRecordRefs"][0]
    row = env.store.get_record(target)
    assert row["payload"]["assertionType"] == "OBSERVATION_ASSERTION"
    assert row["payload"]["claimState"] == "PENDING_REVIEW"
    assert row["payload"]["assertedByPartyRef"] == actor
    assert row["tenant_ref"] == env.store.tenant_ref
    assert row["runtime_bundle_digest"] == env.store.runtime_bundle_digest
    assert env.store.edges_from(target, "REVIEW") == []
    assert [edge["src_record_id"] for edge in
            env.store.edges_to(target, "PROMOTION_EMITS")] == [result["promotionTraceRef"]]
    trace = env.store.get_payload(result["promotionTraceRef"])
    assert any(g["gate"] == "VALIDATION" and g["outcome"] == "PASS"
               for g in trace["gateSequence"])
    assert trace["gateSequence"][-1]["gate"] == "REVIEW_PROMOTION"
    return target


def _review(env, target, *, actor=demo.ADVISOR, kind="accept", **extra):
    response = env.client.post(f"/review/{kind}", json={
        "farmRef": demo.FARM, "assertionRef": target,
        "rationale": "Fictional reviewer checked the observation and evidence",
        "idempotencyKey": _id(kind), **extra,
    }, headers={"x-acting-party": actor})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("confirmation", [
    pytest.param(True, id="true"), pytest.param(OMITTED, id="omitted"),
    pytest.param(False, id="false"),
])
@pytest.mark.parametrize("reviewer", [
    pytest.param(OMITTED, id="reviewer-omitted"), pytest.param(None, id="reviewer-null"),
    pytest.param(demo.FARMER, id="reviewer-self"),
    pytest.param(demo.ADVISOR, id="reviewer-distinct"),
])
def test_observation_capture_matrix_http_and_direct(env, confirmation, reviewer):
    """O01/O02: both public entries retain capture and exact raw identity."""
    for commit in (lambda sub: _commit(env, sub), env.pipeline.commit):
        submission = _observation(confirmation=confirmation, reviewer=reviewer)
        original = deepcopy(submission)
        before, truth = _snapshot(env.store), _truth(env.store)
        result = commit(submission)
        target = _pending(env, result, truth, confirmed=confirmation is True)
        assert env.store.edges_from(target, "LINEAGE_SUPERSEDES_INTENT") == []
        assert submission == original
        assert env.store.get_payload(result["requestId"])["sourcePayloadDigest"] == \
            sha256_of(original)
        after = _snapshot(env.store)
        logs = [row for row in after["kernel_gate_log"]
                if row["request_id"] == result["requestId"]
                and row["gate"] == "REVIEW_PROMOTION"]
        reason = DISABLED[0] if confirmation is True else None
        assert [(row["outcome"], row["reason_code"]) for row in logs] == \
            [("RETAIN_DRAFT", reason)]
        _assert_prior_records_unchanged(before, after)
        assert env.store.unreachable_authoritative_records() == []


def test_same_observation_survives_acceptance_refusals_then_terminal_rejection(env):
    """O03: the refusal does not consume the claim; lawful reject still does."""
    # Grant reject explicitly so self-rejection reaches the relationship check.
    _grant(env.store, demo.FARMER, ("REVIEW_REJECT_OR_CONTEST",))
    before, truth = _snapshot(env.store), _truth(env.store)
    captured = _commit(env, _observation())
    target = _pending(env, captured, truth)
    target_row = env.store.get_record(target)
    for actor, diagnostic in ((demo.FARMER, ("HUMAN_APPROVAL_REQUIRED", "Self-review out of scope")),
                              (demo.ADVISOR, DISABLED)):
        refused = _review(env, target, actor=actor,
                          actingPartyRef=demo.FARMER, assertionType="OPERATION_CLAIM_ASSERTION")
        assert refused["decisionOutcome"] == "RETAIN_DRAFT", refused
        assert _diagnostic(refused) == [diagnostic]
        assert not refused.get("emittedAssertionRecordRefs")
        _no_acceptance(env.store, refused, truth)
        assert env.store.get_record(target) == target_row
        assert env.store.edges_from(target, "REVIEW") == []
        assert target in {p["assertionRef"] for p in env.outputs._pending_claims(demo.FARM)}

    # Direct callers can supply extra raw fields that the HTTP body model
    # discards. Neither those fields nor reviewer hints replace the stored type.
    forged = dict(_acceptance_submission(target, demo.ADVISOR),
                  assertionType="OPERATION_CLAIM_ASSERTION", reviewerPartyRef=demo.FARMER)
    direct_refusal = env.pipeline.commit(forged)
    assert _diagnostic(direct_refusal) == [DISABLED]
    _no_acceptance(env.store, direct_refusal, truth)
    assert env.store.get_payload(direct_refusal["requestId"])["sourcePayloadDigest"] == sha256_of(forged)
    assert env.store.edges_from(target, "REVIEW") == []

    self_rejection = _review(env, target, actor=demo.FARMER, kind="reject")
    assert _diagnostic(self_rejection) == [("HUMAN_APPROVAL_REQUIRED", "Self-review out of scope")]
    _no_acceptance(env.store, self_rejection, truth)
    rejected = _review(env, target, kind="reject", evidenceRefs=[demo.PHOTO_EVIDENCE])
    assert rejected["decisionOutcome"] == "RETAIN_DRAFT", rejected
    assert rejected["problems"] == []
    assert not rejected.get("emittedAcceptedConsequenceRefs")
    assert len(rejected["emittedReviewDecisionRefs"]) == 1
    review_ref = rejected["emittedReviewDecisionRefs"][0]
    review = env.store.get_payload(review_ref)
    assert review["decisionOutcomeState"] == "REJECTED"
    assert review["reviewAction"] == "REVIEW_REJECT_OR_CONTEST"
    assert review["decidedByPartyRef"] == demo.ADVISOR
    assert review["reviewedArtifactRef"] == target
    assert env.store.get_record(target) == target_row
    assert [edge["dst_record_id"] for edge in env.store.edges_from(target, "REVIEW")] == [review_ref]
    assert target not in {p["assertionRef"] for p in env.outputs._pending_claims(demo.FARM)}
    after_rejection = _truth(env.store)
    assert set(after_rejection) - set(truth) == {review_ref}
    for kind in ("accept", "reject"):
        duplicate = _review(env, target, kind=kind)
        assert _diagnostic(duplicate) == [("SUPERSEDED_RECORD_USED", "Target already reviewed")]
        _no_acceptance(env.store, duplicate, after_rejection)
    _assert_prior_records_unchanged(before, _snapshot(env.store))
    assert env.store.unreachable_authoritative_records() == []


def test_observation_capture_needs_creation_grant_but_accept_grant_cannot_enable_it(env):
    """O04: creation-only authority captures; adding review rights never accepts."""
    actor = _actor(env.store, ("OBSERVE_CREATE_OBSERVATION",))
    for confirmation in (False, True):
        truth = _truth(env.store)
        result = _commit(env, _observation(actor=actor, confirmation=confirmation))
        _pending(env, result, truth, confirmed=confirmation, actor=actor)
    _grant(env.store, actor, ("REVIEW_ACCEPT", "REVIEW_SUPERSEDE"))
    truth = _truth(env.store)
    result = _commit(env, _observation(actor=actor))
    _pending(env, result, truth, actor=actor)


@pytest.mark.parametrize("condition, reason, gate", [
    ("no-authority", "AUTHORITY_DENIED", "AUTHORITY"),
    ("no-durable-evidence", "EVIDENCE_INSUFFICIENT", "EVIDENCE_SUFFICIENCY"),
    ("wrong-target", "HIGH_CONSEQUENCE_BLOCKED", "VALIDATION"),
    ("wrong-subject-type", "IDENTITY_UNRESOLVED", "VALIDATION"),
    ("wrong-farm-subject", "SCOPE_NOT_AUTHORIZED", "VALIDATION"),
])
def test_observation_keeps_earlier_direct_refusals(env, condition, reason, gate):
    """O04: compatible target maps and earlier capture checks remain active."""
    submission = _observation()
    if condition == "no-authority":
        submission["actingPartyRef"] = _actor(env.store, ("REVIEW_ACCEPT",))
    elif condition == "no-durable-evidence":
        submission["evidenceRefs"] = [demo.FARMER]
    elif condition == "wrong-target":
        submission["requestedPromotionTarget"] = "COMPLIANCE_FACT"
    elif condition == "wrong-subject-type":
        submission["subjectType"] = "TENANT"
    else:
        submission.update(subjectType="FARM", subjectRef="farm:fictional.other")
    truth = _truth(env.store)
    result = _commit(env, submission)
    assert result["decisionOutcome"] != "PROMOTE_ACCEPTED", result
    assert result["problems"][0]["reasonCode"] == reason
    assert DISABLED not in _diagnostic(result)
    assert env.store.get_payload(result["promotionTraceRef"])["gateSequence"][-1]["gate"] == gate
    _no_acceptance(env.store, result, truth)


@pytest.mark.parametrize("condition, reason", [
    ("no-authority", "AUTHORITY_DENIED"),
    ("wrong-target", "EVIDENCE_REFERENCE_UNAVAILABLE"),
    ("no-rationale", "EVIDENCE_INSUFFICIENT"),
    ("wrong-evidence", "EVIDENCE_REFERENCE_UNAVAILABLE"),
])
def test_observation_keeps_earlier_queue_refusals(env, condition, reason):
    truth = _truth(env.store)
    captured = _commit(env, _observation(confirmation=False))
    target = _pending(env, captured, truth, confirmed=False)
    actor, supplied_target, extra = demo.ADVISOR, target, {}
    if condition == "no-authority":
        actor = _actor(env.store, ("OBSERVE_CREATE_OBSERVATION",))
    elif condition == "wrong-target":
        supplied_target = demo.FARMER
    elif condition == "no-rationale":
        extra["rationale"] = "   "
    else:
        extra["evidenceRefs"] = [demo.FARMER]
    result = _review(env, supplied_target, actor=actor, **extra)
    assert result["problems"][0]["reasonCode"] == reason
    assert DISABLED not in _diagnostic(result)
    _no_acceptance(env.store, result, truth)
    assert env.store.edges_from(target, "REVIEW") == []


def test_observation_cross_bundle_acceptance_keeps_prior_refusal(env):
    truth = _truth(env.store)
    captured = _commit(env, _observation(confirmation=False))
    target = _pending(env, captured, truth, confirmed=False)
    other = _second_store(env.store)
    try:
        assert other.runtime_bundle_digest != env.store.runtime_bundle_digest
        result = GatePipeline(other).commit(_acceptance_submission(target, demo.ADVISOR))
        assert _diagnostic(result) == [("PACK_CONFLICT", "Cross-bundle acceptance refused")]
        _no_acceptance(other, result, truth)
        assert other.edges_from(target, "REVIEW") == []
    finally:
        other.close()


@pytest.mark.parametrize("confirmation", [None, "true", 1, []])
def test_observation_transport_refusals_precede_all_durable_effects(env, confirmation):
    """O02: actual observation bodies preserve 403 before malformed 422."""
    submission = _observation(confirmation=confirmation)
    before = _snapshot(env.store)
    mismatch = _post(env, submission, actor=demo.WORKER)
    assert mismatch.status_code == 403
    assert mismatch.json()["detail"]["reasonCode"] == "ACTOR_BINDING_UNRESOLVED"
    assert _snapshot(env.store) == before
    malformed = _post(env, submission)
    assert malformed.status_code == 422
    assert malformed.json() == {"detail": "malformed ingress submission header"}
    assert _snapshot(env.store) == before


def test_observation_late_failure_rolls_back_capture_and_retry_stays_inert(env, monkeypatch):
    """O07: fail after the real final write; no partial capture or key survives."""
    submission = _observation()
    before, truth = _snapshot(env.store), _truth(env.store)
    prior_assertions = env.store.find_by_kind("ofarm.assertionrecord.v0.1")
    original_claim = env.store.idempotency_claim

    def fail_after_claim(*args, **kwargs):
        original_claim(*args, **kwargs)
        assert len(env.store.find_by_kind("ofarm.assertionrecord.v0.1")) == len(prior_assertions) + 1
        raise RuntimeError("fictional observation failure after idempotency write")

    with monkeypatch.context() as patch:
        patch.setattr(env.store, "idempotency_claim", fail_after_claim)
        with pytest.raises(RuntimeError, match="fictional observation failure"):
            env.pipeline.commit(submission)
    assert _snapshot(env.store) == before
    captured = _commit(env, submission)
    _pending(env, captured, truth)
    _assert_valid_replay(env, submission, captured)
    changed = dict(submission, confirmAccept=False)
    conflicting = _commit(env, changed)
    assert _diagnostic(conflicting)[0][0] == "IDEMPOTENCY_REPLAY_CONFLICT"
    _no_acceptance(env.store, conflicting, truth)
    assert env.store.unreachable_authoritative_records() == []


def test_real_base_history_replays_but_fresh_observation_acceptance_stays_disabled(
        observation_history):  # noqa: F811 — imported pytest fixture
    """O01/O05/O06: one retained database crosses unmodified base to candidate."""
    env = observation_history("replay")
    history = env.history
    assert history["source"]["commit"] == BASE_COMMIT
    assert history["source"]["tree"] == BASE_TREE
    assert "kernel/stages.py" in history["source"]["importedSources"]
    truth = _truth(env.store)
    _assert_prior_records_unchanged(history["snapshot"], _snapshot(env.store))
    old = history["predecessor"]
    predecessor = env.store.get_record(old)

    # Reuse exactly the stable original normalized bodies. In particular, a
    # repeated /review/accept would generate a NEW decisionTime and not replay.
    assert set(history["direct_acceptances"]) == {"omitted", "null", "self"}
    for fixture in (*history["direct_acceptances"].values(), history["queued_acceptance"]):
        original, submission = fixture["result"], fixture["submission"]
        assert original["decisionOutcome"] == "PROMOTE_ACCEPTED"
        assert len(original["emittedReviewDecisionRefs"]) == 1
        assert len(original["emittedAcceptedConsequenceRefs"]) == 1
        replay = _assert_valid_replay(env, submission, original)
        assert env.store.get_payload(replay["requestId"])["sourcePayloadDigest"] == \
            sha256_of(submission)
        assert _truth(env.store) == truth

    for fixture in history["direct_acceptances"].values():
        fresh = dict(fixture["submission"], idempotencyKey=_id("fresh"))
        captured = _commit(env, fresh)
        _pending(env, captured, truth, actor=env.reviewer)
    terminal = dict(history["queued_acceptance"]["submission"], idempotencyKey=_id("fresh"))
    refused = _commit(env, terminal)
    assert _diagnostic(refused) == [("SUPERSEDED_RECORD_USED", "Target already reviewed")]
    _no_acceptance(env.store, refused, truth)

    for name in ("pending_observation", "pending_correction"):
        target = history[name]
        old_row = env.store.get_record(target)
        assert old_row["payload"]["claimState"] == "PENDING_REVIEW"
        blocked = _review(env, target, actor=env.reviewer)
        assert blocked["decisionOutcome"] == "RETAIN_DRAFT", blocked
        assert _diagnostic(blocked) == [DISABLED]
        assert not blocked.get("emittedAssertionRecordRefs")
        _no_acceptance(env.store, blocked, truth)
        assert env.store.get_record(target) == old_row
        assert env.store.edges_from(target, "REVIEW") == []
    assert [edge["dst_record_id"] for edge in env.store.edges_from(
        history["pending_correction"], "LINEAGE_SUPERSEDES_INTENT")] == [old]
    assert not env.store.is_superseded(old)

    # Existing accepted observations remain readable and contestable. Contest
    # appends a dispute; the old consequence bytes and acceptance stay in force.
    read = env.client.get(f"/records/{old}", headers={"x-acting-party": demo.FARMER})
    assert read.status_code == 200, read.text
    contest = env.client.post("/review/contest", json={
        "farmRef": demo.FARM, "consequenceRef": old,
        "rationale": "Fictional historical observation remains disputed",
        "idempotencyKey": _id("contest"),
    }, headers={"x-acting-party": env.reviewer})
    assert contest.status_code == 200, contest.text
    disputed = contest.json()
    assert disputed["decisionOutcome"] == "RETAIN_DRAFT", disputed
    assert not disputed.get("emittedAcceptedConsequenceRefs")
    assert len(disputed["emittedReviewDecisionRefs"]) == 1
    review_ref = disputed["emittedReviewDecisionRefs"][0]
    assert env.store.get_payload(review_ref)["decisionOutcomeState"] == "CONTESTED"
    assert [edge["dst_record_id"] for edge in env.store.edges_from(old, "DISPUTE")] == [review_ref]
    assert env.store.get_record(old) == predecessor

    # Even the fully authorized reviewer cannot create a correction successor
    # to remove that dispute. Only the validated inert intent is retained.
    truth = _truth(env.store)
    correction = dict(history["correction"], idempotencyKey=_id("correction"),
                      actingPartyRef=env.reviewer, confirmAccept=True)
    corrected = _commit(env, correction)
    target = _pending(env, corrected, truth, actor=env.reviewer)
    assert [edge["dst_record_id"] for edge in env.store.edges_from(
        target, "LINEAGE_SUPERSEDES_INTENT")] == [old]
    assert env.store.edges_to(old, "LINEAGE_SUPERSEDES") == []
    assert not env.store.is_superseded(old)
    assert env.store.get_record(old) == predecessor
    assert env.store.get_payload(old)["inForceState"] == "IN_FORCE"
    _assert_prior_records_unchanged(history["snapshot"], _snapshot(env.store))
    assert env.store.unreachable_authoritative_records() == []
