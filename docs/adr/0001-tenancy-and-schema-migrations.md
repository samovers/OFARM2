# ADR 0001: Tenancy and schema-migration architecture

- Status: Accepted for implementation
- Date: 2026-07-10
- Decision issue: GitHub #169
- Parent: GitHub #167
- Depends on: GitHub #168
- Implementation owners: GitHub #173 and #174
- Additional prerequisites for #174: GitHub #171 and the #184 semantic stop
  described below

## Scope and authority

This record freezes an implementation architecture before persistence and
transaction hardening begins. It implements the accepted Kernel storage posture
in DECISIONS.md D10; it does not amend OFARM law, contracts, relationship law,
manifests, active artifact sets, profile activation, or capability claims.

Nothing is deployed. Existing databases are development and conformance
fixtures, so the first implementation may replace them. No production
compatibility layer, backfill, dual schema, or legacy identifier translation is
required.

## Context

The current store is a single-tenant prototype:

- only the canonical record relation carries a tenant reference, and that
  column silently defaults to the Slovenian demo tenant;
- identifiers, idempotency, locks, graph references, derived keys, traces, and
  exports are otherwise database-global or unqualified;
- no row-level security policy or production database-role separation exists;
- the application owns an ambient connection rather than a request-scoped
  UnitOfWork;
- application startup executes a mutable, idempotent DDL file and then
  bootstraps data;
- there is no numbered migration ledger or database-schema readiness contract.

The per-record contract schema version and schema digest describe the JSON
contract used to validate a record. They are not the PostgreSQL schema version
and cannot satisfy database readiness.

## Decision summary

Use shared PostgreSQL with tenant-qualified relational keys, forced row-level
security, a trusted authentication-to-tenant binding whose lifetime is one
transaction, and immutable numbered migrations run separately from application
startup.

The application handles exactly one data-owner tenant per UnitOfWork. Tenant
data never refers directly to another tenant's data. Sharing is a governed
authorization inside the data owner's tenant, not a cross-tenant graph join.

## Vocabulary

**Tenant-owned** means that a row belongs to exactly one data-owner tenant and
must carry an immutable internal tenant identifier.

**Globally governed** means immutable content or control-plane state shared by
tenants. Ordinary global content contains no tenant truth, is not writable by
the application role, and changes only through a governed control-plane or
release operation. The principal-binding bridge named below is the sole initial
global-to-tenant control-plane reference; it is not global content.

**Derived/cache** means recomputable acceleration state. It is not authoritative,
but it remains tenant-qualified and isolated because it can disclose tenant
truth.

**Operational metadata** means durable runtime or release bookkeeping. Tenant-
bearing operational metadata is tenant-qualified and isolated; database-global
release metadata is accessible only to the roles that need it.

**TenantBinding** is the verified database context containing at least the
internal tenant identifier, external tenant reference, authenticated Party
reference, issuer, subject, immutable binding-version identity and digest, and
authoritative lifecycle-head identity and digest. It exists only after the
hardened binder verifies a transaction-bound TenantCapability.

**TenantCapability** is a short-lived, signed, single-use proof minted by the
trusted authentication boundary. Its signing authority is unavailable to the
application database role. It binds one immutable principal-binding version and
its authoritative lifecycle head to one database transaction challenge and
cannot be used to select or rebind another tenant.

**UnitOfWork** is one checked-out connection and one database transaction for one
request, governed command, or explicitly assigned background operation.

**Governed write batch** is the durable identity of all records, edges, gate
outcomes, receipts, and other consequences emitted atomically by one governed
command.

## Relation classification

Classification does not waive isolation. Every tenant-bearing relation,
including derived and operational relations, receives forced row-level security
and tenant-qualified keys.

### Current relations

| Relation | Classification | Frozen target rule |
|---|---|---|
| kernel_record | Tenant-owned | Primary identity is (tenant_id, record_id). There is no tenant default. Every emitted record carries its governed write-batch identity. Package or global content may not be mixed into this relation. |
| kernel_edge | Tenant-owned | The edge, source, and destination share tenant_id. Both endpoints have composite foreign keys. The edge carries the batch that emitted it. Promotion reachability additionally requires edge, trace, and emitted record to share one batch. |
| kernel_gate_log | Operational metadata, tenant-scoped and durable | Every entry carries tenant_id, batch identity, and request identity. It remains append-only audit evidence and is not disposable logging. |
| kernel_idempotency | Operational metadata, tenant-scoped and durable | Its unique command identity is (tenant_id, authenticated_principal_ref, governed_operation, caller_key). Its durable result reference stays in the same tenant. |
| derived_materialization | Derived/cache | All keys start with tenant_id. Basis, snapshot, context, and supersession references are same-tenant composite references. Deleting it must not delete its proof or source truth. |
| derived_dependency_index | Derived/cache | Dependency sources and materialization keys are tenant-qualified. It may not invalidate or reveal another tenant. Polymorphic references become typed and constrained rather than unverified text. |
| reference_snapshot_data | Derived/cache, with a rebuildability precondition | Primary identity is (tenant_id, snapshot_ref, data_family), with a same-tenant snapshot reference. It is deletable only after durable source bytes and deterministic rebuild are proven; #171 and #185 own that closure. |
| runtime_trace | Operational metadata, tenant-scoped and durable | Primary identity is (tenant_id, trace_id). Every trace carries its write-batch identity, remains append-only, and is not treated as a disposable cache. |
| export_artifact | Tenant-owned | Primary identity is (tenant_id, artifact_ref). The metadata/output-receipt reference is same-tenant. Document content is never placed in globally shared storage. |

There is no globally governed database relation in the current schema. Package
schemas and other repository files are global inputs, not database relations.

### Required support relations

| Future relation | Classification | Frozen target rule |
|---|---|---|
| tenant_registry | Globally governed | Maps an internal immutable UUID tenant_id to a unique external tenant_ref, active state, and a database-assigned advisory-lock key. Application DML is forbidden. |
| principal_binding | Globally governed immutable authorization versions | One immutable candidate version maps normalized (issuer, subject) to (tenant_id, party_ref), carries a version identity and digest plus validity metadata, and has a composite target-Party foreign key. Repeated principal keys are expected; no mutable lifecycle state or partial ACTIVE uniqueness lives here. It is the only initial global authority relation allowed to reference a tenant-owned Party. |
| principal_binding_lifecycle | Globally governed append-only authorization authority | A digest-chained stream of ACTIVATE, REVOKE, EXPIRE, and SUPERSEDE acts names immutable binding versions, the prior lifecycle head, effective and decision data, accountable control identity, and reason. These acts, together with immutable versions, are the sole source for current and historical binding state. |
| principal_binding_current | Optional derived/disposable global control projection and reservation | A unique (issuer, subject) row points to the computed active version and lifecycle head, or records the computed inactive state. It serializes transitions and accelerates lookup, but is rebuildable and never authoritative. |
| tenant_binding_context | Protected transaction operational metadata | Stores the one-use challenge and verified TenantBinding for one backend transaction. Only hardened owner functions may read or write it; the application role has no table privileges. |
| schema_migration | Database-global operational metadata | Append-only ledger of version, filename, SHA-256, application/release identity, and applied time. Application access is read-only for readiness. |
| governed_write_batch | Tenant-owned | Primary identity is (tenant_id, batch_id). It anchors the transaction's command identity and the records, edges, traces, gate entries, and receipts emitted by that command. |
| kernel_record_reference | Tenant-owned relational enforcement carrier | Normalizes governed references extracted from immutable JSONB payloads without changing those payloads. Owner and tenant targets use composite tenant keys; global-content targets use a distinct constrained lane. |

Any later relation must be classified before its migration is accepted. A future
RuntimeBundle or other shared-content relation may be globally governed only if
its bytes are immutable and content-addressed, it contains no tenant truth, and
identifier equality verifies the canonical bytes.

### RuntimeBundle placement prerequisite

#171 must land before #174 freezes the initial migration. It must classify every
currently bootstrapped descriptor, policy, profile instance, validator/adapter,
query/output plan, and selected reference-source identity as either:

- immutable globally governed RuntimeBundle content in the content carrier
  selected by #171; or
- explicit tenant-owned selection, activation, or context state that references
  the exact RuntimeBundle digest.

Immutable global package/reference bytes may not remain mixed into the
tenant-owned canonical record relation merely because the prototype bootstraps
them there today. Conversely, tenant activation or context state may not be
silently relabelled global. #171 must publish the placement map and equality
rules before #174 cuts 0001; #174 refuses to guess. This prerequisite changes no
manifest, active artifact set, profile activation, contract, or capability
claim.

## Tenant identity and trusted context

The database uses an internal immutable UUID tenant_id for relational identity.
The contract-visible tenant_ref remains an external string mapped uniquely by
the global tenant registry. Business and OFARM references remain tenant-local:
their complete relational identity is always (tenant_id, local reference).
Embedding a tenant name in a string does not qualify a key.

### Governed principal source

The authoritative production source for tenant selection is the combination of
immutable principal-binding versions and their append-only lifecycle acts. A
`principal_binding` version records the normalized issuer and subject,
tenant_id, party_ref, validity bounds, immutable version identity and digest,
and any predecessor version. It has no mutable state. Its target Party has a
composite (tenant_id, party_ref) foreign key.

`principal_binding_lifecycle` is the authoritative state machine. Every
immutable act is one of ACTIVATE, REVOKE, EXPIRE, or SUPERSEDE and contains the
normalized principal key, affected version or predecessor/successor versions,
monotonic stream sequence, prior-act identity and digest, effective time,
decision time, accountable control identity, reason, and its own digest. Unique
stream sequence and prior-head constraints prevent a fork. Folding the accepted
act chain over immutable versions determines the binding at any lifecycle cut;
the projection is never consulted for historical reconstruction.

The current binding is the version left ACTIVE by that fold, within its
immutable validity bounds, and not subsequently revoked, expired, or
superseded. Zero active versions, a broken or ambiguous act chain, more than one
active candidate, an inactive tenant, an inactive Party, or an invalid validity
window denies context. Token roles never synthesize a Party, tenant, OFARM role,
or authority grant.

`principal_binding_current` is only an optional, disposable locator and
concurrency reservation. It has one UNIQUE (issuer, subject) slot containing the
computed active version identity/digest and lifecycle-head identity/digest, or
the computed inactive state. The unique slot does not confer authority. Missing,
stale, corrupt, or mismatched projection data never authorizes a request and can
be dropped and rebuilt deterministically from immutable versions and acts.

Creation, activation, revocation, expiry, supersession, or target replacement
uses one hardened identity-control transition. It first acquires the unique
normalized (issuer, subject) reservation, reconstructs and validates the
authoritative lifecycle head from immutable versions and acts, and checks its
expected-head precondition. In one database transaction it inserts any new
immutable binding version, appends exactly one lifecycle act, and updates the
current projection to the resulting version and head. Any projection update
failure rolls back the version and act. A privileged deterministic rebuild uses
only immutable versions and acts and produces the same projection; it cannot
repair authority by inventing or editing history.

A revocation, expiry, or replacement makes every capability naming the old
version or prior lifecycle head unusable for later UnitOfWork binding. It does
not rewrite earlier receipts or acts. A historical authorization decision is
reconstructed as of its recorded lifecycle cut using only immutable versions
and acts, never the then-current projection.

The initial architecture supports exactly one active tenant and Party per
(issuer, subject). Multi-tenant principals, tenant switching, and user-selected
tenant candidates are unsupported. Supporting them requires a separate decision
covering selection, disclosure, confused-deputy risk, and receipt semantics.
There is no production default.

The identity-control writer may invoke only the hardened lifecycle transition;
it has no direct DML on versions, acts, or projection and may not read tenant
truth. The hardened binder reads immutable versions and lifecycle acts, and may
use the projection only as a candidate locator whose version and head must equal
the authoritative fold. It may not mutate binding authority. The application,
worker, readiness, and end-user roles receive no direct SELECT or DML on binding
versions, lifecycle acts, or current projection.

### Unforgeable transaction binding

In production, #172's authentication boundary verifies issuer, audience,
signature, algorithm, expiry, not-before time, key identity, and the exact
(issuer, subject) identity. It does not pass a raw tenant identifier to SQL.
After #173 begins one UnitOfWork on one checked-out backend, binding proceeds as
follows:

1. A hardened owner function creates a cryptographically random one-use
   challenge bound to the current backend identity and full transaction
   identity in protected transaction context.
2. The trusted authentication boundary mints a short-lived TenantCapability
   containing that challenge, binder audience, issuer, subject, immutable
   binding-version identity and digest, lifecycle-head act identity and digest,
   tenant_id, party_ref, issued/expiry times, and a unique nonce. The capability
   is signed by a key unavailable to the application database role.
3. A schema-qualified SECURITY DEFINER binder with a fixed trusted search_path
   verifies the signature, audience, expiry, backend/transaction challenge,
   nonce, exact immutable version bytes and digest, and the authoritative
   lifecycle head and currentness reconstructed from immutable acts. It may use
   `principal_binding_current` to locate a candidate only when its version and
   head exactly equal that reconstruction; a missing or mismatched projection
   causes refusal or a separate privileged deterministic rebuild, never
   authorization. The binder also verifies the active tenant and active Party,
   then inserts exactly one verified TenantBinding into the protected context
   relation.
4. A uniqueness constraint makes the first successful bind final for that
   transaction. A second call, reset, principal change, tenant change, or
   capability replay refuses. Commit or rollback ends the context; a capability
   from another transaction or backend cannot be reused.

The signing or capability-minting authority is outside the application database
role and the SQL-injection boundary. A fully compromised authentication signer
remains an explicit privileged-boundary compromise, not an RLS guarantee.

RLS policies never read a caller-writable custom setting. They call only a
schema-qualified protected current-tenant function which reads the verified
context row for the current backend transaction and returns one tenant_id or
fails closed. Raw SET, SET LOCAL, set_config, environment values, session
variables, a shadow function/schema, a request body, farm reference, path,
arbitrary header, token role, and the current demo constant cannot establish or
change context.

Development and test modes use a separate explicit fixture capability issuer
that is structurally unavailable in production. A scheduler or worker receives
an explicit, signed, transaction-bound capability for its governed job; it may
not sweep tenants using an unscoped transaction.

Repository APIs receive a bound UnitOfWork and do not accept an optional tenant,
consult a module constant, open an ambient connection, or fall back to an
unbound store. Liveness, readiness, migration, and infrastructure provisioning
use separate database paths that cannot query tenant relations through the
application role.

## Identifier and uniqueness namespaces

- Every tenant-owned primary key, unique constraint, and foreign key begins
  with tenant_id.
- record_id, trace_id, request_id, batch_id, artifact_ref, and other authored
  references are tenant-local even if their textual form appears globally
  distinctive.
- Globally governed identifiers are globally unique and, for content, are
  collision-resistant digests whose canonical bytes are also compared.
- Principal identity is normalized (issuer, subject). Immutable binding versions
  may repeat that pair. Only the disposable current projection/reservation has
  UNIQUE (issuer, subject); serialized lifecycle transitions and the
  authoritative act fold, not that projection constraint, establish at most one
  active version. A token role or caller tenant string is never part of the
  identity.
- Idempotency identity is exactly (tenant_id,
  authenticated_principal_ref, governed_operation, caller_key). #178 adds the
  canonical semantic request digest, complete durable response, retention, and
  named-conflict behavior without changing this namespace.
- Materialization and dependency uniqueness starts with tenant_id. Digest
  equality alone never proves key equality; the canonical key is compared.
- Cache keys, import identities, output references, and operational request
  identities are tenant-qualified.
- Database-generated surrogate numbers may be globally allocated internally,
  but they convey no authorization and cannot replace a tenant-qualified
  relational key.

The tenant registry assigns every tenant a stable, globally unique signed
64-bit advisory-lock key. A separately reserved global migration-lock key cannot
collide with tenant keys. Human-readable tenant references and truncated hashes
are not advisory-lock identities. Only the protected wrappers defined below may
use these keys. Any later resource-lock family must reserve a disjoint namespace
before use.

## Foreign keys, graph rules, and sharing boundary

Every reference to tenant-owned data repeats tenant_id and uses a composite
foreign key. This applies to graph endpoints, carrier records, idempotency
results, materialization basis/snapshot/context records, dependency records,
reference-snapshot data, runtime receipts, and export metadata.

Contract JSON payloads remain byte-for-byte contract-shaped; this ADR does not
add tenant fields or relational metadata to them. The normalized record-
reference carrier gives their governed references a relational enforcement
surface. Each row contains the owner tenant and record, governed reference role
and JSON pointer, stable ordinal, extraction-rule version/digest, emitting batch,
and exactly one of:

- a same-tenant target record identified by (tenant_id, target_record_id); or
- an immutable global-content kind and content identity.

The carrier rows are emitted atomically with the immutable owner record. A
protected extraction verifier compares the exact carrier set and digest against
the versioned extraction rules pinned by the RuntimeBundle; the application
cannot omit a payload reference, add a hidden reference, or declare its own
target kind. Same-tenant targets receive composite foreign keys. The global lane
can reference only #171-approved immutable content and has an exclusive shape
constraint. Unknown lanes or paths refuse.

#184 owns the complete semantic reference, relationship-kind, source/target-kind,
and cardinality matrix. #174 may create the neutral carrier, tenant key, batch
key, exclusivity checks, and already-settled endpoint constraints, but it may
not infer full JSON paths, target kinds, edge meanings, or cardinalities. If the
#184 extraction/matrix artifact is not accepted and RuntimeBundle-pinned, #174
stops before claiming or implementing complete carrier/reference enforcement.

The database enforces these structural graph invariants:

1. Every edge row and both endpoint rows exist in the same tenant.
2. Every edge is bound to the governed write batch that emitted it.
3. A promotion-reachability edge, its PromotionTrace source, and its newly
   emitted destination share the same tenant and governed write batch.
4. Other relationship kinds may point to an earlier same-tenant batch only when
   the accepted relationship-kind and cardinality matrix allows it.
5. Unknown edge kinds, incompatible source/destination kinds, dangling
   endpoints, cross-tenant endpoints, and future identifiers fail closed.
6. Authoritative graph deletion does not cascade. Correction remains
   append-only supersession.

The relationship-kind and cardinality vocabulary remains existing Kernel law
and the closure work owned by #184. This ADR adds relational isolation and
integrity; it does not invent new relationship semantics.

There are no direct cross-tenant relational references in the first deployment.
A SharingGrant, its grantor, grantee Party, target scope, and shared artifact
must resolve inside the data-owner tenant. #177 evaluates the complete grant
inside the same UnitOfWork. A grant authorizes a bounded read or delivery; it
does not move ownership, manufacture authority, expose the tenant's raw graph,
or create a mutable object shared by two tenants.

Cross-tenant sharing or transfer is unsupported. Adding it requires a separate
ADR and explicit governed delivery semantics, such as a frozen copy and receipt.
It may not be introduced as a generic edge or an unqualified Party reference.

Tenant data may reference immutable globally governed content, such as an exact
contract or RuntimeBundle digest. Global content never refers back to tenant
rows, and the application cannot mutate it. The globally governed immutable
principal-binding versions are the sole initial exception: they form a
protected authorization bridge with an explicit composite target-Party foreign
key, not shared content and not a general cross-tenant query path. Lifecycle
acts and the current projection name those versions but add no second tenant-
truth path.

## Database roles and row-level security

Use a dedicated, fully qualified application schema such as ofarm. Revoke
CREATE on public and revoke unnecessary PUBLIC privileges on the database,
schemas, tables, sequences, and functions.

The role model is:

- ofarm_owner: NOLOGIN owner of schemas, tables, policies, and functions;
- ofarm_migrator: release-only credentials allowed to take the migration lock
  and apply reviewed DDL through the owner role;
- ofarm_app: non-owner application role with NOBYPASSRLS, no DDL, no owner or
  migrator membership, and only required DML;
- ofarm_worker: same isolation posture as the application, with an explicit
  TenantBinding per job;
- ofarm_binder: NOLOGIN capability used only by the hardened binder/current-
  context functions to read immutable binding versions, authoritative lifecycle
  acts, optional current projection, tenant, Party, and transaction context; the
  application may EXECUTE those functions but cannot SET ROLE to this role;
- ofarm_identity_writer: control-plane-only capability that may execute the
  principal-binding lifecycle transition but has no direct DML on binding
  versions, lifecycle acts, or projection, no tenant-truth read role, and no
  application membership;
- ofarm_readiness: read-only access to migration metadata and no access to
  tenant data, or an equivalently restricted readiness grant.

Enable and FORCE row-level security on every tenant-bearing relation. Policies
use only the protected current-tenant function for both USING and WITH CHECK.
They never consume a raw custom setting. Missing, invalid, expired, replayed, or
multiply bound context denies or raises; it never selects all tenants. Append-
only restrictions remain additional constraints and do not substitute for RLS.

Normal functions execute as the caller. Any unavoidable SECURITY DEFINER
function has a fixed trusted search_path, schema-qualified objects, no
caller-controlled dynamic SQL, minimal ownership, explicit EXECUTE grants, and
adversarial tests. The challenge, binder, current-context, and lock wrappers are
the named exceptions. Their definitions and owners are migration-checksummed.
Triggers and constraint functions include tenant and batch in every lookup.

Direct SQL using the application role remains subject to forced RLS, composite
constraints, verified context, and append-only rules. The application role
cannot read or write protected context, binding versions, lifecycle acts,
current projection, tenant lock keys, or capability-verification keys; cannot
assume any privileged role; and cannot execute raw advisory-lock functions. End
users and support users never receive
application or migration credentials. Superusers, database administrators,
migrators, identity-control writers, backup readers, and a fully compromised
capability signer are outside the RLS protection boundary; access to those
capabilities requires separate operational controls and audit.

## Protected advisory locks

Cluster provisioning revokes PUBLIC and application EXECUTE on every
pg_advisory_lock, pg_try_advisory_lock, pg_advisory_unlock, and transaction-lock
overload. The application and worker roles cannot choose a numeric lock key,
take a session lock, try a migration lock, or unlock a protected lock.

Two schema-qualified SECURITY DEFINER wrappers are allowed:

- the tenant-write wrapper accepts no tenant or lock-key argument, requires a
  verified TenantBinding, derives the unique key from its tenant registry row,
  and acquires only a transaction-scoped lock; and
- the migration wrapper is executable only by the migrator, accepts no caller
  key, derives the reserved global key internally, and acquires only a
  transaction-scoped lock.

Both wrappers have a fixed trusted search_path, fully qualified calls, exact
owners and EXECUTE grants, and no dynamic SQL. There is no application-visible
unlock wrapper; commit or rollback releases the lock.

## One-time infrastructure provisioning

Database and role creation precede numbered schema migrations. A reviewed,
versioned infrastructure step run by a database administrator creates the
database, the empty ofarm and ofarm_private namespaces, NOLOGIN owner and binder
roles, migrator/application/worker/readiness identities or grants, the identity-
control writer, exact memberships, and initial PUBLIC revocations. Application
startup and the migration runner do not create or repair their own cluster
roles.

Provisioning is verify-or-create only for a provably new target. On an existing
target it compares role attributes, memberships, namespace owners, database
owner, and grants to the declared specification. Any unexpected privilege,
owner, member, object, or role attribute is drift and refuses; provisioning
does not silently widen or reconcile it. Credentials and signing keys remain
outside repository fixtures and migration SQL.

## Immutable migration baseline

The authoritative migration set lives under kernel/migrations with four-digit,
gap-free, immutable filenames. Because there is no deployment, #174 creates one
hardened kernel/migrations/0001_initial.sql containing the target schema from
this ADR only after #171 supplies the reviewed RuntimeBundle placement map. #174
may then progress the neutral carrier and non-semantic isolation work, but 0001
and #174 cannot be accepted as complete reference enforcement until #184
supplies the extraction/kind/cardinality semantics required by the stop above.
It does not preserve the unsafe prototype as a compatibility layer. Development
and conformance databases are dropped and recreated.

Once the baseline is accepted, an applied migration file is never edited,
renamed, reordered, or deleted. Every schema change appends a new migration.
The existing mutable schema.sql ceases to be authoritative; #174 may remove it
or generate a convenience snapshot from the migration set, but runtime code
must never execute that snapshot.

A separate migration command, release job, or operator action:

1. connects using migrator credentials unavailable to the application;
2. takes the reserved global transaction-scoped migration lock;
3. verifies the provisioned database, roles, namespace ownership, and grants;
4. verifies migration filenames are ordered and gap-free;
5. verifies every previously applied filename and SHA-256 against the immutable
   local migration set;
6. applies the next migration and appends its ledger row in one database
   transaction;
7. releases the lock on commit or rollback.

Non-transactional migrations are forbidden in the initial posture. If one ever
becomes necessary, a later ADR must define its resumability, dirty-state
handling, and recovery before it can be added.

The migration ledger is append-only. At minimum it stores version, filename,
SHA-256, applied-at diagnostic time, release/application build identity, and an
execution identifier. Missing, duplicate, reordered, unknown, checksum-
mismatched, or partially applied history is dirty and fails closed.

A missing ledger is fresh only when the provisioned target namespaces are
provably empty of application relations, views, materialized views, sequences,
types, routines, policies, triggers, and migration-owned extensions, and the
catalog shows exactly the declared empty namespace owners and grants. The empty
schemas created by infrastructure provisioning are allowed; any application
object without a ledger is not.

On that one proven-empty path, 0001 creates the ledger and target objects and
appends its own checksum row atomically. If the ledger is missing while any
target object exists, the database is dirty and the runner refuses. It never
adopts, fingerprints as a baseline, repairs, drops, or wraps an untracked schema
with IF NOT EXISTS behavior.

## Startup, readiness, compatibility, and rollback

The application build carries the exact expected latest migration version and
ordered migration-set digest. Lifespan initialization performs a read-only
verification of the ledger before constructing tenant repositories or serving
governed traffic. It never creates, alters, drops, repairs, or bootstraps schema
objects.

Schema mismatch prevents readiness. A dedicated readiness check reports only
the supported/observed version state without tenant counts, identifiers, or
records. Liveness checks only process health. An empty database, an older or
newer schema, a dirty history, an unavailable ledger, or a checksum mismatch
never becomes ready and never triggers DDL.

The first deployment has an exact-version compatibility window: one application
build supports exactly one ordered migration set. There is no N-minus-one
support, dual-read/write path, compatibility view, or backfill. Deployment runs
the migration release step, then starts the matching application build. If a
future availability requirement needs rolling mixed versions, an explicit
expand/contract ADR and bounded compatibility window must precede it.

There are no down migrations for durable truth. Before first deployment,
rollback means deleting and recreating the disposable development database.
After deployment:

- a failed transactional migration rolls back both DDL and ledger append;
- a successful migration is corrected by a new forward migration; or
- operational disaster recovery restores a tested whole-database backup and
  the exactly matching application build together.

Starting an older binary against a newer schema is not rollback; it is a
readiness failure. Destructive forward migrations require a verified backup and
restore rehearsal, but this ADR does not claim that those operations already
exist.

## Threat model

The protected assets are tenant truth, authority and sharing records, runtime
evidence, derived state, frozen outputs, command receipts, and schema integrity.
The attacker may control request fields, identifiers, retry keys, payload
references, timing, concurrency, and malformed SQL inputs. The attacker may
trigger exceptions and pool reuse. The model also covers accidental unqualified
queries and direct SQL under the application role.

| Threat | Required control |
|---|---|
| Forged tenant in a body, route, header, farm reference, or environment default | Only a signed, challenge-bound TenantCapability verified against an immutable binding version and the authoritative lifecycle head can create TenantBinding; selectors are untrusted and there is no production default. |
| Raw SET, SET LOCAL, set_config, reset, shadow object, second bind, or cross-backend capability replay | RLS ignores caller settings and reads protected one-bind-per-transaction context through fixed-schema owner functions. Capability audience, signature, nonce, backend, transaction, immutable version digest, and lifecycle-head digest are verified. |
| Missing, malformed, expired, revoked, superseded, forked, or ambiguous principal binding | The protected binder reconstructs currentness from immutable versions and lifecycle acts and fails before any tenant query; repositories require a bound UnitOfWork. |
| Deleted, stale, forged, or corrupt principal-binding current projection | Projection data is only a candidate locator. The binder compares it with the authoritative lifecycle fold and refuses on absence or mismatch; only a privileged deterministic rebuild from versions and acts may restore it. |
| Edited or deleted binding version or lifecycle history, or concurrent activation attempts | Direct DML is denied, versions and acts are immutable, lifecycle streams are serialized by the unique principal reservation and expected-head checks, and current/historical state ignores projection as authority. |
| Context surviving connection-pool reuse after success, rollback, failure, cancellation, or retry | SET LOCAL-equivalent transaction lifetime, rollback-on-return, and same-backend alternating-tenant tests. |
| Unqualified reads, joins, subqueries, aggregates, prepared statements, or background scans | Forced RLS on every tenant-bearing relation and explicit tenant assignment for workers. |
| Direct SQL inserts another tenant_id or attempts to disable row security | WITH CHECK, NOBYPASSRLS non-owner role, FORCE RLS, composite constraints, and no DDL privileges. |
| Owner, SECURITY DEFINER, search_path, function, trigger, or PUBLIC privilege bypass | Separate NOLOGIN owner, hardened functions, fully qualified SQL, revoked defaults, and role-capability tests. |
| Cross-tenant or dangling graph construction, including a future-ID/two-transaction promotion exploit | Same-tenant composite FKs plus same-batch promotion reachability and deferred constraints. |
| JSONB payload reference omitted from relational enforcement or assigned a guessed kind | Exact RuntimeBundle-pinned carrier extraction is verified; #174 stops before complete semantics unless #184 supplies the accepted path/kind/cardinality matrix. |
| Cross-tenant idempotency replay or uniqueness existence oracle | Tenant/principal/operation command namespace and tenant-prefixed unique indexes. |
| Advisory-lock collision, raw session lock, attacker-selected key, unlock, or migration-lock attempt | Raw advisory functions are denied; protected no-key wrappers derive disjoint keys and acquire transaction locks only. |
| Materialization, dependency, cache, trace, gate-log, error, or frozen-output leakage | Tenant qualification and RLS apply regardless of authoritative status; errors and readiness expose no tenant data. |
| Mutation, substitution, or tenant-table mixing of shared global content | #171 placement is prerequisite to 0001; application read-only privileges plus content digest and canonical-byte equality verification apply. |
| Concurrent, partial, reordered, missing, edited, future, or ledgerless non-empty migration history | Global migration lock, transactional application, immutable checksums, exact readiness, catalog-emptiness proof, and fail-closed dirty detection. |
| Database administrator, migrator, backup, or trusted-binder compromise | Explicitly outside RLS; separate credentials, release controls, audit, and backup governance are required operational controls. |

## Executable adversarial verification plan

#173 and #174 turn this plan into tests using the real PostgreSQL roles and the
real ASGI/application topology, not mocks.

### Tenant context and pool reuse

1. Create tenants A and B with deliberately identical local record, request,
   artifact, materialization, and caller idempotency references.
2. With no context, malformed context, or an expired/invalid TenantBinding,
   tenant SELECTs return nothing or error and writes fail.
3. Reuse the same physical backend for A then B after commit, explicit rollback,
   application exception, cancellation, serialization failure, and retry.
   Each request sees only its own tenant.
4. Run concurrent A and B requests through the ASGI pool and prove authority,
   reads, writes, receipts, and errors contain no other-tenant reference.
5. Prove a repository cannot run without the caller's UnitOfWork or open an
   ambient connection.
6. Under raw application SQL, try SET, SET LOCAL, set_config, RESET, environment
   values, and a tenant-shaped custom variable. None establishes or changes
   context, and an invalid value fails rather than widening a policy.
7. Try a second bind in the same transaction, a different principal/tenant
   capability, a used nonce, a capability from another backend/transaction, and
   a capability after commit/rollback. Every rebind or replay refuses.
8. Pre-create same-named functions, operators, relations, and schemas in every
   caller-writable search path. The fixed-schema challenge, verifier, context,
   and policy functions cannot be shadowed.
9. Revoke, supersede, or expire the active binding, or deactivate its tenant or
   Party, before a new UnitOfWork. Binding refuses. A capability pinning the old
   version or lifecycle head also refuses after any later lifecycle transition.
   Prove a token role and caller tenant string cannot create an alternative
   mapping.
10. Race two ACTIVATE or replacement transitions for one normalized (issuer,
    subject). The unique projection reservation serializes them, expected-head
    validation permits only one authoritative active result, and a principal
    spanning two tenants remains unsupported.
11. Under every non-owner role, attempt UPDATE or DELETE of an immutable binding
    version or lifecycle act and direct INSERT of a lifecycle act. Every attempt
    fails; only the hardened transition can append a valid act.
12. Delete the current projection row, then make it stale and corrupt its
    version/head fields under a privileged test fixture. The binder never
    authorizes from it. A privileged rebuild from immutable versions and acts
    deterministically recreates the same unique projection.
13. Resolve current state with the projection absent, and reconstruct state at
    each earlier lifecycle cut after later revocation and supersession. Results
    come only from immutable versions and acts and are unchanged by any
    projection contents.

### RLS, direct SQL, keys, and graph

1. Under the application role and tenant A context, exercise raw SELECT,
   aggregate, join, subquery, prepared-statement, INSERT, UPDATE, DELETE, COPY,
   and ON CONFLICT paths against rows from both tenants.
2. Prove tenant A cannot supply tenant B's identifier, alter row_security,
   create or alter objects, write global governance state, or call an unsafe
   owner function.
3. Prove identical tenant-local identifiers coexist across A and B while
   same-tenant duplicates fail at the intended named constraints.
4. Attempt dangling, cross-tenant, unknown-kind, wrong-kind, wrong-cardinality,
   and future-ID edges. All fail without partial writes.
5. Attempt promotion reachability using a trace or destination from another
   tenant, another batch, or an earlier transaction. All fail at commit.
6. Prove allowed earlier-batch same-tenant evidence, review, lineage, and
   materialization references succeed only when the accepted relationship
   matrix permits them.
7. Prove a sharing grant cannot resolve a grantee or artifact in another tenant
   and cannot expose an unscoped graph.
8. For every #184-approved JSON reference path, omit, add, reorder, duplicate,
   retag, or cross-tenant-target a normalized carrier row. Exact-set validation
   or composite constraints refuse the write. Before the #184 matrix exists,
   prove the implementation stops instead of guessing path/kind/cardinality.

### Operational and derived isolation

1. Reuse the same caller key in both tenants and prove independent command
   identities; reuse it with another principal or governed operation and prove
   a distinct namespace.
2. Prove materialization, dependency, reference-data, trace, gate-log, and
   export queries remain tenant-isolated even when local references and digests
   match.
3. Hold tenant A's advisory lock and prove tenant B is not blocked; prove a
   second writer for A is serialized and all locks release on rollback.
4. Delete and rebuild only those derived rows whose immutable inputs make the
   rebuild complete; until source-byte durability is proven, reference-data
   deletion must be refused.
5. Under application and worker roles, call every raw advisory lock, try-lock,
   unlock, session-lock, transaction-lock, and migration wrapper overload.
   Raw/keyed calls and migration locking are denied. The no-argument tenant
   wrapper derives only the verified bound tenant and releases on transaction
   end.
6. Cold-bootstrap after #171 and prove globally governed bundle bytes are
   outside tenant-owned records while tenant selection/context rows reference
   the exact bundle digest.

### Migrations and readiness

1. Provision a new target once and verify exact database owner, NOLOGIN owners,
   role attributes/memberships, namespace owners, PUBLIC revocations, and empty
   target catalogs before applying migrations.
2. Apply the migration set to that proven-empty database and verify exact
   version, checksums, roles, grants, forced RLS, constraints, functions, and
   indexes.
3. Re-run provisioning and the migration runner and prove both are verified
   no-ops, not silent repairs.
4. Test missing, duplicate, reordered, renamed, edited, unknown-future,
   partially applied, and checksum-mismatched migrations; each fails closed.
5. Delete or omit the ledger in both an empty target and targets containing one
   relation, view, sequence, type, routine, policy, trigger, or migration-owned
   extension. Only the provably empty target is fresh; every non-empty target
   refuses without adoption or cleanup.
6. Inject a DDL failure and prove both schema changes and the ledger append roll
   back. Run two migration processes and prove the global lock serializes them.
7. Start the application against empty, old, exact, newer, dirty, and
   unavailable schemas. Only exact becomes ready, and catalog snapshots prove
   startup performed no DDL.
8. Prove application and readiness roles cannot provision, apply, repair, or
   downgrade a migration.
9. Restore a test backup with its matching application build and execute the
   documented recovery check before any production-readiness claim.

## Alternatives considered

### Database per tenant

This gives the strongest physical isolation but multiplies provisioning,
migration, connection, backup, and fleet-observability work. It is rejected for
the first deployment. It remains an option for a future regulatory or scale
requirement.

### Schema per tenant

This reduces shared-table exposure but multiplies schema migrations and makes
pooling and search_path handling dangerous. It is rejected.

### Shared tables with application filters only

A missed predicate, direct SQL path, maintenance query, or new repository can
bypass application conventions. It is rejected in favor of composite keys plus
forced RLS.

### One database role per tenant

Role and pool cardinality become operationally expensive, and a shared service
still needs a trusted role-selection mechanism. It is rejected in favor of a
shared non-owner application role and transaction-local context.

### Globally unique business references

This makes tenant isolation depend on string-generation discipline, creates
unnecessary namespace coupling, and can reveal existence through uniqueness
errors. It is rejected; relational identity is tenant-qualified.

### Session-level tenant context

It can survive commit and leak through connection reuse. It is rejected; tenant
context is transaction-local.

### Raw transaction-local tenant setting

SET LOCAL is transaction-scoped but remains caller-writable: direct SQL under
the application role can choose another tenant or shadow the setting consumed by
a policy. A raw tenant GUC or set_config value is rejected. Transaction lifetime
is necessary but not sufficient; RLS consumes only verified protected context.

### Mutable binding row or partial ACTIVE index as authority

Changing lifecycle state on a current binding row makes authoritative history
mutable. Keeping versions immutable while placing a partial UNIQUE index on
rows whose stored state is ACTIVE prevents replacement because the superseded
row remains ACTIVE in storage. Both designs are rejected. Immutable versions and
append-only lifecycle acts are authority; uniqueness belongs only to the
disposable current reservation/projection.

### Application-selected advisory keys

Allowing the application to call raw advisory functions can create session-lock
leaks, cross-tenant blocking, migration-lock interference, or attacker-chosen
serialization. It is rejected in favor of no-key protected wrappers.

### Unverified JSON reference sidecar

An application-populated sidecar can omit or misclassify payload references and
turn a foreign-key claim into convention. It is rejected. The normalized carrier
must match the complete #184-governed, RuntimeBundle-pinned extraction set.

### General cross-tenant edges

They collapse ownership, RLS, sharing, deletion, and revocation boundaries. They
are rejected. The initial system supports governed sharing only within the
data-owner tenant.

### Opportunistic startup DDL or generated ORM migrations

This grants runtime DDL authority and hides drift behind IF NOT EXISTS behavior.
It is rejected in favor of reviewed immutable SQL migrations and a separate
runner.

### Mutable historical migrations and down migrations

Editing history destroys reproducibility; generic down migrations can erase or
reinterpret durable truth. Both are rejected. Recovery is forward correction
or whole-database restore.

### An N-minus-one compatibility window now

Nothing is deployed, so dual behavior would add risk without preserving a real
consumer. It is rejected. The first window is exact-version only.

## Consequences and follow-on ownership

This decision deliberately makes the current implementation fail its future
tenancy and migration tests until the dependent tickets land.

- #172 supplies explicit production authentication, immutable principal-binding
  versions, the append-only lifecycle transition and disposable projection
  rebuild, and the trusted TenantCapability issuer/verifier boundary.
- #173 supplies the pool, UnitOfWork, one-use challenge/binder call, protected
  transaction context, and write-batch allocation.
- #174 supplies the one-time provisioning specification, verifies provisioned
  roles, and creates the hardened initial migration, RLS, composite keys, neutral
  reference carrier, foreign keys, graph constraints, protected lock wrappers,
  runner, and readiness enforcement. It must not bypass the #184 stop.
- #171 is a prerequisite to #174: it supplies immutable RuntimeBundle content,
  equality verification, and the global-versus-tenant placement map required
  before 0001 is frozen.
- #177 completes the within-tenant sharing and output-authorization gate.
- #178 implements content-bound, result-complete command idempotency inside the
  namespace frozen here.
- #184 supplies the complete reference extraction and semantic relationship
  matrix without changing the structural isolation rules in this ADR. Until
  that matrix is accepted, #174 cannot invent or claim complete payload-
  reference kind/cardinality enforcement.
- #185 must make scheduled reference source bytes durable before their parsed
  data can honestly be treated as disposable cache.

No implementation ticket may claim that closing these persistence mechanics
changes OFARM law, activates a profile, or proves a higher capability.

## Acceptance traceability

| Issue #169 criterion | ADR section |
|---|---|
| Classify every table | Relation classification |
| Trusted immutable principal source, non-authoritative current projection, transaction context lifetime, and no production default | Governed principal source; Unforgeable transaction binding |
| Identifier, idempotency-key, advisory-lock, and uniqueness namespaces | Identifier and uniqueness namespaces; Protected advisory locks |
| Tenant-qualified FKs, graph rules, cross-tenant references, and sharing | Foreign keys, normalized reference carrier, graph rules, and sharing boundary |
| Roles, forced RLS, migration privileges, and direct-SQL posture | Database roles and row-level security; One-time infrastructure provisioning |
| Immutable numbered baseline, rollback, compatibility, and readiness | One-time infrastructure provisioning; Immutable migration baseline; Startup, readiness, compatibility, and rollback |
| Startup verifies schema and performs no opportunistic DDL | Startup, readiness, compatibility, and rollback |
| Threat model and adversarial pool/join verification | Threat model; Executable adversarial verification plan |

## Validation for this documentation decision

- Compare the nine CREATE TABLE declarations in kernel/schema.sql with the
  current-relation inventory above; each must be classified exactly once.
- Verify every acceptance criterion maps to a section in the traceability table.
- Run the package contract check and profile extraction-consistency check.
- Run the repository whitespace/diff check.
- Confirm the change contains documentation only.
