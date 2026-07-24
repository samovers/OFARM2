"""Construct and sign one frozen TenantCapability per database challenge."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from deployment.postgresql.tenant_contract import (
    TENANT_CAPABILITY_CONTRACT,
    TENANT_CAPABILITY_MAX_TTL_MICROSECONDS,
    TenantCapability,
    TenantCapabilityContractError,
    canonical_jws_signing_input,
    serialize_tenant_capability_jws,
    validate_tenant_capability,
)

from .authentication import VerifiedIdentity
from .google_kms_signer import GoogleKmsSigner, KmsSigningError
from .principal import PrincipalAuthority
from .signing_authority import (
    SigningAuthority,
    SigningAuthorityReader,
    SigningAuthorityUnavailable,
)


class CapabilityMintError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TenantChallenge:
    challenge_id: UUID
    audience: str


def _raw_digest(value: str) -> bytes:
    if (
        type(value) is not str
        or not value.startswith("sha256:")
        or len(value) != 71
    ):
        raise CapabilityMintError("capability authority digest is invalid")
    try:
        return bytes.fromhex(value[7:])
    except ValueError as exc:
        raise CapabilityMintError(
            "capability authority digest is invalid"
        ) from exc


def _capability(
    identity: VerifiedIdentity,
    authority: PrincipalAuthority,
    challenge: TenantChallenge,
    signing: SigningAuthority,
    nonce: UUID,
) -> TenantCapability:
    issued_at = signing.observed_at_us
    return TenantCapability(
        contract_digest=TENANT_CAPABILITY_CONTRACT.raw_digest,
        challenge_id=challenge.challenge_id,
        audience=challenge.audience,
        key_id=signing.kid,
        equality_policy=identity.equality_policy,
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
        issued_at_unix_microseconds=issued_at,
        not_before_unix_microseconds=issued_at,
        expires_at_unix_microseconds=min(
            issued_at + TENANT_CAPABILITY_MAX_TTL_MICROSECONDS,
            signing.issuance_end_us,
        ),
        nonce=nonce,
    )


class TenantCapabilityIssuer:
    """Pin one key; rebuild on rotation; spend challenges and nonces once."""

    def __init__(
        self,
        signing_authority_reader: SigningAuthorityReader,
        signer: GoogleKmsSigner,
        *,
        kid: str,
        nonce_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._signing_authority_reader = signing_authority_reader
        self._signer = signer
        self._kid = kid
        self._nonce_factory = nonce_factory

    def mint(
        self,
        identity: VerifiedIdentity,
        authority: PrincipalAuthority,
        challenge: TenantChallenge,
    ) -> str:
        if (
            type(challenge) is not TenantChallenge
            or type(challenge.challenge_id) is not UUID
            or challenge.challenge_id.int == 0
            or (
                identity.equality_policy,
                identity.issuer,
                identity.subject,
            )
            != (
                authority.equality_policy,
                authority.issuer,
                authority.subject,
            )
        ):
            raise CapabilityMintError("capability inputs differ")
        try:
            signing = self._signing_authority_reader.current(self._kid)
            if challenge.audience != signing.audience:
                raise CapabilityMintError("challenge audience differs")
            capability = _capability(
                identity,
                authority,
                challenge,
                signing,
                self._nonce_factory(),
            )
            validate_tenant_capability(
                capability,
                now_unix_microseconds=signing.observed_at_us,
            )
            signature = self._signer.sign(
                canonical_jws_signing_input(capability),
                signing,
            )
            return serialize_tenant_capability_jws(capability, signature)
        except (
            KmsSigningError,
            SigningAuthorityUnavailable,
            TenantCapabilityContractError,
        ) as exc:
            raise CapabilityMintError("capability mint refused") from exc
