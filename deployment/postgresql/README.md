# PostgreSQL deployment boundary

Issue #174 defines two independently provisioned PostgreSQL 17 services and
their immutable schema-release boundary:

- `ofarm_tenant` stores tenant truth, protected identity control, and the
  transaction-bound tenant context;
- `ofarm_security_audit` stores only bounded, pre-tenant operational security
  evidence; and
- the audit service must have a different PostgreSQL system identifier from the
  tenant service. A second database in the tenant cluster is not sufficient.

Application startup does not create, alter, repair, or adopt either schema.
Provisioning and migration are explicit release/operator actions. The startup
gate is read-only and fail-closed.

## Release order

Use the exact checked-in release in this order:

1. Provision or verify the tenant infrastructure with
   `TENANT_PROVISIONING_SPEC` and externally supplied SCRAM passwords.
2. Provision or verify the security-audit infrastructure with
   `SECURITY_AUDIT_PROVISIONING_SPEC` and different externally supplied SCRAM
   passwords.
3. Call `verify_provisioned_cluster_lineages` with both administrator routes.
   It requires PostgreSQL 17, the same server patch version, and distinct
   system identifiers.
4. Preflight both immutable migration sets without connecting to PostgreSQL:

   ```bash
   python -m deployment.postgresql.preflight_tenant_migrations
   python -m deployment.postgresql.preflight_security_audit_migrations
   ```

5. Run the two migrations as separate release steps. The commands accept no
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

6. Before constructing database-backed application services, call
   `verify_startup_readiness` with only the tenant and audit readiness routes.
   The caller must not publish its startup-complete observation until that gate
   returns and the caller's surrounding startup transaction has committed.

The #174 library supplies the gate. Issue #173 owns wiring it into the tenant
UnitOfWork, repository, and pool lifecycle. Issue #192 owns the bounded audit
client, producer credential deployment, operational availability policy, and
its runtime readiness threshold.

## Immutable migration authority

The only accepted migrations are:

- `kernel/migrations/0001_initial.sql`; and
- `security_audit/migrations/0001_initial.sql`.

`migration_sets.py` carries a literal reviewed filename, source SHA-256, source
byte length, prefix digest, and complete set digest for each service. A
directory scan is not authority. Editing, renaming, removing, reordering, or
adding a file without changing the reviewed literal release identity refuses
before a database connection is opened. After release, an applied file is
never changed; later schema changes append a gap-free four-digit migration.

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
temporary static owner sealer for the binder, backend-incarnation observer,
graph validator, and tenant-lock functions. The
tenant runner consumes and drops that sealer atomically during `0001`; it is
never recreated after the ledger exists. No runtime role can call either raw
advisory-lock overload or assume the isolated function-owner roles.

Provisioning also closes PostgreSQL's database-local large-object side store.
It freezes the complete 20-routine PostgreSQL 17 `lo_*`/`loread`/`lowrite`
inventory and implementation posture, revokes every PUBLIC EXECUTE path, and
accepts only the bootstrap-superuser owner's symbolic ACL. Both services
require zero `pg_largeobject_metadata` rows before migration and at structural
readiness. An added routine, changed implementation property, widened grant,
or stored large object refuses.

Provisioning also removes the default same-login backend-observation path in
both services. PUBLIC loses SELECT on the exact PostgreSQL 17
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
- an immutable capability-key schedule and exact HMAC-SHA-256 capability frame;
- a protected UNLOGGED context keyed by database-derived PID, backend start,
  and full `xid8`, with one challenge and one final bind per transaction;
- a privileged NOLOGIN backend observer that cannot be inherited or assumed by
  a LOGIN role and exposes only current-incarnation and exact liveness helper
  results to the NOLOGIN binder, plus a NOLOGIN graph validator that remains
  constrained by FORCE RLS and minimum column grants;
- a protected, no-caller-key tenant write lock;
- tenant-qualified composite primary, unique, and foreign keys;
- enabled and forced RLS on every tenant-bearing relation;
- governed write batches, graph integrity, future-identifier refusal, derived
  materialization/dependency keys, and the neutral record-reference carrier;
  and
- exact catalog and contract observers available only to the appropriate
  migration/readiness roles.

The binder validates the immutable binding version, authoritative lifecycle
fold and currentness, pinned tenant/Party identities and digests, one-use
database challenge, full canonical capability frame, HMAC, key schedule, and
time bounds before it publishes a transaction-local binding. Application and
worker SQL cannot establish tenant context through `SET`, request data, a raw
tenant identifier, or a default. Cross-tenant keys, joins, references, and
continuations fail at the database boundary.

Issue #172 owns authentication and external capability signing. Issue #184
owns the complete semantic reference kind/cardinality matrix; #174 supplies
only its isolated neutral relational carrier.

## Security-audit schema

The security-audit migration establishes a separate, non-tenant lane with:

- one closed append API and fixed session-user-to-producer/reason mapping;
- bounded event fields, deterministic retry identity, correlation-digest
  validation, database time, quotas, overflow markers, and bounded query APIs;
- append-only event evidence, visibility-stable access cuts, an event-writer
  close barrier, and protected disposable quota state that cannot reopen;
- declared gap markers and an exact empty-store recreation posture; and
- distinct ingest, control, reader, retention, readiness, and deliberately
  absent recovery/break-glass capabilities.

It never accepts or stores tenant, principal, Party, farm, role, governed-batch,
or knowledge-position fields. It cannot authorize or reconstruct tenant state.
The migration's structural flag proves the #174 schema only. The reserved
runtime-readiness flag remains false until #192 supplies and verifies the
external client and operational controls.

The audit service has no V1 backup, replica, restore, or history-import path.
Loss is represented as an operational evidence gap: recreate an empty verified
service from immutable provisioning and migrations, then let the later #192
control client append a declared gap. This is not tenant recovery.

## Read-only startup gate

`verify_startup_readiness` loads both literal migration identities before it
connects. It then opens both repeatable-read, read-only snapshots before the
first catalog observation. Each transaction fixes
`standard_conforming_strings=on`, `TimeZone=UTC`, `DateStyle=ISO, MDY`, and
`quote_all_identifiers=off` before PostgreSQL deparses any catalog identity, so
caller or cluster display settings cannot change the authenticated bytes. It
then verifies:

- exact readiness session and current-user identities and fixed database names;
- PostgreSQL 17 primary posture, the same patch version, and distinct cluster
  lineages;
- no publication, subscription, replication slot, or live physical-replication
  path in either service;
- the exact closed PostgreSQL 17 large-object routine surface and an empty
  large-object store;
- the exact closed backend-statistics view, routine, ownership, and ACL
  posture;
- the complete ordered seven-column ledger history;
- the complete symbolic catalog identity for each service; and
- the exact tenant and audit contract-observer rows.

Every exit explicitly rolls back and closes both connections. Its returned
manifest exposes only supported and observed schema versions. Errors use closed
diagnostic text and do not include DSNs, observed identifiers, tenant data, or
audit records. The gate performs no DDL, DML, lock acquisition, repair, or
bootstrap.

## Accepted limits

The checked-in conformance workflow proves three disposable, distinct
PostgreSQL 17 lineages and exercises the two services with their real roles.
That evidence does not prove production separation of disks, WAL, network
routes, connection pools, credentials, CPU, memory, storage quotas, monitoring,
or backup targets. Those require deployment evidence and operational controls.

There is no V1 tenant restore, point-in-time promotion, snapshot adoption,
logical history import, or recovery readiness. Issue #193 owns that future
design. Database isolation, migration, recovery, RLS, and direct-SQL boundaries
remain the responsibility of #174; application/pool integration does not
weaken them.
