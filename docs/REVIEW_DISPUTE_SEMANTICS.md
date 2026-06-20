# Review / dispute state-transition semantics

**Status:** G5-1 (REJECT) settled · G5-3 (CONTEST) deferred — see §6.
**Scope:** generic Core/Platform review-verb semantics only. No Slovenia
specifics (those ride a profile through the generic mechanism — M2 brief
mechanism-boundary rule). **This is a candidate package decision (DECISIONS.md
D20), not OFARM law**; it changes no contract and promotes nothing. Claim limit
is unchanged: record-keeping completeness, never current-compliance or
certification.

M1 shipped the acceptance verb only (`REVIEW_ACCEPT`). This document specifies
the **REJECT** verb's exact state effects so G5-2 implements settled semantics,
not an "obvious default." Every effect — on the queued assertion, its
`PromotionTrace`, any materialization, and future acceptance — is named below.

---

## 1. Grounding: how acceptance works today (so REJECT stays symmetric)

A queued claim is an `AssertionRecord` (`ofarm.assertionrecord.v0.1`) emitted
with `claimState = "PENDING_REVIEW"` (`kernel/emission.py:157-159`,
`emit_pending_assertion`). Acceptance is the reviewer's **own** governed
`GOVERNANCE_DECISION` commit. It **never edits the queued assertion**; it
**appends** new records (`kernel/emission.py:238-313`, `emit_queue_acceptance`):

- a `ReviewDecision` (`ofarm.reviewdecision.v0.1`) — `reviewAction =
  "REVIEW_ACCEPT"`, `decisionOutcomeState = "ACCEPTED"`, `reviewedArtifactRef`
  = the queued assertion, reviewer rationale in `notes` (prefixed
  `"resolution: "`), optional `evidenceRefs`;
- an `AcceptedEventConsequence` (`inForceState = "IN_FORCE"`), linked
  `acceptedByReviewDecisionRef`;
- a `REVIEW` edge **assertion → reviewDecision**.

**The disposition is derived, not stored.** The accepted assertion keeps
`claimState = "PENDING_REVIEW"` in its immutable record; "decided" is derived
from the presence of a `REVIEW` edge, and "in force" from the
`AcceptedEventConsequence`. `kernel/views.py:103-105` filters the pending queue
by exactly this rule: *skip any assertion that already has a `REVIEW` edge*,
then keep `claimState ∈ {PENDING_REVIEW, CONTESTED}`.

### Frozen contract vocabulary already supports REJECT (no contract change)

The shipped contracts anticipated the reject/contest verbs — REJECT invents
nothing:

| Contract field | Enum (verbatim) | Source |
|---|---|---|
| `AssertionRecord.claimState` | `PENDING_REVIEW, IN_FORCE, CONTESTED, REJECTED, SUPERSEDED` | `OFARM_AssertionRecord_schema_v0_1.json:136-143` |
| `ReviewDecision.reviewAction` | `REVIEW_ACCEPT, REVIEW_REJECT_OR_CONTEST, REVIEW_SUPERSEDE, REVIEW_REQUEST` | `OFARM_ReviewDecision_schema_v0_1.json:41-47` |
| `ReviewDecision.decisionOutcomeState` | `ACCEPTED, REJECTED, CONTESTED, SUPERSEDED, REVIEW_REQUESTED` | `OFARM_ReviewDecision_schema_v0_1.json:89-96` |
| `PromotionTrace.finalOutcome` / `CommitIngressResult.decisionOutcome` | `RETAIN_DRAFT, REQUIRE_REVIEW, PROMOTE_ACCEPTED, DENY, REPLAY_REUSED_RESULT` | `OFARM_PromotionTrace_schema_v0_1.json:123-129`; `OFARM_CommitIngressResult_schema_v0_1.json` |

REJECT and CONTEST **share one action** (`REVIEW_REJECT_OR_CONTEST`) and split
on the **outcome state** (`REJECTED` vs `CONTESTED`). The commit-level outcome
enum, by contrast, has **no rejection value** — see §3.6 / ERRATA E-005.

---

## 2. What a REJECT *is*

A REJECT is a reviewer's governed decision that a queued `PENDING_REVIEW`
assertion **will not be promoted** and is **terminally declined**. It is the
append-only mirror of acceptance: a new `ReviewDecision` records the decline; no
record is edited; no consequence is created. It is **not** a deletion, **not** a
correction of the claim, and **not** a re-openable pause.

---

## 3. Normative REJECT semantics (settled)

### 3.1 Trigger and surface

A REJECT is a `GOVERNANCE_DECISION` commit naming a target queued assertion
(`reviewTargetAssertionRef`, as acceptance does — `kernel/stages.py:213-214`)
and carrying the **reject action**. The emitted `ReviewDecision` has
`reviewAction = "REVIEW_REJECT_OR_CONTEST"` and `decisionOutcomeState =
"REJECTED"`.

**Recommended HTTP surface (G5-2 confirms):** generalize `/review/accept` into a
single `/review` decision surface carrying the review action (accept | reject),
sharing validation, authority, idempotency, the double-decide guard, and
`ReviewDecision` emission. A separate `/review/reject` endpoint is the minimal
alternative. The surface shape is a G5-2 implementation detail; the **state
effects in this section are binding** regardless of which surface is chosen.

**Ingress discriminator (no contract change).** The review verbs travel on
**kernel-internal submission fields** read by the gate chain — today
`reviewTargetAssertionRef`, `reviewRationale`, `reviewEvidenceRefs`,
`confirmAccept` (`kernel/stages.py:213, 455`; `kernel/api.py:188-190`). These are
**not `CommitIngressRequest` properties** — that contract is closed
(`additionalProperties: false`) and carries none of the review fields (verified);
the authoritative, contract-bound governance record is the emitted
`ReviewDecision`. Adding review-decision input fields is therefore **not a
contract change**, exactly as the existing review fields are not.

**The normalized review-decision input is a *pair*, because REJECT and CONTEST
share the `REVIEW_REJECT_OR_CONTEST` action and split on the outcome.** G5-2 adds
two kernel-internal fields, each a value of the same enum it becomes on the
emitted `ReviewDecision`:

- **`reviewAction`** ∈ `ReviewDecision.reviewAction` — selects the **authority
  action** (§3.2);
- **`decisionOutcomeState`** ∈ `ReviewDecision.decisionOutcomeState` — selects
  the **emission/outcome branch** within a shared action.

The IngressNormalizer normalizes and validates this pair **fail-closed**; a
present-but-invalid field **never falls through to accept**:

| `reviewAction` | `decisionOutcomeState` | Disposition |
|---|---|---|
| absent | (ignored) | normalize to `REVIEW_ACCEPT` / `ACCEPTED` ⇒ **accept** (legacy back-compat) |
| `REVIEW_ACCEPT` | absent or `ACCEPTED` | **accept** path |
| `REVIEW_ACCEPT` | any other value | **governed refusal** (action/outcome mismatch) |
| `REVIEW_REJECT_OR_CONTEST` | `REJECTED` | **reject** path (this ticket) |
| `REVIEW_REJECT_OR_CONTEST` | `CONTESTED` | **governed refusal until G5-3** (the contest emission path does not exist yet — never silently downgraded to a reject or an accept) |
| `REVIEW_REJECT_OR_CONTEST` | absent / any other | **governed refusal** (the shared action is ambiguous without a supported outcome) |
| `REVIEW_SUPERSEDE`, `REVIEW_REQUEST`, or any unrecognized/malformed value | (any) | **governed refusal** (not wired in G5) |

The refusal of an unrecognized/unwired **action** is principled default-deny
(Kernel rule 2): the verb resolves to **no authority action** in the
reviewAction-keyed selector (§3.2), so no grant can authorize it — the AUTHORITY
gate denies (`AUTHORITY_DENIED`, outcome `RETAIN_DRAFT`). The refusal of a
recognized-but-unimplemented or mismatched **outcome** (e.g. `CONTESTED`) is an
emission-branch default-deny: no path exists to emit it, so the commit refuses
rather than guess — never a silent accept or reject.

**Endpoint normalization.** If G5-2 ships a dedicated `/review/reject` endpoint
rather than a generic `/review`, the **endpoint itself supplies** the normalized
pair (`reviewAction = REVIEW_REJECT_OR_CONTEST`, `decisionOutcomeState =
REJECTED`) so clients never pass raw outcome values; a generic `/review` carries
both fields explicitly and the same matrix governs. Either way the pipeline sees
the normalized pair above.

### 3.2 Authority (distinct action — REVIEW_REJECT_OR_CONTEST)

REJECT is authorized by the **`REVIEW_REJECT_OR_CONTEST`** action class, a
distinct high-governance row in the Authority Action Matrix
(`reference/rfcs/OFARM_Authority_Action_Matrix_v0_1.md:18`, `NO_INHERIT by
default`, `human-only by default`). **Holding `REVIEW_ACCEPT` does not confer
it** — they are separate, non-inheriting grants. Default-deny if absent.

Today both authority touchpoints hardcode `REVIEW_ACCEPT`: the generic AUTHORITY
gate (`kernel/stages.py:229`, keyed only on commit class via
`policy.COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS`) and the review-specific check in
the ReviewPromotionGate (`kernel/stages.py:500`). **G5-2 requirement:** the
evaluated authority action must be selected by the *review action*
(accept → `REVIEW_ACCEPT`, reject → `REVIEW_REJECT_OR_CONTEST`) at **both**
touchpoints — generically (a table/selector keyed on the review action), never a
per-verb procedural branch and never a scheme/profile literal.

**Self-review note (not decided here):** D8/D17 grant a farmer self-*acceptance*
of bounded classes. Whether the self-review actor also holds
`REVIEW_REJECT_OR_CONTEST` is a **profile-grant** question (P5), out of scope for
G5-1. G5-2 reuses the *same* self-review/distinct-reviewer gate as acceptance
(`kernel/stages.py:497-507`); a self-reject of a class the actor may not
self-review routes to a distinct reviewer exactly as a self-accept would. No new
self-review surface is introduced.

### 3.3 Validation (rationale required, evidence optional)

REJECT inherits the target-**validity** guards acceptance applies, but **not**
its **promotion** guards — because a decline creates no consequence, the guards
that exist to make a *safe promotion* are irrelevant to it. Concretely:

- **Inherited (validity):** the target must **resolve** to a record of kind
  `AssertionRecord` (`kernel/validators.py:260-261`,
  `FAIL_REFERENCE_RESOLUTION` for a non-existent / wrong-kind ref), be
  **farm-contained** (`:267-271`, `SCOPE_NOT_AUTHORIZED` — no cross-farm
  rejection), have **`claimState == "PENDING_REVIEW"`** in its immutable record
  (`:272-275`), and carry **no prior `REVIEW` edge** (`:276-279`,
  `SUPERSEDED_RECORD_USED` "already reviewed"). A target already decided
  (accepted, rejected, or otherwise REVIEW-edged) is refused (§3.8).
- **Not inherited (promotion-only):** the `assertionType` →
  `ACCEPTANCE_BY_ASSERTION_TYPE` gate (`:280-283`, "has no acceptance path"), the
  D18 structure-supersession checks (`:301-317`), and the
  evidence-to-overcome-insufficiency rule. **REJECT applies to any
  `PENDING_REVIEW` `AssertionRecord` regardless of `assertionType`** — a reviewer
  may decline a queued claim that has no *acceptance* path, and may decline a
  queued structure correction whose supersession ref is stale (rejecting it
  retires nothing, so D18's "name the current consequence" guard does not apply).
- A REJECT **must carry a non-empty rejection rationale** in the **same
  submission field acceptance uses, `reviewRationale`** (gate-validated non-empty,
  `kernel/validators.py:330-334`; emission prefixes it `"rejection: "` vs
  acceptance's `"resolution: "`). A rejection with no stated reason is a silent
  denial, forbidden by Kernel rule 7 ("refusal is a feature … never silently
  pretends").
- Reviewer **evidence is optional** on a REJECT. This is deliberately *asymmetric
  with acceptance*: accepting a claim routed for a `NEEDS_EVIDENCE` reason
  (`kernel/policy.py:231-234`, `NEEDS_EVIDENCE_CODES`) requires **new** durable
  evidence to overcome the insufficiency; declining requires only a reason. A
  reviewer rejecting *because* evidence is missing should not have to supply
  evidence to say so. **But evidence that *is* supplied is validated exactly as
  acceptance validates it** (`kernel/validators.py:336-342`): every
  `reviewEvidenceRefs[]` member must resolve to a record of kind
  `ofarm.evidencerecord.v0.1`; an unresolved or wrong-kind ref **refuses the
  rejection** (`FAIL_REFERENCE_RESOLUTION`), and an `EVIDENCE` edge is emitted
  **only** for a validated ref. Optional means "may be omitted," never
  "accepted unchecked."
- An **`EvidenceSufficiencyCase`** stored when the claim was queued (if it was
  routed for a `NEEDS_EVIDENCE` reason — `kernel/emission.py:_store_case`) is
  **left unchanged** (append-only); the rejection is recorded solely in the
  `ReviewDecision`, never by amending the case. The case stays as the historical
  evidence-floor evaluation made at submission time.

### 3.4 Emission (append-only; no consequence)

The REJECT commit appends exactly one authoritative governance record plus its
edges, mirroring acceptance minus the consequence:

```jsonc
{
  "schemaVersion": "ofarm.reviewdecision.v0.1",
  "reviewDecisionId": "review:<minted>",
  "reviewedArtifactFamily": "ASSERTION_RECORD",
  "reviewedArtifactRef": "<the queued PENDING_REVIEW assertion>",
  "reviewAction": "REVIEW_REJECT_OR_CONTEST",
  "decisionOutcomeState": "REJECTED",
  "anchorScopes": [{ "scopeType": "FARM", "scopeRef": "<farm>" }],
  "decidedByPartyRef": "<reviewer transport principal>",
  "decidedAt": "<now>",
  "notes": "rejection: <non-empty rationale>"
  // optional: "evidenceRefs": [...]
  // NO resultingAcceptedConsequenceRefs — nothing is promoted
}
```

- a `REVIEW` edge **assertion → reviewDecision** (this is what flips the derived
  disposition and removes the claim from the pending queue);
- one `EVIDENCE` edge per optional `evidenceRefs` member (as acceptance does,
  `kernel/emission.py:265-266`);
- **no `AcceptedEventConsequence`**, **no `LINEAGE_SUPERSEDES`** (there is no
  in-force consequence to retire — the claim never reached force);
- **no resolution of any `LINEAGE_SUPERSEDES_INTENT` edge.** If the rejected
  claim was a queued *correction* carrying a supersession intent (recorded at
  capture, `kernel/emission.py:161-167`), that intent is **abandoned**: the prior
  in-force consequence it would have retired **stays in force** (the correction
  was declined), and the intent edge remains in history (append-only) but never
  takes effect. Supersession resolves only on acceptance
  (`kernel/emission.py:294-302`), never on a decline.

### 3.5 Effect on the queued assertion (terminal; derived)

The queued `AssertionRecord` is **never edited** (Kernel rule 1, append-only).
Its `claimState` field stays `PENDING_REVIEW` in the immutable record — exactly
as an accepted assertion's does. The **derived disposition becomes `REJECTED`**,
read from the latest `ReviewDecision` for that `reviewedArtifactRef`
(`decisionOutcomeState = "REJECTED"`, no consequence). Because the assertion now
carries a `REVIEW` edge, the existing pending-queue filter
(`kernel/views.py:103-104`) **already excludes it** — no view change is needed
for the claim to leave the queue. It never appears in force (no consequence). A
"rejected claims" derivation, if any is built, reads the `REVIEW_REJECT_OR_CONTEST`
/ `REJECTED` `ReviewDecision`.

### 3.6 PromotionTrace and commit outcome

A REJECT commit promotes nothing, so its commit-level outcome
(`PromotionTrace.finalOutcome` / `CommitIngressResult.decisionOutcome`) is
**`RETAIN_DRAFT`** — the existing value for "this governed commit promoted no
consequence." This reuses the established convention: the review stage already
returns `RETAIN_DRAFT` for non-promoting governance outcomes, including the
double-decide refusal "Target already reviewed" (`kernel/validators.py:277-280`)
and the no-review-act path (`kernel/stages.py:474, 492`). The
`CommitIngressResult` `allOf` adds required companions only for `PROMOTE_ACCEPTED`
(`inForceResultCategory` + `inForceArtifactRefs`) and `REPLAY_REUSED_RESULT`
(`replayOfRequestId`); `RETAIN_DRAFT` may lawfully carry
`emittedReviewDecisionRefs` (the `ReviewDecision`) with empty consequence refs.

**Caveat (ERRATA E-005):** the commit-outcome enum has **no terminal-rejection
value**. `RETAIN_DRAFT` here means **only** "no consequence promoted" — it is
**not** a claim that the target remains re-promotable. The authoritative,
unambiguous signal of a terminal decline is the `ReviewDecision`
(`decisionOutcomeState = "REJECTED"`) and the derived disposition, never
`finalOutcome` alone. The **target assertion's original queuing `PromotionTrace`**
(`finalOutcome = "REQUIRE_REVIEW"`, written when it was queued) is unchanged —
append-only; the REJECT is a separate commit with its own trace.

**Reachability / receipt (D3 — every authoritative record reachable from exactly
one `PromotionTrace`).** The rejection `ReviewDecision` is **not** a side record:
it flows through the *same generic receipt machinery* acceptance uses. G5-2's
`emit_queue_rejection` registers the decision in `ctx.emitted["reviews"]` (as
acceptance does, `kernel/emission.py:263`); the generic `PromotionTraceWriter`
(`kernel/emission.py:341-352`) then — with no rejection-specific code —
(a) lists it in `PromotionTrace.emittedReviewDecisionRefs`, (b) adds its
`PROMOTION_EMITS` reachability edge from the trace, and (c) returns it in the
`CommitIngressResult` (whose `promotionTraceRef` points at that trace). A G5-2
test must assert this path: the rejection `ReviewDecision` appears in the
result's `emittedReviewDecisionRefs`, in the trace, and carries its
`PROMOTION_EMITS` edge. (This is *why* the rejection must register in
`ctx.emitted["reviews"]` and not be inserted out-of-band.)

### 3.7 Effect on materialization (none)

**A REJECT touches no materialization.** The materialization basis is built
exclusively from **in-force `AcceptedEventConsequence`s**
(`kernel/materializer.py:169, 181`). A rejected assertion never produced a
consequence, so it was never a basis member; there is nothing to stale or
invalidate (D12 basis-set staleness has no member to flip). Current state
already excluded the queued claim and continues to. *(Contrast CONTEST/G5-3,
which disputes an **already in-force** consequence and therefore **does** stale
the dependent materializations — see §6.)*

### 3.8 Future acceptance and terminality

REJECT is **terminal for the target assertion**:

- Once a `REJECTED` `ReviewDecision` exists for the assertion, it carries a
  `REVIEW` edge, so **any subsequent review of the same target** — a later
  ACCEPT or a second REJECT — is refused by the **existing** double-decide guard
  (`kernel/validators.py:277-280`): outcome `RETAIN_DRAFT`, reason code
  **`SUPERSEDED_RECORD_USED`**, detail "Target already reviewed." This guard
  already fires on *any* prior `REVIEW` edge, so it covers reject-then-accept,
  reject-then-reject, and accept-then-reject with **no new code and no new
  reason code**.
- **The lawful way to pursue the claim after a rejection is a new capture** — a
  fresh `AssertionRecord` via a new commit, reviewed independently. This is the
  Kernel's universal correction discipline: "correction is supersession; …
  correction or dispute = new payload + supersession — never edits"
  (`KERNEL.md` rule 1; `CORE.md`). A rejected claim is never reopened in place.

### 3.9 Idempotency

Symmetric with acceptance. The review surface accepts an optional
`idempotencyKey` (auto-generated if absent, `kernel/api.py:159-162`); a genuine
replay of the *same* REJECT reuses the prior result via the existing idempotency
mechanism (`REPLAY_REUSED_RESULT`). A *different-key* second decision on an
already-decided target is not idempotency — it is caught by the §3.8 double-decide
guard. A **conflicting replay** (same `idempotencyKey`, different submission body)
is refused `DENY` / `IDEMPOTENCY_REPLAY_CONFLICT` by the existing idempotency gate,
exactly as for any commit — REJECT introduces no special idempotency behavior.

### 3.10 Explicit non-effects

A REJECT does **not**: edit or delete the queued assertion; emit an
`AcceptedEventConsequence`; create, stale, or invalidate any materialization;
supersede any in-force consequence (there is none); hide the assertion from
history (it stays reachable with its `REJECTED` decision); reopen on a corrected
re-submission (that is a new capture); or — in G5 — support reversing/overturning
the rejection (§3.11).

### 3.11 Out of scope for G5 (deferred, do not implement under this spec)

- **Reversing a wrongful rejection.** The contract permits a `ReviewDecision` to
  supersede a prior one (`ReviewDecision.supersedesReviewDecisionRef`,
  `ReviewDecision.reviewAction = "REVIEW_SUPERSEDE"`). A decision-reversal /
  overturn path is **not** part of G5-2; resurrecting a declined claim without a
  fresh capture is deliberately withheld to keep the verb bounded. If needed it
  is its own future ticket.
- **CONTEST / dispute** (§6, G5-3).
- **SI advisory/grant specifics** (whether a profile actor holds
  `REVIEW_REJECT_OR_CONTEST`) — P5.

---

## 4. Claim lifecycle (settled, after G5-2)

```
                         REVIEW_ACCEPT
                     ┌────────────────────► IN_FORCE (derived; consequence)   [terminal]
   PENDING_REVIEW ───┤
   (queued claim)    └────────────────────► REJECTED (derived; ReviewDecision) [terminal]
                         REVIEW_REJECT_OR_CONTEST / REJECTED

   any further review of a decided target ──► refused (RETAIN_DRAFT,
                                              SUPERSEDED_RECORD_USED, "already reviewed")
   pursue a rejected claim ─────────────────► NEW capture (new AssertionRecord)
```

`CONTESTED` / `SUPERSEDED` transitions are CONTEST/G5-3 and the deferred
reversal path; not introduced by G5-2.

---

## 5. Vocabulary discipline

- **No invented reason codes.** REJECT introduces none. The only `RuntimeProblem`
  reason code it relies on is `SUPERSEDED_RECORD_USED` (already used by the
  double-decide guard). A reviewer's decline is a **governance outcome**
  (`ReviewDecision.decisionOutcomeState = "REJECTED"`), not a `RuntimeProblem` —
  the registry intentionally pairs no rejection code (`kernel/problems.py`).
- **No invented contract values.** All enum values used
  (`REVIEW_REJECT_OR_CONTEST`, `REJECTED`, `RETAIN_DRAFT`) are shipped contract
  vocabulary (§1).
- The one recorded gap is the commit-outcome enum (E-005), worked around per §3.6
  without misreporting.

---

## 6. CONTEST / dispute — DEFERRED to G5-3

**Do not implement CONTEST under this spec.** G5-3 specifies it: which
`recordClass` is emitted, what becomes `disputeStatus`-flagged, which
materializations stale (the key REJECT/CONTEST difference — CONTEST disputes an
**already in-force** consequence, so unlike REJECT it **does** trigger D12
basis-set staling on the dependent materializations), and how supersession
resolves it. CONTEST reuses the same `REVIEW_REJECT_OR_CONTEST` action with
`decisionOutcomeState = "CONTESTED"` and the `AssertionRecord.claimState =
"CONTESTED"` lane that `kernel/views.py:105-107` already surfaces as `DISPUTED`.
Because REJECT and CONTEST share the action and split only on the
`decisionOutcomeState` half of the normalized input pair (§3.1), G5-1 already
pins the discriminator: until G5-3 wires the contest emission path, a
`REVIEW_REJECT_OR_CONTEST` + `CONTESTED` input is a **governed refusal** (§3.1
matrix), never silently handled as a reject. This section is a forward pointer
only.

---

## 7. G5-2 build list and acceptance checklist (derived from this spec)

**The concrete code touchpoints G5-2 must change** (all generic; no per-verb
procedural branch, no scheme/profile literal):

- `kernel/emission.py` — add `emit_queue_rejection()`, the mirror of
  `emit_queue_acceptance()` minus the consequence: emit the `ReviewDecision`
  (`REVIEW_REJECT_OR_CONTEST` / `REJECTED`, `notes` prefixed `"rejection: "`,
  optional `evidenceRefs` + EVIDENCE edges) and the `REVIEW` edge; emit **no**
  `AcceptedEventConsequence`, **no** `LINEAGE_SUPERSEDES`; set
  `final_outcome = "RETAIN_DRAFT"`.
- `kernel/policy.py` — select the authority action by the *review action* (a
  table keyed on `reviewAction`, e.g. `REVIEW_ACCEPT → REVIEW_ACCEPT`,
  `REVIEW_REJECT_OR_CONTEST → REVIEW_REJECT_OR_CONTEST`), and add
  `REVIEW_REJECT_OR_CONTEST` to `NON_COMMIT_ACTION_CLASSES` so default-deny
  registers it.
- `kernel/stages.py` — consume that selector at **both** authority touchpoints
  (`:229` generic AUTHORITY gate, `:500` ReviewPromotionGate check) instead of
  the hardcoded `REVIEW_ACCEPT`; in the ReviewPromotionGate, dispatch
  `reviewAction` → `emit_queue_acceptance` | `emit_queue_rejection`.
- `kernel/validators.py` — apply the **target-validity** guards (§3.3), the
  non-empty `reviewRationale` check, and the **evidence-ref validation**
  (every supplied `reviewEvidenceRefs[]` resolves to `ofarm.evidencerecord.v0.1`,
  `:336-342`) for the reject branch; do **not** apply the acceptance-only
  promotion guards (`ACCEPTANCE_BY_ASSERTION_TYPE`, D18 structure-supersession).
- `kernel/stages.py` (IngressNormalizer) — **normalize and validate the
  `(reviewAction, decisionOutcomeState)` pair fail-closed** per the §3.1 matrix:
  absent ⇒ `REVIEW_ACCEPT`/`ACCEPTED`; `REVIEW_REJECT_OR_CONTEST`+`REJECTED` ⇒
  reject; `REVIEW_REJECT_OR_CONTEST`+`CONTESTED` ⇒ refuse until G5-3; any
  mismatched / unrecognized action or outcome ⇒ governed refusal, never a silent
  accept.
- receipt is **free**: because `emit_queue_rejection` registers the
  `ReviewDecision` in `ctx.emitted["reviews"]`, the generic `PromotionTraceWriter`
  already wires `emittedReviewDecisionRefs`, the `PROMOTION_EMITS` edge, and the
  `CommitIngressResult` (§3.6) — no new machinery.
- `kernel/api.py` — the review surface passes `reviewAction` (default
  `REVIEW_ACCEPT`).

**Acceptance checklist:**

1. A REJECT of a `PENDING_REVIEW` assertion emits a `ReviewDecision`
   (`REVIEW_REJECT_OR_CONTEST` / `REJECTED`, non-empty rationale), **no
   `AcceptedEventConsequence`**, a `REVIEW` edge, commit outcome `RETAIN_DRAFT`.
2. The rejected claim leaves the pending queue and never appears in force; the
   assertion record is unedited.
3. Authority: a principal lacking `REVIEW_REJECT_OR_CONTEST` is denied even if it
   holds `REVIEW_ACCEPT` (distinct, non-inheriting action).
4. A REJECT with an empty/missing rationale is refused; a non-existent,
   wrong-kind, or cross-farm target is refused (validity guards); a supplied
   `reviewEvidenceRefs` member that does not resolve to an `EvidenceRecord`
   refuses the rejection, and an EVIDENCE edge is written only for a validated
   ref.
4a. The `(reviewAction, decisionOutcomeState)` pair is normalized fail-closed
   (§3.1): an absent action still accepts; `REVIEW_REJECT_OR_CONTEST`+`REJECTED`
   rejects; `REVIEW_REJECT_OR_CONTEST`+`CONTESTED` is refused until G5-3; any
   mismatched / unrecognized action or outcome is a governed refusal, never a
   silent accept.
4b. The rejection `ReviewDecision` is reachable as a receipt: it appears in the
   `CommitIngressResult.emittedReviewDecisionRefs`, in the `PromotionTrace`, and
   carries its `PROMOTION_EMITS` edge (D3).
5. A REJECT of a queued claim with **no acceptance path** (an `assertionType`
   outside `ACCEPTANCE_BY_ASSERTION_TYPE`) still succeeds — REJECT is not
   type-gated.
6. Rejecting a queued **structure correction** leaves the prior consequence in
   force and retires nothing (the supersession intent is abandoned).
7. Any later review of a rejected target is refused (`RETAIN_DRAFT`,
   `SUPERSEDED_RECORD_USED`, "already reviewed") — covering reject→accept,
   reject→reject, accept→reject; a new capture is reviewable afresh.
8. No materialization is staled or invalidated by a REJECT.
9. The M1 suite stays green and `ofarm_pkg_contract_check.py` PASSes.
