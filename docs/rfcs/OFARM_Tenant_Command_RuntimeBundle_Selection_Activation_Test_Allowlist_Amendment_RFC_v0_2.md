# OFARM2 Tenant Command RuntimeBundle Selection Activation Test-Allowlist Amendment — Phase A Contract v0.2

**Contract identity:**
`ofarm.tenant-command-runtime-bundle-selection-activation-test-allowlist-amendment.issue176.v0.2`

**Decision identity:**
`ISSUE176-SELECTION-ACTIVATION-TEST-ALLOWLIST-001`, proposed version `1`

**Status:** proposed Phase A contract; documentation-only; unapproved

**Primary trust boundary:** governance of the exact repository file envelope
for the already-approved tenant RuntimeBundle-selection database Phase B

## 1. Decision

The approved database Phase B cannot complete its literal migration-release
verification while two existing V7 identity tests remain outside its exact
nine-path allowlist.

This amendment proposes one correction only: replace the parent contract's
nine-path Phase B allowlist with the complete eleven-path allowlist in section
5. The original nine paths and their permitted reasons remain unchanged. The
two added paths may change only the mechanically stale literal-identity tests
defined in section 6.

This contract does not implement migration 0008, change either test, or grant
database Phase B authority by authorship, review, commit, or merge. Until this
exact amendment is approved under the active pre-deployment workflow, its
documentation-only PR merges, and a separate implementation decision names
the database PR and complete eleven-path envelope, the database Phase B
remains paused at the original nine-path boundary.

## 2. Why this is one narrow boundary

The production changes already required by the parent contract necessarily
advance:

- the complete tenant authoritative migration-set digest from the seven-row
  V7 set to the eight-row V8 set; and
- the external final tenant catalog-verifier digest from the V7 verifier to
  the V8 verifier.

Two unit tests independently pin those exact production literals. They now
fail when the approved Phase B production files contain the required V8
values:

```text
kernel/tests/test_migration_sets.py::
test_tenant_v7_is_verifier_only_and_pins_write_lock_owner_admission

kernel/tests/test_postgresql_catalog_identity_unit.py::
test_tenant_v7_external_catalog_anchor_is_literal
```

The first test correctly preserves the V7 migration's own filename, source
digest, byte length, and verifier-only properties, but incorrectly equates the
complete current migration-set digest with the V7 prefix digest after V8 is
appended. The second test correctly requires a literal external catalog anchor,
but its name and expected value are fixed to V7 after the production anchor
lawfully advances to V8.

These are mechanical verification changes for the same database migration and
catalog-identity trust boundary. They add no runtime, credential, tenant,
principal, storage, route, output, or audit authority. Hiding the conflict in
production compatibility behavior would weaken the literal release authority
and is forbidden.

## 3. Pinned authorities and evidence

This amendment is subordinate to the complete merged parent contract:

| Authority | Exact identity |
| --- | --- |
| Parent contract | `ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1` |
| Parent path | `docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_Activation_Admission_RFC_v0_1.md` |
| Parent bytes | `52,382` UTF-8 bytes |
| Parent SHA-256 | `af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb` |
| Reviewed repository base | merge commit `9c061c8c7633e4c2b70cf25deb1ad53127a18f54` |
| Merged verifier prerequisite | PR `#290`, exact implementation head `abac4e1949eb8a13b45428f606e65e4f9bc791e9` |

At the reviewed base, the parent contract, its approval record, its authority
map, invariants, negative cases, non-goals, prerequisites, verification duties,
and stop conditions are accepted law. This amendment may change only the Phase
B file allowlist and the directly related verification-path statement.

The observed conflict is exact:

- the proposed V8 authoritative migration-set digest is
  `sha256:95e2a1b3b3e5d9b8bcc84c49a56a4b45c29aab7eb54d72b47d95fb871d36c67d`,
  while the existing V7 test expects the complete set to remain
  `sha256:5616797d1362c55c78175126edab29cc3e88c021ba0709e3766d3196d2b0126b`;
  and
- the proposed V8 external tenant catalog anchor is
  `sha256:c977adc2dbbdbc426173920f2f23f53ef998ec6c7be2849ab67867f30da5fa93`,
  while the existing test expects the V7 anchor
  `sha256:026bb61026a9f752fc8dde84bca0e3cbbab374d0ac8f0ba942a72654e44f5f1a`.

The V8 values remain implementation evidence subject to disposable-target
derivation and exact-head review. This Phase A amendment authorizes their
mechanical tests; it does not approve an incorrect value merely because it is
listed here.

## 4. Authority map

- The parent contract remains the sole design authority for selection storage,
  activation, fixed binding, database custody, knowledge allocation, atomicity,
  retry, RLS, and the production-versus-legacy firewall.
- This amendment owns only the replacement Phase B file allowlist in section 5
  and the closed permitted reasons for the two added tests.
- `deployment/postgresql/migration_sets.py` remains the production authority
  for the literal authoritative migration set.
- `deployment/postgresql/catalog_identity.py` remains the production authority
  for the external tenant catalog-verifier digest.
- The two newly admitted test files may verify those production literals; they
  do not define, derive, select, or override them.
- Reviewers own demonstrated contract and implementation Blockers.
- CI owns mechanical collection, test, lint, conformance, and exact-path
  evidence.
- The active pre-deployment workflow owns approval transport and the one-PR
  decision envelope.
- Runtime, routes, commands, outputs, deployment, legacy behavior, and #192
  retain their existing closed authorities.

## 5. Complete replacement Phase B allowlist

After this exact amendment is approved and its documentation-only PR merges,
the parent contract's section 14 allowlist is replaced only by this complete
table:

| Exact path | Permitted reason |
| --- | --- |
| `kernel/migrations/0008_tenant_command_runtime_bundle_selection.sql` | Immutable relation, composite keys, forced RLS, exact session-gated owner policies, mutation refusal, closed bound-tenant activation function, controller execute grant, and exact allocator branch. |
| `deployment/postgresql/migration_sets.py` | Append only the literal authoritative migration-0008 identity and new full-set digest. |
| `deployment/postgresql/catalog_identity.py` | Update only the external final verifier-pair digest. |
| `deployment/postgresql/README.md` | Document migration 0008, the bound control flow, and non-activation posture. |
| `deployment/postgresql/tenant_command_runtime_bundle_selection.py` | Fixed-binding validation and activation adapter requiring an already bound connection and accepting no tenant or principal argument. |
| `kernel/tests/test_postgresql_readiness_unit.py` | Mechanically changed final migration/readiness identity tests. |
| `kernel/tests/test_postgresql_tenant_migration.py` | Disposable real-role migration, exact controller-only function execution, owner-policy closure, binding, RLS, lock, atomicity, retry, refusal, and concurrency tests. |
| `kernel/tests/test_tenant_command_runtime_bundle_selection.py` | Focused fixed-binding adapter, closed-input, and runtime/legacy non-import tests. |
| `conformance/review_baseline_test_inventory.json` | Mechanical regeneration only if the canonical collected node IDs change. |
| `kernel/tests/test_migration_sets.py` | Preserve every V7 migration-0007 assertion while replacing the stale complete-set assertion with exact V7-prefix evidence and adding only the literal migration-0008 filename, source SHA-256, byte length, applied-prefix digest, and complete V8 set-digest assertions. |
| `kernel/tests/test_postgresql_catalog_identity_unit.py` | Rename or replace only the stale V7 external-anchor assertion so it pins the exact V8 `TENANT_CATALOG_VERIFIER_DIGEST`; no catalog observation, digest computation, injection, or refusal behavior may change. |

No path prefix, wildcard, generated-file family, or "related test" authority is
implied. The amendment RFC itself belongs only to its separate documentation
PR and is not an implementation path in the later database Phase B PR.

If implementation requires any twelfth path, broader change inside either
newly admitted test file, or a change to another production or conformance
authority, the database Phase B stops for a separate reviewed boundary.

## 6. Invariants

- **TATA-001 — Parent law is unchanged.** Every parent-contract trust boundary,
  authority, effect, non-effect, invariant, negative case, non-goal,
  prerequisite, verification duty, and stop condition remains controlling.
- **TATA-002 — Exactly two added paths.** The complete implementation envelope
  is the original nine paths plus exactly the two test files in section 5.
- **TATA-003 — V7 remains pinned as a prefix.** Migration 0007 retains its exact
  filename, source digest, byte length, verifier-only behavior, and applied
  prefix digest. Appending V8 does not rewrite V7 or claim that the complete
  set is still V7.
- **TATA-004 — V8 release identity is literal.** The migration-set test may pin
  only the exact eighth row and complete eight-row digest produced by the
  authoritative literal migration set.
- **TATA-005 — Catalog identity remains literal.** The catalog-identity unit
  test may change only its version label and expected final tenant anchor. The
  production catalog observer and digest algorithm remain unchanged.
- **TATA-006 — Tests are evidence, not authority.** Neither test may compute a
  permissive fallback, accept multiple current digests, mutate production
  values, monkeypatch release authority, or weaken fail-closed comparison.
- **TATA-007 — One database boundary.** The two tests verify the same migration
  release and catalog-anchor changes already owned by the parent database
  Phase B; they introduce no independent trust boundary.
- **TATA-008 — No implementation in this PR.** The amendment PR changes exactly
  this RFC and no production, test, inventory, workflow, or active artifact.
- **TATA-009 — No retained state.** Later Phase B remains limited to disposable
  PostgreSQL targets that are rolled back or destroyed and creates no retained
  tenant selection.
- **TATA-010 — Closed production surface.** No runtime selector, command
  integration, route, read, output, deployment, legacy behavior, or #192
  behavior is admitted.

## 7. Required negative cases

Review and conformance must refuse:

- editing either added test before this exact amendment is approved and
  merged;
- deleting or weakening a V7 migration-0007 identity or verifier-only
  assertion;
- making the V7 prefix assertion depend on the complete V8 set digest;
- accepting both V7 and V8 as current complete migration-set identities;
- deriving the expected V8 migration or catalog digest from the implementation
  value under test;
- changing migration loading, source authentication, digest policy, catalog
  observation, catalog hashing, trust-anchor injection, or refusal behavior in
  either added test file;
- changing an unrelated test in either added file;
- editing the parent RFC, another frozen contract, candidate artifact,
  conformance checker, workflow, or active registry;
- adding a twelfth Phase B path;
- retaining a database, batch, selection row, credential, capability, or target
  after verification;
- opening runtime, command, route, read, historical, WINDOW, output,
  deployment, legacy, or #192 behavior; or
- treating review, CI, commit, merge, repository credentials, or this document
  as architect approval.

## 8. Non-goals

This amendment does not:

- implement, validate, or approve migration 0008 or its final digests;
- edit the parent contract or any accepted prerequisite;
- change a production module, SQL source, test, README, or inventory;
- add database storage, roles, grants, functions, policies, credentials, rows,
  batches, or knowledge positions;
- reconcile or upgrade an existing database target;
- add a new test framework, helper service, generic release mechanism, alias,
  compatibility value, or dual-current identity;
- resume the database Phase B before the amendment and later implementation
  approvals are complete;
- authorize another implementation PR, transfer the amendment approval, or
  treat the parent nine-path approval as authority for the two added paths;
- publish or select a RuntimeBundle; or
- change runtime, semantic, output, legacy, deployment, or #192 authority.

## 9. Smallest coherent change

The complete Phase A change is this one RFC in one documentation-only PR.

After approval and merge, the existing paused database Phase B branch may be
rebased onto the amendment. Before another implementation edit, the active
pre-deployment workflow must bind a separate implementation decision to the
already-created database PR and the complete eleven-path table in section 5.
The amendment approval cannot transfer to, authorize, or be replayed for that
PR. After the exact later implementation approval, the two new test edits must
be mechanically minimal:

1. preserve the migration-0007 test and replace only its stale complete-set
   assertion with the exact version-7 prefix digest;
2. add one focused migration-0008 literal identity test;
3. rename or replace the V7 external-anchor test with one exact V8 anchor
   assertion; and
4. regenerate the canonical node inventory only if node IDs change.

No production workaround, compatibility branch, duplicated authority, or
general test refactor is permitted.

## 10. Verification

Phase A must prove:

- the parent contract path, byte length, digest, identity, and approved status;
- the reviewed base includes merged verifier PR #290;
- the existing database Phase B partial diff remains untouched by this PR;
- the two named existing tests fail only because their old literal values
  conflict with the required V8 production identities;
- this PR changes exactly this RFC;
- the complete section-5 table equals the parent nine-path table plus exactly
  the two closed test paths;
- the package, temporal, architecture, decision-log, and documentation checks
  pass under the repository-pinned Python runtime; and
- one full exact-head technical review reports no unresolved Blocker before a
  live decision card is presented.

Later database Phase B must prove every parent section-15 requirement plus:

- migration 0007 retains its exact source identity and its version-7 applied
  prefix digest;
- migration 0008 has one exact literal filename, source digest, byte length,
  applied-prefix digest, and complete-set digest;
- the external tenant catalog anchor has exactly one V8 literal value;
- the two added test files contain no unrelated semantic change; and
- the cumulative implementation diff is a subset of the complete eleven-path
  allowlist.

## 11. Stop conditions

Work stops before:

1. changing either added test until this exact amendment is approved and
   merged and the separate database implementation decision is approved;
2. implementing database Phase B under an unreviewed or unapproved widened
   envelope;
3. changing the parent design, production authority map, invariant, effect,
   non-effect, negative case, non-goal, prerequisite, or stop condition;
4. editing any path outside section 5 in the database Phase B PR;
5. using test compatibility behavior to conceal two current production
   identities;
6. changing another trust boundary or active artifact;
7. using a retained or existing database target; or
8. adding runtime, route, command, read, output, deployment, legacy, or #192
   behavior.

## 12. Approval and next sequence

This proposal is not approved by authorship, commit, PR creation, review,
mergeability, CI, repository credentials, or the earlier approval of the
parent nine-path contract.

The active pre-deployment workflow requires one complete live decision card in
the designated Codex task naming the already-created amendment PR. A later
exact user-authored approval message in that same task may authorize only the
documentation-only amendment PR. The database implementation remains paused
until that approved amendment merges and a separate live implementation card
names the already-created database PR, the parent design, this merged
amendment, and the complete eleven-path envelope. Only the exact later approval
of that implementation card may resume database Phase B.

The required sequence is:

```text
ONE-FILE AMENDMENT DRAFT PR
  -> EXACT-HEAD TECHNICAL REVIEW WITH NO BLOCKER
  -> COMPLETE LIVE DECISION CARD
  -> EXACT LATER SAME-TASK USER APPROVAL
  -> DOCUMENTATION-ONLY AMENDMENT MERGE
  -> REBASE PAUSED DATABASE PHASE B
  -> CREATE OR REUSE THE DRAFT DATABASE PR
  -> COMPLETE DATABASE IMPLEMENTATION CARD FOR ELEVEN PATHS
  -> EXACT LATER SAME-TASK DATABASE IMPLEMENTATION APPROVAL
  -> IMPLEMENT ONLY THE COMPLETE ELEVEN-PATH ENVELOPE
  -> DISPOSABLE DATABASE AND CONFORMANCE VERIFICATION
  -> EXACT-HEAD IMPLEMENTATION REVIEW
  -> MERGE DATABASE PHASE B ONLY WHEN EVERY GATE PASSES
```

The amendment decision grants no database mutation, implementation, or merge
authority for the later database PR. It changes only the reviewed file
envelope. The separate database implementation decision must preserve every
parent effect, non-effect, invariant, and stop condition while naming the two
added mechanical test paths explicitly.
