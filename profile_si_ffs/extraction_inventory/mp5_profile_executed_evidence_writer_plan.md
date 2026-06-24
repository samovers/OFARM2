# MP5 Profile Executed-Evidence Writer Plan

Status: documentation-only MP5 planning record. This file does not implement an
evidence writer, write evidence, change root pytest collection, relabel platform
MVP evidence, update contracts, update schemas, update generated manifests,
change runtime behavior, activate a second profile, or claim production
readiness.

## Goal

Define the future profile executed-evidence lane before any writer exists.

MP4 made profile engineering-test harness discovery generic, but discovery is
not execution. MP5 records the boundary a later implementation must satisfy
before profile-local engineering-test output can be represented as executed
profile evidence.

## Baseline

This plan assumes PR #121 / MP4 has merged.

Current repository state:

- root platform MVP evidence remains under `conformance/evidence/`;
- the root evidence writer remains `kernel/tests/conftest.py`;
- `profile_si_ffs/tests/profile_test_harness.json` remains an engineering-test
  harness descriptor;
- no profile-local executed-evidence writer exists;
- no profile-local evidence artifact is created by this plan.

## Vocabulary

| Term | Meaning | Boundary |
| --- | --- | --- |
| `PLATFORM_MVP_EXECUTED_EVIDENCE` | Root platform evidence under `conformance/evidence/platform_mvp_results_*.json`. | Remains root-owned and must not be relabeled as profile evidence. |
| `PROFILE_ENGINEERING_TESTS` | Profile-local engineering tests declared by a profile harness descriptor. | Not platform conformance and not executed profile evidence by themselves. |
| `PROFILE_EXECUTED_EVIDENCE` | Future opt-in evidence output for executed profile engineering tests. | Must have a distinct suite id, path, honesty note, and non-claims. |
| Profile evidence writer | Future writer that records actual executed profile harness results. | Not implemented by this PR. |

## Future Evidence Lane Shape

A later MP5 implementation may create a profile-local evidence lane. The
recommended future path for SI is:

```text
profile_si_ffs/evidence/profile_executed_engineering_results_<timestamp>.json
```

This documentation-only PR must not create `profile_si_ffs/evidence/` and must
not commit any profile evidence artifact.

Any later profile evidence artifact must include at least:

- `evidenceKind`: `PROFILE_EXECUTED_EVIDENCE`;
- `suiteId`: for SI, `profile:si.ffs.engineering-tests.v0_1`;
- `profilePackage`;
- `harnessDescriptorPath`;
- `harnessDescriptorSha256` or equivalent descriptor identity;
- `generatedAt`;
- `command`;
- `gitCommit` if available;
- `resultRecords`;
- `summary`;
- `nonClaims`;
- `honestyNote`.

Each `resultRecords` entry must identify an actually executed test node id or
equivalent test id, module, outcome, duration if available, and bounded failure
metadata when applicable. The writer must not fabricate records for tests that
were merely discoverable but not executed.

Before any future MP5 implementation writes profile evidence artifacts, it must
define a machine-checkable `PROFILE_EXECUTED_EVIDENCE` shape, such as a JSON
schema, contract-like validator, or equivalent check.

## Writer Boundary

A future profile evidence writer must:

- use a suite id distinct from
  `conformance:ofarm2.platform-mvp.tests-1-15-plus-regressions.v0_2`;
- write only to a clearly profile-local evidence path;
- record only actual executed profile engineering tests;
- include an honesty note distinguishing profile engineering evidence from root
  platform MVP evidence, design cases, and fixtures;
- keep `profile_si_ffs/tests/profile_test_harness.json` as discovery
  configuration, not as an evidence artifact;
- avoid overwriting, renaming, deleting, or relabeling historical root platform
  evidence;
- remain opt-in unless a later PR deliberately changes root collection and
  evidence semantics.

## Stop Conditions

Stop and re-plan if a future PR would:

- treat harness discovery as evidence execution;
- make `profile_si_ffs/tests/profile_test_harness.json` itself an evidence
  artifact;
- write profile evidence into `conformance/evidence/`;
- reuse the platform MVP suite id for profile engineering evidence;
- present profile engineering tests as platform MVP conformance;
- present profile design cases or fixtures as executed evidence;
- move, delete, rename, overwrite, or relabel historical platform MVP evidence;
- change `kernel/tests/conftest.py` evidence-writer behavior without an explicit
  evidence-lane implementation design.

## Non-Claims

This plan and PR do not claim or create:

- profile executed evidence;
- platform MVP evidence for profile engineering tests;
- automatic pytest collection changes;
- root platform evidence relabeling;
- a profile evidence writer;
- a second active runtime profile;
- Netherlands runtime support;
- multi-profile runtime readiness;
- generated manifest or capability expansion;
- schema or contract changes;
- Slovenia production readiness;
- L5 Core country/profile neutrality certification.

## Validation For This Plan

For this documentation-only plan, run:

```sh
python3 conformance/ofarm_profile_extraction_consistency_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --cached --check
```

Do not run pytest unless a reviewer asks. If pytest is accidentally run and
creates `conformance/evidence/platform_mvp_results_*.json`, remove that new
generated evidence file before commit because this plan does not change evidence
grounding.
