"""Closed PostgreSQL service provisioning specifications for issue #174.

The specifications in this module contain no credentials.  Importing them is
free of native-authority file I/O, so the independent security-audit lane does
not depend on tenant release artifacts.  Each tenant manifest or digest loads
and fully validates the current checked native-verifier identity and evidence
receipt before embedding their complete canonical content.  The
specifications otherwise freeze the database, namespace, role, membership,
and database-scoped setting posture that the one-time infrastructure
provisioner must create or verify.  Runtime processes and migration runners
consume observations of this posture; they never reconcile it.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    MigrationService,
)
from deployment.postgresql.native_release_identity import (
    EVIDENCE_RECEIPT_PATH,
    IDENTITY_PATH,
    PACKAGE_ROOT,
    SOURCE_DIRECTORY,
    NativeEvidenceReceipt,
    NativeReleaseIdentity,
    NativeReleaseIdentityError,
    load_native_evidence_receipt,
    load_native_release_identity,
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
ACCESS_CLOCK_LOCK_KEY_POLICY = "OFARM_SECURITY_AUDIT_ACCESS_CLOCK_LOCK_V1"
_ACCESS_CLOCK_LOCK_KEY = (-274079271, -1019032096)
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
    superuser: bool = False

    def manifest(self) -> dict[str, object]:
        return {
            "name": self.name,
            "login": self.login,
            "superuser": self.superuser,
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
class NativeVerifierSpec:
    """One pre-ledger, provisioning-owned verification-only extension."""

    schema_name: str
    installer_role: str
    extension_name: str
    extension_version: str
    module_pathname: str
    function_name: str

    def require_frozen_release_authority(self) -> None:
        """Refuse until hosted evidence and durable preservation are frozen."""

        identity, receipt = _load_current_native_verifier_authority()
        preservation = receipt.document["preservation"]
        if (
            identity.status != "frozen"
            or identity.index_digest is None
            or receipt.status != "frozen"
            or not isinstance(preservation, dict)
            or preservation.get("status") != "verified"
        ):
            raise ProvisioningSpecError(
                "tenant native verifier release authority is not frozen"
            )

    def manifest(self) -> dict[str, object]:
        identity, receipt = _load_current_native_verifier_authority()
        source_input = identity.document["sourceInput"]
        receipt_authority = receipt.document["evidenceAuthorityInput"]
        return {
            "schema": self.schema_name,
            "schemaOwner": self.installer_role,
            "extension": self.extension_name,
            "version": self.extension_version,
            "modulePathname": self.module_pathname,
            "installerRole": self.installer_role,
            "installerSuperuser": True,
            "installerLogin": False,
            "trusted": False,
            "relocatable": False,
            "requires": [],
            "checkedReleaseAuthority": {
                "releaseIdentity": {
                    "canonicalDigest": identity.digest,
                    "status": identity.status,
                    "sourceInputDigest": source_input["digest"],
                    "indexDigest": identity.index_digest,
                    "document": identity.manifest(),
                },
                "evidenceReceipt": {
                    "canonicalDigest": receipt.digest,
                    "status": receipt.status,
                    "evidenceAuthorityInputDigest": receipt_authority["digest"],
                    "document": receipt.manifest(),
                },
            },
            "sqlCallableSurface": [
                {
                    "name": self.function_name,
                    "argumentTypes": ["bytea", "bytea", "bytea"],
                    "returnType": "boolean",
                    "security": "INVOKER",
                    "strict": True,
                    "volatility": "IMMUTABLE",
                    "parallelSafety": "UNSAFE",
                    "leakproof": False,
                }
            ],
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
    """One built-in whose PUBLIC access is revoked exactly."""

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
class AccessClockLockSpec:
    """Exact provisioning-owned, no-caller-key audit clock mutex wrappers."""

    schema_name: str
    owner_role: str
    take_function_name: str
    release_function_name: str
    execute_role: str
    key_class_id: int
    key_object_id: int

    @property
    def take_qualified_function(self) -> str:
        return f"{self.schema_name}.{self.take_function_name}"

    @property
    def release_qualified_function(self) -> str:
        return f"{self.schema_name}.{self.release_function_name}"

    @property
    def take_source(self) -> str:
        return (
            "SELECT pg_catalog.pg_advisory_lock("
            f"{self.key_class_id}, {self.key_object_id})"
        )

    @property
    def release_source(self) -> str:
        return (
            "SELECT pg_catalog.pg_advisory_unlock("
            f"{self.key_class_id}, {self.key_object_id})"
        )

    def manifest(self) -> dict[str, object]:
        function_common: dict[str, object] = {
            "argumentTypes": [],
            "owner": self.owner_role,
            "language": "sql",
            "securityDefiner": True,
            "strict": False,
            "leakproof": False,
            "volatility": "VOLATILE",
            "parallelSafety": "UNSAFE",
            "searchPath": ["pg_catalog", "pg_temp"],
            "executeRoles": [self.execute_role],
        }
        return {
            "schema": self.schema_name,
            "owner": self.owner_role,
            "functions": [
                {
                    **function_common,
                    "qualifiedName": self.take_qualified_function,
                    "returnType": "pg_catalog.void",
                    "source": self.take_source,
                },
                {
                    **function_common,
                    "qualifiedName": self.release_qualified_function,
                    "returnType": "pg_catalog.bool",
                    "source": self.release_source,
                },
            ],
            "lockKey": {
                "policy": ACCESS_CLOCK_LOCK_KEY_POLICY,
                "namespace": "pg_advisory_lock(integer,integer)",
                "classId": self.key_class_id,
                "objectId": self.key_object_id,
                "callerSelectable": False,
                "transactionScoped": False,
                "functionScopedByProtocol": True,
            },
            "rawRoutineOwnerGrants": [
                {
                    "schema": "pg_catalog",
                    "name": "pg_advisory_lock",
                    "argumentTypes": ["integer", "integer"],
                    "grantee": self.owner_role,
                },
                {
                    "schema": "pg_catalog",
                    "name": "pg_advisory_unlock",
                    "argumentTypes": ["integer", "integer"],
                    "grantee": self.owner_role,
                },
            ],
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
class TenantAdmissionLockSpec:
    """Closed owners for the fixed shared/exclusive admission lock pair."""

    shared_owner_role: str
    exclusive_owner_role: str
    key_class_id: int
    key_object_id: int

    def manifest(self) -> dict[str, object]:
        return {
            "key": [self.key_class_id, self.key_object_id],
            "callerSelectableKey": False,
            "transactionScoped": True,
            "sharedRoutineOwnerGrant": {
                "schema": "pg_catalog",
                "name": "pg_advisory_xact_lock_shared",
                "argumentTypes": ["integer", "integer"],
                "grantee": self.shared_owner_role,
            },
            "exclusiveRoutineOwnerGrant": {
                "schema": "pg_catalog",
                "name": "pg_advisory_xact_lock",
                "argumentTypes": ["integer", "integer"],
                "grantee": self.exclusive_owner_role,
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
class TenantBindingSelectionControlAdmissionSealerSpec:
    """One-use V5 capsule for the selection-control binder admission."""

    schema_name: str
    function_name: str
    execute_role: str
    ledger_schema_name: str
    ledger_name: str
    target_schema_name: str
    controller_role: str

    @property
    def qualified_function(self) -> str:
        return f"{self.schema_name}.{self.function_name}"

    @property
    def source(self) -> str:
        return " ".join(
            (
                "BEGIN",
                "IF (SELECT pg_catalog.count(*) = 5 "
                "AND pg_catalog.max(version) = 5 "
                "AND pg_catalog.max(filename) FILTER (WHERE version = 5) = "
                "'0005_tenant_binding_selection_control_admission.sql' "
                "AND pg_catalog.max(service_identity) "
                "FILTER (WHERE version = 5) = "
                "'ofarm.tenant-postgresql.v1' "
                f"FROM {self.ledger_schema_name}.{self.ledger_name}) "
                "IS DISTINCT FROM TRUE THEN",
                "RAISE EXCEPTION USING ERRCODE = '55000', "
                "MESSAGE = 'tenant binding selection-control admission "
                "ordering marker differs';",
                "END IF;",
                "GRANT EXECUTE ON FUNCTION "
                f"{self.target_schema_name}.create_tenant_challenge() "
                f"TO {self.controller_role};",
                "GRANT EXECUTE ON FUNCTION "
                f"{self.target_schema_name}.bind_tenant_capability(text) "
                f"TO {self.controller_role};",
                f"GRANT CREATE ON SCHEMA {self.schema_name} "
                f"TO {self.execute_role};",
                f"ALTER FUNCTION {self.qualified_function}() SECURITY INVOKER;",
                f"ALTER FUNCTION {self.qualified_function}() OWNER TO "
                f"{self.execute_role};",
                f"REVOKE CREATE ON SCHEMA {self.schema_name} "
                f"FROM {self.execute_role};",
                "END",
            )
        )

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
            "orderingMarker": {
                "ledger": f"{self.ledger_schema_name}.{self.ledger_name}",
                "rowCount": 5,
                "headVersion": 5,
                "headFilename": (
                    "0005_tenant_binding_selection_control_admission.sql"
                ),
                "headServiceIdentity": "ofarm.tenant-postgresql.v1",
            },
            "grants": [
                {
                    "schema": self.target_schema_name,
                    "name": "create_tenant_challenge",
                    "argumentTypes": [],
                    "grantee": self.controller_role,
                },
                {
                    "schema": self.target_schema_name,
                    "name": "bind_tenant_capability",
                    "argumentTypes": ["text"],
                    "grantee": self.controller_role,
                },
            ],
            "consumedAfterMigrationVersion": 5,
            "postConsumption": {
                "securityInvoker": True,
                "owner": self.execute_role,
                "droppedBeforeCommit": True,
                "transientSchemaCreatePrivilegesAbsent": True,
            },
        }


@dataclass(frozen=True, slots=True)
class TenantCurrentContextSelectionOwnerAdmissionSealerSpec:
    """One-use V6 capsule for the current-context owner admission."""

    schema_name: str
    function_name: str
    execute_role: str
    ledger_schema_name: str
    ledger_name: str
    target_schema_name: str
    owner_role: str

    @property
    def qualified_function(self) -> str:
        return f"{self.schema_name}.{self.function_name}"

    @property
    def source(self) -> str:
        return " ".join(
            (
                "BEGIN",
                "IF (SELECT pg_catalog.count(*) = 6 "
                "AND pg_catalog.max(version) = 6 "
                "AND pg_catalog.max(filename) FILTER (WHERE version = 6) = "
                "'0006_tenant_current_context_selection_owner_admission.sql' "
                "AND pg_catalog.max(service_identity) "
                "FILTER (WHERE version = 6) = "
                "'ofarm.tenant-postgresql.v1' "
                f"FROM {self.ledger_schema_name}.{self.ledger_name}) "
                "IS DISTINCT FROM TRUE THEN",
                "RAISE EXCEPTION USING ERRCODE = '55000', "
                "MESSAGE = 'tenant current-context selection-owner admission "
                "ordering marker differs';",
                "END IF;",
                "GRANT EXECUTE ON FUNCTION "
                f"{self.target_schema_name}.current_tenant_id() "
                f"TO {self.owner_role};",
                "GRANT EXECUTE ON FUNCTION "
                f"{self.target_schema_name}.current_authenticated_principal_ref() "
                f"TO {self.owner_role};",
                f"GRANT CREATE ON SCHEMA {self.schema_name} "
                f"TO {self.execute_role};",
                f"ALTER FUNCTION {self.qualified_function}() SECURITY INVOKER;",
                f"ALTER FUNCTION {self.qualified_function}() OWNER TO "
                f"{self.execute_role};",
                f"REVOKE CREATE ON SCHEMA {self.schema_name} "
                f"FROM {self.execute_role};",
                "END",
            )
        )

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
            "orderingMarker": {
                "ledger": f"{self.ledger_schema_name}.{self.ledger_name}",
                "rowCount": 6,
                "headVersion": 6,
                "headFilename": (
                    "0006_tenant_current_context_selection_owner_admission.sql"
                ),
                "headServiceIdentity": "ofarm.tenant-postgresql.v1",
            },
            "grants": [
                {
                    "schema": self.target_schema_name,
                    "name": "current_tenant_id",
                    "argumentTypes": [],
                    "grantee": self.owner_role,
                },
                {
                    "schema": self.target_schema_name,
                    "name": "current_authenticated_principal_ref",
                    "argumentTypes": [],
                    "grantee": self.owner_role,
                },
            ],
            "consumedAfterMigrationVersion": 6,
            "postConsumption": {
                "securityInvoker": True,
                "owner": self.execute_role,
                "droppedBeforeCommit": True,
                "transientSchemaCreatePrivilegesAbsent": True,
            },
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
    access_clock_lock: AccessClockLockSpec | None
    tenant_write_lock: TenantWriteLockSpec | None
    tenant_admission_lock: TenantAdmissionLockSpec | None
    tenant_initial_owner_sealer: TenantInitialOwnerSealerSpec | None
    tenant_binding_selection_control_admission_sealer: (
        TenantBindingSelectionControlAdmissionSealerSpec | None
    )
    tenant_current_context_selection_owner_admission_sealer: (
        TenantCurrentContextSelectionOwnerAdmissionSealerSpec | None
    )
    native_verifier: NativeVerifierSpec | None
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
        if self.access_clock_lock is not None:
            owners.append(self.access_clock_lock.owner_role)
        if self.tenant_write_lock is not None:
            owners.append(self.tenant_write_lock.owner_role)
        if self.tenant_admission_lock is not None:
            owners.extend(
                (
                    self.tenant_admission_lock.shared_owner_role,
                    self.tenant_admission_lock.exclusive_owner_role,
                )
            )
        if self.tenant_initial_owner_sealer is not None:
            owners.extend(
                transfer.owner_role
                for transfer in self.tenant_initial_owner_sealer.transfers
            )
        if self.native_verifier is not None:
            owners.append(self.native_verifier.installer_role)
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
                **(
                    {
                        "tenantBindingSelectionControlAdmissionSealer": (
                            self.tenant_binding_selection_control_admission_sealer.manifest()
                        )
                    }
                    if self.tenant_binding_selection_control_admission_sealer
                    is not None
                    else {}
                ),
                **(
                    {
                        "tenantCurrentContextSelectionOwnerAdmissionSealer": (
                            self.tenant_current_context_selection_owner_admission_sealer.manifest()
                        )
                    }
                    if self.tenant_current_context_selection_owner_admission_sealer
                    is not None
                    else {}
                ),
                **(
                    {"nativeVerifier": self.native_verifier.manifest()}
                    if self.native_verifier is not None
                    else {}
                ),
            },
            **(
                {"accessClockLock": self.access_clock_lock.manifest()}
                if self.access_clock_lock is not None
                else {}
            ),
            "tenantWriteLock": (
                None
                if self.tenant_write_lock is None
                else self.tenant_write_lock.manifest()
            ),
            **(
                {
                    "tenantAdmissionLock": self.tenant_admission_lock.manifest()
                }
                if self.tenant_admission_lock is not None
                else {}
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
        source = _SPEC_DIGEST_DOMAIN + _canonical_json(value)
        value["provisioningSpecDigest"] = (
            "sha256:" + hashlib.sha256(source).hexdigest()
        )
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

_TENANT_ADMISSION_LOCK = TenantAdmissionLockSpec(
    shared_owner_role="ofarm_binder",
    exclusive_owner_role="ofarm_admission_lock_owner",
    key_class_id=1330004306,
    key_object_id=1413694001,
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
        RoutineOwnerTransfer(
            "ofarm",
            "bind_tenant_capability",
            ("text",),
            "ofarm_binder",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "valid_tenant_capability_time_window",
            ("bigint", "bigint", "bigint", "bigint", "bigint"),
            "ofarm_binder",
        ),
        RoutineOwnerTransfer(
            "ofarm", "current_tenant_context", (), "ofarm_binder"
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "current_authenticated_principal_ref",
            (),
            "ofarm_binder",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "verify_tenant_capability_preflight",
            ("bytea", "bytea"),
            "ofarm_binder",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "fold_principal_binding_authority",
            ("text", "text", "text"),
            "ofarm_admission_lock_owner",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "fold_tenant_capability_key_lifecycle",
            ("text",),
            "ofarm_admission_lock_owner",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "transition_principal_binding",
            (
                "text", "text", "text", "uuid", "text", "uuid", "text",
                "text", "uuid", "text", "uuid", "text", "uuid", "text",
                "text", "text", "text", "text", "text", "text",
                "timestamp with time zone", "timestamp with time zone",
                "uuid", "timestamp with time zone",
                "timestamp with time zone", "text", "text",
            ),
            "ofarm_admission_lock_owner",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "rebuild_principal_binding_current",
            (),
            "ofarm_admission_lock_owner",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "register_tenant_capability_key",
            ("bytea", "text", "text"),
            "ofarm_admission_lock_owner",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "verify_tenant_capability_candidate_preflight",
            ("text", "bytea"),
            "ofarm_admission_lock_owner",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "activate_tenant_capability_key",
            ("text", "uuid", "text", "text", "text", "text", "text"),
            "ofarm_admission_lock_owner",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "rotate_tenant_capability_key",
            (
                "text", "text", "uuid", "text", "text", "text", "text",
                "text",
            ),
            "ofarm_admission_lock_owner",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "close_tenant_capability_admission",
            ("uuid", "text", "text", "text", "text", "text"),
            "ofarm_admission_lock_owner",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "revoke_tenant_capability_key",
            (
                "text", "uuid", "text", "uuid", "uuid", "text", "text",
                "text",
            ),
            "ofarm_admission_lock_owner",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "resume_tenant_capability_admission",
            (
                "uuid", "text", "uuid", "uuid", "text", "text", "text",
            ),
            "ofarm_admission_lock_owner",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "rebuild_tenant_capability_keyring",
            (),
            "ofarm_admission_lock_owner",
        ),
        RoutineOwnerTransfer(
            "ofarm",
            "observe_tenant_capability_key",
            ("text",),
            "ofarm_admission_lock_owner",
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
            "ofarm",
            "publish_materialization_generation",
            (
                "text",
                "text",
                "jsonb",
                "text",
                "jsonb",
                "text",
                "text",
                "text",
                "jsonb",
                "text",
            ),
            "ofarm_graph_validator",
        ),
        RoutineOwnerTransfer(
            "ofarm", "take_tenant_write_lock", (), "ofarm_tenant_lock_owner"
        ),
    ),
)


_TENANT_BINDING_SELECTION_CONTROL_ADMISSION_SEALER = (
    TenantBindingSelectionControlAdmissionSealerSpec(
        schema_name="ofarm_infrastructure",
        function_name="seal_tenant_binding_selection_control_admission",
        execute_role="ofarm_migrator",
        ledger_schema_name="ofarm",
        ledger_name="schema_migration",
        target_schema_name="ofarm",
        controller_role="ofarm_command_runtime_bundle_selection_controller",
    )
)


_TENANT_CURRENT_CONTEXT_SELECTION_OWNER_ADMISSION_SEALER = (
    TenantCurrentContextSelectionOwnerAdmissionSealerSpec(
        schema_name="ofarm_infrastructure",
        function_name="seal_tenant_current_context_selection_owner_admission",
        execute_role="ofarm_migrator",
        ledger_schema_name="ofarm",
        ledger_name="schema_migration",
        target_schema_name="ofarm",
        owner_role="ofarm_owner",
    )
)


_TENANT_NATIVE_VERIFIER = NativeVerifierSpec(
    schema_name="ofarm_crypto",
    installer_role="ofarm_crypto_installer",
    extension_name="ofarm_ed25519",
    extension_version="1.0",
    module_pathname="$libdir/ofarm_ed25519",
    function_name="ed25519_verify",
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
    access_clock_lock=None,
    tenant_write_lock=_TENANT_WRITE_LOCK,
    tenant_admission_lock=_TENANT_ADMISSION_LOCK,
    tenant_initial_owner_sealer=_TENANT_INITIAL_OWNER_SEALER,
    tenant_binding_selection_control_admission_sealer=(
        _TENANT_BINDING_SELECTION_CONTROL_ADMISSION_SEALER
    ),
    tenant_current_context_selection_owner_admission_sealer=(
        _TENANT_CURRENT_CONTEXT_SELECTION_OWNER_ADMISSION_SEALER
    ),
    native_verifier=_TENANT_NATIVE_VERIFIER,
    roles=(
        RoleSpec("ofarm_owner", False, False, False, -1),
        RoleSpec(
            "ofarm_tenant_migration_lock_owner", False, False, False, -1
        ),
        RoleSpec("ofarm_tenant_lock_owner", False, False, False, -1),
        RoleSpec("ofarm_admission_lock_owner", False, False, False, -1),
        RoleSpec(
            "ofarm_crypto_installer",
            False,
            False,
            False,
            -1,
            superuser=True,
        ),
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
            "ofarm_runtime_bundle_publisher", False, False, False, -1
        ),
        RoleSpec(
            "ofarm_runtime_bundle_control_login",
            True,
            True,
            False,
            1,
            True,
            _CONTROL_SETTINGS,
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
        RoleSpec(
            "ofarm_capability_key_controller", False, False, False, -1
        ),
        RoleSpec(
            "ofarm_capability_key_control_login",
            True,
            True,
            False,
            1,
            True,
            _CONTROL_SETTINGS,
        ),
        RoleSpec("ofarm_backend_observer", False, True, False, -1),
        RoleSpec("ofarm_graph_validator", False, False, False, -1),
        RoleSpec(
            "ofarm_command_runtime_bundle_selection_controller",
            False,
            False,
            False,
            -1,
        ),
        RoleSpec(
            "ofarm_command_runtime_bundle_selection_control_login",
            True,
            True,
            False,
            1,
            True,
            _CONTROL_SETTINGS,
        ),
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
            "ofarm_runtime_bundle_publisher",
            "ofarm_runtime_bundle_control_login",
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
            "ofarm_capability_key_controller",
            "ofarm_capability_key_control_login",
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
        MembershipSpec(
            "ofarm_command_runtime_bundle_selection_controller",
            "ofarm_command_runtime_bundle_selection_control_login",
            True,
            False,
            False,
        ),
    ),
    database_connect_roles=(
        "ofarm_migrator",
        "ofarm_app",
        "ofarm_worker",
        "ofarm_runtime_bundle_publisher",
        "ofarm_readiness",
        "ofarm_tenant_registrar",
        "ofarm_identity_writer",
        "ofarm_capability_key_controller",
        "ofarm_command_runtime_bundle_selection_control_login",
    ),
    schema_usage_roles=(
        "ofarm_app",
        "ofarm_worker",
        "ofarm_runtime_bundle_publisher",
        "ofarm_readiness",
        "ofarm_tenant_registrar",
        "ofarm_identity_writer",
        "ofarm_binder",
        "ofarm_admission_lock_owner",
        "ofarm_capability_key_controller",
        "ofarm_graph_validator",
        "ofarm_tenant_lock_owner",
        "ofarm_command_runtime_bundle_selection_controller",
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
    access_clock_lock=AccessClockLockSpec(
        schema_name="ofarm_infrastructure",
        owner_role="ofarm_security_audit_access_clock_lock_owner",
        take_function_name="take_audit_access_clock_lock",
        release_function_name="release_audit_access_clock_lock",
        execute_role="ofarm_security_audit_owner",
        key_class_id=_ACCESS_CLOCK_LOCK_KEY[0],
        key_object_id=_ACCESS_CLOCK_LOCK_KEY[1],
    ),
    tenant_write_lock=None,
    tenant_admission_lock=None,
    tenant_initial_owner_sealer=None,
    tenant_binding_selection_control_admission_sealer=None,
    tenant_current_context_selection_owner_admission_sealer=None,
    native_verifier=None,
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
            "ofarm_security_audit_access_clock_lock_owner",
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


def require_frozen_tenant_native_verifier_authority() -> None:
    """Final release gate; intentionally not enabled during hosted bootstrap."""

    verifier = TENANT_PROVISIONING_SPEC.native_verifier
    if verifier is None:
        raise ProvisioningSpecError("tenant native verifier is absent")
    verifier.require_frozen_release_authority()


def _load_current_native_verifier_authority(
    *,
    identity_path: Path = IDENTITY_PATH,
    evidence_receipt_path: Path = EVIDENCE_RECEIPT_PATH,
    source_directory: Path = SOURCE_DIRECTORY,
    repository_root: Path = PACKAGE_ROOT,
) -> tuple[NativeReleaseIdentity, NativeEvidenceReceipt]:
    """Load both checked documents through their complete current schemas."""

    try:
        identity = load_native_release_identity(
            identity_path,
            verify_current_sources=True,
            source_directory=source_directory,
        )
        receipt = load_native_evidence_receipt(
            evidence_receipt_path,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=repository_root,
        )
    except (NativeReleaseIdentityError, OSError) as exc:
        raise ProvisioningSpecError(
            "checked tenant native-verifier authority is invalid or stale"
        ) from exc
    return identity, receipt


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
        if role.superuser != (role.name == "ofarm_crypto_installer"):
            raise ProvisioningSpecError(
                "only the exact crypto installer may be a governed superuser"
            )
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

    access_clock_lock = spec.access_clock_lock
    if spec.migration_service == SECURITY_AUDIT_SERVICE:
        if access_clock_lock is None:
            raise ProvisioningSpecError("security-audit access-clock lock is absent")
        for value, label in (
            (access_clock_lock.schema_name, "access-clock lock schema"),
            (access_clock_lock.owner_role, "access-clock lock owner"),
            (access_clock_lock.take_function_name, "access-clock take function"),
            (
                access_clock_lock.release_function_name,
                "access-clock release function",
            ),
            (access_clock_lock.execute_role, "access-clock lock caller"),
        ):
            _validate_identifier(value, label)
        if (
            access_clock_lock.schema_name,
            access_clock_lock.owner_role,
            access_clock_lock.take_function_name,
            access_clock_lock.release_function_name,
            access_clock_lock.execute_role,
            access_clock_lock.key_class_id,
            access_clock_lock.key_object_id,
        ) != (
            lock.schema_name,
            "ofarm_security_audit_access_clock_lock_owner",
            "take_audit_access_clock_lock",
            "release_audit_access_clock_lock",
            spec.schema_owner,
            *_ACCESS_CLOCK_LOCK_KEY,
        ):
            raise ProvisioningSpecError("access-clock lock boundary is not exact")
        access_clock_owner = role_map.get(access_clock_lock.owner_role)
        if access_clock_owner is None or (
            access_clock_owner.login,
            access_clock_owner.inherit,
            access_clock_owner.bypass_rls,
            access_clock_owner.connection_limit,
        ) != (False, False, False, -1):
            raise ProvisioningSpecError(
                "access-clock lock owner must be closed "
                "NOLOGIN/NOINHERIT/NOBYPASSRLS"
            )
    elif access_clock_lock is not None:
        raise ProvisioningSpecError(
            "tenant service must not carry the audit access-clock lock"
        )

    tenant_lock = spec.tenant_write_lock
    admission_lock = spec.tenant_admission_lock
    sealer = spec.tenant_initial_owner_sealer
    selection_admission_sealer = (
        spec.tenant_binding_selection_control_admission_sealer
    )
    context_owner_admission_sealer = (
        spec.tenant_current_context_selection_owner_admission_sealer
    )
    native_verifier = spec.native_verifier
    if spec == TENANT_PROVISIONING_SPEC:
        if tenant_lock != _TENANT_WRITE_LOCK:
            raise ProvisioningSpecError("tenant write-lock boundary is not exact")
        if admission_lock != _TENANT_ADMISSION_LOCK:
            raise ProvisioningSpecError("tenant admission-lock boundary is not exact")
        if sealer != _TENANT_INITIAL_OWNER_SEALER:
            raise ProvisioningSpecError("tenant initial owner sealer is not exact")
        if (
            selection_admission_sealer
            != _TENANT_BINDING_SELECTION_CONTROL_ADMISSION_SEALER
        ):
            raise ProvisioningSpecError(
                "tenant binding selection-control admission sealer is not exact"
            )
        if (
            context_owner_admission_sealer
            != _TENANT_CURRENT_CONTEXT_SELECTION_OWNER_ADMISSION_SEALER
        ):
            raise ProvisioningSpecError(
                "tenant current-context selection-owner admission sealer is not exact"
            )
        if native_verifier != _TENANT_NATIVE_VERIFIER:
            raise ProvisioningSpecError("tenant native verifier boundary is not exact")
    elif (
        tenant_lock is not None
        or admission_lock is not None
        or sealer is not None
        or selection_admission_sealer is not None
        or context_owner_admission_sealer is not None
        or native_verifier is not None
    ):
        raise ProvisioningSpecError(
            "the security-audit service must not carry tenant capsules"
        )

    if native_verifier is not None:
        for value, label in (
            (native_verifier.schema_name, "crypto schema"),
            (native_verifier.installer_role, "crypto installer"),
            (native_verifier.extension_name, "crypto extension"),
            (native_verifier.function_name, "crypto verifier function"),
        ):
            _validate_identifier(value, label)
        if (
            native_verifier.schema_name,
            native_verifier.installer_role,
            native_verifier.extension_name,
            native_verifier.extension_version,
            native_verifier.module_pathname,
            native_verifier.function_name,
        ) != (
            "ofarm_crypto",
            "ofarm_crypto_installer",
            "ofarm_ed25519",
            "1.0",
            "$libdir/ofarm_ed25519",
            "ed25519_verify",
        ):
            raise ProvisioningSpecError("native verifier identity differs")
        installer = role_map.get(native_verifier.installer_role)
        if installer is None or (
            installer.login,
            installer.inherit,
            installer.bypass_rls,
            installer.connection_limit,
            installer.superuser,
        ) != (False, False, False, -1, True):
            raise ProvisioningSpecError("crypto installer attributes differ")

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

    if admission_lock is not None:
        if (
            admission_lock.shared_owner_role,
            admission_lock.exclusive_owner_role,
            admission_lock.key_class_id,
            admission_lock.key_object_id,
        ) != (
            "ofarm_binder",
            "ofarm_admission_lock_owner",
            1330004306,
            1413694001,
        ):
            raise ProvisioningSpecError("tenant admission-lock identity differs")
        for owner_name in (
            admission_lock.shared_owner_role,
            admission_lock.exclusive_owner_role,
        ):
            owner = role_map.get(owner_name)
            if owner is None or (
                owner.login,
                owner.inherit,
                owner.connection_limit,
            ) != (False, False, -1):
                raise ProvisioningSpecError(
                    "tenant admission-lock owner must be unassumable"
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
                "ofarm_admission_lock_owner",
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
                    "jsonb",
                    "timestamp with time zone",
                }
                for value in transfer.argument_types
            ):
                raise ProvisioningSpecError("tenant sealer argument type differs")

    if selection_admission_sealer is not None:
        for value, label in (
            (selection_admission_sealer.schema_name, "selection sealer schema"),
            (
                selection_admission_sealer.function_name,
                "selection sealer function",
            ),
            (selection_admission_sealer.execute_role, "selection sealer caller"),
            (
                selection_admission_sealer.ledger_schema_name,
                "selection sealer ledger schema",
            ),
            (selection_admission_sealer.ledger_name, "selection sealer ledger"),
            (
                selection_admission_sealer.target_schema_name,
                "selection sealer target schema",
            ),
            (
                selection_admission_sealer.controller_role,
                "selection sealer controller",
            ),
        ):
            _validate_identifier(value, label)
        if (
            selection_admission_sealer.schema_name,
            selection_admission_sealer.function_name,
            selection_admission_sealer.execute_role,
            selection_admission_sealer.ledger_schema_name,
            selection_admission_sealer.ledger_name,
            selection_admission_sealer.target_schema_name,
            selection_admission_sealer.controller_role,
        ) != (
            lock.schema_name,
            "seal_tenant_binding_selection_control_admission",
            "ofarm_migrator",
            spec.migration_service.schema_name,
            spec.migration_service.ledger_name,
            spec.schema_name,
            "ofarm_command_runtime_bundle_selection_controller",
        ):
            raise ProvisioningSpecError(
                "tenant binding selection-control admission sealer identity differs"
            )

    if context_owner_admission_sealer is not None:
        for value, label in (
            (context_owner_admission_sealer.schema_name, "context sealer schema"),
            (
                context_owner_admission_sealer.function_name,
                "context sealer function",
            ),
            (context_owner_admission_sealer.execute_role, "context sealer caller"),
            (
                context_owner_admission_sealer.ledger_schema_name,
                "context sealer ledger schema",
            ),
            (context_owner_admission_sealer.ledger_name, "context sealer ledger"),
            (
                context_owner_admission_sealer.target_schema_name,
                "context sealer target schema",
            ),
            (context_owner_admission_sealer.owner_role, "context sealer grantee"),
        ):
            _validate_identifier(value, label)
        if (
            context_owner_admission_sealer.schema_name,
            context_owner_admission_sealer.function_name,
            context_owner_admission_sealer.execute_role,
            context_owner_admission_sealer.ledger_schema_name,
            context_owner_admission_sealer.ledger_name,
            context_owner_admission_sealer.target_schema_name,
            context_owner_admission_sealer.owner_role,
        ) != (
            lock.schema_name,
            "seal_tenant_current_context_selection_owner_admission",
            "ofarm_migrator",
            spec.migration_service.schema_name,
            spec.migration_service.ledger_name,
            spec.schema_name,
            spec.database_owner,
        ):
            raise ProvisioningSpecError(
                "tenant current-context selection-owner admission sealer identity differs"
            )

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
        if access_clock_lock is not None and access_clock_lock.owner_role in edge:
            raise ProvisioningSpecError(
                "access-clock lock owner must have no membership edge"
            )
        if tenant_lock is not None and tenant_lock.owner_role in edge:
            raise ProvisioningSpecError("tenant-lock owner must have no membership edge")
        if admission_lock is not None and (
            admission_lock.shared_owner_role in edge
            or admission_lock.exclusive_owner_role in edge
        ):
            raise ProvisioningSpecError(
                "admission-lock owners must have no membership edge"
            )
        if native_verifier is not None and native_verifier.installer_role in edge:
            raise ProvisioningSpecError("crypto installer must have no membership edge")

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
        selection_controller_name = (
            "ofarm_command_runtime_bundle_selection_controller"
        )
        selection_login_name = (
            "ofarm_command_runtime_bundle_selection_control_login"
        )
        selection_controller = role_map.get(selection_controller_name)
        selection_login = role_map.get(selection_login_name)
        if selection_controller is None or (
            selection_controller.login,
            selection_controller.inherit,
            selection_controller.bypass_rls,
            selection_controller.connection_limit,
            selection_controller.superuser,
        ) != (False, False, False, -1, False):
            raise ProvisioningSpecError(
                "selection controller attributes are not exact"
            )
        if selection_login is None or (
            selection_login.login,
            selection_login.inherit,
            selection_login.bypass_rls,
            selection_login.connection_limit,
            selection_login.password_required,
            selection_login.settings,
            selection_login.superuser,
        ) != (True, True, False, 1, True, _CONTROL_SETTINGS, False):
            raise ProvisioningSpecError(
                "selection-control login attributes are not exact"
            )
        selection_memberships = {
            (
                membership.granted_role,
                membership.member_role,
                membership.inherit,
                membership.set_role,
                membership.admin,
            )
            for membership in spec.memberships
            if selection_controller_name in (
                membership.granted_role,
                membership.member_role,
            )
            or selection_login_name in (
                membership.granted_role,
                membership.member_role,
            )
        }
        if selection_memberships != {
            (
                selection_controller_name,
                selection_login_name,
                True,
                False,
                False,
            )
        }:
            raise ProvisioningSpecError(
                "selection-control membership is not exact"
            )
        if spec.database_connect_roles.count(selection_login_name) != 1:
            raise ProvisioningSpecError(
                "selection-control login CONNECT grant is not exact"
            )
        if selection_controller_name in spec.database_connect_roles:
            raise ProvisioningSpecError(
                "selection controller must not receive direct CONNECT"
            )
        if spec.schema_usage_roles.count(selection_controller_name) != 1:
            raise ProvisioningSpecError(
                "selection controller schema USAGE grant is not exact"
            )
        if selection_login_name in spec.schema_usage_roles:
            raise ProvisioningSpecError(
                "selection-control login must not receive direct schema USAGE"
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
