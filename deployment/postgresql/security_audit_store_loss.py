"""One-shot reconstruction of one provably fresh security-audit store.

The operation creates and migrates only the fixed audit service, holds one
server-local witness across every authoritative connection, appends one
unknown-count gap, and returns only after a bounded final observation.
"""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol, Self, cast
from uuid import UUID

import psycopg

from deployment.postgresql.audit_contract import (
    EVENT_FORMAT_IDENTITY,
    REDACTION_POLICY_IDENTITY,
    RETENTION_POLICY_IDENTITY,
    RETENTION_SECONDS,
)
from deployment.postgresql.migration_runner import (
    MigrationRunReport,
    _migrate_security_audit_store_loss,
)
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    MigrationSet,
    load_authoritative_migration_set,
)
from deployment.postgresql.provisioning import (
    ProvisioningReport,
    ProvisioningTargetError,
    _StoreLossLiveWitness,
    _assert_security_audit_store_loss_witness,
    _provision_security_audit_store_loss,
)
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
)
from deployment.postgresql.version_policy import (
    SUPPORTED_POSTGRESQL_SERVER_VERSION,
    SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
)


STORE_LOSS_REPORT_SCHEMA = (
    "ofarm.security-audit-store-loss-recovery-report.v1"
)
STORE_LOSS_CONNECT_TIMEOUT_SECONDS = 5
STORE_LOSS_LONG_OPTIONS = (
    "-c statement_timeout=300000 "
    "-c lock_timeout=5000 "
    "-c TimeZone=UTC "
    "-c DateStyle=ISO,MDY "
    "-c synchronous_commit=on"
)
STORE_LOSS_SHORT_OPTIONS = (
    "-c statement_timeout=2000 "
    "-c lock_timeout=250 "
    "-c TimeZone=UTC "
    "-c DateStyle=ISO,MDY "
    "-c synchronous_commit=on"
)
WITNESS_IDENTITY_SQL = """
SELECT SESSION_USER::text,
       CURRENT_USER::text,
       pg_catalog.current_database()::text,
       observed_database.oid::bigint,
       observed_role.rolsuper,
       pg_catalog.current_setting('server_version_num')::integer,
       pg_catalog.current_setting('server_version')::text,
       control.system_identifier::text,
       pg_catalog.pg_is_in_recovery(),
       pg_catalog.current_setting('transaction_read_only')::text,
       pg_catalog.pg_backend_pid()
FROM pg_catalog.pg_roles AS observed_role
JOIN pg_catalog.pg_database AS observed_database
  ON observed_database.datname = pg_catalog.current_database()
CROSS JOIN pg_catalog.pg_control_system() AS control
WHERE observed_role.rolname = CURRENT_USER
"""
WITNESS_BIGINT_LOCK_SQL = (
    "SELECT pg_catalog.pg_try_advisory_lock(%s::bigint)"
)
WITNESS_INTEGER_PAIR_LOCK_SQL = (
    "SELECT pg_catalog.pg_try_advisory_lock(%s::integer, %s::integer)"
)
FRESH_STATE_SQL = """
SELECT (SELECT pg_catalog.count(*)::bigint
        FROM ofarm_security.operational_security_event),
       (SELECT pg_catalog.count(*)::bigint
        FROM ofarm_security.operational_security_quota_bucket),
       (SELECT pg_catalog.count(*)::bigint
        FROM ofarm_security.operational_security_quota_high_water),
       (SELECT pg_catalog.count(*)::bigint
        FROM ofarm_security.operational_security_event_identity_lock),
       (SELECT pg_catalog.min(lock_slot)::integer
        FROM ofarm_security.operational_security_event_identity_lock),
       (SELECT pg_catalog.max(lock_slot)::integer
        FROM ofarm_security.operational_security_event_identity_lock),
       (SELECT pg_catalog.count(*)::bigint
        FROM ofarm_security.operational_security_overflow_identity_receipt),
       (SELECT pg_catalog.count(*)::bigint
        FROM ofarm_security.operational_security_overflow_identity_receipt
        WHERE event_id IS NOT NULL
           OR append_input_fingerprint IS NOT NULL
           OR bucket_start IS NOT NULL
           OR purge_after IS NOT NULL),
       (SELECT pg_catalog.count(DISTINCT (producer, component))::integer
        FROM ofarm_security.operational_security_overflow_identity_receipt),
       (SELECT pg_catalog.min(lock_slot)::integer
        FROM ofarm_security.operational_security_overflow_identity_receipt),
       (SELECT pg_catalog.max(lock_slot)::integer
        FROM ofarm_security.operational_security_overflow_identity_receipt),
       sequence_state.last_value,
       sequence_state.is_called
FROM ofarm_security.operational_security_access_clock_high_water AS sequence_state
"""
LEDGER_SQL = """
SELECT version,
       filename,
       source_sha256,
       source_byte_length,
       applied_prefix_digest,
       service_identity,
       provisioning_spec_digest,
       release_identity,
       execution_id,
       applied_at
FROM ofarm_security.schema_migration
ORDER BY version
LIMIT %s
"""
CLOCK_SQL = "SELECT pg_catalog.clock_timestamp()"
APPEND_GAP_SQL = """
SELECT *
FROM ofarm_security.append_audit_gap(%s, %s, 0, true)
"""
FINAL_STATE_SQL = """
WITH event_count AS (
    SELECT pg_catalog.count(*)::bigint AS value
    FROM ofarm_security.operational_security_event
),
sole_event AS (
    SELECT event.*
    FROM ofarm_security.operational_security_event AS event
    WHERE (SELECT value FROM event_count) = 1
    LIMIT 1
),
inventory AS (
    SELECT (SELECT pg_catalog.count(*)::bigint
            FROM ofarm_security.operational_security_quota_bucket)
               AS quota_count,
           (SELECT pg_catalog.count(*)::bigint
            FROM ofarm_security.operational_security_quota_high_water)
               AS high_water_count,
           (SELECT pg_catalog.count(*)::bigint
            FROM ofarm_security.operational_security_overflow_identity_receipt)
               AS receipt_count,
           (SELECT pg_catalog.count(*)::bigint
            FROM ofarm_security.operational_security_overflow_identity_receipt
            WHERE event_id IS NOT NULL
               OR append_input_fingerprint IS NOT NULL
               OR bucket_start IS NOT NULL
               OR purge_after IS NOT NULL)
               AS used_receipt_count
)
SELECT event_count.value,
       sole_event.event_id,
       sole_event.observed_at,
       sole_event.purge_after,
       sole_event.event_kind,
       sole_event.producer,
       sole_event.component,
       sole_event.interval_start,
       sole_event.interval_end,
       sole_event.interval_event_count,
       sole_event.interval_count_unknown,
       sole_event.event_format_identity,
       sole_event.redaction_policy_identity,
       sole_event.retention_policy_identity,
       pg_catalog.octet_length(sole_event.append_input_fingerprint),
       (sole_event.reason IS NULL
        AND sole_event.correlation_hmac_domain IS NULL
        AND sole_event.correlation_hmac_key_version IS NULL
        AND sole_event.correlation_hmac_value IS NULL
        AND sole_event.access_purpose IS NULL
        AND sole_event.access_function_identity IS NULL
        AND sole_event.access_data_cut IS NULL
        AND sole_event.access_visibility_snapshot IS NULL
        AND sole_event.access_cursor_observed_at IS NULL
        AND sole_event.access_cursor_event_id IS NULL
        AND sole_event.access_max_rows IS NULL
        AND sole_event.access_max_bytes IS NULL
        AND sole_event.access_expires_at IS NULL
        AND sole_event.retention_cutoff IS NULL
        AND sole_event.retention_deleted_count IS NULL
        AND sole_event.affected_producer IS NULL
        AND sole_event.affected_component IS NULL),
       inventory.quota_count,
       inventory.high_water_count,
       inventory.receipt_count,
       inventory.used_receipt_count,
       sequence_state.last_value,
       sequence_state.is_called
FROM event_count
CROSS JOIN inventory
CROSS JOIN ofarm_security.operational_security_access_clock_high_water
    AS sequence_state
LEFT JOIN sole_event ON true
"""


_RELEASE_IDENTITY = re.compile(r"[!-~]{1,128}")
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_AUDIT_DATABASE = SECURITY_AUDIT_PROVISIONING_SPEC.database_name
_EXPECTED_FRESH_STATE = (0, 0, 0, 256, 0, 255, 512, 0, 2, 0, 255, 0, False)
_RETENTION_INTERVAL = timedelta(seconds=RETENTION_SECONDS)


class SecurityAuditStoreLossError(RuntimeError):
    """Base class for the closed recovery outcomes."""


class SecurityAuditStoreLossInputError(SecurityAuditStoreLossError):
    """The request or secret carrier was refused before PostgreSQL work."""


class SecurityAuditStoreLossRefused(SecurityAuditStoreLossError):
    """Recovery did not succeed and the replacement remains quarantined."""


class SecurityAuditStoreLossOutcomeUnknown(SecurityAuditStoreLossError):
    """The one append may commit, but final state could not prove its outcome."""


@dataclass(frozen=True, slots=True)
class StoreLossRecoveryRequest:
    loss_start: datetime
    release_identity: str
    execution_id: UUID


@dataclass(frozen=True, slots=True, repr=False)
class StoreLossRecoverySecrets:
    admin_dsn: str
    migrator_dsn: str
    control_dsn: str
    login_passwords: tuple[tuple[str, str], ...]

    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return NotImplemented
        other_carrier = cast(Self, other)
        return (
            self.admin_dsn,
            self.migrator_dsn,
            self.control_dsn,
            self.login_passwords,
        ) == (
            other_carrier.admin_dsn,
            other_carrier.migrator_dsn,
            other_carrier.control_dsn,
            other_carrier.login_passwords,
        )


@dataclass(frozen=True, slots=True)
class StoreLossRecoveryReport:
    service_identity: str
    provisioning_spec_digest: str
    migration_set_digest: str
    system_identifier: str
    migration_execution_id: UUID
    event_id: UUID
    interval_start: datetime
    interval_end: datetime
    observed_at: datetime
    purge_after: datetime

    @property
    def report_bytes(self) -> bytes:
        return _render_report(self)


@dataclass(frozen=True, slots=True, repr=False)
class _Routes:
    admin_long: str
    admin_short: str
    admin_target_short: str
    migrator_long: str
    control_short: str

    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return NotImplemented
        other_carrier = cast(Self, other)
        return (
            self.admin_long,
            self.admin_short,
            self.admin_target_short,
            self.migrator_long,
            self.control_short,
        ) == (
            other_carrier.admin_long,
            other_carrier.admin_short,
            other_carrier.admin_target_short,
            other_carrier.migrator_long,
            other_carrier.control_short,
        )
@dataclass(frozen=True, slots=True, repr=False)
class _ValidatedInvocation:
    request: StoreLossRecoveryRequest
    routes: _Routes
    login_passwords: tuple[tuple[str, str], ...]

    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return NotImplemented
        other_carrier = cast(Self, other)
        return (
            self.request,
            self.routes,
            self.login_passwords,
        ) == (
            other_carrier.request,
            other_carrier.routes,
            other_carrier.login_passwords,
        )


@dataclass(frozen=True, slots=True)
class _GapResult:
    event_id: UUID
    interval_end: datetime
    observed_at: datetime
    purge_after: datetime


@dataclass(frozen=True, slots=True)
class _GapAttempt:
    result: _GapResult
    commit_ambiguous: bool
    cleanup_failed: bool


class _Cursor(Protocol):
    def fetchone(self) -> object: ...

    def fetchall(self) -> object: ...


class _Connection(Protocol):
    closed: bool

    def execute(
        self,
        query: str,
        parameters: tuple[object, ...] | None = None,
    ) -> _Cursor: ...

    def rollback(self) -> None: ...

    def commit(self) -> None: ...

    def close(self) -> None: ...


class _ConnectionFactory(Protocol):
    def __call__(
        self,
        conninfo: str,
        *,
        autocommit: bool,
    ) -> _Connection: ...


class _RandomBytes(Protocol):
    def __call__(self, length: int) -> bytes: ...


class _Provision(Protocol):
    def __call__(
        self,
        admin_dsn: str,
        *,
        login_passwords: dict[str, str],
        witness: _StoreLossLiveWitness,
    ) -> ProvisioningReport: ...


class _Migrate(Protocol):
    def __call__(
        self,
        *,
        admin_dsn: str,
        migrator_dsn: str,
        migration_set: MigrationSet,
        release_identity: str,
        execution_id: UUID,
        witness: _StoreLossLiveWitness,
    ) -> MigrationRunReport: ...


class _LoadMigrations(Protocol):
    def __call__(self) -> MigrationSet: ...


@dataclass(frozen=True, slots=True)
class _Dependencies:
    connection_factory: _ConnectionFactory
    random_bytes: _RandomBytes
    provision: _Provision
    migrate: _Migrate
    load_migrations: _LoadMigrations


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _utc_timestamp(value: object) -> datetime:
    if type(value) is not datetime or value.utcoffset() != timedelta(0):
        raise ValueError("store-loss timestamp is invalid")
    return value.astimezone(timezone.utc)


def _render_report(report: StoreLossRecoveryReport) -> bytes:
    document = {
        "countUnknown": True,
        "eventId": str(report.event_id),
        "intervalEnd": _timestamp(report.interval_end),
        "intervalStart": _timestamp(report.interval_start),
        "migrationExecutionId": str(report.migration_execution_id),
        "migrationSetDigest": report.migration_set_digest,
        "observedAt": _timestamp(report.observed_at),
        "outcome": "RECOVERED",
        "provisioningSpecDigest": report.provisioning_spec_digest,
        "purgeAfter": _timestamp(report.purge_after),
        "schema": STORE_LOSS_REPORT_SCHEMA,
        "serviceIdentity": report.service_identity,
        "systemIdentifier": report.system_identifier,
    }
    return (
        json.dumps(
            document,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        + b"\n"
    )


def _bounded_dsn(value: str, database_name: str, options: str) -> str:
    parameters = psycopg.conninfo.conninfo_to_dict(value)
    parameters["dbname"] = database_name
    parameters["connect_timeout"] = str(STORE_LOSS_CONNECT_TIMEOUT_SECONDS)
    parameters["options"] = options
    return psycopg.conninfo.make_conninfo(**parameters)


def _validated_invocation(
    request: StoreLossRecoveryRequest,
    secret_carrier: StoreLossRecoverySecrets,
) -> _ValidatedInvocation:
    if type(request) is not StoreLossRecoveryRequest:
        raise ValueError("store-loss request type differs")
    loss_start = _utc_timestamp(request.loss_start)
    if (
        type(request.release_identity) is not str
        or _RELEASE_IDENTITY.fullmatch(request.release_identity) is None
        or type(request.execution_id) is not UUID
        or request.execution_id.int == 0
    ):
        raise ValueError("store-loss request values differ")
    if type(secret_carrier) is not StoreLossRecoverySecrets:
        raise ValueError("store-loss secret carrier type differs")
    dsn_values = (
        secret_carrier.admin_dsn,
        secret_carrier.migrator_dsn,
        secret_carrier.control_dsn,
    )
    if any(type(value) is not str or not value.strip() for value in dsn_values):
        raise ValueError("store-loss route is absent")
    expected_roles = SECURITY_AUDIT_PROVISIONING_SPEC.required_password_role_names
    pairs = secret_carrier.login_passwords
    if (
        type(pairs) is not tuple
        or len(pairs) != len(expected_roles)
        or any(type(pair) is not tuple or len(pair) != 2 for pair in pairs)
        or tuple(pair[0] for pair in pairs) != expected_roles
        or any(type(pair[1]) is not str or not pair[1] for pair in pairs)
    ):
        raise ValueError("store-loss login password carrier differs")
    routes = _Routes(
        admin_long=_bounded_dsn(dsn_values[0], "postgres", STORE_LOSS_LONG_OPTIONS),
        admin_short=_bounded_dsn(dsn_values[0], "postgres", STORE_LOSS_SHORT_OPTIONS),
        admin_target_short=_bounded_dsn(
            dsn_values[0], _AUDIT_DATABASE, STORE_LOSS_SHORT_OPTIONS
        ),
        migrator_long=_bounded_dsn(
            dsn_values[1], _AUDIT_DATABASE, STORE_LOSS_LONG_OPTIONS
        ),
        control_short=_bounded_dsn(
            dsn_values[2], _AUDIT_DATABASE, STORE_LOSS_SHORT_OPTIONS
        ),
    )
    normalized = StoreLossRecoveryRequest(
        loss_start=loss_start,
        release_identity=request.release_identity,
        execution_id=request.execution_id,
    )
    return _ValidatedInvocation(normalized, routes, pairs)


def _exact_row(cursor: _Cursor, length: int) -> tuple[object, ...]:
    row = cursor.fetchone()
    second_row = cursor.fetchone()
    if type(row) is not tuple or len(row) != length or second_row is not None:
        raise ValueError("store-loss database result shape differs")
    return row


def _signed_int4(value: bytes) -> int:
    return int.from_bytes(value, "big", signed=True)


def _witness_carrier(
    connection: _Connection,
    token: bytes,
) -> _StoreLossLiveWitness:
    identity = _exact_row(connection.execute(WITNESS_IDENTITY_SQL), 11)
    if (
        any(type(identity[index]) is not str for index in (0, 1, 2, 6, 7, 9))
        or type(identity[3]) is not int
        or type(identity[4]) is not bool
        or type(identity[5]) is not int
        or type(identity[8]) is not bool
        or type(identity[10]) is not int
        or identity[0] != identity[1]
        or not identity[0]
        or identity[2] != "postgres"
        or identity[3] <= 0
        or identity[4] is not True
        or identity[5] != SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM
        or identity[6] != SUPPORTED_POSTGRESQL_SERVER_VERSION
        or not identity[7]
        or identity[8] is not False
        or identity[9] != "off"
        or identity[10] <= 0
    ):
        raise ValueError("store-loss witness route posture differs")
    bigint_key = int.from_bytes(token[0:8], "big", signed=True)
    pair_key = (_signed_int4(token[8:12]), _signed_int4(token[12:16]))
    if _exact_row(
        connection.execute(WITNESS_BIGINT_LOCK_SQL, (bigint_key,)), 1
    ) != (True,):
        raise ValueError("store-loss witness lock was not acquired")
    if _exact_row(
        connection.execute(WITNESS_INTEGER_PAIR_LOCK_SQL, pair_key), 1
    ) != (True,):
        raise ValueError("store-loss witness lock was not acquired")
    return _StoreLossLiveWitness(
        control_database_oid=identity[3],
        backend_pid=identity[10],
        system_identifier=identity[7],
        server_version_num=identity[5],
        server_version=identity[6],
        bigint_classid=_signed_int4(token[0:4]),
        bigint_objid=_signed_int4(token[4:8]),
        integer_pair_classid=pair_key[0],
        integer_pair_objid=pair_key[1],
    )


def _close_suppressed(connection: _Connection | None) -> None:
    if connection is None:
        return
    try:
        connection.close()
    except Exception:
        pass


def _rollback_suppressed(connection: _Connection) -> None:
    try:
        connection.rollback()
    except Exception:
        pass


def _close_strict(connection: _Connection) -> None:
    connection.close()
    if connection.closed is not True:
        raise ValueError("store-loss connection did not close")


def _validate_provisioning_report(
    report: ProvisioningReport,
    witness: _StoreLossLiveWitness,
) -> None:
    if (
        type(report) is not ProvisioningReport
        or report.service_identity != SECURITY_AUDIT_PROVISIONING_SPEC.identity
        or report.provisioning_spec_digest != SECURITY_AUDIT_PROVISIONING_SPEC.digest
        or report.database_name != _AUDIT_DATABASE
        or report.system_identifier != witness.system_identifier
        or report.server_version_num != witness.server_version_num
        or report.created is not True
        or report.migration_ledger_present is not False
    ):
        raise ValueError("store-loss provisioning result differs")


def _validate_migration_report(
    report: MigrationRunReport,
    migration_set: MigrationSet,
    invocation: _ValidatedInvocation,
    witness: _StoreLossLiveWitness,
) -> None:
    versions = tuple(migration.version for migration in migration_set.migrations)
    if (
        type(report) is not MigrationRunReport
        or report.service_identity != SECURITY_AUDIT_SERVICE.identity
        or report.provisioning_spec_digest != SECURITY_AUDIT_PROVISIONING_SPEC.digest
        or report.migration_set_digest != migration_set.digest
        or report.database_name != _AUDIT_DATABASE
        or report.system_identifier != witness.system_identifier
        or report.server_version_num != witness.server_version_num
        or report.previous_version != 0
        or report.applied_versions != versions
        or report.final_version != len(versions)
        or report.execution_id != invocation.request.execution_id
        or report.observed_head_execution_id != invocation.request.execution_id
        or report.verified_noop is not False
    ):
        raise ValueError("store-loss migration result differs")


def _read_ledger(
    connection: _Connection,
    migration_set: MigrationSet,
    request: StoreLossRecoveryRequest,
) -> None:
    cursor = connection.execute(LEDGER_SQL, (len(migration_set.migrations) + 1,))
    rows = cursor.fetchall()
    if type(rows) is not list or len(rows) != len(migration_set.migrations):
        raise ValueError("store-loss migration ledger differs")
    for migration, row in zip(migration_set.migrations, rows, strict=True):
        if (
            type(row) is not tuple
            or len(row) != 10
            or tuple(row[0:9])
            != (
                migration.version,
                migration.filename,
                migration.source_sha256,
                migration.byte_length,
                migration_set.prefix_digest(migration.version),
                SECURITY_AUDIT_SERVICE.identity,
                SECURITY_AUDIT_PROVISIONING_SPEC.digest,
                request.release_identity,
                request.execution_id,
            )
        ):
            raise ValueError("store-loss migration ledger differs")
        _utc_timestamp(row[9])


def _admit_read_observation(
    connection: _Connection,
    witness: _StoreLossLiveWitness,
) -> None:
    connection.execute(
        "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    )
    admission = _assert_security_audit_store_loss_witness(
        cast(psycopg.Connection, connection),
        witness,
    )
    if (
        admission.session_user != admission.current_user
        or not admission.session_user
        or admission.database_name != _AUDIT_DATABASE
        or admission.transaction_read_only != "on"
        or admission.transaction_isolation != "repeatable read"
        or admission.synchronous_commit != "on"
    ):
        raise ProvisioningTargetError("store-loss observation posture differs")


def _observe_fresh_state(
    dependencies: _Dependencies,
    invocation: _ValidatedInvocation,
    witness: _StoreLossLiveWitness,
    migration_set: MigrationSet,
) -> None:
    connection = dependencies.connection_factory(
        invocation.routes.admin_target_short,
        autocommit=True,
    )
    try:
        _admit_read_observation(connection, witness)
        state = _exact_row(connection.execute(FRESH_STATE_SQL), 13)
        if state != _EXPECTED_FRESH_STATE:
            raise ValueError("store-loss fresh target state differs")
        _read_ledger(connection, migration_set, invocation.request)
        connection.rollback()
        _close_strict(connection)
    except BaseException:
        _rollback_suppressed(connection)
        _close_suppressed(connection)
        raise


def _admit_control(
    connection: _Connection,
    witness: _StoreLossLiveWitness,
    provisioning: ProvisioningReport,
    migration: MigrationRunReport,
) -> None:
    if (
        provisioning.database_name != migration.database_name
        or provisioning.system_identifier != migration.system_identifier
        or provisioning.server_version_num != migration.server_version_num
    ):
        raise ValueError("store-loss reports identify different targets")
    connection.execute(
        "BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED READ WRITE"
    )
    admission = _assert_security_audit_store_loss_witness(
        cast(psycopg.Connection, connection),
        witness,
    )
    if (
        admission.session_user != "ofarm_security_audit_control_login"
        or admission.current_user != "ofarm_security_audit_control_login"
        or admission.database_name != _AUDIT_DATABASE
        or admission.transaction_read_only != "off"
        or admission.transaction_isolation != "read committed"
        or admission.synchronous_commit != "on"
    ):
        raise ProvisioningTargetError("store-loss control route posture differs")


def _append_gap(
    dependencies: _Dependencies,
    invocation: _ValidatedInvocation,
    witness: _StoreLossLiveWitness,
    provisioning: ProvisioningReport,
    migration: MigrationRunReport,
) -> _GapAttempt:
    connection = dependencies.connection_factory(
        invocation.routes.control_short,
        autocommit=False,
    )
    commit_sent = False
    try:
        _admit_control(connection, witness, provisioning, migration)
        interval_end = _utc_timestamp(
            _exact_row(connection.execute(CLOCK_SQL), 1)[0]
        )
        if interval_end <= invocation.request.loss_start:
            raise ValueError("store-loss interval does not advance")
        row = _exact_row(
            connection.execute(
                APPEND_GAP_SQL,
                (invocation.request.loss_start, interval_end),
            ),
            3,
        )
        event_id, observed_at_value, purge_after_value = row
        observed_at = _utc_timestamp(observed_at_value)
        purge_after = _utc_timestamp(purge_after_value)
        if (
            type(event_id) is not UUID
            or event_id.int == 0
            or observed_at < interval_end
            or purge_after != observed_at + _RETENTION_INTERVAL
        ):
            raise ValueError("store-loss gap result differs")
        result = _GapResult(event_id, interval_end, observed_at, purge_after)
        commit_sent = True
        try:
            connection.commit()
            ambiguous = False
        except Exception:
            ambiguous = True
        try:
            _close_strict(connection)
            cleanup_failed = False
        except Exception:
            cleanup_failed = True
        return _GapAttempt(result, ambiguous, cleanup_failed)
    except BaseException:
        if not commit_sent:
            _rollback_suppressed(connection)
        _close_suppressed(connection)
        raise


def _validate_final_state(
    row: tuple[object, ...],
    request: StoreLossRecoveryRequest,
    gap: _GapResult,
) -> None:
    if (
        row[0] != 1
        or row[1] != gap.event_id
        or _utc_timestamp(row[2]) != gap.observed_at
        or _utc_timestamp(row[3]) != gap.purge_after
        or tuple(row[4:15])
        != (
            "AUDIT_GAP",
            "SECURITY_OPERATIONS_V1",
            "AUDIT_CONTROL",
            request.loss_start,
            gap.interval_end,
            None,
            True,
            EVENT_FORMAT_IDENTITY,
            REDACTION_POLICY_IDENTITY,
            RETENTION_POLICY_IDENTITY,
            32,
        )
        or row[15] is not True
        or tuple(row[16:22]) != (0, 0, 512, 0, 0, False)
    ):
        raise ValueError("store-loss final state differs")


def _observe_final_state(
    dependencies: _Dependencies,
    invocation: _ValidatedInvocation,
    witness: _StoreLossLiveWitness,
    migration_set: MigrationSet,
    gap: _GapResult,
) -> None:
    connection = dependencies.connection_factory(
        invocation.routes.admin_target_short,
        autocommit=True,
    )
    try:
        _admit_read_observation(connection, witness)
        row = _exact_row(connection.execute(FINAL_STATE_SQL), 22)
        _validate_final_state(row, invocation.request, gap)
        _read_ledger(connection, migration_set, invocation.request)
        connection.rollback()
        _close_strict(connection)
    except BaseException:
        _rollback_suppressed(connection)
        _close_suppressed(connection)
        raise


def _execute_recovery(
    dependencies: _Dependencies,
    invocation: _ValidatedInvocation,
) -> StoreLossRecoveryReport:
    token = dependencies.random_bytes(16)
    if type(token) is not bytes or len(token) != 16:
        raise ValueError("store-loss witness entropy differs")
    witness_connection: _Connection | None = None
    witness: _StoreLossLiveWitness | None = None
    try:
        witness_connection = dependencies.connection_factory(
            invocation.routes.admin_short,
            autocommit=True,
        )
        witness = _witness_carrier(witness_connection, token)
        provisioning = dependencies.provision(
            invocation.routes.admin_long,
            login_passwords=dict(invocation.login_passwords),
            witness=witness,
        )
        _validate_provisioning_report(provisioning, witness)
        migration_set = dependencies.load_migrations()
        migration = dependencies.migrate(
            admin_dsn=invocation.routes.admin_long,
            migrator_dsn=invocation.routes.migrator_long,
            migration_set=migration_set,
            release_identity=invocation.request.release_identity,
            execution_id=invocation.request.execution_id,
            witness=witness,
        )
        _validate_migration_report(migration, migration_set, invocation, witness)
        _observe_fresh_state(dependencies, invocation, witness, migration_set)
        gap_attempt = _append_gap(
            dependencies,
            invocation,
            witness,
            provisioning,
            migration,
        )
        try:
            _observe_final_state(
                dependencies,
                invocation,
                witness,
                migration_set,
                gap_attempt.result,
            )
        except Exception:
            if gap_attempt.commit_ambiguous:
                raise SecurityAuditStoreLossOutcomeUnknown from None
            raise SecurityAuditStoreLossRefused from None
        if gap_attempt.cleanup_failed:
            raise SecurityAuditStoreLossRefused
        _close_strict(witness_connection)
        witness_connection = None
        report = StoreLossRecoveryReport(
            service_identity=migration.service_identity,
            provisioning_spec_digest=provisioning.provisioning_spec_digest,
            migration_set_digest=migration.migration_set_digest,
            system_identifier=migration.system_identifier,
            migration_execution_id=invocation.request.execution_id,
            event_id=gap_attempt.result.event_id,
            interval_start=invocation.request.loss_start,
            interval_end=gap_attempt.result.interval_end,
            observed_at=gap_attempt.result.observed_at,
            purge_after=gap_attempt.result.purge_after,
        )
        witness = None
        token = b""
        return report
    finally:
        _close_suppressed(witness_connection)


def _load_fixed_migrations() -> MigrationSet:
    return load_authoritative_migration_set(_PACKAGE_ROOT, SECURITY_AUDIT_SERVICE)


_PRODUCTION_DEPENDENCIES = _Dependencies(
    connection_factory=cast(_ConnectionFactory, psycopg.connect),
    random_bytes=secrets.token_bytes,
    provision=_provision_security_audit_store_loss,
    migrate=_migrate_security_audit_store_loss,
    load_migrations=_load_fixed_migrations,
)


class SecurityAuditStoreLossRecoveryRunner:
    """Execute the repository-fixed recovery composition once."""

    def run(
        self,
        request: StoreLossRecoveryRequest,
        secret_carrier: StoreLossRecoverySecrets,
    ) -> StoreLossRecoveryReport:
        try:
            invocation = _validated_invocation(request, secret_carrier)
        except Exception:
            raise SecurityAuditStoreLossInputError from None
        try:
            return _execute_recovery(_PRODUCTION_DEPENDENCIES, invocation)
        except SecurityAuditStoreLossOutcomeUnknown:
            raise
        except SecurityAuditStoreLossRefused:
            raise
        except Exception:
            raise SecurityAuditStoreLossRefused from None


def _run_security_audit_store_loss_for_testing(
    request: StoreLossRecoveryRequest,
    secret_carrier: StoreLossRecoverySecrets,
    dependencies: _Dependencies,
) -> StoreLossRecoveryReport:
    """Private deterministic seam with the same validation and state machine."""

    try:
        invocation = _validated_invocation(request, secret_carrier)
    except Exception:
        raise SecurityAuditStoreLossInputError from None
    try:
        return _execute_recovery(dependencies, invocation)
    except SecurityAuditStoreLossOutcomeUnknown:
        raise
    except SecurityAuditStoreLossRefused:
        raise
    except Exception:
        raise SecurityAuditStoreLossRefused from None


__all__ = (
    "APPEND_GAP_SQL",
    "FINAL_STATE_SQL",
    "FRESH_STATE_SQL",
    "LEDGER_SQL",
    "STORE_LOSS_CONNECT_TIMEOUT_SECONDS",
    "STORE_LOSS_LONG_OPTIONS",
    "STORE_LOSS_REPORT_SCHEMA",
    "STORE_LOSS_SHORT_OPTIONS",
    "SecurityAuditStoreLossError",
    "SecurityAuditStoreLossInputError",
    "SecurityAuditStoreLossOutcomeUnknown",
    "SecurityAuditStoreLossRecoveryRunner",
    "SecurityAuditStoreLossRefused",
    "StoreLossRecoveryReport",
    "StoreLossRecoveryRequest",
    "StoreLossRecoverySecrets",
    "WITNESS_BIGINT_LOCK_SQL",
    "WITNESS_IDENTITY_SQL",
    "WITNESS_INTEGER_PAIR_LOCK_SQL",
)
