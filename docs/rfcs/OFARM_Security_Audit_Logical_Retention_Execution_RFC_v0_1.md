# OFARM Security-Audit Logical Retention Execution — Phase A Contract v0.1

**Status:** proposed; Phase B is not authorized; the implementation draft pull
request will be assigned after the first contract-only commit and before any
live decision card is shown

**Contract identity:**
`ofarm2.security-audit-logical-retention-execution.v0.1`

**Decision identity:**
`ISSUE192-SECURITY-AUDIT-LOGICAL-RETENTION-EXECUTION-001`, proposed version `1`

**Issue:** #192

**Reviewed base:** `c33778c46c09141a624b97db4f9a69cfb527f645`

**Primary trust boundary:** isolated security-audit logical retention execution

**Phase A review-head boundary:** this RFC only

**Final pull request boundary:** this RFC, one deployment-layer runner, one
fixed command adapter, one focused test module, minimal operator documentation,
and the mechanically regenerated test inventory only

## 1. Problem and goal

The accepted security-audit database already owns logical retention, but
current `main` has no supported production command that invokes it.

This task establishes one bounded, one-shot command that:

- uses the isolated retention route;
- invokes the existing zero-argument PostgreSQL function exactly once;
- accepts no cutoff, identifiers, cursor, or batch size;
- acknowledges success only after an explicit `commit()` returns normally;
- reports every controlled commit exception as an unknown outcome; and
- never retries automatically.

The existing function remains the sole destructive-policy authority:

```sql
SELECT *
FROM ofarm_security.purge_expired_operational_security_events()
```

It owns the database-observed cutoff, victim selection and ordering, the
1,024-row event-deletion ceiling, overflow-receipt and quota cleanup, exact
retention identity, and atomic `AUDIT_RETENTION` event.

This task advances issue #192's logical/query-visible retention criterion. It
does not establish an autonomous schedule or complete all retention operations.

## 2. Learning value

The slice proves that irreversible audit deletion can be operated without
transferring cutoff, victim-selection, batch-size, cleanup, or maintenance-event
authority out of PostgreSQL. It also establishes an honest terminal protocol
for a destructive, non-idempotent transaction whose commit acknowledgement can
be lost.

## 3. Non-goals

This pull request does not change or add:

- migrations, functions, relations, database roles, grants, or provisioning;
- Kernel production code, application composition, or `RuntimeConfig`;
- a scheduler, daemon, service, loop, or drain-until-empty behavior;
- dynamic audit health or readiness;
- gap/overflow, HMAC custody, reader, export, break-glass, or store-loss
  operations;
- reconciliation through another audit credential;
- physical erasure, vacuum, WAL or media sanitization, legal hold, backup,
  replica, or CDC;
- tenant storage, application pools, telemetry, ordinary logs, queues, or
  spools;
- issue #172 authentication work or any issue #176 work;
- an absolute network deadline or a new multi-host routing policy;
- deployment activation, production-readiness, autonomous-retention, or
  lossless-retention claims; or
- signal-management infrastructure.

## 4. Trust model

### 4.1 Protected assets

- unexpired operational-security events;
- the database-owned cutoff, victim set, ordering, and 1,024-row ceiling;
- atomic `AUDIT_RETENTION` evidence and its returned count;
- separation from tenant databases, application pools, and other audit roles;
- the retention credential; and
- honest commit and command-report outcomes.

### 4.2 Trusted components

- the accepted issue #174 migrations and provisioning;
- PostgreSQL transaction semantics, database clock, grants, and exact
  `session_user`;
- Psycopg 3.3.4 and libpq;
- the deployment-layer retention runner;
- deployment-controlled routing, service files, DNS, TLS configuration, and
  secret injection; and
- the operating system and Python runtime.

### 4.3 Untrusted actors and inputs

- every command-line token;
- missing, malformed, or whitespace-only conninfo;
- DSN-provided timeout and startup options;
- network availability and commit acknowledgement;
- database result shape until validated;
- output-channel availability;
- invocation timing and frequency; and
- audit volume created by a compromised producer.

A holder of the retention credential may invoke repeatedly, but cannot select
individual rows or alter database retention policy. Preventing theft of that
credential is outside this slice.

### 4.4 Explicitly excluded attacker capabilities

The following are out of scope:

- arbitrary in-process mutation;
- local source substitution;
- compromised dependencies;
- filesystem mutation;
- operator, database-owner, or superuser compromise;
- DNS, service-file, TLS endpoint, operating-system, or database-clock
  compromise; and
- simultaneous failure of stderr, where the process cannot guarantee
  diagnostic delivery.

Ordinary invocation mistakes, malformed configuration, network loss, database
refusal, commit acknowledgement loss, and stdout failure remain in scope.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Cutoff and eligibility | Existing database function and database clock |
| Victims, ordering, and 1,024 ceiling | Existing database function |
| Receipt and quota cleanup | Existing database function |
| Retention identity | Existing grant and exact `session_user` check inside the function |
| Atomic deletion and maintenance event | PostgreSQL transaction |
| Retention duration validation | Existing `RETENTION_SECONDS` constant |
| Maximum returned deletion-count validation | Existing `PURGE_BATCH_ROWS` constant |
| Explicit conninfo input | `OFARM_SECURITY_AUDIT_RETENTION_PG_DSN` |
| Endpoint expansion and selection | Deployment configuration and libpq |
| Runtime startup options | Fixed runner keyword arguments |
| Transaction construction | Idle non-autocommit Psycopg connection plus the fixed function query |
| Transaction finality | Explicit `Connection.commit()` |
| Successful process report | Fixed, pre-rendered JSON protocol |
| Report delivery | Complete stdout write and successful flush |

The named environment variable is not the sole endpoint authority. Unset
connection parameters may come from libpq environment variables or built-in
defaults, while `service=` may expand a service file. Multi-host, DNS, TLS, and
endpoint selection remain deployment route concerns.

The runner validates syntax with `psycopg.conninfo.conninfo_to_dict()`.
Code-supplied keyword parameters override matching conninfo parameters,
including `connect_timeout` and `options`.

No legacy path, alias, direct table DML, alternate credential, compatibility
shim, or automatic retry is preserved or introduced. The audit-ingest client
is not reused because its same-event-ID retry has no safe retention equivalent.

## 6. State machine and ordering

### 6.1 Command and connection validation

Empty `argv` is the only executing command shape. Every token, including `-h`,
`--help`, positional text, `--`, and malformed option syntax, causes exit `2`,
no stdout, one fixed stderr line, and no connection attempt. Human-readable
usage belongs only in `deployment/postgresql/README.md`.

The command then:

1. requires a non-empty, non-whitespace DSN;
2. validates it with Psycopg conninfo parsing;
3. makes exactly one call to `psycopg.connect`;
4. receives and uses at most one returned backend connection;
5. permits libpq to perform multiple host or address attempts inside that one
   call; and
6. uses five seconds per configured host or address attempt, with no global
   network or process deadline.

Code-owned connection arguments are:

- `autocommit=False`;
- `connect_timeout=5`; and
- `options` replacing all DSN-provided startup options with:
  - `statement_timeout=15000`;
  - `lock_timeout=500`;
  - `idle_in_transaction_session_timeout=10000`;
  - `transaction_timeout=30000`; and
  - `synchronous_commit=on`.

These server-side settings do not claim to bound DNS resolution, every TCP
operation, output writes, or total process wall time.

### 6.2 Exact transaction construction

Before any SQL, the runner requires that the returned connection:

- is open;
- has `autocommit is False`; and
- reports `psycopg.pq.TransactionStatus.IDLE`.

Any other returned connection state is refused before the retention function
or `commit()` is called.

While the connection remains idle, the runner sets its isolation level through
the Psycopg connection API to `psycopg.IsolationLevel.READ_COMMITTED`.

The implementation must not:

- use the connection as a context manager;
- use `connection.transaction()`;
- use any other transaction-managing context; or
- send a separate `BEGIN`, identity query, readiness query, or session-policy
  query.

The fixed retention-function query is the first SQL and starts the one implicit
transaction. That transaction is terminated only by explicit `rollback()` or
explicit `commit()`. Closing an open transaction without a commit causes
PostgreSQL to discard it.

### 6.3 Transaction states

```text
NOT_SUBMITTED
    -> SUBMITTED
    -> RESULT_OBSERVED
    -> COMMITTING
    -> ACKNOWLEDGED
    -> REPORTED
```

Ordering is fixed:

1. Enter `SUBMITTED` immediately before executing the exact function query.
2. Fetch exactly one row and prove there is no second row.
3. Validate exactly five fields:
   - timezone-aware cutoff;
   - `type(deleted_count) is int`;
   - `0 <= deleted_count <= PURGE_BATCH_ROWS`;
   - non-nil UUID retention-event identity;
   - timezone-aware event and purge times; and
   - `purge_after == observed_at + timedelta(seconds=RETENTION_SECONDS)`.
4. Enter `RESULT_OBSERVED`.
5. Normalize every timestamp to UTC.
6. Pre-render the complete success JSON bytes, including the trailing newline.
7. Enter `COMMITTING` immediately before calling `commit()`.
8. Enter `ACKNOWLEDGED` only when `commit()` returns normally.
9. Close the connection. A cleanup exception after `ACKNOWLEDGED` is suppressed
   and cannot change the database outcome or turn it into refused or unknown.
10. Write the complete pre-rendered byte sequence to stdout.
11. Require the write operation to return the complete byte count.
12. Flush stdout successfully, then enter `REPORTED` and exit `0`.

### 6.4 Failure classification

| Point of failure | Terminal result |
| --- | --- |
| Invalid arguments or conninfo configuration | Exit `2`, command invalid |
| Connection or transport failure before `SUBMITTED` | Exit `3`, unavailable; no commit sent |
| Invalid returned connection state | Exit `1`, refused; no function or commit call |
| Deterministic SQL refusal before `COMMITTING` | Exit `1`, refused |
| Invalid result or pre-render failure before `COMMITTING` | Explicit rollback where possible, then exit `1` |
| Transport loss after submission but before `COMMITTING` | Exit `3`, unavailable; no commit sent |
| Any `Exception` raised from `commit()` | Exit `4`, outcome unknown |
| Normal return from `commit()` | `ACKNOWLEDGED` |
| Cleanup failure after `ACKNOWLEDGED` | Suppressed; acknowledged database outcome is unchanged |
| Incomplete stdout write or failed flush after `ACKNOWLEDGED` | Exit `5`, committed but reporting failed |
| Complete stdout write and flush after `ACKNOWLEDGED` | Exit `0`, acknowledged and reported |

There is no commit-time SQLSTATE or exception-class allowlist. Once the runner
enters `COMMITTING`, normal return from `commit()` is the only controlled path
to `ACKNOWLEDGED`. Every caught exception from `commit()`, including a class-08
`OperationalError` or a different Psycopg server exception, becomes
`OUTCOME_UNKNOWN`.

`KeyboardInterrupt`, forced process termination, container shutdown, and other
termination outside the command's controlled exception protocol require no new
signal-management infrastructure. Any invocation that terminates without one
complete declared terminal protocol is operationally `OUTCOME_UNKNOWN` and
must not be retried automatically.

Rollback or cleanup failures before `COMMITTING` cannot create commit ambiguity
because this command has not granted `commit()` authority. They expose no
retention result and cannot cause a retry.

### 6.5 Forbidden transitions

- `OUTCOME_UNKNOWN -> SUBMITTED`;
- acknowledged-reporting failure to a second database attempt;
- success output before `ACKNOWLEDGED`;
- exposing validated result fields from an unknown transaction;
- a second function submission in one invocation;
- a fallback connection or role;
- a caller-supplied cutoff, victim, cursor, limit, or event identity; and
- treating exit `4`, exit `5`, or an incomplete terminal protocol as
  automatically retryable.

A later independent invocation is a separately authorized new batch, not a
retry of the ambiguous transaction.

## 7. Complete command protocol

### 7.1 Success

Exit `0` writes exactly one ASCII JSON line to stdout:

```json
{"cutoff":"2026-08-12T09:10:11.123456Z","deletedCount":1024,"observedAt":"2026-08-12T09:10:11.234567Z","outcome":"ACKNOWLEDGED","purgeAfter":"2026-09-11T09:10:11.234567Z","retentionEventId":"11111111-1111-4111-8111-111111111111"}
```

The encoding rules are:

- the exact six keys shown above;
- `outcome` is exactly `ACKNOWLEDGED`;
- keys sorted lexicographically;
- compact separators `,` and `:`;
- ASCII bytes;
- exactly one trailing newline;
- canonical lowercase UUID text;
- UTC timestamps ending in `Z`; and
- exactly six fractional-second digits.

No complete stdout report is valid unless the process exits `0`. Consumers must
discard any partial stdout from a nonzero exit.

### 7.2 Closed failures

| Exit | Exact stderr line |
| --- | --- |
| `1` | `security-audit retention was refused\n` |
| `2` | `security-audit retention command is invalid\n` |
| `3` | `security-audit retention is unavailable; no commit was sent\n` |
| `4` | `security-audit retention outcome is unknown; do not retry automatically\n` |
| `5` | `security-audit retention committed but reporting failed; do not retry automatically\n` |

Exits `1` through `5` do not deliberately write success data to stdout. No
line interpolates exception text, SQLSTATE, DSN, host, username, function
argument, or database diagnostic. A partial stdout write may precede exit `5`;
the nonzero exit makes that partial report invalid.

Failure of the fixed stderr channel itself is excluded from the command's
guarantee and therefore lacks a complete terminal protocol. Operationally it
must be treated as unknown and must not trigger automatic retry.

## 8. Invariants and acceptance criteria

| ID | Invariant |
| --- | --- |
| `RET-001` | The supported command accepts no arguments and cannot influence cutoff, victims, ordering, cleanup, event contents, or batch size. |
| `RET-002` | The runner invokes only the existing zero-argument function over the retention route, with no alternate role, `SET ROLE`, tenant connection, application pool, direct DML, or fallback. |
| `RET-003` | Every acknowledged invocation is one atomic transaction: no unexpired event is deleted, no more than `PURGE_BATCH_ROWS` event rows are deleted, and the matching maintenance event commits with the returned cutoff and count. |
| `RET-004` | One invocation makes exactly one `psycopg.connect` call, uses at most one returned backend connection, begins from an open idle non-autocommit state, submits the function once, and makes no retry. Code-owned connection parameters override matching DSN settings without claiming a global network deadline. |
| `RET-005` | The fixed function query starts the only transaction at `READ_COMMITTED`. No connection or transaction context may hide its boundary. Success requires exactly one valid result, successful pre-rendering, and normal return from explicit `commit()`. |
| `RET-006` | A failure before `COMMITTING` is never called commit ambiguity. Every controlled `commit()` exception is `OUTCOME_UNKNOWN`, exposes no result, and causes no retry. Any invocation lacking a complete terminal protocol is operationally unknown. |
| `RET-007` | Output contains only the five validated retention-result fields and fixed outcome token. It contains no event payload, pre-tenant failure record, tenant, Party, actor, correlation value, DSN, credential, or raw exception detail. |
| `RET-008` | Acknowledged commit followed by reporting failure produces exit `5`, never a false uncommitted or unknown database outcome, and must not trigger automatic retry. Post-commit cleanup failure cannot downgrade acknowledgement. |
| `RET-009` | The operational implementation remains in `deployment/postgresql`; production Kernel composition and import direction do not change. |
| `RET-010` | The command makes no scheduling, physical-erasure, readiness, continuity, deployment, or lossless-retention claim. |

## 9. Production-reachable negative cases

| ID | Counterexample and required result |
| --- | --- |
| `RET-001` | Invoke with `-h`, `--help`, `--cutoff`, a positional value, `--`, or any other token. Exit `2`; no connection call. |
| `RET-002` | Supply a control, reader, producer, or application DSN. The database function refuses before destructive work; no fallback occurs. |
| `RET-003` | Seed 1,025 expired rows and one unexpired canary. One run deletes exactly 1,024 expired rows, preserves the canary, and commits one matching retention event. |
| `RET-004` | Put `connect_timeout=0` and timeout-disabling `options` in valid conninfo. The supported connection seam observes exactly one connect call with code-owned overrides. A live conflicting lock proves bounded SQL refusal without a second attempt. |
| `RET-004` | Return a connection already in a transaction from the supported connection-factory seam. The runner refuses before the function or `commit()` is called. |
| `RET-005` | Return zero rows, two rows, a nil UUID, an invalid count, or inconsistent timestamps through the public runner seam. The runner rolls back where possible and never calls `commit()`. |
| `RET-006` | Return one valid row, validate and pre-render it, then make `commit()` raise a class-08 `OperationalError`. Exit `4`; no result fields, retry, or fallback. |
| `RET-006` | Repeat the commit-seam test with a different Psycopg server exception. It has the same exit `4` result; no SQLSTATE allowlist exists. |
| `RET-007` | Cause authentication failure with canaries in the DSN and raw exception. Stdout remains empty and stderr is only the fixed exit-`3` line. Compare success JSON byte-for-byte. |
| `RET-008` | Let `commit()` return normally, then make stdout return a short byte count or make flush fail. Exit `5`; no second database attempt. |
| `RET-008` | Let `commit()` return normally and make connection close fail. The acknowledged result remains eligible for the normal stdout protocol; it never becomes refused or unknown. |
| `RET-009` | Architecture checks prove no deployment production module imports the runner from Kernel and no new Kernel module imports the operational runner. |
| `RET-010` | Invoke while every row is unexpired. The count is zero and rows remain. Documentation states one batch per invocation and disclaims scheduling and physical erasure. |

A live backend-termination test may supplement `RET-006`, but it is not
acceptance evidence for commit ambiguity unless termination occurs at the
explicit commit seam.

## 10. Proposed architecture and smallest change

### 10.1 Production ownership

`deployment/postgresql/security_audit_retention.py` owns:

- one immutable validated retention-result value;
- one acknowledged result carrying its pre-rendered report bytes;
- closed unavailable, refused, and outcome-unknown failures;
- fixed SQL and fixed connection options;
- idle-connection and result validation;
- the explicit transaction and commit state machine; and
- canonical success-report rendering.

`deployment/postgresql/run_security_audit_retention.py` owns:

- exact empty-argument enforcement;
- environment lookup and conninfo validation;
- production Psycopg connection composition;
- exit-code mapping;
- stdout and stderr writes and flushing; and
- post-commit reporting failure.

The runner accepts one constructor-bound connection factory as its supported
production composition seam. It introduces no generic operations framework,
renderer interface, pool, scheduler, mutable registry, optional capability bag,
or `Any`-typed authority object.

The application runtime and `RuntimeConfig` remain unchanged, so the
application never receives the retention credential.

### 10.2 Data flow

```text
fixed DSN environment
        -> conninfo validation
        -> fixed bounded psycopg.connect arguments
        -> one idle non-autocommit connection
        -> exact zero-argument database function
        -> validated immutable result
        -> pre-rendered report
        -> explicit COMMITTING boundary
        -> acknowledged commit
        -> exact command protocol
```

This is the minimum coherent design because the destructive database
transition already exists. The operational module belongs beside PostgreSQL
migration, provisioning, readiness, and audit contracts. `kernel/README.md`
explicitly excludes dynamic audit retention operations from the Kernel.

## 11. Elegance audit

- destructive-policy sources of truth: one;
- destructive transition points: one;
- function submissions per invocation: one;
- explicit commit points: one;
- transaction-managing contexts: zero;
- conninfo inputs: one, without claiming it is all endpoint authority;
- returned result objects: one immutable five-field value;
- success encodings: one;
- retry paths: zero;
- alternate credentials or direct DML paths: zero; and
- new generic abstractions: zero.

`PURGE_BATCH_ROWS` and `RETENTION_SECONDS` are imported rather than duplicated.
Nothing existing needs deletion because no production retention caller exists.
A clean new deployment module is safer than modifying the ingest client, whose
idempotent same-event-ID retry is deliberately incompatible with retention.

## 12. Pull request and approval boundary

### 12.1 Exact technical path allowlist

The final pull request may change exactly these paths:

1. `docs/rfcs/OFARM_Security_Audit_Logical_Retention_Execution_RFC_v0_1.md`
2. `deployment/postgresql/security_audit_retention.py`
3. `deployment/postgresql/run_security_audit_retention.py`
4. `deployment/postgresql/README.md`
5. `kernel/tests/test_security_audit_retention.py`
6. `conformance/review_baseline_test_inventory.json`

The RFC may change after approval only to mark the approved status, append the
compact AI-attested approval evidence required by the governing workflow, and
record meaning-preserving implementation or verification disposition. A
semantic contract change requires a new decision version.

The test inventory is a required mechanical Phase B change because the new test
module necessarily adds collected nodes.

### 12.2 Explicitly unchanged paths and authorities

- `kernel/README.md` and every production Kernel module;
- `kernel/runtime_config.py`;
- `kernel/security_audit_client.py`;
- `kernel/security_audit_runtime.py`;
- `security_audit/migrations/*`;
- `deployment/postgresql/audit_contract.py`;
- `deployment/postgresql/provisioning_specs.py`;
- every issue #176 path; and
- every file outside the exact allowlist.

### 12.3 Dependencies

- reviewed base `c33778c46c09141a624b97db4f9a69cfb527f645`;
- existing issue #174 database authority;
- merged issue #192 foundation;
- no stacked pull request;
- open issue #172 does not block this isolated operation; and
- completed issues #252 and #254 evidence is not recreated.

### 12.4 Reviewer non-requirements

Reviewers must not require a scheduler, readiness, gap/overflow, key
retirement, reader/export, break-glass, store-loss, physical-erasure, or
deployment-activation change from this pull request.

### 12.5 Stop and reapproval conditions

Stop immediately if implementation requires:

- a migration, function, role, grant, or provisioning change;
- a reader or control credential for reconciliation;
- an autonomous scheduler or readiness coupling;
- Kernel runtime composition;
- physical-retention or key-custody authority;
- another pull request;
- any path outside the exact allowlist; or
- a material change to the trust boundary, authority map, permitted effects,
  non-effects, invariant, irreversible behavior, or command protocol.

Those changes require a separate prerequisite, follow-up, or new decision
version. A named draft pull request change also requires a new decision version
and approval.

## 13. Provisional design record

The one-shot technical primitive is not provisional. It remains valid if a
separately governed scheduler invokes it later.

The decision workflow and its task-message evidence are provisional
pre-deployment authority. They authorize repository implementation in the one
named draft pull request only. They do not authorize deployment, production
access, release, current/default promotion, or a production security waiver.
Before deployment they must be replaced by an independently human-controlled
and independently verifiable approval or signing system.

Evidence requiring technical redesign includes inability to identify the
explicit commit boundary, a safe need to retry, a required second credential,
or a demonstrated defect in the accepted database function. The likely upgrade
path would be a separately governed forward migration or reconciliation
boundary, never a silent expansion of this pull request.

## 14. Traceability and verification

| ID | Owning code | Negative evidence | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `RET-001` | Command adapter and existing function | Every argument shape rejected | No connection for nonempty argv | Focused CLI tests |
| `RET-002` | Runner and existing SQL authorization | Wrong-role live invocation | No deletion or event | PostgreSQL test |
| `RET-003` | Existing function and result validator | 1,025 expired rows plus canary | 1,024 ceiling and matching event | Live bounded-retention test |
| `RET-004` | Connection composition and idle-state gate | Hostile conninfo, held lock, already-active transaction | One connect call and one submission | Seam and live timeout tests |
| `RET-005` | Result validator and explicit transaction construction | Missing, duplicate, or malformed rows | No hidden context commit | Public runner-seam tests |
| `RET-006` | Explicit `COMMITTING` state | Two distinct commit exceptions | Exit `4`, no exposed result or retry | Deterministic commit-seam tests |
| `RET-007` | Renderer and CLI | Canary exception and DSN | Exact success and failure bytes | Byte-level protocol tests |
| `RET-008` | CLI reporting and cleanup ordering | Short write, flush failure, close failure | Exit `5` only for report failure; close cannot downgrade | Output-sink and cleanup tests |
| `RET-009` | Deployment placement | Forbidden import edge | Kernel unchanged | Architecture checks |
| `RET-010` | README and database deadline | Early invocation | Zero deletion and claim-limited docs | Live test and documentation assertion |

### 14.1 Phase B verification gates

The package contract check must pass before every commit:

```text
python3 conformance/ofarm_pkg_contract_check.py
```

The final exact head must also pass:

```text
.venv/bin/pytest -q kernel/tests/test_security_audit_retention.py
.venv/bin/pytest -q kernel/tests/test_postgresql_audit_migration.py -k retention
.venv/bin/pytest -q kernel/tests/test_rewrite_architecture.py
.venv/bin/ruff check deployment/postgresql/security_audit_retention.py deployment/postgresql/run_security_audit_retention.py kernel/tests/test_security_audit_retention.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

PostgreSQL-backed skips are reported as skips and never presented as passing
evidence.

Before merge, the AI must also:

1. compare every path changed from the reviewed base through exact PR head
   against section 12.1's exact technical allowlist;
2. verify that the exact allowlist is a subset of the live decision card's
   maximum path envelope;
3. reject any path or subset failure;
4. post the compact PR scope report required by `AGENTS.md` with stable
   decision, card, approval, and PR references;
5. recheck the exact head, required tests, review result, live task evidence,
   and absence of later cancellation; and
6. run `git diff --check` after the final change.

The canonical test-node inventory must be regenerated to contain every
collected test in the new module.

### 14.2 Review disposition

- **Blockers:** this contract must be committed to its draft pull request,
  updated to name that stable PR, reviewed at the exact contract head, and
  presented through the governing decision card before Phase B.
- **Follow-ups:** separate remaining issue #192 boundaries, including external
  cadence and deployment ownership.
- **Preferences:** none.
- **Open material decisions:** none.

Once `RET-001` through `RET-010` pass and no demonstrated in-scope Blocker
remains, the approved workflow permits merging the named pull request. New ideas
and adjacent hardening remain follow-ups.

## 15. Phase A stop

This proposed contract grants no Phase B implementation authority. It stops
before production code, tests, operator-documentation changes, inventory
regeneration, approval recognition, or any database operation.

The next lawful actions are to publish this RFC alone in one draft pull request,
replace the pending PR marker with that stable reference, review the exact
contract head, and display one complete live card for
`ISSUE192-SECURITY-AUDIT-LOGICAL-RETENTION-EXECUTION-001` version `1`.
