# OFARM Security-Audit Live Gap Reconciliation — Phase A Contract v0.1

**Status:** Phase A approved after zero-Blocker exact-head Review 4946752582;
Phase B repository implementation is authorized only in draft PR #317;
deployment, release, and production operation remain unauthorized

**Draft pull request:** `https://github.com/samovers/OFARM2/pull/317`

**Contract identity:**
`ofarm2.security-audit-live-gap-reconciliation.v0.1`

**Approved decision identity:**
`ISSUE192-SECURITY-AUDIT-LIVE-GAP-RECONCILIATION-001`, version `1`

**Issue:** #192

**Reviewed base:** `6c061c4b9c12ac0c1141cf97fd6cf569f64ead00`

**Primary trust boundary:** bounded process-local observation of failed
pre-tenant security-audit attempts, audit-control-authorized durable
`AUDIT_GAP` reconciliation after live-process recovery, and context-detached
propagation of its two fixed errors through the accepted producer adapters

**Phase A review-head boundary:** this RFC only

**Maximum final pull request boundary:** this RFC; one bounded live-gap
controller and audit-control client; mechanical production-runtime composition;
narrow fixed-error deferral in the two accepted producer adapters; focused
unit, live PostgreSQL, producer-adapter, and runtime tests; minimal Kernel
documentation; architecture-budget registration; and the mechanically
regenerated review-baseline test inventory only

## 1. Problem and goal

The production pre-tenant audit path is synchronous and fail closed. Merged PR
#314 adds two process-local health lanes and makes a lane not ready after its
complete HMAC-and-append operation fails. A later-started success on that same
lane proves current delivery recovery and restores that lane's readiness.

That current-health result deliberately creates no durable history. If a live
process observes one or more failed governed audit attempts and later observes
same-lane recovery, the accepted database already exposes
`ofarm_security.append_audit_gap(...)`, but production code never calls it.
The process can therefore know that evidence may be missing while the isolated
audit store never receives the closed maintenance event required by ADR 0001.

This task establishes one bounded live-process reconciliation controller around
the already accepted health-observed producer sinks. It has exactly two fixed
lanes:

- `AUTHENTICATION`;
- `REQUEST_ROUTER`.

Before the production runtime is published, the controller obtains one
database-owned timestamp through the existing audit-control credential. That
timestamp is the initial conservative evidence anchor. Every governed producer
attempt receives a lane-local sequence number and an immutable snapshot of the
latest trusted database anchor before the existing health-observed sink begins
HMAC work.

When the inner sink raises an ordinary `Exception`, the controller records one
failed logical audit attempt without retaining its reason, exception, event
identity, correlation value, request, principal, tenant, or other event data.
The first failure freezes that attempt ticket's pre-attempt database anchor as
the start of a potential evidence-gap interval. Every later failure preserves
the earliest ticket anchor. Exact pre-submission or rolled-back failures
increase a bounded count. An ambiguous or unclassified failure changes the
whole interval to `COUNT_UNKNOWN`.

A lane is recovered for this interval only after a later-started successful
inner producer attempt is processed on that same lane after the lane's most
recently recorded failure. Every newly recorded failure clears that lane's
prior recovery marker even when its older ticket completes out of order. When
every affected lane has such a recovery, that successful request may attempt
one audit-control transaction. The transaction observes a fresh database
clock, calls the existing `append_audit_gap` function once, validates the
returned maintenance identity, and explicitly commits. The durable interval is
deliberately conservative: it starts at the earliest pre-attempt database
anchor carried by any recorded failure and ends at the fresh database clock
immediately before the gap append. It may begin earlier than a failed attempt,
but it never claims a narrower interval from an anchor observed after that
attempt began or from an untrusted process wall clock.

Only an acknowledged commit clears the frozen interval. A failure known to be
before commit restores the interval for a later successful request. An error
while committing produces permanent `OUTCOME_UNKNOWN` for that controller
instance and is never retried automatically because the accepted function
generates a new event identity on every invocation.

Both supported producer call sites invoke their audit sink from inside a
handler for the original authentication, principal-resolution, or tenant-
boundary denial. If a fixed gap error is created or raised there, Python keeps
the original denial and its traceback in `__context__`; `raise ... from None`
only suppresses display and does not detach that object graph. The two producer
adapters must therefore retain only a closed gap-error kind, leave the original
denial handler, and create a fresh fixed gap error outside that handler.

This slice covers intervals observed and recovered inside one still-running
process. Process death can erase an uncommitted interval and is not disguised
as solved. Restart, empty-recreate store recovery, and externally witnessed
crash intervals remain separate #192 work and must use `COUNT_UNKNOWN` when
their count cannot be known.

## 2. Learning value

The slice proves that the production denial path can turn a bounded in-memory
observation of potentially missing pre-tenant evidence into the already
governed durable `AUDIT_GAP` event without adding a spool, queue, migration,
role, timer, background worker, tenant write, or caller-selected maintenance
operation.

It reduces the demonstrated risk that a still-running process recovers current
audit delivery but leaves its known live-process evidence uncertainty entirely
undocumented. It also establishes the exact ambiguity rule required before
store-loss and process-crash work can safely add independent unknown-count
intervals.

It additionally proves that the fixed failure surface has an exact class,
message, and arguments; has no cause or context; links no original denial,
dependency exception, or prior traceback through its exception chain; and does
not expose runtime-injected protected values through normal formatted
diagnostics.

## 3. Non-goals

This pull request does not change or add:

- any accepted migration, function, relation, type, database role, grant,
  provisioning specification, or structural-readiness rule;
- a replacement or wrapper SQL function for `append_audit_gap`;
- caller-selected producer, component, event kind, database function, SQL,
  credential, retry count, transaction mode, or output schema;
- process-crash, forced-termination, host-loss, restart, store-loss,
  empty-recreate, backup, replica, CDC, or disaster-recovery reconciliation;
- an ungoverned local file, spool, queue, broker, cache, dead letter, telemetry
  event, metric label, or ordinary log fallback;
- overflow observation or closure, `mark_overflow_count_unknown`, overflow
  receipt handling, or reinterpretation of a valid `OverflowAuditAppend` as a
  delivery failure;
- current dynamic-health lane identities, latest-started completion ordering,
  same-lane recovery threshold, `GET /ready`, `GET /health`, or either route's
  response;
- an assertion that current readiness proves every historical gap is durable;
- producer reason vocabularies, HMAC generation or custody, active key version,
  retirement, KMS mutation, IAM, or deadline enforcement;
- retention, normal reader, export, break-glass, temporary login, credential
  creation or revocation, or cumulative disclosure authority;
- authentication, principal, capability, binder, TenantBinding, tenant
  UnitOfWork, post-binding tenant-batched refusal, ordinary 404 behavior, or
  any existing denial type, result, reason mapping, catch boundary, or
  authority; the two producer adapters may only defer the closed fixed gap
  error kind until after the original denial handler exits;
- structural non-reachability of application arguments or trusted objects from
  the fresh exception's own active traceback frame locals; any error-reporting
  integration that captures frame locals is forbidden unless separately
  governed and is not authorized by this pull request;
- a scheduler, periodic probe, timer-driven retry, maintenance loop, web
  endpoint, operator command, or deployment orchestrator;
- a claim that the database or host clock cannot regress, or that deployment
  satisfies the clock premise stated by this contract;
- a complete issue #192 hostile matrix or issue #192 closure;
- issue #176 behavior or any temporal storage/query work; or
- deployment activation, production traffic, release, current/default
  promotion, production readiness, or a security waiver.

## 4. Trust model

### 4.1 Protected assets

- denial remaining in force when producer delivery or gap reconciliation fails;
- honest durable evidence that one live process observed a potential
  pre-tenant audit-evidence gap;
- exact separation between acknowledged, known-uncommitted, and
  commit-ambiguous gap attempts;
- no duplicate automatic append after an ambiguous commit;
- conservative interval bounds from a pre-attempt database-anchor snapshot and
  a fresh database close time rather than an untrusted request or process
  wall-clock value;
- exact same-lane recovery before an affected lane is treated as recovered;
- bounded process memory and bounded work per governed producer attempt;
- continued separation of the audit-control credential from both producer
  credentials and tenant credentials;
- absence of tenant, Party, farm, actor, issuer, subject, request, route,
  credential, token, secret, reason, exception, event identity, HMAC, and
  attacker-controlled identity data from controller state and gap input;
- absence of the original denial, dependency exception, or either prior
  traceback from the fixed error's cause/context chain; exact non-sensitive
  fixed error fields; and normal formatted diagnostics without runtime-injected
  token, principal, tenant, Party, credential, internal-detail, DSN, or
  dependency-exception text;
- the accepted dynamic-health/readiness semantics without a silent threshold
  change; and
- the accepted post-binding switch forbidding this lane after trusted binding.

### 4.2 Trusted components

- the closed #169, #170, #172, #173, and #174 boundaries;
- merged PRs #223–#236 and #314, including the existing producer clients,
  health-observed sinks, runtime startup admission, and fixed two-lane graph;
- `PreTenantAuditClient` as the sole producer append/retry and result-mapping
  authority;
- exact `StoredAuditAppend`, `OverflowAuditAppend`,
  `SecurityAuditUnavailable`, `SecurityAuditRefused`, and
  `SecurityAuditOutcomeUnknown` values from the bound production sink;
- the immutable `security_audit/migrations/0001_initial.sql` definition of
  `append_audit_gap` and its `operational_security_event_identity` result;
- the exact existing `ofarm_security_audit_control_login` credential route and
  database-enforced `session_user` check;
- PostgreSQL transactional behavior: an uncommitted transaction is not made
  durable merely because its session ends, while a commit acknowledgement can
  be lost after the commit became durable;
- PostgreSQL `clock_timestamp()` as the wall-clock authority for the
  conservative interval anchor and end, subject to the explicit deployment
  premise below;
- Python object construction, locks, integer comparison, exact type checks,
  and ordinary `Exception` semantics inside the trusted process; and
- the runtime builder as the only production constructor and lane-composition
  authority.

Deployment must separately establish that the audit database clock does not
regress across a live controller's startup anchor, producer observations, and
gap-close transaction. This repository contract neither measures nor proves
that premise. If deployment cannot establish it, it must not activate this
operation. A fresh close clock at or before the frozen start is always refused
before calling `append_audit_gap`, but that local comparison cannot detect an
advance followed by an unobserved rollback.

### 4.3 Untrusted actors and inputs

- unauthenticated and authenticated callers causing supported pre-binding
  failures at arbitrary rates and concurrency;
- request order, thread scheduling, completion order, cancellation, and
  ordinary dependency exceptions;
- attacker-controlled token, header, route, body, query, network, issuer,
  subject, principal, tenant, Party, actor, and credential bytes;
- exception messages, arguments, causes, contexts, and tracebacks;
- malformed, duplicate, missing, substituted, naive, infinite, or regressing
  database result values;
- connection establishment, transaction setup, statement, lock, rollback,
  close, and commit failures;
- loss of a commit acknowledgement;
- a producer success completing while an older attempt is still in flight;
- additional failures or recoveries while a gap transaction is in flight;
- runtime configuration text other than the already validated exact control
  DSN route; and
- any attempt to use controller types outside the fixed production builder.

No untrusted value selects an event kind, maintenance function, session user,
lane, interval timestamp, count posture, SQL statement, transaction mode,
retry, or controller transition.

### 4.4 Explicitly excluded attacker capabilities

This contract does not claim protection against:

- arbitrary in-process mutation or reflective replacement of trusted private
  objects after construction;
- local source, bytecode, interpreter, dependency, or import substitution after
  repository and package admission;
- compromise of the audit database owner, audit-control credential, operating
  system, Python runtime, PostgreSQL server, or deployment operator;
- malicious modification of accepted migration bytes or database functions;
- a database or host clock that violates the deployment premise;
- guaranteed execution after `BaseException`, process kill, host loss, or
  power loss; or
- recovery of live-process state after process death.

Those exclusions never permit an authorization bypass. Affected requests still
remain denied; the excluded cases limit only the completeness of diagnostic
gap evidence.

## 5. Authority map

| Decision | Sole authority | Rejected alternatives |
| --- | --- | --- |
| Production lanes | Runtime-owned fixed authentication and request-router composition | Request input, configuration registry, plugin, dynamic map |
| Logical attempt identity and lower-bound anchor | Controller-issued lane-local sequence plus the latest trusted database timestamp copied atomically before entering the inner sink | Event UUID, request ID, database transaction ID, object identity, anchor read after the attempt began |
| Producer success or failure | Return or ordinary exception from the already bound health-observed sink | Exception text, readiness polling, synthetic probe, caller report |
| Exact accepted producer result | Existing health-observed sink and `PreTenantAuditClient` result mapping | Duck type, subclass, mapping, caller-created carrier |
| Initial and later conservative anchors | Validated database-owned timestamps from the exact control route or accepted producer result | Request time, process wall clock, HTTP time, file time |
| Gap start | Earliest pre-attempt database anchor carried by any recorded failed ticket in the interval | Shared anchor observed after a failed attempt began, first-failure local time, caller-selected time, retrospective narrowing |
| Affected lanes | Fixed lane of each failed controller attempt | Error message, reason, producer payload, caller selection |
| Same-lane recovery | Greater-ticket success processed after the most recently recorded failure on each affected lane | Numeric maximum from a success processed before a later failure record, cross-lane success, readiness read, elapsed time, operator reset |
| Count posture | Controller classification and signed 64-bit saturation rule | Operator estimate, event query, log count, metrics count |
| Gap end | Fresh `clock_timestamp()` in the exact close transaction | Process clock, last event time supplied by caller, deployment timestamp |
| Durable gap insertion | Existing `ofarm_security.append_audit_gap` | Table DML, generic SQL, new function, producer append function |
| Callable identity | Exact `session_user = ofarm_security_audit_control_login` plus database function check | `current_user`, role membership alone, DSN label, self-attestation |
| Control-session durability | Client-supplied keyword options pin `synchronous_commit=on`, and the client verifies the effective setting before mutation | Provisioned role default alone, DSN option, caller selection, asynchronous commit |
| Commit outcome | Runner-owned `PRE_COMMIT`, `COMMIT_IN_FLIGHT`, and `COMMIT_ACKNOWLEDGED` phase around one explicit PostgreSQL `commit()` | Valid result row alone, connection close, exception class alone |
| Retry eligibility | Exact runner phase before `commit()` began | Timer, generic retry library, caller retry flag, cleanup error after acknowledgement |
| Fixed gap-error propagation | Exact producer adapter records only one of the two trusted fixed class identities, exits the original denial handler, and creates a fresh instance | Reusing the caught object, `raise ... from None` alone, generic exception interception |
| Fixed gap diagnostics | Exact fields, empty cause/context, no linked prior exception, and normal formatting with local capture disabled | Frame-local capture, protected-value rendering, or a structural secrecy claim over arbitrary caller frames |
| Current readiness | Existing two-lane `SecurityAuditHealth` contract | Gap-controller state, gap event presence, operator input |
| Post-binding use | Existing request-router/TenantBinding boundary | Gap state, caller flag, fallback to pre-tenant lane |

There is one durable write path: the accepted function through the exact
control session. There is no alias, fallback, compatibility adapter, alternate
table write, or producer-credential path.

## 6. State machine and ordering

### 6.1 Startup anchor and publication

The runtime constructs one `SecurityAuditGapClient` and one
`SecurityAuditGapController` before constructing either lane wrapper. The client
uses only the existing control DSN. Every initialization and close connection
supplies these exact driver keyword arguments rather than relying on DSN or
provisioned-role defaults:

```text
connect_timeout=5
options="-c statement_timeout=2000 -c lock_timeout=250 -c synchronous_commit=on"
```

The client exposes no override for any of those settings. A conflicting DSN
attempt cannot weaken the keyword-supplied session settings.

Initialization performs one read-only control transaction:

1. require `autocommit = false` and `READ COMMITTED`;
2. read exactly one `(session_user, current_setting('synchronous_commit'),
   clock_timestamp())` row;
3. require the exact control login, exact setting `on`, one finite timezone-
   aware timestamp, and no second row;
4. end the transaction without a maintenance write; and
5. install that timestamp as the controller's initial database anchor.

Any ordinary initialization failure becomes one closed runtime-startup
unavailability and prevents publication. Initialization creates no gap event
because no production producer attempt has yet been admitted.

The controller is passed privately to exactly two lane-bound wrappers. No
controller or client is placed in `app.state`, returned from the runtime, or
accepted from a request.

### 6.2 Attempt tickets and outer composition

Each lane wrapper allocates an immutable ticket before calling the complete
existing health-observed sink. Under one short-held state lock, the controller
increments the fixed lane's positive sequence and copies the current latest
trusted database anchor into that ticket. A ticket contains only its fixed
lane, sequence, and finite aware database-anchor snapshot. It remains on that
wrapper call's stack; the controller keeps no in-flight ticket registry.
Sequence allocation is synchronized and checked before increment; exhaustion
at signed-bigint maximum `9,223,372,036,854,775,807` changes the controller to
fixed `OUTCOME_UNKNOWN`, raises only the closed gap-outcome error, does not
enter the inner sink, and performs no maintenance mutation.

Capturing the anchor before entering the inner sink is mandatory. A different
attempt may commit and advance the shared latest anchor while this attempt is
in flight. That later shared value cannot replace the immutable ticket anchor
if this attempt subsequently fails.

The call order is fixed:

```text
closed producer reason
  -> live-gap wrapper allocates lane ticket
  -> existing health-observed sink allocates its own health attempt
  -> existing correlation-HMAC factory
  -> existing PreTenantAuditClient append/retry
  -> health-observed sink completes current-health state
  -> live-gap wrapper records failure or processes success
  -> original result/error, or a closed gap-control error
```

The outer placement observes HMAC failures as well as append failures and does
not modify the previously approved health transition. On an inner failure the
health sink has already recorded that lane failure. On an inner success it has
already recorded current delivery success before any separate gap transaction.

### 6.3 Failure accumulation

On an ordinary inner exception, the wrapper records the failure under the
controller's short-held state lock and re-raises the exact inner exception. It
does not perform database I/O from the failure path and never replaces the
original audit-delivery error with a reconciliation error.

The first recorded failure creates one open accumulator with:

- `interval_start` equal to that failed ticket's pre-attempt database anchor;
- one affected-lane bit;
- the lane's failed ticket number;
- an exact count of one or unknown posture; and
- no event, request, reason, exception, or correlation field.

Later failures update the same bounded accumulator. The interval start becomes
the earlier of its existing start and each failed ticket's immutable anchor.
For each lane it keeps the greatest failed ticket number and one optional
recovery ticket. Recording any failure clears that lane's recovery ticket
unconditionally, including when an older in-flight ticket completes after a
newer success was processed. The logical failed-attempt count increases once
per wrapper call, not once per `PreTenantAuditClient` database attempt, so the
existing same-event-ID retry remains one logical event.

`SecurityAuditUnavailable` and `SecurityAuditRefused` are exact known-missing
logical attempts because their accepted client paths have no durable producer
commit. `SecurityAuditOutcomeUnknown` makes the interval count unknown. Every
other ordinary exception is also unknown because this boundary cannot prove
its submission phase from exception text or type. Unknown posture stores no
estimated count.

The exact count is capped at PostgreSQL signed-bigint maximum
`9,223,372,036,854,775,807`. The next increment converts the accumulator to
unknown instead of allocating an unbounded Python integer or wrapping. Once
unknown, it remains unknown and the eventual database call supplies
`event_count = 0` and `count_unknown = true`.

`BaseException` is not caught, counted, or converted. Process death and forced
termination remain the separate crash/store-loss boundary.

### 6.4 Success, anchors, and same-lane recovery

An exact successful inner result is processed under the short-held state lock:

- `StoredAuditAppend.observed_at` may advance the latest database anchor;
- `OverflowAuditAppend.bucket.bucket_start` may advance it as a conservative
  database-owned lower bound but may never move it backward;
- a valid overflow result, including `count_unknown = true`, remains producer
  delivery success and does not itself create an `AUDIT_GAP`; and
- no event identity, purge timestamp, bucket identity, or correlation field is
  retained after the transition.

An anchor advanced by this success is available only to tickets allocated
after the advance. It never retimes an already allocated in-flight ticket or
an existing accumulator.

For an open interval, the successful ticket is a recovery only for its own lane
and only when its number is greater than that lane's greatest failed ticket and
the success is processed after the failure that most recently cleared the
lane's recovery marker. Cross-lane success never recovers another lane. A
success that was already processed before an older in-flight failure is later
recorded cannot survive that failure record as recovery; a further
later-started success is required. This conservative rule avoids maintenance
I/O while propagating the original failure and cannot falsely close an
interval.

An interval is close-eligible only when every affected lane has a recorded
later-started success. Readiness polling, elapsed time, dependency recovery,
operator action, or an unaffected lane cannot make it eligible.

### 6.5 One closing snapshot and one concurrent accumulator

One successful wrapper call may claim at most one close-eligible accumulator.
Under the short-held lock it moves the immutable accumulator to one `closing`
slot, clears the `open` slot, and releases the lock before any database I/O.

Controller memory contains at most:

- one immutable closing snapshot;
- one new open accumulator for failures that complete while the close is in
  flight;
- two lane sequence counters plus each accumulator's fixed per-lane greatest
  failure bound and optional recovery ticket;
- one latest database anchor; and
- one closed controller phase.

Each concurrent wrapper call additionally holds one fixed-size immutable
ticket on its own stack. This is bounded per admitted call and does not create
controller-owned state proportional to request history.

No database or network call occurs while the state lock is held. Concurrent
producer calls therefore may finish their existing bounded work while a gap
transaction is in flight. Their short state transitions either update the new
open accumulator or observe that no new gap exists. They never append the same
closing snapshot.

The acknowledging thread does not loop into another close. If a concurrent
accumulator becomes eligible while the first close is in flight, a later
successful producer attempt may claim it. This fixes work at no more than one
gap transaction per successful producer call.

### 6.6 Audit-control transaction and ambiguity

The gap client receives only one controller-created immutable snapshot. It
opens one exact control connection with the keyword settings fixed in section
6.1, requires `autocommit = false`, sets `READ COMMITTED`, and verifies the
exact `session_user` and effective `synchronous_commit = on` before any
maintenance call.

The client owns a closed transaction phase initialized to `PRE_COMMIT`. It does
not use a connection or transaction context manager that can add an implicit
commit. Immediately before entering the one explicit `commit()` method it sets
`COMMIT_IN_FLIGHT`; immediately after that method returns it sets
`COMMIT_ACKNOWLEDGED`. No dependency callback or validation occurs between the
return and the phase advance.

Inside that transaction it:

1. reads exactly one fresh finite aware `clock_timestamp()` as `interval_end`;
2. refuses if `interval_end <= interval_start`;
3. calls exactly
   `ofarm_security.append_audit_gap(interval_start, interval_end,
   event_count, count_unknown)` once;
4. validates one and only one nonzero UUID, finite aware `observed_at`, and
   `purge_after = observed_at + 2,592,000 seconds`;
5. requires `observed_at >= interval_end`; and
6. explicitly commits once.

The client exposes no generic statement, function, interval, count, retry, or
transaction option. It performs no table read, event query, retention,
overflow, reader, export, role, KMS, or tenant operation.

Failure while the phase is `PRE_COMMIT` is known not durable: the transaction
is rolled back or abandoned, the closing snapshot is merged back into the open
accumulator, and the successful producer call raises one fixed
`SecurityAuditGapUnavailable`. A rollback or close failure in this phase does
not change durability because this private connection has no path that can
later commit the abandoned transaction. No automatic retry occurs in that
call. A later successful producer attempt may try the restored interval again.

Any ordinary exception while the phase is `COMMIT_IN_FLIGHT` changes the
controller permanently to `OUTCOME_UNKNOWN`. The closing snapshot is not
restored, merged, cleared, or resubmitted. The current producer call raises one
fixed `SecurityAuditGapOutcomeUnknown`. Every later producer append may still
use its existing HMAC-and-audit path, but the wrapper never performs another
gap mutation in that controller instance and returns the same closed unknown
error after an inner success. This is an accepted availability loss, not an
authorization bypass.

Only `COMMIT_ACKNOWLEDGED` clears the closing snapshot. Its validated
`observed_at` may advance the database anchor. An ordinary connection-close or
final-cleanup exception observed after that phase cannot restore the snapshot
or change the acknowledged result to unknown; cleanup is attempted once, the
fixed client exposes no connection handle, and the wrapper returns the exact
inner producer result. A concurrently opened interval remains independent and
may overlap the acknowledged conservative interval; overlap is honest and
preferable to narrowing or dropping uncertainty.

If a known-precommit failure must be merged with a concurrent open accumulator,
the controller keeps the earlier interval start, unions affected lanes, and
adds exact counts with the same saturation rule. For a lane not affected by the
newer concurrent accumulator, it retains the closing snapshot's failure and
recovery bounds. For a lane affected only by the newer accumulator, it retains
that accumulator's failure and recovery bounds, which already satisfy its
failure-epoch invariant. For every lane affected by both accumulators, the
merge applies exactly:

```text
merged_failure = max(closing_failure, concurrent_failure)
merged_recovery = (
    concurrent_recovery
    if concurrent_recovery is not None
    and concurrent_recovery > merged_failure
    else None
)
```

The concurrent recovery is eligible for that formula only if it was processed
after the concurrent accumulator's most recently recorded failure epoch. The
older closing recovery can never cross a failure recorded after snapshot
detachment. Thus closing failure `10`, concurrent failure `5`, and concurrent
recovery `6` merge to failure `10` with no recovery; concurrent recovery `12`
instead remains recovery for merged failure `10`. Unknown in either input makes
the merged count unknown. The merge performs no I/O and cannot discard a
failure or manufacture recovery from numeric maxima alone.

### 6.7 Error and disclosure protocol

Outward gap-control errors have exact fixed classes and messages. Their
arguments are exactly the fixed-message tuple and contain no other payload. No
original denial, dependency exception, prior traceback, DSN, SQL, role,
timestamp, count, lane, event identity, request value, credential, or
correlation value is rendered or stored in a public response by this boundary.

The client never attaches an underlying exception to a fixed gap error. It
classifies the runner phase, discards the caught exception, completes bounded
cleanup, leaves the exception handler, and only then constructs and raises the
fixed error. That removes the client dependency error, connection, cursor, and
arbitrary payload from the signal's cause/context graph, but it does not defeat
Python attaching an exception already active in a caller's handler. A post-
acknowledgement cleanup error is likewise discarded after its phase is
classified and cannot replace the acknowledged result.

On an inner producer failure, the exact inner error remains primary after the
controller records its bounded state. On an inner producer success followed by
a gap-control failure, the fixed gap error becomes primary. In both cases the
original action remains denied. A successful gap acknowledgement returns the
unchanged exact inner `SecurityAuditAppend`.

The two producer adapters need a second, mechanical detachment because they
call that sink while handling the original denial. Each adapter catches exactly
`SecurityAuditGapUnavailable` and `SecurityAuditGapOutcomeUnknown` from its
audit-sink call and records only the exact trusted class identity
`SecurityAuditGapUnavailable` or `SecurityAuditGapOutcomeUnknown`. It does not
retain the caught object, its traceback, or any value from the original denial.
It then exits the original denial handler and, only outside every exception
handler, constructs and raises a new instance of that recorded fixed class. The
fresh value must have both `__cause__` and `__context__` equal to `None`. It
links no original denial, dependency exception, or either prior traceback
through its exception chain.

When the audit/gap operation succeeds, the adapter re-raises the exact original
authentication, principal-resolution, or tenant-boundary denial from its
existing handler. The adapters do not catch or translate any other audit,
HMAC, producer, authentication, principal, or tenant exception. Their existing
reason maps, denial outcomes, and authority remain byte-for-byte unchanged
except for the minimal control flow needed to defer the two fixed gap-error
kinds. Tests inspect the exact class, fixed message and arguments, cause/context
chain, and any prior exception or traceback linked from that chain. Normal
formatted diagnostics produced with
`traceback.TracebackException.from_exception(error, capture_locals=False)` must contain
none of the runtime-injected token, internal-detail, tenant, Party, principal,
credential, DSN, or dependency-exception canaries.

Like every raised Python exception, the fresh outward error receives its own
active traceback through the producer and upstream caller frames. Those frames
can expose application arguments and trusted objects through
`traceback.tb_frame.f_locals`; this contract does not claim structural
non-reachability from that fresh call stack. This pull request adds no error
collector, logger, or formatter that captures frame locals. Enabling such
capture for these paths is forbidden unless a separate reviewed decision
governs its disclosure, custody, access, and retention.

This contract adds no logger, metric, trace, crash report, output document,
endpoint, or mutable public status object. Tests may inspect closed controller
state through a fixed non-sensitive enum, but production does not expose it to
requests or `app.state`.

### 6.8 Readiness, restart, and incomplete history

The existing `SecurityAuditHealth` object and `/ready` response are unchanged.
They continue to report only current HMAC-and-producer delivery. Gap-controller
state is not a third health lane, does not alter latest-started health ordering,
and is not added to the readiness conjunction. `READY` therefore remains a
current-delivery result and never asserts that a historical gap was committed.

This separation is deliberate. The approved dynamic-health decision explicitly
forbids a silent threshold change and says gap persistence requires its own
decision. This contract adds that persistence outside the health-observed sink
rather than reopening readiness authority.

Controller state is process-local. A clean restart creates a fresh controller
only after the complete existing startup admission and a new database anchor.
It neither imports nor clears the prior process's state. The new process makes
no claim about a previous interval.

Process crash, forced termination, host loss, and empty-store recreation can
erase an unacknowledged accumulator or unknown commit posture. A later
store-loss/crash operation must append its own conservatively witnessed
`COUNT_UNKNOWN` interval when possible. It must not infer that this live
controller completed merely because the new process initialized.

## 7. Invariants and acceptance criteria

### `AUDGAP-001` — exactly two fixed outer lanes

Production has exactly one authentication wrapper and one request-router
wrapper. No request, configuration, plugin, registry, or caller can add,
remove, rename, or select a lane.

### `AUDGAP-002` — startup anchor precedes publication

The runtime is not published unless the exact control route returns one valid
database-owned anchor under the expected session user. Initialization performs
no maintenance mutation.

### `AUDGAP-003` — every governed live attempt is observed once

Each supported pre-binding producer attempt receives exactly one controller
ticket, including its immutable pre-attempt database anchor, before the
existing complete health-observed sink begins. A logical client retry remains
one controller attempt. The successful post-binding path never enters either
wrapper.

### `AUDGAP-004` — bounded non-sensitive state

Controller memory has only fixed lane counters, fixed lane masks, one database
anchor, at most one closing snapshot, at most one open accumulator, bounded
count posture, and a closed phase. Each admitted call holds only one fixed-size
ticket outside controller history. Neither stores a producer reason,
exception, event identity, correlation value, request, credential, principal,
tenant, Party, route, key, DSN, SQL, or attacker-controlled identity.
Both lane sequences and the exact event count stop at signed-bigint maximum;
neither grows as an unbounded Python integer.

The gap client and both producer adapters discard each caught exception before
leaving their respective active handler. The final outward fixed error is newly
constructed only after the producer's original denial handler exits. Its class,
message, and arguments are exact and non-sensitive; its cause and context are
`None`; and its exception chain links no original denial, dependency exception,
or prior traceback. Normal formatting with frame-local capture disabled contains
no runtime-injected protected value. The fresh error's own active traceback
frames are not claimed to be free of application locals, and this boundary
authorizes no collector to capture them.

### `AUDGAP-005` — conservative database-owned interval

Every failure contributes the trusted database anchor copied before that
attempt entered the inner sink, and the interval preserves the earliest such
anchor. A later success cannot retime an older in-flight failure. The close end
is a fresh database clock in the same transaction as the gap append. No request
or process wall-clock timestamp can narrow or select the interval, and
`end <= start` refuses before mutation.

### `AUDGAP-006` — exact count becomes unknown conservatively

Known unavailable/refused logical attempts increment one exact signed-bigint
count. Ambiguous, unclassified, or overflowed count posture becomes unknown
irreversibly and is written only as `(event_count=0, count_unknown=true)`.

### `AUDGAP-007` — recovery is same-lane, later-started, and later-observed

Every affected lane requires a successful ticket greater than its greatest
failed ticket and processed after its most recently recorded failure. Every
failure record clears that lane's previous recovery marker. Cross-lane success,
prior out-of-order success, numeric maximum alone, readiness, elapsed time, and
operator action cannot close the interval.

### `AUDGAP-008` — at most one fixed gap call per successful attempt

One successful wrapper call may claim and submit at most one immutable closing
snapshot. The client calls only `append_audit_gap` once and has no automatic
retry or caller-selected operation.

### `AUDGAP-009` — commit acknowledgement is the only success

A validated function result without an acknowledged explicit commit is not
success. The client pins and verifies `synchronous_commit=on` before mutation.
Known-precommit failure restores the interval. A commit exception is permanent
outcome unknown and never permits resubmission in that process. Once the
explicit commit returns, later cleanup failure cannot revoke success, restore
the interval, or cause a duplicate append.

### `AUDGAP-010` — concurrency cannot duplicate or drop an interval

At most one thread owns the closing snapshot. Concurrent failures use one
separate bounded accumulator. A precommit merge preserves the earlier start,
all affected lanes, greatest failure bounds, and conservative count posture.
For a lane present in both accumulators it preserves the concurrent
accumulator's recovery only when the recovery was processed after its last
failure epoch and its ticket is greater than the merged maximum failure bound.

### `AUDGAP-011` — current delivery semantics remain unchanged

Stored and overflow results remain producer successes. The existing health
lanes, readiness threshold, result ordering, HTTP responses, and current-health
claims are unchanged. Gap state is never presented as readiness or historical
completeness.

### `AUDGAP-012` — audit degradation never authorizes

Producer failure, gap-client failure, clock refusal, count saturation, and
outcome unknown never authenticate, resolve a principal, mint a capability,
enter a tenant, select tenant storage, invoke a tenant batch, fall back to
ordinary logs, or change a denial into access.

### `AUDGAP-013` — database authority remains exact and narrow

Only the exact audit-control session may call the existing function. No
producer, reader, retention, export, tenant, application, migrator, or owner
credential is added, granted, assumed, or reused. Every control connection
pins fixed statement, lock, connection, and synchronous-commit settings through
client-owned keyword arguments and verifies the effective durability setting.

### `AUDGAP-014` — restart is not reconciliation

The controller does not claim persistence across `BaseException`, process
death, host loss, or restart. A new startup anchor cannot clear, acknowledge,
or reconstruct a prior interval.

### `AUDGAP-015` — no migration or alternate evidence store

The accepted numbered migrations and function semantics remain byte-identical.
No file, queue, cache, log, metric, replica, backup, CDC stream, or tenant table
stores gap-controller state or evidence.

## 8. Production-reachable negative cases

| Invariant | Supported production entry and minimal counterexample | Required result |
| --- | --- | --- |
| `AUDGAP-001` | Build the production runtime with the fixed two producers; attempt to supply a third lane through environment or request data. | No selectable lane surface exists; startup graph remains exactly two wrappers. |
| `AUDGAP-002` | Start with the control DSN resolving to the reader login, a duplicate clock row, a naive/infinite time, or an unavailable service. | Startup refuses before runtime publication and performs no gap append. |
| `AUDGAP-003` | A producer append loses its first commit acknowledgement and performs the accepted same-ID retry. | The wrapper records one logical success or failure, never two attempts. |
| `AUDGAP-004` | Through both `AuthenticationAuditProducer.authenticate()` and `RequestRouterAuditProducer._audited_unit_of_work()`, inject token, internal-detail, tenant, Party, principal, credential, DSN, and dependency canaries at runtime, then cause each fixed gap error and format it with local capture disabled; also exhaust a lane sequence and the exact count at signed-bigint maximum. | Each adapter exits the original handler and raises a fresh exact fixed class with fixed message/arguments and cause/context `None`; its exception chain links no prior exception or traceback; normal formatted diagnostics contain no runtime canary; the test makes no structural claim about the fresh traceback's frame locals; both numeric fields refuse unbounded growth and state size remains fixed. |
| `AUDGAP-005` | Allocate an older ticket, let a later attempt advance the shared database anchor, then complete the older attempt as a failure; also recover with a fresh end equal to or before the frozen anchor, or supply a request timestamp. | The interval starts at the older ticket's pre-attempt anchor; the later anchor cannot narrow it; an invalid end prevents the function call; request time is unused. |
| `AUDGAP-006` | Produce one `SecurityAuditOutcomeUnknown`, one unexpected ordinary exception, or one increment beyond bigint maximum. | Whole interval becomes unknown; no estimate or wrapped count is written. |
| `AUDGAP-007` | Fail authentication, then succeed only on request-router; or process a later-ticket auth success before an older in-flight auth failure is recorded. | The cross-lane success is ignored; the later failure record clears the prior auth recovery; the interval remains open until a further greater-ticket auth success is processed. |
| `AUDGAP-008` | Make two lanes recover concurrently for one interval. | Exactly one thread claims one snapshot and at most one function call occurs per successful wrapper call. |
| `AUDGAP-009` | Attempt to set `synchronous_commit=off` in the DSN; return a valid maintenance row and raise from explicit commit; separately let commit return and then raise from connection close. | Keyword-supplied options and effective-setting verification require `on`; commit exception produces fixed outcome unknown with zero automatic retry; post-acknowledgement cleanup failure preserves success and never restores or duplicates the gap. |
| `AUDGAP-010` | On a known-precommit merge, supply closing failure `10`, concurrent failure `5`, and concurrent recovery `6`; repeat with concurrent recovery `12`, each processed after the concurrent failure epoch. | The first merge has failure `10` and no recovery; the second has failure `10` and recovery `12`; no failure is lost, numeric maxima do not manufacture recovery, and no duplicate closing owner exists. |
| `AUDGAP-011` | Return a valid `OverflowAuditAppend(count_unknown=true)` with no existing failed interval. | Producer remains successful; no `AUDIT_GAP` call; current health behavior is unchanged. |
| `AUDGAP-012` | Make gap closure unavailable during missing-credential or binder-refusal handling. | The request remains denied; no principal, tenant UnitOfWork, tenant write, or ordinary-log fallback occurs. |
| `AUDGAP-013` | Point the control route at a producer/reader login, alter `current_user` through role state, or supply conflicting DSN session options. | Exact `session_user` and effective `synchronous_commit=on` checks refuse before maintenance mutation; client-owned keyword bounds cannot be weakened. |
| `AUDGAP-014` | Kill a process after it records a failure but before a close; construct a fresh runtime. | New controller has only a new anchor and makes no claim about the prior interval. |
| `AUDGAP-015` | Search the final diff and runtime writes for a migration, local spool, file, tenant table, metrics path, alternate SQL, error collector, or frame-local capture. | Exact path and import gates reject the change. |

Tests may inject deterministic dependency outcomes at public constructors and
supported producer entry points. They must not manufacture a Blocker by
mutating private state. Controlled clocks, connections, and barriers are test
dependencies for the accepted public controller/client constructors, not
production authority inputs.

## 9. Proposed architecture and smallest change

### 9.1 Types and ownership

One new `kernel/security_audit_gap.py` owns:

- `SecurityAuditGapController` — one fixed-size shared state machine;
- two controller-created `LiveGapObservedAuditSink` instances bound to fixed
  lanes and existing inner health-observed sinks;
- immutable private attempt-with-anchor, accumulator, and closing-snapshot
  values;
- one `SecurityAuditGapClient` bound to the exact control DSN route;
- closed `SecurityAuditGapState`, `SecurityAuditGapUnavailable`, and
  `SecurityAuditGapOutcomeUnknown` values; and
- exact timestamp, result, count, transaction-phase, merge, and ambiguity
  validation.

`kernel/security_audit_runtime.py` constructs the client/controller after the
existing startup authorities are validated, initializes the database anchor,
and wraps the two existing health-observed sinks.
`kernel/authentication_audit.py` and `kernel/request_router_audit.py` each add
one mechanical branch that catches only the two fixed gap errors, retains only
their exact trusted class identity until the active original-denial handler has
exited, and raises a fresh fixed error. No producer reason map, denial type,
denial result,
`PreTenantAuditClient`, health state, API route, application state, or runtime
configuration field is changed.

### 9.2 Data flow

Authentication failure:

```text
supported AuthenticationError or PrincipalResolutionError
  -> existing closed reason mapping
  -> fixed authentication live-gap wrapper starts ticket
  -> existing authentication health-observed sink
  -> existing HMAC and producer append/retry
  -> inner error: record bounded failure, re-raise inner error
  -> inner success: process same-lane recovery
       -> no eligible gap: return unchanged result
       -> eligible gap: one control transaction
            -> acknowledged: return unchanged result
            -> known precommit failure: restore; fixed unavailable kind
            -> commit ambiguity: terminal fixed outcome-unknown kind
  -> audit/gap success: re-raise exact original denial in its handler
  -> fixed gap kind: leave original handler; create and raise fresh fixed error
```

Request-router pre-binding failure uses the same flow with the fixed
request-router lane. Successful TenantBinding yields the tenant UnitOfWork and
never enters this flow.

### 9.3 Why this is the minimum coherent design

Calling `append_audit_gap` from an operator command with caller-supplied times
or counts would create a new self-attested authority and would not observe the
production failures named by #192. Adding state only inside
`PreTenantAuditClient` would miss HMAC failures. Adding it inside each producer
would duplicate concurrency and ambiguity policy. Changing the health object
would reopen an independently approved readiness threshold.

One outer wrapper around each complete existing health-observed sink sees the
supported operation without changing its producer, transport, retry, or health
authority. One shared controller can combine overlapping lane intervals while
retaining only fixed-size non-sensitive state. The existing database function
already owns the durable event shape and role check, so no migration or new SQL
authority is justified.

The outer wrapper cannot detach the original denial that Python automatically
adds as context when the wrapper raises from inside a producer's denial
handler. A runtime wrapper or `raise ... from None` would only hide display, not
remove the retained object graph. The two existing call sites are therefore the
smallest coherent place to record a closed gap-error kind, exit the handler,
and raise a fresh fixed error. Those mechanical branches do not decide whether
authentication, principal resolution, or tenant binding succeeds and do not
change any denial authority.

A background reconciler is not smaller: it requires lifecycle, wakeup,
shutdown, retry, and deployment policy and would need another channel to learn
process-local failures. A local spool would contradict the accepted V1
boundary. Synchronous reconciliation on an actual later producer success gives
one bounded trigger and one supported denial path without inventing either.

The conservative earliest pre-attempt ticket-anchor interval is preferable to
a process wall clock. It can overstate the possible interval after quiet
traffic, but its exact or unknown count states how many logical failures were
observed. It never pretends to know a narrower failure timestamp that the
isolated database did not supply.

## 10. Elegance audit

- **Producer-delivery sources of truth:** one existing client per fixed lane;
  unchanged.
- **Current-health sources of truth:** one existing health object; unchanged.
- **Live-gap sources of truth:** one shared controller.
- **Durable gap write paths:** one accepted database function.
- **Wall-clock authorities:** one audit-database clock.
- **Attempt-order authorities:** two fixed lane-local controller counters, with
  one latest trusted database-anchor snapshot copied into each admitted ticket
  and one failure-cleared recovery marker per affected lane.
- **Closing owners:** at most one immutable snapshot.
- **Concurrent accumulation owners:** at most one bounded accumulator.
- **Compatibility surfaces introduced:** none.
- **Producer-adapter changes:** two mechanical fixed-error deferral sites; no
  denial mapping or authority change.
- **Diagnostic capture surfaces introduced:** none; frame-local capture remains
  forbidden without a separate reviewed boundary.
- **Configurable policy introduced:** none.
- **Generic SQL/function selectors introduced:** none.
- **Background abstractions introduced:** none.
- **New credentials or grants:** none.
- **Deletions:** none; no obsolete gap caller or fallback exists.
- **Clean rewrite assessment:** a new small module is clearer than distributing
  correlated state across the client, health object, and two producers. A
  repository-wide or migration rewrite is not justified.

The two lane wrappers are created by the controller because they share one
security transition. They are not a plugin system, optional service bag, or
public registry.

## 11. Pull request and approval boundary

### 11.1 Exact technical path allowlist

The final implementation may change only these paths:

1. `docs/rfcs/OFARM_Security_Audit_Live_Gap_Reconciliation_RFC_v0_1.md`
2. `kernel/security_audit_gap.py`
3. `kernel/security_audit_runtime.py`
4. `kernel/authentication_audit.py`
5. `kernel/request_router_audit.py`
6. `kernel/README.md`
7. `kernel/tests/test_security_audit_gap.py`
8. `kernel/tests/test_security_audit_runtime.py`
9. `kernel/tests/test_authentication_audit.py`
10. `kernel/tests/test_request_router_audit.py`
11. `conformance/rewrite_architecture_check.py`
12. `conformance/review_baseline_test_inventory.json`

The Phase A review head changes only path 1. Phase B may use a strict subset of
the remaining paths. The inventory is a required mechanical change only when
the focused implementation tests add collected nodes.

### 11.2 Explicitly unchanged paths and authorities

Every unlisted path is immutable for this decision, especially:

- `security_audit/migrations/**`;
- all `deployment/postgresql/**` production and test paths;
- `kernel/security_audit.py`, `kernel/security_audit_client.py`, and
  `kernel/security_audit_health.py`;
- `kernel/application_runtime.py`, `kernel/api.py`, and every HTTP route;
- correlation-HMAC generation, posture, retirement, and KMS modules;
- authentication, principal, capability, binder, tenant, signing, and
  authorization modules;
- retention, overflow, reader, export, recovery, and store-loss modules;
- `docs/adr/**`, `reference/**`, workflow, dependency, provisioning, deployment,
  and issue #176 paths.

Within the two listed producer adapters, existing reason maps, handled denial
classes, return values, authorization decisions, `TenantBinding` behavior, and
all non-gap exception behavior are immutable. The only permitted edits are the
exact two-class deferral branches described in section 6.7. Catching a generic
exception, changing a denial mapping or type, or retaining a denial/gap
exception object stops Phase B and requires re-review and a new approval.

No accepted numbered migration may be edited. No database authority defect is
asserted by this contract. A demonstrated defect would require a separately
approved forward migration and must not be appended to this pull request.

### 11.3 Dependencies

- Reviewed base `6c061c4b9c12ac0c1141cf97fd6cf569f64ead00`.
- #169, #170, #172, #173, and #174 are closed as completed.
- Merged PRs #223–#236 provide the accepted database, control function,
  producer, HMAC, runtime, and bounded-I/O foundations.
- Merged PR #314 provides the exact inner health-observed sinks and fixed lane
  semantics; this contract does not amend them.
- Merged PR #316 closes the separate HMAC-retirement repository executor and
  is not invoked or changed here.
- Completed #252/#254 mutex evidence is not recreated.
- No open or stacked pull request is a prerequisite.

### 11.4 Reviewer non-requirements

Reviewers must not require this pull request to:

- persist controller state across process death;
- add a crash witness, PID/process identity, lease, heartbeat, host agent,
  orchestrator, file, or spool;
- implement store-loss or empty-recreate recovery;
- change the dynamic-health threshold or expose gap status through `/ready`;
- invoke `mark_overflow_count_unknown` or change overflow closure;
- add a scheduler, loop, timer, active probe, command, or endpoint;
- add a migration, role, grant, new function, or database result shape;
- implement retention, reader/export, break-glass, or temporary-login work;
- change HMAC custody, retirement, IAM, or deployment ownership;
- add the final real-ASGI/PostgreSQL cross-slice hostile matrix;
- deploy, release, operate, or claim production readiness; or
- close issue #192.

Those are separate trust boundaries or later evidence and cannot be appended
merely to clear this decision.

### 11.5 Follow-ups

Issue #192 continues to own separate decisions for:

- process-crash and forced-termination `COUNT_UNKNOWN` reconciliation;
- verified empty-recreate/store-loss operation and its independent honest gap;
- ambiguous overflow-bucket `mark_overflow_count_unknown` orchestration before
  deployed overflow scheduling;
- dual-approved, time-bounded break-glass export and temporary-login closure;
- deployment clock-health evidence and activation policy;
- external supervision of permanent gap `OUTCOME_UNKNOWN`; and
- remaining real-ASGI/PostgreSQL cross-slice hostile closure evidence.

No new issue is required merely to duplicate those existing parent criteria.

### 11.6 Stop and reapproval conditions

Stop and require a new decision version before implementation or merge if work
would:

- change the two fixed lanes or their outer placement;
- change the conservative database-anchor interval or exact/unknown count rule;
- permit caller-selected interval, count, lane, function, SQL, retry, or
  transaction behavior;
- automatically retry after commit ambiguity;
- add persistent state outside the accepted audit event;
- change current-health/readiness state, threshold, ordering, or output;
- catch anything other than the two exact fixed gap errors in either producer
  adapter, change an existing denial map/type/outcome, or raise a fixed gap
  error before the original denial handler has exited;
- add an error collector, logger, formatter, or diagnostic hook that captures
  frame locals or protected runtime values;
- add process-crash, store-loss, overflow, export, break-glass, retention, KMS,
  IAM, tenant, authorization, deployment, or issue #176 authority;
- edit a migration, role, grant, function, provisioning path, or any unlisted
  path;
- name a different draft pull request; or
- authorize deployment, release, production access, issue closure, or a
  security waiver.

Meaning-preserving wording, test clarity, fixed error wording, line-budget
headroom, and mechanical inventory regeneration inside the allowlist do not
require a new version.

## 12. Provisional design record

**Not provisional.**

The live-process controller is intentionally one independently useful source
of gap evidence, not a temporary substitute for crash or store-loss
reconciliation. A later external witness may append separate overlapping
`COUNT_UNKNOWN` intervals after process or store loss without changing this
controller's attempt ordering, database-anchor rule, count classification, or
commit ambiguity protocol.

Deployment remains unauthorized until the database-clock premise, process
supervision, permanent `OUTCOME_UNKNOWN` handling, crash/store-loss coverage,
and the other remaining #192 operations are independently governed. That
deployment gap limits activation; it does not make this repository mechanism
disposable.

Evidence requiring redesign would be a demonstrated inability to preserve the
accepted same-lane producer ordering at the outer sink, PostgreSQL behavior
that permits an unacknowledged pre-commit transaction to become durable, or a
requirement for durable process identity to distinguish live controllers. Such
evidence requires a new decision and cannot be patched into this version.

## 13. Traceability and verification

| Invariant | Owning implementation | Negative test/evidence | Smallest verification |
| --- | --- | --- | --- |
| `AUDGAP-001` | gap controller and runtime composition | configured/third lane has no constructor path | exact factory and architecture test |
| `AUDGAP-002` | gap client initialization and runtime builder | wrong user, malformed clock, wrong effective synchronous-commit setting, connection failure | focused client plus runtime publication tests |
| `AUDGAP-003` | lane wrapper | accepted ambiguous producer retry | one-ticket/one-count deterministic test |
| `AUDGAP-004` | controller state, gap client, and both producer adapters | runtime-canary original denials and dependency exceptions through both supported producer entry points; lane-sequence and count saturation | exact fields, cause/context and linked-prior-exception checks, normal formatting without local capture, state-shape, and bounded-field tests |
| `AUDGAP-005` | ticket anchor, controller merge, and gap-client clock validation | older in-flight failure after a later anchor advance; equal/regressing end; request-time injection | deterministic barrier and no-function-call clock tests |
| `AUDGAP-006` | failure classifier and count merge | unavailable, refused, outcome unknown, foreign exception, bigint edge | table-driven count tests |
| `AUDGAP-007` | per-lane failure-cleared recovery epoch | cross-lane recovery and later-ticket success processed before an older failure | deterministic barrier tests |
| `AUDGAP-008` | close claim and gap client | simultaneous recovery | exact function-call count test |
| `AUDGAP-009` | exact connection options and explicit three-phase transaction runner | DSN requests `synchronous_commit=off`; valid result then commit error; acknowledged commit then close error | effective-setting, outcome-unknown/no-retry, and post-ack cleanup tests |
| `AUDGAP-010` | closing/open slots and ordered epoch merge | exact closing/concurrent failure/recovery tickets `10/5/6` and `10/5/12` after the concurrent failure epoch | deterministic negative and positive merge/concurrency tests |
| `AUDGAP-011` | outer wrapper and unchanged health sink | stored/overflow success, gap failure, readiness snapshot | focused health/runtime regression tests |
| `AUDGAP-012` | producer composition | credential/binder denial plus gap failure | runtime denial/no-tenant-path tests |
| `AUDGAP-013` | fixed connection options, gap client, and existing SQL function | producer/reader session, role-state substitution, and conflicting DSN options | unit and live PostgreSQL role/session-setting tests |
| `AUDGAP-014` | runtime construction and docs | discard controller, construct fresh runtime | restart non-claim test |
| `AUDGAP-015` | architecture/path gate | alternate store/import/SQL, migration edit, error collector, or frame-local capture | exact diff and import-budget checks |

### 13.1 Phase A verification gates

- The draft diff contains only this RFC.
- The RFC names the exact base, one primary trust boundary, authority map,
  state machine, stable invariants, production-reachable negatives, exact path
  allowlist, reapproval triggers, and claim limits.
- The RFC explicitly preserves the accepted dynamic-health/readiness contract.
- `python3 conformance/ofarm_pkg_contract_check.py` passes.
- `git diff --check` passes.
- Independent exact-head Phase A review reports no demonstrated Blocker before
  a live decision card is shown.

### 13.2 Prospective Phase B verification gates

After exact approval, implementation must pass:

- focused controller/client/wrapper tests for every `AUDGAP-*` invariant;
- deterministic concurrent and out-of-order completion tests using supported
  constructors and barriers, without private-state mutation;
- exact authentication and request-router producer-entry tests proving that
  successful audit/gap handling preserves the original denial and that each
  fixed gap failure is freshly raised only after its original handler exits;
- exact fixed-error class, message, arguments, cause, and context checks;
- exception-chain inspection proving no original denial, dependency exception,
  or prior traceback is linked from the fresh fixed error;
- normal formatted diagnostics with `capture_locals=False` proving runtime-
  injected token, internal-detail, tenant, Party, principal, credential, DSN,
  and dependency-exception canaries are absent;
- exact path and import checks proving this slice adds no error collector,
  logger, formatter, or other frame-local capture surface;
- exact negative `10/5/6 => unrecovered` and positive `10/5/12 => recovered`
  merge tests after the concurrent failure epoch;
- live PostgreSQL tests for the exact control login, wrong-login refusal,
  keyword-pinned and effective `synchronous_commit=on`, conflicting DSN
  options, acknowledged gap fields, rollback, and commit-ambiguity posture;
- production runtime tests proving startup initialization, two fixed wrappers,
  denial preservation, post-binding exclusion, and unchanged readiness;
- existing security-audit client, health, producer, runtime, overflow,
  retention, reader, HMAC-posture, and HMAC-retirement focused suites;
- Ruff for every changed Python path;
- `python3 conformance/rewrite_architecture_check.py`;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- exact review-baseline inventory regeneration and validation;
- `git diff --check`;
- exact final path rejection for every unlisted path; and
- complete exact-head hosted conformance, native verifier amd64, native
  verifier arm64, and canonical-index gates.

No skipped environment-backed test is affirmative evidence. The pinned hosted
PostgreSQL/Python environment remains authoritative for the complete baseline.

Before merge, the exact implementation head requires bounded review against
this approved contract. A Blocker must name the violated invariant, supported
production entry point, in-scope actor, exact transition, required
preconditions, material consequence, and minimal counterexample.

## 14. Open decisions and review disposition

### 14.1 Open material decisions

None. Version 1 fixes:

- two fixed outer lane wrappers;
- one database anchor before runtime publication;
- conservative earliest pre-attempt ticket-anchor-to-close-clock intervals;
- one logical count per wrapper attempt;
- exact known versus unknown failure classification and bigint saturation;
- later-started and later-observed same-lane recovery for every affected lane;
- at most one closing snapshot plus one concurrent accumulator;
- at most one gap transaction per successful producer attempt;
- known-precommit restoration, permanent no-retry commit ambiguity, and
  post-acknowledgement cleanup that cannot revoke success;
- merged recovery revalidation against the greatest failure bound;
- keyword-pinned and verified synchronous commit;
- context-detached propagation of the two fixed gap errors through the two
  accepted producer adapters, with exact fields and safe normal formatting but
  no impossible structural secrecy claim for the fresh traceback's frame
  locals, without changing denial authority;
- no current-health/readiness change; and
- live-process scope with an explicit restart/crash non-claim.

Changing any of these requires version 2.

### 14.2 Review disposition

- **Blockers:** [Review
  4946525305](https://github.com/samovers/OFARM2/pull/317#pullrequestreview-4946525305)
  reported context retention at the two producer call sites and recovery below
  a merged failure bound. [Review
  4946639753](https://github.com/samovers/OFARM2/pull/317#pullrequestreview-4946639753)
  accepted the merge, synchronous-commit, and cause/context corrections but
  found that the RFC overclaimed structural secrecy from the fresh exception's
  own traceback frame locals. This revision narrows `AUDGAP-004` to exact fixed
  fields, no cause/context or linked prior exception, and safe normal formatting
  while explicitly governing frame-local capture separately. [Review
  4946752582](https://github.com/samovers/OFARM2/pull/317#pullrequestreview-4946752582)
  accepted the corrected exact head with zero remaining Phase A Blockers. Its
  two Phase B test interpretations require exact fixed-class identity and
  runtime-injected formatting canaries; both are binding implementation gates.
- **Follow-ups:** the separately governed remaining #192 boundaries in section
  11.5.
- **Preferences:** the review's explicit keyword-level
  `synchronous_commit=on` pin is incorporated and verified before mutation.

Those Phase B prerequisites were satisfied by the evidence recorded in section
16. Repository implementation remains bounded to the named pull request and
exact path allowlist.

Once prospective Phase B acceptance criteria pass and no demonstrated Blocker
remains, merge the approved pull request. New ideas, Preferences, and
non-blocking hardening become Follow-ups and do not reopen review.

## 15. Phase A approval boundary

This RFC is not approval. It authorizes no implementation or external action.

After the complete RFC is published in its named draft pull request and an
independent Phase A review reports no demonstrated Blocker, the assistant may
show one complete live decision card for:

`ISSUE192-SECURITY-AUDIT-LIVE-GAP-RECONCILIATION-001`, version `1`.

The only valid approval form will be the entire visible text of a later task
user message in the same Codex task:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-LIVE-GAP-RECONCILIATION-001 version 1.
```

Generic approval, GitHub activity, credentials, review comments, another task,
or a summary is not approval. A later stop-like user message pauses work. Any
semantic contract/card change, authority change, path-envelope change, or named
pull-request change requires a new decision version.

A valid approval authorizes repository implementation only within the named
draft pull request and exact path envelope. It does not authorize deployment,
release, production access or operation, issue #192 closure, current/default
promotion, a database migration, credential change, or security waiver.

## 16. Approval evidence

- **Decision:** `ISSUE192-SECURITY-AUDIT-LIVE-GAP-RECONCILIATION-001`,
  version `1`.
- **Codex task:** `019ff570-c253-7d02-bbda-1ad8f4143f00`.
- **Complete live card:** stable reference `item-1743` in that task.
- **Task-user approval:** stable reference `item-1744`, observed as the later
  task-user message in the same task.
- **Exact approval sentence:** `I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-LIVE-GAP-RECONCILIATION-001 version 1.`
- **Implementation PR:** `https://github.com/samovers/OFARM2/pull/317`.
- **Observed role and order:** the assistant displayed the complete card first;
  the task user then supplied the exact sentence as the entire visible message.
- **Evidence posture:** these task references and role/order observations are
  provisional AI-attested evidence of the task user's decision. The task-user
  message remains authority. This record is not deployment authority,
  production authority, or an independently verifiable identity claim.
