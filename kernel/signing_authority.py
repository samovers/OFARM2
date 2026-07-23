"""Current signing authority from PostgreSQL plus fresh observer evidence."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

import psycopg

from deployment.postgresql.tenant_contract import (
    TENANT_CAPABILITY_CONTRACT,
    derive_ed25519_key_id,
    raw_public_key_digest,
    validate_binder_audience,
    validate_google_kms_key_version_resource,
)

from .signing_receipt import (
    SigningEvidenceError,
    SigningEvidenceReceipt,
    SigningEvidenceVerifier,
)


_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
ConnectionFactory = Callable[[], psycopg.Connection[tuple[object, ...]]]
ReceiptSource = Callable[[], bytes]


class SigningAuthorityError(RuntimeError):
    pass


class SigningAuthorityUnavailable(SigningAuthorityError):
    pass


@dataclass(frozen=True, slots=True)
class SigningAuthority:
    binder_instance_id: UUID
    audience: str
    capability_contract_digest: str
    candidate_id: UUID
    kid: str
    candidate_digest: str
    public_key: bytes
    public_key_digest: str
    kms_key_version_resource: str
    kms_attestation_digest: str
    admission_state: str
    lifecycle_head_sequence: int
    lifecycle_head_id: UUID
    lifecycle_head_digest: str
    issuance_start_us: int
    issuance_end_us: int
    kms_evidence_digest: str
    iam_evidence_digest: str
    observed_at_us: int

    @classmethod
    def from_database_row(
        cls,
        row: tuple[object, ...],
        requested_kid: str,
    ) -> SigningAuthority:
        if len(row) != 19:
            raise ValueError("signing authority row shape differs")
        authority = cls(*row)
        authority._validate(requested_kid)
        return authority

    def _validate(self, requested_kid: str) -> None:
        uuids = (
            self.binder_instance_id,
            self.candidate_id,
            self.lifecycle_head_id,
        )
        digests = (
            self.capability_contract_digest,
            self.candidate_digest,
            self.public_key_digest,
            self.kms_attestation_digest,
            self.lifecycle_head_digest,
            self.kms_evidence_digest,
            self.iam_evidence_digest,
        )
        if (
            any(type(value) is not UUID or value.int == 0 for value in uuids)
            or any(
                type(value) is not str or _DIGEST.fullmatch(value) is None
                for value in digests
            )
            or type(self.public_key) is not bytes
            or len(self.public_key) != 32
            or type(self.lifecycle_head_sequence) is not int
            or self.lifecycle_head_sequence < 1
            or any(
                type(value) is not int
                for value in (
                    self.issuance_start_us,
                    self.issuance_end_us,
                    self.observed_at_us,
                )
            )
        ):
            raise ValueError("signing authority value shape differs")
        if (
            self.kid != requested_kid
            or self.kid != derive_ed25519_key_id(self.public_key)
            or self.public_key_digest
            != "sha256:" + raw_public_key_digest(self.public_key).hex()
            or self.capability_contract_digest
            != TENANT_CAPABILITY_CONTRACT.digest
            or self.admission_state != "OPEN"
            or not self.issuance_start_us <= (
                self.observed_at_us
            ) < self.issuance_end_us
        ):
            raise ValueError("signing authority differs")
        validate_binder_audience(self.audience)
        validate_google_kms_key_version_resource(
            self.kms_key_version_resource
        )

    def require_receipt(self, receipt: SigningEvidenceReceipt) -> None:
        expected = (
            self.binder_instance_id,
            self.audience,
            self.candidate_id,
            self.kid,
            self.candidate_digest,
            self.public_key_digest,
            self.kms_key_version_resource,
            self.kms_attestation_digest,
            self.kms_evidence_digest,
            self.iam_evidence_digest,
            self.lifecycle_head_id,
            self.lifecycle_head_digest,
        )
        observed = (
            receipt.binder_instance_id,
            receipt.audience,
            receipt.candidate_id,
            receipt.kid,
            receipt.candidate_digest,
            receipt.public_key_digest,
            receipt.kms_key_version_resource,
            receipt.kms_attestation_digest,
            receipt.kms_evidence_digest,
            receipt.iam_evidence_digest,
            receipt.lifecycle_head_id,
            receipt.lifecycle_head_digest,
        )
        if observed != expected:
            raise SigningAuthorityUnavailable(
                "signing evidence conflicts with database authority"
            )


class SigningAuthorityReader:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        receipt_source: ReceiptSource,
        receipt_verifier: SigningEvidenceVerifier,
    ) -> None:
        self._connection_factory = connection_factory
        self._receipt_source = receipt_source
        self._receipt_verifier = receipt_verifier

    def current(self, kid: str) -> SigningAuthority:
        try:
            with self._connection_factory() as connection:
                cursor = connection.execute(
                    "SELECT * FROM ofarm.observe_signing_authority(%s)",
                    (kid,),
                )
                row = cursor.fetchone()
                duplicate = cursor.fetchone()
        except psycopg.Error as exc:
            raise SigningAuthorityUnavailable(
                "database signing authority is unavailable"
            ) from exc
        if row is None:
            raise SigningAuthorityUnavailable(
                "database has no current signing authority"
            )
        if type(row) is not tuple or duplicate is not None:
            raise SigningAuthorityUnavailable(
                "database signing authority shape differs"
            )
        try:
            authority = SigningAuthority.from_database_row(row, kid)
            receipt = self._receipt_verifier.verify(
                self._receipt_source(),
                now_us=authority.observed_at_us,
            )
        except (OSError, SigningEvidenceError, TypeError, ValueError) as exc:
            raise SigningAuthorityUnavailable(
                "signing evidence is unavailable"
            ) from exc
        authority.require_receipt(receipt)
        return authority
