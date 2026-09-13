"""Legacy compliance self-review eligibility, RFC v0.1 E01–E03/E06.

Fictional records exercise real HTTP, public GatePipeline.commit and PostgreSQL
through fresh_env. Historical accepted-key replay and the unchanged authority,
evidence and correction controls remain in their existing compatibility suites.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from kernel import config, demo
from kernel.context import now_iso
from kernel.contracts import sha256_of
from kernel.legacy_m1.api import create_test_app
from kernel.tests.test_review_confirmation import (
    CONSEQUENCE_KIND,
    GOVERNED_TABLES,
    OMITTED,
    REVIEW_KIND,
    _assert_prior_records_unchanged,
    _assert_valid_replay,
    _commit,
    _snapshot,
)


def _id(prefix):
    return f"{prefix}:self-review-test.{uuid4().hex[:12]}"


@pytest.fixture
def env(fresh_env):
    store, pipeline, _ = fresh_env
    with TestClient(create_test_app(store, oidc=None)) as client:
        yield SimpleNamespace(store=store, pipeline=pipeline, client=client)


def _compliance(reviewer=None):
    submission = {
        "commitClass": "COMPLIANCE_ASSERTION",
        "actingPartyRef": demo.FARMER,
        "farmRef": demo.FARM,
        "idempotencyKey": _id("commit"),
        "eventTime": "2026-06-10T09:00:00Z",
        "evidenceRefs": [demo.PHOTO_EVIDENCE],
        "payload": {"complianceClaim": {
            "statement": "Fictional compliance claim requiring independent review",
            "assertedStatus": "CLAIMED_COMPLIANT",
            "governingRuleRefs": [config.EVIDENCE_POLICY_REF],
            "subjectScopeRef": demo.FARM,
        }},
        "confirmAccept": True,
    }
    if reviewer is not OMITTED:
        submission["reviewerPartyRef"] = reviewer
    return submission


def _truth(store):
    return {row["record_id"]: row
            for kind in (REVIEW_KIND, CONSEQUENCE_KIND)
            for row in store.find_by_kind(kind)}


def _assert_no_acceptance(store, result, before):
    assert not result.get("emittedReviewDecisionRefs")
    assert not result.get("emittedAcceptedConsequenceRefs")
    assert _truth(store) == before


def _assert_pending(store, result, before):
    assert result["decisionOutcome"] == "REQUIRE_REVIEW", result
    assert "HUMAN_APPROVAL_REQUIRED" in {
        problem["reasonCode"] for problem in result["problems"]}
    _assert_no_acceptance(store, result, before)
    assert len(result["emittedAssertionRecordRefs"]) == 1
    assertion_ref = result["emittedAssertionRecordRefs"][0]
    assertion = store.get_payload(assertion_ref)
    assert assertion["claimState"] == "PENDING_REVIEW"
    assert assertion["assertionType"] == "COMPLIANCE_ASSERTION"
    assert assertion["assertedByPartyRef"] == demo.FARMER
    assert store.edges_from(assertion_ref, "REVIEW") == []
    assert store.edges_from(assertion_ref, "LINEAGE_SUPERSEDES_INTENT") == []
    trace = store.get_payload(result["promotionTraceRef"])
    assert any(entry["gate"] == "VALIDATION" and entry["outcome"] == "PASS"
               for entry in trace["gateSequence"])
    assert trace["gateSequence"][-1]["gate"] == "REVIEW_PROMOTION"
    return assertion_ref


def _review(env, assertion_ref, actor, **extra):
    response = env.client.post(
        "/review/accept",
        json={
            "farmRef": demo.FARM,
            "assertionRef": assertion_ref,
            "rationale": "Fictional reviewer checked this claim and its evidence",
            "idempotencyKey": _id("accept"),
            **extra,
        },
        headers={"x-acting-party": actor},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_http_null_compliance_remains_reviewable_until_distinct_acceptance(env):
    """E01/E03: the same null-origin claim survives self-refusal and accepts once."""
    before = _snapshot(env.store)
    initial_truth = _truth(env.store)
    submission = _compliance()
    pending = _commit(env, submission)
    assertion_ref = _assert_pending(env.store, pending, initial_truth)
    assertion_row = env.store.get_record(assertion_ref)
    assert env.store.get_payload(pending["requestId"])["sourcePayloadDigest"] == \
        sha256_of(submission)

    self_review = _review(env, assertion_ref, demo.FARMER)
    assert self_review["decisionOutcome"] == "RETAIN_DRAFT", self_review
    assert self_review["problems"][0]["reasonCode"] == "HUMAN_APPROVAL_REQUIRED"
    _assert_no_acceptance(env.store, self_review, initial_truth)
    assert env.store.get_record(assertion_ref) == assertion_row
    assert env.store.edges_from(assertion_ref, "REVIEW") == []

    # Caller body hints cannot name the reviewer or backdate the actual decision.
    caller_time = "2001-01-01T00:00:00Z"
    started = now_iso()
    accepted = _review(env, assertion_ref, demo.ADVISOR,
                       actingPartyRef=demo.FARMER, decisionTime=caller_time)
    finished = now_iso()
    assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED", accepted
    assert len(accepted["emittedReviewDecisionRefs"]) == 1
    assert len(accepted["emittedAcceptedConsequenceRefs"]) == 1
    review_ref = accepted["emittedReviewDecisionRefs"][0]
    consequence_ref = accepted["emittedAcceptedConsequenceRefs"][0]
    after_acceptance = _truth(env.store)
    assert set(after_acceptance) - set(initial_truth) == {review_ref, consequence_ref}
    for record_id, row in initial_truth.items():
        assert after_acceptance[record_id] == row

    review = env.store.get_payload(review_ref)
    assert review["reviewAction"] == "REVIEW_ACCEPT"
    assert review["decisionOutcomeState"] == "ACCEPTED"
    assert review["decidedByPartyRef"] == demo.ADVISOR
    assert review["reviewedArtifactRef"] == assertion_ref
    assert started <= review["decidedAt"] <= finished
    assert review["decidedAt"] != caller_time
    consequence = env.store.get_payload(consequence_ref)
    assert consequence["consequenceType"] == "COMPLIANCE_STATUS_ACCEPTED"
    assert consequence["acceptedByReviewDecisionRef"] == review_ref
    assert consequence["sourceEventRef"] == pending["semanticEventRef"]
    assert consequence["inForceState"] == "IN_FORCE"
    assert started <= consequence["acceptedAt"] <= finished
    for source in (assertion_ref, consequence_ref):
        assert [edge["dst_record_id"] for edge in
                env.store.edges_from(source, "REVIEW")] == [review_ref]
    assert [edge["dst_record_id"] for edge in
            env.store.edges_from(consequence_ref, "EVENT_SOURCE")] == \
        [pending["semanticEventRef"]]
    assert env.store.edges_from(consequence_ref, "LINEAGE_SUPERSEDES") == []

    # The REVIEW edge derives the completed disposition; capture stays immutable.
    assert env.store.get_record(assertion_ref) == assertion_row
    assert assertion_row["payload"]["claimState"] == "PENDING_REVIEW"
    duplicate = _review(env, assertion_ref, demo.ADVISOR)
    assert duplicate["decisionOutcome"] == "RETAIN_DRAFT", duplicate
    assert duplicate["problems"][0]["reasonCode"] == "SUPERSEDED_RECORD_USED"
    _assert_no_acceptance(env.store, duplicate, after_acceptance)
    assert env.store.get_record(assertion_ref) == assertion_row
    assert [edge["dst_record_id"] for edge in
            env.store.edges_from(assertion_ref, "REVIEW")] == [review_ref]
    _assert_prior_records_unchanged(before, _snapshot(env.store))


@pytest.mark.parametrize("reviewer", [
    pytest.param(None, id="null"),
    pytest.param(OMITTED, id="omitted"),
    pytest.param(demo.FARMER, id="self"),
    pytest.param(demo.ADVISOR, id="body-named-distinct"),
])
def test_direct_compliance_reviewer_metadata_cannot_supply_review(env, reviewer):
    """E01/E02: public direct ingress preserves each raw body and requires review."""
    submission = _compliance(reviewer)
    original = deepcopy(submission)
    before = _snapshot(env.store)
    truth = _truth(env.store)
    result = env.pipeline.commit(submission)
    _assert_pending(env.store, result, truth)
    assert submission == original
    assert env.store.get_payload(result["requestId"])["sourcePayloadDigest"] == \
        sha256_of(original)
    _assert_prior_records_unchanged(before, _snapshot(env.store))


@pytest.mark.parametrize("confirmation", [
    pytest.param(OMITTED, id="omitted"),
    pytest.param(False, id="false"),
])
def test_http_unconfirmed_compliance_keeps_capture_only(env, confirmation):
    """E02: omitted and false confirmation retain ordinary compliance capture."""
    submission = _compliance()
    if confirmation is OMITTED:
        del submission["confirmAccept"]
    else:
        submission["confirmAccept"] = confirmation
    original = deepcopy(submission)
    before = _snapshot(env.store)
    truth = _truth(env.store)
    result = _commit(env, submission)

    assert result["decisionOutcome"] == "RETAIN_DRAFT", result
    assert result["problems"] == []
    _assert_no_acceptance(env.store, result, truth)
    assert len(result["emittedAssertionRecordRefs"]) == 1
    assertion_ref = result["emittedAssertionRecordRefs"][0]
    assertion = env.store.get_payload(assertion_ref)
    assert assertion["claimState"] == "PENDING_REVIEW"
    assert assertion["assertionType"] == "COMPLIANCE_ASSERTION"
    assert assertion["assertedByPartyRef"] == demo.FARMER
    assert env.store.edges_from(assertion_ref, "REVIEW") == []
    assert submission == original
    assert env.store.get_payload(result["requestId"])["sourcePayloadDigest"] == \
        sha256_of(original)
    after = _snapshot(env.store)
    promotion_logs = [row for row in after["kernel_gate_log"]
                      if row["request_id"] == result["requestId"]
                      and row["gate"] == "REVIEW_PROMOTION"]
    assert [(row["outcome"], row["reason_code"]) for row in promotion_logs] == \
        [("RETAIN_DRAFT", None)]
    _assert_prior_records_unchanged(before, after)


def test_http_pending_null_replay_preserves_raw_identity_and_history(env):
    """E06: matching pending replay adds receipts; null-to-omitted conflicts."""
    submission = _compliance()
    truth = _truth(env.store)
    original = _commit(env, submission)
    _assert_pending(env.store, original, truth)
    replay = _assert_valid_replay(env, submission, original)
    assert env.store.get_payload(replay["requestId"])["sourcePayloadDigest"] == \
        sha256_of(submission)

    omitted = deepcopy(submission)
    del omitted["reviewerPartyRef"]
    assert sha256_of(omitted) != sha256_of(submission)
    before = _snapshot(env.store)
    conflict = _commit(env, omitted)
    assert conflict["decisionOutcome"] == "DENY", conflict
    assert conflict["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
    assert conflict["problems"][0]["reasonCode"] == "IDEMPOTENCY_REPLAY_CONFLICT"
    assert not conflict.get("emittedAssertionRecordRefs")
    _assert_no_acceptance(env.store, conflict, truth)
    assert env.store.get_payload(conflict["requestId"])["sourcePayloadDigest"] == \
        sha256_of(omitted)
    after = _snapshot(env.store)
    _assert_prior_records_unchanged(before, after)
    for table in GOVERNED_TABLES:
        if table not in {"kernel_record", "kernel_gate_log"}:
            assert after[table] == before[table], table
