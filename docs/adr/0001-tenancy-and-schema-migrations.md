# ADR 0001: Tenancy and schema-migration architecture

- Status: Accepted for implementation
- Date: 2026-07-10
- Decision issue: GitHub #169
- Parent: GitHub #167
- Depends on: GitHub #168
- Implementation coordination: GitHub #172, #173, #174, and #192
- Accepted TenantCapability trust-model refinement: ADR 0003, accepted through
  GitHub #200. It refines the cryptographic transport and key lifecycle without
  transferring the implementation ownership below.
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
| kernel_record | Tenant-owned | Primary identity is (tenant_id, record_id). There is no tenant default. Every emitted record carries its governed write-batch identity. Package or global content may not be mixed into this relation. |
| kernel_edge | Tenant-owned | The edge, source, and destination share tenant_id. Both endpoints have composite foreign keys. The edge carries the batch that emitted it. Promotion reachability additionally requires edge, trace, and emitted record to share one batch. |
| kernel_gate_log | Operational metadata, tenant-scoped and durable | Every entry carries tenant_id, batch identity, and request identity. It remains append-only audit evidence and is not disposable logging. |
| kernel_idempotency | Operational metadata, tenant-scoped and durable | Its unique command identity is (tenant_id, authenticated_principal_ref, governed_operation, caller_key). Its durable result reference stays in the same tenant. |
| derived_materialization | Derived/cache | All keys start with tenant_id. Basis, snapshot, context, and supersession references are same-tenant composite references. At most one unsuperseded row exists for an exact materialization key. Regeneration inserts a new generation and atomically supersedes the prior live generation; generation content and batch provenance are fixed for each row's lifetime. Application and worker roles may directly degrade `freshness` only along `FRESH -> STALE`, `FRESH -> INVALID`, or `STALE -> INVALID`; only hardened generation publication may create a new `FRESH` generation, and supersession is available only through that function. Deleting cache state must not delete its proof or source truth. |
| derived_dependency_index | Derived/cache | Dependency sources and materialization keys are tenant-qualified. It may not invalidate or reveal another tenant. Polymorphic references become typed and constrained rather than unverified text. |
| reference_snapshot_data | Derived/cache, with a rebuildability precondition | Primary identity is (tenant_id, snapshot_ref, data_family), with a same-tenant snapshot reference. It is deletable only after durable source bytes and deterministic rebuild are proven; #171 and #185 own that closure. |
| runtime_trace | Operational metadata, tenant-scoped and durable | Primary identity is (tenant_id, trace_id). Every trace carries its write-batch identity, remains append-only, and is not treated as a disposable cache. |
| export_artifact | Tenant-owned | Primary identity is (tenant_id, artifact_ref). The metadata/output-receipt reference is same-tenant. Document content is never placed in globally shared storage. |

There is no globally governed database relation in the current schema. Package
schemas and other repository files are global inputs, not database relations.

### Required support relations

| Future relation | Classification | Frozen target rule |
|---|---|---|
| tenant_registry | Globally governed immutable V1 registry | Maps an internal immutable UUID tenant_id to one unique, bytewise-equal external tenant_ref, a row digest, and a database-assigned advisory-lock key. V1 has no mutable active flag, tenant retirement transition, or tenant eligibility lifecycle. Direct DML is forbidden; one hardened insert-only registrar creates rows. |
| principal_binding | Globally governed immutable authorization versions | One immutable candidate version maps the exact-policy (issuer, subject) bytes to (tenant_id, party_ref), pins the immutable tenant-registry digest and exact ACTIVE Party record identity/schema/payload digests, and carries an equality-policy identity, version identity/digest, and validity metadata. Repeated principal keys are expected; no mutable lifecycle state or partial ACTIVE uniqueness lives here. It is the only initial global authority relation allowed to reference a tenant-owned Party. |
| principal_binding_lifecycle | Globally governed append-only authorization authority | A digest-chained stream of ACTIVATE, REVOKE, EXPIRE, and SUPERSEDE acts names immutable binding versions, the prior lifecycle head, effective and decision data, accountable control identity, and reason. These acts, together with immutable versions, are the sole source for current and historical binding state. |
| principal_binding_current | Optional derived/disposable global control projection and reservation | A unique (equality_policy, issuer, subject) row points to the computed active version and lifecycle head, or records the computed inactive state. It serializes transitions and accelerates lookup, but is rebuildable and never authoritative. |
| tenant_binder_instance | Globally governed immutable binder installation identity | One fresh-provisioning singleton stores a random installation UUID, exact derived binder audience, creation evidence, and canonical row digest. It is not recovery-continuity proof. Direct DML is forbidden. |
| tenant_capability_verification_key | Globally governed immutable public-key candidates | Stores only exact Ed25519 public material, content-derived key identity, binder audience, accepted KMS/HSM evidence, candidate identity/time, and canonical row digest. Existence is not authority. |
| tenant_capability_key_lifecycle | Globally governed append-only capability-key and admission authority | A digest-chained stream of ACTIVATE, ROTATE, CLOSE_ADMISSION, REVOKE, and RESUME_ADMISSION acts plus ADR 0003's fixed database-time rules is the sole capability-key and binder-admission authority. |
| tenant_capability_keyring | Disposable global capability-key reservation/projection | One row per binder audience is a row-lock fence and projected current key/admission head. It cannot provide advisory-lock fairness or authorize independently of the complete lifecycle fold and fixed time rules. |
| tenant_binding_context | Protected disposable transaction operational metadata | An UNLOGGED migration-owned relation stores the one-use challenge and verified TenantBinding for exactly one database-derived backend identity and full xid8. Exact backend-start/full-transaction matching makes a physically retained row unusable after commit, rollback, backend restart, or pool reuse. Only hardened functions may read or write it; the application role has no table privileges. |
| runtime_content_blob | Globally governed immutable content carrier | Stores exact content-addressed package/reference bytes. Application and worker roles may read but cannot publish these rows. A row is inert until a sealed tenant RuntimeBundle names its exact digest and byte length. |
| runtime_tenant_content_blob | Tenant-scoped immutable content carrier | Stores exact content-addressed bytes for tenant runtime selection under forced RLS. Existence is not runtime authority; only a sealed RuntimeBundle component can select a row. |
| runtime_bundle | Tenant-scoped immutable provenance root | Stores the exact canonical RuntimeBundle identity document under its full digest. Ordinary application and worker roles have read-only access. The dedicated startup publisher is the only provisioned non-owner role that can invoke the closed atomic publication function; direct INSERT is denied. |
| runtime_bundle_component | Tenant-scoped immutable bundle membership | Stores exactly the component identities selected by one RuntimeBundle. The atomic publisher installs the complete set with the bundle row. No runtime role can append a component before or after a governed batch references the bundle. |
| operational_security_event | Database-global operational security metadata, explicitly non-tenant | Append-only, bounded pre-tenant failure events plus audit-access, retention, and declared-gap maintenance events for this lane. It carries no tenant_id, tenant_ref, Party/farm/role identity, governed batch, knowledge position, or request-supplied attribution. It lives only in the separately provisioned audit PostgreSQL service's protected `ofarm_security` schema and is never read as tenant history. |
| operational_security_access_clock_high_water | Durable non-tenant authorization control state | One owner-only bigint sequence stores the greatest database wall-clock microsecond observed by the audit-access protocol. A function-scoped session advisory mutex serializes observation and is released before the caller regains control. Advancement is nontransactional, so a rejected or rolled-back read cannot erase an observed expiry crossing. Normal APIs never decrease it; an observed clock regression fails closed. It contains no request, tenant, principal, correlation, or evidence data. |
| operational_security_quota_bucket | Disposable non-tenant operational security control state | One fixed database-time bucket per provisioned producer/component records accepted and overflow counts plus marker state. Only hardened audit functions mutate it. It contains no request, tenant, principal, correlation, or evidence data and cannot authorize anything. |
| operational_security_quota_high_water | Durable bounded non-tenant operational security control state | At most one row for each of the two fixed producer/component pairs records the latest closed quota minute. It survives bucket deletion and makes a backward wall-clock step fail closed instead of recreating a closed bucket. It contains no request, tenant, principal, correlation, or evidence data and cannot authorize anything. |
| operational_security_event_identity_lock | Fixed non-tenant operational mutex state | Exactly 256 migration-created lock stripes serialize same-ID append attempts before database time and quota selection. The table stores no event ID, fingerprint, request, tenant, principal, correlation, or evidence data; a stripe collision only reduces concurrency and cannot authorize anything. |
| operational_security_overflow_identity_receipt | Fixed bounded non-tenant overflow retry state | Exactly 256 migration-created receipt slots for each of the two fixed producer/component pairs retain an exact overflow event ID, its append fingerprint, bucket, and retention bound. A slot collision makes the affected bucket `COUNT_UNKNOWN` instead of evicting exact evidence. The relation has no tenant, principal, request, raw correlation, or authorization data and cannot grow beyond 512 rows. |
| schema_migration | Database-global operational metadata | Append-only ledger of version, filename, SHA-256, application/release identity, and applied time. Application access is read-only for readiness. |
| governed_write_batch | Tenant-owned | Primary identity is (tenant_id, batch_id). It anchors the transaction's command identity and the records, edges, traces, gate entries, and receipts emitted by that command. Runtime insertion requires authenticated_principal_ref to equal the protected transaction binding's party_ref; it is not caller-selected attribution. |
| kernel_record_reference | Tenant-owned relational enforcement carrier | Normalizes governed references extracted from immutable JSONB payloads without changing those payloads. Owner and tenant targets use composite tenant keys; global-content targets use a distinct constrained lane. |

Any later relation must be classified before its migration is accepted. A future
RuntimeBundle or other shared-content relation may be globally governed only if
its bytes are immutable and content-addressed, it contains no tenant truth, and
identifier equality verifies the canonical bytes.

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
`1`. The database sets `purge_after` to exactly 2,592,000 seconds after
`observed_at`; this duration is independent of the session time zone and
daylight-saving transitions.
Changing a domain, accepted key version, or either policy requires a reviewed
forward migration and applies only to newly appended rows; it never rewrites
existing evidence.

`SECURITY_DIAGNOSTIC_30D_V1` is an exact live/query-visible retention policy,
not a claim of physical erasure from PostgreSQL heap pages, local WAL, storage
snapshots, or retired media at the same instant. Every bounded query and export
first requires its committed access intent to be unexpired at the freshly
observed database time. Target-event membership is frozen when that intent is
created: only rows whose immutable `purge_after` is strictly later than the
intent's fixed `access_expires_at` can appear. A backward wall-clock step during
reuse therefore cannot re-admit a row excluded from that page, and an event is
undisclosable for the entire permitted reuse window before its retention
deadline even if the bounded purge job lags. Because
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
Every event writer takes a protected relation-level writer lock before deriving
its database time or bucket. Overflow close takes the mutually exclusive
transaction-level writer barrier before checking the current bucket and holds
it through the end marker, a durable high-water advance, and bucket deletion. A
writer admitted before close must therefore commit before its old bucket can
close. A writer admitted after close refuses any derived bucket at or below the
pair's closed high-water, so a backward wall-clock step cannot recreate the old
key. The high-water relation is bounded to the two fixed producer/component
pairs and is not a general clock, ordering, continuity, or recovery service.
Connection limits, statement timeouts, reserved marker capacity, service-level
CPU/storage limits, and growth alerts are provisioned independently of tenant
traffic. A compromised producer cannot select or reset its bucket. Exhausting
the audit service is an accepted denial/readiness availability risk, never an
authorization bypass or tenant-storage exhaustion path.

Before policy, database-time, or quota evaluation, an append hashes all 16
canonical UUID bytes and maps the first SHA-256 octet to one of 256 fixed
migration-owned mutex rows, takes that row `FOR UPDATE`, and rechecks both the
event relation and fixed overflow receipts while holding the lock through
transaction end. Append transactions must use `READ COMMITTED`; the append
function refuses every fixed-snapshot isolation level before acquiring the
mutex or reading either outcome relation. Each post-wait recheck can therefore
observe the preceding same-ID transaction's committed event or receipt.
Concurrent same-ID attempts therefore cannot split one logical event between an
individual row in one minute and an exact overflow count in another. No event
ID or fingerprint is persisted in the mutex table; unrelated IDs sharing a
stripe can only wait for one another.

An overflow result is exact only when its event ID and full append fingerprint
occupy the corresponding fixed receipt slot for that producer. An equal retry
returns the original overflow bucket without incrementing it; a changed retry
refuses. A different ID whose derived slot is occupied never evicts the older
exact receipt: the current bucket becomes `COUNT_UNKNOWN` and its now-unneeded
receipts are cleared. Exact receipts survive bucket close through the matching
`OVERFLOW_ENDED` marker's retention lifetime and are cleared only after that
exact marker is gone. Control-declared unknown posture clears the affected
receipts immediately. The fixed 512-row grid therefore preserves exact retry
semantics when it has evidence and otherwise makes uncertainty explicit without
unbounded event-identity storage.

#### Read, retention, replica, and backup boundary

Ingest and reader roles receive no table SELECT or COPY privilege. A dedicated
security-operations service first commits an `AUDIT_ACCESS` intent through its
separate audit-control transaction, binding the closed purpose, exact bounded
query function, every argument, database-observed data cut, cursor/page, row and
byte ceiling, and a five-minute expiry. The intent also persists a PostgreSQL
MVCC snapshot. The audit-control transaction must use `READ COMMITTED`;
`commit_audit_access_intent` refuses higher isolation before capturing either
value, so a caller cannot combine a later wall-clock cut with a transaction
snapshot frozen earlier. After validating the closed request, the function
takes the same migration-owned `SHARE ROW EXCLUSIVE` event-writer barrier used
by retention and overflow close. Previously admitted writers finish before a
fresh snapshot and wall-clock cut are captured; later writers wait until the
intent transaction commits. Access-clock observation is serialized with one
provisioning-owned, function-scoped session advisory mutex. The helper releases
that mutex before the outer caller regains control, so a reader, exporter, or
controller cannot retain it merely by keeping its transaction open. The audit
schema owner can execute only no-argument take/release wrappers whose fixed key
is embedded by provisioning. A separate NOLOGIN/NOINHERIT access-clock lock
owner with no members or role-assumption path owns those wrappers and alone has
the exact raw session-lock and unlock grants. The audit schema owner, migrator,
and runtime logins have no raw advisory-lock authority. The helper
advances an owner-only bigint sequence to the greatest observed database-time
microsecond. Sequence advancement is not rolled back with its calling
transaction. A new intent refuses whenever current database time is behind
that high-water mark. Every event stores its top-level `xid8`, and the
bounded reader intersects the timestamp cut with `pg_visible_in_snapshot`.
A transaction ordered before the cut is visible in the persisted snapshot, and
a transaction ordered after the cut is outside both boundaries. The snapshot
is internal control metadata and is not exposed in the event-report result.
Only then may its distinct reader session call that migration-owned function
with the committed access event ID; the function verifies the exact scope
fingerprint before returning that one bounded page. Rollback of the read cannot
erase either the already-committed access intent or an access-clock advance.
Both normal query and break-glass export compare expiry with the non-regressing
high-water mark. Once an observation reaches the intent deadline, that intent
remains expired; a later backward wall-clock step cannot resurrect it. An
observed clock regression before expiry also refuses rather than extending the
authorization window. PostgreSQL has no independent monotonic elapsed-time
authority here, so V1 explicitly trusts the database wall clock not to pass an
intent deadline and roll back before any access-protocol observation occurs.
Such an unobserved excursion cannot be distinguished from ordinary time by the
database. #192 owns external clock-health fencing if deployment cannot satisfy
that trusted operating-system prerequisite.
Reuse can return only the same cut/page/ceiling and cannot widen unique data. Retention cannot reveal a
replacement row: `purge_after` is constrained to exactly
`observed_at + 2,592,000 seconds`, target eligibility requires `purge_after` later than
the intent's fixed `access_expires_at`, and the page is ordered by `observed_at`
descending before `LIMIT`, independent of wall-clock reversal or whether
physical deletion has run. A new page or later cut needs a new intent. Function
results
can still be copied or repeatedly retrieved, so the reader is explicitly a
privileged, export-capable boundary within the precommitted bound, not a
no-exfiltration role. Direct table or unbounded extraction is unsupported. A
break-glass export
requires a separately provisioned, time-bounded export LOGIN, dual approval, an
exact purpose and cumulative result bound, and a committed `AUDIT_ACCESS`
event; it never grants tenant access or digest-key access. Normal provisioning
installs only the NOLOGIN `ofarm_security_audit_export` capability and
intentionally creates no break-glass export LOGIN or membership. #192 may open
an approved temporary export window, but the presence of that LOGIN or its
membership intentionally makes the audit lane structurally incompatible. #192
must independently treat the window as runtime-unhealthy. After the bounded
export, the temporary LOGIN must be dropped and the exact normal role/membership
posture reverified before structural compatibility can return. #192 owns that
operational window, its approvals, audit acts, credential handling, and closure.

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

RuntimeBundle publication is a startup-only capability. Provisioning creates
the NOLOGIN `ofarm_runtime_bundle_publisher` capability and one separately
credentialed `ofarm_runtime_bundle_control_login` with only inherited,
non-assumable membership (`INHERIT TRUE`, `SET FALSE`, `ADMIN FALSE`). The
trusted operating-system startup process uses that login after it has built and
validated the Python RuntimeBundle. Application and worker roles cannot execute
the publication function and have no INSERT privilege on `runtime_bundle` or
`runtime_bundle_component`.

`publish_runtime_bundle` receives the tenant, expected full digest, and exact
identity document. It accepts only the closed V1 document shape, a non-empty
bounded component array in canonical `(role, logicalRef)` order, closed roles,
canonicalization and placement values, canonical bounded byte lengths, and
content digests whose exact bytes already exist in the appropriate immutable
carrier. It reconstructs the canonical identity bytes itself, compares their
SHA-256 digest with the expected digest, locks the immutable tenant-registry
row, and inserts the bundle plus its complete component set in one statement
and transaction. An exact replay is an idempotent no-op; unequal reuse refuses.

The bundle row's existence is its immutable seal. There is no mutable sealed
flag, draft bundle state, hot reload, or same-process defensive machinery. A
governed batch has a composite foreign key to that row, which cannot become
visible without the same publication statement also completing every component
insert. Because no non-owner role has direct component INSERT, membership
cannot be appended after publication or first use. Complete semantic validation
remains in the already trusted Python publisher boundary accepted by #171;
arbitrary code execution in that process, database-owner/migrator use, or DBA
compromise remains outside the ordinary-role SQL threat boundary.

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

In production, #172's authentication boundary verifies the external OIDC
token's issuer, audience, signature, algorithm, expiry, not-before time, key
identity, and the exact (issuer, subject) identity under the binding version's
equality policy. It does not pass a raw tenant identifier to SQL. After #173
begins one UnitOfWork on one checked-out backend, binding proceeds as follows:

Accepted ADR 0003 freezes the TenantCapability transport,
verification-material, bounded validity, rotation, revocation, and compromise-
response choices used by this flow. It does not move the boundary: #172 owns
authentication, principal-lifecycle integration, capability minting, and
signer custody; #174 owns the database verification material and schema plus
the hardened challenge, binder, current-context, roles, grants, and direct
PostgreSQL tests; and #173 owns the same-backend UnitOfWork sequence.

1. A hardened owner function creates a cryptographically random one-use
   challenge bound to the current backend identity and full transaction
   identity in protected transaction context.
2. The trusted authentication boundary mints a short-lived TenantCapability
   containing that challenge, binder audience, equality-policy identity, exact
   issuer and subject, immutable binding-version identity and digest,
   lifecycle-head act identity and digest, tenant_id, tenant-registry digest,
   party_ref, pinned Party record-kind identity, record identity, schema digest,
   and payload digest,
   issued/expiry times, and a unique nonce. The capability is signed
   by a key unavailable to the application database role.
3. #174's hardened binder independently verifies the exact signed capability
   with the accepted database verifier and enforces the audience, expiry,
   backend/transaction challenge, nonce, exact immutable version bytes and
   digest, and the authoritative lifecycle head and currentness reconstructed
   from immutable acts. The binder may use
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

Accepted ADR 0003 selects those previously deferred choices and preserves the
ownership split above. Production binding remains fail-closed and unavailable
until the required #172, #173, and #174 implementation and evidence pass.

The bootstrap path is explicit. `tenant_registry`, `principal_binding`,
`principal_binding_lifecycle`, `principal_binding_current`,
`tenant_binding_context`, and `schema_migration` are non-tenant control or
operational relations and are not
given tenant RLS policies. They are protected by ownership, relation privilege
denial, and migration-checksummed hardened functions. Every tenant-bearing
relation, including the Party-bearing `kernel_record`, remains under enabled and
forced RLS.

The hardened binder executes as `ofarm_binder`, provisioned `NOSUPERUSER`,
`NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, `NOLOGIN`, `NOINHERIT`, and
`BYPASSRLS`. No LOGIN role is a member, no `SET ROLE` or admin path to it is
granted, and it has only the relation/column privileges required
to reconstruct one principal stream and compare the exact tenant-registry and
Party tuple named by that binding. Its fixed, schema-qualified SQL accepts no
table, column, predicate, tenant, or Party selector other than the signed and
database-matched binding tuple; it returns no tenant row or Party payload. Once
#174 installs the accepted binder, the application receives EXECUTE only on the
exact challenge, binder, and current-context functions. There is no generic
query/dynamic-SQL function owned by this role.
Compromise of `ofarm_binder` is therefore an explicit privileged-boundary
compromise outside RLS, while possession of application credentials or raw SQL
cannot exercise its bypass as a general tenant-data read path.

Backend-incarnation observation is isolated from that binder authority.
`ofarm_backend_observer` is a NOLOGIN, INHERIT, NOBYPASSRLS role whose sole
membership is `pg_read_all_stats` with `INHERIT TRUE`, `SET FALSE`, and `ADMIN
FALSE`. PUBLIC SELECT on `pg_catalog.pg_stat_activity` and PUBLIC EXECUTE on the
complete PostgreSQL 17 family of `pg_stat_get_activity(integer)` plus the 13
`pg_stat_get_backend_*` routines are revoked in both services. The audit
service grants no replacement. The tenant service grants the observer only
SELECT on that exact view and EXECUTE on `pg_stat_get_activity(integer)`, in
addition to its predefined-role membership. The observer owns only two
fixed-search-path SECURITY DEFINER helpers: one returns the current session's
backend start and one answers whether one exact `(backend_pid, backend_start)`
incarnation is live. PUBLIC and every runtime role have no EXECUTE on those
helpers; only `ofarm_binder` may call them. The helpers return no query text,
role inventory, or generic statistics. Neither privileged NOLOGIN role can be
inherited or assumed by a LOGIN role, so same-login raw SQL has no direct
backend-observation path.

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

V1 uses two closed equality policies. They validate or reject input; neither
rewrites it.

| Namespace | Policy and canonical bytes | V1 grammar and bound | Database equality |
|---|---|---|---|
| OIDC issuer | `OIDC_EXACT_UTF8_V1`: UTF-8 encoding of the verified decoded `iss` JSON string exactly as received | 1-2048 UTF-8 bytes; configured case-sensitive `https` issuer URL with host, optional port/path, and no query, fragment, NUL, or control character | Exact bytes; no trimming, case folding, percent/host/path rewriting, Unicode normalization, or discovery-alias substitution |
| OIDC subject | `OIDC_EXACT_UTF8_V1`: UTF-8 encoding of the verified decoded `sub` JSON string exactly as received | 1-255 visible ASCII bytes, as required by the V1 OIDC profile; no whitespace, control, or NUL | Exact case-sensitive bytes; no trimming, folding, or Unicode transformation |
| External `tenant_ref` | `OFARM_ASCII_ID_V1`: the authored ASCII bytes | 1-255 bytes matching `[A-Za-z0-9._:-]+` | Exact bytes |
| Tenant-local authored identifiers, including record, Party, farm, scope, request, trace, batch, artifact, snapshot, materialization, and reference keys | `OFARM_ASCII_ID_V1`: the contract-validated authored ASCII bytes | 1-255 bytes matching `[A-Za-z0-9._:-]+`; a narrower contract grammar still applies where defined | Exact bytes inside the tenant-qualified composite key |
| Idempotency `caller_key` | `OFARM_ASCII_ID_V1`: the contract-validated authored ASCII bytes | 1-255 bytes matching `[A-Za-z0-9._:-]+` | Exact bytes inside the full idempotency identity; no transport-layer rewriting |
| Principal lifecycle stream and current reservation | Separate equality-policy, issuer, and subject columns; digest input uses tag plus unsigned length-prefixed field bytes | Exactly the issuer/subject rules above | One composite exact-byte key; delimiter concatenation and digest-only equality are forbidden |

Accepted ADR 0003's bounded byte grammar is the exact V1
meaning of the issuer/subject rows above. It narrows `host`, port, path, and
visible-subject syntax without normalization and requires identical independent
live-PostgreSQL and #172 outcomes; neither a wider SQL regex nor a platform URL
parser may define authority.

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
64-bit advisory-lock key. The migration lock instead uses one fixed pair of
signed 32-bit integers derived from its checked-in domain tag. PostgreSQL keeps
the two-integer advisory-lock namespace disjoint from the single-bigint
namespace, so the migration lock cannot collide with tenant keys. Human-readable
tenant references and truncated hashes are not advisory-lock identities. Only
the protected wrappers defined below may use these keys. Any later resource-lock
family must reserve a disjoint namespace before use.

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

- ofarm_crypto_installer: a dedicated
  NOLOGIN/NOINHERIT cluster-superuser boundary with exact catalog flags
  `SUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, and
  `NOBYPASSRLS`; it has no members or runtime/migrator assumption path and owns
  only the locked `ofarm_crypto` schema, `ofarm_ed25519` extension, and its one
  verification function. A separately authenticated cluster DBA assumes it
  only during reviewed provisioning; both are outside RLS;
- ofarm_owner: NOLOGIN owner of tenant/application schemas, tables, policies,
  and ordinary functions, explicitly excluding the isolated `ofarm_security`
  objects, the `ofarm_crypto` objects accepted by ADR 0003, the narrowly
  binder/backend-observer/graph-validator-owned functions, and the tenant-write
  lock wrapper;
- ofarm_migrator: release-only credentials allowed to take the migration lock
  and apply reviewed DDL through the applicable application or security-audit
  owner role, with no runtime ingest/read/retention authority and no raw
  advisory-function EXECUTE;
- each service has one provisioning-declared migration-lock owner: a
  NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOLOGIN, NOINHERIT,
  NOBYPASSRLS role with no members or role-assumption path. It owns exactly that
  service's `ofarm_infrastructure` schema and permanent migration-lock wrapper,
  and is the sole provisioned role that receives raw EXECUTE on
  `pg_catalog.pg_advisory_xact_lock(integer, integer)`; it has no table,
  application, binder, audit, migration, or other raw advisory-lock authority;
- ofarm_tenant_lock_owner: NOSUPERUSER, NOCREATEDB, NOCREATEROLE,
  NOREPLICATION, NOLOGIN, NOINHERIT, and NOBYPASSRLS, with no members or
  role-assumption path. It owns only the no-argument tenant-write wrapper and is
  the sole provisioned role that receives raw EXECUTE on
  `pg_catalog.pg_advisory_xact_lock(bigint)`. It has only application-schema
  USAGE, EXECUTE on the no-argument current-context function, and column SELECT
  on the tenant registry's tenant identity and advisory-lock key needed by that
  static wrapper; it has no schema ownership, other table privilege, binder
  authority, migration lock, or other raw advisory-lock authority;
- ofarm_app: non-owner application role with NOBYPASSRLS, no DDL, no owner or
  migrator membership, and only required DML;
- ofarm_worker: same isolation posture as the application, with an explicit
  TenantBinding per job;
- ofarm_runtime_bundle_publisher: NOLOGIN, NOINHERIT, NOBYPASSRLS startup
  capability with EXECUTE only on the closed atomic RuntimeBundle publication
  function and no direct bundle/component DML;
- ofarm_runtime_bundle_control_login: separately credentialed trusted-startup
  LOGIN with NOBYPASSRLS and a sole `ofarm_runtime_bundle_publisher` membership
  using `INHERIT TRUE`, `SET FALSE`, and `ADMIN FALSE`; it has no application,
  worker, binder, owner, migrator, identity, or tenant-registration authority;
- ofarm_tenant_registrar: NOLOGIN control-plane capability granted only to one
  separately provisioned tenant-control LOGIN with `INHERIT TRUE`, `SET FALSE`,
  and `ADMIN FALSE`; it has EXECUTE only on the insert-only `register_tenant`
  function, no direct relation privileges, application membership,
  binding/lifecycle authority, or tenant reads;
- ofarm_binder: NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOLOGIN,
  NOINHERIT, BYPASSRLS privileged function owner used
  only by the hardened challenge, binder, and current-context functions
  installed by #174. It has
  no members or role-assumption path and only the exact column/relation rights
  needed to read immutable binding versions, authoritative lifecycle acts,
  optional current projection, tenant registry, one pinned Party record, and
  transaction context. The application may EXECUTE those closed functions but
  cannot SET ROLE to this role or obtain generic tenant reads. ADR 0003 adds
  only the exact binder-instance, verification-key, key-lifecycle,
  keyring-fence, and verify-function access named there. It leaves this role,
  its database verification material/schema, and all three migration-owned
  functions under #174; #172 owns capability minting and signer custody, not
  this database role;
- ofarm_backend_observer: NOSUPERUSER, NOCREATEDB, NOCREATEROLE,
  NOREPLICATION, NOLOGIN, INHERIT, and NOBYPASSRLS. Its sole membership is the
  predefined `pg_read_all_stats` role with `INHERIT TRUE`, `SET FALSE`, and
  `ADMIN FALSE`; no governed or LOGIN role is its member. It alone receives
  SELECT on the otherwise closed `pg_stat_activity` view and EXECUTE on
  `pg_stat_get_activity(integer)`. It owns only the two fixed
  backend-incarnation helpers and grants EXECUTE only to `ofarm_binder`, so
  governed and LOGIN roles receive only their narrow results rather than a
  general statistics path;
- ofarm_graph_validator: NOSUPERUSER, NOCREATEDB, NOCREATEROLE,
  NOREPLICATION, NOLOGIN, NOINHERIT, and NOBYPASSRLS, with no membership or
  role-assumption path. It owns only the two deferred promotion-graph trigger
  functions, may execute the sealed current-context function, and has SELECT
  on only the record/edge columns those triggers use. It is named in those two
  tables' tenant policies, so FORCE RLS still constrains it to the bound tenant;
- ofarm_identity_writer: control-plane-only capability that may execute the
  principal-binding lifecycle transition but has no direct DML on binding
  versions, lifecycle acts, or projection, no tenant-truth read role, and no
  application membership;
- ofarm_capability_key_controller:
  an exact `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`,
  `NOBYPASSRLS`, `NOLOGIN`, `NOINHERIT` capability with EXECUTE only on closed
  public-key registration/lifecycle/rebuild functions. The separate
  `ofarm_capability_key_control_login` has the same flags except `LOGIN` and
  `INHERIT`; its sole membership is this capability with `INHERIT TRUE`,
  `SET FALSE`, and `ADMIN FALSE`. It cannot sign or read tenant truth, but it can
  authorize a replacement public key and is therefore an explicit privileged
  signing-authority root outside RLS;
- ofarm_security_audit_owner: NOLOGIN owner only of the protected
  `ofarm_security` schema, operational security-event relation, and hardened
  append/control/query/export/purge/readiness functions, with no tenant-schema
  membership;
- ofarm_security_audit_access_clock_lock_owner: isolated NOLOGIN/NOINHERIT
  owner only of the two fixed-key access-clock wrappers, with no membership or
  role-assumption path and only the exact raw two-integer session lock/unlock
  grants needed by those wrappers;
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
  temporary time-bounded LOGIN during a #192-owned, dual-approved export window;
  normal provisioning creates no such LOGIN or membership. The capability
  executes only the exact pre-authorized bounded export function and has no
  table, append, retention, tenant, application, or digest-key access;
- ofarm_security_audit_retention: NOLOGIN security-operations capability that
  may execute only the migration-owned no-caller-cutoff expired-row purge
  procedure, with no arbitrary row mutation, append, reader, tenant, or
  application authority;
- ofarm_security_audit_readiness: read-only access only to the audit migration
  ledger and structural verification function, with no event/quota/query,
  tenant, application, ingest, control, export, or retention access; and
- ofarm_readiness: read-only access to migration metadata and no access to
  tenant data, or an equivalently restricted readiness grant.

The shared PostgreSQL large-object store is not a tenant or audit carrier.
Provisioning freezes the complete PostgreSQL 17 inventory, signatures,
implementation properties, internal symbols, symbolic bootstrap-superuser
ownership, and ACLs of the 20 `lo_*`, `loread`, and `lowrite` routines. It
revokes PUBLIC EXECUTE from every one and grants no governed runtime or control
role an alternative path. Fresh-target, migration, and startup verification
also require zero `pg_largeobject_metadata` rows. A missing or added routine,
property change, widened ACL, or stored large object is structural drift and
refuses in both the tenant and audit services.

PostgreSQL's default same-role backend visibility is also outside the tenant
and audit carriers. Provisioning freezes the `pg_stat_activity` view's exact
owner category, definition, ordered typed/collated columns, relation posture,
and ACL, plus the complete 14-routine `pg_stat_get_activity` and
`pg_stat_get_backend_*` family with exact signatures, implementation
properties, owners, and ACLs. Both services revoke PUBLIC access. Audit grants
no replacement; tenant grants only the non-assumable backend observer the view
and activity function access needed by its sealed helpers. An unexpected
family member, changed definition or property, or widened grant is structural
drift and refuses.

Enable and FORCE row-level security on every tenant-bearing relation. Policies
use only the protected current-tenant function for both USING and WITH CHECK.
They never consume a raw custom setting. Missing, invalid, expired, replayed, or
multiply bound context denies or raises; it never selects all tenants. Append-
only restrictions remain additional constraints and do not substitute for RLS.
The closed non-tenant control list is `tenant_registry`, `principal_binding`,
`principal_binding_lifecycle`, `principal_binding_current`,
`tenant_binding_context`, and `schema_migration`; these relations have no
tenant RLS policy and instead deny
direct application, worker, readiness, registrar, and end-user relation access.
The binder, registrar, and identity-control paths reach only their named
functions and minimum underlying fields; readiness receives the separately
specified exact read-only migration-ledger grant. Adding any relation or
privilege to that list requires a migration and classification change. Party
and every other tenant-bearing record remain forced-RLS protected.

Under accepted ADR 0003, that closed list also contains
`tenant_binder_instance`, `tenant_capability_verification_key`,
`tenant_capability_key_lifecycle`, and `tenant_capability_keyring`, with the
classifications above. Their direct runtime relation access is denied; only the
closed key-control and binder functions receive the minimum fields they need.

Normal functions execute as the caller. Any unavoidable SECURITY DEFINER
function has a fixed trusted search_path, schema-qualified objects, no
caller-controlled dynamic SQL, minimal ownership, explicit EXECUTE grants, and
adversarial tests. The ADR 0003 challenge, binder, capability-key-control,
principal-lifecycle, projection-rebuild, and current-context functions and the
lock wrappers are named exceptions, together with the isolated security-audit
append, control, query, export, purge, and readiness procedures. Their
definitions and owners are content-addressed by the applicable migration or by
the closed provisioning capsule defined below; `0001` pins that exact
provisioning digest. Triggers and constraint functions include tenant and batch
in every tenant lookup.

Direct SQL using the application role remains subject to forced RLS, composite
constraints, verified context, and append-only rules. The application role
cannot read or write protected context, binding versions, lifecycle acts,
current projection, pre-tenant security events, tenant lock keys, or
capability-verification material; cannot call the security-audit append or retention
functions; cannot assume any privileged role; and cannot execute raw
advisory-lock functions. End users and support users never receive application,
migration, or security-audit credentials. Superusers, database administrators,
migrators, identity-control writers, the crypto installer and capability-key
controller, security-audit owners/readers/retention operators,
backup readers, `ofarm_binder`, and a fully compromised capability signer are
outside the RLS protection boundary; access to those capabilities requires
separate operational controls and audit. The binder's NOLOGIN/no-
membership posture and fixed functions are the control that keeps this narrow
bypass from becoming an application SQL path.

## Protected advisory locks

Cluster provisioning revokes PUBLIC and application EXECUTE on every
pg_advisory_lock, pg_try_advisory_lock, pg_advisory_unlock, and transaction-lock
overload. Among provisioned roles there are exactly three raw-function grant
classes:
`ofarm_tenant_lock_owner` alone receives EXECUTE on
`pg_catalog.pg_advisory_xact_lock(bigint)`, and each service's isolated
migration-lock owner alone receives EXECUTE on
`pg_catalog.pg_advisory_xact_lock(integer, integer)` in that service. In the
audit service only, isolated `ofarm_security_audit_access_clock_lock_owner`
alone receives the exact `pg_advisory_lock(integer, integer)` and
`pg_advisory_unlock(integer, integer)` grants. None of these owners has LOGIN,
members, or a role-assumption path. The audit schema owner, application,
worker, and migrator roles cannot call any raw advisory routine or choose a
numeric lock key.

Four schema-qualified SECURITY DEFINER wrapper functions in three closed
capsules are allowed:

- the tenant-write wrapper accepts no tenant or lock-key argument, requires a
  verified TenantBinding, derives the unique key from its tenant registry row,
  is owned by isolated `ofarm_tenant_lock_owner`, calls only the raw bigint
  transaction-lock overload, and acquires only a transaction-scoped lock; and
- the permanent migration wrapper lives in the separately provisioned
  `ofarm_infrastructure` schema, is owned by the service-specific isolated
  migration-lock owner, is executable only by the migrator, accepts no
  arguments, derives the fixed domain-separated integer pair internally, and
  acquires only a transaction-scoped lock; and
- the audit access-clock take/release pair lives in the same separately
  provisioned infrastructure schema, is owned by the distinct isolated
  access-clock lock owner, is executable only by the audit schema owner,
  accepts no arguments, and embeds the one fixed access-clock integer pair.
  The take wrapper acquires one session lock and the release wrapper releases
  only that same lock; the migration-owned clock helper invokes them in one
  exception-safe function-scoped protocol.

All wrappers have a fixed trusted search_path, fully qualified calls, exact
owners and EXECUTE grants, and no dynamic SQL. There is no application-visible
unlock wrapper; commit or rollback releases each transaction lock. The access-
clock release wrapper is not executable by runtime roles and selects no key.
The infrastructure wrappers are part of the exact provisioning capsule and
remain after `0001`; application startup cannot create, invoke, replace, or
repair them.

The administrator-only provisioning command serializes every verify-or-create
operation in one PostgreSQL cluster with one fixed, cluster-global two-integer
session-lock pair. Every target on that cluster uses the same pair; the
separately bounded audit service uses the same defined pair within its own
cluster, without weakening its required service isolation. The pair comes from
a provisioning-only domain and differs from every permanent migration-wrapper
pair; it also never uses the disjoint single-bigint tenant-lock namespace. Only
the external provisioning administrator takes and explicitly releases this
session lock; it is not exposed through either protected wrapper or granted to
any runtime or migrator role.

Under accepted ADR 0003, its binder, public-key control,
principal-lifecycle, and projection-rebuild entry points may additionally use
only the reserved two-int transaction-level admission pair fixed there. The
binder owner receives only the exact shared acquisition overload; the exact
control-function owners receive only the exact exclusive acquisition overload.
No LOGIN receives either raw privilege, no new caller-visible lock wrapper is
added, and the migration fingerprints the grants, fixed pair, function bodies,
and absence of every re-entry or alternate-key path. ADR 0003's denial-only
admission-close function appends its immutable close act and compare-and-swaps
only non-key projection columns under `FOR NO KEY UPDATE`; it deliberately
takes no advisory admission lock so it can commit before an exclusive
emergency-revocation wait.

## One-time infrastructure provisioning

Database and role creation precede numbered schema migrations. A reviewed,
versioned infrastructure step run by a database administrator creates the
tenant database, plus a separately bounded audit PostgreSQL service/database.
It creates the empty application namespace, the separate `ofarm_infrastructure`
namespace and closed capsule described below, the tenant service's NOLOGIN
application, binder, and tenant-lock owners, the audit service's NOLOGIN
security owner, and each service's specific migration-lock owner. It also
creates the tenant backend-observer and graph-validator roles and the
observer's one non-assumable predefined-role membership, plus the declared
migrator/application/worker/readiness identities or
grants, tenant registrar, identity-control writer, seven isolated security-
audit capabilities, the distinct tenant-control and audit producer/control
LOGIN identities and exact `INHERIT TRUE`/`SET FALSE`/`ADMIN FALSE`
memberships, service resource limits, and initial PUBLIC revocations. Those
revocations include the exact PostgreSQL 17 backend-statistics view/routine
surface in both services; tenant grants its non-assumable observer only the two
catalog privileges needed by the sealed helpers.
Application startup and either migration runner do not create or repair their
own cluster roles or services.

Under accepted ADR 0003, this same reviewed infrastructure step also
creates the exact crypto-installer and capability-key-control roles/login above,
installs the fixed non-trusted/non-relocatable `ofarm_ed25519` extension from
the already pinned derived image, and then removes every runtime/migrator
assumption path. The numbered migration verifies the installation; it never
compiles, installs, updates, replaces, or repairs native code.

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

An administrator-side infrastructure observation made before the migration
command may establish that the database, roles, namespaces, grants, and capsule
are suitable for attempting migration. It is diagnostic infrastructure
evidence only: it is not migration-history authority, cannot classify a target
as fresh or migrated, and cannot be reused as the runner's phase, capsule, or
ledger observation after the migration lock is acquired.

The pre-ledger capsule is a closed provisioning-owned exception to the otherwise
empty target. Each service's capsule contains the permanent, no-argument,
fixed-pair migration-lock wrapper in `ofarm_infrastructure`. Its service-specific
NOLOGIN/no-membership owner is the only role granted raw EXECUTE on
`pg_catalog.pg_advisory_xact_lock(integer, integer)`; the migrator receives only
USAGE on `ofarm_infrastructure` and EXECUTE on the wrapper. The complete tenant
production specification additionally contains one temporary, no-argument
owner sealer. The sealer is a SECURITY DEFINER routine owned by the external
provisioning-superuser category, not by any runtime, control, owner, or migrator
role. Its only EXECUTE grant is to the migrator.

The sealer contains only static statements naming the two frozen challenge and
current-context signatures, the two backend-incarnation helpers,
the two promotion-graph validators, the no-argument tenant-write wrapper,
their four target owners, and the application schema. It accepts no SQL, role,
schema, object, signature, owner, or other caller input and contains no dynamic
SQL. Inside its one transaction it temporarily grants CREATE on only the
application schema to the four fixed owners, as PostgreSQL requires before
those roles receive ownership. It transfers the two `ofarm_binder`-owned
routines, two
observer helpers, two graph validators, and tenant-write wrapper to their exact
owners, then revokes every transient CREATE grant. It finally
changes itself to SECURITY INVOKER and transfers its own ownership to
`ofarm_migrator`. Provisioning creates none of the seven target routine bodies.

The owner sealer grants no LOGIN membership and creates no `SET ROLE`,
inheritance, administration, caller-selected grant, or generic ownership-
transfer path. Tenant `0001` alone uses it. After creating the seven exact
routines under the ordinary application owner, the runner issues `RESET ROLE`,
calls the sealer as the migrator, verifies all seven final owners, all revoked
CREATE grants, and the sealer's SECURITY INVOKER/migrator-owned state, drops the
sealer, and restores the ordinary application owner role before completing the
ledger append. A rollback restores every owner and grant plus the exact usable,
provisioning-superuser-owned SECURITY DEFINER sealer, so failed `0001` can be
retried without repair. The audit capsule has no owner sealer. Every capsule
signature, definition, owner category, function property, grant, and absence is
part of the provisioning digest; missing, extra, changed, or widened capsule
state is drift and refuses. Verification is phase-aware: before the tenant
ledger exists the exact sealer must be present, while after `0001` commits it
must be absent. The permanent migration wrapper and its isolated owner remain
exact in both phases; provisioning never recreates a missing post-`0001` sealer.

## Immutable migration baseline

Two authoritative, independently ordered migration sets use four-digit,
gap-free, immutable filenames: `kernel/migrations` for the tenant service and
`security_audit/migrations` for the separate audit service. Because there is no
deployment, #174 creates hardened `0001_initial.sql` migrations for both. The
tenant migration waits for #171's reviewed RuntimeBundle placement map; the
audit migration contains only the two classified audit relations, closed
constants/checks/functions, roles/grants, and its own ledger/readiness surface.
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
2. begins one READ COMMITTED transaction and invokes the permanent no-argument
   wrapper first, taking the reserved global transaction-scoped migration lock;
3. while holding that lock in the same transaction, obtains fresh catalog and
   ledger observations and repeats the exact phase-aware provisioning digest,
   database, role, namespace ownership, grant, isolated lock-owner, capsule,
   empty-target or ledger-presence, and migration-history checks. No earlier
   administrator observation is accepted as authority for these checks;
4. verifies migration filenames are ordered and gap-free;
5. verifies every previously applied filename and SHA-256 against the immutable
   local migration set;
6. applies the next migration and appends its ledger row in that same database
   transaction; tenant `0001` alone creates the seven sealed routines, resets
   from the application owner to the migrator, invokes the exact owner sealer,
   verifies the two `ofarm_binder`-owned, two observer, two graph-validator,
   and one tenant-lock owners, revoked transient CREATE grants, and the sealer's
   SECURITY INVOKER/migrator-owned state, drops the sealer, restores the
   application owner role, and records the provisioning digest before that
   append;
7. releases the lock on commit or rollback.

Non-transactional migrations are forbidden in the initial posture. If one ever
becomes necessary, a later ADR must define its resumability, dirty-state
handling, and recovery before it can be added.

The migration ledger is append-only. At minimum it stores version, filename,
SHA-256, applied-at diagnostic time, release/application build identity, and an
execution identifier. Missing, duplicate, reordered, unknown, checksum-
mismatched, or partially applied history is dirty and fails closed.

A missing ledger is fresh only when the application and `public` schemas are
provably empty of application relations, views, materialized views, sequences,
types, routines, policies, triggers, and migration-owned extensions, their
owners and grants are exact, and `ofarm_infrastructure` contains exactly the
capsule declared by the applicable provisioning specification. For the complete
tenant production specification that means the permanent migration wrapper
plus the temporary exact owner sealer; for the audit service it means the
permanent migration wrapper only. Any other object, privilege, or function
property without a ledger is dirty.

On that one proven-empty-plus-capsule path, `0001` creates the ledger and target
objects, completes the tenant owner-sealing lifecycle when applicable, records
the exact provisioning digest, and appends its own checksum row atomically. If
the ledger is missing while any non-capsule target object exists, or the capsule
is not exact, the database is dirty and the runner refuses. It never adopts,
fingerprints as a baseline, repairs, drops, or wraps an untracked schema with
`IF NOT EXISTS` behavior.

Before a migration or startup transaction asks PostgreSQL to deparse any
catalog identity, it fixes `standard_conforming_strings=on`, `TimeZone=UTC`,
`DateStyle=ISO, MDY`, and `quote_all_identifiers=off` locally and verifies that
posture. The migration-owned structural verifiers pin every setting their own
deparser or lazy PL/pgSQL compilation consumes. Catalog bytes therefore do not
depend on the caller's display settings, server host time zone, or connection
options.

## Structural compatibility, startup policy, and rollback

The application build carries the exact expected latest tenant migration
version and ordered migration-set digest. The #192 audit client carries the
exact expected audit migration version/digest. Each performs read-only
verification of its own ledger before constructing its repositories or serving
its traffic. Neither creates, alters, drops, repairs, or bootstraps schema
objects. Application and audit startup cannot invoke, install, complete, or
repair the pre-ledger capsule; a capsule-only target is structurally
incompatible.

#174 exposes independent read-only tenant and audit structural-compatibility
reports plus a cross-service separation attestation. Each lane verifies its
pinned build, provisioning identity, ledger, catalog-visible posture, and
observer state internally; its returned report exposes only the fixed service
identity and supported/observed schema versions, never tenant counts,
identifiers, or records. The separation
attestation proves only that the two fixed database routes expose different
PostgreSQL system identifiers. It does not combine their availability or choose
a startup policy. An empty database,
an older or newer schema, a dirty history, an unavailable ledger, or a checksum
mismatch is structurally incompatible and never triggers DDL. #173 composes the
tenant result for application startup, while #192 independently composes the
audit result with its operational-health policy.

#174 exposes no generic `ready`, service-promotion, recovery-readiness, or
continuity result. A physical restore or promoted clone can preserve the
ledger, catalog, roles, and PostgreSQL system identifier, and can therefore be
structurally compatible after promotion. That observation is not authorization
to serve. A target declared restored, point-in-time promoted, snapshot-cloned,
tenant-history imported, forked, or of unknown provenance cannot be promoted to
service in V1 even when its structural report matches. #193 must add an
external continuity witness and explicit promotion policy before such a target
can serve. Database-administrator and recovery-control compromise remains
outside the RLS boundary.
The audit access-clock high-water is also copied or rewound by physical
recovery. Within one uninterrupted audit-store lineage it preserves only
observed wall-clock advances and refuses observed regressions; it cannot detect
a pass-and-rollback excursion between observations. It is not recovery-
continuity or promotion evidence.

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

Controls below that require production capability minting or a UnitOfWork
describe the required end state after #172 and #173. #174 independently
implements the accepted package-local reference capability, database verifier
and binder, and fail-closed storage primitives; it does not claim that the
dependent production path is active.

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
| Advisory-lock collision, raw session lock, attacker-selected key, unlock, or migration-lock attempt | Raw advisory functions are denied except for each isolated capsule owner's exact required overloads: tenant bigint transaction lock, service migration two-integer transaction lock, and audit access-clock two-integer session lock/unlock. Protected no-key wrappers derive or embed the disjoint keys. Only the audit clock capsule uses a session lock, and its helper releases the fixed key on every normal or exception path before returning. |
| Materialization, dependency, cache, trace, gate-log, bound error, or frozen-output leakage | Tenant qualification and RLS apply regardless of authoritative status; pre-tenant errors use only the protected non-tenant audit lane, and structural observations expose no tenant or security-event data. |
| Arbitrary RuntimeBundle bytes, a partial component set, or component append after governed use forges or corrupts provenance | Ordinary runtime roles have read-only bundle/component access and cannot call the dedicated publisher. The trusted startup capability reconstructs and hashes the exact canonical document, verifies every exact content link, and atomically inserts one complete non-empty component set. Row existence is the immutable seal; governed batches reference only that sealed row. |
| Mutation, substitution, or tenant-table mixing of shared global content | #171 placement is prerequisite to 0001; application read-only privileges on global content plus content digest and canonical-byte equality verification apply. Tenant content is inert unless selected by the sealed exact bundle. |
| Concurrent, partial, reordered, missing, edited, future, or ledgerless non-empty migration history | Global migration lock, transactional application, immutable checksums, exact structural compatibility, exact empty-application-plus-capsule proof, and fail-closed dirty detection. |
| Database administrator, migrator, backup, or trusted-binder compromise | Explicitly outside RLS; separate credentials, release controls, audit, and backup governance are required operational controls. |

## Executable adversarial verification plan

The implementation owners named below turn this plan into tests using the real
PostgreSQL roles and real ASGI/application topology, not mocks.

#174 owns the direct PostgreSQL challenge, binder, bootstrap, replay, role, and
catalog tests for accepted ADR 0003. #172 owns external authentication and OIDC
verification, principal-lifecycle integration, capability construction and
minting, and signer-custody tests. #173 owns the same-backend UnitOfWork and real
application/pool sequence; #192 owns audit integration, and #193 owns any
restore-continuity path. Architecture acceptance authorizes implementation
only; production binding remains unavailable until the required evidence passes.

### Tenant context and pool reuse

#174 executes the storage, role, fail-closed context, issuer-vector, and
direct-SQL binder cases. #172's production capability and signer cases and
#173's UnitOfWork and pool cases become mandatory after their implementation
and integration; they are not claims of `0001`.

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
17. Execute the same table-driven issuer and identifier vectors against the
    Python contract and live PostgreSQL constraints, including malformed hosts,
    bracket syntax, ports outside 1..65535, URI delimiters, Unicode, controls,
    and byte limits. #174 exposes no production signing key or issuance path.
    It owns the frozen manifest, independent reference codec, test-only fixture
    signer, live-PostgreSQL binder, and baseline vectors. #172 later proves its
    independent production codec and KMS signer match those exact bytes; #172
    is not a prerequisite for #174 to close. Production context binding remains
    unavailable until the #172/#173/#174 path and evidence pass.

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
   bytes. Golden vectors from #172's production capability codec and #174's
   PostgreSQL functions
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
   into access. Retry an exact overflow ID after commit and across the next
   minute; prove the original overflow outcome is returned without an increment.
   Force two different IDs onto one fixed receipt slot; prove the affected
   bucket becomes `COUNT_UNKNOWN` rather than evicting older exact evidence or
   presenting a double increment as exact. Hold
   a producer transaction at `REPEATABLE READ`, commit each possible same-ID
   outcome in another session, and prove both accepted-to-overflow and
   overflow-to-accepted adjacent-minute retries refuse before reading a stale
   snapshot. Hold
   an append and a close on opposite sides of the minute boundary; prove the
   event-writer barrier admits exactly one ordering, the close count is final,
   the old bucket cannot be recreated, and only one `OVERFLOW_ENDED` exists.
9. Inject cancellation, process exit, connection loss, ambiguous commit, key-
   service failure, relation/disk failure, and whole-audit-service outage before
   and after append acknowledgement. Requests remain denied, timeouts/retries
   stay bounded, no raw or ungoverned queue fallback is emitted, exact-ID retry
   deduplicates ambiguous commits while a durable row or fixed receipt exists,
   any receipt-capacity loss makes the affected count unknown, and recovery
   records every known gap or `COUNT_UNKNOWN` without claiming
   lossless/exactly-once delivery. Rotate keys
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
    bounds. Advance the access-clock authority through expiry, reject the read,
    roll back that read, move the database wall clock backward, and prove the
    same intent still refuses. Only the exact precommitted page succeeds;
    rollback cannot erase its intent or an observed non-regressing clock
    high-water advance,
    replay/COPY returns no wider unique data, and a new page/cut requires
    a new intent. Hold an append transaction open while creating an intent and
    prove the intent waits on the event-writer barrier; commit that append and
    prove it is included by the fresh cut and snapshot. While the intent
    transaction still holds the barrier, attempt a later append and prove it
    waits, then remains outside the committed cut. Keep one successful reader
    transaction open with transaction and idle-in-transaction timeouts disabled
    and prove a second reader can still observe the same access intent without
    waiting on access-clock serialization. Treat database wall-clock
    monotonicity between observations as a trusted prerequisite; #192 must
    supply external fencing if that prerequisite is unavailable. Normal
    provisioning has no export LOGIN. Exercise break-glass
    approval, credential expiry/revocation, cumulative bounded export, and
    denial without tenant or HMAC-key access; audit structural compatibility
    remains false for the whole temporary window, and only dropping the
    temporary LOGIN and reverifying the exact normal posture restores it. #192
    independently decides the corresponding runtime-health policy.
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
   end. Prove `ofarm_tenant_lock_owner` alone has only the exact raw bigint
   EXECUTE needed by that wrapper. Prove the migrator can execute only the
   permanent migration wrapper, not the raw two-integer function, while the
   isolated migration-lock owner alone has only the exact raw two-integer
   EXECUTE needed by that wrapper. Neither lock owner can assume a LOGIN role or
   invoke the other namespace. In the audit service, prove the audit schema
   owner and migrator cannot call either raw session routine or select a key;
   the distinct access-clock lock owner alone has those two raw grants, the
   no-argument wrappers embed the fixed pair, and the clock helper releases it
   before the reader transaction ends.
6. Cold-bootstrap after #171 and prove globally governed bundle bytes are
   outside tenant-owned records while tenant selection/context rows reference
   the exact bundle digest.
7. As application and worker roles, attempt arbitrary bundle INSERT, direct
   component INSERT, invocation of the startup publisher, and component append
   after a governed batch references the bundle. Every attempt refuses. As the
   dedicated publisher, prove one exact publication is complete and an exact
   replay is idempotent; malformed, empty, duplicate, unsorted, digest-mismatched,
   or absent-content component sets leave no partial bundle row.

### Migrations and structural compatibility

1. Provision a new target once and verify exact database owner, NOLOGIN owners,
   role attributes/memberships, namespace owners, PUBLIC revocations, isolated
   lock-owner privilege, empty application catalogs, and exact pre-ledger
   capsule before applying migrations. Prove every provisioning operation in
   one cluster uses the one fixed cluster-global two-integer session-lock pair,
   distinct from every permanent migration pair and the tenant single-bigint
   namespace.
2. Apply each migration set to its proven-empty-plus-capsule tenant or audit
   service and verify exact version, checksums, roles, grants, constraints,
   functions, and indexes. Tenant `0001` leaves the permanent wrapper exact and
   the owner sealer absent, with all seven routines assigned to their exact
   four final owner roles and every transient CREATE grant absent; forced RLS
   applies to every tenant-bearing relation and never supplies a fake tenant
   context to the audit service.
3. Re-run provisioning and the migration runner and prove both are verified
   no-ops, not silent repairs.
4. Test missing, duplicate, reordered, renamed, edited, unknown-future,
   partially applied, and checksum-mismatched migrations; each fails closed.
5. Delete or omit the ledger in both an exact capsule-only target and targets
   with a missing, changed, or widened capsule or one extra relation, view,
   sequence, type, routine, policy, trigger, or migration-owned extension. Only
   the exact empty-application-plus-capsule target is fresh; every other target
   refuses without adoption or cleanup.
6. Inject a DDL failure after the tenant owner sealer runs and prove its seven
   routine-owner changes, transient CREATE grants and revocations,
   self-demotion, drop, all schema changes, and the ledger append roll back to
   the exact usable, provisioning-superuser-owned pre-ledger capsule. Run two
   migration processes
   and prove the global lock serializes them. Give the waiting runner an earlier
   administrator observation of the pre-ledger phase, let the first runner
   commit `0001`, and prove the waiter discards that stale evidence and observes
   the committed post-ledger phase only after its wrapper call returns, within
   its still-open READ COMMITTED transaction.
7. Observe capsule-only, empty, old, exact, newer, dirty, crossed, and
   unavailable tenant/audit schemas independently. Only each exact fully
   migrated lane is structurally compatible; the capsule-only lane refuses.
   Prove the pair-separation attestation has no generic ready bit, does not
   combine lane availability, and that every observation performs no DDL.
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
- #172 supplies explicit production authentication and external OIDC-verifier
  behavior, the governed control-plane integration for immutable principal-
  binding versions, append-only lifecycle transitions and deterministic
  projection rebuild, exact-principal equality enforcement, immutable V1
  tenant/Party eligibility validation, TenantCapability construction and
  minting, production signing, and signer custody, as refined by accepted
  ADR 0003. #174 is its database-primitives prerequisite and supplies the
  classified storage, database verification material/schema, and hardened
  binder functions. #172 does not own those migrations, roles, functions,
  direct PostgreSQL tests, or durable pre-tenant audit emission.
- #173 follows #172 and #174. It supplies the pool, UnitOfWork, application call
  to #174's one-use challenge/binder functions, exact digest propagation,
  same-backend sequencing, transaction finalization/rollback, pool-idle
  enforcement, and write-batch allocation. It does not own the context DDL,
  binder, separate audit connection, or producer integrations.
- #174 follows #168, #169, and #171 and is independently closeable before #172
  and #173. It supplies the one-time provisioning specification, exact role
  attributes and grants, immutable tenant/audit migration baselines, equality
  domains/collations, immutable registry and insert-only registrar, principal
  storage, accepted ADR 0003's package-local framing manifest,
  reference/fixture vectors, database verification material/schema, NOLOGIN
  BYPASSRLS binder, challenge/binder/current-context functions, roles/grants,
  forced RLS, composite keys, the neutral reference carrier and settled
  structural graph constraints, protected lock wrappers, separately bounded audit
  service/relations, producer LOGIN/session map/reason allowlist, hardened
  audit functions, resource limits, direct PostgreSQL binder/bootstrap/replay,
  role and catalog tests, runners, separate lane structural-compatibility
  reports, and a pair-separation attestation. It exposes no generic ready,
  recovery, or promotion result. It does not
  implement #172 authentication, OIDC verification, principal-lifecycle
  integration, TenantCapability minting or signer custody, #173
  application/pool integration, #184's semantic relationship matrix, #192's
  audit runtime/integration, or #193 restore continuity.
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
- #171 is a prerequisite to #174: it supplies immutable RuntimeBundle content,
  equality verification, and the global-versus-tenant placement map required
  before 0001 is frozen.
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
- #185 must make scheduled reference source bytes durable before their parsed
  data can honestly be treated as disposable cache.

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

## Validation for this documentation decision

- Compare the nine CREATE TABLE declarations in kernel/schema.sql with the
  current-relation inventory above; each must be classified exactly once.
- Verify every acceptance criterion maps to a section in the traceability table.
- Run the package contract check and profile extraction-consistency check.
- Run the repository whitespace/diff check.
- Confirm the change contains documentation only.
