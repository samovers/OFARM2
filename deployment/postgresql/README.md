# PostgreSQL deployment boundary

Issue #174 defines two independently provisioned PostgreSQL 17.10 services and
their immutable schema-release boundary:

- `ofarm_tenant` stores tenant truth, protected identity control, and the
  transaction-bound tenant context;
- `ofarm_security_audit` stores only bounded, pre-tenant operational security
  evidence; and
- the audit service must have a different PostgreSQL system identifier from the
  tenant service. A second database in the tenant cluster is not sufficient.

Application startup does not create, alter, repair, or adopt either schema.
Provisioning and migration are explicit release/operator actions. The tenant
and audit structural observations are independent, read-only evidence inputs;
neither is a service or runtime decision.

## Release order

Use the exact checked-in release in this order:

1. Before any tenant release action, require the checked
   `native_release_identity.json` and `native_evidence_receipt.json` to pass
   their complete validators with `frozen` status and verified durable
   preservation. `TENANT_PROVISIONING_SPEC` embeds both complete canonical
   documents, not only their digests. Tenant provisioning, tenant migration
   preflight, the tenant migration runner, and tenant structural readiness all
   refuse provisional, incomplete, stale, or otherwise invalid native
   authority. This gate does not claim that a production KMS signer or its IAM
   controls have been deployed.
2. Provision or verify the tenant infrastructure with
   `TENANT_PROVISIONING_SPEC` and externally supplied SCRAM passwords.
3. Provision or verify the security-audit infrastructure with
   `SECURITY_AUDIT_PROVISIONING_SPEC` and different externally supplied SCRAM
   passwords.
4. Call `verify_provisioned_system_identifier_separation` with both
   administrator routes. It requires the pinned PostgreSQL build
   `17.10 (Debian 17.10-1.pgdg13+1)` and directly observes different system
   identifiers. That observation does not prove origin, clone history,
   continuity, promotion authority, or recovery lineage.
5. Preflight both immutable migration sets without connecting to PostgreSQL:

   ```bash
   python -m deployment.postgresql.preflight_tenant_migrations
   python -m deployment.postgresql.preflight_security_audit_migrations
   ```

6. Run the two migrations as separate release steps. The commands accept no
   service, database, schema, or migration-directory selector:

   ```bash
   export OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN='...'
   export OFARM_TENANT_MIGRATOR_DSN='...'
   python -m deployment.postgresql.run_tenant_migrations \
     --release-identity '<printable-release-id>' \
     --execution-id '<canonical-non-nil-uuid>'

   export OFARM_SECURITY_AUDIT_PG_ADMIN_DSN='...'
   export OFARM_SECURITY_AUDIT_MIGRATOR_DSN='...'
   python -m deployment.postgresql.run_security_audit_migrations \
     --release-identity '<printable-release-id>' \
     --execution-id '<canonical-non-nil-uuid>'
   ```

7. Observe each migrated lane independently:

   - the #173 application integration may call
     `verify_tenant_structural_compatibility` with only the tenant structural
     route; and
   - the #192 audit integration may call
     `verify_security_audit_structural_compatibility` with only the audit
     structural route.

   Neither call opens, loads, or makes a policy decision for the other lane.
8. Where deployment evidence needs a fresh pair check, call
   `verify_postgresql_service_separation` with both structural routes. Its only
   claim is that the fixed tenant and audit routes expose different PostgreSQL
   system identifiers.

Issue #173 owns composing the tenant structural report with its application,
UnitOfWork, repository, and pool policy. Issue #192 independently owns the audit
client, producer credential deployment, operational availability policy, and
runtime-health threshold.

## Immutable migration authority

The only accepted migrations are:

- `kernel/migrations/0001_initial.sql`;
- `kernel/migrations/0002_authentication_read_api.sql`;
- `kernel/migrations/0003_tenant_knowledge_position.sql`;
- `kernel/migrations/0004_temporal_governance_runtime_bundle_role.sql`;
- `kernel/migrations/0005_tenant_binding_selection_control_admission.sql`;
- `kernel/migrations/0006_tenant_current_context_selection_owner_admission.sql`;
- `kernel/migrations/0007_tenant_write_lock_selection_owner_admission.sql`;
- `kernel/migrations/0008_tenant_command_runtime_bundle_selection.sql`;
- `kernel/migrations/0009_runtime_bundle_global_content_retention.sql`;
- `security_audit/migrations/0001_initial.sql`;
- `security_audit/migrations/0002_hmac_v2_operations.sql`; and
- `security_audit/migrations/0003_outcome_reason_vocabulary.sql`.

`migration_sets.py` carries a literal reviewed filename, source SHA-256, source
byte length, prefix digest, and complete set digest for each service. A
directory scan is not authority. Editing, renaming, removing, reordering, or
adding a file without changing the reviewed literal release identity refuses
before a database connection is opened. After release, an applied file is
never changed; later schema changes append a gap-free four-digit migration.

Tenant migration `0005` admits only the isolated command RuntimeBundle
selection-control login to the existing tenant challenge and
capability-binding entry points. Fresh provisioning creates its controller,
login, sole non-assumable membership, inert `CONNECT`/schema `USAGE`, and one
closed one-use grant capsule. The runner authenticates the complete V5 ledger
row before consuming that capsule in the same transaction. Fresh provisioning
also creates the independently governed V6 capsule described below. Through
durable V4, both capsules must remain exact and both admission grant sets must
remain absent. Durable V5 requires the exact two binder-granted controller ACLs,
forbids the V5 capsule, and retains the exact V6 capsule with its grants absent.
No selection storage, runtime activation, route, output, or audit-service
authority is added.

The complete merged authority for that admission is the 32,169-byte
`docs/rfcs/OFARM_Tenant_Binding_Selection_Control_Admission_RFC_v0_1.md` at
`sha256:c1d02969811be0d5b02bdae158cb48e5d8148356ca9d4bac956c8861d529c37a`.
The implementation does not rely only on the earlier child-design digest.

Tenant migration `0006` admits only the existing `NOLOGIN ofarm_owner` role to
`ofarm.current_tenant_id()` and
`ofarm.current_authenticated_principal_ref()`. Fresh provisioning creates one
static no-argument V6 capsule owned by the external provisioning superuser. The
runner appends and authenticates all nine V6 ledger fields before invoking that
capsule. The capsule checks only the exact V6 ordering marker, grants the two
fixed privileges, self-demotes to `SECURITY INVOKER`, transfers itself to
`ofarm_migrator`, and removes its temporary schema `CREATE` privilege. The
runner verifies the exact binder-attributed ACLs, drops only the V6 capsule, and
runs the final structural verifier before commit. Migration `0006` itself is
verifier-only and issues no grant.

Tenant migration `0007` admits only the existing `NOLOGIN ofarm_owner` role to
the existing no-argument `ofarm.take_tenant_write_lock()` wrapper. Fresh
provisioning creates one static no-argument V7 capsule owned by the external
provisioning superuser. The runner authenticates all nine V7 ledger fields,
consumes only that capsule, verifies the exact lock-owner-attributed wrapper
ACL, removes the capsule, restores the fixed migration execution role,
re-authenticates the row, and runs the final structural verifier before commit.
Migration `0007` itself is verifier-only and issues no privilege statement.

Tenant migration `0008` adds one immutable, forced-RLS selection relation for
the reviewed `COMMIT_OPERATION_CLAIM_DRAFT` binding. Only the dedicated
selection-control login may execute the security-definer activation function,
and only after that transaction has an exact protected tenant and Party
context. The function accepts only a sealed same-tenant RuntimeBundle digest,
uses the registered tenant advisory lock, allocates the knowledge position in
PostgreSQL, and writes one governed activation batch and one selection row in
the same transaction. An exact retry returns that row without advancing the
tenant head; a different digest or authority state refuses without a write.

The accompanying `tenant_command_runtime_bundle_selection.py` adapter loads
the reviewed binding and its sixteen required components from fixed repository
paths, accepts no tenant or principal argument, and passes only the validated
RuntimeBundle digest to PostgreSQL. It is a closed control adapter, not an
application or worker runtime service. Migration, repository state, and bundle
publication create no selection. This boundary adds no command integration,
route, runtime read, output, deployment activation, legacy behavior, or #192
behavior.

Tenant migration `0009` adds one publisher-capability
`ofarm.retain_runtime_content(text,bytea)` transition. It derives length and
SHA-256 from the supplied bytes, accepts only exact replay, and retains one
append-only global blob inside the caller's transaction. Retention alone adds
no tenant, bundle membership, selection, runtime activation, route, output, or
current-truth effect. The existing RuntimeBundle publication function and role
topology, including the governed database-owner path, remain unchanged.

The A0/A1/A2/A4 matrix is the sole durable phase authority. A0 through head 4
has all three capsules and no admission grants. A1 at exact head 5 has the V5
controller grants plus exact V6 and V7 capsules. A2 at exact head 6 has exact
V5 and V6 grants plus the V7 capsule. A4 at exact head 7 has no capsule and all
three exact grant sets. Any mixed ledger, capsule, or ACL state refuses without
repair. Failure during V7 restores A2. Lost commit acknowledgement reports an
unknown outcome; reconnect accepts only exact A2 for retry or exact A4 as a
verified no-op preserving the committed execution UUID.

The complete merged authority for V6 is the 50,383-byte
`docs/rfcs/OFARM_Tenant_Current_Context_Selection_Owner_Admission_RFC_v0_1.md`
at
`sha256:af85e259230b69edeba80ddc2eea2f070a601fd3888fd463ce595f9cc446b13d`.
This admission creates no owner login or role-assumption edge and does not add
storage, tenant-lock behavior, RuntimeBundle activation, command integration,
routes, reads, outputs, deployment behavior, legacy behavior, or #192 behavior.
An existing pre-deployment target at durable head 5 or earlier that lacks the
exact provisioning-owned V6 capsule is deliberately refused. This boundary
authorizes no in-place upgrade or repair; that target must be reprovisioned
before migration 0006 may run.

The complete merged authority for V7 is the 45,758-byte
`docs/rfcs/OFARM_Tenant_Write_Lock_Selection_Owner_Admission_RFC_v0_1.md` at
`sha256:5745ad4b8b588be2b5a1b64b4b84aa757b23f8d2de00ca59e71de8ea304f51b0`.
This admission does not add a login, role-assumption edge, raw advisory-lock
grant, selection storage, activation function, RuntimeBundle integration,
command, route, output, deployment repair, legacy behavior, or #192 behavior.
An existing pre-deployment head-6 target without the exact V7 capsule is
refused and must be reprovisioned; no in-place repair is authorized.

The source and set digests cover exact bytes. The set framing uses the tagged,
length-prefixed `OFARM_POSTGRESQL_MIGRATION_SET_V1` policy documented in
`migration_sets.py`; it does not depend on JSON, paths discovered at runtime,
or platform text conversion.

Each migration runs in one PostgreSQL transaction with its matching ledger
append. The runner takes the provisioning-owned no-argument migration lock,
re-observes the locked target, checks the exact existing history, executes one
migration, validates the complete final catalog, and commits. A failure rolls
back both DDL and history. A missing ledger is accepted only for the exact
empty application/public posture plus the fixed provisioning capsule. The
runner never baselines, repairs, drops, or wraps an unknown schema.

## Provisioning contract

`provisioning.py` is administrator tooling with create-or-verify semantics:

- creation is allowed only when the target database and complete reserved
  `ofarm_` role namespace are absent;
- an existing target is verified without writes;
- all catalog observations for one target use one repeatable-read, read-only
  snapshot;
- role attributes, memberships, database settings, owners, ACLs, default ACLs,
  namespaces, collations, and the pre-ledger capsule must be exact; and
- partial infrastructure or any extra governed role, object, privilege,
  membership path, prepared transaction, or enabled subscription refuses. It
  is never silently reconciled.

Both databases use UTF8 and the built-in deterministic `C` locale/equality
posture. PostgreSQL connection limits and `temp_file_limit` are enforced in the
database. Other USERSET timeouts in the role specifications are operational
defaults, not controls against a hostile raw SQL session.

The permanent `ofarm_infrastructure` capsule contains a fixed, no-argument,
transaction-scoped migration-lock wrapper. Tenant bootstrap also uses a
temporary static owner sealer for the transaction-context helpers,
backend-incarnation observer, graph validator, and tenant-lock functions. The
tenant runner consumes and drops that sealer atomically during `0001`; it is
never recreated after the ledger exists. No runtime role can call either raw
advisory-lock overload or assume the isolated function-owner roles.

Provisioning also closes PostgreSQL's database-local large-object side store.
It freezes the complete 20-routine PostgreSQL 17.10 `lo_*`/`loread`/`lowrite`
inventory and implementation posture, revokes every PUBLIC EXECUTE path, and
accepts only the bootstrap-superuser owner's symbolic ACL. Both services
require zero `pg_largeobject_metadata` rows before migration and at structural
observation. An added routine, changed implementation property, widened grant,
or stored large object refuses.

Provisioning also removes the default same-login backend-observation path in
both services. PUBLIC loses SELECT on the exact PostgreSQL 17.10
`pg_catalog.pg_stat_activity` view and EXECUTE on the complete
`pg_stat_get_activity`/`pg_stat_get_backend_*` family of 14 routines. The audit
service grants no replacement. The tenant service grants only its NOLOGIN,
non-assumable backend observer SELECT on that view and EXECUTE on
`pg_stat_get_activity(integer)`, because the observer's two sealed helpers need
those privileges. The exact view definition, ordered columns, routine
properties, owners, and ACLs are structural posture; any sibling routine,
definition change, or widened grant refuses.

## Tenant schema

The tenant migration establishes:

- an immutable tenant registry and append-only principal-binding versions and
  lifecycle acts;
- a rebuildable current-binding projection that is never authority by itself;
- one exact, shared Python/PostgreSQL issuer-storage grammar and exact UTF-8
  issuer equality;
- one immutable binder installation identity and derived audience, immutable
  Ed25519 public-key candidates, an append-only digest-chained key/admission
  lifecycle, and a rebuildable keyring projection that is never authority by
  itself;
- closed key-control entry points for candidate registration and preflight,
  activation, rotation, durable admission close, revocation, controlled
  resumption, projection rebuild, and observation;
- the exact compact-JWS header, canonical binary payload, time bounds, and
  shared Python/PostgreSQL contract vectors accepted by ADR 0003;
- a protected UNLOGGED context keyed by database-derived PID, backend start,
  and full `xid8`, with storage for one database-created challenge or one
  database-binder-verified bound context per transaction;
- a hardened `create_tenant_challenge()` and `bind_tenant_capability(text)`
  path. The binder uses the provisioned verification-only native extension,
  then checks the protected challenge and audience, backend incarnation and
  transaction, exact time window, authoritative key/admission and principal
  folds, tenant registration, and pinned Party tuple before the one-way
  `CHALLENGE`-to-`BOUND` transition;
- a privileged NOLOGIN backend observer that cannot be inherited or assumed by
  a LOGIN role and exposes only current-incarnation and exact liveness helper
  results to the isolated NOLOGIN context-function owner, plus a NOLOGIN graph
  validator that remains constrained by FORCE RLS and minimum column grants;
- a protected, no-caller-key tenant write lock;
- tenant-qualified composite primary, unique, and foreign keys;
- enabled and forced RLS on every tenant-bearing relation;
- governed write batches, graph integrity, future-identifier refusal, derived
  materialization/dependency keys, and the neutral record-reference carrier;
  and
- exact catalog and contract observers available only to the appropriate
  migration/readiness roles.

The `0001` baseline now installs ADR 0003's database verifier, binder, public-key
registry, and database lifecycle rules. It stores no signing secret and cannot
mint a capability. The keyring projection and caller-supplied evidence digests
cannot authorize by themselves; the binder reconstructs append-only authority
under the fixed `READ COMMITTED` lock protocol. Application and worker SQL
still cannot publish a `BOUND` context through `SET`, request data, a raw tenant
identifier, or a default. A missing or invalid native release blocks tenant
release operations and structural readiness. Once deployed, closed admission,
an ineligible key, an invalid signature, a stale principal, a reused or wrong
challenge, or any contract mismatch makes binding refuse.

The additive `0002` migration exposes three read-only issue #172 entry points:
the pinned authentication runtime contract, exact active principal authority,
and current signing authority. They are owned by the unreachable schema owner
and grant `ofarm_app` only `EXECUTE`; the application still has no direct
identity, Party, tenant, or signing-control table privilege. Each observer
recomputes the relevant immutable digests and lifecycle chain and raises
SQLSTATE `PT001` when database authority is internally inconsistent.
That full-chain validation is deliberate and linear in the relevant lifecycle
history. Callers observe authority at the decision point and must not reuse a
signing result across mints or retain a principal result after its request.

The additive `0003` migration adds the tenant knowledge-position ledger head.
The additive `0004` migration admits only `TEMPORAL_GOVERNANCE_ARTIFACT` to the
closed persisted RuntimeBundle component-role vocabulary. It leaves candidate
selection, RuntimeBundle composition, profiles, commands, routes, outputs, and
runtime activation unchanged; persisted membership alone has no semantic or
current/default effect.

Issue #172 owns external identity verification, exact principal resolution, an
independent capability codec, nonce and capability creation, and signing with
the accepted non-exportable Cloud KMS HSM key. It also owns the live KMS/IAM
observation, quiescence, and minting controls that coordinate with the
database's lifecycle receipts. This package does not implement or attest that
production signer or control-plane deployment, and PostgreSQL does not query
Google Cloud; its key-control functions validate governed database state and
record the required external evidence digests. A frozen native verifier release
therefore makes the checked database release deployable, but does not by itself
open admission or make production capability issuance available. Issue #173
owns keeping challenge creation, binder invocation, governed work, commit or
rollback, and pool return on one backend and transaction. Issue #184 owns the
complete semantic reference kind/cardinality matrix; #174 supplies only its
isolated neutral relational carrier.

## Security-audit schema

The security-audit migration establishes a separate, non-tenant lane with:

- one closed append API and fixed session-user-to-producer/reason mapping;
- bounded event fields, deterministic retry identity, correlation-digest
  validation, database time, quotas, overflow markers, and bounded query APIs;
- append-only event evidence, visibility-stable access cuts, an event-writer
  close barrier, and protected disposable quota state that cannot reopen;
- HMAC V2 for fresh appends, exact committed-identity V1 retries, and bounded
  control observations for overflow closure and key-retention deadlines;
- declared gap markers and an exact empty-store recreation posture; and
- distinct ingest, control, reader, retention, readiness, and deliberately
  absent recovery/break-glass capabilities.

It never accepts or stores tenant, principal, Party, farm, role, governed-batch,
or knowledge-position fields. It cannot authorize or reconstruct tenant state.
The migration's structural flag proves the #174 schema only. It is not an audit
client availability or operational-health result; #192 owns those decisions.

The audit service has no V1 backup, replica, restore, or history-import path.
Loss is represented as an operational evidence gap: recreate an empty verified
service from immutable provisioning and migrations, then let the later #192
control client append a declared gap. This is not tenant recovery.

## Read-only structural compatibility

Each lane-specific structural function loads only its own literal migration
identity and opens one repeatable-read, read-only snapshot. Each transaction
fixes `standard_conforming_strings=on`, `TimeZone=UTC`,
`DateStyle=ISO, MDY`, and `quote_all_identifiers=off` before PostgreSQL deparses
any catalog identity, so caller or cluster display settings cannot change the
authenticated bytes. It then verifies:

- the exact structural session and current-user identity and fixed database name;
- the exact tested PostgreSQL build
  `17.10 (Debian 17.10-1.pgdg13+1)` with
  `server_version_num = 170010`;
- no publication, subscription, replication slot, or live physical-replication
  path in that service;
- the exact closed PostgreSQL 17.10 large-object routine surface and an empty
  large-object store;
- the exact closed backend-statistics view, routine, ownership, and ACL
  posture;
- the complete ordered seven-column ledger history;
- that lane's complete symbolic catalog identity; and
- that lane's exact structural contract-observer fields.

Every exit explicitly rolls back and closes the connection it opened. A report
exposes only the service identity and supported/observed schema versions. It has
no generic service decision, runtime-health result, primary-state result,
promotion result, or continuity result. Errors use closed diagnostic text and
do not include DSNs, observed identifiers, tenant data, or audit records. The
observation performs no DDL, DML, lock acquisition, repair, or bootstrap.

`verify_postgresql_service_separation` is deliberately narrower. It opens both
structural routes, verifies their fixed role/database identities and pinned
PostgreSQL build, and attests only that their system identifiers differ. A system
identifier is copied by a physical backup. After promotion, a physical clone can
therefore produce the same tenant structural report and still satisfy tenant-
versus-audit separation. Neither result proves uninterrupted tenant history or
authorizes traffic. Issue #193 must supply an external non-rewindable witness
before any restore or promotion decision can exist.

## One-shot security-audit bounded query

The bounded-query command commits one fixed `AUDIT_ACCESS` intent through the
control route, opens the reader route only after that commit is acknowledged,
and returns one descending page with at most 256 event rows:

```bash
export OFARM_SECURITY_AUDIT_CONTROL_PG_DSN='...'
export OFARM_SECURITY_AUDIT_READER_PG_DSN='...'
python -m deployment.postgresql.run_security_audit_query
```

The only optional argument is one exact older-page cursor:

```bash
python -m deployment.postgresql.run_security_audit_query \
  --cursor '2026-08-13T10:20:30.123456Z/11111111-1111-4111-8111-111111111111'
```

The control route must authenticate only as
`ofarm_security_audit_control_login`; the reader route must authenticate only
as `ofarm_security_audit_reader_login`. The command validates the cursor and
both complete conninfo values before opening either route. It fixes the normal
purpose, exact database function identity, maximum of 256 event rows, and
1,048,576-byte database-encoded event ceiling. It never accepts an access-event
ID, purpose, function, or limit from the caller.

Each route gets at most one `psycopg.connect` call. Code-owned startup options
replace caller-supplied conninfo options and fix the statement, lock,
idle-transaction, transaction, work-memory, bytea, time-zone, and date-style
settings. The control route also fixes `synchronous_commit=on`.
`temp_file_limit=0` remains a database-scoped role default installed by
provisioning; the non-superuser command does not send it or require permission
to set it.

After acknowledged intent commit, the reader submits the existing bounded
query exactly once. PostgreSQL remains authoritative for authorization, the
data cut, snapshot membership, five-minute intent expiry, ordering, and encoded
byte accounting. The command validates the complete 30-field carrier and
buffers one canonical ASCII JSON line before touching stdout. Valid historical
reasons remain readable even when they are no longer accepted for fresh
appends. A nonempty page reports a canonical `nextCursor` derived from its last
row; following it is a new privileged access act with a new durable intent.

Closed terminal outcomes are:

- exit `0`: intent acknowledged, one query completed, and the complete report
  was written and flushed;
- exit `1`: refused after the control route opened but before commit ambiguity;
- exit `2`: invalid arguments, cursor, or conninfo configuration;
- exit `3`: the control connection factory failed before returning a
  connection, so no commit was sent;
- exit `4`: access-intent commit outcome unknown and no query was sent;
- exit `5`: intent acknowledged but no complete validated report is available;
  and
- exit `6`: a complete report existed but stdout write or flush failed, so
  partial output is possible.

Operators and automation must not retry exits `4`, `5`, or `6`, or an
incomplete process protocol, automatically. A later invocation never resumes
or reconciles an earlier access event; it commits a new intent and makes at
most one new query.

This command is a privileged one-shot diagnostic primitive. It is not an
export or break-glass operation, scheduler, loop, or web endpoint.
It is not a deployment-readiness or external clock-fence claim. It grants no
production-access authorization or guarantee that authorized output cannot be
copied after disclosure.

## Library-only security-audit bounded export page

`security_audit_export.py` is a bounded export-page library primitive for a
later, separately approved break-glass lifecycle. It has no standalone export
command, module entry point, scheduler, endpoint, output sink, or documented
operator invocation. The library accepts only two complete raw conninfo
strings and either no cursor or one already validated immutable cursor. It
preflights both routes before external I/O, commits one fixed export
`AUDIT_ACCESS` intent, opens the export route only after that commit is
acknowledged, and requests exactly one descending page with at most 2,048
event rows and an 8,388,608-byte database-encoded event ceiling.

The control route still must authenticate exactly as
`ofarm_security_audit_control_login`. The future lifecycle must supply an
already-created exact `ofarm_security_audit_export_login` route with the
existing export-capability membership. This library does not create or receive
a separate temporary export credential parameter, create or change a role,
grant membership, verify approval, choose an operator or output destination,
revoke or drop the temporary login, or terminate a session. A lifecycle-owned
credential may be present inside the supplied export conninfo and remains
resident for the runner call; the library neither extracts nor returns that
route. Normal provisioning deliberately keeps the login absent.

Code-owned startup values replace conflicting conninfo keywords. In
particular, a code-owned keyword never merges with a conflicting conninfo
value: an `options` value present in either supplied route is dropped in full
and replaced by the fixed option string. Both connections fix statement,
lock, idle-transaction, transaction, work-memory, bytea, time-zone, and
date-style settings; the control route also fixes
`synchronous_commit=on`. PostgreSQL remains authoritative for session-user
authorization, the data cut, snapshot membership, five-minute expiry,
request equality, row membership and ordering, and encoded-byte accounting.

Success is one immutable acknowledged intent, validated event tuple, derived
next cursor, and completely buffered canonical ASCII JSON line. The library
does not write that page anywhere and does not consume the next cursor. An
unknown commit outcome or any failure after acknowledged intent must not be
retried automatically. A repeated invocation is a new caller action outside
this primitive, not a resume or reconciliation.

This primitive proves only one bounded export page. It does not prove dual
approval, approval currentness or single use, temporary-login expiry or
cleanup, structural closure, runtime health, protected output delivery,
external clock fencing, deployment readiness, or completion of issue #192.
Those remain prerequisites for a future operator-facing lifecycle.

## Library-only security-audit dual-approval verification

`security_audit_approval.py` is a side-effect-free verifier for a later,
separately approved break-glass lifecycle. Trusted composition constructs it
with one exact Ed25519 observer public key. A caller then supplies one bounded
canonical observer-signed authority receipt, one bounded canonical approval
bundle, and trusted current Unix time in microseconds. The verifier accepts
only the fixed one-page export purpose, callable, cursor grammar, 2,048-row
ceiling, and 8,388,608-byte ceiling. Exactly two canonical Ed25519 statements
must bind the same receipt, request, and operation and resolve to different
approver IDs, key IDs, and independence domains in the presented receipt.

Success is one private immutable normalized evidence value. It contains no
private key, signature, public key, raw carrier, credential, output, or
consumption claim. It is not a bearer grant: a later admission boundary must
receive and reverify the original carrier bytes with admission-owned time and
atomically consume the exact operation and approval digest before creating any
credential. Repeated verification here is deliberately equal and
side-effect-free.

The verifier does not acquire a clock, discover the latest authority receipt,
issue approvals, persist replay state, create or change a role, receive a
conninfo, call PostgreSQL, invoke the bounded export runner, write output, or
provide a command or module entry point. Removing a key from newly issued
receipts is therefore fully effective only after older signed receipts expire;
every accepted receipt and request is capped at five minutes. Immediate
revocation, production observer-root composition, durable admission,
temporary-login lifecycle, protected delivery, deployment readiness, and
issue #192 closure remain separate trust boundaries.

## Library-only security-audit authority-receipt issuance

`security_audit_authority.py` is the stateless issuance counterpart to the
dual-approval verifier. Trusted composition constructs one issuer with an
exact Google Cloud KMS HSM Ed25519 key-version resource, its matching raw
observer public key, one bounded canonical approver manifest, and an injected
KMS client. Each call supplies trusted current Unix time in microseconds. The
issuer derives every approver key ID locally, emits the verifier's exact
five-minute payload, makes one raw-data `asymmetric_sign` call with CRC32C,
`retry=None`, and a five-second timeout, validates the complete HSM response,
and independently verifies the signature before returning a canonical bounded
receipt.

The module has no repository production imports and performs no clock,
database, filesystem, environment, logging, random, process, credential,
export, delivery, or persistence work. It cannot provision or observe the KMS
key, load a manifest, choose production time, issue an approval, admit or
consume an operation, create a login, export data, or deliver output. Those
composition, custody, and lifecycle authorities remain separate decisions;
this library alone does not establish deployment readiness or complete issue
#192.

## Library-only security-audit observer-root admission

`security_audit_observer_root_admission.py` is the non-provisioning admission
boundary for one independently reviewed Google Cloud KMS HSM Ed25519 observer
root. Trusted composition supplies one bounded canonical manifest, separate
observer and signer KMS clients, an authenticated evidence HTTP session, and a
trusted clock. One call observes the exact key, version, DER public key,
attestation bundle, three closed custom roles, and ten effective-IAM tuples
twice around one fixed non-production signing probe. Every Policy
Troubleshooter request uses the v3beta allow/deny/PAB surface and accepts only
the exact no-PAB posture frozen by the RFC.

Success is one frozen 30-second admission containing the pinned identities,
times, and SHA-256 digests of the manifest, equal normalized snapshot, and
complete probe-bound evidence. It contains no policy, certificate,
attestation, signature, credential, client, or mutable carrier. Any ordinary
failure becomes a fresh empty refusal, while invalid local configuration makes
no clock or network call and a successful call performs exactly one probe
between two complete 16-read snapshots.

The module cannot create or change a key, role, policy, credential, database,
export, delivery route, runtime, or readiness state. It does not load the
manifest, select production credentials, publish the admission, or authorize
production use of the Preview v3beta dependency. Credential custody,
provider-currentness acceptance, refresh and atomic publication, root
rotation, runtime integration, deployment readiness, and issue #192 closure
remain separate decisions.

## One-shot security-audit overflow closure

The overflow-closure command observes and closes at most one database-selected
oldest closeable overflow bucket and accepts no arguments:

```bash
export OFARM_SECURITY_AUDIT_CONTROL_PG_DSN='...'
python -m deployment.postgresql.run_security_audit_overflow
```

The route must authenticate only as
`ofarm_security_audit_control_login`. The command accepts no producer,
component, bucket, timestamp, count posture, limit, role, mode, or retry
selector. PostgreSQL's existing
`observe_next_closeable_overflow_bucket()` function chooses the oldest bucket;
the command may pass only that returned identity to the existing
`close_overflow_bucket(...)` function.

One process invocation makes one `psycopg.connect` call. Observation and the
optional close occur on the same idle non-autocommit `READ COMMITTED`
connection. The five-second connection timeout applies to each libpq host or
address attempt, not to the total network or process lifetime. Code-owned
statement, lock, idle-transaction, transaction, work-memory, time-zone,
date-style, and synchronous-commit settings replace all DSN-provided startup
options.
`temp_file_limit=0` remains a provisioned database-role default.

An empty observation is a successful bounded no-op: the command explicitly
rolls back, submits no close, and emits `NO_CLOSEABLE_BUCKET`. A nonempty
observation can submit the close function once, validate and pre-render its
fixed non-sensitive report, and call `commit()` once. `ACKNOWLEDGED` means the
selected bucket is closed under the reported `OVERFLOW_ENDED` identity; a
concurrent closer may have created that event first, so `observedAt` can predate
this invocation. The report deliberately contains no overflow count or
`COUNT_UNKNOWN` claim.

Closed terminal outcomes are:

- exit `0`: a known no-bucket or acknowledged closure report was completely
  written and flushed;
- exit `1`: the returned route or transaction was refused before commit
  ambiguity;
- exit `2`: invalid arguments or conninfo configuration;
- exit `3`: unavailable before `commit()` was sent;
- exit `4`: the explicit closure commit outcome is unknown; and
- exit `5`: a known terminal result existed but reporting failed.

Operators and automation must not retry exit `4`, exit `5`, or an incomplete
process protocol automatically. A later invocation observes the then-oldest
bucket and is not reconciliation of an earlier result.

Deployment or scheduling must ensure that every possibly ambiguous bucket is
marked `COUNT_UNKNOWN` before operational closure, because closure makes the
database-owned count posture immutable.
This command does not invoke `mark_overflow_count_unknown`. It does not infer
whether a count is exact.

This command is not a scheduler, drain loop, gap recorder, readiness or clock
fence, deployment action, or production-operation authorization. It changes no
Kernel runtime, database object, role, grant, retention, reader/export,
break-glass, recovery, HMAC-custody, issue #172, or issue #176 authority.

## One-shot security-audit logical retention

The retention command performs exactly one database-owned logical-retention
batch and accepts no arguments:

```bash
export OFARM_SECURITY_AUDIT_RETENTION_PG_DSN='...'
python -m deployment.postgresql.run_security_audit_retention
```

The route must authenticate only as
`ofarm_security_audit_retention_login`. PostgreSQL chooses the cutoff, victims,
ordering, cleanup, maintenance-event identity, and maximum deletion count of
1,024 event rows. The command never accepts a cutoff, row identity, cursor,
limit, role, service, or retry selector. An invocation before any row is
eligible commits a matching `AUDIT_RETENTION` event with a zero deletion count.

One process invocation makes one `psycopg.connect` call and submits the fixed
function once. The five-second connection timeout applies to each libpq host or
address attempt; it is not a total network or process deadline. Statement,
lock, idle-transaction, transaction, and synchronous-commit settings are fixed
by the command and override matching conninfo options.

Exit `0` is the only acknowledged and completely reported result. It emits one
canonical ASCII JSON line. Closed failures are:

- exit `1`: refused before a commit could become ambiguous;
- exit `2`: invalid command arguments or conninfo configuration;
- exit `3`: unavailable with no commit sent;
- exit `4`: commit outcome unknown; do not retry automatically; and
- exit `5`: committed but reporting failed; do not retry automatically.

Any invocation lacking one complete terminal protocol is operationally
unknown. Operators and automation must not retry exit `4`, exit `5`, or an
incomplete protocol automatically. A later invocation is a separately
authorized new batch, not reconciliation of an ambiguous batch.

This command is not a scheduler or drain loop. It makes no deployment,
readiness, continuity, lossless-retention, legal-hold, backup, replica, WAL,
vacuum, media-sanitization, or physical-erasure claim.

## One-shot security-audit store-loss recovery

The store-loss command rebuilds only one absent, unpublished security-audit
service. Before invocation, external authorities must have declared the old
service lost, made the fixed target database and every governed `ofarm_*` role
absent, kept every replacement credential and route quarantined from
producers/readers/maintenance jobs, and supplied a conservative loss-start
timestamp. Deployment evidence must separately establish a non-regressing
replacement PostgreSQL clock throughout the operation.

The command uses these fixed secret environment names:

```text
OFARM_SECURITY_AUDIT_PG_ADMIN_DSN
OFARM_SECURITY_AUDIT_MIGRATOR_DSN
OFARM_SECURITY_AUDIT_CONTROL_PG_DSN
OFARM_SECURITY_AUDIT_MIGRATOR_LOGIN_PASSWORD
OFARM_SECURITY_AUTHENTICATION_PRODUCER_LOGIN_PASSWORD
OFARM_SECURITY_REQUEST_ROUTER_PRODUCER_LOGIN_PASSWORD
OFARM_SECURITY_AUDIT_CONTROL_LOGIN_PASSWORD
OFARM_SECURITY_AUDIT_READER_LOGIN_PASSWORD
OFARM_SECURITY_AUDIT_RETENTION_LOGIN_PASSWORD
OFARM_SECURITY_AUDIT_READINESS_LOGIN_PASSWORD
```

Invoke it once with only the externally witnessed start, the bounded release
identity, and one canonical non-nil migration UUID:

```bash
python -m deployment.postgresql.run_security_audit_store_loss \
  --loss-start '2026-08-23T08:00:00.000000Z' \
  --release-identity '<printable-release-id>' \
  --execution-id '<canonical-non-nil-uuid>'
```

One runner-owned admin session holds two nonpersistent advisory locks before
creation starts and through final observation. Every provisioner, migration,
fresh-state, control, and final-observation connection must see those exact
locks locally before its first authoritative observation or effect. Recovery
requires `created = true`, the complete authoritative migration set applied
from version zero, exact migration-created empty state, one fixed
`append_audit_gap(start, database_end, 0, true)` call, and one final exact
one-gap observation. Database name, version, migration history, and system
identifier alone cannot substitute for the live locks because a promoted
physical clone can retain all four.

Exit `0` is the only recovered result and emits one canonical ASCII JSON line.
The other closed exits are:

- exit `2`: invalid arguments or incomplete fixed secrets before PostgreSQL;
- exit `3`: recovery refused or cleanup failed; keep the target quarantined;
- exit `4`: append outcome unknown; keep the target quarantined and do not
  retry; and
- exit `5`: the database state recovered but complete report delivery failed;
  keep the target quarantined and do not retry.

There is no supported rerun, repair, adoption, or in-command cleanup path. A
failed or incomplete target remains quarantined until a separately authorized
DBA inspects and, if approved, removes it. The report is evidence for an
external publication authority; it does not publish a route, distribute a
credential, authorize deployment, or claim that the old service was destroyed.
The command adds no backup, restore, replica, WAL, CDC, history import, tenant
recovery, or production operation.

## One-shot correlation-HMAC version-1 retirement

The correlation-HMAC retirement command is a fixed technical primitive for
the accepted version-1 to version-2 rotation:

```bash
export OFARM_SECURITY_AUDIT_CONTROL_PG_DSN='...'
export OFARM_CORRELATION_HMAC_KMS_KEY_RESOURCE='projects/.../cryptoKeys/...'
python -m deployment.postgresql.run_security_audit_hmac_retirement
```

It accepts no arguments and no caller-selected version, state, deadline,
duration, timeout, retry, or action. It requires known versions `(1, 2)`,
active version `2`, and retirement target version `1`. It reuses the existing
read-only lifecycle observer, validates the exact MAC/HSM/HMAC-SHA-256 parent
and its 86,400-second destruction delay, reads the live version-1 deadline and
fresh clock only through `ofarm_security_audit_control_login`, and closes the
database transaction before any mutation can be submitted.

An enabled or disabled target with a live deadline must have at least 172,800
seconds of database-observed lead. The process then enters the Cloud KMS
destroy method at most once, with `retry=None` and only the positive remaining
part of its fixed five-second monotonic admission budget. The only request is
`DestroyCryptoKeyVersion` for version `1`. A conforming pre-existing
`DESTROY_SCHEDULED` or `DESTROYED` state is reported without mutation. The
canonical result is point-in-time evidence only. A null `greatestPurgeAfter`
means no currently retained version-1 event was observed; it does not prove
that version `1` was never used or that every historical deadline was met.

The dedicated retirement principal must be independently provisioned and
verified with only these permissions on the exact configured CryptoKey:

- `cloudkms.cryptoKeys.get`;
- `cloudkms.cryptoKeyVersions.get`;
- `cloudkms.cryptoKeyVersions.list`; and
- `cloudkms.cryptoKeyVersions.destroy`.

It must have no `macSign`, restore, update, create, delete, import, reimport, or
IAM-management permission. The production audit runtime identity must never
receive `destroy`. Repository code neither provisions nor self-attests IAM.

This primitive is intentionally non-deployable until a separate deployment
gate has current, independently controlled, verifiable evidence for both
timing premises. Clock evidence must bind the exact PostgreSQL route and Cloud
KMS endpoint to an authenticated common time reference, prove absolute skew no
greater than one second, be measured within 60 seconds before invocation, and
remain valid through the operation. Provider-acceptance evidence must bind the
exact endpoint, service, method, client and transport versions, and transmitted
deadline semantics, and prove that no state change can be accepted more than
five seconds after admission starts, including timeout and cancellation paths
with ambiguous completion. The GAPIC timeout and historical latency samples
are not that proof. This repository supplies neither artifact; the external
gate must refuse before launching the process when either is absent, expired,
or incomplete.

Closed terminal outcomes are:

- exit `0`: one complete known scheduled or destroyed report was flushed;
- exit `1`: a prerequisite or deadline policy refused before mutation;
- exit `2`: command or static configuration was invalid;
- exit `3`: unavailable before destroy submission;
- exit `4`: destroy was submitted but its exact outcome is unknown; and
- exit `5`: a known result existed but complete report delivery failed.

Operators and automation must not retry exit `4`, exit `5`, or an incomplete
process protocol automatically. This command does not authorize deployment,
IAM changes, a real Cloud KMS invocation, release, production readiness,
physical-media erasure, historical compliance, or issue #192 closure. It is
not a scheduler, rotation controller, readiness check, continuous monitor, or
runtime integration.

## Accepted limits

The checked-in conformance workflow exercises three disposable PostgreSQL
17.10 instances and the two services with their real roles.
That evidence does not prove production separation of disks, WAL, network
routes, connection pools, credentials, CPU, memory, storage quotas, monitoring,
or backup targets. Those require deployment evidence and operational controls.

There is no V1 tenant restore, point-in-time promotion, snapshot adoption, or
logical history import. Issue #193 owns that future design and any continuity
witness or promotion decision. Database isolation, migration, recovery, RLS,
and direct-SQL boundaries remain the responsibility of #174; application/pool
integration does not weaken them.
