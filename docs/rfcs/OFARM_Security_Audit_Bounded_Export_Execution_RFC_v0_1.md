# OFARM Security-Audit Bounded Export Execution — Phase A Contract v0.1

**Status:** approved version 1; Phase B implementation is in exact-head verification

**Draft implementation pull request:**
`https://github.com/samovers/OFARM2/pull/318`

**Contract identity:**
`ofarm2.security-audit-bounded-export-execution.v0.1`

**Decision identity:**
`ISSUE192-SECURITY-AUDIT-BOUNDED-EXPORT-EXECUTION-001`, approved version `1`

**Issue:** #192

**Reviewed base:** `e65569fd82045607ec7eb8971834a340d82c5b2d`

**Approved Phase A head:** `7cbc37db12521699c091bfb1165a94cf5da0540d`

**Primary trust boundary:** isolated security-audit bounded export disclosure
execution after one acknowledged fixed export access intent

**Phase A review-head boundary:** this RFC only

**Prospective Phase B pull request boundary:** this RFC, one fixed library-only
export runner, the smallest shared event-carrier validation extraction needed
to avoid a second reader policy implementation, focused reader/export tests,
minimal deployment documentation, and the mechanically regenerated test
inventory only

## 1. Problem and goal

The accepted security-audit database already provides a separate bounded
break-glass function. It requires the exact temporary session user
`ofarm_security_audit_export_login`, a committed `AUDIT_ACCESS` intent with the
closed purpose `DUAL_APPROVED_BREAK_GLASS_EXPORT_V1`, the exact export-function
identity, one immutable cursor, at most 2,048 rows, and at most 8,388,608
database-encoded bytes. Normal provisioning intentionally creates neither the
temporary LOGIN nor its membership.

Current `main` has no repository execution primitive that safely couples the
two existing database transitions. A future dual-approval and temporary-login
lifecycle would otherwise have to issue generic SQL, duplicate the normal
reader's hostile carrier validation, or expose an access-event identifier
between independently operated steps.

This task establishes one library-only, one-shot bounded export-page primitive
that:

- accepts either the newest page or one immutable canonical descending-page
  cursor object supplied by its future lifecycle caller;
- fixes the export purpose, function identity, 2,048-row ceiling, and
  8,388,608-byte database ceiling;
- commits the exact export access intent through a distinct audit-control
  connection and explicit non-autocommit transaction;
- opens the temporary export route only after that commit is acknowledged;
- invokes the accepted export function exactly once;
- validates the complete bounded result against the same closed event-carrier
  rules used by the normal reader;
- buffers one canonical ASCII JSON page in memory; and
- never retries, resumes, loops, writes output, creates a credential, or
  changes a role.

The fixed database calls are:

```sql
SELECT *
FROM ofarm_security.commit_audit_access_intent(
    'DUAL_APPROVED_BREAK_GLASS_EXPORT_V1',
    'ofarm_security.export_operational_security_events(uuid, timestamptz, uuid, integer, bigint)',
    :cursor_observed_at,
    :cursor_event_id,
    2048,
    8388608
)
```

and, only after acknowledged intent commit:

```sql
SELECT *
FROM ofarm_security.export_operational_security_events(
    :access_event_id,
    :cursor_observed_at,
    :cursor_event_id,
    2048,
    8388608
)
```

PostgreSQL remains the sole authority for session-user authorization, the
event-writer barrier, data cut, persisted MVCC snapshot, five-minute expiry,
non-regressing access-clock observation, exact request equality, row
membership and ordering, and database-encoded-byte accounting.

This task directly advances issue #192's bounded-export criterion. It is a
stacked prerequisite, not the complete break-glass operation. The later
temporary-login and independently verifiable dual-approval decision must be
approved separately before it may call this primitive in an operator-facing
path.

## 2. Learning value

This slice proves that the accepted export database authority can be consumed
without direct table `SELECT`, `COPY`, generic SQL, caller-selected purpose or
ceilings, an externally supplied access-event identifier, or duplicated event
carrier policy. It gives the later lifecycle one closed disclosure primitive
whose maximum unique page is fixed and whose authorization ambiguity cannot
become permission to export.

It also validates a clean architectural seam: database disclosure execution
can remain separate from the higher-risk authority that verifies two
approvals, creates and revokes a credential, controls the structurally
incompatible window, and proves closure.

## 3. Non-goals

This pull request does not change or add:

- a temporary LOGIN, password, SCRAM verifier, `VALID UNTIL`, role membership,
  grant, revoke, drop, session termination, or credential transport;
- dual-approval creation, signature verification, approver identity,
  single-use approval state, approval currentness, or approval evidence
  storage;
- an operator-facing CLI, executable module, web endpoint, daemon, scheduler,
  loop, or output destination;
- permission to call the primitive while normal structural posture is active;
- cumulative paging across more than one access intent or more than one export
  function invocation;
- automatic continuation from the returned next cursor, replay prevention
  across separate invocations, or a drain-until-empty operation;
- migrations, functions, types, relations, indexes, role specifications,
  grants, provisioning behavior, or structural-readiness rules;
- changes to the accepted normal reader's purpose, limits, command protocol,
  result schema, diagnostics, or public imports;
- Kernel runtime composition, dynamic health, `/health`, `/ready`, or the rule
  that temporary-login presence makes the audit lane structurally
  incompatible and runtime-unhealthy;
- authentication, principal resolution, authorization, tenant binding,
  tenant storage, post-binding refusal evidence, or any issue #176 behavior;
- HMAC generation, key custody, retirement, KMS/IAM, retention, gap/overflow,
  store-loss, empty recreation, backup, replica, CDC, or legal hold;
- a claim that an authorized caller cannot copy the returned page;
- structural non-reachability of lifecycle arguments or trusted values from a
  fresh outward exception's own active traceback frame locals; any diagnostic
  integration that captures frame locals requires a separate reviewed
  disclosure, custody, access, and retention decision;
- deployment activation, production access, production approval, credential
  issuance, release, current/default promotion, issue #192 closure, production
  readiness, or a security waiver.

The purpose token's name records the accepted operational precondition. This
primitive does not independently prove that precondition. It therefore has no
standalone command adapter and must remain unreachable in normal provisioned
posture because the exact export LOGIN is absent. The later lifecycle must
establish approval before it creates that LOGIN and calls this primitive.

## 4. Trust model

### 4.1 Protected assets

- operational-security event data returned by the privileged export function;
- the requirement for one durable, exactly equal export `AUDIT_ACCESS` intent
  before disclosure;
- separation between the audit-control and temporary-export credentials;
- the database-owned data cut, visibility snapshot, expiry, cursor, ordering,
  row ceiling, and encoded-byte ceiling;
- normal-reader behavior and its existing 256-row/1,048,576-byte authority;
- the absence of direct table, `COPY`, generic-query, and tenant-data access;
- structurally bounded row count, field count, validation work, database
  calls, and client containers for one page, without misrepresenting the
  database byte ceiling as an exact Python process-memory ceiling;
- honest distinction between pre-commit refusal, commit ambiguity, and
  post-intent export failure;
- fixed diagnostics at the future lifecycle boundary, which this primitive
  must make possible without retaining dependency exception text; and
- the structural fact that no export operation is reachable under normal
  provisioning without a separate temporary-login authority change.

### 4.2 Trusted components

- the merged #174 database contract, immutable
  `security_audit/migrations/0001_initial.sql`, and exact export function;
- `SECURITY_AUDIT_CONTRACT` and its fixed export purpose, function identity,
  row ceiling, byte ceiling, event kinds, producer/component pairs, HMAC
  versions, policy identities, retention duration, and access expiry;
- the contract's cumulative known producer/component and correlation-HMAC
  key-version read sets, which remain append-only for retained historical
  events; retiring a reason or key version does not remove its pair or version
  from read acceptance;
- the normal reader merged through pull requests #309 and #310 as the accepted
  client-side event-carrier and canonical-cursor behavior;
- PostgreSQL transaction semantics and the explicit control commit
  acknowledgement boundary;
- PostgreSQL's exact `session_user` checks inside the two accepted functions;
- the distinct future control and export connection routes supplied by the
  separately governed lifecycle;
- Python immutable values, exact type checks, bounded tuple/list construction,
  integer comparison, and ordinary `Exception` semantics; and
- repository/package admission before execution.

The deployment environment must separately establish endpoint routing,
credential custody, database wall-clock prerequisites, temporary-login
lifecycle, two-person approval, single-operation admission, and protected
handling of returned bytes. This RFC does not claim those prerequisites exist.

### 4.3 Untrusted actors and inputs

- every cursor value before it becomes the validated immutable cursor object;
- arbitrary command, environment, approval, and lifecycle values outside this
  primitive;
- malformed, duplicate, missing, substituted, oversized, naive, infinite,
  misordered, or out-of-cut database result values;
- database errors and exception messages, arguments, causes, contexts, and
  tracebacks;
- control/export connection establishment, state, statement, fetch, rollback,
  close, and commit failures;
- loss of the control commit acknowledgement;
- cancellation and ordinary exceptions at each external seam;
- an export route aimed at the wrong role or service; and
- attempts by a future caller to invoke more than one page through one runner
  call.

No untrusted input selects the purpose, function, SQL statement, row limit,
byte limit, transaction mode, retry count, result schema, event kind, producer,
component, or access-event identifier.

### 4.4 Explicitly excluded attacker capabilities

This contract does not claim protection against:

- compromise of the audit-control credential, future export credential,
  database owner, PostgreSQL superuser, dual-approval authority, output
  recipient, or deployment route authority;
- arbitrary in-process mutation, reflective replacement of private objects,
  or calls to private helpers after trusted construction;
- local source, bytecode, interpreter, dependency, or import substitution
  after repository/package admission;
- arbitrary filesystem, process-memory, debugger, ptrace, core-dump, or host
  compromise;
- PostgreSQL server compromise or migration-owner compromise;
- uncatchable termination or physical host loss; or
- copying data after a later authorized lifecycle receives the returned page.

These exclusions do not authorize a public constructor that self-attests dual
approval, a generic export CLI, or a fallback around the absent temporary
LOGIN. Such additions remain outside this decision.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Export access purpose | Existing `EXPORT_ACCESS_PURPOSE_IDENTITY` constant |
| Exact export callable | Existing `EXPORT_FUNCTION_IDENTITY` constant |
| Maximum rows | Existing `EXPORT_MAX_ROWS`, exactly `2048` |
| Maximum database-encoded bytes | Existing `EXPORT_MAX_BYTES`, exactly `8388608` |
| Cursor components | One validated immutable cursor object or both SQL values `NULL` |
| Control identity | Existing exact `session_user` check and grant in `commit_audit_access_intent` |
| Export identity | Existing exact `session_user = 'ofarm_security_audit_export_login'` check and export-capability grant |
| Access event ID | Existing database maintenance-event function; never a caller input |
| Data cut, snapshot, and five-minute expiry | Existing access-intent function and database clock |
| Access-clock serialization/high-water | Existing migration/provisioning-owned wrappers and sequence |
| Intent durability | Explicit control transaction `commit()` acknowledgement |
| Permission to open export route | Runner state reached only after acknowledged intent commit |
| Page membership/order/encoded-byte accounting | Existing bounded export function |
| Historical event carrier acceptance | One shared client validator bounded by the contract's cumulative known producer/component and HMAC-version sets, closed-token shape, and trusted database constraints |
| Export page schema | Fixed `ofarm.security-audit-bounded-export-page.v1` runner constant |
| Next cursor | Last validated row's normalized `(observed_at, event_id)` pair |
| Endpoint and credential selection | Future approved lifecycle; not this primitive |
| Dual approval and one-operation admission | Future independently governed lifecycle; not this primitive |
| Temporary-login creation and closure | Future database-role/credential decision; not this primitive |
| Output delivery | Future lifecycle; this primitive returns buffered bytes only |

There is no legacy export runner, alias, direct table path, generic SQL path,
caller-selected protocol, credential fallback, access-event input, automatic
retry, or continuation path to preserve.

The extraction of shared event-carrier validation is mechanical authority
consolidation, not a new policy layer. The accepted normal reader and new
export runner each retain their own fixed top-level protocol, limits, SQL,
state machine, and report schema. Only cursor parsing/rendering, access-intent
shape validation, event-carrier validation, canonical event documents, and
bounded page validation are shared.

## 6. State machine and ordering

### 6.1 Request construction

The future lifecycle constructs either:

- a newest-page request containing no cursor; or
- one request containing a validated immutable cursor with canonical UTC
  microsecond timestamp and canonical lowercase nonzero UUID.

The primitive receives the object, never separate mutable cursor fields and
never raw command tokens. It accepts exactly two raw conninfo strings: one
control route and one temporary export route. Before deriving request values
or calling either connection factory, the runner validates both complete
values as exact strings, rejects blank values, and parses each with
`psycopg.conninfo.conninfo_to_dict`. Both values must pass before any external
I/O; the returned parse mappings are not retained. A validation failure
produces the fixed refused outcome with zero connection-factory calls and zero
access intent. Earlier lifecycle validation does not replace this runner-owned
preflight. After both values pass, each connection factory receives the same
original preflighted string as its positional conninfo argument plus the
code-owned keyword settings in section 6.2. The runner does not canonicalize,
reconstruct, expand, or substitute either route from the temporary parse
mapping.

The runner accepts no approval document, separate password parameter, role
name, purpose string, function name, limit, access-event ID, SQL, or output
sink. A credential may exist only inside a lifecycle-supplied conninfo value.
Because both routes are preflighted before control I/O, both values are
resident in the process for the whole runner call. The ordering guarantee is
that the export route is not opened before acknowledged intent; it is not a
claim of deferred credential materialization. The separately governed future
lifecycle owns that custody window. This primitive never logs, renders,
stores, or returns either route.

The supported future lifecycle calls this runner outside every active
exception handler. That invocation posture is required for a fresh outward
error to have `__context__ is None`; Python can otherwise attach an unrelated
exception already active in the caller. A later lifecycle adapter that needs
to call or propagate this runner while handling another exception must first
exit that handler and then perform the call or fixed propagation. Direct use
from inside an active handler is outside the supported production entry and
cannot claim the fixed-error detachment guarantee.

### 6.2 Fixed connection posture

Each route gets at most one `psycopg.connect` call. Both use the accepted
five-second per-host/address connect timeout and these code-owned libpq startup
settings:

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

The control route additionally fixes `synchronous_commit=on`. A code-owned
keyword replaces, and never merges with, a conflicting conninfo value; any
`options` present in a supplied route is therefore dropped in full. The
control connection must be open, non-autocommit, idle, and set to
`READ COMMITTED`. The export connection must be open, autocommit, and idle.
Any unequal posture refuses or fails according to the current state; there is
no alternate route.

Provisioning remains the authority for role/database settings such as
`temp_file_limit=0`. This primitive does not issue `SET`, inspect HBA rules, or
attempt to prove the future temporary credential's authentication mechanism.

### 6.3 Access-intent transaction

The initial states are:

```text
CONTROL_UNOPENED
CONTROL_OPEN
INTENT_RESULT_VALIDATED
COMMITTING
INTENT_ACKNOWLEDGED
```

The runner:

1. opens one control connection;
2. validates its initial state and selects `READ COMMITTED`;
3. submits the fixed export intent once with the immutable cursor and fixed
   limits;
4. fetches exactly one three-field result and rejects a missing or second row;
5. validates a nonzero UUID, finite timezone-aware cut and expiry, and exact
   300-second elapsed duration after UTC normalization;
6. preconstructs the exact export request using that access event ID and the
   same cursor;
7. enters `COMMITTING` immediately before calling `commit()`; and
8. reaches `INTENT_ACKNOWLEDGED` only if `commit()` returns normally.

An ordinary exception before `commit()` causes best-effort rollback and close,
then the fixed pre-intent refusal outcome. The export route is never opened.
An ordinary exception from `commit()` makes the intent outcome unknown. The
control route closes, no export is attempted, and no retry occurs. Normal close
failure after acknowledged commit cannot revoke or duplicate the intent.

### 6.4 One bounded export page

Only `INTENT_ACKNOWLEDGED` permits these states:

```text
EXPORT_OPEN
EXPORT_SUBMITTED
PAGE_READY
```

The runner then:

1. opens one temporary export connection;
2. validates its autocommit and idle state;
3. submits the exact export function once with the acknowledged access event
   ID, same cursor, and fixed limits;
4. requests at most 2,049 rows from the client cursor in one fetch call and
   refuses if a hostile seam exposes the extra row;
5. validates at most 2,048 exact 30-field event carriers, fixed identities,
   allowed event shapes, finite timestamps, exact retention relation,
   maintenance extensions, descending order, data-cut membership, intent
   expiry membership, and cursor boundary;
6. derives a next cursor only from the final validated row;
7. renders the entire canonical page in memory; and
8. closes the export connection before returning the immutable result.

The database function's `LIMIT p_max_rows`, fixed at 2,048 by the runner and
equality-checked against the committed intent, and its encoded-row accounting
are the authoritative bounds. Client `fetchmany(2049)` is hostile-seam
validation, not a transport bound. The primitive performs no second statement,
cursor loop, page continuation, retry, output write, or close-window action.

An ordinary exception after acknowledged intent and before `PAGE_READY`
produces a fixed export-failed outcome. The access intent remains durable, no
partial page is returned, and there is no retry. Normal connection close
failure after the complete page is validated is suppressed because the
autocommit query already completed and no second operation is authorized.

### 6.5 Canonical page

The result contains:

- the validated access intent;
- the immutable input cursor, if any;
- the tuple of validated event values;
- the derived next cursor, if any; and
- one pre-rendered canonical ASCII JSON line.

The top-level document contains exactly:

| Key | Value |
| --- | --- |
| `schemaVersion` | `ofarm.security-audit-bounded-export-page.v1` |
| `outcome` | `ACKNOWLEDGED` |
| `purpose` | fixed export purpose |
| `functionIdentity` | fixed export function identity |
| `accessEventId` | canonical UUID text |
| `dataCut` | canonical UTC microsecond timestamp |
| `expiresAt` | canonical UTC microsecond timestamp |
| `inputCursor` | canonical cursor or JSON `null` |
| `maxRows` | `2048` |
| `maxBytes` | `8388608` |
| `returnedRowCount` | integer `0..2048` |
| `nextCursor` | derived canonical cursor or JSON `null` |
| `events` | validated event documents in database order |

Event documents retain the accepted normal reader's exact keys and encodings.
Historical closed reason tokens remain accepted by closed-token shape.
Producer/component pairs and correlation-HMAC key versions remain bounded by
the contract's cumulative known read sets, which are append-only for retained
history. The client therefore preserves a retired lawful reason under a known
pair/version without accepting an unknown pair or version. JSON uses sorted
keys, compact separators, ASCII escaping, no NaN, and exactly one trailing LF
byte.

The 8,388,608-byte ceiling is a database-encoded disclosure bound, not an exact
Python RSS limit. At peak the runner may retain fetched typed carriers,
normalized immutable values, event documents, and the canonical ASCII page at
the same time. Expected payload memory is therefore several multiples of the
database ceiling plus fixed overhead for at most 2,048 carriers of exactly 30
fields. The fixed row/field counts and absence of loops or retained prior pages
provide the process bound; this contract makes no platform-specific RSS claim.

The page contains no conninfo, password, role-creation data, approval evidence,
operator identity, exception text, traceback, or output destination. The later
lifecycle may wrap the page only under a separately approved contract; it may
not reinterpret this page as proof that approval or closure occurred.

### 6.6 Closed library outcomes

The primitive exposes only these exact ordinary outcomes:

| Outcome | Exact outward value | Meaning |
| --- | --- | --- |
| acknowledged page | `AcknowledgedSecurityAuditExport` | Intent commit acknowledged and one complete page validated/rendered |
| control unavailable | `SecurityAuditExportControlUnavailable` | Control connection factory failed before a connection returned |
| refused | `SecurityAuditExportRefused` | Either route failed preflight before I/O, or the control route returned, but no commit became ambiguous |
| intent outcome unknown | `SecurityAuditExportOutcomeUnknown` | Explicit intent commit raised; export was not attempted; never retry automatically |
| export failed | `SecurityAuditExportFailed` | Intent acknowledged, but no complete validated page is available; never retry automatically |

The four failure classes are exact direct subclasses of
`SecurityAuditExportError`, itself a `RuntimeError`. Every outward failure is a
fresh exact instance constructed with no arguments: `error.args == ()` and
`str(error) == ""`. Given the supported section 6.1 invocation posture, its
`__cause__` and `__context__` are both `None`.

An ordinary dependency exception is classified inside its handler by retaining
only the trusted fixed outward class identity. The caught object, its message,
arguments, cause, context, and traceback are discarded. Only after the handler
has exited does the runner construct and raise the fresh fixed error. Its
exception chain links no dependency exception or prior traceback. Focused test
evidence formats the error with
`traceback.TracebackException.from_exception(error, capture_locals=False)`
and requires that output to contain no runtime-injected conninfo, credential,
access-event, event, page, or dependency-exception canary. The production
export and shared-access modules do not import `traceback` or format errors.

Like every raised Python exception, the fresh fixed error has its own active
traceback. Its frames, and upstream caller frames, may expose application
arguments or trusted values through `traceback.tb_frame.f_locals`; this
contract does not claim structural non-reachability from that fresh call
stack. This decision adds no logger, collector, formatter, or diagnostic hook
that captures frame locals. A future lifecycle must not enable such capture
for this path without a separate reviewed decision governing disclosure,
custody, access, and retention.

`KeyboardInterrupt`, `SystemExit`, and other `BaseException` subclasses remain
outside this closed ordinary-exception protocol and are never converted into
success or retried.

This decision defines no process exit code or stderr/stdout protocol because
it intentionally adds no executable adapter. The later lifecycle must define
its own complete approval, credential, cleanup, output, and terminal protocol.

## 7. Invariants and acceptance criteria

### `BEX-001` — fixed export authority only

Every runner call uses the accepted export purpose, exact export function,
2,048-row ceiling, and 8,388,608-byte ceiling. None is a caller input.

### `BEX-002` — immutable request and complete route preflight

The runner receives either no cursor or one already validated immutable
timestamp/UUID cursor. The same two values are used for intent and export.
Both exact conninfo strings pass nonblank libpq parsing before either
connection factory is called; one malformed route cannot persist an intent.
Successful factory calls receive the unchanged original preflighted strings.

### `BEX-003` — acknowledged intent precedes export access

No export connection or function call occurs unless the exact control intent
commit returned normally. Commit ambiguity never authorizes disclosure.

### `BEX-004` — database role separation remains authoritative

The runner does not create, grant, assume, or choose a role. The control and
export functions retain their exact independent `session_user` checks, and
normal provisioning retains no export LOGIN or membership.

### `BEX-005` — exactly one equal bounded page

After acknowledged intent, at most one export connection and one export
function call occur with the exact access event ID, cursor, and fixed ceilings.
No loop, continuation, or second intent exists inside one runner call.

### `BEX-006` — carrier validation is shared, bounded, and historical

The normal reader and export runner use one shared event-carrier validator.
The validator accepts lawful retained history under the contract's cumulative
known producer/component and HMAC-version sets, including retired closed
reasons, and refuses unknown-set, malformed, excessive, misordered,
expired-at-intent, out-of-cut, or cursor-violating rows.

### `BEX-007` — canonical page is exact and buffered

Success returns one immutable result with one canonical ASCII JSON line and no
partial or streaming result. The page has the fixed export schema and contains
no credential, approval, operator, route, or dependency-exception data. An
unlawful quote/control-bearing closed token is refused before rendering.

### `BEX-008` — honest state-classified outcomes

Pre-connection unavailability, pre-commit refusal, explicit-commit ambiguity,
and post-intent export failure remain distinct. No ordinary exception becomes
success, leaks its content through the fixed fields, linked prior exception
graph, or normal formatting with local capture disabled, or triggers a retry.
Given the supported section 6.1 invocation posture outside every active
exception handler, the fresh fixed error has exact empty arguments/message,
cause/context `None`, and no linked dependency traceback. No structural claim
is made about its own active traceback frame locals.

### `BEX-009` — no automatic retry, resume, or access-ID input

Each permitted connection and SQL statement is attempted at most once. The
caller cannot supply or reuse an access-event ID. The primitive does not
automatically consume `nextCursor`.

### `BEX-010` — no standalone break-glass operation

Phase B adds no CLI, module entry point, role lifecycle, approval verifier,
output sink, or normal-posture fallback. The primitive alone cannot satisfy or
claim the complete dual-approved temporary window.

### `BEX-011` — normal reader semantics remain unchanged

The shared extraction preserves the normal reader's public imports, SQL,
purpose, limits, cursor parsing, canonical report bytes, state transitions,
exceptions, CLI exits/diagnostics, and focused/live evidence.

### `BEX-012` — no database or runtime authority expansion

No migration, function, role, grant, provisioning, readiness, Kernel runtime,
tenant, HMAC/KMS, retention, gap/overflow, recovery, or issue #176 path changes.

### `BEX-013` — claim-limited operational posture

Repository success proves only the bounded export-page primitive. It does not
prove dual approval, single-use approval, login expiry/revocation, structural
closure, runtime health, protected delivery, clock fencing, deployment, or
issue #192 completion.

## 8. Production-reachable negative cases

These cases begin at the future lifecycle-to-runner seam or at accepted
database seams. Tests may inject connection factories and cursors to make the
same production states deterministic; they must not mutate private runner
state and call that production evidence.

| Invariant | Counterexample | Required result |
| --- | --- | --- |
| `BEX-001` | A future caller attempts to pass the normal purpose, query function, 2,049 rows, or 8,388,609 bytes. | No such runner parameters exist; captured SQL contains only export constants. |
| `BEX-002` | The request attempts a timestamp without UUID, uppercase UUID, non-UTC timestamp, changes cursor values between calls, or supplies a valid control conninfo with a blank/malformed export conninfo. | Construction or runner preflight refuses before external I/O; both factory call counts remain zero; otherwise the immutable normalized cursor pair remains identical in both SQL calls and the captured factory positional values equal the original preflighted strings. |
| `BEX-003` | Control commit raises after submission may have reached PostgreSQL. | Intent outcome is unknown; export factory and function call counts remain zero; no retry. |
| `BEX-004` | Control and export conninfo values point at swapped roles or an export role lacking exact membership. | Existing database session-user/grant checks refuse; no direct table or alternate-role path. |
| `BEX-005` | A hostile seam exposes a 2,049th row or fails after the first export statement. | No successful page; exactly one intent and at most one export statement; no continuation. |
| `BEX-006` | Return a retired closed reason under a cumulatively known producer/component pair and HMAC version; then separately return an unknown pair/version, zero UUID, unknown event kind, wrong digest length, malformed maintenance extension, ascending row, row after the cut, or row at/above the cursor. | The lawful retained row is preserved; each unknown-set, malformed, or out-of-bound case fails after intent with no page. |
| `BEX-007` | Render a valid golden fixture; separately return a reason containing a quote or control character, which cannot be a lawful closed token. | Valid canonical bytes remain exact and ASCII; the unlawful token is refused before any page is returned. |
| `BEX-008` | From the supported section 6.1 posture outside every active exception handler, inject runtime-generated conninfo, credential, access-event, event, page, and dependency-exception canaries; fail control preflight/connect, intent execute, control commit, export connect/execute, fetch, and render in separate calls; format each fixed error with local capture disabled. | Exact class, empty message/arguments, cause/context `None`, and state outcome follow; no prior exception/traceback is linked and normal formatting contains no canary; the test makes no structural claim about fresh traceback frame locals. |
| `BEX-009` | Attempt to rerun after ambiguous commit or pass the prior access UUID as a new request. | No automatic retry and no access-ID input surface; a new caller invocation is outside this primitive's authority. |
| `BEX-010` | Run `python -m deployment.postgresql.security_audit_export` or search deployment docs for a standalone export command. | No executable entry point or operator command exists; documentation names the later lifecycle requirement. |
| `BEX-011` | Run the complete accepted normal-reader unit/live suite and compare canonical fixtures before and after extraction. | Public behavior and exact report bytes remain unchanged. |
| `BEX-012` | Diff the Phase B head or inspect migration/provisioning/runtime sources. | Every changed path is allowlisted; all forbidden authority paths are byte-identical to base. |
| `BEX-013` | Inspect returned page and README for approval, closure, health, or deployment claims. | Page makes no such claim; documentation states all are unresolved prerequisites. |

Live PostgreSQL evidence must additionally create the fixed temporary export
LOGIN and exact membership only inside the isolated test fixture, prove normal
reader and export role separation, execute one successful page, exercise
intent mismatch/replay/expiry and widened limits against the database, drop
the test LOGIN in `finally`, and verify exact normal structural posture after
cleanup. Test-only role creation does not authorize or implement the
production lifecycle.

## 9. Proposed architecture and smallest change

### 9.1 Types and ownership

`deployment/postgresql/security_audit_access.py` will own only the shared,
protocol-neutral client values and validators already needed by both accepted
database read functions:

- immutable canonical `SecurityAuditAccessCursor`;
- immutable validated access-intent and event-report values;
- exact event-carrier, ordering, cut, expiry, and cursor validation;
- canonical event-document rendering; and
- a bounded page validator parameterized only by a trusted fixed maximum.

It will not own SQL, connection factories, purpose/function identities,
protocol limits, runner state, output schemas, role names, or approval state.

`deployment/postgresql/security_audit_query.py` will continue to own the
normal reader's fixed SQL, purpose, limits, runner, exceptions, and report
schema. It will import the shared values/validators and preserve its existing
public names by direct imports/exports, not by a second compatibility
implementation.

`deployment/postgresql/security_audit_export.py` will own:

- complete two-route conninfo preflight before external I/O;
- fixed export intent and function SQL;
- fixed connection settings;
- export-specific closed exception classes, dependency detachment, and state
  machine;
- immutable acknowledged export-page result;
- export-page rendering; and
- one `SecurityAuditExportRunner` with an injected connection-factory seam.

There is deliberately no `run_security_audit_export.py` in this decision.

### 9.2 Data flow

```text
future approved lifecycle
    -> immutable newest-page/cursor request
    -> fixed control route
    -> one fixed export AUDIT_ACCESS intent
    -> explicit COMMITTING boundary
    -> acknowledged intent
    -> exact temporary export route
    -> one exact bounded export function call
    -> shared complete carrier validation
    -> fixed canonical buffered export page
    -> return to the same future lifecycle
```

### 9.3 Why this is the smallest coherent slice

An intent-only helper would persist an export claim without delivering the
bounded disclosure primitive. An export-only helper would require an external
access-event ID and separate correlated cursor/limit handoff, weakening the
accepted ordering. Coupling the two existing database transitions in one
runner is therefore the minimum honest disclosure execution.

Copying approximately the entire normal reader validator into an export module
would create two policy implementations that can diverge when lawful
historical carriers evolve. The small shared extraction is necessary
mechanical integration. It does not make purpose, SQL, limits, or state generic.

Conversely, adding temporary role creation, credential custody, approval
verification, structural-health transitions, cleanup, or output delivery would
cross from reader/export disclosure into database-role, credential, approval,
runtime-health, and operational-output authority. Those changes are not
necessary to validate the one-page database protocol and would require either
separate decisions or a prominently approved cross-boundary exception.

## 10. Elegance audit

- export-purpose sources of truth: one accepted contract constant;
- export-function sources of truth: one accepted contract constant;
- export row/byte bound sources of truth: one accepted contract pair;
- cursor objects per request: zero or one immutable object;
- event-carrier client validators: one shared implementation;
- access-intent transitions per call: one;
- export-function transitions per call: at most one;
- control/export connection attempts per call: at most one each;
- complete conninfo preflight operations before external I/O: exactly two;
- automatic retries, resumes, loops, or page continuations: zero;
- caller-supplied access IDs, purposes, functions, SQL, or limits: zero;
- new operator entry points: zero;
- error collectors, loggers, formatters, or hooks that capture frame locals:
  zero;
- new roles, grants, migrations, or runtime constructors: zero; and
- new generic framework or optional capability bags: zero.

The duplicate cursor, intent, event-carrier, event-document, and page
validation code can be deleted from the normal-reader module only when moved
byte-for-semantics into the shared module. No public normal-reader behavior or
deprecated compatibility path is deleted.

A clean shared extraction plus one small export runner is safer than either a
copy of the reader module or a generic caller-configured access engine.

## 11. Pull request and approval boundary

### 11.1 Exact prospective Phase B technical path allowlist

The final pull request may change exactly these paths:

1. `docs/rfcs/OFARM_Security_Audit_Bounded_Export_Execution_RFC_v0_1.md`
2. `deployment/postgresql/security_audit_access.py`
3. `deployment/postgresql/security_audit_query.py`
4. `deployment/postgresql/security_audit_export.py`
5. `deployment/postgresql/README.md`
6. `kernel/tests/test_security_audit_query.py`
7. `kernel/tests/test_security_audit_export.py`
8. `conformance/review_baseline_test_inventory.json`

The Phase A review head changes only path 1. After approval, the RFC may change
only to mark approved status, bind the named draft pull request and reviewed
head, append truthful AI-attested approval evidence, and record
meaning-preserving implementation/review disposition. A semantic contract
change requires a new decision version.

The inventory is a mechanical Phase B change because the focused export tests
necessarily add collected nodes.

Focused shared-validator cases must live inside the two allowlisted test paths
`kernel/tests/test_security_audit_query.py` and
`kernel/tests/test_security_audit_export.py`. The phrase "shared-access tests"
names cases exercising the shared production module through those two suites;
it does not authorize a third test file or a ninth path.

### 11.2 Explicitly unchanged paths and authorities

- `deployment/postgresql/run_security_audit_query.py` and its executable
  command protocol;
- `deployment/postgresql/audit_contract.py`;
- `deployment/postgresql/provisioning.py` and
  `deployment/postgresql/provisioning_specs.py`;
- `security_audit/migrations/*` and `kernel/migrations/*`;
- every Kernel production/runtime/readiness module;
- every HMAC, retention, gap, overflow, and recovery module;
- every authentication, principal, authorization, tenant, and issue #176
  path; and
- every file outside the exact allowlist.

### 11.3 Dependencies

- reviewed base `e65569fd82045607ec7eb8971834a340d82c5b2d`;
- the accepted #174 database authority;
- merged normal-reader pull requests #309 and #310;
- merged dynamic-readiness, HMAC-retirement, and live-gap pull requests
  #314, #316, and #317;
- closed issue #172; and
- no open stacked implementation pull request.

### 11.4 Reviewer non-requirements

Reviewers must not require a migration, new role, credential, approval system,
operator CLI, output file, runtime-health coupling, deployment route, KMS/IAM
change, store recovery, full hostile closure matrix, issue #176 change, or
issue #192 closure from this pull request.

### 11.5 Follow-ups

Issue #192 continues to own:

- independently verifiable dual approval and single-operation admission;
- exact temporary export-login creation, expiry, membership, credential
  custody, revocation/drop, crash residue handling, and structural reverify;
- the rule that one approved lifecycle invokes this primitive at most once and
  does not turn `nextCursor` into an unbounded operation;
- protected output delivery and terminal protocol after structural closure;
- empty-recreate/store-loss handling; and
- final real-ASGI/PostgreSQL hostile and cross-slice closure evidence.

Review additionally records, without making them gates or effects of this
decision:

- a separately reviewed normal-reader fixed-error detachment change if the
  accepted reader's retained dependency exception through `__context__` is to
  be removed; `BEX-011` preserves that reader behavior in this decision; and
- optional gap-style architecture-checker registration for the export/access
  modules under a separate path-envelope decision; this slice instead uses
  the focused test enforcement fixed in section 13.

No new issue is required merely to duplicate the open parent criteria. Either
additional implementation-quality improvement requires its own later decision
and path envelope before repository work; this RFC records but does not
authorize it.

### 11.6 Stop and reapproval conditions

Stop immediately if implementation requires:

- a migration, function, role, grant, provisioning, or readiness change;
- login/password creation, approval input, credential transport, cleanup, or
  output delivery;
- an executable export adapter or documented standalone invocation;
- more than one intent or export function call per runner invocation;
- a caller-selected purpose, function, SQL statement, limit, role, or access
  event ID;
- a normal-reader public behavior or report-byte change;
- any connection-factory call occurring before both complete raw conninfo
  strings pass runner-owned exact-type, nonblank, libpq parsing;
- an error collector, logger, formatter, or diagnostic hook that captures
  frame locals or protected runtime values;
- direct relation access, `COPY`, generic SQL, a file/spool/queue/cache, or
  automatic retry;
- any path outside the exact allowlist; or
- a material change to the trust boundary, authority map, effects,
  non-effects, invariant, state machine, or named draft pull request.

Such evidence requires a separate prerequisite, Follow-up, or new decision
version. Combining role lifecycle with disclosure execution would also require
the explicit cross-boundary approval procedure in workspace policy.

## 12. Provisional design record

Not provisional.

The primitive is a stable lower-level consequence of the accepted database
contract: every lawful break-glass lifecycle needs one committed intent and one
equal bounded export call. The absence of a standalone command is intentional,
not a temporary shortcut.

The complete break-glass operation remains unimplemented and undeployable
until a separate approved decision establishes independently verifiable
approval, one-operation admission, temporary credential lifecycle, crash
residue closure, runtime-health interaction, and protected output delivery.
Evidence that the database function cannot safely preserve one-page bounds or
that a future lifecycle needs a different purpose/function/cursor protocol
would require a new database or export decision rather than silently widening
this runner.

## 13. Traceability and verification

| Invariant | Owning code | Negative evidence | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `BEX-001` | Export constants and SQL | Attempt caller-selected protocol values | Captured exact parameters | Focused unit test plus contract assertions |
| `BEX-002` | Shared immutable cursor and export route preflight | Partial/noncanonical/mutated cursor or malformed second route | Same pair in both statements; zero I/O until both routes parse; unchanged original strings reach the factories only afterward | Existing cursor tests plus export preflight/capture tests |
| `BEX-003` | Export runner state machine | Commit raises | Zero export connections/calls | Deterministic state-seam test |
| `BEX-004` | Existing database functions | Swapped/missing roles | Session-user/grant refusal | Live PostgreSQL role test |
| `BEX-005` | Export runner | 2,049th row/fetch failure | One intent and at most one export | Focused call-count tests plus live page |
| `BEX-006` | Shared access validator | Retired reason under cumulative known sets; unknown-set and malformed carriers | Lawful retained acceptance; unknown/malformed refusal | Shared normal/export parametrized cases in the two allowlisted test files |
| `BEX-007` | Export renderer/result | Valid golden fixture and unlawful quote/control-bearing token | Exact canonical ASCII bytes; unlawful-token refusal | Golden-byte and carrier tests |
| `BEX-008` | Closed exceptions/state mapping | Supported-posture runtime canaries and failure at every external seam | Exact fields/state; no linked prior exception or canary in normal formatting | Focused transition, exception-chain, formatting, and static-surface matrix in the two allowlisted test files |
| `BEX-009` | Runner API and call graph | Prior access ID/retry attempt | No input or second call surface | Signature/static and call-count tests |
| `BEX-010` | Module/docs boundary | Module execution/doc search | No entry point or standalone command | Import/static/documentation tests |
| `BEX-011` | Shared extraction/query imports | Full reader regression corpus | Exact prior public behavior/bytes | Complete reader unit/live suite |
| `BEX-012` | PR allowlist | Base-to-head path diff | Exact eight-path envelope | Mechanical path checks and architecture conformance |
| `BEX-013` | README/RFC/page schema | Search for overclaims | Explicit prerequisite wording | Documentation assertions and review |

### 13.1 Phase A verification gates

Before Phase A review:

1. diff from the reviewed base changes exactly this RFC path;
2. `git diff --check` passes;
3. the mandatory package contract checker passes;
4. RFC metadata, decision identity, version, base, boundary, allowlist, and
   approval form are internally consistent; and
5. the draft pull request remains draft and Phase B remains unauthorized.

### 13.2 Prospective Phase B verification gates

After explicit approval and before implementation review:

1. reproduce this invariant traceability table;
2. run the shared-validator cases housed in
   `kernel/tests/test_security_audit_query.py` and
   `kernel/tests/test_security_audit_export.py`, plus both complete focused
   normal-query and export suites;
3. run live PostgreSQL export role, mismatch, replay, expiry, widening, and
   post-test structural-closure cases on PostgreSQL 17;
4. run Ruff on every changed Python path;
5. run architecture/conformance checks and the mandatory package checker;
6. regenerate the review-baseline inventory mechanically;
7. run `git diff --check` and exact allowlist equality/subset checks; and
8. obtain green hosted conformance, amd64 native verifier, arm64 native
   verifier, and canonical native-index evidence at the exact Phase B head.

PostgreSQL-backed skips must be reported as skips and never presented as
passing live evidence. Exact-head review must exercise each `BEX` invariant,
the shared-validator regression risk, and the absence of lifecycle/approval
authority.

For `BEX-008`, absence of a production frame-local collector, formatter, or
`traceback` import is enforced by focused runtime and static-source assertions
inside the two allowlisted test files. The existing gap-style architecture
checker is hard-coded to the separately accepted live-gap module and is not
claimed as enforcement for this export slice. Registering the export/access
modules there would require a separate path-envelope decision and is not a
Phase B gate for this contract.

## 14. Open decisions and review disposition

### 14.1 Open material decisions

None inside this boundary. The database already fixes the export purpose,
function identity, session user, cursor pair, result carrier, row/byte bounds,
expiry, cut, ordering, and clock premise.

The following are deliberately open outside this decision and must not be
answered by Phase B implementation:

- the independently verifiable dual-approval carrier and single-use authority;
- how the fixed temporary LOGIN is created, time-bounded, and dropped;
- how crash residue is closed without reviving disclosure;
- how runtime-health observation spans the full incompatible window; and
- how approved output is delivered only after verified closure.

### 14.2 Review disposition

- **Blockers:** the first exact-head [Phase A
  review](https://github.com/samovers/OFARM2/pull/318#issuecomment-5309069795)
  reported zero demonstrated Blockers. Later [review
  4947132962](https://github.com/samovers/OFARM2/pull/318#pullrequestreview-4947132962)
  demonstrated that the original retained-error wording made an impossible
  secrecy claim about the fresh exception's own traceback frame locals. Later
  [review comment
  5309267998](https://github.com/samovers/OFARM2/pull/318#issuecomment-5309267998)
  demonstrated an internal contradiction between the eight-path allowlist and
  the shared-validator test gate. This revision adopts the executable fixed
  error boundary used by the accepted live-gap slice and explicitly houses all
  shared-validator cases in the two allowlisted test files. The first
  correction-focused [automated
  re-review](https://github.com/samovers/OFARM2/pull/318#issuecomment-5309421653)
  reported zero Blockers, but later [review
  4947232777](https://github.com/samovers/OFARM2/pull/318#pullrequestreview-4947232777)
  and [review comment
  5309490378](https://github.com/samovers/OFARM2/pull/318#issuecomment-5309490378)
  demonstrated that the new stop condition accidentally forbade the
  post-preflight raw conninfo factory calls required by sections 6.1 and 6.2.
  This revision restricts the stop to a factory call before both complete raw
  strings pass exact-type, nonblank, libpq parsing and carries the section 6.1
  invocation posture into `BEX-008`. The corrected exact-head [automated
  review](https://github.com/samovers/OFARM2/pull/318#issuecomment-5309515388),
  [review
  4947285696](https://github.com/samovers/OFARM2/pull/318#pullrequestreview-4947285696),
  and [independent review
  comment](https://github.com/samovers/OFARM2/pull/318#issuecomment-5309627643)
  reported zero demonstrated Blockers. Review 4947285696 also recorded the
  now-adopted meaning-preserving preference that a code-owned `options`
  keyword replaces the complete conflicting conninfo value.
- **Adopted corrections:** route preflight, lawful-token test wording,
  cumulative-known historical acceptance, database-limit wording,
  refused/replay precision, fixed-error test attribution, and enforcement-level
  clarity are incorporated without widening the trust boundary or path
  envelope.
- **Follow-ups:** the issue #192 lifecycle, store-loss, and final hostile
  evidence boundaries, accepted-reader context detachment, and optional
  gap-style architecture registration listed above.
- **Preferences:** explicit credential residency and honest client-memory
  posture are incorporated without widening the trust boundary or path
  envelope.
- **Authorized Phase B disposition:** the implementation uses the shared
  protocol-neutral validator, preserves the normal reader's fixed protocol,
  adds only the library export runner, keeps all lifecycle authority absent,
  and houses shared/export evidence in the two allowlisted test files. Local
  focused PostgreSQL 17.10, package-checker, deterministic-inventory,
  architecture/conformance, Ruff, and diff gates are recorded in pull request
  #318; hosted exact-head checks and implementation review remain merge gates.

Once every `BEX-001` through `BEX-013` invariant passes and no demonstrated
in-scope Blocker remains, the approved workflow permits Phase B implementation
and eventual merge in the named draft pull request. New ideas, Preferences,
and unrelated hardening remain Follow-ups and do not widen this decision.

## 15. Phase A approval boundary

This RFC grants no Phase B authority by authorship, commit, push, review, or
GitHub activity. It must first be bound to one already-created draft pull
request and receive an independent exact-head Phase A review with zero
demonstrated in-scope Blockers. The AI must then display one complete live
decision card in the same Codex task.

Only the exact entire text of a later task-user message matching the live
card's approval sentence can authorize Phase B. Generic approval, GitHub
activity, repository credentials, an AI message, delegation, another task, or
a summary of lost task items does not authorize implementation.

The exact approval form was:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-BOUNDED-EXPORT-EXECUTION-001 version 1.
```

Approval authorizes only in-envelope repository implementation, tests,
documentation, mechanical inventory regeneration, review handling, commits,
pushes, and merge in the one named draft pull request after every gate passes.
It authorizes no temporary LOGIN, credential, role grant/revoke/drop,
dual-approval operation, database operation outside isolated test fixtures,
deployment, production export, release, current/default promotion, issue #192
closure, or production security waiver.

After the complete live decision card named draft pull request #318, reviewed
base `e65569fd82045607ec7eb8971834a340d82c5b2d`, approved Phase A head
`7cbc37db12521699c091bfb1165a94cf5da0540d`, the exact eight-path envelope,
all invariants and gates, and the exact approval form, the task user supplied
this exact entire later message on 2026-08-16:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-BOUNDED-EXPORT-EXECUTION-001 version 1.
```

This is the AI-attested Phase B authorization for the in-envelope repository
implementation, tests, documentation, mechanical inventory, review handling,
commits, pushes, and eventual merge in pull request #318 after all gates pass.
It grants none of the production, temporary-role, approval-system, deployment,
release, waiver, or issue-closure authority excluded above.
