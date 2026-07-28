"""Synthetic non-SI services used only to prove the neutral runtime seam."""
from __future__ import annotations

from kernel.profile_runtime_services import (
    GovernedViewBinding,
    MaterializationSpecification,
    OutputSpecification,
    ProfileManifestEvidenceSpecification,
    ProfileRuntimeServices,
)


class SyntheticPolicy:
    def __init__(self, descriptor):
        self.descriptor = descriptor
        self.policy_ref = descriptor.evidence_policy_ref
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
    def __init__(self, descriptor):
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
            "farmRef": farm_ref,
            "targetTwin": target_twin,
            "evaluationTimePolicy": evaluation_time_policy,
        }


class SyntheticMaterializer:
    def __init__(self, descriptor, specification):
        self.active_profile = descriptor
        self.specification = specification

    def invalidate_for_sources(
        self,
        _cur,
        source_refs,
        *,
        trigger_family="BASIS_ADVANCED",
    ):
        return len(source_refs)

    def recompute(
        self,
        _cur,
        farm_ref,
        *,
        twin="COMPLIANCE",
        time_policy=None,
    ):
        return {
            "farmRef": farm_ref,
            "twin": twin,
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
            time_policy=time_policy,
        )


class SyntheticReverification:
    def run(self, _context):
        return None


class SyntheticOutputAssembler:
    def __init__(self, descriptor, specification, materializer):
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
    materializer = SyntheticMaterializer(descriptor, materialization)
    return ProfileRuntimeServices(
        descriptor=descriptor,
        policy_provider=SyntheticPolicy(descriptor),
        context_assembler=SyntheticContextAssembler(descriptor),
        materialization_specification=materialization,
        materializer=materializer,
        registry_reverification=SyntheticReverification(),
        output_specification=outputs,
        output_assembler=SyntheticOutputAssembler(
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
