"""Sealed production composition for the application trust boundary."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

from .auth_oidc import (
    AuthenticationMode,
    AuthenticationStartupError,
    ProductionAuthenticationRuntime,
)
from .principal_binding import PostgreSQLPrincipalBindingResolver
from .tenant_capability import ProductionTenantCapabilityIssuer


@final
@dataclass(frozen=True, slots=True)
class AuthenticationRuntimeMetadata:
    """Non-authoritative authentication facts safe to expose for diagnostics."""

    mode: AuthenticationMode
    verifier_kind: str


@final
@dataclass(frozen=True, slots=True)
class ProductionApplicationRuntime:
    """One closed production graph for authentication and capability minting."""

    authentication: ProductionAuthenticationRuntime
    capability_issuer: ProductionTenantCapabilityIssuer
    _authentication_initialized: bool = field(
        default=False,
        init=False,
        repr=False,
        compare=False,
    )
    _initialized: bool = field(
        default=False,
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        self._validate()

    @classmethod
    def from_initialized_authentication(
        cls,
        *,
        authentication: ProductionAuthenticationRuntime,
        capability_issuer: ProductionTenantCapabilityIssuer,
    ) -> "ProductionApplicationRuntime":
        """Bind a graph whose authentication dependencies already passed."""

        runtime = cls(
            authentication=authentication,
            capability_issuer=capability_issuer,
        )
        if getattr(authentication, "_initialized", None) is not True:
            raise AuthenticationStartupError(
                "production authentication initialization is absent"
            )
        # The exact resolver API additionally proves that database-owned
        # binder identity was pinned during authentication initialization.
        authentication.principal_binding_resolver.audience
        object.__setattr__(
            runtime,
            "_authentication_initialized",
            True,
        )
        return runtime

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
        if self._initialized:
            return
        if not self._authentication_initialized:
            self.authentication.initialize()
            object.__setattr__(
                self,
                "_authentication_initialized",
                True,
            )
        self.capability_issuer.initialize()
        object.__setattr__(self, "_initialized", True)


__all__ = [
    "AuthenticationRuntimeMetadata",
    "ProductionApplicationRuntime",
]
