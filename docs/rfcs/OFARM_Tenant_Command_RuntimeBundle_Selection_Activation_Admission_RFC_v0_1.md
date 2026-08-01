# OFARM2 Tenant Command RuntimeBundle Selection Activation Admission — Phase A Contract v0.1

**Status:** proposed Phase A contract; documentation-only, unapproved, and
without storage, custody, activation, selection, runtime, or deployment effect

**Contract identity:**
`ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1`

**Reviewed base:** `0826a0e3572661756bd7a3200f4675ecaa38274c`

**Date:** 2026-08-01

**Primary ticket:** #176

**Governed command:** `COMMIT_OPERATION_CLAIM_DRAFT`

**Primary trust boundary:** one protected, tenant-owned transition from no
command RuntimeBundle selection to one immutable selection, recorded in the
tenant's governed knowledge order

**Intended PR boundary:** this Phase A PR adds only this RFC. It does not amend
an active or frozen artifact and does not implement the transition.

## 1. Decision

After explicit architect approval of this exact contract, durable publication
of this RFC, and the separate conformance prerequisite in section 13, one
later Phase B database PR may implement one closed pre-deployment control
operation:

```text
ABSENT -- exact governed activation --> SEALED
SEALED -- exact retry ----------------> SEALED (no-op)
SEALED -- unequal reuse --------------> REFUSED (no write)
```

The operation is limited to the tenant command-selection binding:

```text
ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1
```

It may create one immutable selection record and its one governed activation
batch in the same transaction. The batch receives one database-allocated
tenant knowledge position. The selected RuntimeBundle must already be sealed
in the same tenant's production RuntimeBundle storage.

The implementation may provide one administrator-invoked control command. It
must not provide a service, route, runtime hook, profile hook, environment
selector, current pointer, or application/worker write path.

No non-disposable selection record is created by approving, merging, testing,
or implementing this mechanism. Phase B may exercise the operation only on a
disposable test target that is rolled back or destroyed. Invoking it for any
other tenant is a later operational act outside Phase A and the Phase B
implementation PR.

## 2. Why this is one boundary

The immutable row, its dedicated write custody, and its governed activation
batch are one protected state transition:

- storage without the closed transition would have no lawful writer;
- a writer without immutable tenant storage would have no durable authority;
- a selection outside the governed batch ledger would have no tenant knowledge
  position; and
- a separately committed batch and row could expose a partial or unaccounted
  selection.

The role, relation, closed function, knowledge-allocation branch, provisioning
declarations, and mechanical structural verification needed to prove this one
transition may therefore travel in one Phase B database PR. Runtime reads,
public refusal mapping, authorization-provider integration, and governed
command integration are independent trust boundaries and may not travel with
it.

## 3. Fixed prerequisite authorities

This contract does not rewrite its prerequisites. It binds their exact current
identities:

- tenant selection RFC:
  `docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_RFC_v0_1.md`;
- tenant selection RFC byte length: `18492`;
- tenant selection RFC SHA-256:
  `sha256:c432ba48bee2b98edd8fa28b6f214db0c41d56f0b141a0d459d8423ae1480192`;
- selection schema path:
  `contracts/candidates/temporal_runtime_bundle_selection/OFARM_TenantCommandRuntimeBundleSelectionBinding_schema_v0_1.json`;
- selection schema file byte length: `17252`;
- selection schema file SHA-256:
  `sha256:56604a52465ffc027382e99dea96f2c9bc1bd2479cbaff30dec6bd39c08e6b3d`;
- selection binding path:
  `contracts/candidates/temporal_runtime_bundle_selection/OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json`;
- selection binding file byte length: `15993`;
- selection binding file SHA-256:
  `sha256:1500ffbbfdf11207a6657848fce12618347f767578e55dc070bb282dc5775aac`;
- selection binding canonical byte length: `13287`;
- selection binding canonical SHA-256:
  `sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f`;
- command binding identity:
  `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1`;
- command binding canonical SHA-256:
  `sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1`;
- tenant knowledge-position migration:
  `kernel/migrations/0003_tenant_knowledge_position.sql`;
- stable knowledge-storage prefix through migration 0003:
  `sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0`;
- current production migration head: version `4`;
- current production migration-set digest:
  `sha256:424577016d637e10d7315465983e7d97c04fb394377d6445a4163490e676cd6d`;
- production RuntimeBundle role-persistence migration:
  `kernel/migrations/0004_temporal_governance_runtime_bundle_role.sql`;
- production RuntimeBundle role-persistence migration SHA-256:
  `sha256:0c51948be7cebf2c1523d472ca44a57e32942bd358124e126ccaf2bad248ecc8`;
- production RuntimeBundle publication function:
  `ofarm.publish_runtime_bundle(uuid,text,jsonb)`; and
- external production catalog-verifier anchor:
  `deployment/postgresql/catalog_identity.py::TENANT_CATALOG_VERIFIER_DIGEST`.

The selection schema and binding remain candidate artifacts. This admission
contract does not edit, promote, register, or place them in an active
RuntimeBundle. A future control implementation may authenticate and consume
only the exact fixed binding above for this one write transition. That limited
use does not make the binding a profile, route, runtime default, or general
production registry member.

If any pinned prerequisite changes before Phase B, implementation stops for a
new review. Later numbered migrations may advance the complete migration-set
digest without changing the stable migration-0003 prerequisite prefix.

## 4. Exact future record

The future production relation is exactly:

```text
ofarm.tenant_command_runtime_bundle_selection
```

Its authority-bearing columns are exactly:

| Column | SQL class | Authority |
| --- | --- | --- |
| `tenant_id` | `uuid` | Tenant chosen by the dedicated control authority; immutable foreign key to `ofarm.tenant_registry`. |
| `selection_binding_id` | closed ASCII identifier | Fixed literal selection-binding identity from this reviewed contract; never caller-selected. |
| `selection_binding_canonical_digest` | SHA-256 identifier | Fixed literal `sha256:56fb...fa03`; never caller-selected. |
| `command_id` | closed ASCII identifier | Fixed literal `COMMIT_OPERATION_CLAIM_DRAFT`. |
| `command_binding_id` | closed ASCII identifier | Fixed literal command-binding identity from this reviewed contract. |
| `command_binding_canonical_digest` | SHA-256 identifier | Fixed literal `sha256:6dad...9da1`; never caller-selected. |
| `runtime_bundle_digest` | SHA-256 identifier | Chosen only by the dedicated selection-control authority after exact local validation; immutable foreign key to a sealed RuntimeBundle for the same tenant. |
| `selection_batch_id` | tenant-local identifier | Database-generated identity of the same-transaction governed activation batch. |
| `selection_knowledge_position` | positive `int8` within the accepted JavaScript-safe bound | Database-allocated knowledge position of that exact activation batch. |

The primary key is:

```text
(tenant_id, selection_binding_id)
```

The relation must have a composite foreign key proving that
`tenant_id`, `selection_batch_id`, `selection_knowledge_position`, and
`runtime_bundle_digest` name the same governed batch. Migration 0005 may add
the matching unique key to `ofarm.governed_write_batch`; it may not weaken or
remove an existing key.

The row has no mutable status, current flag, supersession pointer, deletion
path, effective-time field, wall-clock ordering field, profile reference, or
caller-supplied alias. The existing governed batch `created_at` remains
diagnostic only and does not order selection authority.

The relation uses forced row-level security. It grants no direct `SELECT`,
`INSERT`, `UPDATE`, `DELETE`, or `TRUNCATE` to the application, worker,
publisher, binder, authorizer, registrar, identity controller, readiness role,
or selection-control credential. An immutable-relation trigger refuses every
update, delete, or truncate.

The activation function is `SECURITY DEFINER`, owned by `ofarm_owner`, with a
fixed trusted search path and fully qualified SQL. Two additive owner policies
are permitted only while `SESSION_USER` is the exact selection-control login:

- the selection-relation policy permits owner reads and permits writes only
  when every binding and command field equals the fixed literals in this
  contract; and
- the governed-batch policy permits owner reads needed to find the tenant head
  and permits writes only for the fixed operation, fixed control-principal
  marker, fixed identifier shapes, null caller knowledge position, and a
  same-tenant sealed RuntimeBundle.

The existing application/worker governed-batch policy is unchanged. The new
policies grant no relation privilege to the login or capability and expose no
generic owner function to them.

## 5. Closed activation operation

The only non-owner write API is:

```text
ofarm.activate_commit_operation_claim_draft_runtime_bundle_selection(
    requested_tenant_id uuid,
    requested_runtime_bundle_digest text
)
RETURNS TABLE (
    selection_batch_id text,
    selection_knowledge_position int8,
    runtime_bundle_digest text
)
```

The SQL function accepts no selection-binding identity, command identity,
schema, matrix, row, component list, component identity, knowledge position,
batch identity, request identity, principal identity, timestamp, profile,
route, or source-contract choice.

The function fixes from this reviewed contract:

- the selection-binding identity and canonical digest;
- the command identity, command-binding identity, and canonical digest;
- the governed operation
  `ACTIVATE_COMMAND_RUNTIME_BUNDLE_SELECTION`;
- the control principal marker
  `ofarm_command_runtime_bundle_selection_control_login`;
- the rule that the activation batch's RuntimeBundle digest equals the selected
  RuntimeBundle digest.

The control principal marker records the authenticated PostgreSQL control
identity for this pre-deployment control-plane act. It is not an OFARM Party,
`TenantBinding`, role assignment, authority grant, or caller attribution, and
it cannot be reused by runtime commands. This is one closed non-runtime
exception; the existing application/worker rule that
`authenticated_principal_ref` equals the protected binding's `party_ref`
remains unchanged.

For an absent selection, the function must:

1. require `READ COMMITTED`;
2. require the exact provisioned selection-control session identity;
3. validate the tenant identifier and SHA-256 syntax;
4. verify that the same-tenant RuntimeBundle is already sealed;
5. acquire `SHARE ROW EXCLUSIVE` on
   `ofarm.governed_write_batch` before allocating the batch, so this rare
   pre-deployment control write and all ordinary governed-batch inserts cannot
   race for a tenant knowledge position;
6. recheck absence after acquiring the lock;
7. generate fresh `selection-batch:<uuid>` and
   `selection-request:<uuid>` identifiers inside PostgreSQL;
8. insert one governed activation batch with a null caller-supplied knowledge
   position;
9. let the migration-owned allocator assign exactly the next committed tenant
   position; and
10. insert the exact selection row in the same transaction.

The table lock is held only by the database transaction. The administrator
control command must commit or roll back immediately after the one function
call. A long-lived transaction, caller-selected lock, alternate lock key, raw
advisory-lock grant, or change to the existing tenant-lock owner is forbidden.

For an existing selection, the function must compare every authority-bearing
field and the referenced batch. An exact retry returns the already sealed
selection without inserting a batch or advancing the tenant knowledge head.
Any unequal, partial, corrupt, cross-tenant, or missing-reference state refuses
without a write.

All validation and both inserts are atomic. SQL exceptions are internal
control-plane refusals. This contract adds no `RuntimeProblem` value and no
public mapping.

## 6. Fixed binding validation

Before calling the SQL function, the administrator control command must:

1. load the selection schema and binding only from the literal paths pinned in
   section 3;
2. verify their exact file lengths and SHA-256 values;
3. verify the binding's canonical length and SHA-256;
4. validate the complete binding against its exact schema;
5. build and validate the selected RuntimeBundle with the production
   RuntimeBundle model;
6. prove the exact sixteen-component command-required subset fixed by the
   binding, including role, identity, canonicalization, placement, byte
   length, digest, and each required schema/instance relationship;
7. treat every unrelated bundle component as inert for this command; and
8. pass only the trusted tenant identifier and computed full RuntimeBundle
   digest to SQL.

The binding path, matrix, rows, command identity, component closure, and source
contracts are compiled control authority, not command-line, environment,
request, route, profile, principal, capability, timestamp, or database-row
choices.

The operator may choose only the target tenant and a RuntimeBundle identity
document to validate. Possession of the dedicated control credential is the
pre-deployment operational authority to make that choice. A bypass of the
fixed validation command while using that credential is compromised
selection-control custody and is outside the ordinary-role SQL threat model,
just as bypassing model validation with the RuntimeBundle publisher credential
is compromised publisher custody.

No operational credential, secret, target-tenant choice, selected bundle
instance, or retained selection row is checked into the repository. Bounded
test values may exist only for disposable verification.

## 7. Selection-control custody

Fresh-target provisioning may add exactly:

- `ofarm_command_runtime_bundle_selection_controller`: a `NOLOGIN`,
  `NOINHERIT`, `NOBYPASSRLS`, non-owner capability with no superuser, database
  creation, role creation, replication, application, worker, binder,
  publisher, registrar, identity, authorization, readiness, migrator, or owner
  authority; and
- `ofarm_command_runtime_bundle_selection_control_login`: a separately
  credentialed `LOGIN`, `INHERIT`, `NOBYPASSRLS` identity with connection limit
  one and the standard control-session settings.

The login's sole membership is the controller capability with:

```text
INHERIT TRUE
SET FALSE
ADMIN FALSE
```

The capability receives schema use and execute on only the closed activation
function. It receives no direct relation privilege and no raw advisory-lock,
tenant-binding, RuntimeBundle-publication, general batch-write, or generic
function authority. The function must also require:

```text
SESSION_USER = 'ofarm_command_runtime_bundle_selection_control_login'
```

Credentials remain outside repository fixtures, migrations, logs, and test
snapshots.

OFARM2 is pre-deployment. Version 0.1 permits this role-set evolution only on a
freshly provisioned disposable target. Existing-target role reconciliation,
silent privilege widening, deployment upgrade, backup adoption, and repair are
unsupported. Before any deployment exists, this fresh-target limit must either
remain true or be replaced by a separately reviewed infrastructure-evolution
contract.

## 8. Knowledge-position authority

The existing `ofarm.allocate_tenant_knowledge_position()` trigger remains the
only allocator. Migration 0005 may add one exact branch for the selection
control session. That branch is valid only when:

- the knowledge position arrived null;
- the governed operation is the fixed selection-activation operation;
- the authenticated-principal marker is the fixed control marker;
- batch and request identifiers have the exact database-generated prefixes and
  UUID shapes fixed above;
- the batch RuntimeBundle digest is the selected sealed bundle digest; and
- the closed activation function already holds the required table lock.

The branch computes `max(knowledge_position) + 1` for the selected tenant under
that lock and preserves the existing exhaustion bound. It does not change the
application/worker branch, target-admin genesis rule, tenant-binding rule,
rollback semantics, committed-head meaning, or wall-clock non-authority rule.

A successful activation consumes one tenant knowledge position. A rollback,
refusal, or exact retry consumes none. The stored selection position must later
be less than or equal to the command's `Kbefore`; enforcement of that read-time
condition belongs to the separately reviewed production selector, not this
write boundary.

## 9. Authority map

- The reviewed tenant selection binding owns the fixed source, identities,
  exact sixteen-component subset, state transitions, and caller non-authority.
- This admission contract owns the one permitted production storage and
  control transition for that exact binding.
- Fresh-target PostgreSQL provisioning owns role attributes, login membership,
  connection custody, schema use, and credential separation.
- The dedicated administrator control command owns authentication of the fixed
  binding and local RuntimeBundle closure validation.
- `ofarm.publish_runtime_bundle(uuid,text,jsonb)` remains the sole publisher of
  sealed production RuntimeBundles. Publication does not select one.
- A later catalog/publication boundary must own the exact temporal
  RuntimeBundle composition and any real publication act; this contract owns
  neither.
- The activation function owns fixed-field construction, exact retry, atomic
  batch/row creation, and no-write refusal.
- The two session-gated owner RLS policies own only the row visibility and
  fixed write checks needed by that function; they do not alter the existing
  application/worker policy.
- `ofarm.governed_write_batch` remains the sole committed tenant knowledge
  ledger.
- `ofarm.allocate_tenant_knowledge_position()` remains the sole knowledge
  allocator.
- The selection relation owns the immutable tenant-and-binding to bundle
  association after activation.
- A later read-only production selector will own lookup after trusted tenant
  binding and before command admission.
- A later production authorization provider will own command authorization.
- A later command-integration contract will own use of the selected digest in
  admission, replay, batch provenance, evidence, and result.
- ActiveArtifactSet, Capability Manifest, profiles, routes, materialization,
  reads, and outputs retain their existing closed authorities.
- `kernel/schema.sql`, `kernel/store.py`, and
  `kernel/runtime_bundle_repository.py` remain quarantined legacy-M1
  authorities and are not dependencies.
- #192 retains sole authority over audit-runtime behavior.

## 10. Invariants

- **TCSA-001 — One command and binding.** Version 0.1 admits only the fixed
  selection binding for `COMMIT_OPERATION_CLAIM_DRAFT`.
- **TCSA-002 — Fixed authority.** Binding, matrix, row, source-contract,
  command, and component identities never come from caller data.
- **TCSA-003 — Separate custody.** Selection control is separate from
  publication, binding, application, worker, authorization, registration, and
  identity control.
- **TCSA-004 — One immutable row.** One tenant and binding version has at most
  one sealed selection; change requires a new reviewed binding version.
- **TCSA-005 — Sealed same-tenant bundle.** The selected digest already names a
  sealed RuntimeBundle for the same tenant.
- **TCSA-006 — Exact closure before write.** The fixed sixteen-component subset
  validates before SQL activation; unrelated components remain inert.
- **TCSA-007 — One atomic governed batch.** First activation creates exactly
  one batch and one selection row in the same transaction.
- **TCSA-008 — Database knowledge authority.** The caller never supplies or
  derives the knowledge position; the migration-owned allocator assigns it.
- **TCSA-009 — Concurrency safety.** The closed control write cannot race an
  ordinary governed-batch insert for the same next position.
- **TCSA-010 — Exact retry is inert.** Exact retry creates no row or batch and
  consumes no position.
- **TCSA-011 — Unequal reuse is no-write.** Replacement, update, deletion,
  partial equality, or conflicting reuse refuses atomically.
- **TCSA-012 — No implicit selection.** Publication, existence, newest, sole,
  profile-listed, or loose component rows never create selection state.
- **TCSA-013 — Write only.** This boundary provides no application/worker read
  authority and does not resolve a selection at command time.
- **TCSA-014 — No activation by repository state.** Approval, merge,
  conformance, migration presence, role presence, or function presence creates
  no tenant selection.
- **TCSA-015 — Production/legacy firewall.** No production code imports or
  consults a legacy Store, profile runtime, semantic route, materializer, or
  output module.
- **TCSA-016 — Closed semantic surface.** No route, command, current-state
  read, historical view, WINDOW behavior, or output opens.
- **TCSA-017 — Audit separation.** No #192 event, receipt, attribution, or
  failure behavior is added.
- **TCSA-018 — Pre-deployment limit.** Role evolution is fresh-target only and
  cannot silently reconcile an existing target.
- **TCSA-019 — RLS remains closed.** Forced RLS remains enabled; only the exact
  control session inside the one owner function receives the additive policy
  path, with fixed write checks and no direct table grant.
- **TCSA-020 — No invented Party.** The control marker identifies only the
  authenticated PostgreSQL control session; it never becomes a Party,
  TenantBinding, tenant role, authority grant, or runtime principal.

## 11. Required negative cases

Verification must refuse or prove unsupported:

- missing, altered, substituted, or multiply resolved Phase A authority;
- changed prerequisite length, digest, canonical digest, identity, or path;
- caller-supplied binding, matrix, row, source-contract, command, component,
  batch, request, principal, knowledge-position, timestamp, or profile choice;
- direct selection-relation reads or DML under the application, worker,
  publisher, binder, authorizer, registrar, identity, readiness, or
  selection-control login;
- direct governed-batch insertion by the selection-control roles outside the
  closed activation function;
- execute by any session other than the exact selection-control login;
- extra membership, `SET ROLE`, administration, inheritance widening,
  connection widening, direct table privilege, or raw advisory-lock grant;
- disabled forced RLS, a changed application/worker policy, an owner policy
  usable by another session, widened owner-policy write checks, or another
  owner function executable by the selection-control roles;
- absent, unsealed, malformed, cross-tenant, or digest-mismatched RuntimeBundle;
- missing, substituted, wrong-role, wrong-placement, wrong-canonicalization,
  wrong-length, wrong-digest, or schema-invalid required component;
- an unrelated component influencing selection authority;
- selection inferred from publication, existence, ordering, newest, sole,
  profile, environment, route, request, principal, or capability data;
- supplied or wall-clock-derived knowledge position;
- the control marker treated as a Party, TenantBinding, role assignment,
  authority grant, or reusable runtime principal;
- activation without the required batch lock;
- concurrent application, worker, or control allocation producing duplicate,
  skipped, reused, or externally selected committed positions;
- rollback leaving a batch, selection row, or consumed position;
- exact retry creating a batch or advancing the head;
- unequal retry, replacement, update, delete, or truncate writing anything;
- mismatched row and batch tenant, bundle digest, batch identity, position, or
  governed operation;
- a retained selection row created by migration, fixture, startup, test
  package, profile, application, or worker code;
- runtime or legacy import of the administrator control module;
- an existing target being repaired or silently reconciled to the new roles;
- any public refusal mapping, runtime selection, command execution, semantic
  route, materialization, read, output, or #192 effect; and
- any change to a frozen active contract, candidate artifact bytes,
  ActiveArtifactSet, Capability Manifest, profile, or RuntimeBundle selection.

## 12. Non-goals

This contract and its Phase A PR do not:

- add a relation, migration, role, login, privilege, function, controller,
  credential, fixture, selection record, batch, or knowledge position;
- amend the selection schema, binding, carrier matrix, carrier selector,
  governed-command binding, RuntimeBundle carrier, or promotion decision;
- activate or promote any candidate artifact;
- publish or select a RuntimeBundle;
- create a production selector or application/worker repository API;
- define a public refusal or `RuntimeProblem` mapping;
- implement the production authorization provider;
- integrate `COMMIT_OPERATION_CLAIM_DRAFT`;
- add a route, profile, materialization, qualification, current-state read,
  historical view, WINDOW execution, output, receipt, deployment, hot reload,
  upgrade, rollback, supersession, or mutable current pointer;
- create an existing-target role migration or infrastructure repair path;
- import or change the legacy semantic surface; or
- implement or change #192.

## 13. Mandatory conformance prerequisite

The active temporal checker currently proves that the tenant selection package
is inactive and creates no storage or active role. That statement remains true
of the candidate package itself, but the checker does not yet authenticate or
confine a separate production storage-admission exception.

Before database Phase B, one separate Phase A conformance contract and one
separate conformance implementation PR must:

- pin this merged RFC's exact path, byte length, and SHA-256;
- allow the fixed selection binding identity and canonical digest only in the
  exact future migration-0005 and administrator control module;
- continue to reject candidate paths or identities in active RuntimeBundle
  catalogs, ActiveArtifactSet, Capability Manifest, profiles, routes,
  application/worker imports, and legacy imports;
- authenticate the exact migration-0005 filename and expected boundary;
- prove that the migration-0003 knowledge prefix remains stable while the full
  migration set advances independently;
- preserve the existing authenticated exception for migration 0004;
- verify that no checked-in operational selection row, target-tenant choice,
  selected bundle instance, or credential is introduced; and
- update the canonical collected test-node inventory only when mechanically
  required by a change to that inventory, including a count or node-ID change.

That conformance authority may not be changed in the database Phase B PR. If
the checker cannot express the exception without widening another active
authority, work stops for a new contract.

## 14. Smallest coherent future Phase B change

After the conformance prerequisite merges, the database Phase B PR is limited
to:

- fresh-target provisioning declarations for the exact capability, login, and
  sole membership;
- `kernel/migrations/0005_tenant_command_runtime_bundle_selection.sql` with
  the immutable relation, keys, forced RLS, two session-gated owner policies,
  mutation refusal, closed activation function, and exact allocator branch;
- the literal authoritative migration-set entry and mechanically changed
  migration/readiness/catalog verifier identities;
- one administrator-only fixed-binding validation and activation command that
  is absent from production and legacy runtime import closures;
- disposable real-PostgreSQL tests under the actual roles; and
- focused repository tests proving fixed binding validation and non-import.

It may implement the mechanism and invoke it only on a disposable test target
that is rolled back or destroyed. It may not create a retained selection.
It may not edit this RFC, the prerequisite candidate artifacts, the active
temporal checker, a frozen contract, an active registry, a runtime selector,
application or worker integration, routes, outputs, legacy code, or #192.

## 15. Verification

Phase A verification is limited to:

- exact reviewed-base and prerequisite pin checks;
- internal consistency of names, fields, roles, transition states, and stop
  conditions;
- proof that only this RFC changed;
- `python3 conformance/ofarm_pkg_contract_check.py`; and
- normal documentation checks required by the repository.

The later conformance contract must require Phase B to prove on a disposable
fresh PostgreSQL target:

- exact provisioning flags, membership, database connection, schema use, and
  absence of every forbidden privilege or role path;
- exact migration history, source digest, applied-prefix digest, structural
  verifier, observer, external verifier-pair digest, and readiness result;
- direct-DML denial under every non-owner role;
- exact forced-RLS posture, unchanged application/worker policy, exact
  session-gated owner policies, and absence of another executable owner path;
- exact function-only execution under the dedicated control login;
- complete fixed binding and sixteen-component validation before SQL;
- same-tenant sealed RuntimeBundle enforcement;
- atomic first activation with one batch and one allocated position;
- exact retry no-op with no head advance;
- unequal retry, mutation, deletion, and partial/corrupt state refusal with no
  write;
- concurrent app, worker, and control attempts preserve unique monotonic
  committed knowledge positions;
- rollback consumes no knowledge position and leaves no row or batch;
- the application and worker have no selection read path;
- no selection exists after migration or test setup unless a test creates it
  inside a disposable transaction or target;
- no runtime or legacy import reaches the control module;
- no active registry, route, profile, command, output, or #192 change; and
- the focused, PostgreSQL, temporal, architecture, package, and canonical test
  inventory gates pass.

## 16. Stop conditions for later boundaries

Work stops before:

1. implementing anything until the architect explicitly approves this exact
   contract and the documentation-only RFC merges;
2. implementing database Phase B until the separate conformance contract and
   conformance implementation merge;
3. changing a pinned prerequisite, candidate artifact, active authority, or
   frozen contract;
4. reconciling or upgrading any existing database target;
5. invoking the control operation outside a disposable test target that is
   rolled back or destroyed;
6. publishing the exact temporal RuntimeBundle composition needed by the
   selection unless a separate catalog/publication boundary has been reviewed;
7. implementing the production read-only selector;
8. mapping `RUNTIME_BUNDLE_SELECTION_REFUSED_NO_WRITE` to a public result or
   existing reason code;
9. implementing the production authorization provider;
10. integrating `COMMIT_OPERATION_CLAIM_DRAFT` with application or worker
   execution;
11. opening a route, profile, materialization, qualification, current-state
    read, historical view, WINDOW behavior, output, receipt, or deployment;
12. importing or changing legacy production behavior; or
13. adding or changing #192 behavior.

Each later item requires its own reviewed trust boundary and PR. Current-state
reads and outputs remain blocked by their output-governance prerequisites.

## 17. Approval gate

This document is a proposal, not an approved contract. PR authorship, commit
authorship, branch state, tests, review conclusions, mergeability, GitHub
credentials, or merge do not approve it.

Phase B remains forbidden until the designated architect explicitly approves
the exact contract in the designated Codex task and a documentation-only PR
truthfully records that approval before merge.
