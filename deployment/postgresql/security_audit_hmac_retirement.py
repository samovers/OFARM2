"""One-shot retirement of the fixed pre-tenant correlation-HMAC version."""

from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Protocol, cast

import psycopg
from google.cloud import kms_v1

from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT
from kernel.security_audit_hmac_posture import (
    CorrelationHmacLifecycleObserver,
    CorrelationHmacLifecycleUnavailable,
    CorrelationHmacVersionDisposition,
    ConnectionFactory as LifecycleConnectionFactory,
    KmsLifecycleClient,
)

TARGET_KEY_VERSION, ACTIVE_KEY_VERSION = 1, 2
KNOWN_KEY_VERSIONS = (1, 2)
KMS_READ_TIMEOUT_SECONDS = 5.0
POSTGRES_CONNECT_TIMEOUT_SECONDS = 5
POSTGRES_CONNECTION_OPTIONS = "-c statement_timeout=2000"
DESTROY_DURATION_NS = 86_400_000_000_000
LIVE_DEADLINE_LEAD_NS = 172_800_000_000_000
CLOCK_SKEW_NS = 1_000_000_000
ADMISSION_BUDGET_NS = 5_000_000_000
AUDIT_CONTROL_LOGIN = "ofarm_security_audit_control_login"
DATABASE_CLOCK_SQL = "SELECT session_user, clock_timestamp()"

_READ_ONLY = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
_NANOSECONDS = 1_000_000_000
_MAX_MONOTONIC_NS = (1 << 63) - 1
_MIN_PROTOBUF_SECONDS = -62_135_596_800
_MAX_PROTOBUF_SECONDS = 253_402_300_799
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_PARENT = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/"
    r"locations/[a-z0-9](?:[a-z0-9-]*[a-z0-9])?/"
    r"keyRings/[A-Za-z0-9_-]{1,63}/cryptoKeys/[A-Za-z0-9_-]{1,63}$"
)

Connection = psycopg.Connection[tuple[object, ...]]

class SecurityAuditHmacRetirementRefused(RuntimeError):
    pass

class SecurityAuditHmacRetirementUnavailable(RuntimeError):
    pass

class SecurityAuditHmacRetirementOutcomeUnknown(RuntimeError):
    pass

class SecurityAuditHmacRetirementPhase(Enum):
    PRE_SUBMISSION = "PRE_SUBMISSION"
    SUBMITTED = "SUBMITTED"
    RESULT_KNOWN = "RESULT_KNOWN"

_PHASE = SecurityAuditHmacRetirementPhase
_STATE = kms_v1.CryptoKeyVersion.CryptoKeyVersionState
_ALGORITHM = kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm

class SecurityAuditHmacRetirementPhaseCarrier:
    """Single adapter-visible phase whose transitions are runner-owned."""
    __slots__ = ("_phase",)
    def __init__(self) -> None:
        self._phase = SecurityAuditHmacRetirementPhase.PRE_SUBMISSION
    @property
    def phase(self) -> SecurityAuditHmacRetirementPhase:
        return self._phase
    def _advance(
        self,
        expected: SecurityAuditHmacRetirementPhase,
        target: SecurityAuditHmacRetirementPhase,
    ) -> None:
        if self._phase is not expected:
            raise SecurityAuditHmacRetirementUnavailable
        self._phase = target

class SecurityAuditHmacRetirementOutcome(Enum):
    SCHEDULED = "SCHEDULED"
    ALREADY_SCHEDULED = "ALREADY_SCHEDULED"
    ALREADY_DESTROYED = "ALREADY_DESTROYED"

@dataclass(frozen=True, slots=True)
class SecurityAuditHmacRetirementResult:
    outcome: SecurityAuditHmacRetirementOutcome
    destruction_time_ns: int
    greatest_purge_after_ns: int | None

class PostgresConnectionFactory(Protocol):
    def __call__(
        self,
        conninfo: str,
        *,
        autocommit: bool,
        connect_timeout: int,
        options: str,
    ) -> Connection: ...

class KmsHmacRetirementClient(KmsLifecycleClient, Protocol):
    def get_crypto_key(
        self,
        *,
        request: kms_v1.GetCryptoKeyRequest,
        retry: None,
        timeout: float,
    ) -> kms_v1.CryptoKey: ...

    def destroy_crypto_key_version(
        self,
        *,
        request: kms_v1.DestroyCryptoKeyVersionRequest,
        retry: None,
        timeout: float,
    ) -> kms_v1.CryptoKeyVersion: ...

@dataclass(frozen=True, slots=True)
class _TargetObservation:
    state: object
    destruction_time_ns: int | None

def validated_hmac_retirement_parent(value: object) -> str:
    if type(value) is not str or _PARENT.fullmatch(value) is None:
        raise ValueError("invalid correlation-HMAC parent")
    return value

def _datetime_ns(value: object) -> int:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise SecurityAuditHmacRetirementUnavailable
    delta = value.astimezone(timezone.utc) - _EPOCH
    seconds = delta.days * 86_400 + delta.seconds
    return seconds * _NANOSECONDS + delta.microseconds * 1_000

def _protobuf_ns(version: kms_v1.CryptoKeyVersion, field: str) -> int:
    protobuf = kms_v1.CryptoKeyVersion.pb(version)
    timestamp = getattr(protobuf, field)
    seconds = timestamp.seconds
    nanos = timestamp.nanos
    if (
        type(seconds) is not int
        or type(nanos) is not int
        or not _MIN_PROTOBUF_SECONDS <= seconds <= _MAX_PROTOBUF_SECONDS
        or not 0 <= nanos < _NANOSECONDS
    ):
        raise SecurityAuditHmacRetirementUnavailable
    return seconds * _NANOSECONDS + nanos

def _validate_parent_key(key: object, parent: str) -> None:
    if not isinstance(key, kms_v1.CryptoKey):
        raise SecurityAuditHmacRetirementUnavailable
    protobuf = kms_v1.CryptoKey.pb(key)
    template = key.version_template
    duration = protobuf.destroy_scheduled_duration
    if (
        not protobuf.HasField("version_template")
        or not protobuf.HasField("destroy_scheduled_duration")
        or key.name != parent
        or key.purpose != kms_v1.CryptoKey.CryptoKeyPurpose.MAC
        or template.algorithm
        != _ALGORITHM.HMAC_SHA256
        or template.protection_level != kms_v1.ProtectionLevel.HSM
        or duration.seconds != 86_400
        or duration.nanos != 0
        or key.import_only is not False
    ):
        raise SecurityAuditHmacRetirementRefused

def _validate_target(version: object, resource: str) -> _TargetObservation:
    if not isinstance(version, kms_v1.CryptoKeyVersion):
        raise SecurityAuditHmacRetirementUnavailable
    protobuf = kms_v1.CryptoKeyVersion.pb(version)
    if (
        version.name != resource
        or version.algorithm
        != _ALGORITHM.HMAC_SHA256
        or version.protection_level != kms_v1.ProtectionLevel.HSM
        or version.reimport_eligible is not False
        or version.import_job != ""
        or protobuf.HasField("import_time")
    ):
        raise SecurityAuditHmacRetirementRefused
    destroy_time = protobuf.HasField("destroy_time")
    event_time = protobuf.HasField("destroy_event_time")
    if version.state in (_STATE.ENABLED, _STATE.DISABLED):
        if destroy_time or event_time:
            raise SecurityAuditHmacRetirementUnavailable
        return _TargetObservation(version.state, None)
    if version.state == _STATE.DESTROY_SCHEDULED and destroy_time and not event_time:
        return _TargetObservation(version.state, _protobuf_ns(version, "destroy_time"))
    if version.state == _STATE.DESTROYED and event_time and not destroy_time:
        return _TargetObservation(
            version.state,
            _protobuf_ns(version, "destroy_event_time"),
        )
    raise SecurityAuditHmacRetirementUnavailable

def _render_timestamp(value_ns: int) -> str:
    if type(value_ns) is not int:
        raise ValueError("invalid retirement timestamp")
    seconds, nanos = divmod(value_ns, _NANOSECONDS)
    if not _MIN_PROTOBUF_SECONDS <= seconds <= _MAX_PROTOBUF_SECONDS:
        raise ValueError("retirement timestamp is outside RFC 3339 range")
    value = _EPOCH + timedelta(seconds=seconds)
    return (
        f"{value.year:04d}-{value.month:02d}-{value.day:02d}T"
        f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}."
        f"{nanos:09d}Z"
    )

def render_security_audit_hmac_retirement_report(
    result: SecurityAuditHmacRetirementResult,
) -> bytes:
    if (
        type(result) is not SecurityAuditHmacRetirementResult
        or type(result.outcome) is not SecurityAuditHmacRetirementOutcome
    ):
        raise ValueError("invalid retirement result")
    deadline = (
        None
        if result.greatest_purge_after_ns is None
        else _render_timestamp(result.greatest_purge_after_ns)
    )
    document = {
        "destructionTime": _render_timestamp(result.destruction_time_ns),
        "greatestPurgeAfter": deadline,
        "outcome": result.outcome.value,
        "schema": "ofarm.security-audit-hmac-retirement-report.v2",
        "targetKeyVersion": TARGET_KEY_VERSION,
    }
    return json.dumps(
        document,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii") + b"\n"

def _destroy_timeout(start_ns: object, now_ns: object) -> float:
    if (
        type(start_ns) is not int
        or type(now_ns) is not int
        or not 0 <= start_ns <= _MAX_MONOTONIC_NS
        or not 0 <= now_ns <= _MAX_MONOTONIC_NS
    ):
        raise SecurityAuditHmacRetirementRefused
    elapsed_ns = now_ns - start_ns
    if elapsed_ns < 0 or elapsed_ns >= ADMISSION_BUDGET_NS:
        raise SecurityAuditHmacRetirementRefused
    remaining_ns = ADMISSION_BUDGET_NS - elapsed_ns
    exact_seconds = remaining_ns / _NANOSECONDS
    timeout = math.nextafter(exact_seconds, 0.0)
    if not math.isfinite(timeout) or timeout <= 0 or timeout > exact_seconds:
        raise SecurityAuditHmacRetirementRefused
    return timeout

class SecurityAuditHmacRetirementRunner:
    """Bind one database deadline to at most one fixed KMS destroy request."""
    def __init__(
        self,
        connection_factory: PostgresConnectionFactory,
        kms_client: KmsHmacRetirementClient,
        kms_parent_resource: str,
        phase: SecurityAuditHmacRetirementPhaseCarrier,
        *,
        monotonic_ns: Callable[[], int] | None = None,
    ) -> None:
        self._connection_factory = connection_factory
        self._kms_client = kms_client
        self._parent = validated_hmac_retirement_parent(kms_parent_resource)
        self._phase = phase
        self._monotonic_ns = time.monotonic_ns if monotonic_ns is None else monotonic_ns
    def _connection(self, conninfo: str) -> Connection:
        return self._connection_factory(
            conninfo,
            autocommit=False,
            connect_timeout=POSTGRES_CONNECT_TIMEOUT_SECONDS,
            options=POSTGRES_CONNECTION_OPTIONS,
        )

    def _posture(self, conninfo: str) -> int | None:
        def connect() -> Connection:
            return self._connection(conninfo)

        try:
            posture = CorrelationHmacLifecycleObserver(
                cast(LifecycleConnectionFactory, connect),
                self._kms_client,
                self._parent,
                rpc_timeout_seconds=KMS_READ_TIMEOUT_SECONDS,
            ).current()
        except CorrelationHmacLifecycleUnavailable:
            raise SecurityAuditHmacRetirementUnavailable from None
        if (
            tuple(value.key_version for value in posture.versions)
            != KNOWN_KEY_VERSIONS
            or posture.versions[0].disposition
            not in {
                CorrelationHmacVersionDisposition.RETIREMENT_REQUIRED,
                CorrelationHmacVersionDisposition.DESTROY_SCHEDULED_OBSERVED,
                CorrelationHmacVersionDisposition.DESTROYED_OBSERVED,
            }
            or posture.versions[1].disposition
            is not CorrelationHmacVersionDisposition.ACTIVE
            or posture.versions[1].kms_state != "ENABLED"
        ):
            raise SecurityAuditHmacRetirementRefused
        deadline = posture.versions[0].greatest_purge_after
        return None if deadline is None else _datetime_ns(deadline)

    def _database_clock(self, conninfo: str) -> int:
        with self._connection(conninfo) as connection:
            if connection.autocommit is not False or connection.closed is not False:
                raise SecurityAuditHmacRetirementUnavailable
            with connection.transaction():
                connection.execute(_READ_ONLY)
                cursor = connection.execute(DATABASE_CLOCK_SQL)
                row = cursor.fetchone()
                duplicate = cursor.fetchone()
        if type(row) is not tuple or len(row) != 2 or duplicate is not None:
            raise SecurityAuditHmacRetirementUnavailable
        session_user, observed_at = row
        if session_user != AUDIT_CONTROL_LOGIN:
            raise SecurityAuditHmacRetirementRefused
        return _datetime_ns(observed_at)

    def _known_result(
        self,
        observation: _TargetObservation,
        database_ns: int,
        deadline_ns: int | None,
    ) -> SecurityAuditHmacRetirementResult:
        destruction_ns = observation.destruction_time_ns
        if destruction_ns is None:
            raise SecurityAuditHmacRetirementUnavailable
        if observation.state == _STATE.DESTROY_SCHEDULED:
            if not (
                database_ns + CLOCK_SKEW_NS < destruction_ns
                <= database_ns + DESTROY_DURATION_NS + CLOCK_SKEW_NS
            ):
                raise SecurityAuditHmacRetirementUnavailable
            outcome = SecurityAuditHmacRetirementOutcome.ALREADY_SCHEDULED
        elif observation.state == _STATE.DESTROYED:
            if destruction_ns > database_ns + CLOCK_SKEW_NS:
                raise SecurityAuditHmacRetirementUnavailable
            outcome = SecurityAuditHmacRetirementOutcome.ALREADY_DESTROYED
        else:
            raise SecurityAuditHmacRetirementUnavailable
        if deadline_ns is not None and destruction_ns > deadline_ns:
            raise SecurityAuditHmacRetirementRefused
        result = SecurityAuditHmacRetirementResult(outcome, destruction_ns, deadline_ns)
        self._phase._advance(_PHASE.PRE_SUBMISSION, _PHASE.RESULT_KNOWN)
        return result

    def _schedule(
        self,
        database_ns: int,
        deadline_ns: int | None,
        admission_start_ns: object,
    ) -> SecurityAuditHmacRetirementResult:
        if (
            deadline_ns is not None
            and database_ns + LIVE_DEADLINE_LEAD_NS > deadline_ns
        ):
            raise SecurityAuditHmacRetirementRefused
        resource = f"{self._parent}/cryptoKeyVersions/{TARGET_KEY_VERSION}"
        request = kms_v1.DestroyCryptoKeyVersionRequest(name=resource)
        timeout = _destroy_timeout(admission_start_ns, self._monotonic_ns())
        self._phase._advance(_PHASE.PRE_SUBMISSION, _PHASE.SUBMITTED)
        response = self._kms_client.destroy_crypto_key_version(
            request=request,
            retry=None,
            timeout=timeout,
        )
        observed = _validate_target(response, resource)
        destruction_ns = observed.destruction_time_ns
        if (
            observed.state != _STATE.DESTROY_SCHEDULED
            or destruction_ns is None
            or not database_ns + DESTROY_DURATION_NS - CLOCK_SKEW_NS
            <= destruction_ns
            <= database_ns + DESTROY_DURATION_NS + ADMISSION_BUDGET_NS
            + CLOCK_SKEW_NS
            or deadline_ns is not None
            and destruction_ns > deadline_ns
        ):
            raise SecurityAuditHmacRetirementOutcomeUnknown
        result = SecurityAuditHmacRetirementResult(
            SecurityAuditHmacRetirementOutcome.SCHEDULED,
            destruction_ns,
            deadline_ns,
        )
        self._phase._advance(_PHASE.SUBMITTED, _PHASE.RESULT_KNOWN)
        return result

    def _run(self, conninfo: str) -> SecurityAuditHmacRetirementResult:
        contract = SECURITY_AUDIT_CONTRACT
        if (
            contract.correlation_hmac_known_key_versions != KNOWN_KEY_VERSIONS
            or contract.correlation_hmac.key_version != ACTIVE_KEY_VERSION
        ):
            raise SecurityAuditHmacRetirementRefused
        deadline_ns = self._posture(conninfo)
        parent = self._kms_client.get_crypto_key(
            request=kms_v1.GetCryptoKeyRequest(name=self._parent),
            retry=None,
            timeout=KMS_READ_TIMEOUT_SECONDS,
        )
        _validate_parent_key(parent, self._parent)
        resource = f"{self._parent}/cryptoKeyVersions/{TARGET_KEY_VERSION}"
        target = self._kms_client.get_crypto_key_version(
            request=kms_v1.GetCryptoKeyVersionRequest(name=resource),
            retry=None,
            timeout=KMS_READ_TIMEOUT_SECONDS,
        )
        observation = _validate_target(target, resource)
        admission_start_ns = self._monotonic_ns()
        database_ns = self._database_clock(conninfo)
        if observation.state in (_STATE.DESTROY_SCHEDULED, _STATE.DESTROYED):
            return self._known_result(observation, database_ns, deadline_ns)
        return self._schedule(database_ns, deadline_ns, admission_start_ns)

    def run(self, conninfo: str) -> SecurityAuditHmacRetirementResult:
        try:
            return self._run(conninfo)
        except SecurityAuditHmacRetirementOutcomeUnknown:
            raise
        except (
            SecurityAuditHmacRetirementRefused,
            SecurityAuditHmacRetirementUnavailable,
        ):
            if self._phase.phase is _PHASE.SUBMITTED:
                raise SecurityAuditHmacRetirementOutcomeUnknown from None
            raise
        except Exception:
            if self._phase.phase is _PHASE.SUBMITTED:
                raise SecurityAuditHmacRetirementOutcomeUnknown from None
            raise SecurityAuditHmacRetirementUnavailable from None
