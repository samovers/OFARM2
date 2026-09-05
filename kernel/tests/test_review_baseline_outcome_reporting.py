"""Expected-failure outcome integration tests for review-baseline evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from conformance import run_review_baseline as baseline
from conformance.evidence_publication_policy import (
    PublicationPolicyError,
    _validate_test_results,
)


EXPECTED_FAILURE_SUITE = """\
import pytest


@pytest.mark.xfail(reason="", strict=False)
def test_xpass_empty_reason():
    assert True


@pytest.mark.xfail(strict=False)
def test_xpass_omitted_reason():
    assert True


@pytest.mark.xfail(reason="known defect", strict=False)
def test_xpass_nonempty_reason():
    assert True


@pytest.mark.xfail(reason="", strict=False)
def test_xfail_empty_reason():
    assert False


@pytest.mark.xfail(strict=False)
def test_xfail_omitted_reason():
    assert False


@pytest.mark.xfail(reason="known defect", strict=False)
def test_xfail_nonempty_reason():
    assert False


def test_ordinary_pass():
    assert True
"""

ORDINARY_PASS_SUITE = """\
def test_ordinary_pass():
    assert True
"""

STRICT_XPASS_SUITE = """\
import pytest


@pytest.mark.xfail(reason="", strict=True)
def test_strict_xpass():
    assert True
"""


def _run_child_suite(root: Path, source: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    root.mkdir()
    (root / "test_probe.py").write_text(source, encoding="utf-8")
    results_path = root / "results.json"
    env = os.environ.copy()
    for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONOPTIMIZE"):
        env.pop(key, None)
    env.update({
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": str(baseline.ROOT),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "test_probe.py",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "conformance.review_baseline_pytest",
            "--review-baseline-results",
            str(results_path),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert results_path.is_file(), process.stdout + process.stderr
    return process, json.loads(results_path.read_text(encoding="utf-8"))


def _matching_acceptance_inputs(results: dict) -> tuple[dict, dict]:
    inventory = baseline._inventory_document(
        ".", results["collection"]["collected"]
    )
    warning_policy = {"mode": "exact-inventory", "expected": []}
    assert baseline._test_inventory_check(
        inventory, results["collection"]["collected"]
    )["matches"] is True
    assert baseline._warning_policy_check(
        warning_policy, results["warnings"]
    )["matches"] is True
    return inventory, warning_policy


def test_expected_failure_reasons_preserve_xpass_and_xfail_classifications(
    tmp_path: Path,
):
    process, results = _run_child_suite(
        tmp_path / "expected-failures", EXPECTED_FAILURE_SUITE
    )

    assert process.returncode == 0, process.stdout + process.stderr
    assert results["collection"]["errors"] == []
    assert results["collection"]["deselected"] == []
    assert results["execution"]["skipped"] == []
    assert results["execution"]["unavailable"] == []
    assert results["warnings"] == []
    assert results["summary"] == {
        "collected": 7,
        "collectionErrors": 0,
        "collectionSkipped": 0,
        "deselected": 0,
        "error": 0,
        "failed": 0,
        "passed": 1,
        "pytestExitStatus": 0,
        "selected": 7,
        "skipped": 0,
        "unavailable": 0,
        "warnings": 0,
        "xfailed": 3,
        "xpassed": 3,
    }

    expected = {
        "test_xpass_empty_reason": ("xpassed", ""),
        "test_xpass_omitted_reason": ("xpassed", ""),
        "test_xpass_nonempty_reason": ("xpassed", "known defect"),
        "test_xfail_empty_reason": ("xfailed", ""),
        "test_xfail_omitted_reason": ("xfailed", ""),
        "test_xfail_nonempty_reason": ("xfailed", "known defect"),
    }
    outcomes = {
        outcome["nodeid"].rsplit("::", 1)[-1]: outcome
        for outcome in results["execution"]["outcomes"]
    }
    for test_name, (classification, reason) in expected.items():
        outcome = outcomes[test_name]
        call_phase = next(
            phase for phase in outcome["phases"] if phase["phase"] == "call"
        )
        assert outcome["outcome"] == classification
        assert call_phase["classification"] == classification
        assert "expectedFailure" in call_phase
        assert call_phase["expectedFailure"] == reason

    inventory, warning_policy = _matching_acceptance_inputs(results)
    assert baseline._test_result_is_complete(results) is False
    with pytest.raises(PublicationPolicyError, match="not one complete pass"):
        _validate_test_results(
            results,
            expected_inventory=inventory,
            warning_policy=warning_policy,
        )


def test_child_reporter_runs_are_deterministic_and_isolated(tmp_path: Path):
    first_process, first = _run_child_suite(
        tmp_path / "first", EXPECTED_FAILURE_SUITE
    )
    second_process, second = _run_child_suite(
        tmp_path / "second", EXPECTED_FAILURE_SUITE
    )
    pass_process, ordinary = _run_child_suite(
        tmp_path / "after-expected-failures", ORDINARY_PASS_SUITE
    )

    assert first_process.returncode == second_process.returncode == 0
    assert first == second
    assert pass_process.returncode == 0, pass_process.stdout + pass_process.stderr
    assert ordinary["summary"]["collected"] == 1
    assert ordinary["summary"]["passed"] == 1
    assert ordinary["summary"]["xfailed"] == 0
    assert ordinary["summary"]["xpassed"] == 0
    assert [
        outcome["nodeid"] for outcome in ordinary["execution"]["outcomes"]
    ] == ["test_probe.py::test_ordinary_pass"]


def test_ordinary_pass_is_accepted_by_existing_consumers(tmp_path: Path):
    process, results = _run_child_suite(tmp_path / "ordinary", ORDINARY_PASS_SUITE)

    assert process.returncode == 0, process.stdout + process.stderr
    inventory, warning_policy = _matching_acceptance_inputs(results)
    assert baseline._test_result_is_complete(results) is True
    inventory_check, warning_check = _validate_test_results(
        results,
        expected_inventory=inventory,
        warning_policy=warning_policy,
    )
    assert inventory_check["matches"] is True
    assert warning_check["matches"] is True


def test_strict_xpass_remains_failed_and_rejected(tmp_path: Path):
    process, results = _run_child_suite(tmp_path / "strict", STRICT_XPASS_SUITE)

    assert process.returncode == 1, process.stdout + process.stderr
    assert results["summary"]["failed"] == 1
    assert results["summary"]["xpassed"] == 0
    outcome = results["execution"]["outcomes"][0]
    assert outcome["outcome"] == "failed"
    call_phase = next(
        phase for phase in outcome["phases"] if phase["phase"] == "call"
    )
    assert call_phase == {"phase": "call", "outcome": "failed"}

    inventory, warning_policy = _matching_acceptance_inputs(results)
    assert baseline._test_result_is_complete(results) is False
    with pytest.raises(PublicationPolicyError, match="not one complete pass"):
        _validate_test_results(
            results,
            expected_inventory=inventory,
            warning_policy=warning_policy,
        )
