"""Issue one bounded observer-signed security-audit authority receipt.

The issuer is stateless and library-only.  Trusted composition pins one exact
KMS key version, matching observer public key, canonical approver manifest,
KMS client, and caller-owned time.  The only external effect is one raw-data
KMS signing call after all local validation succeeds.
"""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as BinasciiError
from dataclasses import dataclass
from hashlib import sha256
from json import dumps, loads
from re import fullmatch
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)
from google.cloud import kms_v1


_APPROVER_MANIFEST_SCHEMA = (
    "ofarm.security-audit-break-glass-approver-manifest.v1"
)
_AUTHORITY_RECEIPT_SCHEMA = (
    "ofarm.security-audit-break-glass-authority-receipt.v1"
)
_AUDIENCE = "ofarm.security-audit-break-glass-export.v1"
_AUTHORITY_SIGNATURE_DOMAIN = (
    b"OFARM_SECURITY_AUDIT_BREAK_GLASS_AUTHORITY_RECEIPT_V1\x00"
)
_KMS_RPC_TIMEOUT_SECONDS = 5.0
_RECEIPT_LIFETIME_MICROSECONDS = 300_000_000
_MAX_UNIX_MICROSECONDS = 9_223_372_036_854_775_807
_APPROVER_MANIFEST_MAX_BYTES = 8_192
_AUTHORITY_PAYLOAD_MAX_BYTES = 12_288
_SIGNING_INPUT_MIN_BYTES = 55
_SIGNING_INPUT_MAX_BYTES = 12_342
_AUTHORITY_ENVELOPE_MAX_BYTES = 16_384
_RESOURCE_PATTERN = (
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/"
    r"locations/[a-z0-9](?:[a-z0-9-]*[a-z0-9])?/"
    r"keyRings/[A-Za-z0-9_-]{1,63}/"
    r"cryptoKeys/[A-Za-z0-9_-]{1,63}/"
    r"cryptoKeyVersions/[1-9][0-9]*$"
)
_MANIFEST_MEMBERS = ("approvers", "audience", "schemaVersion")
_MANIFEST_ENTRY_MEMBERS = (
    "approverId",
    "independenceDomain",
    "publicKey",
)


class KmsAuthoritySigningClient(Protocol):
    def asymmetric_sign(
        self,
        *,
        request: kms_v1.AsymmetricSignRequest,
        retry: None,
        timeout: float,
    ) -> kms_v1.AsymmetricSignResponse: ...


class SecurityAuditAuthorityReceiptRefused(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _ApproverEntry:
    approver_id: str
    key_id: str
    independence_domain: str
    public_key_text: str


def _bounded_bytes(value: object, maximum: int) -> bytes:
    if type(value) is not bytes or not value or len(value) > maximum:
        raise ValueError
    return value


def _reject_constant(_value: str) -> object:
    raise ValueError


def _pairs_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for name, member in pairs:
        if name in value:
            raise ValueError
        value[name] = member
    return value


def _canonical_bytes(value: object) -> bytes:
    return dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _canonical_object(data: object, maximum: int) -> dict[str, object]:
    carrier = _bounded_bytes(data, maximum)
    if carrier.startswith(b"\xef\xbb\xbf"):
        raise ValueError
    value = loads(
        carrier.decode("utf-8"),
        object_pairs_hook=_pairs_object,
        parse_constant=_reject_constant,
    )
    if type(value) is not dict or _canonical_bytes(value) != carrier:
        raise ValueError
    return value


def _exact_members(value: object, expected: tuple[str, ...]) -> dict[str, object]:
    if type(value) is not dict or tuple(sorted(value)) != tuple(sorted(expected)):
        raise ValueError
    return value


def _base64url_text(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url(value: object, exact: int) -> bytes:
    if (
        type(value) is not str
        or not value
        or fullmatch(r"[A-Za-z0-9_-]+", value) is None
    ):
        raise ValueError
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        decoded = urlsafe_b64decode((value + padding).encode("ascii"))
    except (BinasciiError, ValueError):
        raise ValueError from None
    if len(decoded) != exact or _base64url_text(decoded) != value:
        raise ValueError
    return decoded


def _closed_id(value: object) -> str:
    if (
        type(value) is not str
        or fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) is None
    ):
        raise ValueError
    return value


def _derive_key_id(public_key: bytes) -> str:
    x = _base64url_text(public_key).encode("ascii")
    thumbprint = b'{"crv":"Ed25519","kty":"OKP","x":"' + x + b'"}'
    return _base64url_text(sha256(thumbprint).digest())


def _resource(value: object) -> str:
    if type(value) is not str or fullmatch(_RESOURCE_PATTERN, value) is None:
        raise ValueError
    return value


def _public_key(value: object) -> tuple[bytes, Ed25519PublicKey]:
    if type(value) is not bytes or len(value) != 32:
        raise ValueError
    return value, Ed25519PublicKey.from_public_bytes(value)


def _manifest_entry(value: object) -> _ApproverEntry:
    document = _exact_members(value, _MANIFEST_ENTRY_MEMBERS)
    approver_id = _closed_id(document["approverId"])
    domain = _closed_id(document["independenceDomain"])
    public_key_text = document["publicKey"]
    public_key = _base64url(public_key_text, 32)
    Ed25519PublicKey.from_public_bytes(public_key)
    return _ApproverEntry(
        approver_id=approver_id,
        key_id=_derive_key_id(public_key),
        independence_domain=domain,
        public_key_text=public_key_text,
    )


def _manifest_entries(carrier: object) -> tuple[_ApproverEntry, ...]:
    document = _canonical_object(carrier, _APPROVER_MANIFEST_MAX_BYTES)
    _exact_members(document, _MANIFEST_MEMBERS)
    if (
        document["schemaVersion"] != _APPROVER_MANIFEST_SCHEMA
        or document["audience"] != _AUDIENCE
        or type(document["approvers"]) is not list
        or not 2 <= len(document["approvers"]) <= 16
    ):
        raise ValueError
    entries = tuple(_manifest_entry(value) for value in document["approvers"])
    ordering = tuple(
        (entry.approver_id, entry.key_id, entry.independence_domain)
        for entry in entries
    )
    if ordering != tuple(sorted(ordering)):
        raise ValueError
    if (
        len({entry.approver_id for entry in entries}) != len(entries)
        or len({entry.key_id for entry in entries}) != len(entries)
    ):
        raise ValueError
    return entries


def _trusted_time(now_us: object) -> int:
    if (
        type(now_us) is not int
        or now_us < 0
        or now_us
        > _MAX_UNIX_MICROSECONDS - _RECEIPT_LIFETIME_MICROSECONDS
    ):
        raise ValueError
    return now_us


def _authority_payload(
    entries: tuple[_ApproverEntry, ...],
    now_us: int,
) -> bytes:
    approvers = [
        {
            "approverId": entry.approver_id,
            "independenceDomain": entry.independence_domain,
            "keyId": entry.key_id,
            "publicKey": entry.public_key_text,
        }
        for entry in entries
    ]
    payload = _canonical_bytes(
        {
            "approvers": approvers,
            "audience": _AUDIENCE,
            "expiresAtUnixMicroseconds": (
                now_us + _RECEIPT_LIFETIME_MICROSECONDS
            ),
            "observedAtUnixMicroseconds": now_us,
            "schemaVersion": _AUTHORITY_RECEIPT_SCHEMA,
        }
    )
    return _bounded_bytes(payload, _AUTHORITY_PAYLOAD_MAX_BYTES)


def _crc32c(value: bytes) -> int:
    checksum = 0xFFFFFFFF
    for octet in value:
        checksum ^= octet
        for _ in range(8):
            checksum = (checksum >> 1) ^ (
                0x82F63B78 if checksum & 1 else 0
            )
    return checksum ^ 0xFFFFFFFF


def _request(
    resource: str,
    payload: bytes,
) -> tuple[kms_v1.AsymmetricSignRequest, bytes]:
    signing_input = _AUTHORITY_SIGNATURE_DOMAIN + payload
    if not _SIGNING_INPUT_MIN_BYTES <= len(signing_input) <= _SIGNING_INPUT_MAX_BYTES:
        raise ValueError
    request = kms_v1.AsymmetricSignRequest(
        name=resource,
        data=signing_input,
        data_crc32c=_crc32c(signing_input),
    )
    return request, signing_input


def _signature(
    response: object,
    resource: str,
    observer_key: Ed25519PublicKey,
    signing_input: bytes,
) -> bytes:
    if type(response) is not kms_v1.AsymmetricSignResponse:
        raise ValueError
    signature = response.signature
    checksum = response.signature_crc32c
    if (
        response.name != resource
        or response.protection_level != kms_v1.ProtectionLevel.HSM
        or response.verified_data_crc32c is not True
        or response.verified_digest_crc32c is not False
        or type(signature) is not bytes
        or len(signature) != 64
        or type(checksum) is not int
        or isinstance(checksum, bool)
        or not 0 <= checksum <= 0xFFFFFFFF
        or checksum != _crc32c(signature)
    ):
        raise ValueError
    observer_key.verify(signature, signing_input)
    return signature


def _envelope(payload: bytes, signature: bytes) -> bytes:
    carrier = _canonical_bytes(
        {
            "payload": _base64url_text(payload),
            "signature": _base64url_text(signature),
        }
    )
    return _bounded_bytes(carrier, _AUTHORITY_ENVELOPE_MAX_BYTES)


def _issue(
    client: KmsAuthoritySigningClient,
    resource: str,
    observer_key: Ed25519PublicKey,
    entries: tuple[_ApproverEntry, ...],
    now_us: object,
) -> bytes:
    trusted_now_us = _trusted_time(now_us)
    payload = _authority_payload(entries, trusted_now_us)
    request, signing_input = _request(resource, payload)
    response = client.asymmetric_sign(
        request=request,
        retry=None,
        timeout=_KMS_RPC_TIMEOUT_SECONDS,
    )
    signature = _signature(response, resource, observer_key, signing_input)
    return _envelope(payload, signature)


class SecurityAuditAuthorityReceiptIssuer:
    """Issue exact verifier-compatible receipts under one pinned root."""

    __slots__ = ("_client", "_entries", "_observer_key", "_resource")

    def __init__(
        self,
        client: KmsAuthoritySigningClient,
        *,
        kms_key_version_resource: str,
        observer_public_key: bytes,
        approver_manifest_bytes: bytes,
    ) -> None:
        refused = False
        try:
            if not callable(client.asymmetric_sign):
                raise ValueError
            resource = _resource(kms_key_version_resource)
            _, observer_key = _public_key(observer_public_key)
            entries = _manifest_entries(approver_manifest_bytes)
        except Exception:
            refused = True
        if refused:
            raise SecurityAuditAuthorityReceiptRefused()
        self._client = client
        self._resource = resource
        self._observer_key = observer_key
        self._entries = entries

    def issue(self, *, now_us: int) -> bytes:
        """Return one canonical receipt or one fixed fresh refusal."""

        refused = False
        try:
            result = _issue(
                self._client,
                self._resource,
                self._observer_key,
                self._entries,
                now_us,
            )
        except Exception:
            refused = True
        if refused:
            raise SecurityAuditAuthorityReceiptRefused()
        return result


__all__ = (
    "SecurityAuditAuthorityReceiptIssuer",
    "SecurityAuditAuthorityReceiptRefused",
)
