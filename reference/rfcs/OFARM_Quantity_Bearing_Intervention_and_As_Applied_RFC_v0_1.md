# OFARM Quantity-Bearing Intervention and As-Applied RFC v0.1

Date: 2026-05-12  
Status: accepted post-charter RFC  
Scope: close the smallest active carrier gap for quantity-bearing agronomic recommendation, prescription, planned operation, operation claim, as-applied evidence, accepted execution, correction, and dispute payloads without changing OFARM truth law

---

## 1. Problem statement

The active OFARM package already separates advisory output, operation claims, evidence, review decisions, accepted consequences, and current-state materializations.
That separation is correct and must be preserved.

The agronomic gap is payload depth.
A record may currently prove that a plan, assertion, event, or accepted consequence exists, but not enough about:

- product or input identity
- target organism or agronomic target
- rate, dose, concentration, total quantity, carrier volume, or application volume
- intended extent versus actual extent
- actor, contractor, machine, controller, calibration, and source payload
- actual-versus-planned deltas
- partial work, failed pass, manual correction, and dispute lineage

Without a small carrier patch, OFARM can appear auditable while losing the practical agronomic content needed for field reconstruction.

---

## 2. Core stance

### 2.1 Two small carriers, not one CRUD application object

This RFC creates two bounded payload carriers:

- `InterventionIntentPayload`
- `ExecutionRecordPayload`

The split is intentional.
A recommendation, prescription, and planned operation are intent-side payloads.
A claim, as-applied evidence, accepted execution detail, correction, and dispute are execution/history-side payloads.

The carriers may reference each other, but they must not collapse the legal and governance meanings of their surrounding OFARM records.

### 2.2 No promotion shortcut

These payloads do not create execution truth by themselves.
They support existing event, assertion, review, evidence sufficiency, promotion, accepted-consequence, and materialization law.

The default boundaries remain:

- recommendation is advisory only
- prescription is authorised intent, not execution
- planned operation is operational intent, not execution
- operation claim is asserted history, not accepted execution
- as-applied evidence is evidence, not accepted consequence
- accepted execution requires review/evidence sufficiency/promotion
- correction is a new historical assertion, not an edit path
- dispute remains reconstructable and does not silently drive high-consequence materialization

### 2.3 Quantities must be explicit

Every quantity parameter carried by these contracts must include both:

- `quantityKindRef`
- `unitRef`

Original reported value and unit labels should be retained where available.
Normalised values may be carried, but must not replace the original evidence basis.

### 2.4 External exchange formats stay exchange surfaces

This RFC is compatible with ADAPT, ISOXML, EFDI, ISOBUS DDI mappings, and machine-timelog sources.
Those are exchange and evidence surfaces.
They do not become OFARM truth stores, and importing them does not bypass authority, evidence, review, or promotion.

---

## 3. New active contract families

This RFC creates these active machine-contract families:

- `03_machine_contracts/schemas/agronomic/OFARM_InterventionIntentPayload_schema_v0_1.json`
- `03_machine_contracts/schemas/agronomic/OFARM_ExecutionRecordPayload_schema_v0_1.json`

It also adds optional additive bridge references to existing active schemas:

- `PlannedIntervention.interventionIntentPayloadRefs`
- `AssertionRecord.interventionIntentPayloadRefs`
- `AssertionRecord.executionRecordPayloadRefs`
- `SemanticEventEnvelope.interventionIntentPayloadRefs`
- `SemanticEventEnvelope.executionRecordPayloadRefs`
- `AcceptedEventConsequence.executionRecordPayloadRefs`

These fields are additive references only.
They do not change the meaning of the existing objects.

---

## 4. InterventionIntentPayload minimums

An `InterventionIntentPayload` must be able to carry at least:

- stable payload identifier
- intent class: recommendation, prescription, planned operation, cancellation, or supersession
- intent state
- creation time and creator
- subject and target scope
- intervention kind
- intended action
- intended time window
- one or more quantity parameters with quantity kind and unit
- evidence basis references
- promotion boundary

It may also carry:

- crop-cycle reference
- target extent reference
- crop, target-organism, product, and input bindings
- thresholds
- observation and measurement evidence references
- authority and delegation references
- contractor assignment
- machine, weather, and variable-rate-map constraints
- derived-from or supersedes relations
- exchange binding references

### 4.1 What it must not do

`InterventionIntentPayload` must not:

- make an advisory recommendation authoritative
- make a prescription prove work occurred
- make a planned operation an accepted execution
- create inventory, withholding-period, compliance, or current-state effects directly
- hide product, rate, unit, or threshold ambiguity behind free text

---

## 5. ExecutionRecordPayload minimums

An `ExecutionRecordPayload` must be able to carry at least:

- stable payload identifier
- record class: operation claim, as-applied evidence, accepted execution detail, correction, or dispute
- record state
- capture time
- subject and anchor scopes
- effective execution interval
- actor, operator, contractor, or machine references where available
- execution extent and extent-basis posture
- actual action details
- source payload reference
- evidence references
- promotion boundary

Accepted execution details must additionally carry:

- review decision reference
- evidence sufficiency case reference
- accepted event consequence reference
- actual quantity parameters

Corrections must carry correction lineage.
Disputes must carry disputed-record reference and counter-evidence.

### 5.1 What it must not do

`ExecutionRecordPayload` must not:

- overwrite earlier claims or evidence
- treat machine logs as accepted truth by import alone
- silently turn partial application into whole-field treatment
- merge accepted and disputed records into one projection
- hide missing rate, missing product identity, missing calibration, or ambiguous extent

---

## 6. Relationship to existing active law

### 6.1 PlannedIntervention

`PlannedIntervention` remains a planning/local-knowledge artifact.
It may reference an `InterventionIntentPayload`, but that reference does not make the plan an execution record.

### 6.2 AssertionRecord

An operation claim may reference an `ExecutionRecordPayload`.
The assertion remains an assertion until promotion/review accepts a consequence.

### 6.3 SemanticEventEnvelope

A semantic event may reference intent and execution payloads to preserve event context.
The envelope still follows the event-ingress and promotion boundary law.

### 6.4 AcceptedEventConsequence

An accepted consequence may reference an accepted execution detail payload.
The accepted consequence is still created only through the governed review/promotion path.

### 6.5 EvidenceSufficiencyCase

The existing `EvidenceSufficiencyCase v0.2` remains the active gate for intervention evidence sufficiency.
No `v0.3` schema is required in this phase.

Existing insufficiency codes such as `MISSING_NORMALIZED_INTERPRETATION`, `MACHINE_RECORD_PARTIAL`, `HUMAN_MACHINE_CONFLICT`, `AMBIGUOUS_PRODUCT_ID`, and `BASIS_NOT_RETAINED` are sufficient for the Phase 3 fixtures.

---

## 7. Conformance expectation

A conforming implementation or package must prove at least:

1. recommendations remain advisory
2. prescriptions carry authority and quantity semantics but do not become execution
3. planned operations reference intent payloads but do not become accepted consequences
4. operation claims with missing rate remain claims or review-required records
5. as-applied evidence preserves source payload, actual quantities, machine/controller/calibration context, and partial extent posture
6. accepted execution is limited to the reviewed sub-extent and reviewed quantity basis
7. corrections supersede without deleting original claims
8. disputes remain visible and excluded from high-consequence materialization unless explicitly resolved
9. quantity parameters cannot omit quantity kind or unit
10. external machine/import payloads are evidence surfaces, not truth stores

---

## 8. Out of scope

This RFC does not:

- create the full partial-extent / geometry-basis carrier
- create the agronomic code-binding profile
- create query/output reconstruction policy
- update baseline law text directly
- adopt ADAPT, ISOXML, EFDI, ISOBUS DDI, or AIM as OFARM's canonical truth model
- create a universal operation ontology
- weaken promotion, authority, or evidence gates

---

## 9. Phase closure

This RFC closes Phase AGR-P3 at the carrier-shell level.

Remaining follow-on phases:

- AGR-P4: partial extent and geometry basis
- AGR-P5: agronomic code-binding and standards profile
- AGR-P6: query/output reconstruction
- AGR-P7: baseline harmonisation after accepted RFC/contract stability
