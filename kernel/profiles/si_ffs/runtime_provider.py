"""Executable service construction for the registered SI runtime profile."""
from __future__ import annotations

from dataclasses import dataclass

from ... import profile_policy
from ...context import ContextAssembler, SIProductRegister, SIReferenceBindings
from ...materializer import Materializer
from ...profile_runtime import ProfileRuntimeDescriptor, ProfileRuntimeError
from ...profile_runtime_provider import ProfileRuntimeServices
from ...runtime_bundle import RuntimeBundleError, RuntimeComponentRole
from ...sufficiency import OPERATION_FLOOR_CHECKS


@dataclass(frozen=True)
class SIProfileRuntimeProvider:
    """Build the existing SI services behind one explicit provider boundary."""

    package_name: str = "profile_si_ffs"
    profile_ref: str = "profile:si.ffs.recordkeeping.v0_1"
    source_component_role: RuntimeComponentRole = (
        RuntimeComponentRole.ADAPTER_SOURCE
    )
    source_component_logical_ref: str = (
        "python:profile-si-ffs-v0_1:runtime-provider"
    )

    def build_services(
        self,
        store,
        descriptor: ProfileRuntimeDescriptor,
    ) -> ProfileRuntimeServices:
        if descriptor.profile_ref != self.profile_ref:
            raise ProfileRuntimeError(
                "the SI runtime provider received an unsupported profile descriptor"
            )
        try:
            policy_component = store.runtime_bundle.component(
                RuntimeComponentRole.PROFILE_POLICY,
                descriptor.evidence_policy_ref,
            )
        except (AttributeError, RuntimeBundleError) as exc:
            raise ProfileRuntimeError(
                "the SI runtime provider policy is not retained as its exact "
                "startup-verified RuntimeBundle component"
            ) from exc
        policy_provider = profile_policy.DescriptorPolicyProvider.from_runtime_bundle(
            descriptor,
            policy_component.canonical_bytes,
            supported_checks=OPERATION_FLOOR_CHECKS,
        )
        reference_bindings = SIReferenceBindings.from_runtime_descriptor(descriptor)
        product_lookup = SIProductRegister(reference_bindings)
        product_lookup.load_from_store(store)
        return ProfileRuntimeServices(
            provider=self,
            descriptor=descriptor,
            policy_provider=policy_provider,
            context_assembler=ContextAssembler(
                store,
                active_descriptor=descriptor,
            ),
            materializer=Materializer(
                store,
                active_descriptor=descriptor,
            ),
            reference_bindings=reference_bindings,
            product_lookup=product_lookup,
        )


SI_RUNTIME_PROVIDER = SIProfileRuntimeProvider()
