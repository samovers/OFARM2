"""Focused stable-identity tests for the issue #171 RuntimeBundle."""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from kernel.contracts import ContractRegistry
from kernel.runtime_bundle import (
    COMPONENT_CATALOG_VERSION,
    Canonicalization,
    ContentPlacement,
    RuntimeBundle,
    RuntimeBundleBuilder,
    RuntimeBundleError,
    RuntimeComponentRole,
    RuntimeComponentSpec,
    canonical_json_bytes,
    sha256_bytes,
    strict_json_document,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
TENANT_REF = "tenant:test.runtime-bundle"
POLICY_REF = "policy:test.runtime-bundle.v1"
SOURCE_REF = "python:test.runtime-bundle:adapter"


def _write(root: Path, relative_path: str, raw: bytes) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _selected_specs() -> tuple[RuntimeComponentSpec, ...]:
    return (
        RuntimeComponentSpec(
            role=RuntimeComponentRole.PROFILE_POLICY,
            logical_ref=POLICY_REF,
            relative_path="selected/policy.json",
            canonicalization=Canonicalization.CANONICAL_JSON,
            placement=ContentPlacement.GLOBAL,
        ),
        RuntimeComponentSpec(
            role=RuntimeComponentRole.ADAPTER_SOURCE,
            logical_ref=SOURCE_REF,
            relative_path="selected/adapter.py",
            canonicalization=Canonicalization.EXACT_BYTES,
            placement=ContentPlacement.GLOBAL,
        ),
    )


def _selected_root(
    root: Path,
    *,
    policy: bytes = (
        b'{"alpha":1,"beta":2,'
        b'"policyId":"policy:test.runtime-bundle.v1"}'
    ),
    source: bytes = b"def decide():\n    return True\n",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write(root, "selected/policy.json", policy)
    _write(root, "selected/adapter.py", source)
    return root


def _build(root: Path, specs=None):
    selected = _selected_specs() if specs is None else specs
    return RuntimeBundleBuilder(root, selected).build(TENANT_REF)


def test_identical_selected_content_is_stable_across_clean_locations(tmp_path):
    left_root = _selected_root(tmp_path / "checkout-a")
    right_root = _selected_root(tmp_path / "nested" / "checkout-b")

    left = _build(left_root)
    right = _build(right_root)

    assert left.digest == right.digest
    assert left.canonical_document_bytes == right.canonical_document_bytes
    assert left.components == right.components
    for root in (left_root, right_root):
        assert str(root.resolve()).encode("utf-8") not in left.canonical_document_bytes
    for spec in _selected_specs():
        assert spec.relative_path.encode("utf-8") not in left.canonical_document_bytes


def test_component_input_order_does_not_change_bundle_identity(tmp_path):
    root = _selected_root(tmp_path / "checkout")
    specs = _selected_specs()

    forward = _build(root, specs)
    reversed_order = _build(root, tuple(reversed(specs)))

    assert forward.digest == reversed_order.digest
    assert forward.canonical_document_bytes == reversed_order.canonical_document_bytes
    assert forward.components == reversed_order.components


def test_json_formatting_is_canonical_but_semantic_change_changes_digest(tmp_path):
    root = _selected_root(
        tmp_path / "checkout",
        policy=(
            b'{\n  "beta": 2,\n  "policyId": '
            b'"policy:test.runtime-bundle.v1",\n  "alpha": 1\n}\n'
        ),
    )
    formatted = _build(root)

    _write(
        root,
        "selected/policy.json",
        b'{"alpha":1,"beta":2,'
        b'"policyId":"policy:test.runtime-bundle.v1"}',
    )
    compact = _build(root)

    assert formatted.digest == compact.digest
    assert formatted.component(
        RuntimeComponentRole.PROFILE_POLICY, POLICY_REF
    ).canonical_bytes == (
        b'{"alpha":1,"beta":2,'
        b'"policyId":"policy:test.runtime-bundle.v1"}'
    )

    _write(
        root,
        "selected/policy.json",
        b'{"alpha":1,"beta":3,'
        b'"policyId":"policy:test.runtime-bundle.v1"}',
    )
    changed = _build(root)

    assert changed.digest != compact.digest
    assert changed.component(
        RuntimeComponentRole.PROFILE_POLICY, POLICY_REF
    ).content_digest != compact.component(
        RuntimeComponentRole.PROFILE_POLICY, POLICY_REF
    ).content_digest


def test_exact_byte_change_changes_component_and_bundle_digest(tmp_path):
    root = _selected_root(tmp_path / "checkout")
    original = _build(root)

    _write(
        root,
        "selected/adapter.py",
        b"def decide():\n    return True\n# exact-byte change\n",
    )
    changed = _build(root)

    original_source = original.component(RuntimeComponentRole.ADAPTER_SOURCE, SOURCE_REF)
    changed_source = changed.component(RuntimeComponentRole.ADAPTER_SOURCE, SOURCE_REF)
    assert changed_source.content_digest != original_source.content_digest
    assert changed.digest != original.digest


def test_missing_selected_file_refuses_bundle_construction(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    spec = RuntimeComponentSpec(
        role=RuntimeComponentRole.PROFILE_POLICY,
        logical_ref=POLICY_REF,
        relative_path="selected/missing-policy.json",
        canonicalization=Canonicalization.CANONICAL_JSON,
        placement=ContentPlacement.GLOBAL,
    )

    with pytest.raises(RuntimeBundleError, match="missing or escapes") as exc_info:
        _build(root, (spec,))

    message = str(exc_info.value)
    assert POLICY_REF in message
    assert spec.relative_path in message


def test_duplicate_component_identity_refuses_bundle_construction(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    _write(root, "selected/one.py", b"one\n")
    _write(root, "selected/two.py", b"two\n")
    duplicate_specs = tuple(
        RuntimeComponentSpec(
            role=RuntimeComponentRole.ADAPTER_SOURCE,
            logical_ref=SOURCE_REF,
            relative_path=relative_path,
            canonicalization=Canonicalization.EXACT_BYTES,
            placement=ContentPlacement.GLOBAL,
        )
        for relative_path in ("selected/one.py", "selected/two.py")
    )

    with pytest.raises(RuntimeBundleError, match="duplicate component identities"):
        _build(root, duplicate_specs)


def test_canonical_json_logical_ref_must_match_intrinsic_identity(tmp_path):
    root = _selected_root(
        tmp_path / "checkout",
        policy=b'{"policyId":"policy:different.v1"}',
    )

    with pytest.raises(RuntimeBundleError, match="does not declare policyId"):
        _build(root)


def test_runtime_bundle_create_rejects_non_component_without_attribute_error():
    with pytest.raises(RuntimeBundleError, match="non-component"):
        RuntimeBundle.create(TENANT_REF, [object()])


@pytest.mark.parametrize("invalid_length", (True, 1.0), ids=("boolean", "float"))
def test_runtime_bundle_document_requires_type_exact_component_identity(
    tmp_path,
    invalid_length,
):
    bundle = _build(_selected_root(tmp_path / "checkout", source=b"x"))
    document = json.loads(bundle.canonical_document_bytes)
    document["components"][0]["byteLength"] = invalid_length
    malformed_bytes = canonical_json_bytes(document)

    with pytest.raises(RuntimeBundleError, match="exact canonical component identity"):
        RuntimeBundle(
            tenant_ref=bundle.tenant_ref,
            components=bundle.components,
            canonical_document_bytes=malformed_bytes,
            digest=sha256_bytes(malformed_bytes),
        )


@pytest.mark.parametrize(
    ("raw", "message"),
    (
        (b'{"value":1,"value":2}', "duplicate key"),
        (b'{"value":NaN}', "non-finite number"),
        (b'{"value":Infinity}', "non-finite number"),
        (b'{"value":-Infinity}', "non-finite number"),
        (b'\xef\xbb\xbf{"value":1}', "UTF-8 BOM"),
        (b'{"value":"\xff"}', "strict UTF-8 JSON"),
        (b'{"value":"\\ud800"}', "outside canonical JSON"),
    ),
    ids=(
        "duplicate-key",
        "nan",
        "positive-infinity",
        "negative-infinity",
        "utf8-bom",
        "invalid-utf8",
        "lone-surrogate",
    ),
)
def test_strict_json_rejects_ambiguous_or_nonportable_input(raw, message):
    with pytest.raises(RuntimeBundleError, match=message):
        strict_json_document(raw, "test runtime document")


def _manifest_document() -> dict:
    return {
        "manifestVersion": COMPONENT_CATALOG_VERSION,
        "components": [
            {
                "role": RuntimeComponentRole.PROFILE_POLICY.value,
                "logicalRef": POLICY_REF,
                "path": "selected/policy.json",
                "canonicalization": Canonicalization.CANONICAL_JSON.value,
                "placement": ContentPlacement.GLOBAL.value,
            }
        ],
        "contractSchemas": [],
    }


def _write_manifest(root: Path, document: dict) -> None:
    _write(
        root,
        "kernel/runtime_bundle_components.json",
        json.dumps(document, separators=(",", ":")).encode("utf-8"),
    )


@pytest.mark.parametrize(
    ("case", "message"),
    (
        ("unknown-top-field", "unknown or missing fields"),
        ("missing-top-field", "unknown or missing fields"),
        ("unsupported-version", "version is unsupported"),
        ("components-not-list", "components must be a list"),
        ("contract-path-not-string", "contractSchemas must be strings"),
        ("unknown-entry-field", "entry 0 has unknown or missing fields"),
        ("missing-entry-field", "entry 0 has unknown or missing fields"),
        ("unknown-role", "unknown vocabulary value"),
        ("unsafe-path", "must be a normalized relative path"),
    ),
    ids=(
        "unknown-top-field",
        "missing-top-field",
        "unsupported-version",
        "components-not-list",
        "contract-path-not-string",
        "unknown-entry-field",
        "missing-entry-field",
        "unknown-role",
        "unsafe-path",
    ),
)
def test_component_manifest_has_a_closed_strict_shape(tmp_path, case, message):
    root = tmp_path / "checkout"
    root.mkdir()
    document = _manifest_document()
    component = document["components"][0]

    if case == "unknown-top-field":
        document["unexpected"] = True
    elif case == "missing-top-field":
        del document["contractSchemas"]
    elif case == "unsupported-version":
        document["manifestVersion"] = "ofarm.runtime-component-catalog.local.v999"
    elif case == "components-not-list":
        document["components"] = {}
    elif case == "contract-path-not-string":
        document["contractSchemas"] = [17]
    elif case == "unknown-entry-field":
        component["unexpected"] = True
    elif case == "missing-entry-field":
        del component["placement"]
    elif case == "unknown-role":
        component["role"] = "ARBITRARY_PYTHON_GRAPH"
    elif case == "unsafe-path":
        component["path"] = "../outside.json"
    else:  # pragma: no cover - the fixed parameter table is exhaustive
        raise AssertionError(case)

    _write_manifest(root, document)
    with pytest.raises(RuntimeBundleError, match=message):
        RuntimeBundleBuilder.from_manifest(root)


def test_component_manifest_is_decoded_with_the_strict_json_profile(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    raw = (
        b'{"manifestVersion":"ofarm.runtime-component-catalog.local.v1",'
        b'"components":[],"components":[],"contractSchemas":[]}'
    )
    _write(root, "kernel/runtime_bundle_components.json", raw)

    with pytest.raises(RuntimeBundleError, match="duplicate key"):
        RuntimeBundleBuilder.from_manifest(root)


def test_missing_manifest_root_uses_runtime_bundle_error(tmp_path):
    with pytest.raises(RuntimeBundleError, match="package root is unavailable"):
        RuntimeBundleBuilder.from_manifest(tmp_path / "missing-checkout")


def test_manifest_expected_digest_refuses_changed_selected_content(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    _write(
        root,
        "selected/policy.json",
        b'{"alpha":1,"policyId":"policy:test.runtime-bundle.v1"}',
    )
    document = _manifest_document()
    document["components"][0]["expectedContentDigest"] = "sha256:" + "0" * 64
    _write_manifest(root, document)

    builder = RuntimeBundleBuilder.from_manifest(root)
    with pytest.raises(RuntimeBundleError, match="digest is .* expected"):
        builder.build(TENANT_REF)


def test_descriptor_declared_files_are_exact_catalog_closure(tmp_path):
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    root = tmp_path / "checkout"
    selected_specs = tuple(
        spec for spec in checked_in.component_specs
        if spec.canonicalization is Canonicalization.CANONICAL_JSON
    )
    for spec in selected_specs:
        source = PACKAGE_ROOT / spec.relative_path
        destination = root / spec.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    incomplete_specs = tuple(
        spec for spec in selected_specs
        if spec.logical_ref != "contextsnapshot:si.ffs.pilot.compliance.demo.v0_1"
    )
    builder = RuntimeBundleBuilder(root, incomplete_specs)

    with pytest.raises(RuntimeBundleError, match="exactly retain profileInstanceFiles"):
        builder.build("tenant:si.ffs.pilot.demo")


def test_contract_registry_schema_omitted_from_catalog_refuses(tmp_path):
    root = _selected_root(tmp_path / "checkout")
    for relative_directory in (
        "contracts/kernel",
        "contracts/core",
        "contracts/platform",
        "contracts/drafts_reference/explainable_current_state_evidence",
    ):
        (root / relative_directory).mkdir(parents=True)
    _write(
        root,
        "contracts/core/OFARM_Test_schema_v0_1.json",
        b'{"properties":{"schemaVersion":{"const":"ofarm.test.v0.1"}}}',
    )
    builder = RuntimeBundleBuilder(root, _selected_specs())

    with pytest.raises(RuntimeBundleError, match="exactly retain ContractRegistry"):
        builder.build(TENANT_REF)


def _checked_builder_with_specs(specs, *, require_profile_descriptor=False):
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    return RuntimeBundleBuilder(
        PACKAGE_ROOT,
        specs,
        checked_in.contract_schema_paths,
        require_profile_descriptor=require_profile_descriptor,
    )


def test_catalog_cannot_relabel_manifest_as_exact_bytes():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    specs = tuple(
        replace(spec, canonicalization=Canonicalization.EXACT_BYTES)
        if spec.role is RuntimeComponentRole.ACTIVE_MANIFEST else spec
        for spec in checked_in.component_specs
    )

    with pytest.raises(RuntimeBundleError, match="ACTIVE_MANIFEST must use canonical JSON"):
        _checked_builder_with_specs(specs).build("tenant:si.ffs.pilot.demo")


def test_catalog_cannot_place_tenant_manifest_in_global_content():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    specs = tuple(
        replace(spec, placement=ContentPlacement.GLOBAL)
        if spec.role is RuntimeComponentRole.ACTIVE_MANIFEST else spec
        for spec in checked_in.component_specs
    )

    with pytest.raises(RuntimeBundleError, match="invalid content placement"):
        _checked_builder_with_specs(specs).build("tenant:si.ffs.pilot.demo")


def test_manifest_role_requires_the_manifest_schema_version(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    _write(
        root,
        "selected/manifest.json",
        b'{"manifestId":"manifest:test.v1",'
        b'"schemaVersion":"ofarm.queryplanir.v0.1"}',
    )
    spec = RuntimeComponentSpec(
        role=RuntimeComponentRole.ACTIVE_MANIFEST,
        logical_ref="manifest:test.v1",
        relative_path="selected/manifest.json",
        canonicalization=Canonicalization.CANONICAL_JSON,
        placement=ContentPlacement.TENANT,
    )

    with pytest.raises(RuntimeBundleError, match="unsupported schemaVersion"):
        RuntimeBundleBuilder(root, (spec,)).build(TENANT_REF)


def test_active_profile_catalog_cannot_omit_descriptor():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    specs = tuple(
        spec for spec in checked_in.component_specs
        if spec.role is not RuntimeComponentRole.PROFILE_DESCRIPTOR
    )

    with pytest.raises(RuntimeBundleError, match="require one profile descriptor"):
        _checked_builder_with_specs(specs).build("tenant:si.ffs.pilot.demo")


def test_active_artifact_set_ref_cannot_be_omitted_from_catalog():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    omitted_ref = "queryplan:si.ffs.spray-register.passportview.v0_1"
    specs = tuple(
        spec for spec in checked_in.component_specs
        if spec.logical_ref != omitted_ref
    )

    with pytest.raises(RuntimeBundleError, match="has no retained component"):
        _checked_builder_with_specs(specs).build("tenant:si.ffs.pilot.demo")


def test_checked_in_tenant_selection_cannot_be_owned_by_another_tenant():
    with pytest.raises(RuntimeBundleError, match="does not match RuntimeBundle tenant_ref"):
        RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build("tenant:other")


def test_checked_in_selection_is_stable_when_catalog_order_is_reversed():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    tenant_ref = "tenant:si.ffs.pilot.demo"
    forward = checked_in.build(tenant_ref)
    reversed_builder = RuntimeBundleBuilder(
        PACKAGE_ROOT,
        reversed(checked_in.component_specs),
        reversed(checked_in.contract_schema_paths),
    )

    assert reversed_builder.build(tenant_ref).digest == forward.digest


def test_production_catalog_cannot_remove_the_whole_profile_selection():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    retained_roles = {
        RuntimeComponentRole.PROFILE_POLICY,
        RuntimeComponentRole.REFERENCE_SOURCE,
        RuntimeComponentRole.VALIDATOR_SOURCE,
        RuntimeComponentRole.ADAPTER_SOURCE,
        RuntimeComponentRole.QUERY_OUTPUT_SOURCE,
        RuntimeComponentRole.RUNTIME_SCHEMA,
    }
    specs = tuple(
        spec for spec in checked_in.component_specs
        if spec.role in retained_roles
    )

    with pytest.raises(RuntimeBundleError, match="requires one profile descriptor"):
        _checked_builder_with_specs(
            specs, require_profile_descriptor=True
        ).build("tenant:si.ffs.pilot.demo")


def test_shipped_artifact_source_cannot_be_omitted_from_catalog():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    specs = tuple(
        spec for spec in checked_in.component_specs
        if spec.role is not RuntimeComponentRole.REFERENCE_SOURCE
    )

    with pytest.raises(RuntimeBundleError, match="artifact source refs"):
        _checked_builder_with_specs(specs).build("tenant:si.ffs.pilot.demo")


def test_reference_source_path_must_match_profile_artifact_resolution():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    specs = tuple(
        replace(
            spec,
            relative_path="kernel/validators.py",
            expected_content_digest=None,
        )
        if spec.role is RuntimeComponentRole.REFERENCE_SOURCE else spec
        for spec in checked_in.component_specs
    )

    with pytest.raises(RuntimeBundleError, match="source path does not match"):
        _checked_builder_with_specs(specs).build("tenant:si.ffs.pilot.demo")


def test_context_snapshot_cannot_name_an_unretained_reference(tmp_path):
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    root = tmp_path / "checkout"
    selected_paths = {
        spec.relative_path for spec in checked_in.component_specs
    } | set(checked_in.contract_schema_paths)
    for relative_path in selected_paths:
        source = PACKAGE_ROOT / relative_path
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    context_path = (
        root / "profile_si_ffs"
        / "OFARM_ContextSnapshot_example_si_ffs_pilot_compliance_v0_1.json"
    )
    context = json.loads(context_path.read_text())
    context["referenceSnapshotRefs"].append("referencesnapshot:unretained.v1")
    context_path.write_text(json.dumps(context))

    builder = RuntimeBundleBuilder(
        root,
        checked_in.component_specs,
        checked_in.contract_schema_paths,
        require_profile_descriptor=True,
    )
    with pytest.raises(RuntimeBundleError, match="ContextSnapshot basis"):
        builder.build("tenant:si.ffs.pilot.demo")


def test_checked_in_component_catalog_builds_the_reviewed_closed_set():
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build(
        "tenant:si.ffs.pilot.demo")

    expected_catalog_roles = {
        RuntimeComponentRole.ACTIVE_MANIFEST,
        RuntimeComponentRole.ADAPTER_SOURCE,
        RuntimeComponentRole.CONTRACT_SCHEMA,
        RuntimeComponentRole.PROFILE_DESCRIPTOR,
        RuntimeComponentRole.PROFILE_INSTANCE,
        RuntimeComponentRole.PROFILE_POLICY,
        RuntimeComponentRole.QUERY_OUTPUT_SOURCE,
        RuntimeComponentRole.QUERY_PLAN,
        RuntimeComponentRole.QUERY_SPECIFICATION,
        RuntimeComponentRole.REFERENCE_SNAPSHOT,
        RuntimeComponentRole.REFERENCE_SOURCE,
        RuntimeComponentRole.RUNTIME_SCHEMA,
        RuntimeComponentRole.VALIDATOR_SOURCE,
    }
    expected_vocabulary = expected_catalog_roles | {
        RuntimeComponentRole.RELEASE_MANIFEST,
    }

    assert len(bundle.components) == 88
    assert {component.role for component in bundle.components} == expected_catalog_roles
    assert set(RuntimeComponentRole) == expected_vocabulary
    identities = [
        (component.role.value, component.logical_ref)
        for component in bundle.components
    ]
    assert identities == sorted(identities)
    assert len(identities) == len(set(identities))
    retained_contract_refs = {
        component.logical_ref
        for component in bundle.components
        if component.role is RuntimeComponentRole.CONTRACT_SCHEMA
    }
    assert retained_contract_refs == {
        f"contract:{kind}" for kind in ContractRegistry().kinds()
    }
