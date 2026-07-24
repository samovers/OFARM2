"""Shared fixture for the isolated PostgreSQL security-audit service."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from deployment.postgresql.migration_runner import migrate_service
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


def database_dsn(
    admin_dsn: str, database_name: str, **overrides: str
) -> str:
    parameters = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    parameters["dbname"] = database_name
    parameters.update(overrides)
    return psycopg.conninfo.make_conninfo(**parameters)


def destroy_audit_service(admin_dsn: str) -> None:
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
                    sql.SQL(", ").join(
                        sql.Identifier(role) for role in roles
                    )
                )
            )
        for database_name in ("postgres", "template0", "template1"):
            connection.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO PUBLIC").format(
                    sql.Identifier(database_name)
                )
            )
        connection.execute("GRANT TEMPORARY ON DATABASE postgres TO PUBLIC")
        for database_name in ("template0", "template1"):
            connection.execute(
                sql.SQL(
                    "REVOKE TEMPORARY ON DATABASE {} FROM PUBLIC"
                ).format(sql.Identifier(database_name))
            )


def role_dsn(state: dict[str, object], role: str) -> str:
    return database_dsn(
        str(state["admin_dsn"]),
        SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
        user=role,
        password=state["passwords"][role],
    )


@pytest.fixture(scope="module", name="migrated_audit_service")
def audit_service_fixture():
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
        role: f"audit-v2-{index}-{secrets.token_urlsafe(32)}"
        for index, role in enumerate(spec.required_password_role_names)
    }
    try:
        provision_service(admin_dsn, spec, login_passwords=passwords)
        migration_set = load_migration_set(PACKAGE_ROOT, SECURITY_AUDIT_SERVICE)
        report = migrate_service(
            admin_dsn=admin_dsn,
            migrator_dsn=database_dsn(
                admin_dsn,
                spec.database_name,
                user="ofarm_migrator",
                password=passwords["ofarm_migrator"],
            ),
            spec=spec,
            migration_set=migration_set,
            release_identity="issue-174-audit-v2-test",
            execution_id=uuid4(),
        )
        yield {
            "admin_dsn": admin_dsn,
            "target_admin_dsn": database_dsn(
                admin_dsn, spec.database_name
            ),
            "passwords": passwords,
            "migration_set": migration_set,
            "report": report,
        }
    finally:
        destroy_audit_service(admin_dsn)
