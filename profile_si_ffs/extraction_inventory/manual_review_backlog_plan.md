# SI Manual-Review Backlog Status

Status: documentation-only backlog status record. This file does not move code,
change runtime behavior, update contracts or generated manifests, alter tests,
or change Core, Kernel, or Platform semantics.

This began as the manual-review backlog for ambiguous SI extraction surfaces
left after the inventory, the SI view artifact move, and Core-neutrality
hardening. It now records which D-lane follow-ups have landed and which
runtime-sensitive areas remain intentionally root-owned or future-scoped.

Any future implementation must preserve assertion/history-first truth, governed
materialization, evidence, review, correction, freshness, refusal, and authority
rules.

## Classification Legend

| Classification | Meaning |
| --- | --- |
| `KEEP_AS_ACTIVE_RUNTIME_SI_SUPPORT` | Keep in the current runtime because the active implementation is still the SI pilot and moving it would change behavior or generated claims. |
| `PROFILE_LOADER_DESIGN_REQUIRED` | Do not move until there is an explicit active-profile loader or hook design that preserves current behavior. Some D1 preconditions are now implemented, but this remains relevant for broader multi-profile or loader-generalization work. |
| `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` | Candidate for profile-local relocation only after tests, fixtures, or conformance harnesses can follow without coverage loss. D2/D6 implemented parts of this, while some root facades and bridges remain. |
| `REWORD_ONLY_LATER` | Candidate for comment or documentation neutralization only; no structural move is currently justified. |
| `DO_NOT_TOUCH` | Already correctly placed, protected, or not part of the extraction problem. |

## Follow-Up Status

These rows are status records for prior D-lane work. They are not fresh
validation evidence by themselves; the backing references below identify the
files, tests, and commits that should be checked when a future PR relies on an
implemented-status claim.

| Lane | Current status record | Remaining boundary |
| --- | --- | --- |
| D1 active-profile loader | Prior implemented boundary recorded in `active_profile_loader_design.md`. The active SI runtime descriptor and loader exist. | No multi-profile activation or broad country abstraction. Root context assembly remains Kernel-owned. |
| D2 demo fixtures | Prior D2a-D2d boundary recorded in `demo_fixture_migration_plan.md`. Profile-local fixture refs, records, payload builders, and facade exist. | `kernel/demo.py` remains the public compatibility facade until any D2e-style cleanup proves root callers can migrate safely. |
| D3 evidence display metadata | Prior implemented boundary recorded in `evidence_policy_metadata_display_design.md`. SI sufficiency display metadata is profile-owned. | Kernel sufficiency mechanics remain generic and root-owned. |
| D4 validation policy metadata | Prior implemented boundary recorded in `validator_policy_hook_design.md`. SI validator values and text are profile-owned. | Validator order and mechanics remain Kernel-owned; registry-family reverification policy is not moved. |
| D5 manifest boundary | D5 design, D5a checklist, and D5b navigation index are recorded in `multi_profile_manifest_design.md`, `manifest_implementation_checklist.md`, and `profile_navigation_index.json`. | No generated manifest change, profile manifest generation, or runtime capability claim for design-only slices. |
| D6 test harness | Prior implemented boundary recorded in `test_harness_split_plan.md`. Profile-local SI engineering test modules and root discovery bridges exist. | Root evidence writer and remaining root active-runtime tests stay root-owned. |
| D7 conformance lanes | Root lane map and evidence README boundary recorded in `conformance_lane_split_plan.md`. | No profile-local executed evidence writer or profile conformance evidence lane yet. |

## Evidence Backing For Status Records

| Lane | Primary status document | Evidence references |
| --- | --- | --- |
| D1 active-profile loader | `active_profile_loader_design.md` | `kernel/tests/test_profile_runtime_loader.py`; implementation PR validation should include `.venv/bin/python -m pytest kernel/tests/ -q`. |
| D2 demo fixtures | `demo_fixture_migration_plan.md` | `kernel/tests/test_profile_si_demo_refs.py`, `kernel/tests/test_profile_si_demo_records.py`, `kernel/tests/test_profile_si_demo_payloads.py`; profile modules under `profile_si_ffs.tests.d2_demo_fixture_*`. |
| D3 evidence display metadata | `evidence_policy_metadata_display_design.md` | `kernel/tests/test_m2_si_floor.py`; profile module `profile_si_ffs.tests.m2_si_floor_tests`; implementation PR validation should include `.venv/bin/python -m pytest kernel/tests/ -q`. |
| D4 validation policy metadata | `validator_policy_hook_design.md` | Commits `5518f55`, `6390093`, `34413c6`; `kernel/tests/test_m2_si_validation_policy.py`; profile module `profile_si_ffs.tests.m2_si_validation_policy_tests`. |
| D5 manifest boundary | `multi_profile_manifest_design.md`, `manifest_implementation_checklist.md`, `profile_navigation_index.json` | Navigation-only/status design record. No generated manifest or runtime capability implementation is claimed by D5b. |
| D6 test harness | `test_harness_split_plan.md` | Commits `b5f54c0`, `63e6430`, `45b3a50`, `3c98188`, `a21fed8`, `f82820c`; `kernel/tests/test_profile_harness_bridge.py`; root bridge files in `kernel/tests/`. |
| D7 conformance lanes | `conformance_lane_split_plan.md` | Commits `1cc0383`, `01eee6b`, `9e3e5cc`, `556ce39`, `5759b46`, `5e88394`, `8ff6d53`, `f82820c`; `conformance/CONFORMANCE.md`; `conformance/evidence/README.md`; `conformance/evidence/platform_mvp_results_*.json`. |

## Manual-Review Areas

| Area | Current SI-specific responsibility | Current status | Remaining classification | Preconditions before future change | Validation or review risks |
| --- | --- | --- | --- | --- | --- |
| `kernel/context.py` | Active SI context spine, shipped SI profile instance bootstrap, REGSR/GERK snapshot family metadata, and per-farm `ContextSnapshot` assembly. | D1 moved active runtime inputs into `profile_si_ffs/runtime_profile_descriptor.json`; context assembly remains Kernel-owned and descriptor-backed. | `KEEP_AS_ACTIVE_RUNTIME_SI_SUPPORT` plus future `PROFILE_LOADER_DESIGN_REQUIRED` for broader loader work. | Any future move needs explicit multi-profile loader design, AS_OF equivalence tests, and context-spine coherence tests. | High risk of breaking freshness, context closure, and refusal-over-pretending behavior. |
| `kernel/demo.py` | Public compatibility facade for fictional SI-format demo payloads, SI scheme examples, demo product/register refs, bootstrap, and onboarding. | D2a-D2d moved fixture construction behind `profile_si_ffs/test_fixtures/**`; `kernel.demo` still delegates and remains public. | `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` for optional D2e facade shrink only. | Root callers and API examples must be migrated or proven unaffected before shrinking the facade. | Medium/high risk of silently changing test semantics or losing privacy-safe format-true examples. |
| `kernel/sufficiency.py` | Generic sufficiency generation that reads profile policy and builds `EvidenceSufficiencyCase` records. | D3 moved SI display strings, rule refs, labels, and selected reason-code mappings into profile policy metadata. | `KEEP_AS_ACTIVE_RUNTIME_SI_SUPPORT` for Kernel mechanics; `REWORD_ONLY_LATER` for comments only if needed. | Any future change must preserve decisions and governed fail-closed behavior. | High risk of changing review/refusal reasons or evidence sufficiency case meaning. |
| `kernel/validators.py` | Generic validator units for quantity/unit policy, record-field completeness, binding posture, and active SI validation text. | D4 moved SI validator values and text into profile validation metadata; validator order and mechanics remain Kernel-owned. | `KEEP_AS_ACTIVE_RUNTIME_SI_SUPPORT` for validator mechanics; registry-family reverification remains future-scoped. | Any future hook must preserve validation order, refusal/review outcomes, and fail-closed policy loading. | High risk of weakening refusal/review routing or changing promotion behavior. |
| `kernel/manifest.py` | Builds and verifies the active SI pilot Capability Manifest and ActiveArtifactSet, including REGSR/GERK/FFSNaprave import surfaces. | D5/D5a/D5b documented the manifest boundary and navigation-only index. Runtime manifest generation remains active SI pilot support. | `KEEP_AS_ACTIVE_RUNTIME_SI_SUPPORT`. | Multi-profile manifest generation design, active descriptors, tests, and evidence lanes before any generation change. | High risk of over-claiming support, breaking manifest grounding, or changing active runtime claims. |
| `kernel/tests/**` | Root tests plus root bridge files for active SI pilot engineering tests, profile-local SI modules, manifest grounding, context AS_OF behavior, and platform conformance. | D6 moved several SI engineering test bodies into `profile_si_ffs/tests/**` while root bridges preserve default discovery. | `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` only for future splits that keep coverage intact; root generic tests stay root-owned. | Any future move must preserve root collection, test meaning, and evidence writer semantics. | High risk of losing regression coverage or presenting profile tests as generic platform conformance. |
| `conformance/**` | Package-wide conformance docs/checks plus executed platform MVP evidence files and inherited fixtures. | D7 documented root lanes and evidence labels. No evidence writer or profile evidence lane moved. | `KEEP_AS_ACTIVE_RUNTIME_SI_SUPPORT` for root platform MVP evidence; future profile evidence needs explicit design. | Define a profile evidence writer and suite id before any profile-local executed evidence. | Medium/high risk of mislabeling design cases as executed evidence or dropping evidence-lane history. |

## Related Surfaces

| Area | Current role | Current status | Suggested lane |
| --- | --- | --- | --- |
| `kernel/config.py` | Holds active SI profile root and active deployment/demo binding. | D1 made active profile refs descriptor-backed while tenant binding remains separate runtime config. | Keep as active runtime SI support unless broader loader work is explicitly scoped. |
| `kernel/profile_policy.py` | Generic loader for profile-owned evidence-review and validation policy content. | D3/D4 made display and validation metadata fail-closed profile content. | Keep generic loader root-owned; reword comments only if useful. |
| `kernel/README.md` | Documents current active SI runtime bootstrap, context spine, and import surfaces. | Still a possible docs cleanup surface. | `REWORD_ONLY_LATER`. |
| `kernel/profiles/si_ffs/**` | Already profile-specific SI runtime adapters and binding wrappers. | Already correctly placed. | `DO_NOT_TOUCH`. |
| `kernel/adapters.py` | Generic adapter mechanism with explanatory SI examples. | Comment-only neutralization remains optional. | `REWORD_ONLY_LATER`. |
| `kernel/verification.py` | Generic verification mechanism with explanatory SI binding references. | Comment-only neutralization remains optional. | `REWORD_ONLY_LATER`. |
| `kernel/policy.py` | Core policy constants with comments that point out SI bindings are not Core law. | Comment-only neutralization remains optional and must preserve the country/profile separation. | `REWORD_ONLY_LATER`. |

## Remaining Work Order

1. Optional D2e: shrink `kernel/demo.py` only after root callers and API examples are proven safe.
2. Optional D5c/D5d: design real profile-manifest generation hooks or split manifest tests only after multiple active runtime profiles and evidence lanes exist.
3. Optional D7 future: add profile-local executed evidence only after an approved profile evidence writer and suite id exist.
4. Optional comment-only rewording: neutralize explanatory SI examples in Kernel docs/comments when doing so will not hide active SI pilot behavior.

## Stop Conditions

Stop and re-plan if a future PR would require any of the following without an
approved design first:

- Core, Kernel, or Platform semantic changes.
- Contract edits or generated manifest updates.
- Runtime adapter behavior changes.
- Loss of current SI pilot validation coverage.
- Moving active SI support into a generic country abstraction.
- Any claim of Slovenia production readiness.
- Any weakening of assertion/history-first truth, governed current-state
  materialization, evidence, review, correction, freshness, refusal, or
  authority rules.

## Validation For Documentation-Only Status Updates

Run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

Run the manual audit when a future PR changes Core-facing wording:

```sh
rg -n "KMG-MID|GERK|Dutch GO|GLMC 7|Gecombineerde Opgave|Slovenia|Slovenian|\bSI\b" CORE.md PLATFORM.md KERNEL.md contracts kernel views conformance README.md AGENTS.md || true
```

The audit is informational. Remaining matches should be explained by existing
profile-local material, review guards, root navigation, or this manual-review
backlog. This PR should not run pytest unless needed; if pytest creates a
timestamped `conformance/evidence/platform_mvp_results_*.json`, remove it
before commit because this PR is documentation-only.
