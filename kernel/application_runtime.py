"""Ordered production graph construction and its sealed public surface."""
from __future__ import annotations

from contextlib import AbstractContextManager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx
import psycopg
from google.cloud import kms_v1

from deployment.postgresql.tenant_contract import (
    TENANT_CAPABILITY_PREFLIGHT_PROBE,
)

from .authentication import VerifiedIdentity
from .deployment_identity import require_deployment_image_digest
from .google_kms_signer import GoogleKmsSigner
from .principal import AuthenticatedPrincipal, PrincipalAuthority
from .principal_resolver import PrincipalBindingResolver
from .production_oidc import ProductionOidcConfig, ProductionOidcVerifier
from .runtime_config import RuntimeConfig, RuntimeMode
from .security_audit_runtime import (
    PreTenantAuditRuntime,
    build_pretenant_audit_runtime,
)
from .security_audit_health import SecurityAuditReadiness
from .signing_authority import SigningAuthorityReader
from .signing_receipt import (
    SIGNING_EVIDENCE_MAX_BYTES,
    SigningEvidenceVerifier,
)
from .tenant_capability_issuer import (
    TenantCapabilityIssuer,
    TenantChallenge,
)
from .tenant_uow import (
    TenantUnitOfWork,
    TenantUnitOfWorkManager,
    create_tenant_connection_pool,
)


class RuntimeStartupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RuntimeMetadata:
    mode: RuntimeMode
    deployment_image_digest: str
    oidc_issuer: str
    oidc_audience: str
    binder_audience: str
    tenant_capability_kid: str
    tenant_boundary: str = "transaction-bound"

    def as_dict(self) -> dict[str, str]:
        return {
            "mode": self.mode.value,
            "deploymentImageDigest": self.deployment_image_digest,
            "oidcIssuer": self.oidc_issuer,
            "oidcAudience": self.oidc_audience,
            "binderAudience": self.binder_audience,
            "tenantCapabilityKid": self.tenant_capability_kid,
            "tenantBoundary": self.tenant_boundary,
        }


class ApplicationRuntime:
    def __init__(
        self,
        security_audit: PreTenantAuditRuntime,
        issuer: TenantCapabilityIssuer,
        metadata: RuntimeMetadata,
        oidc_client: httpx.Client,
        kms_client: kms_v1.KeyManagementServiceClient,
        tenant_uow: TenantUnitOfWorkManager,
    ) -> None:
        self._security_audit = security_audit
        self._issuer = issuer
        self.metadata = metadata
        self._oidc_client = oidc_client
        self._kms_client = kms_client
        self._tenant_uow = tenant_uow

    def authenticate(self, token: str) -> AuthenticatedPrincipal:
        return self._security_audit.authenticate(token)

    def mint_capability(
        self,
        identity: VerifiedIdentity,
        authority: PrincipalAuthority,
        challenge: TenantChallenge,
    ) -> str:
        return self._issuer.mint(identity, authority, challenge)

    def tenant_unit_of_work(
        self,
        principal: AuthenticatedPrincipal,
    ) -> AbstractContextManager[TenantUnitOfWork]:
        return self._security_audit.unit_of_work(principal)

    @property
    def security_audit_readiness(self) -> SecurityAuditReadiness:
        return self._security_audit.readiness

    def close(self) -> None:
        try:
            self._tenant_uow.close()
        finally:
            _close_runtime_clients(self._oidc_client, self._kms_client)


def _close_runtime_clients(
    oidc_client: httpx.Client,
    kms_client: kms_v1.KeyManagementServiceClient,
) -> None:
    try:
        oidc_client.close()
    finally:
        kms_client.transport.close()


def _receipt_source(path: Path) -> bytes:
    with path.open("rb") as stream:
        receipt = stream.read(SIGNING_EVIDENCE_MAX_BYTES + 1)
    if not 1 <= len(receipt) <= SIGNING_EVIDENCE_MAX_BYTES:
        raise OSError("signing evidence receipt size differs")
    return receipt


def _connection_factory(
    dsn: str,
) -> Callable[[], psycopg.Connection[tuple[object, ...]]]:
    def connect() -> psycopg.Connection[tuple[object, ...]]:
        return psycopg.connect(dsn)

    return connect


def build_application_runtime(config: RuntimeConfig) -> ApplicationRuntime:
    if type(config) is not RuntimeConfig or config.mode is not RuntimeMode.PRODUCTION:
        raise RuntimeStartupError("production runtime config differs")
    image_digest = require_deployment_image_digest(
        config.deployment_image_digest
    )
    oidc_client = httpx.Client(follow_redirects=False)
    try:
        kms_client = kms_v1.KeyManagementServiceClient()
    except Exception:
        with suppress(Exception):
            oidc_client.close()
        raise
    tenant_uow = None
    try:
        connection_factory = _connection_factory(config.pg_dsn)
        verifier = ProductionOidcVerifier(
            ProductionOidcConfig(
                issuer=config.oidc_issuer,
                audience=config.oidc_audience,
                jwks_url=config.oidc_jwks_url,
            ),
            oidc_client,
        )
        resolver = PrincipalBindingResolver(connection_factory)
        signing_reader = SigningAuthorityReader(
            connection_factory,
            lambda: _receipt_source(config.signing_evidence_receipt_path),
            SigningEvidenceVerifier(
                config.signing_evidence_observer_public_key
            ),
        )
        signer = GoogleKmsSigner(kms_client)
        issuer = TenantCapabilityIssuer(
            signing_reader,
            signer,
            kid=config.tenant_capability_kid,
        )
        tenant_uow = TenantUnitOfWorkManager(
            create_tenant_connection_pool(config.pg_dsn),
            issuer,
        )
        verifier.initialize()
        resolver.initialize()
        security_audit = build_pretenant_audit_runtime(
            config,
            verifier,
            resolver,
            tenant_uow,
            kms_client,
        )
        signing = signing_reader.current(config.tenant_capability_kid)
        if signing.audience != resolver.audience:
            raise RuntimeStartupError("database runtime audiences differ")
        signer.sign(TENANT_CAPABILITY_PREFLIGHT_PROBE, signing)
        tenant_uow.initialize()
        metadata = RuntimeMetadata(
            mode=RuntimeMode.PRODUCTION,
            deployment_image_digest=image_digest,
            oidc_issuer=config.oidc_issuer,
            oidc_audience=config.oidc_audience,
            binder_audience=resolver.audience,
            tenant_capability_kid=config.tenant_capability_kid,
        )
        return ApplicationRuntime(
            security_audit,
            issuer,
            metadata,
            oidc_client,
            kms_client,
            tenant_uow,
        )
    except Exception:
        if tenant_uow is not None:
            with suppress(Exception):
                tenant_uow.close()
        with suppress(Exception):
            _close_runtime_clients(oidc_client, kms_client)
        raise
