"""Focused RuntimeBundle closure regressions for issue #171."""
from __future__ import annotations

import copy
import hashlib
import importlib.machinery
import json
import mmap
import os
import re
import sys
import threading
import time
import types
import uuid
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path, PurePosixPath

import pytest
import psycopg
import psycopg.conninfo
from psycopg import sql
from psycopg.adapt import AdaptersMap, PyFormat
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
from kernel.schema_guard import SchemaGuardError
from kernel.runtime_bundle import (
    GLOBAL_CONTENT_PLACEMENT,
    JSON_CANONICALIZATION,
    RAW_CANONICALIZATION,
    TENANT_CONTENT_PLACEMENT,
    RuntimeBundle,
    RuntimeBundleError,
    RuntimeComponent,
    _C0_CONTROL_RE,
    _build_live_runtime_bundle,
    _canonical_stable_semantic_bytes,
    _capture_decision_semantics,
    _freeze_semantic_value,
    _inventory_contains_path,
    _join_stable_locator,
    _locked_components,
    _new_semantic_traversal,
    _require_decision_semantics,
    _require_runtime_bundle_integrity,
    _require_runtime_bundle_validation_implementation,
    _require_runtime_environment_seal_integrity,
    _retained_locator_ancestor_index,
    _runtime_environment_component_from_document,
    _same_semantic_value,
    _stable_decision_semantics_document,
    _stable_locator_parts,
    _stable_runtime_environment_document,
    _validate_stable_runtime_environment_document,
    _validated_runtime_component_value,
    _validated_selected_reference_value,
    _validated_stable_decision_semantics_value,
    _validated_stable_runtime_environment_value,
    assert_runtime_environment_compatible,
    build_runtime_bundle,
    database_runtime_environment_component,
    observed_decision_semantics_component,
    require_current_runtime_catalog,
    require_live_python_import_posture,
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


def _assert_exact_http_receipt(
        response, runtime_bundle_digest: str, *,
        canonicalization: str = JSON_CANONICALIZATION,
        expected_content: bytes | None = None,
        expect_content_length: bool = True) -> None:
    """The receipt covers the bytes delivered, not a reparsed JSON value."""
    assert response.headers["content-type"] == \
        "application/json; charset=utf-8"
    if expect_content_length:
        assert int(response.headers["content-length"]) == len(response.content)
    else:
        assert "content-length" not in response.headers
    assert response.headers["x-ofarm-runtime-bundle-digest"] == \
        runtime_bundle_digest
    assert response.headers["x-ofarm-receipt-canonicalization"] == \
        canonicalization
    assert response.headers["x-ofarm-receipt-payload-digest"] == \
        "sha256:" + hashlib.sha256(response.content).hexdigest()
    if expected_content is None:
        assert response.content == canonical_json(response.json()).encode("utf-8")
    else:
        assert response.content == expected_content


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
        _selection_environment_seal=None,
    )


class _BundleOnlyStore:
    """No-I/O Store seam proving bundle-backed caches use retained bytes only."""

    def __init__(self, bundle):
        self.runtime_bundle = bundle
        self._runtime_environment_seal = bundle._selection_environment_seal


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
            "searchPath": "pg_catalog, public",
            "sessionReplicationRole": "origin",
            "transactionIsolation": "read committed",
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


def test_runtime_bundle_integrity_rejects_mutable_container_substitutions():
    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)

    original_components = bundle.components
    object.__setattr__(bundle, "components", list(original_components))
    try:
        with pytest.raises(RuntimeBundleError, match="field types"):
            _require_runtime_bundle_integrity(bundle)
    finally:
        object.__setattr__(bundle, "components", original_components)

    component = bundle.components[0]
    original_bytes = component.canonical_bytes
    object.__setattr__(component, "canonical_bytes", bytearray(original_bytes))
    try:
        with pytest.raises(RuntimeBundleError, match="role/ref/path"):
            _require_runtime_bundle_integrity(bundle)
    finally:
        object.__setattr__(component, "canonical_bytes", original_bytes)

    reference = bundle.selected_references[0]
    original_sources = reference.source_identities
    object.__setattr__(reference, "source_identities", list(original_sources))
    try:
        with pytest.raises(RuntimeBundleError, match="field types"):
            _require_runtime_bundle_integrity(bundle)
    finally:
        object.__setattr__(reference, "source_identities", original_sources)


def test_runtime_bundle_integrity_cache_rejects_same_type_mutation_and_restore():
    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    caches = (
        _validated_runtime_component_value,
        _validated_selected_reference_value,
        _validated_stable_runtime_environment_value,
        _validated_stable_decision_semantics_value,
    )
    for cache in caches:
        cache.cache_clear()
    _require_runtime_bundle_integrity(bundle)
    warm_sizes = tuple(cache.cache_info().currsize for cache in caches)
    assert warm_sizes == (len(bundle.components), len(bundle.selected_references), 1, 1)

    component = bundle.component(
        "PROFILE_POLICY", bundle.descriptor.evidence_policy_ref)
    original_component_bytes = component.canonical_bytes
    object.__setattr__(
        component, "canonical_bytes", original_component_bytes + b" ")
    try:
        with pytest.raises(RuntimeBundleError):
            _require_runtime_bundle_integrity(bundle)
        assert tuple(cache.cache_info().currsize for cache in caches) == warm_sizes
    finally:
        object.__setattr__(
            component, "canonical_bytes", original_component_bytes)
    _require_runtime_bundle_integrity(bundle)

    reference = bundle.selected_references[0]
    original_snapshot_digest = reference.snapshot_payload_digest
    object.__setattr__(
        reference, "snapshot_payload_digest", "sha256:" + "z" * 64)
    try:
        with pytest.raises(RuntimeBundleError):
            _require_runtime_bundle_integrity(bundle)
        assert tuple(cache.cache_info().currsize for cache in caches) == warm_sizes
    finally:
        object.__setattr__(
            reference, "snapshot_payload_digest", original_snapshot_digest)
    _require_runtime_bundle_integrity(bundle)

    descriptor = bundle.descriptor
    original_pack_ref = descriptor.pack_ref
    object.__setattr__(descriptor, "pack_ref", original_pack_ref + ".hostile")
    try:
        with pytest.raises(RuntimeBundleError, match="descriptor"):
            _require_runtime_bundle_integrity(bundle)
        assert tuple(cache.cache_info().currsize for cache in caches) == warm_sizes
    finally:
        object.__setattr__(descriptor, "pack_ref", original_pack_ref)
    _require_runtime_bundle_integrity(bundle)

    original_document = bundle.canonical_document_bytes
    object.__setattr__(
        bundle, "canonical_document_bytes", original_document + b" ")
    try:
        with pytest.raises(RuntimeBundleError):
            _require_runtime_bundle_integrity(bundle)
        assert tuple(cache.cache_info().currsize for cache in caches) == warm_sizes
    finally:
        object.__setattr__(bundle, "canonical_document_bytes", original_document)
    before_restore = tuple(cache.cache_info() for cache in caches)
    _require_runtime_bundle_integrity(bundle)
    after_restore = tuple(cache.cache_info() for cache in caches)
    assert all(after.hits > before.hits
               for before, after in zip(before_restore, after_restore))
    assert tuple(info.currsize for info in after_restore) == warm_sizes


def test_runtime_bundle_integrity_cache_implementation_is_anchored(monkeypatch):
    from kernel import runtime_bundle as runtime_bundle_module

    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    _require_runtime_bundle_integrity(bundle)
    monkeypatch.setattr(
        runtime_bundle_module,
        "_validated_runtime_component_value",
        lambda _value: None,
    )
    with pytest.raises(RuntimeBundleError, match="implementation changed"):
        _require_runtime_bundle_integrity(bundle)
    with pytest.raises(RuntimeBundleError, match="implementation changed"):
        _require_runtime_bundle_validation_implementation()


def test_runtime_bundle_integrity_value_cache_benchmark():
    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    caches = (
        _validated_runtime_component_value,
        _validated_selected_reference_value,
        _validated_stable_runtime_environment_value,
        _validated_stable_decision_semantics_value,
    )
    for cache in caches:
        cache.cache_clear()

    started = time.perf_counter()
    _require_runtime_bundle_integrity(bundle)
    cold_seconds = time.perf_counter() - started
    cold_info = tuple(cache.cache_info() for cache in caches)

    started = time.perf_counter()
    _require_runtime_bundle_integrity(bundle)
    warm_seconds = time.perf_counter() - started
    warm_info = tuple(cache.cache_info() for cache in caches)

    assert tuple(info.misses for info in cold_info) == (
        len(bundle.components), len(bundle.selected_references), 1, 1)
    assert tuple(info.currsize for info in cold_info) == (
        len(bundle.components), len(bundle.selected_references), 1, 1)
    assert all(warm.hits > cold.hits
               for cold, warm in zip(cold_info, warm_info))
    assert tuple(info.currsize for info in warm_info) == \
        tuple(info.currsize for info in cold_info)
    assert warm_seconds < cold_seconds
    print(
        "RuntimeBundle integrity cache benchmark: "
        f"cold={cold_seconds:.6f}s warm={warm_seconds:.6f}s "
        f"speedup={cold_seconds / warm_seconds:.1f}x")


def test_runtime_environment_seal_integrity_rejects_mutable_receipt_state():
    bundle = _live_test_bundle()
    seal = bundle._selection_environment_seal

    original_semantics = seal.decision_semantics
    object.__setattr__(seal, "decision_semantics", list(original_semantics))
    try:
        with pytest.raises(RuntimeBundleError, match="seal structure"):
            _require_runtime_environment_seal_integrity(bundle, seal)
    finally:
        object.__setattr__(seal, "decision_semantics", original_semantics)
    _require_runtime_environment_seal_integrity(bundle, seal)

    original_canonical = seal.decision_semantics_canonical
    object.__setattr__(
        seal, "decision_semantics_canonical", bytearray(original_canonical))
    try:
        with pytest.raises(RuntimeBundleError, match="seal structure"):
            _require_runtime_environment_seal_integrity(bundle, seal)
    finally:
        object.__setattr__(
            seal, "decision_semantics_canonical", original_canonical)
    _require_runtime_environment_seal_integrity(bundle, seal)

    poisoned_canonical = bytes([original_canonical[0] ^ 1]) + \
        original_canonical[1:]
    object.__setattr__(
        seal, "decision_semantics_canonical", poisoned_canonical)
    try:
        with pytest.raises(RuntimeBundleError, match="semantics differ"):
            _require_runtime_environment_seal_integrity(bundle, seal)
    finally:
        object.__setattr__(
            seal, "decision_semantics_canonical", original_canonical)
    _require_runtime_environment_seal_integrity(bundle, seal)


def test_observed_runtime_environment_change_is_detected(monkeypatch):
    from kernel import runtime_bundle as runtime_bundle_module

    bundle = build_runtime_bundle(config.ACTIVE_PROFILE)
    monkeypatch.setattr(
        runtime_bundle_module.platform, "python_version", lambda: "0.0.0-hostile")
    with pytest.raises(RuntimeBundleError, match="observed interpreter"):
        assert_runtime_environment_compatible(bundle)


def test_stable_runtime_identity_excludes_host_paths_and_inodes(monkeypatch):
    live = require_live_python_import_posture(config.PACKAGE_ROOT)
    retained_components = _locked_components(config.PACKAGE_ROOT)
    stable = _stable_runtime_environment_document(live, retained_components)
    relocated = copy.deepcopy(live)
    physical_roots = [
        live["importPosture"]["projectRoot"],
        *live["importPosture"]["dependencyRoots"],
        *(root["path"] for root in live["standardRuntime"]["roots"]),
    ]
    standard_root_paths = [
        Path(root["path"]) for root in live["standardRuntime"]["roots"]
    ]
    standalone_paths = [
        entry["resolvedPath"]
        for entry in (
            *live["standardRuntime"]["archives"],
            *([live["standardRuntime"]["sharedLibrary"]]
              if live["standardRuntime"]["sharedLibrary"] is not None else []),
        )
        if not any(
            Path(entry["resolvedPath"]).is_relative_to(root)
            for root in standard_root_paths
        )
    ]
    physical_roots.extend(standalone_paths)
    replacements = {
        physical_roots[0]: "/relocated/ofarm-project",
        **{
            root: f"/relocated/ofarm-wheel-root-{index}"
            for index, root in enumerate(
                live["importPosture"]["dependencyRoots"])
        },
        **{
            root["path"]: f"/relocated/ofarm-runtime-root-{index}"
            for index, root in enumerate(live["standardRuntime"]["roots"])
        },
        **{
            path: f"/relocated/ofarm-runtime-file-{index}"
            for index, path in enumerate(standalone_paths)
        },
    }

    def relocate(value):
        if isinstance(value, dict):
            return {key: relocate(item) for key, item in value.items()}
        if isinstance(value, list):
            return [relocate(item) for item in value]
        if isinstance(value, str):
            for old, new in sorted(
                    replacements.items(), key=lambda item: len(item[0]), reverse=True):
                if value == old:
                    return new
                if value.startswith(old + os.sep):
                    return new + value[len(old):]
        return value

    relocated = relocate(relocated)
    relocated["python"]["pycachePrefix"] = "/relocated/absent-pycache"
    for index, image in enumerate(
            relocated["nativeRuntime"]["actualNativeImages"]):
        image["device"] = f"{index + 100:x}:{index + 200:x}"
        image["inode"] += 1_000_000

    assert _stable_runtime_environment_document(
        relocated, retained_components) == stable
    monkeypatch.setattr(Path, "exists", lambda _path: True)
    assert _stable_runtime_environment_document(
        relocated, retained_components) == stable
    assert _runtime_environment_component_from_document(
        relocated, retained_components) == \
        _runtime_environment_component_from_document(
            live, retained_components)
    retained = canonical_json(stable)
    assert all(root not in retained for root in physical_roots)
    assert all(set(image) == {
        "originLocator", "contentDigest", "byteLength", "classification",
        "distributions",
    } for image in stable["nativeRuntime"]["actualNativeImages"])
    assert "pathImporterCache" not in stable["importIdentity"]

    live_shared = live["standardRuntime"]["sharedLibrary"]
    if (live_shared is not None
            and any(image["resolvedPath"] == live_shared["resolvedPath"]
                    for image in live["nativeRuntime"]["actualNativeImages"])):
        stable_shared = stable["standardRuntime"]["sharedLibrary"]
        retained_native = next(
            image for image in stable["nativeRuntime"]["actualNativeImages"]
            if image["originLocator"] == stable_shared["originLocator"])
        assert (retained_native["contentDigest"], retained_native["byteLength"]) == (
            stable_shared["contentDigest"], stable_shared["byteLength"])
        forged_shared_native = copy.deepcopy(stable)
        forged_native = next(
            image for image in forged_shared_native["nativeRuntime"]
            ["actualNativeImages"]
            if image["originLocator"] == stable_shared["originLocator"])
        forged_native["contentDigest"] = "sha256:" + "e" * 64
        with pytest.raises(RuntimeBundleError, match="native image identity"):
            _validate_stable_runtime_environment_document(
                forged_shared_native, retained_components)

    changed = copy.deepcopy(relocated)
    module = next(
        item for item in changed["importPosture"]["actualModules"]
        if "contentDigest" in item)
    module["contentDigest"] = "sha256:" + "f" * 64
    with pytest.raises(RuntimeBundleError, match="classification identity"):
        _stable_runtime_environment_document(changed, retained_components)

    unowned = copy.deepcopy(relocated)
    unowned_module = next(
        item for item in unowned["importPosture"]["actualModules"]
        if isinstance(item.get("origin"), str)
        and item["origin"] not in {"built-in", "frozen"})
    unowned_module["origin"] = "/Users/alice/private/unowned.py"
    unowned_module["classification"] = "UNKNOWN"
    unowned_module.pop("retainedComponent", None)
    unowned_module.pop("distributions", None)
    with pytest.raises(RuntimeBundleError, match="outside every retained root"):
        _stable_runtime_environment_document(unowned, retained_components)

    malformed_raw_documents = []
    malformed_raw = copy.deepcopy(relocated)
    malformed_raw["process"]["localeEnvironment"] = None
    malformed_raw_documents.append(malformed_raw)
    malformed_raw = copy.deepcopy(relocated)
    malformed_raw["python"]["pycachePrefix"] = 7
    malformed_raw_documents.append(malformed_raw)
    malformed_raw = copy.deepcopy(relocated)
    ambient_name = next(iter(malformed_raw["importPosture"]
                             ["ambientEnvironment"]))
    malformed_raw["importPosture"]["ambientEnvironment"][ambient_name] = 7
    malformed_raw_documents.append(malformed_raw)
    malformed_raw = copy.deepcopy(relocated)
    malformed_raw["importPosture"]["startupCustomizationModules"] = [1]
    malformed_raw_documents.append(malformed_raw)
    malformed_raw = copy.deepcopy(relocated)
    malformed_raw["importPosture"]["sysPath"][1]["index"] = True
    malformed_raw_documents.append(malformed_raw)
    for malformed_raw in malformed_raw_documents:
        with pytest.raises(RuntimeBundleError, match="malformed"):
            _stable_runtime_environment_document(
                malformed_raw, retained_components)

    malformed = copy.deepcopy(stable)
    malformed["python"]["hostHome"] = "Users/alice/private-runtime"
    with pytest.raises(RuntimeBundleError, match="Python identity"):
        _validate_stable_runtime_environment_document(
            malformed, retained_components)

    unsafe = copy.deepcopy(stable)
    unsafe["importIdentity"]["sysPath"][0]["rootLocator"] = \
        "PROJECT_ROOT/../host-private"
    with pytest.raises(RuntimeBundleError, match="locator"):
        _validate_stable_runtime_environment_document(
            unsafe, retained_components)

    bool_index = copy.deepcopy(stable)
    bool_index["importIdentity"]["sysPath"][1]["index"] = True
    with pytest.raises(RuntimeBundleError, match="sys.path entry"):
        _validate_stable_runtime_environment_document(
            bool_index, retained_components)

    forged_root = copy.deepcopy(stable)
    forged_root["distributions"][0]["rootLocator"] = \
        "LOCKED_WHEEL_ROOT[sha256:" + "e" * 64 + "]"
    with pytest.raises(RuntimeBundleError, match="root content identity"):
        _validate_stable_runtime_environment_document(
            forged_root, retained_components)

    forged_suffix = copy.deepcopy(stable)
    distribution_module = next(
        item for item in forged_suffix["importIdentity"]["actualModules"]
        if item["classification"] == "RETAINED_DISTRIBUTION_FILE")
    distribution_root = distribution_module["originLocator"].split("/", 1)[0]
    distribution_module["originLocator"] = \
        distribution_root + "/not-in-the-retained-wheel.py"
    with pytest.raises(RuntimeBundleError, match="module classification"):
        _validate_stable_runtime_environment_document(
            forged_suffix, retained_components)

    forged_namespace = copy.deepcopy(stable)
    namespace_module = forged_namespace["importIdentity"]["actualModules"][0]
    namespace_module.clear()
    namespace_module.update({
        "name": stable["importIdentity"]["actualModules"][0]["name"],
        "loader": None,
        "classification": "RETAINED_NAMESPACE",
        "originLocator": None,
        "packageSearchLocators": ["PROJECT_ROOT/not-retained"],
        "specSearchLocators": [],
    })
    with pytest.raises(RuntimeBundleError, match="project locator"):
        _validate_stable_runtime_environment_document(
            forged_namespace, retained_components)

    forged_root_namespace = copy.deepcopy(stable)
    namespace_module = forged_root_namespace["importIdentity"]["actualModules"][0]
    namespace_module.clear()
    namespace_module.update({
        "name": stable["importIdentity"]["actualModules"][0]["name"],
        "loader": None,
        "classification": "RETAINED_NAMESPACE",
        "originLocator": None,
        "packageSearchLocators": ["PROJECT_ROOT"],
        "specSearchLocators": ["PROJECT_ROOT"],
    })
    with pytest.raises(RuntimeBundleError, match="classification identity"):
        _validate_stable_runtime_environment_document(
            forged_root_namespace, retained_components)

    non_code = next(
        component for component in retained_components
        if component.role not in {
            "RUNTIME_CODE", "RUNTIME_CATALOG_CODE", "PARSER_CODE"}
        and component.repository_path.endswith(".json"))
    forged_non_code_module = copy.deepcopy(stable)
    module = forged_non_code_module["importIdentity"]["actualModules"][0]
    module.clear()
    module.update({
        "name": stable["importIdentity"]["actualModules"][0]["name"],
        "loader": "_frozen_importlib_external.SourceFileLoader",
        "classification": "RETAINED_PROJECT_COMPONENT",
        "originLocator": f"PROJECT_ROOT/{non_code.repository_path}",
        "packageSearchLocators": [],
        "specSearchLocators": [],
        "contentDigest": non_code.content_digest,
        "byteLength": len(non_code.canonical_bytes),
        "retainedComponent": {
            "role": non_code.role,
            "logicalRef": non_code.logical_ref,
        },
    })
    with pytest.raises(RuntimeBundleError, match="classification identity"):
        _validate_stable_runtime_environment_document(
            forged_non_code_module, retained_components)

    if stable["standardRuntime"]["sharedLibrary"] is not None:
        forged_standalone = copy.deepcopy(stable)
        forged_standalone["standardRuntime"]["sharedLibrary"] \
            ["originLocator"] += "/host-suffix"
        with pytest.raises(RuntimeBundleError, match="content locator"):
            _validate_stable_runtime_environment_document(
                forged_standalone, retained_components)

    if stable["nativeRuntime"]["actualNativeImages"]:
        unknown_native = copy.deepcopy(stable)
        unknown_native["nativeRuntime"]["actualNativeImages"][0] \
            ["classification"] = "UNKNOWN"
        with pytest.raises(RuntimeBundleError, match="native image identity"):
            _validate_stable_runtime_environment_document(
                unknown_native, retained_components)

    auxiliary = next((
        item for item in stable["importIdentity"]["actualModules"]
        if item["classification"] == "REVIEWED_NATIVE_AUXILIARY"
    ), None)
    if auxiliary is not None:
        forged_parent = copy.deepcopy(stable)
        parent = next(
            item for item in forged_parent["importIdentity"]["actualModules"]
            if item["name"] == auxiliary["name"])
        parent["retainedParent"]["originLocator"] = \
            parent["retainedParent"]["originLocator"].split("/", 1)[0]
        with pytest.raises(RuntimeBundleError, match="classification"):
            _validate_stable_runtime_environment_document(
                forged_parent, retained_components)

        forged_parent_name = copy.deepcopy(stable)
        parent = next(
            item for item in forged_parent_name["importIdentity"]["actualModules"]
            if item["name"] == auxiliary["name"])
        parent["retainedParent"]["name"] = auxiliary["name"]
        with pytest.raises(RuntimeBundleError, match="classification"):
            _validate_stable_runtime_environment_document(
                forged_parent_name, retained_components)

    if stable["nativeRuntime"]["containerBoundary"] == "PINNED_READ_ONLY_IMAGE":
        missing_loader = copy.deepcopy(stable)
        missing_loader["nativeRuntime"]["loaderConfiguration"]["files"].clear()
        with pytest.raises(RuntimeBundleError, match="native runtime inventory"):
            _validate_stable_runtime_environment_document(
                missing_loader, retained_components)

        missing_native = copy.deepcopy(stable)
        missing_native["nativeRuntime"]["actualNativeImages"].clear()
        with pytest.raises(RuntimeBundleError, match="native runtime inventory"):
            _validate_stable_runtime_environment_document(
                missing_native, retained_components)


def test_stable_locator_c0_control_check_is_exact():
    matched_codepoints = {
        codepoint
        for codepoint in range(sys.maxunicode + 1)
        if _C0_CONTROL_RE.search(f"safe{chr(codepoint)}suffix") is not None
    }

    assert matched_codepoints == set(range(32))
    for codepoint in range(32):
        relative = f"safe{chr(codepoint)}suffix"
        with pytest.raises(RuntimeBundleError, match="unsafe relative locator"):
            _join_stable_locator("PROJECT_ROOT", PurePosixPath(relative))
        assert _stable_locator_parts(f"PROJECT_ROOT/{relative}") is None

    for character in ("\x7f", "\x85", "\u2028", "\ud800"):
        relative = f"safe{character}suffix"
        locator = f"PROJECT_ROOT/{relative}"
        assert _join_stable_locator(
            "PROJECT_ROOT", PurePosixPath(relative)) == locator
        assert _stable_locator_parts(locator) == ("PROJECT_ROOT", relative)


def test_stable_locator_inventory_index_preserves_ancestor_boundaries():
    standard_root = f"PINNED_IMAGE_ROOT[sha256:{'a' * 64}]"
    wheel_root = f"LOCKED_WHEEL_ROOT[sha256:{'b' * 64}]"
    missing_root = f"LOCKED_WHEEL_ROOT[sha256:{'c' * 64}]"
    inventory = {
        f"{standard_root}/lib/python3.12/pkg/module.py": object(),
        f"{standard_root}/lib/python3.12/pkg/sub/other.py": object(),
        f"{standard_root}/lib/python3.12/pkgish/sibling.py": object(),
        f"{standard_root}/unsafe/../ignored.py": object(),
        f"{wheel_root}/example/__init__.py": object(),
    }
    index = _retained_locator_ancestor_index(inventory)

    for retained in inventory:
        if "/../" not in retained:
            assert _inventory_contains_path(retained, index)
    assert _inventory_contains_path(standard_root, index)
    assert _inventory_contains_path(f"{standard_root}/lib", index)
    assert _inventory_contains_path(
        f"{standard_root}/lib/python3.12/pkg/sub", index)
    assert not _inventory_contains_path(
        f"{standard_root}/lib/python3.12/pk", index)
    assert not _inventory_contains_path(
        f"{standard_root}/lib/python3.12/pkg/sibling", index)
    assert not _inventory_contains_path(f"{standard_root}/unsafe", index)
    assert not _inventory_contains_path(f"{missing_root}/example", index)
    assert not _inventory_contains_path("not-a-stable-locator", index)


def test_selection_to_activation_refuses_fake_retained_origin_module():
    bundle = _live_test_bundle()
    module_name = f"_ofarm_selection_gap_{uuid.uuid4().hex}"
    source = str(Path(json.__file__).resolve())
    loader = importlib.machinery.SourceFileLoader(module_name, source)
    module = types.ModuleType(module_name)
    module.__file__ = source
    module.__loader__ = loader
    module.__spec__ = importlib.machinery.ModuleSpec(
        module_name, loader=loader, origin=source)
    sys.modules[module_name] = module
    try:
        with pytest.raises(RuntimeBundleError, match="changed after selection"):
            assert_runtime_environment_compatible(bundle)
    finally:
        del sys.modules[module_name]


def test_import_posture_refuses_behavior_on_originless_project_namespace():
    module_name = f"issue171_namespace_{uuid.uuid4().hex}"
    module = types.ModuleType(module_name)
    module.__package__ = module_name
    module.__loader__ = None
    module.__file__ = None
    module.__path__ = [str(config.PACKAGE_ROOT)]
    module.__spec__ = importlib.machinery.ModuleSpec(
        module_name, loader=None, is_package=True)
    module.__spec__.submodule_search_locations = [str(config.PACKAGE_ROOT)]
    module.hostile_behavior = lambda: "unretained"
    sys.modules[module_name] = module
    try:
        with pytest.raises(RuntimeBundleError, match="outside retained identities"):
            require_live_python_import_posture(config.PACKAGE_ROOT)
    finally:
        del sys.modules[module_name]


def test_live_seal_refuses_originless_namespace_metadata_mutation():
    import tooling

    bundle = _live_test_bundle()
    original = tooling.__package__
    tooling.__package__ = "hostile.tooling"
    try:
        with pytest.raises(RuntimeBundleError):
            assert_runtime_environment_compatible(bundle)
    finally:
        tooling.__package__ = original


def test_every_loaded_reviewed_originless_auxiliary_has_stable_state_identity():
    from kernel import runtime_bundle as runtime_bundle_module

    loaded = []
    for name in runtime_bundle_module._REVIEWED_ORIGINLESS_AUXILIARY_MODULES:
        module = sys.modules.get(name)
        if module is None:
            continue
        loaded.append(name)
        assert re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            runtime_bundle_module._originless_module_state_digest(
                name, module, config.PACKAGE_ROOT),
        )
    assert loaded


def test_live_seal_refuses_originless_namespace_child_object_replacement():
    import tooling
    from tooling import runtime_bundle_lock

    bundle = _live_test_bundle()
    replacement = types.ModuleType(runtime_bundle_lock.__name__)
    tooling.runtime_bundle_lock = replacement
    try:
        with pytest.raises(RuntimeBundleError):
            assert_runtime_environment_compatible(bundle)
    finally:
        tooling.runtime_bundle_lock = runtime_bundle_lock


def test_live_seal_refuses_originless_auxiliary_state_mutation():
    import pyexpat

    bundle = _live_test_bundle()
    original = pyexpat.errors.XML_ERROR_ABORTED
    pyexpat.errors.XML_ERROR_ABORTED = "hostile parsing outcome"
    try:
        with pytest.raises(RuntimeBundleError):
            assert_runtime_environment_compatible(bundle)
    finally:
        pyexpat.errors.XML_ERROR_ABORTED = original


def test_live_seal_refuses_pseudo_module_auxiliary_state_mutation():
    import typing

    class PseudoAuxiliary:
        pass

    pseudo = PseudoAuxiliary()
    pseudo.__name__ = "typing.io"
    pseudo.__package__ = None
    pseudo.__doc__ = "reviewed pseudo-module probe"
    pseudo.__loader__ = None
    pseudo.__spec__ = None
    pseudo.marker = "selected"
    prior_module = sys.modules.get("typing.io")
    prior_attribute = getattr(typing, "io", None)
    sys.modules["typing.io"] = pseudo
    typing.io = pseudo
    try:
        bundle = _live_test_bundle()
        pseudo.marker = "mutated"
        with pytest.raises(RuntimeBundleError):
            assert_runtime_environment_compatible(bundle)
    finally:
        if prior_module is None:
            del sys.modules["typing.io"]
        else:
            sys.modules["typing.io"] = prior_module
        if prior_attribute is None:
            del typing.io
        else:
            typing.io = prior_attribute


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


def test_profile_register_frozen_methods_refuse_assignment_and_deletion():
    cases = (
        (context.ProductRegister(), "lookup_by_decision"),
        (GerkLayer(), "lookup"),
        (FFSNapraveRegister(), "match"),
    )

    for register, method_name in cases:
        register.freeze()
        with pytest.raises(AttributeError, match="immutable"):
            setattr(register, method_name, lambda *_args: None)
        with pytest.raises(AttributeError, match="cannot be deleted"):
            delattr(register, method_name)
        assert method_name not in vars(register)


@pytest.mark.parametrize("register_kind", ("product", "gerk", "ffsnaprave"))
def test_construction_seam_cache_cannot_be_upgraded_to_bundle_runtime(
        fresh_env, register_kind):
    from kernel.context import require_product_register_runtime_composition
    from kernel.profiles.si_ffs.ffsnaprave_adapter import (
        require_ffsnaprave_register_runtime_composition,
    )
    from kernel.profiles.si_ffs.gerk_adapter import (
        require_gerk_layer_runtime_composition,
    )

    store, _pipeline, _outputs = fresh_env
    bundle = store.runtime_bundle
    if register_kind == "product":
        register = context.ProductRegister()
        register.register_artifact("referencesnapshot:test.forged-product", {
            "products": [{"regsrCode": "FORGED", "name": "Forged"}],
            "productDetails": [],
        })
        guard = require_product_register_runtime_composition
    elif register_kind == "gerk":
        register = GerkLayer()
        register.register_artifact("referencesnapshot:test.forged-gerk", {
            "features": [{
                "gerkPid": "9999999", "area": "999", "rabaId": "FORGED",
            }],
        })
        guard = require_gerk_layer_runtime_composition
    else:
        register = FFSNapraveRegister()
        register.register_artifact("referencesnapshot:test.forged-ffsnaprave", {
            "inspections": [{
                "StevilkaZnaka": "FORGED",
                "VeljavnostZnaka": "2099-12-31",
            }],
        })
        guard = require_ffsnaprave_register_runtime_composition

    register.freeze()
    object.__setattr__(register, "runtime_bundle", bundle)
    with pytest.raises(RuntimeBundleError, match="cache was not derived"):
        with store.serialized_tx():
            guard(store, register, "forged construction-seam upgrade")


@pytest.mark.parametrize("register_kind", ("product", "gerk", "ffsnaprave"))
def test_profile_register_callable_shadow_poisons_active_transaction(
        fresh_env, register_kind):
    from kernel.context import require_product_register_runtime_composition
    from kernel.profiles.si_ffs.ffsnaprave_adapter import (
        require_ffsnaprave_register_runtime_composition,
    )
    from kernel.profiles.si_ffs.gerk_adapter import (
        require_gerk_layer_runtime_composition,
    )

    store, _pipeline, _outputs = fresh_env
    bundle = store.runtime_bundle
    bindings = context.SIReferenceBindings.from_descriptor(
        bundle.descriptor, runtime_bundle=bundle)
    cases = {
        "product": (
            context.ProductRegister(bindings, runtime_bundle=bundle),
            "lookup_by_decision",
            require_product_register_runtime_composition,
        ),
        "gerk": (
            GerkLayer(runtime_bundle=bundle),
            "lookup",
            require_gerk_layer_runtime_composition,
        ),
        "ffsnaprave": (
            FFSNapraveRegister(runtime_bundle=bundle),
            "match",
            require_ffsnaprave_register_runtime_composition,
        ),
    }
    register, method_name, guard = cases[register_kind]

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx():
            object.__setattr__(register, method_name, lambda *_args: None)
            try:
                with pytest.raises(
                        RuntimeBundleError, match="runtime composition changed"):
                    guard(store, register, "hostile callable shadow")
            finally:
                object.__delattr__(register, method_name)


def test_si_resolvers_and_evidence_attachment_reject_duck_and_subclass_registers(
        fresh_env):
    from kernel.profiles.si_ffs import si_bindings
    from kernel.profiles.si_ffs.ffsnaprave_adapter import (
        attach_inspection_evidence,
    )

    store, _pipeline, _outputs = fresh_env
    bundle = store.runtime_bundle
    bindings = context.SIReferenceBindings.from_descriptor(
        bundle.descriptor, runtime_bundle=bundle)

    class ProductRegisterSubclass(context.ProductRegister):
        pass

    class DuckGerkLayer:
        runtime_bundle = bundle
        _frozen = True

        def lookup(self, *_args):
            return None

    class FFSNapraveRegisterSubclass(FFSNapraveRegister):
        pass

    product = ProductRegisterSubclass(bindings, runtime_bundle=bundle)
    gerk = DuckGerkLayer()
    ffsnaprave = FFSNapraveRegisterSubclass(runtime_bundle=bundle)

    calls = (
        lambda cur: si_bindings.resolve_product_authorisation(
            store, cur, product, "FORGED-DECISION", "resource:test.forged",
            created_by=demo.FARMER, evidence_ref=demo.ONBOARDING_EVIDENCE),
        lambda cur: si_bindings.resolve_parcel(
            store, cur, gerk, "9999999", "field:test.forged",
            created_by=demo.FARMER, evidence_ref=demo.ONBOARDING_EVIDENCE),
        lambda cur: si_bindings.resolve_equipment(
            store, cur, ffsnaprave, "FORGED", "equipment:test.forged",
            created_by=demo.FARMER, evidence_ref=demo.ONBOARDING_EVIDENCE),
        lambda _cur: attach_inspection_evidence(
            store, ffsnaprave,
            "referencesnapshot:test.forged-ffsnaprave", "FORGED",
            captured_by=demo.FARMER, farm_ref=demo.FARM),
    )

    for call in calls:
        with pytest.raises(
                RuntimeBundleError, match="runtime composition changed"):
            with store.serialized_tx() as cur:
                call(cur)


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
        _runtime_environment_seal = bundle._selection_environment_seal

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
    _assert_exact_http_receipt(response, store.runtime_bundle_digest)


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
    _assert_exact_http_receipt(response, store.runtime_bundle_digest)


def test_read_and_output_apis_receipt_exact_response_payloads(fresh_env):
    from fastapi.testclient import TestClient
    from kernel.api import create_app

    store, _pipeline, _outputs = fresh_env
    app = create_app(store, oidc=None)
    client = TestClient(app)
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
        _assert_exact_http_receipt(response, store.runtime_bundle_digest)


def test_record_api_blocks_authority_instance_dispatch_shadow(fresh_env):
    from kernel.api import create_app

    store, _pipeline, _outputs = fresh_env
    app = create_app(store, oidc=None)
    called = False

    def hostile_allow(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("hostile read-authority override executed")

    with pytest.raises(AttributeError, match="runtime composition is immutable"):
        app.state.outputs.authority.evaluate_read = hostile_allow
    assert called is False


def test_health_and_api_refusals_receipt_exact_response_payloads(fresh_env):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from kernel.api import _ReceiptedApplication, create_app

    store, _pipeline, _outputs = fresh_env
    app = create_app(store, oidc=None)
    client = TestClient(app)
    responses = [
        client.get("/health"),
        client.get(f"/records/{demo.FARMER}"),
        client.get(
            "/records/record:does-not-exist",
            headers={"X-Acting-Party": demo.FARMER},
        ),
        client.post(
            "/commit",
            headers={"X-Acting-Party": demo.WORKER},
            json={"submission": demo.spray_submission(
                f"issue171:api-actor-refusal:{uuid.uuid4().hex}",
                confirm=True,
            )},
        ),
        client.post(
            "/commit",
            headers={"X-Acting-Party": demo.FARMER},
            json={},
        ),
        client.get("/route-that-does-not-exist"),
        client.get("/docs"),
        client.get("/redoc"),
        client.get("/openapi.json"),
        client.get("/health/"),
    ]
    assert [response.status_code for response in responses] == \
        [200, 401, 404, 403, 422, 404, 404, 404, 404, 404]
    for response in responses:
        _assert_exact_http_receipt(response, store.runtime_bundle_digest)

    # HTTP suppresses the representation body for HEAD. The receipt must cover
    # the empty bytes the client actually receives, while preserving the 405's
    # method-discovery header.
    head_response = client.head("/health")
    assert head_response.status_code == 405
    assert head_response.headers["allow"] == "GET"
    _assert_exact_http_receipt(
        head_response,
        store.runtime_bundle_digest,
        canonicalization=RAW_CANONICALIZATION,
        expected_content=b"",
        expect_content_length=False,
    )

    # Exercise the generic outer boundary with all hostile routes registered
    # before wrapping.  The production create_app() graph is already sealed
    # when returned and cannot expose a test-only, unbound construction seam.
    hostile_inner = FastAPI(
        openapi_url=None, docs_url=None, redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
    )

    @hostile_inner.get("/_test/unhandled-runtime-error")
    def unhandled_runtime_error():
        raise RuntimeError("hostile detail must never cross the HTTP boundary")

    @hostile_inner.get("/_test/unreceipted-response")
    def unreceipted_response():
        return {"forged": True}

    hostile_boundary = _ReceiptedApplication(
        hostile_inner, store.runtime_bundle_digest)
    hostile_boundary._seal()
    hostile_client = TestClient(
        hostile_boundary, raise_server_exceptions=False)
    unhandled = hostile_client.get("/_test/unhandled-runtime-error")
    assert unhandled.status_code == 500
    assert unhandled.json() == {"detail": "Internal Server Error"}
    assert b"hostile detail" not in unhandled.content
    _assert_exact_http_receipt(unhandled, store.runtime_bundle_digest)

    unreceipted = hostile_client.get("/_test/unreceipted-response")
    assert unreceipted.status_code == 500
    assert unreceipted.json() == {"detail": "Internal Server Error"}
    _assert_exact_http_receipt(unreceipted, store.runtime_bundle_digest)


def test_http_graph_mutation_is_stopped_before_dispatch(fresh_env):
    from fastapi.testclient import TestClient
    from kernel.api import create_app

    store, _pipeline, _outputs = fresh_env
    app = create_app(store, oidc=None)
    with pytest.raises(AttributeError):
        app.get("/_test/late-route")(lambda: {"late": True})
    client = TestClient(app, raise_server_exceptions=False)
    baseline = client.get("/health")
    assert baseline.status_code == 200

    health_route = next(route for route in app.router.routes
                        if getattr(route, "path", None) == "/health")
    original_app = health_route.app
    called = False

    async def hostile_route(_scope, _receive, _send):
        nonlocal called
        called = True

    health_route.app = hostile_route
    try:
        response = client.get("/health")
    finally:
        health_route.app = original_app
    assert response.status_code == 500
    assert called is False
    _assert_exact_http_receipt(response, store.runtime_bundle_digest)

    original_store = app.state.store
    app.state.store = object()
    try:
        state_response = client.get("/health")
    finally:
        app.state.store = original_store
    assert state_response.status_code == 500
    assert state_response.json() == {"detail": "Internal Server Error"}
    _assert_exact_http_receipt(state_response, store.runtime_bundle_digest)

    with pytest.raises(TypeError):
        app.dependency_overrides[app.state.get_principal] = lambda: demo.FARMER


def test_http_graph_covers_regex_route_handle_router_stack_and_helpers(
        fresh_env, monkeypatch):
    from fastapi.testclient import TestClient
    from kernel import api as api_runtime
    from kernel.api import create_app

    store, _pipeline, _outputs = fresh_env
    app = create_app(store, oidc=None)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/health").status_code == 200
    health_route = next(route for route in app.router.routes
                        if getattr(route, "path", None) == "/health")

    original_regex = health_route.path_regex

    class BehavioralRegex:
        pattern = original_regex.pattern
        flags = original_regex.flags

        def match(self, value):
            return original_regex.match(value)

    health_route.path_regex = BehavioralRegex()
    try:
        regex_response = client.get("/health")
    finally:
        health_route.path_regex = original_regex
    assert regex_response.status_code == 500
    _assert_exact_http_receipt(regex_response, store.runtime_bundle_digest)

    route_type = type(health_route)
    original_handle = route_type.handle
    handle_called = False

    async def hostile_handle(_self, _scope, _receive, _send):
        nonlocal handle_called
        handle_called = True

    route_type.handle = hostile_handle
    try:
        handle_response = client.get("/health")
    finally:
        route_type.handle = original_handle
    assert handle_response.status_code == 500
    assert handle_called is False
    _assert_exact_http_receipt(handle_response, store.runtime_bundle_digest)

    original_router_stack = app.router.middleware_stack
    stack_called = False

    async def hostile_stack(_scope, _receive, _send):
        nonlocal stack_called
        stack_called = True

    app.router.middleware_stack = hostile_stack
    try:
        stack_response = client.get("/health")
    finally:
        app.router.middleware_stack = original_router_stack
    assert stack_response.status_code == 500
    assert stack_called is False
    _assert_exact_http_receipt(stack_response, store.runtime_bundle_digest)

    original_helper = api_runtime._route_graph_state
    monkeypatch.setattr(
        api_runtime, "_route_graph_state", lambda _route: ("forged",))
    helper_response = client.get("/health")
    monkeypatch.setattr(api_runtime, "_route_graph_state", original_helper)
    assert helper_response.status_code == 500
    _assert_exact_http_receipt(helper_response, store.runtime_bundle_digest)


def test_http_wire_validator_rejects_duplicate_terminal_body_messages():
    from kernel.api import _validate_receipted_messages

    bundle_digest = "sha256:" + "0" * 64
    body = canonical_json({"forged": True}).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"x-ofarm-runtime-bundle-digest",
         bundle_digest.encode("ascii")),
        (b"x-ofarm-receipt-payload-digest",
         sha256_bytes(body).encode("ascii")),
        (b"x-ofarm-receipt-canonicalization",
         JSON_CANONICALIZATION.encode("ascii")),
    ]

    messages = (
        {
            "type": "http.response.start", "status": 200,
            "headers": headers,
        },
        {"type": "http.response.body", "body": body},
        {"type": "http.response.body", "body": body},
    )
    assert not _validate_receipted_messages(
        messages, bundle_digest, "GET")


def test_runtime_bundle_mixed_bundle_write_is_refused(fresh_env):
    store, _pipeline, _outputs = fresh_env
    bundle_b = _variant_bundle(store.runtime_bundle)
    with pytest.raises(RuntimeError, match="different RuntimeBundle"):
        with store.serialized_tx() as cur:
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
    with Store._raw_connection(store).cursor() as cur:
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
    with Store._raw_connection(store).cursor() as cur:
        with pytest.raises(RuntimeError, match="exact active governed cursor"):
            store.install_runtime_bundle(cur, store.runtime_bundle)


def test_runtime_bundle_each_transaction_restores_and_verifies_database_posture(
        fresh_env):
    store, _pipeline, _outputs = fresh_env
    selected = store.runtime_bundle.component(
        "RUNTIME_DATABASE_OBSERVED", "environment:observed-postgresql.v1")
    mutations = (
        ("TimeZone", "Europe/Ljubljana", "UTC"),
        ("DateStyle", "SQL, DMY", "ISO, MDY"),
        ("IntervalStyle", "iso_8601", "postgres"),
        ("search_path", "public", "pg_catalog, public"),
        ("session_replication_role", "replica", "origin"),
        ("default_transaction_isolation", "repeatable read", "read committed"),
        ("standard_conforming_strings", "off", "on"),
        ("extra_float_digits", "0", "1"),
        ("bytea_output", "escape", "hex"),
    )

    for setting_name, poison, retained_value in mutations:
        poisoned = Store._raw_connection(store).execute(
            "SELECT pg_catalog.set_config(%s, %s, false) AS value",
            (setting_name, poison),
        ).fetchone()["value"]
        assert poisoned != retained_value
        party_id = f"party:issue171.session-posture.{uuid.uuid4().hex}"
        with store.serialized_tx() as cur:
            observed = store._observe_database_environment(cur)
            assert database_runtime_environment_component(observed) == selected
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": party_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 session posture test (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
        assert store.get_record(party_id) is not None


def test_runtime_bundle_late_database_posture_drift_rolls_back_current_transaction(
        fresh_env):
    store, _pipeline, _outputs = fresh_env
    mutations = (
        ("TimeZone", "Europe/Ljubljana"),
        ("DateStyle", "SQL, DMY"),
        ("IntervalStyle", "iso_8601"),
        ("search_path", "public"),
        ("session_replication_role", "replica"),
        ("standard_conforming_strings", "off"),
        ("extra_float_digits", "0"),
        ("bytea_output", "escape"),
    )

    for setting_name, poison in mutations:
        party_id = f"party:issue171.late-db-posture.{uuid.uuid4().hex}"
        with pytest.raises(
                RuntimeError,
                match="PostgreSQL transaction did not retain"):
            with store.serialized_tx() as cur:
                store.insert_record(cur, {
                    "schemaVersion": "ofarm.party.v0.1",
                    "partyId": party_id,
                    "partyClass": "NATURAL_PERSON",
                    "displayName": "Issue 171 late DB posture test (fictional)",
                    "partyState": "ACTIVE",
                    "recordedAt": context.now_iso(),
                })
                store._transaction_state.connection.execute(
                    "SELECT pg_catalog.set_config(%s, %s, true) AS value",
                    (setting_name, poison),
                )
        assert store.get_record(party_id) is None


def test_runtime_bundle_same_transaction_ddl_rolls_back_before_commit(fresh_env):
    store, _pipeline, _outputs = fresh_env
    party_id = f"party:issue171.late-ddl.{uuid.uuid4().hex}"
    relation = f"issue171_late_ddl_{uuid.uuid4().hex}"

    with pytest.raises(SchemaGuardError, match="catalog-drifted"):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": party_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 late DDL test (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            store._transaction_state.connection.execute(
                sql.SQL("CREATE TABLE public.{} (value text)").format(
                    sql.Identifier(relation))
            )

    assert store.get_record(party_id) is None
    with store.tx() as cur:
        cur._execute_read(
            "SELECT pg_catalog.to_regclass(%s) AS relation",
            (f"public.{relation}",),
        )
        assert cur.fetchone()["relation"] is None


def test_runtime_bundle_transaction_refuses_temporary_schema_shadow(fresh_env):
    store, _pipeline, _outputs = fresh_env
    Store._raw_connection(store).execute(
        "CREATE TEMP TABLE kernel_record "
        "(LIKE public.kernel_record INCLUDING ALL)"
    )
    try:
        with pytest.raises(SchemaGuardError, match="temporary schema"):
            store.get_record(demo.FARMER)
    finally:
        Store._raw_connection(store).execute(
            "DROP TABLE pg_temp.kernel_record")


def test_runtime_bundle_outer_transaction_rechecks_live_catalog(fresh_env):
    store, _pipeline, _outputs = fresh_env
    entered = False
    Store._raw_connection(store).execute(
        "CREATE AGGREGATE public.hostile_runtime_sum(integer) "
        "(SFUNC = pg_catalog.int4pl, STYPE = integer, INITCOND = '0')"
    )
    try:
        with pytest.raises(SchemaGuardError, match="catalog-drifted"):
            with store.tx():
                entered = True
        assert entered is False
    finally:
        Store._raw_connection(store).execute(
            "DROP AGGREGATE public.hostile_runtime_sum(integer)")
    with store.tx() as cur:
        cur._execute_read("SELECT 1 AS ok")
        assert cur.fetchone()["ok"] == 1


def test_runtime_bundle_outer_transaction_refuses_ambient_connection_state(
        fresh_env):
    store, _pipeline, _outputs = fresh_env

    Store._raw_connection(store).execute(
        "BEGIN ISOLATION LEVEL REPEATABLE READ")
    try:
        with pytest.raises(RuntimeError, match="ambient transactions are forbidden"):
            store.get_record(demo.FARMER)
    finally:
        Store._raw_connection(store).rollback()

    Store._raw_connection(store).autocommit = False
    try:
        with pytest.raises(RuntimeError, match="autocommit connection to be IDLE"):
            store.get_record(demo.FARMER)
    finally:
        Store._raw_connection(store).autocommit = True


def test_governed_transaction_requires_exact_nested_ownership(fresh_env):
    store, _pipeline, _outputs = fresh_env

    for forged_depth in (True, "1", 1):
        store._transaction_state.depth = forged_depth
        try:
            expected = ("exact integer" if forged_depth != 1
                        or type(forged_depth) is not int else "ownership")
            with pytest.raises(RuntimeError, match=expected):
                with Store.tx(store):
                    pass
        finally:
            del store._transaction_state.depth

    Store._raw_connection(store).execute("BEGIN")
    store._transaction_state.depth = 1
    try:
        with pytest.raises(RuntimeError, match="ownership"):
            with Store.tx(store):
                pass
    finally:
        del store._transaction_state.depth
        Store._raw_connection(store).rollback()


def test_governed_transaction_valid_nesting_and_cleanup(fresh_env):
    store, _pipeline, _outputs = fresh_env
    with Store.tx(store) as outer:
        outer._execute_read("SELECT 1 AS outer_value")
        assert outer.fetchone()["outer_value"] == 1
        with Store.tx(store) as inner:
            inner._execute_read("SELECT 2 AS inner_value")
            assert inner.fetchone()["inner_value"] == 2

    class BodyFailure(Exception):
        pass

    with pytest.raises(BodyFailure):
        with Store.serialized_tx(store):
            raise BodyFailure
    assert Store._transaction_depth(store) == 0
    assert store._active_transaction_token is None
    assert not any(hasattr(store._transaction_state, name)
                   for name in (
                       "token", "ownerThread", "connection",
                       "integrity",
                   ))
    assert store._active_transaction_integrity is None


def test_caught_runtime_integrity_failure_poison_rolls_back_transaction(
        fresh_env):
    from kernel import policy

    store, pipeline, _outputs = fresh_env
    party_id = f"party:issue171.rollback-only.{uuid.uuid4().hex}"
    marker = "ISSUE171_CAUGHT_SEMANTIC_MUTATION"

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": party_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 rollback-only test (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            policy.COMMIT_CLASS_TO_FAMILY[marker] = "HOSTILE_EVENT"
            try:
                with pytest.raises(
                        RuntimeBundleError, match="decision semantic state"):
                    GatePipeline._assert_runtime_composition(pipeline)
            finally:
                policy.COMMIT_CLASS_TO_FAMILY.pop(marker, None)
            latch = store._active_transaction_integrity
            with pytest.raises(AttributeError, match="one-way"):
                latch.poisoned = False
            # Replacing the public thread-local pointer cannot replace or
            # clear the Store-retained one-way latch.
            store._transaction_state.integrity = object()

    assert store.get_record(party_id) is None


def test_context_structural_helper_cannot_self_restore_before_full_proof(
        fresh_env):
    store, _pipeline, outputs = fresh_env
    assembler = outputs.materializer.context
    helper = context._RETAINED_CONTEXT_REQUIRE_RUNTIME_COMPOSITION_STRUCTURE
    original_code = helper.__code__
    original_profile = assembler.active_profile
    party_id = f"party:issue171.context-helper.{uuid.uuid4().hex}"

    def self_restoring_helper(_self, _cur=None):
        retained = globals()[
            "_RETAINED_CONTEXT_REQUIRE_RUNTIME_COMPOSITION_STRUCTURE"]
        retained.__code__ = retained.__dict__.pop(
            "_issue171_restore_code")

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": party_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 Context guard test (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            object.__setattr__(
                assembler, "active_profile",
                replace(
                    original_profile,
                    context_snapshot_id_prefix="hostile-context-helper"),
            )
            helper.__dict__["_issue171_restore_code"] = original_code
            helper.__code__ = self_restoring_helper.__code__
            try:
                with pytest.raises(RuntimeBundleError):
                    context.ContextAssembler._assert_runtime_composition(
                        assembler, cur)
            finally:
                helper.__code__ = original_code
                helper.__dict__.pop("_issue171_restore_code", None)
                object.__setattr__(
                    assembler, "active_profile", original_profile)

    assert store.get_record(party_id) is None


@pytest.mark.parametrize("forbidden_sql", (
    "COMMIT AND CHAIN",
    'SELECT "pg_catalog".U&"set\\005fconfig"('
    "'session_replication_role', 'replica', true)",
))
def test_governed_cursor_refuses_caught_commit_and_rolls_back(
        fresh_env, forbidden_sql):
    store, _pipeline, _outputs = fresh_env
    party_id = f"party:issue171.cursor-commit.{uuid.uuid4().hex}"

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": party_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 cursor COMMIT test (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            with pytest.raises(RuntimeError, match="public governed cursor SQL"):
                cur.execute(forbidden_sql)

    assert store.get_record(party_id) is None


@pytest.mark.parametrize("forbidden_sql", ("COMMIT", "COMMIT AND CHAIN"))
def test_governed_cursor_self_restoring_statement_guard_cannot_commit(
        fresh_env, forbidden_sql):
    store, _pipeline, _outputs = fresh_env
    party_id = f"party:issue171.cursor-self-restore.{uuid.uuid4().hex}"
    hostile_guard_called = False

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": party_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 cursor dispatch test (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            cursor_type = type(cur)
            retained_guard = cursor_type._require_statement

            def restore_then_accept(_self, query, *, allow_mutation=False):
                nonlocal hostile_guard_called
                hostile_guard_called = True
                cursor_type._require_statement = retained_guard
                return query

            cursor_type._require_statement = restore_then_accept
            try:
                with pytest.raises(RuntimeError, match="public governed cursor SQL"):
                    cur.execute(forbidden_sql)
                assert hostile_guard_called is False
            finally:
                cursor_type._require_statement = retained_guard

    assert store.get_record(party_id) is None


def test_governed_cursor_transient_mutation_replacement_cannot_skip_write(
        fresh_env):
    store, _pipeline, _outputs = fresh_env
    first_id = f"party:issue171.cursor-transient-first.{uuid.uuid4().hex}"
    skipped_id = f"party:issue171.cursor-transient-skip.{uuid.uuid4().hex}"
    replacement_called = False
    returned_id = None

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": first_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 transient cursor first write (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            cursor_type = type(cur)
            retained_mutation = cursor_type._execute_mutation

            def restore_then_skip(self, *_args, **_kwargs):
                nonlocal replacement_called
                replacement_called = True
                cursor_type._execute_mutation = retained_mutation
                return self

            cursor_type._execute_mutation = restore_then_skip
            try:
                with pytest.raises(
                        RuntimeError, match="exact active governed cursor"):
                    returned_id = store.insert_record(cur, {
                        "schemaVersion": "ofarm.party.v0.1",
                        "partyId": skipped_id,
                        "partyClass": "NATURAL_PERSON",
                        "displayName": (
                            "Issue 171 transient cursor skipped write (fictional)"),
                        "partyState": "ACTIVE",
                        "recordedAt": context.now_iso(),
                    })
            finally:
                cursor_type._execute_mutation = retained_mutation

    assert replacement_called is False
    assert returned_id is None
    assert store.get_record(first_id) is None
    assert store.get_record(skipped_id) is None


def test_reference_resolver_rejects_noop_cursor_and_poisons_transaction(
        fresh_env):
    from kernel.verification import ReferenceResolver

    store, _pipeline, _outputs = fresh_env
    party_id = f"party:issue171.fake-resolver-cursor.{uuid.uuid4().hex}"

    class NoOpCursor:
        calls = 0

        def execute(self, *_args, **_kwargs):
            self.calls += 1
            return self

    fake_cursor = NoOpCursor()
    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": party_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 fake cursor test (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            with pytest.raises(RuntimeError, match="exact active governed cursor"):
                ReferenceResolver(store).verify(
                    fake_cursor,
                    query_value="1234567",
                    snapshot_prefix=context.GERK_SNAPSHOT_PREFIX,
                    lookup=lambda _snapshot, _query: None,
                    profile_ref=config.ACTIVE_PROFILE.profile_ref,
                    authority_ref="party:si.mkgp",
                    jurisdiction_ref="jurisdiction:SI",
                    lookup_runtime_bundle=store.runtime_bundle,
                )
            assert fake_cursor.calls == 0

    assert store.get_record(party_id) is None


def test_authority_evaluator_requires_active_serialized_cursor(fresh_env):
    from kernel.authority import AuthorityEvaluator

    store, _pipeline, _outputs = fresh_env
    evaluator = AuthorityEvaluator(store)
    request = {
        "acting_party_ref": demo.FARMER,
        "action_class": "RECEIVE_READ_DATA",
        "action_stage": "QUERY_READ",
        "scope": {"scopeType": "FARM", "scopeRef": demo.FARM},
    }

    with pytest.raises(RuntimeError, match="exact active governed cursor"):
        evaluator.evaluate(cur=None, **request)
    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.tx() as cur:
            with pytest.raises(RuntimeError, match="active serialized cursor"):
                evaluator.evaluate(cur=cur, **request)
    with store.serialized_tx() as cur:
        decision = evaluator.evaluate(cur=cur, **request)
        assert decision.outcome in {"ALLOW", "DENY"}


def test_authority_evaluator_has_no_instance_dispatch_shadow_seam():
    from kernel.authority import AuthorityEvaluator

    evaluator = object.__new__(AuthorityEvaluator)
    assert not hasattr(evaluator, "__dict__")
    for name in (
        "_party",
        "_role_assignments",
        "_matching_grants",
        "_matching_delegations",
    ):
        with pytest.raises(AttributeError):
            object.__setattr__(evaluator, name, lambda *_args: None)


def test_gate_dispatch_guard_accepts_slot_only_authority_evaluator():
    from kernel import gates as gates_module
    from kernel import stages as stages_module
    from kernel.authority import AuthorityEvaluator
    from kernel.context import ContextAssembler

    guard = gates_module._RETAINED_HAS_INSTANCE_DISPATCH_OVERRIDE
    evaluator = object.__new__(AuthorityEvaluator)
    assert guard(evaluator) is False
    ctx = types.SimpleNamespace(store=None)
    stages_module._require_retained_context_service(
        ctx, stages_module._AUTHORITY_EVALUATE, evaluator)

    class ShadowableService:
        def run(self):
            return None

    service = ShadowableService()
    service.run = lambda: None
    assert guard(service) is True

    context_service = object.__new__(ContextAssembler)
    context_service.assemble = lambda *_args, **_kwargs: None
    with pytest.raises(RuntimeBundleError, match="callable changed"):
        stages_module._require_retained_context_service(
            ctx, stages_module._CONTEXT_ASSEMBLE, context_service)


def test_plain_transaction_cannot_mutate_or_upgrade_to_writer(fresh_env):
    store, _pipeline, _outputs = fresh_env

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.tx() as cur:
            with pytest.raises(RuntimeError, match="active serialized cursor"):
                cur._execute_mutation("SELECT 1")

    with store.tx() as cur:
        with pytest.raises(RuntimeError, match="cannot be upgraded"):
            with store.serialized_tx():
                pass
        cur._execute_read("SELECT 1 AS ok")
        assert cur.fetchone()["ok"] == 1


def test_closed_nested_cursor_cannot_authorize_inside_live_outer_transaction(
        fresh_env):
    from kernel.authority import AuthorityEvaluator

    store, _pipeline, _outputs = fresh_env
    evaluator = AuthorityEvaluator(store)
    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx():
            with store.tx() as escaped:
                escaped._execute_read("SELECT 1 AS ok")
                assert escaped.fetchone()["ok"] == 1
            with pytest.raises(RuntimeError, match="escaped its transaction"):
                evaluator.evaluate(
                    cur=escaped,
                    acting_party_ref=demo.FARMER,
                    action_class="RECEIVE_READ_DATA",
                    action_stage="QUERY_READ",
                    scope={"scopeType": "FARM", "scopeRef": demo.FARM},
                )


def test_authority_decision_is_immutable_and_detects_payload_mutation():
    from kernel.authority import (
        AuthorityDecision,
        authority_decision_allowed,
    )

    problems = []
    request = {"requestId": "authzreq:test"}
    result = {
        "decisionOutcome": "DENY",
        "finalActionPermitted": False,
        "humanApprovalRequired": False,
        "problems": problems,
    }
    trace = {"decisionOutcome": "DENY"}
    decision = AuthorityDecision("DENY", request, result, trace, problems)
    assert authority_decision_allowed(decision) is False
    with pytest.raises(AttributeError):
        decision.outcome = "ALLOW"
    with pytest.raises(TypeError, match="runtime type is immutable"):
        AuthorityDecision.allowed = property(lambda _self: True)
    result["finalActionPermitted"] = True
    with pytest.raises(RuntimeError, match="state changed"):
        authority_decision_allowed(decision)


@pytest.mark.parametrize(("field", "value", "error"), [
    ("action_stage", "UNREVIEWED_FINALIZATION", ValueError),
    ("revocation_disposition", "ALLOW", ValueError),
    ("scope", {"scopeType": "FARM", "scopeRef": demo.FARM, "extra": True},
     TypeError),
])
def test_authority_evaluator_rejects_unclosed_inputs(
        fresh_env, field, value, error):
    from kernel.authority import AuthorityEvaluator

    store, _pipeline, _outputs = fresh_env
    evaluator = AuthorityEvaluator(store)
    request = {
        "acting_party_ref": demo.FARMER,
        "action_class": "RECEIVE_READ_DATA",
        "action_stage": "QUERY_READ",
        "scope": {"scopeType": "FARM", "scopeRef": demo.FARM},
        "revocation_disposition": "DENY",
    }
    request[field] = value
    with store.serialized_tx() as cur:
        with pytest.raises(error):
            evaluator.evaluate(cur=cur, **request)


def test_reference_resolver_rejects_cursor_from_another_store(fresh_env):
    from kernel.verification import ReferenceResolver

    store, _pipeline, _outputs = fresh_env
    other_store = Store(dsn=store.dsn)
    party_id = f"party:issue171.foreign-resolver-cursor.{uuid.uuid4().hex}"
    try:
        context.bootstrap_for_descriptor(other_store, config.ACTIVE_PROFILE)
        with pytest.raises(RuntimeBundleError, match="rollback-only"):
            with store.serialized_tx() as cur:
                store.insert_record(cur, {
                    "schemaVersion": "ofarm.party.v0.1",
                    "partyId": party_id,
                    "partyClass": "NATURAL_PERSON",
                    "displayName": "Issue 171 foreign cursor test (fictional)",
                    "partyState": "ACTIVE",
                    "recordedAt": context.now_iso(),
                })
                with other_store.tx() as foreign_cur:
                    with pytest.raises(
                            RuntimeError, match="this Store's exact active"):
                        ReferenceResolver(store).verify(
                            foreign_cur,
                            query_value="1234567",
                            snapshot_prefix=context.GERK_SNAPSHOT_PREFIX,
                            lookup=lambda _snapshot, _query: None,
                            profile_ref=config.ACTIVE_PROFILE.profile_ref,
                            authority_ref="party:si.mkgp",
                            jurisdiction_ref="jurisdiction:SI",
                            lookup_runtime_bundle=store.runtime_bundle,
                        )
    finally:
        other_store.close()

    assert store.get_record(party_id) is None


def test_governed_transaction_hides_direct_connection_commit(fresh_env):
    store, _pipeline, _outputs = fresh_env
    party_id = f"party:issue171.connection-commit.{uuid.uuid4().hex}"
    retained_connection = store.conn

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": party_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 connection COMMIT test (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            store._transaction_state.depth = 0
            with pytest.raises(RuntimeError, match="public Store connection SQL"):
                retained_connection.execute("COMMIT")

    assert store.get_record(party_id) is None


def test_governed_cursor_does_not_leak_raw_command_channels(fresh_env):
    store, _pipeline, _outputs = fresh_env

    with store.tx() as cur:
        assert iter(cur) is cur
        cur._execute_read("SELECT 1 AS value")
        assert next(cur)["value"] == 1
        with pytest.raises(AttributeError):
            _ = cur.connection.info.pgconn
        with pytest.raises(AttributeError):
            _ = cur.connection.pgconn


def test_public_store_sql_facades_are_disabled(fresh_env):
    store, _pipeline, _outputs = fresh_env
    direct_id = f"party:issue171.direct-sql.{uuid.uuid4().hex}"
    statement = (
        "INSERT INTO kernel_record "
        "(record_id, record_kind, lane, schema_hash, payload, payload_sha256, "
        "tenant_ref, runtime_bundle_digest) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    )
    params = (
        direct_id, "ofarm.party.v0.1", "canonical", "sha256:" + "0" * 64,
        Jsonb({}), "sha256:" + "0" * 64, config.TENANT_REF,
        store.runtime_bundle_digest,
    )

    with pytest.raises(RuntimeError, match="public Store connection SQL"):
        store.conn.execute(statement, params)
    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.tx() as cur:
            with pytest.raises(RuntimeError, match="public governed cursor SQL"):
                cur.execute(statement, params)
    assert store.get_record(direct_id) is None


def test_governed_cursor_rejects_stateful_composable_without_rendering(fresh_env):
    store, _pipeline, _outputs = fresh_env

    class FlippingComposable(sql.Composable):
        def __init__(self):
            super().__init__(None)
            self.render_count = 0

        def as_bytes(self, _context=None):
            self.render_count += 1
            return b"SELECT 1 AS value" if self.render_count == 1 else b"COMMIT"

    statement = FlippingComposable()
    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.tx() as cur:
            with pytest.raises(TypeError, match="exact immutable"):
                cur._execute_read(statement)
    assert statement.render_count == 0


def test_governed_savepoint_cannot_escape_parent_transaction(fresh_env):
    store, _pipeline, _outputs = fresh_env

    with store.tx() as cur:
        escaped = cur.connection.transaction()
    with pytest.raises(RuntimeError, match="ownership"):
        with escaped:
            pass


def test_governed_cursor_cannot_escape_parent_transaction(fresh_env):
    store, _pipeline, _outputs = fresh_env

    with store.tx() as escaped:
        escaped._execute_read("SELECT 1 AS value")
        assert escaped.fetchone()["value"] == 1
    with pytest.raises(RuntimeError, match="ownership"):
        escaped._execute_read("SELECT 2 AS value")


def test_governed_savepoint_preserves_database_error_and_recovers(fresh_env):
    store, _pipeline, _outputs = fresh_env

    with store.tx() as cur:
        with pytest.raises(psycopg.errors.DivisionByZero):
            with cur.connection.transaction():
                cur._execute_read("SELECT 1 / 0")
        cur._execute_read("SELECT 1 AS value")
        assert cur.fetchone()["value"] == 1


def test_public_maintenance_cursor_is_not_exposed(fresh_env):
    store, _pipeline, _outputs = fresh_env
    with pytest.raises(RuntimeError, match="public Store cursors are forbidden"):
        store.conn.cursor()
    with pytest.raises(RuntimeError, match="public Store connection SQL"):
        store.conn.execute("SELECT pg_catalog.pg_notify('issue171', 'x')")


def test_runtime_bundle_outer_transaction_rechecks_live_python_posture(
        fresh_env):
    store, _pipeline, _outputs = fresh_env
    original_codes = store._runtime_posture_verifier_codes
    try:
        with pytest.raises(RuntimeError, match="posture verifier changed"):
            with store.tx() as cur:
                cur._execute_read("SELECT 1 AS ok")
                assert cur.fetchone()["ok"] == 1
                object.__setattr__(
                    store, "_runtime_posture_verifier_codes",
                    (object(), *original_codes[1:]))
    finally:
        object.__setattr__(
            store, "_runtime_posture_verifier_codes", original_codes)


def test_runtime_bundle_refuses_paired_posture_verifier_replacement(fresh_env):
    store, _pipeline, _outputs = fresh_env
    original_verifiers = store._runtime_posture_verifiers
    original_codes = store._runtime_posture_verifier_codes

    def no_op_verifier(*_args, **_kwargs):
        return None

    replacements = (no_op_verifier,) * len(original_verifiers)
    try:
        object.__setattr__(store, "_runtime_posture_verifiers", replacements)
        object.__setattr__(
            store, "_runtime_posture_verifier_codes",
            tuple(item.__code__ for item in replacements),
        )
        with pytest.raises(RuntimeError, match="posture verifier changed"):
            store.get_record(demo.FARMER)
    finally:
        object.__setattr__(
            store, "_runtime_posture_verifiers", original_verifiers)
        object.__setattr__(
            store, "_runtime_posture_verifier_codes", original_codes)


def test_store_refuses_class_level_guard_replacement(fresh_env):
    store, _pipeline, _outputs = fresh_env
    original = Store._require_transaction_python_posture
    Store._require_transaction_python_posture = lambda _self: None
    try:
        with pytest.raises(RuntimeError, match="runtime dispatch changed"):
            store.get_record(demo.FARMER)
    finally:
        Store._require_transaction_python_posture = original


def test_caught_store_dispatch_drift_poison_rolls_back_transaction(fresh_env):
    store, _pipeline, _outputs = fresh_env
    party_id = f"party:issue171.dispatch-poison.{uuid.uuid4().hex}"
    original = Store._bundle_digest

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with store.serialized_tx() as cur:
            store.insert_record(cur, {
                "schemaVersion": "ofarm.party.v0.1",
                "partyId": party_id,
                "partyClass": "NATURAL_PERSON",
                "displayName": "Issue 171 dispatch poison test (fictional)",
                "partyState": "ACTIVE",
                "recordedAt": context.now_iso(),
            })
            Store._bundle_digest = lambda _self, _explicit=None: "hostile"
            try:
                with pytest.raises(RuntimeError, match="runtime dispatch changed"):
                    Store._require_runtime_dispatch_integrity(store)
            finally:
                Store._bundle_digest = original

    assert store.get_record(party_id) is None


def test_store_refuses_registry_instance_validate_shadow(fresh_env):
    store, _pipeline, _outputs = fresh_env
    store._registry.validate = lambda _payload: None
    try:
        with pytest.raises(RuntimeError, match="decision semantics"):
            store.get_record(demo.FARMER)
    finally:
        del store._registry.validate


def test_store_read_cursor_instance_shadow_cannot_skip_guards(fresh_env):
    store, _pipeline, _outputs = fresh_env

    @contextmanager
    def unguarded_cursor():
        yield Store._raw_connection(store).cursor()

    object.__setattr__(store, "_read_cursor", unguarded_cursor)
    try:
        with pytest.raises(RuntimeError, match="runtime dispatch changed"):
            store.get_record(demo.FARMER)
    finally:
        object.__delattr__(store, "_read_cursor")


def test_runtime_bundle_late_python_drift_rolls_back_current_transaction(
        fresh_env):
    store, _pipeline, _outputs = fresh_env
    party_id = f"party:issue171.late-import.{uuid.uuid4().hex}"
    module_name = f"_ofarm_late_transaction_{uuid.uuid4().hex}"
    module = types.ModuleType(module_name)
    try:
        with pytest.raises(RuntimeBundleError, match="module set changed"):
            with store.serialized_tx() as cur:
                store.insert_record(cur, {
                    "schemaVersion": "ofarm.party.v0.1",
                    "partyId": party_id,
                    "partyClass": "NATURAL_PERSON",
                    "displayName": "Issue 171 late import rollback test (fictional)",
                    "partyState": "ACTIVE",
                    "recordedAt": context.now_iso(),
                })
                sys.modules[module_name] = module
    finally:
        sys.modules.pop(module_name, None)
    assert store.get_record(party_id) is None


def test_runtime_bundle_refuses_mutable_decision_semantic_roots(fresh_env):
    from kernel import gates as gates_module
    from kernel import policy
    from kernel import runtime_bundle as runtime_bundle_module

    store, _pipeline, _outputs = fresh_env

    original_policy = policy.COMMIT_CLASS_TO_FAMILY
    policy.COMMIT_CLASS_TO_FAMILY = dict(original_policy)
    try:
        with pytest.raises(RuntimeBundleError, match="decision semantic root"):
            store.get_record(demo.FARMER)
    finally:
        policy.COMMIT_CLASS_TO_FAMILY = original_policy

    original_validate = ContractRegistry.validate
    replacement = types.FunctionType(
        original_validate.__code__, original_validate.__globals__,
        original_validate.__name__, original_validate.__defaults__,
        original_validate.__closure__,
    )
    ContractRegistry.validate = replacement
    try:
        with pytest.raises(RuntimeBundleError, match="decision semantic state"):
            store.get_record(demo.FARMER)
    finally:
        ContractRegistry.validate = original_validate

    def hostile_validate(self, payload):
        del self, payload
        raise AssertionError("hostile ContractRegistry.validate executed")

    original_code = original_validate.__code__
    original_validate.__code__ = hostile_validate.__code__
    try:
        with pytest.raises(RuntimeBundleError, match="decision semantic state"):
            store.get_record(demo.FARMER)
    finally:
        original_validate.__code__ = original_code

    authority_class = type(_pipeline.authority)
    original_evaluate = authority_class.evaluate
    authority_class.evaluate = lambda self, **_kwargs: None
    try:
        with pytest.raises(RuntimeBundleError, match="decision semantic state"):
            store.get_record(demo.FARMER)
    finally:
        authority_class.evaluate = original_evaluate

    original_chain = gates_module.CHAIN
    stage_class = type(original_chain[0])
    original_run = stage_class.run
    stage_class.run = lambda self, ctx: None
    try:
        with pytest.raises(RuntimeBundleError, match="decision semantic state"):
            store.get_record(demo.FARMER)
    finally:
        stage_class.run = original_run

    gates_module.CHAIN = tuple(reversed(original_chain))
    try:
        with pytest.raises(RuntimeBundleError, match="decision semantic root"):
            store.get_record(demo.FARMER)
    finally:
        gates_module.CHAIN = original_chain

    original_ingress = gates_module.IngressNormalizer
    gates_module.IngressNormalizer = object
    try:
        with pytest.raises(RuntimeBundleError, match="decision semantic root"):
            store.get_record(demo.FARMER)
    finally:
        gates_module.IngressNormalizer = original_ingress

    original_checker = runtime_bundle_module.require_store_runtime_bundle
    runtime_bundle_module.require_store_runtime_bundle = lambda *_args: None
    try:
        with pytest.raises(RuntimeError, match="posture verifier changed"):
            store.get_record(demo.FARMER)
    finally:
        runtime_bundle_module.require_store_runtime_bundle = original_checker

    original_semantic_checker = runtime_bundle_module._require_decision_semantics
    runtime_bundle_module._require_decision_semantics = lambda *_args: None
    try:
        with pytest.raises(RuntimeError, match="posture verifier changed"):
            store.get_record(demo.FARMER)
    finally:
        runtime_bundle_module._require_decision_semantics = \
            original_semantic_checker

    assert store.get_record(demo.FARMER) is not None


def test_gate_pipeline_refuses_instance_level_dispatch_override(fresh_env):
    _store, pipeline, _outputs = fresh_env
    with pytest.raises(AttributeError, match="runtime composition is immutable"):
        pipeline.authority.evaluate = lambda **_kwargs: None

    with pytest.raises(AttributeError, match="runtime dispatch is immutable"):
        pipeline._commit_in_tx = lambda _cur, _submission: {}  # type: ignore[method-assign]

    object.__setattr__(
        pipeline, "_commit_in_tx", lambda _cur, _submission: {})
    try:
        with pytest.raises(RuntimeBundleError, match="runtime composition changed"):
            pipeline._assert_runtime_composition()
    finally:
        object.__delattr__(pipeline, "_commit_in_tx")

    object.__setattr__(pipeline, "_assert_runtime_composition", lambda: None)
    object.__setattr__(pipeline.authority, "evaluate", lambda **_kwargs: None)
    try:
        with pytest.raises(RuntimeBundleError, match="runtime composition changed"):
            pipeline.commit({})
    finally:
        object.__delattr__(pipeline.authority, "evaluate")
        object.__delattr__(pipeline, "_assert_runtime_composition")

    original_cache = pipeline.products._by_snapshot
    object.__setattr__(pipeline.products, "_by_snapshot", {})
    try:
        with pytest.raises(RuntimeBundleError, match="runtime composition changed"):
            GatePipeline._assert_runtime_composition(pipeline)
    finally:
        object.__setattr__(pipeline.products, "_by_snapshot", original_cache)


def test_gate_entry_refuses_temporary_semantic_mutation_even_if_restored(
        fresh_env, monkeypatch):
    from kernel import policy

    store, pipeline, _outputs = fresh_env
    submission = demo.spray_submission(
        f"issue171-temporary-semantics:{uuid.uuid4().hex}",
        erp_id=f"erp:issue171.temporary-semantics.{uuid.uuid4().hex}",
        confirm=True,
    )
    with pytest.raises(RuntimeBundleError, match="decision semantic root"):
        with store.serialized_tx() as cur:
            with monkeypatch.context() as patch:
                patch.setattr(
                    policy, "COMMIT_CLASS_TO_FAMILY",
                    dict(policy.COMMIT_CLASS_TO_FAMILY),
                )
                GatePipeline._commit_in_tx(pipeline, cur, submission)


def test_gate_uses_retained_stage_callable_during_temporary_class_mutation(
        fresh_env):
    from kernel import gates as gates_module

    store, pipeline, _outputs = fresh_env
    submission = demo.spray_submission(
        f"issue171-retained-stage:{uuid.uuid4().hex}",
        erp_id=f"erp:issue171.retained-stage.{uuid.uuid4().hex}",
        confirm=True,
    )
    hostile_called = False

    def hostile_run(_self, _ctx):
        nonlocal hostile_called
        hostile_called = True
        raise AssertionError("temporary hostile stage dispatch executed")

    class RollbackProbe(Exception):
        pass

    with pytest.raises(RollbackProbe):
        with Store.serialized_tx(store) as cur:
            ctx = GatePipeline._new_context(pipeline, cur, submission)
            ingress_run = gates_module._GATE_ENTRY_CALLABLES[0][2]
            ingress_run(gates_module.IngressNormalizer(), ctx)
            stage, stage_type, retained_run, retained_code = \
                pipeline._stage_dispatch[0]
            assert retained_run.__code__ is retained_code
            original = stage_type.run
            stage_type.run = hostile_run
            try:
                retained_run(stage, ctx)
            finally:
                stage_type.run = original
            assert hostile_called is False
            raise RollbackProbe


def test_runtime_bundle_late_semantic_mutation_rolls_back_current_transaction(
        fresh_env):
    from kernel import policy

    store, _pipeline, _outputs = fresh_env
    party_id = f"party:issue171.late-semantics.{uuid.uuid4().hex}"
    marker = "ISSUE171_HOSTILE_COMMIT_CLASS"
    try:
        with pytest.raises(RuntimeBundleError, match="decision semantic state"):
            with store.serialized_tx() as cur:
                store.insert_record(cur, {
                    "schemaVersion": "ofarm.party.v0.1",
                    "partyId": party_id,
                    "partyClass": "NATURAL_PERSON",
                    "displayName": "Issue 171 late semantic drift (fictional)",
                    "partyState": "ACTIVE",
                    "recordedAt": context.now_iso(),
                })
                policy.COMMIT_CLASS_TO_FAMILY[marker] = "HOSTILE_EVENT"
    finally:
        policy.COMMIT_CLASS_TO_FAMILY.pop(marker, None)
    assert store.get_record(party_id) is None


def test_preselection_semantic_mutation_changes_runtime_bundle_digest():
    from kernel import policy

    clean = build_runtime_bundle(config.ACTIVE_PROFILE)
    marker = "ISSUE171_PRESELECTION_SEMANTIC_MUTATION"
    try:
        policy.COMMIT_CLASS_TO_FAMILY[marker] = "HOSTILE_EVENT"
        changed = build_runtime_bundle(config.ACTIVE_PROFILE)
    finally:
        policy.COMMIT_CLASS_TO_FAMILY.pop(marker, None)

    clean_semantics = clean.component(
        "RUNTIME_ENVIRONMENT_OBSERVED",
        "environment:stable-decision-semantics.v1")
    changed_semantics = changed.component(
        "RUNTIME_ENVIRONMENT_OBSERVED",
        "environment:stable-decision-semantics.v1")
    assert changed_semantics.content_digest != clean_semantics.content_digest
    assert changed.digest != clean.digest


def test_preselection_method_mutation_changes_semantic_receipt():
    clean = observed_decision_semantics_component(config.PACKAGE_ROOT)
    original = ContractRegistry.validate.__code__

    def hostile_validate(self, payload):
        del self, payload
        return None

    try:
        ContractRegistry.validate.__code__ = hostile_validate.__code__
        changed = observed_decision_semantics_component(config.PACKAGE_ROOT)
    finally:
        ContractRegistry.validate.__code__ = original

    assert changed.content_digest != clean.content_digest


def test_decision_semantic_seal_is_self_consistent_without_mutation():
    selected = _capture_decision_semantics()
    control_pattern = next(
        entry for entry in selected
        if entry[1] == "kernel.runtime_bundle._C0_CONTROL_RE"
    )

    assert control_pattern[5] is _C0_CONTROL_RE
    assert control_pattern[6][0] == "DATA"
    assert control_pattern[6][1][0] == "REGEX"
    _require_decision_semantics(selected)


def test_semantic_traversal_shares_aliases_without_changing_stable_receipt():
    from kernel import runtime_bundle as runtime_bundle_module

    shared_value = {"semantic": ["alias"]}
    aliased = (shared_value, shared_value)
    shared_state = _freeze_semantic_value(aliased)
    unshared_state = (
        "SEQUENCE", tuple, aliased,
        tuple(_freeze_semantic_value(shared_value) for _index in range(2)),
    )

    assert shared_state[3][0] is shared_state[3][1]
    assert unshared_state[3][0] is not unshared_state[3][1]

    module = types.ModuleType("_ofarm_semantic_traversal_test")
    shared_selected = ((
        "DATA", "test.semantic_alias", module, module.__name__, "alias",
        aliased, shared_state,
    ),)
    unshared_selected = ((
        "DATA", "test.semantic_alias", module, module.__name__, "alias",
        aliased, unshared_state,
    ),)
    shared_document = _stable_decision_semantics_document(
        shared_selected, config.PACKAGE_ROOT)
    unshared_document = _stable_decision_semantics_document(
        unshared_selected, config.PACKAGE_ROOT)

    assert shared_document == unshared_document
    assert (
        _canonical_stable_semantic_bytes(shared_document)
        == _canonical_stable_semantic_bytes(unshared_document)
    )

    def projection_probe(value=None):
        return value

    class ProjectionProbe:
        def decide(self, value=None):
            return value

    traversal = _new_semantic_traversal()
    function_state = runtime_bundle_module._semantic_function_state(
        projection_probe, traversal)
    class_state = runtime_bundle_module._semantic_class_state(
        ProjectionProbe, traversal)
    projection = ({}, {})
    projected_function = runtime_bundle_module._stable_semantic_function_state(
        function_state, config.PACKAGE_ROOT, projection)
    projected_class = runtime_bundle_module._stable_semantic_class_state(
        class_state, config.PACKAGE_ROOT, projection)
    assert runtime_bundle_module._stable_semantic_function_state(
        function_state, config.PACKAGE_ROOT, projection) is projected_function
    assert runtime_bundle_module._stable_semantic_class_state(
        class_state, config.PACKAGE_ROOT, projection) is projected_class

    fresh_projection = ({}, {})
    fresh_function = runtime_bundle_module._stable_semantic_function_state(
        function_state, config.PACKAGE_ROOT, fresh_projection)
    fresh_class = runtime_bundle_module._stable_semantic_class_state(
        class_state, config.PACKAGE_ROOT, fresh_projection)
    assert fresh_function is not projected_function
    assert fresh_class is not projected_class
    assert _canonical_stable_semantic_bytes(fresh_function) == \
        _canonical_stable_semantic_bytes(projected_function)
    assert _canonical_stable_semantic_bytes(fresh_class) == \
        _canonical_stable_semantic_bytes(projected_class)


def test_semantic_comparison_memo_keeps_container_identity_mode_distinct():
    current_state = _freeze_semantic_value([])
    prior_state = _freeze_semantic_value([])
    traversal = _new_semantic_traversal()

    assert _same_semantic_value(
        current_state, prior_state,
        require_container_identity=False,
        traversal=traversal,
    )
    assert not _same_semantic_value(
        current_state, prior_state,
        require_container_identity=True,
        traversal=traversal,
    )


def test_semantic_traversal_does_not_publish_partial_cycle_state():
    cyclic = []
    cyclic.append(cyclic)

    with pytest.raises(RuntimeBundleError, match="sequence cycle"):
        _freeze_semantic_value(cyclic)


def test_semantic_traversal_factory_is_an_implementation_anchor():
    from kernel import runtime_bundle as runtime_bundle_module

    def forged_helper(*_args, **_kwargs):
        return {}

    for helper in (
        runtime_bundle_module._new_semantic_traversal,
        runtime_bundle_module._stable_code_constant,
        runtime_bundle_module._stable_semantic_sequence_state,
    ):
        original = helper.__code__
        try:
            helper.__code__ = forged_helper.__code__
            with pytest.raises(RuntimeBundleError, match="implementation changed"):
                observed_decision_semantics_component(config.PACKAGE_ROOT)
        finally:
            helper.__code__ = original


def test_semantic_proof_rechecks_mutation_after_restore():
    from kernel import policy

    selected = _capture_decision_semantics()
    marker = "ISSUE171_REPEATED_SEMANTIC_MUTATION"
    _require_decision_semantics(selected)
    for _index in range(2):
        policy.COMMIT_CLASS_TO_FAMILY[marker] = "HOSTILE_EVENT"
        try:
            with pytest.raises(RuntimeBundleError, match="decision semantic state"):
                _require_decision_semantics(selected)
        finally:
            policy.COMMIT_CLASS_TO_FAMILY.pop(marker)
        _require_decision_semantics(selected)


def test_decision_semantic_seal_retains_exact_import_table_key():
    selected = _capture_decision_semantics()
    entry = next(item for item in selected if item[3] == "_collections_abc")
    module = entry[2]
    alias = f"_ofarm_semantic_alias_{uuid.uuid4().hex}"
    prior_alias = sys.modules.get(alias)
    assert sys.modules.pop("_collections_abc") is module
    sys.modules[alias] = module
    try:
        with pytest.raises(RuntimeBundleError, match="module changed"):
            _require_decision_semantics(selected)
    finally:
        sys.modules["_collections_abc"] = module
        if prior_alias is None:
            sys.modules.pop(alias, None)
        else:
            sys.modules[alias] = prior_alias


def test_runtime_module_lifetime_signature_seals_module_spec_name():
    import posixpath
    from kernel import runtime_bundle as runtime_bundle_module

    original = posixpath.__spec__.name
    selected = runtime_bundle_module._module_origin_stat_signature(posixpath)
    try:
        posixpath.__spec__.name = "os.path"
        assert runtime_bundle_module._module_origin_stat_signature(
            posixpath) != selected
    finally:
        posixpath.__spec__.name = original


def test_nested_jsonschema_helper_mutation_changes_semantic_receipt():
    from jsonschema import _keywords

    clean = observed_decision_semantics_component(config.PACKAGE_ROOT)
    original = _keywords.ensure_list
    try:
        _keywords.ensure_list = lambda _value: ["integer"]
        changed = observed_decision_semantics_component(config.PACKAGE_ROOT)
    finally:
        _keywords.ensure_list = original

    assert changed.content_digest != clean.content_digest


def test_si_binding_resolver_mutation_is_in_semantic_closure():
    from kernel.profiles.si_ffs import si_bindings

    selected = _capture_decision_semantics()
    original = si_bindings.resolve_equipment.__code__

    def hostile(*_args, **_kwargs):
        return {"bindingState": "CONFIRMED"}

    try:
        si_bindings.resolve_equipment.__code__ = hostile.__code__
        with pytest.raises(RuntimeBundleError, match="decision semantic state"):
            _require_decision_semantics(selected)
    finally:
        si_bindings.resolve_equipment.__code__ = original


def test_copy_dispatch_mutation_changes_semantic_receipt():
    clean = observed_decision_semantics_component(config.PACKAGE_ROOT)
    original = copy._deepcopy_dispatch[dict]
    try:
        copy._deepcopy_dispatch[dict] = lambda _value, _memo: {}
        changed = observed_decision_semantics_component(config.PACKAGE_ROOT)
    finally:
        copy._deepcopy_dispatch[dict] = original

    assert changed.content_digest != clean.content_digest


def test_calendar_validation_table_mutation_changes_semantic_receipt():
    import calendar

    clean = observed_decision_semantics_component(config.PACKAGE_ROOT)
    original = calendar.mdays[4]
    try:
        calendar.mdays[4] = 31
        changed = observed_decision_semantics_component(config.PACKAGE_ROOT)
    finally:
        calendar.mdays[4] = original

    assert changed.content_digest != clean.content_digest


def test_builtin_callable_rebinding_changes_semantic_receipt():
    import bisect

    clean = observed_decision_semantics_component(config.PACKAGE_ROOT)
    original = bisect.bisect_right
    try:
        bisect.bisect_right = bisect.bisect_left
        changed = observed_decision_semantics_component(config.PACKAGE_ROOT)
    finally:
        bisect.bisect_right = original

    assert changed.content_digest != clean.content_digest


def test_regex_compiler_rebinding_changes_semantic_receipt():
    clean = observed_decision_semantics_component(config.PACKAGE_ROOT)
    original = re._compile
    try:
        re._compile = lambda _pattern, _flags=0: None
        changed = observed_decision_semantics_component(config.PACKAGE_ROOT)
    finally:
        re._compile = original

    assert changed.content_digest != clean.content_digest


def test_regex_cache_growth_does_not_change_semantic_receipt():
    clean = observed_decision_semantics_component(config.PACKAGE_ROOT)
    re.compile(f"issue171-derived-cache-{uuid.uuid4().hex}")
    after_cache_growth = observed_decision_semantics_component(
        config.PACKAGE_ROOT)
    assert after_cache_growth == clean


def test_concurrent_regex_cache_growth_does_not_poison_semantic_proof():
    from kernel import runtime_bundle as runtime_bundle_module

    selected = _capture_decision_semantics()
    release = threading.Event()
    populated = threading.Event()
    pattern = f"issue171-concurrent-derived-cache-{uuid.uuid4().hex}"

    def populate_cache():
        release.wait(timeout=10)
        re.compile(pattern)
        populated.set()

    worker = threading.Thread(target=populate_cache)
    prepare_code = runtime_bundle_module._prepare_decision_semantic_caches.__code__

    def release_after_cache_validation(frame, event, _arg):
        if event == "return" and frame.f_code is prepare_code:
            release.set()
            if not populated.wait(timeout=10):
                raise AssertionError("concurrent regex cache growth did not run")
        return release_after_cache_validation

    worker.start()
    sys.settrace(release_after_cache_validation)
    try:
        _require_decision_semantics(selected)
    finally:
        sys.settrace(None)
        release.set()
        worker.join(timeout=10)
        re.purge()

    assert populated.is_set()
    assert not worker.is_alive()


def test_regex_cache_mapping_replacement_remains_fail_closed():
    selected = _capture_decision_semantics()
    original = re._cache
    try:
        re._cache = {}
        with pytest.raises(
                RuntimeBundleError,
                match=r"decision semantic root changed after activation: re\._cache"):
            _require_decision_semantics(selected)
    finally:
        re._cache = original
        re.purge()


def test_nested_regex_compiler_mutation_is_in_semantic_closure():
    selected = _capture_decision_semantics()
    original = re._compiler.compile
    try:
        re._compiler.compile = lambda _pattern, _flags=0: None
        with pytest.raises(RuntimeBundleError, match="decision semantic root"):
            _require_decision_semantics(selected)
    finally:
        re._compiler.compile = original


def test_json_default_decoder_mutation_is_in_semantic_closure():
    selected = _capture_decision_semantics()
    original = json._default_decoder
    try:
        json._default_decoder = json.JSONDecoder(parse_int=lambda _value: 0)
        with pytest.raises(RuntimeBundleError, match="decision semantic root"):
            _require_decision_semantics(selected)
    finally:
        json._default_decoder = original


def test_external_python_class_mutation_changes_semantic_receipt():
    clean = observed_decision_semantics_component(config.PACKAGE_ROOT)
    original = Path.read_text
    try:
        Path.read_text = lambda _self, **_kwargs: "{}"
        changed = observed_decision_semantics_component(config.PACKAGE_ROOT)
    finally:
        Path.read_text = original
    assert changed.content_digest != clean.content_digest


def test_retained_psycopg_adapter_class_mutation_is_in_semantic_closure():
    from psycopg.types import json as psycopg_json

    selected = _capture_decision_semantics()
    original_code = psycopg_json._JsonDumper.dump.__code__

    def hostile_dump(_self, _obj):
        return b'{}'

    try:
        psycopg_json._JsonDumper.dump.__code__ = hostile_dump.__code__
        with pytest.raises(RuntimeBundleError, match="decision semantic state"):
            _require_decision_semantics(selected)
    finally:
        psycopg_json._JsonDumper.dump.__code__ = original_code


def test_retained_psycopg_adapters_survive_lazy_connection_resolution():
    from kernel.store import (
        _RETAINED_PSYCOPG_ADAPTERS,
        _detached_psycopg_adapter_context,
    )

    public_auto = vars(psycopg.adapters)["_dumpers"][PyFormat.AUTO]
    retained_auto = vars(
        _RETAINED_PSYCOPG_ADAPTERS)["_dumpers"][PyFormat.AUTO]
    assert retained_auto is not public_auto
    assert "datetime.datetime" in retained_auto
    assert datetime not in retained_auto

    selected = _capture_decision_semantics()
    connection_context = _detached_psycopg_adapter_context(
        _RETAINED_PSYCOPG_ADAPTERS)
    connection_adapters = AdaptersMap(connection_context)
    cursor_adapters = AdaptersMap(connection_adapters)
    transient_auto = vars(cursor_adapters)["_dumpers"][PyFormat.AUTO]

    assert transient_auto is not retained_auto
    dumper = cursor_adapters.get_dumper(datetime, PyFormat.AUTO)
    assert dumper is transient_auto[datetime]
    assert "datetime.datetime" not in transient_auto
    assert "datetime.datetime" in retained_auto
    assert datetime not in retained_auto
    _require_decision_semantics(selected)


def test_unbound_dynamic_psycopg_adapter_class_is_in_semantic_closure():
    from kernel.store import _RETAINED_PSYCOPG_ADAPTERS

    dumpers_by_oid = vars(_RETAINED_PSYCOPG_ADAPTERS)["_dumpers_by_oid"]
    adapter_class = next(
        class_object
        for dumpers in dumpers_by_oid
        for class_object in dumpers.values()
        if (isinstance(class_object, type)
            and class_object.__name__ == "JsonbListDumper")
    )
    owner = sys.modules[adapter_class.__module__]
    assert vars(owner).get(adapter_class.__name__) is not adapter_class

    selected = _capture_decision_semantics()
    marker = object()
    original = vars(adapter_class).get("dump", marker)
    adapter_class.dump = lambda _self, _obj: b'{}'
    try:
        with pytest.raises(RuntimeBundleError, match="decision semantic state"):
            _require_decision_semantics(selected)
    finally:
        if original is marker:
            del adapter_class.dump
        else:
            adapter_class.dump = original


@pytest.mark.parametrize(("class_object", "method_name"), [
    (OutputGenerator, "passport_view"),
    (ImportRunner, "run_import"),
    (GerkLayer, "lookup"),
    (FFSNapraveRegister, "match"),
])
def test_all_governed_service_entries_are_in_semantic_closure(
        class_object, method_name):
    selected = _capture_decision_semantics()
    original = getattr(class_object, method_name)
    setattr(class_object, method_name, lambda *_args, **_kwargs: None)
    try:
        with pytest.raises(RuntimeBundleError, match="decision semantic state"):
            _require_decision_semantics(selected)
    finally:
        setattr(class_object, method_name, original)


def test_inherited_jsonschema_error_behavior_changes_semantic_receipt():
    from collections import deque
    from jsonschema import exceptions

    clean = observed_decision_semantics_component(config.PACKAGE_ROOT)
    original = exceptions._Error.absolute_path
    try:
        exceptions._Error.absolute_path = property(
            lambda _self: deque(["hostile"]))
        changed = observed_decision_semantics_component(config.PACKAGE_ROOT)
    finally:
        exceptions._Error.absolute_path = original

    assert changed.content_digest != clean.content_digest


def test_reached_kernel_object_class_behavior_changes_semantic_receipt():
    from kernel import policy

    absent_class = type(policy.ABSENT)
    clean = observed_decision_semantics_component(config.PACKAGE_ROOT)
    had_equality = "__eq__" in vars(absent_class)
    original = vars(absent_class).get("__eq__")
    try:
        absent_class.__eq__ = lambda _self, _other: True
        changed = observed_decision_semantics_component(config.PACKAGE_ROOT)
    finally:
        if had_equality:
            absent_class.__eq__ = original
        else:
            del absent_class.__eq__

    assert changed.content_digest != clean.content_digest


def test_semantic_receipt_normalizes_relocated_kernel_module_file():
    from kernel import runtime_bundle as runtime_bundle_module

    clean = observed_decision_semantics_component(config.PACKAGE_ROOT)
    original = runtime_bundle_module.__file__
    try:
        runtime_bundle_module.__file__ = \
            "/relocated/checkout/kernel/runtime_bundle.py"
        relocated = observed_decision_semantics_component(config.PACKAGE_ROOT)
    finally:
        runtime_bundle_module.__file__ = original

    assert relocated == clean


def test_semantic_receipt_refuses_projector_code_replacement():
    from kernel import runtime_bundle as runtime_bundle_module

    helper = runtime_bundle_module._canonical_stable_semantic_bytes

    def strict_reference(value):
        return canonical_json(value).encode("utf-8")

    def outcome(serializer, value):
        try:
            return "RETURN", serializer(value)
        except Exception as exc:  # noqa: BLE001 - exact behavior is asserted.
            return type(exc), str(exc)

    shared = ["retained once", {"accent": "ž"}]
    valid = {
        "left": shared,
        "right": shared,
        "nested": [None, False, 7, -0.0, "漢字"],
    }
    assert helper(valid) == strict_reference(valid)

    cycle = []
    cycle.append(cycle)
    for invalid in (
            {"bad": float("nan")},
            {"bad": "\ud800"},
            {"bad": object()},
            cycle):
        assert outcome(helper, invalid) == outcome(strict_reference, invalid)

    original = runtime_bundle_module._stable_decision_semantics_document.__code__

    def forged_projector(_selected, _package_root):
        return {
            "schemaVersion":
                "ofarm.runtime-decision-semantics-identity.local.v1",
            "entries": [],
        }

    try:
        runtime_bundle_module._stable_decision_semantics_document.__code__ = \
            forged_projector.__code__
        with pytest.raises(RuntimeBundleError, match="implementation changed"):
            observed_decision_semantics_component(config.PACKAGE_ROOT)
    finally:
        runtime_bundle_module._stable_decision_semantics_document.__code__ = original

    helper_original = helper.__code__

    def forged_serializer(_value):
        return b"{}"

    try:
        helper.__code__ = forged_serializer.__code__
        with pytest.raises(RuntimeBundleError, match="implementation changed"):
            observed_decision_semantics_component(config.PACKAGE_ROOT)
    finally:
        helper.__code__ = helper_original


def test_runtime_bundle_refuses_new_module_claiming_retained_origin(fresh_env):
    store, _pipeline, _outputs = fresh_env
    module_name = f"_ofarm_fake_retained_origin_{uuid.uuid4().hex}"
    source = str(Path(json.__file__).resolve())
    loader = importlib.machinery.SourceFileLoader(module_name, source)
    module = types.ModuleType(module_name)
    module.__file__ = source
    module.__loader__ = loader
    module.__spec__ = importlib.machinery.ModuleSpec(
        module_name, loader=loader, origin=source)
    sys.modules[module_name] = module
    try:
        with pytest.raises(RuntimeBundleError, match="module set changed"):
            store.get_record(demo.FARMER)
    finally:
        del sys.modules[module_name]


def test_runtime_bundle_refuses_existing_module_object_replacement(fresh_env):
    store, _pipeline, _outputs = fresh_env
    original = sys.modules["typing.io"]
    sys.modules["typing.io"] = types.ModuleType("typing.io")
    try:
        with pytest.raises(RuntimeBundleError, match="module object replaced"):
            store.get_record(demo.FARMER)
    finally:
        sys.modules["typing.io"] = original


def test_runtime_bundle_refuses_same_module_loader_state_replacement(fresh_env):
    store, _pipeline, _outputs = fresh_env
    module = json
    original_spec = module.__spec__
    original_loader = module.__loader__
    source = str(Path(module.__file__).resolve())
    changed_loader = importlib.machinery.SourceFileLoader(module.__name__, source)
    module.__loader__ = changed_loader
    module.__spec__ = importlib.machinery.ModuleSpec(
        module.__name__, loader=changed_loader, origin=source)
    try:
        with pytest.raises(RuntimeBundleError, match="module state changed"):
            store.get_record(demo.FARMER)
    finally:
        module.__loader__ = original_loader
        module.__spec__ = original_spec


def test_runtime_bundle_refuses_none_valued_module_set_growth(fresh_env):
    store, _pipeline, _outputs = fresh_env
    module_name = f"_ofarm_none_import_blocker_{uuid.uuid4().hex}"
    sys.modules[module_name] = None
    try:
        with pytest.raises(RuntimeBundleError, match="module set changed"):
            store.get_record(demo.FARMER)
    finally:
        del sys.modules[module_name]


def test_runtime_bundle_refuses_sys_modules_mapping_replacement(fresh_env):
    store, _pipeline, _outputs = fresh_env
    original = sys.modules
    sys.modules = dict(original)
    try:
        with pytest.raises(RuntimeBundleError, match="sys.modules mapping identity"):
            store.get_record(demo.FARMER)
    finally:
        sys.modules = original


def test_runtime_bundle_refuses_path_importer_cache_replacement(fresh_env):
    store, _pipeline, _outputs = fresh_env
    retained_root = str(config.PACKAGE_ROOT.resolve())
    original = sys.path_importer_cache[retained_root]

    class HostileFinder:
        pass

    sys.path_importer_cache[retained_root] = HostileFinder()
    try:
        with pytest.raises(RuntimeBundleError, match="path_importer_cache"):
            store.get_record(demo.FARMER)
    finally:
        sys.path_importer_cache[retained_root] = original


def test_runtime_bundle_refuses_path_importer_cache_alias_key(fresh_env):
    store, _pipeline, _outputs = fresh_env
    retained_root = str(config.PACKAGE_ROOT.resolve())
    finder = sys.path_importer_cache.pop(retained_root)
    alias = retained_root + "/."
    sys.path_importer_cache[alias] = finder
    try:
        with pytest.raises(RuntimeBundleError, match="path importer cache key"):
            store.get_record(demo.FARMER)
    finally:
        del sys.path_importer_cache[alias]
        sys.path_importer_cache[retained_root] = finder


def test_runtime_bundle_refuses_file_finder_instance_method_override(fresh_env):
    store, _pipeline, _outputs = fresh_env
    retained_root = str(config.PACKAGE_ROOT.resolve())
    finder = sys.path_importer_cache[retained_root]
    finder.find_spec = lambda *args, **kwargs: None
    try:
        with pytest.raises(RuntimeBundleError, match="instance method override"):
            store.get_record(demo.FARMER)
    finally:
        del finder.find_spec


def test_runtime_bundle_refuses_sys_path_alias(fresh_env):
    store, _pipeline, _outputs = fresh_env
    retained_root = str(config.PACKAGE_ROOT.resolve())
    index = sys.path.index(retained_root)
    sys.path[index] = retained_root + "/."
    try:
        with pytest.raises(RuntimeBundleError, match="live sys.path changed"):
            store.get_record(demo.FARMER)
    finally:
        sys.path[index] = retained_root


def test_runtime_bundle_refuses_import_provider_method_replacement(fresh_env):
    store, _pipeline, _outputs = fresh_env
    provider = importlib.machinery.PathFinder
    original = vars(provider)["find_spec"]

    @classmethod
    def hostile_find_spec(cls, fullname, path=None, target=None):
        del cls, fullname, path, target
        return None

    provider.find_spec = hostile_find_spec
    try:
        with pytest.raises(RuntimeBundleError, match="import callable identity"):
            store.get_record(demo.FARMER)
    finally:
        provider.find_spec = original


def test_store_runtime_activation_fields_reject_direct_replacement(fresh_env):
    store, _pipeline, _outputs = fresh_env
    for field_name in (
        "_runtime_bundle",
        "_runtime_environment_seal",
        "_pending_runtime_bundle_activation",
        "_bootstrap_bundle",
        "_runtime_posture_verifiers",
        "_runtime_posture_verifier_codes",
    ):
        with pytest.raises(AttributeError, match="sealed lifecycle"):
            setattr(store, field_name, object())
    with pytest.raises(AttributeError, match="runtime dispatch is immutable"):
        store._require_transaction_python_posture = lambda: None  # type: ignore[method-assign]
    object.__setattr__(
        store, "_require_database_transaction_posture", lambda _cur: {})
    try:
        with pytest.raises(RuntimeError, match="runtime dispatch changed"):
            with store.tx():
                pass
    finally:
        object.__delattr__(store, "_require_database_transaction_posture")


@pytest.mark.skipif(sys.platform != "linux", reason="Linux executable mappings")
def test_runtime_bundle_late_native_mapping_rolls_back_current_transaction(
        fresh_env):
    store, _pipeline, _outputs = fresh_env
    party_id = f"party:issue171.late-native.{uuid.uuid4().hex}"
    mapped_path = (
        config.PACKAGE_ROOT / ".artifacts" /
        f"issue171-native-map-{uuid.uuid4().hex}.bin")
    mapped_path.parent.mkdir(parents=True, exist_ok=True)
    mapped_path.write_bytes(b"unretained executable mapping")
    descriptor = os.open(mapped_path, os.O_RDONLY)
    mapping = None
    try:
        with pytest.raises(RuntimeBundleError, match="native executable mappings"):
            with store.serialized_tx() as cur:
                store.insert_record(cur, {
                    "schemaVersion": "ofarm.party.v0.1",
                    "partyId": party_id,
                    "partyClass": "NATURAL_PERSON",
                    "displayName": "Issue 171 native mapping rollback (fictional)",
                    "partyState": "ACTIVE",
                    "recordedAt": context.now_iso(),
                })
                mapping = mmap.mmap(
                    descriptor, 0, flags=mmap.MAP_PRIVATE,
                    prot=mmap.PROT_READ | mmap.PROT_EXEC)
    finally:
        if mapping is not None:
            mapping.close()
        os.close(descriptor)
        mapped_path.unlink(missing_ok=True)
    assert store.get_record(party_id) is None


def test_runtime_bundle_shared_connection_serializes_complete_transactions(
        fresh_env):
    """A second sync FastAPI worker cannot join another worker's transaction."""
    store, _pipeline, _outputs = fresh_env
    writer_entered = threading.Event()
    writer_done = threading.Event()
    release_writer = threading.Event()
    reader_attempting = threading.Event()
    reader_done = threading.Event()
    failures = []
    result = []

    def writer():
        try:
            with store.tx() as cur:
                cur._execute_read("SELECT 1 AS ok")
                assert cur.fetchone()["ok"] == 1
                writer_entered.set()
                if not release_writer.wait(300):
                    raise AssertionError("threaded transaction test timed out")
        except BaseException as exc:  # preserve thread failures for the test
            failures.append(exc)
        finally:
            writer_done.set()

    def reader():
        try:
            if not writer_entered.wait(300):
                raise AssertionError("writer did not enter its transaction")
            reader_attempting.set()
            result.append(store.get_record(demo.FARMER))
        except BaseException as exc:  # preserve thread failures for the test
            failures.append(exc)
        finally:
            reader_done.set()

    writer_thread = threading.Thread(target=writer)
    reader_thread = threading.Thread(target=reader)
    try:
        writer_thread.start()
        assert writer_entered.wait(300), \
            "writer did not enter its governed transaction"
        reader_thread.start()
        assert reader_attempting.wait(300), \
            "reader did not attempt its governed transaction"
        # This short wait is the assertion under test: the shared Store must
        # keep the reader blocked for the complete writer transaction.
        assert reader_done.wait(0.25) is False
        release_writer.set()
        assert writer_done.wait(300), \
            "writer did not complete after release"
        assert reader_done.wait(300), \
            "reader did not complete after writer release"
        writer_thread.join(10)
        reader_thread.join(10)
    finally:
        release_writer.set()
        if writer_thread.ident is not None:
            writer_thread.join(10)
        if reader_thread.ident is not None:
            reader_thread.join(10)
    assert not writer_thread.is_alive()
    assert not reader_thread.is_alive()
    assert failures == []
    assert result and result[0]["record_id"] == demo.FARMER


def test_runtime_bundle_rejects_role_drift_before_governed_sql(fresh_env):
    store, _pipeline, _outputs = fresh_env
    role_name = f"ofarm_issue171_role_{uuid.uuid4().hex[:12]}"
    party_id = f"party:issue171.role-drift.{uuid.uuid4().hex}"
    entered = False
    Store._raw_connection(store).execute(
        sql.SQL("CREATE ROLE {}").format(sql.Identifier(role_name)))
    try:
        Store._raw_connection(store).execute(
            sql.SQL("SET ROLE {}").format(sql.Identifier(role_name)))
        with pytest.raises(
                RuntimeError,
                match="PostgreSQL current role differs"):
            with store.serialized_tx() as cur:
                entered = True
                store.insert_record(cur, {
                    "schemaVersion": "ofarm.party.v0.1",
                    "partyId": party_id,
                    "partyClass": "NATURAL_PERSON",
                    "displayName": "Issue 171 role drift test (fictional)",
                    "partyState": "ACTIVE",
                    "recordedAt": context.now_iso(),
                })
        assert entered is False
    finally:
        Store._raw_connection(store).execute("RESET ROLE")
        Store._raw_connection(store).execute(
            sql.SQL("DROP ROLE {}").format(sql.Identifier(role_name)))
    assert store.get_record(party_id) is None


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
            cur._execute_mutation(
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
        with Store._raw_connection(store).cursor() as cur:
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
            with unbound.serialized_tx() as cur:
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
            cur._execute_mutation(
                "INSERT INTO runtime_content_blob "
                "(content_digest, content_class, canonicalization, canonical_bytes, "
                "byte_length) VALUES (%s, 'CONTRACT_METADATA', 'EXACT_BYTES_V1', "
                "%s, %s)",
                (extra_digest, extra_bytes, len(extra_bytes)),
            )
            cur._execute_mutation(
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
    with Store._raw_connection(store).cursor() as cur:
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
        _selection_environment_seal=None,
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
    with Store._raw_connection(store).cursor() as cur:
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
        with Store._raw_connection(store).cursor() as cur:
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


def test_pending_runtime_seal_is_rechecked_before_bootstrap_commit():
    dbname = f"ofarm_issue171_pending_seal_{uuid.uuid4().hex[:10]}"
    admin_dsn = _admin_dsn()
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{dbname}"')
    params = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    params["dbname"] = dbname
    store = Store(dsn=psycopg.conninfo.make_conninfo(**params))
    module_name = f"_ofarm_pending_seal_{uuid.uuid4().hex}"
    source = str(Path(json.__file__).resolve())
    loader = importlib.machinery.SourceFileLoader(module_name, source)
    module = types.ModuleType(module_name)
    module.__file__ = source
    module.__loader__ = loader
    module.__spec__ = importlib.machinery.ModuleSpec(
        module_name, loader=loader, origin=source)
    try:
        store.migrate()
        try:
            with pytest.raises(RuntimeBundleError, match="module set changed"):
                with store.serialized_tx() as cur:
                    bundle = _build_live_runtime_bundle(
                        config.ACTIVE_PROFILE,
                        _database_environment=
                        Store._observe_database_environment(cur),
                    )
                    Store.install_runtime_bundle(store, cur, bundle)
                    with Store._bootstrap_bundle_writes(store, bundle):
                        Store._prepare_runtime_bundle_binding(store, bundle)
                        # Mutate only after the pending seal exists.  The outer
                        # transaction's final posture proof must detect it.
                        sys.modules[module_name] = module
        finally:
            sys.modules.pop(module_name, None)
            Store._discard_prepared_runtime_bundle_binding(store)
        assert store._runtime_bundle is None
        assert store._runtime_environment_seal is None
        assert store._pending_runtime_bundle_activation is None
        with Store._raw_connection(store).cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM ONLY runtime_bundle")
            assert cur.fetchone()["n"] == 0
    finally:
        sys.modules.pop(module_name, None)
        store.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


def test_pending_database_identity_is_rechecked_before_bootstrap_commit():
    dbname = f"ofarm_issue171_pending_db_{uuid.uuid4().hex[:10]}"
    role_name = f"ofarm_issue171_pending_{uuid.uuid4().hex[:12]}"
    admin_dsn = _admin_dsn()
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE ROLE {}").format(sql.Identifier(role_name)))
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    params = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    params["dbname"] = dbname
    store = Store(dsn=psycopg.conninfo.make_conninfo(**params))
    try:
        store.migrate()
        try:
            with pytest.raises(RuntimeError, match="PostgreSQL environment differs"):
                with store.serialized_tx() as cur:
                    bundle = _build_live_runtime_bundle(
                        config.ACTIVE_PROFILE,
                        _database_environment=
                        Store._observe_database_environment(cur),
                    )
                    Store.install_runtime_bundle(store, cur, bundle)
                    with Store._bootstrap_bundle_writes(store, bundle):
                        Store._prepare_runtime_bundle_binding(store, bundle)
                        store._transaction_state.connection.execute(
                            sql.SQL("SET LOCAL SESSION AUTHORIZATION {}").format(
                                sql.Identifier(role_name)))
                        cur._execute_read(
                            "SELECT CURRENT_USER::pg_catalog.text AS "
                            "current_user_name, SESSION_USER::pg_catalog.text AS "
                            "session_user_name"
                        )
                        identity = cur.fetchone()
                        assert identity == {
                            "current_user_name": role_name,
                            "session_user_name": role_name,
                        }
        finally:
            Store._discard_prepared_runtime_bundle_binding(store)
        assert store._runtime_bundle is None
        assert store._runtime_environment_seal is None
        assert store._pending_runtime_bundle_activation is None
        with Store._raw_connection(store).cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM ONLY runtime_bundle")
            assert cur.fetchone()["n"] == 0
    finally:
        store.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(dbname)))
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(
                sql.Identifier(role_name)))


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
        with Store._raw_connection(competing).transaction():
            with Store._raw_connection(competing).cursor() as cur:
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
        with Store._raw_connection(store).cursor() as cur:
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
