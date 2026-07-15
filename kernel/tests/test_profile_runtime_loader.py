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
    ProfileRuntimeSurfaceInventory,
    ProfileRouteRecord,
    ReferenceFamily,
    evaluate_profile_runtime_preconditions,
    load_active_profile_selection,
    load_profile_descriptor_registry,
    load_profile_runtime_descriptor,
    profile_route_selection_document,
    resolve_profile_route as _resolve_profile_route,
    resolve_active_descriptor,
)
from kernel.runtime_bundle import _build_live_runtime_bundle, build_runtime_bundle
from kernel.stages import (
    AuthorityGate,
    EvidenceSufficiencyGate,
    GatePass,
    GateRefusal,
    IngressNormalizer,
    ProfileApplicabilityGate,
)
from kernel.store import Store
from kernel.views import OutputGenerator


_ACTIVE_TEST_RUNTIME_BUNDLE = build_runtime_bundle(config.ACTIVE_PROFILE)


def resolve_profile_route(*args, **kwargs):
    kwargs.setdefault("runtime_bundle_digest", _ACTIVE_TEST_RUNTIME_BUNDLE.digest)
    return _resolve_profile_route(*args, **kwargs)


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
        "runtime_bundle_digest": _ACTIVE_TEST_RUNTIME_BUNDLE.digest,
    }
    values.update(overrides)
    return ProfileRouteRecord(**values)


def _route_registry(*, enabled=None):
    return load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=(
            config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES
            if enabled is None else enabled
        ),
    )


def _surface_inventory(*package_names: str) -> ProfileRuntimeSurfaceInventory:
    packages = frozenset(package_names)
    return ProfileRuntimeSurfaceInventory(
        adapter_supported_package_names=packages,
        harness_covered_package_names=packages,
        profile_executed_evidence_lane_package_names=packages,
        generated_or_verified_manifest_grounding_package_names=packages,
    )


def _route_pipeline(store, *, routes=None, registry=None, selected=None, tenant=None):
    route_records = tuple([_si_route()] if routes is None else routes)
    route_registry = registry or _route_registry()
    selected_names = tuple(
        config.ACTIVE_PROFILE_PACKAGE_NAMES if selected is None else selected)
    tenant_ref = config.TENANT_REF if tenant is None else tenant
    selection = profile_route_selection_document(
        route_registry, selected_names, route_records, tenant_ref=tenant_ref)
    route_store = Store(dsn=store.dsn)
    # The fresh-env owner closes this shared connection at teardown; using the
    # same connection avoids leaving a second backend attached to the test DB.
    Store._raw_connection(store)
    route_store._conn = store._conn
    context.bootstrap_for_descriptor(
        route_store,
        config.ACTIVE_PROFILE,
        profile_route_selection=selection,
    )
    receipted_routes = tuple(
        replace(route, runtime_bundle_digest=route_store.runtime_bundle_digest)
        for route in route_records)
    return GatePipeline(
        route_store,
        profile_route_records=receipted_routes,
        profile_route_registry=route_registry,
        selected_profile_package_names=selected_names,
        tenant_ref=tenant_ref,
    )


def _route_interval(month: str, *, route_id: str | None = None) -> ProfileRouteRecord:
    start = datetime.fromisoformat(f"2026-{month}-01T00:00:00+00:00")
    end = datetime.fromisoformat(f"2026-{int(month) + 1:02d}-01T00:00:00+00:00")
    return _si_route(
        route_id=route_id or f"profileroute:test.si.{month}.{_uid()}",
        effective_from=start,
        effective_until=end,
    )


def _assert_profile_route_refusal(store, result: dict) -> dict:
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    trace = _trace_payload(store, result)
    assert [entry["gate"] for entry in trace["gateSequence"]] == [
        "INGRESS_NORMALIZATION",
        "PACK_PROFILE_APPLICABILITY",
    ]
    assert trace["gateSequence"][-1]["outcome"] == "PROFILE_ROUTE_REFUSE"
    return trace


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
    profile = _profile_instance_payload(
        "agronomicCodeBindingProfileId",
        config.ACTIVE_PROFILE.code_binding_profile_ref)
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

    with store.serialized_tx() as cur:
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
        if payload.get("schemaVersion") not in {
                "ofarm.activeartifactset.v0.1",
                "ofarm.packactivationset.v0.1"}:
            continue
        contract = store.registry.get(payload["schemaVersion"])
        expected.append(payload[contract.id_field])
    return expected


def _bootstrap_demo_substrate_only(store) -> None:
    for payload in demo.substrate_records():
        contract = store.registry.get(payload["schemaVersion"])
        record_id = payload[contract.id_field]
        if store.record_exists(record_id):
            continue
        with store.serialized_tx() as cur:
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
        original_profile = copy.deepcopy(profile)
        activation = _profile_instance_payload(
            "packActivationSetId",
            config.ACTIVE_PROFILE.pack_activation_set_ref)
        artifact = _profile_instance_payload(
            "activeArtifactSetId",
            config.ACTIVE_PROFILE.active_artifact_set_ref)
        mutate(profile, activation, artifact)
        with store.serialized_tx() as cur:
            bundle = _build_live_runtime_bundle(
                config.ACTIVE_PROFILE,
                _database_environment=store._observe_database_environment(cur),
            )
            store.install_runtime_bundle(cur, bundle)
            with store._bootstrap_bundle_writes(bundle):
                if profile != original_profile:
                    store.insert_record(
                        cur, profile, runtime_bundle_digest=bundle.digest)
                store.insert_record(cur, activation, runtime_bundle_digest=bundle.digest)
                store.insert_record(cur, artifact, runtime_bundle_digest=bundle.digest)
        context.bootstrap(store)
        for payload in demo.substrate_records():
            contract = store.registry.get(payload["schemaVersion"])
            record_id = payload[contract.id_field]
            if store.record_exists(record_id):
                continue
            with store.serialized_tx() as cur:
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
    assert context.PROFILE_INSTANCE_FILES == tuple(active.profile_instance_files)
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
    provider = profile_policy.DescriptorPolicyProvider(
        config.ACTIVE_PROFILE, runtime_bundle=_ACTIVE_TEST_RUNTIME_BUNDLE)
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
    provider = profile_policy.DescriptorPolicyProvider(
        config.ACTIVE_PROFILE, runtime_bundle=_ACTIVE_TEST_RUNTIME_BUNDLE)
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
        [sys.executable, "-B", "-c", "import kernel.config"],
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


def test_profile_runtime_preconditions_are_passive_for_active_runtime(fresh_store, fresh_pipeline):
    store, pipeline = fresh_store, fresh_pipeline
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


def test_profile_route_rejects_runtime_bundle_digest_mismatch():
    registry = load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    )
    route = _si_route(runtime_bundle_digest="sha256:" + "0" * 64)

    with pytest.raises(ProfileRuntimeError, match="RuntimeBundle digest"):
        resolve_profile_route(
            registry,
            config.ACTIVE_PROFILE_PACKAGE_NAMES,
            [route],
            tenant_ref=config.TENANT_REF,
            farm_ref=demo.FARM,
        )


def test_profile_route_selection_preimage_excludes_only_bundle_receipt():
    registry = _route_registry()
    original = _si_route()
    changed_receipt = replace(
        original, runtime_bundle_digest="sha256:" + "0" * 64)
    first = profile_route_selection_document(
        registry, config.ACTIVE_PROFILE_PACKAGE_NAMES, [original],
        tenant_ref=config.TENANT_REF)
    second = profile_route_selection_document(
        registry, config.ACTIVE_PROFILE_PACKAGE_NAMES, [changed_receipt],
        tenant_ref=config.TENANT_REF)
    assert first == second
    assert first != profile_route_selection_document(
        registry,
        config.ACTIVE_PROFILE_PACKAGE_NAMES,
        [replace(original, status="DRAFT")],
        tenant_ref=config.TENANT_REF,
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


def test_descriptor_rejects_required_non_context_reference_family(tmp_path):
    def mutate(doc):
        family = doc["referenceFamilies"][0]
        family["includeInContext"] = False
        family["requiredForNowContext"] = True
        family["missingFamilyBehaviorNow"] = "REFUSE_CONTEXT"

    with pytest.raises(ProfileRuntimeError, match="includeInContext false"):
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


def test_optional_missing_reference_family_is_omitted(fresh_store):
    store = fresh_store
    descriptor = replace(
        config.ACTIVE_PROFILE,
        reference_families=config.ACTIVE_PROFILE.reference_families
        + (_missing_family(required=False),),
    )

    snapshots = context.context_reference_snapshots_for_descriptor(
        store, descriptor)

    assert not any(
        snapshot["referenceSnapshotId"].startswith(
            "referencesnapshot:test.missing-family")
        for snapshot in snapshots
    )


def test_required_missing_reference_family_refuses_context(fresh_store):
    store = fresh_store
    descriptor = replace(
        config.ACTIVE_PROFILE,
        reference_families=config.ACTIVE_PROFILE.reference_families
        + (_missing_family(required=True),),
    )

    with pytest.raises(context.ContextNotReconstructible, match="required reference family"):
        context.context_reference_snapshots_for_descriptor(store, descriptor)


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


def test_explicit_descriptor_reference_snapshots_match_wrapper(fresh_store):
    store = fresh_store

    explicit = context.context_reference_snapshots_for_descriptor(
        store,
        config.ACTIVE_PROFILE,
    )
    implicit = context.context_reference_snapshots(store)

    assert explicit == implicit


def test_explicit_descriptor_context_assembly_matches_wrapper(fresh_store):
    store = fresh_store

    with store.serialized_tx() as cur:
        implicit = context.ContextAssembler(store).assemble(cur, demo.FARM)
    with store.serialized_tx() as cur:
        explicit = context.ContextAssembler(
            store,
            active_profile=config.ACTIVE_PROFILE,
        ).assemble(cur, demo.FARM)

    assert explicit == implicit


def test_explicit_descriptor_asof_context_matches_wrapper(fresh_store):
    store = fresh_store
    policy = {"policyType": "AS_OF", "asOfTime": "2026-12-01T00:00:00Z"}

    with store.serialized_tx() as cur:
        implicit = context.ContextAssembler(store).assemble(
            cur,
            demo.FARM,
            evaluation_time_policy=policy,
        )
    with store.serialized_tx() as cur:
        explicit = context.ContextAssembler(
            store,
            active_profile=config.ACTIVE_PROFILE,
        ).assemble(
            cur,
            demo.FARM,
            evaluation_time_policy=policy,
        )

    assert explicit == implicit


def test_explicit_descriptor_reference_family_change_requires_new_bundle(fresh_store):
    store = fresh_store
    active = replace(
        config.ACTIVE_PROFILE,
        reference_families=config.ACTIVE_PROFILE.reference_families
        + (_missing_family(required=False),),
    )

    with pytest.raises(ProfileRuntimeError, match="RuntimeBundle do not match exactly"):
        context.ContextAssembler(store, active_profile=active)


def test_explicit_descriptor_required_family_change_requires_new_bundle(fresh_store):
    store = fresh_store
    active = replace(
        config.ACTIVE_PROFILE,
        reference_families=config.ACTIVE_PROFILE.reference_families
        + (_missing_family(required=True),),
    )

    with pytest.raises(ProfileRuntimeError, match="RuntimeBundle do not match exactly"):
        context.ContextAssembler(store, active_profile=active)


def test_now_context_uses_descriptor_spine_not_later_store_rows(fresh_store):
    store = fresh_store
    decoy = _insert_decoy_spine(store)

    with store.serialized_tx() as cur:
        snap = context.ContextAssembler(store).assemble(cur, demo.FARM)

    assert snap["activeArtifactSetRef"] == config.ACTIVE_PROFILE.active_artifact_set_ref
    assert snap["sourcePackActivationSetRefs"] == [
        config.ACTIVE_PROFILE.pack_activation_set_ref
    ]
    assert decoy["artifact"] != snap["activeArtifactSetRef"]
    assert decoy["activation"] not in snap["sourcePackActivationSetRefs"]


def test_explicit_descriptor_now_context_uses_descriptor_spine_not_later_store_rows(
        fresh_store):
    store = fresh_store
    decoy = _insert_decoy_spine(store)

    with store.serialized_tx() as cur:
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
        fresh_store):
    store = fresh_store
    active = replace(
        config.ACTIVE_PROFILE,
        active_artifact_set_ref="activeartifactset:si.ffs.not-selected.v0_1",
    )

    with pytest.raises(ProfileRuntimeError, match="RuntimeBundle do not match exactly"):
        context.ContextAssembler(store, active_profile=active)


def test_now_context_refuses_descriptor_id_spine_with_wrong_pack_profile():
    bad_pack = "pack:si.ffs.dirty.v0_1"
    bad_profile = "profile:si.ffs.dirty.v0_1"

    def mutate(_profile, activation, artifact):
        activation["activePackRefs"] = [bad_pack]
        activation["activeProfileRefs"] = [bad_profile]
        artifact["activePackRefs"] = [bad_pack]
        artifact["activeProfileRefs"] = [bad_profile]

    with pytest.raises(context.ContextNotReconstructible,
                       match="already bound to different canonical content"):
        with _preseeded_dirty_spine_store(mutate):
            pass


def test_now_context_refuses_descriptor_id_spine_missing_evidence_policy():
    def mutate(_profile, _activation, artifact):
        artifact["activeArtifactRefs"] = [
            ref for ref in artifact["activeArtifactRefs"]
            if ref != config.ACTIVE_PROFILE.evidence_policy_ref
        ]

    with pytest.raises(context.ContextNotReconstructible,
                       match="is reused for different canonical content"):
        with _preseeded_dirty_spine_store(mutate):
            pass


def test_now_context_refuses_descriptor_id_profile_wrong_pack_scope():
    def mutate(profile, _activation, _artifact):
        profile["profileScope"]["packRefs"] = ["pack:si.ffs.dirty.v0_1"]

    with pytest.raises(context.ContextNotReconstructible,
                       match="tenant-origin profile instance.*collides"):
        with _preseeded_dirty_spine_store(mutate):
            pass


def test_gate_pipeline_explicit_active_profile_matches_default_for_clean_operation(
        fresh_store, fresh_pipeline):
    store, default_pipeline = fresh_store, fresh_pipeline
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


def test_gate_pipeline_default_sequence_remains_unrouted(fresh_store, fresh_pipeline):
    store, pipeline = fresh_store, fresh_pipeline

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
        fresh_store, fresh_pipeline):
    store, pipeline = fresh_store, fresh_pipeline
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


def test_route_backed_gate_pipeline_accepts_clean_si_operation(fresh_store, fresh_pipeline):
    store, default_pipeline = fresh_store, fresh_pipeline
    routed_pipeline = _route_pipeline(store)

    default = default_pipeline.commit(demo.spray_submission(
        f"mp7-default-clean:{_uid()}",
        erp_id=f"erp:mp7.default.clean.{_uid()}",
        confirm=True,
    ))
    routed = routed_pipeline.commit(demo.spray_submission(
        f"mp7-routed-clean:{_uid()}",
        erp_id=f"erp:mp7.routed.clean.{_uid()}",
        confirm=True,
    ))

    assert default["decisionOutcome"] == routed["decisionOutcome"] == \
        "PROMOTE_ACCEPTED"
    assert default.get("problems", []) == routed.get("problems", []) == []
    trace = _trace_payload(store, routed)
    assert [entry["gate"] for entry in trace["gateSequence"]][:3] == [
        "INGRESS_NORMALIZATION",
        "PACK_PROFILE_APPLICABILITY",
        "AUTHORITY",
    ]
    assert trace["gateSequence"][1]["outcome"] == "PROFILE_ROUTE_PASS"


def test_route_backed_pipeline_freezes_caller_selection_sequences(fresh_store):
    store = fresh_store
    routes = [_si_route()]
    selected = list(config.ACTIVE_PROFILE_PACKAGE_NAMES)
    pipeline = _route_pipeline(store, routes=routes, selected=selected)
    expected_routes = pipeline.profile_route_records
    expected_selected = pipeline.selected_profile_package_names

    routes.clear()
    selected.append("profile_hostile_mutation")

    assert pipeline.profile_route_records == expected_routes
    assert pipeline.selected_profile_package_names == expected_selected
    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-frozen:{_uid()}",
        erp_id=f"erp:mp7.route.frozen.{_uid()}",
        confirm=True,
    ))
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_route_backed_pipeline_rejects_same_digest_different_route(fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(store)
    changed = replace(pipeline.profile_route_records[0], status="DRAFT")
    with pytest.raises(ProfileRuntimeError, match="differs from the RuntimeBundle"):
        GatePipeline(
            pipeline.store,
            profile_route_records=[changed],
            profile_route_registry=pipeline.profile_route_registry,
            selected_profile_package_names=pipeline.selected_profile_package_names,
            tenant_ref=pipeline.tenant_ref,
        )


@pytest.mark.parametrize("routes,match", [
    ([], "no active profile route"),
    ([_si_route(), _si_route()], "multiple active overlapping"),
])
def test_route_backed_gate_pipeline_refuses_route_resolution_failures(
        fresh_store, routes, match):
    store = fresh_store
    pipeline = _route_pipeline(store, routes=routes)

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-fail:{_uid()}",
        erp_id=f"erp:mp7.route.fail.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert match in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_missing_farm_context(fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-no-farm:{_uid()}",
        erp_id=f"erp:mp7.route.no-farm.{_uid()}",
        confirm=True,
    )
    sub["targetScopes"] = [{"scopeType": "FIELD", "scopeRef": "field:demo.no-farm"}]

    result = pipeline.commit(sub)

    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_farm_ref_scope_mismatch(fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-farm-mismatch:{_uid()}",
        erp_id=f"erp:mp7.route.farm-mismatch.{_uid()}",
        confirm=True,
    )
    sub["farmRef"] = "farm:demo.other"
    sub["targetScopes"] = [{"scopeType": "FARM", "scopeRef": demo.FARM}]

    result = pipeline.commit(sub)

    assert "must match the top-level submission farmRef" in \
        result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


@pytest.mark.parametrize("scopes", [
    [
        {"scopeType": "FARM", "scopeRef": demo.FARM},
        {"scopeType": "FARM", "scopeRef": demo.FARM},
    ],
    [
        {"scopeType": "FARM", "scopeRef": demo.FARM},
        {"scopeType": "FARM", "scopeRef": "farm:demo.other"},
    ],
])
def test_route_backed_gate_pipeline_refuses_multiple_farm_scope_entries(
        fresh_store, scopes):
    store = fresh_store
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-multiple-farm:{_uid()}",
        erp_id=f"erp:mp7.route.multiple-farm.{_uid()}",
        confirm=True,
    )
    sub["targetScopes"] = scopes

    result = pipeline.commit(sub)

    assert "exactly one FARM anchor scope entry" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


@pytest.mark.parametrize("malformed_farm_scope", [
    {"scopeType": "FARM"},
    {"scopeType": "FARM", "scopeRef": ""},
])
def test_route_backed_gate_pipeline_counts_malformed_farm_scope_entries(
        fresh_store, malformed_farm_scope):
    store = fresh_store
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-malformed-farm:{_uid()}",
        erp_id=f"erp:mp7.route.malformed-farm.{_uid()}",
        confirm=True,
    )

    with pipeline.store.serialized_tx() as cur:
        ctx = pipeline._new_context(cur, sub)
        ctx.envelope = {
            "anchorScopes": [
                {"scopeType": "FARM", "scopeRef": demo.FARM},
                malformed_farm_scope,
            ],
        }
        outcome = pipeline._resolve_profile_route(ctx)

    assert outcome.final_outcome == "RETAIN_DRAFT"
    assert outcome.problems[0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert "exactly one FARM anchor scope entry" in outcome.problems[0]["detail"]
    assert ctx.gate_sequence[-1]["gate"] == "PACK_PROFILE_APPLICABILITY"
    assert ctx.gate_sequence[-1]["outcome"] == "PROFILE_ROUTE_REFUSE"


def test_route_backed_gate_pipeline_refuses_same_context_time_bounded_route(
        fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(
        store,
        routes=[
            _route_interval("06"),
            _si_route(route_id=f"profileroute:test.si.timeless.{_uid()}"),
        ],
    )

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-time-bound:{_uid()}",
        erp_id=f"erp:mp7.route.time-bound.{_uid()}",
        confirm=True,
    ))

    assert "multiple active overlapping" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_accepts_time_bounded_operation_route(
        fresh_store):
    store = fresh_store
    route = _route_interval("06")
    pipeline = _route_pipeline(store, routes=[route])

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-june:{_uid()}",
        erp_id=f"erp:mp7.route.june.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    trace = _trace_payload(store, result)
    assert trace["gateSequence"][1]["outcome"] == "PROFILE_ROUTE_PASS"
    assert route.route_id in trace["gateSequence"][1]["relatedArtifactRefs"]


def test_route_backed_gate_pipeline_refuses_operation_outside_route_interval(
        fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(store, routes=[_route_interval("05")])

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-outside:{_uid()}",
        erp_id=f"erp:mp7.route.outside.{_uid()}",
        confirm=True,
    ))

    assert "no active profile route" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_missing_event_time_no_captured_fallback(
        fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])
    sub = demo.spray_submission(
        f"mp7-route-no-event:{_uid()}",
        erp_id=f"erp:mp7.route.no-event.{_uid()}",
        confirm=True,
    )
    del sub["eventTime"]
    sub["capturedAt"] = "2026-06-10T07:45:00Z"

    result = pipeline.commit(sub)

    assert "eventTime" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_unparseable_event_time_no_fallback(
        fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])
    sub = demo.spray_submission(
        f"mp7-route-bad-event:{_uid()}",
        erp_id=f"erp:mp7.route.bad-event.{_uid()}",
        confirm=True,
    )
    sub["eventTime"] = "not-a-time"

    result = pipeline.commit(sub)

    assert "eventTime is unparseable" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_operation_decision_time_fallback(
        fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])
    sub = demo.spray_submission(
        f"mp7-route-no-decision-fallback:{_uid()}",
        erp_id=f"erp:mp7.route.no-decision-fallback.{_uid()}",
        confirm=True,
    )
    del sub["eventTime"]
    sub["decisionTime"] = "2026-06-10T10:00:00Z"

    result = pipeline.commit(sub)

    assert "eventTime" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_unsupported_route_time_source(
        fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])

    result = pipeline.commit(_note_submission(
        f"mp7-route-note-unsupported:{_uid()}"))

    assert "unsupported" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_operation_event_time_selects_half_open_route(
        fresh_store):
    store = fresh_store
    may = _route_interval("05", route_id=f"profileroute:test.si.may.{_uid()}")
    june = _route_interval("06", route_id=f"profileroute:test.si.june.{_uid()}")
    pipeline = _route_pipeline(store, routes=[may, june])

    may_result = pipeline.commit(demo.spray_submission(
        f"mp7-route-may:{_uid()}",
        erp_id=f"erp:mp7.route.may.{_uid()}",
        confirm=True,
        event_start="2026-05-15T07:30:00Z",
        event_end="2026-05-15T08:15:00Z",
    ))
    june_result = pipeline.commit(demo.spray_submission(
        f"mp7-route-june-boundary:{_uid()}",
        erp_id=f"erp:mp7.route.june-boundary.{_uid()}",
        confirm=True,
        event_start="2026-06-01T00:00:00Z",
        event_end="2026-06-01T01:00:00Z",
    ))

    assert may.route_id in _trace_payload(store, may_result)["gateSequence"][1][
        "relatedArtifactRefs"]
    assert june.route_id in _trace_payload(store, june_result)["gateSequence"][1][
        "relatedArtifactRefs"]


def test_route_backed_gate_pipeline_ignores_other_farm_time_bounded_route(
        fresh_store):
    store = fresh_store
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pipeline = _route_pipeline(
        store,
        routes=[
            _si_route(farm_ref="farm:demo.other", effective_from=t0),
            _si_route(route_id=f"profileroute:test.si.timeless.{_uid()}"),
        ],
    )

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-other-farm-time:{_uid()}",
        erp_id=f"erp:mp7.route.other-farm-time.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_route_backed_gate_pipeline_rejects_other_tenant_route_storage(
        fresh_store):
    store = fresh_store
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ProfileRuntimeError, match="another tenant's route"):
        _route_pipeline(
            store,
            routes=[
                _si_route(tenant_ref="tenant:demo.other", effective_from=t0),
                _si_route(route_id=f"profileroute:test.si.timeless.{_uid()}"),
            ],
        )


def test_route_backed_gate_pipeline_ignores_inactive_time_bounded_route(
        fresh_store):
    store = fresh_store
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pipeline = _route_pipeline(
        store,
        routes=[
            _si_route(status="DRAFT", effective_from=t0),
            _si_route(route_id=f"profileroute:test.si.timeless.{_uid()}"),
        ],
    )

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-inactive-time:{_uid()}",
        erp_id=f"erp:mp7.route.inactive-time.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def _governance_submission(idem_key: str, *, decision_time=None,
                           event_time=None, target="assert:demo.pending") -> dict:
    sub = {
        "commitClass": "GOVERNANCE_DECISION",
        "actingPartyRef": demo.FARMER,
        "farmRef": demo.FARM,
        "idempotencyKey": idem_key,
        "reviewTargetAssertionRef": target,
        "reviewRationale": "route-time policy probe",
    }
    if decision_time is not None:
        sub["decisionTime"] = decision_time
    if event_time is not None:
        sub["eventTime"] = event_time
    return sub


def test_route_backed_gate_pipeline_governance_uses_decision_time(fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])
    # Queue and review under the same receipted route selection. Crossing from
    # the default bundle into this route bundle is an automatic migration and
    # must remain a PACK_CONFLICT refusal.
    queued = pipeline.commit(demo.spray_submission(
        f"mp7-governance-queued:{_uid()}",
        erp_id=f"erp:mp7.governance.queued.{_uid()}",
        confirm=False,
    ))

    result = pipeline.commit(_governance_submission(
        f"mp7-governance-accept:{_uid()}",
        decision_time="2026-06-10T10:00:00Z",
        event_time="2026-05-10T10:00:00Z",
        target=queued["emittedAssertionRecordRefs"][0],
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    trace = _trace_payload(store, result)
    assert trace["gateSequence"][1]["outcome"] == "PROFILE_ROUTE_PASS"


@pytest.mark.parametrize("decision_time,match", [
    (None, "decisionTime"),
    ("not-a-time", "decisionTime"),
])
def test_route_backed_gate_pipeline_governance_requires_decision_time(
        fresh_store, decision_time, match):
    store = fresh_store
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])

    result = pipeline.commit(_governance_submission(
        f"mp7-governance-no-decision:{_uid()}",
        decision_time=decision_time,
        event_time="2026-06-10T10:00:00Z",
    ))

    assert match in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_governance_does_not_use_event_time_fallback(
        fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])

    result = pipeline.commit(_governance_submission(
        f"mp7-governance-event-fallback:{_uid()}",
        decision_time="2026-05-10T10:00:00Z",
        event_time="2026-06-10T10:00:00Z",
    ))

    assert "no active profile route" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


@pytest.mark.parametrize("package_name", [
    "profile_nl_go_glmc7_2026",
    "profile_rs_organic_crop",
])
def test_route_backed_gate_pipeline_refuses_design_only_route_target(
        fresh_store, package_name):
    if not (config.PACKAGE_ROOT / package_name).exists():
        pytest.skip(f"{package_name} is not present in this checkout")
    store = fresh_store
    pipeline = _route_pipeline(
        store,
        routes=[_si_route(profile_package_name=package_name)],
        registry=_route_registry(enabled=("profile_si_ffs", package_name)),
        selected=("profile_si_ffs", package_name),
    )

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-design-only:{_uid()}",
        erp_id=f"erp:mp7.route.design-only.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    trace = _trace_payload(store, result)
    assert trace["gateSequence"][-1]["gate"] == "PACK_PROFILE_APPLICABILITY"
    assert trace["gateSequence"][-1]["outcome"] == "PROFILE_ROUTE_REFUSE"


def test_route_backed_gate_pipeline_uses_descriptor_backed_policy_paths(
        fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(store)

    submission = demo.spray_submission(
        f"mp7-route-provider:{_uid()}",
        erp_id=f"erp:mp7.route.provider.{_uid()}",
        confirm=True,
    )
    result = pipeline.commit(submission)

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert type(pipeline.policy_provider) is \
        profile_policy.DescriptorPolicyProvider


def test_route_backed_handoff_binds_materializer_to_resolved_descriptor(fresh_store):
    store = fresh_store
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-bind:{_uid()}",
        erp_id=f"erp:mp7.route.bind.{_uid()}",
        confirm=True,
    )

    with pipeline.store.serialized_tx() as cur:
        ctx = pipeline._new_context(cur, sub)
        ingress = IngressNormalizer().run(ctx)
        assert not hasattr(ingress, "result")
        assert pipeline._resolve_profile_route(ctx) is None

    assert ctx.profile_route_resolution.descriptor == config.ACTIVE_PROFILE
    assert ctx.active_profile == ctx.profile_route_resolution.descriptor
    assert ctx.materializer.active_profile == ctx.profile_route_resolution.descriptor
    assert ctx.materializer.context.active_profile == ctx.profile_route_resolution.descriptor
    assert ctx.context_assembler.active_profile == ctx.profile_route_resolution.descriptor
    assert ctx.policy_provider.descriptor == ctx.profile_route_resolution.descriptor
    assert ctx.si_reference_bindings.regsr_shipped_snapshot_ref == \
        context.SI_REFERENCE_BINDINGS.regsr_shipped_snapshot_ref


def test_route_resolver_swap_cannot_bypass_effective_time_and_rolls_back(
        fresh_store):
    from kernel import gates as gates_module
    from kernel.runtime_bundle import RuntimeBundleError

    pipeline = _route_pipeline(
        fresh_store,
        routes=[_route_interval("05")],
    )
    store = pipeline.store
    submission = demo.spray_submission(
        f"issue171-route-resolver:{_uid()}",
        erp_id=f"erp:issue171.route-resolver.{_uid()}",
        confirm=True,
    )
    marker_id = f"party:issue171.route-resolver.{_uid()}"
    original = gates_module.resolve_profile_route
    hostile_called = False
    ctx = None

    def hostile_resolver(*args, **kwargs):
        nonlocal hostile_called
        hostile_called = True
        gates_module.resolve_profile_route = original
        kwargs["effective_time"] = datetime(
            2026, 5, 15, tzinfo=timezone.utc)
        return original(*args, **kwargs)

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": marker_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 route rollback marker (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            GatePipeline._assert_runtime_composition(pipeline)
            ctx = GatePipeline._new_context(pipeline, cur, submission)
            assert isinstance(IngressNormalizer().run(ctx), GatePass)

            gates_module.resolve_profile_route = hostile_resolver
            try:
                with pytest.raises(
                        RuntimeBundleError,
                        match="retained profile route resolver changed"):
                    GatePipeline._resolve_profile_route(pipeline, ctx)
                assert store._active_transaction_integrity.poisoned is True
            finally:
                gates_module.resolve_profile_route = original

    assert hostile_called is False
    assert ctx is not None
    assert ctx.profile_route_resolution is None
    assert store.get_record(marker_id) is None


def test_route_wrapper_swap_cannot_skip_retained_resolution_and_rolls_back(
        fresh_store):
    from kernel import gates as gates_module
    from kernel.runtime_bundle import RuntimeBundleError

    pipeline = _route_pipeline(
        fresh_store,
        routes=[_route_interval("06")],
    )
    store = pipeline.store
    submission = demo.spray_submission(
        f"issue171-route-wrapper:{_uid()}",
        erp_id=f"erp:issue171.route-wrapper.{_uid()}",
        confirm=True,
    )
    marker_id = f"party:issue171.route-wrapper.{_uid()}"
    original = GatePipeline._resolve_profile_route
    hostile_called = False
    ctx = None

    def hostile_wrapper(instance, context_value):
        nonlocal hostile_called
        hostile_called = True
        GatePipeline._resolve_profile_route = original
        return None

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": marker_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 route-wrapper marker (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            GatePipeline._assert_runtime_composition(pipeline)
            ctx = GatePipeline._new_context(pipeline, cur, submission)
            assert isinstance(IngressNormalizer().run(ctx), GatePass)

            GatePipeline._resolve_profile_route = hostile_wrapper
            try:
                with pytest.raises(
                        RuntimeBundleError,
                        match="retained gate callable changed"):
                    gates_module._RETAINED_INVOKE_GATE_CALLABLE(
                        store, pipeline._route_dispatch[0], pipeline, ctx)
                assert store._active_transaction_integrity.poisoned is True
            finally:
                GatePipeline._resolve_profile_route = original

    assert hostile_called is False
    assert ctx is not None
    assert ctx.profile_route_resolution is None
    assert store.get_record(marker_id) is None


def test_forged_exact_route_resolution_is_rejected_and_rolls_back(fresh_store):
    from kernel import gates as gates_module
    from kernel.runtime_bundle import RuntimeBundleError

    pipeline = _route_pipeline(
        fresh_store,
        routes=[_route_interval("06")],
    )
    store = pipeline.store
    submission = demo.spray_submission(
        f"issue171-forged-route:{_uid()}",
        erp_id=f"erp:issue171.forged-route.{_uid()}",
        confirm=True,
    )
    marker_id = f"party:issue171.forged-route.{_uid()}"
    ctx = None

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": marker_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 forged-route marker (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            GatePipeline._assert_runtime_composition(pipeline)
            ctx = GatePipeline._new_context(pipeline, cur, submission)
            assert isinstance(IngressNormalizer().run(ctx), GatePass)
            farm_ref = GatePipeline._route_farm_ref(ctx)
            effective_time = GatePipeline._route_effective_time(ctx)
            genuine = gates_module._PROFILE_ROUTE_RESOLVER[2](
                pipeline.profile_route_registry,
                pipeline.selected_profile_package_names,
                pipeline.profile_route_records,
                tenant_ref=pipeline.tenant_ref,
                farm_ref=farm_ref,
                effective_time=effective_time,
                runtime_bundle_digest=pipeline.runtime_bundle.digest,
            )
            forged = replace(
                genuine,
                effective_time=datetime(2026, 5, 15, tzinfo=timezone.utc),
            )

            with pytest.raises(
                    RuntimeBundleError,
                    match="resolved profile route differs"):
                gates_module._RETAINED_INVOKE_GATE_CALLABLE(
                    store, pipeline._route_dispatch[1], pipeline, ctx, forged,
                    farm_ref=farm_ref,
                    effective_time=effective_time,
                )
            assert store._active_transaction_integrity.poisoned is True

    assert ctx is not None
    assert ctx.profile_route_resolution is None
    assert store.get_record(marker_id) is None


def test_route_model_descriptors_cannot_change_bound_profile(fresh_store):
    from kernel import gates as gates_module
    from kernel import profile_runtime as profile_runtime_module

    pipeline = _route_pipeline(
        fresh_store,
        routes=[_route_interval("06")],
    )
    store = pipeline.store
    submission = demo.spray_submission(
        f"issue171-route-descriptor:{_uid()}",
        erp_id=f"erp:issue171.route-descriptor.{_uid()}",
        confirm=True,
    )
    marker_id = f"party:issue171.route-descriptor.{_uid()}"
    foreign_descriptor = replace(
        pipeline.active_profile,
        evidence_policy_ref="policy:issue171.hostile-route",
    )
    candidate_type = profile_runtime_module.ProfileDescriptorCandidate
    descriptor_type = profile_runtime_module.ProfileRuntimeDescriptor
    original_equality = descriptor_type.__eq__
    descriptor_called = False
    equality_called = False
    ctx = None

    class HostileCandidateDescriptor:
        def __get__(self, candidate, _owner):
            nonlocal descriptor_called
            if candidate is None:
                return self
            descriptor_called = True
            del candidate_type.descriptor
            return foreign_descriptor

        def __set__(self, candidate, value):
            dict.__setitem__(
                object.__getattribute__(candidate, "__dict__"),
                "descriptor", value)

    def hostile_equality(_left, _right):
        nonlocal equality_called
        equality_called = True
        descriptor_type.__eq__ = original_equality
        return True

    class RollbackProbe(Exception):
        pass

    with pytest.raises(RollbackProbe):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": marker_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 route-descriptor marker (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            GatePipeline._assert_runtime_composition(pipeline)
            ctx = GatePipeline._new_context(pipeline, cur, submission)
            assert isinstance(IngressNormalizer().run(ctx), GatePass)

            candidate_type.descriptor = HostileCandidateDescriptor()
            descriptor_type.__eq__ = hostile_equality
            try:
                assert gates_module._RETAINED_INVOKE_GATE_CALLABLE(
                    store, pipeline._route_dispatch[0], pipeline, ctx) is None
                assert ctx.active_profile is pipeline.active_profile
                resolution_namespace = object.__getattribute__(
                    ctx.profile_route_resolution, "__dict__")
                assert dict.__getitem__(
                    resolution_namespace, "descriptor") is pipeline.active_profile
            finally:
                if "descriptor" in vars(candidate_type):
                    del candidate_type.descriptor
                descriptor_type.__eq__ = original_equality
            raise RollbackProbe

    assert descriptor_called is False
    assert equality_called is False
    assert ctx is not None
    assert ctx.active_profile is pipeline.active_profile
    assert store.get_record(marker_id) is None


def test_output_generator_explicit_descriptor_matches_default_profile_refs(fresh_store, fresh_outputs):
    store, outputs = fresh_store, fresh_outputs
    explicit = OutputGenerator(store, active_descriptor=config.ACTIVE_PROFILE)

    default_view = outputs.passport_view(demo.FARM, demo.FARMER)
    explicit_view = explicit.passport_view(demo.FARM, demo.FARMER)

    assert default_view["refused"] is False
    assert explicit_view["refused"] is False
    assert default_view["metadata"]["profileRefs"] == \
        explicit_view["metadata"]["profileRefs"] == [config.ACTIVE_PROFILE.profile_ref]
    assert explicit.materializer.active_profile == config.ACTIVE_PROFILE


def test_descriptor_backed_validation_uses_provider_without_config_wrapper(
        fresh_pipeline):
    pipeline = fresh_pipeline

    submission = demo.spray_submission(
        f"mp3d-validation-provider:{_uid()}",
        erp_id=f"erp:mp3d.validation.provider.{_uid()}",
        confirm=True,
    )
    result = pipeline.commit(submission)

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert pipeline.policy_provider.validation_policy() == \
        pipeline.runtime_bundle.json_component(
            "PROFILE_POLICY", config.ACTIVE_PROFILE.evidence_policy_ref)["validation"]


def test_descriptor_backed_sufficiency_uses_provider_without_config_wrappers(
        fresh_pipeline):
    pipeline = fresh_pipeline

    submission = demo.spray_submission(
        f"mp3d-sufficiency-provider:{_uid()}",
        erp_id=f"erp:mp3d.sufficiency.provider.{_uid()}",
        confirm=True,
    )
    result = pipeline.commit(submission)

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert pipeline.policy_provider.policy_ref == \
        config.ACTIVE_PROFILE.evidence_policy_ref
    assert pipeline.policy_provider.evidence_policy(
        supported_checks=sufficiency.OPERATION_FLOOR_CHECKS,
    ) == pipeline.runtime_bundle.json_component(
        "PROFILE_POLICY", config.ACTIVE_PROFILE.evidence_policy_ref)


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
        fresh_store, fresh_pipeline):
    store, pipeline = fresh_store, fresh_pipeline
    queued = pipeline.commit(demo.spray_submission(
        f"mp3d-accept-queued:{_uid()}",
        erp_id=f"erp:mp3d.accept.queued.{_uid()}",
        confirm=False,
    ))
    assert queued["decisionOutcome"] == "RETAIN_DRAFT"

    submission = {
        "commitClass": "GOVERNANCE_DECISION",
        "actingPartyRef": demo.FARMER,
        "farmRef": demo.FARM,
        "idempotencyKey": f"mp3d-accept:{_uid()}",
        "decisionTime": "2026-06-10T10:00:00Z",
        "reviewTargetAssertionRef": queued["emittedAssertionRecordRefs"][0],
        "reviewRationale": "self-review of a routine operation claim meeting the floor",
    }
    accepted = pipeline.commit(submission)

    assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED"
    case = _case_payload(store, accepted)
    assert case["governingPolicyRefs"] == [config.ACTIVE_PROFILE.evidence_policy_ref]
    assert {arg["policyRef"] for arg in case["arguments"]} == {
        config.ACTIVE_PROFILE.evidence_policy_ref}


def test_descriptor_validation_policy_failure_stops_at_validation(fresh_store, fresh_pipeline):
    store, pipeline = fresh_store, fresh_pipeline

    class FailingValidationPolicyProvider:
        @staticmethod
        def validation_policy():
            raise profile_policy.ProfilePolicyError(
                "descriptor validation unavailable")

    submission = demo.spray_submission(
        f"mp3d-validation-fail:{_uid()}",
        erp_id=f"erp:mp3d.validation.fail.{_uid()}",
        confirm=True,
    )
    with pytest.raises(RuntimeError, match="rollback-only stage probe"):
        with store.serialized_tx() as cur:
            ctx = pipeline._new_context(cur, submission)
            assert isinstance(IngressNormalizer().run(ctx), GatePass)
            assert isinstance(AuthorityGate().run(ctx), GatePass)
            ctx.policy_provider = FailingValidationPolicyProvider()
            refusal = validators.ValidationGate().run(ctx)
            raise RuntimeError("rollback-only stage probe")

    assert isinstance(refusal, GateRefusal)
    assert refusal.final_outcome == "RETAIN_DRAFT"
    assert refusal.problems[0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert [entry["gate"] for entry in ctx.gate_sequence] == [
        "INGRESS_NORMALIZATION",
        "AUTHORITY",
        "VALIDATION",
    ]
    assert ctx.gate_sequence[-1]["outcome"] == "FAIL_PROFILE_POLICY"
    assert "evidenceSufficiencyCaseRef" not in ctx.trace_refs


def test_descriptor_sufficiency_policy_failure_happens_after_validation(
        fresh_store, fresh_pipeline):
    store, pipeline = fresh_store, fresh_pipeline

    class FailingEvidencePolicyProvider:
        def __init__(self, provider):
            self.policy_ref = provider.policy_ref
            self.recognized_rule_refs = provider.recognized_rule_refs

        @staticmethod
        def evidence_policy(*_args, **_kwargs):
            raise profile_policy.ProfilePolicyError(
                "descriptor floor unavailable")

    submission = demo.spray_submission(
        f"mp3d-sufficiency-fail:{_uid()}",
        erp_id=f"erp:mp3d.sufficiency.fail.{_uid()}",
        confirm=True,
    )
    with pytest.raises(RuntimeError, match="rollback-only stage probe"):
        with store.serialized_tx() as cur:
            ctx = pipeline._new_context(cur, submission)
            for stage in (
                IngressNormalizer(),
                AuthorityGate(),
                validators.ValidationGate(),
                ProfileApplicabilityGate(),
            ):
                assert isinstance(stage.run(ctx), GatePass)
            ctx.policy_provider = FailingEvidencePolicyProvider(ctx.policy_provider)
            refusal = EvidenceSufficiencyGate().run(ctx)
            raise RuntimeError("rollback-only stage probe")

    assert isinstance(refusal, GateRefusal)
    assert refusal.final_outcome == "RETAIN_DRAFT"
    assert refusal.problems[0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert [entry["gate"] for entry in ctx.gate_sequence] == [
        "INGRESS_NORMALIZATION",
        "AUTHORITY",
        "VALIDATION",
        "PACK_PROFILE_APPLICABILITY",
        "EVIDENCE_SUFFICIENCY",
    ]
    assert ctx.gate_sequence[2]["outcome"] == "PASS"
    assert ctx.gate_sequence[-1]["outcome"] == "INSUFFICIENT"


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

    with pytest.raises(context.ContextNotReconstructible,
                       match="already bound to different canonical content"):
        with _preseeded_dirty_spine_store(mutate):
            pass


def test_profile_applicability_missing_evidence_policy_is_governed_refusal():
    def mutate(_profile, _activation, artifact):
        artifact["activeArtifactRefs"] = [
            ref for ref in artifact["activeArtifactRefs"]
            if ref != config.ACTIVE_PROFILE.evidence_policy_ref
        ]

    with pytest.raises(context.ContextNotReconstructible,
                       match="is reused for different canonical content"):
        with _preseeded_dirty_spine_store(mutate):
            pass


def test_profile_applicability_missing_descriptor_artifact_is_governed_refusal(
        fresh_store):
    store = fresh_store
    active = replace(
        config.ACTIVE_PROFILE,
        active_artifact_set_ref="activeartifactset:si.ffs.issue125.missing.v0_1",
    )

    with pytest.raises(ProfileRuntimeError, match="RuntimeBundle do not match exactly"):
        GatePipeline(store, active_profile=active)


def test_profile_applicability_required_reference_family_is_governed_refusal(
        fresh_store):
    store = fresh_store
    active = replace(
        config.ACTIVE_PROFILE,
        reference_families=config.ACTIVE_PROFILE.reference_families
        + (_missing_family(required=True),),
    )

    with pytest.raises(ProfileRuntimeError, match="RuntimeBundle do not match exactly"):
        GatePipeline(store, active_profile=active)


def test_gate_pipeline_requires_bootstrapped_runtime_bundle():
    with _fresh_unbootstrapped_store() as store:
        with pytest.raises(RuntimeError, match="no verified RuntimeBundle"):
            GatePipeline(store)


def test_materializer_requires_bootstrapped_runtime_bundle():
    with _fresh_unbootstrapped_store() as store:
        with pytest.raises(RuntimeError, match="no verified RuntimeBundle"):
            Materializer(store)


def test_dirty_profile_spine_refuses_before_api_startup():
    def mutate(_profile, _activation, artifact):
        artifact["activeArtifactRefs"] = [
            ref for ref in artifact["activeArtifactRefs"]
            if ref != config.ACTIVE_PROFILE.evidence_policy_ref
        ]

    with pytest.raises(context.ContextNotReconstructible,
                       match="is reused for different canonical content"):
        with _preseeded_dirty_spine_store(mutate):
            pass


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


def test_gate_pipeline_threads_si_reference_bindings(fresh_pipeline):
    pipeline = fresh_pipeline
    sub = demo.spray_submission(
        f"issue127b-binding-context:{_uid()}",
        erp_id=f"erp:issue127b.binding.{_uid()}",
        confirm=True,
    )

    ctx = pipeline._new_context(None, sub)

    assert pipeline.products.bindings is pipeline.si_reference_bindings
    assert ctx.si_reference_bindings is pipeline.si_reference_bindings


def test_gate_pipeline_runtime_descriptor_cannot_change_after_construction(
        fresh_pipeline):
    pipeline = fresh_pipeline
    with pytest.raises(AttributeError, match="runtime composition is immutable"):
        pipeline.active_profile = replace(
            config.ACTIVE_PROFILE,
            profile_ref="profile:si.ffs.changed-binding-context.v0_1",
        )


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
        fresh_store, fresh_pipeline):
    store, pipeline = fresh_store, fresh_pipeline

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


def test_materializer_policy_ref_change_requires_new_bundle(fresh_store):
    store = fresh_store
    policy_ref = f"policy:si.ffs.issue125.{_uid()}"
    active = replace(config.ACTIVE_PROFILE, evidence_policy_ref=policy_ref)
    with pytest.raises(ProfileRuntimeError, match="RuntimeBundle do not match exactly"):
        Materializer(store, active_profile=active)
