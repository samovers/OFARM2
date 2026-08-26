# OFARM Security Audit Surviving-Store Process-Crash Reconciliation RFC v0.1

Status: **Phase A proposed; Phase B not authorized**

- Decision: `ISSUE192-SECURITY-AUDIT-PROCESS-CRASH-RECONCILIATION-001`
- Version: `1`
- Issue: [#192](https://github.com/samovers/OFARM2/issues/192)
- Base: `775e6fde6256f9c87a6e13dd5610d753115b7eaf`
- Draft pull request: [#338](https://github.com/samovers/OFARM2/pull/338)
- Primary trust boundary: one operator-triggered, independently witnessed,
  unknown-count process-crash interval recorded in the surviving security-audit
  PostgreSQL store
- Phase A path: this RFC only
- Phase B status: not authorized by this RFC, a generic `go`, review success,
  CI success, or GitHub activity

## 1. Problem and goal

The production security-audit runtime keeps live delivery-gap state in one
process-local `SecurityAuditGapController`. That accepted design can record and
close bounded failures while the same process remains alive. It intentionally
does not persist controller state across `BaseException`, forced termination,
process death, host loss, or restart. A fresh runtime obtains a new database
anchor and makes no claim about the prior interval.

That non-claim is correct, but issue #192 also requires hostile process-crash
evidence. When the audit PostgreSQL store survives but the producing process
does not, the repository has no supported operation that can turn an
independently witnessed conservative crash start into one durable
`AUDIT_GAP` with `COUNT_UNKNOWN`. Operators would otherwise have to improvise
SQL, use a caller-selected count or end time, retry after an ambiguous commit,
or falsely treat restart as reconciliation.

The store-loss recovery operation does not solve this case. It is restricted
to a provably fresh empty replacement store and refuses an existing surviving
store. The live-gap controller also does not solve it because the lost process
state is deliberately unrecoverable.

This decision establishes one fixed, one-shot operator operation for the
surviving-store case. The operation:

1. accepts one canonical UTC interval-start value supplied by an independent
   crash witness;
2. obtains only the already provisioned audit-control DSN from its fixed secret
   environment;
3. uses one bounded transaction under the exact
   `ofarm_security_audit_control_login` session;
4. pins and verifies the transaction, timeout, durability, database, role, and
   supported-primary posture before mutation;
5. obtains the interval end from `clock_timestamp()` on that same connection;
6. calls only the existing immutable
   `ofarm_security.append_audit_gap(start, database_end, 0, true)` once;
7. accepts success only after explicit commit acknowledgement;
8. emits one fixed, non-secret report after commit; and
9. exposes closed invalid, refused, outcome-unknown, and reporting-failed
   command outcomes without dependency detail.

The operation does not detect a crash. It does not prove the external witness
or choose the interval start. Deployment composition must provide an
independently governed conservative witness. Without that prerequisite, the
operation is unavailable and no process-crash completeness claim may be made.

## 2. Learning value

This slice proves that the accepted live-process gap boundary and the accepted
no-restore V1 store posture have a coherent surviving-store handoff. A process
death can be recorded conservatively without persisting request data, adding a
spool, changing readiness, creating a crash detector, or changing the audit
schema.

It reduces the demonstrated risk that restart erases known evidence
uncertainty or that an operator invents a count, end time, SQL path, retry, or
alternate evidence store. It also establishes the exact crash and ambiguity
semantics required before the final real-ASGI/PostgreSQL cross-slice evidence
can be completed.

## 3. Non-goals

This decision does not change or add:

- automatic crash detection, PID or process identity tracking, a lease,
  heartbeat, timer, scheduler, watchdog, host agent, orchestrator, signal
  handler, shutdown hook, or background worker;
- persistent controller state, a file, spool, queue, broker, cache, log,
  metric, trace, crash report, replica, backup, WAL consumer, or CDC path;
- a numbered migration, relation, function, trigger, type, role, grant,
  provisioning specification, structural contract, retention rule, or event
  shape;
- a wrapper or replacement for `append_audit_gap`;
- a known event count, inferred count, caller-selected interval end, retry
  count, event kind, producer, component, SQL function, transaction mode, or
  database name;
- producer publication, runtime startup, ASGI routes, readiness or health
  semantics, authentication, principal resolution, tenant binding, tenant
  UnitOfWork, or tenant storage;
- store-loss recreation, store destruction, repair, restore, clone admission,
  failover, backup, replica, or multi-store selection;
- overflow closure, HMAC custody or retirement, reader, retention, export,
  break-glass, temporary LOGIN, output custody, or source-capability governance;
- proof that an external interval start is truthful, complete, independently
  witnessed, or conservative;
- production clock certification, route custody, secret distribution,
  deployment activation, production traffic, release, current/default
  promotion, production readiness, certification, current compliance, issue
  #192 closure, or a security waiver.

A process death in which the audit store is also lost remains owned by the
merged store-loss operation. A process that remains alive is owned by the
merged live-gap controller. Final cross-slice hostile evidence follows this
operation and must not be appended to its implementation merely to close the
parent issue.

## 4. Trust model

### 4.1 Protected assets

- honest disclosure that an unknown number of pre-tenant events may be absent;
- denial remaining in force regardless of audit-operation failure;
- the surviving audit store's event history and 30-day logical purge posture;
- the audit-control credential and DSN;
- absence of tenant, Party, farm, actor, issuer, subject, role, request, route,
  credential, token, secret, exception, and free-text data from the gap event;
- one-shot mutation and no duplicate retry after ambiguity;
- the distinction between external crash-witness evidence and database-owned
  interval-end/commit evidence.

### 4.2 Trusted components and inputs

- an external operations authority supplies one independently witnessed
  conservative lower bound for the uncertainty interval;
- deployment secret custody supplies the exact surviving-store audit-control
  DSN through one fixed environment name;
- PostgreSQL authentication and `session_user` identify the existing
  audit-control LOGIN;
- the selected PostgreSQL primary owns `clock_timestamp()`, transaction commit,
  and the existing `append_audit_gap` function;
- the checked-in supported PostgreSQL version policy and fixed audit database
  name own local admission expectations;
- the command module owns parsing, fixed SQL, fixed connection options, state
  transitions, report shape, and error translation.

The external witness is a deployment prerequisite, not a repository-generated
fact. Phase B may transport its canonical timestamp but may not add a receipt,
signature, approver, public key, witness registry, or self-attestation scheme.

### 4.3 Untrusted actors and inputs

- command-line bytes, argument order, duplicates, omissions, extra arguments,
  malformed timestamps, Unicode alternatives, and ambient environment values;
- DSN query parameters that attempt to weaken timeouts, durability, time zone,
  date style, database selection, or transaction posture;
- dependency exceptions, PostgreSQL error text, server notices, and output-sink
  failures;
- ordinary application, producer, reader, retention, export, readiness,
  tenant, and migration credentials;
- process interruption at any instruction, including before, during, and after
  commit;
- a wrong database, standby, wrong LOGIN, inherited role, altered
  `current_user`, malformed SQL result, or unsupported PostgreSQL version.

### 4.4 Explicitly excluded attacker capabilities

The following remain outside this repository boundary:

- compromise of the external witness authority or deliberate supply of a
  falsely late interval start;
- compromise of the audit-control credential, database owner, superuser,
  migrator, PostgreSQL server, operating system, hypervisor, or deployment
  secret store;
- arbitrary in-process mutation, debugger access, local source substitution,
  compromised Python or PostgreSQL dependencies, filesystem mutation, or
  operator compromise;
- an admitted backup, replica, promoted clone, restored store, or multiple
  eligible audit stores.

If any excluded capability becomes required, this decision stops for a new
authority design rather than claiming that the fixed command covers it.

## 5. Authority map

| Decision | Sole authority | Forbidden substitute |
| --- | --- | --- |
| A crash interval must be recorded | Independently governed external operations witness | restart, runtime readiness, absence of traffic, a Python exception, command invocation itself |
| Interval start | Canonical UTC lower bound supplied by that witness | process wall clock sampled after restart, database end time, event observation time, guessed count |
| Target route | One fixed secret environment containing the surviving-store audit-control DSN | command argument, tenant DSN, readiness DSN, admin DSN, DSN assembled from parts |
| Database identity | Fixed expected audit database name observed on the effectful connection | DSN text alone, caller database name, search path, database OID alone |
| Mutation authority | Exact `session_user = ofarm_security_audit_control_login` and existing `append_audit_gap` grant | `current_user` alone, `SET ROLE`, admin, owner, migrator, producer, reader, retention or export role |
| Transaction posture | Code-pinned read-committed writable transaction with `synchronous_commit=on` on the effectful connection | role default alone, caller DSN options, autocommit, read-only transaction |
| Interval end | Fresh `clock_timestamp()` on the same effectful transaction | caller time, Python time, witness time, a previous query or another connection |
| Event contents | Existing immutable `append_audit_gap(start, end, 0, true)` function and database constraints | direct DML, another function, caller producer/component/count/event kind |
| Mutation success | Explicit commit acknowledgement | returned function row, connection close, report rendering, later inference |
| Ambiguity | Local transaction phase when commit does not acknowledge | automatic retry, event-table read with another role, claimed rollback |
| Positive report | Fixed command-owned report constructed only after acknowledged commit | stdout presence, database notice, dependency object, precommit result |

No legacy crash operation, alias, fallback, duplicate state, or alternate write
path exists. Phase B introduces one operation and no compatibility surface.

## 6. State machine and ordering

### 6.1 States

The library operation has these states:

```text
UNVALIDATED
  -> ADMITTED
  -> CONNECTED
  -> PREPARED
  -> APPEND_IN_FLIGHT
  -> COMMIT_IN_FLIGHT
  -> COMMITTED
  -> REPORTED
```

Terminal refusal states are:

```text
INVALID_INPUT       before connection
REFUSED             known before commit begins
OUTCOME_UNKNOWN     commit began without acknowledgement
REPORTING_FAILED    commit acknowledged but report output failed
INTERRUPTED         process ended; no retry or success inference
```

`COMMITTED` is irreversible. Cleanup or output failure after it cannot restore
an earlier state, roll back the event, authorize a retry, or change success
into a claim that no event exists.

### 6.2 Validation before effects

The command accepts exactly one ordered argument pair:

```text
--interval-start YYYY-MM-DDTHH:MM:SS.ffffffZ
```

It rejects missing, duplicate, reordered, additional, non-string, noncanonical,
naive, infinite, or non-UTC values before reading the secret environment or
opening PostgreSQL. The environment supplies exactly one nonempty parseable DSN
under `OFARM_SECURITY_AUDIT_CONTROL_PG_DSN`.

The connection factory overrides conflicting DSN options with fixed bounded
values for connect timeout, statement timeout, lock timeout, `TimeZone=UTC`,
`DateStyle=ISO,MDY`, and `synchronous_commit=on`. It opens with autocommit off
and explicitly prepares a read-committed transaction.

Before calling the append function, one fixed admission query on that same
connection verifies:

- exact `session_user` and `current_user` are the audit-control LOGIN;
- exact current database is the provisioned audit database;
- server version is the checked-in supported version;
- the server is not in recovery;
- transaction read-only is off;
- transaction isolation is read committed; and
- effective `synchronous_commit` is on.

The operation then obtains one fresh database clock. If the value is malformed,
non-finite, naive, or not strictly later than the supplied interval start, it
refuses before the append call.

### 6.3 Effect and acknowledgement

The exact mutation is:

```sql
SELECT *
FROM ofarm_security.append_audit_gap(%s, %s, 0, true)
```

It is invoked once with the validated witness start and same-transaction
database end. The operation validates one exact nonnil event UUID, aware
`observed_at`, and exact 30-day `purge_after` relationship before commit.

Any known failure before commit begins rolls back best-effort and returns only
the fixed refused outcome. Once commit begins, any exception produces only the
fixed outcome-unknown result; it is never automatically retried. A returned
commit acknowledgement transitions irreversibly to `COMMITTED`.

Connection close is best-effort. A close failure after acknowledged commit does
not revoke the committed result or expose dependency detail. The fixed report
contains only schema identity, event UUID, interval start, interval end,
observed time, and purge time. It is rendered to canonical UTF-8 JSON with one
trailing newline.

### 6.4 Interruption and retry posture

Forced termination before commit may leave no event; termination during or
after commit may leave one event. The dead process cannot report which. A
missing command result is therefore `INTERRUPTED`, not refusal and not success.

There is no operation identity in the accepted event shape and no safe retry
deduplication authority. Deployment must quarantine every interrupted or
outcome-unknown invocation and must not rerun it. Determining whether a later,
separately witnessed interval should be recorded is a new external decision,
not a retry of this operation.

## 7. Invariants and acceptance criteria

### `PCR-001` — one independently witnessed input

The production command accepts exactly one canonical UTC interval start. It
does not accept a count, interval end, producer, component, event kind,
database, SQL, retry, operation mode, or arbitrary evidence field.

### `PCR-002` — exact surviving-store control authority

Every mutation uses one connection from the fixed audit-control secret route.
The operation verifies the exact LOGIN, fixed database, supported writable
primary, isolation, and durability posture on that connection before mutation.
No role assumption or alternate credential is supported.

### `PCR-003` — database-owned conservative end

The supplied witnessed start is used unchanged. The interval end is one fresh
database clock from the effectful transaction and must be strictly later. No
Python, request, restart, or caller-supplied time can narrow or select the end.

### `PCR-004` — exactly one unknown-count mutation

One admitted invocation calls only the existing `append_audit_gap` once with
`event_count=0` and `count_unknown=true`. It performs no direct DML and cannot
select another event kind, producer, component, count, retention, or function.

### `PCR-005` — commit acknowledgement is the only success

A valid function result is not success. Only explicit commit acknowledgement
permits a positive report. Known-precommit failure refuses; commit ambiguity is
permanent outcome unknown for that invocation; neither path retries.

### `PCR-006` — interruption never manufactures certainty

Process death before, during, or after commit produces no success inference and
no retry authority. Restart does not clear or reconstruct the prior attempt.

### `PCR-007` — fixed non-sensitive observability

The event, report, stdout, stderr, exception surface, and ordinary formatted
diagnostics contain no DSN, password, dependency detail, tenant, Party, farm,
actor, issuer, subject, role, request, route, token, credential, secret,
free text, or attacker-controlled identity. Fixed stderr never includes caught
exception text.

### `PCR-008` — bounded one-shot cost

Parsing, connection count, SQL count, transaction count, cryptographic work,
report size, and cleanup are fixed and bounded. There is no loop, retry, sleep,
poll, scheduler, background task, or unbounded collection.

### `PCR-009` — audit degradation never authorizes

Invalid input, wrong authority, unavailable PostgreSQL, refusal, ambiguity,
interruption, cleanup failure, and reporting failure never authenticate,
resolve a principal, enter a tenant, start tenant work, publish a route, alter
readiness, or fall back to another evidence sink.

### `PCR-010` — accepted schema and authorities remain unchanged

All accepted migrations, roles, grants, functions, event shapes, readiness
semantics, runtime composition, and retention behavior remain byte-identical.
No alternate evidence store or crash state is added.

### `PCR-011` — honest external-witness non-claim

The success report proves only that the supplied interval was appended with an
unknown count to the admitted surviving store. It does not claim that the
repository observed the crash, authenticated the witness, proved the earliest
possible start, detected every lost event, or made production composition safe.

## 8. Production-reachable negative cases

| Invariant | Supported entry and counterexample | Required result |
| --- | --- | --- |
| `PCR-001` | Invoke the fixed command with a missing, duplicate, reordered, extra, noncanonical, offset, naive, infinite, or Unicode-lookalike timestamp; add count/end/database/SQL arguments. | Exit invalid before secret read or connection; no mutation. |
| `PCR-002` | Point the fixed secret route at a reader, producer, retention, readiness, migrator, owner-like test role, wrong database, standby, unsupported server, read-only transaction, or conflicting DSN options. | Code-owned options win; exact admission refuses before append. |
| `PCR-003` | Supply a start equal to or later than the database clock, or return malformed/naive/infinite clock data. | Refuse and roll back before the function call. |
| `PCR-004` | Inspect the public request, SQL inventory, and live database result; attempt to select a known count, another kind, direct insert, producer, component, or function. | No such surface exists; exactly one `AUDIT_GAP` has count unknown and no protected fields. |
| `PCR-005` | Return a valid append row then raise before commit; raise from commit; return from commit then fail close. | Precommit failure rolls back and refuses; commit failure is outcome unknown with zero retries; post-ack close failure preserves one committed success. |
| `PCR-006` | Start the real command against live PostgreSQL, block the append transaction with a privileged test fixture, terminate the process, and release the lock; separately make commit raise through the runner's public connection-factory dependency. | No positive report or retry occurs; the killed precommit transaction leaves no event; the commit exception is outcome unknown; restart makes no claim about either interrupted attempt. |
| `PCR-007` | Put canaries in the DSN password, PostgreSQL error, dependency exception, interval parser input, output failure, and environment; capture stdout, stderr, exception formatting, ordinary logs, warnings, and test telemetry. | Only fixed output appears; no canary crosses an authorized sink. |
| `PCR-008` | Count connections, statements, append calls, commits, rollbacks, closes, output writes, and child-process duration under success and every failure phase. | Each count stays within its fixed contract; no retry, poll, sleep, or growth appears. |
| `PCR-009` | Make every dependency fail while presenting a token, tenant-shaped value, route value, and alternate sink fixture. | No authorization, tenant, route publication, readiness change, or fallback call occurs. |
| `PCR-010` | Compare the final path set, migrations, audit contract, provisioning graph, runtime imports, and role/function catalogs with the base. | Only approved operation, command, tests, docs, and mechanical conformance paths differ; accepted authorities are identical. |
| `PCR-011` | Read the success report and documentation after supplying an intentionally earlier conservative start. | The exact supplied start is reported, but no text claims repository crash detection, witness authentication, exact loss count, deployment eligibility, or completeness beyond the appended interval. |

Tests may provide controlled connections, output sinks, and barriers through
public constructors. Live interruption evidence must enter through the actual
command process and real PostgreSQL; it must not mutate private state and call
that production evidence.

## 9. Proposed architecture and smallest change

### 9.1 Types and ownership

One new `deployment/postgresql/security_audit_process_crash.py` module owns:

- immutable `ProcessCrashReconciliationRequest` with one interval start;
- immutable `ProcessCrashReconciliationSecrets` with one control DSN;
- immutable `ProcessCrashReconciliationReport` with only fixed safe fields;
- fixed invalid, refused, and outcome-unknown exceptions;
- one `SecurityAuditProcessCrashReconciliationRunner`;
- one private transaction phase enum;
- fixed admission, clock, and append SQL; and
- canonical report rendering.

One new `deployment/postgresql/run_security_audit_process_crash.py` module owns:

- the sole supported CLI argument and environment names;
- canonical parsing;
- closed exit codes and fixed stderr;
- one report write and flush; and
- construction of the fixed runner.

One focused test module owns deterministic unit, live PostgreSQL, subprocess,
forced-termination, canary, bounded-call, and architecture evidence. Existing
README files may document the command and its non-deployable external witness
prerequisite. Mechanical conformance files may inventory the test and reject
paths or imports outside this contract.

### 9.2 Data flow

```text
independent external crash witness
  -> canonical --interval-start
  -> fixed command parser
  -> fixed secret audit-control DSN
  -> one bounded connection and transaction
  -> exact role/database/primary/version/isolation/durability admission
  -> same-transaction database clock
  -> existing append_audit_gap(start, end, 0, true), once
  -> validate fixed row
  -> explicit commit
       -> acknowledged: fixed safe report
       -> exception: fixed outcome unknown, no retry
  -> output
       -> complete: exit success
       -> failed: fixed reporting failure, no retry
```

### 9.3 Why this is the minimum coherent design

Changing the live-gap controller to persist state would add a durable process
identity, lifecycle, concurrency, and restart protocol. Automatic detection
would add deployment supervision and false-positive policy. Reusing store-loss
recovery would incorrectly require an empty replacement target. Direct
operator SQL would permit caller-selected function arguments and unsafe retry.

The existing function already owns the event shape, retention, role check, and
unknown-count rule. One new fixed operation is therefore sufficient. A separate
module avoids widening the runtime controller's public surface or importing its
private snapshot type. No migration or role change is justified.

## 10. Elegance audit

- Sources of truth: one external witness for interval start; one fixed secret
  route for target; one database transaction for authority, end time, append,
  and commit; one existing database function for event contents.
- Authoritative transition points: one append call and one commit.
- Duplicated fields: none. The report reflects committed values and creates no
  second authority.
- Compatibility surfaces: none. There is no previous crash command or request
  schema to retain.
- New abstractions: one bound request, one bound secret carrier, one bound
  report, and one runner. No framework or registry is introduced.
- Deletion: no accepted production path can be deleted. Any implementation
  helper not required by the fixed command should be removed rather than kept
  as a generic operation surface.
- Rewrite posture: a new small module is cleaner than modifying the live-gap or
  store-loss modules because those have different state and authority models.

## 11. Pull request boundary

### 11.1 Primary boundary

The primary trust boundary is one operator-triggered, independently witnessed,
unknown-count process-crash interval recorded in the surviving security-audit
PostgreSQL store.

Tests, documentation, and mechanical conformance needed to verify this exact
operation may travel with it. No other authority or custody change may.

### 11.2 Maximum path envelope

The draft and any authorized Phase B implementation are limited to at most:

1. `docs/rfcs/OFARM_Security_Audit_Process_Crash_Reconciliation_RFC_v0_1.md`
2. `deployment/postgresql/security_audit_process_crash.py`
3. `deployment/postgresql/run_security_audit_process_crash.py`
4. `kernel/tests/test_security_audit_process_crash.py`
5. `deployment/postgresql/README.md`
6. `kernel/README.md`
7. `conformance/rewrite_architecture_check.py`
8. `conformance/review_baseline_test_inventory.json`

Phase A changes only path 1. The technical Phase B allowlist may narrow this
envelope but may not add a path. No cross-boundary exception is proposed.

### 11.3 Dependencies

- Merged live-gap reconciliation provides the accepted live-process boundary
  and restart non-claim.
- Merged store-loss recovery owns the distinct lost-store case.
- Merged temporary export lifecycle does not participate in this operation.
- Existing migration 1 provides immutable `append_audit_gap` and the exact
  audit-control role and grant.
- No open or stacked pull request is a prerequisite.

### 11.4 Reviewer non-requirements

Reviewers must not require this pull request to:

- detect crashes automatically or persist process identity/state;
- add a lease, heartbeat, PID, timer, scheduler, watchdog, host agent,
  orchestrator, signal hook, background worker, or shutdown protocol;
- authenticate or sign the external witness;
- change a migration, role, grant, function, event shape, structural contract,
  readiness threshold, runtime graph, or ASGI route;
- implement store loss, backup, restore, replication, failover, clone support,
  HMAC, overflow, reader, retention, export, output custody, or source policy;
- add final all-slice ASGI/PostgreSQL evidence or close issue #192;
- deploy, release, operate, authorize production access, or claim production
  readiness, certification, or current compliance.

Those are separate trust boundaries, external prerequisites, or later evidence.

### 11.5 Follow-ups

Issue #192 continues to own:

- final real-ASGI/two-PostgreSQL hostile cross-slice closure evidence; and
- final closure audit.

Already traceable separate Follow-ups remain:

- protected output custody and delivery;
- production clock, timer, route, and provider evidence;
- issue #334 package-initializer reachability residue; and
- complete execution-root and source-capability governance.

No new issue is required merely to duplicate those recorded items.

### 11.6 Stop and reapproval conditions

Stop for decision version 2 if implementation or review would:

- add automatic detection, persistent state, another store, another credential,
  another connection authority, or an external witness receipt;
- change the meaning or source of the interval start or end;
- add idempotent retry, a persistent operation identity, a known count, or a
  caller-selected SQL/function/event field;
- change any migration, role, grant, function, readiness, runtime, ASGI,
  authentication, tenant, deployment, output, or source-governance boundary;
- add a path outside section 11.2 or name another pull request;
- authorize deployment, production use, issue closure, or a security waiver.

## 12. Provisional design record

**Not provisional** for the repository operation inside ADR 0001's V1
surviving-store, no-backup/no-replica/no-restore boundary.

External production composition remains unavailable and unauthorized until an
independently human-controlled operations system governs the crash witness,
conservative start, surviving-store route, no-retry quarantine, and command
result. This RFC does not design or simulate that authority.

Evidence that V1 must support automatic detection, multiple replicas, store
promotion, recovery retries, authenticated witness receipts, or a compromised
operator would invalidate this design. The likely upgrade would require a
separate durable process-epoch and externally governed witness protocol, not a
patch to this command.

## 13. Traceability and verification

| Invariant | Owning implementation | Negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `PCR-001` | command parser and request | malformed, duplicate, reordered, extra and lookalike inputs | no connection or secret read | focused parser tests |
| `PCR-002` | runner connection factory and admission query | wrong role/database/standby/version/options | no append call | focused connection tests plus live role matrix |
| `PCR-003` | same-transaction clock path | equal/later start and malformed clock | append absent | unit and live PostgreSQL clock cases |
| `PCR-004` | fixed append SQL | attempted count/kind/function widening | one unknown-count `AUDIT_GAP`, no protected fields | SQL inventory and live row query |
| `PCR-005` | transaction phase state machine | precommit, commit, postcommit-close failures | exact refusal/unknown/success and zero retries | deterministic connection tests |
| `PCR-006` | command process and no-retry contract | terminate a blocked real command; inject commit ambiguity through the public connection factory | no success output or automatic retry | real subprocess/PostgreSQL interruption plus deterministic commit-phase test |
| `PCR-007` | fixed errors, report and CLI sinks | canaries across parser, DSN, database, exception and output failures | no canary in authorized sinks | capture and formatting tests |
| `PCR-008` | direct runner and command | every dependency phase | fixed call-count ceilings and bounded report | deterministic call inventory |
| `PCR-009` | module imports and closed failures | token/tenant/route-shaped inputs with dependency failures | no authority or fallback calls | import and collaborator-call gates |
| `PCR-010` | path and architecture gates | migration/role/runtime/import mutation | exact approved paths only; base authorities identical | diff allowlist, contract check, architecture check |
| `PCR-011` | report schema and documentation | intentionally early conservative start | exact non-claims preserved | report golden and documentation assertions |

Required Phase B verification, if later authorized:

- focused unit tests for every state and dependency boundary;
- live PostgreSQL tests under every relevant provisioned role;
- actual subprocess/live-PostgreSQL precommit interruption and deterministic
  public-constructor commit-ambiguity evidence;
- exact one-row unknown-count event and protected-field absence checks;
- fixed canary and observability-sink checks;
- exact call-count and no-retry checks;
- existing live-gap and store-loss focused suites unchanged;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- Ruff, `git diff --check`, exact path equality, and mechanically regenerated
  canonical test inventory when required;
- one exact-head zero-Blocker content review before any expensive hosted
  baseline is monitored or diagnosed;
- one unedited exact-head baseline-admission comment after that review; and
- required hosted conformance and native-verifier results on the admitted exact
  head before an implementation approval card or merge decision.

## 14. Open decisions and review disposition

### 14.1 Open decisions

No repository design ambiguity may silently change Phase B.

Before production composition, external owners must still define:

- who independently witnesses a crash and how the conservative lower bound is
  recorded;
- how the surviving audit-control route is selected and held;
- how interrupted and outcome-unknown attempts are quarantined from retry; and
- how the result gates later runtime publication.

Those are explicit deployment prerequisites. Their absence makes production
composition unavailable; it does not authorize provider fixtures or a witness
system in this pull request.

### 14.2 Review disposition

- Blockers: exact-head Phase A content review pending.
- Follow-ups: final cross-slice hostile evidence and closure audit remain in
  issue #192; the separate recorded items in section 11.5 remain outside this
  boundary.
- Preferences: none recorded.
- Full reviews: zero at this proposed head.
- Phase B: not authorized.
- Production composition: unauthorized and non-deployable.

### 14.3 Merge stop rule

Phase A does not merge as an implementation. After the complete exact-head
contract has zero demonstrated Blockers and every required admitted hosted gate
passes, present the complete decision card naming this draft pull request and
stop for the exact task-user approval sentence.

If Phase B is later authorized, merge only when every approved invariant
passes, the exact path allowlist is preserved, exact-head review and admitted
hosted gates are green, the original card and approval remain live, no later
cancellation exists, and no demonstrated Blocker remains. New ideas,
Preferences, hypothetical deployment hardening, and separate trust boundaries
remain Follow-ups and do not reopen this decision.
