"""Real PostgreSQL 17 startup-readiness tests for the independent pair."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import psycopg
import psycopg.conninfo
import pytest
from psycopg import sql

from deployment.postgresql.migration_runner import migrate_service
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    load_authoritative_migration_set,
)
from deployment.postgresql.provisioning import provision_service
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC,
    ProvisioningSpec,
)
from deployment.postgresql.readiness import (
    PostgreSQLReadinessError,
    verify_startup_readiness,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
TENANT_ADMIN_ENV = "OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN"
AUDIT_ADMIN_ENV = "OFARM_SECURITY_AUDIT_PG_ADMIN_DSN"
MAINTENANCE_DATABASES = ("postgres", "template0", "template1")


@dataclass(frozen=True, slots=True)
class _ReadyPair:
    tenant_admin_dsn: str
    audit_admin_dsn: str
    tenant_target_admin_dsn: str
    audit_target_admin_dsn: str
    tenant_readiness_dsn: str
    audit_readiness_dsn: str


def _database_dsn(admin_dsn: str, database_name: str, **overrides: str) -> str:
    parameters = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    parameters["dbname"] = database_name
    parameters.update(overrides)
    return psycopg.conninfo.make_conninfo(**parameters)


def _assert_clean_service(admin_dsn: str, spec: ProvisioningSpec) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        database = connection.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (spec.database_name,),
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
    assert database is None
    assert roles == []
    assert databases == [(name,) for name in MAINTENANCE_DATABASES]


def _destroy_service(admin_dsn: str, spec: ProvisioningSpec) -> None:
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
        unexpected = sorted(set(role_names) - set(spec.role_names))
        if unexpected:
            raise AssertionError(
                "refusing disposable cleanup with unexpected governed roles: "
                f"{unexpected}"
            )
        if role_names:
            connection.execute(
                sql.SQL("DROP ROLE {}").format(
                    sql.SQL(", ").join(
                        sql.Identifier(role_name) for role_name in role_names
                    )
                )
            )
        for database_name in MAINTENANCE_DATABASES:
            connection.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO PUBLIC").format(
                    sql.Identifier(database_name)
                )
            )
        connection.execute("GRANT TEMPORARY ON DATABASE postgres TO PUBLIC")
        connection.execute(
            "REVOKE TEMPORARY ON DATABASE template0, template1 FROM PUBLIC"
        )


def _passwords(spec: ProvisioningSpec, lane: str) -> dict[str, str]:
    nonce = secrets.token_urlsafe(32)
    return {
        role_name: f"readiness-{lane}-{index}-{nonce}"
        for index, role_name in enumerate(spec.required_password_role_names)
    }


@pytest.fixture(scope="module")
def ready_pair() -> _ReadyPair:
    tenant_admin_dsn = os.environ.get(TENANT_ADMIN_ENV)
    audit_admin_dsn = os.environ.get(AUDIT_ADMIN_ENV)
    if not tenant_admin_dsn or not audit_admin_dsn:
        pytest.skip("both dedicated PostgreSQL 17 admin routes are required")

    tenant_spec = TENANT_PROVISIONING_SPEC
    audit_spec = SECURITY_AUDIT_PROVISIONING_SPEC
    _assert_clean_service(tenant_admin_dsn, tenant_spec)
    _assert_clean_service(audit_admin_dsn, audit_spec)
    tenant_passwords = _passwords(tenant_spec, "tenant")
    audit_passwords = _passwords(audit_spec, "audit")
    try:
        provision_service(
            tenant_admin_dsn,
            tenant_spec,
            login_passwords=tenant_passwords,
        )
        provision_service(
            audit_admin_dsn,
            audit_spec,
            login_passwords=audit_passwords,
        )
        tenant_target_admin_dsn = _database_dsn(
            tenant_admin_dsn,
            tenant_spec.database_name,
        )
        audit_target_admin_dsn = _database_dsn(
            audit_admin_dsn,
            audit_spec.database_name,
        )
        migrate_service(
            admin_dsn=tenant_admin_dsn,
            migrator_dsn=_database_dsn(
                tenant_admin_dsn,
                tenant_spec.database_name,
                user="ofarm_migrator",
                password=tenant_passwords["ofarm_migrator"],
            ),
            spec=tenant_spec,
            migration_set=load_authoritative_migration_set(
                PACKAGE_ROOT,
                TENANT_SERVICE,
            ),
            release_identity="issue-174-readiness-tenant-test",
            execution_id=uuid4(),
        )
        migrate_service(
            admin_dsn=audit_admin_dsn,
            migrator_dsn=_database_dsn(
                audit_admin_dsn,
                audit_spec.database_name,
                user="ofarm_migrator",
                password=audit_passwords["ofarm_migrator"],
            ),
            spec=audit_spec,
            migration_set=load_authoritative_migration_set(
                PACKAGE_ROOT,
                SECURITY_AUDIT_SERVICE,
            ),
            release_identity="issue-174-readiness-audit-test",
            execution_id=uuid4(),
        )
        yield _ReadyPair(
            tenant_admin_dsn=tenant_admin_dsn,
            audit_admin_dsn=audit_admin_dsn,
            tenant_target_admin_dsn=tenant_target_admin_dsn,
            audit_target_admin_dsn=audit_target_admin_dsn,
            tenant_readiness_dsn=_database_dsn(
                tenant_admin_dsn,
                tenant_spec.database_name,
                user="ofarm_readiness",
                password=tenant_passwords["ofarm_readiness"],
            ),
            audit_readiness_dsn=_database_dsn(
                audit_admin_dsn,
                audit_spec.database_name,
                user="ofarm_security_audit_readiness_login",
                password=audit_passwords[
                    "ofarm_security_audit_readiness_login"
                ],
            ),
        )
    finally:
        try:
            _destroy_service(tenant_admin_dsn, tenant_spec)
        finally:
            _destroy_service(audit_admin_dsn, audit_spec)


def _ledger_rows(dsn: str, qualified_ledger: str) -> list[tuple[object, ...]]:
    with psycopg.connect(dsn, autocommit=True) as connection:
        return connection.execute(
            sql.SQL(
                "SELECT version, filename, source_sha256, source_byte_length, "
                "applied_prefix_digest, service_identity, "
                "provisioning_spec_digest FROM {} ORDER BY version"
            ).format(sql.Identifier(*qualified_ledger.split(".")))
        ).fetchall()


def test_real_readiness_logins_prove_exact_independent_read_only_pair(
    ready_pair: _ReadyPair,
):
    tenant_before = _ledger_rows(
        ready_pair.tenant_target_admin_dsn,
        TENANT_SERVICE.qualified_ledger,
    )
    audit_before = _ledger_rows(
        ready_pair.audit_target_admin_dsn,
        SECURITY_AUDIT_SERVICE.qualified_ledger,
    )

    report = verify_startup_readiness(
        tenant_readiness_dsn=ready_pair.tenant_readiness_dsn,
        audit_readiness_dsn=ready_pair.audit_readiness_dsn,
    )

    assert report.ready is True
    assert report.tenant_supported_version == 1
    assert report.tenant_observed_version == 1
    assert report.audit_supported_version == 1
    assert report.audit_observed_version == 1
    assert _ledger_rows(
        ready_pair.tenant_target_admin_dsn,
        TENANT_SERVICE.qualified_ledger,
    ) == tenant_before
    assert _ledger_rows(
        ready_pair.audit_target_admin_dsn,
        SECURITY_AUDIT_SERVICE.qualified_ledger,
    ) == audit_before


def test_readiness_fixes_catalog_output_settings_before_observation(
    ready_pair: _ReadyPair,
):
    hostile_options = (
        "-c quote_all_identifiers=on "
        "-c TimeZone=Pacific/Honolulu "
        "-c DateStyle=SQL,DMY "
        "-c standard_conforming_strings=off"
    )
    tenant_parameters = psycopg.conninfo.conninfo_to_dict(
        ready_pair.tenant_readiness_dsn
    )
    tenant_parameters["options"] = hostile_options
    audit_parameters = psycopg.conninfo.conninfo_to_dict(
        ready_pair.audit_readiness_dsn
    )
    audit_parameters["options"] = hostile_options

    report = verify_startup_readiness(
        tenant_readiness_dsn=psycopg.conninfo.make_conninfo(
            **tenant_parameters
        ),
        audit_readiness_dsn=psycopg.conninfo.make_conninfo(
            **audit_parameters
        ),
    )

    assert report.ready is True


def test_crossed_readiness_routes_and_newer_history_refuse(
    ready_pair: _ReadyPair,
):
    with pytest.raises(PostgreSQLReadinessError):
        verify_startup_readiness(
            tenant_readiness_dsn=ready_pair.audit_readiness_dsn,
            audit_readiness_dsn=ready_pair.tenant_readiness_dsn,
        )

    try:
        with psycopg.connect(
            ready_pair.tenant_target_admin_dsn,
            autocommit=True,
        ) as admin:
            admin.execute(
                "ALTER TABLE ofarm.schema_migration DISABLE TRIGGER ALL"
            )
            admin.execute(
                """
                INSERT INTO ofarm.schema_migration (
                    version, filename, source_sha256, source_byte_length,
                    applied_prefix_digest, service_identity,
                    provisioning_spec_digest, release_identity, execution_id
                )
                SELECT 2, '0002_future.sql', source_sha256, source_byte_length,
                       applied_prefix_digest, service_identity,
                       provisioning_spec_digest, 'hostile-readiness-test',
                       pg_catalog.gen_random_uuid()
                FROM ofarm.schema_migration WHERE version = 1
                """
            )
        with pytest.raises(
            PostgreSQLReadinessError,
            match="tenant migration history differs",
        ):
            verify_startup_readiness(
                tenant_readiness_dsn=ready_pair.tenant_readiness_dsn,
                audit_readiness_dsn=ready_pair.audit_readiness_dsn,
            )
    finally:
        with psycopg.connect(
            ready_pair.tenant_target_admin_dsn,
            autocommit=True,
        ) as admin:
            admin.execute(
                "DELETE FROM ofarm.schema_migration WHERE version = 2"
            )
            admin.execute(
                "ALTER TABLE ofarm.schema_migration ENABLE TRIGGER ALL"
            )


@pytest.mark.parametrize(
    ("target_attribute", "schema_name", "function_name", "lane_label"),
    (
        (
            "tenant_target_admin_dsn",
            "ofarm",
            "verify_tenant_structure",
            "tenant",
        ),
        (
            "audit_target_admin_dsn",
            "ofarm_security",
            "verify_security_audit_structure",
            "security-audit",
        ),
    ),
)
def test_external_catalog_anchor_refuses_semantically_unchanged_verifier_body(
    ready_pair: _ReadyPair,
    target_attribute: str,
    schema_name: str,
    function_name: str,
    lane_label: str,
):
    target_dsn = getattr(ready_pair, target_attribute)
    original_definition: str | None = None
    try:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            original_definition = admin.execute(
                """
                SELECT pg_catalog.pg_get_functiondef(routine.oid)
                FROM pg_catalog.pg_proc AS routine
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = routine.pronamespace
                WHERE namespace.nspname = %s
                  AND routine.proname = %s
                  AND pg_catalog.pg_get_function_identity_arguments(
                        routine.oid
                      ) = ''
                """,
                (schema_name, function_name),
            ).fetchone()[0]
            delimiter = "$function$"
            final_delimiter = original_definition.rfind(delimiter)
            assert final_delimiter > 0
            tampered_definition = (
                original_definition[:final_delimiter]
                + "\n-- issue-174 external-anchor tamper\n"
                + original_definition[final_delimiter:]
            )
            admin.execute(tampered_definition)

        with pytest.raises(
            PostgreSQLReadinessError,
            match=f"{lane_label} catalog verifier identity differs",
        ):
            verify_startup_readiness(
                tenant_readiness_dsn=ready_pair.tenant_readiness_dsn,
                audit_readiness_dsn=ready_pair.audit_readiness_dsn,
            )
    finally:
        if original_definition is not None:
            with psycopg.connect(target_dsn, autocommit=True) as admin:
                admin.execute(original_definition)

    assert verify_startup_readiness(
        tenant_readiness_dsn=ready_pair.tenant_readiness_dsn,
        audit_readiness_dsn=ready_pair.audit_readiness_dsn,
    ).ready is True
