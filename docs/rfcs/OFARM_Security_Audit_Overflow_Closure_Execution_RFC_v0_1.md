# OFARM Security-Audit Overflow Closure Execution — Phase A Contract v0.2

**Status:** proposed decision-version-2 contract amendment under exact-head
Phase A review; version-2 Phase B implementation, deployment, and production
operation are not authorized

**Draft implementation pull request:**
`https://github.com/samovers/OFARM2/pull/311`

**Contract identity:**
`ofarm2.security-audit-overflow-closure-execution.v0.2`

**Decision identity:**
`ISSUE192-SECURITY-AUDIT-OVERFLOW-CLOSURE-EXECUTION-001`, proposed version `2`;
the version-1 approval remains historical evidence only for this semantic
amendment

**Issue:** #192

**Reviewed base:** `9c12c115bd29d9889234edd9e4c84377d9e332f8`

**Primary trust boundary:** isolated security-audit overflow-closure execution

**Phase A version-2 review boundary:** the semantic RFC amendment only. The
same pull-request head may also contain the meaning-preserving binary-stderr
correction authorized by version 1; no version-2 semantic implementation may
precede exact version-2 approval

**Maximum final pull request boundary:** this RFC, one deployment-layer
overflow runner, one fixed command adapter, one focused test module, minimal
operator documentation, and the mechanically regenerated test inventory only

## 1. Problem and goal

The accepted security-audit database already starts an `OVERFLOW_STARTED`
marker when a producer reaches its fixed quota. It also owns two control-only
operations:

```sql
SELECT *
FROM ofarm_security.observe_next_closeable_overflow_bucket()
```

and:

```sql
SELECT *
FROM ofarm_security.close_overflow_bucket(
    :producer,
    :component,
    :bucket_start
)
```

Current `main` has no supported production command that selects the one
database-authorized oldest closeable bucket and commits its matching
`OVERFLOW_ENDED` transition. Open overflow buckets can therefore remain
unclosed even though the database protocol is complete.

This task establishes one privileged, one-shot command that:

- accepts no caller-selected bucket, producer, component, limit, or mode;
- validates its complete command configuration before any connection;
- uses only the isolated audit-control credential;
- asks PostgreSQL for at most the oldest closeable bucket;
- closes at most that exact observed bucket in the same `READ COMMITTED`
  transaction;
- validates and pre-renders the complete non-sensitive result before commit;
- commits explicitly with `synchronous_commit=on`;
- emits one canonical ASCII JSON report;
- treats no closeable bucket as a successful bounded no-op; and
- never retries automatically.

PostgreSQL remains the sole authority for producer/component attribution,
database time, bucket ordering, closeability, writer fencing, overflow count,
`COUNT_UNKNOWN`, idempotent closure, quota high-water advancement, receipt
handling, and the `OVERFLOW_ENDED` maintenance event.

This task directly advances issue #192's bounded gap/overflow-control
criterion for overflow closure. It does not establish runtime gap detection,
mark a bucket unknown, or operate a scheduler.

## 2. Learning value

The slice proves that an overflow interval can reach its database-owned closed
state without table access, a caller-selected bucket, a drain loop, or a
second authority. It reduces the demonstrated risk that accepted
`OVERFLOW_STARTED` evidence remains indefinitely open because no supported
operator primitive invokes the already accepted closure protocol.

## 3. Non-goals

This pull request does not change or add:

- migrations, functions, types, relations, indexes, roles, grants, or
  provisioning;
- producer quota, bucket duration, accepted-event ceiling, overflow receipt,
  count, `COUNT_UNKNOWN`, high-water, writer-barrier, or marker policy;
- `mark_overflow_count_unknown` orchestration or any inference that a count is
  exact;
- `AUDIT_GAP` creation, unavailable-interval tracking, process-crash evidence,
  audit-health state, readiness thresholds, or external clock-health fencing;
- authentication, routing, producer append behavior, denial behavior, Kernel
  runtime composition, `RuntimeConfig`, `/health`, or readiness;
- HMAC key custody, retirement, destruction, or deployment ownership;
- retention, bounded query, export, break-glass, temporary login, store-loss,
  empty-recreate, backup, replica, CDC, or recovery operations;
- a web endpoint, daemon, service, scheduler, loop, drain-until-empty mode,
  queue, spool, cache, or dead-letter path;
- tenant storage, tenant reconstruction, application pools, support paths,
  telemetry, ordinary logs, or issue #176 temporal behavior;
- deployment activation, production operation, release, current/default
  promotion, production readiness, or a security waiver; or
- a guarantee that every open overflow bucket will be closed by a deadline.

The command deliberately does not accept a possible ambiguous bucket from a
producer. That carrier and the authority to invoke
`mark_overflow_count_unknown` belong to a separately governed runtime-health
and gap-control boundary. Closing a database-selected bucket honors whatever
count posture PostgreSQL already owns at the transaction's closure point.

## 4. Trust model

### 4.1 Protected assets

- correct pairing of every `OVERFLOW_ENDED` marker with one accepted open
  bucket;
- the requirement that the caller cannot choose producer, component, bucket,
  count posture, interval, event identity, or retention values;
- the event-writer close barrier and quota high-water transition;
- explicit transaction finality and honest commit-ambiguity reporting;
- the audit-control credential and conninfo value;
- absence of tenant, Party, principal, actor, request, credential, route, raw
  correlation, and exception data from output and diagnostics; and
- the one-operation resource bound.

### 4.2 Trusted components

- the accepted issue #174 migrations, roles, grants, functions, constraints,
  and provisioning;
- PostgreSQL transaction, lock, database-clock, exact `session_user`, and
  function semantics;
- the checked-in security-audit contract constants;
- Psycopg 3.3.4 and libpq;
- the deployment-layer runner and fixed command adapter;
- deployment-controlled endpoint routing, service files, DNS, TLS
  configuration, secret injection, and stdout destination; and
- the operating system and Python runtime.

The accepted database is trusted to implement
`observe_next_closeable_overflow_bucket()` and `close_overflow_bucket()`
exactly. This command validates their supported carrier shapes but does not
duplicate their policy.

### 4.3 Untrusted actors and inputs

- every command-line token;
- missing, malformed, whitespace-only, or hostile conninfo;
- DSN-provided timeout and startup options;
- network availability and commit acknowledgement;
- a wrong-role or cross-service route;
- every returned row and value until validated;
- stdout and stderr availability, short writes, and flush failures;
- invocation timing and frequency; and
- a compromised producer limited to its accepted database grants and fixed
  producer/component pair.

A holder of the audit-control credential is a privileged security operator.
The database still prevents that holder from choosing an active, absent,
never-overflowed, malformed, or cross-pair bucket through this command because
the command supplies only the bucket that the database observer returned.

### 4.4 Explicitly excluded attacker capabilities

The following are out of scope:

- arbitrary in-process mutation;
- local source substitution;
- compromised dependencies;
- filesystem mutation;
- operator, database-owner, migrator, or superuser compromise;
- DNS, service-file, TLS endpoint, operating-system, or database-clock
  compromise; and
- simultaneous failure of stderr, where no diagnostic delivery can be
  guaranteed.

Ordinary invocation mistakes, hostile configuration, wrong credentials,
network loss, database refusal, result corruption at the supported connection
seam, commit acknowledgement loss, and stdout failure remain in scope.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Fixed producer/component pairs | Existing security-audit contract and database functions |
| Oldest closeable bucket | `observe_next_closeable_overflow_bucket()` |
| Closeability at transition time | `close_overflow_bucket()` and database clock |
| Writer serialization | Existing event-writer barrier inside the close function |
| Overflow count and `COUNT_UNKNOWN` | Existing quota bucket and close function |
| `OVERFLOW_ENDED` identity, interval, and count posture | Existing close function |
| Quota high-water and receipt cleanup/retention | Existing close function |
| Atomic closure and marker commit | PostgreSQL transaction |
| Retention timestamp validation | Existing `RETENTION_SECONDS` constant |
| Bucket-duration validation | Existing `QUOTA_BUCKET_SECONDS` constant |
| Explicit conninfo input | `OFARM_SECURITY_AUDIT_CONTROL_PG_DSN` |
| Endpoint expansion and selection | Deployment configuration and libpq |
| Runtime startup options | Fixed runner keyword arguments |
| Transaction construction | Idle non-autocommit Psycopg connection plus the two fixed queries |
| Transaction finality | Explicit `Connection.commit()` or no-op `rollback()` |
| Successful process report | Fixed, pre-rendered JSON protocol |
| Report delivery | Complete stdout write and successful flush |

The environment variable is not the sole endpoint authority. Unset
connection parameters may come from libpq environment variables or built-in
defaults, and `service=` may expand a service file. Multi-host, DNS, TLS, and
endpoint selection remain deployment-route concerns.

The adapter validates conninfo syntax with
`psycopg.conninfo.conninfo_to_dict()`. Code-supplied keyword parameters
override matching conninfo parameters, including `connect_timeout` and
`options`.

There is no caller bucket, direct table read, generic SQL, alternate
credential, `SET ROLE`, compatibility alias, or automatic retry. The existing
retention and reader runners are not generalized because they have different
credentials, transaction shapes, and result protocols.

## 6. State machine and ordering

### 6.1 Command and connection validation

Empty `argv` is the only executing command shape. Every token, including
`-h`, `--help`, a bucket, a producer, a limit, `--`, or positional text, causes
exit `2`, no stdout, one fixed stderr line, and no connection attempt.
Human-readable usage belongs only in `deployment/postgresql/README.md`.

The command then:

1. requires a non-empty, non-whitespace audit-control DSN;
2. validates it with Psycopg conninfo parsing;
3. makes exactly one call to `psycopg.connect`;
4. receives and uses at most one returned backend connection;
5. permits libpq to attempt multiple configured hosts inside that one call;
   and
6. uses five seconds per configured host or address attempt, with no claim of
   a global network or process deadline.

Code-owned connection arguments are:

- `autocommit=False`;
- `connect_timeout=5`; and
- `options` replacing all DSN-provided startup options with:
  - `statement_timeout=5000`;
  - `lock_timeout=500`;
  - `idle_in_transaction_session_timeout=10000`;
  - `transaction_timeout=15000`;
  - `work_mem=1024kB`;
  - `TimeZone=UTC`;
  - `DateStyle=ISO,MDY`; and
  - `synchronous_commit=on`.

`temp_file_limit=0` remains a provisioned role default. The non-superuser
command does not send it or require permission to set it.

These settings match or narrow the accepted audit-control role's database I/O
budgets. They do not claim to bound DNS resolution, every TCP operation,
output writes, or total process wall time.

### 6.2 Exact transaction construction

Before SQL, the runner requires that the returned connection:

- is open;
- has `autocommit is False`; and
- reports `psycopg.pq.TransactionStatus.IDLE`.

Any other state refuses before either database function or `commit()` is
called. While idle, the runner sets the isolation level through the Psycopg
connection API to `psycopg.IsolationLevel.READ_COMMITTED`.

The implementation must not use a connection or transaction context manager,
because implicit exit-time commit would hide the exact ambiguity boundary.

The first and only observation query is:

```sql
SELECT *
FROM ofarm_security.observe_next_closeable_overflow_bucket()
```

The runner fetches at most two rows to prove the result is empty or exactly
one row. A nonempty row must be one exact producer/component pair from the
accepted contract and one finite, aware, minute-aligned bucket timestamp.

### 6.3 No-bucket transition

If the observation is empty:

```text
NOT_SUBMITTED -> OBSERVATION_SUBMITTED -> EMPTY_OBSERVED
              -> ROLLING_BACK -> NO_BUCKET_COMPLETE
```

The runner calls `rollback()` to end the observation transaction. It never
calls the close function or `commit()`. Only normal return from `rollback()`
permits the fixed `NO_CLOSEABLE_BUCKET` report.

If `rollback()` raises, the runner applies section 6.5's fixed transport
classifier: a transport failure is exit `3`, and every other ordinary
exception is exit `1`. No close or commit was submitted, so neither outcome is
commit ambiguity. Connection cleanup after a normally returned rollback is
best effort and cannot downgrade the known no-bucket result.

### 6.4 Closure transition

If the observation returns one valid bucket, the runner submits exactly once:

```sql
SELECT *
FROM ofarm_security.close_overflow_bucket(%s, %s, %s)
```

using only the three validated observed values as bound parameters in the same
transaction:

```text
NOT_SUBMITTED -> OBSERVATION_SUBMITTED -> BUCKET_OBSERVED
              -> CLOSE_SUBMITTED -> CLOSE_RESULT_OBSERVED
              -> REPORT_RENDERED -> COMMITTING -> ACKNOWLEDGED
```

The close result must contain exactly one non-nil event UUID, one finite aware
`observed_at`, and one finite aware `purge_after` equal to `observed_at` plus
the accepted retention duration. No second result row may exist.

The close function is idempotent. If a concurrent closer committed first, the
function can return that already-existing `OVERFLOW_ENDED` event. Therefore
`ACKNOWLEDGED` means that the selected bucket is closed under the reported
event identity; it does not prove that this invocation created the event, and
the reported `observedAt` may predate this invocation.

The complete success report is rendered before `COMMITTING`. Any observation,
close, shape, or rendering failure before that state is classified by section
6.5, then triggers best-effort rollback and close. Cleanup cannot replace the
classification. `commit()` is never called.

Only normal return from the one explicit `commit()` is acknowledgement.
Every exception from that call is `OUTCOME_UNKNOWN`; the runner closes the
connection, exposes no closure result, and makes no retry or reconciliation
attempt. A `BaseException` or process death after `CLOSE_SUBMITTED` can prevent
a terminal protocol and must also be treated operationally as unknown.

Post-acknowledgement connection cleanup is best effort. Cleanup failure cannot
downgrade a normally returned commit to refused or unknown.

### 6.5 Output protocol

Exit `0` has exactly one canonical ASCII JSON line and one LF byte.

For an empty observation:

```json
{"outcome":"NO_CLOSEABLE_BUCKET","schema":"ofarm.security-audit-overflow-closure-report.v1"}
```

For an acknowledged closure, the report contains only:

- `schema`, fixed to
  `ofarm.security-audit-overflow-closure-report.v1`;
- `outcome`, fixed to `ACKNOWLEDGED`;
- `producer` and `component`, copied from the validated closed contract pair;
- `bucketStart`, copied from the validated observed bucket;
- `overflowEndedEventId`, copied from the validated close result;
- `observedAt`, copied from the validated close result; and
- `purgeAfter`, copied from the validated close result.

Every timestamp is normalized to UTC and encoded with exactly six fractional
digits and a final `Z`. Every UUID uses Python's canonical lowercase string
form. Both report forms use:

```python
json.dumps(
    document,
    ensure_ascii=True,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("ascii") + b"\n"
```

An acknowledged closure therefore has exactly these keys and ordering:

```json
{"bucketStart":"2026-08-14T08:00:00.000000Z","component":"AUTHENTICATION","observedAt":"2026-08-14T08:01:00.123456Z","outcome":"ACKNOWLEDGED","overflowEndedEventId":"11111111-1111-4111-8111-111111111111","producer":"AUTHENTICATION_BOUNDARY_V1","purgeAfter":"2026-09-13T08:01:00.123456Z","schema":"ofarm.security-audit-overflow-closure-report.v1"}
```

It deliberately contains no overflow count or `COUNT_UNKNOWN` field. Those
remain visible only through the separately authorized reader and cannot be
inferred by this command.

### 6.5.1 Complete state-to-terminal classification

For failures after a connection has been returned and before `COMMITTING`, a
transport failure is exactly a `psycopg.OperationalError` whose SQLSTATE is
absent or starts with class `08`. Every other ordinary exception from a
supported observer, close, result-validation, rendering, rollback, or
connection-state step is non-transport and is refused. The connection factory
is the one exception to that split: any ordinary exception before it returns
a connection is unavailable.

The production runner applies this table without inspecting secret-bearing
exception text:

| Failure or completion point | Required terminal result |
| --- | --- |
| Invalid arguments, blank conninfo, or malformed conninfo | Exit `2`, command invalid; no connection call |
| Connection factory raises before returning a connection | Exit `3`, unavailable; no commit sent |
| Returned connection is closed, autocommit, non-idle, or otherwise deterministically invalid | Exit `1`, refused; no observer, close, or commit call |
| Transport failure while validating or configuring the returned connection | Exit `3`, unavailable; no commit sent |
| Non-transport observer or close SQL refusal | Best-effort rollback and close, then exit `1`, refused |
| Transport failure during observer or close execution or fetch, before `COMMITTING` | Best-effort rollback and close, then exit `3`, unavailable; no commit sent |
| Invalid observation, invalid close result, or report pre-rendering failure | Best-effort rollback and close, then exit `1`, refused |
| Empty observation followed by transport failure from `rollback()` | Best-effort close, then exit `3`, unavailable; no commit sent |
| Empty observation followed by any other ordinary `rollback()` exception | Best-effort close, then exit `1`, refused |
| Empty observation followed by normal `rollback()` return | `NO_BUCKET_COMPLETE`; cleanup is best effort |
| Any ordinary exception raised from the one explicit `commit()` | Exit `4`, `OUTCOME_UNKNOWN`; expose no result and do not retry |
| Normal return from the one explicit `commit()` | `ACKNOWLEDGED`; cleanup is best effort |
| Known no-bucket or acknowledged result followed by incomplete stdout write or failed flush | Exit `5`, reporting failed; partial stdout is invalid |
| Known no-bucket or acknowledged result followed by complete stdout write and flush | Exit `0`, complete terminal report |

Best-effort rollback or close failure never replaces the already selected
terminal classification. Cleanup failure after normal no-bucket rollback or
normal commit likewise cannot downgrade that known database result.

Exit `4` is reserved exclusively for an ordinary exception raised by the
explicit `commit()` call. There is no commit-time SQLSTATE or exception-class
allowlist: normal return from `commit()` is the only controlled path to
`ACKNOWLEDGED`.

### 6.5.2 Exact failure diagnostics

Failure diagnostics contain no raw exception, DSN, credential, database
result, bucket, timestamp, UUID, tenant, principal, request, route, or
correlation value.

In this table, the two source characters `\n` denote exactly one terminal LF
byte (`0x0A`). The backslash and `n` are not emitted. Each diagnostic is ASCII
on one physical line, with no CR or additional trailing byte.

| Exit | Exact stderr bytes |
| --- | --- |
| `1` | `security-audit overflow closure was refused\n` |
| `2` | `security-audit overflow closure command is invalid\n` |
| `3` | `security-audit overflow closure is unavailable; no commit was sent\n` |
| `4` | `security-audit overflow closure outcome is unknown; do not retry automatically\n` |
| `5` | `security-audit overflow closure result reporting failed; do not retry automatically\n` |

Every controlled failure requires the complete diagnostic write count and a
successful stderr flush. If either fails, the invocation has no complete
terminal protocol.

The production runner converts every ordinary exception from its supported
external steps into one declared outcome using the state it actually reached.
The command adapter catches only those declared outcomes. It deliberately has
no catch-all for an unexpected ordinary exception from a nonconforming
injected runner, because it cannot reconstruct that runner's hidden state and
cannot truthfully invent exit `1`, `3`, or `4`. Such a programming-seam
failure, a `BaseException`, forced process termination, or stderr failure may
leave an incomplete protocol; none is evidence that `commit()` was attempted
or that the operation succeeded.

Operators and automation must not retry exit `4`, exit `5`, or an incomplete
process protocol automatically. A later invocation does not reconcile an
earlier bucket; it asks the database for the then-oldest closeable bucket and
could close a different one.

## 7. Invariants and acceptance criteria

| ID | Falsifiable invariant |
| --- | --- |
| `OVC-001` | Empty `argv` and one syntactically valid, nonblank audit-control conninfo are the only caller inputs that can reach a connection. No bucket, producer, component, count, timestamp, limit, role, or retry selector is accepted. |
| `OVC-002` | The runner invokes only the existing observer and, after exactly one valid nonempty result, the existing close function through one returned connection. It uses no table read, generic SQL, alternate role, `SET ROLE`, tenant connection, or fallback. |
| `OVC-003` | One invocation observes at most one database-selected oldest closeable bucket and closes, or idempotently acknowledges, at most that exact bucket. An empty observation submits no close and no commit. `ACKNOWLEDGED` proves the bucket is closed under the reported event identity, not that this invocation created the event. |
| `OVC-004` | One invocation makes exactly one `psycopg.connect` call, begins from an open idle non-autocommit connection, runs at `READ_COMMITTED`, and makes no automatic retry. Code-owned connection parameters override matching conninfo settings without claiming a global deadline. |
| `OVC-005` | Observation and close occur in the same explicit transaction. A closure success requires one valid result, complete pre-rendering, and normal return from explicit `commit()` with `synchronous_commit=on`. |
| `OVC-006` | PostgreSQL alone decides closeability, ordering, count posture, writer fencing, high-water, receipts, interval, and maintenance-event values. Client validation cannot widen or replace that authority. |
| `OVC-007` | A failure before `COMMITTING` never becomes commit ambiguity. The production runner classifies every ordinary supported-step exception from its actual state. Every controlled `commit()` exception, and only such an exception, is `OUTCOME_UNKNOWN`, exposes no closure result, and triggers no retry or second credential. The adapter does not invent a state for a nonconforming runner. |
| `OVC-008` | Output is exactly one of the two fixed canonical JSON forms and contains only the fixed schema/outcome plus the six named validated closure identity fields when applicable. Every controlled failure writes and flushes exactly the exit-paired ASCII diagnostic bytes. Neither channel contains a count claim, event payload, tenant, Party, actor, principal, request, credential, route, correlation value, DSN, or raw exception detail. |
| `OVC-009` | A terminal database/no-bucket result followed by report failure produces exit `5`, never a false successful report or a database retry. Post-terminal cleanup failure cannot downgrade the known result. |
| `OVC-010` | The implementation remains in `deployment/postgresql`; Kernel production composition, audit-health/readiness, gap handling, and every independent authority remain unchanged. |
| `OVC-011` | The command makes no scheduler, deadline, lossless delivery, exact-count, dynamic-readiness, external-clock, deployment, or production-operation claim. Operator documentation repeats that every possibly ambiguous bucket must be marked `COUNT_UNKNOWN` before operational closure because closure makes its count posture immutable. |

## 8. Production-reachable negative cases

| ID | Counterexample and required result |
| --- | --- |
| `OVC-001` | Invoke with `-h`, `--help`, `--bucket`, a producer, a timestamp, `--`, or any positional token. Exit `2`; no connection call. Supply blank or malformed conninfo with the same result. |
| `OVC-002` | Supply a reader, retention, producer, readiness, application, or tenant DSN. The public observer refuses through its exact `session_user` rule; the runner performs no fallback or close. |
| `OVC-003` | Seed two closeable overflow buckets in the live isolated audit fixture. One run closes only the database-ordered oldest bucket and leaves the second observable. Run with no bucket and prove no close query or commit. Through the provisioned control login, pause one real runner after it observes one exact bucket and before it submits the close. Commit that same exact close through a controlled test-only closer, then resume the runner. The runner reports `ACKNOWLEDGED` with the closer's event ID, and exactly one `OVERFLOW_ENDED` event exists. This evidence requires only one simultaneous connection through the connection-limited control login and makes no two-runner production claim. |
| `OVC-004` | Put `connect_timeout=0` and timeout-disabling `options` in valid conninfo. The supported connection seam observes exactly one connect call with code-owned overrides. Return an already-active connection and prove both functions and commit remain untouched. |
| `OVC-005` | Return a valid bucket, then zero, two, nil-UUID, naive-time, or retention-inconsistent close rows through the public runner seam. The runner rolls back and never calls commit. |
| `OVC-006` | Race an admitted writer and closure in the existing live PostgreSQL test. The writer barrier and high-water prevent premature close or bucket recreation; the runner introduces no alternate decision. |
| `OVC-006` | Set the observed database bucket to a never-overflowed, active, malformed, or wrong-pair value through the supported result seam. Client validation or the close function refuses; no marker commits. |
| `OVC-007` | Exercise a factory exception, invalid returned connection, deterministic observer and close refusals, observer and close transport losses, malformed carriers, and both transport and non-transport no-bucket rollback exceptions; require the exact exit `3`/`1` split and no commit. Return one valid close result, pre-render it, then make `commit()` raise both a class-08 `OperationalError` and a different Psycopg server exception in separate tests; only these cases exit `4`. Make a stub runner raise an unexpected canary-bearing `RuntimeError`; the exception escapes the adapter without a fabricated terminal diagnostic or retry. |
| `OVC-008` | Cause authentication failure with canaries in the DSN and raw exception. Stdout remains empty and stderr is only the exit-paired fixed diagnostic. Compare all five diagnostics and both success reports byte-for-byte, including exact keys, UTC microseconds, UUID spelling, sort order, separators, and one final LF with no CR or extra byte; prove no count field exists. Make a diagnostic short-write or flush failure and require an incomplete protocol rather than a claimed exit. |
| `OVC-009` | After a normal no-bucket rollback or acknowledged close, make stdout short-write or flush fail. Exit `5`; no second database attempt. Make post-terminal close fail and prove the known result remains reportable. |
| `OVC-010` | Architecture checks prove no Kernel production module imports the operational runner and every forbidden path remains unchanged. |
| `OVC-011` | Inspect the command and README. They provide one-shot operation only, expressly disclaim scheduling, gap recovery, readiness, deployment, and exact-count claims, and state the required `COUNT_UNKNOWN`-before-closure ordering for every possibly ambiguous bucket. |

The existing live database tests remain authoritative for overflow receipt
collisions, `COUNT_UNKNOWN`, concurrent quota-boundary writes, close barriers,
backward-clock high-water refusal, idempotent close, retention cleanup, and
wrong-role function access. This slice does not duplicate those policies in
Python.

## 9. Proposed architecture and smallest change

### 9.1 Production ownership

`deployment/postgresql/security_audit_overflow.py` will own:

- one immutable validated bucket value;
- one immutable validated closure-event value;
- fixed observer and close SQL;
- fixed bounded connection options;
- closed unavailable, refused, outcome-unknown failures;
- connection-state and result validation;
- the explicit no-bucket rollback and closure commit state machine; and
- both canonical success-report encodings.

`deployment/postgresql/run_security_audit_overflow.py` will own:

- exact empty-argument enforcement;
- environment lookup and conninfo validation;
- production Psycopg connection composition;
- exit-code mapping for the runner's declared outcomes, with no generic
  runner-exception catch-all;
- stdout and stderr writes and flushing; and
- terminal reporting failure.

The runner accepts one constructor-bound connection factory as its supported
composition seam. It introduces no generic operations framework, renderer
interface, pool, scheduler, mutable registry, optional capability bag, or
`Any`-typed authority object.

The application runtime and `RuntimeConfig` remain unchanged, so the
application never receives the audit-control credential through this slice.

### 9.2 Data flow

```text
fixed control DSN environment
    -> complete conninfo validation
    -> one bounded psycopg.connect call
    -> one idle non-autocommit READ COMMITTED connection
    -> exact oldest-closeable observer
        -> empty: explicit rollback -> fixed no-bucket report
        -> one bucket: validate closed pair and minute timestamp
            -> exact close function with the same three values
            -> validate event identity and retention deadline
            -> acknowledge either this close or an idempotent concurrent close
            -> pre-render fixed closure report
            -> explicit COMMITTING boundary
            -> acknowledged commit
            -> fixed closure report
```

### 9.3 Why no smaller slice is honest

An observer-only command would expose a bucket but not advance the required
closure state. A caller-parameterized close command would move bucket
selection outside the accepted database authority. A close-only wrapper over
a supplied identity would create a new operator input and reconciliation
protocol.

Combining the existing one-row observer and close operation in one explicit
transaction is therefore the minimum functional boundary. It preserves the
database as the only selector and delivers the missing `OVERFLOW_ENDED`
transition without importing gap, health, readiness, or scheduler authority.

## 10. Elegance audit

- bucket-selection sources of truth: one;
- closeability and count-posture sources of truth: one database transition;
- supported database connections per invocation: one;
- observer submissions: one;
- close submissions: zero or one;
- explicit commit points: zero or one;
- explicit no-op rollback points: zero or one;
- transaction-managing contexts: zero;
- caller bucket identities: zero;
- automatic retry or reconciliation paths: zero;
- direct relation-read or DML paths: zero;
- success schemas: one schema with two closed outcomes;
- new generic abstractions: zero; and
- independent authorities changed: zero.

`QUOTA_BUCKET_SECONDS`, `RETENTION_SECONDS`, and the producer/component matrix
are imported from the accepted contract rather than duplicated. Nothing
existing needs deletion because no production overflow controller exists. A
small dedicated deployment module is safer than modifying the ingest client,
retention runner, or bounded reader, each of which has a different credential
and state machine.

## 11. Pull request and approval boundary

### 11.1 Exact technical path allowlist

The final pull request may change exactly these paths:

1. `docs/rfcs/OFARM_Security_Audit_Overflow_Closure_Execution_RFC_v0_1.md`
2. `deployment/postgresql/security_audit_overflow.py`
3. `deployment/postgresql/run_security_audit_overflow.py`
4. `deployment/postgresql/README.md`
5. `kernel/tests/test_security_audit_overflow.py`
6. `conformance/review_baseline_test_inventory.json`

The RFC may change after approval only to mark approved status, append the
compact AI-attested approval evidence required by the governing workflow, and
record meaning-preserving implementation or verification disposition. A
semantic contract change requires a new decision version.

The inventory is a required mechanical Phase B change because the focused
test module necessarily adds collected nodes.

The existing `v0_1` filename is retained because renaming it would leave the
exact technical path envelope. The contract identity inside that fixed path
advances to `v0.2` for decision version 2.

### 11.2 Explicitly unchanged paths and authorities

- every production Kernel module and `kernel/README.md`;
- `kernel/runtime_config.py`, `kernel/security_audit_client.py`, and
  `kernel/security_audit_runtime.py`;
- `security_audit/migrations/*`;
- `deployment/postgresql/audit_contract.py`;
- `deployment/postgresql/provisioning.py` and
  `deployment/postgresql/provisioning_specs.py`;
- the retention and bounded-reader modules merged through pull requests #307,
  #308, #309, and #310;
- every issue #172 and #176 path; and
- every file outside the exact allowlist.

### 11.3 Dependencies

- reviewed base `9c12c115bd29d9889234edd9e4c84377d9e332f8`;
- existing issue #174 database authority;
- merged issue #192 ingest, runtime, retention, and bounded-reader foundations;
- no stacked pull request;
- open issue #172 does not block this isolated security operation; and
- completed issues #252 and #254 mutex evidence is not recreated.

### 11.4 Reviewer non-requirements

Reviewers must not require a migration, new role, new observation API,
`mark_overflow_count_unknown` caller, gap recorder, health state, readiness
threshold, external clock fence, scheduler, HMAC retirement, retention,
reader/export, break-glass, store recovery, deployment activation, or issue
#172/#176 change from this pull request.

### 11.5 Follow-ups

Issue #192 continues to own separate boundaries for:

- external clock-health fencing and dynamic audit readiness;
- runtime unavailable-interval and `AUDIT_GAP` control;
- ambiguous overflow-bucket `COUNT_UNKNOWN` orchestration before operational
  closure scheduling;
- destructive HMAC retirement after its custody prerequisite;
- break-glass export and temporary-login closure;
- store-loss recovery; and
- remaining end-to-end hostile evidence.

No new issue is required merely to duplicate those open acceptance criteria.

### 11.6 Stop and reapproval conditions

Stop immediately if implementation requires:

- a migration, function, role, grant, contract, or provisioning change;
- accepting a caller-selected bucket or count posture;
- invoking `mark_overflow_count_unknown` or `append_audit_gap`;
- a second credential, table read, generic SQL, or cross-service route;
- an autonomous scheduler, loop, queue, spool, health state, or readiness
  coupling;
- Kernel runtime composition, HMAC custody, reader/export, break-glass,
  retention, recovery, or deployment activation;
- another pull request;
- any path outside the exact allowlist; or
- a material change to the trust boundary, authority map, permitted effects,
  non-effects, invariant, transaction protocol, output protocol, irreversible
  behavior, or named draft pull request.

Those changes require a separate prerequisite, follow-up, or new decision
version.

## 12. Provisional design record

The one-shot technical primitive is not provisional. It remains valid if a
separately governed operations surface or scheduler invokes it later after
runtime unknown-count ordering is solved.

The command is not deployment-ready by itself. Deployment must independently
establish credential custody, route isolation, cadence, runtime-health
coordination, and the rule that every possible ambiguous overflow bucket is
marked `COUNT_UNKNOWN` before it can be operationally closed. This pull request
does not authorize an operator to run the command against a deployed service.
The operator README must repeat that ordering and explain that closure makes
the database-owned count posture immutable.

Evidence requiring technical redesign includes inability to keep observation
and close on one transaction, a safe need for caller bucket selection or
automatic reconciliation, a required second credential, or a demonstrated
defect in either accepted database function. The upgrade path would be a
separately governed forward migration or orchestration boundary, never a
silent expansion here.

The decision workflow and task-message evidence are provisional
pre-deployment authority. They may authorize repository implementation in one
named draft pull request only. They never authorize deployment, production
operation, release, current/default promotion, production access, or a
security waiver. Before deployment they must be replaced by an independently
human-controlled and independently verifiable approval or signing system.

## 13. Traceability and verification

| ID | Owning code | Negative evidence | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `OVC-001` | Command adapter | Every argument and malformed conninfo rejected | No connection before complete validation | Focused CLI tests |
| `OVC-002` | Runner and existing public functions | Wrong-role live invocation and forbidden SQL inspection | Exact two-query maximum on one route | Seam tests plus PostgreSQL role test |
| `OVC-003` | Runner state machine and database observer | Two closeable buckets, empty database, and a paused real runner followed by a controlled test-only close | Oldest only; zero close/commit on empty; the resumed runner acknowledges the one committed event identity | Live focused tests |
| `OVC-004` | Connection composition and idle-state gate | Hostile conninfo and active returned connection | One connect call, fixed options, `READ_COMMITTED` | Public runner-seam tests |
| `OVC-005` | Explicit transaction and result validators | Missing, duplicate, or malformed rows | Same transaction, pre-render, one explicit commit | Seam and live tests |
| `OVC-006` | Existing database functions | Writer race, wrong pair, active and never-overflowed bucket | Barrier, high-water, count posture remain database-owned | Existing live overflow suites |
| `OVC-007` | Production runner state machine and no-catch-all command adapter | Pre-commit refusal/transport matrix, two distinct commit exceptions, and unexpected runner exception | Exact exits `1`/`3`; exit `4` only from commit; nonconforming seam remains incomplete | Deterministic state- and adapter-seam tests |
| `OVC-008` | Renderer and CLI | Canary DSN/error, malformed result carriers, diagnostic short write, and flush failure | Exact byte reports and exit-paired diagnostics; UTC timestamp/UUID forms; no count | Byte-level protocol tests |
| `OVC-009` | CLI reporting and cleanup order | Short write, flush failure, close failure | Exit `5`; cleanup cannot downgrade known result | Output-sink tests |
| `OVC-010` | Deployment placement | Forbidden import edge and path diff | Kernel and independent authorities unchanged | Architecture and path checks |
| `OVC-011` | README and command surface | Search for scheduler/readiness/claim drift and missing `COUNT_UNKNOWN` precedence | One-shot claim-limited documentation with ambiguity-before-closure ordering | Documentation assertions |

### 13.1 Phase A verification gates

Before the version-2 live decision card, the exact amendment head must pass:

```text
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

The semantic review scope is the RFC amendment, while the exact pull-request
head may also carry the separately authorized meaning-preserving binary-stderr
correction. The exact head must receive one full Phase A review against this
contract. Every demonstrated in-scope Blocker must be corrected and the
affected invariants re-reviewed before a version-2 live card is shown.

### 13.2 Phase B verification gates

If later approved, the final exact implementation head must pass:

```text
.venv/bin/pytest -q kernel/tests/test_security_audit_overflow.py
.venv/bin/pytest -q kernel/tests/test_postgresql_audit_operations.py -k overflow
.venv/bin/pytest -q kernel/tests/test_postgresql_audit_migration.py -k overflow
.venv/bin/pytest -q kernel/tests/test_rewrite_architecture.py
.venv/bin/ruff check deployment/postgresql/security_audit_overflow.py deployment/postgresql/run_security_audit_overflow.py kernel/tests/test_security_audit_overflow.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

PostgreSQL-backed skips are reported as skips and never presented as passing
evidence. The canonical test-node inventory must be regenerated to contain
every collected test in the new module.

Before merge, the AI must also:

1. compare every path changed from the reviewed base through exact PR head
   against section 11.1's exact technical allowlist;
2. verify that the allowlist is a subset of the live decision card's maximum
   path envelope;
3. reject any path or subset failure;
4. post the compact PR scope report required by `AGENTS.md` with stable
   decision, card, approval, and pull-request references;
5. recheck the exact head, required tests, review result, live task evidence,
   and absence of later cancellation; and
6. run `git diff --check` after the final change.

## 14. Open decisions and review disposition

### 14.1 Open material decisions

None inside the proposed version-2 contract. The amendment replaces an
unreachable simultaneous-two-runner evidence requirement with a deterministic
paused-runner interleaving that exercises one real provisioned control-login
connection and one controlled test-only closer. It does not change the
database authority, production connection limit, timeouts, runner behavior,
idempotence claim, permitted effects, or primary trust boundary.

### 14.2 Review disposition

- **Earlier review history:** exact head
  `ba2419d8dd0a94080fe28123dcc06ebf401c61d2` exposed report-encoding and
  adapter-classification gaps; correction head
  `26090478164005f3924c096323b52e6d2a1a4212` received a focused pass.
- **Latest formal Phase A review:** exact head
  `21c98c4f3f984a76d16cb80608471121135be80f` superseded the earlier
  conversational disposition and demonstrated two remaining Blockers: an
  adapter catch-all could invent commit ambiguity, and the pre-commit
  state-to-exit plus diagnostic-byte protocol was incomplete. This revision
  removes the catch-all, reserves exit `4` for explicit `commit()` exceptions,
  fixes the complete exit `1`/`3` state classification, freezes all diagnostic
  bytes, and incorporates the idempotent-acknowledgement and `COUNT_UNKNOWN`
  documentation clarifications without changing authority, effects, paths, or
  the primary boundary.
- **Focused Phase A re-review:** exact head
  `ff1ed57d7c6edc4fa9797b3144fb38ef7fc9f816` passed `OVC-003`,
  `OVC-007`, `OVC-008`, `OVC-009`, and `OVC-011` with no remaining
  in-scope Phase A Blocker.
- **Blockers:** none at approval recognition; merge remains conditioned on
  every exact-head implementation, verification, review, and scope gate.
- **Follow-ups:** the separate issue #192 boundaries in section 11.5.
- **Preferences:** both latest review preferences are incorporated in this
  Phase A RFC revision. The later traceback-documentation wording suggestion
  remains a non-blocking parked Preference and is not added after approval.
- **Hosted conformance:** red retained-native-evidence reverification is an
  out-of-boundary pre-merge prerequisite and does not authorize a CI change in
  this pull request.
- **Post-implementation exact-head review:** exact head
  `8d1b3b5cfa2549e16d079c4f5b0e8a5dd072e878` demonstrated two Phase B
  Blockers. First, the adapter used text stderr even though `OVC-008` freezes
  exact diagnostic bytes. The correction converts all diagnostics and both
  output sinks to binary without changing the approved protocol. Second, the
  mandatory simultaneous-two-runner evidence bypassed the provisioned
  control login's `CONNECTION LIMIT 1` and could fail nondeterministically
  under the fixed lock timeout. This version-2 amendment retains the already
  present paused-runner live evidence and removes the unreachable two-runner
  production claim without widening credentials, connection limits, or
  timeouts.
- **Current Blockers:** the binary-stderr correction requires exact-head
  re-review. Removing the simultaneous-two-runner test and regenerating the
  inventory are version-2 semantic implementation and remain blocked until a
  complete version-2 card receives the exact approval in section 15.
- **Phase B authority:** the version-1 approval in section 15.1 authorizes the
  meaning-preserving binary-stderr correction. It does not authorize this
  semantic amendment or its version-2 implementation.

The named pull request cannot merge until the version-2 amendment passes
exact-head review, a complete live version-2 card receives exact user
approval, the authorized semantic implementation is completed, and
`OVC-001` through `OVC-011` pass with no demonstrated in-scope Blocker. New
ideas, Preferences, and non-blocking hardening remain follow-ups.

## 15. Phase A approval boundary

This RFC grants no Phase B authority by authorship, commit, push, review, or
GitHub activity. After this contract is bound to one draft pull request and
reviewed at its exact head, the AI must display one complete live decision card
in the same Codex task.

The complete version-2 card must state the decision identity and version, problem,
recommended decision, primary trust boundary, authority map, primary risk and
bound, permitted effects, non-effects, decision-level invariants, maximum path
envelope, named draft pull request, verification gates, reapproval triggers,
provisional posture, and this exact approval form:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-OVERFLOW-CLOSURE-EXECUTION-001 version 2.
```

Only the exact entire text of a later task-user message matching that sentence
can authorize Phase B. The original card and approval must remain directly
retrievable with stable task-item references and correct role and order.
Generic approval, GitHub activity, credentials, AI or tool messages,
delegation, another task, or a summary of lost items never supplies approval.

A valid approval binds only the named draft pull request and the card's path
envelope. It authorizes no database operation, deployment, production access,
release, current/default promotion, issue #176 work, or production security
waiver.

### 15.1 Historical version-1 AI-attested approval evidence

- **Task:** `codex-task:019ff570-c253-7d02-bbda-1ad8f4143f00`
- **Live card:**
  `codex-task:019ff570-c253-7d02-bbda-1ad8f4143f00#item-640`
- **Approval:**
  `codex-task:019ff570-c253-7d02-bbda-1ad8f4143f00#item-641`
- **Exact approval sentence:**
  `I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-OVERFLOW-CLOSURE-EXECUTION-001 version 1.`
- **Observed role and order:** the assistant-authored complete version-1 live
  card was directly followed in the same task by the task user's exact entire-
  message approval. No later cancellation preceded Phase B implementation.
- **Named pull request:** `https://github.com/samovers/OFARM2/pull/311`
- **Exact reviewed Phase A head:**
  `ff1ed57d7c6edc4fa9797b3144fb38ef7fc9f816`
- **Review evidence:** focused exact-head PASS review
  `https://github.com/samovers/OFARM2/pull/311#pullrequestreview-4936596045`.
- **Evidence limitation:** the task messages remain authority; this record is
  AI-attested evidence only. The authority is provisional repository-
  development authority and grants no deployment or production authority.
  Version 1 does not authorize the version-2 semantic amendment or removal of
  the simultaneous-two-runner evidence node.

### 15.2 Version-2 Phase B execution boundary

Version-2 Phase B authority has not been granted. Only a later task-user
message whose entire text exactly matches the version-2 sentence in section
15, after a complete live version-2 card at the reviewed exact head, can
authorize the semantic test removal and mechanical inventory regeneration.
If granted, that approval authorizes only in-envelope repository
implementation, tests, documentation, review handling, commits, pushes, and
merge in the named pull request after every gate passes. It authorizes no
database operation, deployment, release, production access, current/default
promotion, or production security waiver.
