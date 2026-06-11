# OFARM Evidence Sufficiency and Attestation Policy v0.1

Date: 2026-04-11  
Status: active companion artifact  
Scope: structured evidence-sufficiency and attestation policy for high-consequence compliance assertions, attested DocumentAssemblies, and SubmissionAssemblies

---

## 1. Purpose

OFARM already has the right high-level law:
- evidence sufficiency is an explicit enforcement gate
- high-consequence uses may not rely on stale or invalid materialization by default
- DocumentAssembly remains separate from canonical truth
- attestation is a governed publication/output action rather than a shortcut to truth

What is still missing is a small, executable structure that records why a high-consequence claim or output was allowed, refused, or routed to review.

This policy closes that gap.

---

## 2. Core stance

### 2.1 Evidence sufficiency is not an attachment checklist
Evidence sufficiency should be represented as a governed case object that links:
- the claim or output being evaluated
- the governing policy/rule posture
- the evidence bundles that support it
- the provenance and chain-of-custody posture for those bundles
- the resulting allow/review/refuse outcome

### 2.2 OFARM keeps raw source and normalized interpretation distinct
Where evidence matters, the platform should keep:
- the raw source or linked original
- the normalized interpretation used by the runtime
- provenance showing how the interpretation was derived and bound to the claim/output context

A PDF, scan, photo, or export alone is not sufficient merely because it exists.

### 2.3 Current-state reliance must remain traceable
If a high-consequence assertion or a frozen/attested output materially relies on current state, the sufficiency case should point to:
- the relevant `MaterializationBasis`
- and, for attested/frozen outputs, a retained `MaterializationSnapshot` or equivalent basis record

### 2.4 Attestation is post-assembly governance, not truth mutation
Attestation or signing does not convert a compiled output into canonical truth.
It confirms that a governed output was reviewed under the declared policy posture.

### 2.5 PassportView is not the attested output family
This policy is for:
- high-consequence compliance assertions
- attested/frozen `DocumentAssembly` family outputs
- `SubmissionAssembly` filing/delivery packages
- review/refusal cases when evidence is insufficient for those paths

It should not be used to treat a live `PassportView` as though it were already a frozen signed document.

---

## 3. When a structured sufficiency case is expected

A structured `EvidenceSufficiencyCase` should be produced when policy requires the platform to justify one of these outcomes:

1. promotion of a high-consequence compliance assertion
2. attestation/sign-off of a `DocumentAssembly` or `DossierAssembly`
3. approval or filing of a `SubmissionAssembly`
4. review-routing or refusal because the evidence posture is incomplete, contradictory, or not trustworthy enough

Routine low-consequence operations do not all need heavyweight assurance objects.
This policy is intentionally scoped to the higher-risk paths.

---

## 4. Minimum structure of an EvidenceSufficiencyCase

At minimum, the case should identify:
- the governed subject being evaluated
- the governing evidence/attestation policy references
- the claim set under evaluation
- the rule/argument chain supporting or blocking those claims
- the evidence bundles and provenance links used by the evaluation
- the materialization basis/snapshot relied upon when current state matters
- the final outcome: `ALLOW`, `REQUIRE_REVIEW`, or `REFUSE`

Conceptually, the structure should remain readable as:

`Claim or output outcome` ← `Argument/rule posture` ← `Evidence bundle + provenance`

The machine contract may stay narrower than a full assurance-case standard.
The important thing is that OFARM can explain the decision in a stable, auditable, and testable form.

---

## 5. Outcome semantics

### 5.1 ALLOW
`ALLOW` means the platform found the evidence posture sufficient for the requested high-consequence path under the declared policy.

### 5.2 REQUIRE_REVIEW
`REQUIRE_REVIEW` means the path is not safely auto-allowed, but policy still permits explicit human/governance review.
Typical reasons include partial chain-of-custody, incomplete but recoverable support, or evidence conflicts that must be resolved by a reviewer.

### 5.3 REFUSE
`REFUSE` means the path must not proceed under current evidence posture.
Typical reasons include missing required evidence, missing normalized interpretation/provenance, or material gaps that policy does not allow a reviewer to waive.

---

## 6. Guardrails

### 6.1 Do not let compiled outputs become the truth store
A `DocumentAssembly`, `DossierAssembly`, or `SubmissionAssembly` may later serve as evidence, but it is not canonical truth by itself.
The sufficiency case should still point back to authoritative basis objects.

### 6.2 Do not erase raw-versus-interpreted evidence discipline
A case that only carries a frozen output ref without the supporting raw/normalized/provenance posture is incomplete.

### 6.3 Do not auto-attest from AI assistance
AI assistance may help classify, summarize, or draft evidence handling, but an AI path must not silently create attested truth or sign-off posture.
Any attestation path remains governed by explicit authority and review policy.

### 6.4 Portable envelopes remain optional
Portable signatures or verifiable export envelopes may later be useful.
They remain optional export/attestation packaging, not internal truth law.

---

## 7. Conformance posture for this wave

This wave is intentionally narrow.
It should provide:
- a machine-validatable `EvidenceSufficiencyCase` schema
- grounded examples for allow, review, and refuse outcomes
- coverage for compliance assertion, attested dossier/document, and submission package paths
- fixture-level checks that current-state-dependent outputs point to retained basis records and that support chains remain explainable

This wave does **not** claim:
- full runtime-generated assurance graphs
- full signature/key-management workflows
- complete executor-backed publication pipelines
- a credential ecosystem for portable attestation
