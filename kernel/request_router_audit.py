"""Request-router production of pre-tenant audit evidence."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from types import MappingProxyType
from typing import Protocol

from .principal import AuthenticatedPrincipal
from .security_audit import SecurityAuditAppend
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


class AuditSink(Protocol):
    def append(self, reason: str) -> SecurityAuditAppend: ...


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
        audit_sink: AuditSink,
    ) -> None:
        self._tenant_boundary = tenant_boundary
        self._audit_sink = audit_sink

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
                self._audit_sink.append(reason)
                raise
            yield unit
