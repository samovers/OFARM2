"""Production composition and startup admission for pre-tenant audit."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from types import MappingProxyType

import psycopg
from google.cloud import kms_v1

from deployment.postgresql.audit_contract import (
    SECURITY_AUDIT_CONTRACT,
    ProducerReasonSpec,
)
from deployment.postgresql.readiness import (
    verify_postgresql_service_separation,
    verify_security_audit_structural_compatibility,
    verify_tenant_structural_compatibility,
)

from .authentication_audit import AuthenticationAuditProducer
from .google_kms_correlation_hmac import GoogleKmsCorrelationHmac
from .principal import AuthenticatedPrincipal
from .principal_resolver import PrincipalBindingResolver
from .production_oidc import ProductionOidcVerifier
from .request_router_audit import RequestRouterAuditProducer
from .runtime_config import RuntimeConfig
from .security_audit_client import PreTenantAuditClient
from .security_audit_hmac_posture import (
    CorrelationHmacLifecyclePosture,
    CorrelationHmacLifecycleObserver,
    CorrelationHmacVersionDisposition,
)
from .tenant_uow import TenantUnitOfWork, TenantUnitOfWorkManager


Connection = psycopg.Connection[tuple[object, ...]]
ConnectionFactory = Callable[[], Connection]
_READ_ONLY = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
_DATABASE_SESSION_USERS = MappingProxyType(
    {
        "tenant_readiness_pg_dsn": "ofarm_readiness",
        "security_audit_readiness_pg_dsn": "ofarm_security_audit_readiness_login",
        "security_audit_authentication_pg_dsn":
            "ofarm_security_authentication_producer_login",
        "security_audit_request_router_pg_dsn":
            "ofarm_security_request_router_producer_login",
        "security_audit_control_pg_dsn": "ofarm_security_audit_control_login",
    }
)


class PreTenantAuditRuntimeUnavailable(RuntimeError):
    """The production pre-tenant audit graph cannot be admitted."""


class PreTenantAuditRuntime:
    def __init__(
        self,
        authentication: AuthenticationAuditProducer,
        request_router: RequestRouterAuditProducer,
    ) -> None:
        self._authentication = authentication
        self._request_router = request_router

    def authenticate(self, token: str) -> AuthenticatedPrincipal:
        return self._authentication.authenticate(token)

    def unit_of_work(
        self,
        principal: AuthenticatedPrincipal,
    ) -> AbstractContextManager[TenantUnitOfWork]:
        return self._request_router.unit_of_work(principal)


def _connection_factory(dsn: str) -> ConnectionFactory:
    def connect() -> Connection:
        return psycopg.connect(dsn)

    return connect


def _require_session_user(factory: ConnectionFactory, expected: str) -> None:
    try:
        with factory() as connection:
            if connection.autocommit is not False:
                raise PreTenantAuditRuntimeUnavailable()
            with connection.transaction():
                connection.execute(_READ_ONLY)
                cursor = connection.execute("SELECT SESSION_USER::text")
                row = cursor.fetchone()
                duplicate = cursor.fetchone()
                if row != (expected,) or duplicate is not None:
                    raise PreTenantAuditRuntimeUnavailable()
    except PreTenantAuditRuntimeUnavailable:
        raise
    except Exception as exc:
        raise PreTenantAuditRuntimeUnavailable() from exc


def _verify_database_authorities(config: RuntimeConfig) -> None:
    for field, expected in _DATABASE_SESSION_USERS.items():
        factory = _connection_factory(getattr(config, field))
        _require_session_user(factory, expected)


def _producer(component: str) -> ProducerReasonSpec:
    matches = tuple(
        producer
        for producer in SECURITY_AUDIT_CONTRACT.reason_matrix
        if producer.component == component
    )
    if len(matches) != 1:
        raise PreTenantAuditRuntimeUnavailable()
    return matches[0]


def _active_resource(
    config: RuntimeConfig,
    posture: CorrelationHmacLifecyclePosture,
) -> str:
    active = tuple(
        version
        for version in posture.versions
        if version.disposition is CorrelationHmacVersionDisposition.ACTIVE
    )
    if len(active) != 1:
        raise PreTenantAuditRuntimeUnavailable()
    parent = config.correlation_hmac_kms_key_resource
    return f"{parent}/cryptoKeyVersions/{active[0].key_version}"


def build_pretenant_audit_runtime(
    config: RuntimeConfig,
    verifier: ProductionOidcVerifier,
    resolver: PrincipalBindingResolver,
    tenant_boundary: TenantUnitOfWorkManager,
    kms_client: kms_v1.KeyManagementServiceClient,
) -> PreTenantAuditRuntime:
    verify_tenant_structural_compatibility(
        tenant_structural_dsn=config.tenant_readiness_pg_dsn
    )
    verify_security_audit_structural_compatibility(
        audit_structural_dsn=config.security_audit_readiness_pg_dsn
    )
    verify_postgresql_service_separation(
        tenant_structural_dsn=config.tenant_readiness_pg_dsn,
        audit_structural_dsn=config.security_audit_readiness_pg_dsn,
    )
    _verify_database_authorities(config)
    control_factory = _connection_factory(config.security_audit_control_pg_dsn)
    posture = CorrelationHmacLifecycleObserver(
        control_factory,
        kms_client,
        config.correlation_hmac_kms_key_resource,
    ).current()
    correlation_hmac = GoogleKmsCorrelationHmac(
        kms_client,
        _active_resource(config, posture),
    )
    correlation_hmac.initialize()
    authentication = AuthenticationAuditProducer(
        verifier,
        resolver,
        correlation_hmac,
        PreTenantAuditClient(
            _connection_factory(config.security_audit_authentication_pg_dsn),
            _producer("AUTHENTICATION"),
        ),
    )
    request_router = RequestRouterAuditProducer(
        tenant_boundary,
        correlation_hmac,
        PreTenantAuditClient(
            _connection_factory(config.security_audit_request_router_pg_dsn),
            _producer("REQUEST_ROUTER"),
        ),
    )
    return PreTenantAuditRuntime(authentication, request_router)
