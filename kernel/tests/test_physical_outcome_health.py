"""PS10/11 health-check cancellation: real runtime, native pool and capacity.

Cancellation/cleanup injections are explicit test seams after real operations.
The original COMMIT-loss seam executes a real COMMIT and only withholds its
Python completion; actual wire-loss and crash evidence live in separate tests.
"""
from __future__ import annotations

import asyncio

import psycopg
import pytest

from kernel import tenant_physical_outcome as physical
from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome
from kernel.tests._physical_outcome_support import (
    lose_commit_reply, physical_harness, request,
)
from kernel.tests.test_physical_outcome_runtime import role  # noqa: F401
from kernel.tests.test_postgresql_tenant_migration import (
    authority, capability_key, tenant_target,  # noqa: F401
)


class _HealthFault:
    def __init__(self, harness, stage, phase, failure, secondary=False):
        self.harness = harness
        self.stage = stage
        self.phase = phase
        self.failure = failure
        self.secondary = secondary
        self.connection = None
        self.checks = []
        self.failures = []
        self.native_returns = []
        self.public_returns = []
        self.secondary_failures = []
        self.injected = False

    def _secondary_failure(self, phase):
        self.secondary_failures.append(phase)
        if self.secondary in ("control", "return"):
            kind = asyncio.CancelledError if isinstance(self.failure, KeyboardInterrupt) else KeyboardInterrupt
            raise kind("explicit second process-control cleanup failure")
        raise OSError("explicit secondary cleanup failure")

    def install(self, monkeypatch):
        pool = self.harness.pool.inner
        execute, cursor_close = physical._BoundedTransaction.execute, psycopg.Cursor.close
        connection_close, autocommit = psycopg.Connection.close, psycopg.Connection.autocommit
        check, native_return, public_return = pool._check, pool._putconn, pool.putconn
        actual_wait = physical.wait

        def probe(transaction, query, params=None):
            eligible = len(self.harness.pool.acquired) == (self.stage == "observer")
            if query == "" and eligible and self.connection is None:
                self.connection = transaction.connection
            result = execute(transaction, query, params)
            if transaction.connection is self.connection and self.phase == "probe" and not self.injected:
                self.injected = True
                raise self.failure
            return result

        def wait(*args, **kwargs):
            result = actual_wait(*args, **kwargs)
            if self.connection is not None and self.phase == "wait" and not self.injected:
                self.injected = True
                raise self.failure
            return result

        def close_cursor(cursor):
            cursor_close(cursor)
            if cursor.connection is self.connection:
                if self.phase == "cursor" and not self.injected:
                    self.injected = True
                    raise self.failure
                if self.secondary and self.secondary != "return":
                    self._secondary_failure("cursor")

        def close_connection(connection):
            connection_close(connection)
            if connection is self.connection and self.secondary and self.secondary != "return":
                self._secondary_failure("connection")

        def set_autocommit(connection, value):
            autocommit.fset(connection, value)
            if connection is self.connection and value is False and self.phase == "restore" and not self.injected:
                self.injected = True
                raise self.failure

        def checked(connection):
            self.checks.append(connection)
            try:
                return check(connection)
            except BaseException as failure:
                self.failures.append(failure)
                raise

        def returned(connection, from_getconn):
            self.native_returns.append((connection, from_getconn))
            return native_return(connection, from_getconn=from_getconn)

        def publicly_returned(connection):
            self.public_returns.append(connection)
            result = public_return(connection)
            if connection is self.connection and self.secondary == "return":
                self._secondary_failure("return")
            return result

        monkeypatch.setattr(physical._BoundedTransaction, "execute", probe)
        monkeypatch.setattr(physical, "wait", wait)
        monkeypatch.setattr(psycopg.Cursor, "close", close_cursor)
        monkeypatch.setattr(psycopg.Connection, "close", close_connection)
        monkeypatch.setattr(psycopg.Connection, "autocommit", property(autocommit.fget, set_autocommit))
        monkeypatch.setattr(pool, "_check", checked)
        monkeypatch.setattr(pool, "_putconn", returned)
        monkeypatch.setattr(pool, "putconn", publicly_returned)


def _record_original_error(monkeypatch, harness):
    actual_run = harness.manager._run
    errors = []

    def run(connection, principal, capture):
        result = yield from actual_run(connection, principal, capture)
        if result is not None:
            errors.append(result)
        return result

    monkeypatch.setattr(harness.manager, "_run", run)
    return errors


def _eight_slots_remain_available(pool):
    # Wait for real background replacement/reset work, then hold all eight
    # native leases together. Reported pool_size alone cannot prove capacity.
    pool.wait(timeout=5)
    held = []
    try:
        for _ in range(8):
            held.append(pool.getconn(timeout=.1))
        assert len(set(held)) == 8
        assert all(not connection.closed for connection in held)
    finally:
        for connection in held:
            pool.putconn(connection)
        # Drain resets before fixture shutdown: retained diagnostic references
        # must not prolong discarded queued tasks in the pinned pool's close.
        pool.wait(timeout=5)


def _assert_single_native_return(fault, *, process_control):
    assert fault.connection is not None and fault.connection.closed
    assert len(fault.failures) == 1 and fault.failures[0] is fault.failure
    returns = [from_check for connection, from_check in fault.native_returns if connection is fault.connection]
    assert returns == [not process_control]
    assert sum(connection is fault.connection for connection in fault.public_returns) == int(process_control)


@pytest.mark.parametrize("stage", ("entry", "observer"))
@pytest.mark.parametrize("cancellation", (KeyboardInterrupt, asyncio.CancelledError))
@pytest.mark.parametrize("phase,secondary", (
    ("probe", False), ("cursor", False), ("restore", False), ("probe", True),
    ("wait", False), ("wait", True),
    ("wait", "control"), ("probe", "return"),
))
def test_ps10_ps11_health_cancellation_returns_native_slot_once(
    tenant_target, authority, capability_key, tmp_path, monkeypatch, role,
    stage, cancellation, phase, secondary,
):
    with physical_harness(tenant_target, authority, capability_key, tmp_path, role) as harness:
        pool = harness.pool.inner
        pool.resize(8, 8)
        pool.wait(timeout=5)
        failure = cancellation("explicit health-check process cancellation")
        fault = _HealthFault(harness, stage, phase, failure, secondary)
        fault.install(monkeypatch)
        original_errors = _record_original_error(monkeypatch, harness)
        commits = lose_commit_reply(monkeypatch, harness) if stage == "observer" else []
        expected = TenantBoundaryError if stage == "observer" else cancellation
        with pytest.raises(expected) as caught:
            with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
                unit.begin_batch(request(authority, "health-cancel"))
        if stage == "observer":
            assert original_errors == [caught.value] and caught.value is original_errors[0]
            assert caught.value.outcome is TenantBoundaryOutcome.FINALIZATION_UNKNOWN
            observation = caught.value.physical_observation
            assert observation.physical_status == "UNKNOWN"
            assert observation.observer_failure == "CANCELLED"
            assert observation.cleanup == "NOT_ACQUIRED"
            assert len(commits) == 1
        else:
            assert caught.value is failure
            assert original_errors == [] and commits == []
        _assert_single_native_return(fault, process_control=True)
        assert len(fault.checks) == (2 if stage == "observer" else 1)
        assert len(harness.pool.acquired) == len(harness.pool.returned) == (stage == "observer")
        assert sum(event[0] == "REQUEST" for event in harness.pool.events) == (2 if stage == "observer" else 1)
        assert harness.audit.reasons == []
        if secondary:
            expected_secondary = ["return"] if secondary == "return" else ["connection", "cursor"]
            assert sorted(fault.secondary_failures) == expected_secondary
        harness.pool.assert_released()
        _eight_slots_remain_available(pool)


@pytest.mark.parametrize("stage", ("entry", "observer"))
@pytest.mark.parametrize("phase", ("probe", "cursor", "restore", "wait"))
def test_ps10_ps11_ordinary_health_exception_keeps_pool_owned_return(
    tenant_target, authority, capability_key, tmp_path, monkeypatch, role, stage, phase,
):
    with physical_harness(tenant_target, authority, capability_key, tmp_path, role) as harness:
        pool = harness.pool.inner
        pool.resize(8, 8)
        pool.wait(timeout=5)
        fault = _HealthFault(harness, stage, phase, OSError("explicit ordinary health failure"))
        fault.install(monkeypatch)
        commits = lose_commit_reply(monkeypatch, harness) if stage == "observer" else []
        if stage == "observer":
            with pytest.raises(TenantBoundaryError) as caught:
                with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
                    unit.begin_batch(request(authority, "health-exception"))
            assert caught.value.outcome is TenantBoundaryOutcome.FINALIZATION_UNKNOWN
            assert caught.value.physical_observation.physical_status == "COMMITTED"
            assert caught.value.physical_observation.cleanup == "RETURNED"
            assert len(commits) == 1
        else:
            with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
                unit.begin_batch(request(authority, "health-exception"))
        _assert_single_native_return(fault, process_control=False)
        assert len(fault.checks) == (3 if stage == "observer" else 2)
        assert sum(event[0] == "REQUEST" for event in harness.pool.events) == (2 if stage == "observer" else 1)
        assert harness.audit.reasons == []
        harness.pool.assert_released()
        _eight_slots_remain_available(pool)
