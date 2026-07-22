"""Explicit, code-owned profile runtime provider selection.

Descriptors describe package content. They never import executable code or make
that code available merely by existing on disk. This module is the trusted
composition seam that maps a deliberately registered package to the services
the current runtime already needs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .profile_runtime import ProfileRuntimeDescriptor, ProfileRuntimeError


class ProfileRuntimeProvider(Protocol):
    """A deliberately registered constructor for one executable profile."""

    package_name: str
    profile_ref: str

    def build_services(
        self,
        store,
        descriptor: ProfileRuntimeDescriptor,
    ) -> "ProfileRuntimeServices": ...


@dataclass(frozen=True)
class ProfileRuntimeServices:
    """Capability-specific services selected for one bound descriptor.

    Optional service slots do not require future profiles to implement the SI
    product-register surface. A provider supplies only the services its later,
    separately reviewed runtime slice actually uses.
    """

    provider: ProfileRuntimeProvider
    descriptor: ProfileRuntimeDescriptor
    policy_provider: Any
    context_assembler: Any
    materializer: Any
    reference_bindings: Any = None
    product_lookup: Any = None


@dataclass(frozen=True)
class ProfileRuntimeProviderRegistry:
    """Immutable executable-provider registrations owned by trusted code."""

    providers: tuple[ProfileRuntimeProvider, ...]

    def __post_init__(self) -> None:
        names = [provider.package_name for provider in self.providers]
        if any(not isinstance(name, str) or not name for name in names):
            raise ProfileRuntimeError(
                "profile runtime provider package names must be non-empty strings"
            )
        if len(names) != len(set(names)):
            raise ProfileRuntimeError(
                "profile runtime provider registry contains duplicate package names"
            )

    @property
    def registered_package_names(self) -> tuple[str, ...]:
        return tuple(provider.package_name for provider in self.providers)

    def provider_for(
        self,
        descriptor: ProfileRuntimeDescriptor,
    ) -> ProfileRuntimeProvider:
        package_name = _descriptor_package_name(descriptor)
        provider = next(
            (
                candidate
                for candidate in self.providers
                if candidate.package_name == package_name
            ),
            None,
        )
        if provider is None:
            raise ProfileRuntimeError(
                "no registered executable runtime provider for profile package "
                f"{package_name!r}"
            )
        if provider.profile_ref != descriptor.profile_ref:
            raise ProfileRuntimeError(
                f"registered runtime provider for {package_name!r} does not support "
                f"descriptor profileRef {descriptor.profile_ref!r}"
            )
        return provider

    def build_services(
        self,
        store,
        descriptor: ProfileRuntimeDescriptor,
    ) -> ProfileRuntimeServices:
        provider = self.provider_for(descriptor)
        services = provider.build_services(store, descriptor)
        if services.provider is not provider or services.descriptor != descriptor:
            raise ProfileRuntimeError(
                "profile runtime provider returned services for a different provider "
                "or descriptor"
            )
        return services


def default_profile_runtime_provider_registry() -> ProfileRuntimeProviderRegistry:
    """Return the code-owned registry; RS1 deliberately registers SI only."""
    from .profiles.si_ffs.runtime_provider import SI_RUNTIME_PROVIDER

    return ProfileRuntimeProviderRegistry((SI_RUNTIME_PROVIDER,))


def _descriptor_package_name(descriptor: ProfileRuntimeDescriptor) -> str:
    try:
        package_name = Path(descriptor.profile_root).name
    except (AttributeError, TypeError) as exc:
        raise ProfileRuntimeError(
            "profile runtime descriptor package name is unavailable"
        ) from exc
    if not package_name:
        raise ProfileRuntimeError(
            "profile runtime descriptor package name is unavailable"
        )
    return package_name
