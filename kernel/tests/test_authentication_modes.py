"""Security tests for #172's explicit modes and maintained OIDC verifier."""
from __future__ import annotations

import time
from dataclasses import FrozenInstanceError, dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from deployment.postgresql.tenant_contract import derive_binder_audience
from kernel import config, demo
from kernel.api import create_app, create_test_app
from kernel.auth_oidc import (
    AuthenticationMode,
    AuthenticationRuntime,
    AuthenticationStartupError,
    OidcConfig,
    OidcError,
    PreBindingOutcome,
    ProductionAuthenticationRuntime,
    ProductionOidcConfig,
    ProductionOidcVerifier,
)
from kernel.principal_binding import (
    PostgreSQLPrincipalBindingResolver,
    PrincipalBindingAuthority,
)
from kernel.runtime_activation import RuntimeActivationError
from kernel.runtime_composition import (
    AuthenticationRuntimeMetadata,
    ProductionApplicationRuntime,
)
from kernel.tenant_capability import (
    CapabilityIssuanceError,
    GoogleCloudKmsClientAdapter,
    GoogleKmsEd25519Signer,
    ProductionTenantCapabilityIssuer,
)


ISSUER = "https://issuer.example.test/tenant"
AUDIENCE = "ofarm-production"
JWKS_URL = "https://issuer.example.test/tenant/jwks"


@dataclass
class _SigningKey:
    key_id: str
    algorithm_name: str
    key: object
    public_key_use: str | None = None
    _jwk_data: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self._jwk_data is None and isinstance(self.key, rsa.RSAPublicKey):
            self._jwk_data = {
                "kty": "RSA",
                "alg": self.algorithm_name,
            }


@dataclass
class _JwkSet:
    keys: list[_SigningKey]


class _JwksClient:
    def __init__(self, keys: list[_SigningKey], *, unavailable: bool = False):
        self.keys = keys
        self.unavailable = unavailable
        self.refreshes: list[bool] = []

    def get_jwk_set(self, *, refresh: bool):
        self.refreshes.append(refresh)
        if self.unavailable:
            raise RuntimeError("provider detail must stay private")
        return _JwkSet(self.keys)

    def get_signing_key(self, key_id: str):
        for key in self.keys:
            if key.key_id == key_id:
                return key
        raise RuntimeError("unknown key")


class _Resolver:
    def __init__(self):
        self.initialized = False

    def initialize(self):
        self.initialized = True

    def resolve(self, identity):
        return type("Binding", (), {"party_ref": "party:bound"})()


class _AuthorityResolver:
    def __init__(self, authority):
        self.authority = authority
        self.initialized = False

    def initialize(self):
        self.initialized = True

    def resolve(self, identity):
        assert self.initialized
        assert identity.issuer == self.authority.issuer
        assert identity.subject == self.authority.subject
        return self.authority


@pytest.fixture(scope="module")
def rsa_keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


def _production_verifier(
    rsa_keys,
    *,
    client=None,
    clock=None,
    algorithms=("RS256",),
    jwks_lifespan_seconds=300,
    jwks_miss_refresh_seconds=5,
):
    _, public = rsa_keys
    selected = client or _JwksClient([_SigningKey("key-1", "RS256", public)])
    return ProductionOidcVerifier.for_test(
        ProductionOidcConfig(
            issuer=ISSUER,
            audience=AUDIENCE,
            jwks_url=JWKS_URL,
            algorithms=algorithms,
            jwks_lifespan_seconds=jwks_lifespan_seconds,
            jwks_miss_refresh_seconds=jwks_miss_refresh_seconds,
        ),
        jwks_client=selected,
        clock=clock,
    )


def _production_oidc_config() -> ProductionOidcConfig:
    return ProductionOidcConfig(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=JWKS_URL,
        algorithms=("RS256",),
    )


def _authority() -> PrincipalBindingAuthority:
    now = datetime.now(UTC)
    return PrincipalBindingAuthority(
        equality_policy="OIDC_EXACT_UTF8_V1",
        issuer=ISSUER,
        subject="subject-01",
        binding_version_id=uuid4(),
        binding_version_digest="sha256:" + "11" * 32,
        lifecycle_head_id=uuid4(),
        lifecycle_head_digest="sha256:" + "22" * 32,
        tenant_id=uuid4(),
        tenant_registration_digest="sha256:" + "33" * 32,
        party_ref="party:bound",
        party_record_kind="ofarm.party.v0.1",
        party_record_id="party:bound",
        party_schema_digest="sha256:" + "44" * 32,
        party_payload_digest="sha256:" + "55" * 32,
        party_state="ACTIVE",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
    )


def _sealed_production_composition() -> ProductionApplicationRuntime:
    resolver = PostgreSQLPrincipalBindingResolver(lambda: None)
    authentication = AuthenticationRuntime.production(
        ProductionOidcVerifier(_production_oidc_config()),
        resolver,
    )
    signer = object.__new__(GoogleKmsEd25519Signer)
    issuer = ProductionTenantCapabilityIssuer(
        resolver=resolver,
        signer=signer,
    )
    return ProductionApplicationRuntime(
        authentication=authentication,
        capability_issuer=issuer,
    )


def _signed_token(private, *, key_id="key-1", algorithm="RS256", **claims):
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "sub": "subject-01",
        "aud": AUDIENCE,
        "iat": now,
        "nbf": now - 1,
        "exp": now + 60,
    }
    payload.update(claims)
    return jwt.encode(
        payload,
        private,
        algorithm=algorithm,
        headers={"kid": key_id},
    )


def _token(rsa_keys, **claims):
    private, _ = rsa_keys
    return _signed_token(private, **claims)


def test_mode_is_required_and_never_inferred(monkeypatch):
    monkeypatch.delenv("OFARM_AUTH_MODE", raising=False)
    monkeypatch.setenv("OFARM_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OFARM_OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("OFARM_OIDC_HS256_SECRET", "not-a-mode-selector")
    with pytest.raises(AuthenticationStartupError, match="OFARM_AUTH_MODE is required"):
        config.authentication_runtime_from_env()


def test_environment_modes_are_exact_and_production_forbids_hs256(monkeypatch):
    monkeypatch.setenv("OFARM_AUTH_MODE", "development")
    assert config.authentication_runtime_from_env().mode is AuthenticationMode.DEVELOPMENT
    monkeypatch.setenv("OFARM_AUTH_MODE", "Development")
    with pytest.raises(AuthenticationStartupError):
        config.authentication_runtime_from_env()
    monkeypatch.setenv("OFARM_AUTH_MODE", "production")
    monkeypatch.setenv("OFARM_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OFARM_OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("OFARM_OIDC_JWKS_URL", JWKS_URL)
    monkeypatch.setenv("OFARM_OIDC_HS256_SECRET", "forbidden")
    with pytest.raises(AuthenticationStartupError, match="forbidden"):
        config.authentication_runtime_from_env(principal_binding_resolver=_Resolver())


def test_production_startup_requires_initialized_jwks_and_binding_resolver(rsa_keys):
    unavailable = _JwksClient([], unavailable=True)
    runtime = AuthenticationRuntime.production_for_test(
        _production_verifier(rsa_keys, client=unavailable), _Resolver()
    )
    with pytest.raises(AuthenticationStartupError, match="JWKS initialization failed"):
        runtime.initialize()
    with pytest.raises(AuthenticationStartupError, match="resolver"):
        AuthenticationRuntime.production_for_test(
            _production_verifier(rsa_keys),
            None,
        )
    with pytest.raises(TypeError):
        AuthenticationRuntime(
            AuthenticationMode.PRODUCTION,
            verifier=_production_verifier(rsa_keys),
        )


def test_local_hs256_verifier_is_structurally_rejected_by_production():
    local = OidcConfig(
        issuer=ISSUER,
        audience=AUDIENCE,
        hs256_secret="test-only",
    )
    with pytest.raises(AuthenticationStartupError, match="HS256"):
        AuthenticationRuntime.production(local, _Resolver()).initialize()


def test_wrapped_hs256_verifier_is_rejected_at_production_construction():
    local = OidcConfig(
        issuer=ISSUER,
        audience=AUDIENCE,
        hs256_secret="test-only",
    )

    class WrappedVerifier:
        def initialize(self):
            local.initialize()

        def verify_identity(self, token):
            return local.verify_identity(token)

    with pytest.raises(AuthenticationStartupError, match="wrapped verifiers"):
        AuthenticationRuntime.production(WrappedVerifier(), _Resolver())


def test_wrapped_or_mutable_binding_resolver_is_rejected_by_production(
    rsa_keys, monkeypatch
):
    verifier = ProductionOidcVerifier(_production_oidc_config())
    with pytest.raises(AuthenticationStartupError, match="sealed PostgreSQL"):
        AuthenticationRuntime.production(verifier, _Resolver())
    monkeypatch.setenv("OFARM_AUTH_MODE", "production")
    monkeypatch.setenv("OFARM_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OFARM_OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("OFARM_OIDC_JWKS_URL", JWKS_URL)
    monkeypatch.delenv("OFARM_OIDC_HS256_SECRET", raising=False)
    with pytest.raises(AuthenticationStartupError, match="sealed PostgreSQL"):
        config.authentication_runtime_from_env(principal_binding_resolver=_Resolver())
    sealed = PostgreSQLPrincipalBindingResolver(lambda: None)
    runtime = AuthenticationRuntime.production(verifier, sealed)
    assert runtime.principal_binding_resolver is sealed


def test_production_rejects_a_verifier_with_injected_trust_inputs(rsa_keys):
    _, public = rsa_keys
    client = _JwksClient([_SigningKey("key-1", "RS256", public)])
    injected = ProductionOidcVerifier.for_test(
        _production_oidc_config(),
        jwks_client=client,
        clock=lambda: 1_000.0,
    )
    sealed = PostgreSQLPrincipalBindingResolver(lambda: None)

    with pytest.raises(AuthenticationStartupError, match="injected trust inputs"):
        AuthenticationRuntime.production(injected, sealed)
    with pytest.raises(TypeError):
        ProductionOidcVerifier(
            _production_oidc_config(),
            jwks_client=client,
        )


def test_legacy_oidc_argument_rejects_a_production_verifier(rsa_keys):
    production = _production_verifier(rsa_keys)
    with pytest.raises(AuthenticationStartupError, match="exact OidcConfig or None"):
        create_test_app(oidc=production)
    with pytest.raises(AuthenticationStartupError, match="exact local OidcConfig"):
        AuthenticationRuntime.test(production)


def test_production_runtime_uses_binding_not_subject_as_party(rsa_keys):
    resolver = _Resolver()
    runtime = AuthenticationRuntime.production_for_test(
        _production_verifier(rsa_keys), resolver
    )
    runtime.initialize()
    party_ref, binding = runtime.resolve_principal(
        authorization=f"Bearer {_token(rsa_keys)}",
        development_header="party:must-not-authenticate",
    )
    assert resolver.initialized
    assert party_ref == "party:bound"
    assert binding.party_ref == "party:bound"


def test_production_app_rejects_test_runtime_subclasses_and_mutation(rsa_keys):
    resolver = _Resolver()
    runtime = AuthenticationRuntime.production_for_test(
        _production_verifier(rsa_keys), resolver
    )
    with pytest.raises(AuthenticationStartupError, match="exact production"):
        create_app(authentication=runtime)

    class RuntimeSubclass(ProductionAuthenticationRuntime):
        def initialize(self):
            raise AssertionError("subclass method must not run")

    with pytest.raises(AuthenticationStartupError, match="exact production"):
        create_app(authentication=object.__new__(RuntimeSubclass))

    runtime.initialize()
    with pytest.raises(FrozenInstanceError):
        runtime.mode = AuthenticationMode.DEVELOPMENT
    with pytest.raises(FrozenInstanceError):
        runtime.principal_binding_resolver = _Resolver()


def test_deployment_identity_preflight_precedes_runtime_construction(
    monkeypatch,
):
    constructed = []

    def unexpected_runtime_construction(**_kwargs):
        constructed.append(True)
        raise AssertionError(
            "invalid deployment identity reached authentication construction"
        )

    monkeypatch.setattr(
        config,
        "authentication_runtime_from_env",
        unexpected_runtime_construction,
    )
    with pytest.raises(RuntimeActivationError):
        create_app(deployment_image_digest="sha256:not-a-deployment-digest")
    assert constructed == []


@pytest.mark.parametrize(
    ("invalid_name", "invalid_value"),
    (
        (
            "OFARM_TENANT_CAPABILITY_SIGNING_KEY_VERSION",
            "not-a-kms-key-version",
        ),
        (
            "OFARM_SIGNING_EVIDENCE_OBSERVER_KEY_VERSION",
            "not-a-kms-key-version",
        ),
        ("OFARM_SIGNING_EVIDENCE_RECEIPT_PATH", "relative/receipt.json"),
        ("OFARM_SIGNING_EVIDENCE_HIGH_WATER_PATH", "relative/head.json"),
    ),
)
def test_production_signing_configuration_refuses_before_any_kms_client(
    monkeypatch,
    tmp_path,
    invalid_name,
    invalid_value,
):
    runtime = AuthenticationRuntime.production(
        ProductionOidcVerifier(_production_oidc_config()),
        PostgreSQLPrincipalBindingResolver(lambda: None),
    )
    monkeypatch.setenv(
        "OFARM_TENANT_CAPABILITY_SIGNING_KEY_VERSION",
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/capability/cryptoKeyVersions/1",
    )
    monkeypatch.setenv(
        "OFARM_SIGNING_EVIDENCE_OBSERVER_KEY_VERSION",
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/evidence-observer/cryptoKeyVersions/1",
    )
    monkeypatch.setenv(
        "OFARM_SIGNING_EVIDENCE_RECEIPT_PATH",
        str(tmp_path / "receipt.json"),
    )
    monkeypatch.setenv(
        "OFARM_SIGNING_EVIDENCE_HIGH_WATER_PATH",
        str(tmp_path / "high-water.json"),
    )
    monkeypatch.setenv(invalid_name, invalid_value)
    constructions = []
    authority_initializations = []
    monkeypatch.setattr(
        ProductionAuthenticationRuntime,
        "initialize",
        lambda _runtime: authority_initializations.append(True),
    )
    monkeypatch.setattr(
        GoogleCloudKmsClientAdapter,
        "__init__",
        lambda _adapter: constructions.append(True),
    )

    with pytest.raises(
        AuthenticationStartupError,
        match="production (KMS key resource|signing-evidence path) "
        "configuration is invalid",
    ):
        config.production_application_runtime(runtime)
    assert constructions == []
    assert authority_initializations == []


def test_production_signer_uses_db_pinned_audience_without_reinitializing_auth(
    monkeypatch,
    tmp_path,
):
    resolver = PostgreSQLPrincipalBindingResolver(lambda: None)
    runtime = AuthenticationRuntime.production(
        ProductionOidcVerifier(_production_oidc_config()),
        resolver,
    )
    binder_audience = derive_binder_audience(uuid4())
    assert binder_audience != AUDIENCE
    monkeypatch.setattr(
        PostgreSQLPrincipalBindingResolver,
        "audience",
        property(lambda _resolver: binder_audience),
        raising=False,
    )
    initialization_order = []

    def initialize_authentication(selected_runtime):
        initialization_order.append("authentication")
        object.__setattr__(selected_runtime, "_initialized", True)

    monkeypatch.setattr(
        ProductionAuthenticationRuntime,
        "initialize",
        initialize_authentication,
    )
    monkeypatch.setattr(
        ProductionTenantCapabilityIssuer,
        "initialize",
        lambda _issuer: initialization_order.append("capability"),
    )
    monkeypatch.setenv(
        "OFARM_TENANT_CAPABILITY_SIGNING_KEY_VERSION",
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/capability/cryptoKeyVersions/1",
    )
    monkeypatch.setenv(
        "OFARM_SIGNING_EVIDENCE_OBSERVER_KEY_VERSION",
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/evidence-observer/cryptoKeyVersions/1",
    )
    monkeypatch.setenv(
        "OFARM_SIGNING_EVIDENCE_RECEIPT_PATH",
        str(tmp_path / "receipt.json"),
    )
    monkeypatch.setenv(
        "OFARM_SIGNING_EVIDENCE_HIGH_WATER_PATH",
        str(tmp_path / "high-water.json"),
    )
    signing_private_key = ed25519.Ed25519PrivateKey.generate()

    def construct_without_external_client(adapter):
        adapter._client = object()
        adapter._production_eligible = True

    monkeypatch.setattr(
        GoogleCloudKmsClientAdapter,
        "__init__",
        construct_without_external_client,
    )
    monkeypatch.setattr(
        GoogleCloudKmsClientAdapter,
        "get_ed25519_public_key",
        lambda _adapter, *, name: signing_private_key.public_key(),
    )
    observed_audiences = []

    def capture_audience(_signer, *, client, public_key, audience):
        assert type(client) is GoogleCloudKmsClientAdapter
        assert public_key.public_key == (
            signing_private_key.public_key().public_bytes_raw()
        )
        observed_audiences.append(audience)

    monkeypatch.setattr(
        GoogleKmsEd25519Signer,
        "__init__",
        capture_audience,
    )

    composition = config.production_application_runtime(runtime)
    assert observed_audiences == [binder_audience]
    composition.initialize()
    composition.initialize()
    assert initialization_order == ["authentication", "capability"]


def test_production_composition_initializes_every_boundary_and_propagates_refusal(
    monkeypatch,
):
    composition = _sealed_production_composition()
    initialized = []

    def initialize_authentication(_runtime):
        initialized.append("authentication")

    def refuse_stale_evidence(_issuer):
        initialized.append("capability")
        raise CapabilityIssuanceError(
            PreBindingOutcome.SIGNER_UNAVAILABLE,
            internal_detail="stale evidence detail must stay private",
        )

    monkeypatch.setattr(
        ProductionAuthenticationRuntime,
        "initialize",
        initialize_authentication,
    )
    monkeypatch.setattr(
        ProductionTenantCapabilityIssuer,
        "initialize",
        refuse_stale_evidence,
    )

    with pytest.raises(CapabilityIssuanceError) as raised:
        composition.initialize()
    assert raised.value.outcome is PreBindingOutcome.SIGNER_UNAVAILABLE
    assert initialized == ["authentication", "capability"]
    assert "stale evidence detail" not in str(raised.value)


def test_request_authentication_has_no_mutable_app_state_authority_alias(
    store,
):
    app = create_test_app(store, oidc=None)

    class MutableStateBypass:
        mode = AuthenticationMode.DEVELOPMENT

        def resolve_principal(self, **_kwargs):
            return demo.FARMER, None

        def get_record(self, _record_ref):
            return {
                "record_kind": "ofarm.party.v0.1",
                "payload": {"partyState": "ACTIVE"},
            }

    exposed = app.state._state
    assert "oidc" not in exposed
    assert "get_principal" not in exposed
    assert type(exposed["authentication"]) is AuthenticationRuntimeMetadata
    with pytest.raises(FrozenInstanceError):
        exposed["authentication"].mode = AuthenticationMode.PRODUCTION

    principal_dependencies = {
        dependency.call
        for route in app.routes
        for dependency in getattr(
            getattr(route, "dependant", None),
            "dependencies",
            (),
        )
        if getattr(dependency.call, "__name__", None) == "get_principal"
    }
    assert len(principal_dependencies) == 1
    get_principal = principal_dependencies.pop()

    for name, original in tuple(exposed.items()):
        setattr(app.state, name, MutableStateBypass())
        try:
            with pytest.raises(HTTPException) as raised:
                get_principal(
                    authorization=None,
                    x_acting_party=None,
                )
            assert raised.value.status_code == 401
            assert (
                raised.value.detail["reasonCode"]
                == "AUTHORITY_DENIED"
            )
        finally:
            setattr(app.state, name, original)


def test_production_refuses_legacy_store_surface_with_full_binding(
    store,
    rsa_keys,
):
    authority = _authority()
    runtime = AuthenticationRuntime.production_for_test(
        _production_verifier(rsa_keys),
        _AuthorityResolver(authority),
    )
    app = create_test_app(store, authentication=runtime)

    with TestClient(app) as client:
        response = client.get(
            "/records/record:not-present",
            headers={"Authorization": f"Bearer {_token(rsa_keys)}"},
        )

    assert response.status_code == 503
    assert response.json()["detail"]["reasonCode"] == "TENANT_BOUNDARY_BLOCKED"


def test_safe_failure_outcome_does_not_expose_exception_detail():
    error = OidcError(
        PreBindingOutcome.VERIFIER_UNAVAILABLE,
        internal_detail="token=secret issuer=private stack=provider",
    )
    assert str(error) == "authentication refused (VERIFIER_UNAVAILABLE)"
    assert "secret" not in str(error)
