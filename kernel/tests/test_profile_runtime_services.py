"""test profile runtime services."""
# ruff: noqa: F403, F405

import copy
from inspect import signature

from kernel.problems import runtime_problem
from kernel.profile_runtime_services import (
    ProfileMaterializer,
    RegistryReverificationDisposition,
    RegistryReverificationOutcome,
    RegistryReverificationRequest,
)
from kernel.stages import GatePass, GateRefusal

from kernel.tests._profile_runtime_test_support import *


def test_descriptor_backed_validation_uses_provider_without_config_wrapper(
        fresh_env, monkeypatch):
    store, _, _ = fresh_env

    def fail_config_policy(*_args, **_kwargs):
        raise AssertionError("config-backed validation policy path was called")

    monkeypatch.setattr(profile_policy, "validation_policy", fail_config_policy)

    result = GatePipeline(store).commit(demo.spray_submission(
        f"mp3d-validation-provider:{_uid()}",
        erp_id=f"erp:mp3d.validation.provider.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_descriptor_backed_sufficiency_uses_provider_without_config_wrappers(
        fresh_env, monkeypatch):
    store, _, _ = fresh_env

    def fail_config_policy(*_args, **_kwargs):
        raise AssertionError("config-backed sufficiency policy path was called")

    monkeypatch.setattr(profile_policy, "load_evidence_review_policy",
                        fail_config_policy)
    monkeypatch.setattr(profile_policy, "operation_floor_with_display",
                        fail_config_policy)
    monkeypatch.setattr(profile_policy, "operation_floor_display",
                        fail_config_policy)
    monkeypatch.setattr(profile_policy, "advisory_rules", fail_config_policy)
    monkeypatch.setattr(sufficiency, "build_floor_case", fail_config_policy)
    monkeypatch.setattr(sufficiency, "operation_advisories", fail_config_policy)

    result = GatePipeline(store).commit(demo.spray_submission(
        f"mp3d-sufficiency-provider:{_uid()}",
        erp_id=f"erp:mp3d.sufficiency.provider.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_validation_services_require_explicit_profile_policy():
    with pytest.raises(TypeError):
        validators.CarrierSemanticsValidator()
    with pytest.raises(TypeError):
        validators.ExecutionExtentValidator()
    with pytest.raises(TypeError):
        validators.CodeBindingValidator()


def test_acceptance_sufficiency_uses_descriptor_policy_ref_without_policy_body(
        fresh_env, monkeypatch):
    store, pipeline, _ = fresh_env
    queued = pipeline.commit(demo.spray_submission(
        f"mp3d-accept-queued:{_uid()}",
        erp_id=f"erp:mp3d.accept.queued.{_uid()}",
        confirm=False,
    ))
    assert queued["decisionOutcome"] == "RETAIN_DRAFT"

    def fail_descriptor_policy(*_args, **_kwargs):
        raise AssertionError("acceptance path loaded the full descriptor policy")

    monkeypatch.setattr(profile_policy, "load_evidence_review_policy_for_descriptor",
                        fail_descriptor_policy)

    accepted = pipeline.commit({
        "commitClass": "GOVERNANCE_DECISION",
        "actingPartyRef": demo.FARMER,
        "farmRef": demo.FARM,
        "idempotencyKey": f"mp3d-accept:{_uid()}",
        "decisionTime": "2026-06-10T10:00:00Z",
        "reviewTargetAssertionRef": queued["emittedAssertionRecordRefs"][0],
        "reviewRationale": "self-review of a routine operation claim meeting the floor",
    })

    assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED"
    case = _case_payload(store, accepted)
    assert case["governingPolicyRefs"] == [config.ACTIVE_PROFILE.evidence_policy_ref]
    assert {arg["policyRef"] for arg in case["arguments"]} == {
        config.ACTIVE_PROFILE.evidence_policy_ref}


def test_descriptor_validation_policy_failure_stops_at_validation(
        fresh_env, monkeypatch):
    store, _, _ = fresh_env

    def fail_validation_policy(_provider):
        raise profile_policy.ProfilePolicyError("descriptor validation unavailable")

    monkeypatch.setattr(profile_policy.DescriptorPolicyProvider, "validation_policy",
                        fail_validation_policy)

    result = GatePipeline(store).commit(demo.spray_submission(
        f"mp3d-validation-fail:{_uid()}",
        erp_id=f"erp:mp3d.validation.fail.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    trace = _trace_payload(store, result)
    assert [entry["gate"] for entry in trace["gateSequence"]] == [
        "INGRESS_NORMALIZATION",
        "AUTHORITY",
        "VALIDATION",
    ]
    assert trace["gateSequence"][-1]["outcome"] == "FAIL_PROFILE_POLICY"
    assert "evidenceSufficiencyCaseRef" not in trace


def test_descriptor_sufficiency_policy_failure_happens_after_validation(
        fresh_env, monkeypatch):
    store, _, _ = fresh_env
    validation = profile_policy.validation_policy_for_descriptor(config.ACTIVE_PROFILE)

    monkeypatch.setattr(profile_policy.DescriptorPolicyProvider, "validation_policy",
                        lambda _provider: validation)

    def fail_evidence_policy(_provider, *_args, **_kwargs):
        raise profile_policy.ProfilePolicyError("descriptor floor unavailable")

    monkeypatch.setattr(profile_policy.DescriptorPolicyProvider, "evidence_policy",
                        fail_evidence_policy)

    result = GatePipeline(store).commit(demo.spray_submission(
        f"mp3d-sufficiency-fail:{_uid()}",
        erp_id=f"erp:mp3d.sufficiency.fail.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    trace = _trace_payload(store, result)
    assert [entry["gate"] for entry in trace["gateSequence"]] == [
        "INGRESS_NORMALIZATION",
        "AUTHORITY",
        "VALIDATION",
        "PACK_PROFILE_APPLICABILITY",
        "EVIDENCE_SUFFICIENCY",
    ]
    assert trace["gateSequence"][2]["outcome"] == "PASS"
    assert trace["gateSequence"][-1]["outcome"] == "INSUFFICIENT"


def test_descriptor_compliance_recognized_refs_are_exact():
    provider = profile_policy.DescriptorPolicyProvider(config.ACTIVE_PROFILE)
    assert provider.recognized_rule_refs == \
        frozenset({
            config.ACTIVE_PROFILE.evidence_policy_ref,
            config.ACTIVE_PROFILE.profile_ref,
            config.ACTIVE_PROFILE.pack_ref,
            config.ACTIVE_PROFILE.code_binding_profile_ref,
        })


def test_materializer_requires_committed_store_startup():
    with _fresh_unbootstrapped_store() as store:
        with pytest.raises(
            RuntimeBundleBindingError,
            match="requires completed schema, bundle, and profile startup",
        ):
            Materializer(
                store,
                specification=TEST_MATERIALIZATION_SPECIFICATION,
                context_assembler=context.ContextAssembler(
                    store,
                    active_descriptor=config.ACTIVE_PROFILE,
                ),
                active_descriptor=config.ACTIVE_PROFILE,
            )


def test_context_assembler_missing_context_spine_refuses_direct_use():
    with _fresh_unbootstrapped_store() as store:
        assembler = context.ContextAssembler(
            store,
            active_descriptor=config.ACTIVE_PROFILE,
        )
        with store.tx() as cur:
            with pytest.raises(
                context.ContextNotReconstructible,
                match="context spine not bootstrapped",
            ):
                assembler.assemble(cur, demo.FARM)


def test_api_startup_refuses_non_exact_selected_profile_instance():
    def mutate(_profile, _activation, artifact):
        artifact["activeArtifactRefs"] = [
            ref for ref in artifact["activeArtifactRefs"]
            if ref != config.ACTIVE_PROFILE.evidence_policy_ref
        ]

    with _preseeded_dirty_spine_store(mutate) as store:
        from kernel.legacy_m1.api import create_test_app

        with pytest.raises(
            context.ContextNotReconstructible,
            match="not the exact selected contract and payload",
        ):
            create_test_app(store, oidc=None)


def test_product_register_boundary_remains_single_active_si_runtime():
    assert config.ACTIVE_PROFILE_PACKAGE_NAMES == ("profile_si_ffs",)
    assert config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES == ("profile_si_ffs",)
    assert config.ACTIVE_PROFILE_SELECTION.profile_package_names == ("profile_si_ffs",)
    assert context.SI_REFERENCE_BINDINGS == \
        context.SIReferenceBindings.from_runtime_descriptor(config.ACTIVE_PROFILE)
    assert context.REGSR_SNAPSHOT_PREFIX == config.ACTIVE_PROFILE.reference_family(
        "si.uvhvvr.ffs-reg").snapshot_prefix
    assert context.REGSR_DATA_FAMILY == config.ACTIVE_PROFILE.reference_family(
        "si.uvhvvr.ffs-reg").data_family
    assert config.SHIPPED_REGSR_SNAPSHOT_REF == config.ACTIVE_PROFILE.reference_family(
        "si.uvhvvr.ffs-reg").shipped_snapshot_ref


def test_product_register_uses_explicit_si_reference_bindings(tmp_path):
    descriptor, artifact_path, decision = _custom_si_descriptor_with_regsr_artifact(
        tmp_path)
    bindings = context.SIReferenceBindings.from_descriptor(descriptor)
    register = context.ProductRegister(bindings)

    assert bindings.regsr_shipped_artifact_path == artifact_path
    assert register.bindings == bindings
    assert register.lookup_by_decision(
        bindings.regsr_shipped_snapshot_ref,
        decision,
    ) is not None
    assert register.has_snapshot(bindings.regsr_shipped_snapshot_ref)
    assert not register.has_snapshot(config.SHIPPED_REGSR_SNAPSHOT_REF)


def test_product_register_load_from_store_uses_only_selected_source_data(
        tmp_path):
    descriptor, _, constructor_decision = _custom_si_descriptor_with_regsr_artifact(
        tmp_path)
    bindings = context.SIReferenceBindings.from_descriptor(descriptor)
    bundle_decision = f"U9{_uid()[:4]}-50/26/b"
    artifact_ref = "artifact:bundle-selected-regsr.json"

    class FakeStore:
        active_descriptor = descriptor
        runtime_bundle = object()
        requested_prefixes: list[str] = []

        def selected_reference_source_data(self, prefix):
            self.requested_prefixes.append(prefix)
            return [{
                "snapshot_ref": f"{bindings.regsr_snapshot_prefix}.bundle",
                "artifact_ref": artifact_ref,
                "source_digest": "sha256:" + "a" * 64,
                "payload": _regsr_artifact(decision=bundle_decision),
            }]

    store = FakeStore()
    register = context.ProductRegister()
    register.load_from_store(store)

    assert store.requested_prefixes == [bindings.regsr_snapshot_prefix]
    assert register.runtime_bundle is store.runtime_bundle
    assert register.selected_input_bindings == ((
        f"{bindings.regsr_snapshot_prefix}.bundle",
        artifact_ref,
        "sha256:" + "a" * 64,
    ),)
    assert register.bindings == context.SIReferenceBindings.from_runtime_descriptor(
        descriptor
    )
    assert register.lookup_by_decision(
        f"{bindings.regsr_snapshot_prefix}.bundle",
        bundle_decision,
    ) is not None
    assert not register.has_snapshot(bindings.regsr_shipped_snapshot_ref)
    assert not register.has_snapshot(config.SHIPPED_REGSR_SNAPSHOT_REF)
    assert register.lookup_by_decision(
        bindings.regsr_shipped_snapshot_ref,
        constructor_decision,
    ) is None


def test_gate_pipeline_threads_si_reference_bindings(fresh_env):
    _store, pipeline, _ = fresh_env
    sub = demo.spray_submission(
        f"issue127b-binding-context:{_uid()}",
        erp_id=f"erp:issue127b.binding.{_uid()}",
        confirm=True,
    )

    ctx = pipeline._new_context(None, sub, parse_ingress_header(sub))

    services = pipeline.runtime_services
    revalidator = services.registry_reverification
    regsr_family = config.ACTIVE_PROFILE.reference_family(
        context.SI_REGSR_FAMILY_ID
    )
    assert services.registry_reference_family is regsr_family
    assert revalidator.reference_family is regsr_family
    assert revalidator.active_profile is config.ACTIVE_PROFILE
    assert revalidator.runtime_bundle is _store.runtime_bundle
    assert revalidator.product_lookup.bindings.regsr_snapshot_prefix == \
        revalidator.snapshot_prefix
    assert ctx.runtime_services is services


def test_registry_reverification_requires_exact_si_family():
    descriptor = config.ACTIVE_PROFILE
    family = descriptor.reference_family(context.SI_REGSR_FAMILY_ID)
    runtime_bundle = object()
    lookup = SimpleNamespace(
        bindings=context.SIReferenceBindings.from_runtime_descriptor(descriptor),
        runtime_bundle=runtime_bundle,
        selected_input_bindings=(("snapshot", "artifact", "digest"),),
        lookup_by_decision=lambda *_args: None,
    )

    validator = validators.RegistryReverificationValidator(
        active_profile=descriptor,
        reference_family=family,
        product_lookup=lookup,
    )

    assert validator.active_profile is descriptor
    assert validator.reference_family is family
    assert validator.runtime_bundle is runtime_bundle
    assert validator.selected_input_bindings is lookup.selected_input_bindings
    for wrong_family_id in (
        context.SI_GERK_FAMILY_ID,
        context.SI_FFSNAPRAVE_FAMILY_ID,
    ):
        with pytest.raises(ProfileRuntimeError, match="exact REGSR family"):
            validators.RegistryReverificationValidator(
                active_profile=descriptor,
                reference_family=descriptor.reference_family(wrong_family_id),
                product_lookup=lookup,
            )


def test_materializer_uses_active_descriptor_for_context_and_policy_freshness(
        fresh_env):
    store, pipeline, _ = fresh_env

    assert pipeline.runtime_services.materializer.active_profile is \
        config.ACTIVE_PROFILE
    assert pipeline.runtime_services.materializer.context.active_profile is \
        config.ACTIVE_PROFILE

    explicit = load_profile_runtime_services(
        store,
        store.active_profile_package_name,
        config.ACTIVE_PROFILE,
    ).materializer
    vector = explicit.build_freshness_vector(
        {"materializationKeyId": "matkey:mp3d.policy"},
        "matbasis:mp3d.policy",
        "contextsnapshot:mp3d.policy",
        [],
    )

    assert explicit.context.active_profile is config.ACTIVE_PROFILE
    assert _policy_dimension(vector) == {
        "dimensionFamily": "RULE_EVIDENCE_POLICY",
        "sourceRef": config.ACTIVE_PROFILE.evidence_policy_ref,
        "observedVersionRef": config.ACTIVE_PROFILE.evidence_policy_ref,
    }


def test_materializer_dependency_index_uses_bound_policy_and_invalidates(fresh_env):
    store, pipeline, _ = fresh_env
    policy_ref = store.active_descriptor.evidence_policy_ref
    materializer = pipeline.runtime_services.materializer

    with store.tx() as cur:
        materialized = materializer.recompute(cur, demo.FARM)
    key_digest = materialized["materializationKey"]["materializationKeyId"]

    with store.conn.cursor() as cur:
        cur.execute(
            "SELECT dependency_source_ref FROM derived_dependency_index "
            "WHERE key_digest = %s "
            "AND dependency_source_family = 'RULE_EVIDENCE_POLICY'",
            (key_digest,),
        )
        policy_dependencies = {row["dependency_source_ref"] for row in cur.fetchall()}
        cur.execute(
            "SELECT freshness FROM derived_materialization "
            "WHERE key_digest = %s AND superseded_by IS NULL",
            (key_digest,),
        )
        assert cur.fetchone()["freshness"] == "FRESH"

    assert policy_dependencies == {policy_ref}

    with store.tx() as cur:
        marked = materializer.invalidate_for_sources(
            cur,
            [policy_ref],
            trigger_family="POLICY_CHANGED",
            trigger_source_ref=policy_ref,
            farm_scope_ref=demo.FARM,
            reason_code="POLICY_CHANGED",
        )

    assert marked == 1
    with store.conn.cursor() as cur:
        cur.execute(
            "SELECT freshness FROM derived_materialization "
            "WHERE key_digest = %s AND superseded_by IS NULL",
            (key_digest,),
        )
        assert cur.fetchone()["freshness"] == "STALE"


def test_issue_159_default_pipeline_selects_registered_si_provider(fresh_env):
    store, pipeline, _ = fresh_env

    assert pipeline.runtime_services.descriptor is store.active_descriptor
    assert pipeline.runtime_services.policy_provider.descriptor is \
        store.active_descriptor


def test_issue_159_si_submission_behavior_remains_assertion_equivalent(
        fresh_env):
    store, default_pipeline, _ = fresh_env
    explicit_pipeline = GatePipeline(
        store,
        active_descriptor=config.ACTIVE_PROFILE,
    )

    default = default_pipeline.commit(demo.spray_submission(
        f"issue159-default:{_uid()}",
        erp_id=f"erp:issue159.default.{_uid()}",
        confirm=True,
    ))
    explicit = explicit_pipeline.commit(demo.spray_submission(
        f"issue159-explicit:{_uid()}",
        erp_id=f"erp:issue159.explicit.{_uid()}",
        confirm=True,
    ))

    assert default["decisionOutcome"] == explicit["decisionOutcome"] == \
        "PROMOTE_ACCEPTED"
    assert default["problems"] == explicit["problems"] == []
    assert [
        entry["gate"] for entry in _trace_payload(store, default)["gateSequence"]
    ] == [
        entry["gate"] for entry in _trace_payload(store, explicit)["gateSequence"]
    ]


def test_issue_159_route_uses_composition_root_services(fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store)
    result = pipeline.commit(demo.spray_submission(
        f"issue159-route:{_uid()}",
        erp_id=f"erp:issue159.route.{_uid()}",
        confirm=True,
    ))
    trace = _trace_payload(store, result)

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert result["problems"] == []
    assert any(
        entry["outcome"] == "PROFILE_ROUTE_PASS"
        for entry in trace["gateSequence"]
    )
    assert trace["gateSequence"][-1]["gate"] == "CURRENT_STATE_MATERIALIZATION"


def test_issue_159_unregistered_identity_cannot_construct_runtime(fresh_env):
    store, _, _ = fresh_env

    with pytest.raises(
        ProfileRuntimeError,
        match="no executable runtime is registered",
    ):
        load_profile_runtime_services(
            store,
            "profile_unregistered",
            config.ACTIVE_PROFILE,
        )


def test_issue_159_unregistered_route_refuses_without_si_fallback(fresh_env):
    store, _, _ = fresh_env
    package_name = "profile_nl_go_glmc7_2026"
    pipeline = _route_pipeline(
        store,
        routes=[_si_route(profile_package_name=package_name)],
        registry=_route_registry(enabled=("profile_si_ffs", package_name)),
        selected=("profile_si_ffs", package_name),
    )

    result = pipeline.commit(demo.spray_submission(
        f"issue159-unregistered-route:{_uid()}",
        erp_id=f"erp:issue159.unregistered.route.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert _trace_payload(store, result)["gateSequence"][-1]["outcome"] == \
        "PROFILE_ROUTE_REFUSE"


def test_issue_159_descriptor_runtime_never_uses_legacy_policy(
        fresh_env, monkeypatch):
    store, _, _ = fresh_env

    def fail_legacy_policy(*_args, **_kwargs):
        raise AssertionError("legacy config-backed policy executed")

    monkeypatch.setattr(profile_policy, "validation_policy", fail_legacy_policy)
    monkeypatch.setattr(
        profile_policy,
        "load_evidence_review_policy",
        fail_legacy_policy,
    )

    result = GatePipeline(store).commit(demo.spray_submission(
        f"issue159-no-legacy:{_uid()}",
        erp_id=f"erp:issue159.no.legacy.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_issue_159_descriptor_discovery_does_not_register_provider():
    descriptor_registry = _route_registry()

    assert (
        "profile_nl_go_glmc7_2026"
        in descriptor_registry.discoverable_package_names
    )
    with pytest.raises(ProfileRuntimeError, match="no executable runtime"):
        profile_runtime_provider._registration_for(
            "profile_nl_go_glmc7_2026",
            config.ACTIVE_PROFILE,
        )


def test_issue_159_rs_remains_design_only_and_unexecutable(fresh_env):
    store, _, _ = fresh_env
    rs_root = config.PACKAGE_ROOT / "profile_rs_organic_crop"

    assert rs_root.is_dir()
    assert not (rs_root / DESCRIPTOR_FILENAME).exists()
    with pytest.raises(
        ProfileRuntimeError,
        match="no executable runtime is registered",
    ):
        load_profile_runtime_services(
            store,
            "profile_rs_organic_crop",
            config.ACTIVE_PROFILE,
        )


def test_issue_159_provider_source_component_is_required():
    class MissingBundle:
        @staticmethod
        def component(_role, _logical_ref):
            raise RuntimeBundleError("missing provider source")

    store = SimpleNamespace(
        require_startup_complete=lambda _operation: None,
        runtime_bundle=MissingBundle(),
    )

    with pytest.raises(
        ProfileRuntimeError,
        match="registered runtime source .* is unavailable",
    ):
        load_profile_runtime_services(
            store,
            config.ACTIVE_PROFILE_PACKAGE_NAME,
            config.ACTIVE_PROFILE,
        )


def test_issue_159_provider_bytes_are_verified_before_import(monkeypatch):
    registration = profile_runtime_provider._REGISTRATIONS[0]
    registry_bytes = Path(profile_runtime_provider.__file__).read_bytes()
    registry_component = RuntimeComponent.from_selected_bytes(
        role=RuntimeComponentRole.ADAPTER_SOURCE,
        logical_ref=profile_runtime_provider._REGISTRY_COMPONENT_REF,
        canonicalization=Canonicalization.EXACT_BYTES,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=registry_bytes,
    )
    mismatched_component = RuntimeComponent.from_selected_bytes(
        role=registration.component_role,
        logical_ref=registration.component_ref,
        canonicalization=Canonicalization.EXACT_BYTES,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=b"mismatched provider source",
    )

    class MismatchedBundle:
        @staticmethod
        def component(_role, logical_ref):
            if logical_ref == profile_runtime_provider._REGISTRY_COMPONENT_REF:
                return registry_component
            return mismatched_component

    store = SimpleNamespace(
        require_startup_complete=lambda _operation: None,
        runtime_bundle=MismatchedBundle(),
    )

    def load_must_not_run(*_args):
        raise AssertionError("provider loaded before its bytes were verified")

    monkeypatch.setattr(
        profile_runtime_provider,
        "_load_factory",
        load_must_not_run,
    )
    with pytest.raises(ProfileRuntimeError, match="differs from"):
        load_profile_runtime_services(
            store,
            registration.package_name,
            config.ACTIVE_PROFILE,
        )


def test_issue_159_factory_refuses_module_loaded_before_trusted_admission(
    tmp_path,
    monkeypatch,
):
    module_name = f"ofarm_test_runtime_provider_{_uid()}"
    source_path = tmp_path / "runtime_provider.py"
    verified_bytes = (
        b"def build(_store, _descriptor):\n"
        b"    return 'verified provider bytes'\n"
    )
    source_path.write_bytes(verified_bytes)
    registration = replace(
        profile_runtime_provider._REGISTRATIONS[0],
        source_path=str(source_path),
        factory_module=module_name,
        factory_name="build",
        factory_resolver=lambda: cached.build,
    )
    cached = SimpleNamespace(build=lambda _store, _descriptor: "cached module")
    monkeypatch.setitem(sys.modules, module_name, cached)

    with pytest.raises(
        ProfileRuntimeError,
        match="runtime factory module .* is unavailable",
    ):
        profile_runtime_provider._load_factory(
            registration,
            source_path,
            verified_bytes,
        )


def test_issue_159_composition_returns_fresh_service_graphs(fresh_env):
    store, first, _ = fresh_env
    second = GatePipeline(store)

    assert first.runtime_services is not second.runtime_services
    assert first.runtime_services.policy_provider is not \
        second.runtime_services.policy_provider
    assert first.runtime_services.context_assembler is not \
        second.runtime_services.context_assembler
    assert first.runtime_services.materializer is not \
        second.runtime_services.materializer
    assert first.runtime_services.registry_reverification.product_lookup is not \
        second.runtime_services.registry_reverification.product_lookup


def test_issue_159_composition_rejects_missing_required_service(
        fresh_env, monkeypatch):
    store, _, _ = fresh_env

    def incomplete_factory(_store, descriptor):
        complete = (
            profile_runtime_provider._resolve_si_factory()(
                _store,
                descriptor,
            )
        )
        return replace(complete, policy_provider=None)

    monkeypatch.setattr(
        profile_runtime_provider,
        "_load_factory",
        lambda _registration, _path, _source: incomplete_factory,
    )
    with pytest.raises(ProfileRuntimeError, match="incomplete or mismatched"):
        load_profile_runtime_services(
            store,
            config.ACTIVE_PROFILE_PACKAGE_NAME,
            config.ACTIVE_PROFILE,
        )


def test_composition_rejects_cross_profile_service_binding(
        fresh_env, monkeypatch):
    store, _, _ = fresh_env

    def mismatched_factory(_store, descriptor):
        services = (
            profile_runtime_provider._resolve_si_factory()(
                _store,
                descriptor,
            )
        )
        services.output_assembler.active_profile = replace(
            descriptor,
            profile_ref="profile:synthetic.mismatch.v0_1",
        )
        return services

    monkeypatch.setattr(
        profile_runtime_provider,
        "_load_factory",
        lambda _registration, _path, _source: mismatched_factory,
    )
    with pytest.raises(
        ProfileRuntimeError,
        match="different profile bindings",
    ):
        load_profile_runtime_services(
            store,
            config.ACTIVE_PROFILE_PACKAGE_NAME,
            config.ACTIVE_PROFILE,
        )


def test_composition_requires_trusted_manifest_evidence_inputs(
        fresh_env, monkeypatch):
    store, _, _ = fresh_env

    def untrusted_factory(_store, descriptor):
        services = profile_runtime_provider._resolve_si_factory()(
            _store,
            descriptor,
        )
        return replace(services, manifest_evidence_specification=object())

    monkeypatch.setattr(
        profile_runtime_provider,
        "_load_factory",
        lambda _registration, _path, _source: untrusted_factory,
    )
    with pytest.raises(ProfileRuntimeError, match="incomplete or mismatched"):
        load_profile_runtime_services(
            store,
            config.ACTIVE_PROFILE_PACKAGE_NAME,
            config.ACTIVE_PROFILE,
        )


def test_issue_159_service_bundle_has_no_optional_slots():
    with pytest.raises(TypeError):
        ProfileRuntimeServices(descriptor=config.ACTIVE_PROFILE)


def _runtime_table_counts(store):
    tables = (
        "kernel_record",
        "kernel_edge",
        "kernel_gate_log",
        "kernel_idempotency",
        "derived_materialization",
        "derived_dependency_index",
        "runtime_trace",
    )
    with store.conn.cursor() as cur:
        return {
            table: cur.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            for table in tables
        }


def _fault_runtime_graph(services, fault, store):
    descriptor = services.descriptor
    if fault == "signature":
        services.materializer.recompute = (
            lambda _cur, _farm, *, twin="COMPLIANCE", time_policy=None: {}
        )
    elif fault == "policy_component":
        services.policy_provider.runtime_component = replace(
            services.policy_provider.runtime_component
        )
    elif fault == "path_policy":
        services.policy_provider.runtime_component = None
    elif fault == "policy_descriptor":
        services.policy_provider.descriptor = replace(descriptor)
    elif fault == "policy_ref":
        services.policy_provider.policy_ref = "policy:foreign"
    elif fault == "rule_refs":
        services.policy_provider.recognized_rule_refs = frozenset()
    elif fault == "context_store":
        services.context_assembler.store = SimpleNamespace(
            active_descriptor=descriptor,
            runtime_bundle=store.runtime_bundle,
        )
    elif fault == "context_descriptor":
        services.context_assembler.active_profile = replace(descriptor)
    elif fault == "materializer_store":
        services.materializer.store = object()
    elif fault == "materializer_descriptor":
        services.materializer.active_profile = replace(descriptor)
    elif fault == "materializer_spec":
        services.materializer.specification = replace(
            services.materialization_specification
        )
    elif fault == "materializer_context":
        services.materializer.context = copy.copy(services.context_assembler)
    elif fault == "output_store":
        services.output_assembler.store = object()
    elif fault == "output_descriptor":
        services.output_assembler.active_profile = replace(descriptor)
    elif fault == "output_spec":
        services.output_assembler.specification = replace(
            services.output_specification
        )
    elif fault == "output_materializer":
        services.output_assembler.materializer = copy.copy(services.materializer)
    elif fault == "registry_descriptor":
        services.registry_reverification.active_profile = replace(descriptor)
    elif fault == "registry_family":
        services.registry_reverification.reference_family = descriptor.reference_family(
            context.SI_GERK_FAMILY_ID
        )
    elif fault == "registry_bundle":
        services.registry_reverification.runtime_bundle = object()
    elif fault == "registry_inputs":
        services.registry_reverification.selected_input_bindings = (
            ("snapshot:foreign", "artifact:foreign", "sha256:" + "a" * 64),
        )
    elif fault == "outer_family_copy":
        services = replace(
            services,
            registry_reference_family=replace(services.registry_reference_family),
        )
    return services


@pytest.mark.parametrize("fault", (
    "signature", "policy_component", "path_policy", "policy_descriptor",
    "policy_ref", "rule_refs", "context_store", "context_descriptor",
    "materializer_store", "materializer_descriptor", "materializer_spec",
    "materializer_context", "output_store", "output_descriptor", "output_spec",
    "output_materializer", "registry_descriptor", "registry_family",
    "registry_bundle", "registry_inputs", "outer_family_copy",
))
def test_issue_160_both_composition_paths_reject_cross_wires(
    fresh_env,
    monkeypatch,
    fault,
):
    store, pipeline, _ = fresh_env
    descriptor = store.active_descriptor
    factory = profile_runtime_provider._resolve_si_factory()
    explicit = _fault_runtime_graph(factory(store, descriptor), fault, store)
    transactions = 0
    serialized_tx = store.serialized_tx

    def counted_transaction():
        nonlocal transactions
        transactions += 1
        return serialized_tx()

    monkeypatch.setattr(store, "serialized_tx", counted_transaction)
    with pytest.raises(ProfileRuntimeError):
        GatePipeline(store, runtime_services=explicit)

    def malformed_factory(provider_store, provider_descriptor):
        graph = factory(provider_store, provider_descriptor)
        return _fault_runtime_graph(graph, fault, provider_store)

    monkeypatch.setattr(
        profile_runtime_provider,
        "_load_factory",
        lambda *_args: malformed_factory,
    )
    with pytest.raises(ProfileRuntimeError):
        load_profile_runtime_services(
            store,
            config.ACTIVE_PROFILE_PACKAGE_NAME,
            descriptor,
        )
    assert transactions == 0
    assert pipeline.runtime_services.descriptor is descriptor


@pytest.mark.parametrize("candidate", ("lookalike", "copied_descriptor", "bad_spec"))
def test_issue_160_injected_outer_types_fail_before_pipeline(fresh_env, candidate):
    store, pipeline, _ = fresh_env
    services = pipeline.runtime_services
    if candidate == "lookalike":
        services = SimpleNamespace(**{
            field: getattr(services, field)
            for field in services.__dataclass_fields__
        })
    elif candidate == "copied_descriptor":
        services = replace(services, descriptor=replace(services.descriptor))
    else:
        services = replace(services, materialization_specification=object())
    with pytest.raises(ProfileRuntimeError):
        GatePipeline(store, runtime_services=services)


def test_issue_160_materializer_protocol_declares_complete_calls():
    value = object()
    signature(ProfileMaterializer.invalidate_for_sources).bind(
        value,
        value,
        ["source:test"],
        trigger_family="BASIS_ADVANCED",
        trigger_source_ref="source:test",
        farm_scope_ref="farm:test",
        reason_code="TRUTH_BASIS_ADVANCED",
    )
    signature(ProfileMaterializer.recompute).bind(
        value,
        value,
        "farm:test",
        twin="COMPLIANCE",
        use_class="OPERATIONAL_DASHBOARD",
        time_policy={"policyType": "NOW"},
    )


@pytest.mark.parametrize("result", (
    {},
    {"contextSnapshotId": ""},
    {"contextSnapshotId": object()},
))
def test_issue_160_malformed_applicability_rolls_back_before_success(
    fresh_env,
    result,
):
    store, pipeline, _ = fresh_env
    before = _runtime_table_counts(store)
    pipeline.runtime_services.context_assembler.assemble = lambda *_args, **_kw: result
    with pytest.raises(ProfileRuntimeError, match="contextSnapshotId"):
        pipeline.commit(demo.spray_submission(
            f"issue160-context:{_uid()}",
            erp_id=f"erp:issue160.context.{_uid()}",
            confirm=True,
        ))
    assert _runtime_table_counts(store) == before


@pytest.mark.parametrize("result", (
    {},
    {"basisRef": "", "snapshotRef": "snapshot:test"},
    {"basisRef": object(), "snapshotRef": "snapshot:test"},
    {"basisRef": "basis:test"},
    {"basisRef": "basis:test", "snapshotRef": ""},
    {"basisRef": "basis:test", "snapshotRef": object()},
))
def test_issue_160_malformed_materialization_rolls_back_before_success(
    fresh_env,
    result,
):
    store, pipeline, _ = fresh_env
    before = _runtime_table_counts(store)
    pipeline.runtime_services.materializer.recompute = lambda *_args, **_kw: result
    with pytest.raises(ProfileRuntimeError, match="materialization result"):
        pipeline.commit(demo.spray_submission(
            f"issue160-materialization:{_uid()}",
            erp_id=f"erp:issue160.materialization.{_uid()}",
            confirm=True,
        ))
    assert _runtime_table_counts(store) == before


def _pipeline_with_registry_run(store, services, run):
    registry_service = copy.copy(services.registry_reverification)
    registry_service.run = run
    return GatePipeline(
        store,
        runtime_services=replace(
            services,
            registry_reverification=registry_service,
        ),
    )


def _invalid_registry_run(case):
    def run(_request):
        if case == "exception":
            raise RuntimeError("provider failure")
        if case == "none":
            return None
        if case == "mapping":
            return {}
        if case == "falsey":
            return False
        if case == "gate_pass":
            return GatePass()
        if case == "gate_refusal":
            return GateRefusal("VALIDATION", "FAIL", "RETAIN_DRAFT", [])
        if case == "unknown":
            return RegistryReverificationOutcome("UNKNOWN")
        if case == "no_effect_payload":
            return RegistryReverificationOutcome(
                RegistryReverificationDisposition.NO_EFFECT,
                rationale="unexpected",
            )
        if case == "reverified_empty":
            return RegistryReverificationOutcome(
                RegistryReverificationDisposition.REVERIFIED
            )
        problem = runtime_problem(
            "PRODUCT_BINDING_UNRESOLVED",
            "Registry review",
            "Synthetic registry review.",
            severity="WARNING",
        )
        if case == "unknown_reason":
            problem["reasonCode"] = "UNKNOWN_PROVIDER_REASON"
        disposition = (
            RegistryReverificationDisposition.REFUSED
            if case == "refused_warning"
            else RegistryReverificationDisposition.REVIEW_REQUIRED
        )
        return RegistryReverificationOutcome(disposition, problem=problem)
    return run


@pytest.mark.parametrize("case", (
    "exception", "none", "mapping", "falsey", "gate_pass", "gate_refusal",
    "unknown", "no_effect_payload", "reverified_empty", "unknown_reason",
    "refused_warning",
))
def test_issue_160_malformed_registry_outcome_rolls_back(fresh_env, case):
    store, pipeline, _ = fresh_env
    candidate = _pipeline_with_registry_run(
        store,
        pipeline.runtime_services,
        _invalid_registry_run(case),
    )
    before = _runtime_table_counts(store)
    with pytest.raises(ProfileRuntimeError):
        candidate.commit(demo.spray_submission(
            f"issue160-registry-invalid:{_uid()}",
            erp_id=f"erp:issue160.registry.invalid.{_uid()}",
            confirm=True,
        ))
    assert _runtime_table_counts(store) == before


def _legacy_registry_mutation(case):
    def run(request):
        if case == "durable_log":
            request.store.log_gate(request.cur, "request", "VALIDATION", "PASS")
        elif case == "sequence":
            request.gate_sequence.append({"outcome": "REGISTRY_REVERIFIED"})
        elif case == "log_remove":
            request.log("VALIDATION", "REGISTRY_REVERIFIED")
            request.gate_sequence.pop()
        elif case == "review_append":
            request.review_route_reasons.append("malformed")
        else:
            request.review_route_reasons[0]["detail"] = "mutated"
        return RegistryReverificationOutcome(
            RegistryReverificationDisposition.NO_EFFECT
        )
    return run


@pytest.mark.parametrize("case", (
    "durable_log", "sequence", "log_remove", "review_append", "review_prefix",
))
def test_issue_160_registry_request_denies_legacy_mutation(fresh_env, case):
    store, pipeline, _ = fresh_env
    candidate = _pipeline_with_registry_run(
        store,
        pipeline.runtime_services,
        _legacy_registry_mutation(case),
    )
    before = _runtime_table_counts(store)
    with pytest.raises(ProfileRuntimeError, match="service failed"):
        candidate.commit(demo.spray_submission(
            f"issue160-registry-mutation:{_uid()}",
            erp_id=f"erp:issue160.registry.mutation.{_uid()}",
            confirm=True,
        ))
    assert _runtime_table_counts(store) == before


def test_issue_160_valid_registry_outcomes_are_code_owned(fresh_env):
    store, pipeline, _ = fresh_env
    services = pipeline.runtime_services
    reverified = _pipeline_with_registry_run(
        store,
        services,
        lambda _request: RegistryReverificationOutcome(
            RegistryReverificationDisposition.REVERIFIED,
            rationale="synthetic identity reverification",
        ),
    ).commit(demo.spray_submission(
        f"issue160-reverified:{_uid()}",
        erp_id=f"erp:issue160.reverified.{_uid()}",
        confirm=True,
    ))
    assert reverified["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert any(
        entry["outcome"] == "REGISTRY_REVERIFIED"
        for entry in _trace_payload(store, reverified)["gateSequence"]
    )

    review_problem = runtime_problem(
        "PRODUCT_BINDING_UNRESOLVED",
        "Certificate review",
        "The certificate requires profile-owned review.",
        severity="WARNING",
    )
    reviewed = _pipeline_with_registry_run(
        store,
        services,
        lambda _request: RegistryReverificationOutcome(
            RegistryReverificationDisposition.REVIEW_REQUIRED,
            problem=review_problem,
        ),
    ).commit(demo.spray_submission(
        f"issue160-reviewed:{_uid()}",
        erp_id=f"erp:issue160.reviewed.{_uid()}",
        confirm=True,
    ))
    review_problem["detail"] = "provider mutation after return"
    assert reviewed["decisionOutcome"] == "REQUIRE_REVIEW"
    assert reviewed["problems"][0]["detail"] == \
        "The certificate requires profile-owned review."

    refused_problem = runtime_problem(
        "PRODUCT_BINDING_UNRESOLVED",
        "Registry refusal",
        "The registry result cannot support this claim.",
    )
    refused = _pipeline_with_registry_run(
        store,
        services,
        lambda _request: RegistryReverificationOutcome(
            RegistryReverificationDisposition.REFUSED,
            problem=refused_problem,
        ),
    ).commit(demo.spray_submission(
        f"issue160-refused:{_uid()}",
        erp_id=f"erp:issue160.refused.{_uid()}",
        confirm=True,
    ))
    assert refused["decisionOutcome"] == "RETAIN_DRAFT"
    assert _trace_payload(store, refused)["gateSequence"][-1]["outcome"] == \
        "FAIL_REFERENCE_RESOLUTION"


@pytest.mark.parametrize("field,value", (
    ("claim_canonical_bytes", b""),
    ("resolved_binding_canonical_bytes", []),
    ("current_reference_snapshot_ref", ""),
    ("event_time", ""),
))
def test_issue_160_registry_request_requires_exact_immutable_fields(field, value):
    values = {
        "claim_canonical_bytes": b"{}",
        "resolved_binding_canonical_bytes": (),
        "current_reference_snapshot_ref": None,
        "event_time": "2026-01-01T00:00:00Z",
    }
    values[field] = value
    with pytest.raises(ValueError):
        RegistryReverificationRequest(**values)
