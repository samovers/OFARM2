"""Shared, closed values crossing authentication trust boundaries."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuthenticationOutcome(str, Enum):
    VERIFIED = "VERIFIED"
    NO_CREDENTIAL = "NO_CREDENTIAL"
    INVALID_CREDENTIAL = "INVALID_CREDENTIAL"
    VERIFIER_UNAVAILABLE = "VERIFIER_UNAVAILABLE"
    CONFIGURATION_REFUSED = "CONFIGURATION_REFUSED"


class AuthenticationError(Exception):
    def __init__(
        self,
        outcome: AuthenticationOutcome,
        *,
        internal_detail: str,
    ) -> None:
        self.outcome = outcome
        self.internal_detail = internal_detail
        super().__init__(f"authentication refused ({outcome.value})")


class AuthenticationStartupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    equality_policy: str
    issuer: str
    subject: str
