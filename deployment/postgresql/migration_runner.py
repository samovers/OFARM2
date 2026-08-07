"""Transactional PostgreSQL 17 migration runner for the two fixed services.

This is release/operator tooling.  It never creates infrastructure, invents a
ledger, or runs from application startup.  Exact migration bytes own every
application object, including the ledger created by ``0001_initial.sql``.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from textwrap import dedent
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from deployment.postgresql.catalog_classifier import (
    SCHEMA_LOCAL_OBJECT_SELECTS_SQL,
)
from deployment.postgresql.catalog_identity import (
    CATALOG_OUTPUT_SETTING_ASSIGNMENTS,
    CatalogIdentityError,
    verify_catalog_identity,
)
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    Migration,
    MigrationSet,
    MigrationSetError,
    require_authoritative_migration_set,
    revalidate_migration_set,
)
from deployment.postgresql.provisioning import (
    ProvisioningError,
    ProvisioningInfrastructureReport,
    _tenant_selection_v8_post_source_locked_differences,
    migration_locked_differences,
    verify_service_infrastructure,
)
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC,
    ProvisioningSpec,
    ProvisioningSpecError,
    require_frozen_tenant_native_verifier_authority,
)
from deployment.postgresql.tenant_contract import TENANT_CONTEXT_CONTRACT
from deployment.postgresql.version_policy import (
    SUPPORTED_POSTGRESQL_SERVER_VERSION,
    SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
)


_RELEASE_IDENTITY = re.compile(r"[!-~]{1,128}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_LEDGER_GUARD_FUNCTION = "reject_schema_migration_mutation"
_UPDATE_DELETE_TRIGGER = "schema_migration_reject_update_delete"
_TRUNCATE_TRIGGER = "schema_migration_reject_truncate"
_TENANT_SELECTION_ACTIVATION_MIGRATION_FILENAME = (
    "0008_tenant_command_runtime_bundle_selection.sql"
)
_LEDGER_GUARD_SOURCE = (
    "BEGIN RAISE EXCEPTION USING ERRCODE = '55000', "
    "MESSAGE = 'schema_migration is append-only'; END"
)


class MigrationError(RuntimeError):
    """Base class for migration release failures."""


class MigrationInputError(MigrationError):
    """Caller input or migration bytes are not in the closed contract."""


class MigrationTargetError(MigrationError):
    """A route, identity, server, or infrastructure observation is wrong."""


class MigrationDirtyError(MigrationError):
    """The target phase, ledger contract, or history is not exact."""


class MigrationBusyError(MigrationError):
    """Another release holds the protected transaction lock."""


class MigrationExecutionError(MigrationError):
    """One exact migration or its atomic ledger append failed."""

    def __init__(self, version: int, filename: str, message: str):
        self.version = version
        self.filename = filename
        super().__init__(
            f"migration {version:04d} ({filename}) failed: {message}"
        )


class MigrationOutcomeUnknown(MigrationError):
    """The database connection failed while commit outcome was uncertain."""

    def __init__(self, version: int, filename: str, execution_id: UUID):
        self.version = version
        self.filename = filename
        self.execution_id = execution_id
        super().__init__(
            "migration commit outcome is unknown for "
            f"{version:04d} ({filename}); retry execution {execution_id}"
        )


@dataclass(frozen=True, slots=True)
class MigrationRunReport:
    """Exact observed outcome of one release-runner invocation."""

    service_identity: str
    provisioning_spec_digest: str
    migration_set_digest: str
    database_name: str
    system_identifier: str
    server_version_num: int
    previous_version: int
    final_version: int
    applied_versions: tuple[int, ...]
    execution_id: UUID
    observed_head_execution_id: UUID

    @property
    def verified_noop(self) -> bool:
        return not self.applied_versions

    def manifest(self) -> dict[str, object]:
        return {
            "schemaVersion": "ofarm.postgresql-migration-run-report.v1",
            "serviceIdentity": self.service_identity,
            "provisioningSpecDigest": self.provisioning_spec_digest,
            "migrationSetDigest": self.migration_set_digest,
            "databaseName": self.database_name,
            "systemIdentifier": self.system_identifier,
            "serverVersionNum": self.server_version_num,
            "previousVersion": self.previous_version,
            "finalVersion": self.final_version,
            "appliedVersions": list(self.applied_versions),
            "executionId": str(self.execution_id),
            "observedHeadExecutionId": str(self.observed_head_execution_id),
            "verifiedNoop": self.verified_noop,
        }


@dataclass(frozen=True, slots=True)
class _TargetIdentity:
    database_name: str
    system_identifier: str
    server_version_num: int


@dataclass(frozen=True, slots=True)
class _HistoryObservation:
    version: int
    head_execution_id: UUID | None


def _quoted_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quoted_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _require_fixed_pair(spec: ProvisioningSpec, migration_set: MigrationSet) -> None:
    if spec not in (TENANT_PROVISIONING_SPEC, SECURITY_AUDIT_PROVISIONING_SPEC):
        raise MigrationInputError("spec must be one checked-in PostgreSQL service")
    if spec == TENANT_PROVISIONING_SPEC:
        try:
            require_frozen_tenant_native_verifier_authority()
        except ProvisioningSpecError as exc:
            raise MigrationInputError(str(exc)) from exc
    try:
        revalidate_migration_set(migration_set)
    except MigrationSetError as exc:
        raise MigrationInputError(str(exc)) from exc
    if migration_set.service != spec.migration_service:
        raise MigrationInputError("migration set and provisioning service differ")
    if migration_set.service not in (TENANT_SERVICE, SECURITY_AUDIT_SERVICE):
        raise MigrationInputError("migration service is not fixed")


def initial_ledger_sql(spec: ProvisioningSpec) -> str:
    """Return exact reviewed ``0001`` ledger DDL for tests and baseline authoring.

    The runner deliberately never calls this helper.  The returned text must be
    included in immutable migration bytes before execution can create a ledger.
    """

    if spec not in (TENANT_PROVISIONING_SPEC, SECURITY_AUDIT_PROVISIONING_SPEC):
        raise MigrationInputError("ledger DDL requires one checked-in service")
    schema = _quoted_identifier(spec.schema_name)
    ledger = _quoted_identifier(spec.migration_service.ledger_name)
    qualified_ledger = f"{schema}.{ledger}"
    guard = f"{schema}.{_quoted_identifier(_LEDGER_GUARD_FUNCTION)}"
    readiness = _quoted_identifier(spec.readiness_role_name)
    service_identity = _quoted_literal(spec.migration_service.identity)
    return dedent(
        f"""
        CREATE TABLE {qualified_ledger} (
            version pg_catalog.int4 NOT NULL,
            filename pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
            source_sha256 pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
            source_byte_length pg_catalog.int8 NOT NULL,
            applied_prefix_digest pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
            service_identity pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
            provisioning_spec_digest pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
            release_identity pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
            execution_id pg_catalog.uuid NOT NULL,
            applied_at pg_catalog.timestamptz NOT NULL
                DEFAULT pg_catalog.clock_timestamp(),

            CONSTRAINT schema_migration_pkey PRIMARY KEY (version),
            CONSTRAINT schema_migration_filename_key UNIQUE (filename),
            CONSTRAINT schema_migration_version_check
                CHECK (version BETWEEN 1 AND 9999),
            CONSTRAINT schema_migration_filename_check
                CHECK (
                    filename ~ '^[0-9]{{4}}_[a-z][a-z0-9_]*[.]sql$'
                    AND pg_catalog.substring(filename, 1, 4)
                        = pg_catalog.lpad(version::pg_catalog.text, 4, '0')
                ),
            CONSTRAINT schema_migration_source_sha256_check
                CHECK (source_sha256 ~ '^sha256:[0-9a-f]{{64}}$'),
            CONSTRAINT schema_migration_source_length_check
                CHECK (source_byte_length > 0),
            CONSTRAINT schema_migration_prefix_digest_check
                CHECK (applied_prefix_digest ~ '^sha256:[0-9a-f]{{64}}$'),
            CONSTRAINT schema_migration_service_check
                CHECK (service_identity = {service_identity}),
            CONSTRAINT schema_migration_provisioning_digest_check
                CHECK (provisioning_spec_digest ~ '^sha256:[0-9a-f]{{64}}$'),
            CONSTRAINT schema_migration_release_check
                CHECK (release_identity ~ '^[!-~]{{1,128}}$'),
            CONSTRAINT schema_migration_execution_id_check
                CHECK (
                    execution_id <>
                    '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
                ),
            CONSTRAINT schema_migration_applied_at_check
                CHECK (
                    applied_at <> 'infinity'::pg_catalog.timestamptz
                    AND applied_at <> '-infinity'::pg_catalog.timestamptz
                )
        );

        CREATE FUNCTION {guard}() RETURNS pg_catalog.trigger
        LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS {_quoted_literal(_LEDGER_GUARD_SOURCE)};

        REVOKE ALL PRIVILEGES ON FUNCTION {guard}() FROM PUBLIC;
        REVOKE ALL PRIVILEGES ON TABLE {qualified_ledger} FROM PUBLIC;

        CREATE TRIGGER {_quoted_identifier(_UPDATE_DELETE_TRIGGER)}
        BEFORE UPDATE OR DELETE ON {qualified_ledger}
        FOR EACH ROW EXECUTE FUNCTION {guard}();

        CREATE TRIGGER {_quoted_identifier(_TRUNCATE_TRIGGER)}
        BEFORE TRUNCATE ON {qualified_ledger}
        FOR EACH STATEMENT EXECUTE FUNCTION {guard}();

        GRANT SELECT (
            version,
            filename,
            source_sha256,
            source_byte_length,
            applied_prefix_digest,
            service_identity,
            provisioning_spec_digest
        ) ON TABLE {qualified_ledger} TO {readiness};
        """
    ).lstrip()


def _is_escape_string(text: str, quote_index: int) -> bool:
    if quote_index >= 1 and text[quote_index - 1] in "eE":
        before = text[quote_index - 2] if quote_index >= 2 else ""
        return not (before.isalnum() or before in "_$")
    if quote_index >= 2 and text[quote_index - 2 : quote_index].lower() == "u&":
        before = text[quote_index - 3] if quote_index >= 3 else ""
        return not (before.isalnum() or before in "_$")
    return False


def _statement_tokens(source: str, filename: str) -> list[list[str]]:
    statements: list[list[str]] = []
    tokens: list[str] = []
    length = len(source)
    index = 0
    while index < length:
        character = source[index]
        if character.isspace():
            index += 1
            continue
        if source.startswith("--", index):
            carriage_return = source.find("\r", index + 2)
            line_feed = source.find("\n", index + 2)
            line_endings = tuple(
                ending for ending in (carriage_return, line_feed) if ending >= 0
            )
            index = length if not line_endings else min(line_endings) + 1
            continue
        if source.startswith("/*", index):
            depth = 1
            index += 2
            while index < length and depth:
                if source.startswith("/*", index):
                    depth += 1
                    index += 2
                elif source.startswith("*/", index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            if depth:
                raise MigrationInputError(
                    f"migration {filename} contains an unterminated block comment"
                )
            continue
        if character == "'":
            escape_backslash = _is_escape_string(source, index)
            index += 1
            while index < length:
                if source[index] == "'":
                    if index + 1 < length and source[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    break
                if escape_backslash and source[index] == "\\":
                    index += 2
                else:
                    index += 1
            else:
                raise MigrationInputError(
                    f"migration {filename} contains an unterminated string"
                )
            continue
        if character == '"':
            index += 1
            while index < length:
                if source[index] == '"':
                    if index + 1 < length and source[index + 1] == '"':
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            else:
                raise MigrationInputError(
                    f"migration {filename} contains an unterminated identifier"
                )
            continue
        if character == "$":
            match = re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$", source[index:])
            if match is not None:
                tag = match.group(0)
                end = source.find(tag, index + len(tag))
                if end < 0:
                    raise MigrationInputError(
                        f"migration {filename} contains an unterminated dollar body"
                    )
                index = end + len(tag)
                continue
        if character == "\\":
            raise MigrationInputError(
                f"migration {filename} contains a client-side meta-command"
            )
        if character == ";":
            if tokens:
                statements.append(tokens)
                tokens = []
            index += 1
            continue
        if character.isalpha() or character == "_":
            end = index + 1
            while end < length and (
                source[end].isalnum() or source[end] in "_$"
            ):
                end += 1
            tokens.append(source[index:end].upper())
            index = end
            continue
        index += 1
    if tokens:
        statements.append(tokens)
    return statements


def _prohibited_statement(tokens: list[str]) -> bool:
    first = tokens[0]
    if first in {
        "BEGIN",
        "COMMIT",
        "END",
        "ROLLBACK",
        "ABORT",
        "SAVEPOINT",
        "RELEASE",
    }:
        return True
    if first == "START" and len(tokens) > 1 and tokens[1] == "TRANSACTION":
        return True
    if first == "PREPARE" and len(tokens) > 1 and tokens[1] == "TRANSACTION":
        return True
    if first in {"SET", "RESET"}:
        return True
    if first == "COPY":
        return any(
            tokens[index : index + 2] == ["FROM", "STDIN"]
            for index in range(1, len(tokens) - 1)
        )
    return False


def validate_migration_source(source_bytes: bytes, filename: str) -> str:
    """Decode exact bytes and reject runner-owned top-level SQL controls."""

    if type(source_bytes) is not bytes or not source_bytes:
        raise MigrationInputError(f"migration {filename} source must be exact bytes")
    if not isinstance(filename, str) or not filename:
        raise MigrationInputError("migration filename must be non-empty")
    if b"\x00" in source_bytes or source_bytes.startswith(b"\xef\xbb\xbf"):
        raise MigrationInputError(f"migration {filename} source encoding is forbidden")
    try:
        source = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise MigrationInputError(
            f"migration {filename} is not strict UTF-8"
        ) from exc
    if not source.strip():
        raise MigrationInputError(f"migration {filename} contains no SQL")
    statements = _statement_tokens(source, filename)
    if not statements:
        raise MigrationInputError(f"migration {filename} contains no SQL statement")
    for tokens in statements:
        if _prohibited_statement(tokens):
            raise MigrationInputError(
                f"migration {filename} contains runner-owned SQL control"
            )
    return source


def _release_identity(value: str) -> str:
    if not isinstance(value, str) or _RELEASE_IDENTITY.fullmatch(value) is None:
        raise MigrationInputError(
            "release_identity must contain 1-128 visible ASCII characters"
        )
    return value


def _execution_identity(value: UUID) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise MigrationInputError("execution_id must be one nonnil UUID")
    return value


def _preflight_sources(migration_set: MigrationSet) -> tuple[str, ...]:
    return tuple(
        validate_migration_source(migration.source_bytes, migration.filename)
        for migration in migration_set.migrations
    )


def _observe_infrastructure(
    admin_dsn: str, spec: ProvisioningSpec
) -> ProvisioningInfrastructureReport:
    deadline = time.monotonic() + 5.0
    while True:
        try:
            return verify_service_infrastructure(admin_dsn, spec)
        except ProvisioningError as exc:
            if (
                "another provisioner holds the service lock" in str(exc)
                and time.monotonic() < deadline
            ):
                time.sleep(0.025)
                continue
            raise MigrationTargetError(str(exc)) from exc
        except psycopg.Error:
            raise MigrationTargetError(
                "admin provisioning route is unavailable"
            ) from None


def _target_identity(
    connection: psycopg.Connection,
    report: ProvisioningInfrastructureReport,
) -> _TargetIdentity:
    try:
        row = connection.execute(
            """
            SELECT SESSION_USER::text,
                   CURRENT_USER::text,
                   pg_catalog.current_database()::text,
                   pg_catalog.current_setting('server_version_num')::integer,
                   pg_catalog.current_setting('server_version')::text,
                   control.system_identifier::text,
                   pg_catalog.pg_is_in_recovery(),
                   pg_catalog.current_setting('transaction_read_only')
            FROM pg_catalog.pg_control_system() AS control
            """
        ).fetchone()
    except psycopg.Error as exc:
        raise MigrationTargetError("migrator route identity is unreadable") from exc
    if row is None or row[0:2] != ("ofarm_migrator", "ofarm_migrator"):
        raise MigrationTargetError("migrator route must use exact ofarm_migrator")
    identity = _TargetIdentity(row[2], row[5], row[3])
    if identity.database_name != report.database_name:
        raise MigrationTargetError("migrator route reached the wrong database")
    if identity.system_identifier != report.system_identifier:
        raise MigrationTargetError("admin and migrator routes reach different clusters")
    if (
        identity.server_version_num != report.server_version_num
        or identity.server_version_num != SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM
        or row[4] != SUPPORTED_POSTGRESQL_SERVER_VERSION
    ):
        raise MigrationTargetError("migrator route PostgreSQL version differs")
    if row[6] is not False or row[7] != "off":
        raise MigrationTargetError("migrator route is not a writable primary")
    return identity


def _begin_and_lock(connection: psycopg.Connection, spec: ProvisioningSpec) -> None:
    wrapper = sql.Identifier(
        spec.migration_lock.schema_name,
        spec.migration_lock.function_name,
    )
    try:
        connection.execute(
            "BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED READ WRITE"
        )
        try:
            connection.execute(sql.SQL("SELECT {}()").format(wrapper)).fetchone()
        except (
            psycopg.errors.QueryCanceled,
            psycopg.errors.LockNotAvailable,
        ) as exc:
            raise MigrationBusyError(
                "another migration runner holds the lock"
            ) from exc
        for assignment in CATALOG_OUTPUT_SETTING_ASSIGNMENTS:
            connection.execute(f"SET LOCAL {assignment}")
    except MigrationBusyError:
        _rollback_quietly(connection)
        raise
    except psycopg.Error as exc:
        _rollback_quietly(connection)
        raise MigrationTargetError(
            "protected migration transaction setup failed"
        ) from exc


def _rollback_quietly(connection: psycopg.Connection) -> None:
    try:
        connection.rollback()
    except psycopg.Error:
        pass


def _ledger_oid(connection: psycopg.Connection, spec: ProvisioningSpec) -> int | None:
    return connection.execute(
        "SELECT pg_catalog.to_regclass(%s)::pg_catalog.oid",
        (spec.migration_service.qualified_ledger,),
    ).fetchone()[0]


def _locked_boundary_differences(
    connection: psycopg.Connection, spec: ProvisioningSpec
) -> list[str]:
    try:
        return migration_locked_differences(connection, spec)
    except ProvisioningError as exc:
        raise MigrationTargetError(str(exc)) from exc


def _locked_tenant_v8_post_source_boundary_differences(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
) -> list[str]:
    try:
        return _tenant_selection_v8_post_source_locked_differences(
            connection,
            spec,
        )
    except ProvisioningError as exc:
        raise MigrationTargetError(str(exc)) from exc


def _schema_object_rows(
    connection: psycopg.Connection,
    schema_names: tuple[str, ...],
) -> list[tuple[str, str, str]]:
    rows = connection.execute(
        f"""
        WITH target_names AS (
            SELECT pg_catalog.unnest(%s::text[]) AS schema_name
        )
        {SCHEMA_LOCAL_OBJECT_SELECTS_SQL}
        ORDER BY 1, 2, 3
        """,
        (list(schema_names),),
    ).fetchall()
    return [tuple(row) for row in rows]


def _require_fresh_catalog(
    connection: psycopg.Connection, spec: ProvisioningSpec
) -> None:
    if _ledger_oid(connection, spec) is not None or _schema_object_rows(
        connection,
        (spec.schema_name,),
    ):
        raise MigrationDirtyError("missing ledger target is not exactly fresh")


def _set_owner_role(connection: psycopg.Connection, spec: ProvisioningSpec) -> None:
    connection.execute(
        sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(spec.schema_owner))
    )
    current_user = connection.execute("SELECT CURRENT_USER::text").fetchone()[0]
    if current_user != spec.schema_owner:
        raise MigrationTargetError("migrator cannot assume the fixed schema owner")


def _consume_tenant_initial_owner_sealer(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    migration: Migration,
) -> None:
    """Seal migration-0001 routine owners and remove the bootstrap capsule."""

    sealer = spec.tenant_initial_owner_sealer
    if sealer is None:
        return
    if migration.version != 1:
        raise MigrationDirtyError("tenant owner sealer survived migration 0001")

    connection.execute("RESET ROLE")
    if connection.execute("SELECT CURRENT_USER::text").fetchone()[0] != (
        sealer.execute_role
    ):
        raise MigrationTargetError("tenant owner sealer caller differs")
    connection.execute(
        sql.SQL("SELECT {}()").format(
            sql.Identifier(sealer.schema_name, sealer.function_name)
        )
    ).fetchone()

    transfer_names = sorted({item.function_name for item in sealer.transfers})
    rows = connection.execute(
        """
        SELECT namespace.nspname::text,
               routine.proname::text,
               pg_catalog.oidvectortypes(routine.proargtypes),
               owner.rolname::text
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        WHERE namespace.nspname = %s
          AND routine.proname::text = ANY (%s::text[])
        ORDER BY 1, 2, 3
        """,
        (sealer.target_schema_name, transfer_names),
    ).fetchall()
    expected_transfers = {
        (
            item.schema_name,
            item.function_name,
            item.identity_arguments,
            item.owner_role,
        )
        for item in sealer.transfers
    }
    if {tuple(row) for row in rows} != expected_transfers:
        raise MigrationDirtyError("tenant initial routine ownership seal differs")

    sealer_row = connection.execute(
        """
        SELECT owner.rolname::text,
               routine.prosecdef
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        WHERE namespace.nspname = %s
          AND routine.proname = %s
          AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = ''
        """,
        (sealer.schema_name, sealer.function_name),
    ).fetchone()
    if tuple(sealer_row or ()) != (sealer.execute_role, False):
        raise MigrationDirtyError("tenant initial owner sealer did not self-demote")

    privilege_roles = sorted(
        {item.owner_role for item in sealer.transfers} | {sealer.execute_role}
    )
    create_privileges = connection.execute(
        """
        SELECT role_name,
               pg_catalog.has_schema_privilege(
                   role_name, schema_name, 'CREATE'
               )
        FROM pg_catalog.unnest(%s::text[]) AS roles(role_name)
        CROSS JOIN pg_catalog.unnest(%s::text[]) AS schemas(schema_name)
        ORDER BY 1, 2
        """,
        (privilege_roles, [sealer.target_schema_name, sealer.schema_name]),
    ).fetchall()
    if any(has_create for _role_name, has_create in create_privileges):
        raise MigrationDirtyError("tenant owner sealer left schema CREATE privilege")

    connection.execute(
        sql.SQL("DROP FUNCTION {}()").format(
            sql.Identifier(sealer.schema_name, sealer.function_name)
        )
    )
    _set_owner_role(connection, spec)


def _authenticate_tenant_binding_selection_control_admission_row(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    migration_set: MigrationSet,
    migration: Migration,
    release_identity: str,
    execution_id: UUID,
) -> None:
    """Authenticate the complete runner-owned V5 row before capsule use."""

    row = connection.execute(
        sql.SQL(
            "SELECT version, filename, source_sha256, source_byte_length, "
            "applied_prefix_digest, service_identity, "
            "provisioning_spec_digest, release_identity, execution_id "
            "FROM {} WHERE version = 5"
        ).format(
            sql.Identifier(
                spec.migration_service.schema_name,
                spec.migration_service.ledger_name,
            )
        )
    ).fetchone()
    if tuple(row or ()) != (
        5,
        "0005_tenant_binding_selection_control_admission.sql",
        migration.source_sha256,
        migration.byte_length,
        migration_set.prefix_digest(5),
        "ofarm.tenant-postgresql.v1",
        spec.digest,
        release_identity,
        execution_id,
    ):
        raise MigrationDirtyError(
            "tenant binding selection-control admission row is not exact"
        )


def _consume_tenant_binding_selection_control_admission_sealer(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    migration: Migration,
) -> None:
    """Consume the closed V5 binder-admission capsule and prove its result."""

    sealer = spec.tenant_binding_selection_control_admission_sealer
    if sealer is None:
        return
    if (
        migration.version,
        migration.filename,
    ) != (5, "0005_tenant_binding_selection_control_admission.sql"):
        raise MigrationDirtyError(
            "tenant binding selection-control admission sealer reached wrong migration"
        )

    connection.execute("RESET ROLE")
    if connection.execute("SELECT CURRENT_USER::text").fetchone()[0] != (
        sealer.execute_role
    ):
        raise MigrationTargetError(
            "tenant binding selection-control admission sealer caller differs"
        )
    connection.execute(
        sql.SQL("SELECT {}()").format(
            sql.Identifier(sealer.schema_name, sealer.function_name)
        )
    ).fetchone()

    sealer_row = connection.execute(
        """
        SELECT owner.rolname::text,
               routine.prosecdef,
               language.lanname::text,
               routine.provolatile,
               routine.proparallel,
               routine.proretset,
               routine.prorettype = 'pg_catalog.void'::pg_catalog.regtype,
               routine.prosrc,
               COALESCE(routine.proconfig, ARRAY[]::text[])
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
        WHERE namespace.nspname = %s
          AND routine.proname = %s
          AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = ''
        """,
        (sealer.schema_name, sealer.function_name),
    ).fetchone()
    if tuple(sealer_row or ()) != (
        sealer.execute_role,
        False,
        "plpgsql",
        "v",
        "u",
        False,
        True,
        sealer.source,
        ["search_path=pg_catalog, pg_temp"],
    ):
        raise MigrationDirtyError(
            "tenant binding selection-control admission sealer did not self-demote"
        )

    capsule_acl = connection.execute(
        """
        SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
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
          AND routine.proname = %s
          AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = ''
        ORDER BY 1, 2, 3, 4
        """,
        (sealer.schema_name, sealer.function_name),
    ).fetchall()
    if {tuple(row) for row in capsule_acl} != {
        (
            sealer.execute_role,
            sealer.execute_role,
            "EXECUTE",
            False,
        )
    }:
        raise MigrationDirtyError(
            "tenant binding selection-control admission sealer ACL differs"
        )

    binder_acl = connection.execute(
        """
        SELECT routine.proname::text,
               pg_catalog.oidvectortypes(routine.proargtypes),
               grantee.rolname::text,
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
        JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        WHERE namespace.nspname = %s
          AND grantee.rolname = ANY (%s::text[])
        ORDER BY 1, 2, 3, 4, 5, 6
        """,
        (
            sealer.target_schema_name,
            [
                sealer.controller_role,
                "ofarm_command_runtime_bundle_selection_control_login",
            ],
        ),
    ).fetchall()
    if {tuple(row) for row in binder_acl} != {
        (
            "create_tenant_challenge",
            "",
            sealer.controller_role,
            "ofarm_binder",
            "EXECUTE",
            False,
        ),
        (
            "bind_tenant_capability",
            "text",
            sealer.controller_role,
            "ofarm_binder",
            "EXECUTE",
            False,
        ),
    }:
        raise MigrationDirtyError(
            "tenant binding selection-control admission grants differ"
        )

    create_privilege = connection.execute(
        "SELECT pg_catalog.has_schema_privilege(%s, %s, 'CREATE')",
        (sealer.execute_role, sealer.schema_name),
    ).fetchone()
    if tuple(create_privilege or ()) != (False,):
        raise MigrationDirtyError(
            "tenant binding selection-control admission sealer left schema CREATE"
        )

    connection.execute(
        sql.SQL("DROP FUNCTION {}()").format(
            sql.Identifier(sealer.schema_name, sealer.function_name)
        )
    )
    _set_owner_role(connection, spec)


def _authenticate_tenant_current_context_selection_owner_admission_row(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    migration_set: MigrationSet,
    migration: Migration,
    release_identity: str,
    execution_id: UUID,
) -> None:
    """Authenticate the complete runner-owned V6 row before capsule use."""

    row = connection.execute(
        sql.SQL(
            "SELECT version, filename, source_sha256, source_byte_length, "
            "applied_prefix_digest, service_identity, "
            "provisioning_spec_digest, release_identity, execution_id "
            "FROM {} WHERE version = 6"
        ).format(
            sql.Identifier(
                spec.migration_service.schema_name,
                spec.migration_service.ledger_name,
            )
        )
    ).fetchone()
    if tuple(row or ()) != (
        6,
        "0006_tenant_current_context_selection_owner_admission.sql",
        migration.source_sha256,
        migration.byte_length,
        migration_set.prefix_digest(6),
        "ofarm.tenant-postgresql.v1",
        spec.digest,
        release_identity,
        execution_id,
    ):
        raise MigrationDirtyError(
            "tenant current-context selection-owner admission row is not exact"
        )


def _consume_tenant_current_context_selection_owner_admission_sealer(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    migration: Migration,
) -> None:
    """Consume the closed V6 binder-admission capsule and prove its result."""

    sealer = spec.tenant_current_context_selection_owner_admission_sealer
    if sealer is None:
        return
    if (
        migration.version,
        migration.filename,
    ) != (6, "0006_tenant_current_context_selection_owner_admission.sql"):
        raise MigrationDirtyError(
            "tenant current-context selection-owner admission sealer reached "
            "wrong migration"
        )

    connection.execute("RESET ROLE")
    if connection.execute("SELECT CURRENT_USER::text").fetchone()[0] != (
        sealer.execute_role
    ):
        raise MigrationTargetError(
            "tenant current-context selection-owner admission sealer caller differs"
        )
    connection.execute(
        sql.SQL("SELECT {}()").format(
            sql.Identifier(sealer.schema_name, sealer.function_name)
        )
    ).fetchone()

    sealer_row = connection.execute(
        """
        SELECT owner.rolname::text,
               routine.prosecdef,
               language.lanname::text,
               routine.provolatile,
               routine.proparallel,
               routine.proretset,
               routine.prorettype = 'pg_catalog.void'::pg_catalog.regtype,
               routine.prosrc,
               COALESCE(routine.proconfig, ARRAY[]::text[])
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
        WHERE namespace.nspname = %s
          AND routine.proname = %s
          AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = ''
        """,
        (sealer.schema_name, sealer.function_name),
    ).fetchone()
    if tuple(sealer_row or ()) != (
        sealer.execute_role,
        False,
        "plpgsql",
        "v",
        "u",
        False,
        True,
        sealer.source,
        ["search_path=pg_catalog, pg_temp"],
    ):
        raise MigrationDirtyError(
            "tenant current-context selection-owner admission sealer did not "
            "self-demote"
        )

    capsule_acl = connection.execute(
        """
        SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
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
          AND routine.proname = %s
          AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = ''
        ORDER BY 1, 2, 3, 4
        """,
        (sealer.schema_name, sealer.function_name),
    ).fetchall()
    if {tuple(row) for row in capsule_acl} != {
        (
            sealer.execute_role,
            sealer.execute_role,
            "EXECUTE",
            False,
        )
    }:
        raise MigrationDirtyError(
            "tenant current-context selection-owner admission sealer ACL differs"
        )

    # This closes admission-adjacent roles. The final SQL verifier owns the
    # exhaustive ten-row current-context ACL inventory.
    current_context_acl = connection.execute(
        """
        SELECT routine.proname::text,
               pg_catalog.oidvectortypes(routine.proargtypes),
               grantee.rolname::text,
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
        JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        WHERE namespace.nspname = %s
          AND routine.proname = ANY (%s::text[])
          AND pg_catalog.oidvectortypes(routine.proargtypes) = ''
          AND grantee.rolname = ANY (%s::text[])
        ORDER BY 1, 2, 3, 4, 5, 6
        """,
        (
            sealer.target_schema_name,
            ["current_authenticated_principal_ref", "current_tenant_id"],
            [
                sealer.owner_role,
                "ofarm_command_runtime_bundle_selection_controller",
                "ofarm_command_runtime_bundle_selection_control_login",
                sealer.execute_role,
            ],
        ),
    ).fetchall()
    if {tuple(row) for row in current_context_acl} != {
        (
            "current_authenticated_principal_ref",
            "",
            sealer.owner_role,
            "ofarm_binder",
            "EXECUTE",
            False,
        ),
        (
            "current_tenant_id",
            "",
            sealer.owner_role,
            "ofarm_binder",
            "EXECUTE",
            False,
        ),
    }:
        raise MigrationDirtyError(
            "tenant current-context selection-owner admission grants differ"
        )

    create_privilege = connection.execute(
        "SELECT pg_catalog.has_schema_privilege(%s, %s, 'CREATE')",
        (sealer.execute_role, sealer.schema_name),
    ).fetchone()
    if tuple(create_privilege or ()) != (False,):
        raise MigrationDirtyError(
            "tenant current-context selection-owner admission sealer left "
            "schema CREATE"
        )

    connection.execute(
        sql.SQL("DROP FUNCTION {}()").format(
            sql.Identifier(sealer.schema_name, sealer.function_name)
        )
    )
    _set_owner_role(connection, spec)


def _authenticate_tenant_write_lock_selection_owner_admission_row(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    migration_set: MigrationSet,
    migration: Migration,
    release_identity: str,
    execution_id: UUID,
) -> None:
    """Authenticate the complete runner-owned V7 row before capsule use."""

    row = connection.execute(
        sql.SQL(
            "SELECT version, filename, source_sha256, source_byte_length, "
            "applied_prefix_digest, service_identity, "
            "provisioning_spec_digest, release_identity, execution_id "
            "FROM {} WHERE version = 7"
        ).format(
            sql.Identifier(
                spec.migration_service.schema_name,
                spec.migration_service.ledger_name,
            )
        )
    ).fetchone()
    if tuple(row or ()) != (
        7,
        "0007_tenant_write_lock_selection_owner_admission.sql",
        migration.source_sha256,
        migration.byte_length,
        migration_set.prefix_digest(7),
        "ofarm.tenant-postgresql.v1",
        spec.digest,
        release_identity,
        execution_id,
    ):
        raise MigrationDirtyError(
            "tenant write-lock selection-owner admission row is not exact"
        )


def _consume_tenant_write_lock_selection_owner_admission_sealer(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    migration: Migration,
) -> None:
    """Consume the closed V7 write-lock admission capsule and prove its result."""

    sealer = spec.tenant_write_lock_selection_owner_admission_sealer
    lock = spec.tenant_write_lock
    if sealer is None:
        return
    if lock is None:
        raise MigrationDirtyError(
            "tenant write-lock selection-owner admission target is absent"
        )
    if (
        migration.version,
        migration.filename,
    ) != (7, "0007_tenant_write_lock_selection_owner_admission.sql"):
        raise MigrationDirtyError(
            "tenant write-lock selection-owner admission sealer reached "
            "wrong migration"
        )

    connection.execute("RESET ROLE")
    if connection.execute("SELECT CURRENT_USER::text").fetchone()[0] != (
        sealer.execute_role
    ):
        raise MigrationTargetError(
            "tenant write-lock selection-owner admission sealer caller differs"
        )
    connection.execute(
        sql.SQL("SELECT {}()").format(
            sql.Identifier(sealer.schema_name, sealer.function_name)
        )
    ).fetchone()

    sealer_row = connection.execute(
        """
        SELECT owner.rolname::text,
               routine.prosecdef,
               language.lanname::text,
               routine.provolatile,
               routine.proparallel,
               routine.proretset,
               routine.prorettype = 'pg_catalog.void'::pg_catalog.regtype,
               routine.prosrc,
               COALESCE(routine.proconfig, ARRAY[]::text[])
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
        WHERE namespace.nspname = %s
          AND routine.proname = %s
          AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = ''
        """,
        (sealer.schema_name, sealer.function_name),
    ).fetchone()
    if tuple(sealer_row or ()) != (
        sealer.execute_role,
        False,
        "plpgsql",
        "v",
        "u",
        False,
        True,
        sealer.source,
        ["search_path=pg_catalog, pg_temp"],
    ):
        raise MigrationDirtyError(
            "tenant write-lock selection-owner admission sealer did not "
            "self-demote"
        )

    capsule_acl = connection.execute(
        """
        SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
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
          AND routine.proname = %s
          AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = ''
        ORDER BY 1, 2, 3, 4
        """,
        (sealer.schema_name, sealer.function_name),
    ).fetchall()
    if {tuple(row) for row in capsule_acl} != {
        (sealer.execute_role, sealer.execute_role, "EXECUTE", False)
    }:
        raise MigrationDirtyError(
            "tenant write-lock selection-owner admission sealer ACL differs"
        )

    wrapper_acl = connection.execute(
        """
        SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
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
          AND routine.proname = %s
          AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = ''
        ORDER BY 1, 2, 3, 4
        """,
        (lock.schema_name, lock.function_name),
    ).fetchall()
    if {tuple(row) for row in wrapper_acl} != {
        (lock.owner_role, lock.owner_role, "EXECUTE", False),
        ("ofarm_app", lock.owner_role, "EXECUTE", False),
        ("ofarm_worker", lock.owner_role, "EXECUTE", False),
        (sealer.owner_role, lock.owner_role, "EXECUTE", False),
    }:
        raise MigrationDirtyError(
            "tenant write-lock selection-owner admission grants differ"
        )

    create_privilege = connection.execute(
        "SELECT pg_catalog.has_schema_privilege(%s, %s, 'CREATE')",
        (sealer.execute_role, sealer.schema_name),
    ).fetchone()
    if tuple(create_privilege or ()) != (False,):
        raise MigrationDirtyError(
            "tenant write-lock selection-owner admission sealer left schema CREATE"
        )

    connection.execute(
        sql.SQL("DROP FUNCTION {}()").format(
            sql.Identifier(sealer.schema_name, sealer.function_name)
        )
    )
    _set_owner_role(connection, spec)


def _relation_acl(
    connection: psycopg.Connection, oid: int
) -> set[tuple[str, str, str, bool]]:
    rows = connection.execute(
        """
        SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                    ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
               pg_catalog.pg_get_userbyid(acl.grantor),
               acl.privilege_type,
               acl.is_grantable
        FROM pg_catalog.pg_class AS relation
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                relation.relacl,
                pg_catalog.acldefault('r', relation.relowner)
            )
        ) AS acl
        WHERE relation.oid = %s
        """,
        (oid,),
    ).fetchall()
    return {
        (str(row[0]), str(row[1]), str(row[2]), bool(row[3]))
        for row in rows
    }


def _verify_ledger_contract(
    connection: psycopg.Connection, spec: ProvisioningSpec
) -> None:
    oid = _ledger_oid(connection, spec)
    if oid is None:
        raise MigrationDirtyError("migration ledger is absent")
    relation = connection.execute(
        """
        SELECT relation.relkind,
               relation.relpersistence,
               owner.rolname::text,
               relation.relispartition,
               relation.relrowsecurity,
               relation.relforcerowsecurity,
               EXISTS (
                   SELECT 1
                   FROM pg_catalog.pg_rewrite AS relation_rule
                   WHERE relation_rule.ev_class = relation.oid
               ),
               EXISTS (
                   SELECT 1
                   FROM pg_catalog.pg_trigger AS relation_trigger
                   WHERE relation_trigger.tgrelid = relation.oid
               ),
               EXISTS (
                   SELECT 1
                   FROM pg_catalog.pg_index AS relation_index
                   WHERE relation_index.indrelid = relation.oid
               ),
               relation.relnatts,
               relation.relchecks,
               relation.relreplident,
               relation.reltablespace,
               relation.reloptions,
               access_method.amname::text,
               relation.reltoastrelid <> 0,
               relation.relrewrite
        FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = relation.relowner
        JOIN pg_catalog.pg_am AS access_method
             ON access_method.oid = relation.relam
        WHERE relation.oid = %s
        """,
        (oid,),
    ).fetchone()
    if tuple(relation or ()) != (
        "r",
        "p",
        spec.schema_owner,
        False,
        False,
        False,
        False,
        True,
        True,
        10,
        10,
        "d",
        0,
        None,
        "heap",
        True,
        0,
    ):
        raise MigrationDirtyError("migration ledger relation posture differs")

    columns = connection.execute(
        """
        SELECT attribute.attnum,
               attribute.attname::text,
               pg_catalog.format_type(attribute.atttypid, attribute.atttypmod),
               attribute.attnotnull,
               CASE WHEN attribute.attcollation = 0 THEN NULL
                    ELSE namespace.nspname::text || '.' || collation_entry.collname::text
               END,
               pg_catalog.pg_get_expr(default_value.adbin, default_value.adrelid),
               attribute.attidentity,
               attribute.attgenerated
        FROM pg_catalog.pg_attribute AS attribute
        LEFT JOIN pg_catalog.pg_attrdef AS default_value
               ON default_value.adrelid = attribute.attrelid
              AND default_value.adnum = attribute.attnum
        LEFT JOIN pg_catalog.pg_collation AS collation_entry
               ON collation_entry.oid = attribute.attcollation
        LEFT JOIN pg_catalog.pg_namespace AS namespace
               ON namespace.oid = collation_entry.collnamespace
        WHERE attribute.attrelid = %s
          AND attribute.attnum > 0
          AND NOT attribute.attisdropped
        ORDER BY attribute.attnum
        """,
        (oid,),
    ).fetchall()
    expected_columns = [
        (1, "version", "integer", True, None, None, "", ""),
        (2, "filename", "text", True, "pg_catalog.C", None, "", ""),
        (3, "source_sha256", "text", True, "pg_catalog.C", None, "", ""),
        (4, "source_byte_length", "bigint", True, None, None, "", ""),
        (
            5,
            "applied_prefix_digest",
            "text",
            True,
            "pg_catalog.C",
            None,
            "",
            "",
        ),
        (6, "service_identity", "text", True, "pg_catalog.C", None, "", ""),
        (
            7,
            "provisioning_spec_digest",
            "text",
            True,
            "pg_catalog.C",
            None,
            "",
            "",
        ),
        (8, "release_identity", "text", True, "pg_catalog.C", None, "", ""),
        (9, "execution_id", "uuid", True, None, None, "", ""),
        (
            10,
            "applied_at",
            "timestamp with time zone",
            True,
            None,
            "clock_timestamp()",
            "",
            "",
        ),
    ]
    if [tuple(row) for row in columns] != expected_columns:
        raise MigrationDirtyError("migration ledger columns differ")

    constraints = connection.execute(
        """
        SELECT constraint_name.conname::text,
               constraint_name.contype,
               constraint_name.condeferrable,
               constraint_name.condeferred,
               constraint_name.convalidated,
               constraint_name.conkey::text,
               constraint_name.connoinherit,
               pg_catalog.pg_get_constraintdef(constraint_name.oid, false)
        FROM pg_catalog.pg_constraint AS constraint_name
        WHERE constraint_name.conrelid = %s
        ORDER BY constraint_name.conname
        """,
        (oid,),
    ).fetchall()
    expected_constraints = {
        (
            "schema_migration_pkey",
            "p",
            False,
            False,
            True,
            "{1}",
            True,
            "PRIMARY KEY (version)",
        ),
        (
            "schema_migration_filename_key",
            "u",
            False,
            False,
            True,
            "{2}",
            True,
            "UNIQUE (filename)",
        ),
        (
            "schema_migration_version_check",
            "c",
            False,
            False,
            True,
            "{1}",
            False,
            "CHECK (((version >= 1) AND (version <= 9999)))",
        ),
        (
            "schema_migration_filename_check",
            "c",
            False,
            False,
            True,
            "{2,1}",
            False,
            "CHECK (((filename ~ "
            "'^[0-9]{4}_[a-z][a-z0-9_]*[.]sql$'::text) AND "
            '("substring"(filename, 1, 4) = '
            "lpad((version)::text, 4, '0'::text))))",
        ),
        (
            "schema_migration_source_sha256_check",
            "c",
            False,
            False,
            True,
            "{3}",
            False,
            "CHECK ((source_sha256 ~ '^sha256:[0-9a-f]{64}$'::text))",
        ),
        (
            "schema_migration_source_length_check",
            "c",
            False,
            False,
            True,
            "{4}",
            False,
            "CHECK ((source_byte_length > 0))",
        ),
        (
            "schema_migration_prefix_digest_check",
            "c",
            False,
            False,
            True,
            "{5}",
            False,
            "CHECK ((applied_prefix_digest ~ "
            "'^sha256:[0-9a-f]{64}$'::text))",
        ),
        (
            "schema_migration_service_check",
            "c",
            False,
            False,
            True,
            "{6}",
            False,
            "CHECK ((service_identity = "
            f"'{spec.migration_service.identity}'::text))",
        ),
        (
            "schema_migration_provisioning_digest_check",
            "c",
            False,
            False,
            True,
            "{7}",
            False,
            "CHECK ((provisioning_spec_digest ~ "
            "'^sha256:[0-9a-f]{64}$'::text))",
        ),
        (
            "schema_migration_release_check",
            "c",
            False,
            False,
            True,
            "{8}",
            False,
            "CHECK ((release_identity ~ '^[!-~]{1,128}$'::text))",
        ),
        (
            "schema_migration_execution_id_check",
            "c",
            False,
            False,
            True,
            "{9}",
            False,
            "CHECK ((execution_id <> "
            "'00000000-0000-0000-0000-000000000000'::uuid))",
        ),
        (
            "schema_migration_applied_at_check",
            "c",
            False,
            False,
            True,
            "{10}",
            False,
            "CHECK (((applied_at <> 'infinity'::timestamp with time zone) "
            "AND (applied_at <> '-infinity'::timestamp with time zone)))",
        ),
    }
    if {tuple(row) for row in constraints} != expected_constraints:
        raise MigrationDirtyError("migration ledger constraints differ")

    indexes = connection.execute(
        """
        SELECT index_relation.relname::text,
               index_owner.rolname::text,
               index_relation.relkind,
               index_relation.relpersistence,
               access_method.amname::text,
               index_relation.reltablespace,
               index_relation.reloptions::text,
               index_entry.indisprimary,
               index_entry.indisunique,
               index_entry.indisvalid,
               index_entry.indisready,
               index_entry.indislive,
               index_entry.indisexclusion,
               index_entry.indimmediate,
               index_entry.indisclustered,
               index_entry.indisreplident,
               index_entry.indnullsnotdistinct,
               index_entry.indnatts,
               index_entry.indnkeyatts,
               index_entry.indkey::text,
               CASE WHEN index_entry.indcollation[0] = 0 THEN NULL
                    ELSE collation_namespace.nspname::text || '.' ||
                         collation_entry.collname::text
               END,
               operator_namespace.nspname::text || '.' ||
                   operator_class.opcname::text,
               index_entry.indoption::text,
               index_entry.indexprs IS NULL,
               index_entry.indpred IS NULL,
               pg_catalog.pg_get_indexdef(index_entry.indexrelid, 0, false)
        FROM pg_catalog.pg_index AS index_entry
        JOIN pg_catalog.pg_class AS index_relation
             ON index_relation.oid = index_entry.indexrelid
        JOIN pg_catalog.pg_roles AS index_owner
             ON index_owner.oid = index_relation.relowner
        JOIN pg_catalog.pg_am AS access_method
             ON access_method.oid = index_relation.relam
        LEFT JOIN pg_catalog.pg_collation AS collation_entry
             ON collation_entry.oid = index_entry.indcollation[0]
        LEFT JOIN pg_catalog.pg_namespace AS collation_namespace
             ON collation_namespace.oid = collation_entry.collnamespace
        JOIN pg_catalog.pg_opclass AS operator_class
             ON operator_class.oid = index_entry.indclass[0]
        JOIN pg_catalog.pg_namespace AS operator_namespace
             ON operator_namespace.oid = operator_class.opcnamespace
        WHERE index_entry.indrelid = %s
        ORDER BY index_relation.relname
        """,
        (oid,),
    ).fetchall()
    if {tuple(row) for row in indexes} != {
        (
            "schema_migration_filename_key",
            spec.schema_owner,
            "i",
            "p",
            "btree",
            0,
            None,
            False,
            True,
            True,
            True,
            True,
            False,
            True,
            False,
            False,
            False,
            1,
            1,
            "2",
            "pg_catalog.C",
            "pg_catalog.text_ops",
            "0",
            True,
            True,
            "CREATE UNIQUE INDEX schema_migration_filename_key ON "
            f"{spec.schema_name}.{spec.migration_service.ledger_name} "
            "USING btree (filename)",
        ),
        (
            "schema_migration_pkey",
            spec.schema_owner,
            "i",
            "p",
            "btree",
            0,
            None,
            True,
            True,
            True,
            True,
            True,
            False,
            True,
            False,
            False,
            False,
            1,
            1,
            "1",
            None,
            "pg_catalog.int4_ops",
            "0",
            True,
            True,
            "CREATE UNIQUE INDEX schema_migration_pkey ON "
            f"{spec.schema_name}.{spec.migration_service.ledger_name} "
            "USING btree (version)",
        ),
    }:
        raise MigrationDirtyError("migration ledger indexes differ")

    triggers = connection.execute(
        """
        SELECT trigger_entry.tgname::text,
               pg_catalog.pg_get_triggerdef(trigger_entry.oid, false),
               trigger_entry.tgtype,
               trigger_entry.tgenabled,
               trigger_entry.tgisinternal,
               function_name.proname::text,
               function_namespace.nspname::text,
               trigger_entry.tgparentid,
               trigger_entry.tgconstrrelid,
               trigger_entry.tgconstrindid,
               trigger_entry.tgconstraint,
               trigger_entry.tgdeferrable,
               trigger_entry.tginitdeferred,
               trigger_entry.tgnargs,
               trigger_entry.tgattr::text,
               pg_catalog.encode(trigger_entry.tgargs, 'hex'),
               trigger_entry.tgqual,
               trigger_entry.tgoldtable,
               trigger_entry.tgnewtable
        FROM pg_catalog.pg_trigger AS trigger_entry
        JOIN pg_catalog.pg_proc AS function_name
             ON function_name.oid = trigger_entry.tgfoid
        JOIN pg_catalog.pg_namespace AS function_namespace
             ON function_namespace.oid = function_name.pronamespace
        WHERE trigger_entry.tgrelid = %s
          AND NOT trigger_entry.tgisinternal
        ORDER BY trigger_entry.tgname
        """,
        (oid,),
    ).fetchall()
    if {tuple(row) for row in triggers} != {
        (
            _UPDATE_DELETE_TRIGGER,
            "CREATE TRIGGER schema_migration_reject_update_delete "
            f"BEFORE DELETE OR UPDATE ON {spec.schema_name}."
            f"{spec.migration_service.ledger_name} FOR EACH ROW "
            f"EXECUTE FUNCTION {spec.schema_name}."
            f"{_LEDGER_GUARD_FUNCTION}()",
            27,
            "O",
            False,
            _LEDGER_GUARD_FUNCTION,
            spec.schema_name,
            0,
            0,
            0,
            0,
            False,
            False,
            0,
            "",
            "",
            None,
            None,
            None,
        ),
        (
            _TRUNCATE_TRIGGER,
            "CREATE TRIGGER schema_migration_reject_truncate "
            f"BEFORE TRUNCATE ON {spec.schema_name}."
            f"{spec.migration_service.ledger_name} FOR EACH STATEMENT "
            f"EXECUTE FUNCTION {spec.schema_name}."
            f"{_LEDGER_GUARD_FUNCTION}()",
            34,
            "O",
            False,
            _LEDGER_GUARD_FUNCTION,
            spec.schema_name,
            0,
            0,
            0,
            0,
            False,
            False,
            0,
            "",
            "",
            None,
            None,
            None,
        ),
    }:
        raise MigrationDirtyError("migration ledger triggers differ")

    guard = connection.execute(
        """
        SELECT owner.rolname::text,
               pg_catalog.pg_get_function_identity_arguments(routine.oid),
               language.lanname::text,
               routine.prokind,
               routine.prosecdef,
               routine.proleakproof,
               routine.proisstrict,
               routine.provolatile,
               routine.proparallel,
               routine.proretset,
               routine.prorettype = 'pg_catalog.trigger'::pg_catalog.regtype,
               routine.prosrc,
               COALESCE(routine.proconfig, ARRAY[]::text[])
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
             ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
        WHERE namespace.nspname = %s
          AND routine.proname = %s
        """,
        (spec.schema_name, _LEDGER_GUARD_FUNCTION),
    ).fetchall()
    if len(guard) != 1 or tuple(guard[0]) != (
        spec.schema_owner,
        "",
        "plpgsql",
        "f",
        False,
        False,
        False,
        "v",
        "u",
        False,
        True,
        _LEDGER_GUARD_SOURCE,
        ["search_path=pg_catalog, pg_temp"],
    ):
        raise MigrationDirtyError("migration ledger guard differs")

    guard_acl = connection.execute(
        """
        SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
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
          AND routine.proname = %s
        """,
        (spec.schema_name, _LEDGER_GUARD_FUNCTION),
    ).fetchall()
    if {tuple(row) for row in guard_acl} != {
        (spec.schema_owner, spec.schema_owner, "EXECUTE", False)
    }:
        raise MigrationDirtyError("migration ledger guard ACL differs")

    expected_relation_acl = {
        (spec.schema_owner, spec.schema_owner, privilege, False)
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
    if _relation_acl(connection, oid) != expected_relation_acl:
        raise MigrationDirtyError("migration ledger relation ACL differs")

    column_acls = connection.execute(
        """
        SELECT attribute.attname::text,
               CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                    ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
               pg_catalog.pg_get_userbyid(acl.grantor),
               acl.privilege_type,
               acl.is_grantable
        FROM pg_catalog.pg_attribute AS attribute
        CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) AS acl
        WHERE attribute.attrelid = %s
        ORDER BY 1, 2, 3, 4, 5
        """,
        (oid,),
    ).fetchall()
    readiness_columns = {
        "version",
        "filename",
        "source_sha256",
        "source_byte_length",
        "applied_prefix_digest",
        "service_identity",
        "provisioning_spec_digest",
    }
    if {tuple(row) for row in column_acls} != {
        (column, spec.readiness_role_name, spec.schema_owner, "SELECT", False)
        for column in readiness_columns
    }:
        raise MigrationDirtyError("migration ledger column ACL differs")


def _history_version(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    migration_set: MigrationSet,
    *,
    allow_empty: bool,
) -> _HistoryObservation:
    rows = connection.execute(
        sql.SQL(
            "SELECT version, filename, source_sha256, source_byte_length, "
            "applied_prefix_digest, service_identity, "
            "provisioning_spec_digest, release_identity, execution_id, "
            "applied_at FROM {} ORDER BY version"
        ).format(
            sql.Identifier(
                spec.schema_name,
                spec.migration_service.ledger_name,
            )
        )
    ).fetchall()
    if not rows:
        if allow_empty:
            return _HistoryObservation(0, None)
        raise MigrationDirtyError("existing migration ledger is empty")
    if len(rows) > len(migration_set.migrations):
        raise MigrationDirtyError("migration history is newer than the local set")
    for expected_version, row in enumerate(rows, start=1):
        migration = migration_set.migrations[expected_version - 1]
        if row[0] != expected_version or tuple(row[1:7]) != (
            migration.filename,
            migration.source_sha256,
            migration.byte_length,
            migration_set.prefix_digest(expected_version),
            spec.migration_service.identity,
            spec.digest,
        ):
            raise MigrationDirtyError("migration history is not the exact local prefix")
        if _RELEASE_IDENTITY.fullmatch(row[7] or "") is None:
            raise MigrationDirtyError("migration history release identity is malformed")
        if not isinstance(row[8], UUID) or row[8].int == 0:
            raise MigrationDirtyError("migration history execution identity is malformed")
        if not isinstance(row[9], datetime) or row[9].tzinfo is None:
            raise MigrationDirtyError("migration history diagnostic time is malformed")
    return _HistoryObservation(len(rows), rows[-1][8])


def _verify_final_service_structure(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    migration_set: MigrationSet,
) -> None:
    """Require the migration-owned catalog verifier at the exact final head."""

    try:
        verify_catalog_identity(connection, spec.migration_service)
    except CatalogIdentityError as exc:
        raise MigrationDirtyError(
            "migration-owned catalog verifier identity differs at the final head"
        ) from exc
    try:
        if spec is TENANT_PROVISIONING_SPEC:
            row = connection.execute(
                "SELECT * FROM ofarm.verify_tenant_structure()"
            ).fetchone()
            exact_tail = (
                spec.digest,
                spec.migration_service.identity,
                len(migration_set.migrations),
                migration_set.digest,
                len(migration_set.migrations),
                False,
            )
            if (
                row is None
                or len(row) != 11
                or row[0] is not True
                or row[1] != TENANT_CONTEXT_CONTRACT.digest
                or row[2] != 0
                or not isinstance(row[3], str)
                or _DIGEST.fullmatch(row[3]) is None
                or not isinstance(row[4], str)
                or _DIGEST.fullmatch(row[4]) is None
                or tuple(row[5:11]) != exact_tail
            ):
                raise MigrationDirtyError(
                    "tenant structural verifier differs at the final head"
                )
        elif spec is SECURITY_AUDIT_PROVISIONING_SPEC:
            row = connection.execute(
                "SELECT * FROM ofarm_security.verify_security_audit_structure()"
            ).fetchone()
            if tuple(row or ()) != (True, 0, False):
                raise MigrationDirtyError(
                    "security-audit structural verifier differs at the final head"
                )
        else:  # pragma: no cover - closed by _require_fixed_pair
            raise MigrationInputError("structural verifier service is not fixed")
    except MigrationError:
        raise
    except psycopg.Error as exc:
        raise MigrationDirtyError(
            "migration-owned structural verifier is unreadable"
        ) from exc


def _insert_ledger_row(
    connection: psycopg.Connection,
    spec: ProvisioningSpec,
    migration_set: MigrationSet,
    migration: Migration,
    release_identity: str,
    execution_id: UUID,
) -> None:
    connection.execute(
        sql.SQL(
            "INSERT INTO {} ("
            "version, filename, source_sha256, source_byte_length, "
            "applied_prefix_digest, service_identity, "
            "provisioning_spec_digest, release_identity, execution_id"
            ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        ).format(
            sql.Identifier(
                spec.schema_name,
                spec.migration_service.ledger_name,
            )
        ),
        (
            migration.version,
            migration.filename,
            migration.source_sha256,
            migration.byte_length,
            migration_set.prefix_digest(migration.version),
            spec.migration_service.identity,
            spec.digest,
            release_identity,
            execution_id,
        ),
    )


def _commit(
    connection: psycopg.Connection,
    migration: Migration,
    execution_id: UUID,
) -> None:
    try:
        connection.commit()
    except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
        raise MigrationOutcomeUnknown(
            migration.version,
            migration.filename,
            execution_id,
        ) from exc
    except psycopg.Error as exc:
        raise MigrationExecutionError(
            migration.version,
            migration.filename,
            "commit was rejected",
        ) from exc
    except BaseException as exc:
        raise MigrationOutcomeUnknown(
            migration.version,
            migration.filename,
            execution_id,
        ) from exc


def _finish_verified_noop(connection: psycopg.Connection) -> None:
    """Release a read-only verification transaction without a write outcome."""

    try:
        connection.rollback()
    except psycopg.Error as exc:
        raise MigrationTargetError(
            "verified migration no-op could not close its transaction"
        ) from exc


def _migrate_service(
    *,
    admin_dsn: str,
    migrator_dsn: str,
    spec: ProvisioningSpec,
    migration_set: MigrationSet,
    release_identity: str,
    execution_id: UUID,
    verify_final_structure: bool,
) -> MigrationRunReport:
    """Shared executor after the public or synthetic preflight boundary."""

    _require_fixed_pair(spec, migration_set)
    release_identity = _release_identity(release_identity)
    execution_id = _execution_identity(execution_id)
    source_texts = _preflight_sources(migration_set)
    if not isinstance(admin_dsn, str) or not admin_dsn:
        raise MigrationInputError("admin_dsn must be non-empty")
    if not isinstance(migrator_dsn, str) or not migrator_dsn:
        raise MigrationInputError("migrator_dsn must be non-empty")

    infrastructure = _observe_infrastructure(admin_dsn, spec)
    try:
        connection = psycopg.connect(migrator_dsn, autocommit=True)
    except psycopg.Error as exc:
        raise MigrationTargetError("migrator route is unavailable") from exc

    applied: list[int] = []
    previous_version: int | None = None
    observed_head_execution_id: UUID | None = None
    identity: _TargetIdentity
    with connection:
        identity = _target_identity(connection, infrastructure)
        while True:
            _begin_and_lock(connection, spec)
            try:
                _set_owner_role(connection, spec)
                boundary_differences = _locked_boundary_differences(
                    connection, spec
                )
                if boundary_differences:
                    raise MigrationDirtyError(
                        "locked provisioning/application boundary differs: "
                        + "; ".join(sorted(set(boundary_differences)))
                    )
                ledger_present = _ledger_oid(connection, spec) is not None
                if not ledger_present:
                    _require_fresh_catalog(connection, spec)
                if ledger_present:
                    _verify_ledger_contract(connection, spec)
                    history = _history_version(
                        connection,
                        spec,
                        migration_set,
                        allow_empty=False,
                    )
                    observed_version = history.version
                    observed_head_execution_id = history.head_execution_id
                else:
                    observed_version = 0
                    observed_head_execution_id = None
                if previous_version is None:
                    previous_version = observed_version
                if observed_version == len(migration_set.migrations):
                    if verify_final_structure:
                        _verify_final_service_structure(
                            connection,
                            spec,
                            migration_set,
                        )
                    _finish_verified_noop(connection)
                    break

                migration = migration_set.migrations[observed_version]
                source_text = source_texts[observed_version]
                try:
                    connection.execute(source_text)
                    if connection.info.transaction_status != TransactionStatus.INTRANS:
                        raise MigrationExecutionError(
                            migration.version,
                            migration.filename,
                            "migration escaped its transaction",
                        )
                    if observed_version == 0:
                        _consume_tenant_initial_owner_sealer(
                            connection,
                            spec,
                            migration,
                        )
                    if (
                        spec == TENANT_PROVISIONING_SPEC
                        and observed_version == 7
                        and migration.version == 8
                        and migration.filename
                        == _TENANT_SELECTION_ACTIVATION_MIGRATION_FILENAME
                    ):
                        try:
                            require_authoritative_migration_set(migration_set)
                        except MigrationSetError as exc:
                            raise MigrationInputError(str(exc)) from exc
                        post_boundary = (
                            _locked_tenant_v8_post_source_boundary_differences(
                                connection,
                                spec,
                            )
                        )
                    else:
                        post_boundary = _locked_boundary_differences(
                            connection,
                            spec,
                        )
                    if post_boundary:
                        raise MigrationDirtyError(
                            "migration widened the provisioning boundary"
                        )
                    _verify_ledger_contract(connection, spec)
                    unchanged_history = _history_version(
                        connection,
                        spec,
                        migration_set,
                        allow_empty=observed_version == 0,
                    )
                    if unchanged_history.version != observed_version:
                        raise MigrationDirtyError(
                            "migration changed history before its runner append"
                        )
                    _insert_ledger_row(
                        connection,
                        spec,
                        migration_set,
                        migration,
                        release_identity,
                        execution_id,
                    )
                    appended_history = _history_version(
                        connection,
                        spec,
                        migration_set,
                        allow_empty=False,
                    )
                    if appended_history.version != migration.version:
                        raise MigrationDirtyError(
                            "migration ledger append was not exact"
                        )
                    observed_head_execution_id = \
                        appended_history.head_execution_id
                    if (
                        spec.tenant_binding_selection_control_admission_sealer
                        is not None
                        and migration.version == 5
                    ):
                        _authenticate_tenant_binding_selection_control_admission_row(
                            connection,
                            spec,
                            migration_set,
                            migration,
                            release_identity,
                            execution_id,
                        )
                        _consume_tenant_binding_selection_control_admission_sealer(
                            connection,
                            spec,
                            migration,
                        )
                        admitted_boundary = _locked_boundary_differences(
                            connection,
                            spec,
                        )
                        if admitted_boundary:
                            raise MigrationDirtyError(
                                "tenant binding selection-control admission "
                                "boundary differs"
                            )
                    if (
                        spec.tenant_current_context_selection_owner_admission_sealer
                        is not None
                        and migration.version == 6
                    ):
                        _authenticate_tenant_current_context_selection_owner_admission_row(
                            connection,
                            spec,
                            migration_set,
                            migration,
                            release_identity,
                            execution_id,
                        )
                        _consume_tenant_current_context_selection_owner_admission_sealer(
                            connection,
                            spec,
                            migration,
                        )
                        _authenticate_tenant_current_context_selection_owner_admission_row(
                            connection,
                            spec,
                            migration_set,
                            migration,
                            release_identity,
                            execution_id,
                        )
                        admitted_boundary = _locked_boundary_differences(
                            connection,
                            spec,
                        )
                        if admitted_boundary:
                            raise MigrationDirtyError(
                                "tenant current-context selection-owner admission "
                                "boundary differs"
                            )
                    if (
                        spec.tenant_write_lock_selection_owner_admission_sealer
                        is not None
                        and migration.version == 7
                    ):
                        _authenticate_tenant_write_lock_selection_owner_admission_row(
                            connection,
                            spec,
                            migration_set,
                            migration,
                            release_identity,
                            execution_id,
                        )
                        _consume_tenant_write_lock_selection_owner_admission_sealer(
                            connection,
                            spec,
                            migration,
                        )
                        _authenticate_tenant_write_lock_selection_owner_admission_row(
                            connection,
                            spec,
                            migration_set,
                            migration,
                            release_identity,
                            execution_id,
                        )
                        admitted_boundary = _locked_boundary_differences(
                            connection,
                            spec,
                        )
                        if admitted_boundary:
                            raise MigrationDirtyError(
                                "tenant write-lock selection-owner admission "
                                "boundary differs"
                            )
                    if (
                        verify_final_structure
                        and migration.version == len(migration_set.migrations)
                    ):
                        _verify_final_service_structure(
                            connection,
                            spec,
                            migration_set,
                        )
                except (MigrationDirtyError, MigrationExecutionError):
                    raise
                except psycopg.Error as exc:
                    raise MigrationExecutionError(
                        migration.version,
                        migration.filename,
                        exc.diag.message_primary or "database execution failed",
                    ) from exc
                _commit(connection, migration, execution_id)
                applied.append(migration.version)
            except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
                if connection.info.transaction_status != TransactionStatus.IDLE:
                    _rollback_quietly(connection)
                raise MigrationTargetError(
                    "locked migration target became unavailable"
                ) from exc
            except psycopg.Error as exc:
                if connection.info.transaction_status != TransactionStatus.IDLE:
                    _rollback_quietly(connection)
                raise MigrationDirtyError(
                    "locked migration catalog or ledger is unreadable"
                ) from exc
            except BaseException:
                if connection.info.transaction_status != TransactionStatus.IDLE:
                    _rollback_quietly(connection)
                raise

    if previous_version is None:
        raise MigrationTargetError("migration phase was not observed")
    if observed_head_execution_id is None:
        raise MigrationDirtyError("migration history has no execution identity")
    return MigrationRunReport(
        service_identity=spec.migration_service.identity,
        provisioning_spec_digest=spec.digest,
        migration_set_digest=migration_set.digest,
        database_name=identity.database_name,
        system_identifier=identity.system_identifier,
        server_version_num=identity.server_version_num,
        previous_version=previous_version,
        final_version=len(migration_set.migrations),
        applied_versions=tuple(applied),
        execution_id=execution_id,
        observed_head_execution_id=observed_head_execution_id,
    )


def migrate_service(
    *,
    admin_dsn: str,
    migrator_dsn: str,
    spec: ProvisioningSpec,
    migration_set: MigrationSet,
    release_identity: str,
    execution_id: UUID,
) -> MigrationRunReport:
    """Apply only the literal authoritative release migration history."""

    _require_fixed_pair(spec, migration_set)
    try:
        require_authoritative_migration_set(migration_set)
    except MigrationSetError as exc:
        raise MigrationInputError(str(exc)) from exc
    return _migrate_service(
        admin_dsn=admin_dsn,
        migrator_dsn=migrator_dsn,
        spec=spec,
        migration_set=migration_set,
        release_identity=release_identity,
        execution_id=execution_id,
        verify_final_structure=True,
    )


def _migrate_service_for_testing(
    *,
    admin_dsn: str,
    migrator_dsn: str,
    spec: ProvisioningSpec,
    migration_set: MigrationSet,
    release_identity: str,
    execution_id: UUID,
) -> MigrationRunReport:
    """Exercise runner mechanics with synthetic migration sets in tests only."""

    _require_fixed_pair(spec, migration_set)
    if (
        spec == TENANT_PROVISIONING_SPEC
        and len(migration_set.migrations) >= 8
        and migration_set.migrations[7].version == 8
        and migration_set.migrations[7].filename
        == _TENANT_SELECTION_ACTIVATION_MIGRATION_FILENAME
    ):
        raise MigrationInputError(
            "test migration executor cannot execute tenant migration 0008"
        )
    return _migrate_service(
        admin_dsn=admin_dsn,
        migrator_dsn=migrator_dsn,
        spec=spec,
        migration_set=migration_set,
        release_identity=release_identity,
        execution_id=execution_id,
        verify_final_structure=False,
    )
