"""Security tests for #172's explicit modes and maintained OIDC verifier."""
from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from kernel import config
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


ISSUER = "https://issuer.example.test/tenant"
AUDIENCE = "ofarm-production"
JWKS_URL = "https://issuer.example.test/tenant/jwks"


@dataclass
class _SigningKey:
    key_id: str
    algorithm_name: str
    key: object


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


def _production_verifier(rsa_keys, *, client=None):
    _, public = rsa_keys
    selected = client or _JwksClient([_SigningKey("key-1", "RS256", public)])
    return ProductionOidcVerifier(
        ProductionOidcConfig(
            issuer=ISSUER,
            audience=AUDIENCE,
            jwks_url=JWKS_URL,
            algorithms=("RS256",),
        ),
        jwks_client=selected,
    )


def _token(rsa_keys, **claims):
    private, _ = rsa_keys
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
    return jwt.encode(payload, private, algorithm="RS256", headers={"kid": "key-1"})


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
    runtime = AuthenticationRuntime.production(
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


def test_maintained_verifier_accepts_exact_identity_and_initializes_fresh_jwks(rsa_keys):
    verifier = _production_verifier(rsa_keys)
    verifier.initialize()
    identity = verifier.verify_identity(_token(rsa_keys))
    assert identity.issuer == ISSUER
    assert identity.subject == "subject-01"
    assert identity.equality_policy == "OIDC_EXACT_UTF8_V1"
    assert verifier._jwks_client.refreshes == [True]


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


def test_production_runtime_uses_binding_not_subject_as_party(rsa_keys):
    resolver = _Resolver()
    runtime = AuthenticationRuntime.production(_production_verifier(rsa_keys), resolver)
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
