"""Focused evidence for security-audit dual-approval verification."""

from __future__ import annotations

import ast
import base64
import builtins
import hashlib
import json
import traceback
from dataclasses import dataclass

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from conformance import rewrite_architecture_check
from deployment.postgresql import security_audit_approval
from deployment.postgresql.audit_contract import (
    EXPORT_ACCESS_PURPOSE_IDENTITY,
    EXPORT_FUNCTION_IDENTITY,
    EXPORT_MAX_BYTES,
    EXPORT_MAX_ROWS,
)
from deployment.postgresql.security_audit_approval import (
    SecurityAuditApprovalRefused,
    SecurityAuditDualApprovalVerifier,
)
from deployment.postgresql.security_audit_access import (
    SecurityAuditAccessCursor,
)
from deployment.postgresql.tenant_contract import derive_ed25519_key_id


AUTHORITY_SCHEMA = "ofarm.security-audit-break-glass-authority-receipt.v1"
REQUEST_SCHEMA = "ofarm.security-audit-break-glass-export-request.v2"
STATEMENT_SCHEMA = "ofarm.security-audit-break-glass-export-approval.v1"
BUNDLE_SCHEMA = "ofarm.security-audit-break-glass-approval-bundle.v1"
VERIFIED_SCHEMA = "ofarm.security-audit-break-glass-verified-approval.v1"
AUDIENCE = "ofarm.security-audit-break-glass-export.v1"
AUTHORITY_DOMAIN = (
    b"OFARM_SECURITY_AUDIT_BREAK_GLASS_AUTHORITY_RECEIPT_V1\x00"
)
APPROVAL_DOMAIN = b"OFARM_SECURITY_AUDIT_BREAK_GLASS_EXPORT_APPROVAL_V1\x00"
OPERATION_ID = "123e4567-e89b-42d3-a456-426614174000"
OTHER_OPERATION_ID = "223e4567-e89b-42d3-a456-426614174000"
STORE_MIGRATION_EXECUTION_ID = "018f39f1-a8f1-7a3c-8400-123456789abc"
CANONICAL_CURSOR = (
    "2026-08-17T12:34:56.123456Z/"
    "123e4567-e89b-42d3-a456-426614174000"
)
NOW_US = 1_000_000
AUTHORITY_OBSERVED_US = 900_000
AUTHORITY_EXPIRES_US = 300_900_000
REQUEST_NOT_BEFORE_US = 950_000
REQUEST_EXPIRES_US = 300_800_000


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _public_key(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )


def _key_id(public_key: bytes) -> str:
    thumbprint = _canonical(
        {"crv": "Ed25519", "kty": "OKP", "x": _b64(public_key)}
    )
    return _b64(hashlib.sha256(thumbprint).digest())


@dataclass(frozen=True)
class _ApproverSpec:
    private_key: Ed25519PrivateKey
    approver_id: str
    independence_domain: str

    def document(self) -> dict[str, object]:
        public_key = _public_key(self.private_key)
        return {
            "approverId": self.approver_id,
            "independenceDomain": self.independence_domain,
            "keyId": _key_id(public_key),
            "publicKey": _b64(public_key),
        }


@dataclass(frozen=True)
class _Material:
    observer_private_key: Ed25519PrivateKey
    observer_public_key: bytes
    approvers: tuple[_ApproverSpec, ...]
    authority_receipt_bytes: bytes
    approval_bundle_bytes: bytes


def _default_approvers() -> tuple[_ApproverSpec, ...]:
    return (
        _ApproverSpec(
            Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33))),
            "APPROVER_A",
            "DOMAIN_A",
        ),
        _ApproverSpec(
            Ed25519PrivateKey.from_private_bytes(bytes(range(2, 34))),
            "APPROVER_B",
            "DOMAIN_B",
        ),
        _ApproverSpec(
            Ed25519PrivateKey.from_private_bytes(bytes(range(3, 35))),
            "APPROVER_C",
            "DOMAIN_C",
        ),
    )


def _material(
    *,
    approvers: tuple[_ApproverSpec, ...] | None = None,
    authority_entry_updates: dict[int, dict[str, object]] | None = None,
    authority_updates: dict[str, object] | None = None,
    request_updates: dict[str, object] | None = None,
    statement_updates: dict[int, dict[str, object]] | None = None,
    selected: tuple[int, ...] = (0, 1),
    authority_signer: Ed25519PrivateKey | None = None,
    authority_domain: bytes = AUTHORITY_DOMAIN,
    approval_signers: dict[int, Ed25519PrivateKey] | None = None,
    approval_domain: bytes = APPROVAL_DOMAIN,
    sort_authority: bool = True,
    sort_approvals: bool = True,
) -> _Material:
    observer = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    specs = approvers or _default_approvers()
    entry_updates = authority_entry_updates or {}
    authority_documents = []
    for index, spec in enumerate(specs):
        document = spec.document()
        document.update(entry_updates.get(index, {}))
        authority_documents.append(document)
    if sort_authority:
        authority_documents.sort(
            key=lambda value: (
                value["approverId"],
                value["keyId"],
                value["independenceDomain"],
            )
        )
    else:
        authority_documents.reverse()
    authority_payload_document: dict[str, object] = {
        "approvers": authority_documents,
        "audience": AUDIENCE,
        "expiresAtUnixMicroseconds": AUTHORITY_EXPIRES_US,
        "observedAtUnixMicroseconds": AUTHORITY_OBSERVED_US,
        "schemaVersion": AUTHORITY_SCHEMA,
    }
    authority_payload_document.update(authority_updates or {})
    authority_payload = _canonical(authority_payload_document)
    signer = authority_signer or observer
    authority_receipt = _canonical(
        {
            "payload": _b64(authority_payload),
            "signature": _b64(
                signer.sign(authority_domain + authority_payload)
            ),
        }
    )
    request_document: dict[str, object] = {
        "audience": AUDIENCE,
        "authorityReceiptDigest": _digest(authority_receipt),
        "cursor": None,
        "expiresAtUnixMicroseconds": REQUEST_EXPIRES_US,
        "functionIdentity": EXPORT_FUNCTION_IDENTITY,
        "maxBytes": EXPORT_MAX_BYTES,
        "maxPages": 1,
        "maxRows": EXPORT_MAX_ROWS,
        "notBeforeUnixMicroseconds": REQUEST_NOT_BEFORE_US,
        "operationId": OPERATION_ID,
        "purpose": EXPORT_ACCESS_PURPOSE_IDENTITY,
        "schemaVersion": REQUEST_SCHEMA,
        "storeMigrationExecutionId": STORE_MIGRATION_EXECUTION_ID,
    }
    request_document.update(request_updates or {})
    request_payload = _canonical(request_document)
    request_digest = _digest(request_payload)
    approval_documents = []
    updates = statement_updates or {}
    signers = approval_signers or {}
    for approval_index, authority_index in enumerate(selected):
        authority_entry = specs[authority_index].document()
        authority_entry.update(entry_updates.get(authority_index, {}))
        statement_document: dict[str, object] = {
            "approverId": authority_entry["approverId"],
            "audience": AUDIENCE,
            "authorityReceiptDigest": _digest(authority_receipt),
            "independenceDomain": authority_entry["independenceDomain"],
            "keyId": authority_entry["keyId"],
            "operationId": request_document["operationId"],
            "requestDigest": request_digest,
            "schemaVersion": STATEMENT_SCHEMA,
        }
        statement_document.update(updates.get(approval_index, {}))
        statement_payload = _canonical(statement_document)
        approval_documents.append(
            {
                "signature": _b64(
                    signers.get(
                        approval_index, specs[authority_index].private_key
                    ).sign(approval_domain + statement_payload)
                ),
                "statement": _b64(statement_payload),
            }
        )
    if sort_approvals:
        approval_documents.sort(
            key=lambda value: tuple(
                json.loads(_unb64(value["statement"]))[name]
                for name in ("approverId", "keyId", "independenceDomain")
            )
        )
    else:
        approval_documents.reverse()
    approval_bundle = _canonical(
        {
            "approvals": approval_documents,
            "request": _b64(request_payload),
            "schemaVersion": BUNDLE_SCHEMA,
        }
    )
    return _Material(
        observer_private_key=observer,
        observer_public_key=_public_key(observer),
        approvers=specs,
        authority_receipt_bytes=authority_receipt,
        approval_bundle_bytes=approval_bundle,
    )


def _replace_outer_member(carrier: bytes, name: str, value: object) -> bytes:
    document = json.loads(carrier)
    document[name] = value
    return _canonical(document)


def _replace_signature(carrier: bytes, index: int, signature: bytes) -> bytes:
    document = json.loads(carrier)
    document["approvals"][index]["signature"] = _b64(signature)
    return _canonical(document)


def _replace_statement(
    carrier: bytes,
    index: int,
    statement: bytes | str,
) -> bytes:
    document = json.loads(carrier)
    document["approvals"][index]["statement"] = (
        statement if type(statement) is str else _b64(statement)
    )
    return _canonical(document)


def _replace_request(carrier: bytes, **updates: object) -> bytes:
    document = json.loads(carrier)
    request = json.loads(_unb64(document["request"]))
    request.update(updates)
    document["request"] = _b64(_canonical(request))
    return _canonical(document)


def _verifier(material: _Material) -> SecurityAuditDualApprovalVerifier:
    return SecurityAuditDualApprovalVerifier(material.observer_public_key)


def _assert_refused(
    verifier: SecurityAuditDualApprovalVerifier,
    authority_receipt_bytes: object,
    approval_bundle_bytes: object,
    *,
    now_us: object = NOW_US,
) -> SecurityAuditApprovalRefused:
    with pytest.raises(SecurityAuditApprovalRefused) as caught:
        verifier.verify(
            authority_receipt_bytes,
            approval_bundle_bytes,
            now_us=now_us,
        )
    error = caught.value
    assert type(error) is SecurityAuditApprovalRefused
    assert error.args == ()
    assert str(error) == ""
    assert error.__cause__ is None
    assert error.__context__ is None
    return error


def test_real_ed25519_success_returns_exact_private_normalized_evidence():
    material = _material()
    result = _verifier(material).verify(
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
        now_us=NOW_US,
    )

    assert result.schema_version == VERIFIED_SCHEMA
    assert str(result.operation_id) == OPERATION_ID
    assert str(result.store_migration_execution_id) == \
        STORE_MIGRATION_EXECUTION_ID
    assert result.authority_receipt_digest == _digest(
        material.authority_receipt_bytes
    )
    bundle = json.loads(material.approval_bundle_bytes)
    assert result.request_digest == _digest(_unb64(bundle["request"]))
    assert result.approval_digest == _digest(material.approval_bundle_bytes)
    assert result.valid_from_us == REQUEST_NOT_BEFORE_US
    assert result.valid_until_us == REQUEST_EXPIRES_US
    assert result.cursor is None
    assert result.approver_ids == ("APPROVER_A", "APPROVER_B")
    assert result.key_ids == tuple(
        _key_id(_public_key(spec.private_key))
        for spec in material.approvers[:2]
    )
    assert result.independence_domains == ("DOMAIN_A", "DOMAIN_B")
    assert result.__class__.__name__ == "_VerifiedSecurityAuditApproval"
    assert security_audit_approval.__all__ == (
        "SecurityAuditApprovalRefused",
        "SecurityAuditDualApprovalVerifier",
    )


def test_key_id_matches_existing_boundary_oracle_for_exact_vector():
    public_key = bytes(range(32))
    expected = "P7IdLIpiTZiFaIoOSqbX3JrSyps3hvZ4Y2SieP96XIY"

    assert security_audit_approval._derive_key_id(public_key) == expected
    assert derive_ed25519_key_id(public_key) == expected


@pytest.mark.parametrize(
    "observer_public_key",
    [b"", b"x" * 31, b"x" * 33, bytearray(b"x" * 32), "x" * 32, True],
    ids=("blank", "short", "long", "bytearray", "text", "boolean"),
)
def test_constructor_has_one_exact_fresh_refusal(observer_public_key):
    with pytest.raises(SecurityAuditApprovalRefused) as caught:
        SecurityAuditDualApprovalVerifier(observer_public_key)

    error = caught.value
    assert type(error) is SecurityAuditApprovalRefused
    assert error.args == ()
    assert error.__cause__ is None
    assert error.__context__ is None


@pytest.mark.parametrize(
    "authority",
    [
        b"",
        b"x" * 16_385,
        b"[]",
        b'{"payload":"x","payload":"y","signature":"z"}',
        b'{"payload":NaN,"signature":"z"}',
        b"\xef\xbb\xbf{}",
        bytearray(b"{}"),
    ],
    ids=(
        "blank",
        "oversized",
        "wrong-root",
        "duplicate-member",
        "non-json-constant",
        "bom",
        "non-bytes",
    ),
)
def test_authority_carrier_type_size_and_canonical_failures_refuse(authority):
    material = _material()
    _assert_refused(
        _verifier(material), authority, material.approval_bundle_bytes
    )


def test_whitespace_extra_member_and_padded_base64url_refuse():
    material = _material()
    verifier = _verifier(material)
    document = json.loads(material.authority_receipt_bytes)
    padded = _replace_outer_member(
        material.authority_receipt_bytes, "payload", document["payload"] + "="
    )
    extra = json.loads(material.authority_receipt_bytes)
    extra["extra"] = 1

    _assert_refused(
        verifier,
        material.authority_receipt_bytes + b" ",
        material.approval_bundle_bytes,
    )
    _assert_refused(verifier, _canonical(extra), material.approval_bundle_bytes)
    _assert_refused(verifier, padded, material.approval_bundle_bytes)


@pytest.mark.parametrize(
    "bundle",
    [
        b"",
        b"x" * 16_385,
        b"[]",
        b'{"approvals":[],"request":"x","request":"y",'
        b'"schemaVersion":"wrong"}',
        b'{"approvals":NaN,"request":"x","schemaVersion":"wrong"}',
        bytearray(b"{}"),
    ],
    ids=(
        "blank",
        "oversized",
        "wrong-root",
        "duplicate-member",
        "non-json-constant",
        "non-bytes",
    ),
)
def test_bundle_carrier_type_size_and_canonical_failures_refuse(bundle):
    material = _material()
    _assert_refused(
        _verifier(material), material.authority_receipt_bytes, bundle
    )


def test_bundle_whitespace_extra_member_and_wrong_schema_refuse():
    material = _material()
    verifier = _verifier(material)
    extra = json.loads(material.approval_bundle_bytes)
    extra["extra"] = 1
    wrong_schema = json.loads(material.approval_bundle_bytes)
    wrong_schema["schemaVersion"] = "wrong"

    for bundle in (
        material.approval_bundle_bytes + b" ",
        _canonical(extra),
        _canonical(wrong_schema),
    ):
        _assert_refused(verifier, material.authority_receipt_bytes, bundle)


def test_decoded_authority_payload_and_signature_bounds_refuse():
    material = _material()
    verifier = _verifier(material)
    malformed_payload = _replace_outer_member(
        material.authority_receipt_bytes, "payload", _b64(b"{}")
    )
    short_signature = _replace_outer_member(
        material.authority_receipt_bytes, "signature", _b64(b"x" * 63)
    )

    for authority in (malformed_payload, short_signature):
        _assert_refused(
            verifier, authority, material.approval_bundle_bytes
        )


def test_authority_requires_two_through_sixteen_entries():
    one = _material(approvers=_default_approvers()[:1], selected=(0,))
    seventeen_specs = tuple(
        _ApproverSpec(
            Ed25519PrivateKey.from_private_bytes(bytes([index]) * 32),
            f"APPROVER_{index:02d}",
            f"DOMAIN_{index:02d}",
        )
        for index in range(1, 18)
    )
    seventeen = _material(approvers=seventeen_specs)

    for material in (one, seventeen):
        _assert_refused(
            _verifier(material),
            material.authority_receipt_bytes,
            material.approval_bundle_bytes,
        )


@pytest.mark.parametrize(
    "now_us",
    [-1, 9_223_372_036_854_775_808, True, 1.0, "1000000"],
    ids=("negative", "too-large", "boolean", "float", "text"),
)
def test_now_us_is_exact_bounded_integer(now_us):
    material = _material()
    _assert_refused(
        _verifier(material),
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
        now_us=now_us,
    )


def test_bundle_is_type_and_size_checked_before_observer_crypto(monkeypatch):
    material = _material()
    calls = []
    real = security_audit_approval._verify_ed25519

    def counted(key, signature, message):
        calls.append(message)
        return real(key, signature, message)

    monkeypatch.setattr(security_audit_approval, "_verify_ed25519", counted)
    _assert_refused(
        _verifier(material),
        material.authority_receipt_bytes,
        bytearray(material.approval_bundle_bytes),
    )
    assert calls == []


def test_authority_requires_configured_observer_domain_schema_and_audience():
    material = _material()
    attacker = Ed25519PrivateKey.from_private_bytes(bytes(range(32, 64)))
    cases = (
        _material(authority_signer=attacker),
        _material(authority_domain=b"WRONG\x00"),
        _material(authority_updates={"schemaVersion": "wrong"}),
        _material(authority_updates={"audience": "wrong"}),
    )

    for case in cases:
        _assert_refused(
            SecurityAuditDualApprovalVerifier(material.observer_public_key),
            case.authority_receipt_bytes,
            case.approval_bundle_bytes,
        )


def test_authority_entry_order_uniqueness_and_identity_bounds_refuse():
    duplicate = _material(
        authority_entry_updates={1: {"approverId": "APPROVER_A"}}
    )
    wrong_key_id = _material(
        authority_entry_updates={0: {"keyId": "A" * 43}}
    )
    overlong = _material(
        authority_entry_updates={0: {"approverId": "A" * 129}}
    )
    unsorted = _material(sort_authority=False)

    for material in (duplicate, wrong_key_id, overlong, unsorted):
        _assert_refused(
            _verifier(material),
            material.authority_receipt_bytes,
            material.approval_bundle_bytes,
        )


@pytest.mark.parametrize(
    "authority_updates",
    [
        {"observedAtUnixMicroseconds": NOW_US + 1},
        {"expiresAtUnixMicroseconds": NOW_US},
        {
            "observedAtUnixMicroseconds": 0,
            "expiresAtUnixMicroseconds": 300_000_001,
        },
        {"observedAtUnixMicroseconds": True},
    ],
    ids=("future", "expired", "overlong", "boolean"),
)
def test_authority_time_window_refuses(authority_updates):
    material = _material(authority_updates=authority_updates)
    _assert_refused(
        _verifier(material),
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
    )


@pytest.mark.parametrize(
    "request_updates",
    [
        {"notBeforeUnixMicroseconds": AUTHORITY_OBSERVED_US - 1},
        {"notBeforeUnixMicroseconds": NOW_US + 1},
        {"expiresAtUnixMicroseconds": NOW_US},
        {"expiresAtUnixMicroseconds": AUTHORITY_EXPIRES_US + 1},
        {
            "notBeforeUnixMicroseconds": 0,
            "expiresAtUnixMicroseconds": 300_000_001,
        },
        {"expiresAtUnixMicroseconds": True},
    ],
    ids=(
        "before-receipt",
        "future",
        "expired",
        "outside-receipt",
        "overlong",
        "boolean",
    ),
)
def test_request_time_window_refuses(request_updates):
    material = _material(request_updates=request_updates)
    _assert_refused(
        _verifier(material),
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
    )


def test_currentness_boundaries_and_still_valid_older_receipt_are_honest():
    material = _material(
        authority_updates={"expiresAtUnixMicroseconds": 1_100_000},
        request_updates={
            "notBeforeUnixMicroseconds": NOW_US,
            "expiresAtUnixMicroseconds": 1_100_000,
        },
    )
    verifier = _verifier(material)

    assert verifier.verify(
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
        now_us=NOW_US,
    ).valid_until_us == 1_100_000
    assert verifier.verify(
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
        now_us=1_099_999,
    ).valid_until_us == 1_100_000
    _assert_refused(
        verifier,
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
        now_us=1_100_000,
    )


@pytest.mark.parametrize(
    "request_updates",
    [
        {"purpose": "OTHER"},
        {"functionIdentity": "other()"},
        {"maxPages": 2},
        {"maxPages": True},
        {"maxRows": EXPORT_MAX_ROWS + 1},
        {"maxRows": float(EXPORT_MAX_ROWS)},
        {"maxBytes": EXPORT_MAX_BYTES + 1},
        {"cursor": "not-a-cursor"},
        {"operationId": OPERATION_ID.upper()},
        {"operationId": "123e4567-e89b-12d3-a456-426614174000"},
        {"storeMigrationExecutionId": STORE_MIGRATION_EXECUTION_ID.upper()},
        {"storeMigrationExecutionId": "00000000-0000-0000-0000-000000000000"},
        {"storeMigrationExecutionId": True},
    ],
    ids=(
        "purpose",
        "function",
        "pages",
        "pages-boolean",
        "rows",
        "rows-float",
        "bytes",
        "cursor",
        "uuid-case",
        "uuid-version",
        "store-uuid-case",
        "store-uuid-nil",
        "store-uuid-type",
    ),
)
def test_fixed_request_substitution_refuses(request_updates):
    material = _material(request_updates=request_updates)
    _assert_refused(
        _verifier(material),
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
    )


def test_null_and_exact_canonical_cursor_are_the_only_supported_forms():
    material = _material(request_updates={"cursor": CANONICAL_CURSOR})
    result = _verifier(material).verify(
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
        now_us=NOW_US,
    )

    assert type(result.cursor) is SecurityAuditAccessCursor
    assert result.cursor.render() == CANONICAL_CURSOR


def test_receipt_request_and_statement_digest_substitution_refuses():
    first = _material()
    second = _material(authority_updates={"observedAtUnixMicroseconds": 899_999})
    wrong_request_digest = _material(
        statement_updates={0: {"requestDigest": "sha256:" + "0" * 64}}
    )
    wrong_receipt_digest = _material(
        request_updates={"authorityReceiptDigest": "sha256:" + "0" * 64}
    )

    _assert_refused(
        _verifier(second),
        second.authority_receipt_bytes,
        first.approval_bundle_bytes,
    )
    for material in (wrong_request_digest, wrong_receipt_digest):
        _assert_refused(
            _verifier(material),
            material.authority_receipt_bytes,
            material.approval_bundle_bytes,
        )


def test_cross_request_statement_and_mutated_signature_refuse():
    material = _material()
    cross_request = _replace_request(
        material.approval_bundle_bytes, operationId=OTHER_OPERATION_ID
    )
    changed_signature = _replace_signature(
        material.approval_bundle_bytes, 0, b"\x00" * 64
    )

    _assert_refused(
        _verifier(material), material.authority_receipt_bytes, cross_request
    )
    _assert_refused(
        _verifier(material), material.authority_receipt_bytes, changed_signature
    )


def test_statement_canonical_base64url_shape_and_signature_bounds_refuse():
    material = _material()
    bundle_document = json.loads(material.approval_bundle_bytes)
    statement_text = bundle_document["approvals"][0]["statement"]
    statement_bytes = _unb64(statement_text)
    statement_document = json.loads(statement_bytes)
    statement_document["extra"] = 1
    cases = (
        _replace_statement(
            material.approval_bundle_bytes, 0, statement_bytes + b" "
        ),
        _replace_statement(
            material.approval_bundle_bytes, 0, statement_text + "="
        ),
        _replace_statement(material.approval_bundle_bytes, 0, b"[]"),
        _replace_statement(
            material.approval_bundle_bytes, 0, _canonical(statement_document)
        ),
        _replace_statement(material.approval_bundle_bytes, 0, b"x" * 2_049),
        _replace_signature(material.approval_bundle_bytes, 0, b"x" * 63),
    )

    for bundle in cases:
        _assert_refused(
            _verifier(material), material.authority_receipt_bytes, bundle
        )


def test_exactly_two_sorted_approvals_are_required():
    one = _material(selected=(0,))
    three = _material(selected=(0, 1, 2))
    unsorted = _material(sort_approvals=False)

    for material in (one, three, unsorted):
        _assert_refused(
            _verifier(material),
            material.authority_receipt_bytes,
            material.approval_bundle_bytes,
        )


def test_pair_requires_distinct_approver_key_and_independence_domain():
    repeated = _material(selected=(0, 0))
    same_domain = _material(
        authority_entry_updates={1: {"independenceDomain": "DOMAIN_A"}}
    )
    absent = _material(
        statement_updates={1: {"approverId": "APPROVER_MISSING"}}
    )

    for material in (repeated, same_domain, absent):
        _assert_refused(
            _verifier(material),
            material.authority_receipt_bytes,
            material.approval_bundle_bytes,
        )


def test_repeated_verification_is_equal_but_result_is_not_admission():
    material = _material()
    verifier = _verifier(material)
    first = verifier.verify(
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
        now_us=NOW_US,
    )
    second = verifier.verify(
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
        now_us=NOW_US,
    )

    assert first == second
    assert not hasattr(first, "consumed")
    assert not hasattr(first, "admitted")
    _assert_refused(
        verifier, first, material.approval_bundle_bytes, now_us=NOW_US
    )


def test_refusal_trace_does_not_link_or_format_dependency_canary():
    material = _material()
    canary = "RUNTIME_GENERATED_DAV_CANARY_5f6d7c"
    error = _assert_refused(
        _verifier(material),
        ("{" + canary + "}").encode(),
        material.approval_bundle_bytes,
    )
    rendered = "".join(
        traceback.TracebackException.from_exception(
            error, capture_locals=False
        ).format()
    )

    assert canary not in rendered


def test_baseexception_propagates_unchanged(monkeypatch):
    material = _material()
    interrupt = KeyboardInterrupt()

    def interrupted(_data, _maximum):
        raise interrupt

    monkeypatch.setattr(
        security_audit_approval, "_canonical_object", interrupted
    )
    with pytest.raises(KeyboardInterrupt) as caught:
        _verifier(material).verify(
            material.authority_receipt_bytes,
            material.approval_bundle_bytes,
            now_us=NOW_US,
        )
    assert caught.value is interrupt


def test_valid_verification_uses_no_direct_effect_builtins(monkeypatch):
    material = _material()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("direct effect builtin was called")

    for name in ("open", "print", "input", "breakpoint"):
        monkeypatch.setattr(builtins, name, forbidden)

    assert _verifier(material).verify(
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
        now_us=NOW_US,
    ).schema_version == VERIFIED_SCHEMA


def test_architecture_surface_accepts_exact_module_and_rejects_effects():
    source = rewrite_architecture_check.ROOT.joinpath(
        "deployment/postgresql/security_audit_approval.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert (
        rewrite_architecture_check._security_audit_approval_surface_violations(
            tree
        )
        == []
    )
    for source_line in (
        "open('/tmp/x', 'wb')",
        "print('verified')",
        "input()",
        "breakpoint()",
        "from time import time",
        "from uuid import uuid4",
        "now_us = 1",
    ):
        mutated = ast.Module(
            body=[*tree.body, *ast.parse(source_line).body], type_ignores=[]
        )
        assert rewrite_architecture_check._security_audit_approval_surface_violations(
            mutated
        )


def test_signature_checks_have_exact_order_counts_and_no_retry(monkeypatch):
    material = _material()
    real = security_audit_approval._verify_ed25519
    counts = {"observer": 0, "approver": 0}

    def counted(key, signature, message):
        if message.startswith(AUTHORITY_DOMAIN):
            counts["observer"] += 1
        else:
            assert message.startswith(APPROVAL_DOMAIN)
            counts["approver"] += 1
        return real(key, signature, message)

    monkeypatch.setattr(security_audit_approval, "_verify_ed25519", counted)

    def refuse(authority, bundle, expected):
        counts.update(observer=0, approver=0)
        _assert_refused(_verifier(material), authority, bundle)
        assert counts == expected

    refuse(b"{}", material.approval_bundle_bytes, {"observer": 0, "approver": 0})
    invalid_observer = _replace_outer_member(
        material.authority_receipt_bytes, "signature", _b64(b"\x00" * 64)
    )
    refuse(
        invalid_observer,
        material.approval_bundle_bytes,
        {"observer": 1, "approver": 0},
    )
    malformed_request = _replace_outer_member(
        material.approval_bundle_bytes, "request", _b64(b"{}")
    )
    refuse(
        material.authority_receipt_bytes,
        malformed_request,
        {"observer": 1, "approver": 0},
    )
    invalid_first = _replace_signature(
        material.approval_bundle_bytes, 0, b"\x00" * 64
    )
    refuse(
        material.authority_receipt_bytes,
        invalid_first,
        {"observer": 1, "approver": 1},
    )
    invalid_second = _replace_signature(
        material.approval_bundle_bytes, 1, b"\x00" * 64
    )
    refuse(
        material.authority_receipt_bytes,
        invalid_second,
        {"observer": 1, "approver": 2},
    )
    counts.update(observer=0, approver=0)
    _verifier(material).verify(
        material.authority_receipt_bytes,
        material.approval_bundle_bytes,
        now_us=NOW_US,
    )
    assert counts == {"observer": 1, "approver": 2}
