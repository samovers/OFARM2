# OFARM Security-Audit Dynamic Health and Readiness — Phase A Contract v0.1

**Status:** Phase A draft under review; Phase B repository implementation,
deployment, release, and production operation are not authorized

**Draft pull request:** this contract will be updated with the stable draft
pull-request URL immediately after that pull request is created

**Contract identity:**
`ofarm2.security-audit-dynamic-health-readiness.v0.1`

**Proposed decision identity:**
`ISSUE192-SECURITY-AUDIT-DYNAMIC-HEALTH-READINESS-001`, version `1`

**Issue:** #192

**Reviewed base:** `061ec320be299062a3cc56aac656e1fcb535d771`

**Primary trust boundary:** production runtime observation of pre-tenant
security-audit delivery health and its HTTP readiness decision

**Phase A review-head boundary:** this RFC only

**Maximum final pull request boundary:** this RFC; one bounded audit-health
module; mechanical producer, runtime, application, and HTTP composition; focused
tests; minimal Kernel documentation; architecture-budget registration; and the
mechanically regenerated review-baseline test inventory only

## 1. Problem and goal

The production runtime currently proves the security-audit database structure,
route identities, service separation, correlation-HMAC lifecycle, and one KMS
MAC preflight before publishing the application. After publication, the two
pre-tenant producers remain synchronous and fail closed, but the runtime does
not retain a safe observation of their delivery results. `GET /health` therefore
continues to return immutable startup metadata even after a producer has just
failed to create a correlation HMAC or complete an audit append.

This task establishes one bounded, process-local readiness decision with two
fixed lanes:

- `AUTHENTICATION`;
- `REQUEST_ROUTER`.

Each lane starts ready only behind the already accepted production startup
admission. Every governed pre-tenant audit attempt receives a monotonically
ordered lane-local attempt number before HMAC work begins. A completed attempt
has exactly one health result:

- a validated `StoredAuditAppend` or `OverflowAuditAppend` is `SUCCEEDED`;
- every ordinary exception before such a result is `FAILED`.

The most recently started completed attempt for each lane owns that lane's
current readiness. One failed completion makes the lane not ready. Only a
later-started successful completion on that same lane restores it. Overall
security-audit readiness is ready only when both lanes are ready.

The production application adds `GET /ready`. It performs no dependency I/O
and discloses only the fixed overall readiness token. It returns HTTP 200 for
`READY` and HTTP 503 for `NOT_READY`. Existing `GET /health` remains a liveness
and immutable-runtime-metadata surface.

This readiness decision is observational. It does not prove lossless delivery,
record or reconcile an `AUDIT_GAP`, close an overflow bucket, establish
continuous reachability, or clear evidence uncertainty. A restart creates a
new process observation only after full startup admission; it is not gap
reconciliation.

## 2. Learning value

The slice proves that the production denial path can publish a current,
non-sensitive readiness result from the same HMAC-and-append operation that
actually carries pre-tenant evidence. It reduces the demonstrated risk that an
application remains externally ready after its own bounded audit operation has
failed, without creating a second audit authority or widening another #192
operation.

## 3. Non-goals

This pull request does not change or add:

- migrations, functions, relations, database roles, grants, provisioning, or
  structural-readiness policy;
- producer reason vocabularies, append fingerprints, same-ID retry, database
  quotas, overflow receipts, or transaction semantics;
- `AUDIT_GAP` creation, unavailable-interval persistence, process-crash
  reconciliation, count accounting, or gap closure;
- overflow observation or closure, including `mark_overflow_count_unknown`;
- correlation-HMAC key creation, rotation, retirement, destruction,
  deadline enforcement, IAM, or deployment ownership;
- retention, normal reader, export, break-glass, temporary login, store-loss,
  empty-recreate, backup, replica, CDC, or recovery operations;
- active readiness probes, synthetic security events, background threads,
  schedulers, timers, periodic KMS calls, periodic database calls, queues,
  spools, files, caches, telemetry, metrics, or dead letters;
- an external clock-health authority or a claim that deployment satisfies the
  bounded-reader clock prerequisite;
- authentication, principal, capability, binder, tenant UnitOfWork, or
  post-binding tenant-batched authority;
- ordinary 404 auditing or a new public diagnostic/support API;
- a change to `GET /health`, `/manifest`, governed-route blocking, or the
  immutable `app.state` posture;
- issue #176 behavior or any temporal storage/query work;
- deployment activation, production traffic, production readiness, release,
  current/default promotion, or a security waiver; or
- a claim that `READY` means no historical audit gap exists.

## 4. Trust model

### 4.1 Protected assets

- denial remaining in force when HMAC or audit delivery fails;
- an honest readiness result derived from actual supported producer outcomes;
- separation between authentication and request-router delivery health;
- exact ordering under concurrent and out-of-order completions;
- bounded memory and constant-time readiness observation;
- absence of event, credential, principal, tenant, Party, request, route,
  correlation, exception, database, and key material from health state and
  readiness output;
- the existing startup, database, HMAC, retry, and post-binding authorities;
  and
- the rule that overflow aggregation is an acknowledged governed result rather
  than a caller-invented failure.

### 4.2 Trusted components

- the accepted #172, #173, and #174 boundaries and merged #192 producer/runtime
  stack;
- existing production startup admission in `kernel/security_audit_runtime.py`;
- `PreTenantAuditClient` as the sole append/retry owner and source of validated
  `StoredAuditAppend` or `OverflowAuditAppend` results;
- the fixed `AuthenticationAuditProducer` and `RequestRouterAuditProducer`
  reason mappings;
- Python object construction, `threading.Lock`, integer ordering, and normal
  exception semantics inside the trusted process;
- the production runtime's private route closures; and
- FastAPI/Starlette HTTP status and JSON response handling.

The readiness state trusts a normally returned validated append result to mean
that the existing client completed its governed database protocol. It does not
reinterpret database rows, KMS responses, or overflow policy.

### 4.3 Untrusted actors and inputs

- every credential and request that can reach the supported production
  authentication or tenant-boundary entry points;
- hostile request volume and concurrent attempts;
- the timing and completion order of HMAC, network, and database operations;
- ordinary exceptions from the HMAC factory or append client;
- a malformed result returned across the audit-appender protocol seam;
- repeated and concurrent readiness requests;
- mutation of public `app.state` values by application-adjacent code; and
- process restarts and the absence of a prior process's in-memory state.

Request values cannot choose a lane, readiness state, sequence, threshold,
recovery rule, response shape, or HTTP status.

### 4.4 Explicitly excluded attacker capabilities

The following are out of scope:

- arbitrary in-process mutation or code execution;
- direct private-field mutation;
- local source substitution or filesystem mutation;
- compromised dependencies, Python runtime, operating system, or process
  scheduler;
- memory corruption;
- operator, database-owner, superuser, KMS administrator, or deployment-host
  compromise;
- forced process termination and `BaseException` paths that prevent controlled
  completion; and
- simultaneous corruption of the trusted append result and the health module.

Ordinary dependency exceptions, supported concurrency, stale completion order,
hostile volume, and readiness polling remain in scope.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Fixed health lanes | Code-owned production composition: `AUTHENTICATION` and `REQUEST_ROUTER` |
| Initial externally observable readiness | Existing complete production startup admission and application publication order |
| Lane-local attempt order | Shared health object under one lock |
| HMAC and append execution | One lane-bound health-observed sink using the existing HMAC factory and `PreTenantAuditClient` |
| Successful delivery observation | Exact validated `StoredAuditAppend` or `OverflowAuditAppend` return |
| Failed delivery observation | Any caught ordinary exception before a valid successful result |
| Current lane result | Greatest completed lane-local attempt number |
| Same-lane recovery | A successful completion whose attempt number is greater than the lane's current completed attempt |
| Overall audit readiness | Logical conjunction of the two fixed lane results |
| Readiness HTTP status and body | Fixed production API adapter in this contract |
| Event identity, persistence, retry, quota, and overflow truth | Existing client and PostgreSQL authorities, unchanged |
| Authorization and denial result | Existing authentication, principal, and tenant-boundary authorities, unchanged |
| Historical gap existence or reconciliation | No authority in this slice |

There is no configurable lane list, failure threshold, recovery threshold,
timer, stale-state timeout, caller reset, administrative reset, public health
mutation, compatibility alias, alternate appender, fallback audit path, or
readiness override.

The health state is not evidence that an audit event occurred. It is not read
by tenant authorization, capability minting, binder execution, tenant storage,
or any database function.

## 6. State machine and ordering

### 6.1 Construction and publication

One `SecurityAuditHealth` object is constructed while the pre-tenant runtime is
composed. It contains exactly two lane records. Each record begins as:

```text
latest_started   = 0
latest_completed = 0
result           = SUCCEEDED
```

This initial value is not externally observable until all existing production
startup gates pass and FastAPI is published. Startup failure still prevents
publication and closes acquired resources. The health object performs no I/O
and does not weaken or replace any startup check.

The runtime creates exactly one health-observed sink for each fixed lane. Each
sink binds:

- one exact lane;
- the shared health object;
- the existing shared correlation-HMAC factory; and
- that lane's existing `PreTenantAuditClient`.

The producer adapters receive only their bound sink. They no longer hold two
separate correlated HMAC/appender fields.

### 6.2 Attempt transition

Immediately before correlation-HMAC creation, a sink starts one attempt under
the health lock:

```text
lane.latest_started += 1
attempt = (lane, lane.latest_started)
```

Starting an attempt does not alter readiness. The sink then performs exactly
the existing operation:

```text
correlation_hmac = hmac_factory.create()
result = audit_appender.append(reason, correlation_hmac)
```

There is no health-owned retry. The existing audit client remains the sole
same-event-ID retry owner.

### 6.3 Completion classification

If the operation returns, the sink accepts success only when the result's exact
type is `StoredAuditAppend` or `OverflowAuditAppend`. It records `SUCCEEDED` for
the attempt and returns the same result. Any other returned type creates one
closed `SecurityAuditUnavailable`, records `FAILED`, and raises that closed
error; it cannot be treated as a successful protocol result.

An `OverflowAuditAppend` is success whether `count_unknown` is true or false.
The database has acknowledged its governed bounded aggregation posture; health
must not reinterpret that result or let hostile volume alone manufacture a
delivery failure.

If HMAC creation, append, or result validation raises an `Exception`, the sink
records `FAILED` for the attempt and re-raises the original exception with its
identity and traceback preserved. It does not catch `BaseException`, translate
the failure, inspect exception text, or expose it through readiness.

### 6.4 Concurrent and stale completions

A completion changes its lane only when:

```text
attempt.number > lane.latest_completed
```

When true, the health object atomically sets `latest_completed` and the new
result. Otherwise the completion is stale and has no health effect.

This produces deterministic start-order semantics:

- attempt 1 fails, then later-started attempt 2 succeeds: the lane is ready;
- attempt 2 succeeds before attempt 1 later fails: attempt 1 is stale and the
  lane remains ready;
- attempt 2 fails before attempt 1 later succeeds: attempt 1 is stale and the
  lane remains not ready;
- a success on the other lane never restores the failed lane; and
- an in-flight attempt does not hide the most recent completed result.

The state is constant-size. It stores only two lane tokens, two counters, and
two closed results. It stores no attempt object after completion and no history.

### 6.5 Readiness threshold and recovery

The reviewed threshold is exactly one most-recently-started completed failure
per lane:

```text
lane_ready = lane.result == SUCCEEDED
overall_ready = authentication_ready and request_router_ready
```

There is no failure quorum, time window, decay, hysteresis, sampling, or manual
override. A lane recovers only through a later-started successful operation on
that same production lane.

Recovery means only that the latest observed operation on that lane completed
the existing governed delivery protocol. It does not assert that an earlier
event exists, that an unavailable interval is counted, or that an `AUDIT_GAP`
was committed.

### 6.6 HTTP protocol

`GET /health` remains unchanged and returns liveness plus immutable runtime
metadata.

`GET /ready` takes one constant-time snapshot of overall readiness and performs
no database, KMS, network, filesystem, audit, tenant, or clock I/O.

Ready response:

```http
HTTP/1.1 200 OK
cache-control: no-store
content-type: application/json

{"schemaVersion":"ofarm.security-audit-readiness.v1","status":"READY"}
```

Not-ready response:

```http
HTTP/1.1 503 Service Unavailable
cache-control: no-store
content-type: application/json

{"schemaVersion":"ofarm.security-audit-readiness.v1","status":"NOT_READY"}
```

Both responses require `Cache-Control: no-store`; an intermediary must not be
invited to reuse an earlier readiness decision. Each response is a point-in-time
observation and makes no continuous-reachability claim.

The body contains no lane, reason, count, time, event identity, bucket,
exception, endpoint, role, key, tenant, principal, credential, request, or
runtime-configuration field. The route captures the runtime privately and does
not trust or publish a mutable health object through `app.state`.

This route reports only the security-audit boundary. HTTP 200 does not assert
that governed product handlers are implemented, that another runtime boundary
is ready, or that OFARM2 is production-ready. Existing governed routes remain
blocked.

### 6.7 Restart and gap boundary

Health state is process-local and is not a durable audit record. Process death
can lose it, exactly as ADR 0001 already acknowledges for a crash before audit
append. A new process does not import, infer, or clear prior health. It becomes
externally ready only after the complete existing startup admission succeeds.

Restarting therefore does not prove that a previous interval was gap-free and
must never be presented as gap reconciliation. Durable unavailable-interval
recording, process-crash `COUNT_UNKNOWN`, and the authority to commit
`AUDIT_GAP` require a separate #192 decision.

## 7. Invariants and acceptance criteria

### `AUDHLTH-001` — exactly two fixed health lanes

Production contains exactly `AUTHENTICATION` and `REQUEST_ROUTER` health lanes.
No environment value, request, plugin, registry, or caller can add, remove,
rename, or select a lane.

### `AUDHLTH-002` — bounded non-sensitive state

Health memory remains constant-size and contains only lane identity,
monotonically ordered attempt counters, and closed success/failure state. It
contains no audit result fields, event data, correlation material, exception,
request, identity, tenant, route, key, endpoint, or timestamp.

### `AUDHLTH-003` — startup authority remains prerequisite

The initial ready state is externally observable only after every existing
structural, route-identity, service-separation, HMAC-lifecycle, KMS, signing,
and tenant-runtime startup gate passes.

### `AUDHLTH-004` — one observation around every governed delivery

Every mapped authentication or pre-binding request-router refusal starts one
health attempt before HMAC creation and completes it exactly once around the
existing HMAC-and-append operation. Successful authentication, successful
TenantBinding, post-binding body/exit failure, and unmapped failure start none.

### `AUDHLTH-005` — exact result classification

Only an exact `StoredAuditAppend` or `OverflowAuditAppend` return is success.
Every caught ordinary HMAC, append, transport, database, KMS, result-shape, or
other operation exception is failure and is re-raised unchanged.

### `AUDHLTH-006` — latest-started completion owns lane state

For concurrent operations, only a completed attempt with a greater lane-local
number than the current completed number may change readiness. A stale
completion cannot overwrite a newer-started completed result.

### `AUDHLTH-007` — recovery is same-lane and later-started

One failure makes its lane not ready. Only a later-started successful result on
that same lane restores it. Activity on the other lane, readiness polling,
time passage, restart terminology, or caller action cannot mutate that lane in
the running process.

### `AUDHLTH-008` — overall threshold is fixed conjunction

Overall audit readiness is `READY` if and only if both fixed lanes are ready.
There is no configurable threshold, quorum, grace period, or override.

### `AUDHLTH-009` — readiness is safe, passive, and bounded

`GET /ready` returns only the fixed version/status body, `Cache-Control:
no-store`, and its matching 200 or 503 status from one in-memory snapshot. It
performs no I/O, mutation, append, probe, retry, sleep, or dependency call and
exposes no internal health state.

### `AUDHLTH-010` — audit failure never authorizes

Health observation never suppresses, replaces with success, retries outside
the client, or converts an authentication, principal, capability, binder,
HMAC, or audit failure into authorization or tenant entry. No fallback lane,
tenant table, ordinary log, or ungoverned store is used.

### `AUDHLTH-011` — governed overflow remains healthy delivery

A validated overflow result, including `count_unknown=true`, is a successful
delivery observation. Hostile event volume cannot directly set health failure
while PostgreSQL continues to acknowledge the governed overflow protocol.

### `AUDHLTH-012` — no gap or completeness claim

Readiness state is never persisted as security evidence and cannot create,
close, count, reconcile, or clear an audit gap. `READY` never means lossless,
exactly-once, historically complete, or gap-free.

### `AUDHLTH-013` — post-binding boundary remains closed

After successful TenantBinding entry, no separate-lane health attempt or append
is started for body or context-exit failures. The existing tenant-batched
boundary remains unchanged.

### `AUDHLTH-014` — authoritative objects remain private

The application publishes no health tracker, sink, appender, HMAC factory,
database client, or reset capability through `app.state`, dependency injection,
module globals, or the readiness response.

## 8. Production-reachable negative cases

| Invariant | Supported entry and counterexample | Required result |
| --- | --- | --- |
| `AUDHLTH-001` | Start production with normal configuration and attempt to supply a lane or threshold through environment/request data. | No such input surface exists; only the two code-owned lanes are composed. |
| `AUDHLTH-002` | Submit a malformed credential whose audit result contains UUIDs, times, and a correlation HMAC. | Health stores none of those values; only the authentication lane's counter/result changes. |
| `AUDHLTH-003` | `create_app()` encounters a structural, role, HMAC, signing, or tenant-pool startup refusal. | FastAPI and `/ready` are never published. |
| `AUDHLTH-004` | `ApplicationRuntime.authenticate()` receives a mapped verification failure and HMAC creation then fails. | One authentication attempt completes failed; no append occurs; the original HMAC exception propagates. |
| `AUDHLTH-005` | A production-bound appender returns an unsupported object or raises `SecurityAuditOutcomeUnknown`. | The lane becomes not ready and the unsupported/unknown failure propagates; it cannot become success. |
| `AUDHLTH-006` | Authentication attempt 2 starts after attempt 1, succeeds first, and attempt 1 fails later. | Attempt 1 is stale and cannot replace attempt 2's ready result. |
| `AUDHLTH-007` | Authentication is not ready, then the request-router lane succeeds. | Overall remains not ready until a later authentication attempt succeeds. |
| `AUDHLTH-008` | One lane is ready and one is not ready when `/ready` is called. | Overall is `NOT_READY`; no majority or grace policy exists. |
| `AUDHLTH-009` | A hostile client polls `/ready` concurrently, tries to cache an earlier response, and mutates `app.state.runtime_metadata`. | Responses remain fixed no-store snapshots; no dependency call occurs and mutable `app.state` does not control readiness. |
| `AUDHLTH-010` | A principal refusal is mapped, but the audit database is unavailable. | Audit failure propagates, authentication does not return a principal, and no tenant operation starts. |
| `AUDHLTH-011` | More than the accepted per-minute threshold of invalid credentials reaches the live audit service and PostgreSQL returns governed overflow results. | Denials remain denials and the lane remains ready while delivery continues to return validated overflow results. |
| `AUDHLTH-012` | A failed attempt is followed by a same-lane success and readiness returns to ready. | No `AUDIT_GAP` is claimed, written, or cleared; the response says only `READY`. |
| `AUDHLTH-013` | TenantBinding succeeds and the governed body or context exit fails. | No isolated audit-health attempt or pre-tenant append occurs after binding. |
| `AUDHLTH-014` | Application-adjacent code enumerates and changes `app.state`. | It finds only immutable runtime metadata; no health authority or reset handle is present. |

Tests may use constructor-level protocol fakes and controlled concurrency to
drive these supported paths. They must not mutate private health fields or
claim that a fake is executed PostgreSQL/KMS evidence.

## 9. Proposed architecture and smallest change

### 9.1 Types and ownership

Add `kernel/security_audit_health.py` with:

- a private fixed lane enum;
- a closed public readiness enum;
- one frozen private attempt token;
- one `SecurityAuditHealth` object owning the lock and two lane records; and
- one `HealthObservedAuditSink` binding a lane, the existing HMAC factory, and
  the existing appender.

The sink exposes one operation:

```python
def append(self, reason: str) -> SecurityAuditAppend: ...
```

It owns the complete health observation around the already governed HMAC and
append calls. The producer adapters keep only outcome-to-reason mapping and
denial ordering. Their duplicated HMAC/appender protocols and `_append`
implementations are deleted and replaced by one narrow sink protocol.

`PreTenantAuditRuntime` owns the shared health object and exposes only a closed
readiness value in addition to its existing `authenticate()` and
`unit_of_work()` methods. `ApplicationRuntime` delegates that closed value.
The API adapter maps it to the fixed `/ready` protocol. The mutable object and
its transition methods remain private.

### 9.2 Data flow

For authentication:

```text
supported authentication failure
  -> closed reason mapping
  -> authentication health-observed sink starts attempt
  -> correlation HMAC
  -> existing authentication PreTenantAuditClient append/retry
  -> success/failure health completion
  -> existing original-denial or audit-failure propagation
```

For the request router:

```text
supported pre-binding TenantBoundaryError
  -> closed reason mapping
  -> request-router health-observed sink starts attempt
  -> correlation HMAC
  -> existing request-router PreTenantAuditClient append/retry
  -> success/failure health completion
  -> existing original-denial or audit-failure propagation
```

For readiness:

```text
GET /ready
  -> ApplicationRuntime closed readiness value
  -> PreTenantAuditRuntime in-memory snapshot
  -> fixed 200/503 response
```

No readiness read enters either producer flow, and no producer result field
enters readiness state.

### 9.3 Why this is the minimum coherent design

Updating health only in `PreTenantAuditClient` would miss correlation-HMAC
failure and would mix shared delivery state into the database transport/retry
authority. Updating it separately in both producer adapters would duplicate
concurrency and classification policy. A generic middleware cannot see exact
HMAC/append outcomes and risks crossing the successful TenantBinding boundary.

One shared state plus two lane-bound sinks places the observation around the
complete operation without changing the client, database, KMS, or tenant
authorities. A separate `/ready` route preserves `/health` liveness semantics
and avoids active dependency work in readiness polling.

An active probe is not smaller or more truthful: there is no accepted synthetic
audit reason, and read-only structural/KMS probes cannot prove the producer
append path. A timer or background worker would add lifecycle, cost, and
deployment authority without solving that mismatch.

## 10. Elegance audit

- **Audit persistence sources of truth:** one existing PostgreSQL/client path;
  unchanged.
- **Health sources of truth:** one shared in-process object.
- **Health transition points:** one sink class used by two fixed instances.
- **Readiness decision points:** one conjunction method and one HTTP adapter.
- **Duplicated correlated fields removed:** the separate HMAC factory and
  appender fields/protocols in both producer adapters.
- **Compatibility surfaces introduced:** none.
- **Configurable policy introduced:** none.
- **General framework introduced:** none.
- **History or event carrier introduced:** none.
- **Deletions:** duplicate producer `_append` methods and their paired
  protocols/fields.
- **Clean rewrite assessment:** a repository-wide rewrite is not justified.
  A local constructor refactor is smaller and makes the bound sink explicit.

The design uses one new abstraction because the same security transition must
be exact for two existing producer lanes. It is not a service bag or optional
capability collection.

## 11. Pull request and approval boundary

### 11.1 Exact technical path allowlist

The final implementation may change only these paths:

1. `docs/rfcs/OFARM_Security_Audit_Dynamic_Health_Readiness_RFC_v0_1.md`
2. `kernel/security_audit_health.py`
3. `kernel/authentication_audit.py`
4. `kernel/request_router_audit.py`
5. `kernel/security_audit_runtime.py`
6. `kernel/application_runtime.py`
7. `kernel/api.py`
8. `kernel/README.md`
9. `kernel/tests/test_security_audit_health.py`
10. `kernel/tests/test_authentication_audit.py`
11. `kernel/tests/test_request_router_audit.py`
12. `kernel/tests/test_security_audit_runtime.py`
13. `kernel/tests/test_application_runtime.py`
14. `conformance/rewrite_architecture_check.py`
15. `conformance/review_baseline_test_inventory.json`

The Phase A review head changes only path 1. Phase B may use a strict subset of
the remaining paths. The inventory is mechanical and must be regenerated from
the exact implementation tree.

### 11.2 Explicitly unchanged paths and authorities

Reviewers must treat every unlisted path as immutable for this decision,
especially:

- `security_audit/migrations/**`;
- `deployment/postgresql/**`;
- `kernel/security_audit.py` and `kernel/security_audit_client.py`;
- `kernel/google_kms_correlation_hmac.py` and
  `kernel/security_audit_hmac_posture.py`;
- `kernel/production_oidc.py`, `kernel/principal_resolver.py`,
  `kernel/tenant_uow.py`, and all signing/key-control modules;
- `docs/adr/**` and `reference/**`;
- deployment, workflow, dependency, provisioning, and issue #176 paths.

No accepted numbered migration may be edited.

### 11.3 Dependencies

- #169, #170, #172, #173, and #174 are closed as completed.
- Merged #223–#236 provide the database, client, HMAC, producer, startup, and
  bounded-I/O prerequisites.
- Merged #311 provides overflow closure but is not changed or invoked here.
- No open pull request is a prerequisite for this Phase A boundary.

### 11.4 Reviewer non-requirements

Reviewers must not require this pull request to:

- persist or reconcile gaps;
- add an active or periodic dependency probe;
- make readiness durable across process death;
- block startup because a previous process may have lost state;
- close overflow buckets or mark counts unknown;
- destroy HMAC keys;
- implement retention, reader/export, break-glass, or store-loss operations;
- add production deployment or a complete #192 hostile matrix; or
- close issue #192.

Those requests change another trust boundary and must become a separate
decision or a demonstrated prerequisite.

### 11.5 Follow-ups

Issue #192 continues to own separately governed work for:

- operational gap recording and crash/unavailable-interval reconciliation;
- destructive HMAC retirement and deadline enforcement;
- dual-approved break-glass export and temporary-login lifecycle;
- empty-recreate/store-loss operation; and
- remaining real-ASGI/PostgreSQL cross-slice hostile closure evidence.

No new issue is required merely to repeat those existing parent blockers.

### 11.6 Stop and reapproval conditions

Stop and require a new decision version before implementation or merge if work
would:

- add or remove a health lane;
- change the one-failure/one-later-success same-lane threshold;
- make readiness active, timed, durable, externally resettable, or
  configurable;
- store or expose more than the closed status;
- reinterpret overflow as failure;
- catch `BaseException` or suppress an audit failure;
- change retry, database, KMS, authorization, tenant, or post-binding
  authority;
- add any path outside the allowlist;
- name a different pull request; or
- authorize deployment, release, production access, or production readiness.

Meaning-preserving wording, test clarity, mechanical inventory regeneration,
and line-budget headroom inside the allowlist do not require a new version.

## 12. Provisional design record

**Not provisional.**

The process-local result is intentionally a current runtime-readiness
observation, not a temporary substitute for durable gap evidence. Later gap
control may observe or wrap the same failure path under its own approved
authority, but it must not silently change this slice's lane identities,
completion ordering, readiness threshold, safe response, or non-authorization
invariants.

The design makes no deployment-readiness claim and therefore does not pretend
to settle orchestration policy, restart policy, or external clock health.

## 13. Traceability and verification

| Invariant | Owning implementation | Negative test/evidence | Smallest verification |
| --- | --- | --- | --- |
| `AUDHLTH-001` | health module and runtime composition | unknown/configured lane unavailable | exact enum/composition test |
| `AUDHLTH-002` | health module | rich result/exception does not enter state or output | state-shape and response test |
| `AUDHLTH-003` | runtime/application builder | every existing startup failure publishes no app | affected startup tests |
| `AUDHLTH-004` | both producer adapters and sinks | HMAC failure, successful path, post-binding path | focused producer tests |
| `AUDHLTH-005` | health-observed sink | stored, overflow, invalid result, unavailable/refused/unknown | sink classification tests |
| `AUDHLTH-006` | health module | controlled out-of-order success/failure completions | deterministic thread/barrier tests |
| `AUDHLTH-007` | health module | cross-lane success and same-lane later success | state-transition tests |
| `AUDHLTH-008` | health module | all four two-lane combinations | table-driven threshold test |
| `AUDHLTH-009` | API adapter | concurrent polling, no-store headers, `app.state` mutation, dependency call sentinels | ASGI route tests |
| `AUDHLTH-010` | producers/runtime | audit failure during credential/principal/binder denial | producer and runtime tests |
| `AUDHLTH-011` | sink and live client integration | quota overflow including `count_unknown` | focused live PostgreSQL test |
| `AUDHLTH-012` | health/API/docs | fail then recover without maintenance call | no-control-call assertion and response test |
| `AUDHLTH-013` | request-router adapter | successful entry then body/exit failure | existing and updated router tests |
| `AUDHLTH-014` | application/API composition | enumerate/tamper `app.state` | application-runtime ASGI test |

### 13.1 Phase A verification gates

- The draft diff contains only this RFC.
- The RFC names the exact reviewed base, one primary boundary, all authorities,
  the state machine, stable invariants, production-reachable negatives, path
  allowlist, reapproval triggers, and claim limits.
- `python3 conformance/ofarm_pkg_contract_check.py` passes.
- `git diff --check` passes.
- Independent review reports no demonstrated Phase A Blocker before a live
  decision card is shown.

### 13.2 Prospective Phase B verification gates

After exact approval, the implementation must pass:

- focused health-state, sink, producer, runtime, and application/ASGI tests;
- deterministic concurrent/out-of-order completion tests without private-field
  mutation;
- a focused live PostgreSQL result path proving stored and overflow success plus
  bounded failure-to-readiness behavior;
- existing authentication, request-router, audit-client, HMAC, startup,
  application-runtime, and tenant UnitOfWork tests;
- Ruff for every changed Python path;
- `python3 conformance/rewrite_architecture_check.py`;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- exact review-baseline inventory regeneration and validation;
- `git diff --check`;
- exact path-envelope rejection for every unlisted path; and
- the complete exact-head hosted conformance and native-verifier gates.

No skipped environment-backed test is affirmative evidence. The pinned hosted
PostgreSQL/Python environment remains authoritative for the full baseline.

Before merge, the PR must receive an exact-head review against the approved
contract. A Blocker must name the violated invariant, supported production
entry, in-scope actor, exact transition, preconditions, consequence, and a
minimal reproduction or counterexample.

## 14. Open decisions and review disposition

### 14.1 Open material decisions

None. Version 1 fixes:

- two lanes;
- process-local state;
- start-order completion semantics;
- one-failure/one-later-same-lane-success recovery;
- stored and overflow results as success;
- passive fixed `/ready` output; and
- no gap/completeness claim.

Changing any of these requires version 2.

### 14.2 Review disposition

- **Blockers:** none known in this draft; independent Phase A review is pending.
- **Follow-ups:** the separately governed remaining #192 boundaries in section
  11.5.
- **Preferences:** none recorded.

Once Phase B acceptance criteria pass and no demonstrated Blocker remains,
merge the approved pull request. New ideas, Preferences, and non-blocking
hardening become Follow-ups and do not reopen review.

## 15. Phase A approval boundary

This RFC is not approval and does not authorize Phase B.

After the complete RFC is published in its named draft pull request and
independent Phase A review reports no demonstrated Blocker, the assistant may
show one live decision card for:

`ISSUE192-SECURITY-AUDIT-DYNAMIC-HEALTH-READINESS-001`, version `1`.

The only valid approval form will be the entire visible text of a later task
user message in the same Codex task:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-DYNAMIC-HEALTH-READINESS-001 version 1.
```

Generic approval, GitHub activity, credentials, review comments, another task,
or a summary is not approval. A later stop-like user message pauses work. Any
semantic card or contract change, path-envelope change, authority change, or
named-pull-request change requires a new decision version.

Approval would authorize repository implementation only within the named draft
pull request and the exact path envelope. It would not authorize deployment,
release, production access, production operation, current/default promotion,
issue #192 closure, or a security waiver.
