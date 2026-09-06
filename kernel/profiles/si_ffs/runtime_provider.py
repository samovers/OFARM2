"""Construct the complete Slovenian runtime service graph."""

from ...context import (
    ContextAssembler,
    SI_REGSR_FAMILY_ID,
    SIProductRegister,
    SIReferenceBindings,
)
from ...materializer import Materializer
from ...profile_policy import DescriptorPolicyProvider
from ...profile_runtime import ProfileRuntimeDescriptor, ProfileRuntimeError
from ...profile_runtime_services import (
    MaterializationSpecification,
    ProfileRuntimeServices,
)
from ...runtime_bundle import RuntimeBundleError, RuntimeComponentRole
from ...sufficiency import OPERATION_FLOOR_CHECKS
from ...validators import RegistryReverificationValidator
from .manifest_inputs import SI_MANIFEST_EVIDENCE_SPECIFICATION
from .outputs import SI_OUTPUT_SPECIFICATION, SIOutputAssembler


_PROFILE_REF = "profile:si.ffs.recordkeeping.v0_1"
SI_MATERIALIZATION_SPECIFICATION = MaterializationSpecification(
    policy_ref="policy:si.ffs.materialization.v0_1",
    default_result_shape_family="si.ffs.spray-register.v0_1",
    identity_registry_result_shape_family="ofarm.identity-registry.v0_1",
)


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
        policy_component,
        supported_checks=OPERATION_FLOOR_CHECKS,
    )
    registry_family = descriptor.reference_family(SI_REGSR_FAMILY_ID)
    reference_bindings = SIReferenceBindings.from_runtime_descriptor(descriptor)
    product_lookup = SIProductRegister(reference_bindings)
    product_lookup.load_from_store(store)
    context_assembler = ContextAssembler(
        store,
        active_descriptor=descriptor,
    )
    materializer = Materializer(
        store,
        specification=SI_MATERIALIZATION_SPECIFICATION,
        context_assembler=context_assembler,
        active_descriptor=descriptor,
    )

    return ProfileRuntimeServices(
        descriptor=descriptor,
        policy_provider=policy_provider,
        context_assembler=context_assembler,
        materialization_specification=SI_MATERIALIZATION_SPECIFICATION,
        materializer=materializer,
        registry_reverification=RegistryReverificationValidator(
            active_profile=descriptor,
            reference_family=registry_family,
            product_lookup=product_lookup,
        ),
        registry_reference_family=registry_family,
        output_specification=SI_OUTPUT_SPECIFICATION,
        output_assembler=SIOutputAssembler(
            store,
            specification=SI_OUTPUT_SPECIFICATION,
            materializer=materializer,
            active_descriptor=descriptor,
        ),
        manifest_evidence_specification=SI_MANIFEST_EVIDENCE_SPECIFICATION,
    )
