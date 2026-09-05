# OFARM2 Tenant Command RuntimeBundle Selector Admission — Phase A Contract v0.1

**Status:** proposed Phase A contract; documentation-only, unapproved, and
without implementation effect

**Decision identity:**
`OFARM2-ISSUE363-TRUSTED-COMMAND-RUNTIME-BUNDLE-SELECTOR-001`, version `1`

**Contract identity:**
`ofarm.tenant-command-runtime-bundle-selector.issue363.v0.1`

**Date:** 2026-09-05

**Primary Delivery issue:** #363

**Delivery linkage:** Closes #363 only when this implementation PR merges.

**Tracking parent:** #176

**Satisfied dependencies:** #170, #173, #174, and #192

**Phase A comparison base:**
`fcb729b62c365b833c58b0f4ef759aa877bc0ced`

**Named draft implementation PR:** pending creation from
`delivery/issue-363-runtime-bundle-selector`

**Phase A review-head boundary:** this RFC only

**Primary trust boundary:** read-only, tenant-bound resolution and full
validation of the persisted `COMMIT_OPERATION_CLAIM_DRAFT` RuntimeBundle
selection at one captured tenant knowledge cut

**Intended implementation PR boundary:** the same draft PR may, only after an
exact approval of this decision version, add the database read capability,
production selector, narrow tenant UnitOfWork integration, and the tests and
mechanical conformance evidence listed in section 15. It may change no other
trust boundary.

## 1. Decision in plain English

OFARM already has a separately controlled way to choose one sealed
RuntimeBundle for the future `COMMIT_OPERATION_CLAIM_DRAFT` command. The choice
is stored immutably, but normal application and worker code cannot read it.

This decision admits one read-only production path. After PostgreSQL has bound
the request to a verified tenant, the tenant UnitOfWork may ask one no-argument
question:

```text
resolve_commit_operation_claim_draft_runtime_bundle()
```

The method either returns one tenant-bound, fully checked
`TrustedCommandRuntimeBundle` or raises one opaque internal refusal. The caller
cannot choose the tenant, command, binding, bundle digest, component list, or
knowledge position.

The read does not allocate a governed batch, advance tenant knowledge, take a
tenant write lock, persist a refusal, emit an output, or open an endpoint. It
only makes the already stored authority safely available to later work.

## 2. Current state and the exact gap

Current main already provides these relevant guarantees:

- `TenantUnitOfWorkManager` checks out one PostgreSQL connection, starts a
  `READ COMMITTED` transaction, installs one verified `TenantBinding`, and
  hides the connection from the UnitOfWork caller;
- migration `0008_tenant_command_runtime_bundle_selection.sql` stores at most
  one immutable selection per tenant for the fixed selection binding;
- that selection references the exact sealed RuntimeBundle and the exact
  governed activation batch that received its selection knowledge position;
- the selection-control login is the only production client of the activation
  transition;
- the application and worker roles have no direct privilege on the selection
  relation;
- RuntimeBundle, membership, and retained-content rows are immutable and
  content addressed;
- migration `0009_runtime_bundle_global_content_retention.sql` closes global
  retained-content durability; and
- the pure `RuntimeBundle` model reconstructs canonical component identity and
  validates the admitted component semantics.

The missing guarantee is a production read that joins these authorities
without accepting a request-selected digest or importing the administrator
selection-control adapter.

### 2.1 Knowledge-cut terminology correction

Issue #363 uses `Kbefore` for the head captured by the selector. The durable
design uses the more precise name `Kselection`.

`Kbefore` is already defined by the operation-claim command contract as the
knowledge position immediately before that command's future governed batch:

```text
Kbefore = Kbatch - 1
```

This selector must run before that batch is allocated. Another unrelated batch
may commit after selection resolution and before the future command obtains
`Kbatch`. Therefore the two values can differ without any inconsistency.

This contract defines:

```text
Kselection = greatest committed tenant knowledge position visible to the
             selector's fixed PostgreSQL statement snapshot

1 <= selectionKnowledgePosition <= Kselection
```

A later command boundary may require:

```text
Kselection <= Kbefore
```

It must use the result cached by this UnitOfWork and must not resolve the
selection again. This issue neither allocates `Kbatch` nor derives `Kbefore`.

`Kselection` is a knowledge-time observation. It is not a valid-time value, a
generic caller `KnowledgeCut`, or a historical query parameter.

## 3. Capability and effects

### 3.1 Admitted capability

One active tenant UnitOfWork may resolve the fixed selection exactly once and
cache its terminal result for the rest of that UnitOfWork.

The capability is available through the existing production composition path:

```text
ApplicationRuntime
  -> TenantUnitOfWorkManager
    -> TenantUnitOfWork
      -> fixed private resolver callback
        -> PostgreSQL fixed no-argument resolver
        -> immutable production RuntimeBundle relations
```

The same database function is executable by the existing `ofarm_app` and
`ofarm_worker` roles after trusted tenant binding. No new role or login is
admitted.

### 3.2 Permitted effects

Phase B may:

- add one additive V10 tenant migration;
- add one fixed production selector module;
- add one no-argument method and private state to `TenantUnitOfWork`;
- make a selector refusal mark that UnitOfWork rollback-only;
- extend architecture and temporal conformance for this exact production read;
- add focused unit and PostgreSQL evidence; and
- update migration, provisioning, documentation, and canonical test inventory
  evidence mechanically required by those changes.

### 3.3 Forbidden effects

Phase B may not:

- accept any request or caller selection input;
- activate, replace, repair, or publish a selection or RuntimeBundle;
- allocate a governed batch or knowledge position as part of resolution;
- turn the selected result into command authority outside its owning
  UnitOfWork;
- implement `COMMIT_OPERATION_CLAIM_DRAFT`;
- make an authorization decision;
- add a route, response, reason code, receipt, output, profile, manifest, or
  capability claim;
- persist a post-binding refusal or change #192 audit behavior;
- add a valid-time or dual-cut query;
- add a role, login, credential, key, secret, or recovery path; or
- change or import the selection-control adapter, publisher, binder, legacy
  Store, or legacy RuntimeBundle repository.

## 4. Trust model

### 4.1 Protected assets

- the association between one verified tenant and that tenant's one immutable
  command RuntimeBundle selection;
- the exact fixed selection-binding and command-binding identities;
- the selection activation batch and its knowledge position;
- the truthful value of `Kselection`;
- the sealed RuntimeBundle digest, canonical identity document, complete
  membership, and exact retained bytes;
- the fixed 16-component command-required closure;
- tenant isolation and the inability to detect another tenant's selection;
- the application/worker versus selection-control authority split;
- the UnitOfWork connection-hiding and transaction-lifetime guarantees; and
- the absence of write, audit, route, output, and public-refusal effects.

### 4.2 Trusted components

- the already verified `TenantBinding` installed by
  `TenantUnitOfWorkManager`;
- protected PostgreSQL current-tenant context;
- the exact V10 database structure, forced RLS, and immutable constraints;
- the fixed, schema-qualified, no-argument database resolver;
- the pinned selection-binding schema and binding artifact;
- production RuntimeBundle, membership, and retained-content relations;
- strict JSON parsing, canonical JSON, SHA-256 checks, JSON Schema validation,
  `RuntimeComponent`, and `RuntimeBundle`;
- the new production selector's closed validation sequence;
- the UnitOfWork's private callback, one-attempt cache, active-state check, and
  rollback-only state; and
- the existing `ApplicationRuntime` composition root.

### 4.3 Untrusted inputs and observations

- every value returned by PostgreSQL until its type, shape, tenant, identity,
  range, and relationship checks succeed;
- the presence or absence of the selection row;
- the selected digest and every bundle, membership, and retained-content row;
- all retained bytes, including bytes from a previously trusted publisher;
- database exception text and driver exception details;
- object use after the UnitOfWork closes;
- caller attempts to pass a digest or other selection value through an
  unrelated API; and
- concurrent selection activation or unrelated tenant batches.

The resolver has no public input from an HTTP body, header, route, profile,
environment variable, clock, tenant reference, Party, digest, command, binding,
component set, or knowledge cut.

### 4.4 Excluded compromise capabilities

Compromise of PostgreSQL itself, the migration owner, application process,
Python interpreter, installed third-party packages, operating system, source
repository, trusted deployment artifact, selection-control credentials,
RuntimeBundle publisher credentials, or tenant-binding credentials is outside
this boundary.

Arbitrary in-process private-field mutation and arbitrary SQL execution through
a separately compromised application process are also outside this boundary.
Normal application code remains in scope: it must receive no connection handle
or general selection-table capability from this change.

Publisher compromise is excluded, but corrupted, missing, or inconsistent
persisted content is still refused by reconstruction. This boundary does not
repair corruption.

## 5. Authority map

- `TenantBinding.tenant_id` is the sole in-process tenant authority.
- `ofarm.current_tenant_id()` is the sole database tenant authority after
  binding. The two values must be exactly equal.
- `ofarm.tenant_registry` supplies the matching stable tenant reference used
  only to verify tenant-bearing RuntimeBundle semantics.
- The exact pinned selection-binding artifact owns the selection binding,
  command identity, command binding, and required component closure.
- `ofarm.tenant_command_runtime_bundle_selection` owns the immutable mapping
  from tenant plus fixed binding to one RuntimeBundle digest and one activation
  batch.
- The referenced activation row in `ofarm.governed_write_batch` owns the
  selection knowledge position and activation provenance.
- The greatest visible committed `governed_write_batch.knowledge_position`
  owns `Kselection`.
- A clock, timestamp, transaction ID, row order, UUID order, request value,
  profile, package order, newest bundle, or sole bundle owns no selection or
  knowledge authority.
- `ofarm.runtime_bundle` owns the sealed digest and canonical bundle document.
- `ofarm.runtime_bundle_component` owns exact membership metadata.
- `ofarm.runtime_content_blob` and
  `ofarm.runtime_tenant_content_blob` own retained component bytes according
  to each membership placement.
- `RuntimeComponent` and `RuntimeBundle` own in-process reconstruction,
  canonicalization, digest, membership, and semantic validation.
- The fixed selection-binding closure owns which 16 components are required by
  this command. Additional valid bundle components are allowed but confer no
  command authority.
- The production selector owns only lookup orchestration, comparison of the
  independent authorities above, full reconstruction, fixed-closure checking,
  and one opaque internal success/refusal result.
- `TenantUnitOfWork` owns the resolver's active transaction lifetime and
  terminal cache. It exposes neither the connection nor arbitrary SQL.
- `ApplicationRuntime` owns production reachability. Its existing composition
  is sufficient; Phase B does not edit it.
- The selection-control adapter remains the sole activation client and is
  neither imported nor edited.
- #175 retains authorization authority. #192 retains pre-tenant audit
  authority and its existing post-binding rollback behavior.

## 6. Fixed binding and closure authority

### 6.1 Pinned source artifacts

The production selector independently authenticates the same immutable source
artifacts as the selection-control path without importing that path:

| Artifact | Exact path | File bytes | File SHA-256 |
| --- | --- | ---: | --- |
| selection-binding schema | `contracts/candidates/temporal_runtime_bundle_selection/OFARM_TenantCommandRuntimeBundleSelectionBinding_schema_v0_1.json` | 17,252 | `sha256:56604a52465ffc027382e99dea96f2c9bc1bd2479cbaff30dec6bd39c08e6b3d` |
| fixed selection binding | `contracts/candidates/temporal_runtime_bundle_selection/OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json` | 15,993 | `sha256:1500ffbbfdf11207a6657848fce12618347f767578e55dc070bb282dc5775aac` |

The binding must also canonicalize to exactly 13,287 bytes and:

```text
sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f
```

Its closed identities are:

```text
selection binding:
  ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1

command:
  COMMIT_OPERATION_CLAIM_DRAFT

command binding:
  ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1

command binding canonical digest:
  sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1
```

The selector must strictly parse both files, validate the schema, validate the
binding completely against that schema, verify all file and canonical pins,
and then read the closure from the authenticated binding. Paths are location
hints only; exact bytes and digests are authority.

This deliberately leaves the control adapter unchanged. The two paths are
independent verifiers of one authoritative artifact, not two sources of
selection truth. Temporal conformance must prove that their top-level pins
remain equal to each other and to the checked-in bytes. Phase B must stop and
split a neutral-validator prerequisite if satisfying this rule would require
moving procedural validation into, importing, or changing the control path.

### 6.2 Exact required component closure

The authenticated binding declares
`EXACT_COMMAND_REQUIRED_COMPONENT_SUBSET`, count 16, with unrelated valid
components allowed but inert. The exact required rows are:

| Role | Identity | Canonicalization | Placement | Bytes | Content digest |
| --- | --- | --- | --- | ---: | --- |
| `CONTRACT_SCHEMA` | `contract:ofarm.temporal-coordinate.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 3,943 | `sha256:b81e4c7b0aacebb11ff8bf0d186cdb36150fade31180552b46f7be9e13c551eb` |
| `CONTRACT_SCHEMA` | `contract:ofarm.temporal-carrier-matrix.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 3,088 | `sha256:cdb5c09ec033cc3b4de1dea9eb383c499045d8a3bfc5b80fd7abeab579a566ed` |
| `CONTRACT_SCHEMA` | `contract:ofarm.temporal-carrier-selection-binding.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 3,340 | `sha256:d252420507393d1d9816a0f20549faa8cf67c94bd1e2c10a3c509aadf4f3800a` |
| `CONTRACT_SCHEMA` | `contract:ofarm.temporal-governed-command-binding.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 13,132 | `sha256:afda003df90e2787cfdc97f5561e3e5b098177a5add91556af2e935a3b9711db` |
| `CONTRACT_SCHEMA` | `contract:ofarm.commitingressrequest.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 3,405 | `sha256:397ec3a61ed572b14f9916bc9e7b316ff48150c743c6b7aa2eab94a3be3e8ffc` |
| `CONTRACT_SCHEMA` | `contract:ofarm.semanticeventenvelope.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 4,238 | `sha256:75662a6c4952a62b7e8f8e9de99c23c98899c692914a98ba4b752873f48bd1a4` |
| `CONTRACT_SCHEMA` | `contract:ofarm.executionrecordpayload.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 20,245 | `sha256:ca62f01d056794ee588d55c3f5df652fc039124b76af5631d417714bc7059ff0` |
| `CONTRACT_SCHEMA` | `contract:ofarm.authorizationdecisionrequest.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 4,666 | `sha256:a62c7b8a269130a4c3b618ab029ffada97597626131bd45e2335ff31e95880fa` |
| `CONTRACT_SCHEMA` | `contract:ofarm.authorizationdecisionresult.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 5,538 | `sha256:f6d0de06e1bc6b8fc7a3f991abf28f2a3242942b50834b97292fa8e00fdd0127` |
| `CONTRACT_SCHEMA` | `contract:ofarm.authorizationdecisiontrace.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 3,606 | `sha256:1cc9886c3a9787a76657753fb682dd29337f2b8485e51557607bb6736de1571d` |
| `CONTRACT_SCHEMA` | `contract:ofarm.promotiontrace.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 4,759 | `sha256:07c073fba6fa023e4463339a383d4b0d881be38c17d626ec7d27caaa688d4e3f` |
| `CONTRACT_SCHEMA` | `contract:ofarm.commitingressresult.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 5,362 | `sha256:55a21c697a651cdff6ce8d64dd7c29dd2afaa329047b4ebd55c94497a411e7d5` |
| `CONTRACT_SCHEMA` | `contract:ofarm.runtimeproblem.v0.1` | `EXACT_BYTES_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 1,319 | `sha256:873dbeda2932d48a54e5d08d22f4031c6a86b44712a3cec85f1c1008f4d6e95b` |
| `TEMPORAL_GOVERNANCE_ARTIFACT` | `ofarm.temporal-carrier-matrix.adr0002.v0.1` | `OFARM_CANONICAL_JSON_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 9,504 | `sha256:c404c0cd1e08f389664b5381c2c038cf65bac9a3b725fc2b1882990636eb179b` |
| `TEMPORAL_GOVERNANCE_ARTIFACT` | `ofarm.temporal-carrier-selection.intervention.v0.1` | `OFARM_CANONICAL_JSON_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 1,814 | `sha256:373a5f402ad077039946c1dfe7b972e4382d3c6a6805fbf0b271e4a0bc729bf1` |
| `TEMPORAL_GOVERNANCE_ARTIFACT` | `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1` | `OFARM_CANONICAL_JSON_V1` | `GLOBAL_IMMUTABLE_CONTENT` | 9,614 | `sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1` |

The three governance artifacts must validate against their exact same-bundle
schema identities. The complete required bytes total 97,573 bytes. A digest-
only reference, missing row, substituted row, duplicate identity, wrong role,
wrong placement, wrong canonicalization, wrong byte length, wrong digest, or
schema-validation failure is refused.

## 7. Database read capability

### 7.1 Fixed function

Migration V10 adds exactly one externally named database capability:

```sql
ofarm.resolve_commit_operation_claim_draft_runtime_bundle_selection()
```

It has zero arguments. It is `STABLE`, `PARALLEL UNSAFE`, and
`SECURITY DEFINER`, is owned by `ofarm_owner`, uses only explicitly
schema-qualified objects, and fixes `search_path` to `pg_catalog, pg_temp`.
All privileges are revoked from `PUBLIC`; execute is granted only to
`ofarm_app` and `ofarm_worker`. The function itself also requires
`SESSION_USER` to be exactly one of those two login roles, so role membership
does not widen the callable set.

The function requires `READ COMMITTED`, obtains the tenant only through
`ofarm.current_tenant_id()`, and returns zero rows for an absent selection. It
does not accept even the fixed identity as an argument.

### 7.2 Narrow RLS addition

The selection table remains unavailable directly to application and worker
roles. V10 grants them no table privilege.

Because forced RLS also applies to the table owner, V10 adds two owner-facing,
`FOR SELECT`-only policies used by the security-definer function:

- one on `ofarm.tenant_command_runtime_bundle_selection`; and
- one on `ofarm.governed_write_batch`.

Each policy is true only when:

```text
SESSION_USER IN ('ofarm_app', 'ofarm_worker')
AND row.tenant_id = ofarm.current_tenant_id()
```

The selection policy also requires the fixed selection binding and command
identities. These policies do not grant `INSERT`, `UPDATE`, `DELETE`,
`TRUNCATE`, or direct `SELECT` to the session roles. The existing
selection-control owner policies remain byte-for-byte semantically unchanged.

No new policy is needed for RuntimeBundle relations. Application and worker
roles already have the exact production read privileges and tenant RLS needed
to load a bundle selected by the fixed function. V10 does not broaden those
grants.

### 7.3 One-statement observation

One SQL statement inside the function must:

1. resolve the protected current tenant and matching tenant reference;
2. compute the greatest visible committed tenant knowledge position;
3. read only the fixed selection row;
4. join the exact referenced activation batch on tenant, batch ID, selection
   position, and RuntimeBundle digest;
5. require the activation operation and fixed batch/request identifier shapes;
6. require all fixed binding and command identities; and
7. return the complete row plus `Kselection` only when every relationship is
   exact.

The result columns are closed to:

```text
tenant_id
tenant_ref
selection_binding_id
selection_binding_canonical_digest
command_id
command_binding_id
command_binding_canonical_digest
selection_batch_id
selection_knowledge_position
runtime_bundle_digest
selection_knowledge_cut
```

The statement must require:

```text
1 <= selection_knowledge_position <= selection_knowledge_cut
```

PostgreSQL `READ COMMITTED` gives the statement one snapshot. A concurrently
committing activation is therefore seen as either absent or as both its batch
and immutable selection. It cannot be returned partially.

The greatest visible batch position is the cut. `created_at`, transaction ID,
MVCC metadata, selection row order, or an application-supplied value may not be
used as a substitute.

### 7.4 Ordering guard and read neutrality

Resolution is valid only before the current UnitOfWork has a governed batch.
The UnitOfWork checks this first. The database function independently refuses
if the bound transaction already owns a governed batch row. Transaction ID is
used only for this ordering guard, never as knowledge authority.

The function performs no insert, update, delete, allocation, advisory lock,
row lock, notification, audit call, or retry. Ordinary MVCC relation locks
needed to execute `SELECT` do not become write or ordering authority.

## 8. RuntimeBundle reconstruction

After the fixed resolver returns one row, the private production selector must
perform this closed sequence:

1. require the exact row shape and built-in Python types;
2. require the returned tenant UUID to equal `TenantBinding.tenant_id`;
3. validate the stable tenant reference and all fixed identities;
4. validate positive bounded selection position and `Kselection` and their
   ordering;
5. load exactly the selected same-tenant `runtime_bundle` row;
6. require its stored digest, canonical document bytes, byte length, and
   `runtimebundle:<digest>` reference to be exact;
7. load its complete membership metadata in canonical role/logical-reference
   order;
8. reject zero, duplicate, malformed, or over-4,096 membership rows before
   loading content;
9. require the stored canonical bundle document to describe exactly those
   membership rows;
10. load each membership's bytes only from its declared global or tenant
    retained-content relation;
11. require one and only one content source, exact byte length, and exact
    SHA-256 for every component;
12. reconstruct every `RuntimeComponent` and then one `RuntimeBundle` from the
    retained bytes;
13. require reconstructed canonical bytes and digest to equal the stored
    bundle row;
14. if `RuntimeBundle.selected_tenant_ref` is not `None`, require it to equal
    the database tenant reference;
15. authenticate the fixed selection binding and require the exact 16-row
    command closure; and
16. construct one immutable success value.

The complete bundle is reconstructed, not just the 16 required components.
This preserves the existing RuntimeBundle model's cross-component validation.
Additional valid components remain inert for this command.

The loader first reads membership metadata and refuses if the sum of declared
component byte lengths exceeds 134,217,728 bytes. This selector-specific
128 MiB fail-closed ceiling prevents one selected bundle from forcing
unbounded process allocation. It is not a publication limit and does not make
size a selection authority. The fixed required closure is far below it.

Bundle and content reads may use statements after the selection/head statement
because the referenced bundle, memberships, and content are content-addressed
and mutation-refusing. V10 structural verification must continue to prove
those guarantees. A missing or differing later read is refusal, never a reason
to infer another bundle or retry selection.

## 9. Success and refusal types

### 9.1 Immutable success

`TrustedCommandRuntimeBundle` is a frozen, slotted value with exactly these
authoritative fields:

```text
tenant_id: UUID
tenant_ref: str
selection_binding_id: str
selection_binding_canonical_digest: str
command_id: str
command_binding_id: str
command_binding_canonical_digest: str
selection_batch_id: str
selection_knowledge_position: int
selection_knowledge_cut: int
runtime_bundle: RuntimeBundle
```

The RuntimeBundle object is the only bundle carrier. Its digest and canonical
document are not copied into independently mutable or potentially divergent
fields. Convenience read-only properties may delegate to the RuntimeBundle,
but they own no separate authority.

Constructing the dataclass directly must not bypass validation. Its constructor
is private to the module or its post-construction checks replay every invariant.
Tests must prove that malformed direct construction is refused.

### 9.2 Opaque internal refusal

All expected absence, database, row-shape, binding, visibility, bundle,
content, schema, and closure failures normalize to one internal exception and
one fixed outcome:

```text
RUNTIME_BUNDLE_SELECTION_REFUSED_NO_WRITE
```

The exception exposes no SQLSTATE, query, relation, tenant, digest, component,
path, credential, content, or nested exception detail. Expected failures are
raised without a public cause chain. The module emits no log, audit row,
receipt, or public `RuntimeProblem`.

Programming defects and process-level failures are not misreported as a
semantic refusal. They propagate to the existing UnitOfWork exception path,
which rolls back or discards the connection.

## 10. Tenant UnitOfWork state machine

The public UnitOfWork surface becomes exactly:

```text
binding
batch
begin_batch(request)
resolve_commit_operation_claim_draft_runtime_bundle()
```

It still exposes no connection, cursor, execute method, generic selector, or
raw SQL callback.

The selector state is closed:

```text
UNRESOLVED
  -> RESOLVING
      -> RESOLVED(result)
      -> REFUSED_ROLLBACK_ONLY

any state -> CLOSED when the context exits
```

Rules:

- the public resolver accepts no arguments;
- it requires an active UnitOfWork and no existing governed batch;
- the first call invokes the private callback at most once;
- success caches the exact object, and every later call in the same active
  UnitOfWork returns that same object by identity;
- expected refusal caches a terminal refusal and marks the UnitOfWork
  rollback-only;
- later calls after refusal raise the same opaque outcome without database
  access;
- `begin_batch()` after selector refusal is rejected, so caught refusal cannot
  fall back to a caller-selected digest;
- resolver use after any batch exists is refusal and makes the transaction
  rollback-only;
- re-entry while `RESOLVING` is refused;
- all UnitOfWork methods reject use after close; and
- a caught refusal followed by a normal context exit causes rollback, not
  commit.

Selector success does not silently rewrite or constrain the existing generic
`GovernedBatchRequest.runtime_bundle_digest`. Changing batch allocation or
creating the future selected-bundle command seam belongs to a later trust
boundary. Until that boundary exists, copying the returned digest into
`begin_batch()` does not give the request a `TrustedCommandRuntimeBundle`
authority claim.

The immutable values may remain inspectable in ordinary Python memory after
the context closes. Closed lifetime means they are no longer an accepted
authority: no API added here accepts a `TrustedCommandRuntimeBundle`, another
UnitOfWork cannot install one, and every operation on the owning UnitOfWork is
closed. Future authoritative consumers must remain inside that UnitOfWork and
must not accept the result as a caller argument.

## 11. Concurrency and transaction behavior

### 11.1 Concurrent activation

The activation batch and selection row commit in one existing control
transaction. The fixed statement snapshot sees neither row or both rows. An
absent result is cached as refusal; the same request never retries after the
activation commits. A later request may resolve it.

### 11.2 Later unrelated batch

If an unrelated batch commits after the resolver statement, the cached
`Kselection` does not change. A new UnitOfWork may observe a greater cut while
returning the same immutable selection. No old UnitOfWork refreshes.

### 11.3 Immutable content after the cut

The selected RuntimeBundle was sealed before its activation batch could
reference it. Its rows cannot be updated or deleted through supported
production authority. Later statements can therefore reconstruct that exact
content without changing what was visible at `Kselection`.

### 11.4 Database failure

A supported driver/database failure during lookup or content loading becomes
the opaque refusal and rollback-only state. If rollback cannot be proved, the
existing manager discards the connection. There is no selector retry loop and
no partial success object.

## 12. Falsifiable invariants

- **TRBS-001 — One fixed selection.** Only
  `ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1`
  can be resolved.
- **TRBS-002 — Bound tenant only.** The lookup tenant comes only from the
  installed `TenantBinding` and protected database context, and those values
  must agree.
- **TRBS-003 — No caller authority.** The public selector API has no tenant,
  Party, binding, command, digest, component, time, or knowledge-cut
  parameter.
- **TRBS-004 — Exact knowledge visibility.** The selection position is
  positive and no greater than same-snapshot `Kselection`; `Kselection` is not
  mislabeled as future `Kbefore`.
- **TRBS-005 — Atomic observation.** Concurrent activation is observed as
  absent or complete. One UnitOfWork never mixes snapshots or retries into a
  later state.
- **TRBS-006 — Exact sealed content.** The complete selected RuntimeBundle and
  every retained component are reconstructed and revalidated from production
  rows, within the closed resource ceiling, before success.
- **TRBS-007 — No inference.** Newest, sole, published, profile-listed,
  package order, timestamp order, UUID order, and caller assertion never
  select or replace a bundle.
- **TRBS-008 — Read neutrality.** Resolution creates no row, batch, knowledge
  position, advisory or row lock, isolated audit event, receipt, result, or
  output, and does not advance tenant knowledge.
- **TRBS-009 — Tenant isolation.** Tenant A cannot resolve, detect, or
  distinguish tenant B's selection or tenant-retained content.
- **TRBS-010 — Closed lifetime.** The result is cached in one active
  UnitOfWork, cannot be installed in another, and carries no authority after
  its owner closes.
- **TRBS-011 — Production reachability.** Acceptance and refusal are exercised
  through the real `ApplicationRuntime -> TenantUnitOfWork` graph and the real
  PostgreSQL application role/RLS boundary; worker execute/RLS posture is also
  verified.
- **TRBS-012 — Production/legacy firewall.** Production resolution imports no
  legacy Store, legacy RuntimeBundle repository, profile runtime, publisher,
  or selection-control adapter.
- **TRBS-013 — Internal refusal only.** This issue introduces no public reason
  code, response mapping, route, durable refusal record, or changed #192 audit
  behavior.

## 13. Acceptance and hostile evidence

### 13.1 Positive production-reachable cases

Using a disposable PostgreSQL 17 database and real provisioned roles, Phase B
must prove:

1. a fully valid bundle published and selected through existing fixture/control
   authority resolves through `ApplicationRuntime -> TenantUnitOfWork`;
2. every success field, `Kselection`, bundle byte, digest, membership, and
   required closure row is exact;
3. application and worker function calls require trusted binding;
4. direct application/worker selection-table reads and every mutation remain
   denied;
5. selection resolution leaves selection row count, governed batch row count,
   tenant head, and security-audit rows unchanged;
6. repeated resolution in one UnitOfWork returns the identical cached object
   without another SQL call;
7. a later unrelated committed batch changes only a new UnitOfWork's
   `Kselection`;
8. an exact activation retry remains idempotent and creates no new selection;
   and
9. unchanged `ApplicationRuntime` composition reaches the new selector while
   legacy composition cannot.

### 13.2 Hostile cases

Phase B must prove fail-closed behavior for:

- use before binding and use after UnitOfWork close;
- absent selection;
- tenant A selected while tenant B is unselected;
- attempted tenant, digest, binding, command, component, clock, and cut
  injection at every public surface;
- selection position zero, above `Kselection`, or unrelated to its activation
  row;
- wrong selection binding, command, command binding, canonical digest,
  activation operation, batch shape, request shape, tenant, or bundle digest;
- missing, duplicate, unsealed, cross-tenant, or digest-mismatched bundle;
- empty, missing, duplicate, substituted, malformed, oversized, wrong-role,
  wrong-placement, wrong-canonicalization, wrong-length, or unequal component
  membership/content;
- canonical bundle document mismatch;
- required governance instance/schema mismatch and every missing or substituted
  member of the fixed 16-row closure;
- a valid bundle with unrelated extra components, proving extras neither
  select a bundle nor become command requirements;
- a bundle whose model-derived tenant reference differs from the bound tenant;
- concurrent activation at the resolver statement boundary;
- a batch allocated before resolver use;
- caught refusal followed by a fallback `begin_batch()` attempt;
- database failure before, during, and after selection and content reads;
- repeated use after success, repeated use after refusal, and re-entrant use;
- attempted result installation or transfer between UnitOfWorks;
- execution by `PUBLIC`, owner membership through another login, readiness,
  binder, publisher, selection controller, and unbound app/worker sessions;
- unchanged pre-tenant audit rows and tenant head on every refusal;
- production imports of the selection-control adapter, publisher, profile
  runtime, legacy Store, or legacy RuntimeBundle repository; and
- any new route, output, materialization, profile, manifest, capability, or
  public error mapping.

Corruption-only cases may use a disposable test database with constraints or
triggers deliberately removed after provisioning. Such setup is test authority
only and must not create a production repair or bypass path.

## 14. Smallest coherent architecture and elegance audit

### 14.1 Production modules

Phase B adds one module:

```text
kernel/tenant_command_runtime_bundle_selector.py
```

It owns the fixed pins, artifact authentication, closed result/refusal types,
database row parsing, selected-bundle loading, reconstruction, and closure
validation. It exposes only the types and private resolver needed by
`tenant_uow.py`. It does not expose a generic repository or query service.

`kernel/tenant_uow.py` owns the no-argument public method, private callback,
cache, rollback-only state, and lifecycle checks. The manager builds the
callback from its already private connection and verified binding.

`kernel/application_runtime.py` remains unchanged. Its existing construction
of `TenantUnitOfWorkManager` makes the new method production reachable. A test,
not another composition layer, proves that graph.

### 14.2 Closed source budgets

Architecture conformance changes the existing ceilings to:

| Production area | Maximum physical lines |
| --- | ---: |
| `kernel/tenant_command_runtime_bundle_selector.py` | 420 |
| `kernel/tenant_uow.py` | 520 |
| tenant transaction group containing both modules | 940 |
| `kernel/application_runtime.py` | unchanged at 230 |

The global maximum of 80 lines per production function remains unchanged. A
need to exceed these ceilings is a design review event, not a reason to relax
them silently.

### 14.3 Elegance audit

- Public selection methods: one fixed no-argument method.
- Database selection functions: one fixed no-argument function.
- Selection inputs: zero.
- New roles or logins: zero.
- New mutable production tables: zero.
- New runtime modules: one.
- New success carriers: one frozen value.
- New refusal outcomes: one opaque internal value.
- Selection attempts per UnitOfWork: at most one.
- Knowledge cuts returned per success: one immutable `Kselection`.
- RuntimeBundle sources of truth: existing production relations and model.
- Control-path imports or edits: zero.
- Legacy/profile/runtime-route imports: zero.

The selector is capability-specific because a generic selection repository
would create an extension surface and invite caller-controlled binding,
command, or digest lookup. The result embeds one RuntimeBundle rather than
copying its digest and document into competing fields.

An independent fixed-artifact check in the read path is intentional. Sharing
it by importing the control adapter would collapse production read and
administrator write reachability. Moving the control validator in this PR
would cross the PR boundary. Only immutable top-level pins are mirrored, and
conformance ties both verifiers to the same exact artifact.

## 15. Pull request boundary

### 15.1 Phase A head

Before approval, the draft implementation PR may change only:

```text
docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selector_Admission_RFC_v0_1.md
```

It remains Draft. Phase A contains no migration, runtime code, test, generated
inventory, active contract, or implementation effect.

### 15.2 Exact Phase B allowlist

After exact approval of decision version 1, the same draft PR may change only:

```text
docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selector_Admission_RFC_v0_1.md
kernel/migrations/0010_tenant_command_runtime_bundle_selector.sql
deployment/postgresql/migration_sets.py
deployment/postgresql/provisioning.py
deployment/postgresql/README.md
kernel/tenant_command_runtime_bundle_selector.py
kernel/tenant_uow.py
kernel/tests/test_tenant_command_runtime_bundle_selector.py
kernel/tests/test_postgresql_tenant_command_runtime_bundle_selector.py
kernel/tests/test_tenant_uow.py
kernel/tests/test_application_runtime.py
kernel/tests/test_migration_sets.py
kernel/tests/test_postgresql_provisioning.py
kernel/tests/test_temporal_contract_governance.py
kernel/tests/test_rewrite_architecture_check.py
conformance/temporal_contract_candidate_check.py
conformance/rewrite_architecture_check.py
conformance/review_baseline_test_inventory.json
```

The RFC may receive only approval/review/head traceability updates that do not
change the approved decision. The inventory file may receive only canonical
mechanical changes caused by the admitted tests.

No other path is allowed. If implementation proves another path is required,
stop before editing it and return to design review. In particular, Phase B
does not edit `kernel/application_runtime.py`, any active or candidate contract,
the selection-control adapter, RuntimeBundle publisher, profile runtime,
legacy code, route, authorization, security-audit, output, deployment secret,
or role-definition source.

### 15.3 One-boundary confirmation

The whole future implementation remains inside one primary trust boundary:
read-only, tenant-bound resolution and full validation of an already persisted
fixed command RuntimeBundle selection at `Kselection`.

Migration, UnitOfWork wiring, tests, and conformance travel together only
because they are necessary to implement and prove that one read boundary.
They do not change selection write custody, principal resolution,
authorization, key custody, audit persistence, or command execution.

## 16. Conformance and verification design

### 16.1 Migration and provisioning

V10 must:

- preflight the exact V9 verifier and migration prefix;
- add only the function and two select-only owner policies described above;
- keep the existing role graph and direct table ACLs closed;
- advance the exact structural verifier to V10 only after every new catalog
  object, owner, definition, policy, ACL, RLS posture, and function grant is
  exact;
- update `CURRENT_MIGRATION_SET`, provisioning phase classification, and
  PostgreSQL documentation mechanically; and
- remain replayable only as the next migration after exact V9.

Provisioning tests must report exact PostgreSQL 17 structure, migration head,
row count, applied-prefix digest, structural digest, policy fingerprints,
routine fingerprint, and ACL inventory.

### 16.2 Architecture conformance

`rewrite_architecture_check.py` must:

- admit the new selector module to the production graph and budgets above;
- require its reachability from `kernel.application_runtime` through
  `kernel.tenant_uow`;
- require its absence from legacy production roots;
- preserve the exact UnitOfWork public surface and private slots;
- preserve the raw connection/cursor/execute firewall;
- forbid imports of the control adapter, publisher, profile runtime, legacy
  Store, and legacy RuntimeBundle repository; and
- continue to reject route or public API reachability for this capability.

### 16.3 Temporal conformance

`temporal_contract_candidate_check.py` must:

- extend the migration classifier from exact V7/V8/V9 to exact
  V7/V8/V9/V10;
- classify the existing selection storage/control pair unchanged;
- classify exactly one new production selector module and fixed V10 read seam;
- authenticate the new module's binding pins against the exact source artifacts
  and the unchanged control adapter pins without importing the adapter at
  runtime;
- require production reachability of the selector and non-reachability of the
  control adapter;
- keep active manifest, profile, catalog, and capability surfaces closed; and
- reject any second selector, generic lookup, caller parameter, legacy import,
  or changed fixed identity.

### 16.4 Phase A checks

Before every Phase A commit:

```sh
python3.12 conformance/ofarm_pkg_contract_check.py
git diff --check
```

Phase A review must also prove:

- the branch base is the named current-main commit;
- only this RFC differs from that base;
- the named pull request is Draft and points to the reviewed exact head;
- all material design decisions are closed;
- no demonstrated Phase A Blocker remains; and
- the live approval card matches this committed contract.

Expensive hosted baselines are not started merely to review documentation.

### 16.5 Phase B checks

Phase B uses exact CPython 3.12.13 and a disposable PostgreSQL 17 target. At
minimum it must run:

```sh
python3.12 --version
python3.12 -m pytest -q \
  kernel/tests/test_tenant_command_runtime_bundle_selector.py \
  kernel/tests/test_postgresql_tenant_command_runtime_bundle_selector.py \
  kernel/tests/test_tenant_uow.py \
  kernel/tests/test_application_runtime.py \
  kernel/tests/test_migration_sets.py \
  kernel/tests/test_postgresql_provisioning.py \
  kernel/tests/test_temporal_contract_governance.py \
  kernel/tests/test_rewrite_architecture_check.py \
  kernel/tests/test_tenant_command_runtime_bundle_selection.py
python3.12 -m pytest -q kernel/tests/
python3.12 conformance/temporal_contract_candidate_check.py
python3.12 conformance/rewrite_architecture_check.py
python3.12 conformance/ofarm_pkg_contract_check.py
git diff --check
```

The exact test inventory must be regenerated by its canonical repository
command and reviewed as a mechanical diff. Final evidence reports exact test
counts, PostgreSQL version, V10 head and digests, reviewed commit, changed-file
boundary, and any skipped or unavailable check.

Hosted baseline and final merge authorization remain separate later gates.
Passing tests does not approve a design change or authorize merge.

## 17. Invariant-to-code-to-test traceability

| Invariants | Owning seam | Required evidence |
| --- | --- | --- |
| TRBS-001–003 | fixed V10 function, fixed selector, no-argument UoW method | exact signature/AST checks, role calls, and caller-injection refusal |
| TRBS-004–005 | same-statement selection/head resolver and one-attempt cache | position bounds, concurrent activation, no-retry, and later-request tests |
| TRBS-006–007 | production loader, `RuntimeComponent`, `RuntimeBundle`, authenticated 16-row closure | complete reconstruction, corruption, extra-component, size, and inference matrix |
| TRBS-008 | read-only SQL and UoW refusal handling | before/after row counts, head, locks, audit rows, and SQL-shape checks |
| TRBS-009 | protected current tenant, function policies, existing RuntimeBundle RLS | app/worker same-tenant success and cross-tenant indistinguishability |
| TRBS-010 | UoW state/cache/finish rules | same-object cache, closed use, rollback-only, caught-refusal, and transfer tests |
| TRBS-011 | unchanged `ApplicationRuntime` graph and real provisioned roles | production composition acceptance/refusal plus worker function evidence |
| TRBS-012 | architecture and temporal import closure | exact production/legacy graph checks and forbidden-import cases |
| TRBS-013 | opaque refusal and unchanged outer systems | no public mapping, route, receipt, durable refusal, or audit-row changes |

## 18. Closed decisions, review disposition, and provisional record

### 18.1 Closed decisions

- The public method and database function are capability-specific and take no
  arguments.
- The runtime cut is named `Kselection`, not `Kbefore`.
- Selection and head are observed in one PostgreSQL statement snapshot.
- The V10 security-definer function is executable only by exact app/worker
  sessions and receives two narrow owner select policies.
- App and worker receive no direct selection-table privilege.
- Bundle content is loaded from existing production relations under existing
  privileges and RLS.
- The complete selected RuntimeBundle is reconstructed; the exact 16-row
  command closure is then checked.
- Additional valid bundle components are allowed but inert.
- Total selected component bytes have a 128 MiB fail-closed read ceiling.
- Expected failures collapse to one internal refusal and make the UnitOfWork
  rollback-only.
- One UnitOfWork makes at most one selection attempt and caches success or
  refusal.
- The existing generic batch API is not redesigned in this boundary.
- `ApplicationRuntime`, selection control, publisher, authorization, audit,
  profile, legacy, route, and output code remain unchanged.
- The production reader independently authenticates the fixed artifact; it
  does not share code by crossing into the control adapter.

### 18.2 Open decisions

None.

### 18.3 Review disposition

- Demonstrated Phase A Blockers: pending exact-head design review.
- Follow-ups: future governed command/batch consumption, authorization #175,
  durable post-binding refusal, and later valid-time/dual-cut work each retain
  their own boundaries.
- Preferences: none recorded.

### 18.4 Provisional design record

Not provisional.

The vocabulary, identities, result fields, cut meaning, database capability,
RLS posture, lifecycle, failure outcome, resource ceiling, file allowlist, and
tests are closed. A material change requires a new decision version and another
exact approval.

## 19. Phase gates and approval boundary

This Phase A RFC records a proposed decision only. It grants no implementation,
merge, deployment, role, data, command, or operational authority.

The required order is:

1. commit this RFC alone on the named branch;
2. open one Draft implementation PR for issue #363;
3. bind that PR number and exact Phase A head into this RFC and PR description;
4. review that exact head to zero demonstrated Blockers;
5. display a live decision card that matches the committed RFC;
6. receive the designated architect's exact approval as the entire visible
   user message;
7. only then add Phase B implementation to the same draft PR;
8. verify implementation and review feedback inside this boundary; and
9. request a separate exact-head merge authorization later.

The only Phase A approval sentence is:

```text
I approve OFARM2 decision OFARM2-ISSUE363-TRUSTED-COMMAND-RUNTIME-BUNDLE-SELECTOR-001 version 1.
```

An earlier `go`, paraphrase, approval of another version, approval before the
named Draft PR is bound, or approval embedded in a larger message does not
authorize Phase B. Approval is revocable until implementation starts. Final
merge authorization is not implied.

## 20. Stop conditions

Stop before editing and propose a separate prerequisite, follow-up, or stacked
PR if implementation requires:

1. changing the existing selection record, activation function, activation
   behavior, controller, or selection-control adapter;
2. importing the selection-control adapter or moving shared procedural
   validation across the production-read/control-write boundary;
3. publishing, activating, replacing, or repairing a real RuntimeBundle
   selection;
4. adding a role/login or granting direct/general selection, tenant-registry,
   or catalog table access;
5. changing tenant binding, principal resolution, authorization, credentials,
   key custody, security audit, or transaction authentication;
6. accepting a caller-selected tenant, Party, binding, command, digest,
   component set, clock, profile, or knowledge cut;
7. changing generic governed-batch allocation or treating copied result bits as
   transferable authority;
8. introducing a public reason code, route, result, receipt, output, durable
   refusal, or isolated post-binding audit event;
9. changing a profile, manifest, ActiveArtifactSet, capability, materializer,
   qualification, replay, correction, supersession, or delivery path;
10. activating a valid-time/domain query or changing frozen temporal contract
    bytes;
11. using the legacy Store, legacy RuntimeBundle repository, or closed PR
    assumptions from #283, #305, or #306;
12. changing any path outside the exact allowlist in section 15;
13. exceeding the closed source or resource ceilings; or
14. changing any material decision in this RFC after approval.

Issue #363 closes only this trusted persisted-selection read boundary. It does
not close #176. After merge, #176 must be re-audited before choosing the next
single-boundary Delivery child.
