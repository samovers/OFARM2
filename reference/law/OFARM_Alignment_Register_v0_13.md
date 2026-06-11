# OFARM Alignment Register v0.13

Date: 2026-04-11  
Status: post-charter cumulative patch artifact including wave-6 closure-alignment harmonization, AGR-P7 agronomic carrier harmonization, and ONT-SEMINT v0.3 semantic-integrity harmonisation  
Last harmonized: 2026-05-14 — ONT-SEMINT v0.3 semantic-integrity baseline harmonisation  
Scope: normative alignment inventory for OFARM 2.0 constitutional core concepts after RFC-1 identity/lifecycle, RFC-6 current-state materialization, RFC-2 query schema, RFC-3 pack merge, RFC-4 authority policy-model hardening, the wave-1 to wave-5 closure set, the agronomic carrier closure RFCs, and the ONT-SEMINT semantic-integrity/currentness closures

---

## 1. Purpose

This register makes the OFARM source-of-meaning method enforceable.

For each constitutional core concept, OFARM records:
- the canonical OFARM concept name
- the main OFARM layer
- the alignment class
- the primary external semantic anchor(s)
- the canonical naming choice
- the reason for the choice

This register is intentionally opinionated.
“Provisional” is reserved for genuinely unresolved cases and is not the default posture.

---

## 2. Alignment classes

### REUSE_EXTERNAL
OFARM adopts the external concept directly as the semantic source of truth for that concept family.

### PROFILE_EXTERNAL
OFARM uses the external concept as the base concept, but narrows, constrains, or specializes its usage.

### OFARM_ALIGNED
OFARM keeps an OFARM canonical concept name, but must publish a formal semantic alignment to one or more external anchors.

This class is allowed only when at least one of these is true:
- farmer/product language strongly favors a different canonical term
- OFARM needs to harmonize multiple external concepts under one stable operational term
- OFARM needs a tighter operational meaning than the external concept provides

### OFARM_OWNED
The concept is strategically and substantively OFARM-native.
External standards may still provide foundations or related anchors, but the concept itself is owned by OFARM.

---

## 3. Register

| OFARM canonical concept | Main layer | Alignment class | Primary external semantic anchor(s) | Canonical naming choice | Reason for choice |
|---|---|---|---|---|---|
| Geospatial feature / geometry | Layer 0 | REUSE_EXTERNAL | GeoSPARQL | External naming | OFARM should not reinvent spatial feature/geometry semantics. |
| Time instant / interval / duration | Layer 0 | REUSE_EXTERNAL | OWL-Time | External naming | Time ordering and interval semantics should come from a stable public standard. |
| Quantity / unit / quantity value | Layer 0 | REUSE_EXTERNAL | QUDT | External naming | Quantity kinds and units should not be OFARM-local. |
| Observation | Layer 0 / Layer 4 | PROFILE_EXTERNAL | SOSA/SSN via AIM | External base, OFARM-constrained use | OFARM needs farm-specific observation discipline without redefining the observation concept. |
| Provenance agent / activity / entity / collection | Layer 0 / Layer 3 | REUSE_EXTERNAL | PROV-O | External naming | Provenance is a cross-domain concern and should reuse public semantics. |
| Farm | Layer 1 | PROFILE_EXTERNAL | AIM / agriSystem | OFARM uses “Farm” | This is a shared agri concept already handled in AIM and aligned families. |
| Site | Layer 1 | PROFILE_EXTERNAL | AIM site/parcel context + W3C ORG Site | OFARM uses “Site” | OFARM should inherit shared place-grouping semantics rather than invent them. |
| Field | Layer 1 | OFARM_ALIGNED | AIM Plot / AgriParcel family | OFARM uses “Field” | “Field” remains an OFARM operational term, but its lifecycle must distinguish same-field boundary revisions from split/merge/reconstitution into new field identities. |
| ManagementZone | Layer 1 | PROFILE_EXTERNAL | AIM ManagementZone | OFARM uses “ManagementZone” | ManagementZone semantics stay anchored to shared agri meaning, but OFARM adds lifecycle rules distinguishing durable recurring zones from ephemeral overlays. |
| MicroclimateZone | Layer 1 / Layer 4 | OFARM_ALIGNED | GeoSPARQL + ENVO | OFARM uses “MicroclimateZone” | OFARM needs spatially and environmentally anchored microclimate zones with lifecycle rules for durable recurring zones versus one-off overlays. |
| Crop | Layer 1 | PROFILE_EXTERNAL | AIM agriCrop | OFARM uses “Crop” | Shared crop semantics should come from AIM’s agri layer. |
| Variety / cultivar | Layer 1 / Knowledge | PROFILE_EXTERNAL | Crop Ontology + AGROVOC bindings | OFARM uses “Variety” / “Cultivar” | Variety semantics should be vocabulary-led, not OFARM-invented. |
| PhenologyState | Layer 1 / Layer 4 | OFARM_ALIGNED | BBCH + Plant Ontology + AIM crop context | OFARM uses “PhenologyState” | OFARM needs a stateful crop-cycle concept, while stage codes themselves should bind to external phenology vocabularies. |
| Pest / target organism occurrence | Layer 1 / Layer 4 | PROFILE_EXTERNAL | AIM agriPest + EPPO code bindings | OFARM uses domain-specific terms where needed | Pest and target-organism semantics should stay anchored to agri/pest standards and controlled codes. |
| LocalConditionPattern | Layer 4 | OFARM_ALIGNED | ENVO + PECO | OFARM uses “LocalConditionPattern” | OFARM needs local agronomic pattern semantics that remain connected to environment and condition vocabularies. |
| Party | Layer 1 / Layer 3 | OFARM_ALIGNED | PROV Agent + W3C ORG foundations | OFARM uses “Party” | OFARM needs an accountable operational term while staying anchored to agent and organization semantics. |
| RoleType | Layer 1 / Knowledge | PROFILE_EXTERNAL | W3C ORG Role + SKOS | OFARM uses “RoleType” | Roles should be vocabulary-driven rather than plain free-text labels. |
| RoleAssignment | Layer 1 / Layer 3 | OFARM_OWNED | PROV qualified association/delegation + W3C ORG Membership | OFARM uses “RoleAssignment” | Farming accountability and scoped authority assignments are more specific than generic provenance or organization links. |
| IdentityRevision | Layer 1 / Governance | OFARM_OWNED | Versioning foundations only | OFARM uses “IdentityRevision” | OFARM needs versioned representations of durable identities that are distinct from new identity creation and distinct from time-bounded state. |
| LifecycleRelation | Layer 1 / Governance | OFARM_OWNED | Provenance/lineage foundations only | OFARM uses “LifecycleRelation” | OFARM needs explicit lineage semantics such as revises, splitFrom, mergedFrom, succeeds, overlapsWith, and replaces across identity-bearing objects. |
| AuthorityGrant | Layer 1 / Governance | OFARM_OWNED | None | OFARM uses “AuthorityGrant” | OFARM needs a first-class grant object linking role/party to authority families in scope and time. |
| AuthorityActionClass | Layer 1 / Governance | OFARM_OWNED | None | OFARM uses AuthorityActionClass enumerations | OFARM needs explicit action-level authorization semantics rather than relying only on broad role or family labels. |
| ScopeInheritanceMode | Layer 1 / Governance | OFARM_OWNED | None | OFARM uses ScopeInheritanceMode enumerations | OFARM needs explicit inheritance rules so broad-scope grants do not silently become over-broad authority. |
| AuthorizationDecisionTrace | Layer 1 / Governance | OFARM_OWNED | None | OFARM uses “AuthorizationDecisionTrace” | OFARM needs a traceable decision object explaining why a requested action was allowed, denied, review-required, or human-approval-required. |
| DelegationGrant | Layer 1 / Governance | OFARM_OWNED | PROV delegation foundations only | OFARM uses “DelegationGrant” | OFARM needs explicit, traceable delegated authority rather than implicit “acting for” assumptions. |
| SharingGrant | Layer 1 / Governance | OFARM_OWNED | ODRL-like sharing/permission ideas as inspiration only | OFARM uses “SharingGrant” | OFARM needs explicit visibility/use grants distinct from write/review/decision authority. |
| DataSovereigntyBoundary | Governance | OFARM_OWNED | None | OFARM uses “DataSovereigntyBoundary” | OFARM needs a first-class principle object for farm-scoped control and cross-farm boundary discipline. |
| RevocationDecision | Governance / Truth | OFARM_OWNED | Review/governance foundations only | OFARM uses “RevocationDecision” | OFARM needs explicit prospective narrowing or termination of authority/sharing without erasing truth history. |
| Equipment | Layer 1 / Layer 2 | OFARM_ALIGNED | AIM agriSystem + ETSI SAREF Device/System | OFARM uses “Equipment” | OFARM keeps equipment anchored to shared system/device semantics while adding durable-asset lifecycle rules for revision versus replacement. |
| AppliedResource | Layer 1 / Layer 2 | PROFILE_EXTERNAL | AIM agriProduct + AgrO + AGROVOC/EPPO bindings | OFARM uses “AppliedResource” | Inputs and operational resources recur across contexts and integrations and should be shared as much as possible. |
| Facility | Layer 1 / Layer 2 | OFARM_ALIGNED | GeoSPARQL Feature + W3C ORG Site + AIM system context | OFARM uses “Facility” | OFARM needs a governed operational-place concept with lifecycle rules for revision, restructuring, split, merge, and replacement. |
| StorageLocation | Layer 1 / Layer 2 | OFARM_ALIGNED | GeoSPARQL Feature + Facility context | OFARM uses “StorageLocation” | StorageLocation needs scoped operational meaning with identity semantics distinct from both facility identity and changing occupancy state. |
| Container | Layer 1 / Layer 2 | OFARM_OWNED | Spatial/system foundations only | OFARM uses “Container” | OFARM needs a clear distinction between a containment unit and the lot/material it contains, including reusable-container lifecycle across multiple occupancy episodes. |
| CropCycle | Layer 1 | OFARM_OWNED | AIM crop context + OWL-Time foundations | OFARM uses “CropCycle” | CropCycle is central to OFARM and now explicitly covers failed attempts, replants, child-cycle splits, and intentional overlaps such as relay/intercropping. |
| Lot | Layer 1 / Layer 3 | OFARM_OWNED | Product/traceability anchors where relevant | OFARM uses “Lot” | OFARM treats Lot as a cohort-first traceability identity with explicit split, merge, commingling, transformation, shipment-reference continuity, and claim-basis lineage semantics. |
| PartialExtent | Layer 1 / Layer 2 / Layer 3 | OFARM_ALIGNED | GeoSPARQL + OWL-Time + O&M sampling concepts + ADAPT/ISOXML/EFDI geometry surfaces as exchange influences | OFARM uses “PartialExtent” | OFARM needs an event-bound or identity-candidate spatial slice with explicit geometry basis, quality, evidence, and durable-identity posture without turning every slice into a zone. |
| Intervention | Layer 2 | PROFILE_EXTERNAL | AIM agriIntervention | OFARM uses “Intervention” | Shared intervention meaning should start from AIM. |
| PlannedIntervention | Layer 2 | OFARM_OWNED | AIM Intervention as anchor | OFARM uses “PlannedIntervention” | Planned-versus-executed logic is core OFARM territory. |
| ExecutedIntervention | Layer 2 | OFARM_OWNED | AIM Intervention as anchor | OFARM uses “ExecutedIntervention” | Execution truth, evidence linkage, and correction are core OFARM territory. |
| InterventionIntentPayload | Layer 2 | OFARM_OWNED | AIM intervention + ADAPT/ISOXML/EFDI exchange influences | OFARM uses “InterventionIntentPayload” | OFARM owns the separation between recommendation, prescription, planned operation, cancellation, and supersession payloads. |
| ExecutionRecordPayload | Layer 2 / Layer 3 | OFARM_OWNED | AIM intervention + ADAPT/ISOXML/EFDI/ISOBUS DDI exchange influences | OFARM uses “ExecutionRecordPayload” | OFARM owns the separation between operation claim, as-applied evidence, accepted execution detail, correction, and dispute payloads. |
| StructureEvent | Layer 2 / Truth | OFARM_OWNED | PROV Activity foundations only | OFARM uses “StructureEvent” | OFARM needs a stable top-level family for boundary, scope, assignment, and activation changes. |
| ObservationEvent | Layer 2 / Truth | OFARM_ALIGNED | SOSA/SSN + AIM observation context | OFARM uses “ObservationEvent” | OFARM keeps an event-family term while anchoring observation meaning to public observation semantics. |
| OccurrenceEvent | Layer 2 / Truth | OFARM_ALIGNED | ENVO/PECO + event foundations | OFARM uses “OccurrenceEvent” | OFARM needs a stable family for non-deliberate agronomic/environmental occurrences. |
| InterventionEvent | Layer 2 / Truth | PROFILE_EXTERNAL | AIM agriIntervention | OFARM uses “InterventionEvent” | OFARM should anchor deliberate action semantics to AIM intervention meaning. |
| MaterialEvent | Layer 2 / Truth | OFARM_OWNED | Traceability/material-flow foundations only | OFARM uses “MaterialEvent” | OFARM needs stable lot/resource custody and transformation event semantics. |
| EvidenceEvent | Layer 2 / Truth | OFARM_OWNED | PROV Activity + evidence foundations | OFARM uses “EvidenceEvent” | OFARM needs explicit evidentiary acts such as capture, attestation, and issue/receipt. |
| GovernanceEvent | Layer 2 / Truth | OFARM_OWNED | PROV Activity foundations only | OFARM uses “GovernanceEvent” | OFARM needs explicit review, decision, submission, and enforcement event semantics. |
| AcceptedEventConsequence | Truth | OFARM_OWNED | Event/state foundations only | OFARM uses “AcceptedEventConsequence” | OFARM needs a first-class bridge between history and governed current-state materialization. |
| OperationRecord | Layer 2 / Layer 3 | OFARM_OWNED | Intervention + truth-model foundations | OFARM uses “OperationRecord” | OFARM needs an explicit operational truth object, not just a generic activity. |
| EvidenceRecord | Layer 3 | OFARM_OWNED | PROV Entity | OFARM uses “EvidenceRecord” | OFARM needs governed evidentiary semantics, not only generic provenance entities. |
| MeasurementEvidence | Layer 3 / Layer 4 | OFARM_ALIGNED | SOSA/SSN + O&M + PROV-O + QUDT/UCUM | OFARM uses “MeasurementEvidence” | OFARM needs structured agronomic measurement, sampling, method, calibration, limit, uncertainty, quantity, unit, and evidence-status context while remaining anchored to public observation/provenance/quantity semantics. |
| EvidenceBundle | Layer 3 | OFARM_OWNED | PROV Collection | OFARM uses “EvidenceBundle” | Grouped evidence has operational/compliance meaning beyond simple provenance grouping. |
| AssertionRecord | Layer 3 / Truth | OFARM_OWNED | PROV Entity foundations only | OFARM uses “AssertionRecord” | OFARM needs immutable typed assertion objects with evidence, status, time, and review semantics. |
| ReviewDecision | Layer 3 / Truth | OFARM_OWNED | PROV Activity + qualified relations foundations | OFARM uses “ReviewDecision” | OFARM needs governed acceptance, rejection, contestation, and supersession acts as first-class truth objects. |
| CurrentStateMaterialization | Truth / Cross-layer | OFARM_OWNED | Query/materialization foundations only | OFARM uses “CurrentStateMaterialization” | OFARM needs a governed current-state derivation that is distinct from assertion/history authority. |
| ContextSnapshot | Truth / Governance | OFARM_OWNED | Context/materialization foundations only | OFARM uses “ContextSnapshot” | OFARM needs a governed resolved context-basis object so active pack/profile/policy/identity posture for a materialization is traceable rather than hidden in runtime state. |
| MaterializationBasis | Truth / Governance | OFARM_OWNED | Trace/materialization foundations only | OFARM uses “MaterializationBasis” | OFARM needs an explicit traceable basis object that explains which authoritative elements and resolved context produced a current-state answer. |
| MaterializationSnapshot | Truth / Governance | OFARM_OWNED | Snapshot/trace foundations only | OFARM uses “MaterializationSnapshot” | OFARM needs a durable recorded generation of current-state materialization when later explanation or attestation matters. |
| MaterializationFreshnessState | Truth / Governance | OFARM_OWNED | None | OFARM uses freshness states such as FRESH/STALE/INVALID | OFARM needs governed freshness semantics so current-state can be trusted, recomputed, or refused appropriately. |
| OperationClaim | Truth / Commit | OFARM_OWNED | ExecutedIntervention + assertion foundations | OFARM uses “OperationClaim” | OFARM separates claimed execution from accepted executed consequence. |
| ComplianceAssertion | Truth / Commit | OFARM_OWNED | Compliance/evidence foundations only | OFARM uses “ComplianceAssertion” | OFARM separates compliance claims from governed compliance facts. |
| StructureAssertion | Truth / Commit | OFARM_OWNED | Structural/state foundations only | OFARM uses “StructureAssertion” | OFARM needs explicit structural/configuration claims entering truth law. |
| TraceabilityLineage | Layer 3 | OFARM_OWNED | PROV derivation foundations | OFARM uses “TraceabilityLineage” | OFARM needs explicit material and evidentiary lineage across interventions and lots. |
| ComplianceFact | Layer 3 | OFARM_OWNED | Related provenance/evidence foundations only | OFARM uses “ComplianceFact” | This is a governed concept with legal/certification consequences and is not adequately supplied by generic ontologies. |
| ComplianceSubmission | Layer 3 | OFARM_OWNED | Document/evidence foundations only | OFARM uses “ComplianceSubmission” | Submission semantics are OFARM-owned. |
| InspectionCase | Layer 3 | OFARM_OWNED | Document/evidence foundations only | OFARM uses “InspectionCase” | Inspection workflow semantics are OFARM-owned. |
| NonConformity | Layer 3 | OFARM_OWNED | Domain-specific only | OFARM uses “NonConformity” | Nonconformity semantics are operational/compliance territory. |
| CorrectiveAction | Layer 3 | OFARM_OWNED | Domain-specific only | OFARM uses “CorrectiveAction” | Corrective action semantics are operational/compliance territory. |
| NarrativeObservation | Layer 4 | OFARM_OWNED | Observation + evidence foundations | OFARM uses “NarrativeObservation” | OFARM must preserve rich human observations without flattening them into measurements. |
| AgronomicObservationContext | Layer 4 / Layer 3 | OFARM_ALIGNED | SOSA/SSN + O&M + OWL-Time + GeoSPARQL | OFARM uses “AgronomicObservationContext” | OFARM needs structured crop, phenomenon, method, threshold, spatial, temporal, evidence, and promotion-use context around observations without replacing NarrativeObservation. |
| Heuristic / LocalMemoryRule | Layer 4 | OFARM_OWNED | Provenance foundations only | OFARM uses operational names | OFARM intentionally owns farmer-knowledge and local-memory semantics. |
| Hypothesis | Layer 4 | OFARM_OWNED | Observation/provenance foundations only | OFARM uses “Hypothesis” | Hypothesis semantics are central to OFARM’s uncertainty discipline. |
| ConfidenceAssessment / ReviewState | Layer 4 | OFARM_OWNED | Provenance/review foundations only | OFARM uses operational names | OFARM needs explicit epistemic status and review semantics. |
| Pack | Layer 5 | OFARM_OWNED | None | OFARM uses “Pack” | Packs are OFARM’s modular context mechanism. |
| Profile | Layer 5 | OFARM_OWNED | None | OFARM uses “Profile” | Profiles are OFARM’s constraint-activation mechanism. |
| ScopedExtension | Layer 5 | OFARM_OWNED | None | OFARM uses “ScopedExtension” | This is governance law, not borrowed domain meaning. |
| LocalArtifact | Layer 5 | OFARM_OWNED | None | OFARM uses “LocalArtifact” | This is governance law, not borrowed domain meaning. |
| AgronomicIdentityBinding | Knowledge / Layer 5 | OFARM_OWNED | SKOS mapping discipline + EPPO/BBCH/AGROVOC/Crop Ontology/UPOV/CPVO/GS1/QUDT/UCUM as profile-declared schemes | OFARM uses “AgronomicIdentityBinding” | OFARM needs scheme-bound identity binding that prevents free-text labels, registry lookups, and pack-local terms from becoming hidden truth. |
| AgronomicCodeBindingProfile | Layer 5 / Governance | OFARM_OWNED | SKOS concept-scheme/profile discipline plus profile-declared external schemes | OFARM uses “AgronomicCodeBindingProfile” | OFARM needs profile-governed scheme roles, evidence floors, unresolved-binding behavior, and pack-merge posture without importing external code systems as OFARM law. |
| PackActivationSet | Layer 5 / Governance | OFARM_OWNED | None | OFARM uses “PackActivationSet” | OFARM needs an explicit concept for evaluating pack compatibility in a concrete scope/time context and grounding later ContextSnapshot derivation. |
| PackCompatibilityDeclaration | Layer 5 / Governance | OFARM_OWNED | None | OFARM uses “PackCompatibilityDeclaration” | OFARM needs explicit governed declarations of compatibility, merge behavior, or exclusion. |
| PackMergePolicy | Layer 5 / Governance | OFARM_OWNED | None | OFARM uses “PackMergePolicy” | OFARM needs a first-class rule object for safe same-surface merge behavior. |
| PackSurfaceFamily | Layer 5 / Governance | OFARM_OWNED | None | OFARM uses PackSurfaceFamily enumerations | OFARM needs explicit surface-family classification so merge legality is defined per artifact surface instead of by vague overlap. |
| PackSurfaceMergeMode | Layer 5 / Governance | OFARM_OWNED | None | OFARM uses PackSurfaceMergeMode enumerations | OFARM needs explicit merge-mode semantics such as ADDITIVE_UNION, CONSTRAINT_INTERSECTION, STRONGEST_REQUIREMENT, ORDERED_COMPOSITION, IDENTICAL_ONLY, and HARD_FAIL. |
| PackMergeResolutionTrace | Layer 5 / Governance | OFARM_OWNED | None | OFARM uses “PackMergeResolutionTrace” | OFARM needs a traceable record of which surface family and merge mode produced a merge or hard fail result. |
| PackExclusionRule | Layer 5 / Governance | OFARM_OWNED | None | OFARM uses “PackExclusionRule” | OFARM needs a first-class way to say packs may not co-activate in a given scope/time. |
| Archetype | Layer 6 | OFARM_OWNED | openEHR-inspired pattern only | OFARM uses “Archetype” | OFARM keeps the archetype method as part of its artifact constitution. |
| Template | Layer 6 | OFARM_OWNED | openEHR-inspired pattern only | OFARM uses “Template” | OFARM keeps template composition as part of its artifact constitution. |
| InteractionModule | Layer 6 | OFARM_OWNED | None | OFARM uses “InteractionModule” | OFARM standardizes the artifact type even though runtime realization belongs to Platform. |
| ViewModule | Presentation | OFARM_OWNED | Query/presentation foundations only | OFARM uses “ViewModule” | OFARM needs governed compiled retrieval/assembly semantics. |
| DocumentAssembly | Presentation | OFARM_OWNED | Document/provenance foundations only | OFARM uses “DocumentAssembly” | This is a strategic OFARM concept for governed compiled outputs. |
| PassportView | Presentation | OFARM_OWNED | Query/presentation foundations only | OFARM uses “PassportView” | OFARM needs a first-class portable scope-summary concept distinct from frozen documents. |
| ReportAssembly | Presentation | OFARM_OWNED | DocumentAssembly family | OFARM uses “ReportAssembly” | OFARM needs an explicit frozen report subtype instead of collapsing reports into generic passport language. |
| DossierAssembly | Presentation | OFARM_OWNED | DocumentAssembly family | OFARM uses “DossierAssembly” | OFARM needs an explicit evidence-rich case package subtype. |
| SubmissionAssembly | Presentation | OFARM_OWNED | DocumentAssembly family | OFARM uses “SubmissionAssembly” | OFARM needs an explicit formal filing/submission package subtype. |
| QuerySpecification | Query / Governance | OFARM_OWNED | SPARQL graph-pattern and AQL path-addressing ideas as influences only | OFARM uses “QuerySpecification” | OFARM needs a governed canonical query artifact with a machine-validatable schema without freezing a public syntax too early. |
| AgronomicReconstructionPolicy | Query / Presentation / Governance | OFARM_OWNED | Query/materialization/provenance foundations only | OFARM uses “AgronomicReconstructionPolicy” | OFARM needs explicit effective-as-of, knowledge-cut, promotion, evidence, freshness, geometry, dispute, code-profile, and disclosure controls for high-consequence agronomic reconstruction. |
| AgronomicReconstructionTrace | Query / Traceability / Presentation | OFARM_OWNED | PROV-O and query trace foundations only | OFARM uses “AgronomicReconstructionTrace” | OFARM needs a traceable explanation of agronomic reconstruction decisions without treating query results or projections as truth. |
| SemanticPathAlias | Query / Content | OFARM_ALIGNED | openEHR AQL identified-path idea as inspiration only | OFARM uses “SemanticPathAlias” | OFARM needs governed path-based shorthand for archetype/template-bound content with versioned alias-resolution discipline, governed alias catalogs, and explicit resolution traces without creating a hidden alternate schema. |

---

## 4. Interpretation notes

### 4.1 Canonical OFARM naming is allowed
This register does not require OFARM to expose raw external names to users or builders.

It does require:
- semantic anchor clarity
- explicit formal alignment when OFARM keeps its own canonical term
- no drift into a disconnected private ontology world

### 4.2 Strong OFARM ownership is intentional in operations and compliance
OFARM is deliberately strongest in:
- planned versus executed intervention semantics
- evidence sufficiency
- assertion/history-first truth and governed current-state materialization
- materialization basis, snapshot, and freshness semantics
- top-level event grammar and accepted event consequences
- append-only correction/supersession
- lot and traceability governance
- compliance/inspection/nonconformity/corrective-action semantics
- soft data, heuristics, uncertainty, and review

### 4.3 Operational-domain consequence
This register now treats the following as first-class constitutional domain families:
- accountable parties and role assignments
- equipment and tools
- applied resources and inputs
- facilities, storage locations, and containers

These are not optional product-side conveniences.
They are part of the constitutional crop-farming model.

### 4.3a Identity and lifecycle consequence
This register now also treats the following as first-class constitutional identity/governance concepts:
- IdentityRevision
- LifecycleRelation

The covered domain families must now support explicit same-identity revision, new-identity creation, and lineage semantics rather than hiding those decisions inside implementation conventions.

### 4.4 Truth-mechanics consequence
This register now also treats the following as first-class constitutional truth concepts:
- AssertionRecord
- ReviewDecision
- CurrentStateMaterialization
- ContextSnapshot
- MaterializationBasis
- MaterializationSnapshot
- MaterializationFreshnessState
- top-level event families
- accepted event consequences
- refined commit-class concepts such as OperationClaim, ComplianceAssertion, and StructureAssertion

These are not runtime-only convenience objects.
They are part of OFARM truth law.

### 4.5 Pack-governance consequence
This register now also treats the following as first-class constitutional governance concepts:
- PackActivationSet
- PackCompatibilityDeclaration
- PackMergePolicy
- PackSurfaceFamily
- PackSurfaceMergeMode
- PackMergeResolutionTrace
- PackExclusionRule

These are necessary so pack compatibility and merge behavior are traceable and reproducible rather than hidden in runtime guesswork.

### 4.6 Authority-governance consequence
This register now also treats the following as first-class constitutional governance concepts:
- AuthorityGrant
- AuthorityActionClass
- ScopeInheritanceMode
- AuthorizationDecisionTrace
- DelegationGrant
- SharingGrant
- DataSovereigntyBoundary
- RevocationDecision

These are necessary so authority, access, action policy, and revocation remain explicit, scoped, and traceable rather than hidden in product behavior.

### 4.7 Query consequence
This register now also treats the following as first-class constitutional query concepts:
- QuerySpecification
- SemanticPathAlias

These are necessary so OFARM query behavior is formal, machine-validatable, and governable rather than hidden inside one runtime or one prompt pattern.

### 4.8 Compiled-output consequence
This register now also treats the following as first-class constitutional presentation concepts:
- PassportView
- ReportAssembly
- DossierAssembly
- SubmissionAssembly

These are necessary so OFARM output naming remains semantically clean and “passport” does not become a catch-all term.


### 4.9 Agronomic carrier-shell consequence
This register now treats the following as first-class constitutional agronomic carrier-shell concepts:
- AgronomicObservationContext
- MeasurementEvidence
- InterventionIntentPayload
- ExecutionRecordPayload
- PartialExtent
- AgronomicIdentityBinding
- AgronomicCodeBindingProfile
- AgronomicReconstructionPolicy
- AgronomicReconstructionTrace

These concepts are constitutional because they prevent common agronomic failure modes: fake precision, free-text identity leakage, stage collapse between intent and execution, partial-area whole-field overreach, stale or disputed output, and projection-as-truth. They do not create a second truth model and do not import external standards as hidden OFARM law.

---

## 4.10 ONT-SEMINT semantic-integrity alignment addendum — 2026-05-14

The following concepts are added to the active alignment posture as OFARM-owned or OFARM-governed semantic-integrity surfaces. They make reference resolution, temporal conformance, external currentness verification, and high-consequence output disposition executable while preserving OFARM's assertion/history-first truth model.

| OFARM canonical concept | Main layer | Alignment class | Primary external semantic anchor(s) | Canonical naming choice | Reason for choice |
|---|---|---|---|---|---|
| ReferenceResolutionManifest | Governance / Traceability / Runtime | OFARM_OWNED | None | OFARM uses “ReferenceResolutionManifest” | OFARM needs a governed policy surface for package-local and external reference-resolution expectations; generic JSON reference validation is insufficient for audit-grade output. |
| ReferenceResolutionFinding | Governance / Traceability / Runtime | OFARM_OWNED | None | OFARM uses “ReferenceResolutionFinding” | OFARM needs a traceable per-reference result for resolved, unresolved, stale, aliased, externally declared, externally verified, review-required, or fail-closed references. |
| ReferenceResolutionReport | Governance / Traceability / Runtime | OFARM_OWNED | None | OFARM uses “ReferenceResolutionReport” | OFARM needs a report-level object that distinguishes schema validation from semantic conformance and high-consequence output eligibility. |
| TemporalFieldConformanceMatrix | Governance / Temporal / Conformance | OFARM_OWNED | OWL-Time as temporal foundation only | OFARM uses “TemporalFieldConformanceMatrix” | OFARM needs an implementation-facing matrix that prevents observation, occurrence, assertion, capture, sync, review, correction, materialization, and output time from collapsing into one generic timestamp. |
| ExternalRegistryVerificationTrace | Governance / Traceability / Interoperability | OFARM_OWNED | External registries as profile-declared runtime surfaces only | OFARM uses “ExternalRegistryVerificationTrace” | OFARM needs a traceable carrier for registry lookup inputs, source surfaces, snapshots, status/dates, discrepancies, availability, and output disposition without importing the external registry as hidden OFARM law. |

### 4.11 ONT-SEMINT external-currentness consequence

External standards and registries remain anchors, code bindings, runtime surfaces, exchange mappings, or attestation wrappers. They do not become hidden OFARM law. For the Belgium crop-protection currentness profile, Belgian jurisdictional product authorisation is the mandatory runtime/checking surface for high-consequence Belgian product-authorisation identity; EU active-substance context, trade name, GS1/GTIN identity, EPPO/BBCH vocabulary, UCUM/QUDT unit or quantity anchoring, and other adjunct sources remain supporting context unless the active profile explicitly assigns them a stronger role.

### 4.12 ONT-SEMINT query/output consequence

High-consequence query and output semantics must preserve version-pinned alias resolution, reconstruction policy and trace, reference-resolution results, external-currentness verification where required, materialization freshness, evidence sufficiency, authority decision, dispute/correction posture, and PassportView versus DocumentAssembly separation.

---

## 5. ONT-SEMINT v0.3 alignment supplement — 2026-05-14

This supplement adds the semantic-integrity carriers harmonised into baseline law. It does not demote or replace the register above.

| OFARM canonical concept | Main layer | Alignment class | Primary external semantic anchor(s) | Canonical naming choice | Reason for choice |
|---|---|---|---|---|---|
| ReferenceResolutionManifest | Governance / Traceability / Conformance | OFARM_OWNED | None | OFARM uses “ReferenceResolutionManifest” | OFARM needs package-local and high-consequence reference-resolution policy to be explicit rather than hidden in validators or runtime code. |
| ReferenceResolutionFinding | Governance / Traceability / Conformance | OFARM_OWNED | None | OFARM uses “ReferenceResolutionFinding” | OFARM needs typed resolution outcomes such as resolved, unresolved, type-mismatched, stale, externally declared, externally verified, review-required, or fail-closed. |
| ReferenceResolutionReport | Governance / Traceability / Conformance | OFARM_OWNED | None | OFARM uses “ReferenceResolutionReport” | OFARM needs an auditable report proving whether required references supported a materialization, PassportView, DocumentAssembly, or publication/export path. |
| TemporalFieldConformanceMatrix | Governance / Traceability / Conformance | OFARM_OWNED | OWL-Time as temporal substrate | OFARM uses “TemporalFieldConformanceMatrix” | OFARM needs an implementation-facing carrier that prevents collapse of observation, event, assertion, review, correction, materialization, and output time semantics. |
| ExternalRegistryVerificationTrace | Governance / Traceability / Interoperability | OFARM_OWNED | PROV-O foundations plus profile-declared registry/standard anchors | OFARM uses “ExternalRegistryVerificationTrace” | OFARM needs to record external lookup inputs, authority, jurisdiction, candidate count, selected identifier, status/date context, snapshot evidence, discrepancies, availability, and output disposition without treating external registries as hidden OFARM law. |

### 5.1 Currentness and external-code-binding consequence

The register now treats reference resolution, temporal field conformance, alias-resolution discipline, and external registry verification traces as first-class governance/conformance concepts for high-consequence use.

External schemes such as Phytoweb, EU Pesticides Database, EPPO, BBCH, UCUM, QUDT, GS1, CPVO, UPOV, OECD Seed Schemes, AGROVOC, and Crop Ontology may be used only under declared roles such as runtime surface, code binding, semantic anchor, exchange mapping, evidence source, or attestation wrapper. Those roles do not make the external source OFARM canonical truth.

---

## 6. Agentic AI baseline-safety alignment addendum — 2026-05-14

This addendum records the alignment consequence of the Phase AAI-P1 baseline safety clarification. It does not promote the draft agentic AI/world-model machine contracts into active law and does not create a new truth model.

### 6.1 Active alignment consequence

The register now treats the following as active alignment constraints:

- AI-generated status is provenance and authority context, not a separate truth category;
- software-agent participation requires explicit authority and cannot be inferred from model, tool, prompt, API, or session identity;
- public surfaces and tool calls are runtime affordances, not semantic law;
- world-model and scenario state remain Advisory unless bridged and accepted through ordinary OFARM governance;
- handoff context must not be treated as transferred authority;
- result qualifications must remain visible in AI-facing answers and compiled output preparation.

- AI-facing, public-operation, state-affecting, and high-consequence release surfaces are release-eligible only when material limitations can be expressed as machine-readable qualification and faithfully surfaced to users or downstream systems;

### 6.2 Active and candidate reserved OFARM-owned surfaces

The following OFARM-owned governance/runtime surfaces were originally reserved as candidates. CP2 and CP3 promote only the subsets named below. All other names remain reserved candidates until separately promoted.

#### 6.2.1 Active CP2 public-surface and qualification subset

| Active surface | Active layer | Promotion status | Governing path |
|---|---|---|---|
| PublicOperationDescriptor | Runtime / Public Surface | ACTIVE_BY_AAI_CP2 | `02_accepted_rfcs/OFARM_Application_Builder_Surface_RFC_v0_1.md` |
| PreflightRequest | Runtime / Preflight | ACTIVE_BY_AAI_CP2 | `02_accepted_rfcs/OFARM_Preflight_DryRun_and_Explain_Surface_RFC_v0_1.md` |
| PreflightResult | Runtime / Preflight | ACTIVE_BY_AAI_CP2 | `02_accepted_rfcs/OFARM_Preflight_DryRun_and_Explain_Surface_RFC_v0_1.md` |
| RuntimeProblemReasonCodeRegistry | Runtime / Reason Codes | ACTIVE_BY_AAI_CP2 | `02_accepted_rfcs/OFARM_RuntimeProblem_Reason_Code_Registry_RFC_v0_1.md` |
| ResultQualificationEnvelope | Runtime / Qualification | ACTIVE_BY_AAI_CP2 | `02_accepted_rfcs/OFARM_AI_Facing_Result_Qualification_and_Trace_Surface_RFC_v0_1.md` |
| TraceRetrievalResult | Runtime / Trace Retrieval | ACTIVE_BY_AAI_CP2 | `02_accepted_rfcs/OFARM_AI_Facing_Result_Qualification_and_Trace_Surface_RFC_v0_1.md` |
| PublicReadModelEnvelope | Runtime / Read Model | ACTIVE_BY_AAI_CP2 | `02_accepted_rfcs/OFARM_AI_Facing_Result_Qualification_and_Trace_Surface_RFC_v0_1.md` |
| SourceFidelityEnvelope | Runtime / Source Fidelity | ACTIVE_BY_AAI_CP2 | `02_accepted_rfcs/OFARM_AI_Facing_Result_Qualification_and_Trace_Surface_RFC_v0_1.md` |

#### 6.2.2 Active CP3 sponsor-bound software-agent actorship subset

| Active surface | Active layer | Promotion status | Governing path |
|---|---|---|---|
| SoftwareAgentProfile | Authority / Provenance | ACTIVE_BY_AAI_CP3 | `02_accepted_rfcs/OFARM_Agent_Actorship_and_Authority_RFC_v0_1.md` |
| AgentInstance | Runtime / Provenance | ACTIVE_BY_AAI_CP3 | `02_accepted_rfcs/OFARM_Agent_Actorship_and_Authority_RFC_v0_1.md` |
| AgentSponsorRef | Authority / Accountability | ACTIVE_BY_AAI_CP3 | `02_accepted_rfcs/OFARM_Agent_Actorship_and_Authority_RFC_v0_1.md` |
| AgentModelToolProfile | Authority / Runtime Basis | ACTIVE_BY_AAI_CP3 | `02_accepted_rfcs/OFARM_Agent_Actorship_and_Authority_RFC_v0_1.md` |
| AgentAuthorityEnvelope | Authority / Delegation | ACTIVE_BY_AAI_CP3 | `02_accepted_rfcs/OFARM_Agent_Actorship_and_Authority_RFC_v0_1.md` |
| AgentRevocationState | Authority / Revocation | ACTIVE_BY_AAI_CP3 | `02_accepted_rfcs/OFARM_Agent_Actorship_and_Authority_RFC_v0_1.md` |
| AgentActorshipBinding | Authority / Accountability | ACTIVE_BY_AAI_CP3 | `02_accepted_rfcs/OFARM_Agent_Actorship_and_Authority_RFC_v0_1.md` |
| AgentAuthorizationDecisionTrace | Authority / Traceability | ACTIVE_BY_AAI_CP3 | `02_accepted_rfcs/OFARM_Agent_Actorship_and_Authority_RFC_v0_1.md` |


#### 6.2.3 Active CP4 agent run, trace, and handoff subset

| Active surface | Active layer | Promotion status | Governing path |
|---|---|---|---|
| AgentToolInvocationTrace | Runtime / Traceability | ACTIVE_BY_AAI_CP4 | `02_accepted_rfcs/OFARM_Agent_Run_Envelope_Trace_and_Handoff_RFC_v0_1.md` |
| AgentOutputDisposition | Runtime / Output Disposition | ACTIVE_BY_AAI_CP4 | `02_accepted_rfcs/OFARM_Agent_Run_Envelope_Trace_and_Handoff_RFC_v0_1.md` |
| AgentBlockedActionTrace | Runtime / Enforcement Trace | ACTIVE_BY_AAI_CP4 | `02_accepted_rfcs/OFARM_Agent_Run_Envelope_Trace_and_Handoff_RFC_v0_1.md` |
| AgentRunInputBundle | Runtime / Input Basis | ACTIVE_BY_AAI_CP4 | `02_accepted_rfcs/OFARM_Agent_Run_Envelope_Trace_and_Handoff_RFC_v0_1.md` |
| AgentRunStopCondition | Runtime / Enforcement | ACTIVE_BY_AAI_CP4 | `02_accepted_rfcs/OFARM_Agent_Run_Envelope_Trace_and_Handoff_RFC_v0_1.md` |
| AgentRunApprovalCheckpoint | Runtime / Approval | ACTIVE_BY_AAI_CP4 | `02_accepted_rfcs/OFARM_Agent_Run_Envelope_Trace_and_Handoff_RFC_v0_1.md` |
| AgentRunFreshnessRequirement | Runtime / Freshness | ACTIVE_BY_AAI_CP4 | `02_accepted_rfcs/OFARM_Agent_Run_Envelope_Trace_and_Handoff_RFC_v0_1.md` |

#### 6.2.4 Still-reserved candidate surfaces

The following names remain reserved as candidate OFARM-owned governance/runtime surfaces for later controlled RFC promotion. Their appearance here is a reservation and alignment note, not active machine-contract promotion:

| Candidate surface | Candidate layer | Candidate alignment class | Current status | Rationale |
|---|---|---|---|---|
| AgentToolManifest | Runtime / Capability | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| AgentToolDescriptor | Runtime / Capability | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| AgentSupportSection | Runtime / Capability | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| AgenticCapabilityManifestOverlay | Runtime / Capability | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| AgentToolEffectClassification | Runtime / Capability | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| AgentToolApprovalRequirement | Runtime / Approval | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| AgentToolSemanticPrecondition | Runtime / Enforcement | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| AgentExternalCallPolicy | Runtime / Sharing | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| AgentTraceRetentionPolicy | Runtime / Traceability | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| RedactionAndPermissionLimitedResultPolicy | Runtime / Sharing | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| AgentToolDeclaredHintSet | Runtime / Capability | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| AgentDataLearningPolicy | Runtime / Data | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| AgentCapabilityReadinessClaimLimit | Runtime / Claims | ACTIVE_BY_AAI_CP5 | `02_accepted_rfcs/OFARM_Capability_Manifest_Agentic_Extension_RFC_v0_1.md` |
| WorldModelRun | Advisory Runtime | OFARM_OWNED_CANDIDATE | reserved only | Needed to represent a bounded advisory model run with inputs, assumptions, uncertainty, and outputs. |
| WorldModelState | Advisory Runtime | OFARM_OWNED_CANDIDATE | reserved only | Needed to represent advisory state without treating it as current state or canonical truth. |
| ScenarioSpec | Advisory Runtime | OFARM_OWNED_CANDIDATE | reserved only | Needed to specify scenario objectives, assumptions, scope, and basis. |
| ScenarioResultSet | Advisory Runtime | OFARM_OWNED_CANDIDATE | reserved only | Needed to carry scenario outputs with uncertainty, freshness, and advisory disposition. |
| EvidenceNeed | Evidence / Review | OFARM_OWNED_CANDIDATE | reserved only | Needed to request missing evidence with consequence, severity, and promotion path. |
| ObservationRequest | Observation / Advisory / Evidence | OFARM_OWNED_CANDIDATE | reserved only | Needed to request the cheapest useful observation without silently creating facts. |

### 6.3 Non-alignment consequences

The register explicitly rejects alignment patterns that would make AI-agent frameworks, world-model state stores, generic tool manifests, prompt traces, or third-party API catalogs into OFARM canonical truth or authority sources by themselves.

## AAI-CP3 alignment update — sponsor-bound software-agent actorship

Status: active baseline/RFC/machine-contract alignment note.

AAI-CP3 adds the first active software-agent actorship subset. It aligns with the existing Authority Policy Model and Authority Action Matrix by requiring every state-affecting or high-consequence software-agent action to resolve an explicit sponsor, executing agent instance, actorship basis, AuthorityActionClass, target scope, twin context, authority snapshot, revocation posture, authorization decision, and result-qualification linkage.

AAI-CP3 does not create autonomous agent authority. It does not promote agent run/handoff, tool manifest, world-model, EvidenceNeed, ObservationRequest, two-agent compatibility, production readiness, autonomous compliance decisioning, live-registry integration, legal advice, or external-standard readiness.


## AAI-CP4 alignment update — agent run trace and handoff

Status: active baseline/RFC/machine-contract alignment note.

AAI-CP4 adds active run, trace, blocked-action trace, output-disposition, and handoff surfaces. It aligns with CP2 and CP3 by requiring state-affecting, high-consequence, or multi-step software-agent activity to carry a bounded run envelope, retrievable run trace, explicit tool-invocation trace, output disposition, blocked-action trace where applicable, freshness and approval checkpoints, and handoff reauthorization.

AAI-CP4 does not create runtime AI-agent readiness or two-agent compatibility. It does not promote AgentToolManifest, world-model runtime, EvidenceNeed, ObservationRequest, production readiness, autonomous compliance decisioning, live-registry integration, legal advice, or external-standard readiness.

## AAI-CP5 alignment update — capability/tool manifest honesty

AAI-CP5 promotes a bounded active capability/tool manifest-honesty subset. It aligns CP2 public surfaces, CP3 sponsor-bound actorship, and CP4 run/trace/handoff by requiring manifest and tool self-description to remain descriptive, evidence-qualified, trace-linked, and subordinate to runtime enforcement.

The promoted subset includes `AgentToolManifest`, `AgentToolDescriptor`, `AgentSupportSection`, `AgenticCapabilityManifestOverlay`, `AgentToolEffectClassification`, `AgentToolApprovalRequirement`, `AgentToolSemanticPrecondition`, `AgentExternalCallPolicy`, `AgentTraceRetentionPolicy`, `RedactionAndPermissionLimitedResultPolicy`, `AgentToolDeclaredHintSet`, `AgentDataLearningPolicy`, and `AgentCapabilityReadinessClaimLimit`.

AAI-CP5 does not create authority by manifest, trust by tool annotation, safety by vendor claim, runtime readiness by static validation, or governance success by tool-call success. It does not promote world-model runtime, EvidenceNeed, ObservationRequest, output assembly preview, two-agent compatibility, autonomous compliance decisioning, production readiness, live-registry integration, legal advice, or external-standard readiness.

## AAI-CP7 alignment register addendum — 2026-05-16

Alignment item: bounded advisory world-model contract promotion.

Decision: CP7 aligns with the active truth/current-state/twin boundaries by requiring `WorldModelRun`, `WorldModelState`, `ScenarioSpec`, and `ScenarioResultSet` to remain Advisory Twin material, uncertainty-qualified, validity-windowed, invalidation-aware, output-dispositioned, and result-qualified.

Residual debt: calibration-evidence specialization, farmer-facing world-model comprehension evidence, post-deployment monitoring thresholds, EvidenceNeed/ObservationRequest promotion, and production runtime evidence remain outside CP7.

## AAI-CP8 alignment register addendum — 2026-05-16

Alignment item: bounded EvidenceNeed and ObservationRequest request-layer promotion.

Decision: CP8 aligns with the active truth/evidence/promotion boundaries by requiring EvidenceNeed and ObservationRequest artifacts to remain request-layer records, not evidence, not obligations, and not blockers by themselves. Blocking force must come from an external rule or gate recorded through RequestBlockingBasis.

Residual debt: farmer-facing comprehension evidence, request-fatigue thresholds, live revocation handling, pilot UX evidence, minimum-capture-profile review, formula/default calculation review, and production runtime evidence remain outside CP8.


## CP11 Sustainable Autonomous Farming Charter alignment addendum — 2026-05-21

Status: alignment-register candidate for CP11 once `OFARM_Sustainable_Autonomous_Farming_Charter_RFC_v0_1.md` is accepted.

CP11 introduces the following baseline-recognised charter-governance concepts. These concepts are not introduced by one pack, app, adapter, AI behaviour, dashboard, output template, or external sustainability standard.

| OFARM canonical concept | Main layer | Alignment class | Primary external semantic anchor(s) | Canonical naming choice | Reason for choice |
|---|---|---|---|---|---|
| SustainableFarmingCharter | Governance / Sustainability | OFARM_OWNED | Policy/governance foundations only | OFARM uses `SustainableFarmingCharter` | OFARM needs an executable charter object governing constraints, objectives, evidence, claims, exceptions, and breaches. |
| CharterApplicabilityContext | Governance / Context | OFARM_OWNED | Context/provenance foundations only | OFARM uses `CharterApplicabilityContext` | OFARM needs an explicit context object resolving which charter version and rules apply to a scope/time/twin/output/action. |
| CharterRuleClass | Governance | OFARM_OWNED | None | OFARM uses `CharterRuleClass` | OFARM needs its own rule-class taxonomy so charter prose becomes executable governance. |
| SustainabilityConstraint | Governance / Sustainability | OFARM_OWNED | Environmental policy and constraint foundations only | OFARM uses `SustainabilityConstraint` | OFARM needs non-tradeable or rule-bound sustainability constraints that cannot be optimised away. |
| SustainabilityObjective | Governance / Advisory / Sustainability | OFARM_OWNED | Multi-objective optimisation foundations only | OFARM uses `SustainabilityObjective` | OFARM needs objectives that guide recommendation and simulation without creating authority or truth. |
| ObjectivePriority | Governance | OFARM_OWNED | Priority/decision-policy foundations only | OFARM uses `ObjectivePriority` | OFARM needs explicit hierarchy so objectives are not flattened into arbitrary scoring. |
| TradeoffPolicy | Governance | OFARM_OWNED | Decision-policy foundations only | OFARM uses `TradeoffPolicy` | OFARM needs governed treatment of allowed, review-required, prohibited, emergency-only, and insufficient-basis trade-offs. |
| SustainabilityEvidenceRequirement | Evidence / Governance | OFARM_OWNED | PROV-O, SOSA/SSN, evidence-policy foundations | OFARM uses `SustainabilityEvidenceRequirement` | OFARM needs consequence-sensitive evidence requirements for sustainability decisions, exceptions, breaches, and claims. |
| SustainabilityMetricProfile | Evidence / Sustainability | OFARM_ALIGNED | QUDT, SOSA/SSN, PROV-O, ENVO/PECO where applicable, profile-declared external methods | OFARM uses `SustainabilityMetricProfile` | OFARM needs method, unit, uncertainty, measured/modelled/inferred posture, and claim eligibility around sustainability metrics without inventing all metric science. |
| SustainabilityClaimBasis | Output / Evidence / Governance | OFARM_OWNED | Provenance and claim-basis foundations only | OFARM uses `SustainabilityClaimBasis` | OFARM needs explicit basis for sustainability claims distinct from traceability claim basis and generic output evidence. |
| SustainabilityOutputQualification | Output / Governance | OFARM_OWNED | Result qualification foundations only | OFARM uses `SustainabilityOutputQualification` | OFARM needs material limitations for sustainability-sensitive and claim-bearing outputs. |
| SustainabilityPolicyEvaluationTrace | Traceability / Governance | OFARM_OWNED | PROV-O trace foundations only | OFARM uses `SustainabilityPolicyEvaluationTrace` | OFARM needs a traceable record of charter constraints, objectives, trade-offs, evidence, gates, and outcomes. |
| CharterApprovalGate | Authority / Governance | OFARM_OWNED | Authority/action-class foundations only | OFARM uses `CharterApprovalGate` | OFARM needs explicit approval gates for exceptions, objective changes, claim approval, and charter-sensitive actions. |
| CharterException | Governance / Audit | OFARM_OWNED | Exception/waiver governance foundations only | OFARM uses `CharterException` | OFARM needs bounded, scoped, evidence-linked, expiring exception records that do not delete the rule. |
| CharterBreach | Governance / Audit | OFARM_OWNED | Nonconformity/audit foundations only | OFARM uses `CharterBreach` | OFARM needs sustainability charter breach posture without automatically creating legal nonconformity or Compliance Twin fact. |
| RiskBudget | Governance / Advisory | OFARM_OWNED | Risk-management foundations only | OFARM uses `RiskBudget` | OFARM needs bounded risk allowances for sustainability-sensitive operations and future autonomy hooks. |
| RegretBudget | Governance / Advisory / Learning | OFARM_OWNED | Experimentation/risk foundations only | OFARM uses `RegretBudget` | OFARM needs bounded downside hooks for future experimentation and self-improvement without defining CP13 learning law here. |

### CP11 alignment consequences

CP11 strengthens OFARM-owned governance around sustainability, but it does not create a new sustainability truth substrate.

External sustainability standards, certification programmes, buyer schemes, carbon or natural-capital methods, and environmental accounting frameworks may be admitted as anchors, profiles, mappings, evidence sources, runtime-surface contracts, or attestation wrappers. They do not become hidden OFARM law by being referenced.

`SustainabilityMetricProfile` is intentionally `OFARM_ALIGNED`, not `OFARM_OWNED` in the scientific-method sense: OFARM owns the governed profile carrier, not the underlying measurement science. Quantity, unit, observation, provenance, environmental vocabulary, and method anchors remain external where appropriate.

# OFARM Alignment Register v0.13 — CP12 update candidate

Date: 2026-05-28  
Status: final CP12 alignment-register patch merged active baseline addendum

## CP12 concept rows to add

The following concepts are OFARM-owned or OFARM-governed CP12 concepts. External machinery, robot, drone, tasking, or vendor payload standards may act as anchors, exchange mappings, evidence sources, or adapter profiles only. They do not become hidden OFARM law.

| Concept | Family | Alignment decision | Notes |
|---|---|---|---|
| CyberPhysicalMissionEnvelope | Mission / Runtime / Safety | OFARM_OWNED | Governs mission identity, lifecycle, stage references, and non-authorisation boundaries. |
| MissionIntent | Mission / Planning | OFARM_OWNED | Records physical-mission intent without creating mission authority. |
| MissionCandidate | Mission / Advisory | OFARM_OWNED | Candidate package, often agent-prepared; not dispatch authority. |
| MissionPlan | Mission / Planning | OFARM_OWNED | Governed plan; not command. |
| MissionScope | Mission / Geometry / Context | OFARM_OWNED | Declares mission spatial/temporal/actor/policy scope. |
| MissionPreflightTrace | Mission / Runtime / Safety | OFARM_OWNED | Preflight gate result; not dispatch authority. |
| MissionDispatchAuthorization | Mission / Authority | OFARM_OWNED | Action-specific authority record for dispatch. |
| CommandEnvelope | Mission / Command | OFARM_OWNED | Bounded command wrapper; not execution truth. |
| CommandIntegrityBasis | Mission / Security | OFARM_OWNED | Payload, recipient, mission, expiry, and replay-protection binding. |
| CommandAcknowledgement | Mission / Evidence | OFARM_OWNED | Command receipt acknowledgement; not proof of execution. |
| ExecutionWindow | Mission / Time | OFARM_OWNED | Temporal bounds for dispatch and command validity. |
| GeoFence | Mission / Geometry | OFARM_OWNED | Positive allowed mission boundary. |
| NoGoZone | Mission / Geometry / Safety | OFARM_OWNED | Excluded spatial area or condition. |
| RouteConstraint | Mission / Geometry / Safety | OFARM_OWNED | Route/path constraint for mission planning. |
| MissionGeometryValidationResult | Mission / Geometry / Safety | OFARM_OWNED | Validates geofence/no-go/route/CRS/freshness basis. |
| MissionSafetyConstraint | Mission / Safety | OFARM_OWNED | Safety constraint; critical classes cannot be advisory only. |
| PhysicalActorCapabilityProfile | Mission / Capability | OFARM_OWNED | Declared/verified capability of robot, machine, actuator, drone, or physical actor. |
| MissionCapabilityCompatibilityResult | Mission / Capability / Safety | OFARM_OWNED | Fresh compatibility result required for dispatch-bound missions. |
| AutonomyLevelDeclaration | Mission / Autonomy | OFARM_OWNED | Mission-specific autonomy declaration; does not grant authority by itself. |
| EmergencyStopPolicy | Mission / Safety | OFARM_OWNED | Emergency-stop availability, freshness, and test-evidence posture. |
| HumanOverridePolicy | Mission / Safety | OFARM_OWNED | Human-supervision and override posture. |
| LocalFallbackPolicy | Mission / Safety | OFARM_OWNED | Local fallback behaviour where connectivity/controller path fails. |
| LostLinkPolicy | Mission / Safety | OFARM_OWNED | Lost-link behaviour for mission-bound physical actors. |
| RemoteTakeoverEvent | Mission / Safety / Event | OFARM_OWNED | Remote takeover event; not accepted execution truth by itself. |
| MissionTelemetryEnvelope | Mission / Evidence | OFARM_OWNED | Machine-reported telemetry wrapper; evidence candidate only. |
| MissionExecutionReceipt | Mission / Evidence | OFARM_OWNED | Execution receipt; not verification by itself. |
| MissionVerification | Mission / Verification | OFARM_OWNED | Verification record; promotion still follows OFARM evidence/review law. |
| MissionAbortEvent | Mission / Event / Safety | OFARM_OWNED | Records abort/fallback event. |
| NearMissEvent | Mission / Event / Safety | OFARM_OWNED | Near-miss record requiring review for high-severity cases. |
| PhysicalSafetyIncident | Mission / Event / Safety | OFARM_OWNED | Physical safety incident record; not compliance fact by itself. |
| MissionOutputQualification | Mission / Output | OFARM_OWNED | Qualifies mission outputs and blocks misuse. |

## Residual debt

- CP12 schemas remain draft/non-default.
- External vendor payload profiles are not current/default.
- Safety certification is not claimed.
- Production robot/machine readiness is not claimed.

# OFARM Alignment Register CP13 update — merged active baseline addendum

Add the following CP13 concepts to the Alignment Register after CP13 acceptance and merge:

| Concept | Domain | Alignment posture | Notes | Rationale |
|---|---|---|---|---|
| LearningScope | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| LearningHypothesis | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| ExperimentProtocol | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| TrialDesign | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| ExperimentalUnit | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| TreatmentArm | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| ControlCondition | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| RandomizationPlan | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| BlockingFactor | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| OutcomeMeasureSpec | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| OutcomeObservationSet | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| LearningEvidenceBundle | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| LearningEvaluationTrace | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| CausalEstimate | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| LearningPromotionDecision | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| FarmMemoryEntry | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| FarmMemoryInvalidationRule | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| FarmMemoryRetrievalQualification | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| SeasonalLearningSummary | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| LearningOutputQualification | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| ExperimentRollbackTrigger | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |
| ExperimentException | Learning / Experimentation / Farm Memory | OFARM_OWNED | Active CP13 concept, draft/non-default machine contracts | CP13 needs governed learning/farm-memory semantics without hidden truth or deployment authority. |

CP13 concepts are OFARM-owned because they govern learning, experimentation, causal evidence, farm memory, promotion decisions, and output qualification. They remain subordinate to existing truth, current-state, twin, authority, pack, CP11, and CP12 law.


## CP14 alignment register addendum — Farm-to-Farm Intelligence Boundary — 2026-05-29

Alignment item: CP14 Farm-to-Farm Intelligence Boundary controlled-promotion boundary.

Decision: CP14 promotes the farm-to-farm intelligence concept family as OFARM-owned governance/cross-farm-intelligence surfaces for intelligence-sensitive use.

The CP14 concept family aligns with active OFARM truth/current-state/twin/authority/pack/query/output, CP11, CP12, and CP13 boundaries by requiring cross-farm intelligence, sharing, recipient-use limits, derivative-use limits, training-use limits, revocation propagation, regional alerts, benchmark deltas, aggregation/deidentification/anonymisation claims, re-identification-risk assessment, federated-learning contributions, model-improvement signals, contribution-quality assessment, poisoning/anomaly review, applicability assessment, and intelligence-output qualification to remain explicit, traceable, and subordinate to existing OFARM law.

CP14 does not promote CP15 generated-software/model-deployment contracts, OFARM Social constitution, OFARM Exchange constitution, public benchmark product law, production federated-learning platform law, generic reputation law, or livestock-specific cross-farm intelligence law.

Residual debt: CP14 machine-contract schemas, conformance fixtures, privacy/legal review, external data-space review, federated-learning implementation evidence, public/partner benchmark product governance, farmer-facing comprehension evidence, and production/pilot validation remain outside baseline alignment until separately produced and reviewed.


# OFARM Alignment Register CP15 update — baseline patch candidate

| Concept | Domain | Alignment class | External anchor posture | Canonical OFARM name | Rationale |
|---|---|---|---|---|---|
| SoftwareDeliveryBoundary | Software Delivery / Runtime Governance | OFARM_OWNED | External CI/CD and MLOps systems as integration surfaces only | SoftwareDeliveryBoundary | OFARM needs explicit delivery-governance boundary so generated artifacts and model deployments cannot bypass authority, evidence, conformance, runtime-surface, and CP11–CP14 gates. |
| GeneratedSoftwareArtifact | Software Delivery | OFARM_OWNED | Source-control and build tools as evidence sources only | GeneratedSoftwareArtifact | OFARM needs generated software to be typed as candidate artifact, not hidden runtime law. |
| GeneratedPatchArtifact | Software Delivery | OFARM_OWNED | Patch/diff tools as evidence sources only | GeneratedPatchArtifact | OFARM needs generated patches to remain reviewable candidates. |
| GeneratedAdapterArtifact | Interoperability / Runtime | OFARM_OWNED | Vendor APIs/adapters as external surfaces only | GeneratedAdapterArtifact | OFARM needs adapter generation governed so mappings do not mutate meaning or bypass runtime gates. |
| GeneratedWorkflowArtifact | Runtime / Agentic Development | OFARM_OWNED | Workflow engines as implementation surfaces only | GeneratedWorkflowArtifact | OFARM needs workflow changes governed where they affect OFARM outputs or actions. |
| GeneratedPromptOrPolicyArtifact | AI Runtime / Policy | OFARM_OWNED | Prompt tools/policy engines as implementation surfaces only | GeneratedPromptOrPolicyArtifact | OFARM needs prompt/policy changes governed where they alter runtime behavior or outputs. |
| SemanticMappingCandidate | Interoperability / Semantics | OFARM_OWNED | External standards/mappings as anchors only | SemanticMappingCandidate | OFARM needs candidate mappings to preserve loss/currentness/source-of-meaning boundaries. |
| BuildProvenance | Software Supply Chain | OFARM_OWNED | SLSA/SBOM/provenance standards as anchors only | BuildProvenance | OFARM needs build evidence without making build success deployment authority. |
| SBOMReference | Software Supply Chain | PROFILE_EXTERNAL | SBOM standards as profile anchors | SBOMReference | OFARM needs SBOM evidence while avoiding tool-specific lock-in. |
| DependencyRiskAssessment | Software Supply Chain / Security | OFARM_OWNED | Security tools as evidence sources only | DependencyRiskAssessment | OFARM needs dependency/license/use-constraint risk posture. |
| StaticAnalysisResult | Software Supply Chain / Security | OFARM_OWNED | Static analysis tools as evidence sources only | StaticAnalysisResult | OFARM needs static-analysis evidence without treating tool success as authority. |
| SecurityScanResult | Software Supply Chain / Security | OFARM_OWNED | Security scanners as evidence sources only | SecurityScanResult | OFARM needs security scan evidence without security-certification claims. |
| SecurityFindingWaiver | Authority / Security | OFARM_OWNED | Governance/security review standards as anchors | SecurityFindingWaiver | OFARM needs governed waivers with scope, expiry, authority, and trace. |
| ConformanceTestPlan | Conformance | OFARM_OWNED | Test frameworks as implementation surfaces only | ConformanceTestPlan | OFARM needs declared conformance plans for deployment-sensitive paths. |
| ConformanceRunReceipt | Conformance | OFARM_OWNED | Test runners as evidence sources only | ConformanceRunReceipt | OFARM needs conformance-run evidence without treating test success as deployment authority. |
| DeploymentCandidate | Runtime Governance | OFARM_OWNED | CI/CD systems as implementation surfaces only | DeploymentCandidate | OFARM needs explicit deployment candidates before deployment authorization. |
| DeploymentPlan | Runtime Governance | OFARM_OWNED | Deployment systems as implementation surfaces only | DeploymentPlan | OFARM needs scope/blast-radius/rollback-aware deployment plans. |
| DeploymentAuthorization | Authority / Runtime Governance | OFARM_OWNED | External approval systems as evidence wrappers only | DeploymentAuthorization | OFARM needs explicit authority for deployment. |
| DeploymentPromotionDecision | Authority / Runtime Governance | OFARM_OWNED | Release management systems as evidence wrappers only | DeploymentPromotionDecision | OFARM needs explicit promotion decisions separate from test/canary success. |
| ReleaseBundle | Runtime Governance | OFARM_OWNED | Package registries as evidence/storage surfaces only | ReleaseBundle | OFARM needs governed bundles with evidence, signatures, runtime bindings, and rollback posture. |
| RuntimeSurfaceReleaseBinding | Runtime Governance | OFARM_OWNED | Deployment topology as implementation detail | RuntimeSurfaceReleaseBinding | OFARM needs binding from release bundles to allowed runtime surfaces. |
| CanaryPlan | Runtime Governance | OFARM_OWNED | Observability/canary tools as implementation surfaces only | CanaryPlan | OFARM needs bounded canary posture without treating canary success as promotion. |
| CanaryResult | Runtime Governance / Evidence | OFARM_OWNED | Observability tools as evidence sources only | CanaryResult | OFARM needs canary evidence. |
| RollbackPlan | Runtime Governance | OFARM_OWNED | Deployment tools as implementation surfaces only | RollbackPlan | OFARM needs rollback readiness for high-consequence deployments. |
| RollbackEvent | Runtime Governance / Event | OFARM_OWNED | Deployment tools as evidence sources only | RollbackEvent | OFARM needs rollback events as traceable governance artifacts. |
| DeploymentTelemetryEnvelope | Runtime Governance / Evidence | OFARM_OWNED | Observability tools as evidence sources only | DeploymentTelemetryEnvelope | OFARM needs telemetry evidence without production-readiness implication. |
| RuntimeDeploymentReceipt | Runtime Governance / Evidence | OFARM_OWNED | Deployment tools as evidence sources only | RuntimeDeploymentReceipt | OFARM needs deployment occurrence receipts without making them conformance proof. |
| ModelDeploymentCandidate | Model Governance | OFARM_OWNED | Model registries as external sources only | ModelDeploymentCandidate | OFARM needs model deployment governance without generic MLOps law. |
| ModelEvaluationEvidence | Model Governance / Evidence | OFARM_OWNED | Model cards/benchmarks as evidence anchors only | ModelEvaluationEvidence | OFARM needs model evaluation evidence without deployment authority. |
| PromptPolicyChangeCandidate | AI Runtime / Policy | OFARM_OWNED | Prompt/policy tools as implementation surfaces only | PromptPolicyChangeCandidate | OFARM needs prompt/policy changes governed where they affect outputs/actions. |
| WorkflowDeploymentCandidate | Runtime Governance | OFARM_OWNED | Workflow engines as implementation surfaces only | WorkflowDeploymentCandidate | OFARM needs workflow deployment candidates governed explicitly. |
| SoftwareSupplyChainIncident | Security / Runtime Governance | OFARM_OWNED | Security incident taxonomies as anchors only | SoftwareSupplyChainIncident | OFARM needs governed supply-chain incidents. |
| DeploymentIncident | Runtime Governance / Security | OFARM_OWNED | Incident systems as evidence sources only | DeploymentIncident | OFARM needs governed deployment incidents that can trigger rollback/quarantine. |
| DeploymentOutputQualification | Output / Runtime Governance | OFARM_OWNED | Result-qualification foundations only | DeploymentOutputQualification | OFARM needs deployment-facing outputs to disclose readiness, evidence, authority, limitation, and allowed/prohibited use posture. |

CP15 concepts are OFARM-owned because they govern how generated artifacts, software delivery, model deployment, runtime-surface binding, and currentness/promotion boundaries interact with OFARM truth, authority, evidence, conformance, pack, agent, output, and CP11–CP14 laws.

CP15 does not promote any CP11, CP12, CP13, CP14, or CP15 draft/non-default schema to current/default. CP15 does not create production software-delivery readiness, production model-deployment readiness, cybersecurity certification, generic MLOps readiness, or full CI/CD product implementation.


# OFARM Alignment Register v0.13 — CP15 update

Status: accepted/merged CP15 amendment alignment addendum  
Date: 2026-05-30

## CP15 concept additions

CP15 adds the following OFARM-owned or OFARM-governed delivery concepts to the alignment register as candidate baseline concepts upon acceptance:

| Concept | Area | Alignment status | External role | Preferred OFARM term | Reason |
|---|---|---|---|---|---|
| SoftwareDeliveryBoundary | Delivery governance | OFARM_OWNED | External CI/CD/MLOps tools are runtime surfaces only | SoftwareDeliveryBoundary | Defines CP15 non-bypass boundary for software/model delivery. |
| GeneratedSoftwareArtifact | Agentic delivery | OFARM_OWNED | Generated code tools are provenance sources only | GeneratedSoftwareArtifact | Prevents generated code becoming deployment authority. |
| GeneratedPatchArtifact | Agentic delivery | OFARM_OWNED | Patch systems are evidence/provenance only | GeneratedPatchArtifact | Separates generated patch from accepted release. |
| GeneratedAdapterArtifact | Integration delivery | OFARM_OWNED | Adapter frameworks are external surfaces only | GeneratedAdapterArtifact | Enforces CP12/CP14 gates for mission and intelligence adapters. |
| GeneratedWorkflowArtifact | Runtime workflow | OFARM_OWNED | Workflow engines are runtime surfaces only | GeneratedWorkflowArtifact | Prevents generated workflow from becoming runtime authority. |
| GeneratedPromptOrPolicyArtifact | Policy/prompt delivery | OFARM_OWNED | Prompt/policy generators are provenance sources only | GeneratedPromptOrPolicyArtifact | Prevents high-consequence policy changes without review. |
| SemanticMappingCandidate | Semantic mapping | OFARM_OWNED | Mapping standards/tools are anchors only | SemanticMappingCandidate | Requires loss/coverage review before deployment. |
| BuildProvenance | Supply chain | OFARM_OWNED | Build tools are evidence sources only | BuildProvenance | Records build identity without granting authority. |
| SBOMReference | Supply chain | OFARM_OWNED | SBOM standards are evidence formats | SBOMReference | Connects dependencies to deployment gate. |
| DependencyRiskAssessment | Supply chain risk | OFARM_OWNED | External vuln data are evidence sources | DependencyRiskAssessment | Blocks critical/unknown risk without review. |
| StaticAnalysisResult | Security quality | OFARM_OWNED | External scanners are evidence sources | StaticAnalysisResult | Scan success is not deployment authority. |
| SecurityScanResult | Security quality | OFARM_OWNED | External scanners are evidence sources | SecurityScanResult | Blocks critical findings without authority/waiver. |
| SecurityFindingWaiver | Security governance | OFARM_OWNED | External waiver workflows are context only | SecurityFindingWaiver | Waivers require scope, expiry, and authority. |
| ConformanceTestPlan | Conformance | OFARM_OWNED | Test frameworks are runtime tools only | ConformanceTestPlan | Defines intended conformance coverage. |
| ConformanceRunReceipt | Conformance | OFARM_OWNED | Test runners are evidence sources | ConformanceRunReceipt | Run success is evidence, not deployment authority. |
| DeploymentCandidate | Deployment governance | OFARM_OWNED | Deployment tools are runtime surfaces | DeploymentCandidate | Candidate state is not deployment authority. |
| DeploymentPlan | Deployment governance | OFARM_OWNED | CI/CD plans are external execution plans | DeploymentPlan | Captures environment, gates, rollback, canary, blast radius. |
| DeploymentAuthorization | Authority | OFARM_OWNED | External approval systems are traces only | DeploymentAuthorization | Deployment requires explicit authority trace. |
| DeploymentPromotionDecision | Promotion | OFARM_OWNED | Release tools are evidence/runtime surfaces | DeploymentPromotionDecision | Promotion remains governed and non-automatic. |
| ReleaseBundle | Release | OFARM_OWNED | Registries are distribution surfaces | ReleaseBundle | Bundle release requires signature, SBOM, conformance, candidate consistency. |
| RuntimeSurfaceReleaseBinding | Runtime surface | OFARM_OWNED | Runtime systems are deployment surfaces | RuntimeSurfaceReleaseBinding | Binding is explicit and scoped. |
| CanaryPlan | Runtime release | OFARM_OWNED | Canary tooling is runtime instrumentation | CanaryPlan | Canary is bounded and non-production by default. |
| CanaryResult | Runtime release | OFARM_OWNED | Telemetry tools are evidence sources | CanaryResult | Canary pass is not production readiness. |
| RollbackPlan | Runtime safety | OFARM_OWNED | Rollback tools are execution mechanisms | RollbackPlan | Readiness requires evidence and freshness. |
| RollbackEvent | Runtime safety | OFARM_OWNED | Runtime events are evidence inputs | RollbackEvent | Rollback occurrence is a governed event. |
| RuntimeDeploymentReceipt | Runtime deployment | OFARM_OWNED | Runtime receipt is evidence only | RuntimeDeploymentReceipt | Receipt is not production readiness. |
| ModelDeploymentCandidate | Model delivery | OFARM_OWNED | Model registries are external surfaces | ModelDeploymentCandidate | Model evaluation is not deployment authority. |
| ModelEvaluationEvidence | Model evidence | OFARM_OWNED | Model cards/evals are evidence formats | ModelEvaluationEvidence | Requires bias/quality/fit handling. |
| SoftwareSupplyChainIncident | Incident | OFARM_OWNED | External incident systems are evidence sources | SoftwareSupplyChainIncident | Supply-chain incidents affect deployment gates. |
| DeploymentIncident | Incident | OFARM_OWNED | Runtime incident tools are evidence sources | DeploymentIncident | Incidents block/qualify deployment paths. |
| DeploymentOutputQualification | Output qualification | OFARM_OWNED | Output displays are surfaces only | DeploymentOutputQualification | Prevents deployment outputs from overclaiming authority/readiness. |

## CP15 non-promotions

CP15 does not promote CP11, CP12, CP13, CP14, or CP15 draft/non-default machine contracts to current/default.


# OFARM Alignment Register v0.13 — CP14 Update

Status: final CP14 alignment-register patch candidate  
Amendment: CP14 — Farm-to-Farm Intelligence Boundary

Add the CP14 concept family as OFARM-owned or OFARM-governed cross-farm intelligence boundary concepts. External data-space, certification, buyer, public-authority, social, exchange, or federated-learning systems may be anchors, profiles, mappings, evidence sources, attestations, or sister-platform references; they do not become hidden OFARM law.

## CP14 concept rows

| Concept | Domain | Alignment posture | External relationship | OFARM label | Reason |
|---|---|---|---|---|---|
| FarmIntelligenceBoundary | Cross-farm intelligence / Governance | OFARM_OWNED | Data-space/sister-platform references as anchors only | FarmIntelligenceBoundary | Governs cross-farm intelligence boundaries, advisory default, and non-authorisation rules. |
| FarmIntelligenceSharePolicy | Sharing / Governance | OFARM_OWNED | Contract/policy references as anchors | FarmIntelligenceSharePolicy | Defines what intelligence may be shared, with whom, for what purpose, and under what use constraints. |
| FarmIntelligenceShareGrant | Authority / Sharing | OFARM_OWNED | Existing SharingGrant foundation | FarmIntelligenceShareGrant | Specialised grant for intelligence sharing, recipient use, derivative use, training use, retention, onward sharing, and revocation. |
| FarmIntelligenceContribution | Cross-farm intelligence | OFARM_OWNED | External observations/signals as evidence candidates | FarmIntelligenceContribution | Represents contributed intelligence without making it farm truth. |
| IntelligenceContributionPackage | Packaging / Sharing | OFARM_OWNED | Data-package standards as mappings only | IntelligenceContributionPackage | Packages contribution, limitations, quality, permissions, and output posture. |
| LearningArtifactSharePackage | CP13 / Cross-farm intelligence | OFARM_OWNED | None | LearningArtifactSharePackage | Governs CP13 learning/farm-memory artifacts crossing farm boundaries. |
| RecipientUseConstraint | Sharing / Use restriction | OFARM_OWNED | Contract/policy references as anchors | RecipientUseConstraint | Defines recipient-side use limits, onward sharing, disclosure, and prohibited uses. |
| DerivativeUsePolicy | Sharing / Derivative use | OFARM_OWNED | Contract/policy references as anchors | DerivativeUsePolicy | Controls derivative analytics, summaries, benchmarks, and training derivatives. |
| TrainingUsePolicyBinding | Training / Use governance | OFARM_OWNED | Model-training policy references as anchors | TrainingUsePolicyBinding | Binds contribution use to allowed model/training purposes without creating CP15 deployment authority. |
| RevocationPropagationTrace | Sharing / Revocation | OFARM_OWNED | Existing revocation foundations | RevocationPropagationTrace | Traces revocation effects across packages, outputs, recipients, and training use. |
| RegionalAlert | Regional intelligence | OFARM_OWNED | Public/regional services as evidence or sister-platform sources | RegionalAlert | Represents regional alert outputs without creating farm-level occurrence truth. |
| RegionalRiskSignal | Regional intelligence | OFARM_OWNED | External risk feeds as anchors | RegionalRiskSignal | Represents regional risk signals as Advisory intelligence. |
| RegionalAlertCorrection | Regional intelligence | OFARM_OWNED | Correction/withdrawal references as evidence | RegionalAlertCorrection | Corrects or disputes regional alert outputs. |
| RegionalAlertWithdrawal | Regional intelligence | OFARM_OWNED | Withdrawal references as evidence | RegionalAlertWithdrawal | Withdraws alert outputs and blocks downstream use where required. |
| BenchmarkDelta | Benchmarking | OFARM_OWNED | Benchmark products as sister-platform/product references | BenchmarkDelta | Represents benchmark deltas without creating compliance facts or public ranking law. |
| AggregationFloor | Privacy / Aggregation | OFARM_OWNED | Statistical/privacy standards as anchors | AggregationFloor | States minimum aggregation conditions; not anonymisation by assertion. |
| DeidentificationClaim | Privacy / Disclosure | OFARM_OWNED | Privacy standards as anchors | DeidentificationClaim | Represents deidentification claim with risk basis. |
| AnonymisationClaim | Privacy / Disclosure | OFARM_OWNED | Privacy standards as anchors | AnonymisationClaim | Represents stronger anonymisation claim with approval and low re-identification risk requirements. |
| ReidentificationRiskAssessment | Privacy / Risk | OFARM_OWNED | Privacy risk methods as anchors | ReidentificationRiskAssessment | Controls disclosure posture and risk qualification. |
| FederatedLearningContribution | Federated learning boundary | OFARM_OWNED | Federated-learning systems as sister/platform references | FederatedLearningContribution | Contribution boundary only; not model deployment authority. |
| FederatedAggregationReceipt | Federated learning boundary | OFARM_OWNED | Federated aggregation system receipt | FederatedAggregationReceipt | Receipt/evidence candidate; not deployment authority. |
| ModelImprovementSignal | Model improvement boundary | OFARM_OWNED | CP15 future model-governance references | ModelImprovementSignal | Advisory model-improvement signal; not deployment authority. |
| TrainingUseReceipt | Training-use audit | OFARM_OWNED | Training systems as future CP15/sister refs | TrainingUseReceipt | Records training use under policy; not deployment law. |
| ContributionQualityAssessment | Quality / Security | OFARM_OWNED | Data-quality methods as anchors | ContributionQualityAssessment | Qualifies contribution usability and limitations. |
| PoisoningOrAnomalyReview | Security / Data quality | OFARM_OWNED | Security/anomaly methods as anchors | PoisoningOrAnomalyReview | Blocks or qualifies downstream use when poisoning/anomaly risk exists. |
| CrossFarmApplicabilityAssessment | Advisory / Applicability | OFARM_OWNED | None | CrossFarmApplicabilityAssessment | Required before received intelligence informs high-consequence local use. |
| IntelligenceOutputQualification | Output qualification | OFARM_OWNED | Result-qualification foundations | IntelligenceOutputQualification | Qualifies cross-farm outputs and blocks prohibited use classes. |

## CP14 alignment addendum

CP14 promotes the farm-to-farm intelligence boundary concept family as candidate baseline-recognised concepts. It does not promote CP14 machine contracts to current/default and does not create CP15, OFARM Social, OFARM Exchange, public benchmark product, or production federated-learning platform law.
