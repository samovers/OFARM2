"""Focused tests for the maintained production OIDC verification boundary."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from email.message import Message
from threading import Event
from urllib.request import HTTPRedirectHandler, Request

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa

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


class _StreamingResponse:
    def __init__(
        self,
        body: bytes,
        *,
        chunk_bytes: int = auth_oidc._JWKS_READ_CHUNK_BYTES,
        content_lengths: tuple[str, ...] = (),
        advance_clock=None,
    ):
        self._body = body
        self._offset = 0
        self._chunk_bytes = chunk_bytes
        self._advance_clock = advance_clock
        self.closed = False
        self.read_sizes: list[int] = []
        self.headers = Message()
        for value in content_lengths:
            self.headers.add_header("Content-Length", value)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False

    def geturl(self) -> str:
        return JWKS_URL

    def read1(self, size: int) -> bytes:
        self.read_sizes.append(size)
        if self._advance_clock is not None:
            self._advance_clock()
        if self.closed or self._offset >= len(self._body):
            return b""
        end = min(
            len(self._body),
            self._offset + size,
            self._offset + self._chunk_bytes,
        )
        chunk = self._body[self._offset:end]
        self._offset = end
        return chunk

    def read(self, size: int) -> bytes:
        raise AssertionError(f"bounded transport must use read1(), not read({size})")

    def close(self) -> None:
        self.closed = True


class _StaticOpener:
    def __init__(self, response: _StreamingResponse, *, on_open=None):
        self.response = response
        self._on_open = on_open

    def open(self, request: Request, *, timeout: int):
        assert request.full_url == JWKS_URL
        if self._on_open is not None:
            self._on_open()
        return self.response


@pytest.fixture(scope="module")
def rsa_keys():
    private = rsa.generate_private_key(public_exponent=65_537, key_size=2_048)
    return private, private.public_key()


def _config(
    *,
    algorithms=("RS256",),
    jwks_url=JWKS_URL,
    jwks_lifespan_seconds=60,
    jwks_miss_refresh_seconds=5,
    timeout_seconds=5,
) -> ProductionOidcConfig:
    return ProductionOidcConfig(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=jwks_url,
        algorithms=algorithms,
        jwks_lifespan_seconds=jwks_lifespan_seconds,
        jwks_miss_refresh_seconds=jwks_miss_refresh_seconds,
        timeout_seconds=timeout_seconds,
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


def _public_rsa_jwks_bytes(public_key: rsa.RSAPublicKey) -> bytes:
    jwk_data = jwt.algorithms.RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk_data.update({"kid": "key-1", "alg": "RS256", "use": "sig"})
    return json.dumps(
        {"keys": [jwk_data]},
        separators=(",", ":"),
    ).encode("utf-8")


def _transport_client(
    response: _StreamingResponse,
    *,
    clock=time.monotonic,
    timeout_seconds=5,
    on_open=None,
):
    client = auth_oidc._ProductionJwksClient(
        jwt,
        uri=JWKS_URL,
        timeout_seconds=timeout_seconds,
        monotonic_clock=clock,
    )
    client._opener = _StaticOpener(response, on_open=on_open)
    return client


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


def test_malformed_ipv6_jwks_url_is_a_startup_error() -> None:
    with pytest.raises(
        AuthenticationStartupError,
        match="JWKS URL must be an HTTPS URL",
    ):
        _config(jwks_url="https://[invalid").validate()


def test_jwks_transport_accepts_a_valid_chunked_document(rsa_keys) -> None:
    _, public_key = rsa_keys
    response = _StreamingResponse(
        _public_rsa_jwks_bytes(public_key),
        chunk_bytes=7,
    )

    jwk_set = _transport_client(response).get_jwk_set(refresh=True)

    assert len(jwk_set.keys) == 1
    assert len(response.read_sizes) > 2
    assert max(response.read_sizes) <= auth_oidc._JWKS_READ_CHUNK_BYTES


@pytest.mark.parametrize("declared", (False, True))
def test_jwks_transport_rejects_oversized_response_bytes(declared: bool) -> None:
    body = b"x" * (auth_oidc._MAX_JWKS_BYTES + 1)
    content_lengths = (str(len(body)),) if declared else ()
    response = _StreamingResponse(body, content_lengths=content_lengths)

    with pytest.raises(
        auth_oidc._JwksProviderStateError,
        match="byte bound",
    ):
        _transport_client(response).get_jwk_set(refresh=True)

    if declared:
        assert response.read_sizes == []
    else:
        assert len(response.read_sizes) > 1


def test_jwks_transport_enforces_one_monotonic_end_to_end_deadline() -> None:
    now = [100.0]

    def advance_open() -> None:
        now[0] += 3.0

    def drip_one_second() -> None:
        now[0] += 1.0

    response = _StreamingResponse(
        b'{"keys":[]}',
        chunk_bytes=1,
        advance_clock=drip_one_second,
    )
    client = _transport_client(
        response,
        clock=lambda: now[0],
        timeout_seconds=5,
        on_open=advance_open,
    )

    with pytest.raises(
        auth_oidc._JwksProviderStateError,
        match="deadline exceeded",
    ):
        client.get_jwk_set(refresh=True)

    assert len(response.read_sizes) <= 2


@pytest.mark.parametrize(
    "raw_document",
    (
        b'{"keys":[],"keys":[]}',
        b'{"keys":[{"kty":"RSA","kid":"one","kid":"two"}]}',
        b'{"keys":[],"extension":NaN}',
        b'{"keys":[],"extension":Infinity}',
    ),
)
def test_jwks_transport_rejects_non_strict_json(raw_document: bytes) -> None:
    response = _StreamingResponse(raw_document)

    with pytest.raises(
        auth_oidc._JwksProviderStateError,
        match="JSON is invalid",
    ):
        _transport_client(response).get_jwk_set(refresh=True)


def test_jwks_key_count_is_bounded_before_materialization() -> None:
    document = {
        "keys": [
            {"kty": "unsupported", "kid": f"key-{index}"}
            for index in range(auth_oidc._MAX_JWKS_KEYS + 1)
        ]
    }
    response = _StreamingResponse(
        json.dumps(document, separators=(",", ":")).encode("utf-8")
    )

    with pytest.raises(
        auth_oidc._JwksProviderStateError,
        match="key count",
    ):
        _transport_client(response).get_jwk_set(refresh=True)


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


@pytest.mark.parametrize("key_type", ("RSA", "EC", "OKP"))
def test_private_jwk_material_is_rejected_at_startup(key_type: str) -> None:
    if key_type == "RSA":
        private_key = rsa.generate_private_key(
            public_exponent=65_537,
            key_size=2_048,
        )
        algorithm_adapter = jwt.algorithms.RSAAlgorithm
        algorithm = "RS256"
    elif key_type == "EC":
        private_key = ec.generate_private_key(ec.SECP256R1())
        algorithm_adapter = jwt.algorithms.ECAlgorithm
        algorithm = "ES256"
    else:
        private_key = ed25519.Ed25519PrivateKey.generate()
        algorithm_adapter = jwt.algorithms.OKPAlgorithm
        algorithm = "EdDSA"
    private_jwk = algorithm_adapter.to_jwk(private_key, as_dict=True)
    private_jwk.update({"kid": "private-key", "alg": algorithm, "use": "sig"})
    parsed_set = jwt.PyJWKSet.from_dict({"keys": [private_jwk]})
    client = _JwksClient(list(parsed_set.keys))
    verifier = _verifier(
        object(),
        client=client,
        algorithms=(algorithm,),
    )

    with pytest.raises(AuthenticationStartupError, match="JWKS initialization failed"):
        verifier.initialize()


@pytest.mark.parametrize(
    ("jwk_data", "verifier_key", "algorithm"),
    (
        (
            {"kty": "RSA", "alg": "RS256"},
            ec.generate_private_key(ec.SECP256R1()).public_key(),
            "RS256",
        ),
        (
            {"kty": "EC", "crv": "P-256", "alg": "ES256"},
            ec.generate_private_key(ec.SECP384R1()).public_key(),
            "ES256",
        ),
        (
            {"kty": "OKP", "crv": "Ed25519", "alg": "EdDSA"},
            rsa.generate_private_key(
                public_exponent=65_537,
                key_size=2_048,
            ).public_key(),
            "EdDSA",
        ),
    ),
)
def test_jwk_type_or_curve_mismatch_is_rejected_at_startup(
    jwk_data: dict[str, object],
    verifier_key: object,
    algorithm: str,
) -> None:
    key = _SigningKey(
        "key-1",
        algorithm,
        verifier_key,
        _jwk_data=jwk_data,
    )
    verifier = _verifier(
        object(),
        client=_JwksClient([key]),
        algorithms=(algorithm,),
    )

    with pytest.raises(AuthenticationStartupError, match="JWKS initialization failed"):
        verifier.initialize()


def test_generated_jwks_signing_entry_count_is_bounded(rsa_keys) -> None:
    _, public_key = rsa_keys
    algorithms = ("RS256", "RS384", "RS512", "PS256", "PS384", "PS512")
    entries_per_key = len(algorithms)
    key_count = auth_oidc._MAX_JWKS_SIGNING_ENTRIES // entries_per_key + 1
    keys = [
        _SigningKey(
            f"key-{index}",
            "RS256",
            public_key,
            _jwk_data={"kty": "RSA"},
        )
        for index in range(key_count)
    ]
    verifier = _verifier(
        public_key,
        client=_JwksClient(keys),
        algorithms=algorithms,
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


def test_absent_authorization_is_no_credential() -> None:
    with pytest.raises(OidcError) as raised:
        auth_oidc._bearer_token(None)

    assert raised.value.outcome is PreBindingOutcome.NO_CREDENTIAL


@pytest.mark.parametrize(
    "authorization",
    (
        "",
        "Basic dXNlcjpwYXNz",
        "Bearer",
        "Bearer ",
        "Bearer  token",
        "Bearer\ttoken",
        object(),
    ),
)
def test_present_malformed_authorization_is_invalid_credential(
    authorization: object,
) -> None:
    with pytest.raises(OidcError) as raised:
        auth_oidc._bearer_token(authorization)

    assert raised.value.outcome is PreBindingOutcome.INVALID_CREDENTIAL


def test_bearer_scheme_is_case_insensitive_but_shape_is_exact() -> None:
    assert auth_oidc._bearer_token("bEaReR token") == "token"
