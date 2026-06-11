# OFARM Current-State Materialization RFC v0.1

Date: 2026-04-08  
Status: accepted post-charter RFC  
Scope: define what current-state materialization is operationally, when it is fresh/stale/invalid, and when the platform must recompute or refuse to rely on it

---

## 1. Problem statement

RC2 correctly says:
- OFARM uses assertion/history-first authority
- OFARM maintains governed current-state materializations
- current-state materialization is canonical for current-state use, but not deeper than authority

That is directionally right, but still too abstract for implementation.

The unresolved questions are:
- what exactly counts as a materialization instance
- how a materialization is traced back to authority
- when a materialization is still usable
- what makes it stale or invalid
- when the platform must recompute before using it for high-consequence actions
- how Compliance and Advisory twins differ operationally

This RFC closes that gap.

---

## 2. Core stance

### 2.1 Current-state materialization is derivative
A **CurrentStateMaterialization** is not another truth universe and not a hidden primary store.

It is a governed derived state representation built from:
- assertion/history-first authority
- accepted event consequences
- applicable review decisions
- applicable identity/lifecycle state
- applicable context snapshot

### 2.2 One materialization instance = one governed answer
A materialization instance must answer one governed question of the form:

**“What is the in-force current state for this twin, this scope, under this evaluation time policy and this context basis?”**

If those dimensions change materially, OFARM should treat the result as a different materialization instance.

### 2.3 Materialization must remain explainable
A materialization is only trustworthy if the system can explain:
- what authoritative basis it used
- under which context snapshot it was generated
- when it was generated
- whether it is fresh, stale, or invalid
- why

---

## 3. Materialization instance

A **CurrentStateMaterialization** instance must be identifiable at least by:

- **target twin**
- **anchor scope**
- **evaluation time policy**
- **context snapshot**
- **materialization basis**
- **generated-at time**
- **freshness status**

### 3.1 Target twin
The materialization must be explicitly for:
- Compliance Twin
- Advisory Twin

These are not interchangeable.

### 3.2 Anchor scope
The anchor scope must identify the governed scope basis of the materialization, such as:
- farm
- site
- field
- zone
- crop cycle
- lot
- facility
- another explicitly allowed scope set

### 3.3 Evaluation time policy
The materialization must declare whether it answers:
- **NOW** (current evaluation time)
- **AS_OF(time)**
- another governed time policy explicitly supported by OFARM

### 3.4 Context snapshot
The materialization must declare the context basis under which it was produced, including where relevant:
- active packs/profiles
- relevant scoped extensions
- relevant rule/evidence-policy versions
- relevant reference snapshot versions
- relevant identity revisions active at that evaluation point

### 3.5 Materialization basis
The materialization must have a traceable **MaterializationBasis** describing the authoritative substrate elements that determined the result.

### 3.6 Freshness status
The materialization must carry one of the governed freshness states defined in this RFC.

---

## 4. MaterializationBasis

A **MaterializationBasis** is the traceable basis from which a CurrentStateMaterialization was generated.

At minimum it should be able to identify:
- contributing in-force AssertionRecords
- contributing accepted event consequences
- contributing ReviewDecisions
- relevant identity revisions or lifecycle relations where they affect interpretation
- governing context snapshot identifiers
- evaluation time policy

A MaterializationBasis is not the whole graph copied into a blob.
It is the minimum governed explanation set needed to trace the result.

### 4.1 Basis sufficiency rule
If the system cannot explain the basis strongly enough to justify the materialization result, the materialization is not trustworthy enough for high-consequence use.

---

## 5. MaterializationSnapshot

A **MaterializationSnapshot** is a durable recorded generation of a CurrentStateMaterialization kept because later traceability matters.

Not every materialization needs durable storage.
But OFARM should create or retain a MaterializationSnapshot when:
- a high-consequence action depends on it
- an attested/frozen output depends on it
- later audit/explanation of the exact state basis may matter

Typical cases:
- compliance decisions
- final SubmissionAssemblies
- final DossierAssemblies where state basis matters
- accepted executed intervention consequences whose acceptance relied on current state
- important external claims or filings

A MaterializationSnapshot does not replace the authoritative substrate.
It is a durable trace of what current-state answer was relied upon at that time.

---

## 6. Freshness states

OFARM uses these baseline freshness states:

### 6.1 FRESH
The materialization is still semantically usable for its declared purpose because no known relevant invalidation trigger has occurred since generation.

### 6.2 STALE
The materialization may still be informative, but it is no longer safe for high-consequence reliance without recomputation.

A stale materialization should not be silently treated as current merely because it is recent enough by clock time.

### 6.3 INVALID
The materialization is no longer safe even as a representative state answer for its declared purpose because:
- its context basis is broken or unresolved
- required basis trace is missing
- the anchor identity/basis changed in a way that breaks its semantic applicability
- unresolved pack/context conflict or equivalent hard inconsistency exists
- another stronger condition makes the result no longer trustworthy even as a stale view

### 6.4 Freshness is purpose-sensitive
The same materialization may be:
- acceptable for exploratory advisory viewing
- but unacceptable for compliance or attested publication

So freshness must be evaluated relative to use class, not only time elapsed.

---

## 7. Invalidation triggers

A materialization becomes stale or invalid when relevant changes occur in its basis or context.

At minimum OFARM must recognize these trigger families:

### 7.1 Truth-basis triggers
- an in-force AssertionRecord enters or leaves force in relevant scope
- an accepted event consequence enters or leaves force in relevant scope
- a ReviewDecision changes what is in force
- contradiction resolution changes the in-force result

### 7.2 Identity/lifecycle triggers
- a relevant identity revision becomes active
- a lifecycle change (split/merge/replacement/reconstitution) changes what counts as the anchor scope or included identities
- a lineage decision changes which identities are in play

### 7.3 Context triggers
- relevant pack/profile activation or deactivation
- relevant scoped-extension change
- relevant rule/evidence-policy change
- relevant reference-snapshot change if the materialization depends on it

### 7.4 Time-policy triggers
- the evaluation point crosses a validity boundary
- the declared freshness window for a given use class is exceeded
- a scheduled recomputation rule for that materialization class is missed

### 7.5 Twin-specific triggers
For Advisory Twin, additional triggers may include:
- new hypotheses
- new advisory outputs
- new scenario generation
- model-output change that the materialization policy treats as relevant

### 7.6 Trigger consequence rule
Not every trigger makes a materialization INVALID.
Some only make it STALE.
But the platform must be able to say which and why.

---

## 8. High-consequence use rule

### 8.1 High-consequence uses
A platform action is **high consequence** when it can materially affect:
- compliance fact creation
- acceptance of executed intervention consequences
- governance/review decisions
- attested/frozen outputs
- formal submissions
- externally relied-upon current-state claims

### 8.2 Required rule
Before high-consequence use, the platform must ensure the relevant materialization is either:
- freshly recomputed for that use, or
- demonstrably still FRESH under the declared policy

If the materialization is STALE or INVALID, the platform must:
- recompute
- or refuse the high-consequence action
- or route to explicit review if the policy allows that path

### 8.3 Snapshot obligation
When a high-consequence action relies on current state, OFARM should retain a MaterializationSnapshot or equivalent traceable basis record so the exact relied-upon state can be reconstructed later.

---

## 9. Twin-specific materialization rules

### 9.1 Compliance Twin
Compliance-Twin materialization may derive only from:
- in-force hard-truth assertions
- accepted event consequences
- valid ReviewDecisions
- applicable context/rule/evidence policies

Compliance-Twin materialization should be conservative about freshness.
For high-consequence compliance use, stale state is not acceptable by default.

### 9.2 Advisory Twin
Advisory-Twin materialization may derive from a wider set including:
- hypotheses
- advisory outputs
- risk flags
- scenario outputs
- competing candidate interpretations

Advisory-Twin materialization may tolerate stale state in exploratory or explanatory views if clearly marked, but not when used to support a governed bridge into harder truth.

### 9.3 Bridge rule
If Advisory-Twin materialization contributes to a bridge toward compliance consequence, the platform must re-evaluate the relevant state under the stricter Compliance-Twin freshness and basis rules.

---

## 10. Operational posture

### 10.1 Materialization generation
The platform may generate materializations:
- lazily on demand
- proactively
- by cached refresh
- by event-triggered refresh

What matters constitutionally is not the scheduling style.
What matters is that freshness, invalidation, and traceability remain governable.

### 10.2 Materialization storage
The platform may:
- store materialization instances temporarily
- persist snapshots when required
- discard recomputable working materializations

But it may not let a materialization become a hidden authoritative store detached from the substrate.

### 10.3 Materialization and projections
A projection may be built from current-state materialization.

That does not mean:
- the projection is authoritative
- the materialization stops needing basis trace
- the system may ignore invalidation triggers

---

## 11. Minimal conformance expectations

A conforming implementation should be able to determine, for a declared materialization policy:

- what constitutes a materialization instance
- what its basis is
- whether it is FRESH, STALE, or INVALID
- which triggers changed that status
- whether a high-consequence use is allowed without recomputation
- how a materialization snapshot is referenced when required

At minimum, conformance fixtures should include:
- accepted assertion enters force and makes current state stale
- review decision supersedes accepted consequence and invalidates prior state
- pack activation changes context and invalidates a materialization
- field revision affects current scope interpretation without creating new identity
- crop-cycle replant creates a new identity and invalidates prior cycle-targeted materialization
- exploratory advisory view allowed to use stale materialization with clear marking
- compliance submission blocked until a fresh materialization is produced

---

## 12. Main patch consequences

This RFC requires:
- Constitution patching in truth law, twin law, and conformance direction
- Platform patching in enforcement, substrate/materialization runtime, edge rules, output behavior, and tests
- Alignment Register update for materialization-support concepts

---

## 13. Hard stop question

The RFC succeeds only if the system can answer, for a given materialization:

**What exact authoritative basis produced this state, is it fresh/stale/invalid for this use, and why?**
