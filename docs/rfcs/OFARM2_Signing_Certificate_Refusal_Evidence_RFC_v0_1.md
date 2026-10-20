# Signing certificate-refusal evidence — Phase A v0.1

Decision: `OFARM2-SIGNING-TEST-CERTIFICATE-REFUSAL-001`, version 1.
Status: approved for implementation on 20 October 2026; ordinary CI activation
and merge remain separate.
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
Containment is the existing context manager's completed teardown, proof of actual
native hostname rejection, and identity of its one retained worker error. Any
unexpected or combined failure is re-raised unchanged; groups are never filtered.

## Smallest complete correction

Change the certificate consumer, not `WireFaultProxy`'s general behavior:

1. Observe the native handle's hostname-verification result before its existing
   disposal. Use a passive test-only wrapper at the existing owner-close boundary,
   always calling the real close even if observation fails. Retain only the
   boolean proof needed by the assertion; do not expose driver text publicly.
2. Keep the safe public exception, one native handle, one accepted connection,
   no query or downgrade, and native-handle disposal assertions.
3. Remove the in-body read and clear of `proxy.failure`. Let the existing
   context-manager exit perform its single stop, bounded join and disposal.
   Do not add another join or a second completion/ownership state.
4. Outside that context, acknowledge a raised group only for the certificate
   case and only if it contains exactly one child, that child is the identical
   object held in `proxy.failure`, and it is one `ssl.SSLError` or an `EOFError`
   after a completed TLS 1.2/1.3 handshake. The worker must be terminated and
   all fixture sockets/listener closed. Require actual native wrong-hostname
   refusal, one native handle/accepted connection, no forwarded PostgreSQL
   frames/query, and only the accepted socket and TLS wrapper in the existing
   ownership list. Existing normal exit also retains these final assertions.
5. Re-raise the original group unchanged if any guard fails. A body failure,
   a teardown-only failure, an extra cleanup failure, a nested group or a
   surviving worker cannot match the identity/single-child predicate. Do not
   flatten a group, remove selected leaves, clear `proxy.failure`, or replace
   its traceback. For the password case, every group propagates unchanged.

The existing helper may retain a peer EOF before stop or suppress stop-driven
I/O afterwards. Both schedules become valid only when the real certificate
refusal and disposal assertions hold. The consumer does not need to force one
schedule or modify that existing helper rule. Controlled tests still exercise
both orderings, including a late-retained worker error after the old in-body
inspection point. This uses the current two-second teardown join only; it adds
no extra wait budget.
The production entry remains `SigningAuthorityReader.current`. No production
method, verification setting, timeout, retry, credential decision, driver
implementation or database behavior changes. The shared proxy still retains
unexpected running-state EOF; its existing stop/withholding exception remains.

No new proxy mode, exception hierarchy, lifecycle state, framework, general
error whitelist or alternate authority path is proposed. The existing
unsynchronized consumer assertion/clear sequence is deleted; no replacement
mutation of the worker result or compatibility fallback is introduced.

## Invariants and focused evidence

| Invariant | Owning assertion and required evidence |
| --- | --- |
| EC01 — Actual credential refusal | Real wrong-hostname TLS reaches the unchanged reader, records native hostname rejection, returns only safe `SigningAuthorityUnavailable`, opens one client and emits no query, plaintext retry or upstream connection. A non-certificate native failure cannot justify EOF acknowledgement. |
| EC02 — Completed observation | Acknowledge worker failure only after the existing context-manager teardown has joined and disposed its owners. Exercise worker-first and client-first schedules with events at existing seams, for TLS 1.2 and TLS 1.3. The pre-change assertion must fail the deterministic worker-first control. No extra join, sleeps or retry-until-pass oracle. |
| EC03 — Narrow acknowledgement | A raised group must have exactly one child identical to the retained worker failure, and that child must be a post-handshake EOF or TLS alert under EC01/EC02 and no extra ownership/traffic. Pre-TLS EOF, absent hostname proof, unrelated errors, an extra child or a nested group propagate unchanged. |
| EC04 — Honest failures | Original unexpected startup/relay EOF, framing errors, and body/worker/cleanup groups remain visible. Do not extract an expected leaf and discard the rest of a group. Keep the existing shared-proxy failure tests. |
| EC05 — Ownership and real consumers | Every native handle is disposed; every test socket is closed; the worker is joined. Keep real password rejection, successful TLS forwarding, signing database and physical-outcome consumer assertions. A surviving worker or cleanup error cannot pass. |
| EC06 — Complete acceptance | Regenerate the exact inventory without exclusions. Require package/focused checks, fresh exact-head content review, both complete sequential baselines and their unchanged equivalence comparison, all platform/native evidence, isolated publication and external receipt validation. |

Scheduling and fault controls may wrap existing calls, but cannot replace TLS,
invent a successful certificate rejection, supply a fake database result or
alter production ownership. Ordinary full evidence remains mandatory after
implementation and review. No local diagnostic substitutes for it.

## Scope and code excellence

Expected areas: `kernel/tests/test_signing_observation_database.py`, focused
controls in `kernel/tests/test_signing_certificate_refusal.py`, the mechanically
regenerated `conformance/review_baseline_test_inventory.json`, and this durable
correction to the earlier explicit consumer contract. This draft begins with
design and will carry its complete implementation; it is not an enabling-only PR.

EXC-001: native verification is the sole credential decision and the joined
worker's existing failure slot is the sole proxy result. EXC-002: reuse existing
ownership and teardown; no second join, shadow ledger or duplicated driver. EXC-003:
EC01–EC06 trace to the consumer guards, controlled schedules and existing full
acceptance. EXC-004: delete the unsynchronized assertion/clear path without a new result mutation. EXC-005:
no new shared abstraction; any compact test helper must serve these actual
controls. EXC-006: merely adding EOF to the current assertion leaves the race;
globally suppressing EOF hides defects; forcing one TLS version or retrying
removes required evidence. A new proxy configuration flag adds an unnecessary
general policy for one consumer. Joining and clearing the worker result inside
the body duplicates completion handling already owned by context-manager exit;
consume that completed result instead. EXC-007 preferences do not delay acceptance.

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

The reviewed Phase A and complete card were followed by the task user's exact
version-1 approval in the coordinating Codex task. The original card is message
`msg_08cb29efe0a907b2016ad71d83438c819198dc877e80ff3cfd`; its later approval is
message `01a15879-4f4f-7e43-b286-36c0a5bab259`, both in task
`01a14a01-ece2-7bd1-ba2e-efb4fd96c0f0`. These identifiers are navigation; the
directly retrievable original task-user message supplies authority.
CI admission and merge remain separate later actions.
Reapproval is required for a changed capability, boundary, authority map, effect,
non-effect, invariant, irreversible behavior, named PR or deployment posture.

## Implementation and regression trace

The certificate consumer now observes native hostname rejection at real owner
disposal and reads the proxy result after its existing context manager exits.
Its single-child identity guard preserves the original group and traceback on
refusal. The helper `_certificate_refusal_complete` reads existing ownership
facts and the one native observation; it adds no proxy state or completion path.
Normal teardown must prove the same refusal and disposal facts.

The shared proxy and production reader/I/O files remain unchanged. The original
certificate and password test node IDs and every existing inventory entry remain.
The dedicated certificate-refusal module adds 28 cases:

- EC02 exercises TLS 1.2 and TLS 1.3 with worker-first, client-first stop, and
  client-first late retention, using events at the existing disposal/join seams.
  Against the unchanged consumer, four schedules failed and two passed.
- EC01/EC05 remove native proof, client uniqueness, absence of traffic/upstream
  ownership, or completed disposal and require the original group to propagate.
- EC03/EC04 cover pre-handshake EOF, another error object, nested groups, real
  body/worker-cleanup/teardown-cleanup failures and unrelated worker errors.
  Expected peer-alert handling retains actual native hostname-refusal proof.
- Normal exit without native proof refuses. A failed diagnostic observation
  still calls real native disposal.

The new loopback upstream listener is a connection trap and never supplies
PostgreSQL results. The existing database credential, successful TLS and
physical-outcome consumer cases retain their real roles and database authority.
These focused checks do not replace either complete ordinary baseline or its
publication and external-verification gates.

The new module keeps the original proxy test file byte-identical and satisfies
the package's 800-line test-module limit. This replaces the predicted addition
to that existing file, without changing the capability, evidence requirements
or primary trust boundary.

Next: obtain fresh exact-head content review and prepare ordinary CI admission.
