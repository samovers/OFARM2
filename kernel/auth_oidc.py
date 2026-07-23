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
from urllib.parse import urlsplit

from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TenantCapabilityContractError,
    validate_oidc_issuer,
)


_B64URL_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")
_OIDC_SUBJECT = re.compile(r"^[!-~]{1,255}$")
_VISIBLE_ASCII = re.compile(r"^[!-~]+$")
_MAX_JWT_BYTES = 16_384
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
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
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
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise OidcError(internal_detail=f"invalid {name}")
    return int(value)


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
    issuer: str
    audience: str
    jwks_url: str
    algorithms: tuple[str, ...] = ("RS256",)
    leeway_seconds: int = 0
    jwks_lifespan_seconds: int = 300
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
        if type(self.timeout_seconds) is not int or not 1 <= self.timeout_seconds <= 30:
            raise AuthenticationStartupError("production JWKS timeout is invalid")


class _JwksProviderStateError(RuntimeError):
    """A provider fetch or key-set state cannot safely verify credentials."""


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

    def __init__(
        self,
        config: ProductionOidcConfig,
        *,
        jwks_client: object | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self.config = config
        self._jwks_client = jwks_client
        self._clock = time.monotonic if clock is None else clock
        self._jwt: Any | None = None
        self._generation: _ValidatedJwksGeneration | None = None
        self._generation_lock = Lock()
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def initialize(self) -> None:
        self._initialized = False
        self._generation = None
        self.config.validate()
        try:
            import jwt
        except ImportError as exc:
            raise AuthenticationStartupError(
                "production OIDC verifier dependency is unavailable"
            ) from exc
        self._jwt = jwt
        if self._jwks_client is None:
            self._jwks_client = jwt.PyJWKClient(
                self.config.jwks_url,
                cache_keys=False,
                cache_jwk_set=True,
                lifespan=self.config.jwks_lifespan_seconds,
                timeout=self.config.timeout_seconds,
            )
        try:
            with self._generation_lock:
                self._generation = self._load_generation()
        except _JwksProviderStateError as exc:
            raise AuthenticationStartupError(
                "production OIDC JWKS initialization failed"
            ) from exc
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
            algorithm = getattr(key, "algorithm_name", None)
            key_id = getattr(key, "key_id", None)
            verifier_key = getattr(key, "key", None)
            if algorithm not in self.config.algorithms:
                continue
            if (
                type(key_id) is not str
                or _VISIBLE_ASCII.fullmatch(key_id) is None
                or not 1 <= len(key_id.encode("ascii")) <= 255
                or verifier_key is None
            ):
                continue
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

    def _select_signing_key(self, key_id: str, algorithm: str) -> object:
        try:
            with self._generation_lock:
                generation = self._generation
                refreshed = False
                if (
                    generation is None
                    or self._clock() - generation.loaded_at
                    >= self.config.jwks_lifespan_seconds
                ):
                    generation = self._load_generation()
                    self._generation = generation
                    refreshed = True
                selected = generation.select(key_id, algorithm)
                if selected is None and not refreshed:
                    generation = self._load_generation()
                    self._generation = generation
                    selected = generation.select(key_id, algorithm)
        except _JwksProviderStateError as exc:
            raise OidcError(
                PreBindingOutcome.VERIFIER_UNAVAILABLE,
                internal_detail="JWKS provider state is unavailable",
            ) from exc
        if selected is None:
            raise OidcError(internal_detail="no matching JWKS signing key")
        return selected

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


@dataclass(slots=True)
class AuthenticationRuntime:
    """One explicit mode and only the dependencies permitted in that mode."""

    mode: AuthenticationMode
    verifier: OidcVerifier | None = None
    principal_binding_resolver: PrincipalBindingResolver | None = None
    _initialized: bool = field(default=False, init=False, repr=False)

    @classmethod
    def development(cls) -> "AuthenticationRuntime":
        return cls(AuthenticationMode.DEVELOPMENT)

    @classmethod
    def test(cls, verifier: OidcConfig) -> "AuthenticationRuntime":
        cls._require_test_verifier(verifier)
        return cls(AuthenticationMode.TEST, verifier=verifier)

    @classmethod
    def production(
        cls,
        verifier: ProductionOidcVerifier,
        principal_binding_resolver: PrincipalBindingResolver,
    ) -> "AuthenticationRuntime":
        cls._require_production_verifier(verifier)
        return cls(
            AuthenticationMode.PRODUCTION,
            verifier=verifier,
            principal_binding_resolver=principal_binding_resolver,
        )

    @staticmethod
    def _require_production_verifier(verifier: object) -> None:
        if type(verifier) is not ProductionOidcVerifier:
            raise AuthenticationStartupError(
                "production requires the sealed ProductionOidcVerifier; "
                "local HS256 and wrapped verifiers are forbidden"
            )

    @staticmethod
    def _require_test_verifier(verifier: object) -> None:
        if type(verifier) is not OidcConfig:
            raise AuthenticationStartupError(
                "test mode requires the exact local OidcConfig verifier"
            )

    def initialize(self) -> None:
        if self.mode is AuthenticationMode.DEVELOPMENT:
            if self.verifier is not None or self.principal_binding_resolver is not None:
                raise AuthenticationStartupError(
                    "development mode cannot contain production authentication dependencies"
                )
        elif self.mode is AuthenticationMode.TEST:
            if self.verifier is None or self.principal_binding_resolver is not None:
                raise AuthenticationStartupError("test authentication shape is invalid")
            self._require_test_verifier(self.verifier)
            self.verifier.initialize()
        elif self.mode is AuthenticationMode.PRODUCTION:
            if self.verifier is None or self.principal_binding_resolver is None:
                raise AuthenticationStartupError(
                    "production verifier and principal-binding resolver are required"
                )
            self._require_production_verifier(self.verifier)
            self.verifier.initialize()
            self.principal_binding_resolver.initialize()
        else:
            raise AuthenticationStartupError("authentication mode is invalid")
        self._initialized = True

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
        if self.mode is AuthenticationMode.DEVELOPMENT:
            if type(development_header) is not str or not development_header:
                raise OidcError(PreBindingOutcome.NO_CREDENTIAL)
            return development_header, None
        token = _bearer_token(authorization)
        assert self.verifier is not None
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
    "OidcConfig",
    "OidcError",
    "PreBindingOutcome",
    "ProductionOidcConfig",
    "ProductionOidcVerifier",
    "VerifiedOidcIdentity",
    "issue_dev_token",
]
