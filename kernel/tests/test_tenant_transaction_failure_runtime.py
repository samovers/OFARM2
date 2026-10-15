"""TF01–03/05–07/09–10: real runtime, binder, INSERT and native ownership.

Returned-value, status-read and cleanup faults are named Python seams around
real PostgreSQL operations. They do not simulate a successful authority, claim
crash evidence, or establish absence of effects outside the inspected batch.
"""
from __future__ import annotations

import asyncio
from contextlib import nullcontext
from dataclasses import replace

import psycopg
import pytest
from psycopg.pq import TransactionStatus

from deployment.postgresql import tenant_command_runtime_bundle_selection as control
from kernel import tenant_uow
from kernel.tenant_command_runtime_bundle_selector import CommandRuntimeBundleSelectionRefused
from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome
from kernel.tests._physical_outcome_support import batch_tuple, physical_harness, request
from kernel.tests.test_physical_outcome_runtime import harness, role  # noqa: F401
from kernel.tests.test_postgresql_tenant_migration import (
    _install_test_bound_context, authority, capability_key, command_selection_bundle,
    other_authority, tenant_target,  # noqa: F401
)
from kernel.tests.test_postgresql_tenant_uow import _principal


@pytest.fixture(scope="module")
def selection(tenant_target, authority, command_selection_bundle):
    with psycopg.connect(tenant_target.role_dsn(
        "ofarm_command_runtime_bundle_selection_control_login"
    )) as connection:
        _install_test_bound_context(connection, authority)
        return control.activate_commit_operation_claim_draft_runtime_bundle_selection(
            connection, command_selection_bundle,
        )


@pytest.fixture
def calls(monkeypatch, harness):
    """Record original native operations without replacing successful results."""
    recorded = {name: [] for name in (
        "commit", "rollback", "close", "return", "observe", "allocate", "resolve",
    )}
    for name in ("commit", "rollback", "close"):
        original = getattr(psycopg.Connection, name)
        def method(connection, _name=name, _original=original):
            if connection in harness.pool.acquired:
                recorded[_name].append(connection)
            return _original(connection)
        monkeypatch.setattr(psycopg.Connection, name, method)
    for name, attribute in (
        ("observe", "observe_physical_outcome"),
        ("allocate", "_allocate_governed_batch"),
        ("resolve", "_resolve_commit_operation_claim_draft_runtime_bundle"),
    ):
        original = getattr(tenant_uow, attribute)
        def function(*args, _name=name, _original=original, **kwargs):
            recorded[_name].append(args)
            return _original(*args, **kwargs)
        monkeypatch.setattr(tenant_uow, attribute, function)
    original_return = harness.pool.inner.putconn
    def returned(connection):
        recorded["return"].append(connection)
        return original_return(connection)
    monkeypatch.setattr(harness.pool.inner, "putconn", returned)
    return recorded


def _read_rows(target, role, harness, *ids):
    """Fresh ordinary-role read with the actual binder and current authority."""
    with psycopg.connect(target.role_dsn(role)) as connection:
        harness.manager._bind(connection, harness.principal)
        rows = connection.execute(
            """SELECT tenant_id, batch_id, full_xid::text,
                      authenticated_principal_ref, governed_operation, request_id,
                      runtime_bundle_digest, knowledge_position, created_at
                 FROM ofarm.governed_write_batch
                WHERE tenant_id = %s AND batch_id = ANY(%s)
                ORDER BY batch_id""",
            (harness.principal.authority.tenant_id, list(ids)),
        ).fetchall()
        connection.rollback()
    return rows


def _failed(error):
    assert error.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert str(error) == "tenant boundary refused (TRANSACTION_FAILED)"
    assert error.physical_observation is None


def _one_return(harness, calls, *, leases=1, commits=0):
    assert len(harness.pool.acquired) == len(harness.pool.returned) == leases
    assert len(calls["return"]) == leases and len(calls["commit"]) == commits
    assert calls["observe"] == [] and harness.audit.reasons == []
    assert sum(event[0] == "REQUEST" for event in harness.pool.events) == leases
    assert harness.pool.peak == 1
    harness.pool.assert_released()


def _poisoned_callbacks_refuse(unit, authored, calls):
    before = (len(calls["allocate"]), len(calls["resolve"]))
    with pytest.raises(RuntimeError, match="rollback-only"):
        unit.begin_batch(authored)
    with pytest.raises(CommandRuntimeBundleSelectionRefused):
        unit.resolve_commit_operation_claim_draft_runtime_bundle()
    assert (len(calls["allocate"]), len(calls["resolve"])) == before


@pytest.mark.parametrize("duplicate", ("batch_id", "request_id"))
@pytest.mark.parametrize("restore_driver", (False, True))
def test_tf01_tf03_real_unique_violation_poisoning_preserves_committed_row(
    harness, calls, authority, tenant_target, role, selection, duplicate, restore_driver,
):
    authored = request(authority, "tf01-first")
    with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
        committed = unit.begin_batch(authored)
    expected = list(batch_tuple(committed))
    expected[2] = str(expected[2])
    assert _read_rows(tenant_target, role, harness, authored.batch_id) == [tuple(expected)]
    retry = replace(request(authority, "tf01-rejected"), **{duplicate: getattr(authored, duplicate)})
    with pytest.raises(TenantBoundaryError) as caught:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            selected = unit.resolve_commit_operation_claim_draft_runtime_bundle()
            assert selected.selection_batch_id == selection.selection_batch_id
            assert unit.resolve_commit_operation_claim_draft_runtime_bundle() is selected
            with pytest.raises(psycopg.errors.UniqueViolation) as rejected:
                unit.begin_batch(retry)
            assert rejected.value.sqlstate == "23505" and unit.batch is None
            raw = harness.pool.acquired[-1]
            assert raw.info.transaction_status is TransactionStatus.INERROR
            if restore_driver:
                # Named test seam: explicit rollback/rebind restores the real
                # backend, but cannot restore the application's poisoned unit.
                raw.rollback()
                raw.execute("BEGIN ISOLATION LEVEL READ COMMITTED")
                harness.manager._bind(raw, harness.principal)
                assert raw.info.transaction_status is TransactionStatus.INTRANS
            _poisoned_callbacks_refuse(unit, request(authority), calls)
    _failed(caught.value)
    assert len(calls["allocate"]) == 2 and len(calls["resolve"]) == 1
    assert _read_rows(tenant_target, role, harness, authored.batch_id, retry.batch_id) == [tuple(expected)]
    _one_return(harness, calls, leases=2, commits=1)


def _returned_value_fault(monkeypatch, harness, fault):
    """Consume the actual INSERT row before corrupting only its Python return."""
    execute, fetchone = psycopg.Connection.execute, psycopg.Cursor.fetchone
    cursors, observed = [], []
    def executed(connection, query, *args, **kwargs):
        cursor = execute(connection, query, *args, **kwargs)
        if connection in harness.pool.acquired and "INSERT INTO ofarm.governed_write_batch" in str(query):
            cursors.append(cursor)
        return cursor
    def fetched(cursor):
        row = fetchone(cursor)
        if cursor not in cursors:
            return row
        assert row is not None and len(row) == 10
        assert cursor.connection.info.transaction_status is TransactionStatus.INTRANS
        observed.append(row)
        if isinstance(fault, BaseException):
            raise fault
        if fault == "missing":
            return None
        if fault == "malformed":
            return row[:7]
        assert fault == "timestamp"
        return (*row[:8], "invalid timestamp", row[9])
    monkeypatch.setattr(psycopg.Connection, "execute", executed)
    monkeypatch.setattr(psycopg.Cursor, "fetchone", fetched)
    return observed


@pytest.mark.parametrize("fault", ("missing", "malformed", "timestamp"))
def test_tf02_tf03_post_insert_return_failure_blocks_cached_selection_and_commit(
    harness, calls, authority, tenant_target, role, selection, monkeypatch, fault,
):
    authored = request(authority, "tf02")
    observed = _returned_value_fault(monkeypatch, harness, fault)
    with pytest.raises(TenantBoundaryError) as caught:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            selected = unit.resolve_commit_operation_claim_draft_runtime_bundle()
            assert selected.selection_batch_id == selection.selection_batch_id
            with pytest.raises((RuntimeError, ValueError)):
                unit.begin_batch(authored)
            assert unit.batch is None and len(observed) == 1
            assert harness.pool.acquired[-1].info.transaction_status is TransactionStatus.INTRANS
            _poisoned_callbacks_refuse(unit, request(authority), calls)
    _failed(caught.value)
    assert observed[0][1] == authored.batch_id and len(calls["allocate"]) == 1
    assert len(calls["resolve"]) == 1 and len(calls["rollback"]) == 1
    assert _read_rows(tenant_target, role, harness, authored.batch_id) == []
    _one_return(harness, calls)


@pytest.mark.parametrize("kind", (KeyboardInterrupt, asyncio.CancelledError))
@pytest.mark.parametrize("caught_inside", (False, True))
def test_tf02_tf04_post_insert_process_control_keeps_identity_or_failed_exit(
    harness, calls, authority, tenant_target, role, monkeypatch, kind, caught_inside,
):
    authored = request(authority, "tf04")
    failure = kind("named post-INSERT process-control seam")
    observed = _returned_value_fault(monkeypatch, harness, failure)
    expected = TenantBoundaryError if caught_inside else kind
    with pytest.raises(expected) as caught:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            if caught_inside:
                with pytest.raises(kind) as inner:
                    unit.begin_batch(authored)
                assert inner.value is failure and unit.batch is None
                _poisoned_callbacks_refuse(unit, request(authority), calls)
            else:
                unit.begin_batch(authored)
    if caught_inside:
        _failed(caught.value)
    else:
        assert caught.value is failure
    assert len(observed) == 1 and len(calls["rollback"]) == 1
    assert _read_rows(tenant_target, role, harness, authored.batch_id) == []
    _one_return(harness, calls)


@pytest.mark.parametrize("cleanup", ("rollback", "close"))
def test_tf05_ordinary_cleanup_failure_preserves_failed_exit_and_one_return(
    harness, calls, authority, tenant_target, role, monkeypatch, cleanup,
):
    authored = request(authority, "tf05-cleanup")
    _returned_value_fault(monkeypatch, harness, "timestamp")
    rollback, close = psycopg.Connection.rollback, psycopg.Connection.close
    failures = []
    def fail_rollback(connection):
        if connection in harness.pool.acquired:
            failures.append("rollback-before-native")
            raise OSError("named rollback failure before native operation")
        return rollback(connection)
    def fail_close(connection):
        result = close(connection)
        if connection in harness.pool.acquired:
            failures.append("close-after-native")
            raise OSError("named close failure after actual native close")
        return result
    monkeypatch.setattr(psycopg.Connection, "rollback", fail_rollback)
    if cleanup == "close":
        monkeypatch.setattr(psycopg.Connection, "close", fail_close)
    with pytest.raises(TenantBoundaryError) as caught:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            with pytest.raises(ValueError):
                unit.begin_batch(authored)
    _failed(caught.value)
    assert failures == (["rollback-before-native", "close-after-native"] if cleanup == "close" else ["rollback-before-native"])
    assert harness.pool.acquired[0].closed and len(calls["close"]) == 1
    assert _read_rows(tenant_target, role, harness, authored.batch_id) == []
    _one_return(harness, calls)


@pytest.mark.parametrize("when", ("before-native", "after-native"))
@pytest.mark.parametrize("kind", (OSError, KeyboardInterrupt, asyncio.CancelledError))
def test_tf05_original_return_failure_is_once_without_claiming_capacity(
    tenant_target, authority, capability_key, tmp_path, role, monkeypatch, when, kind,
):
    # Before-native return refusal intentionally leaves one measured held lease.
    # The shared fixture must detect it, then dispose natives without a second
    # putconn. That fixture disposal is not production capacity evidence.
    fixture_refusal = pytest.raises(AssertionError) if when == "before-native" else nullcontext()
    attempts, native_returns, observations, commits = [], [], [], []
    failure = kind("named original pool return failure")
    body_checked = False
    authored = request(authority, "tf05-return")
    with fixture_refusal:
        with physical_harness(tenant_target, authority, capability_key, tmp_path, role) as value:
            original = value.pool.putconn
            inner = value.pool.inner.putconn
            observe = tenant_uow.observe_physical_outcome
            commit = psycopg.Connection.commit
            def committed(connection):
                if connection in value.pool.acquired:
                    commits.append(connection)
                return commit(connection)
            def native_return(connection):
                native_returns.append(connection)
                return inner(connection)
            def failed_return(connection):
                attempts.append(connection)
                if when == "after-native":
                    original(connection)
                raise failure
            def observed(*args, **kwargs):
                observations.append(args)
                return observe(*args, **kwargs)
            monkeypatch.setattr(psycopg.Connection, "commit", committed)
            monkeypatch.setattr(value.pool.inner, "putconn", native_return)
            monkeypatch.setattr(value.pool, "putconn", failed_return)
            monkeypatch.setattr(tenant_uow, "observe_physical_outcome", observed)
            _returned_value_fault(monkeypatch, value, "timestamp")
            expected = TenantBoundaryError if kind is OSError else kind
            with pytest.raises(expected) as caught:
                with value.runtime.tenant_unit_of_work(value.principal) as unit:
                    with pytest.raises(ValueError):
                        unit.begin_batch(authored)
            if kind is OSError:
                _failed(caught.value)
            else:
                assert caught.value is failure
            assert len(attempts) == len(value.pool.acquired) == 1
            assert len(native_returns) == (when == "after-native")
            assert len(value.pool.held) == (when == "before-native")
            assert value.pool.returned == (attempts if when == "after-native" else [])
            assert observations == commits == [] and value.audit.reasons == []
            assert _read_rows(tenant_target, role, value, authored.batch_id) == []
            body_checked = True
    assert body_checked, "fixture teardown expectation must not swallow a body assertion"
    assert len(attempts) == 1 and all(conn.closed for conn in value.pool.native.connections)


@pytest.mark.parametrize("status", ("IDLE", "ACTIVE", "UNKNOWN", "read-error"))
def test_tf07_tf09_precommit_unreadable_or_unexpected_status_never_observes(
    harness, calls, authority, tenant_target, role, monkeypatch, status,
):
    original = psycopg.ConnectionInfo.transaction_status.fget
    authored, injected = request(authority, "tf07"), []
    with pytest.raises(TenantBoundaryError) as caught:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            unit.begin_batch(authored)
            raw = harness.pool.acquired[-1]
            assert raw.info.transaction_status is TransactionStatus.INTRANS
            def read(info):
                if info.pgconn is raw.pgconn and not injected:
                    injected.append(status)
                    if status == "read-error":
                        raise OSError("named pre-COMMIT state-read failure")
                    return getattr(TransactionStatus, status)
                return original(info)
            monkeypatch.setattr(psycopg.ConnectionInfo, "transaction_status", property(read))
    assert caught.value.outcome is TenantBoundaryOutcome.FINALIZATION_UNKNOWN
    assert caught.value.physical_observation is None and injected == [status]
    assert raw.closed and calls["rollback"] == []
    assert _read_rows(tenant_target, role, harness, authored.batch_id) == []
    _one_return(harness, calls)


@pytest.mark.parametrize("kind", (KeyboardInterrupt, asyncio.CancelledError))
def test_tf07_precommit_state_read_process_control_keeps_original_identity(
    harness, calls, authority, tenant_target, role, monkeypatch, kind,
):
    original = psycopg.ConnectionInfo.transaction_status.fget
    failure, injected = kind("named state-read process-control"), []
    authored = request(authority, "tf07-cancel")
    with pytest.raises(kind) as caught:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            unit.begin_batch(authored)
            raw = harness.pool.acquired[-1]
            def read(info):
                if info.pgconn is raw.pgconn and not injected:
                    injected.append(failure)
                    raise failure
                return original(info)
            monkeypatch.setattr(psycopg.ConnectionInfo, "transaction_status", property(read))
    assert caught.value is failure and injected == [failure] and raw.closed
    assert _read_rows(tenant_target, role, harness, authored.batch_id) == []
    _one_return(harness, calls)


@pytest.mark.parametrize("selector_fault", ("expected", "unexpected", "after-batch", "reentry"))
def test_tf06_tf10_caught_selector_refusal_is_failed_runtime_exit_without_audit(
    harness, calls, authority, other_authority, tenant_target, role, monkeypatch, selector_fault,
):
    if selector_fault == "expected":
        # This tenant has no activated selection: the actual fixed resolver
        # returns its existing opaque refusal through the ordinary role.
        harness.principal = _principal(tenant_target, other_authority)
        authority = other_authority
    authored = request(authority, "tf06")
    callbacks = []
    unexpected = RuntimeError("named unexpected selector callback failure")
    def refuse(*args):
        callbacks.append(args)
        if selector_fault == "unexpected":
            raise unexpected
        if selector_fault == "reentry":
            unit.resolve_commit_operation_claim_draft_runtime_bundle()
        raise CommandRuntimeBundleSelectionRefused
    if selector_fault in ("unexpected", "reentry"):
        monkeypatch.setattr(tenant_uow, "_resolve_commit_operation_claim_draft_runtime_bundle", refuse)
    with pytest.raises(TenantBoundaryError) as caught:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            if selector_fault == "after-batch":
                unit.begin_batch(authored)
            expected = RuntimeError if selector_fault == "unexpected" else CommandRuntimeBundleSelectionRefused
            with pytest.raises(expected) as inner:
                unit.resolve_commit_operation_claim_draft_runtime_bundle()
            if selector_fault == "unexpected":
                assert inner.value is unexpected
            _poisoned_callbacks_refuse(unit, request(authority), calls)
    _failed(caught.value)
    assert len(callbacks) == (selector_fault in ("unexpected", "reentry"))
    assert len(calls["resolve"]) == (selector_fault == "expected")
    assert _read_rows(tenant_target, role, harness, authored.batch_id) == []
    _one_return(harness, calls)
