# OFARM2 Kernel

Status: implementation and conformance packaging profile — **not OFARM law, not a new authority layer**.
Source of authority: the OFARM2 canonical repository (see `reference/law/PROJECT_AUTHORITY.md`). If this document and canonical law disagree, that is an extraction bug: log it in `ERRATA.md` and resolve against the canonical repository.

## What the Kernel is

The Kernel is the reusable OFARM truth machine, in one sentence:

> An append-only record of who claimed what, when, on what evidence, with what authority — plus a derived "current state" that can always show its receipts.

It is domain-agnostic. Nothing in it knows about crops. A Kernel-conformant store could in principle govern any operational domain; `CORE.md` is what binds it to crop farming.

## The record families

All contracts live in `contracts/kernel/`. Files marked **(candidate)** are new candidate artifacts (Constitution RC2.1 §6.16); everything else is a byte-identical extraction from the canonical current/default schema lane — see `contracts/CONTRACTS_MANIFEST.json` for digests and source paths.

| # | Family | Contracts | Plain-English meaning |
|---|--------|-----------|----------------------|
| 1 | Identity | `IdentityRecord` **(candidate)**, `IdentityLifecycleChange` | A durable thing with an ID, a type, lineage (revises / split / merged / supersedes), and a lifecycle state. State change ≠ revision ≠ new identity. |
| 2 | Party | `Party` **(candidate)** | A person, organization, or authorized software agent. A SOFTWARE_AGENT party grants nothing by existing — agent actorship law applies. |
| 3 | Role | `RoleAssignment` | Party + role type + scope + time window. A role is who you are in context, never what you may do. |
| 4 | Authority | `AuthorityGrant`, `DelegationGrant`, `SharingGrant`, `RevocationDecision`, `AuthorizationDecisionRequest/Result/Trace` | Explicit, scoped, time-bounded permission; delegation for acting on someone's behalf; sharing for read access; revocation is prospective and erases nothing. Every allow/deny is traceable. |
| 5 | Assertion | `AssertionRecord` | An immutable typed claim with its own times (`assertedAt`, `occurrenceTime`, `effectiveFrom/Until`), evidence refs, and claim state. |
| 6 | Event | `SemanticEventEnvelope` | Something that happened, typed into the seven fixed families, with explicit `timeSemantics`. An event is not current state merely because it exists. |
| 7 | Evidence | `EvidenceRecord` **(candidate)**, `EvidenceSufficiencyCase` (v0.2) | Raw asset (with sha256 digest) + interpretation + provenance; sufficiency cases argue whether evidence meets a policy floor. Evidence supports truth; it never creates accepted state by itself. |
| 8 | Review | `ReviewDecision` | Accept / reject / contest / supersede, by a named party, at a time. Logically Kernel; canonical path remains `output_assembly/` until post-pilot remap. |
| 9 | Consequence | `AcceptedEventConsequence` | The bridge from history to state: "this event's consequence is now in force." Requires a `ReviewDecision` reference — there is no acceptance without a reviewer. |
| 10 | Commit boundary | `CommitIngressRequest/Result`, `PromotionTrace` | The governed front door. **Commit class lives here, not on AssertionRecord.** The trace records the gate sequence and every emitted record. |
| 11 | Materialization | `MaterializationRequest/Result/Basis/Snapshot`, `ContextSnapshot` | Derived current state with receipts: which records, which context, which time policy, which freshness state. |
| 12 | Refusal | `RuntimeProblem` | The standard machine-readable error/refusal object, with reason codes. |

## The seven Kernel rules

1. **Append-only.** Nothing is deleted or edited in place. Correction is supersession; history survives every correction.
2. **Default deny.** No valid path through role, grant, scope, time, delegation, and revocation state means DENY — recorded as an `AuthorizationDecisionTrace`.
3. **Capture is not commitment.** Drafts exist freely; only a governed commit through `CommitIngressRequest` creates authoritative records.
4. **No shortcut to truth.** A claim is not a fact until the promotion path allows it: an operation claim is not an accepted execution; a compliance assertion is not a compliance fact; an advisory output may never directly create or mutate compliance state. Twin discipline attaches to **materialization, promotion, and output paths** via target-twin / use-class / commit-class metadata where the specific contract requires it — substrate records (identity, party, authority, raw evidence) are not intrinsically COMPLIANCE or ADVISORY. The invariant: **no Advisory material enters a Compliance materialization without a governed bridge.**
5. **Current state is derived.** It is computed from in-force records, carries a `MaterializationBasis` naming every contributor and a `ContextSnapshot` naming the interpretation context, and carries a freshness state (FRESH / STALE / INVALID). High-consequence use of stale state must recompute, refuse, or route to review.
6. **Time never collapses.** Event time, record time, assertion time, and effective time are distinct fields and stay distinct — especially for delayed/offline records.
7. **Refusal is a feature.** When authority, evidence, freshness, or resolution is not satisfied, the system refuses or disclosures via `RuntimeProblem` and result qualification — it never silently pretends.

## The reachability invariant

Because commit class lives on the ingress boundary (rule corrected during plan review — see `ERRATA.md` provenance):

> **Every authoritative record (assertion, event, review decision, accepted consequence) must be reachable from exactly one `PromotionTrace`.**

`PromotionTrace` already carries `emittedAssertionRecordRefs`, `emittedReviewDecisionRefs`, `emittedAcceptedConsequenceRefs`, plus the authorization, evidence-sufficiency, and materialization result references. The store enforces reachability with an indexed link written in the same transaction as the commit. No schema change is required or permitted for this.

## Kernel conformance (definition of done)

A store is **Kernel-conformant** when:

1. all Kernel contracts validate on write (schema validation is necessary, never sufficient — semantic conformance is separate);
2. the seven rules hold under the conformance suite in `conformance/` (append-only, default deny, no-shortcut, derived state with basis, time separation, refusal behavior);
3. the reachability invariant holds for every authoritative record;
4. an engineer who has never seen the canonical repository can build a client against the store from this package alone.

## What the Kernel is not

Not a farming model (that is `CORE.md`). Not a runtime (that is `PLATFORM.md`). Not law (that is `reference/law/`). Not a promoted machine-contract set — candidate artifacts here enter the canonical promotion ladder only through post-pilot governance.
