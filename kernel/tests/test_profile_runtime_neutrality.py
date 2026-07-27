"""Conformance evidence for the profile-neutral executable-service seam."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from kernel import config
import kernel.profile_runtime_provider as profile_runtime_provider
from kernel.profile_runtime import ProfileRuntimeError
from kernel.profile_runtime_provider import (
    ProfileRuntimeRegistration,
    load_profile_runtime_services,
)
from kernel.runtime_bundle import (
    Canonicalization,
    ContentPlacement,
    RuntimeComponent,
    RuntimeComponentRole,
)


def test_synthetic_second_profile_uses_only_profile_local_services():
    from kernel.tests._synthetic_profile_runtime import (
        build_synthetic_runtime_services,
    )

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
        factory_name="build_synthetic_runtime_services",
        factory_resolver=lambda: build_synthetic_runtime_services,
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
            }
            return components[(role, logical_ref)]

    store = SimpleNamespace(
        require_startup_complete=lambda _operation: None,
        runtime_bundle=SyntheticBundle(),
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
    assert registration not in profile_runtime_provider._REGISTRATIONS
    assert all(
        "si.ffs" not in value
        for value in (
            services.materialization_specification.policy_ref,
            services.materialization_specification.default_result_shape_family,
            services.output_specification.passport_view.view_ref,
            services.output_specification.document_assembly.view_ref,
        )
    )


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
