"""Regression tests for the profile test-harness bridge."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from kernel.tests.profile_harness_bridge import (
    DEFAULT_DESCRIPTOR,
    ProfileHarnessBridgeError,
    discover_profile_harness_descriptors,
    iter_profile_test_modules,
    load_profile_harness_descriptor,
)


EXPECTED_PROFILE_MODULES = (
    "profile_si_ffs.tests.m2_si_regsr_tests",
    "profile_si_ffs.tests.m2_si_gerk_tests",
    "profile_si_ffs.tests.m2_si_ffsnaprave_tests",
    "profile_si_ffs.tests.m2_si_floor_tests",
    "profile_si_ffs.tests.m2_si_validation_policy_tests",
    "profile_si_ffs.tests.m2_si_binding_wrapper_tests",
    "profile_si_ffs.tests.m2_si_output_lock_tests",
    "profile_si_ffs.tests.d2_demo_fixture_refs_tests",
    "profile_si_ffs.tests.d2_demo_fixture_records_tests",
    "profile_si_ffs.tests.d2_demo_fixture_payloads_tests",
)
ROOT_TESTS_DIR = Path(__file__).resolve().parent


def _descriptor_doc() -> dict:
    return json.loads(DEFAULT_DESCRIPTOR.read_text(encoding="utf-8"))


def _write_descriptor(
    tmp_path,
    doc: dict,
    *,
    profile_package: str = "profile_si_ffs",
    file_name: str = "profile_test_harness.json",
):
    root = tmp_path / "package_root"
    path = root / profile_package / "tests" / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return root, path


def _root_star_import_bridges() -> dict[str, list[str]]:
    bridges: dict[str, list[str]] = {}
    for test_file in ROOT_TESTS_DIR.glob("test_*.py"):
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            parts = node.module.split(".")
            if len(parts) < 3 or not parts[0].startswith("profile_") \
                    or parts[1] != "tests":
                continue
            if not any(alias.name == "*" for alias in node.names):
                continue
            bridges.setdefault(node.module, []).append(test_file.name)
    return bridges


def test_profile_harness_discovery_finds_current_si_harness_only():
    harnesses = discover_profile_harness_descriptors()

    assert [harness.profile_package for harness in harnesses] == [
        "profile_si_ffs"]
    assert harnesses[0].descriptor_path == DEFAULT_DESCRIPTOR.resolve()


def test_profile_harness_discovery_omits_descriptorless_profile_packages(tmp_path):
    root = tmp_path / "package_root"
    root.mkdir()
    (root / "profile_nl_go_glmc7_2026").mkdir()
    (root / "profile_si_ffs").mkdir()

    assert discover_profile_harness_descriptors(root) == ()


def test_profile_harness_descriptor_loads_with_strict_shape():
    harness = load_profile_harness_descriptor()

    assert harness.profile_package == "profile_si_ffs"
    assert harness.test_modules == EXPECTED_PROFILE_MODULES


def test_profile_harness_declared_modules_import():
    module_names = [module.__name__ for module in iter_profile_test_modules()]

    assert module_names == list(EXPECTED_PROFILE_MODULES)


def test_profile_harness_declared_modules_have_root_collection_bridges():
    harness = load_profile_harness_descriptor()
    bridges = _root_star_import_bridges()

    missing = [
        module_name for module_name in harness.test_modules
        if module_name not in bridges
    ]

    assert not missing, (
        "descriptor module(s) missing root collection bridge: " +
        ", ".join(missing)
    )


def test_root_bridge_detection_requires_top_level_star_import(monkeypatch, tmp_path):
    nested = tmp_path / "test_nested.py"
    nested.write_text(
        "if False:\n"
        "    from profile_si_ffs.tests.m2_si_regsr_tests import *\n",
        encoding="utf-8",
    )
    top_level = tmp_path / "test_top_level.py"
    top_level.write_text(
        "from profile_si_ffs.tests.m2_si_floor_tests import *\n",
        encoding="utf-8",
    )
    other_profile = tmp_path / "test_other_profile.py"
    other_profile.write_text(
        "from profile_second.tests.some_profile_tests import *\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(globals(), "ROOT_TESTS_DIR", tmp_path)

    assert _root_star_import_bridges() == {
        "profile_second.tests.some_profile_tests": ["test_other_profile.py"],
        "profile_si_ffs.tests.m2_si_floor_tests": ["test_top_level.py"],
    }


def test_synthetic_profile_harness_validates_with_matching_package_prefix(tmp_path):
    doc = _descriptor_doc()
    doc["profilePackage"] = "profile_second"
    doc["testModules"] = [
        "profile_second.tests.alpha_tests",
        "profile_second.tests.beta_tests",
    ]
    root, path = _write_descriptor(
        tmp_path,
        doc,
        profile_package="profile_second",
    )

    harness = load_profile_harness_descriptor(path, package_root=root)

    assert harness.profile_package == "profile_second"
    assert harness.test_modules == tuple(doc["testModules"])


def test_profile_harness_descriptor_rejects_wrong_schema_version(tmp_path):
    doc = _descriptor_doc()
    doc["schemaVersion"] = "profile_test_harness_v9_9"
    root, path = _write_descriptor(tmp_path, doc)

    with pytest.raises(ProfileHarnessBridgeError, match="schemaVersion"):
        load_profile_harness_descriptor(path, package_root=root)


def test_profile_harness_descriptor_rejects_wrong_root_bridge(tmp_path):
    doc = _descriptor_doc()
    doc["rootBridge"] = "profile_si_ffs/tests/conftest.py"
    root, path = _write_descriptor(tmp_path, doc)

    with pytest.raises(ProfileHarnessBridgeError, match="rootBridge"):
        load_profile_harness_descriptor(path, package_root=root)


def test_profile_harness_descriptor_rejects_unknown_top_level_key(tmp_path):
    doc = _descriptor_doc()
    doc["silentEvidenceMode"] = True
    root, path = _write_descriptor(tmp_path, doc)

    with pytest.raises(ProfileHarnessBridgeError, match="unknown top-level"):
        load_profile_harness_descriptor(path, package_root=root)


def test_profile_harness_descriptor_rejects_profile_package_mismatch(tmp_path):
    doc = _descriptor_doc()
    doc["profilePackage"] = "profile_other"
    root, path = _write_descriptor(tmp_path, doc, profile_package="profile_si_ffs")

    with pytest.raises(ProfileHarnessBridgeError, match="profilePackage"):
        load_profile_harness_descriptor(path, package_root=root)


def test_profile_harness_descriptor_rejects_wrong_file_name(tmp_path):
    doc = _descriptor_doc()
    root, path = _write_descriptor(tmp_path, doc, file_name="not_the_harness.json")

    with pytest.raises(ProfileHarnessBridgeError, match="file name"):
        load_profile_harness_descriptor(path, package_root=root)


def test_profile_harness_descriptor_rejects_non_immediate_profile_path(tmp_path):
    doc = _descriptor_doc()
    root = tmp_path / "package_root"
    path = root / "nested" / "profile_si_ffs" / "tests" / "profile_test_harness.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")

    with pytest.raises(ProfileHarnessBridgeError, match="immediate child"):
        load_profile_harness_descriptor(path, package_root=root)


def test_profile_harness_descriptor_rejects_symlink_escape(tmp_path):
    doc = _descriptor_doc()
    root = tmp_path / "package_root"
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_descriptor = outside / "profile_test_harness.json"
    outside_descriptor.write_text(json.dumps(doc), encoding="utf-8")
    link = root / "profile_si_ffs" / "tests" / "profile_test_harness.json"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside_descriptor)

    with pytest.raises(ProfileHarnessBridgeError, match="escapes"):
        load_profile_harness_descriptor(link, package_root=root)


def test_profile_harness_discovery_rejects_broken_symlink_descriptor(tmp_path):
    root = tmp_path / "package_root"
    link = root / "profile_si_ffs" / "tests" / "profile_test_harness.json"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(tmp_path / "missing_profile_test_harness.json")

    with pytest.raises(ProfileHarnessBridgeError, match="unavailable"):
        discover_profile_harness_descriptors(root)


def test_profile_harness_discovery_rejects_malformed_descriptor_json(tmp_path):
    root = tmp_path / "package_root"
    path = root / "profile_bad" / "tests" / "profile_test_harness.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ProfileHarnessBridgeError, match="unreadable"):
        discover_profile_harness_descriptors(root)


@pytest.mark.parametrize("field,value,match", [
    ("engineeringTestsOnly", False, "engineeringTestsOnly"),
    ("platformConformance", True, "platformConformance"),
    ("executedEvidence", True, "executedEvidence"),
    ("evidenceWriter", "profile-writer", "evidenceWriter"),
])
def test_profile_harness_descriptor_rejects_evidence_or_conformance_claims(
        tmp_path, field, value, match):
    doc = _descriptor_doc()
    doc[field] = value
    root, path = _write_descriptor(tmp_path, doc)

    with pytest.raises(ProfileHarnessBridgeError, match=match):
        load_profile_harness_descriptor(path, package_root=root)


def test_profile_harness_descriptor_rejects_duplicate_modules(tmp_path):
    doc = _descriptor_doc()
    doc["testModules"] = [
        "profile_si_ffs.tests.m2_si_floor_tests",
        "profile_si_ffs.tests.m2_si_floor_tests",
    ]
    root, path = _write_descriptor(tmp_path, doc)

    with pytest.raises(ProfileHarnessBridgeError, match="duplicate test module"):
        load_profile_harness_descriptor(path, package_root=root)


def test_profile_harness_discovery_rejects_duplicate_modules_across_descriptors(
        tmp_path):
    root = tmp_path / "package_root"
    doc = _descriptor_doc()
    doc["profilePackage"] = "profile_first"
    doc["testModules"] = ["profile_first.tests.shared_tests"]
    first_path = root / "profile_first" / "tests" / "profile_test_harness.json"
    first_path.parent.mkdir(parents=True, exist_ok=True)
    first_path.write_text(json.dumps(doc), encoding="utf-8")
    (root / "profile_second").symlink_to(root / "profile_first")

    with pytest.raises(ProfileHarnessBridgeError, match="duplicate test module"):
        discover_profile_harness_descriptors(root)
