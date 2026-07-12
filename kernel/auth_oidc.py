"""OIDC principal verification (M2 G4) — a PLUGGABLE, fail-closed verifier that
turns a bearer token into a Party transport principal.

POSTURE (decided, not a production claim): this build ships a zero-dependency
HS256 verifier for the DEVELOPMENT / CONFORMANCE OIDC path only. Production
RS256 / JWKS (Keycloak) verification is a deliberate `NotImplemented` path — the
boundary is executable and obvious, never a silent fallback. The HTTP surface
remains a development/conformance surface, not a production-authenticated runtime
(see profile_si_ffs/UNSUPPORTED_SURFACES.md). No PyJWT / jose / cryptography /
authlib dependency is introduced.

Authority is unchanged by this module: a verified token yields a Party id (the
transport principal) and, separately, any role claims — but roles map to
`RoleAssignment` only and NEVER synthesize authority. Authority still comes solely
from AuthorityGrant / DelegationGrant / SharingGrant (kernel/authority.py, D4).
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
from dataclasses import dataclass

# compact-JWS segments are UNPADDED base64url — strictly this alphabet, no "="
# padding, no other characters. Enforcing canonical form before decode keeps the
# verifier fail-closed: a non-canonical segment is rejected even if it would
# otherwise decode (base64 decoders silently drop stray characters) and even if it
# was signed over that exact mutated segment (PR #16 hostile B2).
_B64URL_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")


class OidcError(Exception):
    """A token was absent, malformed, or failed verification — fail closed."""


_RETAINED_OIDC_ERROR_TYPE = OidcError


def _reject_json_constant(token: str):
    # JSON has no NaN/Infinity; a JWT must not carry them (PR #16 hostile B1)
    raise OidcError(f"non-finite JSON constant {token!r} is not allowed in a token")


def _b64url_decode(segment: str) -> bytes:
    if not isinstance(segment, str) or not _B64URL_SEGMENT.match(segment):
        raise OidcError("token segment is not canonical unpadded base64url")
    pad = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + pad)
    except (binascii.Error, ValueError) as exc:
        raise OidcError(f"malformed base64url segment: {exc}")


def _numeric_date(claims: dict, name: str, *, required: bool):
    """A JWT NumericDate carried in a portable signed-64-bit epoch range.

    JSON integers are arbitrary precision in Python, while ``math.isfinite``
    first converts them to a C double and can raise ``OverflowError``.  Reject
    values outside the portable range explicitly so malformed signed tokens
    always fail as ``OidcError`` rather than escaping the verifier as a 500.
    """
    value = claims.get(name)
    if value is None:
        if required:
            raise OidcError(f"missing {name} claim")
        return None
    minimum = -(1 << 63)
    maximum = (1 << 63) - 1
    valid_integer = type(value) is int and minimum <= value <= maximum
    valid_float = (
        type(value) is float
        and math.isfinite(value)
        and minimum <= value <= maximum
    )
    if not (valid_integer or valid_float):
        raise OidcError(
            f"invalid {name} claim (must be a finite signed-64-bit NumericDate)")
    return int(value)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _claim_path(claims: dict, path: str):
    """Resolve a dotted claim path (e.g. realm_access.roles), or None."""
    node = claims
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _verify_hs256(token: str, *, secret: str, issuer: str, audience: str,
                  leeway_seconds: int = 0) -> dict:
    """Verify a compact-JWS HS256 token, fail-closed. Rejects alg=none /
    non-HS256, missing/short structure, malformed base64url or JSON, a bad or
    missing signature (constant-time compare), and missing/invalid iss / aud /
    exp (and nbf if present). Returns the decoded claims on success."""
    if not secret:
        raise OidcError("no HS256 secret configured; cannot verify")
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise OidcError("token is not a well-formed compact JWS (header.payload.signature)")
    header_b64, payload_b64, signature_b64 = parts

    try:
        header = json.loads(
            _RETAINED_B64URL_DECODE(header_b64),
            parse_constant=_RETAINED_REJECT_JSON_CONSTANT,
        )
        claims = json.loads(
            _RETAINED_B64URL_DECODE(payload_b64),
            parse_constant=_RETAINED_REJECT_JSON_CONSTANT,
        )
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        # ValueError also covers a non-finite-constant rejection raised inside json
        raise OidcError(f"malformed token JSON: {exc}")
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise OidcError("token header/payload is not a JSON object")

    # This minimal verifier understands NO critical JOSE header extensions, so any
    # `crit` (RFC 7515 §4.1.11) must be rejected, and `b64` (RFC 7797 — unencoded
    # payload, which would change the signing input) is unsupported. Fail closed
    # rather than ignore them (PR #16 hostile B1), e.g. {"b64": false, "crit": ["b64"]}.
    if "crit" in header:
        raise OidcError("unsupported critical JOSE header(s) 'crit' — rejected (no extensions understood)")
    if "b64" in header:
        raise OidcError("unsupported JOSE 'b64' header (RFC 7797) — rejected")

    alg = header.get("alg")
    if alg == "none":
        raise OidcError("alg=none is rejected (unsigned tokens are never accepted)")
    if alg != "HS256":
        # never silently fall back from another algorithm to HS256
        raise OidcError(f"unsupported/mismatched alg {alg!r}; this verifier accepts only HS256")

    expected_sig = _RETAINED_B64URL_ENCODE(
        hmac.new(secret.encode("utf-8"), f"{header_b64}.{payload_b64}".encode("ascii"),
                 hashlib.sha256).digest())
    # constant-time comparison (never short-circuit on the signature)
    if not hmac.compare_digest(expected_sig, signature_b64):
        raise OidcError("signature verification failed")

    now = int(time.time())
    iss = claims.get("iss")
    if iss != issuer:
        raise OidcError(f"issuer {iss!r} is not the configured issuer {issuer!r}")
    aud = claims.get("aud")
    aud_ok = (aud == audience) or (isinstance(aud, list) and audience in aud)
    if not aud_ok:
        raise OidcError(f"audience {aud!r} does not include the configured audience {audience!r}")
    exp = _RETAINED_NUMERIC_DATE(claims, "exp", required=True)
    if now > exp + leeway_seconds:
        raise OidcError("token has expired")
    nbf = _RETAINED_NUMERIC_DATE(claims, "nbf", required=False)
    if nbf is not None and now + leeway_seconds < nbf:
        raise OidcError("token is not yet valid (nbf)")
    return claims


_RETAINED_REJECT_JSON_CONSTANT = _reject_json_constant
_RETAINED_REJECT_JSON_CONSTANT_CODE = _RETAINED_REJECT_JSON_CONSTANT.__code__
_RETAINED_B64URL_DECODE = _b64url_decode
_RETAINED_B64URL_DECODE_CODE = _RETAINED_B64URL_DECODE.__code__
_RETAINED_NUMERIC_DATE = _numeric_date
_RETAINED_NUMERIC_DATE_CODE = _RETAINED_NUMERIC_DATE.__code__
_RETAINED_B64URL_ENCODE = _b64url_encode
_RETAINED_B64URL_ENCODE_CODE = _RETAINED_B64URL_ENCODE.__code__
_RETAINED_CLAIM_PATH = _claim_path
_RETAINED_CLAIM_PATH_CODE = _RETAINED_CLAIM_PATH.__code__
_RETAINED_VERIFY_HS256 = _verify_hs256
_RETAINED_VERIFY_HS256_CODE = _RETAINED_VERIFY_HS256.__code__
_OIDC_HELPER_ANCHORS = (
    (("_reject_json_constant", "_RETAINED_REJECT_JSON_CONSTANT"),
     _RETAINED_REJECT_JSON_CONSTANT,
     _RETAINED_REJECT_JSON_CONSTANT_CODE),
    (("_b64url_decode", "_RETAINED_B64URL_DECODE"),
     _RETAINED_B64URL_DECODE,
     _RETAINED_B64URL_DECODE_CODE),
    (("_numeric_date", "_RETAINED_NUMERIC_DATE"),
     _RETAINED_NUMERIC_DATE, _RETAINED_NUMERIC_DATE_CODE),
    (("_b64url_encode", "_RETAINED_B64URL_ENCODE"),
     _RETAINED_B64URL_ENCODE,
     _RETAINED_B64URL_ENCODE_CODE),
    (("_claim_path", "_RETAINED_CLAIM_PATH"),
     _RETAINED_CLAIM_PATH, _RETAINED_CLAIM_PATH_CODE),
    (("_verify_hs256", "_RETAINED_VERIFY_HS256"),
     _RETAINED_VERIFY_HS256,
     _RETAINED_VERIFY_HS256_CODE),
)


@dataclass(frozen=True, slots=True)
class OidcConfig:
    """A pluggable verifier config. `algorithm` selects the verification path;
    RS256 / JWKS is a deliberate NotImplemented production path."""
    issuer: str
    audience: str
    algorithm: str = "HS256"
    hs256_secret: str | None = None
    subject_claim: str = "sub"          # the claim carrying the Party id
    roles_claim: str | None = None      # dotted path to role claims, e.g. realm_access.roles
    leeway_seconds: int = 0

    def __post_init__(self) -> None:
        exact_strings = {
            "issuer": self.issuer,
            "audience": self.audience,
            "algorithm": self.algorithm,
            "subject_claim": self.subject_claim,
        }
        if any(type(value) is not str or not value
               for value in exact_strings.values()):
            raise TypeError(
                "OIDC issuer, audience, algorithm, and subject claim must be "
                "non-empty exact strings")
        if self.algorithm not in {"HS256", "RS256", "JWKS"}:
            raise ValueError("OIDC algorithm is not a supported closed value")
        if (self.hs256_secret is not None
                and type(self.hs256_secret) is not str):
            raise TypeError("OIDC HS256 secret must be None or an exact string")
        if (self.roles_claim is not None
                and (type(self.roles_claim) is not str
                     or not self.roles_claim)):
            raise TypeError(
                "OIDC roles claim must be None or a non-empty exact string")
        if (type(self.leeway_seconds) is not int
                or self.leeway_seconds < 0):
            raise TypeError(
                "OIDC leeway must be a non-negative exact integer")

    def verify(self, token: str) -> dict:
        """Verify the token and return {partyRef, roles, claims}. Raises OidcError
        on any failure (fail closed). `partyRef` is the Party transport principal;
        `roles` are recognised RoleAssignment-level roles that NEVER grant authority."""
        _RETAINED_OIDC_RUNTIME_GUARD(self)
        if not isinstance(token, str) or not token.strip():
            raise OidcError("no token presented")
        if self.algorithm == "HS256":
            claims = _RETAINED_VERIFY_HS256(
                token,
                secret=self.hs256_secret,
                issuer=self.issuer,
                audience=self.audience,
                leeway_seconds=self.leeway_seconds,
            )
        elif self.algorithm in ("RS256", "JWKS"):
            raise OidcError(
                "RS256 / JWKS (Keycloak) production verification is not implemented in "
                "this development/conformance build (see UNSUPPORTED_SURFACES.md); "
                "there is no fallback to HS256")
        else:
            raise OidcError(f"unsupported verifier algorithm {self.algorithm!r}")

        party_ref = claims.get(self.subject_claim)
        if not isinstance(party_ref, str) or not party_ref:
            raise OidcError(f"token carries no usable {self.subject_claim!r} (Party) claim")
        roles = (
            _RETAINED_CLAIM_PATH(claims, self.roles_claim)
            if self.roles_claim else None
        )
        if not isinstance(roles, list):
            roles = []
        # roles are RoleAssignment-level only — recorded/recognised, never authority
        result = {"partyRef": party_ref, "roles": list(roles), "claims": claims}
        _RETAINED_OIDC_RUNTIME_GUARD(self)
        return result


_RETAINED_OIDC_VERIFY = OidcConfig.verify
_RETAINED_OIDC_VERIFY_CODE = _RETAINED_OIDC_VERIFY.__code__
_RETAINED_OIDC_POST_INIT = OidcConfig.__post_init__
_RETAINED_OIDC_POST_INIT_CODE = _RETAINED_OIDC_POST_INIT.__code__


def _require_oidc_runtime(config) -> None:
    if (type(config) is not OidcConfig
            or globals().get("OidcError") is not _RETAINED_OIDC_ERROR_TYPE
            or vars(OidcConfig).get("verify") is not _RETAINED_OIDC_VERIFY
            or _RETAINED_OIDC_VERIFY.__code__ is not _RETAINED_OIDC_VERIFY_CODE
            or vars(OidcConfig).get("__post_init__") is not
            _RETAINED_OIDC_POST_INIT
            or _RETAINED_OIDC_POST_INIT.__code__ is not
            _RETAINED_OIDC_POST_INIT_CODE
            or globals().get("_require_oidc_runtime") is not
            _RETAINED_OIDC_RUNTIME_GUARD
            or _RETAINED_OIDC_RUNTIME_GUARD.__code__ is not
            _RETAINED_OIDC_RUNTIME_GUARD_CODE
            or any(
                any(globals().get(name) is not function for name in names)
                or function.__code__ is not code
                for names, function, code in _OIDC_HELPER_ANCHORS)):
        raise OidcError("OIDC verifier runtime composition changed")


_RETAINED_OIDC_RUNTIME_GUARD = _require_oidc_runtime
_RETAINED_OIDC_RUNTIME_GUARD_CODE = _require_oidc_runtime.__code__


def issue_dev_token(claims: dict, *, secret: str) -> str:
    """Issue an HS256 token for the DEVELOPMENT / CONFORMANCE flow (a stand-in for
    a real IdP, which the production RS256/JWKS path will replace). NOT a security
    boundary — only the verifier is. Used by conformance tests and local dev."""
    header_b64 = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"},
                                           separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    signature = _b64url_encode(
        hmac.new(secret.encode("utf-8"), f"{header_b64}.{payload_b64}".encode("ascii"),
                 hashlib.sha256).digest())
    return f"{header_b64}.{payload_b64}.{signature}"
