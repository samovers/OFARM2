# Governed-read protection: Phase A assessment and open blockers

Version 0.11, 2026-09-17. Delivery [#392](https://github.com/samovers/OFARM2/issues/392).
**Draft for design review. The assessment is complete; the implementation design
is blocked. No protection mechanism is selected or ready for approval.**

This document consolidates the current source investigation and rejected
alternatives into the existing Delivery's review surface. This draft PR is the
Phase A workspace for #392, not a separately mergeable contract or approval
prerequisite. It does not close the issue. No runtime, role, schema, canonical
candidate, production route or dependency changes accompany it.

## 1. Problem, scope and governing inputs

A permitted limited historical read must preserve complete source observation
and protection until its first irreversible disclosure. A hidden competing writer
must not invalidate that protection or defeat the retained post-commit progress
guarantee. The current transaction foundation supplies tenant binding and write
serialization, but not this complete read capability.

Primary boundary: **governed-read database observation, evidence membership and
protection lifetime**, including participating source advancement. Runtime
placement, source withdrawal, identity/key authority and output handoff are
dependencies with existing owners; describing them here does not change them.

| Input | Exact basis and authority limit |
|---|---|
| Implementation | OFARM2 `1b4d52e2d6387d486110465973ad822089bd9583`, tree `14d4d61d9410251aafdf8f6e559be3fdd24d23ef`. Live main matched this pin on 2026-09-16. |
| Read semantics | [OFARM PR #37 candidate at 33abbe3](https://github.com/samovers/OFARM/blob/33abbe3c413a33ae38ba5ce189850c1d8556c4bd/package_meta/history/clean_baseline_migration/phase_reports/governed_read_transaction_coverage_and_disclosure_protocol_rfc_candidate_v0_1.md), especially sections 8.3–8.3.1 and RD-C20/C21. Approved candidate semantics, not an admitted PostgreSQL provider. |
| Source withdrawal | [OFARM PR #26 candidate at 38af747](https://github.com/samovers/OFARM/blob/38af7475d8cbd41b158e50ba77b60f140cbef4ba/package_meta/history/clean_baseline_migration/phase_reports/not_required_transaction_and_consumption_protocol_rfc_candidate_v0_1.md), section 11.5. The task user approved this exact head in the publication task; implementation is not approved by that message. |
| Existing design correction | [#392 comment 5694678785](https://github.com/samovers/OFARM2/issues/392#issuecomment-5694678785). Its database resource finding is reused, not presented as a new runtime reproduction. |
| Remaining owner decisions | [Restricted placement proposal](https://github.com/samovers/OFARM2/issues/392#issuecomment-5695599206), [preparation correction and hardware hold](https://github.com/samovers/OFARM2/issues/392#issuecomment-5697404147), and [source-withdrawal review](https://github.com/samovers/OFARM2/issues/392#issuecomment-5698376629). Historical proposals remain subject to their recorded corrections. |

Use the existing protocol terms: A is durable read admission; S is the final
complete observation; P is frozen preparation; I is actual entry into the one
evidence-finalization operation; C is actual atomic evidence commit; L is the
first irreversible disclosure handoff; O records later truthful observations.
D is the unchanged full deadline. C is distinct from its acknowledgement.

Protection precedes final S and survives C through L or proved irrevocable
termination. For the RD-C20 positive pair, hold independent authority, retention,
session, deadline and fault conditions fixed. Offer a hidden candidate after
actual C, including before acknowledgement. Both permitted limited replies must
reach L, and the same deferred writer must actually commit afterward under valid
authority. Dropping the writer or suppressing the read is not that result.

## 2. Authority, trust and non-effects

| Owner | Retained responsibility |
|---|---|
| #392 database binding | Complete observation/membership, source participation, actual protection, evidence-finalization and storage-side completion facts. |
| #178 / PR #26 source owner | Real attempt identity, lawful withdrawal, outstanding operations, truthful outcome, complete evidence and retry eligibility. A read gains no rollback power. |
| Existing tenant, principal and signing owners | Challenge and current authority verification; key custody and admission/revocation decisions. |
| Runtime/deployment owner | Execution placement, connection ownership, ingress enforcement and actual resource isolation. |
| #177 and existing output owner | Original live read ownership, current handoff guards, immutable bytes and actual L. |
| Existing policy/projection/retention owners | Reader eligibility, public fields, admitted persistence and custody. Missing bindings are not supplied by SQL capability. |

Protected assets are tenant authority, source and evidence integrity, truthful
outcomes, complete read coverage, and the retained disclosure/progress contract.
Trusted components may stall or complete in adverse order. Caller flags, stale
results, connection IDs, phase labels and queued requests are not authority.
Arbitrary compromise of trusted native process memory is outside this assessment;
no new isolation claim against such compromise is made.

The primary risk is claiming an established stop/protection from an earlier check
while source work can still advance or interfere. Containment is to leave the
mechanism unselected until actual ordering, participation and resource paths are
shown. No temporary reader, deadline relaxation, authority bypass, new public
failure code, hidden-selected fallback or permanent-refusal substitute is proposed.
Conditional PR #26 semantics remain approved; withdrawal is not enabled without
its reader, actual-attempt, history, public-projection and retention bindings.

## 3. Current source path and concrete limits

The [tenant manager](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/tenant_uow.py#L422)
executes:

```text
pool checkout -> BEGIN READ COMMITTED -> challenge -> observation
 -> synchronous issuer -> bind_tenant_capability -> bound-context read
 -> yield UnitOfWork -> caller work -> commit or rollback -> pool return
```

The [issuer](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/tenant_capability_issuer.py#L111)
includes a [separate current-authority database lookup](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/signing_authority.py#L180)
and signing evidence verification before external signing. Whole issuer execution is not
database-free or proof of a KMS-only stage. The [existing cancellation test](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/tests/test_tenant_uow.py#L356) raises
inside the post-binding caller body; it does not verify interruption of a stalled
issuer. These are source observations; no tests were rerun for this claim.

| Mechanism at the pinned source | Actual guarantee | Limit for #392 |
|---|---|---|
| [UNLOGGED CHALLENGE/BOUND context](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/migrations/0001_initial.sql#L1026) and [challenge creation](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/migrations/0001_initial.sql#L5801) | Backend-incarnation/transaction binding. CHALLENGE is inserted inside the source transaction before issuer invocation. | Another ordinary connection cannot see that new uncommitted row as a stop record. It is neither durable withdrawal history nor a canonical attempt identity. |
| [Binder admission lock](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/migrations/0001_initial.sql#L6007) | Fixed shared transaction lock before current key/principal reconstruction; designated authority transitions acquire the exclusive pair. | Key/principal authority protection, not per-attempt read cancellation. [Ownership is separately specified](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/deployment/postgresql/provisioning_specs.py#L1698). |
| [Global CLOSE_ADMISSION](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/migrations/0001_initial.sql#L4599) | Key-control login and closed key-management reasons record a global key-lifecycle act. | This routine does not itself acquire the exclusive advisory pair. It is not a reader-owned stop API. |
| [Tenant write lock](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/migrations/0001_initial.sql#L6382) and [knowledge allocator](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/migrations/0008_tenant_command_runtime_bundle_selection.sql#L179) | Tenant derives from BOUND context; batch allocation serializes through transaction end. | Acquired after binding. A gate after allocation can inherit already-held write resources. |

The source retains a backend, pool lease, XID and uncommitted context work while
the issuer is pending. During its current-authority lookup, the issuer also opens
a separate unpooled connection through the [runtime factory](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/application_runtime.py#L134).
That connection's context exits before signing-evidence verification and KMS
signing; an issuer stalled specifically at KMS does not normally retain it.
Pending connection establishment and lookup are separate capacity/progress cases.
This does not prove either harmlessness or deadline failure.
The challenge cut is not automatically PR #26's canonical eligible source stage.

The [pool](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/tenant_uow.py#L28)
has maximum size 8 per manager, checkout timeout 5 seconds and maximum 32 waiters.
If eight parked writers retain all its connections, a future read sharing that
pool cannot obtain another checkout until capacity is released. Separate pools
do not alone reserve shared role/database slots: the provisioning specification
sets [ofarm_app's limit to 24](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/deployment/postgresql/provisioning_specs.py#L1984)
and the [tenant database's limit to 48](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/deployment/postgresql/provisioning_specs.py#L1937).
The production composition uses the same configured DSN for pool and unpooled
lookups. Actual deployed connection identity and the future read's placement are
not attested here. Physical A/S-C/O stages do not themselves require a fresh
checkout per stage; the eventual ownership plan must name retained and reacquired
resources. Pool exhaustion remains outside Scope B's permitted waits.
Returning a checkout lease normally leaves its backend open for pool reuse;
it does not necessarily free role/database capacity for an unpooled lookup.
Account for already-open pool backends, pending connection establishment, lookup
execution and transaction exit separately.

## 4. Evaluated approaches and why they remain insufficient

### Application dispatch permit

Separating issuer execution from the source connection owner could remove one
signer-completion dependency. It requires the issuer to receive only existing
immutable inputs, with no source connection or advancing callback. The current
`mint` arguments already have this shape; the issuer retains its separate
authority-reader dependency and database I/O. Moving its execution does not make
it a pure computation or remove that dependency. Actual concurrency and lifetime
compatibility still need proof. Parking after checkout also retains the source
pool lease until lawful cleanup and return. This ownership separation does not
by itself settle `claim permit -> pause -> read closes gate -> resume send`.
A final flag check leaves a check-to-send interval; waiting for the permit holder
retains its scheduling dependency. This symbolic case assumes no independently
established covered storage cause. No replacement runtime interface is selected
in this database PR.

### Concurrent connection close

The exact [review lock](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/requirements-review-baseline.lock)
pins Psycopg/binary 3.3.4 and pool 3.3.1 for CPython 3.12 Linux x86_64.
The inspected binary wheel SHA-256 is
`e7510c37550f91a187e3660a8cc50d4b760f8c3b8b2f89ebc5698cd2c7f2c85d`.
Static ZIP/generated-C/ELF inspection found that ordinary close takes no
`Connection.lock`; wrapper finish frees and clears its handle. On this build,
the generated critical-section macros add no mutex. Parameterized send releases
the GIL and copies the handle before calling libpq.

Reviewers can reproduce the narrow static observation from that hash-pinned
wheel: `psycopg_binary/pq.c` lines 1581–1600, 4933–5008 and 9739–9818;
`pq.cpython-312-x86_64-linux-gnu.so` offsets `0x1796d–0x1797b` and
`0x38ab8–0x38afd`. The bundled client's static version constant is libpq 18.0;
the configured PostgreSQL server remains 17.10. No live library selection was
attested and no downloaded code was loaded or executed.

Therefore raw concurrent close/finish is not selected as an irreversible stop
against a racing send. This is consistent with [libpq's same-connection threading
restriction](https://www.postgresql.org/docs/18/libpq-threading.html). It is not a
reproduced crash or driver-defect claim. Exclusive idle close remains ordinary
cleanup; local close proves neither prior command outcome nor backend rollback.
No driver fork, upgrade or unsafe concurrent-call experiment is proposed.

### Earlier SQL admission

A plain stop-row check admits `writer checks open -> reader closes -> writer
commits`. A later check still needs serialization through commit; a deferred
trigger alone provides no such order, and [SET CONSTRAINTS](https://www.postgresql.org/docs/17/sql-set-constraints.html)
can force deferred checks earlier. A complete conflicting gate could order source
commit against final S, provided all paths participate and read protection survives
C through L. That conditional safety property is different from resource isolation.

The [recorded #392 correction](https://github.com/samovers/OFARM2/issues/392#issuecomment-5694678785)
identifies this source-backed interference path:

```text
reader: actual C -> PostgreSQL lock cleanup -> acknowledgement -> L
                         ^
new writer: binder/gate acquisition touches shared resources -> waits/refuses
```

The binder admission tag identifies a common lock-manager partition. Compatible
high-level locks do not eliminate internal exclusive partition activity during
acquisition/cleanup. An idle client holding the compatible advisory lock does
not continuously hold that internal partition lock. This path identifies a
dependency, not its measured duration or the sole or dominant source of delay.
CPU scheduling, other database activity, memory and I/O may add other paths.

The later [executed review](https://github.com/samovers/OFARM2/pull/396#pullrequestreview-5226679109)
reports commit round-trip perturbation under both binder-tag and unrelated/CPU-only
loads. Its PostgreSQL 16 measurements are useful diagnostics, but the workers
already run before COMMIT is sent; actual C, post-C offer, L and the same writer's
later commit are not observed. The asynchronous-commit variant also changes
durability/acknowledgement behavior. These measurements neither isolate the
partition contribution nor bound execution noise, refute that dependency, or
prove that every provider must fail RD-C20.

An earlier SQL gate remains unselected as a complete solution: refusing a late
command establishes neither no server work nor causal independence of required
read progress. The partition path alone does not rank SQL gates against other
placements or establish the necessity of physical separation. A new candidate
must supply its actual resource argument; another lock name alone is no progress.

## 5. Retained cases, falsifiable evidence and blocker disposition

| Existing case / invariant | Required evidence | Current status |
|---|---|---|
| Withdrawal/controller scheduling | Real source attempt and lawful stop order; no escaped continuation or unlisted control wait. | Open. A database disposition could order effects but does not automatically stop the client or settle its obligations. |
| Database preparation already running | Exact command, resource, reached stage, outcome and causal interval; no simultaneous rollback or guessed cancellation. | Open. A genuine required protection-release wait may qualify under Scope B; BEGIN or a stalled task alone does not establish it. |
| Parked writers and connection capacity; RD-C21 | Hold all eight source-pool leases; require the selected read's needed checkout/lookup to remain usable under its actual placement. Separately exhaust shared role/database capacity with pending unpooled lookups. Cover capacity retained or reacquired at each stage. | Open conditional negative case. A future reader sharing exhausted capacity fails; no live governed-reader reproduction or selected separate pool/role is claimed. |
| Cleanup complete, report delayed | Distinguish storage release/acknowledgement, owner observation and onward delivery; protection must not depend on an unrelated delayed report. | Open. A completed cause cannot justify later callback delay; outcome uncertainty remains separately owned. |
| New source or late completion after actual C; RD-C20 | Both admitted limited reads reach L under matched independent conditions; independently observe C, then offer the candidate, observe acknowledgement/L and the same writer's actual later valid commit. Use the causal-evidence distinction below. | B1 remains open. Commit exclusion does not supply resource isolation; latency distributions alone do not decide this pair. |
| Full membership and continuous protection; RD-C21 | Include every relevant admission/import/migration/commit path, malformed/unresolved-root candidates through their enclosing partition, qualifications of qualifiers, writers outside today's executable writer set and pre-acquisition commits notified after C. Exercise omitted partitions/paths, forged/released protection, optimistic conflict abort and hidden-dependent waits; reject notification blindness or empty-history fallback. | Required. Protection cannot be filtered by successful admission, valid form, qualifier depth, current writer set, known IDs or predicted public label. No inventory-completeness or provider-admission claim is made here. |
| Actual finalization entry and original-owner lifetime | Original live owner and full D ordered against I without a check-to-start gap; no new initiation after actual owner loss. | Existing finalization-entry obligation remains open; this assessment does not clear it. |

Scope B permits only its closed, precisely established causal storage waits
through unchanged D. It does not turn arbitrary control/pool/callback delay into
storage finalization, nor excuse a newly offered writer's interference after
actual C. Genuine independent loss of C acknowledgement still suppresses L.

Separate two kinds of evidence. For retained resources, park the writer while it
holds a pool slot, conflicting lock or relevant queue position, and identify the
read's exact dependency and release. For shared execution interference, observe
actual C independently of the client COMMIT round trip and explain how the
candidate's effect is distinguished from independent environmental variation.
Control experiments and distributions help diagnose paths; they are not an
automatic conformance verdict. Mark deliberately instrumented delays as imposed
schedules rather than naturally measured latencies. If the observation/control
method cannot attribute a failure, report it as inconclusive, not a pass or proof
of universal impossibility. A finite observed maximum is not a bound on noise.
Neither compatible-lock parking nor a short benchmark proves its exclusion.

The approved requirement is the retained outcome under the stated causal pair,
not identical successful wall-clock durations. No statistical pass threshold,
deadline guard band or exemption for candidate-induced delay is introduced here.
Required future runtime evidence uses fictional fixtures and isolated disposable
databases through real participating entry paths, not a model that assumes the
missing ordering or physical isolation.

Production governed routes remain closed at the inspected head. These schedules
describe required future production-composition negative/positive cases; they
are not claims of a live governed-reader vulnerability or executed conformance.

### 5.1 Proposed evidence method for the existing read-owner question

Use two distinct judgments: whether an executed case meets its stated outcome,
and whether the selected provider supplies the complete guarantee. Passing cases
support the latter judgment but cannot replace its source-participation, resource
and lifetime argument. This is a proposed verification method under the existing
rules, not a new admission rule or an answer that certifies an unselected provider.

The [corrected-head review's imposed schedule](https://github.com/samovers/OFARM2/pull/396#pullrequestreview-5227162401)
provides a starting point. On PostgreSQL 16.13 the reviewer paused the reader at
`LockReleaseAll` entry, observed committed transaction status from another session,
then committed a compatible-lock writer before releasing the reader. It separates
database commit from client acknowledgement. It does not supply the complete
read-evidence set C, L, the protected progress pair or a candidate-held partition
wait. Its pause is imposed, not a measured candidate-induced latency. We read
the supplied probe/output; we did not reproduce that experiment.

For a future selected provider, keep a small execution record in its existing
test evidence, not a new runtime ledger or public response field:

- Pin the implementation, database/driver versions, effective durability and
  connection settings, roles, resource placement, fixture and instrumented source
  points. Use fictional records in a fresh disposable database with unique run,
  transaction and attempt identities; never reuse debugger signal files.
- Bind the original live attempt, final protected S, exact buffered/public bytes,
  complete C set and its transaction. Establish commitment
  under the selected storage/durability contract independently of the original
  client's acknowledgement. Status, a commit timestamp or one visible row alone
  does not prove complete durable C. A raw fixture remains mechanism evidence.
- Record the order of commit observation, candidate offer, acknowledgement,
  actual L and that same candidate's later valid commit. Distinguish actual
  events from when they are observed: observing C before offering the candidate
  establishes that ordering, not C's exact wall-clock instant. Include clock
  provenance/uncertainty for deadline claims; ambiguous ordering is inconclusive.
- Fix the original full D, authority/session/retention, policy branch and
  independent fault schedule before each pair. Vary only the hidden candidate.
  Keep observers and instrumentation equivalent and account for their resource
  effects. Do not reset D after a pause, pick a passing margin from results or
  turn measurement uncertainty into a permitted timing tolerance.

The causal sequence for the before-acknowledgement variant is:

```text
complete durable C -> independent observation -> candidate offer
 -> original owner's acknowledgement -> actual L -> same candidate's valid commit
```

Instrumented schedules must also check that the expected interception actually
occurred, match the full backend/transaction/lock identity being observed, and
release/detach/clean up on failure. Release the imposed reader pause independently
of candidate completion; otherwise the harness can manufacture the dependency.
A pause that itself consumes D cannot establish candidate-induced failure.
Test observers supply evidence, not the
original owner's acknowledgement, continued lifetime or disclosure authority.

Every adversary enumerated in the pinned RD-C20/RD-C21 is a required named case;
these tables do not narrow that enumeration. Candidate admission/classification
may remain unresolved; that does not waive source-writer authority or read guards.

| Case using the existing requirements | Decisive observation |
|---|---|
| Observation-method calibration | A database transaction is committed while its client has no acknowledgement; candidate introduction is ordered afterward. This validates the ordering technique only. Revalidate any instrumented location on the pinned runtime before using it. |
| Defective-mechanism control | Permit an actual intervening candidate commit before L, or demonstrate its concrete resource dependency causing required acknowledgement/L to miss D while the matched no-candidate execution succeeds. The method must report failure; sanitized suppression is not a pass. An imposed pause without that causal dependency establishes only a test schedule. |
| RD-C20 positive pair | Through real participating paths, both permitted limited replies reach actual L exactly once before unchanged D; all handoff guards hold and the same deferred candidate actually commits later under valid authority. Exercise offers after C before acknowledgement and after acknowledgement before L, including unresolved candidate admission/classification and malformed-root candidates protected through their enclosing partition. A dropped or permanently blocked writer fails this case. |
| Independent acknowledgement loss | Apply the same independent loss in both runs. Neither may disclose without acknowledged complete C; reconciliation does not revive either attempt. This is a fault case, not a substitute for the positive pair. |
| Public-policy comparator | Compare the exact permitted public content and omissions in each pair. A policy-excluded pair stays identically excluded without inventing C/L for a successful read. Disclosable-history refresh/suppression retains its separate existing case. |
| RD-C21 coverage, capacity and allowed wait | Use the existing section 5 cases. Record the exact resource holder and release dependency, pool lease versus backend capacity, and every participating source path. Only the existing enumerated storage wait evidenced through full D qualifies for Scope B; arbitrary exhaustion or missing coverage does not. |
| Actual owner loss versus I | Observe original-owner termination and actual finalization entry through their owning mechanisms. Loss or reaching D before I prevents entry; eligible I before loss/expiry may settle only under its independent persistence authority and never restores L. Delaying a notification is not evidence that actual owner loss has been ordered. Keep this separate from the C/acknowledgement calibration. |

For each named case, report the observed outcome and scope: **pass** requires all
its positive obligations; **failure** requires the violated obligation and
supported causal trace; **inconclusive** means identity, order, completeness,
deadline or attribution could not be established. Independently observed wrong
commit order is a failure even if a timing explanation is uncertain. Finite load
samples can expose a failure but cannot establish a noise bound or guarantee.
Instrumented success must not be presented as an uninstrumented production result.

Before further placement work, the candidate must map every relevant writer
entry, already-running preparation, pending authority lookup and late completion
to the read's required resources through acknowledgement and L. For each shared
dependency, show how candidate activity preserves the existing outcome rule;
merely preventing its commit is insufficient. Missing control/evidence leaves
the candidate unproved, not proof that every architecture is impossible. This
source-backed argument and focused runtime cases are complementary. No pool,
isolation device, new service or source-withdrawal mechanism is selected here.

## 6. Restricted-provider assessment and next work

Applying section 5.1 to the existing restricted arrangement yields **not ready
to select**. This is a bounded assessment of the published candidate and its
corrections, not a new general method or a finding that every provider fails.
The governing outcome rules remain unchanged; method review supplies no provider
admission, deadline tolerance or renewed semantic approval.

The candidate in the [placement proposal](https://github.com/samovers/OFARM2/issues/392#issuecomment-5695599206)
has concrete content: establish the original read owner in one native PostgreSQL
invocation before A; synchronously execute its evidence finalization there;
and hold new source offers on a separate ingress machine before any request-driven
database/host work. A pull-only dispatcher would remain quiet through L.
The [preparation correction](https://github.com/samovers/OFARM2/issues/392#issuecomment-5697404147)
withdraws waiting for every entered invocation and parks the hardware bridge.

**Conditional benefit.** Same-invocation ownership removes the old sequence
`application owner dies -> surviving backend starts I` if the backend invocation
really was the original owner from before A and no alternate finalizer exists.
It is not merely a liveness flag. PostgreSQL provides
[nonatomic SPI transaction control](https://www.postgresql.org/docs/17/spi-spi-connect.html),
but [SPI commit also starts another transaction](https://www.postgresql.org/docs/17/spi-spi-commit.html);
post-C cleanup/startup remains inside the protected resource argument.
The exact sealed-set entry witness, full-D enforcement and irreversible
invocation cleanup remain unimplemented. Error unwinding while the backend
survives must make a later SQL COMMIT unable to finalize the old invocation.
Eligible I before later owner loss may still settle truthfully; no L follows.
I need not equal WAL insertion, and no new counterexample to this prospective
owner placement is claimed here.

This cannot run inside the existing [`TenantUnitOfWorkManager._run`](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/tenant_uow.py#L475),
which opens `BEGIN` before binding. The candidate needs an eligible
[top-level nonatomic entry](https://www.postgresql.org/docs/17/sql-call.html).
Under [ADR 0003](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/docs/adr/0003-tenant-capability-trust-and-binder.md#L1102),
tenant binding belongs to one backend incarnation and full `xid8`; the
[binder/context lookup](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/migrations/0001_initial.sql#L6370)
cannot carry it across A's commit. Each later tenant-bound transaction in that
invocation, including the final protected transaction, needs its own challenge,
externally signed capability and bind while the original invocation remains alive.

**Native-entry/minting feasibility.** The existing value contract is compatible
with fresh per-transaction minting; an end-to-end binding is still absent.
[`ApplicationRuntime.mint_capability`](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/application_runtime.py#L91)
already delegates immutable identity, authority and challenge values to the
existing issuer, which takes no tenant connection as an argument but opens its
own database connection for signing-authority lookup. This is an internal Python
method, not a native callback or exposed endpoint. Reuse does not inherently
require a capability-format, binder-lifetime or signing-custody amendment.

The current client sequence cannot deliver the round trip inside an unfinished
native invocation. [Ordinary libpq commands](https://www.postgresql.org/docs/17/libpq-async.html)
await prior completion; [pipeline mode](https://www.postgresql.org/docs/17/libpq-pipeline-mode.html)
orders commands rather than executing a reply command inside the running CALL.
A second connection cannot bind the original backend/xid, and returning then
calling again ends the proposed original invocation. A private request/reply
exchange with the existing runtime minter is a concrete candidate, not a facility
the repository currently supplies. Section 6.1 proposes a receiver for review;
neither it nor the complete provider is admitted for implementation.

The database side of that exchange also needs an owner. The [review's PostgreSQL
16.13 probe](https://github.com/samovers/OFARM2/pull/396#pullrequestreview-5233289051)
demonstrates a NOTICE request reaching the client during CALL and a reply row
committed by another session being read in the still-running transaction. It uses
a fake capability and superuser access, not the real binder or production grants.
[NOTIFY waits for commit](https://www.postgresql.org/docs/17/sql-notify.html), and
[SPI rejects client COPY](https://www.postgresql.org/docs/17/spi-spi-execute.html).
These observations are not an exhaustive proof of every possible channel or
selection of NOTICE/table transport.

A reply-table route would require database-owned schema, grants and catalog
attestation, plus approved custody/retention for the capability and its retained
copies. Its additional write transaction, polling and cleanup join section 5.1's
resource argument, including the pre-protection and quiet-execution boundaries.
A native I/O route instead requires database-owned receiver code, privileges,
build/provisioning and catalog evidence. The proposed native entry already needs
database review; runtime ownership does not absorb that receiver. Neither route
may widen the existing [verification-only crypto extension](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/docs/adr/0003-tenant-capability-trust-and-binder.md#L377)
or inherit its installer authority. Its specific crypto requirements do not
select the packaging or acceptance criteria for a future native receiver.

The smallest candidate ordering to assess is:

```text
trusted request/principal association -> original native invocation before A
  -> transaction A: create/observe challenge -> external mint -> bind/context check
  -> persist and acknowledge A through synchronous SPI_commit
  -> new transaction: fresh challenge -> external mint -> bind/context check
  -> establish required protection before final S -> S/P -> eligible I
  -> complete C -> acknowledgement -> guarded L, without another mint or bind
```

This places rebinding before protection acquisition; the quiet-execution boundary
and all outstanding work still need an exact mapping. It does not establish S,
I, protection or L merely by naming them, and does not require direct
backend-to-KMS access. The exchange must associate the database-created challenge
with the already authenticated request and return the unchanged capability only
to that live invocation/transaction. Caller-supplied identity fields, an endpoint
or a serialized object labelled verified cannot establish that association.
The binder and returned-context check remain authoritative for tenant binding.
Minting refreshes signing authority, not OIDC/session validity or principal
resolution; stale principal authority must still fail at the binder. A capability
expiry never extends the original read's full D or grants disclosure authority.

Before the adapter can be selected, its focused cases must cover two successful
bindings across A's commit, mismatched request/challenge replies, authority change
between mint and bind, and a reply after rollback, timeout or invocation loss.
Late replies cannot resume an ended invocation or bind a successor. Required
[refusal auditing](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/request_router_audit.py#L59)
and transaction cleanup must survive the new entry; calling the issuer alone
does not preserve the existing audited UnitOfWork path. No credential or JWS
belongs in diagnostic output. Dropping a reply proves no cessation of authority
lookup, signing or transport activity; their full lifecycle still joins section
5.1's resource argument. These are unexecuted adapter cases, not provider evidence.

Map effective timeouts separately. The [provisioned role defaults](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/deployment/postgresql/provisioning_specs.py#L1286)
give app/worker statement limits of 30/60 seconds and transaction limits of
60/120 seconds; defaults do not attest the eventual entry's settings.
[Statement timeout](https://www.postgresql.org/docs/17/runtime-config-client.html#GUC-STATEMENT-TIMEOUT)
covers the whole CALL, while [PostgreSQL 17.10 transaction timeout](https://github.com/postgres/postgres/blob/REL_17_10/src/backend/access/transam/xact.c)
is armed for each physical transaction and disabled during commit; idle timeout
concerns waiting for another client command. None substitutes for the full D.
The native exchange must handle interruption and irreversible invocation cleanup;
a configured timeout or cancellation request alone does not prove actual owner
termination. No timer is extended, disabled or reclassified here. Before-I loss
prevents I; eligible I before loss retains only lawful settlement, never L.

**First source case: no demonstrated closure.** The current path supplies this
schedule. The following is source/contract analysis, not an executed timing test:

```text
W: pool checkout -> BEGIN -> challenge -> synchronous mint
   -> separate current-authority connection/query (still outstanding)
R: original A and D -> request quiet source execution
W: lookup exits -> receipt verification -> signing -> capability-bind SQL
```

The [authority SQL](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/migrations/0002_authentication_read_api.sql#L260)
reads the binder instance, keyring, complete lifecycle stream and verification
key, checking their digests. It contains no explicit advisory/row lock, write or
source-stop operation. It is not the later binder admission-lock acquisition;
ordinary database reads and their transaction/connection cleanup still use shared
resources. Mere sharing proves neither a missed deadline nor harmlessness.

| Outstanding part | Actual ownership and remaining work |
|---|---|
| Source transaction | The source stack retains its pool lease, backend, full XID and uncommitted challenge. It is inside synchronous mint; the current code has no stop/dispatch arbitration. After mint returns successfully it sends bind SQL; its error cleanup runs only after control returns. |
| Authority lookup | `SigningAuthorityReader.current` owns a separate unpooled connection using the same configured DSN. Its two fetches and connection-context exit precede receipt verification. Rolling back the source transaction does not finish this query or release this backend. |
| Later issuer work | Receipt loading/verification, capability construction and external signing remain possible after lookup exit. The issuer already takes immutable values and no source connection; that does not fence the source stack's later bind. KMS-only pending is a narrower state after the authority context has exited. |
| Cleanup and reuse | Source rollback, authoritative attempt evidence, authority-connection completion and pool return are different facts. Pool return can retain the backend and invokes reset work; it is not database-capacity release. Late callbacks, reports and reclamation still need disposition through C acknowledgement and L. |

A proved source rollback removes the old challenge. The existing binder requires
the matching backend incarnation, current full XID and CHALLENGE row, so an old
capability does not thereby gain a valid new binding. The unresolved continuation
can still dispatch SQL and consume resources even when binding is refused.

There is no current stop point to select from these facts. The existing
source-owned withdrawal proposal remains conditional: PR #26 section 11.5
requires independently bound reader eligibility, operation-wide withdrawal
history, exact attempt/stage and exclusive persistence ownership before the
irreversible stop, plus the required public-projection and retention bindings.
Those bindings remain absent; A is not permission. Command-idleness of the source
connection does not account for the separate query. Nor does that separate query
automatically forbid rollback of a different idle transaction: its ownership,
status and continued effects must be accounted for without concurrent commands
or pretending cancellation succeeded.

| Proposed disposition of this schedule | Why it does not yet close the case |
|---|---|
| Hold new offers and wait for all existing mint work | This leaves W running and may wait on connection setup, application scheduling, receipt verification or signing. Scope B permits no generic drain. Identify an actual enumerated storage dependency and causal wait through full D; SQL execution alone does not qualify. |
| Fence forward dispatch and roll back only W's source transaction | This is the [existing narrow source proposal](https://github.com/samovers/OFARM2/issues/392#issuecomment-5697735355), not an implemented hook or newly granted authority. Even with its prerequisites proved, the separate lookup and later work remain; source outcome evidence and resource disposition are still required. |
| Cancel/close the authority operation as well | A cancellation delivery primitive is not an owned complete mechanism. The exact operation, control availability, terminal outcome, cleanup and surviving work need proof. No reader cancellation authority or latency bound follows, and raw concurrent connection manipulation is not selected. |
| Proceed while the lookup or late result remains active | Discarding a result can prevent its use only at an effective dispatch fence; it proves no cessation or isolation. No mapping yet shows that the surviving work preserves the required acknowledgement/L outcome under unchanged D. |

Natural completion before protected final S remains a legitimate ordering when
the complete observation includes any resulting commit. It is not permission to
wait for arbitrary preparation through D. After actual C, newly offered hidden
work must not defeat acknowledgement or L; the positive pair also requires the
same deferred writer's later valid commit. Neither suppression nor dropping W
closes that obligation. The present evidence leaves this candidate **unproved**;
it establishes neither a complete mechanism nor impossibility of other placements.

**Scope and cost.** The [existing boundary allocation](https://github.com/samovers/OFARM2/issues/392#issuecomment-5695962121)
is substantial; locating components together does not combine their authorities.

| Owner | Concrete work this candidate still requires |
|---|---|
| #392 database binding, with the database/provisioning owners under ADR 0001/#174 | Native invocation/entry/cleanup and database-side reply consumption; any reply schema/grants/catalog changes or native receiver I/O/build/privilege surface need their own owner-scoped review. Complete S/C membership, actual acknowledgement and protection surviving C remain #392's capability. |
| Tenant binder and signer owners under ADR 0003 (#174/#172), with #173 transaction ownership | A fresh challenge, external mint and bind for each tenant-bound transaction inside the native invocation; an eligible entry outside the current `BEGIN` wrapper. Changes to binding lifetime or signer placement belong to these owners, not #392. These closed issues identify existing ownership, not authorization to reopen or implement changes. |
| #178 source owner | Real attempt/eligibility bindings, stop versus actual dispatch, separate operation outcomes and complete withdrawal/settlement evidence. PR #26's conditional approval supplies no implementation of these. |
| Runtime/deployment owner under #167 | Runtime half of the private exchange, trusted request association and existing minter invocation, refusal/cleanup integration, earliest-entry and late-completion isolation, capacity and queue ownership, restricted connectivity and reduced concurrency; it does not own the database receiver. No suitable implementation Delivery is assigned by this assessment. |
| Capability custody/retention owners, with #172/#174 under ADR 0003 | If the reply is stored, decide permitted storage, access, retained copies and cleanup before choosing that route. Single-use binding does not authorize capability persistence. |
| #177 output owner | A concrete irreversible acceptance primitive with current guards and strict D. The proposed response-port contract has not implemented it; preflight followed by an unguarded transfer is insufficient. |

Independent identity, signing and custody authority stays with its owners;
native placement still needs their per-transaction binding and minting support.
Queuing before acquisition avoids new leases; it does not free old backends.
Source cleanup may preserve the original request under PR #26's complete rules,
but no universal lease-free-successor topology or working stop follows from that
permission. Shared post-C compute, storage or output activity cannot be excluded
by calling the machines separate; the actual paths require the reviewed proof.

**Assessment decision: freeze adapter expansion.** Native original-owner
placement remains conditional and unproved. Sections 6.1–6.2 retain useful
feasibility work and association safeguards, but do not answer the source case
above. Fresh transaction binding is required under that placement; socket/NOTICE
transport, direct local SQL, a dedicated connection and the two runtime paths are
candidate choices, not universal #392 requirements. Do not build out their audit,
cancellation or isolation machinery before demonstrating source/progress viability.

The next substantive design work stays with the existing source-owner discussion:
bind the actual eligible attempt and exclusive stop versus dispatch; account for
the separate lookup and every surviving continuation through acknowledgement/L;
identify only real covered storage waits. Apply section 5's existing four cases,
including delayed control/reporting and late completion. If this placement cannot
supply that argument under unchanged D, reconsider it rather than add another
flag, registry, controller or prerequisite. Do not infer global impossibility.
Original-owner entry, complete S/C membership and guarded output remain open.
Independent authority changes still require their own bounded owner work before
implementation. No new Delivery, hardware, interface or semantic decision is
selected, and no kernel workaround or implementation permission is supplied.

The connection-factory timeout is a separate runtime follow-up, not a missing
timeout proven from an omitted keyword. It passes the configured DSN to Psycopg.
The exact pinned pure-Python 3.3.4 wheel (`b6bbc25ccf05c8fad3b061d9db2ef0909a555171b84b07f29458a447253d679a`)
sets a default of 130 seconds per connection attempt in `psycopg/conninfo.py`
lines 20–23 and 123–151; DSN/environment values participate. `connection.py`
lines 97–109 compute it before resolving and trying connection targets.
That default is not an end-to-end bound on DNS, multiple attempts, lookup or D.
Any change to deadline propagation/connection policy requires separately bounded
runtime work; no timeout, DSN, pool size or role limit changes in this PR.

No implementation decision card is ready. Keep the current draft open while
reviewing Phase A; do not merge this assessment as a substitute for #392's complete
capability. An independent runtime, key, deployment or output authority change
must be handled in its own bounded Delivery rather than appended to this PR.

Expected eventual #392 areas include typed database operations; native placement
would need an eligible entry outside `kernel/tenant_uow.py`'s current `BEGIN`
wrapper, not a drop-in call within it. Other expected areas are an additive
migration if justified, matching narrow provisioning/readiness checks and focused
evidence. These are predictions, not approval or a selected design. Existing
migrations and canonical references stay immutable. No executable abstraction,
duplicate authority store or compatibility
path is added. The simplest gate/close alternatives and their concrete failures
are above; small diff size does not override the missing guarantees.

### 6.1. Receiver candidate for review

**Propose one fixed, private pathname Unix-domain stream to the existing runtime
minter process, received inside the already-proposed native read component.**
This avoids a reply table, capability rows/WAL copies, an extra reply transaction
and polling snapshots. It adds native I/O and a required local Linux deployment
arrangement. No new daemon, generic broker, direct database-to-KMS access or
cryptographic verifier is proposed. The existing runtime has no such listener;
this is a candidate interface, not evidence that it works.

**Associate the request before minting.** Runtime must exclusively retain the
actual PostgreSQL connection and its authenticated read/principal context while
dispatching the fixed top-level native CALL. The native entry derives its backend
incarnation and a fresh per-invocation nonce, then emits a bounded, fixed-format
NOTICE containing only protocol/correlation metadata: PID, backend start and
nonce. A notice handler on that exact connection associates these values with
the pending read. The native component presents the same tuple on its one socket;
runtime admits it only after matching the connection-associated tuple and OS peer
identity. The nonce is correlation, not a bearer credential; arbitrary SQL NOTICE
content or possession of that tuple must never grant minting authority.

This avoids assuming that application SQL may inspect backend start: the current
[observer/binder grant](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/migrations/0001_initial.sql#L6434)
does not grant that helper to the application. PID alone also cannot distinguish
backend reuse, nor can backend incarnation distinguish successive invocations.
Only the intended native entry on the exclusively owned connection may establish
the association. Effective `client_min_messages` must permit NOTICE at entry;
actual receipt and handling are required before socket admission. Suppressed or
missing NOTICE means no mint and no A. A permissive setting alone proves no
delivery. No global setting change or JWS in NOTICE, diagnostics or SQL results is
proposed. This bootstrap remains unimplemented and needs the hostile cases below.

The [Linux pathname/peer-credential contract](https://man7.org/linux/man-pages/man7/unix.7.html)
requires a protected directory/socket and attested local placement with compatible
PID/UID namespace mapping. Do not assume that PostgreSQL's PID equals the runtime's
peer PID across arbitrary containers. `SO_PEERCRED` gives connection-time process
credentials, not tenant identity, current liveness or invocation authority. Both
ends must verify their expected peer under the deployment owner's process mapping;
the runtime receiving the association must be the process retaining that request.
No caller-selected endpoint or transport fallback is allowed. This co-location
requirement is a real cost, not proof of isolation from source activity.

**One connection, two serialized mint phases.** Each request/reply is tied to the
admitted socket, invocation nonce, phase, full xid and fresh database-created
challenge (including its existing audience/time values). Runtime takes identity
and authority only from its retained trusted context, never from socket fields,
and calls the existing issuer. Its reply carries the unchanged JWS and the
expected binding fields from that trusted context. Native pins those expected
fields from the first reply for both phases, passes only the JWS as a parameter
to fixed schema-qualified binder SQL, then compares the returned tenant context
under the [existing binding contract](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/tenant_uow.py#L126).
These are comparison values, not alternate binder arguments or a new principal
decision; phase two must not silently replace them with another authority.
Bound frames before allocation, including the existing
[8192-byte capability limit](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/deployment/postgresql/tenant_contract.py#L37);
do not add a second JWS verifier. The association admits one socket and exactly
these phases: no reconnect, descriptor transfer, resumed invocation, replacement
socket, duplicate phase or successor consumption. Retire it on success, error or
abandonment. Finish the exchange and close the local socket after the second
successful binding, before final protection/S; no adapter work is added to the
positive C-to-L path. Existing refusal audit and remote-work disposition are still
obligations, not consequences of closing a descriptor.

**Native lifecycle.** The top-level procedure must be
[`SECURITY INVOKER` without an attached `SET` clause](https://www.postgresql.org/docs/17/sql-createprocedure.html)
to permit its transaction control. Keep invocation/socket state in the nonatomic
SPI procedure context, which [survives internal commits](https://github.com/postgres/postgres/blob/REL_17_10/src/backend/executor/spi.c#L148),
with fresh per-transaction challenge state. Use nonblocking I/O and bounded,
interruptible [latch/socket waits](https://github.com/postgres/postgres/blob/REL_17_10/src/include/storage/latch.h)
with PostgreSQL interrupt checks; do not retain transaction-owned wait state
across A. Account for the descriptor through
[`AcquireExternalFD`/`ReleaseExternalFD`](https://github.com/postgres/postgres/blob/REL_17_10/src/backend/storage/file/fd.c#L1186),
which do not close it. Explicit success cleanup and idempotent, non-throwing
[`PG_ENSURE_ERROR_CLEANUP`](https://github.com/postgres/postgres/blob/REL_17_10/src/include/storage/ipc.h#L24)
handling cover local cleanup; hard process death relies on OS closure. None proves
that dispatched authority lookup, KMS or transport work stopped. Connection,
accept, framing and cleanup work, including rejected traffic, still belongs in
section 5.1's resource argument. Wait limits never extend full D.

Avoiding persisted reply rows does not eliminate custody: runtime/native memory,
socket buffers and possible crash/swap copies remain. Custody owners must assess
those surfaces and permitted diagnostics; no perfect erasure or zero-copy claim
is made. Database/provisioning owners own receiver privileges, installation and
catalog evidence; runtime/deployment owners own the listener, exclusive connection
association, peer/namespace mapping and cleanup. Existing signing, binder and
audit authorities retain their boundaries. Joint interface review supplies no
combined implementation permission or inherited crypto-installer authority.

**First falsifiers, before admission.** Use the pinned PostgreSQL 17.10 and actual
roles/binder in isolated disposable databases with fictional requests: two binds
across A; suppressed/delayed/spoofed NOTICE; another request/backend presenting the
tuple; reused PID or backend with a stale registration; runtime restart; duplicate,
oversized, partial or wrong-phase frames; authority change; interruption or late
reply at each phase/commit. Verify no wrong-principal binding, successor use or
credential-bearing diagnostics, and account for all outstanding remote work. These
are proposed cases, not executed evidence. A failed trusted association or an
unacceptable local-placement/custody cost requires reconsidering the receiver;
neither justifies silently falling back to a table or widening authority.

This is the smallest receiver candidate found within the native-owner proposal,
not a complete protection design. Source stop/dispatch, S/I/C/L, full-D progress
and output acceptance remain open. Section 6.2 proposes the complementary runtime
lifecycle; neither section supplies an implementation decision card.

### 6.2. Complementary runtime candidate and unresolved integration

**One exchange, two execution paths in the existing runtime process.** Propose
one thread driving the fixed native CALL and one bounded socket/minter worker for
its registered read. This is the smallest arrangement assessed against the current
synchronous issuer; it is not a new daemon, broker, general worker pool or
multi-read capacity claim. The native invocation remains the proposed original
read owner. Neither runtime thread acquires its I/L authority.

Start from the existing [audited authentication path](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/application_runtime.py#L88),
retaining the authenticated principal and read context as immutable trusted values.
Use an exclusive, per-invocation non-pooled connection in autocommit mode for the
top-level CALL, without automatic preparation or an outer BEGIN. The current
[pool/reset contract](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/tenant_uow.py#L371)
is different; do not lend this connection through that pool. Acquisition and
backend capacity need explicit runtime/deployment admission. A dedicated connection
avoids that pool's lease dependency, not shared database/role capacity exhaustion.
No role, timeout or original lifetime bound is changed by this proposal.

**Pair both ends without a process registry.** Narrow this candidate to a direct
local PostgreSQL Unix socket as well as the private minter socket. The same runtime
process must create and exclusively retain the SQL connection and minter listener;
no proxy, process handoff or runtime descriptor inheritance/transfer is admitted.
Runtime captures its connection's [protocol backend PID](https://www.postgresql.org/docs/17/libpq-status.html)
before CALL. Under the attested namespace mapping, require socket peer PID =
NOTICE PID = that captured PID, alongside expected credentials, backend incarnation
and invocation nonce. Shared UID/GID alone cannot distinguish PostgreSQL backends.
Native can compare the minter peer credentials with those on its actual
[PostgreSQL frontend descriptor](https://github.com/postgres/postgres/blob/REL_17_10/src/include/libpq/libpq-be.h#L132);
PostgreSQL's [existing peer-credential use](https://github.com/postgres/postgres/blob/REL_17_10/src/backend/libpq/auth.c#L1872)
supports inspecting that socket. Native must not read, write or close the frontend
descriptor. This binds connection-time processes, not current liveness or native
code origin; the exclusive fixed CALL and full association remain necessary.
Local SQL connectivity and its authentication policy need deployment/database
owner review. Do not silently switch database authentication to `peer` or `trust`.
This additional placement restriction is a cost, not an already admitted topology.

**Register before CALL; accept either arrival order.** Retain one bounded request
record attached to the actual connection and its captured PID, then install the
notice callback and dispatch the fixed CALL. In pinned Psycopg 3.3.4,
[`execute` holds the connection lock while waiting](https://github.com/psycopg/psycopg/blob/3.3.4/psycopg/psycopg/cursor.py#L112),
and the [notice handler runs inline and catches callback exceptions](https://github.com/psycopg/psycopg/blob/3.3.4/psycopg/psycopg/_connection_base.py#L348).
The callback copies only bounded validated correlation fields; it does no SQL,
minting, socket I/O or worker join. Do not retain its temporary Diagnostic object
or depend on raising an exception to abort CALL. Invalid protocol metadata sets
an explicit refusal state without placing raw diagnostics or credentials in logs.

Native NOTICE emission before connect does not ensure Python processes NOTICE
before socket acceptance. The worker first checks the peer against the registered
connection PID, retains at most the bounded unadmitted socket/hello for that peer,
and waits for the matching copied NOTICE within the unchanged lifetime bounds.
No registration lock is held across waits, issuer calls, socket I/O or cleanup.
Only when both observations match may it atomically claim the single socket.
Wrong or duplicate presenters cannot consume, replace, retire or extend the live
registration or D. Missing NOTICE never authorizes minting; neither arrival order
requires reconnect. Test with the nonce deliberately disclosed: it is correlation,
not a secrecy assumption. The worker never operates the active PostgreSQL connection.

**Bound phase work to that registration.** Use section 6.1's bounded frames and
exact socket/nonce/phase/xid/challenge association; no client-selected method,
identity, endpoint or signing key. Admit each of the two phases once, then call
the existing issuer with the retained principal. Pin the existing first fourteen
principal-authority comparison fields across phases; independently validate each
binding's key/head, nonce and timestamp under the existing contract. Do not freeze
all nineteen returned fields or refresh principal authority from the next frame.
Retirement disables further phase admission. An already admitted issuer operation
may continue, including later lookup/signing stages; late completion must not
recreate a registration, move its reply to another socket or authorize a successor.
Before starting reply publication, recheck that the same request/phase is active;
discard the completed result if retirement is observed. Already admitted or
in-flight reply bytes remain separately accounted for, not retractable by a flag.
Finishing the mint exchange does not mean the CALL, A/C or L completed.

**Cancellation and completion stay distinct.** Separate CALL processing permits
native/server interruption to reach the SQL thread while the minter is blocked.
It does not supply application-triggered cancellation: the SQL thread is inside
execute and the worker may be inside synchronous minting. An independently
available control path is still unbound; this proposal does not invent a watchdog
or treat concurrent rollback/close as its substitute. The issuer exposes no stop
handle. Its [KMS timeout and disabled RPC retry](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/google_kms_signer.py#L30)
are not an end-to-end bound on lookup, receipt processing, cleanup or full D.

Normal disposal follows terminal CALL/result processing, then removal of the
callback and closure of the dedicated connection. Early close is abandonment,
not observed native-owner loss: PostgreSQL may [finish and commit before observing
disconnection](https://www.postgresql.org/docs/17/protocol-flow.html#PROTOCOL-FLOW-TERMINATION).
A lost response cannot prove A/C rolled back, trigger automatic CALL replay, or
restore I/L. Retire only this invocation's association; keep outstanding issuer
work owned and accounted for. Neither a local retired flag nor a worker join
establishes complete remote cessation or allowed waiting. The existing
[runtime shutdown](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/application_runtime.py#L109)
does not yet cover this listener, connection and mint lifecycle. Their startup,
shutdown, rejected traffic and delayed cleanup remain in section 5.1's resource
argument through acknowledgement/L; two threads establish no isolation guarantee.

**Audit integration is a concrete remaining owner decision.** The existing
[request-router wrapper](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/request_router_audit.py#L88)
catches classified errors during UnitOfWork entry only; its
[tests exclude post-binding failures and finalization uncertainty](https://github.com/samovers/OFARM2/blob/1b4d52e2d6387d486110465973ad822089bd9583/kernel/tests/test_request_router_audit.py#L232).
Putting the entire two-transaction CALL inside a replacement context entry could
misclassify a second-bind error after durable A as an initial pre-tenant denial.
The audit/runtime owners must map initial entry, post-A binding and uncertain
finalization separately while preserving existing reason, health and gap rules.
No new audit reason or reinterpretation is selected here; calling mint_capability
alone does not inherit that wrapper. SQL completion and phase labels also grant
no output authority; the actual guarded L remains the output owner's open binding.

**Focused evidence before implementation admission.** Add to section 6.1's cases:
both socket/NOTICE arrival orders; rejected presenter followed by legitimate
presentation; callback refusal without raw-data logging; attempted SQL re-entry;
retirement during authority lookup/KMS with inert late results; server interruption
while mint is stalled; failure after committed A; lost CALL response; shutdown with
outstanding work. Use actual roles/binder, pinned PostgreSQL and driver, fictional
requests and disposable databases after approval. These cases have not run.

Phase-specific audit disposition, independently available cancellation and full
remote-work/capacity disposition remain conditional owner obligations. Preserve
these findings and safeguards, but park further adapter design until section 6's
source/progress case has a credible answer. This assessment grants no authority
change or implementation permission; the original S/I/C/L obligations remain open.

## 7. Verification and claim limits

Completed before publication: live main/#392/PR inventory reads; pinned source
and canonical input checks; primary driver/PostgreSQL contract reads; inert
inspection of three lock-matching wheels (139 RECORD entries and ten extracted
members verified); bounded local peer assessments. These are static evidence,
not independent approval or #392 blocker clearance.

The draft PR body records the fresh mandatory package check, whitespace/link
checks and exact publication head. No runtime, PostgreSQL, KMS, concurrency,
benchmark, crash or hosted expensive baseline ran for this design. No isolation
topology was built. Prior implementation test results are not reused as evidence
for this candidate.

Next: review the bounded source-case assessment and corrected work priority, then
resolve actual source ownership, stop/dispatch and surviving resources before
resuming adapter design. Retain open blockers and existing approvals; no
implementation decision card is ready.
