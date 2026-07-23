"""Focused tests for the maintained production OIDC verification boundary."""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from kernel.auth_oidc import (
    AuthenticationStartupError,
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
    public_key_use: str | None = None
    _jwk_data: dict[str, object] | None = None


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


@pytest.fixture(scope="module")
def rsa_keys():
    private = rsa.generate_private_key(public_exponent=65_537, key_size=2_048)
    return private, private.public_key()


def _config(*, algorithms=("RS256",)) -> ProductionOidcConfig:
    return ProductionOidcConfig(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=JWKS_URL,
        algorithms=algorithms,
        jwks_lifespan_seconds=60,
        jwks_miss_refresh_seconds=5,
    )


def _verifier(
    public_key,
    *,
    client=None,
    algorithms=("RS256",),
) -> ProductionOidcVerifier:
    selected = client or _JwksClient(
        [_SigningKey("key-1", "RS256", public_key)]
    )
    return ProductionOidcVerifier.for_test(
        _config(algorithms=algorithms),
        jwks_client=selected,
        clock=time.monotonic,
    )


def _token(private_key, *, algorithm="RS256", key_id="key-1") -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": ISSUER,
            "sub": "subject-01",
            "aud": AUDIENCE,
            "iat": now,
            "nbf": now - 1,
            "exp": now + 60,
        },
        private_key,
        algorithm=algorithm,
        headers={"kid": key_id},
    )


def test_production_verifier_accepts_one_exact_asymmetric_identity(rsa_keys):
    private_key, public_key = rsa_keys
    verifier = _verifier(public_key)

    verifier.initialize()
    identity = verifier.verify_identity(_token(private_key))

    assert identity.issuer == ISSUER
    assert identity.subject == "subject-01"
    assert identity.equality_policy == "OIDC_EXACT_UTF8_V1"


@pytest.mark.parametrize(("algorithm", "declared"), (
    ("RS256", True),
    ("RS256", False),
    ("PS256", True),
    ("PS256", False),
))
def test_undersized_rsa_jwks_is_rejected(
    algorithm: str,
    declared: bool,
) -> None:
    public_key = rsa.generate_private_key(
        public_exponent=65_537,
        key_size=1_024,
    ).public_key()
    jwk_data: dict[str, object] = {"kty": "RSA"}
    if declared:
        jwk_data["alg"] = algorithm
    key = _SigningKey(
        "key-1",
        algorithm if declared else "RS256",
        public_key,
        _jwk_data=jwk_data,
    )
    verifier = _verifier(
        public_key,
        client=_JwksClient([key]),
        algorithms=(algorithm,),
    )

    with pytest.raises(AuthenticationStartupError, match="JWKS initialization failed"):
        verifier.initialize()


def test_provider_outage_is_a_safe_unavailable_outcome(rsa_keys):
    _, public_key = rsa_keys
    verifier = _verifier(
        public_key,
        client=_JwksClient([], unavailable=True),
    )

    with pytest.raises(AuthenticationStartupError, match="JWKS initialization failed"):
        verifier.initialize()
