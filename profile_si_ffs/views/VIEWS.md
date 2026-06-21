# Static views (governed retrieval basis for the two pilot outputs)

Status: binding view specifications. Platform v1 exposes **no** general QuerySpecification authoring/compiler surface — it ships these two predefined, versioned views. The query **law** is not deferred: both outputs carry full QuerySpecification/QueryPlanIR references, context snapshot, materialization basis, and qualification envelopes, exactly as `PassportViewMetadata` and `DocumentAssemblyMetadata` require.

The concrete `QuerySpecification` + `QueryPlanIR` JSON artifacts are shipped alongside this file. This file remains the human-readable SI profile view specification; the JSON artifacts carry the executable QuerySpecification/QueryPlanIR references used by conformance. (Required schema blocks: QuerySpecification — `target`, `graphPattern`, `selection`, `resultProfile`; QueryPlanIR — `sourceQuerySpecificationId`, `normalizedTarget`, `resolvedPathAliases`, `executionSteps`, `materializationPolicy`, `outputAssembly`.)

---

## View 1 — `view:si.ffs.spray-register.passportview.v0_1`

**Purpose:** the live register the farmer and advisor see daily; freshness and gaps always visible.

- **Twin / scope / time:** COMPLIANCE · anchor scope = one Farm · evaluation time policy NOW.
- **Retrieves:** accepted executed intervention consequences (plant-protection kind) joined to their `ExecutionRecordPayload` details (product binding, dose, parcel/extent, crop, operator, equipment, event time), plus **pending claims** (drafts/under-review) explicitly marked as not-accepted, plus advisory flags linked to each record.
- **Ordering:** event time descending; filterable by parcel, crop cycle, season.
- **Freshness:** materialization must be FRESH for the register body; STALE renders only with a banner and is barred from export.
- **Refusal/disclosure:** unresolved product bindings, disputed records, and post-sync discrepancies render as visible exception rows — never silently omitted, never silently promoted. If the materialization basis cannot be produced, the view refuses with a `RuntimeProblem`.
- **Qualification:** every response carries a `ResultQualificationEnvelope` (truth posture, staleness class, evidence sufficiency, permission class, allowed/blocked use classes).

## View 2 — `view:si.ffs.inspection-register.documentassembly.v0_1`

**Purpose:** the frozen, exportable register the farmer hands to an inspection (PDF + JSON; the JSON carries full metadata, the PDF renders the qualification legend with record identifiers).

- **Twin / scope / time:** COMPLIANCE · anchor scope = one Farm · evaluation time policy AS_OF (the requested period, e.g. season or date range).
- **Freeze semantics:** assembles **only** accepted consequences within the window from a fresh materialization; freezes with `MaterializationSnapshot`, `MaterializationBasis`, `ContextSnapshot` (including the product-register `ReferenceSnapshot`s in force), and the auto-generated `EvidenceSufficiencyCase`.
- **Gaps are content:** records that exist but did not reach accepted state appear in a clearly-marked annex (claims pending review, disputed, unresolved bindings) **without promotion** — annexing never makes truth (Constitution §10.12). The document never pretends completeness it does not have; the completeness statement enumerates known gaps.
- **Refusal:** if the evidence floor for the assembly is unmet or the materialization cannot be made FRESH for the window, generation refuses or routes to review — it does not emit a degraded document silently.
- **Identification:** every exported document carries its `DocumentAssembly` id, version label, freeze time, and digest, so a later inspection can verify the artifact against the store.

## Conformance hooks

`../../conformance/CONFORMANCE.md` tests: PassportView refusal/disclosure behavior · DocumentAssembly freeze/trace completeness · stale-materialization export bar · annex-without-promotion.
