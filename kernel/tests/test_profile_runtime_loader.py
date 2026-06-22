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
from contextlib import contextmanager
from dataclasses import replace
import uuid

import psycopg
import psycopg.conninfo
import pytest

from kernel import config, context, demo
from kernel.profile_runtime import (
    OMIT_FROM_CONTEXT,
    REFUSE_CONTEXT,
    ProfileRuntimeError,
    ReferenceFamily,
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
