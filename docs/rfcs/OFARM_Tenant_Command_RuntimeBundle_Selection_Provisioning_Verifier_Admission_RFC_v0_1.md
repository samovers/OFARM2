# OFARM2 Tenant Command RuntimeBundle Selection Provisioning-Verifier Admission — Phase A Contract v0.1

**Status:** architect-approved for Phase B implementation only in PR #290;
no provisioning, migration, grant, database, runtime, route, output,
deployment, legacy, or #192 effect follows from this record alone

**Contract identity:**
`ofarm.tenant-command-runtime-bundle-selection-provisioning-verifier-admission.issue176.v0.1`

**Decision identity:**
`ISSUE176-SELECTION-PROVISIONING-VERIFIER-001`, version `2`

**Withdrawn card:** version `1` was displayed but not approved. Exact-head
review `4873828149` found an incomplete composition with the accepted V5–V7
phase authority and a premature V8 integration-proof requirement. Version `1`
is withdrawn, creates no implementation or merge authority, and cannot be
approved or reused.

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

This contract admits one separate, narrow verifier change. It preserves the
accepted durable V5–V7 admission phases `A0`, `A1`, `A2`, and `A4` and composes
them with one subordinate selection-controller ACL substate:

```text
existing admission phase: A0 | A1 | A2 | A4

selection-controller ACL substate:
NOT_APPLICABLE | STABLE_V7 | V8_POST_SOURCE_PRE_LEDGER_APPEND | STABLE_V8
```

`AUTHENTICATED_V8_SOURCE_EXECUTING` is a runner event between observations, not
a verifier state. `STABLE_V7` continues to require exactly the existing two
binder-owned selection-control grants. `V8_POST_SOURCE_PRE_LEDGER_APPEND` is a
transaction-local runner posture that permits exactly the activation-routine
identity and its one additional owner-owned controller grant after the exact
authoritative migration 0008 source executes and before the runner appends its
ledger row. `STABLE_V8` requires that same exact routine identity and third
grant plus an exact authenticated V8 ledger row.

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

## 3. Fixed governing authorities and reviewed baselines

| Authority | Exact reviewed identity |
| --- | --- |
| Architecture | `reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md`; 96,406 bytes; `sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256` |
| Migration and provisioning law | `docs/adr/0001-tenancy-and-schema-migrations.md`; 147,112 bytes; `sha256:bc49e566ddbdf98868162aa7ccca0940fa76fca1bfaaa261c8c831dbb5515a4d` |
| Temporal separation | `docs/adr/0002-valid-time-and-knowledge-time.md`; 61,427 bytes; `sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796` |
| TenantBinding authority | `docs/adr/0003-tenant-capability-trust-and-binder.md`; 93,419 bytes; `sha256:b188f4d60e46887fde4231e73bb00adb9bd70b75e807627e8a3906389a0fa5be` |
| Parent selection-activation contract | Exact path, identity, byte length, and digest in section 2 |
| V5 selection-control admission | `docs/rfcs/OFARM_Tenant_Binding_Selection_Control_Admission_RFC_v0_1.md`; `ofarm.tenant-binding-selection-control-admission.issue176.v0.1`; 32,169 bytes; `sha256:c1d02969811be0d5b02bdae158cb48e5d8148356ca9d4bac956c8861d529c37a` |
| V6 current-context owner admission | `docs/rfcs/OFARM_Tenant_Current_Context_Selection_Owner_Admission_RFC_v0_1.md`; `ofarm.tenant-current-context-selection-owner-admission.issue176.v0.1`; 50,383 bytes; `sha256:af85e259230b69edeba80ddc2eea2f070a601fd3888fd463ce595f9cc446b13d` |
| V7 write-lock owner admission | `docs/rfcs/OFARM_Tenant_Write_Lock_Selection_Owner_Admission_RFC_v0_1.md`; `ofarm.tenant-write-lock-selection-owner-admission.issue176.v0.1`; 45,758 bytes; `sha256:5745ad4b8b588be2b5a1b64b4b84aa757b23f8d2de00ca59e71de8ea304f51b0` |
| Current tenant migration authority | `deployment/postgresql/migration_sets.py::TENANT_AUTHORITATIVE_MIGRATION_SET`; exact reviewed seven-migration digest `sha256:5616797d1362c55c78175126edab29cc3e88c021ba0709e3766d3196d2b0126b` |
| Provisioning verifier starting baseline | `deployment/postgresql/provisioning.py`; reviewed Git blob `efd78f52b2b152fe67ee7c454feba3edbaff0160`; authenticated before applying this contract, not a required post-implementation source identity |
| Migration runner starting baseline | `deployment/postgresql/migration_runner.py`; reviewed Git blob `cbf5e956733e39b16e20652d6b89541dd5b58c57`; authenticated before applying this contract, not a required post-implementation source identity |
| Migration-set starting baseline | `deployment/postgresql/migration_sets.py`; reviewed Git blob `c14919d8b94c0ad9ac9ca2b51f1692135d554cfb`; authenticated before applying this contract and unchanged by this PR |
| Active pre-deployment workflow | `docs/rfcs/OFARM2_Predeployment_AI_Assisted_Development_Workflow_RFC_v0_1.md` and the active merged rules in `AGENTS.md` and `TASK_PROMPT.md` |

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

The complete V5, V6, and V7 child-contract identities above remain controlling
for their capsules, grants, transaction ordering, and `A0`–`A4` meanings.
This contract does not add `A5`, replace `_TenantBindingAdmissionPhase`, or
reinterpret an earlier phase. The V7 contract owns only the exact existing
`ofarm_owner` lock-wrapper execution edge and expressly does not own migration
0008, its activation function, or this additional verifier recognition.

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

## 5. Exact ACL observation and permitted family

The repository's existing mechanical boundary defines a non-system routine as
a `pg_catalog.pg_proc` row whose OID is greater than or equal to
`_POSTGRESQL_FIRST_NORMAL_OBJECT_ID`, whose fixed value is `16384`. Prose such
as “user routine” or namespace membership cannot replace that OID comparison.

The verifier performs three closed target-database observations.

### 5.1 Controller, login, and `PUBLIC` family

The first observation includes:

- every explicit routine ACL row across every schema and overload whose
  grantee is the controller, the control login, or `PUBLIC`; and
- every effective default-`PUBLIC` routine ACL row for a non-system routine
  whose explicit ACL is null.

The permitted named-grantee family remains closed to:

```text
ofarm_command_runtime_bundle_selection_controller
ofarm_command_runtime_bundle_selection_control_login
```

The observation compares schema, routine name, identity arguments, grantee,
grantor, privilege, and grantability. It does not infer identity from a
function name alone. `PUBLIC` is represented explicitly as grantee OID `0`,
not by joining through `pg_catalog.pg_roles`; a roles join cannot define or
filter this observation. System-default `PUBLIC` execution inherited from the
unchanged PostgreSQL catalog is outside this new user-routine family scan;
explicit changes to system routine ACLs remain covered by the existing global
provisioning checks.

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

No family row is granted to the login or `PUBLIC`. No grant option is accepted.
No alternate overload, schema, grantor, grantee, or privilege is accepted.

### 5.2 Exact activation-routine inventory

The second observation inventories every routine with the exact name
`activate_commit_operation_claim_draft_runtime_bundle_selection` across every
schema and overload. It compares schema, routine name, and PostgreSQL identity
arguments.

| ACL substate | Complete permitted inventory for that routine name |
| --- | --- |
| `NOT_APPLICABLE` or `STABLE_V7` | Empty. No routine with that name may exist in any schema or overload. |
| `V8_POST_SOURCE_PRE_LEDGER_APPEND` | Exactly `ofarm.activate_commit_operation_claim_draft_runtime_bundle_selection(text)`. |
| `STABLE_V8` | Exactly `ofarm.activate_commit_operation_claim_draft_runtime_bundle_selection(text)`. |

An owner-only activation routine at V7 therefore fails even when the family
ACL scan observes no forbidden grantee. A same-named routine in another schema
or another overload is an additional inventory row and fails.

### 5.3 Every non-owner ACL row on the exact activation routine

When the exact activation routine is present, the third observation explodes
its effective ACL and retains every row whose grantee is not the routine owner,
regardless of grantee identity. `PUBLIC` is represented explicitly rather than
joined through `pg_catalog.pg_roles`.

| ACL substate | Complete permitted non-owner ACL rows |
| --- | --- |
| `NOT_APPLICABLE` or `STABLE_V7` | Empty because the routine must be absent. |
| `V8_POST_SOURCE_PRE_LEDGER_APPEND` | Exactly controller / `ofarm_owner` / `EXECUTE` / not grantable. |
| `STABLE_V8` | Exactly controller / `ofarm_owner` / `EXECUTE` / not grantable. |

This observation rejects an arbitrary managed or unmanaged grantee, the
control login, `PUBLIC`, a wrong grantor, wrong privilege, grant option, or an
additional fourth row. The routine owner's own ACL row is excluded here and
remains under the migration-0008 structural verifier, together with the
function body, owner identity, language, security, configuration, RLS, and
complete structural contract.

## 6. Closed composition and state model

### 6.1 Composition with `A0`–`A4`

The accepted `_TenantBindingAdmissionPhase` values remain exactly `A0`, `A1`,
`A2`, and `A4`. They remain the sole authority for V5 selection grants, V6
current-context grants, V7 write-lock grants, and all three capsule-presence
rules. This contract adds no durable admission phase.

The selection-controller ACL substate composes as follows:

| Existing phase and ledger evidence | ACL substate | Complete section-5 expectation |
| --- | --- | --- |
| `A0` | `NOT_APPLICABLE` | Existing A0 behavior; no V5 selection-control grants; empty activation-routine inventory; no activation-routine non-owner ACL row. |
| `A1` or `A2` | `NOT_APPLICABLE` | Existing phase behavior; exactly the two V5 binder grants; empty activation-routine inventory; no activation-routine non-owner ACL row. |
| `A4` with exact durable head 7 | `STABLE_V7` | Exactly the two V5 binder grants; empty activation-routine inventory; no activation-routine non-owner ACL row. |
| `A4` with exact head 7 plus the runner-authenticated post-source event in section 6.3 | `V8_POST_SOURCE_PRE_LEDGER_APPEND` | Exactly the two V5 binder grants; exactly the activation-routine identity in section 5.2; exactly the controller non-owner ACL row in section 5.3. |
| `A4` projection with exact authenticated durable head 8 | `STABLE_V8` | Exactly the two V5 binder grants; exactly the activation-routine identity in section 5.2; exactly the controller non-owner ACL row in section 5.3. |

For exact durable head 8, the existing phase classifier must authenticate the
V8 ledger evidence and return the existing `A4` capsule-and-grant projection.
The subordinate ACL classifier returns `STABLE_V8` from that same exact
evidence. One private ledger-classification operation returns the composed
`(existing phase, ACL substate)` result; two independently authoritative
classifiers are forbidden. Existing capsule and grant checks consume only the
phase projection from that result. Any incomplete or contradictory
classification is one provisioning difference and fails the target.

### 6.2 Stable V7

Stable V7 requires the existing exact V7 ledger phase, exactly the two family
ACL rows in section 5.1, and an empty activation-routine inventory under
section 5.2. The general provisioning verifier and the ordinary
`migration_locked_differences` entry use only stable-state classification.

The presence of the activation routine or the third ACL while the durable
ledger remains at V7 is drift and must fail every ordinary verification path.

### 6.3 Authenticated V8 source transition

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

Execution of the source statement is a runner event. No verifier observation
occurs while PostgreSQL is executing that statement. After it returns and the
connection is still `INTRANS`, the runner may invoke one narrowly named private
verifier seam for this post-source posture. The seam accepts no source
identity, row identity,
filename, digest, role, routine, grantee, grantor, or allow/deny flag from a
caller. It independently requires the fixed tenant specification, exact V7
durable phase, and availability of the exact eighth authoritative binding
entry. Its only semantic difference from ordinary locked verification is the
exact activation-routine inventory row and the one third ACL row in section 5.

The existing public `migration_locked_differences(target, spec)` signature and
meaning stay closed and unchanged. It always performs stable-state
verification. The new private seam is not exported through
`deployment.postgresql.__init__` and is not a generic transition registry.

If the private seam reports any difference, the runner must raise a governed
migration refusal. A returned difference or governed verifier refusal must
make the existing outer runner boundary roll back the same transaction before
any V8 ledger append. The runner must never continue to ledger append, commit,
or stable-V8 recognition from a refused seam result.

Any rollback must remove the source effects and return to stable V7. A backend
loss, exception, or refusal before commit cannot make the transition posture a
lawful durable state. The real migration-0008 rollback and uncertain-outcome
proof belongs to the later database Phase B under section 11.3.

### 6.4 Stable V8

After the runner appends V8 and commits, ordinary verification may classify
stable V8 only when:

- the ledger remains gap-free with count, minimum, and maximum exactly
  consistent through version 8;
- the existing V5, V6, and V7 filename and service fields remain exact;
- the V8 ledger row's version, filename, source SHA-256, source byte length,
  applied-prefix digest, service identity, and provisioning-spec digest match
  the exact active eighth authoritative migration and fixed tenant
  provisioning specification; and
- all three section-5 observations equal the stable-V8 routine inventory and
  ACL expectations.

An exact V8 ledger row with only two grants is drift. Three grants with no
exact V8 ledger row are drift. A V8 row cannot be authenticated by its
filename alone.

Later V9 or another grant family is unsupported. It requires its own reviewed
contract rather than being inferred by this implementation.

## 7. Implementation architecture

The smallest coherent implementation has four parts:

1. Preserve the exact `A0`/`A1`/`A2`/`A4` phase vocabulary. Extend its private
   ledger classification only to return the existing `A4` projection for exact
   stable V8, and derive the subordinate ACL substate in section 6 from the
   same authenticated evidence.
2. Keep the ordinary verifier path strict. Implement the three exact section-5
   observations, including same-name routine inventory across schemas and
   overloads and every non-owner ACL row on the exact activation routine. Add
   one private post-source V8 verifier seam whose sole permitted delta is the
   exact activation identity and its one controller ACL row.
3. In `migration_runner.py`, select that seam only for the exact authenticated
   tenant migration-0008 transition described in section 6.3. Immediately
   before the production-only branch, repeat complete
   `require_authoritative_migration_set(migration_set)` authentication. A
   version, filename, source object, or earlier shared-executor argument cannot
   substitute for that repeated authentication. Every pre-source check, every
   other migration, the next-loop stable check, and all ordinary provisioning
   verification continue through the stable verifier.
4. Add focused unit, source-structure, and disposable PostgreSQL tests proving
   the classifications, exact ACL observation, private-seam behavior,
   authoritative-binding refusal, and production/test entry-point separation
   available before migration 0008 exists.

The implementation must not introduce a caller-controlled transition mode of
any kind, including a Boolean, enum, callback, singleton token, capability bag,
registry, plugin, database marker, GUC, or temporary table. It must not add a
new role, credential, or alternate public migration entry point. Code size is
a warning signal: if this design cannot remain a small composition and one
runner branch, work stops for review.

## 8. Invariants

- **PSVA-001 — Stable verification stays strict.** Ordinary provisioning and
  `migration_locked_differences` accept the third ACL only with exact stable
  V8 ledger evidence.
- **PSVA-002 — Binding artifact owns identity.** The V8 source contract,
  position, filename, digest, length, and prefix identity come only from the
  literal reviewed `TENANT_AUTHORITATIVE_MIGRATION_SET`, never caller data or
  observed database shape.
- **PSVA-003 — One closed transition delta.** The post-source verifier differs
  from stable V7 only by the exact activation-routine inventory identity and
  exact third ACL tuple in section 5.
- **PSVA-003A — Existing phase law controls.** `A0`, `A1`, `A2`, and `A4`
  retain every accepted V5–V7 meaning; V8 is an `A4` projection plus a
  subordinate selection-controller ACL substate, never `A5` or a replacement
  phase family.
- **PSVA-004 — Runner-owned ordering.** Only reviewed migration-runner control
  flow may enter the post-source posture, after exact source execution and
  before ledger append in the same locked transaction.
- **PSVA-005 — No inference from effects.** Routine existence, matching ACL,
  ledger filename alone, a database marker, or a caller assertion never selects
  the transition or authenticates V8.
- **PSVA-006 — Exact ACL closure.** Missing, additional, grantable, direct-login,
  PUBLIC, wrong-schema, wrong-overload, wrong-grantor, wrong-grantee, or
  wrong-privilege rows fail closed.
- **PSVA-006A — Exact routine existence.** `NOT_APPLICABLE` and `STABLE_V7`
  require the activation routine name to be absent across every schema and
  overload. Transition and stable V8 require exactly the one identity in
  section 5.2.
- **PSVA-006B — Arbitrary grantees remain visible.** Every non-owner ACL row on
  the exact activation routine is observed regardless of grantee and must equal
  the one row in section 5.3.
- **PSVA-007 — No mutation or repair.** Every verifier in this boundary is
  observational. It never grants, revokes, creates, drops, appends, repairs, or
  reconciles.
- **PSVA-008 — Rollback closure.** In the completed database composition, a
  refused or interrupted V8 attempt retains no lawful third grant and no V8
  ledger row; the real source and transaction proof is deferred to section
  11.3.
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
- stable V7 contains an owner-only activation routine or an activation routine
  granted to `ofarm_app` or any other non-owner role;
- the activation routine name exists in another schema or with another
  overload in any substate;
- any `A0`, `A1`, or `A2` target is reclassified as a new V8 phase, or exact
  durable head 8 is accepted without both the existing `A4` projection and
  `STABLE_V8` substate;
- the special seam is attempted before source execution, after ledger append,
  outside the locked transaction, from another migration, or for another
  service;
- V8 ledger evidence is missing, partial, duplicated, non-gap-free, filename-
  only, or inconsistent with the exact authoritative row or provisioning spec;
- any of the three required ACL rows is missing;
- the activation grant is grantable, granted by a role other than
  `ofarm_owner`, granted to the login or PUBLIC, uses another schema or
  overload, or is accompanied by any fourth family row;
- stable V8 or the transition contains an arbitrary fourth non-owner grantee on
  the exact activation routine;
- an explicit controller, control-login, or `PUBLIC` routine ACL row in another
  schema or overload escapes the exhaustive observation;
- a same-named activation routine or a non-owner activation-routine ACL row
  escapes the exact inventory or arbitrary-grantee observation;
- an exception or simulated backend loss leaves a committed V8 row or third
  grant;
- a caller, environment value, target observation, function-existence check,
  or database marker can select the transition posture;
- `_migrate_service_for_testing()` or a synthetic migration set can enter the
  production-only branch;
- the production-only branch does not repeat complete authoritative-set
  authentication immediately before selecting the private seam;
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
| `deployment/postgresql/provisioning.py` | Composed stable-V7/stable-V8 ledger and ACL-substate classification; all three exact section-5 observations; exact third-row expectation; and the private post-source verifier seam. |
| `deployment/postgresql/migration_runner.py` | Select the private seam only at the authenticated V8 post-source/pre-ledger point. |
| `kernel/tests/test_postgresql_provisioning.py` | Focused phase composition, stable/controlled-transition/final classification, exact routine inventory, arbitrary non-owner ACL closure, and refusal verification on disposable PostgreSQL targets. |
| `kernel/tests/test_postgresql_migration_runner.py` | Focused runner ordering, repeated authoritative authentication, production/test entry separation, source-structure, and refusal tests. |
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
- `A0`, `A1`, `A2`, and `A4` remain the complete existing phase vocabulary and
  retain their accepted V5–V7 capsule and grant meanings;
- exact stable V8 composes as the existing `A4` projection plus `STABLE_V8`,
  with no `A5` and no contradictory classifier result;
- no production call site can select the special seam except the one exact
  runner branch;
- V7 with two rows passes ordinary verification;
- V7 with the third row fails ordinary provisioning and ordinary locked
  verification;
- controlled protocol/database evidence proves the stable-V8 ledger
  classification without claiming a real production migration-0008 run;
- the private seam accepts exactly the V8 post-source ACL shape when exercised
  directly under controlled test evidence;
- missing, extra, wrong-grantor, wrong-grantee, direct-login, PUBLIC,
  grantable, wrong-overload, and wrong-privilege variants fail;
- the exhaustive explicit controller/control-login/`PUBLIC` scan covers every
  schema and overload, and effective default `PUBLIC` execution on a
  non-system routine cannot escape it;
- the non-system routine boundary is the exact existing OID threshold `16384`,
  not a caller value, namespace heuristic, or prose-only classification;
- stable V7 refuses an owner-only activation routine and the same routine
  granted only to `ofarm_app`;
- every substate refuses the activation routine name in another schema or with
  another overload;
- transition and stable V8 refuse an arbitrary fourth non-owner grantee on the
  exact activation routine;
- exact routine inventory and every non-owner ACL row are verified independently
  of whether the controller/login/`PUBLIC` family scan observes a row;
- exact stable V8 requires both the exact authoritative ledger evidence and
  exactly three rows;
- incomplete or substituted V8 ledger evidence fails;
- another service, migration version, filename, set position, or unauthenticated
  set cannot select the transition;
- source-structure evidence proves the production branch is after
  `connection.execute(source_text)`, after the `INTRANS` check, and before
  `_insert_ledger_row(...)`;
- source-structure and behavior tests prove the branch repeats
  `require_authoritative_migration_set(migration_set)` and that
  `_migrate_service_for_testing()` and synthetic histories cannot select it;
- no second public migration entry point or caller-controlled transition mode
  exists;
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
  -> real literal eighth authoritative row and retained migration 0008 source
  -> production migrate_service() enters the authenticated branch
  -> exact post-source verifier passage
  -> exact V8 ledger append and commit
  -> ordinary stable-V8 verifier passage
```

That later proof must also cover source refusal, transaction rollback, backend
loss, commit-acknowledgement uncertainty, exact retry/no-op behavior, and final
stable-V8 verification. It belongs to the parent's existing database tests and
paths and does not authorize a verifier edit in the database PR.

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
I approve OFARM2 decision ISSUE176-SELECTION-PROVISIONING-VERIFIER-001 version 2.
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

## Appendix A — Compact approval evidence

This appendix is provisional, AI-attested evidence of the task user's
decision. The user message is the authority; this appendix, repository
credentials, reviews, checks, and merge metadata are not substitutes for it.

- decision: `ISSUE176-SELECTION-PROVISIONING-VERIFIER-001`, version `2`;
- Codex task: `019fa821-93c9-7ef1-8c94-1c0e92ea46b9`;
- complete live card: assistant-authored `item-2829`;
- approval: later user-authored `item-2831`;
- exact approval sentence:
  `I approve OFARM2 decision ISSUE176-SELECTION-PROVISIONING-VERIFIER-001 version 2.`;
- observed ordering: `item-2829` preceded `item-2831` in the same task;
- implementation PR: `https://github.com/samovers/OFARM2/pull/290`; and
- limitation: pre-deployment repository-development authority only, to be
  replaced by independently human-controlled and independently verifiable
  approval or signing before deployment.

The earlier fenced message `item-2830` was not the exact visible approval
sentence and supplied no authority. No later cancellation or stop instruction
was present when Phase B began.
