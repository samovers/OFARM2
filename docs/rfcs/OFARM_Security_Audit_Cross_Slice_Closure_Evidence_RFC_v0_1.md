# OFARM Security Audit Cross-Slice Closure Evidence RFC v0.1

**Status:** version 1 merged through PR #344; version 2 closure-correction
Phase A is complete in draft PR #345, awaits exact-head review and task-user
approval, and is not approved for implementation

**Decision:** `ISSUE192-SECURITY-AUDIT-CROSS-SLICE-CLOSURE-EVIDENCE-001`

**Decision version:** proposed version 2; version 1 remains the historical
authority for merged PR #344

**Issue:** [#192](https://github.com/samovers/OFARM2/issues/192)

**Reviewed base for version 2:**
`bbf8f0fb9235ffca4f891d789f25e6f1aed7fab8`

**Version 2 draft implementation PR:**
<https://github.com/samovers/OFARM2/pull/345>

**Version 2 primary trust boundary:** executed evidence that exact typed
correlation-HMAC unavailability remains fail-closed across one real ASGI
request path, one independently provisioned tenant PostgreSQL service, one
independently provisioned security-audit PostgreSQL service, audit health, and
durable live-gap reconciliation.

This RFC creates no OFARM authority. It does not authorize deployment,
production access, production composition, release, certification, current
compliance, or issue closure.

## 1. Problem and goal

Issue #192 requires real-ASGI/PostgreSQL hostile evidence for the complete
pre-binding security-audit path and the switch to tenant-bound behavior after a
verified `TenantBinding` exists. The repository currently has strong focused
evidence for each participating slice:

- authentication and principal-resolution outcome mapping;
- request-router and tenant-boundary outcome mapping;
- the isolated audit client, database roles, quota, overflow, health, and live
  gap controller;
- tenant principal resolution, capability minting, challenge consumption,
  `TenantBinding`, transaction-bound UnitOfWork, rollback, and commit;
- live PostgreSQL producer tests for both audit lanes;
- real PostgreSQL tenant UnitOfWork and ASGI concurrency tests; and
- process-crash reconciliation, store-loss recovery, retention, reader, and
  temporary export lifecycle operations.

The focused tests do not execute one request through the joined boundary. The
existing ASGI concurrency test substitutes a fake security-audit graph. The
producer tests use the live audit PostgreSQL service but do not cross a real
tenant UnitOfWork. The production FastAPI application intentionally keeps all
governed semantic routes blocked, so adding an endpoint merely to obtain test
evidence would change runtime authority and contradict the current production
boundary.

The goal is therefore to add bounded, executed, test-only evidence in which a
real FastAPI request handler calls the unchanged public `ApplicationRuntime`
operations, while the runtime graph uses the actual accepted authentication
and request-router producers, tenant principal resolver and UnitOfWork, audit
client, health state, live-gap controller, bounded reader, and two distinct
PostgreSQL services.

This establishes only the composition claim that the already-accepted pieces
preserve their boundaries when joined. It does not establish that a governed
production HTTP endpoint exists.

## 2. Learning value

The slice delivers the last parent-level integration evidence that cannot be
obtained from isolated unit or single-service tests:

1. a pre-binding denial can commit only safe evidence to the audit service and
   cannot begin or partially commit a tenant transaction;
2. a successful `TenantBinding` moves the request to the tenant transaction and
   closes the isolated audit lane for all later body and finalization behavior;
3. audit failure preserves denial, changes only the bounded audit health/gap
   posture, and never authorizes tenant work;
4. concurrent denied and successful requests cannot exchange audit or tenant
   effects; and
5. the evidence is executed through real ASGI scheduling and two independently
   identified PostgreSQL systems rather than inferred from separately passing
   fixtures.

The demonstrated risk reduced is false confidence from tests that validate
each slice but never exercise their ordering together.

## 3. Non-goals

This decision does not:

- add, enable, or change a production HTTP route;
- change `kernel.api`, `ApplicationRuntime`, authentication, principal
  resolution, request-router, tenant UnitOfWork, audit client, health, gap,
  readiness, retry, overflow, or database behavior;
- change a migration, database function, role, grant, credential, session
  identity, provisioning manifest, or PostgreSQL route;
- call live OIDC/JWKS, Google Cloud KMS, a production signer, or a production
  correlation-HMAC key;
- claim provider, IAM, clock, timer, route-custody, secret-distribution, or
  deployment evidence;
- add a scheduler, worker, timer, queue, spool, crash detector, lease,
  heartbeat, or automatic retry;
- retest every internal negative case already owned by focused slice tests;
- change retention, destructive HMAC retirement, store-loss, process-crash,
  reader, approval, temporary export, or output-delivery behavior;
- add protected output custody or delivery;
- repair issue #334 package-initializer reachability or define complete
  execution-root/source-capability governance;
- change issue #176, any temporal behavior, OFARM law, a candidate contract,
  profile activation, or currentness; or
- close issue #192 automatically when this pull request merges.

The final issue-closure audit remains a separate read-only action after this
evidence is merged.

## 4. Trust model

### 4.1 Protected assets

The protected assets are:

- denial preservation before trusted tenant binding;
- the separation of tenant truth/knowledge order from operational security
  evidence;
- the tenant PostgreSQL system identity, database, roles, transaction,
  `TenantBinding`, governed batch, and rollback/commit outcome;
- the security-audit PostgreSQL system identity, database, two producer roles,
  control role, reader/access-intent protocol, append rows, overflow/gap rows,
  and health state;
- the rule that audit evidence carries no tenant, Party, actor, raw credential,
  token, route, free text, request body, exception detail, or attacker-chosen
  identity;
- the post-binding switch that forbids isolated-lane appends after the tenant
  UnitOfWork yields; and
- the honesty of the resulting executed test evidence.

### 4.2 Trusted components and inputs

The evidence trusts only:

- the exact repository source at the reviewed pull-request head;
- the accepted tenant and security-audit migration sets and provisioning
  specifications;
- PostgreSQL authentication, `session_user`, transaction semantics,
  `pg_control_system()` system identity, and the database clocks used by the
  accepted functions;
- the existing `PrincipalBindingResolver`, `TenantUnitOfWorkManager`,
  `AuthenticationAuditProducer`, `RequestRouterAuditProducer`,
  `PreTenantAuditClient`, `SecurityAuditHealth`, `SecurityAuditGapController`,
  `SecurityAuditGapClient`, and bounded query runner;
- one test-owned FastAPI handler that does nothing except call the unchanged
  public runtime operations in production order and return a fixed result after
  a successful tenant transaction;
- existing repository test authorities for a fictional tenant, Party,
  principal, capability key, and signed capability;
- a deterministic verifier seam that returns only accepted typed verification
  outcomes or one exact fictional identity; and
- a deterministic correlation-HMAC factory that supplies one exact accepted
  `CorrelationHmac` value solely to exercise the database carrier contract.

The verifier seam is not an identity authority beyond the test. The tenant
database remains authoritative for principal binding and `TenantBinding`. The
deterministic HMAC is not evidence of KMS custody, key readiness, production key
material, or provider availability.

### 4.3 Untrusted actors and inputs

The evidence treats as untrusted:

- Authorization header bytes, missing credentials, malformed tokens, unknown
  paths, request bodies, query strings, and all other ASGI request input;
- any fictional token, subject, tenant, Party, actor, request, batch, route,
  password, DSN, and exception canary used by the tests;
- ordering and concurrency between ASGI worker threads;
- database connection loss or refusal at the audit producer route;
- database errors and all exception text;
- an invalid or unavailable tenant capability minting result;
- stale, malformed, mismatched, or unavailable tenant binding inputs; and
- test failures, skipped tests, captured output, and generated baseline data
  until the trusted conformance pipeline validates them.

### 4.4 Explicitly excluded attacker capabilities

The following remain out of scope:

- arbitrary in-process mutation or reflective replacement of runtime objects;
- local source substitution after the reviewed commit is selected;
- compromised Python, FastAPI, Psycopg, PostgreSQL, cryptography, or test
  dependencies;
- host, kernel, hypervisor, container-runtime, or PostgreSQL-server compromise;
- arbitrary filesystem mutation during the test;
- database owner, migrator, superuser, KMS administrator, trusted operator, or
  repository-owner compromise;
- deliberate mutation of private object state; and
- a malicious test runner that fabricates results rather than executing the
  checked-in tests.

These exclusions match the accepted component contracts. The evidence does
not claim to turn a Python test into a boundary against its own operator.

## 5. Authority map

| Decision | Sole authority | Explicit non-authorities |
| --- | --- | --- |
| Tenant and audit service identity | Exact `pg_control_system()` system identifiers observed through the two configured admin routes | Port number, hostname, database name, fixture label |
| Service schema and role posture | Accepted provisioning specifications, migration ledgers, structural verifiers, and PostgreSQL catalogs | Test assumptions, class names, successful connection alone |
| Credential verification outcome | Deterministic test verifier implementing the production `CredentialVerifier` protocol | Header text, ASGI handler, audit database |
| Principal identity and tenant/Party binding | Tenant PostgreSQL `resolve_principal_binding_authority` result through `PrincipalBindingResolver` | Test route, audit row, caller-selected tenant or Party |
| Capability and `TenantBinding` | Existing tenant capability fixture plus tenant PostgreSQL challenge/binder functions through `TenantUnitOfWorkManager` | Test handler, audit controller, response body |
| Pre-binding reason mapping | Existing producer adapters' closed typed-outcome maps | Test-selected reason text, exception message, caller field |
| Audit producer/component | Exact audit PostgreSQL `session_user` and immutable reason allowlist | DSN username string alone, test recorder |
| Audit event identity and observation time | Audit PostgreSQL append functions | ASGI request, tenant database, Python wall clock |
| Audit HMAC carrier shape | Existing `CorrelationHmac` type and audit database contract | Production KMS custody or key readiness claim |
| Audit health state | Existing `SecurityAuditHealth` ordering | HTTP response, log line, test assertion order |
| Gap interval and count posture | Existing live-gap controller plus audit PostgreSQL clocks/functions | Test clock, request duration, caller count |
| Audit read visibility | Accepted committed access-intent and bounded-reader protocol | Direct table scan as acceptance proof |
| Tenant effects | Verified `TenantBinding` plus tenant PostgreSQL transaction and governed-batch relation | Audit row, header, ASGI route closure |
| ASGI request ordering | Starlette/FastAPI execution of the test-owned handler calling public runtime methods | A claim that `kernel.api` publishes a governed route |
| Test pass/fail | Pytest execution in the exact-tree conformance baseline | RFC text, skipped local fixture, design assertion |

There is no legacy fallback, alias, alternate write path, generic audit logger,
tenant-table audit fallback, or duplicate state introduced by this decision.

## 6. State machine and ordering

### 6.1 Harness admission

Before serving a test request, the fixture must:

1. require both existing hosted admin-route environment variables;
2. provision and migrate the tenant and audit services through their accepted
   fixtures;
3. prove that their PostgreSQL system identifiers are nonempty and distinct;
4. construct the real tenant principal resolver and initialize it;
5. construct and initialize a real tenant UnitOfWork manager with the accepted
   test capability authority;
6. construct producer clients under the exact two audit producer LOGINs;
7. construct one real audit-control gap client/controller;
8. wrap both producer clients first with the existing health observers and
   then with the controller's fixed authentication/request-router lanes;
9. construct the two accepted producer adapters and one `ApplicationRuntime`;
10. construct a test-owned FastAPI handler that calls only
    `runtime.authenticate(token)` followed by
    `runtime.tenant_unit_of_work(principal)`; and
11. record a bounded before-snapshot through the accepted tenant and audit
    observation protocols.

Any failure before step 10 skips locally only when a required hosted database
route is absent. When routes exist, every failure fails the test; it may not be
converted to a skip.

### 6.2 Per-request states

Each request begins in `REQUEST_RECEIVED` and follows exactly one path:

```text
REQUEST_RECEIVED
  -> AUTHENTICATION_IN_FLIGHT
      -> AUTHENTICATION_AUDIT_IN_FLIGHT
          -> AUTHENTICATION_REFUSED
      -> PRINCIPAL_RESOLVED
          -> TENANT_BINDING_IN_FLIGHT
              -> ROUTER_AUDIT_IN_FLIGHT
                  -> TENANT_ENTRY_REFUSED
              -> TENANT_BOUND
                  -> BODY_IN_FLIGHT
                      -> TENANT_ROLLED_BACK
                      -> TENANT_COMMIT_IN_FLIGHT
                          -> TENANT_COMMITTED
                          -> TENANT_FINALIZATION_UNKNOWN
```

The isolated audit lane is eligible only before `TENANT_BOUND`.

### 6.3 Required ordering

- A mapped authentication or principal failure must complete its audit append
  or surface an audit/gap failure before the original denial leaves the runtime.
- A mapped tenant-entry failure must complete its request-router audit append
  or surface an audit/gap failure before tenant entry is reported refused.
- Audit failure cannot be caught and replaced with principal resolution,
  capability minting, tenant binding, tenant SQL, or an HTTP success.
- Successful tenant binding yields the UnitOfWork once and irrevocably closes
  the isolated lane for that request.
- A body exception rolls back tenant effects and propagates without an audit
  append.
- A finalization-unknown outcome propagates without an audit append or retry.
- Only a successfully returned UnitOfWork body may commit its governed batch.
- The accepted reader runs only after the request is terminal; its own durable
  `AUDIT_ACCESS` event is excluded from comparisons by event kind, not hidden
  by an unbounded or privileged query.

There is no cross-database transaction and no claim of atomic commit between
the services. The invariant is one-way exclusion: before binding, no tenant
effect; after binding, no isolated audit effect.

## 7. Invariants and acceptance criteria

### `XSLICE-001` — exact two-service evidence

Every executed cross-slice test uses the accepted tenant and audit fixtures,
and proves their PostgreSQL system identifiers are distinct before requests.
No single PostgreSQL service, schema split, mock database, SQLite database, or
in-memory store satisfies the evidence.

### `XSLICE-002` — authentication denial is audit-only

A real ASGI request whose deterministic verifier produces any selected mapped
authentication failure completes exactly one corresponding authentication
producer result before denial. Tenant principal resolution and tenant
UnitOfWork entry do not begin, and the tenant knowledge head is unchanged.

### `XSLICE-003` — principal denial is audit-only

A real ASGI request with a verified fictional identity that the real tenant
resolver refuses completes exactly one corresponding authentication-lane
principal reason before denial. No tenant UnitOfWork begins and no tenant row
is committed.

### `XSLICE-004` — tenant-entry denial uses only the router lane

After real principal resolution succeeds, a production-reachable capability
or binder refusal before UnitOfWork yield completes exactly one corresponding
request-router producer result. It creates no authentication-lane event and
commits no tenant governed batch.

### `XSLICE-005` — successful binding switches lanes

A real principal resolution and `TenantBinding` followed by one governed batch
commit creates exactly the expected tenant batch and no isolated audit event.
The tenant, Party, and runtime-bundle values come only from the verified
binding and accepted request object.

### `XSLICE-006` — post-binding failure never returns to isolated audit

After the UnitOfWork yields, a body failure rolls back any staged tenant batch
and creates no isolated audit event. A focused existing finalization-unknown
case remains required in the verification set and likewise creates no audit
event. Neither case is reclassified as a pre-binding router reason.

### `XSLICE-007` — audit failure never authorizes

When an exact producer connection route is unavailable, the mapped denial is
not replaced by success, principal authority, tenant binding, or tenant SQL.
The affected health lane becomes `NOT_READY`; the live-gap controller records
the failed attempt's bounded posture. A later-started successful request on the
same lane may restore health and close the gap through existing rules, but it
may not retry the failed request.

### `XSLICE-008` — unmatched ASGI routes are not security events

An ordinary request to an unregistered path returns the ASGI framework's fixed
not-found result and creates no authentication or request-router event, health
attempt, gap transition, or tenant effect.

### `XSLICE-009` — concurrent requests remain isolated

One mapped denied request and one successful tenant-bound request executed
concurrently produce exactly one audit-side denial result and exactly one
tenant-side committed batch. Neither request's token, identity, tenant, Party,
batch, response, or exception can appear in the other request's authority or
effect.

### `XSLICE-010` — no protected value crosses an observability sink

The exact audit rows visible through the bounded reader contain only the
accepted fixed event shape. Fictional raw token, issuer, subject, tenant UUID,
Party reference, batch/request identifiers, route, body, DSN, password, and
exception canaries do not occur in audit row values, ASGI responses, captured
stdout/stderr, or formatted exceptions used as acceptance evidence.

### `XSLICE-011` — observation is bounded and authorized

Audit acceptance evidence uses the existing committed access-intent and
bounded-reader protocol with its fixed row and byte bounds. Tenant acceptance
evidence uses exact keyed queries against the fixture's admin observation
route. No unbounded audit scan, COPY, export role, break-glass role, or private
runtime state is used.

### `XSLICE-012` — the evidence is honest and bounded

The test module contains a fixed finite scenario set, fixed thread count, fixed
timeouts, and no background worker, scheduler, retry loop, unbounded polling,
or wall-clock success inference. It remains at or below the existing 800-line
test-module budget. Local absence of either required database route is reported
as an intentional skip; hosted baseline acceptance requires execution and pass
of every node.

### `XSLICE-013` — production authority remains unchanged

The pull request changes no production Python, SQL, migration, provisioning,
role, workflow, endpoint, configuration, or deployment file. Passing evidence
does not claim that governed routes in `kernel.api` are open, that external
OIDC/KMS providers were exercised, or that production composition is ready.

## 8. Production-reachable negative cases

| Invariant | Counterexample from the supported runtime boundary | Required result |
| --- | --- | --- |
| `XSLICE-001` | Point both fixture admin routes at one PostgreSQL system or omit one route in hosted execution. | Same-system execution fails before ASGI construction; absent hosted route fails rather than becoming evidence. |
| `XSLICE-002` | Send a request whose verifier returns `NO_CREDENTIAL`, `CREDENTIAL_MALFORMED`, `VERIFIER_UNAVAILABLE`, or `VERIFICATION_REFUSED`. | Exact authentication reason is durable before denial; resolver and tenant pool are unused. |
| `XSLICE-003` | Send a syntactically verified fictional identity absent from the tenant principal authority. | `PRINCIPAL_BINDING_REFUSED` is durable through the authentication producer; tenant entry never begins. |
| `XSLICE-004` | Resolve a real principal, then make the accepted capability minting seam return `CapabilityMintError` before binder execution. | `CAPABILITY_REFUSED` is durable through the router producer; no batch commits. |
| `XSLICE-005` | Send a valid identity through resolver, capability, binder, and one governed batch request. | One exact tenant batch commits and the audit event set is unchanged apart from reader access evidence. |
| `XSLICE-006` | Raise a body exception after allocating a governed batch inside the yielded UnitOfWork. | Tenant batch rolls back, no isolated audit event appears, and the body exception is not recast as pre-binding denial. |
| `XSLICE-007` | Use the exact producer client with a refused connection route for a mapped denial, then restore that route for a later independent request. | First request cannot bind or write tenant state and marks health not ready; later request is a new attempt, may restore health, and closes any eligible gap without retrying the first request. |
| `XSLICE-008` | Request a random unregistered path with hostile Authorization, query, and body canaries. | Fixed 404, no producer call, no health/gap transition, no tenant effect. |
| `XSLICE-009` | Release one denied and one valid request concurrently from a barrier. | One exact audit event and one exact tenant batch; no swapped subject, tenant, Party, or event. |
| `XSLICE-010` | Place unique canaries in token, issuer, subject, tenant, Party, batch, route, body, DSN label, and exception detail. | None appears in accepted audit rows, response, output, or formatted exception evidence. |
| `XSLICE-011` | Attempt to use direct unbounded audit SQL, COPY, export, break-glass, or a test-created privileged reader as acceptance evidence. | Test design fails review; only accepted bounded reader output may prove visible audit events. |
| `XSLICE-012` | Remove either hosted database environment variable, add an unbounded wait/retry, or let a node skip in the admitted hosted baseline. | Hosted evidence fails; no design fixture or local skip is reported as executed proof. |
| `XSLICE-013` | Add a production endpoint, provider call, migration, role, workflow, or deployment configuration to make a test pass. | Stop for a new decision version or separate prerequisite; this pull request cannot absorb it. |

The test may use deterministic protocol seams only where the external provider
is not the authority being tested. It may not mutate private production fields
or monkeypatch a supposedly executed PostgreSQL result.

## 9. Proposed architecture and smallest change

### 9.1 One test-owned composition

One new module,
`kernel/tests/test_security_audit_runtime_cross_slice.py`, owns all new Phase B
code. It reuses existing module-scoped tenant and audit fixtures and defines:

- a deterministic credential verifier with a closed token-to-outcome map;
- a deterministic correlation-HMAC factory using the accepted contract shape;
- a recording wrapper around the real audit appender that records only returned
  event identities/results, never protected request values;
- a switchable connection factory whose only state is whether the next producer
  connection uses the valid fixture DSN or a refused route;
- one fixture that builds the real resolver, tenant manager, audit clients,
  health object, gap controller, producer adapters, and `ApplicationRuntime`;
- one small test-owned FastAPI handler that calls public runtime methods in
  their production order;
- fixed helpers for exact tenant batch counts and accepted bounded audit reads;
  and
- a finite test matrix covering the invariants above.

The test-owned handler is not imported by production, not exposed by
`kernel.api`, not a dependency-injection constructor, and not presented as a
candidate endpoint. It exists solely to let Starlette/FastAPI schedule the
unchanged runtime boundary under real ASGI request semantics.

### 9.2 Data flow

```text
fictional ASGI request
  -> test-owned fixed handler
  -> ApplicationRuntime.authenticate
  -> AuthenticationAuditProducer
       verifier protocol seam
       -> real PrincipalBindingResolver -> tenant PostgreSQL
       failure -> real health/gap/audit client -> audit PostgreSQL
  -> ApplicationRuntime.tenant_unit_of_work
  -> RequestRouterAuditProducer
       -> real TenantUnitOfWorkManager -> tenant PostgreSQL
       pre-yield failure -> real health/gap/audit client -> audit PostgreSQL
       yield -> tenant-only body/commit-or-rollback
  -> fixed ASGI terminal result
  -> accepted bounded audit reader + exact tenant observation
```

### 9.3 Why this is the minimum coherent change

Adding only another unit test would not cross ASGI scheduling or both stores.
Using a fake tenant or audit graph would repeat the existing evidence gap.
Adding a production endpoint would create new runtime authority merely for a
test. Calling live OIDC or KMS would add provider credentials, IAM, network,
clock, and custody boundaries unrelated to the missing database composition
evidence.

One test module can join the already-accepted seams without modifying them.
The only other Phase B change is the mechanically required canonical baseline
inventory update. The RFC remains the durable contract and status record.

## 10. Elegance audit

- **Sources of truth:** one tenant PostgreSQL authority, one audit PostgreSQL
  authority, one typed verifier outcome seam, one deterministic HMAC carrier
  seam, and one test pass/fail result.
- **Authoritative transition points:** audit append commit, tenant UnitOfWork
  yield, tenant transaction commit/rollback, health completion ordering, and
  gap append commit.
- **Duplicated fields:** none added to production. Test canaries are generated
  once per scenario and compared only as forbidden values.
- **Compatibility surfaces:** none. No alias, shim, generic test app, fallback,
  optional capability bag, mutable global registry, or production injection
  constructor is introduced.
- **New abstractions:** only narrow test fixtures/wrappers needed to observe
  returned event IDs and switch a connection route. They remain in one test
  module.
- **Deletion:** no accepted production path can be deleted. Any duplicated
  test helper that proves unnecessary during implementation should be removed
  rather than generalized.
- **Rewrite assessment:** no production rewrite is justified. A new focused
  test module is cleaner than expanding the already budgeted focused slice
  tests or changing production composition.

## 11. Pull request boundary

### 11.1 Maximum path envelope

Phase A changes exactly one path:

1. `docs/rfcs/OFARM_Security_Audit_Cross_Slice_Closure_Evidence_RFC_v0_1.md`

If Phase B is later approved, the complete maximum envelope is exactly three
paths:

1. `docs/rfcs/OFARM_Security_Audit_Cross_Slice_Closure_Evidence_RFC_v0_1.md`
2. `kernel/tests/test_security_audit_runtime_cross_slice.py`
3. `conformance/review_baseline_test_inventory.json`

The test filename is deliberately covered by the existing
`*security_audit_runtime*.py` architecture glob and the global 800-line test
budget. No architecture-checker edit is required. Adding a fourth path,
renaming the test outside that existing rule, or raising a line budget requires
a new decision version.

### 11.2 Dependencies

The decision depends on current `main` at the reviewed base, including merged:

- tenant provisioning, principal resolution, capability binding, and
  UnitOfWork evidence;
- security-audit database, client, producer, health, live-gap, bounded-reader,
  retention, HMAC-retirement, store-loss, export, and temporary-login slices;
- process-crash PR #338 and its admitted published evidence; and
- default-branch review admission and evidence-publication policy through PRs
  #340–#343.

No open pull request or issue #176 implementation is a dependency.

### 11.3 Reviewer non-requirements

Reviewers must not require this pull request to:

- open a governed production endpoint or change `kernel.api`;
- use live external OIDC, JWKS, KMS, IAM, provider, or production secrets;
- change database SQL, roles, migrations, grants, quotas, readers, or routes;
- add deployment manifests, containers, services, timers, workers, schedulers,
  retries, or production health aggregation;
- combine every operational command into one ASGI request;
- implement output custody or production evidence;
- repair issue #334 or complete source-capability governance;
- change issue #176 or temporal behavior;
- claim production readiness, certification, current compliance, or legal
  completeness; or
- close issue #192 in the implementation pull request.

These are separate trust boundaries, external prerequisites, or later audit
actions, not review fixes.

### 11.4 Follow-ups

The following remain traceably outside this boundary:

- protected export-output custody and delivery;
- production clock, timer, route, provider, and secret-custody evidence;
- issue #334 package-initializer reachability;
- complete production/operator execution-root classification and closed
  source-capability governance; and
- issue #192's final read-only closure audit.

No new issue is required merely to duplicate those existing records.

### 11.5 Stop and reapproval conditions

Stop and require a new decision version if implementation or review requires:

- any production-code, SQL, migration, provisioning, workflow, deployment, or
  configuration change;
- another database, service identity, role, credential, route, event kind,
  reason, HMAC shape, health lane, gap state, or retry path;
- an actual production HTTP route or external provider call;
- a test-owned authority replacing tenant PostgreSQL principal/binding
  authority or audit PostgreSQL event authority;
- an unbounded reader, direct export, break-glass role, COPY, or private-state
  observation as acceptance evidence;
- a path outside section 11.1, more than 800 lines in the new test module, or an
  architecture budget/rule change;
- a claim that passing the test authorizes deployment or proves live external
  provider behavior; or
- a material change to an invariant, non-goal, authority, or attacker model.

## 12. Provisional design record

Not provisional for the evidence scope stated here. The design intentionally
proves repository composition through accepted public runtime seams and two
real PostgreSQL systems. It does not temporarily stand in for a production
route, external provider test, or deployment authorization.

The AI-assisted approval governing any later implementation remains
provisional repository-development authority under `AGENTS.md` and has no
production effect.

Evidence that would require redesign rather than an in-place fix includes:

- the public runtime operations cannot be composed without a production
  authority change;
- the accepted tenant and audit fixtures cannot coexist on distinct systems;
- a valid negative case requires private-state mutation or privileged audit
  observation;
- the ASGI harness masks an ordering or exception property it claims to prove;
  or
- the required evidence cannot fit within the three-path envelope and existing
  test budget.

## 13. Traceability and verification

| Invariant | Owning code exercised | Negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `XSLICE-001` | existing provisioning fixtures and PostgreSQL identity checks | same or absent service route | two distinct system IDs and accepted schemas | focused hosted module plus both migration preflights |
| `XSLICE-002` | `AuthenticationAuditProducer`, health/gap sink, real authentication producer client | mapped verifier denial | exact bounded-reader event; unchanged tenant head | focused module and authentication producer suite |
| `XSLICE-003` | real `PrincipalBindingResolver` plus authentication producer | unknown fictional identity | exact principal-refusal event; no tenant entry | focused module and principal resolver tests |
| `XSLICE-004` | `RequestRouterAuditProducer`, real tenant manager and router client | capability mint refusal | exact router event; no tenant batch | focused module and router/tenant UOW suites |
| `XSLICE-005` | resolver, tenant manager, `ApplicationRuntime` public surface | valid bound request | exact committed batch; unchanged audit events | focused module and tenant UOW tests |
| `XSLICE-006` | yielded UnitOfWork and router adapter | body failure after batch allocation | rollback; no isolated event | focused module plus existing body/finalization tests |
| `XSLICE-007` | real client, health, gap controller | refused producer route then later restoration | denial; not-ready; later recovery and exact gap posture | focused module plus health/gap suites |
| `XSLICE-008` | FastAPI router and unopened runtime path | hostile unknown route | fixed 404; no state change | focused module |
| `XSLICE-009` | TestClient/ASGI threads plus both runtime lanes/stores | concurrent denied and valid requests | one event and one batch with exact ownership | focused module with fixed barriers/timeouts |
| `XSLICE-010` | closed event carriers and fixed ASGI terminal surface | unique canaries at every input seam | forbidden-value absence across accepted evidence | focused module plus existing leakage suites |
| `XSLICE-011` | `SecurityAuditQueryRunner` and exact tenant keyed observation | attempt privileged/unbounded observation | fixed bounded page and exact keyed tenant rows | bounded-query suite and focused module |
| `XSLICE-012` | pytest inventory/conformance pipeline | missing route, skip, unbounded wait, inventory drift | every hosted node executed and canonical inventory | collection, inventory, admitted hosted conformance |
| `XSLICE-013` | exact Git diff and architecture check | any production or fourth-path change | one RFC, one test, one inventory path only | path equality, package contract, architecture, diff check |

Required Phase A checks:

- exact one-path Phase A diff;
- CPython 3.12 package contract;
- workflow-free local RFC/diff checks; and
- exact-head content review with zero demonstrated Blockers before any hosted
  baseline admission.

Required Phase B local checks after approval:

- both migration preflights;
- focused cross-slice collection and test execution, with honest local skips
  when the two hosted database routes are absent;
- authentication, principal, request-router, audit-client, health, gap,
  bounded-query, application-runtime, tenant UnitOfWork, and tenant concurrency
  focused suites;
- canonical test-inventory regeneration and byte/digest verification;
- CPython 3.12 package contract and architecture constraints;
- Ruff and `git diff --check`; and
- exact three-path equality.

Required exact-head hosted gates after zero-Blocker review:

- one admitted conformance source run with both baseline runs, exact inventory,
  equivalence, and every cross-slice node executed rather than skipped;
- both native verifier lanes required by repository policy;
- the trusted provisional handoff seal; and
- the separate trusted evidence-publication run and final receipt.

No earlier-head result carries forward after a commit.

## 14. Open decisions and review disposition

### 14.1 Resolved design choices

The test-owned ASGI handler is accepted for this decision because the claim is
ASGI scheduling of the existing public runtime boundary, not availability of a
production governed HTTP route. Opening such a route would be a different
runtime authority and is explicitly forbidden.

Live OIDC/JWKS and KMS are not required because their network, IAM, custody,
clock, and provider behavior are separately tested or tracked. This decision
uses their typed production seams only and makes no external-provider claim.

The test may reuse existing fixture authorities from other test modules. It
must not move them into production or create a generic shared test framework
unless duplication proves that a small test-only helper is necessary within
the same path; a fourth path requires reapproval.

### 14.2 Current review disposition

- Phase A exact-head review `5042579603` supersedes and withdraws erroneous
  review `5041228763`; its disposition is zero Blockers, no new Follow-ups,
  and zero Preferences at head
  `acfb97bf025f7a06dbc9039c0d0fa0d5023db22a`.
- Phase B exact-head dispositions are recorded on PR #344. Only the most
  recent unsuperseded review of the live head controls the merge stop rule.
- Follow-ups: protected output custody; production prerequisite evidence;
  issue #334; complete execution-root/source-capability governance; and final
  issue #192 closure audit.
- Preferences: none.
- Phase B: authorized and implemented only for this decision and draft PR
  #344; section 14.5 controls exact-head review, gates, and merge.
- Production composition: unauthorized and non-deployable.

### 14.3 Approval record

The complete version-1 decision card was displayed in the governing Codex task
after the exact Phase A contract, zero-Blocker review, admitted hosted source
run `33066325206`, and trusted publication run `33067812712` were directly
retrievable. After reading the complete review chain, the task user supplied
this exact sentence as the entire later message:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-CROSS-SLICE-CLOSURE-EVIDENCE-001 version 1.
```

That approval authorizes repository implementation only in draft PR #344 and
only inside section 11.1's three-path envelope. It does not authorize
deployment, release, production access, production composition, current or
default promotion, certification, current compliance, issue #192 closure, or
a security waiver.

### 14.4 Implemented evidence surface

The approved implementation adds one focused, test-owned ASGI composition in
`kernel/tests/test_security_audit_runtime_cross_slice.py`. Its eleven fixed
pytest nodes execute all thirteen `XSLICE-*` invariants through the accepted
tenant and audit fixtures. The canonical review-baseline inventory is updated
mechanically from 3,570 to 3,581 entries. No production path is changed.

Local execution intentionally skips all eleven nodes when the required hosted
tenant or audit PostgreSQL admin route is absent. Hosted acceptance requires
all eleven nodes to execute and pass. Section 14.5 makes exact-head review,
admitted hosted gates, trusted publication, and the final scope/cancellation
report prerequisites to merge.

### 14.5 Merge stop rule

Merge only after every invariant passes, the exact three-path envelope is
preserved, the exact head has zero demonstrated Blockers, required admitted
hosted gates and publication are green, the live card and approval remain
retrievable in order, no later cancellation exists, and the required pre-merge
scope report is posted. New ideas, Preferences, hypothetical deployment
hardening, and separate trust boundaries become Follow-ups and do not reopen
this decision.

## 15. Version 2 closure-correction Phase A contract

Sections 1 through 14 preserve the complete version 1 design and its
historical approval and merge evidence. Version 2 does not reinterpret that
work. This section is the complete controlling Phase A contract for the narrow
post-closure correction. Where a version 1 statement excludes provider
availability evidence, that exclusion continues to prohibit a live provider
claim but no longer excludes executed evidence for the runtime's exact typed
unavailability seam.

### 15.1 Problem and goal

Issue #192 explicitly requires real-ASGI/PostgreSQL hostile evidence for an
unavailable key. Version 1 joined the accepted runtime and both PostgreSQL
services, but its HMAC factory always succeeds. Lower-level KMS, HMAC, health,
and gap tests do not prove the joined request ordering when HMAC creation
refuses.

The one problem is therefore a missing issue-level evidence case, not a
currently demonstrated production-code defect. Version 2 must establish that
one mapped authentication denial whose correlation-HMAC creation raises exact
`CorrelationHmacUnavailable`:

1. returns only the fixed audit-unavailable ASGI result;
2. cannot start principal resolution or tenant UnitOfWork entry;
3. cannot change tenant knowledge state or report an audit event as stored;
4. marks the authentication health lane not ready and opens the bounded live
   gap;
5. exposes no protected input through the accepted evidence surfaces; and
6. is followed by a later independent same-lane denial that stores its own
   event, restores health, and durably closes the prior unknown-count gap
   without retrying the failed request.

If the focused case demonstrates that existing production code violates any
of those conditions, implementation stops before changing production code and
requires a versioned contract amendment.

### 15.2 Learning value

This correction validates that the accepted typed key-service failure crosses
the same health, gap, producer, ASGI, tenant, and two-service composition as an
audit-database connection failure. It reduces the demonstrated risk that
issue-level closure inferred key-unavailability behavior from isolated unit
tests that never executed the joined state transitions.

### 15.3 Non-goals

Version 2 does not:

- change production Python, SQL, migrations, roles, grants, provisioning,
  configuration, workflows, deployment, or HTTP routes;
- call Cloud KMS or prove provider availability, IAM, key custody, key
  readiness, rotation, destruction, clocks, or secret distribution;
- change `CorrelationHmacUnavailable`, `SecurityAuditHealth`, live-gap
  semantics, producer mapping, exception mapping, retry, or readiness;
- add a key, credential, provider client, network call, scheduler, queue,
  spool, timer, worker, or automatic retry;
- suppress credential-bearing dataclass representations or resolve the
  separate diagnostic-representation finding;
- protect export-output custody or delivery;
- change production clock, timer, route, provider, or secret-custody evidence;
- repair issue #334 or complete execution-root/source-capability governance;
- authorize production composition, deployment, release, certification,
  current compliance, or issue closure; or
- broaden the original version 1 test-owned ASGI evidence claim into a claim
  that `kernel.api` publishes a governed production route.

### 15.4 Trust model

#### Protected assets

The protected assets are denial preservation, tenant truth and knowledge
state, the absence of a falsely reported audit append, the exact health lane,
the bounded durable gap posture, the no-retry rule, and the absence of tokens,
identity, tenant, Party, route, DSN, password, exception detail, or provider
key material from responses, captured output, and durable audit evidence.

#### Trusted components

Version 2 trusts the exact reviewed repository head; the accepted tenant and
audit fixtures; PostgreSQL authentication, `session_user`, transaction and
clock behavior; the existing `ApplicationRuntime`, authentication producer,
principal resolver, tenant UnitOfWork, audit client, health observer, live-gap
controller, and bounded reader; and the existing test-owned FastAPI handler.

One test-owned switchable HMAC factory is trusted only to implement the
existing `CorrelationHmacFactory` protocol. On an explicitly armed next call,
it raises the production type `CorrelationHmacUnavailable`. Otherwise it
returns the same accepted deterministic `CorrelationHmac` carrier as version
1. It is not a key authority, KMS emulator, provider readiness source, or
source of production key material.

#### Untrusted actors and inputs

Authorization bytes, fictional tokens, request headers and bodies, ASGI
ordering, all identity and tenant canaries, DSN and exception canaries, the
typed HMAC refusal, database exception text, test output, and durable rows are
untrusted until the exact assertions and conformance gates validate them.

The supported runtime entry point is public
`ApplicationRuntime.authenticate(token)` invoked by the already accepted
test-owned ASGI handler. The handler creates no production route authority.
The hostile state is reached through an explicit test protocol seam, not by
mutating a private production field or monkeypatching production results.

#### Explicitly excluded attacker capabilities

Arbitrary in-process mutation, reflective object replacement, local source
substitution after exact-head selection, compromised dependencies, arbitrary
filesystem mutation, host or database-server compromise, repository-owner or
trusted-operator compromise, KMS administrator compromise, and a malicious
test runner are out of scope. Live KMS networking, IAM, custody, provider
timing, and production secret injection are also out of scope. The test proves
the joined runtime response to the exact typed failure only.

### 15.5 Authority map

| Decision | Sole authority | Explicit non-authorities |
| --- | --- | --- |
| ASGI scheduling and fixed terminal response | Existing test-owned FastAPI handler calling public runtime operations | A claim that `kernel.api` exposes a governed route |
| Mapped authentication denial | Existing deterministic verifier and `AuthenticationAuditProducer` closed outcome map | HMAC seam, response text, caller-selected reason |
| HMAC availability for this scenario | One next call of the switchable test factory, returning the accepted carrier or raising exact `CorrelationHmacUnavailable` | Generic exception, audit database, HTTP response, live provider posture |
| Provider-specific failure semantics | Existing focused `GoogleKmsCorrelationHmac` tests | This cross-slice test or deterministic carrier |
| Authentication health state | Existing `SecurityAuditHealth` start/completion ordering | HTTP status, gap state, test assertion order |
| Live-gap state and close record | Existing `SecurityAuditGapController`, `SecurityAuditGapClient`, and audit PostgreSQL functions/clocks | Python wall clock, caller count, HMAC seam |
| Audit append outcome | Exact audit producer LOGIN, `PreTenantAuditClient`, and audit PostgreSQL append function | Recorder contents alone, tenant database, response text |
| Principal and tenant effects | Tenant PostgreSQL through `PrincipalBindingResolver` and `TenantUnitOfWorkManager` | Audit row, HMAC seam, request headers |
| Audit observation | Existing committed access-intent and bounded-reader protocol | Direct table scan, COPY, export, break-glass, private state |
| Test admission | Exact collected pytest node, canonical inventory, exact-head review, and admitted gates | RFC prose, skipped local node, earlier-head result |

No fallback logger, tenant-table audit path, duplicate HMAC state, alternate
gap writer, retry path, or production dependency-injection surface is added.

### 15.6 State machine and ordering

The first request follows this exact order:

```text
ASGI_REQUEST
  -> MAPPED_AUTHENTICATION_DENIAL
  -> AUTHENTICATION_GAP_ATTEMPT_STARTED
  -> AUTHENTICATION_HEALTH_ATTEMPT_STARTED
  -> CORRELATION_HMAC_UNAVAILABLE
  -> HEALTH_ATTEMPT_FAILED
  -> GAP_OPENED_WITH_UNKNOWN_COUNT
  -> FIXED_AUDIT_UNAVAILABLE_RESPONSE
  -> REQUEST_TERMINAL
```

HMAC refusal occurs before the audit appender receives a carrier. Principal
resolution, tenant UnitOfWork entry, tenant SQL, and audit append are forbidden
after that refusal. The health failure completes before the exception leaves
the inner sink. The outer gap controller records the failed attempt and
rethrows the original typed error. Because that type does not prove whether a
durable audit event exists, the accepted gap count is unknown rather than an
invented exact count.

Recovery is a new request, never a retry:

```text
NEW_ASGI_REQUEST
  -> DIFFERENT_MAPPED_AUTHENTICATION_DENIAL
  -> GAP_AND_HEALTH_ATTEMPTS_STARTED
  -> CORRELATION_HMAC_CREATED
  -> PRE_TENANT_FAILURE_COMMITTED
  -> HEALTH_ATTEMPT_SUCCEEDED
  -> UNKNOWN_COUNT_GAP_COMMITTED_AND_CLEARED
  -> ORIGINAL_AUTHENTICATION_DENIAL_RESPONSE
  -> REQUEST_TERMINAL
```

The fixture must establish two distinct PostgreSQL system identifiers and take
bounded before-snapshots before arming the failure. A lock protects the
one-call switch so the test does not infer ordering from wall time. Audit
PostgreSQL remains authoritative for event and gap time. There is no
cross-database transaction and no time-of-check/time-of-use claim between the
services.

Forbidden transitions include HMAC refusal to appender invocation, principal
resolution, tenant entry, tenant commit, HTTP success, or a claimed stored
event; health recovery without a later successful same-lane attempt; gap clear
without its durable close append; and replay of the failed request.

### 15.7 Invariants and acceptance criteria

All version 1 `XSLICE-001` through `XSLICE-013` invariants remain controlling.
Version 2 adds exactly two stable invariants.

#### `XSLICE-014` — typed HMAC unavailability is fail-closed before storage

For a real ASGI request with a mapped authentication denial, exact
`CorrelationHmacUnavailable` from the next HMAC creation returns the fixed 503
audit-unavailable result. The audit appender records no returned result, no
new `PRE_TENANT_FAILURE` is durably visible for that request, principal
resolution and tenant UnitOfWork counts are unchanged, and the tenant
knowledge head is unchanged. The authentication health lane is `NOT_READY`
and the live-gap controller is `OPEN` when the request terminates.

#### `XSLICE-015` — same-lane recovery is independent, bounded, and leak-free

After HMAC availability is restored, one later independent mapped denial on
the authentication lane stores exactly its own accepted event, changes health
to `READY`, and closes the prior gap to `CLEAR`. The durable gap event reports
an unknown interval count and does not claim the failed request was stored or
retry it. Tokens, identity, tenant, Party, batch/request, route, DSN, password,
and exception canaries are absent from the fixed responses, captured
stdout/stderr, formatted accepted evidence, and durable event projection. The
harness supplies no raw provider key material.

Acceptance additionally requires the existing two-service, bounded-reader,
finite-timeout, no-production-change, exact-inventory, and no-skip hosted
invariants to remain true.

### 15.8 Production-reachable negative cases

| Invariant | Counterexample from the supported runtime boundary | Required result |
| --- | --- | --- |
| `XSLICE-014` | POST a mapped malformed credential to the accepted test ASGI handler after arming the next HMAC call to raise exact `CorrelationHmacUnavailable`. | Fixed 503; no appender result, resolver call, tenant entry, tenant head change, or durable pre-tenant event; health not ready and gap open. |
| `XSLICE-015` | Restore the factory and POST a later distinct mapped refusal on the same lane. | The later event alone is stored; health becomes ready; one unknown-count gap closes; the first request is not retried and no canary leaks. |
| `XSLICE-001` | Point the tenant and audit fixtures at the same PostgreSQL system. | Fixture fails before ASGI construction. |
| `XSLICE-010` | Put unique canaries in both requests and accepted evidence surfaces. | No forbidden value appears in response, output, or durable event projection. |
| `XSLICE-011` | Replace the bounded reader with direct or unbounded audit SQL. | Design fails review; such output is not acceptance evidence. |
| `XSLICE-012` | Skip the new node in admitted hosted execution, add an unbounded wait, or omit its canonical inventory entry. | Hosted or conformance admission fails. |
| `XSLICE-013` | Change production code, provider configuration, SQL, workflow, or a fourth path to make the case pass. | Stop for a new version or separate boundary before editing. |

No negative case mutates a private production field, monkeypatches a
production result, or invents an unsupported runtime state.

### 15.9 Proposed architecture and smallest change

Within `kernel/tests/test_security_audit_runtime_cross_slice.py` only:

1. replace the test-only `_DeterministicHmac` with `_SwitchableHmac`;
2. give it a lock, a one-shot next-call refusal flag, and `refuse_once()`;
3. make `create()` atomically consume one armed refusal and raise exact
   `CorrelationHmacUnavailable`, otherwise returning the existing accepted
   deterministic carrier;
4. expose that same factory on `_Harness` while continuing to bind it to both
   existing health lanes; and
5. add one finite test named
   `test_hmac_failure_denies_then_later_lane_success_closes_gap` that executes
   the state transitions and observations above.

The canonical inventory changes mechanically from 3,581 to 3,582 collected
nodes. The test module must remain at or below its existing 800-line
architecture budget. No production source, shared test framework, new fixture
module, generic provider emulator, or architecture-checker change is needed.

This is the minimum coherent solution because an isolated unit test would
repeat the evidence gap, a live KMS call would add unrelated custody and
provider boundaries, and a production route or injection seam would create
authority solely for testing.

### 15.10 Elegance audit

- **Sources of truth:** one typed test availability switch, one tenant
  PostgreSQL authority, one audit PostgreSQL authority, one health owner, one
  gap owner, and one canonical test result.
- **Authoritative transitions:** HMAC `create()`, health completion, audit
  append commit, gap close append, and request terminal response.
- **Duplicated fields:** none in production. The existing deterministic HMAC
  carrier shape remains defined once.
- **Compatibility surfaces:** none. No alias, optional provider bag, fallback,
  mutable global, or production constructor is introduced.
- **New abstraction count:** zero outside the existing test module; the
  existing test factory is renamed and gains one bounded behavior.
- **Deletion:** the obsolete always-successful test class name is removed.
  No accepted production behavior is deleted.
- **Rewrite assessment:** modifying the existing focused harness is cleaner
  than a new test application or production rewrite.

### 15.11 Pull request boundary

The one implementation PR is draft PR
<https://github.com/samovers/OFARM2/pull/345>.

The exact Phase A path allowlist is:

1. `docs/rfcs/OFARM_Security_Audit_Cross_Slice_Closure_Evidence_RFC_v0_1.md`

After exact later approval, the exact Phase B path allowlist is:

1. `docs/rfcs/OFARM_Security_Audit_Cross_Slice_Closure_Evidence_RFC_v0_1.md`
2. `kernel/tests/test_security_audit_runtime_cross_slice.py`
3. `conformance/review_baseline_test_inventory.json`

The reviewed base is
`bbf8f0fb9235ffca4f891d789f25e6f1aed7fab8`. There is no stacked pull-request
dependency. Reviewers must not require live KMS/provider evidence, production
code, a production route, new SQL or authority, credential-representation
hardening, source-governance changes, issue #334, deployment evidence, or
issue closure from this PR.

Separate Follow-ups remain:

- credential-bearing diagnostic representation correction recorded in the
  [post-closure issue comment](https://github.com/samovers/OFARM2/issues/192#issuecomment-5444455513);
- protected export-output custody and delivery;
- production clock, timer, route, provider, and secret-custody evidence;
- issue #334 package-initializer reachability; and
- complete execution-root/source-capability governance.

Stop and require a new decision version before editing if implementation or
review needs production code, another exception contract, a different health
or gap semantic, live provider credentials, a fourth path, more than 800 test
module lines, an architecture rule change, or any material change to the trust
model, authority map, invariant, non-goal, or effect. A production defect
revealed by the test is evidence for a separate amended boundary, not
permission to fix it in this version.

### 15.12 Provisional design record

Not provisional for the stated evidence scope. A typed protocol failure is the
correct composition seam because this decision tests runtime ordering after
the provider has refused, not why the external provider refused. It does not
stand in for KMS custody, IAM, readiness, or production-route evidence.

The AI-assisted approval remains provisional pre-deployment repository
authority only. Before deployment it must be replaced by independently
human-controlled and independently verifiable approval. Evidence requiring
redesign includes inability to reach the state through the public runtime
surface, a need to mutate private production state, a need for production code
or provider credentials, or failure to fit the exact three-path and 800-line
envelope.

### 15.13 Traceability and verification

| Invariant | Owning code exercised | Negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `XSLICE-001` | Existing tenant and audit fixtures and system-ID check | Same-system routes | Distinct nonempty PostgreSQL system IDs | Focused hosted module and both migration preflights |
| `XSLICE-007` | Existing audit client, health, and gap path | Refused audit connection | Existing connection-failure recovery remains passing | Focused module plus health/gap suites |
| `XSLICE-010` | Closed event projection and fixed ASGI results | Unique input and exception canaries | Forbidden-value absence | Focused module plus existing leakage suites |
| `XSLICE-011` | Existing bounded query runner | Direct/unbounded observation | Accepted bounded event page only | Bounded-query suite and focused module |
| `XSLICE-012` | Pytest inventory and conformance pipeline | Skip, timeout, or inventory drift | 3,582 exact hosted nodes with the new node executed | Collection, inventory check, admitted baselines |
| `XSLICE-013` | Exact Git diff and architecture check | Production or fourth-path edit | Exact three-path equality and unchanged production tree | Package contract, architecture, diff check |
| `XSLICE-014` | HMAC factory, health sink, gap wrapper, authentication producer, ASGI handler, both stores | Exact typed refusal on mapped denial | Fixed 503, no appender/tenant effect, not-ready/open posture | New focused node plus HMAC/health/gap suites |
| `XSLICE-015` | Same components plus real audit append and gap close | Later same-lane independent denial | One later event, one unknown-count gap, ready/clear posture, no leakage | New focused node plus bounded reader and gap suites |

Required Phase A verification is the CPython 3.12 package contract, exact
one-path equality, `git diff --check`, exact-head contract review, and zero
demonstrated Phase A Blockers. A hosted baseline is not evidence for an
RFC-only head and must not run before that review.

After approval, required local Phase B verification is:

- both tenant and audit migration preflights;
- focused cross-slice collection and execution, with honest local skips only
  when hosted routes are absent;
- focused Google KMS HMAC, authentication producer, principal resolver,
  request-router, audit client, health, live-gap, bounded-reader, application
  runtime, tenant UnitOfWork, and concurrency suites;
- canonical inventory regeneration and exact comparison;
- CPython 3.12 package contract and architecture constraints;
- Ruff, `git diff --check`, the 800-line budget, and exact three-path equality.

Review-before-baseline ordering is mandatory. First review the exact Phase B
head against this contract to zero demonstrated Blockers. Only then admit one
hosted source run whose two 3,582-test baselines execute without skips, match
the canonical inventory, pass equivalence, and pass both native lanes. The
trusted publication run must then publish that exact source result. No
earlier-head evidence carries forward.

### 15.14 Open decisions and review disposition

Open decisions: none. Exact `CorrelationHmacUnavailable` is the selected
failure; the existing deterministic carrier is the selected recovery seam;
the existing unknown-count gap rule is preserved; and live provider behavior
remains outside this decision.

Current review disposition:

- Phase A design Blockers: exact-head review pending;
- issue-level evidence Blockers: one, closed only by passing and reviewed
  `XSLICE-014` and `XSLICE-015` evidence;
- Follow-ups: the five separate boundaries listed in section 15.11;
- Preferences: none;
- Phase B: not approved and not started;
- production composition: unauthorized and non-deployable.

After this exact Phase A head has zero demonstrated Blockers, one complete live
card may name decision
`ISSUE192-SECURITY-AUDIT-CROSS-SLICE-CLOSURE-EVIDENCE-001`, version `2`, and
draft PR <https://github.com/samovers/OFARM2/pull/345>. Only this exact later
same-task task-user message can approve Phase B:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-CROSS-SLICE-CLOSURE-EVIDENCE-001 version 2.
```

Merge only after the approved invariants pass, the exact three-path boundary
is preserved, the exact head has zero demonstrated Blockers, required hosted
source and publication gates pass, the live card and approval remain directly
retrievable in order, no cancellation exists, and the required exact-head
scope report is posted. The PR does not close issue #192 automatically.
