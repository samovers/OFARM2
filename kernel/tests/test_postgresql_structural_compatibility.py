"""Real PostgreSQL 17.10 structural-compatibility tests."""

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
    PostgreSQLVerificationError,
    verify_postgresql_service_separation,
    verify_security_audit_structural_compatibility,
    verify_tenant_structural_compatibility,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
TENANT_ADMIN_ENV = "OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN"
AUDIT_ADMIN_ENV = "OFARM_SECURITY_AUDIT_PG_ADMIN_DSN"
MAINTENANCE_DATABASES = ("postgres", "template0", "template1")
TENANT_LATEST_VERSION = load_authoritative_migration_set(
    PACKAGE_ROOT,
    TENANT_SERVICE,
).migrations[-1].version
AUDIT_LATEST_VERSION = load_authoritative_migration_set(
    PACKAGE_ROOT,
    SECURITY_AUDIT_SERVICE,
).migrations[-1].version


@dataclass(frozen=True, slots=True)
class _StructuralPair:
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
def structural_pair() -> _StructuralPair:
    tenant_admin_dsn = os.environ.get(TENANT_ADMIN_ENV)
    audit_admin_dsn = os.environ.get(AUDIT_ADMIN_ENV)
    if not tenant_admin_dsn or not audit_admin_dsn:
        pytest.skip("both dedicated PostgreSQL 17.10 admin routes are required")

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
            release_identity="issue-174-structural-tenant-test",
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
            release_identity="issue-174-structural-audit-test",
            execution_id=uuid4(),
        )
        yield _StructuralPair(
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


def test_real_structural_logins_prove_independent_read_only_lanes(
    structural_pair: _StructuralPair,
):
    tenant_before = _ledger_rows(
        structural_pair.tenant_target_admin_dsn,
        TENANT_SERVICE.qualified_ledger,
    )
    audit_before = _ledger_rows(
        structural_pair.audit_target_admin_dsn,
        SECURITY_AUDIT_SERVICE.qualified_ledger,
    )

    tenant_report = verify_tenant_structural_compatibility(
        tenant_structural_dsn=structural_pair.tenant_readiness_dsn,
    )
    audit_report = verify_security_audit_structural_compatibility(
        audit_structural_dsn=structural_pair.audit_readiness_dsn,
    )
    separation = verify_postgresql_service_separation(
        tenant_structural_dsn=structural_pair.tenant_readiness_dsn,
        audit_structural_dsn=structural_pair.audit_readiness_dsn,
    )

    assert tenant_report.service_identity == TENANT_SERVICE.identity
    assert tenant_report.supported_version == TENANT_LATEST_VERSION
    assert tenant_report.observed_version == TENANT_LATEST_VERSION
    assert audit_report.service_identity == SECURITY_AUDIT_SERVICE.identity
    assert audit_report.supported_version == AUDIT_LATEST_VERSION
    assert audit_report.observed_version == AUDIT_LATEST_VERSION
    assert not hasattr(tenant_report, "ready")
    assert not hasattr(audit_report, "ready")
    assert separation.manifest()["distinctPostgreSQLSystemIdentifiers"] is True
    assert _ledger_rows(
        structural_pair.tenant_target_admin_dsn,
        TENANT_SERVICE.qualified_ledger,
    ) == tenant_before
    assert _ledger_rows(
        structural_pair.audit_target_admin_dsn,
        SECURITY_AUDIT_SERVICE.qualified_ledger,
    ) == audit_before


@pytest.mark.parametrize("lane", ("tenant", "security-audit"))
def test_structural_observation_fixes_catalog_output_settings(
    structural_pair: _StructuralPair,
    lane: str,
):
    hostile_options = (
        "-c quote_all_identifiers=on "
        "-c TimeZone=Pacific/Honolulu "
        "-c DateStyle=SQL,DMY "
        "-c standard_conforming_strings=off"
    )
    tenant_parameters = psycopg.conninfo.conninfo_to_dict(
        structural_pair.tenant_readiness_dsn
    )
    tenant_parameters["options"] = hostile_options
    audit_parameters = psycopg.conninfo.conninfo_to_dict(
        structural_pair.audit_readiness_dsn
    )
    audit_parameters["options"] = hostile_options

    if lane == "tenant":
        report = verify_tenant_structural_compatibility(
            tenant_structural_dsn=psycopg.conninfo.make_conninfo(
                **tenant_parameters
            )
        )
        assert report.service_identity == TENANT_SERVICE.identity
    else:
        report = verify_security_audit_structural_compatibility(
            audit_structural_dsn=psycopg.conninfo.make_conninfo(
                **audit_parameters
            )
        )
        assert report.service_identity == SECURITY_AUDIT_SERVICE.identity


def test_crossed_structural_routes_and_newer_history_refuse(
    structural_pair: _StructuralPair,
):
    future_version = TENANT_LATEST_VERSION + 1
    with pytest.raises(PostgreSQLVerificationError):
        verify_tenant_structural_compatibility(
            tenant_structural_dsn=structural_pair.audit_readiness_dsn,
        )
    with pytest.raises(PostgreSQLVerificationError):
        verify_security_audit_structural_compatibility(
            audit_structural_dsn=structural_pair.tenant_readiness_dsn,
        )

    try:
        with psycopg.connect(
            structural_pair.tenant_target_admin_dsn,
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
                SELECT %s, %s, source_sha256, source_byte_length,
                       applied_prefix_digest, service_identity,
                       provisioning_spec_digest, 'hostile-structural-test',
                       pg_catalog.gen_random_uuid()
                FROM ofarm.schema_migration WHERE version = %s
                """,
                (
                    future_version,
                    f"{future_version:04d}_future.sql",
                    TENANT_LATEST_VERSION,
                ),
            )
        with pytest.raises(
            PostgreSQLVerificationError,
            match="tenant migration history differs",
        ):
            verify_tenant_structural_compatibility(
                tenant_structural_dsn=structural_pair.tenant_readiness_dsn,
            )
    finally:
        with psycopg.connect(
            structural_pair.tenant_target_admin_dsn,
            autocommit=True,
        ) as admin:
            admin.execute(
                "DELETE FROM ofarm.schema_migration WHERE version = %s",
                (future_version,),
            )
            admin.execute(
                "ALTER TABLE ofarm.schema_migration ENABLE TRIGGER ALL"
            )


@pytest.mark.parametrize(
    (
        "target_attribute",
        "schema_name",
        "function_name",
        "lane_label",
        "structural_dsn_attribute",
    ),
    (
        (
            "tenant_target_admin_dsn",
            "ofarm",
            "verify_tenant_structure",
            "tenant",
            "tenant_readiness_dsn",
        ),
        (
            "audit_target_admin_dsn",
            "ofarm_security",
            "verify_security_audit_structure",
            "security-audit",
            "audit_readiness_dsn",
        ),
    ),
)
def test_external_catalog_anchor_refuses_semantically_unchanged_verifier_body(
    structural_pair: _StructuralPair,
    target_attribute: str,
    schema_name: str,
    function_name: str,
    lane_label: str,
    structural_dsn_attribute: str,
):
    target_dsn = getattr(structural_pair, target_attribute)
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
            PostgreSQLVerificationError,
            match=f"{lane_label} catalog verifier identity differs",
        ):
            if lane_label == "tenant":
                verify_tenant_structural_compatibility(
                    tenant_structural_dsn=getattr(
                        structural_pair, structural_dsn_attribute
                    )
                )
            else:
                verify_security_audit_structural_compatibility(
                    audit_structural_dsn=getattr(
                        structural_pair, structural_dsn_attribute
                    )
                )
    finally:
        if original_definition is not None:
            with psycopg.connect(target_dsn, autocommit=True) as admin:
                admin.execute(original_definition)

    if lane_label == "tenant":
        restored_report = verify_tenant_structural_compatibility(
            tenant_structural_dsn=structural_pair.tenant_readiness_dsn,
        )
        assert restored_report.service_identity == TENANT_SERVICE.identity
    else:
        restored_report = verify_security_audit_structural_compatibility(
            audit_structural_dsn=structural_pair.audit_readiness_dsn,
        )
        assert restored_report.service_identity == SECURITY_AUDIT_SERVICE.identity


def test_tenant_structural_observation_refuses_retention_function_drift(
    structural_pair: _StructuralPair,
):
    signature = "ofarm.retain_runtime_content(text,bytea)"
    try:
        with psycopg.connect(
            structural_pair.tenant_target_admin_dsn,
            autocommit=True,
        ) as admin:
            admin.execute(f"ALTER FUNCTION {signature} PARALLEL SAFE")

        with pytest.raises(PostgreSQLVerificationError):
            verify_tenant_structural_compatibility(
                tenant_structural_dsn=structural_pair.tenant_readiness_dsn
            )
    finally:
        with psycopg.connect(
            structural_pair.tenant_target_admin_dsn,
            autocommit=True,
        ) as admin:
            admin.execute(f"ALTER FUNCTION {signature} PARALLEL UNSAFE")

    restored = verify_tenant_structural_compatibility(
        tenant_structural_dsn=structural_pair.tenant_readiness_dsn
    )
    assert restored.service_identity == TENANT_SERVICE.identity


@pytest.mark.parametrize("lane", ("tenant", "security-audit"))
def test_public_structural_observation_refuses_post_migration_rogue_collation(
    structural_pair: _StructuralPair,
    lane: str,
):
    if lane == "tenant":
        target_dsn = structural_pair.tenant_target_admin_dsn
        structural_dsn = structural_pair.tenant_readiness_dsn
        owner_role = "ofarm_owner"
        schema_name = "ofarm"
    else:
        target_dsn = structural_pair.audit_target_admin_dsn
        structural_dsn = structural_pair.audit_readiness_dsn
        owner_role = "ofarm_security_audit_owner"
        schema_name = "ofarm_security"

    qualified_collation = sql.SQL("{}.{}").format(
        sql.Identifier(schema_name),
        sql.Identifier("rogue"),
    )
    try:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("SET ROLE {}").format(sql.Identifier(owner_role))
            )
            admin.execute(
                sql.SQL(
                    "CREATE COLLATION {} (provider = builtin, locale = 'C')"
                ).format(qualified_collation)
            )
            admin.execute("RESET ROLE")

        with pytest.raises(PostgreSQLVerificationError):
            if lane == "tenant":
                verify_tenant_structural_compatibility(
                    tenant_structural_dsn=structural_dsn
                )
            else:
                verify_security_audit_structural_compatibility(
                    audit_structural_dsn=structural_dsn
                )
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP COLLATION IF EXISTS {}").format(
                    qualified_collation
                )
            )

    if lane == "tenant":
        restored = verify_tenant_structural_compatibility(
            tenant_structural_dsn=structural_dsn
        )
        assert restored.service_identity == TENANT_SERVICE.identity
    else:
        restored = verify_security_audit_structural_compatibility(
            audit_structural_dsn=structural_dsn
        )
        assert restored.service_identity == SECURITY_AUDIT_SERVICE.identity


@pytest.mark.parametrize("lane", ("tenant", "security-audit"))
def test_public_structural_observation_refuses_post_migration_rewrite_rule(
    structural_pair: _StructuralPair,
    lane: str,
):
    if lane == "tenant":
        target_dsn = structural_pair.tenant_target_admin_dsn
        structural_dsn = structural_pair.tenant_readiness_dsn
        owner_role = "ofarm_owner"
        schema_name = "ofarm"
        relation_name = "kernel_record"
    else:
        target_dsn = structural_pair.audit_target_admin_dsn
        structural_dsn = structural_pair.audit_readiness_dsn
        owner_role = "ofarm_security_audit_owner"
        schema_name = "ofarm_security"
        relation_name = "operational_security_event"

    qualified_relation = sql.SQL("{}.{}").format(
        sql.Identifier(schema_name),
        sql.Identifier(relation_name),
    )
    try:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("SET ROLE {}").format(sql.Identifier(owner_role))
            )
            admin.execute(
                sql.SQL(
                    "CREATE RULE {} AS ON INSERT TO {} DO INSTEAD NOTHING"
                ).format(sql.Identifier("rogue"), qualified_relation)
            )
            admin.execute("RESET ROLE")

        with pytest.raises(PostgreSQLVerificationError):
            if lane == "tenant":
                verify_tenant_structural_compatibility(
                    tenant_structural_dsn=structural_dsn
                )
            else:
                verify_security_audit_structural_compatibility(
                    audit_structural_dsn=structural_dsn
                )
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP RULE IF EXISTS {} ON {}").format(
                    sql.Identifier("rogue"), qualified_relation
                )
            )

    if lane == "tenant":
        restored = verify_tenant_structural_compatibility(
            tenant_structural_dsn=structural_dsn
        )
        assert restored.service_identity == TENANT_SERVICE.identity
    else:
        restored = verify_security_audit_structural_compatibility(
            audit_structural_dsn=structural_dsn
        )
        assert restored.service_identity == SECURITY_AUDIT_SERVICE.identity


@pytest.mark.parametrize("lane", ("tenant", "security-audit"))
def test_public_structural_observation_restores_after_backend_view_trigger(
    structural_pair: _StructuralPair,
    lane: str,
):
    if lane == "tenant":
        target_dsn = structural_pair.tenant_target_admin_dsn
        structural_dsn = structural_pair.tenant_readiness_dsn
    else:
        target_dsn = structural_pair.audit_target_admin_dsn
        structural_dsn = structural_pair.audit_readiness_dsn

    try:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute(
                """
                CREATE FUNCTION public.ofarm_backend_view_trigger_probe()
                RETURNS pg_catalog.trigger
                LANGUAGE plpgsql
                SET search_path = pg_catalog, pg_temp
                AS 'BEGIN RETURN NEW; END'
                """
            )
            admin.execute(
                """
                CREATE TRIGGER ofarm_backend_view_trigger_probe
                INSTEAD OF INSERT ON pg_catalog.pg_stat_activity
                FOR EACH ROW EXECUTE FUNCTION
                    public.ofarm_backend_view_trigger_probe()
                """
            )

        with pytest.raises(PostgreSQLVerificationError):
            if lane == "tenant":
                verify_tenant_structural_compatibility(
                    tenant_structural_dsn=structural_dsn
                )
            else:
                verify_security_audit_structural_compatibility(
                    audit_structural_dsn=structural_dsn
                )
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute(
                "DROP TRIGGER IF EXISTS ofarm_backend_view_trigger_probe "
                "ON pg_catalog.pg_stat_activity"
            )
            admin.execute(
                "DROP FUNCTION IF EXISTS "
                "public.ofarm_backend_view_trigger_probe()"
            )

    with psycopg.connect(target_dsn, autocommit=True) as admin:
        assert admin.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_trigger AS relation_trigger
                WHERE relation_trigger.tgrelid =
                    'pg_catalog.pg_stat_activity'::pg_catalog.regclass
            )
            """
        ).fetchone() == (False,)

    if lane == "tenant":
        restored = verify_tenant_structural_compatibility(
            tenant_structural_dsn=structural_dsn
        )
        assert restored.service_identity == TENANT_SERVICE.identity
    else:
        restored = verify_security_audit_structural_compatibility(
            audit_structural_dsn=structural_dsn
        )
        assert restored.service_identity == SECURITY_AUDIT_SERVICE.identity


@pytest.mark.parametrize("lane", ("tenant", "security-audit"))
def test_public_structural_observation_refuses_database_wide_setting(
    structural_pair: _StructuralPair,
    lane: str,
):
    if lane == "tenant":
        target_dsn = structural_pair.tenant_target_admin_dsn
        structural_dsn = structural_pair.tenant_readiness_dsn
        owner_role = "ofarm_owner"
        database_name = "ofarm_tenant"
    else:
        target_dsn = structural_pair.audit_target_admin_dsn
        structural_dsn = structural_pair.audit_readiness_dsn
        owner_role = "ofarm_security_audit_owner"
        database_name = "ofarm_security_audit"

    try:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("SET ROLE {}").format(sql.Identifier(owner_role))
            )
            admin.execute(
                sql.SQL(
                    "ALTER DATABASE {} SET default_transaction_read_only = on"
                ).format(sql.Identifier(database_name))
            )

        with pytest.raises(PostgreSQLVerificationError):
            if lane == "tenant":
                verify_tenant_structural_compatibility(
                    tenant_structural_dsn=structural_dsn
                )
            else:
                verify_security_audit_structural_compatibility(
                    audit_structural_dsn=structural_dsn
                )
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute("SET default_transaction_read_only = off")
            admin.execute(
                sql.SQL(
                    "ALTER DATABASE {} RESET default_transaction_read_only"
                ).format(sql.Identifier(database_name))
            )

    if lane == "tenant":
        restored = verify_tenant_structural_compatibility(
            tenant_structural_dsn=structural_dsn
        )
        assert restored.service_identity == TENANT_SERVICE.identity
    else:
        restored = verify_security_audit_structural_compatibility(
            audit_structural_dsn=structural_dsn
        )
        assert restored.service_identity == SECURITY_AUDIT_SERVICE.identity


def _lane_routes(
    structural_pair: _StructuralPair,
    lane: str,
) -> tuple[str, str, str, str]:
    if lane == "tenant":
        return (
            structural_pair.tenant_admin_dsn,
            structural_pair.tenant_target_admin_dsn,
            structural_pair.tenant_readiness_dsn,
            "ofarm_app",
        )
    return (
        structural_pair.audit_admin_dsn,
        structural_pair.audit_target_admin_dsn,
        structural_pair.audit_readiness_dsn,
        "ofarm_security_audit_readiness_login",
    )


def _verify_lane(structural_dsn: str, lane: str) -> object:
    if lane == "tenant":
        return verify_tenant_structural_compatibility(
            tenant_structural_dsn=structural_dsn
        )
    return verify_security_audit_structural_compatibility(
        audit_structural_dsn=structural_dsn
    )


@pytest.mark.parametrize("lane", ("tenant", "security-audit"))
def test_public_structural_observation_refuses_rogue_schema_and_grant(
    structural_pair: _StructuralPair,
    lane: str,
):
    _admin_dsn, target_dsn, structural_dsn, granted_role = _lane_routes(
        structural_pair, lane
    )
    rogue_schema = sql.Identifier("ofarm_hostile_schema")
    rogue_table = sql.SQL("{}.{}").format(
        rogue_schema,
        sql.Identifier("reachable_data"),
    )
    try:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE SCHEMA {}").format(rogue_schema))
            admin.execute(
                sql.SQL("CREATE TABLE {} (value pg_catalog.int4)").format(rogue_table)
            )
            admin.execute(
                sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                    rogue_schema,
                    sql.Identifier(granted_role),
                )
            )
            admin.execute(
                sql.SQL("GRANT SELECT ON {} TO {}").format(
                    rogue_table,
                    sql.Identifier(granted_role),
                )
            )

        with pytest.raises(PostgreSQLVerificationError):
            _verify_lane(structural_dsn, lane)
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(rogue_schema)
            )

    restored = _verify_lane(structural_dsn, lane)
    expected_identity = (
        TENANT_SERVICE.identity if lane == "tenant" else SECURITY_AUDIT_SERVICE.identity
    )
    assert restored.service_identity == expected_identity


@pytest.mark.parametrize("lane", ("tenant", "security-audit"))
def test_public_structural_observation_refuses_rogue_database_access(
    structural_pair: _StructuralPair,
    lane: str,
):
    admin_dsn, _target_dsn, structural_dsn, login_role = _lane_routes(
        structural_pair, lane
    )
    rogue_database = sql.Identifier("ofarm_hostile_database")
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(rogue_database))
            access = admin.execute(
                """
                SELECT pg_catalog.has_database_privilege(
                           %s, 'ofarm_hostile_database', 'CONNECT'
                       ),
                       pg_catalog.has_database_privilege(
                           %s, 'ofarm_hostile_database', 'TEMPORARY'
                       )
                """,
                (login_role, login_role),
            ).fetchone()
        assert access == (True, True)

        with pytest.raises(PostgreSQLVerificationError):
            _verify_lane(structural_dsn, lane)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(rogue_database))

    restored = _verify_lane(structural_dsn, lane)
    expected_identity = (
        TENANT_SERVICE.identity if lane == "tenant" else SECURITY_AUDIT_SERVICE.identity
    )
    assert restored.service_identity == expected_identity


@pytest.mark.parametrize("lane", ("tenant", "security-audit"))
def test_public_structural_observation_refuses_maintenance_database_access(
    structural_pair: _StructuralPair,
    lane: str,
):
    admin_dsn, _target_dsn, structural_dsn, login_role = _lane_routes(
        structural_pair, lane
    )
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("GRANT CONNECT, TEMPORARY ON DATABASE postgres TO {}").format(
                    sql.Identifier(login_role)
                )
            )

        with pytest.raises(PostgreSQLVerificationError):
            _verify_lane(structural_dsn, lane)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL(
                    "REVOKE CONNECT, TEMPORARY ON DATABASE postgres FROM {}"
                ).format(sql.Identifier(login_role))
            )

    restored = _verify_lane(structural_dsn, lane)
    expected_identity = (
        TENANT_SERVICE.identity if lane == "tenant" else SECURITY_AUDIT_SERVICE.identity
    )
    assert restored.service_identity == expected_identity


@pytest.mark.parametrize("lane", ("tenant", "security-audit"))
def test_public_structural_observation_refuses_global_foreign_objects(
    structural_pair: _StructuralPair,
    lane: str,
):
    _admin_dsn, target_dsn, structural_dsn, _login_role = _lane_routes(
        structural_pair, lane
    )
    try:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute("CREATE FOREIGN DATA WRAPPER ofarm_hostile_fdw")
            admin.execute(
                "CREATE SERVER ofarm_hostile_server "
                "FOREIGN DATA WRAPPER ofarm_hostile_fdw"
            )

        with pytest.raises(PostgreSQLVerificationError):
            _verify_lane(structural_dsn, lane)
    finally:
        with psycopg.connect(target_dsn, autocommit=True) as admin:
            admin.execute("DROP SERVER IF EXISTS ofarm_hostile_server")
            admin.execute("DROP FOREIGN DATA WRAPPER IF EXISTS ofarm_hostile_fdw")

    restored = _verify_lane(structural_dsn, lane)
    expected_identity = (
        TENANT_SERVICE.identity if lane == "tenant" else SECURITY_AUDIT_SERVICE.identity
    )
    assert restored.service_identity == expected_identity


def test_tenant_structural_observation_requires_native_verifier_extension(
    structural_pair: _StructuralPair,
):
    try:
        with psycopg.connect(
            structural_pair.tenant_target_admin_dsn,
            autocommit=True,
        ) as admin:
            admin.execute("DROP EXTENSION ofarm_ed25519")
            admin.execute("DROP SCHEMA ofarm_crypto")

        with pytest.raises(PostgreSQLVerificationError):
            verify_tenant_structural_compatibility(
                tenant_structural_dsn=structural_pair.tenant_readiness_dsn
            )
    finally:
        with psycopg.connect(
            structural_pair.tenant_target_admin_dsn,
            autocommit=True,
        ) as admin:
            schema_present = admin.execute(
                "SELECT pg_catalog.to_regnamespace('ofarm_crypto') IS NOT NULL"
            ).fetchone()[0]
            if not schema_present:
                admin.execute(
                    "CREATE SCHEMA ofarm_crypto AUTHORIZATION ofarm_crypto_installer"
                )
            extension_present = admin.execute(
                """
                SELECT pg_catalog.count(*) = 1
                FROM pg_catalog.pg_extension
                WHERE extname = 'ofarm_ed25519'
                """
            ).fetchone()[0]
            if not extension_present:
                admin.execute("SET ROLE ofarm_crypto_installer")
                admin.execute("CREATE EXTENSION ofarm_ed25519 VERSION '1.0'")
                admin.execute("RESET ROLE")
            admin.execute("REVOKE ALL PRIVILEGES ON SCHEMA ofarm_crypto FROM PUBLIC")
            admin.execute("GRANT USAGE ON SCHEMA ofarm_crypto TO ofarm_binder")
            admin.execute(
                """
                GRANT EXECUTE ON FUNCTION ofarm_crypto.ed25519_verify(
                    pg_catalog.bytea, pg_catalog.bytea, pg_catalog.bytea
                ) TO ofarm_binder
                """
            )

    restored = verify_tenant_structural_compatibility(
        tenant_structural_dsn=structural_pair.tenant_readiness_dsn
    )
    assert restored.service_identity == TENANT_SERVICE.identity
