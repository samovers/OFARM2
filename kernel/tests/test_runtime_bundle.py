"""Focused RuntimeBundle closure regressions for issue #171."""
from __future__ import annotations

import copy
import json
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
import psycopg
import psycopg.conninfo
from psycopg.types.json import Jsonb

from kernel import config, context, demo
from kernel.adapters import ImportRunner, ParseResult
from kernel.contracts import (
    ContractRegistry,
    ContractViolation,
    canonical_json,
    sha256_of,
)
from kernel.gates import GatePipeline
from kernel.materializer import Materializer
from kernel.profiles.si_ffs.gerk_adapter import GerkLayer
from kernel.profiles.si_ffs.ffsnaprave_adapter import FFSNapraveRegister
from kernel.runtime_bundle import (
    GLOBAL_CONTENT_PLACEMENT,
    TENANT_CONTENT_PLACEMENT,
    RuntimeBundle,
    RuntimeBundleError,
    RuntimeComponent,
    _build_live_runtime_bundle,
    assert_runtime_environment_compatible,
    build_runtime_bundle,
    require_current_runtime_catalog,
    runtime_bundle_from_persisted,
    sha256_bytes,
    strict_json_bytes,
)
from kernel.store import Store
from kernel.store import _SINGLE_WRITER_LOCK_KEY
from kernel.views import OutputGenerator
from kernel.tests.conftest import _admin_dsn
from tooling.runtime_bundle_lock import (
    CatalogError,
    build_catalog,
    canonical_lock_bytes,
    verify_lock_bytes,
)


def _variant_bundle(base: RuntimeBundle) -> RuntimeBundle:
    marker_payload = base.json_component(
        "PROFILE_INSTANCE", "contextsnapshot:si.ffs.pilot.compliance.demo.v0_1")
    marker_payload["contextSnapshotId"] = "contextsnapshot:issue171.bundle-b"
    marker_payload["notes"] += " Synthetic second tenant selection receipt."
    marker = canonical_json(marker_payload).encode("utf-8")
    component = RuntimeComponent(
        role="PROFILE_INSTANCE",
        logical_ref=marker_payload["contextSnapshotId"],
        repository_path=(
            "database/profile-instance/" + marker_payload["contextSnapshotId"]),
        canonicalization="OFARM_CANONICAL_JSON_V1",
        content_digest=sha256_bytes(marker),
        canonical_bytes=marker,
        placement="TENANT_RUNTIME_SELECTION",
    )
    components = tuple(sorted(
        (*base.components, component), key=lambda item: (item.role, item.logical_ref)))
    document = json.loads(base.canonical_document_bytes)
    document["components"] = [item.identity_document() for item in components]
    canonical = canonical_json(document).encode("utf-8")
    digest = sha256_bytes(canonical)
    return replace(
        base,
        digest=digest,
        bundle_ref=f"runtimebundle:{digest}",
        canonical_document_bytes=canonical,
        components=components,
        construction_mode="PERSISTED_AUDIT",
    )


class _BundleOnlyStore:
    """No-I/O Store seam proving bundle-backed caches use retained bytes only."""

    def __init__(self, bundle):
        self.runtime_bundle = bundle


def _test_database_environment() -> dict:
    return {
        "schemaVersion": "ofarm.runtime-database-observation.local.v1",
        "server": {
            "version": "17.10 synthetic test observation",
            "versionNumber": "170010",
            "normalizedVersion": "17.10",
        },
        "database": {
            "encoding": "UTF8",
            "localeProvider": "c",
            "collation": "C.UTF-8",
            "ctype": "C.UTF-8",
            "locale": "C.UTF-8",
            "icuRules": None,
            "collationVersion": None,
        },
        "session": {
            "currentUser": "ofarm-test",
            "sessionUser": "ofarm-test",
            "timezone": "UTC",
            "dateStyle": "ISO, MDY",
            "intervalStyle": "postgres",
            "searchPath": '"$user", public',
            "standardConformingStrings": "on",
            "extraFloatDigits": "1",
            "byteaOutput": "hex",
        },
        "extensions": [{"name": "plpgsql", "version": "1.0"}],
    }


def _live_test_bundle():
    return _build_live_runtime_bundle(
        config.ACTIVE_PROFILE,
        _database_environment=_test_database_environment(),
    )


def test_runtime_bundle_lock_catalog_is_exact_and_complete():
    expected = build_catalog()
    actual = (config.PACKAGE_ROOT / "kernel" / "runtime_bundle.lock.json").read_bytes()
    verify_lock_bytes(actual, expected)
    paths = {entry["path"] for entry in expected["components"]}
    assert {f"profile_si_ffs/views/{name}" for name in (
        "OFARM_QuerySpecification_si_ffs_spray_register_passportview_v0_1.json",
        "OFARM_QueryPlanIR_si_ffs_spray_register_passportview_v0_1.json",
        "OFARM_QuerySpecification_si_ffs_inspection_register_documentassembly_v0_1.json",
        "OFARM_QueryPlanIR_si_ffs_inspection_register_documentassembly_v0_1.json",
    )} <= paths
    assert {
        ".python-version",
        "requirements-review-baseline.lock",
        "requirements-review-pip.lock",
        "conformance/review_baseline_config.json",
    } <= paths


def test_runtime_bundle_component_placement_map_is_exact():
    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    require_current_runtime_catalog(bundle, config.PACKAGE_ROOT)
    placement = {(item.role, item.logical_ref): item.placement
                 for item in bundle.components}
    assert placement[("PROFILE_INSTANCE", config.ACTIVE_PROFILE.pack_activation_set_ref)] \
        == TENANT_CONTENT_PLACEMENT
    assert placement[("PROFILE_INSTANCE", config.ACTIVE_PROFILE.active_artifact_set_ref)] \
        == TENANT_CONTENT_PLACEMENT
    assert placement[(
        "PROFILE_INSTANCE", "contextsnapshot:si.ffs.pilot.compliance.demo.v0_1")] \
        == TENANT_CONTENT_PLACEMENT
    assert placement[("ACTIVE_MANIFEST", "manifest:si.ffs.pilot.v0_1")] \
        == TENANT_CONTENT_PLACEMENT
    assert placement[("PROFILE_DESCRIPTOR", config.ACTIVE_PROFILE.profile_ref)] \
        == TENANT_CONTENT_PLACEMENT
    assert placement[("TENANT_BINDING", "tenant-binding:active")] \
        == TENANT_CONTENT_PLACEMENT
    assert all(item.placement == TENANT_CONTENT_PLACEMENT
               for item in bundle.components if item.role == "QUERY_PLAN")
    assert placement[("PROFILE_INSTANCE", config.ACTIVE_PROFILE.code_binding_profile_ref)] \
        == GLOBAL_CONTENT_PLACEMENT
    assert all(
        item.placement == GLOBAL_CONTENT_PLACEMENT
        for item in bundle.components if item.role == "REFERENCE_SNAPSHOT")
    document = json.loads(bundle.canonical_document_bytes)
    assert document["tenantRef"] == config.TENANT_REF
    assert [entry["placement"] for entry in document["components"]] == [
        item.placement for item in bundle.components]
    gerk = bundle.selected_reference(
        context.SI_REFERENCE_BINDINGS.gerk_shipped_snapshot_ref)
    assert gerk.source_byte_status == "PROVENANCE_LOCATOR_ONLY"
    assert all(ref.startswith(("archive:", "surface:"))
               for ref in gerk.unavailable_source_identities)


def test_tenant_origin_reference_snapshot_never_enters_global_placement():
    base = build_runtime_bundle(config.ACTIVE_PROFILE)
    payload = base.reference_payload(
        context.SI_REFERENCE_BINDINGS.regsr_shipped_snapshot_ref)
    payload["referenceSnapshotId"] = (
        "referencesnapshot:si.uvhvvr.ffs-reg.tenant-origin-test")
    payload["canonicalVersionLabel"] = "tenant-origin-placement-test"
    bundle = build_runtime_bundle(
        config.ACTIVE_PROFILE,
        additional_reference_payloads=[payload],
        tenant_ref=config.TENANT_REF,
    )
    component = bundle.component(
        "REFERENCE_SNAPSHOT", payload["referenceSnapshotId"])
    assert component.placement == TENANT_CONTENT_PLACEMENT
    assert component.repository_path.startswith("database/reference-snapshot/")


def test_tenant_origin_reference_cannot_reuse_global_identity_even_if_equal():
    base = build_runtime_bundle(config.ACTIVE_PROFILE)
    payload = base.reference_payload(
        context.SI_REFERENCE_BINDINGS.regsr_shipped_snapshot_ref)
    with pytest.raises(RuntimeBundleError, match="tenant-origin.*collides"):
        build_runtime_bundle(
            config.ACTIVE_PROFILE,
            additional_reference_payloads=[payload],
            tenant_ref=config.TENANT_REF,
        )


def test_import_refuses_package_global_reference_identity_before_write(fresh_env):
    store, _pipeline, _outputs = fresh_env
    records = {"synthetic": "restart-safe collision probe"}
    result = ImportRunner(store).run_import(
        ParseResult(ok=True, sourceDigest=sha256_of(records), records=records),
        {"referenceSnapshotId":
         context.SI_REFERENCE_BINDINGS.regsr_shipped_snapshot_ref},
        data_family=context.SI_REFERENCE_BINDINGS.regsr_data_family,
    )
    assert result["imported"] is False
    assert result["disposition"] == "GLOBAL_IDENTITY_COLLISION"
    assert store.get_record(
        context.SI_REFERENCE_BINDINGS.regsr_shipped_snapshot_ref) is None


def test_tenant_origin_code_binding_cannot_reuse_global_identity_even_if_equal():
    base = build_runtime_bundle(config.ACTIVE_PROFILE)
    payload = base.json_component(
        "PROFILE_INSTANCE", config.ACTIVE_PROFILE.code_binding_profile_ref)
    with pytest.raises(RuntimeBundleError, match="tenant-origin.*collides"):
        build_runtime_bundle(
            config.ACTIVE_PROFILE,
            additional_profile_payloads=[payload],
            tenant_ref=config.TENANT_REF,
        )


def test_runtime_bundle_rejects_tenant_substitution():
    with pytest.raises(RuntimeBundleError, match="owned exactly|scoped exactly"):
        build_runtime_bundle(
            config.ACTIVE_PROFILE,
            tenant_ref="tenant:issue171.other",
        )


def test_runtime_component_rejects_wrong_storage_lane():
    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    tenant_component = bundle.component(
        "PROFILE_INSTANCE", config.ACTIVE_PROFILE.active_artifact_set_ref)
    with pytest.raises(RuntimeBundleError, match="placement"):
        replace(tenant_component, placement=GLOBAL_CONTENT_PLACEMENT)
    global_component = bundle.component(
        "PROFILE_INSTANCE", config.ACTIVE_PROFILE.code_binding_profile_ref)
    with pytest.raises(RuntimeBundleError, match="placement"):
        replace(global_component, placement=TENANT_CONTENT_PLACEMENT)


@pytest.mark.parametrize("raw", [
    b"\xff",
    '{"a":1}'.encode("utf-16"),
    b'\xef\xbb\xbf{"a":1}',
    b'{"a":NaN}',
    b'{"a":Infinity}',
    b'{"a":1,"a":2}',
    b'{"a":"\\ud800"}',
])
def test_runtime_bundle_strict_json_rejects_nonportable_bytes(tmp_path, raw):
    path = tmp_path / "hostile.json"
    path.write_bytes(raw)
    with pytest.raises(RuntimeBundleError):
        strict_json_bytes(path)


def test_contract_registry_schema_view_cannot_mutate_validation():
    registry = ContractRegistry()
    schema = registry.get("ofarm.party.v0.1").schema
    schema["required"].remove("partyClass")
    with pytest.raises(ContractViolation, match="partyClass"):
        registry.validate({
            "schemaVersion": "ofarm.party.v0.1",
            "partyId": "party:issue171.registry-mutation",
            "displayName": "Fictional registry mutation probe",
            "partyState": "ACTIVE",
            "recordedAt": "2026-07-11T00:00:00Z",
        })


def test_contract_registry_and_store_registry_binding_are_immutable():
    registry = ContractRegistry()
    kind = "ofarm.party.v0.1"
    with pytest.raises(TypeError):
        registry._by_kind[kind] = replace(  # type: ignore[index]
            registry.get(kind), lane="draft")
    store = Store(registry=registry)
    with pytest.raises(AttributeError):
        store.registry = ContractRegistry()  # type: ignore[misc]
    with pytest.raises(AttributeError, match="binding is immutable"):
        store._registry = ContractRegistry()
    poisoned = ContractRegistry()
    object.__setattr__(poisoned, "_by_kind", {
        **poisoned._by_kind,
        kind: replace(poisoned.get(kind), lane="draft"),
    })
    object.__setattr__(store, "_registry", poisoned)
    try:
        with pytest.raises(RuntimeError, match="changed after construction"):
            _ = store.registry
    finally:
        object.__setattr__(store, "_registry", registry)


def test_bound_store_rejects_object_level_registry_replacement(fresh_env):
    store, _pipeline, _outputs = fresh_env
    assert store.runtime_bundle_digest
    original = store._registry
    poisoned = ContractRegistry()
    kind = "ofarm.party.v0.1"
    object.__setattr__(poisoned, "_by_kind", {
        **poisoned._by_kind,
        kind: replace(poisoned.get(kind), lane="draft"),
    })
    object.__setattr__(store, "_registry", poisoned)
    try:
        with pytest.raises(RuntimeError, match="changed after construction"):
            _ = store.registry
    finally:
        object.__setattr__(store, "_registry", original)


@pytest.mark.parametrize("changes", [
    {"lane": "draft"},
    {"id_field": "displayName"},
])
def test_store_rejects_unreceipted_registry_decision_semantics(changes):
    registry = ContractRegistry()
    kind = "ofarm.party.v0.1"
    object.__setattr__(registry, "_by_kind", {
        **registry._by_kind,
        kind: replace(registry.get(kind), **changes),
    })
    store = Store(registry=registry)
    with pytest.raises(RuntimeError, match="decision semantics"):
        store.assert_runtime_bundle_compatible(
            build_runtime_bundle(config.ACTIVE_PROFILE))


def test_cold_bundle_cannot_be_relabelled_live():
    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    assert bundle.construction_mode == "PERSISTED_AUDIT"
    with pytest.raises(RuntimeBundleError, match="live-selection provenance"):
        replace(bundle, construction_mode="LIVE_CURRENT")


def test_live_bundle_cannot_be_copied_or_replaced_as_live():
    with pytest.raises(RuntimeBundleError, match="live-selection provenance"):
        replace(_live_test_bundle())


def test_observed_runtime_environment_change_is_detected(monkeypatch):
    from kernel import runtime_bundle as runtime_bundle_module

    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    monkeypatch.setattr(
        runtime_bundle_module.platform, "python_version", lambda: "0.0.0-hostile")
    with pytest.raises(RuntimeBundleError, match="observed interpreter"):
        assert_runtime_environment_compatible(bundle)


def test_runtime_bundle_lock_rejects_missing_extra_duplicate_and_stale_entries():
    expected = build_catalog()

    missing = copy.deepcopy(expected)
    missing["components"].pop()
    with pytest.raises(CatalogError, match="missing="):
        verify_lock_bytes(canonical_lock_bytes(missing), expected)

    extra = copy.deepcopy(expected)
    extra["components"].append({
        "role": "EXTRA", "logicalRef": "extra:component",
        "path": "extra/component", "canonicalization": "EXACT_BYTES_V1",
        "sha256": "sha256:" + "0" * 64,
        "placement": "GLOBAL_IMMUTABLE_CONTENT",
    })
    with pytest.raises(CatalogError, match="extra="):
        verify_lock_bytes(canonical_lock_bytes(extra), expected)

    duplicate = copy.deepcopy(expected)
    duplicate["components"][1]["path"] = duplicate["components"][0]["path"]
    with pytest.raises(CatalogError, match="duplicate component paths"):
        verify_lock_bytes(canonical_lock_bytes(duplicate), expected)

    stale = copy.deepcopy(expected)
    stale["components"][0]["sha256"] = "sha256:" + "f" * 64
    with pytest.raises(CatalogError, match="stale"):
        verify_lock_bytes(canonical_lock_bytes(stale), expected)


def test_runtime_bundle_query_plan_mutation_refuses_startup(monkeypatch):
    target = (config.PACKAGE_ROOT / "profile_si_ffs" / "views" /
              "OFARM_QueryPlanIR_si_ffs_spray_register_passportview_v0_1.json")
    original_read_bytes = Path.read_bytes
    payload = json.loads(original_read_bytes(target))
    payload["issue171Mutation"] = True
    mutated = json.dumps(payload).encode("utf-8")

    def read_bytes(path):
        if path.resolve() == target.resolve():
            return mutated
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    with pytest.raises(RuntimeBundleError, match="catalog|component lock mismatch"):
        build_runtime_bundle(config.ACTIVE_PROFILE)


def test_runtime_bundle_startup_rejects_missing_catalog_entry(monkeypatch):
    lock_path = config.PACKAGE_ROOT / "kernel" / "runtime_bundle.lock.json"
    lock = json.loads(lock_path.read_bytes())
    lock["components"] = [entry for entry in lock["components"]
                          if entry["logicalRef"] != "python:kernel/validators.py"]
    missing = canonical_lock_bytes(lock)
    original_read_bytes = Path.read_bytes

    def read_bytes(path):
        if path.resolve() == lock_path.resolve():
            return missing
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    with pytest.raises(RuntimeBundleError, match="code-owned catalog"):
        build_runtime_bundle(config.ACTIVE_PROFILE)


def test_runtime_bundle_contract_whitespace_mutation_refuses_startup(monkeypatch):
    target = (config.CONTRACTS_ROOT / "kernel" /
              "OFARM_AssertionRecord_schema_v0_1.json")
    original_read_bytes = Path.read_bytes
    changed = original_read_bytes(target) + b"\n"

    def read_bytes(path):
        if path.resolve() == target.resolve():
            return changed
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    with pytest.raises(RuntimeBundleError, match="code-owned catalog"):
        build_runtime_bundle(config.ACTIVE_PROFILE)


def test_runtime_bundle_policy_cache_returns_defensive_copies():
    from kernel.profile_policy import DescriptorPolicyProvider

    bundle = _live_test_bundle()
    provider = DescriptorPolicyProvider(config.ACTIVE_PROFILE, runtime_bundle=bundle)
    first = provider.evidence_policy()
    original = first["operationFloor"]["hardItems"][0]
    first["operationFloor"]["hardItems"][0] = "MUTATED_BY_CALLER"
    assert provider.evidence_policy()["operationFloor"]["hardItems"][0] == original


def test_runtime_bundle_policy_provider_composition_is_immutable():
    from kernel.profile_policy import DescriptorPolicyProvider

    bundle = _live_test_bundle()
    provider = DescriptorPolicyProvider(config.ACTIVE_PROFILE, runtime_bundle=bundle)
    mutations = {
        "descriptor": replace(
            config.ACTIVE_PROFILE, profile_ref="profile:issue171.poison.v0_1"),
        "runtime_bundle": _variant_bundle(bundle),
        "policy_ref": "policy:issue171.poison.v0_1",
        "recognized_rule_refs": frozenset({"policy:issue171.poison.v0_1"}),
        "_evidence_policy_cache": {
            None: b'{"operationFloor":{"hardItems":[],"softItems":[]}}'},
    }
    for field, value in mutations.items():
        with pytest.raises(
                AttributeError,
                match="DescriptorPolicyProvider runtime composition is immutable"):
            setattr(provider, field, value)


def test_product_register_frozen_cache_refuses_nested_in_place_poisoning():
    snapshot_ref = "referencesnapshot:test.product-cache"
    register = context.ProductRegister()
    register.register_artifact(snapshot_ref, {
        "products": [{
            "regsrCode": "CACHE-1",
            "name": "Original product",
            "uses": [{"crop": "wheat", "dose": ["1", "2"]}],
        }],
        "productDetails": [{
            "regsrCode": "CACHE-1",
            "decisions": [{
                "decisionNumber": "DECISION-1",
                "issued": "2025-01-01",
                "validUntil": "2027-01-01",
                "conditions": [{"code": "ORIGINAL"}],
            }],
        }],
    })
    register.freeze()

    cache = register._by_snapshot
    with pytest.raises(TypeError):
        cache[snapshot_ref] = {}
    with pytest.raises(TypeError):
        cache[snapshot_ref]["products"]["CACHE-2"] = {}
    with pytest.raises(TypeError):
        cache[snapshot_ref]["products"]["CACHE-1"]["name"] = "POISONED"
    with pytest.raises(TypeError):
        cache[snapshot_ref]["products"]["CACHE-1"]["uses"][0]["crop"] = \
            "POISONED"
    with pytest.raises(TypeError):
        cache[snapshot_ref]["byDecision"]["DECISION-1"][0]["decision"] \
            ["conditions"][0]["code"] = "POISONED"
    with pytest.raises(AttributeError):
        register._frozen = False

    product = register.lookup(snapshot_ref, "CACHE-1")
    identity = register.lookup_by_decision(snapshot_ref, "DECISION-1")
    assert product["name"] == "Original product"
    assert product["uses"] == [{"crop": "wheat", "dose": ["1", "2"]}]
    assert identity["decision"]["conditions"] == [{"code": "ORIGINAL"}]


def test_gerk_layer_frozen_cache_and_unavailable_set_refuse_poisoning():
    snapshot_ref = "referencesnapshot:test.gerk-cache"
    unavailable_ref = "referencesnapshot:test.gerk-unavailable"
    layer = GerkLayer()
    layer._unavailable_snapshot_refs.add(unavailable_ref)
    layer.register_artifact(snapshot_ref, {
        "features": [{
            "gerkPid": "1234567",
            "rabaId": "1100",
            "area": "1.2500",
            "provenance": {"checks": [{"status": "ORIGINAL"}]},
        }],
    })
    layer.freeze()

    cache = layer._by_snapshot
    with pytest.raises(TypeError):
        cache[snapshot_ref] = {}
    with pytest.raises(TypeError):
        cache[snapshot_ref]["7654321"] = {}
    with pytest.raises(TypeError):
        cache[snapshot_ref]["1234567"]["area"] = "999"
    with pytest.raises(TypeError):
        cache[snapshot_ref]["1234567"]["provenance"]["checks"][0] \
            ["status"] = "POISONED"
    with pytest.raises(AttributeError):
        layer._unavailable_snapshot_refs.add("referencesnapshot:test.forged")
    with pytest.raises(AttributeError):
        layer._frozen = False

    parcel = layer.lookup(snapshot_ref, "1234567")
    assert parcel["area"] == "1.2500"
    assert parcel["provenance"] == {"checks": [{"status": "ORIGINAL"}]}


def test_ffsnaprave_frozen_cache_refuses_nested_in_place_poisoning():
    snapshot_ref = "referencesnapshot:test.ffsnaprave-cache"
    sticker = "STICKER-1"
    validity = "2027-01-01"
    register = FFSNapraveRegister()
    register.register_artifact(snapshot_ref, {
        "inspections": [{
            "StevilkaZnaka": sticker,
            "VeljavnostZnaka": validity,
            "VrstaNaprave": "Original sprayer",
            "checks": [{"name": "nozzle", "status": "ORIGINAL"}],
        }],
    })
    register.freeze()

    cache = register._by_snapshot
    with pytest.raises(TypeError):
        cache[snapshot_ref] = {}
    with pytest.raises(TypeError):
        cache[snapshot_ref]["byKey"][("FORGED", validity)] = {}
    with pytest.raises(TypeError):
        cache[snapshot_ref]["byKey"][(sticker, validity)]["VrstaNaprave"] = \
            "POISONED"
    with pytest.raises(TypeError):
        cache[snapshot_ref]["bySticker"][sticker][0]["checks"][0]["status"] = \
            "POISONED"
    with pytest.raises(AttributeError):
        cache[snapshot_ref]["bySticker"][sticker].append({})
    with pytest.raises(AttributeError):
        register._frozen = False

    inspection = register.match(snapshot_ref, sticker, validity)
    assert inspection["VrstaNaprave"] == "Original sprayer"
    assert inspection["checks"] == [{
        "name": "nozzle", "status": "ORIGINAL"}]
    assert register.validity_windows(snapshot_ref, sticker) == [validity]


def test_runtime_bundle_post_start_source_mutation_has_no_filesystem_fallback(
        monkeypatch):
    bundle = _live_test_bundle()
    bindings = context.SIReferenceBindings.from_descriptor(
        config.ACTIVE_PROFILE, runtime_bundle=bundle)
    source_path = bindings.regsr_shipped_artifact_path.resolve()
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text

    def refuse_bytes(path):
        if path.resolve() == source_path:
            raise AssertionError("bundle-backed ProductRegister read the live source file")
        return original_read_bytes(path)

    def refuse_text(path, *args, **kwargs):
        if path.resolve() == source_path:
            raise AssertionError("bundle-backed ProductRegister read the live source file")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", refuse_bytes)
    monkeypatch.setattr(Path, "read_text", refuse_text)
    register = context.ProductRegister(bindings, runtime_bundle=bundle)

    class NoLiveCache:
        runtime_bundle = bundle

        def reference_data(self, *_args, **_kwargs):
            raise AssertionError("bundle-backed ProductRegister read the live cache")

        def find_by_kind(self, *_args, **_kwargs):
            raise AssertionError("bundle-backed ProductRegister reselected live rows")

    register.load_from_store(NoLiveCache())
    snapshot_ref = bundle.descriptor.reference_family(
        context.SI_REGSR_FAMILY_ID).shipped_snapshot_ref
    first = register.lookup(snapshot_ref, "1646")
    assert first is not None
    original_name = first["name"]
    first["name"] = "MUTATED BY CALLER"
    assert register.lookup(snapshot_ref, "1646")["name"] == original_name
    with pytest.raises(RuntimeError, match="immutable"):
        register.register_artifact("referencesnapshot:test.post-load", {"products": []})


def test_runtime_bundle_stale_cache_and_live_rows_cannot_change_selection(fresh_env):
    store, pipeline, _outputs = fresh_env
    selected = context.current_reference_snapshot(
        store, context.REGSR_SNAPSHOT_PREFIX)["referenceSnapshotId"]
    newer = f"referencesnapshot:si.uvhvvr.ffs-reg.bundle-stale-{uuid.uuid4().hex}"
    with store.serialized_tx() as cur:
        store.insert_record(cur, {
            "schemaVersion": "ofarm.referencesnapshot.v0.1",
            "referenceSnapshotId": newer,
            "referenceClass": "CODE_LIST",
            "domain": "SYNTHETIC TEST: post-start stale-cache row",
            "canonicalVersionLabel": "issue-171-stale-cache",
            "effectiveFrom": context.now_iso(),
            "sourceArtifactRefs": ["artifact:post-start-unretained.json"],
        })
        stale_payload = {"products": [], "productDetails": []}
        store.insert_reference_data(
            cur, newer, context.REGSR_DATA_FAMILY, stale_payload,
            source_digest=sha256_bytes(canonical_json(stale_payload).encode("utf-8")),
        )
    assert context.current_reference_snapshot(
        store, context.REGSR_SNAPSHOT_PREFIX)["referenceSnapshotId"] == selected
    assert not pipeline.products.has_snapshot(newer)
    with pytest.raises(RuntimeError, match="immutable"):
        pipeline.products.register_artifact(newer, stale_payload)


def test_runtime_bundle_metadata_only_gerk_refuses_resolution():
    bundle = _live_test_bundle()
    layer = GerkLayer(runtime_bundle=bundle)
    layer.load_from_store(_BundleOnlyStore(bundle))
    shipped = bundle.descriptor.reference_family(
        context.SI_GERK_FAMILY_ID).shipped_snapshot_ref
    with pytest.raises(RuntimeBundleError, match="metadata-only"):
        layer.lookup(shipped, "1234567")

    construction_seam = GerkLayer()
    construction_seam.register_artifact("referencesnapshot:test.gerk", {
        "features": [{"gerkPid": "1234567", "area": "1.0", "rabaId": "1100"}],
    })
    first = construction_seam.lookup("referencesnapshot:test.gerk", "1234567")
    first["area"] = "999"
    assert construction_seam.lookup(
        "referencesnapshot:test.gerk", "1234567")["area"] == "1.0"


def test_runtime_bundle_metadata_only_reference_resolver_never_calls_lookup(fresh_env):
    from kernel.verification import REFUSE, ReferenceResolver

    store, _pipeline, _outputs = fresh_env
    called = False

    def lookup(_snapshot, _query):
        nonlocal called
        called = True
        raise AssertionError("metadata-only lookup was invoked")

    with store.serialized_tx() as cur:
        result = ReferenceResolver(store).verify(
            cur,
            query_value="1234567",
            snapshot_prefix=context.GERK_SNAPSHOT_PREFIX,
            lookup=lookup,
            profile_ref=config.ACTIVE_PROFILE.profile_ref,
            authority_ref="party:si.mkgp",
            jurisdiction_ref="jurisdiction:SI",
            lookup_runtime_bundle=store.runtime_bundle,
        )
    assert result["verdict"] == REFUSE
    assert result["problem"]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"
    assert called is False


def test_runtime_bundle_unselected_ffsnaprave_refuses_and_cache_is_defensive():
    bundle = _live_test_bundle()
    register = FFSNapraveRegister(runtime_bundle=bundle)
    register.load_from_store(_BundleOnlyStore(bundle))
    with pytest.raises(RuntimeBundleError, match="not selected"):
        register.match("referencesnapshot:test.ffsnaprave", "STICKER-1")

    construction_seam = FFSNapraveRegister()
    construction_seam.register_artifact("referencesnapshot:test.ffsnaprave", {
        "inspections": [{
            "StevilkaZnaka": "STICKER-1",
            "VeljavnostZnaka": "2027-01-01",
            "VrstaNaprave": "fictional test sprayer",
        }],
    })
    first = construction_seam.match(
        "referencesnapshot:test.ffsnaprave", "STICKER-1", "2027-01-01")
    first["VrstaNaprave"] = "MUTATED"
    assert construction_seam.match(
        "referencesnapshot:test.ffsnaprave", "STICKER-1",
        "2027-01-01")["VrstaNaprave"] == "fictional test sprayer"


def test_bundle_backed_resolvers_refuse_preload_injection():
    bundle = _live_test_bundle()
    bindings = context.SIReferenceBindings.from_descriptor(
        config.ACTIVE_PROFILE, runtime_bundle=bundle)
    product_register = context.ProductRegister(
        bindings, runtime_bundle=bundle)
    with pytest.raises(RuntimeError, match="immutable"):
        product_register.register_artifact(
            bindings.regsr_shipped_snapshot_ref,
            {"products": [{"regsrCode": "1646", "name": "FORGED"}]},
        )

    gerk = GerkLayer(runtime_bundle=bundle)
    with pytest.raises(RuntimeError, match="immutable"):
        gerk.register_artifact(
            bindings.gerk_shipped_snapshot_ref,
            {"features": [{
                "gerkPid": "1234567", "area": "999", "rabaId": "FORGED"}]},
        )

    ffsnaprave = FFSNapraveRegister(runtime_bundle=bundle)
    with pytest.raises(RuntimeError, match="immutable"):
        ffsnaprave.register_artifact(
            "referencesnapshot:si.uvhvvr.ffs-naprave.forged",
            {"inspections": [{
                "StevilkaZnaka": "FORGED", "VeljavnostZnaka": "2099-01-01"}]},
        )


def test_runtime_bundle_manifest_response_ignores_post_start_file_mutation(
        fresh_env, monkeypatch):
    from fastapi.testclient import TestClient
    from kernel.api import create_app

    store, _pipeline, _outputs = fresh_env
    app = create_app(store, oidc=None)
    manifest_component = next(item for item in store.runtime_bundle.components
                              if item.role == "ACTIVE_MANIFEST")
    expected = store.runtime_bundle.json_component(
        "ACTIVE_MANIFEST", manifest_component.logical_ref)
    manifest_path = config.PROFILE_ROOT / "OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json"
    original_read_text = Path.read_text

    def changed_manifest(path, *args, **kwargs):
        if path.resolve() == manifest_path.resolve():
            raise AssertionError("manifest endpoint consulted the live filesystem")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", changed_manifest)
    response = TestClient(app).get("/manifest")
    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["x-ofarm-runtime-bundle-digest"] == \
        store.runtime_bundle_digest
    assert response.headers["x-ofarm-receipt-payload-digest"] == sha256_of(expected)


def test_commit_api_returns_self_contained_runtime_receipt_headers(fresh_env):
    from fastapi.testclient import TestClient
    from kernel.api import create_app

    store, _pipeline, _outputs = fresh_env
    response = TestClient(create_app(store, oidc=None)).post(
        "/commit",
        headers={"X-Acting-Party": demo.FARMER},
        json={"submission": demo.spray_submission(
            f"issue171:api-receipt:{uuid.uuid4().hex}",
            confirm=True,
        )},
    )
    assert response.status_code == 200
    assert response.headers["x-ofarm-runtime-bundle-digest"] == \
        store.runtime_bundle_digest
    assert response.headers["x-ofarm-receipt-payload-digest"] == \
        sha256_of(response.json())


def test_read_and_output_apis_receipt_exact_response_payloads(fresh_env):
    from fastapi.testclient import TestClient
    from kernel.api import create_app

    store, _pipeline, _outputs = fresh_env
    client = TestClient(create_app(store, oidc=None))
    commit = client.post(
        "/commit",
        headers={"X-Acting-Party": demo.FARMER},
        json={"submission": demo.spray_submission(
            f"issue171:api-surface-receipt:{uuid.uuid4().hex}",
            confirm=True,
        )},
    )
    assert commit.status_code == 200
    responses = [
        client.get(
            f"/records/{commit.json()['promotionTraceRef']}",
            headers={"X-Acting-Party": demo.FARMER},
        ),
        client.get(
            f"/views/passport/{demo.FARM}",
            headers={"X-Acting-Party": demo.FARMER},
        ),
        client.post(
            "/views/inspection-register/freeze",
            headers={"X-Acting-Party": demo.FARMER},
            json={
                "farmRef": demo.FARM,
                "windowStart": "2026-01-01T00:00:00Z",
                "windowEnd": "2026-12-31T23:59:59Z",
            },
        ),
    ]
    for response in responses:
        assert response.status_code == 200
        assert response.headers["x-ofarm-runtime-bundle-digest"] == \
            store.runtime_bundle_digest
        assert response.headers["x-ofarm-receipt-payload-digest"] == \
            sha256_of(response.json())


def test_health_and_api_refusals_receipt_exact_response_payloads(fresh_env):
    from fastapi.testclient import TestClient
    from kernel.api import create_app

    store, _pipeline, _outputs = fresh_env
    client = TestClient(create_app(store, oidc=None))
    responses = [
        client.get("/health"),
        client.get(f"/records/{demo.FARMER}"),
        client.post(
            "/commit",
            headers={"X-Acting-Party": demo.FARMER},
            json={},
        ),
    ]
    assert [response.status_code for response in responses] == [200, 401, 422]
    for response in responses:
        assert response.headers["x-ofarm-runtime-bundle-digest"] == \
            store.runtime_bundle_digest
        assert response.headers["x-ofarm-receipt-payload-digest"] == \
            sha256_of(response.json())


def test_runtime_bundle_mixed_bundle_write_is_refused(fresh_env):
    store, _pipeline, _outputs = fresh_env
    bundle_b = _variant_bundle(store.runtime_bundle)
    with pytest.raises(RuntimeError, match="different RuntimeBundle"):
        with store.tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": f"party:issue171.mixed.{uuid.uuid4().hex}",
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 mixed-bundle test (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            }, runtime_bundle_digest=bundle_b.digest)


def test_runtime_bundle_persists_components_in_exact_storage_carriers(fresh_env):
    store, _pipeline, _outputs = fresh_env
    bundle = store.runtime_bundle
    with store.conn.cursor() as cur:
        cur.execute(
            "SELECT component_role, logical_ref, content_placement, "
            "global_content_digest, tenant_content_digest "
            "FROM runtime_bundle_component WHERE tenant_ref = %s "
            "AND bundle_digest = %s",
            (config.TENANT_REF, bundle.digest),
        )
        rows = {(row["component_role"], row["logical_ref"]): row
                for row in cur.fetchall()}
        assert set(rows) == {
            (item.role, item.logical_ref) for item in bundle.components}
        for component in bundle.components:
            row = rows[(component.role, component.logical_ref)]
            assert row["content_placement"] == component.placement
            if component.placement == GLOBAL_CONTENT_PLACEMENT:
                assert row["global_content_digest"] == component.content_digest
                assert row["tenant_content_digest"] is None
            else:
                assert row["global_content_digest"] is None
                assert row["tenant_content_digest"] == component.content_digest

    # Tenant-neutral package/reference content is selected through the global
    # carrier and never copied into tenant canonical truth.
    assert store.get_record(config.ACTIVE_PROFILE.code_binding_profile_ref) is None
    for reference in bundle.selected_references:
        shipped = bundle.component("REFERENCE_SNAPSHOT", reference.snapshot_ref)
        if shipped.placement == GLOBAL_CONTENT_PLACEMENT:
            assert store.get_record(reference.snapshot_ref) is None
    assert store.get_record(config.ACTIVE_PROFILE.pack_activation_set_ref) is not None
    assert store.get_record(config.ACTIVE_PROFILE.active_artifact_set_ref) is not None
    assert store.get_record(
        "contextsnapshot:si.ffs.pilot.compliance.demo.v0_1") is None


def test_runtime_bundle_install_refuses_autocommit_cursor(fresh_env):
    store, _pipeline, _outputs = fresh_env
    with store.conn.cursor() as cur:
        with pytest.raises(RuntimeError, match="one active database transaction"):
            store.install_runtime_bundle(cur, store.runtime_bundle)


def test_existing_incomplete_bundle_receipt_is_never_repaired():
    dbname = f"ofarm_issue171_incomplete_{uuid.uuid4().hex[:10]}"
    admin_dsn = _admin_dsn()
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{dbname}"')
    params = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    params["dbname"] = dbname
    store = Store(dsn=psycopg.conninfo.make_conninfo(**params))
    try:
        store.migrate()
        with store.serialized_tx() as cur:
            bundle = _build_live_runtime_bundle(
                config.ACTIVE_PROFILE,
                _database_environment=store._observe_database_environment(cur),
            )
            cur.execute(
                "INSERT INTO runtime_bundle "
                "(tenant_ref, bundle_digest, bundle_ref, canonical_document, "
                "canonical_bytes, byte_length) VALUES (%s, %s, %s, %s, %s, %s)",
                (bundle.tenant_ref, bundle.digest, bundle.bundle_ref,
                 Jsonb(json.loads(bundle.canonical_document_bytes)),
                 bundle.canonical_document_bytes,
                 len(bundle.canonical_document_bytes)),
            )
        with pytest.raises(
                context.ContextNotReconstructible,
                match="component set is not exact"):
            context.bootstrap_for_descriptor(store, config.ACTIVE_PROFILE)
        with store.conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) AS n FROM runtime_bundle_component "
                "WHERE bundle_digest = %s", (bundle.digest,))
            assert cur.fetchone()["n"] == 0
    finally:
        store.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


def test_runtime_bundle_unbound_store_cannot_claim_persisted_digest(fresh_env):
    store_a, _pipeline, _outputs = fresh_env
    unbound = Store(dsn=store_a.dsn)
    try:
        with pytest.raises(
                RuntimeError,
                match="has no verified RuntimeBundle tenant; bootstrap first"):
            with unbound.tx() as cur:
                unbound.insert_record(cur, {
                    "schemaVersion": "ofarm.party.v0.1",
                    "partyId": f"party:issue171.unbound.{uuid.uuid4().hex}",
                    "partyClass": "NATURAL_PERSON",
                    "displayName": "Issue 171 unbound attribution test (fictional)",
                    "partyState": "ACTIVE",
                    "recordedAt": context.now_iso(),
                }, runtime_bundle_digest=store_a.runtime_bundle_digest)
    finally:
        unbound.close()


def test_runtime_bundle_mixed_service_composition_is_refused(fresh_env):
    store, _pipeline, _outputs = fresh_env
    bundle_b = _variant_bundle(store.runtime_bundle)
    constructors = (
        lambda: context.ContextAssembler(store, runtime_bundle=bundle_b),
        lambda: Materializer(store, runtime_bundle=bundle_b),
        lambda: OutputGenerator(store, runtime_bundle=bundle_b),
        lambda: GatePipeline(store, runtime_bundle=bundle_b),
    )
    for construct in constructors:
        with pytest.raises(RuntimeBundleError, match="does not exactly match"):
            construct()


def test_runtime_service_composition_cannot_mutate_after_construction(fresh_env):
    _store, pipeline, outputs = fresh_env
    with pytest.raises(AttributeError, match="runtime composition is immutable"):
        pipeline.runtime_bundle = _variant_bundle(pipeline.runtime_bundle)
    with pytest.raises(AttributeError, match="runtime composition is immutable"):
        pipeline.products.bindings = replace(
            pipeline.products.bindings,
            regsr_data_family="si.test.unreceipted-family",
        )
    with pytest.raises(AttributeError, match="runtime composition is immutable"):
        outputs.materializer = Materializer(outputs.store)


def test_gate_pipeline_rechecks_exact_policy_provider_identity():
    bundle = _live_test_bundle()
    pipeline = GatePipeline(_BundleOnlyStore(bundle), runtime_bundle=bundle)
    provider = pipeline.policy_provider
    mutations = {
        "runtime_bundle": _variant_bundle(pipeline.runtime_bundle),
        "policy_ref": "policy:issue171.poison.v0_1",
        "recognized_rule_refs": frozenset({"policy:issue171.poison.v0_1"}),
    }
    for field, value in mutations.items():
        original = getattr(provider, field)
        object.__setattr__(provider, field, value)
        try:
            with pytest.raises(RuntimeBundleError, match="runtime composition changed"):
                pipeline._assert_runtime_composition()
        finally:
            object.__setattr__(provider, field, original)

    # Even an object-level bypass cannot replace the verifier the pipeline uses
    # to derive the expected rule-ref set from the retained descriptor.
    object.__setattr__(
        provider,
        "expected_recognized_rule_refs",
        lambda _descriptor: frozenset({"policy:issue171.poison.v0_1"}),
    )
    original_refs = provider.recognized_rule_refs
    object.__setattr__(
        provider, "recognized_rule_refs",
        frozenset({"policy:issue171.poison.v0_1"}))
    try:
        with pytest.raises(RuntimeBundleError, match="runtime composition changed"):
            pipeline._assert_runtime_composition()
    finally:
        object.__delattr__(provider, "expected_recognized_rule_refs")
        object.__setattr__(provider, "recognized_rule_refs", original_refs)
    pipeline._assert_runtime_composition()


def test_runtime_bundle_direct_caller_binding_is_forbidden(fresh_env):
    store, _pipeline, _outputs = fresh_env
    with pytest.raises(RuntimeError, match="direct RuntimeBundle binding is forbidden"):
        store.bind_runtime_bundle(store.runtime_bundle)


def test_runtime_bundle_direct_activation_without_prepare_is_forbidden():
    store = Store()
    with pytest.raises(RuntimeError, match="not successfully prepared"):
        store._activate_prepared_runtime_bundle(object())


def test_runtime_bundle_queue_crossing_refuses_without_migration(fresh_env):
    store_a, pipeline_a, _outputs = fresh_env
    queued = pipeline_a.commit({
        "commitClass": "COMPLIANCE_ASSERTION",
        "actingPartyRef": demo.FARMER,
        "farmRef": demo.FARM,
        "idempotencyKey": f"issue171:queue-a:{uuid.uuid4().hex}",
        "eventTime": context.now_iso(),
        "evidenceRefs": [demo.PHOTO_EVIDENCE],
        "payload": {"complianceClaim": {
            "statement": "fictional issue 171 cross-bundle claim",
            "assertedStatus": "CLAIMED_COMPLIANT",
            "governingRuleRefs": [config.EVIDENCE_POLICY_REF],
            "subjectScopeRef": demo.FARM,
        }},
        "confirmAccept": True,
        "reviewerPartyRef": demo.ADVISOR,
    })
    assert queued["decisionOutcome"] == "REQUIRE_REVIEW"
    assertion_ref = queued["emittedAssertionRecordRefs"][0]

    future_reference = store_a.runtime_bundle.reference_payload(
        context.SI_REFERENCE_BINDINGS.regsr_shipped_snapshot_ref)
    future_reference["referenceSnapshotId"] = (
        f"referencesnapshot:si.uvhvvr.ffs-reg.2099-12-31-{uuid.uuid4().hex}")
    future_reference["canonicalVersionLabel"] = "synthetic-future-selection-2099"
    future_reference["effectiveFrom"] = "2099-12-31T00:00:00Z"
    future_reference["notes"] += " Synthetic future bundle-selection test."
    with store_a.serialized_tx() as cur:
        store_a.insert_record(cur, future_reference)
    store_b = Store(dsn=store_a.dsn)
    try:
        context.bootstrap(store_b)
        assert store_b.runtime_bundle_digest != store_a.runtime_bundle_digest
        pipeline_b = GatePipeline(store_b)
        result = pipeline_b.commit({
            "commitClass": "GOVERNANCE_DECISION",
            "ingressChannel": "MANUAL_UI",
            "actingPartyRef": demo.ADVISOR,
            "farmRef": demo.FARM,
            "idempotencyKey": f"issue171:queue-b:{uuid.uuid4().hex}",
            "decisionTime": context.now_iso(),
            "reviewTargetAssertionRef": assertion_ref,
            "reviewRationale": "reviewed, but automatic bundle migration is forbidden",
            "reviewEvidenceRefs": [],
            "dominantSemanticConsequence": "cross-bundle acceptance attempt",
        })
        assert result["decisionOutcome"] == "RETAIN_DRAFT"
        assert "PACK_CONFLICT" in {
            problem["reasonCode"] for problem in result["problems"]
        }
    finally:
        store_b.close()


def test_runtime_bundle_cold_rebuild_uses_persisted_bytes_and_rejects_drift(
        fresh_env, monkeypatch):
    store, _pipeline, _outputs = fresh_env
    expected = store.runtime_bundle

    def no_filesystem_bytes(_path):
        raise AssertionError("cold RuntimeBundle reconstruction consulted the filesystem")

    monkeypatch.setattr(Path, "read_bytes", no_filesystem_bytes)
    cold = store.cold_load_runtime_bundle(None, expected.digest)
    assert cold.digest == expected.digest
    assert cold.canonical_document_bytes == expected.canonical_document_bytes
    assert cold.components == expected.components
    assert cold.descriptor == expected.descriptor
    with pytest.raises(RuntimeError, match="persisted-audit"):
        store.bind_runtime_bundle(cold)

    drifted = replace(config.ACTIVE_PROFILE, pack_ref="pack:issue171.drift.v0_1")
    with pytest.raises(RuntimeBundleError, match="caller descriptor"):
        store.cold_load_runtime_bundle(drifted, expected.digest)

    with pytest.raises(RuntimeBundleError, match="key/digest mismatch"):
        runtime_bundle_from_persisted(
            config.ACTIVE_PROFILE,
            expected_digest="sha256:" + "0" * 64,
            canonical_document_bytes=expected.canonical_document_bytes,
            components=expected.components,
        )


def test_runtime_bundle_cold_rebuild_rejects_tampered_reference_identity(fresh_env):
    store, _pipeline, _outputs = fresh_env
    bundle = store.runtime_bundle
    document = json.loads(bundle.canonical_document_bytes)
    document["selectedReferenceIdentities"][0]["snapshotPayloadDigest"] = (
        "sha256:" + "0" * 64)
    canonical = canonical_json(document).encode("utf-8")
    with pytest.raises(RuntimeBundleError, match="selected snapshot identity drift"):
        runtime_bundle_from_persisted(
            config.ACTIVE_PROFILE,
            expected_digest=sha256_bytes(canonical),
            canonical_document_bytes=canonical,
            components=bundle.components,
        )

    document = json.loads(bundle.canonical_document_bytes)
    document["selectedReferenceIdentities"][0]["sourceIdentities"] = []
    canonical = canonical_json(document).encode("utf-8")
    with pytest.raises(RuntimeBundleError, match="provenance identity drift"):
        runtime_bundle_from_persisted(
            config.ACTIVE_PROFILE,
            expected_digest=sha256_bytes(canonical),
            canonical_document_bytes=canonical,
            components=bundle.components,
        )


def test_runtime_bundle_persisted_extra_component_is_refused(fresh_env):
    store, _pipeline, _outputs = fresh_env
    extra_bytes = b"issue-171-persisted-extra-component"
    extra_digest = sha256_bytes(extra_bytes)
    with pytest.raises(RuntimeError, match="component set is not exact"):
        with store.serialized_tx() as cur:
            cur.execute(
                "INSERT INTO runtime_content_blob "
                "(content_digest, content_class, canonicalization, canonical_bytes, "
                "byte_length) VALUES (%s, 'CONTRACT_METADATA', 'EXACT_BYTES_V1', "
                "%s, %s)",
                (extra_digest, extra_bytes, len(extra_bytes)),
            )
            cur.execute(
                "INSERT INTO runtime_bundle_component "
                "(tenant_ref, bundle_digest, component_role, logical_ref, "
                "repository_path, canonicalization, content_placement, "
                "global_content_digest, byte_length) "
                "VALUES (%s, %s, 'CONTRACT_METADATA', "
                "'contract-file:extra.issue171', 'extra/issue171', "
                "'EXACT_BYTES_V1', 'GLOBAL_IMMUTABLE_CONTENT', %s, %s)",
                (config.TENANT_REF, store.runtime_bundle_digest,
                 extra_digest, len(extra_bytes)),
            )
            store.install_runtime_bundle(cur, store.runtime_bundle)


def test_runtime_bundle_rejects_unpaired_reference_digest():
    payload = {
        "schemaVersion": "ofarm.referencesnapshot.v0.1",
        "referenceSnapshotId": "referencesnapshot:si.uvhvvr.ffs-reg.unpaired-test",
        "referenceClass": "CODE_LIST",
        "domain": "SYNTHETIC TEST: unpaired source digest",
        "canonicalVersionLabel": "issue-171-unpaired",
        "effectiveFrom": "2026-07-10T00:00:00Z",
        "sourceArtifactRefs": ["digest:sha256:" + "1" * 64],
    }
    with pytest.raises(RuntimeBundleError, match="unpaired"):
        build_runtime_bundle(
            config.ACTIVE_PROFILE, additional_reference_payloads=[payload])


def test_runtime_bundle_active_artifact_ref_must_resolve_exactly():
    from kernel.runtime_bundle import _validate_active_artifact_refs

    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    components = {(item.role, item.logical_ref): item for item in bundle.components}
    active = bundle.json_component(
        "PROFILE_INSTANCE", config.ACTIVE_PROFILE.active_artifact_set_ref)
    active["activeArtifactRefs"].append("view:si.ffs.bogus-output.v0_1")
    instances = {config.ACTIVE_PROFILE.active_artifact_set_ref: (active, Path("test"))}
    with pytest.raises(RuntimeBundleError, match="active view ref"):
        _validate_active_artifact_refs(config.ACTIVE_PROFILE, instances, components)


def test_runtime_bundle_view_requires_its_exact_query_plan():
    from kernel.runtime_bundle import _validate_active_artifact_refs

    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    components = {(item.role, item.logical_ref): item for item in bundle.components}
    active = bundle.json_component(
        "PROFILE_INSTANCE", config.ACTIVE_PROFILE.active_artifact_set_ref)
    view_ref = "view:si.ffs.spray-register.passportview.v0_1"
    plan_ref = "queryplan:" + view_ref.split(":", 1)[1]
    active["activeArtifactRefs"].remove(plan_ref)
    instances = {config.ACTIVE_PROFILE.active_artifact_set_ref: (active, Path("test"))}
    with pytest.raises(RuntimeBundleError, match="query plan"):
        _validate_active_artifact_refs(config.ACTIVE_PROFILE, instances, components)

    # Keeping the stable plan id/ref is insufficient if its semantic link or
    # output mode drifts behind that name.
    active = bundle.json_component(
        "PROFILE_INSTANCE", config.ACTIVE_PROFILE.active_artifact_set_ref)
    plan_component = components[("QUERY_PLAN", plan_ref)]
    plan = json.loads(plan_component.canonical_bytes)
    plan["sourceQuerySpecificationId"] = (
        "queryspec:si.ffs.inspection-register.documentassembly.v0_1")
    changed_bytes = canonical_json(plan).encode("utf-8")
    changed_components = dict(components)
    changed_components[("QUERY_PLAN", plan_ref)] = RuntimeComponent(
        role="QUERY_PLAN", logical_ref=plan_ref,
        repository_path=plan_component.repository_path,
        canonicalization=plan_component.canonicalization,
        content_digest=sha256_bytes(changed_bytes), canonical_bytes=changed_bytes,
        placement=plan_component.placement)
    with pytest.raises(RuntimeBundleError, match="does not target its exact"):
        _validate_active_artifact_refs(
            config.ACTIVE_PROFILE,
            {config.ACTIVE_PROFILE.active_artifact_set_ref: (active, Path("test"))},
            changed_components)


def test_runtime_bundle_historical_stable_ref_requires_origin_bytes():
    from kernel.runtime_bundle import _validate_historical_artifact_origin

    current = build_runtime_bundle(config.ACTIVE_PROFILE)
    target = current.component(
        "PROFILE_POLICY", config.ACTIVE_PROFILE.evidence_policy_ref)
    payload = json.loads(target.canonical_bytes)
    payload["issue171HistoricalMutation"] = True
    changed_bytes = canonical_json(payload).encode("utf-8")
    changed = RuntimeComponent(
        role=target.role, logical_ref=target.logical_ref,
        repository_path=target.repository_path,
        canonicalization=target.canonicalization,
        content_digest=sha256_bytes(changed_bytes), canonical_bytes=changed_bytes)
    origin_components = tuple(
        changed if item == target else item for item in current.components)
    document = json.loads(current.canonical_document_bytes)
    document["components"] = [item.identity_document() for item in origin_components]
    canonical = canonical_json(document).encode("utf-8")
    digest = sha256_bytes(canonical)
    origin = RuntimeBundle(
        descriptor=current.descriptor, digest=digest,
        bundle_ref=f"runtimebundle:{digest}", canonical_document_bytes=canonical,
        components=origin_components, selected_references=current.selected_references,
        construction_mode="PERSISTED_AUDIT")
    active = current.json_component(
        "PROFILE_INSTANCE", config.ACTIVE_PROFILE.active_artifact_set_ref)
    with pytest.raises(RuntimeBundleError, match="originating RuntimeBundle"):
        _validate_historical_artifact_origin(
            active,
            {(item.role, item.logical_ref): item for item in current.components},
            origin)


def test_runtime_component_rejects_unknown_or_noncanonical_json_bytes():
    with pytest.raises(RuntimeBundleError, match="closed vocabulary"):
        RuntimeComponent(
            role="TEST", logical_ref="test:unknown-role",
            repository_path="test/unknown-role",
            canonicalization="EXACT_BYTES_V1",
            content_digest=sha256_bytes(b"bytes"), canonical_bytes=b"bytes")
    with pytest.raises(RuntimeBundleError, match="unknown canonicalization"):
        RuntimeComponent(
            role="CONTRACT_METADATA", logical_ref="contract-file:test.unknown",
            repository_path="test/unknown", canonicalization="UNKNOWN",
            content_digest=sha256_bytes(b"bytes"), canonical_bytes=b"bytes")
    noncanonical = b'{"b":2, "a":1}'
    with pytest.raises(RuntimeBundleError, match="not a canonical object"):
        RuntimeComponent(
            role="CONTRACT_METADATA", logical_ref="contract-file:test.noncanonical",
            repository_path="test/noncanonical.json",
            canonicalization="OFARM_CANONICAL_JSON_V1",
            content_digest=sha256_bytes(noncanonical), canonical_bytes=noncanonical)


def test_runtime_bundle_cold_input_rejects_duplicate_component_identities():
    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    with pytest.raises(RuntimeBundleError, match="duplicate component identities"):
        runtime_bundle_from_persisted(
            config.ACTIVE_PROFILE,
            expected_digest=bundle.digest,
            canonical_document_bytes=bundle.canonical_document_bytes,
            components=(*bundle.components, bundle.components[0]),
            package_root=config.PACKAGE_ROOT)


def test_runtime_bundle_recomputes_unavailable_reference_identities():
    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    target = next(ref for ref in bundle.selected_references
                  if ref.unavailable_source_identities)
    forged_ref = replace(target, unavailable_source_identities=())
    references = tuple(
        forged_ref if ref == target else ref for ref in bundle.selected_references)
    document = json.loads(bundle.canonical_document_bytes)
    document["selectedReferenceIdentities"] = [
        ref.identity_document() for ref in references]
    canonical = canonical_json(document).encode("utf-8")
    digest = sha256_bytes(canonical)
    with pytest.raises(RuntimeBundleError, match="unavailable-source identity drift"):
        RuntimeBundle(
            descriptor=bundle.descriptor, digest=digest,
            bundle_ref=f"runtimebundle:{digest}",
            canonical_document_bytes=canonical, components=bundle.components,
            selected_references=references, construction_mode="PERSISTED_AUDIT")


def test_selected_reference_rejects_partial_data_identity():
    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    target = next(ref for ref in bundle.selected_references
                  if ref.data_family is None)
    with pytest.raises(RuntimeBundleError, match="incomplete reference-data identity"):
        replace(
            target,
            data_payload_digest="sha256:" + "1" * 64,
            source_digest="sha256:" + "1" * 64)


def test_bundle_backed_cache_load_rejects_mixed_store_bundle():
    bundle_a = _live_test_bundle()
    bundle_b = _variant_bundle(bundle_a)
    store_b = _BundleOnlyStore(bundle_b)
    bindings = context.SIReferenceBindings.from_descriptor(
        config.ACTIVE_PROFILE, runtime_bundle=bundle_a)
    with pytest.raises(RuntimeBundleError, match="does not exactly match"):
        context.ProductRegister(
            bindings, runtime_bundle=bundle_a).load_from_store(store_b)
    with pytest.raises(RuntimeBundleError, match="does not exactly match"):
        GerkLayer(runtime_bundle=bundle_a).load_from_store(store_b)
    with pytest.raises(RuntimeBundleError, match="does not exactly match"):
        FFSNapraveRegister(runtime_bundle=bundle_a).load_from_store(store_b)


def test_si_reference_bindings_reject_mixed_descriptor_and_bundle():
    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    other = replace(config.ACTIVE_PROFILE, profile_ref="profile:test.other.v0_1")
    with pytest.raises(context.ProfileRuntimeError,
                       match="does not exactly match RuntimeBundle"):
        context.SIReferenceBindings.from_descriptor(other, runtime_bundle=bundle)


def test_gate_pipeline_rejects_caller_supplied_product_register(fresh_env):
    store, _pipeline, _outputs = fresh_env
    bindings = context.SIReferenceBindings.from_descriptor(
        store.runtime_bundle.descriptor, runtime_bundle=store.runtime_bundle)
    register = context.ProductRegister(
        bindings, runtime_bundle=store.runtime_bundle)
    with pytest.raises(context.ProfileRuntimeError,
                       match="caller-supplied ProductRegister is forbidden"):
        GatePipeline(store, product_register=register)


def test_governed_import_refuses_post_start_parser_mutation(fresh_env, monkeypatch):
    from kernel.profiles.si_ffs import regsr_adapter as regsr

    store, _pipeline, _outputs = fresh_env
    target = config.PACKAGE_ROOT / regsr.REGSR_PARSER_REF
    original_read_bytes = Path.read_bytes
    artifact = {
        "snapshotKind": "SI_UVHVVR_FFS_REG_HTML_PARSE",
        "parserCodeDigest": regsr.parser_code_digest(),
        "registerDay": "2099-12-31",
        "sourceUrl": regsr.REGSR_SOURCE_URL,
        "productCount": 1,
        "products": [{"regsrCode": "9001", "name": "Fictional"}],
        "productDetails": [],
        "rowProblems": [],
        "inputs": [{"file": "fixture.html", "digest": "sha256:" + "2" * 64}],
    }

    def mutated(path):
        value = original_read_bytes(path)
        return value + b"\n# post-start mutation\n" \
            if path.resolve() == target.resolve() else value

    monkeypatch.setattr(Path, "read_bytes", mutated)
    result = regsr.import_regsr_snapshot(store, artifact)
    assert result["imported"] is False
    assert result["disposition"] == "PARSER_BUNDLE_MISMATCH"
    assert store.get_record(
        "referencesnapshot:si.uvhvvr.ffs-reg.2099-12-31") is None
    with store.conn.cursor() as cur:
        cur.execute(
            "SELECT outcome, reason_code FROM kernel_gate_log "
            "WHERE gate = 'GOVERNED_IMPORT' ORDER BY entry_id DESC LIMIT 1")
        row = cur.fetchone()
    assert row == {"outcome": "REFUSED", "reason_code": "SOURCE_FIDELITY_LOSS"}


def test_runtime_bundle_same_document_cannot_swap_component_bytes():
    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    target = next(component for component in bundle.components
                  if component.canonicalization == "EXACT_BYTES_V1")
    changed_bytes = target.canonical_bytes + b" "
    forged = RuntimeComponent(
        role=target.role,
        logical_ref=target.logical_ref,
        repository_path=target.repository_path,
        canonicalization=target.canonicalization,
        content_digest=sha256_bytes(changed_bytes),
        canonical_bytes=changed_bytes,
    )
    components = tuple(forged if item == target else item for item in bundle.components)
    with pytest.raises(RuntimeBundleError, match="document component inventory"):
        replace(bundle, components=components)


def test_runtime_bundle_live_bind_rejects_stale_executable_bytes(fresh_env):
    store, _pipeline, _outputs = fresh_env
    base = store.runtime_bundle
    target = next(item for item in base.components
                  if item.role == "RUNTIME_CODE")
    changed_bytes = target.canonical_bytes + b"\n# stale executable variant\n"
    changed = RuntimeComponent(
        role=target.role,
        logical_ref=target.logical_ref,
        repository_path=target.repository_path,
        canonicalization=target.canonicalization,
        content_digest=sha256_bytes(changed_bytes),
        canonical_bytes=changed_bytes,
    )
    components = tuple(changed if item == target else item for item in base.components)
    document = json.loads(base.canonical_document_bytes)
    document["components"] = [item.identity_document() for item in components]
    canonical = canonical_json(document).encode("utf-8")
    digest = sha256_bytes(canonical)
    stale = replace(
        base,
        digest=digest,
        bundle_ref=f"runtimebundle:{digest}",
        canonical_document_bytes=canonical,
        components=components,
        construction_mode="PERSISTED_AUDIT",
    )
    with pytest.raises(RuntimeBundleError, match="differs from current catalog"):
        require_current_runtime_catalog(stale, config.PACKAGE_ROOT)


def test_runtime_bundle_digest_pins_commit_context_materialization_review_and_output(
        fresh_env):
    store, pipeline, outputs = fresh_env
    digest = store.runtime_bundle_digest
    result = pipeline.commit(demo.spray_submission(
        f"issue171:receipt:{uuid.uuid4().hex}",
        erp_id=f"erp:issue171.receipt.{uuid.uuid4().hex}",
    ))
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert store.get_record(result["resultId"])["runtime_bundle_digest"] == digest

    passport = outputs.passport_view(demo.FARM, demo.FARMER)
    assert passport["refused"] is False
    assert passport["runtimeReceipt"]["runtimeBundleDigest"] == digest
    frozen = outputs.freeze_inspection_register(
        demo.FARM, demo.FARMER,
        "2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z",
    )
    assert frozen["refused"] is False
    assert frozen["runtimeReceipt"]["runtimeBundleDigest"] == digest
    refused = outputs.freeze_inspection_register(
        demo.FARM, demo.FARMER, "not-a-time", "also-not-a-time")
    assert refused["refused"] is True
    assert refused["runtimeReceipt"]["runtimeBundleDigest"] == digest
    assert set(refused["runtimeReceipt"]["payloadDigests"]) == {
        "problem", "qualification"}

    required_kinds = {
        "ofarm.commitingressrequest.v0.1",
        "ofarm.commitingressresult.v0.1",
        "ofarm.assertionrecord.v0.1",
        "ofarm.reviewdecision.v0.1",
        "ofarm.contextsnapshot.v0.1",
        "ofarm.materializationbasis.v0.1",
        "ofarm.materializationsnapshot.v0.1",
    }
    # Query once for the matrix so the assertion also covers every emitted row,
    # not only one representative ID per receipt family.
    with store.conn.cursor() as cur:
        cur.execute(
            "SELECT record_kind, runtime_bundle_digest FROM kernel_record "
            "WHERE record_kind = ANY(%s)", (list(required_kinds),))
        rows = cur.fetchall()
        observed = {row["record_kind"] for row in rows}
        assert required_kinds <= observed
        assert {row["runtime_bundle_digest"] for row in rows} == {digest}
        for table in (
            "kernel_edge", "kernel_gate_log", "kernel_idempotency",
            "derived_materialization", "derived_dependency_index",
            "runtime_trace", "export_artifact",
        ):
            cur.execute(
                f"SELECT DISTINCT runtime_bundle_digest FROM {table}")
            values = {row["runtime_bundle_digest"] for row in cur.fetchall()}
            assert values == {digest}, table


def test_runtime_bundle_atomic_bootstrap_rolls_back_on_unequal_identifier_reuse():
    dbname = f"ofarm_issue171_atomic_{uuid.uuid4().hex[:10]}"
    admin_dsn = _admin_dsn()
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{dbname}"')
    params = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    params["dbname"] = dbname
    store = Store(dsn=psycopg.conninfo.make_conninfo(**params))
    try:
        store.migrate()
        target_path = config.ACTIVE_PROFILE.profile_instance_paths[2]
        conflicting = json.loads(target_path.read_text())
        conflicting["notes"] += " Synthetic unequal-content collision for issue 171."
        contract = store.registry.get(conflicting["schemaVersion"])
        conflict_id = conflicting[contract.id_field]

        with store.serialized_tx() as cur:
            database_environment = store._observe_database_environment(cur)
            target_bundle = _build_live_runtime_bundle(
                config.ACTIVE_PROFILE,
                _database_environment=database_environment,
            )
            extra_reference = target_bundle.reference_payload(
                context.SI_REFERENCE_BINDINGS.regsr_shipped_snapshot_ref)
            extra_reference["referenceSnapshotId"] = (
                "referencesnapshot:si.uvhvvr.ffs-reg.atomic-seed")
            extra_reference["canonicalVersionLabel"] = "issue-171-atomic-seed"
            seed_bundle = _build_live_runtime_bundle(
                config.ACTIVE_PROFILE,
                additional_reference_payloads=[extra_reference],
                _database_environment=database_environment,
            )
            store.install_runtime_bundle(cur, seed_bundle)
            with store._bootstrap_bundle_writes(seed_bundle):
                store.insert_record(
                    cur, conflicting, runtime_bundle_digest=seed_bundle.digest)

        earlier_ids = []
        for path in config.ACTIVE_PROFILE.profile_instance_paths[1:2]:
            payload = json.loads(path.read_text())
            item_contract = store.registry.get(payload["schemaVersion"])
            earlier_ids.append(payload[item_contract.id_field])

        with pytest.raises(context.ContextNotReconstructible,
                           match="reused for different canonical content"):
            context.bootstrap_for_descriptor(store, config.ACTIVE_PROFILE)

        assert store._runtime_bundle is None
        assert all(not store.record_exists(record_id) for record_id in earlier_ids)
        assert store.get_payload(conflict_id) == conflicting
        with store.conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) AS n FROM runtime_bundle WHERE bundle_digest = %s",
                (target_bundle.digest,),
            )
            assert cur.fetchone()["n"] == 0
            cur.execute(
                "SELECT count(*) AS n FROM runtime_bundle_component "
                "WHERE bundle_digest = %s",
                (target_bundle.digest,),
            )
            assert cur.fetchone()["n"] == 0
    finally:
        store.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


def test_runtime_bundle_bootstrap_selects_and_builds_under_import_lock(monkeypatch):
    dbname = f"ofarm_issue171_lock_{uuid.uuid4().hex[:10]}"
    admin_dsn = _admin_dsn()
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{dbname}"')
    params = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    params["dbname"] = dbname
    dsn = psycopg.conninfo.make_conninfo(**params)
    store = Store(dsn=dsn)
    competing = Store(dsn=dsn)
    original_build = context._build_runtime_bundle_for_bootstrap
    observations = []

    def checked_build(*args, **kwargs):
        with competing.conn.transaction():
            with competing.conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_try_advisory_xact_lock(%s) AS acquired",
                    (_SINGLE_WRITER_LOCK_KEY,),
                )
                observations.append(cur.fetchone()["acquired"])
        return original_build(*args, **kwargs)

    try:
        store.migrate()
        monkeypatch.setattr(
            context, "_build_runtime_bundle_for_bootstrap", checked_build)
        context.bootstrap_for_descriptor(store, config.ACTIVE_PROFILE)
        assert observations == [False], \
            "bundle selection/build ran without the governed import advisory lock"
    finally:
        competing.close()
        store.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


def test_runtime_bundle_registry_mismatch_rolls_back_bootstrap():
    dbname = f"ofarm_issue171_registry_{uuid.uuid4().hex[:10]}"
    admin_dsn = _admin_dsn()
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{dbname}"')
    params = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    params["dbname"] = dbname
    registry = ContractRegistry()
    kind = "ofarm.assertionrecord.v0.1"
    original = registry.get(kind)
    object.__setattr__(registry, "_by_kind", {
        **registry._by_kind,
        kind: replace(
            original,
            schema_hash="sha256:" + "0" * 64,
            schema_bytes=original.schema_bytes + b" ",
        ),
    })
    store = Store(
        dsn=psycopg.conninfo.make_conninfo(**params), registry=registry)
    try:
        store.migrate()
        with pytest.raises(context.ContextNotReconstructible,
                           match="atomic RuntimeBundle bootstrap failed"):
            context.bootstrap_for_descriptor(store, config.ACTIVE_PROFILE)
        with store.conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM runtime_bundle")
            assert cur.fetchone()["n"] == 0
            cur.execute("SELECT count(*) AS n FROM runtime_bundle_component")
            assert cur.fetchone()["n"] == 0
            cur.execute("SELECT count(*) AS n FROM kernel_record")
            assert cur.fetchone()["n"] == 0
    finally:
        store.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
