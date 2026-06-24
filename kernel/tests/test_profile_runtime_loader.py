"""Active profile runtime descriptor loader tests.

These pin the PR D1 boundary: SI profile runtime inputs are package content, but
tenant/demo binding remains deployment fixture content. The loader fails closed
before any descriptor mistake can become hidden runtime truth.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import uuid

import psycopg
import psycopg.conninfo
import pytest

from kernel import config, context, demo
from kernel.profile_runtime import (
    OMIT_FROM_CONTEXT,
    REFUSE_CONTEXT,
    DESCRIPTOR_FILENAME,
    ProfileRuntimeError,
    ReferenceFamily,
    load_active_profile_selection,
    load_profile_descriptor_registry,
    load_profile_runtime_descriptor,
)
from kernel.store import Store


def _base_doc() -> dict:
    return json.loads((config.PROFILE_ROOT / "runtime_profile_descriptor.json").read_text())


def _load_modified(tmp_path, mutate):
    doc = copy.deepcopy(_base_doc())
    mutate(doc)
    path = tmp_path / "runtime_profile_descriptor.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return load_profile_runtime_descriptor(config.PROFILE_ROOT, descriptor_path=path)


def _copied_profile_root(tmp_path):
    root = tmp_path / f"profile_si_ffs_{_uid()}"
    root.mkdir()
    doc = _base_doc()
    (root / "runtime_profile_descriptor.json").write_text(
        json.dumps(doc), encoding="utf-8")
    for rel in [doc["evidencePolicyPath"], *doc["profileInstanceFiles"]]:
        shutil.copy2(config.PROFILE_ROOT / rel, root / rel)
    return root, doc


def _copied_package_root(tmp_path):
    root = tmp_path / f"package_root_{_uid()}"
    root.mkdir()
    shutil.copytree(config.PROFILE_ROOT, root / "profile_si_ffs")
    nl_root = root / "profile_nl_go_glmc7_2026"
    nl_root.mkdir()
    (nl_root / "README.md").write_text("design-only profile slice\n", encoding="utf-8")
    return root


def _copied_si_package(package_root: Path, package_name: str) -> tuple[Path, dict]:
    target = package_root / package_name
    shutil.copytree(config.PROFILE_ROOT, target)
    doc_path = target / DESCRIPTOR_FILENAME
    return target, json.loads(doc_path.read_text())


def _profile_file_by_id(profile_root: Path, doc: dict, id_field: str, expected: str):
    for rel in doc["profileInstanceFiles"]:
        path = profile_root / rel
        payload = json.loads(path.read_text())
        if payload.get(id_field) == expected:
            return path, payload
    raise AssertionError(f"missing profile instance {id_field}={expected}")


def _make_second_descriptor_unique(
    profile_root: Path,
    doc: dict,
    *,
    duplicate_field: str,
) -> None:
    base = copy.deepcopy(doc)
    unique = {
        "profileRef": "profile:second.runtime.v0_1",
        "packRef": "pack:second.runtime.v0_1",
        "packActivationSetRef": "packactivationset:second.runtime.v0_1",
        "activeArtifactSetRef": "activeartifactset:second.runtime.v0_1",
        "codeBindingProfileRef": "codebindingprofile:second.runtime.v0_1",
        "evidencePolicyRef": "policy:second.runtime.evidence-review.v0_1",
        "contextSnapshotIdPrefix": "contextsnapshot:second.runtime",
    }
    for field, value in unique.items():
        if field != duplicate_field:
            doc[field] = value

    policy_path = profile_root / doc["evidencePolicyPath"]
    policy = json.loads(policy_path.read_text())
    policy["policyId"] = doc["evidencePolicyRef"]
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    profile_path, profile = _profile_file_by_id(
        profile_root, base, "agronomicCodeBindingProfileId",
        base["codeBindingProfileRef"])
    profile["agronomicCodeBindingProfileId"] = doc["codeBindingProfileRef"]
    profile["profileScope"]["packRefs"] = [doc["packRef"]]
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    activation_path, activation = _profile_file_by_id(
        profile_root, base, "packActivationSetId",
        base["packActivationSetRef"])
    activation["packActivationSetId"] = doc["packActivationSetRef"]
    activation["activePackRefs"] = [doc["packRef"]]
    activation["activeProfileRefs"] = [doc["profileRef"]]
    activation_path.write_text(json.dumps(activation), encoding="utf-8")

    artifact_path, artifact = _profile_file_by_id(
        profile_root, base, "activeArtifactSetId",
        base["activeArtifactSetRef"])
    artifact["activeArtifactSetId"] = doc["activeArtifactSetRef"]
    artifact["sourcePackActivationSetRefs"] = [doc["packActivationSetRef"]]
    artifact["activePackRefs"] = [doc["packRef"]]
    artifact["activeProfileRefs"] = [doc["profileRef"]]
    artifact["activeArtifactRefs"] = [
        ref for ref in artifact["activeArtifactRefs"]
        if ref not in {base["codeBindingProfileRef"], base["evidencePolicyRef"]}
    ] + [doc["codeBindingProfileRef"], doc["evidencePolicyRef"]]
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    (profile_root / DESCRIPTOR_FILENAME).write_text(json.dumps(doc), encoding="utf-8")


def _uid():
    return uuid.uuid4().hex[:8]


def _admin_dsn() -> str:
    explicit = os.environ.get("OFARM_PG_ADMIN_DSN")
    if explicit:
        return explicit
    socket_dir = os.environ.get("OFARM_PG_SOCKET_DIR", str(config.PACKAGE_ROOT / ".pgrun"))
    port = os.environ.get("OFARM_PG_PORT", "54317")
    user = os.environ.get("OFARM_PG_USER", "ofarm")
    return f"host={socket_dir} port={port} dbname=postgres user={user}"


def _payload(store, kind: str, record_id: str, id_field: str) -> dict:
    for row in store.find_by_kind(kind):
        payload = dict(row["payload"])
        if payload.get(id_field) == record_id:
            return payload
    raise AssertionError(f"missing {kind} {record_id}")


def _insert_decoy_spine(store) -> dict:
    """Insert a coherent but non-descriptor active spine after bootstrap.

    The former NOW selection path (`[-1]`) would have picked this generation by
    store order. Descriptor-backed NOW selection must ignore it.
    """
    suffix = _uid()
    profile = _payload(
        store, "ofarm.agronomiccodebindingprofile.v0.1",
        config.ACTIVE_PROFILE.code_binding_profile_ref,
        "agronomicCodeBindingProfileId")
    profile_id = f"codebindingprofile:si.ffs.decoy.{suffix}"
    profile["agronomicCodeBindingProfileId"] = profile_id
    profile["issuedAt"] = context.now_iso()
    profile["profileState"] = "ACTIVE"

    activation = _payload(
        store, "ofarm.packactivationset.v0.1",
        config.ACTIVE_PROFILE.pack_activation_set_ref,
        "packActivationSetId")
    activation_id = f"packactivationset:si.ffs.decoy.{suffix}"
    activation["packActivationSetId"] = activation_id
    activation["evaluatedAt"] = context.now_iso()

    artifact = _payload(
        store, "ofarm.activeartifactset.v0.1",
        config.ACTIVE_PROFILE.active_artifact_set_ref,
        "activeArtifactSetId")
    artifact_id = f"activeartifactset:si.ffs.decoy.{suffix}"
    artifact["activeArtifactSetId"] = artifact_id
    artifact["generatedAt"] = context.now_iso()
    artifact["sourcePackActivationSetRefs"] = [activation_id]
    artifact["activeArtifactRefs"] = [
        ref for ref in artifact["activeArtifactRefs"]
        if not ref.startswith("codebindingprofile:")
    ] + [profile_id]

    with store.tx() as cur:
        store.insert_record(cur, profile)
        store.insert_record(cur, activation)
        store.insert_record(cur, artifact)
    return {"profile": profile_id, "activation": activation_id, "artifact": artifact_id}


def _profile_instance_payload(id_field: str, expected: str) -> dict:
    for path in config.ACTIVE_PROFILE.profile_instance_paths:
        payload = json.loads(path.read_text())
        if payload.get(id_field) == expected:
            return payload
    raise AssertionError(f"missing profile instance {id_field}={expected}")


@contextmanager
def _preseeded_dirty_spine_store(mutate):
    """Fresh store where descriptor-id spine records exist before bootstrap."""
    dbname = f"ofarm_dirty_spine_{_uid()}"
    with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        admin.execute(f'CREATE DATABASE "{dbname}"')
    params = psycopg.conninfo.conninfo_to_dict(_admin_dsn())
    params["dbname"] = dbname
    store = Store(dsn=psycopg.conninfo.make_conninfo(**params))
    try:
        store.migrate()
        profile = _profile_instance_payload(
            "agronomicCodeBindingProfileId",
            config.ACTIVE_PROFILE.code_binding_profile_ref)
        activation = _profile_instance_payload(
            "packActivationSetId",
            config.ACTIVE_PROFILE.pack_activation_set_ref)
        artifact = _profile_instance_payload(
            "activeArtifactSetId",
            config.ACTIVE_PROFILE.active_artifact_set_ref)
        mutate(profile, activation, artifact)
        with store.tx() as cur:
            store.insert_record(cur, profile)
            store.insert_record(cur, activation)
            store.insert_record(cur, artifact)
        context.bootstrap(store)
        yield store
    finally:
        store.close()
        with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


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
    assert config.SHIPPED_REGSR_SNAPSHOT_REF == active.reference_family(
        "si.uvhvvr.ffs-reg").shipped_snapshot_ref


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


def _missing_family(required: bool) -> ReferenceFamily:
    behavior = REFUSE_CONTEXT if required else OMIT_FROM_CONTEXT
    return ReferenceFamily(
        family_id="test.missing-family",
        snapshot_prefix="referencesnapshot:test.missing-family",
        data_family=None,
        required_for_now_context=required,
        required_for_as_of_context=required,
        missing_family_behavior_now=behavior,
        missing_family_behavior_as_of=behavior,
        shipped_snapshot_ref=None,
    )


def test_optional_missing_reference_family_is_omitted(fresh_env, monkeypatch):
    store, _, _ = fresh_env
    monkeypatch.setattr(
        config,
        "ACTIVE_PROFILE",
        replace(
            config.ACTIVE_PROFILE,
            reference_families=config.ACTIVE_PROFILE.reference_families
            + (_missing_family(required=False),),
        ),
    )

    with store.tx() as cur:
        snap = context.ContextAssembler(store).assemble(cur, demo.FARM)

    assert not any(
        ref.startswith("referencesnapshot:test.missing-family")
        for ref in snap["referenceSnapshotRefs"]
    )


def test_required_missing_reference_family_refuses_context(fresh_env, monkeypatch):
    store, _, _ = fresh_env
    monkeypatch.setattr(
        config,
        "ACTIVE_PROFILE",
        replace(
            config.ACTIVE_PROFILE,
            reference_families=config.ACTIVE_PROFILE.reference_families
            + (_missing_family(required=True),),
        ),
    )

    with pytest.raises(context.ContextNotReconstructible, match="required reference family"):
        with store.tx() as cur:
            context.ContextAssembler(store).assemble(cur, demo.FARM)


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
