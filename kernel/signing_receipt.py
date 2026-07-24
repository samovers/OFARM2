"""Canonical signed evidence from the read-only KMS/IAM observer."""
from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


SIGNING_EVIDENCE_SCHEMA = "ofarm.signing-evidence-receipt.v1"
SIGNING_EVIDENCE_MAX_BYTES = 16_384
SIGNING_EVIDENCE_MAX_LIFETIME_US = 60_000_000
_B64URL = re.compile(r"[A-Za-z0-9_-]+")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_PAYLOAD_MEMBERS = frozenset(
    {
        "schemaVersion",
        "binderInstanceId",
        "audience",
        "candidateId",
        "kid",
        "candidateDigest",
        "publicKeyDigest",
        "kmsKeyVersionResource",
        "kmsAttestationDigest",
        "kmsEvidenceDigest",
        "iamEvidenceDigest",
        "lifecycleHeadId",
        "lifecycleHeadDigest",
        "observedAtUnixMicroseconds",
        "expiresAtUnixMicroseconds",
    }
)


class SigningEvidenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SigningEvidenceReceipt:
    binder_instance_id: UUID
    audience: str
    candidate_id: UUID
    kid: str
    candidate_digest: str
    public_key_digest: str
    kms_key_version_resource: str
    kms_attestation_digest: str
    kms_evidence_digest: str
    iam_evidence_digest: str
    lifecycle_head_id: UUID
    lifecycle_head_digest: str
    observed_at_us: int
    expires_at_us: int


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SigningEvidenceError("duplicate receipt JSON member")
        result[key] = value
    return result


def _json(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_object,
        )
    except SigningEvidenceError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SigningEvidenceError(f"{label} JSON is malformed") from exc
    if type(value) is not dict:
        raise SigningEvidenceError(f"{label} must be an object")
    return value


def _decode(segment: object, label: str) -> bytes:
    if type(segment) is not str or _B64URL.fullmatch(segment) is None:
        raise SigningEvidenceError(f"{label} is not canonical base64url")
    try:
        raw = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (binascii.Error, ValueError) as exc:
        raise SigningEvidenceError(f"{label} is malformed") from exc
    if base64.urlsafe_b64encode(raw).rstrip(b"=").decode() != segment:
        raise SigningEvidenceError(f"{label} is not canonical base64url")
    return raw


def _uuid(value: object, label: str) -> UUID:
    if type(value) is not str:
        raise SigningEvidenceError(f"{label} is invalid")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise SigningEvidenceError(f"{label} is invalid") from exc
    if parsed.int == 0 or str(parsed) != value:
        raise SigningEvidenceError(f"{label} is invalid")
    return parsed


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise SigningEvidenceError(f"{label} is invalid")
    return value


def _digest(value: object, label: str) -> str:
    checked = _text(value, label)
    if _DIGEST.fullmatch(checked) is None:
        raise SigningEvidenceError(f"{label} is invalid")
    return checked


def canonical_signing_evidence_payload(
    payload: dict[str, object],
) -> bytes:
    if set(payload) != _PAYLOAD_MEMBERS:
        raise SigningEvidenceError("receipt payload shape differs")
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


class SigningEvidenceVerifier:
    def __init__(self, observer_public_key: bytes) -> None:
        if type(observer_public_key) is not bytes or len(observer_public_key) != 32:
            raise SigningEvidenceError("observer public key is invalid")
        self._public_key = Ed25519PublicKey.from_public_bytes(
            observer_public_key
        )

    def verify(
        self,
        receipt_bytes: bytes,
        *,
        now_us: int,
    ) -> SigningEvidenceReceipt:
        if (
            type(receipt_bytes) is not bytes
            or not 1 <= len(receipt_bytes) <= SIGNING_EVIDENCE_MAX_BYTES
            or type(now_us) is not int
        ):
            raise SigningEvidenceError("receipt input is invalid")
        envelope = _json(receipt_bytes, "receipt")
        if set(envelope) != {"payload", "signature"}:
            raise SigningEvidenceError("receipt envelope shape differs")
        payload_bytes = _decode(envelope["payload"], "receipt payload")
        signature = _decode(envelope["signature"], "receipt signature")
        if len(signature) != 64:
            raise SigningEvidenceError("receipt signature length differs")
        try:
            self._public_key.verify(signature, payload_bytes)
        except InvalidSignature as exc:
            raise SigningEvidenceError("receipt signature differs") from exc
        payload = _json(payload_bytes, "receipt payload")
        if canonical_signing_evidence_payload(payload) != payload_bytes:
            raise SigningEvidenceError("receipt payload is not canonical")
        return self._map(payload, now_us)

    def _map(
        self,
        payload: dict[str, object],
        now_us: int,
    ) -> SigningEvidenceReceipt:
        observed = payload["observedAtUnixMicroseconds"]
        expires = payload["expiresAtUnixMicroseconds"]
        if (
            payload["schemaVersion"] != SIGNING_EVIDENCE_SCHEMA
            or type(observed) is not int
            or type(expires) is not int
            or not observed <= now_us < expires
            or not 1 <= expires - observed <= SIGNING_EVIDENCE_MAX_LIFETIME_US
        ):
            raise SigningEvidenceError("receipt freshness differs")
        return SigningEvidenceReceipt(
            binder_instance_id=_uuid(
                payload["binderInstanceId"], "binder instance id"
            ),
            audience=_text(payload["audience"], "audience"),
            candidate_id=_uuid(payload["candidateId"], "candidate id"),
            kid=_text(payload["kid"], "kid"),
            candidate_digest=_digest(
                payload["candidateDigest"], "candidate digest"
            ),
            public_key_digest=_digest(
                payload["publicKeyDigest"], "public key digest"
            ),
            kms_key_version_resource=_text(
                payload["kmsKeyVersionResource"], "KMS resource"
            ),
            kms_attestation_digest=_digest(
                payload["kmsAttestationDigest"], "KMS attestation digest"
            ),
            kms_evidence_digest=_digest(
                payload["kmsEvidenceDigest"], "KMS evidence digest"
            ),
            iam_evidence_digest=_digest(
                payload["iamEvidenceDigest"], "IAM evidence digest"
            ),
            lifecycle_head_id=_uuid(
                payload["lifecycleHeadId"], "lifecycle head id"
            ),
            lifecycle_head_digest=_digest(
                payload["lifecycleHeadDigest"], "lifecycle head digest"
            ),
            observed_at_us=observed,
            expires_at_us=expires,
        )
