"""Real PostgreSQL crash/reuse controls, through both ordinary runtime roles.

Faults delay only delivery of original finalization to the manager. Database
status, batch rows, xids and WAL positions are never substituted.
"""
from __future__ import annotations

from contextlib import contextmanager, suppress

import psycopg
from psycopg.conninfo import make_conninfo
import pytest

from kernel import tenant_uow
from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome
from kernel.tests._physical_outcome_crash import (
    crash_authority, crash_cluster, evidence, lsn,
)
from kernel.tests._physical_outcome_proxy import PhysicalWireProxy
from kernel.tests._physical_outcome_support import (
    batch_tuple, physical_harness, request,
)

ROLES = ("ofarm_app", "ofarm_worker")


@pytest.fixture(scope="module")
def crash_fixture():
    with crash_cluster() as cluster:
        with crash_authority(cluster) as seeded:
            yield cluster, *seeded


@pytest.fixture(autouse=True)
def resume_owned_walwriter_after_failed_control(crash_fixture):
    cluster = crash_fixture[0]
    yield
    if cluster.paused_writer is not None:
        cluster.signal(cluster.paused_writer, "CONT")
        cluster.paused_writer = None


def arrange_observer(monkeypatch, harness):
    original_observe = tenant_uow.observe_physical_outcome

    def after_recovery(pool, bind, principal, capture):
        if pool is harness.pool and capture and capture[0][2] is True:
            # Fixture recovery finishes before the one observer starts. Wait
            # for the pool's replacement of the discarded original lease.
            pool.inner.wait(timeout=10)
        return original_observe(pool, bind, principal, capture)

    monkeypatch.setattr(tenant_uow, "observe_physical_outcome", after_recovery)


def arrange_finalization(monkeypatch, harness, action, *, commit):
    """Before-COMMIT/observer-transition schedule; durable reply loss uses wire."""
    original_commit = psycopg.Connection.commit
    calls = []

    def finalize(connection):
        if connection is harness.pool.acquired[0]:
            calls.append(connection)
            if commit:
                original_commit(connection)
            try:
                action(connection)
            except Exception as exc:
                pytest.fail(f"crash scheduling/control assertion failed: {exc}")
            raise OSError("fixture withheld original finalization completion")
        return original_commit(connection)

    monkeypatch.setattr(psycopg.Connection, "commit", finalize)
    arrange_observer(monkeypatch, harness)
    return calls


def assert_one_wire_commit(proxy):
    commits = [item for item in proxy.statements if item[1] == "commit"]
    assert len(commits) == 1
    assert proxy.ambiguous.is_set()


def capture_eligibility(monkeypatch):
    original = tenant_uow._allocate_governed_batch
    captured = []

    def record(*args, **kwargs):
        result = original(*args, **kwargs)
        captured.append(result)
        return result

    monkeypatch.setattr(tenant_uow, "_allocate_governed_batch", record)
    return captured


@contextmanager
def bound_connection(target, harness, role):
    with psycopg.connect(target.role_dsn(role)) as connection:
        connection.execute("BEGIN ISOLATION LEVEL READ COMMITTED")
        harness.manager._bind(connection, harness.principal)
        assert connection.execute("SELECT SESSION_USER").fetchone() == (role,)
        try:
            yield connection
        finally:
            if not connection.closed:
                with suppress(psycopg.Error):
                    connection.rollback()


def batch_row(connection, batch):
    return connection.execute(
        "SELECT tenant_id, batch_id, full_xid::text, authenticated_principal_ref, "
        "governed_operation, request_id, runtime_bundle_digest, knowledge_position, "
        "created_at FROM ofarm.governed_write_batch "
        "WHERE tenant_id = %s AND full_xid = %s::xid8",
        (batch.tenant_id, str(batch.full_xid)),
    ).fetchone()


def assert_matching(row, batch):
    assert row is not None
    assert (row[0], row[1], int(row[2]), *row[3:]) == batch_tuple(batch)


def observation(caught, harness, physical, batch_kind):
    assert caught.value.outcome is TenantBoundaryOutcome.FINALIZATION_UNKNOWN
    result = caught.value.physical_observation
    assert result.physical_status == physical
    assert result.batch_observation == batch_kind
    assert harness.audit.reasons == []
    assert harness.pool.peak == 1
    harness.pool.assert_released()
    return result


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("replacement_commit", (True, False))
def test_ps15_actual_full_xid_reuse(
    crash_fixture, tmp_path, monkeypatch, role, replacement_commit,
):
    cluster, target, authority, key = crash_fixture
    facts = {}
    with physical_harness(target, authority, key, tmp_path, role) as harness:
        cluster.checkpoint(pause_writer=True)
        captured = capture_eligibility(monkeypatch)

        def crash_then_replace(_connection):
            facts.update(cluster.crash())
            with physical_harness(target, authority, key, tmp_path, role) as replacement:
                try:
                    with replacement.runtime.tenant_unit_of_work(replacement.principal) as unit:
                        other = unit.begin_batch(request(authority, "replacement"))
                        facts["replacement_full_xid"] = other.full_xid
                        assert other.full_xid == original.full_xid, "actual xid reuse was not obtained"
                        assert batch_tuple(other) != batch_tuple(original)
                        if not replacement_commit:
                            raise RuntimeError("fixture aborts replacement")
                except RuntimeError as exc:
                    assert not replacement_commit
                    assert str(exc) == "fixture aborts replacement"

        calls = arrange_finalization(monkeypatch, harness, crash_then_replace, commit=False)
        with pytest.raises(TenantBoundaryError) as caught:
            with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
                original = unit.begin_batch(request(authority, "original"))
                assert captured[0] == (original, True)
                positions = cluster.positions()
                assert lsn(positions["flush"]) < lsn(positions["insert"])
                facts.update(original_full_xid=original.full_xid, allocation_wal=positions,
                             original_eligibility=captured[0][1])
        expected = ("UNKNOWN", "CONFLICT") if replacement_commit else ("ABORTED", "ABSENT_AT_OBSERVATION")
        result = observation(caught, harness, *expected)
        assert result.original_batch is original
        assert result.raw_status == ("committed" if replacement_commit else "aborted")
        assert len(calls) == 1
        evidence("PS15", role, replacement_commit=replacement_commit, **facts,
                 physical_status=result.physical_status, batch_observation=result.batch_observation)


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("restart", (False, True))
def test_ps16_durable_commit_survives_child_crash_and_postmaster_restart(
    crash_fixture, tmp_path, monkeypatch, role, restart,
):
    cluster, target, authority, key = crash_fixture
    facts = {}
    proxy = PhysicalWireProxy(target.role_dsn(role), on_commit=lambda: durable_then_crash())
    with proxy, physical_harness(target, authority, key, tmp_path, role, dsn=proxy.dsn) as harness:
        cluster.checkpoint()
        captured = capture_eligibility(monkeypatch)

        def durable_then_crash():
            after = cluster.positions()
            assert lsn(after["flush"]) >= lsn(after["insert"])
            assert lsn(after["insert"]) > lsn(facts["insert_record_end"])
            facts.update(commit_record_end=after["insert"], flush_after_commit=after["flush"])
            facts.update(cluster.crash(restart=restart))

        arrange_observer(monkeypatch, harness)
        with pytest.raises(TenantBoundaryError) as caught:
            with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
                original = unit.begin_batch(request(authority, "durable"))
                assert captured[0] == (original, True)
                facts.update(original_full_xid=original.full_xid,
                             original_eligibility=captured[0][1],
                             insert_record_end=cluster.positions()["insert"])
        assert facts["postmaster_restarted"] is restart
        assert facts["system_identifier"] == cluster.system_identifier
        result = observation(caught, harness, "COMMITTED", "MATCHING_COMMITTED")
        assert result.original_batch is original
        assert result.raw_status == "committed"
        assert_one_wire_commit(proxy)
        evidence("PS16", role, **facts, wire_commit_reply_withheld=True,
                 physical_status=result.physical_status,
                 batch_observation=result.batch_observation)


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("reuse", (False, True))
def test_ps18_historical_async_commit_loss_is_ineligible(
    crash_fixture, tmp_path, monkeypatch, role, reuse,
):
    cluster, target, authority, key = crash_fixture
    facts = {}
    dsn = make_conninfo(target.role_dsn(role), options="-c synchronous_commit=off")
    proxy = PhysicalWireProxy(dsn, on_commit=lambda: visible_then_lost())
    with proxy, physical_harness(target, authority, key, tmp_path, role, dsn=proxy.dsn) as harness:
        with bound_connection(target, harness, role) as witness:
            cluster.checkpoint(pause_writer=True)
            captured = capture_eligibility(monkeypatch)

            def visible_then_lost():
                after = cluster.positions()
                facts.update(commit_record_end=after["insert"], flush_after_commit=after["flush"])
                assert lsn(after["insert"]) > lsn(facts["before_commit_insert_lsn"])
                assert lsn(after["flush"]) < lsn(after["insert"])
                assert_matching(batch_row(witness, original), original)
                facts["ordinary_role_witness_saw_original_commit"] = True
                facts.update(cluster.crash())
                if reuse:
                    with physical_harness(target, authority, key, tmp_path, role) as replacement:
                        with pytest.raises(RuntimeError, match="fixture aborts replacement"):
                            with replacement.runtime.tenant_unit_of_work(replacement.principal) as unit:
                                other = unit.begin_batch(request(authority, "async-replacement"))
                                facts["replacement_full_xid"] = other.full_xid
                                assert other.full_xid == original.full_xid, "actual xid reuse was not obtained"
                                raise RuntimeError("fixture aborts replacement")
                with bound_connection(target, harness, role) as recovered:
                    recovered_xid = int(recovered.execute(
                        "SELECT pg_current_xact_id()::text"
                    ).fetchone()[0])
                    assert recovered_xid > original.full_xid
                    facts["recovered_bound_full_xid"] = recovered_xid
                    status = recovered.execute(
                        "SELECT pg_xact_status(%s::xid8)", (str(original.full_xid),),
                    ).fetchone()[0]
                    assert status == "aborted", "historical commit loss was not observed"
                    assert batch_row(recovered, original) is None
                    facts.update(recovered_status=status, recovered_batch_absent=True)

            arrange_observer(monkeypatch, harness)
            with pytest.raises(TenantBoundaryError) as caught:
                with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
                    original = unit.begin_batch(request(authority, "asynchronous"))
                    assert captured[0] == (original, False)
                    positions = cluster.positions()
                    facts.update(original_full_xid=original.full_xid,
                                 original_eligibility=captured[0][1],
                                 insert_record_end=positions["insert"])
                    if reuse:
                        assert lsn(positions["flush"]) < lsn(positions["insert"])
                    else:
                        facts["flush_before_commit"] = cluster.flush_insert(positions["insert"])
                    facts["before_commit_insert_lsn"] = cluster.positions()["insert"]
            assert facts["ordinary_role_witness_saw_original_commit"] is True
            assert facts["postmaster_restarted"] is False
            assert facts["recovered_status"] == "aborted"
            assert facts["recovered_batch_absent"] is True
            result = observation(caught, harness, "UNKNOWN", "UNAVAILABLE")
            assert result.original_batch is original
            assert result.observer_failure == "RECOVERY_UNAVAILABLE"
            assert len(harness.pool.acquired) == 1
            assert_one_wire_commit(proxy)
            evidence("PS18", role, reuse=reuse, **facts, wire_commit_reply_withheld=True,
                     physical_status=result.physical_status,
                     batch_observation=result.batch_observation,
                     observer_failure=result.observer_failure)


@pytest.mark.parametrize("role", ROLES)
def test_ps05_real_recovery_future_xid_refuses_status(
    crash_fixture, tmp_path, monkeypatch, role,
):
    cluster, target, authority, key = crash_fixture
    facts = {}
    from kernel import tenant_physical_outcome as physical
    original_execute = physical._BoundedTransaction.execute

    def record_real_status_failure(transaction, query, params=None):
        try:
            return original_execute(transaction, query, params)
        except psycopg.Error as exc:
            if "pg_xact_status" in query:
                facts["observer_status_sqlstate"] = exc.sqlstate
            raise

    monkeypatch.setattr(physical._BoundedTransaction, "execute", record_real_status_failure)
    with physical_harness(target, authority, key, tmp_path, role) as harness:
        cluster.checkpoint(pause_writer=True)
        # Allocate actual xids without durable WAL. This deliberately puts the
        # eventual original ahead of the recovery horizon and observer xid.
        with psycopg.connect(target.role_dsn(role), autocommit=True) as advance:
            for _ in range(12):
                advance.execute("BEGIN")
                advance.execute("SELECT pg_current_xact_id()")
                advance.execute("ROLLBACK")

        def crash_before_commit(_connection):
            facts.update(cluster.crash())
            with psycopg.connect(target.role_dsn(role), autocommit=True) as reader:
                with pytest.raises(psycopg.Error) as status_error:
                    reader.execute("SELECT pg_xact_status(%s::xid8)", (str(original.full_xid),))
                assert status_error.value.sqlstate == "22023"
                facts["direct_status_sqlstate"] = status_error.value.sqlstate

        calls = arrange_finalization(monkeypatch, harness, crash_before_commit, commit=False)
        with pytest.raises(TenantBoundaryError) as caught:
            with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
                original = unit.begin_batch(request(authority, "future-xid"))
                facts["original_full_xid"] = original.full_xid
                positions = cluster.positions()
                assert lsn(positions["flush"]) < lsn(positions["insert"])
        result = observation(caught, harness, "UNKNOWN", "UNAVAILABLE")
        assert result.observer_failure == "STATUS_UNAVAILABLE"
        assert facts["observer_status_sqlstate"] == "22023"
        assert result.cleanup == "DISCARDED"
        assert result.status_received is False
        assert len(harness.pool.acquired) == 2
        assert len(calls) == 1
        evidence("PS05", role, **facts, physical_status=result.physical_status,
                 observer_failure=result.observer_failure, cleanup=result.cleanup)


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("capture", (False, True))
def test_ps16_crash_before_capture_or_commit(
    crash_fixture, tmp_path, monkeypatch, role, capture,
):
    cluster, target, authority, key = crash_fixture
    facts = {}
    with physical_harness(target, authority, key, tmp_path, role) as harness:
        cluster.checkpoint()
        calls = arrange_finalization(
            monkeypatch, harness, lambda connection: facts.update(cluster.crash()), commit=False,
        )
        original = None
        with pytest.raises(TenantBoundaryError) as caught:
            with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
                if capture:
                    original = unit.begin_batch(request(authority, "before-commit"))
                    insert_record_end = cluster.positions()["insert"]
                    facts["flush_before_commit"] = cluster.flush_insert(insert_record_end)
                    facts["insert_record_end"] = insert_record_end
                # With no batch, this crashes after entry but before any capture.
        expected = ("ABORTED", "ABSENT_AT_OBSERVATION") if capture else ("UNKNOWN", "UNAVAILABLE")
        result = observation(caught, harness, *expected)
        assert result.original_batch is original
        assert len(calls) == 1
        evidence("PS16-before", role, capture=capture, **facts,
                 physical_status=result.physical_status, batch_observation=result.batch_observation)


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("stage", ("before_status", "after_status", "after_batch", "aborted_after_status"))
def test_ps16_crash_during_observation_retains_only_received_facts(
    crash_fixture, tmp_path, monkeypatch, role, stage,
):
    from kernel import tenant_physical_outcome as physical

    cluster, target, authority, key = crash_fixture
    facts = {}
    with physical_harness(target, authority, key, tmp_path, role) as harness:
        cluster.checkpoint()
        is_abort = stage == "aborted_after_status"
        calls = arrange_finalization(
            monkeypatch, harness,
            (lambda connection: connection.rollback()) if is_abort else (lambda connection: None),
            commit=not is_abort,
        )
        original_execute = physical._BoundedTransaction.execute
        fired = []

        def interrupted(transaction, query, params=None):
            is_status = "pg_xact_status" in query
            is_batch = "FROM ofarm.governed_write_batch" in query
            if is_status and stage == "before_status":
                facts.update(cluster.crash())
                fired.append(stage)
            cursor = original_execute(transaction, query, params)
            if (is_status and stage in {"after_status", "aborted_after_status"}) or (is_batch and stage == "after_batch"):
                facts.update(cluster.crash())
                fired.append(stage)
            return cursor

        monkeypatch.setattr(physical._BoundedTransaction, "execute", interrupted)
        with pytest.raises(TenantBoundaryError) as caught:
            with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
                original = unit.begin_batch(request(authority, "observation-crash"))
        expected = {"after_batch": ("COMMITTED", "MATCHING_COMMITTED"),
                    "aborted_after_status": ("ABORTED", "UNAVAILABLE")}.get(stage, ("UNKNOWN", "UNAVAILABLE"))
        result = observation(caught, harness, *expected)
        assert result.original_batch is original
        assert len(calls) == 1
        assert fired == [stage]
        assert len(harness.pool.acquired) == 2, "failed observer must not retry"
        assert result.cleanup == "DISCARDED"
        evidence("PS16-observer", role, stage=stage, **facts,
                 original_full_xid=original.full_xid, raw_status=result.raw_status,
                 physical_status=result.physical_status, batch_observation=result.batch_observation,
                 observer_failure=result.observer_failure, cleanup=result.cleanup)
