"""Shared, test-only values for signing-boundary tests."""
from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TENANT_CAPABILITY_CONTRACT,
    TENANT_CAPABILITY_PARTY_RECORD_KIND,
    derive_ed25519_key_id,
    raw_public_key_digest,
)
from kernel.authentication import VerifiedIdentity
from kernel.principal import PrincipalAuthority
from kernel.signing_authority import SigningAuthority
from kernel.signing_receipt import (
    SIGNING_EVIDENCE_SCHEMA,
    canonical_signing_evidence_payload,
)


AUDIENCE = (
    "urn:ofarm:tenant-binder:v1:"
    "a58b7238-5019-49e2-9aaf-530287e5a6ee"
)
ISSUER = "https://issuer.example.test/tenant"
SUBJECT = "subject:Exact-01"
RESOURCE = (
    "projects/example/locations/europe-west1/keyRings/ofarm/"
    "cryptoKeys/tenant-capability/cryptoKeyVersions/1"
)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
NOW_US = 2_000_000_000_000_000
KMS_PRIVATE_KEY = Ed25519PrivateKey.generate()
OBSERVER_PRIVATE_KEY = Ed25519PrivateKey.generate()


def raw_public_key(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )


KMS_PUBLIC_KEY = raw_public_key(KMS_PRIVATE_KEY)
KID = derive_ed25519_key_id(KMS_PUBLIC_KEY)


def authority_row(**changes) -> tuple[object, ...]:
    values = [
        uuid4(),
        AUDIENCE,
        TENANT_CAPABILITY_CONTRACT.digest,
        uuid4(),
        KID,
        DIGEST_A,
        KMS_PUBLIC_KEY,
        "sha256:" + raw_public_key_digest(KMS_PUBLIC_KEY).hex(),
        RESOURCE,
        DIGEST_B,
        "OPEN",
        3,
        uuid4(),
        DIGEST_C,
        NOW_US - 1_000_000,
        NOW_US + 120_000_000,
        DIGEST_A,
        DIGEST_B,
        NOW_US,
    ]
    indexes = {
        "audience": 1,
        "candidate_digest": 5,
        "public_key": 6,
        "public_key_digest": 7,
        "admission_state": 10,
        "lifecycle_head_id": 12,
        "lifecycle_head_digest": 13,
        "issuance_end_us": 15,
        "kms_evidence_digest": 16,
        "iam_evidence_digest": 17,
        "observed_at_us": 18,
    }
    for name, value in changes.items():
        values[indexes[name]] = value
    return tuple(values)


def signing_authority(**changes) -> SigningAuthority:
    return SigningAuthority.from_database_row(
        authority_row(**changes),
        KID,
    )


def authority_database_row(
    authority: SigningAuthority,
) -> tuple[object, ...]:
    return (
        authority.binder_instance_id,
        authority.audience,
        authority.capability_contract_digest,
        authority.candidate_id,
        authority.kid,
        authority.candidate_digest,
        authority.public_key,
        authority.public_key_digest,
        authority.kms_key_version_resource,
        authority.kms_attestation_digest,
        authority.admission_state,
        authority.lifecycle_head_sequence,
        authority.lifecycle_head_id,
        authority.lifecycle_head_digest,
        authority.issuance_start_us,
        authority.issuance_end_us,
        authority.kms_evidence_digest,
        authority.iam_evidence_digest,
        authority.observed_at_us,
    )


def receipt_payload(
    authority: SigningAuthority,
    **changes,
) -> dict[str, object]:
    payload = {
        "schemaVersion": SIGNING_EVIDENCE_SCHEMA,
        "binderInstanceId": str(authority.binder_instance_id),
        "audience": authority.audience,
        "candidateId": str(authority.candidate_id),
        "kid": authority.kid,
        "candidateDigest": authority.candidate_digest,
        "publicKeyDigest": authority.public_key_digest,
        "kmsKeyVersionResource": authority.kms_key_version_resource,
        "kmsAttestationDigest": authority.kms_attestation_digest,
        "kmsEvidenceDigest": authority.kms_evidence_digest,
        "iamEvidenceDigest": authority.iam_evidence_digest,
        "lifecycleHeadId": str(authority.lifecycle_head_id),
        "lifecycleHeadDigest": authority.lifecycle_head_digest,
        "observedAtUnixMicroseconds": NOW_US - 1_000_000,
        "expiresAtUnixMicroseconds": NOW_US + 10_000_000,
    }
    payload.update(changes)
    return payload


def signed_receipt(
    payload: dict[str, object],
    *,
    private_key: Ed25519PrivateKey = OBSERVER_PRIVATE_KEY,
) -> bytes:
    payload_bytes = canonical_signing_evidence_payload(payload)
    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    envelope = {
        "payload": encode(payload_bytes),
        "signature": encode(private_key.sign(payload_bytes)),
    }
    return json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


IDENTITY = VerifiedIdentity(
    equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
    issuer=ISSUER,
    subject=SUBJECT,
)


def principal_authority() -> PrincipalAuthority:
    now = datetime(2026, 7, 23, tzinfo=UTC)
    return PrincipalAuthority(
        equality_policy=IDENTITY.equality_policy,
        issuer=IDENTITY.issuer,
        subject=IDENTITY.subject,
        binding_version_id=uuid4(),
        binding_version_digest=DIGEST_A,
        lifecycle_head_id=uuid4(),
        lifecycle_head_digest=DIGEST_B,
        tenant_id=uuid4(),
        tenant_registration_digest=DIGEST_C,
        party_ref="party:Exact-01",
        party_record_kind=TENANT_CAPABILITY_PARTY_RECORD_KIND,
        party_record_id="party:Exact-01",
        party_schema_digest=DIGEST_A,
        party_payload_digest=DIGEST_B,
        party_state="ACTIVE",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
    )


class Cursor:
    def __init__(self, rows: list[tuple[object, ...]]):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class Transaction:
    def __init__(self, exit_error: Exception | None = None):
        self.exit_error = exit_error

    def __enter__(self):
        return self

    def __exit__(self, exception_type, _exception, _traceback):
        if exception_type is None and self.exit_error is not None:
            raise self.exit_error
        return False


class Connection:
    def __init__(
        self,
        responses: list[list[tuple[object, ...]]],
        *,
        autocommit: bool = False,
        fail_at: int | None = None,
        failure: Exception | None = None,
        exit_error: Exception | None = None,
    ):
        self.responses = list(responses)
        self.autocommit = autocommit
        self.fail_at = fail_at
        self.failure = failure
        self.exit_error = exit_error
        self.executions: list[tuple[str, tuple[object, ...] | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, _exception_type, _exception, _traceback):
        return False

    def transaction(self):
        return Transaction(self.exit_error)

    def execute(self, statement: str, parameters=None):
        self.executions.append((statement, parameters))
        if parameters is not None:
            assert statement.count("%s") == len(parameters)
        if len(self.executions) == self.fail_at:
            assert self.failure is not None
            raise self.failure
        rows = self.responses.pop(0) if self.responses else []
        return Cursor(rows)


class Factory:
    def __init__(self, connection: Connection):
        self.connection = connection

    def __call__(self):
        return self.connection
