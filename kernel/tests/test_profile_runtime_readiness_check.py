"""MP7.6 profile runtime readiness command tests."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from kernel import config

from conformance import ofarm_profile_runtime_readiness_check as readiness


def _evidence_payload(
    package_name: str,
    *,
    failed: int = 0,
    profile_package: str | None = None,
) -> dict:
    total = 1
    return {
        "evidenceKind": "PROFILE_EXECUTED_EVIDENCE",
        "profilePackage": profile_package or package_name,
        "profileRef": f"profile:{package_name.removeprefix('profile_')}.test.v0_1",
        "suiteId": f"profile:{package_name}.engineering-tests.v0_1",
        "harnessDescriptorIdentity": f"{package_name}/tests/profile_test_harness.json#test",
        "command": "pytest profile tests",
        "generatedAt": "2026-06-25T10:00:00Z",
        "resultRecords": [{
            "nodeId": f"{package_name}.tests.test_demo::test_demo",
            "module": f"{package_name}.tests.test_demo",
            "outcome": "failed" if failed else "passed",
        }],
        "summary": {
            "total": total,
            "passed": total - failed,
            "failed": failed,
        },
        "nonClaims": [
            "not platform MVP evidence",
            "not production readiness",
        ],
        "honestyNote": "Synthetic test-only profile evidence shape.",
    }


def _write_profile_evidence(root: Path, package_name: str, payload: dict) -> Path:
    evidence_dir = root / package_name / "evidence"
    evidence_dir.mkdir(parents=True)
    path = evidence_dir / "profile_executed_engineering_results_test.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _copy_si_profile(root: Path) -> Path:
    target = root / "profile_si_ffs"
    shutil.copytree(config.PROFILE_ROOT, target)
    return target


def test_runtime_readiness_command_exits_zero_and_reports_current_boundaries():
    manifest_path = (
        config.PROFILE_ROOT
        / "OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json"
    )
    artifact_set_path = (
        config.PROFILE_ROOT
        / "OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json"
    )
    evidence_before = {
        path.relative_to(config.PACKAGE_ROOT)
        for path in (config.PACKAGE_ROOT / "conformance" / "evidence").glob(
            "platform_mvp_results_*.json"
        )
    }
    profile_evidence_before = {
        path.relative_to(config.PACKAGE_ROOT)
        for path in config.PACKAGE_ROOT.glob("profile_*/evidence/*.json")
    }
    manifest_before = manifest_path.read_bytes()
    artifact_set_before = artifact_set_path.read_bytes()

    proc = subprocess.run(
        [
            sys.executable, "-I", "-B", "-S",
            str(config.PACKAGE_ROOT / "tooling" / "ofarm_isolated.py"),
            "--venv-root", str(Path(sys.executable).absolute().parent.parent),
            "-m", "conformance.ofarm_profile_runtime_readiness_check",
        ],
        cwd=config.PACKAGE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    report = json.loads(proc.stdout)
    assert report["schemaVersion"] == "ofarm.profileRuntimeReadinessCheck.v0_1"
    assert report["runtimeActivationChanged"] is False
    assert report["overclaimFailures"] == []
    profiles = {profile["packageName"]: profile for profile in report["profiles"]}
    assert profiles["profile_si_ffs"]["category"] == "CURRENT_ACTIVE_PROFILE"
    for package_name in ("profile_nl_go_glmc7_2026", "profile_rs_organic_crop"):
        if package_name in profiles:
            assert profiles[package_name]["category"] == "DESIGN_ONLY_PROFILE_PACKAGE"
            assert profiles[package_name]["blockingReasonCodes"] == [
                "NO_DESCRIPTOR_CANDIDATE"
            ]

    assert manifest_path.read_bytes() == manifest_before
    assert artifact_set_path.read_bytes() == artifact_set_before
    assert evidence_before == {
        path.relative_to(config.PACKAGE_ROOT)
        for path in (config.PACKAGE_ROOT / "conformance" / "evidence").glob(
            "platform_mvp_results_*.json"
        )
    }
    assert profile_evidence_before == {
        path.relative_to(config.PACKAGE_ROOT)
        for path in config.PACKAGE_ROOT.glob("profile_*/evidence/*.json")
    }


def test_readiness_policy_check_rejects_unsupported_operation_floor_item(tmp_path):
    root = tmp_path / "package_root"
    root.mkdir()
    profile_root = _copy_si_profile(root)
    policy_path = profile_root / "evidence_review_policy_v0_1.json"
    policy = json.loads(policy_path.read_text())
    policy["operationFloor"]["hardItems"].append("unsupported-floor-item")
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    report = readiness.build_readiness_report(
        root,
        allowed_package_names=("profile_si_ffs",),
        selected_package_names=("profile_si_ffs",),
        manifest_packages=frozenset({"profile_si_ffs"}),
    )

    profile = report["profiles"][0]
    assert profile["packageName"] == "profile_si_ffs"
    assert "POLICY_NOT_LOADABLE" in profile["blockingReasonCodes"]


def test_selected_descriptorless_package_is_overclaim_drift():
    report = readiness.build_readiness_report(
        selected_package_names=("profile_nl_go_glmc7_2026",),
        manifest_packages=frozenset({"profile_si_ffs"}),
    )

    assert any(
        "descriptorless package 'profile_nl_go_glmc7_2026' is selected as active"
        in failure
        for failure in report["overclaimFailures"]
    )


def test_selected_undiscoverable_package_is_overclaim_drift():
    report = readiness.build_readiness_report(
        selected_package_names=("profile_missing",),
        manifest_packages=frozenset({"profile_si_ffs"}),
    )

    assert any(
        "selected profile package 'profile_missing' is not discoverable" in failure
        for failure in report["overclaimFailures"]
    )


def test_root_platform_evidence_never_counts_as_profile_evidence(tmp_path):
    root = tmp_path / "package_root"
    (root / "conformance" / "evidence").mkdir(parents=True)
    (root / "conformance" / "evidence" / "platform_mvp_results_test.json").write_text(
        json.dumps({"suite": "conformance:root", "executed": True}),
        encoding="utf-8",
    )
    (root / "profile_si_ffs").mkdir()

    packages, failures = readiness.profile_executed_evidence_package_names(root)

    assert packages == frozenset()
    assert failures == ()


def test_harness_descriptor_alone_does_not_count_as_profile_evidence(tmp_path):
    root = tmp_path / "package_root"
    root.mkdir()
    _copy_si_profile(root)

    packages, failures = readiness.profile_executed_evidence_package_names(root)

    assert packages == frozenset()
    assert failures == ()


def test_well_shaped_profile_evidence_counts_for_matching_package_only(tmp_path):
    root = tmp_path / "package_root"
    package_name = "profile_example"
    _write_profile_evidence(root, package_name, _evidence_payload(package_name))

    packages, failures = readiness.profile_executed_evidence_package_names(root)

    assert packages == frozenset({package_name})
    assert failures == ()


def test_profile_evidence_with_failures_does_not_count(tmp_path):
    root = tmp_path / "package_root"
    package_name = "profile_example"
    _write_profile_evidence(
        root,
        package_name,
        _evidence_payload(package_name, failed=1),
    )

    packages, failures = readiness.profile_executed_evidence_package_names(root)

    assert packages == frozenset()
    assert failures == ()


def test_profile_evidence_cannot_credit_another_package(tmp_path):
    root = tmp_path / "package_root"
    _write_profile_evidence(
        root,
        "profile_a",
        _evidence_payload("profile_a", profile_package="profile_b"),
    )

    packages, failures = readiness.profile_executed_evidence_package_names(root)

    assert packages == frozenset()
    assert failures
    assert "profilePackage does not match" in failures[0]


def test_docs_navigation_and_source_manifests_do_not_populate_inventory(tmp_path):
    root = tmp_path / "package_root"
    profile_root = root / "profile_docs"
    (profile_root / "source_packet_extracts").mkdir(parents=True)
    (profile_root / "README.md").write_text("runtime ready: no\n", encoding="utf-8")
    (profile_root / "navigation.json").write_text("{}", encoding="utf-8")
    (profile_root / "source_packet_extracts" / "source_manifest.json").write_text(
        "{}",
        encoding="utf-8",
    )

    inventory, failures = readiness.build_surface_inventory(
        root,
        manifest_packages=frozenset(),
    )

    assert failures == ()
    assert "profile_docs" not in inventory.adapter_supported_package_names
    assert "profile_docs" not in inventory.harness_covered_package_names
    assert "profile_docs" not in inventory.profile_executed_evidence_lane_package_names
    assert "profile_docs" not in (
        inventory.generated_or_verified_manifest_grounding_package_names
    )
