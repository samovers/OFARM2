"""Authoritative PostgreSQL 17 security-audit migration tests for issue #174."""

from __future__ import annotations

import hashlib
import os
import secrets
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import UUID, uuid4

import psycopg
import psycopg.conninfo
import pytest
from psycopg import sql

from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT
from deployment.postgresql.catalog_classifier import (
    SCHEMA_LOCAL_CATALOG_CLASSES,
)
from deployment.postgresql.migration_runner import (
    MigrationDirtyError,
    MigrationTargetError,
    initial_ledger_sql,
    migrate_service,
    validate_migration_source,
)
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    load_migration_set,
)
from deployment.postgresql.provisioning import provision_service
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
)


AUDIT_ADMIN_ENV = "OFARM_SECURITY_AUDIT_PG_ADMIN_DSN"
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
QUERY_IDENTITY = (
    "ofarm_security.query_operational_security_events"
    "(uuid, timestamptz, uuid, integer, bigint)"
)
LIVE_PHYSICAL_REPLICATION_GATE = (
    "NOT EXISTS (\n"
    "            SELECT 1\n"
    "            FROM pg_catalog.pg_stat_get_wal_senders()\n"
    "        )\n"
    "        AND NOT EXISTS (\n"
    "            SELECT 1\n"
    "            FROM pg_catalog.pg_stat_get_wal_receiver() AS receiver\n"
    "            WHERE receiver.pid IS NOT NULL\n"
    "        )"
)
LARGE_OBJECT_ROUTINE_IDENTITIES = (
    "lo_close(integer)",
    "lo_creat(integer)",
    "lo_create(oid)",
    "lo_export(oid, text)",
    "lo_from_bytea(oid, bytea)",
    "lo_get(oid)",
    "lo_get(oid, bigint, integer)",
    "lo_import(text)",
    "lo_import(text, oid)",
    "lo_lseek(integer, integer, integer)",
    "lo_lseek64(integer, bigint, integer)",
    "lo_open(oid, integer)",
    "lo_put(oid, bigint, bytea)",
    "lo_tell(integer)",
    "lo_tell64(integer)",
    "lo_truncate(integer, integer)",
    "lo_truncate64(integer, bigint)",
    "lo_unlink(oid)",
    "loread(integer, integer)",
    "lowrite(integer, bytea)",
)
BACKEND_STATISTICS_ROUTINE_IDENTITIES = (
    "pg_stat_get_activity(integer)",
    "pg_stat_get_backend_activity(integer)",
    "pg_stat_get_backend_activity_start(integer)",
    "pg_stat_get_backend_client_addr(integer)",
    "pg_stat_get_backend_client_port(integer)",
    "pg_stat_get_backend_dbid(integer)",
    "pg_stat_get_backend_idset()",
    "pg_stat_get_backend_pid(integer)",
    "pg_stat_get_backend_start(integer)",
    "pg_stat_get_backend_subxact(integer)",
    "pg_stat_get_backend_userid(integer)",
    "pg_stat_get_backend_wait_event(integer)",
    "pg_stat_get_backend_wait_event_type(integer)",
    "pg_stat_get_backend_xact_start(integer)",
)


def _database_dsn(admin_dsn: str, database_name: str, **overrides: str) -> str:
    parameters = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    parameters["dbname"] = database_name
    parameters.update(overrides)
    return psycopg.conninfo.make_conninfo(**parameters)


def _table_definition(source: str, qualified_name: str) -> str:
    marker = f"CREATE TABLE {qualified_name} ("
    start = source.index(marker)
    end = source.index("\n);", start) + len("\n);")
    return source[start:end]


def _destroy_service(admin_dsn: str) -> None:
    spec = SECURITY_AUDIT_PROVISIONING_SPEC
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(
            """
            SELECT pg_catalog.pg_terminate_backend(pid)
            FROM pg_catalog.pg_stat_activity
            WHERE datname = %s AND pid <> pg_catalog.pg_backend_pid()
            """,
            (spec.database_name,),
        )
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(spec.database_name)
            )
        )
        roles = [
            row[0]
            for row in connection.execute(
                r"""
                SELECT rolname::text
                FROM pg_catalog.pg_roles
                WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
                ORDER BY rolname
                """
            ).fetchall()
        ]
        if roles:
            connection.execute(
                sql.SQL("DROP ROLE {}").format(
                    sql.SQL(", ").join(sql.Identifier(role) for role in roles)
                )
            )
        for database_name in ("postgres", "template0", "template1"):
            connection.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO PUBLIC").format(
                    sql.Identifier(database_name)
                )
            )
        connection.execute(
            "GRANT TEMPORARY ON DATABASE postgres TO PUBLIC"
        )
        for database_name in ("template0", "template1"):
            connection.execute(
                sql.SQL("REVOKE TEMPORARY ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(database_name)
                )
            )


def _role_dsn(state: dict[str, object], role: str) -> str:
    return _database_dsn(
        state["admin_dsn"],
        SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
        user=role,
        password=state["passwords"][role],
    )


def _wait_for_event_relation_lock(
    state: dict[str, object], application_name: str, mode: str
) -> None:
    deadline = monotonic() + 5
    with psycopg.connect(
        state["target_admin_dsn"], autocommit=True
    ) as admin:
        while monotonic() < deadline:
            waiting = admin.execute(
                """
                SELECT 1
                FROM pg_catalog.pg_locks AS lock
                JOIN pg_catalog.pg_stat_activity AS activity
                  ON activity.pid = lock.pid
                WHERE activity.application_name = %s
                  AND lock.locktype = 'relation'
                  AND lock.relation =
                      'ofarm_security.operational_security_event'::
                          pg_catalog.regclass
                  AND lock.mode = %s
                  AND NOT lock.granted
                """,
                (application_name, mode),
            ).fetchone()
            if waiting is not None:
                return
            sleep(0.025)
    raise AssertionError(
        f"{application_name} did not wait for {mode} on the event relation"
    )


def _wait_for_blocked_event_writer(
    state: dict[str, object], application_name: str
) -> None:
    deadline = monotonic() + 15
    with psycopg.connect(
        state["target_admin_dsn"], autocommit=True
    ) as admin:
        while monotonic() < deadline:
            waiting = admin.execute(
                """
                SELECT 1
                FROM pg_catalog.pg_stat_activity AS activity
                JOIN pg_catalog.pg_locks AS lock
                  ON lock.pid = activity.pid
                WHERE activity.application_name = %s
                  AND activity.state = 'active'
                  AND activity.wait_event_type = 'Lock'
                  AND lock.locktype = 'relation'
                  AND lock.relation =
                      'ofarm_security.operational_security_event'::
                          pg_catalog.regclass
                  AND lock.mode = 'RowExclusiveLock'
                  AND lock.granted
                """,
                (application_name,),
            ).fetchone()
            if waiting is not None:
                return
            sleep(0.025)
    raise AssertionError(
        f"{application_name} did not block while holding the event writer lock"
    )


@pytest.fixture(scope="module")
def migrated_audit_service():
    admin_dsn = os.environ.get(AUDIT_ADMIN_ENV)
    if not admin_dsn:
        pytest.skip(f"{AUDIT_ADMIN_ENV} is required for real PostgreSQL tests")
    spec = SECURITY_AUDIT_PROVISIONING_SPEC
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        existing_database = connection.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (spec.database_name,),
        ).fetchone()
        existing_roles = connection.execute(
            r"""
            SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\' LIMIT 1
            """
        ).fetchone()
    assert existing_database is None
    assert existing_roles is None

    passwords = {
        role: f"audit-0001-{index}-{secrets.token_urlsafe(32)}"
        for index, role in enumerate(spec.required_password_role_names)
    }
    try:
        provision_service(admin_dsn, spec, login_passwords=passwords)
        migration_set = load_migration_set(PACKAGE_ROOT, SECURITY_AUDIT_SERVICE)
        report = migrate_service(
            admin_dsn=admin_dsn,
            migrator_dsn=_database_dsn(
                admin_dsn,
                spec.database_name,
                user="ofarm_migrator",
                password=passwords["ofarm_migrator"],
            ),
            spec=spec,
            migration_set=migration_set,
            release_identity="issue-174-audit-0001-test",
            execution_id=uuid4(),
        )
        yield {
            "admin_dsn": admin_dsn,
            "target_admin_dsn": _database_dsn(admin_dsn, spec.database_name),
            "passwords": passwords,
            "migration_set": migration_set,
            "report": report,
        }
    finally:
        _destroy_service(admin_dsn)


def test_authoritative_audit_migration_is_one_exact_initial_set():
    migration_set = load_migration_set(PACKAGE_ROOT, SECURITY_AUDIT_SERVICE)
    migration = migration_set.migrations[0]
    source = migration.source_bytes.decode("utf-8")

    assert len(migration_set.migrations) == 1
    assert migration.filename == "0001_initial.sql"
    assert validate_migration_source(
        migration.source_bytes, migration.filename
    ) == source
    assert initial_ledger_sql(SECURITY_AUDIT_PROVISIONING_SPEC) in source
    assert SECURITY_AUDIT_CONTRACT.digest in source
    assert SECURITY_AUDIT_PROVISIONING_SPEC.digest in source
    assert migration.source_sha256 == \
        "sha256:5e648e0127ca386363c3a1d979a5718cbd5b4846b3ad98ceaee5e7684b278517"
    assert migration.byte_length == 169_237
    assert migration_set.digest == \
        "sha256:e3752c1f7d54dff7b749367a29a53b48b5ca3258e51b1a8388dacdcd830392b6"
    assert migration_set.prefix_digest(1) == migration_set.digest


def test_authoritative_audit_migration_has_closed_carriers_and_limits():
    source = load_migration_set(
        PACKAGE_ROOT, SECURITY_AUDIT_SERVICE
    ).migrations[0].source_bytes.decode("utf-8")
    persisted_audit_tables = "\n".join(
        _table_definition(source, qualified_name)
        for qualified_name in (
            "ofarm_security.operational_security_event",
            "ofarm_security.operational_security_quota_bucket",
            "ofarm_security.operational_security_quota_high_water",
            "ofarm_security.operational_security_event_identity_lock",
            "ofarm_security.operational_security_overflow_identity_receipt",
        )
    )

    assert source.count("CREATE TABLE ofarm_security.operational_security_") == 5
    assert "CREATE TABLE ofarm_security.operational_security_event" in source
    assert (
        "CREATE SEQUENCE "
        "ofarm_security.operational_security_access_clock_high_water"
        in source
    )
    assert "operational_security_access_clock_lock" not in source
    assert "CREATE TABLE ofarm_security.operational_security_quota_bucket" in source
    assert (
        "CREATE TABLE ofarm_security.operational_security_quota_high_water"
        in source
    )
    assert (
        "CREATE TABLE ofarm_security.operational_security_event_identity_lock"
        in source
    )
    assert (
        "CREATE TABLE "
        "ofarm_security.operational_security_overflow_identity_receipt"
        in source
    )
    assert "FROM pg_catalog.generate_series(0, 255) AS slots(slot)" in source
    assert "CROSS JOIN pg_catalog.generate_series(0, 255) AS slots(slot)" in source
    assert (
        "pg_catalog.sha256(pg_catalog.uuid_send(p_event_id)), 0" in source
    )
    assert "BETWEEN 0 AND 1024" in source
    assert "LIMIT 1024" in source
    assert "p_max_rows BETWEEN 1 AND 256" in source
    assert "p_max_bytes BETWEEN 1 AND 1048576" in source
    assert "p_max_rows BETWEEN 1 AND 2048" in source
    assert "p_max_bytes BETWEEN 1 AND 8388608" in source
    assert "make_interval(secs => 2592000)" in source
    assert "make_interval(days => 30)" not in source
    assert "make_interval(secs => 300)" in source
    assert "make_interval(secs => 60)" in source
    assert "OFARM_SECURITY_AUDIT_COMPLETE_CATALOG_V1" in source
    assert "SELF_SOURCE_EXCLUDED" in source
    assert "'parameter-acl'" in source
    assert "FROM pg_catalog.pg_parameter_acl AS parameter" in source
    assert LIVE_PHYSICAL_REPLICATION_GATE in source
    assert "WHEN unique_violation THEN" in source
    assert source.count("SET TimeZone = 'UTC'") == 2
    assert source.count("SET DateStyle = 'ISO, MDY'") == 2
    assert source.count("SET bytea_output = 'hex'") == 1
    assert source.count("SET quote_all_identifiers = off") == 1
    assert source.count("SET standard_conforming_strings = on") == 1
    assert source.count(
        "CASE WHEN grantor.rolsuper THEN 'BOOTSTRAP_SUPERUSER'"
    ) == 5
    assert "FROM pg_catalog.pg_largeobject_metadata" in source
    assert "'large-object-routine'" in source
    assert "'large-object-routine-acl'" in source
    assert "routine.pronargs" in source
    assert "routine.pronargdefaults" in source
    assert "routine.prosupport = 0" in source
    assert "routine.prosqlbody IS NULL" in source
    assert source.count(
        "pg_catalog.left(routine.proname::pg_catalog.text, 3) = 'lo_'"
    ) == 3
    for identity in LARGE_OBJECT_ROUTINE_IDENTITIES:
        assert f"'{identity}'" in source
    assert "'backend-statistics-view'" in source
    assert "'backend-statistics-view-columns'" in source
    assert "'backend-statistics-view-rewrite'" in source
    assert "'rewrite-rule'" in source
    assert "FROM pg_catalog.pg_rewrite AS rewrite_rule" in source
    assert "pg_catalog.pg_get_ruledef(rewrite_rule.oid, false)" in source
    assert "rewrite_rule.ev_qual" not in source
    assert "rewrite_rule.ev_action" not in source
    assert source.count("relation_rule.ev_class = class.oid") == 2
    assert source.count("relation_trigger.tgrelid = class.oid") == 1
    assert source.count("relation_child.inhparent = class.oid") == 1
    assert source.count("relation_index.indrelid = class.oid") == 1
    for lazy_hint in (
        "class.relhasrules",
        "class.relhastriggers",
        "class.relhassubclass",
        "class.relhasindex",
    ):
        assert lazy_hint not in source
    assert "'backend-statistics-view-acl'" in source
    assert "'backend-statistics-routine'" in source
    assert "'backend-statistics-routine-acl'" in source
    assert "pg_catalog.pg_get_viewdef(class.oid, false)" in source
    assert source.count(
        "'pg_stat_get_activity', 'pg_stat_get_backend_'"
    ) == 4
    for identity in BACKEND_STATISTICS_ROUTINE_IDENTITIES:
        assert f"'{identity}'" in source
    assert (
        "aadb04a6c86ebe27e142ec71c95a1a48422a5930e942fdfa61cd2095340a3934"
        in source
    )
    assert (
        "sha256:90f439c108b77a33e44cc987a057b601c27dfe2e4a4c3bb1e128d4cb2106f663"
        in source
    )
    assert "jsonb" not in persisted_audit_tables
    for forbidden in (
        "tenant_id",
        "tenant_ref",
        "party_ref",
        "message pg_catalog.text",
        "details",
        "CREATE EXTENSION",
    ):
        assert forbidden not in source


def test_access_intent_serializes_writers_before_combined_cut_capture():
    source = load_migration_set(
        PACKAGE_ROOT, SECURITY_AUDIT_SERVICE
    ).migrations[0].source_bytes.decode("utf-8")
    access_function = source.split(
        "CREATE FUNCTION ofarm_security.commit_audit_access_intent(", 1
    )[1].split(
        "REVOKE ALL PRIVILEGES ON FUNCTION "
        "ofarm_security.commit_audit_access_intent(",
        1,
    )[0]
    isolation_guard = """    IF pg_catalog.current_setting('transaction_isolation') <>
            'read committed' THEN
        RAISE EXCEPTION USING ERRCODE = '25001',
            MESSAGE = 'audit access intent requires READ COMMITTED';
    END IF;"""
    writer_barrier = """    LOCK TABLE ofarm_security.operational_security_event
        IN SHARE ROW EXCLUSIVE MODE;"""
    combined_capture = """    SELECT
        access_clock.observed_at,
        access_clock.clock_regressed,
        pg_catalog.pg_current_snapshot()
    INTO STRICT
        v_data_cut,
        v_clock_regressed,
        v_visibility_snapshot
    FROM ofarm_security._observe_nonregressing_access_clock() AS access_clock;"""

    assert access_function.count(isolation_guard) == 1
    assert access_function.count(writer_barrier) == 1
    assert access_function.count(combined_capture) == 1
    assert (
        access_function.index(isolation_guard)
        < access_function.index(writer_barrier)
        < access_function.index(combined_capture)
    )
    assert "v_data_cut := pg_catalog.clock_timestamp()" not in access_function
    assert (
        "v_visibility_snapshot := pg_catalog.pg_current_snapshot()"
        not in access_function
    )


def test_bounded_access_uses_one_nonregressing_clock_authority():
    source = load_migration_set(
        PACKAGE_ROOT, SECURITY_AUDIT_SERVICE
    ).migrations[0].source_bytes.decode("utf-8")
    clock_function = source.split(
        "CREATE FUNCTION "
        "ofarm_security._observe_nonregressing_access_clock()",
        1,
    )[1].split(
        "REVOKE ALL PRIVILEGES ON FUNCTION\n"
        "ofarm_security._observe_nonregressing_access_clock()",
        1,
    )[0]
    bounded_function = source.split(
        "CREATE FUNCTION "
        "ofarm_security._bounded_operational_security_events(",
        1,
    )[1].split(
        "REVOKE ALL PRIVILEGES ON FUNCTION\n"
        "ofarm_security._bounded_operational_security_events(",
        1,
    )[0]

    assert (
        "ofarm_infrastructure.take_audit_access_clock_lock()"
        in clock_function
    )
    assert clock_function.count(
        "ofarm_infrastructure.release_audit_access_clock_lock()"
    ) == 3
    assert "pg_catalog.pg_advisory_lock(" not in clock_function
    assert "pg_catalog.pg_advisory_unlock(" not in clock_function
    assert "FOR UPDATE;" not in clock_function
    assert "pg_catalog.setval(" in clock_function
    assert "clock_regressed :=" in clock_function
    assert bounded_function.count(
        "ofarm_security._observe_nonregressing_access_clock()"
    ) == 1
    assert "v_access_expiry_microseconds <= " in bounded_function
    assert "MESSAGE = 'audit access clock regressed'" in bounded_function


def test_pretenant_append_rejects_fixed_snapshots_before_identity_reads():
    source = load_migration_set(
        PACKAGE_ROOT, SECURITY_AUDIT_SERVICE
    ).migrations[0].source_bytes.decode("utf-8")
    append_function = source.split(
        "CREATE FUNCTION ofarm_security.append_pretenant_failure(", 1
    )[1].split(
        "REVOKE ALL PRIVILEGES ON FUNCTION "
        "ofarm_security.append_pretenant_failure(",
        1,
    )[0]
    isolation_guard = """    IF pg_catalog.current_setting('transaction_isolation') <>
            'read committed' THEN
        RAISE EXCEPTION USING ERRCODE = '25001',
            MESSAGE = 'pre-tenant append requires READ COMMITTED';
    END IF;"""
    identity_lock = """    SELECT lock_slot INTO STRICT v_identity_lock_slot
    FROM ofarm_security.operational_security_event_identity_lock"""
    body = append_function.split("BEGIN\n", 1)[1]

    assert body.startswith(isolation_guard)
    assert append_function.count(isolation_guard) == 1
    assert append_function.count(identity_lock) == 1
    assert append_function.index(isolation_guard) < append_function.index(
        identity_lock
    )


def test_access_expiry_freezes_retention_membership_for_page_reuse():
    source = load_migration_set(
        PACKAGE_ROOT, SECURITY_AUDIT_SERVICE
    ).migrations[0].source_bytes.decode("utf-8")
    event_table = _table_definition(
        source, "ofarm_security.operational_security_event"
    )
    bounded_function = source.split(
        "CREATE FUNCTION "
        "ofarm_security._bounded_operational_security_events(",
        1,
    )[1].split(
        "REVOKE ALL PRIVILEGES ON FUNCTION\n"
        "ofarm_security._bounded_operational_security_events(",
        1,
    )[0]

    assert (
        "purge_after = observed_at +\n"
        "            pg_catalog.make_interval(secs => 2592000)"
        in event_table
    )
    retained_query = """        WHERE e.purge_after > v_access.access_expires_at
          AND e.observed_at <= v_access.access_data_cut"""
    assert bounded_function.count(retained_query) == 1
    assert "WHERE e.purge_after > v_now" not in bounded_function
    assert bounded_function.count(
        "        ORDER BY e.observed_at DESC, e.event_id DESC\n"
        "        LIMIT p_max_rows"
    ) == 1


def test_audit_catalog_fingerprint_has_exact_shared_schema_class_parity():
    source = (
        PACKAGE_ROOT
        / SECURITY_AUDIT_SERVICE.relative_directory
        / "0001_initial.sql"
    ).read_text(encoding="utf-8")
    marker = "-- SCHEMA_LOCAL_CATALOG_CLASSIFIER_V1"
    assert source.count(marker) == 1
    classifier = source.split(marker, 1)[1].split(
        "    )\n    SELECT 'sha256:'",
        1,
    )[0]
    assert classifier.count("'schema-local-") == len(
        SCHEMA_LOCAL_CATALOG_CLASSES
    )
    for item in SCHEMA_LOCAL_CATALOG_CLASSES:
        assert classifier.count(f"'schema-local-{item.category}'") == 1
        assert classifier.count(
            f"FROM pg_catalog.{item.catalog_name} AS schema_local_object"
        ) == 1
        assert classifier.count(
            f"schema_local_object.{item.name_column}::pg_catalog.text"
        ) == 1
        assert classifier.count(
            f"schema_local_object.{item.namespace_column}"
        ) == 1


def test_audit_observer_requires_zero_prepared_transaction_capacity():
    source = (
        PACKAGE_ROOT
        / SECURITY_AUDIT_SERVICE.relative_directory
        / "0001_initial.sql"
    ).read_text(encoding="utf-8")
    marker = "-- PREPARED_TRANSACTION_STARTUP_POSTURE_V1"
    gate = (
        "pg_catalog.current_setting(\n"
        "           'max_prepared_transactions'\n"
        "       )::pg_catalog.int4 <> 0"
    )

    assert source.count(marker) == 1
    assert source.count(gate) == 1
    assert source.count("FROM pg_catalog.pg_prepared_xacts") == 1


def test_authoritative_audit_migration_installs_exact_public_functions():
    source = load_migration_set(
        PACKAGE_ROOT, SECURITY_AUDIT_SERVICE
    ).migrations[0].source_bytes.decode("utf-8")

    for function in SECURITY_AUDIT_CONTRACT.public_functions:
        assert f"CREATE FUNCTION {function.qualified_name}" in source
        assert f"TO {function.capability_role};" in source
    assert source.count("SECURITY DEFINER") == 10
    assert "FROM PUBLIC;" in source


def test_migrated_audit_structure_observes_exact_ready_contract(
    migrated_audit_service,
):
    state = migrated_audit_service
    report = state["report"]
    assert report.applied_versions == (1,)
    assert report.final_version == 1
    assert report.migration_set_digest == state["migration_set"].digest

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_readiness_login"),
        autocommit=True,
    ) as connection:
        row = connection.execute(
            "SELECT * FROM ofarm_security.observe_security_audit_contract()"
        ).fetchone()
    assert row[0] == SECURITY_AUDIT_CONTRACT.identity
    assert row[1] == SECURITY_AUDIT_CONTRACT.digest
    assert row[8] == SECURITY_AUDIT_PROVISIONING_SPEC.digest
    assert row[9] == 1
    assert row[10] == state["migration_set"].digest
    assert row[11:] == (True, False)

    with psycopg.connect(
        _role_dsn(state, "ofarm_migrator"), autocommit=True
    ) as migrator:
        migrator.execute("SET ROLE ofarm_security_audit_owner")
        structural = migrator.execute(
            "SELECT * FROM ofarm_security.verify_security_audit_structure()"
        ).fetchone()
    assert structural == (True, 0, False)

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_readiness_login"),
        autocommit=True,
    ) as readiness:
        readiness.execute("SET TimeZone = 'Europe/Ljubljana'")
        readiness.execute("SET DateStyle = 'SQL, DMY'")
        readiness.execute("SET quote_all_identifiers = on")
        readiness.execute("SET IntervalStyle = 'sql_standard'")
        readiness.execute("SET extra_float_digits = -15")
        readiness.execute("SET bytea_output = 'escape'")
        readiness.execute("SET standard_conforming_strings = off")
        hostile_guc_structure = readiness.execute(
            "SELECT * FROM ofarm_security.verify_security_audit_structure()"
        ).fetchone()
        assert readiness.execute(
            "SELECT current_setting('TimeZone'), "
            "current_setting('DateStyle'), "
            "current_setting('quote_all_identifiers'), "
            "current_setting('IntervalStyle'), "
            "current_setting('extra_float_digits'), "
            "current_setting('bytea_output'), "
            "current_setting('standard_conforming_strings')"
        ).fetchone() == (
            "Europe/Ljubljana",
            "SQL, DMY",
            "on",
            "sql_standard",
            "-15",
            "escape",
            "off",
        )
    assert hostile_guc_structure == (True, 0, False)

    with psycopg.connect(state["target_admin_dsn"]) as connection:
        (
            verifier_source,
            verifier_proconfig,
            live_replication_count,
        ) = connection.execute(
            """
            SELECT routine.prosrc,
                   routine.proconfig,
                   (SELECT pg_catalog.count(*)
                    FROM pg_catalog.pg_stat_get_wal_senders())
                   +
                   (SELECT pg_catalog.count(*)
                    FROM pg_catalog.pg_stat_get_wal_receiver() AS receiver
                    WHERE receiver.pid IS NOT NULL)
            FROM pg_catalog.pg_proc AS routine
            WHERE routine.oid =
                'ofarm_security.verify_security_audit_structure()'::
                    pg_catalog.regprocedure
            """
        ).fetchone()
        large_object_inventory = tuple(
            row[0]
            for row in connection.execute(
                """
                SELECT routine.proname::pg_catalog.text || '(' ||
                       pg_catalog.pg_get_function_identity_arguments(
                           routine.oid
                       ) || ')' AS routine_identity
                FROM pg_catalog.pg_proc AS routine
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = routine.pronamespace
                WHERE namespace.nspname = 'pg_catalog'
                  AND (
                    pg_catalog.left(
                        routine.proname::pg_catalog.text, 3
                    ) = 'lo_'
                    OR routine.proname IN ('loread', 'lowrite')
                  )
                ORDER BY (
                    routine.proname::pg_catalog.text || '(' ||
                    pg_catalog.pg_get_function_identity_arguments(
                        routine.oid
                    ) || ')'
                ) COLLATE pg_catalog."C"
                """
            )
        )
        large_object_metadata_count = connection.execute(
            "SELECT pg_catalog.count(*) "
            "FROM pg_catalog.pg_largeobject_metadata"
        ).fetchone()[0]
        public_large_object_execute_count = connection.execute(
            """
            SELECT pg_catalog.count(*)
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = routine.pronamespace
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(
                    routine.proacl,
                    pg_catalog.acldefault('f', routine.proowner)
                )
            ) AS acl
            WHERE namespace.nspname = 'pg_catalog'
              AND (
                pg_catalog.left(routine.proname::pg_catalog.text, 3) = 'lo_'
                OR routine.proname IN ('loread', 'lowrite')
              )
              AND acl.grantee = 0
              AND acl.privilege_type = 'EXECUTE'
            """
        ).fetchone()[0]
        backend_statistics_routine_inventory = tuple(
            row[0]
            for row in connection.execute(
                """
                SELECT routine.proname::pg_catalog.text || '(' ||
                       pg_catalog.oidvectortypes(routine.proargtypes) || ')'
                FROM pg_catalog.pg_proc AS routine
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = routine.pronamespace
                WHERE namespace.nspname = 'pg_catalog'
                  AND pg_catalog.left(
                          routine.proname::pg_catalog.text, 20
                      ) IN (
                          'pg_stat_get_activity',
                          'pg_stat_get_backend_'
                      )
                ORDER BY
                    routine.proname COLLATE pg_catalog."C",
                    pg_catalog.oidvectortypes(routine.proargtypes)
                        COLLATE pg_catalog."C"
                """
            )
        )
        backend_statistics_routine_acl_posture = connection.execute(
            """
            SELECT pg_catalog.count(*),
                   pg_catalog.count(*) FILTER (
                       WHERE NOT owner.rolsuper
                          OR acl.grantee <> routine.proowner
                          OR acl.grantor <> routine.proowner
                          OR acl.privilege_type <> 'EXECUTE'
                          OR acl.is_grantable
                   )
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = routine.pronamespace
            JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(
                    routine.proacl,
                    pg_catalog.acldefault('f', routine.proowner)
                )
            ) AS acl
            WHERE namespace.nspname = 'pg_catalog'
              AND pg_catalog.left(
                      routine.proname::pg_catalog.text, 20
                  ) IN ('pg_stat_get_activity', 'pg_stat_get_backend_')
            """
        ).fetchone()
        backend_statistics_view_definition = connection.execute(
            """
            SELECT pg_catalog.pg_get_viewdef(class.oid, false)
            FROM pg_catalog.pg_class AS class
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = class.relnamespace
            WHERE namespace.nspname = 'pg_catalog'
              AND class.relname = 'pg_stat_activity'
              AND class.relkind = 'v'
            """
        ).fetchone()[0]
        backend_statistics_view_columns = tuple(
            connection.execute(
                """
                SELECT attribute.attnum,
                       attribute.attname::pg_catalog.text,
                       type_namespace.nspname::pg_catalog.text,
                       pg_catalog.format_type(
                           attribute.atttypid, attribute.atttypmod
                       ),
                       attribute.attnotnull,
                       CASE WHEN attribute.attcollation = 0 THEN NULL
                            ELSE collation_namespace.nspname::pg_catalog.text ||
                                 '.' ||
                                 column_collation.collname::pg_catalog.text END,
                       attribute.attidentity,
                       attribute.attgenerated,
                       attribute.atthasdef
                FROM pg_catalog.pg_attribute AS attribute
                JOIN pg_catalog.pg_type AS data_type
                  ON data_type.oid = attribute.atttypid
                JOIN pg_catalog.pg_namespace AS type_namespace
                  ON type_namespace.oid = data_type.typnamespace
                LEFT JOIN pg_catalog.pg_collation AS column_collation
                  ON column_collation.oid = attribute.attcollation
                LEFT JOIN pg_catalog.pg_namespace AS collation_namespace
                  ON collation_namespace.oid = column_collation.collnamespace
                WHERE attribute.attrelid =
                      'pg_catalog.pg_stat_activity'::pg_catalog.regclass
                  AND attribute.attnum > 0
                  AND NOT attribute.attisdropped
                ORDER BY attribute.attnum
                """
            )
        )
        backend_statistics_view_acl_posture = connection.execute(
            """
            SELECT pg_catalog.count(*),
                   pg_catalog.count(*) FILTER (
                       WHERE NOT owner.rolsuper
                          OR acl.grantee <> class.relowner
                          OR acl.grantor <> class.relowner
                          OR acl.privilege_type NOT IN (
                              'DELETE',
                              'INSERT',
                              'MAINTAIN',
                              'REFERENCES',
                              'SELECT',
                              'TRIGGER',
                              'TRUNCATE',
                              'UPDATE'
                          )
                          OR acl.is_grantable
                   )
            FROM pg_catalog.pg_class AS class
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = class.relnamespace
            JOIN pg_catalog.pg_roles AS owner ON owner.oid = class.relowner
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(
                    class.relacl,
                    pg_catalog.acldefault('r', class.relowner)
                )
            ) AS acl
            WHERE namespace.nspname = 'pg_catalog'
              AND class.relname = 'pg_stat_activity'
              AND class.relkind = 'v'
            """
        ).fetchone()
        columns = {
            row[0]
            for row in connection.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'ofarm_security'
                  AND table_name = 'operational_security_event'
                """
            )
        }
    assert LIVE_PHYSICAL_REPLICATION_GATE in verifier_source
    assert verifier_proconfig == [
        "search_path=pg_catalog, pg_temp",
        "TimeZone=UTC",
        "DateStyle=ISO, MDY",
        "quote_all_identifiers=off",
        "standard_conforming_strings=on",
    ]
    assert live_replication_count == 0
    assert large_object_inventory == LARGE_OBJECT_ROUTINE_IDENTITIES
    assert large_object_metadata_count == 0
    assert public_large_object_execute_count == 0
    assert backend_statistics_routine_inventory == \
        BACKEND_STATISTICS_ROUTINE_IDENTITIES
    assert backend_statistics_routine_acl_posture == (14, 0)
    assert backend_statistics_view_definition == \
        SECURITY_AUDIT_PROVISIONING_SPEC.activity_view.definition
    assert backend_statistics_view_columns == tuple(
        (
            position,
            column.name,
            "pg_catalog",
            column.data_type,
            False,
            column.collation,
            "",
            "",
            False,
        )
        for position, column in enumerate(
            SECURITY_AUDIT_PROVISIONING_SPEC.activity_view.columns,
            start=1,
        )
    )
    assert backend_statistics_view_acl_posture == (8, 0)
    assert not columns & {
        "tenant_id", "tenant_ref", "party_ref", "actor_ref", "subject",
        "issuer", "request_id", "message", "details", "payload",
    }


def test_pretenant_append_is_attributed_bounded_and_exactly_idempotent(
    migrated_audit_service,
):
    state = migrated_audit_service
    event_id = uuid4()
    arguments = (
        event_id,
        "CREDENTIAL_MISSING",
        bytes(range(32)),
        "OFARM_PRETENANT_CORRELATION_V1",
        1,
    )
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_authentication_producer_login"),
        autocommit=True,
    ) as producer:
        first = producer.execute(
            """
            SELECT * FROM ofarm_security.append_pretenant_failure(
                %s, %s, %s, %s, %s
            )
            """,
            arguments,
        ).fetchone()
        retry = producer.execute(
            """
            SELECT * FROM ofarm_security.append_pretenant_failure(
                %s, %s, %s, %s, %s
            )
            """,
            arguments,
        ).fetchone()
        with pytest.raises(psycopg.Error):
            producer.execute(
                """
                SELECT ofarm_security.append_pretenant_failure(
                    %s, 'VERIFIER_UNAVAILABLE', %s, %s, %s
                )
                """,
                (event_id, arguments[2], arguments[3], arguments[4]),
            )
        with pytest.raises(psycopg.Error):
            producer.execute(
                "SELECT * FROM ofarm_security.operational_security_event"
            )

    assert first == retry
    assert first[0] == event_id
    assert first[3:] == (True, None, False)
    with psycopg.connect(state["target_admin_dsn"]) as connection:
        row = connection.execute(
            """
            SELECT event_kind, producer, component, reason,
                   pg_catalog.octet_length(correlation_hmac_value),
                   EXTRACT(EPOCH FROM purge_after - observed_at)::pg_catalog.int8,
                   pg_catalog.octet_length(append_input_fingerprint)
            FROM ofarm_security.operational_security_event
            WHERE event_id = %s
            """,
            (event_id,),
        ).fetchone()
    assert row == (
        "PRE_TENANT_FAILURE", "AUTHENTICATION_BOUNDARY_V1",
        "AUTHENTICATION", "CREDENTIAL_MISSING", 32, 2592000, 32,
    )


def test_retention_duration_is_fixed_across_caller_timezone_dst_transition(
    migrated_audit_service,
):
    state = migrated_audit_service
    observed_at = datetime.fromisoformat("2099-10-15T12:00:00-04:00")
    with _controlled_pretenant_clock(state):
        with psycopg.connect(
            _role_dsn(
                state, "ofarm_security_authentication_producer_login"
            )
        ) as producer:
            producer.execute("SET LOCAL TimeZone = 'America/New_York'")
            producer.execute(
                "SELECT pg_catalog.set_config('ofarm.test_now', %s, true)",
                (observed_at.isoformat(),),
            )
            retention_seconds = producer.execute(
                """
                SELECT EXTRACT(
                    EPOCH FROM appended.purge_after - appended.observed_at
                )::pg_catalog.int8
                FROM ofarm_security.append_pretenant_failure(
                    %s, 'CREDENTIAL_MISSING', %s,
                    'OFARM_PRETENANT_CORRELATION_V1', 1
                ) AS appended
                """,
                (uuid4(), bytes(range(32))),
            ).fetchone()[0]
            assert retention_seconds == 2592000
            producer.rollback()


def _concurrent_append(
    state: dict[str, object],
    role: str,
    barrier: Barrier,
    arguments: tuple[object, ...],
    observed_at: datetime | None = None,
) -> tuple[str, object]:
    with psycopg.connect(_role_dsn(state, role), autocommit=True) as producer:
        if observed_at is not None:
            producer.execute(
                "SELECT pg_catalog.set_config('ofarm.test_now', %s, false)",
                (observed_at.isoformat(),),
            )
        barrier.wait(timeout=15)
        try:
            row = producer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, %s, %s, %s, %s
                )
                """,
                arguments,
            ).fetchone()
        except psycopg.Error as exc:
            return ("error", exc.diag.message_primary)
    return ("ok", row)


def _run_concurrent_appends(
    state: dict[str, object],
    role: str,
    arguments: tuple[tuple[object, ...], ...],
    observed_at: datetime | None = None,
) -> list[tuple[str, object]]:
    barrier = Barrier(len(arguments))
    with ThreadPoolExecutor(max_workers=len(arguments)) as executor:
        futures = [
            executor.submit(
                _concurrent_append,
                state,
                role,
                barrier,
                call_arguments,
                observed_at,
            )
            for call_arguments in arguments
        ]
        return [future.result(timeout=30) for future in futures]


def _replace_pretenant_append_source(
    admin: psycopg.Connection, source: str
) -> None:
    admin.execute(
        sql.SQL(
            """
            CREATE OR REPLACE FUNCTION ofarm_security.append_pretenant_failure(
                p_event_id pg_catalog.uuid,
                p_reason pg_catalog.text,
                p_correlation_hmac pg_catalog.bytea,
                p_correlation_hmac_domain pg_catalog.text,
                p_correlation_hmac_key_version pg_catalog.int4
            ) RETURNS ofarm_security.append_pretenant_failure_result
            LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
            SET search_path = pg_catalog, pg_temp
            AS {}
            """
        ).format(sql.Literal(source))
    )


@contextmanager
def _controlled_pretenant_clock(
    state: dict[str, object],
) -> Iterator[datetime]:
    with psycopg.connect(
        state["target_admin_dsn"], autocommit=True
    ) as admin:
        original_source, observed_at = admin.execute(
            """
            SELECT routine.prosrc,
                   pg_catalog.date_bin(
                       pg_catalog.make_interval(secs => 60),
                       pg_catalog.clock_timestamp(),
                       '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
                   ) + pg_catalog.make_interval(hours => 1, secs => 30)
            FROM pg_catalog.pg_proc AS routine
            WHERE routine.oid =
                'ofarm_security.append_pretenant_failure('
                'uuid, text, bytea, text, integer)'::pg_catalog.regprocedure
            """
        ).fetchone()
        clock_marker = "    v_now := pg_catalog.clock_timestamp();"
        assert original_source.count(clock_marker) == 1
        _replace_pretenant_append_source(
            admin,
            original_source.replace(
                clock_marker,
                "    v_now := pg_catalog.current_setting('ofarm.test_now')::\n"
                "        pg_catalog.timestamptz;",
            ),
        )

    try:
        yield observed_at
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            _replace_pretenant_append_source(admin, original_source)


def _concurrent_append_at(
    state: dict[str, object],
    role: str,
    barrier: Barrier,
    arguments: tuple[object, ...],
    observed_at: datetime,
    application_name: str,
) -> tuple[str, object]:
    dsn = psycopg.conninfo.make_conninfo(
        _role_dsn(state, role), application_name=application_name
    )
    with psycopg.connect(dsn, autocommit=True) as producer:
        producer.execute(
            "SELECT pg_catalog.set_config('ofarm.test_now', %s, false)",
            (observed_at.isoformat(),),
        )
        barrier.wait(timeout=15)
        try:
            row = producer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, %s, %s, %s, %s
                )
                """,
                arguments,
            ).fetchone()
        except psycopg.Error as exc:
            return ("error", exc.diag.message_primary)
    return ("ok", row)


def _run_coordinated_adjacent_bucket_appends(
    state: dict[str, object],
    role: str,
    calls: tuple[tuple[tuple[object, ...], datetime], ...],
) -> list[tuple[str, object]]:
    assert len(calls) == 2
    token = uuid4().hex
    application_names = [
        f"a174_adjacent_{token}_{index}" for index in range(len(calls))
    ]
    barrier = Barrier(len(calls))
    with psycopg.connect(state["target_admin_dsn"]) as locker:
        locker.execute(
            """
            SELECT singleton
            FROM ofarm_security._test_append_barrier
            WHERE singleton
            FOR UPDATE
            """
        ).fetchone()
        with ThreadPoolExecutor(max_workers=len(calls)) as executor:
            futures = [
                executor.submit(
                    _concurrent_append_at,
                    state,
                    role,
                    barrier,
                    arguments,
                    observed_at,
                    application_names[index],
                )
                for index, (arguments, observed_at) in enumerate(calls)
            ]
            try:
                assert _wait_for_lock_waiters(state, application_names)
            finally:
                locker.commit()
            results = [future.result(timeout=30) for future in futures]
    return results


def _wait_for_lock_waiters(
    state: dict[str, object], application_names: list[str]
) -> bool:
    deadline = monotonic() + 15
    with psycopg.connect(
        state["target_admin_dsn"], autocommit=True
    ) as observer:
        while monotonic() < deadline:
            blocked_count = observer.execute(
                """
                SELECT pg_catalog.count(*)
                FROM pg_catalog.pg_stat_activity
                WHERE application_name = ANY(%s::pg_catalog.text[])
                  AND state = 'active'
                  AND wait_event_type = 'Lock'
                """,
                (application_names,),
            ).fetchone()[0]
            if blocked_count == len(application_names):
                return True
            sleep(0.01)
    return False


def _run_ordered_accepted_then_overflow_retry(
    state: dict[str, object],
    role: str,
    arguments: tuple[object, ...],
    accepted_at: datetime,
    overflow_at: datetime,
) -> list[tuple[str, object]]:
    token = uuid4().hex
    application_names = [
        f"a174_split_{token}_{index}" for index in range(2)
    ]

    with psycopg.connect(state["target_admin_dsn"]) as locker:
        locker.execute(
            """
            SELECT singleton
            FROM ofarm_security._test_append_barrier
            WHERE singleton
            FOR UPDATE
            """
        ).fetchone()
        with ThreadPoolExecutor(max_workers=2) as executor:
            accepted = executor.submit(
                _concurrent_append_at,
                state,
                role,
                Barrier(1),
                arguments,
                accepted_at,
                application_names[0],
            )
            assert _wait_for_lock_waiters(state, application_names[:1])
            overflow_retry = executor.submit(
                _concurrent_append_at,
                state,
                role,
                Barrier(1),
                arguments,
                overflow_at,
                application_names[1],
            )
            try:
                assert _wait_for_lock_waiters(state, application_names)
            finally:
                locker.commit()
            return [
                accepted.result(timeout=30),
                overflow_retry.result(timeout=30),
            ]


def _assert_adjacent_bucket_event_identity_serialization(
    state: dict[str, object],
) -> None:
    role = "ofarm_security_authentication_producer_login"
    producer_name = "AUTHENTICATION_BOUNDARY_V1"
    component = "AUTHENTICATION"
    base_bucket = datetime(2040, 1, 1, tzinfo=timezone.utc)
    event_ids = (uuid4(), uuid4(), uuid4(), uuid4())
    bucket_starts = tuple(
        base_bucket + timedelta(minutes=offset) for offset in range(8)
    )
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        original_source = admin.execute(
            """
            SELECT routine.prosrc
            FROM pg_catalog.pg_proc AS routine
            WHERE routine.oid =
                'ofarm_security.append_pretenant_failure('
                'uuid, text, bytea, text, integer)'::pg_catalog.regprocedure
            """
        ).fetchone()[0]
        clock_marker = "    v_now := pg_catalog.clock_timestamp();"
        quota_marker = "    IF v_bucket.accepted_event_count < 1024 THEN"
        assert original_source.count(clock_marker) == 1
        assert original_source.count(quota_marker) == 1
        test_source = original_source.replace(
            clock_marker,
            "    v_now := pg_catalog.current_setting('ofarm.test_now')::\n"
            "        pg_catalog.timestamptz;",
        ).replace(
            quota_marker,
            "    PERFORM singleton\n"
            "    FROM ofarm_security._test_append_barrier\n"
            "    WHERE singleton\n"
            "    FOR SHARE;\n\n"
            f"{quota_marker}",
        )
        admin.execute(
            """
            CREATE TABLE ofarm_security._test_append_barrier (
                singleton pg_catalog.bool PRIMARY KEY CHECK (singleton)
            )
            """
        )
        admin.execute(
            "ALTER TABLE ofarm_security._test_append_barrier "
            "OWNER TO ofarm_security_audit_owner"
        )
        admin.execute(
            "INSERT INTO ofarm_security._test_append_barrier VALUES (true)"
        )
        admin.execute(
            """
            INSERT INTO ofarm_security.operational_security_quota_bucket (
                producer, component, bucket_start
            )
            SELECT %s, %s, bucket_start
            FROM pg_catalog.unnest(%s::pg_catalog.timestamptz[])
                AS bucket(bucket_start)
            """,
            (producer_name, component, list(bucket_starts)),
        )
        admin.execute(
            """
            UPDATE ofarm_security.operational_security_quota_bucket
            SET accepted_event_count = 1024
            WHERE producer = %s
              AND component = %s
              AND bucket_start = ANY(%s::pg_catalog.timestamptz[])
            """,
            (producer_name, component, [bucket_starts[5], bucket_starts[6]]),
        )
        _replace_pretenant_append_source(admin, test_source)

    try:
        exact_arguments = (
            event_ids[0],
            "CREDENTIAL_MISSING",
            bytes.fromhex("41" * 32),
            "OFARM_PRETENANT_CORRELATION_V1",
            1,
        )
        exact_results = _run_coordinated_adjacent_bucket_appends(
            state,
            role,
            (
                (exact_arguments, bucket_starts[0] + timedelta(seconds=30)),
                (exact_arguments, bucket_starts[1] + timedelta(seconds=30)),
            ),
        )
        assert [result[0] for result in exact_results] == ["ok", "ok"]
        assert exact_results[0][1] == exact_results[1][1]
        assert exact_results[0][1][0] == event_ids[0]
        assert exact_results[0][1][3:] == (True, None, False)

        mismatch_common = (
            bytes.fromhex("42" * 32),
            "OFARM_PRETENANT_CORRELATION_V1",
            1,
        )
        mismatch_results = _run_coordinated_adjacent_bucket_appends(
            state,
            role,
            (
                (
                    (event_ids[1], "CREDENTIAL_MISSING", *mismatch_common),
                    bucket_starts[2] + timedelta(seconds=30),
                ),
                (
                    (event_ids[1], "VERIFIER_UNAVAILABLE", *mismatch_common),
                    bucket_starts[3] + timedelta(seconds=30),
                ),
            ),
        )
        assert sorted(result[0] for result in mismatch_results) == [
            "error", "ok",
        ]
        assert [
            result[1] for result in mismatch_results if result[0] == "error"
        ] == ["event identity was already used with different input"]

        accepted_overflow_arguments = (
            event_ids[2],
            "CREDENTIAL_MISSING",
            bytes.fromhex("43" * 32),
            "OFARM_PRETENANT_CORRELATION_V1",
            1,
        )
        accepted_overflow_results = _run_ordered_accepted_then_overflow_retry(
            state,
            role,
            accepted_overflow_arguments,
            bucket_starts[4] + timedelta(seconds=30),
            bucket_starts[5] + timedelta(seconds=30),
        )
        assert [result[0] for result in accepted_overflow_results] == [
            "ok", "ok",
        ]
        assert accepted_overflow_results[0][1] == \
            accepted_overflow_results[1][1]
        assert accepted_overflow_results[0][1][0] == event_ids[2]
        assert accepted_overflow_results[0][1][3:] == (True, None, False)

        overflow_accepted_arguments = (
            event_ids[3],
            "CREDENTIAL_MISSING",
            bytes.fromhex("44" * 32),
            "OFARM_PRETENANT_CORRELATION_V1",
            1,
        )
        first_overflow = _concurrent_append_at(
            state,
            role,
            Barrier(1),
            overflow_accepted_arguments,
            bucket_starts[6] + timedelta(seconds=30),
            f"a174_overflow_receipt_{uuid4().hex}_0",
        )
        overflow_retry = _concurrent_append_at(
            state,
            role,
            Barrier(1),
            overflow_accepted_arguments,
            bucket_starts[7] + timedelta(seconds=30),
            f"a174_overflow_receipt_{uuid4().hex}_1",
        )
        assert first_overflow == overflow_retry
        assert first_overflow[0] == "ok"
        assert first_overflow[1] == (
            None, None, None, False, bucket_starts[6], False,
        )
        overflow_mismatch = _concurrent_append_at(
            state,
            role,
            Barrier(1),
            (
                event_ids[3],
                "VERIFIER_UNAVAILABLE",
                bytes.fromhex("44" * 32),
                "OFARM_PRETENANT_CORRELATION_V1",
                1,
            ),
            bucket_starts[7] + timedelta(seconds=30),
            f"a174_overflow_receipt_{uuid4().hex}_2",
        )
        assert overflow_mismatch == (
            "error", "event identity was already used with different input",
        )

        with psycopg.connect(state["target_admin_dsn"]) as admin:
            event_rows = admin.execute(
                """
                SELECT event_id, reason
                FROM ofarm_security.operational_security_event
                WHERE event_id = ANY(%s::pg_catalog.uuid[])
                ORDER BY event_id
                """,
                (list(event_ids),),
            ).fetchall()
            quota_rows = admin.execute(
                """
                SELECT bucket_start, accepted_event_count,
                       overflow_event_count, overflow_started_at
                FROM ofarm_security.operational_security_quota_bucket
                WHERE producer = %s
                  AND component = %s
                  AND bucket_start = ANY(%s::pg_catalog.timestamptz[])
                ORDER BY bucket_start
                """,
                (producer_name, component, list(bucket_starts)),
            ).fetchall()
            receipt = admin.execute(
                """
                SELECT event_id, bucket_start
                FROM ofarm_security.
                    operational_security_overflow_identity_receipt
                WHERE event_id = %s
                """,
                (event_ids[3],),
            ).fetchone()
        assert {row[0] for row in event_rows} == set(event_ids[:3])
        assert len(event_rows) == 3
        reasons_by_id = dict(event_rows)
        assert reasons_by_id[event_ids[0]] == "CREDENTIAL_MISSING"
        assert reasons_by_id[event_ids[1]] in {
            "CREDENTIAL_MISSING", "VERIFIER_UNAVAILABLE",
        }
        assert reasons_by_id[event_ids[2]] == "CREDENTIAL_MISSING"
        assert len(quota_rows) == 8
        assert sorted(row[1] for row in quota_rows[0:2]) == [0, 1]
        assert sorted(row[1] for row in quota_rows[2:4]) == [0, 1]
        assert quota_rows[4][1:] == (1, 0, None)
        assert quota_rows[5][1:] == (1024, 0, None)
        assert quota_rows[6][1:3] == (1024, 1)
        assert quota_rows[6][3] is not None
        assert quota_rows[7][1:] == (0, 0, None)
        assert all(row[2] == 0 for row in quota_rows[:6])
        assert all(row[3] is None for row in quota_rows[:6])
        assert receipt == (event_ids[3], bucket_starts[6])
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            _replace_pretenant_append_source(admin, original_source)
            admin.execute(
                """
                DELETE FROM ofarm_security.operational_security_event
                WHERE event_id = ANY(%s::pg_catalog.uuid[])
                """,
                (list(event_ids),),
            )
            admin.execute(
                """
                DELETE FROM ofarm_security.operational_security_quota_bucket
                WHERE producer = %s
                  AND component = %s
                  AND bucket_start = ANY(%s::pg_catalog.timestamptz[])
                """,
                (producer_name, component, list(bucket_starts)),
            )
            admin.execute(
                """
                UPDATE ofarm_security.
                    operational_security_overflow_identity_receipt
                SET event_id = NULL,
                    append_input_fingerprint = NULL,
                    bucket_start = NULL,
                    purge_after = NULL
                WHERE event_id = ANY(%s::pg_catalog.uuid[])
                """,
                (list(event_ids),),
            )
            admin.execute("DROP TABLE ofarm_security._test_append_barrier")


def _assert_repeatable_read_append_refusal(
    state: dict[str, object], first_outcome: str
) -> None:
    assert first_outcome in {"accepted", "overflow"}
    role = "ofarm_security_authentication_producer_login"
    producer_name = "AUTHENTICATION_BOUNDARY_V1"
    component = "AUTHENTICATION"
    event_id = uuid4()
    arguments = (
        event_id,
        "CREDENTIAL_MISSING",
        bytes.fromhex("45" * 32),
        "OFARM_PRETENANT_CORRELATION_V1",
        1,
    )
    _reset_quota_state(state, producer_name, component)

    try:
        with _controlled_pretenant_clock(state) as first_at:
            first_bucket = first_at.replace(second=0, microsecond=0)
            second_at = first_at + timedelta(minutes=1)
            second_bucket = first_bucket + timedelta(minutes=1)
            full_bucket = (
                first_bucket if first_outcome == "overflow" else second_bucket
            )
            with psycopg.connect(
                state["target_admin_dsn"], autocommit=True
            ) as admin:
                admin.execute(
                    """
                    INSERT INTO
                        ofarm_security.operational_security_quota_bucket (
                            producer, component, bucket_start,
                            accepted_event_count
                        )
                    VALUES (%s, %s, %s, 1024)
                    """,
                    (producer_name, component, full_bucket),
                )

            with psycopg.connect(_role_dsn(state, role)) as stale_producer:
                stale_producer.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"
                )
                frozen_snapshot = stale_producer.execute(
                    "SELECT pg_catalog.pg_current_snapshot()"
                ).fetchone()[0]
                assert frozen_snapshot is not None

                with psycopg.connect(
                    _role_dsn(state, role), autocommit=True
                ) as first_producer:
                    first_producer.execute(
                        "SELECT pg_catalog.set_config('ofarm.test_now', %s, false)",
                        (first_at.isoformat(),),
                    )
                    first_result = first_producer.execute(
                        """
                        SELECT *
                        FROM ofarm_security.append_pretenant_failure(
                            %s, %s, %s, %s, %s
                        )
                        """,
                        arguments,
                    ).fetchone()

                stale_producer.execute(
                    "SELECT pg_catalog.set_config('ofarm.test_now', %s, false)",
                    (second_at.isoformat(),),
                )
                with pytest.raises(
                    psycopg.Error,
                    match="pre-tenant append requires READ COMMITTED",
                ) as refused:
                    stale_producer.execute(
                        """
                        SELECT *
                        FROM ofarm_security.append_pretenant_failure(
                            %s, %s, %s, %s, %s
                        )
                        """,
                        arguments,
                    )
                assert refused.value.sqlstate == "25001"
                stale_producer.rollback()

        with psycopg.connect(state["target_admin_dsn"]) as admin:
            event_count = admin.execute(
                """
                SELECT pg_catalog.count(*)
                FROM ofarm_security.operational_security_event
                WHERE event_id = %s
                """,
                (event_id,),
            ).fetchone()[0]
            receipt_count = admin.execute(
                """
                SELECT pg_catalog.count(*)
                FROM ofarm_security.
                    operational_security_overflow_identity_receipt
                WHERE event_id = %s
                """,
                (event_id,),
            ).fetchone()[0]
            quota_rows = admin.execute(
                """
                SELECT bucket_start, accepted_event_count,
                       overflow_event_count, count_unknown
                FROM ofarm_security.operational_security_quota_bucket
                WHERE producer = %s
                  AND component = %s
                  AND bucket_start IN (%s, %s)
                ORDER BY bucket_start
                """,
                (producer_name, component, first_bucket, second_bucket),
            ).fetchall()

        if first_outcome == "accepted":
            assert first_result[0] == event_id
            assert first_result[3:] == (True, None, False)
            assert event_count == 1
            assert receipt_count == 0
            assert quota_rows == [
                (first_bucket, 1, 0, False),
                (second_bucket, 1024, 0, False),
            ]
        else:
            assert first_result == (
                None, None, None, False, first_bucket, False,
            )
            assert event_count == 0
            assert receipt_count == 1
            assert quota_rows == [(first_bucket, 1024, 1, False)]
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                DELETE FROM ofarm_security.operational_security_event
                WHERE event_id = %s
                """,
                (event_id,),
            )
        _reset_quota_state(state, producer_name, component)


@pytest.mark.parametrize("first_outcome", ("accepted", "overflow"))
def test_pretenant_append_refuses_repeatable_read_stale_snapshot(
    migrated_audit_service, first_outcome,
):
    _assert_repeatable_read_append_refusal(
        migrated_audit_service, first_outcome
    )


def test_concurrent_same_event_retry_matches_and_mismatch_refuses_once(
    migrated_audit_service,
):
    state = migrated_audit_service
    role = "ofarm_security_authentication_producer_login"
    exact_id = uuid4()
    exact_arguments = (
        exact_id,
        "CREDENTIAL_MISSING",
        bytes(range(32)),
        "OFARM_PRETENANT_CORRELATION_V1",
        1,
    )
    exact_results = _run_concurrent_appends(
        state, role, (exact_arguments, exact_arguments)
    )
    assert [result[0] for result in exact_results] == ["ok", "ok"]
    assert exact_results[0][1] == exact_results[1][1]
    assert exact_results[0][1][0] == exact_id
    assert exact_results[0][1][3:] == (True, None, False)

    mismatch_id = uuid4()
    common = (
        bytes(reversed(range(32))),
        "OFARM_PRETENANT_CORRELATION_V1",
        1,
    )
    mismatch_results = _run_concurrent_appends(
        state,
        role,
        (
            (mismatch_id, "CREDENTIAL_MISSING", *common),
            (mismatch_id, "VERIFIER_UNAVAILABLE", *common),
        ),
    )
    assert sorted(result[0] for result in mismatch_results) == ["error", "ok"]
    assert [result[1] for result in mismatch_results if result[0] == "error"] == [
        "event identity was already used with different input"
    ]

    with psycopg.connect(state["target_admin_dsn"]) as admin:
        rows = admin.execute(
            """
            SELECT event_id, reason
            FROM ofarm_security.operational_security_event
            WHERE event_id IN (%s, %s)
            ORDER BY event_id
            """,
            (exact_id, mismatch_id),
        ).fetchall()
    assert len(rows) == 2
    assert {row[0] for row in rows} == {exact_id, mismatch_id}
    assert rows[0][1] in {"CREDENTIAL_MISSING", "VERIFIER_UNAVAILABLE"}
    assert rows[1][1] in {"CREDENTIAL_MISSING", "VERIFIER_UNAVAILABLE"}
    _assert_adjacent_bucket_event_identity_serialization(state)


def test_bounded_reader_requires_an_equal_committed_access_intent(
    migrated_audit_service,
):
    state = migrated_audit_service
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_reader_login"),
        autocommit=True,
    ) as reader:
        with pytest.raises(psycopg.Error):
            reader.execute(
                """
                SELECT * FROM ofarm_security.query_operational_security_events(
                    %s, NULL, NULL, 10, 100000
                )
                """,
                (uuid4(),),
            )

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        access = control.execute(
            """
            SELECT * FROM ofarm_security.commit_audit_access_intent(
                'OPERATIONAL_DIAGNOSTIC_QUERY_V1', %s,
                NULL, NULL, 10, 100000
            )
            """,
            (QUERY_IDENTITY,),
        ).fetchone()

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_reader_login"),
        autocommit=True,
    ) as reader:
        rows = reader.execute(
            """
            SELECT * FROM ofarm_security.query_operational_security_events(
                %s, NULL, NULL, 10, 100000
            )
            """,
            (access[0],),
        ).fetchall()
        with pytest.raises(psycopg.Error):
            reader.execute(
                """
                SELECT * FROM ofarm_security.query_operational_security_events(
                    %s, NULL, NULL, 11, 100000
                )
                """,
                (access[0],),
            )
    assert 1 <= len(rows) <= 10
    assert all(row[2] > access[1] for row in rows)


def test_access_clock_mutex_is_released_before_reader_transaction_ends(
    migrated_audit_service,
):
    state = migrated_audit_service
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        access = control.execute(
            """
            SELECT * FROM ofarm_security.commit_audit_access_intent(
                'OPERATIONAL_DIAGNOSTIC_QUERY_V1', %s,
                NULL, NULL, 10, 100000
            )
            """,
            (QUERY_IDENTITY,),
        ).fetchone()

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_reader_login")
    ) as first_reader:
        first_reader.execute("SET transaction_timeout = 0")
        first_reader.execute("SET idle_in_transaction_session_timeout = 0")
        first_reader_pid = first_reader.execute(
            "SELECT pg_catalog.pg_backend_pid()"
        ).fetchone()[0]
        first_rows = first_reader.execute(
            """
            SELECT * FROM ofarm_security.query_operational_security_events(
                %s, NULL, NULL, 10, 100000
            )
            """,
            (access[0],),
        ).fetchall()

        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            assert admin.execute(
                """
                SELECT pg_catalog.count(*)
                FROM pg_catalog.pg_locks
                WHERE pid = %s AND locktype = 'advisory'
                """,
                (first_reader_pid,),
            ).fetchone()[0] == 0

        with psycopg.connect(
            _role_dsn(state, "ofarm_security_audit_reader_login"),
            autocommit=True,
        ) as second_reader:
            second_reader.execute("SET lock_timeout = '1s'")
            second_rows = second_reader.execute(
                """
                SELECT *
                FROM ofarm_security.query_operational_security_events(
                    %s, NULL, NULL, 10, 100000
                )
                """,
                (access[0],),
            ).fetchall()

    assert first_rows == second_rows


def _set_access_clock_high_water(
    state: dict[str, object], observed_at: datetime | None
) -> int:
    with psycopg.connect(
        state["target_admin_dsn"], autocommit=True
    ) as admin:
        high_water = admin.execute(
            """
            SELECT pg_catalog.floor(
                EXTRACT(EPOCH FROM COALESCE(
                    %s::pg_catalog.timestamptz,
                    pg_catalog.clock_timestamp()
                )) * 1000000
            )::pg_catalog.int8
            """,
            (observed_at,),
        ).fetchone()[0]
        admin.execute(
            """
            SELECT pg_catalog.setval(
                'ofarm_security.operational_security_access_clock_high_water'::
                    pg_catalog.regclass,
                %s,
                true
            )
            """,
            (high_water,),
        )
    return high_water


def _assert_access_refuses_twice(
    connection: psycopg.Connection,
    statement: str,
    arguments: tuple[object, ...],
) -> None:
    for _attempt in range(2):
        with pytest.raises(psycopg.Error) as refused:
            connection.execute(statement, arguments).fetchall()
        assert refused.value.sqlstate == "42501"
        assert "expired" in str(refused.value)
        connection.rollback()


def test_access_clock_advance_survives_its_transaction_rollback(
    migrated_audit_service,
):
    state = migrated_audit_service
    _set_access_clock_high_water(
        state, datetime(1970, 1, 1, tzinfo=timezone.utc)
    )
    try:
        with psycopg.connect(state["target_admin_dsn"]) as admin:
            observed = admin.execute(
                """
                SELECT *
                FROM ofarm_security._observe_nonregressing_access_clock()
                """
            ).fetchone()
            assert observed[1] > 0
            assert observed[2] is False
            admin.rollback()

        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            retained = admin.execute(
                """
                SELECT last_value::pg_catalog.int8
                FROM ofarm_security.operational_security_access_clock_high_water
                """
            ).fetchone()[0]
        assert retained == observed[1]
    finally:
        _set_access_clock_high_water(state, None)


def test_expired_access_intent_stays_refused_after_clock_rollback(
    migrated_audit_service,
):
    state = migrated_audit_service
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        access = control.execute(
            """
            SELECT * FROM ofarm_security.commit_audit_access_intent(
                'OPERATIONAL_DIAGNOSTIC_QUERY_V1', %s,
                NULL, NULL, 10, 100000
            )
            """,
            (QUERY_IDENTITY,),
        ).fetchone()

    expiry_microseconds = _set_access_clock_high_water(state, access[2])

    try:
        with psycopg.connect(
            _role_dsn(state, "ofarm_security_audit_reader_login")
        ) as reader:
            _assert_access_refuses_twice(
                reader,
                """
                SELECT *
                FROM ofarm_security.query_operational_security_events(
                    %s, NULL, NULL, 10, 100000
                )
                """,
                (access[0],),
            )

        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            retained_high_water = admin.execute(
                """
                SELECT last_value::pg_catalog.int8
                FROM ofarm_security.operational_security_access_clock_high_water
                """
            ).fetchone()[0]
        assert retained_high_water >= expiry_microseconds
    finally:
        _set_access_clock_high_water(state, None)


def test_expired_break_glass_intent_stays_refused_after_clock_rollback(
    migrated_audit_service,
):
    state = migrated_audit_service
    export_role = "ofarm_security_audit_export_login"
    export_password = "issue-174-export-" + secrets.token_urlsafe(32)
    with psycopg.connect(state["admin_dsn"], autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(export_role), sql.Literal(export_password)
            )
        )
        admin.execute(
            """
            GRANT ofarm_security_audit_export
            TO ofarm_security_audit_export_login
            WITH INHERIT TRUE, SET FALSE, ADMIN FALSE
            """
        )
    try:
        with psycopg.connect(
            _role_dsn(state, "ofarm_security_audit_control_login"),
            autocommit=True,
        ) as control:
            access = control.execute(
                """
                SELECT * FROM ofarm_security.commit_audit_access_intent(
                    'DUAL_APPROVED_BREAK_GLASS_EXPORT_V1',
                    'ofarm_security.export_operational_security_events(uuid, timestamptz, uuid, integer, bigint)',
                    NULL, NULL, 10, 100000
                )
                """
            ).fetchone()

        _set_access_clock_high_water(state, access[2])
        export_dsn = _database_dsn(
            state["admin_dsn"],
            SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
            user=export_role,
            password=export_password,
        )
        with psycopg.connect(export_dsn) as exporter:
            _assert_access_refuses_twice(
                exporter,
                """
                SELECT *
                FROM ofarm_security.export_operational_security_events(
                    %s, NULL, NULL, 10, 100000
                )
                """,
                (access[0],),
            )
    finally:
        _set_access_clock_high_water(state, None)
        with psycopg.connect(state["admin_dsn"], autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP ROLE IF EXISTS {}").format(
                    sql.Identifier(export_role)
                )
            )


def test_bounded_reader_byte_ceiling_is_session_independent(
    migrated_audit_service,
):
    state = migrated_audit_service
    event_ids = (uuid4(), uuid4())
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_authentication_producer_login"),
        autocommit=True,
    ) as producer:
        for event_id in event_ids:
            producer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, 'CREDENTIAL_MISSING', %s,
                    'OFARM_PRETENANT_CORRELATION_V1', 1
                )
                """,
                (event_id, bytes(range(32))),
            )

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        calibration_access = control.execute(
            """
            SELECT * FROM ofarm_security.commit_audit_access_intent(
                'OPERATIONAL_DIAGNOSTIC_QUERY_V1', %s,
                NULL, NULL, 2, 1048576
            )
            """,
            (QUERY_IDENTITY,),
        ).fetchone()

    size_query = """
        SELECT event_id,
               pg_catalog.octet_length(
                   pg_catalog.convert_to(
                       pg_catalog.row_to_json(report)::pg_catalog.text,
                       'UTF8'
                   )
               )
        FROM ofarm_security.query_operational_security_events(
            %s, NULL, NULL, 2, 1048576
        ) AS report
        ORDER BY observed_at DESC, event_id DESC
    """
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_reader_login"),
        autocommit=True,
    ) as reader:
        reader.execute("SET bytea_output = 'hex'")
        reader.execute("SET TimeZone = 'UTC'")
        reader.execute("SET DateStyle = 'ISO, MDY'")
        canonical_sizes = reader.execute(
            size_query, (calibration_access[0],)
        ).fetchall()

        reader.execute("SET bytea_output = 'escape'")
        reader.execute("SET TimeZone = 'Europe/Ljubljana'")
        reader.execute("SET DateStyle = 'SQL, DMY'")
        hostile_sizes = reader.execute(
            size_query, (calibration_access[0],)
        ).fetchall()

    assert [row[0] for row in canonical_sizes] == [
        row[0] for row in hostile_sizes
    ]
    assert set(row[0] for row in canonical_sizes) == set(event_ids)
    canonical_ceiling = sum(row[1] for row in canonical_sizes)
    assert sum(row[1] for row in hostile_sizes) > canonical_ceiling

    with psycopg.connect(state["target_admin_dsn"]) as admin:
        calibration_cursor = admin.execute(
            """
            SELECT observed_at, event_id
            FROM ofarm_security.operational_security_event
            WHERE event_id = %s
            """,
            (calibration_access[0],),
        ).fetchone()
    assert calibration_cursor is not None

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        bounded_access = control.execute(
            """
            SELECT * FROM ofarm_security.commit_audit_access_intent(
                'OPERATIONAL_DIAGNOSTIC_QUERY_V1', %s,
                %s, %s, 2, %s
            )
            """,
            (QUERY_IDENTITY, *calibration_cursor, canonical_ceiling),
        ).fetchone()

    bounded_query = """
        SELECT event_id
        FROM ofarm_security.query_operational_security_events(
            %s, %s, %s, 2, %s
        )
        ORDER BY observed_at DESC, event_id DESC
    """
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_reader_login"),
        autocommit=True,
    ) as reader:
        reader.execute("SET bytea_output = 'escape'")
        reader.execute("SET TimeZone = 'Europe/Ljubljana'")
        reader.execute("SET DateStyle = 'SQL, DMY'")
        hostile_rows = reader.execute(
            bounded_query,
            (bounded_access[0], *calibration_cursor, canonical_ceiling),
        ).fetchall()
        assert reader.execute(
            """
            SELECT current_setting('bytea_output'),
                   current_setting('TimeZone'),
                   current_setting('DateStyle')
            """
        ).fetchone() == ('escape', 'Europe/Ljubljana', 'SQL, DMY')

        reader.execute("SET bytea_output = 'hex'")
        reader.execute("SET TimeZone = 'UTC'")
        reader.execute("SET DateStyle = 'ISO, MDY'")
        canonical_rows = reader.execute(
            bounded_query,
            (bounded_access[0], *calibration_cursor, canonical_ceiling),
        ).fetchall()

    assert hostile_rows == canonical_rows
    assert {row[0] for row in canonical_rows} == set(event_ids)


def test_access_intent_serializes_earlier_and_later_event_writers(
    migrated_audit_service,
):
    state = migrated_audit_service
    earlier_event_id = uuid4()
    later_event_id = uuid4()
    token = uuid4().hex
    control_application = "issue174-cut-control-" + token
    later_application = "issue174-cut-later-" + token
    control_dsn = psycopg.conninfo.make_conninfo(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        application_name=control_application,
    )
    later_dsn = psycopg.conninfo.make_conninfo(
        _role_dsn(state, "ofarm_security_authentication_producer_login"),
        application_name=later_application,
    )
    access_captured = Event()
    release_access = Event()

    def create_access_intent() -> tuple[object, ...]:
        with psycopg.connect(control_dsn) as control:
            control.execute("SET lock_timeout = '10s'")
            access = control.execute(
                """
                SELECT * FROM ofarm_security.commit_audit_access_intent(
                    'OPERATIONAL_DIAGNOSTIC_QUERY_V1', %s,
                    NULL, NULL, 256, 1048576
                )
                """,
                (QUERY_IDENTITY,),
            ).fetchone()
            access_captured.set()
            if not release_access.wait(timeout=10):
                raise AssertionError("access-intent commit was not released")
            control.commit()
            return access

    def append_after_cut() -> tuple[object, ...]:
        with psycopg.connect(later_dsn, autocommit=True) as producer:
            producer.execute("SET lock_timeout = '10s'")
            return producer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, 'CREDENTIAL_MISSING', %s,
                    'OFARM_PRETENANT_CORRELATION_V1', 1
                )
                """,
                (later_event_id, bytes.fromhex("42" * 32)),
            ).fetchone()

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_authentication_producer_login")
    ) as earlier_producer:
        earlier_append = earlier_producer.execute(
            """
            SELECT * FROM ofarm_security.append_pretenant_failure(
                %s, 'CREDENTIAL_MISSING', %s,
                'OFARM_PRETENANT_CORRELATION_V1', 1
            )
            """,
            (earlier_event_id, bytes.fromhex("41" * 32)),
        ).fetchone()
        with ThreadPoolExecutor(max_workers=2) as executor:
            access_future = executor.submit(create_access_intent)
            _wait_for_event_relation_lock(
                state, control_application, "ShareRowExclusiveLock"
            )
            assert not access_future.done()

            earlier_producer.commit()
            assert access_captured.wait(timeout=10)

            later_future = executor.submit(append_after_cut)
            _wait_for_event_relation_lock(
                state, later_application, "RowExclusiveLock"
            )
            assert not later_future.done()

            release_access.set()
            access = access_future.result(timeout=10)
            later_append = later_future.result(timeout=10)

    assert earlier_append[0] == earlier_event_id
    assert later_append[0] == later_event_id
    assert earlier_append[1] <= access[1]
    assert later_append[1] > access[1]

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_reader_login"),
        autocommit=True,
    ) as reader:
        first = reader.execute(
            """
            SELECT * FROM ofarm_security.query_operational_security_events(
                %s, NULL, NULL, 256, 1048576
            )
            """,
            (access[0],),
        ).fetchall()
        reused = reader.execute(
            """
            SELECT * FROM ofarm_security.query_operational_security_events(
                %s, NULL, NULL, 256, 1048576
            )
            """,
            (access[0],),
        ).fetchall()

    assert reused == first
    assert earlier_event_id in {row[0] for row in first}
    assert later_event_id not in {row[0] for row in first}


def test_access_intent_refuses_a_repeatable_read_stale_snapshot(
    migrated_audit_service,
):
    state = migrated_audit_service
    committed_event_id = uuid4()

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        access_count_before = admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_event
            WHERE event_kind = 'AUDIT_ACCESS'
            """
        ).fetchone()[0]

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login")
    ) as control:
        control.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        frozen_snapshot = control.execute(
            "SELECT pg_catalog.pg_current_snapshot()"
        ).fetchone()[0]

        with psycopg.connect(
            _role_dsn(state, "ofarm_security_authentication_producer_login"),
            autocommit=True,
        ) as producer:
            producer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, 'CREDENTIAL_MISSING', %s,
                    'OFARM_PRETENANT_CORRELATION_V1', 1
                )
                """,
                (committed_event_id, bytes.fromhex("42" * 32)),
            ).fetchone()

        with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
            visible_in_frozen_snapshot = admin.execute(
                """
                SELECT pg_catalog.pg_visible_in_snapshot(
                    event_insert_xid, %s::pg_catalog.pg_snapshot
                )
                FROM ofarm_security.operational_security_event
                WHERE event_id = %s
                """,
                (frozen_snapshot, committed_event_id),
            ).fetchone()[0]
        assert visible_in_frozen_snapshot is False

        with pytest.raises(psycopg.Error) as refused:
            control.execute(
                """
                SELECT * FROM ofarm_security.commit_audit_access_intent(
                    'OPERATIONAL_DIAGNOSTIC_QUERY_V1', %s,
                    NULL, NULL, 256, 1048576
                )
                """,
                (QUERY_IDENTITY,),
            )
        assert refused.value.sqlstate == "25001"
        assert "requires READ COMMITTED" in str(refused.value)
        control.rollback()

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        access_count_after = admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_event
            WHERE event_kind = 'AUDIT_ACCESS'
            """
        ).fetchone()[0]
    assert access_count_after == access_count_before


def test_wrong_producer_reasons_and_cross_capabilities_refuse(
    migrated_audit_service,
):
    state = migrated_audit_service
    producer_cases = (
        (
            "ofarm_security_authentication_producer_login",
            "BINDER_REFUSED",
        ),
        (
            "ofarm_security_request_router_producer_login",
            "CREDENTIAL_MISSING",
        ),
    )
    for role, wrong_reason in producer_cases:
        with psycopg.connect(_role_dsn(state, role), autocommit=True) as connection:
            with pytest.raises(psycopg.Error):
                connection.execute(
                    """
                    SELECT ofarm_security.append_pretenant_failure(
                        %s, %s, %s, 'OFARM_PRETENANT_CORRELATION_V1', 1
                    )
                    """,
                    (uuid4(), wrong_reason, bytes(range(32))),
                )

    cross_capability_calls = {
        "ofarm_security_authentication_producer_login": (
            "SELECT ofarm_security.append_audit_gap(now(), now(), 0, true)",
        ),
        "ofarm_security_audit_control_login": (
            "SELECT ofarm_security.append_pretenant_failure("
            "gen_random_uuid(), 'CREDENTIAL_MISSING', decode(repeat('ab',32),'hex'), "
            "'OFARM_PRETENANT_CORRELATION_V1', 1)",
            "SELECT * FROM ofarm_security.query_operational_security_events("
            "gen_random_uuid(), NULL, NULL, 1, 1)",
        ),
        "ofarm_security_audit_reader_login": (
            "SELECT ofarm_security.append_audit_gap(now(), now(), 0, true)",
            "SELECT ofarm_security.purge_expired_operational_security_events()",
        ),
        "ofarm_security_audit_retention_login": (
            "SELECT * FROM ofarm_security.query_operational_security_events("
            "gen_random_uuid(), NULL, NULL, 1, 1)",
        ),
    }
    for role, statements in cross_capability_calls.items():
        with psycopg.connect(_role_dsn(state, role), autocommit=True) as connection:
            for statement in statements:
                with pytest.raises(psycopg.Error):
                    connection.execute(statement)


def test_runtime_roles_have_no_direct_event_table_or_schema_authority(
    migrated_audit_service,
):
    state = migrated_audit_service
    runtime_logins = (
        "ofarm_security_authentication_producer_login",
        "ofarm_security_request_router_producer_login",
        "ofarm_security_audit_control_login",
        "ofarm_security_audit_reader_login",
        "ofarm_security_audit_retention_login",
        "ofarm_security_audit_readiness_login",
    )
    denied_statements = (
        "SELECT * FROM ofarm_security.operational_security_event",
        "SELECT last_value FROM "
        "ofarm_security.operational_security_access_clock_high_water",
        "SELECT pg_catalog.nextval("
        "'ofarm_security.operational_security_access_clock_high_water')",
        "SELECT pg_catalog.pg_advisory_lock(-274079271, -1019032096)",
        "SELECT pg_catalog.pg_advisory_unlock(-274079271, -1019032096)",
        "SELECT ofarm_infrastructure.take_audit_access_clock_lock()",
        "SELECT ofarm_infrastructure.release_audit_access_clock_lock()",
        "INSERT INTO ofarm_security.operational_security_event DEFAULT VALUES",
        "UPDATE ofarm_security.operational_security_event SET reason = reason",
        "DELETE FROM ofarm_security.operational_security_event",
        "TRUNCATE ofarm_security.operational_security_event",
        "CREATE TABLE ofarm_security.untrusted_object (value integer)",
        "SET ROLE ofarm_security_audit_owner",
    )
    for role in runtime_logins:
        with psycopg.connect(_role_dsn(state, role), autocommit=True) as connection:
            for statement in denied_statements:
                with pytest.raises(psycopg.Error):
                    connection.execute(statement)
            with pytest.raises(psycopg.Error):
                with connection.cursor().copy(
                    "COPY ofarm_security.operational_security_event TO STDOUT"
                ) as copy:
                    tuple(copy.rows())

    qualified_large_object_identities = [
        f"pg_catalog.{identity}" for identity in LARGE_OBJECT_ROUTINE_IDENTITIES
    ]
    for role in runtime_logins:
        with psycopg.connect(
            _role_dsn(state, role), autocommit=True
        ) as connection:
            executable_count = connection.execute(
                """
                SELECT pg_catalog.count(*)
                FROM pg_catalog.unnest(%s::pg_catalog.text[])
                    AS routine(identity)
                WHERE pg_catalog.has_function_privilege(
                    current_user, routine.identity, 'EXECUTE'
                )
                """,
                (qualified_large_object_identities,),
            ).fetchone()[0]
            assert executable_count == 0
            with pytest.raises(psycopg.Error):
                connection.execute(
                    "SELECT pg_catalog.lo_from_bytea(0, "
                    "pg_catalog.decode('aa', 'hex'))"
                )
            with pytest.raises(psycopg.Error):
                connection.execute("SELECT pg_catalog.lo_get(1)")


def test_same_login_cannot_observe_peer_activity_surface_while_append_works(
    migrated_audit_service,
):
    state = migrated_audit_service
    role = "ofarm_security_authentication_producer_login"
    peer_application_name = "issue174-audit-peer-" + uuid4().hex
    peer_sql_secret = "issue174_audit_sql_" + uuid4().hex
    event_id = uuid4()
    peer_dsn = psycopg.conninfo.make_conninfo(
        _role_dsn(state, role),
        application_name=peer_application_name,
    )
    reader_dsn = psycopg.conninfo.make_conninfo(
        _role_dsn(state, role),
        application_name="issue174-audit-peer-reader",
    )
    peer_query_started = Event()

    def run_peer_query() -> tuple[object, ...]:
        with psycopg.connect(peer_dsn, autocommit=True) as peer:
            appended = peer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, 'CREDENTIAL_MISSING', %s,
                    'OFARM_PRETENANT_CORRELATION_V1', 1
                )
                """,
                (event_id, bytes(range(32))),
            ).fetchone()
            peer_query_started.set()
            try:
                peer.execute(
                    f"SELECT pg_catalog.pg_sleep(3) /* {peer_sql_secret} */"
                ).fetchone()
            except psycopg.errors.QueryCanceled:
                pass
        return appended

    direct_activity_calls = (
        "SELECT * FROM pg_catalog.pg_stat_get_activity(NULL::integer)",
        "SELECT pg_catalog.pg_stat_get_backend_activity(1)",
        "SELECT pg_catalog.pg_stat_get_backend_activity_start(1)",
        "SELECT pg_catalog.pg_stat_get_backend_client_addr(1)",
        "SELECT pg_catalog.pg_stat_get_backend_client_port(1)",
        "SELECT pg_catalog.pg_stat_get_backend_dbid(1)",
        "SELECT * FROM pg_catalog.pg_stat_get_backend_idset()",
        "SELECT pg_catalog.pg_stat_get_backend_pid(1)",
        "SELECT pg_catalog.pg_stat_get_backend_start(1)",
        "SELECT * FROM pg_catalog.pg_stat_get_backend_subxact(1)",
        "SELECT pg_catalog.pg_stat_get_backend_userid(1)",
        "SELECT pg_catalog.pg_stat_get_backend_wait_event(1)",
        "SELECT pg_catalog.pg_stat_get_backend_wait_event_type(1)",
        "SELECT pg_catalog.pg_stat_get_backend_xact_start(1)",
    )
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            peer_future = executor.submit(run_peer_query)
            assert peer_query_started.wait(timeout=2)
            with psycopg.connect(
                state["target_admin_dsn"], autocommit=True
            ) as admin:
                deadline = monotonic() + 2
                peer_row = None
                while monotonic() < deadline:
                    peer_row = admin.execute(
                        """
                        SELECT application_name, query
                        FROM pg_catalog.pg_stat_activity
                        WHERE application_name = %s
                        """,
                        (peer_application_name,),
                    ).fetchone()
                    if peer_row is not None and peer_sql_secret in peer_row[1]:
                        break
                    sleep(0.025)
                assert peer_row is not None
                assert peer_row[0] == peer_application_name
                assert peer_sql_secret in peer_row[1]

            with psycopg.connect(reader_dsn, autocommit=True) as reader:
                assert reader.execute(
                    """
                    SELECT pg_catalog.has_table_privilege(
                        current_user,
                        'pg_catalog.pg_stat_activity',
                        'SELECT'
                    )
                    """
                ).fetchone() == (False,)
                routine_privileges = tuple(
                    reader.execute(
                        """
                        SELECT routine.proname::pg_catalog.text || '(' ||
                               pg_catalog.oidvectortypes(
                                   routine.proargtypes
                               ) || ')',
                               pg_catalog.has_function_privilege(
                                   current_user, routine.oid, 'EXECUTE'
                               )
                        FROM pg_catalog.pg_proc AS routine
                        JOIN pg_catalog.pg_namespace AS namespace
                          ON namespace.oid = routine.pronamespace
                        WHERE namespace.nspname = 'pg_catalog'
                          AND pg_catalog.left(
                                  routine.proname::pg_catalog.text, 20
                              ) IN (
                                  'pg_stat_get_activity',
                                  'pg_stat_get_backend_'
                              )
                        ORDER BY (
                            routine.proname::pg_catalog.text || '(' ||
                            pg_catalog.oidvectortypes(routine.proargtypes) || ')'
                        ) COLLATE pg_catalog."C"
                        """
                    )
                )
                assert routine_privileges == tuple(
                    (identity, False)
                    for identity in BACKEND_STATISTICS_ROUTINE_IDENTITIES
                )
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    reader.execute(
                        """
                        SELECT application_name, query
                        FROM pg_catalog.pg_stat_activity
                        WHERE application_name = %s OR query LIKE %s
                        """,
                        (peer_application_name, f"%{peer_sql_secret}%"),
                    )
                for statement in direct_activity_calls:
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        reader.execute(statement)
            appended = peer_future.result(timeout=5)
        assert appended[0] == event_id
        assert appended[3:] == (True, None, False)
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                DELETE FROM ofarm_security.operational_security_event
                WHERE event_id = %s
                """,
                (event_id,),
            )


def _reset_quota_state(
    state: dict[str, object], producer: str, component: str
) -> None:
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            """
            DELETE FROM ofarm_security.operational_security_event
            WHERE event_kind IN ('OVERFLOW_STARTED', 'OVERFLOW_ENDED')
              AND affected_producer = %s
              AND affected_component = %s
            """,
            (producer, component),
        )
        admin.execute(
            """
            DELETE FROM ofarm_security.operational_security_quota_bucket
            WHERE producer = %s
              AND component = %s
            """,
            (producer, component),
        )
        admin.execute(
            """
            DELETE FROM ofarm_security.operational_security_quota_high_water
            WHERE producer = %s
              AND component = %s
            """,
            (producer, component),
        )
        admin.execute(
            """
            UPDATE ofarm_security.operational_security_overflow_identity_receipt
            SET event_id = NULL,
                append_input_fingerprint = NULL,
                bucket_start = NULL,
                purge_after = NULL
            WHERE producer = %s
              AND component = %s
            """,
            (producer, component),
        )


def _bulk_append_in_one_bucket(
    state: dict[str, object], role: str, prefix: str, reason: str
) -> tuple[int, int, int]:
    with _controlled_pretenant_clock(state) as observed_at:
        with psycopg.connect(
            _role_dsn(state, role), autocommit=True
        ) as producer:
            producer.execute(
                "SELECT pg_catalog.set_config('ofarm.test_now', %s, false)",
                (observed_at.isoformat(),),
            )
            return producer.execute(
                """
                WITH calls AS MATERIALIZED (
                    SELECT result.*
                    FROM pg_catalog.generate_series(1, 1025) AS series(value)
                    CROSS JOIN LATERAL ofarm_security.append_pretenant_failure(
                        (%s || pg_catalog.lpad(
                            value::pg_catalog.text, 12, '0'
                        ))::pg_catalog.uuid,
                        %s,
                        pg_catalog.decode(
                            pg_catalog.repeat('cd', 32), 'hex'
                        ),
                        'OFARM_PRETENANT_CORRELATION_V1',
                        1
                    ) AS result
                )
                SELECT pg_catalog.count(*) FILTER (WHERE stored_individually),
                       pg_catalog.count(*) FILTER (
                           WHERE NOT stored_individually
                       ),
                       pg_catalog.count(*) FILTER (
                           WHERE overflow_count_unknown
                       )
                FROM calls
                """,
                (prefix, reason),
            ).fetchone()


def test_identity_lock_stripe_hashes_all_uuid_bytes(migrated_audit_service):
    vectors = (
        UUID("01800000-0000-7000-8000-000000000001"),
        UUID("01800000-0000-7000-8000-000000000002"),
    )
    expected_slots = tuple(
        hashlib.sha256(value.bytes).digest()[0] for value in vectors
    )
    assert vectors[0].bytes[0] == vectors[1].bytes[0]
    assert expected_slots[0] != expected_slots[1]

    with psycopg.connect(
        migrated_audit_service["target_admin_dsn"]
    ) as admin:
        observed_slots = tuple(
            row[0]
            for row in admin.execute(
                """
                SELECT pg_catalog.get_byte(
                    pg_catalog.sha256(pg_catalog.uuid_send(value)), 0
                )
                FROM pg_catalog.unnest(%s::pg_catalog.uuid[]) AS item(value)
                ORDER BY value
                """,
                (list(vectors),),
            ).fetchall()
        )
    assert observed_slots == expected_slots


def test_overflow_receipt_collision_makes_count_unknown(
    migrated_audit_service,
):
    state = migrated_audit_service
    producer_name = "AUTHENTICATION_BOUNDARY_V1"
    component = "AUTHENTICATION"
    role = "ofarm_security_authentication_producer_login"
    event_ids = (
        UUID("01800000-0000-7000-8000-000000000009"),
        UUID("01800000-0000-7000-8000-000000000013"),
    )
    assert hashlib.sha256(event_ids[0].bytes).digest()[0] == \
        hashlib.sha256(event_ids[1].bytes).digest()[0]
    _reset_quota_state(state, producer_name, component)

    try:
        with _controlled_pretenant_clock(state) as observed_at:
            with psycopg.connect(
                state["target_admin_dsn"], autocommit=True
            ) as admin:
                bucket_start = admin.execute(
                    """
                    INSERT INTO ofarm_security.operational_security_quota_bucket (
                        producer, component, bucket_start,
                        accepted_event_count
                    ) VALUES (
                        %s, %s,
                        pg_catalog.date_bin(
                            pg_catalog.make_interval(secs => 60),
                            %s::pg_catalog.timestamptz,
                            '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
                        ),
                        1024
                    )
                    RETURNING bucket_start
                    """,
                    (producer_name, component, observed_at),
                ).fetchone()[0]

            common = (
                "CREDENTIAL_MISSING",
                bytes.fromhex("ef" * 32),
                "OFARM_PRETENANT_CORRELATION_V1",
                1,
            )
            first = _concurrent_append_at(
                state, role, Barrier(1), (event_ids[0], *common),
                observed_at, f"a174_receipt_bound_{uuid4().hex}_0",
            )
            collision = _concurrent_append_at(
                state, role, Barrier(1), (event_ids[1], *common),
                observed_at, f"a174_receipt_bound_{uuid4().hex}_1",
            )
            retry_after_roll = _concurrent_append_at(
                state, role, Barrier(1), (event_ids[0], *common),
                observed_at + timedelta(minutes=1),
                f"a174_receipt_bound_{uuid4().hex}_2",
            )

        assert first == (
            "ok", (None, None, None, False, bucket_start, False),
        )
        assert collision == (
            "ok", (None, None, None, False, bucket_start, True),
        )
        assert retry_after_roll[0] == "ok"
        assert retry_after_roll[1][0] == event_ids[0]
        assert retry_after_roll[1][3:] == (True, None, False)

        with psycopg.connect(state["target_admin_dsn"]) as admin:
            old_bucket = admin.execute(
                """
                SELECT accepted_event_count, overflow_event_count,
                       count_unknown
                FROM ofarm_security.operational_security_quota_bucket
                WHERE producer = %s
                  AND component = %s
                  AND bucket_start = %s
                """,
                (producer_name, component, bucket_start),
            ).fetchone()
            retained_receipts = admin.execute(
                """
                SELECT pg_catalog.count(*)
                FROM ofarm_security.
                    operational_security_overflow_identity_receipt
                WHERE event_id = ANY(%s::pg_catalog.uuid[])
                """,
                (list(event_ids),),
            ).fetchone()[0]
        assert old_bucket == (1024, 1, True)
        assert retained_receipts == 0
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                DELETE FROM ofarm_security.operational_security_event
                WHERE event_id = ANY(%s::pg_catalog.uuid[])
                """,
                (list(event_ids),),
            )
        _reset_quota_state(state, producer_name, component)


def test_concurrent_writes_at_quota_boundary_store_one_and_overflow_one(
    migrated_audit_service,
):
    state = migrated_audit_service
    producer_name = "REQUEST_ROUTER_BOUNDARY_V1"
    component = "REQUEST_ROUTER"
    _reset_quota_state(state, producer_name, component)
    with _controlled_pretenant_clock(state) as observed_at:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            bucket_start = admin.execute(
                """
                INSERT INTO ofarm_security.operational_security_quota_bucket (
                    producer, component, bucket_start, accepted_event_count
                ) VALUES (
                    %s,
                    %s,
                    pg_catalog.date_bin(
                        pg_catalog.make_interval(secs => 60),
                        %s::pg_catalog.timestamptz,
                        '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
                    ),
                    1023
                )
                RETURNING bucket_start
                """,
                (producer_name, component, observed_at),
            ).fetchone()[0]

        event_ids = (uuid4(), uuid4())
        common = (
            "BINDER_REFUSED",
            bytes.fromhex("ab" * 32),
            "OFARM_PRETENANT_CORRELATION_V1",
            1,
        )
        results = _run_concurrent_appends(
            state,
            "ofarm_security_request_router_producer_login",
            tuple((event_id, *common) for event_id in event_ids),
            observed_at,
        )
    assert [result[0] for result in results] == ["ok", "ok"]
    rows = [result[1] for result in results]
    assert sorted(row[3] for row in rows) == [False, True]
    assert [row[4] for row in rows if not row[3]] == [bucket_start]

    with psycopg.connect(state["target_admin_dsn"]) as admin:
        bucket = admin.execute(
            """
            SELECT accepted_event_count, overflow_event_count,
                   overflow_started_at IS NOT NULL, count_unknown
            FROM ofarm_security.operational_security_quota_bucket
            WHERE producer = %s AND component = %s AND bucket_start = %s
            """,
            (producer_name, component, bucket_start),
        ).fetchone()
        individually_stored = admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_event
            WHERE event_id IN (%s, %s)
            """,
            event_ids,
        ).fetchone()[0]
        overflow_markers = admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_event
            WHERE event_kind = 'OVERFLOW_STARTED'
              AND affected_producer = %s
              AND affected_component = %s
              AND interval_start = %s
            """,
            (producer_name, component, bucket_start),
        ).fetchone()[0]
    assert bucket == (1024, 1, True, False)
    assert individually_stored == 1
    assert overflow_markers == 1


def test_quota_overflow_is_explicit_bounded_and_count_unknown_closes_once(
    migrated_audit_service,
):
    state = migrated_audit_service
    producer_name = "REQUEST_ROUTER_BOUNDARY_V1"
    component = "REQUEST_ROUTER"
    _reset_quota_state(state, producer_name, component)

    counts = _bulk_append_in_one_bucket(
        state,
        "ofarm_security_request_router_producer_login",
        "a1740000-0000-4000-8000-",
        "BINDER_REFUSED",
    )
    assert counts == (1024, 1, 0)

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        current = admin.execute(
            """
            SELECT bucket_start, accepted_event_count, overflow_event_count,
                   overflow_started_at IS NOT NULL, count_unknown
            FROM ofarm_security.operational_security_quota_bucket
            WHERE producer = %s AND component = %s
            """,
            (producer_name, component),
        ).fetchone()
        individual_count = admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_event
            WHERE producer = %s
              AND component = %s
              AND event_kind = 'PRE_TENANT_FAILURE'
              AND event_id::pg_catalog.text LIKE 'a1740000-%%'
            """,
            (producer_name, component),
        ).fetchone()[0]
        last_id_present = admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_event
            WHERE event_id = 'a1740000-0000-4000-8000-000000001025'::
                pg_catalog.uuid
            """
        ).fetchone()[0]
        overflow_receipt_present = admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_overflow_identity_receipt
            WHERE event_id = 'a1740000-0000-4000-8000-000000001025'::
                pg_catalog.uuid
            """
        ).fetchone()[0]
        start_count = admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_event
            WHERE event_kind = 'OVERFLOW_STARTED'
              AND affected_producer = %s
              AND affected_component = %s
              AND interval_start = %s
            """,
            (producer_name, component, current[0]),
        ).fetchone()[0]
    assert current[1:] == (1024, 1, True, False)
    assert individual_count == 1024
    assert last_id_present == 0
    assert overflow_receipt_present == 1
    assert start_count == 1

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        control.execute(
            "SELECT ofarm_security.mark_overflow_count_unknown(%s, %s, %s)",
            (producer_name, component, current[0]),
        )
        control.execute(
            "SELECT ofarm_security.mark_overflow_count_unknown(%s, %s, %s)",
            (producer_name, component, current[0]),
        )
        with pytest.raises(psycopg.Error):
            control.execute(
                "SELECT ofarm_security.close_overflow_bucket(%s, %s, %s)",
                (producer_name, component, current[0]),
            )

    with psycopg.connect(state["target_admin_dsn"]) as admin:
        assert admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_overflow_identity_receipt
            WHERE event_id = 'a1740000-0000-4000-8000-000000001025'::
                pg_catalog.uuid
            """
        ).fetchone()[0] == 0

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        old_bucket = admin.execute(
            """
            SELECT pg_catalog.date_bin(
                pg_catalog.make_interval(secs => 60),
                pg_catalog.clock_timestamp(),
                '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
            ) - pg_catalog.make_interval(secs => 120)
            """
        ).fetchone()[0]
        admin.execute(
            """
            SELECT ofarm_security._insert_maintenance_event(
                'OVERFLOW_STARTED', 'AUDIT_CONTROL',
                NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                NULL, NULL, %s, %s, NULL, false, %s, %s, NULL
            )
            """,
            (
                old_bucket,
                old_bucket + timedelta(minutes=1),
                "AUTHENTICATION_BOUNDARY_V1",
                "AUTHENTICATION",
            ),
        )
        admin.execute(
            """
            INSERT INTO ofarm_security.operational_security_quota_bucket (
                producer, component, bucket_start, accepted_event_count,
                overflow_event_count, overflow_started_at, count_unknown
            ) VALUES (%s, %s, %s, 1024, 9, %s, false)
            """,
            (
                "AUTHENTICATION_BOUNDARY_V1",
                "AUTHENTICATION",
                old_bucket,
                old_bucket,
            ),
        )

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        control.execute(
            "SELECT ofarm_security.mark_overflow_count_unknown(%s, %s, %s)",
            ("AUTHENTICATION_BOUNDARY_V1", "AUTHENTICATION", old_bucket),
        )
        first_close = control.execute(
            """
            SELECT * FROM ofarm_security.close_overflow_bucket(%s, %s, %s)
            """,
            ("AUTHENTICATION_BOUNDARY_V1", "AUTHENTICATION", old_bucket),
        ).fetchone()
        retry_close = control.execute(
            """
            SELECT * FROM ofarm_security.close_overflow_bucket(%s, %s, %s)
            """,
            ("AUTHENTICATION_BOUNDARY_V1", "AUTHENTICATION", old_bucket),
        ).fetchone()
    assert first_close == retry_close
    with psycopg.connect(state["target_admin_dsn"]) as admin:
        ended = admin.execute(
            """
            SELECT interval_event_count, interval_count_unknown
            FROM ofarm_security.operational_security_event
            WHERE event_id = %s
            """,
            (first_close[0],),
        ).fetchone()
        bucket_exists = admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_quota_bucket
            WHERE producer = 'AUTHENTICATION_BOUNDARY_V1'
              AND component = 'AUTHENTICATION'
              AND bucket_start = %s
            """,
            (old_bucket,),
        ).fetchone()[0]
    assert ended == (None, True)
    assert bucket_exists == 0


def test_exact_overflow_receipt_survives_close_through_marker_retention(
    migrated_audit_service,
):
    state = migrated_audit_service
    producer_name = "AUTHENTICATION_BOUNDARY_V1"
    component = "AUTHENTICATION"
    event_id = uuid4()
    reason = "CREDENTIAL_MISSING"
    hmac_value = bytes.fromhex("a9" * 32)
    _reset_quota_state(state, producer_name, component)

    try:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            bucket_start = admin.execute(
                """
                SELECT pg_catalog.date_bin(
                    pg_catalog.make_interval(secs => 60),
                    pg_catalog.clock_timestamp(),
                    '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
                ) - pg_catalog.make_interval(secs => 120)
                """
            ).fetchone()[0]
            overflow_started_at = admin.execute(
                """
                SELECT observed_at
                FROM ofarm_security._insert_maintenance_event(
                    'OVERFLOW_STARTED', 'AUDIT_CONTROL',
                    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    NULL, NULL, %s, %s, NULL, false, %s, %s, NULL
                )
                """,
                (
                    bucket_start,
                    bucket_start + timedelta(minutes=1),
                    producer_name,
                    component,
                ),
            ).fetchone()[0]
            admin.execute(
                """
                INSERT INTO ofarm_security.operational_security_quota_bucket (
                    producer, component, bucket_start, accepted_event_count,
                    overflow_event_count, overflow_started_at
                ) VALUES (%s, %s, %s, 1024, 1, %s)
                """,
                (
                    producer_name,
                    component,
                    bucket_start,
                    overflow_started_at,
                ),
            )
            admin.execute(
                """
                UPDATE ofarm_security.
                    operational_security_overflow_identity_receipt
                SET event_id = %s,
                    append_input_fingerprint =
                        ofarm_security._pretenant_event_fingerprint(
                            %s, %s, %s, %s,
                            'OFARM_PRETENANT_CORRELATION_V1', 1, %s
                        ),
                    bucket_start = %s,
                    purge_after = 'infinity'::pg_catalog.timestamptz
                WHERE producer = %s
                  AND component = %s
                  AND lock_slot = pg_catalog.get_byte(
                      pg_catalog.sha256(pg_catalog.uuid_send(%s)), 0
                  )
                """,
                (
                    event_id,
                    event_id,
                    producer_name,
                    component,
                    reason,
                    hmac_value,
                    bucket_start,
                    producer_name,
                    component,
                    event_id,
                ),
            )

        with psycopg.connect(
            _role_dsn(state, "ofarm_security_audit_control_login"),
            autocommit=True,
        ) as control:
            closed = control.execute(
                """
                SELECT *
                FROM ofarm_security.close_overflow_bucket(%s, %s, %s)
                """,
                (producer_name, component, bucket_start),
            ).fetchone()

        with psycopg.connect(
            _role_dsn(state, "ofarm_security_authentication_producer_login"),
            autocommit=True,
        ) as producer:
            retry = producer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, %s, %s, 'OFARM_PRETENANT_CORRELATION_V1', 1
                )
                """,
                (event_id, reason, hmac_value),
            ).fetchone()

        with psycopg.connect(state["target_admin_dsn"]) as admin:
            receipt_and_marker = admin.execute(
                """
                SELECT receipt.bucket_start, receipt.purge_after,
                       marker.purge_after
                FROM ofarm_security.
                    operational_security_overflow_identity_receipt AS receipt
                JOIN ofarm_security.operational_security_event AS marker
                  ON marker.event_id = %s
                WHERE receipt.event_id = %s
                """,
                (closed[0], event_id),
            ).fetchone()
        assert retry == (None, None, None, False, bucket_start, False)
        assert receipt_and_marker is not None
        assert receipt_and_marker[0] == bucket_start
        assert receipt_and_marker[1] == receipt_and_marker[2]
    finally:
        _reset_quota_state(state, producer_name, component)


def test_overflow_close_waits_for_old_bucket_append_and_cannot_reopen(
    migrated_audit_service,
):
    state = migrated_audit_service
    producer_name = "AUTHENTICATION_BOUNDARY_V1"
    component = "AUTHENTICATION"
    _reset_quota_state(state, producer_name, component)
    event_id = uuid4()
    token = uuid4().hex
    producer_application = "issue174-overflow-append-" + token
    control_application = "issue174-overflow-close-" + token
    producer_dsn = psycopg.conninfo.make_conninfo(
        _role_dsn(state, "ofarm_security_authentication_producer_login"),
        application_name=producer_application,
    )
    control_dsn = psycopg.conninfo.make_conninfo(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        application_name=control_application,
    )

    with psycopg.connect(
        state["target_admin_dsn"], autocommit=True
    ) as admin:
        original_source = admin.execute(
            """
            SELECT routine.prosrc
            FROM pg_catalog.pg_proc AS routine
            WHERE routine.oid =
                'ofarm_security.append_pretenant_failure('
                'uuid, text, bytea, text, integer)'::pg_catalog.regprocedure
            """
        ).fetchone()[0]
        clock_marker = "    v_now := pg_catalog.clock_timestamp();"
        assert original_source.count(clock_marker) == 1
        test_source = original_source.replace(
            clock_marker,
            "    v_now := pg_catalog.current_setting('ofarm.test_now')::\n"
            "        pg_catalog.timestamptz;\n"
            "    PERFORM singleton\n"
            "    FROM ofarm_security._test_overflow_close_barrier\n"
            "    WHERE singleton\n"
            "    FOR SHARE;",
        )
        old_bucket = admin.execute(
            """
            SELECT pg_catalog.date_bin(
                pg_catalog.make_interval(secs => 60),
                pg_catalog.clock_timestamp(),
                '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
            ) - pg_catalog.make_interval(secs => 120)
            """
        ).fetchone()[0]
        started = admin.execute(
            """
            SELECT * FROM ofarm_security._insert_maintenance_event(
                'OVERFLOW_STARTED', 'AUDIT_CONTROL',
                NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                NULL, NULL, %s, %s, NULL, false, %s, %s, NULL
            )
            """,
            (
                old_bucket,
                old_bucket + timedelta(minutes=1),
                producer_name,
                component,
            ),
        ).fetchone()
        admin.execute(
            """
            INSERT INTO ofarm_security.operational_security_quota_bucket (
                producer, component, bucket_start, accepted_event_count,
                overflow_event_count, overflow_started_at, count_unknown
            ) VALUES (%s, %s, %s, 1024, 9, %s, false)
            """,
            (producer_name, component, old_bucket, started[1]),
        )
        admin.execute(
            """
            CREATE TABLE ofarm_security._test_overflow_close_barrier (
                singleton pg_catalog.bool PRIMARY KEY CHECK (singleton)
            )
            """
        )
        admin.execute(
            "ALTER TABLE ofarm_security._test_overflow_close_barrier "
            "OWNER TO ofarm_security_audit_owner"
        )
        admin.execute(
            "INSERT INTO ofarm_security._test_overflow_close_barrier "
            "VALUES (true)"
        )
        _replace_pretenant_append_source(admin, test_source)

    def append_to_old_bucket() -> tuple[object, ...]:
        with psycopg.connect(producer_dsn, autocommit=True) as producer:
            producer.execute("SET lock_timeout = '10s'")
            producer.execute(
                "SELECT pg_catalog.set_config('ofarm.test_now', %s, false)",
                ((old_bucket + timedelta(seconds=30)).isoformat(),),
            )
            return producer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, 'CREDENTIAL_MISSING', %s,
                    'OFARM_PRETENANT_CORRELATION_V1', 1
                )
                """,
                (event_id, bytes.fromhex("43" * 32)),
            ).fetchone()

    def close_old_bucket() -> tuple[object, ...]:
        with psycopg.connect(control_dsn, autocommit=True) as control:
            control.execute("SET lock_timeout = '10s'")
            return control.execute(
                """
                SELECT *
                FROM ofarm_security.close_overflow_bucket(%s, %s, %s)
                """,
                (producer_name, component, old_bucket),
            ).fetchone()

    try:
        with psycopg.connect(state["target_admin_dsn"]) as locker:
            locker.execute(
                """
                SELECT singleton
                FROM ofarm_security._test_overflow_close_barrier
                WHERE singleton
                FOR UPDATE
                """
            ).fetchone()
            with ThreadPoolExecutor(max_workers=2) as executor:
                appended_future = executor.submit(append_to_old_bucket)
                _wait_for_blocked_event_writer(state, producer_application)
                closed_future = executor.submit(close_old_bucket)
                _wait_for_event_relation_lock(
                    state, control_application, "ShareRowExclusiveLock"
                )
                assert not appended_future.done()
                assert not closed_future.done()
                locker.commit()
                appended = appended_future.result(timeout=10)
                closed = closed_future.result(timeout=10)

        assert appended == (None, None, None, False, old_bucket, False)
        with psycopg.connect(
            _role_dsn(state, "ofarm_security_audit_control_login"),
            autocommit=True,
        ) as control:
            retry_close = control.execute(
                """
                SELECT *
                FROM ofarm_security.close_overflow_bucket(%s, %s, %s)
                """,
                (producer_name, component, old_bucket),
            ).fetchone()
        assert retry_close == closed

        assert append_to_old_bucket() == appended
        with psycopg.connect(producer_dsn, autocommit=True) as producer:
            producer.execute(
                "SELECT pg_catalog.set_config('ofarm.test_now', %s, false)",
                ((old_bucket + timedelta(seconds=30)).isoformat(),),
            )
            with pytest.raises(
                psycopg.errors.InvalidParameterValue,
                match="audit clock moved behind closed quota boundary",
            ):
                producer.execute(
                    """
                    SELECT * FROM ofarm_security.append_pretenant_failure(
                        %s, 'CREDENTIAL_MISSING', %s,
                        'OFARM_PRETENANT_CORRELATION_V1', 1
                    )
                    """,
                    (uuid4(), bytes.fromhex("43" * 32)),
                ).fetchone()

        with psycopg.connect(state["target_admin_dsn"]) as admin:
            old_bucket_count = admin.execute(
                """
                SELECT pg_catalog.count(*)
                FROM ofarm_security.operational_security_quota_bucket
                WHERE producer = %s AND component = %s AND bucket_start = %s
                """,
                (producer_name, component, old_bucket),
            ).fetchone()[0]
            ended_rows = admin.execute(
                """
                SELECT interval_event_count, interval_count_unknown
                FROM ofarm_security.operational_security_event
                WHERE event_kind = 'OVERFLOW_ENDED'
                  AND affected_producer = %s
                  AND affected_component = %s
                  AND interval_start = %s
                """,
                (producer_name, component, old_bucket),
            ).fetchall()
            high_water = admin.execute(
                """
                SELECT closed_through_bucket_start
                FROM ofarm_security.operational_security_quota_high_water
                WHERE producer = %s AND component = %s
                """,
                (producer_name, component),
            ).fetchone()
        assert old_bucket_count == 0
        assert ended_rows == [(10, False)]
        assert high_water == (old_bucket,)
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            try:
                _replace_pretenant_append_source(admin, original_source)
            finally:
                admin.execute(
                    "DROP TABLE IF EXISTS "
                    "ofarm_security._test_overflow_close_barrier"
                )
        _reset_quota_state(state, producer_name, component)


def test_retention_waits_for_delayed_writer_and_cannot_reset_quota(
    migrated_audit_service,
):
    state = migrated_audit_service
    producer_name = "REQUEST_ROUTER_BOUNDARY_V1"
    component = "REQUEST_ROUTER"
    _reset_quota_state(state, producer_name, component)
    event_id = uuid4()
    token = uuid4().hex
    producer_application = "issue174-retention-append-" + token
    retention_application = "issue174-retention-purge-" + token
    producer_dsn = psycopg.conninfo.make_conninfo(
        _role_dsn(state, "ofarm_security_request_router_producer_login"),
        application_name=producer_application,
    )
    retention_dsn = psycopg.conninfo.make_conninfo(
        _role_dsn(state, "ofarm_security_audit_retention_login"),
        application_name=retention_application,
    )

    with psycopg.connect(
        state["target_admin_dsn"], autocommit=True
    ) as admin:
        original_source = admin.execute(
            """
            SELECT routine.prosrc
            FROM pg_catalog.pg_proc AS routine
            WHERE routine.oid =
                'ofarm_security.append_pretenant_failure('
                'uuid, text, bytea, text, integer)'::pg_catalog.regprocedure
            """
        ).fetchone()[0]
        clock_marker = "    v_now := pg_catalog.clock_timestamp();"
        assert original_source.count(clock_marker) == 1
        test_source = original_source.replace(
            clock_marker,
            "    v_now := pg_catalog.current_setting('ofarm.test_now')::\n"
            "        pg_catalog.timestamptz;\n"
            "    PERFORM singleton\n"
            "    FROM ofarm_security._test_retention_barrier\n"
            "    WHERE singleton\n"
            "    FOR SHARE;",
        )
        stale_bucket = admin.execute(
            """
            SELECT pg_catalog.date_bin(
                pg_catalog.make_interval(secs => 60),
                pg_catalog.clock_timestamp(),
                '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
            ) - pg_catalog.make_interval(secs => 120)
            """
        ).fetchone()[0]
        admin.execute(
            """
            INSERT INTO ofarm_security.operational_security_quota_bucket (
                producer, component, bucket_start, accepted_event_count
            ) VALUES (%s, %s, %s, 1024)
            """,
            (producer_name, component, stale_bucket),
        )
        admin.execute(
            """
            CREATE TABLE ofarm_security._test_retention_barrier (
                singleton pg_catalog.bool PRIMARY KEY CHECK (singleton)
            )
            """
        )
        admin.execute(
            "ALTER TABLE ofarm_security._test_retention_barrier "
            "OWNER TO ofarm_security_audit_owner"
        )
        admin.execute(
            "INSERT INTO ofarm_security._test_retention_barrier VALUES (true)"
        )
        _replace_pretenant_append_source(admin, test_source)

    def append_to_stale_full_bucket() -> tuple[object, ...]:
        with psycopg.connect(producer_dsn, autocommit=True) as producer:
            producer.execute("SET lock_timeout = '10s'")
            producer.execute(
                "SELECT pg_catalog.set_config('ofarm.test_now', %s, false)",
                ((stale_bucket + timedelta(seconds=30)).isoformat(),),
            )
            return producer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, 'BINDER_REFUSED', %s,
                    'OFARM_PRETENANT_CORRELATION_V1', 1
                )
                """,
                (event_id, bytes.fromhex("44" * 32)),
            ).fetchone()

    def purge_stale_buckets() -> tuple[object, ...]:
        with psycopg.connect(retention_dsn, autocommit=True) as retention:
            retention.execute("SET lock_timeout = '10s'")
            return retention.execute(
                """
                SELECT * FROM
                    ofarm_security.purge_expired_operational_security_events()
                """
            ).fetchone()

    try:
        with psycopg.connect(state["target_admin_dsn"]) as locker:
            locker.execute(
                """
                SELECT singleton
                FROM ofarm_security._test_retention_barrier
                WHERE singleton
                FOR UPDATE
                """
            ).fetchone()
            with ThreadPoolExecutor(max_workers=2) as executor:
                appended_future = executor.submit(append_to_stale_full_bucket)
                _wait_for_blocked_event_writer(state, producer_application)
                purged_future = executor.submit(purge_stale_buckets)
                _wait_for_event_relation_lock(
                    state, retention_application, "ShareRowExclusiveLock"
                )
                assert not appended_future.done()
                assert not purged_future.done()
                locker.commit()
                appended = appended_future.result(timeout=10)
                purged_future.result(timeout=10)

        assert appended == (None, None, None, False, stale_bucket, False)
        with psycopg.connect(state["target_admin_dsn"]) as admin:
            bucket = admin.execute(
                """
                SELECT accepted_event_count, overflow_event_count,
                       overflow_started_at IS NOT NULL, count_unknown
                FROM ofarm_security.operational_security_quota_bucket
                WHERE producer = %s AND component = %s AND bucket_start = %s
                """,
                (producer_name, component, stale_bucket),
            ).fetchone()
            stored_event_count = admin.execute(
                """
                SELECT pg_catalog.count(*)
                FROM ofarm_security.operational_security_event
                WHERE event_id = %s
                """,
                (event_id,),
            ).fetchone()[0]
            overflow_markers = admin.execute(
                """
                SELECT pg_catalog.count(*)
                FROM ofarm_security.operational_security_event
                WHERE event_kind = 'OVERFLOW_STARTED'
                  AND affected_producer = %s
                  AND affected_component = %s
                  AND interval_start = %s
                """,
                (producer_name, component, stale_bucket),
            ).fetchone()[0]
        assert bucket == (1024, 1, True, False)
        assert stored_event_count == 0
        assert overflow_markers == 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            try:
                _replace_pretenant_append_source(admin, original_source)
            finally:
                admin.execute(
                    "DROP TABLE IF EXISTS "
                    "ofarm_security._test_retention_barrier"
                )
                admin.execute(
                    """
                    DELETE FROM ofarm_security.operational_security_event
                    WHERE event_id = %s
                    """,
                    (event_id,),
                )
        _reset_quota_state(state, producer_name, component)


def test_retention_deleted_bucket_cannot_reopen_after_clock_rollback(
    migrated_audit_service,
):
    state = migrated_audit_service
    producer_name = "REQUEST_ROUTER_BOUNDARY_V1"
    component = "REQUEST_ROUTER"
    _reset_quota_state(state, producer_name, component)

    try:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            stale_bucket = admin.execute(
                """
                SELECT pg_catalog.date_bin(
                    pg_catalog.make_interval(secs => 60),
                    pg_catalog.clock_timestamp(),
                    '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
                ) - pg_catalog.make_interval(secs => 120)
                """
            ).fetchone()[0]
            admin.execute(
                """
                INSERT INTO ofarm_security.operational_security_quota_bucket (
                    producer, component, bucket_start, accepted_event_count
                ) VALUES (%s, %s, %s, 7)
                """,
                (producer_name, component, stale_bucket),
            )

        with psycopg.connect(
            _role_dsn(state, "ofarm_security_audit_retention_login"),
            autocommit=True,
        ) as retention:
            retention.execute(
                "SELECT * FROM "
                "ofarm_security.purge_expired_operational_security_events()"
            ).fetchone()

        with psycopg.connect(state["target_admin_dsn"]) as admin:
            state_after_purge = admin.execute(
                """
                SELECT
                    (SELECT pg_catalog.count(*)
                     FROM ofarm_security.operational_security_quota_bucket
                     WHERE producer = %s AND component = %s
                       AND bucket_start = %s),
                    (SELECT closed_through_bucket_start
                     FROM ofarm_security.operational_security_quota_high_water
                     WHERE producer = %s AND component = %s)
                """,
                (
                    producer_name,
                    component,
                    stale_bucket,
                    producer_name,
                    component,
                ),
            ).fetchone()
        assert state_after_purge == (0, stale_bucket)

        with _controlled_pretenant_clock(state):
            with psycopg.connect(
                _role_dsn(
                    state,
                    "ofarm_security_request_router_producer_login",
                ),
                autocommit=True,
            ) as producer:
                producer.execute(
                    "SELECT pg_catalog.set_config('ofarm.test_now', %s, false)",
                    ((stale_bucket + timedelta(seconds=30)).isoformat(),),
                )
                with pytest.raises(
                    psycopg.errors.InvalidParameterValue,
                    match="audit clock moved behind closed quota boundary",
                ):
                    producer.execute(
                        """
                        SELECT * FROM ofarm_security.append_pretenant_failure(
                            %s, 'BINDER_REFUSED', %s,
                            'OFARM_PRETENANT_CORRELATION_V1', 1
                        )
                        """,
                        (uuid4(), bytes.fromhex("45" * 32)),
                    ).fetchone()

        with psycopg.connect(state["target_admin_dsn"]) as admin:
            reopened = admin.execute(
                """
                SELECT pg_catalog.count(*)
                FROM ofarm_security.operational_security_quota_bucket
                WHERE producer = %s AND component = %s
                  AND bucket_start = %s
                """,
                (producer_name, component, stale_bucket),
            ).fetchone()[0]
        assert reopened == 0
    finally:
        _reset_quota_state(state, producer_name, component)


def test_bounded_query_enforces_exact_row_and_encoded_byte_ceilings(
    migrated_audit_service,
):
    state = migrated_audit_service
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        with pytest.raises(psycopg.Error):
            control.execute(
                """
                SELECT ofarm_security.commit_audit_access_intent(
                    'OPERATIONAL_DIAGNOSTIC_QUERY_V1', %s,
                    NULL, NULL, 257, 1048576
                )
                """,
                (QUERY_IDENTITY,),
            )
        one_byte = control.execute(
            """
            SELECT (ofarm_security.commit_audit_access_intent(
                'OPERATIONAL_DIAGNOSTIC_QUERY_V1', %s,
                NULL, NULL, 256, 1
            )).access_event_id
            """,
            (QUERY_IDENTITY,),
        ).fetchone()[0]
        three_rows = control.execute(
            """
            SELECT (ofarm_security.commit_audit_access_intent(
                'OPERATIONAL_DIAGNOSTIC_QUERY_V1', %s,
                NULL, NULL, 3, 1048576
            )).access_event_id
            """,
            (QUERY_IDENTITY,),
        ).fetchone()[0]

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_reader_login"),
        autocommit=True,
    ) as reader:
        assert reader.execute(
            """
            SELECT * FROM ofarm_security.query_operational_security_events(
                %s, NULL, NULL, 256, 1
            )
            """,
            (one_byte,),
        ).fetchall() == []
        rows = reader.execute(
            """
            SELECT * FROM ofarm_security.query_operational_security_events(
                %s, NULL, NULL, 3, 1048576
            )
            """,
            (three_rows,),
        ).fetchall()
        assert len(rows) == 3
        with pytest.raises(psycopg.Error):
            reader.execute(
                """
                SELECT * FROM ofarm_security.query_operational_security_events(
                    %s, NULL, NULL, 4, 1048576
                )
                """,
                (three_rows,),
            )


def test_retention_hides_expired_rows_then_purges_only_one_bounded_batch(
    migrated_audit_service,
):
    state = migrated_audit_service
    producer_name = "AUTHENTICATION_BOUNDARY_V1"
    component = "AUTHENTICATION"
    _reset_quota_state(state, producer_name, component)
    counts = _bulk_append_in_one_bucket(
        state,
        "ofarm_security_authentication_producer_login",
        "b1740000-0000-4000-8000-",
        "VERIFICATION_REFUSED",
    )
    assert counts[0:2] == (1024, 1)

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        changed = admin.execute(
            """
            UPDATE ofarm_security.operational_security_event
            SET observed_at = observed_at - pg_catalog.make_interval(days => 31),
                purge_after = purge_after - pg_catalog.make_interval(days => 31)
            WHERE event_kind = 'PRE_TENANT_FAILURE'
              AND event_id::pg_catalog.text LIKE 'b1740000-%%'
            """
        ).rowcount
        stale_bucket = admin.execute(
            """
            SELECT pg_catalog.date_bin(
                pg_catalog.make_interval(secs => 60),
                pg_catalog.clock_timestamp(),
                '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
            ) - pg_catalog.make_interval(secs => 120)
            """
        ).fetchone()[0]
        admin.execute(
            """
            INSERT INTO ofarm_security.operational_security_quota_bucket (
                producer, component, bucket_start, accepted_event_count
            ) VALUES (
                'REQUEST_ROUTER_BOUNDARY_V1', 'REQUEST_ROUTER', %s, 5
            )
            """,
            (stale_bucket,),
        )
    assert changed == 1024

    cursor = datetime.now(timezone.utc) - timedelta(days=25)
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        access = control.execute(
            """
            SELECT (ofarm_security.commit_audit_access_intent(
                'OPERATIONAL_DIAGNOSTIC_QUERY_V1', %s,
                %s, %s, 256, 1048576
            )).access_event_id
            """,
            (QUERY_IDENTITY, cursor, "ffffffff-ffff-4fff-bfff-ffffffffffff"),
        ).fetchone()[0]
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_reader_login"),
        autocommit=True,
    ) as reader:
        hidden = reader.execute(
            """
            SELECT * FROM ofarm_security.query_operational_security_events(
                %s, %s, %s, 256, 1048576
            )
            """,
            (access, cursor, "ffffffff-ffff-4fff-bfff-ffffffffffff"),
        ).fetchall()
    assert hidden == []

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_retention_login"),
        autocommit=True,
    ) as retention:
        first = retention.execute(
            """
                SELECT * FROM
                    ofarm_security.purge_expired_operational_security_events()
            """
        ).fetchone()
        second = retention.execute(
            """
                SELECT * FROM
                    ofarm_security.purge_expired_operational_security_events()
            """
        ).fetchone()
    assert first[1] == 1024
    assert second[1] == 0
    with psycopg.connect(state["target_admin_dsn"]) as admin:
        retention_event = admin.execute(
            """
            SELECT event_kind, retention_cutoff, retention_deleted_count,
                   correlation_hmac_value IS NULL
            FROM ofarm_security.operational_security_event
            WHERE event_id = %s
            """,
            (first[2],),
        ).fetchone()
        remaining = admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_event
            WHERE event_id::pg_catalog.text LIKE 'b1740000-%%'
            """
        ).fetchone()[0]
        stale_bucket_exists = admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_quota_bucket
            WHERE producer = 'REQUEST_ROUTER_BOUNDARY_V1'
              AND component = 'REQUEST_ROUTER'
              AND bucket_start = %s
            """,
            (stale_bucket,),
        ).fetchone()[0]
    assert retention_event == ("AUDIT_RETENTION", first[0], 1024, True)
    assert remaining == 0
    assert stale_bucket_exists == 0


def test_destroyed_audit_store_recreates_empty_and_records_only_explicit_gaps(
    migrated_audit_service,
):
    state = migrated_audit_service
    sentinel_start = datetime.now(timezone.utc) - timedelta(hours=1)
    sentinel_end = sentinel_start + timedelta(seconds=1)
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        sentinel_id = control.execute(
            "SELECT * FROM ofarm_security.append_audit_gap(%s, %s, 1, false)",
            (sentinel_start, sentinel_end),
        ).fetchone()[0]
    with psycopg.connect(state["target_admin_dsn"]) as admin:
        assert admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_event
            WHERE event_id = %s
            """,
            (sentinel_id,),
        ).fetchone()[0] == 1

    _destroy_service(state["admin_dsn"])
    provision_service(
        state["admin_dsn"],
        SECURITY_AUDIT_PROVISIONING_SPEC,
        login_passwords=state["passwords"],
    )
    state["report"] = migrate_service(
        admin_dsn=state["admin_dsn"],
        migrator_dsn=_role_dsn(state, "ofarm_migrator"),
        spec=SECURITY_AUDIT_PROVISIONING_SPEC,
        migration_set=state["migration_set"],
        release_identity="issue-174-audit-store-loss-recreate-test",
        execution_id=uuid4(),
    )

    with psycopg.connect(state["target_admin_dsn"]) as admin:
        recreated_counts = admin.execute(
            """
            SELECT
                (SELECT pg_catalog.count(*)
                 FROM ofarm_security.operational_security_event),
                (SELECT pg_catalog.count(*)
                 FROM ofarm_security.operational_security_quota_bucket),
                (SELECT pg_catalog.count(*)
                 FROM ofarm_security.operational_security_event
                 WHERE event_id = %s)
            """,
            (sentinel_id,),
        ).fetchone()
    assert recreated_counts == (0, 0, 0)

    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=10)
    middle = now - timedelta(minutes=5)
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        known = control.execute(
            "SELECT * FROM ofarm_security.append_audit_gap(%s, %s, 7, false)",
            (start, middle),
        ).fetchone()
        unknown = control.execute(
            "SELECT * FROM ofarm_security.append_audit_gap(%s, %s, 0, true)",
            (middle, now),
        ).fetchone()
        with pytest.raises(psycopg.Error):
            control.execute(
                "SELECT ofarm_security.append_audit_gap(%s, %s, 7, true)",
                (start, now),
            )

    with psycopg.connect(state["target_admin_dsn"]) as admin:
        rows = admin.execute(
            """
            SELECT event_id, event_kind, producer, component,
                   interval_event_count, interval_count_unknown,
                   correlation_hmac_value IS NULL
            FROM ofarm_security.operational_security_event
            ORDER BY interval_start
            """,
        ).fetchall()
        copies = admin.execute(
            """
            SELECT
                (SELECT pg_catalog.count(*) FROM pg_catalog.pg_publication),
                (SELECT pg_catalog.count(*) FROM pg_catalog.pg_subscription
                 WHERE subdbid = (SELECT oid FROM pg_catalog.pg_database
                                  WHERE datname = pg_catalog.current_database())),
                (SELECT pg_catalog.count(*) FROM pg_catalog.pg_replication_slots
                 WHERE database = pg_catalog.current_database()),
                pg_catalog.to_regrole('ofarm_security_audit_backup_reader'),
                pg_catalog.to_regrole('ofarm_security_audit_restore_operator')
            """
        ).fetchone()
    assert rows == [
        (
            known[0], "AUDIT_GAP", "SECURITY_OPERATIONS_V1",
            "AUDIT_CONTROL", 7, False, True,
        ),
        (
            unknown[0], "AUDIT_GAP", "SECURITY_OPERATIONS_V1",
            "AUDIT_CONTROL", None, True, True,
        ),
    ]
    assert copies == (0, 0, 0, None, None)


def _observe_structure(state: dict[str, object]) -> tuple[object, ...]:
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_readiness_login"),
        autocommit=True,
    ) as readiness:
        return readiness.execute(
            "SELECT * FROM ofarm_security.verify_security_audit_structure()"
        ).fetchone()


def _replace_pg_stat_activity_view(
    admin: psycopg.Connection, definition: str
) -> None:
    admin.execute(
        sql.SQL(
            "CREATE OR REPLACE VIEW pg_catalog.pg_stat_activity AS {}"
        ).format(sql.SQL(definition))
    )


def test_access_clock_structure_drift_refuses_readiness(
    migrated_audit_service,
):
    state = migrated_audit_service
    with psycopg.connect(
        state["target_admin_dsn"], autocommit=True
    ) as admin:
        admin.execute(
            """
            ALTER SEQUENCE
                ofarm_security.operational_security_access_clock_high_water
            CACHE 2
            """
        )
    try:
        drift = _observe_structure(state)
        assert drift[0] is False
        assert drift[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                ALTER SEQUENCE
                    ofarm_security.operational_security_access_clock_high_water
                CACHE 1
                """
            )
    assert _observe_structure(state) == (True, 0, False)

def test_structural_readiness_refuses_role_attribute_and_membership_drift(
    migrated_audit_service,
):
    state = migrated_audit_service
    producer = "ofarm_security_authentication_producer_login"
    with psycopg.connect(state["admin_dsn"], autocommit=True) as admin:
        admin.execute(sql.SQL("ALTER ROLE {} NOINHERIT").format(
            sql.Identifier(producer)
        ))
    try:
        drift = _observe_structure(state)
        assert drift[0] is False
        assert drift[1] >= 1
    finally:
        with psycopg.connect(state["admin_dsn"], autocommit=True) as admin:
            admin.execute(sql.SQL("ALTER ROLE {} INHERIT").format(
                sql.Identifier(producer)
            ))
    assert _observe_structure(state) == (True, 0, False)

    granted_role = "ofarm_security_audit_ingest"
    member_role = "ofarm_security_authentication_producer_login"
    alternate_dba = "alternate_audit_portability_dba"
    renamed_grantor = "renamed_audit_bootstrap_dba"
    alternate_password = f"audit-portability-{secrets.token_urlsafe(32)}"
    with psycopg.connect(state["admin_dsn"], autocommit=True) as admin:
        original_membership = admin.execute(
            """
            SELECT grantor.rolname::pg_catalog.text,
                   grantor.rolsuper,
                   membership.inherit_option,
                   membership.set_option,
                   membership.admin_option
            FROM pg_catalog.pg_auth_members AS membership
            JOIN pg_catalog.pg_roles AS granted
              ON granted.oid = membership.roleid
            JOIN pg_catalog.pg_roles AS member
              ON member.oid = membership.member
            JOIN pg_catalog.pg_roles AS grantor
              ON grantor.oid = membership.grantor
            WHERE granted.rolname = %s AND member.rolname = %s
            """,
            (granted_role, member_role),
        ).fetchone()
        assert original_membership[1:] == (True, True, False, False)
        assert admin.execute(
            "SELECT pg_catalog.to_regrole(%s), pg_catalog.to_regrole(%s)",
            (alternate_dba, renamed_grantor),
        ).fetchone() == (None, None)
        admin.execute(
            sql.SQL("CREATE ROLE {} SUPERUSER LOGIN PASSWORD {}").format(
                sql.Identifier(alternate_dba),
                sql.Literal(alternate_password),
            )
        )
    alternate_admin_dsn = psycopg.conninfo.make_conninfo(
        state["admin_dsn"], user=alternate_dba, password=alternate_password
    )
    grantor_renamed = False
    try:
        with psycopg.connect(
            alternate_admin_dsn, autocommit=True
        ) as alternate_admin:
            alternate_admin.execute(
                sql.SQL("ALTER ROLE {} RENAME TO {}").format(
                    sql.Identifier(original_membership[0]),
                    sql.Identifier(renamed_grantor),
                )
            )
            grantor_renamed = True
            portable_membership = alternate_admin.execute(
                """
                SELECT grantor.rolname::pg_catalog.text,
                       grantor.rolsuper,
                       membership.inherit_option,
                       membership.set_option,
                       membership.admin_option
                FROM pg_catalog.pg_auth_members AS membership
                JOIN pg_catalog.pg_roles AS granted
                  ON granted.oid = membership.roleid
                JOIN pg_catalog.pg_roles AS member
                  ON member.oid = membership.member
                JOIN pg_catalog.pg_roles AS grantor
                  ON grantor.oid = membership.grantor
                WHERE granted.rolname = %s AND member.rolname = %s
                """,
                (granted_role, member_role),
            ).fetchone()
        assert portable_membership == (
            renamed_grantor, True, True, False, False,
        )
        assert _observe_structure(state) == (True, 0, False)
        report = migrate_service(
            admin_dsn=alternate_admin_dsn,
            migrator_dsn=_role_dsn(state, "ofarm_migrator"),
            spec=SECURITY_AUDIT_PROVISIONING_SPEC,
            migration_set=state["migration_set"],
            release_identity="issue-174-audit-portable-dba-grantor-test",
            execution_id=uuid4(),
        )
        assert report.applied_versions == ()
    finally:
        if grantor_renamed:
            with psycopg.connect(
                alternate_admin_dsn, autocommit=True
            ) as alternate_admin:
                alternate_admin.execute(
                    sql.SQL("ALTER ROLE {} RENAME TO {}").format(
                        sql.Identifier(renamed_grantor),
                        sql.Identifier(original_membership[0]),
                    )
                )
        with psycopg.connect(state["admin_dsn"], autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP ROLE {}").format(sql.Identifier(alternate_dba))
            )
            restored_grantor = admin.execute(
                """
                SELECT grantor.rolname::pg_catalog.text
                FROM pg_catalog.pg_auth_members AS membership
                JOIN pg_catalog.pg_roles AS granted
                  ON granted.oid = membership.roleid
                JOIN pg_catalog.pg_roles AS member
                  ON member.oid = membership.member
                JOIN pg_catalog.pg_roles AS grantor
                  ON grantor.oid = membership.grantor
                WHERE granted.rolname = %s AND member.rolname = %s
                """,
                (granted_role, member_role),
            ).fetchone()[0]
    assert restored_grantor == original_membership[0]
    assert _observe_structure(state) == (True, 0, False)

    with psycopg.connect(state["admin_dsn"], autocommit=True) as admin:
        admin.execute(
            sql.SQL("GRANT {} TO {}").format(
                sql.Identifier("ofarm_security_audit_control"),
                sql.Identifier(producer),
            )
        )
    try:
        drift = _observe_structure(state)
        assert drift[0] is False
        assert drift[1] >= 1
    finally:
        with psycopg.connect(state["admin_dsn"], autocommit=True) as admin:
            admin.execute(
                sql.SQL("REVOKE {} FROM {}").format(
                    sql.Identifier("ofarm_security_audit_control"),
                    sql.Identifier(producer),
                )
            )
    assert _observe_structure(state) == (True, 0, False)


def _replace_event_fingerprint_source(
    admin: psycopg.Connection, source: str
) -> None:
    admin.execute(
        sql.SQL(
            """
            CREATE OR REPLACE FUNCTION ofarm_security._event_fingerprint(
                VARIADIC p_fields pg_catalog.bytea[]
            ) RETURNS pg_catalog.bytea
            LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
            SET search_path = pg_catalog, pg_temp
            AS {}
            """
        ).format(sql.Literal(source))
    )


def test_complete_catalog_fingerprint_refuses_body_constraint_and_acl_tamper(
    migrated_audit_service,
):
    state = migrated_audit_service
    clean = (True, 0, False)
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        original_source = admin.execute(
            """
            SELECT routine.prosrc
            FROM pg_catalog.pg_proc AS routine
            WHERE routine.oid =
                'ofarm_security._event_fingerprint(bytea[])'::pg_catalog.regprocedure
            """
        ).fetchone()[0]
        _replace_event_fingerprint_source(
            admin, original_source + "\n-- hostile source drift"
        )
    try:
        body_drift = _observe_structure(state)
        assert body_drift[0] is False
        assert body_drift[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            _replace_event_fingerprint_source(admin, original_source)
    assert _observe_structure(state) == clean

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            """
            DELETE FROM ofarm_security.
                operational_security_overflow_identity_receipt
            WHERE producer = 'AUTHENTICATION_BOUNDARY_V1'
              AND component = 'AUTHENTICATION'
              AND lock_slot = 0
            """
        )
    try:
        missing_receipt_slot = _observe_structure(state)
        assert missing_receipt_slot[0] is False
        assert missing_receipt_slot[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                INSERT INTO ofarm_security.
                    operational_security_overflow_identity_receipt (
                        producer, component, lock_slot
                    ) VALUES (
                        'AUTHENTICATION_BOUNDARY_V1', 'AUTHENTICATION', 0
                    )
                """
            )
    assert _observe_structure(state) == clean

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            """
            ALTER TABLE ofarm_security.operational_security_quota_bucket
            DROP CONSTRAINT operational_security_quota_bucket_count_check
            """
        )
        admin.execute(
            """
            ALTER TABLE ofarm_security.operational_security_quota_bucket
            ADD CONSTRAINT operational_security_quota_bucket_count_check CHECK (
                accepted_event_count BETWEEN 0 AND 1025
                AND overflow_event_count >= 0
            )
            """
        )
    try:
        constraint_drift = _observe_structure(state)
        assert constraint_drift[0] is False
        assert constraint_drift[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                ALTER TABLE ofarm_security.operational_security_quota_bucket
                DROP CONSTRAINT operational_security_quota_bucket_count_check
                """
            )
            admin.execute(
                """
                ALTER TABLE ofarm_security.operational_security_quota_bucket
                ADD CONSTRAINT operational_security_quota_bucket_count_check CHECK (
                    accepted_event_count BETWEEN 0 AND 1024
                    AND overflow_event_count >= 0
                )
                """
            )
    assert _observe_structure(state) == clean

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            """
            GRANT EXECUTE ON FUNCTION
                ofarm_security._event_fingerprint(pg_catalog.bytea[])
            TO ofarm_security_audit_readiness
            """
        )
    try:
        acl_drift = _observe_structure(state)
        assert acl_drift[0] is False
        assert acl_drift[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                REVOKE EXECUTE ON FUNCTION
                    ofarm_security._event_fingerprint(pg_catalog.bytea[])
                FROM ofarm_security_audit_readiness
                """
            )
    assert _observe_structure(state) == clean

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            """
            DELETE FROM ofarm_security.operational_security_event_identity_lock
            WHERE lock_slot = 0
            """
        )
    try:
        missing_mutex = _observe_structure(state)
        assert missing_mutex[0] is False
        assert missing_mutex[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                INSERT INTO ofarm_security.operational_security_event_identity_lock (
                    lock_slot
                ) VALUES (0)
                """
            )
    assert _observe_structure(state) == clean


def test_complete_catalog_fingerprint_refuses_parameter_acl_tamper(
    migrated_audit_service,
):
    state = migrated_audit_service
    governed_runtime_role = (
        "ofarm_security_authentication_producer_login"
    )
    with psycopg.connect(state["admin_dsn"], autocommit=True) as admin:
        admin.execute(
            sql.SQL(
                "GRANT SET ON PARAMETER session_replication_role TO {}"
            ).format(sql.Identifier(governed_runtime_role))
        )
    try:
        with psycopg.connect(
            _role_dsn(state, governed_runtime_role), autocommit=True
        ) as governed_runtime:
            governed_runtime.execute(
                "SET session_replication_role = replica"
            )
            assert governed_runtime.execute(
                "SHOW session_replication_role"
            ).fetchone()[0] == "replica"
        parameter_acl_drift = _observe_structure(state)
        assert parameter_acl_drift[0] is False
        assert parameter_acl_drift[1] >= 1
    finally:
        with psycopg.connect(state["admin_dsn"], autocommit=True) as admin:
            admin.execute(
                sql.SQL(
                    "REVOKE SET ON PARAMETER session_replication_role FROM {}"
                ).format(sql.Identifier(governed_runtime_role))
            )
    assert _observe_structure(state) == (True, 0, False)

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        injected_large_object = admin.execute(
            "SELECT pg_catalog.lo_from_bytea(0, "
            "pg_catalog.decode(pg_catalog.repeat('ab', 32), 'hex'))"
        ).fetchone()[0]
    try:
        large_object_drift = _observe_structure(state)
        assert large_object_drift[0] is False
        assert large_object_drift[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            assert admin.execute(
                "SELECT pg_catalog.lo_unlink(%s)",
                (injected_large_object,),
            ).fetchone()[0] == 1
    assert _observe_structure(state) == (True, 0, False)

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            """
            GRANT EXECUTE ON FUNCTION pg_catalog.lo_from_bytea(
                pg_catalog.oid, pg_catalog.bytea
            ) TO ofarm_security_audit_ingest
            """
        )
    try:
        large_object_acl_drift = _observe_structure(state)
        assert large_object_acl_drift[0] is False
        assert large_object_acl_drift[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                REVOKE EXECUTE ON FUNCTION pg_catalog.lo_from_bytea(
                    pg_catalog.oid, pg_catalog.bytea
                ) FROM ofarm_security_audit_ingest
                """
            )
    assert _observe_structure(state) == (True, 0, False)

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        original_cost = admin.execute(
            """
            SELECT routine.procost
            FROM pg_catalog.pg_proc AS routine
            WHERE routine.oid =
                'pg_catalog.lo_get(oid)'::pg_catalog.regprocedure
            """
        ).fetchone()[0]
        assert original_cost == 1
        admin.execute("ALTER FUNCTION pg_catalog.lo_get(oid) COST 2")
    try:
        large_object_property_drift = _observe_structure(state)
        assert large_object_property_drift[0] is False
        assert large_object_property_drift[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute("ALTER FUNCTION pg_catalog.lo_get(oid) COST 1")
    assert _observe_structure(state) == (True, 0, False)

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            """
            CREATE OR REPLACE FUNCTION pg_catalog.lo_get(pg_catalog.oid)
            RETURNS pg_catalog.bytea
            LANGUAGE sql VOLATILE STRICT PARALLEL UNSAFE SECURITY INVOKER
            COST 1
            AS 'SELECT pg_catalog.decode(
                ''''::pg_catalog.text, ''hex''::pg_catalog.text
            )'
            """
        )
    try:
        large_object_body_drift = _observe_structure(state)
        assert large_object_body_drift[0] is False
        assert large_object_body_drift[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                CREATE OR REPLACE FUNCTION pg_catalog.lo_get(pg_catalog.oid)
                RETURNS pg_catalog.bytea
                LANGUAGE internal VOLATILE STRICT PARALLEL UNSAFE
                    SECURITY INVOKER
                COST 1
                AS 'be_lo_get'
                """
            )
    assert _observe_structure(state) == (True, 0, False)

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            """
            CREATE FUNCTION pg_catalog.lo_backdoor() RETURNS pg_catalog.int4
            LANGUAGE sql IMMUTABLE PARALLEL SAFE SECURITY INVOKER
            AS 'SELECT 1'
            """
        )
    try:
        unexpected_large_object_routine = _observe_structure(state)
        assert unexpected_large_object_routine[0] is False
        assert unexpected_large_object_routine[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute("DROP FUNCTION pg_catalog.lo_backdoor()")
    assert _observe_structure(state) == (True, 0, False)


def test_backend_statistics_view_routine_and_acl_tamper_refuse(
    migrated_audit_service,
):
    state = migrated_audit_service
    clean = (True, 0, False)

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            """
            GRANT SELECT ON TABLE pg_catalog.pg_stat_activity
            TO ofarm_security_audit_reader
            """
        )
    try:
        view_acl_drift = _observe_structure(state)
        assert view_acl_drift[0] is False
        assert view_acl_drift[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                REVOKE SELECT ON TABLE pg_catalog.pg_stat_activity
                FROM ofarm_security_audit_reader
                """
            )
    assert _observe_structure(state) == clean

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            """
            GRANT EXECUTE ON FUNCTION
                pg_catalog.pg_stat_get_backend_activity(pg_catalog.int4)
            TO ofarm_security_audit_ingest
            """
        )
    try:
        routine_acl_drift = _observe_structure(state)
        assert routine_acl_drift[0] is False
        assert routine_acl_drift[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                REVOKE EXECUTE ON FUNCTION
                    pg_catalog.pg_stat_get_backend_activity(pg_catalog.int4)
                FROM ofarm_security_audit_ingest
                """
            )
    assert _observe_structure(state) == clean

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            """
            ALTER FUNCTION
                pg_catalog.pg_stat_get_backend_activity(pg_catalog.int4)
            COST 2
            """
        )
    try:
        routine_property_drift = _observe_structure(state)
        assert routine_property_drift[0] is False
        assert routine_property_drift[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                """
                ALTER FUNCTION
                    pg_catalog.pg_stat_get_backend_activity(pg_catalog.int4)
                COST 1
                """
            )
    assert _observe_structure(state) == clean

    for routine_name in (
        "pg_stat_get_activity_issue174_extra",
        "pg_stat_get_backend_issue174_extra",
    ):
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                sql.SQL(
                    "CREATE FUNCTION pg_catalog.{}() "
                    "RETURNS pg_catalog.int4 LANGUAGE sql "
                    "IMMUTABLE PARALLEL SAFE SECURITY INVOKER "
                    "AS 'SELECT 1'"
                ).format(sql.Identifier(routine_name))
            )
        try:
            unexpected_routine_drift = _observe_structure(state)
            assert unexpected_routine_drift[0] is False
            assert unexpected_routine_drift[1] >= 1
        finally:
            with psycopg.connect(
                state["target_admin_dsn"], autocommit=True
            ) as admin:
                admin.execute(
                    sql.SQL("DROP FUNCTION pg_catalog.{}()").format(
                        sql.Identifier(routine_name)
                    )
                )
        assert _observe_structure(state) == clean

    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        original_view_definition = admin.execute(
            """
            SELECT pg_catalog.pg_get_viewdef(class.oid, false)
            FROM pg_catalog.pg_class AS class
            WHERE class.oid =
                'pg_catalog.pg_stat_activity'::pg_catalog.regclass
            """
        ).fetchone()[0]
        tampered_view_definition = (
            original_view_definition.rstrip().removesuffix(";")
            + "\n WHERE s.pid IS NOT NULL;"
        )
        _replace_pg_stat_activity_view(admin, tampered_view_definition)
    try:
        view_definition_drift = _observe_structure(state)
        assert view_definition_drift[0] is False
        assert view_definition_drift[1] >= 1
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            _replace_pg_stat_activity_view(admin, original_view_definition)
    assert _observe_structure(state) == clean


def _replace_structure_verifier_source(
    admin: psycopg.Connection, source: str
) -> None:
    admin.execute(
        sql.SQL(
            """
            CREATE OR REPLACE FUNCTION
                ofarm_security.verify_security_audit_structure()
            RETURNS ofarm_security.security_audit_structure_report
            LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
            SET search_path = pg_catalog, pg_temp
            SET TimeZone = 'UTC'
            SET DateStyle = 'ISO, MDY'
            SET quote_all_identifiers = off
            SET standard_conforming_strings = on
            AS {}
            """
        ).format(sql.Literal(source))
    )


def test_external_catalog_anchor_refuses_self_excluded_verifier_body_tamper(
    migrated_audit_service,
):
    state = migrated_audit_service
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        original_source = admin.execute(
            """
            SELECT routine.prosrc
            FROM pg_catalog.pg_proc AS routine
            WHERE routine.oid =
                'ofarm_security.verify_security_audit_structure()'::
                    pg_catalog.regprocedure
            """
        ).fetchone()[0]
        _replace_structure_verifier_source(
            admin,
            """
            BEGIN
                RAISE EXCEPTION 'hostile verifier body executed';
            END
            """,
        )
    try:
        with pytest.raises(
            MigrationDirtyError,
            match=(
                "migration-owned catalog verifier identity differs "
                "at the final head"
            ),
        ):
            migrate_service(
                admin_dsn=state["admin_dsn"],
                migrator_dsn=_role_dsn(state, "ofarm_migrator"),
                spec=SECURITY_AUDIT_PROVISIONING_SPEC,
                migration_set=state["migration_set"],
                release_identity="issue-174-audit-external-anchor-tamper-test",
                execution_id=uuid4(),
            )
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            _replace_structure_verifier_source(admin, original_source)

    assert _observe_structure(state) == (True, 0, False)
    report = migrate_service(
        admin_dsn=state["admin_dsn"],
        migrator_dsn=_role_dsn(state, "ofarm_migrator"),
        spec=SECURITY_AUDIT_PROVISIONING_SPEC,
        migration_set=state["migration_set"],
        release_identity="issue-174-audit-external-anchor-restored-test",
        execution_id=uuid4(),
    )
    assert report.applied_versions == ()


def test_authoritative_runner_noop_refuses_structural_catalog_drift(
    migrated_audit_service,
):
    state = migrated_audit_service
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            "CREATE INDEX rogue_audit_index "
            "ON ofarm_security.operational_security_event (event_id)"
        )
    try:
        with pytest.raises(
            MigrationDirtyError,
            match="structural verifier differs",
        ):
            migrate_service(
                admin_dsn=state["admin_dsn"],
                migrator_dsn=_role_dsn(state, "ofarm_migrator"),
                spec=SECURITY_AUDIT_PROVISIONING_SPEC,
                migration_set=state["migration_set"],
                release_identity="issue-174-audit-noop-drift-test",
                execution_id=uuid4(),
            )
    finally:
        with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
            admin.execute("DROP INDEX ofarm_security.rogue_audit_index")
    assert _observe_structure(state) == (True, 0, False)


def test_post_migration_owner_created_collation_refuses_observer_and_runner(
    migrated_audit_service,
):
    state = migrated_audit_service
    spec = SECURITY_AUDIT_PROVISIONING_SPEC
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            sql.SQL("SET ROLE {}").format(sql.Identifier(spec.schema_owner))
        )
        admin.execute(
            sql.SQL(
                "CREATE COLLATION {}.rogue "
                "(provider = builtin, locale = 'C')"
            ).format(sql.Identifier(spec.schema_name))
        )
    try:
        structure = _observe_structure(state)
        assert structure[0] is False
        assert structure[1] >= 1

        with psycopg.connect(
            _role_dsn(state, "ofarm_security_audit_readiness_login"),
            autocommit=True,
        ) as readiness:
            observation = readiness.execute(
                "SELECT * FROM "
                "ofarm_security.observe_security_audit_contract()"
            ).fetchone()
        assert observation[11:] == (False, False)

        with pytest.raises(
            MigrationDirtyError,
            match="structural verifier differs",
        ):
            migrate_service(
                admin_dsn=state["admin_dsn"],
                migrator_dsn=_role_dsn(state, "ofarm_migrator"),
                spec=spec,
                migration_set=state["migration_set"],
                release_identity="issue-174-audit-schema-class-drift-test",
                execution_id=uuid4(),
            )
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                sql.SQL("DROP COLLATION {}.rogue").format(
                    sql.Identifier(spec.schema_name)
                )
            )
    assert _observe_structure(state) == (True, 0, False)


def test_post_migration_owner_created_rule_refuses_observer_and_runner(
    migrated_audit_service,
):
    state = migrated_audit_service
    spec = SECURITY_AUDIT_PROVISIONING_SPEC
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            sql.SQL("SET ROLE {}").format(sql.Identifier(spec.schema_owner))
        )
        admin.execute(
            "CREATE RULE rogue AS ON INSERT TO "
            "ofarm_security.operational_security_event DO INSTEAD NOTHING"
        )
    try:
        structure = _observe_structure(state)
        assert structure[0] is False
        assert structure[1] >= 1

        with psycopg.connect(
            _role_dsn(state, "ofarm_security_audit_readiness_login"),
            autocommit=True,
        ) as readiness:
            observation = readiness.execute(
                "SELECT * FROM "
                "ofarm_security.observe_security_audit_contract()"
            ).fetchone()
        assert observation[11:] == (False, False)

        with pytest.raises(
            MigrationDirtyError,
            match="structural verifier differs",
        ):
            migrate_service(
                admin_dsn=state["admin_dsn"],
                migrator_dsn=_role_dsn(state, "ofarm_migrator"),
                spec=spec,
                migration_set=state["migration_set"],
                release_identity="issue-174-audit-rewrite-rule-drift-test",
                execution_id=uuid4(),
            )
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute(
                "DROP RULE rogue ON "
                "ofarm_security.operational_security_event"
            )
    assert _observe_structure(state) == (True, 0, False)


def test_post_migration_database_wide_setting_refuses_observer_and_runner(
    migrated_audit_service,
):
    state = migrated_audit_service
    spec = SECURITY_AUDIT_PROVISIONING_SPEC
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            sql.SQL("SET ROLE {}").format(sql.Identifier(spec.database_owner))
        )
        admin.execute(
            "ALTER DATABASE ofarm_security_audit "
            "SET default_transaction_read_only = on"
        )
    try:
        structure = _observe_structure(state)
        assert structure[0] is False
        assert structure[1] >= 1

        with psycopg.connect(
            _role_dsn(state, "ofarm_security_audit_readiness_login"),
            autocommit=True,
        ) as readiness:
            observation = readiness.execute(
                "SELECT * FROM "
                "ofarm_security.observe_security_audit_contract()"
            ).fetchone()
        assert observation[11:] == (False, False)

        with pytest.raises(
            MigrationTargetError,
            match="target route is not a writable primary",
        ):
            migrate_service(
                admin_dsn=state["admin_dsn"],
                migrator_dsn=_role_dsn(state, "ofarm_migrator"),
                spec=spec,
                migration_set=state["migration_set"],
                release_identity="issue-174-audit-database-setting-drift-test",
                execution_id=uuid4(),
            )
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute("SET default_transaction_read_only = off")
            admin.execute(
                "ALTER DATABASE ofarm_security_audit "
                "RESET default_transaction_read_only"
            )
    assert _observe_structure(state) == (True, 0, False)


def test_break_glass_presence_intentionally_makes_readiness_false(
    migrated_audit_service,
):
    state = migrated_audit_service
    with psycopg.connect(state["admin_dsn"], autocommit=True) as admin:
        admin.execute("CREATE ROLE ofarm_security_audit_export_login LOGIN")
    try:
        with psycopg.connect(
            _role_dsn(state, "ofarm_security_audit_readiness_login"),
            autocommit=True,
        ) as readiness:
            row = readiness.execute(
                "SELECT * FROM ofarm_security.verify_security_audit_structure()"
            ).fetchone()
        assert row[0] is False
        assert row[1] >= 1
        assert row[2] is True
    finally:
        with psycopg.connect(state["admin_dsn"], autocommit=True) as admin:
            admin.execute("DROP ROLE IF EXISTS ofarm_security_audit_export_login")
