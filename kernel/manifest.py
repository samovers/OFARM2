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
from .profile_runtime import ProfileRuntimeError
from .profile_runtime_provider import load_profile_runtime_services
from .runtime_bundle import RuntimeBundleError, RuntimeComponentRole

PLATFORM_MVP_TEST_SUITE_REF = (
    "conformance:ofarm2.platform-mvp.tests-1-15-plus-regressions.v0_2"
)
_PLATFORM_ACTIVE_ARTIFACT_REFS = (
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
)


def _profile_manifest_context(store):
    """Resolve manifest inputs only through the production profile authority."""
    descriptor = store.active_descriptor
    package_name = config.ACTIVE_PROFILE_PACKAGE_NAME
    if (
        descriptor != config.ACTIVE_PROFILE
        or descriptor.profile_root.name != package_name
        or config.ACTIVE_PROFILE_PACKAGE_NAMES != (package_name,)
    ):
        raise ProfileRuntimeError(
            "manifest assembly requires the code-selected active profile"
        )
    services = load_profile_runtime_services(store, package_name, descriptor)
    try:
        store.runtime_bundle.component(
            RuntimeComponentRole.ADAPTER_SOURCE,
            services.manifest_evidence_specification.source_component_ref,
        )
    except (AttributeError, RuntimeBundleError) as exc:
        raise ProfileRuntimeError(
            "profile manifest input source is absent from the RuntimeBundle"
        ) from exc
    return package_name, descriptor, services


def _profile_output_paths(store):
    _, descriptor, services = _profile_manifest_context(store)
    specification = services.manifest_evidence_specification
    return (
        descriptor.profile_root / specification.manifest_filename,
        descriptor.profile_root / specification.active_artifact_set_filename,
    )


def _view_artifact_refs(output_specification) -> tuple[str, ...]:
    passport = output_specification.passport_view
    document = output_specification.document_assembly
    return (
        passport.view_ref,
        document.view_ref,
        passport.query_specification_ref,
        passport.query_plan_ref,
        document.query_specification_ref,
        document.query_plan_ref,
    )


def _import_bindings(specification) -> dict[str, tuple[str, str]]:
    return {
        target_ref: (adapter_module, component_ref)
        for target_ref, adapter_module, component_ref
        in specification.supported_import_bindings
    }


def build_manifest(store) -> dict:
    _, descriptor, services = _profile_manifest_context(store)
    specification = services.manifest_evidence_specification
    import_bindings = _import_bindings(specification)
    registry_kinds = [k for k in store.registry.kinds()
                      if store.registry.get(k).lane == "canonical"]
    commit_classes = sorted(
        c.lower().replace("_", " ") for c in COMMIT_CLASS_TO_FAMILY)
    event_families = sorted(set(COMMIT_CLASS_TO_FAMILY.values()))
    return {
        "schemaVersion": "ofarm.capabilitymanifest.v0.1",
        "manifestId": specification.manifest_id,
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
                "activePackRefs": [descriptor.pack_ref],
                "activeProfileRefs": [descriptor.profile_ref],
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
                    {"surfaceType": "IMPORT_MAPPING", "targetRef": target,
                     "direction": "IMPORT", "status": "SUPPORTED"}
                    for target in import_bindings
                ] + [
                    {"surfaceType": "EXPORT_MAPPING",
                     "targetRef":
                         services.output_specification.document_assembly.view_ref,
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
            "activeArtifactSetRef": descriptor.active_artifact_set_ref,
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
            "declaredProfileRefs": [descriptor.profile_ref],
        },
    }


def build_artifact_set(store) -> dict:
    """Build the active artifact set from platform and profile authorities."""
    _, descriptor, services = _profile_manifest_context(store)
    specification = services.manifest_evidence_specification
    shipped_snapshots = tuple(
        family.shipped_snapshot_ref
        for family in descriptor.reference_families
        if family.shipped_snapshot_ref is not None
    )
    return {
        "schemaVersion": "ofarm.activeartifactset.v0.1",
        "activeArtifactSetId": descriptor.active_artifact_set_ref,
        "generatedAt": now_iso(),
        "deploymentScope": {"scopeType": "TENANT", "scopeRef": config.TENANT_REF},
        "artifactRegistryRef": "registry:ofarm2-implementation-package.v0_1",
        "activePackRefs": [descriptor.pack_ref],
        "activeProfileRefs": [descriptor.profile_ref],
        "activeArtifactRefs": [
            *_PLATFORM_ACTIVE_ARTIFACT_REFS,
            *_view_artifact_refs(services.output_specification),
            descriptor.evidence_policy_ref,
            descriptor.code_binding_profile_ref,
            *shipped_snapshots,
            specification.manifest_id,
        ],
        "sourcePackActivationSetRefs": [descriptor.pack_activation_set_ref],
        "notes": specification.artifact_set_notes,
    }


def verify_grounding(store, manifest: dict, artifact_set: dict) -> list[str]:
    """Manifest-grounding check (conformance test 15): every claim the
    manifest makes must match the ActiveArtifactSet and the real runtime."""
    _, descriptor, services = _profile_manifest_context(store)
    specification = services.manifest_evidence_specification
    import_bindings = _import_bindings(specification)
    failures = []
    if manifest.get("manifestId") != specification.manifest_id:
        failures.append("manifest identity differs from the active profile")
    if manifest["registryRelation"]["activeArtifactSetRef"] != \
            artifact_set["activeArtifactSetId"]:
        failures.append("manifest does not reference the regenerated artifact set")
    if artifact_set["activeArtifactSetId"] != descriptor.active_artifact_set_ref:
        failures.append("artifact set identity differs from the active profile")
    refs = set(artifact_set["activeArtifactRefs"])
    if specification.manifest_id not in refs:
        failures.append("artifact set does not list the manifest")
    for ref in _view_artifact_refs(services.output_specification):
        if ref not in refs:
            failures.append(f"artifact set missing authored view artifact {ref}")
    if manifest["conformance"]["declaredProfileRefs"] != [descriptor.profile_ref]:
        failures.append("manifest profile claim differs from the active profile")
    if artifact_set["activeProfileRefs"] != [descriptor.profile_ref]:
        failures.append("artifact set profile claim differs from the active profile")
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
    # profile-owned import binding whose adapter imports — so the SUPPORTED claim
    # is grounded in actual import support, not
    # just profile vocabulary (M2 P6 steward re-review).
    import_targets = [s["targetRef"] for s in manifest["capabilitySections"]
                      ["importExportSupport"]["declaredSurfaces"]
                      if s["surfaceType"] == "IMPORT_MAPPING"]
    if set(import_targets) != set(import_bindings):
        failures.append("manifest import surfaces differ from the active profile")
    profile = store.get_payload(descriptor.code_binding_profile_ref)
    scheme_refs = _standard_refs(profile) if profile is not None else None
    if scheme_refs is None:
        failures.append("code-binding profile not loaded; cannot ground import surfaces")
    for target in import_targets:
        if scheme_refs is not None and target not in scheme_refs:
            failures.append(f"import surface {target} is not a scheme the code-binding "
                            "profile declares (ungrounded import-surface claim)")
        binding = import_bindings.get(target)
        if binding is None:
            failures.append(f"import surface {target} has no supported import adapter "
                            "in the active profile — a profile-declared "
                            "scheme without an adapter cannot be a SUPPORTED import surface")
        else:
            adapter, component_ref = binding
            try:
                store.runtime_bundle.component(
                    RuntimeComponentRole.ADAPTER_SOURCE,
                    component_ref,
                )
            except (AttributeError, RuntimeBundleError):
                failures.append(
                    f"import surface {target} adapter is absent from the "
                    "RuntimeBundle"
                )
                continue
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
    artifact_set = build_artifact_set(store)
    manifest_path, artifact_set_path = _profile_output_paths(store)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    artifact_set_path.write_text(json.dumps(artifact_set, indent=2) + "\n")
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
    generated_artifact_set = build_artifact_set(store)
    manifest_path, artifact_set_path = _profile_output_paths(store)

    committed_manifest, load_failures = _load_committed_json(
        manifest_path, "committed capability manifest")
    failures.extend(load_failures)
    committed_artifact_set, load_failures = _load_committed_json(
        artifact_set_path, "committed active artifact set")
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
    from .runtime_activation import complete_store_startup
    from .runtime_bundle import RuntimeBundleBuilder
    from .store import Store

    store = Store(
        tenant_ref=config.TENANT_REF,
        runtime_bundle=RuntimeBundleBuilder.from_manifest(config.PACKAGE_ROOT).build(),
        active_descriptor=config.ACTIVE_PROFILE,
    )
    complete_store_startup(store)
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
