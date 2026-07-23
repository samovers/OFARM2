"""Production TenantCapability minting and the Google KMS HSM signer boundary."""
from __future__ import annotations

import base64
import json
import os
import re
import stat
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, final
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from deployment.postgresql.tenant_contract import (
    GOOGLE_KMS_KEY_ALGORITHM,
    GOOGLE_KMS_KEY_PURPOSE,
    GOOGLE_KMS_PROTECTION_LEVEL,
    OIDC_ISSUER_EQUALITY_POLICY,
    TENANT_CAPABILITY_CONTRACT,
    TENANT_CAPABILITY_MAX_TTL_MICROSECONDS,
    TENANT_CAPABILITY_PREFLIGHT_PROBE,
    TENANT_CAPABILITY_RFC8410_PREFIX,
    GoogleKmsEd25519PublicKey,
    TenantCapability,
    TenantCapabilityContractError,
    canonical_jws_signing_input,
    derive_ed25519_key_id,
    raw_public_key_digest,
    serialize_tenant_capability_jws,
    validate_binder_audience,
    validate_google_kms_key_version_resource,
    validate_tenant_capability,
)

from .auth_oidc import OidcError, PreBindingOutcome, VerifiedOidcIdentity
from .principal_binding import (
    PostgreSQLPrincipalBindingResolver,
    PrincipalBindingAuthority,
)


_SHA256_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_PRODUCTION_SIGNING_EVIDENCE_MAX_AGE_MICROSECONDS = 300_000_000
_SIGNING_EVIDENCE_RECEIPT_DOMAIN = b"OFARM_PRODUCTION_SIGNING_EVIDENCE_V1"
_SIGNING_EVIDENCE_RECEIPT_MAX_BYTES = 16_384
_SIGNING_EVIDENCE_RECEIPT_PATH_ENV = "OFARM_SIGNING_EVIDENCE_RECEIPT_PATH"
_SIGNING_EVIDENCE_OBSERVER_KEY_ENV = (
    "OFARM_SIGNING_EVIDENCE_OBSERVER_KEY_VERSION"
)
_SIGNING_EVIDENCE_REFRESH_WINDOW_MICROSECONDS = 30_000_000
_SIGNING_EVIDENCE_REFRESH_RETRY_MICROSECONDS = 1_000_000
_SIGNING_EVIDENCE_REFRESH_WAIT_SECONDS = 5.0


class CapabilityIssuanceError(RuntimeError):
    """A safe closed outcome; signer, identity, and crypto details stay private."""

    def __init__(self, outcome: PreBindingOutcome, *, internal_detail: str = ""):
        self.outcome = outcome
        self.internal_detail = internal_detail
        super().__init__(f"capability issuance refused ({outcome.value})")


@dataclass(frozen=True, slots=True)
class TenantChallenge:
    challenge_id: UUID
    audience: str


@dataclass(frozen=True, slots=True)
class GoogleKmsSigningResponse:
    key_version_resource: str
    protection_level: str
    verified_data_crc32c: bool
    signature: bytes
    signature_crc32c: int


@final
class GoogleCloudKmsClientAdapter:
    """Adapter that constructs its Google client inside the trust boundary.

    The production constructor exposes no client or transport injection seam.
    Application Default Credentials and the maintained client's default
    transport remain deployment-owned.  Fixture clients are available only
    through :meth:`for_test` and are never production eligible.
    """

    def __init__(self) -> None:
        try:
            from google.cloud.kms_v1.services.key_management_service.client import (
                KeyManagementServiceClient,
            )
        except ImportError as exc:
            raise TypeError("Google Cloud KMS client dependency is unavailable") from exc
        try:
            client = KeyManagementServiceClient()
        except Exception as exc:
            raise TypeError(
                "Google Cloud KMS client construction failed"
            ) from exc
        if type(client) is not KeyManagementServiceClient:
            raise TypeError("Google Cloud KMS client construction differs")
        self._bind_client(client, production_eligible=True)

    @classmethod
    def for_test(cls, client: object) -> "GoogleCloudKmsClientAdapter":
        """Build a visibly non-production adapter for fixture-only tests."""

        adapter = object.__new__(cls)
        adapter._bind_client(client, production_eligible=False)
        return adapter

    def _bind_client(self, client: object, *, production_eligible: bool) -> None:
        if not callable(getattr(client, "asymmetric_sign", None)):
            raise TypeError("Google KMS client does not expose asymmetric_sign")
        self._client = client
        self._production_eligible = production_eligible

    @property
    def production_eligible(self) -> bool:
        return self._production_eligible is True

    def asymmetric_sign(
        self, *, name: str, data: bytes, data_crc32c: int
    ) -> GoogleKmsSigningResponse:
        response = self._client.asymmetric_sign(
            request={
                "name": name,
                "data": data,
                "data_crc32c": data_crc32c,
            }
        )
        protection = getattr(response, "protection_level", None)
        protection_name = getattr(protection, "name", None)
        signature_checksum = getattr(response, "signature_crc32c", None)
        if (
            type(getattr(response, "name", None)) is not str
            or type(protection_name) is not str
            or type(getattr(response, "verified_data_crc32c", None)) is not bool
            or type(getattr(response, "signature", None)) is not bytes
            or type(signature_checksum) is not int
            or not 0 <= signature_checksum <= 0xFFFFFFFF
        ):
            raise ValueError("Google KMS signing response shape differs")
        return GoogleKmsSigningResponse(
            key_version_resource=response.name,
            protection_level=protection_name,
            verified_data_crc32c=response.verified_data_crc32c,
            signature=response.signature,
            signature_crc32c=signature_checksum,
        )

    def get_ed25519_public_key(self, *, name: str) -> Ed25519PublicKey:
        response = self._client.get_public_key(request={"name": name})
        algorithm = getattr(response, "algorithm", None)
        protection = getattr(response, "protection_level", None)
        pem = getattr(response, "pem", None)
        pem_crc32c = getattr(response, "pem_crc32c", None)
        if (
            getattr(response, "name", None) != name
            or getattr(algorithm, "name", None) != GOOGLE_KMS_KEY_ALGORITHM
            or getattr(protection, "name", None) != GOOGLE_KMS_PROTECTION_LEVEL
            or type(pem) is not str
            or type(pem_crc32c) is not int
            or not 0 <= pem_crc32c <= 0xFFFFFFFF
        ):
            raise ValueError("Google KMS public-key response shape differs")
        pem_bytes = pem.encode("ascii", errors="strict")
        if _crc32c(pem_bytes) != pem_crc32c:
            raise ValueError("Google KMS public-key checksum differs")
        public_key = serialization.load_pem_public_key(pem_bytes)
        if not isinstance(public_key, Ed25519PublicKey):
            raise ValueError("Google KMS observer key algorithm differs")
        return public_key


@dataclass(frozen=True, slots=True)
class ProductionSigningEvidence:
    """Fixture-only decoded evidence; production accepts only a signed receipt."""

    audience: str
    key_version_resource: str
    key_id: str
    public_key_digest: bytes
    key_purpose: str
    key_algorithm: str
    protection_level: str
    key_state: str
    attestation_evidence_digest: str
    iam_evidence_digest: str
    database_candidate_digest: str
    database_lifecycle_head_digest: str
    observed_at_unix_microseconds: int
    valid_until_unix_microseconds: int


def _json_object_without_duplicates(pairs):
    parsed = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError("signing-evidence receipt has duplicate fields")
        parsed[key] = value
    return parsed


def _canonical_evidence_bytes(value: dict[str, object]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    ).encode("ascii")


def _decode_receipt_signature(value: object) -> bytes:
    if (
        type(value) is not str
        or not value
        or "=" in value
        or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None
    ):
        raise ValueError("signing-evidence receipt signature is malformed")
    try:
        decoded = base64.urlsafe_b64decode(
            value.encode("ascii") + b"=" * (-len(value) % 4)
        )
    except (UnicodeError, ValueError) as exc:
        raise ValueError("signing-evidence receipt signature is malformed") from exc
    if (
        len(decoded) != 64
        or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii")
        != value
    ):
        raise ValueError("signing-evidence receipt signature is malformed")
    return decoded


def _decode_signing_evidence_receipt(
    receipt_bytes: bytes,
    observer_public_key: Ed25519PublicKey,
) -> ProductionSigningEvidence:
    if (
        type(receipt_bytes) is not bytes
        or not receipt_bytes
        or len(receipt_bytes) > _SIGNING_EVIDENCE_RECEIPT_MAX_BYTES
    ):
        raise ValueError("signing-evidence receipt size is invalid")
    try:
        receipt = json.loads(
            receipt_bytes.decode("utf-8", errors="strict"),
            object_pairs_hook=_json_object_without_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("signing-evidence receipt JSON is malformed") from exc
    if type(receipt) is not dict or set(receipt) != {"evidence", "signature"}:
        raise ValueError("signing-evidence receipt fields are not exact")
    evidence = receipt["evidence"]
    expected_fields = {
        "audience",
        "keyVersionResource",
        "keyId",
        "publicKeyDigest",
        "keyPurpose",
        "keyAlgorithm",
        "protectionLevel",
        "keyState",
        "attestationEvidenceDigest",
        "iamEvidenceDigest",
        "databaseCandidateDigest",
        "databaseLifecycleHeadDigest",
        "observedAtUnixMicroseconds",
        "validUntilUnixMicroseconds",
    }
    if type(evidence) is not dict or set(evidence) != expected_fields:
        raise ValueError("signing-evidence fields are not exact")
    signature = _decode_receipt_signature(receipt["signature"])
    signing_input = (
        _SIGNING_EVIDENCE_RECEIPT_DOMAIN
        + b"\x00"
        + _canonical_evidence_bytes(evidence)
    )
    try:
        observer_public_key.verify(signature, signing_input)
    except InvalidSignature as exc:
        raise ValueError("signing-evidence receipt signature differs") from exc

    public_key_digest = evidence["publicKeyDigest"]
    if (
        type(public_key_digest) is not str
        or _SHA256_ID.fullmatch(public_key_digest) is None
    ):
        raise ValueError("signing-evidence public-key digest is malformed")
    integer_fields = (
        evidence["observedAtUnixMicroseconds"],
        evidence["validUntilUnixMicroseconds"],
    )
    if any(type(value) is not int for value in integer_fields):
        raise ValueError("signing-evidence time fields are malformed")
    text_fields = tuple(
        value
        for key, value in evidence.items()
        if key
        not in {
            "observedAtUnixMicroseconds",
            "validUntilUnixMicroseconds",
        }
    )
    if any(type(value) is not str for value in text_fields):
        raise ValueError("signing-evidence text fields are malformed")
    return ProductionSigningEvidence(
        audience=evidence["audience"],
        key_version_resource=evidence["keyVersionResource"],
        key_id=evidence["keyId"],
        public_key_digest=bytes.fromhex(
            public_key_digest.removeprefix("sha256:")
        ),
        key_purpose=evidence["keyPurpose"],
        key_algorithm=evidence["keyAlgorithm"],
        protection_level=evidence["protectionLevel"],
        key_state=evidence["keyState"],
        attestation_evidence_digest=evidence["attestationEvidenceDigest"],
        iam_evidence_digest=evidence["iamEvidenceDigest"],
        database_candidate_digest=evidence["databaseCandidateDigest"],
        database_lifecycle_head_digest=evidence[
            "databaseLifecycleHeadDigest"
        ],
        observed_at_unix_microseconds=evidence[
            "observedAtUnixMicroseconds"
        ],
        valid_until_unix_microseconds=evidence[
            "validUntilUnixMicroseconds"
        ],
    )


def _google_kms_crypto_key_parent(value: object) -> str:
    """Return the IAM-grantable CryptoKey parent of one exact key version."""

    resource = validate_google_kms_key_version_resource(value)
    parent, separator, version = resource.rpartition("/cryptoKeyVersions/")
    if not separator or not parent or not version:
        raise TenantCapabilityContractError(
            "KMS CryptoKey parent resource differs"
        )
    return parent


@final
class GoogleKmsSigningEvidenceObserver:
    """Authenticate an out-of-process lifecycle observation receipt."""

    def __init__(self) -> None:
        receipt_path = os.environ.get(_SIGNING_EVIDENCE_RECEIPT_PATH_ENV)
        observer_key_resource = os.environ.get(
            _SIGNING_EVIDENCE_OBSERVER_KEY_ENV
        )
        if (
            type(receipt_path) is not str
            or not receipt_path
            or not Path(receipt_path).is_absolute()
        ):
            raise TypeError("production signing-evidence receipt path is invalid")
        try:
            validate_google_kms_key_version_resource(observer_key_resource)
        except TenantCapabilityContractError as exc:
            raise TypeError(
                "production signing-evidence observer key is invalid"
            ) from exc
        self._client = GoogleCloudKmsClientAdapter()
        self._receipt_path = Path(receipt_path)
        self._observer_key_resource = observer_key_resource
        self._receipt_bytes: bytes | None = None
        self._production_eligible = True

    @classmethod
    def for_test(
        cls,
        *,
        client: GoogleCloudKmsClientAdapter,
        observer_key_resource: str,
        receipt_bytes: bytes,
    ) -> "GoogleKmsSigningEvidenceObserver":
        observer = object.__new__(cls)
        observer._client = client
        observer._receipt_path = None
        observer._observer_key_resource = observer_key_resource
        observer._receipt_bytes = receipt_bytes
        observer._production_eligible = False
        return observer

    @property
    def production_eligible(self) -> bool:
        return (
            self._production_eligible is True
            and type(self._client) is GoogleCloudKmsClientAdapter
            and self._client.production_eligible
        )

    def _read_receipt(self) -> bytes:
        if self._receipt_bytes is not None:
            return self._receipt_bytes
        assert self._receipt_path is not None
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self._receipt_path, flags)
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or not 0 < metadata.st_size
                <= _SIGNING_EVIDENCE_RECEIPT_MAX_BYTES
            ):
                raise ValueError("signing-evidence receipt file is invalid")
            receipt_bytes = os.read(
                descriptor, _SIGNING_EVIDENCE_RECEIPT_MAX_BYTES + 1
            )
            if (
                len(receipt_bytes) != metadata.st_size
                or os.read(descriptor, 1)
            ):
                raise ValueError("signing-evidence receipt changed while read")
            return receipt_bytes
        finally:
            os.close(descriptor)

    def observe(
        self,
        signing_key: GoogleKmsEd25519PublicKey,
    ) -> ProductionSigningEvidence:
        if type(signing_key) is not GoogleKmsEd25519PublicKey:
            raise ValueError("signing-evidence observer identity differs")
        try:
            observer_parent = _google_kms_crypto_key_parent(
                self._observer_key_resource
            )
            signing_parent = _google_kms_crypto_key_parent(
                signing_key.key_version_resource
            )
        except TenantCapabilityContractError as exc:
            raise ValueError(
                "signing-evidence observer identity differs"
            ) from exc
        if observer_parent == signing_parent:
            raise ValueError(
                "signing-evidence observer CryptoKey must differ"
            )
        observer_public_key = self._client.get_ed25519_public_key(
            name=self._observer_key_resource
        )
        evidence = _decode_signing_evidence_receipt(
            self._read_receipt(), observer_public_key
        )
        if (
            evidence.key_version_resource != signing_key.key_version_resource
            or evidence.key_id != signing_key.kid
            or evidence.public_key_digest != signing_key.public_key_digest
        ):
            raise ValueError("signing-evidence receipt names another signing key")
        return evidence


@final
class GoogleKmsEd25519Signer:
    """Sign raw canonical bytes with one pinned EC_SIGN_ED25519 HSM version."""

    def __init__(
        self,
        *,
        client: GoogleCloudKmsClientAdapter,
        public_key: GoogleKmsEd25519PublicKey,
    ) -> None:
        self._bind(
            client=client,
            public_key=public_key,
            evidence=None,
            evidence_observer=GoogleKmsSigningEvidenceObserver(),
            now_microseconds=lambda: time.time_ns() // 1_000,
            production_eligible=True,
        )

    @classmethod
    def for_test(
        cls,
        *,
        client: GoogleCloudKmsClientAdapter,
        public_key: GoogleKmsEd25519PublicKey,
        evidence: ProductionSigningEvidence,
        evidence_observer: GoogleKmsSigningEvidenceObserver | None = None,
        now_microseconds=lambda: time.time_ns() // 1_000,
    ) -> "GoogleKmsEd25519Signer":
        """Build a visibly non-production signer with a controllable clock."""

        signer = object.__new__(cls)
        signer._bind(
            client=client,
            public_key=public_key,
            evidence=evidence,
            evidence_observer=evidence_observer,
            now_microseconds=now_microseconds,
            production_eligible=False,
        )
        return signer

    def _bind(
        self,
        *,
        client: GoogleCloudKmsClientAdapter,
        public_key: GoogleKmsEd25519PublicKey,
        evidence: ProductionSigningEvidence | None,
        evidence_observer: GoogleKmsSigningEvidenceObserver | None,
        now_microseconds,
        production_eligible: bool,
    ) -> None:
        self._client = client
        self._public_key_observation = public_key
        self._evidence = evidence
        self._evidence_observer = evidence_observer
        self._now_microseconds = now_microseconds
        self._production_eligible = production_eligible
        self._initialized = False
        self._state_condition = threading.Condition()
        self._refresh_in_progress = False
        self._next_refresh_attempt_unix_microseconds = 0
        self._last_accepted_evidence: ProductionSigningEvidence | None = None

    @property
    def key_id(self) -> str:
        return self._public_key_observation.kid

    @property
    def public_key(self) -> bytes:
        return self._public_key_observation.public_key

    @property
    def audience(self) -> str:
        with self._state_condition:
            evidence = self._evidence
        if type(evidence) is not ProductionSigningEvidence:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="authenticated production signing evidence is absent",
            )
        return evidence.audience

    @property
    def production_eligible(self) -> bool:
        return (
            self._production_eligible is True
            and type(self._client) is GoogleCloudKmsClientAdapter
            and self._client.production_eligible
            and type(self._evidence_observer)
            is GoogleKmsSigningEvidenceObserver
            and self._evidence_observer.production_eligible
        )

    def _now(self) -> int:
        now = self._now_microseconds()
        if type(now) is not int:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="production signing clock differs",
            )
        return now

    @staticmethod
    def _is_current(
        evidence: object,
        now_unix_microseconds: int,
    ) -> bool:
        return (
            type(evidence) is ProductionSigningEvidence
            and type(evidence.valid_until_unix_microseconds) is int
            and now_unix_microseconds
            < evidence.valid_until_unix_microseconds
        )

    def _observe_candidate(self) -> ProductionSigningEvidence:
        observer = self._evidence_observer
        if type(observer) is not GoogleKmsSigningEvidenceObserver:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="production evidence observer differs",
            )
        if self._production_eligible and not observer.production_eligible:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="production evidence observer differs",
            )
        try:
            return observer.observe(self._public_key_observation)
        except Exception as exc:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail=(
                    "authenticated production signing evidence is unavailable"
                ),
            ) from exc

    def _validate_candidate(
        self,
        evidence: object,
    ) -> ProductionSigningEvidence:
        now = self._now()
        observation = self._public_key_observation
        if (
            type(self._client) is not GoogleCloudKmsClientAdapter
            or type(evidence) is not ProductionSigningEvidence
            or type(observation) is not GoogleKmsEd25519PublicKey
        ):
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="production signing evidence shape differs",
            )
        try:
            validate_binder_audience(evidence.audience)
            validate_google_kms_key_version_resource(
                evidence.key_version_resource
            )
            expected_public_digest = raw_public_key_digest(
                observation.public_key
            )
            expected_key_id = derive_ed25519_key_id(
                observation.public_key
            )
            expected_x = (
                base64.urlsafe_b64encode(observation.public_key)
                .rstrip(b"=")
                .decode("ascii")
            )
        except (TenantCapabilityContractError, UnicodeError, ValueError) as exc:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="signing evidence grammar differs",
            ) from exc
        if (
            observation.key_version_resource != evidence.key_version_resource
            or observation.kid != evidence.key_id
            or observation.public_key_digest != evidence.public_key_digest
            or observation.public_key_digest != expected_public_digest
            or expected_key_id != evidence.key_id
            or observation.der
            != TENANT_CAPABILITY_RFC8410_PREFIX + observation.public_key
            or observation.x != expected_x
            or evidence.key_purpose != GOOGLE_KMS_KEY_PURPOSE
            or evidence.key_algorithm != GOOGLE_KMS_KEY_ALGORITHM
            or evidence.protection_level != GOOGLE_KMS_PROTECTION_LEVEL
            or evidence.key_state != "ENABLED"
            or any(
                type(value) is not str or _SHA256_ID.fullmatch(value) is None
                for value in (
                    evidence.attestation_evidence_digest,
                    evidence.iam_evidence_digest,
                    evidence.database_candidate_digest,
                    evidence.database_lifecycle_head_digest,
                )
            )
            or type(evidence.observed_at_unix_microseconds) is not int
            or type(evidence.valid_until_unix_microseconds) is not int
            or evidence.observed_at_unix_microseconds > now
            or now - evidence.observed_at_unix_microseconds
            > _PRODUCTION_SIGNING_EVIDENCE_MAX_AGE_MICROSECONDS
            or evidence.observed_at_unix_microseconds
            >= evidence.valid_until_unix_microseconds
            or evidence.valid_until_unix_microseconds
            - evidence.observed_at_unix_microseconds
            > _PRODUCTION_SIGNING_EVIDENCE_MAX_AGE_MICROSECONDS
            or now >= evidence.valid_until_unix_microseconds
        ):
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="production signing evidence differs or is stale",
            )
        self._sign_with_evidence(
            TENANT_CAPABILITY_PREFLIGHT_PROBE,
            evidence,
        )
        if self._now() >= evidence.valid_until_unix_microseconds:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail=(
                    "production signing evidence expired during preflight"
                ),
            )
        return evidence

    @staticmethod
    def _candidate_is_no_progress(
        candidate: ProductionSigningEvidence,
        previous: ProductionSigningEvidence | None,
    ) -> bool:
        if previous is None:
            return False
        if (
            candidate.observed_at_unix_microseconds
            < previous.observed_at_unix_microseconds
        ):
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail=(
                    "production signing evidence observation rolls back"
                ),
            )
        if (
            candidate.observed_at_unix_microseconds
            == previous.observed_at_unix_microseconds
        ):
            if candidate != previous:
                raise CapabilityIssuanceError(
                    PreBindingOutcome.SIGNER_UNAVAILABLE,
                    internal_detail=(
                        "production signing evidence conflicts at one "
                        "observation time"
                    ),
                )
            return True
        return False

    def _refresh_evidence(
        self,
        *,
        force: bool,
        allow_previous: bool,
    ) -> ProductionSigningEvidence:
        now = self._now()
        refresh_started = False
        with self._state_condition:
            current = self._evidence if self._initialized else None
            previous_accepted = self._last_accepted_evidence
            observer = self._evidence_observer
            if observer is None:
                if not force and self._is_current(current, now):
                    assert type(current) is ProductionSigningEvidence
                    return current
                if not force:
                    raise CapabilityIssuanceError(
                        PreBindingOutcome.SIGNER_UNAVAILABLE,
                        internal_detail="production signing evidence expired",
                    )
                candidate = self._evidence
            else:
                if type(observer) is not GoogleKmsSigningEvidenceObserver:
                    raise CapabilityIssuanceError(
                        PreBindingOutcome.SIGNER_UNAVAILABLE,
                        internal_detail="production evidence observer differs",
                    )
                if (
                    not force
                    and self._is_current(current, now)
                    and current.valid_until_unix_microseconds - now
                    > _SIGNING_EVIDENCE_REFRESH_WINDOW_MICROSECONDS
                ):
                    assert type(current) is ProductionSigningEvidence
                    return current
                if self._refresh_in_progress:
                    if self._is_current(current, now):
                        assert type(current) is ProductionSigningEvidence
                        return current
                    self._state_condition.wait(
                        timeout=_SIGNING_EVIDENCE_REFRESH_WAIT_SECONDS
                    )
                    completed = self._evidence if self._initialized else None
                    completed_at = self._now()
                    if self._is_current(completed, completed_at):
                        assert type(completed) is ProductionSigningEvidence
                        return completed
                    raise CapabilityIssuanceError(
                        PreBindingOutcome.SIGNER_UNAVAILABLE,
                        internal_detail=(
                            "signing-evidence refresh did not complete"
                        ),
                    )
                if (
                    not force
                    and now
                    < self._next_refresh_attempt_unix_microseconds
                ):
                    if self._is_current(current, now):
                        assert type(current) is ProductionSigningEvidence
                        return current
                    raise CapabilityIssuanceError(
                        PreBindingOutcome.SIGNER_UNAVAILABLE,
                        internal_detail=(
                            "signing-evidence refresh retry is deferred"
                        ),
                    )
                self._refresh_in_progress = True
                refresh_started = True
                candidate = None

        try:
            if observer is not None:
                candidate = self._observe_candidate()
            accepted = self._validate_candidate(candidate)
            no_progress = self._candidate_is_no_progress(
                accepted,
                previous_accepted,
            )
            with self._state_condition:
                published_at = self._now()
                if not self._is_current(accepted, published_at):
                    raise CapabilityIssuanceError(
                        PreBindingOutcome.SIGNER_UNAVAILABLE,
                        internal_detail=(
                            "production signing evidence expired before "
                            "publication"
                        ),
                    )
                if self._last_accepted_evidence is not previous_accepted:
                    raise CapabilityIssuanceError(
                        PreBindingOutcome.SIGNER_UNAVAILABLE,
                        internal_detail=(
                            "production signing evidence changed during "
                            "refresh"
                        ),
                    )
                if no_progress:
                    assert previous_accepted is not None
                    self._evidence = previous_accepted
                    accepted = previous_accepted
                    self._next_refresh_attempt_unix_microseconds = (
                        published_at
                        + _SIGNING_EVIDENCE_REFRESH_RETRY_MICROSECONDS
                    )
                else:
                    self._evidence = accepted
                    self._last_accepted_evidence = accepted
                    self._next_refresh_attempt_unix_microseconds = 0
                self._initialized = True
                self._refresh_in_progress = False
                self._state_condition.notify_all()
                return accepted
        except Exception as exc:
            failure = (
                exc
                if isinstance(exc, CapabilityIssuanceError)
                else CapabilityIssuanceError(
                    PreBindingOutcome.SIGNER_UNAVAILABLE,
                    internal_detail="signing-evidence refresh failed",
                )
            )
            try:
                failed_at = self._now()
            except CapabilityIssuanceError:
                failed_at = now
            with self._state_condition:
                if refresh_started:
                    self._refresh_in_progress = False
                self._next_refresh_attempt_unix_microseconds = (
                    failed_at
                    + _SIGNING_EVIDENCE_REFRESH_RETRY_MICROSECONDS
                )
                prior = self._evidence if self._initialized else None
                prior_is_current = self._is_current(prior, failed_at)
                if not prior_is_current:
                    self._initialized = False
                self._state_condition.notify_all()
                if allow_previous and prior_is_current:
                    assert type(prior) is ProductionSigningEvidence
                    return prior
            if failure is exc:
                raise
            raise failure from exc

    def initialize(self) -> None:
        self._refresh_evidence(force=True, allow_previous=False)

    def _sign_with_evidence(
        self,
        data: bytes,
        evidence: ProductionSigningEvidence,
    ) -> bytes:
        before_signing = self._now()
        if before_signing >= evidence.valid_until_unix_microseconds:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="production signing evidence expired",
            )
        try:
            response = self._client.asymmetric_sign(
                name=evidence.key_version_resource,
                data=data,
                data_crc32c=_crc32c(data),
            )
        except Exception as exc:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="KMS signing call failed",
            ) from exc
        after_signing = self._now()
        if after_signing >= evidence.valid_until_unix_microseconds:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail=(
                    "production signing evidence expired during KMS call"
                ),
            )
        if (
            type(response) is not GoogleKmsSigningResponse
            or response.key_version_resource != evidence.key_version_resource
            or response.protection_level != GOOGLE_KMS_PROTECTION_LEVEL
            or response.verified_data_crc32c is not True
            or type(response.signature) is not bytes
            or len(response.signature) != 64
            or type(response.signature_crc32c) is not int
            or not 0 <= response.signature_crc32c <= 0xFFFFFFFF
            or _crc32c(response.signature) != response.signature_crc32c
        ):
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="KMS signing response differs",
            )
        try:
            Ed25519PublicKey.from_public_bytes(self.public_key).verify(
                response.signature, data
            )
        except (ValueError, InvalidSignature) as exc:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="KMS signature verification failed",
            ) from exc
        return response.signature

    def sign(self, data: bytes) -> bytes:
        if type(data) is not bytes or not data or len(data) > 8_192:
            raise CapabilityIssuanceError(
                PreBindingOutcome.CAPABILITY_REFUSED,
                internal_detail="signing input is outside the bound",
            )
        with self._state_condition:
            if not self._initialized:
                raise CapabilityIssuanceError(
                    PreBindingOutcome.SIGNER_UNAVAILABLE,
                    internal_detail="production signer is not initialized",
                )
        evidence = self._refresh_evidence(
            force=False,
            allow_previous=True,
        )
        return self._sign_with_evidence(data, evidence)


class CapabilitySigner(Protocol):
    @property
    def key_id(self) -> str: ...

    @property
    def public_key(self) -> bytes: ...

    @property
    def audience(self) -> str: ...

    def initialize(self) -> None: ...

    def sign(self, data: bytes) -> bytes: ...


class CapabilityBindingResolver(Protocol):
    def initialize(self) -> None: ...

    def resolve(self, identity: VerifiedOidcIdentity) -> PrincipalBindingAuthority: ...


@final
class ProductionTenantCapabilityIssuer:
    """Mint one exact, short-lived capability for one fresh DB challenge."""

    def __init__(
        self,
        *,
        resolver: CapabilityBindingResolver,
        signer: CapabilitySigner,
        lifetime_microseconds: int = 30_000_000,
    ) -> None:
        self._require_production_resolver(resolver)
        self._bind(
            resolver=resolver,
            signer=signer,
            lifetime_microseconds=lifetime_microseconds,
            now_microseconds=lambda: time.time_ns() // 1_000,
            test_only_dependencies_allowed=False,
        )

    def _bind(
        self,
        *,
        resolver: CapabilityBindingResolver,
        signer: CapabilitySigner,
        lifetime_microseconds: int,
        now_microseconds,
        test_only_dependencies_allowed: bool,
    ) -> None:
        self._resolver = resolver
        self._signer = signer
        self._lifetime_microseconds = lifetime_microseconds
        self._now_microseconds = now_microseconds
        self._initialized = False
        self._test_only_dependencies_allowed = test_only_dependencies_allowed

    @classmethod
    def for_test(
        cls,
        *,
        resolver: CapabilityBindingResolver,
        signer: CapabilitySigner,
        lifetime_microseconds: int = 30_000_000,
        now_microseconds=lambda: time.time_ns() // 1_000,
    ) -> "ProductionTenantCapabilityIssuer":
        """Explicit fixture seam; production application factories never call it."""

        issuer = object.__new__(cls)
        issuer._bind(
            resolver=resolver,
            signer=signer,
            lifetime_microseconds=lifetime_microseconds,
            now_microseconds=now_microseconds,
            test_only_dependencies_allowed=True,
        )
        return issuer

    @staticmethod
    def _require_production_resolver(resolver: object) -> None:
        if type(resolver) is not PostgreSQLPrincipalBindingResolver:
            raise CapabilityIssuanceError(
                PreBindingOutcome.CONFIGURATION_REFUSED,
                internal_detail=(
                    "production issuer requires the sealed PostgreSQL "
                    "principal-binding resolver"
                ),
            )

    def initialize(self) -> None:
        if (
            type(self._lifetime_microseconds) is not int
            or not 1
            <= self._lifetime_microseconds
            <= TENANT_CAPABILITY_MAX_TTL_MICROSECONDS
        ):
            raise CapabilityIssuanceError(
                PreBindingOutcome.CONFIGURATION_REFUSED,
                internal_detail="capability lifetime is invalid",
            )
        if (
            type(self._signer) is not GoogleKmsEd25519Signer
            or (
                not self._test_only_dependencies_allowed
                and not self._signer.production_eligible
            )
        ):
            raise CapabilityIssuanceError(
                PreBindingOutcome.CONFIGURATION_REFUSED,
                internal_detail="production issuer requires the KMS HSM signer",
            )
        if (
            not self._test_only_dependencies_allowed
            and type(self._resolver) is not PostgreSQLPrincipalBindingResolver
        ):
            self._require_production_resolver(self._resolver)
        try:
            self._resolver.initialize()
            self._signer.initialize()
            validate_binder_audience(self._signer.audience)
        except CapabilityIssuanceError:
            raise
        except Exception as exc:
            raise CapabilityIssuanceError(
                PreBindingOutcome.CONFIGURATION_REFUSED,
                internal_detail="capability issuer initialization failed",
            ) from exc
        self._initialized = True

    def mint(self, identity: VerifiedOidcIdentity, challenge: TenantChallenge) -> str:
        if not self._initialized:
            raise CapabilityIssuanceError(
                PreBindingOutcome.CONFIGURATION_REFUSED,
                internal_detail="capability issuer is not initialized",
            )
        if (
            type(challenge) is not TenantChallenge
            or type(challenge.challenge_id) is not UUID
            or challenge.challenge_id.int == 0
            or challenge.audience != self._signer.audience
        ):
            raise CapabilityIssuanceError(
                PreBindingOutcome.CAPABILITY_REFUSED,
                internal_detail="tenant challenge differs",
            )
        if (
            type(identity) is not VerifiedOidcIdentity
            or identity.equality_policy != OIDC_ISSUER_EQUALITY_POLICY
        ):
            raise CapabilityIssuanceError(
                PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
                internal_detail="verified principal identity differs",
            )
        try:
            authority = self._resolver.resolve(identity)
        except OidcError as exc:
            raise CapabilityIssuanceError(
                exc.outcome, internal_detail="principal binding refused capability"
            ) from exc
        if (
            type(authority) is not PrincipalBindingAuthority
            or authority.equality_policy != identity.equality_policy
            or authority.issuer != identity.issuer
            or authority.subject != identity.subject
        ):
            raise CapabilityIssuanceError(
                PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
                internal_detail="resolved principal identity differs",
            )
        now = self._now_microseconds()
        capability = TenantCapability(
            contract_digest=TENANT_CAPABILITY_CONTRACT.raw_digest,
            challenge_id=challenge.challenge_id,
            audience=challenge.audience,
            key_id=self._signer.key_id,
            equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
            issuer=identity.issuer,
            subject=identity.subject,
            binding_version_id=authority.binding_version_id,
            binding_version_digest=_raw_digest(authority.binding_version_digest),
            lifecycle_head_id=authority.lifecycle_head_id,
            lifecycle_head_digest=_raw_digest(authority.lifecycle_head_digest),
            tenant_id=authority.tenant_id,
            tenant_registration_digest=_raw_digest(
                authority.tenant_registration_digest
            ),
            party_ref=authority.party_ref,
            party_record_kind=authority.party_record_kind,
            party_record_id=authority.party_record_id,
            party_schema_digest=_raw_digest(authority.party_schema_digest),
            party_payload_digest=_raw_digest(authority.party_payload_digest),
            issued_at_unix_microseconds=now,
            not_before_unix_microseconds=now,
            expires_at_unix_microseconds=now + self._lifetime_microseconds,
            nonce=uuid4(),
        )
        try:
            validate_tenant_capability(capability, now_unix_microseconds=now)
            signing_input = canonical_jws_signing_input(capability)
            signature = self._signer.sign(signing_input)
            Ed25519PublicKey.from_public_bytes(self._signer.public_key).verify(
                signature, signing_input
            )
            completed_at = self._now_microseconds()
            validate_tenant_capability(
                capability,
                now_unix_microseconds=completed_at,
            )
            return serialize_tenant_capability_jws(capability, signature)
        except CapabilityIssuanceError:
            raise
        except (TenantCapabilityContractError, ValueError, InvalidSignature) as exc:
            raise CapabilityIssuanceError(
                PreBindingOutcome.CAPABILITY_REFUSED,
                internal_detail="capability construction or verification refused",
            ) from exc


def _raw_digest(value: str) -> bytes:
    if type(value) is not str or _SHA256_ID.fullmatch(value) is None:
        raise CapabilityIssuanceError(
            PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
            internal_detail="immutable binding digest differs",
        )
    return bytes.fromhex(value.removeprefix("sha256:"))


def _crc32c(value: bytes) -> int:
    checksum = 0xFFFFFFFF
    for octet in value:
        checksum ^= octet
        for _ in range(8):
            checksum = (checksum >> 1) ^ (
                0x82F63B78 if checksum & 1 else 0
            )
    return checksum ^ 0xFFFFFFFF


__all__ = [
    "CapabilityIssuanceError",
    "GoogleCloudKmsClientAdapter",
    "GoogleKmsEd25519Signer",
    "GoogleKmsSigningEvidenceObserver",
    "GoogleKmsSigningResponse",
    "ProductionSigningEvidence",
    "ProductionTenantCapabilityIssuer",
    "TenantChallenge",
]
