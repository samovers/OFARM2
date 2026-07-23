"""Focused tests for the maintained production OIDC verification boundary."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Event
from urllib.request import HTTPRedirectHandler, Request

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import kernel.auth_oidc as auth_oidc
from kernel.auth_oidc import (
    AuthenticationStartupError,
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


def _config(
    *,
    algorithms=("RS256",),
    jwks_lifespan_seconds=60,
    jwks_miss_refresh_seconds=5,
) -> ProductionOidcConfig:
    return ProductionOidcConfig(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=JWKS_URL,
        algorithms=algorithms,
        jwks_lifespan_seconds=jwks_lifespan_seconds,
        jwks_miss_refresh_seconds=jwks_miss_refresh_seconds,
    )


def _verifier(
    public_key,
    *,
    client=None,
    algorithms=("RS256",),
    clock=None,
    jwks_lifespan_seconds=60,
    jwks_miss_refresh_seconds=5,
) -> ProductionOidcVerifier:
    selected = client or _JwksClient(
        [_SigningKey("key-1", "RS256", public_key)]
    )
    return ProductionOidcVerifier.for_test(
        _config(
            algorithms=algorithms,
            jwks_lifespan_seconds=jwks_lifespan_seconds,
            jwks_miss_refresh_seconds=jwks_miss_refresh_seconds,
        ),
        jwks_client=selected,
        clock=time.monotonic if clock is None else clock,
    )


def _token(
    private_key,
    *,
    algorithm="RS256",
    key_id="key-1",
    **claims,
) -> str:
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
    assert verifier._jwks_client.refreshes == [True]


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


def test_production_verifier_accepts_a_new_key_id_after_jwks_rotation(rsa_keys):
    private_key, old_public_key = rsa_keys
    client = _JwksClient(
        [_SigningKey("key-1", "RS256", old_public_key)]
    )
    verifier = _verifier(old_public_key, client=client)
    verifier.initialize()
    assert verifier.verify_identity(_token(private_key)).subject == "subject-01"

    new_private_key = rsa.generate_private_key(
        public_exponent=65_537,
        key_size=2_048,
    )
    client.keys.append(
        _SigningKey("key-2", "RS256", new_private_key.public_key())
    )
    rotated = _token(
        new_private_key,
        key_id="key-2",
        sub="subject-02",
    )

    assert verifier.verify_identity(rotated).subject == "subject-02"


def test_alg_less_rsa_jwk_supports_configured_ps256(rsa_keys):
    private_key, public_key = rsa_keys
    jwk_data = jwt.algorithms.RSAAlgorithm.to_jwk(
        public_key,
        as_dict=True,
    )
    jwk_data.update({"kid": "key-ps256", "use": "sig"})
    assert "alg" not in jwk_data
    alg_less_key = jwt.PyJWK.from_dict(jwk_data)
    assert alg_less_key.algorithm_name == "RS256"
    verifier = _verifier(
        public_key,
        client=_JwksClient([alg_less_key]),
        algorithms=("PS256",),
    )
    verifier.initialize()

    token = _token(
        private_key,
        key_id="key-ps256",
        algorithm="PS256",
        sub="subject-ps256",
    )
    assert verifier.verify_identity(token).subject == "subject-ps256"


def test_unknown_key_ids_share_one_bounded_jwks_miss_refresh(rsa_keys):
    private_key, public_key = rsa_keys
    now = [1_000.0]
    client = _JwksClient([_SigningKey("key-1", "RS256", public_key)])
    verifier = _verifier(
        public_key,
        client=client,
        clock=lambda: now[0],
        jwks_miss_refresh_seconds=5,
    )
    verifier.initialize()

    for index in range(10):
        with pytest.raises(OidcError) as raised:
            verifier.verify_identity(
                _token(private_key, key_id=f"attacker-key-{index}")
            )
        assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL
    assert client.refreshes == [True, True]

    now[0] += 5
    with pytest.raises(OidcError):
        verifier.verify_identity(
            _token(private_key, key_id="next-window")
        )
    assert client.refreshes == [True, True, True]


def test_failed_jwks_miss_refresh_keeps_unknown_keys_invalid_and_bounded(
    rsa_keys,
):
    private_key, public_key = rsa_keys
    client = _JwksClient([_SigningKey("key-1", "RS256", public_key)])
    verifier = _verifier(
        public_key,
        client=client,
        clock=lambda: 1_000.0,
    )
    verifier.initialize()
    client.unavailable = True

    for key_id in ("attacker-key-1", "attacker-key-2"):
        with pytest.raises(OidcError) as raised:
            verifier.verify_identity(_token(private_key, key_id=key_id))
        assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL
    assert client.refreshes == [True, True]


def test_jwks_miss_refresh_does_not_lock_current_key_verification(rsa_keys):
    private_key, public_key = rsa_keys
    refresh_started = Event()
    release_refresh = Event()

    class BlockingRefreshClient(_JwksClient):
        def get_jwk_set(self, *, refresh: bool):
            if self.refreshes:
                refresh_started.set()
                if not release_refresh.wait(timeout=2):
                    raise RuntimeError("test refresh was not released")
            return super().get_jwk_set(refresh=refresh)

    client = BlockingRefreshClient(
        [_SigningKey("key-1", "RS256", public_key)]
    )
    verifier = _verifier(public_key, client=client)
    verifier.initialize()
    valid = _token(private_key)
    unknown = _token(private_key, key_id="attacker-key")

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


def test_slow_unknown_key_refresh_is_non_blocking_and_completion_bounded(
    rsa_keys,
):
    private_key, public_key = rsa_keys
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

    client = SlowRefreshClient(
        [_SigningKey("key-1", "RS256", public_key)]
    )
    verifier = _verifier(
        public_key,
        client=client,
        clock=lambda: now[0],
        jwks_miss_refresh_seconds=1,
    )
    verifier.initialize()
    valid = _token(private_key)

    with ThreadPoolExecutor(max_workers=24) as executor:
        first_miss = executor.submit(
            verifier.verify_identity,
            _token(private_key, key_id="attacker-key-first"),
        )
        assert refresh_started.wait(timeout=1)
        concurrent_misses = [
            executor.submit(
                verifier.verify_identity,
                _token(private_key, key_id=f"attacker-key-{index}"),
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
            _token(private_key, key_id="attacker-key-after-completion")
        )
    assert client.refreshes == [True, True]


def test_removed_used_key_expires_with_the_bounded_jwks_generation(rsa_keys):
    private_key, public_key = rsa_keys
    backup_private_key = rsa.generate_private_key(
        public_exponent=65_537,
        key_size=2_048,
    )
    now = [1_000.0]
    client = _JwksClient(
        [
            _SigningKey("key-1", "RS256", public_key),
            _SigningKey(
                "key-2",
                "RS256",
                backup_private_key.public_key(),
            ),
        ]
    )
    verifier = _verifier(
        public_key,
        client=client,
        clock=lambda: now[0],
        jwks_lifespan_seconds=60,
    )
    token = _token(private_key)
    verifier.initialize()
    assert verifier.verify_identity(token).subject == "subject-01"

    client.keys = [
        _SigningKey(
            "key-2",
            "RS256",
            backup_private_key.public_key(),
        )
    ]
    assert verifier.verify_identity(token).subject == "subject-01"
    now[0] += 60
    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(token)
    assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL
    assert client.refreshes == [True, True]


def test_same_kid_key_replacement_takes_effect_after_jwks_lifespan(rsa_keys):
    old_private_key, old_public_key = rsa_keys
    new_private_key = rsa.generate_private_key(
        public_exponent=65_537,
        key_size=2_048,
    )
    now = [2_000.0]
    client = _JwksClient(
        [_SigningKey("key-1", "RS256", old_public_key)]
    )
    verifier = _verifier(
        old_public_key,
        client=client,
        clock=lambda: now[0],
        jwks_lifespan_seconds=60,
    )
    old_token = _token(old_private_key)
    new_token = _token(new_private_key, sub="subject-02")
    verifier.initialize()
    assert verifier.verify_identity(old_token).subject == "subject-01"

    client.keys = [
        _SigningKey("key-1", "RS256", new_private_key.public_key())
    ]
    now[0] += 60
    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(old_token)
    assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL
    assert verifier.verify_identity(new_token).subject == "subject-02"


def test_duplicate_or_encryption_only_jwks_refuses_startup(rsa_keys):
    _, public_key = rsa_keys
    duplicate = _JwksClient(
        [
            _SigningKey("key-1", "RS256", public_key),
            _SigningKey("key-1", "RS256", public_key),
        ]
    )
    with pytest.raises(
        AuthenticationStartupError,
        match="JWKS initialization failed",
    ):
        _verifier(public_key, client=duplicate).initialize()

    encryption_only = _JwksClient(
        [
            _SigningKey(
                "key-1",
                "RS256",
                public_key,
                public_key_use="enc",
            )
        ]
    )
    with pytest.raises(
        AuthenticationStartupError,
        match="JWKS initialization failed",
    ):
        _verifier(public_key, client=encryption_only).initialize()


def test_duplicate_signing_identity_after_refresh_is_verifier_unavailable(
    rsa_keys,
):
    private_key, public_key = rsa_keys
    now = [3_000.0]
    client = _JwksClient([_SigningKey("key-1", "RS256", public_key)])
    verifier = _verifier(
        public_key,
        client=client,
        clock=lambda: now[0],
        jwks_lifespan_seconds=60,
    )
    verifier.initialize()
    client.keys.append(_SigningKey("key-1", "RS256", public_key))
    now[0] += 60
    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(_token(private_key))
    assert raised.value.outcome is PreBindingOutcome.VERIFIER_UNAVAILABLE


def test_provider_outage_after_jwks_expiry_is_verifier_unavailable(rsa_keys):
    private_key, public_key = rsa_keys
    now = [4_000.0]
    client = _JwksClient([_SigningKey("key-1", "RS256", public_key)])
    verifier = _verifier(
        public_key,
        client=client,
        clock=lambda: now[0],
        jwks_lifespan_seconds=60,
    )
    verifier.initialize()
    client.unavailable = True
    now[0] += 60
    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(_token(private_key))
    assert raised.value.outcome is PreBindingOutcome.VERIFIER_UNAVAILABLE
    assert "provider detail" not in str(raised.value)


def test_slow_failed_expiry_refresh_is_non_blocking_and_retry_bounded(
    rsa_keys,
):
    private_key, public_key = rsa_keys
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
        [_SigningKey("key-1", "RS256", public_key)]
    )
    verifier = _verifier(
        public_key,
        client=client,
        clock=lambda: now[0],
        jwks_lifespan_seconds=60,
    )
    verifier.initialize()
    token = _token(private_key)
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
def test_exact_identity_policy_refuses_noncanonical_values(rsa_keys, claims):
    private_key, public_key = rsa_keys
    verifier = _verifier(public_key)
    verifier.initialize()
    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(_token(private_key, **claims))
    assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL
    assert "subject-01" not in str(raised.value)


def test_key_id_and_time_failures_are_closed(rsa_keys):
    private_key, public_key = rsa_keys
    verifier = _verifier(public_key)
    verifier.initialize()
    now = int(time.time())
    base = {
        "iss": ISSUER,
        "sub": "subject-01",
        "aud": AUDIENCE,
        "exp": now + 60,
    }
    missing_key_id = jwt.encode(base, private_key, algorithm="RS256")
    wrong_key_id = jwt.encode(
        base,
        private_key,
        algorithm="RS256",
        headers={"kid": "rotated-away"},
    )
    expired = _token(private_key, exp=now - 1)
    future = _token(private_key, nbf=now + 300)

    for token in (missing_key_id, wrong_key_id, expired, future):
        with pytest.raises(OidcError):
            verifier.verify_identity(token)


def test_oversized_numeric_date_refuses_before_key_selection(rsa_keys):
    private_key, public_key = rsa_keys
    verifier = _verifier(public_key)
    verifier.initialize()
    with pytest.raises(OidcError) as raised:
        verifier.verify_identity(_token(private_key, exp=10**400))
    assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL
    assert verifier._jwks_client.refreshes == [True]
