"""Tooling-only tests for the deterministic review baseline (issue #168)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from conformance import review_baseline_pytest as plugin
from conformance import run_review_baseline as baseline
from profile_si_ffs.tests import m2_si_floor_tests


def _evidence(*, clean=True, started="2026-07-10T00:00:00Z", outcome="passed"):
    git_state = {
        "dirty": not clean,
        "dirtyEntryCount": 0 if clean else 1,
        "sha": "abc",
        "treeSha": "tree",
        "statusDigest": "clean" if clean else "dirty",
    }
    return {
        "schemaVersion": baseline.EVIDENCE_SCHEMA,
        "normalizationPolicy": baseline._normalization_policy(),
        "run": {"startedAt": started, "finishedAt": started, "outcome": outcome},
        "git": {
            "start": dict(git_state),
            "end": dict(git_state),
            "unchanged": True,
        },
        "environment": {"ci": {"runId": "1", "runAttempt": "1"}},
        "tests": {"summary": {"passed": 1}},
    }


def _write(path: Path, payload: dict):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_hashed_lock_contains_the_exact_observed_distribution_set():
    lock = baseline.ROOT / "requirements-review-baseline.lock"
    packages = baseline._parse_lock(lock)
    text = lock.read_text(encoding="utf-8")

    assert len(packages) == 49
    assert packages["fastapi"] == "0.138.0"
    assert packages["pyjwt"] == "2.13.0"
    assert packages["cryptography"] == "49.0.0"
    assert packages["google-cloud-kms"] == "3.16.0"
    assert packages["pytest"] == "9.1.1"
    assert packages["psycopg-binary"] == "3.3.4"
    assert packages["psycopg-pool"] == "3.3.1"
    assert text.count("--hash=sha256:") == 49

    pip_lock = baseline.ROOT / "requirements-review-pip.lock"
    assert baseline._parse_lock(pip_lock) == {"pip": "26.1"}
    assert pip_lock.read_text(encoding="utf-8").count("--hash=sha256:") == 1


def test_authoritative_target_requires_linux_x86_64_cpython():
    config = baseline._read_json(baseline.CONFIG_PATH)
    required = config["requiredEnvironment"]

    assert required["operatingSystem"] == "Linux"
    assert required["machine"] == "x86_64"
    assert required["pythonImplementation"] == "CPython"
    assert required["pythonOptimizationLevel"] == 0
    assert required["testDatabaseName"] == "ofarm_kernel_test"


def test_dirty_or_missing_git_state_fails_preflight():
    assert baseline._git_integrity_reasons({"dirty": False}) == []
    assert baseline._git_integrity_reasons({"dirty": True}) == [
        "Git worktree is dirty before execution"
    ]
    assert baseline._git_integrity_reasons({}) == [
        "Git worktree is dirty before execution"
    ]


def test_sanitized_environment_removes_ambient_test_and_ofarm_controls(monkeypatch):
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k hidden")
    monkeypatch.setenv("PYTEST_PLUGINS", "ambient.plugin")
    monkeypatch.setenv("PYTHONOPTIMIZE", "2")
    monkeypatch.setenv("PYTHONPATH", "/ambient")
    monkeypatch.setenv("OFARM_ACTIVE_PROFILE", "profile_bad")
    monkeypatch.setenv("OFARM_PG_DSN", "host=wrong.example dbname=wrong")
    admin_dsn = "host=localhost port=5432 dbname=postgres user=ofarm password=ofarm"
    audit_admin_dsn = (
        "host=localhost port=5433 dbname=postgres "
        "user=ofarm password=audit-ofarm"
    )
    tenant_provisioning_admin_dsn = (
        "host=localhost port=5434 dbname=postgres "
        "user=ofarm password=tenant-ofarm"
    )
    monkeypatch.setenv("OFARM_PG_ADMIN_DSN", admin_dsn)
    monkeypatch.setenv("OFARM_SECURITY_AUDIT_PG_ADMIN_DSN", audit_admin_dsn)
    monkeypatch.setenv(
        "OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN",
        tenant_provisioning_admin_dsn,
    )
    config = baseline._read_json(baseline.CONFIG_PATH)

    env = baseline._sanitized_environment(config)

    assert "PYTEST_ADDOPTS" not in env
    assert "PYTEST_PLUGINS" not in env
    assert "PYTHONOPTIMIZE" not in env
    assert "PYTHONPATH" not in env
    assert "OFARM_ACTIVE_PROFILE" not in env
    assert env["OFARM_PG_ADMIN_DSN"] == admin_dsn
    assert env["OFARM_SECURITY_AUDIT_PG_ADMIN_DSN"] == audit_admin_dsn
    assert env["OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN"] == \
        tenant_provisioning_admin_dsn
    assert env["OFARM_PG_DSN"] == baseline._derive_test_dsn(
        admin_dsn, "ofarm_kernel_test")
    assert "wrong.example" not in env["OFARM_PG_DSN"]
    assert env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert env["PYTHONHASHSEED"] == "0"


def test_provisioning_services_require_distinct_postgresql_system_identifiers():
    primary = {
        "available": True,
        "version": "17.10",
        "rawVersion": "17.10 (Debian 17.10-1.pgdg13+1)",
        "systemIdentifier": "100",
        "database": "postgres",
    }
    tenant = dict(primary, systemIdentifier="200")
    audit = dict(primary, systemIdentifier="300")

    assert baseline._provisioning_system_identifier_separation_reasons(
        primary, tenant, audit
    ) == []
    assert baseline._provisioning_system_identifier_separation_reasons(
        primary, tenant, tenant
    ) == [
        "primary, tenant, and audit PostgreSQL system identifiers are not distinct"
    ]
    assert baseline._provisioning_system_identifier_separation_reasons(
        primary, tenant, dict(audit, rawVersion="17.10 other build")
    ) == ["primary, tenant, and audit PostgreSQL build versions differ"]


def test_malformed_admin_dsn_emits_unavailable_evidence(tmp_path):
    output = tmp_path / "malformed-admin-dsn"
    env = dict(os.environ)
    env["OFARM_PG_ADMIN_DSN"] = "not a valid conninfo='"
    env.pop("OFARM_PG_DSN", None)

    proc = subprocess.run(
        [
            sys.executable,
            "conformance/run_review_baseline.py",
            "run",
            "--output-dir",
            str(output),
        ],
        cwd=baseline.ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    evidence = json.loads(
        (output / "review-baseline-evidence.json").read_text(encoding="utf-8")
    )
    assert evidence["run"]["outcome"] == "failed"
    postgres = evidence["environment"]["postgresql"]
    assert postgres["admin"]["available"] is False
    assert postgres["testStore"]["available"] is False
    assert isinstance(postgres["tenantAuditSystemIdentifiersDistinct"], bool)
    assert postgres["testAndProvisioningSystemIdentifiersPairwiseDistinct"] is False
    assert all("Lineage" not in key for key in postgres)
    preflight = next(
        step for step in evidence["steps"]
        if step["name"] == "environment-preflight"
    )
    assert "derived test-store database route is absent" in preflight["reason"]


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

    with pytest.raises(ValueError, match="fixed policy"):
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


def test_compare_refuses_changed_post_run_git_state(tmp_path):
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    changed = _evidence()
    changed["git"]["end"]["treeSha"] = "changed-tree"
    changed["git"]["unchanged"] = True  # comparator must not trust this claim
    _write(left, changed)
    _write(right, _evidence())

    with pytest.raises(ValueError, match="not from a clean worktree"):
        baseline.compare_evidence(str(left), str(right), str(tmp_path / "proof.json"))


def test_optimized_invoker_is_rejected_and_child_assertions_remain_enabled():
    probe = r"""
import json
import subprocess
import sys
from conformance import run_review_baseline as baseline
config = baseline._read_json(baseline.CONFIG_PATH)
child_env = baseline._sanitized_environment(config)
child = subprocess.run(
    [sys.executable, "-c", "import sys; print(sys.flags.optimize); assert False"],
    env=child_env,
    capture_output=True,
    text=True,
)
print(json.dumps({
    "outerLevel": sys.flags.optimize,
    "preflightReasons": baseline._python_optimization_reasons(0),
    "pythonOptimizeScrubbed": "PYTHONOPTIMIZE" not in child_env,
    "childLevel": child.stdout.strip(),
    "childExitCode": child.returncode,
}))
"""
    env = dict(os.environ)
    env["PYTHONOPTIMIZE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=baseline.ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(proc.stdout)
    assert result == {
        "outerLevel": 1,
        "preflightReasons": ["Python optimization level 1 != 0"],
        "pythonOptimizeScrubbed": True,
        "childLevel": "0",
        "childExitCode": 1,
    }


def test_warning_policy_is_exact_and_multiplicity_sensitive():
    config = baseline._read_json(baseline.CONFIG_PATH)
    policy = config["warningPolicy"]
    expected = policy["expected"]

    assert baseline._warning_policy_check(policy, expected)["matches"] is True
    assert baseline._warning_policy_check(policy, [])["matches"] is False
    assert baseline._warning_policy_check(
        policy, expected + expected)["matches"] is False
    changed = [dict(expected[0], message="different warning")]
    assert baseline._warning_policy_check(policy, changed)["matches"] is False


def test_plugin_preserves_duplicate_warning_occurrences(tmp_path):
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "test_warnings.py").write_text(
        "import warnings\n"
        "def test_duplicate_warnings():\n"
        "    warnings.simplefilter('always')\n"
        "    warnings.warn('duplicate warning', UserWarning)\n"
        "    warnings.warn('duplicate warning', UserWarning)\n",
        encoding="utf-8",
    )
    results_path = tmp_path / "results.json"
    env = dict(os.environ)
    env.update({
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    env.pop("PYTHONOPTIMIZE", None)
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest", str(suite), "-q",
            "-p", "no:cacheprovider",
            "-p", "conformance.review_baseline_pytest",
            "--review-baseline-results", str(results_path),
        ],
        cwd=baseline.ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    results = json.loads(results_path.read_text(encoding="utf-8"))
    assert results["summary"]["warnings"] == 2
    assert results["warnings"][0] == results["warnings"][1]


def test_module_level_skip_is_recorded_and_fails_completeness(tmp_path):
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "test_pass.py").write_text(
        "def test_pass():\n    assert True\n", encoding="utf-8")
    (suite / "test_module_skip.py").write_text(
        "import pytest\n"
        "pytest.skip('fixture module unavailable', allow_module_level=True)\n",
        encoding="utf-8",
    )
    results_path = tmp_path / "results.json"
    env = dict(os.environ)
    env.update({
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    env.pop("PYTHONOPTIMIZE", None)
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest", str(suite), "-q",
            "-p", "no:cacheprovider",
            "-p", "conformance.review_baseline_pytest",
            "--review-baseline-results", str(results_path),
        ],
        cwd=baseline.ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    results = json.loads(results_path.read_text(encoding="utf-8"))
    assert results["summary"]["passed"] == 1
    assert results["summary"]["skipped"] == 0
    assert results["summary"]["collectionSkipped"] == 1
    assert len(results["collection"]["skippedCollectors"]) == 1
    assert "fixture module unavailable" in \
        results["collection"]["skippedCollectors"][0]["reason"]
    assert baseline._test_result_is_complete(results) is False


def _inventory_entries():
    return [
        {
            "nodeid": "kernel/tests/test_a.py::test_a",
            "sourceModule": "kernel.tests.test_a",
            "sourcePath": "kernel/tests/test_a.py",
        },
        {
            "nodeid": "kernel/tests/test_bridge.py::test_profile",
            "sourceModule": "profile_si_ffs.tests.test_profile",
            "sourcePath": "profile_si_ffs/tests/test_profile.py",
        },
    ]


def test_pinned_inventory_detects_removal_addition_and_source_drift():
    expected = baseline._inventory_document("kernel/tests", _inventory_entries())
    assert baseline._test_inventory_check(
        expected, _inventory_entries())["matches"] is True

    removed = baseline._test_inventory_check(expected, _inventory_entries()[:1])
    assert removed["matches"] is False
    assert removed["missing"] == [_inventory_entries()[1]]

    added_entry = {
        "nodeid": "kernel/tests/test_new.py::test_new",
        "sourceModule": "kernel.tests.test_new",
        "sourcePath": "kernel/tests/test_new.py",
    }
    added = baseline._test_inventory_check(
        expected, _inventory_entries() + [added_entry])
    assert added["matches"] is False
    assert added["unexpected"] == [added_entry]

    changed_source = [dict(entry) for entry in _inventory_entries()]
    changed_source[1]["sourcePath"] = "profile_si_ffs/tests/renamed.py"
    drift = baseline._test_inventory_check(expected, changed_source)
    assert drift["matches"] is False
    assert len(drift["missing"]) == len(drift["unexpected"]) == 1


def test_inventory_rejects_duplicate_nodeids_and_stale_digest(tmp_path, monkeypatch):
    duplicate = _inventory_entries() + [dict(_inventory_entries()[0])]
    with pytest.raises(ValueError, match="duplicate review baseline nodeid"):
        baseline._inventory_document("kernel/tests", duplicate)

    document = baseline._inventory_document("kernel/tests", _inventory_entries())
    document["entriesSha256"] = "0" * 64
    inventory_path = tmp_path / "inventory.json"
    _write(inventory_path, document)
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    config = {"paths": {
        "testInventory": inventory_path.name,
        "testRoot": "kernel/tests",
    }}
    with pytest.raises(ValueError, match="stale or non-canonical"):
        baseline._load_test_inventory(config)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_git_postflight_ignores_artifacts_but_detects_mutation(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "review@example.invalid")
    _git(repo, "config", "user.name", "Review Baseline")
    (repo / ".gitignore").write_text(".artifacts/\n", encoding="utf-8")
    tracked = repo / "tracked.txt"
    tracked.write_text("one\n", encoding="utf-8")
    _git(repo, "add", ".gitignore", "tracked.txt")
    _git(repo, "commit", "-m", "initial")

    start = baseline._git_state(repo)
    artifact = repo / ".artifacts" / "run" / "evidence.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}\n", encoding="utf-8")
    ignored_end = baseline._git_state(repo)
    assert baseline._git_integrity_reasons(start, ignored_end) == []

    tracked.write_text("mutated\n", encoding="utf-8")
    dirty_end = baseline._git_state(repo)
    reasons = baseline._git_integrity_reasons(start, dirty_end)
    assert "Git worktree is dirty after execution" in reasons
    assert "Git worktree state changed during execution" in reasons


def test_git_postflight_rejects_clean_but_changed_head(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "review@example.invalid")
    _git(repo, "config", "user.name", "Review Baseline")
    tracked = repo / "tracked.txt"
    tracked.write_text("one\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "initial")
    start = baseline._git_state(repo)
    tracked.write_text("two\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "mutate during run")
    end = baseline._git_state(repo)
    assert start["dirty"] is end["dirty"] is False
    assert baseline._git_integrity_reasons(start, end) == [
        "Git worktree state changed during execution"
    ]


@pytest.mark.parametrize("admin_dsn", [
    "host=localhost port=5432 dbname=postgres user=ofarm password=secret",
    "postgresql://ofarm:secret@localhost:5432/postgres?sslmode=disable",
], ids=["keyword", "uri"])
def test_test_store_dsn_is_derived_from_admin_route(admin_dsn):
    from psycopg.conninfo import conninfo_to_dict

    derived = baseline._derive_test_dsn(admin_dsn, "ofarm_kernel_test")
    admin = conninfo_to_dict(admin_dsn)
    test = conninfo_to_dict(derived)
    assert test["dbname"] == "ofarm_kernel_test"
    assert {key: value for key, value in test.items() if key != "dbname"} == \
        {key: value for key, value in admin.items() if key != "dbname"}


def test_postgres_identity_requires_same_server_version_and_test_database():
    admin = {
        "available": True, "version": "17.10", "rawVersion": "17.10",
        "systemIdentifier": "cluster-a", "database": "postgres",
    }
    test = {
        "available": True, "version": "17.10", "rawVersion": "17.10",
        "systemIdentifier": "cluster-a", "database": "ofarm_kernel_test",
    }
    assert baseline._postgres_identity_reasons(
        admin, test, "ofarm_kernel_test") == []
    assert "admin and test-store PostgreSQL servers differ" in \
        baseline._postgres_identity_reasons(
            admin, dict(test, systemIdentifier="cluster-b"), "ofarm_kernel_test")
    assert "test-store PostgreSQL database name differs from the pinned target" in \
        baseline._postgres_identity_reasons(
            admin, dict(test, database="other"), "ofarm_kernel_test")
