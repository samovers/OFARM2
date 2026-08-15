"""One-shot overflow closure for the isolated security-audit store.

PostgreSQL remains the sole authority for bucket selection, closeability,
writer serialization, count posture, event identity, high-water advancement,
and receipt handling.  This module owns only one explicit observation/closure
transaction and its bounded outcome protocol.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import NoReturn, Protocol, cast
from uuid import UUID

import psycopg
from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus

from deployment.postgresql.audit_contract import (
    QUOTA_BUCKET_SECONDS,
    RETENTION_SECONDS,
    SECURITY_AUDIT_CONTRACT,
)


OBSERVE_OVERFLOW_SQL = (
    "SELECT * FROM "
    "ofarm_security.observe_next_closeable_overflow_bucket()"
)
CLOSE_OVERFLOW_SQL = (
    "SELECT * FROM "
    "ofarm_security.close_overflow_bucket(%s, %s, %s)"
)
OVERFLOW_CONNECT_TIMEOUT_SECONDS = 5
OVERFLOW_CONNECTION_OPTIONS = (
    "-c statement_timeout=5000 "
    "-c lock_timeout=500 "
    "-c idle_in_transaction_session_timeout=10000 "
    "-c transaction_timeout=15000 "
    "-c work_mem=1024kB "
    "-c TimeZone=UTC "
    "-c DateStyle=ISO,MDY "
    "-c synchronous_commit=on"
)
OVERFLOW_REPORT_SCHEMA = (
    "ofarm.security-audit-overflow-closure-report.v1"
)

_PRETENANT_PAIRS = frozenset(
    (entry.producer, entry.component)
    for entry in SECURITY_AUDIT_CONTRACT.reason_matrix
)
_BUCKET_INTERVAL = timedelta(seconds=QUOTA_BUCKET_SECONDS)
_BUCKET_ANCHOR = datetime(2000, 1, 1, tzinfo=timezone.utc)


class SecurityAuditOverflowError(RuntimeError):
    """Base class for one closed overflow-closure outcome."""


class SecurityAuditOverflowRefused(SecurityAuditOverflowError):
    """The route returned, but no commit became ambiguous."""


class SecurityAuditOverflowUnavailable(SecurityAuditOverflowError):
    """The route was unavailable and no commit was sent."""


class SecurityAuditOverflowOutcomeUnknown(SecurityAuditOverflowError):
    """Commit raised, so the closure transaction outcome is unknown."""


@dataclass(frozen=True, slots=True)
class SecurityAuditOverflowBucket:
    """One validated database-selected overflow bucket identity."""

    producer: str
    component: str
    bucket_start: datetime


@dataclass(frozen=True, slots=True)
class SecurityAuditOverflowClosureResult:
    """One validated database-owned overflow closure identity."""

    bucket: SecurityAuditOverflowBucket
    overflow_ended_event_id: UUID
    observed_at: datetime
    purge_after: datetime


@dataclass(frozen=True, slots=True)
class CompletedSecurityAuditOverflowRun:
    """A known no-bucket or acknowledged closure and its fixed report."""

    result: SecurityAuditOverflowClosureResult | None
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
        connect_timeout: int,
        options: str,
    ) -> _Connection: ...


class _State(Enum):
    NOT_SUBMITTED = auto()
    OBSERVATION_SUBMITTED = auto()
    EMPTY_OBSERVED = auto()
    ROLLING_BACK = auto()
    NO_BUCKET_COMPLETE = auto()
    BUCKET_OBSERVED = auto()
    CLOSE_SUBMITTED = auto()
    CLOSE_RESULT_OBSERVED = auto()
    REPORT_RENDERED = auto()
    COMMITTING = auto()
    ACKNOWLEDGED = auto()


def _utc_timestamp(value: object) -> datetime:
    if type(value) is not datetime or value.utcoffset() is None:
        raise ValueError("overflow timestamp is invalid")
    return value.astimezone(timezone.utc)


def _validated_bucket(
    row: object,
    second_row: object,
) -> SecurityAuditOverflowBucket | None:
    if row is None:
        if second_row is not None:
            raise ValueError("overflow observation shape is invalid")
        return None
    if type(row) is not tuple or len(row) != 3 or second_row is not None:
        raise ValueError("overflow observation shape is invalid")
    producer, component, bucket_start = row
    if (
        type(producer) is not str
        or type(component) is not str
        or (producer, component) not in _PRETENANT_PAIRS
    ):
        raise ValueError("overflow observation pair is invalid")
    normalized_bucket_start = _utc_timestamp(bucket_start)
    if (normalized_bucket_start - _BUCKET_ANCHOR) % _BUCKET_INTERVAL:
        raise ValueError("overflow observation bucket is misaligned")
    return SecurityAuditOverflowBucket(
        producer=producer,
        component=component,
        bucket_start=normalized_bucket_start,
    )


def _validated_closure_result(
    bucket: SecurityAuditOverflowBucket,
    row: object,
    second_row: object,
) -> SecurityAuditOverflowClosureResult:
    if type(row) is not tuple or len(row) != 3 or second_row is not None:
        raise ValueError("overflow closure result shape is invalid")
    event_id, observed_at, purge_after = row
    normalized_observed_at = _utc_timestamp(observed_at)
    normalized_purge_after = _utc_timestamp(purge_after)
    if (
        type(event_id) is not UUID
        or event_id.int == 0
        or normalized_purge_after
        != normalized_observed_at + timedelta(seconds=RETENTION_SECONDS)
    ):
        raise ValueError("overflow closure result values are invalid")
    return SecurityAuditOverflowClosureResult(
        bucket=bucket,
        overflow_ended_event_id=event_id,
        observed_at=normalized_observed_at,
        purge_after=normalized_purge_after,
    )


def _canonical_report(document: dict[str, object]) -> bytes:
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


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


NO_CLOSEABLE_BUCKET_REPORT = _canonical_report(
    {
        "outcome": "NO_CLOSEABLE_BUCKET",
        "schema": OVERFLOW_REPORT_SCHEMA,
    }
)


def _render_closure_report(result: SecurityAuditOverflowClosureResult) -> bytes:
    return _canonical_report(
        {
            "bucketStart": _timestamp(result.bucket.bucket_start),
            "component": result.bucket.component,
            "observedAt": _timestamp(result.observed_at),
            "outcome": "ACKNOWLEDGED",
            "overflowEndedEventId": str(result.overflow_ended_event_id),
            "producer": result.bucket.producer,
            "purgeAfter": _timestamp(result.purge_after),
            "schema": OVERFLOW_REPORT_SCHEMA,
        }
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


def _raise_precommit_failure(error: Exception) -> NoReturn:
    if _is_transport_failure(error):
        raise SecurityAuditOverflowUnavailable from None
    raise SecurityAuditOverflowRefused from None


class SecurityAuditOverflowRunner:
    """Observe and close at most one database-selected overflow bucket."""

    def __init__(
        self,
        connection_factory: _ConnectionFactory = cast(
            _ConnectionFactory, psycopg.connect
        ),
    ) -> None:
        self._connection_factory = connection_factory

    def run(self, conninfo: str) -> CompletedSecurityAuditOverflowRun:
        """Return only a known no-bucket or acknowledged closure result."""

        state = _State.NOT_SUBMITTED
        try:
            connection = self._connection_factory(
                conninfo,
                autocommit=False,
                connect_timeout=OVERFLOW_CONNECT_TIMEOUT_SECONDS,
                options=OVERFLOW_CONNECTION_OPTIONS,
            )
        except Exception:
            raise SecurityAuditOverflowUnavailable from None

        try:
            if (
                connection.closed is not False
                or connection.autocommit is not False
                or connection.info.transaction_status != TransactionStatus.IDLE
            ):
                raise ValueError("overflow connection state is invalid")
            connection.isolation_level = IsolationLevel.READ_COMMITTED
        except Exception as exc:
            _close_suppressed(connection)
            _raise_precommit_failure(exc)
        except BaseException:
            _close_suppressed(connection)
            raise

        try:
            state = _State.OBSERVATION_SUBMITTED
            observation = connection.execute(OBSERVE_OVERFLOW_SQL)
            observed_row = observation.fetchone()
            observed_second_row = observation.fetchone()
            bucket = _validated_bucket(observed_row, observed_second_row)
        except Exception as exc:
            _rollback_suppressed(connection)
            _close_suppressed(connection)
            _raise_precommit_failure(exc)
        except BaseException:
            _close_suppressed(connection)
            raise

        if bucket is None:
            state = _State.EMPTY_OBSERVED
            try:
                state = _State.ROLLING_BACK
                connection.rollback()
                state = _State.NO_BUCKET_COMPLETE
            except Exception as exc:
                _close_suppressed(connection)
                _raise_precommit_failure(exc)
            except BaseException:
                _close_suppressed(connection)
                raise
            _close_suppressed(connection)
            return CompletedSecurityAuditOverflowRun(
                result=None,
                report_bytes=NO_CLOSEABLE_BUCKET_REPORT,
            )

        state = _State.BUCKET_OBSERVED
        try:
            state = _State.CLOSE_SUBMITTED
            closure = connection.execute(
                CLOSE_OVERFLOW_SQL,
                (bucket.producer, bucket.component, bucket.bucket_start),
            )
            closure_row = closure.fetchone()
            closure_second_row = closure.fetchone()
            result = _validated_closure_result(
                bucket,
                closure_row,
                closure_second_row,
            )
            state = _State.CLOSE_RESULT_OBSERVED
            report_bytes = _render_closure_report(result)
            state = _State.REPORT_RENDERED
        except Exception as exc:
            _rollback_suppressed(connection)
            _close_suppressed(connection)
            _raise_precommit_failure(exc)
        except BaseException:
            _close_suppressed(connection)
            raise

        try:
            state = _State.COMMITTING
            connection.commit()
            state = _State.ACKNOWLEDGED
        except Exception:
            _close_suppressed(connection)
            raise SecurityAuditOverflowOutcomeUnknown from None
        except BaseException:
            _close_suppressed(connection)
            raise

        _close_suppressed(connection)
        if state is not _State.ACKNOWLEDGED:
            raise SecurityAuditOverflowOutcomeUnknown
        return CompletedSecurityAuditOverflowRun(
            result=result,
            report_bytes=report_bytes,
        )


__all__ = (
    "CLOSE_OVERFLOW_SQL",
    "CompletedSecurityAuditOverflowRun",
    "NO_CLOSEABLE_BUCKET_REPORT",
    "OBSERVE_OVERFLOW_SQL",
    "OVERFLOW_CONNECTION_OPTIONS",
    "OVERFLOW_CONNECT_TIMEOUT_SECONDS",
    "OVERFLOW_REPORT_SCHEMA",
    "SecurityAuditOverflowBucket",
    "SecurityAuditOverflowClosureResult",
    "SecurityAuditOverflowError",
    "SecurityAuditOverflowOutcomeUnknown",
    "SecurityAuditOverflowRefused",
    "SecurityAuditOverflowRunner",
    "SecurityAuditOverflowUnavailable",
)
