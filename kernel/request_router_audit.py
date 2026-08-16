"""Request-router production of pre-tenant audit evidence."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from types import MappingProxyType
from typing import Protocol

from .principal import AuthenticatedPrincipal
from .security_audit import SecurityAuditAppend
from .security_audit_gap import (
    SecurityAuditGapOutcomeUnknown,
    SecurityAuditGapUnavailable,
)
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
        gap_error: _GapErrorType | None = None
        with ExitStack() as stack:
            try:
                unit = stack.enter_context(
                    self._tenant_boundary.unit_of_work(principal)
                )
            except TenantBoundaryError as error:
                reason = _REASONS.get(error.outcome)
                if reason is None:
                    raise
                gap_error = _append_or_defer_gap_error(
                    self._audit_sink,
                    reason,
                )
                if gap_error is None:
                    raise
            if gap_error is not None:
                raise gap_error()
            yield unit
