"""Fixed operation coverage approved by TRANSITION-001 version 4.

This declaration describes the reviewed executable paths. It is not a runtime
classifier or an exception switch. Candidate inputs, hosts, statuses and tool
exit codes cannot change it. Its bytes belong to the selected T closure.
"""
from __future__ import annotations

import copy
import hashlib
import json


_DECLARATION = {
    "schemaVersion": "ofarm.ci-policy-transition-coverage.v1",
    "decision": {"id": "OFARM2-CI-POLICY-TRANSITION-001", "version": 4},
    "classification": "fixed-operation-executable-and-lifecycle",
    "protected": {
        "policy": ["admission", "grant-and-binding", "live-identity-and-history",
            "revocation", "authenticated-source", "artifact-metadata-and-download",
            "handoff", "publication", "seal", "external-acceptance"],
        "node": ["checkout", "setup-python-manifest-tree-blob-archive",
            "artifact-upload-and-download", "reachable-post-actions"],
        "git": "selected checkout children after the trusted bootstrap",
        "curl": {"executions": 4, "retry": 0,
            "scope": "canonical transition downloads including every redirect and body"},
        "gh": ["version", "release-verify", "release-download-both-assets",
            "verify-asset-amd64", "verify-asset-arm64"],
        "requirements": ["first-403-or-429-refuses", "graphql-errors-refuse-even-http-200",
            "complete-calls-pages-costs-bytes-and-outcomes", "bounded-owned-pools",
            "unknown-route-or-incomplete-observation-refuses",
            "configuration-supervisor-drain-and-cleanup-required"],
    },
    "exceptions": {
        "provider": {
            "owner": "GitHub provider processes",
            "operations": ["provisioning", "runner-image-and-tool-cache-supply",
                "action-archive-preparation", "control-logging-and-reporting"],
            "lifecycle": "before-during-and-after-workflow-steps",
            "retained": "authentic provider run, job, actor, attempt and workflow facts",
        },
        "python": {
            "operations": ["canonical-python-archive-installer-and-child-pip-bootstrap",
                "four-canonical-conformance-pip-installs"],
            "permitted": "existing retries, resumes, version checks and redirects",
            "retained": ["requested-python-version", "action-pin", "lock-files",
                "existing-binary-only-no-deps-require-hashes-flags", "pip-check",
                "exact-installed-set"],
            "limits": "version manifest is mutable and installer pip bootstrap is unversioned",
        },
        "docker": {
            "operations": ["daemon-pinned-buildkit-image-acquisition",
                "canonical-buildx-local-image-fallback", "buildkit-pinned-frontend-base-scanner-pulls",
                "checksum-ADD-postgresql-and-libsodium-inputs"],
            "permitted": "existing recovery or checksum-valid content under an error status",
            "retained": ["image-and-input-pins", "TLS-and-registry-authentication",
                "canonical-commands", "hash-digest-size-checks", "RUN-network-settings",
                "downstream-native-validation"],
        },
        "scanner": {
            "operations": ["canonical-native-amd64-build", "canonical-native-arm64-build"],
            "frontend": "docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e",
            "image": "docker/buildkit-syft-scanner@sha256:79e7b013cbec16bbb436f312819a49a4a57752b2270c1a9332ae1a10fcc82a68",
            "target": "canonical core-only mounted scan target",
            "catalogers": ["image", "file", "sbom-cataloger"],
            "configuration": "existing library defaults; PATH and LOG_LEVEL=warn image environment",
            "excluded": ["new-context-or-stage-scan", "selector-override", "remote-enrichment",
                "alternate-binary", "user-selected-URL", "secret-mount-or-token-forwarding",
                "new-scanner-setting"],
            "evidenceLimit": "source inspection is not a zero-egress or all-hostile-path proof",
        },
    },
    "ambient": {
        "owners": ["candidate-code-and-tests", "unrelated-jobs"],
        "treatment": "untrusted activity, never an authorized dependency exception",
        "outputs": "untrusted inputs to the unchanged substantive validators",
    },
    "preserved": ["all-existing-final-content-version-hash-signature-and-completeness-checks",
        "canonical-workload-commands-and-pins", "all-tests-and-warning-inventory",
        "two-complete-sequential-baselines", "23-platform-cases", "both-native-architectures"],
    "protectedPlan": {"nonperiodicREST": 450, "nonperiodicGraphQL": 200,
        "periodSeconds": 120, "sweepDeadlineSeconds": 15, "sweepREST": 15,
        "sweepGraphQL": 5, "sharedMargin": [75, 75],
        "inclusiveHourlyEnvelope": [990, 430]},
    "notEstablished": ["universal-first-403-or-429-refusal", "all-traffic-accounting",
        "absence-of-excepted-throttling", "all-traffic-quota-ceiling-or-attribution",
        "quota-reservation-or-availability", "general-egress-or-credential-sandbox",
        "network-noninterference", "frozen-future-hosted-runner", "universal-content-pinning"],
    "observedContradiction": "refuse recognition and assess; never widen retrospectively",
}


def declaration():
    """Return a copy; no caller can mutate the selected declaration."""
    return copy.deepcopy(_DECLARATION)


def coverage_digest():
    payload = (json.dumps(_DECLARATION, sort_keys=True, separators=(",", ":"),
                          allow_nan=False) + "\n").encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()
