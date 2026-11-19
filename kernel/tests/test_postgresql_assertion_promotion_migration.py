"""Version 11 history, full-visibility checks and concurrent promotion cutover."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from threading import Event
from time import monotonic
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from deployment.postgresql import migration_runner
from deployment.postgresql.migration_runner import MigrationExecutionError
from deployment.postgresql.migration_sets import require_authoritative_migration_set
from deployment.postgresql.provisioning_specs import TENANT_PROVISIONING_SPEC
from kernel.tests.postgresql_tenant_support import TenantTarget, fresh_tenant_service
from kernel.tests.test_postgresql_assertion_promotion import (
    ASSERTION,
    TRACE,
    _edge,
    _pending,
    _record,
)
from kernel.tests.test_postgresql_tenant_migration import (
    _admin_dsn,
    _insert_batch,
    _install_test_bound_context,
    authority as authority,
)


_TRIGGER = "kernel_record_require_assertion_v02_promotion"
_HISTORY_ERROR = "v0.2 promotion history contains incomplete proof"
_VISIBILITY_ERROR = "v0.2 promotion history visibility is incomplete"


def _upgrade(target):
    return migration_runner.migrate_service(
        admin_dsn=target.admin_dsn,
        migrator_dsn=target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=target.migration_set,
        release_identity="ofarm-tests/assertion-promotion",
        execution_id=uuid4(),
    )


@pytest.fixture(scope="module")
def tenant_target(history_case):
    """Each parametrized history gets its own disposable, committed v11 ledger."""

    class StopAfterVersion11(Exception):
        pass

    commit = migration_runner._commit

    def commit_through_11(connection, migration, execution_id):
        commit(connection, migration, execution_id)
        if migration.version == 11:
            raise StopAfterVersion11

    with fresh_tenant_service(_admin_dsn()) as target:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(migration_runner, "_commit", commit_through_11)
            with pytest.raises(StopAfterVersion11):
                _upgrade(target)
        state = _snapshot(target)
        assert [row["version"] for row in state.history] == list(range(1, 12))
        assert state.security == [
            ("kernel_edge", True, True),
            ("kernel_record", True, True),
        ]
        assert not state.trigger
        yield target


@dataclass(frozen=True)
class Snapshot:
    history: list
    security: list
    trigger: bool
    original_protections: tuple
    batches: list
    records: list
    edges: list


def _snapshot(target: TenantTarget) -> Snapshot:
    """All columns, including original stamps and payloads, in one independent snapshot."""
    with psycopg.connect(target.target_admin_dsn) as observer:
        observer.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")

        def rows(table, order):
            return [
                row[0]
                for row in observer.execute(
                    sql.SQL("SELECT to_jsonb(r) FROM ofarm.{} AS r ORDER BY {}").format(
                        sql.Identifier(table),
                        sql.SQL(", ").join(map(sql.Identifier, order)),
                    )
                )
            ]

        security = observer.execute("""
            SELECT relname::text, relrowsecurity, relforcerowsecurity
            FROM pg_catalog.pg_class
            WHERE oid IN ('ofarm.kernel_record'::regclass, 'ofarm.kernel_edge'::regclass)
            ORDER BY relname
        """).fetchall()
        trigger = observer.execute(
            """
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_trigger
                WHERE tgrelid = 'ofarm.kernel_record'::regclass AND tgname = %s)
        """,
            (_TRIGGER,),
        ).fetchone()[0]
        # Keep the sealed v11 trigger bodies, their attachments, ownership and
        # ACLs, plus effective ordinary-role access to the two ledger tables.
        sealed = observer.execute("""
            SELECT t.tgname, pg_get_triggerdef(t.oid), pg_get_functiondef(p.oid),
                   pg_get_userbyid(p.proowner), p.proacl::text
            FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid
            WHERE (tgrelid = 'ofarm.kernel_record'::regclass AND tgname = 'kernel_record_require_promotion')
               OR (tgrelid = 'ofarm.kernel_edge'::regclass AND tgname = 'kernel_edge_validate_promotion')
            ORDER BY tgname
        """).fetchall()
        assert len(sealed) == 2 and all(
            row[3] == "ofarm_graph_validator" for row in sealed
        )
        table_access = observer.execute("""
            SELECT c.relname, c.relacl::text, role.rolname, privilege,
                   has_table_privilege(role.oid, c.oid, privilege)
            FROM pg_class c CROSS JOIN pg_roles role
            CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) privilege
            WHERE c.oid IN ('ofarm.kernel_record'::regclass, 'ofarm.kernel_edge'::regclass)
              AND role.rolname IN ('ofarm_app','ofarm_worker')
            ORDER BY c.relname, role.rolname, privilege
        """).fetchall()
        return Snapshot(
            rows("schema_migration", ("version",)),
            security,
            trigger,
            (sealed, table_access),
            rows("governed_write_batch", ("tenant_id", "batch_id")),
            rows("kernel_record", ("tenant_id", "record_id")),
            rows("kernel_edge", ("tenant_id", "edge_id")),
        )


def _assertion(conn, tenant, batch):
    assertion_id = batch + "-assertion"
    _record(conn, tenant, batch, assertion_id, ASSERTION, _pending(assertion_id))


def _trace(conn, tenant, batch, refs):
    _record(
        conn,
        tenant,
        batch,
        batch + "-trace",
        TRACE,
        {"emittedAssertionRecordRefs": refs},
    )


def _seed_first_tenant(target, tenant):
    batch = "source-alpha"
    with psycopg.connect(target.role_dsn("ofarm_app")) as writer:
        _install_test_bound_context(writer, tenant)
        _insert_batch(writer, tenant, batch)
        _assertion(writer, tenant, batch)
        _trace(writer, tenant, batch, [batch + "-assertion"])
        _edge(writer, tenant, batch, batch + "-trace", batch + "-assertion")


def _stage_second_tenant_history(admin, tenant, shape):
    """Load a fictional legacy snapshot at the unused tenant's fixture-only genesis."""
    batch = "source-beta"
    second = replace(
        tenant,
        tenant_id=tenant.other_tenant_id,
        tenant_registration_digest=tenant.other_tenant_registration_digest,
        party_ref="fixture-bootstrap",
    )
    # Even on the privileged loader backend the sealed edge validator is
    # tenant-bound. Give it the existing fixture's transaction-specific context.
    _install_test_bound_context(admin, second)
    admin.execute(
        """
        SELECT ofarm.publish_runtime_bundle(%s, bundle_digest, convert_from(canonical_bytes,'UTF8')::jsonb)
        FROM ofarm.runtime_bundle WHERE tenant_id=%s AND bundle_digest=%s
    """,
        (second.tenant_id, tenant.tenant_id, tenant.runtime_bundle_digest),
    )
    admin.execute(
        """
        INSERT INTO ofarm.governed_write_batch (tenant_id, batch_id, authenticated_principal_ref,
            governed_operation, request_id, runtime_bundle_digest, knowledge_position)
        VALUES (%s, %s, 'fixture-bootstrap', 'AUTHORITY_BOOTSTRAP', 'fixture-import', %s, 1)
    """,
        (second.tenant_id, batch, second.runtime_bundle_digest),
    )
    _assertion(admin, second, batch)
    if shape == "orphan":
        return
    assertion_id = batch + "-assertion"
    refs = {assertion_id: True} if shape == "object" else [assertion_id]
    _trace(admin, second, batch, refs)
    _edge(admin, second, batch, batch + "-trace", assertion_id)


def _seed_history(target, tenant, shape):
    _seed_first_tenant(target, tenant)
    with psycopg.connect(target.target_admin_dsn) as admin:
        _stage_second_tenant_history(admin, tenant, shape)
    before = _snapshot(target)
    claims = [r for r in before.records if r["record_kind"] == ASSERTION]
    assert {r["tenant_id"] for r in claims} == {
        str(tenant.tenant_id),
        str(tenant.other_tenant_id),
    }
    assert len(claims) == 2
    assert len(before.edges) == (1 if shape == "orphan" else 2)
    return before


def _assert_run_error(error, target, state, primary):
    assert (
        error.version == 12
        and error.filename == target.migration_set.migrations[11].filename
    )
    assert isinstance(error.__cause__, psycopg.Error)
    assert error.__cause__.sqlstate == state
    assert error.__cause__.diag.message_primary == primary
    if primary == _HISTORY_ERROR:
        assert (
            error.__cause__.diag.message_detail == "assessed 2, matched 1, exceptions 1"
        )


def _assert_upgrade_and_noop(target, before):
    upgraded = _upgrade(target)
    assert (
        upgraded.previous_version,
        upgraded.applied_versions,
        upgraded.final_version,
    ) == (11, (12,), 12)
    after = _snapshot(target)
    assert after.trigger
    with psycopg.connect(target.target_admin_dsn) as observer:
        assert observer.execute("""
            SELECT NOT p.prosecdef, pg_get_userbyid(p.proowner),
                   NOT has_function_privilege('ofarm_app', p.oid, 'EXECUTE'),
                   NOT has_function_privilege('ofarm_worker', p.oid, 'EXECUTE'),
                   NOT EXISTS (SELECT 1 FROM aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
                               WHERE a.grantee = 0 AND a.privilege_type = 'EXECUTE')
            FROM pg_proc p WHERE p.oid = 'ofarm.require_assertion_v02_promotion()'::regprocedure
        """).fetchone() == (True, "ofarm_owner", True, True, True)
    assert after.history[-1]["version"] == 12
    assert after.history[-1]["applied_prefix_digest"] == target.migration_set.digest
    assert replace(after, history=after.history[:-1], trigger=False) == before
    replay = _upgrade(target)
    assert replay.verified_noop and replay.applied_versions == ()
    assert replay.previous_version == replay.final_version == 12
    assert replay.observed_head_execution_id == upgraded.execution_id
    assert _snapshot(target) == after


@pytest.mark.parametrize("history_case", ("valid",), scope="module")
def test_two_tenant_history_visibility_rollback_upgrade_and_noop(
    tenant_target, authority
):
    target = tenant_target
    before = _seed_history(target, authority, "valid")
    require_authoritative_migration_set(target.migration_set)
    source = target.migration_set.migrations[11].source_bytes
    start = b"<<verify_history_visibility>>"
    end = b"END verify_history_visibility;"
    assert source.count(start) == source.count(end) == 1
    block = source[source.index(start) : source.index(end) + len(end)]
    assert block.startswith(start) and block.endswith(end)
    for records_visible, edges_visible in ((True, True), (False, True), (True, False)):
        with psycopg.connect(target.migrator_dsn) as conn:
            conn.execute("SET LOCAL ROLE ofarm_owner")
            assert conn.execute("SELECT current_user").fetchone() == ("ofarm_owner",)
            conn.execute(
                "LOCK TABLE ofarm.kernel_record, ofarm.kernel_edge IN ACCESS EXCLUSIVE MODE"
            )
            if records_visible:
                conn.execute(
                    "ALTER TABLE ofarm.kernel_record NO FORCE ROW LEVEL SECURITY"
                )
            if edges_visible:
                conn.execute(
                    "ALTER TABLE ofarm.kernel_edge NO FORCE ROW LEVEL SECURITY"
                )
            assert conn.execute("""
                SELECT count(*) FROM ofarm.kernel_record WHERE record_id IN
                    ('source-alpha-assertion', 'source-beta-assertion')
            """).fetchone() == (2 if records_visible else 0,)
            assert conn.execute("""
                SELECT count(*) FROM ofarm.kernel_edge WHERE dst_record_id IN
                    ('source-alpha-assertion', 'source-beta-assertion')
            """).fetchone() == (2 if edges_visible else 0,)
            assert conn.execute("""
                SELECT row_security_active('ofarm.kernel_record'), row_security_active('ofarm.kernel_edge')
            """).fetchone() == (not records_visible, not edges_visible)
            statement = b"DO $test$\n" + block + b"\n$test$"
            if records_visible and edges_visible:
                conn.execute(statement)
            else:
                with pytest.raises(
                    psycopg.errors.ObjectNotInPrerequisiteState
                ) as refused:
                    conn.execute(statement)
                assert refused.value.sqlstate == "55000"
                assert refused.value.diag.message_primary == _VISIBILITY_ERROR
            conn.rollback()
        assert _snapshot(target) == before
    _assert_upgrade_and_noop(target, before)


@pytest.mark.parametrize("history_case", ("catalog-drift",), scope="module")
def test_runner_refuses_altered_v11_without_changing_its_starting_state(
    tenant_target, authority
):
    target = tenant_target
    original = _seed_history(target, authority, "valid")
    with psycopg.connect(target.target_admin_dsn) as admin:
        admin.execute("ALTER TABLE ofarm.kernel_record NO FORCE ROW LEVEL SECURITY")
    altered = _snapshot(target)
    assert altered == replace(
        original, security=[("kernel_edge", True, True), ("kernel_record", True, False)]
    )
    with pytest.raises(MigrationExecutionError) as refused:
        _upgrade(target)
    _assert_run_error(
        refused.value, target, "55000", "version-11 tenant structure differs"
    )
    assert _snapshot(target) == altered


@pytest.mark.parametrize("history_case", ("orphan", "object"), scope="module")
def test_runner_preserves_incompatible_history_in_another_tenant(
    tenant_target, authority, history_case
):
    before = _seed_history(tenant_target, authority, history_case)
    with pytest.raises(MigrationExecutionError) as refused:
        _upgrade(tenant_target)
    _assert_run_error(refused.value, tenant_target, "55000", _HISTORY_ERROR)
    assert _snapshot(tenant_target) == before


def _wait_for_relation_block(target, writer_pid, relation, *, migration_waits):
    deadline = monotonic() + 10
    with psycopg.connect(target.target_admin_dsn, autocommit=True) as observer:
        while monotonic() < deadline:
            observed = observer.execute(
                """
                SELECT w.pid, pg_catalog.pg_blocking_pids(w.pid), a.usename
                FROM pg_catalog.pg_locks w
                JOIN pg_catalog.pg_stat_activity a ON a.pid = w.pid
                WHERE w.relation = %s::regclass AND w.mode = %s AND NOT w.granted
            """,
                (
                    relation,
                    "AccessExclusiveLock" if migration_waits else "RowExclusiveLock",
                ),
            ).fetchall()
            for waiting_pid, blockers, login in observed:
                if (
                    migration_waits
                    and login == "ofarm_migrator"
                    and writer_pid in blockers
                ):
                    return
                if not migration_waits and waiting_pid == writer_pid and blockers:
                    return
            Event().wait(0.01)
    pytest.fail(f"did not observe the expected cutover wait on {relation}")


@pytest.mark.parametrize("history_case", ("concurrent-history",), scope="module")
def test_record_first_fixture_history_committed_during_cutover_is_inspected(
    tenant_target, authority
):
    """The writer imports fictional legacy data at genesis using the fixture administrator."""
    target = tenant_target
    _seed_first_tenant(target, authority)
    with (
        ThreadPoolExecutor(1) as pool,
        psycopg.connect(target.target_admin_dsn) as importer,
    ):
        _stage_second_tenant_history(importer, authority, "orphan")
        # Capture the actual new rows, including generated fields and the original full xid.
        imported = {}
        for table in ("governed_write_batch", "kernel_record"):
            imported[table] = importer.execute(
                sql.SQL(
                    "SELECT to_jsonb(r) FROM ofarm.{} AS r WHERE batch_id = 'source-beta'"
                ).format(sql.Identifier(table))
            ).fetchone()[0]
        before = _snapshot(target)
        future = pool.submit(_upgrade, target)
        try:
            _wait_for_relation_block(
                target,
                importer.info.backend_pid,
                "ofarm.kernel_record",
                migration_waits=True,
            )
            importer.commit()
        finally:
            importer.rollback()
        with pytest.raises(MigrationExecutionError) as refused:
            future.result(timeout=20)
        _assert_run_error(refused.value, target, "55000", _HISTORY_ERROR)
    after = _snapshot(target)
    assert [r for r in after.batches if r["batch_id"] == "source-beta"] == [
        imported["governed_write_batch"]
    ]
    assert [r for r in after.records if r["batch_id"] == "source-beta"] == [
        imported["kernel_record"]
    ]
    assert (
        replace(
            after,
            batches=[r for r in after.batches if r["batch_id"] != "source-beta"],
            records=[r for r in after.records if r["batch_id"] != "source-beta"],
        )
        == before
    )
    with pytest.raises(MigrationExecutionError) as replay:
        _upgrade(target)
    _assert_run_error(replay.value, target, "55000", _HISTORY_ERROR)
    assert _snapshot(target) == after


@pytest.mark.parametrize("history_case", ("edge-first",), scope="module")
def test_edge_first_writer_and_upgrade_preserve_the_graph(tenant_target, authority):
    target = tenant_target
    before = _seed_history(target, authority, "valid")
    batch = "edge-first"
    with (
        ThreadPoolExecutor(1) as pool,
        psycopg.connect(target.role_dsn("ofarm_app")) as writer,
    ):
        # A live signed challenge reads the Party record before this write. Use the
        # existing storage fixture binding to isolate the supported edge-first ordering.
        _install_test_bound_context(writer, authority)
        _insert_batch(writer, authority, batch)
        _edge(writer, authority, batch, batch + "-trace", batch + "-assertion")
        future = pool.submit(_upgrade, target)
        try:
            _wait_for_relation_block(
                target,
                writer.info.backend_pid,
                "ofarm.kernel_edge",
                migration_waits=True,
            )
            try:
                _assertion(writer, authority, batch)
                _trace(writer, authority, batch, [batch + "-assertion"])
                writer.commit()
                committed = True
            except (psycopg.errors.DeadlockDetected, psycopg.errors.LockNotAvailable):
                writer.rollback()
                committed = False
        finally:
            writer.rollback()
        try:
            result = future.result(timeout=20)
            assert result.applied_versions == (12,)
            upgraded = True
        except MigrationExecutionError as exc:
            assert exc.version == 12
            assert isinstance(
                exc.__cause__,
                (psycopg.errors.DeadlockDetected, psycopg.errors.LockNotAvailable),
            )
            upgraded = False

    after = _snapshot(target)
    assert after.trigger is upgraded
    assert len(after.history) == (12 if upgraded else 11)
    assert after.history[:11] == before.history
    assert after.security == before.security
    assert after.original_protections == before.original_protections
    additions = []
    for current, prior in (
        (after.batches, before.batches),
        (after.records, before.records),
        (after.edges, before.edges),
    ):
        assert [r for r in current if r["batch_id"] != batch] == prior
        additions.append([r for r in current if r["batch_id"] == batch])
    assert list(map(len, additions)) == ([1, 2, 1] if committed else [0, 0, 0])
    if committed:
        batches, records, edges = additions
        assert {r["record_kind"] for r in records} == {ASSERTION, TRACE}
        assert edges[0]["src_record_id"] == batch + "-trace"
        assert edges[0]["dst_record_id"] == batch + "-assertion"
        assert {r["batch_full_xid"] for r in records + edges} == {
            batches[0]["full_xid"]
        }
    if upgraded:
        assert _upgrade(target).verified_noop
        assert _snapshot(target) == after
    else:
        _assert_upgrade_and_noop(target, after)


@pytest.mark.parametrize("history_case", ("new-writer",), scope="module")
def test_writer_waiting_behind_cutover_obeys_new_proof_check(
    tenant_target, authority, monkeypatch
):
    target = tenant_target
    before = _seed_history(target, authority, "valid")
    before_append, allow_commit = Event(), Event()
    insert_row = migration_runner._insert_ledger_row

    def pause_before_append(
        connection, spec, current_set, migration, release_identity, execution_id
    ):
        assert migration.version == 12
        before_append.set()
        assert allow_commit.wait(15)
        insert_row(
            connection, spec, current_set, migration, release_identity, execution_id
        )

    batch = "save-after-cutover"
    with (
        ThreadPoolExecutor(2) as pool,
        psycopg.connect(target.role_dsn("ofarm_worker")) as writer,
    ):
        _install_test_bound_context(writer, authority)
        _insert_batch(writer, authority, batch)

        def save():
            _assertion(writer, authority, batch)
            with pytest.raises(psycopg.errors.CheckViolation) as refused:
                writer.commit()
            assert refused.value.sqlstate == "23514"
            assert (
                refused.value.diag.message_primary
                == "v0.2 assertion lacks matching promotion proof"
            )

        with monkeypatch.context() as patch:
            patch.setattr(migration_runner, "_insert_ledger_row", pause_before_append)
            upgrading = pool.submit(_upgrade, target)
            try:
                assert before_append.wait(15)
                saving = pool.submit(save)
                _wait_for_relation_block(
                    target,
                    writer.info.backend_pid,
                    "ofarm.kernel_record",
                    migration_waits=False,
                )
            finally:
                allow_commit.set()
            assert upgrading.result(timeout=20).applied_versions == (12,)
            saving.result(timeout=10)

    after = _snapshot(target)
    assert after.trigger and len(after.history) == 12
    assert replace(after, history=after.history[:11], trigger=False) == before
    assert _upgrade(target).verified_noop
    assert _snapshot(target) == after
