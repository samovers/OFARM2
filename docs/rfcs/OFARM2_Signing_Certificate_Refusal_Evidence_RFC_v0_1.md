# Signing certificate-refusal evidence — Phase A v0.1

Decision: `OFARM2-SIGNING-TEST-CERTIFICATE-REFUSAL-001`, version 1.
Status: proposed; implementation, CI activation and merge are not approved.
Delivery: [#418](https://github.com/samovers/OFARM2/issues/418). The named draft
PR is identified by its description and the later same-task decision card.

## Problem and boundary

The certificate consumer can fail after correct production refusal solely
because its proxy worker finishes sooner. Main source
[39303072823](https://github.com/samovers/OFARM2/actions/runs/39303072823),
job 118233088334, failed baseline 2 with `EOFError("test peer closed")` at the
post-TLS `_startup` read. It reported one failed and 5,326 passed tests. This
was not a timeout. PR #409's two accepted baselines passed the unchanged case.

The current test reads and clears `proxy.failure` while the worker is live. It
assumes certificate rejection means either no observed worker failure or an
`ssl.SSLError`. Real libpq can complete TLS, reject the certificate hostname,
and close before sending PostgreSQL startup. The server then sees EOF. If the
consumer reaches teardown first, its existing stop condition can suppress that
EOF; if the worker records EOF first, the consumer fails.

Capability: truthful, schedule-independent certificate-refusal evidence.
Primary boundary: **test-owned wire transport and evidence fidelity**.
The PR will contain this complete correction and its tests and inventory.
It is new Delivery work following merged #413, not recovery of that PR.

The [prior lifecycle RFC](OFARM2_Signing_Test_Proxy_Lifecycle_RFC_v0_1.md)
expressly preserved the certificate consumer's existing handling. This proposal
changes that narrow test-evidence contract and therefore needs its own reviewed
decision and approval. It leaves the prior lifecycle mechanism and shared proxy
error-retention rules intact. Historical approvals and results remain historical.

## Evidence and limits

An external diagnostic calls the unchanged certificate test with real production
reader code, real libpq and real TLS. A loopback listener acts only as an upstream
connection trap; it never supplies PostgreSQL responses or authority. The test
must refuse before reaching it or reading a receipt.

On macOS, ten natural cases for each of TLS 1.2 and TLS 1.3 passed. Waiting for the
real worker immediately after native-handle disposal reproduced the assertion
and EOF in both versions. Every case observed the native hostname-mismatch
diagnostic, one accepted connection, no upstream connection or query, a disposed
native handle, joined worker and closed owned sockets. Waiting changes scheduling,
not TLS bytes, credential verification or worker exceptions.

The first sandbox invocation failed to bind before executing a test. A diagnostic
serializer defect affected only the first report's grouped-exception details;
the worker EOF records and all 22 outcomes remain intact. Two fixed-serializer
worker-first executions again failed and retained both original exceptions.
These are bounded local diagnostic executions, not hosted or database acceptance.
The same fixed 22-case diagnostic on local Linux x86_64 with CPython 3.12.13,
OpenSSL 3.0.20, psycopg 3.3.4 and libpq 18 reproduced one natural TLS 1.2 failure
and both worker-first failures: 19 passed, three failed, all retained. The
unchanged dependency lock installed with hash checks. The disposable container
removed itself. This local container is not the GitHub-hosted baseline.

Two further real TLS probes confirmed that the native hostname-mismatch proof
is available at the existing owner-close boundary, and that the joined proxy's
existing ownership list contains exactly the accepted socket and TLS wrapper.
Both still execute and fail the original assertion; they do not implement a fix.

## Authority and trust model

The task user owns this semantic decision and later, separately, CI activation
and exact-head merge authorization. Reviewers identify demonstrated defects;
they do not grant scope. CI and publication own mechanical evidence custody.
GitHub owns native merge state.

Production TLS/libpq owns certificate verification; the production reader owns
safe public refusal and client disposal. The test owns its generated identity,
proxy, scheduling controls and assertions. PostgreSQL remains the only upstream
database authority. Existing signing, key, role, tenant, audit and deployment
authorities remain unchanged.

Protected assets are credible refusal evidence and complete resource/failure
accounting. Wire input and thread timing are untrusted. The trusted side is the
pinned local fixture and unchanged production reader/native driver. Arbitrary
process-memory corruption, hostile interpreter replacement and an unresponsive
host are outside this fixture's existing model.

The primary risk is acknowledging a genuine proxy defect as expected refusal.
Containment is a completed-worker snapshot plus proof of actual native hostname
rejection and a narrow, single-error predicate. Failed guards retain the original
failure; grouped failures are never filtered.

## Smallest complete correction

Change the certificate consumer, not `WireFaultProxy`'s general behavior:

1. Observe the native handle's hostname-verification result before its existing
   disposal. Use a passive test-only wrapper at the existing owner-close boundary,
   always calling the real close even if observation fails. Retain only the
   boolean proof needed by the assertion; do not expose driver text publicly.
2. Keep the safe public exception, one native handle, one accepted connection,
   no query or downgrade, and native-handle disposal assertions.
3. For the certificate case, join the proxy worker using the existing two-second
   bound before inspecting its terminal failure. A surviving worker is a failure;
   do not set stop early to manufacture a passing outcome.
4. Require actual native wrong-hostname refusal and no upstream owner or protocol
   traffic. The existing ownership list must contain only the accepted socket and
   its TLS wrapper. Do not add a second ownership ledger.
5. Acknowledge only no failure, one expected `ssl.SSLError`, or one `EOFError`
   after a completed TLS 1.2/1.3 handshake. EOF before completed TLS, another
   failure type, an exception group, extra ownership or protocol traffic fails.
   Clear the single acknowledged error only after all guards pass and the worker
   has terminated. Existing context-manager exit still owns final disposal and
   propagation of any cleanup failure.

The production entry remains `SigningAuthorityReader.current`. No production
method, verification setting, timeout, retry, credential decision, driver
implementation or database behavior changes. The shared proxy still retains
unexpected running-state EOF; its existing stop/withholding exception remains.

No new proxy mode, exception hierarchy, lifecycle state, framework, general
error whitelist or alternate authority path is proposed. The existing
unsynchronized consumer assertion/clear sequence is replaced, not retained as
a fallback.

## Invariants and focused evidence

| Invariant | Owning assertion and required evidence |
| --- | --- |
| EC01 — Actual credential refusal | Real wrong-hostname TLS reaches the unchanged reader, records native hostname rejection, returns only safe `SigningAuthorityUnavailable`, opens one client and emits no query, plaintext retry or upstream connection. A non-certificate native failure cannot justify EOF acknowledgement. |
| EC02 — Completed observation | Read/acknowledge worker failure only after bounded join. Exercise worker-first and client-first schedules with events at existing seams, for TLS 1.2 and TLS 1.3. The pre-change assertion must fail the deterministic worker-first control. No sleeps or retry-until-pass oracle. |
| EC03 — Narrow acknowledgement | A single post-handshake EOF or TLS alert is acknowledged only under EC01/EC02 and no extra socket ownership/traffic. Pre-TLS EOF, absent hostname proof, extra ownership or traffic, and unrelated exception types fail. |
| EC04 — Honest failures | Original unexpected startup/relay EOF, framing errors, and body/worker/cleanup groups remain visible. Do not extract an expected leaf and discard the rest of a group. Keep the existing shared-proxy failure tests. |
| EC05 — Ownership and real consumers | Every native handle is disposed; every test socket is closed; the worker is joined. Keep real password rejection, successful TLS forwarding, signing database and physical-outcome consumer assertions. A surviving worker or cleanup error cannot pass. |
| EC06 — Complete acceptance | Regenerate the exact inventory without exclusions. Require package/focused checks, fresh exact-head content review, both complete sequential baselines and their unchanged equivalence comparison, all platform/native evidence, isolated publication and external receipt validation. |

Scheduling and fault controls may wrap existing calls, but cannot replace TLS,
invent a successful certificate rejection, supply a fake database result or
alter production ownership. Ordinary full evidence remains mandatory after
implementation and review. No local diagnostic substitutes for it.

## Scope and code excellence

Expected areas: `kernel/tests/test_signing_observation_database.py`, focused
controls in `kernel/tests/test_signing_observation_proxy.py`, the mechanically
regenerated `conformance/review_baseline_test_inventory.json`, and this durable
correction to the earlier explicit consumer contract. This draft begins with
design and will carry its complete implementation; it is not an enabling-only PR.

EXC-001: native verification is the sole credential decision and the joined
worker's existing failure slot is the sole proxy result. EXC-002: reuse existing
ownership and teardown facts; no shadow ledger or duplicated driver. EXC-003:
EC01–EC06 trace to the consumer guards, controlled schedules and existing full
acceptance. EXC-004: remove the unsynchronized assertion/clear path. EXC-005:
no new shared abstraction; any compact test helper must serve these actual
controls. EXC-006: merely adding EOF to the current assertion leaves the race;
globally suppressing EOF hides defects; forcing one TLS version or retrying
removes required evidence. A new proxy configuration flag adds an unnecessary
general policy for one consumer. EXC-007 preferences do not delay acceptance.

No production signing, identity, custody, tenant/database, runtime readiness,
audit, workflow, publication or approval authority change is included. No test
filtering, assertion bypass, timeout extension or waiver is included. PR #409's
optional KeyboardInterrupt test preference, PR #415 and other follow-ups stay
separate. No cross-boundary exception is needed.

## Posture and gates

This is provisional development evidence under the existing healthy-host and
pinned-runtime assumptions. It grants no production or deployment readiness.
An interpreter/libpq change that produces a different outcome requires renewed
diagnosis rather than broadening the predicate silently. Before deployment,
the existing approval arrangement still requires independently human-controlled
and verifiable authority.

Prepare the one Delivery issue and draft PR, review Phase A to zero Blockers,
then present the exact new decision card. Only its later exact task-user approval
permits implementation. CI admission and merge remain separate later actions.
Reapproval is required for a changed capability, boundary, authority map, effect,
non-effect, invariant, irreversible behavior, named PR or deployment posture.

Next: review and publish this prepared Phase A, then obtain its semantic decision.
