"""Hostile startup regressions for the exact PostgreSQL schema guard."""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from pathlib import Path

import psycopg
import psycopg.conninfo
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from kernel import config, context, schema_guard
from kernel.schema_guard import (
    SchemaGuardError,
    SchemaState,
    ensure_schema,
    verify_static_runtime_catalog,
)
from kernel.store import Store
from kernel.tests.conftest import _admin_dsn


class _CatalogLockCursor:
    def __init__(self, failures: int):
        self.connection = type("Connection", (), {
            "info": type("Info", (), {
                "transaction_status": psycopg.pq.TransactionStatus.INTRANS,
            })(),
        })()
        self.failures = failures
        self.lock_attempts = 0
        self.queries = []
        self._row = None

    def execute(self, query, params=None):
        self.queries.append((query, params))
        if query.startswith("SELECT pg_catalog.pg_my_temp_schema"):
            self._row = {"temp_schema_oid": 0}
        elif query.startswith("LOCK TABLE"):
            self.lock_attempts += 1
            if self.lock_attempts <= self.failures:
                raise psycopg.errors.LockNotAvailable("catalog is busy")
        return self

    def fetchone(self):
        return self._row


def test_catalog_lock_contention_releases_partial_locks_before_retry(monkeypatch):
    cursor = _CatalogLockCursor(failures=1)
    delays = []
    monkeypatch.setattr(schema_guard.time, "sleep", delays.append)

    schema_guard.hold_fingerprint_catalog_locks(cursor)

    statements = [query for query, _params in cursor.queries]
    assert cursor.lock_attempts == 2
    assert delays == [schema_guard._CATALOG_LOCK_RETRY_DELAY_SECONDS]
    assert all(statement.endswith("NOWAIT") for statement in statements
               if statement.startswith("LOCK TABLE"))
    assert statements.count(
        f"ROLLBACK TO SAVEPOINT {schema_guard._CATALOG_LOCK_SAVEPOINT}") == 1
    assert statements.count(
        f"RELEASE SAVEPOINT {schema_guard._CATALOG_LOCK_SAVEPOINT}") == 2


def test_catalog_lock_contention_remains_fail_closed(monkeypatch):
    cursor = _CatalogLockCursor(failures=2)
    monkeypatch.setattr(schema_guard, "_CATALOG_LOCK_ATTEMPTS", 2)
    monkeypatch.setattr(schema_guard.time, "sleep", lambda _delay: None)

    with pytest.raises(SchemaGuardError, match="catalogs remained busy"):
        schema_guard.hold_fingerprint_catalog_locks(cursor)
    assert cursor.lock_attempts == 2


@contextmanager
def _isolated_database(label: str):
    dbname = f"ofarm_{label}_{uuid.uuid4().hex[:10]}"
    admin_dsn = _admin_dsn()
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{dbname}"')
    params = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    params["dbname"] = dbname
    dsn = psycopg.conninfo.make_conninfo(**params)
    try:
        yield dsn
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (dbname,),
            )
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


@pytest.mark.parametrize("mutated_input", ["lock", "schema"])
def test_prestart_static_mismatch_never_opens_or_touches_database(
        monkeypatch, mutated_input):
    """A stale lock or schema fails before psycopg.connect can be called."""
    target = (
        config.PACKAGE_ROOT / "kernel" /
        ("runtime_bundle.lock.json" if mutated_input == "lock" else "schema.sql")
    ).resolve()
    original_read_bytes = Path.read_bytes

    def hostile_read_bytes(path):
        raw = original_read_bytes(path)
        if Path(path).resolve() == target:
            return raw + b"\n-- hostile prestart mutation\n"
        return raw

    connection_attempts = []

    def forbidden_connect(*args, **kwargs):
        connection_attempts.append((args, kwargs))
        raise AssertionError("database connection attempted before static verification")

    monkeypatch.setattr(Path, "read_bytes", hostile_read_bytes)
    monkeypatch.setattr(psycopg, "connect", forbidden_connect)
    with pytest.raises(SchemaGuardError, match="before database startup"):
        Store(dsn="dbname=must_not_be_opened")
    assert connection_attempts == []


def test_empty_install_is_atomic_and_exact_restart_executes_no_schema_ddl():
    with _isolated_database("schema_exact_restart") as dsn:
        store = Store(dsn=dsn)
        restarted = None
        try:
            store.migrate()
            with Store._raw_connection(store).cursor() as cur:
                cur.execute(
                    "SELECT ledger_key, schema_digest, catalog_fingerprint, "
                    "catalog_bytes, byte_length, installed_at, xmin::text AS xmin "
                    "FROM runtime_schema_ledger"
                )
                ledger_before = cur.fetchone()
                cur.execute(
                    "SELECT p.xmin::text AS xmin FROM pg_proc p "
                    "JOIN pg_namespace n ON n.oid = p.pronamespace "
                    "WHERE n.nspname = 'public' "
                    "AND p.proname = 'kernel_forbid_mutation'"
                )
                function_xmin_before = cur.fetchone()["xmin"]
                cur.execute(
                    "SELECT xmin::text AS xmin FROM pg_trigger "
                    "WHERE tgname = 'trg_runtime_schema_ledger_append_only'"
                )
                trigger_xmin_before = cur.fetchone()["xmin"]
            assert ledger_before["ledger_key"] == "ofarm-kernel-schema"
            assert ledger_before["schema_digest"].startswith("sha256:")
            assert ledger_before["catalog_fingerprint"].startswith("sha256:")
            assert ledger_before["byte_length"] == len(ledger_before["catalog_bytes"])

            restarted = Store(dsn=dsn)
            restarted.migrate()
            with Store._raw_connection(restarted).cursor() as cur:
                cur.execute(
                    "SELECT ledger_key, schema_digest, catalog_fingerprint, "
                    "catalog_bytes, byte_length, installed_at, xmin::text AS xmin "
                    "FROM runtime_schema_ledger"
                )
                assert cur.fetchone() == ledger_before
                cur.execute(
                    "SELECT p.xmin::text AS xmin FROM pg_proc p "
                    "JOIN pg_namespace n ON n.oid = p.pronamespace "
                    "WHERE n.nspname = 'public' "
                    "AND p.proname = 'kernel_forbid_mutation'"
                )
                assert cur.fetchone()["xmin"] == function_xmin_before
                cur.execute(
                    "SELECT xmin::text AS xmin FROM pg_trigger "
                    "WHERE tgname = 'trg_runtime_schema_ledger_append_only'"
                )
                assert cur.fetchone()["xmin"] == trigger_xmin_before
        finally:
            if restarted is not None:
                restarted.close()
            store.close()


def test_every_append_only_relation_refuses_truncate():
    """TRUNCATE must not bypass the statement-level append-only guard."""
    protected_relations = (
        "runtime_schema_ledger",
        "runtime_content_blob",
        "runtime_tenant_content_blob",
        "runtime_bundle",
        "runtime_bundle_component",
        "kernel_record",
        "kernel_edge",
        "kernel_gate_log",
        "kernel_idempotency",
        "runtime_trace",
        "export_artifact",
    )
    with _isolated_database("schema_truncate_guard") as dsn:
        store = Store(dsn=dsn)
        try:
            store.migrate()
            trigger_rows = Store._raw_connection(store).execute(
                "SELECT rel.relname AS relation, "
                "pg_catalog.pg_get_triggerdef(trg.oid, true) AS definition "
                "FROM pg_catalog.pg_trigger trg "
                "JOIN pg_catalog.pg_class rel ON rel.oid = trg.tgrelid "
                "JOIN pg_catalog.pg_namespace ns ON ns.oid = rel.relnamespace "
                "JOIN pg_catalog.pg_proc fn ON fn.oid = trg.tgfoid "
                "JOIN pg_catalog.pg_namespace fn_ns "
                "ON fn_ns.oid = fn.pronamespace "
                "WHERE ns.nspname = 'public' "
                "AND fn_ns.nspname = 'public' "
                "AND fn.proname = 'kernel_forbid_mutation'"
            ).fetchall()
            definitions = {
                row["relation"]: row["definition"] for row in trigger_rows
            }
            assert len(trigger_rows) == len(protected_relations)
            assert set(definitions) == set(protected_relations)
            assert all(
                "TRUNCATE" in definition
                and "FOR EACH STATEMENT" in definition
                for definition in definitions.values()
            )
            for relation in protected_relations:
                with pytest.raises(
                        psycopg.errors.RaiseException,
                        match="TRUNCATE.*forbidden"):
                    Store._raw_connection(store).execute(
                        sql.SQL("TRUNCATE TABLE {} CASCADE").format(
                            sql.Identifier("public", relation)))
            assert Store._raw_connection(store).execute(
                "SELECT count(*) AS n FROM public.runtime_schema_ledger"
            ).fetchone()["n"] == 1
        finally:
            store.close()


def test_temporary_schema_refuses_before_any_schema_ddl():
    """pg_temp is implicitly searched even when search_path omits it."""
    with _isolated_database("schema_temp_shadow") as dsn:
        store = Store(dsn=dsn)
        try:
            Store._raw_connection(store).execute(
                "CREATE TEMP TABLE export_artifact (value text)")
            with pytest.raises(SchemaGuardError, match="temporary schema"):
                store.migrate()
            assert Store._raw_connection(store).execute(
                "SELECT pg_catalog.to_regclass("
                "'public.runtime_schema_ledger') AS relation"
            ).fetchone()["relation"] is None
        finally:
            store.close()


def test_empty_install_excludes_noncooperating_concurrent_ddl(monkeypatch):
    with _isolated_database("schema_concurrent_ddl") as dsn:
        store = Store(dsn=dsn)
        original_classify = schema_guard.classify_schema
        classifications = []

        def classify_with_hostile_ddl(cur, verified):
            result = original_classify(cur, verified)
            classifications.append(result.state)
            if result.state is SchemaState.EMPTY and len(classifications) == 2:
                with psycopg.connect(dsn, autocommit=True) as competing:
                    competing.execute(
                        "SELECT pg_catalog.set_config("
                        "'lock_timeout', '250ms', false)"
                    )
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        competing.execute(
                            "CREATE TABLE public.hostile_concurrent_ddl "
                            "(value text)"
                        )
            return result

        monkeypatch.setattr(
            schema_guard, "classify_schema", classify_with_hostile_ddl)
        try:
            store.migrate()
            assert classifications[:2] == [SchemaState.EMPTY, SchemaState.EMPTY]
            with Store._raw_connection(store).cursor() as cur:
                cur.execute(
                    "SELECT to_regclass('public.hostile_concurrent_ddl') AS relation"
                )
                assert cur.fetchone()["relation"] is None
                cur.execute("SELECT count(*) AS n FROM runtime_schema_ledger")
                assert cur.fetchone()["n"] == 1
        finally:
            store.close()


def test_empty_install_refuses_ordinary_unprivileged_application_role():
    role = f"ofarm_unprivileged_{uuid.uuid4().hex[:10]}"
    admin_dsn = _admin_dsn()
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(
            sql.Identifier(role)))
    try:
        with _isolated_database("schema_unprivileged") as dsn:
            verified = verify_static_runtime_catalog(config.PACKAGE_ROOT)
            with psycopg.connect(
                    dsn, autocommit=True, row_factory=dict_row) as ordinary:
                ordinary.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(
                    sql.Identifier(role)))
                with pytest.raises(
                        SchemaGuardError,
                        match="could not be classified read-only"):
                    ensure_schema(ordinary, verified)
                assert ordinary.execute(
                    "SELECT to_regclass('public.runtime_schema_ledger') AS relation"
                ).fetchone()["relation"] is None
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(
                sql.Identifier(role)))


def test_base_schema_to_head_is_untouched_and_requires_recreate():
    """The exact pre-#171 base schema is refused, never forward-migrated."""
    base_schema = (
        Path(__file__).parent / "fixtures" / "schema_pre_issue171.sql"
    ).read_text(encoding="utf-8")
    with _isolated_database("schema_legacy") as dsn:
        with psycopg.connect(dsn, autocommit=True) as legacy:
            legacy.execute(base_schema)
            legacy.execute(
                "INSERT INTO public.kernel_record "
                "(record_id, record_kind, schema_hash, payload, payload_sha256) "
                "VALUES ('legacy:sentinel', 'ofarm.test.base-schema.v0.1', "
                "'sha256:base-schema', '{\"untouched\":true}'::jsonb, "
                "'sha256:legacy-payload')"
            )
            with legacy.cursor(row_factory=dict_row) as cur:
                before_catalog = schema_guard.postgres_catalog_document(cur)
                cur.execute(
                    "SELECT record_id, record_kind, schema_hash, payload, "
                    "payload_sha256 FROM public.kernel_record "
                    "WHERE record_id = 'legacy:sentinel'"
                )
                before_record = cur.fetchone()

        store = Store(dsn=dsn)
        try:
            with pytest.raises(SchemaGuardError, match="recreate the target database"):
                store.migrate()
        finally:
            store.close()

        with psycopg.connect(dsn, autocommit=True) as check:
            with check.cursor(row_factory=dict_row) as cur:
                assert schema_guard.postgres_catalog_document(cur) == before_catalog
                cur.execute(
                    "SELECT record_id, record_kind, schema_hash, payload, "
                    "payload_sha256 FROM public.kernel_record "
                    "WHERE record_id = 'legacy:sentinel'"
                )
                assert cur.fetchone() == before_record
                cur.execute(
                    "SELECT to_regclass('public.runtime_schema_ledger') AS relation"
                )
                assert cur.fetchone()["relation"] is None


@pytest.mark.parametrize("global_object", ["cast", "event-trigger"])
def test_object_free_public_refuses_unreviewed_global_executable_catalog(
        global_object):
    with _isolated_database(f"schema_global_{global_object}") as dsn:
        with psycopg.connect(dsn, autocommit=True) as altered:
            if global_object == "cast":
                altered.execute(
                    "CREATE CAST (integer AS date) WITH INOUT AS ASSIGNMENT")
            else:
                altered.execute("CREATE SCHEMA hostile_runtime")
                altered.execute(
                    "CREATE FUNCTION hostile_runtime.on_ddl() "
                    "RETURNS event_trigger LANGUAGE plpgsql AS "
                    "'BEGIN RETURN; END'")
                altered.execute(
                    "CREATE EVENT TRIGGER hostile_runtime_ddl "
                    "ON ddl_command_end EXECUTE FUNCTION "
                    "hostile_runtime.on_ddl()")

        store = Store(dsn=dsn)
        try:
            with pytest.raises(SchemaGuardError, match="recreate the target database"):
                store.migrate()
        finally:
            store.close()

        with psycopg.connect(dsn, autocommit=True) as check:
            assert check.execute(
                "SELECT pg_catalog.to_regclass("
                "'public.runtime_schema_ledger')"
            ).fetchone()[0] is None


def test_object_free_public_schema_with_acl_drift_is_not_provably_empty():
    with _isolated_database("schema_acl_drift") as dsn:
        with psycopg.connect(dsn, autocommit=True) as altered:
            altered.execute("GRANT CREATE ON SCHEMA public TO PUBLIC")
            altered.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT SELECT ON TABLES TO PUBLIC"
            )

        store = Store(dsn=dsn)
        try:
            with pytest.raises(SchemaGuardError, match="owner/default ACL posture"):
                store.migrate()
        finally:
            store.close()

        with psycopg.connect(dsn, autocommit=True) as check:
            assert check.execute(
                "SELECT to_regclass('public.runtime_schema_ledger')"
            ).fetchone()[0] is None
            assert check.execute(
                "SELECT EXISTS ("
                "SELECT 1 FROM pg_namespace n "
                "CROSS JOIN LATERAL aclexplode(n.nspacl) acl "
                "WHERE n.nspname = 'public' AND acl.grantee = 0 "
                "AND acl.privilege_type = 'CREATE')"
            ).fetchone()[0] is True
            assert check.execute(
                "SELECT count(*) FROM pg_default_acl"
            ).fetchone()[0] == 1


def test_catalog_fingerprint_covers_internal_triggers_rules_and_user_types():
    with _isolated_database("schema_trigger_rule_drift") as dsn:
        store = Store(dsn=dsn)
        try:
            store.migrate()
            with Store._raw_connection(store).cursor() as cur:
                cur.execute(
                    "SELECT trg.tgname FROM pg_trigger trg "
                    "JOIN pg_class rel ON rel.oid = trg.tgrelid "
                    "JOIN pg_namespace n ON n.oid = rel.relnamespace "
                    "WHERE n.nspname = 'public' "
                    "AND rel.relname = 'derived_materialization' "
                    "AND trg.tgisinternal ORDER BY trg.tgname LIMIT 1"
                )
                internal_trigger = cur.fetchone()["tgname"]
            Store._raw_connection(store).execute(sql.SQL(
                "ALTER TABLE public.derived_materialization DISABLE TRIGGER {}"
            ).format(sql.Identifier(internal_trigger)))
            with pytest.raises(SchemaGuardError, match="catalog-drifted"):
                store.migrate()
            Store._raw_connection(store).execute(sql.SQL(
                "ALTER TABLE public.derived_materialization ENABLE TRIGGER {}"
            ).format(sql.Identifier(internal_trigger)))
            store.migrate()

            Store._raw_connection(store).execute(
                "CREATE RULE hostile_rule AS ON INSERT TO public.kernel_record "
                "DO INSTEAD NOTHING"
            )
            with pytest.raises(SchemaGuardError, match="catalog-drifted"):
                store.migrate()
            Store._raw_connection(store).execute(
                "DROP RULE hostile_rule ON public.kernel_record"
            )
            store.migrate()

            Store._raw_connection(store).execute(
                "CREATE TYPE public.hostile_enum AS ENUM ('one', 'two')"
            )
            Store._raw_connection(store).execute(
                "CREATE DOMAIN public.hostile_domain AS text "
                "CHECK (VALUE <> '')"
            )
            Store._raw_connection(store).execute(
                "CREATE TYPE public.hostile_composite AS "
                "(label public.hostile_domain, state public.hostile_enum)"
            )
            with pytest.raises(SchemaGuardError, match="catalog-drifted"):
                store.migrate()
            Store._raw_connection(store).execute(
                "DROP TYPE public.hostile_composite")
            Store._raw_connection(store).execute(
                "DROP DOMAIN public.hostile_domain")
            Store._raw_connection(store).execute(
                "DROP TYPE public.hostile_enum")
            store.migrate()

            Store._raw_connection(store).execute(
                "CREATE AGGREGATE public.hostile_sum(integer) "
                "(SFUNC = pg_catalog.int4pl, STYPE = integer, INITCOND = '0')"
            )
            with pytest.raises(SchemaGuardError, match="catalog-drifted"):
                store.migrate()
            Store._raw_connection(store).execute(
                "DROP AGGREGATE public.hostile_sum(integer)")
            store.migrate()
        finally:
            store.close()


def test_live_catalog_drift_refuses_activation_and_rolls_back_bundle_writes():
    with _isolated_database("schema_activation_drift") as dsn:
        store = Store(dsn=dsn)
        try:
            store.migrate()
            Store._raw_connection(store).execute(
                "ALTER TABLE public.kernel_record "
                "ADD COLUMN hostile_catalog_drift text"
            )

            with pytest.raises(
                    context.ContextNotReconstructible,
                    match="catalog-drifted|protected install receipt|recreate"):
                context.bootstrap_for_descriptor(store, config.ACTIVE_PROFILE)

            assert store._runtime_bundle is None
            with Store._raw_connection(store).cursor() as cur:
                cur.execute("SELECT count(*) AS n FROM runtime_bundle")
                assert cur.fetchone()["n"] == 0
                cur.execute("SELECT count(*) AS n FROM runtime_bundle_component")
                assert cur.fetchone()["n"] == 0
                cur.execute("SELECT count(*) AS n FROM kernel_record")
                assert cur.fetchone()["n"] == 0
                cur.execute(
                    "SELECT count(*) AS n FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'kernel_record' "
                    "AND column_name = 'hostile_catalog_drift'"
                )
                assert cur.fetchone()["n"] == 1
        finally:
            store.close()


def test_cross_schema_inheritance_cannot_inject_governed_rows():
    with _isolated_database("schema_inheritance") as dsn:
        store = Store(dsn=dsn)
        try:
            store.migrate()
            with psycopg.connect(dsn, autocommit=True) as hostile:
                hostile.execute("CREATE SCHEMA hostile_runtime")
                hostile.execute(
                    "CREATE TABLE hostile_runtime.injected () "
                    "INHERITS (public.kernel_record)"
                )
                hostile.execute(
                    "INSERT INTO hostile_runtime.injected "
                    "(record_id, record_kind, schema_hash, payload, "
                    "payload_sha256, tenant_ref, runtime_bundle_digest) VALUES "
                    "('hostile:inherited', 'ofarm.hostile.v0.1', "
                    "'sha256:hostile-schema', '{\"injected\":true}'::jsonb, "
                    "'sha256:hostile-payload', 'tenant:hostile', "
                    "'sha256:hostile-runtime')"
                )
                assert hostile.execute(
                    "SELECT record_id FROM public.kernel_record "
                    "WHERE record_id = 'hostile:inherited'"
                ).fetchone()[0] == "hostile:inherited"
            with pytest.raises(SchemaGuardError, match="catalog-drifted"):
                store.get_record("hostile:inherited")
        finally:
            store.close()
            with psycopg.connect(dsn, autocommit=True) as cleanup:
                cleanup.execute("DROP SCHEMA IF EXISTS hostile_runtime CASCADE")
