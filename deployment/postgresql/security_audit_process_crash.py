"""Reconcile one independently witnessed audit process-crash interval.

The operation has one surviving-store route, one database-owned interval end,
one existing unknown-count append, and no retry authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import Protocol, cast
from uuid import UUID

import psycopg

from deployment.postgresql.audit_contract import RETENTION_SECONDS
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
)
from deployment.postgresql.version_policy import (
    SUPPORTED_POSTGRESQL_SERVER_VERSION,
    SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
)


PROCESS_CRASH_REPORT_SCHEMA = (
    "ofarm.security-audit-process-crash-reconciliation-report.v1"
)
PROCESS_CRASH_CONTROL_LOGIN = "ofarm_security_audit_control_login"
PROCESS_CRASH_CONNECT_TIMEOUT_SECONDS = 5
PROCESS_CRASH_MINIMUM_LIBPQ_VERSION = 160000
PROCESS_CRASH_APPLICATION_NAME = (
    "ofarm_security_audit_process_crash_reconciliation"
)
PROCESS_CRASH_CONNECTION_OPTIONS = (
    "-c statement_timeout=2000 "
    "-c lock_timeout=250 "
    "-c idle_in_transaction_session_timeout=10000 "
    "-c transaction_timeout=15000 "
    "-c TimeZone=UTC "
    "-c DateStyle=ISO,MDY "
    "-c synchronous_commit=on"
)
PROCESS_CRASH_REPORT_BYTES = 298
PROCESS_CRASH_REPORT_FAULT_CEILING = 512

ADMISSION_SQL = """
SELECT session_user::pg_catalog.text,
       current_user::pg_catalog.text,
       pg_catalog.current_database()::pg_catalog.text,
       pg_catalog.current_setting('server_version_num')::integer,
       pg_catalog.current_setting('server_version')::pg_catalog.text,
       pg_catalog.pg_is_in_recovery(),
       pg_catalog.current_setting('transaction_read_only'),
       pg_catalog.current_setting('transaction_isolation'),
       pg_catalog.current_setting('statement_timeout'),
       pg_catalog.current_setting('lock_timeout'),
       pg_catalog.current_setting('idle_in_transaction_session_timeout'),
       pg_catalog.current_setting('transaction_timeout'),
       pg_catalog.current_setting('TimeZone'),
       pg_catalog.current_setting('DateStyle'),
       pg_catalog.current_setting('synchronous_commit')
"""
CLOCK_SQL = "SELECT pg_catalog.clock_timestamp()"
APPEND_GAP_SQL = """
SELECT *
FROM ofarm_security.append_audit_gap(%s, %s, 0, true)
"""

_AUDIT_DATABASE = SECURITY_AUDIT_PROVISIONING_SPEC.database_name
_RETENTION_INTERVAL = timedelta(seconds=RETENTION_SECONDS)
_COMMON_CONNINFO_KEYS = frozenset(
    {"host", "port", "dbname", "user", "password", "sslmode"}
)
_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_PORT = re.compile(r"[0-9]+")
_CONNINFO_WHITESPACE = " \t\r\n"


class SecurityAuditProcessCrashError(RuntimeError):
    """Base class for the operation's fixed outcomes."""


class SecurityAuditProcessCrashInputError(SecurityAuditProcessCrashError):
    """The request or route is invalid before PostgreSQL effects."""


class SecurityAuditProcessCrashRefused(SecurityAuditProcessCrashError):
    """A known pre-commit failure or proven rollback occurred."""


class SecurityAuditProcessCrashInterrupted(SecurityAuditProcessCrashError):
    """A catchable interruption occurred before commit invocation."""


class SecurityAuditProcessCrashOutcomeUnknown(SecurityAuditProcessCrashError):
    """Commit invocation began but acknowledgement was not received."""


class SecurityAuditProcessCrashReportingFailed(SecurityAuditProcessCrashError):
    """Commit was acknowledged but report construction failed."""


@dataclass(frozen=True, slots=True)
class ProcessCrashReconciliationRequest:
    interval_start: datetime


@dataclass(frozen=True, slots=True)
class ProcessCrashReconciliationSecrets:
    control_conninfo: str


@dataclass(frozen=True, slots=True)
class ProcessCrashReconciliationReport:
    event_id: UUID
    interval_end: datetime
    interval_start: datetime
    observed_at: datetime
    purge_after: datetime
    _report_bytes: bytes

    @property
    def report_bytes(self) -> bytes:
        return self._report_bytes


class _Phase(Enum):
    INPUT_VALIDATED = auto()
    CONNECTED = auto()
    DATABASE_ADMITTED = auto()
    APPEND_IN_FLIGHT = auto()
    COMMIT_IN_FLIGHT = auto()
    COMMITTED = auto()


class _Cursor(Protocol):
    def fetchone(self) -> object: ...


class _Connection(Protocol):
    def execute(
        self,
        query: str,
        parameters: tuple[object, ...] | None = None,
    ) -> _Cursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


class _ConnectionFactory(Protocol):
    def __call__(
        self,
        conninfo: str,
        *,
        autocommit: bool,
    ) -> _Connection: ...


class _LibpqVersion(Protocol):
    def __call__(self) -> int: ...


@dataclass(frozen=True, slots=True)
class _Dependencies:
    connection_factory: _ConnectionFactory
    libpq_version: _LibpqVersion


def _parse_keyword_conninfo(value: str) -> dict[str, str]:
    """Parse libpq keyword conninfo while preserving duplicate detection."""

    fields: dict[str, str] = {}
    index = 0
    length = len(value)
    while True:
        while index < length and value[index] in _CONNINFO_WHITESPACE:
            index += 1
        if index == length:
            break
        match = _KEY.match(value, index)
        if match is None:
            raise ValueError("process-crash conninfo key is invalid")
        key = match.group(0)
        index = match.end()
        while index < length and value[index] in _CONNINFO_WHITESPACE:
            index += 1
        if index == length or value[index] != "=":
            raise ValueError("process-crash conninfo assignment is invalid")
        index += 1
        while index < length and value[index] in _CONNINFO_WHITESPACE:
            index += 1
        characters: list[str] = []
        if index < length and value[index] == "'":
            index += 1
            while index < length:
                character = value[index]
                index += 1
                if character == "'":
                    break
                if character == "\\":
                    if index == length:
                        raise ValueError("process-crash conninfo escape is invalid")
                    character = value[index]
                    index += 1
                characters.append(character)
            else:
                raise ValueError("process-crash conninfo quote is incomplete")
            if index < length and value[index] not in _CONNINFO_WHITESPACE:
                raise ValueError("process-crash conninfo quote is invalid")
        else:
            while index < length and value[index] not in _CONNINFO_WHITESPACE:
                character = value[index]
                index += 1
                if character == "\\":
                    if index == length:
                        raise ValueError("process-crash conninfo escape is invalid")
                    character = value[index]
                    index += 1
                characters.append(character)
        parsed = "".join(characters)
        if key in fields or not parsed or "\x00" in parsed:
            raise ValueError("process-crash conninfo field is invalid")
        fields[key] = parsed
    if set(fields) != _COMMON_CONNINFO_KEYS:
        raise ValueError("process-crash conninfo authority is incomplete")
    return fields


def reconstruct_process_crash_conninfo(
    value: object,
    *,
    libpq_version: _LibpqVersion = psycopg.pq.version,
) -> str:
    """Validate and reconstruct the operation's complete closed conninfo."""

    if type(value) is not str or not value or len(value) > 4096:
        raise SecurityAuditProcessCrashInputError
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as error:
        raise SecurityAuditProcessCrashInputError from error
    if len(encoded) > 4096 or b"\xef\xbf\xbd" in encoded:
        raise SecurityAuditProcessCrashInputError
    try:
        version = libpq_version()
    except Exception as error:
        raise SecurityAuditProcessCrashInputError from error
    if type(version) is not int or version < PROCESS_CRASH_MINIMUM_LIBPQ_VERSION:
        raise SecurityAuditProcessCrashInputError
    try:
        fields = _parse_keyword_conninfo(value)
        port = fields["port"]
        host = fields["host"]
        if (
            _PORT.fullmatch(port) is None
            or not 1 <= int(port) <= 65535
            or not host.startswith("/")
            or "," in host
            or fields["dbname"] != _AUDIT_DATABASE
            or fields["user"] != PROCESS_CRASH_CONTROL_LOGIN
            or fields["sslmode"] != "disable"
        ):
            raise ValueError("process-crash conninfo posture differs")
        reconstructed = psycopg.conninfo.make_conninfo(
            **fields,
            application_name=PROCESS_CRASH_APPLICATION_NAME,
            target_session_attrs="read-write",
            load_balance_hosts="disable",
            gssencmode="disable",
            require_auth="scram-sha-256",
            connect_timeout=str(PROCESS_CRASH_CONNECT_TIMEOUT_SECONDS),
            options=PROCESS_CRASH_CONNECTION_OPTIONS,
        )
        observed = psycopg.conninfo.conninfo_to_dict(reconstructed)
    except Exception as error:
        raise SecurityAuditProcessCrashInputError from error
    expected = {
        **fields,
        "application_name": PROCESS_CRASH_APPLICATION_NAME,
        "target_session_attrs": "read-write",
        "load_balance_hosts": "disable",
        "gssencmode": "disable",
        "require_auth": "scram-sha-256",
        "connect_timeout": str(PROCESS_CRASH_CONNECT_TIMEOUT_SECONDS),
        "options": PROCESS_CRASH_CONNECTION_OPTIONS,
    }
    if observed != expected:
        raise SecurityAuditProcessCrashInputError
    return reconstructed


def _utc_datetime(value: object) -> datetime:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise ValueError("process-crash timestamp is invalid")
    return cast(datetime, value).astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _exact_row(cursor: _Cursor, length: int) -> tuple[object, ...]:
    row = cursor.fetchone()
    second = cursor.fetchone()
    if type(row) is not tuple or len(row) != length or second is not None:
        raise ValueError("process-crash query returned an invalid row")
    return row


def _rollback_suppressed(connection: _Connection | None) -> None:
    if connection is None:
        return
    try:
        connection.rollback()
    except BaseException:
        pass


def _close_suppressed(connection: _Connection | None) -> None:
    if connection is None:
        return
    try:
        connection.close()
    except BaseException:
        pass


def _is_proven_idle_timeout(error: BaseException) -> bool:
    return (
        isinstance(error, psycopg.errors.IdleInTransactionSessionTimeout)
        and getattr(error, "sqlstate", None) == "25P03"
    )


def _admit(connection: _Connection) -> None:
    connection.execute(
        "BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED READ WRITE"
    )
    row = _exact_row(connection.execute(ADMISSION_SQL), 15)
    expected = (
        PROCESS_CRASH_CONTROL_LOGIN,
        PROCESS_CRASH_CONTROL_LOGIN,
        _AUDIT_DATABASE,
        SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
        SUPPORTED_POSTGRESQL_SERVER_VERSION,
        False,
        "off",
        "read committed",
        "2s",
        "250ms",
        "10s",
        "15s",
        "UTC",
        "ISO, MDY",
        "on",
    )
    if row != expected:
        raise ValueError("process-crash database posture differs")


def _render_report(
    *,
    event_id: UUID,
    interval_end: datetime,
    interval_start: datetime,
    observed_at: datetime,
    purge_after: datetime,
) -> bytes:
    payload = {
        "eventId": str(event_id),
        "intervalEnd": _timestamp(interval_end),
        "intervalStart": _timestamp(interval_start),
        "observedAt": _timestamp(observed_at),
        "purgeAfter": _timestamp(purge_after),
        "schema": PROCESS_CRASH_REPORT_SCHEMA,
    }
    rendered = (
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    if (
        len(rendered) != PROCESS_CRASH_REPORT_BYTES
        or len(rendered) > PROCESS_CRASH_REPORT_FAULT_CEILING
        or rendered.decode("ascii") is None
    ):
        raise ValueError("process-crash report differs")
    return rendered


def _validated_invocation(
    dependencies: _Dependencies,
    request: object,
    secret_carrier: object,
) -> tuple[ProcessCrashReconciliationRequest, str]:
    if (
        type(request) is not ProcessCrashReconciliationRequest
        or type(secret_carrier) is not ProcessCrashReconciliationSecrets
        or type(secret_carrier.control_conninfo) is not str
    ):
        raise SecurityAuditProcessCrashInputError
    try:
        start = _utc_datetime(request.interval_start)
        version = dependencies.libpq_version()
        observed = psycopg.conninfo.conninfo_to_dict(
            secret_carrier.control_conninfo
        )
    except Exception as error:
        raise SecurityAuditProcessCrashInputError from error
    if (
        type(version) is not int
        or version < PROCESS_CRASH_MINIMUM_LIBPQ_VERSION
        or set(observed)
        != _COMMON_CONNINFO_KEYS
        | {
            "application_name",
            "target_session_attrs",
            "load_balance_hosts",
            "gssencmode",
            "require_auth",
            "connect_timeout",
            "options",
        }
        or observed.get("application_name") != PROCESS_CRASH_APPLICATION_NAME
        or observed.get("target_session_attrs") != "read-write"
        or observed.get("load_balance_hosts") != "disable"
        or observed.get("gssencmode") != "disable"
        or observed.get("require_auth") != "scram-sha-256"
        or observed.get("connect_timeout")
        != str(PROCESS_CRASH_CONNECT_TIMEOUT_SECONDS)
        or observed.get("options") != PROCESS_CRASH_CONNECTION_OPTIONS
        or observed.get("dbname") != _AUDIT_DATABASE
        or observed.get("user") != PROCESS_CRASH_CONTROL_LOGIN
        or observed.get("sslmode") != "disable"
        or not cast(str, observed.get("host", "")).startswith("/")
        or "," in cast(str, observed.get("host", ""))
        or _PORT.fullmatch(cast(str, observed.get("port", ""))) is None
        or not 1 <= int(cast(str, observed["port"])) <= 65535
        or not observed.get("password")
    ):
        raise SecurityAuditProcessCrashInputError
    return ProcessCrashReconciliationRequest(start), secret_carrier.control_conninfo


def _execute(
    dependencies: _Dependencies,
    request: ProcessCrashReconciliationRequest,
    conninfo: str,
) -> ProcessCrashReconciliationReport:
    phase = _Phase.INPUT_VALIDATED
    connection: _Connection | None = None
    try:
        connection = dependencies.connection_factory(conninfo, autocommit=False)
        phase = _Phase.CONNECTED
        _admit(connection)
        phase = _Phase.DATABASE_ADMITTED
        interval_end = _utc_datetime(
            _exact_row(connection.execute(CLOCK_SQL), 1)[0]
        )
        if interval_end <= request.interval_start:
            raise ValueError("process-crash interval does not advance")
        phase = _Phase.APPEND_IN_FLIGHT
        row = _exact_row(
            connection.execute(
                APPEND_GAP_SQL,
                (request.interval_start, interval_end),
            ),
            3,
        )
        event_id, observed_value, purge_value = row
        observed_at = _utc_datetime(observed_value)
        purge_after = _utc_datetime(purge_value)
        if (
            type(event_id) is not UUID
            or event_id.int == 0
            or observed_at < interval_end
            or purge_after != observed_at + _RETENTION_INTERVAL
        ):
            raise ValueError("process-crash append result differs")
        phase = _Phase.COMMIT_IN_FLIGHT
        try:
            connection.commit()
        except BaseException as error:
            if _is_proven_idle_timeout(error):
                _close_suppressed(connection)
                raise SecurityAuditProcessCrashRefused from None
            _close_suppressed(connection)
            raise SecurityAuditProcessCrashOutcomeUnknown from None
        phase = _Phase.COMMITTED
        _close_suppressed(connection)
        try:
            report_bytes = _render_report(
                event_id=event_id,
                interval_end=interval_end,
                interval_start=request.interval_start,
                observed_at=observed_at,
                purge_after=purge_after,
            )
            return ProcessCrashReconciliationReport(
                event_id=event_id,
                interval_end=interval_end,
                interval_start=request.interval_start,
                observed_at=observed_at,
                purge_after=purge_after,
                _report_bytes=report_bytes,
            )
        except BaseException:
            raise SecurityAuditProcessCrashReportingFailed from None
    except SecurityAuditProcessCrashError:
        raise
    except BaseException as error:
        if _is_proven_idle_timeout(error):
            _close_suppressed(connection)
            raise SecurityAuditProcessCrashRefused from None
        if phase is not _Phase.COMMITTED:
            _rollback_suppressed(connection)
        _close_suppressed(connection)
        if isinstance(error, Exception):
            raise SecurityAuditProcessCrashRefused from None
        raise SecurityAuditProcessCrashInterrupted from None


_DEFAULT_DEPENDENCIES = _Dependencies(
    connection_factory=cast(_ConnectionFactory, psycopg.connect),
    libpq_version=psycopg.pq.version,
)


class SecurityAuditProcessCrashReconciliationRunner:
    """Execute one fixed surviving-store process-crash reconciliation."""

    def __init__(self, dependencies: _Dependencies = _DEFAULT_DEPENDENCIES) -> None:
        self._dependencies = dependencies

    def run(
        self,
        request: ProcessCrashReconciliationRequest,
        secret_carrier: ProcessCrashReconciliationSecrets,
    ) -> ProcessCrashReconciliationReport:
        try:
            validated, conninfo = _validated_invocation(
                self._dependencies,
                request,
                secret_carrier,
            )
            return _execute(self._dependencies, validated, conninfo)
        except SecurityAuditProcessCrashError:
            raise
        except BaseException as error:
            if isinstance(error, Exception):
                raise SecurityAuditProcessCrashRefused from None
            raise SecurityAuditProcessCrashInterrupted from None


def _runner_for_testing(
    *,
    connection_factory: _ConnectionFactory,
    libpq_version: _LibpqVersion = psycopg.pq.version,
) -> SecurityAuditProcessCrashReconciliationRunner:
    return SecurityAuditProcessCrashReconciliationRunner(
        _Dependencies(connection_factory, libpq_version)
    )


__all__ = (
    "ADMISSION_SQL",
    "APPEND_GAP_SQL",
    "CLOCK_SQL",
    "PROCESS_CRASH_APPLICATION_NAME",
    "PROCESS_CRASH_CONNECTION_OPTIONS",
    "PROCESS_CRASH_CONNECT_TIMEOUT_SECONDS",
    "PROCESS_CRASH_CONTROL_LOGIN",
    "PROCESS_CRASH_MINIMUM_LIBPQ_VERSION",
    "PROCESS_CRASH_REPORT_BYTES",
    "PROCESS_CRASH_REPORT_FAULT_CEILING",
    "PROCESS_CRASH_REPORT_SCHEMA",
    "ProcessCrashReconciliationReport",
    "ProcessCrashReconciliationRequest",
    "ProcessCrashReconciliationSecrets",
    "SecurityAuditProcessCrashInputError",
    "SecurityAuditProcessCrashInterrupted",
    "SecurityAuditProcessCrashOutcomeUnknown",
    "SecurityAuditProcessCrashReconciliationRunner",
    "SecurityAuditProcessCrashRefused",
    "SecurityAuditProcessCrashReportingFailed",
    "reconstruct_process_crash_conninfo",
)
