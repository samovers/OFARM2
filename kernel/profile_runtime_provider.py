"""Explicit, code-owned profile runtime provider selection.

Descriptors describe package content. They never import executable code or make
that code available merely by existing on disk. This module is the trusted
composition seam that maps a deliberately registered package to the services
the current runtime already needs.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from inspect import getattr_static
from importlib.machinery import PathFinder
from pathlib import Path
from types import FunctionType, ModuleType
from typing import Any, Protocol

from . import context as _trusted_context
from . import materializer as _trusted_materializer_module
from . import profile_policy as _trusted_profile_policy
from . import validators as _trusted_validators
from .context import (
    ContextAssembler as _TrustedContextAssembler,
    SIProductRegister as _TrustedSIProductRegister,
    SIReferenceBindings as _TrustedSIReferenceBindings,
)
from .contracts import canonical_json, sha256_of
from .materializer import Materializer as _TrustedMaterializer
from .profile_policy import (
    DescriptorPolicyProvider as _TrustedDescriptorPolicyProvider,
)
from .profile_runtime import ProfileRuntimeDescriptor, ProfileRuntimeError
from .runtime_bundle import (
    RuntimeBundleError,
    RuntimeComponent,
    RuntimeComponentRole,
)
from .sufficiency import OPERATION_FLOOR_CHECKS as _TRUSTED_OPERATION_FLOOR_CHECKS
from .validators import (
    RegistryReverificationValidator as _TrustedRegistryReverificationValidator,
)


_REQUIRED_SERVICE_CAPABILITIES = {
    "policy_provider": ("validation_policy", "evidence_policy"),
    "context_assembler": ("assemble",),
    "materializer": ("invalidate_for_sources", "recompute"),
}
_OPTIONAL_SERVICE_CAPABILITIES = {
    "product_lookup": ("lookup_by_decision",),
    "registry_reverification": ("run",),
    "materializer_context": ("assemble",),
}
_MISSING_CAPABILITY = object()
_CONCRETE_PATH_TYPE = type(Path())


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
    registry_reverification: Any = None


@dataclass(frozen=True)
class _ProviderDependencyReceipt:
    """Exact code-owned constructor and capability provenance."""

    dependency_path: tuple[str, ...]
    dependency: Any
    capabilities: tuple[tuple[str, Any], ...]


@dataclass(frozen=True)
class _RuntimeBehaviorBindingReceipt:
    """Exact class/module/global binding used by authenticated behavior."""

    binding_path: str
    owner: Any
    attribute: str
    dependency: Any
    owner_is_globals: bool = False


@dataclass(frozen=True)
class _RuntimeFunctionReceipt:
    """Mutable Python-function internals retained as executable provenance."""

    function_path: str
    function: FunctionType
    code: Any
    defaults: Any
    kwdefaults: Any


def _dependency_spec(
    dependency_path: tuple[str, ...],
    dependency: Any,
    capabilities: tuple[str, ...] = (),
) -> tuple[
    tuple[str, ...],
    Any,
    tuple[tuple[str, Any], ...],
]:
    return (
        dependency_path,
        dependency,
        tuple(
            (capability, getattr_static(dependency, capability))
            for capability in capabilities
        ),
    )


# These exact identities are captured when the trusted composition module is
# imported, before any provider source is executed. The sealed SI provider
# receives these objects directly in its isolated namespace; it performs no
# live imports and cannot redefine which constructors or methods are trusted.
_SI_PROVIDER_DEPENDENCY_SPECS = (
    _dependency_spec(
        ("DescriptorPolicyProvider",),
        _TrustedDescriptorPolicyProvider,
        (
            "__new__",
            "__init__",
            "from_runtime_bundle",
            "validation_policy",
            "evidence_policy",
        ),
    ),
    _dependency_spec(
        ("ContextAssembler",),
        _TrustedContextAssembler,
        ("__new__", "__init__", "assemble"),
    ),
    _dependency_spec(
        ("SIProductRegister",),
        _TrustedSIProductRegister,
        (
            "__new__",
            "__init__",
            "load_from_store",
            "register_artifact",
            "identities_by_decision",
            "lookup_by_decision",
        ),
    ),
    _dependency_spec(
        ("SIReferenceBindings",),
        _TrustedSIReferenceBindings,
        (
            "__new__",
            "__init__",
            "from_runtime_descriptor",
            "_from_descriptor",
        ),
    ),
    _dependency_spec(
        ("Materializer",),
        _TrustedMaterializer,
        ("__new__", "__init__", "invalidate_for_sources", "recompute"),
    ),
    _dependency_spec(
        ("RegistryReverificationValidator",),
        _TrustedRegistryReverificationValidator,
        ("__new__", "__init__", "run"),
    ),
    _dependency_spec(
        ("ProfileRuntimeServices",),
        ProfileRuntimeServices,
        ("__new__", "__init__"),
    ),
    _dependency_spec(
        ("ProfileRuntimeDescriptor",),
        ProfileRuntimeDescriptor,
    ),
    _dependency_spec(("ProfileRuntimeError",), ProfileRuntimeError),
    _dependency_spec(("RuntimeBundleError",), RuntimeBundleError),
    _dependency_spec(
        ("PROVIDER_SOURCE_COMPONENT_ROLE",),
        RuntimeComponentRole.ADAPTER_SOURCE,
    ),
    _dependency_spec(
        ("PROFILE_POLICY_COMPONENT_ROLE",),
        RuntimeComponentRole.PROFILE_POLICY,
    ),
    _dependency_spec(
        ("OPERATION_FLOOR_CHECKS",),
        _TRUSTED_OPERATION_FLOOR_CHECKS,
    ),
)


_SI_TRUSTED_SERVICE_TYPES = {
    "policy_provider": _TrustedDescriptorPolicyProvider,
    "context_assembler": _TrustedContextAssembler,
    "materializer": _TrustedMaterializer,
    "reference_bindings": _TrustedSIReferenceBindings,
    "product_lookup": _TrustedSIProductRegister,
    "registry_reverification": _TrustedRegistryReverificationValidator,
    "materializer_context": _TrustedContextAssembler,
}
_SI_TRUSTED_IMPLEMENTATION_MODULES = (
    _trusted_context,
    _trusted_materializer_module,
    _trusted_profile_policy,
    _trusted_validators,
)


def _descriptor_functions(value: Any) -> tuple[FunctionType, ...]:
    if type(value) is FunctionType:
        return (value,)
    if type(value) in {classmethod, staticmethod}:
        function = value.__func__
        return (function,) if type(function) is FunctionType else ()
    if type(value) is property:
        return tuple(
            function
            for function in (value.fget, value.fset, value.fdel)
            if type(function) is FunctionType
        )
    return ()


def _build_runtime_behavior_specs() -> tuple[
    _RuntimeBehaviorBindingReceipt | _RuntimeFunctionReceipt,
    ...,
]:
    """Close over mutable Python behavior reachable from SI service roots."""
    receipts: list[
        _RuntimeBehaviorBindingReceipt | _RuntimeFunctionReceipt
    ] = []
    seen_bindings: set[tuple[int, str, bool]] = set()
    seen_functions: set[int] = set()
    pending_functions: list[tuple[str, FunctionType]] = []

    def add_binding(
        binding_path: str,
        owner: Any,
        attribute: str,
        dependency: Any,
        *,
        owner_is_globals: bool = False,
    ) -> None:
        key = (id(owner), attribute, owner_is_globals)
        if key in seen_bindings:
            return
        seen_bindings.add(key)
        receipts.append(_RuntimeBehaviorBindingReceipt(
            binding_path=binding_path,
            owner=owner,
            attribute=attribute,
            dependency=dependency,
            owner_is_globals=owner_is_globals,
        ))

    def add_function(function_path: str, function: FunctionType) -> None:
        if id(function) in seen_functions:
            return
        seen_functions.add(id(function))
        receipts.append(_RuntimeFunctionReceipt(
            function_path=function_path,
            function=function,
            code=function.__code__,
            defaults=function.__defaults__,
            kwdefaults=function.__kwdefaults__,
        ))
        pending_functions.append((function_path, function))

    for trusted_module in _SI_TRUSTED_IMPLEMENTATION_MODULES:
        add_binding(
            trusted_module.__name__,
            sys.modules,
            trusted_module.__name__,
            trusted_module,
            owner_is_globals=True,
        )

    trusted_types = tuple(dict.fromkeys((
        *_SI_TRUSTED_SERVICE_TYPES.values(),
        ProfileRuntimeServices,
    )))
    for trusted_type in trusted_types:
        type_path = f"{trusted_type.__module__}.{trusted_type.__qualname__}"
        defining_module = sys.modules[trusted_type.__module__]
        add_binding(
            type_path,
            defining_module,
            trusted_type.__name__,
            trusted_type,
        )
        for attribute in ("__new__", "__init__"):
            dependency = getattr_static(
                trusted_type,
                attribute,
                _MISSING_CAPABILITY,
            )
            add_binding(
                f"{type_path}.{attribute}",
                trusted_type,
                attribute,
                dependency,
            )
            for function in _descriptor_functions(dependency):
                add_function(f"{type_path}.{attribute}", function)
        for attribute, dependency in sorted(trusted_type.__dict__.items()):
            functions = _descriptor_functions(dependency)
            if not functions:
                continue
            add_binding(
                f"{type_path}.{attribute}",
                trusted_type,
                attribute,
                dependency,
            )
            for function in functions:
                add_function(f"{type_path}.{attribute}", function)

    while pending_functions:
        function_path, function = pending_functions.pop()
        names = set(function.__code__.co_names)
        namespace = function.__globals__
        for name in sorted(names):
            dependency = namespace.get(name, _MISSING_CAPABILITY)
            dependency_module = getattr(dependency, "__module__", "")
            if (
                dependency is not _MISSING_CAPABILITY
                and callable(dependency)
                and isinstance(dependency_module, str)
                and dependency_module.startswith("kernel.")
            ):
                add_binding(
                    f"{function_path}.__globals__.{name}",
                    namespace,
                    name,
                    dependency,
                    owner_is_globals=True,
                )
                if type(dependency) is FunctionType:
                    add_function(
                        f"{dependency.__module__}.{dependency.__qualname__}",
                        dependency,
                    )
            if (
                type(dependency) is ModuleType
                and dependency.__name__.startswith("kernel.")
            ):
                for module_attribute in sorted(names):
                    module_dependency = getattr_static(
                        dependency,
                        module_attribute,
                        _MISSING_CAPABILITY,
                    )
                    module_dependency_name = getattr(
                        module_dependency,
                        "__module__",
                        "",
                    )
                    if (
                        module_dependency is _MISSING_CAPABILITY
                        or not callable(module_dependency)
                        or not isinstance(module_dependency_name, str)
                        or not module_dependency_name.startswith("kernel.")
                    ):
                        continue
                    add_binding(
                        f"{dependency.__name__}.{module_attribute}",
                        dependency,
                        module_attribute,
                        module_dependency,
                    )
                    if type(module_dependency) is FunctionType:
                        add_function(
                            f"{module_dependency.__module__}."
                            f"{module_dependency.__qualname__}",
                            module_dependency,
                        )

    return tuple(receipts)


_SI_RUNTIME_BEHAVIOR_SPECS = _build_runtime_behavior_specs()


@dataclass(frozen=True)
class _ProfileRuntimeProviderCacheEntry:
    """Authenticated composition receipt; never a live mutable service graph."""

    registration_identity: tuple[str, ...]
    source_digest: str
    descriptor: ProfileRuntimeDescriptor
    provider_dependencies: tuple[_ProviderDependencyReceipt, ...]
    runtime_behavior: tuple[
        _RuntimeBehaviorBindingReceipt | _RuntimeFunctionReceipt,
        ...,
    ]
    service_capabilities: tuple["_ServiceCapabilityReceipt", ...]
    service_state_digest: str


@dataclass(frozen=True)
class _ServiceCapabilityReceipt:
    """Captured class capabilities checked before a later composition."""

    service_name: str
    service_type: type
    capabilities: tuple[tuple[str, Any], ...]


@dataclass(frozen=True)
class ProfileRuntimeProviderRegistry:
    """Immutable executable-provider registrations owned by trusted code."""

    registrations: tuple[ProfileRuntimeProviderRegistration, ...]

    def __post_init__(self) -> None:
        if type(self.registrations) is not tuple:
            raise ProfileRuntimeError(
                "profile runtime provider registrations must use an exact tuple"
            )
        if any(
            type(registration) is not ProfileRuntimeProviderRegistration
            for registration in self.registrations
        ):
            raise ProfileRuntimeError(
                "profile runtime provider registry contains an invalid registration"
            )
        names = [
            registration.package_name for registration in self.registrations
        ]
        if any(type(name) is not str or not name for name in names):
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
            type(profile_ref) is not str or not profile_ref
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
            if type(logical_ref) is not str or not logical_ref:
                raise ProfileRuntimeError(
                    "profile runtime provider source component logical ref must "
                    "be a non-empty string"
                )
            source_components.append(
                (registration.source_component_role, logical_ref)
            )
            if (
                type(registration.module_name) is not str
                or not registration.module_name
                or type(registration.provider_attribute) is not str
                or not registration.provider_attribute
                or type(registration.source_path) is not _CONCRETE_PATH_TYPE
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
        if type(package_name) is not str or not package_name:
            raise ProfileRuntimeError(
                "profile runtime provider package name must be a non-empty string"
            )
        if type(descriptor) is not ProfileRuntimeDescriptor:
            raise ProfileRuntimeError(
                "profile runtime provider descriptor must use the exact trusted type"
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
        services, _ = self.build_services_with_receipt(
            store,
            package_name,
            descriptor,
        )
        return services

    def build_services_with_receipt(
        self,
        store,
        package_name: str,
        descriptor: ProfileRuntimeDescriptor,
    ) -> tuple[ProfileRuntimeServices, _ProfileRuntimeProviderCacheEntry]:
        registration = self.registration_for(package_name, descriptor)
        source_component = self._verify_provider_source(store, registration)
        cache_key = self._provider_cache_key(registration, source_component)
        cached_entry = store._cached_profile_runtime_provider(cache_key)
        if cached_entry is not None:
            self._validate_cached_composition_receipt(
                cached_entry,
                registration,
                source_component,
                descriptor,
            )

        provider = self._load_provider(store, registration, source_component)
        provider_dependencies = _capture_provider_dependencies(
            provider,
            registration,
        )
        runtime_behavior = _capture_runtime_behavior_dependencies(
            registration,
        )
        services = provider.build_services(store, descriptor)
        self._validate_service_bundle_identity(provider, services, descriptor)
        self._validate_services(provider, services, descriptor)
        service_capabilities = _capture_service_capabilities(services)
        service_state_digest = _capture_service_state_digest(
            services,
            store,
            descriptor,
        )
        cache_entry = _ProfileRuntimeProviderCacheEntry(
            registration_identity=_registration_identity(registration),
            source_digest=source_component.content_digest,
            descriptor=descriptor,
            provider_dependencies=provider_dependencies,
            runtime_behavior=runtime_behavior,
            service_capabilities=service_capabilities,
            service_state_digest=service_state_digest,
        )
        retained_entry = store._retain_profile_runtime_provider(
            cache_key,
            cache_entry,
        )
        self._validate_cached_composition_receipt(
            retained_entry,
            registration,
            source_component,
            descriptor,
        )
        if (
            not _same_provider_dependencies(
                retained_entry.provider_dependencies,
                cache_entry.provider_dependencies,
            )
            or not _same_runtime_behavior_dependencies(
                retained_entry.runtime_behavior,
                cache_entry.runtime_behavior,
            )
            or not _same_service_capabilities(
                retained_entry.service_capabilities,
                cache_entry.service_capabilities,
            )
            or retained_entry.service_state_digest
            != cache_entry.service_state_digest
        ):
            raise ProfileRuntimeError(
                "profile runtime provider dependency, capability, or state "
                "provenance changed during composition"
            )
        # Every caller receives a newly composed graph. The Store cache is only
        # an authentication receipt and never becomes executable authority.
        return services, retained_entry

    def validate_services_for_execution(
        self,
        store,
        package_name: str,
        descriptor: ProfileRuntimeDescriptor,
        services: ProfileRuntimeServices,
        expected_receipt: _ProfileRuntimeProviderCacheEntry,
    ) -> None:
        """Re-authenticate one long-lived pipeline before every governed use."""
        registration = self.registration_for(package_name, descriptor)
        source_component = self._verify_provider_source(store, registration)
        cache_key = self._provider_cache_key(registration, source_component)
        retained_entry = store._cached_profile_runtime_provider(cache_key)
        if retained_entry is not expected_receipt:
            raise ProfileRuntimeError(
                "profile runtime provider execution receipt is no longer retained"
            )
        self._validate_cached_composition_receipt(
            expected_receipt,
            registration,
            source_component,
            descriptor,
        )
        self._validate_provider_registration(services.provider, registration)
        self._validate_service_bundle_identity(
            services.provider,
            services,
            descriptor,
        )
        current_capabilities = _capture_service_capabilities(services)
        if not _same_service_capabilities(
            expected_receipt.service_capabilities,
            current_capabilities,
        ):
            raise ProfileRuntimeError(
                "profile runtime provider service capabilities changed after "
                "composition"
            )
        current_state_digest = _capture_service_state_digest(
            services,
            store,
            descriptor,
        )
        if current_state_digest != expected_receipt.service_state_digest:
            raise ProfileRuntimeError(
                "profile runtime provider service state changed after composition"
            )
        self._validate_services(services.provider, services, descriptor)

    @staticmethod
    def _validate_service_bundle_identity(
        provider: ProfileRuntimeProvider,
        services: Any,
        descriptor: ProfileRuntimeDescriptor,
    ) -> None:
        if type(services) is not ProfileRuntimeServices:
            raise ProfileRuntimeError(
                "profile runtime provider returned an invalid service bundle"
            )
        if services.provider is not provider or services.descriptor is not descriptor:
            raise ProfileRuntimeError(
                "profile runtime provider returned services for a different provider "
                "or descriptor"
            )

    @classmethod
    def _validate_services(
        cls,
        provider: ProfileRuntimeProvider,
        services: Any,
        descriptor: ProfileRuntimeDescriptor,
    ) -> None:
        cls._validate_service_bundle_identity(provider, services, descriptor)
        if provider.package_name == "profile_si_ffs":
            cls._validate_si_service_types(services)
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
        cls._validate_policy_contract(services, descriptor)
        registry_reverification = _service_attribute(
            services,
            "service bundle",
            "registry_reverification",
        )
        if registry_reverification is not None and not callable(
            _service_attribute(
                registry_reverification,
                "registry_reverification",
                "run",
            )
        ):
            raise ProfileRuntimeError(
                "profile runtime provider registry_reverification lacks "
                "required callable capability 'run'"
            )
        if provider.package_name == "profile_si_ffs":
            cls._validate_si_contract(services)

    @staticmethod
    def _validate_cached_composition_receipt(
        cached_entry: Any,
        registration: ProfileRuntimeProviderRegistration,
        source_component: RuntimeComponent,
        descriptor: ProfileRuntimeDescriptor,
    ) -> None:
        if (
            type(cached_entry) is not _ProfileRuntimeProviderCacheEntry
            or type(cached_entry.registration_identity) is not tuple
            or any(
                type(value) is not str
                for value in cached_entry.registration_identity
            )
            or cached_entry.registration_identity
            != _registration_identity(registration)
            or type(cached_entry.source_digest) is not str
            or cached_entry.source_digest != source_component.content_digest
            or type(cached_entry.descriptor) is not ProfileRuntimeDescriptor
            or type(descriptor) is not ProfileRuntimeDescriptor
            or cached_entry.descriptor != descriptor
            or type(cached_entry.provider_dependencies) is not tuple
            or type(cached_entry.runtime_behavior) is not tuple
            or type(cached_entry.service_capabilities) is not tuple
            or type(cached_entry.service_state_digest) is not str
            or not cached_entry.service_state_digest.startswith("sha256:")
        ):
            raise ProfileRuntimeError(
                "profile runtime provider cache receipt does not match its "
                "canonical registration and descriptor"
            )
        _validate_provider_dependency_receipts(
            cached_entry.provider_dependencies,
            registration,
        )
        _validate_runtime_behavior_dependency_receipts(
            cached_entry.runtime_behavior,
            registration,
        )
        seen_service_names = set()
        for service_receipt in cached_entry.service_capabilities:
            if (
                type(service_receipt) is not _ServiceCapabilityReceipt
                or type(service_receipt.service_name) is not str
                or type(service_receipt.service_type) is not type
                or type(service_receipt.capabilities) is not tuple
            ):
                raise ProfileRuntimeError(
                    "profile runtime provider cache receipt has malformed "
                    "service capability provenance"
                )
            capability_contract = (
                _REQUIRED_SERVICE_CAPABILITIES
                | _OPTIONAL_SERVICE_CAPABILITIES
            )
            expected_capabilities = capability_contract.get(
                service_receipt.service_name
            )
            if (
                expected_capabilities is None
                or service_receipt.service_name in seen_service_names
                or tuple(
                    capability[0]
                    for capability in service_receipt.capabilities
                    if type(capability) is tuple and len(capability) == 2
                )
                != ("__new__", "__init__", *expected_capabilities)
            ):
                raise ProfileRuntimeError(
                    "profile runtime provider cache receipt has incomplete "
                    "service capability provenance"
                )
            seen_service_names.add(service_receipt.service_name)
            for capability_receipt in service_receipt.capabilities:
                if (
                    type(capability_receipt) is not tuple
                    or len(capability_receipt) != 2
                ):
                    raise ProfileRuntimeError(
                        "profile runtime provider cache receipt has malformed "
                        "service capability provenance"
                    )
                capability_name, expected = capability_receipt
                if (
                    type(capability_name) is not str
                    or expected is _MISSING_CAPABILITY
                    or getattr_static(
                        service_receipt.service_type,
                        capability_name,
                        _MISSING_CAPABILITY,
                    )
                    is not expected
                ):
                    raise ProfileRuntimeError(
                        "profile runtime provider cached service capability "
                        f"{service_receipt.service_name}.{capability_name} changed"
                    )
        if not set(_REQUIRED_SERVICE_CAPABILITIES).issubset(
            seen_service_names
        ):
            raise ProfileRuntimeError(
                "profile runtime provider cache receipt has incomplete "
                "service capability provenance"
            )

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
            resolved_module_path = _resolve_module_source_without_import(
                registration.module_name
            )
            source_bytes = registered_source_path.read_bytes()
        except OSError as exc:
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
        _capture_runtime_behavior_dependencies(registration)
        sealed_module = ModuleType("_ofarm_sealed_profile_runtime_provider")
        sealed_module_name = (
            f"{registration.module_name}.__ofarm_sealed_"
            f"{source_component.content_digest}_{id(sealed_module):x}"
        )
        sealed_module.__name__ = sealed_module_name
        sealed_module.__file__ = str(registration.source_path)
        sealed_module.__package__ = registration.module_name.rpartition(".")[0]
        sealed_module.__dict__.update(
            _provider_execution_namespace(registration)
        )
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
        ProfileRuntimeProviderRegistry._validate_provider_registration(
            provider,
            registration,
        )
        return provider

    @staticmethod
    def _provider_cache_key(
        registration: ProfileRuntimeProviderRegistration,
        source_component: RuntimeComponent,
    ) -> tuple[str, ...]:
        return (
            *_registration_identity(registration),
            source_component.content_digest,
        )

    @staticmethod
    def _validate_provider_registration(
        provider: ProfileRuntimeProvider,
        registration: ProfileRuntimeProviderRegistration,
    ) -> None:
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
    def _validate_si_service_types(
        services: ProfileRuntimeServices,
    ) -> None:
        exact_services = {
            "policy_provider": services.policy_provider,
            "context_assembler": services.context_assembler,
            "materializer": services.materializer,
            "reference_bindings": services.reference_bindings,
            "product_lookup": services.product_lookup,
            "registry_reverification": services.registry_reverification,
        }
        for service_name, service in exact_services.items():
            expected_type = _SI_TRUSTED_SERVICE_TYPES[service_name]
            if type(service) is not expected_type:
                raise ProfileRuntimeError(
                    "SI profile runtime provider service "
                    f"{service_name!r} must use the exact trusted "
                    f"{expected_type.__name__} type"
                )
        materializer_context = _service_attribute(
            services.materializer,
            "materializer",
            "context",
        )
        expected_context_type = _SI_TRUSTED_SERVICE_TYPES[
            "materializer_context"
        ]
        if type(materializer_context) is not expected_context_type:
            raise ProfileRuntimeError(
                "SI profile runtime provider service 'materializer_context' "
                f"must use the exact trusted {expected_context_type.__name__} "
                "type"
            )

    @staticmethod
    def _validate_si_contract(services: ProfileRuntimeServices) -> None:
        reference_bindings = services.reference_bindings
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
        try:
            descriptor_regsr_snapshot_prefix = (
                services.descriptor.reference_family(
                    "si.uvhvvr.ffs-reg"
                ).snapshot_prefix
            )
        except ProfileRuntimeError as exc:
            raise ProfileRuntimeError(
                "SI profile runtime provider descriptor does not select the "
                "required REGSR reference family"
            ) from exc
        if regsr_snapshot_prefix != descriptor_regsr_snapshot_prefix:
            raise ProfileRuntimeError(
                "SI profile runtime provider regsr_snapshot_prefix does not "
                "match the descriptor REGSR reference family"
            )
        product_lookup = services.product_lookup
        if not callable(
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
        registry_reverification = services.registry_reverification
        if not callable(
            _service_attribute(
                registry_reverification,
                "registry_reverification",
                "run",
            )
        ):
            raise ProfileRuntimeError(
                "SI profile runtime provider omitted required "
                "registry_reverification capability"
            )
        if (
            _service_attribute(
                registry_reverification,
                "registry_reverification",
                "snapshot_prefix",
            ) != regsr_snapshot_prefix
            or _service_attribute(
                registry_reverification,
                "registry_reverification",
                "product_lookup",
            ) is not product_lookup
        ):
            raise ProfileRuntimeError(
                "SI profile runtime provider registry_reverification is not "
                "bound to its reference bindings and product lookup"
            )


def _registration_identity(
    registration: ProfileRuntimeProviderRegistration,
) -> tuple[str, ...]:
    """Canonical primitive identity for cache keys and cache receipts."""
    if type(registration) is not ProfileRuntimeProviderRegistration:
        raise ProfileRuntimeError(
            "profile runtime provider registration must use the exact trusted type"
        )
    scalar_fields = (
        registration.package_name,
        registration.profile_ref,
        registration.source_component_logical_ref,
        registration.module_name,
        registration.provider_attribute,
    )
    if any(type(value) is not str or not value for value in scalar_fields):
        raise ProfileRuntimeError(
            "profile runtime provider registration identity is invalid"
        )
    if (
        type(registration.source_component_role) is not RuntimeComponentRole
        or type(registration.source_path) is not _CONCRETE_PATH_TYPE
    ):
        raise ProfileRuntimeError(
            "profile runtime provider registration identity uses invalid scalar types"
        )
    try:
        normalized_source_path = str(
            registration.source_path.resolve(strict=True)
        )
    except OSError as exc:
        raise ProfileRuntimeError(
            "profile runtime provider registration source path is unavailable"
        ) from exc
    return (
        registration.package_name,
        registration.profile_ref,
        registration.source_component_role.value,
        registration.source_component_logical_ref,
        registration.module_name,
        registration.provider_attribute,
        normalized_source_path,
    )


def _provider_dependency_specs(
    registration: ProfileRuntimeProviderRegistration,
):
    if registration.package_name != "profile_si_ffs":
        raise ProfileRuntimeError(
            "profile runtime provider has no authenticated dependency table"
        )
    return _SI_PROVIDER_DEPENDENCY_SPECS


def _provider_execution_namespace(
    registration: ProfileRuntimeProviderRegistration,
) -> dict[str, Any]:
    _provider_dependency_specs(registration)
    return {
        "DescriptorPolicyProvider": _TrustedDescriptorPolicyProvider,
        "ContextAssembler": _TrustedContextAssembler,
        "SIProductRegister": _TrustedSIProductRegister,
        "SIReferenceBindings": _TrustedSIReferenceBindings,
        "Materializer": _TrustedMaterializer,
        "RegistryReverificationValidator": (
            _TrustedRegistryReverificationValidator
        ),
        "ProfileRuntimeServices": ProfileRuntimeServices,
        "ProfileRuntimeDescriptor": ProfileRuntimeDescriptor,
        "ProfileRuntimeError": ProfileRuntimeError,
        "RuntimeBundleError": RuntimeBundleError,
        "PROVIDER_SOURCE_COMPONENT_ROLE": RuntimeComponentRole.ADAPTER_SOURCE,
        "PROFILE_POLICY_COMPONENT_ROLE": RuntimeComponentRole.PROFILE_POLICY,
        "OPERATION_FLOOR_CHECKS": _TRUSTED_OPERATION_FLOOR_CHECKS,
    }


def _runtime_behavior_specs(
    registration: ProfileRuntimeProviderRegistration,
) -> tuple[
    _RuntimeBehaviorBindingReceipt | _RuntimeFunctionReceipt,
    ...,
]:
    _provider_dependency_specs(registration)
    return _SI_RUNTIME_BEHAVIOR_SPECS


def _current_behavior_binding(
    receipt: _RuntimeBehaviorBindingReceipt,
) -> Any:
    if receipt.owner_is_globals:
        if type(receipt.owner) is not dict:
            return _MISSING_CAPABILITY
        return receipt.owner.get(receipt.attribute, _MISSING_CAPABILITY)
    return getattr_static(
        receipt.owner,
        receipt.attribute,
        _MISSING_CAPABILITY,
    )


def _capture_runtime_behavior_dependencies(
    registration: ProfileRuntimeProviderRegistration,
) -> tuple[
    _RuntimeBehaviorBindingReceipt | _RuntimeFunctionReceipt,
    ...,
]:
    specs = _runtime_behavior_specs(registration)
    _validate_runtime_behavior_dependency_receipts(specs, registration)
    return specs


def _validate_runtime_behavior_dependency_receipts(
    receipts: tuple[
        _RuntimeBehaviorBindingReceipt | _RuntimeFunctionReceipt,
        ...,
    ],
    registration: ProfileRuntimeProviderRegistration,
) -> None:
    specs = _runtime_behavior_specs(registration)
    if len(receipts) != len(specs):
        raise ProfileRuntimeError(
            "profile runtime provider cache receipt has incomplete runtime "
            "behavior provenance"
        )
    for receipt, spec in zip(receipts, specs):
        if type(receipt) is not type(spec):
            raise ProfileRuntimeError(
                "profile runtime provider cache receipt has malformed runtime "
                "behavior provenance"
            )
        if type(spec) is _RuntimeBehaviorBindingReceipt:
            if (
                receipt.binding_path != spec.binding_path
                or receipt.owner is not spec.owner
                or receipt.attribute != spec.attribute
                or receipt.dependency is not spec.dependency
                or receipt.owner_is_globals is not spec.owner_is_globals
                or _current_behavior_binding(spec) is not spec.dependency
            ):
                raise ProfileRuntimeError(
                    "profile runtime provider runtime behavior dependency "
                    f"{spec.binding_path} changed"
                )
            continue
        if (
            receipt.function_path != spec.function_path
            or receipt.function is not spec.function
            or receipt.code is not spec.code
            or receipt.defaults is not spec.defaults
            or receipt.kwdefaults is not spec.kwdefaults
            or spec.function.__code__ is not spec.code
            or spec.function.__defaults__ is not spec.defaults
            or spec.function.__kwdefaults__ is not spec.kwdefaults
        ):
            raise ProfileRuntimeError(
                "profile runtime provider runtime behavior function "
                f"{spec.function_path} changed"
            )


def _same_runtime_behavior_dependencies(
    left: tuple[
        _RuntimeBehaviorBindingReceipt | _RuntimeFunctionReceipt,
        ...,
    ],
    right: tuple[
        _RuntimeBehaviorBindingReceipt | _RuntimeFunctionReceipt,
        ...,
    ],
) -> bool:
    if len(left) != len(right):
        return False
    for left_receipt, right_receipt in zip(left, right):
        if type(left_receipt) is not type(right_receipt):
            return False
        if type(left_receipt) is _RuntimeBehaviorBindingReceipt:
            if (
                left_receipt.binding_path != right_receipt.binding_path
                or left_receipt.owner is not right_receipt.owner
                or left_receipt.attribute != right_receipt.attribute
                or left_receipt.dependency is not right_receipt.dependency
                or left_receipt.owner_is_globals
                is not right_receipt.owner_is_globals
            ):
                return False
            continue
        if (
            left_receipt.function_path != right_receipt.function_path
            or left_receipt.function is not right_receipt.function
            or left_receipt.code is not right_receipt.code
            or left_receipt.defaults is not right_receipt.defaults
            or left_receipt.kwdefaults is not right_receipt.kwdefaults
        ):
            return False
    return True


def _resolve_dependency_path(
    namespace: dict[str, Any],
    dependency_path: tuple[str, ...],
) -> Any:
    current = namespace.get(dependency_path[0], _MISSING_CAPABILITY)
    for attribute in dependency_path[1:]:
        if current is _MISSING_CAPABILITY:
            break
        current = getattr_static(
            current,
            attribute,
            _MISSING_CAPABILITY,
        )
    return current


def _capture_provider_dependencies(
    provider: ProfileRuntimeProvider,
    registration: ProfileRuntimeProviderRegistration,
) -> tuple[_ProviderDependencyReceipt, ...]:
    provider_type = type(provider)
    build_services = getattr_static(
        provider_type,
        "build_services",
        _MISSING_CAPABILITY,
    )
    if (
        build_services is _MISSING_CAPABILITY
        or getattr_static(
            provider,
            "build_services",
            _MISSING_CAPABILITY,
        )
        is not build_services
        or type(getattr(build_services, "__globals__", None)) is not dict
    ):
        raise ProfileRuntimeError(
            "verified profile runtime provider build_services is not a sealed "
            "class-owned function"
        )
    namespace = build_services.__globals__
    receipts = []
    for dependency_path, expected_dependency, expected_capabilities in (
        _provider_dependency_specs(registration)
    ):
        dependency = _resolve_dependency_path(namespace, dependency_path)
        if dependency is not expected_dependency:
            raise ProfileRuntimeError(
                "verified profile runtime provider imported unauthenticated "
                f"dependency {'.'.join(dependency_path)!r}"
            )
        for capability_name, expected_capability in expected_capabilities:
            if getattr_static(
                dependency,
                capability_name,
                _MISSING_CAPABILITY,
            ) is not expected_capability:
                raise ProfileRuntimeError(
                    "verified profile runtime provider dependency capability "
                    f"{'.'.join(dependency_path)}.{capability_name} changed"
                )
        receipts.append(_ProviderDependencyReceipt(
            dependency_path=dependency_path,
            dependency=dependency,
            capabilities=expected_capabilities,
        ))
    return tuple(receipts)


def _validate_provider_dependency_receipts(
    receipts: tuple[_ProviderDependencyReceipt, ...],
    registration: ProfileRuntimeProviderRegistration,
) -> None:
    specs = _provider_dependency_specs(registration)
    if len(receipts) != len(specs):
        raise ProfileRuntimeError(
            "profile runtime provider cache receipt has incomplete dependency "
            "provenance"
        )
    for receipt, spec in zip(receipts, specs):
        dependency_path, expected_dependency, expected_capabilities = spec
        if (
            type(receipt) is not _ProviderDependencyReceipt
            or receipt.dependency_path != dependency_path
            or receipt.dependency is not expected_dependency
            or type(receipt.capabilities) is not tuple
            or len(receipt.capabilities) != len(expected_capabilities)
        ):
            raise ProfileRuntimeError(
                "profile runtime provider cache receipt has malformed dependency "
                "provenance"
            )
        for retained_capability, expected_capability in zip(
            receipt.capabilities,
            expected_capabilities,
        ):
            if (
                type(retained_capability) is not tuple
                or len(retained_capability) != 2
                or retained_capability[0] != expected_capability[0]
                or retained_capability[1] is not expected_capability[1]
                or getattr_static(
                    expected_dependency,
                    expected_capability[0],
                    _MISSING_CAPABILITY,
                )
                is not expected_capability[1]
            ):
                raise ProfileRuntimeError(
                    "profile runtime provider cached dependency capability "
                    f"{'.'.join(dependency_path)}."
                    f"{expected_capability[0]} changed"
                )


def _same_provider_dependencies(
    left: tuple[_ProviderDependencyReceipt, ...],
    right: tuple[_ProviderDependencyReceipt, ...],
) -> bool:
    if len(left) != len(right):
        return False
    for left_receipt, right_receipt in zip(left, right):
        if (
            type(left_receipt) is not _ProviderDependencyReceipt
            or type(right_receipt) is not _ProviderDependencyReceipt
            or left_receipt.dependency_path != right_receipt.dependency_path
            or left_receipt.dependency is not right_receipt.dependency
            or len(left_receipt.capabilities)
            != len(right_receipt.capabilities)
        ):
            return False
        for left_capability, right_capability in zip(
            left_receipt.capabilities,
            right_receipt.capabilities,
        ):
            if (
                left_capability[0] != right_capability[0]
                or left_capability[1] is not right_capability[1]
            ):
                return False
    return True


def _service_capability_targets(
    services: ProfileRuntimeServices,
) -> tuple[tuple[str, Any, tuple[str, ...]], ...]:
    targets = []
    for service_name, capabilities in _REQUIRED_SERVICE_CAPABILITIES.items():
        targets.append((
            service_name,
            _service_attribute(services, "service bundle", service_name),
            capabilities,
        ))
    for service_name, capabilities in _OPTIONAL_SERVICE_CAPABILITIES.items():
        if service_name == "materializer_context":
            materializer = _service_attribute(
                services,
                "service bundle",
                "materializer",
            )
            service = getattr_static(
                materializer,
                "context",
                _MISSING_CAPABILITY,
            )
        else:
            service = _service_attribute(
                services,
                "service bundle",
                service_name,
            )
        if service is not None and service is not _MISSING_CAPABILITY:
            targets.append((service_name, service, capabilities))
    return tuple(targets)


def _capture_service_capabilities(
    services: ProfileRuntimeServices,
) -> tuple[_ServiceCapabilityReceipt, ...]:
    """Capture class-owned behavior without retaining any live service object."""
    if type(services) is not ProfileRuntimeServices:
        raise ProfileRuntimeError(
            "profile runtime provider returned an invalid service bundle"
        )
    receipts = []
    for service_name, service, capabilities in _service_capability_targets(services):
        service_type = type(service)
        captured = []
        for capability_name in ("__new__", "__init__", *capabilities):
            capability = getattr_static(
                service_type,
                capability_name,
                _MISSING_CAPABILITY,
            )
            if capability is _MISSING_CAPABILITY:
                raise ProfileRuntimeError(
                    "profile runtime provider service "
                    f"{service_name!r} capability {capability_name!r} is not "
                    "class-owned and cannot be authenticated across compositions"
                )
            if getattr_static(
                service,
                capability_name,
                _MISSING_CAPABILITY,
            ) is not capability:
                raise ProfileRuntimeError(
                    "profile runtime provider service "
                    f"{service_name!r} overrides authenticated class capability "
                    f"{capability_name!r} on its instance"
                )
            captured.append((capability_name, capability))
        receipts.append(_ServiceCapabilityReceipt(
            service_name=service_name,
            service_type=service_type,
            capabilities=tuple(captured),
        ))
    return tuple(receipts)


def _state_attribute(value: Any, name: str, owner: str) -> Any:
    attribute = getattr_static(value, name, _MISSING_CAPABILITY)
    if attribute is _MISSING_CAPABILITY:
        raise ProfileRuntimeError(
            f"profile runtime provider {owner} state lacks {name!r}"
        )
    return attribute


def _canonical_state_value(value: Any) -> Any:
    if value is None or type(value) in {bool, int, float, str}:
        return value
    if isinstance(value, Path):
        return {"path": str(value)}
    if isinstance(value, Enum):
        return {
            "enum": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": _canonical_state_value(value.value),
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "dataclass": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": {
                field.name: _canonical_state_value(getattr(value, field.name))
                for field in fields(value)
            },
        }
    if type(value) is dict:
        items = [
            (
                _canonical_state_value(key),
                _canonical_state_value(item),
            )
            for key, item in value.items()
        ]
        items.sort(key=lambda item: canonical_json({"key": item[0]}))
        return {"dict": items}
    if type(value) in {list, tuple}:
        return {
            type(value).__name__: [
                _canonical_state_value(item)
                for item in value
            ],
        }
    if type(value) in {set, frozenset}:
        items = [_canonical_state_value(item) for item in value]
        items.sort(key=lambda item: canonical_json({"item": item}))
        return {type(value).__name__: items}
    raise ProfileRuntimeError(
        "profile runtime provider service state contains an unsupported "
        f"value of type {type(value).__name__}"
    )


def _capture_service_state_digest(
    services: ProfileRuntimeServices,
    store,
    descriptor: ProfileRuntimeDescriptor,
) -> str:
    policy_provider = services.policy_provider
    context_assembler = services.context_assembler
    materializer = services.materializer
    materializer_context = _state_attribute(
        materializer,
        "context",
        "materializer",
    )
    reference_bindings = services.reference_bindings
    product_lookup = services.product_lookup
    registry_reverification = services.registry_reverification
    bindings = (
        _state_attribute(product_lookup, "bindings", "product_lookup")
        if product_lookup is not None else None
    )
    product_state = (
        _state_attribute(product_lookup, "_by_snapshot", "product_lookup")
        if product_lookup is not None else None
    )
    state_bindings = (
        services.descriptor is descriptor,
        _state_attribute(policy_provider, "descriptor", "policy_provider")
        is descriptor,
        _state_attribute(context_assembler, "store", "context_assembler")
        is store,
        _state_attribute(
            context_assembler,
            "active_profile",
            "context_assembler",
        )
        is descriptor,
        _state_attribute(
            context_assembler,
            "runtime_bundle",
            "context_assembler",
        )
        is store.runtime_bundle,
        _state_attribute(materializer, "store", "materializer") is store,
        _state_attribute(
            materializer,
            "active_profile",
            "materializer",
        )
        is descriptor,
        _state_attribute(
            materializer,
            "runtime_bundle",
            "materializer",
        )
        is store.runtime_bundle,
        _state_attribute(
            materializer_context,
            "store",
            "materializer.context",
        )
        is store,
        _state_attribute(
            materializer_context,
            "active_profile",
            "materializer.context",
        )
        is descriptor,
        _state_attribute(
            materializer_context,
            "runtime_bundle",
            "materializer.context",
        )
        is store.runtime_bundle,
        bindings == reference_bindings,
        (
            _state_attribute(
                registry_reverification,
                "product_lookup",
                "registry_reverification",
            )
            is product_lookup
            if registry_reverification is not None else True
        ),
    )
    if not all(state_bindings):
        raise ProfileRuntimeError(
            "profile runtime provider service state is not bound to its exact "
            "Store, descriptor, RuntimeBundle, and peer services"
        )
    payload = {
        "descriptor": _canonical_state_value(descriptor),
        "policyProvider": {
            "policyRef": _canonical_state_value(
                _state_attribute(
                    policy_provider,
                    "policy_ref",
                    "policy_provider",
                )
            ),
            "recognizedRuleRefs": _canonical_state_value(
                _state_attribute(
                    policy_provider,
                    "recognized_rule_refs",
                    "policy_provider",
                )
            ),
            "bundlePolicyDocument": _canonical_state_value(
                _state_attribute(
                    policy_provider,
                    "_bundle_policy_document",
                    "policy_provider",
                )
            ),
        },
        "referenceBindings": _canonical_state_value(reference_bindings),
        "productLookup": {
            "bindings": _canonical_state_value(bindings),
            "snapshots": _canonical_state_value(product_state),
        },
        "registryReverification": {
            "snapshotPrefix": _canonical_state_value(
                _state_attribute(
                    registry_reverification,
                    "snapshot_prefix",
                    "registry_reverification",
                )
                if registry_reverification is not None else None
            ),
        },
        "runtimeBundleDigest": store.runtime_bundle_digest,
        "tenantRef": store.tenant_ref,
    }
    return sha256_of(payload)


def _same_service_capabilities(
    left: tuple[_ServiceCapabilityReceipt, ...],
    right: tuple[_ServiceCapabilityReceipt, ...],
) -> bool:
    if len(left) != len(right):
        return False
    for left_receipt, right_receipt in zip(left, right):
        if (
            type(left_receipt) is not _ServiceCapabilityReceipt
            or type(right_receipt) is not _ServiceCapabilityReceipt
            or left_receipt.service_name != right_receipt.service_name
            or left_receipt.service_type is not right_receipt.service_type
            or len(left_receipt.capabilities) != len(right_receipt.capabilities)
        ):
            return False
        for left_capability, right_capability in zip(
            left_receipt.capabilities,
            right_receipt.capabilities,
        ):
            if (
                left_capability[0] != right_capability[0]
                or left_capability[1] is not right_capability[1]
            ):
                return False
    return True


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
    """Return provider-module-free code-owned registrations; RS1 registers SI."""
    return ProfileRuntimeProviderRegistry(_DEFAULT_PROVIDER_REGISTRATIONS)


def _service_attribute(service: Any, service_name: str, attribute: str) -> Any:
    try:
        return getattr(service, attribute)
    except Exception as exc:
        raise ProfileRuntimeError(
            f"profile runtime provider {service_name} does not expose "
            f"{attribute!r}"
        ) from exc


def _resolve_module_source_without_import(module_name: str) -> Path:
    """Resolve a dotted module through filesystem finders without importing it."""
    module_parts = module_name.split(".")
    if any(not part or not part.isidentifier() for part in module_parts):
        raise ProfileRuntimeError(
            "profile runtime provider module name is invalid"
        )

    search_path = None
    module_spec = None
    qualified_parts = []
    for index, module_part in enumerate(module_parts):
        qualified_parts.append(module_part)
        qualified_name = ".".join(qualified_parts)
        module_spec = PathFinder.find_spec(qualified_name, search_path)
        if module_spec is None:
            raise ProfileRuntimeError(
                "profile runtime provider module source is unavailable"
            )
        if index < len(module_parts) - 1:
            search_path = module_spec.submodule_search_locations
            if search_path is None:
                raise ProfileRuntimeError(
                    "profile runtime provider module parent is not a package"
                )

    module_origin = module_spec.origin if module_spec is not None else None
    if not module_origin or module_origin in {"built-in", "frozen"}:
        raise ProfileRuntimeError(
            "profile runtime provider module source is unavailable"
        )
    return Path(module_origin).resolve(strict=True)
