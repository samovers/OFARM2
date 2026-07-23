"""Focused tests for the maintained production OIDC verification boundary."""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.request import HTTPRedirectHandler, Request

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import kernel.auth_oidc as auth_oidc
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


class _RedirectedResponse:
    def __init__(self, final_url: str):
        self.final_url = final_url
        self.body_read = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self) -> str:
        return self.final_url

    def read(self, *args):
        self.body_read = True
        raise AssertionError("a redirected JWKS body must not be read")


class _RedirectingOpener:
    def __init__(self, final_url: str):
        self.response = _RedirectedResponse(final_url)

    def open(self, request: Request, *, timeout: int):
        assert request.full_url == JWKS_URL
        assert timeout == 5
        return self.response


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


def test_production_jwks_transport_disables_every_redirect() -> None:
    opener = auth_oidc._build_no_redirect_jwks_opener()
    redirect_handlers = [
        handler
        for handler in opener.handlers
        if isinstance(handler, HTTPRedirectHandler)
    ]

    assert len(redirect_handlers) == 1
    assert type(redirect_handlers[0]) is auth_oidc._RejectJwksRedirectHandler
    assert redirect_handlers[0].redirect_request(
        Request(JWKS_URL),
        object(),
        302,
        "Found",
        {},
        "https://issuer.example.test/tenant/new-jwks",
    ) is None


@pytest.mark.parametrize(
    "redirect_target",
    (
        "http://issuer.example.test/tenant/jwks",
        "ftp://issuer.example.test/tenant/jwks",
    ),
)
def test_production_jwks_refuses_downgraded_final_target(
    monkeypatch: pytest.MonkeyPatch,
    redirect_target: str,
) -> None:
    opener = _RedirectingOpener(redirect_target)
    monkeypatch.setattr(
        auth_oidc,
        "_build_no_redirect_jwks_opener",
        lambda: opener,
    )
    verifier = ProductionOidcVerifier(_config())

    with pytest.raises(AuthenticationStartupError, match="JWKS initialization failed"):
        verifier.initialize()

    assert opener.response.body_read is False


@pytest.mark.parametrize(
    ("key_type", "curve", "declared_algorithm"),
    (
        ("EC", "P-256", "ES384"),
        ("EC", "P-384", "ES256"),
        ("OKP", "X25519", "EdDSA"),
        ("OKP", "Ed448", "EdDSA"),
    ),
)
def test_incompatible_declared_jwk_algorithm_is_rejected_at_startup(
    key_type: str,
    curve: str,
    declared_algorithm: str,
) -> None:
    key = _SigningKey(
        "key-1",
        declared_algorithm,
        object(),
        _jwk_data={
            "kty": key_type,
            "crv": curve,
            "alg": declared_algorithm,
        },
    )
    verifier = _verifier(
        object(),
        client=_JwksClient([key]),
        algorithms=(declared_algorithm,),
    )

    with pytest.raises(AuthenticationStartupError, match="JWKS initialization failed"):
        verifier.initialize()
