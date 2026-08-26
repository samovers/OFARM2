# OFARM Security Audit Surviving-Store Process-Crash Reconciliation RFC v0.1

Status: **Phase A correction pending exact-head review; Phase B not authorized**

- Decision: `ISSUE192-SECURITY-AUDIT-PROCESS-CRASH-RECONCILIATION-001`
- Version: `2`
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

This decision establishes one fixed operator operation for the
surviving-store case. The operation:

1. accepts one canonical UTC interval-start value retained by an independent
   process-window witness no later than the crashed process's first governed
   audit attempt after the last independently closed continuity point;
2. obtains only the complete, closed audit-control route from its fixed secret
   environment and rejects ambient libpq configuration;
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
or choose the interval start. A crash-observation timestamp alone is unsafe
because an uncommitted live-process gap may have begun earlier. Deployment
composition must therefore retain an independently governed process-window
lower bound before governed attempts begin. Without that prerequisite, the
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
- a TCP PostgreSQL route, TLS trust root, client certificate, GSS/Kerberos
  transport, service/password file, or other indirect libpq authority;
- overflow closure, HMAC custody or retirement, reader, retention, export,
  break-glass, temporary LOGIN, output custody, or source-capability governance;
- proof that an external interval start was retained before governed attempts,
  is truthful, complete, independently witnessed, or conservative;
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
- the surviving audit store's event history and accepted
  `RETENTION_SECONDS` logical purge posture;
- the audit-control credential and DSN;
- absence of tenant, Party, farm, actor, issuer, subject, role, request, route,
  credential, token, secret, exception, and free-text data from the gap event;
- at most one append attempt per invocation and no automatic retry;
- the distinction between external crash-witness evidence and database-owned
  interval-end/commit evidence.

### 4.2 Trusted components and inputs

- an external operations authority retains, before governed audit attempts,
  one independently witnessed conservative lower bound for the process window;
- deployment secret custody supplies the complete surviving-store
  audit-control conninfo through the operation-specific fixed environment name
  `OFARM_SECURITY_AUDIT_PROCESS_CRASH_CONTROL_PG_DSN`;
- the existing shared `OFARM_SECURITY_AUDIT_CONTROL_PG_DSN` and its four merged
  consumers remain untouched and are not fallback authority for this operation;
- the conninfo owns every route, authentication, and transport parameter; the
  command owns the closed key policy and reconstructs the value before libpq;
- Phase B supports only one local Unix-domain socket route with password
  authentication and SSL/GSS transport disabled; a TCP route, TLS trust store,
  client certificate, or other transport authority requires decision version
  3;
- PostgreSQL authentication and `session_user` identify the existing
  audit-control LOGIN;
- the selected PostgreSQL primary owns `clock_timestamp()`, transaction commit,
  and the existing `append_audit_gap` function;
- the checked-in supported PostgreSQL version policy and fixed audit database
  name own local admission expectations;
- the command module owns parsing, fixed SQL, fixed connection options, state
  transitions, report shape, and error translation.

The external witness is a deployment prerequisite, not a repository-generated
fact. Its lower bound must be no later than the crashed process's first governed
audit attempt after the last independently closed continuity point. A timestamp
first observed after the crash is insufficient. Phase B may transport the
canonical lower bound but may not add a receipt, signature, approver, public
key, witness registry, or self-attestation scheme.

### 4.3 Untrusted actors and inputs

- command-line bytes, argument order, duplicates, omissions, extra arguments,
  malformed timestamps, Unicode alternatives, and every ambient `PG*`
  environment value, including `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`,
  `PGSERVICE`, and `PGSERVICEFILE`;
- conninfo parameters that attempt to add a host, address, service, password
  file, client certificate, TLS file, options string, application name,
  target-session rule, or to weaken timeouts, durability, time zone, date
  style, database selection, authentication, or transaction posture;
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
| Interval start | Canonical UTC process-window lower bound retained by that witness no later than the first governed attempt after the last independently closed continuity point | crash-observation time alone, process wall clock sampled after restart, database end time, event observation time, guessed count |
| Target route and authentication | The operation-specific `OFARM_SECURITY_AUDIT_PROCESS_CRASH_CONTROL_PG_DSN` containing one complete, closed surviving-store audit-control conninfo | shared `OFARM_SECURITY_AUDIT_CONTROL_PG_DSN`, command argument, ambient `PG*`, service file, password file, tenant/readiness/admin DSN, partial conninfo, URI conninfo, multi-host route, or DSN assembled from parts |
| Transport posture | One absolute Unix-domain socket directory with exact `sslmode=disable`, selected in the protected conninfo | TCP, caller default, host list, `hostaddr`, TLS, client certificate/key, CA/CRL file, GSS encryption, or indirect libpq file |
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
  -> INPUT_VALIDATED
  -> CONNECTED
  -> DATABASE_ADMITTED
  -> APPEND_IN_FLIGHT
  -> COMMIT_IN_FLIGHT
  -> COMMITTED
  -> REPORTED
```

Terminal refusal states are:

```text
INVALID_INPUT       before connection
REFUSED             known failure or proven rollback before COMMIT processing
OUTCOME_UNKNOWN     commit invocation began without acknowledgement
REPORTING_FAILED    commit acknowledged but report protocol incomplete
INTERRUPTED         catchable precommit interruption; no success inference
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
opening PostgreSQL. The environment must then contain exactly one nonempty
keyword conninfo under
`OFARM_SECURITY_AUDIT_PROCESS_CRASH_CONTROL_PG_DSN`. This operation-specific
name deliberately does not change the grammar or value of the accepted shared
`OFARM_SECURITY_AUDIT_CONTROL_PG_DSN` consumed by HMAC retirement, overflow,
bounded query, and store-loss operations. Both names may refer to the same
provisioned audit-control LOGIN, but only the process-crash name is an input to
this command. URI conninfo, duplicate keys, and every ambient environment key
whose name starts with `PG` are invalid before connection.

The adapter checks the stored Python string lengths before scanning either
value. The interval-start argument must have exactly 27 code points and then
encode as exactly 27 ASCII bytes. The conninfo may have at most 4096 code
points, then must encode as at most 4096 UTF-8 bytes, including its directly
supplied password, without surrogate or replacement characters. Oversize or
unencodable input is invalid before regex or conninfo parsing. Process startup
and operating-system argv/environment materialization remain external; these
ceilings bound repository-owned parsing after entry and do not claim a hard
wall-clock bound over operating-system scheduling or I/O.

The secret conninfo has a closed grammar and no defaultable authority:

- the only common input keys are exactly `host`, `port`, `dbname`, `user`,
  `password`, and `sslmode`, each present once with a nonempty value;
- `host` names exactly one host and contains no comma; `port` is one decimal
  integer from 1 through 65535; `dbname` equals
  `SECURITY_AUDIT_PROVISIONING_SPEC.database_name`; and `user` equals
  `ofarm_security_audit_control_login`;
- `host` is one absolute Unix-domain socket-directory path and `sslmode` is
  exactly `disable`; TCP hosts and every TLS key are forbidden;
- `service`, `hostaddr`, `passfile`, `options`, `application_name`,
  `target_session_attrs`, `sslcert`, `sslkey`, `sslpassword`, `sslcrl`,
  `sslcrldir`, GSS/Kerberos keys, and every other key are forbidden; and
- no home-directory, service, password, client-certificate, CA, CRL, OpenSSL,
  or other libpq file participates: the password is present directly, no
  service is named, and SSL is disabled. Adding any file-backed or network
  transport authority requires decision version 3.

After parsing and validating the secret, the command reconstructs a new
conninfo from only those accepted values plus code-owned direct parameters. It
does not pass the original text to the connection factory. The code-owned
parameters set exact
`application_name=ofarm_security_audit_process_crash_reconciliation`,
`target_session_attrs=read-write`, `load_balance_hosts=disable`,
`gssencmode=disable`, and `require_auth=scram-sha-256`, plus these exact bounds
and options:

```text
connect_timeout=5 seconds per single libpq address attempt
statement_timeout=2000 milliseconds
lock_timeout=250 milliseconds
idle_in_transaction_session_timeout=10000 milliseconds
transaction_timeout=15000 milliseconds
TimeZone=UTC
DateStyle=ISO,MDY
synchronous_commit=on
```

`connect_timeout` is a client-supplied connection parameter and cannot be
verified by a server query. Its exact value, the single-host rule, and the
sanitized reconstructed conninfo are verified at the public connection-
factory seam. Before parsing or connecting, that seam also requires
`psycopg.pq.version() >= 160000`, the minimum libpq version that owns
`require_auth` and `load_balance_hosts`; an older or unavailable client version
is invalid configuration and opens no connection. The remaining values are
supplied in one code-owned `options` string. The connection opens with
autocommit off and explicitly prepares a read-committed writable transaction.

Before calling the append function, one fixed admission query on that same
connection verifies:

- exact `session_user` and `current_user` are the audit-control LOGIN;
- exact current database is the provisioned audit database;
- server version number and full version string equal
  `SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM` and
  `SUPPORTED_POSTGRESQL_SERVER_VERSION` from
  `deployment.postgresql.version_policy`;
- the server is not in recovery;
- transaction read-only is off;
- transaction isolation is read committed;
- effective `statement_timeout` is `2s`;
- effective `lock_timeout` is `250ms`;
- effective `idle_in_transaction_session_timeout` is `10s`;
- effective `transaction_timeout` is `15s`;
- effective `TimeZone` is `UTC`;
- effective `DateStyle` is `ISO, MDY`; and
- effective `synchronous_commit` is `on`.

The exact database expectation is imported from
`SECURITY_AUDIT_PROVISIONING_SPEC.database_name`; Phase B may not duplicate its
string as a second authority. A missing, extra, malformed, or unequal
admission-row field refuses before the database clock or append. Hostile
conninfo values and hostile role/database defaults cannot override the
code-owned options; the observed admission row must still match every value.

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
`observed_at` no earlier than the interval end, and exact `purge_after -
observed_at = RETENTION_SECONDS` relationship before commit.
`RETENTION_SECONDS` is imported from
`deployment.postgresql.audit_contract`; Phase B may not duplicate the current
numeric duration as a second authority.

Any known failure before the commit-invocation boundary rolls back best-effort
and returns only the fixed refused outcome. An authenticated
`IdleInTransactionSessionTimeout` diagnostic proving server rollback before
`COMMIT` processing also refuses even if first received by the commit call.
Once the commit-invocation boundary is entered, every other exception produces
only the fixed outcome-unknown result; it is never automatically retried. A
returned commit acknowledgement transitions irreversibly to `COMMITTED`.

An ordinary connection-close failure after acknowledged commit is best-effort
and does not revoke the committed result or expose dependency detail. A
catchable process interruption after commit acknowledgement is governed by
section 6.4 and cannot produce a success report unless report output later
completes.

#### 6.3.1 Exact report wire contract

The report schema identity is exactly:

```text
ofarm.security-audit-process-crash-reconciliation-report.v1
```

The complete report is one JSON object with exactly these keys in alphabetical
order, matching the merged store-loss renderer:

1. `eventId`, a canonical lowercase nonzero UUID;
2. `intervalEnd`, the validated database end;
3. `intervalStart`, the exact accepted witness start;
4. `observedAt`, the validated database observation;
5. `purgeAfter`, the validated database purge time; and
6. `schema`, fixed to the schema identity above.

Every timestamp is normalized to UTC and encoded exactly as
`YYYY-MM-DDTHH:MM:SS.ffffffZ`. Every JSON value is a string. Rendering uses
ASCII-only JSON encoded as UTF-8 with `sort_keys=True`, escapes according to the
JSON standard with non-ASCII escaped, uses `,` and `:` as separators with no
spaces, and adds exactly one final LF byte. It emits no BOM, CR, indentation,
or other whitespace. Every admitted value has fixed width and therefore
renders exactly 298 bytes including LF. A separate 512-byte implementation
ceiling remains a fail-closed fault guard: exceeding it is not a
production-reachable input case, but is reporting failure after an acknowledged
commit and never success. The runner constructs and validates all bytes in
memory before stdout is touched.

### 6.4 Interruption and retry posture

The production runner catches `KeyboardInterrupt`, `SystemExit`, and every
other catchable direct `BaseException` during connection, SQL, commit, cleanup,
and report construction. It suppresses the original value and traceback,
performs only the phase-allowed best-effort cleanup, and translates it into a
fixed terminal class.

The command adapter separately owns an end-to-end raw-`BaseException` guard:

- during argument parsing, environment inspection, conninfo preparation,
  minimum-libpq validation, and side-effect-free runner construction, a raw
  catchable `BaseException` becomes `INTERRUPTED`, exit `3`;
- runner construction performs only deterministic object allocation and has no
  environment, connection, SQL, output, or other external effect;
- after the runner returns a committed report, a raw catchable `BaseException`
  from report-byte retrieval, stdout write, or stdout flush becomes
  `REPORTING_FAILED`, exit `5`;
- a raw catchable `BaseException` from stderr write or flush is suppressed; and
- a final module-entry protocol encloses command invocation and the handoff of
  its controlled integer return to ordinary `SystemExit`. It preserves a
  controlled return already computed by `main()`, preserves success after
  `REPORTED`, translates a catchable interruption before either fact is fixed
  to exit `3`, suppresses its value and traceback, and prevents a
  caller-selected `SystemExit` status from escaping.

The module-entry protocol uses private controlled state to distinguish the
adapter's completed return from a raw `SystemExit` raised while evaluating the
entry path. Its final action is ordinary `SystemExit` termination; it is not a
custom signal handler. A deterministic seam injects SIGINT and a custom direct
`BaseException` while the module entry invokes `main()` and while it hands the
computed status to termination. The test proves the computed controlled status
is retained, an already completed `REPORTED` success is not revoked, and no
traceback, source path, exception value, or caller-selected status escapes.

The adapter catches the runner's fixed terminal classes and guards its own raw
interruptions; no dependency text, traceback, source path, or caller-supplied
`SystemExit` status reaches stderr or controls the command return.

| Last reached phase | Required catchable-interruption classification |
| --- | --- |
| Before a connection is returned | `INTERRUPTED`; no success and no connection cleanup |
| Connected but before `commit()` is called | `INTERRUPTED`; best-effort rollback and close; no success inference |
| Authenticated PostgreSQL termination proving `IdleInTransactionSessionTimeout` rolled back the transaction before `COMMIT` processing | `REFUSED`; best-effort close; no commit-success inference |
| Commit invocation boundary entered through return without acknowledgement | `OUTCOME_UNKNOWN`; commit may or may not have been sent or committed; best-effort close, no rollback claim, and no retry |
| Commit acknowledged but the complete report has not been written and flushed | `REPORTING_FAILED`; no rollback claim and no retry |
| Complete report written and flushed and `REPORTED` independently observed | successful report protocol is already complete; a later signal does not revoke it |

The transition to `COMMIT_IN_FLIGHT` occurs immediately before invoking
`commit()`. A generic direct `BaseException` raised by that call is therefore
`OUTCOME_UNKNOWN`, even if no commit bytes were ultimately sent. The sole
narrower classification is a structured, authenticated PostgreSQL
`IdleInTransactionSessionTimeout` diagnostic that proves the server terminated
and rolled back the transaction before processing `COMMIT`; that is `REFUSED`.
`TransactionTimeout` after the commit-invocation boundary remains
`OUTCOME_UNKNOWN`. The transition to `REPORTED` occurs only after an exact full
stdout write and successful flush.

SIGINT is tested as the normal Python `KeyboardInterrupt` path without adding a
custom signal handler. SIGTERM and other uncatchable termination produce no
complete command result. External classification may use only the last phase
independently observed by a test or deployment barrier: a proven pre-commit
phase is `INTERRUPTED`; once commit may have been sent it is
`OUTCOME_UNKNOWN`; complete-looking stdout without an independently observed
`REPORTED` phase is not success. A signal after independently observed
`REPORTED` does not revoke the already complete protocol. Without such
independent evidence the result is never success and is conservatively
quarantined from automatic retry. No signal handler, watchdog, shutdown hook,
or persistent phase record is introduced.

There is no operation identity in the accepted event shape and no safe retry
deduplication authority. The repository proves at most one append attempt per
invocation and no automatic retry. It cannot prevent a human or external
system from starting another invocation. Deployment must quarantine every
interrupted or outcome-unknown invocation from cross-invocation retry.
Determining whether a later, separately witnessed interval should be recorded
is a new external decision, not a retry of this operation.

### 6.5 Terminal command protocol

Controlled command returns use only these exit codes. Uncatchable signals and
operating-system termination may produce another process status and are
interpreted by the terminal truth table below.

| Exit | Meaning | stdout |
| --- | --- | --- |
| `0` | Commit acknowledged and the exact report was completely written and flushed | one canonical JSON line |
| `2` | Command, timestamp, environment, or conninfo invalid before connection | empty |
| `3` | Known refusal, proven pre-commit server rollback, or catchable interruption before commit invocation | empty |
| `4` | Commit invocation began without acknowledgement; commit may or may not have been sent or committed | empty |
| `5` | Commit acknowledged but report construction, stdout write, or stdout flush failed | empty, partial, or complete-looking report bytes |

Each controlled failure makes at most one stderr write and one stderr flush
with the corresponding exact ASCII bytes below. The displayed `\n` is one LF
byte and is not a backslash followed by `n`.

| Classification | Exit | Exact stderr |
| --- | --- | --- |
| `INVALID_INPUT` | `2` | `security-audit process-crash reconciliation command is invalid\n` |
| `REFUSED` | `3` | `security-audit process-crash reconciliation was refused; no commit succeeded\n` |
| `INTERRUPTED` | `3` | `security-audit process-crash reconciliation was interrupted; no commit was sent; do not retry automatically\n` |
| `OUTCOME_UNKNOWN` | `4` | `security-audit process-crash reconciliation outcome is unknown; do not retry automatically\n` |
| `REPORTING_FAILED` | `5` | `security-audit process-crash reconciliation committed but reporting failed; do not retry automatically\n` |

Stdout receives exactly one `write(report_bytes)` call. Success requires its
return value to have exact type `int` and equal the complete byte length,
followed by one successful `flush()`. A short, non-integer, raising write or a
raising flush is `REPORTING_FAILED`; stdout is never retried or repaired.
Stderr is then attempted even if stdout may be partial or complete-looking. A
full-length write followed by a failed flush can already have exposed the whole
canonical line; exit `5` still makes those bytes non-authoritative. A short or
failed stderr write/flush, including direct `BaseException`, is suppressed
because there is no safer output sink. Any incomplete stdout or stderr protocol
is never evidence of success and never creates retry authority.

This is the sole authoritative terminal truth table:

| Process outcome | Observable stdout | Required interpretation |
| --- | --- | --- |
| Controlled exit `0` with empty stderr | Exactly one canonical report | Success |
| Controlled exit `2` or `3` | Empty | No commit success |
| Controlled exit `4` | Empty | Commit may have occurred; outcome unknown; no automatic retry |
| Controlled exit `5` | Empty, partial, or complete-looking | Commit acknowledged, but reporting protocol failed; never output success; no automatic retry |
| Signal termination before an independently observed `REPORTED` phase | Possibly empty, partial, or complete-looking | Never infer success; quarantine from automatic retry |
| Signal termination after an independently observed `REPORTED` phase | Complete canonical report | Report protocol was already complete; the later signal does not revoke it |

A canonical-looking line without controlled exit `0` or an independently
observed `REPORTED` phase is not success. Conversely, an independently observed
`REPORTED` phase is authoritative only for the already flushed report; it does
not authorize deployment, retry, another mutation, or any broader claim.

## 7. Invariants and acceptance criteria

### `PCR-001` — one independently retained process-window input

The production command accepts exactly one canonical UTC interval start. Its
external authority must have retained that lower bound no later than the
crashed process's first governed attempt after the last independently closed
continuity point. A post-crash observation alone is not sufficient. The command
does not accept a count, interval end, producer, component, event kind,
database, SQL, retry, operation mode, or arbitrary evidence field.

### `PCR-002` — exact surviving-store control authority

Every mutation uses one connection reconstructed from the complete, closed,
operation-specific process-crash secret conninfo. The existing shared
audit-control environment remains unchanged and is not an input. Ambient `PG*`,
service/password/client-certificate/CA/CRL files, partial or multi-host
conninfo, alternate credentials, and caller options cannot participate. The
operation verifies the exact LOGIN, database and checked-in PostgreSQL version
constants, writable-primary state, isolation, read-only state, statement,
lock, idle-in-transaction and transaction timeouts, time zone, date style, and
durability posture on that connection before mutation. The minimum libpq
version and client-owned five-second single-address connect timeout are
verified at the factory seam.

### `PCR-003` — database-owned conservative end

The supplied witnessed start is used unchanged. The interval end is one fresh
database clock from the effectful transaction and must be strictly later. The
returned observation must be no earlier than that end. No Python, request,
restart, or caller-supplied time can narrow or select the end.

### `PCR-004` — exactly one unknown-count mutation

One database-admitted invocation calls only the existing `append_audit_gap`
once with `event_count=0` and `count_unknown=true`. It performs no direct DML
and cannot select another event kind, producer, component, count, retention, or
function.

### `PCR-005` — commit acknowledgement is the only success

A valid function result is not success. Only explicit commit acknowledgement
permits a positive report. Known-precommit failure and authenticated server
evidence of a pre-commit rollback refuse; commit-invocation ambiguity is
permanent outcome unknown for that invocation; neither path retries.

### `PCR-006` — interruption never manufactures certainty

Catchable interruption in adapter validation/construction or in the runner
before commit is a fixed interrupted result; catchable interruption once commit
is invoked is outcome unknown; interruption after commit acknowledgement but
before the full report flush is reporting failed. Raw adapter output
interruptions follow the same phase truth, and stderr interruption is
suppressed. Uncatchable process death produces no complete protocol and is
classified only from an independently observed phase. No interruption, death,
or restart produces a success inference or retry authority, and restart does
not clear or reconstruct the prior attempt.

### `PCR-007` — fixed non-sensitive observability

The event, report, stdout, stderr, exception surface, and ordinary formatted
diagnostics contain no DSN, password, dependency detail, tenant, Party, farm,
actor, issuer, subject, role, request, route, token, credential, secret,
free text, or attacker-controlled identity. Fixed stderr never includes caught
exception text. Success is exactly one 298-byte canonical ASCII JSON line with
the fixed schema, six alphabetically ordered fields, canonical values, and a
512-byte fault ceiling. Controlled failure uses only the exact exit/diagnostic
and terminal truth tables in section 6.5. Complete-looking stdout is not
success under exit `5` or an unclassified signal termination.

### `PCR-008` — bounded per-invocation cost

Parsing, connection count, SQL count, transaction count, cryptographic work,
report size, output calls, and cleanup are fixed and bounded. There is one
single-host connection attempt with a five-second per-address client timeout,
one append attempt per invocation, a two-second statement timeout, a
250-millisecond lock timeout, a ten-second idle-in-transaction timeout, a
15-second transaction timeout, a 27-byte timestamp, a 4096-byte conninfo, one
298-byte admitted report, and a 512-byte fault ceiling. There is no internal
retry, loop, sleep, poll, scheduler, background task, or unbounded collection.
These are data, call-count, and configured database/client bounds, not a hard
wall-clock deadline over stdout/stderr write or flush, connection close,
operating-system scheduling, or uncatchable termination. Cross-invocation
quarantine remains external deployment policy.

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
The deliberately conservative start may overlap an earlier `AUDIT_GAP`,
including one closed by the lost live process; overlapping durable gap intervals
are accepted over-disclosure, and this command neither reads nor coalesces them.

## 8. Production-reachable negative cases

| Invariant | Supported entry and counterexample | Required result |
| --- | --- | --- |
| `PCR-001` | Invoke the fixed command with a missing, duplicate, reordered, extra, noncanonical, offset, naive, infinite, or Unicode-lookalike timestamp; add count/end/database/SQL arguments. At the composition boundary, offer only a post-crash observation with no retained pre-attempt lower bound. | Invalid command shape exits before secret read or connection; composition with only the late observation has no supported entry and performs no mutation. |
| `PCR-002` | Supply over-4096-byte, partial, duplicate-key, URI, multi-host, `hostaddr`, service, password-file, client-certificate, caller-CA/CRL, GSS, or caller-options process-crash conninfo; set hostile `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`, `PGSERVICE`, `PGSERVICEFILE`, timeout and TLS environment values; use libpq below 16; mutate the separate shared control DSN; or point the closed route at a reader, producer, retention, readiness, migrator, owner-like test role, wrong database, standby, unsupported server, hostile role defaults, or read-only transaction. | Invalid route/environment/client refuses before connect; changing the shared DSN has no effect; the factory sees only the reconstructed process-crash conninfo and exact five-second connect timeout; exact same-transaction admission of users, database/version constants, writable primary, read-only/isolation, `2s`, `250ms`, `10s`, `15s`, `UTC`, `ISO, MDY`, and `on` refuses before append on any mismatch. |
| `PCR-003` | Supply a start equal to or later than the database clock, return malformed/naive/infinite clock data, or return an append observation earlier than the interval end. | Clock failures refuse before the function call; inconsistent append output rolls back before commit. |
| `PCR-004` | Inspect the public request and SQL inventory, then use the existing accepted reader test fixture to inspect the live database result; attempt to select a known count, another kind, direct insert, producer, component, or function through the operation. | No such operation surface exists; the test-only reader observes exactly one `AUDIT_GAP` with count unknown and no protected fields. |
| `PCR-005` | Return a valid append row then fail before commit; deliver authenticated `IdleInTransactionSessionTimeout` proof of pre-commit rollback; raise generically or with `TransactionTimeout` after the commit-invocation boundary; return from commit then fail ordinary close. | Precommit failure and proven idle-timeout rollback refuse; commit-boundary ambiguity is outcome unknown with zero retries; post-ack ordinary close failure preserves one committed success. |
| `PCR-006` | Raise `KeyboardInterrupt`, `SystemExit`, and a custom direct `BaseException` from adapter parsing, environment inspection, side-effect-free runner construction, report retrieval, stdout write/flush, stderr write/flush, and the final module-entry invocation/status handoff; let the test-owned Unix-socket protocol relay forward the real command's append to PostgreSQL, observe its completed upstream response in an open transaction while withholding that response from the command, and then send SIGINT/SIGTERM; inject direct `BaseException` at commit and after acknowledgement. | Adapter, runner, and module entry produce exact phase-aware classifications without traceback or caller-selected status; a computed controlled return and already `REPORTED` success are preserved; stderr interruption is suppressed; closing the killed command's upstream PostgreSQL connection rolls back the append and the accepted reader observes no durable `AUDIT_GAP`; uncatchable termination has no success inference; generic commit interruption is outcome unknown; post-ack incomplete or complete-looking output is reporting failed; no path retries. |
| `PCR-007` | Put canaries in the conninfo password, PostgreSQL error, direct `BaseException`, interval parser input, output failure, and environment; exercise the 298-byte report golden, exact stderr bytes, short/non-integer/raising stdout and stderr writes, and stdout/stderr flush failures. | Only the exact canonical report or fixed diagnostic bytes appear; partial or complete-looking stdout without successful terminal status is never success; no canary, traceback, or source path crosses an authorized sink. |
| `PCR-008` | Count input bytes, connections, statements, append attempts, commits, rollbacks, closes, stdout/stderr writes and flushes, and report bytes under success and every failure phase; stall an operating-system output sink separately. | Each repository-owned count and size stays within its fixed contract; client/server timeout values are exact; no automatic retry, poll, sleep, or growth appears. A stalled OS sink demonstrates the explicit absence of a hard wall-clock deadline rather than a false timeout claim. |
| `PCR-009` | Make every dependency fail while presenting a token, tenant-shaped value, route value, and alternate sink fixture. | No authorization, tenant, route publication, readiness change, or fallback call occurs. |
| `PCR-010` | Compare the final path set, migrations, audit contract, provisioning graph, runtime imports, and role/function catalogs with the base. | Only approved operation, command, tests, docs, and mechanical conformance paths differ; accepted authorities are identical. |
| `PCR-011` | Read the success report and documentation after supplying an intentionally earlier conservative start that overlaps a previously closed durable gap. | The exact supplied start is reported and the overlap remains accepted; no text claims non-overlap, repository crash detection, witness authentication, exact loss count, deployment eligibility, or completeness beyond the appended interval. |

Tests may provide controlled connections, output sinks, and barriers through
public constructors. Live interruption evidence must enter through the actual
command process and real PostgreSQL; it must not mutate private state and call
that production evidence. The deterministic live precommit barrier is a
test-owned Unix-socket protocol relay that forwards to real PostgreSQL. It
forwards the append request, then observes and buffers the complete upstream
append response through `ReadyForQuery` with transaction status `T`, without
forwarding that response to the command or exposing or interpreting returned
event data. That protocol boundary proves PostgreSQL executed the append while
the transaction remains open and leaves the real command blocked in
`APPEND_IN_FLIGHT`. The test then kills the command, closes the relay's upstream
PostgreSQL connection, and uses the accepted reader fixture to prove that
connection-loss rollback left no durable `AUDIT_GAP` event. No database
lock is added, so the evidence does not race the 250-millisecond lock timeout
or weaken any production setting. The relay is test evidence only and is not
an authorized production route.

Post-commit row inspection uses the already accepted
`OFARM_SECURITY_AUDIT_READER_PG_DSN` reader fixture after the command outcome is
fixed. That test-only observation cannot influence admission, mutation,
commit classification, retry, or production behavior and is not another
operation authority under section 11.6.

The 512-byte renderer ceiling is not a production-reachable negative case and
therefore is not represented as one in the table. Phase B still fault-injects
an over-ceiling renderer result at the unit seam to prove that the guard fails
closed after an acknowledged commit.

## 9. Proposed architecture and smallest change

### 9.1 Types and ownership

One new `deployment/postgresql/security_audit_process_crash.py` module owns:

- immutable `ProcessCrashReconciliationRequest` with one interval start;
- immutable `ProcessCrashReconciliationSecrets` with one complete control
  conninfo;
- immutable `ProcessCrashReconciliationReport` with only fixed safe fields;
- fixed invalid, refused, interrupted, outcome-unknown, and reporting-failed
  terminal classes;
- one `SecurityAuditProcessCrashReconciliationRunner`;
- one private transaction phase enum;
- fixed operation-specific route sanitizer, minimum-libpq and connection
  constants, admission, clock, and append SQL; and
- exact 298-byte canonical report rendering with a 512-byte fault ceiling.

One new `deployment/postgresql/run_security_audit_process_crash.py` module owns:

- the sole supported CLI argument and operation-specific environment name;
- bounded canonical parsing, minimum-libpq validation, ambient `PG*`
  rejection, and side-effect-free runner construction;
- the adapter-owned raw-`BaseException` guards before connection and after
  acknowledged commit;
- the final module-entry interruption protocol around command invocation and
  controlled-status handoff to ordinary `SystemExit`;
- the exact exit codes and stderr bytes in section 6.5;
- one full report write and flush with short-write handling; and
- construction of the fixed runner.

One focused test module owns deterministic unit, live PostgreSQL, test-only
reader observation and Unix-socket protocol relay, actual SIGINT/SIGTERM
subprocess, adapter/runner/module-entry direct-`BaseException`,
conninfo/environment, byte-protocol, canary, bounded-call, and architecture
evidence. Existing README files may document the command and its non-deployable
external witness prerequisite. Mechanical conformance files may inventory the
test and reject paths or imports outside this contract.

### 9.2 Data flow

```text
independently retained process-window lower bound
  -> canonical --interval-start
  -> fixed command parser
  -> complete closed operation-specific audit-control conninfo
  -> reject ambient/indirect libpq authority and reconstruct route
  -> admit minimum libpq 16 client
  -> one bounded connection and transaction
  -> exact role/database/primary/version/settings/isolation/durability admission
  -> same-transaction database clock
  -> existing append_audit_gap(start, end, 0, true), once
  -> validate fixed row
  -> explicit commit
       -> acknowledged: fixed safe report
       -> exception: fixed outcome unknown, no retry
  -> canonical 298-byte output, guarded at 512 bytes
       -> exact full write and flush: exit success
       -> short/write/flush failure: fixed reporting failure, no retry
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

Stop for decision version 3 if implementation or review would:

- add automatic detection, persistent state, another store, another production
  operation credential or connection authority, or an external witness receipt;
- add TCP, TLS, GSS/Kerberos, client-certificate, CA/CRL, service/password-file,
  or any other file-backed or network transport authority;
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
independently human-controlled operations system retains the process-window
lower bound before governed attempts, witnesses the crash, governs the
surviving-store route, enforces no-retry quarantine, and consumes the command
result. This RFC does not design or simulate that authority.

Evidence that V1 must support automatic detection, multiple replicas, store
promotion, recovery retries, authenticated witness receipts, or a compromised
operator would invalidate this design. The likely upgrade would require a
separate durable process-epoch and externally governed witness protocol, not a
patch to this command.

## 13. Traceability and verification

| Invariant | Owning implementation | Negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `PCR-001` | external composition prerequisite plus command parser and request | missing pre-attempt lower bound; malformed, duplicate, reordered, extra and lookalike inputs | unsupported late-only composition; no connection or secret read for invalid command shape | prerequisite review plus focused parser tests |
| `PCR-002` | operation-specific command route sanitizer, minimum-libpq gate, runner connection factory, checked-in provisioning/version constants, and admission query | shared-DSN mutation, ambient `PG*`, oversize/indirect/file/multi-host/partial conninfo, old libpq, hostile options/defaults, wrong role/database/standby/version/settings | shared DSN has no effect; factory receives only closed reconstructed process-crash conninfo and exact client timeout; no append on any same-transaction admission mismatch | focused conninfo/environment/client/factory tests plus live role and complete server-setting matrix |
| `PCR-003` | same-transaction clock and append-result path | equal/later start, malformed clock, observation before end | append absent or transaction rolled back | unit and live PostgreSQL clock/result cases |
| `PCR-004` | fixed append SQL plus accepted test-only reader fixture | attempted count/kind/function widening or operation-owned readback | reader observes one unknown-count `AUDIT_GAP`, no protected fields, only after outcome fixed | SQL inventory and live reader query |
| `PCR-005` | transaction phase state machine | ordinary/direct-`BaseException`, authenticated idle-timeout rollback, and transaction-timeout/generic failure at commit boundary | exact refused/unknown/committed classifications and zero automatic retries | deterministic connection tests plus live timeout termination |
| `PCR-006` | runner, adapter, final module-entry protocol, and command process | direct catchable interruptions at every adapter/runner/module-entry sink; actual SIGINT/SIGTERM after PostgreSQL completes the relayed append in an open transaction | fixed catchable classification without traceback or caller-selected status; controlled return and `REPORTED` success preservation; stderr interruption suppressed; connection-loss rollback leaves no durable `AUDIT_GAP`; no uncatchable success inference or automatic retry | adapter and module-entry seam matrix plus real subprocess/relay/PostgreSQL interruption, accepted-reader rollback observation, and deterministic runner phases |
| `PCR-007` | sorted fixed report renderer, terminal truth mapping, and binary sinks | canaries, 298-byte golden report, exact diagnostics, short/non-integer/raising writes, flush failures, and over-ceiling fault | exact ASCII bytes, 512-byte fault ceiling, no canary/traceback/source path, incomplete or complete-looking failed output never success | byte-level report, terminal-status, and sink tests |
| `PCR-008` | direct runner, bounded parsers, fixed timeout constants, and command | oversize inputs, every dependency phase, hostile timeout defaults, and stalled OS sink | exact input/connection/statement/append/output call and size ceilings; complete effective-timeout row; explicit no-wall-clock non-claim | deterministic call inventory, live timeout evidence, and stalled-sink non-claim test |
| `PCR-009` | module imports and closed failures | token/tenant/route-shaped inputs with dependency failures | no authority or fallback calls | import and collaborator-call gates |
| `PCR-010` | path and architecture gates | migration/role/runtime/import mutation | exact approved paths only; base authorities identical | diff allowlist, contract check, architecture check |
| `PCR-011` | report schema and documentation | intentionally early conservative start overlapping an existing gap | exact start, overlap acceptance, and non-claims preserved | report golden, live overlap observation, and documentation assertions |

Required Phase B verification, if later authorized:

- focused unit tests for every state and dependency boundary;
- live PostgreSQL tests under every relevant provisioned role;
- actual subprocess/live-PostgreSQL SIGINT and SIGTERM interruption plus
  deterministic public-constructor direct-`BaseException` evidence before,
  during, and after commit;
- adapter-owned parsing/construction/stdout/stderr direct-`BaseException`
  evidence, final module-entry invocation/status-handoff interruption evidence,
  and the complete terminal truth table;
- operation-specific closed conninfo reconstruction, shared-DSN isolation,
  input-size and minimum-libpq gates, ambient `PG*` rejection, no indirect
  libpq file authority, exact client timeout, and live complete effective-
  setting evidence;
- deterministic Unix-socket protocol-relay interruption after PostgreSQL has
  completed the append in an open transaction, followed by connection-loss
  rollback evidence without weakening `lock_timeout`;
- exact one-row unknown-count event, protected-field absence, and overlap
  observation through the existing test-only reader fixture;
- byte-exact golden report, diagnostic, short-write, flush-failure, fixed canary,
  and observability-sink checks;
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

- who retains the process-window lower bound before the first governed attempt,
  what establishes the last independently closed continuity point, and who
  independently witnesses a crash;
- how the operation-specific surviving audit-control route is selected and held
  separately from the existing shared control environment;
- how interrupted and outcome-unknown attempts are quarantined from retry; and
- how an output consumer independently observes `REPORTED` and how the result
  gates later runtime publication.

Those are explicit deployment prerequisites. Their absence makes production
composition unavailable; it does not authorize provider fixtures or a witness
system in this pull request.

### 14.2 Review disposition

- Decision version: the previously displayed version 1 card was never approved
  and is withdrawn. The operation-specific route authority and terminal
  protocol are material semantic changes, so this revision is decision version
  2. A version 2 card may be displayed only after its exact head completes
  review and admitted hosted gates; generic task messages do not approve it.
- Blockers: review
  [5032152128](https://github.com/samovers/OFARM2/pull/338#pullrequestreview-5032152128)
  of exact head `53c4c17371a100e28764456a2b0f64896319720b`
  demonstrated adapter-boundary and terminal-truth residues. Review
  [5032563741](https://github.com/samovers/OFARM2/pull/338#pullrequestreview-5032563741)
  of that same head demonstrated omitted transaction-scoped timeouts and a
  shared-environment grammar conflict. This revision addresses the combined
  four Blockers without changing the Phase A path or primary trust boundary.
  They remain review-pending until a new exact-head review reports zero
  demonstrated Blockers.
- Follow-ups: bounded-cost wording, test-only reader observation, a non-locking
  protocol-relay interruption barrier, `RETENTION_SECONDS` authority, accepted
  overlap, and minimum-libpq posture are incorporated. The earlier one-append-
  attempt wording remains incorporated. Cross-invocation quarantine remains an
  external deployment prerequisite. Final cross-slice hostile evidence and
  closure audit remain in issue #192; the separately recorded items in section
  11.5 remain outside this boundary.
- Preferences: `INPUT_VALIDATED` remains distinct from same-connection
  `DATABASE_ADMITTED`; alphabetical report rendering is adopted to reuse the
  store-loss precedent; the 512-byte ceiling is explicitly a fault guard over
  the exact 298-byte admitted report.
- Review independence: review 5032563741 explicitly identifies itself as a
  self-review from the pull-request author account and does not satisfy an
  independent-review gate. Its reproducible evidence is recorded here without
  misrepresenting its independence.
- Next review scope: these corrections and affected invariants only unless new
  evidence demonstrates that the original scope is unsafe.
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
