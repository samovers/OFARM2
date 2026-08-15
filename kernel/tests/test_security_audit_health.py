"""Bounded security-audit health state and sink classification tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

import psycopg
import pytest

from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT
from kernel.security_audit import (
    CorrelationHmac,
    OverflowAuditAppend,
    OverflowBucket,
    SecurityAuditOutcomeUnknown,
    SecurityAuditRefused,
    SecurityAuditUnavailable,
    StoredAuditAppend,
)
from kernel.security_audit_client import PreTenantAuditClient
from kernel.security_audit_health import (
    SecurityAuditHealth,
    SecurityAuditReadiness,
)
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn,
)


NOW = datetime(2026, 8, 15, 12, tzinfo=timezone.utc)
HMAC_POLICY = SECURITY_AUDIT_CONTRACT.correlation_hmac
HMAC = CorrelationHmac(b"h" * 32, HMAC_POLICY.key_version)
STORED = StoredAuditAppend(uuid4(), NOW, NOW + timedelta(days=30))
AUTHENTICATION_PRODUCER = next(
    producer
    for producer in SECURITY_AUDIT_CONTRACT.reason_matrix
    if producer.component == "AUTHENTICATION"
)


def _overflow(*, count_unknown: bool) -> OverflowAuditAppend:
    return OverflowAuditAppend(
        uuid4(),
        OverflowBucket(
            AUTHENTICATION_PRODUCER.producer,
            AUTHENTICATION_PRODUCER.component,
            NOW,
        ),
        count_unknown,
    )


class _HmacFactory:
    def __init__(self, error=None):
        self.error = error
        self.calls = 0

    def create(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return HMAC


class _Appender:
    def __init__(self, result=STORED, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def append(self, reason, correlation_hmac):
        self.calls.append((reason, correlation_hmac))
        if self.error is not None:
            raise self.error
        return self.result


def _fail(sink, error):
    with pytest.raises(type(error)) as raised:
        sink.append("CREDENTIAL_MISSING")
    assert raised.value is error


def test_fixed_lanes_start_ready_and_use_exact_conjunction():
    health = SecurityAuditHealth()
    authentication_appender = _Appender()
    request_router_appender = _Appender()
    authentication = health.authentication_sink(
        _HmacFactory(), authentication_appender
    )
    request_router = health.request_router_sink(
        _HmacFactory(), request_router_appender
    )

    assert health.readiness is SecurityAuditReadiness.READY
    assert not hasattr(health, "__dict__")
    assert {
        name for name in dir(health) if name.endswith("_sink")
    } == {"authentication_sink", "request_router_sink"}

    authentication_error = SecurityAuditUnavailable()
    authentication_appender.error = authentication_error
    _fail(authentication, authentication_error)
    assert health.readiness is SecurityAuditReadiness.NOT_READY

    request_router.append("TENANT_BOUNDARY_UNAVAILABLE")
    assert health.readiness is SecurityAuditReadiness.NOT_READY

    authentication_appender.error = None
    authentication.append("CREDENTIAL_MISSING")
    assert health.readiness is SecurityAuditReadiness.READY

    request_router_error = SecurityAuditRefused()
    request_router_appender.error = request_router_error
    _fail(request_router, request_router_error)
    authentication_appender.error = authentication_error
    _fail(authentication, authentication_error)
    assert health.readiness is SecurityAuditReadiness.NOT_READY

    authentication_appender.error = None
    authentication.append("CREDENTIAL_MISSING")
    assert health.readiness is SecurityAuditReadiness.NOT_READY

    request_router_appender.error = None
    request_router.append("TENANT_BOUNDARY_UNAVAILABLE")
    assert health.readiness is SecurityAuditReadiness.READY


def test_failed_lane_persists_without_later_same_lane_traffic():
    health = SecurityAuditHealth()
    appender = _Appender(error=SecurityAuditUnavailable())
    authentication = health.authentication_sink(_HmacFactory(), appender)
    request_router = health.request_router_sink(_HmacFactory(), _Appender())

    _fail(authentication, appender.error)
    appender.error = None

    for _ in range(3):
        assert health.readiness is SecurityAuditReadiness.NOT_READY
    request_router.append("BINDER_REFUSED")
    assert health.readiness is SecurityAuditReadiness.NOT_READY

    authentication.append("CREDENTIAL_MISSING")
    assert health.readiness is SecurityAuditReadiness.READY


@pytest.mark.parametrize(
    "result",
    (STORED, _overflow(count_unknown=False), _overflow(count_unknown=True)),
)
def test_exact_stored_and_overflow_results_are_success(result):
    health = SecurityAuditHealth()
    hmac_factory = _HmacFactory()
    appender = _Appender(result=result)
    sink = health.authentication_sink(hmac_factory, appender)

    returned = sink.append("CREDENTIAL_MISSING")

    assert returned is result
    assert hmac_factory.calls == 1
    assert appender.calls == [("CREDENTIAL_MISSING", HMAC)]
    assert health.readiness is SecurityAuditReadiness.READY


class _StoredSubclass(StoredAuditAppend):
    pass


@pytest.mark.parametrize(
    "foreign",
    (object(), _StoredSubclass(uuid4(), NOW, NOW + timedelta(days=30))),
)
def test_foreign_or_subclassed_result_fails_closed(foreign):
    health = SecurityAuditHealth()
    sink = health.authentication_sink(_HmacFactory(), _Appender(foreign))

    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")

    assert health.readiness is SecurityAuditReadiness.NOT_READY


def test_hmac_failure_is_preserved_and_append_is_not_called():
    health = SecurityAuditHealth()
    error = SecurityAuditUnavailable()
    hmac_factory = _HmacFactory(error)
    appender = _Appender()
    sink = health.authentication_sink(hmac_factory, appender)

    _fail(sink, error)

    assert hmac_factory.calls == 1
    assert appender.calls == []
    assert health.readiness is SecurityAuditReadiness.NOT_READY


@pytest.mark.parametrize(
    "error",
    (
        SecurityAuditUnavailable(),
        SecurityAuditRefused(),
        SecurityAuditOutcomeUnknown(uuid4(), None),
    ),
)
def test_append_failure_is_preserved_without_sink_retry(error):
    health = SecurityAuditHealth()
    appender = _Appender(error=error)
    sink = health.authentication_sink(_HmacFactory(), appender)

    _fail(sink, error)

    assert appender.calls == [("CREDENTIAL_MISSING", HMAC)]
    assert health.readiness is SecurityAuditReadiness.NOT_READY


class _Abort(BaseException):
    pass


def test_base_exception_is_not_caught_or_completed():
    health = SecurityAuditHealth()
    error = _Abort()
    sink = health.authentication_sink(_HmacFactory(error), _Appender())

    with pytest.raises(_Abort) as raised:
        sink.append("CREDENTIAL_MISSING")

    assert raised.value is error
    assert health.readiness is SecurityAuditReadiness.READY


class _BlockingAppender:
    def __init__(self, started, release, outcome):
        self.started = started
        self.release = release
        self.outcome = outcome

    def append(self, _reason, _correlation_hmac):
        self.started.set()
        if not self.release.wait(5):
            raise TimeoutError("controlled append was not released")
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def _run_sink(sink, reason, errors):
    try:
        sink.append(reason)
    except Exception as error:
        errors.append(error)


def test_inflight_attempt_does_not_hide_last_completed_result():
    health = SecurityAuditHealth()
    started = Event()
    release = Event()
    error = SecurityAuditUnavailable()
    sink = health.authentication_sink(
        _HmacFactory(), _BlockingAppender(started, release, error)
    )
    errors = []
    thread = Thread(
        target=_run_sink,
        args=(sink, "CREDENTIAL_MISSING", errors),
    )

    thread.start()
    assert started.wait(5)
    assert health.readiness is SecurityAuditReadiness.READY
    release.set()
    thread.join(5)

    assert not thread.is_alive()
    assert errors == [error]
    assert health.readiness is SecurityAuditReadiness.NOT_READY


class _OrderedAppender:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.started = {reason: Event() for reason in outcomes}
        self.release = {reason: Event() for reason in outcomes}

    def append(self, reason, _correlation_hmac):
        self.started[reason].set()
        if not self.release[reason].wait(5):
            raise TimeoutError("controlled append was not released")
        outcome = self.outcomes[reason]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    (
        (
            SecurityAuditUnavailable(),
            STORED,
            SecurityAuditReadiness.READY,
        ),
        (
            STORED,
            SecurityAuditUnavailable(),
            SecurityAuditReadiness.NOT_READY,
        ),
    ),
)
def test_later_started_completion_owns_out_of_order_lane(
    first,
    second,
    expected,
):
    health = SecurityAuditHealth()
    appender = _OrderedAppender({"first": first, "second": second})
    sink = health.authentication_sink(_HmacFactory(), appender)
    errors = []
    first_thread = Thread(target=_run_sink, args=(sink, "first", errors))
    second_thread = Thread(target=_run_sink, args=(sink, "second", errors))

    first_thread.start()
    assert appender.started["first"].wait(5)
    second_thread.start()
    assert appender.started["second"].wait(5)

    appender.release["second"].set()
    second_thread.join(5)
    assert health.readiness is expected

    appender.release["first"].set()
    first_thread.join(5)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert len(errors) == 1
    assert health.readiness is expected


def test_live_postgresql_overflow_is_a_healthy_delivery(
    migrated_audit_service,
):
    with psycopg.connect(
        migrated_audit_service["target_admin_dsn"],
        autocommit=True,
    ) as admin:
        bucket_start = admin.execute(
            """
            SELECT pg_catalog.date_bin(
                pg_catalog.make_interval(secs => 60),
                pg_catalog.clock_timestamp(),
                '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
            )
            """
        ).fetchone()[0]
        admin.execute(
            """
            INSERT INTO ofarm_security.operational_security_quota_bucket (
                producer, component, bucket_start, accepted_event_count
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (producer, component, bucket_start) DO UPDATE
            SET accepted_event_count = EXCLUDED.accepted_event_count,
                overflow_event_count = 0,
                overflow_started_at = NULL,
                count_unknown = false
            """,
            (
                AUTHENTICATION_PRODUCER.producer,
                AUTHENTICATION_PRODUCER.component,
                bucket_start,
                SECURITY_AUDIT_CONTRACT.quota_accepted_event_threshold,
            ),
        )

    def connect():
        return psycopg.connect(
            role_dsn(
                migrated_audit_service,
                AUTHENTICATION_PRODUCER.session_user,
            ),
            autocommit=False,
        )

    health = SecurityAuditHealth()
    sink = health.authentication_sink(
        _HmacFactory(),
        PreTenantAuditClient(connect, AUTHENTICATION_PRODUCER),
    )

    result = sink.append("CREDENTIAL_MISSING")

    assert isinstance(result, OverflowAuditAppend)
    assert result.bucket.bucket_start == bucket_start
    assert health.readiness is SecurityAuditReadiness.READY


def test_phase_b_line_budgets_are_fixed():
    root = Path(__file__).resolve().parents[2]
    production = root / "kernel/security_audit_health.py"
    assert len(production.read_text().splitlines()) <= 170
    assert len(Path(__file__).read_text().splitlines()) <= 500
