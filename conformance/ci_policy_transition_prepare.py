"""Prepare the committed root declaration; this grants no execution authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conformance import ci_policy_transition as transition
from conformance import ci_policy_transition_workflows as workflows


def closure_spec(root):
    root = Path(root)
    modules = sorted(str(path.relative_to(root))
        for path in (root / "conformance").glob("ci_policy_transition*.py"))
    tests = sorted(str(path.relative_to(root))
        for path in (root / "conformance").glob("test_ci_policy_transition*.py"))
    tests.append("kernel/tests/test_ci_policy_transition.py")
    assets = ["conformance/ci_policy_transition_node.cjs"]
    return {
        "entrypoints": modules + assets,
        "inputs": {
            "configuration": [transition.ROOT_FILE, "conformance/review_baseline_config.json",
                "conformance/review_baseline_test_inventory.json"],
            "pins": ["requirements-review-baseline.lock", "requirements-review-pip.lock",
                "requirements-review-tools.lock",
                "deployment/postgresql/ofarm_ed25519/Containerfile",
                "deployment/postgresql/ofarm_ed25519/native_release_identity.json",
                "deployment/postgresql/ofarm_ed25519/native_evidence_receipt.json",
                "deployment/postgresql/ofarm_ed25519/native_evidence_verification_currentness.json"],
            "generatedInputs": [workflows.SOURCE_INPUT, workflows.PUBLICATION_INPUT],
            "generatedWorkflows": [workflows.SOURCE_OUTPUT, workflows.PUBLICATION_OUTPUT],
            "tests": tests,
        },
        "dependencies": {
            "conformance/evidence_publication_policy.py": ["deployment/postgresql/native_evidence.py"],
            "kernel/manifest.py": ["kernel/profiles/si_ffs/manifest_inputs.py",
                "kernel/profiles/si_ffs/regsr_adapter.py", "kernel/profiles/si_ffs/gerk_adapter.py",
                "kernel/profiles/si_ffs/ffsnaprave_adapter.py"],
            "kernel/profiles/si_ffs/regsr_adapter.py": ["tooling/regsr_snapshot/parse_regsr.py"],
            "kernel/profiles/si_ffs/gerk_adapter.py": ["tooling/gerk_roundtrip/gerk_roundtrip.py"],
            "kernel/tests/test_security_audit_process_crash.py": [
                "deployment/postgresql/run_security_audit_process_crash.py"],
            "conformance/ci_policy_transition_tools.py": [
                "conformance/ci_policy_transition_execution.py",
                "conformance/ci_policy_transition_gh_relay.py",
                "conformance/ci_policy_transition_curl.py"],
            "conformance/ci_policy_transition_workflows.py": modules + assets,
        },
        "allowedChangedPaths": ["conformance/review_baseline_test_inventory.json",
            "docs/development/DELIVERY_PROTOCOL.md"],
    }


def root_manifest(root, *, consumer_pr, campaign_id, not_before, sunset):
    policy = {
        "schemaVersion": transition.POLICY_SCHEMA,
        "repository": {"name": "samovers/OFARM2", "id": 1266697770},
        "operatorId": 263070375,
        "transitionPullRequest": 417,
        "consumerPullRequest": consumer_pr,
        "baseSha": workflows.TRUSTED_BASE,
        "campaign": {"id": campaign_id, "notBefore": not_before, "sunset": sunset},
        "coverageDigest": transition.coverage.coverage_digest(),
        "closure": closure_spec(root),
        "requestPlan": {"periodSeconds": 120, "sweepDeadlineSeconds": 15,
            "periodicREST": 15, "periodicGraphQL": 5,
            "pools": {key: list(value) for key, value in transition.POOL_LIMITS.items()},
            "toolAllocations": {key: list(value) for key, value in transition.TOOL_ALLOCATIONS.items()},
            "sharedMargin": [75, 75]},
    }
    return transition.validate_policy(policy)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consumer-pr", type=int, choices=(413, 411), required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--not-before", required=True)
    parser.add_argument("--sunset", required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    policy = root_manifest(root, consumer_pr=args.consumer_pr, campaign_id=args.campaign_id,
                           not_before=args.not_before, sunset=args.sunset)
    (root / transition.ROOT_FILE).write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n")
    generated = workflows.generate((root / workflows.SOURCE_INPUT).read_bytes(),
        (root / workflows.PUBLICATION_INPUT).read_bytes(), consumer_pr=args.consumer_pr)
    (root / workflows.SOURCE_OUTPUT).write_bytes(generated.source)
    (root / workflows.PUBLICATION_OUTPUT).write_bytes(generated.publication)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
