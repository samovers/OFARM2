# MP6 Manifest Generation Plan

Status: documentation-only MP6 planning record. This file does not change
`kernel/manifest.py`, regenerate manifests, update active artifact sets, update
contracts, update schemas, alter tests, write evidence, change runtime behavior,
activate a second profile, or expand capability claims.

This MP6 plan extends `multi_profile_manifest_design.md`; it does not supersede
that D5 status memo, regenerate manifests, or reopen manifest schema design.

## Goal

Define the future manifest-generation boundary for active profiles before any
multi-profile manifest implementation exists.

MP6 must preserve the existing manifest claim discipline: active runtime
capability manifests are approved generated or generator-verified outputs
grounded in actual runtime surfaces. They are never hand-claimed from docs,
navigation indexes, harness discovery, design-only slices, or planning records.

## Status And Boundary

The current runtime remains the single-active-SI pilot. Current manifest
generation and grounding remain owned by the existing SI runtime surfaces.

This PR must not modify:

- `kernel/manifest.py`;
- `profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json`;
- `profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json`;
- `kernel/tests/test_m2_manifest.py`;
- `kernel/tests/test_conformance.py`;
- any `conformance/evidence/platform_mvp_results_*.json`.

Root conformance test 15 remains the current manifest-grounding check. The
current `minimumConformanceLevel: "NONE"` posture remains unchanged.

## Vocabulary

| Term | Meaning | Boundary |
| --- | --- | --- |
| Active runtime manifest | A generated or generator-verified manifest for what the current runtime can execute now. | Must be grounded in active runtime surfaces, not docs or plans. |
| Active artifact set | The active artifact set referenced by the selected active profile. | Must remain coherent with active pack/profile refs. |
| Design-only profile slice | Profile-local legal/design/source material without executable runtime support. | Must not appear in active manifest refs or capability claims. |
| Navigation/support artifact | README, navigation index, harness descriptor, design note, or plan. | Never a manifest input by itself. |

## Future Manifest Input Rules

A future manifest implementation may claim capability for an active profile only
when the claim is grounded in all relevant active runtime surfaces:

- active runtime descriptor loaded fail-closed;
- coherent active pack, profile, pack activation set, and active artifact set
  refs;
- profile-owned evidence policy and validation policy for claimed profile
  behavior;
- real adapters for every claimed import/export surface;
- real view/query artifacts for every claimed view/query surface;
- root or profile harness coverage for claimed surfaces;
- an executed evidence lane if executed profile evidence is claimed.

Harness discovery, test execution, and profile executed evidence are necessary
inputs only when claimed, but none of them automatically creates a manifest
capability claim. Capability claims still require adapter, artifact, and runtime
grounding.

Do not use any of the following as manifest capability inputs:

- `profile_navigation_index.json`;
- README files;
- extraction inventory plans;
- profile harness descriptors;
- design-only source/profile slices;
- profile evidence plans;
- source manifests not verified by an approved generator/check.

## Future Implementation Shape

The preferred future shape remains separate manifests per active profile plus a
root aggregate index only after real multi-profile runtime support exists.

A later implementation PR must:

- state whether it changes runtime behavior, generated outputs, schema, tests,
  or evidence;
- run `python3 -m kernel.manifest --verify-generated`, or an explicitly
  approved equivalent, for any change touching manifest generation, committed
  generated manifest JSON, active artifact sets, or manifest grounding tests;
- keep the current SI manifest behavior assertion-equivalent unless the PR
  explicitly scopes an SI manifest change;
- keep design-only slices, including `profile_nl_go_glmc7_2026`, out of active
  manifest refs and capability claims;
- avoid contract or schema changes unless explicitly approved with migration
  notes;
- avoid strengthening conformance claims without accepted evidence;
- keep unsupported surfaces unclaimed rather than described as future support.

## Stop Conditions

Stop and re-plan if a future PR would:

- hand-author an active runtime capability manifest;
- add a design-only profile slice to active manifest refs;
- use navigation, README, harness, source, or planning artifacts as capability
  grounding by themselves;
- claim import/export/view/query support before the runtime surface exists and
  is tested;
- regenerate manifest outputs in a planning PR;
- change active artifact sets without an explicit generated-output PR;
- change root conformance test 15 meaning without an approved manifest-grounding
  design;
- change manifest schema without explicit approval and migration notes;
- claim Slovenia production readiness, Netherlands production readiness, or
  multi-profile runtime readiness.

## Non-Claims

This plan and PR do not claim or create:

- generated manifest updates;
- active artifact set updates;
- a second active profile;
- Netherlands runtime support;
- profile capability expansion;
- platform MVP conformance changes;
- profile executed evidence;
- manifest schema changes;
- Slovenia production readiness;
- Netherlands production readiness;
- L5 Core country/profile neutrality certification.

## Validation For This Plan

For this documentation-only plan, run:

```sh
python3 conformance/ofarm_profile_extraction_consistency_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --cached --check
```

For future implementation PRs touching `kernel/manifest.py`, generated manifest
JSON, active artifact sets, or manifest grounding tests, also run:

```sh
python3 -m kernel.manifest --verify-generated
```

The command must be non-writing by default and may normalize only `publishedAt`
on the Capability Manifest and `generatedAt` on the ActiveArtifactSet. It must
fail if committed generated artifacts differ from generator output.

Do not run pytest unless a reviewer asks. If pytest is accidentally run and
creates `conformance/evidence/platform_mvp_results_*.json`, remove that new
generated evidence file before commit because this plan does not change evidence
grounding.
