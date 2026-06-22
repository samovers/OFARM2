# SI Demo Fixture Migration Plan

Status: plan-only document. This file does not move `kernel/demo.py`, change
runtime behavior, alter tests, update contracts or manifests, regenerate
evidence, or claim Slovenia production readiness.

This is the PR D2 follow-up from `manual_review_backlog_plan.md`. It defines the
future path for moving SI-shaped demo payloads and fixture builders toward the
profile package only after the D6 test-harness and D7 conformance/evidence
boundaries are implemented.

## Goal

Make `kernel/demo.py` smaller and more profile-neutral over time without losing
the current active SI pilot coverage.

The future migration should preserve:

- the same fictional, format-true demo identities and payload semantics;
- the same bootstrap and onboarding behavior;
- the same API examples and tests that import `kernel.demo`;
- the same review, refusal, authority, evidence, currentness, and
  materialization outcomes.

D2 must not move demo payloads before a profile test harness can run relocated
fixtures by default.

## Current Demo Surfaces

| Surface | Current role | Future treatment |
| --- | --- | --- |
| Demo constants (`FARM`, `FIELD`, parties, bindings, evidence refs) | Shared active SI pilot fixture identifiers used across tests and examples. | Move only after profile-local tests and root generic tests can import stable fixture APIs. |
| `substrate_records()` | Boots parties, grants, evidence, and SI-shaped code bindings used by active tests. | Candidate for profile-local fixture module with a `kernel.demo` compatibility facade. |
| Typed identity payload builders | Build farm, field, crop-cycle, equipment, and applied-resource payloads for onboarding and tests. | Split generic payload-shape helpers from SI/profile demo values later. |
| `onboard()` / `bootstrap()` | Commits demo structure assertions and active substrate records into the store. | Keep root facade until all tests and API examples are migrated. |
| Register/product demo binding | Uses public REGSR-derived data and SI code-binding refs. | Keep profile-owned after harness exists; do not treat as Core law. |
| Test imports of `kernel.demo` | Preserve broad current coverage across root tests. | Update gradually after profile fixture imports are discoverable in CI. |

## Future Package Shape

A later implementation may introduce:

- `profile_si_ffs/test_fixtures/demo_refs.py` for SI demo refs and constants;
- `profile_si_ffs/test_fixtures/demo_records.py` for substrate records and
  binding fixtures;
- `profile_si_ffs/test_fixtures/demo_payloads.py` for SI-profile demo payload
  builders;
- `profile_si_ffs/test_fixtures/bootstrap.py` for profile-local demo bootstrap;
- a small `kernel/demo.py` compatibility facade that re-exports current names
  until root tests no longer depend on them.

The profile-local fixture package must stay test/demo support. It must not
become profile law, a runtime adapter, a canonical contract, or a generated
manifest input.

## Migration Sequence

| Step | Scope | Required validation |
| --- | --- | --- |
| D2a | Add profile-local fixture modules that mirror current `kernel.demo` values; keep `kernel/demo.py` as the source of public imports or a strict facade. | Full kernel tests; no output payload changes. |
| D2b | Move SI substrate record construction behind profile-local helpers, with `kernel.demo.substrate_records()` delegating unchanged. | Full kernel tests; spot-check substrate record ids and payloads. |
| D2c | Move SI operation/demo payload builders behind profile-local helpers, keeping `kernel.demo` compatibility imports. | Full kernel tests; compare representative `spray_submission()` and structure payloads. |
| D2d | Update SI-profile tests to import profile-local fixtures directly once D6 harness discovery exists. | Root CI must still discover moved tests and preserve test count. |
| D2e | Shrink `kernel/demo.py` only after root generic tests no longer need SI-profile values directly. | Full kernel tests and conformance evidence writer behavior unchanged. |

## Compatibility Rules

Any implementation must preserve these names until a dedicated cleanup PR proves
they are no longer imported by root tests or examples:

- `FARM`, `FIELD`, `CYCLE`, `FARMER`, `WORKER`, `ADVISOR`, `INSPECTOR`,
  `AGENT`;
- `SPRAYER`, `APPLIED_RESOURCE`, `PRODUCT_BINDING`, `CROP_BINDING`,
  `PHOTO_EVIDENCE`, `ONBOARDING_EVIDENCE`;
- `REGSR_SNAPSHOT`, `VALID_FROM`, `ACTION_CLASSES`;
- `substrate_records()`, `bootstrap()`, `onboard()`;
- structure payload builders and operation submission builders currently used
  by tests.

The compatibility facade must delegate to profile-local helpers without changing
payload ids, record ids, field names, timestamps that tests intentionally fix,
or decision outcomes.

## Boundaries

D2 may later move demo fixture construction. It must not move:

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

Stop and re-plan if a future PR would:

- require changing current test expectations to fit the move;
- drop coverage or remove root discovery of moved profile tests;
- create profile-local fixtures that are later imported as Core law;
- change accepted payloads, promotion traces, materialization keys, or evidence
  records;
- rename the platform MVP suite or regenerate evidence in a docs-only PR;
- remove the `kernel.demo` facade before callers are migrated;
- claim Slovenia production readiness.

## Validation Expectations

For this planning PR, run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

For any future implementation PR that touches demo fixtures, also run:

```sh
.venv/bin/python -m pytest kernel/tests/ -q
```

If a docs-only planning PR accidentally creates
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
