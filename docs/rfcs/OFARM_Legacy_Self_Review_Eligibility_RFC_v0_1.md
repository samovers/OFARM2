# Legacy compliance self-review eligibility

Status: **proposed Phase A; implementation is not approved**.
Decision: `OFARM2-LEGACY-SELF-REVIEW-ELIGIBILITY-001`, version 1.
Delivery: [#385](https://github.com/samovers/OFARM2/issues/385), under Tracking
Epic #180. The later live decision card must name the already-created draft PR.
This document supplies neither semantic approval nor merge authority.

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
accepted-force decision. It enforces the existing D8 restriction; it creates
no new review rights, reviewer identity, contract or production capability.
General reviewer-field typing and wider direct-versus-queued consistency are
separate work. The bounded D17 structure policy stays unchanged.

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

## Smallest proposed correction and ordering

In the existing compliance condition in `ReviewPromotionGate.run`, remove the
comparison to `reviewerPartyRef`. The proposed eligibility condition is simply
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
Store snapshots establish durable effects; they do not prove read-only lookup
counts or pre-transaction ordering. This repair is intentionally after ingress,
so it introduces no transaction-free failure contract.

Start with six new collected cases: one HTTP null-origin queue lifecycle,
four public-pipeline reviewer controls, and one pending-null replay/digest
conflict case. This is a scope prediction, not a fixed test-count requirement.
Reuse `test_review_confirmation.py` for ordinary confirmation, operation,
bounded-structure and authority/evidence controls; `test_m2_review.py` for
reject/contest; and `test_correction_authorization.py` and
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

Expected areas are `kernel/stages.py`, focused files under `kernel/tests/`,
`docs/REVIEW_DISPUTE_SEMANTICS.md`, this RFC and the prescribed generated test
inventory if collection changes. After approval, the active semantics will
state the bounded repair and historical limit; the original PR #384 decision
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
small correction into independent class and queue policy decisions.

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

Next: review this proposal in its existing draft PR, resolve demonstrated
design Blockers, then present the complete same-task decision card for exact
user approval before any implementation.
