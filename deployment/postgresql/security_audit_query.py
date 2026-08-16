"""One-shot bounded reader for the isolated security-audit store.

PostgreSQL remains the sole authority for access authorization, the data cut,
snapshot membership, expiry, page ordering, and encoded-byte accounting.  This
module owns only the fixed two-route orchestration and canonical report
protocol; hostile carrier validation is shared with the bounded export path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol, cast

import psycopg
from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus

from deployment.postgresql.audit_contract import (
    QUERY_ACCESS_PURPOSE_IDENTITY,
    QUERY_FUNCTION_IDENTITY,
    QUERY_MAX_BYTES,
    QUERY_MAX_ROWS,
)
from deployment.postgresql.security_audit_access import (
    SecurityAuditAccessCursor as SecurityAuditQueryCursor,
    SecurityAuditAccessIntent,
    SecurityAuditEventReport,
    security_audit_cursor_values,
    security_audit_event_document,
    security_audit_timestamp_text,
    validate_security_audit_access_intent,
    validate_security_audit_event_page,
)


ACCESS_INTENT_SQL = (
    "SELECT * FROM ofarm_security.commit_audit_access_intent("
    "%s, %s, %s, %s, %s, %s)"
)
BOUNDED_QUERY_SQL = (
    "SELECT * FROM ofarm_security.query_operational_security_events("
    "%s, %s, %s, %s, %s)"
)
QUERY_CONNECT_TIMEOUT_SECONDS = 5
QUERY_READER_CONNECTION_OPTIONS = (
    "-c statement_timeout=5000 "
    "-c lock_timeout=500 "
    "-c idle_in_transaction_session_timeout=10000 "
    "-c transaction_timeout=15000 "
    "-c work_mem=1024kB "
    "-c bytea_output=hex "
    "-c TimeZone=UTC "
    "-c DateStyle=ISO,MDY"
)
QUERY_CONTROL_CONNECTION_OPTIONS = (
    QUERY_READER_CONNECTION_OPTIONS + " -c synchronous_commit=on"
)
QUERY_REPORT_SCHEMA = "ofarm.security-audit-bounded-query-report.v1"


class SecurityAuditQueryError(RuntimeError):
    """Base class for one closed bounded-query outcome."""


class SecurityAuditQueryRefused(SecurityAuditQueryError):
    """The control route returned, but no commit became ambiguous."""


class SecurityAuditQueryControlUnavailable(SecurityAuditQueryError):
    """The control connection factory failed before returning a connection."""


class SecurityAuditQueryOutcomeUnknown(SecurityAuditQueryError):
    """The access-intent commit raised, so its outcome is unknown."""


class SecurityAuditQueryFailed(SecurityAuditQueryError):
    """The intent committed, but no complete validated report is available."""


@dataclass(frozen=True, slots=True)
class AcknowledgedSecurityAuditQuery:
    """One acknowledged intent, validated bounded page, and buffered report."""

    intent: SecurityAuditAccessIntent
    input_cursor: SecurityAuditQueryCursor | None
    events: tuple[SecurityAuditEventReport, ...]
    next_cursor: SecurityAuditQueryCursor | None
    report_bytes: bytes


class _ConnectionInfo(Protocol):
    @property
    def transaction_status(self) -> TransactionStatus: ...


class _Cursor(Protocol):
    def fetchone(self) -> object: ...

    def fetchmany(self, size: int) -> list[object]: ...


class _Connection(Protocol):
    closed: bool
    autocommit: bool
    isolation_level: IsolationLevel | None

    @property
    def info(self) -> _ConnectionInfo: ...

    def execute(self, query: str, params: tuple[object, ...]) -> _Cursor: ...

    def rollback(self) -> None: ...

    def commit(self) -> None: ...

    def close(self) -> None: ...


class _ConnectionFactory(Protocol):
    def __call__(
        self,
        conninfo: str,
        *,
        autocommit: bool,
        connect_timeout: int,
        options: str,
    ) -> _Connection: ...


class _State(Enum):
    CONTROL_UNOPENED = auto()
    CONTROL_OPEN = auto()
    INTENT_RESULT_VALIDATED = auto()
    COMMITTING = auto()
    INTENT_ACKNOWLEDGED = auto()
    READER_OPEN = auto()
    QUERY_SUBMITTED = auto()
    REPORT_READY = auto()


def _render_report(
    intent: SecurityAuditAccessIntent,
    input_cursor: SecurityAuditQueryCursor | None,
    events: tuple[SecurityAuditEventReport, ...],
    next_cursor: SecurityAuditQueryCursor | None,
) -> bytes:
    document = {
        "accessEventId": str(intent.access_event_id),
        "dataCut": security_audit_timestamp_text(intent.data_cut),
        "events": [security_audit_event_document(event) for event in events],
        "expiresAt": security_audit_timestamp_text(intent.expires_at),
        "functionIdentity": QUERY_FUNCTION_IDENTITY,
        "inputCursor": None if input_cursor is None else input_cursor.render(),
        "maxBytes": QUERY_MAX_BYTES,
        "maxRows": QUERY_MAX_ROWS,
        "nextCursor": None if next_cursor is None else next_cursor.render(),
        "outcome": "ACKNOWLEDGED",
        "purpose": QUERY_ACCESS_PURPOSE_IDENTITY,
        "returnedRowCount": len(events),
        "schemaVersion": QUERY_REPORT_SCHEMA,
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


def _rollback_suppressed(connection: _Connection) -> None:
    try:
        connection.rollback()
    except Exception:
        pass


def _close_suppressed(connection: _Connection) -> None:
    try:
        connection.close()
    except Exception:
        pass


class SecurityAuditQueryRunner:
    """Commit one fixed intent, then execute one equal bounded query."""

    def __init__(
        self,
        connection_factory: _ConnectionFactory = cast(
            _ConnectionFactory, psycopg.connect
        ),
    ) -> None:
        self._connection_factory = connection_factory

    def run(
        self,
        control_conninfo: str,
        reader_conninfo: str,
        cursor: SecurityAuditQueryCursor | None,
    ) -> AcknowledgedSecurityAuditQuery:
        """Return only after intent acknowledgement and complete page validation."""

        state = _State.CONTROL_UNOPENED
        cursor_observed_at, cursor_event_id = security_audit_cursor_values(cursor)
        try:
            control = self._connection_factory(
                control_conninfo,
                autocommit=False,
                connect_timeout=QUERY_CONNECT_TIMEOUT_SECONDS,
                options=QUERY_CONTROL_CONNECTION_OPTIONS,
            )
            state = _State.CONTROL_OPEN
        except Exception:
            raise SecurityAuditQueryControlUnavailable from None

        try:
            if (
                control.closed is not False
                or control.autocommit is not False
                or control.info.transaction_status != TransactionStatus.IDLE
            ):
                raise ValueError("security-audit control connection is invalid")
            control.isolation_level = IsolationLevel.READ_COMMITTED
            intent_cursor = control.execute(
                ACCESS_INTENT_SQL,
                (
                    QUERY_ACCESS_PURPOSE_IDENTITY,
                    QUERY_FUNCTION_IDENTITY,
                    cursor_observed_at,
                    cursor_event_id,
                    QUERY_MAX_ROWS,
                    QUERY_MAX_BYTES,
                ),
            )
            intent = validate_security_audit_access_intent(
                intent_cursor.fetchone(), intent_cursor.fetchone()
            )
            reader_arguments: tuple[object, ...] = (
                intent.access_event_id,
                cursor_observed_at,
                cursor_event_id,
                QUERY_MAX_ROWS,
                QUERY_MAX_BYTES,
            )
            state = _State.INTENT_RESULT_VALIDATED
        except Exception:
            _rollback_suppressed(control)
            _close_suppressed(control)
            raise SecurityAuditQueryRefused from None
        except BaseException:
            _close_suppressed(control)
            raise

        try:
            state = _State.COMMITTING
            control.commit()
            state = _State.INTENT_ACKNOWLEDGED
        except Exception:
            _close_suppressed(control)
            raise SecurityAuditQueryOutcomeUnknown from None
        except BaseException:
            _close_suppressed(control)
            raise
        _close_suppressed(control)

        try:
            reader = self._connection_factory(
                reader_conninfo,
                autocommit=True,
                connect_timeout=QUERY_CONNECT_TIMEOUT_SECONDS,
                options=QUERY_READER_CONNECTION_OPTIONS,
            )
            state = _State.READER_OPEN
        except Exception:
            raise SecurityAuditQueryFailed from None

        try:
            if (
                reader.closed is not False
                or reader.autocommit is not True
                or reader.info.transaction_status != TransactionStatus.IDLE
            ):
                raise ValueError("security-audit reader connection is invalid")
            result_cursor = reader.execute(BOUNDED_QUERY_SQL, reader_arguments)
            state = _State.QUERY_SUBMITTED
            rows = result_cursor.fetchmany(QUERY_MAX_ROWS + 1)
            events, next_cursor = validate_security_audit_event_page(
                rows,
                intent=intent,
                input_cursor=cursor,
                maximum_rows=QUERY_MAX_ROWS,
            )
            report_bytes = _render_report(intent, cursor, events, next_cursor)
            state = _State.REPORT_READY
        except Exception:
            _close_suppressed(reader)
            raise SecurityAuditQueryFailed from None
        except BaseException:
            _close_suppressed(reader)
            raise
        _close_suppressed(reader)

        if state is not _State.REPORT_READY:
            raise SecurityAuditQueryFailed
        return AcknowledgedSecurityAuditQuery(
            intent=intent,
            input_cursor=cursor,
            events=events,
            next_cursor=next_cursor,
            report_bytes=report_bytes,
        )


__all__ = (
    "ACCESS_INTENT_SQL",
    "AcknowledgedSecurityAuditQuery",
    "BOUNDED_QUERY_SQL",
    "QUERY_CONNECT_TIMEOUT_SECONDS",
    "QUERY_CONTROL_CONNECTION_OPTIONS",
    "QUERY_READER_CONNECTION_OPTIONS",
    "QUERY_REPORT_SCHEMA",
    "SecurityAuditAccessIntent",
    "SecurityAuditEventReport",
    "SecurityAuditQueryControlUnavailable",
    "SecurityAuditQueryCursor",
    "SecurityAuditQueryError",
    "SecurityAuditQueryFailed",
    "SecurityAuditQueryOutcomeUnknown",
    "SecurityAuditQueryRefused",
    "SecurityAuditQueryRunner",
)
