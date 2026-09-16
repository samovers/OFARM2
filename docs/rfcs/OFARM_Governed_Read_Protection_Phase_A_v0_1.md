# Governed-read protection: Phase A assessment and open blockers

Version 0.4, 2026-09-16. Delivery [#392](https://github.com/samovers/OFARM2/issues/392).
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

## 6. Smallest next scope and review request

Section 5.1 is the proposed answer for the existing PR #37/#36 evidence-binding
question. Before investing in another placement, obtain focused owner review:
**Does this combination of independently observed order, controlled causal cases
and a complete provider resource/lifetime argument establish the required kind
of evidence without exempting candidate-induced failure or changing D; which
concrete proof obligation, if any, is missing?** The existing text remains
controlling. Method review does not approve a provider or clear the other open
bindings. If an owner instead
proposes a noise tolerance or different outcome rule, it needs a concrete,
separately reviewed semantic amendment; this draft supplies no such permission
and requests no repeat approval of the existing semantics.

The existing restricted runtime/deployment proposal would keep new source offers
outside the protected execution domain until L. Its costs include reduced source
concurrency, restricted connectivity, original read-owner placement and output
integration. Queuing before checkout avoids additional checkout leases from those
requests; excluding their authority connections also requires admission before
those lookups start. It does not free already-open pooled or unpooled backends.
Nor is an external queue proved the only
way to preserve an original request: a lawfully stopped attempt can release its
lease while the request survives under PR #26's complete outcome/evidence rules.
No working stop/release mechanism is supplied by that possibility.
The placement's later correction still leaves already-started database
preparation unresolved. Reviewing that arrangement would investigate a candidate,
not adopt a proven solution. The FPGA/device-memory bridge stays parked.

Review this draft for concrete errors in the source/authority mapping, omitted
causal cases, an incorrectly rejected smaller mechanism, or a justified way to
advance the existing arrangement within its owners. In particular:

1. Does any claimed database guarantee exceed what the pinned code supplies?
2. Can a concrete existing mechanism close both actual ordering and retained
   resource progress without assuming a stalled participant will cooperate?
3. After the evidence-method proposal above is reviewed, is further work on
   the restricted arrangement justified by its scope/cost, capacity benefit and
   unresolved preparation/output dependencies?

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

Expected eventual #392 areas remain typed database operations near
`kernel/tenant_uow.py`, an additive migration if justified, matching narrow
provisioning/readiness checks and focused evidence. They are predictions, not
approval or a selected design. Existing migrations and canonical references stay
immutable. No executable abstraction, duplicate authority store or compatibility
path is added. The simplest gate/close alternatives and their concrete failures
are above; small diff size does not override the missing guarantees.

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

Next: review section 5.1 against the existing read-owner requirements, then use
that method to assess a concrete mechanism; retain open blockers and approvals.
