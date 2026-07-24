"""Concrete values crossing the principal-authority boundary."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TENANT_CAPABILITY_PARTY_RECORD_KIND,
)

from .authentication import VerifiedIdentity

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_PARTY_REF = re.compile(r"[A-Za-z0-9._:-]{1,255}")

class PrincipalResolutionOutcome(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    AUTHORITY_UNAVAILABLE = "AUTHORITY_UNAVAILABLE"

class PrincipalResolutionError(RuntimeError):
    def __init__(self, outcome: PrincipalResolutionOutcome) -> None:
        self.outcome = outcome
        super().__init__(f"principal resolution refused ({outcome.value})")

class PrincipalResolutionStartupError(RuntimeError):
    pass

def _uuid(value: object, label: str) -> UUID:
    if type(value) is not UUID or value.int == 0:
        raise ValueError(f"{label} is invalid")
    return value

def _digest(value: object, label: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{label} is invalid")
    return value

def _text(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{label} is invalid")
    return value

def _time(value: object, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} is invalid")
    return value

@dataclass(frozen=True, slots=True)
class PrincipalAuthority:
    equality_policy: str
    issuer: str
    subject: str
    binding_version_id: UUID
    binding_version_digest: str
    lifecycle_head_id: UUID
    lifecycle_head_digest: str
    tenant_id: UUID
    tenant_registration_digest: str
    party_ref: str
    party_record_kind: str
    party_record_id: str
    party_schema_digest: str
    party_payload_digest: str
    party_state: str
    valid_from: datetime
    valid_until: datetime

    @classmethod
    def from_database_row(
        cls,
        row: tuple[object, ...],
        identity: VerifiedIdentity,
    ) -> PrincipalAuthority:
        if len(row) != 17:
            raise ValueError("principal authority row shape differs")
        (
            policy,
            issuer,
            subject,
            version_id,
            version_digest,
            head_id,
            head_digest,
            tenant_id,
            registration_digest,
            party_ref,
            party_kind,
            party_record_id,
            party_schema_digest,
            party_payload_digest,
            party_state,
            valid_from,
            valid_until,
        ) = row
        if (
            policy != OIDC_ISSUER_EQUALITY_POLICY
            or policy != identity.equality_policy
            or issuer != identity.issuer
            or subject != identity.subject
            or party_kind != TENANT_CAPABILITY_PARTY_RECORD_KIND
            or party_state != "ACTIVE"
        ):
            raise ValueError("principal authority identity differs")
        checked_party_ref = _text(party_ref, "party ref")
        checked_record_id = _text(party_record_id, "party record id")
        if (
            _PARTY_REF.fullmatch(checked_party_ref) is None
            or checked_record_id != checked_party_ref
        ):
            raise ValueError("principal Party identity differs")
        checked_from = _time(valid_from, "valid from")
        checked_until = _time(valid_until, "valid until")
        if checked_from >= checked_until:
            raise ValueError("principal validity window differs")
        return cls(
            equality_policy=policy,
            issuer=issuer,
            subject=subject,
            binding_version_id=_uuid(version_id, "binding version id"),
            binding_version_digest=_digest(version_digest, "version digest"),
            lifecycle_head_id=_uuid(head_id, "lifecycle head id"),
            lifecycle_head_digest=_digest(head_digest, "lifecycle head digest"),
            tenant_id=_uuid(tenant_id, "tenant id"),
            tenant_registration_digest=_digest(registration_digest, "tenant digest"),
            party_ref=checked_party_ref,
            party_record_kind=party_kind,
            party_record_id=checked_record_id,
            party_schema_digest=_digest(party_schema_digest, "Party schema digest"),
            party_payload_digest=_digest(party_payload_digest, "Party payload digest"),
            party_state=party_state,
            valid_from=checked_from,
            valid_until=checked_until,
        )

@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    identity: VerifiedIdentity
    authority: PrincipalAuthority

    def __post_init__(self) -> None:
        if (
            self.identity.equality_policy != self.authority.equality_policy
            or self.identity.issuer != self.authority.issuer
            or self.identity.subject != self.authority.subject
        ):
            raise ValueError("authenticated principal identity differs")
