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
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import uuid

import psycopg
import psycopg.conninfo
import pytest

from kernel import config, context, demo, profile_policy, sufficiency, validators
from kernel.gates import GatePipeline
from kernel.materializer import Materializer
from kernel.profile_runtime import (
    OMIT_FROM_CONTEXT,
    REFUSE_CONTEXT,
    DESCRIPTOR_FILENAME,
    ProfileRuntimeError,
    ProfileRouteRecord,
    ReferenceFamily,
    load_active_profile_selection,
    load_profile_descriptor_registry,
    load_profile_runtime_descriptor,
    profile_runtime_descriptor_identity,
    resolve_profile_route,
    resolve_active_descriptor,
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


def _si_route(**overrides) -> ProfileRouteRecord:
    values = {
        "route_id": f"profileroute:test.si.{_uid()}",
        "tenant_ref": config.TENANT_REF,
        "farm_ref": demo.FARM,
        "profile_package_name": "profile_si_ffs",
        "profile_ref": config.ACTIVE_PROFILE.profile_ref,
        "pack_ref": config.ACTIVE_PROFILE.pack_ref,
        "pack_activation_set_ref": config.ACTIVE_PROFILE.pack_activation_set_ref,
        "active_artifact_set_ref": config.ACTIVE_PROFILE.active_artifact_set_ref,
        "descriptor_identity": profile_runtime_descriptor_identity(config.ACTIVE_PROFILE),
    }
    values.update(overrides)
    return ProfileRouteRecord(**values)


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
def _fresh_unbootstrapped_store():
    dbname = f"ofarm_context_explicit_{_uid()}"
    with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        admin.execute(f'CREATE DATABASE "{dbname}"')
    params = psycopg.conninfo.conninfo_to_dict(_admin_dsn())
    params["dbname"] = dbname
    store = Store(dsn=psycopg.conninfo.make_conninfo(**params))
    try:
        store.migrate()
        yield store
    finally:
        store.close()
        with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


def _expected_profile_instance_ids(store, active_profile) -> list[str]:
    expected = []
    for path in active_profile.profile_instance_paths:
        payload = json.loads(path.read_text())
        contract = store.registry.get(payload["schemaVersion"])
        expected.append(payload[contract.id_field])
    return expected


def _bootstrap_demo_substrate_only(store) -> None:
    for payload in demo.substrate_records():
        contract = store.registry.get(payload["schemaVersion"])
        record_id = payload[contract.id_field]
        if store.record_exists(record_id):
            continue
        with store.tx() as cur:
            store.insert_record(cur, payload)


def _trace_payload(store, result: dict) -> dict:
    return store.get_payload(result["promotionTraceRef"])


def _case_payload(store, result: dict) -> dict:
    return store.get_payload(_trace_payload(store, result)["evidenceSufficiencyCaseRef"])


def _policy_dimension(vector: dict) -> dict:
    for dimension in vector["versionDimensions"]:
        if dimension["dimensionFamily"] == "RULE_EVIDENCE_POLICY":
            return dimension
    raise AssertionError("missing RULE_EVIDENCE_POLICY dimension")


def _regsr_artifact(*, decision: str) -> dict:
    return {
        "products": [
            {
                "regsrCode": "9001",
                "name": "FIKTIV CUSTOM (fictional)",
                "registrationValidUntil": "2030-12-31",
            }
        ],
        "productDetails": [
            {
                "regsrCode": "9001",
                "name": "FIKTIV CUSTOM (fictional)",
                "decisions": [
                    {
                        "decisionType": "Registracija",
                        "decisionNumber": decision,
                        "issued": "2026-01-01",
                        "validUntil": "2030-12-31",
                    }
                ],
            }
        ],
    }


def _custom_si_descriptor_with_regsr_artifact(tmp_path):
    root = tmp_path / f"profile_si_ffs_custom_{_uid()}"
    examples = root / "examples"
    examples.mkdir(parents=True)
    decision = f"U9{_uid()[:4]}-50/26/b"
    artifact_name = "custom_regsr_snapshot.json"
    artifact_path = examples / artifact_name
    artifact_path.write_text(json.dumps(_regsr_artifact(decision=decision)),
                             encoding="utf-8")

    regsr_prefix = f"referencesnapshot:si.custom.ffs-reg.{_uid()}"
    regsr_ref = f"{regsr_prefix}.2026-06-11"
    snapshot_path = root / "OFARM_ReferenceSnapshot_custom_regsr.json"
    snapshot_path.write_text(json.dumps({
        "schemaVersion": "ofarm.referencesnapshot.v0.1",
        "referenceSnapshotId": regsr_ref,
        "issuedAt": "2026-06-11T00:00:00Z",
        "effectiveFrom": "2026-06-11T00:00:00Z",
        "effectiveUntil": None,
        "sourceArtifactRefs": [f"artifact:{artifact_name}"],
        "issuingAuthorityRef": "party:si.uvhvvr",
    }), encoding="utf-8")

    regsr_family = ReferenceFamily(
        family_id="si.uvhvvr.ffs-reg",
        snapshot_prefix=regsr_prefix,
        data_family=f"si.custom.ffs-reg.{_uid()}",
        required_for_now_context=False,
        required_for_as_of_context=False,
        missing_family_behavior_now=OMIT_FROM_CONTEXT,
        missing_family_behavior_as_of=OMIT_FROM_CONTEXT,
        shipped_snapshot_ref=regsr_ref,
    )
    gerk_family = ReferenceFamily(
        family_id="si.mkgp.gerk-layer",
        snapshot_prefix=f"referencesnapshot:si.custom.gerk-layer.{_uid()}",
        data_family=f"si.custom.gerk-layer.{_uid()}",
        required_for_now_context=False,
        required_for_as_of_context=False,
        missing_family_behavior_now=OMIT_FROM_CONTEXT,
        missing_family_behavior_as_of=OMIT_FROM_CONTEXT,
        shipped_snapshot_ref=f"referencesnapshot:si.custom.gerk-layer.{_uid()}.2025-06-30",
    )
    descriptor = replace(
        config.ACTIVE_PROFILE,
        profile_root=root,
        profile_instance_files=(snapshot_path.name,),
        profile_instance_paths=(snapshot_path,),
        reference_families=(regsr_family, gerk_family),
    )
    return descriptor, artifact_path.resolve(), decision


def _assert_profile_applicability_refusal(store, result: dict) -> dict:
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    trace = _trace_payload(store, result)
    assert [entry["gate"] for entry in trace["gateSequence"]] == [
        "INGRESS_NORMALIZATION",
        "AUTHORITY",
        "VALIDATION",
        "PACK_PROFILE_APPLICABILITY",
    ]
    assert trace["gateSequence"][-1]["outcome"] == "NOT_APPLICABLE"
    assert "evidenceSufficiencyCaseRef" not in trace
    return trace


def _note_submission(idem_key: str) -> dict:
    return {
        "commitClass": "NOTE",
        "actingPartyRef": demo.FARMER,
        "farmRef": demo.FARM,
        "idempotencyKey": idem_key,
        "noteText": "issue #125 profile applicability probe",
        "eventTime": "2026-06-10T09:00:00Z",
    }


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
        for payload in demo.substrate_records():
            contract = store.registry.get(payload["schemaVersion"])
            record_id = payload[contract.id_field]
            if store.record_exists(record_id):
                continue
            with store.tx() as cur:
                store.insert_record(cur, payload)
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


def test_si_reference_bindings_are_descriptor_derived():
    active = config.ACTIVE_PROFILE
    bindings = context.SIReferenceBindings.from_descriptor(active)
    regsr = active.reference_family("si.uvhvvr.ffs-reg")
    gerk = active.reference_family("si.mkgp.gerk-layer")
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


def test_si_reference_binding_compatibility_aliases_are_binding_backed():
    bindings = context.SI_REFERENCE_BINDINGS

    assert bindings == context.SIReferenceBindings.from_descriptor(config.ACTIVE_PROFILE)
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
    with pytest.raises(ProfileRuntimeError, match="active_descriptor and active_profile"):
        GatePipeline(
            object(),
            active_descriptor=config.ACTIVE_PROFILE,
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


def test_explicit_descriptor_optional_missing_reference_family_is_omitted(fresh_env):
    store, _, _ = fresh_env
    active = replace(
        config.ACTIVE_PROFILE,
        reference_families=config.ACTIVE_PROFILE.reference_families
        + (_missing_family(required=False),),
    )

    with store.tx() as cur:
        snap = context.ContextAssembler(
            store,
            active_profile=active,
        ).assemble(cur, demo.FARM)

    assert not any(
        ref.startswith("referencesnapshot:test.missing-family")
        for ref in snap["referenceSnapshotRefs"]
    )


def test_explicit_descriptor_required_missing_reference_family_refuses(fresh_env):
    store, _, _ = fresh_env
    active = replace(
        config.ACTIVE_PROFILE,
        reference_families=config.ACTIVE_PROFILE.reference_families
        + (_missing_family(required=True),),
    )

    with pytest.raises(context.ContextNotReconstructible, match="required reference family"):
        with store.tx() as cur:
            context.ContextAssembler(
                store,
                active_profile=active,
            ).assemble(cur, demo.FARM)


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


def test_explicit_descriptor_mismatched_spine_ref_fails_without_config_fallback(
        fresh_env):
    store, _, _ = fresh_env
    active = replace(
        config.ACTIVE_PROFILE,
        active_artifact_set_ref="activeartifactset:si.ffs.not-selected.v0_1",
    )

    with pytest.raises(context.ContextNotReconstructible, match="matched 0"):
        with store.tx() as cur:
            context.ContextAssembler(
                store,
                active_profile=active,
            ).assemble(cur, demo.FARM)


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


def test_gate_pipeline_explicit_active_profile_matches_default_for_clean_operation(
        fresh_env):
    store, default_pipeline, _ = fresh_env
    explicit_pipeline = GatePipeline(store, active_profile=config.ACTIVE_PROFILE)

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


def test_global_operation_sequence_uses_named_compatibility_constructors():
    assert validators.OPERATION_SEQUENCE[1].validation_policy is \
        validators._CONFIG_BACKED_POLICY
    assert validators.OPERATION_SEQUENCE[2].validation_policy is \
        validators._CONFIG_BACKED_POLICY
    assert validators.OPERATION_SEQUENCE[5].validation_policy is \
        validators._CONFIG_BACKED_POLICY
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
    assert validators._descriptor_recognized_rule_refs(config.ACTIVE_PROFILE) == \
        frozenset({
            config.ACTIVE_PROFILE.evidence_policy_ref,
            config.ACTIVE_PROFILE.profile_ref,
            config.ACTIVE_PROFILE.pack_ref,
            config.ACTIVE_PROFILE.code_binding_profile_ref,
        })


def test_profile_applicability_wrong_pack_profile_is_governed_refusal():
    def mutate(_profile, activation, artifact):
        activation["activePackRefs"] = ["pack:si.ffs.dirty.v0_1"]
        activation["activeProfileRefs"] = ["profile:si.ffs.dirty.v0_1"]
        artifact["activePackRefs"] = ["pack:si.ffs.dirty.v0_1"]
        artifact["activeProfileRefs"] = ["profile:si.ffs.dirty.v0_1"]

    with _preseeded_dirty_spine_store(mutate) as store:
        result = GatePipeline(store).commit(_note_submission(
            f"issue125-pack-profile:{_uid()}"))
        trace = _assert_profile_applicability_refusal(store, result)
        assert "descriptor packRef" in trace["gateSequence"][-1]["rationale"]


def test_profile_applicability_missing_evidence_policy_is_governed_refusal():
    def mutate(_profile, _activation, artifact):
        artifact["activeArtifactRefs"] = [
            ref for ref in artifact["activeArtifactRefs"]
            if ref != config.ACTIVE_PROFILE.evidence_policy_ref
        ]

    with _preseeded_dirty_spine_store(mutate) as store:
        result = GatePipeline(store).commit(_note_submission(
            f"issue125-policy-missing:{_uid()}"))
        trace = _assert_profile_applicability_refusal(store, result)
        assert "evidence policy" in trace["gateSequence"][-1]["rationale"]


def test_profile_applicability_missing_descriptor_artifact_is_governed_refusal(
        fresh_env):
    store, _, _ = fresh_env
    active = replace(
        config.ACTIVE_PROFILE,
        active_artifact_set_ref="activeartifactset:si.ffs.issue125.missing.v0_1",
    )

    result = GatePipeline(store, active_profile=active).commit(_note_submission(
        f"issue125-artifact-missing:{_uid()}"))

    trace = _assert_profile_applicability_refusal(store, result)
    assert "matched 0" in trace["gateSequence"][-1]["rationale"]


def test_profile_applicability_required_reference_family_is_governed_refusal(
        fresh_env):
    store, _, _ = fresh_env
    active = replace(
        config.ACTIVE_PROFILE,
        reference_families=config.ACTIVE_PROFILE.reference_families
        + (_missing_family(required=True),),
    )

    result = GatePipeline(store, active_profile=active).commit(_note_submission(
        f"issue125-ref-family:{_uid()}"))

    trace = _assert_profile_applicability_refusal(store, result)
    assert "required reference family" in trace["gateSequence"][-1]["rationale"]


def test_profile_applicability_missing_context_spine_is_governed_refusal():
    with _fresh_unbootstrapped_store() as store:
        _bootstrap_demo_substrate_only(store)

        result = GatePipeline(store).commit(_note_submission(
            f"issue137-missing-spine:{_uid()}"))

        trace = _assert_profile_applicability_refusal(store, result)
        assert "context spine not bootstrapped" in \
            trace["gateSequence"][-1]["rationale"]
        assert result["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"


def test_materializer_missing_context_spine_refuses_use_governably():
    with _fresh_unbootstrapped_store() as store:
        materializer = Materializer(store)

        with store.tx() as cur:
            result = materializer.resolve_for_use(cur, demo.FARM)

        assert result["decision"] == "REFUSE_USE"
        assert result["freshness"] == "INVALID"
        assert result["contextSnapshotRef"] == "contextsnapshot:not-reconstructible"
        assert result["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"
        assert "context spine not bootstrapped" in result["problems"][0]["detail"]


def test_api_commit_returns_governed_profile_applicability_refusal_not_500():
    def mutate(_profile, _activation, artifact):
        artifact["activeArtifactRefs"] = [
            ref for ref in artifact["activeArtifactRefs"]
            if ref != config.ACTIVE_PROFILE.evidence_policy_ref
        ]

    with _preseeded_dirty_spine_store(mutate) as store:
        from fastapi.testclient import TestClient
        from kernel.api import create_app

        client = TestClient(create_app(store, oidc=None))
        sub = _note_submission(f"issue125-api:{_uid()}")
        response = client.post(
            "/commit",
            json={"submission": sub},
            headers={"x-acting-party": demo.FARMER},
        )

        assert response.status_code == 200
        payload = response.json()
        _assert_profile_applicability_refusal(store, payload)


def test_product_register_boundary_remains_single_active_si_runtime():
    assert config.ACTIVE_PROFILE_PACKAGE_NAMES == ("profile_si_ffs",)
    assert config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES == ("profile_si_ffs",)
    assert config.ACTIVE_PROFILE_SELECTION.profile_package_names == ("profile_si_ffs",)
    assert context.SI_REFERENCE_BINDINGS == context.SIReferenceBindings.from_descriptor(
        config.ACTIVE_PROFILE)
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


def test_product_register_load_from_store_uses_bindings_and_family_boundary(
        tmp_path):
    descriptor, _, _decision = _custom_si_descriptor_with_regsr_artifact(tmp_path)
    bindings = context.SIReferenceBindings.from_descriptor(descriptor)
    file_decision = f"U9{_uid()[:4]}-50/26/f"
    file_artifact = bindings.si_profile_root / "examples" / "store_file_regsr.json"
    file_artifact.write_text(json.dumps(_regsr_artifact(decision=file_decision)),
                             encoding="utf-8")
    store_decision = f"U9{_uid()[:4]}-50/26/s"

    class FakeStore:
        requested_families: list[str] = []

        def reference_data(self, family):
            self.requested_families.append(family)
            return [{
                "snapshot_ref": f"{bindings.regsr_snapshot_prefix}.store",
                "payload": _regsr_artifact(decision=store_decision),
            }]

        def find_by_kind(self, kind):
            assert kind == "ofarm.referencesnapshot.v0.1"
            return [
                {
                    "payload": {
                        "referenceSnapshotId": f"{bindings.regsr_snapshot_prefix}extra",
                        "sourceArtifactRefs": [f"artifact:{file_artifact.name}"],
                    }
                },
                {
                    "payload": {
                        "referenceSnapshotId": f"{bindings.regsr_snapshot_prefix}.file",
                        "sourceArtifactRefs": [f"artifact:{file_artifact.name}"],
                    }
                },
            ]

    store = FakeStore()
    register = context.ProductRegister(bindings)
    register.load_from_store(store)

    assert store.requested_families == [bindings.regsr_data_family]
    assert register.lookup_by_decision(
        f"{bindings.regsr_snapshot_prefix}.store",
        store_decision,
    ) is not None
    assert register.lookup_by_decision(
        f"{bindings.regsr_snapshot_prefix}.file",
        file_decision,
    ) is not None
    assert not register.has_snapshot(f"{bindings.regsr_snapshot_prefix}extra")


def test_gate_pipeline_threads_si_reference_bindings(fresh_env):
    _store, pipeline, _ = fresh_env
    sub = demo.spray_submission(
        f"issue127b-binding-context:{_uid()}",
        erp_id=f"erp:issue127b.binding.{_uid()}",
        confirm=True,
    )

    ctx = pipeline._new_context(None, sub)

    assert pipeline.products.bindings is pipeline.si_reference_bindings
    assert ctx.si_reference_bindings is pipeline.si_reference_bindings


def test_gate_pipeline_omits_si_reference_bindings_when_descriptor_changes(
        fresh_env):
    _store, pipeline, _ = fresh_env
    pipeline.active_profile = replace(
        config.ACTIVE_PROFILE,
        profile_ref="profile:si.ffs.changed-binding-context.v0_1",
    )
    sub = demo.spray_submission(
        f"issue127b-binding-context-mutated:{_uid()}",
        erp_id=f"erp:issue127b.binding.mutated.{_uid()}",
        confirm=True,
    )

    ctx = pipeline._new_context(None, sub)

    assert ctx.si_reference_bindings is None


def test_registry_reverification_prefers_context_si_reference_bindings(
        monkeypatch):
    seen_prefixes = []

    def fake_current_reference_snapshot(_store, prefix):
        seen_prefixes.append(prefix)
        return None

    monkeypatch.setattr(
        validators,
        "current_reference_snapshot",
        fake_current_reference_snapshot,
    )

    binding_payload = {
        "bindingRole": "CROP_PROTECTION_PRODUCT",
        "bindingState": "VERIFIED",
        "bindingValue": {"registrationRef": "U99999-50/26/context"},
        "referenceSnapshotRefs": ["referencesnapshot:old"],
    }

    class FakeStore:
        def get_record(self, ref):
            if ref == "binding:regsr":
                return {
                    "record_kind": sufficiency.BINDING_KIND,
                    "payload": binding_payload,
                }
            return None

    ctx = SimpleNamespace(
        store=FakeStore(),
        sub={"payload": {"agronomicIdentityBindingRefs": ["binding:regsr"]}},
        si_reference_bindings=SimpleNamespace(
            regsr_snapshot_prefix="referencesnapshot:si.custom.regsr"),
    )

    assert validators.RegistryReverificationValidator().run(ctx) is None
    assert seen_prefixes == ["referencesnapshot:si.custom.regsr"]

    ctx.si_reference_bindings = None
    assert validators.RegistryReverificationValidator().run(ctx) is None
    assert seen_prefixes[-1] == context.REGSR_SNAPSHOT_PREFIX


def test_materializer_uses_active_descriptor_for_context_and_policy_freshness(
        fresh_env):
    store, pipeline, _ = fresh_env

    assert pipeline.materializer.active_profile is config.ACTIVE_PROFILE
    assert pipeline.materializer.context.active_profile is config.ACTIVE_PROFILE

    explicit = Materializer(store, active_profile=config.ACTIVE_PROFILE)
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


def test_materializer_dependency_index_uses_descriptor_policy_ref_and_invalidates():
    policy_ref = f"policy:si.ffs.issue125.{_uid()}"

    def mutate(_profile, _activation, artifact):
        artifact["activeArtifactRefs"] = [
            ref for ref in artifact["activeArtifactRefs"]
            if ref != config.ACTIVE_PROFILE.evidence_policy_ref
        ] + [policy_ref]

    with _preseeded_dirty_spine_store(mutate) as store:
        active = replace(config.ACTIVE_PROFILE, evidence_policy_ref=policy_ref)
        materializer = Materializer(store, active_profile=active)

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
