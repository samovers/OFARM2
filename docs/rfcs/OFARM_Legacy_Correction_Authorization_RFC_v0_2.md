# Legacy correction authorization, version 2

Status: version-2 semantic approval received; implementation written for draft
PR #380, with verification and exact-head content review pending. No merge or
deployment authorization.
Decision: `OFARM2-LEGACY-CORRECTION-AUTHORIZATION-001`, version 2.
Primary trust boundary: semantic promotion and supersession authorization.
Delivery: #379. Named draft PR: #380.

This proposal replaces the unapproved version 1. Its decision card and earlier
ready assessment are withdrawn. Later review identified that refusing all
observation and compliance corrections would remove the D21 resolution path
for their existing disputes. Version 2 preserves those compatible corrections;
CONTEST admission remains unchanged. The prior proposal and reviews remain in
Git and PR history; no implementation or approval is carried forward.

## Problem and independently reviewable outcome

Audit K-02 remains reproducible at merged OFARM2
`ff092c414db9fa24dbd6ab86c7722db89e0c95b5`. An operation-only author with
`ASSERT_OPERATION_CLAIM` and `REVIEW_ACCEPT`, but no `ASSERT_STRUCTURE` or
`REVIEW_SUPERSEDE`, can replace accepted structural state through legacy
`/commit`, either directly or after `/review/accept`. The result is HTTP 200,
`PROMOTE_ACCEPTED`, and an `EXECUTION_CONFIRMED` consequence superseding a
`STATE_CHANGE_ACCEPTED` consequence. Complete trace reachability does not
prevent the wrong transition.

The lead independently reproduced both paths using the real legacy HTTP app,
pipeline and disposable PostgreSQL 17.10 database. Queuing alone did not retire
the target; later acceptance did. This is supplemental Darwin ARM64 / Python
3.12.13 / PostgreSQL ARM64 evidence, not the locked Linux baseline. The script
and JSON remain outside tracked source. Production governed endpoints are
intentionally closed; this is a legacy semantic defect, not a production HTTP
bypass. The original audit pins were OFARM2
`fcac9ba505226e7e2fa2ede0aedb7585721b1841` and canonical OFARM
`71ca724a8b6ec23f1655b086a6f549496d10a47f`. Unmerged PR #359 is excluded.

Deliver one complete legacy correction path that validates the replacement
relationship and separately authorizes the retirement effect, while preserving
same-family correction for all four currently promoting assertion classes.
The rule blocks cross-family and cross-subject retirement and protects exact
structural identity. It does not infer which of several same-subject operations,
observations or compliance claims describes the same real-world occurrence or
proposition: the author explicitly chooses the predecessor, and the reviewer
must authorize that retirement. Deferred operation identity remains D5. This is a
narrow prerequisite for Tracking Epic #180, under #167; it cannot close #180.
This durable note records the correction matrix and the distinction between
proposing a correction and retiring truth, which remain useful after closure.

## Sources and authority map

Canonical authority remains in OFARM. In the pinned canonical repository,
the Authority Action Matrix v0.1 assigns `REVIEW_SUPERSEDE` to govern/decide
over assertion, consequence and state scope: it changes what remains in
force. The Authority Policy Model sections 2.1–2.4 requires action-specific,
scoped, time-bound, revocation-aware evaluation. Constitution sections
7.10–7.13 and 10.1/10.8/10.9/10.14 require mediated authority and immutable,
governed correction history. The Identity and Lifecycle RFC requires durable
identity continuity. These sources outrank this package's decisions.

Implementation D17/D18 preserve bounded structural self-acceptance and require
the same identity's explicit current predecessor. D5 defers operation identity.
D20/D21 preserve rejection, contest and the deferred standalone supersede verb.
`docs/REVIEW_DISPUTE_SEMANTICS.md` describes these accepted behaviors.
In particular, D21 permits a contest on an in-force accepted consequence and
resolves it through a governed superseding correction. Observation and
compliance are already accepted producers in the legacy pipeline, so their
same-family resolution paths must survive. Restricting CONTEST instead would
change a distinct permission and leave already-open disputes unresolved.

| Owner | Authority retained or exercised |
| --- | --- |
| Canonical OFARM | Meaning of action classes, governed truth and identity continuity |
| Existing authority evaluator and grant records | Evaluate the acting principal's existing action permissions at the existing farm scope; no new grant or scope semantics |
| Correction validation and promotion gates | Enforce this closed relationship before intent, recheck it at acceptance, and require the actual reviewer's supersession permission before retirement |
| Existing store transaction | Atomic records, edges, receipts, materialization and result; existing participating-writer serialization |
| Task user | Semantic approval for the named PR, later exact-head final acceptance |
| Reviewers / CI / GitHub | Content findings / mechanical evidence / native PR state, respectively; none supplies human approval |

An inert queued intent does not retire truth. Its author needs the ordinary
assertion permission and a valid relationship, not the future reviewer's
`REVIEW_SUPERSEDE`. Actual acceptance requires both `REVIEW_ACCEPT` and
`REVIEW_SUPERSEDE` from the transport-bound acting reviewer. A body-named party
cannot lend either permission. This additional effect check does not enable
the standalone `REVIEW_SUPERSEDE` governance request verb.

## Protected assets and threat model

Protect which accepted consequence remains in force, immutable lineage,
corrected materialization basis and accountable authorization receipts.
Trust the current store isolation and transaction owners, accepted runtime
bundle, immutable stored records, ordinary ingress principal binding and
existing authority evaluator. Treat submission references, class, subject,
payload, reviewer name and persisted correction intent as data requiring
validation. An authenticated legacy participant may possess assertion and
acceptance rights without supersession rights and may replay, race or choose
another same-farm target. Exclude database-owner compromise, arbitrary store
writes and compromised code or keys. Corrupt graph fixtures test refusal; they
do not imply an ordinary caller can write raw graph edges.

Primary risk: confusing permission to assert or accept one claim with
permission to retire another class or identity. Containment: one closed
relationship check plus the independent retirement action, inside the existing
governed transaction and before any successor or retirement edge is emitted.

## Closed relationship and invariant matrix

This bounded implementation matrix is a package decision, not new canonical
law. No supported correction is inferred from consequence type alone.

| ID | Required behavior | Focused negative and positive evidence |
| --- | --- | --- |
| C01 | A supplied supersession reference must be a nonempty string naming a visible accepted consequence on this farm, with stored IN_FORCE state and no superseding edge | Missing, malformed, wrong-kind, cross-farm/tenant, already superseded; valid explicit predecessor |
| C02 | Structure can replace only structure producing STATE_CHANGE_ACCEPTED for the same exact typed identityRecordRef, naming its sole current structural consequence under D18 | Original operation-to-structure attack, observation masquerading as structure, different identity/type, ambiguous current structure; lawful same-identity revision |
| C03 | Nonstructural correction requires the exact same supported source assertion family, its expected consequence type, exact same subjectType and subjectRef, and explicit current predecessor: OPERATION_CLAIM_ASSERTION → EXECUTION_CONFIRMED; OBSERVATION_ASSERTION → STATE_CHANGE_ACCEPTED; COMPLIANCE_ASSERTION → COMPLIANCE_STATUS_ACCEPTED | Cross-family and cross-subject refusals even with full authority; lawful same-family correction for each class and repeated correction chains |
| C04 | The source facts used for C02/C03 must resolve with exact kinds, agreeing scalar references and unique required graph edges | Missing/multiple/wrong-kind source, review or structure payload; direct and previously queued accepted origins both work |
| C05 | Validate relationship before recording intent; queued acceptance revalidates persisted intent and current predecessor, never accepts a new review-body target | Poisoned or multiple intent edges, target superseded while queued; author without retirement permission can queue a valid correction |
| C06 | Actual retirement requires current acting reviewer REVIEW_ACCEPT and REVIEW_SUPERSEDE using existing scope/time/revocation and human/agent evaluation; only exact ALLOW authorizes emission, with durable authority evidence | Compatible targets with missing/expired/revoked retirement grant, forged body reviewer, author's grant reused by reviewer, SOFTWARE_AGENT or declared acting agent, every non-ALLOW outcome; permitted human reviewer succeeds |
| C07 | A refusing correction emits no successor, successful acceptance review or retirement edge; accepted correction preserves old bytes, emits one successor and one trace, and keeps existing invalidation/replay behavior | Denial, rejection, duplicate retry, rollback before completion; successful direct/queued lineage and dispute-derived CORRECTED |
| C08 | Existing participating writers on separate connections serialize competing corrections; later acceptance sees the committed predecessor and grant state | Two independent Stores with separate connections compete for one predecessor; exactly one succeeds; revocation committed before admission is observed; no claim of same-app concurrent request isolation |
| C09 | Keep production closure, standalone supersede refusal, CORRECTION carrier refusal and the current queued-assertion RuntimeBundle gate | Production governed route refusal; unsupported verb/carrier; changed-bundle queued acceptance refuses while new correction of old accepted history remains possible |
| C10 | Every currently supported emitted assertion family retains its lawful acceptance → contest → compatible same-family correction path under existing review/evidence rules and the new retirement authority; CONTEST and REJECT admission remain unchanged | Structure, operation, observation and compliance: open dispute, queue correction while predecessor remains in force, accept with required authority, verify supersession and derived resolution; missing retirement authority preserves the disputed predecessor |

For C03, same subject is deliberately bounded compatibility, not proof of a
unique operation or claim identity. Ordinary supported OPERATION_CLAIM carriers remain
the input; do not activate `recordClass=CORRECTION` or require a new correction
carrier field. Within correction proof only, the claim, accepted consequence
and carried operation subject must agree; disagreement cannot establish the
relationship. For persisted compliance proof, resolve exactly one
COMPLIANCE_CLAIM edge from the resolved event to an ofarm.complianceclaim.v0.1
carrier with agreeing sourceEventRef and farm anchor. Its subjectScopeRef must
agree with the claim/consequence subject, including the resolved identity type.
An initial incoming correction uses its submitted complianceClaim, which must
pass the existing validators and this subject comparison before intent or
promotion; it has no durable carrier yet. Apply the persisted proof to the old
accepted predecessor and to a queued correction at acceptance. Preserve
the existing structured compliance and evidence validators; do not introduce
governing-rule-set equality, a new claim identity, or new self-review rights.
Observation remains the existing typed assertion with its durable evidence;
do not invent an observation carrier. General semantic graph repair remains
#184. Cross-subject corrections require separate future design; this slice
refuses them.

No correction relationship is supported here for advisory, hypothesis, note,
evidence or arbitrary governance submissions.
An explicit supersession pointer on those classes refuses. A governance
acceptance uses only the queued assertion's validated intent; it cannot supply
a replacement target. Omitted supersession retains existing non-correction
behavior, including D18's requirement on existing structural identity.
The closed set follows the four existing emitting assertion families, not
every consequence enum. C10 preserves their real dispute-resolution consumers;
it does not add a second registry or narrow the independent CONTEST action.

## One owned decision path

Extend the existing correction validator with one shared resolver/check used
by submission validation and queued acceptance. Resolve an old consequence's
`acceptedByReviewDecisionRef` to an exact accepting ReviewDecision
(`ASSERTION_RECORD`, `REVIEW_ACCEPT`, `ACCEPTED`), then its
`reviewedArtifactRef` to the exact AssertionRecord. Resolve exactly one
assertion `EVENT_SOURCE` matching the consequence's `sourceEventRef`; verify
the event kind. For structure, resolve exactly one typed `STRUCTURE_PAYLOAD`
and its identity. Verify the related graph edges consumed by this proof agree
with the named records. Never select the first of several candidates.

An accepted queued assertion remains immutable PENDING_REVIEW, so its stored
claim state is not a reason to reject legitimate accepted provenance. Do not
require optional `resultingAcceptedConsequenceRefs`, which current emitters do
not populate. Accepted history remains tenant-visible across runtime bundle
changes. Do not require an old accepted predecessor to use the current bundle;
retain the existing current-bundle requirement on a queued assertion now being
accepted.

Keep only the checked predecessor reference and needed original event in the
existing GateContext as transient stage products. Pending, direct and queued
emitters consume that checked result; remove their owned raw-pointer and
first-intent selection. A small shared retirement-authorization operation
serves both accepting paths, records the existing authority decision receipts
and binds their references into the gate trace. It runs after ordinary review
admission and immediately before emission. Call the existing evaluator with
action_class REVIEW_SUPERSEDE, action_stage PROMOTION, the transport-bound
acting party, current farm scope, submission actingAgentRef and aiAssistance,
and current revocation checking. Require decision.allowed (exact ALLOW), not
merely an outcome other than DENY. Preserve the evaluator's existing semantics:
SOFTWARE_AGENT or a declared acting agent invokes its non-human guard;
aiAssistance metadata alone is not an invented actor classification. Do not
change the earlier authority or review policies. Do not create a second action
matrix, transition registry, durable correction record, cache or query layer.

Keep REVIEW_SUPERSEDE absent from the standalone review-verb selector. Register
the exercised action in the existing non-commit action inventory, and
regenerate only owned manifest artifacts that actually change. Fictional
positive test actors receive explicit NO_INHERIT review grants. Do not add the
right to broad descendant-scope grants or give any real actor new authority.
Inventory and manifest checks prove declaration/vocabulary consistency only.
Direct and queued behavioral allow/refusal tests and action-specific receipts
prove actual mediation. Correct the affected inventory-grounding comments;
do not replace behavioral proof with a source-shape or call-site search test.

## Ordering, failure and limits

The existing legacy GatePipeline takes its serialized transaction before
authority and semantic reads. For participating writers on separate connections
sharing that lock at READ COMMITTED, an earlier committed correction or revocation is visible to
the later admission. Queued capture records inert intent; acceptance checks
current state and permissions, emits lineage, invalidates materializations,
writes trace and result, then commits atomically. Rejection abandons intent
without retiring the predecessor. A transaction exception rolls back the new
writes. Idempotent replay returns the existing result without another effect.
These statements assume exclusive ownership of the transaction's connection.
The legacy HTTP app shares a Store/connection across handlers; its advisory
lock does not supply request-level exclusion on that same connection.
Overlapping transaction contexts can share a transaction or nested savepoints.
Separate-Store evidence therefore does not prove isolation or independently
committed responses for concurrent requests to one app. Exclusive request
transaction ownership is a separate database/runtime Follow-up under #180;
this correction design neither fixes it nor claims same-app concurrency safety.

Preserve that transaction mechanism. It is a convention among participating
writers, not universal serializability: the legacy lock derives from the demo
tenant configuration; plain transactions and direct SQL do not participate;
there is no continuous permission recheck through commit or new lock deadline.
Do not promise that revocation ordered after admission cancels an in-flight
act. Distributed transaction/lifecycle redesign and arbitrary-writer races
remain #180 and their owning database Delivery. Stop for separate prerequisite
work if this slice cannot uphold its narrower ordering without changing that
boundary. No migration or durability change is proposed; rollback of deployed
code is not authorized by this pre-deployment decision.

## Complete vertical slice and simplicity

Expected areas: `kernel/validators.py`, `kernel/stages.py`,
`kernel/emission.py`, `kernel/policy.py`; focused existing semantic tests;
fictional profile fixtures; this note and review semantics documentation; the
owned generated capability manifest if its action inventory drifts; affected
inventory-grounding comments in `kernel/manifest.py`; and
`conformance/review_baseline_test_inventory.json` after test collection changes.
Expected paths are scope predictions under AGENTS.md, not a closed approval
list. These mechanical companions verify the same correction capability.
No frozen snapshot, contract schema, production route, storage role, migration,
credential, signing, audit or runtime-activation change belongs here.
K-03 confirmation typing and K-04 self-review eligibility remain separate.

EXC-001/002: one compatibility decision and checked target replace parallel
unchecked interpretation. EXC-003: C01–C10 trace to the resolver, retirement
gate and focused tests. EXC-004: remove the raw target and first-intent paths
owned by this capability, without broad unrelated cleanup. EXC-005: a helper
earns its place by serving direct and queued consumers now. EXC-006: adding
only REVIEW_SUPERSEDE is simpler but still permits cross-family, cross-subject
or wrong-structural-identity retirement; adding only class equality omits
authority and the within-family relationship. Same-subject nonstructural claims
remain distinguishable only by their explicit predecessor, not an inferred
operation/claim identity. Disabling correction families would remove accepted
D21 dispute-resolution consumers. No arbitrary line-count or new
architecture-checker exception is needed. Existing numerical module/function/
test budgets do not cover these legacy semantic files; applicable dependency
and isolation checks still apply. Exact-head content review and the final
change report assess EXC-001–006 directly.

The rule is not a temporary adapter. The broader legacy execution environment
is pre-deployment and not production-ready. A future accepted operation
identity/lifecycle design or a required cross-subject correction would require
a new decision rather than loosening this matrix silently.

## Verification and approval

Version-2 Phase A reached zero design Blockers. The complete card naming draft
PR #380 was followed by the exact user approval in Codex task
`01a07cc8-4157-7b33-a0ca-becb772e0e8b` on 2026-09-07. That same-task approval
authorizes implementation within this decision; it does not authorize merge or
deployment. The shared relationship check, checked transient emitter inputs,
and retirement authorization operation are now written. Their implementation
evidence and exact-head content review remain pending.

Verification requires adversarial and lawful-control tests for C01–C10 using the
real legacy HTTP/pipeline/store, plus focused malformed-provenance probes,
existing correction/dispute/replay/rollback tests and production-closure
regressions. For C10, use the ordinary distinct-reviewer path for observation
and compliance, preserving evidence and self-review rules. Check dispute
resolution through stored lineage and the existing derived dispute evaluator;
only assert output qualification/freeze effects when the target is in that
output's actual basis. A test that inserts a class into a generic enum or opens
no real dispute is not a preservation control. Isolate compatibility-negative
tests with otherwise sufficient authority from authority-negative tests using
compatible targets. Test separate-store competing corrections with explicit ordering;
label in-memory/source probes and non-baseline environments honestly. Run the
mandatory package contract check before every commit, owned manifest checks,
Ruff and applicable architecture checks. After test collection changes, run
`python conformance/run_review_baseline.py update-inventory` with repository
Python 3.12.13 and locked dependencies. This regenerates collected nodeids,
count and digest; never hand-edit it or treat collection as passing execution.

Also run `python conformance/ofarm_profile_extraction_consistency_check.py`
to report relevant extraction evidence honestly. At the reviewed version-1
head it exits 1 with two existing missing-review-record failures for
`conformance/review_baseline_test_inventory.json` and
`kernel/tests/test_rewrite_architecture_check.py` in the SI extraction audit
records. All relevant inputs and scanned paths match the merged base; this is
not a newly executed base run or a regression caused by the RFC. Preserve the
failure report and diagnose any change. Do not substitute "no new failures"
for a required PASS or waive an applicable gate. The check is required when
extraction-inventory consistency records change; profile-leakage checks remain
required where applicable. Keep broader extraction-record repair separate
unless concrete in-boundary proof requires it.

Then obtain exact-head content review
with zero Blockers before admitting the locked Linux x86_64 / Python 3.12.13 /
PostgreSQL 17.10 three-cluster baseline, prescribed two-run comparison, native
verification and publication receipt. No expensive baseline is requested for
this Phase A-only head. Preserve existing gates and final exact-head human
merge authorization. These actions grant no release, deployment, current or
default promotion, production access or security waiver.

Next: complete isolated C01–C10 execution and cheap checks, resolve any in-boundary
failures, and obtain zero-Blocker exact-head content review before baseline
admission. Preserve the later final-packet and exact-head merge-authorization stop.
