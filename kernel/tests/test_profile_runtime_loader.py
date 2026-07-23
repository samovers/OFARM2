"""Active profile runtime descriptor loader tests.

These pin the PR D1 boundary: SI profile runtime inputs are package content, but
tenant/demo binding remains deployment fixture content. The loader fails closed
before any descriptor mistake can become hidden runtime truth.
"""
from __future__ import annotations

import copy
import dataclasses
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
import psycopg.sql
import pytest

from kernel import (
    config,
    context,
    demo,
    profile_policy,
    profile_runtime_provider as profile_runtime_providers,
    sufficiency,
    validators,
)
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
    profile_runtime_descriptor_identity,
    resolve_profile_route,
    resolve_active_descriptor,
)
from kernel.profile_runtime_provider import (
    ProfileRuntimeProviderRegistry,
    default_profile_runtime_provider_registry,
)
from kernel.runtime_activation import complete_store_startup
from kernel.runtime_bundle import (
    RuntimeBundle,
    RuntimeBundleBuilder,
    RuntimeComponent,
    RuntimeComponentRole,
)
from kernel.stages import IngressNormalizer
from kernel.store import Store
from kernel.views import OutputGenerator


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
    return GatePipeline(
        store,
        profile_route_records=([_si_route()] if routes is None else routes),
        profile_route_registry=registry or _route_registry(),
        selected_profile_package_names=(
            config.ACTIVE_PROFILE_PACKAGE_NAMES if selected is None else selected
        ),
        tenant_ref=config.TENANT_REF if tenant is None else tenant,
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
    store = Store(
        dsn=psycopg.conninfo.make_conninfo(**params),
        tenant_ref=config.TENANT_REF,
        runtime_bundle=RuntimeBundleBuilder.from_manifest(config.PACKAGE_ROOT).build(),
        active_profile_package_name=config.ACTIVE_PROFILE_PACKAGE_NAME,
        active_descriptor=config.ACTIVE_PROFILE,
    )
    try:
        store.migrate()
        yield store
    finally:
        store.close()
        with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


@contextmanager
def _fresh_started_store(
    runtime_bundle,
    *,
    active_profile_package_name=config.ACTIVE_PROFILE_PACKAGE_NAME,
    active_descriptor=config.ACTIVE_PROFILE,
):
    dbname = f"ofarm_profile_provider_{_uid()}"
    with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        admin.execute(f'CREATE DATABASE "{dbname}"')
    params = psycopg.conninfo.conninfo_to_dict(_admin_dsn())
    params["dbname"] = dbname
    store = Store(
        dsn=psycopg.conninfo.make_conninfo(**params),
        tenant_ref=config.TENANT_REF,
        runtime_bundle=runtime_bundle,
        active_profile_package_name=active_profile_package_name,
        active_descriptor=active_descriptor,
    )
    try:
        complete_store_startup(store)
        yield store
    finally:
        store.close()
        with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


def _expected_profile_instance_ids(store, _active_profile) -> list[str]:
    return [
        component.logical_ref
        for component in store.runtime_bundle.components
        if component.role in {
            RuntimeComponentRole.PROFILE_INSTANCE,
            RuntimeComponentRole.REFERENCE_SNAPSHOT,
        }
    ]


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
    ffsnaprave_family = config.ACTIVE_PROFILE.reference_family(
        context.SI_FFSNAPRAVE_FAMILY_ID
    )
    descriptor = replace(
        config.ACTIVE_PROFILE,
        profile_root=root,
        profile_instance_files=(snapshot_path.name,),
        profile_instance_paths=(snapshot_path,),
        reference_families=(regsr_family, gerk_family, ffsnaprave_family),
    )
    return descriptor, artifact_path.resolve(), decision


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
    store = Store(
        dsn=psycopg.conninfo.make_conninfo(**params),
        tenant_ref=config.TENANT_REF,
        runtime_bundle=RuntimeBundleBuilder.from_manifest(config.PACKAGE_ROOT).build(),
        active_profile_package_name=config.ACTIVE_PROFILE_PACKAGE_NAME,
        active_descriptor=config.ACTIVE_PROFILE,
    )
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
        # This fixture deliberately constructs corrupt same-ID spine records so
        # downstream refusal paths can be tested. Production bootstrap now
        # refuses those records immediately; insert only the remaining exact
        # shipped instances here to preserve the fixture's narrower purpose.
        for path in config.ACTIVE_PROFILE.profile_instance_paths:
            payload = json.loads(path.read_text())
            contract = store.registry.get(payload["schemaVersion"])
            record_id = payload[contract.id_field]
            if store.record_exists(record_id):
                continue
            with store.tx() as cur:
                store.insert_record(cur, payload)
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


def test_default_runtime_provider_registry_registers_only_si():
    registry = default_profile_runtime_provider_registry()

    assert registry.registered_package_names == ("profile_si_ffs",)
    assert "profile_rs_organic_crop" not in registry.registered_package_names
    assert not (
        config.PACKAGE_ROOT
        / "profile_rs_organic_crop"
        / "runtime_profile_descriptor.json"
    ).exists()


def test_gate_pipeline_selects_registered_si_provider(fresh_env):
    _store, pipeline, _ = fresh_env

    assert pipeline.runtime_services.provider.package_name == "profile_si_ffs"
    assert pipeline.runtime_services.descriptor == config.ACTIVE_PROFILE
    assert pipeline.runtime_services.policy_provider is pipeline.policy_provider
    assert pipeline.runtime_services.context_assembler is pipeline.context
    assert pipeline.runtime_services.materializer is pipeline.materializer
    assert pipeline.runtime_services.reference_bindings is \
        pipeline.si_reference_bindings
    assert pipeline.runtime_services.product_lookup is pipeline.products
    assert (
        pipeline.runtime_services.registry_reverification.product_lookup
        is pipeline.products
    )
    assert (
        pipeline.runtime_services.registry_reverification.snapshot_prefix
        == pipeline.si_reference_bindings.regsr_snapshot_prefix
    )
    assert isinstance(pipeline.products, context.SIProductRegister)


def test_runtime_service_construction_refuses_unregistered_provider(fresh_env):
    store, _, _ = fresh_env

    with pytest.raises(
        ProfileRuntimeError,
        match="no registered executable runtime provider",
    ):
        ProfileRuntimeProviderRegistry(()).build_services(
            store,
            "profile_si_ffs",
            config.ACTIVE_PROFILE,
        )


def test_gate_pipeline_rejects_same_identity_provider_injection(fresh_env):
    store, _, _ = fresh_env

    class HostileProvider:
        executed = False

    hostile = HostileProvider()
    with pytest.raises(TypeError, match="runtime_provider_registry"):
        GatePipeline(
            store,
            runtime_provider_registry=hostile,
        )

    assert hostile.executed is False


@pytest.mark.parametrize("bundle_defect", ["omitted", "replaced"])
def test_gate_pipeline_refuses_unbound_runtime_provider_source(bundle_defect):
    base = RuntimeBundleBuilder.from_manifest(config.PACKAGE_ROOT).build()
    registration = default_profile_runtime_provider_registry().registration_for(
        "profile_si_ffs",
        config.ACTIVE_PROFILE,
    )
    source = base.component(
        registration.source_component_role,
        registration.source_component_logical_ref,
    )
    components = tuple(
        component
        for component in base.components
        if component is not source
    )
    if bundle_defect == "replaced":
        components += (
            RuntimeComponent.from_selected_bytes(
                role=source.role,
                logical_ref=source.logical_ref,
                canonicalization=source.canonicalization,
                placement=source.placement,
                selected_bytes=(
                    source.canonical_bytes
                    + b"\n# hostile replacement provider source\n"
                ),
            ),
        )
    runtime_bundle = RuntimeBundle.create(components)

    with _fresh_started_store(runtime_bundle) as store:
        with pytest.raises(
            ProfileRuntimeError,
            match="profile runtime provider source",
        ):
            GatePipeline(store)


def test_default_gate_pipeline_refuses_unregistered_copied_package_with_si_ref(
        tmp_path):
    package_root = tmp_path / "packages"
    package_root.mkdir()
    package_name = "profile_unregistered_si_copy"
    profile_root, _descriptor_doc = _copied_si_package(
        package_root,
        package_name,
    )
    descriptor = load_profile_runtime_descriptor(profile_root)
    runtime_bundle = RuntimeBundleBuilder.from_manifest(
        config.PACKAGE_ROOT
    ).build()

    with _fresh_started_store(
        runtime_bundle,
        active_profile_package_name=package_name,
        active_descriptor=descriptor,
    ) as store:
        with pytest.raises(
            ProfileRuntimeError,
            match="no registered executable runtime provider",
        ):
            GatePipeline(store)


def test_mismatched_provider_source_cannot_execute_during_startup(
        fresh_env, monkeypatch, tmp_path):
    store, _, _ = fresh_env
    module_name = f"hostile_runtime_provider_{_uid()}"
    module_path = tmp_path / f"{module_name}.py"
    execution_marker = tmp_path / "provider-import-executed"
    module_path.write_text(
        "from pathlib import Path\n"
        f"Path({str(execution_marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    registration = (
        default_profile_runtime_provider_registry().registration_for(
            config.ACTIVE_PROFILE_PACKAGE_NAME,
            config.ACTIVE_PROFILE,
        )
    )
    hostile_registration = replace(
        registration,
        module_name=module_name,
        provider_attribute="HOSTILE_PROVIDER",
        source_path=module_path,
    )
    monkeypatch.setattr(
        profile_runtime_providers,
        "_DEFAULT_PROVIDER_REGISTRATIONS",
        (hostile_registration,),
    )

    with pytest.raises(
        ProfileRuntimeError,
        match="source bytes do not match",
    ):
        GatePipeline(store)

    assert not execution_marker.exists()
    assert module_name not in sys.modules


def test_mismatched_provider_source_does_not_import_parent_package(tmp_path):
    package_name = f"hostile_provider_package_{_uid()}"
    package_root = tmp_path / package_name
    package_root.mkdir()
    execution_marker = tmp_path / "parent-import-executed"
    (package_root / "__init__.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(execution_marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )
    module_path = package_root / "runtime_provider.py"
    module_path.write_text(
        "raise AssertionError('unverified provider source executed')\n",
        encoding="utf-8",
    )
    registration = (
        default_profile_runtime_provider_registry().registration_for(
            config.ACTIVE_PROFILE_PACKAGE_NAME,
            config.ACTIVE_PROFILE,
        )
    )
    hostile_registration = replace(
        registration,
        module_name=f"{package_name}.runtime_provider",
        provider_attribute="HOSTILE_PROVIDER",
        source_path=module_path,
    )
    script = "\n".join([
        "import sys",
        "from pathlib import Path",
        "from kernel import config",
        "from kernel.profile_runtime import ProfileRuntimeError",
        (
            "from kernel.profile_runtime_provider import "
            "ProfileRuntimeProviderRegistration, "
            "ProfileRuntimeProviderRegistry"
        ),
        "from kernel.runtime_bundle import RuntimeComponentRole",
        f"sys.path.insert(0, {str(tmp_path)!r})",
        "registration = ProfileRuntimeProviderRegistration(",
        f"    package_name={hostile_registration.package_name!r},",
        f"    profile_ref={hostile_registration.profile_ref!r},",
        "    source_component_role=RuntimeComponentRole.ADAPTER_SOURCE,",
        (
            "    source_component_logical_ref="
            f"{hostile_registration.source_component_logical_ref!r},"
        ),
        f"    module_name={hostile_registration.module_name!r},",
        (
            "    provider_attribute="
            f"{hostile_registration.provider_attribute!r},"
        ),
        f"    source_path=Path({str(hostile_registration.source_path)!r}),",
        ")",
        "registry = ProfileRuntimeProviderRegistry((registration,))",
        "class RuntimeBundle:",
        "    def component(self, _role, _logical_ref):",
        (
            "        return type('Component', (), "
            "{'canonical_bytes': b'retained different bytes'})()"
        ),
        "class Store:",
        "    runtime_bundle = RuntimeBundle()",
        "    def require_startup_complete(self, _operation):",
        "        return None",
        "try:",
        "    registry._verify_provider_source(Store(), registration)",
        "except ProfileRuntimeError as exc:",
        "    if 'source bytes do not match' not in str(exc):",
        "        raise",
        "else:",
        "    raise AssertionError('mismatched provider source was accepted')",
    ])

    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=config.PACKAGE_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert not execution_marker.exists()


def test_preloaded_provider_attribute_replacement_cannot_execute(
        monkeypatch):
    runtime_bundle = RuntimeBundleBuilder.from_manifest(
        config.PACKAGE_ROOT
    ).build()
    registry = default_profile_runtime_provider_registry()
    registration = registry.registration_for(
        config.ACTIVE_PROFILE_PACKAGE_NAME,
        config.ACTIVE_PROFILE,
    )

    class HostileProvider:
        package_name = registration.package_name
        profile_ref = registration.profile_ref
        source_component_role = registration.source_component_role
        source_component_logical_ref = (
            registration.source_component_logical_ref
        )

        def __init__(self):
            self.executed = False

        def build_services(self, provider_store, descriptor):
            self.executed = True
            raise AssertionError("preloaded provider replacement executed")

    hostile_provider = HostileProvider()
    preloaded_module = type(sys)(registration.module_name)
    setattr(
        preloaded_module,
        registration.provider_attribute,
        hostile_provider,
    )
    monkeypatch.setitem(
        sys.modules,
        registration.module_name,
        preloaded_module,
    )

    with _fresh_started_store(runtime_bundle) as store:
        pipeline = GatePipeline(store)

    assert hostile_provider.executed is False
    assert pipeline.runtime_services.provider is not hostile_provider


def test_replaced_provider_dependency_constructor_cannot_execute(
        monkeypatch):
    runtime_bundle = RuntimeBundleBuilder.from_manifest(
        config.PACKAGE_ROOT
    ).build()
    trusted_constructor = context.ContextAssembler
    replacement_executed = False

    def hostile_constructor(*args, **kwargs):
        nonlocal replacement_executed
        replacement_executed = True
        instance = trusted_constructor(*args, **kwargs)
        instance.assemble = lambda *_args, **_kwargs: (
            pytest.fail("hostile instance capability executed")
        )
        return instance

    monkeypatch.setattr(
        context,
        "ContextAssembler",
        hostile_constructor,
    )

    with _fresh_started_store(runtime_bundle) as store:
        with pytest.raises(
            ProfileRuntimeError,
            match="runtime behavior dependency .*ContextAssembler",
        ):
            GatePipeline(store)

    assert replacement_executed is False


def test_provider_source_cannot_execute_live_dataclass_decorator(
        monkeypatch):
    runtime_bundle = RuntimeBundleBuilder.from_manifest(
        config.PACKAGE_ROOT
    ).build()
    trusted_dataclass = dataclasses.dataclass
    replacement_executed = False

    def hostile_dataclass(*args, **kwargs):
        nonlocal replacement_executed
        replacement_executed = True
        return trusted_dataclass(*args, **kwargs)

    monkeypatch.setattr(dataclasses, "dataclass", hostile_dataclass)

    with _fresh_started_store(runtime_bundle) as store:
        pipeline = GatePipeline(store)

    assert replacement_executed is False
    assert pipeline.runtime_services.provider.package_name == "profile_si_ffs"


def test_runtime_behavior_rejects_policy_loader_replacement_before_composition(
        monkeypatch):
    runtime_bundle = RuntimeBundleBuilder.from_manifest(
        config.PACKAGE_ROOT
    ).build()
    trusted_loader = profile_policy.load_evidence_review_policy_from_bytes
    replacement_executed = False

    def hostile_loader(*args, **kwargs):
        nonlocal replacement_executed
        replacement_executed = True
        return trusted_loader(*args, **kwargs)

    monkeypatch.setattr(
        profile_policy,
        "load_evidence_review_policy_from_bytes",
        hostile_loader,
    )

    with _fresh_started_store(runtime_bundle) as store:
        with pytest.raises(
            ProfileRuntimeError,
            match="runtime behavior dependency .*"
                  "load_evidence_review_policy_from_bytes",
        ):
            GatePipeline(store)

    assert replacement_executed is False


def test_runtime_behavior_rejects_hostile_service_subclass_before_construction():
    script = "\n".join([
        "from kernel import config, context",
        (
            "from kernel.profile_runtime import ProfileRuntimeError"
        ),
        (
            "from kernel.profile_runtime_provider import "
            "_capture_runtime_behavior_dependencies, "
            "default_profile_runtime_provider_registry"
        ),
        "executed = [False]",
        "class HostileContextAssembler(context.ContextAssembler):",
        "    pass",
        "def hostile_new(_cls, *args, **kwargs):",
        "    executed[0] = True",
        "    return object.__new__(HostileContextAssembler)",
        (
            "setattr(context.ContextAssembler, '__new__', "
            "staticmethod(hostile_new))"
        ),
        "registry = default_profile_runtime_provider_registry()",
        (
            "registration = registry.registration_for("
            "config.ACTIVE_PROFILE_PACKAGE_NAME, config.ACTIVE_PROFILE)"
        ),
        "try:",
        "    _capture_runtime_behavior_dependencies(registration)",
        "except ProfileRuntimeError as exc:",
        (
            "    if 'ContextAssembler.__new__' not in str(exc): "
            "raise"
        ),
        "else:",
        "    raise AssertionError('hostile __new__ was accepted')",
        "if executed[0]:",
        "    raise AssertionError('hostile __new__ executed')",
    ])

    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=config.PACKAGE_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr


def test_provider_cache_is_bound_to_complete_registration_identity(tmp_path):
    runtime_bundle = RuntimeBundleBuilder.from_manifest(
        config.PACKAGE_ROOT
    ).build()
    default_registry = default_profile_runtime_provider_registry()
    registration = default_registry.registration_for(
        config.ACTIVE_PROFILE_PACKAGE_NAME,
        config.ACTIVE_PROFILE,
    )
    alternate_source_path = tmp_path / "runtime_provider.py"
    alternate_source_path.symlink_to(registration.source_path)
    alternate_registration = replace(
        registration,
        source_path=alternate_source_path,
    )
    alternate_registry = ProfileRuntimeProviderRegistry(
        (alternate_registration,)
    )

    with _fresh_started_store(runtime_bundle) as store:
        alternate_services = alternate_registry.build_services(
            store,
            config.ACTIVE_PROFILE_PACKAGE_NAME,
            config.ACTIVE_PROFILE,
        )
        default_services = default_registry.build_services(
            store,
            config.ACTIVE_PROFILE_PACKAGE_NAME,
            config.ACTIVE_PROFILE,
        )

        assert default_services.provider is not alternate_services.provider
        assert default_services is not alternate_services
        # The symlink and checked-in path normalize to one primitive identity;
        # the receipt is shared, but live services never are.
        assert len(store._profile_runtime_provider_cache) == 1


def test_provider_cache_hit_revalidates_complete_registration():
    runtime_bundle = RuntimeBundleBuilder.from_manifest(
        config.PACKAGE_ROOT
    ).build()
    registry = default_profile_runtime_provider_registry()
    registration = registry.registration_for(
        config.ACTIVE_PROFILE_PACKAGE_NAME,
        config.ACTIVE_PROFILE,
    )
    with _fresh_started_store(runtime_bundle) as store:
        source_component = registry._verify_provider_source(
            store,
            registration,
        )
        cache_key = registry._provider_cache_key(
            registration,
            source_component,
        )
        store._retain_profile_runtime_provider(
            cache_key,
            profile_runtime_providers._ProfileRuntimeProviderCacheEntry(
                registration_identity=("hostile",),
                source_digest=source_component.content_digest,
                descriptor=config.ACTIVE_PROFILE,
                provider_dependencies=(),
                runtime_behavior=(),
                service_capabilities=(),
                service_state_digest="sha256:hostile",
            ),
        )

        with pytest.raises(
            ProfileRuntimeError,
            match="canonical registration",
        ):
            registry.build_services(
                store,
                config.ACTIVE_PROFILE_PACKAGE_NAME,
                config.ACTIVE_PROFILE,
            )


def test_provider_cache_composes_fresh_services_without_mutable_provider_call(
        fresh_env, monkeypatch):
    store, first_pipeline, _ = fresh_env
    provider_type = type(first_pipeline.runtime_services.provider)
    replacement_executed = False

    def hostile_build_services(self, provider_store, descriptor):
        nonlocal replacement_executed
        replacement_executed = True
        raise AssertionError("mutated cached provider behavior executed")

    monkeypatch.setattr(
        provider_type,
        "build_services",
        hostile_build_services,
    )

    second_pipeline = GatePipeline(store)

    assert replacement_executed is False
    assert second_pipeline.runtime_services is not first_pipeline.runtime_services
    assert (
        second_pipeline.runtime_services.provider
        is not first_pipeline.runtime_services.provider
    )


def test_provider_registry_rejects_colliding_registration_subclass():
    registration = (
        default_profile_runtime_provider_registry().registration_for(
            config.ACTIVE_PROFILE_PACKAGE_NAME,
            config.ACTIVE_PROFILE,
        )
    )

    class CollidingRegistration(
        profile_runtime_providers.ProfileRuntimeProviderRegistration
    ):
        def __hash__(self):
            return hash(registration)

        def __eq__(self, _other):
            return True

    colliding = CollidingRegistration(
        package_name=registration.package_name,
        profile_ref=registration.profile_ref,
        source_component_role=registration.source_component_role,
        source_component_logical_ref=(
            registration.source_component_logical_ref
        ),
        module_name=registration.module_name,
        provider_attribute=registration.provider_attribute,
        source_path=registration.source_path,
    )

    with pytest.raises(ProfileRuntimeError, match="invalid registration"):
        ProfileRuntimeProviderRegistry((colliding,))


def test_provider_cache_refuses_incomplete_capability_receipt():
    runtime_bundle = RuntimeBundleBuilder.from_manifest(
        config.PACKAGE_ROOT
    ).build()
    registry = default_profile_runtime_provider_registry()
    registration = registry.registration_for(
        config.ACTIVE_PROFILE_PACKAGE_NAME,
        config.ACTIVE_PROFILE,
    )

    with _fresh_started_store(runtime_bundle) as store:
        _, valid_receipt = registry.build_services_with_receipt(
            store,
            config.ACTIVE_PROFILE_PACKAGE_NAME,
            config.ACTIVE_PROFILE,
        )
        store._profile_runtime_provider_cache.clear()
        source_component = registry._verify_provider_source(store, registration)
        cache_key = registry._provider_cache_key(
            registration,
            source_component,
        )
        store._retain_profile_runtime_provider(
            cache_key,
            profile_runtime_providers._ProfileRuntimeProviderCacheEntry(
                registration_identity=(
                    profile_runtime_providers._registration_identity(
                        registration
                    )
                ),
                source_digest=source_component.content_digest,
                descriptor=config.ACTIVE_PROFILE,
                provider_dependencies=valid_receipt.provider_dependencies,
                runtime_behavior=valid_receipt.runtime_behavior,
                service_capabilities=(),
                service_state_digest=valid_receipt.service_state_digest,
            ),
        )

        with pytest.raises(
            ProfileRuntimeError,
            match="incomplete service capability provenance",
        ):
            registry.build_services(
                store,
                config.ACTIVE_PROFILE_PACKAGE_NAME,
                config.ACTIVE_PROFILE,
            )


def test_mutated_service_instance_is_not_reused_by_later_pipeline(
        fresh_env, monkeypatch):
    store, first_pipeline, _ = fresh_env
    first_registry = first_pipeline.runtime_services.registry_reverification
    replacement_executed = False

    def hostile_run(_ctx):
        nonlocal replacement_executed
        replacement_executed = True
        raise AssertionError("mutated service instance executed")

    monkeypatch.setattr(first_registry, "run", hostile_run)

    second_pipeline = GatePipeline(store)

    assert replacement_executed is False
    assert (
        second_pipeline.runtime_services.registry_reverification
        is not first_registry
    )
    assert second_pipeline.runtime_services is not first_pipeline.runtime_services


def test_long_lived_pipeline_refuses_mutated_service_state_before_next_commit(
        fresh_env):
    store, pipeline, _ = fresh_env
    registry_reverification = (
        pipeline.runtime_services.registry_reverification
    )
    registry_reverification.snapshot_prefix = (
        "referencesnapshot:hostile.runtime-state"
    )
    before = len(store.find_by_kind("ofarm.commitingressrequest.v0.1"))

    with pytest.raises(
        ProfileRuntimeError,
        match="service state changed after composition",
    ):
        pipeline.commit(demo.spray_submission(
            f"rs1-mutated-active-service:{_uid()}",
            erp_id=f"erp:rs1.mutated.active.service.{_uid()}",
            confirm=True,
        ))

    assert len(store.find_by_kind("ofarm.commitingressrequest.v0.1")) == before


def test_long_lived_pipeline_refuses_instance_capability_override_before_use(
        fresh_env, monkeypatch):
    store, pipeline, _ = fresh_env
    registry_reverification = (
        pipeline.runtime_services.registry_reverification
    )
    replacement_executed = False

    def hostile_run(_ctx):
        nonlocal replacement_executed
        replacement_executed = True
        raise AssertionError("instance capability override executed")

    monkeypatch.setattr(registry_reverification, "run", hostile_run)
    before = len(store.find_by_kind("ofarm.commitingressrequest.v0.1"))

    with pytest.raises(
        ProfileRuntimeError,
        match="overrides authenticated class capability 'run'",
    ):
        pipeline.commit(demo.spray_submission(
            f"rs1-overridden-active-service:{_uid()}",
            erp_id=f"erp:rs1.overridden.active.service.{_uid()}",
            confirm=True,
        ))

    assert replacement_executed is False
    assert len(store.find_by_kind("ofarm.commitingressrequest.v0.1")) == before


def test_long_lived_pipeline_refuses_product_lookup_helper_replacement(
        fresh_env, monkeypatch):
    store, pipeline, _ = fresh_env
    replacement_executed = False

    def hostile_identities(_self, _snapshot_id, _decision_number):
        nonlocal replacement_executed
        replacement_executed = True
        raise AssertionError("replaced product lookup helper executed")

    monkeypatch.setattr(
        context.SIProductRegister,
        "identities_by_decision",
        hostile_identities,
    )
    before = len(store.find_by_kind("ofarm.commitingressrequest.v0.1"))

    with pytest.raises(
        ProfileRuntimeError,
        match="(dependency capability|runtime behavior dependency).*"
              "identities_by_decision",
    ):
        pipeline.commit(demo.spray_submission(
            f"rs1-replaced-product-helper:{_uid()}",
            erp_id=f"erp:rs1.replaced.product.helper.{_uid()}",
            confirm=True,
        ))

    assert replacement_executed is False
    assert len(store.find_by_kind("ofarm.commitingressrequest.v0.1")) == before


def test_long_lived_pipeline_refuses_registry_snapshot_helper_replacement(
        fresh_env, monkeypatch):
    store, pipeline, _ = fresh_env
    replacement_executed = False

    def hostile_current_snapshot(*_args, **_kwargs):
        nonlocal replacement_executed
        replacement_executed = True
        raise AssertionError("replaced registry snapshot helper executed")

    monkeypatch.setattr(
        validators,
        "current_reference_snapshot",
        hostile_current_snapshot,
    )
    before = len(store.find_by_kind("ofarm.commitingressrequest.v0.1"))

    with pytest.raises(
        ProfileRuntimeError,
        match="runtime behavior dependency .*current_reference_snapshot",
    ):
        pipeline.commit(demo.spray_submission(
            f"rs1-replaced-registry-helper:{_uid()}",
            erp_id=f"erp:rs1.replaced.registry.helper.{_uid()}",
            confirm=True,
        ))

    assert replacement_executed is False
    assert len(store.find_by_kind("ofarm.commitingressrequest.v0.1")) == before


def test_mutated_service_class_fails_before_later_composition(
        fresh_env, monkeypatch):
    store, first_pipeline, _ = fresh_env
    service_type = type(
        first_pipeline.runtime_services.registry_reverification
    )
    replacement_executed = False

    def hostile_run(self, ctx):
        nonlocal replacement_executed
        replacement_executed = True
        raise AssertionError("mutated service class executed")

    monkeypatch.setattr(service_type, "run", hostile_run)

    with pytest.raises(
        ProfileRuntimeError,
        match="cached (dependency|service) capability .*run changed",
    ):
        GatePipeline(store)

    assert replacement_executed is False


def test_failed_provider_service_validation_does_not_seed_cache(
        monkeypatch):
    runtime_bundle = RuntimeBundleBuilder.from_manifest(
        config.PACKAGE_ROOT
    ).build()
    registry = default_profile_runtime_provider_registry()
    registration = registry.registration_for(
        config.ACTIVE_PROFILE_PACKAGE_NAME,
        config.ACTIVE_PROFILE,
    )

    with _fresh_started_store(runtime_bundle) as store:
        source_component = registry._verify_provider_source(
            store,
            registration,
        )
        provider = registry._load_provider(
            store,
            registration,
            source_component,
        )
        provider_dependencies = (
            profile_runtime_providers._capture_provider_dependencies(
                provider,
                registration,
            )
        )
        provider_type = type(provider)
        original_build_services = provider_type.build_services

        def incomplete_build_services(self, provider_store, descriptor):
            complete = original_build_services(
                self,
                provider_store,
                descriptor,
            )
            return replace(complete, materializer=None)

        monkeypatch.setattr(
            provider_type,
            "build_services",
            incomplete_build_services,
        )
        monkeypatch.setattr(
            ProfileRuntimeProviderRegistry,
            "_load_provider",
            staticmethod(
                lambda _store, _registration, _source_component: provider
            ),
        )
        monkeypatch.setattr(
            profile_runtime_providers,
            "_capture_provider_dependencies",
            lambda _provider, _registration: provider_dependencies,
        )

        with pytest.raises(ProfileRuntimeError, match="materializer"):
            registry.build_services(
                store,
                config.ACTIVE_PROFILE_PACKAGE_NAME,
                config.ACTIVE_PROFILE,
            )

        assert store._profile_runtime_provider_cache == {}


def test_bundle_bound_policy_ignores_copied_root_filesystem_mutation(
        tmp_path):
    package_root = tmp_path / "packages"
    package_root.mkdir()
    profile_root, descriptor_doc = _copied_si_package(
        package_root,
        "profile_si_ffs",
    )
    policy_path = profile_root / descriptor_doc["evidencePolicyPath"]
    retained_policy = json.loads(policy_path.read_text())
    retained_policy["display"]["durableProofBundleLabel"] = (
        "Retained copied-package policy"
    )
    policy_path.write_text(json.dumps(retained_policy), encoding="utf-8")
    descriptor = load_profile_runtime_descriptor(profile_root)

    base = RuntimeBundleBuilder.from_manifest(config.PACKAGE_ROOT).build()
    selected_policy = base.component(
        RuntimeComponentRole.PROFILE_POLICY,
        descriptor.evidence_policy_ref,
    )
    replacement_policy = RuntimeComponent.from_selected_bytes(
        role=selected_policy.role,
        logical_ref=selected_policy.logical_ref,
        canonicalization=selected_policy.canonicalization,
        placement=selected_policy.placement,
        selected_bytes=policy_path.read_bytes(),
    )
    runtime_bundle = RuntimeBundle.create(tuple(
        replacement_policy if component is selected_policy else component
        for component in base.components
    ))

    with _fresh_started_store(
        runtime_bundle,
        active_descriptor=descriptor,
    ) as store:
        pipeline = GatePipeline(store)
        mutated_policy = copy.deepcopy(retained_policy)
        mutated_policy["display"]["durableProofBundleLabel"] = (
            "Unretained filesystem mutation"
        )
        policy_path.write_text(json.dumps(mutated_policy), encoding="utf-8")

        observed = pipeline.policy_provider.evidence_policy(
            supported_checks=sufficiency.OPERATION_FLOOR_CHECKS,
        )

    assert observed["display"]["durableProofBundleLabel"] == (
        "Retained copied-package policy"
    )


@pytest.mark.parametrize("missing_service", [
    "policy_provider",
    "context_assembler",
    "materializer",
])
def test_runtime_service_construction_refuses_missing_required_capability(
        fresh_env, monkeypatch, missing_service):
    store, _, _ = fresh_env
    registry = default_profile_runtime_provider_registry()
    registration = registry.registration_for(
        "profile_si_ffs",
        config.ACTIVE_PROFILE,
    )
    source_component = registry._verify_provider_source(store, registration)
    provider = registry._load_provider(
        store,
        registration,
        source_component,
    )
    provider_dependencies = (
        profile_runtime_providers._capture_provider_dependencies(
            provider,
            registration,
        )
    )
    monkeypatch.setattr(
        ProfileRuntimeProviderRegistry,
        "_load_provider",
        staticmethod(
            lambda _store, _registration, _source_component: provider
        ),
    )
    monkeypatch.setattr(
        profile_runtime_providers,
        "_capture_provider_dependencies",
        lambda _provider, _registration: provider_dependencies,
    )
    provider_type = type(provider)
    original_build_services = provider_type.build_services

    def incomplete_build_services(self, provider_store, descriptor):
        complete = original_build_services(self, provider_store, descriptor)
        return replace(complete, **{missing_service: None})

    monkeypatch.setattr(
        provider_type,
        "build_services",
        incomplete_build_services,
    )
    store._profile_runtime_provider_cache.clear()
    with pytest.raises(ProfileRuntimeError, match=missing_service):
        registry.build_services(
            store,
            "profile_si_ffs",
            config.ACTIVE_PROFILE,
        )


@pytest.mark.parametrize(
    "contract_defect,match",
    [
        ("missing_policy_ref", "policy_ref"),
        ("wrong_policy_ref", "descriptor evidencePolicyRef"),
        ("invalid_recognized_rule_refs", "recognized_rule_refs"),
        ("incomplete_recognized_rule_refs", "recognized_rule_refs"),
        ("missing_lookup_by_decision", "lookup_by_decision"),
        ("missing_registry_reverification", "registry_reverification"),
        ("wrong_registry_product_lookup", "not bound"),
        ("wrong_registry_snapshot_prefix", "descriptor REGSR"),
    ],
)
def test_runtime_service_construction_refuses_incomplete_consumed_contract(
        fresh_env, monkeypatch, contract_defect, match):
    store, _, _ = fresh_env
    registry = default_profile_runtime_provider_registry()
    registration = registry.registration_for(
        "profile_si_ffs",
        config.ACTIVE_PROFILE,
    )
    source_component = registry._verify_provider_source(store, registration)
    provider = registry._load_provider(
        store,
        registration,
        source_component,
    )
    provider_dependencies = (
        profile_runtime_providers._capture_provider_dependencies(
            provider,
            registration,
        )
    )
    monkeypatch.setattr(
        ProfileRuntimeProviderRegistry,
        "_load_provider",
        staticmethod(
            lambda _store, _registration, _source_component: provider
        ),
    )
    monkeypatch.setattr(
        profile_runtime_providers,
        "_capture_provider_dependencies",
        lambda _provider, _registration: provider_dependencies,
    )
    provider_type = type(provider)
    original_build_services = provider_type.build_services

    def incomplete_build_services(self, provider_store, descriptor):
        complete = original_build_services(self, provider_store, descriptor)
        policy = complete.policy_provider
        if contract_defect == "missing_policy_ref":
            del policy.policy_ref
        elif contract_defect == "wrong_policy_ref":
            policy.policy_ref = "policy:wrong.runtime.v0_1"
        elif contract_defect == "invalid_recognized_rule_refs":
            policy.recognized_rule_refs = [policy.policy_ref]
        elif contract_defect == "incomplete_recognized_rule_refs":
            policy.recognized_rule_refs = frozenset({policy.policy_ref})
        product_lookup = complete.product_lookup
        reference_bindings = complete.reference_bindings
        registry_reverification = complete.registry_reverification
        if contract_defect == "missing_lookup_by_decision":
            product_lookup.lookup_by_decision = None
        elif contract_defect == "missing_registry_reverification":
            registry_reverification = None
        elif contract_defect == "wrong_registry_product_lookup":
            registry_reverification.product_lookup = SimpleNamespace()
        elif contract_defect == "wrong_registry_snapshot_prefix":
            wrong_prefix = "referencesnapshot:si.wrong.ffs-reg"
            object.__setattr__(
                reference_bindings,
                "regsr_snapshot_prefix",
                wrong_prefix,
            )
            registry_reverification.snapshot_prefix = wrong_prefix
        return replace(
            complete,
            policy_provider=policy,
            reference_bindings=reference_bindings,
            product_lookup=product_lookup,
            registry_reverification=registry_reverification,
        )

    monkeypatch.setattr(
        provider_type,
        "build_services",
        incomplete_build_services,
    )
    store._profile_runtime_provider_cache.clear()
    with pytest.raises(ProfileRuntimeError, match=match):
        registry.build_services(
            store,
            "profile_si_ffs",
            config.ACTIVE_PROFILE,
        )


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


def test_route_backed_gate_pipeline_refuses_tenant_mismatch_before_writes(
        fresh_env):
    store, _, _ = fresh_env
    receipt_tables = (
        "kernel_record",
        "kernel_edge",
        "kernel_gate_log",
        "kernel_idempotency",
        "derived_materialization",
        "derived_dependency_index",
        "reference_snapshot_data",
        "runtime_trace",
        "export_artifact",
    )

    def receipt_row_counts():
        counts = {}
        with store.conn.cursor() as cur:
            for table in receipt_tables:
                cur.execute(
                    psycopg.sql.SQL("SELECT count(*) AS row_count FROM {}")
                    .format(psycopg.sql.Identifier(table))
                )
                counts[table] = cur.fetchone()["row_count"]
        return counts

    tenant_b = "tenant:route.other"
    route_b = _si_route(tenant_ref=tenant_b)
    before = receipt_row_counts()

    with pytest.raises(ProfileRuntimeError, match="tenant"):
        _route_pipeline(store, routes=[route_b], tenant=tenant_b)

    assert receipt_row_counts() == before


def test_route_backed_gate_pipeline_accepts_clean_si_operation(fresh_env):
    store, default_pipeline, _ = fresh_env
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


def test_route_backed_gate_pipeline_refuses_unregistered_runtime_provider(
        fresh_env, tmp_path):
    store, _, _ = fresh_env
    package_root = _copied_package_root(tmp_path)
    package_name = "profile_unregistered_runtime"
    profile_root, descriptor_doc = _copied_si_package(
        package_root,
        package_name,
    )
    _make_second_descriptor_unique(
        profile_root,
        descriptor_doc,
        duplicate_field="",
    )
    registry = load_profile_descriptor_registry(
        package_root,
        allowed_profile_package_names=("profile_si_ffs", package_name),
    )
    descriptor = registry.candidate_for(package_name).descriptor
    route = ProfileRouteRecord(
        route_id=f"profileroute:test.unregistered.{_uid()}",
        tenant_ref=config.TENANT_REF,
        farm_ref=demo.FARM,
        profile_package_name=package_name,
        profile_ref=descriptor.profile_ref,
        pack_ref=descriptor.pack_ref,
        pack_activation_set_ref=descriptor.pack_activation_set_ref,
        active_artifact_set_ref=descriptor.active_artifact_set_ref,
        descriptor_identity=profile_runtime_descriptor_identity(descriptor),
    )
    pipeline = _route_pipeline(
        store,
        routes=[route],
        registry=registry,
        selected=("profile_si_ffs", package_name),
    )

    result = pipeline.commit(demo.spray_submission(
        f"rs1-route-unregistered:{_uid()}",
        erp_id=f"erp:rs1.route.unregistered.{_uid()}",
        confirm=True,
    ))

    assert "no registered executable runtime provider" in \
        result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)
    assert pipeline.runtime_services.provider.package_name == "profile_si_ffs"


def test_route_backed_replay_refuses_unregistered_current_route(
        fresh_env, tmp_path):
    store, _, _ = fresh_env
    package_root = _copied_package_root(tmp_path)
    package_name = "profile_unregistered_replay"
    profile_root, descriptor_doc = _copied_si_package(
        package_root,
        package_name,
    )
    _make_second_descriptor_unique(
        profile_root,
        descriptor_doc,
        duplicate_field="",
    )
    registry = load_profile_descriptor_registry(
        package_root,
        allowed_profile_package_names=("profile_si_ffs", package_name),
    )
    descriptor = registry.candidate_for(package_name).descriptor
    routes = [_si_route()]
    pipeline = _route_pipeline(store, routes=routes)
    submission = demo.spray_submission(
        f"rs1-route-replay:{_uid()}",
        erp_id=f"erp:rs1.route.replay.{_uid()}",
        confirm=True,
    )

    first = pipeline.commit(submission)
    assert first["decisionOutcome"] == "PROMOTE_ACCEPTED"

    pipeline.profile_route_registry = registry
    pipeline.selected_profile_package_names = ("profile_si_ffs", package_name)
    routes[:] = [ProfileRouteRecord(
        route_id=f"profileroute:test.unregistered.replay.{_uid()}",
        tenant_ref=config.TENANT_REF,
        farm_ref=demo.FARM,
        profile_package_name=package_name,
        profile_ref=descriptor.profile_ref,
        pack_ref=descriptor.pack_ref,
        pack_activation_set_ref=descriptor.pack_activation_set_ref,
        active_artifact_set_ref=descriptor.active_artifact_set_ref,
        descriptor_identity=profile_runtime_descriptor_identity(descriptor),
    )]

    replay = pipeline.commit(submission)

    assert replay["decisionOutcome"] == "DENY"
    assert replay["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
    assert replay["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert "no registered executable runtime provider" in \
        replay["problems"][0]["detail"]
    trace = _trace_payload(store, replay)
    assert [entry["gate"] for entry in trace["gateSequence"]][:2] == [
        "INGRESS_NORMALIZATION",
        "PACK_PROFILE_APPLICABILITY",
    ]
    assert any(
        entry["outcome"] == "PROFILE_ROUTE_REFUSE"
        for entry in trace["gateSequence"]
    )


def test_route_backed_replay_reuses_only_same_execution_fingerprint(
        fresh_env):
    store, _, _ = fresh_env
    route = _si_route()
    pipeline = _route_pipeline(store, routes=[route])
    submission = demo.spray_submission(
        f"rs1-route-replay-match:{_uid()}",
        erp_id=f"erp:rs1.route.replay.match.{_uid()}",
        confirm=True,
    )

    first = pipeline.commit(submission)
    replay = pipeline.commit(submission)

    assert replay["decisionOutcome"] == "REPLAY_REUSED_RESULT"
    assert replay["idempotencyDisposition"] == "REPLAY_MATCH_REUSED_RESULT"
    first_trace = _trace_payload(store, first)
    replay_trace = _trace_payload(store, replay)
    fingerprints = [
        ref
        for ref in first_trace["gateSequence"][1]["relatedArtifactRefs"]
        if ref.startswith("profileexecution:sha256:")
    ]
    assert len(fingerprints) == 1
    assert fingerprints[0] in replay_trace["gateSequence"][1][
        "relatedArtifactRefs"
    ]
    assert [entry["gate"] for entry in replay_trace["gateSequence"]][:2] == [
        "INGRESS_NORMALIZATION",
        "PACK_PROFILE_APPLICABILITY",
    ]


def test_profile_execution_fingerprint_is_independent_of_local_source_path(
        fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store)
    submission = demo.spray_submission(
        f"rs1-route-path-independent:{_uid()}",
        erp_id=f"erp:rs1.route.path.independent.{_uid()}",
        confirm=True,
    )

    with store.tx() as cur:
        ctx = pipeline._new_context(cur, submission)
        ingress = IngressNormalizer().run(ctx)
        assert not hasattr(ingress, "result")
        assert pipeline._resolve_profile_route(ctx) is None

    moved_registration = replace(
        pipeline.runtime_provider_registration,
        source_path=Path("/srv/ofarm/kernel/profiles/si_ffs/runtime_provider.py"),
    )
    moved_fingerprint = pipeline._profile_execution_fingerprint(
        ctx.profile_route_resolution,
        moved_registration,
    )

    assert moved_fingerprint == ctx.profile_execution_fingerprint


def test_route_backed_result_cannot_replay_through_default_pipeline(
        fresh_env):
    store, _, _ = fresh_env
    routed = _route_pipeline(store)
    submission = demo.spray_submission(
        f"rs1-route-replay-default:{_uid()}",
        erp_id=f"erp:rs1.route.replay.default.{_uid()}",
        confirm=True,
    )

    first = routed.commit(submission)
    assert first["decisionOutcome"] == "PROMOTE_ACCEPTED"
    replay = GatePipeline(store).commit(submission)

    assert replay["decisionOutcome"] == "DENY"
    assert replay["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
    assert replay["problems"][0]["reasonCode"] == "PACK_CONFLICT"
    assert "profile execution binding" in replay["problems"][0]["title"].lower()


def test_default_result_cannot_replay_through_route_backed_pipeline(
        fresh_env):
    store, default, _ = fresh_env
    submission = demo.spray_submission(
        f"rs1-default-replay-route:{_uid()}",
        erp_id=f"erp:rs1.default.replay.route.{_uid()}",
        confirm=True,
    )

    first = default.commit(submission)
    assert first["decisionOutcome"] == "PROMOTE_ACCEPTED"
    replay = _route_pipeline(store).commit(submission)

    assert replay["decisionOutcome"] == "DENY"
    assert replay["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
    assert replay["problems"][0]["reasonCode"] == "PACK_CONFLICT"


def test_route_backed_replay_refuses_different_same_provider_route(
        fresh_env):
    store, _, _ = fresh_env
    first_route = _si_route()
    routes = [first_route]
    pipeline = _route_pipeline(store, routes=routes)
    submission = demo.spray_submission(
        f"rs1-route-replay-changed-route:{_uid()}",
        erp_id=f"erp:rs1.route.replay.changed-route.{_uid()}",
        confirm=True,
    )

    first = pipeline.commit(submission)
    assert first["decisionOutcome"] == "PROMOTE_ACCEPTED"
    second_route = _si_route()
    routes[:] = [second_route]

    replay = pipeline.commit(submission)

    assert replay["decisionOutcome"] == "DENY"
    assert replay["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
    assert replay["problems"][0]["reasonCode"] == "PACK_CONFLICT"
    trace = _trace_payload(store, replay)
    assert second_route.route_id in trace["gateSequence"][1][
        "relatedArtifactRefs"
    ]
    assert first_route.route_id not in trace["gateSequence"][1][
        "relatedArtifactRefs"
    ]


def test_malformed_conflicting_replay_is_recorded_and_blocked(fresh_env):
    store, pipeline, _ = fresh_env
    submission = demo.spray_submission(
        f"rs1-replay-malformed-class:{_uid()}",
        erp_id=f"erp:rs1.replay.malformed-class.{_uid()}",
        confirm=True,
    )
    first = pipeline.commit(submission)
    assert first["decisionOutcome"] == "PROMOTE_ACCEPTED"

    malformed = dict(submission, commitClass="UNKNOWN_COMMIT_CLASS")
    replay = pipeline.commit(malformed)

    assert replay["decisionOutcome"] == "DENY"
    assert replay["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
    assert replay["problems"][0]["reasonCode"] == "IDEMPOTENCY_REPLAY_CONFLICT"
    trace = _trace_payload(store, replay)
    assert trace["gateSequence"][0]["gate"] == "INGRESS_NORMALIZATION"


def test_route_backed_malformed_conflict_precedes_route_refusal(fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store)
    submission = demo.spray_submission(
        f"rs1-route-replay-malformed-class:{_uid()}",
        erp_id=f"erp:rs1.route.replay.malformed-class.{_uid()}",
        confirm=True,
    )
    first = pipeline.commit(submission)
    assert first["decisionOutcome"] == "PROMOTE_ACCEPTED"

    malformed = dict(submission, commitClass="UNKNOWN_COMMIT_CLASS")
    replay = pipeline.commit(malformed)

    assert replay["decisionOutcome"] == "DENY"
    assert replay["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
    assert replay["problems"][0]["reasonCode"] == "IDEMPOTENCY_REPLAY_CONFLICT"
    trace = _trace_payload(store, replay)
    assert [entry["gate"] for entry in trace["gateSequence"]][:2] == [
        "INGRESS_NORMALIZATION",
        "PACK_PROFILE_APPLICABILITY",
    ]
    assert trace["gateSequence"][1]["outcome"] == "PROFILE_ROUTE_REFUSE"


def test_route_backed_gate_pipeline_refuses_alias_candidate_identity(fresh_env):
    store, _, _ = fresh_env
    alias = "profile_si_alias"
    registry = _route_registry()
    si_candidate = registry.candidate_for("profile_si_ffs")
    alias_candidate = replace(
        si_candidate,
        package_name=alias,
        enabled=True,
    )
    alias_registry = replace(
        registry,
        discoverable_package_names=(alias,),
        descriptor_candidates=(alias_candidate,),
        enabled_package_names=(alias,),
    )
    pipeline = _route_pipeline(
        store,
        routes=[_si_route(profile_package_name=alias)],
        registry=alias_registry,
        selected=(alias,),
    )

    result = pipeline.commit(demo.spray_submission(
        f"rs1-route-alias:{_uid()}",
        erp_id=f"erp:rs1.route.alias.{_uid()}",
        confirm=True,
    ))

    assert "no registered executable runtime provider" in \
        result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_symlink_alias_identity(
        fresh_env, tmp_path):
    store, _, _ = fresh_env
    alias = "profile_si_symlink_alias"
    alias_root = tmp_path / alias
    alias_root.symlink_to(config.PROFILE_ROOT, target_is_directory=True)
    registry = _route_registry()
    si_candidate = registry.candidate_for("profile_si_ffs")
    alias_candidate = replace(
        si_candidate,
        package_name=alias,
        profile_root=alias_root,
        descriptor_path=alias_root / DESCRIPTOR_FILENAME,
        enabled=True,
    )
    alias_registry = replace(
        registry,
        package_root=tmp_path,
        discoverable_package_names=(alias,),
        descriptor_candidates=(alias_candidate,),
        enabled_package_names=(alias,),
    )
    pipeline = _route_pipeline(
        store,
        routes=[_si_route(profile_package_name=alias)],
        registry=alias_registry,
        selected=(alias,),
    )

    result = pipeline.commit(demo.spray_submission(
        f"rs1-route-symlink-alias:{_uid()}",
        erp_id=f"erp:rs1.route.symlink-alias.{_uid()}",
        confirm=True,
    ))

    assert "no registered executable runtime provider" in \
        result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


@pytest.mark.parametrize("routes,match", [
    ([], "no active profile route"),
    ([_si_route(), _si_route()], "multiple active overlapping"),
    (
        [_si_route(
            descriptor_identity="profile_si_ffs/runtime_profile_descriptor.json#bad",
        )],
        "descriptor identity",
    ),
])
def test_route_backed_gate_pipeline_refuses_route_resolution_failures(
        fresh_env, routes, match):
    store, _, _ = fresh_env
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


def test_route_backed_gate_pipeline_refuses_missing_farm_context(fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-no-farm:{_uid()}",
        erp_id=f"erp:mp7.route.no-farm.{_uid()}",
        confirm=True,
    )
    sub["targetScopes"] = [{"scopeType": "FIELD", "scopeRef": "field:demo.no-farm"}]

    result = pipeline.commit(sub)

    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_farm_ref_scope_mismatch(fresh_env):
    store, _, _ = fresh_env
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
        fresh_env, scopes):
    store, _, _ = fresh_env
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
        fresh_env, malformed_farm_scope):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-malformed-farm:{_uid()}",
        erp_id=f"erp:mp7.route.malformed-farm.{_uid()}",
        confirm=True,
    )

    with store.tx() as cur:
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
        fresh_env):
    store, _, _ = fresh_env
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
        fresh_env):
    store, _, _ = fresh_env
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
        fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store, routes=[_route_interval("05")])

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-outside:{_uid()}",
        erp_id=f"erp:mp7.route.outside.{_uid()}",
        confirm=True,
    ))

    assert "no active profile route" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_reuses_matching_route_refusal(
        fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store, routes=[_route_interval("05")])
    submission = demo.spray_submission(
        f"mp7-route-outside-replay:{_uid()}",
        erp_id=f"erp:mp7.route.outside.replay.{_uid()}",
        confirm=True,
    )

    first = pipeline.commit(submission)
    replay = pipeline.commit(submission)

    assert first["decisionOutcome"] == "RETAIN_DRAFT"
    assert first["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert replay["decisionOutcome"] == "REPLAY_REUSED_RESULT"
    assert replay["idempotencyDisposition"] == "REPLAY_MATCH_REUSED_RESULT"
    assert [problem["reasonCode"] for problem in replay["problems"]] == [
        "IDEMPOTENCY_REPLAY_REUSED",
        "PROFILE_NOT_ACTIVE",
    ]
    assert replay["problems"][1] == first["problems"][0]
    trace = _trace_payload(store, replay)
    assert [entry["outcome"] for entry in trace["gateSequence"]][:2] == [
        "REPLAY_MATCH_REUSED_RESULT",
        "PROFILE_ROUTE_REFUSE",
    ]


def test_route_backed_gate_pipeline_refuses_missing_event_time_no_captured_fallback(
        fresh_env):
    store, _, _ = fresh_env
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
        fresh_env):
    store, _, _ = fresh_env
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
        fresh_env):
    store, _, _ = fresh_env
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
        fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])

    result = pipeline.commit(_note_submission(
        f"mp7-route-note-unsupported:{_uid()}"))

    assert "unsupported" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_operation_event_time_selects_half_open_route(
        fresh_env):
    store, _, _ = fresh_env
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
        fresh_env):
    store, _, _ = fresh_env
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


def test_route_backed_gate_pipeline_ignores_other_tenant_time_bounded_route(
        fresh_env):
    store, _, _ = fresh_env
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pipeline = _route_pipeline(
        store,
        routes=[
            _si_route(tenant_ref="tenant:demo.other", effective_from=t0),
            _si_route(route_id=f"profileroute:test.si.timeless.{_uid()}"),
        ],
    )

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-other-tenant-time:{_uid()}",
        erp_id=f"erp:mp7.route.other-tenant-time.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_route_backed_gate_pipeline_ignores_inactive_time_bounded_route(
        fresh_env):
    store, _, _ = fresh_env
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


def test_route_backed_gate_pipeline_governance_uses_decision_time(fresh_env):
    store, default_pipeline, _ = fresh_env
    queued = default_pipeline.commit(demo.spray_submission(
        f"mp7-governance-queued:{_uid()}",
        erp_id=f"erp:mp7.governance.queued.{_uid()}",
        confirm=False,
    ))
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])

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
        fresh_env, decision_time, match):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])

    result = pipeline.commit(_governance_submission(
        f"mp7-governance-no-decision:{_uid()}",
        decision_time=decision_time,
        event_time="2026-06-10T10:00:00Z",
    ))

    assert match in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_governance_does_not_use_event_time_fallback(
        fresh_env):
    store, _, _ = fresh_env
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
        fresh_env, package_name):
    if not (config.PACKAGE_ROOT / package_name).exists():
        pytest.skip(f"{package_name} is not present in this checkout")
    store, _, _ = fresh_env
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
        fresh_env, monkeypatch):
    store, _, _ = fresh_env

    def fail_config_policy(*_args, **_kwargs):
        raise AssertionError("config-backed policy path was called")

    monkeypatch.setattr(profile_policy, "validation_policy", fail_config_policy)
    monkeypatch.setattr(profile_policy, "load_evidence_review_policy",
                        fail_config_policy)
    monkeypatch.setattr(profile_policy, "operation_floor_with_display",
                        fail_config_policy)
    monkeypatch.setattr(profile_policy, "operation_floor_display",
                        fail_config_policy)
    monkeypatch.setattr(profile_policy, "advisory_rules", fail_config_policy)
    monkeypatch.setattr(sufficiency, "build_floor_case", fail_config_policy)
    monkeypatch.setattr(sufficiency, "operation_advisories", fail_config_policy)

    result = _route_pipeline(store).commit(demo.spray_submission(
        f"mp7-route-provider:{_uid()}",
        erp_id=f"erp:mp7.route.provider.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_route_backed_handoff_binds_materializer_to_resolved_descriptor(fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-bind:{_uid()}",
        erp_id=f"erp:mp7.route.bind.{_uid()}",
        confirm=True,
    )

    with store.tx() as cur:
        ctx = pipeline._new_context(cur, sub)
        ingress = IngressNormalizer().run(ctx)
        assert not hasattr(ingress, "result")
        assert pipeline._resolve_profile_route(ctx) is None

    assert ctx.profile_route_resolution.descriptor == config.ACTIVE_PROFILE
    assert ctx.runtime_services is pipeline.runtime_services
    assert ctx.active_profile == ctx.profile_route_resolution.descriptor
    assert ctx.materializer.active_profile == ctx.profile_route_resolution.descriptor
    assert ctx.materializer.context.active_profile == ctx.profile_route_resolution.descriptor
    assert ctx.context_assembler.active_profile == ctx.profile_route_resolution.descriptor
    assert ctx.policy_provider.descriptor == ctx.profile_route_resolution.descriptor
    assert ctx.si_reference_bindings.regsr_shipped_snapshot_ref == \
        context.SI_REFERENCE_BINDINGS.regsr_shipped_snapshot_ref


def test_output_generator_explicit_descriptor_matches_default_profile_refs(fresh_env):
    store, _, outputs = fresh_env
    explicit = OutputGenerator(store, active_descriptor=config.ACTIVE_PROFILE)

    default_view = outputs.passport_view(demo.FARM, demo.FARMER)
    explicit_view = explicit.passport_view(demo.FARM, demo.FARMER)

    assert default_view["refused"] is False
    assert explicit_view["refused"] is False
    assert default_view["metadata"]["profileRefs"] == \
        explicit_view["metadata"]["profileRefs"] == [config.ACTIVE_PROFILE.profile_ref]
    assert explicit.materializer.active_profile == config.ACTIVE_PROFILE


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

    submission = {
        "commitClass": "GOVERNANCE_DECISION",
        "actingPartyRef": demo.FARMER,
        "farmRef": demo.FARM,
        "idempotencyKey": f"mp3d-accept:{_uid()}",
        "decisionTime": "2026-06-10T10:00:00Z",
        "reviewTargetAssertionRef": queued["emittedAssertionRecordRefs"][0],
        "reviewRationale": "self-review of a routine operation claim meeting the floor",
    }
    # This is a downstream acceptance-path unit test. It bypasses commit()'s
    # deliberate helper-integrity check so the synthetic replacement can prove
    # that the acceptance stage itself never calls the full policy loader.
    with store.serialized_tx() as cur:
        accepted = pipeline._commit_in_tx(cur, submission)

    assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED"
    case = _case_payload(store, accepted)
    assert case["governingPolicyRefs"] == [config.ACTIVE_PROFILE.evidence_policy_ref]
    assert {arg["policyRef"] for arg in case["arguments"]} == {
        config.ACTIVE_PROFILE.evidence_policy_ref}


def test_descriptor_validation_policy_failure_stops_at_validation(
        fresh_env, monkeypatch):
    store, pipeline, _ = fresh_env
    # This downstream unit test deliberately bypasses commit()'s tamper check
    # so it can exercise the governed policy-error mapping in isolation.

    def fail_validation_policy(_provider):
        raise profile_policy.ProfilePolicyError("descriptor validation unavailable")

    monkeypatch.setattr(profile_policy.DescriptorPolicyProvider, "validation_policy",
                        fail_validation_policy)

    submission = demo.spray_submission(
        f"mp3d-validation-fail:{_uid()}",
        erp_id=f"erp:mp3d.validation.fail.{_uid()}",
        confirm=True,
    )
    with store.serialized_tx() as cur:
        result = pipeline._commit_in_tx(cur, submission)

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
    store, pipeline, _ = fresh_env
    # See the validation-policy companion above: this is a downstream unit
    # test, not modified class behavior passed through the governed front door.
    validation = profile_policy.validation_policy_for_descriptor(config.ACTIVE_PROFILE)

    monkeypatch.setattr(profile_policy.DescriptorPolicyProvider, "validation_policy",
                        lambda _provider: validation)

    def fail_evidence_policy(_provider, *_args, **_kwargs):
        raise profile_policy.ProfilePolicyError("descriptor floor unavailable")

    monkeypatch.setattr(profile_policy.DescriptorPolicyProvider, "evidence_policy",
                        fail_evidence_policy)

    submission = demo.spray_submission(
        f"mp3d-sufficiency-fail:{_uid()}",
        erp_id=f"erp:mp3d.sufficiency.fail.{_uid()}",
        confirm=True,
    )
    with store.serialized_tx() as cur:
        result = pipeline._commit_in_tx(cur, submission)

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


def test_api_startup_refuses_non_exact_selected_profile_instance():
    def mutate(_profile, _activation, artifact):
        artifact["activeArtifactRefs"] = [
            ref for ref in artifact["activeArtifactRefs"]
            if ref != config.ACTIVE_PROFILE.evidence_policy_ref
        ]

    with _preseeded_dirty_spine_store(mutate) as store:
        from kernel.api import create_app

        with pytest.raises(
            context.ContextNotReconstructible,
            match="not the exact selected contract and payload",
        ):
            create_app(store, oidc=None)


def test_product_register_boundary_remains_single_active_si_runtime():
    assert config.ACTIVE_PROFILE_PACKAGE_NAMES == ("profile_si_ffs",)
    assert config.ACTIVE_PROFILE_PACKAGE_NAME == "profile_si_ffs"
    assert config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES == ("profile_si_ffs",)
    assert config.ACTIVE_PROFILE_SELECTION.profile_package_names == ("profile_si_ffs",)
    assert (
        config.ACTIVE_PROFILE_SELECTION.active_profile_package_name
        == "profile_si_ffs"
    )
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

    ctx = pipeline._new_context(None, sub)

    assert pipeline.products.bindings == pipeline.si_reference_bindings
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

    assert ctx.runtime_services is None
    assert ctx.policy_provider is None
    assert ctx.context_assembler is None
    assert ctx.materializer is None
    assert ctx.products is None
    assert ctx.si_reference_bindings is None


def test_descriptor_backed_pipeline_cannot_fall_back_to_legacy_validation(
        fresh_env, monkeypatch):
    store, pipeline, _ = fresh_env

    class FailIfRun:
        def run(self, _ctx):
            raise AssertionError("legacy config-backed validation ran")

    monkeypatch.setattr(validators, "OPERATION_SEQUENCE", (FailIfRun(),))
    pipeline.active_profile = replace(
        config.ACTIVE_PROFILE,
        profile_ref="profile:si.ffs.unbound-provider.v0_1",
    )

    result = pipeline.commit(demo.spray_submission(
        f"rs1-no-legacy-policy:{_uid()}",
        erp_id=f"erp:rs1.no-legacy-policy.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    trace = _trace_payload(store, result)
    assert trace["gateSequence"][-1]["outcome"] == "FAIL_PROFILE_POLICY"


def test_registry_reverification_uses_provider_owned_capabilities(monkeypatch):
    seen_prefixes = []
    lookup_calls = []

    def fake_current_reference_snapshot(_store, prefix):
        seen_prefixes.append(prefix)
        return {"referenceSnapshotId": "referencesnapshot:si.custom.regsr.current"}

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

    class FakeProductLookup:
        def lookup_by_decision(self, snapshot_id, decision_number):
            lookup_calls.append((snapshot_id, decision_number))
            return {
                "decision": {"validUntil": "2027-12-31"},
            }

    ctx = SimpleNamespace(
        store=FakeStore(),
        sub={
            "payload": {
                "agronomicIdentityBindingRefs": ["binding:regsr"],
            },
            "capturedAgainstSnapshotRef": "referencesnapshot:si.old",
        },
        event_time="2026-06-01T00:00:00Z",
        captured_at="2026-06-01T00:00:00Z",
        review_route_reasons=[],
        log=lambda *_args, **_kwargs: None,
    )
    capability = validators.RegistryReverificationValidator(
        snapshot_prefix="referencesnapshot:si.custom.regsr",
        product_lookup=FakeProductLookup(),
    )

    assert capability.run(ctx) is None
    assert seen_prefixes == ["referencesnapshot:si.custom.regsr"]
    assert lookup_calls == [(
        "referencesnapshot:si.custom.regsr.current",
        "U99999-50/26/context",
    )]


def test_provider_operation_sequence_omits_unowned_registry_reverification():
    validation_policy = profile_policy.validation_policy()

    sequence = validators._operation_sequence_for_validation_policy(
        validation_policy,
        registry_reverification=None,
    )

    assert not any(
        isinstance(validator, validators.RegistryReverificationValidator)
        for validator in sequence
    )
    with pytest.raises(TypeError):
        validators.RegistryReverificationValidator()


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


def test_materializer_dependency_index_uses_bound_policy_and_invalidates(fresh_env):
    store, _, _ = fresh_env
    policy_ref = store.active_descriptor.evidence_policy_ref
    materializer = Materializer(store)

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
