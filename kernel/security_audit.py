"""Closed values crossing the pre-tenant security-audit boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT


class SecurityAuditError(RuntimeError):
    """Base class for closed audit-ingest failures."""


class SecurityAuditUnavailable(SecurityAuditError):
    def __init__(self) -> None:
        super().__init__("security audit is unavailable")


class SecurityAuditRefused(SecurityAuditError):
    def __init__(self) -> None:
        super().__init__("security audit append was refused")


class SecurityAuditOutcomeUnknown(SecurityAuditError):
    def __init__(
        self,
        event_id: UUID,
        possible_overflow_bucket: OverflowBucket | None,
    ) -> None:
        self.event_id = event_id
        self.possible_overflow_bucket = possible_overflow_bucket
        super().__init__("security audit append outcome is unknown")


@dataclass(frozen=True, slots=True)
class CorrelationHmac:
    value: bytes = field(repr=False)
    key_version: int

    def __post_init__(self) -> None:
        policy = SECURITY_AUDIT_CONTRACT.correlation_hmac
        if (
            type(self.value) is not bytes
            or len(self.value) != policy.length_bytes
            or type(self.key_version) is not int
            or self.key_version != policy.key_version
        ):
            raise ValueError("correlation HMAC is invalid")


@dataclass(frozen=True, slots=True)
class OverflowBucket:
    producer: str
    component: str
    bucket_start: datetime


@dataclass(frozen=True, slots=True)
class StoredAuditAppend:
    event_id: UUID
    observed_at: datetime
    purge_after: datetime


@dataclass(frozen=True, slots=True)
class OverflowAuditAppend:
    event_id: UUID
    bucket: OverflowBucket
    count_unknown: bool


SecurityAuditAppend = StoredAuditAppend | OverflowAuditAppend
