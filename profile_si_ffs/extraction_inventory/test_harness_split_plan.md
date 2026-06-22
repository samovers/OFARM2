# SI Test-Harness Split Status

Status: documentation-only status record. This file does not move tests, change
runtime behavior, update contracts or generated manifests, regenerate evidence,
alter Core, Kernel, or Platform semantics, or claim Slovenia production
readiness.

This began as the PR D6 follow-up from `manual_review_backlog_plan.md`. It now
records the harness boundary implemented by D6a-D6d and D2a-D2d, plus the
remaining guardrails before any later fixture or conformance split work.

## Goal

Record how the current repository separates three ideas that were previously
co-located in root test files:

- Kernel-generic behavior tests that stay root-owned;
- active SI pilot runtime support tests that remain root-owned where they guard
  the current shipped runtime path;
- profile-specific SI adapter, policy, descriptor, output-lock, and fixture
  engineering tests that now live under `profile_si_ffs/` while remaining
  discoverable by the root test command.

This implemented boundary preserves current active SI pilot behavior and does
not create a universal country abstraction layer, reclassify engineering tests
as executed platform evidence, or weaken root-owned conformance evidence rules.

## Implemented Harness Boundary

Current profile-local harness support is:

- `profile_si_ffs/tests/profile_test_harness.json` declares profile-local
  engineering-test modules. It is explicitly engineering-test-only:
  `platformConformance` is false, `executedEvidence` is false, and
  `evidenceWriter` is null.
- `kernel/tests/profile_harness_bridge.py` loads and validates that descriptor.
- Root bridge test files import the profile-local test modules so
  `.venv/bin/python -m pytest kernel/tests/ -q` still discovers the moved
  coverage.
- `kernel/tests/test_profile_harness_bridge.py` verifies descriptor shape,
  importability, and top-level root bridge reachability for every
  descriptor-listed module.
- `profile_si_ffs/test_fixtures/` contains profile-local SI demo fixture helpers
  introduced by D2a-D2d.
- `kernel/demo.py` remains the public compatibility facade for root callers and
  API examples.

The harness is execution support only. It does not define OFARM law, modify
contracts, generate manifests, emit accepted records, write evidence, or become
a hidden truth store.

## Current Test Areas

| Area | Current role | Current status / remaining lane | Preconditions before future change |
| --- | --- | --- | --- |
| `kernel/tests/conftest.py` | Root pytest store, bootstrap, demo setup, and platform evidence writer. | `KEEP_ROOT_HARNESS` | D7 conformance lane split must define evidence ownership before changing evidence writer behavior. |
| `kernel/tests/test_conformance.py` | Named platform MVP conformance suite and evidence source. | `KEEP_ROOT_CONFORMANCE` | D7 must preserve executed-evidence semantics and avoid mixing profile design cases into platform evidence. |
| `kernel/tests/test_profile_runtime_loader.py` | Active SI profile descriptor and context-spine loader tests. | `KEEP_ROOT_ACTIVE_RUNTIME_SUPPORT` for now. | Any future move needs a non-SI-specific active-profile loader test harness and must preserve descriptor bootstrap equivalence. |
| `kernel/tests/test_m2_si_regsr.py` | Root bridge for SI REGSR adapter/import tests now implemented in `profile_si_ffs.tests.m2_si_regsr_tests`. | `PROFILE_LOCAL_WITH_ROOT_BRIDGE` | Keep the bridge until the default root test command explicitly collects profile tests another way. |
| `kernel/tests/test_m2_si_gerk.py` | Root bridge for SI GERK layer adapter/import tests now implemented in `profile_si_ffs.tests.m2_si_gerk_tests`. | `PROFILE_LOCAL_WITH_ROOT_BRIDGE` | Keep the bridge until the default root test command explicitly collects profile tests another way. |
| `kernel/tests/test_m2_si_ffsnaprave.py` | Root bridge for SI FFS naprave inspection adapter/import tests now implemented in `profile_si_ffs.tests.m2_si_ffsnaprave_tests`. | `PROFILE_LOCAL_WITH_ROOT_BRIDGE` | Keep the bridge until the default root test command explicitly collects profile tests another way. |
| `kernel/tests/test_m2_si_bindings.py` | Mixed root file: SI binding wrapper assertions moved to `profile_si_ffs.tests.m2_si_binding_wrapper_tests`; root still keeps active-runtime integration checks. | `SPLIT_IMPLEMENTED_WITH_ROOT_REMAINDER` | Do not move remaining root checks unless generic binding mechanics and active SI runtime checks stay covered. |
| `kernel/tests/test_m2_si_floor.py` | Root bridge for active SI evidence floor policy, display metadata, advisory, and fallback trace tests now implemented in `profile_si_ffs.tests.m2_si_floor_tests`. | `PROFILE_LOCAL_WITH_ROOT_BRIDGE` | Keep malformed-policy fail-closed coverage discoverable from the root command. |
| `kernel/tests/test_m2_si_validation_policy.py` | Root bridge for active SI validation policy metadata tests now implemented in `profile_si_ffs.tests.m2_si_validation_policy_tests`. | `PROFILE_LOCAL_WITH_ROOT_BRIDGE` | Keep wrong-kind ref and unknown-key refusal coverage discoverable from the root command. |
| `kernel/tests/test_m2_manifest.py` | Active SI pilot manifest behavior and non-overclaiming posture. | `KEEP_AS_ACTIVE_RUNTIME_SI_SUPPORT` until D5. | Multi-profile manifest design before any relocation or split. |
| `kernel/tests/test_m2_adapters.py` | Generic adapter mechanics plus root bridge import for active SI output-lock assertions now implemented in `profile_si_ffs.tests.m2_si_output_lock_tests`. | `SPLIT_IMPLEMENTED_WITH_ROOT_GENERIC_REMAINDER` | Keep generic adapter/import mechanics and single-writer lock behavior root-owned. |
| `kernel/tests/test_m2_bindings.py` | Generic reference-snapshot and binding mechanics with fixture families. | `SPLIT_LATER` | Decide which binding tests are Kernel-generic versus SI profile wrapper tests. |
| `kernel/tests/test_m2_asof.py` | Generic AS_OF/currentness behavior using active pilot context. | `KEEP_ROOT_WITH_PROFILE_FIXTURES` | Context behavior must stay Kernel-owned; only fixture construction may move later. |
| `kernel/tests/test_m2_extent.py` | Generic extent-bound mechanics with format-true fixtures. | `KEEP_ROOT_GENERIC` | None, unless fixture helpers are centralized later. |
| `kernel/tests/test_m2_identities.py` | Generic identity, structure, materialization, authority inheritance, and review behavior. | `KEEP_ROOT_GENERIC` | None. |
| `kernel/tests/test_m2_oidc.py` | Generic OIDC/dev-conformance auth behavior. | `KEEP_ROOT_GENERIC` | None. |
| `kernel/tests/test_m2_review.py` | Generic review, correction, and acceptance semantics. | `KEEP_ROOT_GENERIC` | None. |
| `kernel/tests/test_review_fixes.py` | Regression tests for generic review and materialization fixes. | `KEEP_ROOT_GENERIC` | None. |
| `kernel/tests/test_stages.py` | Stage/gate primitive tests. | `KEEP_ROOT_GENERIC` | None. |
| `kernel/tests/test_profile_si_demo_refs.py` | Root bridge for D2a SI demo ref mirror tests now implemented in `profile_si_ffs.tests.d2_demo_fixture_refs_tests`. | `PROFILE_LOCAL_WITH_ROOT_BRIDGE` | Keep until root command collection explicitly includes profile-local tests. |
| `kernel/tests/test_profile_si_demo_records.py` | Root bridge for D2b SI demo record helper tests now implemented in `profile_si_ffs.tests.d2_demo_fixture_records_tests`. | `PROFILE_LOCAL_WITH_ROOT_BRIDGE` | Keep until root command collection explicitly includes profile-local tests. |
| `kernel/tests/test_profile_si_demo_payloads.py` | Root bridge for D2c/D2d SI demo payload/facade tests now implemented in `profile_si_ffs.tests.d2_demo_fixture_payloads_tests`. | `PROFILE_LOCAL_WITH_ROOT_BRIDGE` | Keep until root command collection explicitly includes profile-local tests. |

## Demo Fixture Boundary

`profile_si_ffs/test_fixtures/` now provides the profile-local SI demo fixture
helpers introduced by D2a-D2d:

- D2a mirrors current public `kernel.demo` reference values in profile-local
  fixture helpers.
- D2b moves substrate-record construction behind profile-local helpers while
  keeping the `kernel.demo` public facade.
- D2c moves demo payload builders behind profile-local helpers while keeping the
  `kernel.demo` public facade.
- D2d updates moved SI profile tests to import the profile-local fixture facade
  directly while root bridges preserve default discovery.

`kernel/demo.py` remains in place because root tests and API examples still
depend on the current import shape. A later D2e-style cleanup may shrink the
facade only after full coverage proves behavior and output payloads are
unchanged.

No tenant identity should become inherent profile package content. Tenant/demo
binding remains deployment or fixture binding, consistent with
`runtime_profile_descriptor.json`.

## Conformance Boundary

D6 did not split conformance evidence. D7 documented that lane separately.
Current boundaries remain:

- `kernel/tests/test_conformance.py` remains the named platform MVP executed
  conformance suite;
- `conformance/evidence/platform_mvp_results_*.json` remains root evidence;
- profile-local design cases remain design cases unless later scoped work runs
  them and writes clearly labeled profile evidence;
- engineering tests moved under `profile_si_ffs/tests/` are not platform MVP
  conformance and do not write executed evidence.

## Implemented And Remaining PR Lanes

| PR lane | Status | Boundary / stop condition |
| --- | --- | --- |
| D6a | Implemented. | Profile harness scaffold and root discovery bridge exist without changing evidence writer semantics. |
| D6b | Implemented. | SI adapter/import engineering assertions moved under the profile harness with root bridge files. |
| D6c | Implemented. | SI policy metadata engineering assertions moved under the profile harness with fail-closed coverage preserved. |
| D6d | Implemented. | Mixed adapter/binding/output-lock coverage split so root keeps generic mechanics and profile-local modules keep active SI assertions. |
| D2a-D2d | Implemented. | SI demo fixture refs, records, payloads, and profile test imports are profile-local while `kernel/demo.py` remains the compatibility facade. |
| D2e or later | Remaining optional cleanup. | Stop if shrinking `kernel/demo.py` would break root tests, API examples, or facade compatibility. |
| D7 | Documented separately. | Stop if profile engineering tests or design cases would be mislabeled as `PLATFORM_MVP_EXECUTED_EVIDENCE`. |
| Future multi-profile harness | Not started. | Stop if SI-specific bridge behavior would be treated as a general profile-discovery or capability mechanism. |

## Validation Expectations

For documentation-only status updates to this file, run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

For implementation PRs that touch harness, fixture, or bridge code, also run:

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
  reference law semantic changes are part of this status record.
