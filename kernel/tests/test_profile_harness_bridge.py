"""Regression tests for the profile test-harness bridge."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from kernel.tests.profile_harness_bridge import (
    DEFAULT_DESCRIPTOR,
    ProfileHarnessBridgeError,
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


def _write_descriptor(tmp_path, doc: dict):
    path = tmp_path / "profile_test_harness.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _root_star_import_bridges() -> dict[str, list[str]]:
    bridges: dict[str, list[str]] = {}
    for test_file in ROOT_TESTS_DIR.glob("test_*.py"):
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if not node.module.startswith("profile_si_ffs.tests."):
                continue
            if not any(alias.name == "*" for alias in node.names):
                continue
            bridges.setdefault(node.module, []).append(test_file.name)
    return bridges


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


def test_profile_harness_descriptor_rejects_wrong_schema_version(tmp_path):
    doc = _descriptor_doc()
    doc["schemaVersion"] = "profile_test_harness_v9_9"

    with pytest.raises(ProfileHarnessBridgeError, match="schemaVersion"):
        load_profile_harness_descriptor(_write_descriptor(tmp_path, doc))


def test_profile_harness_descriptor_rejects_wrong_root_bridge(tmp_path):
    doc = _descriptor_doc()
    doc["rootBridge"] = "profile_si_ffs/tests/conftest.py"

    with pytest.raises(ProfileHarnessBridgeError, match="rootBridge"):
        load_profile_harness_descriptor(_write_descriptor(tmp_path, doc))


def test_profile_harness_descriptor_rejects_unknown_top_level_key(tmp_path):
    doc = _descriptor_doc()
    doc["silentEvidenceMode"] = True

    with pytest.raises(ProfileHarnessBridgeError, match="unknown top-level"):
        load_profile_harness_descriptor(_write_descriptor(tmp_path, doc))
