# OFARM Identity and Lifecycle RFC v0.1

Date: 2026-04-08  
Status: accepted post-charter RFC  
Scope: formalize identity, versioning, and lifecycle semantics for the first set of OFARM objects most likely to cause implementation divergence

---

## 1. Problem statement

RC2 says that canonical objects must have:
- stable identity
- scope
- lifecycle
- lineage rules where relevant

That is directionally correct, but still too abstract for implementation.

The most dangerous unresolved questions are:
- when a changed thing is still the **same identity**
- when it is a **new version/revision** of the same identity
- when it is a **new identity**
- how split, merge, overlap, replacement, and failure are represented

This RFC closes that gap for the first priority set:
- Field
- ManagementZone / MicroclimateZone
- CropCycle
- Lot
- Equipment / Tool
- Facility / StorageLocation / Container

---

## 2. Core identity model

### 2.1 Three layers must stay distinct

OFARM must distinguish:

1. **durable identity**  
   the thing that persists through time as the same governed referent

2. **identity revision**  
   a versioned representation of the durable identity when boundary, structure, metadata, or classification changes without breaking continuity

3. **time-bounded state**  
   what is currently true of the identity or its revision during some validity interval

This distinction is crucial.

Without it, implementers tend to confuse:
- state change
- version change
- identity replacement

### 2.2 Durable identity test

A thing keeps the same durable identity only if all of the following still hold:

- **referent continuity**: it still refers to the same governed real-world thing or managed unit
- **one-to-one continuity**: it did not become many things or absorb many things in a way that destroys one-to-one lineage
- **type continuity**: it is still the same constitutional object kind
- **accountability continuity**: its core accountable/managed role has not been reconstituted into a different governed unit
- **purpose continuity**: the thing still serves the same core identity purpose, even if attributes change

If these conditions fail, OFARM should create a new durable identity and express lineage explicitly.

### 2.3 Identity revision rule

Create a new **identity revision** when:
- the durable identity remains the same
- but important governed characteristics change in a way that later queries, reviews, or lineage may need to distinguish

Typical revision triggers:
- geometry/boundary updates
- structural metadata changes
- operational classification changes
- internal layout changes
- registration/detail updates
- non-destructive corrections to the identity-bearing object

A revision is not a new identity.

### 2.4 New identity rule

Create a **new durable identity** when any of the following happens:

- split into two or more independently governed referents
- merge from two or more previously distinct governed referents
- replacement by a different real-world referent
- reconstitution into a different accountable/managed unit
- purpose change so strong that the old and new thing should not answer as “the same governed object”
- cohort continuity is broken in a way that destroys the old identity basis
- a new agronomic attempt or new traceability object begins rather than the old one continuing

### 2.5 Lifecycle lineage

When OFARM creates a new identity or revision, it must preserve lineage explicitly.

At minimum the lifecycle relation set should support:
- **revises**
- **supersedes**
- **splitFrom / splitInto**
- **mergedFrom / mergedInto**
- **succeeds / precededBy**
- **overlapsWith**
- **replaces / replacedBy**
- **derivedFrom** where a weaker relationship is the only justified one

These are lineage relations, not reasons to collapse identities.

---

## 3. Field semantics

### 3.1 Field identity basis
A **Field** is a durable managed land unit used as a primary operational farming scope.

Its durable identity is based on:
- managed land continuity
- accountable operational continuity
- one-to-one continuity as a field-level governed unit

### 3.2 Same field, new revision
Keep the same Field identity and create a new revision when:
- the boundary is corrected or refined
- small regulated/setback/buffer adjustments change geometry but not the basic field unit
- metadata or identifiers are corrected
- the field remains the same one-to-one managed unit

### 3.3 New field identity
Create a new Field identity when:
- one field is intentionally split into separately governed operational fields
- two or more fields are merged into one governed field
- accountability or management scope is reconstituted so the field is no longer the same operational unit
- a boundary change is so substantial that the previous and new unit should not be treated as the same field

### 3.4 Boundary changes must not hide lineage
Boundary change alone is not enough to decide “same field” or “new field.”
The deciding factor is governed operational continuity.

---

## 4. Zone semantics

### 4.1 Durable versus ephemeral zones
A **ManagementZone** or **MicroclimateZone** becomes a constitutional identity-bearing zone only when it is intentionally governed as a recurring zone.

Ephemeral one-off analysis masks, temporary heatmaps, or ad hoc advisory overlays are **not** automatically constitutional zones.

### 4.2 Same zone, new revision
Keep the same zone identity and create a new revision when:
- zone geometry is refined
- the zone remains the same recurring governed zone
- purpose continuity remains intact

### 4.3 New zone identity
Create a new zone identity when:
- one zone is split into separately governed zones
- multiple zones are merged into one zone
- the zone purpose changes materially
- the zone no longer has one-to-one continuity as the same recurring governed zone

### 4.4 Overlap rule
Overlapping zones are allowed when they express:
- different zone families
- different purposes
- different validity intervals

Within the same zone family and same validity interval, overlap should be explicit and explainable rather than accidental.

---

## 5. CropCycle semantics

### 5.1 CropCycle identity basis
A **CropCycle** is the governed identity of a particular cultivation attempt or realized cycle on a scope.

Its identity is based on:
- crop/cultivation attempt continuity
- scope continuity
- operational continuity of that attempt

### 5.2 Same CropCycle
Keep the same CropCycle identity when:
- the cycle continues through normal growth-stage change
- the cycle experiences stress, delay, damage, or partial failure but remains the same cultivation attempt
- the cycle remains the same managed attempt even if expected outcome changes

### 5.3 Failed cycle rule
A failed cycle remains the same CropCycle if the failure is the outcome of that attempt and no new establishment/re-establishment has begun yet.

### 5.4 New CropCycle identity
Create a new CropCycle identity when:
- a replant/re-establishment starts a new cultivation attempt
- a previous cycle is explicitly terminated and a new one begins
- one parent cycle diverges into separately managed or separately harvested child cycles with distinct operational identities
- intentional intercropping or relay-cropping creates concurrent distinct cycles on the same scope

### 5.5 Split and overlap
If one cycle splits into multiple separately governed child cycles:
- child cycles get new identities
- lineage to the parent must remain explicit
- the parent may remain as the planning/lineage origin, but child-specific truth must live on the child identities

Concurrent overlapping CropCycles are allowed, but only with explicit overlap relation and scope clarity.

---

## 6. Lot semantics

### 6.1 Lot identity basis
A **Lot** is a durable traceability identity for a materially coherent cohort under one governed traceability basis.

The lot basis is primarily:
- cohort continuity
- traceability continuity
- claim/compliance continuity where relevant

### 6.2 Same lot, new revision/state
Keep the same Lot identity when:
- the lot changes storage location
- the lot receives metadata corrections
- the lot gains additional references or commercial labels
- the lot remains the same materially coherent cohort under the same traceability basis

### 6.3 New lot identity
Create a new Lot identity when:
- the lot is split into distinct traceability cohorts
- multiple lots are merged or commingled into one cohort
- transformation or handling breaks the previous cohort identity
- certification/claim basis is reset in a way that requires a new traceability object
- material continuity is no longer safely one-to-one

### 6.4 Commercial references are not enough
Commercial shipment/order/invoice identifiers do **not** automatically create a new Lot identity.

They may be:
- references attached to the same lot
- evidence
- shipment or delivery context

A new Lot identity is created only when the traceability cohort itself changes.

### 6.5 Lot is the red-flag object
Lot identity should be treated as a red-flag implementation area.

If the system cannot clearly justify cohort continuity, it should prefer:
- explicit lineage
- a new lot identity
- preserved derivation trace

over hidden ambiguity.

---

## 7. Equipment, facility, storage location, and container semantics

### 7.1 Equipment / Tool
Equipment or tool identity is based on the durable real-world asset.

Keep the same identity when:
- configuration changes
- ownership changes
- maintenance occurs
- the same asset continues

Create a new identity when:
- a different asset replaces it
- the asset is reconstituted in a way that makes “same asset” false in governance or traceability terms

### 7.2 Facility
A **Facility** is a durable governed operational place.

Keep the same Facility identity when:
- layout changes
- metadata changes
- the same operational place continues

Create a new identity when:
- the facility is split into separately governed facility identities
- multiple facilities are merged into one governed facility
- the accountable/operational place is replaced rather than revised

### 7.3 StorageLocation
A **StorageLocation** is a scoped containment/place identity inside or relative to a facility or storage system.

It may:
- remain the same identity across revisions
- be retired and replaced
- participate in lineage when restructured

### 7.4 Container
A **Container** is a containment unit distinct from the lot/material it contains.

For reusable containers:
- keep the same identity across multiple occupancy episodes

For single-use containers:
- first-class identity is only needed when traceability, evidence, or operational control justifies it

A changed occupant does not create a new Container identity.

---

## 8. Relationship between durable identity and time-bounded state

Durable identity answers:
- what thing this is

Identity revision answers:
- which governed version of that thing is being referenced

Time-bounded state answers:
- what is true of that identity or revision at a given time

This means:
- a field may keep the same identity, have several revisions, and many changing states
- a lot may keep the same identity while moving across storage states
- a crop cycle may stay the same identity while moving from planned to damaged to failed
- an equipment identity may remain the same while service status changes many times

Implementers must not create new durable identities just because state changed.

---

## 9. Minimal conformance expectations for this RFC

A conforming implementation should be able to decide, for the covered object families:

- same identity vs new revision
- same identity vs new identity
- required lineage relation after split/merge/replacement
- whether overlap is permitted and how it is represented
- how durable identity differs from time-bounded state

At minimum, conformance fixtures should include:
- field boundary correction vs field split
- durable zone vs ephemeral advisory mask
- failed crop cycle vs replanted crop cycle
- overlapping relay/intercrop cycles
- lot split, merge, commingling, and shipment-reference scenarios
- reusable container with multiple occupancy episodes
- facility restructuring versus facility replacement

---

## 10. Main patch consequences

This RFC requires:
- Constitution patching in section 7 and conformance direction
- Alignment Register update where needed
- no Platform patch yet, except later RFCs may depend on these rules

---

## 11. Hard stop question

The RFC succeeds only if two independent implementers, given the same scenario, can reach the same answer to:

**Is this the same durable identity, a new revision of the same identity, or a new identity with lineage?**
