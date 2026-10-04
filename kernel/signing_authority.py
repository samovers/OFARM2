"""Current signing authority from PostgreSQL plus fresh observer evidence."""
from __future__ import annotations

import re
from pathlib import Path
from threading import Event
import time
from dataclasses import dataclass, fields
from uuid import UUID

from psycopg import pq

from deployment.postgresql.tenant_contract import (
    TENANT_CAPABILITY_CONTRACT,
    derive_ed25519_key_id,
    raw_public_key_digest,
    validate_binder_audience,
    validate_google_kms_key_version_resource,
)

from .postgres_wait import checkpoint, disposing
from .signing_authority_io import (
    ObservationConnectionOwner, connect_observation, read_signing_receipt,
)
from .signing_receipt import (
    SigningEvidenceReceipt,
    SigningEvidenceVerifier,
)


_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


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
        if len(row) != len(_SIGNING_AUTHORITY_COLUMNS):
            raise ValueError("signing authority row shape differs")
        values = dict(zip(_SIGNING_AUTHORITY_COLUMNS, row, strict=True))
        authority = cls(**values)
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


_SIGNING_AUTHORITY_COLUMNS = tuple(field.name for field in fields(SigningAuthority))
_SIGNING_AUTHORITY_QUERY = (
    "SELECT " + ", ".join(_SIGNING_AUTHORITY_COLUMNS)
    + " FROM ofarm.observe_signing_authority(%s)"
)


class SigningAuthorityReader:
    def __init__(
        self,
        conninfo: bytes,
        receipt_path: Path,
        receipt_verifier: SigningEvidenceVerifier,
    ) -> None:
        self._conninfo = conninfo
        self._receipt_path = receipt_path
        self._receipt_verifier = receipt_verifier

    def current(
        self, kid: str, *, cancel_event: Event | None = None,
        deadline_monotonic: float | None = None,
    ) -> SigningAuthority:
        reason = "database signing authority is unavailable"
        try:
            deadline = time.monotonic() + 5.0
            if deadline_monotonic is not None:
                checkpoint(deadline_monotonic, cancel_event)
                deadline = min(deadline, deadline_monotonic)
            checkpoint(deadline, cancel_event)
            owner = ObservationConnectionOwner()
            with disposing(owner.close):
                connection = connect_observation(
                    self._conninfo, deadline, cancel_event, owner=owner,
                )
                cursor = None
                with disposing(lambda: cursor.close() if cursor is not None else None):
                    cursor = connection.cursor()
                    cursor.execute(_SIGNING_AUTHORITY_QUERY, (kid,))
                    columns = tuple(c.name for c in cursor.description or ())
                    row, duplicate = cursor.fetchone(), cursor.fetchone()
                    if (
                        columns != _SIGNING_AUTHORITY_COLUMNS
                        or cursor.nextset() is not None
                        or connection.pgconn.transaction_status != pq.TransactionStatus.IDLE
                        or (row is not None and type(row) is not tuple)
                        or duplicate is not None
                    ):
                        raise SigningAuthorityUnavailable("database signing authority shape differs")
            checkpoint(deadline, cancel_event)
            if row is None:
                raise SigningAuthorityUnavailable("database has no current signing authority")
            reason = "signing evidence is unavailable"
            authority = SigningAuthority.from_database_row(row, kid)
            receipt_bytes = read_signing_receipt(
                self._receipt_path, deadline=deadline, cancel_event=cancel_event,
            )
            checkpoint(deadline, cancel_event)
            receipt = self._receipt_verifier.verify(
                receipt_bytes, now_us=authority.observed_at_us,
            )
            authority.require_receipt(receipt)
            checkpoint(deadline, cancel_event)
        except SigningAuthorityUnavailable as failure:
            reason = str(failure)
        except Exception:
            pass
        else:
            return authority
        # Raising outside the handler avoids retaining driver exception context.
        raise SigningAuthorityUnavailable(reason)
