# OFARM Security-Audit Overflow Closure Execution — Phase A Contract v0.1

**Status:** proposed in draft pull request #311; Phase B implementation,
deployment, and production operation are not authorized

**Draft implementation pull request:**
`https://github.com/samovers/OFARM2/pull/311`

**Contract identity:**
`ofarm2.security-audit-overflow-closure-execution.v0.1`

**Decision identity:**
`ISSUE192-SECURITY-AUDIT-OVERFLOW-CLOSURE-EXECUTION-001`, proposed version `1`

**Issue:** #192

**Reviewed base:** `9c12c115bd29d9889234edd9e4c84377d9e332f8`

**Primary trust boundary:** isolated security-audit overflow-closure execution

**Phase A review-head boundary:** this RFC only

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

A rollback or transport failure cannot create durable overflow effects
because no write or commit was submitted. It is a closed unavailable or
refused outcome, never commit ambiguity.

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

The complete success report is rendered before `COMMITTING`. Any observation,
close, shape, or rendering failure before that state triggers best-effort
rollback and close. `commit()` is never called.

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

Failure diagnostics are fixed ASCII lines with no raw exception, DSN,
credential, database result, bucket, timestamp, UUID, tenant, principal,
request, route, or correlation value.

The exact diagnostic lines are:

```text
security-audit overflow closure was refused
security-audit overflow closure command is invalid
security-audit overflow closure is unavailable; no commit was sent
security-audit overflow closure outcome is unknown; do not retry automatically
security-audit overflow closure result reporting failed; do not retry automatically
```

Closed terminal exits are:

- `0`: empty observation was rolled back normally, or closure committed and
  the complete report was written and flushed;
- `1`: a returned route or transaction was refused before commit ambiguity;
- `2`: arguments or conninfo configuration were invalid;
- `3`: the route was unavailable and no commit was sent;
- `4`: closure commit outcome is unknown; and
- `5`: a terminal result existed but report write or flush failed.

The command adapter maps any unexpected ordinary `Exception` escaping the
runner to the same fixed exit-`4` unknown protocol. It never guesses which
internal state raised the exception, prints the exception, or retries. A
`BaseException` is not converted; it may leave no terminal protocol and is
operationally unknown after `CLOSE_SUBMITTED`.

Operators and automation must not retry exit `4`, exit `5`, or an incomplete
process protocol automatically. A later invocation does not reconcile an
earlier bucket; it asks the database for the then-oldest closeable bucket and
could close a different one.

## 7. Invariants and acceptance criteria

| ID | Falsifiable invariant |
| --- | --- |
| `OVC-001` | Empty `argv` and one syntactically valid, nonblank audit-control conninfo are the only caller inputs that can reach a connection. No bucket, producer, component, count, timestamp, limit, role, or retry selector is accepted. |
| `OVC-002` | The runner invokes only the existing observer and, after exactly one valid nonempty result, the existing close function through one returned connection. It uses no table read, generic SQL, alternate role, `SET ROLE`, tenant connection, or fallback. |
| `OVC-003` | One invocation observes at most one database-selected oldest closeable bucket and closes at most that exact bucket. An empty observation submits no close and no commit. |
| `OVC-004` | One invocation makes exactly one `psycopg.connect` call, begins from an open idle non-autocommit connection, runs at `READ_COMMITTED`, and makes no automatic retry. Code-owned connection parameters override matching conninfo settings without claiming a global deadline. |
| `OVC-005` | Observation and close occur in the same explicit transaction. A closure success requires one valid result, complete pre-rendering, and normal return from explicit `commit()` with `synchronous_commit=on`. |
| `OVC-006` | PostgreSQL alone decides closeability, ordering, count posture, writer fencing, high-water, receipts, interval, and maintenance-event values. Client validation cannot widen or replace that authority. |
| `OVC-007` | A failure before `COMMITTING` never becomes commit ambiguity. Every controlled `commit()` exception is `OUTCOME_UNKNOWN`, exposes no closure result, and triggers no retry or second credential. The adapter conservatively maps any unexpected ordinary runner exception to the same fixed unknown protocol. |
| `OVC-008` | Output is exactly one of the two fixed canonical JSON forms and contains only the fixed schema/outcome plus the six named validated closure identity fields when applicable. It contains no count claim, event payload, tenant, Party, actor, principal, request, credential, route, correlation value, DSN, or raw exception detail. |
| `OVC-009` | A terminal database/no-bucket result followed by report failure produces exit `5`, never a false successful report or a database retry. Post-terminal cleanup failure cannot downgrade the known result. |
| `OVC-010` | The implementation remains in `deployment/postgresql`; Kernel production composition, audit-health/readiness, gap handling, and every independent authority remain unchanged. |
| `OVC-011` | The command makes no scheduler, deadline, lossless delivery, exact-count, dynamic-readiness, external-clock, deployment, or production-operation claim. |

## 8. Production-reachable negative cases

| ID | Counterexample and required result |
| --- | --- |
| `OVC-001` | Invoke with `-h`, `--help`, `--bucket`, a producer, a timestamp, `--`, or any positional token. Exit `2`; no connection call. Supply blank or malformed conninfo with the same result. |
| `OVC-002` | Supply a reader, retention, producer, readiness, application, or tenant DSN. The public observer refuses through its exact `session_user` rule; the runner performs no fallback or close. |
| `OVC-003` | Seed two closeable overflow buckets in the live isolated audit fixture. One run closes only the database-ordered oldest bucket and leaves the second observable. Run with no bucket and prove no close query or commit. |
| `OVC-004` | Put `connect_timeout=0` and timeout-disabling `options` in valid conninfo. The supported connection seam observes exactly one connect call with code-owned overrides. Return an already-active connection and prove both functions and commit remain untouched. |
| `OVC-005` | Return a valid bucket, then zero, two, nil-UUID, naive-time, or retention-inconsistent close rows through the public runner seam. The runner rolls back and never calls commit. |
| `OVC-006` | Race an admitted writer and closure in the existing live PostgreSQL test. The writer barrier and high-water prevent premature close or bucket recreation; the runner introduces no alternate decision. |
| `OVC-006` | Set the observed database bucket to a never-overflowed, active, malformed, or wrong-pair value through the supported result seam. Client validation or the close function refuses; no marker commits. |
| `OVC-007` | Return one valid close result, pre-render it, then make `commit()` raise both a class-08 `OperationalError` and a different Psycopg server exception in separate tests. Exit `4`; no output fields, retry, or fallback. Make a stub runner raise an unexpected canary-bearing `RuntimeError`; the adapter emits the same fixed exit-`4` line without the canary. |
| `OVC-008` | Cause authentication failure with canaries in the DSN and raw exception. Stdout remains empty and stderr is only the fixed diagnostic. Compare both success report forms byte-for-byte, including exact keys, UTC microseconds, UUID spelling, sort order, separators, and final LF; prove no count field exists. |
| `OVC-009` | After a normal no-bucket rollback or acknowledged close, make stdout short-write or flush fail. Exit `5`; no second database attempt. Make post-terminal close fail and prove the known result remains reportable. |
| `OVC-010` | Architecture checks prove no Kernel production module imports the operational runner and every forbidden path remains unchanged. |
| `OVC-011` | Inspect the command and README. They provide one-shot operation only and expressly disclaim scheduling, gap recovery, readiness, deployment, and exact-count claims. |

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
- exit-code mapping;
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
| `OVC-003` | Runner state machine and database observer | Two closeable buckets and empty database | Oldest only; zero close/commit on empty | Live focused tests |
| `OVC-004` | Connection composition and idle-state gate | Hostile conninfo and active returned connection | One connect call, fixed options, `READ_COMMITTED` | Public runner-seam tests |
| `OVC-005` | Explicit transaction and result validators | Missing, duplicate, or malformed rows | Same transaction, pre-render, one explicit commit | Seam and live tests |
| `OVC-006` | Existing database functions | Writer race, wrong pair, active and never-overflowed bucket | Barrier, high-water, count posture remain database-owned | Existing live overflow suites |
| `OVC-007` | Explicit `COMMITTING` state and command adapter | Two distinct commit exceptions plus unexpected runner exception | Exit `4`, no result, detail, or retry | Deterministic commit- and adapter-seam tests |
| `OVC-008` | Renderer and CLI | Canary DSN/error plus malformed result carriers | Exact byte reports, UTC timestamp/UUID forms, and fixed diagnostics without count | Byte-level protocol tests |
| `OVC-009` | CLI reporting and cleanup order | Short write, flush failure, close failure | Exit `5`; cleanup cannot downgrade known result | Output-sink tests |
| `OVC-010` | Deployment placement | Forbidden import edge and path diff | Kernel and independent authorities unchanged | Architecture and path checks |
| `OVC-011` | README and command surface | Search for scheduler/readiness/claim drift | One-shot claim-limited documentation | Documentation assertions |

### 13.1 Phase A verification gates

Before the live decision card, the RFC-only exact head must pass:

```text
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

The exact head must receive one full Phase A review against this contract.
Every demonstrated in-scope Blocker must be corrected and the affected
invariants re-reviewed before a live card is shown.

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

None. The database already fixes bucket selection, pair identity, interval,
count posture, writer ordering, idempotence, event identity, and retention.
The command fixes the credential, one-bucket bound, transaction, report, and
failure protocol instead of exposing policy inputs.

### 14.2 Review disposition

- **Full Phase A review:** exact head
  `ba2419d8dd0a94080fe28123dcc06ebf401c61d2` found two in-scope gaps: the
  closure report encoding was not fully fixed, and an unexpected ordinary
  runner exception lacked a safe adapter mapping. This revision fixes both
  affected `OVC-007`/`OVC-008` contracts without changing authority, effects,
  paths, or the primary boundary. Focused re-review is pending.
- **Blockers:** none outside the two corrected findings; merge remains
  conditioned on focused re-review and every later Phase B gate.
- **Follow-ups:** the separate issue #192 boundaries in section 11.5.
- **Preferences:** none.

Once `OVC-001` through `OVC-011` pass and no demonstrated in-scope Blocker
remains, the approved workflow permits merging the named pull request. New
ideas, Preferences, and non-blocking hardening remain follow-ups.

## 15. Phase A approval boundary

This RFC grants no Phase B authority by authorship, commit, push, review, or
GitHub activity. After this contract is bound to one draft pull request and
reviewed at its exact head, the AI must display one complete live decision card
in the same Codex task.

The complete card must state the decision identity and version, problem,
recommended decision, primary trust boundary, authority map, primary risk and
bound, permitted effects, non-effects, decision-level invariants, maximum path
envelope, named draft pull request, verification gates, reapproval triggers,
provisional posture, and this exact approval form:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-OVERFLOW-CLOSURE-EXECUTION-001 version 1.
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
