# OFARM RuntimeProblem Reason Code Registry RFC v0.1

Date: 2026-05-16  
Status: accepted RFC extension by AAI-CP2; active substance unless overridden by active baseline or a later accepted RFC  
Scope: define registry-backed reason codes for public OFARM Platform operations

## 1. Problem statement

`OFARM_RuntimeProblem_schema_v0_1.json` provides a reusable failure envelope, but `reasonCode` is currently open-ended. AI agents, SDKs, and applications need stable reason codes to behave safely.

Without a registry, apps may handle these cases inconsistently:

- authority denied
- human approval required
- evidence insufficient
- identity unresolved
- unit unresolved
- stale materialization
- pack conflict
- permission redaction
- duplicate import
- retry conflict

## 2. Core stance

A RuntimeProblem reason code is a governed runtime contract, not free-form UI text.

Each reason code should define:

```text
code
family
severity
retryable
humanReviewRequired
redactionSensitive
safeUserMessage
developerMeaning
requiredRemediation
relatedTraceTypes
safeUiBehavior
```

## 3. Required reason-code families

| Family | Example reason codes |
|---|---|
| Authority | `AUTHORITY_DENIED`, `HUMAN_APPROVAL_REQUIRED`, `DELEGATION_REVOKED`, `SCOPE_NOT_AUTHORIZED` |
| Evidence | `EVIDENCE_INSUFFICIENT`, `EVIDENCE_REFERENCE_UNAVAILABLE`, `EVIDENCE_REDACTED` |
| Identity | `IDENTITY_UNRESOLVED`, `DUPLICATE_IMPORT_AMBIGUOUS`, `PRODUCT_BINDING_UNRESOLVED`, `ACTOR_BINDING_UNRESOLVED` |
| Unit/calculation | `UNIT_UNRESOLVED`, `FORMULA_UNAVAILABLE`, `ROUNDING_POLICY_MISSING`, `CALCULATION_BASIS_INCOMPLETE` |
| Materialization | `MATERIALIZATION_STALE`, `MATERIALIZATION_INVALID`, `MATERIALIZATION_BASIS_MISSING` |
| Query | `QUERY_ALIAS_STALE`, `QUERY_ALIAS_AMBIGUOUS`, `QUERY_AUTHORIZATION_FILTERED` |
| Publication | `HIGH_CONSEQUENCE_BLOCKED`, `PUBLICATION_BASIS_INCOMPLETE`, `DOCUMENT_ASSEMBLY_REQUIRES_ANNEX` |
| Pack/profile | `PACK_CONFLICT`, `PACK_GOVERNANCE_REQUIRED`, `PROFILE_NOT_ACTIVE` |
| Import/source fidelity | `IMPORT_CANDIDATE_ONLY`, `SOURCE_FIDELITY_LOSS`, `LOSS_MAP_REQUIRED` |
| Retry/idempotency | `RETRY_CONFLICT`, `IDEMPOTENCY_REPLAY_REUSED`, `IDEMPOTENCY_REPLAY_CONFLICT` |
| Permission/redaction | `PERMISSION_REDACTED`, `TENANT_BOUNDARY_BLOCKED`, `DATA_SOVEREIGNTY_RESTRICTION` |
| Correction/dispute | `DISPUTE_OPEN`, `CORRECTION_REQUIRED`, `SUPERSEDED_RECORD_USED` |

## 4. Safe UI behavior

Reason codes must distinguish:

```text
data does not exist
data exists but is permission-limited
data exists but is redacted
data exists but is stale
data exists but is disputed
data exists but identity is unresolved
data exists but evidence is insufficient
```

This prevents apps from displaying `No records found` when records exist but cannot be shown.

## 5. Machine contract produced by this RFC

Promoted schema:

```text
OFARM_RuntimeProblemReasonCodeRegistry_schema_v0_1.json
```

## 6. Conformance obligations

A public operation fails conformance if it returns an unregistered reason code, omits retryability for a failure, or gives user text that overstates authority, evidence, freshness, or compliance posture.

## AAI-CP2 acceptance boundary — 2026-05-16

This RFC is accepted only for the controlled CP2 public-surface layer: public operation description, preflight/dry-run, runtime problem reason codes, trace retrieval, source-fidelity qualification, public read-model envelopes, and result qualification.

It does not promote agent actorship, agent run/trace/handoff, tool manifests, world-model runtime, EvidenceNeed, ObservationRequest, production readiness, autonomous compliance decisioning, two-agent compatibility, or external-standard readiness.
