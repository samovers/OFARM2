"""test profile runtime descriptor."""
# ruff: noqa: F403, F405

from kernel.tests._profile_runtime_test_support import *


def test_descriptor_drives_existing_si_config_without_tenant_binding():
    raw = _base_doc()
    assert "tenantRef" not in raw
    assert "profilePackageRoot" not in raw
    assert config.TENANT_REF == "tenant:si.ffs.pilot.demo"

    active = config.ACTIVE_PROFILE
    assert active.profile_ref == config.PROFILE_REF
    assert active.pack_ref == config.PACK_REF
    assert active.evidence_policy_ref == config.EVIDENCE_POLICY_REF
    assert active.code_binding_profile_ref == config.CODE_BINDING_PROFILE_REF
    assert active.evidence_policy_path == config.EVIDENCE_POLICY_PATH
    assert active.context_snapshot_id_prefix == "contextsnapshot:si.ffs"
    assert context.PROFILE_INSTANCE_FILES == list(active.profile_instance_files)
    assert context.REGSR_SNAPSHOT_PREFIX == active.reference_family(
        "si.uvhvvr.ffs-reg").snapshot_prefix
    assert context.GERK_SNAPSHOT_PREFIX == active.reference_family(
        "si.mkgp.gerk-layer").snapshot_prefix
    assert context.SI_REFERENCE_BINDINGS.ffsnaprave_snapshot_prefix == \
        active.reference_family("si.uvhvvr.ffs-naprave").snapshot_prefix
    assert config.SHIPPED_REGSR_SNAPSHOT_REF == active.reference_family(
        "si.uvhvvr.ffs-reg").shipped_snapshot_ref


def test_si_reference_bindings_are_descriptor_derived():
    active = config.ACTIVE_PROFILE
    bindings = context.SIReferenceBindings.from_descriptor(active)
    regsr = active.reference_family("si.uvhvvr.ffs-reg")
    gerk = active.reference_family("si.mkgp.gerk-layer")
    ffsnaprave = active.reference_family("si.uvhvvr.ffs-naprave")
    shipped_snapshot = _profile_instance_payload(
        "referenceSnapshotId",
        regsr.shipped_snapshot_ref,
    )
    artifact_refs = [
        ref.split(":", 1)[1]
        for ref in shipped_snapshot["sourceArtifactRefs"]
        if ref.startswith("artifact:")
    ]
    assert len(artifact_refs) == 1

    assert bindings.si_profile_root == active.profile_root.resolve()
    assert bindings.regsr_snapshot_prefix == regsr.snapshot_prefix
    assert bindings.regsr_data_family == regsr.data_family
    assert bindings.regsr_shipped_snapshot_ref == regsr.shipped_snapshot_ref
    assert bindings.regsr_shipped_artifact_path == (
        active.profile_root / "examples" / artifact_refs[0]
    ).resolve()
    assert bindings.gerk_snapshot_prefix == gerk.snapshot_prefix
    assert bindings.gerk_data_family == gerk.data_family
    assert bindings.gerk_shipped_snapshot_ref == gerk.shipped_snapshot_ref
    assert bindings.ffsnaprave_snapshot_prefix == ffsnaprave.snapshot_prefix
    assert bindings.ffsnaprave_data_family == ffsnaprave.data_family


def test_si_reference_binding_compatibility_aliases_are_binding_backed():
    bindings = context.SI_REFERENCE_BINDINGS

    assert bindings == context.SIReferenceBindings.from_runtime_descriptor(
        config.ACTIVE_PROFILE
    )
    assert bindings.si_profile_root is None
    assert bindings.regsr_shipped_artifact_path is None
    assert context.REGSR_SNAPSHOT_PREFIX == bindings.regsr_snapshot_prefix
    assert context.GERK_SNAPSHOT_PREFIX == bindings.gerk_snapshot_prefix
    assert context.REGSR_DATA_FAMILY == bindings.regsr_data_family


def test_config_declares_explicit_single_active_profile_selection(monkeypatch):
    assert config.DEFAULT_ACTIVE_PROFILE_PACKAGE_NAMES == ("profile_si_ffs",)
    assert config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES == ("profile_si_ffs",)
    assert config.ACTIVE_PROFILE_PACKAGE_NAMES == ("profile_si_ffs",)
    assert config.ACTIVE_PROFILE_SELECTION.profile_package_names == ("profile_si_ffs",)
    assert config.ACTIVE_PROFILE_SELECTION.active_profile is config.ACTIVE_PROFILE
    assert config.ACTIVE_PROFILE_ROOTS == (config.PROFILE_ROOT,)
    assert config.PROFILE_ROOT.name == "profile_si_ffs"
    assert config.ACTIVE_PROFILE.profile_root == config.PROFILE_ROOT

    monkeypatch.delenv(config.ACTIVE_PROFILE_PACKAGE_NAMES_ENV, raising=False)
    assert config.active_profile_package_names_from_env() == ("profile_si_ffs",)
    monkeypatch.setenv(
        config.ACTIVE_PROFILE_PACKAGE_NAMES_ENV,
        " profile_si_ffs ",
    )
    assert config.active_profile_package_names_from_env() == ("profile_si_ffs",)


def test_resolve_active_descriptor_requires_explicit_without_config_default():
    with pytest.raises(ProfileRuntimeError, match="active runtime descriptor is required"):
        resolve_active_descriptor(None, allow_config_default=False)


def test_resolve_active_descriptor_explicit_does_not_import_config(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def guard_import(name, *args, **kwargs):
        if name == "kernel" and "config" in (kwargs.get("fromlist") or ()):
            raise AssertionError("config fallback was imported")
        if name == "kernel.config":
            raise AssertionError("config fallback was imported")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard_import)
    assert resolve_active_descriptor(
        config.ACTIVE_PROFILE,
        allow_config_default=False,
    ) is config.ACTIVE_PROFILE


def test_descriptor_constructor_alias_conflict_fails_closed():
    conflict = replace(
        config.ACTIVE_PROFILE,
        profile_ref="profile:si.ffs.alias-conflict.v0_1",
    )
    with pytest.raises(TypeError, match="active_profile"):
        GatePipeline(
            object(),
            active_profile=conflict,
        )
    with pytest.raises(ProfileRuntimeError, match="active_descriptor and active_profile"):
        context.ContextAssembler(
            object(),
            active_descriptor=config.ACTIVE_PROFILE,
            active_profile=conflict,
        )
    with pytest.raises(ProfileRuntimeError, match="active_descriptor and active_profile"):
        Materializer(
            object(),
            active_descriptor=config.ACTIVE_PROFILE,
            active_profile=conflict,
        )


def test_descriptor_policy_provider_recognized_rule_refs_are_descriptor_derived():
    provider = profile_policy.DescriptorPolicyProvider(config.ACTIVE_PROFILE)
    assert provider.policy_ref == config.ACTIVE_PROFILE.evidence_policy_ref
    assert provider.recognized_rule_refs == frozenset({
        config.ACTIVE_PROFILE.evidence_policy_ref,
        config.ACTIVE_PROFILE.profile_ref,
        config.ACTIVE_PROFILE.pack_ref,
        config.ACTIVE_PROFILE.code_binding_profile_ref,
    })


def test_descriptor_policy_provider_evidence_policy_does_not_call_config_wrapper(
        monkeypatch):
    def fail_config_policy(*_args, **_kwargs):
        raise AssertionError("config-backed policy wrapper was called")

    monkeypatch.setattr(profile_policy, "load_evidence_review_policy",
                        fail_config_policy)
    provider = profile_policy.DescriptorPolicyProvider(config.ACTIVE_PROFILE)
    doc = provider.evidence_policy(supported_checks=sufficiency.OPERATION_FLOOR_CHECKS)

    assert doc["policyId"] == config.ACTIVE_PROFILE.evidence_policy_ref


@pytest.mark.parametrize("raw", [
    "",
    "profile_si_ffs,",
    ",profile_si_ffs",
    "profile_si_ffs,,profile_si_ffs",
])
def test_active_profile_env_rejects_blank_tokens(monkeypatch, raw):
    monkeypatch.setenv(config.ACTIVE_PROFILE_PACKAGE_NAMES_ENV, raw)

    with pytest.raises(ProfileRuntimeError, match="blank profile package token"):
        config.active_profile_package_names_from_env()


@pytest.mark.parametrize("raw", [
    "",
    "profile_si_ffs,",
    ",profile_si_ffs",
    "profile_si_ffs,,profile_si_ffs",
])
def test_active_profile_env_import_fails_closed_for_blank_tokens(raw):
    env = os.environ.copy()
    env[config.ACTIVE_PROFILE_PACKAGE_NAMES_ENV] = raw

    proc = subprocess.run(
        [sys.executable, "-c", "import kernel.config"],
        cwd=config.PACKAGE_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "blank profile package token" in proc.stderr


def test_descriptor_registry_discovers_si_candidate_and_nl_design_only_package():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )

    assert "profile_si_ffs" in registry.discoverable_package_names
    assert "profile_nl_go_glmc7_2026" in registry.discoverable_package_names
    assert registry.enabled_package_names == ("profile_si_ffs",)
    candidate_names = {candidate.package_name for candidate in registry.descriptor_candidates}
    assert candidate_names == {"profile_si_ffs"}

    candidate = registry.candidate_for("profile_si_ffs")
    assert candidate is not None
    assert candidate.enabled is True
    assert candidate.descriptor == config.ACTIVE_PROFILE
    assert candidate.descriptor_path == config.PROFILE_ROOT / DESCRIPTOR_FILENAME
    assert registry.candidate_for("profile_nl_go_glmc7_2026") is None


def test_descriptor_registry_marks_unenabled_candidate_without_activating_it():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=("profile_other_runtime",),
    )
    candidate = registry.candidate_for("profile_si_ffs")

    assert candidate is not None
    assert candidate.enabled is False


def test_descriptor_registry_without_allow_list_does_not_enable_candidates():
    registry = load_profile_descriptor_registry(config.PACKAGE_ROOT)
    candidate = registry.candidate_for("profile_si_ffs")

    assert registry.enabled_package_names == ()
    assert candidate is not None
    assert candidate.enabled is False


def test_descriptor_registry_rejects_unsafe_enabled_package_name():
    with pytest.raises(ProfileRuntimeError, match="profile_"):
        load_profile_descriptor_registry(
            config.PACKAGE_ROOT,
            allowed_profile_package_names=("contracts",),
        )


def test_active_profile_selection_rejects_multiple_profiles_in_mp1():
    with pytest.raises(ProfileRuntimeError, match="exactly one active profile package"):
        load_active_profile_selection(
            config.PACKAGE_ROOT,
            ("profile_si_ffs", "profile_nl_go_glmc7_2026"),
            allowed_profile_package_names=(
                "profile_si_ffs",
                "profile_nl_go_glmc7_2026",
            ),
        )


def test_active_profile_selection_rejects_design_only_profile_slice():
    with pytest.raises(ProfileRuntimeError, match="design-only profile slices"):
        load_active_profile_selection(
            config.PACKAGE_ROOT,
            ("profile_nl_go_glmc7_2026",),
            allowed_profile_package_names=("profile_nl_go_glmc7_2026",),
        )


def test_active_profile_selection_rejects_profile_not_enabled_for_mp1():
    with pytest.raises(ProfileRuntimeError, match="not enabled for this runtime"):
        load_active_profile_selection(
            config.PACKAGE_ROOT,
            ("profile_nl_go_glmc7_2026",),
            allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
        )


def test_active_profile_selection_requires_explicit_enabled_allow_list():
    with pytest.raises(ProfileRuntimeError, match="explicit enabled profile package allow-list"):
        load_active_profile_selection(
            config.PACKAGE_ROOT,
            ("profile_si_ffs",),
        )


def test_active_profile_selection_uses_registry_and_preserves_si_activation():
    selected = load_active_profile_selection(
        config.PACKAGE_ROOT,
        ("profile_si_ffs",),
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )

    assert selected.profile_package_names == ("profile_si_ffs",)
    assert selected.profile_roots == (config.PROFILE_ROOT,)
    assert selected.active_profile.profile_ref == config.ACTIVE_PROFILE.profile_ref
    assert selected.active_profile.pack_ref == config.ACTIVE_PROFILE.pack_ref


def test_profile_runtime_preconditions_return_invalid_package_blocker():
    result = evaluate_profile_runtime_preconditions(
        _route_registry(),
        "../profile_si_ffs",
        config.ACTIVE_PROFILE_PACKAGE_NAMES,
        _surface_inventory("profile_si_ffs"),
    )

    assert result.package_name == "../profile_si_ffs"
    assert result.preconditions_satisfied is False
    assert result.blocking_reason_codes == ("INVALID_PACKAGE_NAME",)


@pytest.mark.parametrize("package_name", [
    "profile_nl_go_glmc7_2026",
    "profile_rs_organic_crop",
])
def test_profile_runtime_preconditions_block_descriptorless_design_packages(
        package_name):
    if not (config.PACKAGE_ROOT / package_name).exists():
        pytest.skip(f"{package_name} is not present in this checkout")
    result = evaluate_profile_runtime_preconditions(
        _route_registry(enabled=("profile_si_ffs", package_name)),
        package_name,
        ("profile_si_ffs", package_name),
        _surface_inventory(package_name),
    )

    assert result.preconditions_satisfied is False
    assert result.blocking_reason_codes == ("NO_DESCRIPTOR_CANDIDATE",)


def test_profile_runtime_preconditions_block_candidate_not_enabled():
    result = evaluate_profile_runtime_preconditions(
        _route_registry(enabled=("profile_other_runtime",)),
        "profile_si_ffs",
        ("profile_si_ffs",),
        _surface_inventory("profile_si_ffs"),
    )

    assert result.preconditions_satisfied is False
    assert result.blocking_reason_codes == ("PACKAGE_NOT_ENABLED",)


def test_profile_runtime_preconditions_allow_empty_selection_as_not_selected():
    result = evaluate_profile_runtime_preconditions(
        _route_registry(),
        "profile_si_ffs",
        (),
        _surface_inventory("profile_si_ffs"),
    )

    assert result.preconditions_satisfied is False
    assert result.blocking_reason_codes == ("PACKAGE_NOT_SELECTED",)


def test_profile_runtime_preconditions_reject_malformed_inventory_shape():
    with pytest.raises(ProfileRuntimeError, match="surface_inventory"):
        evaluate_profile_runtime_preconditions(
            _route_registry(),
            "profile_si_ffs",
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            object(),
        )


@pytest.mark.parametrize("value", [
    "profile_si_ffs",
    ["profile_si_ffs", 123],
])
def test_profile_runtime_surface_inventory_rejects_malformed_collections(value):
    with pytest.raises(ProfileRuntimeError):
        ProfileRuntimeSurfaceInventory(
            adapter_supported_package_names=value,
        )


def test_profile_runtime_surface_inventory_rejects_invalid_package_names():
    with pytest.raises(ProfileRuntimeError, match="profile_"):
        ProfileRuntimeSurfaceInventory(
            adapter_supported_package_names={"contracts"},
        )


def test_profile_runtime_preconditions_block_bad_descriptor_policy(tmp_path):
    package_root = _copied_package_root(tmp_path)
    policy_path = package_root / "profile_si_ffs" / _base_doc()["evidencePolicyPath"]
    policy = json.loads(policy_path.read_text())
    policy.pop("validation")
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    registry = load_profile_descriptor_registry(
        package_root,
        allowed_profile_package_names=("profile_si_ffs",),
    )

    result = evaluate_profile_runtime_preconditions(
        registry,
        "profile_si_ffs",
        ("profile_si_ffs",),
        _surface_inventory("profile_si_ffs"),
    )

    assert result.preconditions_satisfied is False
    assert result.blocking_reason_codes == ("POLICY_NOT_LOADABLE",)


def test_profile_runtime_preconditions_accumulate_missing_surface_blockers():
    result = evaluate_profile_runtime_preconditions(
        _route_registry(),
        "profile_si_ffs",
        config.ACTIVE_PROFILE_PACKAGE_NAMES,
        ProfileRuntimeSurfaceInventory(),
    )

    assert result.preconditions_satisfied is False
    assert result.blocking_reason_codes == (
        "MISSING_RUNTIME_ADAPTER_SUPPORT",
        "MISSING_PROFILE_HARNESS_COVERAGE",
        "MISSING_PROFILE_EXECUTED_EVIDENCE_LANE",
        "MISSING_MANIFEST_GROUNDING",
    )


def test_profile_runtime_preconditions_pass_with_explicit_inventory_only():
    result = evaluate_profile_runtime_preconditions(
        _route_registry(),
        "profile_si_ffs",
        config.ACTIVE_PROFILE_PACKAGE_NAMES,
        _surface_inventory("profile_si_ffs"),
    )

    assert result.preconditions_satisfied is True
    assert result.blocking_reason_codes == ()


def test_profile_runtime_preconditions_are_passive_for_active_runtime(fresh_env):
    store, pipeline, _ = fresh_env
    before_profile = config.ACTIVE_PROFILE
    before_selected = config.ACTIVE_PROFILE_PACKAGE_NAMES
    evidence_dir = config.PACKAGE_ROOT / "conformance" / "evidence"
    before_evidence = {
        path.name for path in evidence_dir.glob("platform_mvp_results_*.json")
    }
    manifest_path = (
        config.PROFILE_ROOT
        / "OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json"
    )
    artifact_set_path = (
        config.PROFILE_ROOT
        / "OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json"
    )
    before_manifest = manifest_path.read_bytes()
    before_artifact_set = artifact_set_path.read_bytes()

    result = evaluate_profile_runtime_preconditions(
        _route_registry(),
        "profile_si_ffs",
        config.ACTIVE_PROFILE_PACKAGE_NAMES,
        _surface_inventory("profile_si_ffs"),
    )

    assert result.preconditions_satisfied is True
    assert config.ACTIVE_PROFILE is before_profile
    assert config.ACTIVE_PROFILE_PACKAGE_NAMES == before_selected
    assert before_evidence == {
        path.name for path in evidence_dir.glob("platform_mvp_results_*.json")
    }
    assert manifest_path.read_bytes() == before_manifest
    assert artifact_set_path.read_bytes() == before_artifact_set

    commit = pipeline.commit(demo.spray_submission(
        f"mp7-5-passive:{_uid()}",
        erp_id=f"erp:mp7.5.passive.{_uid()}",
        confirm=True,
    ))
    trace = _trace_payload(store, commit)
    assert [entry["gate"] for entry in trace["gateSequence"]][:2] == [
        "INGRESS_NORMALIZATION",
        "AUTHORITY",
    ]
    assert all(
        entry["outcome"] not in {"PROFILE_ROUTE_PASS", "PROFILE_ROUTE_REFUSE"}
        for entry in trace["gateSequence"]
    )


def test_profile_route_resolves_current_si_descriptor():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )
    route = _si_route()

    resolution = resolve_profile_route(
        registry,
        config.ACTIVE_PROFILE_PACKAGE_NAMES,
        [route],
        tenant_ref=config.TENANT_REF,
        farm_ref=demo.FARM,
    )

    assert resolution.route == route
    assert resolution.candidate.package_name == "profile_si_ffs"
    assert resolution.descriptor == config.ACTIVE_PROFILE
    assert resolution.effective_time is None


@pytest.mark.parametrize("package_name", [
    "profile_nl_go_glmc7_2026",
    "profile_rs_organic_crop",
])
def test_profile_route_rejects_design_only_descriptorless_packages(package_name):
    if not (config.PACKAGE_ROOT / package_name).exists():
        pytest.skip(f"{package_name} is not present in this checkout")
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=("profile_si_ffs", package_name),
    )
    route = _si_route(profile_package_name=package_name)

    with pytest.raises(ProfileRuntimeError):
        resolve_profile_route(
            registry,
            ("profile_si_ffs", package_name),
            [route],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )


def test_profile_route_rejects_package_not_enabled():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=("profile_other_runtime",),
    )

    with pytest.raises(ProfileRuntimeError, match="not enabled"):
        resolve_profile_route(
            registry,
            ("profile_si_ffs",),
            [_si_route()],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )


def test_profile_route_rejects_package_not_selected():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )

    with pytest.raises(ProfileRuntimeError, match="not selected"):
        resolve_profile_route(
            registry,
            ("profile_other_runtime",),
            [_si_route()],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )


@pytest.mark.parametrize("field,value,match", [
    ("profile_ref", "profile:si.ffs.route-mismatch.v0_1", "profile_ref"),
    ("pack_ref", "pack:si.ffs.route-mismatch.v0_1", "pack_ref"),
    (
        "pack_activation_set_ref",
        "packactivationset:si.ffs.route-mismatch.v0_1",
        "pack_activation_set_ref",
    ),
    (
        "active_artifact_set_ref",
        "activeartifactset:si.ffs.route-mismatch.v0_1",
        "active_artifact_set_ref",
    ),
])
def test_profile_route_rejects_descriptor_ref_mismatch(field, value, match):
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )
    route = replace(_si_route(), **{field: value})

    with pytest.raises(ProfileRuntimeError, match=match):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            [route],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )
