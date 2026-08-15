"""Bounded observation of production pre-tenant audit delivery health."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Protocol

from .security_audit import (
    CorrelationHmac,
    OverflowAuditAppend,
    SecurityAuditAppend,
    SecurityAuditUnavailable,
    StoredAuditAppend,
)


class SecurityAuditReadiness(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class _AuditLane(Enum):
    AUTHENTICATION = "AUTHENTICATION"
    REQUEST_ROUTER = "REQUEST_ROUTER"


class _AttemptResult(Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class _Attempt:
    lane: _AuditLane
    number: int


@dataclass(slots=True)
class _LaneState:
    latest_started: int = 0
    latest_completed: int = 0
    result: _AttemptResult = _AttemptResult.SUCCEEDED


class CorrelationHmacFactory(Protocol):
    def create(self) -> CorrelationHmac: ...


class AuditAppender(Protocol):
    def append(
        self,
        reason: str,
        correlation_hmac: CorrelationHmac,
    ) -> SecurityAuditAppend: ...


class SecurityAuditHealth:
    __slots__ = ("_lock", "_states")

    def __init__(self) -> None:
        self._lock = Lock()
        self._states = {lane: _LaneState() for lane in _AuditLane}

    @property
    def readiness(self) -> SecurityAuditReadiness:
        with self._lock:
            ready = all(
                state.result is _AttemptResult.SUCCEEDED
                for state in self._states.values()
            )
        return (
            SecurityAuditReadiness.READY
            if ready
            else SecurityAuditReadiness.NOT_READY
        )

    def authentication_sink(
        self,
        correlation_hmac_factory: CorrelationHmacFactory,
        audit_appender: AuditAppender,
    ) -> HealthObservedAuditSink:
        return HealthObservedAuditSink(
            self,
            _AuditLane.AUTHENTICATION,
            correlation_hmac_factory,
            audit_appender,
        )

    def request_router_sink(
        self,
        correlation_hmac_factory: CorrelationHmacFactory,
        audit_appender: AuditAppender,
    ) -> HealthObservedAuditSink:
        return HealthObservedAuditSink(
            self,
            _AuditLane.REQUEST_ROUTER,
            correlation_hmac_factory,
            audit_appender,
        )

    def _start(self, lane: _AuditLane) -> _Attempt:
        with self._lock:
            state = self._states[lane]
            state.latest_started += 1
            return _Attempt(lane, state.latest_started)

    def _complete(self, attempt: _Attempt, result: _AttemptResult) -> None:
        with self._lock:
            state = self._states[attempt.lane]
            if attempt.number > state.latest_completed:
                state.latest_completed = attempt.number
                state.result = result


class HealthObservedAuditSink:
    __slots__ = (
        "_health",
        "_lane",
        "_correlation_hmac_factory",
        "_audit_appender",
    )

    def __init__(
        self,
        health: SecurityAuditHealth,
        lane: _AuditLane,
        correlation_hmac_factory: CorrelationHmacFactory,
        audit_appender: AuditAppender,
    ) -> None:
        self._health = health
        self._lane = lane
        self._correlation_hmac_factory = correlation_hmac_factory
        self._audit_appender = audit_appender

    def append(self, reason: str) -> SecurityAuditAppend:
        attempt = self._health._start(self._lane)
        try:
            correlation_hmac = self._correlation_hmac_factory.create()
            result = self._audit_appender.append(reason, correlation_hmac)
            if type(result) not in (StoredAuditAppend, OverflowAuditAppend):
                raise SecurityAuditUnavailable()
        except Exception:
            self._health._complete(attempt, _AttemptResult.FAILED)
            raise
        self._health._complete(attempt, _AttemptResult.SUCCEEDED)
        return result
