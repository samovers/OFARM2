# OFARM2 Tenant Command RuntimeBundle Selection Provisioning-Verifier Admission — Phase A Contract v0.1

**Status:** proposed Phase A contract; inactive and unapproved; documentation
only; no provisioning, migration, grant, database, runtime, route, output,
deployment, legacy, or #192 effect

**Contract identity:**
`ofarm.tenant-command-runtime-bundle-selection-provisioning-verifier-admission.issue176.v0.1`

**Decision identity:**
`ISSUE176-SELECTION-PROVISIONING-VERIFIER-001`, version `1`

**Reviewed base:** `d86dede91088dd1ab4cbc5a9e5664a2fa321f199`

**Primary ticket:** #176

**Primary trust boundary:** fail-closed provisioning and locked-migration
recognition of the one controller-to-activation-function EXECUTE ACL created by
the separately governed migration 0008

**Intended PR boundary:** this RFC only before approval; after approval, the
same named pre-deployment PR may implement only the six-path allowlist in
section 10

## 1. Decision

The database Phase B work authorized by the parent contract correctly stopped
when migration 0008's required controller EXECUTE grant was rejected by the
active provisioning verifier. The parent Phase B allowlist does not include
that verifier and therefore cannot change its authority.

This contract admits one separate, narrow verifier change. It permits the
provisioning verifier and migration runner to recognize exactly these states:

```text
STABLE_V7
  -> AUTHENTICATED_V8_SOURCE_EXECUTING
  -> V8_POST_SOURCE_PRE_LEDGER_APPEND
  -> STABLE_V8
```

`STABLE_V7` continues to require exactly the existing two binder-owned
selection-control grants. `V8_POST_SOURCE_PRE_LEDGER_APPEND` is a
transaction-local runner posture that permits exactly one additional
owner-owned controller grant after the exact authoritative migration 0008
source executes and before the runner appends its ledger row. `STABLE_V8`
requires that same exact third grant and an exact authenticated V8 ledger row.

The transition posture is selected only by reviewed migration-runner code from
the literal authoritative tenant migration-set binding. It is never selected
from caller data, a function-existence observation, an ACL observation, a
database marker, an environment value, a release identifier, or a generic
boolean or capability bag.

This decision changes verifier acceptance only. It does not create the
activation function, issue or revoke a grant, create migration 0008, append a
ledger row, modify database state, select a RuntimeBundle, or activate temporal
behavior.

## 2. Relationship to the paused database Phase B

The governing parent is:

- path:
  `docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_Activation_Admission_RFC_v0_1.md`;
- identity:
  `ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1`;
- complete merged byte length: `52,382`;
- complete merged SHA-256:
  `sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb`.

Its section 14 confines database Phase B to nine paths and says to stop if an
additional provisioning or authority path is required. The stop occurred
before a database Phase B commit or PR. This contract is the separate boundary
required by that stop condition. It supplements the prerequisite sequence; it
does not edit, reinterpret, or enlarge the parent's nine-path database
allowlist.

After this verifier admission is approved, implemented, reviewed, and merged,
the paused database branch may be rebased on that merged result and resume only
under the parent's existing database allowlist and stop conditions. The
verifier PR may not absorb any paused database draft. The later database PR may
not edit the verifier or runner.

## 3. Fixed governing authorities

| Authority | Exact reviewed identity |
| --- | --- |
| Architecture | `reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md`; 96,406 bytes; `sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256` |
| Migration and provisioning law | `docs/adr/0001-tenancy-and-schema-migrations.md`; 147,112 bytes; `sha256:bc49e566ddbdf98868162aa7ccca0940fa76fca1bfaaa261c8c831dbb5515a4d` |
| Temporal separation | `docs/adr/0002-valid-time-and-knowledge-time.md`; 61,427 bytes; `sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796` |
| TenantBinding authority | `docs/adr/0003-tenant-capability-trust-and-binder.md`; 93,419 bytes; `sha256:b188f4d60e46887fde4231e73bb00adb9bd70b75e807627e8a3906389a0fa5be` |
| Parent selection-activation contract | Exact path, identity, byte length, and digest in section 2 |
| Current tenant migration authority | `deployment/postgresql/migration_sets.py::TENANT_AUTHORITATIVE_MIGRATION_SET`; exact reviewed seven-migration digest `sha256:5616797d1362c55c78175126edab29cc3e88c021ba0709e3766d3196d2b0126b` |
| Current provisioning verifier source | `deployment/postgresql/provisioning.py`; reviewed Git blob `efd78f52b2b152fe67ee7c454feba3edbaff0160` |
| Current migration runner source | `deployment/postgresql/migration_runner.py`; reviewed Git blob `cbf5e956733e39b16e20652d6b89541dd5b58c57` |
| Current migration-set source | `deployment/postgresql/migration_sets.py`; reviewed Git blob `c14919d8b94c0ad9ac9ca2b51f1692135d554cfb` |
| Active pre-deployment workflow | `docs/rfcs/OFARM2_Predeployment_AI_Assisted_Development_Workflow_RFC_v0_1.md` and the merged prospective rules in `AGENTS.md` and `TASK_PROMPT.md` |

The current authoritative set ends at V7. This contract does not add V8 to
that set. The separate database Phase B remains the sole authority permitted
to add the exact migration-0008 source and its literal
`AuthoritativeMigration` row under the parent's allowlist.

The verifier implementation must consume the future V8 identity from that
reviewed, literal, versioned migration-set binding. It must not duplicate an
unreviewed V8 digest, derive authority from a directory scan, or accept a V8
identity supplied by a caller. If the future authoritative entry is not
exactly version `8` with filename
`0008_tenant_command_runtime_bundle_selection.sql`, the V8 transition and
stable-V8 postures are unavailable.

## 4. Trust model and authority map

### 4.1 Protected assets

The protected assets are the exact controller routine ACL, the distinction
between stable and uncommitted database states, migration-source identity,
migration-ledger truth, locked transaction ordering, provisioning-verifier
meaning, the production-versus-legacy firewall, and the still-closed
production temporal semantic surface.

### 4.2 Trusted components

The trusted components are PostgreSQL 17; the exact authorities in section 3;
the literal `TENANT_AUTHORITATIVE_MIGRATION_SET`; the production
`migrate_service` entry after its existing complete authoritative-set
authentication; the reviewed locked migration runner; the provisioning
verifier; and the architecture Python-source snapshot and ordinary repository
review gates.

The test-only migration executor may construct synthetic migration histories
only to verify mechanics. It is not a production authority and cannot make a
synthetic source authoritative.

### 4.3 Untrusted actors and inputs

Untrusted inputs include every caller argument, DSN, release identity,
execution UUID, target catalog observation, routine-existence observation,
ACL observation, ledger row before authentication, environment value,
filesystem directory order, application or worker request, tenant or
principal value, RuntimeBundle digest, route input, and managed database role.

### 4.4 Authority map

| Decision | Sole authority |
| --- | --- |
| Whether migration 0008 is part of the production release | Literal `TENANT_AUTHORITATIVE_MIGRATION_SET`, changed only by the separate database Phase B |
| Exact V8 source digest, byte length, filename, prefix digest, and order | The exact eighth `AuthoritativeMigration` row in that binding |
| Whether the production migration set matches that binding | Existing `require_authoritative_migration_set` before `migrate_service` execution |
| Stable V7 or V8 classification | Provisioning verifier from the exact ledger fields and authoritative binding |
| Entry into the V8 post-source posture | Reviewed runner control flow after execution of the authenticated eighth source in the already locked transaction |
| Exact permitted third ACL row | This contract and the parent contract's migration-0008 function/grant design |
| Issuance of the third grant | Migration 0008 only; outside this verifier PR |
| Ledger append | Existing migration runner only, after post-source verification |
| Activation-function structure and selection storage | Parent database contract, migration-0008 structural verifier, and later database PR |
| Runtime selection, command integration, reads, routes, outputs, and deployment | Later reviewed boundaries only |
| Legacy behavior and #192 | Their existing separate authorities; unchanged |

The provisioning verifier observes and refuses. It does not own migration
source, issue privileges, repair state, or convert an observation into
authority.

## 5. Exact ACL family

The inspected grantee family remains closed to:

```text
ofarm_command_runtime_bundle_selection_controller
ofarm_command_runtime_bundle_selection_control_login
```

At stable V7 the complete expected non-owner ACL rows in schema `ofarm` for
that family are exactly:

| Routine | Identity arguments | Grantee | Grantor | Privilege | Grantable |
| --- | --- | --- | --- | --- | --- |
| `create_tenant_challenge` | empty | `ofarm_command_runtime_bundle_selection_controller` | `ofarm_binder` | `EXECUTE` | false |
| `bind_tenant_capability` | `text` | `ofarm_command_runtime_bundle_selection_controller` | `ofarm_binder` | `EXECUTE` | false |

The V8 post-source posture and stable V8 add exactly:

| Routine | Identity arguments | Grantee | Grantor | Privilege | Grantable |
| --- | --- | --- | --- | --- | --- |
| `activate_commit_operation_claim_draft_runtime_bundle_selection` | `text` | `ofarm_command_runtime_bundle_selection_controller` | `ofarm_owner` | `EXECUTE` | false |

No row is granted to the login directly. No grant option is accepted. No
alternate overload, schema, owner, grantor, grantee, or privilege is accepted.
Owner-default ACL rows outside the existing query's grantee family are not
reclassified by this contract; the migration-0008 structural verifier remains
responsible for the activation function's complete structure and ACL.

## 6. Closed state model

### 6.1 Stable V7

Stable V7 requires the existing exact V7 ledger phase and exactly the two ACL
rows in section 5. The general provisioning verifier and the ordinary
`migration_locked_differences` entry use only stable-state classification.

The presence of the activation routine or the third ACL while the durable
ledger remains at V7 is drift and must fail every ordinary verification path.

### 6.2 Authenticated V8 source transition

The special post-source posture is available only when all of these facts are
true in reviewed runner control flow:

1. execution entered through production `migrate_service`, whose existing
   preflight authenticated the complete set against
   `TENANT_AUTHORITATIVE_MIGRATION_SET`;
2. the service is the fixed tenant migration service;
3. the observed authenticated durable history is exact stable V7;
4. the next migration is the exact eighth member of that same authenticated
   set;
5. that member is version `8` and has the exact filename in section 3;
6. the runner executed the already retained, preflight-authenticated source
   bytes inside the same permanent-lock transaction;
7. the connection remains in the expected transaction; and
8. the check occurs before any V8 ledger append.

The runner may then invoke one narrowly named private verifier seam for this
post-source posture. The seam accepts no source identity, row identity,
filename, digest, role, routine, grantee, grantor, or allow/deny flag from a
caller. It independently requires the fixed tenant specification, exact V7
durable phase, and availability of the exact eighth authoritative binding
entry. Its only semantic difference from ordinary locked verification is the
one third ACL row in section 5.

The existing public `migration_locked_differences(target, spec)` signature and
meaning stay closed and unchanged. It always performs stable-state
verification. The new private seam is not exported through
`deployment.postgresql.__init__` and is not a generic transition registry.

Any rollback removes the source effects and returns to stable V7. A backend
loss, exception, or refusal before commit cannot leave the transition posture
as a lawful durable state.

### 6.3 Stable V8

After the runner appends V8 and commits, ordinary verification may classify
stable V8 only when:

- the ledger remains gap-free with count, minimum, and maximum exactly
  consistent through version 8;
- the existing V5, V6, and V7 filename and service fields remain exact;
- the V8 ledger row's version, filename, source SHA-256, source byte length,
  applied-prefix digest, service identity, and provisioning-spec digest match
  the exact active eighth authoritative migration and fixed tenant
  provisioning specification; and
- the complete controller/login ACL observation equals the three rows in
  section 5.

An exact V8 ledger row with only two grants is drift. Three grants with no
exact V8 ledger row are drift. A V8 row cannot be authenticated by its
filename alone.

Later V9 or another grant family is unsupported. It requires its own reviewed
contract rather than being inferred by this implementation.

## 7. Implementation architecture

The smallest coherent implementation has four parts:

1. Extend the private durable admission-phase classifier in
   `provisioning.py` to recognize exact stable V8 from the literal
   authoritative migration binding and exact ledger evidence.
2. Keep the ordinary verifier path strict, and add one private post-source V8
   verifier seam whose sole delta is the third ACL row.
3. In `migration_runner.py`, select that seam only for the exact authenticated
   tenant migration-0008 transition described in section 6.2; every pre-source
   check, every other migration, the next-loop stable check, and all ordinary
   provisioning verification continue through the stable verifier.
4. Add focused unit and disposable PostgreSQL tests proving stable, transition,
   final, rollback, and refusal behavior.

The implementation must not introduce a general transition enum exposed to
callers, a caller-set boolean, a registry, a plugin, a database marker, a GUC,
a temporary table, a new role, a new credential, or an alternate migration
entry point. Code size is a warning signal: if this design cannot remain a
small classifier and one runner branch, work stops for review.

## 8. Invariants

- **PSVA-001 — Stable verification stays strict.** Ordinary provisioning and
  `migration_locked_differences` accept the third ACL only with exact stable
  V8 ledger evidence.
- **PSVA-002 — Binding artifact owns identity.** The V8 source contract,
  position, filename, digest, length, and prefix identity come only from the
  literal reviewed `TENANT_AUTHORITATIVE_MIGRATION_SET`, never caller data or
  observed database shape.
- **PSVA-003 — One transition delta.** The post-source verifier differs from
  stable V7 only by the exact third ACL tuple in section 5.
- **PSVA-004 — Runner-owned ordering.** Only reviewed migration-runner control
  flow may enter the post-source posture, after exact source execution and
  before ledger append in the same locked transaction.
- **PSVA-005 — No inference from effects.** Routine existence, matching ACL,
  ledger filename alone, a database marker, or a caller assertion never selects
  the transition or authenticates V8.
- **PSVA-006 — Exact ACL closure.** Missing, additional, grantable, direct-login,
  PUBLIC, wrong-schema, wrong-overload, wrong-grantor, wrong-grantee, or
  wrong-privilege rows fail closed.
- **PSVA-007 — No mutation or repair.** Every verifier in this boundary is
  observational. It never grants, revokes, creates, drops, appends, repairs, or
  reconciles.
- **PSVA-008 — Rollback closure.** A refused or interrupted V8 attempt retains
  no lawful third grant and no V8 ledger row.
- **PSVA-009 — Parent storage authority unchanged.** Migration 0008 remains the
  sole issuer of the third grant and owner of activation-function structure;
  this PR does not edit it or its adapter.
- **PSVA-010 — Closed semantic surface.** No runtime selection, governed-command
  integration, current/default claim, route, read, output, deployment, legacy,
  or #192 behavior becomes reachable.
- **PSVA-011 — Source snapshot remains one-pass.** Architecture verification
  continues to obtain its Python source snapshot through the accepted public
  snapshot authority; this boundary adds no filesystem read or alternate
  snapshot path.
- **PSVA-012 — One trust boundary.** The PR changes only verifier recognition
  and the runner seam needed to order it. Any grant, migration, storage,
  catalog-finalizer, runtime, output, or deployment change stops.

## 9. Required negative cases

The implementation must refuse or stop when:

- the active authoritative set has no eighth row, more than eight rows, a
  non-tenant service, a different V8 position, filename, source digest, byte
  length, or prefix digest;
- stable V7 contains the third ACL during ordinary provisioning or ordinary
  locked verification;
- the special seam is attempted before source execution, after ledger append,
  outside the locked transaction, from another migration, or for another
  service;
- V8 ledger evidence is missing, partial, duplicated, non-gap-free, filename-
  only, or inconsistent with the exact authoritative row or provisioning spec;
- any of the three required ACL rows is missing;
- the activation grant is grantable, granted by a role other than
  `ofarm_owner`, granted to the login or PUBLIC, uses another schema or
  overload, or is accompanied by any fourth family row;
- an exception or simulated backend loss leaves a committed V8 row or third
  grant;
- a caller, environment value, target observation, function-existence check,
  or database marker can select the transition posture;
- the existing public verifier signature or package export surface changes;
- a changed file is outside section 10; or
- implementation requires editing the parent contract, migration 0008,
  `migration_sets.py`, `catalog_identity.py`, provisioning specs, a candidate
  artifact, active temporal checker, RuntimeBundle/profile authority, runtime,
  route, output, legacy code, or #192.

## 10. Smallest coherent implementation and exact path allowlist

Before approval, the PR may contain only the RFC path in this table. After one
valid approval under section 13, implementation remains limited to all six
paths:

| Exact path | Permitted reason |
| --- | --- |
| `docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_Provisioning_Verifier_Admission_RFC_v0_1.md` | This contract and compact approval evidence required by the active pre-deployment workflow. |
| `deployment/postgresql/provisioning.py` | Exact stable-V8 phase recognition, exact third-row expectation, and the private post-source verifier seam. |
| `deployment/postgresql/migration_runner.py` | Select the private seam only at the authenticated V8 post-source/pre-ledger point. |
| `kernel/tests/test_postgresql_provisioning.py` | Focused stable, transitional, final, ACL-closure, and rollback verification on disposable PostgreSQL targets. |
| `kernel/tests/test_postgresql_migration_runner.py` | Focused runner-order, authoritative-identity, refusal, and transaction tests. |
| `conformance/review_baseline_test_inventory.json` | Mechanical regeneration only when the canonical collected test-node inventory changes, including a count or node-ID change. |

No path prefix, generated wildcard, or “related file” is implied. The
implementation may import and read the existing literal migration authority;
it may not edit `deployment/postgresql/migration_sets.py`. The existing
architecture snapshot checker observes changed Python through its accepted
one-pass public source snapshot and needs no authority change.

If a required test cannot be expressed in the two allowed test modules, or a
review fix requires another production or conformance authority, work stops
and proposes a separate boundary. The allowlist is not widened merely to clear
a check or review comment.

## 11. Verification

### 11.1 Phase A verification

Before the decision card, Phase A must prove:

- the exact authorities and baseline blobs in section 3;
- only this RFC differs from the reviewed base;
- internal consistency of the ACL family, state model, authority map,
  invariants, negative cases, allowlist, and stop conditions;
- `python3 conformance/ofarm_pkg_contract_check.py` passes; and
- the draft PR has received one full technical review at its exact head, with
  no unresolved Blocker before the card is presented.

Phase A performs no PostgreSQL mutation and does not use the paused database
worktree as implementation input.

### 11.2 Later verifier implementation verification

After approval, the verifier PR must prove:

- the ordinary public verifier signature and package export surface are
  unchanged;
- no production call site can select the special seam except the one exact
  runner branch;
- V7 with two rows passes ordinary verification;
- V7 with the third row fails ordinary provisioning and ordinary locked
  verification;
- the exact test-only representation of the authenticated V8 post-source state
  passes the private seam with exactly three rows;
- missing, extra, wrong-grantor, wrong-grantee, direct-login, PUBLIC,
  grantable, wrong-overload, and wrong-privilege variants fail;
- exact stable V8 requires both the exact authoritative ledger evidence and
  exactly three rows;
- incomplete or substituted V8 ledger evidence fails;
- another service, migration version, filename, set position, or unauthenticated
  set cannot select the transition;
- exception, refusal, and backend-loss paths roll back without a durable V8 row
  or third grant;
- existing V5, V6, and V7 phase tests remain green;
- focused provisioning and migration-runner tests pass against disposable
  PostgreSQL 17 targets;
- architecture, temporal, package, and canonical test-inventory checks pass;
  and
- the exact changed-path set is a subset of section 10 and of the approved
  decision card's maximum path envelope.

No retained database selection or target is permitted.

### 11.3 Later database Phase B integration proof

This verifier PR cannot prove the final production V8 source before the
separate database Phase B lawfully adds it. After this PR merges, the resumed
database Phase B must additionally prove on a destroyed or rolled-back target:

```text
exact stable V7
  -> authenticated authoritative migration 0008 source
  -> exact post-source verifier passage
  -> exact V8 ledger append and commit
  -> ordinary stable-V8 verifier passage
```

That later proof belongs to the parent's existing database tests and paths. It
does not authorize a verifier edit in the database PR.

## 12. Non-goals and stop conditions

This contract and verifier PR do not authorize:

- migration 0008, its authoritative migration-set row, catalog digest, SQL,
  relation, RLS, allocator branch, activation function, adapter, or grant;
- any database provisioning, migration execution against a retained target,
  existing-target repair, reconciliation, upgrade, or backfill;
- a new role, login, credential, membership, privilege, grant-custody path,
  SECURITY DEFINER function, marker, registry, service, or generic verifier
  extension mechanism;
- amendment of an existing frozen or active contract, candidate artifact,
  RuntimeBundle, ActiveArtifactSet, Capability Manifest, profile, or temporal
  registry;
- runtime temporal selection, current/default selection, a semantic route,
  command integration, materialization, qualification, publication, read,
  historical or WINDOW execution, output, receipt, deployment, or hot reload;
- weakening the production-versus-legacy firewall or importing legacy
  behavior; or
- any #192 behavior.

Work stops before any such effect, before any path outside section 10, or if
the transition cannot be proven without caller-chosen posture. A cross-boundary
review finding is recorded as a prerequisite or follow-up, not appended to this
PR.

## 13. Approval and next sequence

This proposal is not approved by authorship, a commit, a PR, a review, a
GitHub credential, mergeability, CI, or the user's earlier authorization of
the parent database Phase B. The verifier boundary is a new decision.

The active pre-deployment workflow requires one complete plain-English card in
the designated Codex task naming one already-created draft PR. A later
user-authored message in that task must be exactly:

```text
I approve OFARM2 decision ISSUE176-SELECTION-PROVISIONING-VERIFIER-001 version 1.
```

Before that message, the named PR may contain only this RFC and no behavior
change. After valid approval, the same PR may implement, verify, address
in-envelope review Blockers, and merge only within the approved card and
section 10. Any material change to the trust boundary, authority map,
permitted effect, non-effect, invariant, or path envelope requires a new card
version and approval.

The required sequence is:

```text
PHASE_A_RFC_IN_DRAFT_PR
  -> FULL_EXACT_HEAD_TECHNICAL_REVIEW
  -> COMPLETE_LIVE_DECISION_CARD
  -> EXACT_LATER_USER_APPROVAL
  -> VERIFIER_IMPLEMENTATION_IN_THE_SAME_PR
  -> VERIFICATION_AND_REVIEW_GATES
  -> VERIFIER_PR_MERGE
  -> REBASE_PAUSED_DATABASE_PHASE_B_ON_MERGED_VERIFIER
  -> RESUME_ONLY_THE_PARENT_NINE_PATH_DATABASE_BOUNDARY
```

The verifier PR stops after merge. It does not itself resume or merge the
paused database work.
