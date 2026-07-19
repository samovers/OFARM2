"""Real PostgreSQL 17 provisioning boundary tests for issue #174."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import psycopg
import psycopg.conninfo
import pytest
from psycopg import sql

import deployment.postgresql.provisioning as provisioning_module
from deployment.postgresql.catalog_classifier import (
    SCHEMA_LOCAL_CATALOG_CLASSES,
    SCHEMA_LOCAL_OBJECT_SELECTS_SQL,
)
from deployment.postgresql.provisioning import (
    ProvisioningDriftError,
    ProvisioningInfrastructureReport,
    ProvisioningTargetError,
    migration_locked_differences,
    provision_service,
    verify_service,
    verify_service_infrastructure,
    verify_provisioned_cluster_lineages,
)
from deployment.postgresql.provisioning_specs import (
    MIGRATION_LOCK_KEY_POLICY,
    PROVISIONING_SPEC_DIGEST_POLICY,
    SECURITY_AUDIT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC,
)
from deployment.postgresql.tenant_contract import TENANT_CONTEXT_ROUTINE_SIGNATURES
from deployment.postgresql.version_policy import (
    SUPPORTED_POSTGRESQL_SERVER_VERSION,
    SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
    SUPPORTED_POSTGRESQL_VERSION,
)


TENANT_ADMIN_ENV = "OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN"
AUDIT_ADMIN_ENV = "OFARM_SECURITY_AUDIT_PG_ADMIN_DSN"
MAINTENANCE_DATABASES = ("postgres", "template0", "template1")


def _admin_dsn(environment_name: str) -> str:
    value = os.environ.get(environment_name)
    if value:
        return value
    raise RuntimeError(
        f"{environment_name} must identify a dedicated PostgreSQL 17 service"
    )


def _database_dsn(admin_dsn: str, database_name: str, **overrides: str) -> str:
    parameters = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    parameters["dbname"] = database_name
    parameters.update(overrides)
    return psycopg.conninfo.make_conninfo(**parameters)


def _tcp_database_dsn(
    admin_dsn: str, database_name: str, **overrides: str
) -> str:
    parameters = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    if not parameters.get("host") or parameters["host"].startswith("/"):
        pytest.skip("a TCP admin DSN is required for the HBA/SCRAM proof")
    parameters.pop("hostaddr", None)
    parameters["dbname"] = database_name
    parameters.update(overrides)
    return psycopg.conninfo.make_conninfo(**parameters)


def _assert_clean_service(admin_dsn: str, database_name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        database = connection.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (database_name,),
        ).fetchone()
        roles = connection.execute(
            r"""
            SELECT rolname::text
            FROM pg_catalog.pg_roles
            WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
            ORDER BY rolname
            """
        ).fetchall()
        databases = connection.execute(
            "SELECT datname::text FROM pg_catalog.pg_database ORDER BY datname"
        ).fetchall()
        public_database_privileges = connection.execute(
            """
            SELECT database.datname::text, acl.privilege_type
            FROM pg_catalog.pg_database AS database
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(
                    database.datacl,
                    pg_catalog.acldefault('d', database.datdba)
                )
            ) AS acl
            WHERE database.datname = ANY (%s::text[])
              AND acl.grantee = 0
            ORDER BY 1, 2
            """,
            (list(MAINTENANCE_DATABASES),),
        ).fetchall()
    assert database is None, f"disposable database already exists: {database_name}"
    assert roles == [], f"disposable service has governed roles: {roles}"
    assert databases == [("postgres",), ("template0",), ("template1",)]
    assert public_database_privileges == [
        ("postgres", "CONNECT"),
        ("postgres", "TEMPORARY"),
        ("template0", "CONNECT"),
        ("template1", "CONNECT"),
    ]


def _destroy_test_service(admin_dsn: str, database_name: str) -> None:
    """Remove only resources this test module has just created."""

    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(
            """
            SELECT pg_catalog.pg_terminate_backend(pid)
            FROM pg_catalog.pg_stat_activity
            WHERE datname = %s AND pid <> pg_catalog.pg_backend_pid()
            """,
            (database_name,),
        )
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name))
        )
        role_names = [
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
        if role_names:
            connection.execute(
                sql.SQL("DROP ROLE {}").format(
                    sql.SQL(", ").join(sql.Identifier(name) for name in role_names)
                )
            )
        for maintenance_database in MAINTENANCE_DATABASES:
            connection.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO PUBLIC").format(
                    sql.Identifier(maintenance_database)
                )
            )
        connection.execute(
            "GRANT TEMPORARY ON DATABASE postgres TO PUBLIC"
        )
        connection.execute(
            "REVOKE TEMPORARY ON DATABASE template0, template1 FROM PUBLIC"
        )


def _passwords(spec, nonce: str) -> dict[str, str]:
    return {
        role_name: f"{nonce}-{index}-{secrets.token_urlsafe(32)}"
        for index, role_name in enumerate(spec.required_password_role_names)
    }


def _large_object_execute_privileges(
    connection: psycopg.Connection,
) -> list[tuple[str, bool]]:
    return connection.execute(
        """
        SELECT routine.oid::pg_catalog.regprocedure::text,
               pg_catalog.has_function_privilege(
                   CURRENT_USER, routine.oid, 'EXECUTE'
               )
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        WHERE namespace.nspname = 'pg_catalog'
          AND (
                pg_catalog.left(routine.proname::text, 3) = 'lo_'
             OR routine.proname::text IN ('loread', 'lowrite')
          )
        ORDER BY 1
        """
    ).fetchall()


def _backend_statistics_execute_privileges(
    connection: psycopg.Connection,
) -> list[tuple[str, bool]]:
    return connection.execute(
        """
        SELECT routine.oid::pg_catalog.regprocedure::text,
               pg_catalog.has_function_privilege(
                   CURRENT_USER, routine.oid, 'EXECUTE'
               )
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        WHERE namespace.nspname = 'pg_catalog'
          AND (
                pg_catalog.left(routine.proname::text, 20) =
                    'pg_stat_get_activity'
             OR pg_catalog.left(routine.proname::text, 20) =
                    'pg_stat_get_backend_'
          )
        ORDER BY 1
        """
    ).fetchall()


@pytest.fixture(scope="module")
def provisioned_services():
    tenant_admin = _admin_dsn(TENANT_ADMIN_ENV)
    audit_admin = _admin_dsn(AUDIT_ADMIN_ENV)
    tenant_spec = TENANT_PROVISIONING_SPEC
    audit_spec = SECURITY_AUDIT_PROVISIONING_SPEC
    _assert_clean_service(tenant_admin, tenant_spec.database_name)
    _assert_clean_service(audit_admin, audit_spec.database_name)

    nonce = secrets.token_urlsafe(16)
    tenant_passwords = _passwords(tenant_spec, "tenant-" + nonce)
    audit_passwords = _passwords(audit_spec, "audit-" + nonce)
    try:
        tenant = provision_service(
            tenant_admin, tenant_spec, login_passwords=tenant_passwords
        )
        audit = provision_service(
            audit_admin, audit_spec, login_passwords=audit_passwords
        )
        yield {
            "tenantAdmin": tenant_admin,
            "auditAdmin": audit_admin,
            "tenantPasswords": tenant_passwords,
            "auditPasswords": audit_passwords,
            "tenant": tenant,
            "audit": audit,
        }
    finally:
        try:
            _destroy_test_service(audit_admin, audit_spec.database_name)
        finally:
            _destroy_test_service(tenant_admin, tenant_spec.database_name)


def test_provisioning_specs_freeze_distinct_service_and_role_boundaries():
    tenant = TENANT_PROVISIONING_SPEC
    audit = SECURITY_AUDIT_PROVISIONING_SPEC

    assert PROVISIONING_SPEC_DIGEST_POLICY == \
        "OFARM_POSTGRESQL_PROVISIONING_SPEC_V1"
    assert tenant.database_name == "ofarm_tenant"
    assert tenant.database_owner == tenant.schema_owner == "ofarm_owner"
    assert tenant.database_connection_limit == 48
    assert tenant.max_prepared_transactions == 0
    assert audit.database_name == "ofarm_security_audit"
    assert audit.database_owner == audit.schema_owner == \
        "ofarm_security_audit_owner"
    assert audit.database_connection_limit == 16
    assert audit.max_prepared_transactions == 0
    assert set(tenant.role_names) & set(audit.role_names) == {"ofarm_migrator"}
    assert len(tenant.public_execute_revoked_routines) == 21
    assert tenant.public_execute_revoked_routines == \
        audit.public_execute_revoked_routines
    assert tenant.large_object_routines == audit.large_object_routines
    assert tuple(
        (
            routine.name,
            routine.argument_types,
            routine.return_type,
            routine.internal_symbol,
        )
        for routine in tenant.large_object_routines
    ) == (
        ("lo_close", ("integer",), "integer", "be_lo_close"),
        ("lo_creat", ("integer",), "oid", "be_lo_creat"),
        ("lo_create", ("oid",), "oid", "be_lo_create"),
        ("lo_export", ("oid", "text"), "integer", "be_lo_export"),
        ("lo_from_bytea", ("oid", "bytea"), "oid", "be_lo_from_bytea"),
        ("lo_get", ("oid",), "bytea", "be_lo_get"),
        (
            "lo_get",
            ("oid", "bigint", "integer"),
            "bytea",
            "be_lo_get_fragment",
        ),
        ("lo_import", ("text",), "oid", "be_lo_import"),
        (
            "lo_import",
            ("text", "oid"),
            "oid",
            "be_lo_import_with_oid",
        ),
        (
            "lo_lseek",
            ("integer", "integer", "integer"),
            "integer",
            "be_lo_lseek",
        ),
        (
            "lo_lseek64",
            ("integer", "bigint", "integer"),
            "bigint",
            "be_lo_lseek64",
        ),
        ("lo_open", ("oid", "integer"), "integer", "be_lo_open"),
        ("lo_put", ("oid", "bigint", "bytea"), "void", "be_lo_put"),
        ("lo_tell", ("integer",), "integer", "be_lo_tell"),
        ("lo_tell64", ("integer",), "bigint", "be_lo_tell64"),
        (
            "lo_truncate",
            ("integer", "integer"),
            "integer",
            "be_lo_truncate",
        ),
        (
            "lo_truncate64",
            ("integer", "bigint"),
            "integer",
            "be_lo_truncate64",
        ),
        ("lo_unlink", ("oid",), "integer", "be_lo_unlink"),
        ("loread", ("integer", "integer"), "bytea", "be_loread"),
        ("lowrite", ("integer", "bytea"), "integer", "be_lowrite"),
    )
    assert tenant.backend_statistics_routines == \
        audit.backend_statistics_routines
    assert tuple(
        (
            routine.name,
            routine.argument_types,
            routine.return_type,
            routine.strict,
            routine.returns_set,
            routine.rows,
        )
        for routine in tenant.backend_statistics_routines
    ) == (
        (
            "pg_stat_get_activity",
            ("integer",),
            "SETOF record",
            False,
            True,
            100,
        ),
        (
            "pg_stat_get_backend_activity",
            ("integer",),
            "text",
            True,
            False,
            0,
        ),
        (
            "pg_stat_get_backend_activity_start",
            ("integer",),
            "timestamp with time zone",
            True,
            False,
            0,
        ),
        (
            "pg_stat_get_backend_client_addr",
            ("integer",),
            "inet",
            True,
            False,
            0,
        ),
        (
            "pg_stat_get_backend_client_port",
            ("integer",),
            "integer",
            True,
            False,
            0,
        ),
        (
            "pg_stat_get_backend_dbid",
            ("integer",),
            "oid",
            True,
            False,
            0,
        ),
        (
            "pg_stat_get_backend_idset",
            (),
            "SETOF integer",
            True,
            True,
            100,
        ),
        (
            "pg_stat_get_backend_pid",
            ("integer",),
            "integer",
            True,
            False,
            0,
        ),
        (
            "pg_stat_get_backend_start",
            ("integer",),
            "timestamp with time zone",
            True,
            False,
            0,
        ),
        (
            "pg_stat_get_backend_subxact",
            ("integer",),
            "record",
            True,
            False,
            0,
        ),
        (
            "pg_stat_get_backend_userid",
            ("integer",),
            "oid",
            True,
            False,
            0,
        ),
        (
            "pg_stat_get_backend_wait_event",
            ("integer",),
            "text",
            True,
            False,
            0,
        ),
        (
            "pg_stat_get_backend_wait_event_type",
            ("integer",),
            "text",
            True,
            False,
            0,
        ),
        (
            "pg_stat_get_backend_xact_start",
            ("integer",),
            "timestamp with time zone",
            True,
            False,
            0,
        ),
    )
    assert all(
        routine.internal_symbol == routine.name
        and routine.arguments == routine.identity_arguments
        for routine in tenant.backend_statistics_routines
    )
    assert hashlib.sha256(
        tenant.backend_statistics_routines[0].identity_arguments.encode()
    ).hexdigest() == \
        "29b842ee1387d47ed397e567d0d4d2ee82d6d1904cd7b9d1a2c25d7eddd1e3e1"
    assert tenant.backend_statistics_routines[9].identity_arguments == (
        "bid integer, OUT subxact_count integer, "
        "OUT subxact_overflowed boolean"
    )
    assert tenant.activity_view.select_roles == ("ofarm_backend_observer",)
    assert audit.activity_view.select_roles == ()
    assert tenant.activity_view.columns == audit.activity_view.columns
    assert len(tenant.activity_view.columns) == 22
    assert hashlib.sha256(
        tenant.activity_view.definition.encode()
    ).hexdigest() == \
        "17e431e33221426151a6ceb3eb2214b1abc51a7b9390d508603f233742deca28"
    assert tenant.digest == \
        "sha256:c222bbe5c4ea6c640a73179a70a0f3c657db8190dcc96772edd82c97437da06c"
    assert audit.digest == \
        "sha256:770165332bbdb7a5e67e468f021d9fe82df817a2aee1a8a70191a08e869c307a"
    assert next(
        role for role in tenant.roles if role.name == "ofarm_migrator"
    ).connection_limit == 2
    assert next(
        role for role in audit.roles if role.name == "ofarm_migrator"
    ).connection_limit == 2
    assert json.loads(tenant.canonical_manifest_bytes()) == tenant.manifest()
    assert json.loads(audit.canonical_manifest_bytes()) == audit.manifest()


def test_preledger_migration_lock_capsules_are_closed_and_service_owned():
    tenant = TENANT_PROVISIONING_SPEC
    audit = SECURITY_AUDIT_PROVISIONING_SPEC

    assert MIGRATION_LOCK_KEY_POLICY == "OFARM_POSTGRESQL_MIGRATION_LOCK_V1"
    assert provisioning_module._provisioning_lock_key() == \
        (-337509682, -1819990629)
    assert tenant.migration_lock.schema_name == \
        audit.migration_lock.schema_name == "ofarm_infrastructure"
    assert tenant.migration_lock.function_name == \
        audit.migration_lock.function_name == "take_migration_lock"
    assert tenant.migration_lock.execute_role == \
        audit.migration_lock.execute_role == "ofarm_migrator"
    assert (
        tenant.migration_lock.key_class_id,
        tenant.migration_lock.key_object_id,
    ) == (407601354, 2115981953)
    assert tenant.migration_lock.source == audit.migration_lock.source == (
        "SELECT pg_catalog.pg_advisory_xact_lock(407601354, 2115981953)"
    )
    assert tenant.migration_lock.owner_role == \
        "ofarm_tenant_migration_lock_owner"
    assert audit.migration_lock.owner_role == \
        "ofarm_security_audit_migration_lock_owner"
    for spec in (tenant, audit):
        owner = next(
            role for role in spec.roles
            if role.name == spec.migration_lock.owner_role
        )
        assert (owner.login, owner.inherit, owner.bypass_rls) == \
            (False, False, False)
        assert all(
            spec.migration_lock.owner_role not in (
                edge.granted_role,
                edge.member_role,
            )
            for edge in spec.memberships
        )


def test_tenant_write_lock_owner_and_one_time_owner_sealer_are_closed():
    tenant = TENANT_PROVISIONING_SPEC
    audit = SECURITY_AUDIT_PROVISIONING_SPEC
    tenant_lock = tenant.tenant_write_lock
    admission_lock = tenant.tenant_admission_lock
    sealer = tenant.tenant_initial_owner_sealer

    assert tenant_lock is not None
    assert (
        tenant_lock.schema_name,
        tenant_lock.function_name,
        tenant_lock.owner_role,
    ) == ("ofarm", "take_tenant_write_lock", "ofarm_tenant_lock_owner")
    lock_owner = next(
        role for role in tenant.roles if role.name == tenant_lock.owner_role
    )
    assert (
        lock_owner.login,
        lock_owner.inherit,
        lock_owner.bypass_rls,
        lock_owner.connection_limit,
    ) == (False, False, False, -1)
    assert all(
        tenant_lock.owner_role not in (edge.granted_role, edge.member_role)
        for edge in tenant.memberships
    )

    assert admission_lock is not None
    assert (
        admission_lock.shared_owner_role,
        admission_lock.exclusive_owner_role,
        admission_lock.key_class_id,
        admission_lock.key_object_id,
    ) == (
        "ofarm_binder",
        "ofarm_admission_lock_owner",
        1330004306,
        1413694001,
    )
    for owner_name in (
        admission_lock.shared_owner_role,
        admission_lock.exclusive_owner_role,
    ):
        owner = next(role for role in tenant.roles if role.name == owner_name)
        assert (
            owner.login,
            owner.inherit,
            owner.connection_limit,
        ) == (False, False, -1)
        assert all(
            owner_name not in (edge.granted_role, edge.member_role)
            for edge in tenant.memberships
        )

    assert sealer is not None
    assert (
        sealer.qualified_function,
        sealer.execute_role,
        sealer.target_schema_name,
    ) == (
        "ofarm_infrastructure.seal_tenant_routine_owners",
        "ofarm_migrator",
        "ofarm",
    )
    assert {
        (item.qualified_identity, item.owner_role) for item in sealer.transfers
    } == {
        ("ofarm.create_tenant_challenge()", "ofarm_binder"),
        ("ofarm.bind_tenant_capability(text)", "ofarm_binder"),
        ("ofarm.current_tenant_context()", "ofarm_binder"),
        (
            "ofarm.verify_tenant_capability_preflight(bytea, bytea)",
            "ofarm_binder",
        ),
        (
            "ofarm.fold_principal_binding_authority(text, text, text)",
            "ofarm_admission_lock_owner",
        ),
        (
            "ofarm.fold_tenant_capability_key_lifecycle(text)",
            "ofarm_admission_lock_owner",
        ),
        (
            "ofarm.transition_principal_binding("
            "text, text, text, uuid, text, uuid, text, text, uuid, text, "
            "uuid, text, uuid, text, text, text, text, text, text, text, "
            "timestamp with time zone, timestamp with time zone, uuid, "
            "timestamp with time zone, timestamp with time zone, text, text)",
            "ofarm_admission_lock_owner",
        ),
        (
            "ofarm.rebuild_principal_binding_current()",
            "ofarm_admission_lock_owner",
        ),
        (
            "ofarm.register_tenant_capability_key(bytea, text, text)",
            "ofarm_admission_lock_owner",
        ),
        (
            "ofarm.verify_tenant_capability_candidate_preflight(text, bytea)",
            "ofarm_admission_lock_owner",
        ),
        (
            "ofarm.activate_tenant_capability_key("
            "text, uuid, text, text, text, text, text)",
            "ofarm_admission_lock_owner",
        ),
        (
            "ofarm.rotate_tenant_capability_key("
            "text, text, uuid, text, text, text, text, text)",
            "ofarm_admission_lock_owner",
        ),
        (
            "ofarm.close_tenant_capability_admission("
            "uuid, text, text, text, text, text)",
            "ofarm_admission_lock_owner",
        ),
        (
            "ofarm.revoke_tenant_capability_key("
            "text, uuid, text, uuid, uuid, text, text, text)",
            "ofarm_admission_lock_owner",
        ),
        (
            "ofarm.resume_tenant_capability_admission("
            "uuid, text, uuid, uuid, text, text, text)",
            "ofarm_admission_lock_owner",
        ),
        (
            "ofarm.rebuild_tenant_capability_keyring()",
            "ofarm_admission_lock_owner",
        ),
        (
            "ofarm.observe_tenant_capability_key(text)",
            "ofarm_admission_lock_owner",
        ),
        ("ofarm.current_tenant_id()", "ofarm_binder"),
        ("ofarm.current_backend_start()", "ofarm_backend_observer"),
        (
            "ofarm.backend_incarnation_is_live(integer, timestamp with time zone)",
            "ofarm_backend_observer",
        ),
        ("ofarm.validate_promotion_edge()", "ofarm_graph_validator"),
        (
            "ofarm.require_promotion_reachability()",
            "ofarm_graph_validator",
        ),
        ("ofarm.take_tenant_write_lock()", "ofarm_tenant_lock_owner"),
    }
    assert set(
        (item.function_name, item.argument_types) for item in sealer.transfers
    ).issuperset(
        (routine.name, routine.argument_types)
        for routine in TENANT_CONTEXT_ROUTINE_SIGNATURES
    )
    assert sealer.source.startswith(
        "BEGIN GRANT CREATE ON SCHEMA ofarm TO "
        "ofarm_binder, ofarm_admission_lock_owner, ofarm_backend_observer, "
        "ofarm_graph_validator, ofarm_tenant_lock_owner;"
    )
    assert sealer.source.endswith(
        "REVOKE CREATE ON SCHEMA ofarm_infrastructure FROM ofarm_migrator; END"
    )
    assert audit.tenant_write_lock is None
    assert audit.tenant_initial_owner_sealer is None


def test_schema_local_catalog_classifier_is_one_exact_postgresql_17_10_list():
    assert tuple(item.category for item in SCHEMA_LOCAL_CATALOG_CLASSES) == (
        "relation",
        "routine",
        "type",
        "collation",
        "operator",
        "operator_class",
        "operator_family",
        "conversion",
        "text_search_config",
        "text_search_dictionary",
        "text_search_parser",
        "text_search_template",
        "statistics",
    )
    for item in SCHEMA_LOCAL_CATALOG_CLASSES:
        assert SCHEMA_LOCAL_OBJECT_SELECTS_SQL.count(
            f"SELECT '{item.category}'"
        ) == 1
        assert SCHEMA_LOCAL_OBJECT_SELECTS_SQL.count(
            f"FROM pg_catalog.{item.catalog_name} AS object_name"
        ) == 1
        assert SCHEMA_LOCAL_OBJECT_SELECTS_SQL.count(
            f"object_name.{item.name_column}::text"
        ) == 1
        assert SCHEMA_LOCAL_OBJECT_SELECTS_SQL.count(
            f"object_name.{item.namespace_column}"
        ) == 1


class _IdentityCursor:
    def __init__(self, row: tuple[object, ...]):
        self._row = row

    def fetchone(self) -> tuple[object, ...]:
        return self._row


class _IdentityConnection:
    def __init__(self, row: tuple[object, ...]):
        self._row = row

    def execute(self, _statement: str) -> _IdentityCursor:
        return _IdentityCursor(self._row)


def _dba_identity_row(
    server_version_num: int,
    server_version: str = SUPPORTED_POSTGRESQL_SERVER_VERSION,
) -> tuple[object, ...]:
    return (
        "postgres",
        True,
        server_version_num,
        server_version,
        "123456789",
        TENANT_PROVISIONING_SPEC.scram_iterations,
        False,
        "off",
    )


def test_provisioning_accepts_only_the_tested_postgresql_17_10_build():
    assert SUPPORTED_POSTGRESQL_VERSION == "17.10"
    assert SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM == 170010
    assert (
        SUPPORTED_POSTGRESQL_SERVER_VERSION
        == "17.10 (Debian 17.10-1.pgdg13+1)"
    )
    accepted = provisioning_module._require_dba(
        _IdentityConnection(_dba_identity_row(170010)),
        TENANT_PROVISIONING_SPEC,
    )
    assert accepted.server_version_num == 170010
    assert accepted.server_version == SUPPORTED_POSTGRESQL_SERVER_VERSION

    for refused_version in (170000, 170009, 170011, 179999):
        with pytest.raises(
            ProvisioningTargetError,
            match="requires exact PostgreSQL build",
        ):
            provisioning_module._require_dba(
                _IdentityConnection(_dba_identity_row(refused_version)),
                TENANT_PROVISIONING_SPEC,
            )

    with pytest.raises(
        ProvisioningTargetError,
        match="requires exact PostgreSQL build",
    ):
        provisioning_module._require_dba(
            _IdentityConnection(_dba_identity_row(170010, "17.10")),
            TENANT_PROVISIONING_SPEC,
        )


def test_target_identity_accepts_only_the_same_exact_postgresql_build():
    expected = provisioning_module._PostgresIdentity(
        database_name="postgres",
        system_identifier="123456789",
        server_version_num=SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
        server_version=SUPPORTED_POSTGRESQL_SERVER_VERSION,
    )
    row = (
        TENANT_PROVISIONING_SPEC.database_name,
        expected.system_identifier,
        expected.server_version_num,
        expected.server_version,
        False,
        "off",
    )
    accepted = provisioning_module._target_identity(
        _IdentityConnection(row),
        TENANT_PROVISIONING_SPEC,
        expected,
    )
    assert accepted.server_version == SUPPORTED_POSTGRESQL_SERVER_VERSION

    wrong_build = (*row[0:3], "17.10", *row[4:])
    with pytest.raises(
        ProvisioningTargetError,
        match="admin and target PostgreSQL builds differ",
    ):
        provisioning_module._target_identity(
            _IdentityConnection(wrong_build),
            TENANT_PROVISIONING_SPEC,
            expected,
        )


def test_infrastructure_report_cannot_claim_a_migration_phase():
    report = ProvisioningInfrastructureReport(
        service_identity=TENANT_PROVISIONING_SPEC.identity,
        provisioning_spec_digest=TENANT_PROVISIONING_SPEC.digest,
        database_name=TENANT_PROVISIONING_SPEC.database_name,
        system_identifier="123",
        server_version_num=170009,
    )

    assert not hasattr(report, "migration_ledger_present")
    assert report.manifest()["migrationPhaseVerified"] is False


def test_binder_and_runtime_memberships_are_closed():
    tenant = TENANT_PROVISIONING_SPEC
    binder = next(role for role in tenant.roles if role.name == "ofarm_binder")

    assert (binder.login, binder.inherit, binder.bypass_rls) == (False, False, True)
    assert all(
        "ofarm_binder" not in (edge.granted_role, edge.member_role)
        for edge in tenant.memberships
    )
    assert {
        (
            edge.granted_role,
            edge.member_role,
            edge.inherit,
            edge.set_role,
            edge.admin,
        )
        for edge in tenant.memberships
    } == {
        ("ofarm_owner", "ofarm_migrator", False, True, False),
        (
            "ofarm_tenant_registrar",
            "ofarm_tenant_control_login",
            True,
            False,
            False,
        ),
        (
            "ofarm_identity_writer",
            "ofarm_identity_control_login",
            True,
            False,
            False,
        ),
        (
            "ofarm_capability_key_controller",
            "ofarm_capability_key_control_login",
            True,
            False,
            False,
        ),
        (
            "pg_read_all_stats",
            "ofarm_backend_observer",
            True,
            False,
            False,
        ),
    }

    observer = next(
        role for role in tenant.roles if role.name == "ofarm_backend_observer"
    )
    validator = next(
        role for role in tenant.roles if role.name == "ofarm_graph_validator"
    )
    assert (
        observer.login,
        observer.inherit,
        observer.bypass_rls,
        observer.connection_limit,
    ) == (False, True, False, -1)
    assert (
        validator.login,
        validator.inherit,
        validator.bypass_rls,
        validator.connection_limit,
    ) == (False, False, False, -1)
    assert "ofarm_graph_validator" in tenant.schema_usage_roles
    assert "ofarm_backend_observer" not in tenant.schema_usage_roles
    assert tenant.default_privilege_owner_roles == (
        "ofarm_owner",
        "ofarm_tenant_migration_lock_owner",
        "ofarm_tenant_lock_owner",
        "ofarm_binder",
        "ofarm_admission_lock_owner",
        "ofarm_backend_observer",
        "ofarm_graph_validator",
        "ofarm_crypto_installer",
    )


def test_audit_producer_map_and_break_glass_login_are_closed():
    spec = SECURITY_AUDIT_PROVISIONING_SPEC

    assert {
        (producer.login_role, producer.producer, producer.component)
        for producer in spec.audit_producers
    } == {
        (
            "ofarm_security_authentication_producer_login",
            "AUTHENTICATION_BOUNDARY_V1",
            "AUTHENTICATION",
        ),
        (
            "ofarm_security_request_router_producer_login",
            "REQUEST_ROUTER_BOUNDARY_V1",
            "REQUEST_ROUTER",
        ),
        (
            "ofarm_security_audit_control_login",
            "SECURITY_OPERATIONS_V1",
            "AUDIT_CONTROL",
        ),
        (
            "ofarm_security_audit_retention_login",
            "SECURITY_OPERATIONS_V1",
            "AUDIT_RETENTION",
        ),
    }
    assert "ofarm_security_audit_export" in spec.role_names
    assert "ofarm_security_audit_export_login" not in spec.role_names
    assert "ofarm_security_audit_export_login" in \
        spec.intentionally_absent_login_roles


def test_partial_target_refuses_without_repair_or_creation():
    admin_dsn = _admin_dsn(TENANT_ADMIN_ENV)
    spec = TENANT_PROVISIONING_SPEC
    _assert_clean_service(admin_dsn, spec.database_name)
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute("CREATE ROLE ofarm_owner NOLOGIN")
    try:
        with pytest.raises(ProvisioningTargetError, match="not provably new"):
            provision_service(admin_dsn, spec, login_passwords=_passwords(spec, "x"))
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            assert connection.execute(
                "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'ofarm_owner'"
            ).fetchone() == (1,)
            assert connection.execute(
                "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
                (spec.database_name,),
            ).fetchone() is None
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute("DROP ROLE ofarm_owner")


def test_unrelated_database_refuses_before_any_provisioning_write():
    admin_dsn = _admin_dsn(TENANT_ADMIN_ENV)
    spec = TENANT_PROVISIONING_SPEC
    _assert_clean_service(admin_dsn, spec.database_name)
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute("CREATE DATABASE unrelated_scratch")
        before = connection.execute(
            "SELECT datacl::text FROM pg_catalog.pg_database "
            "WHERE datname = 'unrelated_scratch'"
        ).fetchone()
    try:
        with pytest.raises(ProvisioningTargetError, match="database inventory"):
            provision_service(admin_dsn, spec, login_passwords=_passwords(spec, "x"))
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            after = connection.execute(
                "SELECT datacl::text FROM pg_catalog.pg_database "
                "WHERE datname = 'unrelated_scratch'"
            ).fetchone()
            assert after == before
            assert connection.execute(
                r"""
                SELECT rolname::text
                FROM pg_catalog.pg_roles
                WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
                """
            ).fetchall() == []
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute("DROP DATABASE unrelated_scratch")


def test_changed_maintenance_acl_refuses_before_any_provisioning_write():
    admin_dsn = _admin_dsn(TENANT_ADMIN_ENV)
    spec = TENANT_PROVISIONING_SPEC
    _assert_clean_service(admin_dsn, spec.database_name)
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute("REVOKE CONNECT ON DATABASE postgres FROM PUBLIC")
    try:
        with pytest.raises(
            ProvisioningTargetError, match="maintenance database ACL posture"
        ):
            provision_service(admin_dsn, spec, login_passwords=_passwords(spec, "x"))
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            assert connection.execute(
                r"""
                SELECT rolname::text
                FROM pg_catalog.pg_roles
                WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
                """
            ).fetchall() == []
            assert connection.execute(
                "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
                (spec.database_name,),
            ).fetchone() is None
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute("GRANT CONNECT ON DATABASE postgres TO PUBLIC")


def test_provision_and_verify_fix_catalog_output_settings_before_observation():
    admin_dsn = _admin_dsn(TENANT_ADMIN_ENV)
    spec = TENANT_PROVISIONING_SPEC
    _assert_clean_service(admin_dsn, spec.database_name)
    parameters = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    parameters["options"] = (
        "-c quote_all_identifiers=on "
        "-c TimeZone=Pacific/Honolulu "
        "-c DateStyle=SQL,DMY "
        "-c standard_conforming_strings=off"
    )
    hostile_admin_dsn = psycopg.conninfo.make_conninfo(**parameters)
    try:
        created = provision_service(
            hostile_admin_dsn,
            spec,
            login_passwords=_passwords(spec, "hostile-catalog-output"),
        )
        verified = verify_service(hostile_admin_dsn, spec)
        infrastructure = verify_service_infrastructure(
            hostile_admin_dsn, spec
        )

        assert created.created is True
        assert verified.created is False
        assert infrastructure.provisioning_spec_digest == spec.digest
    finally:
        _destroy_test_service(admin_dsn, spec.database_name)


def test_real_services_create_once_then_verify_as_read_only_noops(
    provisioned_services,
):
    first_tenant = provisioned_services["tenant"]
    first_audit = provisioned_services["audit"]

    assert first_tenant.created is True
    assert first_audit.created is True
    assert first_tenant.migration_ledger_present is False
    assert first_audit.migration_ledger_present is False
    second_tenant = provision_service(
        provisioned_services["tenantAdmin"], TENANT_PROVISIONING_SPEC
    )
    second_audit = verify_service(
        provisioned_services["auditAdmin"], SECURITY_AUDIT_PROVISIONING_SPEC
    )
    assert second_tenant == replace(first_tenant, created=False)
    assert second_audit == replace(first_audit, created=False)

    separation = verify_provisioned_cluster_lineages(
        provisioned_services["tenantAdmin"], provisioned_services["auditAdmin"]
    )
    assert separation.tenant_system_identifier != separation.audit_system_identifier
    assert separation.manifest()["distinct"] is True


def test_same_cluster_lineage_refuses_as_audit_service(
    provisioned_services, monkeypatch
):
    tenant = provisioned_services["tenant"]
    crossed_audit = replace(
        tenant,
        service_identity=SECURITY_AUDIT_PROVISIONING_SPEC.identity,
        provisioning_spec_digest=SECURITY_AUDIT_PROVISIONING_SPEC.digest,
        database_name=SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
    )

    def fake_verify(_admin_dsn, spec):
        if spec is TENANT_PROVISIONING_SPEC:
            return tenant
        return crossed_audit

    monkeypatch.setattr(provisioning_module, "verify_service", fake_verify)
    with pytest.raises(ProvisioningTargetError, match="system identifier"):
        verify_provisioned_cluster_lineages("tenant-admin", "audit-admin")


def test_one_cluster_global_lock_serializes_both_specs(provisioned_services):
    admin_dsn = provisioned_services["tenantAdmin"]
    with psycopg.connect(admin_dsn, autocommit=True) as holder:
        lock_key = provisioning_module._acquire_lock(holder)
        try:
            with pytest.raises(ProvisioningTargetError, match="another provisioner"):
                verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
            with pytest.raises(ProvisioningTargetError, match="another provisioner"):
                provision_service(
                    admin_dsn,
                    SECURITY_AUDIT_PROVISIONING_SPEC,
                    login_passwords=_passwords(
                        SECURITY_AUDIT_PROVISIONING_SPEC, "cross-spec"
                    ),
                )
        finally:
            provisioning_module._release_lock(holder, lock_key)


def test_catalog_verification_uses_one_repeatable_read_snapshot(
    provisioned_services, monkeypatch
):
    observed_transactions = []
    original_role_differences = provisioning_module._role_differences

    def observe_transaction(connection, spec):
        observed_transactions.append(
            connection.execute(
                """
                SELECT pg_catalog.current_database(),
                       pg_catalog.current_setting('transaction_isolation'),
                       pg_catalog.current_setting('transaction_read_only')
                """
            ).fetchone()
        )
        return original_role_differences(connection, spec)

    monkeypatch.setattr(
        provisioning_module, "_role_differences", observe_transaction
    )
    verify_service(
        provisioned_services["tenantAdmin"], TENANT_PROVISIONING_SPEC
    )
    assert observed_transactions == [
        (TENANT_PROVISIONING_SPEC.database_name, "repeatable read", "on")
    ]


def test_existing_role_drift_refuses_without_reconciliation(provisioned_services):
    admin_dsn = provisioned_services["tenantAdmin"]
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute("ALTER ROLE ofarm_app CONNECTION LIMIT 25")

        with pytest.raises(ProvisioningDriftError, match="role ofarm_app"):
            provision_service(admin_dsn, TENANT_PROVISIONING_SPEC)

        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            assert connection.execute(
                "SELECT rolconnlimit FROM pg_catalog.pg_roles "
                "WHERE rolname = 'ofarm_app'"
            ).fetchone() == (25,)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute("ALTER ROLE ofarm_app CONNECTION LIMIT 24")
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)


def test_backend_observer_membership_and_builtin_role_are_exact(
    provisioned_services,
):
    admin_dsn = provisioned_services["tenantAdmin"]
    membership = next(
        edge
        for edge in TENANT_PROVISIONING_SPEC.memberships
        if edge.member_role == "ofarm_backend_observer"
    )
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(
                "REVOKE pg_read_all_stats FROM ofarm_backend_observer"
            )
        with pytest.raises(ProvisioningDriftError, match="membership"):
            verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            provisioning_module._create_membership(connection, membership)
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)

    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        with pytest.raises(
            psycopg.errors.ReservedName,
            match="Cannot alter reserved roles",
        ):
            connection.execute("ALTER ROLE pg_read_all_stats NOINHERIT")
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)


def test_scram_verifiers_are_exact_cost_and_never_contain_plaintext(
    provisioned_services,
):
    admin_dsn = provisioned_services["tenantAdmin"]
    passwords = provisioned_services["tenantPasswords"]
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        rows = connection.execute(
            """
            SELECT role.rolname::text, auth.rolpassword
            FROM pg_catalog.pg_roles AS role
            JOIN pg_catalog.pg_authid AS auth ON auth.oid = role.oid
            WHERE role.rolname::text = ANY (%s::text[])
            ORDER BY role.rolname
            """,
            (list(TENANT_PROVISIONING_SPEC.login_role_names),),
        ).fetchall()
    assert {row[0] for row in rows} == set(
        TENANT_PROVISIONING_SPEC.login_role_names
    )
    verifier_pattern = re.compile(
        r"^SCRAM-SHA-256\$4096:[A-Za-z0-9+/]+={0,2}"
        r"\$[A-Za-z0-9+/]+={0,2}:[A-Za-z0-9+/]+={0,2}$"
    )
    for role_name, verifier in rows:
        assert verifier_pattern.fullmatch(verifier)
        assert passwords[role_name] not in verifier


def test_generated_scram_verifier_authenticates_only_the_expected_password(
    provisioned_services,
):
    role_name = "ofarm_app"
    correct_dsn = _tcp_database_dsn(
        provisioned_services["tenantAdmin"],
        TENANT_PROVISIONING_SPEC.database_name,
        user=role_name,
        password=provisioned_services["tenantPasswords"][role_name],
    )
    with psycopg.connect(correct_dsn) as connection:
        assert connection.execute(
            "SELECT SESSION_USER, CURRENT_USER"
        ).fetchone() == (role_name, role_name)

    wrong_dsn = _tcp_database_dsn(
        provisioned_services["tenantAdmin"],
        TENANT_PROVISIONING_SPEC.database_name,
        user=role_name,
        password="wrong-password-that-is-long-but-still-wrong",
    )
    with pytest.raises(
        psycopg.OperationalError, match="password authentication failed"
    ):
        psycopg.connect(wrong_dsn)


def test_split_admin_and_target_routes_refuse_before_catalog_verification(
    provisioned_services, monkeypatch
):
    tenant_admin = provisioned_services["tenantAdmin"]
    audit_admin = provisioned_services["auditAdmin"]
    database_name = TENANT_PROVISIONING_SPEC.database_name
    original_target_dsn = provisioning_module._target_dsn
    with psycopg.connect(audit_admin, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )

    def crossed_target_dsn(admin_dsn, requested_database):
        if admin_dsn == tenant_admin and requested_database == database_name:
            return _database_dsn(audit_admin, database_name)
        return original_target_dsn(admin_dsn, requested_database)

    monkeypatch.setattr(provisioning_module, "_target_dsn", crossed_target_dsn)
    try:
        with pytest.raises(ProvisioningTargetError, match="different clusters"):
            verify_service(tenant_admin, TENANT_PROVISIONING_SPEC)
    finally:
        with psycopg.connect(audit_admin, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name))
            )


def test_parameter_and_global_default_drift_refuse_without_reconciliation(
    provisioned_services,
):
    admin_dsn = provisioned_services["tenantAdmin"]
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(
            "GRANT SET ON PARAMETER session_preload_libraries TO ofarm_app"
        )
    try:
        with pytest.raises(ProvisioningDriftError, match="parameter privileges"):
            verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(
                "REVOKE ALL ON PARAMETER session_preload_libraries FROM ofarm_app"
            )
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)

    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute("ALTER ROLE ALL SET synchronous_commit = off")
    try:
        with pytest.raises(ProvisioningDriftError, match="setting posture"):
            verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute("ALTER ROLE ALL RESET synchronous_commit")
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)


def test_external_maintenance_database_grantee_refuses(provisioned_services):
    admin_dsn = provisioned_services["tenantAdmin"]
    external_role = "issue174_external_operator"
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(external_role))
        )
        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE postgres TO {}").format(
                sql.Identifier(external_role)
            )
        )
    try:
        with pytest.raises(
            ProvisioningDriftError, match="maintenance database ACL posture"
        ):
            verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("REVOKE CONNECT ON DATABASE postgres FROM {}").format(
                    sql.Identifier(external_role)
                )
            )
            connection.execute(
                sql.SQL("DROP ROLE {}").format(sql.Identifier(external_role))
            )
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)


def test_fake_ledger_and_rogue_collation_both_refuse(provisioned_services):
    admin_dsn = provisioned_services["tenantAdmin"]
    target_dsn = _database_dsn(
        admin_dsn, TENANT_PROVISIONING_SPEC.database_name
    )
    with psycopg.connect(target_dsn, autocommit=True) as connection:
        connection.execute("CREATE TABLE ofarm.schema_migration (id integer)")
    try:
        with pytest.raises(
            ProvisioningDriftError, match="exact structural verification"
        ):
            verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute("DROP TABLE ofarm.schema_migration")
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
    with psycopg.connect(target_dsn, autocommit=True) as connection:
        connection.execute(
            "CREATE COLLATION ofarm.rogue "
            "(provider = builtin, locale = 'C')"
        )
    try:
        with pytest.raises(ProvisioningDriftError, match="unverified database objects"):
            verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute("DROP COLLATION ofarm.rogue")
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)


def test_fresh_audit_target_with_owner_created_rogue_collation_refuses(
    provisioned_services,
):
    admin_dsn = provisioned_services["auditAdmin"]
    spec = SECURITY_AUDIT_PROVISIONING_SPEC
    target_dsn = _database_dsn(admin_dsn, spec.database_name)
    with psycopg.connect(target_dsn, autocommit=True) as connection:
        connection.execute(
            sql.SQL("SET ROLE {}").format(sql.Identifier(spec.schema_owner))
        )
        connection.execute(
            sql.SQL(
                "CREATE COLLATION {}.rogue "
                "(provider = builtin, locale = 'C')"
            ).format(sql.Identifier(spec.schema_name))
        )
    try:
        with pytest.raises(
            ProvisioningDriftError,
            match="unverified database objects",
        ):
            verify_service(admin_dsn, spec)
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP COLLATION {}.rogue").format(
                    sql.Identifier(spec.schema_name)
                )
            )
    verify_service(admin_dsn, spec)


def test_acl_and_default_acl_drift_refuse_without_reconciliation(
    provisioned_services,
):
    admin_dsn = provisioned_services["tenantAdmin"]
    target_dsn = _database_dsn(
        admin_dsn, TENANT_PROVISIONING_SPEC.database_name
    )
    with psycopg.connect(target_dsn, autocommit=True) as connection:
        connection.execute(
            "GRANT EXECUTE ON FUNCTION "
            "pg_catalog.pg_try_advisory_lock(bigint) TO ofarm_app"
        )
    try:
        with pytest.raises(ProvisioningDriftError, match="advisory routine ACL"):
            verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
        with psycopg.connect(target_dsn, autocommit=True) as connection:
            assert connection.execute(
                "SELECT pg_catalog.has_function_privilege("
                "'ofarm_app', 'pg_catalog.pg_try_advisory_lock(bigint)', "
                "'EXECUTE')"
            ).fetchone() == (True,)
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute(
                "REVOKE EXECUTE ON FUNCTION "
                "pg_catalog.pg_try_advisory_lock(bigint) FROM ofarm_app"
            )
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)

    with psycopg.connect(target_dsn, autocommit=True) as connection:
        connection.execute("GRANT CREATE ON SCHEMA pg_catalog TO ofarm_app")
    try:
        with pytest.raises(ProvisioningDriftError, match="system-schema"):
            verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute("REVOKE CREATE ON SCHEMA pg_catalog FROM ofarm_app")
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)

    with psycopg.connect(target_dsn, autocommit=True) as connection:
        connection.execute("REVOKE USAGE ON SCHEMA pg_catalog FROM PUBLIC")
    try:
        with pytest.raises(ProvisioningDriftError, match="pg_catalog ACL"):
            verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
        with psycopg.connect(target_dsn, autocommit=True) as connection:
            assert connection.execute(
                "SELECT pg_catalog.has_schema_privilege("
                "'ofarm_app', 'pg_catalog', 'USAGE')"
            ).fetchone() == (False,)
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute("GRANT USAGE ON SCHEMA pg_catalog TO PUBLIC")
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)

    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute("GRANT CONNECT ON DATABASE postgres TO PUBLIC")
    try:
        with pytest.raises(ProvisioningDriftError, match="PUBLIC"):
            verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
        off_target_dsn = _database_dsn(
            admin_dsn,
            "postgres",
            user="ofarm_app",
            password=provisioned_services["tenantPasswords"]["ofarm_app"],
        )
        with psycopg.connect(off_target_dsn):
            pass
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute("REVOKE ALL ON DATABASE postgres FROM PUBLIC")
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)

    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute("GRANT CREATE ON TABLESPACE pg_default TO ofarm_app")
    try:
        with pytest.raises(ProvisioningDriftError, match="tablespace ACL"):
            verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            assert connection.execute(
                "SELECT pg_catalog.has_tablespace_privilege("
                "'ofarm_app', 'pg_default', 'CREATE')"
            ).fetchone() == (True,)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(
                "REVOKE CREATE ON TABLESPACE pg_default FROM ofarm_app"
            )
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)

    with psycopg.connect(target_dsn, autocommit=True) as connection:
        connection.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE ofarm_owner "
            "GRANT EXECUTE ON ROUTINES TO ofarm_app"
        )
    try:
        with pytest.raises(ProvisioningDriftError, match="default-privilege"):
            verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)
        with psycopg.connect(target_dsn, autocommit=True) as connection:
            assert connection.execute(
                """
                SELECT count(*)
                FROM pg_catalog.pg_default_acl AS defaults
                CROSS JOIN LATERAL
                     pg_catalog.aclexplode(defaults.defaclacl) AS acl
                JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
                WHERE grantee.rolname = 'ofarm_app'
                  AND acl.privilege_type = 'EXECUTE'
                """
            ).fetchone() == (1,)
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute(
                "ALTER DEFAULT PRIVILEGES FOR ROLE ofarm_owner "
                "REVOKE EXECUTE ON ROUTINES FROM ofarm_app"
            )
    verify_service(admin_dsn, TENANT_PROVISIONING_SPEC)


def test_no_governed_login_or_migration_owner_can_execute_large_object_api(
    provisioned_services,
):
    cases = (
        (
            TENANT_PROVISIONING_SPEC,
            provisioned_services["tenantAdmin"],
            provisioned_services["tenantPasswords"],
            "ofarm_app",
        ),
        (
            SECURITY_AUDIT_PROVISIONING_SPEC,
            provisioned_services["auditAdmin"],
            provisioned_services["auditPasswords"],
            "ofarm_security_authentication_producer_login",
        ),
    )
    for spec, admin_dsn, passwords, representative_runtime in cases:
        for role_name, password in passwords.items():
            role_dsn = _database_dsn(
                admin_dsn,
                spec.database_name,
                user=role_name,
                password=password,
            )
            with psycopg.connect(role_dsn, autocommit=True) as connection:
                privileges = _large_object_execute_privileges(connection)
                assert len(privileges) == 20
                assert not any(allowed for _routine, allowed in privileges)
                if role_name == "ofarm_migrator":
                    connection.execute(
                        sql.SQL("SET ROLE {}").format(
                            sql.Identifier(spec.schema_owner)
                        )
                    )
                    owner_privileges = _large_object_execute_privileges(connection)
                    assert len(owner_privileges) == 20
                    assert not any(
                        allowed for _routine, allowed in owner_privileges
                    )
                    connection.execute("RESET ROLE")

        runtime_dsn = _database_dsn(
            admin_dsn,
            spec.database_name,
            user=representative_runtime,
            password=passwords[representative_runtime],
        )
        with psycopg.connect(runtime_dsn, autocommit=True) as runtime:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                runtime.execute(
                    "SELECT pg_catalog.lo_create(0::pg_catalog.oid)"
                )


def test_large_object_acl_property_inventory_and_storage_tamper_refuse(
    provisioned_services,
):
    cases = (
        (
            TENANT_PROVISIONING_SPEC,
            provisioned_services["tenantAdmin"],
            provisioned_services["tenantPasswords"],
        ),
        (
            SECURITY_AUDIT_PROVISIONING_SPEC,
            provisioned_services["auditAdmin"],
            provisioned_services["auditPasswords"],
        ),
    )
    for spec, admin_dsn, passwords in cases:
        target_dsn = _database_dsn(admin_dsn, spec.database_name)

        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute(
                "GRANT EXECUTE ON FUNCTION "
                "pg_catalog.lo_create(pg_catalog.oid) TO PUBLIC"
            )
        try:
            with pytest.raises(
                ProvisioningDriftError,
                match="large-object routine ACL",
            ):
                verify_service(admin_dsn, spec)
        finally:
            with psycopg.connect(target_dsn, autocommit=True) as connection:
                connection.execute(
                    "REVOKE EXECUTE ON FUNCTION "
                    "pg_catalog.lo_create(pg_catalog.oid) FROM PUBLIC"
                )
        verify_service(admin_dsn, spec)

        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute(
                "ALTER FUNCTION pg_catalog.lo_tell(pg_catalog.int4) COST 2"
            )
        try:
            with pytest.raises(
                ProvisioningDriftError,
                match="large-object routine security",
            ):
                verify_service(admin_dsn, spec)
        finally:
            with psycopg.connect(target_dsn, autocommit=True) as connection:
                connection.execute(
                    "ALTER FUNCTION pg_catalog.lo_tell(pg_catalog.int4) COST 1"
                )
        verify_service(admin_dsn, spec)

        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute(
                "ALTER FUNCTION pg_catalog.lo_tell(pg_catalog.int4) "
                "RENAME TO lo_issue174_extra_tell"
            )
        try:
            with pytest.raises(
                ProvisioningDriftError,
                match="large-object routine inventory",
            ):
                verify_service(admin_dsn, spec)
        finally:
            with psycopg.connect(target_dsn, autocommit=True) as connection:
                connection.execute(
                    "ALTER FUNCTION "
                    "pg_catalog.lo_issue174_extra_tell(pg_catalog.int4) "
                    "RENAME TO lo_tell"
                )
        verify_service(admin_dsn, spec)

        large_object_oid: int | None = None
        try:
            with psycopg.connect(target_dsn, autocommit=True) as connection:
                large_object_oid = connection.execute(
                    "SELECT pg_catalog.lo_create(0::pg_catalog.oid)"
                ).fetchone()[0]
            with pytest.raises(
                ProvisioningDriftError,
                match="large-object metadata row count",
            ):
                verify_service(admin_dsn, spec)

            migrator_dsn = _database_dsn(
                admin_dsn,
                spec.database_name,
                user="ofarm_migrator",
                password=passwords["ofarm_migrator"],
            )
            with psycopg.connect(migrator_dsn, autocommit=True) as migrator:
                with migrator.transaction():
                    migrator.execute(
                        sql.SQL("SET LOCAL ROLE {}").format(
                            sql.Identifier(spec.schema_owner)
                        )
                    )
                    locked_differences = migration_locked_differences(
                        migrator, spec
                    )
            assert "large-object metadata row count differs" in \
                locked_differences
        finally:
            if large_object_oid is not None:
                with psycopg.connect(
                    target_dsn, autocommit=True
                ) as connection:
                    assert connection.execute(
                        "SELECT pg_catalog.lo_unlink(%s::pg_catalog.oid)",
                        (large_object_oid,),
                    ).fetchone() == (1,)
        verify_service(admin_dsn, spec)


def test_backend_statistics_surface_is_exactly_role_scoped(
    provisioned_services,
):
    tenant_target_dsn = _database_dsn(
        provisioned_services["tenantAdmin"],
        TENANT_PROVISIONING_SPEC.database_name,
    )
    with psycopg.connect(tenant_target_dsn, autocommit=True) as admin:
        assert admin.execute(
            "SELECT pg_catalog.has_table_privilege("
            "'ofarm_backend_observer', 'pg_catalog.pg_stat_activity', "
            "'SELECT')"
        ).fetchone() == (True,)
        assert admin.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'ofarm_backend_observer', "
            "'pg_catalog.pg_stat_get_activity(integer)', 'EXECUTE')"
        ).fetchone() == (True,)
        for role_name in (
            "ofarm_binder",
            "ofarm_app",
            "ofarm_worker",
            "ofarm_tenant_registrar",
            "ofarm_identity_writer",
        ):
            assert admin.execute(
                "SELECT pg_catalog.has_table_privilege("
                "%s, 'pg_catalog.pg_stat_activity', 'SELECT'), "
                "pg_catalog.has_function_privilege("
                "%s, 'pg_catalog.pg_stat_get_activity(integer)', "
                "'EXECUTE')",
                (role_name, role_name),
            ).fetchone() == (False, False)

        admin.execute("SET ROLE ofarm_backend_observer")
        privileges = _backend_statistics_execute_privileges(admin)
        assert len(privileges) == 14
        assert [routine for routine, allowed in privileges if allowed] == [
            "pg_stat_get_activity(integer)"
        ]
        assert admin.execute(
            "SELECT pg_catalog.count(*) > 0 "
            "FROM pg_catalog.pg_stat_activity"
        ).fetchone() == (True,)
        assert admin.execute(
            "SELECT pg_catalog.count(*) > 0 "
            "FROM pg_catalog.pg_stat_get_activity(NULL::integer)"
        ).fetchone() == (True,)
        admin.execute("RESET ROLE")

    audit_target_dsn = _database_dsn(
        provisioned_services["auditAdmin"],
        SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
    )
    with psycopg.connect(audit_target_dsn, autocommit=True) as audit_admin:
        for role_name in SECURITY_AUDIT_PROVISIONING_SPEC.role_names:
            assert audit_admin.execute(
                "SELECT pg_catalog.has_table_privilege("
                "%s, 'pg_catalog.pg_stat_activity', 'SELECT')",
                (role_name,),
            ).fetchone() == (False,)
        function_acl_rows = audit_admin.execute(
            r"""
            SELECT pg_catalog.pg_get_userbyid(acl.grantee),
                   acl.privilege_type
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
                    pg_catalog.left(routine.proname::text, 20) =
                        'pg_stat_get_activity'
                 OR pg_catalog.left(routine.proname::text, 20) =
                        'pg_stat_get_backend_'
              )
              AND acl.grantee IN (
                    SELECT oid FROM pg_catalog.pg_roles
                    WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
              )
            """
        ).fetchall()
        assert function_acl_rows == []


def test_same_role_sessions_cannot_read_peer_sql_text_or_application_name(
    provisioned_services,
):
    admin_dsn = provisioned_services["tenantAdmin"]
    password = provisioned_services["tenantPasswords"]["ofarm_app"]
    peer_application_name = "issue174-peer-activity-secret"
    peer_sql_secret = "issue174_peer_sql_text_secret"
    peer_dsn = _database_dsn(
        admin_dsn,
        TENANT_PROVISIONING_SPEC.database_name,
        user="ofarm_app",
        password=password,
        application_name=peer_application_name,
    )
    reader_dsn = _database_dsn(
        admin_dsn,
        TENANT_PROVISIONING_SPEC.database_name,
        user="ofarm_app",
        password=password,
        application_name="issue174-peer-activity-reader",
    )
    target_admin_dsn = _database_dsn(
        admin_dsn, TENANT_PROVISIONING_SPEC.database_name
    )
    peer_connected = threading.Event()

    def run_peer_query() -> None:
        with psycopg.connect(peer_dsn, autocommit=True) as peer:
            peer_connected.set()
            peer.execute(
                "SELECT pg_catalog.pg_sleep(3), "
                f"'{peer_sql_secret}'::pg_catalog.text"
            ).fetchone()

    with ThreadPoolExecutor(max_workers=1) as executor:
        peer_future = executor.submit(run_peer_query)
        assert peer_connected.wait(timeout=2)
        with psycopg.connect(target_admin_dsn, autocommit=True) as admin:
            deadline = time.monotonic() + 2
            peer_row = None
            while time.monotonic() < deadline:
                peer_row = admin.execute(
                    "SELECT application_name, query "
                    "FROM pg_catalog.pg_stat_activity "
                    "WHERE application_name = %s",
                    (peer_application_name,),
                ).fetchone()
                if peer_row is not None and peer_sql_secret in peer_row[1]:
                    break
                time.sleep(0.025)
            assert peer_row is not None
            assert peer_row[0] == peer_application_name
            assert peer_sql_secret in peer_row[1]

        with psycopg.connect(reader_dsn, autocommit=True) as reader:
            privileges = _backend_statistics_execute_privileges(reader)
            assert len(privileges) == 14
            assert not any(allowed for _routine, allowed in privileges)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                reader.execute(
                    "SELECT application_name, query "
                    "FROM pg_catalog.pg_stat_activity"
                )
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                reader.execute(
                    "SELECT * FROM "
                    "pg_catalog.pg_stat_get_activity(NULL::integer)"
                )
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                reader.execute(
                    "SELECT pg_catalog.pg_stat_get_backend_activity(1)"
                )
        peer_future.result(timeout=5)


def test_backend_statistics_acl_property_and_inventory_tamper_refuse(
    provisioned_services,
):
    cases = (
        (
            TENANT_PROVISIONING_SPEC,
            provisioned_services["tenantAdmin"],
            "ofarm_app",
        ),
        (
            SECURITY_AUDIT_PROVISIONING_SPEC,
            provisioned_services["auditAdmin"],
            "ofarm_security_authentication_producer_login",
        ),
    )
    for spec, admin_dsn, runtime_role in cases:
        target_dsn = _database_dsn(admin_dsn, spec.database_name)

        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute(
                "GRANT SELECT ON TABLE pg_catalog.pg_stat_activity TO PUBLIC"
            )
        try:
            with pytest.raises(
                ProvisioningDriftError, match="pg_stat_activity view ACL"
            ):
                verify_service(admin_dsn, spec)
        finally:
            with psycopg.connect(target_dsn, autocommit=True) as connection:
                connection.execute(
                    "REVOKE SELECT ON TABLE "
                    "pg_catalog.pg_stat_activity FROM PUBLIC"
                )
        verify_service(admin_dsn, spec)

        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION "
                    "pg_catalog.pg_stat_get_backend_activity(pg_catalog.int4) "
                    "TO {}"
                ).format(sql.Identifier(runtime_role))
            )
        try:
            with pytest.raises(
                ProvisioningDriftError,
                match="backend-statistics routine ACL",
            ):
                verify_service(admin_dsn, spec)
        finally:
            with psycopg.connect(target_dsn, autocommit=True) as connection:
                connection.execute(
                    sql.SQL(
                        "REVOKE EXECUTE ON FUNCTION "
                        "pg_catalog.pg_stat_get_backend_activity("
                        "pg_catalog.int4) FROM {}"
                    ).format(sql.Identifier(runtime_role))
                )
        verify_service(admin_dsn, spec)

        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute(
                "ALTER FUNCTION "
                "pg_catalog.pg_stat_get_backend_activity(pg_catalog.int4) "
                "COST 2"
            )
        try:
            with pytest.raises(
                ProvisioningDriftError,
                match="backend-statistics routine properties",
            ):
                verify_service(admin_dsn, spec)
        finally:
            with psycopg.connect(target_dsn, autocommit=True) as connection:
                connection.execute(
                    "ALTER FUNCTION "
                    "pg_catalog.pg_stat_get_backend_activity("
                    "pg_catalog.int4) COST 1"
                )
        verify_service(admin_dsn, spec)

        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute(
                "ALTER FUNCTION "
                "pg_catalog.pg_stat_get_backend_wait_event(pg_catalog.int4) "
                "RENAME TO pg_stat_get_backend_issue174_extra"
            )
        try:
            with pytest.raises(
                ProvisioningDriftError,
                match="backend-statistics routine inventory",
            ):
                verify_service(admin_dsn, spec)
        finally:
            with psycopg.connect(target_dsn, autocommit=True) as connection:
                connection.execute(
                    "ALTER FUNCTION pg_catalog."
                    "pg_stat_get_backend_issue174_extra(pg_catalog.int4) "
                    "RENAME TO pg_stat_get_backend_wait_event"
                )
        verify_service(admin_dsn, spec)

        with psycopg.connect(target_dsn, autocommit=True) as connection:
            connection.execute(
                "ALTER VIEW pg_catalog.pg_stat_activity "
                "SET (security_barrier = true)"
            )
        try:
            with pytest.raises(
                ProvisioningDriftError,
                match="pg_stat_activity view properties",
            ):
                verify_service(admin_dsn, spec)
        finally:
            with psycopg.connect(target_dsn, autocommit=True) as connection:
                connection.execute(
                    "ALTER VIEW pg_catalog.pg_stat_activity "
                    "RESET (security_barrier)"
                )
        verify_service(admin_dsn, spec)


def test_runtime_logins_cannot_create_or_assume_capability_roles(
    provisioned_services,
):
    tenant_admin = provisioned_services["tenantAdmin"]
    tenant_password = provisioned_services["tenantPasswords"]["ofarm_app"]
    app_dsn = _database_dsn(
        tenant_admin,
        TENANT_PROVISIONING_SPEC.database_name,
        user="ofarm_app",
        password=tenant_password,
    )
    with psycopg.connect(app_dsn, autocommit=True) as application:
        advisory_privileges = application.execute(
            """
            SELECT routine.oid::regprocedure::text,
                   pg_catalog.has_function_privilege(
                       CURRENT_USER, routine.oid, 'EXECUTE')
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            WHERE namespace.nspname = 'pg_catalog'
              AND (
                    routine.proname LIKE 'pg_advisory_%'
                 OR routine.proname LIKE 'pg_try_advisory_%'
              )
            ORDER BY 1
            """
        ).fetchall()
        assert len(advisory_privileges) == 21
        assert not any(allowed for _routine, allowed in advisory_privileges)
        assert application.execute(
            "SELECT pg_catalog.pg_has_role(CURRENT_USER, 'ofarm_owner', 'SET')"
        ).fetchone() == (False,)
        assert application.execute(
            "SELECT pg_catalog.pg_has_role(CURRENT_USER, 'ofarm_binder', 'SET')"
        ).fetchone() == (False,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            application.execute("CREATE TEMPORARY TABLE forbidden_temp (id integer)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            application.execute("CREATE TABLE ofarm.forbidden_table (id integer)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            application.execute("SET ROLE ofarm_owner")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            application.execute(
                "SELECT pg_catalog.pg_try_advisory_lock(1::bigint)"
            )

    for off_target_database in ("postgres", "template1"):
        off_target_dsn = _database_dsn(
            tenant_admin,
            off_target_database,
            user="ofarm_app",
            password=tenant_password,
        )
        with pytest.raises(psycopg.OperationalError, match="permission denied"):
            psycopg.connect(off_target_dsn)

    worker_dsn = _database_dsn(
        tenant_admin,
        TENANT_PROVISIONING_SPEC.database_name,
        user="ofarm_worker",
        password=provisioned_services["tenantPasswords"]["ofarm_worker"],
    )
    with psycopg.connect(worker_dsn, autocommit=True) as worker:
        assert worker.execute(
            "SELECT pg_catalog.has_function_privilege("
            "CURRENT_USER, 'pg_catalog.pg_try_advisory_xact_lock(bigint)', "
            "'EXECUTE')"
        ).fetchone() == (False,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            worker.execute(
                "SELECT pg_catalog.pg_try_advisory_xact_lock(1::bigint)"
            )

    audit_admin = provisioned_services["auditAdmin"]
    producer_name = "ofarm_security_authentication_producer_login"
    producer_dsn = _database_dsn(
        audit_admin,
        SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
        user=producer_name,
        password=provisioned_services["auditPasswords"][producer_name],
    )
    with psycopg.connect(producer_dsn, autocommit=True) as producer:
        assert producer.execute(
            "SELECT pg_catalog.pg_has_role("
            "CURRENT_USER, 'ofarm_security_audit_ingest', 'USAGE')"
        ).fetchone() == (True,)
        assert producer.execute(
            "SELECT pg_catalog.pg_has_role("
            "CURRENT_USER, 'ofarm_security_audit_ingest', 'SET')"
        ).fetchone() == (False,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            producer.execute("SET ROLE ofarm_security_audit_ingest")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            producer.execute("CREATE TEMPORARY TABLE forbidden_temp (id integer)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            producer.execute(
                "SELECT pg_catalog.pg_try_advisory_lock(1::bigint)"
            )
    audit_off_target_dsn = _database_dsn(
        audit_admin,
        "postgres",
        user=producer_name,
        password=provisioned_services["auditPasswords"][producer_name],
    )
    with pytest.raises(psycopg.OperationalError, match="permission denied"):
        psycopg.connect(audit_off_target_dsn)


def test_only_migrator_can_reach_the_fixed_migration_lock_wrapper(
    provisioned_services,
):
    cases = (
        (
            TENANT_PROVISIONING_SPEC,
            provisioned_services["tenantAdmin"],
            provisioned_services["tenantPasswords"],
            "ofarm_app",
        ),
        (
            SECURITY_AUDIT_PROVISIONING_SPEC,
            provisioned_services["auditAdmin"],
            provisioned_services["auditPasswords"],
            "ofarm_security_authentication_producer_login",
        ),
    )
    for spec, admin_dsn, passwords, runtime_role in cases:
        target_dsn = _database_dsn(admin_dsn, spec.database_name)
        migrator_dsn = _database_dsn(
            admin_dsn,
            spec.database_name,
            user="ofarm_migrator",
            password=passwords["ofarm_migrator"],
        )
        with psycopg.connect(migrator_dsn, autocommit=True) as migrator:
            with migrator.transaction():
                migrator.execute(
                    sql.SQL("SELECT {}()").format(
                        sql.Identifier(
                            spec.migration_lock.schema_name,
                            spec.migration_lock.function_name,
                        )
                    )
                ).fetchone()
            assert migrator.execute(
                "SELECT pg_catalog.has_function_privilege("
                "CURRENT_USER, "
                "'pg_catalog.pg_advisory_xact_lock(integer,integer)', "
                "'EXECUTE')"
            ).fetchone() == (False,)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                migrator.execute(
                    "SELECT pg_catalog.pg_advisory_xact_lock(1, 2)"
                )

        runtime_dsn = _database_dsn(
            admin_dsn,
            spec.database_name,
            user=runtime_role,
            password=passwords[runtime_role],
        )
        with psycopg.connect(runtime_dsn, autocommit=True) as runtime:
            assert runtime.execute(
                "SELECT pg_catalog.has_schema_privilege("
                "CURRENT_USER, %s, 'USAGE')",
                (spec.migration_lock.schema_name,),
            ).fetchone() == (False,)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                runtime.execute(
                    sql.SQL("SELECT {}()").format(
                        sql.Identifier(
                            spec.migration_lock.schema_name,
                            spec.migration_lock.function_name,
                        )
                    )
                )

        with psycopg.connect(target_dsn, autocommit=True) as admin:
            assert admin.execute(
                "SELECT pg_catalog.has_function_privilege("
                "%s, 'pg_catalog.pg_advisory_xact_lock(integer,integer)', "
                "'EXECUTE')",
                (spec.migration_lock.owner_role,),
            ).fetchone() == (True,)
            assert admin.execute(
                "SELECT pg_catalog.pg_has_role("
                "'ofarm_migrator', %s, 'SET')",
                (spec.migration_lock.owner_role,),
            ).fetchone() == (False,)


def test_tenant_owner_sealer_and_bigint_lock_grant_are_exactly_isolated(
    provisioned_services,
):
    spec = TENANT_PROVISIONING_SPEC
    sealer = spec.tenant_initial_owner_sealer
    tenant_lock = spec.tenant_write_lock
    assert sealer is not None
    assert tenant_lock is not None
    admin_dsn = provisioned_services["tenantAdmin"]
    target_dsn = _database_dsn(admin_dsn, spec.database_name)

    with psycopg.connect(target_dsn, autocommit=True) as admin:
        assert admin.execute(
            """
            SELECT owner.rolsuper,
                   pg_catalog.left(owner.rolname::text, 6) = 'ofarm_',
                   routine.prosecdef,
                   language.lanname::text,
                   routine.prosrc
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
            JOIN pg_catalog.pg_language AS language
                 ON language.oid = routine.prolang
            WHERE namespace.nspname = %s
              AND routine.proname = %s
              AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = ''
            """,
            (sealer.schema_name, sealer.function_name),
        ).fetchone() == (True, False, True, "plpgsql", sealer.source)
        assert admin.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'ofarm_migrator', %s, 'EXECUTE')",
            (sealer.qualified_function + "()",),
        ).fetchone() == (True,)
        assert admin.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'ofarm_app', %s, 'EXECUTE')",
            (sealer.qualified_function + "()",),
        ).fetchone() == (False,)
        assert admin.execute(
            "SELECT pg_catalog.has_function_privilege("
            "%s, 'pg_catalog.pg_advisory_xact_lock(bigint)', 'EXECUTE')",
            (tenant_lock.owner_role,),
        ).fetchone() == (True,)
        assert admin.execute(
            "SELECT pg_catalog.has_function_privilege("
            "%s, 'pg_catalog.pg_advisory_xact_lock(integer,integer)', "
            "'EXECUTE')",
            (tenant_lock.owner_role,),
        ).fetchone() == (False,)
        assert admin.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'ofarm_migrator', 'pg_catalog.pg_advisory_xact_lock(bigint)', "
            "'EXECUTE')"
        ).fetchone() == (False,)
        assert admin.execute(
            """
            SELECT role_name,
                   pg_catalog.has_schema_privilege(role_name, schema_name, 'CREATE')
            FROM pg_catalog.unnest(%s::text[]) AS roles(role_name)
            CROSS JOIN pg_catalog.unnest(%s::text[]) AS schemas(schema_name)
            ORDER BY 1, 2
            """,
            (
                ["ofarm_binder", tenant_lock.owner_role, "ofarm_migrator"],
                [spec.schema_name, sealer.schema_name],
            ),
        ).fetchall() == [
            (role_name, False)
            for role_name in sorted(
                ["ofarm_binder", tenant_lock.owner_role, "ofarm_migrator"]
            )
            for _schema_name in sorted([spec.schema_name, sealer.schema_name])
        ]


def test_migration_lock_capsule_drift_refuses_without_repair(
    provisioned_services,
):
    admin_dsn = provisioned_services["tenantAdmin"]
    spec = TENANT_PROVISIONING_SPEC
    target_dsn = _database_dsn(admin_dsn, spec.database_name)
    wrapper = sql.Identifier(
        spec.migration_lock.schema_name,
        spec.migration_lock.function_name,
    )

    with psycopg.connect(target_dsn, autocommit=True) as admin:
        admin.execute(
            sql.SQL("ALTER FUNCTION {}() SECURITY INVOKER").format(wrapper)
        )
    try:
        with pytest.raises(ProvisioningDriftError, match="migration-lock"):
            verify_service(admin_dsn, spec)
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("ALTER FUNCTION {}() SECURITY DEFINER").format(wrapper)
            )
    verify_service(admin_dsn, spec)

    sealer_spec = spec.tenant_initial_owner_sealer
    assert sealer_spec is not None
    sealer = sql.Identifier(sealer_spec.schema_name, sealer_spec.function_name)
    with psycopg.connect(target_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("ALTER FUNCTION {}() STABLE").format(sealer))
    try:
        with pytest.raises(
            ProvisioningDriftError,
            match="tenant initial owner-sealer",
        ):
            verify_service(admin_dsn, spec)
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("ALTER FUNCTION {}() VOLATILE").format(sealer))
    verify_service(admin_dsn, spec)

    with psycopg.connect(target_dsn, autocommit=True) as admin:
        admin.execute(
            sql.SQL(
                "CREATE FUNCTION {}(pg_catalog.int4) "
                "RETURNS pg_catalog.void LANGUAGE sql "
                "AS 'SELECT pg_catalog.pg_sleep(0)'"
            ).format(wrapper)
        )
    try:
        with pytest.raises(ProvisioningDriftError, match="infrastructure"):
            verify_service(admin_dsn, spec)
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP FUNCTION {}(pg_catalog.int4)").format(wrapper))
    verify_service(admin_dsn, spec)
