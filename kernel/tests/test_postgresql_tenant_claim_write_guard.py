"""The real tenant transaction manager with a test-only, same-backend marker."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import replace
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.pq import TransactionStatus

from kernel import tenant_uow
from kernel.tenant_claim_write_guard import CheckedClaimResult, ClaimWriteAttempt, SelectedClaimCommand
from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome, TenantUnitOfWorkManager
from kernel.tests._physical_outcome_support import lose_commit_reply, physical_harness, request
from kernel.tests.postgresql_tenant_support import tenant_target as tenant_target
from kernel.tests.test_physical_outcome_runtime import role as role
from kernel.tests.test_postgresql_tenant_migration import authority as authority, capability_key as capability_key
from kernel.tests.test_tenant_transaction_failure_runtime import calls as calls


def _command(tenant_id, digest):
    return SelectedClaimCommand(
        tenant_id,
        "ASSERT_OPERATION_CLAIM",
        digest,
        "ofarm.protectedeffect.assertionrecord.submit.v0.1",
        "0.1",
        "sha256:" + "2" * 64,
        "ofarm.assertionrecord.v0.2",
        "sha256:" + "3" * 64,
    )


class MarkerOperation:
    def __init__(self, manager, connection, binding):
        self.manager = manager
        self.connection = connection
        self.command = _command(binding.tenant_id, manager.bundle_digest)

    def selected_claim_command(self):
        self.manager.selection_reads += 1
        if self.manager.mode == "projection-error":
            raise ValueError("fixture projection failed")
        if self.manager.mode == "projection-reentry":
            self.manager.repeat()
        return self.command

    def stage_and_verify_operation_claim(self, attempt):
        manager = self.manager
        manager.dispatches.append(attempt)
        sql = """INSERT INTO claim_guard_fixture.marker (marker_id, batch_id) VALUES (%s, %s)
                 RETURNING marker_id, batch_id, backend_pid, full_xid::text"""
        params = (manager.marker_id, attempt.batch_id)
        row = self.connection.execute(sql, params).fetchone()
        assert row == (manager.marker_id, attempt.batch_id, *manager.allocation)
        if manager.mode == "writer-error":
            raise manager.fault
        if manager.mode == "sql-error":
            self.connection.execute(sql, params)
        if manager.mode == "writer-reentry":
            manager.repeat()
        if manager.mode == "wrong-type":
            return None
        marker_id = "different-marker" if manager.mode == "return-error" else row[0]
        result = CheckedClaimResult(
            self.command,
            marker_id,
            self.command.result_schema_digest,
            "fixture-trace",
            self.command.contract_digest,
            "fixture-payload",
            self.command.bundle_digest,
        )
        if result.assertion_id != row[0]:
            raise ValueError("fixture return differs from staged marker")
        return result


class MarkerManager(TenantUnitOfWorkManager):
    def _bind_claim_operation(self, connection, binding):
        self.operation = MarkerOperation(self, connection, binding)
        return self.operation


@pytest.fixture(scope="module")
def marker_table(tenant_target, authority):
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute("CREATE SCHEMA claim_guard_fixture")
        admin.execute("""CREATE TABLE claim_guard_fixture.marker (
            tenant_id uuid NOT NULL DEFAULT ofarm.current_tenant_id(), marker_id text NOT NULL,
            batch_id text NOT NULL, backend_pid integer NOT NULL DEFAULT pg_backend_pid(),
            full_xid xid8 NOT NULL DEFAULT pg_current_xact_id(), PRIMARY KEY (tenant_id, marker_id))""")
        admin.execute("ALTER TABLE claim_guard_fixture.marker ENABLE ROW LEVEL SECURITY")
        admin.execute("""CREATE POLICY bound_tenant ON claim_guard_fixture.marker
            USING (tenant_id = ofarm.current_tenant_id()) WITH CHECK (tenant_id = ofarm.current_tenant_id())""")
        admin.execute("GRANT USAGE ON SCHEMA claim_guard_fixture TO ofarm_app, ofarm_worker")
        admin.execute("GRANT SELECT, INSERT ON claim_guard_fixture.marker TO ofarm_app, ofarm_worker")
        admin.execute(
            """INSERT INTO claim_guard_fixture.marker (tenant_id, marker_id, batch_id)
            VALUES (%s, 'visible-control', 'fixture-control')""",
            (authority.tenant_id,),
        )


@pytest.fixture
def harness(tenant_target, authority, capability_key, tmp_path, role, marker_table, monkeypatch):
    with physical_harness(
        tenant_target,
        authority,
        capability_key,
        tmp_path,
        role,
        manager_type=MarkerManager,
    ) as value:
        manager = value.manager
        manager.bundle_digest = authority.runtime_bundle_digest
        manager.marker_id = "marker-" + uuid4().hex
        manager.mode = "success"
        manager.dispatches = []
        manager.selection_reads = 0
        manager.fault = KeyboardInterrupt("fixture interrupted after insert")
        value.pool.inner.resize(1, 1)
        allocate = tenant_uow._allocate_governed_batch

        def record_allocation(connection, binding, batch_request):
            result = allocate(connection, binding, batch_request)
            manager.allocation = connection.execute(
                "SELECT pg_backend_pid(), pg_current_xact_id()::text"
            ).fetchone()
            assert result[0].full_xid == int(manager.allocation[1])
            return result

        monkeypatch.setattr(tenant_uow, "_allocate_governed_batch", record_allocation)
        yield value


def _visible(target, role, harness, batch_id):
    with psycopg.connect(target.role_dsn(role)) as observer:
        harness.manager._bind(observer, harness.principal)
        assert observer.execute(
            "SELECT count(*) FROM claim_guard_fixture.marker WHERE marker_id = 'visible-control'"
        ).fetchone() == (1,)
        rows = observer.execute(
            """SELECT marker_id, batch_id, backend_pid, full_xid::text
                 FROM claim_guard_fixture.marker WHERE batch_id = %s""",
            (batch_id,),
        ).fetchall()
        observer.rollback()
        return rows


def _attempt(unit, authority):
    batch = unit.begin_batch(replace(request(authority), operation="ASSERT_OPERATION_CLAIM"))
    return ClaimWriteAttempt(
        _command(unit.binding.tenant_id, batch.runtime_bundle_digest),
        unit.binding.capability_nonce,
        batch.batch_id,
        batch.full_xid,
        b"fixture intent",
    )


@pytest.mark.parametrize("finish", ("commit", "rollback"))
def test_checked_return_is_provisional(harness, authority, tenant_target, role, calls, finish):
    manager = harness.manager
    exit_check = (
        pytest.raises(ValueError, match="rollback after return")
        if finish == "rollback"
        else nullcontext()
    )
    with exit_check:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            attempt = _attempt(unit, authority)
            result = unit.stage_operation_claim(replace(attempt, command=replace(attempt.command)))
            assert result.assertion_id == manager.marker_id
            assert manager.dispatches == [attempt]
            assert harness.pool.acquired[-1].execute(
                "SELECT marker_id FROM claim_guard_fixture.marker WHERE batch_id = %s",
                (attempt.batch_id,),
            ).fetchall() == [(result.assertion_id,)]
            assert _visible(tenant_target, role, harness, attempt.batch_id) == []
            if finish == "rollback":
                raise ValueError("rollback after return")
    expected = [(manager.marker_id, attempt.batch_id, *manager.allocation)] if finish == "commit" else []
    assert _visible(tenant_target, role, harness, attempt.batch_id) == expected
    assert len(calls["commit"]) == int(finish == "commit")
    with harness.runtime.tenant_unit_of_work(harness.principal):
        assert harness.pool.acquired[-1] is harness.pool.acquired[0]
        with pytest.raises(RuntimeError, match="closed"):
            unit.stage_operation_claim(attempt)
    assert manager.dispatches == [attempt]


@pytest.mark.parametrize(
    "mode,error,status",
    (
        ("writer-error", KeyboardInterrupt, TransactionStatus.INTRANS),
        ("return-error", ValueError, TransactionStatus.INTRANS),
        ("wrong-type", RuntimeError, TransactionStatus.INTRANS),
        ("sql-error", psycopg.errors.UniqueViolation, TransactionStatus.INERROR),
    ),
)
def test_caught_failure_after_marker_forces_rollback(
    harness, authority, tenant_target, role, calls, mode, error, status
):
    manager = harness.manager
    manager.mode = mode
    with pytest.raises(TenantBoundaryError) as failure:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            attempt = _attempt(unit, authority)
            with pytest.raises(error) as caught:
                unit.stage_operation_claim(attempt)
            if mode == "writer-error":
                assert caught.value is manager.fault
            assert harness.pool.acquired[-1].info.transaction_status is status
            with pytest.raises(RuntimeError, match="rollback-only"):
                unit.stage_operation_claim(attempt)
    assert failure.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert manager.dispatches == [attempt] and calls["commit"] == []
    assert _visible(tenant_target, role, harness, attempt.batch_id) == []


@pytest.mark.parametrize(
    "mode", ("duplicate", "writer-reentry", "projection-reentry", "projection-error")
)
def test_caught_nested_or_duplicate_refusal_is_terminal(
    harness, authority, tenant_target, role, calls, mode
):
    manager = harness.manager
    manager.mode = mode
    with pytest.raises(TenantBoundaryError) as failure:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            attempt = _attempt(unit, authority)

            def repeat():
                with pytest.raises(RuntimeError, match="already used"):
                    unit.stage_operation_claim(attempt)

            manager.repeat = repeat
            if mode == "duplicate":
                unit.stage_operation_claim(attempt)
                repeat()
            elif mode == "projection-error":
                with pytest.raises(ValueError, match="projection failed"):
                    unit.stage_operation_claim(attempt)
            else:
                with pytest.raises(RuntimeError, match="rollback-only"):
                    unit.stage_operation_claim(attempt)
    assert failure.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert len(manager.dispatches) == int(mode in {"duplicate", "writer-reentry"})
    assert calls["commit"] == [] and _visible(tenant_target, role, harness, attempt.batch_id) == []


@pytest.mark.parametrize(
    "case", ("missing-batch", "absent-selection", "draft", "prior-latch", "batch-action", "malformed")
)
def test_unavailable_claim_never_dispatches(harness, authority, tenant_target, role, calls, case):
    manager = harness.manager
    with pytest.raises(TenantBoundaryError) as failure:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            command = manager.operation.command
            action = "COMMIT_OPERATION_CLAIM_DRAFT" if case == "batch-action" else command.action
            batch = replace(request(authority), operation=action)
            xid = 1 if case == "missing-batch" else unit.begin_batch(batch).full_xid
            attempt = ClaimWriteAttempt(
                command, unit.binding.capability_nonce, batch.batch_id, xid, b"fixture"
            )
            if case == "prior-latch":
                with pytest.raises(tenant_uow.CommandRuntimeBundleSelectionRefused):
                    unit.resolve_commit_operation_claim_draft_runtime_bundle()
            elif case == "absent-selection":
                manager.operation.command = None
            elif case == "draft":
                manager.operation.command = replace(command, action="COMMIT_OPERATION_CLAIM_DRAFT")
            with pytest.raises(RuntimeError):
                unit.stage_operation_claim(object() if case == "malformed" else attempt)
    assert failure.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert manager.dispatches == [] and calls["commit"] == []
    assert manager.selection_reads == int(case not in {"prior-latch", "missing-batch"})
    assert _visible(tenant_target, role, harness, batch.batch_id) == []


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("binding_nonce", UUID(int=1)),
        ("batch_id", "other-batch"),
        ("full_xid", 0),
        ("full_xid", True),
        ("intent_bytes", None),
    ),
)
def test_attempt_must_match_live_batch(harness, authority, calls, field, value):
    manager = harness.manager
    with pytest.raises(TenantBoundaryError) as failure:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            attempt = _attempt(unit, authority)
            with pytest.raises(RuntimeError):
                unit.stage_operation_claim(replace(attempt, **{field: value}))
    assert failure.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert manager.dispatches == [] and calls["commit"] == []


@pytest.mark.parametrize(
    ("field", "value", "change_selection"),
    (
        ("tenant_id", UUID(int=1), True),
        ("action", "OTHER", True),
        ("bundle_digest", "sha256:" + "9" * 64, True),
        ("contract_id", "other", True),
        ("contract_version", "9", True),
        ("result_schema", "other", True),
        ("contract_digest", "sha256:" + "9" * 64, False),
        ("result_schema_digest", "sha256:" + "9" * 64, False),
    ),
)
def test_claim_requires_the_selected_assertion_command(
    harness, authority, calls, field, value, change_selection
):
    manager = harness.manager
    with pytest.raises(TenantBoundaryError) as failure:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            attempt = _attempt(unit, authority)
            changed = replace(attempt.command, **{field: value})
            if change_selection:
                manager.operation.command = changed
            with pytest.raises(RuntimeError):
                unit.stage_operation_claim(replace(attempt, command=changed))
    assert failure.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert manager.dispatches == [] and calls["commit"] == []


def test_foreign_thread_refuses_without_poisoning_owner(harness, authority, tenant_target, role):
    manager = harness.manager
    with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
        attempt = _attempt(unit, authority)
        with ThreadPoolExecutor(1) as thread:
            with pytest.raises(RuntimeError, match="different thread"):
                thread.submit(unit.stage_operation_claim, attempt).result(timeout=5)
        assert manager.dispatches == [] and manager.selection_reads == 0
        result = unit.stage_operation_claim(attempt)
    assert [row[0] for row in _visible(tenant_target, role, harness, attempt.batch_id)] == [
        result.assertion_id
    ]


def test_lost_commit_reply_never_repeats_dispatch(harness, authority, tenant_target, role, monkeypatch):
    commits = lose_commit_reply(monkeypatch, harness)
    with pytest.raises(TenantBoundaryError) as failure:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            attempt = _attempt(unit, authority)
            result = unit.stage_operation_claim(attempt)
    assert failure.value.outcome is TenantBoundaryOutcome.FINALIZATION_UNKNOWN
    assert harness.manager.dispatches == [attempt] and len(commits) == 1
    assert [row[0] for row in _visible(tenant_target, role, harness, attempt.batch_id)] == [
        result.assertion_id
    ]


def test_production_manager_has_no_enabled_claim_operation(
    tenant_target, authority, capability_key, tmp_path, role, marker_table
):
    with physical_harness(tenant_target, authority, capability_key, tmp_path, role) as production:
        with pytest.raises(TenantBoundaryError) as failure:
            with production.runtime.tenant_unit_of_work(production.principal) as unit:
                attempt = _attempt(unit, authority)
                with pytest.raises(RuntimeError, match="unavailable"):
                    unit.stage_operation_claim(attempt)
        assert failure.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
        assert _visible(tenant_target, role, production, attempt.batch_id) == []
