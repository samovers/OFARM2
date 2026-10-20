"""PS01–09/12/14/17 through real runtime, roles and original guarded INSERT."""
from __future__ import annotations

import time
from dataclasses import FrozenInstanceError, astuple
from datetime import timedelta
from uuid import uuid4

import psycopg
import pytest

from kernel import tenant_physical_outcome as physical
from kernel import tenant_uow
from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome
from kernel.tests._physical_outcome_proxy import PhysicalWireProxy
from kernel.tests._physical_outcome_support import (
    batch_tuple, lose_commit_reply, physical_harness, request,
)
from kernel.tests._signing_observation_proxy import tls_context
from kernel.tests.test_postgresql_tenant_migration import (
    authority, capability_key, tenant_target,  # noqa: F401
)


@pytest.fixture(params=("ofarm_app", "ofarm_worker"))
def role(request):
    return request.param


@pytest.fixture
def harness(tenant_target, authority, capability_key, tmp_path, role):
    with physical_harness(tenant_target, authority, capability_key, tmp_path, role) as value:
        yield value


def _caught(harness, action):
    with pytest.raises(TenantBoundaryError) as raised:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            action(unit)
    error = raised.value
    assert error.outcome is TenantBoundaryOutcome.FINALIZATION_UNKNOWN
    assert str(error) == "tenant boundary refused (FINALIZATION_UNKNOWN)"
    assert harness.audit.reasons == []
    harness.pool.assert_released()
    return error


def _stored(target, batch):
    with psycopg.connect(target.target_admin_dsn) as connection:
        return connection.execute(
            "SELECT count(*) FROM ofarm.governed_write_batch WHERE batch_id = %s",
            (batch.batch_id,),
        ).fetchone()[0]


def test_ps02_ps14_lost_wire_commit_delivers_frozen_matching_fact(
    tenant_target, authority, capability_key, tmp_path, role,
):
    tls, certificate = tls_context(tmp_path)
    with PhysicalWireProxy(tenant_target.role_dsn(role), tls=tls, certificate=certificate) as proxy:
        with physical_harness(
            tenant_target, authority, capability_key, tmp_path, role, dsn=proxy.dsn,
        ) as harness:
            batches = []
            error = _caught(harness, lambda unit: batches.append(unit.begin_batch(request(authority))))
            observation = error.physical_observation
            assert observation.physical_status == "COMMITTED"
            assert observation.batch_observation == "MATCHING_COMMITTED"
            assert observation.original_batch is batches[0]
            assert observation.raw_status == "committed" and observation.status_received
            assert observation.integrity_problem is None
            assert observation.cleanup == "RETURNED"
            assert not hasattr(observation, "__dict__")
            with pytest.raises((FrozenInstanceError, AttributeError)):
                observation.physical_status = "UNKNOWN"
            with pytest.raises(AttributeError):
                error.physical_observation = None
            assert len(astuple(batches[0])) == 9
            assert harness.pool.peak == 1
            assert len(harness.pool.acquired) == 2
            assert [e[0] for e in harness.pool.events] == [
                "REQUEST", "ACQUIRE", "RETURN", "REQUEST", "ACQUIRE", "RETURN",
            ]
            assert len(harness.signing.client.calls) == 2
            commits = [q for _, name, q, _ in proxy.statements if name == "commit"]
            inserts = [q for _, _, q, _ in proxy.statements if b"INSERT INTO ofarm.governed_write_batch" in q]
            assert commits == [b"COMMIT"] and len(inserts) == 1
            assert [name for _, name, _, seen in proxy.statements if not seen] == [
                # Existing original execute(BEGIN) includes psycopg's implicit BEGIN.
                "probe", "begin", "begin", "challenge", "challenge_read", "bind", "context", "other", "commit",
            ]
            assert b"current_setting('synchronous_commit')" in inserts[0]
            assert b"current_setting('fsync')" in inserts[0]
            observer = [name for _, name, _, observed in proxy.statements if observed]
            assert observer == [
                "probe", "begin", "timeouts", "challenge", "challenge_read",
                "bind", "context", "status", "batch", "rollback",
            ]
            assert _stored(tenant_target, batches[0]) == 1


def test_ps03_real_idle_timeout_abort_is_delivered(harness, authority):
    batches = []
    def work(unit):
        batches.append(unit.begin_batch(request(authority)))
        raw = harness.pool.acquired[0]
        raw.execute("SET LOCAL idle_in_transaction_session_timeout = '150ms'")
        time.sleep(0.3)
    observation = _caught(harness, work).physical_observation
    assert observation.original_batch is batches[0]
    assert observation.physical_status == "ABORTED"
    assert observation.batch_observation == "ABSENT_AT_OBSERVATION"
    assert observation.raw_status == "aborted"
    assert len(harness.pool.acquired) == 2


def test_ps04_original_queued_commit_remains_unknown_then_finishes_separately(
    tenant_target, authority, capability_key, tmp_path, role,
):
    with PhysicalWireProxy(tenant_target.role_dsn(role), hold_commit=True) as proxy:
        with physical_harness(
            tenant_target, authority, capability_key, tmp_path, role, dsn=proxy.dsn,
        ) as harness:
            batches = []
            observation = _caught(
                harness, lambda unit: batches.append(unit.begin_batch(request(authority))),
            ).physical_observation
            assert observation.physical_status == "UNKNOWN"
            assert observation.raw_status == "in progress"
            assert observation.batch_observation == "ABSENT_AT_OBSERVATION"
            assert _stored(tenant_target, batches[0]) == 0
            proxy.release.set()
            assert proxy.eventual.wait(3)
            assert _stored(tenant_target, batches[0]) == 1
            assert observation.physical_status == "UNKNOWN"
            assert not callable(observation)
            assert len(harness.pool.acquired) == 2


@pytest.mark.parametrize("ambiguous", (False, True))
def test_ps01_dsn_off_keeps_ordinary_behavior_but_disables_recovery(
    tenant_target, authority, capability_key, tmp_path, role, monkeypatch, ambiguous,
):
    dsn = psycopg.conninfo.make_conninfo(
        tenant_target.role_dsn(role), options="-c synchronous_commit=off",
    )
    with physical_harness(tenant_target, authority, capability_key, tmp_path, role, dsn=dsn) as harness:
        with psycopg.connect(tenant_target.role_dsn(role)) as ordinary:
            assert ordinary.execute("SHOW synchronous_commit").fetchone() == ("on",)
            assert ordinary.execute("SHOW fsync").fetchone() == ("on",)
        commits = lose_commit_reply(monkeypatch, harness) if ambiguous else None
        batches, pids = [], []
        def work(unit):
            raw = harness.pool.acquired[0]
            pids.append(raw.info.backend_pid)
            assert raw.execute("SHOW synchronous_commit").fetchone() == ("off",)
            batches.append(unit.begin_batch(request(authority)))
            assert raw.info.backend_pid == pids[0]
            assert raw.execute("SHOW synchronous_commit").fetchone() == ("off",)
        if ambiguous:
            observation = _caught(harness, work).physical_observation
            assert observation.physical_status == "UNKNOWN"
            assert observation.batch_observation == "UNAVAILABLE"
            assert observation.original_batch is batches[0]
            assert observation.observer_failure == "RECOVERY_UNAVAILABLE"
            assert len(commits) == 1
        else:
            with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
                work(unit)
        assert _stored(tenant_target, batches[0]) == 1
        assert len(harness.pool.acquired) == 1


class _Rows:
    def __init__(self, rows):
        self.rows = rows
    def fetchone(self):
        return self.rows[0] if self.rows else None
    def fetchall(self):
        return self.rows


@pytest.mark.parametrize("eligibility", (None, "true", 1, "missing"))
def test_ps01_malformed_private_eligibility_does_not_reject_valid_batch(
    harness, authority, tenant_target, monkeypatch, eligibility,
):
    execute = psycopg.Connection.execute
    def damaged(connection, query, *args, **kwargs):
        cursor = execute(connection, query, *args, **kwargs)
        if "INSERT INTO ofarm.governed_write_batch" in str(query):
            row = cursor.fetchone()
            return _Rows([row[:9] if eligibility == "missing" else (*row[:9], eligibility)])
        return cursor
    monkeypatch.setattr(psycopg.Connection, "execute", damaged)
    lose_commit_reply(monkeypatch, harness)
    batches = []
    observation = _caught(harness, lambda unit: batches.append(unit.begin_batch(request(authority)))).physical_observation
    assert observation.physical_status == "UNKNOWN"
    assert observation.batch_observation == "UNAVAILABLE"
    assert observation.original_batch is batches[0]
    assert _stored(tenant_target, batches[0]) == 1
    assert len(harness.pool.acquired) == 1


@pytest.mark.parametrize("before_batch", (True, False))
def test_ps06_ps07_real_savepoints_preserve_physical_only_meaning(
    harness, authority, tenant_target, monkeypatch, before_batch,
):
    lose_commit_reply(monkeypatch, harness)
    batches = []
    later_record = f"physical-record-{uuid4().hex}"
    def work(unit):
        raw = harness.pool.acquired[0]
        if before_batch:
            raw.execute("SAVEPOINT physical_fixture")
        batches.append(unit.begin_batch(request(authority)))
        if not before_batch:
            raw.execute("SAVEPOINT physical_fixture")
            raw.execute(
                """INSERT INTO ofarm.kernel_record (
                    tenant_id, record_id, record_kind, lane, schema_digest, payload,
                    payload_digest, batch_id, runtime_bundle_digest
                ) SELECT tenant_id, %s, record_kind, lane, schema_digest, payload,
                         payload_digest, %s, runtime_bundle_digest
                  FROM ofarm.kernel_record WHERE record_id = %s AND tenant_id = %s""",
                (later_record, batches[0].batch_id, authority.party_ref, authority.tenant_id),
            )
        raw.execute("ROLLBACK TO SAVEPOINT physical_fixture")
    observation = _caught(harness, work).physical_observation
    assert observation.raw_status == "committed"
    assert observation.physical_status == ("UNKNOWN" if before_batch else "COMMITTED")
    assert observation.batch_observation == ("ABSENT_AT_OBSERVATION" if before_batch else "MATCHING_COMMITTED")
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert admin.execute("SELECT count(*) FROM ofarm.kernel_record WHERE record_id = %s", (later_record,)).fetchone() == (0,)
    assert _stored(tenant_target, batches[0]) == int(not before_batch)


@pytest.mark.parametrize("raw_status", (None, "in progress", "aborted"))
@pytest.mark.parametrize("absent", (False, True))
def test_ps05_ps12_labelled_status_seam_combines_separate_real_batch(
    harness, authority, monkeypatch, raw_status, absent,
):
    """Status is synthetic; batch visibility and runtime delivery are real."""
    execute = physical._BoundedTransaction.execute
    def altered(transaction, query, params=None):
        cursor = execute(transaction, query, params)
        if "pg_xact_status" in query:
            assert cursor.fetchall() == [("committed",)]
            return _Rows([(raw_status,)])
        return cursor
    monkeypatch.setattr(physical._BoundedTransaction, "execute", altered)
    lose_commit_reply(monkeypatch, harness)
    def work(unit):
        raw = harness.pool.acquired[0]
        if absent:
            raw.execute("SAVEPOINT physical_fixture")
        unit.begin_batch(request(authority))
        if absent:
            raw.execute("ROLLBACK TO SAVEPOINT physical_fixture")
    observation = _caught(harness, work).physical_observation
    assert observation.raw_status == raw_status and observation.status_received
    if raw_status == "aborted":
        assert observation.physical_status == ("ABORTED" if absent else "UNKNOWN")
        assert observation.integrity_problem == (None if absent else "STATUS_CONFLICT")
    else:
        assert observation.physical_status == ("UNKNOWN" if absent else "COMMITTED")


@pytest.mark.parametrize("field", range(9))
def test_ps12_every_tuple_field_participates_in_association(
    harness, authority, monkeypatch, field,
):
    """Explicit corrupt-row seam; this is not an actual xid-reuse control."""
    execute = physical._BoundedTransaction.execute
    def altered(transaction, query, params=None):
        cursor = execute(transaction, query, params)
        if "FROM ofarm.governed_write_batch" in query:
            rows = cursor.fetchall()
            assert len(rows) == 1
            row = list(rows[0])
            row[field] = (
                uuid4() if field == 0 else str(int(row[field]) + 1) if field == 2
                else row[field] + 1 if field == 7
                else row[field] + timedelta(microseconds=1) if field == 8
                else "different"
            )
            return _Rows([tuple(row)])
        return cursor
    monkeypatch.setattr(physical._BoundedTransaction, "execute", altered)
    lose_commit_reply(monkeypatch, harness)
    observation = _caught(harness, lambda unit: unit.begin_batch(request(authority))).physical_observation
    assert observation.physical_status == "UNKNOWN"
    assert observation.batch_observation == "CONFLICT"
    assert observation.integrity_problem == "BATCH_DIFFERS"
    assert len(observation.observed_batch) == 9
    expected = list(batch_tuple(observation.original_batch))
    expected[2] = str(expected[2])
    assert observation.observed_batch[field] != expected[field]


def test_ps17_f1_swallowed_sql_failure_refuses_normal_exit(
    harness, authority, tenant_target, monkeypatch,
):
    commits = lose_commit_reply(monkeypatch, harness)
    with pytest.raises(TenantBoundaryError) as caught:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            batch = unit.begin_batch(request(authority))
            # Explicit raw-SQL gate seam: production duplicate-INSERT paths
            # are covered separately by TF01 actual allocator controls.
            with pytest.raises(psycopg.errors.DivisionByZero):
                harness.pool.acquired[0].execute("SELECT 1/0")
    assert caught.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert caught.value.physical_observation is None and commits == []
    assert _stored(tenant_target, batch) == 0
    assert len(harness.pool.acquired) == 1 and harness.audit.reasons == []
    harness.pool.assert_released()


@pytest.mark.parametrize("ambiguous", (False, True))
def test_ps17_f2_post_insert_validation_failure_rolls_back_before_commit(
    harness, authority, tenant_target, monkeypatch, ambiguous,
):
    timestamp = tenant_uow._time
    def refuse(value, label):
        if label == "batch creation time":
            raise ValueError("fixture lost validated allocator return")
        return timestamp(value, label)
    monkeypatch.setattr(tenant_uow, "_time", refuse)
    commits = lose_commit_reply(monkeypatch, harness) if ambiguous else []
    authored = request(authority)
    with pytest.raises(TenantBoundaryError) as caught:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            with pytest.raises(ValueError, match="lost validated"):
                unit.begin_batch(authored)
            assert unit.batch is None
    assert caught.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert caught.value.physical_observation is None and commits == []
    assert _stored(tenant_target, authored) == 0
    assert len(harness.pool.acquired) == 1 and harness.audit.reasons == []
    harness.pool.assert_released()


def test_ps08_real_roles_cannot_forge_xid_mutate_batches_or_read_other_tenant(
    harness, authority,
):
    authored = request(authority)
    with harness.runtime.tenant_unit_of_work(harness.principal):
        raw = harness.pool.acquired[-1]
        row = raw.execute(
            """INSERT INTO ofarm.governed_write_batch (
                tenant_id, batch_id, full_xid, authenticated_principal_ref,
                governed_operation, request_id, runtime_bundle_digest
            ) VALUES (%s, %s, '1'::xid8, %s, %s, %s, %s)
            RETURNING full_xid::text, pg_current_xact_id()::text""",
            (authority.tenant_id, authored.batch_id, authority.party_ref,
             authored.operation, authored.request_id, authored.runtime_bundle_digest),
        ).fetchone()
        assert row[0] == row[1] and row[0] != "1"
        assert raw.execute("SELECT pg_xact_status(%s::xid8)", (row[0],)).fetchone() == ("in progress",)
        assert raw.execute("SELECT pg_has_role(current_user, 'pg_read_all_stats', 'MEMBER')").fetchone() == (False,)
        assert raw.execute(
            "SELECT count(*) FROM ofarm.governed_write_batch WHERE tenant_id = %s",
            (authority.other_tenant_id,),
        ).fetchone() == (0,)
    for sql in (
        "UPDATE ofarm.governed_write_batch SET request_id = request_id",
        "DELETE FROM ofarm.governed_write_batch",
        "TRUNCATE ofarm.governed_write_batch",
    ):
        with pytest.raises(psycopg.Error):
            with harness.runtime.tenant_unit_of_work(harness.principal):
                harness.pool.acquired[-1].execute(sql)
    harness.pool.assert_released()


def test_ps09_actual_principal_revocation_refuses_fresh_observer_without_audit(
    tenant_target, authority, capability_key, tmp_path, role, monkeypatch,
):
    from kernel.tests._physical_outcome_support import activate_subject, revoke_subject

    unique = activate_subject(tenant_target, authority)
    with physical_harness(tenant_target, unique, capability_key, tmp_path, role) as harness:
        challenges = []
        mint = harness.signing.issuer.mint
        def record(identity, principal, challenge, **kwargs):
            challenges.append(challenge.challenge_id)
            return mint(identity, principal, challenge, **kwargs)
        monkeypatch.setattr(harness.signing.issuer, "mint", record)
        lose_commit_reply(monkeypatch, harness, after=lambda _: revoke_subject(tenant_target, unique))
        batches = []
        observation = _caught(harness, lambda unit: batches.append(unit.begin_batch(request(unique)))).physical_observation
        assert observation.physical_status == "UNKNOWN"
        assert observation.batch_observation == "UNAVAILABLE"
        assert observation.observer_failure == "BINDING_REFUSED"
        assert observation.original_batch is batches[0]
        assert len(challenges) == 2 and challenges[0] != challenges[1]
        assert len(harness.signing.client.calls) == 2
        assert _stored(tenant_target, batches[0]) == 1
        assert len(harness.pool.acquired) == 2


def test_ps10_ps14_body_authored_finalization_error_cannot_request_observation(
    harness, authority, tenant_target,
):
    authored = TenantBoundaryError(TenantBoundaryOutcome.FINALIZATION_UNKNOWN)
    with pytest.raises(TenantBoundaryError) as raised:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            batch = unit.begin_batch(request(authority))
            raise authored
    assert raised.value is authored
    assert authored.physical_observation is None
    assert len(harness.pool.acquired) == 1
    assert _stored(tenant_target, batch) == 0
    harness.pool.assert_released()
    assert harness.audit.reasons == []


@pytest.mark.parametrize("rows", ([], [()], [("aborted", "extra")], [(1,)], [("ABORTED",)], [("aborted",), ("aborted",)]))
def test_ps05_corrupt_status_shape_never_supplies_abort_proof(
    harness, authority, monkeypatch, rows,
):
    """Explicit corrupt status seam after an actual PostgreSQL status query."""
    execute = physical._BoundedTransaction.execute
    def altered(transaction, query, params=None):
        cursor = execute(transaction, query, params)
        if "pg_xact_status" in query:
            assert cursor.fetchall() == [("committed",)]
            return _Rows(rows)
        return cursor
    monkeypatch.setattr(physical._BoundedTransaction, "execute", altered)
    lose_commit_reply(monkeypatch, harness)
    observation = _caught(harness, lambda unit: unit.begin_batch(request(authority))).physical_observation
    assert observation.physical_status == "UNKNOWN"
    assert observation.batch_observation == "UNAVAILABLE"
    assert observation.observer_failure == "STATUS_UNAVAILABLE"
    assert not observation.status_received and observation.raw_status is None
    assert observation.cleanup == "DISCARDED"


def test_ps01_ps13_configure_on_cannot_rescue_actual_original_backend_off(
    tenant_target, authority, capability_key, tmp_path, role, monkeypatch,
):
    configured = []
    def configure(connection):
        connection.autocommit = True
        configured.append((connection.info.backend_pid, connection.execute("SHOW synchronous_commit").fetchone()[0]))
        connection.execute("SET SESSION synchronous_commit = on")
        connection.autocommit = False
    with physical_harness(
        tenant_target, authority, capability_key, tmp_path, role, configure=configure,
    ) as harness:
        lose_commit_reply(monkeypatch, harness)
        batches, original = [], []
        def work(unit):
            connection = harness.pool.acquired[0]
            original.append(connection.info.backend_pid)
            assert (original[0], "on") in configured
            connection.execute("SET LOCAL synchronous_commit = off")
            batches.append(unit.begin_batch(request(authority)))
            assert connection.execute("SHOW synchronous_commit").fetchone() == ("off",)
            assert connection.info.backend_pid == original[0]
        observation = _caught(harness, work).physical_observation
        assert observation.physical_status == "UNKNOWN"
        assert observation.observer_failure == "RECOVERY_UNAVAILABLE"
        assert observation.batch_observation == "UNAVAILABLE"
        assert observation.original_batch is batches[0]
        assert len(harness.pool.acquired) == 1
        assert _stored(tenant_target, batches[0]) == 1
