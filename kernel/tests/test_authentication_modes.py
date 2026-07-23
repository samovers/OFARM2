"""Security tests for #172's explicit modes and maintained OIDC verifier."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, dataclass
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from fastapi.testclient import TestClient

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
from kernel.runtime_composition import ProductionApplicationRuntime
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


def test_maintained_verifier_accepts_exact_identity_and_initializes_fresh_jwks(rsa_keys):
    verifier = _production_verifier(rsa_keys)
    verifier.initialize()
    identity = verifier.verify_identity(_token(rsa_keys))
    assert identity.issuer == ISSUER
    assert identity.subject == "subject-01"
    assert identity.equality_policy == "OIDC_EXACT_UTF8_V1"
    assert verifier._jwks_client.refreshes == [True]


def test_default_pyjwt_client_disables_unbounded_per_key_cache(rsa_keys, monkeypatch):
    _, public = rsa_keys
    client = _JwksClient([_SigningKey("key-1", "RS256", public)])
    observed = {}

    def client_factory(url, **kwargs):
        observed["url"] = url
        observed.update(kwargs)
        return client

    monkeypatch.setattr(jwt, "PyJWKClient", client_factory)
    verifier = ProductionOidcVerifier(
        ProductionOidcConfig(
            issuer=ISSUER,
            audience=AUDIENCE,
            jwks_url=JWKS_URL,
            algorithms=("RS256",),
        )
    )
    verifier.initialize()
    assert observed["url"] == JWKS_URL
    assert observed["cache_keys"] is False
    assert "max_cached_keys" not in observed


def test_maintained_verifier_accepts_a_new_key_id_after_jwks_rotation(rsa_keys):
    _, old_public = rsa_keys
    client = _JwksClient([_SigningKey("key-1", "RS256", old_public)])
    verifier = _production_verifier(rsa_keys, client=client)
    verifier.initialize()
    assert verifier.verify_identity(_token(rsa_keys)).subject == "subject-01"

    new_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client.keys.append(_SigningKey("key-2", "RS256", new_private.public_key()))
    now = int(time.time())
    rotated = jwt.encode(
        {
            "iss": ISSUER,
            "sub": "subject-02",
            "aud": AUDIENCE,
            "exp": now + 60,
        },
        new_private,
        algorithm="RS256",
        headers={"kid": "key-2"},
    )
    assert verifier.verify_identity(rotated).subject == "subject-02"


def test_alg_less_rsa_jwk_supports_configured_ps256(rsa_keys):
    private, public = rsa_keys
    jwk_data = jwt.algorithms.RSAAlgorithm.to_jwk(public, as_dict=True)
    jwk_data.update({"kid": "key-ps256", "use": "sig"})
    assert "alg" not in jwk_data
    alg_less_key = jwt.PyJWK.from_dict(jwk_data)
    assert alg_less_key.algorithm_name == "RS256"
    client = _JwksClient([alg_less_key])
    verifier = _production_verifier(
        rsa_keys,
        client=client,
        algorithms=("PS256",),
    )
    verifier.initialize()

    token = _signed_token(
        private,
        key_id="key-ps256",
        algorithm="PS256",
        sub="subject-ps256",
    )
    assert verifier.verify_identity(token).subject == "subject-ps256"


@pytest.mark.parametrize(
    ("algorithm", "declared"),
    (
        ("RS256", True),
        ("RS256", False),
        ("PS256", True),
        ("PS256", False),
    ),
)
def test_undersized_rsa_jwks_refuses_declared_and_alg_less_keys(
    rsa_keys, algorithm, declared
):
    weak_private = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    jwk_data = jwt.algorithms.RSAAlgorithm.to_jwk(
        weak_private.public_key(), as_dict=True
    )
    jwk_data.update({"kid": "weak-key", "use": "sig"})
    if declared:
        jwk_data["alg"] = algorithm
    weak_key = jwt.PyJWK.from_dict(jwk_data)
    verifier = _production_verifier(
        rsa_keys,
        client=_JwksClient([weak_key]),
        algorithms=(algorithm,),
    )

    with pytest.raises(
        AuthenticationStartupError, match="JWKS initialization failed"
    ):
        verifier.initialize()


def test_unknown_key_ids_share_one_bounded_jwks_miss_refresh(rsa_keys):
    private, public = rsa_keys
    now = [1_000.0]
    client = _JwksClient([_SigningKey("key-1", "RS256", public)])
    verifier = _production_verifier(
        rsa_keys,
        client=client,
        clock=lambda: now[0],
        jwks_miss_refresh_seconds=5,
    )
    verifier.initialize()

    for index in range(10):
        with pytest.raises(OidcError) as raised:
            verifier.verify_identity(
                _signed_token(private, key_id=f"attacker-key-{index}")
            )
        assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL
    assert client.refreshes == [True, True]

    now[0] += 5
    with pytest.raises(OidcError):
        verifier.verify_identity(_signed_token(private, key_id="next-window"))
    assert client.refreshes == [True, True, True]


def test_failed_jwks_miss_refresh_keeps_unknown_keys_invalid_and_bounded(rsa_keys):
    private, public = rsa_keys
    client = _JwksClient([_SigningKey("key-1", "RS256", public)])
    verifier = _production_verifier(rsa_keys, client=client, clock=lambda: 1_000.0)
    verifier.initialize()
    client.unavailable = True

    for key_id in ("attacker-key-1", "attacker-key-2"):
        with pytest.raises(OidcError) as raised:
            verifier.verify_identity(_signed_token(private, key_id=key_id))
        assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL
    assert client.refreshes == [True, True]


def test_jwks_miss_refresh_does_not_lock_current_key_verification(rsa_keys):
    private, public = rsa_keys
    refresh_started = Event()
    release_refresh = Event()

    class BlockingRefreshClient(_JwksClient):
        def get_jwk_set(self, *, refresh: bool):
            if self.refreshes:
                refresh_started.set()
                if not release_refresh.wait(timeout=2):
                    raise RuntimeError("test refresh was not released")
            return super().get_jwk_set(refresh=refresh)

    client = BlockingRefreshClient([_SigningKey("key-1", "RS256", public)])
    verifier = _production_verifier(rsa_keys, client=client)
    verifier.initialize()
    valid = _signed_token(private)
    unknown = _signed_token(private, key_id="attacker-key")

    with ThreadPoolExecutor(max_workers=2) as executor:
        hostile_result = executor.submit(verifier.verify_identity, unknown)
        assert refresh_started.wait(timeout=1)
        valid_result = executor.submit(verifier.verify_identity, valid)
        try:
            assert valid_result.result(timeout=1).subject == "subject-01"
        finally:
            release_refresh.set()
        with pytest.raises(OidcError):
            hostile_result.result(timeout=1)


def test_slow_unknown_key_refresh_is_non_blocking_and_completion_bounded(rsa_keys):
    private, public = rsa_keys
    now = [1_000.0]
    refresh_started = Event()
    release_refresh = Event()

    class SlowRefreshClient(_JwksClient):
        def get_jwk_set(self, *, refresh: bool):
            if self.refreshes:
                now[0] += 2
                refresh_started.set()
                if not release_refresh.wait(timeout=2):
                    raise RuntimeError("test refresh was not released")
            return super().get_jwk_set(refresh=refresh)

    client = SlowRefreshClient([_SigningKey("key-1", "RS256", public)])
    verifier = _production_verifier(
        rsa_keys,
        client=client,
        clock=lambda: now[0],
        jwks_miss_refresh_seconds=1,
    )
    verifier.initialize()
    valid = _signed_token(private)

    with ThreadPoolExecutor(max_workers=24) as executor:
        first_miss = executor.submit(
            verifier.verify_identity,
            _signed_token(private, key_id="attacker-key-first"),
        )
        assert refresh_started.wait(timeout=1)
        concurrent_misses = [
            executor.submit(
                verifier.verify_identity,
                _signed_token(private, key_id=f"attacker-key-{index}"),
            )
            for index in range(16)
        ]
        valid_result = executor.submit(verifier.verify_identity, valid)
        assert valid_result.result(timeout=1).subject == "subject-01"
        for result in concurrent_misses:
            with pytest.raises(OidcError):
                result.result(timeout=1)
        release_refresh.set()
        with pytest.raises(OidcError):
            first_miss.result(timeout=1)

    with pytest.raises(OidcError):
        verifier.verify_identity(
            _signed_token(private, key_id="attacker-key-after-completion")
        )
    assert client.refreshes == [True, True]


def test_removed_used_key_expires_with_the_bounded_jwks_generation(rsa_keys):
    private, public = rsa_keys
    backup_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = [1_000.0]
    client = _JwksClient(
        [
            _SigningKey("key-1", "RS256", public),
            _SigningKey("key-2", "RS256", backup_private.public_key()),
        ]
    )
    verifier = _production_verifier(
        rsa_keys,
        client=client,
        clock=lambda: now[0],
        jwks_lifespan_seconds=60,
    )
    token = _signed_token(private)
    verifier.initialize()
    assert verifier.verify_identity(token).subject == "subject-01"

    client.keys = [_SigningKey("key-2", "RS256", backup_private.public_key())]
    assert verifier.verify_identity(token).subject == "subject-01"
    now[0] += 60
    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(token)
    assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL
    assert client.refreshes == [True, True]


def test_same_kid_key_replacement_takes_effect_after_jwks_lifespan(rsa_keys):
    old_private, old_public = rsa_keys
    new_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = [2_000.0]
    client = _JwksClient([_SigningKey("key-1", "RS256", old_public)])
    verifier = _production_verifier(
        rsa_keys,
        client=client,
        clock=lambda: now[0],
        jwks_lifespan_seconds=60,
    )
    old_token = _signed_token(old_private)
    new_token = _signed_token(new_private, sub="subject-02")
    verifier.initialize()
    assert verifier.verify_identity(old_token).subject == "subject-01"

    client.keys = [_SigningKey("key-1", "RS256", new_private.public_key())]
    now[0] += 60
    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(old_token)
    assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL
    assert verifier.verify_identity(new_token).subject == "subject-02"


def test_duplicate_or_encryption_only_jwks_refuses_startup(rsa_keys):
    _, public = rsa_keys
    duplicate = _JwksClient(
        [
            _SigningKey("key-1", "RS256", public),
            _SigningKey("key-1", "RS256", public),
        ]
    )
    with pytest.raises(AuthenticationStartupError, match="JWKS initialization failed"):
        _production_verifier(rsa_keys, client=duplicate).initialize()

    encryption_only = _JwksClient(
        [_SigningKey("key-1", "RS256", public, public_key_use="enc")]
    )
    with pytest.raises(AuthenticationStartupError, match="JWKS initialization failed"):
        _production_verifier(rsa_keys, client=encryption_only).initialize()


def test_duplicate_signing_identity_after_refresh_is_verifier_unavailable(rsa_keys):
    _, public = rsa_keys
    now = [3_000.0]
    client = _JwksClient([_SigningKey("key-1", "RS256", public)])
    verifier = _production_verifier(
        rsa_keys,
        client=client,
        clock=lambda: now[0],
        jwks_lifespan_seconds=60,
    )
    verifier.initialize()
    client.keys.append(_SigningKey("key-1", "RS256", public))
    now[0] += 60
    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(_token(rsa_keys))
    assert raised.value.outcome is PreBindingOutcome.VERIFIER_UNAVAILABLE


def test_provider_outage_after_jwks_expiry_is_verifier_unavailable(rsa_keys):
    _, public = rsa_keys
    now = [4_000.0]
    client = _JwksClient([_SigningKey("key-1", "RS256", public)])
    verifier = _production_verifier(
        rsa_keys,
        client=client,
        clock=lambda: now[0],
        jwks_lifespan_seconds=60,
    )
    verifier.initialize()
    client.unavailable = True
    now[0] += 60
    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(_token(rsa_keys))
    assert raised.value.outcome is PreBindingOutcome.VERIFIER_UNAVAILABLE
    assert "provider detail" not in str(raised.value)


def test_slow_failed_expiry_refresh_is_non_blocking_and_retry_bounded(rsa_keys):
    private, public = rsa_keys
    now = [5_000.0]
    refresh_started = Event()
    release_refresh = Event()

    class SlowFailingRefreshClient(_JwksClient):
        def get_jwk_set(self, *, refresh: bool):
            self.refreshes.append(refresh)
            if len(self.refreshes) > 1:
                refresh_started.set()
                if not release_refresh.wait(timeout=2):
                    raise RuntimeError("test refresh was not released")
                raise RuntimeError("provider detail must stay private")
            return _JwkSet(self.keys)

    client = SlowFailingRefreshClient(
        [_SigningKey("key-1", "RS256", public)]
    )
    verifier = _production_verifier(
        rsa_keys,
        client=client,
        clock=lambda: now[0],
        jwks_lifespan_seconds=60,
    )
    verifier.initialize()
    token = _signed_token(private)
    now[0] += 60

    with ThreadPoolExecutor(max_workers=18) as executor:
        first_refresh = executor.submit(verifier.verify_identity, token)
        assert refresh_started.wait(timeout=1)
        concurrent_requests = [
            executor.submit(verifier.verify_identity, token)
            for _ in range(16)
        ]
        for result in concurrent_requests:
            with pytest.raises(OidcError) as raised:
                result.result(timeout=1)
            assert raised.value.outcome is PreBindingOutcome.VERIFIER_UNAVAILABLE
        release_refresh.set()
        with pytest.raises(OidcError) as raised:
            first_refresh.result(timeout=1)
        assert raised.value.outcome is PreBindingOutcome.VERIFIER_UNAVAILABLE

    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(token)
    assert raised.value.outcome is PreBindingOutcome.VERIFIER_UNAVAILABLE
    assert client.refreshes == [True, True]

    now[0] += 5
    with pytest.raises(OidcError):
        verifier.verify_identity(token)
    assert client.refreshes == [True, True, True]


@pytest.mark.parametrize(
    "claims",
    (
        {"sub": " subject-01"},
        {"sub": "subject-01 "},
        {"sub": "subject with space"},
        {"sub": "subject-ž"},
        {"sub": "x" * 256},
        {"iss": "https://ISSUER.example.test/tenant"},
        {"iss": ISSUER + "/"},
    ),
)
def test_exact_identity_policy_refuses_case_whitespace_unicode_and_overlength(
    rsa_keys, claims
):
    verifier = _production_verifier(rsa_keys)
    verifier.initialize()
    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(_token(rsa_keys, **claims))
    assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL
    assert "subject-01" not in str(raised.value)


def test_key_id_algorithm_time_and_provider_failures_are_closed(rsa_keys):
    verifier = _production_verifier(rsa_keys)
    verifier.initialize()
    private, _ = rsa_keys
    now = int(time.time())
    base = {"iss": ISSUER, "sub": "subject-01", "aud": AUDIENCE, "exp": now + 60}
    missing_kid = jwt.encode(base, private, algorithm="RS256")
    wrong_kid = jwt.encode(
        base, private, algorithm="RS256", headers={"kid": "rotated-away"}
    )
    expired = _token(rsa_keys, exp=now - 1)
    future = _token(rsa_keys, nbf=now + 300)
    for token in (missing_kid, wrong_kid, expired, future):
        with pytest.raises(OidcError):
            verifier.verify_identity(token)


def test_oversized_numeric_date_refuses_before_key_selection(rsa_keys):
    verifier = _production_verifier(rsa_keys)
    verifier.initialize()
    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(_token(rsa_keys, exp=10**400))
    assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL
    assert verifier._jwks_client.refreshes == [True]


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


def test_production_composition_requires_signing_evidence_configuration(
    monkeypatch,
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
    monkeypatch.delenv(
        "OFARM_SIGNING_EVIDENCE_RECEIPT_PATH",
        raising=False,
    )

    with pytest.raises(
        AuthenticationStartupError,
        match="production capability boundary construction failed",
    ):
        config.production_application_runtime(runtime)


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


def test_request_authentication_is_closed_over_not_loaded_from_app_state(store):
    app = create_test_app(store, oidc=None)

    class MutableStateBypass:
        mode = AuthenticationMode.DEVELOPMENT

        def resolve_principal(self, **_kwargs):
            return demo.FARMER, None

    app.state.authentication = MutableStateBypass()
    with TestClient(app) as client:
        response = client.get("/records/record:not-present")

    assert response.status_code == 401
    assert response.json()["detail"]["reasonCode"] == "AUTHORITY_DENIED"


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
