"""Explicit authentication modes and exact OIDC identity verification.

Development header authentication, the local HS256 test issuer, and the
production JWKS verifier are different runtime types.  A missing setting never
selects one of them implicitly.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import math
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Callable, Protocol, final, runtime_checkable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TenantCapabilityContractError,
    validate_oidc_issuer,
)


_B64URL_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")
_OIDC_SUBJECT = re.compile(r"^[!-~]{1,255}$")
_VISIBLE_ASCII = re.compile(r"^[!-~]+$")
_MAX_JWT_BYTES = 16_384
_MIN_NUMERIC_DATE = -62_135_596_800
_MAX_NUMERIC_DATE = 253_402_300_799
_PRODUCTION_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }
)
_FORBIDDEN_JOSE_HEADERS = frozenset(
    {"crit", "b64", "jku", "jwk", "x5u", "x5c", "x5t", "x5t#S256"}
)


class AuthenticationMode(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class PreBindingOutcome(str, Enum):
    """Closed, non-sensitive outcomes that #192 may consume later."""

    NO_CREDENTIAL = "NO_CREDENTIAL"
    INVALID_CREDENTIAL = "INVALID_CREDENTIAL"
    VERIFIER_UNAVAILABLE = "VERIFIER_UNAVAILABLE"
    BINDING_UNAVAILABLE = "BINDING_UNAVAILABLE"
    PRINCIPAL_UNBOUND = "PRINCIPAL_UNBOUND"
    BINDING_INTEGRITY_REFUSED = "BINDING_INTEGRITY_REFUSED"
    CONFIGURATION_REFUSED = "CONFIGURATION_REFUSED"
    SIGNER_UNAVAILABLE = "SIGNER_UNAVAILABLE"
    CAPABILITY_REFUSED = "CAPABILITY_REFUSED"


class AuthenticationStartupError(RuntimeError):
    """The selected authentication mode could not initialize safely."""


class OidcError(Exception):
    """Fail-closed OIDC refusal without credential or identity disclosure."""

    def __init__(
        self,
        outcome: PreBindingOutcome = PreBindingOutcome.INVALID_CREDENTIAL,
        *,
        internal_detail: str = "",
    ) -> None:
        self.outcome = outcome
        self.internal_detail = internal_detail
        super().__init__(f"authentication refused ({outcome.value})")


@dataclass(frozen=True, slots=True)
class VerifiedOidcIdentity:
    """Exact decoded identity bytes accepted by the configured verifier."""

    equality_policy: str
    issuer: str
    subject: str
    claims: dict[str, Any] = field(repr=False, compare=False)


@runtime_checkable
class OidcVerifier(Protocol):
    def initialize(self) -> None: ...

    def verify_identity(self, token: str) -> VerifiedOidcIdentity: ...


@runtime_checkable
class PrincipalBindingResolver(Protocol):
    def initialize(self) -> None: ...

    def resolve(self, identity: VerifiedOidcIdentity) -> object: ...


def _reject_json_constant(token: str) -> None:
    raise OidcError(internal_detail=f"non-finite JSON constant {token!r}")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OidcError(internal_detail="duplicate JWT object member")
        result[key] = value
    return result


def _b64url_decode(segment: str) -> bytes:
    if type(segment) is not str or _B64URL_SEGMENT.fullmatch(segment) is None:
        raise OidcError(internal_detail="noncanonical compact-JWS segment")
    try:
        decoded = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (binascii.Error, ValueError) as exc:
        raise OidcError(internal_detail="malformed compact-JWS segment") from exc
    if _b64url_encode(decoded) != segment:
        raise OidcError(internal_detail="noncanonical compact-JWS segment")
    return decoded


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _strict_unverified_token(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if type(token) is not str:
        raise OidcError(internal_detail="token is not text")
    try:
        encoded = token.encode("ascii", errors="strict")
    except UnicodeEncodeError as exc:
        raise OidcError(internal_detail="token is not ASCII") from exc
    if not 1 <= len(encoded) <= _MAX_JWT_BYTES:
        raise OidcError(internal_detail="token size is outside the bound")
    segments = token.split(".")
    if len(segments) != 3 or not all(segments):
        raise OidcError(internal_detail="token is not compact JWS")
    try:
        header = json.loads(
            _b64url_decode(segments[0]).decode("utf-8", errors="strict"),
            parse_constant=_reject_json_constant,
            object_pairs_hook=_object_without_duplicates,
        )
        claims = json.loads(
            _b64url_decode(segments[1]).decode("utf-8", errors="strict"),
            parse_constant=_reject_json_constant,
            object_pairs_hook=_object_without_duplicates,
        )
        _b64url_decode(segments[2])
    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        OverflowError,
        RecursionError,
    ) as exc:
        raise OidcError(internal_detail="malformed token JSON") from exc
    if type(header) is not dict or type(claims) is not dict:
        raise OidcError(internal_detail="JWT header and claims must be objects")
    return header, claims


def _numeric_date(claims: dict[str, Any], name: str, *, required: bool) -> int | None:
    value = claims.get(name)
    if value is None:
        if required:
            raise OidcError(internal_detail=f"missing {name}")
        return None
    if type(value) is int:
        numeric_date = value
    elif type(value) is float:
        if not math.isfinite(value):
            raise OidcError(internal_detail=f"invalid {name}")
        numeric_date = int(value)
    else:
        raise OidcError(internal_detail=f"invalid {name}")
    if not _MIN_NUMERIC_DATE <= numeric_date <= _MAX_NUMERIC_DATE:
        raise OidcError(internal_detail=f"invalid {name}")
    return numeric_date


def _validate_exact_identity(issuer: object, subject: object) -> tuple[str, str]:
    try:
        exact_issuer = validate_oidc_issuer(issuer)
    except TenantCapabilityContractError as exc:
        raise OidcError(internal_detail="issuer grammar refused") from exc
    if type(subject) is not str or _OIDC_SUBJECT.fullmatch(subject) is None:
        raise OidcError(internal_detail="subject grammar refused")
    return exact_issuer, subject


def _claim_path(claims: dict[str, Any], path: str) -> object:
    node: object = claims
    for part in path.split("."):
        if type(node) is not dict or part not in node:
            return None
        node = node[part]
    return node


def _verify_hs256(
    token: str,
    *,
    secret: str,
    issuer: str,
    audience: str,
    leeway_seconds: int = 0,
) -> dict[str, Any]:
    """Strict local test verifier. This path is never used by production mode."""

    if not secret:
        raise OidcError(internal_detail="test secret is absent")
    header, claims = _strict_unverified_token(token)
    if _FORBIDDEN_JOSE_HEADERS.intersection(header):
        raise OidcError(internal_detail="unsupported JOSE header")
    if header.get("alg") != "HS256":
        raise OidcError(internal_detail="test algorithm differs")
    header_b64, payload_b64, signature_b64 = token.split(".")
    expected = _b64url_encode(
        hmac.new(
            secret.encode("utf-8"),
            f"{header_b64}.{payload_b64}".encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    if not hmac.compare_digest(expected, signature_b64):
        raise OidcError(internal_detail="signature verification failed")
    if claims.get("iss") != issuer:
        raise OidcError(internal_detail="issuer differs")
    audience_claim = claims.get("aud")
    if not (
        audience_claim == audience
        or (
            type(audience_claim) is list
            and all(type(item) is str for item in audience_claim)
            and audience in audience_claim
        )
    ):
        raise OidcError(internal_detail="audience differs")
    now = int(time.time())
    expires = _numeric_date(claims, "exp", required=True)
    assert expires is not None
    if now > expires + leeway_seconds:
        raise OidcError(internal_detail="token expired")
    not_before = _numeric_date(claims, "nbf", required=False)
    if not_before is not None and now + leeway_seconds < not_before:
        raise OidcError(internal_detail="token not yet valid")
    return claims


@dataclass(frozen=True, slots=True)
class OidcConfig:
    """Local HS256 test issuer. It cannot construct production mode."""

    issuer: str
    audience: str
    algorithm: str = "HS256"
    hs256_secret: str | None = None
    subject_claim: str = "sub"
    roles_claim: str | None = None
    leeway_seconds: int = 0

    def initialize(self) -> None:
        if self.algorithm != "HS256":
            raise AuthenticationStartupError(
                "test authentication accepts only the local HS256 verifier"
            )
        if not self.hs256_secret:
            raise AuthenticationStartupError("test authentication secret is required")
        try:
            _validate_exact_identity(self.issuer, "subject-probe")
        except OidcError as exc:
            raise AuthenticationStartupError("test OIDC issuer is invalid") from exc

    def verify_identity(self, token: str) -> VerifiedOidcIdentity:
        if self.algorithm != "HS256":
            raise OidcError(internal_detail="test algorithm differs")
        claims = _verify_hs256(
            token,
            secret=self.hs256_secret or "",
            issuer=self.issuer,
            audience=self.audience,
            leeway_seconds=self.leeway_seconds,
        )
        if self.subject_claim != "sub":
            raise OidcError(internal_detail="subject claim must be sub")
        issuer, subject = _validate_exact_identity(claims.get("iss"), claims.get("sub"))
        return VerifiedOidcIdentity(
            equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
            issuer=issuer,
            subject=subject,
            claims=claims,
        )

    def verify(self, token: str) -> dict[str, Any]:
        """Compatibility view used by the existing M2 engineering tests."""

        identity = self.verify_identity(token)
        roles = _claim_path(identity.claims, self.roles_claim) if self.roles_claim else []
        if type(roles) is not list:
            roles = []
        return {
            "partyRef": identity.subject,
            "roles": list(roles),
            "claims": identity.claims,
        }


@dataclass(frozen=True, slots=True)
class ProductionOidcConfig:
    """Pinned production trust inputs.

    ``jwks_url`` must name the final HTTPS resource. The verifier follows no
    redirect, so neither same-origin nor cross-origin target changes are
    allowed.
    """

    issuer: str
    audience: str
    jwks_url: str
    algorithms: tuple[str, ...] = ("RS256",)
    leeway_seconds: int = 0
    jwks_lifespan_seconds: int = 300
    jwks_miss_refresh_seconds: int = 5
    timeout_seconds: int = 5

    def validate(self) -> None:
        try:
            validate_oidc_issuer(self.issuer)
        except TenantCapabilityContractError as exc:
            raise AuthenticationStartupError("production OIDC issuer is invalid") from exc
        if (
            type(self.audience) is not str
            or not 1 <= len(self.audience.encode("utf-8")) <= 2048
            or _VISIBLE_ASCII.fullmatch(self.audience) is None
        ):
            raise AuthenticationStartupError("production OIDC audience is invalid")
        if (
            type(self.jwks_url) is not str
            or not 1 <= len(self.jwks_url.encode("utf-8")) <= 2048
            or _VISIBLE_ASCII.fullmatch(self.jwks_url) is None
        ):
            raise AuthenticationStartupError("production JWKS URL must be an HTTPS URL")
        parsed_jwks = urlsplit(self.jwks_url)
        if (
            parsed_jwks.scheme != "https"
            or not parsed_jwks.netloc
            or not parsed_jwks.hostname
            or parsed_jwks.username is not None
            or parsed_jwks.password is not None
            or parsed_jwks.fragment
        ):
            raise AuthenticationStartupError("production JWKS URL must be an HTTPS URL")
        if (
            type(self.algorithms) is not tuple
            or not self.algorithms
            or len(set(self.algorithms)) != len(self.algorithms)
            or any(algorithm not in _PRODUCTION_ALGORITHMS for algorithm in self.algorithms)
        ):
            raise AuthenticationStartupError("production OIDC algorithms are invalid")
        if type(self.leeway_seconds) is not int or not 0 <= self.leeway_seconds <= 60:
            raise AuthenticationStartupError("production OIDC leeway is invalid")
        if (
            type(self.jwks_lifespan_seconds) is not int
            or not 60 <= self.jwks_lifespan_seconds <= 86_400
        ):
            raise AuthenticationStartupError("production JWKS lifespan is invalid")
        if (
            type(self.jwks_miss_refresh_seconds) is not int
            or not 1
            <= self.jwks_miss_refresh_seconds
            <= min(self.jwks_lifespan_seconds, 300)
        ):
            raise AuthenticationStartupError(
                "production JWKS miss refresh interval is invalid"
            )
        if type(self.timeout_seconds) is not int or not 1 <= self.timeout_seconds <= 30:
            raise AuthenticationStartupError("production JWKS timeout is invalid")


class _JwksProviderStateError(RuntimeError):
    """A provider fetch or key-set state cannot safely verify credentials."""


class _RejectJwksRedirectHandler(HTTPRedirectHandler):
    """Refuse every JWKS redirect, including same-origin HTTPS redirects."""

    def redirect_request(
        self,
        request: object,
        response: object,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> None:
        return None


def _build_no_redirect_jwks_opener() -> object:
    return build_opener(_RejectJwksRedirectHandler())


@final
class _ProductionJwksClient:
    """Fetch only the configured final HTTPS URL; origin changes are forbidden."""

    def __init__(
        self,
        jwt_module: Any,
        *,
        uri: str,
        timeout_seconds: int,
    ) -> None:
        self._jwt = jwt_module
        self._uri = uri
        self._timeout_seconds = timeout_seconds
        self._opener = _build_no_redirect_jwks_opener()

    def get_jwk_set(self, *, refresh: bool) -> object:
        del refresh
        try:
            request = Request(url=self._uri)
            with self._opener.open(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                response_url = response.geturl()
                if (
                    type(response_url) is not str
                    or response_url != self._uri
                    or urlsplit(response_url).scheme != "https"
                ):
                    raise _JwksProviderStateError(
                        "JWKS response target differs from configured HTTPS URL"
                    )
                jwk_data = json.load(response)
        except _JwksProviderStateError:
            raise
        except HTTPError as exc:
            exc.close()
            raise _JwksProviderStateError("JWKS HTTPS fetch failed") from exc
        except (URLError, TimeoutError) as exc:
            raise _JwksProviderStateError("JWKS HTTPS fetch failed") from exc
        if type(jwk_data) is not dict:
            raise _JwksProviderStateError("JWKS endpoint returned a non-object")
        try:
            return self._jwt.PyJWKSet.from_dict(jwk_data)
        except Exception as exc:
            raise _JwksProviderStateError("JWKS provider state is invalid") from exc


@dataclass(frozen=True, slots=True)
class _ValidatedJwksGeneration:
    loaded_at: float
    signing_keys: tuple[tuple[str, str, object], ...]

    def select(self, key_id: str, algorithm: str) -> object | None:
        for candidate_id, candidate_algorithm, candidate_key in self.signing_keys:
            if candidate_id == key_id and candidate_algorithm == algorithm:
                return candidate_key
        return None


@final
class ProductionOidcVerifier:
    """Maintained PyJWT verifier with bounded, validated JWKS generations."""

    def __init__(self, config: ProductionOidcConfig):
        self._bind(
            config,
            jwks_client=None,
            clock=time.monotonic,
            production_eligible=True,
        )

    @classmethod
    def for_test(
        cls,
        config: ProductionOidcConfig,
        *,
        jwks_client: object,
        clock: Callable[[], float] | None = None,
    ) -> "ProductionOidcVerifier":
        """Build a visibly non-production verifier with fixture trust inputs."""

        verifier = object.__new__(cls)
        verifier._bind(
            config,
            jwks_client=jwks_client,
            clock=time.monotonic if clock is None else clock,
            production_eligible=False,
        )
        return verifier

    def _bind(
        self,
        config: ProductionOidcConfig,
        *,
        jwks_client: object | None,
        clock: Callable[[], float],
        production_eligible: bool,
    ) -> None:
        self.config = config
        self._jwks_client = jwks_client
        self._clock = clock
        self._production_eligible = production_eligible
        self._jwt: Any | None = None
        self._generation: _ValidatedJwksGeneration | None = None
        self._generation_lock = Lock()
        self._refresh_lock = Lock()
        self._last_miss_refresh_at: float | None = None
        self._next_expired_refresh_at: float | None = None
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def production_eligible(self) -> bool:
        return self._production_eligible is True

    def initialize(self) -> None:
        self._initialized = False
        with self._generation_lock:
            self._generation = None
            self._last_miss_refresh_at = None
            self._next_expired_refresh_at = None
        self.config.validate()
        try:
            import jwt
        except ImportError as exc:
            raise AuthenticationStartupError(
                "production OIDC verifier dependency is unavailable"
            ) from exc
        self._jwt = jwt
        if self._jwks_client is None:
            self._jwks_client = _ProductionJwksClient(
                jwt,
                uri=self.config.jwks_url,
                timeout_seconds=self.config.timeout_seconds,
            )
        try:
            generation = self._load_generation()
        except _JwksProviderStateError as exc:
            raise AuthenticationStartupError(
                "production OIDC JWKS initialization failed"
            ) from exc
        with self._generation_lock:
            self._generation = generation
        self._initialized = True

    def _load_generation(self) -> _ValidatedJwksGeneration:
        assert self._jwks_client is not None
        try:
            jwk_set = self._jwks_client.get_jwk_set(refresh=True)
            raw_keys = tuple(jwk_set.keys)
            signing_keys = self._validate_signing_keys(raw_keys)
        except _JwksProviderStateError:
            raise
        except Exception as exc:
            raise _JwksProviderStateError("JWKS provider fetch failed") from exc
        return _ValidatedJwksGeneration(
            loaded_at=self._clock(),
            signing_keys=signing_keys,
        )

    def _validate_signing_keys(
        self,
        raw_keys: tuple[object, ...],
    ) -> tuple[tuple[str, str, object], ...]:
        signing_keys: list[tuple[str, str, object]] = []
        identities: set[tuple[str, str]] = set()
        for key in raw_keys:
            public_key_use = getattr(key, "public_key_use", None)
            if public_key_use not in (None, "sig"):
                continue
            jwk_data = getattr(key, "_jwk_data", None)
            key_operations = jwk_data.get("key_ops") if type(jwk_data) is dict else None
            if key_operations is not None and (
                type(key_operations) is not list
                or not key_operations
                or any(type(operation) is not str for operation in key_operations)
                or "verify" not in key_operations
            ):
                continue
            key_id = getattr(key, "key_id", None)
            verifier_key = getattr(key, "key", None)
            if (
                type(key_id) is not str
                or _VISIBLE_ASCII.fullmatch(key_id) is None
                or not 1 <= len(key_id.encode("ascii")) <= 255
                or verifier_key is None
            ):
                continue
            if (
                type(jwk_data) is dict
                and jwk_data.get("kty") == "RSA"
                and (
                    type(getattr(verifier_key, "key_size", None)) is not int
                    or verifier_key.key_size < 2_048
                )
            ):
                raise _JwksProviderStateError(
                    "JWKS contains an undersized RSA signing key"
                )
            for algorithm in self._key_algorithms(key, jwk_data):
                identity = (key_id, algorithm)
                if identity in identities:
                    raise _JwksProviderStateError(
                        "JWKS contains an ambiguous signing-key identity"
                    )
                identities.add(identity)
                signing_keys.append((key_id, algorithm, verifier_key))

        if not signing_keys:
            raise _JwksProviderStateError("JWKS has no usable signing key")
        return tuple(signing_keys)

    def _key_algorithms(
        self, key: object, jwk_data: object
    ) -> tuple[str, ...]:
        inferred = getattr(key, "algorithm_name", None)
        if type(jwk_data) is not dict:
            return (inferred,) if inferred in self.config.algorithms else ()

        key_type = jwk_data.get("kty")
        curve = jwk_data.get("crv")
        compatible: frozenset[str]
        if key_type == "RSA":
            compatible = frozenset(
                {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512"}
            )
        elif key_type == "EC":
            compatible = {
                "P-256": frozenset({"ES256"}),
                "P-384": frozenset({"ES384"}),
                "P-521": frozenset({"ES512"}),
            }.get(curve, frozenset())
        elif key_type == "OKP" and curve == "Ed25519":
            compatible = frozenset({"EdDSA"})
        else:
            compatible = frozenset()
        if "alg" in jwk_data:
            declared = jwk_data["alg"]
            compatible = (
                compatible.intersection({declared})
                if type(declared) is str
                else frozenset()
            )
        return tuple(
            algorithm
            for algorithm in self.config.algorithms
            if algorithm in compatible
        )

    def _select_signing_key(self, key_id: str, algorithm: str) -> object:
        try:
            with self._generation_lock:
                generation = self._generation
            refreshed_for_lifespan = False
            if (
                generation is None
                or self._clock() - generation.loaded_at
                >= self.config.jwks_lifespan_seconds
            ):
                generation = self._refresh_expired_generation()
                refreshed_for_lifespan = True
            selected = generation.select(key_id, algorithm)
            if selected is None and not refreshed_for_lifespan:
                generation = self._refresh_generation_for_miss(key_id, algorithm)
                selected = generation.select(key_id, algorithm)
            elif selected is None:
                with self._generation_lock:
                    self._last_miss_refresh_at = generation.loaded_at
        except _JwksProviderStateError as exc:
            raise OidcError(
                PreBindingOutcome.VERIFIER_UNAVAILABLE,
                internal_detail="JWKS provider state is unavailable",
            ) from exc
        if selected is None:
            raise OidcError(internal_detail="no matching JWKS signing key")
        return selected

    def _refresh_expired_generation(self) -> _ValidatedJwksGeneration:
        """Non-blocking single-flight a lifespan refresh with failure cooldown."""

        if not self._refresh_lock.acquire(blocking=False):
            raise _JwksProviderStateError("JWKS refresh is already in progress")
        try:
            with self._generation_lock:
                generation = self._generation
                now = self._clock()
                if (
                    generation is not None
                    and now - generation.loaded_at < self.config.jwks_lifespan_seconds
                ):
                    return generation
                if (
                    self._next_expired_refresh_at is not None
                    and now < self._next_expired_refresh_at
                ):
                    raise _JwksProviderStateError(
                        "JWKS lifespan refresh is in failure cooldown"
                    )
            try:
                refreshed = self._load_generation()
            except _JwksProviderStateError:
                with self._generation_lock:
                    self._next_expired_refresh_at = self._clock() + max(
                        self.config.jwks_miss_refresh_seconds,
                        self.config.timeout_seconds,
                    )
                raise
            with self._generation_lock:
                self._generation = refreshed
                self._next_expired_refresh_at = None
            return refreshed
        finally:
            self._refresh_lock.release()

    def _refresh_generation_for_miss(
        self, key_id: str, algorithm: str
    ) -> _ValidatedJwksGeneration:
        """Non-blocking single-flight refresh across all unknown key IDs."""

        if not self._refresh_lock.acquire(blocking=False):
            with self._generation_lock:
                generation = self._generation
                if generation is None:
                    raise _JwksProviderStateError("JWKS generation is absent")
                return generation

        try:
            with self._generation_lock:
                generation = self._generation
                if generation is None:
                    raise _JwksProviderStateError("JWKS generation is absent")
                if generation.select(key_id, algorithm) is not None:
                    return generation
                now = self._clock()
                if (
                    self._last_miss_refresh_at is not None
                    and now - self._last_miss_refresh_at
                    < self.config.jwks_miss_refresh_seconds
                ):
                    return generation
            try:
                refreshed = self._load_generation()
            except _JwksProviderStateError:
                with self._generation_lock:
                    self._last_miss_refresh_at = self._clock()
                return generation
            with self._generation_lock:
                self._generation = refreshed
                self._last_miss_refresh_at = self._clock()
            return refreshed
        finally:
            self._refresh_lock.release()

    def verify_identity(self, token: str) -> VerifiedOidcIdentity:
        if not self._initialized or self._jwt is None or self._jwks_client is None:
            raise OidcError(
                PreBindingOutcome.VERIFIER_UNAVAILABLE,
                internal_detail="production verifier is not initialized",
            )
        header, unverified_claims = _strict_unverified_token(token)
        if _FORBIDDEN_JOSE_HEADERS.intersection(header):
            raise OidcError(internal_detail="unsupported JOSE header")
        algorithm = header.get("alg")
        key_id = header.get("kid")
        if algorithm not in self.config.algorithms:
            raise OidcError(internal_detail="token algorithm differs")
        if (
            type(key_id) is not str
            or not 1 <= len(key_id.encode("ascii", errors="ignore")) <= 255
            or _VISIBLE_ASCII.fullmatch(key_id) is None
        ):
            raise OidcError(internal_detail="token key id is absent or invalid")
        if "typ" in header and header["typ"] not in ("JWT", "at+jwt"):
            raise OidcError(internal_detail="token type differs")
        _numeric_date(unverified_claims, "exp", required=True)
        _numeric_date(unverified_claims, "nbf", required=False)
        _numeric_date(unverified_claims, "iat", required=False)
        verifier_key = self._select_signing_key(key_id, algorithm)
        try:
            claims = self._jwt.decode(
                token,
                verifier_key,
                algorithms=[algorithm],
                audience=self.config.audience,
                issuer=self.config.issuer,
                leeway=self.config.leeway_seconds,
                options={
                    "require": ["exp", "iss", "sub"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "enforce_minimum_key_length": True,
                },
            )
        except self._jwt.exceptions.InvalidTokenError as exc:
            raise OidcError(internal_detail="maintained verifier refused token") from exc
        except Exception as exc:
            raise OidcError(
                PreBindingOutcome.VERIFIER_UNAVAILABLE,
                internal_detail="maintained verifier failed unexpectedly",
            ) from exc
        if type(claims) is not dict or claims != unverified_claims:
            raise OidcError(internal_detail="verified claims representation differs")
        if claims.get("iss") != self.config.issuer:
            raise OidcError(internal_detail="verified issuer differs")
        issuer, subject = _validate_exact_identity(claims.get("iss"), claims.get("sub"))
        return VerifiedOidcIdentity(
            equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
            issuer=issuer,
            subject=subject,
            claims=claims,
        )


class AuthenticationRuntime:
    """Factory facade for immutable, mode-specific authentication runtimes."""

    @classmethod
    def development(cls) -> "AuthenticationRuntime":
        return DevelopmentAuthenticationRuntime()

    @classmethod
    def test(cls, verifier: OidcConfig) -> "AuthenticationRuntime":
        _require_test_verifier(verifier)
        return TestAuthenticationRuntime(
            mode=AuthenticationMode.TEST,
            verifier=verifier,
        )

    @classmethod
    def production(
        cls,
        verifier: ProductionOidcVerifier,
        principal_binding_resolver: PrincipalBindingResolver,
    ) -> "AuthenticationRuntime":
        _require_production_verifier(verifier, allow_test_instance=False)
        _require_production_resolver(principal_binding_resolver)
        return ProductionAuthenticationRuntime(
            verifier=verifier,
            principal_binding_resolver=principal_binding_resolver,
        )

    @classmethod
    def production_for_test(
        cls,
        verifier: ProductionOidcVerifier,
        principal_binding_resolver: PrincipalBindingResolver,
    ) -> "AuthenticationRuntime":
        """Explicit unit-test seam rejected by the production app factory."""

        _require_production_verifier(verifier, allow_test_instance=True)
        return TestAuthenticationRuntime(
            mode=AuthenticationMode.PRODUCTION,
            verifier=verifier,
            principal_binding_resolver=principal_binding_resolver,
        )


def _require_production_verifier(
    verifier: object, *, allow_test_instance: bool
) -> None:
    if type(verifier) is not ProductionOidcVerifier:
        raise AuthenticationStartupError(
            "production requires the sealed ProductionOidcVerifier; "
            "local HS256 and wrapped verifiers are forbidden"
        )
    if not allow_test_instance and not verifier.production_eligible:
        raise AuthenticationStartupError(
            "production requires an internally constructed JWKS client and "
            "monotonic clock; injected trust inputs are test-only"
        )


def _require_test_verifier(verifier: object) -> None:
    if type(verifier) is not OidcConfig:
        raise AuthenticationStartupError(
            "test mode requires the exact local OidcConfig verifier"
        )


def _require_production_resolver(resolver: object) -> None:
    from .principal_binding import PostgreSQLPrincipalBindingResolver

    if type(resolver) is not PostgreSQLPrincipalBindingResolver:
        raise AuthenticationStartupError(
            "production requires the sealed PostgreSQL principal-binding "
            "resolver; wrapped or mutable resolvers are forbidden"
        )


@final
@dataclass(frozen=True, slots=True)
class DevelopmentAuthenticationRuntime(AuthenticationRuntime):
    """Header-only development runtime with no replaceable dependencies."""

    mode: AuthenticationMode = field(
        default=AuthenticationMode.DEVELOPMENT, init=False
    )
    verifier: None = field(default=None, init=False)
    principal_binding_resolver: None = field(default=None, init=False)
    _initialized: bool = field(default=False, init=False, repr=False, compare=False)

    def initialize(self) -> None:
        object.__setattr__(self, "_initialized", True)

    def resolve_principal(
        self,
        *,
        authorization: str | None,
        development_header: str | None,
    ) -> tuple[str, object | None]:
        if not self._initialized:
            raise OidcError(
                PreBindingOutcome.CONFIGURATION_REFUSED,
                internal_detail="authentication runtime is not initialized",
            )
        if type(development_header) is not str or not development_header:
            raise OidcError(PreBindingOutcome.NO_CREDENTIAL)
        return development_header, None


@final
@dataclass(frozen=True, slots=True)
class TestAuthenticationRuntime(AuthenticationRuntime):
    """Test-only runtime, including the production-binding fixture shape."""

    mode: AuthenticationMode
    verifier: OidcVerifier
    principal_binding_resolver: PrincipalBindingResolver | None = None
    _initialized: bool = field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.mode is AuthenticationMode.TEST:
            _require_test_verifier(self.verifier)
            if self.principal_binding_resolver is not None:
                raise AuthenticationStartupError(
                    "test authentication shape is invalid"
                )
        elif self.mode is AuthenticationMode.PRODUCTION:
            _require_production_verifier(
                self.verifier, allow_test_instance=True
            )
            if self.principal_binding_resolver is None:
                raise AuthenticationStartupError(
                    "test production-binding resolver is required"
                )
        else:
            raise AuthenticationStartupError("test authentication mode is invalid")

    def initialize(self) -> None:
        self.verifier.initialize()
        if self.principal_binding_resolver is not None:
            self.principal_binding_resolver.initialize()
        object.__setattr__(self, "_initialized", True)

    def resolve_principal(
        self,
        *,
        authorization: str | None,
        development_header: str | None,
    ) -> tuple[str, object | None]:
        if not self._initialized:
            raise OidcError(
                PreBindingOutcome.CONFIGURATION_REFUSED,
                internal_detail="authentication runtime is not initialized",
            )
        token = _bearer_token(authorization)
        identity = self.verifier.verify_identity(token)
        if self.mode is AuthenticationMode.TEST:
            return identity.subject, identity
        assert self.principal_binding_resolver is not None
        try:
            resolved = self.principal_binding_resolver.resolve(identity)
        except OidcError:
            raise
        except Exception as exc:
            raise OidcError(
                PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
                internal_detail="principal binding resolver refused",
            ) from exc
        party_ref = getattr(resolved, "party_ref", None)
        if type(party_ref) is not str or not party_ref:
            raise OidcError(
                PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
                internal_detail="resolved Party reference is invalid",
            )
        return party_ref, resolved


@final
@dataclass(frozen=True, slots=True)
class ProductionAuthenticationRuntime(AuthenticationRuntime):
    """Sealed production runtime with immutable verifier and resolver bindings."""

    verifier: ProductionOidcVerifier
    principal_binding_resolver: PrincipalBindingResolver
    mode: AuthenticationMode = field(
        default=AuthenticationMode.PRODUCTION, init=False
    )
    _initialized: bool = field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _require_production_verifier(self.verifier, allow_test_instance=False)
        _require_production_resolver(self.principal_binding_resolver)

    def initialize(self) -> None:
        _require_production_verifier(self.verifier, allow_test_instance=False)
        _require_production_resolver(self.principal_binding_resolver)
        self.verifier.initialize()
        self.principal_binding_resolver.initialize()
        object.__setattr__(self, "_initialized", True)

    def resolve_principal(
        self,
        *,
        authorization: str | None,
        development_header: str | None,
    ) -> tuple[str, object | None]:
        if not self._initialized:
            raise OidcError(
                PreBindingOutcome.CONFIGURATION_REFUSED,
                internal_detail="authentication runtime is not initialized",
            )
        identity = self.verifier.verify_identity(_bearer_token(authorization))
        try:
            resolved = self.principal_binding_resolver.resolve(identity)
        except OidcError:
            raise
        except Exception as exc:
            raise OidcError(
                PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
                internal_detail="principal binding resolver refused",
            ) from exc
        party_ref = getattr(resolved, "party_ref", None)
        if type(party_ref) is not str or not party_ref:
            raise OidcError(
                PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
                internal_detail="resolved Party reference is invalid",
            )
        return party_ref, resolved


def _bearer_token(authorization: object) -> str:
    if type(authorization) is not str:
        raise OidcError(PreBindingOutcome.NO_CREDENTIAL)
    pieces = authorization.split(" ")
    if len(pieces) != 2 or pieces[0].lower() != "bearer" or not pieces[1]:
        raise OidcError(PreBindingOutcome.NO_CREDENTIAL)
    return pieces[1]


def issue_dev_token(claims: dict[str, Any], *, secret: str) -> str:
    """Issue a local HS256 fixture token for explicit test mode only."""

    header_b64 = _b64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    payload_b64 = _b64url_encode(
        json.dumps(claims, separators=(",", ":")).encode("utf-8")
    )
    signature = _b64url_encode(
        hmac.new(
            secret.encode("utf-8"),
            f"{header_b64}.{payload_b64}".encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    return f"{header_b64}.{payload_b64}.{signature}"


__all__ = [
    "AuthenticationMode",
    "AuthenticationRuntime",
    "AuthenticationStartupError",
    "DevelopmentAuthenticationRuntime",
    "OidcConfig",
    "OidcError",
    "PreBindingOutcome",
    "ProductionAuthenticationRuntime",
    "ProductionOidcConfig",
    "ProductionOidcVerifier",
    "TestAuthenticationRuntime",
    "VerifiedOidcIdentity",
    "issue_dev_token",
]
