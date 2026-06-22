# SI Manual-Review Backlog Plan

Status: plan-only backlog document. This file does not move code, change runtime
behavior, update contracts or manifests, alter tests, or change Core, Kernel, or
Platform semantics.

This plan covers the ambiguous SI extraction surfaces left after the inventory,
the SI view artifact move, and Core-neutrality hardening. It is a guide for
future PRs only. Any future implementation must preserve assertion/history-first
truth, governed materialization, evidence, review, correction, freshness,
refusal, and authority rules.

## Classification Legend

| Classification | Meaning |
| --- | --- |
| `KEEP_AS_ACTIVE_RUNTIME_SI_SUPPORT` | Keep in the current runtime because the active implementation is still the SI pilot and moving it would change behavior or generated claims. |
| `PROFILE_LOADER_DESIGN_REQUIRED` | Do not move until there is an explicit active-profile loader or hook design that preserves current behavior. |
| `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` | Candidate for profile-local relocation only after tests, fixtures, or conformance harnesses can follow without coverage loss. |
| `REWORD_ONLY_LATER` | Candidate for comment or documentation neutralization only; no structural move is currently justified. |
| `DO_NOT_TOUCH` | Already correctly placed, protected, or not part of the extraction problem. |

## Manual-Review Areas

| Area | Current SI-specific responsibility | Why not safe in PR B or PR C | Likely classification | Required preconditions | Validation or review risks | Suggested future PR lane |
| --- | --- | --- | --- | --- | --- | --- |
| `kernel/context.py` | Active SI context spine, shipped SI profile instance bootstrap, REGSR/GERK snapshot family constants, and per-farm `ContextSnapshot` assembly. | It is executable runtime support for the current active pilot; moving it would affect bootstrap, AS_OF reconstruction, reference snapshot selection, and materialization basis behavior. | `PROFILE_LOADER_DESIGN_REQUIRED` | Design an active-profile loader contract for profile instance discovery, reference snapshot family registration, context assembly, and AS_OF vintage selection. | High risk of breaking freshness, context closure, and refusal-over-pretending behavior. | PR D1: active-profile loader design memo, then a separate implementation PR. |
| `kernel/demo.py` | Fictional SI-format demo payloads, SI scheme examples, demo product/register refs, and bootstrap data used by runtime examples and tests. | Demo data is coupled to tests and API examples; moving it without a fixture harness would break current validation coverage. | `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` | Create a profile fixture/demo harness and update tests to consume profile-local demo data without changing expected behavior. | Medium/high risk of silently changing test semantics or losing privacy-safe format-true examples. | PR D2: profile fixture harness plan; later move demo payloads. |
| `kernel/sufficiency.py` | Generic sufficiency generation that reads profile policy, but emits SI floor rule refs and SI-facing rationale text. | The mechanism is mixed: some behavior is generic, while displayed policy names and rule refs are SI-specific. | `PROFILE_LOADER_DESIGN_REQUIRED` | Define profile policy metadata for rule-ref prefixes, display labels, and claim statements before neutralizing emitted text. | High risk of changing review/refusal reasons or evidence sufficiency case meaning. | PR D3: evidence policy metadata/display design. |
| `kernel/validators.py` | Validation units include SI unresolved-binding posture, quantity/unit policy text, required SI record fields, and SI crop-binding review behavior. | These validators are executable gate behavior; moving policy out requires explicit profile validation hooks and fixture coverage. | `PROFILE_LOADER_DESIGN_REQUIRED` | Design profile validation hooks for quantity policy, required record fields, crop-binding posture, and unresolved-binding outcomes. | High risk of weakening refusal/review routing or changing promotion behavior. | PR D4: profile validation hook design, then implementation with tests. |
| `kernel/manifest.py` | Builds and verifies the active SI pilot Capability Manifest and ActiveArtifactSet, including REGSR/GERK/FFSNaprave import surfaces. | Generated manifest behavior is protected; moving or generalizing it would alter declared runtime surfaces and grounding checks. | `KEEP_AS_ACTIVE_RUNTIME_SI_SUPPORT` | Define multi-profile manifest generation and grounding rules before any extraction. | High risk of over-claiming support, breaking manifest grounding, or changing active runtime claims. | PR D5: multi-profile manifest design only, if needed. |
| `kernel/tests/**` | Contains active SI pilot engineering tests for imports, bindings, sufficiency, manifest grounding, context AS_OF behavior, and platform conformance. | Tests preserve current behavior; moving them before a profile test harness exists would reduce or confuse validation coverage. | `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` | Establish a profile test-harness convention and decide which tests remain kernel-generic versus profile-specific. | High risk of losing regression coverage or presenting profile tests as generic platform conformance. | PR D6: test-harness split plan. |
| `conformance/**` | Contains package-wide conformance docs/checks plus executed SI pilot evidence files and profile-local artifact validation bindings. | Some conformance is package-wide, some is active SI pilot evidence, and some validates profile-local artifacts; split boundaries are not yet explicit. | `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` | Define conformance lanes for package self-checks, platform MVP evidence, profile design cases, and profile-local executed evidence. | Medium/high risk of mislabeling design cases as executed evidence or dropping evidence-lane history. | PR D7: conformance lane split plan. |

## Related Surfaces

| Area | Current role | Classification | Required precondition before change | Suggested lane |
| --- | --- | --- | --- | --- |
| `kernel/config.py` | Holds active SI profile, pack, policy, code-binding, and snapshot refs as runtime configuration. | `PROFILE_LOADER_DESIGN_REQUIRED` | Active-profile configuration source and override semantics. | Pair with PR D1. |
| `kernel/profile_policy.py` | Generic loader for SI evidence-review policy content, with docstrings still naming the SI floor. | `REWORD_ONLY_LATER` | Complete policy metadata/display design so wording can be neutral without hiding active SI policy content. | Pair with PR D3. |
| `kernel/README.md` | Documents current active SI runtime bootstrap, context spine, and import surfaces. | `REWORD_ONLY_LATER` | Runtime design decisions for active-profile loader and test harness. | Update after PR D1/D6 decisions. |
| `kernel/profiles/si_ffs/**` | Already profile-specific SI runtime adapters and binding wrappers. | `DO_NOT_TOUCH` | None; this is already the profile-specific runtime location. | None. |
| `kernel/adapters.py` | Generic adapter mechanism with explanatory SI examples. | `REWORD_ONLY_LATER` | Confirm examples are not needed to explain current active SI adapter behavior. | Comment-only cleanup after runtime-sensitive lanes settle. |
| `kernel/verification.py` | Generic verification mechanism with explanatory SI binding references. | `REWORD_ONLY_LATER` | Confirm wording can be neutralized without obscuring the active SI wrapper role. | Comment-only cleanup after runtime-sensitive lanes settle. |
| `kernel/policy.py` | Core policy constants with comments that point out SI bindings are not Core law. | `REWORD_ONLY_LATER` | Confirm neutral wording still protects the country/profile separation. | Comment-only cleanup after runtime-sensitive lanes settle. |

## Future Work Order

1. PR D1: active-profile loader design for context/config/profile instance loading.
2. PR D3: profile policy metadata/display design for sufficiency text and rule refs.
3. PR D4: profile validation hook design for validator-owned SI policy behavior.
4. PR D6: profile test-harness split plan, captured in `test_harness_split_plan.md`.
5. PR D7: conformance lane split plan, captured in `conformance_lane_split_plan.md`.
6. PR D2: demo fixture migration plan, captured in `demo_fixture_migration_plan.md`.
7. PR D5: multi-profile manifest design, captured in `multi_profile_manifest_design.md`.
8. Comment-only rewording PRs after runtime-sensitive decisions are complete.

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

## Validation For This Planning PR

Run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

Run the manual audit:

```sh
rg -n "KMG-MID|GERK|Dutch GO|GLMC 7|Gecombineerde Opgave|Slovenia|Slovenian|\bSI\b" CORE.md PLATFORM.md KERNEL.md contracts kernel views conformance README.md AGENTS.md || true
```

The audit is informational. Remaining matches should be explained by existing
profile-local material, review guards, root navigation, or this manual-review
plan. This PR should not run pytest unless needed; if pytest creates a
timestamped `conformance/evidence/platform_mvp_results_*.json`, remove it
before commit because this PR is documentation-only.
