"""Active profile runtime descriptor loader tests.

These pin the PR D1 boundary: SI profile runtime inputs are package content, but
tenant/demo binding remains deployment fixture content. The loader fails closed
before any descriptor mistake can become hidden runtime truth.
"""
# ruff: noqa: F401

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

import psycopg.sql

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
    profile_runtime_descriptor_identity,
    resolve_profile_route,
    resolve_active_descriptor,
)

import kernel.profile_runtime_provider as profile_runtime_provider

from kernel.profile_runtime_provider import (
    ProfileRuntimeServices,
    load_profile_runtime_services,
)

from kernel.runtime_bundle import (
    Canonicalization,
    ContentPlacement,
    RuntimeBundleError,
    RuntimeBundleBuilder,
    RuntimeComponent,
    RuntimeComponentRole,
)

from kernel.stages import IngressNormalizer

from kernel.store import Store

from kernel.views import OutputGenerator


def _base_doc() -> dict:
    return json.loads(
        (config.PROFILE_ROOT / "runtime_profile_descriptor.json").read_text()
    )


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
        json.dumps(doc), encoding="utf-8"
    )
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
        profile_root,
        base,
        "agronomicCodeBindingProfileId",
        base["codeBindingProfileRef"],
    )
    profile["agronomicCodeBindingProfileId"] = doc["codeBindingProfileRef"]
    profile["profileScope"]["packRefs"] = [doc["packRef"]]
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    activation_path, activation = _profile_file_by_id(
        profile_root, base, "packActivationSetId", base["packActivationSetRef"]
    )
    activation["packActivationSetId"] = doc["packActivationSetRef"]
    activation["activePackRefs"] = [doc["packRef"]]
    activation["activeProfileRefs"] = [doc["profileRef"]]
    activation_path.write_text(json.dumps(activation), encoding="utf-8")

    artifact_path, artifact = _profile_file_by_id(
        profile_root, base, "activeArtifactSetId", base["activeArtifactSetRef"]
    )
    artifact["activeArtifactSetId"] = doc["activeArtifactSetRef"]
    artifact["sourcePackActivationSetRefs"] = [doc["packActivationSetRef"]]
    artifact["activePackRefs"] = [doc["packRef"]]
    artifact["activeProfileRefs"] = [doc["profileRef"]]
    artifact["activeArtifactRefs"] = [
        ref
        for ref in artifact["activeArtifactRefs"]
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
        "descriptor_identity": profile_runtime_descriptor_identity(
            config.ACTIVE_PROFILE
        ),
    }
    values.update(overrides)
    return ProfileRouteRecord(**values)


def _route_registry(*, enabled=None):
    return load_profile_descriptor_registry(
        config.PACKAGE_ROOT,
        allowed_profile_package_names=(
            config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES if enabled is None else enabled
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
    socket_dir = os.environ.get(
        "OFARM_PG_SOCKET_DIR", str(config.PACKAGE_ROOT / ".pgrun")
    )
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
        store,
        "ofarm.agronomiccodebindingprofile.v0.1",
        config.ACTIVE_PROFILE.code_binding_profile_ref,
        "agronomicCodeBindingProfileId",
    )
    profile_id = f"codebindingprofile:si.ffs.decoy.{suffix}"
    profile["agronomicCodeBindingProfileId"] = profile_id
    profile["issuedAt"] = context.now_iso()
    profile["profileState"] = "ACTIVE"

    activation = _payload(
        store,
        "ofarm.packactivationset.v0.1",
        config.ACTIVE_PROFILE.pack_activation_set_ref,
        "packActivationSetId",
    )
    activation_id = f"packactivationset:si.ffs.decoy.{suffix}"
    activation["packActivationSetId"] = activation_id
    activation["evaluatedAt"] = context.now_iso()

    artifact = _payload(
        store,
        "ofarm.activeartifactset.v0.1",
        config.ACTIVE_PROFILE.active_artifact_set_ref,
        "activeArtifactSetId",
    )
    artifact_id = f"activeartifactset:si.ffs.decoy.{suffix}"
    artifact["activeArtifactSetId"] = artifact_id
    artifact["generatedAt"] = context.now_iso()
    artifact["sourcePackActivationSetRefs"] = [activation_id]
    artifact["activeArtifactRefs"] = [
        ref
        for ref in artifact["activeArtifactRefs"]
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
        active_descriptor=config.ACTIVE_PROFILE,
    )
    try:
        store.migrate()
        yield store
    finally:
        store.close()
        with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


def _expected_profile_instance_ids(store, _active_profile) -> list[str]:
    return [
        component.logical_ref
        for component in store.runtime_bundle.components
        if component.role
        in {
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
    return store.get_payload(
        _trace_payload(store, result)["evidenceSufficiencyCaseRef"]
    )


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
    artifact_path.write_text(
        json.dumps(_regsr_artifact(decision=decision)), encoding="utf-8"
    )

    regsr_prefix = f"referencesnapshot:si.custom.ffs-reg.{_uid()}"
    regsr_ref = f"{regsr_prefix}.2026-06-11"
    snapshot_path = root / "OFARM_ReferenceSnapshot_custom_regsr.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "schemaVersion": "ofarm.referencesnapshot.v0.1",
                "referenceSnapshotId": regsr_ref,
                "issuedAt": "2026-06-11T00:00:00Z",
                "effectiveFrom": "2026-06-11T00:00:00Z",
                "effectiveUntil": None,
                "sourceArtifactRefs": [f"artifact:{artifact_name}"],
                "issuingAuthorityRef": "party:si.uvhvvr",
            }
        ),
        encoding="utf-8",
    )

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
        active_descriptor=config.ACTIVE_PROFILE,
    )
    try:
        store.migrate()
        profile = _profile_instance_payload(
            "agronomicCodeBindingProfileId",
            config.ACTIVE_PROFILE.code_binding_profile_ref,
        )
        activation = _profile_instance_payload(
            "packActivationSetId", config.ACTIVE_PROFILE.pack_activation_set_ref
        )
        artifact = _profile_instance_payload(
            "activeArtifactSetId", config.ACTIVE_PROFILE.active_artifact_set_ref
        )
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


def _governance_submission(
    idem_key: str, *, decision_time=None, event_time=None, target="assert:demo.pending"
) -> dict:
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


__all__ = [name for name in globals() if not name.startswith("__")]
