"""Verified selection of the executable services for one runtime profile."""
from __future__ import annotations

from dataclasses import dataclass
from inspect import signature
from pathlib import Path
from typing import Callable, Protocol

from .profile_runtime import ProfileRuntimeDescriptor, ProfileRuntimeError, ReferenceFamily
from .provider_import_policy import ProviderImportError, load_provider_factory
from .profile_runtime_services import (
    MaterializationSpecification,
    OutputSpecification,
    ProfileContextAssembler,
    ProfileManifestEvidenceSpecification,
    ProfileMaterializer,
    ProfileOutputAssembler,
    ProfilePolicyService,
    ProfileRegistryReverification,
    ProfileRuntimeServices,
)
from .runtime_bundle import RuntimeBundle, RuntimeBundleError, RuntimeComponentRole


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_REGISTRY_COMPONENT_REF = "python:ofarm2-kernel-m1.0:profile-runtime-provider-registry"


class ProfileRuntimeStore(Protocol):
    """The loader's complete view of runtime state."""
    active_descriptor: ProfileRuntimeDescriptor
    runtime_bundle: RuntimeBundle
    def require_startup_complete(self, consumer: str) -> None: ...
    def selected_reference_source_data(self, snapshot_family: str) -> list[dict]: ...


class ProfileRuntimeFactory(Protocol):
    def __call__(
        self,
        store: ProfileRuntimeStore,
        descriptor: ProfileRuntimeDescriptor,
    ) -> ProfileRuntimeServices: ...


@dataclass(frozen=True, slots=True)
class ProfileRuntimeRegistration:
    """Registry-owned identity of one executable profile implementation."""

    package_name: str
    profile_ref: str
    component_role: RuntimeComponentRole
    component_ref: str
    source_path: str
    factory_module: str
    factory_name: str
    factory_resolver: Callable[[], ProfileRuntimeFactory]

    @property
    def key(self) -> tuple[str, str]:
        return self.package_name, self.profile_ref


def _resolve_si_factory() -> ProfileRuntimeFactory:
    from .profiles.si_ffs.runtime_provider import build_si_runtime_services

    return build_si_runtime_services


_REGISTRATIONS = (
    ProfileRuntimeRegistration(
        package_name="profile_si_ffs",
        profile_ref="profile:si.ffs.recordkeeping.v0_1",
        component_role=RuntimeComponentRole.ADAPTER_SOURCE,
        component_ref="python:profile-si-ffs-v0_1:runtime-provider",
        source_path="kernel/profiles/si_ffs/runtime_provider.py",
        factory_module="kernel.profiles.si_ffs.runtime_provider",
        factory_name="build_si_runtime_services",
        factory_resolver=_resolve_si_factory,
    ),
)


def _registration_for(
    package_name: str,
    descriptor: ProfileRuntimeDescriptor,
    registrations: tuple[ProfileRuntimeRegistration, ...] = _REGISTRATIONS,
) -> ProfileRuntimeRegistration:
    if type(package_name) is not str or not package_name:
        raise ProfileRuntimeError("profile runtime package name must be non-empty")
    if type(descriptor) is not ProfileRuntimeDescriptor:
        raise ProfileRuntimeError("profile runtime descriptor must use trusted type")
    if any(
        type(registration) is not ProfileRuntimeRegistration
        for registration in registrations
    ):
        raise ProfileRuntimeError("profile runtime registry contains an invalid registration")
    keys = tuple(registration.key for registration in registrations)
    if len(keys) != len(set(keys)):
        raise ProfileRuntimeError("profile runtime registry contains duplicate identities")
    key = package_name, descriptor.profile_ref
    registration = next(
        (candidate for candidate in registrations if candidate.key == key),
        None,
    )
    if registration is None:
        raise ProfileRuntimeError(
            f"no executable runtime is registered for profile identity {key!r}")
    return registration


def _verify_source(
    store: ProfileRuntimeStore,
    role: RuntimeComponentRole,
    logical_ref: str,
    source_path: str,
) -> tuple[Path, bytes]:
    try:
        component = store.runtime_bundle.component(role, logical_ref)
        path = (_PACKAGE_ROOT / source_path).resolve(strict=True)
        path.relative_to(_PACKAGE_ROOT)
        source_bytes = path.read_bytes()
    except (OSError, RuntimeBundleError, ValueError) as exc:
        raise ProfileRuntimeError(
            f"registered runtime source {logical_ref!r} is unavailable"
        ) from exc
    if component.canonical_bytes != source_bytes:
        raise ProfileRuntimeError(
            f"registered runtime source {logical_ref!r} differs from the "
            "startup-verified RuntimeBundle"
        )
    return path, source_bytes


def _load_factory(
    registration: ProfileRuntimeRegistration,
    source_path: Path,
    source_bytes: bytes,
) -> ProfileRuntimeFactory:
    try:
        return load_provider_factory(
            module_name=registration.factory_module,
            component_ref=registration.component_ref,
            source_path=source_path,
            source_bytes=source_bytes,
            factory_name=registration.factory_name,
            factory_resolver=registration.factory_resolver,
        )
    except ProviderImportError as exc:
        raise ProfileRuntimeError(
            f"runtime factory module {registration.factory_module!r} is unavailable"
        ) from exc


def _validate_call_forms(services: ProfileRuntimeServices) -> None:
    value, pair = object(), (object(), object())
    frozen = (value, value, value, value)
    calls = (
        (services.policy_provider.evidence_policy, (), {}),
        (services.policy_provider.evidence_policy, (), {"supported_checks": value}),
        (services.policy_provider.validation_policy, (), {}),
        (services.context_assembler.assemble, pair, {}),
        (services.context_assembler.assemble, pair,
         {"target_twin": value, "evaluation_time_policy": value}),
        (services.materializer.invalidate_for_sources, pair,
         {"trigger_family": value, "trigger_source_ref": value,
          "farm_scope_ref": value, "reason_code": value}),
        (services.materializer.recompute, pair, {}),
        (services.materializer.recompute, pair,
         {"twin": value, "use_class": value, "time_policy": value}),
        (services.materializer.resolve_for_use, pair,
         {"use_class": value, "required_freshness": value,
          "high_consequence": value, "recompute_if_needed": value}),
        (services.materializer.resolve_for_use, pair,
         {"use_class": value, "time_policy": value,
          "required_freshness": value, "high_consequence": value}),
        (services.registry_reverification.run, (value,), {}),
        (services.output_assembler.passport_view, pair, {}),
        (services.output_assembler.passport_view, pair, {"allow_recompute": value}),
        (services.output_assembler.freeze_document_assembly, frozen, {}),
        (services.output_assembler.freeze_document_assembly, frozen,
         {"as_submission": value}),
    )
    try:
        for method, args, kwargs in calls:
            if not callable(method):
                raise TypeError("required runtime service is not callable")
            signature(method).bind(*args, **kwargs)
    except (TypeError, ValueError) as exc:
        raise ProfileRuntimeError(
            "runtime service has a missing or incompatible callable"
        ) from exc


def _validate_registry_binding(
    services: ProfileRuntimeServices,
    descriptor: ProfileRuntimeDescriptor,
    expected_store: ProfileRuntimeStore,
) -> None:
    family = services.registry_reference_family
    registry = services.registry_reverification
    selected = registry.selected_input_bindings
    if (
        family is not None
        and (type(family) is not ReferenceFamily
             or not any(family is candidate
                        for candidate in descriptor.reference_families))
    ):
        raise ProfileRuntimeError("runtime registry family is not descriptor-owned")
    if (
        registry.active_profile is not descriptor
        or registry.reference_family is not family
        or type(selected) is not tuple
        or any(type(item) is not tuple or len(item) != 3
               or any(type(value) is not str or not value for value in item)
               for item in selected)
    ):
        raise ProfileRuntimeError("runtime registry service provenance is invalid")
    if family is None:
        matches = registry.runtime_bundle is None and selected == ()
    else:
        expected = tuple(
            (row["snapshot_ref"], row["artifact_ref"], row["source_digest"])
            for row in expected_store.selected_reference_source_data(
                family.snapshot_prefix
            )
        )
        matches = (
            registry.runtime_bundle is expected_store.runtime_bundle
            and selected == expected
        )
    if not matches:
        raise ProfileRuntimeError("runtime registry service inputs do not match Store")


def _inspect_services(
    services: object,
    descriptor: ProfileRuntimeDescriptor,
    expected_store: ProfileRuntimeStore,
) -> ProfileRuntimeServices:
    if type(services) is not ProfileRuntimeServices:
        raise ProfileRuntimeError("runtime factory returned an invalid service bundle")
    required_types = (
        (services.policy_provider, ProfilePolicyService),
        (services.context_assembler, ProfileContextAssembler),
        (services.materializer, ProfileMaterializer),
        (services.registry_reverification, ProfileRegistryReverification),
        (services.output_assembler, ProfileOutputAssembler),
    )
    if (
        type(descriptor) is not ProfileRuntimeDescriptor
        or expected_store.active_descriptor is not descriptor
        or services.descriptor is not descriptor
        or type(services.materialization_specification)
        is not MaterializationSpecification
        or type(services.output_specification) is not OutputSpecification
        or type(services.manifest_evidence_specification)
        is not ProfileManifestEvidenceSpecification
        or any(
        not isinstance(service, expected)
        for service, expected in required_types
        )
    ):
        raise ProfileRuntimeError("runtime factory returned incomplete or mismatched services")
    _validate_call_forms(services)
    if (
        services.context_assembler.store is not expected_store
        or services.materializer.store is not expected_store
        or services.output_assembler.store is not expected_store
        or services.materializer.context is not services.context_assembler
        or services.materializer.specification
        is not services.materialization_specification
        or services.output_assembler.specification
        is not services.output_specification
        or services.output_assembler.materializer is not services.materializer
        or services.policy_provider.descriptor is not descriptor
        or services.context_assembler.active_profile is not descriptor
        or services.materializer.active_profile is not descriptor
        or services.output_assembler.active_profile is not descriptor
    ):
        raise ProfileRuntimeError("runtime factory returned services from different profile bindings")
    expected_policy = expected_store.runtime_bundle.component(
        RuntimeComponentRole.PROFILE_POLICY,
        descriptor.evidence_policy_ref,
    )
    if services.policy_provider.runtime_component is not expected_policy:
        raise ProfileRuntimeError("runtime policy lacks the selected component")
    _validate_registry_binding(services, descriptor, expected_store)
    required_rules = frozenset({
        descriptor.evidence_policy_ref,
        descriptor.profile_ref,
        descriptor.pack_ref,
        descriptor.code_binding_profile_ref,
    })
    recognized = services.policy_provider.recognized_rule_refs
    if (
        type(recognized) is not frozenset
        or any(type(ref) is not str or not ref for ref in recognized)
        or services.policy_provider.policy_ref != descriptor.evidence_policy_ref
        or not required_rules.issubset(recognized)
    ):
        raise ProfileRuntimeError("runtime policy does not match the descriptor")
    return services


def _validate_services(services: object, descriptor: ProfileRuntimeDescriptor,
                       expected_store: ProfileRuntimeStore) -> ProfileRuntimeServices:
    """Admit one complete Store-bound graph for every composition path."""
    try:
        return _inspect_services(services, descriptor, expected_store)
    except ProfileRuntimeError:
        raise
    except Exception as exc:
        raise ProfileRuntimeError("runtime service graph inspection failed") from exc


def load_profile_runtime_services(
    store: ProfileRuntimeStore,
    package_name: str,
    descriptor: ProfileRuntimeDescriptor,
    *,
    _registrations: tuple[ProfileRuntimeRegistration, ...] | None = None,
) -> ProfileRuntimeServices:
    """Verify source identity, admit source import, then construct services."""
    store.require_startup_complete("profile runtime service loading")
    _verify_source(
        store,
        RuntimeComponentRole.ADAPTER_SOURCE,
        _REGISTRY_COMPONENT_REF,
        "kernel/profile_runtime_provider.py",
    )
    registrations = _REGISTRATIONS if _registrations is None else _registrations
    registration = _registration_for(package_name, descriptor, registrations)
    source_path, source_bytes = _verify_source(
        store,
        registration.component_role,
        registration.component_ref,
        registration.source_path,
    )
    factory = _load_factory(registration, source_path, source_bytes)
    return _validate_services(factory(store, descriptor), descriptor, store)
