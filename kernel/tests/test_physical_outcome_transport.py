"""PS10/11: real transport bounds, signing composition and owned pool leases."""
from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Thread

import psycopg
import pytest

from kernel import tenant_physical_outcome as physical
from kernel import signing_authority_io
from kernel.signing_authority_io import prepare_signing_conninfo
from kernel.tenant_uow import TenantBoundaryError
from kernel.tests._physical_outcome_proxy import PhysicalWireProxy
from kernel.tests._physical_outcome_support import (
    lose_commit_reply, physical_harness, request,
)
from kernel.tests._signing_observation_proxy import WireFaultProxy
from kernel.tests._signing_observation_support import retained_connections
from kernel.tests.test_physical_outcome_runtime import _caught, harness, role  # noqa: F401
from kernel.tests.postgresql_tenant_support import tenant_target  # noqa: F401
from kernel.tests.test_postgresql_tenant_migration import (
    authority, capability_key,  # noqa: F401
)


@pytest.mark.parametrize("phase", (
    "probe", "begin", "timeouts", "challenge", "challenge_read", "bind",
    "context", "status", "batch", "rollback",
))
def test_ps11_each_real_exchange_has_finite_wait_and_one_disposal(
    tenant_target, authority, capability_key, tmp_path, role, phase,
):
    with PhysicalWireProxy(tenant_target.role_dsn(role), fault=phase) as proxy:
        with physical_harness(
            tenant_target, authority, capability_key, tmp_path, role, dsn=proxy.dsn,
        ) as harness:
            checked = []
            real_check = harness.pool.inner._check
            def record_check(connection):
                checked.append(connection)
                return real_check(connection)
            harness.pool.inner._check = record_check
            started = time.monotonic()
            error = _caught(harness, lambda unit: unit.begin_batch(request(authority)))
            elapsed = time.monotonic() - started
            observation = error.physical_observation
            assert proxy.withheld.is_set()
            assert 2.0 <= elapsed < 3.5
            assert observation.physical_status == ("COMMITTED" if phase == "rollback" else "UNKNOWN")
            assert observation.batch_observation == ("MATCHING_COMMITTED" if phase == "rollback" else "UNAVAILABLE")
            assert len(harness.pool.acquired) == (1 if phase == "probe" else 2)
            assert harness.pool.peak == 1
            harness.pool.assert_released()
            if phase == "probe":
                assert observation.observer_failure == "CHECKOUT_UNAVAILABLE"
                assert observation.cleanup == "NOT_ACQUIRED"
            else:
                assert observation.cleanup == "DISCARDED"
                assert harness.pool.acquired[-1].closed
            assert sum(name == "commit" for _, name, _, _ in proxy.statements) == 1
            assert sum(e[0] == "REQUEST" for e in harness.pool.events) == 2
            assert len(checked) == 2, "failed health check renewed its budget"
            if phase == "probe":
                assert checked[-1].closed
                assert checked[-1].pgconn.status == psycopg.pq.ConnStatus.BAD
                assert checked[-1] not in harness.pool.acquired


@pytest.mark.parametrize("phase", ("status", "batch"))
def test_ps11_partial_wire_result_is_not_a_fact(
    tenant_target, authority, capability_key, tmp_path, role, phase,
):
    with PhysicalWireProxy(tenant_target.role_dsn(role), fault=phase, partial=True) as proxy:
        with physical_harness(
            tenant_target, authority, capability_key, tmp_path, role, dsn=proxy.dsn,
        ) as harness:
            observation = _caught(harness, lambda unit: unit.begin_batch(request(authority))).physical_observation
            assert (phase, b"D") in proxy.results
            assert (phase, b"C") in proxy.results
            assert (phase, b"Z") in proxy.results
            assert observation.physical_status == "UNKNOWN"
            assert observation.batch_observation == "UNAVAILABLE"
            assert observation.status_received is (phase == "batch")
            assert observation.raw_status == ("committed" if phase == "batch" else None)
            assert observation.cleanup == "DISCARDED"


@pytest.mark.parametrize("phase", ("batch", "rollback"))
def test_ps11_qualified_actual_abort_survives_later_wire_loss(
    tenant_target, authority, capability_key, tmp_path, role, monkeypatch, phase,
):
    with PhysicalWireProxy(tenant_target.role_dsn(role), fault=phase) as proxy:
        with physical_harness(
            tenant_target, authority, capability_key, tmp_path, role, dsn=proxy.dsn,
        ) as harness:
            def actual_abort(connection):
                connection.rollback()
                proxy.ambiguous.set()
            lose_commit_reply(monkeypatch, harness, before=actual_abort)
            observation = _caught(harness, lambda unit: unit.begin_batch(request(authority))).physical_observation
            assert observation.physical_status == "ABORTED"
            assert observation.raw_status == "aborted" and observation.status_received
            assert observation.batch_observation == ("UNAVAILABLE" if phase == "batch" else "ABSENT_AT_OBSERVATION")
            assert observation.cleanup == "DISCARDED"
            assert proxy.withheld.is_set()


def test_ps11_real_bind_forwards_one_event_and_unrenewed_provider_deadline(
    harness, authority, monkeypatch,
):
    mint = harness.signing.issuer.mint
    read = harness.signing.reader.current
    execute = physical._BoundedTransaction.execute
    mint_inputs, reader_inputs, challenge_times = [], [], []
    def capture_mint(identity, principal, challenge, **kwargs):
        mint_inputs.append(dict(kwargs))
        return mint(identity, principal, challenge, **kwargs)
    def capture_read(kid, **kwargs):
        reader_inputs.append(dict(kwargs))
        return read(kid, **kwargs)
    def delayed_challenge(transaction, query, params=None):
        if "create_tenant_challenge" in query:
            challenge_times.append(time.monotonic())
            time.sleep(0.08)
        return execute(transaction, query, params)
    monkeypatch.setattr(harness.signing.issuer, "mint", capture_mint)
    monkeypatch.setattr(harness.signing.reader, "current", capture_read)
    monkeypatch.setattr(physical._BoundedTransaction, "execute", delayed_challenge)
    lose_commit_reply(monkeypatch, harness)
    observation = _caught(harness, lambda unit: unit.begin_batch(request(authority))).physical_observation
    assert observation.physical_status == "COMMITTED"
    assert mint_inputs[0] == {"cancel_event": None, "deadline_monotonic": None}
    assert reader_inputs[0] == mint_inputs[0]
    assert len(mint_inputs) == len(reader_inputs) == 2
    assert reader_inputs[1] == mint_inputs[1]
    event = mint_inputs[1]["cancel_event"]
    deadline = mint_inputs[1]["deadline_monotonic"]
    assert isinstance(event, Event)
    assert not event.is_set()
    assert challenge_times[0] + 4.8 < deadline <= challenge_times[0] + 5.0
    assert len(harness.signing.client.calls) == 2


@pytest.mark.parametrize("cancel", (False, True))
def test_ps11_real_provider_blackhole_expiry_and_cancellation_reach_runtime(
    harness, authority, tenant_target, monkeypatch, cancel,
):
    retained = retained_connections(monkeypatch)
    mint = harness.signing.issuer.mint
    observed = []
    workers = []
    with WireFaultProxy(tenant_target.role_dsn("ofarm_app"), "reply") as proxy:
        def capture_mint(identity, principal, challenge, **kwargs):
            event = kwargs.get("cancel_event")
            if event is not None:
                observed.append((event, kwargs["deadline_monotonic"], time.monotonic()))
                harness.signing.reader._conninfo = prepare_signing_conninfo(proxy.dsn)
                if cancel:
                    def cancel_after_dispatch():
                        assert proxy.withheld.wait(3)
                        event.set()
                    worker = Thread(target=cancel_after_dispatch)
                    workers.append(worker)
                    worker.start()
            return mint(identity, principal, challenge, **kwargs)
        monkeypatch.setattr(harness.signing.issuer, "mint", capture_mint)
        lose_commit_reply(monkeypatch, harness)
        started = time.monotonic()
        observation = _caught(harness, lambda unit: unit.begin_batch(request(authority))).physical_observation
        elapsed = time.monotonic() - started
        for worker in workers:
            worker.join(2)
            assert not worker.is_alive()
        assert proxy.withheld.is_set()
        assert len(observed) == 1 and observed[0][0].is_set()
        assert observation.physical_status == "UNKNOWN"
        assert observation.observer_failure == "CAPABILITY_REFUSED"
        assert observation.cleanup == "DISCARDED"
        assert elapsed < (1.0 if cancel else 6.0)
        if not cancel:
            assert elapsed >= 4.8
        assert len(harness.signing.client.calls) == 1
        assert len(retained) == 2 and all(connection.closed for connection, _ in retained)
        assert all(connection.pgconn.status == psycopg.pq.ConnStatus.BAD for connection, _ in retained)


@pytest.mark.parametrize("transition", ("acquired", "begin", "challenge", "status", "batch", "cleanup"))
def test_ps10_ps11_cancellation_at_observer_ownership_transitions(
    harness, authority, monkeypatch, transition,
):
    """Cancellation seam preserves real providers and all already-received facts."""
    event = Event()
    monkeypatch.setattr(physical, "Event", lambda: event)
    command, execute, rollback = (
        physical._BoundedTransaction.command,
        physical._BoundedTransaction.execute,
        physical._BoundedTransaction.rollback,
    )
    if transition == "acquired":
        harness.pool.on_get = lambda _c, n: event.set() if n == 2 else None
    def cancel_command(transaction, query):
        result = command(transaction, query)
        if transition == "begin":
            event.set()
        return result
    def cancel_execute(transaction, query, params=None):
        if ((transition == "challenge" and "create_tenant_challenge" in query)
            or (transition == "status" and "pg_xact_status" in query)
            or (transition == "batch" and "FROM ofarm.governed_write_batch" in query)):
            raise asyncio.CancelledError("fixture observer cancellation")
        return execute(transaction, query, params)
    def cancel_cleanup(transaction):
        if transition == "cleanup":
            raise asyncio.CancelledError("fixture cleanup cancellation")
        return rollback(transaction)
    monkeypatch.setattr(physical._BoundedTransaction, "command", cancel_command)
    monkeypatch.setattr(physical._BoundedTransaction, "execute", cancel_execute)
    monkeypatch.setattr(physical._BoundedTransaction, "rollback", cancel_cleanup)
    lose_commit_reply(monkeypatch, harness)
    observation = _caught(harness, lambda unit: unit.begin_batch(request(authority))).physical_observation
    assert event.is_set()
    assert observation.physical_status == ("COMMITTED" if transition == "cleanup" else "UNKNOWN")
    assert observation.cleanup == "DISCARDED"
    assert observation.observer_failure == ("CLEANUP_UNAVAILABLE" if transition == "cleanup" else "CANCELLED")
    assert len(harness.pool.acquired) == 2 and harness.pool.peak == 1


@pytest.mark.parametrize("finish", ("ordinary", "body-error", "rollback-only", "allocator-failure"))
def test_ps10_eight_ordinary_calls_never_reserve_observers(
    harness, authority, finish,
):
    barrier = Barrier(8)
    harness.pool.inner.resize(8, 8)
    harness.pool.inner.wait(timeout=5)
    def call():
        try:
            with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
                barrier.wait(timeout=8)
                assert len(harness.pool.acquired) == 8
                assert harness.pool.peak == 8
                if finish == "body-error":
                    raise ValueError("fixture body failed")
                if finish == "rollback-only":
                    unit._refuse_selection()
                if finish == "allocator-failure":
                    # Invalid request type is refused before any SQL write.
                    with pytest.raises(RuntimeError):
                        unit.begin_batch(object())
        except ValueError:
            assert finish == "body-error"
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _: call(), range(8)))
    assert len(harness.pool.acquired) == 8
    assert sum(e[0] == "REQUEST" for e in harness.pool.events) == 8
    harness.pool.assert_released()


def test_ps10_pool_pressure_bounds_observation_and_late_release_is_not_retried(
    harness, authority, monkeypatch,
):
    held = []
    original_put = harness.pool.on_put
    def fill_after_original(_connection, ordinal):
        if ordinal == 1:
            # Obtain seven remaining real leases; original return occurs next.
            held.extend(harness.pool.inner.getconn(timeout=1) for _ in range(7))
    harness.pool.on_put = fill_after_original
    original_get = harness.pool.inner.getconn
    requests = []
    def get(*, timeout):
        requests.append(timeout)
        if timeout == 0.1:
            held.append(original_get(timeout=1))
        return original_get(timeout=timeout)
    monkeypatch.setattr(harness.pool.inner, "getconn", get)
    lose_commit_reply(monkeypatch, harness)
    try:
        started = time.monotonic()
        observation = _caught(harness, lambda unit: unit.begin_batch(request(authority))).physical_observation
        assert time.monotonic() - started < 1.5
        assert observation.observer_failure == "CHECKOUT_UNAVAILABLE"
        assert observation.physical_status == "UNKNOWN"
        assert len(harness.pool.acquired) == 1
        assert requests.count(0.1) == 1
        assert harness.pool.inner.get_stats()["pool_size"] == 8
    finally:
        harness.pool.on_put = original_put
        for connection in held:
            harness.pool.inner.putconn(connection)
    assert observation.physical_status == "UNKNOWN"


def test_ps10_shutdown_after_original_return_disposes_without_observer_retry(
    harness, authority, monkeypatch,
):
    actual_put = harness.pool.putconn
    def stop_after_return(connection):
        actual_put(connection)
        if len(harness.pool.returned) == 1:
            harness.pool.inner.close(timeout=2)
    monkeypatch.setattr(harness.pool, "putconn", stop_after_return)
    lose_commit_reply(monkeypatch, harness)
    error = _caught(harness, lambda unit: unit.begin_batch(request(authority)))
    assert error.physical_observation.physical_status == "UNKNOWN"
    assert error.physical_observation.observer_failure == "CHECKOUT_UNAVAILABLE"
    assert len(harness.pool.acquired) == 1
    assert sum(e[0] == "REQUEST" for e in harness.pool.events) == 2
    # Retaining the error is not a live lease or subsequent observation API.
    harness.pool.assert_released()


def test_ps10_body_process_cancellation_propagates_unchanged_without_observer(
    harness, authority,
):
    cancellation = asyncio.CancelledError("fixture original body cancellation")
    with pytest.raises(asyncio.CancelledError) as caught:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            unit.begin_batch(request(authority))
            raise cancellation
    assert caught.value is cancellation
    assert len(harness.pool.acquired) == 1
    harness.pool.assert_released()


@pytest.mark.parametrize("ordinal", (1, 2))
def test_ps10_ps11_pool_return_failure_preserves_original_error_and_received_fact(
    harness, authority, monkeypatch, ordinal,
):
    """Post-return fault reports uncertainty without attempting a second return."""
    actual_put = harness.pool.putconn
    def return_then_fail(connection):
        actual_put(connection)
        if len(harness.pool.returned) == ordinal:
            raise OSError("fixture return acknowledgement lost")
    monkeypatch.setattr(harness.pool, "putconn", return_then_fail)
    lose_commit_reply(monkeypatch, harness)
    error = _caught(harness, lambda unit: unit.begin_batch(request(authority)))
    observation = error.physical_observation
    assert observation.physical_status == ("UNKNOWN" if ordinal == 1 else "COMMITTED")
    assert observation.observer_failure == ("ORIGINAL_RETURN_UNAVAILABLE" if ordinal == 1 else "CLEANUP_UNAVAILABLE")
    assert observation.cleanup == ("NOT_ACQUIRED" if ordinal == 1 else "RETURN_FAILED")
    assert len(harness.pool.returned) == ordinal
    harness.pool.assert_released()


def test_ps11_cursor_cleanup_failure_retains_complete_matching_fact(
    harness, authority, monkeypatch,
):
    close = physical._BoundedTransaction.close
    rollback = physical._BoundedTransaction.rollback
    cleaning = []
    def observe_rollback(transaction):
        cleaning.append(transaction)
        return rollback(transaction)
    def fail_close(transaction):
        close(transaction)
        if transaction in cleaning:
            raise OSError("fixture cursor cleanup failed after complete evidence")
    monkeypatch.setattr(physical._BoundedTransaction, "rollback", observe_rollback)
    monkeypatch.setattr(physical._BoundedTransaction, "close", fail_close)
    lose_commit_reply(monkeypatch, harness)
    observation = _caught(harness, lambda unit: unit.begin_batch(request(authority))).physical_observation
    assert observation.physical_status == "COMMITTED"
    assert observation.batch_observation == "MATCHING_COMMITTED"
    assert observation.observer_failure == "CLEANUP_UNAVAILABLE"
    assert observation.cleanup == "DISCARDED"
    harness.pool.assert_released()


def test_ps10_mixed_seven_ordinary_and_one_observing_call_share_eight_leases(
    harness, authority, monkeypatch,
):
    ready, release = Barrier(8), Event()
    original = []
    actual_commit = psycopg.Connection.commit
    def lost(connection):
        result = actual_commit(connection)
        if original and connection is original[0]:
            raise OSError("fixture lost mixed-call COMMIT reply")
        return result
    monkeypatch.setattr(psycopg.Connection, "commit", lost)
    harness.pool.inner.resize(8, 8)
    harness.pool.inner.wait(timeout=5)
    def ordinary():
        with harness.runtime.tenant_unit_of_work(harness.principal):
            ready.wait(timeout=10)
            assert release.wait(10)
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = [executor.submit(ordinary) for _ in range(7)]
        ready.wait(timeout=10)
        try:
            def work(unit):
                original.append(harness.pool.acquired[-1])
                unit.begin_batch(request(authority))
            # Seven unrelated calls intentionally still hold their leases here.
            with pytest.raises(TenantBoundaryError) as caught:
                with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
                    work(unit)
            error = caught.value
            observation = error.physical_observation
            if observation.physical_status == "COMMITTED":
                assert observation.batch_observation == "MATCHING_COMMITTED"
                assert len(harness.pool.acquired) == 9
                assert harness.pool.acquired[-1] in harness.pool.returned
            else:
                # The released slot is not reserved: actual pool pressure may
                # consume the sole100ms observer checkout budget.
                assert observation.physical_status == "UNKNOWN"
                assert observation.observer_failure == "CHECKOUT_UNAVAILABLE"
                assert len(harness.pool.acquired) == 8
            assert sum(e[0] == "REQUEST" for e in harness.pool.events) == 9
            assert harness.pool.peak == 8 and len(harness.pool.held) == 7
            assert original[0] in harness.pool.returned
            assert harness.pool.inner.get_stats()["pool_size"] == 8
        finally:
            release.set()
            for future in futures:
                future.result(timeout=10)
    harness.pool.assert_released()


def test_ps10_actual_late_pool_connection_is_not_delivered_or_retried(
    harness, authority, monkeypatch,
):
    harness.pool.inner.resize(8, 8)
    harness.pool.inner.wait(timeout=5)
    held = [harness.pool.inner.getconn(timeout=1) for _ in range(7)]
    connect = harness.pool.inner._connect
    started, finish, completed = Event(), Event(), Event()
    late = []
    def late_connect(*args, **kwargs):
        started.set()
        assert finish.wait(3)
        connection = connect(*args, **kwargs)
        late.append(connection)
        completed.set()
        return connection
    monkeypatch.setattr(harness.pool.inner, "_connect", late_connect)
    lose_commit_reply(monkeypatch, harness)
    try:
        error = _caught(harness, lambda unit: unit.begin_batch(request(authority)))
        assert started.is_set()
        assert error.physical_observation.observer_failure == "CHECKOUT_UNAVAILABLE"
        assert error.physical_observation.physical_status == "UNKNOWN"
        assert len(harness.pool.acquired) == 1
        assert sum(event[0] == "REQUEST" for event in harness.pool.events) == 2
    finally:
        finish.set()
        for connection in held:
            harness.pool.inner.putconn(connection)
    assert completed.wait(3)
    harness.pool.inner.wait(timeout=5)
    assert len(late) == 1 and late[0] not in harness.pool.acquired
    assert late[0].info.transaction_status == psycopg.pq.TransactionStatus.IDLE
    harness.pool.assert_released()
    harness.manager.close()
    assert late[0].closed


def test_ps11_existing_kms_rpc_timeout_stays_separate_from_provider_deadline(
    harness, authority, monkeypatch,
):
    actual_sign = harness.signing.client.asymmetric_sign
    observed = []
    def sign(*, request, retry, timeout):
        observed.append((retry, timeout))
        return actual_sign(request=request, retry=retry, timeout=timeout)
    monkeypatch.setattr(harness.signing.client, "asymmetric_sign", sign)
    lose_commit_reply(monkeypatch, harness)
    observation = _caught(harness, lambda unit: unit.begin_batch(request(authority))).physical_observation
    assert observation.physical_status == "COMMITTED"
    assert observed == [(None, 5.0), (None, 5.0)]
