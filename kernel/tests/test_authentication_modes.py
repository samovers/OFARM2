"""Security tests for #172's explicit modes and maintained OIDC verifier."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Event

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from kernel import config
from kernel.api import create_app
from kernel.auth_oidc import (
    AuthenticationMode,
    AuthenticationRuntime,
    AuthenticationStartupError,
    OidcConfig,
    OidcError,
    PreBindingOutcome,
    ProductionOidcConfig,
    ProductionOidcVerifier,
)
from kernel.principal_binding import PostgreSQLPrincipalBindingResolver


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


@pytest.fixture(scope="module")
def rsa_keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


def _production_verifier(
    rsa_keys,
    *,
    client=None,
    clock=None,
    jwks_lifespan_seconds=300,
    jwks_miss_refresh_seconds=5,
):
    _, public = rsa_keys
    selected = client or _JwksClient([_SigningKey("key-1", "RS256", public)])
    return ProductionOidcVerifier(
        ProductionOidcConfig(
            issuer=ISSUER,
            audience=AUDIENCE,
            jwks_url=JWKS_URL,
            algorithms=("RS256",),
            jwks_lifespan_seconds=jwks_lifespan_seconds,
            jwks_miss_refresh_seconds=jwks_miss_refresh_seconds,
        ),
        jwks_client=selected,
        clock=clock,
    )


def _signed_token(private, *, key_id="key-1", **claims):
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
        algorithm="RS256",
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
        AuthenticationRuntime(
            AuthenticationMode.PRODUCTION,
            verifier=_production_verifier(rsa_keys),
        ).initialize()


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
    verifier = _production_verifier(rsa_keys)
    with pytest.raises(AuthenticationStartupError, match="sealed PostgreSQL"):
        AuthenticationRuntime.production(verifier, _Resolver())
    with pytest.raises(AuthenticationStartupError, match="sealed PostgreSQL"):
        AuthenticationRuntime(
            AuthenticationMode.PRODUCTION,
            verifier=verifier,
            principal_binding_resolver=_Resolver(),
        ).initialize()
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


def test_legacy_oidc_argument_rejects_a_production_verifier(rsa_keys):
    production = _production_verifier(rsa_keys)
    with pytest.raises(AuthenticationStartupError, match="exact OidcConfig or None"):
        create_app(oidc=production)
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


def test_safe_failure_outcome_does_not_expose_exception_detail():
    error = OidcError(
        PreBindingOutcome.VERIFIER_UNAVAILABLE,
        internal_detail="token=secret issuer=private stack=provider",
    )
    assert str(error) == "authentication refused (VERIFIER_UNAVAILABLE)"
    assert "secret" not in str(error)
