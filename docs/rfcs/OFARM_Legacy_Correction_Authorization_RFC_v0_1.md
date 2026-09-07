# Legacy correction authorization, version 1

Status: proposed Phase A; no semantic approval or implementation yet.
Decision: `OFARM2-LEGACY-CORRECTION-AUTHORIZATION-001`, version 1.
Primary trust boundary: semantic promotion and supersession authorization.

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
relationship and separately authorizes the retirement effect. This is a
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
| C03 | Operation can replace only OPERATION_CLAIM_ASSERTION producing EXECUTION_CONFIRMED, with the exact same subjectType and subjectRef and explicit current predecessor | Cross-family and cross-subject attacks; same-subject correction and repeated correction chain |
| C04 | The source facts used for C02/C03 must resolve with exact kinds, agreeing scalar references and unique required graph edges | Missing/multiple/wrong-kind source, review or structure payload; direct and previously queued accepted origins both work |
| C05 | Validate relationship before recording intent; queued acceptance revalidates persisted intent and current predecessor, never accepts a new review-body target | Poisoned or multiple intent edges, target superseded while queued; author without retirement permission can queue a valid correction |
| C06 | Actual retirement requires current acting reviewer REVIEW_ACCEPT and REVIEW_SUPERSEDE using existing scope/time/revocation evaluation, with durable authority evidence | Missing/expired/revoked retirement grant, forged body reviewer, author's grant reused by reviewer; explicit permitted reviewer succeeds |
| C07 | A refusing correction emits no successor, successful acceptance review or retirement edge; accepted correction preserves old bytes, emits one successor and one trace, and keeps existing invalidation/replay behavior | Denial, rejection, duplicate retry, rollback before completion; successful direct/queued lineage and dispute-derived CORRECTED |
| C08 | Existing participating writers serialize competing corrections; later acceptance sees the committed predecessor and grant state | Two independent Stores compete for one predecessor; exactly one succeeds; revocation committed before admission is observed |
| C09 | Keep production closure, standalone supersede refusal, CORRECTION carrier refusal and the current queued-assertion RuntimeBundle gate | Production governed route refusal; unsupported verb/carrier; changed-bundle queued acceptance refuses while new correction of old accepted history remains possible |

For C03, same subject is deliberately bounded compatibility, not proof of a
unique operation identity. Ordinary supported OPERATION_CLAIM carriers remain
the input; do not activate `recordClass=CORRECTION` or require a new correction
carrier field. Within correction proof only, the claim, accepted consequence
and carried operation subject must agree; disagreement cannot establish the
relationship. General semantic graph repair remains #184. Cross-subject
corrections require separate future design; this slice refuses them.

No correction relationship is supported here for observation, compliance,
advisory, hypothesis, note, evidence or arbitrary governance submissions.
An explicit supersession pointer on those classes refuses. A governance
acceptance uses only the queued assertion's validated intent; it cannot supply
a replacement target. Omitted supersession retains existing non-correction
behavior, including D18's requirement on existing structural identity.

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
admission and immediately before emission. Do not create a second action
matrix, transition registry, durable correction record, cache or query layer.

Keep REVIEW_SUPERSEDE absent from the standalone review-verb selector. Register
the exercised action in the existing non-commit action inventory, and
regenerate only owned manifest artifacts that actually change. Fictional
positive test actors receive explicit NO_INHERIT review grants. Do not add the
right to broad descendant-scope grants or give any real actor new authority.

## Ordering, failure and limits

The existing legacy GatePipeline takes its serialized transaction before
authority and semantic reads. For participating writers sharing that lock at
READ COMMITTED, an earlier committed correction or revocation is visible to
the later admission. Queued capture records inert intent; acceptance checks
current state and permissions, emits lineage, invalidates materializations,
writes trace and result, then commits atomically. Rejection abandons intent
without retiring the predecessor. A transaction exception rolls back the new
writes. Idempotent replay returns the existing result without another effect.

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
owned generated capability manifest if its action inventory drifts.
No frozen snapshot, contract schema, production route, storage role, migration,
credential, signing, audit or runtime-activation change belongs here.
K-03 confirmation typing and K-04 self-review eligibility remain separate.

EXC-001/002: one compatibility decision and checked target replace parallel
unchecked interpretation. EXC-003: C01–C09 trace to the resolver, retirement
gate and focused tests. EXC-004: remove the raw target and first-intent paths
owned by this capability, without broad unrelated cleanup. EXC-005: a helper
earns its place by serving direct and queued consumers now. EXC-006: adding
only REVIEW_SUPERSEDE is simpler but still lets a permitted reviewer retire an
unrelated class or identity; adding only class equality omits authority and
confuses observation with structure. Disabling every correction would remove
the accepted D18 and dispute-resolution consumers. No arbitrary line-count or
new architecture-checker exception is needed.

The rule is not a temporary adapter. The broader legacy execution environment
is pre-deployment and not production-ready. A future accepted operation
identity/lifecycle design or a required cross-subject correction would require
a new decision rather than loosening this matrix silently.

## Verification and approval

Phase A review must reach zero Blockers before the complete decision card
names the existing draft PR. The later exact same-task user approval authorizes
implementation in that PR. There is no approval yet.

After approval: add adversarial and lawful-control tests for C01–C09 using the
real legacy HTTP/pipeline/store, plus focused malformed-provenance probes,
existing correction/dispute/replay/rollback tests and production-closure
regressions. Test separate-store competing corrections with explicit ordering;
label in-memory/source probes and non-baseline environments honestly. Run the
mandatory package contract check before every commit, owned manifest checks,
Ruff and applicable architecture checks. Then obtain exact-head content review
with zero Blockers before admitting the locked Linux x86_64 / Python 3.12.13 /
PostgreSQL 17.10 three-cluster baseline, prescribed two-run comparison, native
verification and publication receipt. No expensive baseline is requested for
this Phase A-only head. Preserve existing gates and final exact-head human
merge authorization. These actions grant no release, deployment, current or
default promotion, production access or security waiver.

Next: publish and independently review the draft Phase A, then present the
complete decision card before implementation.
