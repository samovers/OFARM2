# OFARM Platform Runtime and Product Architecture (RC2.1)

Date: 2026-04-11  
Status: release candidate 2.1 (cross-RFC harmonized post-charter baseline; wave-6 closure-aligned; AGR-P7 agronomic carrier harmonization applied; ONT-SEMINT v0.3 semantic-integrity runtime-baseline harmonisation applied)  
Role: runtime law and implementation architecture for OFARM Platform  
Last harmonized: 2026-05-14 — ONT-SEMINT v0.3 semantic-integrity runtime-baseline harmonisation

---

## 1. Purpose and relationship to the Constitution

### 1.1 Purpose
OFARM Platform is the runtime and product architecture that realizes the OFARM Constitution.

It answers:
- how canonical truth is stored and materialized
- how edge/offline work is handled
- how capture/import/query/AI/output flows are executed
- how constitutional law is enforced in practice
- how packages, capabilities, integrations, and compiled outputs are exposed

### 1.2 Precedence
The Constitution defines model law.  
OFARM Platform realizes that law.

If a runtime choice conflicts with constitutional meaning, the Constitution wins.

### 1.3 What the platform may optimize
The platform may optimize:
- storage layout
- caches
- indexes
- APIs
- sync strategy
- UI/dialogue orchestration
- service topology
- compute placement

It may not optimize by:
- flattening canonical truth into the authoritative model
- changing commit semantics by convenience
- turning exchange payloads into truth by default
- creating new constitutional meaning by implementation alone

---

## 2. Runtime architecture principles

### 2.1 Semantic-native authority
Canonical truth is semantically native and graph-oriented.

### 2.2 Derived pragmatism
Relational read models, search indexes, reporting marts, analytics views, API payload views, and edge caches are allowed as **derived projections**.

### 2.3 Edge realism
The platform is offline-capable at the edge and online-authoritative at the core.

### 2.4 Governance before automation
Automation, AI, and integration convenience may not bypass constitutional truth, evidence, authority, or promotion law.

### 2.5 Modular context
Packs are runtime-installable and scope-assignable, but may not bypass constitutional boundaries.

### 2.6 Enforcement architecture
The platform must realize constitutional law through deterministic enforcement points rather than UI discipline, operator memory, or hidden conventions.

### 2.7 Failure classes
The platform should distinguish at least:
- reject
- retain as draft
- contested / under review
- require more evidence
- deferred due to pack/context conflict
- accepted with trace

---

## 3. Enforcement architecture

### 3.1 EnforcementChain
Every state-affecting path must cross the relevant gates in an **EnforcementChain**.

Baseline gates are:
1. ingress normalization
2. authority
3. structural/semantic validation
4. pack/profile applicability
5. evidence sufficiency where required
6. review/promotion
7. current-state materialization
8. publication/export traceability

Not every path hits every gate equally, but every authoritative outcome must cross the relevant gates.

### 3.2 Ingress normalization gate
Capture/import must normalize incoming material into typed OFARM draft material before it may progress.

### 3.3 Authority gate
The platform must evaluate whether the acting Party/agent/path has the required:
- authority family
- scope
- time interval
- delegation basis where relevant

### 3.4 Validation gate
The platform must validate:
- structure
- semantic type
- alignment constraints
- event family
- content/path consistency

### 3.4a Agronomic carrier validation
For high-consequence agronomic flows, validation must also check the applicable carrier contracts and profile requirements for:
- observation and measurement context
- quantity kind plus unit code
- intervention intent versus execution/as-applied record class
- partial extent and geometry-basis quality
- scheme-bound identity and unresolved-binding posture
- reconstruction policy references where a query or output depends on those facts

### 3.5 Pack/profile applicability gate
The platform must resolve the active **PackActivationSet** and the rules, evidence policies, and constraints that actually apply.

### 3.6 Evidence sufficiency gate
Where policy requires it, the platform must check required evidence or acceptable durable evidence references before promotion.

### 3.7 Review/promotion gate
The platform must determine whether material:
- stays draft
- becomes accepted
- becomes contested
- requires formal review/decision

### 3.8 Current-state materialization gate
Only accepted/in-force material may change relevant current-state materialization.

The gate must also determine whether the resulting materialization is:
- FRESH
- STALE
- INVALID

for the relevant use class.

### 3.9 Publication/export gate
PassportViews, DocumentAssemblies, APIs, and exports must assemble from the governed substrate and remain traceable back to it.

### 3.9a Agronomic reconstruction and disclosure gate
For high-consequence agronomic outputs, publication/export must evaluate the governing AgronomicReconstructionPolicy and retain or emit an AgronomicReconstructionTrace where required.

PassportView generation must fail, require review, or disclose limitations when evidence, materialization freshness, code binding, geometry basis, or dispute policy is not satisfied.
DocumentAssembly generation may freeze annexes and disputed material only under explicit policy and without promoting that annexed material into accepted truth.

### 3.10 Enforcement logging
The platform must preserve traceable records of gate outcomes where they affect authoritative promotion, rejection, review, activation, or publication.

---

## 4. Canonical substrate and projections

### 4.1 Assertion/history-first canonical substrate
The platform realizes the constitutional authority as an assertion/history-first semantic substrate containing:
- immutable assertion records
- immutable event records
- immutable review decisions
- evidence relations
- lineage relations
- accepted event consequences

### 4.2 Governed current-state materializations
The platform maintains governed current-state materializations derived from the canonical substrate.

Each materialization instance must at minimum be identifiable by:
- target twin
- anchor scope
- evaluation time policy
- context snapshot
- MaterializationBasis
- generated-at time
- freshness status

### 4.3 MaterializationBasis
The platform must be able to trace a materialization back to:
- contributing in-force AssertionRecords
- contributing accepted event consequences
- contributing ReviewDecisions
- relevant identity revisions or lifecycle relations where they affect interpretation
- relevant context snapshot identifiers
- evaluation time policy

For high-consequence use, this context basis should resolve to a governed **ContextSnapshot** rather than an opaque runtime-only token.

### 4.4 MaterializationSnapshot
The platform should create or retain a MaterializationSnapshot or equivalent traceable basis record when:
- a high-consequence action depends on current state
- an attested or frozen compiled output depends on it
- later audit/explanation of the relied-upon state basis may matter

### 4.5 Freshness status
The platform must determine whether a materialization is:
- FRESH
- STALE
- INVALID

Freshness is purpose-sensitive.
A materialization acceptable for exploratory advisory viewing may be unacceptable for compliance or attested publication.

### 4.6 Invalidation triggers
At minimum the platform must recognize these trigger families:
- truth-basis triggers
- identity/lifecycle triggers
- context triggers
- time-policy triggers
- twin-specific advisory triggers where relevant

The platform must be able to explain which trigger changed status and why.

### 4.7 High-consequence use rule
Before a high-consequence use materially relying on current state, the platform must ensure the relevant materialization is either:
- freshly recomputed for that use, or
- demonstrably still FRESH under the declared policy

If STALE or INVALID, the platform must recompute, refuse the action, or route to explicit review if policy allows.

### 4.8 Projection families
The platform may maintain:
- relational read models
- search indexes
- reporting marts
- analytics views
- API payload views
- local device caches

### 4.9 Projection rule
Every non-canonical projection must be:
- derived
- refreshable or recomputable
- traceable back to canonical truth

### 4.10 Authoritative write rule
Authoritative writes must land in the assertion/history-first substrate.

The platform may not allow direct truth writes into:
- projections
- caches
- report stores
- search indexes
- external-facing payload stores

### 4.11 Evidence representation
Where evidence matters, the platform must preserve:
- the raw asset or durable reference
- the structured semantic interpretation

### 4.12 Projection trace-back
Every important projection should remain traceable back to:
- substrate identifiers
- current-state materialization basis
- relevant pack/profile context
- relevant query/view basis where appropriate

---

## 5. Local and offline edge model


### 5.1 Chosen posture
OFARM Platform uses:
- **offline-capable edge**
- **online-authoritative core**

### 5.2 What must work offline
At minimum:
- viewing recent synced farm/field/crop context
- recording operations
- recording observations and heuristics
- taking photos / attaching evidence
- voice sessions
- local drafts
- local validation where feasible
- local event-family typing where feasible
- queueing later sync/commit
- cached passport views and recent history with freshness cues

### 5.3 What stays primarily online in v2
At minimum:
- final canonical graph truth
- cross-farm/regional intelligence
- heavy advisory computation
- pack installation/promotion/governance
- external reference refresh
- complex multi-pack compatibility resolution
- final attested compiled outputs

### 5.4 Local semantic draft graph
The edge may keep a local semantic draft graph.  
It does not become the final authority for the whole OFARM universe.

### 5.5 Sync discipline
Sync must preserve:
- idempotency
- late-arriving evidence
- correction/supersession
- distinction between assertion time, event time, effective time, and record time
- authority and sharing re-evaluation where stale local grants may have changed
- review escalation when conflicts or promotions require it

### 5.6 Edge enforcement posture
The edge may do preliminary typing, validation, and evidence capture.

The edge should not finalize:
- compliance facts
- accepted executed intervention consequences
- pack/context activation requiring central compatibility/governance
- final attested compiled outputs
- high-consequence reliance on stale or invalid current-state materialization

unless a later governed architecture version explicitly makes that safe.

### 5.7 Freshness cues
When the edge shows cached current state, it should expose freshness cues clearly enough that users and services can distinguish:
- fresh enough for exploratory use
- stale for high-consequence use
- invalid/unreliable for governed reliance

---

## 6. Ingestion and capture architecture

### 6.1 Capture channels
The platform should support at least:
- manual UI entry
- voice capture
- scanner/document capture
- machine imports
- partner/system imports
- EO/sensor-derived ingestion where used
- AI-assisted capture as governed draft generation

### 6.2 Capture rule
Capture is not commitment.

Capture may create draft material, evidence, or advisory artifacts.
Promotion into authoritative outcomes still requires the relevant gates.

### 6.3 Scanner and document capture
Scanner/document capture should be document-first:
- capture proof
- register evidence
- parse/OCR as helper
- review
- commit only through governed routes

### 6.4 Machine and partner imports
Import mappings must translate external inputs into:
- typed OFARM draft assertions
- typed OFARM events
- typed evidence links
- typed advisory or auxiliary material where appropriate

No import format is canonical by itself.

### 6.4a Agronomic import normalization
Agronomic imports that carry scouting results, samples, lab reports, sensor readings, prescriptions, work orders, machine logs, as-applied maps, product labels, registry lookups, or geometry must normalize into the applicable OFARM draft records, evidence, and agronomic carrier shells.

ADAPT, ISOXML, EFDI, ISOBUS DDI, registry responses, lab reports, and controller files are exchange or evidence surfaces.
They may support promotion only after authority, evidence, validation, review, and materialization gates pass.

### 6.5 Early checks
Ingress should perform early checks for:
- plausible authority basis
- required scope binding
- obvious pack/profile incompatibility
- obvious evidence absence for flows that cannot succeed without it

### 6.6 Capture-to-commit handoff
Capture services may collect and enrich material, but may not silently skip downstream review/promotion gates.

---

## 7. Interaction and query runtime

### 7.1 Interaction principle
The runtime must keep separate:
- structured content definition
- dialogue flow
- user guidance
- saved views
- final compiled outputs

### 7.2 Voice session rule
A voice session should preserve:
- raw transcript/audio where needed
- interpreted semantic candidates
- commit-class typing
- advisory content separate from truth content

### 7.3 Guided clarification
The runtime may use dialogue to:
- clarify location/scope
- clarify operation details
- ask for evidence
- resolve ambiguity
- suggest next steps

It may not use dialogue convenience to bypass truth discipline.

### 7.4 Public expert-query posture
In v2, the platform should expose:
- guided analytical UI
- AI-mediated semantic retrieval
- saved views/passports

It should not require or publicly expose a full expert textual query language in first release scope.

### 7.5 Query entry surfaces
The runtime may accept query intent from:
- guided UI
- AI-mediated natural language
- saved view invocation
- governed internal expert/developer tools

All such entry surfaces must resolve into the same formal query path.

### 7.6 QuerySpecification validation
The runtime must validate QuerySpecification instances against the formal QuerySpecification schema before planning or execution.

Malformed specifications must fail clearly rather than degrade into hidden fallback behavior.

### 7.7 QueryPlanIR generation
The runtime must compile valid QuerySpecifications into a formal **QueryPlanIR** representation before execution.

QueryPlanIR must be valid against its own formal schema.

### 7.8 QueryPlanIR responsibilities
QueryPlanIR must be able to:
- resolve aliases
- bind twin/scope/time/authority constraints
- choose execution targets
- declare freshness/materialization requirements
- preserve semantic equivalence expectations across execution paths

### 7.8a Agronomic reconstruction planning
When a query or output depends on agronomic observation, measurement, intervention, execution, partial extent, code-binding, or disputed evidence, QueryPlanIR must preserve the governing AgronomicReconstructionPolicy.

The plan must choose between history reconstruction and governed current-state reuse explicitly.
It must fail clearly when stale state, unresolved identity, weak geometry, missing evidence, or unresolved dispute would make a high-consequence result unsafe.

### 7.9 Execution posture
Execution may target:
- semantic graph engines
- current-state materializations
- derived read models or search indexes
- resource/geospatial filter endpoints

provided:
- semantic meaning is preserved
- traceability is preserved
- projection-only semantics are not introduced

### 7.10 Alias resolution contract
SemanticPathAlias must resolve against current governed archetype/template structures using a versioned alias-resolution contract.

Where aliases are resolved, the runtime should be able to identify the governing alias catalog and emit or retain a traceable alias-resolution outcome.

If alias resolution is stale or ambiguous, the runtime should fail clearly rather than guess.

### 7.11 Query equivalence rule
If different execution targets are used for the same QuerySpecification, the runtime must preserve semantic equivalence strongly enough for conformance and debugging.

This does not require identical physical plans.
It does require equivalent governed meaning.

---

## 8. AI services and boundaries


### 8.1 AI role families
The platform may use:
- interpretation AI
- query AI
- authoring AI
- advisory AI
- simulation AI

### 8.2 Boundary rule
AI may:
- interpret raw input
- generate hypotheses
- suggest structure
- recommend queries
- prepare documents/dossiers
- help author local artifacts
- propose packs/templates/rules for review
- generate advisory outputs and scenarios

AI may not:
- silently redefine canonical semantics
- silently promote advice into compliance fact
- bypass evidence requirements
- bypass governance for core/official artifacts

### 8.3 Model governance runtime
Model/module registration should track at minimum:
- identifier
- version
- intended use
- inputs required
- output type
- pack/crop/geography scope
- validation/evaluation status
- approval status
- advisory-only versus promotable status

### 8.4 AI enforcement path
AI outputs must enter through the same enforcement architecture as other inputs:
- interpretation AI -> draft assertions or hypotheses
- query AI -> QuerySpecification and QueryPlanIR
- advisory AI -> advisory outputs
- authoring AI -> draft artifacts pending governance

### 8.5 Future-direction boundary
Agent/tool ecosystem readiness is desirable, but v2 does not depend on autonomous multi-agent workflows.

---

## 9. Digital Twin runtime

### 9.1 One semantic substrate
The platform implements the twins over one semantic substrate.

### 9.2 Compliance Twin
The Compliance Twin is realized as a logical partition and current-state materialization policy that is:
- hard-truth oriented
- evidence-linked
- append-only in history
- auditable
- deterministic in consequence handling

It may only materialize from:
- in-force accepted assertions
- accepted event consequences
- valid review decisions
- applicable context and evidence rules

For high-consequence compliance use, stale materialization is not acceptable by default.

### 9.3 Advisory Twin
The Advisory Twin is realized as a logical partition and current-state materialization policy that is:
- revisable
- simulation-friendly
- hypothesis-rich
- explainability-oriented
- AI-heavy where useful

It may use:
- hypotheses
- advisory outputs
- risk flags
- scenario outputs
- competing candidate interpretations

Advisory materialization may tolerate staleness in exploratory or explanatory views if clearly marked, but not when supporting a governed bridge into harder truth.

### 9.4 Runtime freedom
The platform may use separate services, indexes, caches, and compute paths to realize the twins.

It may not turn those runtime choices into separate truth universes with broken lineage.

### 9.5 Bridge enforcement
The platform must enforce that Advisory-Twin outputs do not mutate Compliance-Twin current state directly without the constitutionally governed bridge.

If Advisory-Twin state contributes to a bridge toward compliance consequence, the platform must re-evaluate the relevant state under Compliance-Twin freshness and basis rules.

### 9.6 Submodel discipline
The twin implementation should expose clear submodels such as:
- identity and geometry
- crop and phenology
- soil and water
- weather and microclimate
- operations and interventions
- observations and evidence
- compliance and claims
- economics and inputs
- advisory state and scenarios

---

## 10. Passport and compiled-output runtime

### 10.1 Output taxonomy principle
The platform must keep separate:
- live/recomputable **PassportViews**
- frozen **DocumentAssemblies**
- DocumentAssembly subfamilies such as reports, dossiers, and submissions

### 10.2 PassportView family
The platform serves a PassportView family of portable scope-centric compiled views, including:
- Farm PassportView
- Site PassportView
- Field PassportView
- CropCycle PassportView
- Lot PassportView
- Facility PassportView where relevant

Recipient-specific variants are usually profiles of these family members, not separate top-level output families.

### 10.3 One source, many outputs
The platform should maintain one canonical machine-readable source of truth and generate:
- machine-readable PassportViews where needed
- human-readable PassportViews where useful
- frozen ReportAssemblies
- frozen DossierAssemblies
- frozen SubmissionAssemblies

### 10.4 Output semantics
Examples:
- a buyer-facing lot summary is usually a **Lot PassportView** with a buyer-oriented profile
- an inspection-centered package is usually a **DossierAssembly**
- a subsidy/support filing package is usually a **SubmissionAssembly**

### 10.5 DocumentAssembly behavior
The platform should realize DocumentAssembly behavior with:
- governed assembly
- freezing/versioning
- derivation trace
- attestation/signature hooks
- later reference as evidence

Where a frozen output materially relies on current state, the platform should retain a MaterializationSnapshot or equivalent traceable basis record.

Where an output is attested, claim-bearing, or filed, the platform should evaluate and retain the applicable evidence-sufficiency result.

### 10.5a Agronomic output reconstruction
For agronomic PassportViews and DocumentAssemblies, the platform must preserve the distinction between:
- accepted consequences used for high-consequence output
- advisory reasoning
- provisional or disputed records
- raw source payloads and machine imports
- annexed unresolved evidence

PassportView remains live/recomputable and accepted-only by default for compliance profiles.
DocumentAssembly remains frozen/versioned and may include annexes under explicit reconstruction policy.

### 10.6 Separation rule
A PassportView is not a DocumentAssembly.  
A DossierAssembly or SubmissionAssembly is not a PassportView.  
A DocumentAssembly is not canonical state.

Runtime metadata contracts must preserve this separation rather than flattening all compiled outputs into one bucket.

### 10.7 Output-subtype handling
The platform should be able to handle output families differently where needed, including:
- different sharing defaults
- different attestation behavior
- different review steps
- different integration/export targets

---

## 11. Advisory runtime including Next 72h Advisor

### 11.1 Advisory posture
Advisory services live primarily in the Advisory Twin and remain explainable, revisable, and non-authoritative unless a governed bridge promotes outcomes later.

### 11.2 Next 72h Advisor
The Next 72h Advisor is an advisory service, not a core semantic layer.

Typical inputs may include:
- weather and microclimate context
- recent observations
- crop-stage context
- active risks
- local heuristics
- pack/profile constraints

Its outputs remain advisory outputs, scenarios, or review prompts unless later promoted through governed paths.

### 11.3 Other advisory services
Other advisory/runtime services may include:
- EO scout prioritization
- benchmark/explainability services
- climate adaptation planning
- scenario generation
- model-assisted interpretation

### 11.4 Scenario support
Scenario artifacts should preserve:
- scenario inputs
- assumptions
- method/model used
- uncertainty
- outputs
- later observed outcomes where available

---

## 12. Eventing, integration, and sync architecture

### 12.1 Event discipline
The platform needs more than CRUD.  
It needs a disciplined event architecture for:
- state-change transport
- notifications
- workflow triggers
- external interoperability
- digital-twin synchronization

### 12.2 Event-family awareness
Runtime transport is free to optimize, but it may not collapse or obscure constitutional event families beyond traceable recovery.

### 12.3 Event envelope versus semantic event
The platform must distinguish:
- semantic events in the canonical model
- transport envelopes used to move them between systems

### 12.4 Commit-gate awareness
Event ingestion and sync must preserve the distinction between:
- incoming commit classes
- accepted event consequences
- current-state updates

Receiving an event is not equivalent to accepting its consequence into current-state materialization.

### 12.5 Asynchronous first-class behavior
The platform should support:
- event publication
- subscriptions
- retry-safe delivery
- idempotent consumption
- delayed reconciliation
- late-arriving evidence

### 12.6 External mappings
External interoperability should be implemented through governed mapping modules, including where relevant:
- ADAPT
- AEF / ISOXML / EFDI
- NGSI-LD / FIWARE-style contexts
- SAREF4Agri-related device semantics
- traceability/event exchange formats
- partner-specific APIs

These are integration surfaces, not canonical truth.

Each declared mapping surface should publish a governed **MappingCoverageStatement** and **LossMap** so coverage, approximation, and loss remain explicit.

Inbound external payloads should normally normalize into draft material or low-promotion commit classes such as operation claim, observation assertion, or evidence record unless separate governed policy explicitly allows stronger promotion.

Partner-facing APIs, event feeds, query façades, and discovery documents should be represented as governed **RuntimeSurfaceContract** artifacts or equivalent contracts and linked from the Capability Manifest where declared.

### 12.7 Event-trace retention
The runtime should retain event envelopes and mapping trace where needed so semantic events, accepted consequences, and exported notifications remain explainable.

---

## 13. Capability, registry, and package runtime

### 13.1 Capability Manifest
The platform must expose a machine-readable **Capability Manifest**.

The Capability Manifest is a deployment/tenant self-description contract, not a second runtime ontology.

### 13.2 Mandatory manifest fields
A valid Capability Manifest must include at minimum:
- schemaVersion
- manifestId
- ofarmVersion
- platformVersion
- publishedAt
- deploymentScope
- capabilitySections
- registryRelation
- conformance

### 13.3 Capability sections
The baseline capability sections are:
- artifactSupport
- packSupport
- querySupport
- eventSupport
- authoritySupport
- importExportSupport
- enforcementSupport

These sections should describe what the deployment actually supports, not what is merely aspirational.

### 13.4 Registry relation
The manifest must declare a registry relation that includes at minimum:
- manifestRegistryRef
- artifactRegistryRef
- activeArtifactSetRef
- discoveryVisibility

The manifest may additionally reference the active SemanticSubstrateBundle and a ConformanceClaimSet where those are published.

This is required so capability claims remain grounded in:
- a real registry context
- a real active artifact/package state

### 13.5 Package/registry runtime
The platform must support installable/versioned artifacts and packages with:
- dependency resolution
- compatibility checks
- exclusion handling
- signing/approval where needed
- activation by scope
- deterministic activation failure behavior

### 13.6 Pack activation planning
Before activation, the platform must evaluate a concrete PackActivationSet including:
- requested pack(s)
- requested scope/time
- already active packs/profiles
- precedence classes
- declared compatibility and merge rules

### 13.7 Surface-family merge evaluation
When packs overlap on touched surfaces, the runtime must:
- assign the overlap to a governed PackSurfaceFamily
- determine the legally allowed PackSurfaceMergeMode for that family
- apply the merge only if it is explicitly declared and safe
- otherwise fail or require governance

### 13.8 Conflict handling posture
When conflicts occur, the platform must:
- apply a declared safe merge policy where one exists and where the merge mode is legal for that surface family
- otherwise fail activation deterministically
- preserve traceable conflict output
- avoid hidden partial activation

### 13.9 Merge-resolution trace
Where overlap matters, the platform must be able to produce a PackMergeResolutionTrace or equivalent trace showing:
- packs compared
- PackActivationSet
- surface family
- merge mode applied
- precedence relationship
- resulting outcome
- reason for failure/governance requirement where relevant

### 13.10 Discovery posture
The platform should expose discovery surfaces for:
- manifests
- artifacts
- packs
- views
- document assemblies
- reference snapshots
- data products where appropriate

Where partner-facing HTTP, event, or query façades are exposed, the platform should publish stable service-description references such as OpenAPI, AsyncAPI, or equivalent contracts, and may expose a stable discovery location such as a `.well-known` capability endpoint.

### 13.11 Activation and approval trace
Artifact approval, pack activation, and activation failure should leave durable trace so enforcement outcomes are explainable later.

### 13.12 Capability-manifest schema
The normative companion artifact for runtime self-description is:

- **OFARM Capability Manifest RFC v0.1**
- **OFARM Capability Manifest schema v0.1**
- **OFARM Conformance Claim Set and Capability Manifest Reference Extension RFC v0.1**

---

## 14. Security, authority, trust, and data-sovereignty controls


### 14.1 Principle
Security is not enough by itself.  
The platform must also enforce:
- authority boundaries
- delegation boundaries
- sharing boundaries
- revocation effects
- farm/tenant data-sovereignty boundaries

### 14.2 Action-based authorization
The platform must evaluate authorization against a governed **AuthorityActionClass**, not only broad role/family labels.

### 14.3 AuthorizationDecision
For a requested action, the platform must evaluate at minimum:
- acting Party / software agent
- requested AuthorityActionClass
- target scope
- target time
- purpose where relevant
- applicable RoleAssignments
- applicable AuthorityGrants
- applicable DelegationGrants
- applicable SharingGrants when access is the action
- applicable RevocationDecisions
- applicable ScopeInheritanceMode

The runtime may expose typed request/result envelopes for this decision boundary, but those envelopes do not change the governing decision factors.

### 14.4 Authorization outcomes
The baseline runtime outcomes are:
- ALLOW
- DENY
- REQUIRE_REVIEW
- REQUIRE_HUMAN_APPROVAL

### 14.5 Default deny
If the platform cannot justify a valid action path, the default is DENY.

### 14.6 No implicit authority rule
The platform may not assume that a Party may:
- assert
- review
- decide
- sign
- activate context
- share
- revoke
- receive/use data

merely because that Party appears in provenance or workflow.

### 14.7 Scope inheritance enforcement
Broad-scope grants do not automatically imply all narrower or derived-scope powers.

The platform must enforce the declared ScopeInheritanceMode and must not:
- infer upward inheritance
- infer governance/signing/context powers from broad operational grants
- treat derived-scope authority as valid without explicit allowed lineage mode

### 14.8 Separation-of-authority enforcement
The platform must enforce separation between:
- write/submit authority
- review authority
- decision authority
- attestation/sign authority
- context-governance authority
- sharing/revocation authority
- receive/use authority

### 14.9 Delegation enforcement
Delegation may not exceed the delegator’s valid authority.
The platform must retain trace of:
- delegator
- delegate
- granted action/path
- scope/time
- purpose/conditions where relevant

### 14.10 Farm/tenant boundary and sharing controls
The platform must support:
- explicit sharing rather than silent cross-party access
- scope-bounded visibility
- compiled-output sharing without implied write authority
- farm/tenant boundary enforcement
- regional/cross-farm intelligence access only through governed pathways

### 14.11 Revocation and retention
The platform must support revocation/narrowing of future authority or access where governance allows it.

Revocation must not:
- erase historical truth
- silently break provenance
- pretend past attested history never existed

### 14.12 AI-assisted action policy
If AI assists a human-authorized actor:
- the human remains the accountable actor for the final action
- AI assistance should be traceable
- the runtime may return REQUIRE_HUMAN_APPROVAL where AI may prepare but not finalize

### 14.13 Non-human default restrictions
Non-human actors may act only if:
- they are recognized Parties/agents allowed by governance
- they hold explicit authority for the requested action class
- the requested action class is allowed for non-human actors

The following action areas remain human-governed by default:
- REVIEW_ACCEPT
- REVIEW_REJECT_OR_CONTEST
- REVIEW_SUPERSEDE
- CONTEXT_INSTALL_PACK
- CONTEXT_ACTIVATE_PACK
- CONTEXT_DEACTIVATE_PACK
- OUTPUT_APPROVE_DOCUMENT_ASSEMBLY
- OUTPUT_ATTEST_DOCUMENT_ASSEMBLY
- OUTPUT_FILE_SUBMISSION_ASSEMBLY

### 14.14 Evidence retention
Where something can matter later for inspection, dispute, insurance, subsidy, certification, or buyer claims, the platform must preserve the original evidence source or a durable reference to it.

### 14.15 AuthorizationDecisionTrace
The platform must be able to produce an AuthorizationDecisionTrace showing at minimum:
- acting Party / agent
- requested action class
- target scope/time
- role basis used
- grant basis used
- delegation basis used where relevant
- revocation result
- inheritance mode applied
- decision outcome
- reason for non-allow outcomes where relevant

### 14.16 Portable attestation readiness
Portable attestations and verifiable claims are a reasonable future direction, but v2 does not require a full credential ecosystem.

---

## 15. Deployment, evolution, and testability


### 15.1 No backward-compatibility obligation
OFARM Platform has no obligation to preserve OFARM 1.x APIs, names, or structures.

### 15.2 Interoperability tooling remains required
“No compatibility obligation” does **not** mean “no mappings, no import/export, no migration tooling from outside systems.”

The platform must provide the tooling required to support the import/export and mapping surfaces it declares.

### 15.3 Minimum conformance and testability baseline
The platform requires at minimum:
- mapping round-trip tests for declared mapping surfaces
- MappingCoverageStatement and LossMap schema validation tests
- mapping coverage/loss consistency tests
- import-surface promotion-posture tests
- RuntimeSurfaceContract schema validation tests
- SemanticSubstrateBundle schema validation tests
- pack compatibility tests
- pack activation-set tests
- deterministic conflict-handling tests
- surface-family merge-mode legality tests
- merge-resolution trace tests
- vocabulary-binding merge fixtures
- evidence-policy merge fixtures
- template-constraint merge fixtures
- decision-rule merge fixtures
- event-subtype merge fixtures
- view/document shaping merge fixtures
- authority action-class decision tests
- scope-inheritance-mode tests
- delegation/revocation tests
- sharing-boundary tests
- AI-assisted decision tests
- non-human restriction tests
- AuthorizationDecisionTrace tests
- authorization/materialization/query/publication request/result envelope tests
- QuerySpecification schema validation tests
- QueryPlanIR schema validation tests
- ContextSnapshot schema validation tests
- MaterializationBasis-to-ContextSnapshot reference consistency tests
- path-alias resolution and alias-version stability tests
- alias-resolution trace tests
- query-plan equivalence tests across execution targets
- enforcement-gate sequencing tests
- projection trace-back tests
- current-state freshness tests
- invalidation-trigger tests
- high-consequence recomputation/refusal tests
- EvidenceSufficiencyCase schema validation tests
- Compliance-versus-Advisory materialization-policy tests
- compiled-output taxonomy tests
- passport-vs-document separation tests
- Capability Manifest schema validation tests
- capability-manifest registry-relation tests
- manifest-to-active-artifact-set consistency tests
- capability-manifest to RuntimeSurfaceContract reference consistency tests
- capability-manifest to SemanticSubstrateBundle consistency tests
- capability-manifest to ConformanceClaimSet consistency tests
- agronomic observation/measurement carrier validation tests
- agronomic intervention intent and execution/as-applied separation tests
- agronomic partial extent and geometry-basis validation tests
- agronomic identity-binding and code-binding-profile tests
- agronomic reconstruction policy and trace tests across query execution, PassportView, and DocumentAssembly
- high-consequence agronomic output refusal tests for stale state, unresolved identity, insufficient evidence, weak geometry, and active disputes

### 15.4 Deeper conformance and operational hardening
The platform should grow toward:
- broader compatibility fixtures
- golden datasets
- broader regression suites
- wider partner-facing verification fixtures
- richer operational observability and recovery drills

### 15.5 Future-direction capabilities
The platform should stay ready for:
- richer simulation services
- public expert-query exposure after the internal model proves stable
- broader agent/tool interoperability
- more formal trust and credential exchange
- larger regional intelligence networks under governance

---

## 16. Glossary

### EnforcementGate
A runtime checkpoint that must be passed before a certain class of authoritative outcome is allowed.

### EnforcementChain
The ordered set of relevant gates a path crosses before it may affect authoritative outcomes.

### QuerySpecification
The runtime input artifact representing a governed semantic retrieval request and required to validate against the formal QuerySpecification schema.

### QueryPlanIR
The internal runtime planning representation derived from QuerySpecification before execution and required to validate against the formal QueryPlanIR schema.

### SemanticPathAlias
A governed path shorthand resolved against current archetype/template structures under a versioned alias-resolution contract.

### Capability Manifest
Machine-readable runtime self-description contract for a deployment or tenant.

### CapabilityManifestRegistryRelation
The manifest block that ties capability claims to manifest registry, artifact registry, active artifact set, and discovery visibility.

### PackActivationSet
A concrete runtime scope/time activation context used to evaluate pack compatibility.

### PackSurfaceFamily
A runtime-relevant classification of the overlapping artifact surface family.

### PackSurfaceMergeMode
A runtime-relevant governed merge mode allowed or forbidden for a given surface family.

### PackMergeResolutionTrace
A traceable runtime record of how pack overlap was resolved or why it failed.

### AuthorityActionClass
A runtime-governed action class against which authorization is evaluated.

### ScopeInheritanceMode
A runtime-enforced inheritance mode controlling whether a grant applies only to the exact scope, descendant scopes, derived-lineage scopes, or not beyond the granted scope.

### AuthorityGrant
A runtime-enforced scoped grant of one or more authority families and/or action classes.

### AuthorizationDecisionTrace
A runtime trace explaining why a requested action was allowed, denied, review-required, or human-approval-required.

### DelegationGrant
A runtime-enforced explicit bounded delegation of authority.

### SharingGrant
A runtime-enforced explicit visibility/use grant distinct from write/review/decision authority.

### event family
One of the fixed constitutional top-level semantic event categories.

### accepted event consequence
A governed event consequence allowed to affect current-state materialization.

### current-state materialization
A governed current-state answer derived from the canonical substrate for a declared twin, scope, time policy, and context basis.

### ContextSnapshot
A governed resolved context-basis object identifying the active interpretation posture for a declared twin, scope, and evaluation time policy.

### MaterializationBasis
The traceable basis from which a current-state materialization was generated.

### MaterializationSnapshot
A durable recorded generation of current-state materialization retained because later traceability matters.

### freshness state
A governed state such as FRESH, STALE, or INVALID indicating whether a materialization is still usable for a declared purpose.

### PassportView
Portable scope-centric compiled view derived from canonical truth through query and view logic.

### DocumentAssembly
Frozen governed compiled output with derivation trace and optional attestation.

### DossierAssembly
Evidence-rich DocumentAssembly subtype for inspection, case, audit, or claim contexts.

### SubmissionAssembly
Formal filing/delivery DocumentAssembly subtype.


### AgronomicObservationContext
Runtime carrier for structured agronomic observation context; it is validated and promoted only through the normal gates.

### MeasurementEvidence
Runtime carrier for sampled, measured, sensed, lab-derived, or imported agronomic evidence and its quality context.

### InterventionIntentPayload
Runtime payload for recommendation, prescription, planned operation, cancellation, or supersession intent.

### ExecutionRecordPayload
Runtime payload for operation claim, as-applied evidence, accepted execution detail, correction, or dispute.

### PartialExtent
Runtime carrier for a spatial slice with geometry basis, quality, evidence, and durable-identity posture.

### AgronomicIdentityBinding
Runtime binding from local agronomic subject to scheme, registry, code list, or profile-scoped identifier.

### AgronomicCodeBindingProfile
Runtime profile declaring allowed/required agronomic schemes, roles, evidence floors, unresolved-binding behavior, and merge posture.

### AgronomicReconstructionPolicy
Runtime query/output policy for high-consequence agronomic reconstruction.

### AgronomicReconstructionTrace
Runtime explanation trace for an agronomic query or output reconstruction decision.

---

## ONT-SEMINT baseline harmonisation addendum — 2026-05-14

**Status:** active platform-runtime harmonisation of ONT-SEMINT Phases 0 through 5.  
**Scope:** runtime gates and output behavior only; no new truth model.

### ONT-SEMINT-P.1 Semantic-conformance gate

Runtime self-description, conformance claims, and output gates must distinguish `SCHEMA_VALID` from `HIGH_CONSEQUENCE_OUTPUT_ELIGIBLE`. A deployment may not claim high-consequence output eligibility unless applicable reference resolution, authority, evidence, freshness, pack/profile, materialization, alias, external-currentness, dispute/correction, and publication/export checks have passed or produced a governed review/refusal disposition.

### ONT-SEMINT-P.2 Reference-resolution gate

The enforcement chain now includes a reference-resolution gate for high-consequence use. The gate must produce or consume a `ReferenceResolutionManifest` and `ReferenceResolutionReport` when package-local or externally anchored references contribute to an output, materialization, review, export, or compliance result.

Package-local reference failures must block or require review according to policy. Externally anchored references may remain declared/informational, but they may not support high-consequence current truth unless the relevant profile supplies snapshot and verification support.

### ONT-SEMINT-P.3 Carrier canonicalization gate

Agronomic carrier validation must treat `agronomicIdentityBindingRefs` and `agronomicCodeBindingProfileRef` as canonical for agronomic identity-binding and code-profile governance. `identityBindingRefs` and `codeBindingProfileRef` are compatibility fields. When both canonical and compatibility fields are present, the runtime must confirm equivalence or route the record to review/refusal according to consequence level.

### ONT-SEMINT-P.4 Temporal conformance gate

The validation and review/promotion gates must reject or review high-consequence records that collapse materially different time meanings. Offline and delayed-sync flows must preserve occurrence/execution time, capture time, assertion time, sync time, review time, correction/dispute time, materialization time, and output time when those distinctions are relevant.

### ONT-SEMINT-P.5 High-consequence query/output gate

For high-consequence Compliance Twin, PassportView, DocumentAssembly, regulated submission, publication/export, or reconstruction-policy-bound use, query execution must require version-pinned semantic aliases through `aliasVersionRef` and an alias-resolution trace.

The publication/export gate must combine:

- reference-resolution report;
- alias-resolution trace;
- reconstruction policy and trace;
- materialization freshness check;
- code-binding status/currentness check;
- geometry and partial-extent policy check;
- correction/dispute policy check;
- evidence-sufficiency outcome;
- authority decision outcome;
- external-registry verification trace where profile-required.

If any required gate is unresolved, stale, ambiguous, conflicting, or unavailable, the runtime must produce `REQUIRE_REVIEW`, `REFUSE_OUTPUT`, or another explicit policy-declared disposition. It must not silently publish, export, or materialize a high-consequence result.

### ONT-SEMINT-P.6 External registry currentness gate

For profile-governed external registry use, the runtime must evaluate `ReferenceSnapshot` and `ExternalRegistryVerificationTrace` before allowing high-consequence output. The Belgium crop-protection currentness profile is the current package-local exemplar: Belgian Phytoweb authorisation-number binding is the required jurisdictional product-authorisation checking surface for the profile; product name, GTIN, EU active-substance status, vocabulary codes, and other adjunct signals are not enough by themselves.

When a registry is stale, unavailable, wrong-jurisdiction, ambiguous, not snapshotted, not accessed-at, or inconsistent with prescription/as-applied identity, the runtime must fail closed or require review according to profile. DocumentAssembly may annex the verification failure and evidence trail; PassportView must not present the result as accepted current compliance.

### ONT-SEMINT-P.7 Capability Manifest honesty

Capability Manifest and conformance output must state which semantic-conformance levels are supported. Claims must separately identify schema validation, package-local reference resolution, external-reference declaration, external-reference verification, runtime policy gates, high-consequence output eligibility, live registry integration, and production runtime evidence. Absence of live registry integration or production evidence must remain visible and must not be inferred from package-local fixtures.

### ONT-SEMINT-P.8 Runtime non-claims

This harmonisation does not claim production runtime readiness, live external registry integration, live Phytoweb integration, legal advice, external-standard readiness, wire-level interoperability closure, or livestock scope expansion.

### ReferenceResolutionManifest
Runtime policy object declaring how references are resolved for a scope, package, query, materialization, or output gate.

### ReferenceResolutionFinding
Runtime finding for a single resolved, unresolved, stale, aliased, externally declared, externally verified, or review-required reference.

### ReferenceResolutionReport
Runtime report aggregating reference-resolution findings and output eligibility consequences.

### TemporalFieldConformanceMatrix
Runtime-supporting matrix used to validate that record classes preserve distinct temporal meanings.

### ExternalRegistryVerificationTrace
Runtime gate-support trace for profile-governed external registry/source currentness checks.

---

## ONT-SEMINT v0.3 runtime-enforcement baseline addendum — 2026-05-14

Status: active runtime baseline law harmonising accepted ONT-SEMINT semantic-integrity closures.

This addendum extends the runtime enforcement chain without changing the model/runtime split or the assertion/history-first substrate.

### A. Semantic-conformance enforcement chain

For high-consequence use, the platform enforcement chain must treat schema validation as necessary but insufficient. Runtime enforcement must be able to distinguish:

- schema validation;
- package-local reference resolution;
- declared external references;
- verified external references under a profile;
- policy-gate passage;
- high-consequence output eligibility.

### B. Reference-resolution gate

Before a high-consequence materialization, publication/export, PassportView, DocumentAssembly, filing, or compliance result relies on referenced artifacts, the runtime must either resolve required package-local references to expected classes or produce a governed review/refusal outcome.

A `ReferenceResolutionReport` or equivalent runtime trace must be retained when the output depends on reference resolution.

Externally anchored references are not automatically runtime-valid merely because they appear in a schema-valid object. They must be handled according to role: semantic anchor, code binding, exchange mapping, runtime surface, evidence source, or attestation wrapper.

### C. Agronomic carrier-field and temporal gates

For agronomic carriers, the runtime must prefer canonical agronomic reference fields over compatibility fields and must detect conflicts between them. Conflicts must require review or fail closed according to consequence level.

For delayed sync, disputed records, correction records, as-applied claims, and high-consequence outputs, the runtime must preserve material time distinctions. Captured time, assertion/record time, occurrence/execution time, effective time, review/correction/dispute time, materialization time, and output time must not be substituted for one another without an explicit policy-supported derivation.

### D. Query alias and reconstruction gate

For Compliance Twin, PassportView, DocumentAssembly, regulated submission, publication/export, or reconstruction-policy-bound use, the runtime must require version-pinned or traceably resolved aliases. A stale, unpinned, ambiguous, or unresolved alias must block output or require review according to policy.

High-consequence agronomic outputs must have reconstruction policy and trace support sufficient to show truth scope, effective-as-of policy, knowledge cut, evidence floor, freshness posture, geometry/partial-extent posture, dispute/correction posture, code-binding posture, and output disposition.

### E. External-registry currentness gate

When an active profile requires external registry currentness, the runtime must obtain or reference sufficient `ReferenceSnapshot` and `ExternalRegistryVerificationTrace` evidence before allowing high-consequence output.

For the Belgium/Phytoweb crop-protection authorisation profile, a current-compliance PassportView must not pass on free-text product name, commercial GTIN, EU active-substance evidence alone, wrong-jurisdiction evidence, stale or missing access-date evidence, registry-unavailable evidence, or mismatched prescription/as-applied product identity.

If the required registry check is unavailable at output time, PassportView must refuse or require review according to policy. DocumentAssembly may annex the failure trace when allowed, but the annex must not promote the failed or unresolved material into accepted truth.

### F. Capability Manifest and conformance honesty

Capability Manifest and conformance claims must distinguish schema validation, package-local reference resolution, external registry verification, runtime policy-gate coverage, and high-consequence output eligibility.

A deployment must not claim live external registry verification, production readiness, broad external-standard readiness, livestock coverage, or legal-advice status unless separate evidence supports that claim.

---

## Agentic AI runtime-safety clarification addendum — 2026-05-14

Status: active runtime baseline-law clarification for pre-implementation agentic AI and world-model readiness.

This addendum extends the runtime safety posture without claiming an implemented agent runtime. CP4 promotes the bounded `AgentRunEnvelope`, `AgentRunTrace`, `AgentToolInvocationTrace`, `AgentOutputDisposition`, `AgentBlockedActionTrace`, `AgentHandoffEnvelope`, `AgentRunInputBundle`, `AgentRunStopCondition`, `AgentRunApprovalCheckpoint`, and `AgentRunFreshnessRequirement` contract subset. CP5 promotes a bounded `AgentToolManifest` and capability/tool manifest-honesty subset. It still does not promote `WorldModelRun`, `WorldModelState`, or related world-model/request schemas into active machine-contract law.

### AAI-P.1 Governed public surfaces only

AI-agent-facing operations must pass through governed runtime surfaces and enforcement gates. Agents and applications may not directly mutate canonical history stores, materialization stores, authority decisions, pack activation state, publication records, sharing grants, or attestation/submission records except through explicitly governed operations that produce traceable results.

A public operation descriptor, SDK method, application workflow, tool manifest entry, or API endpoint does not relax baseline truth, evidence, authority, pack, query, materialization, publication, or sharing law.

### AAI-P.2 Enforcement before tool success

Tool-call success, HTTP success, schema-shape validity, public-operation success, UI workflow completion, or model confidence is not governance success.

For state-affecting or high-consequence use, the platform must still qualify whether the relevant authority, evidence, validation, pack/profile applicability, materialization freshness, review/promotion, reference-resolution, output-disposition, and sharing/publication gates passed.

#### AAI-P.2.1 Sponsor-bound software-agent authority gate

As of AAI-CP3, a software-agent operation is release-eligible for state-affecting or high-consequence use only when the runtime can resolve and record the sponsor-bound actorship posture for the specific action. The runtime must identify the accountable sponsor, executing agent instance, software-agent profile, model/tool profile basis, requested AuthorityActionClass, target scope, twin context, authority snapshot, revocation state, authorization decision, and result qualification linkage.

A model identifier, tool identifier, product feature, API key, prompt, session, capability descriptor, or successful public-operation call is not authority. If sponsor, authority snapshot, revocation check, action-class posture, or human-approval posture is missing or expired, the permitted runtime outcome is deny, require review, require human approval, or another policy-declared blocked disposition.

### AAI-P.3 Preflight and dry-run side-effect boundary

A preflight, dry-run, preview, explanation, or agent plan may compute likely gate outcomes and produce reason codes, but it must not by itself create accepted assertions, activate packs, finalize current-state materialization, approve compiled outputs, create compliance facts, sign/attest, file submissions, grant sharing, revoke authority, or consume a scarce governed resource unless a later active RFC explicitly defines such an effect.

### AAI-P.4 Agent session, memory, and handoff boundary

Agent session state, model memory, chain-of-agent scratchpads, and handoff context are not canonical truth and are not current-state materialization.

A handoff between agents may carry task context, but it may not silently transfer authority, sharing permission, approval status, evidence sufficiency, or freshness posture. A receiving agent or tool path must independently satisfy the applicable enforcement gates before any state-affecting action.

As of AAI-CP4, a state-affecting, high-consequence, or multi-step software-agent run must be bounded by an `AgentRunEnvelope`, recorded by an `AgentRunTrace`, and linked to trace retrieval and result qualification. Tool invocations must separate execution outcome from governance outcome. Blocked actions must emit retrievable blocked-action traces. Output produced by a run must carry explicit output disposition. `AgentHandoffEnvelope.authorityTransferred` remains false in this CP4 layer; the receiving agent must reauthorize and revalidate sponsor, authority, revocation, action-class posture, freshness, evidence, sharing, pack/profile, and result-qualification posture before acting.

### AAI-P.5 Advisory world-model runtime boundary

World-model runs, simulation states, scenario states, and advisory digital-twin states must execute inside the Advisory Twin posture unless a specific governed bridge is invoked.

A world-model output may produce hypotheses, risk flags, scenario results, draft plans, evidence requests, observation requests, review prompts, or BridgeCandidates. It must not directly produce accepted Compliance Twin facts, accepted execution consequences, official attestation, filed submissions, or hidden current state.

### AAI-P.6 Result qualification for AI-facing answers

AI-facing answers, daily briefs, summaries, tool results, and generated documents must preserve material result qualifications. At minimum, high-consequence or state-affecting results must not hide:

- stale or uncomputed materialization basis;
- permission-limited answer posture;
- unresolved reference or alias posture;
- external-currentness uncertainty where a profile requires it;
- evidence insufficiency;
- authority denial or approval requirement;
- disputed/corrected/superseded status;
- Advisory-only status;
- BridgeCandidate proposal-only status;
- publication/export/output-disposition limits.


#### AAI-P.6.1 AI-facing release qualification gate

A runtime, app, API, public operation, agent tool, daily brief, generated document, or compiled-output preparation flow must not be released for state-affecting or high-consequence use unless it can emit a machine-readable release qualification that is also visible or otherwise faithfully represented to the intended user or downstream system.

For each relevant result, the release qualification must identify the result basis and, where applicable, material limitations across freshness, authority, evidence, reference resolution, external currentness, pack/profile applicability, dispute/correction/supersession, Advisory-only or BridgeCandidate status, sharing/redaction/permission limits, output disposition, and blocked or review-required gates.

If a platform cannot produce or retrieve the required qualification for a material limitation, the permitted outcome for state-affecting or high-consequence use is `REQUIRE_REVIEW`, `REFUSE_OUTPUT`, or another policy-declared successor disposition. Free-text explanation alone is not sufficient when the user, another system, or an agent could treat the result as operational or compliance-ready.

Low-consequence exploratory or explanatory surfaces may use proportionate qualification, but they must still not hide a limitation that would change a farm operation, compliance posture, sharing decision, publication/export decision, or compiled-output disposition.

This gate hardens AAI-P.6. CP2 separately promoted `ResultQualificationEnvelope`, `TraceRetrievalResult`, `PublicOperationDescriptor`, `PreflightResult`, and related public-surface schemas as active machine contracts. CP3 separately promotes the sponsor-bound actorship contract subset. CP4 separately promotes the bounded run, trace, blocked-action, output-disposition, and handoff contract subset. CP5 separately promotes bounded capability/tool manifest honesty contracts. This gate still does not promote world-model runtime, EvidenceNeed, ObservationRequest, autonomous compliance decisioning, or two-agent compatibility.

### AAI-P.7 Capability and tool-manifest honesty

Capability manifests, tool manifests, public-operation catalogs, and conformance claims must distinguish supported runtime behavior from aspirational design. A deployment must not claim multi-agent readiness, two-agent compatibility, world-model compliance readiness, autonomous compliance decisioning, production readiness, or external-standard readiness unless separate implementation evidence and conformance execution support that claim.

#### AAI-P.7.1 CP5 capability/tool manifest honesty gate

As of AAI-CP5, a runtime may expose active manifest/tool self-description contracts only as governed description surfaces. The runtime must not treat a manifest, tool descriptor, model/tool profile, capability overlay, API catalog, declared hint, external protocol card, or vendor claim as authority, approval, safety proof, evidence sufficiency, pack activation, publication/export approval, or governance success.

For AI-agent-facing operations, every callable tool or public operation described through `AgentToolManifest` or `AgentToolDescriptor` must separate at least:

- tool identity and publisher/source identity;
- input and output schema references and hashes;
- side-effect/effect class and target state surface;
- data classes in and out;
- authentication mode, required scopes, and external-call posture;
- approval requirement and semantic preconditions;
- trace-retention and blocked-action trace expectations;
- redaction and permission-limited result policy;
- data-learning or memory-use posture;
- declared hints and their non-authoritative status;
- readiness claims, evidence references, expiry, and public-claim limits.

If manifest metadata conflicts with policy, runtime observation, authority posture, trace evidence, result qualification, sharing policy, or active baseline law, the runtime must fail closed by denying, requiring review, requiring human approval, or emitting a qualified/blocked result. A successful tool invocation remains separate from a successful governance outcome.

CP5 is not runtime AI-agent readiness, two-agent compatibility, production readiness, autonomous compliance decisioning, world-model readiness, live registry integration, legal advice, or external-standard readiness.

### AAI-P.8 Runtime non-claims

This clarification does not claim that OFARM has an implemented multi-agent runtime, world-model runtime, live external tool chain, production API, two-agent compatibility proof, or autonomous compliance decisioning capability. It only fixes the baseline safety envelope for later agentic implementation work.

## AAI-CP7 advisory world-model runtime-surface addendum — 2026-05-16

As of AAI-CP7, platform runtimes may expose and validate bounded Advisory Twin world-model contracts, but release-eligible public or AI-facing use must preserve CP1/CP2 result qualification.

The runtime must treat world-model material as advisory unless a separately accepted bridge and normal OFARM governance gates authorize a harder use. A `WorldModelRun` or `WorldModelState` must not mutate current state, must not bypass Compliance Twin promotion law, and must not be shown as complete operational or compliance truth without visible advisory-only, uncertainty, validity, invalidation, reconciliation, freshness, and output-disposition qualification.

CP7 does not claim implemented world-model runtime readiness, production readiness, autonomous compliance decisioning, or external-standard readiness.

## AAI-CP8 request-layer runtime-surface addendum — 2026-05-16

As of AAI-CP8, platform runtimes may expose and validate bounded request-layer contracts for EvidenceNeed, ObservationRequest, and farmer-burden/noise/display control, but release-eligible public or AI-facing use must preserve CP1/CP2 result qualification.

A runtime must not treat request creation, request display, request completion, or request satisfaction as accepted evidence, accepted assertion, compliance obligation, or governance success. Any blocking posture must cite a separate `RequestBlockingBasis` tied to an external rule or gate. Request satisfaction must route through ordinary evidence, authority, quality, review, promotion, and dispute gates before any accepted evidence or compliance consequence is created.

Farmer-facing request surfaces must expose why the request exists, what it blocks, what it does not block, priority, burden, relevance window, completion criteria, acceptable alternatives, privacy/safety notes where applicable, decline/defer posture, and visible stale/advisory/permission/evidence/dispute qualifications.

CP8 does not claim farmer UX readiness, production readiness, autonomous compliance decisioning, minimum capture profile sufficiency, or external-standard readiness.


## CP11 Sustainable Autonomous Farming Charter runtime-enforcement addendum — 2026-05-21

Status: active runtime baseline-law harmonisation candidate for CP11 once `OFARM_Sustainable_Autonomous_Farming_Charter_RFC_v0_1.md` is accepted.

This addendum extends the runtime enforcement posture for charter-sensitive recommendations, plans, outputs, claims, agent runs, exceptions, breaches, and pack/profile activations. It does not create a separate sustainability runtime, separate truth store, separate decision store, or cyber-physical execution authority.

### CP11-P.1 Charter-sensitive runtime surface

A runtime surface is charter-sensitive when sustainability constraints, optimisation objectives, evidence obligations, claim rules, exceptions, breaches, sustainability-disclosure limits, or future autonomous-operation hooks materially affect the result.

Charter-sensitive surfaces include, where applicable:

- sustainability-sensitive recommendations;
- sustainability-sensitive intervention plans;
- high-consequence plans with soil, water, biodiversity, chemical/input, erosion, residue, emissions, habitat, or charter constraints;
- sustainability scenario outputs intended for reliance beyond exploratory use;
- sustainability claim-bearing PassportViews, DocumentAssemblies, DossierAssemblies, SubmissionAssemblies, exports, dashboards, summaries, daily briefs, generated documents, and AI-facing outputs;
- charter exception or breach workflows;
- agent runs that prepare, evaluate, request approval for, or output charter-sensitive material;
- pack/profile activation that changes sustainability constraints, objectives, evidence rules, claim rules, trade-off rules, exception rules, or breach rules.

### CP11-P.2 Charter applicability gate

For a charter-sensitive use, the runtime must resolve the applicable `SustainableFarmingCharter` and `CharterApplicabilityContext` before presenting the result as operationally reliable, claim-ready, Compliance Twin eligible, execution-bound, or approved.

The applicability resolution must consider the relevant scope, time, target twin, output disposition, active pack/profile set, authority context, intended use class, and any governed external standard or certification reference admitted by profile.

If the applicable charter or applicability context cannot be resolved, the permitted runtime outcome is `REQUIRE_REVIEW`, `REQUIRE_HUMAN_APPROVAL`, `ADVISORY_ONLY`, `REFUSE_OUTPUT`, `REFUSE_ACTION`, or another policy-declared blocked disposition. It must not pass silently.

### CP11-P.3 Charter policy-evaluation gate

For a charter-sensitive use, the runtime must evaluate applicable hard constraints, objectives, objective priorities, trade-off policy, evidence requirements, approval gates, claim-basis rules, exception rules, and breach rules at the relevant consequence level.

The runtime must produce or link to a `SustainabilityPolicyEvaluationTrace` where the charter evaluation materially affects recommendation, review, approval, output, claim, exception, breach, pack activation, or future execution-bound packaging.

A charter evaluation trace records gate evaluation. It is not canonical farm truth, not evidence sufficiency by itself, not authority, not approval, not a Compliance Twin fact, and not proof of execution.

### CP11-P.4 Runtime outcomes

Where CP11 gates apply, the runtime must distinguish at least these outcomes:

- allowed;
- allowed with qualification;
- advisory-only;
- evidence-needed;
- require review;
- require human approval;
- blocked by hard constraint;
- blocked by stale or invalid current-state materialisation;
- blocked by insufficient claim basis;
- blocked by unresolved pack/profile conflict;
- exception path required;
- refused output;
- refused action.

A runtime may use implementation-specific reason codes, but they must preserve the material distinction among evidence failure, authority failure, freshness failure, hard-constraint failure, claim-basis failure, pack/profile conflict, and advisory-only limitation.

### CP11-P.5 Current-state and evidence coupling

A charter-sensitive result that materially relies on current-state materialisation must satisfy the existing high-consequence freshness rule. Stale, invalid, uncomputed, disputed, or insufficiently based materialisation must trigger recompute, review, human approval, refusal, or visible qualification according to policy.

Model confidence, AI fluency, tool-call success, public-operation success, or schema-shape validity is not sustainability evidence sufficiency and is not charter compliance.

### CP11-P.6 Sustainability claim output gate

A runtime must not emit, freeze, export, file, attest, or present as claim-ready a sustainability claim unless the relevant `SustainabilityClaimBasis` is present and the output exposes required `SustainabilityOutputQualification`.

Where the claim basis is missing, insufficient, stale, disputed, modelled-only, inferred-only, permission-limited, or review-required, the result must expose that limitation or refuse the stronger output disposition.

### CP11-P.7 Agent-run integration

A sustainability-sensitive software-agent run must preserve CP3, CP4, and CP5 agent law. It must link the relevant `AgentRunEnvelope`, `AgentRunTrace`, `AgentOutputDisposition`, `AgentBlockedActionTrace`, tool invocation trace, approval checkpoint, freshness requirement, and result qualification to the CP11 charter evaluation where the charter materially affects the run.

An agent may evaluate, recommend, simulate, explain, request evidence, prepare a review package, or propose a charter-sensitive output inside its authority envelope. It may not approve charter exceptions, change objective priority, activate charter packs, attest sustainability claims, create Compliance Twin facts, or authorise physical execution unless later active law explicitly grants that bounded action class.

### CP11-P.8 Pack/profile runtime interaction

When pack/profile activation touches sustainability surfaces, the runtime must evaluate merge legality and conflict posture before use. A conflict that could weaken a hard constraint, hide an evidence requirement, alter claim-basis rules, misrepresent a metric method, change objective priority, relax an exception rule, or conceal a breach posture must fail closed or require governance according to active pack law.

### CP11-P.9 Deferral and non-authorisation

CP11 runtime enforcement does not authorise robot or machine execution. A charter-passing evaluation is not a mission command, not a geofence, not a command signature, not an emergency-stop policy, not local fallback, not execution verification, and not a physical-safety proof.

CP11 runtime enforcement does not authorise autonomous experimentation, farm-to-farm intelligence exchange, or generated-software deployment. Those require later controlled amendments.

### CP11-P.10 Runtime non-claims

This addendum does not claim implemented production sustainability governance, autonomous sustainability decisioning, robot/machine execution readiness, external sustainability-standard readiness, live registry integration, legal/certification advice, farm-to-farm intelligence readiness, or generated-software deployment readiness.

## CP12 Cyber-Physical Mission Envelope runtime-enforcement addendum — 2026-05-28

Status: merged runtime baseline addendum for CP12.

CP12 adds a runtime gate for mission-sensitive use. It does not add production robot readiness, machine-control readiness, autonomous field-operation readiness, fleet optimisation, safety certification, legal advice, insurance advice, livestock mission readiness, or vendor-protocol completeness.

For mission-sensitive use, runtime implementations must be able to resolve the active cyber-physical mission envelope and mission stage; distinguish mission intent, candidate, plan, preflight, dispatch authorisation, command envelope, acknowledgement, telemetry, execution receipt, verification, and accepted execution consequence; enforce mission authority action classes through ordinary authority/default-deny law; evaluate current-state freshness and materialisation basis for mission dispatch; evaluate CP11 charter preconditions where material; evaluate geometry basis, geofence, no-go-zone, route, and execution-window coherence; evaluate actor capability, safety constraints, autonomy posture, emergency-stop, human-override, local-fallback, lost-link, and remote-takeover posture; require command integrity, expiry, recipient binding, payload binding, dispatch-authorisation binding, and replay-protection posture for dispatchable command envelopes; preserve telemetry and execution receipts as evidence candidates, not accepted execution truth by themselves; require mission verification before verified-completion or accepted-execution claims; represent abort, emergency-stop, fallback, remote-takeover, near-miss, and physical-safety incident records without automatically creating legal or Compliance Twin facts; and qualify mission outputs according to mission stage, evidence, verification, authority, safety, and allowed/prohibited use.

Physical mission authority is not produced by recommendation, plan, preflight success, CP11 charter pass, agent confidence, tool invocation success, machine capability declaration, command acknowledgement, telemetry receipt, or adapter output alone. Mission dispatch requires explicit CP12 mission envelope, authority trace, safety envelope, command integrity, and applicable preflight/current-state/charter gates.

### CP12-P.1 Mission-envelope and cyber-physical safety gate

For mission-sensitive use, the platform must resolve the applicable `CyberPhysicalMissionEnvelope` and mission stage before command creation, command dispatch, telemetry acceptance as evidence candidate, mission verification, or accepted execution consequence. The gate must evaluate mission identity and lifecycle state, authority action and trace, mission preflight result, CP11 charter precondition result, current-state freshness, mission geometry basis, geofence/no-go-zone constraints, execution window, actor capability, mission safety constraints, autonomy level, emergency-stop policy, human-override policy, local fallback and lost-link policy, command envelope integrity, command expiry, replay-protection, external adapter mapping coverage/loss posture, and mission output qualification where applicable.

A pass through this gate is not by itself accepted execution truth. Accepted execution consequences require ordinary OFARM evidence, review, promotion, and current-state law.

### CP12-P.2 AI and agent mission-preparation boundary

AI-generated mission candidates, plans, simulations, route suggestions, geofence proposals, safety checks, or command-envelope drafts enter the same enforcement architecture as other mission-sensitive inputs. A software agent may prepare a mission candidate, request mission preflight, run advisory mission simulations, identify required evidence or current-state gaps, prepare review or dispatch packages, emit blocked-action traces, and prepare command-envelope candidates for review. A software agent may not by default approve mission dispatch, dispatch a command, perform emergency-stop override or remote takeover, accept mission verification, accept execution consequences, resolve physical-safety incidents, or treat tool success, vendor acknowledgement, or model confidence as physical mission success.

### CP12-P.3 Mission simulation, command, telemetry, and output boundaries

Mission simulations, route simulations, safety simulations, autonomy simulations, actor-capability simulations, and execution-window simulations belong to the Advisory Twin by default. They may inform preflight, reveal blockers, request evidence, prepare mission candidates, compare alternatives, or support review. They may not directly create mission dispatch authority, command envelopes, command dispatch, accepted execution truth, Compliance Twin facts, safety certification, or output claims.

A command envelope, command acknowledgement, telemetry envelope, execution receipt, vendor log, robot log, drone log, machinery payload, or adapter response is not canonical truth by itself. Telemetry and execution receipts are evidence candidates. Mission verification and accepted execution consequences require ordinary OFARM evidence, authority, review, promotion, current-state, and output law.

A mission output must disclose mission stage, dispatch-authorisation posture, command-envelope posture, command-acknowledgement posture, telemetry and receipt posture, verification posture, accepted-execution consequence posture, current-state freshness, geometry basis, CP11 charter posture where applicable, authority and approval posture, incident/abort/fallback/near-miss/safety limitations, and allowed and prohibited downstream uses. A mission summary is not proof of execution merely because it is generated from telemetry, vendor logs, a command acknowledgement, or an AI summary.

CP12 runtime support remains implementation-directed with bounded debt until CP12 machine contracts are explicitly promoted from draft/non-default, runtime evidence exists, and conformance evidence remains passing.

## CP13 Learning, Experimentation, and Farm Memory runtime-enforcement addendum — 2026-05-29

Status: merged controlled runtime addendum for accepted `OFARM_Learning_Experimentation_and_Farm_Memory_RFC_v0_1.md`.

CP13 adds a runtime learning-governance gate for learning-sensitive use. It does not add autonomous self-improvement, farm-to-farm intelligence, model/software deployment authority, or production agronomic-advice certification.

### CP13-P.1 Learning-sensitive runtime surface

A runtime path is learning-sensitive when learning artifacts, experiment results, causal estimates, farm memory, seasonal summaries, agent/model learning, or learning-derived recommendations may materially affect recommendation, planning, review, claim, mission preparation, output, publication, export, or future high-consequence reliance.

Learning-sensitive paths must not write directly to canonical truth, current-state materialisation, Compliance Twin fact, mission authority, claim basis, or deployment authority.

### CP13-P.2 Learning governance gate

For learning-sensitive use, the platform must be able to resolve the applicable `LearningScope` and determine whether the use involves:

- hypothesis creation;
- experiment protocol or trial-design creation;
- outcome-measure definition;
- outcome observation grouping;
- evidence bundling;
- causal estimation;
- learning evaluation;
- learning promotion;
- farm-memory entry creation;
- farm-memory retrieval;
- seasonal learning summary;
- learning output;
- CP11 risk/regret budget use;
- CP11 charter-sensitive learning use;
- CP12 mission/operation evidence use;
- CP14 or CP15 boundary crossing.

The gate must emit or link a `LearningEvaluationTrace` where the outcome affects promotion, farm-memory creation, retrieval, high-consequence recommendation, output, review, claim support, CP11 charter-sensitive use, CP12 mission preparation, publication, export, or later CP14/CP15 handoff.

### CP13-P.3 Experiment and protocol non-authorisation

Runtime acceptance of an `ExperimentProtocol`, `TrialDesign`, `RiskBudget`, or `RegretBudget` must not by itself create operation authority, intervention execution truth, CP12 mission dispatch authority, CP11 charter exception, output publication approval, cross-farm sharing approval, or model/software deployment authority.

If the experiment requires a field operation, input application, physical mission, charter-sensitive action, data disclosure, or model/software deployment, the relevant OFARM authority path must be executed separately.

### CP13-P.4 Learning evidence and causal-estimate gate

A runtime path that produces a `CausalEstimate`, `LearningPromotionDecision`, `FarmMemoryEntry`, `SeasonalLearningSummary`, or high-consequence `LearningOutputQualification` must preserve:

- evidence provenance;
- learning scope;
- design and comparison basis;
- outcome-measure posture;
- missingness and bias posture;
- uncertainty;
- current-state reliance where applicable;
- CP11 and CP12 dependencies where material;
- review and promotion posture;
- allowed and prohibited use.

Weak, post-hoc, observational, modelled, or underpowered evidence must not be upgraded to strong causal or experimental support by runtime presentation.

### CP13-P.5 Farm-memory gate

A `FarmMemoryEntry` may be created only through a governed `LearningPromotionDecision` or another later accepted CP13 path. It must carry scope, evidence basis, validity horizon, retrieval qualification, invalidation posture, and prohibited uses.

Farm memory retrieval for learning-sensitive or high-consequence use must produce or link a `FarmMemoryRetrievalQualification`.

Farm memory must not be used as hidden current state, hidden evidence sufficiency, hidden CP11 charter pass, hidden CP12 mission precondition, hidden claim basis, hidden Compliance Twin fact, or hidden authority.

### CP13-P.6 Agent memory and model-learning boundary

Agent memory, vector memory, prompt history, tool-call history, model weights, embeddings, cached summaries, and model-improvement artifacts are not OFARM farm memory.

Software agents may propose learning artifacts, produce analysis, request evidence, draft traces, and recommend promotion only within explicit authority. They may not approve learning promotion, scope expansion, cross-farm use, or model/software deployment by default.

### CP13-P.7 CP11 and CP12 coupling

Where learning-sensitive use materially depends on CP11 charter state, sustainability constraints/objectives, risk/regret budgets, sustainability claims, charter exceptions, or charter breaches, the runtime must preserve CP11 gates and qualifications.

Where learning-sensitive use materially depends on CP12 mission plan, preflight, dispatch, command, telemetry, receipt, verification, abort, near-miss, or physical-safety incident records, the runtime must preserve CP12 stage separation and truth boundaries.

A CP12 mission verification may serve as learning evidence candidate. It does not create learning truth, causal fact, farm memory, or Compliance Twin fact by itself.

### CP13-P.8 Learning output gate

A learning-sensitive output must carry a `LearningOutputQualification` where it may affect recommendation, planning, review, CP11 charter evaluation, CP12 mission preparation, claim support, publication, export, or future high-consequence reliance.

The runtime must prevent learning outputs from being used as truth, claim basis, mission authority, compliance fact, cross-farm shareable intelligence, or deployment authority unless separate OFARM gates explicitly allow the harder use.

### CP13-P.9 Runtime non-claims

Runtime support for CP13 remains implementation-directed with bounded debt until CP13 machine contracts, conformance fixtures, hostile review, implementation evidence, and steward validation exist.

CP13 runtime support does not claim production autonomous self-improvement readiness, production agronomic-advice certification, farm-to-farm intelligence readiness, federated learning readiness, regional alert readiness, model deployment readiness, generated-software readiness, CP14 readiness, or CP15 readiness.


## CP14 Farm-to-Farm Intelligence Boundary runtime addendum — 2026-05-29

Status: accepted/merged CP14 controlled runtime addendum for `OFARM_Farm_to_Farm_Intelligence_Boundary_RFC_v0_1.md`.

CP14 adds a runtime boundary gate for farm-intelligence-sensitive use.

For outbound farm-to-farm intelligence sharing, the platform must resolve:

- data sovereignty boundary;
- sharing grant or lawful/authority basis;
- source farm or contribution scope;
- recipient class;
- permitted purposes;
- prohibited purposes;
- retention posture;
- onward-sharing posture;
- derivative-use posture;
- training-use posture;
- revocation posture;
- redaction/aggregation/deidentification/anonymisation posture;
- re-identification-risk posture where applicable;
- CP11/CP12/CP13 source limitations where material;
- intelligence-output qualification.

For received cross-farm intelligence, the platform must resolve:

- source and provenance posture;
- contribution quality;
- sharing/recipient-use constraints;
- derivative/training-use permissions;
- re-identification and disclosure limits;
- correction, withdrawal, revocation, dispute, poisoning, or anomaly posture;
- cross-farm applicability assessment where local reliance is contemplated;
- Advisory Twin posture by default;
- output and query qualification.

The CP14 gate must prevent received intelligence, regional alerts, benchmark deltas, aggregates, deidentified/anonymised payloads, federated receipts, model-improvement signals, or AI-generated cross-farm summaries from becoming local farm truth, current state, Compliance Twin fact, claim basis, mission authority, farm memory, model deployment authority, or public benchmark authority by default.


### CP14 received-intelligence current-state boundary

Received cross-farm intelligence is not current state.

A `RegionalAlert`, `RegionalRiskSignal`, `BenchmarkDelta`, `FarmIntelligenceContribution`, `LearningArtifactSharePackage`, `FederatedAggregationReceipt`, `ModelImprovementSignal`, `TrainingUseReceipt`, aggregate output, deidentified dataset, anonymised dataset, or AI-generated cross-farm intelligence summary must not update local farm current-state materialisation merely by being received, displayed, queried, or processed.

Where received intelligence materially informs a local recommendation, observation request, review package, BridgeCandidate, CP11 evaluation, CP12 mission preparation, CP13 learning evaluation, or output, the result must preserve the received-intelligence qualification and must not represent received intelligence as local truth unless separately established through OFARM truth and review law.


### CP14 agent-mediated cross-farm intelligence boundary

Software agents may prepare, summarise, qualify, route, compare, request review of, or produce advisory interpretations of farm-to-farm intelligence only under explicit authority, active sharing/use constraints, and CP14 output qualification.

Software agents may not by default:

- approve a FarmIntelligenceShareGrant;
- approve recipient-use expansion;
- approve derivative use;
- approve training use;
- override revocation;
- downgrade re-identification risk;
- approve anonymisation claims;
- publish partner/public benchmark outputs;
- convert received intelligence into local truth;
- create Compliance Twin facts;
- create CP13 farm memory from received intelligence;
- authorise CP12 missions;
- deploy or update models/software.

Agent memory, prompt context, embeddings, vector stores, tool results, retrieval results, generated summaries, or model-improvement signals are not CP14 authority, sharing grants, training-use permissions, anonymisation proof, applicability proof, or truth.


### CP14 intelligence output and query qualification

A query result, dashboard, API response, agent answer, exported file, PassportView, DocumentAssembly, regional alert, benchmark output, model-improvement signal, data-space payload, or partner/public-facing report that contains or materially relies on cross-farm intelligence must carry IntelligenceOutputQualification or an equivalent result qualification.

The qualification must expose Advisory-only status, source type, sharing grant or lawful basis, recipient-use constraints, derivative-use posture, training-use posture, re-identification-risk posture, aggregation/deidentification/anonymisation posture, applicability assessment, uncertainty, limitations, correction/withdrawal/revocation status, and allowed/prohibited downstream uses where material.

An intelligence output must not silently become truth, current state, Compliance Twin fact, claim basis, dispatch authority, farm memory, public benchmark authority, or model deployment authority.


## CP15 Agentic Software Delivery and Model Deployment Governance runtime-enforcement addendum — 2026-05-30

### CP15-P.1 Delivery-sensitive runtime surface

A delivery-sensitive runtime surface is any OFARM runtime surface on which generated software, adapters, mappings, workflows, prompts, policies, model candidates, release bundles, runtime-surface bindings, canary/rollback mechanisms, or deployment tooling can affect governed outputs, current/default state, CP11 charter-sensitive paths, CP12 mission paths, CP13 learning/farm-memory paths, CP14 intelligence paths, Compliance Twin surfaces, public/export surfaces, security/credential/signing-token surfaces, or farmer-facing high-consequence behavior.

### CP15-P.2 Delivery governance gate

For delivery-sensitive use, the runtime must resolve the applicable SoftwareDeliveryBoundary and evaluate:

- artifact identity and lifecycle state;
- agent-generation provenance and agent-run trace;
- build provenance and artifact digest;
- SBOM/dependency/license/use-constraint posture;
- static-analysis and security-scan posture;
- security-finding waiver posture;
- conformance test plan and conformance run receipt;
- semantic mapping and adapter-generation evidence;
- runtime-surface release binding;
- deployment environment scope and blast radius;
- deployment authorization;
- rollback posture;
- canary posture where used;
- deployment promotion decision where promotion is requested;
- applicable CP11, CP12, CP13, and CP14 gate traces;
- output qualification and readiness/non-claim posture.

The gate must emit or link a CP15 delivery evaluation trace where the outcome affects deployment, refusal, qualification, review, promotion, rollback, quarantine, current/default promotion, or publication/export.

### CP15-P.3 Agentic development boundary

Software agents may generate artifacts, produce patches, propose semantic mappings, generate adapters, prepare workflows, run tests, gather evidence, draft release bundles, and prepare review packages where authorised.

Agent tool success, agent confidence, build success, test success, conformance success, security scan success, canary success, or deployment telemetry is not deployment authority, runtime authority, current/default promotion, or production readiness.

A software agent may not by default authorise deployment, waive blocking security findings, approve release bundles, promote current/default artifacts, bind release bundles to stronger runtime surfaces, approve rollback bypass, or declare production readiness.

### CP15-P.4 Deployment and runtime-surface binding

A deployment candidate must declare its runtime-surface target. A release bundle authorised for an advisory sandbox cannot silently run on farmer-facing, Compliance Twin, CP11 charter-sensitive, CP12 mission-adapter, CP13 learning/farm-memory, CP14 intelligence, public/export, or current/default surfaces.

Surface escalation requires explicit deployment authorization, runtime-surface release binding, authority trace, evidence/conformance basis, rollback posture, and output qualification.

### CP15-P.5 Current/default promotion gate

Current/default promotion for schemas, contracts, packs, profiles, policies, prompts, workflows, adapters, models, release bundles, or runtime-surface bindings requires explicit promotion authority and currentness trace.

A CP15 deployment path must not promote CP11, CP12, CP13, CP14, or CP15 draft/non-default schemas to current/default unless a separate currentness-promotion decision exists.

### CP15-P.6 Security, SBOM, dependency, and waiver gate

A high-consequence deployment candidate must expose SBOM, dependency-risk, license/use-constraint, static-analysis, security-scan, and waiver posture where applicable. A blocking or high-severity security finding cannot be waived without explicit SecurityFindingWaiver authority, scope, expiry, evidence, and review trace.

A waiver is not a security proof and does not remove the underlying finding from trace.

### CP15-P.7 Canary, rollback, telemetry, and incident gate

A canary result is evidence, not promotion. A rollback plan is required where deployment failure can affect high-consequence surfaces. Runtime deployment receipt and deployment telemetry are evidence candidates and must not become production readiness or conformance proof by themselves.

DeploymentIncident and SoftwareSupplyChainIncident must be capable of triggering rollback, quarantine, disablement, currentness downgrade, conformance rerun, evidence review, or human review where policy requires.

### CP15-P.8 Model, prompt, policy, and workflow deployment gate

ModelDeploymentCandidate, PromptPolicyChangeCandidate, and WorkflowDeploymentCandidate objects must be evaluated against intended-use, prohibited-use, evidence, security, privacy, runtime-surface, rollback, and CP11–CP14 gate requirements.

A CP13 learning result or CP14 model-improvement signal may support a candidate. It does not authorize deployment or model release.

### CP15-P.9 Output and readiness qualification

Deployment-facing outputs, agent answers, dashboards, generated summaries, release notes, model cards, public/export surfaces, and capability manifests must not imply deployment readiness, production readiness, security certification, model approval, current/default promotion, or conformance status stronger than the evidence and authority support.

A DeploymentOutputQualification or equivalent result qualification is required for high-consequence deployment-facing outputs.

### CP15-P.10 Runtime non-claims

Runtime support for CP15 remains implementation-directed with bounded debt until CP15 machine contracts, conformance fixtures, hostile review, implementation evidence, security review, steward validation, and pilot/runtime evidence exist.

CP15 runtime support does not claim production software-delivery readiness, production model-deployment readiness, cybersecurity certification, legal/security advice, automatic current/default promotion, autonomous release readiness, generic MLOps readiness, or full CI/CD product implementation.


For delivery-sensitive paths, the runtime EnforcementChain must include, where applicable:

1. generated-artifact and source/provenance normalization;
2. authority evaluation;
3. structural/semantic validation;
4. pack/profile/runtime-surface applicability;
5. CP11/CP12/CP13/CP14 gate evaluation where the deployment affects those surfaces;
6. SBOM/dependency/license/use-constraint evaluation;
7. static-analysis/security-scan evaluation;
8. conformance-test-plan and conformance-run evaluation;
9. security-waiver evaluation where findings are waived;
10. deployment-plan and environment-scope evaluation;
11. rollback/canary evaluation;
12. deployment authorization;
13. release-bundle/runtime-surface binding;
14. deployment-promotion decision where promotion is requested;
15. output/readiness qualification;
16. telemetry/receipt/incidents/rollback capture after deployment.
