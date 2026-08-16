"""Bounded live-process reconciliation of pre-tenant audit gaps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, auto
from threading import Lock
from typing import Protocol, cast
from uuid import UUID

import psycopg
from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus

from deployment.postgresql.audit_contract import RETENTION_SECONDS

from .security_audit import (
    OverflowAuditAppend,
    OverflowBucket,
    SecurityAuditAppend,
    SecurityAuditRefused,
    SecurityAuditUnavailable,
    StoredAuditAppend,
)


AUDIT_CONTROL_LOGIN = "ofarm_security_audit_control_login"
GAP_CONNECT_TIMEOUT_SECONDS = 5
GAP_CONNECTION_OPTIONS = (
    "-c statement_timeout=2000 "
    "-c lock_timeout=250 "
    "-c synchronous_commit=on"
)
SIGNED_BIGINT_MAX = 9_223_372_036_854_775_807

_INITIALIZE_TRANSACTION = (
    "SET TRANSACTION ISOLATION LEVEL READ COMMITTED READ ONLY"
)
_INITIALIZE = (
    "SELECT session_user::text, "
    "current_setting('synchronous_commit'), clock_timestamp()"
)
_AUTHORITY = (
    "SELECT session_user::text, current_setting('synchronous_commit')"
)
_CLOCK = "SELECT clock_timestamp()"
_APPEND = (
    "SELECT * FROM ofarm_security.append_audit_gap(%s, %s, %s, %s)"
)


class SecurityAuditGapError(RuntimeError):
    """Base class for the fixed live-gap failure surface."""


class SecurityAuditGapUnavailable(SecurityAuditGapError):
    """Gap reconciliation failed before commit began."""

    def __init__(self) -> None:
        super().__init__("security audit gap reconciliation is unavailable")


class SecurityAuditGapOutcomeUnknown(SecurityAuditGapError):
    """A gap transaction commit returned an ambiguous outcome."""

    def __init__(self) -> None:
        super().__init__(
            "security audit gap reconciliation outcome is unknown"
        )


class SecurityAuditGapState(str, Enum):
    """Fixed non-sensitive controller state exposed only to local callers."""

    CLEAR = "CLEAR"
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class _Lane(Enum):
    AUTHENTICATION = "AUTHENTICATION"
    REQUEST_ROUTER = "REQUEST_ROUTER"


class _ControllerPhase(Enum):
    ACTIVE = auto()
    COMMIT_OUTCOME_UNKNOWN = auto()
    SEQUENCE_EXHAUSTED = auto()


class _TransactionPhase(Enum):
    PRE_COMMIT = auto()
    COMMIT_IN_FLIGHT = auto()
    COMMIT_ACKNOWLEDGED = auto()


@dataclass(frozen=True, slots=True)
class _Ticket:
    lane: _Lane
    number: int
    anchor: datetime


@dataclass(frozen=True, slots=True)
class _LaneProgress:
    greatest_failure: int
    recovery: int | None


@dataclass(slots=True)
class _Accumulator:
    interval_start: datetime
    exact_count: int | None
    authentication: _LaneProgress | None
    request_router: _LaneProgress | None


@dataclass(frozen=True, slots=True)
class _GapSnapshot:
    interval_start: datetime
    exact_count: int | None
    authentication: _LaneProgress | None
    request_router: _LaneProgress | None

    @property
    def event_count(self) -> int:
        return 0 if self.exact_count is None else self.exact_count

    @property
    def count_unknown(self) -> bool:
        return self.exact_count is None


class AuditSink(Protocol):
    def append(self, reason: str) -> SecurityAuditAppend: ...


class _Cursor(Protocol):
    def fetchone(self) -> object: ...


class _ConnectionInfo(Protocol):
    @property
    def transaction_status(self) -> TransactionStatus: ...


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


class ConnectionFactory(Protocol):
    def __call__(
        self,
        conninfo: str,
        *,
        autocommit: bool,
        connect_timeout: int,
        options: str,
    ) -> _Connection: ...


class GapClient(Protocol):
    def initialize(self) -> datetime: ...

    def append(self, snapshot: _GapSnapshot) -> datetime: ...


def _aware_time(value: object) -> datetime:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("security-audit gap timestamp is invalid")
    return value


def _single_row(cursor: _Cursor) -> object:
    row = cursor.fetchone()
    if cursor.fetchone() is not None:
        raise ValueError("security-audit gap result has duplicate rows")
    return row


def _bounded_sum(left: int | None, right: int | None) -> int | None:
    if left is None or right is None or left > SIGNED_BIGINT_MAX - right:
        return None
    return left + right


def _next_sequence(current: int) -> int | None:
    if type(current) is not int or not 0 <= current < SIGNED_BIGINT_MAX:
        return None
    return current + 1


def _progress(
    accumulator: _Accumulator | _GapSnapshot,
    lane: _Lane,
) -> _LaneProgress | None:
    if lane is _Lane.AUTHENTICATION:
        return accumulator.authentication
    return accumulator.request_router


def _replace_progress(
    accumulator: _Accumulator,
    lane: _Lane,
    progress: _LaneProgress,
) -> None:
    if lane is _Lane.AUTHENTICATION:
        accumulator.authentication = progress
    else:
        accumulator.request_router = progress


def _merged_progress(
    closing: _LaneProgress | None,
    concurrent: _LaneProgress | None,
) -> _LaneProgress | None:
    if concurrent is None:
        return closing
    if closing is None:
        return concurrent
    failure = max(closing.greatest_failure, concurrent.greatest_failure)
    recovery = concurrent.recovery
    if recovery is None or recovery <= failure:
        recovery = None
    return _LaneProgress(failure, recovery)


def _merge(
    closing: _GapSnapshot,
    concurrent: _Accumulator | None,
) -> _Accumulator:
    if concurrent is None:
        return _Accumulator(
            closing.interval_start,
            closing.exact_count,
            closing.authentication,
            closing.request_router,
        )
    return _Accumulator(
        min(closing.interval_start, concurrent.interval_start),
        _bounded_sum(closing.exact_count, concurrent.exact_count),
        _merged_progress(closing.authentication, concurrent.authentication),
        _merged_progress(closing.request_router, concurrent.request_router),
    )


def _snapshot(accumulator: _Accumulator) -> _GapSnapshot:
    return _GapSnapshot(
        accumulator.interval_start,
        accumulator.exact_count,
        accumulator.authentication,
        accumulator.request_router,
    )


def _eligible(accumulator: _Accumulator) -> bool:
    affected = (
        accumulator.authentication,
        accumulator.request_router,
    )
    return all(
        progress is None
        or (
            progress.recovery is not None
            and progress.recovery > progress.greatest_failure
        )
        for progress in affected
    )


def _result_anchor(result: SecurityAuditAppend) -> datetime:
    if type(result) is StoredAuditAppend:
        return _aware_time(result.observed_at)
    if (
        type(result) is OverflowAuditAppend
        and type(result.bucket) is OverflowBucket
    ):
        return _aware_time(result.bucket.bucket_start)
    raise ValueError("security-audit gap producer result is invalid")


def _close_suppressed(connection: _Connection) -> None:
    try:
        connection.close()
    except Exception:
        pass


def _rollback_suppressed(connection: _Connection) -> None:
    try:
        connection.rollback()
    except Exception:
        pass


class SecurityAuditGapClient:
    """One fixed audit-control route for anchors and gap insertion."""

    __slots__ = ("_conninfo", "_connection_factory")

    def __init__(
        self,
        conninfo: str,
        *,
        connection_factory: ConnectionFactory = cast(
            ConnectionFactory, psycopg.connect
        ),
    ) -> None:
        self._conninfo = conninfo
        self._connection_factory = connection_factory

    def _connect(self) -> _Connection:
        return self._connection_factory(
            self._conninfo,
            autocommit=False,
            connect_timeout=GAP_CONNECT_TIMEOUT_SECONDS,
            options=GAP_CONNECTION_OPTIONS,
        )

    @staticmethod
    def _prepare(connection: _Connection) -> None:
        if (
            connection.closed is not False
            or connection.autocommit is not False
            or connection.info.transaction_status is not TransactionStatus.IDLE
        ):
            raise ValueError("security-audit gap connection state is invalid")
        connection.isolation_level = IsolationLevel.READ_COMMITTED
        if connection.isolation_level is not IsolationLevel.READ_COMMITTED:
            raise ValueError("security-audit gap isolation is invalid")

    def initialize(self) -> datetime:
        connection: _Connection | None = None
        anchor: datetime | None = None
        failed = False
        try:
            connection = self._connect()
            self._prepare(connection)
            connection.execute(_INITIALIZE_TRANSACTION)
            row = _single_row(connection.execute(_INITIALIZE))
            if type(row) is not tuple or len(row) != 3:
                raise ValueError("security-audit gap anchor shape is invalid")
            session_user, synchronous_commit, value = row
            if (
                session_user != AUDIT_CONTROL_LOGIN
                or synchronous_commit != "on"
            ):
                raise ValueError("security-audit gap anchor authority is invalid")
            anchor = _aware_time(value)
            connection.rollback()
        except Exception:
            failed = True
        except BaseException:
            if connection is not None:
                _close_suppressed(connection)
            raise
        if connection is not None:
            if failed:
                _rollback_suppressed(connection)
            try:
                connection.close()
            except Exception:
                failed = True
        if failed or anchor is None:
            raise SecurityAuditGapUnavailable()
        return anchor

    def append(self, snapshot: _GapSnapshot) -> datetime:
        if type(snapshot) is not _GapSnapshot:
            raise ValueError("security-audit gap snapshot is invalid")
        connection: _Connection | None = None
        observed_at: datetime | None = None
        phase = _TransactionPhase.PRE_COMMIT
        failed = False
        try:
            connection = self._connect()
            self._prepare(connection)
            authority = _single_row(connection.execute(_AUTHORITY))
            if authority != (AUDIT_CONTROL_LOGIN, "on"):
                raise ValueError("security-audit gap authority is invalid")
            clock_row = _single_row(connection.execute(_CLOCK))
            if type(clock_row) is not tuple or len(clock_row) != 1:
                raise ValueError("security-audit gap clock shape is invalid")
            interval_end = _aware_time(clock_row[0])
            if interval_end <= snapshot.interval_start:
                raise ValueError("security-audit gap interval is invalid")
            row = _single_row(
                connection.execute(
                    _APPEND,
                    (
                        snapshot.interval_start,
                        interval_end,
                        snapshot.event_count,
                        snapshot.count_unknown,
                    ),
                )
            )
            if type(row) is not tuple or len(row) != 3:
                raise ValueError("security-audit gap append shape is invalid")
            event_id, observed, purge = row
            observed_at = _aware_time(observed)
            purge_after = _aware_time(purge)
            if (
                type(event_id) is not UUID
                or event_id.int == 0
                or observed_at < interval_end
                or purge_after
                != observed_at + timedelta(seconds=RETENTION_SECONDS)
            ):
                raise ValueError("security-audit gap append result is invalid")
            phase = _TransactionPhase.COMMIT_IN_FLIGHT
            connection.commit()
            phase = _TransactionPhase.COMMIT_ACKNOWLEDGED
        except Exception:
            failed = True
        except BaseException:
            if connection is not None:
                _close_suppressed(connection)
            raise
        if phase is _TransactionPhase.COMMIT_ACKNOWLEDGED:
            if connection is not None:
                _close_suppressed(connection)
            return cast(datetime, observed_at)
        if connection is not None:
            if phase is _TransactionPhase.PRE_COMMIT:
                _rollback_suppressed(connection)
            _close_suppressed(connection)
        if phase is _TransactionPhase.COMMIT_IN_FLIGHT:
            raise SecurityAuditGapOutcomeUnknown()
        if failed:
            raise SecurityAuditGapUnavailable()
        raise AssertionError("security-audit gap transaction did not finish")


class SecurityAuditGapController:
    """One fixed-size state machine shared by the two production lanes."""

    __slots__ = (
        "_lock",
        "_client",
        "_latest_anchor",
        "_authentication_sequence",
        "_request_router_sequence",
        "_open",
        "_closing",
        "_phase",
        "_authentication_bound",
        "_request_router_bound",
    )

    def __init__(self, client: GapClient) -> None:
        anchor: datetime | None = None
        failed = False
        try:
            anchor = _aware_time(client.initialize())
        except Exception:
            failed = True
        if failed or anchor is None:
            raise SecurityAuditGapUnavailable()
        self._lock = Lock()
        self._client = client
        self._latest_anchor = anchor
        self._authentication_sequence = 0
        self._request_router_sequence = 0
        self._open: _Accumulator | None = None
        self._closing: _GapSnapshot | None = None
        self._phase = _ControllerPhase.ACTIVE
        self._authentication_bound = False
        self._request_router_bound = False

    @property
    def state(self) -> SecurityAuditGapState:
        with self._lock:
            if self._phase is not _ControllerPhase.ACTIVE:
                return SecurityAuditGapState.OUTCOME_UNKNOWN
            if self._closing is not None:
                return SecurityAuditGapState.CLOSING
            if self._open is not None:
                return SecurityAuditGapState.OPEN
            return SecurityAuditGapState.CLEAR

    def authentication_sink(self, inner: AuditSink) -> LiveGapObservedAuditSink:
        with self._lock:
            if self._authentication_bound:
                raise ValueError("authentication gap lane is already bound")
            self._authentication_bound = True
        return LiveGapObservedAuditSink(self, _Lane.AUTHENTICATION, inner)

    def request_router_sink(self, inner: AuditSink) -> LiveGapObservedAuditSink:
        with self._lock:
            if self._request_router_bound:
                raise ValueError("request-router gap lane is already bound")
            self._request_router_bound = True
        return LiveGapObservedAuditSink(self, _Lane.REQUEST_ROUTER, inner)

    def _start(self, lane: _Lane) -> _Ticket | None:
        exhausted = False
        with self._lock:
            if self._phase is _ControllerPhase.COMMIT_OUTCOME_UNKNOWN:
                return None
            if self._phase is _ControllerPhase.SEQUENCE_EXHAUSTED:
                exhausted = True
            else:
                current = (
                    self._authentication_sequence
                    if lane is _Lane.AUTHENTICATION
                    else self._request_router_sequence
                )
                number = _next_sequence(current)
                if number is None:
                    self._phase = _ControllerPhase.SEQUENCE_EXHAUSTED
                    exhausted = True
                else:
                    if lane is _Lane.AUTHENTICATION:
                        self._authentication_sequence = number
                    else:
                        self._request_router_sequence = number
                    return _Ticket(lane, number, self._latest_anchor)
        if exhausted:
            raise SecurityAuditGapOutcomeUnknown()
        raise AssertionError("security-audit gap attempt did not start")

    def _failure(self, ticket: _Ticket, error: Exception) -> None:
        exact = type(error) in (SecurityAuditUnavailable, SecurityAuditRefused)
        with self._lock:
            if self._phase is not _ControllerPhase.ACTIVE:
                return
            if self._open is None:
                self._open = _Accumulator(
                    ticket.anchor,
                    1 if exact else None,
                    None,
                    None,
                )
            else:
                self._open.interval_start = min(
                    self._open.interval_start,
                    ticket.anchor,
                )
                self._open.exact_count = (
                    _bounded_sum(self._open.exact_count, 1)
                    if exact
                    else None
                )
            current = _progress(self._open, ticket.lane)
            greatest = ticket.number
            if current is not None:
                greatest = max(greatest, current.greatest_failure)
            _replace_progress(
                self._open,
                ticket.lane,
                _LaneProgress(greatest, None),
            )

    def _success_transition(
        self,
        ticket: _Ticket,
        anchor: datetime,
    ) -> tuple[_GapSnapshot | None, bool]:
        with self._lock:
            if anchor > self._latest_anchor:
                self._latest_anchor = anchor
            if self._phase is not _ControllerPhase.ACTIVE:
                return None, True
            if self._open is not None:
                current = _progress(self._open, ticket.lane)
                if (
                    current is not None
                    and ticket.number > current.greatest_failure
                ):
                    recovery = max(current.recovery or 0, ticket.number)
                    _replace_progress(
                        self._open,
                        ticket.lane,
                        _LaneProgress(current.greatest_failure, recovery),
                    )
                if self._closing is None and _eligible(self._open):
                    self._closing = _snapshot(self._open)
                    self._open = None
                    return self._closing, False
            return None, False

    def _restore(self, snapshot: _GapSnapshot) -> bool:
        with self._lock:
            if self._closing is not snapshot:
                raise AssertionError("security-audit gap close owner changed")
            self._closing = None
            self._open = _merge(snapshot, self._open)
            return self._phase is _ControllerPhase.ACTIVE

    def _unknown(self, snapshot: _GapSnapshot) -> None:
        with self._lock:
            if self._closing is not snapshot:
                raise AssertionError("security-audit gap close owner changed")
            if self._phase is _ControllerPhase.ACTIVE:
                self._phase = _ControllerPhase.COMMIT_OUTCOME_UNKNOWN

    def _acknowledge(
        self,
        snapshot: _GapSnapshot,
        observed_at: datetime,
    ) -> None:
        with self._lock:
            if self._closing is not snapshot:
                raise AssertionError("security-audit gap close owner changed")
            self._closing = None
            if observed_at > self._latest_anchor:
                self._latest_anchor = observed_at

    def _success(
        self,
        ticket: _Ticket,
        result: SecurityAuditAppend,
    ) -> SecurityAuditAppend:
        invalid_result = False
        anchor: datetime | None = None
        try:
            anchor = _result_anchor(result)
        except Exception:
            invalid_result = True
        if invalid_result or anchor is None:
            raise SecurityAuditGapUnavailable()
        closing, terminal = self._success_transition(ticket, anchor)
        if terminal:
            raise SecurityAuditGapOutcomeUnknown()
        if closing is None:
            return result
        failure: type[SecurityAuditGapError] | None = None
        observed_at: datetime | None = None
        try:
            observed_at = self._client.append(closing)
        except Exception as error:
            failure = (
                SecurityAuditGapOutcomeUnknown
                if type(error) is SecurityAuditGapOutcomeUnknown
                else SecurityAuditGapUnavailable
            )
        if failure is SecurityAuditGapOutcomeUnknown:
            self._unknown(closing)
            raise SecurityAuditGapOutcomeUnknown()
        if failure is SecurityAuditGapUnavailable:
            active = self._restore(closing)
            if not active:
                raise SecurityAuditGapOutcomeUnknown()
            raise SecurityAuditGapUnavailable()
        self._acknowledge(closing, cast(datetime, observed_at))
        return result


class LiveGapObservedAuditSink:
    """Outer fixed-lane wrapper around one complete health-observed sink."""

    __slots__ = ("_controller", "_lane", "_inner")

    def __init__(
        self,
        controller: SecurityAuditGapController,
        lane: _Lane,
        inner: AuditSink,
    ) -> None:
        self._controller = controller
        self._lane = lane
        self._inner = inner

    def append(self, reason: str) -> SecurityAuditAppend:
        ticket = self._controller._start(self._lane)
        try:
            result = self._inner.append(reason)
        except Exception as error:
            if ticket is not None:
                self._controller._failure(ticket, error)
            raise
        if ticket is None:
            raise SecurityAuditGapOutcomeUnknown()
        return self._controller._success(ticket, result)
