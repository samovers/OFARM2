"""Approved legacy confirmation admission, RFC v0.1 R01–R04/R06.

Real legacy HTTP requests and PostgreSQL state, with fictional demo records in
the existing function-isolated database harness. Queue decisions and correction
authority retain their dedicated compatibility suites.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from kernel import demo
from kernel.context import now_iso
from kernel.contracts import sha256_of
from kernel.legacy_m1.api import create_test_app


OMITTED = object()
CONSEQUENCE_KIND = "ofarm.acceptedeventconsequence.v0.1"
REVIEW_KIND = "ofarm.reviewdecision.v0.1"
GOVERNED_TABLES = (
    "kernel_record", "kernel_edge", "kernel_gate_log", "kernel_idempotency",
    "derived_materialization", "derived_dependency_index", "runtime_trace",
    "reference_snapshot_data", "export_artifact",
)


def _id(prefix):
    return f"{prefix}:confirmation-test.{uuid4().hex[:12]}"


@pytest.fixture
def env(fresh_env):
    store, _, _ = fresh_env
    with TestClient(create_test_app(store, oidc=None)) as client:
        yield SimpleNamespace(store=store, client=client)


def _submission(**kwargs):
    return demo.spray_submission(_id("commit"), erp_id=_id("erp"), **kwargs)


def _post(env, submission, *, actor=None):
    return env.client.post(
        "/commit", json={"submission": submission},
        headers={"x-acting-party": actor or submission["actingPartyRef"]},
    )


def _commit(env, submission):
    response = _post(env, submission)
    assert response.status_code == 200, response.text
    return response.json()


def _snapshot(store):
    """Keep every column, including stored payloads, digests and times."""
    with store.tx() as cur:
        state = {}
        for table in GOVERNED_TABLES:
            cur.execute(sql.SQL(
                "SELECT to_jsonb(t) AS row FROM {} AS t ORDER BY to_jsonb(t)::text"
            ).format(sql.Identifier(table)))
            state[table] = [row["row"] for row in cur.fetchall()]
    return state


def _assert_prior_records_unchanged(before, after):
    current = {row["record_id"]: row for row in after["kernel_record"]}
    for row in before["kernel_record"]:
        assert current[row["record_id"]] == row


def _assert_valid_replay(env, submission, original):
    before = _snapshot(env.store)
    replay = _commit(env, submission)
    assert replay["decisionOutcome"] == "REPLAY_REUSED_RESULT", replay
    assert replay["idempotencyDisposition"] == "REPLAY_MATCH_REUSED_RESULT"
    assert replay["replayOfRequestId"] == original["requestId"]
    for field in ("emittedAssertionRecordRefs", "emittedReviewDecisionRefs",
                  "emittedAcceptedConsequenceRefs"):
        assert replay.get(field, []) == original.get(field, [])

    after = _snapshot(env.store)
    _assert_prior_records_unchanged(before, after)
    # Valid replay appends its receipt; it does not change any semantic record,
    # edge, claimed key, materialization or runtime evidence.
    prior_ids = {row["record_id"] for row in before["kernel_record"]}
    added = [row for row in after["kernel_record"]
             if row["record_id"] not in prior_ids]
    assert len(added) == 3
    assert {row["record_kind"] for row in added} == {
        "ofarm.commitingressrequest.v0.1", "ofarm.commitingressresult.v0.1",
        "ofarm.promotiontrace.v0.1",
    }
    assert len(after["kernel_gate_log"]) == len(before["kernel_gate_log"]) + 1
    for row in before["kernel_gate_log"]:
        assert row in after["kernel_gate_log"]
    for table in GOVERNED_TABLES:
        if table not in {"kernel_record", "kernel_gate_log"}:
            assert after[table] == before[table], table
    return replay


@pytest.mark.parametrize("confirmation, expected", [
    pytest.param(OMITTED, "RETAIN_DRAFT", id="omitted"),
    pytest.param(False, "RETAIN_DRAFT", id="false"),
    pytest.param(True, "PROMOTE_ACCEPTED", id="true"),
    pytest.param(None, "MALFORMED", id="null"),
    pytest.param("false", "MALFORMED", id="false-string"),
    pytest.param("true", "MALFORMED", id="true-string"),
    pytest.param("", "MALFORMED", id="empty-string"),
    pytest.param(0, "MALFORMED", id="integer-zero"),
    pytest.param(1, "MALFORMED", id="integer-one"),
    pytest.param(0.0, "MALFORMED", id="float-zero"),
    pytest.param(1.0, "MALFORMED", id="float-one"),
    pytest.param([], "MALFORMED", id="empty-array"),
    pytest.param(["confirm"], "MALFORMED", id="nonempty-array"),
    pytest.param({}, "MALFORMED", id="empty-object"),
    pytest.param({"confirm": True}, "MALFORMED", id="nonempty-object"),
])
def test_http_confirmation_value_matrix_preserves_history(env, confirmation, expected):
    """R01–R04/R06: 15 values, including malformed accepted-key replays."""
    accepted_submission = _submission()
    accepted = _commit(env, accepted_submission)
    assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED", accepted
    before = _snapshot(env.store)

    submission = _submission()
    if confirmation is OMITTED:
        del submission["confirmAccept"]
    else:
        submission["confirmAccept"] = confirmation
    # This caller time and claimed digest confer neither review timing nor
    # replay identity. The server retains the raw confirmation distinction.
    submission["decisionTime"] = "2001-01-01T00:00:00Z"
    raw_digest = sha256_of(submission)
    submission["sourcePayloadDigest"] = "sha256:" + "0" * 64
    started = now_iso()
    response = _post(env, submission)
    finished = now_iso()

    if expected == "MALFORMED":
        assert response.status_code == 422, response.text
        assert response.json() == {"detail": "malformed ingress submission header"}
        assert _snapshot(env.store) == before
        replay_submission = deepcopy(accepted_submission)
        replay_submission["confirmAccept"] = confirmation
        replay = _post(env, replay_submission)
        assert replay.status_code == 422, replay.text
        assert replay.json() == {"detail": "malformed ingress submission header"}
        assert _snapshot(env.store) == before
        return

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["decisionOutcome"] == expected, result
    ingress = env.store.get_payload(result["requestId"])
    assert ingress["sourcePayloadDigest"] == raw_digest
    assert ingress["sourcePayloadDigest"] != submission["sourcePayloadDigest"]
    assert len(result["emittedAssertionRecordRefs"]) == 1
    assertion_ref = result["emittedAssertionRecordRefs"][0]
    assertion = env.store.get_payload(assertion_ref)
    if expected == "RETAIN_DRAFT":
        assert assertion["claimState"] == "PENDING_REVIEW"
        assert not result.get("emittedReviewDecisionRefs")
        assert not result.get("emittedAcceptedConsequenceRefs")
        assert env.store.edges_from(assertion_ref, "REVIEW") == []
    else:
        assert assertion["claimState"] == "IN_FORCE"
        assert len(result["emittedReviewDecisionRefs"]) == 1
        assert len(result["emittedAcceptedConsequenceRefs"]) == 1
        review_ref = result["emittedReviewDecisionRefs"][0]
        review = env.store.get_payload(review_ref)
        consequence = env.store.get_payload(result["emittedAcceptedConsequenceRefs"][0])
        assert review["decidedByPartyRef"] == submission["actingPartyRef"]
        assert review["reviewAction"] == "REVIEW_ACCEPT"
        assert review["reviewedArtifactRef"] == assertion_ref
        assert review["decisionOutcomeState"] == "ACCEPTED"
        assert started <= review["decidedAt"] <= finished
        assert review["decidedAt"] != submission["decisionTime"]
        assert started <= consequence["acceptedAt"] <= finished
        assert consequence["acceptedByReviewDecisionRef"] == review_ref
    _assert_prior_records_unchanged(before, _snapshot(env.store))
    replay = _assert_valid_replay(env, submission, result)
    assert env.store.get_payload(replay["requestId"])["sourcePayloadDigest"] == raw_digest
    assert env.store.unreachable_authoritative_records() == []


def test_omission_false_and_true_keep_distinct_raw_replay_identity(env):
    """R03: changing only confirmation is a conflicting body, even false."""
    omitted = _submission()
    del omitted["confirmAccept"]
    raw_digests = {sha256_of(omitted)}
    original = _commit(env, omitted)
    assert original["decisionOutcome"] == "RETAIN_DRAFT", original
    before = _snapshot(env.store)
    for value in (False, True):
        changed = dict(omitted, confirmAccept=value)
        raw_digests.add(sha256_of(changed))
        result = _commit(env, changed)
        assert result["decisionOutcome"] == "DENY", result
        assert result["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
        assert result["problems"][0]["reasonCode"] == "IDEMPOTENCY_REPLAY_CONFLICT"
        ingress = env.store.get_payload(result["requestId"])
        assert ingress["sourcePayloadDigest"] == sha256_of(changed)
        assert not result.get("emittedAssertionRecordRefs")
        assert not result.get("emittedReviewDecisionRefs")
        assert not result.get("emittedAcceptedConsequenceRefs")
    assert len(raw_digests) == 3
    after = _snapshot(env.store)
    _assert_prior_records_unchanged(before, after)
    for table in GOVERNED_TABLES:
        if table not in {"kernel_record", "kernel_gate_log"}:
            assert after[table] == before[table], table


def test_http_actor_binding_precedes_malformed_confirmation(env):
    """R02: confirmation validation does not replace transport identity."""
    before = _snapshot(env.store)
    submission = _submission()
    submission["confirmAccept"] = "false"
    response = _post(env, submission, actor=demo.WORKER)
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["reasonCode"] == "ACTOR_BINDING_UNRESOLVED"
    assert _snapshot(env.store) == before


@pytest.mark.parametrize("condition, outcome, reason, gate", [
    pytest.param("no-review-authority", "REQUIRE_REVIEW", "AUTHORITY_DENIED",
                 "REVIEW_PROMOTION", id="review-authority"),
    pytest.param("no-durable-evidence", "RETAIN_DRAFT", "EVIDENCE_INSUFFICIENT",
                 "EVIDENCE_SUFFICIENCY", id="evidence-floor"),
    pytest.param("body-named-reviewer", "REQUIRE_REVIEW", "HUMAN_APPROVAL_REQUIRED",
                 "REVIEW_PROMOTION", id="reviewer-own-act"),
])
def test_http_true_preserves_existing_acceptance_requirements(
        env, condition, outcome, reason, gate):
    """R04: well-formed confirmation still needs authority and evidence."""
    if condition == "no-review-authority":
        submission = _submission(actor_ref=demo.WORKER)
    elif condition == "no-durable-evidence":
        # A real Party resolves and satisfies the carrier's nonempty ref shape,
        # but supplies no EvidenceRecord to the actual sufficiency gate.
        submission = _submission(evidence_refs=[demo.FARMER])
    else:
        submission = _submission()
        submission["reviewerPartyRef"] = demo.ADVISOR
    assert submission["confirmAccept"] is True
    before = {kind: env.store.find_by_kind(kind)
              for kind in (REVIEW_KIND, CONSEQUENCE_KIND)}
    result = _commit(env, submission)
    assert result["decisionOutcome"] == outcome, result
    assert reason in {problem["reasonCode"] for problem in result.get("problems", [])}
    assert not result.get("emittedReviewDecisionRefs")
    assert not result.get("emittedAcceptedConsequenceRefs")
    trace = env.store.get_payload(result["promotionTraceRef"])
    assert trace["gateSequence"][-1]["gate"] == gate
    if condition == "no-durable-evidence":
        assert trace["gateSequence"][-1]["outcome"] == "INSUFFICIENT"
        assert any(entry["gate"] == "VALIDATION" and entry["outcome"] == "PASS"
                   for entry in trace["gateSequence"])
    assert {kind: env.store.find_by_kind(kind)
            for kind in (REVIEW_KIND, CONSEQUENCE_KIND)} == before


def test_http_true_keeps_bounded_structure_self_acceptance(env):
    """R04: the existing D17 identity path still accepts literal true."""
    payload = demo.field_identity_payload(_id("fieldpayload"))
    payload["identityRecordRef"] = _id("field")
    submission = demo.structure_submission(payload, idem_key=_id("commit"), confirm=True)
    assert env.store.get_record(payload["identityRecordRef"]) is None
    result = _commit(env, submission)
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED", result
    assert len(result["emittedAcceptedConsequenceRefs"]) == 1
    assert env.store.get_payload(payload["identityRecordRef"])["identityType"] == "FIELD"
    review = env.store.get_payload(result["emittedReviewDecisionRefs"][0])
    assert review["decidedByPartyRef"] == demo.FARMER
    assert review["decisionOutcomeState"] == "ACCEPTED"
