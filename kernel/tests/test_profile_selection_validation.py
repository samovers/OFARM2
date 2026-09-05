"""Focused tests for pure profile-selection validation."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from kernel.profile_runtime import (
    ProfileRuntimeError,
    ReferenceFamily,
    load_profile_runtime_descriptor,
    validate_profile_runtime_selection_documents,
)
from kernel.profile_selection_validation import (
    ProfileSelectionValidationError,
    validate_profile_descriptor_document,
    validate_profile_selection_documents,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PROFILE_ROOT = PACKAGE_ROOT / "profile_si_ffs"


def _selection_documents():
    descriptor = json.loads(
        (PROFILE_ROOT / "runtime_profile_descriptor.json").read_text()
    )
    payloads = [
        json.loads((PROFILE_ROOT / relative).read_text())
        for relative in descriptor["profileInstanceFiles"]
    ]
    return descriptor, payloads


def _payload(payloads, field, expected):
    return next(payload for payload in payloads if payload.get(field) == expected)


def test_validated_descriptor_is_deterministic_immutable_and_non_mutating():
    descriptor, _payloads = _selection_documents()
    before = copy.deepcopy(descriptor)

    first = validate_profile_descriptor_document(descriptor)
    second = validate_profile_descriptor_document(descriptor)

    assert first == second
    assert first.profile_instance_files == tuple(descriptor["profileInstanceFiles"])
    assert type(first.profile_instance_files) is tuple
    assert type(first.reference_families) is tuple
    assert not hasattr(first, "__dict__")
    assert not hasattr(first.reference_families[0], "__dict__")
    with pytest.raises(FrozenInstanceError):
        first.profile_instance_files = ()
    with pytest.raises(FrozenInstanceError):
        first.reference_families[0].family_id = "changed"
    assert descriptor == before


def test_selection_validation_does_not_mutate_inputs():
    descriptor, payloads = _selection_documents()
    before = copy.deepcopy((descriptor, payloads))

    validate_profile_selection_documents(descriptor, payloads)

    assert (descriptor, payloads) == before


@pytest.mark.parametrize(
    ("case", "message"),
    (
        ("descriptor-not-object", "must be a JSON object"),
        ("unknown-field", "unknown field"),
        ("bad-ref", "profileRef"),
        ("duplicate-file", "duplicate entries"),
        ("duplicate-family", "duplicate reference family"),
        ("active-spine", "exactly one active pack"),
        ("profile-scope", "profileScope.packRefs"),
        ("shipped-ref", "is not in profileInstanceFiles"),
        ("non-object-instance", "must be JSON objects"),
    ),
)
def test_pure_and_compatibility_entry_points_refuse_identically(case, message):
    descriptor, payloads = _selection_documents()
    if case == "descriptor-not-object":
        descriptor = []
    elif case == "unknown-field":
        descriptor["unexpected"] = True
    elif case == "bad-ref":
        descriptor["profileRef"] = "not a ref"
    elif case == "duplicate-file":
        descriptor["profileInstanceFiles"].append(
            descriptor["profileInstanceFiles"][0]
        )
    elif case == "duplicate-family":
        descriptor["referenceFamilies"].append(
            copy.deepcopy(descriptor["referenceFamilies"][0])
        )
    elif case == "active-spine":
        activation = _payload(
            payloads,
            "packActivationSetId",
            descriptor["packActivationSetRef"],
        )
        activation["activePackRefs"] = ["pack:wrong.v0_1"]
    elif case == "profile-scope":
        profile = _payload(
            payloads,
            "agronomicCodeBindingProfileId",
            descriptor["codeBindingProfileRef"],
        )
        profile["profileScope"]["packRefs"] = ["pack:wrong.v0_1"]
    elif case == "shipped-ref":
        shipped = descriptor["referenceFamilies"][0]["shippedSnapshotRef"]
        payloads = [
            payload for payload in payloads
            if payload.get("referenceSnapshotId") != shipped
        ]
    elif case == "non-object-instance":
        payloads[0] = []
    else:  # pragma: no cover - the parameter table is closed
        raise AssertionError(case)

    with pytest.raises(ProfileSelectionValidationError, match=message) as pure:
        validate_profile_selection_documents(
            copy.deepcopy(descriptor), copy.deepcopy(payloads)
        )
    with pytest.raises(ProfileRuntimeError, match=message) as compatibility:
        validate_profile_runtime_selection_documents(
            copy.deepcopy(descriptor), copy.deepcopy(payloads)
        )

    assert type(compatibility.value) is ProfileRuntimeError
    assert str(compatibility.value) == str(pure.value)


def test_profile_loader_retains_public_reference_family_identity():
    descriptor_document, _payloads = _selection_documents()
    validated = validate_profile_descriptor_document(descriptor_document)
    descriptor = load_profile_runtime_descriptor(PROFILE_ROOT)

    assert descriptor.profile_instance_files == validated.profile_instance_files
    assert all(type(family) is ReferenceFamily for family in descriptor.reference_families)
    assert [family.family_id for family in descriptor.reference_families] == [
        family.family_id for family in validated.reference_families
    ]


def test_complete_bundle_builds_when_runtime_profile_modules_are_refused():
    script = """
import builtins
import importlib.util
import json
import sys

blocked = {
    "kernel.config",
    "kernel.profile_policy",
    "kernel.profile_runtime",
}
original_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    package = globals.get("__package__") if globals else None
    resolved = importlib.util.resolve_name("." * level + name, package) if level else name
    candidates = {resolved}
    candidates.update(f"{resolved}.{member}" for member in (fromlist or ()) if member != "*")
    if candidates & blocked:
        raise AssertionError(f"forbidden import attempted: {sorted(candidates & blocked)}")
    return original_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import
from kernel.runtime_bundle import RuntimeBundleBuilder
from pathlib import Path

bundle = RuntimeBundleBuilder.from_manifest(Path.cwd()).build()
assert not blocked & set(sys.modules)
print(json.dumps({
    "components": len(bundle.components),
    "digest": bundle.digest,
    "tenant": bundle.selected_tenant_ref,
}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PACKAGE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "components": 95,
        "digest": (
            "sha256:8816a0097d230cf7d165aca2ea54faca8f41794131be35a17363630f959f497f"
        ),
        "tenant": "tenant:si.ffs.pilot.demo",
    }
