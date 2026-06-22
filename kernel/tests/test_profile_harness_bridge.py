"""Regression tests for the profile test-harness bridge."""
from __future__ import annotations

import json

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
)


def _descriptor_doc() -> dict:
    return json.loads(DEFAULT_DESCRIPTOR.read_text(encoding="utf-8"))


def _write_descriptor(tmp_path, doc: dict):
    path = tmp_path / "profile_test_harness.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_profile_harness_descriptor_loads_with_strict_shape():
    harness = load_profile_harness_descriptor()

    assert harness.profile_package == "profile_si_ffs"
    assert harness.test_modules == EXPECTED_PROFILE_MODULES


def test_profile_harness_declared_modules_import():
    module_names = [module.__name__ for module in iter_profile_test_modules()]

    assert module_names == list(EXPECTED_PROFILE_MODULES)


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
