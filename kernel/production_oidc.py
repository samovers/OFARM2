"""Bounded RS256 OIDC verification with a serialized JWKS cache."""
from __future__ import annotations

import base64
import binascii
import json
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from jwt.algorithms import RSAAlgorithm

from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TenantCapabilityContractError,
    validate_oidc_issuer,
)

from .authentication import (
    AuthenticationError,
    AuthenticationOutcome,
    AuthenticationStartupError,
    VerifiedIdentity,
)


_B64URL = re.compile(r"^[A-Za-z0-9_-]+$")
_KID = re.compile(r"^[!-~]{1,128}$")
_SUBJECT = re.compile(r"^[!-~]{1,255}$")
_PRIVATE_JWK_MEMBERS = frozenset({"d", "p", "q", "dp", "dq", "qi", "oth"})
_ALLOWED_HEADERS = frozenset({"alg", "kid", "typ"})


def _refusal(
    detail: str,
    outcome: AuthenticationOutcome = AuthenticationOutcome.INVALID_CREDENTIAL,
) -> AuthenticationError:
    return AuthenticationError(outcome, internal_detail=detail)


@dataclass(frozen=True, slots=True)
class ProductionOidcConfig:
    issuer: str
    audience: str
    jwks_url: str
    cache_ttl_seconds: float = 300
    unknown_kid_cooldown_seconds: float = 30
    connect_timeout_seconds: float = 2
    read_timeout_seconds: float = 2
    overall_deadline_seconds: float = 5
    leeway_seconds: int = 0
    max_token_bytes: int = 16_384
    max_jwks_bytes: int = 1_048_576
    max_jwks_keys: int = 100

    def __post_init__(self) -> None:
        try:
            validate_oidc_issuer(self.issuer)
        except TenantCapabilityContractError as exc:
            raise AuthenticationStartupError("OIDC issuer is invalid") from exc
        if type(self.audience) is not str or not self.audience:
            raise AuthenticationStartupError("OIDC audience is invalid")
        if (
            type(self.jwks_url) is not str
            or not self.jwks_url.startswith("https://")
        ):
            raise AuthenticationStartupError("JWKS URL must use HTTPS")
        positive = (
            self.cache_ttl_seconds,
            self.unknown_kid_cooldown_seconds,
            self.connect_timeout_seconds,
            self.read_timeout_seconds,
            self.overall_deadline_seconds,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
            for value in positive
        ):
            raise AuthenticationStartupError("OIDC timing bound is invalid")
        if (
            self.connect_timeout_seconds > self.overall_deadline_seconds
            or self.read_timeout_seconds > self.overall_deadline_seconds
        ):
            raise AuthenticationStartupError(
                "OIDC I/O timeout exceeds its overall deadline"
            )
        integer_bounds = (
            (self.leeway_seconds, 0, 300),
            (self.max_token_bytes, 1, 1_048_576),
            (self.max_jwks_bytes, 1, 16_777_216),
            (self.max_jwks_keys, 1, 1_000),
        )
        if any(
            type(value) is not int or not minimum <= value <= maximum
            for value, minimum, maximum in integer_bounds
        ):
            raise AuthenticationStartupError("OIDC size bound is invalid")


@dataclass(frozen=True, slots=True)
class _JwksGeneration:
    keys: dict[str, RSAPublicKey]
    expires_at: float


def _duplicate_rejecting_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _refusal("duplicate JSON member")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise _refusal(f"non-finite JSON constant {value!r}")


def _json_object(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_constant,
        )
    except AuthenticationError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as exc:
        raise _refusal(f"malformed {label} JSON") from exc
    if type(value) is not dict:
        raise _refusal(f"{label} must be a JSON object")
    return value


def _b64url_decode(segment: str, label: str) -> bytes:
    if type(segment) is not str or _B64URL.fullmatch(segment) is None:
        raise _refusal(f"{label} is not canonical base64url")
    try:
        decoded = base64.urlsafe_b64decode(
            segment + "=" * (-len(segment) % 4)
        )
    except (binascii.Error, ValueError) as exc:
        raise _refusal(f"{label} is malformed") from exc
    canonical = base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii")
    if canonical != segment:
        raise _refusal(f"{label} is not canonical base64url")
    return decoded


def _token_header(token: str, max_bytes: int) -> dict[str, object]:
    if type(token) is not str:
        raise _refusal("credential is not text", AuthenticationOutcome.NO_CREDENTIAL)
    try:
        token_bytes = token.encode("ascii", errors="strict")
    except UnicodeEncodeError as exc:
        raise _refusal("credential is not ASCII") from exc
    if not 1 <= len(token_bytes) <= max_bytes:
        raise _refusal("credential size is outside the bound")
    segments = token.split(".")
    if len(segments) != 3 or not all(segments):
        raise _refusal("credential is not compact JWS")
    header = _json_object(_b64url_decode(segments[0], "header"), "header")
    _json_object(_b64url_decode(segments[1], "claims"), "claims")
    _b64url_decode(segments[2], "signature")
    if set(header) - _ALLOWED_HEADERS:
        raise _refusal("unsupported JOSE header")
    if header.get("alg") != "RS256":
        raise _refusal("production OIDC accepts only RS256")
    kid = header.get("kid")
    if type(kid) is not str or _KID.fullmatch(kid) is None:
        raise _refusal("JOSE kid is invalid")
    if "typ" in header and header["typ"] != "JWT":
        raise _refusal("JOSE typ is invalid")
    return header


def _rsa_public_key(jwk: dict[str, object]) -> tuple[str, RSAPublicKey]:
    if _PRIVATE_JWK_MEMBERS & set(jwk):
        raise _refusal(
            "JWKS contains private key material",
            AuthenticationOutcome.VERIFIER_UNAVAILABLE,
        )
    kid = jwk.get("kid")
    if (
        type(kid) is not str
        or _KID.fullmatch(kid) is None
        or jwk.get("kty") != "RSA"
        or jwk.get("alg", "RS256") != "RS256"
        or jwk.get("use", "sig") != "sig"
    ):
        raise _refusal(
            "JWKS contains an incompatible key",
            AuthenticationOutcome.VERIFIER_UNAVAILABLE,
        )
    key_ops = jwk.get("key_ops", ["verify"])
    if (
        type(key_ops) is not list
        or any(type(operation) is not str for operation in key_ops)
        or "verify" not in key_ops
        or any(operation != "verify" for operation in key_ops)
    ):
        raise _refusal(
            "JWKS key operations are incompatible",
            AuthenticationOutcome.VERIFIER_UNAVAILABLE,
        )
    modulus = jwk.get("n")
    exponent = jwk.get("e")
    if type(modulus) is not str or type(exponent) is not str:
        raise _refusal(
            "RSA JWK parameters are missing",
            AuthenticationOutcome.VERIFIER_UNAVAILABLE,
        )
    try:
        n_value = int.from_bytes(_b64url_decode(modulus, "RSA modulus"), "big")
        e_value = int.from_bytes(_b64url_decode(exponent, "RSA exponent"), "big")
    except AuthenticationError as exc:
        raise _refusal(
            "RSA JWK parameters are malformed",
            AuthenticationOutcome.VERIFIER_UNAVAILABLE,
        ) from exc
    if n_value.bit_length() < 2048 or e_value < 3 or e_value % 2 == 0:
        raise _refusal(
            "RSA JWK strength is invalid",
            AuthenticationOutcome.VERIFIER_UNAVAILABLE,
        )
    try:
        key = RSAAlgorithm.from_jwk(json.dumps(jwk))
    except (TypeError, ValueError, jwt.PyJWTError) as exc:
        raise _refusal(
            "RSA JWK construction failed",
            AuthenticationOutcome.VERIFIER_UNAVAILABLE,
        ) from exc
    if not isinstance(key, RSAPublicKey):
        raise _refusal(
            "JWK did not produce an RSA public key",
            AuthenticationOutcome.VERIFIER_UNAVAILABLE,
        )
    return kid, key


def _jwks_keys(raw: bytes, maximum: int) -> dict[str, RSAPublicKey]:
    try:
        document = _json_object(raw, "JWKS")
    except AuthenticationError as exc:
        raise _refusal(
            "JWKS JSON is invalid",
            AuthenticationOutcome.VERIFIER_UNAVAILABLE,
        ) from exc
    values = document.get("keys")
    if (
        set(document) != {"keys"}
        or type(values) is not list
        or not 1 <= len(values) <= maximum
    ):
        raise _refusal(
            "JWKS key set is invalid",
            AuthenticationOutcome.VERIFIER_UNAVAILABLE,
        )
    keys: dict[str, RSAPublicKey] = {}
    for value in values:
        if type(value) is not dict:
            raise _refusal(
                "JWKS key entry is invalid",
                AuthenticationOutcome.VERIFIER_UNAVAILABLE,
            )
        kid, key = _rsa_public_key(value)
        if kid in keys:
            raise _refusal(
                "JWKS contains duplicate kid",
                AuthenticationOutcome.VERIFIER_UNAVAILABLE,
            )
        keys[kid] = key
    return keys


class ProductionOidcVerifier:
    """One initialized verifier with one lock and no stale-key fallback."""

    def __init__(
        self,
        config: ProductionOidcConfig,
        client: httpx.Client,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if client.follow_redirects:
            raise AuthenticationStartupError(
                "OIDC HTTP client must disable redirects"
            )
        self._config = config
        self._client = client
        self._monotonic = monotonic
        self._lock = Lock()
        self._generation: _JwksGeneration | None = None
        self._last_unknown_refresh = float("-inf")

    def initialize(self) -> None:
        try:
            with self._lock:
                self._generation = self._fetch_generation()
        except AuthenticationError as exc:
            raise AuthenticationStartupError(
                "production OIDC initialization failed"
            ) from exc

    def _fetch_generation(self) -> _JwksGeneration:
        config = self._config
        started = self._monotonic()
        timeout = httpx.Timeout(
            connect=config.connect_timeout_seconds,
            read=config.read_timeout_seconds,
            write=config.connect_timeout_seconds,
            pool=config.connect_timeout_seconds,
        )
        body = bytearray()
        try:
            with self._client.stream(
                "GET",
                config.jwks_url,
                headers={"Accept": "application/json"},
                timeout=timeout,
            ) as response:
                if response.history or 300 <= response.status_code < 400:
                    raise _refusal(
                        "JWKS redirect refused",
                        AuthenticationOutcome.VERIFIER_UNAVAILABLE,
                    )
                if response.status_code != 200:
                    raise _refusal(
                        "JWKS endpoint did not return 200",
                        AuthenticationOutcome.VERIFIER_UNAVAILABLE,
                    )
                length = response.headers.get("content-length")
                if length is not None and (
                    len(length) > 16
                    or not length.isdigit()
                    or int(length) > config.max_jwks_bytes
                ):
                    raise _refusal(
                        "JWKS body exceeds the byte bound",
                        AuthenticationOutcome.VERIFIER_UNAVAILABLE,
                    )
                for chunk in response.iter_bytes():
                    if self._monotonic() - started > (
                        config.overall_deadline_seconds
                    ):
                        raise _refusal(
                            "JWKS overall deadline exceeded",
                            AuthenticationOutcome.VERIFIER_UNAVAILABLE,
                        )
                    body.extend(chunk)
                    if len(body) > config.max_jwks_bytes:
                        raise _refusal(
                            "JWKS body exceeds the byte bound",
                            AuthenticationOutcome.VERIFIER_UNAVAILABLE,
                        )
        except AuthenticationError:
            raise
        except httpx.HTTPError as exc:
            raise _refusal(
                "JWKS request failed",
                AuthenticationOutcome.VERIFIER_UNAVAILABLE,
            ) from exc
        if self._monotonic() - started > config.overall_deadline_seconds:
            raise _refusal(
                "JWKS overall deadline exceeded",
                AuthenticationOutcome.VERIFIER_UNAVAILABLE,
            )
        keys = _jwks_keys(bytes(body), config.max_jwks_keys)
        return _JwksGeneration(
            keys=keys,
            expires_at=self._monotonic() + config.cache_ttl_seconds,
        )

    def _key(self, kid: str) -> RSAPublicKey:
        now = self._monotonic()
        with self._lock:
            generation = self._generation
            if generation is None:
                raise _refusal(
                    "production OIDC verifier is not initialized",
                    AuthenticationOutcome.VERIFIER_UNAVAILABLE,
                )
            refreshed = False
            if now >= generation.expires_at:
                generation = self._fetch_generation()
                self._generation = generation
                refreshed = True
            key = generation.keys.get(kid)
            if key is not None:
                return key
            if not refreshed and now - self._last_unknown_refresh >= (
                self._config.unknown_kid_cooldown_seconds
            ):
                self._last_unknown_refresh = now
                generation = self._fetch_generation()
                self._generation = generation
                key = generation.keys.get(kid)
                if key is not None:
                    return key
            elif refreshed:
                self._last_unknown_refresh = now
        raise _refusal("JOSE kid is unknown")

    def verify(self, token: str) -> VerifiedIdentity:
        header = _token_header(token, self._config.max_token_bytes)
        key = self._key(header["kid"])
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=self._config.audience,
                issuer=self._config.issuer,
                leeway=self._config.leeway_seconds,
                options={"require": ["iss", "sub", "aud", "exp"]},
            )
        except jwt.PyJWTError as exc:
            raise _refusal("JWT verification failed") from exc
        issuer = claims.get("iss")
        subject = claims.get("sub")
        try:
            exact_issuer = validate_oidc_issuer(issuer)
        except TenantCapabilityContractError as exc:
            raise _refusal("verified issuer grammar refused") from exc
        if type(subject) is not str or _SUBJECT.fullmatch(subject) is None:
            raise _refusal("verified subject grammar refused")
        return VerifiedIdentity(
            equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
            issuer=exact_issuer,
            subject=subject,
        )
