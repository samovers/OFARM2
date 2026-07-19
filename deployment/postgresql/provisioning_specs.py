"""Closed PostgreSQL service provisioning specifications for issue #174.

The specifications in this module contain no credentials and perform no I/O.
They freeze the database, namespace, role, membership, and database-scoped
setting posture that the one-time infrastructure provisioner must create or
verify.  Runtime processes and migration runners consume observations of this
posture; they never reconcile it.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    MigrationService,
)
from deployment.postgresql.tenant_contract import TENANT_CONTEXT_ROUTINE_SIGNATURES


PROVISIONING_SPEC_DIGEST_POLICY = "OFARM_POSTGRESQL_PROVISIONING_SPEC_V1"
_SPEC_DIGEST_DOMAIN = PROVISIONING_SPEC_DIGEST_POLICY.encode("ascii") + b"\x00"
MIGRATION_LOCK_KEY_POLICY = "OFARM_POSTGRESQL_MIGRATION_LOCK_V1"
_MIGRATION_LOCK_KEY_BYTES = hashlib.sha256(
    MIGRATION_LOCK_KEY_POLICY.encode("ascii") + b"\x00"
).digest()[:8]
_MIGRATION_LOCK_KEY = (
    int.from_bytes(_MIGRATION_LOCK_KEY_BYTES[:4], "big", signed=True),
    int.from_bytes(_MIGRATION_LOCK_KEY_BYTES[4:], "big", signed=True),
)
_POSTGRES_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,62}")
_SETTING_NAME = re.compile(r"[a-z][a-z0-9_]{0,62}")


class ProvisioningSpecError(ValueError):
    """A checked-in provisioning specification is unsafe or ambiguous."""


@dataclass(frozen=True, slots=True)
class RoleSetting:
    """One exact database-scoped default for a LOGIN role.

    Most PostgreSQL timeout and planner settings are USERSET defaults, not
    hostile-session security controls.  ``temp_file_limit`` is included in
    every LOGIN role because it is a superuser-scoped hard bound.
    """

    name: str
    value: str

    def manifest(self) -> dict[str, str]:
        return {"name": self.name, "value": self.value}


@dataclass(frozen=True, slots=True)
class RoleSpec:
    """Exact non-secret PostgreSQL role attributes."""

    name: str
    login: bool
    inherit: bool
    bypass_rls: bool
    connection_limit: int
    password_required: bool = False
    settings: tuple[RoleSetting, ...] = ()

    def manifest(self) -> dict[str, object]:
        return {
            "name": self.name,
            "login": self.login,
            "superuser": False,
            "createDatabase": False,
            "createRole": False,
            "replication": False,
            "inherit": self.inherit,
            "bypassRowLevelSecurity": self.bypass_rls,
            "connectionLimit": self.connection_limit,
            "passwordRequired": self.password_required,
            "databaseSettings": [setting.manifest() for setting in self.settings],
        }


@dataclass(frozen=True, slots=True)
class MembershipSpec:
    """One exact PostgreSQL 17 role-membership edge."""

    granted_role: str
    member_role: str
    inherit: bool
    set_role: bool
    admin: bool

    def manifest(self) -> dict[str, object]:
        return {
            "grantedRole": self.granted_role,
            "memberRole": self.member_role,
            "inherit": self.inherit,
            "set": self.set_role,
            "admin": self.admin,
        }


@dataclass(frozen=True, slots=True)
class AuditProducerSpec:
    """Fixed session-user attribution for one audit event producer."""

    login_role: str
    producer: str
    component: str

    def manifest(self) -> dict[str, str]:
        return {
            "loginRole": self.login_role,
            "producer": self.producer,
            "component": self.component,
        }


@dataclass(frozen=True, slots=True)
class RoutineSpec:
    """One exact built-in routine signature whose PUBLIC EXECUTE is revoked."""

    name: str
    argument_types: tuple[str, ...]

    @property
    def identity_arguments(self) -> str:
        return ", ".join(self.argument_types)

    def manifest(self) -> dict[str, object]:
        return {
            "schema": "pg_catalog",
            "name": self.name,
            "argumentTypes": list(self.argument_types),
        }


@dataclass(frozen=True, slots=True)
class LargeObjectRoutineSpec:
    """One exact PostgreSQL 17 built-in large-object routine."""

    name: str
    argument_types: tuple[str, ...]
    return_type: str
    internal_symbol: str

    @property
    def identity_arguments(self) -> str:
        return ", ".join(self.argument_types)

    def manifest(self) -> dict[str, object]:
        return {
            "schema": "pg_catalog",
            "name": self.name,
            "argumentTypes": list(self.argument_types),
            "returnType": self.return_type,
            "implementation": {
                "language": "internal",
                "symbol": self.internal_symbol,
                "kind": "FUNCTION",
                "securityDefiner": False,
                "leakproof": False,
                "strict": True,
                "volatility": "VOLATILE",
                "parallelSafety": "UNSAFE",
                "returnsSet": False,
                "argumentCount": len(self.argument_types),
                "defaultArgumentCount": 0,
                "configuration": None,
                "cost": 1,
                "rows": 0,
                "support": None,
                "binary": None,
                "sqlBody": None,
            },
            "executePrivileges": {
                "ownerOnly": True,
                "public": False,
                "governedRoles": [],
            },
        }


@dataclass(frozen=True, slots=True)
class BackendStatisticsRoutineSpec:
    """One exact PostgreSQL 17 backend-statistics built-in routine."""

    name: str
    argument_types: tuple[str, ...]
    identity_arguments: str
    arguments: str
    return_type: str
    internal_symbol: str
    strict: bool
    returns_set: bool
    rows: int

    def manifest(self, *, execute_roles: tuple[str, ...]) -> dict[str, object]:
        return {
            "schema": "pg_catalog",
            "name": self.name,
            "inputArgumentTypes": list(self.argument_types),
            "identityArguments": self.identity_arguments,
            "arguments": self.arguments,
            "returnType": self.return_type,
            "implementation": {
                "language": "internal",
                "symbol": self.internal_symbol,
                "kind": "FUNCTION",
                "securityDefiner": False,
                "leakproof": False,
                "strict": self.strict,
                "volatility": "STABLE",
                "parallelSafety": "RESTRICTED",
                "returnsSet": self.returns_set,
                "argumentCount": len(self.argument_types),
                "defaultArgumentCount": 0,
                "configuration": None,
                "cost": 1,
                "rows": self.rows,
                "support": None,
                "binary": None,
                "sqlBody": None,
            },
            "executePrivileges": {
                "public": False,
                "governedRoles": list(execute_roles),
            },
        }


@dataclass(frozen=True, slots=True)
class ActivityViewColumnSpec:
    """One exact pg_stat_activity view column."""

    name: str
    data_type: str
    collation: str | None = None

    def manifest(self, *, position: int) -> dict[str, object]:
        return {
            "position": position,
            "name": self.name,
            "dataTypeSchema": "pg_catalog",
            "dataType": self.data_type,
            "collation": self.collation,
            "notNull": False,
            "identity": "",
            "generated": "",
            "hasDefault": False,
        }


@dataclass(frozen=True, slots=True)
class ActivityViewSpec:
    """Exact PostgreSQL 17 pg_stat_activity view and SELECT boundary."""

    columns: tuple[ActivityViewColumnSpec, ...]
    definition: str
    select_roles: tuple[str, ...]

    def manifest(self) -> dict[str, object]:
        return {
            "schema": "pg_catalog",
            "name": "pg_stat_activity",
            "kind": "VIEW",
            "persistence": "PERMANENT",
            "rowSecurity": False,
            "forceRowSecurity": False,
            "populated": True,
            "replicaIdentity": "NOTHING",
            "options": None,
            "hasRules": True,
            "hasTriggers": False,
            "hasSubclass": False,
            "checkConstraintCount": 0,
            "definition": self.definition,
            "columns": [
                column.manifest(position=position)
                for position, column in enumerate(self.columns, start=1)
            ],
            "selectPrivileges": {
                "public": False,
                "governedRoles": list(self.select_roles),
            },
        }


@dataclass(frozen=True, slots=True)
class MigrationLockSpec:
    """Exact provisioning-owned, no-caller-key migration lock wrapper."""

    schema_name: str
    owner_role: str
    function_name: str
    execute_role: str
    key_class_id: int
    key_object_id: int

    @property
    def qualified_function(self) -> str:
        return f"{self.schema_name}.{self.function_name}"

    @property
    def source(self) -> str:
        return (
            "SELECT pg_catalog.pg_advisory_xact_lock("
            f"{self.key_class_id}, {self.key_object_id})"
        )

    def manifest(self) -> dict[str, object]:
        return {
            "schema": {
                "name": self.schema_name,
                "owner": self.owner_role,
                "publicPrivileges": [],
                "usageRoles": [self.execute_role],
            },
            "function": {
                "qualifiedName": self.qualified_function,
                "argumentTypes": [],
                "returnType": "pg_catalog.void",
                "owner": self.owner_role,
                "language": "sql",
                "securityDefiner": True,
                "strict": False,
                "leakproof": False,
                "volatility": "VOLATILE",
                "parallelSafety": "UNSAFE",
                "searchPath": ["pg_catalog", "pg_temp"],
                "source": self.source,
                "executeRoles": [self.execute_role],
            },
            "lockKey": {
                "policy": MIGRATION_LOCK_KEY_POLICY,
                "namespace": "pg_advisory_xact_lock(integer,integer)",
                "classId": self.key_class_id,
                "objectId": self.key_object_id,
                "callerSelectable": False,
                "transactionScoped": True,
            },
            "rawRoutineOwnerGrant": {
                "schema": "pg_catalog",
                "name": "pg_advisory_xact_lock",
                "argumentTypes": ["integer", "integer"],
                "grantee": self.owner_role,
            },
        }


@dataclass(frozen=True, slots=True)
class RoutineOwnerTransfer:
    """One initial tenant routine whose owner is sealed exactly once."""

    schema_name: str
    function_name: str
    argument_types: tuple[str, ...]
    owner_role: str

    @property
    def identity_arguments(self) -> str:
        return ", ".join(self.argument_types)

    @property
    def qualified_identity(self) -> str:
        return (
            f"{self.schema_name}.{self.function_name}"
            f"({self.identity_arguments})"
        )

    def manifest(self) -> dict[str, object]:
        return {
            "schema": self.schema_name,
            "name": self.function_name,
            "argumentTypes": list(self.argument_types),
            "sealedOwner": self.owner_role,
        }


@dataclass(frozen=True, slots=True)
class TenantWriteLockSpec:
    """Closed owner boundary for the no-caller-key tenant write lock."""

    schema_name: str
    function_name: str
    owner_role: str

    @property
    def qualified_function(self) -> str:
        return f"{self.schema_name}.{self.function_name}"

    def manifest(self) -> dict[str, object]:
        return {
            "qualifiedName": self.qualified_function,
            "argumentTypes": [],
            "returnType": "pg_catalog.void",
            "owner": self.owner_role,
            "callerSelectableKey": False,
            "transactionScoped": True,
            "rawRoutineOwnerGrant": {
                "schema": "pg_catalog",
                "name": "pg_advisory_xact_lock",
                "argumentTypes": ["bigint"],
                "grantee": self.owner_role,
            },
        }


@dataclass(frozen=True, slots=True)
class TenantInitialOwnerSealerSpec:
    """Provisioning-superuser capsule consumed by tenant migration 0001."""

    schema_name: str
    function_name: str
    execute_role: str
    target_schema_name: str
    transfers: tuple[RoutineOwnerTransfer, ...]

    @property
    def qualified_function(self) -> str:
        return f"{self.schema_name}.{self.function_name}"

    @property
    def source(self) -> str:
        owner_roles = tuple(dict.fromkeys(item.owner_role for item in self.transfers))
        statements = [
            "BEGIN",
            "GRANT CREATE ON SCHEMA "
            f"{self.target_schema_name} TO " + ", ".join(owner_roles) + ";",
        ]
        statements.extend(
            "ALTER FUNCTION "
            f"{item.qualified_identity} OWNER TO {item.owner_role};"
            for item in self.transfers
        )
        statements.extend(
            (
                "REVOKE CREATE ON SCHEMA "
                f"{self.target_schema_name} FROM "
                + ", ".join(owner_roles)
                + ";",
                "GRANT CREATE ON SCHEMA "
                f"{self.schema_name} TO {self.execute_role};",
                f"ALTER FUNCTION {self.qualified_function}() SECURITY INVOKER;",
                f"ALTER FUNCTION {self.qualified_function}() OWNER TO "
                f"{self.execute_role};",
                "REVOKE CREATE ON SCHEMA "
                f"{self.schema_name} FROM {self.execute_role};",
                "END",
            )
        )
        return " ".join(statements)

    def manifest(self) -> dict[str, object]:
        return {
            "qualifiedName": self.qualified_function,
            "argumentTypes": [],
            "returnType": "pg_catalog.void",
            "ownerCategory": "external-provisioning-superuser",
            "language": "plpgsql",
            "securityDefiner": True,
            "strict": False,
            "leakproof": False,
            "volatility": "VOLATILE",
            "parallelSafety": "UNSAFE",
            "searchPath": ["pg_catalog", "pg_temp"],
            "source": self.source,
            "executeRoles": [self.execute_role],
            "consumedByMigrationVersion": 1,
            "postConsumption": {
                "securityInvoker": True,
                "owner": self.execute_role,
                "droppedBeforeLedgerAppend": True,
                "transientSchemaCreatePrivilegesAbsent": True,
            },
            "ownerTransfers": [item.manifest() for item in self.transfers],
        }


@dataclass(frozen=True, slots=True)
class ProvisioningSpec:
    """One database on one independently provisioned PostgreSQL service."""

    identity: str
    migration_service: MigrationService
    database_name: str
    database_owner: str
    database_connection_limit: int
    scram_iterations: int
    max_prepared_transactions: int
    schema_name: str
    schema_owner: str
    readiness_role_name: str
    migration_lock: MigrationLockSpec
    tenant_write_lock: TenantWriteLockSpec | None
    tenant_initial_owner_sealer: TenantInitialOwnerSealerSpec | None
    roles: tuple[RoleSpec, ...]
    memberships: tuple[MembershipSpec, ...]
    database_connect_roles: tuple[str, ...]
    schema_usage_roles: tuple[str, ...]
    public_execute_revoked_routines: tuple[RoutineSpec, ...]
    large_object_routines: tuple[LargeObjectRoutineSpec, ...]
    backend_statistics_routines: tuple[BackendStatisticsRoutineSpec, ...]
    activity_view: ActivityViewSpec
    audit_producers: tuple[AuditProducerSpec, ...] = ()
    intentionally_absent_login_roles: tuple[str, ...] = ()

    @property
    def role_names(self) -> tuple[str, ...]:
        return tuple(role.name for role in self.roles)

    @property
    def login_role_names(self) -> tuple[str, ...]:
        return tuple(role.name for role in self.roles if role.login)

    @property
    def required_password_role_names(self) -> tuple[str, ...]:
        return tuple(role.name for role in self.roles if role.password_required)

    @property
    def external_membership_roles(self) -> tuple[RoleSpec, ...]:
        """Fixed predefined roles trusted by an explicit membership edge."""

        if self.migration_service == TENANT_SERVICE:
            return (
                RoleSpec(
                    "pg_read_all_stats",
                    False,
                    True,
                    False,
                    -1,
                ),
            )
        return ()

    @property
    def default_privilege_owner_roles(self) -> tuple[str, ...]:
        """All roles that can own migration or provisioning routines."""

        owners = [self.schema_owner, self.migration_lock.owner_role]
        if self.tenant_write_lock is not None:
            owners.append(self.tenant_write_lock.owner_role)
        if self.tenant_initial_owner_sealer is not None:
            owners.extend(
                transfer.owner_role
                for transfer in self.tenant_initial_owner_sealer.transfers
            )
        return tuple(dict.fromkeys(owners))

    def manifest_without_digest(self) -> dict[str, object]:
        return {
            "schemaVersion": "ofarm.postgresql-provisioning-spec.v1",
            "digestPolicy": PROVISIONING_SPEC_DIGEST_POLICY,
            "identity": self.identity,
            "migrationServiceIdentity": self.migration_service.identity,
            "database": {
                "name": self.database_name,
                "owner": self.database_owner,
                "encoding": "UTF8",
                "localeProvider": "builtin",
                "locale": "C",
                "connectionLimit": self.database_connection_limit,
            },
            "credentialPosture": {
                "passwordVerifier": "SCRAM-SHA-256",
                "scramIterations": self.scram_iterations,
                "plaintextInSql": False,
            },
            "transactionPosture": {
                "maxPreparedTransactions": self.max_prepared_transactions,
                "preparedTransactionsAllowed": False,
            },
            "schema": {
                "name": self.schema_name,
                "owner": self.schema_owner,
                "publicPrivileges": [],
                "usageRoles": list(self.schema_usage_roles),
            },
            "preLedgerBootstrap": {
                "migrationLock": self.migration_lock.manifest(),
                "tenantInitialBinderSealer": (
                    None
                    if self.tenant_initial_owner_sealer is None
                    else self.tenant_initial_owner_sealer.manifest()
                ),
            },
            "tenantWriteLock": (
                None
                if self.tenant_write_lock is None
                else self.tenant_write_lock.manifest()
            ),
            "roles": [role.manifest() for role in self.roles],
            **(
                {
                    "externalMembershipRoleTrustAnchors": [
                        role.manifest()
                        for role in self.external_membership_roles
                    ]
                }
                if self.external_membership_roles
                else {}
            ),
            "memberships": [membership.manifest() for membership in self.memberships],
            "databaseConnectRoles": list(self.database_connect_roles),
            "publicExecuteRevokedRoutines": [
                routine.manifest()
                for routine in self.public_execute_revoked_routines
            ],
            "largeObjectPosture": {
                "metadataRowCount": 0,
                "builtInRoutines": [
                    routine.manifest()
                    for routine in self.large_object_routines
                ],
            },
            "backendStatisticsPosture": {
                "activityView": self.activity_view.manifest(),
                "builtInRoutines": [
                    routine.manifest(
                        execute_roles=(
                            self.activity_view.select_roles
                            if routine.name == "pg_stat_get_activity"
                            else ()
                        )
                    )
                    for routine in self.backend_statistics_routines
                ],
            },
            "auditSessionProducers": [
                producer.manifest() for producer in self.audit_producers
            ],
            "intentionallyAbsentLoginRoles": list(
                self.intentionally_absent_login_roles
            ),
            "v1RecoveryPosture": {
                "backup": False,
                "restore": False,
                "pointInTimePromotion": False,
                "snapshotAdoption": False,
                "logicalImport": False,
                "recoveryReadiness": False,
            },
        }

    def canonical_manifest_without_digest_bytes(self) -> bytes:
        return _canonical_json(self.manifest_without_digest())

    @property
    def digest(self) -> str:
        source = _SPEC_DIGEST_DOMAIN + self.canonical_manifest_without_digest_bytes()
        return "sha256:" + hashlib.sha256(source).hexdigest()

    def manifest(self) -> dict[str, object]:
        value = self.manifest_without_digest()
        value["provisioningSpecDigest"] = self.digest
        return value

    def canonical_manifest_bytes(self) -> bytes:
        return _canonical_json(self.manifest())


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def _settings(
    *,
    statement_timeout_ms: int,
    lock_timeout_ms: int,
    idle_transaction_timeout_ms: int,
    transaction_timeout_ms: int,
    temp_file_limit_kib: int,
    work_mem_kib: int,
) -> tuple[RoleSetting, ...]:
    return tuple(
        RoleSetting(name, value)
        for name, value in (
            ("idle_in_transaction_session_timeout", str(idle_transaction_timeout_ms)),
            ("jit", "off"),
            ("lock_timeout", str(lock_timeout_ms)),
            ("max_parallel_workers_per_gather", "0"),
            ("row_security", "on"),
            ("search_path", "pg_catalog"),
            ("statement_timeout", str(statement_timeout_ms)),
            ("synchronous_commit", "on"),
            ("temp_file_limit", str(temp_file_limit_kib)),
            ("transaction_timeout", str(transaction_timeout_ms)),
            ("work_mem", str(work_mem_kib)),
        )
    )


_MIGRATOR_SETTINGS = _settings(
    statement_timeout_ms=900_000,
    lock_timeout_ms=5_000,
    idle_transaction_timeout_ms=60_000,
    transaction_timeout_ms=900_000,
    temp_file_limit_kib=1_048_576,
    work_mem_kib=65_536,
)
_APPLICATION_SETTINGS = _settings(
    statement_timeout_ms=30_000,
    lock_timeout_ms=2_000,
    idle_transaction_timeout_ms=10_000,
    transaction_timeout_ms=60_000,
    temp_file_limit_kib=65_536,
    work_mem_kib=4_096,
)
_WORKER_SETTINGS = _settings(
    statement_timeout_ms=60_000,
    lock_timeout_ms=2_000,
    idle_transaction_timeout_ms=10_000,
    transaction_timeout_ms=120_000,
    temp_file_limit_kib=131_072,
    work_mem_kib=8_192,
)
_CONTROL_SETTINGS = _settings(
    statement_timeout_ms=5_000,
    lock_timeout_ms=500,
    idle_transaction_timeout_ms=5_000,
    transaction_timeout_ms=10_000,
    temp_file_limit_kib=0,
    work_mem_kib=1_024,
)
_READINESS_SETTINGS = _settings(
    statement_timeout_ms=2_000,
    lock_timeout_ms=250,
    idle_transaction_timeout_ms=3_000,
    transaction_timeout_ms=5_000,
    temp_file_limit_kib=0,
    work_mem_kib=1_024,
)
_AUDIT_PRODUCER_SETTINGS = _settings(
    statement_timeout_ms=2_000,
    lock_timeout_ms=250,
    idle_transaction_timeout_ms=3_000,
    transaction_timeout_ms=5_000,
    temp_file_limit_kib=0,
    work_mem_kib=1_024,
)
_AUDIT_OPERATOR_SETTINGS = _settings(
    statement_timeout_ms=5_000,
    lock_timeout_ms=500,
    idle_transaction_timeout_ms=10_000,
    transaction_timeout_ms=15_000,
    temp_file_limit_kib=0,
    work_mem_kib=1_024,
)
_AUDIT_RETENTION_SETTINGS = _settings(
    statement_timeout_ms=15_000,
    lock_timeout_ms=500,
    idle_transaction_timeout_ms=10_000,
    transaction_timeout_ms=30_000,
    temp_file_limit_kib=0,
    work_mem_kib=1_024,
)


_ADVISORY_LOCK_ROUTINES = tuple(
    RoutineSpec(name, argument_types)
    for name, argument_types in (
        ("pg_advisory_lock", ("bigint",)),
        ("pg_advisory_lock", ("integer", "integer")),
        ("pg_advisory_lock_shared", ("bigint",)),
        ("pg_advisory_lock_shared", ("integer", "integer")),
        ("pg_advisory_unlock", ("bigint",)),
        ("pg_advisory_unlock", ("integer", "integer")),
        ("pg_advisory_unlock_all", ()),
        ("pg_advisory_unlock_shared", ("bigint",)),
        ("pg_advisory_unlock_shared", ("integer", "integer")),
        ("pg_advisory_xact_lock", ("bigint",)),
        ("pg_advisory_xact_lock", ("integer", "integer")),
        ("pg_advisory_xact_lock_shared", ("bigint",)),
        ("pg_advisory_xact_lock_shared", ("integer", "integer")),
        ("pg_try_advisory_lock", ("bigint",)),
        ("pg_try_advisory_lock", ("integer", "integer")),
        ("pg_try_advisory_lock_shared", ("bigint",)),
        ("pg_try_advisory_lock_shared", ("integer", "integer")),
        ("pg_try_advisory_xact_lock", ("bigint",)),
        ("pg_try_advisory_xact_lock", ("integer", "integer")),
        ("pg_try_advisory_xact_lock_shared", ("bigint",)),
        ("pg_try_advisory_xact_lock_shared", ("integer", "integer")),
    )
)


_LARGE_OBJECT_ROUTINES = tuple(
    LargeObjectRoutineSpec(name, argument_types, return_type, internal_symbol)
    for name, argument_types, return_type, internal_symbol in (
        ("lo_close", ("integer",), "integer", "be_lo_close"),
        ("lo_creat", ("integer",), "oid", "be_lo_creat"),
        ("lo_create", ("oid",), "oid", "be_lo_create"),
        ("lo_export", ("oid", "text"), "integer", "be_lo_export"),
        (
            "lo_from_bytea",
            ("oid", "bytea"),
            "oid",
            "be_lo_from_bytea",
        ),
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
        (
            "lo_put",
            ("oid", "bigint", "bytea"),
            "void",
            "be_lo_put",
        ),
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
        (
            "loread",
            ("integer", "integer"),
            "bytea",
            "be_loread",
        ),
        (
            "lowrite",
            ("integer", "bytea"),
            "integer",
            "be_lowrite",
        ),
    )
)


_PG_STAT_GET_ACTIVITY_ARGUMENTS = (
    "pid integer, OUT datid oid, OUT pid integer, OUT usesysid oid, "
    "OUT application_name text, OUT state text, OUT query text, "
    "OUT wait_event_type text, OUT wait_event text, "
    "OUT xact_start timestamp with time zone, "
    "OUT query_start timestamp with time zone, "
    "OUT backend_start timestamp with time zone, "
    "OUT state_change timestamp with time zone, OUT client_addr inet, "
    "OUT client_hostname text, OUT client_port integer, "
    "OUT backend_xid xid, OUT backend_xmin xid, OUT backend_type text, "
    "OUT ssl boolean, OUT sslversion text, OUT sslcipher text, "
    "OUT sslbits integer, OUT ssl_client_dn text, "
    "OUT ssl_client_serial numeric, OUT ssl_issuer_dn text, "
    "OUT gss_auth boolean, OUT gss_princ text, OUT gss_enc boolean, "
    "OUT gss_delegation boolean, OUT leader_pid integer, "
    "OUT query_id bigint"
)
_PG_STAT_GET_BACKEND_SUBXACT_ARGUMENTS = (
    "bid integer, OUT subxact_count integer, OUT subxact_overflowed boolean"
)


_BACKEND_STATISTICS_ROUTINES = (
    BackendStatisticsRoutineSpec(
        "pg_stat_get_activity",
        ("integer",),
        _PG_STAT_GET_ACTIVITY_ARGUMENTS,
        _PG_STAT_GET_ACTIVITY_ARGUMENTS,
        "SETOF record",
        "pg_stat_get_activity",
        False,
        True,
        100,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_activity",
        ("integer",),
        "integer",
        "integer",
        "text",
        "pg_stat_get_backend_activity",
        True,
        False,
        0,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_activity_start",
        ("integer",),
        "integer",
        "integer",
        "timestamp with time zone",
        "pg_stat_get_backend_activity_start",
        True,
        False,
        0,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_client_addr",
        ("integer",),
        "integer",
        "integer",
        "inet",
        "pg_stat_get_backend_client_addr",
        True,
        False,
        0,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_client_port",
        ("integer",),
        "integer",
        "integer",
        "integer",
        "pg_stat_get_backend_client_port",
        True,
        False,
        0,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_dbid",
        ("integer",),
        "integer",
        "integer",
        "oid",
        "pg_stat_get_backend_dbid",
        True,
        False,
        0,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_idset",
        (),
        "",
        "",
        "SETOF integer",
        "pg_stat_get_backend_idset",
        True,
        True,
        100,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_pid",
        ("integer",),
        "integer",
        "integer",
        "integer",
        "pg_stat_get_backend_pid",
        True,
        False,
        0,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_start",
        ("integer",),
        "integer",
        "integer",
        "timestamp with time zone",
        "pg_stat_get_backend_start",
        True,
        False,
        0,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_subxact",
        ("integer",),
        _PG_STAT_GET_BACKEND_SUBXACT_ARGUMENTS,
        _PG_STAT_GET_BACKEND_SUBXACT_ARGUMENTS,
        "record",
        "pg_stat_get_backend_subxact",
        True,
        False,
        0,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_userid",
        ("integer",),
        "integer",
        "integer",
        "oid",
        "pg_stat_get_backend_userid",
        True,
        False,
        0,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_wait_event",
        ("integer",),
        "integer",
        "integer",
        "text",
        "pg_stat_get_backend_wait_event",
        True,
        False,
        0,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_wait_event_type",
        ("integer",),
        "integer",
        "integer",
        "text",
        "pg_stat_get_backend_wait_event_type",
        True,
        False,
        0,
    ),
    BackendStatisticsRoutineSpec(
        "pg_stat_get_backend_xact_start",
        ("integer",),
        "integer",
        "integer",
        "timestamp with time zone",
        "pg_stat_get_backend_xact_start",
        True,
        False,
        0,
    ),
)


_PG_STAT_ACTIVITY_VIEW_DEFINITION = (
    " SELECT s.datid,\n"
    "    d.datname,\n"
    "    s.pid,\n"
    "    s.leader_pid,\n"
    "    s.usesysid,\n"
    "    u.rolname AS usename,\n"
    "    s.application_name,\n"
    "    s.client_addr,\n"
    "    s.client_hostname,\n"
    "    s.client_port,\n"
    "    s.backend_start,\n"
    "    s.xact_start,\n"
    "    s.query_start,\n"
    "    s.state_change,\n"
    "    s.wait_event_type,\n"
    "    s.wait_event,\n"
    "    s.state,\n"
    "    s.backend_xid,\n"
    "    s.backend_xmin,\n"
    "    s.query_id,\n"
    "    s.query,\n"
    "    s.backend_type\n"
    "   FROM ((pg_stat_get_activity(NULL::integer) "
    "s(datid, pid, usesysid, application_name, state, query, "
    "wait_event_type, wait_event, xact_start, query_start, backend_start, "
    "state_change, client_addr, client_hostname, client_port, backend_xid, "
    "backend_xmin, backend_type, ssl, sslversion, sslcipher, sslbits, "
    "ssl_client_dn, ssl_client_serial, ssl_issuer_dn, gss_auth, gss_princ, "
    "gss_enc, gss_delegation, leader_pid, query_id)\n"
    "     LEFT JOIN pg_database d ON ((s.datid = d.oid)))\n"
    "     LEFT JOIN pg_authid u ON ((s.usesysid = u.oid)));"
)


_PG_STAT_ACTIVITY_VIEW_COLUMNS = tuple(
    ActivityViewColumnSpec(name, data_type, collation)
    for name, data_type, collation in (
        ("datid", "oid", None),
        ("datname", "name", "pg_catalog.C"),
        ("pid", "integer", None),
        ("leader_pid", "integer", None),
        ("usesysid", "oid", None),
        ("usename", "name", "pg_catalog.C"),
        ("application_name", "text", "pg_catalog.default"),
        ("client_addr", "inet", None),
        ("client_hostname", "text", "pg_catalog.default"),
        ("client_port", "integer", None),
        ("backend_start", "timestamp with time zone", None),
        ("xact_start", "timestamp with time zone", None),
        ("query_start", "timestamp with time zone", None),
        ("state_change", "timestamp with time zone", None),
        ("wait_event_type", "text", "pg_catalog.default"),
        ("wait_event", "text", "pg_catalog.default"),
        ("state", "text", "pg_catalog.default"),
        ("backend_xid", "xid", None),
        ("backend_xmin", "xid", None),
        ("query_id", "bigint", None),
        ("query", "text", "pg_catalog.default"),
        ("backend_type", "text", "pg_catalog.default"),
    )
)


_TENANT_WRITE_LOCK = TenantWriteLockSpec(
    schema_name="ofarm",
    function_name="take_tenant_write_lock",
    owner_role="ofarm_tenant_lock_owner",
)

_TENANT_INITIAL_OWNER_SEALER = TenantInitialOwnerSealerSpec(
    schema_name="ofarm_infrastructure",
    function_name="seal_tenant_routine_owners",
    execute_role="ofarm_migrator",
    target_schema_name="ofarm",
    transfers=(
        RoutineOwnerTransfer(
            "ofarm", "create_tenant_challenge", (), "ofarm_binder"
        ),
        RoutineOwnerTransfer("ofarm", "current_tenant_id", (), "ofarm_binder"),
        RoutineOwnerTransfer(
            "ofarm",
            "current_backend_start",
            (),
            "ofarm_backend_observer",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "backend_incarnation_is_live",
            ("integer", "timestamp with time zone"),
            "ofarm_backend_observer",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "validate_promotion_edge",
            (),
            "ofarm_graph_validator",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "require_promotion_reachability",
            (),
            "ofarm_graph_validator",
        ),
        RoutineOwnerTransfer(
            "ofarm", "take_tenant_write_lock", (), "ofarm_tenant_lock_owner"
        ),
    ),
)


TENANT_PROVISIONING_SPEC = ProvisioningSpec(
    identity="ofarm.tenant-postgresql-provisioning.v1",
    migration_service=TENANT_SERVICE,
    database_name="ofarm_tenant",
    database_owner="ofarm_owner",
    database_connection_limit=48,
    scram_iterations=4096,
    max_prepared_transactions=0,
    schema_name="ofarm",
    schema_owner="ofarm_owner",
    readiness_role_name="ofarm_readiness",
    migration_lock=MigrationLockSpec(
        schema_name="ofarm_infrastructure",
        owner_role="ofarm_tenant_migration_lock_owner",
        function_name="take_migration_lock",
        execute_role="ofarm_migrator",
        key_class_id=_MIGRATION_LOCK_KEY[0],
        key_object_id=_MIGRATION_LOCK_KEY[1],
    ),
    tenant_write_lock=_TENANT_WRITE_LOCK,
    tenant_initial_owner_sealer=_TENANT_INITIAL_OWNER_SEALER,
    roles=(
        RoleSpec("ofarm_owner", False, False, False, -1),
        RoleSpec(
            "ofarm_tenant_migration_lock_owner", False, False, False, -1
        ),
        RoleSpec("ofarm_tenant_lock_owner", False, False, False, -1),
        RoleSpec(
            "ofarm_migrator", True, False, False, 2, True, _MIGRATOR_SETTINGS
        ),
        RoleSpec(
            "ofarm_app", True, True, False, 24, True, _APPLICATION_SETTINGS
        ),
        RoleSpec(
            "ofarm_worker", True, True, False, 12, True, _WORKER_SETTINGS
        ),
        RoleSpec(
            "ofarm_readiness", True, True, False, 2, True, _READINESS_SETTINGS
        ),
        RoleSpec("ofarm_tenant_registrar", False, False, False, -1),
        RoleSpec(
            "ofarm_tenant_control_login",
            True,
            True,
            False,
            1,
            True,
            _CONTROL_SETTINGS,
        ),
        RoleSpec("ofarm_identity_writer", False, False, False, -1),
        RoleSpec(
            "ofarm_identity_control_login",
            True,
            True,
            False,
            1,
            True,
            _CONTROL_SETTINGS,
        ),
        RoleSpec("ofarm_binder", False, False, True, -1),
        RoleSpec("ofarm_backend_observer", False, True, False, -1),
        RoleSpec("ofarm_graph_validator", False, False, False, -1),
    ),
    memberships=(
        MembershipSpec("ofarm_owner", "ofarm_migrator", False, True, False),
        MembershipSpec(
            "ofarm_tenant_registrar",
            "ofarm_tenant_control_login",
            True,
            False,
            False,
        ),
        MembershipSpec(
            "ofarm_identity_writer",
            "ofarm_identity_control_login",
            True,
            False,
            False,
        ),
        MembershipSpec(
            "pg_read_all_stats",
            "ofarm_backend_observer",
            True,
            False,
            False,
        ),
    ),
    database_connect_roles=(
        "ofarm_migrator",
        "ofarm_app",
        "ofarm_worker",
        "ofarm_readiness",
        "ofarm_tenant_registrar",
        "ofarm_identity_writer",
    ),
    schema_usage_roles=(
        "ofarm_app",
        "ofarm_worker",
        "ofarm_readiness",
        "ofarm_tenant_registrar",
        "ofarm_identity_writer",
        "ofarm_binder",
        "ofarm_graph_validator",
        "ofarm_tenant_lock_owner",
    ),
    public_execute_revoked_routines=_ADVISORY_LOCK_ROUTINES,
    large_object_routines=_LARGE_OBJECT_ROUTINES,
    backend_statistics_routines=_BACKEND_STATISTICS_ROUTINES,
    activity_view=ActivityViewSpec(
        columns=_PG_STAT_ACTIVITY_VIEW_COLUMNS,
        definition=_PG_STAT_ACTIVITY_VIEW_DEFINITION,
        select_roles=("ofarm_backend_observer",),
    ),
    intentionally_absent_login_roles=(
        "ofarm_backup_reader",
        "ofarm_restore_operator",
        "ofarm_recovery_readiness",
    ),
)


SECURITY_AUDIT_PROVISIONING_SPEC = ProvisioningSpec(
    identity="ofarm.security-audit-postgresql-provisioning.v1",
    migration_service=SECURITY_AUDIT_SERVICE,
    database_name="ofarm_security_audit",
    database_owner="ofarm_security_audit_owner",
    database_connection_limit=16,
    scram_iterations=4096,
    max_prepared_transactions=0,
    schema_name="ofarm_security",
    schema_owner="ofarm_security_audit_owner",
    readiness_role_name="ofarm_security_audit_readiness",
    migration_lock=MigrationLockSpec(
        schema_name="ofarm_infrastructure",
        owner_role="ofarm_security_audit_migration_lock_owner",
        function_name="take_migration_lock",
        execute_role="ofarm_migrator",
        key_class_id=_MIGRATION_LOCK_KEY[0],
        key_object_id=_MIGRATION_LOCK_KEY[1],
    ),
    tenant_write_lock=None,
    tenant_initial_owner_sealer=None,
    roles=(
        RoleSpec("ofarm_security_audit_owner", False, False, False, -1),
        RoleSpec(
            "ofarm_security_audit_migration_lock_owner",
            False,
            False,
            False,
            -1,
        ),
        RoleSpec(
            "ofarm_migrator", True, False, False, 2, True, _MIGRATOR_SETTINGS
        ),
        RoleSpec("ofarm_security_audit_ingest", False, False, False, -1),
        RoleSpec("ofarm_security_audit_control", False, False, False, -1),
        RoleSpec("ofarm_security_audit_reader", False, False, False, -1),
        RoleSpec("ofarm_security_audit_export", False, False, False, -1),
        RoleSpec("ofarm_security_audit_retention", False, False, False, -1),
        RoleSpec("ofarm_security_audit_readiness", False, False, False, -1),
        RoleSpec(
            "ofarm_security_authentication_producer_login",
            True,
            True,
            False,
            2,
            True,
            _AUDIT_PRODUCER_SETTINGS,
        ),
        RoleSpec(
            "ofarm_security_request_router_producer_login",
            True,
            True,
            False,
            4,
            True,
            _AUDIT_PRODUCER_SETTINGS,
        ),
        RoleSpec(
            "ofarm_security_audit_control_login",
            True,
            True,
            False,
            1,
            True,
            _AUDIT_OPERATOR_SETTINGS,
        ),
        RoleSpec(
            "ofarm_security_audit_reader_login",
            True,
            True,
            False,
            2,
            True,
            _AUDIT_OPERATOR_SETTINGS,
        ),
        RoleSpec(
            "ofarm_security_audit_retention_login",
            True,
            True,
            False,
            1,
            True,
            _AUDIT_RETENTION_SETTINGS,
        ),
        RoleSpec(
            "ofarm_security_audit_readiness_login",
            True,
            True,
            False,
            2,
            True,
            _READINESS_SETTINGS,
        ),
    ),
    memberships=(
        MembershipSpec(
            "ofarm_security_audit_owner", "ofarm_migrator", False, True, False
        ),
        MembershipSpec(
            "ofarm_security_audit_ingest",
            "ofarm_security_authentication_producer_login",
            True,
            False,
            False,
        ),
        MembershipSpec(
            "ofarm_security_audit_ingest",
            "ofarm_security_request_router_producer_login",
            True,
            False,
            False,
        ),
        MembershipSpec(
            "ofarm_security_audit_control",
            "ofarm_security_audit_control_login",
            True,
            False,
            False,
        ),
        MembershipSpec(
            "ofarm_security_audit_reader",
            "ofarm_security_audit_reader_login",
            True,
            False,
            False,
        ),
        MembershipSpec(
            "ofarm_security_audit_retention",
            "ofarm_security_audit_retention_login",
            True,
            False,
            False,
        ),
        MembershipSpec(
            "ofarm_security_audit_readiness",
            "ofarm_security_audit_readiness_login",
            True,
            False,
            False,
        ),
    ),
    database_connect_roles=(
        "ofarm_migrator",
        "ofarm_security_audit_ingest",
        "ofarm_security_audit_control",
        "ofarm_security_audit_reader",
        "ofarm_security_audit_export",
        "ofarm_security_audit_retention",
        "ofarm_security_audit_readiness",
    ),
    schema_usage_roles=(
        "ofarm_security_audit_ingest",
        "ofarm_security_audit_control",
        "ofarm_security_audit_reader",
        "ofarm_security_audit_export",
        "ofarm_security_audit_retention",
        "ofarm_security_audit_readiness",
    ),
    public_execute_revoked_routines=_ADVISORY_LOCK_ROUTINES,
    large_object_routines=_LARGE_OBJECT_ROUTINES,
    backend_statistics_routines=_BACKEND_STATISTICS_ROUTINES,
    activity_view=ActivityViewSpec(
        columns=_PG_STAT_ACTIVITY_VIEW_COLUMNS,
        definition=_PG_STAT_ACTIVITY_VIEW_DEFINITION,
        select_roles=(),
    ),
    audit_producers=(
        AuditProducerSpec(
            "ofarm_security_authentication_producer_login",
            "AUTHENTICATION_BOUNDARY_V1",
            "AUTHENTICATION",
        ),
        AuditProducerSpec(
            "ofarm_security_request_router_producer_login",
            "REQUEST_ROUTER_BOUNDARY_V1",
            "REQUEST_ROUTER",
        ),
        AuditProducerSpec(
            "ofarm_security_audit_control_login",
            "SECURITY_OPERATIONS_V1",
            "AUDIT_CONTROL",
        ),
        AuditProducerSpec(
            "ofarm_security_audit_retention_login",
            "SECURITY_OPERATIONS_V1",
            "AUDIT_RETENTION",
        ),
    ),
    intentionally_absent_login_roles=(
        "ofarm_security_audit_export_login",
        "ofarm_security_audit_backup_reader",
        "ofarm_security_audit_restore_operator",
    ),
)


def _validate_identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or _POSTGRES_IDENTIFIER.fullmatch(value) is None:
        raise ProvisioningSpecError(f"{label} is not a closed PostgreSQL identifier")


def _validate_spec(spec: ProvisioningSpec) -> None:
    _validate_identifier(spec.database_name, "database name")
    _validate_identifier(spec.schema_name, "schema name")
    if spec.schema_name != spec.migration_service.schema_name:
        raise ProvisioningSpecError("provisioned schema differs from migration service")
    if spec.database_connection_limit <= 0:
        raise ProvisioningSpecError("database connection limit must be positive")
    if spec.scram_iterations != 4096:
        raise ProvisioningSpecError("PostgreSQL 17 SCRAM iterations must be exact")
    if spec.max_prepared_transactions != 0:
        raise ProvisioningSpecError("prepared transactions must be disabled in V1")

    lock = spec.migration_lock
    _validate_identifier(lock.schema_name, "migration-lock schema name")
    _validate_identifier(lock.owner_role, "migration-lock owner role")
    _validate_identifier(lock.function_name, "migration-lock function name")
    _validate_identifier(lock.execute_role, "migration-lock execute role")
    if lock.schema_name in {
        spec.schema_name,
        "information_schema",
        "pg_catalog",
        "pg_toast",
        "public",
    }:
        raise ProvisioningSpecError(
            "migration-lock schema must be a separate infrastructure namespace"
        )
    if (lock.key_class_id, lock.key_object_id) != _MIGRATION_LOCK_KEY:
        raise ProvisioningSpecError("migration-lock key does not match its policy")
    if lock.function_name != "take_migration_lock":
        raise ProvisioningSpecError("migration-lock function name is not exact")
    if lock.execute_role != "ofarm_migrator":
        raise ProvisioningSpecError("only ofarm_migrator may execute the lock wrapper")

    role_names = spec.role_names
    if len(role_names) != len(set(role_names)):
        raise ProvisioningSpecError("role names must be unique")
    role_map = {role.name: role for role in spec.roles}
    for role in spec.roles:
        _validate_identifier(role.name, "role name")
        if not role.name.startswith("ofarm_"):
            raise ProvisioningSpecError("every governed role must use the ofarm_ prefix")
        if role.login != role.password_required:
            raise ProvisioningSpecError(
                f"role {role.name} must require a password exactly when it can LOGIN"
            )
        if role.login and role.connection_limit <= 0:
            raise ProvisioningSpecError(
                f"LOGIN role {role.name} must have a positive connection limit"
            )
        if not role.login and role.connection_limit != -1:
            raise ProvisioningSpecError(
                f"NOLOGIN role {role.name} must use connection limit -1"
            )
        setting_names = tuple(setting.name for setting in role.settings)
        if role.login and set(setting_names) != {
            "idle_in_transaction_session_timeout",
            "jit",
            "lock_timeout",
            "max_parallel_workers_per_gather",
            "row_security",
            "search_path",
            "statement_timeout",
            "synchronous_commit",
            "temp_file_limit",
            "transaction_timeout",
            "work_mem",
        }:
            raise ProvisioningSpecError(
                f"LOGIN role {role.name} has an incomplete setting posture"
            )
        if not role.login and role.settings:
            raise ProvisioningSpecError(
                f"NOLOGIN role {role.name} must not carry session defaults"
            )
        if len(setting_names) != len(set(setting_names)):
            raise ProvisioningSpecError(f"role {role.name} repeats a setting")
        for setting in role.settings:
            if _SETTING_NAME.fullmatch(setting.name) is None or not setting.value:
                raise ProvisioningSpecError(f"role {role.name} has an invalid setting")

    if spec.database_owner not in role_map or role_map[spec.database_owner].login:
        raise ProvisioningSpecError("database owner must be one declared NOLOGIN role")
    if spec.schema_owner != spec.database_owner:
        raise ProvisioningSpecError("database and initial schema owners must be identical")
    if spec.readiness_role_name not in role_map:
        raise ProvisioningSpecError("readiness role must be declared")
    lock_owner = role_map.get(lock.owner_role)
    if lock_owner is None or (
        lock_owner.login,
        lock_owner.inherit,
        lock_owner.bypass_rls,
        lock_owner.connection_limit,
    ) != (False, False, False, -1):
        raise ProvisioningSpecError(
            "migration-lock owner must be closed NOLOGIN/NOINHERIT/NOBYPASSRLS"
        )
    if lock.execute_role not in role_map or not role_map[lock.execute_role].login:
        raise ProvisioningSpecError("migration-lock caller must be a declared LOGIN")

    tenant_lock = spec.tenant_write_lock
    sealer = spec.tenant_initial_owner_sealer
    if spec == TENANT_PROVISIONING_SPEC:
        if tenant_lock != _TENANT_WRITE_LOCK:
            raise ProvisioningSpecError("tenant write-lock boundary is not exact")
        if sealer != _TENANT_INITIAL_OWNER_SEALER:
            raise ProvisioningSpecError("tenant initial owner sealer is not exact")
    elif tenant_lock is not None or sealer is not None:
        raise ProvisioningSpecError(
            "the security-audit service must not carry tenant capsules"
        )

    if tenant_lock is not None:
        _validate_identifier(tenant_lock.schema_name, "tenant-lock schema name")
        _validate_identifier(tenant_lock.function_name, "tenant-lock function name")
        _validate_identifier(tenant_lock.owner_role, "tenant-lock owner role")
        if (
            tenant_lock.schema_name,
            tenant_lock.function_name,
            tenant_lock.owner_role,
        ) != (spec.schema_name, "take_tenant_write_lock", "ofarm_tenant_lock_owner"):
            raise ProvisioningSpecError("tenant-lock identity is not exact")
        tenant_lock_owner = role_map.get(tenant_lock.owner_role)
        if tenant_lock_owner is None or (
            tenant_lock_owner.login,
            tenant_lock_owner.inherit,
            tenant_lock_owner.bypass_rls,
            tenant_lock_owner.connection_limit,
        ) != (False, False, False, -1):
            raise ProvisioningSpecError(
                "tenant-lock owner must be closed NOLOGIN/NOINHERIT/NOBYPASSRLS"
            )

    if sealer is not None:
        _validate_identifier(sealer.schema_name, "owner-sealer schema name")
        _validate_identifier(sealer.function_name, "owner-sealer function name")
        _validate_identifier(sealer.execute_role, "owner-sealer execute role")
        _validate_identifier(sealer.target_schema_name, "owner-sealer target schema")
        if (
            sealer.schema_name,
            sealer.function_name,
            sealer.execute_role,
            sealer.target_schema_name,
        ) != (
            lock.schema_name,
            "seal_tenant_routine_owners",
            "ofarm_migrator",
            spec.schema_name,
        ):
            raise ProvisioningSpecError("tenant initial owner sealer identity differs")
        sealed_signatures = {
            (transfer.function_name, transfer.argument_types)
            for transfer in sealer.transfers
        }
        if not set(
            (routine.name, routine.argument_types)
            for routine in TENANT_CONTEXT_ROUTINE_SIGNATURES
        ).issubset(sealed_signatures):
            raise ProvisioningSpecError(
                "tenant owner sealer omits a context contract signature"
            )
        transfer_identities: set[tuple[str, str, tuple[str, ...]]] = set()
        for transfer in sealer.transfers:
            _validate_identifier(transfer.schema_name, "sealed routine schema")
            _validate_identifier(transfer.function_name, "sealed routine name")
            _validate_identifier(transfer.owner_role, "sealed routine owner")
            identity = (
                transfer.schema_name,
                transfer.function_name,
                transfer.argument_types,
            )
            if identity in transfer_identities:
                raise ProvisioningSpecError("tenant sealer repeats a routine identity")
            transfer_identities.add(identity)
            if transfer.schema_name != spec.schema_name:
                raise ProvisioningSpecError("tenant sealer target schema differs")
            if transfer.owner_role not in {
                "ofarm_backend_observer",
                "ofarm_binder",
                "ofarm_graph_validator",
                "ofarm_tenant_lock_owner",
            }:
                raise ProvisioningSpecError("tenant sealer target owner differs")
            if any(
                value
                not in {
                    "text",
                    "uuid",
                    "bigint",
                    "bytea",
                    "integer",
                    "timestamp with time zone",
                }
                for value in transfer.argument_types
            ):
                raise ProvisioningSpecError("tenant sealer argument type differs")

    expected_memberships: set[tuple[str, str]] = set()
    external_role_map = {
        role.name: role for role in spec.external_membership_roles
    }
    for membership in spec.memberships:
        edge = (membership.granted_role, membership.member_role)
        if edge in expected_memberships:
            raise ProvisioningSpecError("role membership edges must be unique")
        expected_memberships.add(edge)
        if (
            membership.granted_role not in role_map
            and membership.granted_role not in external_role_map
        ):
            raise ProvisioningSpecError("membership grants an unknown role")
        if membership.member_role not in role_map:
            raise ProvisioningSpecError("membership names an unknown member")
        if membership.granted_role == membership.member_role:
            raise ProvisioningSpecError("self membership is forbidden")
        if membership.admin:
            raise ProvisioningSpecError("no governed membership may carry ADMIN")
        if lock.owner_role in edge:
            raise ProvisioningSpecError(
                "migration-lock owner must have no membership edge"
            )
        if tenant_lock is not None and tenant_lock.owner_role in edge:
            raise ProvisioningSpecError("tenant-lock owner must have no membership edge")

    if "ofarm_binder" in role_map:
        binder = role_map["ofarm_binder"]
        if (binder.login, binder.inherit, binder.bypass_rls) != (False, False, True):
            raise ProvisioningSpecError("ofarm_binder attributes are not exact")
        if any("ofarm_binder" in edge for edge in expected_memberships):
            raise ProvisioningSpecError("ofarm_binder must have no membership edge")

    if spec.migration_service == TENANT_SERVICE:
        observer = role_map.get("ofarm_backend_observer")
        if observer is None or (
            observer.login,
            observer.inherit,
            observer.bypass_rls,
            observer.connection_limit,
        ) != (False, True, False, -1):
            raise ProvisioningSpecError(
                "backend observer attributes are not exact"
            )
        graph_validator = role_map.get("ofarm_graph_validator")
        if graph_validator is None or (
            graph_validator.login,
            graph_validator.inherit,
            graph_validator.bypass_rls,
            graph_validator.connection_limit,
        ) != (False, False, False, -1):
            raise ProvisioningSpecError(
                "graph validator attributes are not exact"
            )
        observer_memberships = {
            (
                membership.granted_role,
                membership.member_role,
                membership.inherit,
                membership.set_role,
                membership.admin,
            )
            for membership in spec.memberships
            if membership.member_role == "ofarm_backend_observer"
        }
        if observer_memberships != {
            (
                "pg_read_all_stats",
                "ofarm_backend_observer",
                True,
                False,
                False,
            )
        }:
            raise ProvisioningSpecError(
                "backend observer statistics membership is not exact"
            )
        if any(
            "ofarm_graph_validator" in edge for edge in expected_memberships
        ):
            raise ProvisioningSpecError(
                "graph validator must have no membership edge"
            )

    for name in spec.database_connect_roles + spec.schema_usage_roles:
        if name not in role_map:
            raise ProvisioningSpecError("database/schema grant names an unknown role")
    if len(spec.database_connect_roles) != len(set(spec.database_connect_roles)):
        raise ProvisioningSpecError("database CONNECT grants must be unique")
    if len(spec.schema_usage_roles) != len(set(spec.schema_usage_roles)):
        raise ProvisioningSpecError("schema USAGE grants must be unique")

    producer_logins: set[str] = set()
    for producer in spec.audit_producers:
        if producer.login_role in producer_logins:
            raise ProvisioningSpecError("audit producer LOGIN mappings must be unique")
        producer_logins.add(producer.login_role)
        role = role_map.get(producer.login_role)
        if role is None or not role.login:
            raise ProvisioningSpecError("audit producer must name a declared LOGIN role")
        if not producer.producer or not producer.component:
            raise ProvisioningSpecError("audit producer mapping must be closed")

    for absent_role in spec.intentionally_absent_login_roles:
        _validate_identifier(absent_role, "intentionally absent role")
        if absent_role in role_map:
            raise ProvisioningSpecError("an intentionally absent role is provisioned")

    routine_identities: set[tuple[str, tuple[str, ...]]] = set()
    for routine in spec.public_execute_revoked_routines:
        identity = (routine.name, routine.argument_types)
        if identity in routine_identities:
            raise ProvisioningSpecError("revoked routine identities must be unique")
        routine_identities.add(identity)
        if not routine.name.startswith(("pg_advisory_", "pg_try_advisory_")):
            raise ProvisioningSpecError("only raw advisory routines belong here")
        if any(
            argument_type not in {"bigint", "integer"}
            for argument_type in routine.argument_types
        ):
            raise ProvisioningSpecError("revoked routine type is not closed")
        if len(routine.argument_types) not in {0, 1, 2}:
            raise ProvisioningSpecError("revoked routine arity is not closed")

    large_object_identities: set[tuple[str, tuple[str, ...]]] = set()
    allowed_large_object_types = {
        "bigint",
        "bytea",
        "integer",
        "oid",
        "text",
        "void",
    }
    for routine in spec.large_object_routines:
        identity = (routine.name, routine.argument_types)
        if identity in large_object_identities:
            raise ProvisioningSpecError(
                "large-object routine identities must be unique"
            )
        large_object_identities.add(identity)
        if not (
            routine.name.startswith("lo_")
            or routine.name in {"loread", "lowrite"}
        ):
            raise ProvisioningSpecError(
                "only built-in large-object routines belong here"
            )
        if any(
            argument_type not in allowed_large_object_types
            for argument_type in routine.argument_types
        ) or routine.return_type not in allowed_large_object_types:
            raise ProvisioningSpecError(
                "large-object routine type is not closed"
            )
        if not (
            re.fullmatch(r"be_lo_[a-z0-9_]+", routine.internal_symbol)
            or routine.internal_symbol in {"be_loread", "be_lowrite"}
        ):
            raise ProvisioningSpecError(
                "large-object internal symbol is not closed"
            )
    if len(spec.large_object_routines) != 20:
        raise ProvisioningSpecError(
            "PostgreSQL 17 large-object routine inventory differs"
        )

    if spec.backend_statistics_routines != _BACKEND_STATISTICS_ROUTINES:
        raise ProvisioningSpecError(
            "PostgreSQL 17 backend-statistics routine inventory differs"
        )
    if (
        spec.activity_view.columns != _PG_STAT_ACTIVITY_VIEW_COLUMNS
        or spec.activity_view.definition != _PG_STAT_ACTIVITY_VIEW_DEFINITION
    ):
        raise ProvisioningSpecError(
            "PostgreSQL 17 pg_stat_activity view identity differs"
        )
    if len(spec.activity_view.select_roles) != len(
        set(spec.activity_view.select_roles)
    ) or any(
        role_name not in role_map
        for role_name in spec.activity_view.select_roles
    ):
        raise ProvisioningSpecError(
            "pg_stat_activity SELECT roles are not closed"
        )
    expected_activity_roles = (
        ("ofarm_backend_observer",)
        if spec.migration_service == TENANT_SERVICE
        else ()
    )
    if spec.activity_view.select_roles != expected_activity_roles:
        raise ProvisioningSpecError(
            "pg_stat_activity SELECT/EXECUTE grants differ"
        )


for _SPEC in (TENANT_PROVISIONING_SPEC, SECURITY_AUDIT_PROVISIONING_SPEC):
    _validate_spec(_SPEC)

if set(TENANT_PROVISIONING_SPEC.role_names) & set(
    SECURITY_AUDIT_PROVISIONING_SPEC.role_names
) != {"ofarm_migrator"}:
    raise ProvisioningSpecError(
        "the independent services may share only the migrator role name"
    )
