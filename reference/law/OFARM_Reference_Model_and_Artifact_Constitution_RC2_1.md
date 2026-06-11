# OFARM Reference Model and Artifact Constitution (RC2.1)

Date: 2026-04-11  
Status: release candidate 2.1 (cross-RFC harmonized post-charter baseline; wave-6 closure-aligned; AGR-P7 agronomic carrier harmonization applied; ONT-SEMINT v0.3 semantic-integrity baseline harmonisation applied)  
Role: model law and artifact constitution for OFARM 2.0  
Last harmonized: 2026-05-14 — ONT-SEMINT v0.3 semantic-integrity baseline harmonisation

---

## 1. Purpose and scope

### 1.1 Purpose
OFARM defines the reference model, artifact system, and constitutional rules for a semantically native crop-farming operating standard.

The Constitution answers:
- what OFARM means
- what kinds of artifacts exist
- how truth, review, and current state work
- how packs, profiles, and extensions are allowed to modify context
- how advisory and compliance semantics are separated
- how outputs, queries, and conformance are governed

### 1.2 Scope
This Constitution covers:
- shared semantic positioning and alignment method
- semantic layers
- artifact taxonomy
- pack/profile/extension/local-artifact law
- identity, scope, and authority principles
- time, truth, event, commit, and output law
- query law
- conformance baseline

It does **not** define:
- runtime service topology
- UI behavior
- deployment architecture
- execution-engine choices
- performance optimizations
- product orchestration details

Those belong to OFARM Platform.

### 1.2a Crop-only release boundary
This baseline is crop-farming operational law.
Livestock-specific identity, welfare, feeding, treatment, movement, herd/flock, and animal-health semantics are outside this release.
They require a future explicitly accepted livestock profile or sister model and may not be inferred by silently reusing crop-cycle, lot, intervention, or crop-observation abstractions.

### 1.3 Core outcome
OFARM is intended to become the strongest crop-farming operational standard built on top of the standards ecosystem, not a private semantic universe outside it.

---

## 2. Non-goals and anti-goals

### 2.1 Non-goals
OFARM 2.0 does not try to:
- preserve OFARM 1.x names, APIs, or structures
- standardize a public expert query syntax in v2
- standardize every future ecosystem capability before the core is coherent
- replace every external ontology, API, or exchange format
- standardize livestock-specific semantics in the current crop-farming release

### 2.2 Anti-goals
OFARM must not become:
- a **parallel semantic universe** that duplicates public standards unnecessarily
- a system where **exchange payloads or flat projections become truth**
- a standard where **hidden product logic becomes model law**
- a system that enforces **fake certainty** by erasing uncertainty, nuance, and local knowledge

---

## 3. Standards positioning and source-of-meaning

### 3.1 Ecosystem positioning
OFARM is not trying to replace every adjacent system.

Reference positioning:
- **AIM** is the primary semantic alignment target for shared agricultural semantics.
- **ADAPT** is the closest practical FMIS data-standard competitor at production-data exchange level.
- **AEF / ISOXML / EFDI** are machinery and work-record exchange incumbents.
- **NGSI-LD / FIWARE** are context/integration layers, not OFARM canonical truth.
- **SAREF4Agri** is a device/measurement semantic layer, not the whole farming business core.
- **AgroPortal / AgroLD / GARDIAN / AgroFIMS / COPO** are repository, discovery, FAIR, brokering, or linked-data infrastructure around the domain, not direct replacements for OFARM.

### 3.2 Standards-alignment principle
Using existing standards and ontologies for the shared semantic base does **not** meaningfully weaken OFARM in expressive power, agronomic nuance, or analytical usefulness.

What it costs:
- unilateral design freedom
- some modeling convenience
- extra semantic discipline
- some implementation complexity

That cost is acceptable and strategically correct.

### 3.3 Source-of-meaning method
Every constitutional core concept must fall into exactly one alignment class:

- **REUSE_EXTERNAL** — OFARM adopts the external concept directly.
- **PROFILE_EXTERNAL** — OFARM uses the external concept as the base and constrains or specializes it.
- **OFARM_ALIGNED** — OFARM keeps an OFARM canonical term but must publish formal alignment to external anchors.
- **OFARM_OWNED** — the concept is substantively and strategically OFARM-native.

### 3.4 Shared semantic substrate
OFARM reuses public standards where they are the best stewards of meaning, including:
- GeoSPARQL for space/geometry
- OWL-Time for temporal structure
- QUDT for quantities and units
- SOSA/SSN for observation foundations
- PROV-O for provenance foundations
- AIM as the main agricultural semantic anchor
- domain vocabularies such as AGROVOC, EPPO, BBCH, AgrO, Crop Ontology, Plant Ontology, PECO, and ENVO where they fit

The shared substrate should be governable as a version-pinned **SemanticSubstrateBundle** that records the semantic anchors, validation backbones, and exchange bindings a deployment or promoted profile depends on.

SHACL is the baseline validation/profile mechanism for RDF-grounded semantic profiles.
Exchange bindings such as UCUM may be required for declared interoperability surfaces, but they do not replace the semantic anchors themselves.

Agronomic carrier shells added by accepted post-charter RFCs use the shared substrate for observation, sample, measurement, quantity, unit, provenance, time, and geometry discipline. They do not import external standards, registries, or machinery files as OFARM truth stores. External standards and registries remain anchors, bindings, exchange surfaces, or attestation wrappers; external standards remain anchors and do not become hidden OFARM law.

### 3.5 OFARM-owned semantic territory
OFARM intentionally owns the semantics that make it more than a vocabulary alignment project, especially:
- crop-cycle operational identity
- planned versus executed intervention semantics
- assertion/history-first truth and governed current-state materialization
- evidence sufficiency and evidentiary governance
- accepted event consequences and supersession/correction mechanics
- compliance, inspection, nonconformity, and corrective-action semantics
- pack/profile/extension/local-artifact law
- authority, delegation, sharing, revocation, and data-sovereignty law
- query law, compiled-output law, and local-knowledge/uncertainty law
- agronomic observation and measurement context carrier-shell law
- quantity-bearing intervention-intent and execution/as-applied payload separation
- partial extent and geometry-basis governance
- scheme-bound agronomic identity and code-binding profile law
- agronomic reconstruction policy and trace rules for queries and outputs

### 3.6 Alignment Register
Every v2-must constitutional core concept shall appear in the **OFARM Alignment Register** with one alignment classification.

The Alignment Register records constitutional semantic core concepts.
It does not serve as the home for deployment-specific conformance claims, runtime-surface claims, or mapping coverage/loss disclosures unless a new constitutional core concept itself is being introduced.

Absence from the register means the concept is not yet constitutional core.

### 3.7 No-hidden-core rule
A concept may not quietly become constitutional core through:
- one app implementation
- one pack
- one template family
- one integration adapter
- one AI behavior

### 3.8 Agronomic carrier-shell law
The accepted agronomic closure RFCs add small OFARM-owned carrier shells rather than a second agronomic truth model.
The active agronomic carrier families are:
- **AgronomicObservationContext** — structured crop, phenomenon, method, spatial, temporal, threshold, and promotion-use context around an observation.
- **MeasurementEvidence** — sampled, measured, sensed, lab-derived, or imported evidence with quantity, unit, method, calibration, uncertainty, limit, provenance, and evidence-status context.
- **InterventionIntentPayload** — recommendation, prescription, planned-operation, cancellation, or supersession payload semantics for intended agronomic action.
- **ExecutionRecordPayload** — operation claim, as-applied evidence, accepted execution detail, correction, and dispute payload semantics.
- **PartialExtent** — event-bound or identity-candidate spatial slice with geometry basis, quality, evidence, and durable-identity policy.
- **AgronomicIdentityBinding** and **AgronomicCodeBindingProfile** — scheme-bound identity and profile rules for crops, varieties, organisms, products, inputs, methods, thresholds, quantity kinds, and units.
- **AgronomicReconstructionPolicy** and **AgronomicReconstructionTrace** — query/output controls and explanation traces for high-consequence agronomic reconstruction.

These carriers are not alternate stores of truth.
They bind agronomic context, evidence, identities, quantities, extents, and reconstruction rules to the existing assertion/history, evidence, promotion, materialization, advisory/compliance, query, and output law.
External standards and registries remain anchors, bindings, exchange mappings, runtime surfaces, evidence sources, or attestation wrappers as declared by profile; they do not become hidden OFARM law or OFARM canonical truth.

---

## 4. Semantic layer model

OFARM uses the following layer model:

### 4.1 Layer 0 — shared semantic substrate
Public cross-domain and agricultural semantics reused or profiled by OFARM.

### 4.2 Layer 1 — OFARM Crop Core
Core crop-farming identity, scope, parties, roles, facilities, equipment, resources, lots, crop-cycle entities, and durable identity boundaries for agronomic scope.

### 4.3 Layer 2 — OFARM Intervention and Event Core
Interventions, event families, intervention-intent payloads, execution/as-applied payloads, accepted event consequences, and operational consequences.

### 4.4 Layer 3 — OFARM Evidence, Traceability, and Audit Core
Assertions, review decisions, evidence, measurement evidence, bundles, lineage, attestation-relevant relations, and current-state materialization law.

### 4.5 Layer 4 — OFARM Knowledge, Nuance, and Uncertainty Core
Narrative observations, agronomic observation contexts, local patterns, hypotheses, heuristics, confidence/review state, and local memory.

### 4.6 Layer 5 — OFARM Pack and Profile System
Packs, profiles, scoped extensions, local artifacts, activation sets, compatibility, precedence, and agronomic code-binding profiles.

### 4.7 Layer 6 — OFARM Archetype, Template, and Interaction-Specification Layer
Archetypes, templates, and interaction-specification artifacts without runtime UI law.

### 4.8 Separation rule
Shared meaning belongs in the shared substrate where possible.  
Operational/compliance grammar belongs in OFARM.  
Runtime behavior belongs in OFARM Platform.

---

## 5. Artifact constitution

### 5.1 Core rule
A pack assembles modules.  
A pack is not the primitive modeling unit.

Every artifact type should have:
- stable identifier
- version
- status
- steward/owner
- scope
- dependencies
- compatibility rules
- machine-readable form
- promotion/deprecation path where relevant

### 5.2 Artifact families
OFARM standardizes at least these artifact families:

#### Semantic artifacts
- core semantic module
- scoped semantic extension
- SemanticSubstrateBundle
- agronomic carrier-shell module

#### Content artifacts
- archetype
- template

#### Decision and governance artifacts
- rule module
- validation module
- evidence policy module
- commit policy module

#### Knowledge artifacts
- vocabulary module
- code binding module
- code-binding profile module
- identity-binding module
- reference snapshot module

#### Query artifacts
- QuerySpecification
- SemanticPathAlias

#### Presentation artifacts
- ViewModule
- PassportView
- DocumentAssembly

#### Interaction-specification artifacts
- interaction module
- questionnaire/form module
- guidance module

#### Exchange artifacts
- import mapping module
- export mapping module
- MappingCoverageStatement
- LossMap
- RuntimeSurfaceContract

#### Assembly artifacts
- pack manifest
- profile manifest

### 5.3 Dependency discipline
Recommended dependency direction:

- semantic artifacts -> lower/shared semantic artifacts only
- content artifacts -> semantic artifacts
- decision/governance artifacts -> semantic + content + knowledge artifacts
- knowledge artifacts -> semantic artifacts and external sources
- query artifacts -> semantic + content + knowledge artifacts
- presentation artifacts -> query + semantic + content + decision + knowledge artifacts
- interaction artifacts -> content + decision + presentation artifacts
- exchange artifacts -> query + semantic + content + knowledge + presentation artifacts
- assembly artifacts -> any governed artifact family

### 5.4 Minimum standardization target for OFARM 2.0
The minimum artifact set OFARM 2.0 standardizes includes:
- archetype
- template
- rule module
- validation module
- evidence policy module
- vocabulary module
- code binding module
- QuerySpecification
- ViewModule
- PassportView
- DocumentAssembly
- interaction module
- export mapping module
- pack manifest

---

## 6. Pack, profile, extension, and local-artifact law

### 6.1 Definitions
- **Pack** = installable bundle of governed artifacts for a context
- **Profile** = constraint set that narrows or activates behavior within a context
- **Scoped extension** = new meaning not present in the universal core
- **Local artifact** = farm/private artifact not official OFARM unless promoted

These terms are not interchangeable.

### 6.2 Scope assignment
Packs and profiles may be assigned at:
- farm
- site
- field
- zone
- crop cycle
- lot
- operation

Multiple packs may be active simultaneously.

### 6.3 PackActivationSet
Compatibility is evaluated for a concrete **PackActivationSet** defined by:
- scope
- time
- active packs
- active profiles
- relevant scoped extensions
- relevant precedence classes

A PackActivationSet may later be referenced by a governed ContextSnapshot, but it is not by itself the full resolved interpretation basis for current-state materialization.

### 6.4 Precedence classes
OFARM fixes these baseline precedence classes:

1. jurisdiction / law / safety  
2. certification / claim / contract  
3. crop-system / biophysical context  
4. tooling / method  
5. local / community / preference

### 6.5 Required pack declarations
Every pack must declare at least:
- identifier
- version
- status
- steward/owner
- precedence class
- eligible scopes
- dependencies
- incompatibilities/exclusions
- touched constitutional surfaces
- declared compatibility policy where known
- artifact inventory

### 6.6 Touched surfaces
A pack must declare which surfaces it touches, such as:
- vocabularies/bindings
- archetypes/templates
- interaction specs
- evidence policies
- validation/rule modules
- event-family subtypes
- views and compiled outputs
- import/export mappings
- runtime API/event/query/discovery surface contracts
- advisory behavior

### 6.7 Surface families
For merge and compatibility purposes, OFARM recognizes at least these **PackSurfaceFamily** values:
- VOCABULARY_BINDINGS
- EVIDENCE_POLICY
- ARCHETYPE_DEFINITION
- TEMPLATE_CONSTRAINT
- VALIDATION_RULE
- DECISION_RULE
- EVENT_SUBTYPE_DEFINITION
- VIEW_SHAPING
- DOCUMENT_ASSEMBLY_SHAPING
- IMPORT_EXPORT_MAPPING
- RUNTIME_SURFACE_CONTRACT

### 6.8 Merge modes
For pack overlap on a declared surface family, OFARM recognizes these **PackSurfaceMergeMode** values:
- ADDITIVE_UNION
- CONSTRAINT_INTERSECTION
- STRONGEST_REQUIREMENT
- ORDERED_COMPOSITION
- IDENTICAL_ONLY
- HARD_FAIL

### 6.9 What packs may change
A pack may:
- activate scoped behavior
- narrow constraints
- add required evidence
- add event-family subtypes
- add context-specific attributes where allowed
- add validation/rule modules
- add views, compiled outputs, mappings, and runtime surface contracts
- restrict or specialize workflows
- add pack-scoped terminology and code bindings
- declare safe merge behavior where governed

### 6.10 What packs may not change
A pack may not:
- rewrite universal OFARM core meaning
- rewrite the Alignment Register by local force
- change the truth model
- change twin law
- change the fixed top-level event families
- change commit classes by private interpretation
- bypass provenance, evidence, review, or audit rules
- weaken anti-goals
- silently shadow another pack’s artifact
- silently override a higher-precedence requirement
- invent undeclared merge behavior

### 6.11 Compatibility classes
OFARM uses these compatibility classes:
- COMPATIBLE
- COMPATIBLE_WITH_DECLARED_MERGE
- COMPATIBLE_BY_SCOPE_SEPARATION
- EXCLUSIVE
- GOVERNANCE_REQUIRED

### 6.12 Surface-specific merge law
A declared safe merge is only valid if:
- the overlap is assigned to a covered PackSurfaceFamily
- the chosen PackSurfaceMergeMode is legal for that family
- the resulting merged meaning remains deterministic and traceable

### 6.13 Baseline family rules
At minimum, OFARM adopts these family rules:

- **VOCABULARY_BINDINGS**: ADDITIVE_UNION for disjoint/identical keys; CONSTRAINT_INTERSECTION for non-empty compatible narrowing; otherwise HARD_FAIL
- **EVIDENCE_POLICY**: STRONGEST_REQUIREMENT when cumulative and non-contradictory; otherwise HARD_FAIL
- **ARCHETYPE_DEFINITION**: IDENTICAL_ONLY; otherwise HARD_FAIL
- **TEMPLATE_CONSTRAINT**: CONSTRAINT_INTERSECTION for monotone compatible narrowing; otherwise HARD_FAIL
- **VALIDATION_RULE**: CONSTRAINT_INTERSECTION when conjunctive checks remain coherent; otherwise HARD_FAIL
- **DECISION_RULE**: ORDERED_COMPOSITION only with explicit decision partition or governed order; otherwise HARD_FAIL
- **EVENT_SUBTYPE_DEFINITION**: ADDITIVE_UNION or limited additive enrichment only when parent family and semantics remain compatible; otherwise HARD_FAIL
- **VIEW_SHAPING**: ADDITIVE_UNION for disjoint sections or ORDERED_COMPOSITION where section order is governed; conflicting slot semantics HARD_FAIL
- **DOCUMENT_ASSEMBLY_SHAPING**: ADDITIVE_UNION for disjoint sections or ORDERED_COMPOSITION where governed order remains deterministic; conflicting attested slot semantics HARD_FAIL
- **IMPORT_EXPORT_MAPPING**: ADDITIVE_UNION for disjoint external targets or non-overlapping declared coverage; IDENTICAL_ONLY for materially identical mapping/coverage/loss posture; ORDERED_COMPOSITION only with explicit staged traceability; otherwise HARD_FAIL
- **RUNTIME_SURFACE_CONTRACT**: ADDITIVE_UNION for disjoint endpoints/topics/resources/discovery entries; IDENTICAL_ONLY for materially identical contracts; otherwise HARD_FAIL

### 6.14 Conflict rules
When two same-precedence packs touch the same surface incompatibly:
- apply the declared and legally allowed merge mode if it remains safe
- otherwise hard fail the PackActivationSet

When packs conflict across precedence classes:
- higher precedence wins
- lower precedence may enrich only where its surface-specific merge mode remains safe and non-contradictory
- if meaningful operation is no longer possible, activation should fail

### 6.15 PackMergeResolutionTrace
The system must be able to produce a trace of:
- compared packs
- affected PackActivationSet
- surface family
- merge mode applied
- precedence relationship
- resulting outcome
- reason for failure or governance requirement where relevant

Where merge outcomes materially affect interpretation, the resulting trace identifiers may be referenced from a governed ContextSnapshot basis.

### 6.16 Promotion ladder
Artifacts may move through this ladder:
1. private local artifact
2. shared local/community artifact
3. candidate artifact
4. governed OFARM artifact

Sharing does not equal standardization.

### 6.17 Normative companion artifacts
The normative companion artifacts for pack law are:

- **OFARM Pack Safety and Compatibility Policy v0.2**
- **OFARM Pack Merge Semantics RFC v0.1**
- **OFARM External Standards Integration and Interoperability Policy v0.1**
- **OFARM Semantic Substrate Bundle and External Profile Packaging RFC v0.1**
- **OFARM Interoperability Mapping Coverage, Loss, and Runtime Surface RFC v0.1**

---

## 7. Identity, scope, and authority model

### 7.1 Identity layers
OFARM must distinguish:

- **durable identity**: the thing that persists through time as the same governed referent
- **identity revision**: a versioned representation of the durable identity when governed characteristics change without breaking identity continuity
- **time-bounded state**: what is true of that identity or revision during a validity interval

State change, revision change, and identity replacement must not be collapsed into one another.

### 7.2 Durable identity test
A thing keeps the same durable identity only if all of the following still hold:
- referent continuity
- one-to-one continuity
- type continuity
- accountability continuity
- purpose continuity

If these fail, OFARM should create a new durable identity and preserve explicit lineage.

### 7.3 Identity revision rule
Create a new **identity revision** when:
- the durable identity remains the same
- but boundary, structure, metadata, classification, or governed detail changes in a way later queries, reviews, or lineage may need to distinguish

A revision is not a new identity.

### 7.4 New identity rule
Create a **new durable identity** when:
- one governed thing splits into multiple governed things
- multiple governed things merge into one
- a different real-world referent replaces the old one
- accountability/management is reconstituted into a different governed unit
- purpose continuity is broken
- cohort continuity is broken strongly enough that the old identity basis no longer holds
- a new agronomic attempt begins rather than the old one continuing

### 7.5 Lifecycle lineage
When OFARM creates a new identity or revision, lineage must remain explicit.

At minimum lifecycle lineage should support:
- revises
- supersedes
- splitFrom / splitInto
- mergedFrom / mergedInto
- succeeds / precededBy
- overlapsWith
- replaces / replacedBy
- derivedFrom

### 7.6 Party and role
A **Party** is an identifiable agent that can act, hold responsibility, hold authority, or appear in provenance.

A Party may be:
- a natural person
- an organization
- a cooperative
- a public body
- a service company
- a buyer
- a certifier
- a software agent where governance permits it

Terms such as farmer, operator, advisor, inspector, certifier, buyer, and service provider are **role types**, not separate top-level identity classes.

A **RoleAssignment** binds:
- a Party
- to a role type
- in a scope
- for a time interval

### 7.7 Delegated work and service-provider principle
OFARM must be able to record:
- performing Party
- benefiting or delegating Party where relevant
- role basis
- scope
- time interval

### 7.8 Authority law
RoleAssignment identifies who someone is in context.  
It does **not** imply unlimited power.

Authority must be:
- explicit
- scoped
- time-bounded
- traceable
- revocable where governance allows
- distinct by authority family

### 7.9 Authority families
OFARM recognizes at least:
- observe/report
- assert/submit
- operate/intervene
- review
- govern/decide
- attest/sign
- context-governance
- share/revoke
- receive/use

### 7.10 AuthorityActionClass
Authority must be evaluated against a governed **AuthorityActionClass**, not merely against a broad role label.

Baseline AuthorityActionClass values include:
- OBSERVE_CREATE_OBSERVATION
- OBSERVE_ATTACH_EVIDENCE
- ASSERT_STRUCTURE
- ASSERT_OPERATION_CLAIM
- ASSERT_COMPLIANCE
- OPERATE_PLAN_INTERVENTION
- OPERATE_REPORT_EXECUTION
- REVIEW_REQUEST
- REVIEW_ACCEPT
- REVIEW_REJECT_OR_CONTEST
- REVIEW_SUPERSEDE
- CONTEXT_INSTALL_PACK
- CONTEXT_ACTIVATE_PACK
- CONTEXT_DEACTIVATE_PACK
- OUTPUT_APPROVE_DOCUMENT_ASSEMBLY
- OUTPUT_ATTEST_DOCUMENT_ASSEMBLY
- OUTPUT_FILE_SUBMISSION_ASSEMBLY
- SHARE_GRANT_ACCESS
- SHARE_REVOKE_ACCESS
- RECEIVE_READ_DATA

### 7.11 Default-deny principle
If OFARM cannot justify a valid action path through:
- role basis
- authority grant
- scope/time fit
- delegation where relevant
- revocation state
- non-human/AI rules where relevant

the default is **DENY**.

### 7.12 ScopeInheritanceMode
Broad-scope grants do not automatically imply all narrower or derived-scope powers.

OFARM recognizes at least these inheritance modes:
- EXACT_ONLY
- DESCENDANT_SCOPES
- DERIVED_LINEAGE_SCOPES
- NO_INHERIT

No upward inheritance is allowed by default.

Govern/decide, context-governance, and attest/sign actions default to **NO_INHERIT** unless explicitly granted otherwise.

### 7.13 AuthorityGrant
An **AuthorityGrant** binds:
- one Party or RoleAssignment
- to one or more authority families and/or action classes
- in a scope
- for a time interval
- optionally for a stated purpose
- optionally with conditions or limits
- with an explicit inheritance mode where relevant

### 7.14 DelegationGrant
A **DelegationGrant** is an explicit governed grant through which one Party permits another Party to act within a bounded authority family, action class, scope, and time interval.

Delegation may not exceed the delegator’s valid authority.

### 7.15 SharingGrant
A **SharingGrant** gives another Party the right to see, retrieve, or receive specific OFARM data, views, evidence, or compiled outputs.

SharingGrant is not the same as authority to:
- assert
- review
- decide
- sign

### 7.16 DataSovereigntyBoundary
A **DataSovereigntyBoundary** expresses the principle that farm-scoped operational truth and evidence remain under responsible farm-side control unless stronger legal, contractual, certification, or public-authority rules apply.

Cross-farm/regional intelligence belongs in the Advisory Twin by default and must not silently become farm-level compliance truth.

### 7.17 RevocationDecision
A **RevocationDecision** may end or narrow:
- an AuthorityGrant
- a DelegationGrant
- a SharingGrant
- future visibility or use rights

Revocation is prospective unless stronger governance says otherwise.  
It does not erase historical truth.

### 7.18 AI-assisted and non-human action principle
If AI assists a human-authorized actor:
- the human remains the accountable actor for the final action
- AI assistance should be traceable

Non-human actors may act only if:
- they are recognized Parties/agents allowed by governance
- they hold explicit authority for the requested action class
- the action class is allowed for non-human actors

In v0.1, govern/decide, context-governance, and attestation/signing actions remain human-governed by default unless explicitly relaxed later.

### 7.19 Field lifecycle rule
A Field keeps the same durable identity when governed operational continuity remains one-to-one and a boundary change is still the same managed field.

Create a new identity when:
- one field is split into separately governed fields
- multiple fields are merged into one governed field
- the field is reconstituted as a different accountable/managed unit
- the continuity test fails strongly enough that “same field” is no longer justified

### 7.20 Zone lifecycle rule
ManagementZone and MicroclimateZone become constitutional identity-bearing zones only when they are intentionally governed as recurring zones.

Ephemeral one-off advisory masks or analysis overlays are not automatically constitutional zones.

A zone keeps the same identity when its purpose and recurring-zone continuity remain intact, even if geometry is revised.

Create a new zone identity when:
- one zone splits into multiple recurring governed zones
- multiple zones merge
- zone purpose changes materially
- one-to-one recurring-zone continuity is lost

### 7.20a Partial extent and durable-identity rule
A **PartialExtent** may describe a sampled area, observed patch, treatment area, failed pass, re-treatment area, replant area, damage area, operational pass, or disputed geometry.

A PartialExtent does not by itself create a Field, ManagementZone, MicroclimateZone, CropCycle, Lot, or accepted event consequence.
It becomes or supports a durable identity only when the durable identity test and the applicable identity/lifecycle law require that result.

Temporary extents used only for a single observation, operation, calculation, or dispute should remain event-bound geometry/evidence records rather than constitutional zones.

### 7.21 CropCycle lifecycle rule
A CropCycle is the durable identity of a particular cultivation attempt or realized cycle on a scope.

A failed cycle remains the same CropCycle if failure is the outcome of that attempt and no new establishment has begun.

Create a new CropCycle identity when:
- replant/re-establishment starts a new cultivation attempt
- the old cycle is terminated and a new one begins
- one parent cycle diverges into separately governed child cycles
- intentional intercropping or relay-cropping creates concurrent distinct cycles

Overlapping CropCycles are allowed only with explicit overlap relation and scope clarity.

### 7.22 Lot lifecycle rule
A Lot is the durable traceability identity of a materially coherent cohort under one governed traceability basis.

A Lot keeps the same identity when the same traceability cohort continues, even if:
- storage location changes
- metadata changes
- commercial/shipment references are added

Create a new Lot identity when:
- the lot is split into distinct traceability cohorts
- multiple lots are merged or commingled
- transformation or handling breaks the prior cohort identity
- claim/certification basis is reset strongly enough to require a new traceability object
- material continuity is no longer safely one-to-one

Commercial references alone do not create a new Lot identity.

Executable closure for same-lot continuity decisions, explicit lot-lineage-change records, and governed claim-basis declarations is provided by **OFARM Lot Traceability and Claim Basis RFC v0.1**.

### 7.23 Equipment, facility, storage, and container lifecycle rule
Equipment or Tool identity is based on the durable real-world asset.
Facility identity is based on the durable governed operational place.
StorageLocation identity is based on the durable scoped containment/place identity.
Container identity is based on the containment unit, not the lot it contains.

Keep the same identity when the same asset/place/unit continues through revision or state change.

Create a new identity when replacement, split, merge, or continuity failure makes “same governed object” false.

Reusable containers may keep the same identity across many occupancy episodes.  
A changed occupant does not create a new Container identity.

### 7.24 First-class domain objects
OFARM constitutional core includes at minimum:
- Farm
- Site
- Field
- ManagementZone
- MicroclimateZone
- CropCycle
- Equipment / Tool
- AppliedResource
- Facility / StorageLocation / Container
- Lot
- PartialExtent
- Operation
- AgronomicObservationContext
- MeasurementEvidence
- InterventionIntentPayload / ExecutionRecordPayload
- AgronomicIdentityBinding / AgronomicCodeBindingProfile
- EvidenceBundle
- AssertionRecord
- ReviewDecision
- CurrentStateMaterialization
- DocumentAssembly

### 7.25 Relationship between identity and state
Durable identity answers what thing this is.  
Identity revision answers which governed version of that thing is referenced.  
Time-bounded state answers what is true of that identity or revision at a given time.

### 7.26 Normative companion artifacts
The normative companion artifacts for identity and authority law are:

- **OFARM Identity and Lifecycle RFC v0.1**
- **OFARM Lot Traceability and Claim Basis RFC v0.1**
- **OFARM Authority, Delegation, and Data Sovereignty Policy v0.2**
- **OFARM Authority Policy Model RFC v0.1**
- **OFARM Authority Action Matrix v0.1**

---

## 8. Temporal model



OFARM truth law is multi-temporal. At minimum it distinguishes:
- **observation time**
- **event time**
- **assertion time**
- **record time**
- **effective time**
- **review/decision time**
- **supersession time**
- **validity interval**

These must not collapse into one generic “date.”

Late-arriving assertions, evidence, or events do not rewrite earlier record time.  
They may still change effective state or supersession status under governance.

---

## 9. Canonical semantic query model

### 9.1 Rule
OFARM standardizes a **canonical internal query model**.

OFARM does **not** standardize a public expert textual syntax in v2.

### 9.2 QuerySpecification
The constitutional query artifact is **QuerySpecification**.

A QuerySpecification must be representable in a machine-validatable formal schema.

At minimum it defines:
- target twin
- target scope
- target time policy
- optional authority/sharing context
- anchor concepts/entities
- graph pattern block
- optional semantic path-alias block
- predicate/filter block
- selection/projection block
- ordering/pagination where relevant
- result profile or ViewModule reference where relevant

### 9.3 Graph-pattern core
The primary retrieval mechanism is the semantic **graph pattern**.

The canonical query model is:
- graph-pattern-first for semantic relationships
- path-aware for archetype/template-bound content
- filter-rich for time, space, provenance, pack, authority, and review constraints

### 9.4 SemanticPathAlias
OFARM recognizes **SemanticPathAlias** as governed shorthand into archetype/template-bound content structures.

A SemanticPathAlias:
- must resolve to a semantic anchor or governed content node
- must be machine-resolvable under a governed alias contract
- must carry enough version/reference information to avoid silent drift
- is convenience, not alternate schema

Governed alias catalogs and alias-resolution traces belong to this contract layer; they do not create a second schema.

### 9.5 QueryPlanIR
**QueryPlanIR** is a formal runtime planning representation derived from QuerySpecification.

It is not the constitutional query artifact itself.
But it must be formal enough that runtime planning cannot hide query meaning inside ungoverned conventions.

### 9.5a Agronomic reconstruction policy
High-consequence agronomic retrieval, PassportView generation, DocumentAssembly assembly, filing, buyer-facing output, or compliance reconstruction must declare or inherit an **AgronomicReconstructionPolicy** when agronomic observation, measurement, intervention, execution, partial extent, product/input identity, threshold, or code-binding facts materially affect the answer.

The policy must cover effective-as-of semantics, knowledge-cut semantics, truth scope, evidence floor, materialization freshness, geometry policy, late-evidence policy, dispute policy, code-binding profile, and output disclosure posture.
A corresponding **AgronomicReconstructionTrace** should explain whether the query or output used history reconstruction, governed current-state reuse, refusal, review, annexing, or successor-output behavior.

### 9.6 Retrieval/presentation/publication separation
- QuerySpecification retrieves
- ViewModule shapes
- PassportView provides portable scope-centric compiled views
- DocumentAssembly freezes governed outputs

### 9.7 AI mediation rule
AI-mediated retrieval must compile through formal objects.

Required chain in principle:
1. human request  
2. AI interpretation  
3. QuerySpecification  
4. QueryPlanIR  
5. governed execution  
6. result shaping via ViewModule or direct result profile

AI may help author or refine QuerySpecifications.
AI may not bypass governed query compilation.

### 9.8 Runtime and external surfaces
Runtime API filters or external query surfaces are allowed.

But they are not the canonical query model itself.
They are runtime or interoperability surfaces that must preserve query meaning.
Where standardized query façades are exposed, they should be treated as governed runtime-surface contracts rather than alternate constitutional query law.

### 9.9 Early exposure posture
In v2, public access to expert semantic queries is not required.

What is required is:
- a canonical internal query model
- formal QuerySpecification and QueryPlanIR contracts
- reusable saved query/view artifacts
- a path for guided UI and AI-mediated access

### 9.10 Normative companion artifacts
The normative companion artifacts for query law are:

- **OFARM Query Architecture Note v0.1**
- **OFARM QuerySpecification Schema RFC v0.1**
- **OFARM SemanticPathAlias Governance RFC v0.1**

---

## 10. Truth, state, event, and output law


### 10.1 Assertion/history-first authority
The deepest OFARM authority is an assertion/history-first semantic graph composed from:
- immutable AssertionRecords
- immutable event records
- immutable ReviewDecisions
- evidence relations
- lineage relations
- accepted event consequences
- attestation-relevant relations

### 10.2 Governed current-state materialization
OFARM also maintains governed **CurrentStateMaterializations** derived from:
- in-force assertion records
- accepted event consequences
- applicable review decisions
- applicable identity/lifecycle state
- active packs/profiles and other relevant context constraints

Current-state materialization is canonical for current-state use.  
It is not deeper than the assertion/history authority it is derived from.

### 10.3 Materialization instance
A CurrentStateMaterialization instance must be identifiable at least by:
- target twin
- anchor scope
- evaluation time policy
- context snapshot
- MaterializationBasis
- generated-at time
- freshness status

If these dimensions change materially, OFARM should treat the result as a different materialization instance.

### 10.4 MaterializationBasis
A **MaterializationBasis** is the traceable authoritative basis from which a CurrentStateMaterialization was generated.

At minimum it should identify:
- contributing in-force AssertionRecords
- contributing accepted event consequences
- contributing ReviewDecisions
- relevant identity revisions or lifecycle relations where they affect interpretation
- governing context snapshot identifiers
- evaluation time policy

The concrete governed realization of the context basis is **ContextSnapshot**.  
A ContextSnapshot may reference the relevant PackActivationSet, ActiveArtifactSet, rule/evidence-policy revisions, reference snapshots, identity revisions, and PackMergeResolutionTrace objects needed to explain interpretation.

If the system cannot explain the basis strongly enough to justify the result, the materialization is not trustworthy enough for high-consequence use.

### 10.5 MaterializationSnapshot
A **MaterializationSnapshot** is a durable recorded generation of a CurrentStateMaterialization kept because later traceability matters.

A MaterializationSnapshot does not replace the authoritative substrate.
It records what current-state answer was relied upon at a relevant time.

### 10.6 Freshness states
Current-state materialization must carry a governed freshness state.

Baseline states are:
- **FRESH**
- **STALE**
- **INVALID**

Freshness is purpose-sensitive.  
The same materialization may be acceptable for exploratory advisory viewing but unacceptable for high-consequence compliance or attestation use.

### 10.7 Invalidation triggers
At minimum, OFARM must recognize these trigger families for materialization freshness/invalidation:
- truth-basis triggers
- identity/lifecycle triggers
- context triggers
- time-policy triggers
- twin-specific advisory triggers where relevant

The platform must be able to say which trigger changed status and why.

### 10.8 Contradictions
Contradictory assertions may coexist in authority.

OFARM preserves contradiction in history with review status and lineage.

Compliance-Twin current state must resolve mutually exclusive hard-truth positions either to:
- one in-force position, or
- an explicit contested/under-review condition

Advisory-Twin current state may keep competing hypotheses or scenario candidates where governance allows them.

### 10.9 Supersession
Supersession never deletes history.  
It changes what remains in force for current-state materialization.

### 10.10 Raw evidence and interpretation
Where evidence matters, OFARM keeps:
- the raw source or linked original
- the normalized semantic interpretation
- the provenance relation between them

### 10.10a Agronomic carrier truth boundary
Agronomic carrier shells preserve context and evidence needed for governance.
They do not make truth stronger by existing.
A carrier does not make truth stronger by existing; only the surrounding assertion/history, evidence, authority, review, and promotion path can change truth posture.

In particular:
- an AgronomicObservationContext does not by itself create accepted observation state, recommendation, prescription, or treatment truth
- MeasurementEvidence supports evidence sufficiency but does not by itself create accepted state
- an InterventionIntentPayload is intent-side payload, not execution
- an ExecutionRecordPayload may be claim, evidence, accepted detail, correction, or dispute only according to its governed record class and surrounding promotion path
- a PartialExtent is not whole-scope truth and not a durable identity by default
- a PartialExtent does not by itself create a Field, ManagementZone, MicroclimateZone, CropCycle, or other durable identity
- an AgronomicIdentityBinding is evidence-governed identity binding, not accepted identity without the applicable profile and evidence policy
- an AgronomicReconstructionTrace explains reconstruction; it is not canonical truth

### 10.11 Event
An event is something that happened, was attempted, was observed, or was recorded.

An event may:
- create one or more assertion records
- create or qualify evidence links
- propose one or more event consequences
- trigger advisory or review workflows
- influence current-state materialization only when governance accepts the relevant consequence

An event is not automatically current state merely because it exists.

### 10.12 DocumentAssembly
A **DocumentAssembly** is a frozen governed compiled output assembled from:
- current state
- relevant history
- evidence
- rules
- view logic
- attestation/review state

It may later serve as evidence, but publication alone does not make it canonical truth.

Where a DocumentAssembly is attested, claim-bearing, or filed, the applicable evidence-sufficiency policy must be satisfied and remain traceable.

For agronomic use, a DocumentAssembly may include unresolved mappings, disputed geometries, raw source payloads, late evidence, advisory reasoning, or alternative reconstruction annexes only when the governing reconstruction policy allows that disclosure.
Annexing material in a frozen document does not promote it into accepted truth.

DocumentAssembly subfamilies include:
- **ReportAssembly**
- **DossierAssembly**
- **SubmissionAssembly**

### 10.13 PassportView
A **PassportView** is a governed, portable, scope-centric compiled view derived from QuerySpecifications plus view logic.

A PassportView is not:
- canonical truth
- automatically attested merely because it exists
- the catch-all bucket for every compiled output

For high-consequence agronomic use, PassportView defaults to accepted consequences and profile-permitted facts only.
It must refuse, require review, or clearly disclose limitations when materialization, evidence, code binding, geometry, dispute, or freshness policy is not satisfied.

### 10.14 State-change sequence
Canonical state changes through this sequence:
1. capture produces typed draft material
2. governed commit creates assertion and/or event records
3. review/governance decides acceptance, rejection, contestation, or supersession as needed
4. accepted event consequences and in-force assertions feed current-state materialization
5. later review or correction may change what remains in force without deleting prior history

### 10.15 High-consequence use rule
Before a high-consequence use that materially relies on current state, OFARM must ensure the relevant materialization is either:
- freshly recomputed for that use, or
- demonstrably still FRESH under the declared policy

If the materialization is STALE or INVALID, the system must recompute, refuse the action, or route to explicit review if policy allows that path.

### 10.16 Normative companion artifacts
The normative companion artifacts for current-state and high-consequence output law are:

- **OFARM Current-State Materialization RFC v0.1**
- **OFARM ContextSnapshot Closure RFC v0.1**
- **OFARM Evidence Sufficiency and Attestation Policy v0.1**

---

## 11. Commit classes and promotion law


### 11.1 Baseline commit classes
OFARM recognizes at least:
- **note**
- **observation assertion**
- **hypothesis assertion**
- **structure assertion**
- **operation claim**
- **evidence record**
- **compliance assertion**
- **governance decision**
- **advisory output**

### 11.2 Input classes versus stronger in-force results
Commit classes are input classes entering authority.

They are not the same as stronger in-force results such as:
- accepted structural state
- accepted observation/occurrence state
- accepted executed intervention consequence
- accepted material state
- compliance fact

### 11.3 Pipeline rule
Different commit classes must have different:
- consequences
- validation paths
- evidence expectations
- review requirements
- promotion paths

### 11.4 Minimum pipeline
A commit pipeline must distinguish:
1. capture
2. interpretation/typing
3. assertion/event creation
4. validation
5. evidence sufficiency check where required
6. review/governance where required
7. commit, rejection, or contestation outcome
8. accepted-event-consequence creation where appropriate
9. current-state materialization update where appropriate
10. supersession/correction handling if later changed

### 11.5 Promotion safety rule
If OFARM lacks a declared safe promotion path, the default is:
- do not auto-promote
- keep the weaker class
- require explicit governance or additional evidence

### 11.6 No-shortcut consequences
- an **operation claim** is not automatically an accepted executed intervention consequence
- a **compliance assertion** is not automatically a compliance fact
- a **hypothesis assertion** is not automatically hard truth
- an **evidence record** supports truth but does not create hard truth by itself
- an **advisory output** may not directly create compliance fact or accepted executed intervention consequence
- an **InterventionIntentPayload** may not create execution truth by itself
- an **ExecutionRecordPayload** may not create accepted execution unless the surrounding assertion/event/review/evidence path allows it
- a **machine import**, **registry lookup**, **PartialExtent**, or **AgronomicIdentityBinding** may not bypass authority, evidence, review, promotion, or materialization law

---

## 12. Advisory and compliance boundary

### 12.1 One substrate, two logical twins
OFARM has one semantic substrate.

The Compliance Twin and Advisory Twin are **logical partitions with different materialization and governance rules**, not two unrelated truth universes by default.

### 12.2 Compliance Twin
The Compliance Twin contains:
- hard governed truth
- evidence-linked facts
- append-only review/correction history
- legal and certification consequences
- governed current-state materialization built only from in-force hard-truth inputs

For high-consequence compliance use, stale state is not acceptable by default.

### 12.3 Advisory Twin
The Advisory Twin contains:
- hypotheses
- warnings
- simulations
- probabilistic outputs
- heuristics
- model outputs
- scenario reasoning
- competing candidate states where governance allows them

Advisory-Twin materialization may tolerate stale state in exploratory or explanatory views if clearly marked, but not when used to support a governed bridge toward harder truth.

### 12.4 Bridge rule
Advisory outputs may:
- raise risk flags
- request additional evidence
- suggest follow-up observation
- suggest compliance review
- recommend likely interpretation or next step

Advisory outputs may not:
- directly create or mutate a compliance fact
- directly create a nonconformity with hard consequences
- silently override human-recorded truth
- silently satisfy evidence requirements

There is no fully automatic non-human promotion from advisory output into compliance fact in v2.

---

## 13. Event grammar policy

### 13.1 Fixed top-level event families
OFARM fixes these top-level event families:
- StructureEvent
- ObservationEvent
- OccurrenceEvent
- InterventionEvent
- MaterialEvent
- EvidenceEvent
- GovernanceEvent

### 13.2 Family meanings
- **StructureEvent** = creation/change/end of durable configuration or scope-bearing objects
- **ObservationEvent** = observed, measured, sampled, scouted, or inspected reality
- **OccurrenceEvent** = non-deliberate environmental, biological, contamination, damage, or failure occurrence
- **InterventionEvent** = deliberate human or automated action intended to affect crops, land, lots, facilities, or equipment
- **MaterialEvent** = custody, identity, storage, transformation, split/merge, movement, or disposal of lots/resources/materials
- **EvidenceEvent** = evidentiary capture, issue, receipt, attachment, attestation, or signing act
- **GovernanceEvent** = formal review, decision, submission, inspection, enforcement, or correction act

### 13.3 One-primary-family rule
Every event gets one primary family chosen by its dominant semantic consequence.

Additional consequences are represented through:
- linked evidence
- linked assertions
- accepted event consequences
- linked secondary events where needed

### 13.4 Pack-level enrichment
Packs may subtype these families and add context-specific rules, but may not invent arbitrary new top-level families without governance.

---

## 14. Soft-data and local-knowledge policy

OFARM must preserve local agronomic intelligence, including:
- microclimate knowledge
- farmer heuristics
- local historical memory
- narrative scouting observations
- weak signals and early suspicions

These inputs should be represented as:
- typed artifacts
- provenance-aware artifacts
- confidence-bearing artifacts
- reviewable artifacts

They may influence:
- advice
- prioritization
- review attention
- scenario selection

They may not be forced into fake certainty or promoted to hard truth without stronger support where hard truth matters.

---

## 15. Conformance direction

### 15.1 Minimum constitutional conformance baseline
OFARM 2.0 requires at minimum:
- baseline validation suites for core artifact kinds
- profile compatibility tests
- pack compatibility tests
- pack activation-set compatibility checks
- pack conflict determinism checks
- surface-family merge-mode legality tests
- vocabulary-binding merge fixtures
- evidence-policy merge fixtures
- template-constraint merge fixtures
- decision-rule merge fixtures
- event-subtype merge fixtures
- view/document shaping merge fixtures
- authority action-class decision tests
- scope-inheritance-mode tests
- delegation and revocation tests
- sharing-boundary and no-implicit-access tests
- non-human / AI-assisted action tests
- alignment-register coverage checks
- identity-versus-revision tests
- lifecycle lineage tests for split/merge/replacement/overlap
- field boundary revision versus new-field tests
- zone durable-versus-ephemeral tests
- crop-cycle failure/replant/overlap tests
- lot cohort continuity and split/merge tests
- equipment/facility/container lifecycle tests
- current-state freshness tests
- materialization-basis trace tests
- invalidation-trigger tests
- high-consequence recomputation/refusal tests
- Compliance-versus-Advisory materialization-policy tests
- QuerySpecification schema validation tests
- QueryPlanIR schema validation tests
- path-alias resolution and alias-version stability tests
- graph-pattern equivalence tests
- query-plan semantic-equivalence tests across execution targets
- compiled-output taxonomy conformance tests
- passport-vs-document separation tests
- event-family coverage and subtype-compatibility checks
- commit-promotion safety checks
- agronomic observation and measurement context validation tests
- measurement method, sampling, calibration, limit, uncertainty, and unit-quality tests
- quantity-kind plus unit-code tests for agronomic quantities
- intervention intent versus execution/as-applied separation tests
- partial extent, geometry-basis, disputed-geometry, and durable-identity boundary tests
- scheme-bound agronomic identity and code-binding profile tests
- unresolved free-text product/input/organism/method/threshold fail-closed tests
- agronomic reconstruction policy and trace tests for QuerySpecification, QueryPlanIR, PassportView, and DocumentAssembly
- end-to-end agronomic scenario fixtures covering observation-to-decision, prescription-to-execution, offline contractor sync, partial failure/correction, partial replant, and measurement-context disputes

### 15.2 Deeper conformance program
OFARM should grow toward:
- conformance classes
- broader validation suites
- example packages
- golden test datasets
- broader interoperability fixtures
- wider ecosystem-facing certification or verification programs where useful

---

## 16. Normative companion artifacts

The following companion artifacts are part of the RC2.1 post-charter baseline:

- **OFARM Identity and Lifecycle RFC v0.1**
- **OFARM Current-State Materialization RFC v0.1**
- **OFARM QuerySpecification Schema RFC v0.1**
- **OFARM Pack Merge Semantics RFC v0.1**
- **OFARM Authority Policy Model RFC v0.1**
- **OFARM Authority Action Matrix v0.1**
- **OFARM Alignment Register v0.13**
- **OFARM Event Grammar and Commit Matrix v0.1**
- **OFARM Pack Safety and Compatibility Policy v0.2**
- **OFARM Authority, Delegation, and Data Sovereignty Policy v0.2**
- **OFARM Query Architecture Note v0.1**
- **OFARM Compiled Output and Passport Taxonomy Note v0.1**
- **OFARM Agronomic Observation and Measurement Context RFC v0.1**
- **OFARM Quantity-Bearing Intervention and As-Applied RFC v0.1**
- **OFARM Partial Extent and Geometry Basis RFC v0.1**
- **OFARM Agronomic Code Binding and Standards Profile RFC v0.1**
- **OFARM Agronomic Query and Output Reconstruction RFC v0.1**

---

## 17. Glossary

### Alignment Register
Normative companion artifact that records how each constitutional core concept gets its source of meaning.

### QuerySpecification
A first-class constitutional artifact defining the internal canonical OFARM query model for a retrieval task and representable in a machine-validatable schema.

### QueryPlanIR
A formal runtime planning representation derived from QuerySpecification. It is not the constitutional query artifact, but it must remain governed enough to preserve semantic equivalence and traceability.

### SemanticPathAlias
A governed shorthand from archetype/template-bound content paths to semantic anchors or governed content nodes, with versioned resolution discipline.

### PackActivationSet
A concrete scope/time/context combination in which pack compatibility is evaluated.

### PackCompatibilityDeclaration
A governed declaration that packs are compatible, compatible with declared merge behavior, scope-separated, exclusive, or governance-required.

### PackSurfaceFamily
A governed classification of the kind of artifact surface involved in pack overlap, such as vocabulary bindings, evidence policy, templates, rules, event subtypes, or output shaping.

### PackSurfaceMergeMode
A governed merge mode such as ADDITIVE_UNION, CONSTRAINT_INTERSECTION, STRONGEST_REQUIREMENT, ORDERED_COMPOSITION, IDENTICAL_ONLY, or HARD_FAIL.

### PackMergePolicy
A governed rule describing how same-surface pack content may be safely merged.

### PackMergeResolutionTrace
A traceable record of which packs overlapped, on which surface family, under which merge mode, and with what outcome.

### PackExclusionRule
A governed rule describing where pack co-activation is forbidden.

### AuthorityActionClass
A governed action class such as OBSERVE_CREATE_OBSERVATION, ASSERT_OPERATION_CLAIM, REVIEW_SUPERSEDE, CONTEXT_ACTIVATE_PACK, or OUTPUT_ATTEST_DOCUMENT_ASSEMBLY.

### ScopeInheritanceMode
A governed inheritance mode such as EXACT_ONLY, DESCENDANT_SCOPES, DERIVED_LINEAGE_SCOPES, or NO_INHERIT.

### AuthorityGrant
A governed scoped grant of one or more authority families and/or action classes to a Party or RoleAssignment.

### AuthorizationDecisionTrace
A traceable record of why a requested action was allowed, denied, review-required, or human-approval-required.

### DelegationGrant
A governed explicit grant allowing another Party to act within bounded authority.

### SharingGrant
A governed explicit grant of visibility/use rights distinct from write/review/decision authority.

### DataSovereigntyBoundary
A constitutional governance boundary preserving farm-scoped control and limiting silent cross-farm sharing.

### RevocationDecision
A governed prospective narrowing or termination of authority or sharing that does not erase historical truth.

### durable identity
The persistent governed referent that remains the same thing through time until continuity is broken strongly enough to require a new identity.

### identity revision
A versioned representation of a durable identity when governed characteristics change without breaking identity continuity.

### LifecycleRelation
Explicit lineage relation such as revises, splitFrom, mergedFrom, succeeds, overlapsWith, or replaces.

### assertion/history-first authority
The deepest authoritative semantic history made of immutable assertions, events, review decisions, evidence relations, and lineage.

### current-state materialization
A governed current state answer derived from assertion/history authority for a declared twin, scope, time policy, context snapshot, and basis.

### ContextSnapshot
A governed resolved context-basis object identifying the active interpretation posture for a declared twin, scope, and evaluation time policy.

### MaterializationBasis
The traceable authoritative basis from which a CurrentStateMaterialization was generated.

### MaterializationSnapshot
A durable recorded generation of a CurrentStateMaterialization retained because later traceability matters.

### freshness state
A governed state such as FRESH, STALE, or INVALID indicating whether a materialization is still usable for a declared purpose.

### AssertionRecord
An immutable typed truth object entering OFARM truth law.

### ReviewDecision
An immutable governance act that changes the in-force status of assertions or accepted event consequences.

### accepted event consequence
A governed consequence of an event that is allowed to affect current-state materialization.

### PassportView
A governed portable scope-centric compiled view derived from query and view logic.

### DocumentAssembly
Immutable governed frozen compiled output assembled from canonical truth, evidence, and rules for a purpose.

### ReportAssembly
A DocumentAssembly subtype used for a frozen report.

### DossierAssembly
A DocumentAssembly subtype used for an evidence-rich case package.

### SubmissionAssembly
A DocumentAssembly subtype used for a formal filing or delivery package.


### AgronomicObservationContext
A structured carrier for agronomic context around an observation, including phenomenon, crop/cycle context, method, spatial/temporal basis, evidence, threshold, and promotion-use posture where relevant.

### MeasurementEvidence
A carrier for sampled, measured, sensed, lab-derived, interpreted, or imported evidence with method, quantity, unit, calibration, uncertainty, limit, provenance, and evidence-status context.

### InterventionIntentPayload
A payload carrier for agronomic recommendation, prescription, planned operation, cancellation, or supersession intent.

### ExecutionRecordPayload
A payload carrier for agronomic operation claim, as-applied evidence, accepted execution detail, correction, or dispute record content.

### PartialExtent
An event-bound or identity-candidate spatial slice with geometry basis, quality, evidence, temporal applicability, and durable-identity policy.

### AgronomicIdentityBinding
A governed binding from an OFARM-local agronomic subject to an external scheme, registry, code list, local profile scheme, product authority, or attestation surface.

### AgronomicCodeBindingProfile
A profile-level declaration of the schemes, roles, versions, evidence floors, unresolved-binding behavior, and merge behavior that apply to agronomic identity bindings.

### AgronomicReconstructionPolicy
A query/output policy declaring effective-as-of, knowledge-cut, promotion, truth-scope, evidence, freshness, geometry, late-evidence, dispute, code-profile, and disclosure controls for agronomic reconstruction.

### AgronomicReconstructionTrace
A trace explaining how an agronomic query or output reconstruction used history, current-state materialization, evidence, bindings, extents, refusal, review, annexing, or successor-output behavior.

---

## ONT-SEMINT baseline harmonisation addendum — 2026-05-14

**Status:** active baseline harmonisation of ONT-SEMINT Phases 0 through 5.  
**Change class:** baseline law, constrained to semantic-integrity execution rules.  
**Non-rewrite rule:** this addendum does not reopen OFARM's model/runtime split, assertion/history-first truth law, governed current-state materialization law, Compliance Twin / Advisory Twin separation, pack law, authority law, or crop-only release boundary.

### ONT-SEMINT.1 Semantic conformance is not schema validation

OFARM baseline law now distinguishes the following conformance levels for implementation and audit claims:

1. `SCHEMA_VALID` — object shape validates against an applicable machine contract.
2. `PACKAGE_LOCAL_REFERENCES_RESOLVED` — required package-local references resolve to package-local objects of the expected class.
3. `EXTERNAL_REFERENCES_DECLARED` — externally anchored references are explicit but not verified.
4. `EXTERNAL_REFERENCES_VERIFIED` — externally anchored references have declared snapshot and/or verification-trace support.
5. `RUNTIME_POLICY_GATES_PASSED` — authority, evidence, freshness, pack/profile, materialization, query, and publication/export gates pass for the declared use.
6. `HIGH_CONSEQUENCE_OUTPUT_ELIGIBLE` — the result may drive a high-consequence PassportView, DocumentAssembly, export, submission, or compliance-facing output under policy.

`SCHEMA_VALID` must not be presented as `HIGH_CONSEQUENCE_OUTPUT_ELIGIBLE`. A schema-valid assertion, carrier, query, binding, projection, or output is still not governance-safe until the applicable reference, authority, evidence, freshness, alias, currentness, dispute, and publication/export gates pass.

### ONT-SEMINT.2 Reference resolution law

Package-local references that are declared package-local by prefix, policy, manifest, or artifact role must resolve to an object of the expected class before they may support high-consequence use. Missing, type-wrong, stale, ambiguous, or conflicting package-local references must fail conformance or require review according to consequence level.

Externally anchored references may be declared without being package-local. They do not become verified high-consequence identity merely by appearing in a JSON object, profile, example, imported payload, or pack. Externally anchored references require the applicable `ReferenceSnapshot`, `ReferenceResolutionReport`, and, where registry currentness matters, `ExternalRegistryVerificationTrace` before they may support high-consequence output.

### ONT-SEMINT.3 Agronomic carrier-field canonicalization

For agronomic carriers, `agronomicIdentityBindingRefs` is the canonical field for agronomic identity bindings and `agronomicCodeBindingProfileRef` is the canonical field for agronomic code-binding profile governance.

`identityBindingRefs` and `codeBindingProfileRef` remain compatibility fields only. If compatibility fields and canonical agronomic fields are both present, their values must be equivalent for the same reference role. A conflict between compatibility and canonical agronomic fields must require review or fail closed depending on consequence level. New high-consequence examples and implementations should prefer the canonical agronomic fields.

### ONT-SEMINT.4 Temporal conformance law

OFARM records must preserve materially distinct time meanings when those distinctions affect interpretation, authority, evidence, currentness, or output safety. Observation or phenomenon time is not report time. Intended time is not execution time. Captured time is not accepted execution time. Assertion time is not occurrence time. Review, correction, dispute, and supersession time are not the original event time. Materialization and output generation time are not canonical event time.

The `TemporalFieldConformanceMatrix` is the companion/machine-contract surface that records required, optional, forbidden-substitution, and delayed-sync time-field expectations by record class. It does not replace the constitutional temporal model; it makes that model easier to validate.

### ONT-SEMINT.5 High-consequence alias and reconstruction law

A high-consequence `QuerySpecification` that feeds Compliance Twin use, PassportView input, DocumentAssembly input, regulated submission, publication/export, or a reconstruction-policy-bound result must use version-pinned semantic path aliases. In those cases, each applicable `semanticPathAliases[]` item must carry `aliasVersionRef`, and the runtime must retain an alias-resolution trace.

A high-consequence output must not pass silently when alias resolution, reference resolution, reconstruction policy, reconstruction trace, materialization freshness, code-binding status/currentness, geometry or partial-extent policy, correction/dispute policy, evidence sufficiency, or authority decision is unresolved, stale, ambiguous, or conflicting. The permitted dispositions are governed acceptance, `REQUIRE_REVIEW`, `REFUSE_OUTPUT`, or a policy-declared successor behavior.

### ONT-SEMINT.6 External registry currentness law

External registries and standards remain semantic anchors, code bindings, runtime surfaces, exchange mappings, or attestation wrappers. They do not become hidden OFARM law and they do not mutate OFARM core meaning.

When a high-consequence output depends on current external registry status, the runtime must use a profile-declared snapshot/currentness posture. For crop-protection product authorisation identity, a jurisdictional product-authorisation record is the required checking surface where the active profile says so. EU active-substance records, trade names, commercial product identifiers such as GTIN, and other adjunct vocabulary records may support evidence and cross-checking, but they do not by themselves establish jurisdictional product authorisation for high-consequence use.

The Belgium crop-protection currentness profile is accepted as a narrow package-local profile/conformance closure. It requires Belgian jurisdictional authorisation-number binding, ReferenceSnapshot support, ExternalRegistryVerificationTrace support, currentness/access-date handling, and fail-closed or review-required outcomes for free-text product name only, GTIN-only evidence, active-substance-only evidence, missing snapshot, missing access date, wrong jurisdiction, stale or unavailable registry evidence, ambiguity, and prescription/as-applied product mismatch.

### ONT-SEMINT.7 PassportView and DocumentAssembly disposition

PassportView must not represent unresolved, disputed, stale, externally unverified, or review-required material as accepted truth. A PassportView may disclose limitations only according to its reconstruction policy and output-disposition trace.

DocumentAssembly may annex unresolved, disputed, refused, stale, or verification-failure evidence when its purpose permits, but annexing does not promote the annexed material into canonical truth, accepted event consequence, current-state fact, or PassportView-safe result.

### ONT-SEMINT.8 New baseline concepts reflected by this addendum

The following concepts are now baseline-recognized OFARM-owned or OFARM-governed semantic-integrity carriers/surfaces:

- `ReferenceResolutionManifest`
- `ReferenceResolutionFinding`
- `ReferenceResolutionReport`
- `TemporalFieldConformanceMatrix`
- `ExternalRegistryVerificationTrace`

These objects make traceability and output gating executable. They do not create new canonical truth by themselves.

### ONT-SEMINT.9 Non-claims preserved

This addendum does not claim live external registry integration, live Phytoweb integration, legal advice, production runtime readiness, external-standard readiness, full wire-level interoperability, livestock scope expansion, or full jurisdictional/crop/profile coverage.

### ReferenceResolutionManifest
A governed policy object declaring package-local and external reference-resolution scope, consequence posture, and required resolution behavior for a package, runtime scope, or conformance run.

### ReferenceResolutionFinding
A traceable finding describing whether a specific reference resolved, failed, required review, used an alias, was stale, was externally declared, or was externally verified.

### ReferenceResolutionReport
A traceable report aggregating reference-resolution findings for a package, runtime evaluation, query, materialization, or output gate.

### TemporalFieldConformanceMatrix
A companion/machine-contract surface mapping required, optional, forbidden-substitution, and delayed-sync time semantics by record class.

### ExternalRegistryVerificationTrace
A traceable evidence and gate-support carrier recording external registry/source lookup inputs, source surface, candidate count, selected identifier, status/dates observed, snapshot basis, discrepancies, availability, and downstream disposition. It is not canonical truth by itself.

---

## ONT-SEMINT v0.3 baseline-harmonisation addendum — 2026-05-14

Status: active baseline law harmonising accepted ONT-SEMINT v0.1 and v0.2 RFC/machine-contract closures into RC2.1.

This addendum is a controlled semantic-integrity patch. It does not replace the Constitution, change the assertion/history-first truth model, create a second agronomic truth model, or promote current-state projections, AI outputs, external registries, machine imports, PassportViews, or DocumentAssemblies into canonical truth.

### A. Semantic conformance versus schema validation

OFARM implementations and package validators must distinguish at least these levels:

1. schema-valid object shape;
2. package-local reference resolution;
3. declared but unverified external reference posture;
4. verified external-reference posture under a declared profile;
5. runtime policy gates passed;
6. high-consequence output eligibility.

Schema validation alone is never sufficient to claim high-consequence output eligibility.

### B. Reference-resolution law

A package-local reference that is required for semantic interpretation must resolve to a package-local object of the expected class, or the consuming action must fail conformance, require review, or refuse output according to the consequence level and governing policy.

Externally anchored references may be declared without being package-local. They may support interpretation, evidence, or interoperability only under their declared role. They must not support high-consequence identity, compliance, attestation, or PassportView output unless the applicable profile requires and obtains sufficient `ReferenceSnapshot` and verification-trace evidence.

`ReferenceResolutionManifest`, `ReferenceResolutionFinding`, and `ReferenceResolutionReport` are OFARM-owned conformance carriers for this purpose. They record resolution policy and outcome. They do not create farm truth by themselves.

### C. Agronomic carrier reference canonicalization

For agronomic carrier shells, the canonical fields for agronomic identity and code-profile references are:

- `agronomicIdentityBindingRefs`
- `agronomicCodeBindingProfileRef`

Generic fields such as `identityBindingRefs` and `codeBindingProfileRef` may remain as compatibility fields only. If canonical and compatibility fields are both present, they must be equivalent. Conflict is a semantic-conformance problem and must require review or fail closed according to consequence level.

### D. Temporal conformance law

High-consequence OFARM records must preserve distinct time meanings when those meanings are material to interpretation or audit. Observation or phenomenon time, event or occurrence time, intended/planned time, execution time, captured time, assertion time, record/transaction time, effective interval, review/decision time, correction/dispute time, materialization time, and output-generation time must not be collapsed into a single generic timestamp.

The `TemporalFieldConformanceMatrix` is a conformance support artifact for this rule. It does not replace the constitutional temporal model.

### E. High-consequence query and output gate law

A high-consequence query or output path must not hide semantic meaning inside unpinned aliases, stale materialization, unresolved code bindings, unresolved partial extent, disputed facts, or missing authority/evidence decisions.

For Compliance Twin, PassportView, DocumentAssembly, regulated submission, publication/export, or reconstruction-policy-bound use, governed `SemanticPathAlias` use must be version-pinned or otherwise resolved through a traceable alias-resolution contract.

Before high-consequence output, the governing runtime must have or be able to produce the required reference-resolution report, alias-resolution trace, reconstruction policy/trace, materialization freshness outcome, code-binding/currentness outcome, geometry or partial-extent policy outcome, dispute/correction policy outcome, evidence-sufficiency outcome, and authority-decision outcome.

If a required gate is unresolved, stale, ambiguous, conflicting, or unavailable, the output must require review or be refused according to policy. It must not pass silently.

### F. External registry currentness and code-binding law

External registries and standards remain anchors, code bindings, exchange mappings, runtime surfaces, or attestation wrappers according to profile. They do not become hidden OFARM law.

For high-consequence crop-protection product identity, a jurisdictional product-authorisation record is the required governing external surface when the profile or jurisdictional context requires product authorisation. Free-text product name, commercial GTIN, active-substance-only evidence, EU-level evidence alone, wrong-jurisdiction evidence, stale source evidence, missing access date, missing required `ReferenceSnapshot`, registry unavailability, or prescription/as-applied identity mismatch must not silently support a current-compliant PassportView.

`ExternalRegistryVerificationTrace` is an OFARM-owned evidence/gate carrier for recording what external authority, jurisdiction, lookup surface, query inputs, candidate count, selected identifier, observed status/date context, snapshot, discrepancies, availability, and final outcome were used. It does not create canonical farm truth by itself.

The Belgium/Phytoweb crop-protection authorisation profile is a narrow accepted profile and package-local conformance proof. It does not claim live registry integration, legal advice, external-standard readiness, or production runtime readiness.

### G. PassportView and DocumentAssembly disposition

`PassportView` must not represent unresolved, disputed, stale, externally unverified, or wrong-jurisdiction material as accepted current truth.

`DocumentAssembly` may annex unresolved, disputed, failed, or unavailable verification material only when the governing reconstruction/output policy allows it. Annexing material does not promote it.

### H. Scope and non-claims

This harmonisation does not expand OFARM beyond the crop-only release boundary. It does not close livestock semantics. It does not claim live external registry verification, production runtime readiness, broad external-standard readiness, or legal-advice status.

---

## Agentic AI baseline-safety clarification addendum — 2026-05-14

Status: active baseline-law clarification for pre-implementation agentic AI and world-model readiness.

This addendum is protective and narrow. It does not replace the Constitution, does not create a new truth model, does not promote the draft agentic machine contracts into active law, and does not claim runtime, production, two-agent, world-model-compliance, or external-standard readiness.

### AAI-C.1 No hidden truth or hidden governance

OFARM must not become a system where AI outputs, agent memories, chain-of-agent scratch state, runtime tool-call results, operation-success responses, projections, caches, public read models, compiled-output previews, scenario states, or world-model states become hidden truth stores or hidden governance decisions.

Canonical truth remains assertion/history-first. Current state remains a governed materialization. Compiled outputs remain output classes with explicit basis and disposition. Public surfaces and AI-facing tools are runtime affordances, not new truth substrates.


### AAI-C.1.1 AI-facing release qualification gate

Any AI-facing, public-operation, state-affecting, or high-consequence release surface is release-eligible only if it can produce explicit, machine-readable release qualification for the relevant answer, operation, preview, brief, summary, or generated output.

Where applicable, the qualification must expose the governed basis and material limitations for:

- assertion/history, query, current-state, output, advisory, or bridge basis;
- materialization freshness and computation status;
- authority, delegation, revocation, approval, and human-review posture;
- evidence sufficiency, missing evidence, and evidence-use limits;
- reference, alias, code-binding, external-currentness, and profile applicability posture;
- disputed, corrected, superseded, or contested material;
- Advisory-only, scenario, world-model, or BridgeCandidate proposal-only disposition;
- sharing, redaction, data-sovereignty, and permission-limited answer posture;
- compiled-output, publication, export, PassportView, or DocumentAssembly disposition limits;
- blocked-action, refusal, review-required, or other gate-failure reasons.

Suppressing, omitting, or hiding a material qualification is a governance failure, not a display preference. The gate does not create a new truth substrate and does not promote `ResultQualificationEnvelope`, trace-retrieval schemas, public-operation schemas, or any other draft machine contract into active law; later active RFCs may standardize the concrete contract shape.

### AAI-C.2 Agent-generated status is provenance, not an artifact family

Generated-by-agent status is provenance, authority, and review context. It is not a separate artifact family and does not create a generic `AgentOutput` truth bucket.

Agent-generated material must resolve to an existing OFARM category or governed future category, such as draft assertion, observation, evidence record, hypothesis, advisory output, planned intervention, BridgeCandidate, review request, query specification, document draft, compiled output class, local knowledge artifact, sharing request, EvidenceNeed, or ObservationRequest.

### AAI-C.3 Software-agent actorship boundary

A software agent may participate only through explicit governance. Agent identity must distinguish, at minimum and where relevant:

- the accountable human or organizational sponsor/controller;
- the software-agent profile;
- the deployed agent instance;
- the model/tool profile or runtime capability basis;
- the authority grant or delegated envelope;
- the requested AuthorityActionClass;
- the target scope, time, and twin.

Agent identity does not itself confer authority. A model identifier, tool identifier, product feature, prompt instruction, or application session is not an AuthorityGrant.

As of AAI-CP3, sponsor-bound software-agent actorship is an active controlled-promotion subset. A state-affecting or high-consequence software-agent action must resolve an explicit sponsor, executing agent instance, actorship basis, authority snapshot, requested AuthorityActionClass, target scope, twin context, revocation posture, and authorization trace before it can be treated as permitted. Missing sponsor, missing authority snapshot, stale or revoked authority, or silent delegation defaults to deny, require review, or require human approval according to the applicable gate.

AAI-CP3 promotes only the actorship and sponsor-bound authority subset. CP4 separately promotes the bounded run, trace, blocked-action, output-disposition, and handoff subset described below. CP3 still does not promote AgentToolManifest, world-model runtime, EvidenceNeed, ObservationRequest, autonomous compliance decisioning, two-agent compatibility, production readiness, or external-standard readiness.

As of AAI-CP4, a state-affecting, high-consequence, or multi-step software-agent run must be bounded by an explicit run envelope and explained by a retrievable run trace. The active CP4 subset requires run envelope, input bundle, freshness requirement, approval checkpoint, stop condition, tool-invocation trace, output-disposition record, blocked-action trace, handoff envelope where applicable, and result-qualification linkage. A blocked action is a traceable governance outcome, not an invisible non-event. A handoff may carry task context but does not silently transfer authority, sharing permission, approval, evidence sufficiency, freshness posture, or promotion rights; the receiving agent must independently reauthorize and revalidate before acting.

### AAI-C.3.1 Capability and tool manifest boundary

As of AAI-CP5, manifest and tool self-description are active only as bounded descriptive governance surfaces. `AgentToolManifest`, `AgentToolDescriptor`, `AgentSupportSection`, and related manifest-honesty contracts may describe callable operations, declared hints, side-effect classes, approval requirements, semantic preconditions, external-call posture, trace-retention posture, redaction/permission-limited result policy, data-learning posture, and readiness-claim limits.

A manifest, tool descriptor, capability overlay, declared hint, API catalog, tool annotation, model card, deployment feature flag, or vendor readiness claim is not an AuthorityGrant, not an approval, not evidence sufficiency, not pack activation, not publication/export approval, not a Compliance Twin mutation, and not governance success. Manifest metadata must remain subordinate to the active authority, evidence, freshness, pack, query, sharing, output, run-trace, and twin-separation gates.

Read-only, safe, idempotent, destructive, or external-call hints are untrusted hints until reconciled with active OFARM policy and runtime enforcement. If a manifest or descriptor overclaims readiness, omits side effects, hides network egress, misstates read/write posture, lacks evidence for a readiness claim, or conflicts with an active governance gate, the applicable operation must deny, require review, require human approval, or emit a qualified result according to policy.

AAI-CP5 promotes only capability/tool manifest honesty and readiness-claim-limit contracts. It does not promote world-model runtime, `WorldModelRun`, `WorldModelState`, `ScenarioSpec`, `ScenarioResultSet`, `EvidenceNeed`, `ObservationRequest`, output assembly preview, runtime AI-agent readiness, two-agent compatibility, autonomous compliance decisioning, production readiness, live registry integration, legal advice, or external-standard readiness.

### AAI-C.4 World-model and scenario-state boundary

World-model runs, scenario states, simulation memory, model confidence, prediction state, and advisory digital-twin state belong to the Advisory Twin unless separately bridged and accepted through normal OFARM governance.

World-model state is not canonical truth, not Compliance Twin state, not current-state materialization, not an accepted event consequence, not evidence sufficiency by itself, and not a high-consequence compliance basis by itself.

OFARM does not create a third AI Twin. World-model outputs must remain Advisory material, or must pass through explicit bridge, review, authority, evidence, freshness, and promotion gates before any harder use.

### AAI-C.5 Query, authority, evidence, and promotion preservation

AI-mediated retrieval and AI-agent operation must preserve the existing query, authority, evidence, and promotion disciplines.

An AI or agent may help formulate a QuerySpecification, draft an artifact, propose a bridge, request evidence, prepare a dossier, or summarize governed results. It may not bypass QuerySpecification/QueryPlanIR where those are required, bypass evidence sufficiency, bypass authority checks, bypass review, bypass pack/context governance, or treat a permission-limited or stale result as complete truth.

### AAI-C.6 Human-governed defaults reaffirmed

The following remain human-governed by default unless explicitly relaxed by later active law:

- review acceptance, rejection, contest, and supersession;
- pack installation, activation, deactivation, and context-governance decisions;
- official output approval;
- attestation and signing;
- filing and submission;
- high-consequence Compliance Twin promotion;
- grant, revocation, or expansion of sharing/authority beyond pre-authorized scope.

### AAI-C.7 Future RFC lane

Future agentic AI and world-model amendments should be introduced through controlled RFCs, companion artifacts, machine contracts, examples, and conformance tests. CP2 separately promoted the public-surface/result-qualification subset. CP3 separately promotes the sponsor-bound actorship subset: `SoftwareAgentProfile`, `AgentInstance`, `AgentSponsorRef`, `AgentModelToolProfile`, `AgentAuthorityEnvelope`, `AgentRevocationState`, `AgentActorshipBinding`, and `AgentAuthorizationDecisionTrace`. CP4 separately promotes the bounded run/trace/handoff subset: `AgentRunEnvelope`, `AgentRunTrace`, `AgentToolInvocationTrace`, `AgentOutputDisposition`, `AgentBlockedActionTrace`, `AgentHandoffEnvelope`, `AgentRunInputBundle`, `AgentRunStopCondition`, `AgentRunApprovalCheckpoint`, and `AgentRunFreshnessRequirement`. CP5 separately promotes the capability/tool manifest honesty subset: `AgentToolManifest`, `AgentToolDescriptor`, `AgentSupportSection`, `AgenticCapabilityManifestOverlay`, `AgentToolEffectClassification`, `AgentToolApprovalRequirement`, `AgentToolSemanticPrecondition`, `AgentExternalCallPolicy`, `AgentTraceRetentionPolicy`, `RedactionAndPermissionLimitedResultPolicy`, `AgentToolDeclaredHintSet`, `AgentDataLearningPolicy`, and `AgentCapabilityReadinessClaimLimit`.

Candidate terms not yet promoted include `WorldModelCalibrationEvidence`, minimum-capture-profile law, formula/default calculation law, and output assembly preview. `WorldModelRun`, `WorldModelState`, `ScenarioSpec`, and `ScenarioResultSet` were promoted only as bounded Advisory Twin contract families by CP7. `EvidenceNeed` and `ObservationRequest` are promoted only as bounded request-layer contract families by CP8.

## AAI-CP7 advisory world-model contract addendum — 2026-05-16

As of AAI-CP7, `WorldModelRun`, `WorldModelState`, `WorldModelInputBasis`, `WorldModelObservationBasis`, `WorldModelAssumptionSet`, `WorldModelUncertaintyStatement`, `WorldModelValidityWindow`, `WorldModelInvalidationRule`, `WorldModelOutputDisposition`, `WorldModelGovernanceBlocker`, `WorldModelReconciliationRecord`, `ScenarioSpec`, and `ScenarioResultSet` are promoted only as bounded Advisory Twin contract families.

The promotion makes world-model material representable, traceable, uncertainty-qualified, validity-windowed, invalidation-aware, and reconcilable. It does not make world-model state canonical truth, Compliance Twin state, current-state materialization, evidence sufficiency, accepted event consequence, official output approval, or high-consequence compliance basis by itself.

A world-model output may support a hypothesis, risk flag, scenario result, draft plan, candidate request, or BridgeCandidate proposal. Any harder use must pass through explicit bridge, authority, evidence, freshness, review, promotion, sharing, output-disposition, and result-qualification gates. `WorldModelCalibrationEvidence`, `EvidenceNeed`, and `ObservationRequest` remain unpromoted in CP7.

## AAI-CP8 EvidenceNeed and ObservationRequest addendum — 2026-05-16

As of AAI-CP8, `EvidenceNeed`, `ObservationRequest`, `EvidenceOption`, `RequestTargetScope`, `RequestBurdenEstimate`, `RequestPriorityClassification`, `RequestRelevanceWindow`, `RequestCompletionCriteria`, `RequestLifecycleState`, `RequestSatisfactionTrace`, `RequestNoiseControlEnvelope`, `RequestBlockingBasis`, `RequestDeduplicationKey`, `RequestDisplayEnvelope`, and `RequestGovernanceBlocker` are promoted only as bounded request-layer contract families.

The promotion makes missing-information needs and observation requests explicit, burden-aware, relevance-windowed, deduplicated, display-governed, lifecycle-traceable, and result-qualified. It does not make a request evidence, an accepted assertion, a compliance obligation, a compliance blocker, evidence sufficiency, output approval, or a high-consequence compliance basis by itself.

A request may point to an external rule, governance gate, pack requirement, output policy, sharing policy, or human decision that supplies blocking force. The request alone is not the blocker. Satisfying a request may create candidate evidence or a review item, but accepted evidence still requires normal OFARM evidence, authority, quality, review, promotion, and dispute handling.

Minimum capture profile law, formula/default calculation law, and output assembly preview remain unpromoted by CP8.


## CP11 Sustainable Autonomous Farming Charter baseline addendum — 2026-05-21

Status: active CP11 baseline-law harmonisation, accepted by architect merge on 2026-05-28.

This addendum introduces a bounded Sustainable Autonomous Farming Charter layer into the OFARM model law. It is a controlled extension. It does not replace the Constitution, does not create a second truth model, does not alter assertion/history-first authority, does not promote current-state materialisations into deeper truth, does not collapse Advisory Twin and Compliance Twin, and does not authorise robot, machine, or actuator execution.

### CP11-C.1 Charter purpose and boundary

The Sustainable Autonomous Farming Charter is OFARM's governed sustainability layer for crop-farming operational contexts. It defines how sustainability constraints, optimisation objectives, trade-offs, evidence requirements, claim-basis rules, approval gates, exceptions, breaches, risk budgets, and regret-budget hooks are represented and governed.

The charter is executable governance, not marketing prose. Every operative charter rule must be classifiable as one or more of:

- hard constraint;
- optimisation objective;
- evidence obligation;
- human approval gate;
- agent authority limit;
- robot authority hook;
- learning permission;
- data-sharing limit;
- exception rule;
- breach rule;
- claim-basis rule;
- output-qualification rule.

A charter rule, charter evaluation, sustainability objective, exception, breach record, or sustainability claim basis is not canonical farm truth merely because it exists. Any harder consequence must pass through existing OFARM truth, authority, evidence, review, promotion, current-state, output, sharing, and twin-boundary law.

### CP11-C.2 CP11 core concepts

The following CP11 concepts are baseline-recognised OFARM-governed concepts and must be represented in the Alignment Register before they are treated as constitutional core:

- `SustainableFarmingCharter`;
- `CharterApplicabilityContext`;
- `CharterRuleClass`;
- `SustainabilityConstraint`;
- `SustainabilityObjective`;
- `ObjectivePriority`;
- `TradeoffPolicy`;
- `SustainabilityEvidenceRequirement`;
- `SustainabilityMetricProfile`;
- `SustainabilityClaimBasis`;
- `SustainabilityOutputQualification`;
- `SustainabilityPolicyEvaluationTrace`;
- `CharterApprovalGate`;
- `CharterException`;
- `CharterBreach`;
- `RiskBudget`;
- `RegretBudget`.

These concepts may be detailed by accepted RFCs, companion artifacts, machine contracts, and conformance fixtures, but they may not be introduced silently through a pack, app, adapter, AI behaviour, dashboard, or external standard.

### CP11-C.3 Hard constraints and optimisation objectives

A `SustainabilityConstraint` is a non-tradeable or rule-bound charter condition that must not be violated under normal policy. A hard constraint may be overridden only through an explicit `CharterException` path if the active charter allows such an exception.

A `SustainabilityObjective` is an optimisation target used to compare, rank, recommend, simulate, plan, or explain candidate actions. An optimisation objective does not create authority, does not create truth, does not satisfy evidence sufficiency, and does not override a hard constraint.

Report-only posture is not a constraint strength. A report-only sustainability indicator, metric posture, objective note, or priority annotation may require disclosure, monitoring, evidence request, or review, but it must not be represented as a `SustainabilityConstraint` or used as a hard-constraint pass/fail condition unless separate active charter law classifies it as a hard constraint. Report-only posture belongs to objective, metric, or priority surfaces and remains subordinate to hard constraints, evidence sufficiency, claim-basis, authority, and output-qualification gates.

A `TradeoffPolicy` must distinguish, at minimum, allowed trade-offs, review-required trade-offs, human-approval-required trade-offs, prohibited trade-offs, emergency-exception-only trade-offs, and insufficient-basis outcomes.

### CP11-C.4 Sustainability evidence, metrics, and claim basis

A sustainability-sensitive recommendation, plan, output, exception, breach finding, or claim-bearing artifact must declare its evidence posture according to the applicable `SustainabilityEvidenceRequirement`.

A `SustainabilityMetricProfile` must distinguish measured, sampled, lab-confirmed, machine-reported, sensor-derived, satellite-derived, modelled, inferred, estimated, self-declared, externally attested, certified, disputed, stale, and insufficient evidence postures where these distinctions are material.

A sustainability claim must not be produced, frozen, filed, exported, attested, or shown as claim-ready unless the required `SustainabilityClaimBasis` is present or the output clearly exposes that the claim basis is missing, insufficient, advisory-only, stale, disputed, or review-required.

Modelled or inferred sustainability values must not be represented as measured values. An AI summary, PassportView, DocumentAssembly, dashboard, generated document, or public operation result must not convert weak, stale, inferred, or partial evidence into stronger sustainability posture by presentation.

### CP11-C.5 Charter-sensitive current-state reliance

A charter-sensitive recommendation, charter evaluation, sustainability claim, exception, breach finding, or output that materially relies on current-state materialisation is a high-consequence use for the relevant materialisation basis.

Before such use, OFARM must ensure the relevant materialisation is freshly recomputed for that use or demonstrably still `FRESH` under the declared policy. If the materialisation is `STALE` or `INVALID`, the permitted outcomes are recompute, require review, require human approval, refuse action, refuse output, or another policy-declared blocked disposition.

### CP11-C.6 Advisory and Compliance Twin boundary for sustainability

Sustainability simulations, optimisation outputs, modelled natural-capital values, charter-risk flags, scenario results, and advisory sustainability recommendations belong to the Advisory Twin unless bridged through explicit OFARM governance.

Advisory sustainability material may request evidence, raise risk flags, generate scenario results, prepare a review package, propose a plan, propose a BridgeCandidate, or recommend a next step. It may not directly create a Compliance Twin fact, accepted executed consequence, official sustainability claim, charter breach with hard consequence, filed submission, attestation, or hidden current state.

### CP11-C.7 Charter authority and human-governed defaults

The following charter-sensitive actions are human-governed or human-approval-required by default unless a later active RFC explicitly relaxes the posture for a bounded action class:

- setting or changing objective priority;
- approving a prohibited or review-required trade-off;
- approving a charter exception;
- accepting, contesting, or resolving a charter breach with hard consequence;
- approving sustainability claim basis for high-consequence output;
- attesting or filing a sustainability claim;
- activating a pack/profile that changes sustainability constraints, evidence requirements, claim rules, or exception policy;
- approving risk or regret budgets where they affect high-consequence recommendations, experimentation, or future autonomous action.

A software agent may evaluate, recommend, simulate, explain, request evidence, prepare a dossier, or produce a charter evaluation trace only within its authority envelope. A software agent may not become a hidden governor of charter exceptions, objective hierarchy, claim attestation, pack activation, or Compliance Twin promotion.

### CP11-C.8 Charter exceptions and breaches

A `CharterException` is a governed, bounded, auditable override path. It is not a deletion of the rule. It must carry scope, time interval, affected rule, reason, evidence basis, approving authority, risk basis, expiry condition, review requirement, and output/claim consequence where applicable.

A `CharterBreach` records a suspected, confirmed, contested, resolved, superseded, false-positive, or exception-covered violation of a charter rule. A `CharterBreach` does not automatically become a legal nonconformity, Compliance Twin fact, accepted event consequence, or filed/attested claim unless a separate governed path creates that consequence.

### CP11-C.9 Pack/profile interaction

Packs and profiles may specialise charter constraints, objectives, evidence requirements, claim rules, metric profiles, trade-off policies, exception rules, and breach policies only through declared sustainability surface families and merge modes.

Sustainability pack/profile merge must fail closed where a conflict could weaken a hard constraint, hide an evidence requirement, misrepresent a metric method, alter claim basis, change objective priority without authority, or relax exception/breach policy without explicit governance.

External sustainability standards, buyer schemes, certification programmes, carbon methods, or environmental accounting methods may be admitted only as governed anchors, profiles, mappings, evidence sources, runtime-surface contracts, or attestation wrappers. They do not become hidden OFARM law, hidden truth stores, or hidden governance decisions.

### CP11-C.10 Deferrals

CP11 does not define robot mission law, command authority, geofence law, emergency-stop law, machine autonomy level, local fallback, physical safety incident law, or execution verification for cyber-physical systems. Those belong to CP12.

CP11 does not define the full experimentation, causal-learning, farm-memory, seasonal-learning, or learning-promotion model. Those belong to CP13.

CP11 does not define the full farm-to-farm intelligence, benchmark exchange, regional alert, federated learning, or derivative model-use boundary. Those belong to CP14.

CP11 does not define the full generated-software, adapter-generation, deployment, rollback, SBOM, or software-supply-chain governance model. Those belong to CP15.

CP11 does not expand OFARM beyond the crop-only release boundary into livestock identity, welfare, feeding, treatment, movement, herd/flock, or animal-health semantics.

### CP11-C.11 Non-claims

CP11 does not claim production sustainability-governance readiness, autonomous sustainability decisioning, robot/machine execution readiness, legal advice, certification advice, external sustainability-standard readiness, live environmental-registry integration, farm-to-farm intelligence readiness, generated-software deployment readiness, or livestock welfare readiness.

## CP12 Cyber-Physical Mission Envelope baseline addendum — 2026-05-28

Status: merged controlled baseline addendum for `OFARM_Cyber_Physical_Mission_Envelope_RFC_v0_1.md`.

CP12 introduces a bounded cyber-physical mission-envelope layer into OFARM model law. It does not replace the Constitution, create a second truth model, alter assertion/history-first authority, promote current-state materialisations into deeper truth, collapse the Advisory Twin and Compliance Twin, weaken CP11 charter gates, or make software agents physical governors.

Physical mission authority is not produced by recommendation, plan, preflight success, CP11 charter pass, agent confidence, tool invocation success, machine capability declaration, command acknowledgement, telemetry receipt, or adapter output alone. Mission dispatch requires explicit CP12 mission envelope, authority trace, safety envelope, command integrity, and applicable preflight/current-state/charter gates.

### CP12-C.1 Mission-envelope purpose and boundary

A cyber-physical mission is any OFARM-governed preparation, dispatch, monitoring, receipt, verification, or incident-handling path involving a physical actor that may move, sense, actuate, apply an input, affect a field/crop/zone, interact with a human/animal/environment, or create machine-reported evidence for a physical operation.

CP12 mission-envelope law applies to crop-farming contexts already within the active OFARM release boundary. It includes robots, drones, tractors, implements, actuators, irrigation devices, scouting devices, or other physical actors only to the extent they are represented through mission-envelope concepts. CP12 is not a vendor protocol, robot runtime, fleet optimisation system, or safety certification.

### CP12-C.2 CP12 core concepts

The following CP12 concepts are baseline-recognised OFARM-governed concepts and must be represented in the Alignment Register before they are treated as constitutional core: `CyberPhysicalMissionEnvelope`, `MissionIntent`, `MissionCandidate`, `MissionPlan`, `MissionScope`, `MissionLifecycleState`, `MissionPreflightTrace`, `MissionDispatchAuthorization`, `CommandEnvelope`, `CommandIntegrityBasis`, `CommandSignature`, `CommandAcknowledgement`, `ExecutionWindow`, `GeoFence`, `NoGoZone`, `RouteConstraint`, `MissionGeometryBasis`, `MissionGeometryValidationResult`, `MissionSafetyConstraint`, `PhysicalActorCapabilityProfile`, `RobotCapabilityProfile`, `MachineCapabilityProfile`, `MissionCapabilityCompatibilityResult`, `AutonomyLevelDeclaration`, `EmergencyStopPolicy`, `HumanOverridePolicy`, `LocalFallbackPolicy`, `LostLinkPolicy`, `RemoteTakeoverEvent`, `MissionTelemetryEnvelope`, `MissionExecutionReceipt`, `MissionVerification`, `MissionAbortEvent`, `NearMissEvent`, `PhysicalSafetyIncident`, and `MissionOutputQualification`.

These concepts may be detailed by accepted RFCs, companion artifacts, draft/non-default machine contracts, examples, and conformance fixtures. They may not be introduced silently through a vendor adapter, robot app, machinery payload, AI tool result, telemetry stream, output template, or pack.

### CP12-C.3 Mission stage separation

OFARM distinguishes mission intent, mission candidate, mission plan, preflight or dry-run result, dispatch authorisation, command envelope, command acknowledgement, telemetry, execution receipt, mission verification, and accepted execution consequence. No stage automatically promotes to a later stage merely because it exists, is machine-generated, is syntactically valid, or was accepted by an external system.

A `MissionPlan` is not a `CommandEnvelope`. A `CommandAcknowledgement` is not accepted execution truth. A `MissionExecutionReceipt` is evidence candidate material, not accepted execution truth by itself. A `MissionVerification` may support promotion only through ordinary OFARM review, evidence, current-state, and accepted-consequence law.

### CP12-C.4 Mission authority and human-governed defaults

CP12 adds mission-sensitive action classes including `MISSION_PREPARE_CANDIDATE`, `MISSION_REQUEST_PREFLIGHT`, `MISSION_APPROVE_PLAN`, `MISSION_APPROVE_DISPATCH`, `MISSION_DISPATCH_COMMAND`, `MISSION_ACKNOWLEDGE_COMMAND`, `MISSION_ABORT`, `MISSION_EMERGENCY_STOP`, `MISSION_OVERRIDE_TAKEOVER`, `MISSION_REPORT_TELEMETRY`, `MISSION_REPORT_EXECUTION_RECEIPT`, `MISSION_VERIFY_RESULT`, `MISSION_ACCEPT_VERIFICATION`, `MISSION_RECORD_NEAR_MISS`, `MISSION_RECORD_PHYSICAL_SAFETY_INCIDENT`, `MISSION_RESOLVE_PHYSICAL_SAFETY_INCIDENT`, and `MISSION_ACTIVATE_POLICY_PACK`.

Default posture remains deny unless an applicable authority path exists. Software agents may prepare mission candidates, request preflight, run advisory simulations, and prepare review packages within their authority envelope. Software agents may not dispatch physical commands by default. Mission dispatch is human-governed or human-approval-required unless later accepted law explicitly grants bounded policy authority for a specific low-risk mission class. Emergency stop must remain available through local safety and authorised human paths regardless of agent, pack, or vendor state.

### CP12-C.5 Preflight, current-state, and CP11 charter preconditions

Mission preflight or dry-run is no-side-effect evaluation. It may produce findings, blockers, evidence needs, charter-gate results, geometry findings, capability findings, safety findings, or review requirements. It may not create mission dispatch authority, command authority, accepted execution truth, Compliance Twin fact, or current-state mutation by itself.

Mission dispatch, command-envelope creation, command dispatch, mission verification, and accepted mission-execution consequence are high-consequence uses. Where such use materially relies on current-state materialisation, geometry, actor capability, safety posture, CP11 charter evaluation, authority status, pack/profile state, or external adapter mapping, the high-consequence freshness and basis rules apply. Silent dispatch is prohibited when required basis is stale, invalid, unavailable, disputed, insufficiently based, expired, or outside declared scope.

Where a mission materially implicates CP11 sustainability constraints, objectives, evidence, claim, exception, or breach posture, applicable CP11 gates must be evaluated before dispatch. A CP11 charter pass is a precondition where applicable, not dispatch authority.

### CP12-C.6 Geometry, execution-window, safety, capability, and command law

A dispatchable mission must declare a governed mission scope, geometry basis, geofence/no-go-zone/route posture where applicable, and an execution window with temporal coherence. Expired, inverted, ambiguous, stale, conflicting, or unsupported windows and geometries must block dispatch, require review, or require human approval according to policy.

A mission-sensitive path must evaluate mission safety constraints and physical actor capability before dispatch. Vendor capability, machine telemetry, adapter mapping, or static manifest support is descriptive and not safety proof or dispatch authority by itself.

A `CommandEnvelope` is the governed package that may be sent to a physical actor or adapter for dispatch. It must be bound to mission, dispatch authorisation, recipient, payload digest, expiry, and replay-protection posture as required by the accepted CP12 RFC and draft/non-default contracts. Command acknowledgement confirms only that an external actor or adapter acknowledged a command envelope according to the declared external boundary. It is not proof that the command was executed or completed.

### CP12-C.7 Telemetry, execution receipt, verification, incidents, and accepted consequences

Mission telemetry and execution receipts are evidence candidates. They may support reconstruction, review, verification, incident handling, current-state materialisation, or accepted execution consequences only through ordinary OFARM evidence, authority, review, promotion, current-state, and twin-boundary law.

Abort events, emergency-stop activations, fallback activations, remote takeovers, near misses, and physical safety incidents must be first-class records where applicable. A `NearMissEvent` or `PhysicalSafetyIncident` does not automatically create a legal compliance fact, insurance fact, liability determination, or Compliance Twin fact unless a separate governed path creates that consequence.

### CP12-C.8 External vendor and payload boundary

External machinery, robot, drone, actuator, sensor, irrigation, or tasking payloads may be mapped into OFARM only as external payloads, evidence candidates, command envelopes, telemetry envelopes, execution receipts, or adapter surfaces according to declared mapping coverage and loss posture. External systems do not become hidden OFARM truth stores, hidden authority stores, hidden mission plans, hidden mission approvals, or hidden dispatch authorities by being integrated.

### CP12-C.9 Deferrals and non-claims

CP12 does not define CP13 learning, experimentation, farm-memory, seasonal-learning, or learning-promotion law. CP12 does not define CP14 farm-to-farm intelligence, regional mission coordination, benchmark exchange, federated learning, derivative model-use, or shared fleet-coordination law. CP12 does not define CP15 generated-software delivery governance, robot adapter deployment, rollback, SBOM, build provenance, or generated workflow promotion. CP12 does not expand OFARM beyond the crop-only release boundary into livestock identity, welfare, feeding, treatment, movement, herd/flock, or animal-health semantics.

CP12 does not claim production robot readiness, machine-control readiness, autonomous field-operation readiness, safety certification, legal advice, insurance advice, livestock mission readiness, external vendor protocol completeness, live robot integration, live machinery integration, fleet optimisation readiness, CP13 readiness, CP14 readiness, or CP15 readiness.

### CP12-C.10 Minimum conformance baseline

For CP12 mission-sensitive use, a conforming implementation must demonstrate that mission candidates and preflight results do not create mission dispatch authority; CP11 charter pass does not create mission dispatch authority; software-agent tool success does not create mission dispatch authority; dispatch requires a mission envelope, authority trace, safety envelope, command integrity posture, execution window, and required geofence/no-go-zone basis where applicable; command acknowledgement, telemetry, and execution receipt do not create accepted execution truth by themselves; mission verification is distinct from mission execution receipt; near-miss and physical-safety incident records do not automatically create legal, insurance, or Compliance Twin facts; and CP12 does not create CP13, CP14, CP15, livestock, legal-certification, or production-autonomy claims.

## CP13 Learning, Experimentation, and Farm Memory baseline addendum — 2026-05-29

Status: merged controlled baseline addendum for accepted `OFARM_Learning_Experimentation_and_Farm_Memory_RFC_v0_1.md`.

CP13 introduces a bounded learning, experimentation, causal-evidence, farm-memory, and seasonal-learning layer into OFARM model law.

CP13 does not replace the Constitution, create a second truth model, alter assertion/history-first authority, promote current-state materialisations into deeper truth, collapse the Advisory Twin and Compliance Twin, weaken CP11 charter gates, weaken CP12 cyber-physical mission gates, or make software agents hidden farm-memory governors.

The CP13 invariant is:

`Learning output is not truth. Experiment result is not automatic causal fact. Farm memory is not hidden current state. Agent memory is not farm memory. Causal estimate is not compliance fact. Model improvement is not deployment authority. Mission or operation records may inform learning, but they do not become learning law by themselves.`

A CP13 artifact may affect harder OFARM outcomes only through explicit authority, evidence, review, promotion, output, current-state, CP11, CP12, and later CP14/CP15 gates where applicable.

### CP13-C.1 Learning purpose and boundary

CP13 governs learning-sensitive uses where learning artifacts, experiment results, causal estimates, farm memory, seasonal summaries, or agent/model learning may materially affect recommendation, planning, claim, review, mission preparation, output, or future high-consequence reliance.

CP13 applies to crop-farming OFARM contexts already within the active baseline scope. It does not expand OFARM into livestock-specific learning, animal-welfare learning, herd/flock learning, feeding, treatment, movement, or animal-health learning law.

CP13 is not generic AI memory, farm-to-farm intelligence, federated learning, model deployment governance, generated-software delivery governance, or production autonomous self-improvement readiness.

### CP13-C.2 CP13 core concepts

The following CP13 concepts are baseline-recognised OFARM-governed concepts and must be represented in the Alignment Register before they are treated as constitutional core:

- `LearningScope`;
- `LearningHypothesis`;
- `ExperimentProtocol`;
- `TrialDesign`;
- `ExperimentalUnit`;
- `TreatmentArm`;
- `ControlCondition`;
- `RandomizationPlan`;
- `BlockingFactor`;
- `OutcomeMeasureSpec`;
- `OutcomeObservationSet`;
- `LearningEvidenceBundle`;
- `LearningEvaluationTrace`;
- `CausalEstimate`;
- `LearningPromotionDecision`;
- `FarmMemoryEntry`;
- `FarmMemoryInvalidationRule`;
- `FarmMemoryRetrievalQualification`;
- `SeasonalLearningSummary`;
- `LearningOutputQualification`;
- `ExperimentRollbackTrigger`;
- `ExperimentException`.

These concepts may be detailed by accepted RFCs, companion artifacts, draft/non-default machine contracts, and conformance fixtures. They may not be introduced silently through an app, pack, adapter, AI memory, vector store, dashboard, world-model state, or external model registry.

### CP13-C.3 Learning artifact family and truth boundary

CP13 learning artifacts are not alternate truth stores.

A `LearningHypothesis` is a testable proposition. It is not fact.

An `ExperimentProtocol` or `TrialDesign` governs learning design. It is not authority to perform a field operation, apply an input, dispatch a robot or machine, approve a CP11 charter exception, publish a claim, share data cross-farm, or deploy a model/software change.

An `OutcomeObservationSet` is grouped evidence input. It is not a causal conclusion by itself.

A `CausalEstimate` is a qualified estimate of an effect under declared scope, method, evidence, assumptions, uncertainty, and limitations. It is not causal truth, Compliance Twin fact, claim basis, or operational authority by itself.

A `FarmMemoryEntry` is governed, scoped, evidence-linked, retrieval-qualified, and invalidation-aware local farm memory. It is not hidden current state, hidden canonical truth, hidden governance, or agent memory.

A `SeasonalLearningSummary` is a season-bounded summary. It is not a blanket truth update or automatic current-state mutation.

### CP13-C.4 Learning scope and locality

High-consequence CP13 artifacts must declare a `LearningScope` or explicit inherited scope. A learning scope must identify the spatial, temporal, biological, operational, equipment, evidence, and reuse boundary within which the learning artifact may be interpreted.

Default posture:

`CP13 learning is local/farm-scoped unless CP14 explicitly governs cross-farm use.`

A farm memory entry, causal estimate, seasonal learning summary, or learning-derived recommendation must not be reused outside its declared `LearningScope` without retrieval qualification, scope-expansion review, or later CP14-governed exchange law.

### CP13-C.5 Experimentation and non-authorisation

An `ExperimentProtocol`, `TrialDesign`, `RiskBudget`, or `RegretBudget` does not authorise operations or missions by itself.

Operations still require ordinary OFARM operation/intervention law. Cyber-physical missions still require CP12. Sustainability-sensitive trial actions still require CP11. Cross-farm learning requires CP14. Model/software deployment requires CP15.

Where an experiment or trial would materially affect soil, water, biodiversity, chemical/input use, safety, mission authority, output claims, data sharing, or high-consequence decisions, applicable CP11 and CP12 gates remain in force.

### CP13-C.6 Outcome measures, evidence, and causal uncertainty

Where a learning output claims experimental or causal support, it must disclose whether outcome measures were predeclared, amended, added post hoc, excluded, substituted, or missing.

A CP13 `LearningEvidenceBundle` must preserve evidence provenance, quality, missingness, bias, stale/invalid status, current-state reliance where applicable, CP11/CP12 dependencies where material, and uncertainty.

A `LearningEvaluationTrace` must record the scope, design, assumptions, evidence basis, outcome-measure posture, missingness, comparison basis, uncertainty, review posture, blocked/review-required conditions, and output disposition used to evaluate a learning result.

A `CausalEstimate` must expose effect estimate, uncertainty, comparison basis, method, assumptions, scope, validity horizon, limitations, and prohibited uses. Weak, observational, modelled, post-hoc, or underpowered evidence must not be represented as strong experimental support.

### CP13-C.7 Learning promotion and farm memory

A learning result may become a `FarmMemoryEntry` only through a governed `LearningPromotionDecision`.

A `LearningPromotionDecision` may decide, at minimum:

- promote to farm memory;
- keep advisory-only;
- require more evidence;
- require review;
- reject;
- supersede;
- invalidate;
- restrict reuse;
- defer to CP14 or CP15 where cross-farm exchange or deployment is involved.

A `FarmMemoryEntry` must declare evidence basis, scope, validity horizon, retrieval qualification, invalidation rules, confidence/uncertainty posture, and prohibited uses.

Farm memory must not update current state, create Compliance Twin fact, create claim basis, or authorise mission/operation by itself.

### CP13-C.8 Farm memory invalidation and retrieval

A `FarmMemoryInvalidationRule` must identify conditions that cause a farm memory entry to expire, downgrade, require review, or be invalidated.

A `FarmMemoryRetrievalQualification` is required when farm memory is retrieved for learning-sensitive or high-consequence use. It must disclose scope match, freshness, evidence strength, uncertainty, limitations, current applicability, and prohibited uses.

A retrieved farm memory entry may inform recommendations, planning, review packages, BridgeCandidates, or advisory reasoning. It may not silently act as hidden current state, hidden evidence sufficiency, hidden claim basis, hidden CP11 charter pass, hidden CP12 mission precondition, or hidden authority.

### CP13-C.9 Agent memory, training data, and model improvement boundary

Agent memory, model context, vector-store memory, prompt history, tool-call history, model weights, embeddings, and generated summaries are not OFARM farm memory.

A software agent may propose a learning hypothesis, prepare an experiment protocol draft, summarise outcome observations, propose a causal estimate, request evidence, prepare a learning evaluation trace candidate, or propose a farm-memory entry only within its authority envelope.

A software agent may not by default approve experiments, promote learning to farm memory, expand learning scope, approve cross-farm learning, deploy model/software changes, or create Compliance Twin facts.

A model improvement, prompt change, workflow change, adapter change, generated code artifact, or deployment candidate is not authorised by CP13. Deployment governance belongs to CP15.

### CP13-C.10 CP11 and CP12 integration

CP11 remains governing for sustainability-sensitive learning, experimentation, claims, charter evaluations, risk/regret budgets, exceptions, and output qualification.

CP12 remains governing for cyber-physical mission preparation, dispatch, command, telemetry, receipt, verification, incidents, and mission outputs.

CP12 mission telemetry, execution receipts, mission verification, near-miss records, and physical-safety incident records may serve as learning evidence candidates. They do not become learning conclusions, causal estimates, farm memory, or Compliance Twin facts merely by existing.

### CP13-C.11 Learning output qualification

A learning-sensitive output must carry a `LearningOutputQualification` where it may affect recommendation, planning, claim, review, mission preparation, CP11 charter evaluation, CP12 mission preparation, publication, export, or future high-consequence reliance.

A learning output must expose, where material:

- artifact type and lifecycle posture;
- scope;
- evidence strength;
- outcome-measure posture;
- causal strength;
- uncertainty;
- missingness;
- advisory/compliance posture;
- farm-memory promotion posture;
- CP11/CP12 dependencies;
- allowed uses;
- prohibited uses;
- required review or blocked-use reasons.

A learning output must not be represented as claim-ready, compliance-ready, mission-ready, deployment-ready, or cross-farm-shareable unless the applicable OFARM gates have been satisfied.

### CP13-C.12 Pack/profile interaction

Packs and profiles may specialise learning policy, experiment policy, outcome-measure rules, farm-memory retrieval/invalidation rules, learning-output qualification, and local-method profiles only through declared CP13 learning surface families and merge modes.

Learning pack/profile merge must fail closed where a conflict could weaken evidence requirements, hide uncertainty, loosen promotion rules, expand scope, alter invalidation posture, allow unsupported causal claims, bypass CP11/CP12 gates, or create hidden cross-farm/deployment authority.

### CP13-C.13 Authority and human-governed defaults

The following CP13 action classes are human-governed or human-approval-required by default unless a later active RFC explicitly relaxes posture for a bounded lower-risk class:

- approving an experiment protocol where it materially affects operations, CP11-sensitive decisions, CP12 mission preparation, or high-consequence outputs;
- approving learning promotion to farm memory;
- expanding a farm memory entry beyond its original learning scope;
- overriding a farm memory invalidation rule;
- approving a causal estimate for high-consequence use;
- approving a seasonal learning summary for publication, claim support, or external disclosure;
- approving cross-farm learning use, which remains CP14 territory;
- approving model/software deployment based on learning, which remains CP15 territory.

A software agent may support these workflows only within explicit authority and trace boundaries.

### CP13-C.14 Explicit deferrals

CP13 does not define farm-to-farm intelligence, federated learning, cross-farm benchmark exchange, regional alerts, derivative model-use policy, aggregation-floor rules, re-identification-risk handling, or cross-farm model contribution law. Those belong to CP14.

CP13 does not define generated-software delivery, model deployment, adapter generation, rollout, canary promotion, rollback, SBOM, build provenance, model-card governance, or deployment promotion. Those belong to CP15.

CP13 does not expand OFARM into livestock-specific learning, animal-welfare learning, herd/flock learning, feeding, treatment, movement, or animal-health learning law.

CP13 does not create production autonomous self-improvement readiness or production agronomic-advice certification.

### CP13-C.15 Non-claims

CP13 does not claim production autonomous self-improvement readiness, production agronomic advice certification, farm-to-farm intelligence readiness, federated learning readiness, regional alert readiness, model deployment readiness, generated-software readiness, CP14 readiness, CP15 readiness, legal advice, insurance advice, certification advice, or livestock learning readiness.


## CP14 Farm-to-Farm Intelligence Boundary baseline addendum — 2026-05-29

Status: accepted/merged CP14 controlled baseline addendum for `OFARM_Farm_to_Farm_Intelligence_Boundary_RFC_v0_1.md`.

CP14 introduces a bounded farm-to-farm intelligence boundary layer into OFARM model law.

CP14 governs cross-farm sharing, received intelligence, regional alerts, benchmark deltas, aggregation/deidentification/anonymisation claims, re-identification-risk assessment, derivative-use restrictions, training-use restrictions, federated-learning contribution boundaries, contribution-quality review, poisoning/anomaly review, revocation propagation, and cross-farm intelligence-output qualification.

CP14 does not replace the Constitution, create a second truth model, alter assertion/history-first authority, promote received intelligence into farm truth, collapse Advisory and Compliance Twins, weaken CP11 sustainability disclosure law, weaken CP12 cyber-physical mission boundaries, weaken CP13 local farm-memory boundaries, or make software agents hidden cross-farm sharing governors.

The CP14 invariant is:

`Cross-farm intelligence is advisory by default. Farm-to-farm sharing is not authority. Aggregation is not anonymisation by assertion. Regional alerts are not farm-level truth. Benchmark deltas are not compliance facts. Federated-learning contribution is not model deployment authority. CP13 local learning may not cross farm boundaries without CP14 governance.`

A CP14 artifact may affect harder OFARM outcomes only through explicit authority, evidence, review, promotion, current-state, output, CP11, CP12, CP13, and later CP15 gates where applicable.

### CP14-C.1 Farm-to-farm intelligence purpose and boundary

CP14 applies to farm-intelligence-sensitive use where farm-scoped data, summaries, evidence, sustainability indicators, mission/incident signals, local learning artifacts, farm-memory derivatives, regional alerts, benchmark deltas, aggregates, deidentified/anonymised datasets, federated-learning contributions, model-improvement signals, or received cross-farm intelligence materially affect recommendation, planning, warning, output, disclosure, claim, sharing, benchmark, model-improvement, or high-consequence reliance.

CP14 applies to crop-farming OFARM contexts already within the active baseline scope. It does not expand OFARM into livestock-specific cross-farm intelligence, animal-health intelligence, welfare intelligence, herd/flock intelligence, veterinary signal exchange, or public social-network law.

CP14 is not OFARM Social, OFARM Exchange, a public benchmark product, production federated-learning platform law, generated-software/model-deployment law, generic reputation law, or legal/certification/advice readiness.

### CP14-C.2 CP14 core concepts

The following CP14 concepts are baseline-recognised OFARM-governed concepts and must be represented in the Alignment Register before they are treated as constitutional core:

- `FarmIntelligenceBoundary`;
- `FarmIntelligenceSharePolicy`;
- `FarmIntelligenceShareGrant`;
- `FarmIntelligenceContribution`;
- `IntelligenceContributionPackage`;
- `LearningArtifactSharePackage`;
- `RecipientUseConstraint`;
- `DerivativeUsePolicy`;
- `TrainingUsePolicyBinding`;
- `RevocationPropagationTrace`;
- `RegionalAlert`;
- `RegionalRiskSignal`;
- `RegionalAlertCorrection`;
- `RegionalAlertWithdrawal`;
- `BenchmarkDelta`;
- `AggregationFloor`;
- `DeidentificationClaim`;
- `AnonymisationClaim`;
- `ReidentificationRiskAssessment`;
- `FederatedLearningContribution`;
- `FederatedAggregationReceipt`;
- `ModelImprovementSignal`;
- `TrainingUseReceipt`;
- `ContributionQualityAssessment`;
- `PoisoningOrAnomalyReview`;
- `CrossFarmApplicabilityAssessment`;
- `IntelligenceOutputQualification`.

These concepts may be detailed by accepted RFCs, companion artifacts, draft/non-default machine contracts, and conformance fixtures. They may not be introduced silently through an app, dashboard, pack, adapter, AI memory, cross-farm exchange payload, data-space import, buyer programme, federated-learning service, public benchmark, social feature, or sister platform.

### CP14-C.3 Cross-farm Advisory-default rule

Received cross-farm intelligence belongs to the Advisory Twin by default.

A `RegionalAlert`, `RegionalRiskSignal`, `BenchmarkDelta`, `FarmIntelligenceContribution`, `LearningArtifactSharePackage`, `FederatedAggregationReceipt`, `ModelImprovementSignal`, or other received intelligence artifact may raise risk flags, request observation, suggest review, inform advisory planning, qualify an output, or trigger a CP14-governed applicability assessment.

It may not directly create:

- farm-level occurrence truth;
- farm-level current state;
- Compliance Twin fact;
- accepted execution consequence;
- accepted CP11 sustainability claim;
- CP12 mission dispatch authority;
- CP13 farm-memory entry;
- CP15 model/software deployment authority;
- public benchmark claim;
- legal/certification/insurance conclusion.

A bridge from cross-farm intelligence toward harder OFARM consequences must pass ordinary OFARM authority, evidence, current-state, review, promotion, CP11, CP12, CP13, output, and later CP15 gates where applicable.

### CP14-C.4 Sharing and recipient-use law

Farm-to-farm sharing is a governed disclosure and use event. It is not authority to assert, review, decide, attest, file, promote, deploy, or operate.

A `FarmIntelligenceShareGrant` or equivalent CP14-governed share authorization must declare scope, source farm or contribution scope, recipient class, permitted purposes, prohibited purposes, retention posture, onward-sharing posture, derivative-use posture, training-use posture, revocation posture, redaction/aggregation/deidentification/anonymisation posture, and output-use limits.

A `RecipientUseConstraint` binds the recipient-side use of shared intelligence. A recipient may not expand received intelligence beyond declared purpose, scope, retention, derivative-use, training-use, onward-sharing, or output constraints merely because the payload is technically accessible.

A `DerivativeUsePolicy` governs whether derived features, summaries, benchmarks, model-improvement signals, embeddings, transformed datasets, aggregates, or downstream outputs may be created. Derivative use is not automatically allowed by sharing.

A `TrainingUsePolicyBinding` governs whether shared intelligence may train, fine-tune, evaluate, benchmark, or improve models. Training use is not automatically allowed by sharing, aggregation, deidentification, or platform access.

A `RevocationPropagationTrace` is required when a share grant, derivative-use permission, training-use permission, alert, benchmark, or intelligence package is revoked, narrowed, corrected, withdrawn, disputed, or invalidated in a way that materially affects downstream use.

### CP14-C.5 CP13 local learning and farm memory crossing boundary

CP13 local learning and farm memory are farm-scoped by default. A CP13 `FarmMemoryEntry`, `SeasonalLearningSummary`, `CausalEstimate`, `LearningEvaluationTrace`, `LearningEvidenceBundle`, or `LearningPromotionDecision` must not cross a farm boundary as shareable intelligence unless governed by CP14.

A `LearningArtifactSharePackage` must preserve scope, evidence basis, uncertainty, missingness, bias, limitations, invalidation posture, retrieval qualification, prohibited uses, and source-farm disclosure policy.

A received CP13-derived learning artifact remains Advisory by default and must not become local farm memory, current state, claim basis, mission authority, Compliance Twin fact, or model deployment authority without applicable OFARM gates.

### CP14-C.6 Regional alerts, risk signals, and applicability

A `RegionalAlert` or `RegionalRiskSignal` is not farm-level occurrence truth.

A regional pest, disease, weather, input, safety, sustainability, mission, or incident signal may indicate a regional risk context. It must not be treated as evidence that the same event, condition, infestation, disease, contamination, breach, mission incident, or risk exists on a particular farm without local evidence or a governed `CrossFarmApplicabilityAssessment`.

A `CrossFarmApplicabilityAssessment` must declare scope match, context similarity, evidence transferability, uncertainty, limitations, missing local evidence, and prohibited uses.

A `RegionalAlertCorrection` or `RegionalAlertWithdrawal` must propagate to materially affected downstream outputs, alerts, benchmark deltas, applicability assessments, agent runs, and query results where required by policy.

### CP14-C.7 Benchmark delta and public benchmark boundary

A `BenchmarkDelta` is not compliance fact, certification status, economic advice, legal conclusion, public ranking, or farm-performance truth by itself.

Benchmark outputs must declare cohort definition, aggregation floor, inclusion/exclusion criteria, data-quality posture, missingness, sample size class, re-identification risk, uncertainty, normalisation method, allowed uses, prohibited uses, and disclosure posture.

Public benchmark products, leaderboards, marketplace ratings, social reputation, or buyer-facing ranking systems are not created by CP14. They require separate product/sister-platform governance.

### CP14-C.8 Aggregation, deidentification, anonymisation, and re-identification risk

Aggregation is not anonymisation by assertion.

A `DeidentificationClaim` states a governed reduction of directly identifying detail. It does not claim irreversible anonymity unless separately supported.

An `AnonymisationClaim` requires explicit method basis, aggregation floor, residual-risk posture, re-identification-risk assessment, context limitation, and intended-use limitation. It must not be inferred merely from removal of names or farm identifiers.

A `ReidentificationRiskAssessment` is required where shared, published, partner-facing, or model-training uses rely on deidentification, anonymisation, aggregation, redaction, or cohorting to protect farm identity or commercial confidentiality.

### CP14-C.9 Federated-learning and model-improvement boundary

A `FederatedLearningContribution` is a governed contribution to a learning or aggregation process. It is not model deployment authority, software deployment authority, truth, current state, Compliance Twin fact, CP13 farm memory, or claim basis by itself.

A `FederatedAggregationReceipt` records aggregation or receipt posture. It is not proof that the resulting model is valid, safe, unbiased, deployable, authorised, or production-ready.

A `ModelImprovementSignal` may indicate that a model, heuristic, threshold, feature, benchmark, or candidate update may deserve review. It is not authority to deploy, fine-tune, update, activate, or promote a model or generated software artifact.

A `TrainingUseReceipt` records that a permitted training or evaluation use occurred under a declared policy. It does not expand future training, derivative, deployment, or sharing rights.

Model/software deployment governance belongs to CP15.

### CP14-C.10 Contribution quality, poisoning, and anomaly review

A `ContributionQualityAssessment` must qualify cross-farm intelligence by source trust posture, evidence quality, missingness, freshness, scope fit, method basis, uncertainty, anomaly posture, poisoning risk, and known limitations where relevant.

A `PoisoningOrAnomalyReview` is required when received intelligence, aggregate data, federated contributions, regional alerts, or benchmark deltas appear malicious, inconsistent, out-of-distribution, adversarial, contaminated, fabricated, commercially manipulated, or otherwise unsafe for reliance.

A poisoning or anomaly review may block, quarantine, downgrade, require review, require local confirmation, or mark downstream outputs as limited. It does not create Compliance Twin fact or blame/liability determination by itself.

### CP14-C.11 CP11, CP12, and sustainability/mission disclosure interaction

CP11 sustainability outputs, evidence, metrics, claim bases, charter breaches, exceptions, or risk budgets may not become cross-farm intelligence without CP14 disclosure and recipient-use governance.

CP12 mission telemetry, execution receipts, mission verification, near-miss events, physical safety incidents, emergency-stop activations, or mission safety records may not become cross-farm intelligence without CP14 disclosure, redaction, aggregation, re-identification-risk, recipient-use, and incident-sensitivity controls.

A CP14 output must preserve the original CP11/CP12/CP13 limitations, output qualifications, evidence posture, authority posture, and prohibited uses where material.

### CP14-C.12 Intelligence output qualification

A cross-farm intelligence output must carry an `IntelligenceOutputQualification` or equivalent result qualification when it is shared, received, displayed, exported, used by an agent, used in a query result, used in a benchmark, used in a regional alert, used in a model-improvement signal, or used in a high-consequence advisory context.

The qualification must disclose, where material:

- source type;
- sharing grant or lawful basis;
- recipient-use constraints;
- derivative-use and training-use posture;
- data-sovereignty boundary;
- aggregation/deidentification/anonymisation posture;
- re-identification-risk posture;
- contribution-quality posture;
- poisoning/anomaly-review posture;
- applicability assessment;
- Advisory-only status;
- output disposition;
- allowed and prohibited uses;
- uncertainty, missingness, evidence limitations, and correction/withdrawal status.

An intelligence output may not grant authority, create truth, create current state, create Compliance Twin fact, create claim basis, authorise missions, create farm memory, or deploy models by itself.

### CP14-C.13 Agent and tool-manifest boundary

A software agent may prepare, summarise, route, qualify, compare, or request review of cross-farm intelligence only within its authority envelope and applicable sharing/use constraints.

A software agent may not by default expand sharing, approve recipient use, approve derivative use, approve training use, override revocation, downgrade re-identification risk, treat received intelligence as local truth, promote regional signals to Compliance Twin fact, publish benchmarks, or deploy models.

Agent memory, model context, embeddings, vector stores, tool outputs, and generated summaries are not CP14 share grants, recipient-use approvals, training-use permissions, anonymisation claims, applicability assessments, or truth.

### CP14-C.14 Authority actions

CP14 adds farm-intelligence-sensitive action classes that must be evaluated under ordinary OFARM authority law, default deny, delegation, sharing, revocation, data sovereignty, and agent actorship rules.

The following action classes are baseline-recognised candidates for CP14 mapping in the Authority Action Matrix:

- `INTELLIGENCE_PREPARE_CONTRIBUTION`;
- `INTELLIGENCE_APPROVE_SHARE_GRANT`;
- `INTELLIGENCE_REVOKE_SHARE_GRANT`;
- `INTELLIGENCE_APPROVE_RECIPIENT_USE`;
- `INTELLIGENCE_APPROVE_DERIVATIVE_USE`;
- `INTELLIGENCE_APPROVE_TRAINING_USE`;
- `INTELLIGENCE_RECORD_TRAINING_USE`;
- `INTELLIGENCE_CREATE_REGIONAL_ALERT`;
- `INTELLIGENCE_CORRECT_OR_WITHDRAW_ALERT`;
- `INTELLIGENCE_CREATE_BENCHMARK_DELTA`;
- `INTELLIGENCE_APPROVE_PUBLIC_OR_PARTNER_BENCHMARK_OUTPUT`;
- `INTELLIGENCE_APPROVE_DEIDENTIFICATION_CLAIM`;
- `INTELLIGENCE_APPROVE_ANONYMISATION_CLAIM`;
- `INTELLIGENCE_ACCEPT_REIDENTIFICATION_RISK_ASSESSMENT`;
- `INTELLIGENCE_ACCEPT_FEDERATED_CONTRIBUTION`;
- `INTELLIGENCE_RECORD_FEDERATED_AGGREGATION_RECEIPT`;
- `INTELLIGENCE_CREATE_MODEL_IMPROVEMENT_SIGNAL`;
- `INTELLIGENCE_ACCEPT_POISONING_OR_ANOMALY_REVIEW`;
- `INTELLIGENCE_APPLY_REVOCATION_PROPAGATION`.

High-consequence CP14 action classes are human-governed or human-approval-required by default unless a later accepted RFC explicitly narrows that posture for a lower-risk class.

### CP14-C.15 Pack/profile surface law

CP14 permits pack/profile surfaces for farm-intelligence governance only where they do not mutate core OFARM meaning.

CP14 pack/profile surfaces may include sharing policy, recipient-use policy, derivative-use policy, training-use policy, aggregation floor, deidentification/anonymisation method profile, re-identification-risk threshold, regional-alert policy, benchmark-delta policy, contribution-quality policy, poisoning/anomaly-review policy, and intelligence-output qualification policy.

Packs must not weaken farm data sovereignty, sharing/revocation law, recipient-use constraints, CP11 claim limitations, CP12 mission/incident disclosure controls, CP13 farm-memory locality, or cross-farm Advisory-default posture without explicit governance.

### CP14-C.16 Conformance baseline

A conforming CP14 implementation must demonstrate, at minimum, that:

- received cross-farm intelligence remains Advisory by default;
- a regional alert does not create farm-level occurrence truth;
- a benchmark delta does not create compliance fact;
- a share package without a valid FarmIntelligenceShareGrant fails;
- recipient-use constraints block prohibited downstream use;
- derivative-use and training-use require explicit permission;
- revocation propagation blocks or qualifies materially affected downstream use;
- aggregation does not imply anonymisation;
- anonymisation claims require re-identification-risk assessment;
- public/partner benchmark outputs require aggregation floor and output qualification;
- CP13 local farm memory cannot cross farm boundaries without CP14 governance;
- federated-learning contribution does not authorise model deployment;
- model-improvement signal does not authorise model/software deployment;
- poisoning/anomaly review can quarantine or downgrade suspect intelligence;
- CP11 sustainability and CP12 mission/incident intelligence preserve their original limitations and disclosure controls;
- agents cannot approve sharing, derivative use, training use, benchmark publication, anonymisation claims, or model deployment by default.


### FarmIntelligenceBoundary
A governed boundary for cross-farm intelligence sharing, receiving, output, qualification, revocation, derivative use, training use, benchmarking, regional alerts, federated contributions, and applicability assessment.

### FarmIntelligenceShareGrant
A governed grant authorising a defined farm-intelligence sharing scope, recipient class, purpose, retention posture, recipient-use constraints, derivative-use posture, training-use posture, revocation posture, and disclosure limits.

### FarmIntelligenceContribution
A bounded contribution of farm-scoped or farm-derived information into a cross-farm intelligence context.

### IntelligenceContributionPackage
A governed package containing one or more farm-intelligence contributions plus basis, scope, limitations, permitted uses, prohibited uses, and output qualifications.

### LearningArtifactSharePackage
A CP14-governed package for sharing CP13 learning artifacts, preserving scope, evidence, uncertainty, invalidation, retrieval qualification, and prohibited uses.

### RecipientUseConstraint
A governed constraint limiting how a recipient may use, retain, transform, onward-share, disclose, derive from, or train on shared intelligence.

### DerivativeUsePolicy
A governed policy controlling creation and use of derived features, summaries, embeddings, transformed datasets, benchmarks, model-improvement signals, or other derivative outputs.

### TrainingUsePolicyBinding
A governed binding controlling whether shared intelligence may be used for model training, fine-tuning, evaluation, benchmarking, or improvement.

### RevocationPropagationTrace
A trace showing how revocation, withdrawal, correction, narrowing, dispute, or invalidation of shared intelligence propagated to downstream recipients, outputs, artifacts, or uses.

### RegionalAlert
A regional advisory signal or warning that does not by itself establish farm-level occurrence truth.

### RegionalRiskSignal
A regional advisory risk signal that may inform observation, review, or local applicability assessment.

### BenchmarkDelta
A qualified comparison or difference between a farm, field, crop-cycle, metric, practice, cohort, or aggregate and a declared benchmark context. It is not compliance fact by itself.

### AggregationFloor
A governed minimum cohort, spatial, temporal, contribution-count, diversity, or disclosure-safety threshold required before aggregate intelligence may be disclosed or used.

### DeidentificationClaim
A claim that certain direct identifiers or identifying features have been reduced, removed, transformed, or masked under a declared method. It is not irreversible anonymisation by itself.

### AnonymisationClaim
A stronger claim that information is anonymised for a declared context and use, requiring method basis, aggregation floor, residual-risk posture, and re-identification-risk assessment.

### ReidentificationRiskAssessment
A governed assessment of the risk that a farm, party, field, practice, event, incident, or commercially sensitive pattern can be inferred from shared, aggregated, deidentified, anonymised, or derived intelligence.

### FederatedLearningContribution
A governed contribution to a federated or distributed learning process. It is not model deployment authority.

### FederatedAggregationReceipt
A receipt that a federated or distributed aggregation process accepted, rejected, transformed, or used a contribution under a declared policy. It is not model deployment evidence by itself.

### ModelImprovementSignal
An advisory signal that a model, heuristic, threshold, benchmark, feature, or candidate update may deserve review. It is not deployment authority.

### TrainingUseReceipt
A trace that shared intelligence was used for permitted training, fine-tuning, evaluation, benchmarking, or model-improvement use under a declared policy.

### ContributionQualityAssessment
A governed assessment of contribution quality, including provenance, freshness, missingness, evidence strength, scope fit, anomaly posture, poisoning risk, and limitations.

### PoisoningOrAnomalyReview
A governed review of suspected malicious, anomalous, fabricated, out-of-distribution, adversarial, commercially manipulated, or unsafe cross-farm intelligence.

### CrossFarmApplicabilityAssessment
A governed assessment of whether and how received intelligence may be relevant to a receiving farm or context, without becoming local truth by default.

### IntelligenceOutputQualification
A result qualification for cross-farm intelligence outputs, disclosing source, sharing authority, recipient-use constraints, derivative/training posture, aggregation/deidentification/anonymisation posture, re-identification risk, Advisory-only status, allowed uses, prohibited uses, uncertainty, limitations, correction, withdrawal, and revocation status.


## CP15 Agentic Software Delivery and Model Deployment Governance baseline addendum — 2026-05-30

### CP15-C.1 Delivery-governance purpose and boundary

CP15 introduces **Agentic Software Delivery and Model Deployment Governance** as an OFARM constitutional boundary for generated software, generated adapters, generated semantic mappings, generated workflows, prompt/policy changes, model deployment candidates, release bundles, runtime-surface bindings, canary/rollback paths, deployment telemetry, and software-supply-chain incidents.

CP15 is delivery-governance law, not a CI/CD product specification, cloud topology, generic MLOps platform, cybersecurity certification, legal/security advice, or automatic deployment engine.

Generated software, generated adapters, generated mappings, model improvements, prompt/workflow changes, build success, test success, static-analysis success, security-scan completion, conformance-run completion, capability-manifest declaration, canary success, deployment telemetry, runtime-deployment receipt, or agent tool success do not create deployment authority, runtime authority, current/default promotion, mission authority, Compliance Twin fact, or production readiness by themselves.

Deployment requires explicit delivery-envelope governance, authority trace, provenance/SBOM/security/conformance evidence, applicable CP11/CP12/CP13/CP14 gates, runtime-surface binding, deployment authorization, rollback posture, output qualification, and conformance evidence.

### CP15-C.2 CP15 core concepts

CP15 recognises the following OFARM-owned delivery-governance concepts:

- **SoftwareDeliveryBoundary**
- **GeneratedSoftwareArtifact**
- **GeneratedPatchArtifact**
- **GeneratedAdapterArtifact**
- **GeneratedWorkflowArtifact**
- **GeneratedPromptOrPolicyArtifact**
- **SemanticMappingCandidate**
- **AdapterGenerationRequest**
- **BuildProvenance**
- **SBOMReference**
- **DependencyRiskAssessment**
- **StaticAnalysisResult**
- **SecurityScanResult**
- **SecurityFindingWaiver**
- **ConformanceTestPlan**
- **ConformanceRunReceipt**
- **DeploymentCandidate**
- **DeploymentPlan**
- **DeploymentAuthorization**
- **DeploymentPromotionDecision**
- **ReleaseBundle**
- **RuntimeSurfaceReleaseBinding**
- **CanaryPlan**
- **CanaryResult**
- **RollbackPlan**
- **RollbackEvent**
- **DeploymentTelemetryEnvelope**
- **RuntimeDeploymentReceipt**
- **ModelDeploymentCandidate**
- **ModelEvaluationEvidence**
- **PromptPolicyChangeCandidate**
- **WorkflowDeploymentCandidate**
- **SoftwareSupplyChainIncident**
- **DeploymentIncident**
- **DeploymentOutputQualification**

These concepts are delivery-governance shells. They do not create alternate truth stores, alternate authority stores, automatic current/default promotion, or production readiness.

### CP15-C.3 Generated artifacts are candidates, not runtime law

A generated artifact is not executable OFARM law merely because an agent produced it, a build succeeded, tests passed, a security scan found no blocking issue, or a reviewer viewed it.

Generated software, generated adapters, generated semantic mappings, generated workflows, generated prompts, and generated policies must resolve to explicit CP15 artifact classes and lifecycle states. They remain candidates until they pass applicable authority, provenance, security, conformance, pack/profile, runtime-surface, output-qualification, and deployment gates.

A generated adapter or semantic mapping candidate must not mutate OFARM core meaning, override external-standard boundary law, bypass pack/profile merge law, or convert lossy mappings into hidden truth.

### CP15-C.4 Delivery lifecycle and no-shortcut rule

CP15 separates at least the following stages:

- generated artifact;
- build provenance;
- SBOM/dependency/license/use-constraint assessment;
- static analysis and security scan;
- conformance test plan;
- conformance run receipt;
- deployment candidate;
- deployment plan;
- deployment authorization;
- release bundle;
- runtime-surface release binding;
- canary plan and canary result;
- deployment promotion decision;
- runtime deployment receipt;
- deployment telemetry;
- rollback event;
- deployment incident or software-supply-chain incident.

No later state is valid merely because an earlier state exists. A build artifact is not a deployment candidate by itself. A passed test is not deployment authorization. A canary result is not promotion. A runtime deployment receipt is not proof of safety, correctness, conformance, or production readiness by itself.

### CP15-C.5 Deployment authority and human-governed defaults

CP15 deployment-sensitive actions must be evaluated through explicit AuthorityActionClass law.

High-consequence CP15 actions are human-governed or human-approval-required by default unless a later accepted RFC explicitly narrows that rule for a low-risk class. These include, at minimum:

- approving a DeploymentAuthorization;
- approving a DeploymentPromotionDecision;
- promoting any schema, contract, pack, policy, prompt, workflow, adapter, model, or release bundle to current/default;
- approving a SecurityFindingWaiver for blocking or high-severity findings;
- approving deployment to a CP11/CP12/CP13/CP14-sensitive runtime surface;
- approving model deployment candidate release;
- approving rollback disablement or emergency rollback bypass;
- approving release of mission-adapter, farm-to-farm intelligence, sustainability-claim, farm-memory, or Compliance Twin-affecting code.

A software agent may prepare artifacts, generate candidates, run tests, collect evidence, package review bundles, perform preflight/dry-run where authorised, and report blocked actions. A software agent may not by default grant deployment authority, waive blocking security findings, promote current/default artifacts, or declare production readiness.

### CP15-C.6 Evidence, conformance, SBOM, and security gate

A CP15 DeploymentCandidate must declare the evidence required for its intended use class and runtime surface. Evidence may include build provenance, SBOM reference, dependency risk assessment, license/use-constraint assessment, static-analysis result, security-scan result, security-finding waiver where allowed, conformance test plan, conformance run receipt, runtime-surface binding, pack/profile compatibility, and applicable CP11/CP12/CP13/CP14 gate traces.

Evidence sufficiency is consequence-sensitive. Evidence sufficient for advisory sandbox deployment is not evidence sufficient for production, Compliance Twin, mission-adapter, cross-farm intelligence, sustainability-claim, current/default, or farmer-facing high-consequence deployment.

A ConformanceRunReceipt is evidence. It is not deployment authorization, production readiness, security certification, or current/default promotion by itself.

### CP15-C.7 Runtime-surface release binding

A release bundle must bind explicitly to the runtime surface on which it may operate. Runtime surfaces may include advisory sandbox, internal developer preview, farmer-facing advisory surface, Compliance Twin support surface, CP11 charter-sensitive surface, CP12 mission-adapter surface, CP13 learning/farm-memory surface, CP14 intelligence-sharing surface, public/export surface, or current/default contract/policy surface.

A release bundle authorised for one runtime surface must not silently operate on a stronger surface. Surface escalation requires explicit CP15 deployment authorization and applicable authority/evidence/conformance gates.

### CP15-C.8 Model, prompt, policy, and workflow deployment boundary

A model deployment candidate, prompt/policy change candidate, or workflow deployment candidate is not deployed, approved, trusted, or production-ready merely because it is derived from CP13 learning output, CP14 model-improvement signal, public model registry metadata, benchmark result, or agent-generated evaluation.

Model deployment requires model-evaluation evidence, intended-use and prohibited-use classification, runtime-surface binding, applicable CP11/CP12/CP13/CP14 gates, security/privacy/use-constraint review, deployment authorization, rollback posture, and output qualification.

A CP13 learning result or CP14 model-improvement signal may inform a model deployment candidate. It does not become deployment authority or model release approval.

### CP15-C.9 Canary, rollback, telemetry, and incident boundary

A canary plan or canary result may support deployment promotion review. It does not create deployment-promotion authority by itself.

Rollback posture is required for deployment candidates whose failure could affect high-consequence outputs, farm operational data, CP11 charter-sensitive outputs, CP12 mission paths, CP13 learning/farm-memory paths, CP14 cross-farm intelligence, Compliance Twin surfaces, or current/default artifact surfaces.

Deployment telemetry and runtime deployment receipts are evidence candidates. They do not create truth, compliance fact, conformance proof, security proof, or production readiness by themselves.

SoftwareSupplyChainIncident and DeploymentIncident records must be traceable, reviewable, and capable of triggering rollback, disablement, quarantine, evidence review, conformance re-run, or currentness downgrade where policy requires.

### CP15-C.10 Current/default promotion boundary

Current/default schema, contract, pack, profile, policy, model, prompt, workflow, adapter, release bundle, or runtime-surface binding promotion requires explicit currentness or deployment-promotion law.

CP15 does not promote CP11, CP12, CP13, CP14, or CP15 draft/non-default schemas to current/default. CP15 only defines the governance boundary for future promotion decisions.

### CP15-C.11 Interaction with CP11, CP12, CP13, and CP14

A deployment that affects CP11 charter-sensitive outputs, CP12 mission/command/adaptor surfaces, CP13 learning/farm-memory outputs, or CP14 cross-farm intelligence outputs must satisfy the relevant CP11, CP12, CP13, or CP14 gate in addition to CP15 gates.

CP15 does not replace those gates. It prevents generated software, model deployment, prompt changes, workflow changes, release bundles, or agent tooling from bypassing them.

### CP15-C.12 Deferrals and non-claims

CP15 does not create:

- a full CI/CD product specification;
- specific cloud/vendor deployment architecture;
- a generic MLOps platform;
- OFARM Social constitution;
- OFARM Exchange constitution;
- robot mission or command law;
- farm-to-farm intelligence law;
- production software-delivery readiness;
- production model-deployment readiness;
- cybersecurity certification;
- legal, security, compliance, privacy, insurance, or certification advice;
- automatic current/default schema promotion;
- autonomous release readiness.

CP15 remains implementation-directed with bounded debt until CP15 machine contracts, conformance fixtures, hostile review, implementation evidence, steward validation, security review, and pilot/runtime evidence exist.

### CP15-C.13 Minimum conformance baseline

A CP15-conforming implementation must be able to show, at minimum, that:

- generated artifacts cannot deploy without DeploymentAuthorization;
- build success does not create DeploymentAuthorization;
- security scan success does not create DeploymentAuthorization;
- conformance run success does not create DeploymentAuthorization;
- a blocking security finding cannot be waived without authorised waiver and trace;
- release bundles cannot bind silently to stronger runtime surfaces;
- canary success cannot promote deployment without DeploymentPromotionDecision;
- rollback posture is required for high-consequence deployment classes;
- runtime deployment receipt does not become conformance proof, truth, or production readiness;
- CP11, CP12, CP13, and CP14 gates cannot be bypassed by generated code, adapters, models, prompts, workflows, or deployment tooling;
- current/default promotion cannot occur without explicit promotion authority and currentness trace;
- agent tool success cannot become deployment authority.


CP15 adds delivery-governance semantics to OFARM-owned territory. These semantics govern how generated software and model-deployment candidates may become release candidates, deployment candidates, runtime-surface bindings, or current/default promotion candidates without bypassing existing OFARM truth, authority, evidence, conformance, pack/profile, output, agent, and CP11–CP14 laws.


CP15 adds the following delivery-governance artifact families:

- generated software artifact;
- generated patch artifact;
- generated adapter artifact;
- generated workflow artifact;
- generated prompt or policy artifact;
- semantic mapping candidate;
- build provenance artifact;
- SBOM/dependency/security evidence artifact;
- conformance test plan and conformance run receipt;
- deployment candidate;
- deployment plan;
- deployment authorization;
- deployment promotion decision;
- release bundle;
- runtime-surface release binding;
- canary and rollback artifacts;
- deployment telemetry and runtime deployment receipt;
- model deployment candidate and model-evaluation evidence;
- prompt/policy/workflow deployment candidate;
- software-supply-chain incident and deployment incident;
- deployment output qualification.

These are delivery-governance artifacts. They do not become canonical domain truth, Compliance Twin fact, current-state materialisation, mission authority, farm-memory truth, cross-farm intelligence truth, or production readiness by existence alone.


- software-delivery policy;
- generated-artifact policy;
- semantic-mapping policy;
- adapter-generation policy;
- conformance-test policy;
- deployment-authorization policy;
- release-bundle policy;
- runtime-surface binding policy;
- canary/rollback policy;
- security-finding waiver policy;
- model-deployment policy;
- prompt/workflow deployment policy;
- current/default promotion policy.


### 7.10e CP15 software-delivery and model-deployment authority actions

CP15 adds software-delivery and model-deployment action classes. These must be evaluated through ordinary OFARM authority law. A broad role, model confidence, build success, tool success, security scan, conformance run, capability declaration, canary result, or deployment telemetry is not an AuthorityGrant.

CP15 recognised action classes include:

- **DELIVERY_REGISTER_GENERATED_ARTIFACT**
- **DELIVERY_APPROVE_GENERATED_ARTIFACT_FOR_REVIEW**
- **DELIVERY_APPROVE_SEMANTIC_MAPPING_CANDIDATE**
- **DELIVERY_APPROVE_ADAPTER_GENERATION_REQUEST**
- **DELIVERY_ACCEPT_BUILD_PROVENANCE**
- **DELIVERY_ACCEPT_SBOM_REFERENCE**
- **DELIVERY_ACCEPT_DEPENDENCY_RISK_ASSESSMENT**
- **DELIVERY_ACCEPT_STATIC_ANALYSIS_RESULT**
- **DELIVERY_ACCEPT_SECURITY_SCAN_RESULT**
- **DELIVERY_APPROVE_SECURITY_FINDING_WAIVER**
- **DELIVERY_APPROVE_CONFORMANCE_TEST_PLAN**
- **DELIVERY_ACCEPT_CONFORMANCE_RUN_RECEIPT**
- **DELIVERY_CREATE_DEPLOYMENT_CANDIDATE**
- **DELIVERY_APPROVE_DEPLOYMENT_PLAN**
- **DELIVERY_AUTHORIZE_DEPLOYMENT**
- **DELIVERY_APPROVE_RELEASE_BUNDLE**
- **DELIVERY_BIND_RUNTIME_SURFACE**
- **DELIVERY_APPROVE_CANARY_PLAN**
- **DELIVERY_ACCEPT_CANARY_RESULT**
- **DELIVERY_PROMOTE_DEPLOYMENT**
- **DELIVERY_APPROVE_ROLLBACK_PLAN**
- **DELIVERY_TRIGGER_ROLLBACK**
- **DELIVERY_ACCEPT_RUNTIME_DEPLOYMENT_RECEIPT**
- **DELIVERY_RECORD_DEPLOYMENT_TELEMETRY**
- **DELIVERY_RECORD_SOFTWARE_SUPPLY_CHAIN_INCIDENT**
- **DELIVERY_RECORD_DEPLOYMENT_INCIDENT**
- **DELIVERY_RESOLVE_DEPLOYMENT_INCIDENT**
- **DELIVERY_APPROVE_MODEL_DEPLOYMENT_CANDIDATE**
- **DELIVERY_APPROVE_PROMPT_POLICY_CHANGE**
- **DELIVERY_APPROVE_WORKFLOW_DEPLOYMENT**
- **DELIVERY_PROMOTE_CURRENT_DEFAULT_ARTIFACT**
- **DELIVERY_REVOKE_OR_QUARANTINE_RELEASE**

By default, deployment authorization, release-bundle approval, runtime-surface binding to high-consequence surfaces, high-severity security waiver approval, model deployment approval, prompt/policy/workflow deployment approval, rollback-bypass approval, and current/default promotion are human-governed or human-approval-required.

Software agents may generate candidates, collect evidence, run tests, draft deployment plans, prepare review packages, and report blocked actions under explicit authority envelopes. They may not by default authorise deployment, waive blocking findings, promote current/default artifacts, or declare production readiness.


### 10.15e CP15 deployment and currentness high-consequence rule

A CP15 deployment-sensitive action is high-consequence when it can affect:

- current/default schema, contract, pack, profile, policy, model, prompt, workflow, adapter, or release-bundle state;
- Compliance Twin surfaces;
- CP11 sustainability claims or charter-sensitive outputs;
- CP12 mission/command/robot/machine adapter paths;
- CP13 farm-memory, learning-promotion, or causal-estimate surfaces;
- CP14 cross-farm intelligence, training-use, regional alert, or benchmark surfaces;
- farmer-facing high-consequence outputs;
- public/export/partner-facing outputs;
- security, secrets, credentials, signing keys, or authority tokens;
- rollback, emergency-disable, quarantine, or incident-handling paths.

High-consequence CP15 actions require explicit authority, provenance, evidence sufficiency, conformance posture, runtime-surface binding, rollback posture, output qualification, and applicable CP11–CP14 gate evaluation.

A build result, scan result, conformance run, deployment receipt, telemetry stream, canary result, capability declaration, or generated summary is not current state, not deployment authority, not promotion authority, and not production readiness by itself.


### 12.9 CP15 delivery artifact twin boundary

Generated artifacts, deployment candidates, canary results, model-evaluation evidence, deployment telemetry, conformance run receipts, and software-supply-chain findings are delivery-governance evidence. They belong to Advisory or governance/workflow posture by default unless explicitly accepted into a stronger governed consequence through ordinary OFARM authority, review, evidence, currentness, and promotion law.

They may support review, block deployment, request evidence, trigger rollback, qualify outputs, or prepare promotion decisions.

They may not directly create Compliance Twin facts, accepted execution consequences, accepted sustainability claims, accepted farm-memory entries, accepted cross-farm intelligence facts, mission dispatch authority, current/default promotion, or production readiness.

A bridge from delivery evidence toward Compliance Twin consequence, current/default promotion, runtime-surface release, or production claim must pass CP15 deployment governance and any applicable CP11, CP12, CP13, or CP14 gates.


### SoftwareDeliveryBoundary
A governed boundary defining how generated artifacts, build/security/conformance evidence, deployment candidates, release bundles, runtime-surface bindings, canary/rollback paths, and deployment incidents may affect OFARM runtime surfaces.

### GeneratedSoftwareArtifact
A software artifact generated or materially modified by a software agent or agentic development process, without deployment authority by itself.

### GeneratedAdapterArtifact
A generated integration or adapter artifact that maps external inputs, outputs, APIs, schemas, or vendor systems into OFARM runtime surfaces, without source-of-meaning authority by itself.

### SemanticMappingCandidate
A proposed semantic mapping whose coverage, loss, authority, and conformance must be governed before high-consequence use.

### BuildProvenance
A record of build inputs, process, environment, toolchain, source refs, agent/run refs, and artifact digest sufficient to reconstruct or assess a build.

### SBOMReference
A reference to software bill of materials information relevant to dependency, license, use-constraint, and supply-chain risk.

### SecurityFindingWaiver
A governed waiver of a security finding, not a security proof, and not valid without authority, scope, expiry, and trace.

### ConformanceRunReceipt
A record of conformance execution and results. It is evidence, not deployment authorization.

### DeploymentCandidate
A proposed deployment unit awaiting authority, evidence, runtime-surface, rollback, and conformance gates.

### DeploymentAuthorization
A governed authorization allowing deployment under specified scope, time, environment, surface, evidence, and rollback constraints.

### DeploymentPromotionDecision
A governed decision promoting or refusing a deployment candidate or release bundle for a specified runtime surface or currentness class.

### ReleaseBundle
A packaged set of deployment artifacts, evidence, manifests, signatures, policies, rollback information, and runtime-surface bindings.

### RuntimeSurfaceReleaseBinding
A governed binding between a release bundle and an allowed OFARM runtime surface.

### CanaryResult
A bounded canary outcome record. It is evidence, not promotion by itself.

### RollbackPlan
A governed rollback or disablement plan for a deployment candidate or release bundle.

### RuntimeDeploymentReceipt
A runtime receipt indicating deployment occurrence or status. It is not production readiness or conformance proof by itself.

### ModelDeploymentCandidate
A proposed model release candidate requiring model-evaluation evidence, use constraints, runtime-surface binding, authority, rollback, and CP11–CP14 gate checks where applicable.

### DeploymentOutputQualification
The visible or machine-readable qualification required for deployment-related outputs, claims, dashboards, public surfaces, and agent answers.
