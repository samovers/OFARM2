"""Synthetic services used only to prove the profile-neutral runtime seam."""
from __future__ import annotations

from kernel.profile_runtime_services import (
    GovernedViewBinding,
    MaterializationSpecification,
    OutputSpecification,
    ProfileManifestEvidenceSpecification,
    ProfileRuntimeServices,
    RegistryReverificationDisposition,
    RegistryReverificationOutcome,
)
from kernel.runtime_bundle import RuntimeComponentRole


class SyntheticPolicy:
    def __init__(self, descriptor, runtime_component):
        self.descriptor = descriptor
        self.policy_ref = descriptor.evidence_policy_ref
        self.runtime_component = runtime_component
        self.recognized_rule_refs = frozenset({
            descriptor.evidence_policy_ref,
            descriptor.profile_ref,
            descriptor.pack_ref,
            descriptor.code_binding_profile_ref,
        })

    def evidence_policy(self, supported_checks=None):
        return {"supportedChecks": supported_checks}

    def validation_policy(self):
        return {"profile": "synthetic"}


class SyntheticContextAssembler:
    def __init__(self, store, descriptor):
        self.store = store
        self.active_profile = descriptor

    def assemble(
        self,
        _cur,
        farm_ref,
        *,
        target_twin="COMPLIANCE",
        evaluation_time_policy=None,
    ):
        return {
            "contextSnapshotId": "contextsnapshot:synthetic.runtime.v0_1",
            "farmRef": farm_ref,
            "targetTwin": target_twin,
            "evaluationTimePolicy": evaluation_time_policy,
        }


class SyntheticMaterializer:
    def __init__(self, store, descriptor, specification, context_assembler):
        self.store = store
        self.active_profile = descriptor
        self.specification = specification
        self.context = context_assembler
        self.invalidation_calls = []

    def invalidate_for_sources(
        self,
        _cur,
        source_refs,
        *,
        trigger_family,
        trigger_source_ref,
        farm_scope_ref=None,
        reason_code="BASIS_ADVANCED",
    ):
        self.invalidation_calls.append({
            "sourceRefs": tuple(source_refs),
            "triggerFamily": trigger_family,
            "triggerSourceRef": trigger_source_ref,
            "farmScopeRef": farm_scope_ref,
            "reasonCode": reason_code,
        })
        return len(source_refs)

    def recompute(
        self,
        _cur,
        farm_ref,
        *,
        twin="COMPLIANCE",
        use_class="OPERATIONAL_DASHBOARD",
        time_policy=None,
    ):
        return {
            "basisRef": "basis:synthetic.runtime.v0_1",
            "snapshotRef": "snapshot:synthetic.runtime.v0_1",
            "farmRef": farm_ref,
            "twin": twin,
            "useClass": use_class,
            "timePolicy": time_policy,
            "policyRef": self.specification.policy_ref,
            "resultShapeFamily": (
                self.specification.default_result_shape_family
            ),
        }

    def resolve_for_use(
        self,
        _cur,
        farm_ref,
        *,
        twin="COMPLIANCE",
        use_class="OPERATIONAL_DASHBOARD",
        time_policy=None,
        required_freshness=None,
        high_consequence=False,
        recompute_if_needed=True,
    ):
        return self.recompute(
            _cur,
            farm_ref,
            twin=twin,
            use_class=use_class,
            time_policy=time_policy,
        )


class SyntheticReverification:
    def __init__(self, descriptor):
        self.active_profile = descriptor
        self.reference_family = None
        self.runtime_bundle = None
        self.selected_input_bindings = ()
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        return RegistryReverificationOutcome(
            RegistryReverificationDisposition.NO_EFFECT
        )


class SyntheticOutputAssembler:
    def __init__(self, store, descriptor, specification, materializer):
        self.store = store
        self.active_profile = descriptor
        self.specification = specification
        self.materializer = materializer

    def passport_view(
        self,
        farm_ref,
        requesting_party_ref,
        *,
        allow_recompute=True,
    ):
        return {
            "viewRef": self.specification.passport_view.view_ref,
            "farmRef": farm_ref,
            "requestingPartyRef": requesting_party_ref,
            "allowRecompute": allow_recompute,
        }

    def freeze_document_assembly(
        self,
        farm_ref,
        requesting_party_ref,
        window_start,
        window_end,
        *,
        as_submission=False,
    ):
        return {
            "viewRef": self.specification.document_assembly.view_ref,
            "farmRef": farm_ref,
            "requestingPartyRef": requesting_party_ref,
            "window": [window_start, window_end],
            "asSubmission": as_submission,
        }


def build_synthetic_runtime_services(_store, descriptor):
    policy_component = _store.runtime_bundle.component(
        RuntimeComponentRole.PROFILE_POLICY,
        descriptor.evidence_policy_ref,
    )
    materialization = MaterializationSpecification(
        policy_ref="policy:synthetic.materialization.v0_1",
        default_result_shape_family="synthetic.operations.v0_1",
        identity_registry_result_shape_family="synthetic.identities.v0_1",
    )
    outputs = OutputSpecification(
        passport_view=GovernedViewBinding(
            view_ref="view:synthetic.passport.v0_1",
            query_specification_ref="queryspec:synthetic.passport.v0_1",
            query_plan_ref="queryplan:synthetic.passport.v0_1",
        ),
        document_assembly=GovernedViewBinding(
            view_ref="view:synthetic.document.v0_1",
            query_specification_ref="queryspec:synthetic.document.v0_1",
            query_plan_ref="queryplan:synthetic.document.v0_1",
        ),
        claim_statement="Synthetic profile-local output.",
        freeze_rule_ref="rule:synthetic.freeze.v0_1",
        durable_artifact_prefix="document:synthetic.",
        version_label_prefix="synthetic.document.",
    )
    context_assembler = SyntheticContextAssembler(_store, descriptor)
    materializer = SyntheticMaterializer(
        _store,
        descriptor,
        materialization,
        context_assembler,
    )
    return ProfileRuntimeServices(
        descriptor=descriptor,
        policy_provider=SyntheticPolicy(descriptor, policy_component),
        context_assembler=context_assembler,
        materialization_specification=materialization,
        materializer=materializer,
        registry_reverification=SyntheticReverification(descriptor),
        registry_reference_family=None,
        output_specification=outputs,
        output_assembler=SyntheticOutputAssembler(
            _store,
            descriptor,
            outputs,
            materializer,
        ),
        manifest_evidence_specification=ProfileManifestEvidenceSpecification(
            manifest_id="manifest:synthetic.runtime.v0_1",
            manifest_filename="synthetic_manifest.json",
            active_artifact_set_filename="synthetic_artifact_set.json",
            source_component_ref="python:synthetic-profile:manifest-inputs",
            supported_import_bindings=(),
            artifact_set_notes="Synthetic test-only profile artifacts.",
            profile_executed_evidence_refs=(),
        ),
    )
