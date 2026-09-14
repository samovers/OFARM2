# Legacy observation acceptance eligibility

Status: **Approved decision; implemented, with review and hosted evidence pending**.
Decision: `OFARM2-LEGACY-OBSERVATION-ELIGIBILITY-001`, version 1.
Delivery: [#387](https://github.com/samovers/OFARM2/issues/387), under #180;
implementation: [PR #388](https://github.com/samovers/OFARM2/pull/388);
related promotion-matrix programme: #179. This record is design evidence,
not user approval or OFARM law.

Approval navigation: in Codex task `01a07cc8-4157-7b33-a0ca-becb772e0e8b`,
the original card is message
`msg_0d813f8071772f9a016aa6ef908cdc87d2b3edbcf339956013`
(2026-09-13T18:46:59.909Z, session line 11819), naming existing draft PR #388.
The later task-user message
`msg_01a09c78-89b3-75b3-91fa-c8e6d25863b8`
(2026-09-13T20:32:20.403Z, session line 12080) states exactly:
`I approve OFARM2 decision OFARM2-LEGACY-OBSERVATION-ELIGIBILITY-001 version 1.`
The original messages were directly retrieved in that order. The design
clarifications at `0931e47a2f03c5ff10eeeaac12108e2add175544` preserved O01–O07
and the live card's semantic scope. This reference supplies navigation only;
the task-user message supplies approval. Merge requires a later exact-head
packet and authorization under `AGENTS.md`.

Design base: `9d7541d96bc708e9270b986927d7f4b8a035454f`, after merged PR #386;
runtime tree: `63d532112ed7c705997d0d71f5f6d0fec12928f7`.
PRs #380, #382, #384 and #386 remain completed historical work.

## Problem, selected outcome and exact boundary

At the design base, an authorized actor with observation-creation and
review-accept grants can self-accept a confirmed legacy `OBSERVATION_ASSERTION`
with omitted, null or self-named reviewer metadata. The same actor's queued acceptance is refused
under D8, while a distinct authorized reviewer can accept it. Audit K04 and
PR #386's executed review already demonstrate that discrepancy. The complete
review is now public as [review 5191268560](https://github.com/samovers/OFARM2/pull/386#pullrequestreview-5191268560),
whose body names design head `0472668`; its API-associated commit is not its
executed candidate. Its CPython 3.11/PostgreSQL 16/unpinned measurements are
supplemental, not pinned verification of this proposal. No audit is restarted.

D8 permits routine-operation self-review; D17 adds only bounded farm-owned
structure. Neither grants observation self-review. [Issue #179](https://github.com/samovers/OFARM2/issues/179)
also requires observation promotion to remain disabled until typed semantics
exist. Merely sending observations to a distinct reviewer would leave that
recorded requirement unmet. The approved independently useful outcome is:
**retain otherwise-valid observation captures, but permit no new observation
acceptance through either the direct or queued legacy path, for any actor**.
This implements only that eligibility limit from #179, not its broader matrix
or evidence-ingestion programme.

The primary trust boundary is **observation acceptance eligibility before
new accepted-force emission**. This is high-risk because it removes reachable
direct and independently reviewed acceptance, including observation correction.
The PR contains this one complete restriction and its tests/documentation;
it does not change observation payload meaning, reviewer grants, correction
compatibility/retirement authority, custody or production activation.

**Explicit change to an earlier approved capability:** correction decision
`OFARM2-LEGACY-CORRECTION-AUTHORIZATION-001` version 2, RFC v0.2 C03/C10,
previously preserved observation acceptance and same-family correction.
This approved decision narrows only their observation acceptance
availability: no new accepted observation or observation correction successor
can be emitted, even with valid `REVIEW_ACCEPT` and `REVIEW_SUPERSEDE`.
Their relationship/provenance checks and retirement permissions are not
weakened. Other assertion families retain their decided correction paths.
The historical RFC and completed decision are not rewritten. This explicit
restriction, rather than treating a former positive test as disposable, is
why this restriction required its own semantic approval.

## Authority, threat and containment

| Owner | Authority that stays with it |
| --- | --- |
| Task user | This new eligibility restriction and later exact-head merge acceptance |
| D8/D17 and existing review policy | Routine-operation and bounded-structure rights; compliance independent review |
| Existing transport/parser | Bound actor; strict optional boolean; raw request and idempotency identity |
| Existing authority/validation/evidence gates | Farm/scope, grants, durable evidence, target/carrier and correction relationships |
| Existing review-promotion gate | One observation eligibility decision before either acceptance emitter |
| Existing queue validator | Stored target, actor relationship, rationale/evidence, terminal and bundle checks |
| Existing Store/pipeline/emitters | Transactions, append-only lineage, replay, rejection/contest and materialization |
| Review, CI, publisher and GitHub | Findings, mechanical evidence/custody and native PR state; no user authority |

Protected assets are the capture/accepted distinction, accountable review,
accepted history and predecessor lineage. The caller can control the body,
confirmation, reviewer hint, requested target and fresh/reused idempotency key,
and may legitimately hold both assertion and review rights on the farm.
A distinct authorized reviewer is also in scope: stronger grants cannot
manufacture missing typed observation semantics. Trusted-process modification,
direct database writers, host compromise and stolen credentials are excluded.

The supported reachable negatives are legacy `POST /commit` and
`POST /review/accept`, backed by real `GatePipeline.commit` and Store.
Public production governed routes remain closed (`kernel/api.py:74–83`).
This is a legacy development/conformance correction, not a production
reachability, readiness or authentication claim.

## Smallest correction and ordering

Keep every existing type/target map and all earlier gates. At the start of
`ReviewPromotionGate.run`, before reviewer-hint routing, retirement authority
and both acceptance emitters, determine the assertion type for this act:

- For a validated queue **ACCEPT** with `acceptance_target`, use the fetched
  `ctx.acceptance_payload` assertion type, never caller-supplied type fields.
- Otherwise use the existing commit-class-to-assertion-type map. Queue REJECT
  and CONTEST are governance decisions, so neither becomes an observation
  acceptance merely because its stored target is an observation.

One explicit observation condition controls both outcomes. A direct observation
that passed earlier gates uses the existing pending-assertion emitter and
returns `RETAIN_DRAFT`. Omitted/false confirmation retains the ordinary
capture diagnostic; literal true reports registered `HIGH_CONSEQUENCE_BLOCKED`
with the exact title `Observation acceptance disabled` and text explaining
that acceptance awaits approved typed semantics and
cannot be enabled by a distinct reviewer. A queued observation ACCEPT that
reaches this gate returns `RETAIN_DRAFT` with the same eligibility explanation,
without a new assertion, ReviewDecision, REVIEW edge, consequence or retirement.
No new runtime constant set, helper, policy service, contract value or persistent flag
is needed for this single condition with two actual emission paths.

For the O02 diagnostic checks, assert the pair `(HIGH_CONSEQUENCE_BLOCKED,
Observation acceptance disabled)` on the new direct/queued eligibility result;
earlier refusals keep their existing code/title. This pins an implementation
diagnostic without changing O02 or introducing a new reason-code enum.

A direct observation outside the event-time plausibility window still returns
`RETAIN_DRAFT`, preserving its earlier `EVIDENCE_INSUFFICIENT` / `Event time
outside plausibility window` warning in result problems and as the promotion
gate's reason code, before the eligibility diagnostic when confirmation is true.
This preserves O02's ordinary diagnostics without promising available acceptance.

Existing earlier refusals retain their precedence. In particular, the
asserter's queued self-acceptance still fails the existing D8 validator with
`HUMAN_APPROVAL_REQUIRED`; a distinct reviewer passes that relationship check
and encounters the new eligibility refusal. Missing authority/evidence, invalid
targets, wrong farm/bundle and terminal claims need not reach the new guard.
The final outcome is not silently relabelled to hide those earlier reasons.

Keep `COMMIT_CLASS_TO_PROMOTION_TARGET` and `ACCEPTANCE_BY_ASSERTION_TYPE`:
they also describe historical consequence families, requested-target/subject
validation, evidence floors and correction provenance. Removing observation
entries would skip capture checks or change historical interpretation.
Those maps are representational, not sufficient current acceptance authority;
the existing governed pipeline remains the only supported acceptance entry.
In particular, accepting `ACCEPTED_OBSERVATION_OCCURRENCE_STATE` as a matching
requested-target value establishes type compatibility only: a well-shaped
request still reaches the new acceptance-disabled outcome.

Direct captures retain `claimState: PENDING_REVIEW` because that is the existing
inert assertion vocabulary, not a promise that acceptance is enabled. They may
remain visible in the pending queue. A distinct authorized reviewer may still
reject them under D20; the asserter may not self-reject. Rejection remains
terminal and append-only. A blocked acceptance must not consume the claim or
prevent a later lawful rejection. No queue UI, new state or invented decline
is added. User-facing diagnostics must not promise that an advisor can accept.

Evidence sufficiency remains distinct from acceptance eligibility. Direct
observation capture does not create `case_payload`, so `_store_case` returns
without inserting an EvidenceSufficiencyCase; use the existing pending emitter
with `amend_case_for_routing=False`. A validated queued ACCEPT may already have
persisted a satisfied evidence case before this guard. Its evidence decision
is not acceptance permission and is not retroactively amended. The new
eligibility explanation belongs to the result problems and promotion gate log.
[Delivery #389](https://github.com/samovers/OFARM2/issues/389), under #179, owns
any separate improvement to retained case/final-outcome reporting for consumers;
this PR neither invents a direct observation case nor changes case semantics.

## History, correction and non-effects

History is deliberately preserved. Matching old successful idempotency keys
still return old accepted references before eligibility is reevaluated. No
assertion, acceptance, consequence or lineage is repaired, deleted or relabelled.
The same body under a fresh key encounters the new rule. Previously queued
observations also cannot newly accept; they can remain pending or be lawfully
rejected. Existing accepted observations stay available for reads and governed
CONTEST. Old acceptance replay is not new acceptance authority.

An otherwise-valid new observation correction can retain its existing inert
intent and pending assertion, but cannot produce a successor or retire its
predecessor. A previously queued correction is similarly blocked before the
retirement check/emitter. Existing provenance/compatibility validation can
still refuse it earlier. An old disputed observation may therefore remain
unresolved by correction until a future explicit typed-semantics decision.
This material limit is part of the approved decision.

Operation/structure/compliance acceptance, correction and review decisions,
strict confirmation parsing, raw request digest, actor binding, grant ownership,
evidence policy, transaction ownership, D20 rejection, contest rules, signing,
publication custody, canonical contracts, manifests and production closure
are non-effects. No general promotion matrix or latent structure predicate
repair travels here. #179 and #180 retain their wider programme scope.

## Decision-level invariants and falsifiable verification

The table defines required candidate results, not a claim that checks passed.
Executed results belong to PR #388's implementation evidence.
Use fictional fixtures, real HTTP and durable Store records in function-isolated
disposable PostgreSQL databases. Preserve earlier refusal reasons and check
whole accepted-record/lineage snapshots, not response enums alone.

| ID | Required result and counterexample |
| --- | --- |
| O01 | Valid fresh confirmed direct observations with reviewer omitted/null/self/distinct all retain one pending assertion and emit zero accepted reviews/consequences/retirements. The unmodified base positively reproduces direct acceptance for omitted/null/self; the candidate refuses that capability. Check direct-call and real HTTP paths. |
| O02 | Omitted and literal-false confirmation retain capture-only behavior and ordinary diagnostics, irrespective of reviewer hint; true cannot accept. Malformed confirmation still gets pre-transaction 422 and actor mismatch retains 403 precedence. Raw body and digest stay unchanged. Do not substitute another class's confirmation controls for observation coverage. |
| O03 | Continue the same captured observation: self and distinct queued acceptance cannot consume it; both leave zero REVIEW edges and accepted outputs. A distinct authorized rejection still appends exactly one REJECTED decision/edge, changes derived disposition without editing claimState, and rejects duplicate review. Self-rejection remains refused. |
| O04 | Missing/invalid evidence, authority, requested target, subject, scope, rationale, bundle and already-decided target retain the earlier governing refusals and create no accepted truth. Valid observation creation without REVIEW_ACCEPT still permits inert capture; granting REVIEW_ACCEPT cannot bypass O01/O03. |
| O05 | Valid observation correction, direct or previously queued, never emits successor/accepted review/retirement or changes the old accepted/disputed predecessor. Earlier provenance/compatibility refusals remain meaningful. Operation, bounded structure and independently reviewed compliance keep their acceptance/contest/correction positive controls. |
| O06 | In one retained disposable database, unmodified base HTTP creates fictional direct and queued accepted observations, pending observation/correction targets and history. Candidate matching historical keys reuse exact old references with no new accepted objects/edges; fresh keys cannot accept. Old accepted observations remain readable/contestable, old pending targets cannot newly accept, and old raw record bytes remain unchanged. |
| O07 | No new authority, state, contract, transaction owner or production route. All emitted records remain reachable; refusal/rollback/replay preserve atomicity and accepted-state non-effects. Production closure, mandatory package/architecture checks, pinned full inventory, fresh exact-head review, two hosted baselines and publication receipt are required implementation evidence. |

The implementation tests must distinguish the public request outcome, immutable
claimState, derived review disposition and emitted authority/lineage records.
For accepted-history controls, run unmodified base bytes against the same
retained disposable database before candidate bytes. Do not create fake past
acceptances by changing candidate guards, disabling protection, monkeypatching
emitters or inserting hand-claimed accepted results.

Expected areas are `kernel/stages.py`, a focused observation eligibility test
module, observation expectations/fixtures in `test_review_fixes.py` and
`test_correction_authorization.py`, affected conformance/review tests,
one small test-local retained-history fixture/base-phase driver (expected
`kernel/tests/observation_history.py`, shared with O06),
`docs/REVIEW_DISPUTE_SEMANTICS.md`, this RFC and the generated test inventory.
The current H3 positive observation control must become a durable-evidence
capture control. Observation members of correction matrices must not simply
be removed: retain historical-target/cross-family negatives and assert the
new refusal while preserving other families' positive paths. Additions within
this boundary are explained in final scope; semantic expansion needs approval.

**Concrete mechanism for those retained negatives:** reuse O06's two-process
retained-database procedure for all six observation-predecessor rows, rather
than asking candidate `_original` to create a newly accepted observation.
The test-local fixture runs unmodified pinned base
`9d7541d96bc708e9270b986927d7f4b8a035454f` (tree
`63d532112ed7c705997d0d71f5f6d0fec12928f7`) in a separate process to create real
accepted predecessors through the legacy HTTP path, closes that process, then
opens the candidate on the same function-isolated disposable database. For
the stale-target C05 row, base also queues both corrections and accepts the
competing correction before candidate revalidation. The candidate must retain
the earlier `SUPERSEDED_RECORD_USED` refusal for the loser, not merely fail at
the new guard. The three cross-family rows and separate same-family/different-
subject row preserve their relationship refusal and absence of a new assertion;
the latter specifically keeps `CORRECTION_REQUIRED`. The rejection row retains
its lawful terminal rejection and unchanged predecessor. Other families keep
their existing candidate fixtures and positive paths. No row is dropped and
no raw accepted-record seeding or guard exception is granted.

The helper materializes the complete fixed base from local Git objects into
one owned temporary source tree per pytest session, authenticating its
commit/tree and executed source bytes. Hosted conformance already supplies
full history (`.github/workflows/conformance.yml`, checkout `fetch-depth: 0`);
missing local objects fail clearly, without a network fetch, skip or fallback.
Each affected case adds one base process and one owned isolated database,
using the pinned interpreter/dependencies and explicit per-database DSN.
The base process imports only that base runtime; its JSON output carries
scenario/actor/result references and snapshots, not a replacement writer.
Candidate connections open after base exits. Finally close all connections,
drop only the owned database and remove owned temporary outputs. This is
bounded test infrastructure shared with O06, not a checked-in old-runtime copy,
production service, workflow change or new publication boundary.

For historical queued-acceptance replay, preserve the complete normalized
governance submission through `POST /commit`, including its original generated
decision-time field. Calling `/review/accept` again generates a new time and
therefore a different source digest. Tenant, runtime-bundle and source-digest
matching remain mandatory; never weaken replay checks to reuse a key.

Before each commit run the mandatory package check with CPython 3.12.13, then
whitespace and relevant cheap checks. Run the focused real
PostgreSQL 17.10 tests and history probe, update inventory through the prescribed
maintenance command, and obtain an exact-head content review with zero Blockers.
Only then admit fresh hosted baselines and separate publication. Existing
PR #386 tests, reviews, admission and receipts are historical and cannot replace
new implementation evidence. No expensive baseline is requested for Phase A.

## Alternatives, excellence and approval limits

- **EXC-001:** one observation acceptance condition at the common pre-emission
  gate; existing validators remain owners of their distinct earlier decisions.
- **EXC-002:** no second policy table, authoritative state, durable flag or
  copied emitter; both paths consume the same eligibility decision.
- **EXC-003:** O01–O07 trace real entry points through stored effects, including
  omitted/false, independent reviewer, correction and retained-history controls.
- **EXC-004:** retire the positive claim that current observation acceptance is
  permitted; retain historical/type maps that still serve validation and reads.
- **EXC-005:** no runtime abstraction is proposed; two guarded emissions justify
  one direct condition. The bounded test fixture has existing consumers in
  O06 and the retained correction negatives, not a hypothetical future use.
- **EXC-006:** routing only self-review to a distinct actor is fewer changed
  paths but conflicts with #179. Deleting map entries skips material evidence/
  subject checks; a full allowlist/matrix redesign belongs to #179. Blocking
  all governance acts on observations would wrongly remove rejection/contest.

This is provisional pre-deployment maintenance. Removing the guard requires a
new explicit decision supported by typed observation semantics and corresponding
acceptance evidence; an arbitrary later payload or reviewer grant cannot open
the path. Phase A is acceptable because it reduces unsupported accepted force
while preserving captures and history. An invariant failure or unavoidable
change to another authority boundary requires redesign before implementation.

Capability, effects/non-effects, authority, O01–O07, historical treatment or
named-PR changes require a new version and exact same-task approval. Generic
“go,” earlier approvals, review findings and GitHub activity do not authorize
this runtime change. Final merge remains a separate later exact-head stop.

Next: obtain exact-head content review, then fresh hosted evidence and
publication before presenting the separate final merge packet.
