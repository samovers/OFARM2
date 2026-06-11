
# OFARM Event Ingress and Promotion Boundary Closure RFC v0.1

Date: 2026-04-18
Status: accepted post-charter RFC
Scope: close the machine-contract seam for semantic event ingress, idempotent replay, and promotion tracing already required by RC2.1, the Platform runtime law, and the event grammar companion artifact

---

## 1. Problem statement

RC2.1, the Platform runtime law, and the event grammar companion artifact already depend on all of the following being true at runtime:
- semantic events stay distinct from transport envelopes
- ingress normalizes capture/import into typed OFARM draft material
- commit classes stay distinct from accepted in-force consequences
- replay-safe delivery and idempotent consumption are explicit
- promotion remains explainable across gates

That direction is correct.
It is not yet machine-closed inside the active contract set.

Today:
- the package ships event-family and promotion fixtures in `04_implementation_and_conformance/`
- the package already has source-truth record contracts for assertions, review decisions, and accepted consequences
- active contracts still do not define the semantic event boundary object or the ingress request/result pair above it
- promotion traces exist only as runtime/support evidence rather than as a governed active contract family

This RFC closes that seam with the smallest controlled patch.

---

## 2. Core stance

### 2.1 Thin boundary closure, not new architecture
This RFC does not reopen OFARM’s event grammar, commit law, truth model, or gate ordering.
It only gives first-class machine contracts to a runtime boundary seam that is already required by active law.

### 2.2 Semantic event remains distinct from transport
`SemanticEventEnvelope` is the governed OFARM-side event object retained after normalization.
It is not a transport protocol, queue wrapper, or partner payload contract.

### 2.3 Promotion tracing stays downstream of source truth
`PromotionTrace` explains how a request moved through ingress and promotion gates.
It does not replace `AssertionRecord`, `ReviewDecision`, or `AcceptedEventConsequence`.
Those source-truth records remain the authoritative history-bearing objects.

### 2.4 Idempotency must be explicit
Retry-safe and delayed-sync behavior may not remain an implementation secret.
The active contract layer must be able to represent:
- a new ingress request
- a replay that deterministically reuses an earlier result
- a conflicting replay that is blocked rather than silently duplicating truth

### 2.5 Minimum fields only
The contracts created here must carry only the minimum machine-verifiable fields needed for:
- primary event family and subtype identity
- dominant semantic consequence
- scope and subject binding
- multi-temporal preservation
- commit class and ingress mode
- idempotency/replay posture
- promotion outcome and source-truth links

This RFC does **not** create a transport SDK, message-bus profile, or giant workflow engine schema.

---

## 3. New contract families created by this RFC

This RFC creates these active machine-contract families in `03_machine_contracts/`:
- `OFARM_SemanticEventEnvelope_schema_v0_1.json`
- `OFARM_CommitIngressRequest_schema_v0_1.json`
- `OFARM_CommitIngressResult_schema_v0_1.json`
- `OFARM_PromotionTrace_schema_v0_1.json`

---

## 4. Contract minimums

### 4.1 SemanticEventEnvelope minimums
A `SemanticEventEnvelope` contract must be able to carry at least:
- stable semantic event identifier
- one primary top-level event family
- optional governed subtype identifier
- dominant semantic consequence summary
- anchor scope and subject references
- preserved event/observation/decision versus record time distinction
- optional linked family and evidence references

### 4.2 CommitIngressRequest minimums
A `CommitIngressRequest` contract must be able to carry at least:
- stable request identifier
- ingestion time
- ingress channel/mode
- incoming commit class
- acting party and/or agent reference
- target scope
- linked semantic event reference
- idempotency key
- optional evidence or source transport references

### 4.3 CommitIngressResult minimums
A `CommitIngressResult` contract must be able to carry at least:
- stable result identifier
- source request reference
- processing time
- final ingress/promotion outcome
- commit class and primary event family
- idempotency disposition
- linked promotion-trace reference
- in-force result category where promotion succeeded
- references to emitted source-truth records where created
- stable machine-readable problems

### 4.4 PromotionTrace minimums
A `PromotionTrace` contract must be able to carry at least:
- stable trace identifier
- source request and semantic-event references
- commit class and primary event family
- idempotency key/disposition
- explicit gate sequence with per-gate outcomes
- final outcome
- links to emitted source-truth records where relevant
- optional references to authority, evidence, or materialization boundary results when those were part of the path

---

## 5. Compatibility rule

Existing source-truth record contracts remain valid and separate.
This RFC does not require `AssertionRecord`, `ReviewDecision`, `AcceptedEventConsequence`, or `MaterializationResult` to embed the new event-boundary objects.

It only requires that active package examples may now point to governed package-local semantic event, ingress, and promotion-trace objects rather than leaving those identifiers implicit or support-layer-only.

---

## 6. Out of scope

This RFC does not:
- redefine the seven top-level event families
- define every future event subtype contract
- standardize transport topics, brokers, or webhook payloads
- guarantee full deployment telemetry or live bridge evidence
- replace the broader gate-sequencing fixture family

---

## 7. Outcome

After this RFC:
- semantic event objects are active and machine-distinct from transport wrappers
- ingress requests/results can express retry-safe replay posture explicitly
- promotion traces become governed active contracts rather than support-layer-only evidence
- audit reconstruction can cross the event-ingress seam without relying on prose alone
