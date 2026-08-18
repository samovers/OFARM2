"""Focused evidence for bounded security-audit authority-receipt issuance."""

from __future__ import annotations

import ast
import base64
import builtins
import hashlib
import json
import traceback
from dataclasses import dataclass
from uuid import UUID

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from google.cloud import kms_v1

from conformance import rewrite_architecture_check
from deployment.postgresql import security_audit_authority
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
from deployment.postgresql.security_audit_authority import (
    SecurityAuditAuthorityReceiptIssuer,
    SecurityAuditAuthorityReceiptRefused,
)
from deployment.postgresql.tenant_contract import (
    crc32c,
    derive_ed25519_key_id,
    valid_google_kms_key_version_resource,
)
from kernel.google_kms_signer import GoogleKmsSigner, KmsSigningError
from kernel.signing_authority import SigningAuthority


MANIFEST_SCHEMA = "ofarm.security-audit-break-glass-approver-manifest.v1"
AUTHORITY_SCHEMA = "ofarm.security-audit-break-glass-authority-receipt.v1"
REQUEST_SCHEMA = "ofarm.security-audit-break-glass-export-request.v1"
STATEMENT_SCHEMA = "ofarm.security-audit-break-glass-export-approval.v1"
BUNDLE_SCHEMA = "ofarm.security-audit-break-glass-approval-bundle.v1"
AUDIENCE = "ofarm.security-audit-break-glass-export.v1"
AUTHORITY_DOMAIN = (
    b"OFARM_SECURITY_AUDIT_BREAK_GLASS_AUTHORITY_RECEIPT_V1\x00"
)
APPROVAL_DOMAIN = b"OFARM_SECURITY_AUDIT_BREAK_GLASS_EXPORT_APPROVAL_V1\x00"
RESOURCE = (
    "projects/example/locations/europe-west1/keyRings/ofarm/cryptoKeys/"
    "security-audit-observer/cryptoKeyVersions/1"
)
NOW_US = 1_000_000
LIFETIME_US = 300_000_000
MAX_UNIX_US = 9_223_372_036_854_775_807
OPERATION_ID = "123e4567-e89b-42d3-a456-426614174000"
_DEFAULT_RESPONSE = object()


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
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _public_key(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )


@dataclass(frozen=True)
class _Approver:
    private_key: Ed25519PrivateKey
    approver_id: str
    independence_domain: str

    def manifest_document(self) -> dict[str, object]:
        return {
            "approverId": self.approver_id,
            "independenceDomain": self.independence_domain,
            "publicKey": _b64(_public_key(self.private_key)),
        }

    def authority_document(self) -> dict[str, object]:
        public_key = _public_key(self.private_key)
        return {
            **self.manifest_document(),
            "keyId": derive_ed25519_key_id(public_key),
        }


def _approvers(count: int = 3) -> tuple[_Approver, ...]:
    return tuple(
        _Approver(
            Ed25519PrivateKey.from_private_bytes(
                bytes(range(index + 1, index + 33))
            ),
            f"APPROVER_{index:02d}",
            f"DOMAIN_{index:02d}",
        )
        for index in range(count)
    )


def _manifest_document(
    approvers: tuple[_Approver, ...] | None = None,
) -> dict[str, object]:
    entries = [item.manifest_document() for item in approvers or _approvers()]
    entries.sort(
        key=lambda value: (
            value["approverId"],
            derive_ed25519_key_id(_unb64(value["publicKey"])),
            value["independenceDomain"],
        )
    )
    return {
        "approvers": entries,
        "audience": AUDIENCE,
        "schemaVersion": MANIFEST_SCHEMA,
    }


def _manifest(approvers: tuple[_Approver, ...] | None = None) -> bytes:
    return _canonical(_manifest_document(approvers))


class _KmsClient:
    def __init__(
        self,
        private_key: Ed25519PrivateKey,
        *,
        resource: str = RESOURCE,
        changes: dict[str, object] | None = None,
        response_signer: Ed25519PrivateKey | None = None,
        response: object = _DEFAULT_RESPONSE,
        failure: BaseException | None = None,
    ) -> None:
        self.private_key = private_key
        self.resource = resource
        self.changes = changes or {}
        self.response_signer = response_signer or private_key
        self.response = response
        self.failure = failure
        self.calls: list[tuple[object, object, object]] = []

    def asymmetric_sign(self, *, request, retry, timeout):
        self.calls.append((request, retry, timeout))
        if self.failure is not None:
            raise self.failure
        if self.response is not _DEFAULT_RESPONSE:
            return self.response
        signature = self.changes.get(
            "signature", self.response_signer.sign(request.data)
        )
        values = {
            "name": self.resource,
            "signature": signature,
            "signature_crc32c": crc32c(signature),
            "verified_data_crc32c": True,
            "verified_digest_crc32c": False,
            "protection_level": kms_v1.ProtectionLevel.HSM,
            **self.changes,
        }
        return kms_v1.AsymmetricSignResponse(**values)


def _observer() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes(range(32)))


def _issuer(
    *,
    client: object | None = None,
    observer: Ed25519PrivateKey | None = None,
    manifest: object | None = None,
    resource: object = RESOURCE,
) -> tuple[SecurityAuditAuthorityReceiptIssuer, _KmsClient, Ed25519PrivateKey]:
    root = observer or _observer()
    kms_client = client or _KmsClient(root)
    issuer = SecurityAuditAuthorityReceiptIssuer(
        kms_client,
        kms_key_version_resource=resource,
        observer_public_key=_public_key(root),
        approver_manifest_bytes=(
            _manifest() if manifest is None else manifest
        ),
    )
    return issuer, kms_client, root


def _assert_refused(
    issuer: SecurityAuditAuthorityReceiptIssuer,
    *,
    now_us: object = NOW_US,
) -> SecurityAuditAuthorityReceiptRefused:
    with pytest.raises(SecurityAuditAuthorityReceiptRefused) as caught:
        issuer.issue(now_us=now_us)
    error = caught.value
    assert type(error) is SecurityAuditAuthorityReceiptRefused
    assert error.args == ()
    assert str(error) == ""
    assert error.__cause__ is None
    assert error.__context__ is None
    return error


def _assert_constructor_refused(
    *,
    client: object,
    observer_public_key: object,
    manifest: object,
    resource: object = RESOURCE,
) -> SecurityAuditAuthorityReceiptRefused:
    with pytest.raises(SecurityAuditAuthorityReceiptRefused) as caught:
        SecurityAuditAuthorityReceiptIssuer(
            client,
            kms_key_version_resource=resource,
            observer_public_key=observer_public_key,
            approver_manifest_bytes=manifest,
        )
    error = caught.value
    assert type(error) is SecurityAuditAuthorityReceiptRefused
    assert error.args == ()
    assert str(error) == ""
    assert error.__cause__ is None
    assert error.__context__ is None
    return error


def _receipt_payload(receipt: bytes) -> bytes:
    return _unb64(json.loads(receipt)["payload"])


def _tenant_authority(public_key: bytes) -> SigningAuthority:
    digest = "sha256:" + "0" * 64
    identity = UUID("123e4567-e89b-42d3-a456-426614174000")
    return SigningAuthority(
        binder_instance_id=identity,
        audience="test",
        capability_contract_digest=digest,
        candidate_id=identity,
        kid="test",
        candidate_digest=digest,
        public_key=public_key,
        public_key_digest=digest,
        kms_key_version_resource=RESOURCE,
        kms_attestation_digest=digest,
        admission_state="OPEN",
        lifecycle_head_sequence=1,
        lifecycle_head_id=identity,
        lifecycle_head_digest=digest,
        issuance_start_us=0,
        issuance_end_us=1,
        kms_evidence_digest=digest,
        iam_evidence_digest=digest,
        observed_at_us=0,
    )


def _approval_bundle(
    receipt: bytes,
    approvers: tuple[_Approver, ...],
    *,
    request_expires_us: int = NOW_US + 100_000_000,
) -> bytes:
    request = _canonical(
        {
            "audience": AUDIENCE,
            "authorityReceiptDigest": _digest(receipt),
            "cursor": None,
            "expiresAtUnixMicroseconds": request_expires_us,
            "functionIdentity": EXPORT_FUNCTION_IDENTITY,
            "maxBytes": EXPORT_MAX_BYTES,
            "maxPages": 1,
            "maxRows": EXPORT_MAX_ROWS,
            "notBeforeUnixMicroseconds": NOW_US,
            "operationId": OPERATION_ID,
            "purpose": EXPORT_ACCESS_PURPOSE_IDENTITY,
            "schemaVersion": REQUEST_SCHEMA,
        }
    )
    request_digest = _digest(request)
    approvals = []
    for item in approvers[:2]:
        authority = item.authority_document()
        statement = _canonical(
            {
                "approverId": authority["approverId"],
                "audience": AUDIENCE,
                "authorityReceiptDigest": _digest(receipt),
                "independenceDomain": authority["independenceDomain"],
                "keyId": authority["keyId"],
                "operationId": OPERATION_ID,
                "requestDigest": request_digest,
                "schemaVersion": STATEMENT_SCHEMA,
            }
        )
        approvals.append(
            {
                "signature": _b64(item.private_key.sign(APPROVAL_DOMAIN + statement)),
                "statement": _b64(statement),
            }
        )
    approvals.sort(
        key=lambda value: tuple(
            json.loads(_unb64(value["statement"]))[name]
            for name in ("approverId", "keyId", "independenceDomain")
        )
    )
    return _canonical(
        {
            "approvals": approvals,
            "request": _b64(request),
            "schemaVersion": BUNDLE_SCHEMA,
        }
    )


def test_real_ed25519_success_returns_exact_canonical_receipt():
    specs = _approvers()
    root = _observer()
    client = _KmsClient(root)
    issuer, _, _ = _issuer(client=client, observer=root, manifest=_manifest(specs))

    receipt = issuer.issue(now_us=NOW_US)

    assert type(receipt) is bytes
    assert 1 <= len(receipt) <= 16_384
    assert receipt == _canonical(json.loads(receipt))
    envelope = json.loads(receipt)
    assert set(envelope) == {"payload", "signature"}
    payload = _receipt_payload(receipt)
    document = json.loads(payload)
    assert payload == _canonical(document)
    assert document == {
        "approvers": [item.authority_document() for item in specs],
        "audience": AUDIENCE,
        "expiresAtUnixMicroseconds": NOW_US + LIFETIME_US,
        "observedAtUnixMicroseconds": NOW_US,
        "schemaVersion": AUTHORITY_SCHEMA,
    }
    root.public_key().verify(
        _unb64(envelope["signature"]), AUTHORITY_DOMAIN + payload
    )
    assert security_audit_authority.__all__ == (
        "SecurityAuditAuthorityReceiptIssuer",
        "SecurityAuditAuthorityReceiptRefused",
    )


def test_key_id_crc32c_and_real_signing_bytes_match_existing_oracles():
    public_key = bytes(range(32))
    expected = "P7IdLIpiTZiFaIoOSqbX3JrSyps3hvZ4Y2SieP96XIY"
    assert security_audit_authority._derive_key_id(public_key) == expected
    assert derive_ed25519_key_id(public_key) == expected
    assert security_audit_authority._crc32c(b"123456789") == 0xE3069283
    assert crc32c(b"123456789") == 0xE3069283

    issuer, client, _ = _issuer()
    receipt = issuer.issue(now_us=NOW_US)
    request = client.calls[0][0]
    signature = _unb64(json.loads(receipt)["signature"])
    assert security_audit_authority._crc32c(request.data) == crc32c(request.data)
    assert security_audit_authority._crc32c(signature) == crc32c(signature)


@pytest.mark.parametrize(
    ("expected", "resource"),
    [
        (True, RESOURCE),
        (
            True,
            "projects/a1234z/locations/global/keyRings/r/cryptoKeys/k/"
            "cryptoKeyVersions/999",
        ),
        (
            False,
            "projects/a123z/locations/global/keyRings/r/cryptoKeys/k/"
            "cryptoKeyVersions/1",
        ),
        (
            False,
            "projects/example/locations/GLOBAL/keyRings/r/cryptoKeys/k/"
            "cryptoKeyVersions/1",
        ),
        (False, "projects/example/locations/global/keyRings/r/cryptoKeys/k"),
        (
            False,
            "projects/example/locations/global/keyRings/r/cryptoKeys/k/"
            "cryptoKeyVersions/0",
        ),
        (
            False,
            "projects/example/locations/global/keyRings/r/cryptoKeys/k/"
            "cryptoKeyVersions/01",
        ),
        (
            False,
            "projects/example/locations/global/keyRings/r/cryptoKeys/k/"
            "cryptoKeyVersions/1/trailing",
        ),
    ],
)
def test_resource_matrix_matches_existing_oracle(expected, resource):
    root = _observer()
    client = _KmsClient(root, resource=resource)
    assert valid_google_kms_key_version_resource(resource) is expected
    if expected:
        SecurityAuditAuthorityReceiptIssuer(
            client,
            kms_key_version_resource=resource,
            observer_public_key=_public_key(root),
            approver_manifest_bytes=_manifest(),
        )
    else:
        _assert_constructor_refused(
            client=client,
            resource=resource,
            observer_public_key=_public_key(root),
            manifest=_manifest(),
        )
    assert client.calls == []


def test_constructor_refuses_client_and_observer_key_shape_before_kms():
    root = _observer()

    class MissingClient:
        pass

    class NonCallableClient:
        asymmetric_sign = 1

    for client in (MissingClient(), NonCallableClient()):
        _assert_constructor_refused(
            client=client,
            observer_public_key=_public_key(root),
            manifest=_manifest(),
        )
    for public_key in (
        b"",
        b"x" * 31,
        b"x" * 33,
        bytearray(b"x" * 32),
        "x" * 32,
        True,
    ):
        client = _KmsClient(root)
        _assert_constructor_refused(
            client=client,
            observer_public_key=public_key,
            manifest=_manifest(),
        )
        assert client.calls == []


def test_manifest_carrier_and_canonical_failures_refuse_before_kms():
    root = _observer()
    document = _manifest_document()
    duplicate = (
        b'{"approvers":[],"audience":"x","audience":"y",'
        b'"schemaVersion":"z"}'
    )
    raw_non_ascii = json.dumps(
        {**document, "audience": "\u00e9"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    cases: tuple[object, ...] = (
        b"",
        b"x" * 8_193,
        b"[]",
        b"{}",
        b"\xef\xbb\xbf{}",
        b'{"approvers":NaN}',
        duplicate,
        bytearray(_manifest()),
        json.dumps(document).encode("ascii"),
        raw_non_ascii,
    )
    for carrier in cases:
        client = _KmsClient(root)
        _assert_constructor_refused(
            client=client,
            observer_public_key=_public_key(root),
            manifest=carrier,
        )
        assert client.calls == []


def test_manifest_member_type_identity_order_and_uniqueness_fail_closed():
    root = _observer()
    documents = []
    for update in (
        {"schemaVersion": "wrong"},
        {"audience": "wrong"},
        {"extra": "x"},
        {"approvers": _manifest_document()["approvers"][:1]},
        {"approvers": _manifest_document(_approvers(17))["approvers"]},
    ):
        value = _manifest_document()
        value.update(update)
        documents.append(value)

    def changed_entry(**updates):
        value = _manifest_document()
        value["approvers"][0].update(updates)
        return value

    documents.extend(
        (
            changed_entry(approverId=""),
            changed_entry(approverId="-wrong"),
            changed_entry(approverId="A" * 129),
            changed_entry(independenceDomain=""),
            changed_entry(publicKey=_manifest_document()["approvers"][0]["publicKey"] + "="),
            changed_entry(publicKey="eA"),
            changed_entry(keyId="caller-owned"),
        )
    )
    unsorted = _manifest_document()
    unsorted["approvers"].reverse()
    documents.append(unsorted)
    duplicate_id = _manifest_document()
    duplicate_id["approvers"][1]["approverId"] = (
        duplicate_id["approvers"][0]["approverId"]
    )
    duplicate_id["approvers"].sort(
        key=lambda value: (
            value["approverId"],
            derive_ed25519_key_id(_unb64(value["publicKey"])),
            value["independenceDomain"],
        )
    )
    documents.append(duplicate_id)
    duplicate_key = _manifest_document()
    duplicate_key["approvers"][1]["publicKey"] = (
        duplicate_key["approvers"][0]["publicKey"]
    )
    duplicate_key["approvers"].sort(
        key=lambda value: (
            value["approverId"],
            derive_ed25519_key_id(_unb64(value["publicKey"])),
            value["independenceDomain"],
        )
    )
    documents.append(duplicate_key)

    for document in documents:
        client = _KmsClient(root)
        _assert_constructor_refused(
            client=client,
            observer_public_key=_public_key(root),
            manifest=_canonical(document),
        )
        assert client.calls == []


@pytest.mark.parametrize(
    "now_us",
    [True, False, 1.0, "1", b"1", -1, MAX_UNIX_US - LIFETIME_US + 1],
    ids=("true", "false", "float", "text", "bytes", "negative", "overflow"),
)
def test_invalid_time_refuses_before_kms(now_us):
    issuer, client, _ = _issuer()
    _assert_refused(issuer, now_us=now_us)
    assert client.calls == []


def test_maximum_nonoverflowing_time_is_accepted_exactly():
    issuer, client, _ = _issuer()
    now_us = MAX_UNIX_US - LIFETIME_US
    receipt = issuer.issue(now_us=now_us)
    payload = json.loads(_receipt_payload(receipt))
    assert payload["observedAtUnixMicroseconds"] == now_us
    assert payload["expiresAtUnixMicroseconds"] == MAX_UNIX_US
    assert len(client.calls) == 1


def test_request_is_raw_data_crc_no_retry_fixed_timeout_and_one_attempt():
    issuer, client, _ = _issuer()
    first = issuer.issue(now_us=NOW_US)
    second = issuer.issue(now_us=NOW_US)

    assert first == second
    assert len(client.calls) == 2
    for request, retry, timeout in client.calls:
        payload = _receipt_payload(first)
        assert type(request) is kms_v1.AsymmetricSignRequest
        assert request.name == RESOURCE
        assert request.data == AUTHORITY_DOMAIN + payload
        assert 55 <= len(request.data) <= 12_342
        assert request.data_crc32c == crc32c(request.data)
        assert "data" in request
        assert "data_crc32c" in request
        assert "digest" not in request
        assert "digest_crc32c" not in request
        assert retry is None
        assert timeout == 5.0


def test_request_matches_existing_google_kms_signer_test_side_only():
    issuer, issuer_client, root = _issuer()
    receipt = issuer.issue(now_us=NOW_US)
    issuer_request, issuer_retry, issuer_timeout = issuer_client.calls[0]
    signing_input = AUTHORITY_DOMAIN + _receipt_payload(receipt)
    tenant_client = _KmsClient(root)

    signature = GoogleKmsSigner(tenant_client).sign(
        signing_input, _tenant_authority(_public_key(root))
    )

    tenant_request, tenant_retry, tenant_timeout = tenant_client.calls[0]
    assert signature == _unb64(json.loads(receipt)["signature"])
    assert tenant_request.name == issuer_request.name
    assert tenant_request.data == issuer_request.data
    assert tenant_request.data_crc32c == issuer_request.data_crc32c
    for request in (issuer_request, tenant_request):
        assert "data" in request
        assert "data_crc32c" in request
        assert "digest" not in request
        assert "digest_crc32c" not in request
    assert (issuer_retry, tenant_retry) == (None, None)
    assert (issuer_timeout, tenant_timeout) == (5.0, 5.0)


@pytest.mark.parametrize(
    "changes",
    [
        {"name": RESOURCE.replace("/1", "/2")},
        {"protection_level": kms_v1.ProtectionLevel.SOFTWARE},
        {"verified_data_crc32c": False},
        {"verified_digest_crc32c": True},
        {"signature": b"x" * 63},
        {"signature_crc32c": 0},
        {"signature": b"x" * 64},
    ],
    ids=(
        "sibling-name",
        "software",
        "data-unverified",
        "digest-verified",
        "short-signature",
        "wrong-crc",
        "wrong-key-material",
    ),
)
def test_common_response_mutations_match_existing_signer_refusal(changes):
    root = _observer()
    issuer_client = _KmsClient(root, changes=changes)
    issuer, _, _ = _issuer(client=issuer_client, observer=root)
    _assert_refused(issuer)
    assert len(issuer_client.calls) == 1
    signing_input = issuer_client.calls[0][0].data

    tenant_client = _KmsClient(root, changes=changes)
    with pytest.raises(KmsSigningError):
        GoogleKmsSigner(tenant_client).sign(
            signing_input, _tenant_authority(_public_key(root))
        )
    assert len(tenant_client.calls) == 1


def test_issuer_only_response_type_crc_bounds_and_other_key_refuse():
    root = _observer()
    other = Ed25519PrivateKey.from_private_bytes(b"z" * 32)
    cases = (
        _KmsClient(root, response={}),
        _KmsClient(root, changes={"signature_crc32c": None}),
        _KmsClient(root, changes={"signature_crc32c": -1}),
        _KmsClient(root, changes={"signature_crc32c": 0x1_0000_0000}),
        _KmsClient(root, response_signer=other),
    )
    for client in cases:
        issuer, _, _ = _issuer(client=client, observer=root)
        _assert_refused(issuer)
        assert len(client.calls) == 1


def test_dependency_exception_is_empty_unlinked_and_one_attempt():
    root = _observer()
    canary = "RUNTIME_GENERATED_ARI_CANARY_b952d1"
    client = _KmsClient(root, failure=RuntimeError(canary))
    issuer, _, _ = _issuer(client=client, observer=root)

    error = _assert_refused(issuer)
    rendered = "".join(
        traceback.TracebackException.from_exception(
            error, capture_locals=False
        ).format()
    )

    assert canary not in rendered
    assert len(client.calls) == 1


def test_baseexception_propagates_unchanged_after_one_attempt():
    root = _observer()
    interrupt = KeyboardInterrupt()
    client = _KmsClient(root, failure=interrupt)
    issuer, _, _ = _issuer(client=client, observer=root)

    with pytest.raises(KeyboardInterrupt) as caught:
        issuer.issue(now_us=NOW_US)

    assert caught.value is interrupt
    assert len(client.calls) == 1


def test_returned_receipt_passes_public_verifier_unchanged():
    specs = _approvers()
    root = _observer()
    issuer, _, _ = _issuer(observer=root, manifest=_manifest(specs))
    receipt = issuer.issue(now_us=NOW_US)
    bundle = _approval_bundle(receipt, specs)

    result = SecurityAuditDualApprovalVerifier(_public_key(root)).verify(
        receipt,
        bundle,
        now_us=NOW_US,
    )

    assert result.approver_ids == ("APPROVER_00", "APPROVER_01")
    other = Ed25519PrivateKey.from_private_bytes(b"z" * 32)
    with pytest.raises(SecurityAuditApprovalRefused):
        SecurityAuditDualApprovalVerifier(_public_key(other)).verify(
            receipt,
            bundle,
            now_us=NOW_US,
        )


def test_exact_five_minute_receipt_accepts_and_one_microsecond_more_refuses():
    specs = _approvers()
    root = _observer()
    issuer, _, _ = _issuer(observer=root, manifest=_manifest(specs))
    receipt = issuer.issue(now_us=NOW_US)
    verifier = SecurityAuditDualApprovalVerifier(_public_key(root))

    verifier.verify(receipt, _approval_bundle(receipt, specs), now_us=NOW_US)
    payload_document = json.loads(_receipt_payload(receipt))
    payload_document["expiresAtUnixMicroseconds"] = NOW_US + LIFETIME_US + 1
    payload = _canonical(payload_document)
    mutated = _canonical(
        {
            "payload": _b64(payload),
            "signature": _b64(root.sign(AUTHORITY_DOMAIN + payload)),
        }
    )
    with pytest.raises(SecurityAuditApprovalRefused):
        verifier.verify(
            mutated,
            _approval_bundle(mutated, specs),
            now_us=NOW_US,
        )


def test_maximum_manifest_stays_inside_every_constructed_bound():
    specs = tuple(
        _Approver(
            Ed25519PrivateKey.from_private_bytes(bytes([index + 1]) * 32),
            f"A{index:02d}" + "A" * 125,
            f"D{index:02d}" + "D" * 125,
        )
        for index in range(16)
    )
    manifest = _manifest(specs)
    issuer, client, _ = _issuer(manifest=manifest)
    receipt = issuer.issue(now_us=NOW_US)
    payload = _receipt_payload(receipt)
    request = client.calls[0][0]

    assert len(manifest) <= 8_192
    assert len(payload) <= 12_288
    assert 55 <= len(request.data) <= 12_342
    assert len(receipt) <= 16_384


def test_valid_issuance_uses_no_direct_effect_builtins(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("direct effect builtin was called")

    for name in ("open", "print", "input", "breakpoint"):
        monkeypatch.setattr(builtins, name, forbidden)

    issuer, _, _ = _issuer()
    assert issuer.issue(now_us=NOW_US)


def test_architecture_surface_accepts_exact_module_and_rejects_mutations():
    source = rewrite_architecture_check.ROOT.joinpath(
        "deployment/postgresql/security_audit_authority.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert (
        rewrite_architecture_check._security_audit_authority_surface_violations(
            tree
        )
        == []
    )
    for source_line in (
        "open('/tmp/x', 'wb')",
        "print('issued')",
        "from os import getenv",
        "now_us = 1",
        "client.other()",
        "self._client.other()",
        "_KMS_RPC_TIMEOUT_SECONDS = 4.0",
        "client.asymmetric_sign(request=x, retry=None, timeout=5.0)",
        "kms_v1.AsymmetricSignRequest(name=x, data=y, data_crc32c=1, digest=z)",
        "SecurityAuditAuthorityReceiptRefused('detail')",
    ):
        mutated = ast.Module(
            body=[*tree.body, *ast.parse(source_line).body],
            type_ignores=[],
        )
        assert rewrite_architecture_check._security_audit_authority_surface_violations(
            mutated
        )


def test_source_pins_strict_crc_types_and_contains_no_repository_imports():
    source = rewrite_architecture_check.ROOT.joinpath(
        "deployment/postgresql/security_audit_authority.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    ]

    assert "type(checksum) is not int" in source
    assert "isinstance(checksum, bool)" in source
    assert not any(
        name == "kernel" or name.startswith("kernel.")
        or name == "deployment" or name.startswith("deployment.")
        for name in imports
    )
