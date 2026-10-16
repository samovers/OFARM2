# Signing test-proxy lifecycle repair — design v0.1

**Status:** implemented in PR413; focused local checks passed; hosted acceptance pending.
**Delivery:** [#412](https://github.com/samovers/OFARM2/issues/412), child of #167,
prerequisite of #410 / PR411 and transitively #408 / PR409.
**Decision:** `OFARM2-SIGNING-TEST-PROXY-LIFECYCLE-001`, version `1`.
**Primary boundary:** test-owned wire transport and evidence fidelity.

## Problem and evidence limits

[PR411 source 38740690045](https://github.com/samovers/OFARM2/actions/runs/38740690045)
logged 5,206 passes, one failure and one warning in its first baseline. The
password-refusal test reached `WireFaultProxy._relay`'s framing assertion;
`__exit__` then raised `test proxy failed`. Both affected files are identical
to main `301bf4aa3196b503ec114ebfa0f455be818627a4`. The source failed before the
job limit. Its log does not identify the offending bytes or exact interleaving.

A bounded local diagnostic on Python 3.12.13/macOS arm64 used real TLS 1.2 and
1.3 socket pairs and the unchanged relay/exit methods. Scheduling the reader
after `SSLSocket.shutdown` clears TLS state exposed TLS record bytes to
PostgreSQL framing and reproduced the same assertion. That diagnostic forced
the read before raw shutdown; safe cleanup must not assume raw shutdown makes
already buffered ciphertext unreadable on every supported platform. Both
ordinary-order controls passed; every diagnostic worker/socket was reclaimed.
This proves a sufficient fixture defect, not the hosted event's precise cause,
production authentication behavior, a Linux acceptance result or a timing fix.

The already merged `_physical_outcome_proxy.py` and its regression tests provide
the accepted direct pattern: native socket wake-up preserving TLS state,
stop-aware registration, explicit handshake after registration and disposal
after the I/O owner finishes. This record preserves that ownership rule and
its evidence limits for later fixture maintenance; it adds no runtime policy.

## Capability, authority and containment

Deliver one independently usable capability: the existing signing wire proxy
can stop safely without feeding ciphertext to its application parser, leaking
owned resources or hiding genuine failures. Treat this as approval-governed
test-evidence work: it supports credential-refusal and signing-observation
acceptance, even though production authority and code remain unchanged.

The task user owns semantic approval and later final acceptance. The proxy
owns only its listener, one test worker, test sockets and existing fault modes.
Production signing/receipt validators, credentials, keys, database roles and
client handles retain their existing owners. Reviewers judge the design and
implementation; CI and the separate publisher retain evidence checks/custody;
GitHub retains native merge. Synthetic peers confer no database or signing
authority and cannot replace the unchanged actual-runtime controls.

Protected assets are honest test results and bounded fixture-resource ownership.
Trusted inputs are the reviewed fixture, pinned interpreter/libraries and
pytest-owned local resources. Treat peer bytes, partial I/O, refusal, errors and
stop/registration/read schedules as adversarial inputs. Assume the existing
healthy local host, finite OS operations and scheduling; interpreter/host
compromise and an indefinitely hung kernel are excluded. The main risk is
concealing a real failure while removing a fixture race. Preserve framing,
credential, refusal and disposal assertions and prove hostile cleanup schedules.

## Smallest complete repair and ordering

Retain one `WireFaultProxy`, one worker and one socket ownership list.
Reuse the physical proxy's small direct lifecycle operations locally; importing
its class would create a cycle because it already imports signing helpers.
No common cleanup framework, new thread, descriptor-copy strategy or registry.

The lifecycle is **created → running → stopping → joined → disposed**;
failure is retained alongside the lifecycle and never converts it to success.

1. Register each acquired socket under one fixture-local lock. Registration
   after stop immediately wakes that socket. Keep an explicit local owner
   across acquisition/registration failures; a created Unix socket is owned
   before its connect attempt. Preserve existing TCP/Unix route handling.
2. Wrap TLS with automatic handshake disabled, register the returned wrapper,
   then perform the handshake. The wrapper must be wakeable during incomplete
   handshake. A detached original socket is not ownership of its TLS wrapper.
3. On teardown, set stop and close the listener, then wake registered sockets
   with the base `socket.socket.shutdown` operation. It must not clear the
   active SSL object's state. The single signing worker must be woken
   **before** joining; the physical helper's separate-listener ordering does
   not transfer literally.
4. The worker disposes its owned connections after its final I/O, including
   exceptional exits. Teardown joins that owner before final object close and
   sweeps retained objects afterward. One cleanup failure cannot prevent other
   owned cleanup attempts. Coordinate late registration with the same lock.
5. Preserve existing finite bounds: listener polling 0.1s, socket operations
   2s, worker join 2s and relay polling 0.01s. Existing withheld modes remain
   stop-event driven; their 10s wait does not become a teardown delay. Never
   declare success with a live worker or descriptor. If acquisition/cleanup
   cannot satisfy these bounds under the supported test setup, report the
   design gap rather than widening them or claiming successful disposal.

A stop check before `recv` alone leaves a check/read race. Do not suppress
framing assertions, erase failures after stop, relax frame sizes, retry a
failed case or change credential expectations.

Keep signing's current error semantics: `OSError`/`EOFError` are ignored only
during the existing stop/withholding condition; other worker failures remain
observable with their original cause. A body exception propagates unchanged
when there is no fixture failure; concurrent body and fixture failures must
remain inspectable. Cleanup failures must be reported without dropping the
primary failure or skipping remaining disposal. Do not copy physical's broader
ordinary-I/O suppression or COMMIT-specific error behavior. The certificate
test's explicit expected TLS-alert handling remains unchanged.

## Scope, non-effects and provisional posture

Expected implementation areas are `kernel/tests/_signing_observation_proxy.py`,
a focused `kernel/tests/test_signing_observation_proxy.py`, the mechanically
regenerated `conformance/review_baseline_test_inventory.json`, and this record.
Implementation, regressions and inventory belong in this same single PR.
Keep `tls_context`, `_exact`, `_startup`, backpressure injection, DSN/TLS
settings, framing, query forwarding and fault meanings unchanged. Existing
signing database and physical-observer assertions remain intact.

No production source, authority predicate, receipt, key, grant, migration,
runtime deadline, credential check, pool, readiness rule, workflow, CI budget,
accepted evidence policy, publication custody, dependency pin or deployment
changes. In-boundary test-file discovery is explained in the final scope report;
changed capability, boundary, authority, invariant, effect, named PR or posture
requires a new decision. This is separate from the approved PR411/PR409 work.

This is provisional pre-deployment fixture engineering. It is acceptable only
with real-socket race controls plus unchanged actual-runtime verification.
A supported interpreter/TLS change that defeats the ownership sequence, or
failure to preserve cleanup/error behavior, requires redesign before relying
on evidence. A broader fixture framework or support profile is future work,
not an automatic upgrade path. No production-readiness or deployment claim.

## Falsifiable verification

| ID / invariant | Required negative and positive controls |
| --- | --- |
| SP01 TLS ownership | Real TLS 1.2 and 1.3: pause the reader between readiness and `recv`, then release it from a neutral seam reached by both old and new teardown at the wrapper's base socket wake, before the actual shutdown. Prove that this scheduled reader decrypts and forwards the plaintext frame, rather than merely avoiding an error. Apply the same schedule to both helpers: it fails the old helper and passes the repair. Ordinary forwarding also passes. |
| SP02 complete ownership | Stop during accept, partial startup, incomplete TLS handshake, relay read and withholding; race accepted/wrapped/upstream registration with stop; exercise acquisition failure and Unix upstream. Include the worker passing its stop check and re-entering `select` during teardown, on plain and TLS sockets. Every owned worker joins and every owned descriptor closes within existing bounds. |
| SP03 honest errors | Malformed startup/frame, genuine worker error immediately before stop, body-only failure and simultaneous body/worker/cleanup failures stay observable with cause/context intact; remaining cleanup is attempted. Expected stop I/O stays distinct from an unexpected error while running. |
| SP04 credential evidence | Preserve actual `SigningAuthorityReader.current` certificate/password refusal through the existing test: safe refusal, one accepted connection, no query/downgrade, native handles disposed. Retain successful observation and existing result/cancel/deadline controls. |
| SP05 downstream compatibility | Existing physical transport PS11 invokes the actual signing reader under observer cancellation/deadline; its assertions pass. Existing physical-proxy socket tests and shared helper consumers retain their behavior. |
| SP06 evidence and scope | Package/architecture/whitespace pass; inventory adds only reviewed regressions without losing or reattributing existing tests; complete diff proves production/CI owners unchanged. Fresh exact-head content review precedes all expensive hosted work. |

The production entry points protected by SP04/SP05 are the existing signing
reader during startup/mint and its physical-observation consumer. SP01–SP03
exercise only the peer/fixture around those calls, not a new production path.
A synthetic protocol peer proves socket/lifecycle behavior only; it cannot
satisfy database authority or real credential controls.

After implementation, run the new socket suite and affected existing signing
database, physical transport and physical-proxy controls using pinned Python
3.12.13 and the supported disposable PostgreSQL/TLS setup. Record actual
versions/platform, selections, failures and unavailable cases honestly.
Regenerate the inventory using its existing maintenance command. After a
zero-Blocker review naming the full implementation head, use fresh admission
for both complete unfiltered baselines, fixed-policy equivalence, 23 platform
cases, both native architectures and sealed publication. Existing final
human acceptance and exact-head native merge authorization remain required.

Phase A performed only mandatory/cheap checks and design review. It requested
no expensive source run, reused no failed evidence and changed no test code.
The current 45-minute pre-merge budget remains a separate unresolved constraint.
If complete gates cannot pass, report it; this repair grants no bypass or
further identical PR411/PR409 attempt and promises no capacity saving.

## Code excellence and simplest alternative

EXC-001: one worker/lifecycle and socket list own fixture disposal.
EXC-002: one small registration lock closes the stop/registration race; no duplicate
authority, generic proxy layer, parallel implementation or cleanup registry.
EXC-003: SP01–SP06 trace ownership, error and evidence invariants to focused
controls and unchanged runtime assertions.
EXC-004: remove the unsafe SSL-shutdown/close-before-join path; no fallback.
EXC-005: local wake/register/close helpers serve current lifecycle sites.
EXC-006: a stop check or ignored assertion cannot serialize TLS disposal;
the already accepted direct physical-proxy pattern is the simpler sufficient
starting point. Preserve signing-specific topology/error/Unix behavior.

## Implementation evidence and limits

The fixture now preserves TLS state through native wake-up, registers wrappers
before handshake, retains acquisition ownership and joins its single worker
before final disposal. It keeps one worker-failure record; grouped exceptions
retain concurrent body, worker and cleanup errors without losing their original
tracebacks. A lone expected certificate failure remains available through the
existing `failure` attribute. Stop is set before acquiring the registration lock.

On pinned Python 3.12.13/macOS arm64, all 53 focused socket cases passed. The
same neutral SP01 schedule failed against the unchanged base helper for both
TLS versions at its original framing assertion; the repaired reader forwarded
the actual plaintext query. The regression adds no alternate parser or fault
suppression. All 5,207 existing inventory entries are retained unchanged; the
complete inventory now has 5,260 entries.

The unchanged signing database, physical transport and physical-proxy modules
passed all 132 cases against owned PostgreSQL 17.10 with TLS/SCRAM. Actual
certificate/password refusal and PS11 cancellation/deadline controls passed.
One existing Starlette/httpx deprecation warning was reported. No timing shim,
retry, production-source change or relaxed assertion was used. These are local
engineering results, not the required Linux hosted acceptance or a capacity
claim. Complete hosted gates and authenticated publication remain pending.

Next: obtain fresh implementation review before requesting complete hosted
evidence, then present final acceptance only after every applicable gate passes.
