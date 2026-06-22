# SI Test-Harness Split Plan

Status: plan-only document. This file does not move tests, change runtime
behavior, update contracts or manifests, regenerate evidence, alter Core,
Kernel, or Platform semantics, or claim Slovenia production readiness.

This is the PR D6 follow-up from `manual_review_backlog_plan.md`. It defines the
smallest future harness boundary needed before SI-specific engineering tests and
demo fixtures can move out of `kernel/tests/**` or `kernel/demo.py` without
losing coverage.

## Goal

Separate three ideas that are currently co-located in root test files:

- Kernel-generic behavior tests that should stay root-owned;
- active SI pilot runtime support tests that may remain root-owned until a
  profile harness exists;
- profile-specific SI adapter, policy, descriptor, and fixture tests that can
  later move under `profile_si_ffs/` once they remain discoverable by the root
  test command.

The first implementation after this plan should preserve the current active SI
pilot behavior and the current test count. It should not create a universal
country abstraction layer, move demo payloads by itself, or reclassify design
fixtures as executed platform evidence.

## Proposed Harness Boundary

A future implementation may add profile-local test support such as:

- `profile_si_ffs/tests/` for SI profile engineering tests;
- `profile_si_ffs/test_fixtures/` or profile-local fixture helpers for
  fictional, format-true SI payloads;
- a root-owned pytest collection bridge or explicit root test command so
  profile tests still run in CI with `python -m pytest kernel/tests/ -q` or a
  documented successor command;
- a fixture API that imports active profile runtime descriptor values instead of
  copying SI refs into generic Kernel constants.

The harness is execution support only. It must not define OFARM law, modify
contracts, generate manifests, emit accepted records, or become a hidden truth
store.

## Current Test Areas

| Area | Current role | Likely future lane | Preconditions before move |
| --- | --- | --- | --- |
| `kernel/tests/conftest.py` | Root pytest store, bootstrap, demo setup, and platform evidence writer. | `KEEP_ROOT_HARNESS` | D7 conformance lane split must define evidence ownership before changing evidence writer behavior. |
| `kernel/tests/test_conformance.py` | Named platform MVP conformance suite and evidence source. | `KEEP_ROOT_CONFORMANCE` | D7 must preserve executed-evidence semantics and avoid mixing profile design cases into platform evidence. |
| `kernel/tests/test_profile_runtime_loader.py` | Active SI profile descriptor and context-spine loader tests. | `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` for descriptor-specific cases; keep root coverage bridge. | Profile test discovery must run these tests by default, and descriptor bootstrap equivalence must remain pinned. |
| `kernel/tests/test_m2_si_regsr.py` | SI REGSR adapter/import tests. | `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` | Profile-local adapter test harness and fixture artifact helpers. |
| `kernel/tests/test_m2_si_gerk.py` | SI GERK layer adapter/import tests. | `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` | Profile-local adapter test harness and fixture artifact helpers. |
| `kernel/tests/test_m2_si_ffsnaprave.py` | SI FFS naprave inspection adapter/import tests. | `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` | Profile-local adapter test harness and fixture artifact helpers. |
| `kernel/tests/test_m2_si_bindings.py` | SI binding wrapper behavior and active profile binding semantics. | `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` | Profile-local binding fixture helpers and unchanged promotion/review expectations. |
| `kernel/tests/test_m2_si_floor.py` | Active SI evidence floor policy, display metadata, advisory, and fallback trace tests. | `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` | Profile policy tests must still run with malformed-policy fail-closed coverage. |
| `kernel/tests/test_m2_si_validation_policy.py` | Active SI validation policy metadata tests. | `MOVE_TO_PROFILE_AFTER_HARNESS_EXISTS` | Profile policy tests must still prove wrong-kind refs hard-refuse and unknown keys fail closed. |
| `kernel/tests/test_m2_manifest.py` | Active SI pilot manifest behavior and non-overclaiming posture. | `KEEP_AS_ACTIVE_RUNTIME_SI_SUPPORT` until D5. | Multi-profile manifest design before any relocation or split. |
| `kernel/tests/test_m2_adapters.py` | Generic adapter mechanics plus active-profile examples. | `SPLIT_LATER` | Extract generic adapter tests from profile-specific examples without changing import semantics. |
| `kernel/tests/test_m2_bindings.py` | Generic reference-snapshot and binding mechanics with fixture families. | `SPLIT_LATER` | Decide which binding tests are Kernel-generic versus SI profile wrapper tests. |
| `kernel/tests/test_m2_asof.py` | Generic AS_OF/currentness behavior using active pilot context. | `KEEP_ROOT_WITH_PROFILE_FIXTURES` | Context behavior must stay Kernel-owned; only fixture construction may move later. |
| `kernel/tests/test_m2_extent.py` | Generic extent-bound mechanics with format-true fixtures. | `KEEP_ROOT_GENERIC` | None, unless fixture helpers are centralized later. |
| `kernel/tests/test_m2_identities.py` | Generic identity, structure, materialization, authority inheritance, and review behavior. | `KEEP_ROOT_GENERIC` | None, unless demo fixture construction moves after D2. |
| `kernel/tests/test_m2_oidc.py` | Generic OIDC/dev-conformance auth behavior. | `KEEP_ROOT_GENERIC` | None. |
| `kernel/tests/test_m2_review.py` | Generic review, correction, and acceptance semantics. | `KEEP_ROOT_GENERIC` | None. |
| `kernel/tests/test_review_fixes.py` | Regression tests for generic review and materialization fixes. | `KEEP_ROOT_GENERIC` | None. |
| `kernel/tests/test_stages.py` | Stage/gate primitive tests. | `KEEP_ROOT_GENERIC` | None. |

## Demo Fixture Boundary

`kernel/demo.py` remains in place until a later D2 implementation because many
root tests and API examples depend on the current import shape. A future harness
may introduce profile-local demo payload builders, but the move must be staged:

1. Add profile-local fixture helpers while keeping `kernel/demo.py` as a
   compatibility facade.
2. Update SI-profile tests to use profile-local helpers.
3. Keep root generic tests on stable Kernel fixture helpers.
4. Remove or shrink the facade only after full coverage proves behavior and
   output payloads are unchanged.

No tenant identity should become inherent profile package content. Tenant/demo
binding remains deployment or fixture binding, consistent with
`runtime_profile_descriptor.json`.

## Conformance Boundary

D6 does not split conformance evidence. That belongs to D7.

Until D7 exists:

- `kernel/tests/test_conformance.py` remains the named platform MVP executed
  conformance suite;
- `conformance/evidence/platform_mvp_results_*.json` remains root evidence;
- profile-local design cases remain design cases unless a future harness runs
  them and writes clearly labeled profile evidence;
- engineering tests moved under `profile_si_ffs/tests/` must not be presented as
  platform MVP conformance unless D7 explicitly defines that lane.

## Suggested Future PRs

| Future PR | Scope | Stop condition |
| --- | --- | --- |
| D6a | Add a profile test-harness scaffold and root discovery bridge, but move no tests yet. | Stop if CI command or evidence writer semantics must change. |
| D6b | Move SI adapter/import tests (`REGSR`, `GERK`, `FFS naprave`) under the profile harness with unchanged assertions. | Stop if adapter behavior or generated reference data changes. |
| D6c | Move SI policy metadata tests under the profile harness after D3/D4 coverage remains green from the root command. | Stop if malformed-policy fail-closed routes change. |
| D6d | Split mixed tests such as adapters/bindings into Kernel-generic and SI-profile parts. | Stop if classification would reduce coverage or hide active SI pilot assumptions. |
| D2 | Move demo payload builders after the harness is proven. | Stop if `kernel/demo.py` facade removal would break API examples or root tests. |
| D7 | Split conformance lanes and evidence ownership. | Stop if design cases would be mislabeled as executed platform evidence. |

## Validation Expectations

For this planning PR, run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

For any future implementation PR, also run:

```sh
.venv/bin/python -m pytest kernel/tests/ -q
```

If a future docs-only planning PR accidentally runs pytest and creates
`conformance/evidence/platform_mvp_results_*.json`, remove that new generated
evidence before commit unless the PR intentionally changes executable
conformance grounding.

## Invariants To Preserve

- Assertion/history-first truth remains canonical.
- Governed materialization remains Kernel-owned.
- Authority, review, correction, freshness, refusal, and evidence behavior are
  not weakened.
- Profile tests do not become hidden profile law.
- SI profile fixtures stay fictional or public-reference-derived as appropriate.
- No Core, Kernel, Platform, contract, generated manifest, NL profile, or
  reference law semantic changes are part of this plan.
