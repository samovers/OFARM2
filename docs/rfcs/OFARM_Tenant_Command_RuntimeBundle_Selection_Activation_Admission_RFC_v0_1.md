# OFARM2 Tenant Command RuntimeBundle Selection Activation Admission — Phase A Contract v0.1

**Status:** architect-approved Phase A contract; documentation-only and without
storage, custody, activation, selection, runtime, or deployment effect

**Contract identity:**
`ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1`

**Reviewed base:** `0826a0e3572661756bd7a3200f4675ecaa38274c`

**Date:** 2026-08-01

**Primary ticket:** #176

**Governed command:** `COMMIT_OPERATION_CLAIM_DRAFT`

**Primary trust boundary:** one protected, `TenantBinding`-derived transition
from no command RuntimeBundle selection to one immutable tenant-owned
selection, recorded in that tenant's governed knowledge order

**Intended PR boundary:** this Phase A PR adds only this RFC. It does not amend
an active or frozen artifact and does not implement the transition.

## 1. Decision

After explicit architect approval of this exact contract, durable publication
of this RFC, and every separate prerequisite in section 13, one later Phase B
database PR may implement one closed pre-deployment control operation:

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
batch in the same already trusted tenant-bound transaction. The record tenant
comes only from `ofarm.current_tenant_id()`. The batch principal comes only
from `ofarm.current_authenticated_principal_ref()`. The batch receives one
database-allocated tenant knowledge position under the existing registered
tenant advisory lock. The selected RuntimeBundle must already be sealed in the
bound tenant's production RuntimeBundle storage.

The implementation may provide one administrator-only control adapter that
requires an already bound selection-control database transaction. The adapter
and SQL function accept no tenant identifier or principal identifier. They must
not provide a service, route, runtime hook, profile hook, environment selector,
current pointer, or application/worker write path.

No non-disposable selection record is created by approving, merging, testing,
or implementing this mechanism. Phase B may exercise the operation only on a
disposable test target that is rolled back or destroyed. Invoking it for any
other tenant is a later operational act outside Phase A and the Phase B
implementation PR.

## 2. Why this is one boundary

The immutable row, its closed function-only write custody, and its governed
activation batch are one protected state transition:

- storage without the closed transition would have no lawful write path;
- a write path without immutable tenant storage would have no durable authority;
- a selection outside the governed batch ledger would have no tenant knowledge
  position; and
- a separately committed batch and row could expose a partial or unaccounted
  selection.

The relation, closed owner-executed function, narrow allocator branch, and
mechanical structural verification needed to prove this one transition may
therefore travel in one Phase B database PR. That PR creates no new writer
role and gives the controller and login no direct relation privilege.

Tenant capability verification, principal resolution, creation of the
protected `TenantBinding`, and admission of the selection-control login to that
binding surface are a separate prerequisite trust boundary. They may not be
implemented in the selection-storage PR. Runtime reads, public refusal mapping,
authorization-provider integration, and governed command integration are also
independent boundaries and may not travel with it.

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
  `ofarm.publish_runtime_bundle(uuid,text,jsonb)`;
- protected tenant-binding functions:
  `ofarm.create_tenant_challenge()`,
  `ofarm.bind_tenant_capability(text)`,
  `ofarm.current_tenant_id()`, and
  `ofarm.current_authenticated_principal_ref()`;
- existing tenant serialization function:
  `ofarm.take_tenant_write_lock()`; and
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

The required selection-control tenant-binding admission and the two protected
dependency-grant admissions do not exist at this reviewed base. Section 13
defines each as a distinct mandatory contract and implementation. This RFC
does not grant the control login binder access, give `ofarm_owner` new execute
authority, or change tenant capability verification, principal resolution,
current-context semantics, or tenant-lock custody.

## 4. Exact future record

The future production relation is exactly:

```text
ofarm.tenant_command_runtime_bundle_selection
```

Its authority-bearing columns are exactly:

| Column | SQL class | Authority |
| --- | --- | --- |
| `tenant_id` | `uuid` | Derived only from the transaction's verified `TenantBinding` through `ofarm.current_tenant_id()`; immutable foreign key to `ofarm.tenant_registry`. |
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
`runtime_bundle_digest` name the same governed batch. Migration 0008 may add
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

The activation function is `SECURITY DEFINER`, owned by the existing unreachable
`ofarm_owner`, with a fixed trusted search path and fully qualified SQL. The
separate current-context and tenant-lock grant-custody prerequisites must first
establish the owner's exact ability to call those protected functions without
changing their bodies or exposing them to a login.

Two additive owner policies are permitted only while `SESSION_USER` is the
exact selection-control login:

- the selection-relation policy permits only rows whose `tenant_id` equals
  `ofarm.current_tenant_id()` and permits writes only when every binding and
  command field equals the fixed literals in this contract; and
- the governed-batch policy permits only the bound tenant and permits writes
  only when `tenant_id` and `authenticated_principal_ref` equal the protected
  current context, the operation and identifier shapes are fixed, the caller
  has the exact selection-control `SESSION_USER`, the allocator-assigned final
  knowledge position is positive and within the accepted JavaScript-safe
  bound, and the RuntimeBundle is sealed for that tenant.

The governed-batch policy observes the final row after `BEFORE INSERT`
triggers. It must not require the stored knowledge position to remain null.
Null-input enforcement belongs exclusively to
`ofarm.allocate_tenant_knowledge_position()` before that trigger assigns the
next position.

The existing application/worker policies are unchanged. Neither new policy
grants a relation privilege to the login or controller capability, and the
controller may execute no other owner function. RuntimeBundle verification
uses its exact bound-tenant predicate in the function; it adds no new
RuntimeBundle policy or grant.

## 5. Closed activation operation

The only non-owner write API is:

```text
ofarm.activate_commit_operation_claim_draft_runtime_bundle_selection(
    requested_runtime_bundle_digest text
)
RETURNS TABLE (
    selection_batch_id text,
    selection_knowledge_position int8,
    runtime_bundle_digest text
)
```

The SQL function accepts no tenant identity, principal identity,
selection-binding identity, command identity, schema, matrix, row, component
list, component identity, knowledge position, batch identity, request identity,
timestamp, profile, route, or source-contract choice.

The function fixes from this reviewed contract:

- the selection-binding identity and canonical digest;
- the command identity, command-binding identity, and canonical digest;
- the governed operation
  `ACTIVATE_COMMAND_RUNTIME_BUNDLE_SELECTION`;
- `ofarm.current_tenant_id()` as the only tenant source;
- `ofarm.current_authenticated_principal_ref()` as the only activation-batch
  principal source;
- `ofarm.take_tenant_write_lock()` as the only serialization source; and
- the rule that the activation batch's RuntimeBundle digest equals the selected
  RuntimeBundle digest.

The selection-control login is database custody, not tenant authority. A valid
signed tenant capability must already have been verified into a protected
`TenantBinding` for the same backend incarnation and full transaction. Missing,
stale, ambiguous, or invalid context refuses before a selection read, lock, or
write. The function never accepts registration existence, a tenant UUID, the
control-login name, or an administrator assertion as a substitute.

For an absent selection, the function must:

1. require `READ COMMITTED`;
2. require the exact provisioned selection-control session identity;
3. derive the tenant and Party reference from the protected current context;
4. validate only the selected RuntimeBundle SHA-256 syntax;
5. verify that the bound tenant's RuntimeBundle is already sealed;
6. acquire the bound tenant's existing advisory lock only through
   `ofarm.take_tenant_write_lock()`;
7. rederive the protected tenant and Party reference and recheck the sealed
   bundle and selection absence after acquiring the lock;
8. generate fresh `selection-batch:<uuid>` and
   `selection-request:<uuid>` identifiers inside PostgreSQL;
9. insert one governed activation batch whose tenant and
   `authenticated_principal_ref` equal the protected current context and whose
   caller-supplied knowledge position is null;
10. let the migration-owned allocator assign exactly the next committed bound
    tenant position under that same tenant advisory lock; and
11. insert the exact selection row in the same transaction.

No table-wide lock is permitted. The control adapter must commit or roll back
immediately after the one function call. A long-lived transaction,
caller-selected tenant or lock, alternate lock key, raw advisory-lock grant, or
change to the existing tenant-lock owner is forbidden.

For an existing selection, the function must compare every authority-bearing
field and the referenced batch under the same protected tenant context. An
exact retry returns the already sealed selection without inserting a batch or
advancing the tenant knowledge head. Any unequal, partial, corrupt,
cross-tenant, cross-principal, or missing-reference state refuses without a
write.

All validation and both inserts are atomic. SQL exceptions are internal
control-plane refusals. This contract adds no `RuntimeProblem` value and no
public mapping.

## 6. Fixed binding validation

Before calling the SQL function, the administrator-only control adapter must:

1. require an already tenant-bound selection-control transaction and accept no
   tenant or principal argument;
2. load the selection schema and binding only from the literal paths pinned in
   section 3;
3. verify their exact file lengths and SHA-256 values;
4. verify the binding's canonical length and SHA-256;
5. validate the complete binding against its exact schema;
6. build and validate the selected RuntimeBundle with the production
   RuntimeBundle model;
7. prove the exact sixteen-component command-required subset fixed by the
   binding, including role, identity, canonicalization, placement, byte
   length, digest, and each required schema/instance relationship;
8. treat every unrelated bundle component as inert for this command; and
9. pass only the computed full RuntimeBundle digest to SQL.

The binding path, matrix, rows, command identity, component closure, and source
contracts are compiled control authority, not command-line, environment,
request, route, profile, principal, capability, timestamp, or database-row
choices.

The adapter may receive a RuntimeBundle identity document to validate. Tenant
and principal authority come only from the separately admitted signed-capability
binding flow, not from the adapter, operator argument, database credential, or
registration lookup. This RFC neither mints that capability nor changes its
issuer, verifier, challenge, audience, lifecycle, or principal rules.

A bypass of fixed component-closure validation while using the dedicated
credential is compromised selection-control custody and is outside the
ordinary-role SQL threat model, just as bypassing model validation with the
RuntimeBundle publisher credential is compromised publisher custody. Even in
that excluded posture, the SQL function still cannot name or escape the bound
tenant.

No operational credential, secret, tenant capability, target-tenant choice,
selected bundle instance, or retained selection row is checked into the
repository. Bounded test values may exist only for disposable verification.

## 7. Selection-control custody

The separate tenant-binding admission prerequisite must first provision:

- `ofarm_command_runtime_bundle_selection_controller`: a `NOLOGIN`,
  `NOINHERIT`, `NOBYPASSRLS`, non-owner capability with no superuser, database
  creation, role creation, replication, application, worker, publisher,
  registrar, identity, authorization, readiness, migrator, or owner authority;
  and
- `ofarm_command_runtime_bundle_selection_control_login`: a separately
  credentialed `LOGIN`, `INHERIT`, `NOBYPASSRLS` identity with connection limit
  one and the standard control-session settings.

The login's sole membership is the controller capability with:

```text
INHERIT TRUE
SET FALSE
ADMIN FALSE
```

That prerequisite may grant the controller capability schema use and execute
only on `ofarm.create_tenant_challenge()` and
`ofarm.bind_tenant_capability(text)`, as required to establish a verified
`TenantBinding`. It may not grant application or worker membership, relation
access, raw advisory-lock access, signing or capability-minting authority, any
other binder routine, RuntimeBundle publication, selection write access, or
another control authority.

Two further prerequisites must separately establish that existing
`ofarm_owner` may execute the two protected current-context functions and the
protected tenant-lock function for the future closed activation function.
Those grants go to the unreachable owner, never to the controller or login.
Each prerequisite must define its own lawful grant-custody mechanism for its
one protected owner. If either grant cannot be made without changing a
function body, adding a role-assumption path, or widening another authority,
work stops for a new contract.

Phase B grants the controller capability execute only on the closed activation
function. The control login and capability receive no direct selection or
governed-batch relation privilege. The activation function must also require:

```text
SESSION_USER = 'ofarm_command_runtime_bundle_selection_control_login'
```

Credentials and tenant capabilities remain outside repository fixtures,
migrations, logs, and test snapshots.

OFARM2 is pre-deployment. Version 0.1 permits each role-set evolution only on a
freshly provisioned disposable target. Existing-target role reconciliation,
silent privilege widening, deployment upgrade, backup adoption, and repair are
unsupported. Before any deployment exists, this fresh-target limit must either
remain true or be replaced by a separately reviewed infrastructure-evolution
contract.

## 8. Knowledge-position authority

The existing `ofarm.allocate_tenant_knowledge_position()` trigger remains the
only allocator. Migration 0008 may add one exact branch for the selection
control session. That branch is valid only when:

- the knowledge position arrived null;
- a verified current `TenantBinding` exists for the same backend incarnation
  and full transaction;
- `tenant_id` equals `ofarm.current_tenant_id()`;
- `authenticated_principal_ref` equals
  `ofarm.current_authenticated_principal_ref()`;
- the governed operation is the fixed selection-activation operation;
- batch and request identifiers have the exact database-generated prefixes and
  UUID shapes fixed above;
- the batch RuntimeBundle digest is the selected sealed bundle digest; and
- the branch acquires the registered bound tenant's existing advisory lock
  through `ofarm.take_tenant_write_lock()` before reading the committed head.

The branch computes `max(knowledge_position) + 1` for the selected tenant under
that same per-tenant lock and preserves the existing exhaustion bound. It adds
no table lock or second lock protocol. It does not change the
application/worker branch, target-admin genesis rule, tenant-binding rule,
rollback semantics, committed-head meaning, or wall-clock non-authority rule.
An activation for tenant A therefore cannot block an ordinary governed write
for tenant B through this serialization mechanism.

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
- The existing tenant capability and binder contracts own verification and
  construction of `TenantBinding`; this contract does not change their
  semantics.
- The separate selection-control tenant-binding admission contract owns the
  exact additional database session allowed to invoke that unchanged binding
  surface and nothing else.
- The separate current-context consumer admission contract owns only the two
  binder-authorized execute grants from `ofarm_binder` to `ofarm_owner`.
- The separate tenant-lock consumer admission contract owns only the one
  lock-owner-authorized execute grant from `ofarm_tenant_lock_owner` to
  `ofarm_owner`.
- The protected current `TenantBinding` owns the activation tenant and Party
  reference. Registration existence and control credentials own neither.
- Fresh-target PostgreSQL provisioning owns role attributes, login membership,
  connection custody, schema use, and credential separation.
- The administrator-only control adapter owns authentication of the fixed
  selection binding and local RuntimeBundle closure validation after tenant
  binding. It does not own tenant or principal choice.
- `ofarm.publish_runtime_bundle(uuid,text,jsonb)` remains the sole publisher of
  sealed production RuntimeBundles. Publication does not select one.
- A later catalog/publication boundary must own the exact temporal
  RuntimeBundle composition and any real publication act; this contract owns
  neither.
- The activation function owns fixed-field construction, exact retry, atomic
  batch/row creation, and no-write refusal.
- The existing unreachable `ofarm_owner` remains the database and schema
  owner. Its use in this transition is confined to the one fixed activation
  function and two session-gated, bound-tenant RLS policies. Those policies
  authorize only the function's required row visibility and fixed writes; they
  do not alter the existing application/worker policy or create a new
  role-assumption path.
- `ofarm.governed_write_batch` remains the sole committed tenant knowledge
  ledger.
- `ofarm.allocate_tenant_knowledge_position()` remains the sole knowledge
  allocator.
- `ofarm.take_tenant_write_lock()` remains the sole tenant write-serialization
  path for runtime and selection activation.
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
  identity control. Its narrowly admitted use of the binding functions does
  not give the binder selection authority.
- **TCSA-004 — Bound tenant and Party only.** The record tenant and activation
  batch principal come only from the protected current `TenantBinding`; neither
  is an activation argument or control-login assertion.
- **TCSA-005 — One immutable row.** One tenant and binding version has at most
  one sealed selection; change requires a new reviewed binding version.
- **TCSA-006 — Sealed same-tenant bundle.** The selected digest already names a
  sealed RuntimeBundle for the same tenant.
- **TCSA-007 — Exact closure before write.** The fixed sixteen-component subset
  validates before SQL activation; unrelated components remain inert.
- **TCSA-008 — One atomic governed batch.** First activation creates exactly
  one batch and one selection row in the same transaction.
- **TCSA-009 — Database knowledge authority.** The caller never supplies or
  derives the knowledge position; the migration-owned allocator assigns it.
- **TCSA-010 — One tenant lock protocol.** Selection activation and ordinary
  writes use the same registered per-tenant advisory lock; tenant A activation
  does not take a table-wide lock that blocks tenant B.
- **TCSA-011 — Exact retry is inert.** Exact retry creates no row or batch and
  consumes no position.
- **TCSA-012 — Unequal reuse is no-write.** Replacement, update, deletion,
  partial equality, or conflicting reuse refuses atomically.
- **TCSA-013 — No implicit selection.** Publication, existence, newest, sole,
  profile-listed, or loose component rows never create selection state.
- **TCSA-014 — Write only.** This boundary provides no application/worker read
  authority and does not resolve a selection at command time.
- **TCSA-015 — No activation by repository state.** Approval, merge,
  conformance, migration presence, role presence, or function presence creates
  no tenant selection.
- **TCSA-016 — Production/legacy firewall.** No production code imports or
  consults a legacy Store, profile runtime, semantic route, materializer, or
  output module.
- **TCSA-017 — Closed semantic surface.** No route, command, current-state
  read, historical view, WINDOW behavior, or output opens.
- **TCSA-018 — Audit separation.** No #192 event, receipt, attribution, or
  failure behavior is added.
- **TCSA-019 — Pre-deployment limit.** Role evolution is fresh-target only and
  cannot silently reconcile an existing target.
- **TCSA-020 — RLS remains closed.** Forced RLS remains enabled; only the
  existing unreachable owner inside the one function receives the
  session-gated bound-tenant policy path, with fixed write checks and no login,
  controller relation privilege, or assumption path.
- **TCSA-021 — Prerequisite separation.** Selection-control tenant binding,
  current-context consumer admission, tenant-lock consumer admission,
  selection-storage conformance, and selection storage are separately
  contracted and implemented; no PR combines those authorities.

## 11. Required negative cases

Verification must refuse or prove unsupported:

- missing, altered, substituted, or multiply resolved Phase A authority;
- changed prerequisite length, digest, canonical digest, identity, or path;
- caller-supplied tenant, principal, binding, matrix, row, source-contract,
  command, component, batch, request, knowledge-position, timestamp, or profile
  choice;
- missing, stale, ambiguous, cross-transaction, cross-backend, or otherwise
  invalid protected `TenantBinding`;
- registration existence, database credentials, an administrator assertion, or
  the selection-control login name substituted for the bound tenant or Party;
- direct selection-relation reads or DML under the application, worker,
  publisher, binder, authorizer, registrar, identity, readiness, or
  selection-control login;
- direct governed-batch insertion by the selection-control roles outside the
  closed activation function;
- execute by any session other than the exact selection-control login;
- extra membership, `SET ROLE`, administration, inheritance widening,
  connection widening, direct table privilege, or raw advisory-lock grant;
- disabled forced RLS, a changed application/worker policy, an owner policy
  usable outside the exact control session and protected context, widened
  owner-policy checks, direct controller or login relation privilege, or
  controller execute on another owner function;
- absent, unsealed, malformed, cross-tenant, or digest-mismatched RuntimeBundle;
- missing, substituted, wrong-role, wrong-placement, wrong-canonicalization,
  wrong-length, wrong-digest, or schema-invalid required component;
- an unrelated component influencing selection authority;
- selection inferred from publication, existence, ordering, newest, sole,
  profile, environment, route, request, principal, or capability data;
- supplied or wall-clock-derived knowledge position;
- batch tenant or `authenticated_principal_ref` unequal to the protected current
  context;
- activation without the registered bound tenant's existing advisory lock;
- a table-wide lock, caller-selected lock, alternate lock key, or second
  serialization protocol;
- concurrent application, worker, or control allocation producing duplicate,
  skipped, reused, or externally selected committed positions;
- activation for tenant A blocking an ordinary governed write for tenant B
  through selection serialization;
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
- grant the selection-control login tenant-binding access or change capability
  verification, signer custody, principal resolution, current-context
  semantics, or tenant-lock custody;
- amend the selection schema, binding, carrier matrix, carrier selector,
  governed-command binding, RuntimeBundle carrier, or promotion decision;
- activate or promote any candidate artifact;
- publish or select a RuntimeBundle;
- create a production selector or application/worker repository API;
- create a service, route, or generic administrator tenant-selection API;
- define a public refusal or `RuntimeProblem` mapping;
- implement the production authorization provider;
- integrate `COMMIT_OPERATION_CLAIM_DRAFT`;
- add a route, profile, materialization, qualification, current-state read,
  historical view, WINDOW execution, output, receipt, deployment, hot reload,
  upgrade, rollback, supersession, or mutable current pointer;
- create an existing-target role migration or infrastructure repair path;
- import or change the legacy semantic surface; or
- implement or change #192.

## 13. Mandatory separate prerequisites

### 13.1 Tenant-binding admission

The selection-control login cannot currently establish a `TenantBinding`.
The exact existing challenge and capability-binding functions are granted only
to application and worker roles. Adding a new authenticated session to that
principal-resolution surface is a separate trust boundary.

Before selection-storage conformance or database Phase B, one separate Phase A
contract and one separate implementation PR must govern only:

- contract identity
  `ofarm.tenant-binding-selection-control-admission.issue176.v0.1`;
- Phase A RFC path
  `docs/rfcs/OFARM_Tenant_Binding_Selection_Control_Admission_RFC_v0_1.md`;
- fresh-target provisioning of the exact controller capability, control login,
  and sole membership in section 7;
- exact execute grants to the controller capability on only
  `ofarm.create_tenant_challenge()` and
  `ofarm.bind_tenant_capability(text)`;
- migration path
  `kernel/migrations/0005_tenant_binding_selection_control_admission.sql`;
- the exact migration-set, provisioning, structural-verifier, readiness,
  external catalog-verifier, and documentation changes mechanically required
  by those roles and grants; and
- focused proof that the control login can establish a normal verified
  `TenantBinding` but cannot mint or sign a capability, name a tenant, bypass a
  challenge, read tenant data, take a raw lock, publish a RuntimeBundle, create
  a selection, or acquire application/worker authority.

The migration-0005 path reserves the prerequisite's migration-history slot; it
does not assert that the migration runner may issue the binder-owned grants.
The prerequisite contract must pin the exact independently authorized
grant-custody mechanism, its transient authority, its file allowlist, its
self-removal or final privilege state, and its structural proof before
implementation. No such mechanism is authorized by this RFC.

That prerequisite may not edit the challenge or binding function bodies;
change their authority semantics; leave the migrator, controller, or login
able to assume `ofarm_binder`; grant another binder routine; give the
controller or login execute on a current-context or lock function; or add
selection storage. If the exact final grants cannot be made without one of
those effects or another authority widening, the prerequisite stops for a new
reviewed principal-resolution or grant-custody contract rather than widening
Phase B.

### 13.2 Current-context consumer admission

The existing `ofarm_owner` cannot currently execute the two binder-owned
current-context functions. Granting that unreachable owner the ability to
consume protected context is not part of admitting the control login to create
the context.

Before selection-storage conformance or database Phase B, one separate Phase A
contract and one separate implementation PR must govern only:

- contract identity
  `ofarm.tenant-current-context-selection-owner-admission.issue176.v0.1`;
- Phase A RFC path
  `docs/rfcs/OFARM_Tenant_Current_Context_Selection_Owner_Admission_RFC_v0_1.md`;
- exact execute grants from `ofarm_binder` to the unreachable `ofarm_owner` on
  only `ofarm.current_tenant_id()` and
  `ofarm.current_authenticated_principal_ref()`;
- migration path
  `kernel/migrations/0006_tenant_current_context_selection_owner_admission.sql`;
- the exact grant-custody, migration-set, structural-verifier, readiness,
  external catalog-verifier, and documentation changes mechanically required
  by only those two grants; and
- focused proof that no login or controller receives either grant, no new
  binder or owner role-assumption path exists, and no function body or context
  semantics change.

The migration-0006 path reserves this prerequisite's migration-history slot;
it does not authorize the migration runner to act as `ofarm_binder`. The Phase
A prerequisite must pin the independently authorized grant-custody mechanism,
its transient authority, its closed file allowlist, its self-removal or final
privilege state, and its structural proof. If that cannot be done without
widening principal-resolution, migration, or owner authority, it stops for a
new contract. It may not add the lock grant, selection storage, the activation
function, or controller execution authority.

### 13.3 Tenant-lock consumer admission

The existing `ofarm_owner` also cannot currently execute the protected
tenant-lock function. Admitting that one consumer is a change to tenant-lock
custody and is separate from current-context access.

Before selection-storage conformance or database Phase B, one separate Phase A
contract and one separate implementation PR must govern only:

- contract identity
  `ofarm.tenant-write-lock-selection-owner-admission.issue176.v0.1`;
- Phase A RFC path
  `docs/rfcs/OFARM_Tenant_Write_Lock_Selection_Owner_Admission_RFC_v0_1.md`;
- the exact execute grant from `ofarm_tenant_lock_owner` to the unreachable
  `ofarm_owner` on only `ofarm.take_tenant_write_lock()`;
- migration path
  `kernel/migrations/0007_tenant_write_lock_selection_owner_admission.sql`;
- the exact grant-custody, migration-set, structural-verifier, readiness,
  external catalog-verifier, and documentation changes mechanically required
  by only that grant; and
- focused proof that no login or controller receives the grant, no raw
  advisory-lock privilege or alternate lock path exists, no owner-role
  assumption path exists, and the function body and lock-key authority remain
  unchanged.

The migration-0007 path reserves this prerequisite's migration-history slot;
it does not authorize the migration runner to act as
`ofarm_tenant_lock_owner`. The Phase A prerequisite must pin the independently
authorized grant-custody mechanism, its transient authority, its closed file
allowlist, its self-removal or final privilege state, and its structural proof.
If that cannot be done without widening tenant-lock, migration, or owner
authority, it stops for a new contract. It may not add a context grant,
selection storage, the activation function, or controller execution authority.

### 13.4 Selection-storage conformance

The active temporal checker currently proves that the tenant selection package
is inactive and creates no storage or active role. That statement remains true
of the candidate package itself, but the checker does not yet authenticate or
confine a separate production storage-admission exception.

After all three authority-admission implementations above merge, one separate
Phase A conformance contract and one separate conformance implementation PR
must:

- pin this merged RFC's exact path, byte length, and SHA-256;
- pin the merged tenant-binding, current-context consumer, and tenant-lock
  consumer admission RFC and implementation identities;
- allow the fixed selection binding identity and canonical digest only in
  `kernel/migrations/0008_tenant_command_runtime_bundle_selection.sql` and
  `deployment/postgresql/tenant_command_runtime_bundle_selection.py`;
- continue to reject candidate paths or identities in active RuntimeBundle
  catalogs, ActiveArtifactSet, Capability Manifest, profiles, routes,
  application/worker imports, and legacy imports;
- authenticate the exact migration-0008 filename and boundary;
- prove that the migration-0003 knowledge prefix remains stable while the full
  migration set advances independently;
- preserve the authenticated migration-0004 exception and exact
  migration-0005, migration-0006, and migration-0007 prerequisite admissions;
- verify that no checked-in operational selection row, tenant capability,
  target-tenant choice, selected bundle instance, or credential is introduced;
  and
- update the canonical collected test-node inventory only when mechanically
  required by a change to that inventory, including a count or node-ID change.

None of the three admission authorities or the conformance authority may be
changed in the selection-storage Phase B PR. If the checker cannot express the
exception without widening another active authority, work stops for a new
contract.

## 14. Smallest coherent future Phase B change

After the conformance prerequisite merges, the database Phase B PR is limited
to this closed file allowlist:

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

No other path is permitted. If implementation requires another production,
provisioning, migration, test, documentation, contract, conformance, or
authority file, Phase B stops and proposes that boundary separately.

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

- exact merged tenant-binding, current-context consumer, and tenant-lock
  consumer prerequisite identities and unchanged protected function bodies;
- exact controller and login provisioning flags, membership, database
  connection, schema use, and absence of every forbidden privilege or role
  path;
- exact owner execute grants on only the two protected current-context
  functions and the protected tenant-lock function, with no protected-owner
  role-assumption path and no direct controller or login grant to those three
  functions;
- exact migration history, source digest, applied-prefix digest, structural
  verifier, observer, external verifier-pair digest, and readiness result;
- direct-DML denial under every non-owner role;
- exact forced-RLS posture, unchanged application/worker policy, exact
  session-gated bound-tenant owner policies, and absence of direct controller
  or login relation privilege or execute on another owner function;
- exact governed-batch policy acceptance of the allocator-assigned positive
  final position and structural proof that its expression does not require the
  stored position to be null;
- allocator-branch refusal of an explicitly supplied knowledge position before
  any assignment or write;
- exact function-only execution under the dedicated control login;
- absence of a tenant or principal argument at the adapter and SQL seams;
- refusal before any selection read, lock, or write when the protected
  `TenantBinding` is absent or invalid;
- exact equality between record tenant, batch tenant, batch Party reference,
  and the protected current context;
- complete fixed binding and sixteen-component validation before SQL;
- same-tenant sealed RuntimeBundle enforcement;
- atomic first activation with one batch and one allocated position;
- exact retry no-op with no head advance;
- unequal retry, mutation, deletion, and partial/corrupt state refusal with no
  write;
- same-tenant app, worker, and control attempts serialize through the one
  registered tenant advisory lock and preserve distinct monotonic committed
  positions;
- tenant A activation does not take a table-wide lock or block an ordinary
  tenant B write through selection serialization;
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
2. current-context or tenant-lock consumer admission, selection-storage
   conformance, or Phase B until the separate selection-control tenant-binding
   admission contract and implementation merge;
3. tenant-lock consumer admission, selection-storage conformance, or Phase B
   until the separate current-context consumer admission contract and
   implementation merge;
4. selection-storage conformance or Phase B until the separate tenant-lock
   consumer admission contract and implementation merge;
5. implementing database Phase B until the separate selection-storage
   conformance contract and conformance implementation merge;
6. changing a pinned prerequisite, protected function body, tenant capability
   authority, candidate artifact, active authority, or
   frozen contract;
7. accepting a tenant or principal argument, registration lookup, credential
   identity, or administrator assertion as selection tenant authority;
8. reconciling or upgrading any existing database target;
9. invoking the control operation outside a disposable test target that is
   rolled back or destroyed;
10. publishing the exact temporal RuntimeBundle composition needed by the
   selection unless a separate catalog/publication boundary has been reviewed;
11. implementing the production read-only selector;
12. mapping `RUNTIME_BUNDLE_SELECTION_REFUSED_NO_WRITE` to a public result or
   existing reason code;
13. implementing the production authorization provider;
14. integrating `COMMIT_OPERATION_CLAIM_DRAFT` with application or worker
   execution;
15. opening a route, profile, materialization, qualification, current-state
    read, historical view, WINDOW behavior, output, receipt, or deployment;
16. importing or changing legacy production behavior; or
17. adding or changing #192 behavior.

Each later item requires its own reviewed trust boundary and PR. Current-state
reads and outputs remain blocked by their output-governance prerequisites.

## 17. Approval gate

This document is a proposal, not an approved contract. PR authorship, commit
authorship, branch state, tests, review conclusions, mergeability, GitHub
credentials, or merge do not approve it.

Phase B remains forbidden until the designated architect explicitly approves
the exact contract in the designated Codex task and a documentation-only PR
truthfully records that approval before merge.

## Appendix A. Architect approval record

This appendix is the documentation-only approval record required by section
17. The proposal-state wording in section 17 describes the state of the exact
design bytes before the later approval recorded here. It is preserved as part
of those approved design bytes and is not a competing current status.

The designated architect approved this exact Phase A design:

- contract identity:
  `ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1`;
- repository path:
  `docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_Activation_Admission_RFC_v0_1.md`;
- repository review base:
  `4aa82240f788ba5f8e3e2451c3822df4293bb5be`;
- approved design canonical byte length: `49259`; and
- approved design digest:
  `sha256:137fc69f203ff18229efd0c97ada8affae209c0e64dd3e8c464d7627937de44b`.

The complete live decision card preceded the approval in the same Codex task.
Its evidence is:

- Codex task identifier:
  `019fa821-93c9-7ef1-8c94-1c0e92ea46b9`;
- decision-card canonical byte length: `1886`;
- decision-card digest:
  `sha256:d0782493042dc2b6dd782a2a8dcced1315ad2474c5b305da1a54ae7ab775fc28`;
- approval turn stable reference:
  `019fc0d0-7f17-7db0-9989-316971f4d112`;
- user-authored approval-message stable reference: `item-1550`;
- user-authored approval-message timestamp: `2026-08-02T04:51:57Z`;
- approval-sentence canonical byte length: `528`; and
- approval-sentence digest:
  `sha256:4e195b7443c3919d748c5697a3f265b9ee9b675236ea23d7741926cd171f0b4c`.

The exact user-authored approval sentence was:

> I explicitly approve the Phase A design of contract ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1 at sha256:137fc69f203ff18229efd0c97ada8affae209c0e64dd3e8c464d7627937de44b (49,259 bytes) in Codex task 019fa821-93c9-7ef1-8c94-1c0e92ea46b9 and authorize one documentation-only parent approval record with exactly the provenance, effects, non-effects, preservation rules, and next required sequence stated in decision card sha256:d0782493042dc2b6dd782a2a8dcced1315ad2474c5b305da1a54ae7ab775fc28.

The approval has exactly two effects:

1. the pinned parent Phase A design is architect-approved; and
2. this one documentation-only parent approval record is authorized.

The only permitted changes from the approved design bytes are the status
metadata and this appendix. The decision, authority map, invariants, negative
cases, architecture, and pull-request boundaries remain byte-for-byte
unchanged.

The approval does not approve the tenant-binding child contract and does not
authorize Phase B, a migration, database storage, a role or grant change,
runtime selection or activation, a RuntimeBundle or profile change, command or
route integration, materialization, output, legacy behavior, or #192 behavior.

After this approval record merges, later work must compute the complete
approved-parent file length and digest, re-pin the child contract to that
identity, obtain explicit approval of the exact re-pinned child, and publish
and merge the child approval record before evaluating its Phase B gate.
