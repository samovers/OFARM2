# Multi-Profile Manifest Design Status

Status: documentation-only D5 status memo. This file records the manifest
boundary and navigation-index status, but does not change `kernel/manifest.py`,
regenerate manifests, update contracts, move runtime adapters, change tests, or
alter Core, Kernel, Platform, or active SI pilot semantics.

This began as the PR D5 follow-up from `manual_review_backlog_plan.md`. It
records the design boundary needed before the current active SI pilot manifest
generation could support more than one profile without over-claiming runtime
capability. It also records that D5a/D5b documentation-only guardrails now
exist: `manifest_implementation_checklist.md` and
`profile_navigation_index.json`.

## Goal

Define a future manifest boundary for a runtime that might eventually host more
than the active SI pilot.

The current runtime remains single-profile SI pilot support. The current
Capability Manifest and ActiveArtifactSet are grounded in:

- the active SI runtime descriptor;
- the actual contract registry;
- the actual gate/action mappings;
- active SI view artifacts;
- active SI import adapters;
- package self-check and platform MVP evidence.

D5 does not authorize changing any of that. It only records what a later
multi-profile design would need to prove before implementation.

## Current Manifest Surfaces

| Surface | Current role | D5 treatment |
| --- | --- | --- |
| `kernel/manifest.py` | Builds the active SI pilot Capability Manifest and ActiveArtifactSet from runtime surfaces. | Keep as active runtime SI support. No code change in D5. |
| `profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json` | Authored/generated SI pilot manifest snapshot. | Do not regenerate in D5. |
| `profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json` | Active artifact set for the SI pilot. | Do not regenerate in D5. |
| `kernel/tests/test_m2_manifest.py` | Engineering tests pinning grounded SI manifest behavior. | Keep root-owned until a later manifest harness exists. |
| `kernel/tests/test_conformance.py::test_15_manifest_grounding` | Platform MVP manifest grounding check. | Keep root conformance behavior unchanged. |
| `profile_nl_go_glmc7_2026/**` | Narrow NL profile slice, not active runtime manifest support. | Must not be added to active runtime manifest claims. |

## Future Manifest Boundary

A later implementation should separate at least three concepts:

- **active runtime manifest**: what this runtime can actually execute now;
- **profile package descriptors**: authored profile-local inputs and artifacts;
- **non-active profile design slices**: source/legal/design material that is not
  active runtime capability.

The manifest may only claim active runtime capability for a profile when all
required runtime surfaces are present and grounded:

- active profile descriptor;
- active pack and profile refs;
- active artifact set coherence;
- evidence policy and validation policy hooks;
- view/query artifacts if claimed;
- import/export adapters if claimed;
- root or profile test harness coverage;
- executed evidence lane defined by D7 if claiming executed profile evidence.

## Proposed Future Shape

A future multi-profile manifest design may use one of these approaches:

| Approach | Description | Risk |
| --- | --- | --- |
| Separate manifests per active profile | Keep one manifest per active runtime profile/package. | Lowest over-claim risk, but needs explicit discovery. |
| Root aggregate manifest plus profile manifests | Root manifest lists active profile manifests and package-wide Kernel capabilities. | Requires strict distinction between package capability and profile capability. |
| Single expanded manifest | One manifest carries multiple profile sections. | Highest over-claim risk unless contract shape changes are approved. |

The smallest safe future path is likely separate profile manifests plus a root
index that only lists manifests for active runtime profiles.

## Navigation-Only Naming Guard

D5b added `profile_navigation_index.json`, a profile navigation index, not a
profile manifest. It is labeled as navigation-only and non-capability in both
machine-visible metadata and prose:

- `artifactKind: "profile_navigation_index"`;
- `navigationOnly: true`;
- `capabilityClaim: false`;
- `runtimeSupport: false`;
- prose states that the index is not a manifest, not generated output, not
  runtime support, and not evidence of active capability.

## Grounding Rules

Any future implementation must prove:

- a profile listed as active has a runtime descriptor and coherent active spine;
- `activePackRefs` and `activeProfileRefs` match the selected active artifact
  set and pack activation set;
- import surfaces are declared only when a real adapter exists and imports;
- view/export surfaces are declared only when the referenced artifacts exist and
  are active;
- conformance claims do not exceed executed evidence;
- design-only profile slices are never listed as active runtime capability;
- unsupported surfaces remain unclaimed rather than described as future support.

The current `minimumConformanceLevel: "NONE"` posture must remain unless a later
accepted evidence standard supports a stronger claim.

## NL Profile Slice Guard

The Netherlands GO + GLMC 7 slice is a legal-source/profile slice, not active
runtime support. A future manifest implementation must not add it to:

- `activeProfileRefs`;
- active artifact sets;
- runtime import/export surfaces;
- platform MVP conformance claims;
- generated manifest outputs;
- active SI pilot runtime descriptors.

If a later NL runtime profile is ever implemented, it needs its own active
runtime descriptor, test harness, evidence lane, and manifest grounding.

## Stop Conditions

Stop and re-plan if implementation would require:

- contract schema changes without explicit approval;
- generated manifest updates in a design-only PR;
- adding non-active profile slices to active runtime claims;
- changing current SI manifest ids, artifact refs, or conformance posture;
- removing `minimumConformanceLevel: "NONE"` without accepted evidence;
- weakening import-surface grounding;
- moving manifest tests without D6 harness support;
- changing platform MVP conformance behavior;
- claiming Slovenia production readiness or whole-Netherlands runtime readiness.

## Implemented And Future PR Lanes

| PR lane | Status | Stop condition |
| --- | --- | --- |
| D5a | Implemented as `manifest_implementation_checklist.md`. | Stop if checklist language could allow hand-claimed active runtime capability manifests. |
| D5b | Implemented as `profile_navigation_index.json`. | Stop if the navigation artifact could be read as runtime support, generated manifest output, or capability. |
| D5c | Future: add profile-manifest generation hooks after multiple active runtime profiles exist. | Stop unless active descriptors, tests, and evidence lanes exist. |
| D5d | Future: split manifest tests after manifest and harness boundaries are explicit. | Stop if root conformance test 15 changes meaning. |

## Validation Expectations

For documentation-only status updates to this file, run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

For any future implementation touching `kernel/manifest.py`, active artifact
sets, or manifest tests, also run:

```sh
.venv/bin/python -m pytest kernel/tests/ -q
```

If a docs-only status PR accidentally creates
`conformance/evidence/platform_mvp_results_*.json`, remove that new generated
evidence before commit unless the PR intentionally changes executable evidence
grounding.

## Invariants To Preserve

- Capability claims must be grounded in active runtime surfaces.
- Design slices are not runtime capability.
- Generated manifests are not edited in planning PRs.
- Assertion/history-first truth remains canonical.
- Governed materialization remains Kernel-owned.
- Authority, review, correction, freshness, refusal, and evidence behavior are
  not weakened.
- Country/profile law stays in profile packages, not Core, Kernel, Platform, or
  generated manifest semantics.
