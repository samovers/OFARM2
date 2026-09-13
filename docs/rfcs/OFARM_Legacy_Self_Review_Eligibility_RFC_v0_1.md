# Legacy compliance self-review eligibility

Status: **approved implementation; local verification recorded below;
exact-head content review and hosted evidence are separate gates**.
Decision: `OFARM2-LEGACY-SELF-REVIEW-ELIGIBILITY-001`, version 1.
Delivery: [#385](https://github.com/samovers/OFARM2/issues/385), under Tracking
Epic #180, in named [PR #386](https://github.com/samovers/OFARM2/pull/386).

Approval navigation: in task `01a07cc8-4157-7b33-a0ca-becb772e0e8b`, the live
card `msg_0d813f8071772f9a016aa59fc72b5487d293c170fb684a3b55` at
2026-09-12T18:54:24.109Z names PR #386. The later original task-user message
`msg_01a09a37-50c0-7991-acaa-b175fe812417` at 2026-09-13T10:01:51.552Z says
`I approve OFARM2 decision OFARM2-LEGACY-SELF-REVIEW-ELIGIBILITY-001 version 1.`
That original user message supplies semantic authority; these references are
navigation only. The original card and E01–E07 remain unchanged. Approval does
not authorize merge, deployment or another Delivery.

Design base: `e50ae95f43d0e73b12113463d0e4ea85eebdc14b`, after merged PR #384.
Its reviewed runtime tree is `17b134856f75391df50cf2dc298dc3bcef6c6208`.
PRs #380, #382 and #384 remain completed historical work.

## Problem and one deliverable

An otherwise valid fresh legacy compliance submission with literal
`confirmAccept: true` and `reviewerPartyRef: null` can self-accept. In
`ReviewPromotionGate.run`, `sub.get("reviewerPartyRef", ctx.acting_party)`
returns `None` for a present null, suppressing the compliance routing rule.
The separate body-named-reviewer guard also excludes `None`. Sufficient
authority and evidence then allow `emit_self_review_promotion` to create an
accepted review and compliance consequence naming the asserter as reviewer.

The independently useful outcome is that a fresh confirmed compliance claim
requires its existing independent-review path, regardless of omitted, null,
self-named or distinct-body-named reviewer metadata. The claim remains usable
in the queue: the asserter cannot accept it, while a distinct acting reviewer
with the existing authority and evidence can accept that same pending claim.

The primary trust boundary is **self-review eligibility enforcement** before
new accepted-force emission. This is high-risk because it changes a reachable
accepted-force decision. It enforces the existing D8 restriction for confirmed
compliance assertions; it creates no new review rights, reviewer identity,
contract or production capability.
General reviewer-field typing and wider direct-versus-queued consistency are
separate work. The bounded D17 structure policy stays unchanged.

**Known K04 residual, outside this correction:** with otherwise sufficient
authority and evidence, a confirmed `OBSERVATION_ASSERTION` can directly
self-accept on the legacy route with omitted, null or self-named reviewer
metadata, while its asserter's queued acceptance is refused. This existing
discrepancy is not permitted D8 behavior or repaired by this compliance change.
[Delivery #387](https://github.com/samovers/OFARM2/issues/387) owns the separate
observation correction; its implementation is not approved here. E04 preserves
the named permitted positive controls, not an exhaustive account or guarantee
of every other class's behavior. This PR does not close K04.

## Existing authority and containment

| Owner | Authority that remains with it |
| --- | --- |
| Accepted D8/D17 and existing policy | Eligible self-review classes and independent-review requirements |
| Existing transport and direct-call integration | Actor binding; HTTP actor mismatch retains its existing 403 precedence |
| Existing parser | Strict optional boolean confirmation and unmodified raw submission identity |
| Existing authority and validation gates | Assertion/review rights, scope, evidence, semantic validation and correction targets |
| Existing promotion gate and emitters | Routing before new acceptance, reviewer provenance and server decision time |
| Existing queue validator | Reviewer's own governed decision, stored-asserter comparison and terminal-decision guards |
| Existing Store and pipeline | Transaction ownership, idempotency, append-only records, lineage and materialization |
| Task user | This semantic decision and a later separate exact-head merge decision |
| Reviewers, CI, publisher and GitHub | Findings, mechanical evidence, evidence custody and native PR state; no human approval |

Protected assets are independent-review eligibility, the pending/accepted
distinction, accountable review records, unchanged history and replay identity.
The submitter may hold legitimate farm-scoped assertion and review grants and
control the request body, reviewer hint and idempotency key. That body cannot
supply another party's review act. Arbitrary trusted-process modification,
direct database-writer access, host compromise and stolen credentials are
excluded attacker capabilities; this correction does not purport to repair them.

The real negative is the existing legacy `POST /commit` route with a bound
actor, valid compliance payload, sufficient evidence and authority, literal
true, a fresh key and present-null reviewer metadata. The same decision is
exercised through supported `GatePipeline.commit`; callers retain its
existing actor-context obligations. Public production governed routes remain
closed. No authentication or principal-resolution change is included.

## Smallest approved correction and ordering

In the existing compliance condition in `ReviewPromotionGate.run`, remove the
comparison to `reviewerPartyRef`. The approved eligibility condition is simply
`ctx.commit_class == "COMPLIANCE_ASSERTION" and confirmed`. The direct emitter
always names `ctx.acting_party` as both asserter and reviewer, so the claim
class and confirmation already identify the disallowed self-review attempt.
There is no need for a fallback reviewer, coercion, stored flag or new policy.

Keep the existing warning and pending-assertion path. Keep the later
distinct-body-named-reviewer guard for its existing consumers, the D17
structure condition, queue validator and every emitter unchanged. For a
distinct-body-named compliance request, both existing routing explanations may
now appear; the decision remains review-required. This diagnostic addition is
permitted, not a second authority decision.

The similar structure comparison remains at the design base's
`kernel/stages.py:645–648`. `StructureCarrierValidator` and
`policy.structure_self_acceptable` both use `STRUCTURE_PAYLOAD_IDENTITY_TYPE`
(`kernel/validators.py:766`, `kernel/policy.py:202–211`). Supplementary review
F1 reports seven hostile structure shapes refused and a recognized bounded
positive accepted. This is latent follow-up context for later structure/K04
work, not proof that every possible hostile input is unreachable. If carrier
admission and that eligibility set diverge, the retained comparison needs
review in its own scope; this PR neither deletes it nor certifies it safe.

The existing order remains:

1. Transport binding and shared ingress parsing precede the transaction.
2. Ingress checks the key and handles replay/conflict before the stage chain.
3. Fresh submissions pass the existing identity, authority, evidence and
   semantic validation gates before promotion eligibility.
4. A confirmed compliance submission reaching the direct-promotion decision
   gains the existing compliance routing reason and emits a pending assertion.
   It does not enter direct `REVIEW_ACCEPT`, retirement authorization or the
   self-review acceptance emitter. Earlier failures retain their own outcomes;
   not every malformed or unauthorized request promises `REQUIRE_REVIEW`.
5. An independent queued acceptance remains a separate `GOVERNANCE_DECISION`
   by the actual reviewer, with its existing validator, authority, retirement
   checks and acceptance emitter. Reject and contest remain unchanged.

The normalizer populates `acceptance_target` only for `GOVERNANCE_DECISION`.
A compliance submission cannot select the earlier queue emitter merely by
including review-target fields. Preserve that existing class boundary.

This fixes a new evaluation. It does not re-evaluate or retrospectively repair
an already accepted historical submission.

## Historical replay is deliberately preserved

`IngressNormalizer.run` and `ReplayWriter.write` short-circuit before the
promotion gate for existing keys. A matching key, raw digest and existing
tenant/runtime-bundle coordinates may return `REPLAY_REUSED_RESULT` with the
original accepted references, even if that old acceptance used the null defect.
The replay appends its existing ingress request, trace, result and gate log;
it creates no new assertion, review, accepted consequence or retirement, and
does not rewrite prior record bytes, edges, materialization or claimed key.
Mismatched payload or runtime coordinates retain their existing conflict path.
Changing null to omission under the same key is a raw-digest change, not a
new eligibility evaluation. The gate edit does not change the existing runtime
bundle component inventory or invent a new bundle identity to defeat replay.
Malformed confirmation still fails the pre-transaction parser as established
by PR #384; replay does not bypass that admission.

**Material limit:** deploying this repository correction would not cleanse old
incorrect acceptances or remove accepted references from their matching replay
responses. No historical repair, migration, replay-policy change or production
deployment is proposed. A different historical treatment needs its own scoped
decision before implementation; it cannot be silently included in this fix.

## Decision invariants and falsifiable evidence

| ID | Required outcome and verification |
| --- | --- |
| E01 | A fresh otherwise-valid confirmed compliance request with null reviewer metadata takes `REQUIRE_REVIEW` / `HUMAN_APPROVAL_REQUIRED` on the real HTTP route and supported direct pipeline. Inspect persisted records/edges: pending assertion, no newly accepted review or compliance consequence. Demonstrate the same regression fails on the unmodified base. |
| E02 | Omitted, explicit-self and distinct-body-named controls remain review-required. Raw reviewer metadata is neither normalized nor promoted into reviewer identity. Literal false/omission of confirmation retain existing capture behavior, and malformed confirmation retains existing rejection. |
| E03 | Continue from E01's exact pending assertion: its asserter's queue acceptance refuses without consuming the claim; an authorized distinct reviewer can then accept it once, with that reviewer's provenance and server decision time. A duplicate decision remains refused. Existing reject/contest behavior is preserved. |
| E04 | Existing permitted routine-operation and bounded farm-owned-structure self-acceptance remain functional, with their existing actor/evidence/authority checks. No new eligibility guarantee for other classes, wrong-typed reviewer metadata, unbounded structure assertions or the wider K-04 matrix is claimed. |
| E05 | Existing assertion/review authority, evidence refusal and correction-retirement controls remain effective. Routing this compliance claim creates no acceptance or retirement; accepted correction paths retain the existing separate `REVIEW_SUPERSEDE` requirement and transactional refusal behavior. |
| E06 | Preserve raw submission digests, omitted/null identity distinctions, pending and accepted-key replay/conflicts, and prior record bytes/lineage. A matching historical accepted-null replay may return old accepted refs but creates no new acceptance. Check actual Store effects; response labels alone are insufficient. |
| E07 | Keep transaction ownership, frozen/canonical records, grants/principals, signing, production closure and audit/publication policy unchanged. Verify a bounded diff and relevant existing atomicity/closure controls; do not claim a full security or lifecycle audit. |

## Verification plan and proof attribution

Use existing fictional fixtures and isolated disposable PostgreSQL only. For
implementation, capture the hostile fresh-null failure on the pinned parent
and the fixed result with the same fixture, naming interpreter, dependencies,
database version and every unavailable case. Use a fresh database for each
independent probe or clearly identified isolated fixture; preserve other local
resources and remove only this Delivery's disposable resources afterward.

Extend the existing HTTP/Store review tests and supported direct-pipeline
tests. Prefer the same-assertion queue sequence over an unrelated acceptance
positive. Inspect new record kinds, review/consequence counts and relevant
edges, the immutable pending assertion, queue disposition and reviewer identity.
After queue acceptance, that original assertion still stores
`claimState: PENDING_REVIEW`; acceptance and removal from the pending queue are
derived from its `REVIEW` edge, accepted decision and consequence. Compare the
original assertion bytes unchanged; do not expect or introduce an `IN_FORCE`
mutation to satisfy E03.
Store snapshots establish durable effects; they do not prove read-only lookup
counts or pre-transaction ordering. This repair is intentionally after ingress,
so it introduces no transaction-free failure contract.

The focused module has eight collected cases: one HTTP null-origin queue
lifecycle, four public-pipeline reviewer controls, one pending-null replay/digest
conflict case, and two HTTP compliance capture controls. For E02, omitted and
literal-false `confirmAccept` on valid compliance submissions must retain
`RETAIN_DRAFT`, no problems, one pending assertion, and no review or consequence.
The original six-case prediction missed this compliance-specific confirmation
axis; review B2 adds evidence for the unchanged invariant, not new semantics.
Reuse `test_review_confirmation.py` for operation-claim confirmation and shared
parser/transport controls; those operation claims do not execute the compliance
predicate. Keep its bounded-structure and authority/evidence controls;
`test_m2_review.py` covers reject/contest; and `test_correction_authorization.py` and
`test_correction_transactions.py` for retirement, history and atomicity.
The existing conformance tests 93/94 provide valid compliance/queue fixture
patterns. The HTTP fixture binds the legacy test transport principal; it does
not exercise production OIDC authentication.

For the particular historical accepted-null limit, use a bounded, explicitly
labelled base-to-candidate probe after approval: create the fictional bad
acceptance only under the unmodified base in its disposable database, then
observe candidate replay against that same retained fixture and a fresh key.
Keep its old record bytes and digest available to compare. This is evidence of
the history non-effect, not an assertion that new wrongful acceptance must
remain possible. Reuse existing lawful accepted-compliance replay tests for
ongoing compatibility rather than adding a production bypass or a second
synthetic acceptance writer. Exact replay uses a stable full submission through
`/commit`; `/review/accept` itself generates a new `decisionTime` on each call.
Name which controls were executed and which remain source-inspection claims.

Supplementary review evidence is separate from implementation proof. The full
review supplied in task-user message
`msg_01a0971d-c6fa-7ca3-8f6a-bb14ef0b4a4f` (SHA-256
`f568d9740295a1c9b45511e4963adeb810cd54eecdc37f6047c28a3fa5249e4a`)
is also published as [review 5191268560](https://github.com/samovers/OFARM2/pull/386#pullrequestreview-5191268560),
body SHA-256 `e90217cb974bef9c9e5c4ece5a997489193bb2d322b03a94775304837bb14960`.
The public body differs only by one terminal newline; its text reviews the old
design head even though GitHub attaches it to the implementation head. It
reports a transcribed predicate in the reviewer's clone, CPython 3.11.15,
PostgreSQL 16.13 and unpinned wheels: 229 passed and 2 failed on each side,
plus separate 23/23 and 42/42 runs. Its attribution of the two failures to
harness pollution is the reviewer's diagnosis, not an independently verified
result. Its legacy test transport, supplied fixture grants and sequential
isolated probes do not establish production authentication, concurrency,
transaction, custody or publication guarantees. Those measurements, including
F1, are supplementary design evidence and do not replace fresh parent and
implementation-head verification. The local results below are separately
executed implementation evidence.

Expected areas are `kernel/stages.py`, focused files under `kernel/tests/`,
`docs/REVIEW_DISPUTE_SEMANTICS.md`, this RFC and the prescribed generated test
inventory if collection changes. The active semantics state the approved
bounded repair and historical limit; the original PR #384 decision
records remain unchanged as history. The implemented capability, tests and
necessary inventory/documentation belong in this one PR. No independent
evidence-only or approval-only companion PR is needed.

Before every commit, the package check must pass. During Phase A, run only
design hygiene and mandatory cheap checks; no runtime implementation or
expensive baselines. After exact semantic approval, implement, run focused
tests and required cheap checks, push and obtain an exact-head zero-Blocker
content review. Only then create the existing unedited admission comment and
run the trusted source/publisher sequence: prescribed twice-run full baseline,
equivalence, platform/native jobs and authenticated final receipt. Inventory
and receipt must name this candidate; PR #384's results are historical context,
never replacement proof. Apply the existing extraction gate according to its
actual scope, reporting any failures without inventing an exemption or waiver.

Every new candidate requires fresh review and applicable evidence. Finally
present the complete packet and yield for the separate later exact-head user
merge authorization under `AGENTS.md`. No manual admission substitute, policy
change, rerun of source/publisher attempts, admin/auto merge or direct main push
is included.

## Code excellence, non-goals and provisional posture

EXC-001/002: keep one authoritative eligibility path and actual actor identity,
without another validator, identity source or stored state. EXC-003: each
guarantee traces to the existing gate/emitter and actual public-entry/Store
evidence. EXC-004: delete the misleading compliance reviewer-hint comparison;
keep still-used distinct-reviewer and structure controls. EXC-005: add no
kernel abstraction. EXC-006: a blanket null rejection would change ingress and
capture semantics unnecessarily; metadata coercion would leave eligibility
dependent on a caller hint. A shared eligibility framework would broaden this
small correction into independent class and queue policy decisions. Reusing
the queue's allowlist for direct promotion is the simpler broad alternative,
but it would change observation behavior and require an explicit D17 exception;
those additional eligibility decisions belong to separate work.

No confirmation-parser change, general reviewer-field schema, wrong-typed
subject repair, observation semantics, broad K-04 consistency, evidence matrix,
new grants/actions or actor classes. No canonical/reference/frozen-contract,
profile activation, credential, signing/custody, database-role or transaction
ownership change. No audit/publication mechanism, historical rewrite,
deployment, release or production-route activation. Epics #180/#167, related
#179 and #184, and wider K-04 remain separate work.

The independent-review rule is intended to endure. The legacy development
surface remains provisional before deployment and this is no production-safety
certification. Evidence that the narrow predicate cannot preserve a usable
queue or the stated history/authority invariants requires redesign before
implementation proceeds; another authority boundary requires separate work.
Changes to capability, effects/non-effects, authority, E01–E07, named PR or
production posture require a new decision version and exact approval.

Next: finish the remaining verification gates, obtain exact-head content
review, and follow the existing evidence and separate final merge-authorization
sequence for PR #386.

## Initial local implementation verification — 2026-09-13, head `81f1ce1`

The runtime change removes only the compliance reviewer-hint comparison
(one insertion, two deletions). Six focused regressions were added and the
prescribed inventory grew from 4,475 to 4,481 entries, with no removals.
The unchanged design-head runtime produced three null-related failures and
three passing reviewer controls; the corrected runtime passed all six. The
existing conformance module passed 23/23 in its own database/session.

The sequential E06 probe created an actual fictional bad acceptance using the
unchanged base runtime, then used candidate code against that retained
isolated database. Matching replay returned the same assertion/review/
consequence references, adding only three request/trace/result records and
one gate-log row. All prior records and other governed tables were unchanged.
A fresh key required review without a new accepted review or consequence.
No history rewrite or synthetic acceptance emitter was used.

These are supplemental local runs on CPython 3.12.13, macOS ARM64, with
installed versions matching the lock, and a uniquely labelled disposable
PostgreSQL 17.10 container pinned by the baseline image digest. Linux wheel
hash authentication and the complete hosted baseline remain separate gates.
Function-isolated tests use fresh databases; the history probe deliberately
retains one database across its two sequential phases. Fictional demo grants
and legacy actor binding do not establish production authentication or a full
security audit. PR #386 records the complete execution and review evidence.

## E02 evidence correction — 2026-09-13

[Implementation review 5191463884](https://github.com/samovers/OFARM2/pull/386#pullrequestreview-5191463884)
closed its prior B1/F1/P1/P2 requests and identified B2: the six initial tests
did not detect removal of `and confirmed`, while the cited confirmation tests
exercise operation claims. The runtime predicate was correct; the compliance
capture guarantee lacked direct evidence. Two added HTTP cases now show that
omitted and literal-false confirmation retain ordinary capture, with empty
problems, one pending assertion, no review/consequence or REVIEW edge, unchanged
raw-input digest and prior records, and no routing reason in the stored gate log.

All eight focused cases passed on the unchanged runtime. In a disposable copy
with only `and confirmed` removed, both new cases failed on `REQUIRE_REVIEW`
versus `RETAIN_DRAFT` (six other cases deliberately deselected). This is focused
mutation calibration, not an exhaustive test-adequacy or security claim. The
prescribed inventory gained exactly those two entries, 4,481 to 4,483, without
removal or reattribution. This correction changes tests and attribution only;
the runtime and approved E01–E07 are unchanged. Local evidence uses the same
interpreter/package limits above and a newly owned isolated PostgreSQL 17.10
fixture. Fresh exact-head review and hosted publication remain required.

The reviewer's closure of the disclosure requests does not repair observations
owned by #387, remove the structure comparison, change historical replay, or
turn the separately disclosed extraction diagnostic into a passing check.
