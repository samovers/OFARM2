"""Ordered production graph construction and its sealed public surface."""
from __future__ import annotations

from contextlib import suppress
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
from .google_kms_signer import GoogleKmsSigner
from .principal import AuthenticatedPrincipal, PrincipalAuthority
from .principal_resolver import PrincipalBindingResolver
from .production_oidc import ProductionOidcConfig, ProductionOidcVerifier
from .runtime_activation import require_deployment_image_digest
from .runtime_config import RuntimeConfig, RuntimeMode
from .signing_authority import SigningAuthorityReader
from .signing_receipt import (
    SIGNING_EVIDENCE_MAX_BYTES,
    SigningEvidenceVerifier,
)
from .tenant_capability_issuer import (
    TenantCapabilityIssuer,
    TenantChallenge,
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
    tenant_boundary: str = "blocked"

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
        verifier: ProductionOidcVerifier,
        resolver: PrincipalBindingResolver,
        issuer: TenantCapabilityIssuer,
        metadata: RuntimeMetadata,
        oidc_client: httpx.Client,
        kms_client: kms_v1.KeyManagementServiceClient,
    ) -> None:
        self._verifier = verifier
        self._resolver = resolver
        self._issuer = issuer
        self.metadata = metadata
        self._oidc_client = oidc_client
        self._kms_client = kms_client

    def authenticate(self, token: str) -> AuthenticatedPrincipal:
        return self._resolver.resolve(self._verifier.verify(token))

    def mint_capability(
        self,
        identity: VerifiedIdentity,
        authority: PrincipalAuthority,
        challenge: TenantChallenge,
    ) -> str:
        return self._issuer.mint(identity, authority, challenge)

    def close(self) -> None:
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
    try:
        verifier.initialize()
        resolver.initialize()
        signing = signing_reader.current(config.tenant_capability_kid)
        if signing.audience != resolver.audience:
            raise RuntimeStartupError("database runtime audiences differ")
        signer.sign(TENANT_CAPABILITY_PREFLIGHT_PROBE, signing)
    except Exception:
        with suppress(Exception):
            _close_runtime_clients(oidc_client, kms_client)
        raise
    metadata = RuntimeMetadata(
        mode=RuntimeMode.PRODUCTION,
        deployment_image_digest=image_digest,
        oidc_issuer=config.oidc_issuer,
        oidc_audience=config.oidc_audience,
        binder_audience=resolver.audience,
        tenant_capability_kid=config.tenant_capability_kid,
    )
    return ApplicationRuntime(
        verifier,
        resolver,
        issuer,
        metadata,
        oidc_client,
        kms_client,
    )
