# OFARM2 RuntimeBundle Global Content Retention Provisioning-Classifier Admission — Phase A Contract v0.1

**Status:** proposed and inactive Phase A contract; documentation-only;
unapproved; no implementation or database effect

**Contract identity:**
`ofarm.runtime-bundle-global-content-retention-provisioning-classifier-admission.issue176.v0.1`

**Decision identity:**
`ISSUE176-RUNTIME-CONTENT-RETENTION-PROVISIONING-CLASSIFIER-001`, version `1`

**Reviewed base:** `dc8f9d8c976ed15c5fd2a660e58f34f579de2dde`

**Primary ticket:** #176

**Primary trust boundary:** fail-closed provisioning and locked-migration
classification of the exact tenant migration release before and after future
migration 0009

**Intended PR boundary:** this RFC only before approval; after approval, the
same named pre-deployment PR may implement only section 10's five-path
allowlist

## 1. Problem, goal, and learning value

The approved global-content-retention database Phase B stopped correctly on a
clean disposable PostgreSQL 17 target. Adding an exact ninth migration to
`TENANT_AUTHORITATIVE_MIGRATION_SET` makes the existing production
provisioning classifier reject the still-exact eighth migration:

```text
_authoritative_tenant_selection_activation_migration()
  -> requires len(authority.migrations) == 8
  -> returns no V8 authority when the complete release has nine rows
  -> locked provisioning reports "tenant binding admission phase differs"
  -> migrate_service refuses "migration widened the provisioning boundary"
```

The classifier also has no exact durable-ledger case for a committed ninth
row. The database contract does not allow `deployment/postgresql/provisioning.py`
to change, so that implementation was reverted and every disposable target was
destroyed.

This contract admits one narrow prerequisite: preserve the exact V5-V8
selection-admission meaning while allowing the classifier to extract the exact
V8 prefix from a closed eight- or nine-migration literal release and to
recognize one exact durable V9 ledger state. It validates that the migration
gate can advance without a caller-selected mode, a generic future-version
fallback, or a V9-specific runner bypass.

The delivered learning value is explicit: release growth and selection-ACL
state are different dimensions. A migration head may advance from V8 to V9
while the already governed selection-controller ACL remains the exact
`A4 / STABLE_V8` projection.

## 2. Governing authorities and relationship to paused database Phase B

The controlling database design is:

- path:
  `docs/rfcs/OFARM_RuntimeBundle_Global_Content_Retention_Admission_RFC_v0_1.md`;
- identity:
  `ofarm.runtime-bundle-global-content-retention-admission.issue176.v0.1`;
- complete merged length: `38,116` UTF-8 bytes; and
- complete merged SHA-256:
  `sha256:aa5de04c08390e1439d59f39c4b6f5608e8b43b320fec531721d9c53b936873a`.

Its test-allowlist amendment is:

- path:
  `docs/rfcs/OFARM_RuntimeBundle_Global_Content_Retention_Catalog_Anchor_Test_Allowlist_Amendment_RFC_v0_2.md`;
- identity:
  `ofarm.runtime-bundle-global-content-retention-catalog-anchor-test-allowlist-amendment.issue176.v0.2`;
- complete merged length: `19,491` UTF-8 bytes; and
- complete merged SHA-256:
  `sha256:b126e49f6c86bfe6bdac81480c6af6ed9c719d9abecbcd13535a7aa326e8e9a3`.

Those contracts authorize migration 0009 only in their exact eleven-path
database envelope and require work to stop when another production authority
must change. This RFC is the separate prerequisite required by that stop. It
does not edit, reinterpret, or widen the database envelope.

The accepted selection-provisioning classifier design remains controlling:

- path:
  `docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_Provisioning_Verifier_Admission_RFC_v0_1.md`;
- identity:
  `ofarm.tenant-command-runtime-bundle-selection-provisioning-verifier-admission.issue176.v0.1`;
- complete merged length: `39,935` UTF-8 bytes; and
- complete merged SHA-256:
  `sha256:24d56e67430efb0e145b31217a4898010ec437bd235b9cd8c82d25570fd58fe5`.

It owns the accepted `A0`, `A1`, `A2`, and `A4` admission phases and the
`NOT_APPLICABLE`, `STABLE_V7`, `V8_POST_SOURCE_PRE_LEDGER_APPEND`, and
`STABLE_V8` selection-controller ACL substates. This contract preserves that
vocabulary and meaning.

Reviewed implementation baselines at the base commit are:

| Authority | Exact reviewed identity |
| --- | --- |
| Literal tenant migration release | eight migrations; digest `sha256:7231c869066c56f7c642460d33391bab00456daecdb04530b34da7210e8e8a54`; exact V8 file `0008_tenant_command_runtime_bundle_selection.sql`, 37,933 bytes, source `sha256:635e476fb4eb93073ed353397a977ea887c42e1be11b42f9a4782a76f88ab765` |
| `deployment/postgresql/migration_sets.py` | Git blob `b44dc3816b37a9ec942aa97329521d8701ae011a` |
| `deployment/postgresql/provisioning.py` | Git blob `8c7c2db7d9ce6ceee87e6b74db576f109870d51b` |
| `deployment/postgresql/migration_runner.py` | Git blob `36284b3595c5b1fcd260eef3cba3ee3c13fd04d4` |
| `kernel/tests/test_postgresql_provisioning.py` | Git blob `2e741327c29204abb019aa1cfae123a087fd3aa7` |
| `kernel/tests/test_postgresql_migration_runner.py` | Git blob `c84add016f451687015c2795f504ef8921fc67fe` |

If any reviewed authority changes before implementation, work stops for an
exact-head assessment. A semantics-preserving rebase may update a source blob
pin only when the relevant behavior and this contract remain unchanged.

After this classifier prerequisite is approved, implemented, reviewed, and
merged, the paused database Phase B may rebase on it and resume only under its
existing eleven-path law and stop conditions. The two PRs may not absorb each
other.

## 3. Non-goals

Neither this contract nor its later classifier implementation will:

- add migration 0009 or another migration-set row;
- create `ofarm.retain_runtime_content`, issue a grant, or retain content;
- edit `migration_sets.py`, `migration_runner.py`, a provisioning
  specification, an existing migration, or the SQL structural verifier;
- add a new admission phase, selection-ACL substate, caller flag, capability
  bag, environment switch, public verifier, or generic migration hook;
- accept migration head 10 or any unspecified future head;
- change V5-V8 capsule, grant, ledger, or transition meanings;
- publish or select a RuntimeBundle, choose a tenant, create a governed batch,
  or retain tenant or RuntimeBundle state;
- activate temporal artifacts, commands, current/default state, routes, reads,
  materialization, historical/WINDOW behavior, or outputs;
- change production-to-legacy isolation, legacy behavior, or #192; or
- deploy, reconcile, repair, backfill, or mutate a retained target.

## 4. Trust model

### 4.1 Protected assets

Protected assets are the literal migration-release identity, exact V8 prefix,
exact durable ledger phase, selection-controller ACL meaning, locked migration
ordering, database rollback boundary, and the distinction between release
authority and observed target state.

### 4.2 Trusted components

Trusted components are PostgreSQL 17; the exact contracts in section 2; the
literal `TENANT_AUTHORITATIVE_MIGRATION_SET`; existing
`require_authoritative_migration_set`; the production locked runner; the
provisioning classifier; the migration-owned final structural verifier and
external catalog anchor; and repository review and CI.

Tests may construct controlled authority objects and disposable database
states as evidence. They are not production authority and cannot promote a
synthetic migration.

### 4.3 Untrusted actors and inputs

Untrusted inputs include every DSN, release identity, execution UUID,
environment value, caller argument, directory listing, filename discovered by
scan, target ledger row before authentication, catalog observation, role,
tenant, principal, RuntimeBundle digest, content digest, and application or
worker request.

The task user decides whether to approve this repository-development boundary.
GitHub credentials, AI-generated text, CI, and repository state are not that
decision authority.

### 4.4 Excluded compromise capabilities

PostgreSQL superuser compromise, repository-host compromise, task-platform
role compromise, arbitrary local source substitution after verification,
malicious dependencies, operating-system compromise, and cryptographic hash
failure are outside this contract. Normal target drift, malformed literal
authority, malformed ledger evidence, and caller-controlled inputs remain in
scope and fail closed.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Which migrations form the production tenant release | Literal `TENANT_AUTHORITATIVE_MIGRATION_SET`, changed only by the later database PR |
| Whether that release is exact before execution | Existing `require_authoritative_migration_set` |
| Exact V8 identity inside an eight- or nine-row release | The eighth literal `AuthoritativeMigration` row, only when the complete release is one of the two closed lengths and its service, ordering, version, and filename are exact |
| Exact V9 identity | The ninth literal `AuthoritativeMigration` row, available only when the complete release has exactly nine rows and the row is version 9 with filename `0009_runtime_bundle_global_content_retention.sql` |
| Durable V5-V9 admission classification | `deployment/postgresql/provisioning.py`, comparing exact ledger evidence with the literal authority |
| V8 post-source/pre-ledger transition | Existing private V8 runner seam and accepted selection-provisioning contract; unchanged |
| V9 source execution and ledger append | Existing generic production migration-runner path; unchanged |
| Retention function, ACL, replay, and structural identity | Parent database contract, future migration 0009, migration-owned verifier, and catalog anchor |
| Runtime, selection, command, route, output, deployment, legacy, and #192 behavior | Their separate existing or future authorities; unchanged |

No directory scan, database observation, test fixture, caller field, generic
version comparison, or documentation digest is an alternate release authority.

## 6. State machine and ordering

This contract distinguishes the complete literal release from the durable
target ledger. `R8` and `R9` mean exact closed authoritative releases, not
caller-supplied integers. `L7`, `L8`, and `L9` mean authenticated exact ledger
prefixes.

Supported projections are:

```text
R8 + existing L0..L7
  -> preserve the accepted A0/A1/A2/A4 and V8-transition rules

R8 + exact L8
  -> A4 / STABLE_V8

R9 + existing L0..L7
  -> preserve the same accepted phases
  -> exact eighth row remains available to the existing V8 transition

R9 + exact L8
  -> A4 / STABLE_V8
  -> migration 0009 is pending; no V9-specific bypass exists

R9 + exact L9
  -> A4 / STABLE_V8
  -> the selection-controller ACL shape is unchanged at release head 9
```

`STABLE_V8` names the exact selection-controller ACL substate introduced at
V8. It does not claim that the migration head is always 8. Adding
`STABLE_V9` would duplicate ledger-head state and imply an ACL transition that
does not occur.

The only lawful database ordering after the separate database PR supplies the
exact R9 release is:

```text
authenticate complete R9 release
  -> lock caller-owned migration transaction
  -> authenticate current ledger and exact R9/L8 projection
  -> execute exact migration-0009 source
  -> run the unchanged generic locked-boundary check
  -> verify history remained L8
  -> append exact L9 ledger row
  -> run final SQL structure and external catalog verification
  -> commit, or roll back every V9 effect
```

This classifier PR changes only the release/ledger recognition needed at those
existing checks. It neither executes a source nor writes a ledger row.

Forbidden states include R8/L9, R9 with an inexact V8 prefix, an inexact V9
row, any release longer than nine, any gap or reorder, and any V9 acceptance
selected from a caller or observation. They return no classification and cause
the existing locked migration boundary to refuse.

## 7. Invariants and acceptance criteria

- **GCPV-001 — Parent law unchanged.** The parent database and test-amendment
  contracts, their eleven-path envelope, invariants, and stop conditions are
  not edited or reinterpreted.
- **GCPV-002 — One classifier authority.** Durable admission state remains
  classified only by `deployment/postgresql/provisioning.py` from literal
  authority and exact ledger evidence.
- **GCPV-003 — Closed release family.** Only exact R8 and exact R9 releases are
  recognized. Another length, service, order, version, or filename refuses.
- **GCPV-004 — V8 prefix survives release growth.** Exact R9 exposes the exact
  eighth authority row to the already accepted V8 transition without treating
  the complete release as R8.
- **GCPV-005 — Exact V9 ledger.** Stable V9 recognition requires count 9,
  minimum 1, maximum 9, the preserved exact V5-V8 evidence, and the exact V9
  filename, source digest, byte length, prefix digest, service identity, and
  provisioning-spec digest from literal authority.
- **GCPV-006 — Selection state does not fork.** Exact L8 and L9 both project to
  the existing `A4 / STABLE_V8` selection-ACL state. No phase or substate is
  added or renamed.
- **GCPV-007 — No caller-selected posture.** No input, environment value,
  observed function, observed ACL, release label, or generic boolean selects
  R9 or changes classifier behavior.
- **GCPV-008 — Runner remains closed.** Production and test runner entry
  points, the private V8 seam, transaction order, history append, and final
  verification are unchanged. There is no special V9 runner branch.
- **GCPV-009 — Fail closed before side effects.** An inexact authority or
  durable phase is refused by the existing locked checks; the classifier does
  not repair or mutate state.
- **GCPV-010 — Final SQL custody unchanged.** Function structure, ACL,
  immutability, replay, complete-catalog identity, and V9 ledger truth remain
  owned by the future database migration and final verifier, not duplicated
  in this classifier.
- **GCPV-011 — Production semantic surface remains closed.** The classifier
  creates no content, bundle, selection, temporal meaning, route, read,
  output, deployment, legacy effect, or #192 effect.
- **GCPV-012 — Exact path boundary.** Before approval only this RFC changes;
  after approval every changed path is inside section 10.
- **GCPV-013 — Disposable evidence only.** Tests use controlled objects and
  disposable or rolled-back PostgreSQL targets and retain no service state.

## 8. Required negative cases

| Invariant | Concrete counterexample at a supported entry | Required result |
| --- | --- | --- |
| GCPV-001 | A review fix edits the parent contract or database allowlist | Stop and split the boundary |
| GCPV-002 | A runner or test independently decides that V9 is stable | Refuse; provisioning classifier remains sole authority |
| GCPV-003 | Literal release has 7, 10, duplicate, reordered, wrong-service, wrong-version, or wrong-filename rows | No R8/R9 authority and locked migration refusal |
| GCPV-004 | Exact R9 exists but the V8 helper still requires total length 8 | Focused regression test fails; implementation is incomplete |
| GCPV-005 | L9 has a null, substituted, or copied V9 field, or count/min/max differs | No classification; locked migration refusal |
| GCPV-006 | Implementation adds `A5`, `STABLE_V9`, or changes the V8 ACL expectation | Contract and source-structure tests refuse |
| GCPV-007 | Caller passes `allow_v9=True`, an environment variable, or an observed function marker | API and source review refuse |
| GCPV-008 | Implementation adds a V9 branch or bypass in `migration_runner.py` | Changed-path gate refuses and work stops |
| GCPV-009 | Classifier repairs a ledger row or tolerates a partial state | Mutation/behavior tests refuse |
| GCPV-010 | Classifier validates retention-function body or grants | Boundary review refuses duplicated SQL authority |
| GCPV-011 | A classified V9 state is treated as content, bundle, tenant selection, current truth, or runtime activation | No supported seam; changed-path and conformance gates refuse |
| GCPV-012 | Any unlisted code, test, documentation, workflow, temporal, legacy, or #192 path changes | Stop without widening this PR |
| GCPV-013 | A test leaves an OFARM database, role, content row, or bundle state behind | Test boundary fails; target is destroyed before completion |

Private-field mutation is not required. Controlled authority objects may test
classifier mechanics, and disposable PostgreSQL targets may exercise the
existing public migration boundary. Neither is production authority.

## 9. Proposed architecture and smallest coherent change

The implementation should make one closed evolution in
`deployment/postgresql/provisioning.py`:

1. Replace the total-length-eight assumption with a helper that authenticates
   the complete literal release as exactly R8 or R9.
2. Return the exact eighth row for both R8 and R9, preserving the existing V8
   transition seam.
3. Return the exact ninth row only for R9 and only when its version and filename
   are the governed migration-0009 identity.
4. Extend the existing ledger observation with the V9 row's exact fields.
5. Add one exact R9/L9 comparison that returns the existing
   `A4 / STABLE_V8` projection.
6. Preserve every existing earlier-phase branch and every selection-ACL
   observation unchanged.

The helper consumes the already bound `AuthoritativeMigration` objects rather
than duplicating digest fields, inventing a new registry, or accepting
correlated caller inputs. The existing runner already calls the ordinary
locked provisioning check before and after each source and the final SQL
verifier after ledger append. No runner change is needed or allowed.

If real implementation proves that a special V9 transition seam or a
`migration_runner.py` edit is necessary, this design is invalidated and work
stops for another Phase A decision. It must not be smuggled into this PR as a
review fix.

## 10. Pull-request boundary and exact allowlist

Before approval, the PR may contain only the RFC path below. After valid
approval under section 15, the same named PR remains limited to these five
paths:

| Exact path | Permitted reason |
| --- | --- |
| `docs/rfcs/OFARM_RuntimeBundle_Global_Content_Retention_Provisioning_Classifier_Admission_RFC_v0_1.md` | This contract, truthful approval status, and compact approval evidence. |
| `deployment/postgresql/provisioning.py` | Closed R8/R9 literal-authority extraction and exact L9 admission classification only. |
| `kernel/tests/test_postgresql_provisioning.py` | Focused classifier state, authority, exact-field, and fail-closed tests. |
| `kernel/tests/test_postgresql_migration_runner.py` | Focused evidence that the unchanged ordinary runner boundary accepts exact pending R9/L8 classification and refuses malformed states without a V9 bypass. |
| `conformance/review_baseline_test_inventory.json` | Mechanical regeneration only if the canonical collected node inventory changes, including a count or node-ID change. |

No path prefix, wildcard, generated family, or “related file” is implied.
`deployment/postgresql/migration_runner.py`, `migration_sets.py`, provisioning
specifications, SQL migrations, parent RFCs, and temporal checkers are
explicitly outside this PR.

The paused database branch is not implementation input. It may resume only
after this separate PR merges.

## 11. Elegance audit

- Release sources of truth: one literal migration-set binding.
- Durable admission classifiers: one provisioning classifier.
- Selection admission phase families after implementation: one unchanged
  family, `A0/A1/A2/A4`.
- Selection ACL substates after implementation: four unchanged values.
- New runner branches, flags, registries, services, roles, or database objects:
  zero.
- Duplicated V9 digest fields outside literal authority: zero.
- Compatibility shims or future-version fallbacks: zero.
- Production files changed in later Phase B: one.

A rewrite is not justified. The defect is one total-release-length assumption
and one missing exact durable-row comparison in the existing authority owner.

## 12. Traceability and verification

| Invariants | Owning later seam | Negative evidence | Smallest acceptance verification |
| --- | --- | --- | --- |
| GCPV-001, 012 | exact diff allowlist | parent, runner, migration, or unrelated path changes | name-only diff and package contract check |
| GCPV-002, 003, 007 | closed release helper in `provisioning.py` | wrong length/service/order/version/filename and caller-selected inputs | focused provisioning unit tests |
| GCPV-004, 006 | exact V8 extraction and existing projection | R9 hides V8, or new phase/substate appears | controlled R8/R9 authority tests and enum/phase closure assertions |
| GCPV-005, 009 | exact ledger query and R9/L9 comparison | each V9 evidence field absent or substituted | parameterized classifier refusal tests |
| GCPV-008 | unchanged runner plus focused tests | V9 branch, bypass, or test-only production authority | source-structure and public-boundary tests |
| GCPV-010 | unchanged SQL/final-verifier authorities | classifier duplicates function or ACL semantics | changed-path gate and later database integration proof |
| GCPV-011 | unchanged runtime and semantic authorities | classified head produces runtime or truth effect | temporal and architecture conformance |
| GCPV-013 | disposable fixtures | retained service or state | fixture teardown and clean-target assertions |

Phase A verification must prove:

- only this RFC differs from the reviewed base;
- every section-2 authority pin is exact;
- the problem reproduces from the current production classifier source;
- the state model, authority map, invariants, negative cases, allowlist, and
  stop conditions are internally consistent;
- `git diff --check` passes; and
- `python3 conformance/ofarm_pkg_contract_check.py` passes.

After approval, focused implementation verification must include:

```text
python3 -m pytest -q kernel/tests/test_postgresql_provisioning.py
python3 -m pytest -q kernel/tests/test_postgresql_migration_runner.py
python3 conformance/temporal_contract_candidate_check.py
python3 conformance/rewrite_architecture_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

PostgreSQL-backed tests must use the exact repository-supported PostgreSQL 17
build on disposable targets. Hosted conformance and native architecture lanes
remain required before merge.

The later database Phase B, not this classifier PR, must prove the complete
production sequence from exact R8 through real migration 0009, exact L9,
catalog authentication, no-op retry, rollback, and destruction of the target.

## 13. Provisional design record

Not provisional. The release/ledger separation and closed R8/R9 recognition
are production design law for this release.

The repository's same-task approval evidence remains a provisional
pre-deployment workflow and must be replaced by independently human-controlled,
independently verifiable approval or signing before deployment.

## 14. Open decisions, review disposition, and stop conditions

No design decision remains open. The implementation intentionally does not
pre-decide migration head 10 or any later release.

Current disposition:

- **Blocker:** this contract requires exact-head technical review before a live
  decision card.
- **Follow-up:** resume the already approved eleven-path database Phase B only
  after this prerequisite merges.
- **Preference:** none.

Stop before implementation or merge if:

1. a governing authority or reviewed behavior differs;
2. the exact-head review finds a decision-level contradiction;
3. approval is absent, invalid, cancelled, superseded, or no longer directly
   retrievable in the same Codex task;
4. implementation needs a path outside section 10;
5. `migration_runner.py`, `migration_sets.py`, a provisioning specification,
   SQL migration, parent contract, or temporal checker must change;
6. a new phase, substate, public API, caller flag, environment input, generic
   future-version fallback, or V9 transition bypass is required;
7. an existing V5-V8 meaning or V8 transition rule must change;
8. retention-function, ACL, catalog, runtime, selection, route, output,
   deployment, legacy, or #192 semantics enter this classifier; or
9. verification requires a retained target or weakens an existing test.

A valid cross-boundary finding becomes a separate prerequisite or follow-up.
It never widens this PR merely to clear review.

## 15. Pre-deployment approval and next sequence

This proposal is not approved by authorship, commit, PR, review, CI,
mergeability, repository credentials, or the earlier database Phase B request.
It must first exist as the only change in one named draft PR and pass exact-head
technical review.

The later complete live decision card must name that PR and use this exact
approval sentence:

```text
I approve OFARM2 decision ISSUE176-RUNTIME-CONTENT-RETENTION-PROVISIONING-CLASSIFIER-001 version 1.
```

Only that entire visible sentence in a later user-authored message in this same
Codex task can approve the decision. Approval authorizes only the named PR and
section 10. A material card or contract change requires a new decision version.

The required sequence is:

```text
ONE-FILE PHASE_A RFC IN NAMED DRAFT PR
  -> EXACT-HEAD TECHNICAL REVIEW
  -> COMPLETE LIVE DECISION CARD
  -> EXACT LATER USER APPROVAL
  -> CLASSIFIER IMPLEMENTATION IN THE SAME PR
  -> FOCUSED AND CONFORMANCE VERIFICATION
  -> EXACT-HEAD REVIEW AND MERGE
  -> REBASE PAUSED DATABASE PHASE_B
  -> RESUME ONLY ITS EXISTING ELEVEN-PATH BOUNDARY
```

This Phase A stops before implementation.
