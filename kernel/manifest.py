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

import argparse
import copy
import difflib
import importlib
import json
import sys

import jsonschema

from . import config
from .context import now_iso
from .policy import (COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS,
                     COMMIT_CLASS_TO_FAMILY, NON_COMMIT_ACTION_CLASSES)
from .runtime_bundle import (GLOBAL_CONTENT_PLACEMENT, JSON_CANONICALIZATION,
                             RuntimeBundleError, require_store_runtime_bundle)

MANIFEST_ID = "manifest:si.ffs.pilot.v0_1"
MANIFEST_PATH = config.PROFILE_ROOT / "OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json"
ARTIFACT_SET_PATH = config.PROFILE_ROOT / "OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json"
PLATFORM_MVP_TEST_SUITE_REF = (
    "conformance:ofarm2.platform-mvp.tests-1-15-plus-regressions.v0_2"
)

VIEW_ARTIFACTS = [
    "queryspec:si.ffs.spray-register.passportview.v0_1",
    "queryplan:si.ffs.spray-register.passportview.v0_1",
    "queryspec:si.ffs.inspection-register.documentassembly.v0_1",
    "queryplan:si.ffs.inspection-register.documentassembly.v0_1",
]

# the SINGLE-HOMED source of truth for which import targets actually have a
# SUPPORTED import adapter riding the generic G2 mechanism: import-target scheme
# -> the adapter module behind it. build_manifest derives the IMPORT_MAPPING
# surfaces FROM this map, and verify_grounding requires every declared import
# surface to be BOTH a scheme the code-binding profile declares AND a key here
# whose adapter actually imports — so a scheme the profile merely names in its
# vocabulary (EPPO, KMG-MID, …) can never be declared a SUPPORTED import surface
# without a real adapter behind it. "SUPPORTED" covers the governed snapshot-import
# MECHANISM only (parser reuse + G2 import + fixtures); never live fetch / cron /
# currentness / current-compliance (D9; UNSUPPORTED_SURFACES.md). Per-target scope:
#  - REGSR (P1): unofficial HTML surface, decision-number identity, weekly cadence.
#  - GERK  (P2): ATTRIBUTE import only (existence / raw AREA / use code); geometry P2.
#  - FFSNaprave (P3): official yearly downloads (D7) + composite-key inspection evidence.
SUPPORTED_IMPORT_SURFACES = {
    "scheme:si.uvhvvr.ffs-reg.html-surface": "kernel.profiles.si_ffs.regsr_adapter",
    "scheme:si.gerk-pid": "kernel.profiles.si_ffs.gerk_adapter",
    "scheme:si.ffs-naprave": "kernel.profiles.si_ffs.ffsnaprave_adapter",
}


def preload_runtime_import_surfaces() -> tuple[object, ...]:
    """Load every reviewed adapter before RuntimeBundle environment selection."""
    modules = tuple(
        importlib.import_module(module_name)
        for module_name in sorted(set(SUPPORTED_IMPORT_SURFACES.values()))
    )
    if tuple(module.__name__ for module in modules) != tuple(
            sorted(set(SUPPORTED_IMPORT_SURFACES.values()))):
        raise RuntimeError("reviewed runtime import-surface preload is not exact")
    for module in modules:
        hook = getattr(module, "preload_runtime_import_surface", None)
        if not callable(hook):
            raise RuntimeError(
                f"reviewed runtime import surface has no preload hook: "
                f"{module.__name__}")
        dependencies = hook()
        if not isinstance(dependencies, tuple) or not dependencies:
            raise RuntimeError(
                f"reviewed runtime import surface preload is empty: "
                f"{module.__name__}")
    return modules


def _retained_code_binding_profile(store) -> dict:
    """Return the exact global code-binding bytes selected by this Store.

    The code-binding profile is immutable package content, so bootstrap does
    not copy it into the tenant ``kernel_record`` table.  Manifest grounding
    must therefore cross the verified RuntimeBundle receipt instead of falling
    back to either tenant records or the live package filesystem.
    """
    bundle = store.runtime_bundle
    require_store_runtime_bundle(store, bundle, "Capability Manifest grounding")
    descriptor = bundle.descriptor
    if (bundle.tenant_ref != config.TENANT_REF
            or descriptor.profile_ref != config.PROFILE_REF
            or descriptor.pack_ref != config.PACK_REF
            or descriptor.code_binding_profile_ref !=
            config.CODE_BINDING_PROFILE_REF):
        raise RuntimeBundleError(
            "Capability Manifest selection does not exactly match the bound "
            "RuntimeBundle tenant/profile/pack/code-binding identity")

    component = bundle.component(
        "PROFILE_INSTANCE", descriptor.code_binding_profile_ref)
    if (component.placement != GLOBAL_CONTENT_PLACEMENT
            or component.canonicalization != JSON_CANONICALIZATION):
        raise RuntimeBundleError(
            "code-binding profile is not exact global canonical JSON content")
    profile = bundle.json_component(
        "PROFILE_INSTANCE", descriptor.code_binding_profile_ref)
    if (profile.get("schemaVersion") !=
            "ofarm.agronomiccodebindingprofile.v0.1"
            or profile.get("agronomicCodeBindingProfileId") !=
            descriptor.code_binding_profile_ref):
        raise RuntimeBundleError(
            "code-binding profile payload identity differs from its RuntimeBundle ref")
    return profile


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
                # the IMPORT_MAPPING surfaces are DERIVED from SUPPORTED_IMPORT_SURFACES
                # (single-homed) — a surface cannot be declared SUPPORTED unless a real
                # adapter rides it; per-target scope is documented on the map.
                "declaredSurfaces": [
                    {"surfaceType": "IMPORT_MAPPING", "targetRef": target,
                     "direction": "IMPORT", "status": "SUPPORTED"}
                    for target in SUPPORTED_IMPORT_SURFACES
                ] + [
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
            # platform MVP + root conformance regression suite — claiming it
            # would be ungrounded (RFC §11.4: no evidence level beyond what
            # evidence supports). The executed suite is declared as a test-suite
            # ref, not a level claim.
            "minimumConformanceLevel": "NONE",
            "testSuiteRefs": [PLATFORM_MVP_TEST_SUITE_REF],
            "declaredProfileRefs": [config.PROFILE_REF],
        },
    }


def build_artifact_set() -> dict:
    """Current active SI ActiveArtifactSet generated/verified from the runtime
    surfaces: the PartialExtent extent-carrier now active (G7), the REGSR/GERK/
    FFSNaprave import adapters, the SI bindings, and the evidence-review floor
    policy; the manifest declares the matching surfaces."""
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
            "contract:ofarm.partialextent.v0.1",
            "contract:ofarm.complianceclaim.v0.1",
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
        "notes": "Current active SI artifact set generated/verified from runtime "
                 "surfaces: the operation/record contracts (incl. the PartialExtent "
                 "extent-carrier now active for partial-extent bounds, G7), the four "
                 "authored QuerySpecification/QueryPlanIR view artifacts, the "
                 "Capability Manifest (which declares the REGSR/GERK/FFSNaprave "
                 "import surfaces and inspection-register export), the evidence-review "
                 "floor policy, both shipped ReferenceSnapshots, and the cut SI "
                 "code-binding profile. "
                 "Unsupported-surface posture: see UNSUPPORTED_SURFACES.md (manifest "
                 "contract carries no free text).",
    }


def verify_grounding(store, manifest: dict, artifact_set: dict) -> list[str]:
    """Manifest-grounding check (conformance test 15): every claim the
    manifest makes must match the ActiveArtifactSet and the real runtime."""
    failures = []
    if manifest["registryRelation"]["activeArtifactSetRef"] != \
            artifact_set["activeArtifactSetId"]:
        failures.append("manifest does not reference the regenerated artifact set")
    expected_scope = {"scopeType": "TENANT", "scopeRef": config.TENANT_REF}
    if manifest.get("deploymentScope") != expected_scope:
        failures.append(
            "manifest deployment scope does not equal the bound runtime tenant")
    if artifact_set.get("deploymentScope") != expected_scope:
        failures.append(
            "artifact set deployment scope does not equal the bound runtime tenant")
    refs = set(artifact_set["activeArtifactRefs"])
    if MANIFEST_ID not in refs:
        failures.append("artifact set does not list the manifest")
    if config.CODE_BINDING_PROFILE_REF not in refs:
        failures.append(
            "artifact set does not list the descriptor code-binding profile")
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
    # every declared IMPORT_MAPPING surface must ground TWICE: in a scheme the
    # code-binding profile actually declares (a standardRef — the manifest must not
    # claim an import for a scheme the profile does not bind), AND in a real
    # SUPPORTED import adapter (a SUPPORTED_IMPORT_SURFACES key whose adapter module
    # imports) — so the SUPPORTED claim is grounded in actual import support, not
    # just profile vocabulary (M2 P6 steward re-review).
    import_targets = [s["targetRef"] for s in manifest["capabilitySections"]
                      ["importExportSupport"]["declaredSurfaces"]
                      if s["surfaceType"] == "IMPORT_MAPPING"]
    try:
        profile = _retained_code_binding_profile(store)
    except RuntimeError as exc:
        profile = None
        failures.append(
            "code-binding profile is not available from the exact verified "
            f"RuntimeBundle; cannot ground import surfaces ({exc})")
    scheme_refs = _standard_refs(profile) if profile is not None else None
    for target in import_targets:
        if scheme_refs is not None and target not in scheme_refs:
            failures.append(f"import surface {target} is not a scheme the code-binding "
                            "profile declares (ungrounded import-surface claim)")
        adapter = SUPPORTED_IMPORT_SURFACES.get(target)
        if adapter is None:
            failures.append(f"import surface {target} has no supported import adapter "
                            "(absent from SUPPORTED_IMPORT_SURFACES) — a profile-declared "
                            "scheme without an adapter cannot be a SUPPORTED import surface")
        else:
            try:
                importlib.import_module(adapter)
            except Exception as exc:  # the adapter the map names must actually load
                failures.append(f"import surface {target} names adapter {adapter!r} that "
                                f"does not import ({exc}) — SUPPORTED claim ungrounded")
    return failures


def _standard_refs(obj) -> set[str]:
    """Every standardRef value anywhere in the code-binding profile (the scheme
    identifiers it actually declares), for grounding manifest import surfaces."""
    found: set[str] = set()
    if isinstance(obj, dict):
        ref = obj.get("standardRef")
        if isinstance(ref, str):
            found.add(ref)
        for value in obj.values():
            found |= _standard_refs(value)
    elif isinstance(obj, list):
        for item in obj:
            found |= _standard_refs(item)
    return found


def write_artifacts(store) -> tuple[dict, dict]:
    manifest = build_manifest(store)
    artifact_set = build_artifact_set()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    ARTIFACT_SET_PATH.write_text(json.dumps(artifact_set, indent=2) + "\n")
    return manifest, artifact_set


def _normalized_for_generated_compare(payload: dict,
                                      volatile_paths: tuple[tuple[str, ...], ...]) -> dict:
    normalized = copy.deepcopy(payload)
    for path in volatile_paths:
        cursor = normalized
        for part in path[:-1]:
            if not isinstance(cursor, dict):
                break
            cursor = cursor.get(part)
        else:
            if isinstance(cursor, dict) and path[-1] in cursor:
                cursor[path[-1]] = "<normalized-generated-timestamp>"
    return normalized


def _stable_json_lines(payload: dict) -> list[str]:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").splitlines(keepends=True)


def _diff_generated_payload(label: str, committed: dict, generated: dict,
                            volatile_paths: tuple[tuple[str, ...], ...]) -> str | None:
    committed_cmp = _normalized_for_generated_compare(committed, volatile_paths)
    generated_cmp = _normalized_for_generated_compare(generated, volatile_paths)
    if committed_cmp == generated_cmp:
        return None
    diff = difflib.unified_diff(
        _stable_json_lines(committed_cmp),
        _stable_json_lines(generated_cmp),
        fromfile=f"committed {label}",
        tofile=f"generated {label}",
    )
    return f"{label} differs from generated output:\n{''.join(diff)}"


def _schema_validation_failures(label: str, payload: dict, schema_path) -> list[str]:
    schema = json.loads(schema_path.read_text())
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    failures = []
    for error in errors:
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        failures.append(
            f"{label} violates {schema_path.relative_to(config.PACKAGE_ROOT)} "
            f"at {location}: {error.message}"
        )
    return failures


def _load_committed_json(path, label: str) -> tuple[dict | None, list[str]]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return None, [f"{label} could not be read as JSON at {path}: {exc}"]
    if not isinstance(payload, dict):
        return None, [f"{label} at {path} must be a JSON object"]
    return payload, []


def verify_generated_artifacts(store) -> list[str]:
    """Verify committed generated artifacts equal generator output.

    This is intentionally read-only for the working tree: it builds artifacts in
    memory, normalizes approved volatile timestamp fields, and reports drift.
    """
    failures: list[str] = []
    generated_manifest = build_manifest(store)
    generated_artifact_set = build_artifact_set()

    committed_manifest, load_failures = _load_committed_json(
        MANIFEST_PATH, "committed capability manifest")
    failures.extend(load_failures)
    committed_artifact_set, load_failures = _load_committed_json(
        ARTIFACT_SET_PATH, "committed active artifact set")
    failures.extend(load_failures)
    if committed_manifest is None or committed_artifact_set is None:
        return failures

    manifest_schema = (
        config.CONTRACTS_ROOT / "platform" / "OFARM_Capability_Manifest_schema_v0_1.json"
    )
    artifact_set_schema = (
        config.CONTRACTS_ROOT / "platform" / "OFARM_ActiveArtifactSet_schema_v0_1.json"
    )
    failures.extend(_schema_validation_failures(
        "committed capability manifest", committed_manifest, manifest_schema))
    failures.extend(_schema_validation_failures(
        "generated capability manifest", generated_manifest, manifest_schema))
    failures.extend(_schema_validation_failures(
        "committed active artifact set", committed_artifact_set, artifact_set_schema))
    failures.extend(_schema_validation_failures(
        "generated active artifact set", generated_artifact_set, artifact_set_schema))

    manifest_diff = _diff_generated_payload(
        "capability manifest",
        committed_manifest,
        generated_manifest,
        (("publishedAt",),),
    )
    if manifest_diff is not None:
        failures.append(manifest_diff)
    artifact_set_diff = _diff_generated_payload(
        "active artifact set",
        committed_artifact_set,
        generated_artifact_set,
        (("generatedAt",),),
    )
    if artifact_set_diff is not None:
        failures.append(artifact_set_diff)

    for failure in verify_grounding(store, committed_manifest, committed_artifact_set):
        failures.append(f"committed manifest grounding failure: {failure}")
    for failure in verify_grounding(store, generated_manifest, generated_artifact_set):
        failures.append(f"generated manifest grounding failure: {failure}")
    return failures


def _bootstrapped_store_for_verify():
    from . import context
    from .store import Store

    store = Store()
    store.migrate()
    context.bootstrap(store)
    return store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify OFARM generated manifest artifacts.")
    parser.add_argument(
        "--verify-generated",
        action="store_true",
        help="verify committed manifest JSON against generated output without writing files",
    )
    args = parser.parse_args(argv)
    if not args.verify_generated:
        parser.print_help()
        return 0

    store = _bootstrapped_store_for_verify()
    try:
        failures = verify_generated_artifacts(store)
    finally:
        store.close()

    if failures:
        for failure in failures:
            print(failure)
        print(f"RESULT: FAIL ({len(failures)} failures)")
        return 1
    print("RESULT: PASS (generated manifest artifacts match committed JSON)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
