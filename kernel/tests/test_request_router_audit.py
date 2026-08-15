"""Focused tests for request-router pre-tenant audit production."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT
from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TENANT_CAPABILITY_PARTY_RECORD_KIND,
)
from kernel.authentication import VerifiedIdentity
from kernel.principal import AuthenticatedPrincipal, PrincipalAuthority
from kernel.request_router_audit import RequestRouterAuditProducer
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
from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn,
)


NOW = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)
HMAC_POLICY = SECURITY_AUDIT_CONTRACT.correlation_hmac
HMAC = CorrelationHmac(b"h" * 32, HMAC_POLICY.key_version)
UNIT = object()
ROUTER_CASES = (
    (TenantBoundaryOutcome.UNAVAILABLE, "TENANT_BOUNDARY_UNAVAILABLE"),
    (TenantBoundaryOutcome.CAPABILITY_REFUSED, "CAPABILITY_REFUSED"),
    (TenantBoundaryOutcome.BINDING_REFUSED, "BINDER_REFUSED"),
)
ROUTER_PRODUCER = next(
    entry
    for entry in SECURITY_AUDIT_CONTRACT.reason_matrix
    if entry.session_user == "ofarm_security_request_router_producer_login"
)


def _principal() -> AuthenticatedPrincipal:
    identity = VerifiedIdentity(
        equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
        issuer="https://issuer-canary.example",
        subject="subject-canary",
    )
    authority = PrincipalAuthority(
        equality_policy=identity.equality_policy,
        issuer=identity.issuer,
        subject=identity.subject,
        binding_version_id=uuid4(),
        binding_version_digest="sha256:" + "1" * 64,
        lifecycle_head_id=uuid4(),
        lifecycle_head_digest="sha256:" + "2" * 64,
        tenant_id=uuid4(),
        tenant_registration_digest="sha256:" + "3" * 64,
        party_ref="party:canary",
        party_record_kind=TENANT_CAPABILITY_PARTY_RECORD_KIND,
        party_record_id="party:canary",
        party_schema_digest="sha256:" + "4" * 64,
        party_payload_digest="sha256:" + "5" * 64,
        party_state="ACTIVE",
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=1),
    )
    return AuthenticatedPrincipal(identity, authority)


PRINCIPAL = _principal()
STORED = StoredAuditAppend(uuid4(), NOW, NOW + timedelta(days=30))


class _Boundary:
    def __init__(self, *, enter_error=None, exit_error=None):
        self.enter_error = enter_error
        self.exit_error = exit_error
        self.calls = []

    @contextmanager
    def unit_of_work(self, principal):
        self.calls.append(principal)
        if self.enter_error is not None:
            raise self.enter_error
        try:
            yield UNIT
        finally:
            if self.exit_error is not None:
                raise self.exit_error


class _HmacFactory:
    def __init__(self):
        self.calls = 0

    def create(self):
        self.calls += 1
        return HMAC


class _Sink:
    def __init__(self, result=STORED, error=None):
        self.result = result
        self.error = error
        self.calls = []
        self.completed = False

    def append(self, reason):
        self.calls.append(reason)
        if self.error is not None:
            raise self.error
        self.completed = True
        return self.result


def _producer(boundary, sink):
    return RequestRouterAuditProducer(boundary, sink)


def _enter(producer):
    with producer.unit_of_work(PRINCIPAL):
        raise AssertionError("tenant UnitOfWork must not be yielded")


def test_reason_cases_are_exact_and_exhaustive():
    mapped = {outcome for outcome, _ in ROUTER_CASES}

    assert mapped == set(TenantBoundaryOutcome) - {
        TenantBoundaryOutcome.FINALIZATION_UNKNOWN
    }
    assert tuple(reason for _, reason in ROUTER_CASES) == ROUTER_PRODUCER.reasons


@pytest.mark.parametrize(("outcome", "reason"), ROUTER_CASES)
def test_closed_entry_failure_is_audited_before_original_denial(
    outcome,
    reason,
):
    denial = TenantBoundaryError(outcome)
    boundary = _Boundary(enter_error=denial)
    sink = _Sink()

    with pytest.raises(TenantBoundaryError) as raised:
        _enter(_producer(boundary, sink))

    assert raised.value is denial
    assert boundary.calls == [PRINCIPAL]
    assert sink.calls == [reason]
    assert sink.completed is True
    assert "canary" not in repr(sink.calls)


def test_success_yields_exact_unit_without_audit_work():
    boundary = _Boundary()
    sink = _Sink()

    with _producer(boundary, sink).unit_of_work(
        PRINCIPAL
    ) as unit:
        assert unit is UNIT

    assert boundary.calls == [PRINCIPAL]
    assert sink.calls == []


@pytest.mark.parametrize(
    "result",
    (
        STORED,
        OverflowAuditAppend(
            uuid4(),
            OverflowBucket(
                "REQUEST_ROUTER_BOUNDARY_V1",
                "REQUEST_ROUTER",
                NOW,
            ),
            False,
        ),
    ),
)
def test_stored_and_overflow_results_complete_before_denial(result):
    denial = TenantBoundaryError(TenantBoundaryOutcome.UNAVAILABLE)
    sink = _Sink(result)

    with pytest.raises(TenantBoundaryError) as raised:
        _enter(
            _producer(_Boundary(enter_error=denial), sink)
        )

    assert raised.value is denial
    assert sink.completed is True


def test_finalization_outcome_on_entry_is_not_a_pretenant_reason():
    denial = TenantBoundaryError(TenantBoundaryOutcome.FINALIZATION_UNKNOWN)
    sink = _Sink()

    with pytest.raises(TenantBoundaryError) as raised:
        _enter(_producer(_Boundary(enter_error=denial), sink))

    assert raised.value is denial
    assert sink.calls == []


@pytest.mark.parametrize(
    ("phase", "outcome"),
    (
        ("body", TenantBoundaryOutcome.BINDING_REFUSED),
        ("exit", TenantBoundaryOutcome.FINALIZATION_UNKNOWN),
    ),
)
def test_post_binding_failure_never_uses_isolated_audit(phase, outcome):
    denial = TenantBoundaryError(outcome)
    boundary = _Boundary(exit_error=denial if phase == "exit" else None)
    sink = _Sink()

    with pytest.raises(TenantBoundaryError) as raised:
        with _producer(
            boundary,
            sink,
        ).unit_of_work(PRINCIPAL):
            if phase == "body":
                raise denial

    assert raised.value is denial
    assert sink.calls == []


def test_unexpected_entry_failure_gets_no_audit_classification():
    unexpected = LookupError("unexpected")
    sink = _Sink()

    with pytest.raises(LookupError) as raised:
        _enter(
            _producer(_Boundary(enter_error=unexpected), sink)
        )

    assert raised.value is unexpected
    assert sink.calls == []


@pytest.mark.parametrize(
    "audit_error",
    (
        SecurityAuditUnavailable(),
        SecurityAuditRefused(),
        SecurityAuditOutcomeUnknown(uuid4(), None),
    ),
)
def test_sink_failure_propagates_without_tenant_entry(audit_error):
    denial = TenantBoundaryError(TenantBoundaryOutcome.CAPABILITY_REFUSED)
    sink = _Sink(error=audit_error)

    with pytest.raises(type(audit_error)) as raised:
        _enter(_producer(_Boundary(enter_error=denial), sink))

    assert raised.value is audit_error
    assert sink.calls == ["CAPABILITY_REFUSED"]


class _RecordingAppender:
    def __init__(self, client):
        self.client = client
        self.result = None

    def append(self, reason, correlation_hmac):
        self.result = self.client.append(reason, correlation_hmac)
        return self.result


def test_live_postgresql_uses_exact_router_role_and_reason(
    migrated_audit_service,
):
    def connect():
        return psycopg.connect(
            role_dsn(
                migrated_audit_service,
                ROUTER_PRODUCER.session_user,
            ),
            autocommit=False,
        )

    denial = TenantBoundaryError(TenantBoundaryOutcome.BINDING_REFUSED)
    appender = _RecordingAppender(PreTenantAuditClient(connect, ROUTER_PRODUCER))
    health = SecurityAuditHealth()
    sink = health.request_router_sink(_HmacFactory(), appender)

    with pytest.raises(TenantBoundaryError) as raised:
        _enter(_producer(_Boundary(enter_error=denial), sink))

    assert raised.value is denial
    assert isinstance(appender.result, StoredAuditAppend)
    assert health.readiness is SecurityAuditReadiness.READY
    with psycopg.connect(
        migrated_audit_service["target_admin_dsn"]
    ) as connection:
        row = connection.execute(
            """
            SELECT producer, component, reason
            FROM ofarm_security.operational_security_event
            WHERE event_id = %s
            """,
            (appender.result.event_id,),
        ).fetchone()
    assert row == (
        "REQUEST_ROUTER_BOUNDARY_V1",
        "REQUEST_ROUTER",
        "BINDER_REFUSED",
    )


def test_phase_a_line_budgets_are_fixed():
    root = Path(__file__).resolve().parents[2]
    production = root / "kernel/request_router_audit.py"
    assert len(production.read_text().splitlines()) <= 120
    assert len(Path(__file__).read_text().splitlines()) <= 360
