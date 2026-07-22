"""Executable service construction for the registered SI runtime profile."""
from __future__ import annotations

from dataclasses import dataclass

from ... import profile_policy
from ...context import ContextAssembler, SIProductRegister, SIReferenceBindings
from ...materializer import Materializer
from ...profile_runtime import ProfileRuntimeDescriptor, ProfileRuntimeError
from ...profile_runtime_provider import ProfileRuntimeServices


@dataclass(frozen=True)
class SIProfileRuntimeProvider:
    """Build the existing SI services behind one explicit provider boundary."""

    package_name: str = "profile_si_ffs"
    profile_ref: str = "profile:si.ffs.recordkeeping.v0_1"

    def build_services(
        self,
        store,
        descriptor: ProfileRuntimeDescriptor,
    ) -> ProfileRuntimeServices:
        if descriptor.profile_ref != self.profile_ref:
            raise ProfileRuntimeError(
                "the SI runtime provider received an unsupported profile descriptor"
            )
        policy_provider = profile_policy.DescriptorPolicyProvider(descriptor)
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
