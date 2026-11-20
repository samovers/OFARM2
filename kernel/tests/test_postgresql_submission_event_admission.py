"""Real tenant leases, prior fictional proofs and the accepted offline checker."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import asdict, replace
from hashlib import sha256
import json
from uuid import UUID, uuid4

import psycopg
import pytest
import rfc8785
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from kernel import _submission_event_admission, _submission_event_checker
from kernel._submission_event_admission import _AdmissionBinding, _EventAdmission, _ProofSelection, _RetainedProof
from kernel.tenant_claim_write_guard import ClaimWriteAttempt, SelectedClaimCommand
from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome
from kernel.tests._physical_outcome_support import request
from kernel.tests.test_postgresql_tenant_claim_write_guard import (
    MarkerManager, MarkerOperation, authority as authority, calls as calls,
    capability_key as capability_key, harness as harness, marker_table as marker_table,
    role as role, tenant_target as tenant_target,
)
from kernel.tests.test_submission_event_admission import _case

_ACT_CASES = {"missing-act-envelope", "wrong-act-envelope"}
_ALLOWED = ("world-initial", "act-initial", "world-exact", "act-exact")
_READ_FAULT = "SELECT fixture.missing_proof_bytes FROM (VALUES ('fictional'::bytea)) AS fixture(proof_bytes)"
_READ_ORIGINALS = """SELECT selection, production_mode, envelope, proof, context, profile, request, intent
                     FROM claim_guard_fixture.event_originals
                     WHERE tenant = ofarm.current_tenant_id() AND proof_ref = %s"""
_READ_ADMISSION = """SELECT binding FROM claim_guard_fixture.event_admission
                     WHERE tenant = ofarm.current_tenant_id() AND batch_id = %s"""


def _fixture_json(value):
    """Encode the two non-JSON types in the test's original and admission records."""
    def encode(other):
        if isinstance(other, UUID):
            return str(other)
        if isinstance(other, bytes):
            return other.hex()
        raise TypeError(type(other))
    return json.dumps(value, default=encode)


def _selection(document):
    return _ProofSelection(**{**document, "tenant_id": UUID(document["tenant_id"])})


def _recorded_binding(document):
    document = document.copy()
    attempt = document.pop("attempt")
    raw_command = attempt["command"]
    command = SelectedClaimCommand(**{**raw_command, "tenant_id": UUID(raw_command["tenant_id"])})
    document["attempt"] = ClaimWriteAttempt(command, UUID(attempt["binding_nonce"]), attempt["batch_id"],
                                             attempt["full_xid"], bytes.fromhex(attempt["intent_bytes"]))
    document["selection"] = _selection(document["selection"])
    return _AdmissionBinding(**document)


def _read_originals(connection, proof_ref):
    row = connection.execute(_READ_ORIGINALS, (proof_ref,)).fetchone()
    if row is None:
        return None
    selection, timing, envelope, proof, context, profile, request_bytes, intent_bytes = row
    source = _RetainedProof(_selection(selection), timing, envelope, proof, context, profile)
    return source, request_bytes, intent_bytes


@pytest.fixture(scope="module")
def custody_tables(tenant_target, marker_table):
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute("""CREATE TABLE claim_guard_fixture.event_originals (
            tenant uuid NOT NULL, proof_ref text NOT NULL, selection jsonb NOT NULL, production_mode text NOT NULL,
            envelope bytea, proof bytea NOT NULL, context bytea NOT NULL, profile bytea NOT NULL,
            request bytea NOT NULL, intent bytea NOT NULL, PRIMARY KEY (tenant, proof_ref))""")
        admin.execute("GRANT SELECT ON claim_guard_fixture.event_originals TO ofarm_app, ofarm_worker")
        # A test-only record of the original result, written with the staged marker on its physical lease.
        admin.execute("""CREATE TABLE claim_guard_fixture.event_admission (
            tenant uuid NOT NULL DEFAULT ofarm.current_tenant_id(), batch_id text NOT NULL, binding jsonb NOT NULL,
            PRIMARY KEY (tenant, batch_id))""")
        admin.execute("ALTER TABLE claim_guard_fixture.event_admission ENABLE ROW LEVEL SECURITY")
        admin.execute("""CREATE POLICY bound_tenant ON claim_guard_fixture.event_admission
            USING (tenant = ofarm.current_tenant_id()) WITH CHECK (tenant = ofarm.current_tenant_id())""")
        admin.execute("GRANT SELECT, INSERT ON claim_guard_fixture.event_admission TO ofarm_app, ofarm_worker")


def _seed(admin, original, source, *, missing_envelope=False):
    admin.execute(
        """INSERT INTO claim_guard_fixture.event_originals
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (source.selection.tenant_id, source.selection.proof_ref, Jsonb(asdict(source.selection), dumps=_fixture_json),
         source.production_mode, None if missing_envelope else source.envelope_bytes,
         source.proof_bytes, source.context_bytes, source.profile_bytes, original.request_bytes,
         original.attempt.intent_bytes),
    )


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
            return None
        lookup = manager.other_proof_ref if manager.scenario == "other-submission" else proof_ref
        retained = _read_originals(self.connection, lookup)
        if retained is None:
            return None
        source, _, _ = retained
        if manager.scenario == "wrong-act-envelope":
            other, _, _ = _read_originals(self.connection, manager.other_proof_ref)
            return replace(source, envelope_bytes=other.envelope_bytes)
        if manager.scenario == "validation-phase":
            return replace(source, production_mode="VALIDATION_PHASE_PROOF")
        return source

    def stage_and_verify_operation_claim(self, attempt):
        manager = self.manager
        manager.adapter_calls += 1
        backend = self.connection.execute("SELECT pg_backend_pid(), pg_current_xact_id()::text").fetchone()
        assert backend == manager.allocation
        recover = manager.scenario == "savepoint"
        if recover:
            self.connection.execute("SAVEPOINT before_source_read")
        try:
            binding = _EventAdmission(manager.submission, self.reader).admit(attempt)
        except psycopg.errors.UndefinedColumn as error:
            manager.sql_error = error
            assert self.connection.info.transaction_status is TransactionStatus.INERROR
            if recover:
                self.connection.execute("ROLLBACK TO SAVEPOINT before_source_read")
                self.connection.execute("RELEASE SAVEPOINT before_source_read")
                assert self.connection.info.transaction_status is TransactionStatus.INTRANS
                assert _counts(self.connection, attempt.batch_id) == (1, 0, 0, 0, 0)
            raise
        assert binding.selection == manager.source.selection and binding.attempt == attempt
        assert binding.disposition == "CONDITIONAL_CONFORMANCE_PASS" and binding.commit_class == "OPERATION_CLAIM"
        family = "GovernanceEvent" if binding.selection.event_kind == "SUBMISSION_ACT" else "OccurrenceEvent"
        assert binding.family == family
        result = super().stage_and_verify_operation_claim(attempt)
        self.connection.execute(
            "INSERT INTO claim_guard_fixture.event_admission (batch_id, binding) VALUES (%s, %s)",
            (attempt.batch_id, Jsonb(asdict(binding), dumps=_fixture_json)),
        )
        return result


class _FixtureManager(MarkerManager):
    def _bind_claim_operation(self, connection, binding):
        self.operation = _GuardedAdapter(self, connection, binding)
        return self.operation

    def _bind_promotion_operation(self, connection, binding):
        # This fixture tests admission and a local marker. A complete promotion belongs to #428/#178.
        if self.scenario in _ALLOWED:
            return super()._bind_promotion_operation(connection, binding)
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


def _observe(harness, target, role, batch, *, expected_batches=0, committed_admission=False):
    manager = harness.manager
    with psycopg.connect(target.role_dsn(role)) as observer:
        binding = manager._bind(observer, harness.principal)
        assert (binding.tenant_id, binding.party_ref) == (batch.tenant_id, batch.authenticated_principal_ref)
        assert observer.info.backend_pid != manager.allocation[0]
        assert observer.execute("SELECT session_user").fetchone() == (role,)
        assert observer.execute(
            "SELECT marker_id FROM claim_guard_fixture.marker WHERE marker_id = 'visible-control'"
        ).fetchall() == [("visible-control",)]
        source, request_bytes, intent_bytes = _read_originals(observer, manager.source.selection.proof_ref)
        expected_source = manager.source
        if manager.scenario == "missing-act-envelope":
            expected_source = replace(expected_source, envelope_bytes=None)
        if manager.scenario in {"wrong-act-envelope", "other-submission"}:
            other, other_request, _ = _read_originals(observer, manager.other_proof_ref)
            assert other.selection.tenant_id == source.selection.tenant_id
            assert other.selection.event_ref != source.selection.event_ref
            assert other_request != request_bytes
            assert other.selection.event_kind == source.selection.event_kind
            assert json.loads(other_request)["actingPartyRef"] == json.loads(request_bytes)["actingPartyRef"]
            assert json.loads(other.envelope_bytes)["primaryEventFamily"] == json.loads(source.envelope_bytes)["primaryEventFamily"]
        assert source == expected_source
        assert request_bytes == manager.original.request_bytes and intent_bytes == manager.original.attempt.intent_bytes
        assert _counts(observer, batch.batch_id) == (expected_batches, 0, 0, 0, 0)
        markers = observer.execute("SELECT marker_id, backend_pid, full_xid::text FROM claim_guard_fixture.marker "
                                   "WHERE batch_id = %s", (batch.batch_id,)).fetchall()
        records = observer.execute(_READ_ADMISSION, (batch.batch_id,)).fetchall()
        if committed_admission:
            assert markers == [(manager.marker_id, *manager.allocation)] and len(records) == 1
            recorded = _recorded_binding(records[0][0])
            attempt = replace(manager.submission.attempt, intent_bytes=intent_bytes)
            original = replace(manager.original, request_bytes=request_bytes, attempt=attempt)
            reader = _EventAdmission(original, lambda ref: _read_originals(observer, ref)[0])
            assert reader.readback(attempt, recorded) == recorded
            with pytest.raises(ValueError, match="recorded event admission differs"):
                reader.readback(attempt, replace(recorded, disposition="FAIL"))
            if "EXACT_REEVALUATION" in json.loads(source.context_bytes)["permittedUseModes"]:
                assert reader.readback(attempt, recorded, reevaluate=True) == recorded
            else:
                with pytest.raises(ValueError, match="original context forbids exact reevaluation"):
                    reader.readback(attempt, recorded, reevaluate=True)
        else:
            assert markers == [] and records == []
        observer.rollback()


@pytest.fixture
def scenario():
    return "world-initial"


@pytest.fixture
def submission(harness, authority, tenant_target, custody_tables, scenario):
    manager = harness.manager
    identifier = uuid4().hex
    submission_act = scenario in {*_ACT_CASES, "act-initial", "act-exact", "other-submission"}
    args = dict(tenant_id=authority.tenant_id, actor=authority.party_ref, request_id="request:" + identifier)
    original, source = _case(
        **args, event_kind="SUBMISSION_ACT" if submission_act else "ASSOCIATED_WORLD_EVENT",
        event_ref="event:submission:" + identifier if submission_act else None,
        proof_ref="proof:" + identifier, allow_reevaluation=scenario.endswith("-exact"),
    )
    if scenario == "wrong-classification":
        # The source selectors agree on the bytes. Only the checker can reject this family.
        proof = json.loads(source.proof_bytes)
        proof["classification"]["authoritativePrimaryFamily"] = "GovernanceEvent"
        selected = replace(source.selection, proof_digest="sha256:" + sha256(rfc8785.dumps(proof)).hexdigest())
        original = replace(original, selection=selected)
        source = replace(source, selection=selected, proof_bytes=json.dumps(proof).encode())
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        _seed(admin, original, source, missing_envelope=scenario == "missing-act-envelope")
        if scenario in {"wrong-act-envelope", "other-submission"}:
            manager.other_proof_ref = "proof:other-" + identifier
            other, other_source = _case(
                **{**args, "request_id": "request:other-" + identifier},
                event_kind="SUBMISSION_ACT", event_ref="event:other-submission:" + identifier,
                proof_ref=manager.other_proof_ref,
            )
            _seed(admin, other, other_source)
    manager.original = original
    manager.source = source
    manager.adapter_calls = 0
    manager.reads = []
    return original


def _begin_attempt(unit, manager, authority, submission):
    batch_request = replace(request(authority), operation="ASSERT_OPERATION_CLAIM", request_id=submission.request_id)
    batch = unit.begin_batch(batch_request)
    attempt = ClaimWriteAttempt(manager.operation.command, unit.binding.capability_nonce, batch.batch_id,
                                batch.full_xid, submission.attempt.intent_bytes)
    manager.submission = replace(submission, attempt=attempt)
    manager.owning_unit = unit
    return batch, attempt


@pytest.mark.parametrize("scenario", _ALLOWED)
@pytest.mark.parametrize("finish", ["commit", "rollback"])
def test_allowed_submission_and_independent_readback(
    harness, authority, submission, tenant_target, role, calls, scenario, finish, monkeypatch,
):
    manager = harness.manager
    manager.scenario = scenario
    modes = []
    verify = _submission_event_admission._verify_classification

    def count_verify(package, source, original, binding, mode):
        modes.append(mode)
        return verify(package, source, original, binding, mode)

    monkeypatch.setattr(_submission_event_admission, "_verify_classification", count_verify)
    exit_check = nullcontext() if finish == "commit" else pytest.raises(ValueError, match="rollback after admission")
    with exit_check:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            batch, attempt = _begin_attempt(unit, manager, authority, submission)
            _observe(harness, tenant_target, role, batch)
            result = unit.stage_operation_claim(attempt)
            writer = harness.pool.acquired[-1]
            assert result.assertion_id == manager.marker_id and manager.dispatches == [attempt]
            assert manager.adapter_calls == 1 and manager.reads == [submission.selection.proof_ref]
            assert modes == ["INITIAL_EVALUATION"]
            recorded = _recorded_binding(writer.execute(_READ_ADMISSION, (batch.batch_id,)).fetchone()[0])
            assert recorded.attempt == attempt and recorded.selection == submission.selection
            assert recorded.request_id == submission.request_id
            assert writer.execute("SELECT marker_id FROM claim_guard_fixture.marker WHERE batch_id = %s",
                                  (batch.batch_id,)).fetchall() == [(result.assertion_id,)]
            _observe(harness, tenant_target, role, batch)
            if finish == "rollback":
                raise ValueError("rollback after admission")
    committed = finish == "commit"
    assert calls["commit"] == ([writer] if committed else [])
    assert calls["rollback"] == ([] if committed else [writer])
    _observe(harness, tenant_target, role, batch, expected_batches=int(committed), committed_admission=committed)
    expected_modes = ["INITIAL_EVALUATION"]
    if committed and scenario.endswith("-exact"):
        expected_modes.append("EXACT_REEVALUATION")
    assert modes == expected_modes


@pytest.mark.parametrize(("scenario", "error", "reason"), [
    pytest.param("no-reader", ValueError, "retained proof reader unavailable", id="no-reader"),
    pytest.param("missing-proof", ValueError, "missing retained proof", id="missing-proof"),
    pytest.param("other-submission", ValueError, "missing retained proof or different governed source", id="other-submission"),
    pytest.param("missing-act-envelope", ValueError, "^invalid envelope bytes or size$", id="missing-act-envelope"),
    pytest.param("wrong-act-envelope", ValueError, "^envelope bytes differ from the independent selection$",
                 id="wrong-act-envelope"),
    pytest.param("wrong-classification", ValueError, "event classification did not pass", id="wrong-classification"),
    pytest.param("validation-phase", ValueError, "requires a pre-existing proof", id="validation-phase"),
    pytest.param("checker-unavailable", RuntimeError, "accepted Event Ingress checker unavailable", id="checker-unavailable"),
    pytest.param("reentry", ValueError, "missing retained proof", id="reentry"),
    pytest.param("sql", psycopg.errors.UndefinedColumn, "missing_proof_bytes", id="sql"),
    pytest.param("savepoint", psycopg.errors.UndefinedColumn, "missing_proof_bytes", id="savepoint"),
])
def test_caught_admission_failure_rolls_back_batch(
    harness, authority, submission, tenant_target, role, calls, scenario, error, reason, monkeypatch, tmp_path,
):
    manager = harness.manager
    manager.scenario = scenario
    if scenario == "checker-unavailable":
        monkeypatch.setattr(_submission_event_checker, "_PACKAGE", tmp_path / "absent-checker")
    if scenario in _ACT_CASES:
        assert submission.selection.event_kind == "SUBMISSION_ACT"
        assert "associatedSemanticEventBinding" not in json.loads(submission.attempt.intent_bytes)
        assert json.loads(submission.request_bytes)["semanticEventRef"] == submission.selection.event_ref
    if scenario == "missing-proof":
        selection = replace(submission.selection, proof_ref="proof:absent-from-fixture")
        submission = replace(submission, selection=selection)
    with pytest.raises(TenantBoundaryError) as final:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            batch, attempt = _begin_attempt(unit, manager, authority, submission)
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
    manager.scenario = "world-initial"
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
