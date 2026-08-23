# OFARM Security-Audit Store-Loss Recovery — Phase A Contract v0.1

**Status:** Phase A design published for review; Phase B implementation,
deployment, destructive cleanup, and production operation are not authorized

**Draft pull request:** https://github.com/samovers/OFARM2/pull/324

**Contract identity:**
ofarm2.security-audit-store-loss-recovery.v0.1

**Decision identity:**
ISSUE192-SECURITY-AUDIT-STORE-LOSS-RECOVERY-001, version 1

**Issue:** #192

**Reviewed base:** bdf636d155e45ecbf4d9ac828e232bbcf91e1d59

**Primary trust boundary:** non-destructive creation and admission of one
verified-empty replacement security-audit store, followed by one honest
unknown-count evidence gap before that store may be published to producers

**Phase A review-head boundary:** this RFC only

**Maximum final pull request boundary:** this RFC; one fixed deployment-layer
recovery runner; one fixed command adapter; focused unit and live-PostgreSQL
tests; minimal operator documentation; architecture-budget registration; and
the mechanically regenerated review-baseline test inventory only

## 1. Problem and goal

The accepted security-audit design deliberately has no backup, replica, CDC,
restore, or history-import path. If the audit store is lost, ADR 0001 requires
an empty service recreated from immutable provisioning and migrations and an
honest AUDIT_GAP with COUNT_UNKNOWN. The repository currently proves the
ingredients only in a test: test-only code destroys a service, calls the
provisioner and migration runner, checks that old rows are absent, and then
manually calls append_audit_gap.

That test is not an operator-safe recovery operation. Nothing currently binds
these facts into one fail-closed transition:

1. the target database and every governed audit role were absent when this
   invocation started;
2. this invocation, rather than an earlier deployment, created the target;
3. this invocation applied the complete authoritative migration set from
   version zero;
4. the migrated target contained no operational event, quota, high-water, or
   used overflow-receipt state;
5. the loss interval began at an externally witnessed conservative time and
   ended at the replacement database's clock while producer routes remained
   unpublished;
6. exactly one unknown-count gap became durable; and
7. no success result was emitted before the final state was verified.

The missing binding permits unsafe operator improvisation. An operator could
append a gap to an old but currently empty store, publish a fresh store before
the gap is durable, retry a non-idempotent maintenance append after an
ambiguous commit, or mistake a partially recreated target for a recovered
service.

This decision establishes one fixed, one-shot recovery operation. It:

1. accepts one canonical conservative loss-start timestamp, one bounded
   release identity, and one canonical non-nil migration execution UUID;
2. uses only the checked-in security-audit provisioning specification and
   authoritative migration set;
3. invokes the existing non-destructive provisioner and requires its report to
   say created = true;
4. invokes the existing migration runner once and requires previous version
   zero, the complete applied-version tuple, and the exact final version;
5. proves the exact fresh-state inventory before the gap append;
6. obtains the interval end from PostgreSQL clock_timestamp under the exact
   audit-control login with synchronous_commit on;
7. invokes only append_audit_gap(loss_start, database_end, 0, true), at most
   once;
8. performs one bounded read-only final observation, including after a commit
   ambiguity, and succeeds only if the replacement store contains exactly the
   one expected gap and no producer/quota activity; and
9. emits one canonical non-secret success report only after that observation.

The operation never drops, deletes, truncates, restores, copies, repairs, or
adopts a database, role, event, or history. An external DBA must already have
declared the old audit service lost and made the fixed target database and
governed roles absent. That destructive or infrastructure action is a separate
authority and is not implemented or authorized here.

The replacement route must remain quarantined from all producers, readers,
retention jobs, runtime startup, and publication until this operation returns
its exact success report. A failed, interrupted, or indeterminate run leaves
the target quarantined. It is never retried or repaired in place by this
operation.

## 2. Learning value

This slice proves that the accepted no-restore posture is operationally
coherent without adding a backup system, recovery ledger, new migration,
generic disaster-recovery framework, or destructive repository command.

It reduces the demonstrated risks that:

- an apparently empty but previously used audit store is silently adopted;
- a replacement is published with no durable disclosure of the lost interval;
- a non-idempotent AUDIT_GAP append is duplicated after an ambiguous commit;
- partial provisioning or migration is reported as recovery; or
- a recovery tool gains drop, restore, history-import, producer, reader,
  retention, HMAC, or tenant authority.

It also validates the smallest viable idempotence boundary: each attempt gets
one provably new target. A failed attempt is quarantined instead of requiring
new persistent recovery state in the audit schema.

## 3. Non-goals

This pull request does not change or add:

- any numbered migration, database function, relation, sequence, role, grant,
  provisioning specification, migration set, structural contract, or
  retention policy;
- a DROP DATABASE, DROP ROLE, DELETE, TRUNCATE, restore, backup, snapshot,
  replica, WAL, CDC, logical import, filesystem copy, or history-copy path;
- automatic loss detection, a loss monitor, crash witness, host agent,
  heartbeat, scheduler, queue, spool, local receipt, or recovery registry;
- a generic tenant or PostgreSQL disaster-recovery mechanism;
- repair or adoption of an existing, partial, migrated, or previously used
  audit target;
- a retry of provisioning, migration, append, or the complete operation;
- a caller-selected database, schema, role, migration, SQL function, producer,
  component, event kind, event count, interval end, retention period, or
  publication target;
- a claim that the externally supplied loss start is independently proven by
  this repository operation;
- producer publication, runtime startup, credential distribution, deployment
  activation, service routing, load-balancer mutation, or readiness-policy
  change;
- current live-process gap reconciliation, process-crash detection, overflow
  closure, HMAC retirement, reader, export, break-glass, temporary login, or
  retention execution;
- tenant repositories, tenant credentials, TenantBinding, tenant UnitOfWork,
  issue #176, or any tenant truth or knowledge order;
- physical erasure, legal hold, current/default promotion, release,
  production access, production readiness, issue closure, or a security
  waiver.

The operation covers loss of the audit store itself. A live process that dies
while the original store remains intact, with no independently witnessed loss
start and no fresh replacement target, remains separate #192 crash-witness
work.

## 4. Trust model

### 4.1 Protected assets

- the truth that the replacement target was created by this exact invocation;
- the exact checked-in provisioning and migration identities;
- the absence of copied, restored, or previously retained operational
  security history;
- one conservative disclosure interval with unknown event count;
- no producer access before the disclosure is durably verified;
- no duplicate maintenance append after commit ambiguity;
- separation of DBA, migrator, and audit-control capabilities;
- all PostgreSQL DSNs and login passwords;
- bounded non-sensitive diagnostics and output;
- the existing no-backup/no-replica/no-CDC posture; and
- every tenant database, credential, row, and authority, which this operation
  must not address.

### 4.2 Trusted components and premises

- the existing fixed SECURITY_AUDIT_PROVISIONING_SPEC;
- the authoritative SECURITY_AUDIT_SERVICE migration set loaded from the
  checked-out package;
- provision_service and its create-only-or-read-only-verify behavior;
- migrate_service and its exact migration identity, transaction, ledger, and
  final-structure checks;
- PostgreSQL transaction semantics, session_user, synchronous_commit, and
  clock_timestamp;
- the immutable append_audit_gap(timestamp with time zone, timestamp with time
  zone, bigint, boolean) function;
- an external security-operations authority that declares loss and supplies a
  conservative loss-start timestamp;
- an external DBA authority that makes the fixed target and governed roles
  absent before invocation, without presenting restored history;
- a deployment authority that keeps every replacement route and credential
  unpublished until the exact success report is accepted;
- deployment evidence that the replacement PostgreSQL clock remains
  non-regressing throughout the recovery operation;
- protected secret injection for the fixed DSNs and exact provisioning login
  password map; and
- the exact package bytes at the reviewed release.

The external authorities are deployment prerequisites, not self-attestations
created by this command. This repository operation validates the target state
it can observe and refuses to claim more. A fresh target has no earlier durable
database-clock high-water, so the repository operation cannot prove that the
clock did not regress before its first observation.

### 4.3 Untrusted actors and inputs

An attacker may control or corrupt:

- command arguments, environment-variable presence, whitespace, encoding, and
  malformed timestamp or UUID values;
- a DSN that reaches the wrong database, role, server, or PostgreSQL version;
- unexpected existing databases, roles, schemas, relations, migration rows,
  events, quotas, high-water rows, used overflow receipts, sequence state, or
  sessions;
- database result shapes, duplicate rows, nulls, infinities, clock regression,
  and ordinary connection errors;
- timing, interruption, cancellation, output failure, and connection loss
  before, during, or after COMMIT; and
- an attempt to invoke the command again against the same target.

The attacker may not choose a second operation, database, role, migration set,
SQL function, interval end, or known event count.

### 4.4 Explicitly excluded attacker capabilities

Arbitrary in-process memory mutation, local source substitution after package
admission, compromised Python or PostgreSQL dependencies, hostile kernel or
hypervisor control, mutation of the checked-out package during execution,
compromise of the external DBA/security-operations/deployment authorities, and
theft of the protected secret-injection channel are out of scope.

Filesystem content is never a recovery authority. No local file, cached
report, prior stdout, or operator-authored JSON can prove target freshness or
append success.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Fixed service, database, roles, grants, and absent capabilities | SECURITY_AUDIT_PROVISIONING_SPEC |
| Exact migration membership, order, bytes, and final version | authoritative SECURITY_AUDIT_SERVICE migration set |
| Permission to declare this a store-loss attempt | external security-operations authority |
| Conservative interval start | exact canonical timestamp supplied by that external authority |
| Target and governed-role absence before creation | existing provision_service observation under the external DBA route |
| Proof this invocation created the target | returned ProvisioningReport.created is exactly true |
| Migration started from version zero and completed | exact MigrationRunReport from this invocation |
| Fresh operational-data posture | fixed admin read-only inventory after migration |
| Exact structural compatibility | existing audit-readiness verifier over the fixed readiness route |
| Interval end and event observed time | replacement PostgreSQL clock_timestamp |
| Gap event kind, producer, component, count posture, and retention | append_audit_gap and migration constraints |
| Clock monotonicity throughout recovery | external deployment evidence; never a process-clock or fresh-database self-attestation |
| Gap durability acknowledgement | synchronous commit plus final read-only observation |
| Whether producers may be published | external deployment authority consuming exact success only |
| Public result bytes | one fixed canonical renderer |

There is no legacy fallback, alias, alternate write path, recovery file, or
second source of truth. The external loss start is not copied into another
mutable authority before use. The final report describes the database state;
it does not grant publication authority by itself.

The runner receives the exact admin, migrator, control, and readiness routes
and the exact provisioning password map as one bound invocation object. It
does not accept role names or arbitrary mappings from command-line arguments.
The existing provisioner rejects missing, extra, or wrong role-password keys.

## 6. State machine and ordering

### 6.1 States

The runner has these closed states:

1. VALIDATING — no PostgreSQL connection or side effect has begun.
2. PROVISIONING — the existing create-or-verify provisioner has been entered.
3. CREATED — the exact report proves this invocation created the target.
4. MIGRATING — the existing authoritative migration runner has been entered.
5. MIGRATED_EMPTY — migration and the fixed fresh-state observation succeeded.
6. GAP_PRE_COMMIT — the control transaction is open and no COMMIT was sent.
7. GAP_COMMIT_IN_FLIGHT — COMMIT was sent and acknowledgement is not yet known.
8. VERIFYING — no further mutation is permitted; one final read-only
   observation is in progress.
9. RECOVERED — the exact final state is proven and one success report exists.
10. QUARANTINED — recovery did not succeed and the target must not be
    published.
11. OUTCOME_UNKNOWN — the final observation cannot prove the one-gap state
    after COMMIT became ambiguous; this is a terminal quarantined state.

RECOVERED, QUARANTINED, and OUTCOME_UNKNOWN are terminal. OUTCOME_UNKNOWN is a
more specific quarantined result, never a retry state.

### 6.2 Validation before side effects

Before entering PROVISIONING, the runner must validate:

- the request and secret carrier have exact types;
- the loss start is one finite timezone-aware UTC timestamp in the canonical
  command representation;
- release identity satisfies the existing migration-runner grammar and bound;
- execution identity is one canonical non-nil UUID;
- every required DSN and exact password-map member is present and non-empty;
- no extra command argument, environment-selected role, database, or action is
  accepted; and
- loss start is not sourced from process wall-clock fallback.

Validation never probes the database merely to improve an error message.

Every supplied DSN is parsed and rebuilt before use. Caller-supplied
connect_timeout and options values are replaced, not merged. Every PostgreSQL
connection has connect_timeout = 5 seconds. Provisioning and migration routes
use statement_timeout = 300,000 milliseconds and lock_timeout = 5,000
milliseconds. The control route and both admin inventory observations use
statement_timeout = 2,000 milliseconds and lock_timeout = 250 milliseconds.
The readiness route uses statement_timeout = 5,000 milliseconds and
lock_timeout = 250 milliseconds. No timeout is caller-selectable.

Those settings bound connection establishment and PostgreSQL statement and
lock waits. They do not impose a wall-clock deadline on Python cleanup,
operating-system connection close, or stdout/stderr writes. This decision adds
no process watchdog or signal authority. A blocked cleanup or output write can
withhold completion indefinitely, but cannot complete the canonical success
report or success exit, cause a second mutation, or cause a retry. Focused
tests cover timeout expiry,
ordinary failures, short writes, and flush failures; they do not claim to
execute an indefinitely blocked OS call.

### 6.3 Creation and migration

The runner calls provision_service exactly once with:

- the fixed admin route;
- SECURITY_AUDIT_PROVISIONING_SPEC; and
- the exact fixed login-password map.

Any exception or report with created other than true enters QUARANTINED. An
existing target, even if perfectly verified and empty, is not adopted.

The runner then loads the authoritative audit migration set from the package
and calls migrate_service exactly once. The report must bind the expected
audit migration-service identity, the expected audit provisioning-service
identity from the preceding report, and the same provisioning digest,
database, and system identifier. It must prove:

- previous_version = 0;
- applied_versions equals every authoritative version in order;
- final_version equals the authoritative set length;
- observed_head_execution_id equals this invocation's execution ID; and
- verified_noop is false.

Any difference enters QUARANTINED. MigrationOutcomeUnknown is not retried by
this operation, even though the general migration runner supports
same-execution reconciliation. A later external cleanup may discard this
unpublished target under separately authorized DBA control.

### 6.4 Fresh-state observation

Under the fixed admin route, one repeatable-read, read-only transaction checks
the exact migrated target and system identifier and requires:

- zero operational_security_event rows;
- zero operational_security_quota_bucket rows;
- zero operational_security_quota_high_water rows;
- exactly 256 fixed event-identity lock slots;
- exactly 512 fixed overflow identity receipts, all with event_id,
  append_input_fingerprint, bucket_start, and purge_after null;
- the access-clock sequence still at its migration-created initial,
  never-called posture;
- exactly the authoritative migration ledger.

The migration report already includes the migration runner's accepted final
structure check. The new admin query does not copy the existing readiness
verifier's catalog rules.

The transaction returns counts and booleans only. It never returns event
contents, credentials, role passwords, or SQL text. Any unexpected state
enters QUARANTINED before the gap append.

This check proves fresh migrated database state. The separate deployment
quarantine premise prevents a producer or maintenance job from racing between
this observation and final verification. If that premise cannot be enforced,
the operation is not deployable and must not be invoked.

### 6.5 Gap transaction

The runner opens one non-autocommit control connection with fixed bounded
connection, statement, and lock timeouts and synchronous_commit on. It checks
the effective session_user and synchronous_commit setting.

Inside one transaction it:

1. reads one clock_timestamp as interval_end;
2. refuses if interval_end is not finite and strictly after loss_start;
3. invokes exactly:

~~~text
SELECT *
FROM ofarm_security.append_audit_gap(loss_start, interval_end, 0, true)
~~~

4. validates the exact three-field non-nil event identity result, requires its
   finite observed_at to be greater than or equal to interval_end, and
   requires purge_after to equal observed_at plus exactly 30 days;
5. moves to GAP_COMMIT_IN_FLIGHT immediately before COMMIT; and
6. sends COMMIT once.

No retry, savepoint, second append, compensating mutation, or alternate
function is permitted.

An error proven to occur before COMMIT rolls back and enters QUARANTINED. A
COMMIT acknowledgement moves to VERIFYING. An exception after COMMIT was sent
also moves to VERIFYING but records that the acknowledgement was ambiguous.

### 6.6 Final observation and ambiguity

The runner performs exactly one new repeatable-read, read-only admin
observation. Success requires:

- exactly one operational event total;
- that event has the exact event ID returned before COMMIT when that identity
  is available;
- event_kind = AUDIT_GAP;
- producer = SECURITY_OPERATIONS_V1;
- component = AUDIT_CONTROL;
- interval_start equals the supplied loss start;
- interval_end equals the database end captured by this invocation;
- observed_at is finite and greater than or equal to interval_end;
- purge_after equals observed_at plus exactly 30 days;
- interval_event_count is null;
- interval_count_unknown is true;
- correlation HMAC fields, reason, access fields, retention-operation fields,
  and affected producer/component are null;
- event-format, redaction, retention, and fingerprint shape remain exact;
- zero quota-bucket and zero quota-high-water rows;
- all 512 overflow receipts remain unused;
- operational_security_access_clock_high_water still has last_value = 0 and
  is_called = false; and
- the migration identity remains exact.

After that fixed admin observation, the existing audit-readiness verifier runs
once over the fixed readiness route. RECOVERED requires its exact
structural-compatibility report as well as the one-event observation.

If COMMIT acknowledgement was ambiguous but this exact one-event state is
visible, the operation may return RECOVERED. The fresh-target invariant and
one-append maximum make that observation conclusive.

Zero rows, multiple rows, a different row, an unavailable final observation,
or any other difference enters OUTCOME_UNKNOWN after an ambiguous COMMIT and
QUARANTINED otherwise. The operation never retries to turn zero rows into one:
the original server transaction might still become visible after the
observation.

### 6.7 Output and cleanup

Only RECOVERED renders stdout. The canonical JSON report contains:

- schema = ofarm.security-audit-store-loss-recovery-report.v1;
- outcome = RECOVERED;
- service identity;
- provisioning-spec digest;
- migration-set digest;
- system identifier;
- migration execution ID;
- event ID;
- canonical interval start;
- canonical interval end;
- canonical observed-at;
- canonical purge-after; and
- countUnknown = true.

It contains no DSN, hostname, port, username, password, release identity,
exception text, SQL, traceback, environment name, process path, or arbitrary
database value.

Expected refusals and all unexpected ordinary exceptions map to fixed bounded
stderr messages and closed exit codes. No exception text or traceback is
printed. Broken stdout, short write, encoding failure, or flush failure never
changes database state and never becomes a success exit.

The exact command exits are:

- 0 — RECOVERED and the complete success report was flushed;
- 2 — fixed input or secret presence was refused before PostgreSQL work;
- 3 — recovery was refused or the target is quarantined;
- 4 — append outcome is unknown and the target is quarantined; and
- 5 — the success report could not be completely written and the target is
  quarantined.

The corresponding stderr messages are fixed to the outcome kind and contain
no dynamic suffix. No other ordinary-exception exit is permitted.

Connections and in-memory password carriers are released on every path. Python
cannot guarantee physical erasure of immutable string storage; the command
therefore makes no memory-erasure claim. It must not persist secrets to a file,
report, log, telemetry event, metric, queue, or crash artifact.

### 6.8 Retry, replay, and cleanup rule

One invocation attempts one target once. There is no supported rerun against a
target touched by a prior invocation:

- after successful creation, provision_service would report created = false;
- the recovery runner treats that as terminal refusal;
- after a successful gap, the store is non-empty and also refuses the fresh
  posture; and
- after a partial or ambiguous run, the target remains quarantined.

Recovery from a failed attempt requires an external DBA to inspect and, when
separately authorized, remove the unpublished disposable target before a new
invocation. That removal is not a method, fallback, or effect of this
operation.

## 7. Invariants and acceptance criteria

### SLR-001 — this invocation creates the replacement

RECOVERED is possible only when the exact provisioner report says this
invocation created the previously absent fixed audit database and governed
roles. An existing target is never adopted, repaired, or called recovered.

### SLR-002 — no destructive or restore authority

The production operation exposes no path that can drop, delete, truncate,
restore, import, copy, rename, repair, or replace an existing database, role,
schema, event, or history.

### SLR-003 — exact immutable rebuild

RECOVERED requires the fixed security-audit provisioning digest, authoritative
migration-set digest, previous version zero, every migration applied in order,
the exact final version, exact execution identity, and exact structural
compatibility.

### SLR-004 — verified-empty operational state

Before the append there are no operational events, quota buckets, quota
high-water rows, used overflow receipts, or access-clock observations. Static
lock and receipt slots and the migration ledger have only their exact
migration-created state.

### SLR-005 — conservative closed interval and observable nonregression

The external authority supplies the only interval start. PostgreSQL supplies
the only interval end, which is finite and strictly later. The append result
and final row must have finite observed_at greater than or equal to that end
and purge_after exactly 30 days later. No request, environment fallback,
process clock, or caller can supply the end or a known count. The append always
represents count unknown.

The repository operation detects a clock rollback between its interval-end
read and the append function's observed-at read. It does not claim to detect a
rollback before the first read on a newly created database; the external
deployment monotonic-clock premise owns that fact.

### SLR-006 — one fixed mutation

After migration, one admitted invocation calls only append_audit_gap with the
fixed audit-control authority, fixed start/end sources, event count zero, and
count-unknown true, at most once.

### SLR-007 — no publication before verified durability

The command emits no success report until a final read-only observation proves
the exact one-gap state. The deployment prerequisite keeps every producer and
maintenance route unpublished until that report is accepted.

### SLR-008 — ambiguity never causes a retry or false success

Once COMMIT is sent, no mutation is attempted again. An ambiguous commit
succeeds only if one final observation proves exactly the expected sole event;
every other result is terminal OUTCOME_UNKNOWN and quarantined.

### SLR-009 — no unrelated activity

Final success proves exactly one AUDIT_GAP and no producer, access, retention,
overflow, quota, or second-gap state. The nontransactional access-clock
sequence must remain in its exact never-called posture, including when an
access transaction advanced it and later rolled back. Any unrelated activity
refuses recovery.

### SLR-010 — fixed authority and secret separation

Only the fixed admin route may provision and observe operational state, the
fixed migrator route may migrate, the fixed audit-control route may append,
and the fixed readiness route may run the existing structural verifier. The
command never uses producer, reader, export, retention, HMAC, KMS, tenant, or
break-glass authority and never emits a secret.

### SLR-011 — bounded database work, call counts, and diagnostics

The operation has fixed connection and statement budgets, one provision call,
one migration call, two fixed admin inventory observations, one fixed final
readiness verification, one append, one commit, no loop or retry, bounded
result shapes, fixed diagnostics, and one canonical success object. It makes
no wall-clock termination claim for operating-system close or output writes;
failure or short-write paths never become success.

### SLR-012 — one trust boundary and exact paths

The pull request changes only this contract's store-loss-recovery allowlist. No
migration, provisioning authority, tenant path, provider integration,
break-glass path, or deployment activation is changed.

## 8. Production-reachable negative cases

| Invariant | Supported entry and concrete counterexample | Required result |
| --- | --- | --- |
| SLR-001 | Invoke the fixed command after a prior operator already provisioned an exact empty target. | provision report has created = false; no migration or append; QUARANTINED |
| SLR-002 | Invoke against an existing drifted target or absent database with leftover governed roles. | existing provisioner refuses; no repair, drop, or cleanup call exists |
| SLR-003 | Use a route with a partial ledger, wrong migration digest, wrong server identity, or a migration report that begins above zero. | no append and no success |
| SLR-004 | Start a fixed command seam against a created target containing one event, quota row, high-water row, used overflow receipt, or called access sequence. | fresh-state observation refuses before append |
| SLR-005 | Supply a naive, non-UTC, infinite, equal-to-end, or future loss start; separately return append observed_at earlier than the captured interval end or a wrong purge deadline. | refuse before COMMIT with no process-time fallback; pre-first-read monotonicity remains an external deployment premise |
| SLR-006 | Record every SQL call while the database returns ordinary errors before and after append. | at most one exact append call; no alternate function or second mutation |
| SLR-007 | Make the append commit acknowledge, then make final observation fail. | no stdout success and target remains quarantined |
| SLR-008 | Commit the gap but drop the acknowledgement; separately keep the original transaction unresolved while the final read sees zero rows. | exact one visible event may recover; zero or uncertainty becomes OUTCOME_UNKNOWN with no retry |
| SLR-009 | Let a producer append between observations; separately advance the access-clock sequence through the accepted access path and roll back before an AUDIT_ACCESS row remains. | final event or exact sequence check refuses recovery; no false success |
| SLR-010 | Point one DSN at the wrong session user or inject canary secrets into DSNs, passwords, and raised exceptions. | fixed refusal, no traceback or canary in output |
| SLR-011 | Expire connect/statement/lock budgets; separately make close, stdout write, or flush fail or short-write. | bounded database refusal and fixed call count; cleanup/output failure is never success; no indefinite-OS-call deadline is claimed |
| SLR-012 | Add a migration, drop helper, provider client, tenant file, workflow, or unlisted path. | mechanical path check blocks Phase B and merge |

These cases use the fixed command, runner, provisioner, migration runner, and
real PostgreSQL routes. Private-field mutation and impossible database states
are not acceptance evidence.

## 9. Proposed architecture and smallest change

### 9.1 One bound request and one runner

A new deployment/postgresql/security_audit_store_loss.py owns:

- one immutable StoreLossRecoveryRequest;
- one immutable fixed secret/route carrier;
- one StoreLossRecoveryReport;
- closed refusal and outcome-unknown error kinds;
- exact timestamp and report rendering helpers;
- the fixed state machine; and
- narrow protocols for existing provision, migrate, connect, and output seams
  used by deterministic tests.

The production constructor binds only repository-fixed functions and
specifications. Protocols are test seams, not plugin registries or caller
capability bags. There is no Any-typed authority object, mutable global
registry, callback selected from configuration, or optional action.

### 9.2 One fixed command

A new deployment/postgresql/run_security_audit_store_loss.py:

- accepts only --loss-start, --release-identity, and --execution-id;
- loads the existing fixed admin, migrator, control, and readiness DSN
  environment names;
- loads one fixed environment name for each login password required by
  SECURITY_AUDIT_PROVISIONING_SPEC;
- rejects missing values before database work;
- invokes the runner once;
- prints only the canonical success report; and
- maps every failure to closed bounded exit behavior.

No password or DSN may be accepted as a positional argument or printed in help,
diagnostics, or output. Unknown command options are rejected by the fixed
parser.

### 9.3 Existing authorities remain owners

The new module composes, but does not copy or weaken:

- provisioning.py for target creation and exact role/database posture;
- migration_runner.py and migration_sets.py for schema authority;
- readiness.py for the final exact structural-compatibility observation;
- the accepted migration's append_audit_gap for gap contents and retention;
  and
- PostgreSQL for session identity, clock, transaction, and durability.

The runner adds only the missing cross-step admission state machine and fixed
fresh/final observations. It does not introduce a second provisioner,
migrator, append function, or structural verifier.

### 9.4 Why this is the minimum coherent solution

Calling the existing tools manually is insufficient because no durable fact
binds their separate reports to one unpublished target and one append attempt.
Allowing rerun would require an idempotent recovery identity in a forward
migration or an external durable receipt authority. Neither is needed when a
failed fresh target can remain quarantined.

A new migration, signed declaration, recovery ledger, generic orchestrator,
backup design, crash detector, or publication controller would add independent
authority without improving this slice's proof. One one-shot state machine
around the accepted primitives is sufficient.

## 10. Elegance audit

- **Provisioning sources of truth:** one checked-in audit provisioning spec.
- **Migration sources of truth:** one authoritative audit migration set.
- **Loss-start sources of truth:** one external declaration value.
- **Interval-end sources of truth:** one replacement PostgreSQL clock read.
- **Gap mutation points:** one existing append_audit_gap call.
- **Final-state authorities:** one fixed read-only database observation.
- **Publication authorities introduced:** none.
- **Destructive authorities introduced:** none.
- **Persistent recovery state introduced:** none.
- **Generic selectors or registries introduced:** none.
- **Loops, schedulers, retries, or background workers introduced:** none.
- **Duplicated correlated fields:** the final observation compares the bound
  request and database-returned event identity; it creates no second mutable
  authority.
- **Compatibility surfaces:** none. Existing or partial targets refuse.
- **Deletions:** none; no production store-loss operation exists to replace.
- **Clean rewrite assessment:** a new small module is clearer than adding
  store-loss branches to provisioning, migration, live-process gap, runtime,
  or readiness modules. Those owners remain unchanged.

The deliberate cost is availability: any non-success can require external
cleanup of an unpublished target. That is smaller and safer than a recovery
receipt migration or retry protocol for a pre-deployment V1 service.

## 11. Pull request and approval boundary

### 11.1 Exact technical path allowlist

The final implementation may change only:

1. docs/rfcs/OFARM_Security_Audit_Store_Loss_Recovery_RFC_v0_1.md
2. deployment/postgresql/security_audit_store_loss.py
3. deployment/postgresql/run_security_audit_store_loss.py
4. deployment/postgresql/README.md
5. kernel/tests/test_security_audit_store_loss.py
6. kernel/tests/test_postgresql_audit_migration.py
7. conformance/rewrite_architecture_check.py
8. conformance/review_baseline_test_inventory.json

The Phase A review head changes only path 1. Phase B may use a strict subset of
the remaining paths. The inventory changes only if focused tests add collected
nodes.

### 11.2 Explicitly unchanged paths and authorities

Every unlisted path is immutable, especially:

- security_audit/migrations/**;
- deployment/postgresql/provisioning.py, provisioning_specs.py,
  migration_runner.py, migration_sets.py, readiness.py, and audit_contract.py;
- all kernel production runtime, audit client, live-gap, health, HMAC,
  authentication, request-router, binder, tenant, and API modules;
- every tenant migration, role, database, credential, and repository;
- HMAC/KMS, overflow, reader, export, retention, break-glass, provider
  evidence, observer-root, and temporary-login modules;
- docs/adr/**, reference/**, workflows, package dependencies, and issue #176.

No accepted numbered migration may be edited. A demonstrated need for an
idempotent recovery identity or new database function requires a new decision
and forward migration, not an amendment hidden in this pull request.

### 11.3 Dependencies

- Reviewed base bdf636d155e45ecbf4d9ac828e232bbcf91e1d59.
- Issues #169, #170, #172, #173, and #174 are closed.
- Existing merged issue #192 slices provide isolated audit provisioning,
  migration, append, health, live-gap, overflow, reader, export, retention,
  HMAC, and runtime foundations.
- The current main tree already contains the immutable append_audit_gap
  function and the test-only empty-recreate demonstration.
- No open or stacked pull request is a prerequisite.

Provider-evidence draft PR #323, observer-root evidence, and any follow-up to
PR #322 do not affect this local PostgreSQL recovery boundary.

### 11.4 Reviewer non-requirements

Reviewers must not require this pull request to:

- detect or destroy the old service;
- implement cleanup of a failed replacement;
- add backup, replica, WAL, snapshot, CDC, restore, or history import;
- recover a tenant database;
- add a persistent recovery receipt, signed loss declaration, generic
  orchestration framework, deployment controller, or producer-publication
  mechanism;
- make a failed target reusable;
- retry migration or a gap append;
- implement process-crash witnessing when the store survives;
- change live health/readiness thresholds or route output;
- add overflow, HMAC, reader, export, retention, break-glass, IAM, KMS, or
  provider-evidence work;
- add final all-slice hostile closure evidence unrelated to store loss;
- deploy, operate, release, close issue #192, or claim production readiness.

Those are separate trust boundaries, external deployment prerequisites, or
later evidence. They cannot be appended merely to clear this decision.

### 11.5 Follow-ups

Issue #192 continues to own:

- independently witnessed process-crash intervals when the store itself
  survives;
- dual-approved, time-bounded break-glass and temporary-login closure;
- any remaining real-ASGI/PostgreSQL hostile closure evidence; and
- final parent-issue closure audit.

No new issue is required merely to duplicate the parent acceptance criteria.

### 11.6 Stop and reapproval conditions

Stop and require a new decision version before implementation or merge if work
would:

- add destructive cleanup, restore, copy, history import, backup, replica,
  snapshot, WAL, or CDC authority;
- adopt or repair an existing target or allow created other than true;
- permit migration from a nonzero version or accept a migration no-op;
- add a caller-selected database, role, migration, function, event kind,
  component, producer, interval end, count, retry, timeout, or action;
- replace the external conservative start or PostgreSQL end authority;
- remove the external monotonic-clock premise, permit observed_at before the
  captured interval end, or weaken the exact purge-deadline comparison;
- append a known count or anything other than one COUNT_UNKNOWN gap;
- retry after any append attempt or treat zero rows after ambiguity as safe to
  retry;
- add a persistent receipt, recovery registry, spool, queue, scheduler,
  background worker, or generic plugin seam;
- publish producer routes, change runtime readiness, distribute credentials,
  or authorize deployment;
- omit the final never-called access-clock sequence check;
- change provisioning, migration, structural-verification, or accepted
  migration code;
- add another trust boundary or any path outside the allowlist;
- name a different draft pull request;
- materially change a permitted effect, non-effect, authority, invariant,
  terminal state, or irreversible behavior; or
- authorize production operation, release, issue closure, or a security
  waiver.

Meaning-preserving wording, fixed diagnostic wording, test clarity,
architecture-budget registration, and mechanical inventory regeneration
inside the allowlist do not require a new version.

## 12. Provisional design record

The one-shot repository operation is not provisional. Its create-in-this-run
proof, exact migration-from-zero rule, unknown-count interval, one-append
maximum, final observation, no-retry behavior, and quarantine outcome remain
valid in a deployed composition.

The deployment composition is provisional and unauthorized:

- AI-assisted approval may authorize repository implementation only in the
  named draft pull request;
- an independently controlled system must declare loss, authorize any old
  target removal, inject fresh credentials, quarantine the new routes, and
  accept the success report before publication;
- no such deployment system or production invocation is created here;
- that system must prove the replacement PostgreSQL clock remains
  non-regressing throughout the recovery operation; and
- before deployment, AI-attested task approval must be replaced by an
  independently human-controlled and independently verifiable approval or
  signing system.

Evidence requiring redesign includes inability to keep replacement
credentials unpublished, a requirement to recover without discarding failed
fresh targets, a requirement to preserve audit history, a provider where
provision_service cannot prove same-invocation creation, or a requirement to
reconcile ambiguous commits without a conclusive fresh-store observation.

The likely upgrade path would be a separately approved external recovery
receipt authority or forward migration carrying an idempotent recovery
identity. Neither is justified for the accepted V1 no-restore posture.

## 13. Traceability and verification

| ID | Owning implementation | Negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| SLR-001 | recovery runner plus existing provision_service | exact pre-existing target | created = true from same call | focused seam test and live PostgreSQL rerun refusal |
| SLR-002 | fixed protocol surface and CLI | drifted/partial target; method inventory | no destructive method or SQL | architecture check and source review |
| SLR-003 | existing migration loader/runner plus report validator | nonzero, no-op, partial, wrong digest/identity | complete from-zero report | seam tests plus live migration |
| SLR-004 | fixed fresh-state query | each dynamic table/receipt/sequence dirty in turn | exact migration-created inventory | live PostgreSQL parametrized state tests |
| SLR-005 | request validator, control clock query, append-result validator, and final verifier | malformed/future/equal times; observed_at before interval_end; wrong purge deadline | external start, database end, observable nonregression, unknown count | deterministic time tests and live SQL capture |
| SLR-006 | gap transaction state machine | exceptions at every statement/commit phase | one exact function call maximum | call-recording seam and live event assertion |
| SLR-007 | final verifier and CLI renderer | final read unavailable after acknowledged commit | no output before exact one-gap proof | subprocess output and live publication-gate documentation test |
| SLR-008 | commit phase plus one final observation | lost acknowledgement with zero/one/multiple rows | exact one may recover; otherwise terminal unknown | deterministic transaction seam tests |
| SLR-009 | final-state query | injected producer/retention/second-gap row; rolled-back access after nontransactional sequence advance | sole expected gap, unused quota state, and never-called access sequence | live PostgreSQL hostile tests |
| SLR-010 | fixed route carrier and sanitizer | wrong session user and canary secret exceptions | exact user per phase; fixed outputs | seam, subprocess, and live role tests |
| SLR-011 | fixed runner and command | database timeout expiry; cleanup/output failure and short-write faults | bounded database calls, fixed call counts, and no false success | deterministic budget and subprocess tests |
| SLR-012 | path allowlist | base-to-head path diff | only approved files | mechanical diff and conformance checks |

### 13.1 Phase A gates

Before a live decision card, the exact RFC head must pass:

~~~text
python3 conformance/ofarm_pkg_contract_check.py
python3 conformance/rewrite_architecture_check.py
git diff --check
~~~

The exact head must receive one full Phase A review against this contract.
Every demonstrated Blocker must name the violated invariant, supported entry
point, exact transition, preconditions, consequence, and minimal
counterexample.

### 13.2 Phase B focused verification

If version 1 is later approved, the smallest implementation evidence is:

1. focused unit and subprocess tests for validation, database timeout expiry,
   call budgets, state, ambiguity, sanitizer, output failures, and report
   bytes;
2. live PostgreSQL proof of same-invocation creation, exact migration from
   zero, empty-state checks, one unknown gap, old-row absence, rerun refusal,
   wrong-role refusal, rolled-back access-sequence activity, and no
   backup/replica/CDC capability;
3. the existing PostgreSQL provisioning, migration, structural, live-gap,
   runtime, and audit-contract regression suites affected by composition;
4. architecture and review-baseline inventory checks;
5. full package conformance and git diff checks; and
6. exact base-to-head path allowlist enforcement.

No destructive real-service rehearsal or production invocation is authorized
by repository tests. Test-only disposable service teardown remains test
fixture authority and must not become production code.

## 14. Open decisions and review disposition

### 14.1 Open decisions

None currently changes the proposed repository design.

Before deployment, external owners still must define:

- how a human-controlled authority records the conservative loss start;
- who authorizes destructive disposal of the lost or failed unpublished
  target;
- how replacement credentials and routes remain quarantined until success;
- how deployment proves the replacement PostgreSQL clock remains
  non-regressing throughout recovery; and
- how the success report gates route publication.

Those are explicit deployment prerequisites. They are not unresolved Phase B
implementation choices and do not authorize expansion of this pull request.

### 14.2 Review disposition

- **Blockers:** review
  https://github.com/samovers/OFARM2/pull/324#pullrequestreview-5001965255
  found two on head 575c97d38be477e9fcacc080ae200902c63668a1:
  observable clock rollback and omission of the final access-clock sequence
  check. Both are corrected in this revision; exact-head re-review remains
  required.
- **Follow-ups:** the remaining issue #192 criteria listed in section 11.5.
- **Preferences:** the same review's non-blocking timeout concern is resolved
  by narrowing SLR-011 to the executable database and failure boundaries
  rather than adding an OS watchdog.
- **Provisional posture:** repository operation not provisional; external
  deployment composition provisional and unauthorized.

### 14.3 Merge stop rule

Phase A does not authorize Phase B. After this RFC is published in its named
draft pull request and reviewed, one complete live decision card may be shown.
Only the exact later task-user approval sentence for that card may start Phase
B.

If Phase B is approved, merge only after every invariant passes, the exact path
allowlist holds, required checks pass, no demonstrated Blocker remains, the
original card and approval remain retrievable, and no later cancellation
exists. New ideas, Preferences, and non-blocking hardening become Follow-ups
and do not reopen review.
