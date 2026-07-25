"""Request-router production of pre-tenant audit evidence."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from types import MappingProxyType
from typing import Protocol

from .principal import AuthenticatedPrincipal
from .security_audit import CorrelationHmac, SecurityAuditAppend
from .tenant_uow import (
    TenantBoundaryError,
    TenantBoundaryOutcome,
    TenantUnitOfWork,
)


class TenantBoundary(Protocol):
    def unit_of_work(
        self,
        principal: AuthenticatedPrincipal,
    ) -> AbstractContextManager[TenantUnitOfWork]: ...


class CorrelationHmacFactory(Protocol):
    def create(self) -> CorrelationHmac: ...


class AuditAppender(Protocol):
    def append(
        self,
        reason: str,
        correlation_hmac: CorrelationHmac,
    ) -> SecurityAuditAppend: ...


_REASONS = MappingProxyType(
    {
        TenantBoundaryOutcome.UNAVAILABLE: "TENANT_BOUNDARY_UNAVAILABLE",
        TenantBoundaryOutcome.CAPABILITY_REFUSED: "CAPABILITY_REFUSED",
        TenantBoundaryOutcome.BINDING_REFUSED: "BINDER_REFUSED",
    }
)


class RequestRouterAuditProducer:
    def __init__(
        self,
        tenant_boundary: TenantBoundary,
        correlation_hmac_factory: CorrelationHmacFactory,
        audit_appender: AuditAppender,
    ) -> None:
        self._tenant_boundary = tenant_boundary
        self._correlation_hmac_factory = correlation_hmac_factory
        self._audit_appender = audit_appender

    def unit_of_work(
        self,
        principal: AuthenticatedPrincipal,
    ) -> AbstractContextManager[TenantUnitOfWork]:
        return self._audited_unit_of_work(principal)

    @contextmanager
    def _audited_unit_of_work(
        self,
        principal: AuthenticatedPrincipal,
    ) -> Iterator[TenantUnitOfWork]:
        with ExitStack() as stack:
            try:
                unit = stack.enter_context(
                    self._tenant_boundary.unit_of_work(principal)
                )
            except TenantBoundaryError as error:
                reason = _REASONS.get(error.outcome)
                if reason is None:
                    raise
                self._append(reason)
                raise
            yield unit

    def _append(self, reason: str) -> None:
        correlation_hmac = self._correlation_hmac_factory.create()
        self._audit_appender.append(reason, correlation_hmac)
