"""One-shot logical retention execution for the isolated security-audit store.

PostgreSQL remains the sole authority for the cutoff, victim selection,
bounded deletion, disposable-state cleanup, retention identity, and atomic
maintenance event.  This module owns only one explicit submission and its
transaction outcome protocol.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import Protocol, cast
from uuid import UUID

import psycopg
from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus

from deployment.postgresql.audit_contract import (
    PURGE_BATCH_ROWS,
    RETENTION_SECONDS,
)


RETENTION_SQL = (
    "SELECT * FROM "
    "ofarm_security.purge_expired_operational_security_events()"
)
RETENTION_CONNECT_TIMEOUT_SECONDS = 5
RETENTION_CONNECTION_OPTIONS = (
    "-c statement_timeout=15000 "
    "-c lock_timeout=500 "
    "-c idle_in_transaction_session_timeout=10000 "
    "-c transaction_timeout=30000 "
    "-c synchronous_commit=on"
)


class SecurityAuditRetentionError(RuntimeError):
    """Base class for one closed retention outcome."""


class SecurityAuditRetentionRefused(SecurityAuditRetentionError):
    """The transaction was not submitted or was rolled back before commit."""


class SecurityAuditRetentionUnavailable(SecurityAuditRetentionError):
    """The route was unavailable and no commit was sent."""


class SecurityAuditRetentionOutcomeUnknown(SecurityAuditRetentionError):
    """Commit raised, so the destructive transaction outcome is unknown."""


@dataclass(frozen=True, slots=True)
class SecurityAuditRetentionResult:
    """The five validated values returned by the database-owned transition."""

    cutoff: datetime
    deleted_count: int
    retention_event_id: UUID
    observed_at: datetime
    purge_after: datetime


@dataclass(frozen=True, slots=True)
class AcknowledgedSecurityAuditRetention:
    """A normally committed result and its pre-rendered success report."""

    result: SecurityAuditRetentionResult
    report_bytes: bytes


class _ConnectionInfo(Protocol):
    @property
    def transaction_status(self) -> TransactionStatus: ...


class _Cursor(Protocol):
    def fetchone(self) -> object: ...


class _Connection(Protocol):
    closed: bool
    autocommit: bool
    isolation_level: IsolationLevel | None

    @property
    def info(self) -> _ConnectionInfo: ...

    def execute(self, query: str) -> _Cursor: ...

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
    NOT_SUBMITTED = auto()
    SUBMITTED = auto()
    RESULT_OBSERVED = auto()
    COMMITTING = auto()
    ACKNOWLEDGED = auto()


def _utc_timestamp(value: object) -> datetime:
    if type(value) is not datetime or value.utcoffset() is None:
        raise ValueError("retention timestamp is invalid")
    return value.astimezone(timezone.utc)


def _validated_result(row: object, second_row: object) -> SecurityAuditRetentionResult:
    if type(row) is not tuple or len(row) != 5 or second_row is not None:
        raise ValueError("retention result shape is invalid")
    cutoff, deleted_count, event_id, observed_at, purge_after = row
    normalized_cutoff = _utc_timestamp(cutoff)
    normalized_observed_at = _utc_timestamp(observed_at)
    normalized_purge_after = _utc_timestamp(purge_after)
    if (
        type(deleted_count) is not int
        or not 0 <= deleted_count <= PURGE_BATCH_ROWS
        or type(event_id) is not UUID
        or event_id.int == 0
        or normalized_purge_after
        != normalized_observed_at + timedelta(seconds=RETENTION_SECONDS)
    ):
        raise ValueError("retention result values are invalid")
    return SecurityAuditRetentionResult(
        cutoff=normalized_cutoff,
        deleted_count=deleted_count,
        retention_event_id=event_id,
        observed_at=normalized_observed_at,
        purge_after=normalized_purge_after,
    )


def _render_report(result: SecurityAuditRetentionResult) -> bytes:
    def timestamp(value: datetime) -> str:
        return value.isoformat(timespec="microseconds").replace("+00:00", "Z")

    document = {
        "cutoff": timestamp(result.cutoff),
        "deletedCount": result.deleted_count,
        "observedAt": timestamp(result.observed_at),
        "outcome": "ACKNOWLEDGED",
        "purgeAfter": timestamp(result.purge_after),
        "retentionEventId": str(result.retention_event_id),
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


def _is_transport_failure(error: Exception) -> bool:
    if not isinstance(error, psycopg.OperationalError):
        return False
    sqlstate = error.sqlstate
    return sqlstate is None or sqlstate.startswith("08")


class SecurityAuditRetentionRunner:
    """Submit one fixed retention transaction through one connection factory."""

    def __init__(
        self,
        connection_factory: _ConnectionFactory = cast(
            _ConnectionFactory, psycopg.connect
        ),
    ) -> None:
        self._connection_factory = connection_factory

    def run(self, conninfo: str) -> AcknowledgedSecurityAuditRetention:
        """Run one batch and return only after explicit commit acknowledgement."""

        state = _State.NOT_SUBMITTED
        try:
            connection = self._connection_factory(
                conninfo,
                autocommit=False,
                connect_timeout=RETENTION_CONNECT_TIMEOUT_SECONDS,
                options=RETENTION_CONNECTION_OPTIONS,
            )
        except Exception:
            raise SecurityAuditRetentionUnavailable from None

        try:
            if (
                connection.closed is not False
                or connection.autocommit is not False
                or connection.info.transaction_status != TransactionStatus.IDLE
            ):
                raise ValueError("retention connection state is invalid")
            connection.isolation_level = IsolationLevel.READ_COMMITTED
        except Exception as exc:
            _close_suppressed(connection)
            if _is_transport_failure(exc):
                raise SecurityAuditRetentionUnavailable from None
            raise SecurityAuditRetentionRefused from None

        try:
            state = _State.SUBMITTED
            cursor = connection.execute(RETENTION_SQL)
            row = cursor.fetchone()
            second_row = cursor.fetchone()
            result = _validated_result(row, second_row)
            state = _State.RESULT_OBSERVED
            report_bytes = _render_report(result)
        except Exception as exc:
            _rollback_suppressed(connection)
            _close_suppressed(connection)
            if _is_transport_failure(exc):
                raise SecurityAuditRetentionUnavailable from None
            raise SecurityAuditRetentionRefused from None
        except BaseException:
            _close_suppressed(connection)
            raise

        try:
            state = _State.COMMITTING
            connection.commit()
            state = _State.ACKNOWLEDGED
        except Exception:
            _close_suppressed(connection)
            raise SecurityAuditRetentionOutcomeUnknown from None
        except BaseException:
            _close_suppressed(connection)
            raise

        _close_suppressed(connection)
        if state is not _State.ACKNOWLEDGED:
            raise SecurityAuditRetentionOutcomeUnknown
        return AcknowledgedSecurityAuditRetention(
            result=result,
            report_bytes=report_bytes,
        )


__all__ = (
    "AcknowledgedSecurityAuditRetention",
    "RETENTION_CONNECTION_OPTIONS",
    "RETENTION_CONNECT_TIMEOUT_SECONDS",
    "RETENTION_SQL",
    "SecurityAuditRetentionError",
    "SecurityAuditRetentionOutcomeUnknown",
    "SecurityAuditRetentionRefused",
    "SecurityAuditRetentionResult",
    "SecurityAuditRetentionRunner",
    "SecurityAuditRetentionUnavailable",
)
