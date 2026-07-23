"""Test-only HS256 token verification for the injected HTTP surface.

Production uses ``ProductionOidcVerifier``; neither path grants authority.
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

# Canonical segments prevent decoder/signature ambiguity (PR #16).
_B64URL_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")


class TestOidcError(Exception):
    """A token was absent, malformed, or failed verification — fail closed."""


def _reject_json_constant(token: str):
    # JSON has no NaN/Infinity; a JWT must not carry them (PR #16 hostile B1)
    raise TestOidcError(f"non-finite JSON constant {token!r} is not allowed in a token")


def _b64url_decode(segment: str) -> bytes:
    if not isinstance(segment, str) or not _B64URL_SEGMENT.match(segment):
        raise TestOidcError("token segment is not canonical unpadded base64url")
    pad = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + pad)
    except (binascii.Error, ValueError) as exc:
        raise TestOidcError(f"malformed base64url segment: {exc}")


def _numeric_date(claims: dict, name: str, *, required: bool):
    """Return a finite, non-boolean JWT NumericDate."""
    value = claims.get(name)
    if value is None:
        if required:
            raise TestOidcError(f"missing {name} claim")
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise TestOidcError(f"invalid {name} claim (must be a finite NumericDate)")
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
    """Verify one development-only compact HS256 token."""
    if not secret:
        raise TestOidcError("no HS256 secret configured; cannot verify")
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise TestOidcError("token is not a well-formed compact JWS (header.payload.signature)")
    header_b64, payload_b64, signature_b64 = parts

    try:
        header = json.loads(_b64url_decode(header_b64), parse_constant=_reject_json_constant)
        claims = json.loads(_b64url_decode(payload_b64), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        # ValueError also covers a non-finite-constant rejection raised inside json
        raise TestOidcError(f"malformed token JSON: {exc}")
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise TestOidcError("token header/payload is not a JSON object")

    # `crit` and RFC 7797 `b64` change JOSE processing; this verifier implements
    # neither and must reject them instead of silently ignoring them (PR #16).
    if "crit" in header:
        raise TestOidcError("unsupported critical JOSE header(s) 'crit' — rejected (no extensions understood)")
    if "b64" in header:
        raise TestOidcError("unsupported JOSE 'b64' header (RFC 7797) — rejected")

    alg = header.get("alg")
    if alg == "none":
        raise TestOidcError("alg=none is rejected (unsigned tokens are never accepted)")
    if alg != "HS256":
        # never silently fall back from another algorithm to HS256
        raise TestOidcError(f"unsupported/mismatched alg {alg!r}; this verifier accepts only HS256")

    expected_sig = _b64url_encode(
        hmac.new(secret.encode("utf-8"), f"{header_b64}.{payload_b64}".encode("ascii"),
                 hashlib.sha256).digest())
    # constant-time comparison (never short-circuit on the signature)
    if not hmac.compare_digest(expected_sig, signature_b64):
        raise TestOidcError("signature verification failed")

    now = int(time.time())
    iss = claims.get("iss")
    if iss != issuer:
        raise TestOidcError(f"issuer {iss!r} is not the configured issuer {issuer!r}")
    aud = claims.get("aud")
    aud_ok = (aud == audience) or (isinstance(aud, list) and audience in aud)
    if not aud_ok:
        raise TestOidcError(f"audience {aud!r} does not include the configured audience {audience!r}")
    exp = _numeric_date(claims, "exp", required=True)
    if now > exp + leeway_seconds:
        raise TestOidcError("token has expired")
    nbf = _numeric_date(claims, "nbf", required=False)
    if nbf is not None and now + leeway_seconds < nbf:
        raise TestOidcError("token is not yet valid (nbf)")
    return claims


@dataclass(frozen=True)
class TestOidcVerifier:
    """Injected HS256 verifier, structurally absent from production."""
    issuer: str
    audience: str
    hs256_secret: str | None = None
    subject_claim: str = "sub"          # the claim carrying the Party id
    roles_claim: str | None = None      # dotted path to role claims, e.g. realm_access.roles
    leeway_seconds: int = 0

    def verify(self, token: str) -> dict:
        """Verify and return the development transport identity."""
        if not isinstance(token, str) or not token.strip():
            raise TestOidcError("no token presented")
        claims = _verify_hs256(
            token,
            secret=self.hs256_secret,
            issuer=self.issuer,
            audience=self.audience,
            leeway_seconds=self.leeway_seconds,
        )

        party_ref = claims.get(self.subject_claim)
        if not isinstance(party_ref, str) or not party_ref:
            raise TestOidcError(f"token carries no usable {self.subject_claim!r} (Party) claim")
        roles = _claim_path(claims, self.roles_claim) if self.roles_claim else None
        if not isinstance(roles, list):
            roles = []
        # roles are RoleAssignment-level only — recorded/recognised, never authority
        return {"partyRef": party_ref, "roles": list(roles), "claims": claims}


def issue_test_token(claims: dict, *, secret: str) -> str:
    """Issue one test-only HS256 token."""
    header_b64 = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"},
                                           separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    signature = _b64url_encode(
        hmac.new(secret.encode("utf-8"), f"{header_b64}.{payload_b64}".encode("ascii"),
                 hashlib.sha256).digest())
    return f"{header_b64}.{payload_b64}.{signature}"
