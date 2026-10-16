# Tenant Runtime Fixture Capacity RFC v0.1

Status: approved implementation for [Delivery #414](https://github.com/samovers/OFARM2/issues/414) / [PR #415](https://github.com/samovers/OFARM2/pull/415). The task user approved version 1 after the complete reviewed decision card in the coordinating chat on 16 October 2026. Decision identity: `OFARM2-TENANT-RUNTIME-FIXTURE-CAPACITY-001`, version `1`. This RFC stays useful as the ownership contract between staged migration evidence and current-state runtime fixtures. It does not establish a new repository process or grant authority.

## Problem and one complete capability

The unchanged module-scoped tenant fixture repeats migration-specific staged probes in fourteen runtime test modules that consume the resulting current database, rather than the staged reports. Required hosted jobs have exhausted their 45-minute allowance during the second full baseline. This is a measured setup-capacity improvement, not a demonstrated resolution of that hosted limit. This proposal would remove measured duplicate setup from those runtime consumers while retaining the complete staged evidence owner and each module's fresh real database. It cannot promise that local savings resolve the hosted deadline.

The primary trust boundary is **test-fixture construction and evidence fidelity**. This is separate from PR #413's signing proxy lifecycle, PR #411's trusted CI execution/currentness policy, and PR #409's transaction failure behavior. Those branches and authorities remain separate.

## Evidence and decision condition

Base: `301bf4aa3196b503ec114ebfa0f455be818627a4`. The unchanged selector module and migration evidence-owner test passed all 12 selected cases in each of two fresh processes, without warnings, skips, deselections or altered source. Selector tenant setup took 4.345s and 4.558s. Required prefix SQL is not removable overhead. An external comparison of existing APIs then measured the actual schedule difference. Its staged/direct/direct/staged setup times were 4.357681s, 2.792392s, 2.755632s and 4.170380s. Means were 4.264030s staged and 2.774012s direct: 1.490018s (34.94%) less per fresh service, with the public no-op retained. The difference exceeded the observed within-schedule spreads (0.187301s staged, 0.036760s direct). This supports a bounded setup improvement; it does not establish aggregate savings or hosted margin.

The environment was CPython 3.12.13 on macOS arm64, PostgreSQL 17.10 arm64/native extension 1.0, and verified TLS/SCRAM. The four comparison processes started fresh services; all public structural observations passed at version 11, all eleven ledger rows matched on their seven immutable columns, true report/no-op execution lineage passed, dirty-target entry refused without adoption, and owned cleanup completed. All three diagnostic clusters and volumes were removed. No replacement pytest fixture or runtime consumer against changed setup was implemented. Two samples per schedule are descriptive, not a statistical confidence interval. Multiplying the mean reduction by fourteen registrations gives about 20.86 seconds per local baseline, an arithmetic illustration only; added regression cost and actual aggregate/hosted savings remain to be measured.

The source audit found fourteen external fixture registrations, including an assignment-based registration missed by the earlier list. They contain 375 committed cases, of which 373 depend on the tenant target. The migration owner has 120 cases, of which 117 depend on its staged target; the separate manual crash route has 26. These are source/inventory counts, not new execution results. Only the owner's authoritative source/ledger test reads the eleven historical report/probe fields, but the entire owner module remains staged because it also owns migration refusal and reconciliation evidence.

## Permitted change and direct design

One neutral test-support module owns the operational target facts, role-DSN derivation and fresh service lifetime. It uses the existing disposable-service helpers and fixed provisioning specification; it adds no parallel production validation. The common lifetime takes an explicit admin route, refuses an existing service before acquiring cleanup responsibility, and protects partial provisioning and every later step with the existing cleanup discipline.

The migration owner keeps its no-argument `tenant_target` generator and its `_admin_dsn()` lookup. It uses the common lifetime while retaining every v3–v7 prefix, guard/refusal/admission probe, full tail migration, no-op and historical assertion. Its evidence-bearing target adds genuine executed reports to the shared operational facts. No test function or authority/key/bootstrap body moves.

A separate module-scoped runtime fixture uses that same fresh lifetime. It invokes public `migrate_service` over the complete authoritative set, then the real verified no-op; it exposes only operational facts. It never fabricates staged reports or calls the partial-set testing migration path. Each of the fourteen audited modules registers that fixture under its existing `tenant_target` name. Existing dependent fixtures, dynamic requests, per-test pools, operations, parametrization, waits and assertions remain intact.

The crash harness stays on the staged route. It must still patch the migration owner's `_admin_dsn`, call `tenant_target.__wrapped__()` without arguments, and close the generator against its own cluster. The helper cannot replace that explicit route with ambient environment lookup. Similar-name fixtures belonging to provisioning, the migration runner, structural compatibility and challenge-migration tests are outside this adoption set.

The complete change includes the common lifetime, runtime fixture, all justified consumer registrations, focused integrity regressions, the preserved owner/crash route, documentation and mechanical inventory additions. A selector-only pilot would be an implementation checkpoint inside this Delivery, not a separate enabling PR or a claim that capacity is fixed.

## Authority map and threat model

The task user owns the decision, cancellation and later final acceptance. The AI owns implementation within an approved scope and truthful evidence coordination; reviewers own demonstrated Blockers. Existing public provisioning/migration and the migration-owned verifier retain all database/role/admission decisions. Existing tenant, key, signing, transaction, runtime and audit owners retain their behavior. Existing baseline, native verification and publisher policy retain acceptance and evidence custody.

Protected assets are faithful test preconditions, tenant/role isolation, complete migration regression evidence, fixture credentials and honest test results. Trusted components are the unchanged authoritative sources and public executors, existing fixed spec and cleanup ownership checks, and exact source/inventory verification. Untrusted inputs include ambient DSNs, stale or dirty services, malformed migration/catalog state, failing setup and transport, and incorrectly wired consumer fixtures. A compromised superuser, runner, host or repository administrator is outside the test-fixture threat model; no claim here protects against them.

The primary risk is a faster fixture concealing a defect or changing the authority/isolation being tested. Containment is fresh owned services, the unchanged authoritative full migration, genuine staged evidence in its owner, preserved real runtime operations, and fail-closed setup/cleanup. Fixture credentials remain ephemeral and local; no new secret custody, signing or production access is introduced.

## Invariants and falsifying cases

| ID | Required invariant | Evidence and negative case |
| --- | --- | --- |
| TFC-01 | One common operational fact and service-lifetime owner; fresh service at the existing module scope. | Exercise two successive modules and cleanup. A pre-existing governed role/database must cause refusal before adoption or destructive cleanup. No cache, clone, shared session or second lifecycle implementation. |
| TFC-02 | Runtime setup executes every authoritative migration and the real no-op through the public path. | Fresh report applies all current versions; no-op applies none and observes the actual head. A migration/catalog/role refusal propagates before yield and owned resources are cleaned. Existing production verifier and role refusal controls remain required. |
| TFC-03 | Every staged migration probe/report and owner assertion remains genuine. | Run the entire original owner module unchanged in meaning; exact reports retain their actual prefix/tail schedules. Omitting a probe or fabricating its result must fail the existing evidence owner. |
| TFC-04 | Required final structure, grants, immutable ledger identities and runtime preconditions match; diagnostic history remains truthful. | Use the existing structural verifier and seven-column immutable ledger contract. Compare actual required data preconditions separately. Source drift, wrong grants or a changed ledger digest must refuse. Do not infer all data equality from structure alone. |
| TFC-05 | Each adopted consumer and its authority/key/bootstrap fixtures resolve the one intended target; the crash route stays staged and explicit. | Run all adopted modules' original cases, plus the crash route control and its existing tests. A conflicting fixture registration, lost dynamic name or ambient-route fallback must fail. Preserve the two different `other_authority` owners. |
| TFC-06 | All existing case IDs, real callable source identities, operations, assertions, waits and refusal paths remain. | Compare the full committed inventory and source/test diffs; only meaningful new regression cases may add identities. Existing cross-tenant, signing, transaction, cancellation, pool and audit negative controls execute unchanged. |
| TFC-07 | Setup, body and teardown failures stay failures; cleanup follows dependent fixtures and covers owned partial setup. | Inject failures at provisioning/migration/yield/body boundaries and retain leak/cleanup assertions. Do not swallow failures, dispose early to hide leaks or delete an unowned dirty service. |
| TFC-08 | Performance claims are measured, and evidence acceptance is unchanged. | Repeat comparable local diagnostics, record overhead/variation and actual adoption cost. Both complete hosted baselines, fixed comparison, native/platform checks and authenticated publication remain mandatory. Local timing or a partial second run cannot count as success. |

Production-reachable negative paths remain the actual `provision_service`, `migrate_service`, structural verifier, tenant authentication/selection/UnitOfWork, signing observation and audit paths exercised by these tests. The new fixture does not become a production entry point. Fixture wiring and inventory failures are test-harness failures that must prevent those paths from being reported as tested successfully.

## Lifetime, provenance and rollback

The lifetime is: clean-target check → ownership of fresh provisioning → fully migrated current state → verified no-op → yield to unchanged dependents → dependent teardown → target destruction. Refusal before ownership leaves an unowned service untouched. Failure after ownership still disposes owned resources and fails the test. Every module starts fresh; there is no new durable production state or recovery path.

The seven immutable ledger columns remain version, filename, source SHA-256, byte length, applied-prefix digest, service identity and provisioning-spec digest. Direct full migration truthfully has different release identity, execution grouping and diagnostic time from staged prefixes. Those values are not fabricated, equalized or added to canonical evidence exclusions. The runtime type must not advertise historical evidence it did not execute. Fresh services also legitimately have distinct binder instance/audience/time/digest values and their linked closed keyring bootstrap. Staged probes consume database/catalog/transaction/WAL identities. Source inspection found no persistent application-data contribution from those probes: catalog mutations are restored, denied function calls stop before their bodies, and capsule calls refuse at their initial ledger guard before changing grants. Required preconditions are fresh empty tenant/principal/key/selection/governed-operation data plus genuine valid binder/keyring bootstrap, followed by unchanged authority/key fixtures. Do not invent whole-database equality or normalize these facts in canonical evidence.

Rollback is to revert this test-owned change and return adopted consumers to the staged fixture. No production migration, data rollback or policy change is involved. A preservation failure stops implementation for correction; an authority or semantic expansion requires a new decision.

## Expected areas and non-goals

Expected areas are a small neutral helper under `kernel/tests/`, the operational target/lifetime portions of `test_postgresql_tenant_migration.py`, the fourteen audited consumer registrations, focused fixture-integrity tests, the committed test inventory for new controls, and this durable design. Expected supporting inspection includes `_physical_outcome_crash.py` and existing disposable-service helpers; change them only if an unambiguously in-boundary preservation fix is necessary and explain it.

The fourteen expected consumer registrations, all under `kernel/tests/`, are:

- `test_authentication_read_api.py`
- `test_physical_outcome_fixture.py`
- `test_physical_outcome_health.py`
- `test_physical_outcome_runtime.py`
- `test_physical_outcome_transport.py`
- `test_postgresql_tenant_capability_retirement.py`
- `test_postgresql_tenant_capability_signing.py`
- `test_postgresql_tenant_challenge_observation.py`
- `test_postgresql_tenant_command_runtime_bundle_selector.py`
- `test_postgresql_tenant_uow.py`
- `test_postgresql_tenant_uow_concurrency.py`
- `test_security_audit_runtime_cross_slice.py`
- `test_signing_observation_acquisition.py`
- `test_signing_observation_database.py`

Excluded are production implementation/SQL/specification changes; new database privileges; transaction, signing, tenant, readiness or audit behavior; fixture scope expansion; database reuse; test deletion or selective baselines; timing/deadline reductions; CI budgets/runner scheduling; publication/equivalence policy; merge, deployment, release or production-readiness claims. No work from PRs #409, #411 or #413 is folded into this PR.

## Code excellence and provisional posture

EXC-001: public migration remains the authoritative executor, while the common helper owns operational target facts and service lifetime. EXC-002: share that lifetime instead of copying credentials, route construction, cleanup or grants validation. EXC-003: each invariant above names its implementation owner and focused evidence. EXC-004: remove superseded staged registrations only in adopted runtime modules; retain the staged owner/crash path because they still own evidence, not compatibility. EXC-005: the small common helper serves the two current construction paths and fourteen current runtime consumers; no generic strategy layer, plugin registry or cache. EXC-006: keeping the original fixture is the simplest alternative and remains preferable if savings are not useful; a copied faster fixture would duplicate cleanup/route authority, and sharing a service would violate module isolation. Preferences do not become Blockers.

The posture is provisional pre-deployment development. It is acceptable only with useful measured savings, demonstrated preserved preconditions and full required evidence. Redesign or reject if the timing hypothesis fails, a consumer needs staged history, data/route/lifetime equivalence is uncertain, or preservation requires another boundary. The likely upgrade is an in-boundary correction using the same authoritative executors; unrelated capacity work needs its own Delivery. No readiness or deployment authority follows from this design.

## Verification and approval gate

Before any implementation: a separate Delivery issue, existing draft PR with this reviewed Phase A, zero-Blocker design review, and the later exact same-task semantic approval required by the Delivery Protocol. A decision card is not issued until the measurement and review support it. No expensive baseline runs on a design-only head.

After approval: mandatory package check before every commit; meaningful fixture integrity/refusal controls; exact preservation of original inventory and source attribution; unchanged complete adopted-module, migration-owner and crash acceptance; repeated diagnostic comparison including added regression cost; complete implementation and exact-head zero-Blocker review; only then existing admission and both full hosted baselines, comparison, native/platform checks and sealed publication. A failed timing or hosted gate remains a failure, not grounds to weaken tests or acceptance. Final acceptance and exact-head merge authorization remain later separate task-user steps.

## Diagnostic provenance

The diagnostic artifacts are retained in the coordinating task, outside canonical conformance evidence. These hashes bind the inspected local records; they do not constitute hosted acceptance. The measurement scripts delegate existing APIs and leave tracked source unchanged at the measured base. A future implementation must repeat the relevant measurement against its actual fixture rather than reusing these schedule results.

| Record | SHA-256 |
| --- | --- |
| `measurement-report.md` | `193cf96b51dadcb1ff7ed0f507303e510c176273e75598cd11dbea2cf4e957be` |
| `stage1-summary.json` | `6acde33248f716ca5068d2373b315e3a82105567875057ffde11bc0bcbc4811c` |
| `ab-comparison.json` | `ba3103c8c3d353d4aacaf705d565362e30c779e75f1bca6312063e77a889662a` |
| `final-summary.json` | `33b8b99aa1433934d50b55df965b16ffb46b09c6460d2ac8fbad34befc3b3453` |
| `run_measurement.py` | `700a228280af2b60cc1823907acb5d50ba7155803c1e1b1e91a587554969fe65` |
| `run_schedule.py` | `310d950c9882c241403bd9e77452bea3ab17783dc6af1077152a2146be6b270d` |
| `artifact-manifest.json` | `02fdf34951ded846487ffca1cf23ed7f5c7b3caf8ec0d88835cb1630294dd585` |

The canonical seven-column ledger row payload for all four schedules has SHA-256 `61e15e76123c64781d755d278a88a80141f04fa00d7041f89df1efde69316b4e`. No private credentials, keys or raw private logs belong in this PR.

## Approved implementation and measurable utility

The original complete card (coordinator turn `01a143e9-206a-7202-a81b-bf94c1c66f5f`) precedes the exact user approval (turn `01a1446e-caa8-7693-87ed-9f678fb7e078`) in coordinator task `01a0aab4-3ce9-7540-abf2-41bc78b859b3`. Both original messages were retrieved before implementation. This record is navigation to that authority, not a substitute for the original messages. The approved design head was `ebdba97274cb0211ebc77c42e6a73503d2836982`; decision identity, version, named PR, boundary and invariants are unchanged.

[Supporting review 5547060150](https://github.com/samovers/OFARM2/pull/415#pullrequestreview-5547060150) reported zero Blockers, one Follow-up and three Preferences. Its separate prototype and modified non-TLS environment are supporting investigation only, with three inherited audit failures, not candidate acceptance. The remaining hosted capacity question stays with Delivery #410 / PR #411. Explicit complete-migration and real no-op lineage assertions are needed because some downstream consumers can pass with an incomplete schema. Preserve the existing 800-line cross-slice budget and include the added regression cost in the capacity calculation.

Before candidate timing, the implementation contract defined the local utility condition: on the same macOS arm64, CPython 3.12.13, PostgreSQL 17.10/native 1.0 TLS/SCRAM environment, measure the actual staged and implemented runtime generators in at least three interleaved staged/runtime/runtime/staged blocks with fresh services. Exclude imports and diagnostic observations from construction timing, report cleanup separately, and require at least 25% mean setup reduction, the minimum staged time greater than the maximum runtime time, and at least 10 seconds estimated net saving across fourteen setups after subtracting every added regression's setup, call and teardown cost. Also record aggregate tenant setup cost during actual adopted-module acceptance. This is a predeclared local component criterion, not a full-baseline or hosted-fit claim; failed criteria are not retuned after observing results.

## Implementation and local results — 16 October 2026

The complete implementation is inside the approved test-fixture construction and evidence-fidelity boundary. `kernel/tests/postgresql_tenant_support.py` owns the five operational target facts, unchanged role-DSN derivation and one fresh-service lifetime. Its module fixture executes the public complete migration and real no-op, checks all versions 1–11 and their actual execution/head lineage, then yields only operational facts. The staged owner extends those facts with its eleven genuine historical fields. All fourteen approved runtime registrations use the new fixture; the owner and manual crash route remain staged.

Twenty inexpensive fault and wiring controls cover incomplete migration reports, incorrect no-op lineage, dirty entry before cleanup custody, partial setup, body/cleanup failure visibility, the explicit staged route and all fourteen registrations. They replace database effects only within these new controls and add no repeated real migration workload. All 5,207 original inventory entries remain identical; the inventory now has 5,227 entries. Read-only source comparison preserves all 2,112 original test-function ASTs and 1,851 unaffected helper/fixture ASTs. The role-DSN method is moved unchanged; only the approved service-lifetime extraction changes the owner's fixture. The cross-slice module remains 800 lines. No production, migration, privilege, timing-limit, CI or publication policy change is included.

Twelve fresh-service samples, in three staged/runtime/runtime/staged blocks on the declared local environment, measured mean setup of 4.885114 seconds staged and 3.275791 seconds runtime: a 32.9434% reduction. The minimum staged time, 4.691405 seconds, remained above the maximum runtime time, 3.563756 seconds. All 20 added controls cost 0.110336 seconds in aggregate setup/call/teardown phases. The resulting fourteen-setup net component estimate is 22.420191 seconds. Actual aggregate tenant setup across the fourteen adopted modules was 45.042937 seconds. These pass the predeclared numerical utility conditions; they do not establish full-baseline time, hosted fit or successful acceptance.

Every measured service passed the existing structural verifier at version 11, role/grant and seven-column immutable-ledger checks, actual fresh-data/bootstrap observations, real no-op lineage and dirty-entry refusal. All fourteen runtime module databases and binder identities were distinct. Source snapshots remained unchanged throughout execution. These checks establish the stated preconditions, not equality of all database history or random identities.

The original local acceptance run remains **FAIL: 513 passed, 2 failed out of 515 selected cases**. It includes all 120 staged-owner cases, all 375 adopted-module cases and the 20 new controls, with no skips, deselections or collection errors. The two failures are signing-evidence refusals before their intended physical-outcome operations. One existing Starlette deprecation warning was recorded. The 26 unchanged crash cases were unavailable locally because the exact required amd64 image/archive was absent; its unchanged validator refused execution. Nothing was retagged, overridden or counted as a pass.

A bounded diagnostic comparison preserved these failures. The two initially failed cases passed individually once on the untouched base and once on the candidate; that did not identify their original cause. Running the first five original modules once per source then produced 258 passed/2 failed on the untouched base and 257 passed/3 failed on the candidate. External delegating observations captured two `SigningEvidenceError("receipt freshness differs")` refusals on each source: the later database observation was 45,611–118,676 microseconds earlier than the receipt's observation. Both times come from the unchanged database observation path. This establishes the same refusal mechanism on the base and candidate, not its environmental cause or the exact cause of the earlier uninstrumented failures. The third candidate failure exceeded the unchanged transport-time assertion, 3.792820 seconds against less than 3.5 seconds; its cause remains unclassified. There were no source, selection or service-cleanup discrepancies. No retries were used to replace failed outcomes with green results.

These are local diagnostic records, not canonical baseline evidence. Their retained names and SHA-256 digests are:

| Record under `implementation-20261016/acceptance/` | SHA-256 |
| --- | --- |
| `source-freeze.json` | `355cbd89b69e0a890dcd3b04a38196a9535ae13aaa22884ac37fdccdc9821fe4` |
| `utility-criteria.json` | `24bfa148ae4c0282239da3bae7fa20ffc0ea2e2ffe289d4a900610ddd9af12cc` |
| `attempt-02/acceptance-01.json` | `42eaf61ca259a421151e513b5bf4f3dad5d4942abb3fac86f791d782a7229d8b` |
| `attempt-02/utility-summary.json` | `6f2a0a0455ad39d0c5fd9fb557ca8a09fb191df02c56bd2b5d8e1e9c82482fb1` |
| `context-base-01.json` | `4f42d366718613a7e8b3eb1704ad0ebc37f2fb90c84f275eca81cf2f1a0a75eb` |
| `context-candidate-01.json` | `75d7e4620540c48caa889759e508d98d73d7f4914772385c10765820f12239de` |

The implementation remains provisional. The failed local run and unavailable crash coverage are open evidence limitations, not waived gates or demonstrated fixture defects. Any required signing, transport or execution-capacity repair stays in separate Delivery work under its own boundary. No changes from PRs #409, #411 or #413 were imported. An independent exact-head content review must precede admission; both complete hosted baselines, fixed equivalence, native/platform checks and authenticated publication remain required before final acceptance.

Next: complete the exact-head implementation review, then apply the existing hosted gates if review clears the implementation; keep every failed or unavailable result visible.
