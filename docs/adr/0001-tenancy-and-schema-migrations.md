# ADR 0001: Tenancy and schema-migration architecture

- Status: Accepted for implementation
- Date: 2026-07-10
- Decision issue: GitHub #169
- Parent: GitHub #167
- Depends on: GitHub #168
- Implementation coordination: GitHub #172, #173, #174, and #192
- Additional prerequisite for #174: GitHub #171. GitHub #184 follows the
  neutral structural carrier supplied by #174 and owns semantic reference
  kind/cardinality enforcement; #174 may not claim that later semantic closure.
- Temporal/audit-boundary coordination: GitHub #170 and ADR 0002
- Non-forking recovery design (not supported in V1): GitHub #193
- Pre-tenant audit runtime/operations owner: GitHub #192, consuming the bounded
  outcomes and storage supplied by GitHub #172, #173, and #174

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

**Pre-tenant operational security metadata** means bounded diagnostic evidence
created before a trusted TenantBinding exists. It is neither tenant-owned truth
nor globally governed shared content. It carries no tenant knowledge position,
cannot authorize or reconstruct tenant state, and is visible only to the
separate security-operations boundary defined below.

**TenantBinding** is the verified database context containing at least the
internal tenant identifier and registration digest, external tenant reference,
authenticated Party reference and exact `ofarm.party.v0.1` record-kind
identity/record identity/schema digest/payload digest, issuer, subject,
equality-policy identity, immutable binding-version identity and digest, and
authoritative lifecycle-head identity and digest. It exists only after the
hardened binder verifies a transaction-bound TenantCapability.

**TenantCapability** is a short-lived, signed, single-use proof minted by the
trusted authentication boundary. Its signing authority is unavailable to the
application database role. It binds one immutable principal-binding version and
its authoritative lifecycle head, exact equality policy, immutable tenant
registration, and pinned Party record-kind/identity/schema/payload digests to one
database transaction challenge and cannot be used to select or rebind another
tenant.

**UnitOfWork** is one checked-out connection and one database transaction for one
trusted-tenant request, governed command, or explicitly assigned background
operation. The isolated pre-tenant audit transaction below is not a tenant
UnitOfWork and cannot use tenant repositories.

**Governed write batch** is the tenant-scoped durable identity of all records,
edges, gate outcomes, receipts, and other consequences emitted atomically by
one governed command after trusted tenant binding. A pre-tenant security event
is explicitly outside every governed write batch.

## Relation classification

Classification does not waive isolation. Every tenant-bearing relation,
including derived and operational relations, receives forced row-level security
and tenant-qualified keys.

### Current relations

| Relation | Classification | Frozen target rule |
|---|---|---|
| kernel_record | Tenant-owned | Primary identity is (tenant_id, record_id). There is no tenant default. Every emitted record carries its governed write-batch identity. Tenant-neutral package/global content may not be mixed into this relation; a package-authored tenant-scoped instance enters only as a governed row for its exact tenant. |
| kernel_edge | Tenant-owned | The edge, source, and destination share tenant_id. Both endpoints have composite foreign keys. The edge carries the batch that emitted it. Promotion reachability additionally requires edge, trace, and emitted record to share one batch. |
| kernel_gate_log | Operational metadata, tenant-scoped and durable | Every entry carries tenant_id, batch identity, and request identity. It remains append-only audit evidence and is not disposable logging. |
| kernel_idempotency | Operational metadata, tenant-scoped and durable | Its unique command identity is (tenant_id, authenticated_principal_ref, governed_operation, caller_key). Its durable result reference stays in the same tenant. |
| derived_materialization | Derived/cache | All keys start with tenant_id. Basis, snapshot, context, and supersession references are same-tenant composite references. Deleting it must not delete its proof or source truth. |
| derived_dependency_index | Derived/cache | Dependency sources and materialization keys are tenant-qualified. It may not invalidate or reveal another tenant. Polymorphic references become typed and constrained rather than unverified text. |
| reference_snapshot_data | Derived/cache, with a rebuildability precondition | Primary identity is (tenant_id, snapshot_ref, data_family), with a same-tenant snapshot reference. It is deletable only after durable source bytes and deterministic rebuild are proven; #171 and #185 own that closure. |
| runtime_trace | Operational metadata, tenant-scoped and durable | Primary identity is (tenant_id, trace_id). Every trace carries its write-batch identity, remains append-only, and is not treated as a disposable cache. |
| export_artifact | Tenant-owned | Primary identity is (tenant_id, artifact_ref). The metadata/output-receipt reference is same-tenant. Document content is never placed in globally shared storage. |

At the #169 review baseline there was no globally governed content relation in
the prototype schema. #171 adds one such target carrier,
`runtime_content_blob`, solely for immutable tenant-neutral bytes. The
tenant-specific RuntimeBundle receipt and membership relations remain
tenant-owned; their placement is frozen below and #174 must reproduce it in
the initial migration rather than preserve the prototype's unqualified tables.

### Required support relations

| Future relation | Classification | Frozen target rule |
|---|---|---|
| tenant_registry | Globally governed immutable V1 registry | Maps an internal immutable UUID tenant_id to one unique, bytewise-equal external tenant_ref, a row digest, and a database-assigned advisory-lock key. V1 has no mutable active flag, tenant retirement transition, or tenant eligibility lifecycle. Direct DML is forbidden; one hardened insert-only registrar creates rows. |
| principal_binding | Globally governed immutable authorization versions | One immutable candidate version maps the exact-policy (issuer, subject) bytes to (tenant_id, party_ref), pins the immutable tenant-registry digest and exact ACTIVE Party record identity/schema/payload digests, and carries an equality-policy identity, version identity/digest, and validity metadata. Repeated principal keys are expected; no mutable lifecycle state or partial ACTIVE uniqueness lives here. It is the only initial global authority relation allowed to reference a tenant-owned Party. |
| principal_binding_lifecycle | Globally governed append-only authorization authority | A digest-chained stream of ACTIVATE, REVOKE, EXPIRE, and SUPERSEDE acts names immutable binding versions, the prior lifecycle head, effective and decision data, accountable control identity, and reason. These acts, together with immutable versions, are the sole source for current and historical binding state. |
| principal_binding_current | Optional derived/disposable global control projection and reservation | A unique (equality_policy, issuer, subject) row points to the computed active version and lifecycle head, or records the computed inactive state. It serializes transitions and accelerates lookup, but is rebuildable and never authoritative. |
| tenant_binding_context | Protected disposable transaction operational metadata | An UNLOGGED migration-owned relation stores the one-use challenge and verified TenantBinding for exactly one database-derived backend identity and full xid8. Exact backend-start/full-transaction matching makes a physically retained row unusable after commit, rollback, backend restart, or pool reuse. Only hardened functions may read or write it; the application role has no table privileges. |
| runtime_content_blob | Globally governed immutable tenant-neutral content | Stores only exact tenant-neutral bytes under a closed content class and canonicalization identity. Primary identity is the full content digest; an equal digest is reusable only after exact class, canonicalization, byte-length, and byte equality. It has no tenant, Party, farm, activation, selection, batch, knowledge, bundle, or component back-reference. |
| runtime_tenant_content_blob | Tenant-owned immutable RuntimeBundle content | Primary identity is (tenant_id, content_digest). It retains exact canonical bytes for tenant-scoped activation/context instances and selected tenant reference data. Every key and reference is tenant-qualified, forced RLS applies, and an equal digest within one tenant is reusable only after exact class, canonicalization, byte-length, and byte equality. Bytes are never promoted or deduplicated into the global carrier merely because another tenant has the same digest. |
| runtime_bundle | Tenant-owned immutable runtime-selection receipt | Primary identity is (tenant_id, bundle_digest). Its canonical receipt binds that tenant, the exact closed component inventory, every global content identity, and every tenant-scoped active-instance/reference-selection identity and digest. It carries the governed batch that created it. It is append-only, forced-RLS protected, and cannot be selected before trusted tenant binding. |
| runtime_bundle_component | Tenant-owned immutable RuntimeBundle membership | Primary identity is (tenant_id, bundle_digest, component_role, logical_ref). A closed storage-lane discriminator and exactly-one target bind each member either to one global `runtime_content_blob` digest or to one same-tenant `runtime_tenant_content_blob` composite key; unverified polymorphic text is forbidden. Membership is exact, append-only, forced-RLS protected, and cannot point into another tenant. |
| operational_security_event | Database-global operational security metadata, explicitly non-tenant | Append-only, bounded pre-tenant failure events plus audit-access, retention, and declared-gap maintenance events for this lane. It carries no tenant_id, tenant_ref, Party/farm/role identity, governed batch, knowledge position, or request-supplied attribution. It lives only in the separately provisioned audit PostgreSQL service's protected `ofarm_security` schema and is never read as tenant history. |
| operational_security_quota_bucket | Disposable non-tenant operational security control state | One fixed database-time bucket per provisioned producer/component records accepted and overflow counts plus marker state. Only hardened audit functions mutate it. It contains no request, tenant, principal, correlation, or evidence data, cannot authorize anything, and is deleted after its bucket is closed and the corresponding overflow marker commits. |
| schema_migration | Database-global operational metadata | Append-only ledger of version, filename, SHA-256, application/release identity, and applied time. Application access is read-only for readiness. |
| governed_write_batch | Tenant-owned | Primary identity is (tenant_id, batch_id). It anchors the transaction's command identity and the records, edges, traces, gate entries, and receipts emitted by that command. |
| kernel_record_reference | Tenant-owned relational enforcement carrier | Normalizes governed references extracted from immutable JSONB payloads without changing those payloads. Owner and tenant targets use composite tenant keys; global-content targets use a distinct constrained lane. |

Any later relation must be classified before its migration is accepted. No
additional RuntimeBundle relation or other content carrier may be globally
governed merely because it is immutable or content-addressed. Global placement
also requires an accepted tenant-neutral content class, no tenant truth or
tenant back-reference, exact canonical-byte verification, and a release-owned
write path unavailable to tenant application roles.

### Pre-tenant operational security-audit lane

ADR 0002 establishes the ordering boundary: tenant knowledge begins only after
the hardened binder has verified the transaction-bound TenantCapability and
installed one trusted TenantBinding. A durable failure before that point cannot
enter `kernel_gate_log`, `runtime_trace`, `governed_write_batch`, or any other
tenant relation. The first implementation therefore uses a separately
provisioned and resource-bounded audit PostgreSQL service/database, with the
dedicated `ofarm_security.operational_security_event` relation, rather than a
default, claimed, inferred, or attacker-selected tenant. It shares no database,
WAL, volume, connection pool, owner, backup, or runtime credential with tenant
storage. A same-cluster schema or database does not satisfy this isolation.

The relation has a closed, migration-owned shape. A pre-tenant failure row
contains only:

- a cryptographically random event UUID generated by the trusted producer,
  before delivery, and a database-generated diagnostic `observed_at` instant;
- closed event-kind, producer/component, and safe-reason classes;
- one fixed-length keyed digest of a high-entropy, server-generated
  correlation value, with its HMAC domain and non-secret key version; and
- immutable event-format, redaction-policy, and retention-policy identities,
  a database-derived `purge_after` instant, and a database-derived canonical
  SHA-256 `append_input_fingerprint` used only for exact retry comparison.

Maintenance kinds use the same core envelope and only their migration-owned
typed extension: `AUDIT_ACCESS` binds a closed purpose, exact query-function and
time/result ceiling fingerprint; `AUDIT_RETENTION` binds the database cutoff and
deleted count; gap/overflow markers bind a bounded interval plus a count or
`COUNT_UNKNOWN`. Check constraints forbid an extension on the wrong kind. There
is no generic attribute, message, or details carrier. Correlation HMAC/domain/key
fields are required for a pre-tenant failure and forbidden for maintenance
kinds, whose identifiers and typed values are generated inside the hardened
control/retention functions.

V1 has no general evidence digest or arbitrary evidence field. Credentials,
identities, network values, paths, and other request data are not HMAC
preimages. The only allowed digest preimage is the high-entropy correlation
value created inside the trusted producer. That value is digested inside the
producer's isolated key boundary and never stored or transmitted raw to SQL,
database/access logs, APM, traces, queues, dead letters, crash reports, or
metrics. Domain separation and key rotation are fixed by the redaction policy;
digest keys are unavailable to database, application, worker, readiness,
tenant, reader, and retention roles.

The database validates digest length, HMAC domain, and known key version but
cannot recompute a producer-held HMAC. A compromised authorized producer can
therefore forge a correctly shaped diagnostic event within its own allowlist.
That limitation is explicit: the lane is tamper-resistant against ordinary
roles and cross-producer impersonation, not an authority ledger or proof that a
network event occurred.

HMAC rotation never rewrites an event. Accepted HMAC domains/key versions are a
migration-checksummed allowlist, and #192 runtime readiness verifies exact
equality with the isolated key service before enabling ingest. Readers never
receive keys. The key service destroys a version no later than the greatest
`purge_after` stamped on a row naming it, even if a failed purge leaves the row
present; purge failure separately disables ingest/readiness until repaired. If
the required key service is unavailable, the append follows the audit-
unavailability posture below rather than accepting an unkeyed value or
extending key lifetime silently.

Event IDs are server generated but never request supplied. Reusing an event ID
is allowed only for a retry after an ambiguous commit. The append function
computes an append-input fingerprint over the retry-invariant event ID, derived
producer/component, allowed event/reason class, correlation HMAC domain/key
version/value, fixed format/redaction/retention policy identities, and the
complete canonical kind-specific typed extension; the fingerprint binds explicit
extension absence for a pre-tenant failure. It excludes database-generated
`observed_at`, `purge_after`, quota counters, and other insert results. An exact
repeat returns the original committed identity, while any mismatch refuses. No
wall clock, request value, or tenant identifier participates in deduplication.

The function checks an existing event ID before applying current policies. An
exact retry compares against the stored append-input fingerprint and returns the
original row even after clock advance or a later policy/key rotation; it never
re-stamps the row. A new ID must use the currently active policy/domain/key
version. A retired version remains accepted only for exact retry until its last
row expires, then is removed and destroyed under the rule above.

Producer and component derive from exact `session_user` through an immutable
provisioning map; `current_user` inside SECURITY DEFINER is not attribution.
Each workload has a distinct LOGIN identity, receives a direct function grant
through membership in the audit-ingest capability granted with `INHERIT TRUE`,
`SET FALSE`, and `ADMIN FALSE`, and cannot share a pooled login with another
producer class. The migration owns a producer-to-reason allowlist. A compromised
producer may fabricate or flood only its own bounded allowed classes; it cannot
impersonate another component, choose attribution or retention, read or mutate
existing events, access tenant data, or make an event authoritative.

The producer map, producer-to-reason allowlist, event format, redaction policy,
and retention calculation are migration-checksummed constants/functions, not
mutable or unclassified policy tables. V1 names redaction policy
`CORRELATION_HMAC_ONLY_V1` and retention policy `SECURITY_DIAGNOSTIC_30D_V1`.
Its sole initial HMAC domain is `OFARM_PRETENANT_CORRELATION_V1` with key version
`1`. The database sets `purge_after = observed_at + interval '30 days'`.
Changing a domain, accepted key version, or either policy requires a reviewed
forward migration and applies only to newly appended rows; it never rewrites
existing evidence.

`SECURITY_DIAGNOSTIC_30D_V1` is an exact live/query-visible retention policy,
not a claim of physical erasure from PostgreSQL heap pages, local WAL, storage
snapshots, or retired media at the same instant. Every bounded query and export
function applies `purge_after` strictly greater than its database-observed
current time before any other filter, so an expired row is undisclosable even if
the bounded purge job lags. Because
V1 stores no raw identity/evidence and destroys the correlation key version by
the last stamped deadline, delayed physical remnants cannot be correlated
through this system. A requirement for physical-byte erasure at 30 days needs a
separately governed encrypted-storage, WAL, vacuum, snapshot, and media-
sanitization design and is unsupported in V1.

The relation and append API reject tenant identifiers or references, farm,
Party, actor, subject, issuer, role, batch, knowledge-position, caller key,
request-supplied request ID, raw route parameter, and arbitrary message or JSON
fields. Producers must never pass credentials, bearer tokens, cookies, headers,
request or response bodies, query strings, raw paths, network addresses, user
agents, secrets, or unredacted attacker-controlled identity material. Request
fields and token claims cannot select event class, producer/component, reason,
policy, or attribution. Only security-relevant routing failures from a closed
reason list enter the lane; an ordinary unmatched route/404 is not automatically
a durable security event.

This evidence is operational diagnosis only. It cannot prove a principal,
tenant, or authorization fact; cannot be joined into tenant reconstruction;
cannot become a RuntimeBundle, gate, trace, output, or capability input; and is
not exposed through tenant, support, export, or readiness APIs.

#### Write and delivery boundary

The `ofarm_security` schema and relation are owned by a dedicated NOLOGIN
security-audit owner. Producers have no table privileges. Separately
provisioned authentication/router audit identities may execute only the
schema-qualified hardened append function through the audit-ingest capability;
they cannot read the relation, read tenant data, choose a tenant context, or
assume an application, binder, owner, reader, retention, or migrator role. The
normal application and worker roles cannot call the append function. Binder
failure is mapped to a closed safe reason by the trusted request boundary and
sent through the same isolated audit channel after the failed tenant
transaction is discarded.

PostgreSQL has no autonomous transaction inside the failed TenantBinding or
tenant UnitOfWork. A pre-tenant event therefore commits synchronously on a
separate, resource-isolated, bounded audit connection/transaction using only
the producer's audit-ingest credential. The producer returns the denial only
after commit acknowledgement or a bounded same-ID retry. It never partially
commits the attempted tenant transaction. Once TenantBinding succeeds, that
separate channel is no longer used for the request: a durable refusal is written
atomically in the bound tenant's governed batch instead.

Delivery is not claimed exactly-once across process death. Stable event IDs and
fingerprints make acknowledged or ambiguous-commit retries idempotent, but a
process crash before append can lose an event, and a whole audit-database outage
cannot be recorded in that database. V1 has no ungoverned local spool, broker,
queue, or dead-letter fallback. Timeouts, connection waits, and retries are
strictly bounded. The attempted action remains denied. Audit-health counters
contain no event fields; after recovery #192's control client uses its distinct
audit-control credential to append a closed `AUDIT_GAP` event for every known
overflow or unavailable interval. A producer ingest identity cannot append that
maintenance kind. If process death makes the count unknowable, the gap says
`COUNT_UNKNOWN` rather than claiming completeness. Audit health affects
readiness by a reviewed threshold, but hostile event volume alone cannot change
a denial into access.

Event size, database work, cryptographic work, producer concurrency, and audit
pool/storage capacity are fixed and isolated from tenant pools, WAL, and volume.
The append function, not the client, enforces migration-owned per-session
budgets in `operational_security_quota_bucket`, keyed only on derived trusted
producer/component and a database-time bucket. At a threshold it first commits
`OVERFLOW_STARTED`, then increments only the bounded bucket counter instead of
appending individual events, and finally the control procedure commits
`OVERFLOW_ENDED` with a count or `COUNT_UNKNOWN`; there is no silent sampling.
Connection limits, statement timeouts, reserved marker capacity, service-level
CPU/storage limits, and growth alerts are provisioned independently of tenant
traffic. A compromised producer cannot select or reset its bucket. Exhausting
the audit service is an accepted denial/readiness availability risk, never an
authorization bypass or tenant-storage exhaustion path.

Once a bucket is in overflow posture, individual submitted event IDs are
deliberately not durable. An acknowledged overflow call increments the bounded
counter once. If its commit acknowledgement is ambiguous, the producer must not
retry it as a countable append; the #192 control path atomically and idempotently
sets that derived bucket to `COUNT_UNKNOWN`. The closing marker then makes no
exact-count claim. This is the explicit exception to per-event retry because the
individual event was intentionally aggregated; it cannot cause a silent double
count presented as exact evidence.

#### Read, retention, replica, and backup boundary

Ingest and reader roles receive no table SELECT or COPY privilege. A dedicated
security-operations service first commits an `AUDIT_ACCESS` intent through its
separate audit-control transaction, binding the closed purpose, exact bounded
query function, every argument, database-observed data cut, cursor/page, row and
byte ceiling, and a five-minute expiry. Only then may its distinct reader
session call that migration-owned function with the committed access event ID;
the function verifies the exact scope fingerprint before returning that one
bounded page. Rollback of the read cannot erase the already-committed access
intent. Reuse can return only the same cut/page/ceiling and cannot widen unique
data; a new page or later cut needs a new intent. Function results can still be
copied or repeatedly retrieved, so the reader is explicitly a privileged,
export-capable boundary within the precommitted bound, not a no-exfiltration
role. Direct table or unbounded extraction is unsupported. A break-glass export
requires a separately provisioned, time-bounded export LOGIN/capability, dual
approval, an exact purpose and cumulative result bound, and a committed
`AUDIT_ACCESS` event; it never grants tenant access or digest-key access.

Rows are immutable to ingest and reader roles. V1 uses one ordinary relation;
the append path performs no runtime partition or other DDL. The append function
stamps `SECURITY_DIAGNOSTIC_30D_V1` and its immutable `purge_after` on each row.
A migration-owned, no-caller-cutoff retention procedure deletes only rows whose
stamped `purge_after` is at or before its database-observed time, in bounded
batches, and appends an `AUDIT_RETENTION` event with the closed cutoff and
deleted count in the same transaction. The retention capability cannot choose
individual IDs, edit rows, or read event contents. Legal hold is unsupported in
V1; adding it requires a new governed schema and policy decision.

Tenant/support backups cannot contain the separate audit service. V1 creates no
audit replica, logical stream, CDC feed, backup, or disaster-recovery copy,
which prevents a managed copy from restoring an expired row but does not turn
SQL DELETE into physical media erasure. Loss of the audit store is therefore a
declared diagnostic-evidence gap, not recoverable tenant data loss. Recovery
recreates an empty verified store from its immutable migrations and, when
possible, appends `AUDIT_GAP` with `COUNT_UNKNOWN`; it never restores expired
events. Adding audit backup or replication requires a new governed design with
an explicit logical-retention and physical-erasure posture. Audit read,
break-glass export, role-grant, purge, store-loss, and empty-recreate tests are
required before operational readiness.

### RuntimeBundle placement and equality

#171 lands before #174 freezes the initial migration. The accepted design has
one one-way global content carrier and a tenant-owned RuntimeBundle receipt:

```text
tenant runtime_bundle
        |
        v
tenant runtime_bundle_component
        |-- GLOBAL target --> runtime_content_blob
        |                     (tenant-neutral exact bytes only)
        |
        `-- TENANT target --> runtime_tenant_content_blob
```

The target arrows are references from tenant membership rows. The global blob relation
never stores tenant_id, bundle membership, a reverse reference, or tenant truth.
Deleting or changing either global or tenant content is forbidden; a bundle is
replaced only by appending a new tenant bundle and selecting it through a later
governed tenant batch.

The placement map is:

| Content or state | Placement | Binding rule |
|---|---|---|
| Profile candidate metadata that does not select tenant state, evidence policy, contracts and contract manifest, Kernel/runtime/validator/adapter/parser/output code, query specifications, runtime schema/environment/catalog inputs, and tenant-neutral AgronomicCodeBindingProfile bytes | Global `runtime_content_blob` | The reviewed release catalog classifies each item as tenant-neutral and pins its exact canonicalization, bytes, length, and full digest. Candidate metadata may describe packages but cannot select a tenant-local activation, context, manifest, route, plan, or reference-data row. |
| Tenant-neutral authored ReferenceSnapshot metadata and genuinely global retained reference-source bytes | Global `runtime_content_blob` | Global placement is allowed only when neither the metadata nor retained bytes contain tenant truth. A tenant bundle names the exact global content identities it selects; the global rows never point back to the tenant or bundle. |
| Active runtime descriptor, tenant binding, route-selection preimage, selection-bearing query plans, and package PackActivationSet, ActiveArtifactSet, or ContextSnapshot instances | Tenant-owned `runtime_tenant_content_blob`; governed PAS/AAS and derived ContextSnapshots also use tenant `kernel_record` | Package files are fixtures/templates, not global activation authority. The active descriptor and plans currently contain tenant selection pointers, so they stay tenant-side. A route preimage pins registry/package/route status, farm, interval, and target fields but excludes the completed bundle digest to avoid a hash cycle; every supplied route must then receipt that completed digest exactly. |
| A Capability Manifest or any other authored instance whose deployment or target scope is `TENANT` | Tenant-owned state | Its package presence does not make it global and does not activate or raise a capability. Selection pins its exact tenant record identity/payload digest and tenant bundle digest. |
| Imported or selected tenant ReferenceSnapshot state and canonical bytes derived from `reference_snapshot_data` | Tenant-owned `kernel_record`/selection state and `runtime_tenant_content_blob` | The selected bytes, data family, source identity, payload digest, and owning tenant are fixed in the bundle. Derived bytes are never copied into `runtime_content_blob`; #185 still owns durable source-byte closure before the separate cache may be treated as rebuildable. |
| Farm, Party, route, activation, selection, ContextSnapshot, request, output, or other tenant truth | Tenant relations only | It is never global bundle content. Every durable consumer uses the trusted tenant key and pins the exact tenant bundle digest in its governed batch. |

The current package's active runtime descriptor, selection-bearing query plans,
tenant binding, PackActivationSet, ActiveArtifactSet, tenant-scoped Capability
Manifest, and ContextSnapshot therefore cannot be global bundle members. They
may remain source fixtures without becoming cross-tenant startup authority.
The tenant-neutral code-binding profile and tenant-neutral reference metadata
may be global content. A descriptor or process-global cache cannot use
`tenant_ref`, a demo default, or rows from `kernel_record` to construct a global
content identity.

`runtime_bundle` and `runtime_bundle_component` are tenant-owned even though
their digests are content-addressed. The #171 prototype, which necessarily
precedes the tenant registry and TenantBinding delivered by #174, keys these
relations by the exact external `tenant_ref` and includes that value in the
canonical receipt. This is a transitional relational key, not authority and not
permission to infer a tenant. #174 replaces it with the trusted internal
tenant_id and pins the immutable tenant-registry digest during the one-time
migration; no runtime fallback from tenant_id to textual tenant_ref is allowed.

The target canonical bundle document contains its internal tenant_id, a closed
schema/canonicalization version, and the complete
component inventory sorted by exact (component_role, logical_ref) bytes. Each
entry carries its `GLOBAL` or `TENANT` storage lane, canonicalization identity,
full content digest, and byte length. It also binds the exact tenant record and
payload digests for active instances and reference selections. Missing, extra,
duplicate, cross-tenant, wrong-lane, or unequal entries refuse the entire
atomic install. The receipt, its component rows, and any new tenant content
blobs commit in one governed tenant batch; a partial bundle is never visible.

V1 supports exactly two byte policies:

- `OFARM_CANONICAL_JSON_V1` parses strict UTF-8 JSON with duplicate-key
  rejection and emits the one reviewed canonical JSON byte representation; and
- `EXACT_BYTES_V1` preserves every input byte without text decoding or
  normalization.

Every content and bundle digest is lowercase `sha256:` followed by 64
hexadecimal digits and covers the exact bytes named by its policy. Digest
equality alone is insufficient. Reuse of `runtime_content_blob` compares the
closed content class, canonicalization, byte length, and exact bytes; reuse of
`runtime_tenant_content_blob` compares the same fields inside the same tenant.
The same digest in two tenants grants no sharing or cross-tenant reference.
Bundle reuse compares the canonical receipt bytes and the exact relational
component set. A mismatch under an existing digest is a collision or corrupt
identity and fails closed.

Component roles are a closed migration-owned vocabulary. `logical_ref` and any
repository provenance use bounded ASCII `RUNTIME_COMPONENT_REF_V1` bytes. The
#171 prototype pins and requires the PostgreSQL libc (`c`) locale provider in
the bundle; #174 additionally declares the final identity domains and indexes
with `COLLATE "C"`. Neither value is a content identity without tenant_id,
bundle_digest, role, storage lane, and content digest. Provenance is bounded, relative,
digest-bound, and never lookup or authorization authority. Truncated hashes,
path-only identity, implicit normalization, delimiter-built composite keys,
filesystem fallback, and last-writer-wins replacement are forbidden.

Startup verifies the release-owned global catalog, exact interpreter/process
environment, and a transaction-local PostgreSQL observation covering exact
server build, encoding, locale/collation identity, timezone, semantic session
settings, search path, roles, and extensions. It may cache defensive
immutable views of those verified bytes without selecting a tenant. Only after
trusted tenant binding may the runtime load `(tenant_id, bundle_digest)` through
forced RLS. Cold load reconstructs from the persisted canonical receipt,
membership rows, and exact global/tenant blob bytes; it rechecks every digest,
length, canonicalization, storage lane, tenant key, and inventory equality and
never reopens repository paths. The cache key is `(tenant_id, bundle_digest)`,
is immutable for that bundle lifetime, and cannot satisfy another tenant. A
queued operation or acceptance under a different tenant bundle refuses unless
a separately governed migration operation is later defined.

The Python boundary is executable, not an environment convention. Every live
entry point uses the retained launcher with actual `python -I -B -S` flags
inside the one digest-pinned, read-only Python Bookworm image.
Before exposing project or dependency roots, that launcher verifies the static
component lock and exact locked distribution set, verifies each retained wheel
archive against its reviewed hash, and compares every installed import-root
member directly with that archive. Mutable installed `RECORD` metadata is not
an integrity authority. It also refuses `PYTHONPATH`/`PYTHONHOME` or other
startup customization, native loader environment (including empty values),
`.pth` files, user/site customization, project or
dependency bytecode, and unowned dependency data or importable files. The only
resulting path order is the pinned CPython standard runtime, locked virtual-
environment roots, then the reviewed project root.

The retained OCI-derived image manifest binds the exact executable, complete
stdlib tree, libpython/native files, loader configuration, and required loader
preload absence. `RUNTIME_ENVIRONMENT_OBSERVED` v3 retains that image identity,
ordered path and flag posture, a complete source/native stdlib and
lib-dynload inventory, every locked wheel import-root member, and each actually
loaded module's name, loader, resolved origin, byte identity, package search
paths, and classification. It also binds `sys.meta_path` and `sys.path_hooks`
provider provenance and live object identity. Project origins must equal
retained `RUNTIME_CODE`; dependency and standard-runtime origins must equal
their retained file inventory. Unknown origins refuse, with closed built-in/
frozen and native-created auxiliary cases attributed to their retained parent
runtime. Live selection captures exact identities for the `sys.modules`
mapping (including `None` entries), every module object and loader state, the
`sys.path`/meta-path/path-hook containers and providers, and every canonical
`sys.path_importer_cache` key, `FileFinder` object, loader configuration, and
mutable finder cache. Activation, the pre-commit bootstrap guard, and every
later decision boundary require that immutable seal: module additions,
removals, replacements or reload state, path/container changes, and importer
cache/finder drift refuse instead of widening the selected runtime. It also
inventories every file-backed executable Linux
mapping, attributes it to the read-only image or a hash-locked wheel, explicitly
receipts the kernel vDSO/vsyscall boundary, and rejects anonymous, deleted,
memfd, unknown, or late-added mappings before a governed commit.

Before #174 replaces the prototype with immutable numbered migrations, #171
also closes the mutable-DDL startup gap without inventing a compatibility path.
The process verifies the complete static RuntimeBundle lock, exact schema bytes,
and closed Python import posture before opening a database connection. It then
classifies `public` through catalog reads as provably empty, exact current, or
other. Only the empty case executes the verified schema and writes one protected
`runtime_schema_ledger` receipt in the same transaction. The receipt retains the
schema digest and canonical pg_catalog fingerprint for relations, columns and
defaults, types, constraints and their internal enforcement-trigger state,
indexes, non-internal triggers, functions, rewrite rules, policies, owners, and
grants. Exact current is a verified no-DDL restart. A
missing ledger on a non-empty schema, an older prototype schema, changed schema
bytes, or catalog drift refuses before DDL with an instruction to recreate the
pre-deployment database. #174 supersedes this transitional one-schema receipt
with the separately applied numbered migration/readiness design below; it does
not forward-migrate or adopt a database accepted by the prototype receipt.
The one allowed empty install runs at SERIALIZABLE and holds SHARE locks on
every catalog relation read by the fingerprint from its second empty check
through DDL, fingerprinting, and ledger insertion. Every later outer governed
transaction takes the same catalog locks before recomputing the receipt and
holds them through commit, so DDL cannot land between verification and decision
SQL. Concurrent non-cooperating DDL therefore finishes before the check or
waits until the governed transaction completes.

This transitional, pre-deployment prototype uses one elevated schema-owner and
runtime identity because both installation and the per-transaction DDL exclusion
need catalog-lock authority. It does not claim a least-privilege application
role. #174 must separate numbered-migration ownership from stable application
grants, provide a least-privilege runtime design that preserves the no-DDL-race
invariant, and remove schema installation from application startup before any
deployment.

The global content installer is release-owned and unavailable to application,
worker, tenant, and support roles. It accepts only catalog-classified
tenant-neutral classes and exact bytes. Tenant bundle creation happens only
after binding through the tenant write path. #174 must express these relations,
domains, one-way foreign keys, forced RLS policies, grants, and atomic insertion
constraints in 0001; it must not copy the prototype's globally unqualified
bundle receipt tables. This placement changes no manifest, active artifact set,
profile activation, contract, or capability claim.

## Tenant identity and trusted context

The database uses an internal immutable UUID tenant_id for relational identity.
The contract-visible tenant_ref remains an external string mapped uniquely by
the global tenant registry. Business and OFARM references remain tenant-local:
their complete relational identity is always (tenant_id, local reference).
Embedding a tenant name in a string does not qualify a key.

### Governed principal source

The authoritative production source for tenant selection is the combination of
immutable principal-binding versions and their append-only lifecycle acts. A
`principal_binding` version records the exact issuer and subject bytes under a
named equality policy, tenant_id, the immutable tenant-registry row digest,
party_ref, the exact `ofarm.party.v0.1` Party record identity, record-kind
identity, schema digest, payload digest, validity bounds, immutable version
identity and digest, and any predecessor version. The pinned payload must
declare `partyState=ACTIVE`. The version has no mutable state. Its target Party
has a composite (tenant_id, party_ref) foreign key, and its version digest covers
every pinned identity, digest, and equality-policy field.
For this contract, party_ref is both the Party `kernel_record.record_id` and the
validated payload `partyId`; the binder requires all three values and the
`record_kind` to agree.

`principal_binding_lifecycle` is the authoritative state machine. Every
immutable act is one of ACTIVATE, REVOKE, EXPIRE, or SUPERSEDE and contains the
exact-policy principal key, affected version or predecessor/successor versions,
monotonic stream sequence, prior-act identity and digest, effective time,
decision time, accountable control identity, reason, and its own digest. Unique
stream sequence and prior-head constraints prevent a fork. Folding the accepted
act chain over immutable versions determines the binding at any lifecycle cut;
the projection is never consulted for historical reconstruction.

The current binding is the version left ACTIVE by that fold, within its
immutable validity bounds, and not subsequently revoked, expired, or
superseded. Zero active versions, a broken or ambiguous act chain, more than one
active candidate, a tenant-registry or pinned Party identity/digest mismatch, a
pinned Party record that does not declare `partyState=ACTIVE`, or an invalid
validity window denies context. Token roles never synthesize a Party, tenant,
OFARM role, or authority grant.

`principal_binding_current` is only an optional, disposable locator and
concurrency reservation. It has one UNIQUE (equality_policy, issuer, subject)
slot containing the computed active version identity/digest and lifecycle-head
identity/digest, or the computed inactive state. The unique slot does not confer
authority. Missing,
stale, corrupt, or mismatched projection data never authorizes a request and can
be dropped and rebuilt deterministically from immutable versions and acts.

Creation, activation, revocation, expiry, supersession, or target replacement
uses one hardened identity-control transition. It first acquires the unique
exact-policy (issuer, subject) reservation, reconstructs and validates the
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
reconstructed as of its recorded lifecycle cut using the immutable binding
version, its pinned tenant/Party record digests and equality policy, and the
append-only acts, never the then-current projection or a floating Party record.

V1 deliberately has no mutable tenant eligibility, tenant retirement, or Party
authorization-eligibility lifecycle. A tenant-registry row is immutable after
provisioning. Binding creation may pin only an immutable Party record whose
payload declares `partyState=ACTIVE`; a later Party payload does not silently
change that binding's authority. A new Party record is a different immutable
target and requires a new principal-binding version plus lifecycle transition.
To stop a principal from binding in V1, the
control plane revokes, expires, or supersedes its principal binding. A claim to
deactivate one tenant or Party across principals is unsupported. Adding it
requires a later decision with append-only tenant and Party lifecycle sources,
transition authority, historical-cut semantics, knowledge ordering, current
projections, and exact head identities/digests in capabilities, bindings, and
authorization receipts. The `partyState` field in an immutable domain payload
is not a hidden authentication switch.

The tenant-registration digest is SHA-256 over
`ASCII("OFARM_TENANT_REGISTRATION_V1") || 0x00`, the tenant UUID in RFC 4122
network byte order exactly as PostgreSQL `uuid_send(tenant_id)`,
`lp32(ASCII("OFARM_ASCII_ID_V1"))`, `lp32(tenant_ref ASCII bytes)`, and the
advisory-lock key as one signed 64-bit big-endian integer, in that order.
`lp32` is defined below. The registry stores the source fields as well as the
digest; equality is never digest-only. Binding versions and capabilities carry
tenant_id and this digest, and the binder compares both against the immutable
row.

Tenant registration occurs only through a migration-owned, fixed-SQL
`register_tenant` SECURITY DEFINER function. The control-plane caller supplies
only a validated external tenant_ref; the function derives the UUID, disjoint
advisory-lock key, equality-policy identity, canonical digest, and returned
registration receipt inside the database. `ofarm_tenant_registrar` may EXECUTE
only that function and has no direct registry or tenant-table privileges.
Direct INSERT, UPDATE, and DELETE are denied to application, worker, readiness,
identity-writer, registrar, and every other runtime/control role. A
migration-owned mutation-forbid trigger rejects UPDATE/DELETE regardless of a
mistaken grant. Owner or migrator ability to alter that protection remains an
explicit privileged-boundary compromise.

The initial architecture supports exactly one active principal-binding version
per exact-policy (issuer, subject), and that version pins one immutable tenant
registry row and Party record. Multi-tenant principals, tenant switching, and
user-selected tenant candidates are unsupported. Supporting them requires a
separate decision covering selection, disclosure, confused-deputy risk, and
receipt semantics. There is no production default.

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
(issuer, subject) identity under the binding version's equality policy. It does
not pass a raw tenant identifier to SQL. After #173 begins one UnitOfWork on one
checked-out backend, binding proceeds as follows:

1. A hardened owner function creates a cryptographically random one-use
   challenge bound to the current backend identity and full transaction
   identity in protected transaction context.
2. The trusted authentication boundary mints a short-lived TenantCapability
   containing that challenge, binder audience, equality-policy identity, exact
   issuer and subject, immutable binding-version identity and digest,
   lifecycle-head act identity and digest, tenant_id, tenant-registry digest,
   party_ref, pinned Party record-kind identity, record identity, schema digest,
   and payload digest,
   issued/expiry times, and a unique nonce. The capability is signed by a key
   unavailable to the application database role.
3. A schema-qualified SECURITY DEFINER binder with a fixed trusted search_path
   verifies the signature, audience, expiry, backend/transaction challenge,
   nonce, exact immutable version bytes and digest, and the authoritative
   lifecycle head and currentness reconstructed from immutable acts. It may use
   `principal_binding_current` to locate a candidate only when its version and
   head exactly equal that reconstruction; a missing or mismatched projection
   causes refusal or a separate privileged deterministic rebuild, never
   authorization. Before context exists, the binder uses only the narrow
   bootstrap privilege frozen below to verify the immutable tenant-registry row
   and the exact pinned ACTIVE `ofarm.party.v0.1` record kind, identity, schema
   digest, and payload digest; it performs no floating latest-Party or mutable
   tenant-state lookup. It then inserts exactly one verified
   TenantBinding, including those pinned identities/digests and the equality
   policy, into the protected context relation.
4. A uniqueness constraint makes the first successful bind final for that
   transaction. A second call, reset, principal change, tenant change, or
   capability replay refuses. The current-context function accepts the row only
   when its database-derived backend identity, backend-start instant, and full
   xid8 all equal the current transaction. Commit, rollback, or backend restart
   makes the physical row unusable; a capability from another transaction or
   backend cannot be reused.

The bootstrap path is explicit. `tenant_registry`, `principal_binding`,
`principal_binding_lifecycle`, `principal_binding_current`,
`tenant_binding_context`, and `schema_migration` are non-tenant control or
operational relations and are not given tenant RLS policies. They are protected
by ownership, relation privilege denial, and migration-checksummed hardened
functions. Every tenant-bearing relation, including the Party-bearing
`kernel_record`, remains under enabled and forced RLS.

The hardened binder executes as `ofarm_binder`, provisioned `NOSUPERUSER`,
`NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, `NOLOGIN`, `NOINHERIT`, and
`BYPASSRLS`. No LOGIN role is a member, no `SET ROLE` or admin path to it is
granted, and it has only the relation/column privileges required
to reconstruct one principal stream and compare the exact tenant-registry and
Party tuple named by that binding. Its fixed, schema-qualified SQL accepts no
table, column, predicate, tenant, or Party selector other than the signed and
database-matched binding tuple; it returns no tenant row or Party payload. The
application receives EXECUTE only on the exact challenge, binder, and current-
context functions. There is no generic query/dynamic-SQL function owned by this
role. Compromise of `ofarm_binder` is therefore an explicit privileged-boundary
compromise outside RLS, while possession of application credentials or raw SQL
cannot exercise its bypass as a general tenant-data read path.

`tenant_binding_context` is an UNLOGGED, migration-owned disposable relation.
Its authority key is `(backend_pid, backend_start, full_xid8)`, all derived
inside PostgreSQL; an additional UNIQUE `(backend_pid, backend_start)` permits
at most one visible row for a backend incarnation. The challenge function uses
`pg_current_xact_id()` for xid8, deletes only a stale row for the same backend
incarnation, and inserts state `CHALLENGE` with all binding fields null. A
guarded binder update must change exactly that current row once from
`CHALLENGE` to `BOUND`; all verified binding fields are then non-null. Zero or
more than one affected row refuses, and no transition out of `BOUND` exists.
The no-argument current-context function recomputes and exactly matches all
three keys and `BOUND` state. xid8 includes the transaction epoch and is never
treated as a wrapping 32-bit XID. A committed orphan may remain physically,
but no later transaction can match it; the next challenge on that backend
removes it. Every challenge also invokes the protected no-caller-cutoff
`purge_stale_tenant_context` function, which deletes up to a fixed migration-
owned bound of rows whose exact backend incarnation is absent from
`pg_stat_activity`; it accepts no PID, xid, timestamp, or cutoff argument and
returns no context data. #174 owns that function, its EXECUTE grant only through
the challenge path, and direct-role tests. Cleanup is mandatory for bounded
physical state but never makes a row valid and is not required for fail-closed
authorization. Rollback removes uncommitted context, and crash recovery clears
the UNLOGGED relation.

#173 must commit or roll back before returning a connection to the pool and
must reject a return whose PostgreSQL transaction status is not idle.
Cancellation, exception, timeout, serialization retry, and pool reset all issue
rollback before reuse. Successful commit changes the full xid before any later
checkout. This lifetime rule avoids deleting context before deferred checks run
while proving that no completed transaction's binding is usable in another.

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

V1 uses closed, named equality policies. They validate or reject input; none
rewrites it. `OIDC_EXACT_UTF8_V1` and `OFARM_ASCII_ID_V1` govern request and
business identifiers. `RUNTIME_COMPONENT_REF_V1` is a release-only policy for
the wider exact ASCII component/path vocabulary and is never accepted as a
tenant-local identifier.

| Namespace | Policy and canonical bytes | V1 grammar and bound | Database equality |
|---|---|---|---|
| OIDC issuer | `OIDC_EXACT_UTF8_V1`: UTF-8 encoding of the verified decoded `iss` JSON string exactly as received | 1-2048 UTF-8 bytes; configured case-sensitive `https` issuer URL with host, optional port/path, and no query, fragment, NUL, or control character | Exact bytes; no trimming, case folding, percent/host/path rewriting, Unicode normalization, or discovery-alias substitution |
| OIDC subject | `OIDC_EXACT_UTF8_V1`: UTF-8 encoding of the verified decoded `sub` JSON string exactly as received | 1-255 visible ASCII bytes, as required by the V1 OIDC profile; no whitespace, control, or NUL | Exact case-sensitive bytes; no trimming, folding, or Unicode transformation |
| External `tenant_ref` | `OFARM_ASCII_ID_V1`: the authored ASCII bytes | 1-255 bytes matching `[A-Za-z0-9._:-]+` | Exact bytes |
| Tenant-local authored identifiers, including record, Party, farm, scope, request, trace, batch, artifact, snapshot, materialization, and reference keys | `OFARM_ASCII_ID_V1`: the contract-validated authored ASCII bytes | 1-255 bytes matching `[A-Za-z0-9._:-]+`; a narrower contract grammar still applies where defined | Exact bytes inside the tenant-qualified composite key |
| Idempotency `caller_key` | `OFARM_ASCII_ID_V1`: the contract-validated authored ASCII bytes | 1-255 bytes matching `[A-Za-z0-9._:-]+` | Exact bytes inside the full idempotency identity; no transport-layer rewriting |
| RuntimeBundle component role, logical reference, and repository provenance | `RUNTIME_COMPONENT_REF_V1`: the release-catalog ASCII bytes exactly as authored | Role is one closed enum value. Logical reference and relative POSIX provenance path are 1-1024 bytes from `[A-Za-z0-9._:/#-]+`; no whitespace, control, NUL, backslash, absolute path, empty path segment, or `.`/`..` path segment | Exact bytes under `COLLATE "C"`; identity remains the full tenant/bundle/role/lane/logical-ref/content-digest tuple, never the path alone |
| Principal lifecycle stream and current reservation | Separate equality-policy, issuer, and subject columns; digest input uses tag plus unsigned length-prefixed field bytes | Exactly the issuer/subject rules above | One composite exact-byte key; delimiter concatenation and digest-only equality are forbidden |

PostgreSQL tenant storage is provisioned with `server_encoding=UTF8`.
Equality-sensitive text columns and their unique/foreign-key indexes use the
deterministic built-in `COLLATE "C"` byte ordering plus migration-owned domains
that enforce `octet_length` and grammar; canonical digest input uses
`convert_to(value, 'UTF8')` and unambiguous tagged length prefixes. `citext`,
locale-default equality, nondeterministic ICU collations, application-only
normalization, and delimiter-joined composite keys are forbidden. Readiness
verifies the database encoding, each governed domain/check, collation provider
and determinism, explicit index collation, and equality-policy identity.

Every immutable principal-binding version stores its equality-policy identity,
and the version digest covers that identity and the exact length-prefixed issuer
and subject bytes. Lifecycle acts, reservations, capabilities, bindings, and
receipts name the same version and policy; no layer recomputes a differently
normalized principal. An issuer that cannot satisfy `OIDC_EXACT_UTF8_V1`
requires a new reviewed policy identity, migration, verifier configuration, and
cross-layer tests before it is accepted.

The canonical principal key bytes are exactly:

```text
ASCII("OFARM_PRINCIPAL_KEY_V1") || 0x00
|| lp32(ASCII(equality_policy))
|| lp32(UTF8(issuer))
|| lp32(UTF8(subject))
```

`lp32(x)` is the unsigned 32-bit big-endian byte length of `x`, followed by
`x`. The JSON parser first produces the verified decoded claim string, so JSON
escape spellings that decode to the same scalar sequence are the same input;
no transformation occurs after decoding. Delimiter concatenation, implicit
database casts, and digest equality without the canonical bytes are forbidden.

- Every tenant-owned primary key, unique constraint, and foreign key begins
  with tenant_id.
- record_id, trace_id, request_id, batch_id, artifact_ref, and other authored
  references are tenant-local even if their textual form appears globally
  distinctive.
- Globally governed identifiers are globally unique and, for content, are
  collision-resistant digests whose canonical bytes are also compared.
- Principal identity is the exact-policy (issuer, subject) pair. Immutable
  binding versions may repeat that pair. Only the disposable current
  projection/reservation has UNIQUE (equality_policy, issuer, subject);
  serialized lifecycle transitions and the authoritative act fold, not that
  projection constraint, establish at most one active version. A token role or
  caller tenant string is never part of the identity.
- Idempotency identity is exactly (tenant_id,
  authenticated_principal_ref, governed_operation, caller_key). #178 adds the
  canonical semantic request digest, complete durable response, retention, and
  named-conflict behavior without changing this namespace.
- Materialization and dependency uniqueness starts with tenant_id. Digest
  equality alone never proves key equality; the canonical key is compared.
- Cache keys, import identities, output references, and post-binding operational
  request identities are tenant-qualified. A pre-tenant security event instead
  has only its database-generated global event UUID and optional protected
  correlation digest; neither can convey tenant identity or authorization.
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
can close only its neutral structural slice and the runtime refuses surfaces
that need complete carrier/reference semantics. #184 then adds those semantics
through a reviewed forward migration.

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
contract or tenant-neutral component digest, only through an accepted global
lane. It references a RuntimeBundle through the same-tenant composite
`(tenant_id, bundle_digest)` key; a bundle digest is not a global target. Global
content never refers back to tenant rows, and the application cannot mutate it.
The globally governed immutable principal-binding versions are the sole initial
exception: they form a protected authorization bridge with an explicit
composite target-Party foreign key, not shared content and not a general cross-
tenant query path. Lifecycle acts and the current projection name those
versions but add no second tenant-truth path.

## Database roles and row-level security

Use a dedicated, fully qualified application schema such as ofarm. Revoke
CREATE on public and revoke unnecessary PUBLIC privileges on the database,
schemas, tables, sequences, and functions.

The role model is:

- ofarm_owner: NOLOGIN owner of tenant/application schemas, tables, policies,
  and ordinary functions, explicitly excluding the isolated `ofarm_security`
  objects and the three narrowly `ofarm_binder`-owned functions;
- ofarm_migrator: release-only credentials allowed to take the migration lock
  and apply reviewed DDL through the applicable application or security-audit
  owner role, with no runtime ingest/read/retention authority;
- ofarm_app: non-owner application role with NOBYPASSRLS, no DDL, no owner or
  migrator membership, and only required DML;
- ofarm_worker: same isolation posture as the application, with an explicit
  TenantBinding per job;
- ofarm_tenant_registrar: NOLOGIN control-plane capability granted only to one
  separately provisioned tenant-control LOGIN with `INHERIT TRUE`, `SET FALSE`,
  and `ADMIN FALSE`; it has EXECUTE only on the insert-only `register_tenant`
  function, no direct relation privileges, application membership,
  binding/lifecycle authority, or tenant reads;
- ofarm_binder: NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOLOGIN,
  NOINHERIT, BYPASSRLS privileged function owner used
  only by the hardened challenge, binder, and current-context functions. It has
  no members or role-assumption path and only the exact column/relation rights
  needed to read immutable binding versions, authoritative lifecycle acts,
  optional current projection, tenant registry, one pinned Party record, and
  transaction context. The application may EXECUTE those closed functions but
  cannot SET ROLE to this role or obtain generic tenant reads;
- ofarm_identity_writer: control-plane-only capability that may execute the
  principal-binding lifecycle transition but has no direct DML on binding
  versions, lifecycle acts, or projection, no tenant-truth read role, and no
  application membership;
- ofarm_security_audit_owner: NOLOGIN owner only of the protected
  `ofarm_security` schema, operational security-event relation, and hardened
  append/control/query/export/purge/readiness functions, with no tenant-schema
  membership;
- ofarm_security_audit_ingest: NOLOGIN capability granted only to separately
  provisioned authentication/router producer LOGIN identities with `INHERIT
  TRUE`, `SET FALSE`, and `ADMIN FALSE`; it may execute only the pre-tenant
  append function and has no relation SELECT/DML, tenant-data access, or
  membership in application, binder, control, reader, export, retention, owner,
  or migrator roles;
- ofarm_security_audit_control: NOLOGIN security-operations capability used by
  a distinct control LOGIN to append only typed `AUDIT_ACCESS`, gap, and
  overflow maintenance events and close quota buckets; it has no pre-tenant
  append, query-result, retention, tenant, or application authority;
- ofarm_security_audit_reader: NOLOGIN security-operations capability with
  EXECUTE only on bounded audited query functions, no table SELECT/COPY,
  append/retention authority, tenant-data access, or application membership;
- ofarm_security_audit_export: NOLOGIN break-glass capability granted only to a
  time-bounded LOGIN after dual approval; it executes only the exact
  pre-authorized bounded export function and has no table, append, retention,
  tenant, application, or digest-key access;
- ofarm_security_audit_retention: NOLOGIN security-operations capability that
  may execute only the migration-owned no-caller-cutoff expired-row purge
  procedure, with no arbitrary row mutation, append, reader, tenant, or
  application authority;
- ofarm_security_audit_readiness: read-only access only to the audit migration
  ledger and structural verification function, with no event/quota/query,
  tenant, application, ingest, control, export, or retention access; and
- ofarm_readiness: read-only access to migration metadata and no access to
  tenant data, or an equivalently restricted readiness grant.

Enable and FORCE row-level security on every tenant-bearing relation. Policies
use only the protected current-tenant function for both USING and WITH CHECK.
They never consume a raw custom setting. Missing, invalid, expired, replayed, or
multiply bound context denies or raises; it never selects all tenants. Append-
only restrictions remain additional constraints and do not substitute for RLS.
The closed non-tenant control list is `tenant_registry`, `principal_binding`,
`principal_binding_lifecycle`, `principal_binding_current`,
`tenant_binding_context`, and `schema_migration`; these relations have no
tenant RLS policy and instead deny direct application, worker, and end-user
relation access. The binder/registrar reach only their named functions and
minimum underlying fields; readiness receives the separately specified exact
read-only migration-ledger grant. Adding any relation or privilege to that list
requires a migration and classification change. Party and every other tenant-
bearing record remain forced-RLS protected.

Normal functions execute as the caller. Any unavoidable SECURITY DEFINER
function has a fixed trusted search_path, schema-qualified objects, no
caller-controlled dynamic SQL, minimal ownership, explicit EXECUTE grants, and
adversarial tests. The challenge, binder, current-context, and lock wrappers are
named exceptions, together with the isolated security-audit append, control,
query, export, purge, and readiness procedures. Their definitions and owners are
migration-checksummed. Triggers and constraint functions include tenant and
batch in every tenant lookup.

Direct SQL using the application role remains subject to forced RLS, composite
constraints, verified context, and append-only rules. The application role
cannot read or write protected context, binding versions, lifecycle acts,
current projection, pre-tenant security events, tenant lock keys, or
capability-verification keys; cannot call the security-audit append or retention
functions; cannot assume any privileged role; and cannot execute raw
advisory-lock functions. End users and support users never receive application,
migration, or security-audit credentials. Superusers, database administrators,
migrators, identity-control writers, security-audit owners/readers/retention
operators, backup readers, `ofarm_binder`, and a fully compromised capability
signer are outside the RLS protection boundary; access to those capabilities
requires separate operational controls and audit. The binder's NOLOGIN/no-
membership posture and fixed functions are the control that keeps this narrow
bypass from becoming an application SQL path.

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
tenant database, plus a separately bounded audit PostgreSQL service/database
with its empty `ofarm_security` namespace. It creates the NOLOGIN application,
binder, and security owners, migrator/application/worker/readiness identities or
grants, tenant registrar, identity-control writer, seven isolated
security-audit capabilities,
the distinct tenant-control and audit producer/control LOGIN identities and
exact `INHERIT TRUE`/`SET FALSE`/`ADMIN FALSE` memberships, service resource
limits, and initial PUBLIC revocations. Application startup and either migration
runner do not create or repair their own cluster roles or services.

The tenant database is created with UTF8 server encoding. Provisioning verifies
the built-in deterministic `C` collation used by every equality-sensitive
domain and index, creates `ofarm_binder` with exactly NOSUPERUSER, NOCREATEDB,
NOCREATEROLE, NOREPLICATION, NOLOGIN, NOINHERIT, and BYPASSRLS, and proves that
no LOGIN can inherit, assume, or administer it. It
creates no tenant-service restore, point-in-time-recovery promotion, snapshot-
adoption, or tenant-history import identity or command in V1.

Provisioning is verify-or-create only for a provably new target. On an existing
target it compares role attributes, memberships, namespace owners, database
owner, and grants to the declared specification. Any unexpected privilege,
owner, member, object, or role attribute is drift and refuses; provisioning
does not silently widen or reconcile it. Credentials and signing keys remain
outside repository fixtures and migration SQL.

## Immutable migration baseline

Two authoritative, independently ordered migration sets use four-digit,
gap-free, immutable filenames: `kernel/migrations` for the tenant service and
`security_audit/migrations` for the separate audit service. Because there is no
deployment, #174 creates hardened `0001_initial.sql` migrations for both. The
tenant migration waits for #171's reviewed RuntimeBundle placement map; the
audit migration contains only the two classified audit relations, closed
constants/checks/functions, roles/grants, and its own ledger/readiness surface.
The tenant migration creates global `runtime_content_blob` with no tenant
back-reference and creates `runtime_tenant_content_blob`, `runtime_bundle`, and
`runtime_bundle_component` as tenant-qualified forced-RLS relations. It uses
separate exact foreign-key lanes from tenant component membership to global or
same-tenant content and gives the global installer and tenant bundle writer no
interchangeable capability.
#174 may progress the neutral carrier and non-semantic isolation work, but the
tenant 0001 deliberately supplies only the neutral carrier and settled
structural isolation constraints. #174 can close that database-primitives
slice without claiming complete reference semantics. #184 follows with the
accepted extraction/kind/cardinality artifact and an immutable forward
migration; until then the runtime must refuse any operation that depends on the
missing semantic matrix. Neither initial migration preserves the unsafe
prototype as a compatibility layer. Development and conformance targets are
dropped and recreated.

Once either baseline is accepted, an applied migration file is never edited,
renamed, reordered, or deleted. Every schema change appends to the applicable
set. The existing mutable schema.sql ceases to be authoritative; #174 may remove
it or generate a convenience tenant snapshot, but runtime code must never
execute that snapshot.

A separate migration command, release job, or operator action targets exactly
one provisioned service and its migration set:

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

The application build carries the exact expected latest tenant migration
version and ordered migration-set digest. The #192 audit client carries the
exact expected audit migration version/digest. Each performs read-only
verification of its own ledger before constructing its repositories or serving
its traffic. Neither creates, alters, drops, repairs, or bootstraps schema
objects.

Schema mismatch prevents readiness. A dedicated readiness check reports only
the supported/observed version state without tenant counts, identifiers, or
records. Liveness checks only process health. An empty database, an older or
newer schema, a dirty history, an unavailable ledger, or a checksum mismatch
never becomes ready and never triggers DDL.

V1 readiness applies only to a proven-empty initial target or the uninterrupted
in-place lineage created from that target. It has no recovery-readiness mode.
A target declared restored, point-in-time promoted, snapshot-cloned,
tenant-history imported, forked, or of unknown provenance cannot be promoted to
service even when its build and migration digests match. The application cannot
detect a privileged operator who conceals such an operation; database-
administrator and recovery-control compromise is outside the RLS boundary.
Schema compatibility is never represented as proof of timeline continuity.

The first deployment has an exact-version compatibility window: one release
supports exactly one tenant migration-set digest and one audit migration-set
digest. There is no N-minus-one support, dual-read/write path, compatibility
view, or backfill. Deployment runs both migration release steps, then starts the
matching application and audit client. If a future availability requirement
needs rolling mixed versions, an explicit expand/contract ADR and bounded
compatibility window must precede it.

There are no down migrations for durable truth. Before first deployment,
rollback means deleting and recreating the disposable development database.
After deployment:

- a failed transactional migration rolls back both DDL and ledger append;
- a successful migration is corrected by a new forward migration; and
- loss of the uninterrupted live tenant-service lineage is terminal unreadiness
  in V1. There is no supported tenant-service backup restore, point-in-time
  recovery promotion, snapshot-clone promotion, database logical restore, or
  tenant-history logical import. The separate V1 audit service independently
  keeps its empty-recreate/declared-gap posture.

A domain data import that writes new governed batches at new positions is not
database recovery. Whole shared-database physical recovery and tenant-specific
logical history recovery are different future designs; neither is supported.
#193 must define and implement an external non-rewindable recovery witness,
authority/idempotency/release reconciliation, non-reuse of every published cut,
and fail-closed recovery readiness before either path exists.

Starting an older binary against a newer schema is not rollback; it is a
readiness failure. Destructive forward migrations are unsupported in V1 because
there is no accepted recovery path. They require #193's accepted recovery ADR,
implementation, and real recovery rehearsal first.

## Threat model

The protected assets are tenant truth, authority and sharing records, runtime
evidence, derived state, frozen outputs, command receipts, pre-tenant security
evidence, and schema integrity. The attacker may control request fields,
identifiers, retry keys, payload references, timing, concurrency, event volume,
and malformed SQL inputs. The attacker may trigger authentication, verifier,
routing, binder, transaction, and pool-reuse failures. The model also covers
accidental unqualified queries and direct SQL under the application role.

| Threat | Required control |
|---|---|
| Forged tenant in a body, route, header, farm reference, or environment default | Only a signed, challenge-bound TenantCapability verified against an immutable binding version and the authoritative lifecycle head can create TenantBinding; selectors are untrusted and there is no production default. |
| Raw SET, SET LOCAL, set_config, reset, shadow object, second bind, stale committed context, or cross-backend/transaction capability replay | RLS ignores caller settings and reads protected one-bind-per-transaction context through fixed-schema functions. Capability audience, signature, nonce, database-derived backend identity/start and full xid8, immutable version/tenant/Party digests, equality policy, and lifecycle-head digest are verified. A physically retained row cannot match a later transaction. |
| Missing, malformed, expired, revoked, superseded, forked, or ambiguous principal binding | The protected binder reconstructs currentness from immutable versions and lifecycle acts and fails before tenant repository access; its sole pre-context tenant read is the fixed exact pinned-Party comparison. Repositories require a bound UnitOfWork. |
| Case, whitespace, Unicode, URI, collation, or delimiter ambiguity splits or merges a principal, tenant reference, local identifier, lifecycle reservation, or caller key | Closed equality policies preserve exact validated bytes, use explicit byte bounds and grammars, store separate composite fields, bind policy identity into immutable digests, and use verified UTF8/`C`-collated database domains and indexes. |
| Mutable tenant flag or floating Party payload silently changes authentication authority without history | V1 has no tenant active flag or tenant/Party eligibility transition. Each binding pins one immutable tenant-registry digest and exact ACTIVE Party record identity/schema/payload digests; access cessation uses the append-only principal-binding lifecycle. |
| Attacker-supplied tenant, Party, role, issuer/subject, request ID, route value, or token claim contaminates a pre-tenant audit event | The closed append API accepts only a trusted-producer event UUID, allowed reason and protected correlation HMAC; it derives producer/time/policies itself and writes a relation with no tenant or principal columns. Exact ID/fingerprint retry prevents substitution. Request data cannot select a tenant lane. |
| Credential, token, header, body, network identifier, low-entropy identity, or arbitrary error detail leaks through security audit | Closed reason/component classes, one bounded HMAC of only a high-entropy server correlation value, keys outside database/application roles, and rejection of every general evidence field. No ordinary log, telemetry, queue, or dead-letter fallback is allowed. |
| Failed binder or tenant transaction loses its audit event, partially commits tenant work, or redirects it into a tenant log | The attempted tenant transaction rolls back; a separate bounded audit connection commits only the non-tenant event. After successful binding, the separate lane is forbidden and durable refusal joins the tenant batch. |
| Forged, replayed, flooded, mutated, selectively deleted, or indefinitely retained pre-tenant events | Exact session-user attribution and per-producer reason allowlists, idempotent append-input comparison, insert-only hardened API, database-enforced quota buckets, fixed event cost, explicit overflow/gap markers, immutable policy/purge fields, a separate audit PostgreSQL service/volume/WAL/pool, and bounded reader/retention capabilities. A producer compromise can forge only its own diagnostic class and never grants authority or consumes tenant storage. |
| Tenant, support, readiness, tenant-export, or application path reads or joins pre-tenant security evidence | No credentials, network route, privileges, or API surface for those roles; no tenant identifiers; only the separately bounded security reader/export protocol; and adversarial privilege/join tests. |
| Audit backup, replica, CDC, or restore retains or resurrects an event beyond 30 days | V1 provisions none. Tenant backup targets cannot address the separate audit service; audit-store loss uses verified empty recreation plus an honest gap marker, never restore. |
| Deleted, stale, forged, or corrupt principal-binding current projection | Projection data is only a candidate locator. The binder compares it with the authoritative lifecycle fold and refuses on absence or mismatch; only a privileged deterministic rebuild from versions and acts may restore it. |
| Edited or deleted binding version or lifecycle history, or concurrent activation attempts | Direct DML is denied, versions and acts are immutable, lifecycle streams are serialized by the unique principal reservation and expected-head checks, and current/historical state ignores projection as authority. |
| Stale shared-database restore, snapshot/PITR promotion, or tenant-history logical import reuses a published position, removes a revocation, loses an idempotency/receipt row, or forks an already released output | V1 exposes no recovery/import promotion or recovery-readiness path; a matching schema/build is insufficient. No signer, binder, allocator, repository, release, or delivery path may start for a declared recovery target. #193 must supply non-rewindable continuity proof before this posture changes. |
| Context surviving connection-pool reuse after success, rollback, failure, cancellation, or retry | Exact database-derived backend/start/xid8 matching, unusable committed orphans, rollback-on-return, idle-status enforcement, protected stale cleanup, and same-backend alternating-tenant tests. |
| Unqualified reads, joins, subqueries, aggregates, prepared statements, or background scans | Forced RLS on every tenant-bearing relation and explicit tenant assignment for workers. |
| Direct SQL inserts another tenant_id or attempts to disable row security | WITH CHECK, NOBYPASSRLS non-owner role, FORCE RLS, composite constraints, and no DDL privileges. |
| Owner, SECURITY DEFINER, search_path, function, trigger, or PUBLIC privilege bypass | Separate NOLOGIN owner, hardened functions, fully qualified SQL, revoked defaults, and role-capability tests. |
| Cross-tenant or dangling graph construction, including a future-ID/two-transaction promotion exploit | Same-tenant composite FKs plus same-batch promotion reachability and deferred constraints. |
| JSONB payload reference omitted from relational enforcement or assigned a guessed kind | #174 supplies only the neutral structural carrier and makes no semantic-completeness claim. Exact RuntimeBundle-pinned extraction/kind/cardinality enforcement arrives through #184's reviewed forward migration; dependent runtime surfaces refuse before it exists. |
| Cross-tenant idempotency replay or uniqueness existence oracle | Tenant/principal/operation command namespace and tenant-prefixed unique indexes. |
| Advisory-lock collision, raw session lock, attacker-selected key, unlock, or migration-lock attempt | Raw advisory functions are denied; protected no-key wrappers derive disjoint keys and acquire transaction locks only. |
| Materialization, dependency, cache, trace, gate-log, bound error, or frozen-output leakage | Tenant qualification and RLS apply regardless of authoritative status; pre-tenant errors use only the protected non-tenant audit lane, and readiness exposes no tenant or security-event data. |
| Mutation, substitution, tenant-table mixing of tenant-neutral global content, or global placement of tenant RuntimeBundle state | #171 placement is prerequisite to 0001; the release-owned global installer, one-way membership lanes, tenant-qualified bundle relations, content digest, and canonical-byte equality verification apply. |
| Concurrent, partial, reordered, missing, edited, future, or ledgerless non-empty migration history | Global migration lock, transactional application, immutable checksums, exact readiness, catalog-emptiness proof, and fail-closed dirty detection. |
| Database administrator, migrator, backup, or trusted-binder compromise | Explicitly outside RLS; separate credentials, release controls, audit, and backup governance are required operational controls. |

## Executable adversarial verification plan

The implementation owners named below turn this plan into tests using the real
PostgreSQL roles and real ASGI/application topology, not mocks.

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
9. Exercise the actual provisioned roles: the NOBYPASSRLS application cannot
   read Party without context; the NOLOGIN/NOINHERIT/BYPASSRLS binder can compare
   only the exact signed Party tuple through its fixed function; it cannot be
   inherited, assumed, used through a generic query, or made to return payload.
10. Commit a context row, then attempt reuse under a new full xid8 on the same
    backend; restart the backend; create a stale orphan; and alternate tenants
    through pool reuse. Exact backend-start/xid8 matching always refuses stale
    state, the next challenge or protected sweep removes it, and no completed
    transaction's binding becomes usable again.
11. Revoke, supersede, or expire the active binding before a new UnitOfWork.
    Binding refuses. A capability pinning the old version or lifecycle head also
    refuses after any later lifecycle transition. Attempt to mutate the tenant
    registry, replace the pinned Party record kind/identity/schema/payload
    digests, or use a floating newer Party payload; all refuse. Prove
    tenant/Party deactivate/reactivate is not a V1 transition and a token role
    or caller tenant string cannot create an alternative mapping.
12. Race two ACTIVATE or replacement transitions for one exact-policy (issuer,
    subject). The unique projection reservation serializes them, expected-head
    validation permits only one authoritative active result, and a principal
    spanning two tenants remains unsupported.
13. Under every non-owner role, attempt UPDATE or DELETE of an immutable binding
    version or lifecycle act and direct INSERT of a lifecycle act. Every attempt
    fails; only the hardened transition can append a valid act.
14. Delete the current projection row, then make it stale and corrupt its
    version/head fields under a privileged test fixture. The binder never
    authorizes from it. A privileged rebuild from immutable versions and acts
    deterministically recreates the same unique projection.
15. Resolve current state with the projection absent, and reconstruct state at
    each earlier lifecycle cut after later revocation and supersession. Results
    come only from immutable versions and acts and are unchanged by any
    projection contents.
16. Across verifier, control plane, capability, binder, and PostgreSQL UNIQUE
    behavior, test issuer/subject case changes, leading/trailing/internal
    whitespace, URI variants, composed/decomposed Unicode, invisible/control
    characters, delimiter-like values, maximum and over-limit bytes, and
    equality-policy mismatch. Valid distinct bytes never collapse; rejected
    bytes never reach storage; the same exact bytes never split into two streams.

### Identifier equality and immutable eligibility

1. For issuer, subject, tenant_ref, every tenant-local authored identifier, and
   caller_key, exercise case variants, leading/trailing/internal whitespace,
   ASCII/Unicode boundaries, controls, empty input, exact maximum bytes, and one
   byte over the limit. Each value is either one exact distinct key or a stable
   validation refusal; no layer rewrites it.
2. Prove the same tenant-local identifier can exist in tenants A and B while an
   exact duplicate in one tenant fails. An exact caller key replays; an allowed
   case variant is distinct; whitespace or Unicode variants outside
   `OFARM_ASCII_ID_V1` refuse.
3. Prove `(policy, issuer="ab", subject="c")` and
   `(policy, issuer="a", subject="bc")` cannot collide. JSON escape spellings
   that decode to the same issuer/subject scalars produce the same canonical
   bytes. Golden vectors from #172's verifier and #174's PostgreSQL functions
   must produce identical tagged/lp32 bytes and digests.
4. Provision targets with a non-UTF8 encoding, wrong/default/nondeterministic
   collation, missing/widened domain check, wrong index collation, `citext`, or
   a folding functional index. Provisioning or readiness refuses each before
   repositories are constructed.
5. Register a tenant only through `register_tenant`, then attempt direct INSERT,
   UPDATE, or DELETE under application, worker, readiness, identity-writer, and
   registrar identities. Every attempt fails. Bind to a wrong-kind record, an
   initially INACTIVE Party, altered Party record/schema/payload digest, or
   mutated registry field; every bind refuses and no unsupported eligibility
   transition is exposed.

### RuntimeBundle placement and equality tests

1. Build the reviewed global catalog twice and prove the ordered content
   classes, canonical bytes, lengths, and full digests are identical. Mutate,
   remove, duplicate, or add any descriptor, policy, contract, code,
   validator/adapter/parser, query/plan/output, code-binding, or tenant-neutral
   reference input; startup refuses the stale catalog before serving traffic.
2. Try to install the package tenant-scoped PackActivationSet,
   ActiveArtifactSet, Capability Manifest, ContextSnapshot, or tenant-derived
   reference data through the global installer. Each attempt refuses and
   leaves `runtime_content_blob` unchanged. Direct global-blob DML fails under
   every application, worker, tenant, support, and readiness role.
3. For tenants A and B, install equal and unequal tenant component bytes. Prove
   every tenant blob, bundle, and component key starts with tenant_id, forced
   RLS hides the other tenant, an equal cross-tenant digest grants no sharing,
   and a component cannot target another tenant's blob or bundle.
4. Reuse a global content digest, tenant content digest, and tenant bundle
   digest with one-at-a-time changes to class, canonicalization, bytes, length,
   receipt JSON, storage lane, role, logical ref, or relational inventory.
   Exact replay is a no-op; every unequal reuse refuses atomically.
5. Supply malformed UTF-8, duplicate JSON keys, non-canonical JSON, an unknown
   canonicalization, truncated/uppercase/non-hex digests, path traversal,
   absolute paths, duplicate component identities, and missing/extra rows.
   Installation and cold load fail closed without a partial receipt.
6. Build a tenant bundle from the reviewed global identities plus that
   tenant's exact active-instance, manifest, ContextSnapshot, ReferenceSnapshot
   selection, and `reference_snapshot_data` bytes. Alter any global identity,
   tenant record/payload digest, source identity, data family, or retained byte;
   the bundle digest changes and acceptance under the old bundle refuses.
7. Cold-load after deleting process caches and making repository paths
   unavailable. Reconstruction succeeds only from the exact persisted receipt,
   membership, and blob bytes. Filesystem mutation, tenant-row mutation,
   current selection drift, or a cache keyed only by bundle digest cannot alter
   or satisfy `(tenant_id, bundle_digest)`.
8. Cross a queue or retry boundary after the tenant selects a different bundle.
   The old work refuses unless its exact tenant bundle remains the explicitly
   governed basis; no descriptor default, demo tenant, latest row, or automatic
   migration substitutes the new bundle.

### Pre-tenant operational security audit

1. Trigger missing/malformed credentials, unknown/revoked principal, immutable
   tenant-registry or Party record kind/identity/schema/payload mismatch,
   verifier outage, actor mismatch, security-relevant route rejection,
   capability failure, and binder rejection while supplying tenant A, tenant B,
   and the demo tenant in every request-controlled location. Every durable event
   uses the same closed non-tenant schema, contains no tenant attribution or
   position, and leaves every tenant head and table unchanged.
2. Submit credentials, headers, cookies, bodies, query values, paths, network
   identifiers, user agents, Unicode controls, oversized strings, SQL/JSON, and
   low-entropy identities. None appears raw in the relation, SQL parameters,
   database/access logs, APM, traces, queues, dead letters, crash reports,
   ordinary logs, metrics labels, or health output; unsupported classes and
   wrong digest lengths refuse.
3. Prove event IDs are cryptographically generated inside the trusted producer,
   never from a request; diagnostic time, format/redaction/retention policy, and
   purge bounds are generated inside the hardened append API;
   producer/component derive only from exact `session_user`; and caller attempts
   to alter derived fields fail. Retry the same ID with equal and unequal
   fingerprints before/after clock advance and policy/key rotation; prove the
   exact retry returns the original row while any stable-input change refuses.
4. With the producer alive and audit service available, roll back or abort the
   attempted tenant/binder transaction through exception, handled cancellation,
   serialization failure, and pool return. The tenant transaction publishes
   nothing; the separate audit transaction contains exactly the safe pre-tenant
   event and cannot see tenant data. Process death/unacknowledged cancellation
   belongs to the explicit loss/gap cases in test 9.
5. Complete TenantBinding and then force a durable refusal. The separate audit
   relation remains unchanged; exactly one refusal appears in the bound
   tenant's governed batch and no other tenant changes.
6. Under application, worker, binder, readiness, support, tenant, each distinct
   producer LOGIN, audit-ingest, audit-control, audit-reader, break-glass export,
   retention, and audit-readiness identities,
   exercise SELECT, INSERT, UPDATE, DELETE, COPY, TRUNCATE, function execution,
   SET ROLE, role inheritance, and schema-object creation. Each identity has
   exactly its frozen capability and no combination yields tenant-plus-security-
   audit access or cross-producer attribution.
7. Attempt direct append-function calls with invented producer/reason classes,
   arbitrary messages, request identifiers, wrong-length digests, unknown key
   versions, and attacker-chosen retention. Closed validation refuses. Prove a
   correctly shaped HMAC from a compromised authorized producer is treated only
   as untrusted diagnosis in that producer's allowed class, never as tenant or
   authority evidence. A compromised normal application role cannot call the
   function at all.
8. Flood each public failure surface concurrently. Event size stays bounded,
   the database-enforced bucket keys only on derived producer/component and
   cannot be reset by that producer, `OVERFLOW_STARTED` precedes bounded
   aggregation, and `OVERFLOW_ENDED` records a count or `COUNT_UNKNOWN`. Measure
   the separate audit service's connection/CPU/storage limits and prove tenant
   pool, WAL, volume, and latency remain isolated; pressure never changes denial
   into access. Lose acknowledgement for an aggregated event and prove the
   control path marks the bucket `COUNT_UNKNOWN` idempotently instead of
   retrying a countable append or presenting a double increment as exact.
9. Inject cancellation, process exit, connection loss, ambiguous commit, key-
   service failure, relation/disk failure, and whole-audit-service outage before
   and after append acknowledgement. Requests remain denied, timeouts/retries
   stay bounded, no raw or ungoverned queue fallback is emitted, exact-ID retry
   deduplicates ambiguous commits, and recovery records every known gap or
   `COUNT_UNKNOWN` without claiming lossless/exactly-once delivery. Rotate keys
   and prove each old version is destroyed by its last stamped `purge_after`
   even when row purge is delayed.
10. Test the no-caller-cutoff purge immediately before and after `purge_after`,
    attempt caller-selected cutoffs/IDs and selective deletion, and verify legal
    hold is unsupported. Only the retention capability can delete bounded
    eligible rows; it appends the closed cutoff/count maintenance event in the
    same transaction. With the correlation key service unavailable, maintenance
    kinds still use their governed no-HMAC shape; a pre-tenant failure cannot.
    Before a deliberately delayed purge, every reader/export function already
    hides the expired row and the HMAC key is destroyed at its deadline. Inspect
    heap/WAL behavior and confirm the evidence makes no physical-erasure claim.
    Ingest/reader/application roles cannot mutate or delete.
    Prove tenant backups do not address the audit service; attempts to enable an
    audit backup, replica, logical decoding, CDC, or restore path refuse V1
    readiness. Destroy and recreate only an empty verified audit store and
    record the declared gap without resurrecting expired events.
11. Call every bounded reader function without a committed `AUDIT_ACCESS`
    intent, with a missing/mismatched function/argument/data-cut/cursor, after
    five-minute expiry or read rollback, and while attempting to widen row/byte
    bounds. Only the exact precommitted page succeeds; rollback cannot erase its
    intent, replay/COPY returns no wider unique data, and a new page/cut requires
    a new intent. Exercise break-glass approval, credential expiry/revocation,
    cumulative bounded export, and denial without tenant or HMAC-key access.
12. Prove tenant reconstruction, authorization, RuntimeBundle, materialization,
    qualification, output, support, readiness, and export paths cannot name,
    join, count, or infer the pre-tenant relation.

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
2. Apply each migration set to its proven-empty tenant or audit service and
   verify exact version, checksums, roles, grants, constraints, functions, and
   indexes; forced RLS applies to every tenant-bearing relation and never
   supplies a fake tenant context to the audit service.
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
7. Start the application and audit client against empty, old, exact, newer,
   dirty, crossed, and unavailable tenant/audit schemas. Only the exact matched
   pair among fresh or uninterrupted in-place targets becomes ready, and
   catalog snapshots prove startup performed no DDL.
8. Prove application and readiness roles cannot provision, apply, repair, or
   downgrade a migration.
9. Restore a tenant snapshot ending at K40 after K41-K45 and a principal/grant
   revocation were published. Also try a matching build/digest, PITR/snapshot
   promotion, and one-tenant history import. Prove V1 exposes no recovery
   promotion/readiness procedure and starts no capability minting, binder,
   allocator, repository, release, outbox, or delivery path. Matching schema is
   insufficient and the old K41 cannot be republished. Separately destroy the
   audit service, rebuild only an empty exact-version store, append the declared
   gap where possible, and prove no backup/replica/expired event is restored
   before any operational-readiness claim.

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

### Mutable tenant or Party active flags as authentication authority

A mutable registry flag or floating `partyState` lookup would affect binding
without an append-only authority history and could not reconstruct an earlier
decision. It is rejected. V1 pins immutable tenant-registry and ACTIVE Party
record digests into the binding version and stops access through the governed
principal-binding lifecycle. Tenant-wide suspension or Party eligibility
transitions require a later lifecycle decision.

### Implicit principal or identifier normalization

Trimming, case folding, URI rewriting, Unicode normalization, locale collation,
or delimiter-joined composite keys can split or merge authority streams across
the verifier, control plane, and database. They are rejected in favor of closed
validation policies and exact deterministic byte equality.

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
reinterpret durable truth. Both are rejected. Tenant correction is forward-only
in V1; the audit store separately has only the empty-recreate/gap posture above.

### Restore a tenant-service backup with the matching build

Matching application and migration digests prove compatibility, not continuity.
An older image can reuse a published knowledge position, erase revocation and
idempotency tails, and fork an already released output. V1 rejects recovery
promotion until #193 supplies a non-rewindable external witness and complete
reconciliation.

### Import one tenant's old database history

The shared service contains global principal/tenant control state and
cross-cutting knowledge, receipt, sharing, and release invariants. Splicing one
tenant's old rows cannot honestly preserve them. Tenant-history logical import
is unsupported; ordinary domain imports must enter new governed batches.

### An N-minus-one compatibility window now

Nothing is deployed, so dual behavior would add risk without preserving a real
consumer. It is rejected. The first window is exact-version only.

## Consequences and follow-on ownership

This decision deliberately makes the current implementation fail its future
tenancy and migration tests until the dependent tickets land.

- #169 and this ADR own only the architecture decision: classification, closed
  event shape, trust/access boundary, privileges, independent-commit/failure
  posture, retention/redaction rules, producer classes, and verification plan.
  The documentation-only guardrail authorizes no implementation.
- #172 supplies explicit production authentication and verifier behavior, the
  governed control-plane integration for immutable principal-binding versions,
  append-only lifecycle transitions and deterministic projection rebuild,
  exact-principal equality enforcement, immutable V1 tenant/Party eligibility
  validation, and the trusted TenantCapability issuer/verifier boundary. #174
  is its database-primitives prerequisite and supplies the classified storage
  and hardened functions. #172 does not own durable pre-tenant audit emission.
- #173 follows #172 and #174. It supplies the pool, UnitOfWork, application call
  to #174's one-use challenge/binder functions, exact digest propagation,
  transaction finalization/rollback, pool-idle enforcement, and write-batch
  allocation. It does not own the context DDL, separate audit connection, or
  producer integrations.
- #174 follows #168, #169, and #171 and is independently closeable before #172
  and #173. It supplies the one-time provisioning specification, exact role
  attributes and grants, immutable tenant/audit migration baselines, equality
  domains/collations, the release-owned tenant-neutral global content carrier,
  tenant-qualified RuntimeBundle content/receipt/membership relations and
  one-way content foreign keys, immutable registry and insert-only registrar,
  principal storage, NOLOGIN BYPASSRLS binder,
  challenge/context/current-tenant functions, forced RLS,
  composite keys, the neutral reference carrier and settled structural graph
  constraints, protected lock wrappers, separately bounded audit
  service/relations, producer LOGIN/session map/reason allowlist, hardened
  audit functions, resource limits, direct-SQL/catalog tests, runners, and
  structural readiness. It does not implement #172 verifier integration, #173
  application/pool integration, #184's semantic relationship matrix, #192's
  audit runtime, or #193 recovery.
- #192 owns the end-to-end pre-tenant audit implementation: isolated client and
  connection/credentials, use of the provisioned producer identities,
  closed-outcome-to-reason integration, HMAC/redaction/key-service lifecycle,
  authentication/verifier/principal/tenant/Party/capability/routing/binder/actor
  producers, bounded delivery and gap/overflow orchestration, runtime audit-
  health/readiness threshold, security-operations and retention execution,
  post-binding switch, and hostile ASGI tests. It consumes #172/#173 outcomes
  and #174 storage; those tickets do not gain that ownership by reference.
- #176 depends on #192 for this boundary and must not reuse a tenant relation,
  infer a tenant, or claim the lane exists before #192 lands.
- #171 is a prerequisite to #174: it supplies the tenant-neutral global content
  catalog, tenant RuntimeBundle receipt and component model, exact-byte
  equality/cold-load verification, and the one-way global-versus-tenant
  placement map required before 0001 is frozen. It does not turn package
  tenant fixtures into global activation authority.
- #177 completes the within-tenant sharing and output-authorization gate.
- #178 implements content-bound, result-complete command idempotency inside the
  exact `OFARM_ASCII_ID_V1` caller-key namespace frozen here and exposes the
  durable identities/receipts later recovery must reconcile.
- #184 supplies the complete reference extraction and semantic relationship
  matrix in a forward migration after #174's neutral structural carrier. Until
  that matrix is accepted, no ticket can invent or claim complete payload-
  reference kind/cardinality enforcement.
- #193 owns any later non-forking tenant-service recovery or tenant-history
  import design. It does not block #174's safe negative V1 posture, but it
  blocks destructive migrations, recovery promotion, and recovery-readiness
  claims.
- #185 must make scheduled reference source bytes durable before
  `reference_snapshot_data` can honestly be treated as disposable cache.
  Exact selected derived bytes retained in `runtime_tenant_content_blob` remain
  tenant-owned reconstruction inputs and never become global content.

No implementation ticket may claim that closing these persistence mechanics
changes OFARM law, activates a profile, or proves a higher capability.

## Acceptance traceability

| Issue #169 criterion | ADR section |
|---|---|
| Classify every table | Relation classification |
| Trusted immutable principal source, immutable V1 tenant/Party eligibility, non-authoritative current projection, transaction context lifetime, and no production default | Governed principal source; Unforgeable transaction binding |
| Exact identifier equality, idempotency-key, advisory-lock, and uniqueness namespaces | Identifier and uniqueness namespaces; Protected advisory locks |
| Tenant-qualified FKs, graph rules, cross-tenant references, and sharing | Foreign keys, normalized reference carrier, graph rules, and sharing boundary |
| Roles, forced RLS, migration privileges, and direct-SQL posture | Database roles and row-level security; One-time infrastructure provisioning |
| Immutable numbered baseline, forward-only correction, no unsafe V1 recovery, compatibility, and readiness | One-time infrastructure provisioning; Immutable migration baseline; Startup, readiness, compatibility, and rollback |
| Startup verifies schema and performs no opportunistic DDL | Startup, readiness, compatibility, and rollback |
| Threat model and adversarial pool/join verification | Threat model; Executable adversarial verification plan |

## Validation for this architecture decision

- Preserve the nine-relation #169 prototype inventory above, then verify the
  #171 target map adds exactly `runtime_content_blob`,
  `runtime_tenant_content_blob`, `runtime_bundle`, and
  `runtime_bundle_component`, with only the first globally governed.
- Verify the initial-migration design gives every tenant RuntimeBundle relation
  a tenant-leading key and forced RLS, gives membership exactly one global or
  same-tenant content target, and gives global content no tenant back-reference.
- Verify every current package/runtime input appears exactly once in the
  placement map and that tenant-scoped PackActivationSet, ActiveArtifactSet,
  Capability Manifest, ContextSnapshot, and derived reference bytes are absent
  from the global catalog.
- Verify every acceptance criterion maps to a section in the traceability table.
- Run the package contract check and profile extraction-consistency check.
- Run the repository whitespace/diff check.
- Confirm the implementation changes neither manifests nor active artifact sets,
  activates no profile, claims no capability, and does not relabel SI as RS.
