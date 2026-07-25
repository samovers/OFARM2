"""Focused tests for authentication-side pre-tenant audit production."""

from __future__ import annotations

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
from kernel.authentication import (
    AuthenticationError,
    AuthenticationOutcome,
    VerifiedIdentity,
)
from kernel.authentication_audit import AuthenticationAuditProducer
from kernel.principal import (
    AuthenticatedPrincipal,
    PrincipalAuthority,
    PrincipalResolutionError,
    PrincipalResolutionOutcome,
)
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
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn,
)

NOW = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)
HMAC_POLICY = SECURITY_AUDIT_CONTRACT.correlation_hmac
HMAC = CorrelationHmac(b"h" * 32, HMAC_POLICY.key_version)
IDENTITY = VerifiedIdentity(
    equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
    issuer="https://identity-canary.example",
    subject="subject-canary",
)

AUTHENTICATION_CASES = (
    (AuthenticationOutcome.NO_CREDENTIAL, "CREDENTIAL_MISSING"),
    (AuthenticationOutcome.CREDENTIAL_MALFORMED, "CREDENTIAL_MALFORMED"),
    (AuthenticationOutcome.VERIFIER_UNAVAILABLE, "VERIFIER_UNAVAILABLE"),
    (AuthenticationOutcome.VERIFICATION_REFUSED, "VERIFICATION_REFUSED"),
)
PRINCIPAL_CASES = (
    (
        PrincipalResolutionOutcome.PRINCIPAL_BINDING_REFUSED,
        "PRINCIPAL_BINDING_REFUSED",
    ),
    (
        PrincipalResolutionOutcome.AUTHORITY_INTEGRITY_REFUSED,
        "AUTHORITY_INTEGRITY_REFUSED",
    ),
    (
        PrincipalResolutionOutcome.AUTHORITY_UNAVAILABLE,
        "AUTHORITY_UNAVAILABLE",
    ),
)
FAILURE_CASES = tuple(
    ("authentication", outcome, reason)
    for outcome, reason in AUTHENTICATION_CASES
) + tuple(
    ("principal", outcome, reason)
    for outcome, reason in PRINCIPAL_CASES
)
AUTHENTICATION_PRODUCER = next(
    entry
    for entry in SECURITY_AUDIT_CONTRACT.reason_matrix
    if entry.session_user == "ofarm_security_authentication_producer_login"
)


def _principal() -> AuthenticatedPrincipal:
    authority = PrincipalAuthority(
        equality_policy=IDENTITY.equality_policy,
        issuer=IDENTITY.issuer,
        subject=IDENTITY.subject,
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
    return AuthenticatedPrincipal(IDENTITY, authority)


PRINCIPAL = _principal()
STORED = StoredAuditAppend(uuid4(), NOW, NOW + timedelta(days=30))


class _Verifier:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def verify(self, token):
        self.calls.append(token)
        if self.error is not None:
            raise self.error
        return IDENTITY


class _Resolver:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def resolve(self, identity):
        self.calls.append(identity)
        if self.error is not None:
            raise self.error
        return PRINCIPAL


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
        self.completed = False

    def append(self, reason, correlation_hmac):
        self.calls.append((reason, correlation_hmac))
        if self.error is not None:
            raise self.error
        self.completed = True
        return self.result


def _producer(verifier, resolver, hmac_factory, appender):
    return AuthenticationAuditProducer(verifier, resolver, hmac_factory, appender)


def test_reason_cases_are_exact_and_exhaustive():
    assert {outcome for outcome, _ in AUTHENTICATION_CASES} == set(
        AuthenticationOutcome
    )
    assert {outcome for outcome, _ in PRINCIPAL_CASES} == set(
        PrincipalResolutionOutcome
    )
    assert tuple(
        reason for _, reason in AUTHENTICATION_CASES + PRINCIPAL_CASES
    ) == AUTHENTICATION_PRODUCER.reasons


@pytest.mark.parametrize(("boundary", "outcome", "reason"), FAILURE_CASES)
def test_closed_failure_is_audited_before_original_denial(
    boundary,
    outcome,
    reason,
):
    authentication_failure = boundary == "authentication"
    denial = (
        AuthenticationError(outcome, internal_detail="internal-canary")
        if authentication_failure
        else PrincipalResolutionError(outcome)
    )
    verifier = _Verifier(denial if authentication_failure else None)
    resolver = _Resolver(None if authentication_failure else denial)
    hmac_factory = _HmacFactory()
    appender = _Appender()

    with pytest.raises(type(denial)) as raised:
        _producer(verifier, resolver, hmac_factory, appender).authenticate(
            "raw-token-canary"
        )

    assert raised.value is denial
    assert resolver.calls == ([] if authentication_failure else [IDENTITY])
    assert hmac_factory.calls == 1
    assert appender.calls == [(reason, HMAC)]
    assert appender.completed is True
    assert "canary" not in repr(appender.calls)


def test_success_returns_exact_principal_without_audit_work():
    verifier = _Verifier()
    resolver = _Resolver()
    hmac_factory = _HmacFactory()
    appender = _Appender()

    result = _producer(
        verifier,
        resolver,
        hmac_factory,
        appender,
    ).authenticate("token")

    assert result is PRINCIPAL
    assert verifier.calls == ["token"]
    assert resolver.calls == [IDENTITY]
    assert hmac_factory.calls == 0
    assert appender.calls == []


@pytest.mark.parametrize(
    "result",
    (
        STORED,
        OverflowAuditAppend(
            uuid4(),
            OverflowBucket(
                "AUTHENTICATION_BOUNDARY_V1",
                "AUTHENTICATION",
                NOW,
            ),
            False,
        ),
    ),
)
def test_stored_and_overflow_results_complete_before_denial(result):
    denial = AuthenticationError(
        AuthenticationOutcome.NO_CREDENTIAL, internal_detail="missing"
    )
    appender = _Appender(result)

    with pytest.raises(AuthenticationError) as raised:
        _producer(
            _Verifier(denial),
            _Resolver(),
            _HmacFactory(),
            appender,
        ).authenticate(None)

    assert raised.value is denial
    assert appender.completed is True


def test_hmac_failure_propagates_without_append_or_authorization():
    denial = AuthenticationError(
        AuthenticationOutcome.NO_CREDENTIAL, internal_detail="missing"
    )
    audit_error = SecurityAuditUnavailable()
    hmac_factory = _HmacFactory(audit_error)
    appender = _Appender()

    with pytest.raises(SecurityAuditUnavailable) as raised:
        _producer(
            _Verifier(denial),
            _Resolver(),
            hmac_factory,
            appender,
        ).authenticate(None)

    assert raised.value is audit_error
    assert hmac_factory.calls == 1
    assert appender.calls == []


@pytest.mark.parametrize(
    "audit_error",
    (
        SecurityAuditUnavailable(),
        SecurityAuditRefused(),
        SecurityAuditOutcomeUnknown(uuid4(), None),
    ),
)
def test_append_failure_propagates_without_producer_retry(audit_error):
    denial = PrincipalResolutionError(PrincipalResolutionOutcome.AUTHORITY_UNAVAILABLE)
    appender = _Appender(error=audit_error)

    with pytest.raises(type(audit_error)) as raised:
        _producer(
            _Verifier(),
            _Resolver(denial),
            _HmacFactory(),
            appender,
        ).authenticate("token")

    assert raised.value is audit_error
    assert appender.calls == [("AUTHORITY_UNAVAILABLE", HMAC)]


@pytest.mark.parametrize("boundary", ("verifier", "resolver"))
def test_unexpected_failure_is_not_given_an_audit_classification(boundary):
    unexpected = LookupError("unexpected")
    verifier = _Verifier(unexpected if boundary == "verifier" else None)
    resolver = _Resolver(unexpected if boundary == "resolver" else None)
    hmac_factory = _HmacFactory()
    appender = _Appender()

    with pytest.raises(LookupError) as raised:
        _producer(
            verifier,
            resolver,
            hmac_factory,
            appender,
        ).authenticate("token")

    assert raised.value is unexpected
    assert hmac_factory.calls == 0
    assert appender.calls == []


class _RecordingAppender:
    def __init__(self, client):
        self.client = client
        self.result = None

    def append(self, reason, correlation_hmac):
        self.result = self.client.append(reason, correlation_hmac)
        return self.result


def test_live_postgresql_uses_exact_authentication_role_and_reason(
    migrated_audit_service,
):
    def connect():
        return psycopg.connect(
            role_dsn(
                migrated_audit_service,
                AUTHENTICATION_PRODUCER.session_user,
            ),
            autocommit=False,
        )

    denial = AuthenticationError(
        AuthenticationOutcome.NO_CREDENTIAL, internal_detail="missing"
    )
    appender = _RecordingAppender(PreTenantAuditClient(connect, AUTHENTICATION_PRODUCER))

    with pytest.raises(AuthenticationError) as raised:
        _producer(
            _Verifier(denial),
            _Resolver(),
            _HmacFactory(),
            appender,
        ).authenticate(None)

    assert raised.value is denial
    assert isinstance(appender.result, StoredAuditAppend)
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
        "AUTHENTICATION_BOUNDARY_V1",
        "AUTHENTICATION",
        "CREDENTIAL_MISSING",
    )


def test_phase_a_line_budgets_are_fixed():
    root = Path(__file__).resolve().parents[2]
    production = root / "kernel/authentication_audit.py"
    assert len(production.read_text().splitlines()) <= 140
    assert len(Path(__file__).read_text().splitlines()) <= 400
