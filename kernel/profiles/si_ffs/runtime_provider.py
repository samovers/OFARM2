"""Construct the complete Slovenian runtime service graph."""

from ...context import (
    ContextAssembler,
    SIProductRegister,
    SIReferenceBindings,
)
from ...materializer import Materializer
from ...profile_policy import DescriptorPolicyProvider
from ...profile_runtime import ProfileRuntimeDescriptor, ProfileRuntimeError
from ...profile_runtime_provider import ProfileRuntimeServices
from ...runtime_bundle import RuntimeBundleError, RuntimeComponentRole
from ...sufficiency import OPERATION_FLOOR_CHECKS
from ...validators import RegistryReverificationValidator


_PROFILE_REF = "profile:si.ffs.recordkeeping.v0_1"


def build_si_runtime_services(
    store,
    descriptor: ProfileRuntimeDescriptor,
) -> ProfileRuntimeServices:
    """Construct a fresh graph for the already verified SI implementation."""
    if descriptor.profile_ref != _PROFILE_REF:
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
            "the SI profile policy is not retained by the startup-verified "
            "RuntimeBundle"
        ) from exc

    policy_provider = DescriptorPolicyProvider.from_runtime_bundle(
        descriptor,
        policy_component.canonical_bytes,
        supported_checks=OPERATION_FLOOR_CHECKS,
    )
    reference_bindings = SIReferenceBindings.from_runtime_descriptor(descriptor)
    product_lookup = SIProductRegister(reference_bindings)
    product_lookup.load_from_store(store)

    return ProfileRuntimeServices(
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
        registry_reverification=RegistryReverificationValidator(
            snapshot_prefix=reference_bindings.regsr_snapshot_prefix,
            product_lookup=product_lookup,
        ),
    )
