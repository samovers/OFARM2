"""Side-effect-free verification for one dual-approved audit export request.

The verifier authenticates one bounded authority receipt and exactly two
independent Ed25519 approval statements.  It returns normalized evidence only;
it does not admit an operation, create credentials, call the database, export
data, deliver output, acquire time, or consume an approval.
"""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as BinasciiError
from dataclasses import dataclass
from hashlib import sha256
from json import dumps, loads
from re import fullmatch
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)

from deployment.postgresql.audit_contract import (
    EXPORT_ACCESS_PURPOSE_IDENTITY,
    EXPORT_FUNCTION_IDENTITY,
    EXPORT_MAX_BYTES,
    EXPORT_MAX_ROWS,
)
from deployment.postgresql.security_audit_access import (
    SecurityAuditAccessCursor,
)


_AUTHORITY_RECEIPT_SCHEMA = (
    "ofarm.security-audit-break-glass-authority-receipt.v1"
)
_EXPORT_REQUEST_SCHEMA = "ofarm.security-audit-break-glass-export-request.v1"
_APPROVAL_STATEMENT_SCHEMA = (
    "ofarm.security-audit-break-glass-export-approval.v1"
)
_APPROVAL_BUNDLE_SCHEMA = (
    "ofarm.security-audit-break-glass-approval-bundle.v1"
)
_VERIFIED_APPROVAL_SCHEMA = (
    "ofarm.security-audit-break-glass-verified-approval.v1"
)
_AUDIENCE = "ofarm.security-audit-break-glass-export.v1"
_AUTHORITY_SIGNATURE_DOMAIN = (
    b"OFARM_SECURITY_AUDIT_BREAK_GLASS_AUTHORITY_RECEIPT_V1\x00"
)
_APPROVAL_SIGNATURE_DOMAIN = (
    b"OFARM_SECURITY_AUDIT_BREAK_GLASS_EXPORT_APPROVAL_V1\x00"
)
_MAX_UNIX_MICROSECONDS = 9_223_372_036_854_775_807
_MAX_INTERVAL_MICROSECONDS = 300_000_000
_AUTHORITY_ENVELOPE_MAX_BYTES = 16_384
_AUTHORITY_PAYLOAD_MAX_BYTES = 12_288
_APPROVAL_BUNDLE_MAX_BYTES = 16_384
_EXPORT_REQUEST_MAX_BYTES = 4_096
_APPROVAL_STATEMENT_MAX_BYTES = 2_048

_AUTHORITY_ENVELOPE_MEMBERS = ("payload", "signature")
_AUTHORITY_PAYLOAD_MEMBERS = (
    "approvers",
    "audience",
    "expiresAtUnixMicroseconds",
    "observedAtUnixMicroseconds",
    "schemaVersion",
)
_AUTHORITY_ENTRY_MEMBERS = (
    "approverId",
    "independenceDomain",
    "keyId",
    "publicKey",
)
_EXPORT_REQUEST_MEMBERS = (
    "audience",
    "authorityReceiptDigest",
    "cursor",
    "expiresAtUnixMicroseconds",
    "functionIdentity",
    "maxBytes",
    "maxPages",
    "maxRows",
    "notBeforeUnixMicroseconds",
    "operationId",
    "purpose",
    "schemaVersion",
)
_APPROVAL_STATEMENT_MEMBERS = (
    "approverId",
    "audience",
    "authorityReceiptDigest",
    "independenceDomain",
    "keyId",
    "operationId",
    "requestDigest",
    "schemaVersion",
)
_APPROVAL_ENTRY_MEMBERS = ("signature", "statement")
_APPROVAL_BUNDLE_MEMBERS = ("approvals", "request", "schemaVersion")


class SecurityAuditApprovalRefused(RuntimeError):
    """The authority receipt or approval bundle was refused."""


@dataclass(frozen=True, slots=True)
class _AuthorityEntry:
    approver_id: str
    key_id: str
    independence_domain: str
    public_key: Ed25519PublicKey


@dataclass(frozen=True, slots=True)
class _Authority:
    digest: str
    observed_at_us: int
    expires_at_us: int
    entries: tuple[_AuthorityEntry, ...]


@dataclass(frozen=True, slots=True)
class _ExportRequest:
    operation_id: UUID
    digest: str
    not_before_us: int
    expires_at_us: int
    cursor: SecurityAuditAccessCursor | None


@dataclass(frozen=True, slots=True)
class _Approval:
    approver_id: str
    key_id: str
    independence_domain: str
    public_key: Ed25519PublicKey
    statement_bytes: bytes
    signature: bytes


@dataclass(frozen=True, slots=True)
class _VerifiedSecurityAuditApproval:
    schema_version: str
    operation_id: UUID
    authority_receipt_digest: str
    request_digest: str
    approval_digest: str
    valid_from_us: int
    valid_until_us: int
    cursor: SecurityAuditAccessCursor | None
    approver_ids: tuple[str, str]
    key_ids: tuple[str, str]
    independence_domains: tuple[str, str]


def _bounded_bytes(value: object, maximum: int) -> bytes:
    if type(value) is not bytes or not value or len(value) > maximum:
        raise ValueError
    return value


def _integer(value: object) -> int:
    if (
        type(value) is not int
        or value < 0
        or value > _MAX_UNIX_MICROSECONDS
    ):
        raise ValueError
    return value


def _fixed_integer(value: object, expected: int) -> int:
    validated = _integer(value)
    if validated != expected:
        raise ValueError
    return validated


def _reject_constant(_value: str) -> object:
    raise ValueError


def _pairs_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for name, member in pairs:
        if name in value:
            raise ValueError
        value[name] = member
    return value


def _canonical_object(data: bytes, maximum: int) -> dict[str, object]:
    _bounded_bytes(data, maximum)
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError
    text = data.decode("utf-8")
    value = loads(
        text,
        object_pairs_hook=_pairs_object,
        parse_constant=_reject_constant,
    )
    if type(value) is not dict:
        raise ValueError
    canonical = dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    if canonical != data:
        raise ValueError
    return value


def _exact_members(value: object, expected: tuple[str, ...]) -> dict[str, object]:
    if type(value) is not dict or tuple(sorted(value)) != tuple(sorted(expected)):
        raise ValueError
    return value


def _base64url(value: object, maximum: int, exact: int | None = None) -> bytes:
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
    if (
        not decoded
        or len(decoded) > maximum
        or (exact is not None and len(decoded) != exact)
        or _base64url_text(decoded) != value
    ):
        raise ValueError
    return decoded


def _base64url_text(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _digest(value: bytes) -> str:
    return "sha256:" + sha256(value).hexdigest()


def _closed_id(value: object) -> str:
    if (
        type(value) is not str
        or len(value) > 128
        or fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) is None
    ):
        raise ValueError
    return value


def _key_id_text(value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 43
        or fullmatch(r"[A-Za-z0-9_-]{43}", value) is None
    ):
        raise ValueError
    return value


def _derive_key_id(public_key: bytes) -> str:
    x = _base64url_text(public_key).encode("ascii")
    thumbprint = b'{"crv":"Ed25519","kty":"OKP","x":"' + x + b'"}'
    return _base64url_text(sha256(thumbprint).digest())


def _uuid_v4(value: object) -> UUID:
    if type(value) is not str:
        raise ValueError
    parsed = UUID(value)
    if (
        str(parsed) != value
        or parsed.version != 4
        or (parsed.int >> 62) & 3 != 2
    ):
        raise ValueError
    return parsed


def _cursor(value: object) -> SecurityAuditAccessCursor | None:
    if value is None:
        return None
    if type(value) is not str or len(value) != 64:
        raise ValueError
    parsed = SecurityAuditAccessCursor.parse(value)
    if parsed.render() != value:
        raise ValueError
    return parsed


def _interval(start: object, end: object) -> tuple[int, int]:
    validated_start = _integer(start)
    validated_end = _integer(end)
    duration = validated_end - validated_start
    if duration < 1 or duration > _MAX_INTERVAL_MICROSECONDS:
        raise ValueError
    return validated_start, validated_end


def _public_key(value: bytes) -> Ed25519PublicKey:
    if type(value) is not bytes or len(value) != 32:
        raise ValueError
    return Ed25519PublicKey.from_public_bytes(value)


def _verify_ed25519(
    key: Ed25519PublicKey,
    signature: bytes,
    message: bytes,
) -> None:
    try:
        key.verify(signature, message)
    except InvalidSignature:
        raise ValueError from None


def _authority_entry(value: object) -> _AuthorityEntry:
    document = _exact_members(value, _AUTHORITY_ENTRY_MEMBERS)
    approver_id = _closed_id(document["approverId"])
    domain = _closed_id(document["independenceDomain"])
    public_key_bytes = _base64url(document["publicKey"], 32, 32)
    key_id = _key_id_text(document["keyId"])
    if key_id != _derive_key_id(public_key_bytes):
        raise ValueError
    return _AuthorityEntry(
        approver_id=approver_id,
        key_id=key_id,
        independence_domain=domain,
        public_key=_public_key(public_key_bytes),
    )


def _authority_entries(value: object) -> tuple[_AuthorityEntry, ...]:
    if type(value) is not list or not 2 <= len(value) <= 16:
        raise ValueError
    entries = tuple(_authority_entry(member) for member in value)
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


def _authority(
    carrier: bytes,
    observer_key: Ed25519PublicKey,
    now_us: int,
) -> _Authority:
    envelope = _canonical_object(carrier, _AUTHORITY_ENVELOPE_MAX_BYTES)
    _exact_members(envelope, _AUTHORITY_ENVELOPE_MEMBERS)
    payload = _base64url(
        envelope["payload"], _AUTHORITY_PAYLOAD_MAX_BYTES
    )
    signature = _base64url(envelope["signature"], 64, 64)
    document = _canonical_object(payload, _AUTHORITY_PAYLOAD_MAX_BYTES)
    _exact_members(document, _AUTHORITY_PAYLOAD_MEMBERS)
    if (
        document["schemaVersion"] != _AUTHORITY_RECEIPT_SCHEMA
        or document["audience"] != _AUDIENCE
    ):
        raise ValueError
    observed_at_us, expires_at_us = _interval(
        document["observedAtUnixMicroseconds"],
        document["expiresAtUnixMicroseconds"],
    )
    if not observed_at_us <= now_us < expires_at_us:
        raise ValueError
    entries = _authority_entries(document["approvers"])
    _verify_ed25519(
        observer_key,
        signature,
        _AUTHORITY_SIGNATURE_DOMAIN + payload,
    )
    return _Authority(
        digest=_digest(carrier),
        observed_at_us=observed_at_us,
        expires_at_us=expires_at_us,
        entries=entries,
    )


def _request(
    encoded: object,
    authority: _Authority,
    now_us: int,
) -> _ExportRequest:
    payload = _base64url(encoded, _EXPORT_REQUEST_MAX_BYTES)
    document = _canonical_object(payload, _EXPORT_REQUEST_MAX_BYTES)
    _exact_members(document, _EXPORT_REQUEST_MEMBERS)
    if (
        document["schemaVersion"] != _EXPORT_REQUEST_SCHEMA
        or document["audience"] != _AUDIENCE
        or document["authorityReceiptDigest"] != authority.digest
        or document["purpose"] != EXPORT_ACCESS_PURPOSE_IDENTITY
        or document["functionIdentity"] != EXPORT_FUNCTION_IDENTITY
    ):
        raise ValueError
    _fixed_integer(document["maxPages"], 1)
    _fixed_integer(document["maxRows"], EXPORT_MAX_ROWS)
    _fixed_integer(document["maxBytes"], EXPORT_MAX_BYTES)
    not_before_us, expires_at_us = _interval(
        document["notBeforeUnixMicroseconds"],
        document["expiresAtUnixMicroseconds"],
    )
    if (
        not authority.observed_at_us <= not_before_us
        or not not_before_us <= now_us < expires_at_us
        or expires_at_us > authority.expires_at_us
    ):
        raise ValueError
    return _ExportRequest(
        operation_id=_uuid_v4(document["operationId"]),
        digest=_digest(payload),
        not_before_us=not_before_us,
        expires_at_us=expires_at_us,
        cursor=_cursor(document["cursor"]),
    )


def _resolved_authority_entry(
    authority: _Authority,
    approver_id: str,
    key_id: str,
    domain: str,
) -> _AuthorityEntry:
    matched = tuple(
        entry
        for entry in authority.entries
        if entry.approver_id == approver_id
    )
    if (
        len(matched) != 1
        or matched[0].key_id != key_id
        or matched[0].independence_domain != domain
    ):
        raise ValueError
    return matched[0]


def _approval(
    value: object,
    authority: _Authority,
    request: _ExportRequest,
) -> _Approval:
    entry_document = _exact_members(value, _APPROVAL_ENTRY_MEMBERS)
    statement_bytes = _base64url(
        entry_document["statement"], _APPROVAL_STATEMENT_MAX_BYTES
    )
    signature = _base64url(entry_document["signature"], 64, 64)
    statement = _canonical_object(
        statement_bytes, _APPROVAL_STATEMENT_MAX_BYTES
    )
    _exact_members(statement, _APPROVAL_STATEMENT_MEMBERS)
    approver_id = _closed_id(statement["approverId"])
    key_id = _key_id_text(statement["keyId"])
    domain = _closed_id(statement["independenceDomain"])
    if (
        statement["schemaVersion"] != _APPROVAL_STATEMENT_SCHEMA
        or statement["audience"] != _AUDIENCE
        or statement["authorityReceiptDigest"] != authority.digest
        or statement["requestDigest"] != request.digest
        or statement["operationId"] != str(request.operation_id)
    ):
        raise ValueError
    authority_entry = _resolved_authority_entry(
        authority, approver_id, key_id, domain
    )
    return _Approval(
        approver_id=approver_id,
        key_id=key_id,
        independence_domain=domain,
        public_key=authority_entry.public_key,
        statement_bytes=statement_bytes,
        signature=signature,
    )


def _approvals(
    value: object,
    authority: _Authority,
    request: _ExportRequest,
) -> tuple[_Approval, _Approval]:
    if type(value) is not list or len(value) != 2:
        raise ValueError
    first = _approval(value[0], authority, request)
    second = _approval(value[1], authority, request)
    approvals = (first, second)
    ordering = tuple(
        (item.approver_id, item.key_id, item.independence_domain)
        for item in approvals
    )
    if ordering != tuple(sorted(ordering)):
        raise ValueError
    if (
        first.approver_id == second.approver_id
        or first.key_id == second.key_id
        or first.independence_domain == second.independence_domain
    ):
        raise ValueError
    return approvals


def _bundle(
    carrier: bytes,
    authority: _Authority,
    now_us: int,
) -> tuple[_ExportRequest, tuple[_Approval, _Approval]]:
    document = _canonical_object(carrier, _APPROVAL_BUNDLE_MAX_BYTES)
    _exact_members(document, _APPROVAL_BUNDLE_MEMBERS)
    if document["schemaVersion"] != _APPROVAL_BUNDLE_SCHEMA:
        raise ValueError
    request = _request(document["request"], authority, now_us)
    return request, _approvals(document["approvals"], authority, request)


def _verify(
    observer_key: Ed25519PublicKey,
    authority_receipt_bytes: object,
    approval_bundle_bytes: object,
    now_us: object,
) -> _VerifiedSecurityAuditApproval:
    authority_carrier = _bounded_bytes(
        authority_receipt_bytes, _AUTHORITY_ENVELOPE_MAX_BYTES
    )
    bundle_carrier = _bounded_bytes(
        approval_bundle_bytes, _APPROVAL_BUNDLE_MAX_BYTES
    )
    trusted_now_us = _integer(now_us)
    authority = _authority(authority_carrier, observer_key, trusted_now_us)
    request, approvals = _bundle(
        bundle_carrier, authority, trusted_now_us
    )
    for approval in approvals:
        _verify_ed25519(
            approval.public_key,
            approval.signature,
            _APPROVAL_SIGNATURE_DOMAIN + approval.statement_bytes,
        )
    return _VerifiedSecurityAuditApproval(
        schema_version=_VERIFIED_APPROVAL_SCHEMA,
        operation_id=request.operation_id,
        authority_receipt_digest=authority.digest,
        request_digest=request.digest,
        approval_digest=_digest(bundle_carrier),
        valid_from_us=request.not_before_us,
        valid_until_us=min(authority.expires_at_us, request.expires_at_us),
        cursor=request.cursor,
        approver_ids=(approvals[0].approver_id, approvals[1].approver_id),
        key_ids=(approvals[0].key_id, approvals[1].key_id),
        independence_domains=(
            approvals[0].independence_domain,
            approvals[1].independence_domain,
        ),
    )


class SecurityAuditDualApprovalVerifier:
    """Verify one exact receipt, request, and independent approval pair."""

    __slots__ = ("_observer_key",)

    def __init__(self, observer_public_key: bytes) -> None:
        refused = False
        try:
            key_bytes = _bounded_bytes(observer_public_key, 32)
            if len(key_bytes) != 32:
                raise ValueError
            observer_key = _public_key(key_bytes)
        except Exception:
            refused = True
        if refused:
            raise SecurityAuditApprovalRefused()
        self._observer_key = observer_key

    def verify(
        self,
        authority_receipt_bytes: bytes,
        approval_bundle_bytes: bytes,
        *,
        now_us: int,
    ) -> _VerifiedSecurityAuditApproval:
        """Return normalized evidence or one fixed fresh refusal."""

        refused = False
        try:
            result = _verify(
                self._observer_key,
                authority_receipt_bytes,
                approval_bundle_bytes,
                now_us,
            )
        except Exception:
            refused = True
        if refused:
            raise SecurityAuditApprovalRefused()
        return result


__all__ = (
    "SecurityAuditApprovalRefused",
    "SecurityAuditDualApprovalVerifier",
)
