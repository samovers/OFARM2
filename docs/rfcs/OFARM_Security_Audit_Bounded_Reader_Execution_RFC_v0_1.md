# OFARM Security-Audit Bounded Reader Execution — Phase A Contract v0.1

**Status:** approved for Phase B repository implementation in draft pull
request #309; deployment and production operation are not authorized

**Draft implementation pull request:**
`https://github.com/samovers/OFARM2/pull/309`

**Contract identity:**
`ofarm2.security-audit-bounded-reader-execution.v0.1`

The contract identity remains `v0.1` through its first approved publication.
Decision version `2` instead records the semantic replacement of a withdrawn
live card; the RFC filename is fixed by the approved path envelope and is not
renamed under this decision.

**Decision identity:**
`ISSUE192-SECURITY-AUDIT-BOUNDED-READER-EXECUTION-001`, approved version `2`

**Issue:** #192

**Reviewed base:** `6db6d75bccad285e37510c3a3a7b74df8990815a`

**Primary trust boundary:** isolated security-audit bounded normal-reader
access execution

**Phase A review-head boundary:** this RFC only

**Final pull request boundary:** this RFC, one deployment-layer reader runner,
one fixed command adapter, one focused test module, minimal operator
documentation, and the mechanically regenerated test inventory only

## 1. Problem and goal

The accepted security-audit database already owns a bounded normal diagnostic
query protocol. Current `main` has no supported production command that first
commits the required `AUDIT_ACCESS` intent through the audit-control credential
and then executes the exactly bound page through the distinct audit-reader
credential.

This task establishes one privileged, one-shot normal reader command that:

- accepts either the newest page or one exact descending-page cursor;
- fixes the normal purpose, exact function identity, 256-row ceiling, and
  1,048,576-byte database ceiling;
- validates the complete command configuration before any connection;
- commits the access intent through an explicit non-autocommit control
  transaction;
- opens the reader route only after that commit is acknowledged;
- invokes the existing bounded query function exactly once;
- validates and buffers the complete bounded result before writing it;
- emits one canonical ASCII JSON report with an optional next cursor; and
- never retries automatically.

The existing database functions remain the sole access-policy authorities:

```sql
SELECT *
FROM ofarm_security.commit_audit_access_intent(
    'OPERATIONAL_DIAGNOSTIC_QUERY_V1',
    'ofarm_security.query_operational_security_events(uuid, timestamptz, uuid, integer, bigint)',
    :cursor_observed_at,
    :cursor_event_id,
    256,
    1048576
)
```

and, only after acknowledged intent commit:

```sql
SELECT *
FROM ofarm_security.query_operational_security_events(
    :access_event_id,
    :cursor_observed_at,
    :cursor_event_id,
    256,
    1048576
)
```

The database continues to own session-user authorization, the event-writer
barrier, database-time cut, persisted MVCC snapshot, five-minute expiry,
non-regressing access-clock observation, exact scope equality, row selection,
ordering, and encoded-byte accounting.

This task advances issue #192 criterion 11 for the normal bounded reader. It
does not establish break-glass export or complete external clock-health
fencing.

## 2. Learning value

The slice proves that privileged audit diagnosis can be operated without table
`SELECT`, `COPY`, a caller-selected access purpose, an unaudited page, or a
combined control-and-reader database identity. It demonstrates that a complete
page can be disclosed only after durable access evidence has committed and
that ambiguous access authorization never becomes permission to read.

## 3. Non-goals

This pull request does not change or add:

- migrations, functions, types, relations, indexes, roles, grants, or
  provisioning;
- the accepted database access protocol, clock authority, retention policy, or
  event-report carrier;
- Kernel production code, application composition, `RuntimeConfig`, `/health`,
  or readiness;
- a web endpoint, daemon, service, scheduler, loop, query session, or
  drain-until-empty operation;
- dynamic audit health, gap recording, overflow closure, HMAC key custody or
  retirement, retention execution, store-loss recovery, or empty recreation;
- export, break-glass login creation, credential grant/revocation, dual
  approval, or cumulative export accounting;
- direct relation reads, generic SQL, arbitrary purpose/function selection,
  caller-selected row or byte ceilings, caller-supplied access-event IDs, or
  reuse of an earlier access intent;
- tenant storage, tenant reconstruction, application pools, support paths,
  telemetry, ordinary logs, queues, files, caches, or spools;
- process-signal management or a guarantee of a terminal protocol after
  uncatchable process termination;
- issue #172 authentication work or any issue #176 work;
- deployment activation, production access, production readiness, wall-clock
  monotonicity evidence, or a security waiver; or
- a guarantee that authorized output cannot be copied after disclosure.

The normal reader is privileged and export-capable within one precommitted
page. Preventing a holder of both credentials from repeatedly authorizing new
pages is not a property of this database protocol.

## 4. Trust model

### 4.1 Protected assets

- unexpired operational-security event reports;
- the requirement for a durable, exactly equal `AUDIT_ACCESS` intent before
  disclosure;
- separation between audit-control and audit-reader credentials;
- the database-owned data cut, visibility snapshot, expiry, cursor, ordering,
  and row/byte ceilings;
- the non-regressing access-clock high-water authority;
- absence of tenant, principal, credential, and raw request data from this
  lane;
- the two conninfo values and every event field returned to the command; and
- honest command outcomes when authorization, query, or report delivery fails.

### 4.2 Trusted components

- the accepted issue #174 migrations, roles, grants, and provisioning;
- PostgreSQL transaction, snapshot, sequence, advisory-lock, database-clock,
  exact `session_user`, and function semantics;
- the checked-in security-audit contract constants;
- Psycopg 3.3.4 and libpq;
- the deployment-layer bounded-reader runner and command adapter;
- deployment-controlled endpoint routing, service files, DNS, TLS
  configuration, secret injection, and output destination; and
- the operating system and Python runtime.

The accepted protocol trusts the database wall clock not to pass an intent
deadline and roll back before any access-protocol observation occurs. This
command does not replace that prerequisite or claim that deployment satisfies
it.

### 4.3 Untrusted actors and inputs

- every command-line token and cursor byte;
- missing, malformed, whitespace-only, or hostile conninfo;
- DSN-provided timeout and startup options;
- network availability and control-commit acknowledgement;
- wrong-role or cross-service route configuration;
- every returned row and result shape until the client validates it;
- stdout and stderr availability, short writes, and flush failures;
- invocation timing and frequency; and
- a compromised producer that can create only its accepted bounded event
  classes.

A holder of only the control credential cannot query. A holder of only the
reader credential cannot create an access intent. A holder of both credentials
is a privileged security operator and can authorize repeated bounded pages;
the database records each new authorization.

### 4.4 Explicitly excluded attacker capabilities

The following are out of scope:

- arbitrary in-process mutation;
- local source substitution;
- compromised dependencies;
- filesystem mutation;
- operating-system, database-owner, superuser, or trusted operator compromise;
- theft of both required database credentials;
- DNS, service-file, TLS endpoint, or database-clock compromise; and
- simultaneous failure of stderr, where the process cannot guarantee a
  diagnostic.

Ordinary invocation mistakes, malformed configuration, wrong credentials,
network loss, database refusal, commit-acknowledgement loss, malformed seam
results, and output failure remain in scope.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Normal access purpose | Existing `QUERY_ACCESS_PURPOSE_IDENTITY` contract constant |
| Exact callable identity | Existing `QUERY_FUNCTION_IDENTITY` contract constant |
| Maximum rows and database-encoded bytes | Existing `QUERY_MAX_ROWS` and `QUERY_MAX_BYTES` contract constants |
| Cursor components | One validated immutable command cursor, or both SQL values `NULL` |
| Control identity | Exact `session_user` check and grant inside `commit_audit_access_intent` |
| Reader identity | Exact `session_user` check and grant inside `query_operational_security_events` |
| Access event ID | Existing database maintenance-event function |
| Data cut and five-minute expiry | Existing access-intent function and database clock |
| Visibility membership | Existing persisted PostgreSQL snapshot plus `pg_visible_in_snapshot` |
| Access-clock serialization and high-water | Existing migration/provisioning-owned wrappers and sequence |
| Intent durability | Explicit control transaction `commit()` acknowledgement |
| Permission to open the reader route | Runner state reached only after acknowledged intent commit |
| Page membership and descending order | Existing bounded query function |
| Report schema, JSON encodings, and fixed diagnostics | This approved contract and fixed runner/adapter constants |
| Successful process report | Complete validated result plus one complete stdout write and flush |
| Next cursor | Last validated row's normalized `(observed_at, event_id)` pair |
| Conninfo input | `OFARM_SECURITY_AUDIT_CONTROL_PG_DSN` and `OFARM_SECURITY_AUDIT_READER_PG_DSN` |
| Endpoint expansion and selection | Deployment configuration and libpq |
| Runtime startup options | Fixed runner keyword arguments |

The named environment variables are not the sole endpoint authorities. Unset
parameters may come from libpq environment variables or built-in defaults, and
`service=` may expand a service file. Multi-host, DNS, TLS, and endpoint
selection remain deployment route concerns.

The command validates both conninfo strings with
`psycopg.conninfo.conninfo_to_dict()` before the first connection. Code-supplied
keyword parameters override matching conninfo parameters, including
`connect_timeout` and `options`.

No legacy path, alias, direct table read, generic query, alternate purpose,
credential fallback, or automatic retry is preserved or introduced. The
control and reader functions remain separate even when both conninfo values
route to the same accepted audit service.

## 6. State machine and ordering

### 6.1 Command validation

The only accepted command shapes are:

```text
[]
```

for the newest page, or:

```text
["--cursor", "<UTC_TIMESTAMP>/<UUID>"]
```

for one older page. Every other token shape, including `-h`, `--help`, `--`,
duplicate flags, additional arguments, or an empty cursor, causes exit `2`, no
stdout, one fixed stderr line, and no connection attempt. Human-readable usage
belongs only in `deployment/postgresql/README.md`.

The cursor is one immutable value. Its canonical external form is:

```text
YYYY-MM-DDTHH:MM:SS.ffffffZ/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

The timestamp must be finite UTC with exactly six fractional digits. The UUID
must be canonical lowercase text and nonzero. The parser rejects equivalent but
noncanonical offsets, missing fractions, uppercase UUID hex, braces, whitespace,
or extra separators. The command never accepts only one cursor component.

Before any connection, the adapter validates the cursor and both complete,
non-whitespace conninfo values. A malformed reader conninfo therefore cannot
cause an access intent to commit first.

### 6.2 Fixed connection posture

Each required route gets at most one `psycopg.connect` call. Libpq may make
multiple host or address attempts inside one call. The five-second connect
timeout is per libpq host or address attempt, not a total command deadline.

Both routes use these fixed client-owned USERSET and output settings, supplied
as one code-owned libpq `options` value that replaces any caller-supplied
conninfo `options` value:

```text
statement_timeout=5000
lock_timeout=500
idle_in_transaction_session_timeout=10000
transaction_timeout=15000
work_mem=1024kB
bytea_output=hex
TimeZone=UTC
DateStyle=ISO,MDY
```

`temp_file_limit=0` is not client-owned startup policy. Provisioning installs
it as an exact database-scoped role default for both non-superuser logins, and
this command neither sends it in startup options nor adds `SET` privilege on
the parameter. A hostile caller therefore cannot replace it through conninfo,
while the command also cannot cause either login to fail by attempting to set
a superuser-scoped parameter.

The control route additionally includes `synchronous_commit=on` in the same
code-owned options value. The control connection must be open,
non-autocommit, idle, and set to `READ COMMITTED` before submission. The reader
connection must be open, autocommit, and idle before its single query. Any
unequal connection posture refuses without a fallback. The production command
adds no identity, readiness, or `SHOW` query to verify provisioned settings.

### 6.3 Access-intent transaction

After complete validation, the runner:

1. opens exactly one control connection;
2. verifies its initial state and selects `READ COMMITTED`;
3. submits the fixed access-intent function exactly once with one bound cursor
   object and the contract constants;
4. fetches exactly one three-field result and rejects a missing or second row;
5. validates a nonzero UUID, finite timezone-aware cut and expiry, and exact
   300-second elapsed duration after UTC normalization;
6. preconstructs the exact reader request from the validated result and the
   same immutable cursor;
7. enters `COMMITTING` immediately before calling `commit()`; and
8. reaches `INTENT_ACKNOWLEDGED` only if `commit()` returns normally.

An exception before the explicit commit call causes a best-effort rollback and
close. No reader connection is opened. An exception from the explicit commit
call makes the access-intent outcome unknown. The runner closes the connection,
does not query, does not retry, and exposes no access event ID.

Normal close failure after acknowledged commit cannot downgrade the already
committed intent or authorize an alternate path.

### 6.4 Bounded query and validation

Only `INTENT_ACKNOWLEDGED` permits the runner to:

1. open exactly one distinct reader connection;
2. verify its autocommit and idle state;
3. submit the exact bounded query once with the acknowledged access event ID,
   the same cursor, and the same fixed ceilings;
4. request at most 257 rows from the client cursor in one fetch call, retain at
   most 256, and refuse if the cursor seam exposes a 257th row;
5. validate the exact 30-field carrier type, fixed policy identities, allowed
   event kind and producer/component shape, UUID and digest lengths, finite
   timestamps, 30-day elapsed retention relation, maintenance extensions,
   descending order, fixed data-cut membership, fixed expiry membership, and
   cursor boundary;
6. normalize timestamps to UTC and bytes to lowercase hexadecimal text;
7. derive a next cursor only from the last validated row; and
8. render the complete canonical report in memory before stdout is touched.

The reader connection is then closed before stdout is touched. Normal close
failure after the one autocommit query has returned and the complete page has
validated cannot change the page, create commit ambiguity, or authorize a
second query; it is suppressed and cannot downgrade the report. A close
attempt never becomes a retry or an alternate route.

The runner does not duplicate row selection, snapshot visibility, access
expiry, or database byte accounting. Validation proves that the trusted
database result fits the accepted carrier and the request's observable bounds;
the database remains the policy authority.

The database function's `LIMIT 256` is the authoritative row bound. A normal
client-side psycopg cursor may have materialized the complete server result
before `fetchmany(257)` returns, so the client fetch is a hostile-seam
validation and not a network or transport bound. No server-side cursor or
second statement is introduced.

Carrier validation derives the event kinds, producer/component pairs, known
HMAC versions, policy identities, access protocols, and their limits from
`SECURITY_AUDIT_CONTRACT`. The active fresh-append reason lists are not treated
as a historical query-membership registry. For a `PRE_TENANT_FAILURE` row, the
validator requires:

- an exact producer/component pair from the contract reason matrix;
- a non-empty closed ASCII `reason` token;
- the contract HMAC domain, a known key version, and an exact 32-byte HMAC; and
- the remaining exact carrier identities and shapes.

The trusted relation constraints and bounded database function remain
authoritative for historical reason membership. The client therefore accepts
and preserves retired immutable reasons that the database can lawfully return,
including authentication `TENANT_PARTY_PIN_REFUSED` and `CAPABILITY_REFUSED`,
and router `SECURITY_ROUTE_REFUSED` and `ACTOR_BINDING_REFUSED`; it does not add
those reasons to the active append contract.

The validator accepts every valid event kind as query data, including an
`AUDIT_ACCESS` row for the separately governed break-glass export protocol if
one later exists. Reading that evidence does not invoke export or grant an
export capability. The validator never silently filters a valid event kind or
invents a narrower access-event vocabulary.

The canonical report is one ASCII JSON line with sorted object keys, no NaN,
compact separators, and one terminal newline. Its exact top-level keys and
values are:

| Key | Exact value |
| --- | --- |
| `schemaVersion` | `"ofarm.security-audit-bounded-query-report.v1"` |
| `outcome` | `"ACKNOWLEDGED"` |
| `accessEventId` | Canonical lowercase nonzero UUID text |
| `dataCut` | Canonical UTC timestamp |
| `expiresAt` | Canonical UTC timestamp exactly 300 elapsed seconds after `dataCut` |
| `purpose` | `"OPERATIONAL_DIAGNOSTIC_QUERY_V1"` |
| `functionIdentity` | The exact accepted query function identity |
| `maxRows` | JSON integer `256` |
| `maxBytes` | JSON integer `1048576` |
| `inputCursor` | The exact canonical input cursor string or JSON `null` |
| `returnedRowCount` | JSON integer from `0` through `256`, equal to the array length |
| `nextCursor` | Cursor derived from the last event, or JSON `null` for an empty array |
| `events` | One ordered array of the exact event objects below |

Every event object contains all 30 keys below. A nullable database field remains
an explicit JSON `null`; no key is omitted.

| Event key | Database field | JSON encoding |
| --- | --- | --- |
| `eventId` | `event_id` | Canonical lowercase nonzero UUID text |
| `observedAt` | `observed_at` | Canonical UTC timestamp |
| `purgeAfter` | `purge_after` | Canonical UTC timestamp |
| `eventKind` | `event_kind` | Closed ASCII text |
| `producer` | `producer` | Closed ASCII text |
| `component` | `component` | Closed ASCII text |
| `reason` | `reason` | Closed ASCII text or `null` |
| `correlationHmacDomain` | `correlation_hmac_domain` | Closed ASCII text or `null` |
| `correlationHmacKeyVersion` | `correlation_hmac_key_version` | JSON integer or `null` |
| `correlationHmacValue` | `correlation_hmac_value` | 64 lowercase hexadecimal characters without a prefix, or `null` |
| `eventFormatIdentity` | `event_format_identity` | Closed ASCII text |
| `redactionPolicyIdentity` | `redaction_policy_identity` | Closed ASCII text |
| `retentionPolicyIdentity` | `retention_policy_identity` | Closed ASCII text |
| `appendInputFingerprint` | `append_input_fingerprint` | 64 lowercase hexadecimal characters without a prefix |
| `accessPurpose` | `access_purpose` | Closed ASCII text or `null` |
| `accessFunctionIdentity` | `access_function_identity` | Closed ASCII text or `null` |
| `accessDataCut` | `access_data_cut` | Canonical UTC timestamp or `null` |
| `accessCursorObservedAt` | `access_cursor_observed_at` | Canonical UTC timestamp or `null` |
| `accessCursorEventId` | `access_cursor_event_id` | Canonical lowercase nonzero UUID text or `null` |
| `accessMaxRows` | `access_max_rows` | JSON integer or `null` |
| `accessMaxBytes` | `access_max_bytes` | Base-10 integer string or `null` |
| `accessExpiresAt` | `access_expires_at` | Canonical UTC timestamp or `null` |
| `retentionCutoff` | `retention_cutoff` | Canonical UTC timestamp or `null` |
| `retentionDeletedCount` | `retention_deleted_count` | Base-10 integer string or `null` |
| `intervalStart` | `interval_start` | Canonical UTC timestamp or `null` |
| `intervalEnd` | `interval_end` | Canonical UTC timestamp or `null` |
| `intervalEventCount` | `interval_event_count` | Base-10 integer string or `null` |
| `intervalCountUnknown` | `interval_count_unknown` | JSON boolean or `null` |
| `affectedProducer` | `affected_producer` | Closed ASCII text or `null` |
| `affectedComponent` | `affected_component` | Closed ASCII text or `null` |

A canonical UTC timestamp has exactly the input cursor timestamp form:
`YYYY-MM-DDTHH:MM:SS.ffffffZ`. All elapsed-time comparisons occur after UTC
normalization. All `int8` event fields use base-10 strings so downstream JSON
consumers cannot silently lose integer precision; `int4` fields remain JSON
integers. Top-level `maxBytes` is fixed command-protocol metadata and remains a
JSON integer because `1048576` is exactly representable. Event-level
`accessMaxBytes` follows the uniform `int8` event-carrier rule and remains a
base-10 string. The deliberate encoding difference is part of schema version
`ofarm.security-audit-bounded-query-report.v1`.

The database's 1,048,576-byte ceiling applies to the sum of its canonical
encoded event rows, not to the complete stdout line. The wrapper, key names,
and explicit conversion can make stdout larger than that number. Output remains
bounded by the fixed database byte ceiling, the 256-row ceiling, and the closed
30-field carrier; this RFC makes no false one-megabyte stdout claim.

The report never contains conninfo, database errors, Python exception text,
visibility snapshots, internal sequence state, or access-clock lock identity.
The report schema version is owned by this command protocol. Changing a key,
value encoding, null posture, ordering rule, or schema identity is a semantic
contract change and requires reapproval.

### 6.5 Terminal command protocol

The process has these closed exits:

| Exit | Meaning | stdout |
| --- | --- | --- |
| `0` | Intent commit acknowledged, exact query completed, and complete report written and flushed | one canonical JSON line |
| `1` | Refused after a control connection was returned but before a commit could become ambiguous | empty |
| `2` | Invalid command, cursor, or conninfo configuration | empty |
| `3` | Control connection factory failed before returning a connection; no commit was sent | empty |
| `4` | Access-intent commit outcome unknown; reader was not opened | empty |
| `5` | Intent was acknowledged, but reader connection, query, result validation, or complete report construction failed | empty |
| `6` | Complete query report existed, but stdout write or flush failed; partial output is possible | empty or partial |

Every controlled failure writes and flushes exactly its corresponding ASCII
line:

In the table, the two source characters `\n` denote exactly one terminal LF
byte (`0x0A`). The backslash and `n` are not emitted; no CR or other trailing
byte is permitted. Each complete diagnostic appears on one physical source
line.

| Exit | Exact stderr |
| --- | --- |
| `1` | `security-audit query was refused\n` |
| `2` | `security-audit query command is invalid\n` |
| `3` | `security-audit query control route is unavailable; no commit was sent\n` |
| `4` | `security-audit query access-intent outcome is unknown; no query was sent; do not retry automatically\n` |
| `5` | `security-audit query intent committed but no complete report is available; do not retry automatically\n` |
| `6` | `security-audit query completed but reporting failed; do not retry automatically\n` |

An unexpected ordinary `Exception` maps according to the state already
reached, never to success. A `BaseException`, uncatchable process termination,
or simultaneous stderr failure may leave an incomplete protocol. An incomplete
process protocol is not evidence of success and is never a reason to retry
automatically.

The production adapter uses `SecurityAuditQueryRunner`, which converts every
ordinary external-step exception to a closed outcome using its internal state.
The adapter deliberately has no catch-all for a nonconforming injected runner:
it cannot observe that runner's state and therefore cannot truthfully claim
either that no query was sent or that an intent committed. Such a programming
seam failure is an incomplete protocol, never success.

The command performs no automatic retry in any state. A later invocation is a
new access act and commits a new access intent. It never accepts an old access
event ID or resumes an interrupted report.

## 7. Invariants and acceptance criteria

### `BRQ-001` — validate all authority inputs before I/O

Only the two exact command shapes execute. The cursor and both conninfo values
must validate before the first connection. Invalid reader configuration cannot
leave a committed control intent.

### `BRQ-002` — one fixed normal access intent

One invocation submits at most one access-intent function call. Purpose,
function identity, cursor, 256-row ceiling, and 1,048,576-byte ceiling are exact
and cannot be widened or replaced by caller input.

### `BRQ-003` — acknowledged intent precedes reader access

No reader connection or query occurs before the explicit control `commit()`
returns normally. Any commit exception produces an unknown outcome and no read.

### `BRQ-004` — database role separation remains authoritative

The control and reader calls use their separate conninfo values and existing
functions. Wrong-role, cross-service, missing-intent, expired-intent, and
unequal-scope cases refuse without direct SQL, another credential, or a
fallback.

### `BRQ-005` — exactly one equal bounded page

After intent acknowledgement, one invocation submits the bounded query at most
once with the acknowledged access event ID and the exact same cursor and
ceilings. The database `LIMIT 256` owns the row bound. One client fetch requests
at most 257 rows to detect a hostile-seam excess, retains and returns at most
256 descending rows inside the fixed cut, expiry, and cursor boundary, and
makes no transport-bound claim.

### `BRQ-006` — carrier and output remain bounded and exact

Every row must match the accepted 30-field event-report carrier and closed
policy shapes before any byte is written. A missing, extra, malformed,
misordered, out-of-cut, expired-at-intent, or cursor-violating row produces no
successful report. Every valid accepted event kind remains readable; client
validation cannot silently filter the result set. In particular, active
fresh-append reason lists cannot reject a valid retired historical reason.

### `BRQ-007` — canonical privileged output only

Success is exactly one canonical ASCII JSON line matching the fixed report
schema. It may contain only the acknowledged access metadata, fixed query
metadata, validated event reports, row count, and derived cursor. Diagnostics
are the exact fixed lines and contain none of those values, conninfo, or
exception text.

### `BRQ-008` — honest terminal outcomes

Exit `0` occurs only after the complete report write and flush. Intent-commit
ambiguity, post-intent query failure, and report-delivery failure remain
distinguishable and never appear as success.

### `BRQ-009` — no retry, resume, or intent reuse

The runner makes at most one control connection, one intent submission, one
control commit call, one reader connection, and one query submission. It never
accepts a caller access-event ID or automatically retries any operation.

### `BRQ-010` — no authority expansion

The implementation changes no database or Kernel authority and adds no export,
break-glass, readiness, recovery, or deployment path. PostgreSQL remains the
sole authorization, cut, expiry, membership, ordering, and byte-limit authority.

### `BRQ-011` — claim-limited clock posture

The command documents the accepted wall-clock prerequisite and makes no claim
that it is externally fenced, production-ready, or safe to deploy where that
prerequisite is unavailable.

## 8. Production-reachable negative cases

| Invariant | Supported entry and counterexample | Required result |
| --- | --- | --- |
| `BRQ-001` | Run the module with `--help`, a partial cursor, a noncanonical timestamp, an uppercase UUID, an empty control DSN, or a malformed reader DSN. | Exit `2`; no connection, stdout, access intent, or leaked input. |
| `BRQ-002` | Supply extra limit or purpose tokens, or hostile DSN startup options. | Tokens refuse; code-owned fixed function arguments and USERSET/output settings cannot be widened, while provisioned `temp_file_limit=0` remains server-owned. |
| `BRQ-003` | Use a control route whose commit acknowledgement is dropped after the commit call begins. | Exit `4`; zero reader connection attempts and zero retry attempts. |
| `BRQ-004` | Point the control DSN at the reader login, the reader DSN at the control login, or the two routes at different accepted audit services. | Existing exact session-user or equal-intent checks refuse; no report or fallback. |
| `BRQ-005` | Request a cursor page while a hostile seam returns a 257th row, a row at or above the cursor, or ascending order. | The single result fetch detects seam excess; post-intent failure emits no successful output and makes no second query. The database `LIMIT`, not the client fetch, owns the row bound. |
| `BRQ-006` | Return valid retired historical reasons `TENANT_PARTY_PIN_REFUSED` for authentication and `SECURITY_ROUTE_REFUSED` for the router; separately return a zero UUID, naive/infinite timestamp, wrong digest length, unknown event kind, bad maintenance extension, row beyond the fixed cut, or row whose `purge_after` is not later than intent expiry. | Both retired-reason rows remain readable and appear unchanged in the canonical report; each malformed or out-of-bound row causes post-intent failure before stdout. |
| `BRQ-007` | Return a carrier that would force a missing key or alternate encoding, then put a recognizable secret in either DSN and force each connection, SQL, validation, and output failure. | Success matches the exact schema; fixed diagnostic bytes never contain the secret, row data, access ID, or exception text. |
| `BRQ-008` | Make stdout short-write or fail on flush after the complete report exists. | Exit `6`; never exit `0`; no retry. |
| `BRQ-009` | Fail control connect, intent execute, control commit, reader connect, reader execute, row fetch, and report write in separate invocations. | Exact call counts remain at most one per permitted step; no resume or old-intent input exists. |
| `BRQ-010` | Invoke the command with only an ingest, retention, readiness, application, or tenant credential. | No direct relation read, alternate function, role assumption, or tenant path succeeds. |
| `BRQ-011` | Run where the external database-clock prerequisite has not been established. | Documentation and command output make no healthy, ready, deployment, or monotonic-clock claim. |

The deterministic connection and output seams are public constructor/adapter
boundaries used to exercise network and sink behavior. Tests do not mutate
private fields or manufacture an in-process authority corruption model.

## 9. Proposed architecture and smallest change

### 9.1 Types and ownership

`deployment/postgresql/security_audit_query.py` will own:

- one immutable `SecurityAuditQueryCursor` containing normalized timestamp and
  event UUID, plus canonical parse/render functions;
- one immutable validated access-intent result;
- one immutable validated event-report value;
- one acknowledged result containing the pre-rendered report bytes;
- closed exception classes for pre-intent refusal/unavailability,
  intent-outcome ambiguity, and acknowledged-intent query failure;
- fixed SQL and connection options; and
- one `SecurityAuditQueryRunner` with an injected connection-factory seam.

`deployment/postgresql/run_security_audit_query.py` will own:

- the two exact environment-variable names;
- exact argv and conninfo validation;
- fixed stderr and exit mapping;
- complete stdout write/flush handling; and
- the executable module entry point.

The runner receives one optional cursor object, never separate mutable cursor
fields. It imports purpose, function, ceilings, policy identities, retention
duration, and access-expiry duration from the accepted contract rather than
duplicating policy values.

### 9.2 Data flow

```text
exact argv + two conninfo values
    -> complete pre-I/O validation
    -> one immutable cursor or newest-page sentinel
    -> exact control connection
    -> fixed access-intent call
    -> validated intent result
    -> explicit COMMITTING boundary
    -> acknowledged intent commit
    -> exact reader connection
    -> exact bounded query
    -> complete validated page
    -> canonical buffered report
    -> one complete stdout write and flush
```

This is the minimum coherent design because the two authoritative database
transitions already exist. The client must orchestrate both to deliver a
functional reader, but it does not absorb either authority. Placing the module
beside PostgreSQL migration, provisioning, readiness, retention, and contract
code honors `kernel/README.md`, which excludes dynamic audit operations from
the Kernel.

### 9.3 Why no smaller slice is honest

A control-only intent command would create access evidence without delivering
the accepted reader capability. A reader-only command would require an
externally supplied access event ID and separate correlated fields, leaving the
authorization ordering and credential handoff unaudited by the supported
operation. Combining the existing control intent and reader query in one
deployment operation is therefore the smallest functional boundary.

Export and break-glass remain separate because they add temporary login
custody, dual approval, cumulative disclosure bounds, structural
incompatibility, and runtime-health effects.

## 10. Elegance audit

- access-purpose sources of truth: one contract constant;
- function-identity sources of truth: one contract constant;
- row/byte ceiling sources of truth: one contract pair;
- cursor objects in the client: one immutable value;
- authoritative access-intent transition points: one database function;
- authoritative query transition points: one database function;
- explicit control commit points: one;
- control and reader connection attempts: at most one each;
- query submissions: at most one;
- automatic retries: zero;
- caller-supplied access IDs, purposes, functions, or ceilings: zero;
- direct relation-read paths: zero;
- success encodings: one; and
- new generic abstractions: zero.

Nothing existing needs deletion because no production reader caller exists.
No compatibility shim is needed. A clean deployment module is safer than
modifying the ingest client, retention runner, or Kernel runtime because each
has a different credential and transaction protocol.

## 11. Pull request and approval boundary

### 11.1 Exact technical path allowlist

The final pull request may change exactly these paths:

1. `docs/rfcs/OFARM_Security_Audit_Bounded_Reader_Execution_RFC_v0_1.md`
2. `deployment/postgresql/security_audit_query.py`
3. `deployment/postgresql/run_security_audit_query.py`
4. `deployment/postgresql/README.md`
5. `kernel/tests/test_security_audit_query.py`
6. `conformance/review_baseline_test_inventory.json`

The RFC may change after approval only to mark approved status, append the
compact AI-attested approval evidence required by the governing workflow, and
record meaning-preserving implementation or verification disposition. A
semantic contract change requires a new decision version.

The inventory is a required mechanical Phase B change because the focused test
module necessarily adds collected nodes.

### 11.2 Explicitly unchanged paths and authorities

- `kernel/README.md` and every production Kernel module;
- `kernel/runtime_config.py`, `kernel/api.py`,
  `kernel/security_audit_client.py`, and `kernel/security_audit_runtime.py`;
- `security_audit/migrations/*`;
- `deployment/postgresql/audit_contract.py`;
- `deployment/postgresql/provisioning.py` and
  `deployment/postgresql/provisioning_specs.py`;
- the retention modules and tests merged through pull requests #307 and #308;
- every issue #176 path; and
- every file outside the exact allowlist.

### 11.3 Dependencies

- reviewed base `6db6d75bccad285e37510c3a3a7b74df8990815a`;
- existing issue #174 database authority;
- merged issue #192 foundations and retention corrections;
- merged test-only prerequisite pull request #310 and no open stacked pull
  request;
- open issue #172 does not block this isolated operation; and
- completed issues #252 and #254 evidence is not recreated.

### 11.4 Reviewer non-requirements

Reviewers must not require a migration, new role, credential provisioning,
Kernel integration, web endpoint, dynamic health/readiness, external clock
fence, gap/overflow controller, HMAC retirement, retention, export,
break-glass, store recovery, deployment activation, or issue #172/#176 change
from this pull request.

### 11.5 Follow-ups

The existing issue #192 continues to own:

- external clock-health fencing and dynamic audit readiness;
- gap and overflow control;
- destructive HMAC retirement after its custody prerequisite;
- break-glass export and temporary-login closure;
- store-loss recovery; and
- remaining end-to-end hostile evidence; and
- any future migration that widens a persisted event constraint must recheck
  `deployment/postgresql/security_audit_query.py` so the normal reader cannot
  reject a newly lawful historical carrier after committing access intent.

No new issue is required merely to duplicate those open acceptance criteria.

### 11.6 Stop and reapproval conditions

Stop immediately if implementation requires:

- a migration, function, role, grant, or provisioning change;
- Kernel runtime composition or readiness coupling;
- an export credential, break-glass transition, or temporary login;
- a caller-supplied access event ID, arbitrary purpose/function, or wider
  result ceiling;
- direct relation access, generic SQL, a spool, cache, or output file;
- automatic retry or reconciliation through another credential;
- another pull request;
- any path outside the exact allowlist; or
- a material change to the trust boundary, authority map, permitted effects,
  non-effects, invariant, irreversible access evidence, command protocol, or
  named draft pull request.

Those changes require a separate prerequisite, Follow-up, or new decision
version.

## 12. Provisional design record

The one-shot technical primitive is not provisional. It remains valid if a
separately governed operator surface or scheduler invokes it later.

The command is not deployment-ready by itself. Deployment must independently
establish credential custody, output-destination protection, endpoint routing,
resource isolation, and the accepted database wall-clock prerequisite.
Evidence that either database function cannot safely implement its accepted
contract, that two credentials cannot be kept distinct, that a page must be
cumulatively bounded across invocations, or that clock rollback cannot be
externally fenced would require a new governed design rather than silent
expansion here.

The decision workflow and task-message evidence are provisional
pre-deployment authority. They authorize repository implementation in the one
named draft pull request only. They do not authorize deployment, production
access, release, current/default promotion, or a production security waiver.
Before deployment they must be replaced by an independently human-controlled
and independently verifiable approval or signing system.

## 13. Traceability and verification

| ID | Owning code | Negative evidence | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `BRQ-001` | Command adapter and cursor parser | Invalid argv/cursor plus malformed second DSN | Zero factory calls | Focused CLI tests |
| `BRQ-002` | Runner constants and intent call | Extra purpose/limit tokens and hostile options | Exact parameters, one submission, final options connect both roles, and server-owned `temp_file_limit=0` remains in force | Runner seam plus live connection and intent tests |
| `BRQ-003` | Explicit intent state machine | Commit acknowledgement exception | No reader factory call | Deterministic commit seam |
| `BRQ-004` | Existing functions and two DSNs | Swapped roles and cross-service routes | Exact role/equal-intent refusal | PostgreSQL integration test |
| `BRQ-005` | Immutable request and query call | Extra, misordered, out-of-cursor row | One equal query and bounded page | Runner seam plus live cursor test |
| `BRQ-006` | Event carrier validator | Malformed field, digest, time, policy, extension, or active-only historical-reason check | Complete accepted carrier, including unchanged retired authentication and router reasons | Parametric seam tests and live query |
| `BRQ-007` | Renderer and fixed diagnostics | Canary secret across every failure phase | Exact success/failure bytes | Byte-level protocol tests |
| `BRQ-008` | CLI terminal mapping | Intent ambiguity, post-intent failure, short write, flush failure | Distinct exits `4`, `5`, and `6` | State and sink tests |
| `BRQ-009` | Runner and CLI surface | Failure injected at every external step | Exact maximum call counts and no access-ID input | Seam call assertions |
| `BRQ-010` | Deployment placement and existing grants | Wrong capability roles and forbidden import edge | No alternate authority or Kernel diff | PostgreSQL role test and architecture checks |
| `BRQ-011` | README and report claims | Unestablished clock prerequisite | No ready/healthy/deployed claim | Documentation assertion and review |

### 13.1 Phase A verification gates

The contract-only head must pass:

```text
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

It must contain only this RFC and receive one exact-head review against this
contract before a live card is shown.

### 13.2 Prospective Phase B verification gates

The package contract check must pass before every commit:

```text
python3 conformance/ofarm_pkg_contract_check.py
```

The final exact Phase B head must also pass:

```text
.venv/bin/pytest -q kernel/tests/test_security_audit_query.py
.venv/bin/pytest -q kernel/tests/test_postgresql_audit_migration.py -k 'bounded_reader or bounded_query or access_intent'
.venv/bin/pytest -q kernel/tests/test_rewrite_architecture.py
.venv/bin/ruff check deployment/postgresql/security_audit_query.py deployment/postgresql/run_security_audit_query.py kernel/tests/test_security_audit_query.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

PostgreSQL-backed skips are reported as skips and never presented as passing
evidence.

PostgreSQL-backed Phase B evidence must additionally prove that the provisioned
control and reader logins both connect with the final code-owned options, each
connection still inherits `temp_file_limit=0` from its database-scoped role
default, and hostile conninfo options cannot replace the code-owned
USERSET/output settings. These observations belong to tests and provisioning
evidence; the production command must not add an identity, readiness, or
settings-observation query.

Before merge, the AI must also:

1. compare every path changed from the reviewed base through exact PR head
   against section 11.1's exact technical allowlist;
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

## 14. Open decisions and review disposition

### 14.1 Open material decisions

None. The existing database contract already fixes the purpose, callable
identity, role split, cursor pair, page ordering, ceilings, expiry, cut, and
clock prerequisite. The command fixes the maximum accepted normal-page limits
instead of exposing new policy inputs.

### 14.2 Review disposition

- **Earlier review:** the unconstrained review at
  `8bf9f935b2484f8e86e935c407a099467804c432` found three in-scope gaps in the
  success schema, diagnostic/failure protocol, and excess-row handling.
  Commit `2cedfa62c41a18c0441c60140b2587a5bf194ecc` corrected those gaps, and the
  permitted focused re-review of `BRQ-005` through `BRQ-008` passed.
- **Technical Blockers resolved:** two top-level reviews of exact head
  `cb5e0957702109b456a7250365b03f64fdaa2238` demonstrated that an active-only
  reason check would reject valid retired historical rows and that client-sent
  `temp_file_limit=0` could prevent the non-superuser routes from connecting.
  Commit `d9b1a12da75ecde3add2532a067663a7a2e125fa` preserves historical reasons
  under database authority and leaves `temp_file_limit=0` under provisioned
  role authority. Focused re-review of that exact head found no remaining
  technical Blocker.
- **Accuracy finding corrected:** the client fetch is now described as seam
  validation; only the database `LIMIT 256` is claimed as the row bound.
- **Diagnostic clarification:** the exact reviewed blob already stored each
  table value on one source line with the literal source characters `\n`.
  This revision now defines those characters explicitly as one emitted LF byte
  and forbids CR or any additional trailing byte.
- **Preference resolved by clarification:** top-level `maxBytes` remains an
  exactly representable JSON integer, while event-level `accessMaxBytes`
  retains the uniform `int8` carrier string encoding.
- **Governance Blocker resolved:** the formal review
  of `d9b1a12da75ecde3add2532a067663a7a2e125fa` required a new decision version
  because the withdrawn version-1 card preceded semantic authority and
  invariant corrections. Commit
  `590a32f5a094432e35ea1630d719940a1945a32a` advanced every decision binding
  and approval reference to proposed version `2`. Its exact-head focused
  re-review passed with no remaining in-scope Phase A Blocker.
- **Checklist Preference resolved:** section 8 now has one consolidated
  `BRQ-006` row covering both valid retired reasons and malformed carriers.
- **Numbering observation settled:** contract identity `v0.1` tracks the first
  approved publication, while decision version `2` tracks the semantic live-
  card replacement. The existing filename remains inside the approved exact
  path envelope; a rename would require reapproval.
- **Follow-ups:** the remaining issue #192 boundaries listed in section 11.5.

The version-1 live card bound to
`cb5e0957702109b456a7250365b03f64fdaa2238` is withdrawn and cannot authorize
Phase B. It was never approved, but review required semantic changes to
historical-reason acceptance, startup-setting authority, row-bound ownership,
and diagnostic semantics. The repository workflow therefore requires proposed
decision version `2`. The corrected exact head requires focused Phase A
re-review before a version-2 live card may be shown. That review passed at
`590a32f5a094432e35ea1630d719940a1945a32a`; the complete live card and later
exact approval are recorded below.

Once `BRQ-001` through `BRQ-011` pass and no demonstrated in-scope Blocker
remains, the approved workflow permits merging the named pull request. New
ideas, Preferences, and non-blocking hardening remain Follow-ups.

## 15. Phase A approval boundary

This RFC grants no Phase B authority by authorship, commit, push, review, or
GitHub activity. After this contract is bound to draft pull request #309 and
reviewed at its exact head, the AI must display one complete live decision card
in the same Codex task.

Only the exact entire text of a later task-user message matching the live
card's approval sentence can authorize Phase B. The original card and approval
must remain directly retrievable with stable task-item references and correct
role and order. Generic approval, another task, repository credentials, a
GitHub review/comment/reaction, an AI message, or a summary of lost items does
not authorize implementation.

The eventual exact approval form will be:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-BOUNDED-READER-EXECUTION-001 version 2.
```

Approval will authorize only in-envelope repository implementation, tests,
documentation, mechanical inventory regeneration, review handling, commits,
pushes, and merge in the one named draft pull request after every gate passes.
It will authorize no database operation, deployment, release, production
access, current/default promotion, or production security waiver.

### 15.1 AI-attested approval evidence

- **Task:** `codex-task:019ff570-c253-7d02-bbda-1ad8f4143f00`
- **Live card:**
  `codex-task:019ff570-c253-7d02-bbda-1ad8f4143f00#item-437`
- **Approval:**
  `codex-task:019ff570-c253-7d02-bbda-1ad8f4143f00#item-438`
- **Exact approval sentence:**
  `I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-BOUNDED-READER-EXECUTION-001 version 2.`
- **Observed role and order:** the assistant-authored complete version-2 live
  card was directly followed in the same task by the task user's exact entire-
  message approval. No later cancellation preceded Phase B implementation.
- **Named pull request:** `https://github.com/samovers/OFARM2/pull/309`
- **Exact reviewed Phase A head:**
  `590a32f5a094432e35ea1630d719940a1945a32a`
- **Review evidence:** focused exact-head PASS review
  `https://github.com/samovers/OFARM2/pull/309#pullrequestreview-4927679005`
  and detailed review comment
  `https://github.com/samovers/OFARM2/pull/309#issuecomment-5281183938`.
- **Evidence limitation:** the task messages remain authority; this record is
  AI-attested evidence only. The authority is provisional repository-
  development authority and grants no deployment or production authority.
