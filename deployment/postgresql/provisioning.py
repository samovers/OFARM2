"""Fail-closed PostgreSQL 17 create-or-verify infrastructure provisioning.

This module is an operator/release tool, not application startup code.  It may
create one target only when the target database and every governed role are
absent.  An existing or partially-created target is read-only verified and is
never repaired, widened, dropped, or adopted.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Mapping

import psycopg
import psycopg.conninfo
from psycopg import sql

from deployment.postgresql.catalog_identity import (
    CATALOG_OUTPUT_SETTING_ASSIGNMENTS,
    CATALOG_OUTPUT_SETTING_VALUES,
)
from deployment.postgresql.catalog_classifier import (
    SCHEMA_LOCAL_OBJECT_SELECTS_SQL,
)
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC,
    MembershipSpec,
    ProvisioningSpec,
    RoleSpec,
)
from deployment.postgresql.version_policy import (
    SUPPORTED_POSTGRESQL_SERVER_VERSION,
    SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
)


_POSTGRESQL_FIRST_NORMAL_OBJECT_ID = 16384
_CONTROL_DATABASE = "postgres"
_BASE_DATABASE_INVENTORY = frozenset({"postgres", "template0", "template1"})
_ROUTINE_ARGUMENT_SQL = {
    "bigint": sql.Identifier("pg_catalog", "int8"),
    "bytea": sql.Identifier("pg_catalog", "bytea"),
    "integer": sql.Identifier("pg_catalog", "int4"),
    "oid": sql.Identifier("pg_catalog", "oid"),
    "text": sql.Identifier("pg_catalog", "text"),
}


class ProvisioningError(RuntimeError):
    """Base class for safe provisioning failures."""


class ProvisioningAuthorityError(ProvisioningError):
    """The caller is not the external database-administrator boundary."""


class ProvisioningTargetError(ProvisioningError):
    """A target is not provably new or cannot be safely inspected."""


class ProvisioningDriftError(ProvisioningError):
    """An existing target differs from its exact checked-in specification."""

    def __init__(self, differences: tuple[str, ...]):
        if not differences:
            raise ValueError("provisioning drift requires at least one difference")
        self.differences = tuple(sorted(set(differences)))
        super().__init__(
            "PostgreSQL provisioning drift: " + "; ".join(self.differences)
        )


@dataclass(frozen=True, slots=True)
class ProvisioningReport:
    """Non-secret identity of one exactly verified service target."""

    service_identity: str
    provisioning_spec_digest: str
    database_name: str
    system_identifier: str
    server_version_num: int
    created: bool
    migration_ledger_present: bool

    def manifest(self) -> dict[str, object]:
        return {
            "schemaVersion": "ofarm.postgresql-provisioning-report.v1",
            "serviceIdentity": self.service_identity,
            "provisioningSpecDigest": self.provisioning_spec_digest,
            "databaseName": self.database_name,
            "systemIdentifier": self.system_identifier,
            "serverVersionNum": self.server_version_num,
            "created": self.created,
            "migrationLedgerPresent": self.migration_ledger_present,
        }


@dataclass(frozen=True, slots=True)
class ProvisioningInfrastructureReport:
    """Identity of exact infrastructure, with no migration-phase claim."""

    service_identity: str
    provisioning_spec_digest: str
    database_name: str
    system_identifier: str
    server_version_num: int

    def manifest(self) -> dict[str, object]:
        return {
            "schemaVersion": "ofarm.postgresql-infrastructure-report.v1",
            "serviceIdentity": self.service_identity,
            "provisioningSpecDigest": self.provisioning_spec_digest,
            "databaseName": self.database_name,
            "systemIdentifier": self.system_identifier,
            "serverVersionNum": self.server_version_num,
            "migrationPhaseVerified": False,
        }


@dataclass(frozen=True, slots=True)
class ClusterLineageReport:
    """Fresh SQL evidence that tenant and audit use different cluster lineages."""

    tenant_system_identifier: str
    audit_system_identifier: str

    def manifest(self) -> dict[str, object]:
        return {
            "schemaVersion": "ofarm.postgresql-cluster-lineage.v1",
            "tenantSystemIdentifier": self.tenant_system_identifier,
            "auditSystemIdentifier": self.audit_system_identifier,
            "distinct": True,
        }


@dataclass(frozen=True, slots=True)
class _PostgresIdentity:
    database_name: str
    system_identifier: str
    server_version_num: int
    server_version: str


def _provisioning_lock_key() -> tuple[int, int]:
    digest = hashlib.sha256(
        b"OFARM_POSTGRESQL_CLUSTER_PROVISIONING_LOCK_V1\x00"
    ).digest()[:8]
    return (
        int.from_bytes(digest[:4], "big", signed=True),
        int.from_bytes(digest[4:], "big", signed=True),
    )


def _target_dsn(admin_dsn: str, database_name: str) -> str:
    try:
        parameters = psycopg.conninfo.conninfo_to_dict(admin_dsn)
        parameters["dbname"] = database_name
        return psycopg.conninfo.make_conninfo(**parameters)
    except Exception as exc:
        raise ProvisioningTargetError("admin DSN cannot derive the target route") from exc


def _require_fixed_spec(spec: ProvisioningSpec) -> None:
    if spec not in (TENANT_PROVISIONING_SPEC, SECURITY_AUDIT_PROVISIONING_SPEC):
        raise ProvisioningTargetError(
            "spec must be one of the two checked-in PostgreSQL services"
        )


def _require_dba(
    connection: psycopg.Connection, spec: ProvisioningSpec
) -> _PostgresIdentity:
    row = connection.execute(
        """
        SELECT pg_catalog.current_database()::text,
               r.rolsuper,
               pg_catalog.current_setting('server_version_num')::integer,
               pg_catalog.current_setting('server_version')::text,
               s.system_identifier::text,
               pg_catalog.current_setting('scram_iterations')::integer,
               pg_catalog.pg_is_in_recovery(),
               pg_catalog.current_setting('transaction_read_only')
        FROM pg_catalog.pg_roles AS r
        CROSS JOIN pg_catalog.pg_control_system() AS s
        WHERE r.rolname = CURRENT_USER
        """
    ).fetchone()
    if row is None or row[1] is not True:
        raise ProvisioningAuthorityError(
            "provisioning requires an external PostgreSQL superuser"
        )
    if row[0] != _CONTROL_DATABASE:
        raise ProvisioningTargetError(
            f"admin DSN must connect to {_CONTROL_DATABASE}"
        )
    if (
        row[2] != SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM
        or row[3] != SUPPORTED_POSTGRESQL_SERVER_VERSION
    ):
        raise ProvisioningTargetError(
            "provisioning requires exact PostgreSQL build "
            f"{SUPPORTED_POSTGRESQL_SERVER_VERSION}"
        )
    if row[5] != spec.scram_iterations:
        raise ProvisioningTargetError("PostgreSQL SCRAM iteration posture differs")
    if row[6] is not False or row[7] != "off":
        raise ProvisioningTargetError("provisioning requires a writable primary")
    return _PostgresIdentity(
        database_name=row[0],
        system_identifier=row[4],
        server_version_num=row[2],
        server_version=row[3],
    )


def _acquire_lock(connection: psycopg.Connection) -> tuple[int, int]:
    lock_key = _provisioning_lock_key()
    acquired = connection.execute(
        "SELECT pg_catalog.pg_try_advisory_lock(%s, %s)", lock_key
    ).fetchone()[0]
    if acquired is not True:
        raise ProvisioningTargetError("another provisioner holds the service lock")
    return lock_key


def _release_lock(
    connection: psycopg.Connection, lock_key: tuple[int, int]
) -> None:
    released = connection.execute(
        "SELECT pg_catalog.pg_advisory_unlock(%s, %s)", lock_key
    ).fetchone()[0]
    if released is not True:
        raise ProvisioningTargetError("the service provisioning lock was lost")


def _database_exists(connection: psycopg.Connection, database_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (database_name,),
        ).fetchone()
        is not None
    )


def _database_names(connection: psycopg.Connection) -> frozenset[str]:
    return frozenset(
        row[0]
        for row in connection.execute(
            "SELECT datname::text FROM pg_catalog.pg_database ORDER BY datname"
        ).fetchall()
    )


def _expected_database_names(
    spec: ProvisioningSpec, *, target_exists: bool
) -> frozenset[str]:
    if not target_exists:
        return _BASE_DATABASE_INVENTORY
    return _BASE_DATABASE_INVENTORY | {spec.database_name}


def _require_database_inventory(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    *,
    target_exists: bool,
) -> None:
    if _database_names(connection) != _expected_database_names(
        spec, target_exists=target_exists
    ):
        raise ProvisioningTargetError(
            "dedicated PostgreSQL service database inventory differs"
        )


def _governed_role_names(connection: psycopg.Connection) -> tuple[str, ...]:
    rows = connection.execute(
        r"""
        SELECT rolname::text
        FROM pg_catalog.pg_roles
        WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
        ORDER BY rolname
        """
    ).fetchall()
    return tuple(row[0] for row in rows)


def _validate_passwords(
    spec: ProvisioningSpec, login_passwords: Mapping[str, str] | None
) -> dict[str, str]:
    if login_passwords is None:
        raise ProvisioningTargetError(
            "a new target requires an external password for every LOGIN role"
        )
    passwords = dict(login_passwords)
    expected = set(spec.required_password_role_names)
    if set(passwords) != expected:
        raise ProvisioningTargetError(
            "LOGIN password names differ from the provisioning specification"
        )
    for role_name, password in passwords.items():
        if not isinstance(password, str) or not 32 <= len(password) <= 128:
            raise ProvisioningTargetError(
                f"password for {role_name} must contain 32-128 visible ASCII characters"
            )
        try:
            encoded = password.encode("ascii", errors="strict")
        except UnicodeEncodeError as exc:
            raise ProvisioningTargetError(
                f"password for {role_name} must contain visible ASCII"
            ) from exc
        if any(byte < 33 or byte > 126 for byte in encoded):
            raise ProvisioningTargetError(
                f"password for {role_name} must contain visible ASCII"
            )
    if len(set(passwords.values())) != len(passwords):
        raise ProvisioningTargetError("every LOGIN role requires a distinct password")
    return passwords


def _scram_verifier(password: str, iterations: int) -> str:
    """Build PostgreSQL's SCRAM verifier without putting plaintext in SQL."""

    salt = secrets.token_bytes(16)
    salted_password = hashlib.pbkdf2_hmac(
        "sha256", password.encode("ascii"), salt, iterations
    )
    client_key = hmac.digest(salted_password, b"Client Key", "sha256")
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.digest(salted_password, b"Server Key", "sha256")
    return (
        f"SCRAM-SHA-256${iterations}:"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(stored_key).decode('ascii')}:"
        f"{base64.b64encode(server_key).decode('ascii')}"
    )


def _create_role(
    connection: psycopg.Connection, role: RoleSpec, password_verifier: str | None
) -> None:
    attributes = [
        sql.SQL("LOGIN" if role.login else "NOLOGIN"),
        sql.SQL("INHERIT" if role.inherit else "NOINHERIT"),
        sql.SQL("BYPASSRLS" if role.bypass_rls else "NOBYPASSRLS"),
        sql.SQL("SUPERUSER" if role.superuser else "NOSUPERUSER"),
        sql.SQL("NOCREATEDB"),
        sql.SQL("NOCREATEROLE"),
        sql.SQL("NOREPLICATION"),
        sql.SQL("CONNECTION LIMIT {} ").format(sql.Literal(role.connection_limit)),
    ]
    if role.login:
        if password_verifier is None:
            raise ProvisioningTargetError(f"password verifier for {role.name} is absent")
        attributes.extend((sql.SQL("PASSWORD"), sql.Literal(password_verifier)))
    else:
        attributes.append(sql.SQL("PASSWORD NULL"))
    statement = sql.SQL("CREATE ROLE {} WITH ").format(sql.Identifier(role.name))
    statement += sql.SQL(" ").join(attributes)
    connection.execute(statement)


def _create_membership(
    connection: psycopg.Connection, membership: MembershipSpec
) -> None:
    base = sql.SQL("GRANT {} TO {} WITH ").format(
        sql.Identifier(membership.granted_role),
        sql.Identifier(membership.member_role),
    )
    for option, enabled in (
        ("ADMIN", membership.admin),
        ("INHERIT", membership.inherit),
        ("SET", membership.set_role),
    ):
        connection.execute(
            base + sql.SQL("{} {}").format(
                sql.SQL(option), sql.SQL("TRUE" if enabled else "FALSE")
            )
        )


def _create_cluster_roles(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    passwords: Mapping[str, str],
) -> None:
    with connection.transaction():
        connection.execute("SET LOCAL password_encryption = 'scram-sha-256'")
        connection.execute(
            "SELECT pg_catalog.set_config('scram_iterations', %s, true)",
            (str(spec.scram_iterations),),
        )
        for role in spec.roles:
            password = passwords.get(role.name)
            verifier = (
                _scram_verifier(password, spec.scram_iterations)
                if password is not None
                else None
            )
            _create_role(connection, role, verifier)
        for membership in spec.memberships:
            _create_membership(connection, membership)


def _create_database(connection: psycopg.Connection, spec: ProvisioningSpec) -> None:
    connection.execute(
        sql.SQL(
            "CREATE DATABASE {} WITH OWNER {} TEMPLATE template0 "
            "ENCODING 'UTF8' LOCALE_PROVIDER builtin LOCALE 'C' "
            "CONNECTION LIMIT {}"
        ).format(
            sql.Identifier(spec.database_name),
            sql.Identifier(spec.database_owner),
            sql.Literal(spec.database_connection_limit),
        )
    )


def _target_identity(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    expected: _PostgresIdentity,
) -> _PostgresIdentity:
    row = connection.execute(
        """
        SELECT pg_catalog.current_database()::text,
               control.system_identifier::text,
               pg_catalog.current_setting('server_version_num')::integer,
               pg_catalog.current_setting('server_version')::text,
               pg_catalog.pg_is_in_recovery(),
               pg_catalog.current_setting('default_transaction_read_only')
        FROM pg_catalog.pg_control_system() AS control
        """
    ).fetchone()
    identity = _PostgresIdentity(row[0], row[1], row[2], row[3])
    if identity.database_name != spec.database_name:
        raise ProvisioningTargetError("target route reached the wrong database")
    if identity.system_identifier != expected.system_identifier:
        raise ProvisioningTargetError("admin and target routes reach different clusters")
    if identity.server_version_num != expected.server_version_num:
        raise ProvisioningTargetError("admin and target PostgreSQL versions differ")
    if (
        identity.server_version != expected.server_version
        or identity.server_version != SUPPORTED_POSTGRESQL_SERVER_VERSION
    ):
        raise ProvisioningTargetError("admin and target PostgreSQL builds differ")
    if row[4] is not False or row[5] != "off":
        raise ProvisioningTargetError("target route is not a writable primary")
    return identity


def _configure_target(
    admin_dsn: str,
    spec: ProvisioningSpec,
    expected_identity: _PostgresIdentity,
) -> None:
    with psycopg.connect(
        _target_dsn(admin_dsn, spec.database_name), autocommit=True
    ) as target:
        for assignment in CATALOG_OUTPUT_SETTING_ASSIGNMENTS:
            target.execute(f"SET {assignment}")
        _target_identity(target, spec, expected_identity)
        _require_database_inventory(target, spec, target_exists=True)
        initial_large_object_differences = (
            _large_object_inventory_differences(target, spec)
            + _large_object_storage_differences(target)
        )
        initial_catalog_differences = (
            initial_large_object_differences
            + _backend_statistics_inventory_differences(target, spec)
        )
        if initial_catalog_differences:
            raise ProvisioningTargetError(
                "fresh target built-in catalog posture differs: "
                + "; ".join(sorted(set(initial_catalog_differences)))
            )
        with target.transaction():
            target.execute(
                sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                    sql.Identifier(spec.schema_name),
                    sql.Identifier(spec.schema_owner),
                )
            )
            if spec.native_verifier is not None:
                verifier = spec.native_verifier
                target.execute(
                    sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                        sql.Identifier(verifier.schema_name),
                        sql.Identifier(verifier.installer_role),
                    )
                )
                target.execute(
                    sql.SQL("SET LOCAL ROLE {}").format(
                        sql.Identifier(verifier.installer_role)
                    )
                )
                target.execute(
                    sql.SQL("CREATE EXTENSION {} VERSION {}").format(
                        sql.Identifier(verifier.extension_name),
                        sql.Literal(verifier.extension_version),
                    )
                )
                target.execute("RESET ROLE")
            target.execute(
                sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                    sql.Identifier(spec.migration_lock.schema_name),
                    sql.Identifier(spec.migration_lock.owner_role),
                )
            )
            for database_name in sorted(
                _expected_database_names(spec, target_exists=True)
            ):
                target.execute(
                    sql.SQL(
                        "REVOKE ALL PRIVILEGES ON DATABASE {} FROM PUBLIC"
                    ).format(sql.Identifier(database_name))
                )
            target.execute("REVOKE ALL PRIVILEGES ON SCHEMA public FROM PUBLIC")
            target.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA {} FROM PUBLIC").format(
                    sql.Identifier(spec.schema_name)
                )
            )
            if spec.native_verifier is not None:
                verifier = spec.native_verifier
                target.execute(
                    sql.SQL(
                        "REVOKE ALL PRIVILEGES ON SCHEMA {} FROM PUBLIC"
                    ).format(sql.Identifier(verifier.schema_name))
                )
                if spec.tenant_admission_lock is None:
                    raise ProvisioningTargetError(
                        "native verifier requires the tenant admission owner"
                    )
                verifier_callers = (
                    spec.tenant_admission_lock.shared_owner_role,
                )
                for verifier_caller in verifier_callers:
                    target.execute(
                        sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                            sql.Identifier(verifier.schema_name),
                            sql.Identifier(verifier_caller),
                        )
                    )
                target.execute(
                    sql.SQL(
                        "REVOKE ALL PRIVILEGES ON FUNCTION {}.{}("
                        "pg_catalog.bytea, pg_catalog.bytea, pg_catalog.bytea) "
                        "FROM PUBLIC"
                    ).format(
                        sql.Identifier(verifier.schema_name),
                        sql.Identifier(verifier.function_name),
                    )
                )
                for verifier_caller in verifier_callers:
                    target.execute(
                        sql.SQL(
                            "GRANT EXECUTE ON FUNCTION {}.{}("
                            "pg_catalog.bytea, pg_catalog.bytea, pg_catalog.bytea) "
                            "TO {}"
                        ).format(
                            sql.Identifier(verifier.schema_name),
                            sql.Identifier(verifier.function_name),
                            sql.Identifier(verifier_caller),
                        )
                    )
            target.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA {} FROM PUBLIC").format(
                    sql.Identifier(spec.migration_lock.schema_name)
                )
            )
            target.execute(
                "REVOKE SELECT ON TABLE pg_catalog.pg_stat_activity FROM PUBLIC"
            )
            for routine in (
                *spec.public_execute_revoked_routines,
                *spec.large_object_routines,
                *spec.backend_statistics_routines,
            ):
                target.execute(
                    sql.SQL("REVOKE EXECUTE ON FUNCTION {}({}) FROM PUBLIC").format(
                        sql.Identifier("pg_catalog", routine.name),
                        sql.SQL(", ").join(
                            _ROUTINE_ARGUMENT_SQL[argument_type]
                            for argument_type in routine.argument_types
                        ),
                    )
                )
            for role_name in spec.activity_view.select_roles:
                target.execute(
                    sql.SQL(
                        "GRANT SELECT ON TABLE pg_catalog.pg_stat_activity TO {}"
                    ).format(sql.Identifier(role_name))
                )
                target.execute(
                    sql.SQL(
                        "GRANT EXECUTE ON FUNCTION "
                        "pg_catalog.pg_stat_get_activity(pg_catalog.int4) TO {}"
                    ).format(sql.Identifier(role_name))
                )
            target.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION "
                    "pg_catalog.pg_advisory_xact_lock("
                    "pg_catalog.int4, pg_catalog.int4) TO {}"
                ).format(sql.Identifier(spec.migration_lock.owner_role))
            )
            if spec.tenant_admission_lock is not None:
                target.execute(
                    sql.SQL(
                        "GRANT EXECUTE ON FUNCTION "
                        "pg_catalog.pg_advisory_xact_lock_shared("
                        "pg_catalog.int4, pg_catalog.int4) TO {}"
                    ).format(
                        sql.Identifier(
                            spec.tenant_admission_lock.shared_owner_role
                        )
                    )
                )
                target.execute(
                    sql.SQL(
                        "GRANT EXECUTE ON FUNCTION "
                        "pg_catalog.pg_advisory_xact_lock("
                        "pg_catalog.int4, pg_catalog.int4) TO {}"
                    ).format(
                        sql.Identifier(
                            spec.tenant_admission_lock.exclusive_owner_role
                        )
                    )
                )
            if spec.tenant_write_lock is not None:
                target.execute(
                    sql.SQL(
                        "GRANT EXECUTE ON FUNCTION "
                        "pg_catalog.pg_advisory_xact_lock(pg_catalog.int8) TO {}"
                    ).format(sql.Identifier(spec.tenant_write_lock.owner_role))
                )
            for role_name in spec.database_connect_roles:
                target.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(spec.database_name), sql.Identifier(role_name)
                    )
                )
            for role_name in spec.schema_usage_roles:
                target.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                        sql.Identifier(spec.schema_name), sql.Identifier(role_name)
                    )
                )
            target.execute(
                sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                    sql.Identifier(spec.migration_lock.schema_name),
                    sql.Identifier(spec.migration_lock.execute_role),
                )
            )

            wrapper = sql.Identifier(
                spec.migration_lock.schema_name,
                spec.migration_lock.function_name,
            )
            target.execute(
                sql.SQL(
                    "CREATE FUNCTION {}() RETURNS pg_catalog.void "
                    "LANGUAGE sql VOLATILE PARALLEL UNSAFE SECURITY DEFINER "
                    "SET search_path = pg_catalog, pg_temp AS {}"
                ).format(wrapper, sql.Literal(spec.migration_lock.source))
            )
            target.execute(
                sql.SQL("ALTER FUNCTION {}() OWNER TO {}").format(
                    wrapper, sql.Identifier(spec.migration_lock.owner_role)
                )
            )
            target.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON FUNCTION {}() FROM PUBLIC").format(
                    wrapper
                )
            )
            target.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {}() TO {}").format(
                    wrapper, sql.Identifier(spec.migration_lock.execute_role)
                )
            )

            if spec.tenant_initial_owner_sealer is not None:
                sealer_spec = spec.tenant_initial_owner_sealer
                sealer = sql.Identifier(
                    sealer_spec.schema_name,
                    sealer_spec.function_name,
                )
                target.execute(
                    sql.SQL(
                        "CREATE FUNCTION {}() RETURNS pg_catalog.void "
                        "LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE "
                        "SECURITY DEFINER "
                        "SET search_path = pg_catalog, pg_temp AS {}"
                    ).format(sealer, sql.Literal(sealer_spec.source))
                )
                target.execute(
                    sql.SQL(
                        "REVOKE ALL PRIVILEGES ON FUNCTION {}() FROM PUBLIC"
                    ).format(sealer)
                )
                target.execute(
                    sql.SQL("GRANT EXECUTE ON FUNCTION {}() TO {}").format(
                        sealer, sql.Identifier(sealer_spec.execute_role)
                    )
                )

            for owner in spec.default_privilege_owner_roles:
                target.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES FOR ROLE {} "
                        "REVOKE EXECUTE ON ROUTINES FROM PUBLIC"
                    ).format(sql.Identifier(owner))
                )
                target.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES FOR ROLE {} "
                        "REVOKE USAGE ON TYPES FROM PUBLIC"
                    ).format(sql.Identifier(owner))
                )

            for role in spec.roles:
                for setting in role.settings:
                    target.execute(
                        sql.SQL("ALTER ROLE {} IN DATABASE {} SET {} = {}").format(
                            sql.Identifier(role.name),
                            sql.Identifier(spec.database_name),
                            sql.Identifier(setting.name),
                            sql.Literal(setting.value),
                        )
                    )


def _role_surface_differences(
    connection: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    rows = connection.execute(
        r"""
        SELECT r.rolname::text,
               r.rolsuper,
               r.rolinherit,
               r.rolcreaterole,
               r.rolcreatedb,
               r.rolcanlogin,
               r.rolreplication,
               r.rolbypassrls,
               r.rolconnlimit,
               r.rolvaliduntil,
               COALESCE(r.rolconfig, ARRAY[]::text[])
        FROM pg_catalog.pg_roles AS r
        WHERE r.rolname::text LIKE 'ofarm\_%' ESCAPE '\'
        ORDER BY r.rolname
        """
    ).fetchall()
    observed = {row[0]: row[1:] for row in rows}
    expected_names = set(spec.role_names)
    differences: list[str] = []
    for name in sorted(expected_names - set(observed)):
        differences.append(f"role {name} is missing")
    for name in sorted(set(observed) - expected_names):
        differences.append(f"unexpected governed role {name}")

    for role in spec.roles:
        row = observed.get(role.name)
        if row is None:
            continue
        expected = (
            role.superuser,
            role.inherit,
            False,
            False,
            role.login,
            False,
            role.bypass_rls,
            role.connection_limit,
            None,
            [],
        )
        if tuple(row) != expected:
            differences.append(f"role {role.name} attributes differ")
    return differences


def _external_membership_role_differences(
    connection: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    external_roles = spec.external_membership_roles
    external_names = [role.name for role in external_roles]
    if not external_names:
        return []
    rows = connection.execute(
        """
        SELECT r.rolname::text,
               r.rolsuper,
               r.rolinherit,
               r.rolcreaterole,
               r.rolcreatedb,
               r.rolcanlogin,
               r.rolreplication,
               r.rolbypassrls,
               r.rolconnlimit,
               r.rolvaliduntil,
               COALESCE(r.rolconfig, ARRAY[]::text[])
        FROM pg_catalog.pg_roles AS r
        WHERE r.rolname = ANY (%s::text[])
        ORDER BY r.rolname
        """,
        (external_names,),
    ).fetchall()
    expected = [
        (
            role.name,
            False,
            role.inherit,
            False,
            False,
            role.login,
            False,
            role.bypass_rls,
            role.connection_limit,
            None,
            [],
        )
        for role in external_roles
    ]
    if rows != expected:
        return ["external membership role attributes differ"]
    return []


def _role_password_differences(
    connection: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    """Inspect password verifier internals on the administrator-only path."""

    rows = connection.execute(
        r"""
        SELECT role.rolname::text,
               verifier.rolpassword IS NULL,
               COALESCE(
                   verifier.rolpassword LIKE 'SCRAM-SHA-256$%',
                   FALSE
               ),
               CASE
                    WHEN verifier.rolpassword LIKE 'SCRAM-SHA-256$%' THEN
                        ((pg_catalog.regexp_match(
                            verifier.rolpassword,
                            '^SCRAM-SHA-256\$([0-9]+):'
                        ))[1])::integer
                    ELSE NULL
               END
        FROM pg_catalog.pg_roles AS role
        JOIN pg_catalog.pg_authid AS verifier ON verifier.oid = role.oid
        WHERE role.rolname::text LIKE 'ofarm\_%' ESCAPE '\'
        ORDER BY role.rolname
        """
    ).fetchall()
    observed = {row[0]: tuple(row[1:]) for row in rows}
    differences: list[str] = []
    for role in spec.roles:
        expected = (
            not role.password_required,
            role.password_required,
            spec.scram_iterations if role.password_required else None,
        )
        if observed.get(role.name) != expected:
            differences.append(f"role {role.name} password posture differs")
    return differences


def _role_differences(
    connection: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    differences = _role_surface_differences(connection, spec)
    differences.extend(_external_membership_role_differences(connection, spec))
    differences.extend(_role_password_differences(connection, spec))
    return differences


def _membership_differences(
    connection: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    rows = connection.execute(
        """
        SELECT granted.rolname::text,
               member.rolname::text,
               grantor.rolname::text,
               grantor.rolsuper,
               m.inherit_option,
               m.set_option,
               m.admin_option
        FROM pg_catalog.pg_auth_members AS m
        JOIN pg_catalog.pg_roles AS granted ON granted.oid = m.roleid
        JOIN pg_catalog.pg_roles AS member ON member.oid = m.member
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = m.grantor
        ORDER BY granted.rolname, member.rolname, grantor.rolname
        """
    ).fetchall()
    governed = set(spec.role_names)
    external_grants = {
        membership.granted_role
        for membership in spec.memberships
        if membership.granted_role not in governed
    }
    relevant = [
        row
        for row in rows
        if row[0] in governed
        or row[1] in governed
        or row[1] in external_grants
    ]
    expected = {
        (
            membership.granted_role,
            membership.member_role,
            membership.inherit,
            membership.set_role,
            membership.admin,
        )
        for membership in spec.memberships
    }
    observed = {(row[0], row[1], row[4], row[5], row[6]) for row in relevant}
    differences: list[str] = []
    for edge in sorted(expected - observed):
        differences.append(f"membership {edge[0]} -> {edge[1]} is missing or differs")
    for edge in sorted(observed - expected):
        differences.append(f"unexpected membership {edge[0]} -> {edge[1]}")
    for granted, member, _grantor, grantor_super, *_ in relevant:
        if (granted, member) in {(edge[0], edge[1]) for edge in expected}:
            if grantor_super is not True:
                differences.append(
                    f"membership {granted} -> {member} has a non-DBA grantor"
                )

    if "ofarm_binder" in governed:
        binder_paths = connection.execute(
            """
            SELECT r.rolname::text
            FROM pg_catalog.pg_roles AS r
            WHERE r.rolname <> 'ofarm_binder'
              AND NOT r.rolsuper
              AND (
                    pg_catalog.pg_has_role(r.oid, 'ofarm_binder', 'MEMBER')
                 OR pg_catalog.pg_has_role(r.oid, 'ofarm_binder', 'USAGE')
                 OR pg_catalog.pg_has_role(r.oid, 'ofarm_binder', 'SET')
                 OR pg_catalog.pg_has_role(
                        r.oid, 'ofarm_binder', 'MEMBER WITH ADMIN OPTION')
              )
            ORDER BY r.rolname
            """
        ).fetchall()
        for row in binder_paths:
            differences.append(f"role {row[0]} has a path to ofarm_binder")
    return differences


def _database_differences(
    target: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    row = target.execute(
        """
        SELECT d.datname::text,
               pg_catalog.pg_get_userbyid(d.datdba),
               pg_catalog.pg_encoding_to_char(d.encoding),
               d.datlocprovider,
               d.datcollate,
               d.datctype,
               d.datlocale,
               d.daticurules,
               d.datcollversion,
               d.datistemplate,
               d.datallowconn,
               d.datconnlimit,
               t.spcname::text,
               pg_catalog.current_setting('server_encoding')
        FROM pg_catalog.pg_database AS d
        JOIN pg_catalog.pg_tablespace AS t ON t.oid = d.dattablespace
        WHERE d.datname = pg_catalog.current_database()
        """
    ).fetchone()
    expected = (
        spec.database_name,
        spec.database_owner,
        "UTF8",
        "b",
        "C",
        "C",
        "C",
        None,
        "1",
        False,
        True,
        spec.database_connection_limit,
        "pg_default",
        "UTF8",
    )
    differences: list[str] = []
    if row is None or tuple(row) != expected:
        differences.append("database metadata differs")

    collation = target.execute(
        """
        SELECT c.collprovider,
               c.collisdeterministic,
               c.collencoding,
               c.collcollate,
               c.collctype,
               c.colllocale,
               c.collicurules,
               c.collversion
        FROM pg_catalog.pg_collation AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.collnamespace
        WHERE n.nspname = 'pg_catalog'
          AND c.collname IN ('C', 'default')
        ORDER BY c.collname
        """
    ).fetchall()
    if collation != [
        ("c", True, -1, "C", "C", None, None, None),
        ("d", True, -1, None, None, None, None, None),
    ]:
        differences.append("database-default or pg_catalog.C collation differs")
    return differences


def _acl_rows(
    connection: psycopg.Connection, object_kind: str, object_name: str
) -> set[tuple[str, str, str, bool]]:
    if object_kind == "database":
        rows = connection.execute(
            """
            SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                        ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
                   pg_catalog.pg_get_userbyid(acl.grantor),
                   acl.privilege_type,
                   acl.is_grantable
            FROM pg_catalog.pg_database AS d
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(d.datacl, pg_catalog.acldefault('d', d.datdba))
            ) AS acl
            WHERE d.datname = %s
            """,
            (object_name,),
        ).fetchall()
    elif object_kind == "schema":
        rows = connection.execute(
            """
            SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                        ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
                   pg_catalog.pg_get_userbyid(acl.grantor),
                   acl.privilege_type,
                   acl.is_grantable
            FROM pg_catalog.pg_namespace AS n
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(n.nspacl, pg_catalog.acldefault('n', n.nspowner))
            ) AS acl
            WHERE n.nspname = %s
            """,
            (object_name,),
        ).fetchall()
    else:
        raise ValueError("unknown ACL object kind")
    return {(row[0], row[1], row[2], row[3]) for row in rows}


def _namespace_and_acl_differences(
    target: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    schemas = target.execute(
        """
        SELECT n.nspname::text,
               owner.rolname::text,
               owner.rolsuper
        FROM pg_catalog.pg_namespace AS n
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = n.nspowner
        ORDER BY n.nspname
        """
    ).fetchall()
    differences: list[str] = []
    expected_schemas = {
        "information_schema",
        spec.migration_lock.schema_name,
        spec.schema_name,
        "pg_catalog",
        "pg_toast",
        "public",
    }
    if spec.native_verifier is not None:
        expected_schemas.add(spec.native_verifier.schema_name)
    if {row[0] for row in schemas} != expected_schemas:
        differences.append("database user-schema inventory or ownership differs")
    observed_schema_owners = {row[0]: (row[1], row[2]) for row in schemas}
    if observed_schema_owners.get(spec.schema_name) != (spec.schema_owner, False):
        differences.append(f"schema {spec.schema_name} owner differs")
    if observed_schema_owners.get(spec.migration_lock.schema_name) != (
        spec.migration_lock.owner_role,
        False,
    ):
        differences.append("migration-lock infrastructure schema owner differs")
    if spec.native_verifier is not None and observed_schema_owners.get(
        spec.native_verifier.schema_name
    ) != (spec.native_verifier.installer_role, True):
        differences.append("native-verifier schema owner differs")
    if observed_schema_owners.get("public") != ("pg_database_owner", False):
        differences.append("schema public owner differs")
    for system_schema in ("information_schema", "pg_catalog", "pg_toast"):
        owner = observed_schema_owners.get(system_schema)
        if owner is None or owner[1] is not True or owner[0].startswith("ofarm_"):
            differences.append(f"schema {system_schema} owner is not the external DBA")

    non_superuser_roles = [role.name for role in spec.roles if not role.superuser]
    governed_system_schema_privileges = target.execute(
        """
        SELECT role.rolname::text,
               namespace.nspname::text,
               pg_catalog.has_schema_privilege(
                   role.oid, namespace.oid, 'USAGE'
               ),
               pg_catalog.has_schema_privilege(
                   role.oid, namespace.oid, 'CREATE'
               )
        FROM pg_catalog.pg_roles AS role
        CROSS JOIN pg_catalog.pg_namespace AS namespace
        WHERE role.rolname::text = ANY (%s::text[])
          AND namespace.nspname = 'pg_catalog'
        ORDER BY 1, 2
        """,
        (non_superuser_roles,),
    ).fetchall()
    if any(
        has_usage is not True or has_create is not False
        for _role, _schema, has_usage, has_create
        in governed_system_schema_privileges
    ) or len(governed_system_schema_privileges) != len(non_superuser_roles):
        differences.append("governed role system-schema privileges differ")

    for system_schema, public_usage in (
        ("information_schema", True),
        ("pg_catalog", True),
        ("pg_toast", False),
    ):
        observed_owner = observed_schema_owners.get(system_schema)
        if observed_owner is None:
            continue
        owner_name, _owner_super = observed_owner
        expected_system_schema_acl = {
            (owner_name, owner_name, "CREATE", False),
            (owner_name, owner_name, "USAGE", False),
        }
        if public_usage:
            expected_system_schema_acl.add(
                ("PUBLIC", owner_name, "USAGE", False)
            )
        if _acl_rows(target, "schema", system_schema) != expected_system_schema_acl:
            differences.append(f"schema {system_schema} ACL differs")

    database_acl = _acl_rows(target, "database", spec.database_name)
    expected_database_acl = {
        (spec.database_owner, spec.database_owner, "CONNECT", False),
        (spec.database_owner, spec.database_owner, "CREATE", False),
        (spec.database_owner, spec.database_owner, "TEMPORARY", False),
    }
    expected_database_acl.update(
        (role_name, spec.database_owner, "CONNECT", False)
        for role_name in spec.database_connect_roles
    )
    if database_acl != expected_database_acl:
        differences.append("database ACL differs")

    target_schema_acl = _acl_rows(target, "schema", spec.schema_name)
    expected_target_schema_acl = {
        (spec.schema_owner, spec.schema_owner, "CREATE", False),
        (spec.schema_owner, spec.schema_owner, "USAGE", False),
    }
    expected_target_schema_acl.update(
        (role_name, spec.schema_owner, "USAGE", False)
        for role_name in spec.schema_usage_roles
    )
    if target_schema_acl != expected_target_schema_acl:
        differences.append(f"schema {spec.schema_name} ACL differs")

    infrastructure_schema_acl = _acl_rows(
        target, "schema", spec.migration_lock.schema_name
    )
    expected_infrastructure_schema_acl = {
        (
            spec.migration_lock.owner_role,
            spec.migration_lock.owner_role,
            "CREATE",
            False,
        ),
        (
            spec.migration_lock.owner_role,
            spec.migration_lock.owner_role,
            "USAGE",
            False,
        ),
        (
            spec.migration_lock.execute_role,
            spec.migration_lock.owner_role,
            "USAGE",
            False,
        ),
    }
    if infrastructure_schema_acl != expected_infrastructure_schema_acl:
        differences.append("migration-lock infrastructure schema ACL differs")

    if spec.native_verifier is not None:
        verifier_schema_acl = _acl_rows(
            target, "schema", spec.native_verifier.schema_name
        )
        expected_verifier_schema_acl = {
            (
                spec.native_verifier.installer_role,
                spec.native_verifier.installer_role,
                "CREATE",
                False,
            ),
            (
                spec.native_verifier.installer_role,
                spec.native_verifier.installer_role,
                "USAGE",
                False,
            ),
            (
                "ofarm_binder",
                spec.native_verifier.installer_role,
                "USAGE",
                False,
            ),
        }
        if verifier_schema_acl != expected_verifier_schema_acl:
            differences.append("native-verifier schema ACL differs")

    public_schema_acl = _acl_rows(target, "schema", "public")
    if public_schema_acl != {
        ("pg_database_owner", "pg_database_owner", "CREATE", False),
        ("pg_database_owner", "pg_database_owner", "USAGE", False),
    }:
        differences.append("schema public ACL differs")
    return differences


def _native_verifier_differences(
    target: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    """Authenticate the exact pre-ledger verification-only extension surface."""

    verifier = spec.native_verifier
    if verifier is None:
        rows = target.execute(
            """
            SELECT extension.extname::text
            FROM pg_catalog.pg_extension AS extension
            WHERE extension.extname <> 'plpgsql'
            ORDER BY extension.extname
            """
        ).fetchall()
        return [] if rows == [] else ["unexpected extension is installed"]
    if spec.tenant_admission_lock is None:
        return ["native verifier has no admission-lock owner"]

    extension_rows = target.execute(
        """
        SELECT extension.extname::text,
               extension.extversion::text,
               namespace.nspname::text,
               owner.rolname::text,
               extension.extrelocatable,
               extension.extconfig,
               extension.extcondition
        FROM pg_catalog.pg_extension AS extension
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = extension.extnamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = extension.extowner
        WHERE extension.extname <> 'plpgsql'
        ORDER BY extension.extname
        """
    ).fetchall()
    expected_extension = [
        (
            verifier.extension_name,
            verifier.extension_version,
            verifier.schema_name,
            verifier.installer_role,
            False,
            None,
            None,
        )
    ]
    differences: list[str] = []
    if extension_rows != expected_extension:
        differences.append("native-verifier extension identity differs")

    function_rows = target.execute(
        """
        SELECT routine.proname::text,
               pg_catalog.pg_get_function_identity_arguments(routine.oid),
               pg_catalog.format_type(routine.prorettype, NULL),
               owner.rolname::text,
               language.lanname::text,
               routine.prosecdef,
               routine.proisstrict,
               routine.proleakproof,
               routine.provolatile,
               routine.proparallel,
               routine.probin,
               routine.prosrc,
               routine.pronargs,
               routine.pronargdefaults,
               routine.prokind,
               routine.proconfig,
               routine.procost,
               routine.prorows,
               routine.prosupport = 0,
               routine.provariadic = 0,
               routine.proallargtypes,
               routine.proargmodes,
               routine.proargnames,
               routine.prosqlbody IS NULL,
               dependency.deptype,
               extension.extname::text
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
        LEFT JOIN pg_catalog.pg_depend AS dependency
          ON dependency.classid = 'pg_catalog.pg_proc'::pg_catalog.regclass
         AND dependency.objid = routine.oid
         AND dependency.deptype = 'e'
        LEFT JOIN pg_catalog.pg_extension AS extension
          ON extension.oid = dependency.refobjid
         AND dependency.refclassid =
             'pg_catalog.pg_extension'::pg_catalog.regclass
        WHERE namespace.nspname = %s
        ORDER BY routine.proname,
                 pg_catalog.pg_get_function_identity_arguments(routine.oid)
        """,
        (verifier.schema_name,),
    ).fetchall()
    expected_function = [
        (
            verifier.function_name,
            "public_key bytea, signed_bytes bytea, signature bytea",
            "boolean",
            verifier.installer_role,
            "c",
            False,
            True,
            False,
            "i",
            "u",
            verifier.module_pathname,
            "ofarm_ed25519_verify",
            3,
            0,
            "f",
            None,
            1.0,
            0.0,
            True,
            True,
            None,
            None,
            ["public_key", "signed_bytes", "signature"],
            True,
            "e",
            verifier.extension_name,
        )
    ]
    if function_rows != expected_function:
        differences.append("native-verifier SQL function identity differs")

    extension_members = target.execute(
        """
        SELECT dependency.classid::pg_catalog.regclass::pg_catalog.text,
               dependency.objsubid,
               dependency.deptype,
               identified.type,
               identified.schema,
               identified.name,
               identified.identity
        FROM pg_catalog.pg_depend AS dependency
        JOIN pg_catalog.pg_extension AS extension
          ON extension.oid = dependency.refobjid
        CROSS JOIN LATERAL pg_catalog.pg_identify_object(
            dependency.classid, dependency.objid, dependency.objsubid
        ) AS identified
        WHERE dependency.refclassid =
                'pg_catalog.pg_extension'::pg_catalog.regclass
          AND extension.extname = %s
        ORDER BY 1, 2, 3, 4, 5, 6, 7
        """,
        (verifier.extension_name,),
    ).fetchall()
    if extension_members != [
        (
            "pg_proc",
            0,
            "e",
            "function",
            verifier.schema_name,
            None,
            (
                f"{verifier.schema_name}.{verifier.function_name}"
                "(pg_catalog.bytea,pg_catalog.bytea,pg_catalog.bytea)"
            ),
        )
    ]:
        differences.append("native-verifier extension membership differs")

    schema_rows = target.execute(
        f"""
        WITH target_names(schema_name) AS (VALUES (%s::text))
        {SCHEMA_LOCAL_OBJECT_SELECTS_SQL}
        ORDER BY 1, 2, 3
        """,
        (verifier.schema_name,),
    ).fetchall()
    if schema_rows != [("routine", verifier.schema_name, verifier.function_name)]:
        differences.append("native-verifier schema object inventory differs")

    acl_rows = target.execute(
        """
        SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                    ELSE grantee.rolname::text END,
               grantor.rolname::text,
               acl.privilege_type,
               acl.is_grantable
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
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
        WHERE namespace.nspname = %s
          AND routine.proname = %s
          AND pg_catalog.pg_get_function_identity_arguments(routine.oid) =
              'public_key bytea, signed_bytes bytea, signature bytea'
        ORDER BY 1, 2, 3, 4
        """,
        (verifier.schema_name, verifier.function_name),
    ).fetchall()
    if acl_rows != [
        ("ofarm_binder", verifier.installer_role, "EXECUTE", False),
        (verifier.installer_role, verifier.installer_role, "EXECUTE", False),
    ]:
        differences.append("native-verifier function ACL differs")
    return differences


def _cluster_database_access_differences(
    connection: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    differences = _base_database_acl_differences(
        connection, public_privileges_expected=False
    )
    public_acl_rows = connection.execute(
        """
        SELECT database.datname::text, acl.privilege_type
        FROM pg_catalog.pg_database AS database
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                database.datacl,
                pg_catalog.acldefault('d', database.datdba)
            )
        ) AS acl
        WHERE acl.grantee = 0
        ORDER BY 1, 2
        """
    ).fetchall()
    if public_acl_rows:
        differences.append("a cluster database grants privileges to PUBLIC")

    access_rows = connection.execute(
        """
        SELECT role.rolname::text,
               database.datname::text,
               pg_catalog.has_database_privilege(
                   role.oid, database.oid, 'CONNECT'),
               pg_catalog.has_database_privilege(
                   role.oid, database.oid, 'TEMPORARY')
        FROM pg_catalog.pg_roles AS role
        CROSS JOIN pg_catalog.pg_database AS database
        WHERE role.rolname::text = ANY (%s::text[])
        ORDER BY 1, 2
        """,
        (list(spec.login_role_names),),
    ).fetchall()
    for role_name, database_name, can_connect, can_create_temporary in access_rows:
        expected_connect = database_name == spec.database_name
        if can_connect is not expected_connect or can_create_temporary is not False:
            differences.append(
                f"LOGIN role {role_name} database access differs for {database_name}"
            )
    return differences


def _database_inventory_differences(
    connection: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    if _database_names(connection) != _expected_database_names(
        spec, target_exists=True
    ):
        return ["dedicated PostgreSQL service database inventory differs"]
    return []


def _base_database_acl_differences(
    connection: psycopg.Connection,
    *,
    public_privileges_expected: bool,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT database.datname::text,
               owner.rolname::text,
               owner.rolsuper,
               CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                    ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
               pg_catalog.pg_get_userbyid(acl.grantor),
               acl.privilege_type,
               acl.is_grantable
        FROM pg_catalog.pg_database AS database
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = database.datdba
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                database.datacl,
                pg_catalog.acldefault('d', database.datdba)
            )
        ) AS acl
        WHERE database.datname = ANY (%s::text[])
        ORDER BY 1, 4, 5, 6, 7
        """,
        (sorted(_BASE_DATABASE_INVENTORY),),
    ).fetchall()
    owners = {
        database_name: (owner_name, owner_super)
        for database_name, owner_name, owner_super, *_rest in rows
    }
    differences: list[str] = []
    if set(owners) != _BASE_DATABASE_INVENTORY or any(
        owner_super is not True or owner_name.startswith("ofarm_")
        for owner_name, owner_super in owners.values()
    ):
        differences.append("maintenance database ownership differs")
        return differences

    observed = {
        (database_name, grantee, grantor, privilege, grantable)
        for (
            database_name,
            _owner_name,
            _owner_super,
            grantee,
            grantor,
            privilege,
            grantable,
        ) in rows
    }
    expected: set[tuple[str, str, str, str, bool]] = set()
    for database_name, (owner_name, _owner_super) in owners.items():
        expected.update(
            (database_name, owner_name, owner_name, privilege, False)
            for privilege in ("CONNECT", "CREATE", "TEMPORARY")
        )
        if public_privileges_expected:
            expected.add(
                (database_name, "PUBLIC", owner_name, "CONNECT", False)
            )
            if database_name == _CONTROL_DATABASE:
                expected.add(
                    (
                        database_name,
                        "PUBLIC",
                        owner_name,
                        "TEMPORARY",
                        False,
                    )
                )
    if observed != expected:
        differences.append("maintenance database ACL posture differs")
    return differences


def _global_role_default_differences(
    connection: psycopg.Connection,
) -> list[str]:
    row = connection.execute(
        """
        SELECT count(*)
        FROM pg_catalog.pg_db_role_setting
        WHERE setdatabase = 0 AND setrole = 0
        """
    ).fetchone()
    if row != (0,):
        return ["cluster-wide ALTER ROLE ALL defaults are present"]
    return []


def _cluster_service_posture_differences(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
) -> list[str]:
    tablespaces = connection.execute(
        """
        SELECT tablespace.spcname::text,
               owner.rolname::text,
               owner.rolsuper,
               CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                    ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
               pg_catalog.pg_get_userbyid(acl.grantor),
               acl.privilege_type,
               acl.is_grantable
        FROM pg_catalog.pg_tablespace AS tablespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = tablespace.spcowner
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                tablespace.spcacl,
                pg_catalog.acldefault('t', tablespace.spcowner)
            )
        ) AS acl
        ORDER BY tablespace.spcname, 4, 5, 6, 7
        """
    ).fetchall()
    differences: list[str] = []
    if {row[0] for row in tablespaces} != {"pg_default", "pg_global"}:
        differences.append("cluster tablespace inventory differs")
    if any(
        owner_super is not True or owner.startswith("ofarm_")
        for _name, owner, owner_super, *_acl in tablespaces
    ):
        differences.append("cluster tablespace owner is not the external DBA")
    tablespace_owners = {
        name: owner for name, owner, _owner_super, *_acl in tablespaces
    }
    observed_tablespace_acl = {
        (name, grantee, grantor, privilege, grantable)
        for (
            name,
            _owner,
            _owner_super,
            grantee,
            grantor,
            privilege,
            grantable,
        ) in tablespaces
    }
    expected_tablespace_acl = {
        (name, owner, owner, "CREATE", False)
        for name, owner in tablespace_owners.items()
    }
    if observed_tablespace_acl != expected_tablespace_acl:
        differences.append("cluster tablespace ACL differs")
    replication_counts = connection.execute(
        """
        SELECT
            (SELECT count(*) FROM pg_catalog.pg_replication_slots),
            (SELECT count(*) FROM pg_catalog.pg_stat_get_wal_senders()),
            (SELECT count(*)
             FROM pg_catalog.pg_stat_get_wal_receiver() AS receiver
             WHERE receiver.pid IS NOT NULL)
        """
    ).fetchone()
    if tuple(replication_counts) != (0, 0, 0):
        differences.append("replication or recovery connections are present")
    prepared_transaction_posture = connection.execute(
        """
        SELECT pg_catalog.current_setting(
                   'max_prepared_transactions'
               )::integer,
               (SELECT count(*) FROM pg_catalog.pg_prepared_xacts)
        """
    ).fetchone()
    if tuple(prepared_transaction_posture) != (
        spec.max_prepared_transactions,
        0,
    ):
        differences.append("prepared transaction posture differs")
    return differences


def _setting_differences(
    target: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    rows = target.execute(
        """
        WITH target_database AS (
            SELECT oid FROM pg_catalog.pg_database
            WHERE datname = pg_catalog.current_database()
        ), service_roles AS (
            SELECT oid FROM pg_catalog.pg_roles
            WHERE rolname::text = ANY (%s::text[])
        )
        SELECT COALESCE(d.datname::text, '*'),
               COALESCE(r.rolname::text, '*'),
               setting.value
        FROM pg_catalog.pg_db_role_setting AS configured
        LEFT JOIN pg_catalog.pg_database AS d ON d.oid = configured.setdatabase
        LEFT JOIN pg_catalog.pg_roles AS r ON r.oid = configured.setrole
        CROSS JOIN LATERAL pg_catalog.unnest(configured.setconfig) AS setting(value)
        CROSS JOIN target_database AS target
        WHERE configured.setdatabase = target.oid
           OR configured.setrole IN (SELECT oid FROM service_roles)
           OR (configured.setdatabase = 0 AND configured.setrole = 0)
        ORDER BY 1, 2, 3
        """,
        (list(spec.role_names),),
    ).fetchall()
    observed = {(row[0], row[1], row[2]) for row in rows}
    expected = {
        (spec.database_name, role.name, f"{setting.name}={setting.value}")
        for role in spec.roles
        for setting in role.settings
    }
    if observed != expected:
        return ["database/role setting posture differs"]
    return []


def _parameter_acl_differences(
    connection: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    rows = connection.execute(
        """
        SELECT parameter.parname::text,
               CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                    ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
               pg_catalog.pg_get_userbyid(acl.grantor),
               acl.privilege_type,
               acl.is_grantable
        FROM pg_catalog.pg_parameter_acl AS parameter
        CROSS JOIN LATERAL pg_catalog.aclexplode(parameter.paracl) AS acl
        WHERE acl.grantee = 0
           OR acl.grantee IN (
                SELECT oid FROM pg_catalog.pg_roles
                WHERE rolname::text = ANY (%s::text[])
           )
        ORDER BY 1, 2, 3, 4
        """,
        (list(spec.role_names),),
    ).fetchall()
    if rows:
        return ["PUBLIC or governed role has parameter privileges"]
    return []


def _default_acl_differences(
    target: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    rows = target.execute(
        """
        SELECT owner.rolname::text,
               defaults.defaclobjtype,
               COALESCE(namespace.nspname::text, '*'),
               CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                    ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
               pg_catalog.pg_get_userbyid(acl.grantor),
               acl.privilege_type,
               acl.is_grantable
        FROM pg_catalog.pg_default_acl AS defaults
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = defaults.defaclrole
        LEFT JOIN pg_catalog.pg_namespace AS namespace
               ON namespace.oid = defaults.defaclnamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(defaults.defaclacl) AS acl
        ORDER BY 1, 2, 3, 4, 5, 6, 7
        """
    ).fetchall()
    expected_owners = set(spec.default_privilege_owner_roles)
    relevant = {
        tuple(row)
        for row in rows
        if row[0].startswith("ofarm_") or row[3].startswith("ofarm_")
    }
    expected = {
        (owner, "f", "*", owner, owner, "EXECUTE", False)
        for owner in expected_owners
    } | {
        (owner, "T", "*", owner, owner, "USAGE", False)
        for owner in expected_owners
    }
    if relevant != expected:
        return ["default-privilege rows differ"]
    return []


def _routine_acl_differences(
    target: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    routine_names = sorted(
        {routine.name for routine in spec.public_execute_revoked_routines}
    )
    rows = target.execute(
        """
        SELECT routine.proname::text,
               pg_catalog.pg_get_function_identity_arguments(routine.oid),
               owner.rolname::text,
               owner.rolsuper,
               language.lanname::text,
               routine.prokind,
               routine.prosecdef,
               routine.proleakproof,
               routine.provolatile,
               routine.proparallel,
               CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                    ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
               pg_catalog.pg_get_userbyid(acl.grantor),
               acl.privilege_type,
               acl.is_grantable
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                routine.proacl,
                pg_catalog.acldefault('f', routine.proowner)
            )
        ) AS acl
        WHERE namespace.nspname = 'pg_catalog'
          AND routine.proname::text = ANY (%s::text[])
        ORDER BY 1, 2, 11, 13, 14
        """,
        (routine_names,),
    ).fetchall()
    expected_identities = {
        (routine.name, routine.identity_arguments)
        for routine in spec.public_execute_revoked_routines
    }
    observed_identities = {(row[0], row[1]) for row in rows}
    differences: list[str] = []
    if observed_identities != expected_identities:
        differences.append("raw advisory routine inventory differs")
    observed_acls: dict[
        tuple[str, str], set[tuple[str, str, str, bool]]
    ] = {}
    observed_owners: dict[tuple[str, str], str] = {}
    for (
        routine_name,
        arguments,
        owner,
        owner_super,
        language,
        routine_kind,
        security_definer,
        leakproof,
        volatility,
        parallel_safety,
        grantee,
        grantor,
        privilege,
        grantable,
    ) in rows:
        identity = (routine_name, arguments)
        observed_acls.setdefault(identity, set()).add(
            (grantee, grantor, privilege, grantable)
        )
        observed_owners[identity] = owner
        if (
            owner_super,
            owner.startswith("ofarm_"),
            language,
            routine_kind,
            security_definer,
            leakproof,
            volatility,
            parallel_safety,
        ) != (True, False, "internal", "f", False, False, "v", "r"):
            differences.append(
                f"raw advisory routine security differs: {routine_name}({arguments})"
            )

    migration_lock_identity = (
        "pg_advisory_xact_lock",
        "integer, integer",
    )
    tenant_lock_identity = ("pg_advisory_xact_lock", "bigint")
    admission_shared_identity = (
        "pg_advisory_xact_lock_shared",
        "integer, integer",
    )
    for identity in sorted(expected_identities):
        owner = observed_owners.get(identity)
        if owner is None:
            continue
        expected_acl = {(owner, owner, "EXECUTE", False)}
        if identity == migration_lock_identity:
            expected_acl.add(
                (
                    spec.migration_lock.owner_role,
                    owner,
                    "EXECUTE",
                    False,
                )
            )
            if spec.tenant_admission_lock is not None:
                expected_acl.add(
                    (
                        spec.tenant_admission_lock.exclusive_owner_role,
                        owner,
                        "EXECUTE",
                        False,
                    )
                )
        if (
            identity == admission_shared_identity
            and spec.tenant_admission_lock is not None
        ):
            expected_acl.add(
                (
                    spec.tenant_admission_lock.shared_owner_role,
                    owner,
                    "EXECUTE",
                    False,
                )
            )
        if identity == tenant_lock_identity and spec.tenant_write_lock is not None:
            expected_acl.add(
                (
                    spec.tenant_write_lock.owner_role,
                    owner,
                    "EXECUTE",
                    False,
                )
            )
        if observed_acls.get(identity, set()) != expected_acl:
            differences.append(
                f"raw advisory routine ACL differs: {identity[0]}({identity[1]})"
            )
    return differences


def _large_object_inventory_rows(
    target: psycopg.Connection,
) -> list[tuple[object, ...]]:
    return target.execute(
        """
        SELECT routine.proname::text,
               pg_catalog.pg_get_function_identity_arguments(routine.oid),
               pg_catalog.pg_get_function_result(routine.oid),
               owner.rolname::text,
               owner.rolsuper,
               language.lanname::text,
               routine.prokind,
               routine.prosecdef,
               routine.proleakproof,
               routine.proisstrict,
               routine.provolatile,
               routine.proparallel,
               routine.proretset,
               routine.pronargs,
               routine.pronargdefaults,
               routine.prosrc,
               routine.probin,
               routine.proconfig,
               routine.procost,
               routine.prorows,
               CASE WHEN routine.prosupport = 0 THEN NULL
                    ELSE routine.prosupport::pg_catalog.regprocedure::text END,
               routine.prosqlbody IS NULL
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
        WHERE namespace.nspname = 'pg_catalog'
          AND (
                pg_catalog.left(routine.proname::text, 3) = 'lo_'
             OR routine.proname::text IN ('loread', 'lowrite')
          )
        ORDER BY routine.proname,
                 pg_catalog.pg_get_function_identity_arguments(routine.oid)
        """
    ).fetchall()


def _large_object_inventory_differences(
    target: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    rows = _large_object_inventory_rows(target)
    expected = {
        (routine.name, routine.identity_arguments): routine
        for routine in spec.large_object_routines
    }
    observed = {(row[0], row[1]) for row in rows}
    differences: list[str] = []
    if observed != set(expected):
        differences.append("large-object routine inventory differs")

    for row in rows:
        identity = (row[0], row[1])
        routine_spec = expected.get(identity)
        if routine_spec is None:
            continue
        owner = row[3]
        if tuple(row[2:]) != (
            routine_spec.return_type,
            owner,
            True,
            "internal",
            "f",
            False,
            False,
            True,
            "v",
            "u",
            False,
            len(routine_spec.argument_types),
            0,
            routine_spec.internal_symbol,
            None,
            None,
            1,
            0,
            None,
            True,
        ) or owner.startswith("ofarm_"):
            differences.append(
                "large-object routine security differs: "
                f"{identity[0]}({identity[1]})"
            )
    return differences


def _large_object_routine_differences(
    target: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    differences = _large_object_inventory_differences(target, spec)
    rows = target.execute(
        """
        SELECT routine.proname::text,
               pg_catalog.pg_get_function_identity_arguments(routine.oid),
               owner.rolname::text,
               CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                    ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
               pg_catalog.pg_get_userbyid(acl.grantor),
               acl.privilege_type,
               acl.is_grantable
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
          AND (
                pg_catalog.left(routine.proname::text, 3) = 'lo_'
             OR routine.proname::text IN ('loread', 'lowrite')
          )
        ORDER BY 1, 2, 4, 6, 7
        """
    ).fetchall()
    expected_identities = {
        (routine.name, routine.identity_arguments)
        for routine in spec.large_object_routines
    }
    observed_acls: dict[
        tuple[str, str], set[tuple[str, str, str, bool]]
    ] = {}
    observed_owners: dict[tuple[str, str], str] = {}
    for (
        routine_name,
        arguments,
        owner,
        grantee,
        grantor,
        privilege,
        grantable,
    ) in rows:
        identity = (routine_name, arguments)
        observed_acls.setdefault(identity, set()).add(
            (grantee, grantor, privilege, grantable)
        )
        observed_owners[identity] = owner

    for identity in sorted(expected_identities):
        owner = observed_owners.get(identity)
        if owner is None:
            differences.append(
                f"large-object routine ACL differs: {identity[0]}({identity[1]})"
            )
            continue
        expected_acl = {(owner, owner, "EXECUTE", False)}
        if observed_acls.get(identity, set()) != expected_acl:
            differences.append(
                f"large-object routine ACL differs: {identity[0]}({identity[1]})"
            )
    return differences


def _large_object_storage_differences(
    target: psycopg.Connection,
) -> list[str]:
    row = target.execute(
        "SELECT pg_catalog.count(*)::bigint "
        "FROM pg_catalog.pg_largeobject_metadata"
    ).fetchone()
    if tuple(row or ()) != (0,):
        return ["large-object metadata row count differs"]
    return []


def _backend_statistics_routine_rows(
    target: psycopg.Connection,
) -> list[tuple[object, ...]]:
    return target.execute(
        """
        SELECT routine.proname::text,
               pg_catalog.oidvectortypes(routine.proargtypes),
               pg_catalog.pg_get_function_identity_arguments(routine.oid),
               pg_catalog.pg_get_function_arguments(routine.oid),
               pg_catalog.pg_get_function_result(routine.oid),
               owner.rolname::text,
               owner.rolsuper,
               language.lanname::text,
               routine.prokind,
               routine.prosecdef,
               routine.proleakproof,
               routine.proisstrict,
               routine.provolatile,
               routine.proparallel,
               routine.proretset,
               routine.pronargs,
               routine.pronargdefaults,
               routine.prosrc,
               routine.probin,
               routine.proconfig,
               routine.procost,
               routine.prorows,
               CASE WHEN routine.prosupport = 0 THEN NULL
                    ELSE routine.prosupport::pg_catalog.regprocedure::text END,
               routine.prosqlbody IS NULL
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
        WHERE namespace.nspname = 'pg_catalog'
          AND (
                pg_catalog.left(routine.proname::text, 20) =
                    'pg_stat_get_activity'
             OR pg_catalog.left(routine.proname::text, 20) =
                    'pg_stat_get_backend_'
          )
        ORDER BY routine.proname,
                 pg_catalog.oidvectortypes(routine.proargtypes)
        """
    ).fetchall()


def _backend_statistics_view_differences(
    target: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    rows = target.execute(
        """
        SELECT relation.relkind,
               relation.relpersistence,
               relation.relrowsecurity,
               relation.relforcerowsecurity,
               relation.relispopulated,
               relation.relreplident,
               relation.reloptions,
               relation.relhasrules,
               relation.relhastriggers,
               relation.relhassubclass,
               relation.relchecks,
               owner.rolname::text,
               owner.rolsuper,
               pg_catalog.pg_get_viewdef(relation.oid, false)
        FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = relation.relnamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = relation.relowner
        WHERE namespace.nspname = 'pg_catalog'
          AND relation.relname = 'pg_stat_activity'
        """
    ).fetchall()
    if len(rows) != 1:
        return ["pg_stat_activity view inventory differs"]
    row = rows[0]
    owner = row[11]
    if tuple(row) != (
        "v",
        "p",
        False,
        False,
        True,
        "n",
        None,
        True,
        False,
        False,
        0,
        owner,
        True,
        spec.activity_view.definition,
    ) or owner.startswith("ofarm_"):
        return ["pg_stat_activity view properties differ"]

    columns = target.execute(
        """
        SELECT attribute.attnum,
               attribute.attname::text,
               type_namespace.nspname::text,
               pg_catalog.format_type(
                   attribute.atttypid, attribute.atttypmod
               ),
                attribute.attnotnull,
                CASE WHEN attribute.attcollation = 0 THEN NULL
                    ELSE collation_namespace.nspname::text || '.' ||
                         column_collation.collname::text END,
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
    ).fetchall()
    expected_columns = [
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
        for position, column in enumerate(spec.activity_view.columns, start=1)
    ]
    if [tuple(column) for column in columns] != expected_columns:
        return ["pg_stat_activity view columns differ"]
    return []


def _backend_statistics_inventory_differences(
    target: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    rows = _backend_statistics_routine_rows(target)
    expected = {
        (routine.name, ", ".join(routine.argument_types)): routine
        for routine in spec.backend_statistics_routines
    }
    observed = {(row[0], row[1]) for row in rows}
    differences = _backend_statistics_view_differences(target, spec)
    if observed != set(expected):
        differences.append("backend-statistics routine inventory differs")

    for row in rows:
        identity = (row[0], row[1])
        routine_spec = expected.get(identity)
        if routine_spec is None:
            continue
        owner = row[5]
        if tuple(row[1:]) != (
            ", ".join(routine_spec.argument_types),
            routine_spec.identity_arguments,
            routine_spec.arguments,
            routine_spec.return_type,
            owner,
            True,
            "internal",
            "f",
            False,
            False,
            routine_spec.strict,
            "s",
            "r",
            routine_spec.returns_set,
            len(routine_spec.argument_types),
            0,
            routine_spec.internal_symbol,
            None,
            None,
            1,
            routine_spec.rows,
            None,
            True,
        ) or owner.startswith("ofarm_"):
            differences.append(
                "backend-statistics routine properties differ: "
                f"{identity[0]}({identity[1]})"
            )
    return differences


def _backend_statistics_acl_differences(
    target: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    differences = _backend_statistics_inventory_differences(target, spec)
    rows = target.execute(
        """
        SELECT routine.proname::text,
               pg_catalog.oidvectortypes(routine.proargtypes),
               owner.rolname::text,
               CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                    ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
               pg_catalog.pg_get_userbyid(acl.grantor),
               acl.privilege_type,
               acl.is_grantable
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
          AND (
                pg_catalog.left(routine.proname::text, 20) =
                    'pg_stat_get_activity'
             OR pg_catalog.left(routine.proname::text, 20) =
                    'pg_stat_get_backend_'
          )
        ORDER BY 1, 2, 4, 6, 7
        """
    ).fetchall()
    expected_identities = {
        (routine.name, ", ".join(routine.argument_types))
        for routine in spec.backend_statistics_routines
    }
    observed_acls: dict[
        tuple[str, str], set[tuple[str, str, str, bool]]
    ] = {}
    observed_owners: dict[tuple[str, str], str] = {}
    for (
        routine_name,
        arguments,
        owner,
        grantee,
        grantor,
        privilege,
        grantable,
    ) in rows:
        identity = (routine_name, arguments)
        observed_acls.setdefault(identity, set()).add(
            (grantee, grantor, privilege, grantable)
        )
        observed_owners[identity] = owner
    for identity in sorted(expected_identities):
        owner = observed_owners.get(identity)
        if owner is None:
            differences.append(
                "backend-statistics routine ACL differs: "
                f"{identity[0]}({identity[1]})"
            )
            continue
        expected_acl = {(owner, owner, "EXECUTE", False)}
        if identity == ("pg_stat_get_activity", "integer"):
            expected_acl.update(
                (role_name, owner, "EXECUTE", False)
                for role_name in spec.activity_view.select_roles
            )
        if observed_acls.get(identity, set()) != expected_acl:
            differences.append(
                "backend-statistics routine ACL differs: "
                f"{identity[0]}({identity[1]})"
            )

    view_acl_rows = target.execute(
        """
        SELECT owner.rolname::text,
               CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                    ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
               pg_catalog.pg_get_userbyid(acl.grantor),
               acl.privilege_type,
               acl.is_grantable
        FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = relation.relnamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = relation.relowner
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                relation.relacl,
                pg_catalog.acldefault('r', relation.relowner)
            )
        ) AS acl
        WHERE namespace.nspname = 'pg_catalog'
          AND relation.relname = 'pg_stat_activity'
        ORDER BY 2, 4, 5
        """
    ).fetchall()
    view_owner = view_acl_rows[0][0] if view_acl_rows else None
    expected_view_acl = {
        (view_owner, view_owner, privilege, False)
        for privilege in (
            "DELETE",
            "INSERT",
            "MAINTAIN",
            "REFERENCES",
            "SELECT",
            "TRIGGER",
            "TRUNCATE",
            "UPDATE",
        )
    }
    expected_view_acl.update(
        (role_name, view_owner, "SELECT", False)
        for role_name in spec.activity_view.select_roles
    )
    observed_view_acl = {
        (row[1], row[2], row[3], row[4]) for row in view_acl_rows
    }
    if view_owner is None or observed_view_acl != expected_view_acl:
        differences.append("pg_stat_activity view ACL differs")
    return differences


def _migration_lock_capsule_differences(
    target: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    lock = spec.migration_lock
    ledger_present = target.execute(
        "SELECT pg_catalog.to_regclass(%s) IS NOT NULL",
        (spec.migration_service.qualified_ledger,),
    ).fetchone()[0]
    rows = target.execute(
        """
        SELECT routine.proname::text,
               pg_catalog.pg_get_function_identity_arguments(routine.oid),
               owner.rolname::text,
               owner.rolsuper,
               language.lanname::text,
               routine.prokind,
               routine.prosecdef,
               routine.proleakproof,
               routine.proisstrict,
               routine.provolatile,
               routine.proparallel,
               routine.proretset,
               routine.prorettype = 'pg_catalog.void'::pg_catalog.regtype,
               routine.prosrc,
               routine.probin,
               COALESCE(routine.proconfig, ARRAY[]::text[]),
               routine.procost,
               routine.prorows,
               routine.prosupport = 0,
               routine.prosqlbody IS NULL
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
        WHERE namespace.nspname = %s
        ORDER BY routine.proname,
                 pg_catalog.pg_get_function_identity_arguments(routine.oid)
        """,
        (lock.schema_name,),
    ).fetchall()
    expected_lock = (
        lock.function_name,
        "",
        lock.owner_role,
        False,
        "sql",
        "f",
        True,
        False,
        False,
        "v",
        "u",
        False,
        True,
        lock.source,
        None,
        ["search_path=pg_catalog, pg_temp"],
        100,
        0,
        True,
        True,
    )
    differences: list[str] = []
    row_map = {(row[0], row[1]): row for row in rows}
    expected_identities = {(lock.function_name, "")}
    sealer = spec.tenant_initial_owner_sealer
    if sealer is not None and not ledger_present:
        expected_identities.add((sealer.function_name, ""))
    if set(row_map) != expected_identities:
        differences.append("migration-lock infrastructure routine differs")
    elif tuple(row_map[(lock.function_name, "")]) != expected_lock:
        differences.append("migration-lock infrastructure routine differs")

    sealer_owner: str | None = None
    if sealer is not None and not ledger_present:
        sealer_row = row_map.get((sealer.function_name, ""))
        if sealer_row is None:
            differences.append("tenant initial owner-sealer routine differs")
        else:
            sealer_owner = sealer_row[2]
            if (
                sealer_owner.startswith("ofarm_")
                or tuple(sealer_row[3:])
                != (
                    True,
                    "plpgsql",
                    "f",
                    True,
                    False,
                    False,
                    "v",
                    "u",
                    False,
                    True,
                    sealer.source,
                    None,
                    ["search_path=pg_catalog, pg_temp"],
                    100,
                    0,
                    True,
                    True,
                )
            ):
                differences.append("tenant initial owner-sealer routine differs")

    acl_rows = target.execute(
        """
        SELECT routine.proname::text,
               pg_catalog.pg_get_function_identity_arguments(routine.oid),
               CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                    ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
               pg_catalog.pg_get_userbyid(acl.grantor),
               acl.privilege_type,
               acl.is_grantable
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                routine.proacl,
                pg_catalog.acldefault('f', routine.proowner)
            )
        ) AS acl
        WHERE namespace.nspname = %s
        ORDER BY 1, 2, 3, 4, 5, 6
        """,
        (lock.schema_name,),
    ).fetchall()
    expected_acl = {
        (
            lock.function_name,
            "",
            lock.owner_role,
            lock.owner_role,
            "EXECUTE",
            False,
        ),
        (
            lock.function_name,
            "",
            lock.execute_role,
            lock.owner_role,
            "EXECUTE",
            False,
        ),
    }
    if sealer is not None and not ledger_present and sealer_owner is not None:
        expected_acl.update(
            {
                (
                    sealer.function_name,
                    "",
                    sealer_owner,
                    sealer_owner,
                    "EXECUTE",
                    False,
                ),
                (
                    sealer.function_name,
                    "",
                    sealer.execute_role,
                    sealer_owner,
                    "EXECUTE",
                    False,
                ),
            }
        )
    if {tuple(row) for row in acl_rows} != expected_acl:
        differences.append("migration-lock infrastructure routine ACL differs")

    decoration_counts = target.execute(
        """
        WITH infrastructure_objects AS (
            SELECT 'pg_catalog.pg_namespace'::pg_catalog.regclass AS classoid,
                   namespace.oid AS objoid
            FROM pg_catalog.pg_namespace AS namespace
            WHERE namespace.nspname = %s
            UNION ALL
            SELECT 'pg_catalog.pg_proc'::pg_catalog.regclass,
                   routine.oid
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            WHERE namespace.nspname = %s
        )
        SELECT (
                   SELECT count(*)
                   FROM pg_catalog.pg_description AS description
                   JOIN infrastructure_objects AS object
                     ON object.classoid = description.classoid
                    AND object.objoid = description.objoid
               ),
               (
                   SELECT count(*)
                   FROM pg_catalog.pg_seclabel AS label
                   JOIN infrastructure_objects AS object
                     ON object.classoid = label.classoid
                    AND object.objoid = label.objoid
               ),
               (
                   SELECT count(*)
                   FROM pg_catalog.pg_depend AS dependency
                   JOIN pg_catalog.pg_proc AS routine
                     ON dependency.classid =
                        'pg_catalog.pg_proc'::pg_catalog.regclass
                    AND dependency.objid = routine.oid
                   JOIN pg_catalog.pg_namespace AS namespace
                     ON namespace.oid = routine.pronamespace
                   WHERE namespace.nspname = %s
                     AND dependency.deptype = 'e'
               )
        """,
        (lock.schema_name, lock.schema_name, lock.schema_name),
    ).fetchone()
    if tuple(decoration_counts) != (0, 0, 0):
        differences.append("migration-lock infrastructure metadata differs")
    return differences


def _unmigrated_object_differences(
    target: psycopg.Connection,
    spec: ProvisioningSpec,
    *,
    allow_migration_objects: bool,
) -> tuple[list[str], bool]:
    ledger = target.execute(
        "SELECT pg_catalog.to_regclass(%s)::text",
        (spec.migration_service.qualified_ledger,),
    ).fetchone()[0]
    ledger_present = ledger is not None
    inspected_schemas = [spec.migration_lock.schema_name, "public"]
    if not allow_migration_objects:
        inspected_schemas.append(spec.schema_name)
    rows = target.execute(
        f"""
        WITH target_names AS (
            SELECT pg_catalog.unnest(%s::text[]) AS schema_name
        )
        {SCHEMA_LOCAL_OBJECT_SELECTS_SQL}
        UNION ALL
        SELECT 'extension', n.nspname::text, e.extname::text
        FROM pg_catalog.pg_extension AS e
        JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace
        WHERE NOT (e.extname = 'plpgsql' AND n.nspname = 'pg_catalog')
        UNION ALL
        SELECT 'event_trigger', '*', e.evtname::text
        FROM pg_catalog.pg_event_trigger AS e
        UNION ALL
        SELECT 'publication', '*', p.pubname::text
        FROM pg_catalog.pg_publication AS p
        UNION ALL
        SELECT 'subscription', '*', s.subname::text
        FROM pg_catalog.pg_subscription AS s
        UNION ALL
        SELECT 'foreign_data_wrapper', '*', f.fdwname::text
        FROM pg_catalog.pg_foreign_data_wrapper AS f
        UNION ALL
        SELECT 'foreign_server', '*', s.srvname::text
        FROM pg_catalog.pg_foreign_server AS s
        UNION ALL
        SELECT 'large_object', '*', l.oid::text
        FROM pg_catalog.pg_largeobject_metadata AS l
        UNION ALL
        SELECT 'transform', '*', t.oid::text
        FROM pg_catalog.pg_transform AS t
        UNION ALL
        SELECT 'cast', '*', c.oid::text
        FROM pg_catalog.pg_cast AS c
        WHERE c.oid >= %s
        UNION ALL
        SELECT 'access_method', '*', a.amname::text
        FROM pg_catalog.pg_am AS a
        WHERE a.oid >= %s
        UNION ALL
        SELECT 'language', '*', l.lanname::text
        FROM pg_catalog.pg_language AS l
        WHERE l.oid >= %s
        ORDER BY 1, 2, 3
        """,
        (
            inspected_schemas,
            _POSTGRESQL_FIRST_NORMAL_OBJECT_ID,
            _POSTGRESQL_FIRST_NORMAL_OBJECT_ID,
            _POSTGRESQL_FIRST_NORMAL_OBJECT_ID,
        ),
    ).fetchall()
    unexpected_rows = [tuple(row) for row in rows]
    # A user mapping cannot exist without a foreign server.  The server row is
    # globally visible and already refuses above, while pg_user_mapping itself
    # is intentionally unreadable to the non-superuser migration owner.
    expected_capsule_routine = (
        "routine",
        spec.migration_lock.schema_name,
        spec.migration_lock.function_name,
    )
    try:
        unexpected_rows.remove(expected_capsule_routine)
    except ValueError:
        pass
    if spec.tenant_initial_owner_sealer is not None and not ledger_present:
        expected_sealer_routine = (
            "routine",
            spec.tenant_initial_owner_sealer.schema_name,
            spec.tenant_initial_owner_sealer.function_name,
        )
        try:
            unexpected_rows.remove(expected_sealer_routine)
        except ValueError:
            pass
    if spec.native_verifier is not None:
        expected_extension = (
            "extension",
            spec.native_verifier.schema_name,
            spec.native_verifier.extension_name,
        )
        try:
            unexpected_rows.remove(expected_extension)
        except ValueError:
            pass
    differences: list[str] = []
    if ledger_present and not allow_migration_objects:
        differences.append(
            "migration ledger is present but exact structural verification is unavailable"
        )
    if unexpected_rows:
        differences.append("target contains unverified database objects")
    return differences, ledger_present


def migration_locked_differences(
    target: psycopg.Connection,
    spec: ProvisioningSpec,
) -> list[str]:
    """Repeat migration-relevant provisioning checks on the locked route.

    The caller must already hold the permanent transaction lock and have
    assumed the fixed schema owner.  Password verifier bytes remain an
    administrator-only preflight check because PostgreSQL deliberately hides
    ``pg_authid`` from this non-superuser route; every authorization-relevant
    role attribute and membership is repeated here.
    """

    _require_fixed_spec(spec)
    posture = target.execute(
        """
        SELECT SESSION_USER::text,
               CURRENT_USER::text,
               pg_catalog.current_database()::text,
               pg_catalog.current_setting('server_version_num')::integer,
               pg_catalog.current_setting('server_version')::text,
               pg_catalog.pg_is_in_recovery(),
               pg_catalog.current_setting('transaction_isolation'),
               pg_catalog.current_setting('transaction_read_only'),
               pg_catalog.current_setting('transaction_deferrable'),
               pg_catalog.current_setting('standard_conforming_strings'),
               pg_catalog.current_setting('TimeZone'),
               pg_catalog.current_setting('DateStyle'),
               pg_catalog.current_setting('quote_all_identifiers'),
               pg_catalog.current_setting('synchronous_commit'),
               pg_catalog.current_setting('row_security')
        """
    ).fetchone()
    differences: list[str] = []
    if tuple(posture or ()) != (
        "ofarm_migrator",
        spec.schema_owner,
        spec.database_name,
        SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
        SUPPORTED_POSTGRESQL_SERVER_VERSION,
        False,
        "read committed",
        "off",
        "off",
        *CATALOG_OUTPUT_SETTING_VALUES,
        "on",
        "on",
    ):
        differences.append("locked migration route or transaction posture differs")

    differences.extend(_database_inventory_differences(target, spec))
    differences.extend(_role_surface_differences(target, spec))
    differences.extend(_membership_differences(target, spec))
    differences.extend(_cluster_database_access_differences(target, spec))
    differences.extend(_cluster_service_posture_differences(target, spec))
    differences.extend(_parameter_acl_differences(target, spec))
    differences.extend(_database_differences(target, spec))
    differences.extend(_namespace_and_acl_differences(target, spec))
    differences.extend(_native_verifier_differences(target, spec))
    differences.extend(_setting_differences(target, spec))
    differences.extend(_default_acl_differences(target, spec))
    differences.extend(_routine_acl_differences(target, spec))
    differences.extend(_large_object_routine_differences(target, spec))
    differences.extend(_large_object_storage_differences(target))
    differences.extend(_backend_statistics_acl_differences(target, spec))
    differences.extend(_migration_lock_capsule_differences(target, spec))
    object_differences, _ledger_present = _unmigrated_object_differences(
        target,
        spec,
        allow_migration_objects=True,
    )
    differences.extend(object_differences)
    return differences


def _verify_locked(
    admin_dsn: str,
    spec: ProvisioningSpec,
    *,
    created: bool,
    expected_identity: _PostgresIdentity,
    allow_migration_objects: bool,
) -> ProvisioningReport:
    with psycopg.connect(
        _target_dsn(admin_dsn, spec.database_name), autocommit=True
    ) as target:
        with target.transaction():
            target.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
            )
            for assignment in CATALOG_OUTPUT_SETTING_ASSIGNMENTS:
                target.execute(f"SET LOCAL {assignment}")
            identity = _target_identity(target, spec, expected_identity)
            differences = _database_inventory_differences(target, spec)
            differences.extend(_role_differences(target, spec))
            differences.extend(_membership_differences(target, spec))
            differences.extend(
                _cluster_database_access_differences(target, spec)
            )
            differences.extend(
                _cluster_service_posture_differences(target, spec)
            )
            differences.extend(_parameter_acl_differences(target, spec))
            differences.extend(_database_differences(target, spec))
            differences.extend(_namespace_and_acl_differences(target, spec))
            differences.extend(_native_verifier_differences(target, spec))
            differences.extend(_setting_differences(target, spec))
            differences.extend(_default_acl_differences(target, spec))
            differences.extend(_routine_acl_differences(target, spec))
            differences.extend(_large_object_routine_differences(target, spec))
            differences.extend(_large_object_storage_differences(target))
            differences.extend(
                _backend_statistics_acl_differences(target, spec)
            )
            differences.extend(_migration_lock_capsule_differences(target, spec))
            object_differences, ledger_present = _unmigrated_object_differences(
                target,
                spec,
                allow_migration_objects=allow_migration_objects,
            )
            differences.extend(object_differences)
    if differences:
        raise ProvisioningDriftError(tuple(differences))
    return ProvisioningReport(
        service_identity=spec.identity,
        provisioning_spec_digest=spec.digest,
        database_name=spec.database_name,
        system_identifier=identity.system_identifier,
        server_version_num=identity.server_version_num,
        created=created,
        migration_ledger_present=ledger_present,
    )


def provision_service(
    admin_dsn: str,
    spec: ProvisioningSpec,
    *,
    login_passwords: Mapping[str, str] | None = None,
) -> ProvisioningReport:
    """Create a provably new target or read-only verify an existing target.

    Credentials are required only on the creation path and are never returned.
    If creation is interrupted, the partial target is intentionally not
    repairable by this function; an external DBA must destroy the disposable
    target and start again.
    """

    _require_fixed_spec(spec)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        for assignment in CATALOG_OUTPUT_SETTING_ASSIGNMENTS:
            admin.execute(f"SET {assignment}")
        admin_identity = _require_dba(admin, spec)
        lock_key = _acquire_lock(admin)
        try:
            database_exists = _database_exists(admin, spec.database_name)
            _require_database_inventory(
                admin, spec, target_exists=database_exists
            )
            governed_roles = _governed_role_names(admin)
            created = False
            if not database_exists:
                if governed_roles:
                    raise ProvisioningTargetError(
                        "database is absent but governed roles already exist; "
                        "the target is not provably new"
                    )
                new_cluster_differences = _base_database_acl_differences(
                    admin, public_privileges_expected=True
                )
                new_cluster_differences.extend(
                    _cluster_service_posture_differences(admin, spec)
                )
                new_cluster_differences.extend(
                    _parameter_acl_differences(admin, spec)
                )
                new_cluster_differences.extend(
                    _global_role_default_differences(admin)
                )
                if new_cluster_differences:
                    raise ProvisioningTargetError(
                        "new dedicated PostgreSQL service posture differs: "
                        + "; ".join(sorted(set(new_cluster_differences)))
                    )
                passwords = _validate_passwords(spec, login_passwords)
                _create_cluster_roles(admin, spec, passwords)
                _create_database(admin, spec)
                _configure_target(
                    admin_dsn, spec, admin_identity
                )
                created = True
            return _verify_locked(
                admin_dsn,
                spec,
                created=created,
                expected_identity=admin_identity,
                allow_migration_objects=False,
            )
        finally:
            _release_lock(admin, lock_key)


def _verify_existing_service(
    admin_dsn: str,
    spec: ProvisioningSpec,
    *,
    allow_migration_objects: bool,
) -> ProvisioningReport:
    _require_fixed_spec(spec)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        for assignment in CATALOG_OUTPUT_SETTING_ASSIGNMENTS:
            admin.execute(f"SET {assignment}")
        admin_identity = _require_dba(admin, spec)
        lock_key = _acquire_lock(admin)
        try:
            if not _database_exists(admin, spec.database_name):
                raise ProvisioningTargetError("provisioned database is absent")
            _require_database_inventory(admin, spec, target_exists=True)
            return _verify_locked(
                admin_dsn,
                spec,
                created=False,
                expected_identity=admin_identity,
                allow_migration_objects=allow_migration_objects,
            )
        finally:
            _release_lock(admin, lock_key)


def verify_service(admin_dsn: str, spec: ProvisioningSpec) -> ProvisioningReport:
    """Read-only verify exact fresh provisioning with no migration objects."""

    return _verify_existing_service(
        admin_dsn,
        spec,
        allow_migration_objects=False,
    )


def verify_service_infrastructure(
    admin_dsn: str, spec: ProvisioningSpec
) -> ProvisioningInfrastructureReport:
    """Verify provisioning while allowing migration objects in its one schema.

    This does not verify migration identity or structure.  The migration runner
    remains responsible for those checks.  Objects outside the application
    schema, including every provisioning-owned capsule object, remain exact.
    """

    report = _verify_existing_service(
        admin_dsn,
        spec,
        allow_migration_objects=True,
    )
    return ProvisioningInfrastructureReport(
        service_identity=report.service_identity,
        provisioning_spec_digest=report.provisioning_spec_digest,
        database_name=report.database_name,
        system_identifier=report.system_identifier,
        server_version_num=report.server_version_num,
    )


def _cluster_lineage_report(
    tenant: ProvisioningReport, audit: ProvisioningReport
) -> ClusterLineageReport:
    """Validate two freshly observed fixed-service reports."""

    if tenant.service_identity != TENANT_PROVISIONING_SPEC.identity:
        raise ProvisioningTargetError("tenant report has the wrong service identity")
    if audit.service_identity != SECURITY_AUDIT_PROVISIONING_SPEC.identity:
        raise ProvisioningTargetError("audit report has the wrong service identity")
    if tenant.provisioning_spec_digest != TENANT_PROVISIONING_SPEC.digest:
        raise ProvisioningTargetError("tenant report has the wrong specification digest")
    if audit.provisioning_spec_digest != SECURITY_AUDIT_PROVISIONING_SPEC.digest:
        raise ProvisioningTargetError("audit report has the wrong specification digest")
    if tenant.database_name != TENANT_PROVISIONING_SPEC.database_name:
        raise ProvisioningTargetError("tenant report has the wrong database name")
    if audit.database_name != SECURITY_AUDIT_PROVISIONING_SPEC.database_name:
        raise ProvisioningTargetError("audit report has the wrong database name")
    if tenant.server_version_num != audit.server_version_num:
        raise ProvisioningTargetError("tenant and audit PostgreSQL versions differ")
    if tenant.system_identifier == audit.system_identifier:
        raise ProvisioningTargetError(
            "tenant and audit targets share one PostgreSQL system identifier"
        )
    return ClusterLineageReport(
        tenant_system_identifier=tenant.system_identifier,
        audit_system_identifier=audit.system_identifier,
    )


def verify_provisioned_cluster_lineages(
    tenant_admin_dsn: str, audit_admin_dsn: str
) -> ClusterLineageReport:
    """Verify both services directly, then require distinct cluster lineages.

    A distinct PostgreSQL system identifier proves different cluster lineages.
    It does not prove separate current disks, WAL routes, pools, credentials,
    network routes, or backup targets; deployment evidence must cover those
    external resources independently.
    """

    tenant = verify_service(tenant_admin_dsn, TENANT_PROVISIONING_SPEC)
    audit = verify_service(audit_admin_dsn, SECURITY_AUDIT_PROVISIONING_SPEC)
    return _cluster_lineage_report(tenant, audit)
