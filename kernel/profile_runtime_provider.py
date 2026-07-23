"""Small, explicit profile-runtime service selection.

Descriptors describe package content; they do not provide executable code.
This composition seam contains the complete code-owned provider registry and
currently has exactly one registered implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .profile_runtime import ProfileRuntimeDescriptor, ProfileRuntimeError
from .runtime_bundle import (
    RuntimeBundleError,
    RuntimeComponent,
    RuntimeComponentRole,
)


ProfileRuntimeFactory = Callable[
    [Any, ProfileRuntimeDescriptor, RuntimeComponent],
    "ProfileRuntimeServices",
]


@dataclass(frozen=True)
class RuntimeServiceRequirement:
    """One service slot and the callable capabilities its provider promises."""

    service_name: str
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfileRuntimeProviderRegistration:
    """One deliberately registered executable provider factory."""

    package_name: str
    profile_ref: str
    factory: ProfileRuntimeFactory
    source_component_role: RuntimeComponentRole
    source_component_logical_ref: str
    source_component_digest: str
    required_services: tuple[RuntimeServiceRequirement, ...]

    @property
    def key(self) -> tuple[str, str]:
        return self.package_name, self.profile_ref


@dataclass(frozen=True)
class ProfileRuntimeServices:
    """Capability-specific services selected for one descriptor.

    The optional field defaults keep this seam usable by a future separately
    reviewed provider without requiring a universal product-register API.
    Each registration declares which of these fields it actually requires.
    """

    provider_key: tuple[str, str]
    provider_source_digest: str
    descriptor: ProfileRuntimeDescriptor
    policy_provider: Any
    context_assembler: Any
    materializer: Any
    reference_bindings: Any = None
    product_lookup: Any = None
    registry_reverification: Any = None


@dataclass(frozen=True)
class ProfileRuntimeProviderRegistry:
    """Immutable provider registrations keyed by package/profile identity."""

    registrations: tuple[ProfileRuntimeProviderRegistration, ...]

    def __post_init__(self) -> None:
        keys = [registration.key for registration in self.registrations]
        if len(keys) != len(set(keys)):
            raise ProfileRuntimeError(
                "profile runtime provider registry contains duplicate identities"
            )

    @property
    def registered_identities(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            registration.key for registration in self.registrations
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
                "profile runtime provider descriptor must use the trusted type"
            )
        key = package_name, descriptor.profile_ref
        registration = next(
            (
                candidate
                for candidate in self.registrations
                if candidate.key == key
            ),
            None,
        )
        if registration is None:
            raise ProfileRuntimeError(
                "no registered executable runtime provider for profile identity "
                f"{key!r}"
            )
        return registration

    def build_services(
        self,
        store,
        package_name: str,
        descriptor: ProfileRuntimeDescriptor,
    ) -> ProfileRuntimeServices:
        """Compose and validate a fresh service graph for one pipeline."""
        registration = self.registration_for(package_name, descriptor)
        source_component = self._verified_source_component(store, registration)
        services = registration.factory(store, descriptor, source_component)
        self._validate_services(
            registration,
            descriptor,
            source_component,
            services,
        )
        return services

    @staticmethod
    def _verified_source_component(
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
                "profile runtime provider source is not retained by the "
                "startup-verified RuntimeBundle"
            ) from exc
        if component.content_digest != registration.source_component_digest:
            raise ProfileRuntimeError(
                "profile runtime provider source digest does not match its "
                "code-owned registration"
            )
        return component

    @staticmethod
    def _validate_services(
        registration: ProfileRuntimeProviderRegistration,
        descriptor: ProfileRuntimeDescriptor,
        source_component: RuntimeComponent,
        services: Any,
    ) -> None:
        if type(services) is not ProfileRuntimeServices:
            raise ProfileRuntimeError(
                "profile runtime provider returned an invalid service bundle"
            )
        if (
            services.provider_key != registration.key
            or services.descriptor is not descriptor
            or services.provider_source_digest != source_component.content_digest
        ):
            raise ProfileRuntimeError(
                "profile runtime provider returned services with mismatched identity"
            )
        for requirement in registration.required_services:
            service = getattr(services, requirement.service_name, None)
            if service is None:
                raise ProfileRuntimeError(
                    "profile runtime provider omitted required service "
                    f"{requirement.service_name!r}"
                )
            missing = [
                capability
                for capability in requirement.capabilities
                if not callable(getattr(service, capability, None))
            ]
            if missing:
                raise ProfileRuntimeError(
                    "profile runtime provider service "
                    f"{requirement.service_name!r} lacks required callable "
                    f"capabilities {missing!r}"
                )

        policy_provider = services.policy_provider
        if (
            getattr(policy_provider, "policy_ref", None)
            != descriptor.evidence_policy_ref
        ):
            raise ProfileRuntimeError(
                "profile runtime provider policy_ref does not match the "
                "descriptor evidencePolicyRef"
            )
        recognized_rule_refs = getattr(
            policy_provider,
            "recognized_rule_refs",
            None,
        )
        required_rule_refs = frozenset({
            descriptor.evidence_policy_ref,
            descriptor.profile_ref,
            descriptor.pack_ref,
            descriptor.code_binding_profile_ref,
        })
        if (
            type(recognized_rule_refs) is not frozenset
            or not required_rule_refs.issubset(recognized_rule_refs)
        ):
            raise ProfileRuntimeError(
                "profile runtime provider policy service has invalid "
                "recognized_rule_refs"
            )


_SI_PROVIDER_SOURCE_DIGEST = (
    "sha256:a982e3793ee11593c9a542c0cf6094e99738204c13c0dfe992fac82be61f5f1b"
)

_SI_SERVICE_REQUIREMENTS = (
    RuntimeServiceRequirement(
        "policy_provider",
        ("validation_policy", "evidence_policy"),
    ),
    RuntimeServiceRequirement("context_assembler", ("assemble",)),
    RuntimeServiceRequirement(
        "materializer",
        ("invalidate_for_sources", "recompute"),
    ),
    RuntimeServiceRequirement("reference_bindings"),
    RuntimeServiceRequirement("product_lookup", ("lookup_by_decision",)),
    RuntimeServiceRequirement("registry_reverification", ("run",)),
)

from .profiles.si_ffs.runtime_provider import (  # noqa: E402
    build_si_runtime_services as _build_si_runtime_services,
)

_DEFAULT_PROFILE_RUNTIME_PROVIDER_REGISTRY = ProfileRuntimeProviderRegistry((
    ProfileRuntimeProviderRegistration(
        package_name="profile_si_ffs",
        profile_ref="profile:si.ffs.recordkeeping.v0_1",
        factory=_build_si_runtime_services,
        source_component_role=RuntimeComponentRole.ADAPTER_SOURCE,
        source_component_logical_ref=(
            "python:profile-si-ffs-v0_1:runtime-provider"
        ),
        source_component_digest=_SI_PROVIDER_SOURCE_DIGEST,
        required_services=_SI_SERVICE_REQUIREMENTS,
    ),
))


def default_profile_runtime_provider_registry() -> ProfileRuntimeProviderRegistry:
    """Return the immutable code-owned single-provider registry."""
    return _DEFAULT_PROFILE_RUNTIME_PROVIDER_REGISTRY
