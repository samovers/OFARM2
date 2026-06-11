# OFARM AI-Facing Result Qualification and Trace Surface RFC v0.1

Date: 2026-05-16  
Status: accepted RFC extension by AAI-CP2; active substance unless overridden by active baseline or a later accepted RFC  
Scope: make the CP1 release-qualification gate contract-shaped for AI-facing, public-operation, state-affecting, and high-consequence surfaces

## 1. Problem statement

AAI-CP1 made AI-facing release qualification an active baseline gate. CP2 supplies the minimum accepted RFC and machine-contract surface required to execute that gate without treating AI output, caches, materializations, previews, or public tool success as truth or governance success.

Without a contract-shaped qualification and trace surface, a platform could satisfy CP1 only in prose while still hiding material limits from users, downstream systems, SDKs, or AI agents.

## 2. Core decision

Any AI-facing, public-operation, state-affecting, publication-affecting, or high-consequence result must return or link to a `ResultQualificationEnvelope` when material limitations may affect reliance.

The qualification must expose, where applicable:

```text
basis / source references
as-of timestamp
surface class
twin scope
truth posture
authority level
candidate status
dispute/correction/supersession status
staleness class
evidence sufficiency
permission/redaction posture
data-absence reason
allowed and blocked use classes
high-consequence use eligibility
trace references
safe display hints
```

## 3. No hidden truth rule

A result qualification does not create canonical truth. It describes the reliance posture of a result. Canonical truth remains assertion/history-first, and current state remains a governed materialization.

A qualified result must not be displayed as complete compliance-ready truth when the envelope reports stale, advisory-only, candidate-only, evidence-insufficient, permission-limited, redacted, disputed, corrected, superseded, or unknown posture.

## 4. Trace retrieval rule

A high-consequence or state-affecting public operation must return or link to retrievable trace evidence subject to authority and redaction. Trace retrieval must expose gate outcomes for the relevant surface family, including authorization, promotion, query, materialization, publication, pack activation, import, calculation, or preflight.

A trace may be redacted or access-denied, but the result must still indicate that redaction or denial occurred rather than presenting missing information as if no record exists.

## 5. Public read-model rule

A public read model must be wrapped in `PublicReadModelEnvelope` or an equivalent contract shape that carries qualification, problems, trace references, and next actions. A payload body by itself is insufficient for high-consequence reliance.

## 6. Source-fidelity rule

When a public result depends on imported or external source material, the platform must preserve source-fidelity posture through `SourceFidelityEnvelope` or an equivalent traceable mechanism. Source data, import payloads, and external-system records remain candidate/evidence/source material until accepted through OFARM governance.

## 7. RuntimeProblem reason-code rule

Runtime problems returned by public surfaces must use registered reason codes. A reason code must distinguish absent data from redacted, permission-limited, stale, disputed, unresolved, evidence-insufficient, or blocked data.

## 8. Required machine contracts

AAI-CP2 promotes the following active machine contracts:

```text
OFARM_PublicOperationDescriptor_schema_v0_1.json
OFARM_PreflightRequest_schema_v0_1.json
OFARM_PreflightResult_schema_v0_1.json
OFARM_RuntimeProblemReasonCodeRegistry_schema_v0_1.json
OFARM_ResultQualificationEnvelope_schema_v0_1.json
OFARM_TraceRetrievalResult_schema_v0_1.json
OFARM_PublicReadModelEnvelope_schema_v0_1.json
OFARM_SourceFidelityEnvelope_schema_v0_1.json
```

`OutputAssemblyPreviewRequest` and `OutputAssemblyPreviewResult` remain unpromoted in CP2. They may be promoted later only through an output-assembly-specific decision.

## 9. Conformance obligations

A platform fails CP2 conformance if:

- a high-consequence or state-affecting result lacks machine-readable qualification;
- a preflight or dry-run creates authoritative state;
- a public operation hides stale, redacted, permission-limited, disputed, candidate-only, or evidence-insufficient posture;
- a blocked operation lacks a registered RuntimeProblem reason code;
- trace retrieval cannot represent gate outcomes, redactions, or access denial;
- a public read model exposes a payload without a qualification envelope;
- source-fidelity loss is hidden when imported or external data supports the result;
- public-operation success is presented as governance success.

## 10. Non-promotion boundary

This RFC does not promote software-agent actorship, AgentRunEnvelope, AgentRunTrace, AgentHandoffEnvelope, AgentToolManifest, world-model runtime, EvidenceNeed, ObservationRequest, autonomous compliance decisioning, two-agent compatibility, production readiness, live-registry integration, legal advice, or external-standard readiness.
