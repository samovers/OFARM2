"""A prior fictional proof and a real tenant lease, with no enabled canonical checker."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json

import psycopg
import pytest
from psycopg.pq import TransactionStatus

from kernel._submission_event_admission import _EventAdmission
from kernel.tenant_claim_write_guard import ClaimWriteAttempt
from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome
from kernel.tests._physical_outcome_support import request
from kernel.tests.test_postgresql_tenant_claim_write_guard import (
    MarkerManager, MarkerOperation, authority as authority, calls as calls,
    capability_key as capability_key, harness as harness, marker_table as marker_table,
    role as role, tenant_target as tenant_target,
)
from kernel.tests.test_submission_event_admission import _case

_REQUEST_ID = "request:event-admission-fixture"
_OTHER_PROOF = "proof:other-submission"
_READ_FAULT = "SELECT fixture.missing_proof_bytes FROM (VALUES ('fictional'::bytea)) AS fixture(proof_bytes)"
_READ_ORIGINALS = """SELECT envelope, proof, context, profile FROM claim_guard_fixture.event_originals
                     WHERE tenant = ofarm.current_tenant_id() AND proof_ref = %s"""


@pytest.fixture(scope="module")
def retained(tenant_target, authority, marker_table):
    submission, source = _case(tenant_id=authority.tenant_id, actor=authority.party_ref, request_id=_REQUEST_ID)
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute("""CREATE TABLE claim_guard_fixture.event_originals (
            tenant uuid NOT NULL, proof_ref text NOT NULL, envelope bytea NOT NULL, proof bytea NOT NULL,
            context bytea NOT NULL, profile bytea NOT NULL, PRIMARY KEY (tenant, proof_ref))""")
        admin.execute("GRANT SELECT ON claim_guard_fixture.event_originals TO ofarm_app, ofarm_worker")
        other_event = json.loads(source.envelope_bytes)
        other_event["semanticEventId"] = "event:another-job"
        other_proof = json.dumps({**json.loads(source.proof_bytes), "proofId": _OTHER_PROOF}).encode()
        other_context = json.dumps({**json.loads(source.context_bytes), "expectedProofId": _OTHER_PROOF}).encode()
        for proof_ref, envelope, proof, context in (
            (source.selection.proof_ref, source.envelope_bytes, source.proof_bytes, source.context_bytes),
            (_OTHER_PROOF, json.dumps(other_event).encode(), other_proof, other_context),
        ):
            admin.execute(
                "INSERT INTO claim_guard_fixture.event_originals VALUES (%s, %s, %s, %s, %s, %s)",
                (authority.tenant_id, proof_ref, envelope, proof, context, source.profile_bytes),
            )
    return submission, source


class _GuardedAdapter(MarkerOperation):
    def __init__(self, manager, connection, binding):
        super().__init__(manager, connection, binding)
        self.reader = None if manager.scenario == "no-reader" else self._read

    def _read(self, proof_ref):
        manager = self.manager
        manager.reads.append(proof_ref)
        if manager.scenario in {"sql", "savepoint"}:
            self.connection.execute(_READ_FAULT)
            pytest.fail("expected undefined_column from the inline fixture")
        if manager.scenario == "reentry":
            with pytest.raises(RuntimeError, match="already used"):
                manager.owning_unit.stage_operation_claim(manager.submission.attempt)
            with pytest.raises(RuntimeError, match="rollback-only"):
                manager.owning_unit.stage_operation_claim(manager.submission.attempt)
        lookup = _OTHER_PROOF if manager.scenario == "other-submission" else proof_ref
        row = self.connection.execute(_READ_ORIGINALS, (lookup,)).fetchone()
        if row is None:
            return None
        timing = "VALIDATION_PHASE_PROOF" if manager.scenario == "validation-phase" else manager.source.production_mode
        return replace(manager.source, production_mode=timing, envelope_bytes=row[0], proof_bytes=row[1],
                       context_bytes=row[2], profile_bytes=row[3])

    def stage_and_verify_operation_claim(self, attempt):
        manager = self.manager
        manager.adapter_calls += 1
        backend = self.connection.execute("SELECT pg_backend_pid(), pg_current_xact_id()::text").fetchone()
        assert backend == manager.allocation
        recover = manager.scenario == "savepoint"
        if recover:
            self.connection.execute("SAVEPOINT before_source_read")
        try:
            _EventAdmission(manager.submission, self.reader).admit(attempt)
        except psycopg.errors.UndefinedColumn as error:
            manager.sql_error = error
            assert self.connection.info.transaction_status is TransactionStatus.INERROR
            if recover:
                self.connection.execute("ROLLBACK TO SAVEPOINT before_source_read")
                self.connection.execute("RELEASE SAVEPOINT before_source_read")
                assert self.connection.info.transaction_status is TransactionStatus.INTRANS
                assert _counts(self.connection, attempt.batch_id) == (1, 0, 0, 0, 0)
            raise
        return super().stage_and_verify_operation_claim(attempt)


class _FixtureManager(MarkerManager):
    def _bind_claim_operation(self, connection, binding):
        self.operation = _GuardedAdapter(self, connection, binding)
        return self.operation

    def _bind_promotion_operation(self, connection, binding):
        return self

    def stage_and_verify_promotion(self, inputs, claim, batch):
        pytest.fail("promotion was dispatched after an early refusal")


@pytest.fixture
def marker_manager_type():
    return _FixtureManager


def _counts(connection, batch_id):
    return connection.execute(
        """SELECT (SELECT count(*) FROM ofarm.governed_write_batch WHERE batch_id = %(batch)s),
                  (SELECT count(*) FROM ofarm.kernel_record WHERE batch_id = %(batch)s),
                  (SELECT count(*) FROM ofarm.kernel_gate_log WHERE batch_id = %(batch)s),
                  (SELECT count(*) FROM ofarm.kernel_edge WHERE batch_id = %(batch)s),
                  (SELECT count(*) FROM ofarm.kernel_idempotency WHERE batch_id = %(batch)s)""",
        {"batch": batch_id},
    ).fetchone()


def _observe(harness, target, role, batch, *, expected_batches=0):
    manager = harness.manager
    with psycopg.connect(target.role_dsn(role)) as observer:
        binding = manager._bind(observer, harness.principal)
        assert (binding.tenant_id, binding.party_ref) == (batch.tenant_id, batch.authenticated_principal_ref)
        assert observer.info.backend_pid != manager.allocation[0]
        assert observer.execute("SELECT session_user").fetchone() == (role,)
        assert observer.execute(
            "SELECT marker_id FROM claim_guard_fixture.marker WHERE marker_id = 'visible-control'"
        ).fetchall() == [("visible-control",)]
        source = manager.source
        assert observer.execute(_READ_ORIGINALS, (source.selection.proof_ref,)).fetchall() == [
            (source.envelope_bytes, source.proof_bytes, source.context_bytes, source.profile_bytes),
        ]
        assert _counts(observer, batch.batch_id) == (expected_batches, 0, 0, 0, 0)
        observer.rollback()


@pytest.fixture
def submission(harness, retained):
    original, harness.manager.source = retained
    harness.manager.adapter_calls = 0
    harness.manager.reads = []
    return original


@pytest.mark.parametrize(("scenario", "error", "reason"), [
    pytest.param("no-reader", ValueError, "retained proof reader unavailable", id="no-reader"),
    pytest.param("missing-proof", ValueError, "missing retained proof", id="missing-proof"),
    pytest.param("other-submission", ValueError, "envelope bytes differ", id="other-submission"),
    pytest.param("validation-phase", ValueError, "requires a pre-existing proof", id="validation-phase"),
    pytest.param("checker-unavailable", RuntimeError, "accepted Event Ingress checker unavailable", id="checker-unavailable"),
    pytest.param("reentry", RuntimeError, "accepted Event Ingress checker unavailable", id="reentry"),
    pytest.param("sql", psycopg.errors.UndefinedColumn, "missing_proof_bytes", id="sql"),
    pytest.param("savepoint", psycopg.errors.UndefinedColumn, "missing_proof_bytes", id="savepoint"),
])
def test_caught_admission_failure_rolls_back_batch(
    harness, authority, submission, tenant_target, role, calls, scenario, error, reason,
):
    manager = harness.manager
    manager.scenario = scenario
    if scenario == "missing-proof":
        selection = replace(submission.selection, proof_ref="proof:absent-from-fixture")
        submission = replace(submission, selection=selection)
    with pytest.raises(TenantBoundaryError) as final:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            batch_request = replace(request(authority), operation="ASSERT_OPERATION_CLAIM", request_id=_REQUEST_ID)
            batch = unit.begin_batch(batch_request)
            attempt = ClaimWriteAttempt(manager.operation.command, unit.binding.capability_nonce, batch.batch_id,
                                        batch.full_xid, submission.attempt.intent_bytes)
            manager.submission = replace(submission, attempt=attempt)
            manager.owning_unit = unit
            writer = harness.pool.acquired[-1]
            assert _counts(writer, batch.batch_id) == (1, 0, 0, 0, 0)
            _observe(harness, tenant_target, role, batch)
            with pytest.raises(error, match=reason) as caught:
                unit.stage_operation_claim(attempt)
            if error is psycopg.errors.UndefinedColumn:
                assert caught.value is manager.sql_error and caught.value.sqlstate == "42703"
            assert manager.adapter_calls == 1 and manager.dispatches == []
            assert manager.reads == ([] if scenario == "no-reader" else [submission.selection.proof_ref])
            status = TransactionStatus.INERROR if scenario == "sql" else TransactionStatus.INTRANS
            assert writer.info.transaction_status is status
    assert final.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert calls["commit"] == [] and calls["rollback"] == [writer]
    _observe(harness, tenant_target, role, batch)


def test_stale_and_foreign_calls_cannot_read_or_poison_new_lease(harness, authority, submission, tenant_target, role, calls):
    manager = harness.manager
    manager.scenario = "checker-unavailable"
    with harness.runtime.tenant_unit_of_work(harness.principal) as old:
        previous_backend = harness.pool.acquired[-1].info.backend_pid
    with harness.runtime.tenant_unit_of_work(harness.principal) as live:
        assert harness.pool.acquired[-1].info.backend_pid == previous_backend
        with pytest.raises(RuntimeError, match="closed"):
            old.stage_operation_claim(submission.attempt)
        with ThreadPoolExecutor(1) as thread:
            with pytest.raises(RuntimeError, match="different thread"):
                thread.submit(live.stage_operation_claim, submission.attempt).result(timeout=5)
        assert manager.selection_reads == manager.adapter_calls == 0 and manager.reads == []
        # A separate ordinary operation on the healthy current lease can still commit.
        batch = live.begin_batch(request(authority))
    assert len(calls["commit"]) == 2 and calls["rollback"] == []
    _observe(harness, tenant_target, role, batch, expected_batches=1)
