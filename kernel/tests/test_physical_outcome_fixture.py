"""Fixture isolation after assertions; no production F3 shutdown claim."""
from __future__ import annotations

import json
import time
from threading import Barrier, Event, Lock, Thread
from types import SimpleNamespace

import psycopg
import pytest

from kernel.tenant_uow import TenantUnitOfWorkStartupError
from kernel.tests._physical_outcome_support import physical_harness
from kernel.tests.test_physical_outcome_runtime import role  # noqa: F401
from kernel.tests.test_postgresql_tenant_migration import (
    authority, capability_key, tenant_target,  # noqa: F401
)


def _assert_pids_absent(target, pids):
    until = time.monotonic() + 2
    with psycopg.connect(target.target_admin_dsn, autocommit=True) as admin:
        while True:
            remaining = admin.execute(
                "SELECT pid FROM pg_stat_activity WHERE pid = ANY(%s)", (pids,),
            ).fetchall()
            if not remaining or time.monotonic() >= until:
                break
            time.sleep(.01)
    assert remaining == []


def _queue_eight_returns(harness, borrower, monkeypatch):
    pool = harness.pool.inner
    pool.resize(8, 8)
    pool.wait(timeout=5)
    owner = harness.pool if borrower == "tracked" else pool
    held = [owner.getconn(timeout=1) for _ in range(8)]
    gate, release, lock = Barrier(4), Event(), Lock()
    entered, failures, returned = [], [], []
    actual_return, actual_put = pool._return_connection, pool._putconn

    def gated_return(connection, *, from_getconn):
        with lock:
            entered.append(connection)
            ordinal = len(entered)
        if ordinal <= 3:
            gate.wait(timeout=5)
            assert release.wait(5)
        actual_return(connection, from_getconn=from_getconn)

    def put(connection, *, from_getconn):
        returned.append(connection)
        return actual_put(connection, from_getconn=from_getconn)

    def release_after_close():
        try:
            until = time.monotonic() + 5
            while not pool.closed and time.monotonic() < until:
                time.sleep(.001)
            assert pool.closed
        except BaseException as error:
            failures.append(error)
        finally:
            release.set()

    monkeypatch.setattr(pool, "_return_connection", gated_return)
    monkeypatch.setattr(pool, "_putconn", put)
    for connection in held:
        owner.putconn(connection)
    gate.wait(timeout=5)
    releaser = Thread(target=release_after_close)
    releaser.start()
    return held, returned, releaser, failures


@pytest.mark.parametrize("borrower", ("tracked", "direct"))
def test_fixture_disposes_retained_natives_before_next_eight_slot_pool(
    tenant_target, authority, capability_key, tmp_path, monkeypatch, role, borrower,
):
    before_disposal = []
    with physical_harness(tenant_target, authority, capability_key, tmp_path, role) as first:
        held, returned, releaser, failures = _queue_eight_returns(first, borrower, monkeypatch)
        pids = [connection.info.backend_pid for connection in held]
        dispose = first.pool.native.dispose

        def record_then_dispose():
            before_disposal.extend(connection.closed for connection in held)
            dispose()

        monkeypatch.setattr(first.pool.native, "dispose", record_then_dispose)
        first.pool.assert_released()
    releaser.join(timeout=1)
    assert not releaser.is_alive() and failures == []
    # The unchanged production close still leaves five queued native returns.
    assert sum(not closed for closed in before_disposal) == 5
    assert set(returned) == set(held) and len(returned) == 8
    assert set(first.pool.native.connections) == set(held)
    assert all(type(connection) is psycopg.Connection and connection.closed for connection in held)
    _assert_pids_absent(tenant_target, pids)
    # Keep first, held and the returned recorder alive across the next pool.
    with physical_harness(tenant_target, authority, capability_key, tmp_path, role) as second:
        second.pool.inner.resize(8, 8)
        second.pool.inner.wait(timeout=5)
        next_eight = [second.pool.getconn(timeout=.1) for _ in range(8)]
        try:
            assert len(set(next_eight)) == 8
            for connection in next_eight:
                assert connection.execute("SELECT 1").fetchone() == (1,)
                connection.rollback()
        finally:
            for connection in next_eight:
                second.pool.putconn(connection)
        second.pool.assert_released()
    assert all(connection.closed for connection in next_eight)
    print("FIXTURE_ISOLATION", json.dumps({
        "role": role, "borrower": borrower, "first_pids": pids,
        "open_after_production_close": 5, "open_after_fixture_disposal": 0,
        "next_simultaneous_usable_leases": 8,
    }, sort_keys=True))


def test_fixture_missing_runtime_return_still_fails_before_native_cleanup(
    tenant_target, authority, capability_key, tmp_path, monkeypatch, role,
):
    ownership_errors = []
    with pytest.raises(AssertionError) as caught:
        with physical_harness(tenant_target, authority, capability_key, tmp_path, role) as harness:
            leaked = harness.pool.getconn(timeout=1)
            pid = leaked.info.backend_pid
            assert_released, dispose = harness.pool.assert_released, harness.pool.native.dispose

            def record_ownership_failure():
                assert not leaked.closed
                try:
                    assert_released()
                except AssertionError as error:
                    ownership_errors.append(error)
                    raise

            def secondary_disposal_failure():
                dispose()
                raise OSError("explicit error after real fixture disposal")

            monkeypatch.setattr(harness.pool, "assert_released", record_ownership_failure)
            monkeypatch.setattr(harness.pool.native, "dispose", secondary_disposal_failure)
    assert len(ownership_errors) == 1 and caught.value is ownership_errors[0]
    assert harness.pool.held == {leaked} and harness.pool.returned == []
    assert any("OSError" in note for note in caught.value.__notes__)
    assert leaked.closed
    _assert_pids_absent(tenant_target, [pid])


def test_fixture_preserves_body_assertion_and_disposes_native_references(
    tenant_target, authority, capability_key, tmp_path, role,
):
    failure = AssertionError("explicit test-body failure")
    with pytest.raises(AssertionError) as caught:
        with physical_harness(tenant_target, authority, capability_key, tmp_path, role) as harness:
            connection = harness.pool.getconn(timeout=1)
            pid = connection.info.backend_pid
            harness.pool.putconn(connection)
            raise failure
    assert caught.value is failure
    assert connection.closed and not harness.pool.held
    _assert_pids_absent(tenant_target, [pid])


def test_fixture_setup_failure_closes_natives_created_before_configure(
    tenant_target, authority, capability_key, tmp_path, role,
):
    created, pids = [], []

    def failed_configure(connection):
        created.append(connection)
        pids.append(connection.info.backend_pid)
        raise OSError("explicit configure failure after actual native creation")

    with pytest.raises(TenantUnitOfWorkStartupError):
        with physical_harness(
            tenant_target, authority, capability_key, tmp_path, role,
            configure=failed_configure,
        ):
            pytest.fail("failed initialization must not yield the fixture")
    assert created and all(connection.closed for connection in created)
    inventory = created[0]._pool.connection_class
    assert set(inventory.connections) == set(created) and inventory.disposed
    _assert_pids_absent(tenant_target, pids)


def test_fixture_closes_real_native_creation_finishing_after_teardown(
    tenant_target, authority, capability_key, tmp_path, monkeypatch, role,
):
    started, release = Event(), Event()
    created, pids, workers = [], [], []
    try:
        with physical_harness(tenant_target, authority, capability_key, tmp_path, role) as harness:
            inventory = harness.pool.native
            actual_connect = inventory.connection_class.connect

            def delayed_connect(*args, **kwargs):
                started.set()
                assert release.wait(10)
                connection = actual_connect(*args, **kwargs)
                created.append(connection)
                pids.append(connection.info.backend_pid)
                return connection

            monkeypatch.setattr(inventory, "connection_class", SimpleNamespace(connect=delayed_connect))
            workers = list(harness.pool.inner._workers)
            harness.pool.inner.resize(2, 2)
            assert started.wait(2)
        # The real existing five-second close wait expired while creation was
        # gated. No timeout/production setting was changed for this control.
        assert harness.pool.inner.closed and inventory.disposed
        assert any(worker.is_alive() for worker in workers)
        assert created == []
    finally:
        release.set()
        for worker in workers:
            worker.join(timeout=3)
    assert all(not worker.is_alive() for worker in workers)
    assert len(created) == 1 and type(created[0]) is psycopg.Connection
    assert created[0] in inventory.connections and created[0].closed
    _assert_pids_absent(tenant_target, pids)
