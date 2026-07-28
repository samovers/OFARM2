"""Profile-owned inputs for the active Slovenian capability artifacts."""
from __future__ import annotations

from ...profile_runtime_services import ProfileManifestEvidenceSpecification


SI_MANIFEST_EVIDENCE_SPECIFICATION = ProfileManifestEvidenceSpecification(
    manifest_id="manifest:si.ffs.pilot.v0_1",
    manifest_filename="OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json",
    active_artifact_set_filename=(
        "OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json"
    ),
    source_component_ref="python:profile-si-ffs-v0_1:manifest-inputs",
    supported_import_bindings=(
        (
            "scheme:si.uvhvvr.ffs-reg.html-surface",
            "kernel.profiles.si_ffs.regsr_adapter",
            "python:profile-si-ffs-v0_1:regsr-adapter",
        ),
        (
            "scheme:si.gerk-pid",
            "kernel.profiles.si_ffs.gerk_adapter",
            "python:profile-si-ffs-v0_1:gerk-adapter",
        ),
        (
            "scheme:si.ffs-naprave",
            "kernel.profiles.si_ffs.ffsnaprave_adapter",
            "python:profile-si-ffs-v0_1:ffsnaprave-adapter",
        ),
    ),
    artifact_set_notes=(
        "Current active SI artifact set generated/verified from runtime "
        "surfaces: the operation/record contracts (incl. the PartialExtent "
        "extent-carrier now active for partial-extent bounds, G7), the four "
        "authored QuerySpecification/QueryPlanIR view artifacts, the "
        "Capability Manifest (which declares the REGSR/GERK/FFSNaprave "
        "import surfaces and inspection-register export), the evidence-review "
        "floor policy, both shipped ReferenceSnapshots, and the cut SI "
        "code-binding profile. "
        "Unsupported-surface posture: see UNSUPPORTED_SURFACES.md (manifest "
        "contract carries no free text)."
    ),
    profile_executed_evidence_refs=(),
)
