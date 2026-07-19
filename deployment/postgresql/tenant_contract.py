"""Frozen tenant capability and PostgreSQL binder contract for issue #174.

This module performs no I/O and contains no verification key.  It fixes the
exact bytes that the trusted issuer and database binder must share.  The HMAC
helper exists only for cross-layer golden vectors; it is not a signer or key
store.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import unicodedata
import urllib.parse
import uuid
from dataclasses import dataclass


TENANT_CAPABILITY_CONTRACT_DIGEST_POLICY = (
    "OFARM_POSTGRESQL_TENANT_CAPABILITY_CONTRACT_V1"
)
TENANT_CAPABILITY_VERSION = "OFARM_TENANT_CAPABILITY_V1"
TENANT_CAPABILITY_DOMAIN_IDENTIFIER = TENANT_CAPABILITY_VERSION
TENANT_CAPABILITY_DOMAIN = (
    TENANT_CAPABILITY_DOMAIN_IDENTIFIER.encode("ascii") + b"\x00"
)
TENANT_BINDER_AUDIENCE = "OFARM_TENANT_BINDER_V1"
TENANT_CAPABILITY_MAC_ALGORITHM = "HMAC-SHA-256"
TENANT_CAPABILITY_EQUALITY_POLICY = "OIDC_EXACT_UTF8_V1"
TENANT_CAPABILITY_BOUNDS_POLICY = "OFARM_TENANT_CAPABILITY_BOUNDS_V1"
TENANT_CAPABILITY_KEY_ROW_POLICY = "OFARM_TENANT_CAPABILITY_KEY_ROW_V1"
TENANT_CAPABILITY_ASCII_ID_POLICY = "OFARM_ASCII_ID_V1"
TENANT_CAPABILITY_MAX_TTL_MICROSECONDS = 60_000_000
TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS = 5_000_000
TENANT_CAPABILITY_KEY_BYTES = 32
TENANT_CAPABILITY_MAC_BYTES = 32

_CONTRACT_DIGEST_DOMAIN = (
    TENANT_CAPABILITY_CONTRACT_DIGEST_POLICY.encode("ascii") + b"\x00"
)
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1
_ASCII_ID = re.compile(r"[A-Za-z0-9._:-]{1,255}")
_SUBJECT = re.compile(r"[!-~]{1,255}")
_PARTY_RECORD_KIND = "ofarm.party.v0.1"


class TenantCapabilityContractError(ValueError):
    """A capability value or checked-in contract is not exact."""


@dataclass(frozen=True, slots=True)
class TenantCapability:
    """The exact V1 MAC fields, excluding the MAC itself."""

    challenge_id: uuid.UUID
    audience: str
    key_id: str
    equality_policy: str
    issuer: str
    subject: str
    binding_version_id: uuid.UUID
    binding_version_digest: bytes
    lifecycle_head_id: uuid.UUID
    lifecycle_head_digest: bytes
    tenant_id: uuid.UUID
    tenant_registration_digest: bytes
    party_ref: str
    party_record_kind: str
    party_record_id: str
    party_schema_digest: bytes
    party_payload_digest: bytes
    issued_at_unix_microseconds: int
    not_before_unix_microseconds: int
    expires_at_unix_microseconds: int
    nonce: uuid.UUID


@dataclass(frozen=True, slots=True)
class BinderRoutineSignature:
    """One exact core-type PostgreSQL routine identity."""

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


_BINDER_ARGUMENT_TYPES = (
    "uuid",
    "text",
    "text",
    "text",
    "text",
    "text",
    "uuid",
    "bytea",
    "uuid",
    "bytea",
    "uuid",
    "bytea",
    "text",
    "text",
    "text",
    "bytea",
    "bytea",
    "bigint",
    "bigint",
    "bigint",
    "uuid",
    "bytea",
)

TENANT_BINDER_ROUTINE_SIGNATURES = (
    BinderRoutineSignature("create_tenant_challenge", ()),
    BinderRoutineSignature("bind_tenant_capability", _BINDER_ARGUMENT_TYPES),
    BinderRoutineSignature("current_tenant_id", ()),
    BinderRoutineSignature("take_tenant_write_lock", ()),
)

_FRAMING = (
    ("challengeId", "uuid", "lp32(uuid-rfc4122-network-order-16)"),
    ("audience", "text", "lp32(ascii)"),
    ("keyId", "text", "lp32(ascii)"),
    ("equalityPolicy", "text", "lp32(ascii)"),
    ("issuer", "text", "lp32(utf8)"),
    ("subject", "text", "lp32(utf8)"),
    ("bindingVersionId", "uuid", "lp32(uuid-rfc4122-network-order-16)"),
    ("bindingVersionDigest", "bytea", "lp32(raw-sha256-32)"),
    ("lifecycleHeadId", "uuid", "lp32(uuid-rfc4122-network-order-16)"),
    ("lifecycleHeadDigest", "bytea", "lp32(raw-sha256-32)"),
    ("tenantId", "uuid", "lp32(uuid-rfc4122-network-order-16)"),
    ("tenantRegistrationDigest", "bytea", "lp32(raw-sha256-32)"),
    ("partyRef", "text", "lp32(ascii-id)"),
    ("partyRecordKind", "text", "lp32(ascii-id)"),
    ("partyRecordId", "text", "lp32(ascii-id)"),
    ("partySchemaDigest", "bytea", "lp32(raw-sha256-32)"),
    ("partyPayloadDigest", "bytea", "lp32(raw-sha256-32)"),
    ("issuedAtUnixMicroseconds", "bigint", "lp32(int64-signed-big-endian)"),
    ("notBeforeUnixMicroseconds", "bigint", "lp32(int64-signed-big-endian)"),
    ("expiresAtUnixMicroseconds", "bigint", "lp32(int64-signed-big-endian)"),
    ("nonce", "uuid", "lp32(uuid-rfc4122-network-order-16)"),
)


@dataclass(frozen=True, slots=True)
class TenantCapabilityContract:
    """Canonical, non-secret manifest of the V1 capability boundary."""

    identity: str
    capability_version: str
    audience: str
    equality_policy: str
    bounds_policy: str
    key_row_policy: str
    routines: tuple[BinderRoutineSignature, ...]

    def manifest_without_digest(self) -> dict[str, object]:
        return {
            "schemaVersion": "ofarm.postgresql-tenant-capability-contract.v1",
            "digestPolicy": TENANT_CAPABILITY_CONTRACT_DIGEST_POLICY,
            "identity": self.identity,
            "capability": {
                "version": self.capability_version,
                "versionCarriedAsField": False,
                "audience": self.audience,
                "equalityPolicy": self.equality_policy,
                "boundsPolicy": self.bounds_policy,
                "mac": {
                    "algorithm": TENANT_CAPABILITY_MAC_ALGORITHM,
                    "domainIdentifier": TENANT_CAPABILITY_DOMAIN_IDENTIFIER,
                    "domainAscii": TENANT_CAPABILITY_DOMAIN_IDENTIFIER + "\x00",
                    "domainTerminatorHex": "00",
                    "macBytes": TENANT_CAPABILITY_MAC_BYTES,
                    "macFieldIncludedInInput": False,
                },
                "frameDefinitions": {
                    "concatenation": (
                        "domain bytes followed by each lp32 framing entry in "
                        "listed order with no separator, tag, or field count"
                    ),
                    "lp32": {
                        "length": "unsigned-32-bit-big-endian",
                        "lengthMeasures": "encoded-octets",
                        "value": "exact-encoded-octets",
                        "appliesToEveryField": True,
                    },
                    "uuid": {
                        "bytes": 16,
                        "encoding": "RFC-4122-network-byte-order/uuid_send",
                    },
                    "sha256": {"bytes": 32, "encoding": "raw-digest-bytes"},
                    "int64": {
                        "bytes": 8,
                        "encoding": "signed-twos-complement-big-endian",
                        "unit": "UTC-microseconds-since-Unix-epoch",
                    },
                },
                "framing": [
                    {"field": name, "sqlType": sql_type, "frame": frame}
                    for name, sql_type, frame in _FRAMING
                ],
                "limits": {
                    "maximumTtlMicroseconds": (
                        TENANT_CAPABILITY_MAX_TTL_MICROSECONDS
                    ),
                    "maximumFutureSkewMicroseconds": (
                        TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS
                    ),
                    "keyIdBytes": {"minimum": 1, "maximum": 255},
                    "issuerUtf8Bytes": {"minimum": 1, "maximum": 2048},
                    "subjectUtf8Bytes": {"minimum": 1, "maximum": 255},
                    "asciiIdBytes": {"minimum": 1, "maximum": 255},
                    "digestBytes": 32,
                },
                "timeOrder": "issuedAt <= notBefore < expiresAt",
                "asciiIdPolicy": TENANT_CAPABILITY_ASCII_ID_POLICY,
                "fixedPartyRecordKind": _PARTY_RECORD_KIND,
                "partyRecordIdEqualsPartyRef": True,
            },
            "verificationKeyRows": {
                "policy": self.key_row_policy,
                "secretBytes": TENANT_CAPABILITY_KEY_BYTES,
                "immutable": True,
                "validityBounds": {
                    "from": "signed-unix-microseconds-inclusive",
                    "until": "signed-unix-microseconds-exclusive",
                    "rule": "validFromUnixMicroseconds < validUntilUnixMicroseconds",
                    "unboundedEndpointsAllowed": False,
                },
                "installationCapabilityRole": "ofarm_identity_writer",
                "directDmlAllowed": False,
                "secretMaterialIncludedInManifest": False,
            },
            "binderRoutines": {
                "identityTypeNames": "PostgreSQL-core-types-only",
                "signatures": [routine.manifest() for routine in self.routines],
            },
            "claimBoundary": (
                "canonical framing and HMAC golden-vector helper only; no "
                "signer, key custody, authentication, replay, or binder "
                "correctness claim"
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
        value["tenantCapabilityContractDigest"] = self.digest
        return value

    def canonical_manifest_bytes(self) -> bytes:
        return _canonical_json(self.manifest())


TENANT_CAPABILITY_CONTRACT = TenantCapabilityContract(
    identity="ofarm.tenant-capability-and-binder.v1",
    capability_version=TENANT_CAPABILITY_VERSION,
    audience=TENANT_BINDER_AUDIENCE,
    equality_policy=TENANT_CAPABILITY_EQUALITY_POLICY,
    bounds_policy=TENANT_CAPABILITY_BOUNDS_POLICY,
    key_row_policy=TENANT_CAPABILITY_KEY_ROW_POLICY,
    routines=TENANT_BINDER_ROUTINE_SIGNATURES,
)


def validate_tenant_capability(
    capability: TenantCapability,
    *,
    now_unix_microseconds: int | None = None,
) -> None:
    """Reject every value outside the exact V1 field and time bounds."""

    if type(capability) is not TenantCapability:
        raise TenantCapabilityContractError("capability must be a TenantCapability")
    _validate_uuid(capability.challenge_id, "challenge id")
    _require_exact_text(capability.audience, TENANT_BINDER_AUDIENCE, "audience")
    _validate_ascii_id(capability.key_id, "key id")
    _require_exact_text(
        capability.equality_policy,
        TENANT_CAPABILITY_EQUALITY_POLICY,
        "equality policy",
    )
    _validate_issuer(capability.issuer)
    _validate_subject(capability.subject)
    _validate_uuid(capability.binding_version_id, "binding version id")
    _validate_digest(capability.binding_version_digest, "binding version digest")
    _validate_uuid(capability.lifecycle_head_id, "lifecycle head id")
    _validate_digest(capability.lifecycle_head_digest, "lifecycle head digest")
    _validate_uuid(capability.tenant_id, "tenant id")
    _validate_digest(
        capability.tenant_registration_digest, "tenant registration digest"
    )
    _validate_ascii_id(capability.party_ref, "party ref")
    _require_exact_text(
        capability.party_record_kind,
        _PARTY_RECORD_KIND,
        "party record kind",
    )
    _validate_ascii_id(capability.party_record_id, "party record id")
    if capability.party_record_id != capability.party_ref:
        raise TenantCapabilityContractError("party record id must equal party ref")
    _validate_digest(capability.party_schema_digest, "party schema digest")
    _validate_digest(capability.party_payload_digest, "party payload digest")
    _validate_int64(capability.issued_at_unix_microseconds, "issued-at")
    _validate_int64(capability.not_before_unix_microseconds, "not-before")
    _validate_int64(capability.expires_at_unix_microseconds, "expires-at")
    if not (
        capability.issued_at_unix_microseconds
        <= capability.not_before_unix_microseconds
        < capability.expires_at_unix_microseconds
    ):
        raise TenantCapabilityContractError(
            "capability times must satisfy issued-at <= not-before < expires-at"
        )
    ttl = (
        capability.expires_at_unix_microseconds
        - capability.not_before_unix_microseconds
    )
    if ttl > TENANT_CAPABILITY_MAX_TTL_MICROSECONDS:
        raise TenantCapabilityContractError(
            "capability TTL must be between 1 and 60000000 microseconds"
        )
    _validate_uuid(capability.nonce, "nonce")

    if now_unix_microseconds is not None:
        _validate_int64(now_unix_microseconds, "current Unix microseconds")
        maximum_future = (
            now_unix_microseconds
            + TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS
        )
        if capability.issued_at_unix_microseconds > maximum_future:
            raise TenantCapabilityContractError(
                "capability issued-at exceeds the future-skew bound"
            )
        if capability.not_before_unix_microseconds > maximum_future:
            raise TenantCapabilityContractError(
                "capability not-before exceeds the future-skew bound"
            )
        if capability.expires_at_unix_microseconds <= now_unix_microseconds:
            raise TenantCapabilityContractError("capability is expired")


def canonical_tenant_capability_bytes(capability: TenantCapability) -> bytes:
    """Return the exact domain-separated, all-fields-lp32 V1 HMAC input."""

    validate_tenant_capability(capability)
    values = (
        capability.challenge_id.bytes,
        _ascii(capability.audience, "audience"),
        _ascii(capability.key_id, "key id"),
        _ascii(capability.equality_policy, "equality policy"),
        _utf8(capability.issuer, "issuer"),
        _utf8(capability.subject, "subject"),
        capability.binding_version_id.bytes,
        capability.binding_version_digest,
        capability.lifecycle_head_id.bytes,
        capability.lifecycle_head_digest,
        capability.tenant_id.bytes,
        capability.tenant_registration_digest,
        _ascii(capability.party_ref, "party ref"),
        _ascii(capability.party_record_kind, "party record kind"),
        _ascii(capability.party_record_id, "party record id"),
        capability.party_schema_digest,
        capability.party_payload_digest,
        capability.issued_at_unix_microseconds.to_bytes(8, "big", signed=True),
        capability.not_before_unix_microseconds.to_bytes(8, "big", signed=True),
        capability.expires_at_unix_microseconds.to_bytes(8, "big", signed=True),
        capability.nonce.bytes,
    )
    return TENANT_CAPABILITY_DOMAIN + b"".join(_lp32(value) for value in values)


def tenant_capability_hmac(secret: bytes, capability: TenantCapability) -> bytes:
    """Compute the exact cross-layer HMAC-SHA-256 golden-vector value."""

    _validate_secret(secret)
    return hmac.new(
        secret,
        canonical_tenant_capability_bytes(capability),
        digestmod=hashlib.sha256,
    ).digest()


def validate_tenant_capability_mac(mac: bytes) -> None:
    if type(mac) is not bytes or len(mac) != TENANT_CAPABILITY_MAC_BYTES:
        raise TenantCapabilityContractError(
            "capability MAC must be exactly 32 bytes"
        )


def validate_tenant_capability_key_row(
    *,
    key_id: str,
    secret: bytes,
    valid_from_unix_microseconds: int,
    valid_until_unix_microseconds: int,
) -> None:
    """Validate the non-I/O shape of one externally installed key row."""

    _validate_ascii_id(key_id, "key id")
    _validate_secret(secret)
    _validate_int64(valid_from_unix_microseconds, "key valid-from")
    _validate_int64(valid_until_unix_microseconds, "key valid-until")
    if valid_from_unix_microseconds >= valid_until_unix_microseconds:
        raise TenantCapabilityContractError(
            "key validity window must be finite and increasing"
        )


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


def _lp32(value: bytes) -> bytes:
    if len(value) >= 2**32:
        raise TenantCapabilityContractError("field exceeds the lp32 bound")
    return len(value).to_bytes(4, "big", signed=False) + value


def _ascii(value: str, label: str) -> bytes:
    if type(value) is not str:
        raise TenantCapabilityContractError(f"{label} must be text")
    try:
        return value.encode("ascii", errors="strict")
    except UnicodeEncodeError as exc:
        raise TenantCapabilityContractError(
            f"{label} must contain only ASCII"
        ) from exc


def _utf8(value: str, label: str) -> bytes:
    if type(value) is not str:
        raise TenantCapabilityContractError(f"{label} must be text")
    try:
        return value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise TenantCapabilityContractError(
            f"{label} must be strict UTF-8 text"
        ) from exc


def _require_exact_text(value: str, expected: str, label: str) -> None:
    if type(value) is not str or value != expected:
        raise TenantCapabilityContractError(f"{label} is not exact")


def _validate_ascii_id(value: str, label: str) -> None:
    if type(value) is not str or _ASCII_ID.fullmatch(value) is None:
        raise TenantCapabilityContractError(
            f"{label} must satisfy {TENANT_CAPABILITY_ASCII_ID_POLICY}"
        )


def _validate_digest(value: bytes, label: str) -> None:
    if type(value) is not bytes or len(value) != 32:
        raise TenantCapabilityContractError(
            f"{label} must be exactly 32 raw SHA-256 bytes"
        )


def _validate_uuid(value: uuid.UUID, label: str) -> None:
    if type(value) is not uuid.UUID:
        raise TenantCapabilityContractError(f"{label} must be a UUID")
    if value.int == 0:
        raise TenantCapabilityContractError(f"{label} must not be the nil UUID")


def _validate_int64(value: int, label: str) -> None:
    if type(value) is not int or not _INT64_MIN <= value <= _INT64_MAX:
        raise TenantCapabilityContractError(
            f"{label} must be a signed 64-bit integer"
        )


def _validate_issuer(value: str) -> None:
    encoded = _utf8(value, "issuer")
    if not 1 <= len(encoded) <= 2048:
        raise TenantCapabilityContractError(
            "issuer must contain between 1 and 2048 UTF-8 bytes"
        )
    if any(
        character == "\x00"
        or character.isspace()
        or unicodedata.category(character).startswith("C")
        for character in value
    ):
        raise TenantCapabilityContractError(
            "issuer must not contain whitespace, NUL, or control characters"
        )
    try:
        parsed = urllib.parse.urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise TenantCapabilityContractError("issuer URL is invalid") from exc
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or port is not None
        and not 1 <= port <= 65535
    ):
        raise TenantCapabilityContractError(
            "issuer must be an exact configured https URL without query or fragment"
        )


def _validate_subject(value: str) -> None:
    if type(value) is not str or _SUBJECT.fullmatch(value) is None:
        raise TenantCapabilityContractError(
            "subject must contain between 1 and 255 visible ASCII bytes"
        )


def _validate_secret(secret: bytes) -> None:
    if type(secret) is not bytes or len(secret) != TENANT_CAPABILITY_KEY_BYTES:
        raise TenantCapabilityContractError(
            "capability verification secret must be exactly 32 bytes"
        )


def _validate_checked_in_contract() -> None:
    contract = TENANT_CAPABILITY_CONTRACT
    if (
        contract.capability_version != TENANT_CAPABILITY_VERSION
        or contract.audience != TENANT_BINDER_AUDIENCE
        or contract.equality_policy != TENANT_CAPABILITY_EQUALITY_POLICY
        or contract.bounds_policy != TENANT_CAPABILITY_BOUNDS_POLICY
        or contract.key_row_policy != TENANT_CAPABILITY_KEY_ROW_POLICY
        or contract.routines != TENANT_BINDER_ROUTINE_SIGNATURES
        or TENANT_CAPABILITY_DOMAIN != b"OFARM_TENANT_CAPABILITY_V1\x00"
        or tuple(field[1] for field in _FRAMING)
        != TENANT_BINDER_ROUTINE_SIGNATURES[1].argument_types[:-1]
        or TENANT_BINDER_ROUTINE_SIGNATURES[1].argument_types[-1] != "bytea"
    ):
        raise TenantCapabilityContractError(
            "checked-in tenant capability contract is internally inconsistent"
        )


_validate_checked_in_contract()


__all__ = [
    "TENANT_BINDER_AUDIENCE",
    "TENANT_BINDER_ROUTINE_SIGNATURES",
    "TENANT_CAPABILITY_ASCII_ID_POLICY",
    "TENANT_CAPABILITY_BOUNDS_POLICY",
    "TENANT_CAPABILITY_CONTRACT",
    "TENANT_CAPABILITY_CONTRACT_DIGEST_POLICY",
    "TENANT_CAPABILITY_DOMAIN",
    "TENANT_CAPABILITY_DOMAIN_IDENTIFIER",
    "TENANT_CAPABILITY_EQUALITY_POLICY",
    "TENANT_CAPABILITY_KEY_BYTES",
    "TENANT_CAPABILITY_KEY_ROW_POLICY",
    "TENANT_CAPABILITY_MAC_ALGORITHM",
    "TENANT_CAPABILITY_MAC_BYTES",
    "TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS",
    "TENANT_CAPABILITY_MAX_TTL_MICROSECONDS",
    "TENANT_CAPABILITY_VERSION",
    "BinderRoutineSignature",
    "TenantCapability",
    "TenantCapabilityContract",
    "TenantCapabilityContractError",
    "canonical_tenant_capability_bytes",
    "tenant_capability_hmac",
    "validate_tenant_capability",
    "validate_tenant_capability_key_row",
    "validate_tenant_capability_mac",
]
