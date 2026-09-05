"""Focused invariants and reproduced bypasses for production OIDC."""
from __future__ import annotations

import base64
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Barrier, Condition, Event, Lock

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from jwt.algorithms import RSAAlgorithm

from deployment.postgresql.tenant_contract import OIDC_ISSUER_EQUALITY_POLICY
from kernel.authentication import (
    AuthenticationError,
    AuthenticationOutcome,
    AuthenticationStartupError,
)
from kernel.production_oidc import ProductionOidcConfig, ProductionOidcVerifier


ISSUER = "https://issuer.example.test/tenant"
AUDIENCE = "ofarm2-api"
JWKS_URL = "https://issuer.example.test/tenant/jwks"


@dataclass
class _Clock:
    value: float = 0

    def __call__(self) -> float:
        return self.value


class _ObservedLock:
    def __init__(self):
        self._mutex = Lock()
        self._condition = Condition()
        self._attempts = 0

    def __enter__(self):
        with self._condition:
            self._attempts += 1
            self._condition.notify_all()
        self._mutex.acquire()
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        self._mutex.release()

    def wait_for_attempts(self, count: int, timeout: float) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: self._attempts >= count,
                timeout=timeout,
            )


class _BytesStream(httpx.SyncByteStream):
    def __init__(self, body: bytes):
        self.body = body

    def __iter__(self):
        yield self.body[:32]
        yield self.body[32:]


def _key(kid: str, *, size: int = 2048):
    private = rsa.generate_private_key(public_exponent=65537, key_size=size)
    jwk = json.loads(RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update({"kid": kid, "alg": "RS256", "use": "sig", "key_ops": ["verify"]})
    return private, jwk


def _jwks(*keys: dict, **members: object) -> bytes:
    return json.dumps(
        {"keys": list(keys), **members},
        separators=(",", ":"),
    ).encode()


def _token(private, kid: str, subject: str = "subject:Exact-01", **claims):
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "sub": subject,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 300,
        **claims,
    }
    return jwt.encode(
        payload,
        private,
        algorithm="RS256",
        headers={"kid": kid, "typ": "JWT"},
    )


def _client(handler) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )


def _config(**changes) -> ProductionOidcConfig:
    values = {
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "jwks_url": JWKS_URL,
        "cache_ttl_seconds": 10,
        "refresh_cooldown_seconds": 5,
    }
    values.update(changes)
    return ProductionOidcConfig(**values)


def _initialized_verifier(jwk: dict, **config_changes):
    calls = []

    def handler(_request):
        calls.append(1)
        return httpx.Response(200, content=_jwks(jwk))

    client = _client(handler)
    verifier = ProductionOidcVerifier(_config(**config_changes), client)
    verifier.initialize()
    return verifier, client, calls


def _raw_signed(private, header: bytes, claims: bytes) -> str:
    def encode(value):
        return base64.urlsafe_b64encode(value).rstrip(b"=")

    signing_input = encode(header) + b"." + encode(claims)
    signature = private.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return (
        signing_input + b"." + encode(signature)
    ).decode("ascii")


def test_initialize_and_verify_preserve_exact_identity_bytes():
    private, jwk = _key("kid-1")
    client = _client(lambda _request: httpx.Response(200, content=_jwks(jwk)))
    verifier = ProductionOidcVerifier(_config(), client)

    verifier.initialize()
    identity = verifier.verify(_token(private, "kid-1"))

    assert identity.equality_policy == OIDC_ISSUER_EQUALITY_POLICY
    assert identity.issuer == ISSUER
    assert identity.subject == "subject:Exact-01"
    client.close()


def test_authentication_outcomes_are_the_exact_audit_safe_failures():
    assert tuple(AuthenticationOutcome) == (
        AuthenticationOutcome.NO_CREDENTIAL,
        AuthenticationOutcome.CREDENTIAL_MALFORMED,
        AuthenticationOutcome.VERIFICATION_REFUSED,
        AuthenticationOutcome.VERIFIER_UNAVAILABLE,
    )


@pytest.mark.parametrize(
    ("credential", "expected"),
    [
        (None, AuthenticationOutcome.NO_CREDENTIAL),
        (0, AuthenticationOutcome.CREDENTIAL_MALFORMED),
        ("", AuthenticationOutcome.CREDENTIAL_MALFORMED),
        ("not-a-jws", AuthenticationOutcome.CREDENTIAL_MALFORMED),
        ("é", AuthenticationOutcome.CREDENTIAL_MALFORMED),
    ],
)
def test_missing_and_malformed_credentials_are_distinct(
    credential,
    expected,
):
    _private, jwk = _key("kid-entry")
    verifier, client, calls = _initialized_verifier(jwk)

    with pytest.raises(AuthenticationError) as raised:
        verifier.verify(credential)

    assert raised.value.outcome is expected
    assert calls == [1]
    client.close()


def test_signature_from_another_key_cannot_claim_a_known_kid():
    _trusted_private, trusted_jwk = _key("kid-trusted")
    attacker_private, _attacker_jwk = _key("kid-attacker")
    verifier, client, calls = _initialized_verifier(trusted_jwk)

    with pytest.raises(AuthenticationError) as raised:
        verifier.verify(_token(attacker_private, "kid-trusted"))

    assert raised.value.outcome is AuthenticationOutcome.VERIFICATION_REFUSED
    assert calls == [1]
    client.close()


def test_unsigned_alg_none_token_is_refused():
    _private, jwk = _key("kid-none")
    verifier, client, calls = _initialized_verifier(jwk)
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": ISSUER,
            "sub": "subject:unsigned",
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + 300,
        },
        key="",
        algorithm="none",
        headers={"kid": "kid-none", "typ": "JWT"},
    )

    with pytest.raises(AuthenticationError) as raised:
        verifier.verify(token)

    assert raised.value.outcome is AuthenticationOutcome.CREDENTIAL_MALFORMED
    assert calls == [1]
    client.close()


def test_not_before_claim_honors_only_the_configured_leeway():
    private, jwk = _key("kid-not-before")
    token = _token(private, "kid-not-before", nbf=int(time.time()) + 60)
    strict, strict_client, _ = _initialized_verifier(jwk)
    tolerant, tolerant_client, _ = _initialized_verifier(
        jwk,
        leeway_seconds=120,
    )

    with pytest.raises(AuthenticationError) as raised:
        strict.verify(token)

    assert raised.value.outcome is AuthenticationOutcome.VERIFICATION_REFUSED
    assert tolerant.verify(token).subject == "subject:Exact-01"
    strict_client.close()
    tolerant_client.close()


def test_verify_before_initialize_performs_no_network_io():
    private, _jwk = _key("kid-uninitialized")
    calls = []
    client = _client(lambda _request: calls.append(1))
    verifier = ProductionOidcVerifier(_config(), client)

    with pytest.raises(AuthenticationError) as raised:
        verifier.verify(_token(private, "kid-uninitialized"))

    assert raised.value.outcome is AuthenticationOutcome.VERIFIER_UNAVAILABLE
    assert calls == []
    client.close()


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "other-api"},
        {"aud": [AUDIENCE, "other-api"]},
        {"iss": "https://other.example.test"},
        {"exp": 0},
    ],
)
def test_verified_signature_does_not_bypass_claim_validation(claims):
    private, jwk = _key("kid-claims")
    client = _client(lambda _request: httpx.Response(200, content=_jwks(jwk)))
    verifier = ProductionOidcVerifier(_config(), client)
    verifier.initialize()

    with pytest.raises(AuthenticationError) as raised:
        verifier.verify(_token(private, "kid-claims", **claims))

    assert raised.value.outcome is AuthenticationOutcome.VERIFICATION_REFUSED
    client.close()


@pytest.mark.parametrize("subject", ["", "\n", "subjéct", "s" * 256])
def test_verified_subject_must_match_the_exact_transport_grammar(subject):
    private, jwk = _key("kid-subject")
    client = _client(lambda _request: httpx.Response(200, content=_jwks(jwk)))
    verifier = ProductionOidcVerifier(_config(), client)
    verifier.initialize()

    with pytest.raises(AuthenticationError) as raised:
        verifier.verify(_token(private, "kid-subject", subject))

    assert raised.value.outcome is AuthenticationOutcome.VERIFICATION_REFUSED
    client.close()


def test_token_size_bound_is_checked_before_key_lookup():
    private, jwk = _key("kid-token-size")
    calls = []

    def handler(_request):
        calls.append(1)
        return httpx.Response(200, content=_jwks(jwk))

    client = _client(handler)
    verifier = ProductionOidcVerifier(
        _config(max_token_bytes=64),
        client,
    )
    verifier.initialize()

    with pytest.raises(AuthenticationError) as raised:
        verifier.verify(_token(private, "kid-token-size"))

    assert raised.value.outcome is AuthenticationOutcome.CREDENTIAL_MALFORMED
    assert calls == [1]
    client.close()


def test_redirect_is_refused_and_never_followed():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            302,
            headers={"Location": "https://attacker.example/jwks"},
        )

    client = _client(handler)
    verifier = ProductionOidcVerifier(_config(), client)

    with pytest.raises(AuthenticationStartupError):
        verifier.initialize()

    assert calls == [JWKS_URL]
    client.close()


@pytest.mark.parametrize("with_length", [False, True])
def test_oversized_jwks_is_refused_while_streaming(with_length):
    body = b"x" * 65
    response = (
        httpx.Response(200, headers={"Content-Length": str(len(body))}, content=body)
        if with_length
        else httpx.Response(200, stream=_BytesStream(body))
    )
    client = _client(lambda _request: response)
    verifier = ProductionOidcVerifier(
        _config(max_jwks_bytes=64),
        client,
    )

    with pytest.raises(AuthenticationStartupError):
        verifier.initialize()
    client.close()


@pytest.mark.parametrize(
    "body",
    [
        b'{"keys":[],"keys":[]}',
        b'{"keys":[],"extra":true}',
        b'{"keys":[]}',
    ],
)
def test_jwks_shape_and_duplicate_members_are_refused(body):
    client = _client(lambda _request: httpx.Response(200, content=body))
    verifier = ProductionOidcVerifier(_config(), client)

    with pytest.raises(AuthenticationStartupError):
        verifier.initialize()
    client.close()


def test_private_jwk_material_is_refused():
    _private, jwk = _key("kid-private")
    jwk["d"] = "AQAB"
    client = _client(lambda _request: httpx.Response(200, content=_jwks(jwk)))

    with pytest.raises(AuthenticationStartupError):
        ProductionOidcVerifier(_config(), client).initialize()
    client.close()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda jwk: jwk.update(kty="EC"),
        lambda jwk: jwk.update(alg="RS512"),
        lambda jwk: jwk.update(use="enc"),
        lambda jwk: jwk.update(key_ops=["sign"]),
    ],
)
def test_incompatible_jwk_is_refused(mutation):
    _private, jwk = _key("kid-incompatible")
    mutation(jwk)
    client = _client(lambda _request: httpx.Response(200, content=_jwks(jwk)))

    with pytest.raises(AuthenticationStartupError):
        ProductionOidcVerifier(_config(), client).initialize()
    client.close()


def test_mixed_use_jwks_keeps_only_compatible_signing_keys():
    _private, signing = _key("kid-signing")
    _private, encryption = _key("kid-encryption")
    encryption.update(use="enc", alg="RSA-OAEP")
    client = _client(
        lambda _request: httpx.Response(
            200,
            content=_jwks(encryption, signing, extra="permitted"),
        )
    )
    verifier = ProductionOidcVerifier(_config(), client)

    verifier.initialize()

    client.close()


def test_private_material_refuses_the_whole_mixed_use_jwks():
    _private, signing = _key("kid-signing")
    _private, encryption = _key("kid-encryption")
    encryption.update(use="enc", alg="RSA-OAEP", d="AQAB")
    client = _client(
        lambda _request: httpx.Response(
            200,
            content=_jwks(encryption, signing),
        )
    )

    with pytest.raises(AuthenticationStartupError):
        ProductionOidcVerifier(_config(), client).initialize()
    client.close()


def test_rsa_keys_below_2048_bits_are_refused():
    _private, jwk = _key("kid-small", size=1024)
    client = _client(lambda _request: httpx.Response(200, content=_jwks(jwk)))

    with pytest.raises(AuthenticationStartupError):
        ProductionOidcVerifier(_config(), client).initialize()
    client.close()


def test_duplicate_kid_and_oversized_key_set_are_refused():
    _private, jwk = _key("kid-duplicate")
    duplicate_client = _client(
        lambda _request: httpx.Response(200, content=_jwks(jwk, jwk))
    )
    with pytest.raises(AuthenticationStartupError):
        ProductionOidcVerifier(_config(), duplicate_client).initialize()
    duplicate_client.close()

    oversized_client = _client(
        lambda _request: httpx.Response(200, content=_jwks(jwk, jwk))
    )
    with pytest.raises(AuthenticationStartupError):
        ProductionOidcVerifier(
            _config(max_jwks_keys=1),
            oversized_client,
        ).initialize()
    oversized_client.close()


@pytest.mark.parametrize(
    "header",
    [
        {"alg": "HS256", "kid": "kid-header", "typ": "JWT"},
        {"alg": "RS256", "typ": "JWT"},
        {"alg": "RS256", "kid": "kid-header", "crit": ["exp"]},
        {
            "alg": "RS256",
            "kid": "kid-header",
            "jku": "https://attacker.example/jwks",
        },
        {"alg": "RS256", "kid": "kid-header", "typ": "not-jwt"},
    ],
)
def test_malformed_or_non_rs256_jose_headers_are_refused(header):
    private, jwk = _key("kid-header")
    client = _client(lambda _request: httpx.Response(200, content=_jwks(jwk)))
    verifier = ProductionOidcVerifier(_config(), client)
    verifier.initialize()
    claims = json.dumps({
        "iss": ISSUER,
        "sub": "subject:header",
        "aud": AUDIENCE,
        "exp": int(time.time()) + 300,
    }).encode()
    token = _raw_signed(private, json.dumps(header).encode(), claims)

    with pytest.raises(AuthenticationError) as raised:
        verifier.verify(token)

    assert raised.value.outcome is AuthenticationOutcome.CREDENTIAL_MALFORMED
    client.close()


@pytest.mark.parametrize(
    ("header", "claims"),
    [
        (
            b'{"alg":"RS256","alg":"RS256","kid":"kid-duplicate-json"}',
            b'{"iss":"' + ISSUER.encode() + b'","sub":"subject:one","aud":"'
            + AUDIENCE.encode() + b'","exp":4102444800}',
        ),
        (
            b'{"alg":"RS256","kid":"kid-duplicate-json"}',
            b'{"iss":"' + ISSUER.encode()
            + b'","sub":"subject:one","sub":"subject:two","aud":"'
            + AUDIENCE.encode() + b'","exp":4102444800}',
        ),
    ],
)
def test_duplicate_token_json_members_are_refused(header, claims):
    private, jwk = _key("kid-duplicate-json")
    client = _client(lambda _request: httpx.Response(200, content=_jwks(jwk)))
    verifier = ProductionOidcVerifier(_config(), client)
    verifier.initialize()

    with pytest.raises(AuthenticationError) as raised:
        verifier.verify(_raw_signed(private, header, claims))
    assert raised.value.outcome is AuthenticationOutcome.CREDENTIAL_MALFORMED
    client.close()


def test_unknown_kid_refreshes_once_then_throttles_repeated_misses():
    private_1, jwk_1 = _key("kid-1")
    private_2, jwk_2 = _key("kid-2")
    calls = []
    generations = [_jwks(jwk_1), _jwks(jwk_1, jwk_2)]

    def handler(_request):
        calls.append(1)
        return httpx.Response(200, content=generations.pop(0))

    clock = _Clock()
    client = _client(handler)
    verifier = ProductionOidcVerifier(_config(), client, monotonic=clock)
    verifier.initialize()

    assert verifier.verify(_token(private_2, "kid-2")).subject
    with pytest.raises(AuthenticationError) as raised:
        verifier.verify(_token(private_1, "kid-missing"))

    assert raised.value.outcome is AuthenticationOutcome.VERIFICATION_REFUSED
    assert len(calls) == 2
    client.close()


def test_failed_expiry_refresh_cools_down_without_using_stale_keys():
    private, jwk = _key("kid-stale")
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, content=_jwks(jwk))
        raise httpx.ConnectError("offline", request=request)

    clock = _Clock()
    client = _client(handler)
    verifier = ProductionOidcVerifier(_config(), client, monotonic=clock)
    verifier.initialize()
    clock.value = 11

    for _attempt in range(2):
        with pytest.raises(AuthenticationError) as raised:
            verifier.verify(_token(private, "kid-stale"))
        assert raised.value.outcome is AuthenticationOutcome.VERIFIER_UNAVAILABLE

    assert calls == 2

    clock.value = 17
    with pytest.raises(AuthenticationError):
        verifier.verify(_token(private, "kid-stale"))
    assert calls == 3
    client.close()


def test_waiter_uses_post_lock_time_after_failed_refresh():
    private, jwk = _key("kid-retained")
    unknown_private, _unknown_jwk = _key("kid-refresh-trigger")
    clock = _Clock(90)
    refresh_started = Event()
    release_refresh = Event()
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, content=_jwks(jwk))
        if calls == 2:
            refresh_started.set()
            if not release_refresh.wait(timeout=5):
                raise AssertionError("refresh release was not signaled")
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(200, content=_jwks(jwk))

    client = _client(handler)
    verifier = ProductionOidcVerifier(_config(), client, monotonic=clock)
    verifier.initialize()
    observed_lock = _ObservedLock()
    verifier._lock = observed_lock
    clock.value = 99
    executor = ThreadPoolExecutor(max_workers=2)
    refresh = executor.submit(
        verifier.verify,
        _token(unknown_private, "kid-refresh-trigger"),
    )
    try:
        assert refresh_started.wait(timeout=5)
        waiter = executor.submit(verifier.verify, _token(private, "kid-retained"))
        assert observed_lock.wait_for_attempts(2, timeout=5)
        clock.value = 101
        release_refresh.set()

        with pytest.raises(AuthenticationError) as refresh_raised:
            refresh.result(timeout=5)
        assert refresh_raised.value.outcome is AuthenticationOutcome.VERIFIER_UNAVAILABLE
        with pytest.raises(AuthenticationError) as waiter_raised:
            waiter.result(timeout=5)
        assert waiter_raised.value.outcome is AuthenticationOutcome.VERIFIER_UNAVAILABLE
        assert calls == 2

        clock.value = 103
        with pytest.raises(AuthenticationError) as cooldown_raised:
            verifier.verify(_token(private, "kid-retained"))
        assert cooldown_raised.value.outcome is AuthenticationOutcome.VERIFIER_UNAVAILABLE
        assert calls == 2

        clock.value = 104
        assert verifier.verify(_token(private, "kid-retained")).subject
        assert calls == 3
    finally:
        release_refresh.set()
        executor.shutdown(wait=True, cancel_futures=True)
        client.close()


def test_waiters_use_successful_replacement_generation():
    old_private, old_jwk = _key("kid-old")
    new_private, new_jwk = _key("kid-new")
    clock = _Clock(90)
    refresh_started = Event()
    release_refresh = Event()
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, content=_jwks(old_jwk))
        refresh_started.set()
        if not release_refresh.wait(timeout=5):
            raise AssertionError("refresh release was not signaled")
        return httpx.Response(200, content=_jwks(new_jwk))

    client = _client(handler)
    verifier = ProductionOidcVerifier(_config(), client, monotonic=clock)
    verifier.initialize()
    observed_lock = _ObservedLock()
    verifier._lock = observed_lock
    clock.value = 99
    new_token = _token(new_private, "kid-new")
    old_token = _token(old_private, "kid-old")
    executor = ThreadPoolExecutor(max_workers=3)
    refresh = executor.submit(verifier.verify, new_token)
    try:
        assert refresh_started.wait(timeout=5)
        new_waiter = executor.submit(verifier.verify, new_token)
        old_waiter = executor.submit(verifier.verify, old_token)
        assert observed_lock.wait_for_attempts(3, timeout=5)
        clock.value = 101
        release_refresh.set()

        assert refresh.result(timeout=5).subject == "subject:Exact-01"
        assert new_waiter.result(timeout=5).subject == "subject:Exact-01"
        with pytest.raises(AuthenticationError) as old_raised:
            old_waiter.result(timeout=5)
        assert old_raised.value.outcome is AuthenticationOutcome.VERIFICATION_REFUSED
        assert calls == 2
    finally:
        release_refresh.set()
        executor.shutdown(wait=True, cancel_futures=True)
        client.close()


def test_expiry_causes_only_one_refresh_for_an_unknown_kid():
    private, jwk = _key("kid-current")
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=_jwks(jwk))

    clock = _Clock()
    client = _client(handler)
    verifier = ProductionOidcVerifier(_config(), client, monotonic=clock)
    verifier.initialize()
    clock.value = 10

    with pytest.raises(AuthenticationError):
        verifier.verify(_token(private, "kid-unknown-after-expiry"))

    assert calls == 2
    client.close()


def test_concurrent_verifies_share_one_expired_generation_refresh():
    private, jwk = _key("kid-concurrent")
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=_jwks(jwk))

    clock = _Clock()
    client = _client(handler)
    verifier = ProductionOidcVerifier(_config(), client, monotonic=clock)
    verifier.initialize()
    clock.value = 11
    barrier = Barrier(3)
    token = _token(private, "kid-concurrent")

    def verify():
        barrier.wait(timeout=5)
        return verifier.verify(token).subject

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(verify) for _index in range(2)]
        barrier.wait(timeout=5)
        assert [future.result(timeout=5) for future in futures] == [
            "subject:Exact-01",
            "subject:Exact-01",
        ]

    assert calls == 2
    client.close()


def test_monotonic_overall_deadline_is_enforced():
    _private, jwk = _key("kid-deadline")
    clock = _Clock()

    def handler(_request):
        clock.value = 6
        return httpx.Response(200, content=_jwks(jwk))

    client = _client(handler)
    verifier = ProductionOidcVerifier(
        _config(overall_deadline_seconds=5),
        client,
        monotonic=clock,
    )

    with pytest.raises(AuthenticationStartupError):
        verifier.initialize()
    client.close()


def test_client_redirect_mode_and_non_https_url_are_configuration_errors():
    redirecting = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"keys": []})
        ),
        follow_redirects=True,
    )
    with pytest.raises(AuthenticationStartupError):
        ProductionOidcVerifier(_config(), redirecting)
    redirecting.close()

    with pytest.raises(AuthenticationStartupError):
        _config(jwks_url="http://issuer.example.test/jwks")

    with pytest.raises(AuthenticationStartupError):
        _config(cache_ttl_seconds=4, refresh_cooldown_seconds=5)
