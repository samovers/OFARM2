# SI Demo Fixture Migration Status

Status: documentation-only status record. This file does not move
`kernel/demo.py`, change runtime behavior, alter tests, update contracts or
generated manifests, regenerate evidence, or claim Slovenia production
readiness.

This began as the PR D2 follow-up from `manual_review_backlog_plan.md`. It now
records the D2a-D2d fixture boundary that is implemented under
`profile_si_ffs/test_fixtures/`, plus the remaining guardrails before any later
`kernel.demo` facade cleanup.

## Goal

Keep `kernel/demo.py` compatible for root callers while moving SI-shaped demo
fixture construction behind profile-local helpers where the profile engineering
tests can use it directly.

The implemented boundary preserves:

- the same fictional, format-true demo identities and payload semantics;
- the same bootstrap and onboarding behavior;
- the same API examples and root tests that import `kernel.demo`;
- the same review, refusal, authority, evidence, currentness, and
  materialization outcomes.

D2a-D2d do not make demo fixtures profile law, runtime adapters, canonical
contracts, generated manifest inputs, or conformance evidence.

## Current Demo Surfaces

| Surface | Current role | Current status / remaining guardrail |
| --- | --- | --- |
| Demo constants (`FARM`, `FIELD`, parties, bindings, evidence refs) | Shared active SI pilot fixture identifiers used across tests and examples. | D2a mirrors these through `profile_si_ffs/test_fixtures/demo_refs.py`; `kernel.demo` remains the public compatibility source for root callers. |
| `substrate_records()` | Boots parties, grants, evidence, and SI-shaped code bindings used by active tests. | D2b moves construction behind `profile_si_ffs/test_fixtures/demo_records.py`; `kernel.demo.substrate_records()` delegates unchanged. |
| Typed identity payload builders | Build farm, field, crop-cycle, equipment, and applied-resource payloads for onboarding and tests. | D2c moves construction behind `profile_si_ffs/test_fixtures/demo_payloads.py`; `kernel.demo` delegates unchanged. |
| Operation/demo payload builders | Build active SI demo operation submissions and related payloads. | D2c moves construction behind profile-local helpers while preserving payload ids, field names, defaults, and decision outcomes. |
| `onboard()` / `bootstrap()` | Commits demo structure assertions and active substrate records into the store. | Remain in `kernel.demo`; do not move until root callers and API examples no longer depend on the current facade. |
| Register/product demo binding | Uses public REGSR-derived data and SI code-binding refs. | Stays profile-scoped fixture support and must not be treated as Core law. |
| SI profile engineering tests | Use direct profile-local fixture imports under the profile harness. | D2d updates moved SI profile tests to import `profile_si_ffs.test_fixtures.demo` while root bridge files preserve default discovery. |
| Root test imports of `kernel.demo` | Preserve broad current coverage across root tests and examples. | Keep until a later D2e-style cleanup proves the facade can shrink without changing behavior. |

## Implemented Package Shape

The current profile-local fixture package is:

- `profile_si_ffs/test_fixtures/demo_refs.py`: D2a compatibility mirror for
  current `kernel.demo` reference values;
- `profile_si_ffs/test_fixtures/demo_records.py`: D2b substrate-record builder;
- `profile_si_ffs/test_fixtures/demo_payloads.py`: D2c typed identity and
  operation payload builder;
- `profile_si_ffs/test_fixtures/demo.py`: D2d profile-local facade used by moved
  SI profile engineering tests.

There is no separate profile-local bootstrap module. `kernel.demo.bootstrap()`
and `kernel.demo.onboard()` remain root facade behavior because they are still
used by root tests and examples.

The profile-local fixture package stays test/demo support. It must not become
profile law, a runtime adapter, a canonical contract, a generated manifest
input, or an evidence writer.

## Migration Sequence

| Step | Status | Required validation / stop condition |
| --- | --- | --- |
| D2a | Implemented. | Profile-local fixture refs mirror current `kernel.demo` values with no payload, id, bootstrap, evidence, authority, review, currentness, or materialization behavior change. |
| D2b | Implemented. | SI substrate record construction lives behind profile-local helpers, with `kernel.demo.substrate_records()` delegating unchanged. |
| D2c | Implemented. | SI operation/demo payload builders live behind profile-local helpers, with representative payloads preserved. |
| D2d | Implemented. | Moved SI profile tests import the profile-local fixture facade directly, while root bridge files keep default discovery. |
| D2e or later | Remaining optional cleanup. | Stop if shrinking `kernel/demo.py` would break root tests, API examples, facade compatibility, or conformance evidence writer behavior. |

## Compatibility Rules

Any later cleanup must preserve these names until a dedicated PR proves they are
no longer imported by root tests or examples:

- `FARM`, `FIELD`, `CYCLE`, `FARMER`, `WORKER`, `ADVISOR`, `INSPECTOR`,
  `AGENT`;
- `SPRAYER`, `APPLIED_RESOURCE`, `PRODUCT_BINDING`, `CROP_BINDING`,
  `PHOTO_EVIDENCE`, `ONBOARDING_EVIDENCE`;
- `REGSR_SNAPSHOT`, `VALID_FROM`, `ACTION_CLASSES`;
- `substrate_records()`, `bootstrap()`, `onboard()`;
- structure payload builders and operation submission builders currently used
  by tests.

The compatibility facade must continue to delegate to profile-local helpers
without changing payload ids, record ids, field names, timestamps that tests
intentionally fix, or decision outcomes.

## Boundaries

D2a-D2d moved demo fixture construction behind profile-local helpers. They did
not move:

- Kernel validation, gates, materialization, context assembly, or authority
  mechanics;
- SI runtime adapters under `kernel/profiles/si_ffs/**`;
- conformance evidence writer behavior;
- platform MVP conformance fixtures;
- contracts or generated manifests;
- Netherlands profile material.

Tenant identity remains deployment/demo binding and must not become inherent
profile package law.

## Stop Conditions

Stop and re-plan if a later PR would:

- require changing current test expectations to fit the move;
- drop coverage or remove root discovery of moved profile tests;
- create profile-local fixtures that are imported as Core law;
- change accepted payloads, promotion traces, materialization keys, or evidence
  records;
- rename the platform MVP suite or regenerate evidence in a docs-only PR;
- remove the `kernel.demo` facade before callers are migrated;
- claim Slovenia production readiness.

## Validation Expectations

For documentation-only status updates to this file, run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

For implementation PRs that touch demo fixture code, also run:

```sh
.venv/bin/python -m pytest kernel/tests/ -q
```

If a documentation-only PR accidentally creates
`conformance/evidence/platform_mvp_results_*.json`, remove that new generated
evidence before commit unless the PR intentionally changes executable evidence
grounding.

## Invariants To Preserve

- Assertion/history-first truth remains canonical.
- Demo fixtures do not become hidden truth stores.
- Governed materialization remains Kernel-owned.
- Authority, review, correction, freshness, refusal, and evidence behavior are
  not weakened.
- Fictional demo identifiers remain fictional and format-true.
- Public register-derived demo binding data stays profile-scoped and is never
  represented as Core law.
