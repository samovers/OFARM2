"""Explicit, code-owned profile runtime provider selection.

Descriptors describe package content. They never import executable code or make
that code available merely by existing on disk. This module is the trusted
composition seam that maps a deliberately registered package to the services
the current runtime already needs.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

from .profile_runtime import ProfileRuntimeDescriptor, ProfileRuntimeError
from .runtime_bundle import (
    RuntimeBundleError,
    RuntimeComponent,
    RuntimeComponentRole,
)


_REQUIRED_SERVICE_CAPABILITIES = {
    "policy_provider": ("validation_policy", "evidence_policy"),
    "context_assembler": ("assemble",),
    "materializer": ("invalidate_for_sources", "recompute"),
}


class ProfileRuntimeProvider(Protocol):
    """A deliberately registered constructor for one executable profile."""

    package_name: str
    profile_ref: str
    source_component_role: RuntimeComponentRole
    source_component_logical_ref: str

    def build_services(
        self,
        store,
        descriptor: ProfileRuntimeDescriptor,
    ) -> "ProfileRuntimeServices": ...


@dataclass(frozen=True)
class ProfileRuntimeProviderRegistration:
    """Import-free registration for one reviewed executable provider source."""

    package_name: str
    profile_ref: str
    source_component_role: RuntimeComponentRole
    source_component_logical_ref: str
    module_name: str
    provider_attribute: str
    source_path: Path


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

    registrations: tuple[ProfileRuntimeProviderRegistration, ...]

    def __post_init__(self) -> None:
        if any(
            not isinstance(registration, ProfileRuntimeProviderRegistration)
            for registration in self.registrations
        ):
            raise ProfileRuntimeError(
                "profile runtime provider registry contains an invalid registration"
            )
        names = [
            registration.package_name for registration in self.registrations
        ]
        if any(not isinstance(name, str) or not name for name in names):
            raise ProfileRuntimeError(
                "profile runtime provider package names must be non-empty strings"
            )
        if len(names) != len(set(names)):
            raise ProfileRuntimeError(
                "profile runtime provider registry contains duplicate package names"
            )
        profile_refs = [
            registration.profile_ref for registration in self.registrations
        ]
        if any(
            not isinstance(profile_ref, str) or not profile_ref
            for profile_ref in profile_refs
        ):
            raise ProfileRuntimeError(
                "profile runtime provider profile refs must be non-empty strings"
            )
        if len(profile_refs) != len(set(profile_refs)):
            raise ProfileRuntimeError(
                "profile runtime provider registry contains duplicate profile refs"
            )
        source_components = []
        for registration in self.registrations:
            if (
                type(registration.source_component_role)
                is not RuntimeComponentRole
                or registration.source_component_role
                is not RuntimeComponentRole.ADAPTER_SOURCE
            ):
                raise ProfileRuntimeError(
                    "profile runtime provider source component role must be "
                    "ADAPTER_SOURCE"
                )
            logical_ref = registration.source_component_logical_ref
            if not isinstance(logical_ref, str) or not logical_ref:
                raise ProfileRuntimeError(
                    "profile runtime provider source component logical ref must "
                    "be a non-empty string"
                )
            source_components.append(
                (registration.source_component_role, logical_ref)
            )
            if (
                not isinstance(registration.module_name, str)
                or not registration.module_name
                or not isinstance(registration.provider_attribute, str)
                or not registration.provider_attribute
                or not isinstance(registration.source_path, Path)
                or not registration.source_path.is_absolute()
            ):
                raise ProfileRuntimeError(
                    "profile runtime provider import registration is invalid"
                )
        if len(source_components) != len(set(source_components)):
            raise ProfileRuntimeError(
                "profile runtime provider registry contains duplicate source "
                "components"
            )

    @property
    def registered_package_names(self) -> tuple[str, ...]:
        return tuple(
            registration.package_name for registration in self.registrations
        )

    def registration_for(
        self,
        package_name: str,
        descriptor: ProfileRuntimeDescriptor,
    ) -> ProfileRuntimeProviderRegistration:
        if not isinstance(package_name, str) or not package_name:
            raise ProfileRuntimeError(
                "profile runtime provider package name must be a non-empty string"
            )
        registration = next(
            (
                candidate
                for candidate in self.registrations
                if candidate.package_name == package_name
            ),
            None,
        )
        if registration is None:
            raise ProfileRuntimeError(
                "no registered executable runtime provider for profile package "
                f"{package_name!r}"
            )
        if registration.profile_ref != descriptor.profile_ref:
            raise ProfileRuntimeError(
                f"registered runtime provider for {package_name!r} does not support "
                f"descriptor profileRef {descriptor.profile_ref!r}"
            )
        return registration

    def build_services(
        self,
        store,
        package_name: str,
        descriptor: ProfileRuntimeDescriptor,
    ) -> ProfileRuntimeServices:
        registration = self.registration_for(package_name, descriptor)
        source_component = self._verify_provider_source(store, registration)
        provider = self._load_provider(store, registration, source_component)
        services = provider.build_services(store, descriptor)
        if not isinstance(services, ProfileRuntimeServices):
            raise ProfileRuntimeError(
                "profile runtime provider returned an invalid service bundle"
            )
        if services.provider is not provider or services.descriptor != descriptor:
            raise ProfileRuntimeError(
                "profile runtime provider returned services for a different provider "
                "or descriptor"
            )
        for service_name, capabilities in _REQUIRED_SERVICE_CAPABILITIES.items():
            service = _service_attribute(services, "service bundle", service_name)
            if service is None:
                raise ProfileRuntimeError(
                    "profile runtime provider omitted required service "
                    f"{service_name!r}"
                )
            missing = [
                capability
                for capability in capabilities
                if not callable(
                    _service_attribute(service, service_name, capability)
                )
            ]
            if missing:
                raise ProfileRuntimeError(
                    f"profile runtime provider service {service_name!r} lacks "
                    f"required callable capabilities {missing!r}"
                )
        self._validate_policy_contract(services, descriptor)
        if provider.package_name == "profile_si_ffs":
            self._validate_si_contract(services)
        return services

    @staticmethod
    def _verify_provider_source(
        store,
        registration: ProfileRuntimeProviderRegistration,
    ) -> RuntimeComponent:
        try:
            store.require_startup_complete("profile runtime provider composition")
            component = store.runtime_bundle.component(
                registration.source_component_role,
                registration.source_component_logical_ref,
            )
        except (AttributeError, RuntimeBundleError) as exc:
            raise ProfileRuntimeError(
                "profile runtime provider source is not retained as its exact "
                "startup-verified RuntimeBundle component"
            ) from exc

        try:
            registered_source_path = registration.source_path.resolve(
                strict=True
            )
            module_spec = importlib.util.find_spec(registration.module_name)
            module_origin = module_spec.origin if module_spec is not None else None
            if not module_origin:
                raise ProfileRuntimeError(
                    "profile runtime provider module source is unavailable"
                )
            resolved_module_path = Path(module_origin).resolve(strict=True)
            source_bytes = registered_source_path.read_bytes()
        except (ImportError, OSError) as exc:
            raise ProfileRuntimeError(
                "profile runtime provider source file is unavailable"
            ) from exc
        if resolved_module_path != registered_source_path:
            raise ProfileRuntimeError(
                "profile runtime provider module does not resolve to its "
                "registered source path"
            )
        if component.canonical_bytes != source_bytes:
            raise ProfileRuntimeError(
                "profile runtime provider source bytes do not match the exact "
                "startup-verified RuntimeBundle component"
            )
        return component

    @staticmethod
    def _load_provider(
        store,
        registration: ProfileRuntimeProviderRegistration,
        source_component: RuntimeComponent,
    ) -> ProfileRuntimeProvider:
        cache_key = (
            registration.package_name,
            registration.profile_ref,
            registration.source_component_role,
            registration.source_component_logical_ref,
            source_component.content_digest,
        )
        cached_provider = store._cached_profile_runtime_provider(cache_key)
        if cached_provider is not None:
            return cached_provider

        sealed_module = ModuleType("_ofarm_sealed_profile_runtime_provider")
        sealed_module_name = (
            f"{registration.module_name}.__ofarm_sealed_"
            f"{source_component.content_digest}_{id(sealed_module):x}"
        )
        sealed_module.__name__ = sealed_module_name
        sealed_module.__file__ = str(registration.source_path)
        sealed_module.__package__ = registration.module_name.rpartition(".")[0]
        if sealed_module_name in sys.modules:
            raise ProfileRuntimeError(
                "sealed profile runtime provider module identity collision"
            )
        try:
            code = compile(
                source_component.canonical_bytes,
                str(registration.source_path),
                "exec",
                dont_inherit=True,
            )
            sys.modules[sealed_module_name] = sealed_module
            exec(code, sealed_module.__dict__)
            provider = getattr(sealed_module, registration.provider_attribute)
        except Exception as exc:
            raise ProfileRuntimeError(
                "verified profile runtime provider module could not be loaded"
            ) from exc
        finally:
            sys.modules.pop(sealed_module_name, None)
        expected_attributes = {
            "package_name": registration.package_name,
            "profile_ref": registration.profile_ref,
            "source_component_role": registration.source_component_role,
            "source_component_logical_ref": (
                registration.source_component_logical_ref
            ),
        }
        build_services = _service_attribute(
            provider,
            "provider",
            "build_services",
        )
        if any(
            _service_attribute(
                provider,
                "provider",
                attribute,
            ) != expected
            for attribute, expected in expected_attributes.items()
        ) or not callable(build_services):
            raise ProfileRuntimeError(
                "verified profile runtime provider does not match its registration"
            )
        return store._retain_profile_runtime_provider(cache_key, provider)

    @staticmethod
    def _validate_policy_contract(
        services: ProfileRuntimeServices,
        descriptor: ProfileRuntimeDescriptor,
    ) -> None:
        policy_provider = services.policy_provider
        policy_ref = _service_attribute(
            policy_provider,
            "policy_provider",
            "policy_ref",
        )
        if policy_ref != descriptor.evidence_policy_ref:
            raise ProfileRuntimeError(
                "profile runtime provider policy_ref does not match the "
                "descriptor evidencePolicyRef"
            )
        recognized_rule_refs = _service_attribute(
            policy_provider,
            "policy_provider",
            "recognized_rule_refs",
        )
        required_rule_refs = frozenset({
            descriptor.evidence_policy_ref,
            descriptor.profile_ref,
            descriptor.pack_ref,
            descriptor.code_binding_profile_ref,
        })
        if (
            type(recognized_rule_refs) is not frozenset
            or not recognized_rule_refs
            or any(
                not isinstance(ref, str) or not ref
                for ref in recognized_rule_refs
            )
            or not required_rule_refs.issubset(recognized_rule_refs)
        ):
            raise ProfileRuntimeError(
                "profile runtime provider policy_provider has invalid "
                "recognized_rule_refs"
            )

    @staticmethod
    def _validate_si_contract(services: ProfileRuntimeServices) -> None:
        reference_bindings = services.reference_bindings
        if reference_bindings is None:
            raise ProfileRuntimeError(
                "SI profile runtime provider omitted required reference_bindings"
            )
        regsr_snapshot_prefix = _service_attribute(
            reference_bindings,
            "reference_bindings",
            "regsr_snapshot_prefix",
        )
        if not isinstance(regsr_snapshot_prefix, str) or not regsr_snapshot_prefix:
            raise ProfileRuntimeError(
                "SI profile runtime provider reference_bindings has an invalid "
                "regsr_snapshot_prefix"
            )
        product_lookup = services.product_lookup
        if product_lookup is None or not callable(
            _service_attribute(
                product_lookup,
                "product_lookup",
                "lookup_by_decision",
            )
        ):
            raise ProfileRuntimeError(
                "SI profile runtime provider product_lookup lacks required "
                "callable capability 'lookup_by_decision'"
            )


_DEFAULT_PROVIDER_REGISTRATIONS = (
    ProfileRuntimeProviderRegistration(
        package_name="profile_si_ffs",
        profile_ref="profile:si.ffs.recordkeeping.v0_1",
        source_component_role=RuntimeComponentRole.ADAPTER_SOURCE,
        source_component_logical_ref=(
            "python:profile-si-ffs-v0_1:runtime-provider"
        ),
        module_name="kernel.profiles.si_ffs.runtime_provider",
        provider_attribute="SI_RUNTIME_PROVIDER",
        source_path=(
            Path(__file__).resolve().parent
            / "profiles"
            / "si_ffs"
            / "runtime_provider.py"
        ),
    ),
)


def default_profile_runtime_provider_registry() -> ProfileRuntimeProviderRegistry:
    """Return import-free code-owned registrations; RS1 registers SI only."""
    return ProfileRuntimeProviderRegistry(_DEFAULT_PROVIDER_REGISTRATIONS)


def _service_attribute(service: Any, service_name: str, attribute: str) -> Any:
    try:
        return getattr(service, attribute)
    except Exception as exc:
        raise ProfileRuntimeError(
            f"profile runtime provider {service_name} does not expose "
            f"{attribute!r}"
        ) from exc
