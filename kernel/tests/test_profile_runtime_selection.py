"""test profile runtime selection."""
# ruff: noqa: F403, F405

from kernel.tests._profile_runtime_test_support import *


def test_profile_route_rejects_descriptor_identity_mismatch():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )
    route = _si_route(descriptor_identity="profile_si_ffs/runtime_profile_descriptor.json#bad")

    with pytest.raises(ProfileRuntimeError, match="descriptor identity"):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            [route],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )


def test_profile_route_requires_one_active_matching_route():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )

    with pytest.raises(ProfileRuntimeError, match="no active profile route"):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            [],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )
    with pytest.raises(ProfileRuntimeError, match="multiple active overlapping"):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            [_si_route(), _si_route()],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )


@pytest.mark.parametrize("status", ["DRAFT", "RETIRED", "REVOKED"])
def test_profile_route_inactive_records_do_not_count_as_matches(status):
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )

    with pytest.raises(ProfileRuntimeError, match="no active profile route"):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            [_si_route(status=status)],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )


def test_profile_route_validates_inactive_record_structure():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )

    with pytest.raises(ProfileRuntimeError, match="route.route_id"):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            [_si_route(route_id="not-a-ref", status="DRAFT")],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )


def test_profile_route_rejects_scalar_route_records():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )

    with pytest.raises(ProfileRuntimeError, match="must be a sequence"):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            123,
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )


@pytest.mark.parametrize("route,match", [
    (_si_route(profile_package_name="contracts"), "profile_"),
    (_si_route(status="PAUSED"), "status"),
])
def test_profile_route_rejects_malformed_route_values(route, match):
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )

    with pytest.raises(ProfileRuntimeError, match=match):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            [route],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )


def test_profile_route_effective_time_uses_half_open_intervals():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    t2 = datetime(2027, 1, 1, tzinfo=timezone.utc)
    first = _si_route(
        route_id=f"profileroute:test.si.first.{_uid()}",
        effective_from=t0,
        effective_until=t1,
    )
    second = _si_route(
        route_id=f"profileroute:test.si.second.{_uid()}",
        effective_from=t1,
        effective_until=t2,
    )

    at_start = resolve_profile_route(
        registry,
        config.ACTIVE_PROFILE_PACKAGE_NAMES,
        [first, second],
        tenant_ref=config.TENANT_REF,
        farm_ref=demo.FARM,
        effective_time=t0,
    )
    at_boundary = resolve_profile_route(
        registry,
        config.ACTIVE_PROFILE_PACKAGE_NAMES,
        [first, second],
        tenant_ref=config.TENANT_REF,
        farm_ref=demo.FARM,
        effective_time=t1,
    )

    assert at_start.route == first
    assert at_boundary.route == second
    with pytest.raises(ProfileRuntimeError, match="no active profile route"):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            [first, second],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )


def test_profile_route_rejects_overlapping_time_bounded_active_routes():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    t3 = datetime(2027, 1, 1, tzinfo=timezone.utc)
    first = _si_route(
        route_id=f"profileroute:test.si.overlap.first.{_uid()}",
        effective_from=t0,
        effective_until=t2,
    )
    second = _si_route(
        route_id=f"profileroute:test.si.overlap.second.{_uid()}",
        effective_from=t1,
        effective_until=t3,
    )

    with pytest.raises(ProfileRuntimeError, match="multiple active overlapping"):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            [first, second],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
            effective_time=t1,
        )


def test_profile_route_rejects_malformed_time_values():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )
    aware = datetime(2026, 1, 1, tzinfo=timezone.utc)
    naive = datetime(2026, 1, 1)

    with pytest.raises(ProfileRuntimeError, match="timezone-aware"):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            [_si_route(effective_from=naive)],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )
    with pytest.raises(ProfileRuntimeError, match="earlier than effective_until"):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            [_si_route(effective_from=aware, effective_until=aware)],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )


@pytest.mark.parametrize("selection,match", [
    ((), "must not be empty"),
    ("profile_si_ffs", "must be a sequence"),
    (("../profile_si_ffs",), "simple repository-local"),
    (("profile_si_ffs/runtime_profile_descriptor.json",), "simple repository-local"),
    (("contracts",), "profile_"),
])
def test_active_profile_selection_rejects_unsafe_or_non_profile_names(selection, match):
    with pytest.raises(ProfileRuntimeError, match=match):
        load_active_profile_selection(
            config.PACKAGE_ROOT,
            selection,
            allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
        )


def test_descriptor_registry_rejects_malformed_descriptor_candidate(tmp_path):
    root = _copied_package_root(tmp_path)
    descriptor = root / "profile_si_ffs" / DESCRIPTOR_FILENAME
    descriptor.write_text("{not json", encoding="utf-8")

    with pytest.raises(ProfileRuntimeError, match="descriptor unreadable"):
        load_profile_descriptor_registry(root)


def test_descriptor_registry_rejects_descriptor_file_escape(tmp_path):
    root = _copied_package_root(tmp_path)
    descriptor = root / "profile_si_ffs" / DESCRIPTOR_FILENAME
    doc = json.loads(descriptor.read_text())
    doc["evidencePolicyPath"] = "../outside.json"
    descriptor.write_text(json.dumps(doc), encoding="utf-8")

    with pytest.raises(ProfileRuntimeError, match=r"\.\."):
        load_profile_descriptor_registry(root)


def test_descriptor_registry_rejects_descriptor_symlink_escape(tmp_path):
    root = _copied_package_root(tmp_path)
    profile_root = root / "profile_si_ffs"
    descriptor = profile_root / DESCRIPTOR_FILENAME
    outside_descriptor = tmp_path / f"outside_descriptor_{_uid()}.json"
    outside_descriptor.write_text(descriptor.read_text(), encoding="utf-8")
    descriptor.unlink()
    descriptor.symlink_to(outside_descriptor)

    with pytest.raises(ProfileRuntimeError, match="escapes the profile root"):
        load_profile_descriptor_registry(root)


@pytest.mark.parametrize("field,match", [
    ("profileRef", "duplicate profile_ref"),
    ("packRef", "duplicate pack_ref"),
    ("packActivationSetRef", "duplicate pack_activation_set_ref"),
    ("activeArtifactSetRef", "duplicate active_artifact_set_ref"),
    ("contextSnapshotIdPrefix", "duplicate context_snapshot_id_prefix"),
    ("codeBindingProfileRef", "duplicate code_binding_profile_ref"),
    ("evidencePolicyRef", "duplicate evidence_policy_ref"),
])
def test_descriptor_registry_rejects_duplicate_descriptor_refs(tmp_path, field, match):
    root = tmp_path / "package_root"
    root.mkdir()
    _copied_si_package(root, "profile_si_ffs")
    second_root, second_doc = _copied_si_package(root, "profile_second_runtime")
    _make_second_descriptor_unique(
        second_root,
        second_doc,
        duplicate_field=field,
    )

    with pytest.raises(ProfileRuntimeError, match=match):
        load_profile_descriptor_registry(root)


@pytest.mark.parametrize("field,value", [
    ("tenantRef", "tenant:si.ffs.pilot.demo"),
    ("profilePackageRoot", "profile_si_ffs"),
    ("surprise", True),
])
def test_descriptor_rejects_unknown_fields(tmp_path, field, value):
    with pytest.raises(ProfileRuntimeError, match="unknown field"):
        _load_modified(tmp_path, lambda doc: doc.__setitem__(field, value))


@pytest.mark.parametrize("field,value,match", [
    ("evidencePolicyPath", "/tmp/evidence_review_policy_v0_1.json", "absolute"),
    ("evidencePolicyPath", "../evidence_review_policy_v0_1.json", r"\.\."),
])
def test_descriptor_rejects_bad_profile_paths(tmp_path, field, value, match):
    with pytest.raises(ProfileRuntimeError, match=match):
        _load_modified(tmp_path, lambda doc: doc.__setitem__(field, value))


def test_descriptor_rejects_bad_profile_instance_path(tmp_path):
    def mutate(doc):
        doc["profileInstanceFiles"][0] = "../OFARM_AgronomicCodeBindingProfile_si_ffs_v0_1.json"

    with pytest.raises(ProfileRuntimeError, match=r"\.\."):
        _load_modified(tmp_path, mutate)


def test_descriptor_wraps_malformed_profile_instance_json(tmp_path):
    root, doc = _copied_profile_root(tmp_path)
    bad_rel = doc["profileInstanceFiles"][0]
    (root / bad_rel).write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ProfileRuntimeError, match=bad_rel):
        load_profile_runtime_descriptor(root)


def test_descriptor_wraps_unreadable_profile_instance_json(tmp_path, monkeypatch):
    root, doc = _copied_profile_root(tmp_path)
    bad_rel = doc["profileInstanceFiles"][0]
    bad_path = (root / bad_rel).resolve()
    original_read_text = Path.read_text

    def fail_profile_instance_read(self, *args, **kwargs):
        if self.resolve() == bad_path:
            raise OSError("permission denied by test")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_profile_instance_read)

    with pytest.raises(ProfileRuntimeError, match=bad_rel):
        load_profile_runtime_descriptor(root)


def test_descriptor_rejects_malformed_refs(tmp_path):
    with pytest.raises(ProfileRuntimeError, match="profileRef"):
        _load_modified(tmp_path, lambda doc: doc.__setitem__("profileRef", "not a ref"))


def test_descriptor_rejects_incoherent_active_spine(tmp_path):
    with pytest.raises(ProfileRuntimeError, match="exactly one active pack"):
        _load_modified(tmp_path, lambda doc: doc.__setitem__("packRef", "pack:si.ffs.other"))


def test_descriptor_rejects_multiple_active_packs_or_profiles(tmp_path):
    root, doc = _copied_profile_root(tmp_path)
    activation_name = "OFARM_PackActivationSet_example_si_ffs_pilot_v0_1.json"
    activation_path = root / activation_name
    activation = json.loads(activation_path.read_text())
    activation["activePackRefs"] = [doc["packRef"], "pack:si.ffs.second.v0_1"]
    activation_path.write_text(json.dumps(activation), encoding="utf-8")

    with pytest.raises(ProfileRuntimeError, match="exactly one active pack"):
        load_profile_runtime_descriptor(root)

    root, doc = _copied_profile_root(tmp_path)
    activation_path = root / activation_name
    activation = json.loads(activation_path.read_text())
    activation["activeProfileRefs"] = [
        doc["profileRef"],
        "profile:si.ffs.second.v0_1",
    ]
    activation_path.write_text(json.dumps(activation), encoding="utf-8")

    with pytest.raises(ProfileRuntimeError, match="exactly one active profile"):
        load_profile_runtime_descriptor(root)


def test_descriptor_rejects_code_binding_profile_wrong_pack_scope(tmp_path):
    root, doc = _copied_profile_root(tmp_path)
    profile_name = "OFARM_AgronomicCodeBindingProfile_si_ffs_v0_1.json"
    profile_path = root / profile_name
    profile = json.loads(profile_path.read_text())
    profile["profileScope"]["packRefs"] = ["pack:si.ffs.wrong.v0_1"]
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(ProfileRuntimeError, match="profileScope.packRefs"):
        load_profile_runtime_descriptor(root)


def test_descriptor_rejects_missing_active_spine_ref(tmp_path):
    with pytest.raises(ProfileRuntimeError, match="expected exactly one"):
        _load_modified(
            tmp_path,
            lambda doc: doc.__setitem__(
                "activeArtifactSetRef", "activeartifactset:si.ffs.missing"),
        )


def test_descriptor_rejects_inconsistent_reference_family_behavior(tmp_path):
    def mutate(doc):
        doc["referenceFamilies"][0]["requiredForNowContext"] = True

    with pytest.raises(ProfileRuntimeError, match="required flag and missing behavior disagree"):
        _load_modified(tmp_path, mutate)


def test_descriptor_rejects_mismatched_shipped_snapshot_ref(tmp_path):
    def mutate(doc):
        doc["referenceFamilies"][0]["shippedSnapshotRef"] = (
            "referencesnapshot:si.other-family.2026-06-11"
        )

    with pytest.raises(ProfileRuntimeError, match="does not match prefix"):
        _load_modified(tmp_path, mutate)


def test_explicit_descriptor_bootstrap_inserts_expected_profile_instances():
    with _fresh_unbootstrapped_store() as store:
        expected = _expected_profile_instance_ids(store, config.ACTIVE_PROFILE)
        inserted = context.bootstrap_for_descriptor(store, config.ACTIVE_PROFILE)

        assert inserted == expected
        assert all(store.record_exists(record_id) for record_id in expected)


def test_explicit_descriptor_bootstrap_matches_compatibility_wrapper():
    with _fresh_unbootstrapped_store() as implicit_store:
        expected = _expected_profile_instance_ids(
            implicit_store,
            config.ACTIVE_PROFILE,
        )
        implicit = context.bootstrap(implicit_store)

    with _fresh_unbootstrapped_store() as explicit_store:
        explicit = context.bootstrap_for_descriptor(
            explicit_store,
            config.ACTIVE_PROFILE,
        )

    assert implicit == explicit == expected


def test_explicit_descriptor_reference_snapshots_match_wrapper(fresh_env):
    store, _, _ = fresh_env

    explicit = context.context_reference_snapshots_for_descriptor(
        store,
        config.ACTIVE_PROFILE,
    )
    implicit = context.context_reference_snapshots(store)

    assert explicit == implicit


def test_explicit_descriptor_context_assembly_matches_wrapper(fresh_env):
    store, _, _ = fresh_env

    with store.tx() as cur:
        implicit = context.ContextAssembler(store).assemble(cur, demo.FARM)
    with store.tx() as cur:
        explicit = context.ContextAssembler(
            store,
            active_profile=config.ACTIVE_PROFILE,
        ).assemble(cur, demo.FARM)

    assert explicit == implicit


def test_explicit_descriptor_asof_context_matches_wrapper(fresh_env):
    store, _, _ = fresh_env
    policy = {"policyType": "AS_OF", "asOfTime": "2026-12-01T00:00:00Z"}

    with store.tx() as cur:
        implicit = context.ContextAssembler(store).assemble(
            cur,
            demo.FARM,
            evaluation_time_policy=policy,
        )
    with store.tx() as cur:
        explicit = context.ContextAssembler(
            store,
            active_profile=config.ACTIVE_PROFILE,
        ).assemble(
            cur,
            demo.FARM,
            evaluation_time_policy=policy,
        )

    assert explicit == implicit


def test_descriptor_reference_selection_omits_optional_missing_family(fresh_env):
    store, _, _ = fresh_env
    active = replace(
        config.ACTIVE_PROFILE,
        reference_families=config.ACTIVE_PROFILE.reference_families
        + (_missing_family(required=False),),
    )

    snapshots = context.context_reference_snapshots_for_descriptor(store, active)

    assert not any(
        snapshot["referenceSnapshotId"].startswith(
            "referencesnapshot:test.missing-family"
        )
        for snapshot in snapshots
    )


def test_descriptor_reference_selection_refuses_required_missing_family(fresh_env):
    store, _, _ = fresh_env
    active = replace(
        config.ACTIVE_PROFILE,
        reference_families=config.ACTIVE_PROFILE.reference_families
        + (_missing_family(required=True),),
    )

    with pytest.raises(context.ContextNotReconstructible, match="required reference family"):
        context.context_reference_snapshots_for_descriptor(store, active)


def test_now_context_uses_descriptor_spine_not_later_store_rows(fresh_env):
    store, _, _ = fresh_env
    decoy = _insert_decoy_spine(store)

    with store.tx() as cur:
        snap = context.ContextAssembler(store).assemble(cur, demo.FARM)

    assert snap["activeArtifactSetRef"] == config.ACTIVE_PROFILE.active_artifact_set_ref
    assert snap["sourcePackActivationSetRefs"] == [
        config.ACTIVE_PROFILE.pack_activation_set_ref
    ]
    assert decoy["artifact"] != snap["activeArtifactSetRef"]
    assert decoy["activation"] not in snap["sourcePackActivationSetRefs"]


def test_explicit_descriptor_now_context_uses_descriptor_spine_not_later_store_rows(
        fresh_env):
    store, _, _ = fresh_env
    decoy = _insert_decoy_spine(store)

    with store.tx() as cur:
        snap = context.ContextAssembler(
            store,
            active_profile=config.ACTIVE_PROFILE,
        ).assemble(cur, demo.FARM)

    assert snap["activeArtifactSetRef"] == config.ACTIVE_PROFILE.active_artifact_set_ref
    assert snap["sourcePackActivationSetRefs"] == [
        config.ACTIVE_PROFILE.pack_activation_set_ref
    ]
    assert decoy["artifact"] != snap["activeArtifactSetRef"]
    assert decoy["activation"] not in snap["sourcePackActivationSetRefs"]


def test_context_assembler_refuses_descriptor_outside_store_selection(
        fresh_env):
    store, _, _ = fresh_env
    active = replace(
        config.ACTIVE_PROFILE,
        active_artifact_set_ref="activeartifactset:si.ffs.not-selected.v0_1",
    )

    with pytest.raises(ProfileRuntimeError, match="startup selection"):
        context.ContextAssembler(store, active_profile=active)


def test_now_context_refuses_descriptor_id_spine_with_wrong_pack_profile():
    bad_pack = "pack:si.ffs.dirty.v0_1"
    bad_profile = "profile:si.ffs.dirty.v0_1"

    def mutate(_profile, activation, artifact):
        activation["activePackRefs"] = [bad_pack]
        activation["activeProfileRefs"] = [bad_profile]
        artifact["activePackRefs"] = [bad_pack]
        artifact["activeProfileRefs"] = [bad_profile]

    with _preseeded_dirty_spine_store(mutate) as store:
        with pytest.raises(context.ContextNotReconstructible, match="descriptor packRef"):
            with store.tx() as cur:
                context.ContextAssembler(store).assemble(cur, demo.FARM)


def test_now_context_refuses_descriptor_id_spine_missing_evidence_policy():
    def mutate(_profile, _activation, artifact):
        artifact["activeArtifactRefs"] = [
            ref for ref in artifact["activeArtifactRefs"]
            if ref != config.ACTIVE_PROFILE.evidence_policy_ref
        ]

    with _preseeded_dirty_spine_store(mutate) as store:
        with pytest.raises(context.ContextNotReconstructible, match="evidence policy"):
            with store.tx() as cur:
                context.ContextAssembler(store).assemble(cur, demo.FARM)


def test_now_context_refuses_descriptor_id_profile_wrong_pack_scope():
    def mutate(profile, _activation, _artifact):
        profile["profileScope"]["packRefs"] = ["pack:si.ffs.dirty.v0_1"]

    with _preseeded_dirty_spine_store(mutate) as store:
        with pytest.raises(context.ContextNotReconstructible, match="profileScope.packRefs"):
            with store.tx() as cur:
                context.ContextAssembler(store).assemble(cur, demo.FARM)


def test_gate_pipeline_explicit_descriptor_matches_default_for_clean_operation(
        fresh_env):
    store, default_pipeline, _ = fresh_env
    explicit_pipeline = GatePipeline(
        store,
        active_descriptor=config.ACTIVE_PROFILE,
    )

    default = default_pipeline.commit(demo.spray_submission(
        f"mp3d-default:{_uid()}",
        erp_id=f"erp:mp3d.default.{_uid()}",
        confirm=True,
    ))
    explicit = explicit_pipeline.commit(demo.spray_submission(
        f"mp3d-explicit:{_uid()}",
        erp_id=f"erp:mp3d.explicit.{_uid()}",
        confirm=True,
    ))

    assert default["decisionOutcome"] == explicit["decisionOutcome"] == \
        "PROMOTE_ACCEPTED"
    assert default.get("problems", []) == explicit.get("problems", []) == []


def test_gate_pipeline_default_sequence_remains_unrouted(fresh_env):
    store, pipeline, _ = fresh_env

    result = pipeline.commit(demo.spray_submission(
        f"mp7-default:{_uid()}",
        erp_id=f"erp:mp7.default.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    trace = _trace_payload(store, result)
    gates = [entry["gate"] for entry in trace["gateSequence"]]
    assert "PROFILE_ROUTE" not in gates
    assert gates[:2] == ["INGRESS_NORMALIZATION", "AUTHORITY"]


def test_gate_pipeline_default_missing_farm_ref_still_fails_before_route(
        fresh_env):
    store, pipeline, _ = fresh_env
    sub = demo.spray_submission(
        f"mp7-default-missing-farm:{_uid()}",
        erp_id=f"erp:mp7.default.missing-farm.{_uid()}",
        confirm=True,
    )
    del sub["farmRef"]
    before = len(store.find_by_kind("ofarm.promotiontrace.v0.1"))

    with pytest.raises(KeyError, match="farmRef"):
        pipeline.commit(sub)

    assert len(store.find_by_kind("ofarm.promotiontrace.v0.1")) == before


@pytest.mark.parametrize("kwargs", [
    {"profile_route_records": [_si_route()]},
    {"profile_route_registry": _route_registry()},
    {"selected_profile_package_names": config.ACTIVE_PROFILE_PACKAGE_NAMES},
    {"tenant_ref": config.TENANT_REF},
    {
        "profile_route_records": [_si_route()],
        "profile_route_registry": _route_registry(),
        "selected_profile_package_names": config.ACTIVE_PROFILE_PACKAGE_NAMES,
    },
])
def test_gate_pipeline_partial_route_config_fails_closed(kwargs):
    with pytest.raises(ProfileRuntimeError, match="route-backed GatePipeline requires"):
        GatePipeline(object(), **kwargs)
