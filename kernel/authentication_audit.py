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


class CredentialVerifier(Protocol):
    def verify(self, token: object) -> VerifiedIdentity: ...


class PrincipalResolver(Protocol):
    def resolve(self, identity: VerifiedIdentity) -> AuthenticatedPrincipal: ...


class AuditSink(Protocol):
    def append(self, reason: str) -> SecurityAuditAppend: ...


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
        try:
            identity = self._verifier.verify(token)
        except AuthenticationError as error:
            self._audit_sink.append(_AUTHENTICATION_REASONS[error.outcome])
            raise
        try:
            return self._resolver.resolve(identity)
        except PrincipalResolutionError as error:
            self._audit_sink.append(_PRINCIPAL_REASONS[error.outcome])
            raise
