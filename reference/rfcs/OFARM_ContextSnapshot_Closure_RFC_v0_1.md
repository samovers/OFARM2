# OFARM ContextSnapshot Closure RFC v0.1

Date: 2026-04-11  
Status: accepted post-charter RFC  
Scope: formalize the already-implied context snapshot basis for current-state materialization without turning it into a hidden truth store

---

## 1. Problem statement

The active baseline and the Current-State Materialization RFC already say the right high-level thing:
- a current-state materialization is derived from assertion/history authority
- that materialization is identifiable partly by **context snapshot**
- `MaterializationBasis` must carry governing context snapshot identifiers
- the applicable context includes active packs/profiles, relevant scoped extensions, relevant rule/evidence-policy versions, relevant reference snapshot versions, and relevant identity revisions

That direction is correct.
What is still missing is the actual governed object contract for the context basis itself.

Without that closure, the package still leaves too much drift-prone room around questions such as:
- what exactly a runtime is expected to mean by “context snapshot”
- how pack activation and active-artifact state become a resolved materialization context rather than loose references
- when a context change is only a recomputation under the same basis versus a true basis drift
- what a high-consequence `MaterializationBasis` must be able to point to

This RFC closes that gap with a small executable patch.

It does **not** reopen OFARM’s truth model.
It makes the already-required materialization context basis explicit.

---

## 2. Core stance

### 2.1 ContextSnapshot is a governed basis object, not a second truth store
A **ContextSnapshot** is a traceable resolved context basis for a governed materialization answer.

It is **not**:
- a hidden primary store
- a runtime cache promoted into truth by accident
- a full copy of the semantic substrate

It is the minimum machine-readable object that explains **which active context materially governed interpretation** when a current-state answer was produced.

### 2.2 Pack activation alone is necessary but not sufficient
A `PackActivationSet` answers which pack/profile activation posture was evaluated for a scope/time.
That is necessary.
It is not, by itself, the full materialization context basis.

A materialization context may also need to make explicit:
- the resolved active artifact state
- the relevant rule/evidence-policy revisions actually governing the answer
- the relevant reference snapshot versions
- the relevant identity revisions active at that evaluation point
- any merge-resolution traces that materially affected the context

### 2.3 High-consequence materialization must point to resolvable context
For high-consequence current-state use, a `MaterializationBasis` should not merely contain an opaque string that claims to be a context snapshot identifier.
It should be able to resolve that identifier to a concrete governed `ContextSnapshot` object.

### 2.4 Basis-preserving recomputation must be distinguished from basis drift
Not every recomputation means the context basis changed.

If the governing context is materially the same, the platform may recompute under the same `ContextSnapshot` basis.
That is **basis-preserving recomputation**.

If the governing context changes materially, the platform must treat that as **basis drift** and mint a new `ContextSnapshot` rather than silently pretending the old basis still applies.

### 2.5 Material context changes must be query-visible and audit-visible
If context changes materially because of:
- active pack/profile change
- scoped extension change
- governing rule/evidence-policy change
- relevant reference snapshot version change
- relevant identity revision change
- merge-resolution outcome change

then the runtime should not hide that inside implementation detail.
It should produce a new resolvable context basis.

---

## 3. Formal artifacts produced by this RFC

This RFC creates:

- **OFARM ContextSnapshot schema v0.1** (`ofarm.contextsnapshot.v0.1`)

This RFC also introduces executable example payloads for:
- baseline compliance context on a field
- the same field after orchard-pack activation materially changes the governing context
- corresponding pack-activation, active-artifact, merge-trace, and materialization-basis examples needed to make the snapshot grounding testable

---

## 4. What a ContextSnapshot means

### 4.1 One ContextSnapshot = one resolved interpretation basis
A `ContextSnapshot` represents the resolved context basis for a governed materialization answer at a declared:
- twin
- anchor scope
- evaluation time policy

It captures the context dimensions that materially affect interpretation.

### 4.2 Minimum resolution dimensions
At minimum, a `ContextSnapshot` should be able to identify:
- target twin
- anchor scope
- evaluation time policy
- source `PackActivationSet` references
- resolved active pack/profile/scoped-extension references
- governing `ActiveArtifactSet` reference
- relevant precedence classes
- governing rule/evidence-policy references where relevant
- relevant reference snapshot references where relevant
- relevant identity revision references where relevant
- relevant `PackMergeResolutionTrace` references where overlap materially affected the resulting context

### 4.3 Relation to PackActivationSet
A `PackActivationSet` is an input and grounding trace for context.
A `ContextSnapshot` is the resolved materialization context basis that may be built from one or more activation sets.

This means:
- a context snapshot may refer to one or more activation sets
- a context snapshot must not invent active packs/profiles that are inconsistent with those activation sets
- where pack overlap mattered, the relevant merge trace should be reachable

### 4.4 Relation to ActiveArtifactSet
`ActiveArtifactSet` remains the runtime-facing grounding object for which artifacts are actually active in a deployment or tenant posture.

A `ContextSnapshot` should point to the relevant `ActiveArtifactSet` when that grounding matters.
This avoids turning the context snapshot into a blob that copies all artifact metadata into itself.

### 4.5 Relation to MaterializationBasis
`MaterializationBasis.contextSnapshotRefs` now has an explicit object family to point to.

For high-consequence use, the referenced context snapshot should be resolvable and should align with the basis on at least:
- twin
- anchor scope
- evaluation time policy

### 4.6 Relation to MaterializationSnapshot
A `MaterializationSnapshot` records the relied-upon current-state answer.
A `ContextSnapshot` records the resolved interpretation basis under which that answer was generated.

They are related, but they are not the same object.

---

## 5. When a new ContextSnapshot is required

### 5.1 Basis-preserving recomputation
The platform may reuse an existing `ContextSnapshot` when recomputing current state if the governing context remains materially the same.

Typical basis-preserving cases:
- regenerated current-state answer under the same active context
- new durable `MaterializationSnapshot` retained for audit while the context basis remains unchanged
- truth-basis recomputation caused by new assertions or accepted consequences, but without material context change

### 5.2 Basis drift
The platform should mint a new `ContextSnapshot` when any context dimension changes materially, including at least:
- active pack set
- active profile set
- active scoped extension set
- relevant precedence relationship outcome
- governing rule/evidence-policy revision
- relevant reference snapshot version
- relevant identity revision where interpretation depends on it
- pack merge-resolution trace outcome affecting the applied context
- evaluation time policy when it changes the applicable context basis

### 5.3 High-consequence posture
If context drift occurs, a prior materialization may become:
- **STALE** for exploratory use, or
- **INVALID** for high-consequence use

The exact freshness decision remains governed by current-state materialization law.
This RFC does not replace that law.
It gives the runtime a concrete context object needed to apply it consistently.

---

## 6. Minimum machine-contract expectations

A minimal `ContextSnapshot` contract in this wave should support:
- schema validation
- resolution to `PackActivationSet` and `ActiveArtifactSet`
- optional linkage to `PackMergeResolutionTrace`
- linkage from `MaterializationBasis`
- fixture-level distinction between:
  - same-basis recomputation
  - basis drift causing stale/invalid posture

This wave is intentionally narrow.
It does **not** claim:
- full runtime materialization envelopes
- full refusal/reroute logic
- comprehensive twin-differential policy coverage

Those remain later closure work.

---

## 7. Conformance posture

This RFC is a closure artifact.
It should be implemented with:
- machine-validatable `ContextSnapshot` schema
- grounded example payloads
- fixture-level checks that confirm:
  - `MaterializationBasis` resolves to a concrete context snapshot
  - context snapshots ground to activation/artifact state
  - same-basis recomputation is distinguishable from basis drift

---

## 8. Non-goals and safety guardrails

### 8.1 No hidden truth-store promotion
This RFC must not be used to treat `ContextSnapshot` as a second authoritative substrate.
Truth remains assertion/history-first.

### 8.2 No cache leakage into semantic law
An implementation cache entry is not automatically a governed context snapshot.
Only a governed, traceable, resolvable basis object counts.

### 8.3 No broad architecture rewrite
This RFC does not change:
- the twin model
- the canonical truth model
- pack law
- current-state law

It closes a missing executable contract that those laws already imply.
