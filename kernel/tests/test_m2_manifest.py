"""M2 P6 — regenerated Capability Manifest / ActiveArtifactSet grounding.

Engineering tests, NOT part of the named conformance suite (test_15 is the named
grounding test). They pin P6: the manifest declares the real M2 import surfaces
(REGSR / GERK / FFSNaprave), each grounded in a scheme the code-binding profile
actually declares; the ActiveArtifactSet lists the now-active PartialExtent
extent-carrier; the regenerated artifacts ground; and nothing over-claims above
the NONE conformance level. All identifiers fictional and format-true.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from types import SimpleNamespace

from kernel import config, manifest
from kernel.runtime_bundle import GLOBAL_CONTENT_PLACEMENT
from kernel.tests import conftest as evidence_conftest


def test_supported_adapter_preload_closes_dynamic_parser_imports():
    script = """
import sys
from kernel import manifest
from kernel.profiles.si_ffs import gerk_adapter, regsr_adapter

manifest.preload_runtime_import_surfaces()
required = {"html", "html.entities", "encodings.cp1250", "encodings.utf_8_sig"}
missing = sorted(required - set(sys.modules))
before = set(sys.modules)
regsr_adapter._parser()
gerk_adapter._parser()
added = sorted(set(sys.modules) - before)
if missing or added:
    raise SystemExit(f"missing={missing!r}, added={added!r}")
"""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=config.PACKAGE_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_manifest_declares_all_m2_import_surfaces(store):
    m = manifest.build_manifest(store)
    imports = {s["targetRef"]
               for s in m["capabilitySections"]["importExportSupport"]["declaredSurfaces"]
               if s["surfaceType"] == "IMPORT_MAPPING"}
    assert {"scheme:si.uvhvvr.ffs-reg.html-surface",   # REGSR (P1)
            "scheme:si.gerk-pid",                       # GERK (P2)
            "scheme:si.ffs-naprave"} <= imports          # FFSNaprave (P3)


def test_artifact_set_lists_active_partial_extent_carrier(store):
    # G7 made the PartialExtent an active extent-carrier; the M2 artifact set lists it
    a = manifest.build_artifact_set()
    assert "contract:ofarm.partialextent.v0.1" in a["activeArtifactRefs"]


def test_grounding_passes_for_regenerated_artifacts(store):
    m = manifest.build_manifest(store)
    a = manifest.build_artifact_set()
    assert manifest.verify_grounding(store, m, a) == []


def test_grounding_uses_retained_global_code_binding_bytes(store):
    # Global immutable package content is deliberately not copied into the
    # tenant record table. Grounding must use the exact component selected by
    # this Store's verified RuntimeBundle and must not fall back to that table.
    assert store.get_payload(config.CODE_BINDING_PROFILE_REF) is None
    component = store.runtime_bundle.component(
        "PROFILE_INSTANCE", config.CODE_BINDING_PROFILE_REF)
    assert component.placement == GLOBAL_CONTENT_PLACEMENT
    profile = manifest._retained_code_binding_profile(store)
    assert profile["agronomicCodeBindingProfileId"] == \
        config.CODE_BINDING_PROFILE_REF

    m = manifest.build_manifest(store)
    a = manifest.build_artifact_set()
    assert manifest.verify_grounding(store, m, a) == []


def test_grounding_rejects_other_tenant_manifest_scope(store):
    m = manifest.build_manifest(store)
    a = manifest.build_artifact_set()
    m["deploymentScope"] = {
        "scopeType": "TENANT", "scopeRef": "tenant:other.invalid"
    }

    failures = manifest.verify_grounding(store, m, a)

    assert "manifest deployment scope does not equal the bound runtime tenant" \
        in failures


def test_generated_artifacts_match_committed_json_after_timestamp_normalization(store):
    assert manifest.verify_generated_artifacts(store) == []


def test_generated_artifact_diff_reports_drift(store):
    generated = manifest.build_manifest(store)
    committed = json.loads(json.dumps(generated))
    committed["manifestId"] = "manifest:drifted.by.test"
    diff = manifest._diff_generated_payload(
        "capability manifest",
        committed,
        generated,
        (("publishedAt",),),
    )
    assert diff is not None
    assert "manifest:drifted.by.test" in diff
    assert "manifestId" in diff


def test_manifest_suite_ref_matches_evidence_writer(store):
    m = manifest.build_manifest(store)
    assert m["conformance"]["testSuiteRefs"] == [manifest.PLATFORM_MVP_TEST_SUITE_REF]
    assert evidence_conftest.PLATFORM_MVP_EVIDENCE_SUITE == manifest.PLATFORM_MVP_TEST_SUITE_REF


def test_platform_evidence_writer_excludes_profile_engineering_tests():
    assert evidence_conftest.is_platform_mvp_evidence_report(SimpleNamespace(
        when="call",
        nodeid="kernel/tests/test_conformance.py::test_01_append_only",
    ))
    assert not evidence_conftest.is_platform_mvp_evidence_report(SimpleNamespace(
        when="call",
        nodeid="kernel/tests/test_profile_harness_bridge.py::test_profile_bridge",
    ))
    assert not evidence_conftest.is_platform_mvp_evidence_report(SimpleNamespace(
        when="call",
        nodeid="profile_si_ffs/tests/m2_si_floor_tests.py::test_floor",
    ))
    assert not evidence_conftest.is_platform_mvp_evidence_report(SimpleNamespace(
        when="setup",
        nodeid="kernel/tests/test_conformance.py::test_01_append_only",
    ))


def test_grounding_rejects_ungrounded_import_surface(store):
    # an import surface for a scheme the code-binding profile does NOT declare is
    # an ungrounded claim — grounding must catch it (revert-proofs the P6 check).
    m = manifest.build_manifest(store)
    a = manifest.build_artifact_set()
    m["capabilitySections"]["importExportSupport"]["declaredSurfaces"].append(
        {"surfaceType": "IMPORT_MAPPING", "targetRef": "scheme:si.not-a-real-scheme",
         "direction": "IMPORT", "status": "SUPPORTED"})
    failures = manifest.verify_grounding(store, m, a)
    assert any("scheme:si.not-a-real-scheme" in f for f in failures)


def test_grounding_rejects_profile_scheme_without_supported_adapter(store):
    # scheme:si.kmg-mid IS a standardRef the code-binding profile declares, but it
    # has NO import adapter (it is captured-identifier vocabulary, not an import
    # surface). Declaring it a SUPPORTED IMPORT_MAPPING must fail grounding — a
    # profile-declared scheme is not importable without a real adapter behind it.
    m = manifest.build_manifest(store)
    a = manifest.build_artifact_set()
    assert "scheme:si.kmg-mid" not in manifest.SUPPORTED_IMPORT_SURFACES
    m["capabilitySections"]["importExportSupport"]["declaredSurfaces"].append(
        {"surfaceType": "IMPORT_MAPPING", "targetRef": "scheme:si.kmg-mid",
         "direction": "IMPORT", "status": "SUPPORTED"})
    failures = manifest.verify_grounding(store, m, a)
    assert any("scheme:si.kmg-mid" in f and "adapter" in f for f in failures)


def test_supported_import_surfaces_drive_the_declared_surfaces(store):
    # the IMPORT_MAPPING surfaces are derived from the single-homed map (not hand-listed)
    m = manifest.build_manifest(store)
    declared = {s["targetRef"] for s in m["capabilitySections"]["importExportSupport"]
                ["declaredSurfaces"] if s["surfaceType"] == "IMPORT_MAPPING"}
    assert declared == set(manifest.SUPPORTED_IMPORT_SURFACES)


def test_manifest_does_not_overclaim_conformance(store):
    # the only grounded level without benchmark evidence is NONE (RFC §11.4)
    m = manifest.build_manifest(store)
    assert m["conformance"]["minimumConformanceLevel"] == "NONE"
