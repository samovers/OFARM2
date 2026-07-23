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
from .runtime_bundle import RuntimeBundleError, RuntimeComponentRole


PROFILE_RUNTIME_PROVIDER_REGISTRY_COMPONENT_REF = (
    "python:ofarm2-kernel-m1.0:profile-runtime-provider-registry"
)
_PROFILE_RUNTIME_PROVIDER_REGISTRY_SOURCE_BYTES = (
    Path(__file__).resolve(strict=True).read_bytes()
)


class ProfileRuntimeProvider(Protocol):
    """A deliberately registered constructor for one executable profile."""

    package_name: str
    profile_ref: str
    runtime_component_ref: str
    runtime_component_bytes: bytes

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
        refs = [provider.runtime_component_ref for provider in self.providers]
        if any(not isinstance(ref, str) or not ref for ref in refs):
            raise ProfileRuntimeError(
                "profile runtime provider component refs must be non-empty strings"
            )

    @property
    def runtime_component_ref(self) -> str:
        """The immutable selected-source identity for this selector."""
        return PROFILE_RUNTIME_PROVIDER_REGISTRY_COMPONENT_REF

    @property
    def registered_package_names(self) -> tuple[str, ...]:
        return tuple(provider.package_name for provider in self.providers)

    def provider_for(
        self,
        package_name: str,
        descriptor: ProfileRuntimeDescriptor,
    ) -> ProfileRuntimeProvider:
        if package_name != descriptor.package_name:
            raise ProfileRuntimeError(
                f"selected profile package {package_name!r} does not match "
                f"descriptor package identity {descriptor.package_name!r}"
            )
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

    def verify_registry_source(self, runtime_bundle) -> None:
        """Bind provider selection itself to the activated source bytes."""
        _require_selected_source(
            runtime_bundle,
            self.runtime_component_ref,
            _PROFILE_RUNTIME_PROVIDER_REGISTRY_SOURCE_BYTES,
            "profile runtime provider registry",
        )

    def verify_selected_provider_source(
        self,
        runtime_bundle,
        provider: ProfileRuntimeProvider,
    ) -> None:
        """Bind only the selected provider to its activated source bytes."""
        if not any(candidate is provider for candidate in self.providers):
            raise ProfileRuntimeError(
                "selected profile runtime provider is not registered")
        _require_selected_source(
            runtime_bundle,
            provider.runtime_component_ref,
            provider.runtime_component_bytes,
            f"profile runtime provider for {provider.package_name!r}",
        )

    def verify_selected_sources(
        self,
        runtime_bundle,
        provider: ProfileRuntimeProvider,
    ) -> None:
        """Bind the selector and selected provider to activated source bytes."""
        self.verify_registry_source(runtime_bundle)
        self.verify_selected_provider_source(runtime_bundle, provider)

    def build_services(
        self,
        store,
        package_name: str,
        descriptor: ProfileRuntimeDescriptor,
    ) -> ProfileRuntimeServices:
        self.verify_registry_source(store.runtime_bundle)
        provider = self.provider_for(package_name, descriptor)
        self.verify_selected_provider_source(store.runtime_bundle, provider)
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

    global _DEFAULT_PROFILE_RUNTIME_PROVIDER_REGISTRY
    if _DEFAULT_PROFILE_RUNTIME_PROVIDER_REGISTRY is None:
        _DEFAULT_PROFILE_RUNTIME_PROVIDER_REGISTRY = \
            ProfileRuntimeProviderRegistry((SI_RUNTIME_PROVIDER,))
    return _DEFAULT_PROFILE_RUNTIME_PROVIDER_REGISTRY


_DEFAULT_PROFILE_RUNTIME_PROVIDER_REGISTRY: ProfileRuntimeProviderRegistry | None = None


def _require_selected_source(
    runtime_bundle,
    logical_ref: str,
    executable_bytes: bytes,
    label: str,
) -> None:
    if type(executable_bytes) is not bytes:
        raise ProfileRuntimeError(f"{label} executable source bytes are unavailable")
    try:
        component = runtime_bundle.component(
            RuntimeComponentRole.ADAPTER_SOURCE,
            logical_ref,
        )
    except (AttributeError, RuntimeBundleError) as exc:
        raise ProfileRuntimeError(
            f"{label} source {logical_ref!r} is not selected by the "
            "activated RuntimeBundle"
        ) from exc
    if component.canonical_bytes != executable_bytes:
        raise ProfileRuntimeError(
            f"{label} source {logical_ref!r} does not match the exact "
            "executable bytes selected by the activated RuntimeBundle"
        )
