"""Focused stable-identity tests for the issue #171 RuntimeBundle."""
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import replace
from enum import IntEnum
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
    RuntimeComponent,
    RuntimeComponentRole,
    RuntimeComponentSpec,
    require_tenant_ref,
    canonical_json_bytes,
    strict_json_document,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
POLICY_REF = "policy:test.runtime-bundle.v1"
SOURCE_REF = "python:test.runtime-bundle:adapter"
TENANT_SCOPE_LOCATIONS = (
    (
        "profile_si_ffs/OFARM_PackActivationSet_example_si_ffs_pilot_v0_1.json",
        ("targetScope",),
    ),
    (
        "profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json",
        ("deploymentScope",),
    ),
    (
        "profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json",
        ("deploymentScope",),
    ),
    (
        "profile_si_ffs/OFARM_ContextSnapshot_example_si_ffs_pilot_compliance_v0_1.json",
        ("anchorScopes", 0),
    ),
)
EXPECTED_EXECUTABLE_SOURCE_SELECTION = {
    (
        RuntimeComponentRole.VALIDATOR_SOURCE,
        "python:ofarm2-kernel-m1.0:validators",
        "kernel/validators.py",
    ),
    (
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:ofarm2-kernel-m1.0:adapters",
        "kernel/adapters.py",
    ),
    (
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:ofarm2-kernel-m1.0:profile-runtime-provider-registry",
        "kernel/profile_runtime_provider.py",
    ),
    (
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:ofarm2-kernel-m1.0:provider-import-policy",
        "kernel/provider_import_policy.py",
    ),
    (
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:ofarm2-kernel-m1.0:profile-runtime-services",
        "kernel/profile_runtime_services.py",
    ),
    (
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:profile-si-ffs-v0_1:regsr-adapter",
        "kernel/profiles/si_ffs/regsr_adapter.py",
    ),
    (
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:profile-si-ffs-v0_1:gerk-adapter",
        "kernel/profiles/si_ffs/gerk_adapter.py",
    ),
    (
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:profile-si-ffs-v0_1:ffsnaprave-adapter",
        "kernel/profiles/si_ffs/ffsnaprave_adapter.py",
    ),
    (
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:profile-si-ffs-v0_1:bindings",
        "kernel/profiles/si_ffs/si_bindings.py",
    ),
    (
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:profile-si-ffs-v0_1:runtime-provider",
        "kernel/profiles/si_ffs/runtime_provider.py",
    ),
    (
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:profile-si-ffs-v0_1:manifest-inputs",
        "kernel/profiles/si_ffs/manifest_inputs.py",
    ),
    (
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:profile-si-ffs-v0_1:regsr-parser",
        "tooling/regsr_snapshot/parse_regsr.py",
    ),
    (
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:profile-si-ffs-v0_1:gerk-parser",
        "tooling/gerk_roundtrip/gerk_roundtrip.py",
    ),
    (
        RuntimeComponentRole.QUERY_OUTPUT_SOURCE,
        "python:ofarm2-kernel-m1.0:query-output",
        "kernel/profiles/si_ffs/outputs.py",
    ),
}


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
    return RuntimeBundleBuilder(root, selected).build()


def test_identical_selected_content_is_stable_across_clean_locations(tmp_path):
    left_root = _selected_root(tmp_path / "checkout-a")
    right_root = _selected_root(tmp_path / "nested" / "checkout-b")

    left = _build(left_root)
    right = _build(right_root)

    assert left.digest == right.digest
    assert left.canonical_document_bytes == right.canonical_document_bytes
    assert left.components == right.components
    assert left.selected_tenant_ref is None
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


@pytest.mark.parametrize(
    (
        "role",
        "logical_ref",
        "canonicalization",
        "placement",
        "selected_bytes",
        "message",
    ),
    (
        (
            RuntimeComponentRole.ACTIVE_MANIFEST,
            "manifest:test.direct.v1",
            Canonicalization.EXACT_BYTES,
            ContentPlacement.GLOBAL,
            b"not-json",
            "must use canonical JSON",
        ),
        (
            RuntimeComponentRole.ACTIVE_MANIFEST,
            "manifest:test.direct.v1",
            Canonicalization.CANONICAL_JSON,
            ContentPlacement.GLOBAL,
            (
                b'{"manifestId":"manifest:test.direct.v1",'
                b'"schemaVersion":"ofarm.capabilitymanifest.v0.1"}'
            ),
            "invalid content placement",
        ),
        (
            RuntimeComponentRole.ACTIVE_MANIFEST,
            "manifest:test.direct.v1",
            Canonicalization.CANONICAL_JSON,
            ContentPlacement.TENANT,
            (
                b'{"manifestId":"manifest:test.direct.v1",'
                b'"schemaVersion":"ofarm.queryplanir.v0.1"}'
            ),
            "unsupported schemaVersion",
        ),
        (
            RuntimeComponentRole.PROFILE_POLICY,
            "policy:test.expected.v1",
            Canonicalization.CANONICAL_JSON,
            ContentPlacement.GLOBAL,
            b'{"policyId":"policy:test.different.v1"}',
            "does not declare policyId",
        ),
        (
            RuntimeComponentRole.VIEW_BINDING,
            "view:test.direct.v1",
            Canonicalization.CANONICAL_JSON,
            ContentPlacement.GLOBAL,
            (
                b'{"extra":true,"queryOutputSourceRef":"python:test:output",'
                b'"queryPlanRef":"queryplan:test.direct.v1",'
                b'"querySpecificationRef":"queryspec:test.direct.v1",'
                b'"schemaVersion":"ofarm.runtime-view-binding.local.v1",'
                b'"viewRef":"view:test.direct.v1"}'
            ),
            "invalid shape",
        ),
        (
            RuntimeComponentRole.DRAFT_CONTRACT_SCHEMA,
            "contract:ofarm.test.expected-draft.v0.1",
            Canonicalization.EXACT_BYTES,
            ContentPlacement.GLOBAL,
            canonical_json_bytes({
                "properties": {
                    "schemaVersion": {
                        "const": "ofarm.test.different-draft.v0.1",
                    },
                },
            }),
            "does not declare its logical ref",
        ),
    ),
    ids=(
        "wrong-canonicalization",
        "wrong-placement",
        "wrong-role-schema",
        "mismatched-intrinsic-identity",
        "open-view-binding-shape",
        "draft-contract-logical-ref",
    ),
)
def test_direct_component_construction_enforces_role_semantics(
    role,
    logical_ref,
    canonicalization,
    placement,
    selected_bytes,
    message,
):
    with pytest.raises(RuntimeBundleError, match=message):
        RuntimeComponent.from_selected_bytes(
            role=role,
            logical_ref=logical_ref,
            canonicalization=canonicalization,
            placement=placement,
            selected_bytes=selected_bytes,
        )


@pytest.mark.parametrize(
    ("field_path", "wrong_value", "message"),
    (
        (
            ("deploymentScope", "scopeRef"),
            "tenant:other",
            "tenant scopes do not identify one tenant",
        ),
        (
            ("registryRelation", "activeArtifactSetRef"),
            "activeartifactset:other.v0_1",
            "deployment identity",
        ),
    ),
    ids=("mixed-tenant", "mismatched-deployment"),
)
def test_direct_bundle_construction_enforces_selected_runtime_closure(
    field_path,
    wrong_value,
    message,
):
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()
    manifest = next(
        component for component in bundle.components
        if component.role is RuntimeComponentRole.ACTIVE_MANIFEST
    )
    document = json.loads(manifest.canonical_bytes)
    parent = document
    for field in field_path[:-1]:
        parent = parent[field]
    parent[field_path[-1]] = wrong_value
    changed_manifest = RuntimeComponent.from_selected_bytes(
        role=manifest.role,
        logical_ref=manifest.logical_ref,
        canonicalization=manifest.canonicalization,
        placement=manifest.placement,
        selected_bytes=json.dumps(document).encode("utf-8"),
    )

    with pytest.raises(RuntimeBundleError, match=message):
        RuntimeBundle.create(
            changed_manifest if component is manifest else component
            for component in bundle.components
        )


def test_direct_bundle_construction_requires_descriptor_selected_policy():
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()

    with pytest.raises(RuntimeBundleError, match="exact profile policy component"):
        RuntimeBundle.create(
            component for component in bundle.components
            if component.role is not RuntimeComponentRole.PROFILE_POLICY
        )


def test_direct_bundle_construction_closes_manifest_contract_claims():
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()

    with pytest.raises(
        RuntimeBundleError,
        match="supported artifact type is not retained as a canonical contract",
    ):
        RuntimeBundle.create(
            component for component in bundle.components
            if not (
                component.role is RuntimeComponentRole.CONTRACT_SCHEMA
                and component.logical_ref == "contract:ofarm.party.v0.1"
            )
        )


@pytest.mark.parametrize(
    "anchor_scopes",
    (
        17,
        [],
        [17, {
            "scopeType": "TENANT",
            "scopeRef": "tenant:si.ffs.pilot.demo",
        }],
        [{
            "scopeType": "TENANT",
            "scopeRef": "tenant:si.ffs.pilot.demo",
            "extra": True,
        }],
        [{
            "scopeType": 17,
            "scopeRef": "tenant:si.ffs.pilot.demo",
        }],
        [{
            "scopeType": [],
            "scopeRef": "tenant:si.ffs.pilot.demo",
        }],
        [{
            "scopeType": {},
            "scopeRef": "tenant:si.ffs.pilot.demo",
        }],
        [{
            "scopeType": "TENANT",
            "scopeRef": 17,
        }],
    ),
    ids=(
        "scalar",
        "empty",
        "mixed-member-types",
        "open-scope-object",
        "untyped-scope-type",
        "unhashable-list-scope-type",
        "unhashable-object-scope-type",
        "untyped-scope-ref",
    ),
)
def test_direct_bundle_construction_rejects_malformed_context_anchor_scopes(
    anchor_scopes,
):
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()
    context = next(
        component for component in bundle.components
        if (
            component.role is RuntimeComponentRole.PROFILE_INSTANCE
            and component.logical_ref.startswith("contextsnapshot:")
        )
    )
    document = json.loads(context.canonical_bytes)
    document["anchorScopes"] = anchor_scopes
    changed_context = RuntimeComponent.from_selected_bytes(
        role=context.role,
        logical_ref=context.logical_ref,
        canonicalization=context.canonicalization,
        placement=context.placement,
        selected_bytes=json.dumps(document).encode("utf-8"),
    )

    with pytest.raises(RuntimeBundleError, match="anchorScopes"):
        RuntimeBundle.create(
            changed_context if component is context else component
            for component in bundle.components
        )


def test_direct_bundle_construction_refuses_malformed_profile_scope():
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()
    code_binding = next(
        component for component in bundle.components
        if (
            component.role is RuntimeComponentRole.PROFILE_INSTANCE
            and json.loads(component.canonical_bytes).get("schemaVersion")
            == "ofarm.agronomiccodebindingprofile.v0.1"
        )
    )
    document = json.loads(code_binding.canonical_bytes)
    document["profileScope"] = ["not-an-object"]
    changed_code_binding = RuntimeComponent.from_selected_bytes(
        role=code_binding.role,
        logical_ref=code_binding.logical_ref,
        canonicalization=code_binding.canonicalization,
        placement=code_binding.placement,
        selected_bytes=canonical_json_bytes(document),
    )

    with pytest.raises(
        RuntimeBundleError,
        match=(
            "selected profile runtime is inconsistent: "
            "code-binding profile profileScope must be an object"
        ),
    ):
        RuntimeBundle.create(
            changed_code_binding if component is code_binding else component
            for component in bundle.components
        )


def test_direct_bundle_construction_refuses_malformed_profile_pack_refs():
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()
    code_binding = next(
        component for component in bundle.components
        if (
            component.role is RuntimeComponentRole.PROFILE_INSTANCE
            and json.loads(component.canonical_bytes).get("schemaVersion")
            == "ofarm.agronomiccodebindingprofile.v0.1"
        )
    )
    document = json.loads(code_binding.canonical_bytes)
    document["profileScope"]["packRefs"] = [123]
    changed_code_binding = RuntimeComponent.from_selected_bytes(
        role=code_binding.role,
        logical_ref=code_binding.logical_ref,
        canonicalization=code_binding.canonicalization,
        placement=code_binding.placement,
        selected_bytes=canonical_json_bytes(document),
    )

    with pytest.raises(
        RuntimeBundleError,
        match=(
            "selected profile runtime is inconsistent: "
            "code-binding profile profileScope.packRefs must be a "
            "non-empty list of strings"
        ),
    ):
        RuntimeBundle.create(
            changed_code_binding if component is code_binding else component
            for component in bundle.components
        )


def test_canonical_numeric_profile_refuses_a_lossy_float_collision():
    accepted = RuntimeComponent.from_selected_bytes(
        role=RuntimeComponentRole.PROFILE_POLICY,
        logical_ref="policy:test.numeric.v1",
        canonicalization=Canonicalization.CANONICAL_JSON,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=(
            b'{"policyId":"policy:test.numeric.v1",'
            b'"value":9007199254740992.0}'
        ),
    )
    RuntimeBundle.create((accepted,))

    with pytest.raises(RuntimeBundleError, match="not preserved"):
        RuntimeComponent.from_selected_bytes(
            role=RuntimeComponentRole.PROFILE_POLICY,
            logical_ref="policy:test.numeric.v1",
            canonicalization=Canonicalization.CANONICAL_JSON,
            placement=ContentPlacement.GLOBAL,
            selected_bytes=(
                b'{"policyId":"policy:test.numeric.v1",'
                b'"value":9007199254740993.0}'
            ),
        )


@pytest.mark.parametrize("sign", ("", "-"), ids=("positive", "negative"))
@pytest.mark.parametrize(
    ("digit_count", "accepted"),
    ((640, True), (641, False)),
    ids=("at-limit", "over-limit"),
)
def test_strict_json_integer_bound_is_process_independent(
    sign,
    digit_count,
    accepted,
):
    token = sign + ("1" * digit_count)
    raw = f'{{"value":{token}}}'.encode("ascii")
    original_limit = sys.get_int_max_str_digits()
    outcomes = []

    try:
        for process_limit in (640, 0):
            sys.set_int_max_str_digits(process_limit)
            try:
                document, canonical = strict_json_document(
                    raw, "test runtime document"
                )
            except RuntimeBundleError as exc:
                outcomes.append(("error", str(exc)))
            else:
                outcomes.append(("accepted", document["value"], canonical))
    finally:
        sys.set_int_max_str_digits(original_limit)

    assert sys.get_int_max_str_digits() == original_limit
    assert outcomes[0] == outcomes[1]
    if accepted:
        assert outcomes[0] == ("accepted", int(token), raw)
    else:
        assert outcomes[0] == (
            "error",
            "JSON integer exceeds the canonical limit of 640 decimal digits",
        )


@pytest.mark.parametrize("sign", (1, -1), ids=("positive", "negative"))
@pytest.mark.parametrize(
    ("digit_count", "accepted"),
    ((640, True), (641, False)),
    ids=("at-limit", "over-limit"),
)
def test_canonical_json_encoder_integer_bound_is_process_independent(
    sign,
    digit_count,
    accepted,
):
    value = sign * (10 ** (digit_count - 1))
    document = {"nested": [{"value": value}]}
    original_limit = sys.get_int_max_str_digits()
    outcomes = []

    try:
        for process_limit in (640, 0):
            sys.set_int_max_str_digits(process_limit)
            try:
                canonical = canonical_json_bytes(document)
            except RuntimeBundleError as exc:
                outcomes.append(("error", str(exc)))
            else:
                outcomes.append(("accepted", canonical))
    finally:
        sys.set_int_max_str_digits(original_limit)

    assert sys.get_int_max_str_digits() == original_limit
    assert outcomes[0] == outcomes[1]
    if accepted:
        token = ("-" if sign < 0 else "") + "1" + ("0" * (digit_count - 1))
        assert outcomes[0] == (
            "accepted",
            f'{{"nested":[{{"value":{token}}}]}}'.encode("ascii"),
        )
    else:
        assert outcomes[0] == (
            "error",
            "JSON integer exceeds the canonical limit of 640 decimal digits",
        )


def test_canonical_json_encoder_integer_bound_covers_int_subclasses():
    class OverLimitInteger(IntEnum):
        VALUE = 10 ** 640

    document = {"nested": [{"value": OverLimitInteger.VALUE}]}
    original_limit = sys.get_int_max_str_digits()
    outcomes = []

    try:
        for process_limit in (640, 0):
            sys.set_int_max_str_digits(process_limit)
            try:
                canonical_json_bytes(document)
            except RuntimeBundleError as exc:
                outcomes.append(("error", str(exc)))
            else:
                outcomes.append(("accepted",))
    finally:
        sys.set_int_max_str_digits(original_limit)

    assert outcomes == [
        (
            "error",
            "JSON integer exceeds the canonical limit of 640 decimal digits",
        ),
        (
            "error",
            "JSON integer exceeds the canonical limit of 640 decimal digits",
        ),
    ]


def test_canonical_encoder_bound_cannot_be_overridden_by_int_subclass():
    class BypassInteger(int):
        def __abs__(self):
            return 0

    document = {"nested": [{"value": BypassInteger(10 ** 640)}]}
    original_limit = sys.get_int_max_str_digits()
    outcomes = []

    try:
        for process_limit in (640, 0):
            sys.set_int_max_str_digits(process_limit)
            try:
                canonical_json_bytes(document)
            except RuntimeBundleError as exc:
                outcomes.append(("error", str(exc)))
            else:
                outcomes.append(("accepted",))
    finally:
        sys.set_int_max_str_digits(original_limit)

    assert outcomes == [
        (
            "error",
            "JSON integer exceeds the canonical limit of 640 decimal digits",
        ),
        (
            "error",
            "JSON integer exceeds the canonical limit of 640 decimal digits",
        ),
    ]


def test_canonical_encoder_refuses_non_string_object_keys_before_encoding():
    document = {"nested": [{10 ** 640: "value"}]}
    original_limit = sys.get_int_max_str_digits()
    outcomes = []

    try:
        for process_limit in (640, 0):
            sys.set_int_max_str_digits(process_limit)
            try:
                canonical_json_bytes(document)
            except RuntimeBundleError as exc:
                outcomes.append(("error", str(exc)))
            else:
                outcomes.append(("accepted",))
    finally:
        sys.set_int_max_str_digits(original_limit)

    assert outcomes == [
        ("error", "JSON object keys must be strings"),
        ("error", "JSON object keys must be strings"),
    ]


@pytest.mark.parametrize("sign", ("", "-"), ids=("positive", "negative"))
@pytest.mark.parametrize(
    ("digit_count", "accepted"),
    ((640, True), (641, False)),
    ids=("at-limit", "over-limit"),
)
def test_direct_bundle_construction_enforces_integer_bound(
    sign,
    digit_count,
    accepted,
):
    token = sign + ("1" * digit_count)
    raw = (
        b'{"policyId":"policy:test.integer.v1","value":'
        + token.encode("ascii")
        + b"}"
    )
    original_limit = sys.get_int_max_str_digits()

    try:
        sys.set_int_max_str_digits(0)
        if accepted:
            component = RuntimeComponent.from_selected_bytes(
                role=RuntimeComponentRole.PROFILE_POLICY,
                logical_ref="policy:test.integer.v1",
                canonicalization=Canonicalization.CANONICAL_JSON,
                placement=ContentPlacement.GLOBAL,
                selected_bytes=raw,
            )
            assert component.canonical_bytes == raw
            assert RuntimeBundle.create((component,)).components == (component,)
        else:
            with pytest.raises(
                RuntimeBundleError,
                match="canonical limit of 640 decimal digits",
            ):
                RuntimeComponent.from_selected_bytes(
                    role=RuntimeComponentRole.PROFILE_POLICY,
                    logical_ref="policy:test.integer.v1",
                    canonicalization=Canonicalization.CANONICAL_JSON,
                    placement=ContentPlacement.GLOBAL,
                    selected_bytes=raw,
                )
        assert sys.get_int_max_str_digits() == 0
    finally:
        sys.set_int_max_str_digits(original_limit)

    assert sys.get_int_max_str_digits() == original_limit


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
        (
            b'{"value":1e-9999999999999999999}',
            "outside the canonical numeric profile",
        ),
    ),
    ids=(
        "duplicate-key",
        "nan",
        "positive-infinity",
        "negative-infinity",
        "utf8-bom",
        "invalid-utf8",
        "lone-surrogate",
        "extreme-exponent",
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


def _copy_checked_selection(root: Path, *, include_catalog: bool = False):
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    relative_paths = {
        spec.relative_path for spec in checked_in.component_specs
    } | set(checked_in.contract_schema_paths)
    if include_catalog:
        relative_paths.add("kernel/runtime_bundle_components.json")
    for relative_path in relative_paths:
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PACKAGE_ROOT / relative_path, destination)
    return checked_in


def _copied_checked_builder(root: Path, checked_in=None):
    selected = checked_in or _copy_checked_selection(root)
    return RuntimeBundleBuilder(
        root,
        selected.component_specs,
        selected.contract_schema_paths,
        require_profile_descriptor=True,
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


def test_full_checked_selection_is_stable_when_relocated(tmp_path):
    expected = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()
    root = tmp_path / "nested" / "relocated-release"
    _copy_checked_selection(root, include_catalog=True)

    actual = RuntimeBundleBuilder.from_manifest(root).build()

    assert actual == expected
    assert str(root.resolve()).encode("utf-8") not in actual.canonical_document_bytes


def test_descriptor_declared_files_are_exact_catalog_closure(tmp_path):
    root = tmp_path / "checkout"
    checked_in = _copy_checked_selection(root)
    descriptor_path = root / "profile_si_ffs/runtime_profile_descriptor.json"
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    context_name = (
        "OFARM_ContextSnapshot_example_si_ffs_pilot_compliance_v0_1.json"
    )
    duplicate_name = "OFARM_ContextSnapshot_duplicate_v0_1.json"
    shutil.copy2(
        root / "profile_si_ffs" / context_name,
        root / "profile_si_ffs" / duplicate_name,
    )
    descriptor["profileInstanceFiles"] = [
        duplicate_name if name == context_name else name
        for name in descriptor["profileInstanceFiles"]
    ]
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")

    with pytest.raises(RuntimeBundleError, match="exactly retain profileInstanceFiles"):
        _copied_checked_builder(root, checked_in).build()


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
        builder.build()


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
        _checked_builder_with_specs(specs).build()


def test_catalog_cannot_place_tenant_manifest_in_global_content():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    specs = tuple(
        replace(spec, placement=ContentPlacement.GLOBAL)
        if spec.role is RuntimeComponentRole.ACTIVE_MANIFEST else spec
        for spec in checked_in.component_specs
    )

    with pytest.raises(RuntimeBundleError, match="invalid content placement"):
        _checked_builder_with_specs(specs).build()


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
        RuntimeBundleBuilder(root, (spec,)).build()


def test_active_profile_catalog_cannot_omit_descriptor():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    specs = tuple(
        spec for spec in checked_in.component_specs
        if spec.role is not RuntimeComponentRole.PROFILE_DESCRIPTOR
    )

    with pytest.raises(RuntimeBundleError, match="require one profile descriptor"):
        _checked_builder_with_specs(specs).build()


def test_active_profile_catalog_cannot_omit_descriptor_selected_policy():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    specs = tuple(
        spec for spec in checked_in.component_specs
        if spec.role is not RuntimeComponentRole.PROFILE_POLICY
    )

    with pytest.raises(RuntimeBundleError, match="exact profile policy component"):
        _checked_builder_with_specs(specs).build()


def test_active_artifact_set_ref_cannot_be_omitted_from_catalog():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    omitted_ref = "queryplan:si.ffs.spray-register.passportview.v0_1"
    specs = tuple(
        spec for spec in checked_in.component_specs
        if spec.logical_ref != omitted_ref
    )

    with pytest.raises(RuntimeBundleError, match="has no retained component"):
        _checked_builder_with_specs(specs).build()


def test_active_artifact_set_cannot_activate_a_retained_draft_contract():
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()
    draft_ref = next(
        component.logical_ref for component in bundle.components
        if component.role is RuntimeComponentRole.DRAFT_CONTRACT_SCHEMA
    )
    active_set = next(
        component for component in bundle.components
        if component.role is RuntimeComponentRole.PROFILE_INSTANCE
        and component.logical_ref.startswith("activeartifactset:")
    )
    document = json.loads(active_set.canonical_bytes)
    document["activeArtifactRefs"].append(draft_ref)
    changed_active_set = RuntimeComponent.from_selected_bytes(
        role=active_set.role,
        logical_ref=active_set.logical_ref,
        canonicalization=active_set.canonicalization,
        placement=active_set.placement,
        selected_bytes=canonical_json_bytes(document),
    )
    active_identity = (active_set.role, active_set.logical_ref)
    components = tuple(
        changed_active_set
        if (component.role, component.logical_ref) == active_identity
        else component
        for component in bundle.components
    )

    with pytest.raises(RuntimeBundleError, match="eligible for activation"):
        RuntimeBundle.create(components)


def test_active_artifact_set_cannot_select_an_unbound_view(tmp_path):
    root = tmp_path / "checkout"
    checked_in = _copy_checked_selection(root)
    path = (
        root
        / "profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json"
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    view_index = next(
        index for index, ref in enumerate(document["activeArtifactRefs"])
        if ref.startswith("view:")
    )
    document["activeArtifactRefs"][view_index] = "view:unbound.v0_1"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RuntimeBundleError, match="has no retained component"):
        _copied_checked_builder(root, checked_in).build()


@pytest.mark.parametrize(
    ("field", "unretained_ref"),
    (
        (
            "querySpecificationRef",
            "queryspec:unretained.v0_1",
        ),
        (
            "queryPlanRef",
            "queryplan:si.ffs.inspection-register.documentassembly.v0_1",
        ),
        (
            "queryOutputSourceRef",
            "python:unretained:query-output",
        ),
    ),
    ids=("query-specification", "query-plan", "query-output-source"),
)
def test_view_binding_must_match_retained_query_artifacts(
    tmp_path,
    field,
    unretained_ref,
):
    root = tmp_path / "checkout"
    checked_in = _copy_checked_selection(root)
    path = (
        root
        / "profile_si_ffs/views/"
        "OFARM_RuntimeViewBinding_si_ffs_spray_register_passportview_v0_1.json"
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    document[field] = unretained_ref
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RuntimeBundleError, match="does not exactly retain"):
        _copied_checked_builder(root, checked_in).build()


def test_view_bindings_must_cover_selected_query_artifacts(tmp_path):
    root = tmp_path / "checkout"
    checked_in = _copy_checked_selection(root)
    path = (
        root
        / "profile_si_ffs/views/"
        "OFARM_RuntimeViewBinding_si_ffs_spray_register_passportview_v0_1.json"
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    document.update({
        "querySpecificationRef": (
            "queryspec:si.ffs.inspection-register.documentassembly.v0_1"
        ),
        "queryPlanRef": (
            "queryplan:si.ffs.inspection-register.documentassembly.v0_1"
        ),
    })
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RuntimeBundleError, match="do not exactly cover"):
        _copied_checked_builder(root, checked_in).build()


@pytest.mark.parametrize(
    ("relative_path", "scope_path"),
    TENANT_SCOPE_LOCATIONS,
    ids=("pack", "active-artifacts", "manifest", "context"),
)
def test_selected_tenant_scopes_must_identify_one_tenant(
    tmp_path,
    relative_path,
    scope_path,
):
    root = tmp_path / "checkout"
    checked_in = _copy_checked_selection(root)
    path = root / relative_path
    document = json.loads(path.read_text(encoding="utf-8"))
    scope = document
    for key in scope_path:
        scope = scope[key]
    scope["scopeRef"] = "tenant:other"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(
        RuntimeBundleError,
        match="selected tenant scopes do not identify one tenant",
    ):
        _copied_checked_builder(root, checked_in).build()


@pytest.mark.parametrize(
    "invalid_tenant_ref",
    ("", "tenant:", "farm:not-a-tenant"),
)
def test_selected_tenant_scope_ref_must_be_valid(tmp_path, invalid_tenant_ref):
    root = tmp_path / "checkout"
    checked_in = _copy_checked_selection(root)
    for relative_path, scope_path in TENANT_SCOPE_LOCATIONS:
        path = root / relative_path
        document = json.loads(path.read_text(encoding="utf-8"))
        scope = document
        for key in scope_path:
            scope = scope[key]
        scope["scopeRef"] = invalid_tenant_ref
        path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RuntimeBundleError, match="tenant scope|tenant anchor"):
        _copied_checked_builder(root, checked_in).build()


def test_tenant_ref_has_one_closed_bounded_syntax():
    assert require_tenant_ref("tenant:a") == "tenant:a"
    assert require_tenant_ref("tenant:" + "a" * 248) == "tenant:" + "a" * 248
    for invalid in (
        "x",
        "farm:x",
        "tenant:",
        "tenant:bad/path",
        "tenant:bad#fragment",
        "tenant:" + "a" * 249,
    ):
        with pytest.raises(RuntimeBundleError, match="tenant:"):
            require_tenant_ref(invalid)


@pytest.mark.parametrize(
    ("field_path", "wrong_value"),
    (
        (
            ("registryRelation", "activeArtifactSetRef"),
            "activeartifactset:other.v0_1",
        ),
        (
            ("registryRelation", "artifactRegistryRef"),
            "registry:other.v0_1",
        ),
        (
            ("capabilitySections", "packSupport", "activePackRefs"),
            ["pack:other.v0_1"],
        ),
        (
            ("capabilitySections", "packSupport", "activeProfileRefs"),
            ["profile:other.v0_1"],
        ),
    ),
    ids=("artifact-set", "registry", "pack", "profile"),
)
def test_manifest_must_match_selected_deployment_identity(
    tmp_path,
    field_path,
    wrong_value,
):
    root = tmp_path / "checkout"
    checked_in = _copy_checked_selection(root)
    path = root / "profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    parent = document
    for key in field_path[:-1]:
        parent = parent[key]
    parent[field_path[-1]] = wrong_value
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RuntimeBundleError, match="deployment identity"):
        _copied_checked_builder(root, checked_in).build()


def test_checked_in_selection_is_stable_when_catalog_order_is_reversed():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    forward = checked_in.build()
    reversed_builder = RuntimeBundleBuilder(
        PACKAGE_ROOT,
        reversed(checked_in.component_specs),
        reversed(checked_in.contract_schema_paths),
    )

    assert reversed_builder.build().digest == forward.digest


def test_production_catalog_cannot_remove_the_whole_profile_selection():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    retained_roles = {
        RuntimeComponentRole.PROFILE_POLICY,
        RuntimeComponentRole.REFERENCE_SOURCE,
        RuntimeComponentRole.VALIDATOR_SOURCE,
        RuntimeComponentRole.ADAPTER_SOURCE,
        RuntimeComponentRole.QUERY_OUTPUT_SOURCE,
    }
    specs = tuple(
        spec for spec in checked_in.component_specs
        if spec.role in retained_roles
    )

    with pytest.raises(RuntimeBundleError, match="requires one profile descriptor"):
        _checked_builder_with_specs(
            specs, require_profile_descriptor=True
        ).build()


def test_shipped_artifact_source_cannot_be_omitted_from_catalog():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    specs = tuple(
        spec for spec in checked_in.component_specs
        if spec.role is not RuntimeComponentRole.REFERENCE_SOURCE
    )

    with pytest.raises(RuntimeBundleError, match="artifact source refs"):
        _checked_builder_with_specs(specs).build()


def test_reference_snapshot_digest_must_bind_retained_source_bytes(tmp_path):
    root = tmp_path / "checkout"
    checked_in = _copy_checked_selection(root)
    path = (
        root
        / "profile_si_ffs/"
        "OFARM_ReferenceSnapshot_example_si_uvhvvr_ffs_reg_2026-06-11.json"
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    document["sourceArtifactRefs"] = [
        "digest:sha256:" + "0" * 64 if ref.startswith("digest:") else ref
        for ref in document["sourceArtifactRefs"]
    ]
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RuntimeBundleError, match="does not exactly bind"):
        _copied_checked_builder(root, checked_in).build()


def test_reference_snapshot_digest_detects_exact_source_byte_change(tmp_path):
    root = tmp_path / "checkout"
    checked_in = _copy_checked_selection(root)
    path = root / "profile_si_ffs/examples/regsr_snapshot_2026-06-12.json"
    path.write_bytes(path.read_bytes() + b"\n")

    with pytest.raises(RuntimeBundleError, match="does not exactly bind"):
        _copied_checked_builder(root, checked_in).build()


def test_reference_source_path_must_match_profile_artifact_resolution(tmp_path):
    root = tmp_path / "checkout"
    checked_in = _copy_checked_selection(root)
    misplaced_path = "selected/regsr_snapshot_2026-06-12.json"
    _write(
        root,
        misplaced_path,
        (root / "profile_si_ffs/examples/regsr_snapshot_2026-06-12.json").read_bytes(),
    )
    specs = tuple(
        replace(
            spec,
            relative_path=misplaced_path,
        )
        if spec.role is RuntimeComponentRole.REFERENCE_SOURCE else spec
        for spec in checked_in.component_specs
    )

    with pytest.raises(RuntimeBundleError, match="source path does not match"):
        RuntimeBundleBuilder(
            root,
            specs,
            checked_in.contract_schema_paths,
            require_profile_descriptor=True,
        ).build()


def test_catalog_retains_the_reviewed_executable_source_selection():
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    source_specs = {
        spec for spec in checked_in.component_specs
        if spec.role in {
            RuntimeComponentRole.VALIDATOR_SOURCE,
            RuntimeComponentRole.ADAPTER_SOURCE,
            RuntimeComponentRole.QUERY_OUTPUT_SOURCE,
        }
    }

    assert {
        (spec.role, spec.logical_ref, spec.relative_path)
        for spec in source_specs
    } == EXPECTED_EXECUTABLE_SOURCE_SELECTION
    assert all(
        spec.canonicalization is Canonicalization.EXACT_BYTES
        and spec.placement is ContentPlacement.GLOBAL
        for spec in source_specs
    )


@pytest.mark.parametrize(
    "role",
    (
        RuntimeComponentRole.VALIDATOR_SOURCE,
        RuntimeComponentRole.ADAPTER_SOURCE,
        RuntimeComponentRole.QUERY_OUTPUT_SOURCE,
    ),
)
def test_catalog_cannot_omit_selected_executable_source_role(role):
    checked_in = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT)
    specs = tuple(
        spec for spec in checked_in.component_specs
        if spec.role is not role
    )

    with pytest.raises(RuntimeBundleError, match="runtime source selection is incomplete"):
        _checked_builder_with_specs(specs).build()


def test_selected_adapter_byte_change_changes_bundle_identity(tmp_path):
    root = tmp_path / "relocated-release"
    _copy_checked_selection(root, include_catalog=True)
    original = RuntimeBundleBuilder.from_manifest(root).build()
    path = root / "kernel/adapters.py"
    path.write_bytes(path.read_bytes() + b"\n# changed selected runtime bytes\n")

    changed = RuntimeBundleBuilder.from_manifest(root).build()

    assert changed.digest != original.digest


def test_context_snapshot_cannot_name_an_unretained_reference(tmp_path):
    root = tmp_path / "checkout"
    checked_in = _copy_checked_selection(root)
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
        builder.build()


def test_checked_in_component_catalog_builds_the_reviewed_closed_set():
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()

    assert bundle.selected_tenant_ref == "tenant:si.ffs.pilot.demo"
    assert bundle.digest == (
        "sha256:e3022473ba97897ecc68bd8fb93a747aa3cc80149442e248e3e39f7b8b28268a"
    )

    expected_catalog_roles = {
        RuntimeComponentRole.ACTIVE_MANIFEST,
        RuntimeComponentRole.ADAPTER_SOURCE,
        RuntimeComponentRole.CONTRACT_SCHEMA,
        RuntimeComponentRole.DRAFT_CONTRACT_SCHEMA,
        RuntimeComponentRole.PROFILE_DESCRIPTOR,
        RuntimeComponentRole.PROFILE_INSTANCE,
        RuntimeComponentRole.PROFILE_POLICY,
        RuntimeComponentRole.QUERY_OUTPUT_SOURCE,
        RuntimeComponentRole.QUERY_PLAN,
        RuntimeComponentRole.QUERY_SPECIFICATION,
        RuntimeComponentRole.REFERENCE_SNAPSHOT,
        RuntimeComponentRole.REFERENCE_SOURCE,
        RuntimeComponentRole.VALIDATOR_SOURCE,
        RuntimeComponentRole.VIEW_BINDING,
    }

    assert len(bundle.components) == 95
    assert {component.role for component in bundle.components} == expected_catalog_roles
    assert set(RuntimeComponentRole) == expected_catalog_roles
    assert {
        component.logical_ref
        for component in bundle.components
        if component.role is RuntimeComponentRole.PROFILE_DESCRIPTOR
    } == {"profile:si.ffs.recordkeeping.v0_1"}
    assert all(
        "synthetic" not in component.logical_ref
        for component in bundle.components
    )
    identities = [
        (component.role.value, component.logical_ref)
        for component in bundle.components
    ]
    assert identities == sorted(identities)
    assert len(identities) == len(set(identities))
    retained_contract_refs = {
        component.logical_ref
        for component in bundle.components
        if component.role in {
            RuntimeComponentRole.CONTRACT_SCHEMA,
            RuntimeComponentRole.DRAFT_CONTRACT_SCHEMA,
        }
    }
    assert retained_contract_refs == {
        f"contract:{kind}" for kind in ContractRegistry().kinds()
    }


def test_contract_lane_changes_bundle_identity_for_identical_schema_bytes(tmp_path):
    schema = canonical_json_bytes({
        "type": "object",
        "properties": {
            "schemaVersion": {"const": "ofarm.test.registry-lane.v0.1"},
            "fixtureId": {"type": "string"},
        },
        "required": ["schemaVersion", "fixtureId"],
    })
    roots_and_paths = (
        (tmp_path / "canonical", "contracts/kernel/fixture.json"),
        (
            tmp_path / "draft",
            "contracts/drafts_reference/"
            "explainable_current_state_evidence/fixture.json",
        ),
    )
    bundles = []
    for root, relative_path in roots_and_paths:
        for directory in (
            "contracts/kernel", "contracts/core", "contracts/platform",
            "contracts/drafts_reference/explainable_current_state_evidence",
        ):
            (root / directory).mkdir(parents=True, exist_ok=True)
        _write(root, relative_path, schema)
        bundles.append(RuntimeBundleBuilder(
            root, (), (relative_path,)
        ).build())

    first_schema = next(component for component in bundles[0].components
                        if component.role is RuntimeComponentRole.CONTRACT_SCHEMA)
    second_schema = next(component for component in bundles[1].components
                         if component.role is RuntimeComponentRole.DRAFT_CONTRACT_SCHEMA)
    assert first_schema.logical_ref == second_schema.logical_ref
    assert first_schema.canonical_bytes == second_schema.canonical_bytes
    assert first_schema.content_digest == second_schema.content_digest
    assert first_schema.role is not second_schema.role
    assert bundles[0].digest != bundles[1].digest


def test_direct_bundle_refuses_same_contract_version_across_lanes():
    schema_version = "ofarm.test.direct-duplicate-lane.v0.1"
    schema = canonical_json_bytes({
        "properties": {
            "schemaVersion": {"const": schema_version},
        },
    })
    components = tuple(
        RuntimeComponent.from_selected_bytes(
            role=role,
            logical_ref=f"contract:{schema_version}",
            canonicalization=Canonicalization.EXACT_BYTES,
            placement=ContentPlacement.GLOBAL,
            selected_bytes=schema,
        )
        for role in (
            RuntimeComponentRole.CONTRACT_SCHEMA,
            RuntimeComponentRole.DRAFT_CONTRACT_SCHEMA,
        )
    )

    with pytest.raises(RuntimeBundleError, match="more than once across lanes"):
        RuntimeBundle.create(components)


def test_same_contract_schema_version_cannot_be_selected_from_both_lanes(tmp_path):
    root = tmp_path / "duplicate-lanes"
    canonical_path = "contracts/kernel/fixture.json"
    draft_path = (
        "contracts/drafts_reference/"
        "explainable_current_state_evidence/fixture.json"
    )
    for directory in (
        "contracts/kernel", "contracts/core", "contracts/platform",
        "contracts/drafts_reference/explainable_current_state_evidence",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)
    schema = canonical_json_bytes({
        "type": "object",
        "properties": {
            "schemaVersion": {"const": "ofarm.test.duplicate-lane.v0.1"},
        },
        "required": ["schemaVersion"],
    })
    _write(root, canonical_path, schema)
    _write(root, draft_path, schema)

    with pytest.raises(RuntimeBundleError, match="more than once across lanes"):
        RuntimeBundleBuilder(
            root, (), (canonical_path, draft_path)
        ).build()
