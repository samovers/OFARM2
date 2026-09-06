"""Conformance evidence for the profile-neutral executable-service seam."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from kernel import config
import kernel.profile_runtime_provider as profile_runtime_provider
from kernel.contracts import ContractRegistry
from kernel.problems import runtime_problem
from kernel.profile_runtime import ProfileRuntimeError
from kernel.profile_runtime_provider import (
    ProfileRuntimeRegistration,
    load_profile_runtime_services,
)
from kernel.profile_runtime_services import (
    RegistryReverificationDisposition,
    RegistryReverificationOutcome,
)
from kernel.runtime_bundle import (
    Canonicalization,
    ContentPlacement,
    RuntimeComponent,
    RuntimeComponentRole,
)
from kernel.stages import GatePass, MaterializationGate, ProfileApplicabilityGate
from kernel.validators import _run_registry_reverification


def test_synthetic_second_profile_uses_only_profile_local_services():
    def resolve_synthetic_factory():
        from kernel.tests._synthetic_profile_runtime import (
            build_synthetic_runtime_services,
        )

        return build_synthetic_runtime_services

    descriptor = replace(
        config.ACTIVE_PROFILE,
        profile_ref="profile:synthetic.runtime.v0_1",
        pack_ref="pack:synthetic.runtime.v0_1",
        code_binding_profile_ref="codebindingprofile:synthetic.runtime.v0_1",
        evidence_policy_ref="policy:synthetic.evidence.v0_1",
    )
    registration = ProfileRuntimeRegistration(
        package_name="profile_synthetic_test",
        profile_ref=descriptor.profile_ref,
        component_role=RuntimeComponentRole.ADAPTER_SOURCE,
        component_ref="python:synthetic-profile:runtime-provider",
        source_path="kernel/tests/_synthetic_profile_runtime.py",
        factory_module="kernel.tests._synthetic_profile_runtime",
        factory_name="build_synthetic_runtime_services",
        factory_resolver=resolve_synthetic_factory,
    )
    registry_component = RuntimeComponent.from_selected_bytes(
        role=RuntimeComponentRole.ADAPTER_SOURCE,
        logical_ref=profile_runtime_provider._REGISTRY_COMPONENT_REF,
        canonicalization=Canonicalization.EXACT_BYTES,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=Path(profile_runtime_provider.__file__).read_bytes(),
    )
    provider_path = (
        config.PACKAGE_ROOT
        / "kernel"
        / "tests"
        / "_synthetic_profile_runtime.py"
    )
    provider_component = RuntimeComponent.from_selected_bytes(
        role=registration.component_role,
        logical_ref=registration.component_ref,
        canonicalization=Canonicalization.EXACT_BYTES,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=provider_path.read_bytes(),
    )
    policy_component = RuntimeComponent.from_selected_bytes(
        role=RuntimeComponentRole.PROFILE_POLICY,
        logical_ref=descriptor.evidence_policy_ref,
        canonicalization=Canonicalization.CANONICAL_JSON,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=(
            b'{"policyId":"policy:synthetic.evidence.v0_1"}'
        ),
    )

    class SyntheticBundle:
        @staticmethod
        def component(role, logical_ref):
            components = {
                (
                    RuntimeComponentRole.ADAPTER_SOURCE,
                    profile_runtime_provider._REGISTRY_COMPONENT_REF,
                ): registry_component,
                (
                    registration.component_role,
                    registration.component_ref,
                ): provider_component,
                (
                    RuntimeComponentRole.PROFILE_POLICY,
                    descriptor.evidence_policy_ref,
                ): policy_component,
            }
            return components[(role, logical_ref)]

    store = SimpleNamespace(
        active_descriptor=descriptor,
        require_startup_complete=lambda _operation: None,
        runtime_bundle=SyntheticBundle(),
        get_record=lambda _ref: None,
        registry=ContractRegistry(),
    )

    services = load_profile_runtime_services(
        store,
        registration.package_name,
        descriptor,
        _registrations=(registration,),
    )

    materialized = services.materializer.recompute(None, "farm:synthetic")
    passport = services.output_assembler.passport_view(
        "farm:synthetic",
        "party:synthetic",
    )
    assert materialized["policyRef"] == "policy:synthetic.materialization.v0_1"
    assert materialized["resultShapeFamily"] == "synthetic.operations.v0_1"
    assert passport["viewRef"] == "view:synthetic.passport.v0_1"
    assert services.output_assembler.materializer is services.materializer
    assert services.policy_provider.runtime_component is policy_component
    assert services.registry_reference_family is None
    assert services.registry_reverification.runtime_bundle is None
    assert services.registry_reverification.selected_input_bindings == ()
    assert registration not in profile_runtime_provider._REGISTRATIONS
    assert all(
        "si.ffs" not in value
        for value in (
            services.materialization_specification.policy_ref,
            services.materialization_specification.default_result_shape_family,
            services.output_specification.passport_view.view_ref,
            services.output_specification.document_assembly.view_ref,
            services.manifest_evidence_specification.manifest_id,
            services.manifest_evidence_specification.manifest_filename,
        )
    )

    log = []
    ctx = SimpleNamespace(
        cur=object(),
        store=store,
        runtime_services=services,
        farm_ref="farm:synthetic",
        invalidation_sources=["source:synthetic.claim"],
        trigger_source="source:synthetic.claim",
        materialization_triggered=False,
        sub={
            "syntheticClaimMarker": "certificate:synthetic.runtime.v0_1",
            "payload": {"agronomicIdentityBindingRefs": []},
        },
        event_time="2026-01-01T10:00:00Z",
        captured_at="2026-01-01T10:00:00Z",
        review_route_reasons=[],
        log=lambda gate, outcome, **kwargs: log.append(
            {"gate": gate, "outcome": outcome, **kwargs}
        ),
    )

    assert isinstance(ProfileApplicabilityGate().run(ctx), GatePass)
    assert _run_registry_reverification(ctx) is None
    assert isinstance(MaterializationGate().run(ctx), GatePass)
    assert ctx.materialization_triggered is True
    assert services.materializer.invalidation_calls == [{
        "sourceRefs": ("source:synthetic.claim",),
        "triggerFamily": "BASIS_ADVANCED",
        "triggerSourceRef": "source:synthetic.claim",
        "farmScopeRef": "farm:synthetic",
        "reasonCode": "TRUTH_BASIS_ADVANCED",
    }]
    assert log == [
        {
            "gate": "PACK_PROFILE_APPLICABILITY",
            "outcome": "APPLICABLE",
            "refs": ["contextsnapshot:synthetic.runtime.v0_1"],
        },
        {
            "gate": "CURRENT_STATE_MATERIALIZATION",
            "outcome": "UPDATED",
            "refs": [
                "basis:synthetic.runtime.v0_1",
                "snapshot:synthetic.runtime.v0_1",
            ],
        },
    ]
    request = services.registry_reverification.requests[0]
    inspected = repr((request, materialized, passport, log)).lower()
    assert "si.ffs" not in inspected
    assert "profile_si_ffs" not in inspected
    assert "crop_protection_product" not in inspected
    assert "registrationref" not in inspected
    assert "lookup_by_decision" not in inspected

    certificate_problem = runtime_problem(
        "PRODUCT_BINDING_UNRESOLVED",
        "Certificate review",
        "The profile-local certificate requires review.",
        severity="WARNING",
    )

    def certificate_run(certificate_request):
        assert b"certificate:synthetic.runtime.v0_1" in \
            certificate_request.claim_canonical_bytes
        return RegistryReverificationOutcome(
            RegistryReverificationDisposition.REVIEW_REQUIRED,
            problem=certificate_problem,
        )

    certificate_registry = SimpleNamespace(
        active_profile=descriptor,
        reference_family=None,
        runtime_bundle=None,
        selected_input_bindings=(),
        run=certificate_run,
    )
    ctx.runtime_services = profile_runtime_provider._validate_services(
        replace(services, registry_reverification=certificate_registry),
        descriptor,
        store,
    )
    assert _run_registry_reverification(ctx) is None
    assert ctx.review_route_reasons == [certificate_problem]
    assert ctx.review_route_reasons[0] is not certificate_problem


def test_profile_runtime_registry_rejects_duplicate_identity():
    registration = profile_runtime_provider._REGISTRATIONS[0]

    with pytest.raises(
        ProfileRuntimeError,
        match="registry contains duplicate identities",
    ):
        profile_runtime_provider._registration_for(
            registration.package_name,
            config.ACTIVE_PROFILE,
            (registration, registration),
        )
