"""Authentication-side production of pre-tenant audit evidence."""

from __future__ import annotations

from types import MappingProxyType
from typing import Protocol

from .authentication import (
    AuthenticationError,
    AuthenticationOutcome,
    VerifiedIdentity,
)
from .principal import (
    AuthenticatedPrincipal,
    PrincipalResolutionError,
    PrincipalResolutionOutcome,
)
from .security_audit import SecurityAuditAppend
from .security_audit_gap import (
    SecurityAuditGapOutcomeUnknown,
    SecurityAuditGapUnavailable,
)


class CredentialVerifier(Protocol):
    def verify(self, token: object) -> VerifiedIdentity: ...


class PrincipalResolver(Protocol):
    def resolve(self, identity: VerifiedIdentity) -> AuthenticatedPrincipal: ...


class AuditSink(Protocol):
    def append(self, reason: str) -> SecurityAuditAppend: ...


_GapErrorType = (
    type[SecurityAuditGapUnavailable]
    | type[SecurityAuditGapOutcomeUnknown]
)


def _append_or_defer_gap_error(
    audit_sink: AuditSink,
    reason: str,
) -> _GapErrorType | None:
    try:
        audit_sink.append(reason)
    except (
        SecurityAuditGapUnavailable,
        SecurityAuditGapOutcomeUnknown,
    ) as error:
        if type(error) is SecurityAuditGapUnavailable:
            return SecurityAuditGapUnavailable
        if type(error) is SecurityAuditGapOutcomeUnknown:
            return SecurityAuditGapOutcomeUnknown
        raise
    return None


_AUTHENTICATION_REASONS = MappingProxyType(
    {
        AuthenticationOutcome.NO_CREDENTIAL: "CREDENTIAL_MISSING",
        AuthenticationOutcome.CREDENTIAL_MALFORMED: "CREDENTIAL_MALFORMED",
        AuthenticationOutcome.VERIFIER_UNAVAILABLE: "VERIFIER_UNAVAILABLE",
        AuthenticationOutcome.VERIFICATION_REFUSED: "VERIFICATION_REFUSED",
    }
)
_PRINCIPAL_REASONS = MappingProxyType(
    {
        PrincipalResolutionOutcome.PRINCIPAL_BINDING_REFUSED:
            "PRINCIPAL_BINDING_REFUSED",
        PrincipalResolutionOutcome.AUTHORITY_INTEGRITY_REFUSED:
            "AUTHORITY_INTEGRITY_REFUSED",
        PrincipalResolutionOutcome.AUTHORITY_UNAVAILABLE:
            "AUTHORITY_UNAVAILABLE",
    }
)


class AuthenticationAuditProducer:
    def __init__(
        self,
        verifier: CredentialVerifier,
        resolver: PrincipalResolver,
        audit_sink: AuditSink,
    ) -> None:
        self._verifier = verifier
        self._resolver = resolver
        self._audit_sink = audit_sink

    def authenticate(self, token: object) -> AuthenticatedPrincipal:
        gap_error: _GapErrorType | None = None
        try:
            identity = self._verifier.verify(token)
        except AuthenticationError as error:
            gap_error = _append_or_defer_gap_error(
                self._audit_sink,
                _AUTHENTICATION_REASONS[error.outcome],
            )
            if gap_error is None:
                raise
        if gap_error is not None:
            raise gap_error()
        try:
            return self._resolver.resolve(identity)
        except PrincipalResolutionError as error:
            gap_error = _append_or_defer_gap_error(
                self._audit_sink,
                _PRINCIPAL_REASONS[error.outcome],
            )
            if gap_error is None:
                raise
        if gap_error is not None:
            raise gap_error()
