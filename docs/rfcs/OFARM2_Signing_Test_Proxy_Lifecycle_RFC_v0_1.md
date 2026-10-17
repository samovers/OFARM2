# Signing test-proxy lifecycle repair — design v0.1

**Status:** implemented in PR413; version-2 consumer amendment approved;
focused local checks passed; exact-root activation and hosted acceptance pending.
**Delivery:** [#412](https://github.com/samovers/OFARM2/issues/412), child of #167,
prerequisite of #410 / PR411 and transitively #408 / PR409.
**Decision:** `OFARM2-SIGNING-TEST-PROXY-LIFECYCLE-001`, version `2`.
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
runtime deadline, credential check, pool, readiness rule, workflow implementation,
dependency pin or deployment changes. Ordinary main's CI budget stays unchanged.
The approved version-2 amendment below changes only this consumer's permitted CI
evidence route and associated publication provenance, including its separately
granted 60-minute conformance ceiling; #417 owns that separate implementation.
In-boundary test-file discovery is explained in the final scope report;
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
The ordinary 45-minute pre-merge budget remains a separate unresolved constraint.
Version 2 permits the separately granted 60-minute transition route below.
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

## Harness review correction, 17 October 2026

[Review 5546518916](https://github.com/samovers/OFARM2/pull/413#pullrequestreview-5546518916)
identified B1 in the new socket-test harness: SP01 could close its echo peer
after proxy forwarding but before the peer read the plaintext; a TLS client
could also finish wrapping after teardown captured its client list. These are
harness ownership/scheduling defects, not new defects in the proxy helper.

SP01 now waits for the peer's existing receipt event before allowing teardown
to continue. One harness-local lock serializes the closed flag with ownership
of both raw and wrapped clients; a client arriving after close is immediately
closed and rejected. The lock is released before proxy teardown. All assertions,
timeouts, 53 collected cases, helper bytes and actual-runtime controls remain
unchanged. The complete 5,260-entry inventory regenerates byte-identically.

On local Linux x86_64 with two CPU cores, CPython 3.12.13, OpenSSL 3.0.20 and
the unchanged hash-locked baseline dependencies, the original harness failed
2 of 10 fresh-process full-suite runs. The repaired harness passed all 20 of
20 fresh-process full-suite runs (1,060 case executions). Controlled real-socket
schedules failed both original SP01 cases and the late-wrapper descriptor
assertion, then passed all three with the repair. The Linux environment runs
under local emulation; these counts do not estimate the hosted failure rate.

The full 53-case suite also passed on CPython 3.12.13 / OpenSSL 3.6.2 / macOS
arm64. The late disconnected-wrapper schedule was reproduced on Linux; macOS
did not satisfy that diagnostic's precondition. Earlier diagnostic refinements
and the rejected Linux ARM dependency setup remain recorded, not passing tests.

With the unchanged main helper substituted into an external diagnostic tree,
the exact repaired tests still expose both original TLS framing failures and
all three close-before-select failures. The diagnostic retains the underlying
worker exceptions, TLS record prefixes and cleared-TLS facts, then explicitly
reclaims old-helper leftovers. No negative-control worker or descriptor survives.
These controls remain separate from candidate pass results.

The previous 132-case database/physical result above is historical and was not
rerun for this harness-only correction; those modules and their helper inputs
remain byte-identical. Complete fresh hosted acceptance is still required.
Review FU-1's additional late-wake and surviving-worker mutation coverage remains
separate follow-up work. P-1 is addressed by explicit platform and repeat counts.
Scope stayed within test-owned wire transport and evidence fidelity.

The harness correction received zero-Blocker reviews at
`f00a6ea09cdd4dd046fe5155b4eda16c763ca616`. These remain historical evidence
after the documentation-only version-2 amendment; the new head requires its
own focused review before admission.

## Approved consumer evidence amendment, version 2

The task user approved version 2 on 17 October 2026 at 19:24:02 UTC, after
the complete live card at 19:06:03 UTC in coordinating chat
`01a14a01-ece2-7bd1-ba2e-efb4fd96c0f0`: card
`msg_08cb29efe0a907b2016ad3c7099c0881919ba57c38e2c80ca1`, then user message
`msg_01a14b52-397f-7c80-b817-a111da464e4c`. The original messages remain the
authority; this committed reference is navigation only. The amendment design
received zero-Blocker focused review before that card. Approval permits the
following consumer route but supplies no exact-root grant or merge authority.

### Recommendation, problem and capability

The approved amendment makes the named PR eligible for complete pre-merge
acceptance
through the separately approved [PR #417](https://github.com/samovers/OFARM2/pull/417)
version-4 transition, subject to a later, separate exact-root grant. Retain the
complete signing test-proxy lifecycle capability: preserve TLS state while the
reader runs, reclaim owned resources and keep genuine failures visible. The
consumer amendment changes its permitted evidence route only.

The original version-1 card and later approval were retrieved directly from
chat `01a0aab4-3ce9-7540-abf2-41bc78b859b3`: card
`msg_0a76f8c31f710916016ad126c93a5c87d2bc42a86034e5b9b5`
(15 October 2026), then user message
`msg_01a14383-adab-70f2-81ff-c0fa0c35fc33` (16 October 2026).
The original card explicitly left CI budgets and evidence requirements unchanged.
Its approval did not authorize this amendment. Version 2 was separately approved
after the complete card in the current chat; these references are navigation,
not transferred approval.

Main's 45-minute source did not finish #413's second baseline or publication.
Its one complete 5,260-case baseline and native successes remain incomplete,
historical evidence. Fixing the separate harness B1 does not solve that budget
or make the earlier source acceptable. Version 2 expressly permits the finite
60-minute conformance route owned by #417; it promises no runtime saving or pass.

### One boundary, authority and precise amendment

The primary boundary remains **test-owned wire transport and evidence fidelity**.
#413 implements the fixture and tests. #417 alone implements CI evidence policy
selection, bounded use, revocation and recognition; #411 alone changes permanent
execution capacity. No transition implementation or resource change joins #413.

The task user owns semantic approval, exact-root selection, final acceptance,
cancellation and later exact-head merge authorization. The fixture owns its
worker, sockets and fault injection. The AI implements and checks the approved
scope; reviewers assess demonstrated findings. The separately selected trusted
operator verifies original messages and translates the later grant into its
machine projection and durable external journal. CI and the isolated publisher
perform mechanical verification and evidence custody, not human approval. The
external verifier authenticates complete evidence against the independently
selected root. GitHub retains native merge. Existing runtime, credential,
database, signing, key, tenant, audit and deployment owners remain unchanged.

For #413 alone, after a separate exact-root grant is valid, replace these three
provenance requirements: default-main admission
and same-main policy selection; the default-main `workflow_run` publisher; and
ordinary receipt recognition. Their only permitted replacement is #417 v4's
created transition admission, externally selected reviewed root T, real push
source, separate push publisher at that same T, distinct transition receipt and
isolated external verification. Ordinary main policy and receipts stay unchanged.
No other PR acquires permission from this consumer decision.

### Risks, preserved invariants and limits

The fixture risk remains hiding a real failure: retain TLS-preserving wake-up,
registration and disposal ownership, stop/join bounds, genuine worker/body/
cleanup errors, framing and real certificate/password refusal assertions.
No test retry, filtering, assertion relaxation or test/runtime timeout change is
permitted; only the separately named conformance job ceiling may become 60 minutes.

The additional evidence risk is reliance on reviewed but unmerged T before
#417's own complete hosted acceptance. The approved amendment knowingly accepts that
temporary bootstrap reliance, bounded by local controls, exact-head review,
one-use authority, independent root selection and live verification. Shared
account identity and delegated journal custody remain provisional limitations;
an AI COMMENT review is not independent human approval.
T's private gh relay performs upstream TLS authentication and transiently handles
forwarded credentials; its pinned configuration, cleanup and isolation remain
required. Revocation detection can take up to 135 seconds plus provider
cancellation latency; fresh checks at each decisive stage remain mandatory.

Use #417's fixed v4 operation coverage. Protected Python policy/evidence reads,
trusted Node/Git after bootstrap, four curl executions and all five gh phases
retain first-403/429 and GraphQL-error refusal and complete protected accounting. Existing recovery,
fallback and valid content received under an error status may succeed only in
the enumerated provider setup/control/reporting, archive installer/pip bootstrap
and four canonical pip installs, Docker/Buildx/BuildKit image/ADD/fallback, and
pinned-scanner operations, with their original final checks intact. Provider
activity before observation is included in the disclosed exception. Bad or
incomplete content and failed final checks still fail. Candidate/unrelated
traffic remains untrusted ambient activity. The 990 REST / 430 GraphQL-point
envelope is protected-operation planning with margin, not a verified total for
all traffic, a quota reservation or a universal throttle guarantee. The immutable
coverage declaration must be selected with T and bound through receipt acceptance.

The later grant must freeze full T/tree/closure/coverage, reviewed #413 head H,
current base B and execution merge M/parents, reviews, operator, exact source and
publisher refs, unique grant ID, verifier, external journal/checkpoint locations,
format and immutable genesis hash (the recorded tail/checkpoint advances monotonically),
and concrete creation/expiry times. It allows at most one source and one publisher,
both attempt 1, expires within 24 hours and cannot exceed the campaign's fixed
sunset, 24 October 2026 00:00 UTC. Revocation, expiry, head/base/history drift,
uncertain state, missing authority or any test/validation failure refuses use.
No automatic renewal, workflow/test retry or reuse of earlier partial results.

The current #417 candidate `f13a526077a56bec99b333c9cfbd53452cde0e46`
and [its focused review](https://github.com/samovers/OFARM2/pull/417#pullrequestreview-5559256227)
are preparation references, not selected authority. This amendment supplies no
grant ID, activation permission, timestamped use slot or admission trigger.

### Verification, sequence and reapproval

Before use require a complete repaired #413, mandatory and focused local checks,
fresh exact-head zero-Blocker review, zero-Blocker amendment design review and its
later exact semantic approval, plus #417's current root checks/review and the
separate exact-root packet and user grant. Every new commit requires fresh review.

The transition must run both complete, unfiltered baselines sequentially on the
same runner and database clusters, the unchanged equivalence comparison, all 23
platform cases and both complete native architectures. Preserve the full current
inventory and substantive validators. Require the successful complete source,
guarded handoff, successful distinct isolated publisher, complete authenticated
artifacts and receipt, external verification, and current unrevoked authority.
Only then present #413's complete final packet and await the later exact-head
native merge authorization. A semantic approval or root grant cannot authorize
merge. No deployment, production access, secret provisioning, direct-main write,
protection change or bypass is allowed.

The selected order remains #413 acceptance and separately authorized native merge;
then rebase/review #417 as T1 and obtain #411's own amendment/grant; then #411's
complete acceptance and separately authorized merge; then retire the transition
and run #417's own full acceptance through normal main60 before its own merge.
This card grants no #411 or #417 consumer authority.

This amendment changes only #413's consumer design record and navigation;
the substantive fixture repair is unchanged. The simpler
route of merging with only partial evidence is rejected because complete
authenticated acceptance before merge remains an invariant. No duplicate policy
implementation, new generic framework or extra validator is introduced.

Development remains provisional under the existing healthy-local-host and finite
operation assumptions. Interpreter/TLS ownership changes or unbounded cleanup
require reassessment. Before deployment the approval arrangement must be replaced
by independently human-controlled and verifiable approval. Changed capability,
boundary, authority, effects, invariants, irreversible behavior, named PR or
deployment posture requires a new version. Changed exact execution coordinates
require fresh checks/review/evidence and a new exact-root grant; they never silently
inherit an earlier grant or extend the fixed sunset.

Next: obtain focused review of this documentation commit, then present the
separate exact-root activation packet. Hosted acceptance remains pending.
