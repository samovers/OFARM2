"""Library-only one-page security-audit bounded export execution.

The runner commits one fixed export access intent and, only after that commit
is acknowledged, invokes the existing bounded export function once.  It does
not create credentials, choose roles, verify approvals, write output, retry,
resume, or implement the temporary break-glass lifecycle.
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
    EXPORT_ACCESS_PURPOSE_IDENTITY,
    EXPORT_FUNCTION_IDENTITY,
    EXPORT_MAX_BYTES,
    EXPORT_MAX_ROWS,
)
from deployment.postgresql.security_audit_access import (
    SecurityAuditAccessCursor,
    SecurityAuditAccessIntent,
    SecurityAuditEventReport,
    security_audit_cursor_values,
    security_audit_event_document,
    security_audit_timestamp_text,
    validate_security_audit_access_intent,
    validate_security_audit_event_page,
)


EXPORT_ACCESS_INTENT_SQL = (
    "SELECT * FROM ofarm_security.commit_audit_access_intent("
    "%s, %s, %s, %s, %s, %s)"
)
BOUNDED_EXPORT_SQL = (
    "SELECT * FROM ofarm_security.export_operational_security_events("
    "%s, %s, %s, %s, %s)"
)
EXPORT_CONNECT_TIMEOUT_SECONDS = 5
EXPORT_CONNECTION_OPTIONS = (
    "-c statement_timeout=5000 "
    "-c lock_timeout=500 "
    "-c idle_in_transaction_session_timeout=10000 "
    "-c transaction_timeout=15000 "
    "-c work_mem=1024kB "
    "-c bytea_output=hex "
    "-c TimeZone=UTC "
    "-c DateStyle=ISO,MDY"
)
EXPORT_CONTROL_CONNECTION_OPTIONS = (
    EXPORT_CONNECTION_OPTIONS + " -c synchronous_commit=on"
)
EXPORT_PAGE_SCHEMA = "ofarm.security-audit-bounded-export-page.v1"


class SecurityAuditExportError(RuntimeError):
    """Base class for one closed bounded-export outcome."""


class SecurityAuditExportRefused(SecurityAuditExportError):
    """Preflight or the pre-commit control transaction was refused."""


class SecurityAuditExportControlUnavailable(SecurityAuditExportError):
    """The control factory failed before returning a connection."""


class SecurityAuditExportOutcomeUnknown(SecurityAuditExportError):
    """The explicit access-intent commit raised and must not be retried."""


class SecurityAuditExportFailed(SecurityAuditExportError):
    """The intent committed, but no complete validated page is available."""


@dataclass(frozen=True, slots=True)
class AcknowledgedSecurityAuditExport:
    """One acknowledged intent and one completely buffered export page."""

    intent: SecurityAuditAccessIntent
    input_cursor: SecurityAuditAccessCursor | None
    events: tuple[SecurityAuditEventReport, ...]
    next_cursor: SecurityAuditAccessCursor | None
    page_bytes: bytes


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
    EXPORT_OPEN = auto()
    EXPORT_SUBMITTED = auto()
    PAGE_READY = auto()


def _preflight_routes(
    control_conninfo: object,
    export_conninfo: object,
    cursor: object,
) -> tuple[str, str, SecurityAuditAccessCursor | None]:
    refused = False
    try:
        if type(control_conninfo) is not str or not control_conninfo.strip():
            raise ValueError("security-audit control route is invalid")
        psycopg.conninfo.conninfo_to_dict(control_conninfo)
        if type(export_conninfo) is not str or not export_conninfo.strip():
            raise ValueError("security-audit export route is invalid")
        psycopg.conninfo.conninfo_to_dict(export_conninfo)
        if cursor is not None and type(cursor) is not SecurityAuditAccessCursor:
            raise ValueError("security-audit cursor is invalid")
    except Exception:
        refused = True
    if refused:
        raise SecurityAuditExportRefused()
    return (
        cast(str, control_conninfo),
        cast(str, export_conninfo),
        cast(SecurityAuditAccessCursor | None, cursor),
    )


def _render_page(
    intent: SecurityAuditAccessIntent,
    input_cursor: SecurityAuditAccessCursor | None,
    events: tuple[SecurityAuditEventReport, ...],
    next_cursor: SecurityAuditAccessCursor | None,
) -> bytes:
    document = {
        "accessEventId": str(intent.access_event_id),
        "dataCut": security_audit_timestamp_text(intent.data_cut),
        "events": [security_audit_event_document(event) for event in events],
        "expiresAt": security_audit_timestamp_text(intent.expires_at),
        "functionIdentity": EXPORT_FUNCTION_IDENTITY,
        "inputCursor": None if input_cursor is None else input_cursor.render(),
        "maxBytes": EXPORT_MAX_BYTES,
        "maxRows": EXPORT_MAX_ROWS,
        "nextCursor": None if next_cursor is None else next_cursor.render(),
        "outcome": "ACKNOWLEDGED",
        "purpose": EXPORT_ACCESS_PURPOSE_IDENTITY,
        "returnedRowCount": len(events),
        "schemaVersion": EXPORT_PAGE_SCHEMA,
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


class SecurityAuditExportRunner:
    """Commit one fixed intent, then return one equal bounded export page."""

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
        export_conninfo: str,
        cursor: SecurityAuditAccessCursor | None,
    ) -> AcknowledgedSecurityAuditExport:
        """Return only after one intent and one page are fully acknowledged."""

        state = _State.CONTROL_UNOPENED
        control_conninfo, export_conninfo, cursor = _preflight_routes(
            control_conninfo,
            export_conninfo,
            cursor,
        )
        cursor_observed_at, cursor_event_id = security_audit_cursor_values(cursor)

        control_unavailable = False
        try:
            control = self._connection_factory(
                control_conninfo,
                autocommit=False,
                connect_timeout=EXPORT_CONNECT_TIMEOUT_SECONDS,
                options=EXPORT_CONTROL_CONNECTION_OPTIONS,
            )
            state = _State.CONTROL_OPEN
        except Exception:
            control_unavailable = True
        if control_unavailable:
            raise SecurityAuditExportControlUnavailable()

        control_refused = False
        try:
            if (
                control.closed is not False
                or control.autocommit is not False
                or control.info.transaction_status != TransactionStatus.IDLE
            ):
                raise ValueError("security-audit control connection is invalid")
            control.isolation_level = IsolationLevel.READ_COMMITTED
            intent_cursor = control.execute(
                EXPORT_ACCESS_INTENT_SQL,
                (
                    EXPORT_ACCESS_PURPOSE_IDENTITY,
                    EXPORT_FUNCTION_IDENTITY,
                    cursor_observed_at,
                    cursor_event_id,
                    EXPORT_MAX_ROWS,
                    EXPORT_MAX_BYTES,
                ),
            )
            intent = validate_security_audit_access_intent(
                intent_cursor.fetchone(), intent_cursor.fetchone()
            )
            export_arguments: tuple[object, ...] = (
                intent.access_event_id,
                cursor_observed_at,
                cursor_event_id,
                EXPORT_MAX_ROWS,
                EXPORT_MAX_BYTES,
            )
            state = _State.INTENT_RESULT_VALIDATED
        except Exception:
            _rollback_suppressed(control)
            _close_suppressed(control)
            control_refused = True
        except BaseException:
            _close_suppressed(control)
            raise
        if control_refused:
            raise SecurityAuditExportRefused()

        outcome_unknown = False
        try:
            state = _State.COMMITTING
            control.commit()
            state = _State.INTENT_ACKNOWLEDGED
        except Exception:
            _close_suppressed(control)
            outcome_unknown = True
        except BaseException:
            _close_suppressed(control)
            raise
        if outcome_unknown:
            raise SecurityAuditExportOutcomeUnknown()
        _close_suppressed(control)

        export_failed = False
        try:
            exporter = self._connection_factory(
                export_conninfo,
                autocommit=True,
                connect_timeout=EXPORT_CONNECT_TIMEOUT_SECONDS,
                options=EXPORT_CONNECTION_OPTIONS,
            )
            state = _State.EXPORT_OPEN
        except Exception:
            export_failed = True
        if export_failed:
            raise SecurityAuditExportFailed()

        page_failed = False
        try:
            if (
                exporter.closed is not False
                or exporter.autocommit is not True
                or exporter.info.transaction_status != TransactionStatus.IDLE
            ):
                raise ValueError("security-audit export connection is invalid")
            result_cursor = exporter.execute(BOUNDED_EXPORT_SQL, export_arguments)
            state = _State.EXPORT_SUBMITTED
            rows = result_cursor.fetchmany(EXPORT_MAX_ROWS + 1)
            events, next_cursor = validate_security_audit_event_page(
                rows,
                intent=intent,
                input_cursor=cursor,
                maximum_rows=EXPORT_MAX_ROWS,
            )
            page_bytes = _render_page(intent, cursor, events, next_cursor)
            state = _State.PAGE_READY
        except Exception:
            _close_suppressed(exporter)
            page_failed = True
        except BaseException:
            _close_suppressed(exporter)
            raise
        if page_failed:
            raise SecurityAuditExportFailed()
        _close_suppressed(exporter)

        if state is not _State.PAGE_READY:
            raise SecurityAuditExportFailed()
        return AcknowledgedSecurityAuditExport(
            intent=intent,
            input_cursor=cursor,
            events=events,
            next_cursor=next_cursor,
            page_bytes=page_bytes,
        )


__all__ = (
    "AcknowledgedSecurityAuditExport",
    "BOUNDED_EXPORT_SQL",
    "EXPORT_ACCESS_INTENT_SQL",
    "EXPORT_CONNECTION_OPTIONS",
    "EXPORT_CONNECT_TIMEOUT_SECONDS",
    "EXPORT_CONTROL_CONNECTION_OPTIONS",
    "EXPORT_PAGE_SCHEMA",
    "SecurityAuditExportControlUnavailable",
    "SecurityAuditExportError",
    "SecurityAuditExportFailed",
    "SecurityAuditExportOutcomeUnknown",
    "SecurityAuditExportRefused",
    "SecurityAuditExportRunner",
)
