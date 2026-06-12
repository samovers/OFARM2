"""Capability Manifest generation (M1 brief task 7).

The manifest is generated FROM the actual runtime surfaces — the registry,
the gate pipeline's commit-class map, the action classes the authority gate
evaluates, and the artifacts that actually exist — never hand-claimed.

Claim discipline: the runtime-evidence level for explainable current state is
CONFORMANCE_FIXTURE_PASSING at most (explainable-evidence RFC §11.3/§11.4):
no benchmark evidence exists, so no fleet-scale or production claim is made
anywhere. Unsupported surfaces (PLATFORM.md list) are declared in the
companion UNSUPPORTED_SURFACES.md because the manifest contract is closed
(additionalProperties: false) and carries no free-text surface; the manifest
itself simply never claims those surfaces.
"""
from __future__ import annotations

import json

from . import config
from .context import now_iso
from .policy import (COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS,
                     COMMIT_CLASS_TO_FAMILY, NON_COMMIT_ACTION_CLASSES)

MANIFEST_ID = "manifest:si.ffs.pilot.v0_1"
MANIFEST_PATH = config.PROFILE_ROOT / "OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json"
ARTIFACT_SET_PATH = config.PROFILE_ROOT / "OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json"

VIEW_ARTIFACTS = [
    "queryspec:si.ffs.spray-register.passportview.v0_1",
    "queryplan:si.ffs.spray-register.passportview.v0_1",
    "queryspec:si.ffs.inspection-register.documentassembly.v0_1",
    "queryplan:si.ffs.inspection-register.documentassembly.v0_1",
]


def build_manifest(store) -> dict:
    registry_kinds = [k for k in store.registry.kinds()
                      if store.registry.get(k).lane == "canonical"]
    commit_classes = sorted(
        c.lower().replace("_", " ") for c in COMMIT_CLASS_TO_FAMILY)
    event_families = sorted(set(COMMIT_CLASS_TO_FAMILY.values()))
    return {
        "schemaVersion": "ofarm.capabilitymanifest.v0.1",
        "manifestId": MANIFEST_ID,
        "status": "ACTIVE",
        "ofarmVersion": "RC2.1",
        "platformVersion": config.RUNTIME_VERSION,
        "publishedAt": now_iso(),
        "deploymentScope": {"scopeType": "TENANT", "scopeRef": config.TENANT_REF},
        "capabilitySections": {
            "artifactSupport": {
                "supportedArtifactTypes": registry_kinds,
            },
            "packSupport": {
                "supportsPackActivation": True,
                "activePackRefs": [config.PACK_REF],
                "activeProfileRefs": [config.PROFILE_REF],
                "supportedPrecedenceClasses": ["JURISDICTION_LAW_SAFETY"],
                "supportedSurfaceFamilies": [
                    "VOCABULARY_BINDINGS", "EVIDENCE_POLICY", "VALIDATION_RULE",
                    "VIEW_SHAPING", "DOCUMENT_ASSEMBLY_SHAPING",
                ],
            },
            "querySupport": {
                "querySpecificationSchemaRef":
                    "contracts/platform/OFARM_QuerySpecification_schema_v0_1.json",
                "queryPlanSchemaRef":
                    "contracts/platform/OFARM_QueryPlanIR_schema_v0_1.json",
                # predefined versioned views only — no public query compiler,
                # no AI-mediated query (PLATFORM.md unsupported surfaces)
                "supportsGuidedQueryUI": False,
                "supportsAIMediatedQuery": False,
                "supportsPublicExpertQuery": False,
                "supportedResultModes": ["PASSPORT_VIEW", "DOCUMENT_ASSEMBLY_INPUT"],
            },
            "eventSupport": {
                "supportedEventFamilies": event_families,
                "supportedCommitClasses": commit_classes,
            },
            "authoritySupport": {
                # Families follow the accepted Authority Action Matrix:
                # OUTPUT_APPROVE_DOCUMENT_ASSEMBLY / OUTPUT_FILE_SUBMISSION_
                # ASSEMBLY are attest/sign-family actions the runtime performs
                # (freeze approval, local filing). OUTPUT_ATTEST_DOCUMENT_
                # ASSEMBLY (portable signature) is deliberately NOT claimed —
                # attestation envelopes stay NONE everywhere.
                "supportedAuthorityFamilies": [
                    "observe/report", "assert/submit", "govern/decide",
                    "attest/sign", "share/revoke", "receive/use",
                ],
                # accepted Action Matrix vocabulary only — the exact classes
                # the authority gate evaluates (no parallel runtime dialect)
                "supportedActionClasses": sorted(
                    set(COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS.values())
                    | NON_COMMIT_ACTION_CLASSES),
                "supportsHumanOnlyRestrictions": True,
            },
            "importExportSupport": {
                "declaredSurfaces": [
                    {"surfaceType": "IMPORT_MAPPING",
                     "targetRef": "scheme:si.uvhvvr.ffs-reg.html-surface",
                     "direction": "IMPORT",
                     # parser exists and produced the shipped snapshot;
                     # scheduled adapter cadence is M2 — PARTIAL, not SUPPORTED
                     "status": "PARTIAL"},
                    {"surfaceType": "EXPORT_MAPPING",
                     "targetRef": "view:si.ffs.inspection-register.documentassembly.v0_1",
                     "direction": "EXPORT",
                     "status": "SUPPORTED"},
                    {"surfaceType": "API_CONTRACT",
                     "targetRef": "api:ofarm2.kernel.m1",
                     "direction": "BIDIRECTIONAL",
                     "status": "SUPPORTED"},
                ],
            },
            "enforcementSupport": {
                "supportedGates": [
                    "INGRESS_NORMALIZATION", "AUTHORITY", "VALIDATION",
                    "PACK_APPLICABILITY", "EVIDENCE_SUFFICIENCY",
                    "REVIEW_PROMOTION", "CURRENT_STATE_MATERIALIZATION",
                    "PUBLICATION_EXPORT",
                ],
                "supportsMergeResolutionTrace": False,
                "supportsAuthorizationDecisionTrace": True,
                "supportsProjectionTraceBack": True,
                "supportsFreshnessEvaluation": True,
            },
        },
        "registryRelation": {
            "manifestRegistryRef": "registry:ofarm2-implementation-package.v0_1",
            "artifactRegistryRef": "registry:ofarm2-implementation-package.v0_1",
            "activeArtifactSetRef": "activeartifactset:si.ffs.pilot.v0_1",
            "discoveryVisibility": "PRIVATE",
        },
        "conformance": {
            # NONE, deliberately: the only available definition of BASELINE is
            # canonical Platform law's, which is far broader than the executed
            # 15-test pilot suite — claiming it would be ungrounded (RFC §11.4:
            # no evidence level beyond what evidence supports). The executed
            # suite is declared as a test-suite ref, not a level claim.
            "minimumConformanceLevel": "NONE",
            "testSuiteRefs": ["conformance:ofarm2.platform-mvp.tests-1-15.v0_1"],
            "declaredProfileRefs": [config.PROFILE_REF],
        },
    }


def build_artifact_set() -> dict:
    """Regenerated ActiveArtifactSet referencing the real M1 artifacts
    (the shipped instance's notes call for exactly this regeneration)."""
    return {
        "schemaVersion": "ofarm.activeartifactset.v0.1",
        "activeArtifactSetId": "activeartifactset:si.ffs.pilot.v0_1",
        "generatedAt": now_iso(),
        "deploymentScope": {"scopeType": "TENANT", "scopeRef": config.TENANT_REF},
        "artifactRegistryRef": "registry:ofarm2-implementation-package.v0_1",
        "activePackRefs": [config.PACK_REF],
        "activeProfileRefs": [config.PROFILE_REF],
        "activeArtifactRefs": [
            "contract:ofarm.assertionrecord.v0.1",
            "contract:ofarm.semanticeventenvelope.v0.1",
            "contract:ofarm.evidencerecord.v0.1",
            "contract:ofarm.reviewdecision.v0.1",
            "contract:ofarm.acceptedeventconsequence.v0.1",
            "contract:ofarm.executionrecordpayload.v0.1",
            "contract:ofarm.agronomicidentitybinding.v0.1",
            "contract:ofarm.referencesnapshot.v0.1",
            "view:si.ffs.spray-register.passportview.v0_1",
            "view:si.ffs.inspection-register.documentassembly.v0_1",
            *VIEW_ARTIFACTS,
            config.EVIDENCE_POLICY_REF,
            config.CODE_BINDING_PROFILE_REF,
            config.SHIPPED_REGSR_SNAPSHOT_REF,
            "referencesnapshot:si.mkgp.gerk-layer.2025-06-30",
            MANIFEST_ID,
        ],
        "sourcePackActivationSetRefs": ["packactivationset:si.ffs.pilot.v0_1"],
        "notes": "Regenerated at M1 against real artifacts: the four authored "
                 "QuerySpecification/QueryPlanIR view artifacts, the Capability "
                 "Manifest, both shipped ReferenceSnapshots, and the cut SI "
                 "code-binding profile. Unsupported-surface posture: see "
                 "UNSUPPORTED_SURFACES.md (manifest contract carries no free text).",
    }


def verify_grounding(store, manifest: dict, artifact_set: dict) -> list[str]:
    """Manifest-grounding check (conformance test 15): every claim the
    manifest makes must match the ActiveArtifactSet and the real runtime."""
    failures = []
    if manifest["registryRelation"]["activeArtifactSetRef"] != \
            artifact_set["activeArtifactSetId"]:
        failures.append("manifest does not reference the regenerated artifact set")
    refs = set(artifact_set["activeArtifactRefs"])
    if MANIFEST_ID not in refs:
        failures.append("artifact set does not list the manifest")
    for ref in VIEW_ARTIFACTS:
        if ref not in refs:
            failures.append(f"artifact set missing authored view artifact {ref}")
    # contract claims must exist in the registry
    for ref in sorted(refs):
        if ref.startswith("contract:"):
            kind = ref.split(":", 1)[1]
            try:
                store.registry.get(kind)
            except Exception:
                failures.append(f"artifact set claims unknown contract {ref}")
    # commit classes claimed must be exactly what the pipeline accepts
    claimed = set(manifest["capabilitySections"]["eventSupport"]["supportedCommitClasses"])
    actual = {c.lower().replace("_", " ") for c in COMMIT_CLASS_TO_FAMILY}
    if claimed != actual:
        failures.append(f"commit-class claims drift: {claimed ^ actual}")
    # no canonical-baseline evidence exists -> the only grounded level is NONE
    if manifest["conformance"]["minimumConformanceLevel"] != "NONE":
        failures.append("over-claimed conformance level without evidence (RFC §11.4)")
    # action-class claims must match the policy tables (the persisted JSON
    # is checked against the code, catching disk-vs-code drift; the four
    # non-commit classes ground in their evaluate() call sites via the
    # law-binding stage test, not here); portable attestation stays unclaimed
    claimed_actions = set(manifest["capabilitySections"]["authoritySupport"]
                          ["supportedActionClasses"])
    evaluated = (set(COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS.values())
                 | NON_COMMIT_ACTION_CLASSES)
    if claimed_actions != evaluated:
        failures.append(f"action-class claims drift from runtime: {claimed_actions ^ evaluated}")
    if "OUTPUT_ATTEST_DOCUMENT_ASSEMBLY" in claimed_actions:
        failures.append("portable attestation claimed while disabled")
    return failures


def write_artifacts(store) -> tuple[dict, dict]:
    manifest = build_manifest(store)
    artifact_set = build_artifact_set()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    ARTIFACT_SET_PATH.write_text(json.dumps(artifact_set, indent=2) + "\n")
    return manifest, artifact_set
