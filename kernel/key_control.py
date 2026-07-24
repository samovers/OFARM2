"""Typed wrappers over the database-owned capability-key control API."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

import psycopg


_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_KID = re.compile(r"[A-Za-z0-9_-]{43}")
ConnectionFactory = Callable[[], psycopg.Connection[tuple[object, ...]]]


class KeyControlError(RuntimeError):
    pass


class KeyControlOutcomeUnknown(KeyControlError):
    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"key-control outcome is unknown ({operation})")


@dataclass(frozen=True, slots=True)
class KeyLifecycleHead:
    act_id: UUID
    act_digest: str


@dataclass(frozen=True, slots=True)
class KeyEvidence:
    kms_evidence_digest: str
    iam_evidence_digest: str


@dataclass(frozen=True, slots=True)
class KeyCandidateRegistration:
    candidate_id: UUID
    kid: str
    candidate_digest: str


@dataclass(frozen=True, slots=True)
class KeyActResult:
    head: KeyLifecycleHead
    decided_at_us: int


@dataclass(frozen=True, slots=True)
class KeyRotationResult:
    head: KeyLifecycleHead
    decided_at_us: int
    old_verification_end_us: int


@dataclass(frozen=True, slots=True)
class AdmissionCloseResult:
    head: KeyLifecycleHead
    incident_id: UUID
    close_receipt_id: UUID
    decided_at_us: int


@dataclass(frozen=True, slots=True)
class KeyringRebuildResult:
    deleted_projection_rows: int
    upserted_projection_rows: int


def _uuid(value: object) -> UUID:
    if type(value) is not UUID or value.int == 0:
        raise KeyControlError("key-control UUID result differs")
    return value


def _digest(value: object) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise KeyControlError("key-control digest result differs")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise KeyControlError("key-control integer result differs")
    return value


def _head(act_id: object, act_digest: object) -> KeyLifecycleHead:
    return KeyLifecycleHead(_uuid(act_id), _digest(act_digest))


class TenantCapabilityKeyController:
    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def _call(
        self,
        operation: str,
        statement: str,
        parameters: tuple[object, ...],
        expected_columns: int,
    ) -> tuple[object, ...]:
        submitted = False
        try:
            with self._connection_factory() as connection:
                if connection.autocommit is not False:
                    raise KeyControlError(
                        "key control requires autocommit=False"
                    )
                with connection.transaction():
                    submitted = True
                    cursor = connection.execute(statement, parameters)
                    row = cursor.fetchone()
                    duplicate = cursor.fetchone()
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            if submitted:
                raise KeyControlOutcomeUnknown(operation) from exc
            raise KeyControlError("key control is unavailable") from exc
        except psycopg.Error as exc:
            raise KeyControlError(f"key control refused ({operation})") from exc
        if (
            type(row) is not tuple
            or len(row) != expected_columns
            or duplicate is not None
        ):
            raise KeyControlError(f"key control result differs ({operation})")
        return row

    def register(
        self,
        public_key: bytes,
        kms_key_version_resource: str,
        kms_attestation_digest: str,
    ) -> KeyCandidateRegistration:
        row = self._call(
            "REGISTER",
            "SELECT * FROM ofarm.register_tenant_capability_key(%s, %s, %s)",
            (
                public_key,
                kms_key_version_resource,
                kms_attestation_digest,
            ),
            3,
        )
        if type(row[1]) is not str or _KID.fullmatch(row[1]) is None:
            raise KeyControlError("registered key id differs")
        return KeyCandidateRegistration(
            candidate_id=_uuid(row[0]),
            kid=row[1],
            candidate_digest=_digest(row[2]),
        )

    def verify_candidate_preflight(
        self,
        kid: str,
        signature: bytes,
    ) -> bool:
        row = self._call(
            "VERIFY_PREFLIGHT",
            "SELECT ofarm.verify_tenant_capability_candidate_preflight(%s, %s)",
            (kid, signature),
            1,
        )
        if type(row[0]) is not bool:
            raise KeyControlError("candidate preflight result differs")
        return row[0]

    def activate(
        self,
        kid: str,
        expected_head: KeyLifecycleHead | None,
        preflight_receipt_digest: str,
        evidence: KeyEvidence,
        reason: str,
    ) -> KeyActResult:
        row = self._call(
            "ACTIVATE",
            "SELECT * FROM ofarm.activate_tenant_capability_key("
            "%s, %s, %s, %s, %s, %s, %s)",
            (
                kid,
                expected_head.act_id if expected_head else None,
                expected_head.act_digest if expected_head else None,
                preflight_receipt_digest,
                evidence.kms_evidence_digest,
                evidence.iam_evidence_digest,
                reason,
            ),
            3,
        )
        return KeyActResult(_head(row[0], row[1]), _integer(row[2]))

    def rotate(
        self,
        old_kid: str,
        new_kid: str,
        expected_head: KeyLifecycleHead,
        preflight_receipt_digest: str,
        evidence: KeyEvidence,
        reason: str,
    ) -> KeyRotationResult:
        row = self._call(
            "ROTATE",
            "SELECT * FROM ofarm.rotate_tenant_capability_key("
            "%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                old_kid,
                new_kid,
                expected_head.act_id,
                expected_head.act_digest,
                preflight_receipt_digest,
                evidence.kms_evidence_digest,
                evidence.iam_evidence_digest,
                reason,
            ),
            4,
        )
        return KeyRotationResult(
            _head(row[0], row[1]),
            _integer(row[2]),
            _integer(row[3]),
        )

    def close_admission(
        self,
        expected_head: KeyLifecycleHead,
        affected_kid: str,
        evidence: KeyEvidence,
        reason: str,
    ) -> AdmissionCloseResult:
        row = self._call(
            "CLOSE_ADMISSION",
            "SELECT * FROM ofarm.close_tenant_capability_admission("
            "%s, %s, %s, %s, %s, %s)",
            (
                expected_head.act_id,
                expected_head.act_digest,
                affected_kid,
                evidence.kms_evidence_digest,
                evidence.iam_evidence_digest,
                reason,
            ),
            5,
        )
        return AdmissionCloseResult(
            head=_head(row[0], row[1]),
            incident_id=_uuid(row[2]),
            close_receipt_id=_uuid(row[3]),
            decided_at_us=_integer(row[4]),
        )

    def revoke(
        self,
        kid: str,
        expected_head: KeyLifecycleHead,
        incident_id: UUID,
        close_receipt_id: UUID,
        evidence: KeyEvidence,
        reason: str,
    ) -> KeyActResult:
        row = self._call(
            "REVOKE",
            "SELECT * FROM ofarm.revoke_tenant_capability_key("
            "%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                kid,
                expected_head.act_id,
                expected_head.act_digest,
                incident_id,
                close_receipt_id,
                evidence.kms_evidence_digest,
                evidence.iam_evidence_digest,
                reason,
            ),
            3,
        )
        return KeyActResult(_head(row[0], row[1]), _integer(row[2]))

    def resume(
        self,
        expected_head: KeyLifecycleHead,
        incident_id: UUID,
        close_receipt_id: UUID,
        evidence: KeyEvidence,
        reason: str,
    ) -> KeyActResult:
        row = self._call(
            "RESUME_ADMISSION",
            "SELECT * FROM ofarm.resume_tenant_capability_admission("
            "%s, %s, %s, %s, %s, %s, %s)",
            (
                expected_head.act_id,
                expected_head.act_digest,
                incident_id,
                close_receipt_id,
                evidence.kms_evidence_digest,
                evidence.iam_evidence_digest,
                reason,
            ),
            3,
        )
        return KeyActResult(_head(row[0], row[1]), _integer(row[2]))

    def rebuild_projection(self) -> KeyringRebuildResult:
        row = self._call(
            "REBUILD",
            "SELECT * FROM ofarm.rebuild_tenant_capability_keyring()",
            (),
            2,
        )
        return KeyringRebuildResult(_integer(row[0]), _integer(row[1]))
