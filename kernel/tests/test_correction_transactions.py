"""Correction C07/C08: atomic effects and ordered, separate-connection writers.

These tests deliberately give each writer its own Store and connection. They
do not establish isolation for concurrent HTTP handlers sharing one Store.
All actors and operation identifiers are fictional.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from threading import Event
from time import monotonic
from uuid import uuid4

from psycopg import sql
import pytest

from kernel import context, demo
from kernel.gates import GatePipeline
from kernel.runtime_activation import complete_store_startup
from kernel.tests.conftest import _bound_store


def _operation(*, predecessor=None, actor=demo.FARMER, confirm=True):
    token = uuid4().hex
    submission = demo.spray_submission(
        f"correction-tx:{token}", erp_id=f"erp:correction.tx.{token}",
        actor_ref=actor, confirm=confirm)
    if predecessor is not None:
        submission["supersedesConsequenceRef"] = predecessor
    return submission


def _accepted(pipeline):
    result = pipeline.commit(_operation())
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    return result["emittedAcceptedConsequenceRefs"][0]


def _correction(pipeline, predecessor, *, queued, actor=demo.FARMER):
    submission = _operation(predecessor=predecessor, actor=actor,
                            confirm=not queued)
    if not queued:
        return submission, None
    captured = pipeline.commit(submission)
    assert captured["decisionOutcome"] == "RETAIN_DRAFT"
    assertion = captured["emittedAssertionRecordRefs"][0]
    assert not pipeline.store.is_superseded(predecessor)
    return {
        "commitClass": "GOVERNANCE_DECISION", "actingPartyRef": actor,
        "farmRef": demo.FARM, "idempotencyKey": f"correction-review:{uuid4().hex}",
        "decisionTime": context.now_iso(),
        "reviewTargetAssertionRef": assertion,
        "reviewRationale": "Fictional reviewer checked the compatible correction",
    }, assertion


@contextmanager
def _other_writer(store):
    other = _bound_store(store.dsn)
    try:
        complete_store_startup(other)
        assert other.conn.info.backend_pid != store.conn.info.backend_pid
        # Bound a broken test without changing the production locking policy.
        other.conn.execute("SET lock_timeout = '10s'")
        yield other, GatePipeline(other)
    finally:
        other.close()


def _await_blocked_writer(cur, writer, future):
    """Observe the actual advisory-lock wait; thread scheduling is not proof."""
    deadline = monotonic() + 5
    tick = Event()
    while monotonic() < deadline:
        cur.execute(
            "SELECT 1 FROM pg_locks WHERE pid = %s "
            "AND locktype = 'advisory' AND NOT granted",
            (writer.conn.info.backend_pid,))
        if cur.fetchone():
            assert not future.done()
            return
        if future.done():
            pytest.fail(f"writer bypassed the held lock: {future.result()!r}")
        tick.wait(0.01)
    pytest.fail("second connection did not reach the advisory-lock wait")


def _assert_no_acceptance(result):
    assert result["decisionOutcome"] in {"DENY", "RETAIN_DRAFT", "REQUIRE_REVIEW"}
    assert not result.get("emittedAcceptedConsequenceRefs")
    assert not result.get("emittedReviewDecisionRefs")


@pytest.mark.parametrize("queued", [False, True], ids=["direct", "queued"])
def test_competing_corrections_observe_the_committed_predecessor(fresh_env, queued):
    store, pipeline, _ = fresh_env
    predecessor = _accepted(pipeline)
    original = store.get_record(predecessor)
    first, _ = _correction(pipeline, predecessor, queued=queued)
    second, second_assertion = _correction(pipeline, predecessor, queued=queued)
    with _other_writer(store) as (other, other_pipeline):
        with ThreadPoolExecutor(max_workers=1) as pool:
            # Hold the first writer's commit boundary until the competing
            # connection is demonstrably waiting. Its later READ COMMITTED
            # admission must see the committed retirement.
            with store.serialized_tx() as cur:
                winner = pipeline.commit(first)
                assert winner["decisionOutcome"] == "PROMOTE_ACCEPTED"
                waiting = pool.submit(other_pipeline.commit, second)
                _await_blocked_writer(cur, other, waiting)
            loser = waiting.result(timeout=15)
    _assert_no_acceptance(loser)
    assert loser["problems"][0]["reasonCode"] == "SUPERSEDED_RECORD_USED"
    successor = winner["emittedAcceptedConsequenceRefs"][0]
    assert [edge["src_record_id"] for edge in
            store.edges_to(predecessor, "LINEAGE_SUPERSEDES")] == [successor]
    assert store.get_record(predecessor) == original
    assert not store.is_superseded(successor)
    if second_assertion:
        assert store.edges_from(second_assertion, "REVIEW") == []
        assert store.get_payload(second_assertion)["claimState"] == "PENDING_REVIEW"


def _revocable_reviewer(store):
    actor, retirement_grant = f"party:correction.tx.{uuid4().hex}", \
        f"grant:correction.retirement.{uuid4().hex}"
    with store.tx() as cur:
        store.insert_record(cur, {
            "schemaVersion": "ofarm.party.v0.1", "partyId": actor,
            "partyClass": "NATURAL_PERSON", "partyState": "ACTIVE",
            "displayName": "Correction reviewer (fictional)",
            "recordedAt": context.now_iso(),
        })
        for grant, actions in (
            (f"grant:correction.assert-accept.{uuid4().hex}",
             ["ASSERT_OPERATION_CLAIM", "REVIEW_ACCEPT"]),
            (retirement_grant, ["REVIEW_SUPERSEDE"]),
        ):
            store.insert_record(cur, {
                "schemaVersion": "ofarm.authoritygrant.v0.1",
                "authorityGrantId": grant, "grantedByPartyRef": demo.FARMER,
                "grantTarget": {"targetKind": "PARTY", "targetRef": actor},
                "targetScope": {"scopeType": "FARM", "scopeRef": demo.FARM},
                "authorityActionClasses": actions, "validFrom": demo.VALID_FROM,
                "inheritanceMode": "NO_INHERIT", "grantState": "ACTIVE",
            })
    return actor, retirement_grant


@pytest.mark.parametrize("queued", [False, True], ids=["direct", "queued"])
def test_retirement_revoked_before_admission_is_observed(fresh_env, queued):
    store, pipeline, _ = fresh_env
    predecessor = _accepted(pipeline)
    actor, grant = _revocable_reviewer(store)
    submission, assertion = _correction(
        pipeline, predecessor, queued=queued, actor=actor)
    revocation = f"revoke:correction.tx.{uuid4().hex}"
    with _other_writer(store) as (other, other_pipeline):
        with ThreadPoolExecutor(max_workers=1) as pool:
            with store.serialized_tx() as cur:
                now = context.now_iso()
                store.insert_record(cur, {
                    "schemaVersion": "ofarm.revocationdecision.v0.1",
                    "revocationDecisionId": revocation,
                    "revokesArtifactFamily": "AUTHORITY_GRANT",
                    "revokesArtifactRef": grant, "decidedByPartyRef": demo.FARMER,
                    "decidedAt": now, "effectiveFrom": now,
                    "revocationMode": "TERMINATE",
                    "targetScope": {"scopeType": "FARM", "scopeRef": demo.FARM},
                })
                waiting = pool.submit(other_pipeline.commit, submission)
                _await_blocked_writer(cur, other, waiting)
            refused = waiting.result(timeout=15)
    _assert_no_acceptance(refused)
    assert not store.is_superseded(predecessor)
    if assertion:
        assert store.edges_from(assertion, "REVIEW") == []
    trace = store.get_payload(refused["promotionTraceRef"])
    refs = {ref for gate in trace["gateSequence"]
            for ref in gate.get("relatedArtifactRefs", [])}
    authority = [store.get_payload(ref) for ref in refs]
    retirement = [record for record in authority if record and
                  record.get("schemaVersion") == "ofarm.authorizationdecisionresult.v0.1"
                  and record.get("requestedActionClass") == "REVIEW_SUPERSEDE"]
    assert len(retirement) == 1
    assert retirement[0]["revocationResult"] == "ACTIVE_REVOCATION_FOUND"
    assert retirement[0]["finalActionPermitted"] is False
    decision_trace = store.get_payload(retirement[0]["authorizationDecisionTraceRef"])
    assert decision_trace["revocationDecisionRefs"] == [revocation]
    # The ordinary accept grant remains live; this must be the retirement
    # revocation, not a refusal earlier in the existing acceptance gate.
    assert pipeline.authority.evaluate(
        acting_party_ref=actor, action_class="REVIEW_ACCEPT", action_stage="PROMOTION",
        scope={"scopeType": "FARM", "scopeRef": demo.FARM}).allowed


def _durable_state(store):
    tables = ("kernel_record", "kernel_edge", "kernel_gate_log",
              "kernel_idempotency", "runtime_trace", "derived_materialization",
              "derived_dependency_index")
    return {
        table: sorted(json.dumps(row, sort_keys=True, default=str) for row in
                      store.conn.execute(sql.SQL("SELECT * FROM {}").format(
                          sql.Identifier(table))).fetchall())
        for table in tables
    }


@pytest.mark.parametrize("queued", [False, True], ids=["direct", "queued"])
def test_late_failure_rolls_back_and_retry_retires_only_once(
        fresh_env, monkeypatch, queued):
    store, pipeline, outputs = fresh_env
    predecessor = _accepted(pipeline)
    submission, _ = _correction(pipeline, predecessor, queued=queued)
    outputs.passport_view(demo.FARM, demo.FARMER)
    before = _durable_state(store)
    original_claim = store.idempotency_claim

    def fail_after_claim(*args, **kwargs):
        original_claim(*args, **kwargs)
        assert store.is_superseded(predecessor), "fault must occur after retirement"
        raise RuntimeError("fictional failure after final idempotency write")

    with monkeypatch.context() as patch:
        patch.setattr(store, "idempotency_claim", fail_after_claim)
        with pytest.raises(RuntimeError, match="fictional failure"):
            pipeline.commit(submission)
    assert _durable_state(store) == before
    assert not store.is_superseded(predecessor)

    accepted = pipeline.commit(submission)
    assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED"
    successor = accepted["emittedAcceptedConsequenceRefs"][0]
    assert [edge["src_record_id"] for edge in
            store.edges_to(predecessor, "LINEAGE_SUPERSEDES")] == [successor]
    truth_kinds = ("ofarm.assertionrecord.v0.1", "ofarm.reviewdecision.v0.1",
                   "ofarm.acceptedeventconsequence.v0.1")
    accepted_truth = {kind: store.find_by_kind(kind) for kind in truth_kinds}
    replay = pipeline.commit(submission)
    assert replay["decisionOutcome"] == "REPLAY_REUSED_RESULT"
    assert replay["emittedAcceptedConsequenceRefs"] == [successor]
    assert {kind: store.find_by_kind(kind) for kind in truth_kinds} == accepted_truth
    assert [edge["src_record_id"] for edge in
            store.edges_to(predecessor, "LINEAGE_SUPERSEDES")] == [successor]
    assert len(store.edges_to(successor, "PROMOTION_EMITS")) == 1
    assert store.unreachable_authoritative_records() == []
