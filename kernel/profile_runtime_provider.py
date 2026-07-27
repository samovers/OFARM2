"""Verified selection of the executable services for one runtime profile."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TYPE_CHECKING, Protocol

from .profile_runtime import ProfileRuntimeDescriptor, ProfileRuntimeError
from .provider_import_policy import ProviderImportError, load_provider_factory
from .runtime_bundle import RuntimeBundle, RuntimeBundleError, RuntimeComponentRole

if TYPE_CHECKING:
    from .context import ContextAssembler, SIProductRegister, SIReferenceBindings
    from .materializer import Materializer
    from .profile_policy import DescriptorPolicyProvider
    from .validators import RegistryReverificationValidator


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_REGISTRY_COMPONENT_REF = (
    "python:ofarm2-kernel-m1.0:profile-runtime-provider-registry"
)


class ProfileRuntimeStore(Protocol):
    """The loader's complete view of runtime state."""

    runtime_bundle: RuntimeBundle

    def require_startup_complete(self, consumer: str) -> None: ...


@dataclass(frozen=True)
class ProfileRuntimeRegistration:
    """Registry-owned identity of one executable profile implementation."""

    package_name: str
    profile_ref: str
    component_role: RuntimeComponentRole
    component_ref: str
    source_path: str
    factory_module: str
    factory_name: str
    factory_resolver: Callable[[], object]

    @property
    def key(self) -> tuple[str, str]:
        return self.package_name, self.profile_ref


@dataclass(frozen=True)
class ProfileRuntimeServices:
    """All services required by the SI gate pipeline."""

    descriptor: ProfileRuntimeDescriptor
    policy_provider: DescriptorPolicyProvider
    context_assembler: ContextAssembler
    materializer: Materializer
    reference_bindings: SIReferenceBindings
    product_lookup: SIProductRegister
    registry_reverification: RegistryReverificationValidator


def _resolve_si_factory():
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
) -> ProfileRuntimeRegistration:
    if type(package_name) is not str or not package_name:
        raise ProfileRuntimeError(
            "profile runtime package name must be a non-empty string"
        )
    if type(descriptor) is not ProfileRuntimeDescriptor:
        raise ProfileRuntimeError(
            "profile runtime descriptor must use the trusted type"
        )
    key = package_name, descriptor.profile_ref
    registration = next(
        (candidate for candidate in _REGISTRATIONS if candidate.key == key),
        None,
    )
    if registration is None:
        raise ProfileRuntimeError(
            f"no executable runtime is registered for profile identity {key!r}"
        )
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
):
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


def _validate_services(
    services: object,
    descriptor: ProfileRuntimeDescriptor,
) -> ProfileRuntimeServices:
    from .context import ContextAssembler, SIProductRegister, SIReferenceBindings
    from .materializer import Materializer
    from .profile_policy import DescriptorPolicyProvider
    from .validators import RegistryReverificationValidator

    if type(services) is not ProfileRuntimeServices:
        raise ProfileRuntimeError("runtime factory returned an invalid service bundle")
    required_types = (
        (services.policy_provider, DescriptorPolicyProvider),
        (services.context_assembler, ContextAssembler),
        (services.materializer, Materializer),
        (services.reference_bindings, SIReferenceBindings),
        (services.product_lookup, SIProductRegister),
        (services.registry_reverification, RegistryReverificationValidator),
    )
    if services.descriptor is not descriptor or any(
        not isinstance(service, expected)
        for service, expected in required_types
    ):
        raise ProfileRuntimeError(
            "runtime factory returned incomplete or mismatched services"
        )
    required_rules = frozenset({
        descriptor.evidence_policy_ref,
        descriptor.profile_ref,
        descriptor.pack_ref,
        descriptor.code_binding_profile_ref,
    })
    if (
        services.policy_provider.policy_ref != descriptor.evidence_policy_ref
        or not required_rules.issubset(
            services.policy_provider.recognized_rule_refs
        )
    ):
        raise ProfileRuntimeError(
            "runtime policy service does not match the selected descriptor"
        )
    return services


def load_profile_runtime_services(
    store: ProfileRuntimeStore,
    package_name: str,
    descriptor: ProfileRuntimeDescriptor,
) -> ProfileRuntimeServices:
    """Verify registry and provider bytes, then construct bound services."""
    store.require_startup_complete("profile runtime service loading")
    _verify_source(
        store,
        RuntimeComponentRole.ADAPTER_SOURCE,
        _REGISTRY_COMPONENT_REF,
        "kernel/profile_runtime_provider.py",
    )
    registration = _registration_for(package_name, descriptor)
    source_path, source_bytes = _verify_source(
        store,
        registration.component_role,
        registration.component_ref,
        registration.source_path,
    )
    factory = _load_factory(registration, source_path, source_bytes)
    return _validate_services(factory(store, descriptor), descriptor)
