"""Sealed production composition for the application trust boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import final

from .auth_oidc import (
    AuthenticationStartupError,
    ProductionAuthenticationRuntime,
)
from .principal_binding import PostgreSQLPrincipalBindingResolver
from .tenant_capability import ProductionTenantCapabilityIssuer


@final
@dataclass(frozen=True, slots=True)
class ProductionApplicationRuntime:
    """One closed production graph for authentication and capability minting."""

    authentication: ProductionAuthenticationRuntime
    capability_issuer: ProductionTenantCapabilityIssuer

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if type(self.authentication) is not ProductionAuthenticationRuntime:
            raise AuthenticationStartupError(
                "production application composition requires the exact "
                "authentication runtime"
            )
        if type(self.capability_issuer) is not ProductionTenantCapabilityIssuer:
            raise AuthenticationStartupError(
                "production application composition requires the exact "
                "capability issuer"
            )
        resolver = self.authentication.principal_binding_resolver
        if (
            type(resolver) is not PostgreSQLPrincipalBindingResolver
            or getattr(self.capability_issuer, "_resolver", None) is not resolver
        ):
            raise AuthenticationStartupError(
                "production application composition must share one sealed "
                "principal-binding resolver"
            )

    def initialize(self) -> None:
        """Initialize every production dependency before the app is published."""

        self._validate()
        self.authentication.initialize()
        self.capability_issuer.initialize()


__all__ = ["ProductionApplicationRuntime"]
