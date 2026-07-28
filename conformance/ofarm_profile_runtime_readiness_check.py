#!/usr/bin/env python3
"""MP7.6 profile runtime readiness input check.

This command is non-runtime and non-writing. It machine-checks the inputs that
may feed the passive MP7.5 precondition evaluator, then reports whether any
profile readiness overclaim was detected. A passing result may simply mean that
no second profile is ready and no overclaim was found.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

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
CURRENT_ACTIVE_PROFILE = "CURRENT_ACTIVE_PROFILE"
CANDIDATE_RUNTIME_PROFILE = "CANDIDATE_RUNTIME_PROFILE"
DESIGN_ONLY_PROFILE_PACKAGE = "DESIGN_ONLY_PROFILE_PACKAGE"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def harness_covered_package_names(package_root: Path = PKG) -> tuple[frozenset[str], tuple[str, ...]]:
    try:
        harnesses = discover_profile_harness_descriptors(package_root=package_root)
    except ProfileHarnessBridgeError as exc:
        return frozenset(), (f"profile harness discovery failed: {exc}",)
    return frozenset(harness.profile_package for harness in harnesses), ()


def _verified_profile_surface_facts() -> tuple[
    frozenset[str],
    frozenset[str],
    frozenset[str],
    tuple[str, ...],
]:
    """Return facts admitted by the production provider and RuntimeBundle."""
    store = manifest._bootstrapped_store_for_verify()
    try:
        package_name, _, _ = manifest._profile_manifest_context(store)
        failures = tuple(manifest.verify_generated_artifacts(store))
        if failures:
            rendered = tuple(
                f"manifest verification failed: {failure}"
                for failure in failures
            )
            return frozenset(), frozenset(), frozenset(), rendered
        return (
            frozenset({package_name}),
            frozenset(),
            frozenset({package_name}),
            (),
        )
    finally:
        store.close()


def build_surface_inventory(
) -> tuple[ProfileRuntimeSurfaceInventory, tuple[str, ...]]:
    adapters, evidence, manifest_packages, authority_failures = (
        _verified_profile_surface_facts()
    )
    harnesses, harness_failures = harness_covered_package_names(PKG)
    return (
        ProfileRuntimeSurfaceInventory(
            adapter_supported_package_names=adapters,
            harness_covered_package_names=harnesses,
            profile_executed_evidence_lane_package_names=evidence,
            generated_or_verified_manifest_grounding_package_names=manifest_packages,
        ),
        (*authority_failures, *harness_failures),
    )


def _assemble_readiness_report(
    package_root: Path,
    *,
    allowed_package_names: tuple[str, ...],
    selected_package_names: tuple[str, ...],
    inventory: ProfileRuntimeSurfaceInventory,
    inventory_failures: tuple[str, ...] = (),
) -> dict:
    root = Path(package_root)
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


def build_readiness_report() -> dict:
    inventory, failures = build_surface_inventory()
    return _assemble_readiness_report(
        PKG,
        allowed_package_names=config.ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
        selected_package_names=config.ACTIVE_PROFILE_PACKAGE_NAMES,
        inventory=inventory,
        inventory_failures=failures,
    )


def main() -> int:
    report = build_readiness_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["overclaimFailures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
