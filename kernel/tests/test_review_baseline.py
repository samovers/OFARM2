"""Tooling-only tests for the deterministic review baseline (issue #168)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from conformance import review_baseline_pytest as plugin
from conformance import run_review_baseline as baseline
from profile_si_ffs.tests import m2_si_floor_tests


def _evidence(*, clean=True, started="2026-07-10T00:00:00Z", outcome="passed"):
    return {
        "schemaVersion": baseline.EVIDENCE_SCHEMA,
        "normalizationPolicy": baseline._normalization_policy(),
        "run": {"startedAt": started, "finishedAt": started, "outcome": outcome},
        "git": {"dirty": not clean, "sha": "abc"},
        "environment": {"ci": {"runId": "1", "runAttempt": "1"}},
        "tests": {"summary": {"passed": 1}},
    }


def _write(path: Path, payload: dict):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_hashed_lock_contains_the_exact_observed_distribution_set():
    lock = baseline.ROOT / "requirements-review-baseline.lock"
    packages = baseline._parse_lock(lock)
    text = lock.read_text(encoding="utf-8")

    assert len(packages) == 30
    assert packages["fastapi"] == "0.138.0"
    assert packages["pytest"] == "9.1.1"
    assert packages["psycopg-binary"] == "3.3.4"
    assert text.count("--hash=sha256:") == 30

    pip_lock = baseline.ROOT / "requirements-review-pip.lock"
    assert baseline._parse_lock(pip_lock) == {"pip": "26.1"}
    assert pip_lock.read_text(encoding="utf-8").count("--hash=sha256:") == 1


def test_authoritative_target_requires_linux_x86_64_cpython():
    config = baseline._read_json(baseline.CONFIG_PATH)
    required = config["requiredEnvironment"]

    assert required["operatingSystem"] == "Linux"
    assert required["machine"] == "x86_64"
    assert required["pythonImplementation"] == "CPython"


def test_sanitized_environment_removes_ambient_test_and_ofarm_controls(monkeypatch):
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k hidden")
    monkeypatch.setenv("PYTEST_PLUGINS", "ambient.plugin")
    monkeypatch.setenv("PYTHONPATH", "/ambient")
    monkeypatch.setenv("OFARM_ACTIVE_PROFILE", "profile_bad")
    monkeypatch.setenv("OFARM_PG_DSN", "dbname=test")
    config = baseline._read_json(baseline.CONFIG_PATH)

    env = baseline._sanitized_environment(config)

    assert "PYTEST_ADDOPTS" not in env
    assert "PYTEST_PLUGINS" not in env
    assert "PYTHONPATH" not in env
    assert "OFARM_ACTIVE_PROFILE" not in env
    assert env["OFARM_PG_DSN"] == "dbname=test"
    assert env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert env["PYTHONHASHSEED"] == "0"


def test_profile_bridge_inventory_preserves_original_callable_source():
    item = SimpleNamespace(
        nodeid="kernel/tests/test_m2_si_floor.py::test_floor_is_sourced_from_package_content",
        obj=m2_si_floor_tests.test_floor_is_sourced_from_package_content,
        config=SimpleNamespace(rootpath=baseline.ROOT),
        module=None,
    )

    entry = plugin._entry(item)

    assert entry["sourceModule"] == "profile_si_ffs.tests.m2_si_floor_tests"
    assert entry["sourcePath"] == "profile_si_ffs/tests/m2_si_floor_tests.py"


@pytest.mark.parametrize(("phases", "expected"), [
    ([{"phase": "call", "outcome": "failed"}], "failed"),
    ([{"phase": "setup", "outcome": "failed"}], "error"),
    ([{"phase": "teardown", "outcome": "failed"}], "error"),
    ([{"phase": "call", "outcome": "skipped", "classification": "xfailed"}],
     "xfailed"),
    ([{"phase": "call", "outcome": "passed", "classification": "xpassed"}],
     "xpassed"),
    ([{"phase": "call", "outcome": "skipped"}], "skipped"),
    ([{"phase": "call", "outcome": "passed"}], "passed"),
    ([], "unavailable"),
])
def test_plugin_terminal_outcomes_are_not_collapsed(phases, expected):
    assert plugin._terminal_outcome(phases) == expected


def test_normalization_changes_only_the_fixed_volatile_fields():
    left = _evidence(started="2026-07-10T00:00:00Z")
    right = _evidence(started="2026-07-10T00:00:01Z")
    right["environment"]["ci"]["runId"] = "2"
    right["environment"]["ci"]["runAttempt"] = "2"

    assert baseline._normalised_evidence(left) == baseline._normalised_evidence(right)

    right["tests"]["summary"]["passed"] = 0
    assert baseline._normalised_evidence(left) != baseline._normalised_evidence(right)


def test_normalization_rejects_a_broadened_policy():
    evidence = _evidence()
    evidence["normalizationPolicy"]["volatileJsonPointers"].append("/tests")

    with pytest.raises(ValueError, match="fixed v1 policy"):
        baseline._normalised_evidence(evidence)


def test_normalization_refuses_when_a_required_volatile_field_is_missing():
    evidence = _evidence()
    del evidence["run"]["startedAt"]

    with pytest.raises(ValueError, match="normalization pointer missing"):
        baseline._normalised_evidence(evidence)


def test_compare_proves_clean_equivalence_and_records_raw_digests(tmp_path):
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    proof = tmp_path / "proof.json"
    _write(left, _evidence(started="2026-07-10T00:00:00Z"))
    _write(right, _evidence(started="2026-07-10T00:00:01Z"))

    assert baseline.compare_evidence(str(left), str(right), str(proof)) == 0
    result = json.loads(proof.read_text(encoding="utf-8"))
    assert result["equivalent"] is True
    assert result["left"]["rawSha256"] != result["right"]["rawSha256"]
    assert result["left"]["normalizedSha256"] == result["right"]["normalizedSha256"]


def test_compare_fails_on_nonvolatile_drift(tmp_path):
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    proof = tmp_path / "proof.json"
    left_payload = _evidence()
    right_payload = _evidence()
    right_payload["tests"]["summary"]["passed"] = 0
    _write(left, left_payload)
    _write(right, right_payload)

    assert baseline.compare_evidence(str(left), str(right), str(proof)) == 1
    result = json.loads(proof.read_text(encoding="utf-8"))
    assert result["equivalent"] is False
    assert result["differenceJsonPointers"] == ["/tests/summary/passed"]


def test_compare_refuses_dirty_evidence(tmp_path):
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    _write(left, _evidence(clean=False))
    _write(right, _evidence())

    with pytest.raises(ValueError, match="not from a clean worktree"):
        baseline.compare_evidence(str(left), str(right), str(tmp_path / "proof.json"))
