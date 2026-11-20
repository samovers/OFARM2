# OFARM Event Grammar and Commit Matrix v0.1

Date: 2026-04-08  
Status: phase-5 baseline artifact  
Scope: normative definition of the small stable top-level event grammar and the commit/promotion rules that sit above it

---

## 1. Purpose

OFARM needs:
- a **small stable top-level event grammar**
- a **clean distinction between event families and commit classes**
- a **promotion matrix** that prevents weak inputs from silently becoming hard truth

This artifact provides that baseline.

---

## 2. Event families vs commit classes

These are not the same thing.

- **Event family** answers: what kind of world event or governed act is this?
- **Commit class** answers: what kind of truth-bearing or truth-supporting record is entering OFARM authority?

One event may create multiple records and consequences.

Example:
- an irrigation action is an **InterventionEvent**
- the farmer’s claim that it happened enters as an **operation claim**
- attached photos/telemetry/receipts enter as **evidence records**
- later review may accept the event consequence into current state

---

## 3. Small stable top-level event grammar

OFARM fixes these top-level event families:

### 3.1 StructureEvent
Used for creation/change/end of durable configuration or scope-bearing objects.

Typical examples:
- field boundary change
- zone definition change
- facility registration/change
- equipment registration/change
- role-assignment lifecycle change
- pack/profile activation or deactivation

### 3.2 ObservationEvent
Used for observed, measured, sampled, scouted, or inspected reality.

Typical examples:
- scouting observation
- lab sampling
- soil measurement
- EO-derived field observation
- machine-sensed field measurement

### 3.3 OccurrenceEvent
Used for natural, accidental, biological, contamination, damage, or failure occurrences that are not primarily deliberate interventions.

Typical examples:
- frost incident
- hail damage
- pest outbreak occurrence
- disease occurrence
- contamination incident
- equipment failure occurrence

### 3.4 InterventionEvent
Used for deliberate human or automated action intended to affect crops, land, lots, facilities, or equipment.

Typical examples:
- planting
- tillage
- fertilizing
- spraying
- irrigation
- pruning
- harvest action
- cleanout / sanitation action
- maintenance action

### 3.5 MaterialEvent
Used for custody, identity, storage, transformation, split/merge, movement, or disposal of lots/resources/materials.

Typical examples:
- lot creation
- lot split or merge
- transfer to storage
- dispatch
- receipt
- reclassification
- disposal

### 3.6 EvidenceEvent
Used for evidentiary capture, attachment, attestation, issue, receipt, or signing acts.

Typical examples:
- receipt scan captured
- photo evidence attached
- certificate issued/received
- lab report ingested
- document signed/attested

### 3.7 GovernanceEvent
Used for formal review, decision, submission, inspection, enforcement, or correction actions.

Typical examples:
- review acceptance/rejection
- inspection opened/updated/closed
- nonconformity raised
- corrective action mandated/completed
- compliance submission filed
- certification decision
- supersession decision

---

## 4. Event-family selection rule

Every event gets **one primary event family**.

Rule:
- choose the family by the event’s **dominant semantic consequence**
- represent additional consequences through linked records/consequences, not by inventing a new top-level family

Example:
- harvest action = primary **InterventionEvent**
- produced lot creation = linked **MaterialEvent consequence**
- receipt photo captured during delivery = linked **EvidenceEvent**

This keeps grammar small without flattening complexity.

---

## 5. Pack-level subtyping rule

Packs may:
- define scoped subtypes under a top-level family
- add family-specific attributes
- add evidence rules
- add workflow consequences
- add views/reports/queries

Packs may not:
- invent arbitrary new top-level families without governance

---

## 6. Commit classes

OFARM fixes these baseline commit classes:

### 6.1 note
Raw or weakly structured human input with no direct hard-truth effect.

### 6.2 observation assertion
Typed claim that something was seen, measured, sampled, or otherwise observed.

### 6.3 hypothesis assertion
Typed possible explanation or suspected condition, not yet treated as hard truth.

### 6.4 structure assertion
Typed claim about structural/configuration/scope state such as boundaries, zones, role assignments, or pack/profile activation state.

### 6.5 operation claim
Typed claim that an intervention or deliberate action was intended or performed.

### 6.6 evidence record
Raw or structured supporting artifact or evidentiary statement.

### 6.7 compliance assertion
Typed claim relevant to compliance, restriction, eligibility, certification, or attested status.

### 6.8 governance decision
Formal accept/reject/contest/supersede/approve/mandate decision.

### 6.9 advisory output
Rule/model/human-generated recommendation, warning, forecast, or scenario output.

---

## 7. In-force result categories

These are not additional input commit classes.
They are stronger in-force outcomes that may be derived after governance.

OFARM recognizes at least these result categories:
- **accepted structural state**
- **accepted observation/occurrence state**
- **accepted executed intervention consequence**
- **accepted material state**
- **compliance fact**

This distinction is intentional:
- weak input enters as a commit class
- stronger truth appears only after validation, evidence, and governance where required

---

## 8. Promotion matrix

| From | May become / yield | Minimum requirements | Forbidden shortcuts |
|---|---|---|---|
| note | observation assertion, hypothesis assertion, structure assertion, operation claim | typing, source attribution, scope | cannot directly become compliance fact or accepted executed intervention consequence |
| observation assertion | accepted observation/occurrence state; support for compliance assertion | validation; evidence where policy requires; review where policy requires | cannot directly become compliance fact without compliance path |
| hypothesis assertion | advisory use; may support review attention; may be replaced by better-typed assertion | source, scope, confidence | cannot directly become hard truth or compliance fact |
| structure assertion | accepted structural state | validation; conflict checks; governance/review where required | cannot silently rewrite structure state if contested |
| operation claim | accepted executed intervention consequence | validation; evidence sufficiency where required; review where policy requires | cannot silently count as executed fact without the required path |
| evidence record | support for other classes | integrity, provenance, linkage | does not create hard truth by itself |
| compliance assertion | compliance fact | required evidence; applicable policy; governed review/decision | cannot auto-promote from weak support alone |
| governance decision | in-force status change, supersession, acceptance/rejection, compliance fact where allowed | valid authority, scope, traceability | may not bypass constitutional evidence rules |
| advisory output | tasks, warnings, hypotheses, review requests | provenance and model/rule identification | cannot directly create compliance fact or accepted executed intervention consequence |

---

## 9. Why this structure is cleaner

This structure fixes three old problems at once:

1. **operation record no longer mixes claim and verified execution**
   - claim enters as operation claim
   - accepted execution appears only after the governed path

2. **compliance fact no longer mixes claim and governed result**
   - claim enters as compliance assertion
   - compliance fact appears only after the governed path

3. **packs no longer need new top-level event families just to express nuance**
   - nuance lives in subtypes, attributes, evidence rules, and consequences

---

## 10. Default safety rule

If OFARM lacks a declared safe promotion path, the default is:
- **do not auto-promote**
- keep the weaker class
- require explicit governance or additional evidence

This is a constitutional safety bias, not a temporary implementation trick.
