#!/usr/bin/env python3
"""MP7.6 profile runtime readiness input check.

This command is non-runtime and non-writing. It machine-checks the inputs that
may feed the passive MP7.5 precondition evaluator, then reports whether any
profile readiness overclaim was detected. A passing result may simply mean that
no second profile is ready and no overclaim was found.
"""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PKG = Path(__file__).resolve().parent.parent
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from kernel import config, manifest, sufficiency  # noqa: E402
from kernel.profile_runtime import (  # noqa: E402
    ProfileRuntimeSurfaceInventory,
    evaluate_profile_runtime_preconditions,
    load_profile_descriptor_registry,
)
from kernel.tests.profile_harness_bridge import (  # noqa: E402
    ProfileHarnessBridgeError,
    discover_profile_harness_descriptors,
)

SCHEMA_VERSION = "ofarm.profileRuntimeReadinessCheck.v0_1"
PROFILE_EXECUTED_EVIDENCE = "PROFILE_EXECUTED_EVIDENCE"
CURRENT_ACTIVE_PROFILE = "CURRENT_ACTIVE_PROFILE"
CANDIDATE_RUNTIME_PROFILE = "CANDIDATE_RUNTIME_PROFILE"
DESIGN_ONLY_PROFILE_PACKAGE = "DESIGN_ONLY_PROFILE_PACKAGE"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def adapter_supported_package_names() -> tuple[frozenset[str], tuple[str, ...]]:
    """Return packages with explicit, importable runtime adapter facts.

    MP7.6 deliberately knows only the current SI active runtime seam here. A
    future profile must add an approved checker before it can be credited.
    """
    failures = []
    for adapter_module in sorted(set(manifest.SUPPORTED_IMPORT_SURFACES.values())):
        try:
            importlib.import_module(adapter_module)
        except Exception as exc:
            failures.append(f"adapter module {adapter_module!r} is not importable: {exc}")
    if failures:
        return frozenset(), tuple(failures)
    return frozenset(config.DEFAULT_ACTIVE_PROFILE_PACKAGE_NAMES), ()


def harness_covered_package_names(package_root: Path = PKG) -> tuple[frozenset[str], tuple[str, ...]]:
    try:
        harnesses = discover_profile_harness_descriptors(package_root=package_root)
    except ProfileHarnessBridgeError as exc:
        return frozenset(), (f"profile harness discovery failed: {exc}",)
    return frozenset(harness.profile_package for harness in harnesses), ()


def profile_executed_evidence_package_names(
    package_root: Path = PKG,
) -> tuple[frozenset[str], tuple[str, ...]]:
    """Credit only profile-local, passing PROFILE_EXECUTED_EVIDENCE artifacts."""
    credited: set[str] = set()
    failures: list[str] = []
    root = Path(package_root)
    for profile_dir in sorted(root.iterdir(), key=lambda path: path.name):
        if not profile_dir.is_dir() or not profile_dir.name.startswith("profile_"):
            continue
        evidence_dir = profile_dir / "evidence"
        if not evidence_dir.exists():
            continue
        for evidence_path in sorted(evidence_dir.glob("*.json")):
            try:
                payload = json.loads(evidence_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                failures.append(f"{_rel(evidence_path, root)} is not valid JSON: {exc}")
                continue
            ok, reason = profile_evidence_credits_package(
                payload,
                profile_dir.name,
            )
            if ok:
                credited.add(profile_dir.name)
            elif reason.startswith("malformed:"):
                failures.append(f"{_rel(evidence_path, root)} {reason}")
    return frozenset(credited), tuple(failures)


def profile_evidence_credits_package(
    payload: Any,
    package_name: str,
) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "malformed: evidence artifact must be a JSON object"
    required = {
        "evidenceKind",
        "profilePackage",
        "suiteId",
        "harnessDescriptorIdentity",
        "command",
        "generatedAt",
        "resultRecords",
        "summary",
        "nonClaims",
        "honestyNote",
    }
    missing = sorted(required - set(payload))
    if missing:
        return False, f"malformed: missing required field(s) {missing}"
    if "profileRef" not in payload and "descriptorIdentity" not in payload:
        return False, "malformed: missing profileRef or descriptorIdentity"
    if payload.get("evidenceKind") != PROFILE_EXECUTED_EVIDENCE:
        return False, "malformed: evidenceKind must be PROFILE_EXECUTED_EVIDENCE"
    if payload.get("profilePackage") != package_name:
        return False, "malformed: profilePackage does not match evidence path"
    for field in ("suiteId", "harnessDescriptorIdentity", "command",
                  "generatedAt", "honestyNote"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            return False, f"malformed: {field} must be a non-empty string"
    records = payload.get("resultRecords")
    if not isinstance(records, list) or not records:
        return False, "malformed: resultRecords must be a non-empty list"
    if not all(isinstance(record, dict) for record in records):
        return False, "malformed: resultRecords must contain JSON objects"
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return False, "malformed: summary must be a JSON object"
    for field in ("total", "passed", "failed"):
        if not isinstance(summary.get(field), int) or summary[field] < 0:
            return False, f"malformed: summary.{field} must be a non-negative integer"
    if summary["total"] != len(records):
        return False, "malformed: summary.total must equal resultRecords length"
    if summary["passed"] + summary["failed"] != summary["total"]:
        return False, "malformed: summary passed/failed must add up to total"
    if summary["failed"] != 0:
        return False, "not-ready: profile evidence records failing tests"
    non_claims = payload.get("nonClaims")
    if not isinstance(non_claims, (list, dict)) or not non_claims:
        return False, "malformed: nonClaims must be a non-empty list or object"
    return True, "credited"


def manifest_grounded_package_names() -> tuple[frozenset[str], tuple[str, ...]]:
    python = PKG / ".venv" / "bin" / "python"
    executable = str(python if python.exists() else Path(sys.executable))
    proc = subprocess.run(
        [executable, "-m", "kernel.manifest", "--verify-generated"],
        cwd=PKG,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        output = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
        return frozenset(), (f"manifest verification failed: {output.strip()}",)
    return frozenset(config.DEFAULT_ACTIVE_PROFILE_PACKAGE_NAMES), ()


def build_surface_inventory(
    package_root: Path = PKG,
    *,
    manifest_packages: frozenset[str] | None = None,
) -> tuple[ProfileRuntimeSurfaceInventory, tuple[str, ...]]:
    failures: list[str] = []
    adapters, adapter_failures = adapter_supported_package_names()
    failures.extend(adapter_failures)
    harnesses, harness_failures = harness_covered_package_names(package_root)
    failures.extend(harness_failures)
    evidence, evidence_failures = profile_executed_evidence_package_names(package_root)
    failures.extend(evidence_failures)
    if manifest_packages is None:
        manifest_packages, manifest_failures = manifest_grounded_package_names()
        failures.extend(manifest_failures)
    return (
        ProfileRuntimeSurfaceInventory(
            adapter_supported_package_names=adapters,
            harness_covered_package_names=harnesses,
            profile_executed_evidence_lane_package_names=evidence,
            generated_or_verified_manifest_grounding_package_names=manifest_packages,
        ),
        tuple(failures),
    )


def build_readiness_report(
    package_root: Path = PKG,
    *,
    allowed_package_names: tuple[str, ...] = config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
    selected_package_names: tuple[str, ...] = config.DEFAULT_ACTIVE_PROFILE_PACKAGE_NAMES,
    manifest_packages: frozenset[str] | None = None,
) -> dict:
    root = Path(package_root)
    inventory, inventory_failures = build_surface_inventory(
        root,
        manifest_packages=manifest_packages,
    )
    registry = load_profile_descriptor_registry(
        root,
        allowed_profile_package_names=allowed_package_names,
    )

    profiles = []
    overclaim_failures = list(inventory_failures)
    selected = frozenset(selected_package_names)
    discoverable = frozenset(registry.discoverable_package_names)
    for package_name in sorted(selected - discoverable):
        overclaim_failures.append(
            f"selected profile package {package_name!r} is not discoverable")

    for package_name in registry.discoverable_package_names:
        candidate = registry.candidate_for(package_name)
        if package_name in selected_package_names:
            category = CURRENT_ACTIVE_PROFILE
        elif candidate is None:
            category = DESIGN_ONLY_PROFILE_PACKAGE
        else:
            category = CANDIDATE_RUNTIME_PROFILE
        result = evaluate_profile_runtime_preconditions(
            registry,
            package_name,
            selected_package_names,
            inventory,
            policy_supported_checks=sufficiency.OPERATION_FLOOR_CHECKS,
        )
        if candidate is None and package_name in selected:
            overclaim_failures.append(
                f"descriptorless package {package_name!r} is selected as active")
        if candidate is None and result.preconditions_satisfied:
            overclaim_failures.append(
                f"descriptorless package {package_name!r} was treated as runtime-ready")
        profiles.append({
            "packageName": package_name,
            "category": category,
            "preconditionsSatisfied": result.preconditions_satisfied,
            "blockingReasonCodes": list(result.blocking_reason_codes),
        })

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": now_iso(),
        "runtimeActivationChanged": False,
        "selectedProfilePackageNames": list(selected_package_names),
        "profiles": profiles,
        "overclaimFailures": overclaim_failures,
    }


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main() -> int:
    report = build_readiness_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["overclaimFailures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
