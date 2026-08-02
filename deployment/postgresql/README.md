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
row before consuming that capsule in the same transaction. Durable V4 requires
the capsule and forbids both binder grants; durable V5 requires the exact two
binder-granted controller ACLs and forbids the capsule. No selection storage,
runtime activation, route, output, or audit-service authority is added.

The complete merged authority for that admission is the 32,169-byte
`docs/rfcs/OFARM_Tenant_Binding_Selection_Control_Admission_RFC_v0_1.md` at
`sha256:c1d02969811be0d5b02bdae158cb48e5d8148356ca9d4bac956c8861d529c37a`.
The implementation does not rely only on the earlier child-design digest.

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
