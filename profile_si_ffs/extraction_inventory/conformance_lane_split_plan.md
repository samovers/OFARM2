# SI Conformance Lane Split Plan

Status: implemented boundary memo plus future-lane plan. The root navigation
pointer and evidence-lane README are now implemented, but this file does not
move conformance files, change test execution, regenerate evidence, update
contracts or manifests, alter Core, Kernel, or Platform semantics, or claim
Slovenia production readiness.

This is the PR D7 follow-up from `manual_review_backlog_plan.md`. It defines the
future boundary between package-wide conformance, active SI pilot executed
evidence, profile-local engineering tests, and profile design cases.

## Goal

Prevent three different artifacts from being confused:

- package-wide checks that validate repository packaging and JSON instances;
- executed platform MVP conformance evidence produced by live tests;
- profile-local design inventories or engineering tests that are useful but are
  not, by themselves, platform conformance evidence.

D7 remains a boundary lane. It must not rename the current suite, change pytest
collection, move evidence files, or alter the `conformance/` runner unless a
future implementation PR explicitly designs that change.

## Implemented Boundary

The first D7 documentation boundary is now present in root conformance docs:

- `conformance/CONFORMANCE.md` contains the short root lane map and points back
  to this plan.
- `conformance/evidence/README.md` labels `platform_mvp_results_*.json` as
  `PLATFORM_MVP_EXECUTED_EVIDENCE`, not package self-check output, profile
  design cases, profile engineering tests, or extraction-planning material.

This implemented boundary does not create a profile-local executed-evidence
lane, evidence writer, pytest command, or platform conformance claim for profile
engineering tests.

## Current Lanes

| Lane | Current location | Current meaning | Keep for now |
| --- | --- | --- | --- |
| Package self-check | `conformance/ofarm_pkg_contract_check.py` | Parse, digest, and schema-instance validation for authored package artifacts. | Yes, root-owned. |
| Platform MVP executed suite | `kernel/tests/test_conformance.py` plus `kernel/tests/conftest.py` evidence writer | Named executed conformance suite against the live store. | Yes, root-owned. |
| Platform MVP evidence | `conformance/evidence/platform_mvp_results_*.json` | Timestamped results of actual platform MVP test runs. | Yes, root-owned evidence lane. |
| Inherited gate fixtures | `conformance/fixtures/gate_sequencing/**` | Canonical input fixtures replayed by platform tests. | Yes, protected root fixtures. |
| NL profile design cases | `profile_nl_go_glmc7_2026/conformance/nl_glmc7_2026_cases.md` | Profile-slice design cases, not executed platform evidence. | Yes, profile-local design lane. |
| SI extraction planning | `profile_si_ffs/extraction_inventory/**` | Planning/inventory docs for SI extraction work. | Yes, profile-local planning lane. |
| SI profile engineering modules | `profile_si_ffs/tests/**` | Profile-owned engineering test bodies for SI adapters, policy metadata, binding wrappers, output locks, and demo fixture helpers. They are not platform MVP executed evidence. | Yes, profile-owned engineering coverage. |
| Root collection bridges for SI profile tests | `kernel/tests/test_profile_*.py` and bridge imports in selected root `kernel/tests/test_*.py` files | Root pytest discovery support for profile engineering modules. These bridges preserve the default root command but do not make profile tests platform MVP evidence. | Yes, root-owned discovery support. |
| Root active-runtime SI integration checks | Selected mixed/root tests such as `kernel/tests/test_m2_si_bindings.py` | Remaining active SI pilot integration coverage whose assertions have not been moved or split into profile-only modules. | Yes, root-owned until a later explicit split. |

## Future Lane Definitions

| Future lane | Intended owner | What belongs there | What must not belong there |
| --- | --- | --- | --- |
| `PACKAGE_SELF_CHECK` | Root `conformance/` | Repository/package validation scripts and their documentation. | Profile design cases, runtime claims, or generated evidence. |
| `PLATFORM_MVP_EXECUTED_EVIDENCE` | Root `conformance/evidence/` | Actual executed platform MVP result JSON from the named root suite. | Design inventories, dry-run notes, or profile-only test output. |
| `PLATFORM_MVP_FIXTURES` | Root `conformance/fixtures/` | Canonical or inherited fixtures that root platform tests execute. | Profile-local law or profile-specific fixture catalogs unless explicitly bridged. |
| `PROFILE_DESIGN_CASES` | Profile package directories | Design case inventories like the NL GLMC 7 slice cases. | Claims that the cases executed as platform evidence. |
| `PROFILE_ENGINEERING_TESTS` | Future profile harness from D6 | Profile-local pytest coverage for SI adapters, policy metadata, and fixture helpers. | Platform MVP evidence labels unless explicitly run and recorded by a defined evidence writer. |
| `PROFILE_EXECUTED_EVIDENCE` | Future profile-local evidence lane | Clearly labeled executed profile test outputs, if a future harness creates them. | Root platform MVP evidence or package self-check output. |
| `EXTRACTION_PLANNING` | `profile_si_ffs/extraction_inventory/` | Plans, inventories, migration maps, and stop conditions. | Runtime behavior, manifests, contracts, or executed evidence. |

## Evidence Writer Rules

The current evidence writer in `kernel/tests/conftest.py` stays root-owned until
a future implementation PR changes it deliberately.

Any future profile evidence writer must:

- use a distinct suite id from `conformance:ofarm2.platform-mvp.tests-1-15.v0_1`;
- write to a clearly profile-labeled path;
- record only tests that actually executed;
- include an honesty note that distinguishes design fixtures from executed
  evidence;
- avoid overwriting or renaming historical root evidence files;
- not present SI profile engineering tests as whole-platform conformance.

## Profile Design Case Rules

Profile-local design cases are allowed and useful. They must be labeled as
design inventories unless a future harness executes them.

Design cases may describe:

- input facts and evidence expectations;
- expected profile-level decisions or refusal posture;
- OFARM invariants protected by the case;
- future harness requirements.

Design cases must not claim:

- platform MVP conformance;
- runtime production readiness;
- whole-country production status;
- execution evidence without an actual executed run.

## Relationship To D6

D6 defines where SI tests may move after a profile harness exists. D7 defines how
evidence and conformance labels should be kept honest when that happens.

The order should be:

1. Keep current root conformance unchanged.
2. Add a D6 profile test harness scaffold without evidence changes.
3. Move SI engineering tests only when root CI still discovers them.
4. Add profile-local executed evidence only after this D7 lane has an approved
   writer shape.
5. Keep root conformance documentation limited to the implemented lane map until
   a future PR deliberately changes evidence writing or profile evidence lanes.

## Stop Conditions

Stop and re-plan if a future PR would require any of the following without an
approved implementation design:

- renaming the platform MVP suite id;
- moving or deleting historical `conformance/evidence/` files;
- changing `kernel/tests/conftest.py` evidence writer semantics;
- presenting design cases as executed evidence;
- moving inherited gate-sequencing fixtures into a profile package;
- dropping current platform MVP tests from CI;
- changing contracts, generated manifests, runtime adapters, or active profile
  behavior;
- claiming Slovenia production readiness.

## Validation Expectations

For this planning PR, run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

For any future implementation PR that touches tests or evidence writing, also
run:

```sh
.venv/bin/python -m pytest kernel/tests/ -q
```

If a docs-only planning PR accidentally creates
`conformance/evidence/platform_mvp_results_*.json`, remove that new generated
evidence before commit unless the PR intentionally changes executable evidence
grounding.

## Invariants To Preserve

- Honest reporting: failing tests are reported as failing.
- Design fixtures are never presented as executed evidence.
- Assertion/history-first truth remains canonical.
- Governed materialization remains Kernel-owned.
- Authority, review, correction, freshness, refusal, and evidence behavior are
  not weakened.
- Country/profile law remains in profile packages, not Core, Kernel, Platform,
  contracts, generated manifests, or default root conformance assumptions.
