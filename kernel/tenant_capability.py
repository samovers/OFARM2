"""Production TenantCapability minting and the Google KMS HSM signer boundary."""
from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from deployment.postgresql.tenant_contract import (
    GOOGLE_KMS_KEY_ALGORITHM,
    GOOGLE_KMS_KEY_PURPOSE,
    GOOGLE_KMS_PROTECTION_LEVEL,
    OIDC_ISSUER_EQUALITY_POLICY,
    TENANT_CAPABILITY_CONTRACT,
    TENANT_CAPABILITY_MAX_TTL_MICROSECONDS,
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
from .principal_binding import PrincipalBindingAuthority


_SHA256_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


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


class GoogleKmsRawSigningClient(Protocol):
    """Narrow adapter over Cloud KMS ``cryptoKeyVersions.asymmetricSign``."""

    def asymmetric_sign(
        self, *, name: str, data: bytes, data_crc32c: int
    ) -> GoogleKmsSigningResponse: ...


class GoogleCloudKmsClientAdapter:
    """Exact adapter for a Google ``KeyManagementServiceClient`` instance.

    The Google client is injected so credentials remain deployment-owned.  The
    adapter requests only raw ``data`` signing and rejects response shapes that
    cannot be mapped without guessing or fallback.
    """

    def __init__(self, client: object) -> None:
        if not callable(getattr(client, "asymmetric_sign", None)):
            raise TypeError("Google KMS client does not expose asymmetric_sign")
        self._client = client

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
        signature_checksum_value = getattr(signature_checksum, "value", None)
        if (
            type(getattr(response, "name", None)) is not str
            or type(protection_name) is not str
            or type(getattr(response, "verified_data_crc32c", None)) is not bool
            or type(getattr(response, "signature", None)) is not bytes
            or type(signature_checksum_value) is not int
        ):
            raise ValueError("Google KMS signing response shape differs")
        return GoogleKmsSigningResponse(
            key_version_resource=response.name,
            protection_level=protection_name,
            verified_data_crc32c=response.verified_data_crc32c,
            signature=response.signature,
            signature_crc32c=signature_checksum_value,
        )


@dataclass(frozen=True, slots=True)
class ProductionSigningEvidence:
    """Fresh observer output required before the signer becomes usable."""

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


class GoogleKmsEd25519Signer:
    """Sign raw canonical bytes with one pinned EC_SIGN_ED25519 HSM version."""

    def __init__(
        self,
        *,
        client: GoogleKmsRawSigningClient,
        public_key: GoogleKmsEd25519PublicKey,
        evidence: ProductionSigningEvidence,
        now_microseconds=lambda: time.time_ns() // 1_000,
    ) -> None:
        self._client = client
        self._public_key_observation = public_key
        self._evidence = evidence
        self._now_microseconds = now_microseconds
        self._initialized = False

    @property
    def key_id(self) -> str:
        return self._public_key_observation.kid

    @property
    def public_key(self) -> bytes:
        return self._public_key_observation.public_key

    @property
    def audience(self) -> str:
        return self._evidence.audience

    def initialize(self) -> None:
        now = self._now_microseconds()
        evidence = self._evidence
        observation = self._public_key_observation
        if (
            type(evidence) is not ProductionSigningEvidence
            or type(observation) is not GoogleKmsEd25519PublicKey
            or type(now) is not int
        ):
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="production signing evidence shape differs",
            )
        try:
            validate_binder_audience(evidence.audience)
            validate_google_kms_key_version_resource(evidence.key_version_resource)
            expected_public_digest = raw_public_key_digest(observation.public_key)
            expected_key_id = derive_ed25519_key_id(observation.public_key)
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
            or evidence.observed_at_unix_microseconds
            >= evidence.valid_until_unix_microseconds
            or now >= evidence.valid_until_unix_microseconds
        ):
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="production signing evidence differs or is stale",
            )
        self._initialized = True

    def sign(self, data: bytes) -> bytes:
        if not self._initialized:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="production signer is not initialized",
            )
        if type(data) is not bytes or not data or len(data) > 8_192:
            raise CapabilityIssuanceError(
                PreBindingOutcome.CAPABILITY_REFUSED,
                internal_detail="signing input is outside the bound",
            )
        if self._now_microseconds() >= self._evidence.valid_until_unix_microseconds:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="production signing evidence expired",
            )
        try:
            response = self._client.asymmetric_sign(
                name=self._evidence.key_version_resource,
                data=data,
                data_crc32c=_crc32c(data),
            )
        except Exception as exc:
            raise CapabilityIssuanceError(
                PreBindingOutcome.SIGNER_UNAVAILABLE,
                internal_detail="KMS signing call failed",
            ) from exc
        if (
            type(response) is not GoogleKmsSigningResponse
            or response.key_version_resource != self._evidence.key_version_resource
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


class ProductionTenantCapabilityIssuer:
    """Mint one exact, short-lived capability for one fresh DB challenge."""

    def __init__(
        self,
        *,
        resolver: CapabilityBindingResolver,
        signer: CapabilitySigner,
        lifetime_microseconds: int = 30_000_000,
        now_microseconds=lambda: time.time_ns() // 1_000,
    ) -> None:
        self._resolver = resolver
        self._signer = signer
        self._lifetime_microseconds = lifetime_microseconds
        self._now_microseconds = now_microseconds
        self._initialized = False

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
        if not isinstance(self._signer, GoogleKmsEd25519Signer):
            raise CapabilityIssuanceError(
                PreBindingOutcome.CONFIGURATION_REFUSED,
                internal_detail="production issuer requires the KMS HSM signer",
            )
        try:
            validate_binder_audience(self._signer.audience)
            self._resolver.initialize()
            self._signer.initialize()
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
    "GoogleKmsRawSigningClient",
    "GoogleKmsSigningResponse",
    "ProductionSigningEvidence",
    "ProductionTenantCapabilityIssuer",
    "TenantChallenge",
]
