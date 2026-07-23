"""Executable service construction for the registered SI runtime profile."""

# This retained source deliberately has no imports or decorators. The trusted
# composition seam verifies the complete runtime-behavior graph, injects exact
# code-owned dependencies into the sealed namespace, and only then executes
# these retained bytes. No live import-time callable can run before that check.
if False:  # pragma: no cover - static names only; never executed
    from ...context import (
        ContextAssembler,
        SIProductRegister,
        SIReferenceBindings,
    )
    from ...materializer import Materializer
    from ...profile_policy import DescriptorPolicyProvider
    from ...profile_runtime import ProfileRuntimeError
    from ...profile_runtime_provider import ProfileRuntimeServices
    from ...runtime_bundle import RuntimeBundleError, RuntimeComponentRole
    from ...sufficiency import OPERATION_FLOOR_CHECKS
    from ...validators import RegistryReverificationValidator

    PROVIDER_SOURCE_COMPONENT_ROLE = RuntimeComponentRole.ADAPTER_SOURCE
    PROFILE_POLICY_COMPONENT_ROLE = RuntimeComponentRole.PROFILE_POLICY


class SIProfileRuntimeProvider:
    """Build the existing SI services behind one explicit provider boundary."""

    package_name = "profile_si_ffs"
    profile_ref = "profile:si.ffs.recordkeeping.v0_1"
    source_component_role = PROVIDER_SOURCE_COMPONENT_ROLE
    source_component_logical_ref = (
        "python:profile-si-ffs-v0_1:runtime-provider"
    )

    def build_services(
        self,
        store,
        descriptor,
    ):
        if descriptor.profile_ref != self.profile_ref:
            raise ProfileRuntimeError(
                "the SI runtime provider received an unsupported profile descriptor"
            )
        try:
            policy_component = store.runtime_bundle.component(
                PROFILE_POLICY_COMPONENT_ROLE,
                descriptor.evidence_policy_ref,
            )
        except (AttributeError, RuntimeBundleError) as exc:
            raise ProfileRuntimeError(
                "the SI runtime provider policy is not retained as its exact "
                "startup-verified RuntimeBundle component"
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
            registry_reverification=RegistryReverificationValidator(
                snapshot_prefix=reference_bindings.regsr_snapshot_prefix,
                product_lookup=product_lookup,
            ),
        )


SI_RUNTIME_PROVIDER = SIProfileRuntimeProvider()
