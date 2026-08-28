"""Executed cross-slice closure evidence for issue #192."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from threading import Barrier, Lock
from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI, Header
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT
from deployment.postgresql.security_audit_query import SecurityAuditQueryRunner
from deployment.postgresql.tenant_contract import OIDC_ISSUER_EQUALITY_POLICY
from kernel import security_audit_gap as audit_gap
from kernel import security_audit_health as audit_health
from kernel import tenant_uow
from kernel.application_runtime import ApplicationRuntime, RuntimeMetadata
from kernel.authentication import (
    AuthenticationError,
    AuthenticationOutcome,
    VerifiedIdentity,
)
from kernel.authentication_audit import AuthenticationAuditProducer
from kernel.google_kms_correlation_hmac import CorrelationHmacUnavailable
from kernel.principal import PrincipalResolutionError
from kernel.principal_resolver import PrincipalBindingResolver
from kernel.request_router_audit import RequestRouterAuditProducer
from kernel.runtime_config import RuntimeMode
from kernel.security_audit import CorrelationHmac, SecurityAuditError
from kernel.security_audit_client import PreTenantAuditClient
from kernel.security_audit_runtime import PreTenantAuditRuntime
from kernel.tenant_capability_issuer import CapabilityMintError
from kernel.tests.postgresql_audit_support import audit_service_fixture  # noqa: F401
from kernel.tests.postgresql_audit_support import role_dsn
from kernel.tests.test_postgresql_tenant_migration import (
    ISSUER,
    CapabilityKeyAuthority,
    TenantAuthority,
    TenantTarget,
    authority,  # noqa: F401
    capability_key,  # noqa: F401
    tenant_target,  # noqa: F401
)
from kernel.tests.test_postgresql_tenant_uow import _FixtureMinter, _knowledge_head


VALID_TOKEN = "TOKEN-CANARY-VALID"
UNKNOWN_IDENTITY_TOKEN = "TOKEN-CANARY-UNKNOWN-IDENTITY"
MALFORMED_TOKEN = "TOKEN-CANARY-MALFORMED"
REFUSED_TOKEN = "TOKEN-CANARY-REFUSED"
UNAVAILABLE_TOKEN = "TOKEN-CANARY-UNAVAILABLE"
UNKNOWN_ISSUER = "https://issuer-canary.example.test/tenant"
UNKNOWN_SUBJECT = "SUBJECT-CANARY-UNKNOWN"
BODY_CANARY = b"BODY-CANARY TENANT-CANARY PARTY-CANARY"
ROUTE_CANARY = "ROUTE-CANARY"
DSN_CANARY = "DSN-LABEL-CANARY"
PASSWORD_CANARY = "PASSWORD-CANARY"
EXCEPTION_CANARY = "EXCEPTION-CANARY"
PRODUCER_OPTIONS = "-c statement_timeout=2000 -c lock_timeout=250"
SHARED_HARNESS_CANARIES = (DSN_CANARY, PASSWORD_CANARY, EXCEPTION_CANARY)
HMAC_CANARY_FIELDS = "ISSUER SUBJECT TENANT PARTY BODY BATCH REQUEST ROUTE".split()


def _producer(component: str):
    matches = tuple(
        item
        for item in SECURITY_AUDIT_CONTRACT.reason_matrix
        if item.component == component
    )
    assert len(matches) == 1
    return matches[0]


AUTHENTICATION = _producer("AUTHENTICATION")
REQUEST_ROUTER = _producer("REQUEST_ROUTER")


class _DeterministicVerifier:
    def __init__(self, subject: str) -> None:
        self._subject = subject
        self._lock = Lock()
        self._barrier: Barrier | None = None

    def set_barrier(self, barrier: Barrier | None) -> None:
        with self._lock:
            self._barrier = barrier

    def verify(self, token: object) -> VerifiedIdentity:
        with self._lock:
            barrier = self._barrier
        if barrier is not None:
            barrier.wait(timeout=10)
        if token == VALID_TOKEN:
            return VerifiedIdentity(
                equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
                issuer=ISSUER,
                subject=self._subject,
            )
        if token == UNKNOWN_IDENTITY_TOKEN:
            return VerifiedIdentity(
                equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
                issuer=UNKNOWN_ISSUER,
                subject=UNKNOWN_SUBJECT,
            )
        outcomes = {
            None: AuthenticationOutcome.NO_CREDENTIAL,
            MALFORMED_TOKEN: AuthenticationOutcome.CREDENTIAL_MALFORMED,
            REFUSED_TOKEN: AuthenticationOutcome.VERIFICATION_REFUSED,
            UNAVAILABLE_TOKEN: AuthenticationOutcome.VERIFIER_UNAVAILABLE,
        }
        outcome = outcomes.get(token, AuthenticationOutcome.CREDENTIAL_MALFORMED)
        raise AuthenticationError(
            outcome,
            internal_detail=f"{EXCEPTION_CANARY}-{outcome.value}",
        )


class _SwitchableHmac:
    def __init__(self) -> None:
        self._lock, self._refuse = Lock(), False

    def refuse_once(self) -> None:
        with self._lock:
            self._refuse = True

    def create(self) -> CorrelationHmac:
        with self._lock:
            refused, self._refuse = self._refuse, False
        if refused:
            raise CorrelationHmacUnavailable()
        version = SECURITY_AUDIT_CONTRACT.correlation_hmac.key_version
        assert version is not None
        return CorrelationHmac(b"c" * 32, version)


class _SwitchableAuditFactory:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._lock = Lock()
        self._failures = 0
        self._refused = psycopg.conninfo.make_conninfo(
            dsn,
            host=f"/tmp/ofarm-cross-slice-{DSN_CANARY}-{uuid4().hex}",
            password=PASSWORD_CANARY,
        )

    def refuse_once(self) -> None:
        with self._lock:
            self._failures += 1

    def __call__(self):
        with self._lock:
            refused = self._failures > 0
            if refused:
                self._failures -= 1
        return psycopg.connect(
            self._refused if refused else self._dsn,
            connect_timeout=5,
            options=PRODUCER_OPTIONS,
        )


class _RecordingAppender:
    def __init__(self, inner: PreTenantAuditClient) -> None:
        self._inner = inner
        self._lock = Lock()
        self._invocations = 0
        self._results: list[tuple[str, object]] = []

    def append(self, reason: str, correlation_hmac: CorrelationHmac):
        with self._lock:
            self._invocations += 1
        result = self._inner.append(reason, correlation_hmac)
        with self._lock:
            self._results.append((reason, result.event_id))
        return result

    def snapshot(self) -> tuple[int, tuple[tuple[str, object], ...]]:
        with self._lock:
            return self._invocations, tuple(self._results)


class _SwitchableMinter:
    def __init__(self, key: CapabilityKeyAuthority) -> None:
        self._inner = _FixtureMinter(key)
        self._lock = Lock()
        self._failures = 0

    def refuse_once(self) -> None:
        with self._lock:
            self._failures += 1

    def mint(self, identity, principal_authority, challenge):
        with self._lock:
            refused = self._failures > 0
            if refused:
                self._failures -= 1
        if refused:
            raise CapabilityMintError(f"{EXCEPTION_CANARY}-CAPABILITY")
        return self._inner.mint(identity, principal_authority, challenge)


class _RecordingResolver:
    def __init__(self, inner: PrincipalBindingResolver) -> None:
        self._inner = inner
        self._lock = Lock()
        self._calls = 0

    @property
    def calls(self) -> int:
        with self._lock:
            return self._calls

    def resolve(self, identity):
        with self._lock:
            self._calls += 1
        return self._inner.resolve(identity)


class _RecordingBoundary:
    def __init__(self, inner: tenant_uow.TenantUnitOfWorkManager) -> None:
        self._inner = inner
        self._lock = Lock()
        self._entries = 0
        self._yields = 0

    @property
    def counts(self) -> tuple[int, int]:
        with self._lock:
            return self._entries, self._yields

    @contextmanager
    def unit_of_work(self, principal):
        with self._lock:
            self._entries += 1
        with self._inner.unit_of_work(principal) as unit:
            with self._lock:
                self._yields += 1
            yield unit


class _BodyFailure(RuntimeError):
    pass


@dataclass(slots=True)
class _Harness:
    client: TestClient
    target: TenantTarget
    authority: TenantAuthority
    verifier: _DeterministicVerifier
    hmac: _SwitchableHmac
    minter: _SwitchableMinter
    resolver: _RecordingResolver
    boundary: _RecordingBoundary
    health: audit_health.SecurityAuditHealth
    gap: audit_gap.SecurityAuditGapController
    authentication_factory: _SwitchableAuditFactory
    authentication_appender: _RecordingAppender
    request_router_appender: _RecordingAppender
    audit_state: dict[str, object]
    tenant_system_id: str
    audit_system_id: str


def _system_id(dsn: str) -> str:
    with psycopg.connect(dsn) as connection:
        row = connection.execute(
            "SELECT system_identifier::text FROM pg_control_system()"
        ).fetchone()
    assert row is not None and type(row[0]) is str and row[0]
    return row[0]


@pytest.fixture(scope="module")
def cross_slice(
    tenant_target: TenantTarget,  # noqa: F811
    authority: TenantAuthority,  # noqa: F811
    capability_key: CapabilityKeyAuthority,  # noqa: F811
    migrated_audit_service,
):
    audit_state = migrated_audit_service
    tenant_system_id = _system_id(tenant_target.admin_dsn)
    audit_system_id = _system_id(str(audit_state["admin_dsn"]))
    assert tenant_system_id != audit_system_id

    tenant_dsn = tenant_target.role_dsn("ofarm_app")
    resolver_inner = PrincipalBindingResolver(lambda: psycopg.connect(tenant_dsn))
    resolver_inner.initialize()
    resolver = _RecordingResolver(resolver_inner)
    minter = _SwitchableMinter(capability_key)
    pool = tenant_uow.create_tenant_connection_pool(tenant_dsn)
    manager = tenant_uow.TenantUnitOfWorkManager(pool, minter)
    manager.initialize()
    pool.resize(2, 2)
    pool.wait(timeout=5)
    boundary = _RecordingBoundary(manager)

    authentication_factory = _SwitchableAuditFactory(
        role_dsn(audit_state, AUTHENTICATION.session_user)
    )
    request_router_factory = _SwitchableAuditFactory(
        role_dsn(audit_state, REQUEST_ROUTER.session_user)
    )
    authentication_appender = _RecordingAppender(
        PreTenantAuditClient(authentication_factory, AUTHENTICATION)
    )
    request_router_appender = _RecordingAppender(
        PreTenantAuditClient(request_router_factory, REQUEST_ROUTER)
    )
    health = audit_health.SecurityAuditHealth()
    hmac = _SwitchableHmac()
    gap_dsn = role_dsn(audit_state, "ofarm_security_audit_control_login")
    gap = audit_gap.SecurityAuditGapController(
        audit_gap.SecurityAuditGapClient(gap_dsn)
    )
    verifier = _DeterministicVerifier(authority.subject)
    authentication = AuthenticationAuditProducer(
        verifier,
        resolver,
        gap.authentication_sink(
            health.authentication_sink(hmac, authentication_appender)
        ),
    )
    request_router = RequestRouterAuditProducer(
        boundary,
        gap.request_router_sink(
            health.request_router_sink(hmac, request_router_appender)
        ),
    )
    runtime = ApplicationRuntime(
        PreTenantAuditRuntime(authentication, request_router, health),
        object(),
        RuntimeMetadata(
            mode=RuntimeMode.PRODUCTION,
            deployment_image_digest="sha256:" + "1" * 64,
            oidc_issuer=ISSUER,
            oidc_audience="cross-slice-evidence",
            binder_audience=resolver_inner.audience,
            tenant_capability_kid=capability_key.kid,
        ),
        object(),
        object(),
        manager,
    )
    app = FastAPI()

    @app.post("/evidence/{action}")
    def evidence(
        action: str,
        authorization: str | None = Header(default=None),
        x_batch_id: str | None = Header(default=None),
        x_request_id: str | None = Header(default=None),
    ):
        token = None
        if authorization is not None:
            token = (
                authorization[7:]
                if authorization.startswith("Bearer ")
                else authorization
            )
        try:
            principal = runtime.authenticate(token)
        except AuthenticationError:
            return PlainTextResponse("authentication refused\n", status_code=401)
        except PrincipalResolutionError:
            return PlainTextResponse("principal refused\n", status_code=403)
        except (SecurityAuditError, audit_gap.SecurityAuditGapError):
            return PlainTextResponse("audit unavailable\n", status_code=503)
        try:
            with runtime.tenant_unit_of_work(principal) as unit:
                if x_batch_id is None or x_request_id is None:
                    return PlainTextResponse("request invalid\n", status_code=400)
                unit.begin_batch(
                    tenant_uow.GovernedBatchRequest(
                        x_batch_id,
                        "CROSS_SLICE_EVIDENCE",
                        x_request_id,
                        authority.runtime_bundle_digest,
                    )
                )
                if action == "rollback":
                    raise _BodyFailure(f"{EXCEPTION_CANARY}-BODY")
        except _BodyFailure:
            return PlainTextResponse("request rolled back\n", status_code=409)
        except tenant_uow.TenantBoundaryError:
            return PlainTextResponse("tenant entry refused\n", status_code=403)
        except (SecurityAuditError, audit_gap.SecurityAuditGapError):
            return PlainTextResponse("audit unavailable\n", status_code=503)
        return PlainTextResponse("request accepted\n", status_code=200)

    try:
        with TestClient(app) as client:
            yield _Harness(
                client=client,
                target=tenant_target,
                authority=authority,
                verifier=verifier,
                hmac=hmac,
                minter=minter,
                resolver=resolver,
                boundary=boundary,
                health=health,
                gap=gap,
                authentication_factory=authentication_factory,
                authentication_appender=authentication_appender,
                request_router_appender=request_router_appender,
                audit_state=audit_state,
                tenant_system_id=tenant_system_id,
                audit_system_id=audit_system_id,
            )
    finally:
        manager.close()


def _request(
    harness: _Harness,
    token: str | None,
    action: str = "commit",
    *,
    batch_id: str | None = None,
    request_id: str | None = None,
    route_canary: str | None = None,
    body: bytes = BODY_CANARY,
):
    headers = {"Content-Type": "application/octet-stream"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if batch_id is not None:
        headers["X-Batch-Id"] = batch_id
    if request_id is not None:
        headers["X-Request-Id"] = request_id
    suffix = f"?input={route_canary}" if route_canary is not None else ""
    return harness.client.post(
        f"/evidence/{action}{suffix}",
        headers=headers,
        content=body,
    )


def _hostile_request(harness: _Harness, label: str, token: str):
    canaries = tuple(f"{kind}-CANARY-HMAC-{label}" for kind in HMAC_CANARY_FIELDS)
    response = _request(
        harness,
        token,
        batch_id=canaries[5],
        request_id=canaries[6],
        route_canary=canaries[7],
        body=" ".join(canaries[:5]).encode(),
    )
    return response, (token, *canaries)


def _audit_events(harness: _Harness) -> dict[object, object]:
    query = SecurityAuditQueryRunner().run(
        role_dsn(
            harness.audit_state,
            "ofarm_security_audit_control_login",
        ),
        role_dsn(
            harness.audit_state,
            "ofarm_security_audit_reader_login",
        ),
        None,
    )
    return {
        event.event_id: event
        for event in query.events
        if event.event_kind in {"PRE_TENANT_FAILURE", "AUDIT_GAP"}
    }


def _audit_delta(before: dict[object, object], after: dict[object, object]):
    return tuple(after[event_id] for event_id in after.keys() - before.keys())


def _response_projection(response):
    headers = tuple(
        sorted((name.lower(), value) for name, value in response.headers.multi_items())
    )
    return response.status_code, bytes(response.content), headers


def _assert_no_canary_leak(responses, events, captured, forbidden, *evidence) -> None:
    response_projection = tuple(_response_projection(item) for item in responses)
    event_projection = tuple(asdict(event) for event in events)
    surface = repr((response_projection, event_projection, evidence))
    surface += captured.out + captured.err
    assert all(value not in surface for value in forbidden)


def _tenant_posture(harness: _Harness):
    return (
        _knowledge_head(harness.target, harness.authority.tenant_id),
        harness.resolver.calls,
        harness.boundary.counts,
    )


def _evidence_posture(harness: _Harness):
    return (
        harness.authentication_appender.snapshot(),
        _tenant_posture(harness),
        harness.health.readiness,
        harness.gap.state,
    )


def _batch_row(harness: _Harness, batch_id: str):
    with psycopg.connect(harness.target.target_admin_dsn) as admin:
        return admin.execute(
            """
            SELECT tenant_id, batch_id, authenticated_principal_ref,
                   governed_operation, request_id, runtime_bundle_digest
            FROM ofarm.governed_write_batch
            WHERE tenant_id = %s AND batch_id = %s
            """,
            (harness.authority.tenant_id, batch_id),
        ).fetchone()


def _assert_event(event, producer, reason: str) -> None:
    assert event.event_kind == "PRE_TENANT_FAILURE"
    assert (event.producer, event.component, event.reason) == (
        producer.producer,
        producer.component,
        reason,
    )


def test_two_services_and_unmatched_route_have_no_effect(cross_slice: _Harness):
    before = _audit_events(cross_slice)
    head = _knowledge_head(cross_slice.target, cross_slice.authority.tenant_id)
    calls = (cross_slice.resolver.calls, cross_slice.boundary.counts)
    response = cross_slice.client.post(
        f"/unregistered-{ROUTE_CANARY}",
        headers={"Authorization": f"Bearer {MALFORMED_TOKEN}"},
        content=BODY_CANARY,
    )
    assert cross_slice.tenant_system_id != cross_slice.audit_system_id
    assert response.status_code == 404
    assert ROUTE_CANARY not in response.text
    assert all(
        canary not in response.text
        for canary in ("BODY-CANARY", "TENANT-CANARY", "PARTY-CANARY", "DSN-CANARY")
    )
    assert _audit_events(cross_slice) == before
    assert _knowledge_head(cross_slice.target, cross_slice.authority.tenant_id) == head
    assert (cross_slice.resolver.calls, cross_slice.boundary.counts) == calls
    assert cross_slice.health.readiness is audit_health.SecurityAuditReadiness.READY
    assert cross_slice.gap.state is audit_gap.SecurityAuditGapState.CLEAR


@pytest.mark.parametrize(
    ("token", "reason"),
    (
        (None, "CREDENTIAL_MISSING"),
        (MALFORMED_TOKEN, "CREDENTIAL_MALFORMED"),
        (REFUSED_TOKEN, "VERIFICATION_REFUSED"),
        (UNAVAILABLE_TOKEN, "VERIFIER_UNAVAILABLE"),
    ),
)
def test_authentication_denial_is_audit_only(
    cross_slice: _Harness,
    token: str | None,
    reason: str,
):
    before = _audit_events(cross_slice)
    head = _knowledge_head(cross_slice.target, cross_slice.authority.tenant_id)
    resolver_calls = cross_slice.resolver.calls
    boundary_counts = cross_slice.boundary.counts
    response = _request(cross_slice, token)
    all_events = _audit_events(cross_slice)
    delta = _audit_delta(before, all_events)
    assert (response.status_code, response.text) == (401, "authentication refused\n")
    assert len(delta) == 1
    _assert_event(delta[0], AUTHENTICATION, reason)
    assert cross_slice.resolver.calls == resolver_calls
    assert cross_slice.boundary.counts == boundary_counts
    assert _knowledge_head(cross_slice.target, cross_slice.authority.tenant_id) == head


def test_principal_denial_is_audit_only(cross_slice: _Harness):
    before = _audit_events(cross_slice)
    head = _knowledge_head(cross_slice.target, cross_slice.authority.tenant_id)
    resolver_calls = cross_slice.resolver.calls
    boundary_counts = cross_slice.boundary.counts
    response = _request(cross_slice, UNKNOWN_IDENTITY_TOKEN, route_canary=ROUTE_CANARY)
    delta = _audit_delta(before, _audit_events(cross_slice))
    assert (response.status_code, response.text) == (403, "principal refused\n")
    assert len(delta) == 1
    _assert_event(delta[0], AUTHENTICATION, "PRINCIPAL_BINDING_REFUSED")
    assert cross_slice.resolver.calls == resolver_calls + 1
    assert cross_slice.boundary.counts == boundary_counts
    assert _knowledge_head(cross_slice.target, cross_slice.authority.tenant_id) == head


def test_capability_refusal_uses_only_router_lane(cross_slice: _Harness):
    before = _audit_events(cross_slice)
    head = _knowledge_head(cross_slice.target, cross_slice.authority.tenant_id)
    entries, yields = cross_slice.boundary.counts
    batch_id = f"batch-capability-{uuid4().hex}"
    cross_slice.minter.refuse_once()
    response = _request(
        cross_slice,
        VALID_TOKEN,
        batch_id=batch_id,
        request_id=f"request-capability-{uuid4().hex}",
    )
    delta = _audit_delta(before, _audit_events(cross_slice))
    assert (response.status_code, response.text) == (403, "tenant entry refused\n")
    assert len(delta) == 1
    _assert_event(delta[0], REQUEST_ROUTER, "CAPABILITY_REFUSED")
    assert cross_slice.boundary.counts == (entries + 1, yields)
    assert _batch_row(cross_slice, batch_id) is None
    assert _knowledge_head(cross_slice.target, cross_slice.authority.tenant_id) == head


def test_successful_binding_commits_tenant_only(cross_slice: _Harness):
    before = _audit_events(cross_slice)
    batch_id = f"batch-success-{uuid4().hex}"
    request_id = f"request-success-{uuid4().hex}"
    response = _request(
        cross_slice,
        VALID_TOKEN,
        batch_id=batch_id,
        request_id=request_id,
    )
    assert (response.status_code, response.text) == (200, "request accepted\n")
    assert _audit_events(cross_slice) == before
    assert _batch_row(cross_slice, batch_id) == (
        cross_slice.authority.tenant_id,
        batch_id,
        cross_slice.authority.party_ref,
        "CROSS_SLICE_EVIDENCE",
        request_id,
        cross_slice.authority.runtime_bundle_digest,
    )


def test_post_binding_body_failure_rolls_back_without_audit(cross_slice: _Harness):
    before = _audit_events(cross_slice)
    head = _knowledge_head(cross_slice.target, cross_slice.authority.tenant_id)
    batch_id = f"batch-rollback-{uuid4().hex}"
    response = _request(
        cross_slice,
        VALID_TOKEN,
        "rollback",
        batch_id=batch_id,
        request_id=f"request-rollback-{uuid4().hex}",
    )
    assert (response.status_code, response.text) == (409, "request rolled back\n")
    assert _batch_row(cross_slice, batch_id) is None
    assert _knowledge_head(cross_slice.target, cross_slice.authority.tenant_id) == head
    assert _audit_events(cross_slice) == before


def _assert_failure_recovery(
    cross_slice: _Harness,
    capsys: pytest.CaptureFixture[str],
    label: str,
    refuse_once,
    failed_invocations: int,
    gap_posture: tuple[int | None, bool],
) -> None:
    before, posture_before = _audit_events(cross_slice), _evidence_posture(cross_slice)
    refuse_once()

    failed, failed_canaries = _hostile_request(
        cross_slice, f"{label}-FAILED", MALFORMED_TOKEN
    )
    posture_after_failed = _evidence_posture(cross_slice)
    recorder_before = posture_before[0]
    assert (failed.status_code, failed.text) == (503, "audit unavailable\n")
    assert posture_after_failed == (
        (recorder_before[0] + failed_invocations, recorder_before[1]),
        posture_before[1],
        audit_health.SecurityAuditReadiness.NOT_READY,
        audit_gap.SecurityAuditGapState.OPEN,
    )

    recovered, recovery_canaries = _hostile_request(
        cross_slice, f"{label}-RECOVERY", REFUSED_TOKEN
    )
    delta = _audit_delta(before, _audit_events(cross_slice))
    failures = [event for event in delta if event.event_kind == "PRE_TENANT_FAILURE"]
    gaps = [event for event in delta if event.event_kind == "AUDIT_GAP"]
    posture_after_recovery = _evidence_posture(cross_slice)
    assert (recovered.status_code, recovered.text) == (401, "authentication refused\n")
    assert len(failures) == len(gaps) == 1
    _assert_event(failures[0], AUTHENTICATION, "VERIFICATION_REFUSED")
    assert (gaps[0].interval_event_count, gaps[0].interval_count_unknown) == gap_posture
    assert posture_after_recovery == (
        (
            recorder_before[0] + failed_invocations + 1,
            recorder_before[1] + (("VERIFICATION_REFUSED", failures[0].event_id),),
        ),
        posture_before[1],
        audit_health.SecurityAuditReadiness.READY,
        audit_gap.SecurityAuditGapState.CLEAR,
    )
    _assert_no_canary_leak(
        (failed, recovered),
        delta,
        capsys.readouterr(),
        (*failed_canaries, *recovery_canaries, *SHARED_HARNESS_CANARIES),
        (posture_before, posture_after_failed, posture_after_recovery),
    )


def test_audit_failure_denies_then_later_lane_success_closes_gap(
    cross_slice: _Harness,
    capsys: pytest.CaptureFixture[str],
):
    refuse_once = cross_slice.authentication_factory.refuse_once
    _assert_failure_recovery(cross_slice, capsys, "AUDIT", refuse_once, 1, (1, False))


def test_hmac_failure_denies_then_later_lane_success_closes_gap(
    cross_slice: _Harness,
    capsys: pytest.CaptureFixture[str],
):
    refuse_once = cross_slice.hmac.refuse_once
    _assert_failure_recovery(cross_slice, capsys, "HMAC", refuse_once, 0, (None, True))


def test_concurrent_denial_and_commit_are_isolated_and_leak_free(
    cross_slice: _Harness,
    capsys: pytest.CaptureFixture[str],
):
    before = _audit_events(cross_slice)
    router_records = cross_slice.request_router_appender.snapshot()
    batch_id = f"BATCH-CANARY-{uuid4().hex}"
    request_id = f"REQUEST-CANARY-{uuid4().hex}"
    cross_slice.verifier.set_barrier(Barrier(2))
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            denied = executor.submit(_request, cross_slice, MALFORMED_TOKEN)
            accepted = executor.submit(
                _request,
                cross_slice,
                VALID_TOKEN,
                batch_id=batch_id,
                request_id=request_id,
                route_canary=ROUTE_CANARY,
            )
            responses = (denied.result(timeout=15), accepted.result(timeout=15))
    finally:
        cross_slice.verifier.set_barrier(None)
    all_events = _audit_events(cross_slice)
    delta = _audit_delta(before, all_events)
    assert {(item.status_code, item.text) for item in responses} == {
        (401, "authentication refused\n"),
        (200, "request accepted\n"),
    }
    assert len(delta) == 1
    _assert_event(delta[0], AUTHENTICATION, "CREDENTIAL_MALFORMED")
    assert _batch_row(cross_slice, batch_id) == (
        cross_slice.authority.tenant_id,
        batch_id,
        cross_slice.authority.party_ref,
        "CROSS_SLICE_EVIDENCE",
        request_id,
        cross_slice.authority.runtime_bundle_digest,
    )
    forbidden = (
        VALID_TOKEN,
        UNKNOWN_IDENTITY_TOKEN,
        MALFORMED_TOKEN,
        REFUSED_TOKEN,
        UNAVAILABLE_TOKEN,
        ISSUER,
        UNKNOWN_ISSUER,
        UNKNOWN_SUBJECT,
        cross_slice.authority.subject,
        str(cross_slice.authority.tenant_id),
        cross_slice.authority.party_ref,
        batch_id,
        request_id,
        ROUTE_CANARY,
        "BODY-CANARY",
        "TENANT-CANARY",
        "PARTY-CANARY",
        DSN_CANARY,
        PASSWORD_CANARY,
        EXCEPTION_CANARY,
    )
    _assert_no_canary_leak(
        responses,
        all_events.values(),
        capsys.readouterr(),
        forbidden,
    )
    assert cross_slice.request_router_appender.snapshot() == router_records
