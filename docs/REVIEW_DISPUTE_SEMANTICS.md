# Review / dispute state-transition semantics

**Status:** G5-1 (REJECT) settled · G5-3 (CONTEST) settled — see §6.
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
| `REVIEW_REJECT_OR_CONTEST` | `CONTESTED` | **governed refusal until G5-4** (CONTEST is specified at §6 but the emission branch is not wired until G5-4 — never silently downgraded to a reject or an accept) |
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

## 6. CONTEST / dispute semantics (G5-3, settled — G5-4 implements)

**Status:** G5-3 settles this section; G5-4 implements it. CONTEST reuses the
shared `REVIEW_REJECT_OR_CONTEST` action with `decisionOutcomeState = "CONTESTED"`
(the discriminator G5-1 §3.1 already pins — until G5-4 wires the contest branch,
`REVIEW_REJECT_OR_CONTEST` + `CONTESTED` is a governed refusal). Like REJECT it is
append-only, no contract changes, no invented vocabulary, record-keeping claim
only.

### 6.0 What CONTEST is, and how it differs from REJECT

A CONTEST **opens a dispute against an already in-force `AcceptedEventConsequence`**
— a record that was accepted and is current. It does not delete or edit it;
it **flags it disputed**, append-only, and **qualifies every read that depends on
it**. Resolution is by the ordinary correction-is-supersession path, never an
edit. This is the structural opposite of REJECT, which declines a *queued* claim
that was never in force.

| | REJECT (§3) | CONTEST (§6) |
|---|---|---|
| Target | a `PENDING_REVIEW` `AssertionRecord` (queued) | an in-force `AcceptedEventConsequence` |
| `reviewedArtifactFamily` | `ASSERTION_RECORD` | `ACCEPTED_EVENT_CONSEQUENCE` |
| `decisionOutcomeState` | `REJECTED` | `CONTESTED` |
| In-force effect | none (was never in force) | the consequence **stays in force**, flagged disputed |
| Materialization | untouched | **stales** dependent materializations (D12); a disputed basis **blocks** high-consequence freeze |
| Read qualification | n/a | `disputeStatus` flips off the hardcoded `NONE` (closes the M4 over-claim) |
| Resolution | a new capture (the queued claim is terminal) | a **supersession** (a governed CORRECTION) → `CORRECTED` |

### 6.1 Trigger and surface

A CONTEST is a `GOVERNANCE_DECISION` commit naming the in-force consequence as
its target and carrying the contest half of the normalized verb pair
(`reviewAction = REVIEW_REJECT_OR_CONTEST`, `decisionOutcomeState = CONTESTED`,
§3.1). G5-4 wires the `CONTESTED` branch in `policy.review_branch` (a third
branch `"CONTEST"`) and the `ReviewPromotionGate` dispatch. **Recommended
surface:** a `/review/contest` endpoint (symmetric with `/review/reject`)
supplying the normalized pair and the target consequence ref; the state effects
below are binding regardless of surface.

### 6.2 Authority

Same **distinct `REVIEW_REJECT_OR_CONTEST`** action as REJECT (the shared verb,
NO_INHERIT; §3.2). A principal lacking it is default-denied. The same
self-decision treatment as REJECT applies (a party may contest a record under the
classes it may self-review; otherwise a distinct reviewer) — contesting is a step
*toward* correction, never a self-promotion, so it is no more privileged than a
decline.

### 6.3 Validation (in-force consequence target)

The CONTEST analog of §3.3's validity guards, retargeted to a consequence:

- the target must **resolve to a record of kind `ofarm.acceptedeventconsequence.v0.1`**
  (a non-existent or wrong-kind ref → gate outcome `FAIL_REFERENCE_RESOLUTION`,
  reason code `EVIDENCE_REFERENCE_UNAVAILABLE` — the exact pair the acceptance
  validator uses for an unresolved target, `kernel/validators.py:260-264`);
- it must be **in force** — `inForceState = "IN_FORCE"` **and** not
  `store.is_superseded(...)` (you cannot contest a record already out of force;
  else `SUPERSEDED_RECORD_USED`). A consequence that has a *pending* correction
  (a `LINEAGE_SUPERSEDES_INTENT` edge from a queued claim, not yet accepted) is
  still in force and **may be contested** — the pending correction, if later
  accepted, resolves the dispute by supersession (§6.7); the two are compatible;
- it must be **farm-contained** (its `anchorScopes` include the acting farm; else
  `SCOPE_NOT_AUTHORIZED`);
- it must **not already carry an open `DISPUTE`** (no double-contest — a second
  contest of an already-disputed consequence, i.e. `edges_from(consequence,
  "DISPUTE")` non-empty and unresolved, is refused `SUPERSEDED_RECORD_USED`
  "already disputed", mirroring the double-decide guard);
- a **non-empty rationale** is required (`reviewRationale`, gate-validated; the
  decision is governed, never a bare pointer — Kernel rule 7);
- **evidence is optional but validated if supplied** (every `reviewEvidenceRefs[]`
  resolves to `ofarm.evidencerecord.v0.1`, else `FAIL_REFERENCE_RESOLUTION`) —
  exactly as REJECT (§3.3).

### 6.4 Emission (append-only; the consequence is never edited)

The CONTEST commit appends one authoritative governance record plus its marker
edge:

```jsonc
{
  "schemaVersion": "ofarm.reviewdecision.v0.1",
  "reviewDecisionId": "review:<minted>",
  "reviewedArtifactFamily": "ACCEPTED_EVENT_CONSEQUENCE",
  "reviewedArtifactRef": "<the in-force consequence>",
  "reviewAction": "REVIEW_REJECT_OR_CONTEST",
  "decisionOutcomeState": "CONTESTED",
  "anchorScopes": [{ "scopeType": "FARM", "scopeRef": "<farm>" }],
  "decidedByPartyRef": "<reviewer>", "decidedAt": "<now>",
  "notes": "dispute: <non-empty rationale>"
  // optional "evidenceRefs"; NO resultingAcceptedConsequenceRefs (nothing promoted)
}
```

- a **`DISPUTE` edge** `consequence → reviewDecision` marks the consequence
  disputed. This is the authoritative dispute flag — "is this consequence
  disputed?" is `bool(edges_from(consequence, "DISPUTE"))` with the dispute
  unresolved (the consequence not yet superseded). G5-4 adds `DISPUTE` to the
  `kernel_edge` `edge_type` CHECK. (A dedicated edge, not the `REVIEW` edge an
  acceptance already wrote on the consequence, keeps the dispute query clean and
  append-only.)
- one `EVIDENCE` edge per validated optional evidence ref (as REJECT);
- **no `AcceptedEventConsequence`** and **no `LINEAGE_SUPERSEDES`** — a contest
  promotes nothing and retires nothing. The disputed consequence **stays
  `IN_FORCE`** (its `inForceState` enum has no `DISPUTED` value, and
  `is_superseded` reads only `LINEAGE_SUPERSEDES`, so it remains current until a
  correction supersedes it). The originating assertion is likewise untouched.
- the ReviewDecision registers in `ctx.emitted["reviews"]` so the generic
  `PromotionTraceWriter` carries it as a receipt (D3), exactly as REJECT (§3.6).

**Decision — CONTEST is governance-only in G5-4 (no `recordClass = DISPUTE`
payload).** The `recordClass` enum carries a `DISPUTE` value (the CORE.md
"dispute = new payload + supersession" carrier, the factual mirror of
`CORRECTION`), but **G5-4 emits and accepts none**. A CONTEST is purely a
governance act: `ReviewDecision (CONTESTED) + DISPUTE edge`, nothing more. An
`ExecutionRecordPayload(recordClass = "DISPUTE")` — a substrate carrier asserting
the disputed *facts* — is **deferred to a later factual-dispute-carrier ticket**
that would specify its required fields, linkage to the contest, validation, and
tests. Until then a contest states its objection in the `ReviewDecision.notes`
rationale (and optional validated evidence), and the factual correction arrives
through the ordinary `recordClass = "CORRECTION"` resolution path (§6.7).

### 6.5 `disputeStatus` derivation — closes the latent M4 over-claim

Today the single qualification builder hardcodes `"disputeStatus": "NONE"`
(`kernel/views.py:58`), so both shipped surfaces (PassportView,
DocumentAssembly) **claim "no dispute" unconditionally** — the M4 over-claim
(WORKLOG 2026-06-14; M2_BRIEF). G5-4 makes `disputeStatus` **derived** from
whether the result's basis (and the records it directly presents) carry an
unresolved `DISPUTE`:

| `disputeStatus` | When |
|---|---|
| `NONE` | no unresolved dispute touches the basis or the presented records (the honest default — *computed*, not assumed) |
| `OPEN_DISPUTE` | the surface presents a disputed record directly (an open `DISPUTE` on a record in view) |
| `DISPUTED_BASIS` | the surface presents a derived result whose `MaterializationBasis` includes an unresolved disputed consequence |
| `CORRECTED` | a current basis member supersedes (via `LINEAGE_SUPERSEDES`) a disputed predecessor — the dispute was resolved by a governed CORRECTION (§6.7) |
| `SUPERSEDED` | a historical/direct surface still references the superseded disputed consequence itself |
| `MIXED` | the result's contributors carry two or more **distinct non-`NONE`** statuses |

**Derivation (all from edges, no stored disputeStatus field).** An *unresolved*
dispute is a `DISPUTE` edge whose target consequence is **not yet superseded**
(`not is_superseded(consequence)`); a *resolved* one has since been superseded.
Because the current basis holds only **in-force** consequences, a resolved
dispute is found by **walking `LINEAGE_SUPERSEDES`** from a current basis member
to its superseded predecessor(s) — the disputed predecessor is no longer in the
basis, only its corrected successor is, so the derivation **must follow the
supersession edge, never look for the disputed member in the current basis**.
Per contributor:
- `OPEN_DISPUTE` — a record the surface presents **directly** carries an
  unresolved dispute;
- `DISPUTED_BASIS` — no directly-presented record is disputed, but the result's
  `MaterializationBasis` (its `contributingAcceptedConsequenceRefs`) **includes**
  an unresolved disputed consequence;
- `CORRECTED` — a **current** in-force basis member has a `LINEAGE_SUPERSEDES`
  edge to a **predecessor that carries a `DISPUTE` edge**: a governed CORRECTION
  resolved the dispute, and the current result reports the resolution by walking
  that lineage (derived, not stored);
- `SUPERSEDED` — a **historical / direct** surface still references the superseded
  disputed consequence itself (it left force; current materializations no longer
  carry it);
- `NONE` — no contributor is disputed or resolves a dispute (computed, never
  assumed).

**Aggregation to a single value.** Compute each contributor's status above. The
result's `disputeStatus` is: that status when all non-`NONE` contributors agree;
`NONE` when none is non-`NONE`; a **lone** non-`NONE` status when the remaining
contributors are clean (a clean member never dilutes a dispute condition); and
**`MIXED` only when two or more *distinct* non-`NONE` statuses are present** —
e.g. one `OPEN_DISPUTE` contributor alongside one `CORRECTED` contributor — so
the result honestly reports the blend rather than collapsing it.

`dataAbsentReason = "DISPUTED"` is a **distinct** concern (data-absence, not
dispute status) and is not set by CONTEST. **CONTEST targets consequences, not
assertions:** G5-4 sets no assertion's `claimState` to `CONTESTED` (the
originating assertion is never mutated — append-only). The
`claimState = "CONTESTED"` view lane (`kernel/views.py:105-107`) is a *surfacing
channel* (and a reserved hook for a future direct-assertion-dispute path), not a
record mutation; a disputed claim is surfaced by deriving from the consequence's
`DISPUTE` edge (tracing consequence → originating assertion).

### 6.6 Materialization staling (D12) and high-consequence blocking

**Two orthogonal axes — freshness vs dispute.** `stalenessClass` describes
**freshness only** (is the materialization current with respect to its basis);
`disputeStatus` carries the **dispute condition** (is a basis member disputed).
They move independently, and a CONTEST acts on both in two distinct steps:

1. **Stale-on-contest (freshness axis).** A CONTEST is a basis-set staleness
   trigger (D12): the disputed consequence is a `MaterializationBasis` member
   whose state changed. G5-4 calls the existing
   `Materializer.invalidate_for_sources([contested_consequence])`
   (`kernel/materializer.py:590`) in the contest commit's transaction, marking
   every materialization whose basis includes it **STALE** — a one-time
   invalidation so the next read recomputes against current state.
2. **Fresh-plus-disputed after recompute (dispute axis).** On recompute the
   result is **`FRESH` again** on the freshness axis (it is current), yet it
   still carries **`disputeStatus = DISPUTED_BASIS`** because its basis includes
   an unresolved disputed consequence. Freshness and dispute are not the same
   signal: a current result can be honestly fresh *and* disputed.

Then, per surface:
- **PassportView** (informational) recomputes (`stalenessClass = FRESH`) and
  qualifies `disputeStatus = DISPUTED_BASIS` — the dispute is **shown, never
  hidden** (Kernel rule 7).
- **DocumentAssembly freeze** (high-consequence) **refuses on the dispute axis**:
  a `DENY`/refusal outcome carrying `DISPUTE_OPEN` (the registered,
  until-now-unused code — "data exists but is disputed") **because the basis is
  disputed, not because the recomputed result is stale**. A disputed truth is
  never frozen into an output even when the materialization is `FRESH`.

This is the key REJECT/CONTEST difference: REJECT touches no materialization
(§3.7); CONTEST stales the dependent ones (freshness axis) and blocks
high-consequence reliance (dispute axis).

### 6.7 Resolution — by supersession, never by edit

A dispute resolves the way every correction does: a governed **CORRECTION** — a
new claim carrying `supersedesConsequenceRef = <disputed consequence>` — committed
and accepted, which emits a new in-force consequence with a `LINEAGE_SUPERSEDES`
edge to the disputed one (`kernel/emission.py:294-302`). The disputed consequence
then leaves force (`is_superseded` true), the dispute is **resolved by the edge
fact** (no record edited), and the dependent materializations re-stale and
recompute against the corrected consequence. The recomputed current basis now
holds the **corrected successor** (not the disputed predecessor), so the current
read derives `disputeStatus = CORRECTED` by **walking `LINEAGE_SUPERSEDES` from
that successor to its disputed predecessor** (§6.5) — never by looking for the
disputed consequence in the current basis, where it no longer appears.
Resolution is **automatic and non-mutual**: the CORRECTION need not reference the
`DISPUTE` edge or the contest `ReviewDecision` — once its acceptance writes
`LINEAGE_SUPERSEDES` to the disputed consequence, that edge alone drives the
derivation, so no follow-up act closes the dispute. This
reuses the existing supersession path entirely; G5-4 adds no new resolution
mechanism. An open dispute that is never corrected stays **visibly open**
(`OPEN_DISPUTE` / `DISPUTED_BASIS`) — honest, never silently cleared.

### 6.8 Commit outcome

A CONTEST promotes no new consequence, so its commit outcome is **`RETAIN_DRAFT`**
(no consequence promoted) — the same convention and the same caveat as REJECT
(§3.6 / ERRATA E-005): the authoritative dispute is carried by the `ReviewDecision`
(`CONTESTED`), the `DISPUTE` edge, and the staled materializations, never by
`finalOutcome` alone.

### 6.9 Explicit non-effects and out of scope for G5-4

A CONTEST does **not**: edit, delete, or remove from force the disputed
consequence (it stays `IN_FORCE`, flagged); emit an `AcceptedEventConsequence` or
`LINEAGE_SUPERSEDES`; mutate the originating assertion's `claimState`; or resolve
the dispute (only a CORRECTION does). **Out of scope (deferred):** dismissing an
*unfounded* contest (a `REVIEW_SUPERSEDE` on the contest `ReviewDecision`) — until
then an unfounded dispute simply stays visibly open until corrected; and SI
advisory specifics (P5).

**Temporal (AS_OF) consistency.** A dispute is an append-only fact with a
`record_time`; an `AS_OF` historical read reconstructs dispute state on the **same
single time axis** as in-force selection (`store.in_force_consequences(as_of=…)`
already reconstructs supersession by `record_time`). So a dispute opened at time T
is **invisible** to an `AS_OF` read of an earlier moment and visible from T onward
— exactly as a supersession is. The G6 AS_OF reconstruction inherits this with no
special case; a later dispute never rewrites an earlier historical answer.

### 6.10 G5-4 build list and acceptance checklist

- `kernel/schema.sql` — add `DISPUTE` to the `kernel_edge` `edge_type` CHECK.
- `kernel/policy.py` — `review_branch` returns a third branch `"CONTEST"` for
  `REVIEW_REJECT_OR_CONTEST` + `CONTESTED`.
- `kernel/validators.py` — the contest branch validates an in-force consequence
  target (§6.3): kind, in-force/not-superseded, farm-contained, no open dispute,
  non-empty rationale, validated optional evidence.
- `kernel/emission.py` — `emit_queue_contest()`: append the `ReviewDecision`
  (`CONTESTED`) + the `DISPUTE` edge (no consequence, no supersession); register
  in `ctx.emitted["reviews"]`; `final_outcome = "RETAIN_DRAFT"`; call
  `invalidate_for_sources([target])` in the same transaction.
- `kernel/views.py` — derive `disputeStatus` (§6.5) instead of the hardcoded
  `NONE`; DocumentAssembly freeze refuses a disputed basis with `DISPUTE_OPEN`.
- `kernel/api.py` — `/review/contest` supplies the normalized pair.
- `kernel/demo.py` / tests — `kernel/tests/test_m2_review.py`.

**Acceptance checklist:**

1. A CONTEST of an in-force consequence emits a `ReviewDecision`
   (`REVIEW_REJECT_OR_CONTEST` / `CONTESTED`, non-empty rationale) + a `DISPUTE`
   edge, **no consequence**, outcome `RETAIN_DRAFT`; the consequence is unedited
   and **stays in force**.
2. **Freshness axis:** a CONTEST stales every dependent materialization
   (`invalidate_for_sources`), proven by a stale-on-contest test.
2a. **Dispute axis:** after recompute the result is `stalenessClass = FRESH`
   yet `disputeStatus = DISPUTED_BASIS` (a fresh-plus-disputed test) — the two
   axes are independent.
2b. **Output refusal:** a DocumentAssembly freeze from a disputed basis refuses
   `DENY` / `DISPUTE_OPEN` **because the basis is disputed, not because it is
   stale** (the result may be `FRESH`).
3. Authority: a principal lacking `REVIEW_REJECT_OR_CONTEST` is denied.
4. Validity: a target that is not an in-force consequence, is already superseded,
   is cross-farm, or is already disputed is refused; an empty rationale or
   unresolved evidence ref refuses.
5. Resolution (lineage-derived): contested **C1** → an accepted CORRECTION **C2**
   supersedes C1 → the recomputed current basis holds **C2** (not C1) → a current
   read derives `disputeStatus = CORRECTED` by walking C2 → C1
   `LINEAGE_SUPERSEDES` and finding C1's `DISPUTE` edge; no record edited.
6. `disputeStatus = NONE` is now **computed** (a clean farm reads `NONE`; the
   over-claim is closed).
7. The M1 suite stays green and `ofarm_pkg_contract_check.py` PASSes.

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
  reject; `REVIEW_REJECT_OR_CONTEST`+`CONTESTED` ⇒ refuse until G5-4; any
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
   rejects; `REVIEW_REJECT_OR_CONTEST`+`CONTESTED` is refused until G5-4; any
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
