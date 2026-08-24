# OFARM Security-Audit Witness-Lock Provisioning — Phase A Contract v0.1

## Status

**Decision:** `ISSUE192-SECURITY-AUDIT-WITNESS-LOCK-PROVISIONING-001`

**Version:** 1, proposed and unapproved

**Parent:** issue #192

**Required by:** draft PR #326, decision
`ISSUE192-SECURITY-AUDIT-ADMISSION-TARGET-EPOCH-001` version 3

**Reviewed base:** `5f51f80981599a0da4678d555a02a648b84a2304`

**Primary trust boundary:** PostgreSQL provisioning custody and exact ACLs for
the security-audit witness-lock acquisition wrapper

**Phase A review-head boundary:** this RFC only

**Intended implementation PR boundary:** one separately approved PostgreSQL
provisioning and verifier-admission change; no target-epoch runtime,
credential, deployment, operation, or provider authority

Phase A publishes and reviews a design. It creates no role, grant, function,
credential, migration row, database mutation, deployment action, or Phase B
authority.

## 1. Problem and exact goal

### 1.1 Missing authority

Draft PR #326 needs one retained audit-control session to acquire two
nonblocking, session-level advisory locks derived by its private target-epoch
module. The current service correctly prevents that:

- `ofarm_security_audit_control_login` has `CONNECTION LIMIT 1` and inherits
  only `ofarm_security_audit_control`;
- neither role can execute a raw advisory-lock routine;
- `ofarm_security_audit_owner`, which will own migration 5 after the ordered
  renumbering, also cannot execute either required try-lock routine; and
- the two existing provisioning-owned lock wrappers have fixed keys and
  different purposes.

A migration-owned wrapper cannot manufacture authority its owner does not
have. Giving a runtime or migration role raw advisory-lock execution would
make the caller-selected key surface reusable and would cross the custody
boundary that current provisioning deliberately closes.

### 1.2 Immutable provisioning and migration identities

The existing audit provisioning identity is
`ofarm.security-audit-postgresql-provisioning.v1` at
`sha256:9b9d06c6f6ac5527a32014ec1719a3cee9742d4d5ab7d8e8a4ff2797053824f7`.
Migration 1 permanently records that digest, and all three current migrations
are immutable. Silently adding the new objects to that manifest would give one
digest two meanings. Rewriting migration 1 would destroy the accepted history.

The migration-owned structural verifier also fingerprints every governed
role, membership, schema ACL, default privilege, infrastructure routine, and
raw advisory-routine ACL. Adding the objects without a forward verifier
admission would correctly make readiness fail.

The smallest coherent model is therefore:

1. preserve the existing core provisioning manifest and digest byte for byte;
2. define one independently digested additive witness-lock provisioning spec;
3. append one verifier-only audit migration 4 that admits exactly two core
   states: the current sidecar-absent state and the complete sidecar-exact
   state;
4. permit the external provisioning superuser to perform one atomic
   absent-to-exact transition only after migration 4 is current; and
5. require every consumer that needs the wrapper to verify the sidecar digest
   and exact installed state rather than treating core readiness as proof.

### 1.3 Exact goal

Phase B, if separately approved, will provide exactly:

- one immutable sidecar spec and digest;
- one new isolated NOLOGIN lock-owner role;
- four exact raw routine grants to that owner and no other new raw grant;
- one closed `SECURITY DEFINER` acquisition wrapper in
  `ofarm_infrastructure`;
- one exact schema-USAGE and wrapper-EXECUTE path from the existing audit
  control capability;
- one forward verifier-only migration 4;
- one external-superuser create-or-verify API and one read-only verifier;
- closed absent, exact, and drift classifications; and
- exact manifest, source, role, ACL, migration, structural, drift, and live
  PostgreSQL evidence.

The wrapper grants no target selection, epoch activation, receipt issuance,
lease, credential, export, output, or positive operation result.

### 1.4 Required correction to PR #326

The upstream interface is sound except for one availability detail. A caller
that can repeatedly invoke a caller-key wrapper could accumulate session locks
and exhaust the dedicated service's advisory-lock table. To preserve PR #326's
stated two-lock availability ceiling, this contract requires one read-only
self-session observation of `pg_catalog.pg_locks` before either acquisition.
Any existing advisory lock refuses before a new lock is attempted.

That is the wrapper's only relation read. It exposes no row and reads no
application or audit relation. PR #326 must later be amended to replace its
unqualified “no relation access” wording with this exact system-catalog
exception, move its target-epoch migration from 4 to 5, and pin the merged
sidecar identity. This RFC does not edit or authorize PR #326.

## 2. Learning value and smallest coherent change

This slice proves a reusable security lesson without creating a generic lock
framework: caller-selectable keys can remain closed when raw routine authority
is isolated in an unassumable owner and the only executable wrapper has a
literal source, a bounded call surface, fixed caller identity, and an exact
catalog proof.

It also preserves the difference between two identities:

- the core provisioning digest continues to identify the immutable database
  bootstrap; and
- the sidecar digest identifies the later additive authority.

Combining them would rewrite history. Omitting the sidecar identity would make
the authority unauthenticated. A separate database, new credential, generic
extension mechanism, or target-epoch implementation is larger than required.

## 3. Non-goals

This decision does not:

- implement target selection, a target epoch, activation, quiescence,
  replacement, or receipt issuance;
- authorize Phase B of PR #326 or any other draft;
- add, replace, rotate, reveal, or use a credential;
- alter `ofarm_security_audit_control_login`, its password, its memberships,
  or its exact `CONNECTION LIMIT 1`;
- add a LOGIN, pool, route, service, endpoint, CLI, daemon, scheduler, or
  deployment workflow;
- grant a runtime, migration, schema-owner, or control role any raw advisory
  routine;
- add a public unlock wrapper, a blocking lock call, a shared lock, a
  transaction lock, or `pg_advisory_unlock_all` authority;
- change an existing migration, core provisioning digest, audit contract
  digest, audit relation, clock, producer, reader, retention, export, HMAC,
  observer-root, or store-loss behavior;
- provision or mutate a production database;
- provide repair, reconciliation, downgrade, uninstall, or legacy upgrade;
- claim PostgreSQL advisory locks are a global election or survive service
  loss, clone, failover, or session close; or
- close issue #192.

## 4. Trust model

### 4.1 Protected assets

Protected assets are the existing audit LOGIN and credentials; role graph;
raw advisory-routine ACLs; infrastructure schema ACL; wrapper identity, source,
owner, and ACL; migration and access-clock fixed keys; advisory-lock capacity;
core and sidecar manifest identities; migration history; structural verifier;
catalog identity; service and database identity; and every target, nonce,
epoch, receipt, or operation value that this slice must not receive.

### 4.2 Trusted components and actors

Trusted components are exact PostgreSQL 17.10; the dedicated audit service;
the existing core provisioning spec and migration runner; the immutable three-
migration prefix; the exact migration-4 source admitted by Phase B; the
external catalog verifier; psycopg and trusted Python; and an external
PostgreSQL superuser only while it runs the closed provision-or-verify API.

The existing audit-control credential remains trusted for the availability-
only envelope in section 6.7. It is not trusted to choose a target, mint an
epoch, or obtain raw routine access.

### 4.3 Untrusted inputs and behavior

Untrusted inputs include arbitrary signed scalar key values; NULLs; repeated
wrapper calls; calls from the wrong login or role; existing advisory locks on
the caller session; ordinary lock contention; cancellation; timeout;
connection loss; acknowledgement loss; malformed catalog results; partial or
extra roles, grants, routines, memberships, default privileges, or schema
ACLs; stale migration heads; copied databases; and every value supplied by a
future operation caller.

Operator mistakes that produce detectable drift remain in scope and fail
closed without repair.

### 4.4 Explicitly excluded attacker capabilities

Compromise of the external PostgreSQL superuser, PostgreSQL process, host,
kernel, trusted Python process, repository verification authority, or
deployment authority can bypass this boundary and is excluded. Physical
tampering that preserves every authenticated catalog observation is excluded.

The absence of replication, failover, backup, CDC, and shared clusters remains
the current V1 deployment premise. This decision does not extend it.

## 5. Authority map

| Decision | Sole authority | Explicitly not authority |
| --- | --- | --- |
| Core database provisioning identity | Existing `SECURITY_AUDIT_PROVISIONING_SPEC` canonical manifest and digest | Sidecar presence, migration 4, PR metadata, or a report field |
| Sidecar object identity | New canonical witness-lock provisioning manifest and SHA-256 digest | Core digest, wrapper success, branch name, or user-supplied JSON |
| Whether structural code recognizes the two states | Immutable migration 4 plus external catalog-verifier source pin | Provisioner mutation, readiness alone, or dynamic SQL |
| Whether installation may begin | External superuser route, exact core infrastructure, exact authoritative migration prefix at or beyond migration 4, current catalog identity, and exact ABSENT classification | A control credential, wrapper call, environment switch, or caller assertion |
| Raw try/unlock authority | New unassumable witness-lock owner only | Control capability, control LOGIN, migrator, schema owner, readiness, or target-epoch code |
| Wrapper invocation | Existing `ofarm_security_audit_control` EXECUTE plus exact `SESSION_USER` check for the existing control LOGIN | Role name alone, SET ROLE, migration owner, PUBLIC, or function owner assumption |
| Allowed key values | Three exact scalar arguments after NULL, registered-fixed-key, and self-session-lock checks | Stored target, database row, environment value, or general key registry |
| Successful acquisition | Exact wrapper result `true` from the one retained session after both nonblocking acquisitions | Presence of one lock, a row, a digest, or a caller assertion |
| Phase B authorization | Later user-authored approval of the complete live decision card | This RFC, `go`, reviews, checks, GitHub credentials, or AI text |

## 6. Closed architecture and ordering

### 6.1 Independent sidecar manifest

Phase B defines one frozen sidecar spec with identity
`ofarm.security-audit-witness-lock-provisioning.v1` and canonical JSON digest
policy
`OFARM_SECURITY_AUDIT_WITNESS_LOCK_PROVISIONING_SPEC_SHA256_CANONICAL_JSON_V1`.

Its manifest contains exactly:

- the reviewed core service identity, database name, and core provisioning
  digest as prerequisites, not as fields to be replaced;
- the required minimum migration version and migration-4 identity;
- the owner role and complete role posture;
- all four raw grants, including exact overload types and grantee;
- the existing infrastructure schema, its added USAGE grantee, and no CREATE
  grant;
- wrapper qualified name, argument names and types, return type, language,
  security properties, fixed settings, literal source, owner, and execute
  role;
- the exact session-user and definer-owner values;
- the two forbidden integer-pair keys and their policy identities;
- the acquisition, refusal, release, exception, and connection-close rules;
- the one `pg_locks` self-session observation; and
- explicit empty lists for LOGINs, credentials, memberships, application
  relations, clocks, public wrappers, and positive operation effects.

The sidecar spec may live beside the existing provisioning specs, but it is
not a field of `SECURITY_AUDIT_PROVISIONING_SPEC`. Tests must prove the core
canonical bytes and digest remain exact.

### 6.2 Exact persistent objects and ACLs

The installed state adds only:

1. role `ofarm_security_audit_witness_lock_owner` with `NOLOGIN`,
   `NOINHERIT`, `NOBYPASSRLS`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`,
   `NOREPLICATION`, `CONNECTION LIMIT -1`, no password, no validity limit,
   and no settings;
2. no membership edge in either direction for that role;
3. exact additional raw `EXECUTE` grants to the new owner on:
   - `pg_catalog.pg_try_advisory_lock(pg_catalog.int8)`;
   - `pg_catalog.pg_try_advisory_lock(pg_catalog.int4, pg_catalog.int4)`;
   - `pg_catalog.pg_advisory_unlock(pg_catalog.int8)`; and
   - `pg_catalog.pg_advisory_unlock(pg_catalog.int4, pg_catalog.int4)`;
4. the two standard default-privilege rows for the new owner that revoke
   PUBLIC routine EXECUTE and type USAGE from its future objects;
5. `USAGE`, without `CREATE`, on `ofarm_infrastructure` for
   `ofarm_security_audit_control`;
6. one function
   `ofarm_infrastructure.acquire_security_audit_witness_locks(
   pg_catalog.int8, pg_catalog.int4, pg_catalog.int4)` owned by the new role;
7. the owner's inherent function EXECUTE and one nonowner EXECUTE ACL for
   `ofarm_security_audit_control`, both without grant option; and
8. no other object or ACL row.

These are the only new raw grants. The existing access-clock owner's grant on
`pg_advisory_unlock(pg_catalog.int4, pg_catalog.int4)` and every other baseline
raw-routine ACL remain exact. `PUBLIC` has no infrastructure-schema privilege
and no wrapper EXECUTE. The existing external bootstrap owner remains the
grantor recorded for raw routine grants; the wrapper owner remains the grantor
recorded for wrapper EXECUTE. The infrastructure schema remains owned by
`ofarm_security_audit_migration_lock_owner`.

### 6.3 Exact wrapper posture

The wrapper has:

- argument names `p_bigint_key`, `p_pair_class_id`, and `p_pair_object_id`;
- exact scalar types `pg_catalog.int8`, `pg_catalog.int4`, and
  `pg_catalog.int4`;
- return type `pg_catalog.bool`, not a set;
- trusted language `plpgsql`;
- `VOLATILE`, `PARALLEL UNSAFE`, `SECURITY DEFINER`, non-leakproof, and
  `CALLED ON NULL INPUT`;
- fixed `search_path = pg_catalog, pg_temp`;
- no support function, transform, SQL body, configuration setting, or
  dependency on an application schema; and
- a literal source authenticated by the sidecar manifest, structural
  verifier, external catalog verifier, and focused tests.

The literal body performs only this order:

1. require `SESSION_USER` exactly
   `ofarm_security_audit_control_login`;
2. require `CURRENT_USER` exactly
   `ofarm_security_audit_witness_lock_owner`;
3. reject any NULL argument before a lock call;
4. reject either registered fixed audit integer-pair key before a lock call;
5. count granted advisory locks for exactly `pg_backend_pid()` in
   `pg_catalog.pg_locks` and require zero;
6. call nonblocking `pg_try_advisory_lock(int8)` once;
7. return `false` immediately only when that result is exactly false;
8. refuse a NULL or malformed first result;
9. call nonblocking `pg_try_advisory_lock(int4,int4)` once;
10. return `true` only when that result is exactly true;
11. when the second result is exactly false, call
    `pg_advisory_unlock(int8)` once, require an exact true release, and then
    return `false`; and
12. raise a fixed, non-sensitive exception for every malformed, unexpected,
    or uncertain state.

There is no loop, dynamic SQL, caller-selected routine, blocking call,
relation mutation, clock call, sleep, retry, logging, notice, or catch-and-
continue branch.

The future caller must close the connection immediately on every exception,
malformed result, cancellation, timeout, or cleanup uncertainty. Connection
close is the final cleanup authority for session locks. The wrapper does not
claim it can recover from an exception raised after the first acquisition.

### 6.4 Registered fixed-key rejection

The only registered fixed session-lock integer pairs in the current audit
database are:

| Policy | Class ID | Object ID |
| --- | ---: | ---: |
| `OFARM_POSTGRESQL_MIGRATION_LOCK_V1` | `407601354` | `2115981953` |
| `OFARM_SECURITY_AUDIT_ACCESS_CLOCK_LOCK_V1` | `-274079271` | `-1019032096` |

The first is currently used with a transaction lock, but the pair identity is
still reserved and must not be caller selectable through this session-lock
wrapper. The second is the access-clock session mutex. Both are rejected
before either acquisition.

The bigint and integer-pair advisory namespaces do not overlap. There is no
registered fixed audit bigint key at the reviewed base. Adding any fixed audit
lock domain requires a new sidecar version that extends the manifest rejection
set before that domain becomes reachable.

### 6.5 Forward verifier-only migration 4

Phase B appends
`security_audit/migrations/0004_witness_lock_provisioning_admission.sql`.
It does not create a role, grant, wrapper, relation, type, trigger, index, or
runtime function. It authenticates the complete migration-3 structural-
verifier source and performs unique literal replacements only.

The resulting verifier recognizes exactly two complete projections:

- **W0 / ABSENT:** the current core catalog with no sidecar role, raw grant,
  default privilege, schema USAGE, or wrapper; and
- **W1 / EXACT:** the same core catalog plus every exact item in sections 6.2
  and 6.3.

Every mixed, partial, widened, extra, or malformed projection remains
structurally incompatible. The verifier uses two literal complete-catalog
digests, not a generic ignore list. Its ledger clause advances from the exact
three-row prefix to the exact four-row prefix. The external catalog identity
pins the complete resulting observer/verifier source.

Core readiness may be structurally true in W0 or W1 because it owns the core
service, not target-epoch eligibility. A consumer that needs the witness lock
must separately require W1 and the exact sidecar digest. No core report or
readiness result may be interpreted as that proof.

### 6.6 Provisioning state machine

The durable state machine is:

```text
W0  exact core, exact migration prefix >= 4, sidecar absent
  -> one external-superuser transaction
W1  exact core, exact migration prefix >= 4, sidecar exact

W1  -> read-only verified no-op

Anything partial, extra, stale, or mixed -> REFUSED
```

Before a write, the provisioner must:

1. validate the fixed checked-in sidecar spec;
2. connect as one external superuser to database `postgres`;
3. verify the exact PostgreSQL build, writable-primary posture, dedicated
   database inventory, and core provisioning identity;
4. acquire the existing cluster provisioning lock nonblockingly;
5. verify the target route reaches the same system identifier;
6. verify exact core infrastructure while allowing only W0 or W1;
7. authenticate the current authoritative audit migration history as an exact
   local prefix whose head is at least migration 4;
8. authenticate the current external catalog-verifier identity; and
9. classify the complete sidecar surface.

W1 returns an exact read-only report. W0 opens one target-database transaction
with `synchronous_commit=on`, repeats every mutation-relevant precondition,
performs the fixed DDL and grants, verifies exact W1 inside that transaction,
and commits once. It then performs one fresh read-only exact verification
before returning the report.

There is no write retry. Failure before commit rolls back to W0. A lost commit
acknowledgement yields only W0 or W1 and returns no success claim; a later
invocation classifies W0 for one fresh attempt or W1 for a verified no-op.
Partial state is never repaired. There is no uninstall API.

### 6.7 Availability and authority envelope

The existing control credential can already occupy its only allowed control
session indefinitely. After W1 it can additionally attempt one wrapper call
per clean session. The self-session precheck ensures a session can hold at
most the two requested advisory locks through this surface. A successful call
cannot be followed by another acquisition on that session; a refused second
lock releases the first before returning false.

A malicious credential holder can choose two nonregistered addresses and
hold them until connection close. That is availability-only under the current
closed registry: it cannot choose either fixed governed pair, obtain a raw
routine, read an audit relation, select a target, create an epoch, or produce a
positive operation result. The credential's one-session limit remains exact.

If a future governed audit-lock domain, shared cluster, or different control
credential makes this envelope incomplete, work stops for a new decision.

### 6.8 Reports and diagnostics

The public sidecar verification report contains only fixed public identity:

- report schema version;
- core service identity and core provisioning digest;
- sidecar identity and sidecar digest;
- database name, system identifier, and PostgreSQL version number;
- observed exact migration head and prefix digest; and
- `installedExact: true`.

It contains no DSN, password, key arguments, backend PID, SQL text, target,
nonce, epoch, lock address, receipt, exception detail, or catalog row. It does
not claim this invocation performed the install.

## 7. Invariants and acceptance criteria

- **WLP-001 — Core identity is immutable.** Core canonical manifest bytes,
  digest, migration 1 bytes, and migrations 2 and 3 remain exact.
- **WLP-002 — Independent sidecar identity.** Every installed-state claim is
  bound to one canonical sidecar manifest and digest.
- **WLP-003 — One isolated owner.** The new role is closed, unassumable, has no
  credential or membership, and owns only the wrapper and its default ACLs.
- **WLP-004 — Four additional raw grants only.** The exact overloads gain only
  the new owner, without grant option; all baseline raw ACLs remain exact,
  including the access-clock owner's existing integer-pair unlock grant.
- **WLP-005 — One callable wrapper.** PUBLIC is revoked, the only nonowner
  grantee is the existing control capability, and the exact control LOGIN is
  enforced inside the body.
- **WLP-006 — Bounded acquisition.** Calls are nonblocking, begin from zero
  self-session advisory locks, acquire bigint then pair, and normally return a
  nonnull boolean only.
- **WLP-007 — False means no held witness lock.** First refusal acquires
  nothing; second refusal releases the first exactly before false.
- **WLP-008 — True means both held by one session.** No success is returned
  after only one acquisition.
- **WLP-009 — Governed keys are unreachable.** Both registered fixed audit
  pairs are rejected before a lock call.
- **WLP-010 — Uncertainty closes the session.** Malformed results, exception,
  cancellation, timeout, or uncertain release cannot return success and require
  immediate caller connection close.
- **WLP-011 — No relation or time authority.** The only relation read is the
  fixed self-session `pg_locks` count; no audit relation or clock is reachable.
- **WLP-012 — Closed two-state structural law.** W0 and W1 are accepted;
  every partial or widened state fails both external and migration-owned proof.
- **WLP-013 — Migration 4 is verifier-only.** It changes only the final
  structural verifier and its exact ledger/catalog identities.
- **WLP-014 — Ordered mutation.** The provisioner writes only at exact
  migration head 4 or a later exact local prefix and only from W0.
- **WLP-015 — Atomic, idempotent, and non-repairing.** A commit produces W1;
  rollback produces W0; W1 is a read-only no-op; drift refuses.
- **WLP-016 — Existing control posture is exact.** No LOGIN, credential,
  membership, connection limit, role setting, or database CONNECT grant changes.
- **WLP-017 — No target-epoch authority.** Neither manifest, migration,
  wrapper, report, nor test selects a target or creates an operation result.
- **WLP-018 — Closed repository boundary.** Phase B changes only section 11
  paths, all evidence passes, and no demonstrated in-scope Blocker remains.

## 8. Production-reachable negative cases

| Invariant | Counterexample that must refuse or fail |
| --- | --- |
| WLP-001–002 | Core digest changes, sidecar bytes are caller supplied, or a report omits either digest |
| WLP-003 | Owner can LOGIN, has a password/setting, appears in any membership edge, or can be assumed by migrator/control/runtime |
| WLP-004 | Wrong overload, fifth raw grant, grant option, PUBLIC grant, or raw grant to a caller role |
| WLP-005 | Wrong session user, SET ROLE caller, extra EXECUTE grantee, wrong owner, invoker security, writable search path, or source drift |
| WLP-006 | Existing self-session advisory lock, blocking call, reversed order, loop, NULL argument, or NULL normal result |
| WLP-007–008 | Second refusal leaves bigint held, first refusal changes lock state, or true is returned with fewer than two locks |
| WLP-009 | Either fixed pair reaches a raw try-lock call |
| WLP-010 | Exception or malformed result is converted to false/true or the future caller reuses the connection |
| WLP-011 | Wrapper reads an audit relation, clock, environment, file, network, or a row not limited to its own advisory-lock count |
| WLP-012 | Role-only, grant-only, wrapper-only, extra ACL, altered default privilege, wrong source, or third catalog projection passes |
| WLP-013 | Migration 4 creates or grants an object, changes an old migration, or accepts an unpinned predecessor source |
| WLP-014–015 | Install before migration 4, write retry after ambiguity, repair of partial state, or W1 mutation on a second call |
| WLP-016 | Control LOGIN limit becomes 2, a new credential appears, or an existing membership/grant changes |
| WLP-017 | Wrapper receives nonce/target/epoch, touches epoch state, or returns a lease/receipt/operation result |
| WLP-018 | Nineteenth path, red hosted lane, unresolved Blocker, or changed trust boundary |

Live tests must use real separate sessions to prove first-lock contention,
second-lock contention and release, success and exact `pg_locks` shape,
repeat-call refusal, fixed-key refusal, wrong-login refusal, raw-call denial,
disconnect cleanup, W1 no-op, rollback to W0, and representative drift.
Private-field mutation and mocked SQL alone are not acceptance evidence.

## 9. Proposed architecture and smallest change

### 9.1 One additive spec, one installer

The sidecar spec reuses the repository's frozen role and canonical-manifest
patterns without joining the core manifest. Provisioning adds one literal
public provision-or-verify function and one literal read-only verifier. It
does not introduce an extension registry, general role builder, generic ACL
reconciler, or dynamic DDL plan.

### 9.2 One wrapper, no unlock surface

One acquisition function is enough. A public unlock function would let a
borrower silently destroy the retained witness. Normal lifetime is session
lifetime; failure cleanup is connection close. The raw owner needs unlock
authority only to undo the first acquisition after ordinary second-lock
contention.

### 9.3 One verifier-only forward migration

Migration 4 is the minimum durable structural admission. It preserves all
earlier bytes and lets fresh store-loss recovery remain W0 until a separately
authorized deployment installs W1. Requiring W1 in generic readiness would
silently add target-epoch deployment policy to the core audit contract.

### 9.4 No compatibility or repair branch

W0 is the exact old state, not a legacy approximation. W1 is the exact new
state. There is no accepted partial state, renamed role, alternate function,
digest allowlist, environment selector, or automatic repair.

## 10. Elegance audit

### 10.1 Sources of truth

There are exactly three non-overlapping authorities:

1. the unchanged core provisioning digest for bootstrap;
2. the migration-set and catalog identities for structural law; and
3. the sidecar digest for additive lock custody.

Each answers one question. No duplicated field independently grants access.

### 10.2 Authoritative transitions

There are two durable transitions:

1. migration 4 changes structural law from one accepted projection to the
   closed W0/W1 pair; and
2. the external provisioner changes W0 to W1 atomically.

Target-epoch activation is not a third transition in this PR.

### 10.3 Complexity controls

Phase B prefers literal checks over abstraction. Production growth is
justified only by exact classification, DDL, and verification of this custody
transition. A generic sidecar registry, advisory-lock service, migration phase
framework, repair engine, or runtime adapter is overdesign and stops the PR.

### 10.4 Phase B size budgets

- `provisioning_specs.py` production delta: at most 300 physical lines;
- `provisioning.py` production delta: at most 900 physical lines;
- migration 4: at most 650 physical lines;
- new focused test module: at most 1,600 physical lines;
- no dependency, lockfile, workflow, container, command, service, endpoint,
  scheduler, test-glob, or shared test-line-limit change; and
- a ceiling increase requires a new decision version rather than a mechanical
  exception.

## 11. Pull-request boundary

The Phase A head changes only:

1. `docs/rfcs/OFARM_Security_Audit_Witness_Lock_Provisioning_RFC_v0_1.md`

A later exact approval may authorize a strict subset of these eighteen Phase B
paths:

1. `docs/rfcs/OFARM_Security_Audit_Witness_Lock_Provisioning_RFC_v0_1.md`
2. `security_audit/migrations/0004_witness_lock_provisioning_admission.sql`
3. `deployment/postgresql/provisioning_specs.py`
4. `deployment/postgresql/provisioning.py`
5. `deployment/postgresql/migration_sets.py`
6. `deployment/postgresql/catalog_identity.py`
7. `deployment/postgresql/README.md`
8. `deployment/postgresql/__init__.py`
9. `kernel/tests/test_security_audit_witness_lock_provisioning.py`
10. `kernel/tests/test_postgresql_provisioning.py`
11. `kernel/tests/test_migration_sets.py`
12. `kernel/tests/test_postgresql_migration_runner.py`
13. `kernel/tests/test_postgresql_audit_migration.py`
14. `kernel/tests/test_postgresql_structural_compatibility.py`
15. `kernel/tests/test_postgresql_catalog_identity_unit.py`
16. `kernel/tests/test_postgresql_provisioning_native_authority.py`
17. `conformance/temporal_contract_candidate_check.py`
18. `conformance/review_baseline_test_inventory.json`

Path 2 may only authenticate and replace the final structural verifier. Paths
5 and 6 record mechanically derived migration and catalog identities. Path 17
may change only the existing `provisioning_specs.py` byte-length and SHA-256
source pin. Path 18 is mechanical test-node inventory regeneration only.
Unneeded allowlisted paths remain unchanged.

No target-epoch module or migration, store-loss production path, readiness
production path, audit contract, old migration, credential, workflow,
container, cloud, provider, IAM, KMS, application, export, output, or
deployment file is allowed. A need for a nineteenth path or another authority
stops Phase B for a versioned amendment or separate PR.

The primary trust boundary remains PostgreSQL provisioning custody and its
mechanical structural admission. No cross-boundary exception is requested.

## 12. Provisional design record

- Decision identity: proposed
  `ofarm.security-audit-witness-lock-provisioning.issue192.v0.1`.
- Reviewed base: `5f51f80981599a0da4678d555a02a648b84a2304`.
- Core provisioning identity and digest: unchanged.
- Current audit migration head: 3 at
  `sha256:f057490417dacdcda8a2d79c2326c6ba5117a5241572ad02ccfb881cd1345b96`.
- New structural admission: migration 4, verifier-only.
- New persistent authority: one NOLOGIN owner, four raw grants, one schema
  USAGE, one wrapper EXECUTE path, and two default-privilege rows.
- New LOGINs, credentials, memberships, relations, clocks, and operation
  surfaces: zero.
- Accepted durable catalog projections after migration 4: W0 and W1 only.
- Wrapper call ceiling: at most two new advisory locks on a clean one-session
  control connection.
- Deployment, provider, IAM, database mutation, Phase B, merge, and issue-
  closure authority: absent.

This design is provisional until exact-head Phase A review and architect
approval. Phase B identities derived from final source are intentionally not
invented in Phase A.

## 13. Traceability and verification

| Invariant | Owning change | Smallest acceptance evidence |
| --- | --- | --- |
| WLP-001–002 | Independent sidecar spec | Structured before/after core canonical-byte comparison plus sidecar digest test |
| WLP-003–005 | Role creation, raw ACLs, schema ACL, wrapper DDL | Complete catalog rows, membership closure, source/owner/ACL drift tests |
| WLP-006–010 | Literal wrapper body | Real multi-session contention, result, lock-shape, fixed-key, repeat-call, and disconnect tests |
| WLP-011 | Fixed source and privilege inventory | Source assertion and relation/clock privilege tests |
| WLP-012–013 | Migration 4 and both verifiers | W0/W1 success, mixed-state failures, migration rollback, final catalog identity |
| WLP-014–015 | Closed provision-or-verify flow | Stale-head refusal, W0 install, W1 no-op, injected rollback, ambiguity classification |
| WLP-016–017 | Exact diff and authority tests | Existing role/credential/membership bytes and target-epoch paths unchanged |
| WLP-018 | PR gate | Base-to-head path audit, focused/full tests, hosted checks, exact-head reviews |

### 13.1 Required Phase A evidence

Before a live decision card:

- exact diff proving only this RFC changed;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- `git diff --check`;
- complete hosted conformance at the exact head;
- confirmation that the reviewed base is still current `main`; and
- two independent exact-head Phase A reviews, each reporting zero
  demonstrated in-scope Blockers.

### 13.2 Required Phase B evidence

Before merge:

- canonical sidecar-manifest and stable-digest tests;
- exact proof that core manifest bytes and digest did not change;
- exact role, membership, password, setting, database-access, default-ACL,
  schema-ACL, raw-routine-ACL, function-source, owner, grantor, and object-
  inventory tests;
- fresh W0 and W1 external verifier evidence;
- migration-4 source, hash, byte-length, prefix, ledger, rollback, no-op, and
  immutable-old-migration evidence;
- W0 and W1 migration-owned structural success and a complete representative
  mixed-state drift matrix;
- external catalog-verifier identity evidence;
- real PostgreSQL wrapper tests listed in section 8;
- proof that the control LOGIN, password posture, membership, and connection
  limit remain exact;
- affected provisioning, migration-runner, audit-migration, readiness,
  structural-compatibility, catalog-identity, and store-loss regression suites;
- mechanical temporal source-pin and review-inventory verification;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- `git diff --check`;
- exact base-to-head path audit; and
- complete hosted conformance at the exact implementation head.

## 14. Review classification and open decisions

An in-scope Blocker demonstrates that:

- the core provisioning digest or an old migration must change;
- W0 and W1 cannot be distinguished from a partial or widened state;
- the wrapper can accumulate more than two new advisory locks per session;
- a fixed governed key reaches a raw routine;
- false can leave a witness lock held after ordinary contention;
- true can be returned without both locks;
- a runtime or migration role receives raw authority;
- the owner can be assumed, LOGIN, or carry a credential;
- generic readiness is treated as W1 proof;
- migration 4 performs an authority mutation rather than verifier admission;
- the provisioner writes before exact migration 4, retries a write after
  ambiguity, or repairs drift;
- an error can return success or preserve a reusable future caller connection;
- a target, nonce, epoch, operation, relation row, or clock enters the wrapper;
- implementation crosses the exact path or trust boundary; or
- evidence cannot prove the live PostgreSQL behavior.

A preference for a distributed lock service, new credential, general
provisioning extension registry, relation-backed lease, automatic deployment,
or combined target-epoch implementation is a follow-up unless it demonstrates
one invariant cannot hold.

There are no knowingly open design choices inside this version. Review may
demonstrate a Blocker; it may not silently choose a wider authority.

## 15. Dependencies, follow-ups, and stop conditions

### 15.1 Dependencies

- The exact core audit provisioning and three-migration prefix are merged at
  the reviewed base.
- PR #326 is an unimplemented Phase A consumer and grants no authority here.
- No cloud fixture, provider, IAM, KMS, observer-root, or export dependency
  exists.

### 15.2 Ordered follow-ups

1. Publish and review this one-file Phase A RFC.
2. Display the complete live card only after section 13.1 passes.
3. Obtain the exact version-1 architect approval.
4. Implement and review only section 11 Phase B.
5. Merge the prerequisite only after exact implementation-head evidence.
6. Amend PR #326: pin the merged prerequisite, permit the exact self-session
   `pg_locks` read, rename its future migration to 5, and obtain new exact-head
   reviews.
7. Only then may PR #326 display its own live card and seek its own Phase B
   approval.

### 15.3 Stop and reapproval conditions

Stop for a new version or separate decision if implementation needs:

- a LOGIN, credential, membership, connection-limit change, or role setting;
- a fifth raw grant or any raw runtime/migration grant;
- another wrapper, public unlock, blocking call, relation mutation, clock, or
  stored state;
- a third accepted catalog projection or generic extension registry;
- repair, reconciliation, uninstall, or existing-target mutation before
  migration 4;
- an old migration or core digest edit;
- a target-epoch, store-loss, readiness, credential, deployment, provider, or
  application production-path edit;
- a path outside section 11;
- a cross-boundary exception; or
- Phase B before the exact live-card approval.

## 16. Phase A publication and decision card

Publishing this RFC to a draft pull request is Phase A only. A generic `go`,
review, check, branch push, repository credential, or PR approval does not
authorize Phase B.

Before the live card, the RFC must be bound to its exact draft PR URL, base,
head, one-path diff, hosted checks, two independent zero-Blocker exact-head
reviews, sidecar contract, migration-4 two-state law, prospective path
boundary, evidence, exclusions, and stop conditions.

Only then may the card display this exact approval form:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-WITNESS-LOCK-PROVISIONING-001 version 1.
```

That exact later user-authored message after the complete card would authorize
only the section 11 Phase B boundary. It would not authorize database
provisioning or migration execution, deployment, production mutation, target-
epoch Phase B, PR #326 edits, provider or IAM action, credentials, export,
output, merge, or issue closure.
