"""Fail-closed tenant context and issuer-storage contract for issue #174.

Issue #174 supplies protected transaction-context and principal-storage
primitives.  It deliberately supplies no production TenantCapability wire
format, cryptographic algorithm, verifier, signer, key custody, or key
schedule.  Those decisions and the forward migration that introduces a
production binder belong to issue #172.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass


TENANT_CONTEXT_CONTRACT_DIGEST_POLICY = "OFARM_POSTGRESQL_TENANT_CONTEXT_POSTURE_V1"
OIDC_ISSUER_EQUALITY_POLICY = "OIDC_EXACT_UTF8_V1"
OIDC_ISSUER_GRAMMAR_POLICY = "OFARM_OIDC_ISSUER_ASCII_HTTPS_V1"
OIDC_ISSUER_MAX_BYTES = 2048

_CONTRACT_DIGEST_DOMAIN = (
    TENANT_CONTEXT_CONTRACT_DIGEST_POLICY.encode("ascii") + b"\x00"
)
_HOST_LABEL = re.compile(r"[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
_PORT = re.compile(r"[0-9]{1,5}")
_PATH = re.compile(r"/[A-Za-z0-9._~!$&()*+,;=:@%/-]*")


# These vectors are the single checked-in cross-layer examples.  Pure Python
# and live PostgreSQL tests consume the same tuples.
OIDC_ISSUER_VALID_VECTORS = (
    "https://issuer.example.test",
    "https://issuer.example.test/tenant",
    "https://issuer.example.test:443/tenant/v1",
    "https://localhost",
    "https://127.0.0.1:8443/oidc",
)
OIDC_ISSUER_INVALID_VECTORS = (
    "",
    "http://issuer.example.test",
    "https://",
    "https://issuer.example.test?query=1",
    "https://issuer.example.test#fragment",
    "https://user@issuer.example.test",
    "https://issuer.example.test:0",
    "https://issuer.example.test:65536",
    "https://issuer.example.test:70000",
    "https://issuer.example.test:not-a-port",
    "https://[invalid",
    "https://[2001:db8::1]",
    "https://-issuer.example.test",
    "https://issuer-.example.test",
    "https://issuer..example.test",
    "https://issuer.example.test.",
    "https://issuer.example.test/white space",
    "https://issuer.example.test/path\\segment",
    "https://issuer.example.test/ž",
)


class TenantContextContractError(ValueError):
    """The fail-closed posture or issuer policy is not exact."""


@dataclass(frozen=True, slots=True)
class ContextRoutineSignature:
    """One exact issue-#174 transaction-context routine identity."""

    name: str
    argument_types: tuple[str, ...]

    @property
    def identity_arguments(self) -> str:
        return ",".join(self.argument_types)

    @property
    def identity(self) -> str:
        return f"ofarm.{self.name}({self.identity_arguments})"

    def manifest(self) -> dict[str, object]:
        return {
            "schema": "ofarm",
            "name": self.name,
            "argumentTypes": list(self.argument_types),
            "identity": self.identity,
        }


TENANT_CONTEXT_ROUTINE_SIGNATURES = (
    ContextRoutineSignature("create_tenant_challenge", ()),
    ContextRoutineSignature("current_tenant_id", ()),
    ContextRoutineSignature("take_tenant_write_lock", ()),
)


@dataclass(frozen=True, slots=True)
class TenantContextContract:
    """Canonical declaration that production binding is unavailable in #174."""

    identity: str
    issuer_equality_policy: str
    issuer_grammar_policy: str
    context_routines: tuple[ContextRoutineSignature, ...]

    def manifest_without_digest(self) -> dict[str, object]:
        return {
            "schemaVersion": "ofarm.postgresql-tenant-context-posture.v1",
            "digestPolicy": TENANT_CONTEXT_CONTRACT_DIGEST_POLICY,
            "identity": self.identity,
            "productionBinding": {
                "available": False,
                "deferredIssue": 172,
                "forwardMigrationRequired": True,
                "cryptographicContract": None,
                "wireContract": None,
                "verificationKeyCustody": None,
                "reason": (
                    "issue #174 supplies no accepted production verifier or "
                    "binder"
                ),
            },
            "issuerPolicy": {
                "equalityPolicy": self.issuer_equality_policy,
                "grammarPolicy": self.issuer_grammar_policy,
                "encoding": "visible-ascii-subset-of-utf8",
                "scheme": "https",
                "host": (
                    "one or more dot-separated 1-63 byte ASCII labels; each "
                    "starts and ends alphanumeric with internal hyphen allowed"
                ),
                "hostMaximumBytes": 253,
                "port": "optional decimal integer in [1,65535]",
                "path": (
                    "optional slash-prefixed RFC3986 visible-ASCII pchar/slash "
                    "subset; query, fragment, userinfo, backslash, and percent "
                    "decoding are not accepted"
                ),
                "maximumBytes": OIDC_ISSUER_MAX_BYTES,
                "comparison": "exact case-sensitive bytes",
            },
            "contextRoutines": [
                routine.manifest() for routine in self.context_routines
            ],
            "claimBoundary": (
                "issuer storage equality and fail-closed transaction-context "
                "primitives only; no production capability, binder, signer, "
                "verifier, algorithm, framing, key custody, or key schedule"
            ),
        }

    def canonical_manifest_without_digest_bytes(self) -> bytes:
        return _canonical_json(self.manifest_without_digest())

    @property
    def digest(self) -> str:
        source = _CONTRACT_DIGEST_DOMAIN + self.canonical_manifest_without_digest_bytes()
        return "sha256:" + hashlib.sha256(source).hexdigest()

    def manifest(self) -> dict[str, object]:
        value = self.manifest_without_digest()
        value["tenantContextContractDigest"] = self.digest
        return value

    def canonical_manifest_bytes(self) -> bytes:
        return _canonical_json(self.manifest())


TENANT_CONTEXT_CONTRACT = TenantContextContract(
    identity="ofarm.tenant-context-fail-closed-posture.v1",
    issuer_equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
    issuer_grammar_policy=OIDC_ISSUER_GRAMMAR_POLICY,
    context_routines=TENANT_CONTEXT_ROUTINE_SIGNATURES,
)


def valid_oidc_issuer(value: object) -> bool:
    """Return whether *value* satisfies the exact V1 storage grammar."""

    if type(value) is not str:
        return False
    try:
        encoded = value.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        return False
    if not 1 <= len(encoded) <= OIDC_ISSUER_MAX_BYTES:
        return False
    if not value.startswith("https://"):
        return False

    authority_and_path = value[len("https://") :]
    if "/" in authority_and_path:
        authority, path_suffix = authority_and_path.split("/", 1)
        path = "/" + path_suffix
    else:
        authority = authority_and_path
        path = ""
    if not authority or "@" in authority or authority.count(":") > 1:
        return False
    if path and _PATH.fullmatch(path) is None:
        return False

    if ":" in authority:
        host, port_text = authority.rsplit(":", 1)
        if _PORT.fullmatch(port_text) is None:
            return False
        port = int(port_text)
        if not 1 <= port <= 65535:
            return False
    else:
        host = authority

    if not 1 <= len(host) <= 253:
        return False
    labels = host.split(".")
    return all(_HOST_LABEL.fullmatch(label) is not None for label in labels)


def validate_oidc_issuer(value: object) -> str:
    """Return exact issuer text or raise when its storage grammar differs."""

    if not valid_oidc_issuer(value):
        raise TenantContextContractError(
            f"issuer must satisfy {OIDC_ISSUER_GRAMMAR_POLICY}"
        )
    assert isinstance(value, str)
    return value


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def _validate_checked_in_contract() -> None:
    contract = TENANT_CONTEXT_CONTRACT
    if (
        contract.issuer_equality_policy != OIDC_ISSUER_EQUALITY_POLICY
        or contract.issuer_grammar_policy != OIDC_ISSUER_GRAMMAR_POLICY
        or contract.context_routines != TENANT_CONTEXT_ROUTINE_SIGNATURES
        or any(not valid_oidc_issuer(value) for value in OIDC_ISSUER_VALID_VECTORS)
        or any(valid_oidc_issuer(value) for value in OIDC_ISSUER_INVALID_VECTORS)
    ):
        raise TenantContextContractError(
            "checked-in tenant context posture is internally inconsistent"
        )


_validate_checked_in_contract()


__all__ = [
    "OIDC_ISSUER_EQUALITY_POLICY",
    "OIDC_ISSUER_GRAMMAR_POLICY",
    "OIDC_ISSUER_INVALID_VECTORS",
    "OIDC_ISSUER_MAX_BYTES",
    "OIDC_ISSUER_VALID_VECTORS",
    "TENANT_CONTEXT_CONTRACT",
    "TENANT_CONTEXT_CONTRACT_DIGEST_POLICY",
    "TENANT_CONTEXT_ROUTINE_SIGNATURES",
    "ContextRoutineSignature",
    "TenantContextContract",
    "TenantContextContractError",
    "valid_oidc_issuer",
    "validate_oidc_issuer",
]
