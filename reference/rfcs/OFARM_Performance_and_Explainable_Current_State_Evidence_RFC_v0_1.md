# OFARM Performance and Explainable Current-State Evidence RFC v0.1

Date: 2026-06-11  
Status: accepted post-charter RFC, effective on merge  
Scope: close the runtime-evidence gap for explainable current-state materialization, dependency-based invalidation, trace expansion, and benchmark-backed capability claims

---

## 1. Problem statement

The active baseline already requires:
- assertion/history-first canonical truth
- governed current-state materializations
- traceable MaterializationBasis records
- freshness states of FRESH, STALE, and INVALID
- invalidation triggers across truth basis, identity/lifecycle, context, time policy, and twin-specific advisory changes
- high-consequence recompute/refuse/review behavior
- QueryPlanIR declarations for materialization and freshness requirements
- Capability Manifest self-description for runtime claims

That law is directionally correct.
But it leaves the hardest implementation risk under-specified: the runtime may need to maintain bitemporal truth, traceable materialization bases, dependency-driven freshness invalidation, and per-query reconstruction traces at fleet scale.

Without an explicit runtime evidence contract, a platform can claim OFARM support while hiding the cost and operational fragility of explainable current state behind generic "Platform" responsibility.

The unresolved questions are:
- how a runtime proves materialization freshness without scanning the whole graph
- how it bounds trace-generation cost without weakening high-consequence traceability
- how it invalidates materializations by dependency rather than by global recomputation
- how it exposes benchmark and storage-amplification evidence
- how Capability Manifest claims distinguish implemented behavior from proven behavior
- how conformance tests detect projection-only shortcuts, hidden truth stores, and stale-current-state reliance

This RFC closes that gap without changing the canonical truth model.

---

## 2. Core stance

### 2.1 Performance freedom is allowed, but performance claims require evidence

The platform may optimize storage layout, indexes, caches, service topology, materialization scheduling, trace compression, and compute placement.

It may not claim fleet-ready explainable current state unless it has benchmark evidence for the declared workload envelope.

### 2.2 Explainability must be tiered, not unbounded by default

OFARM does not require every low-consequence dashboard or exploratory query to retain a full forensic replay artifact.

OFARM does require every relied-upon current-state result to expose enough qualification and basis information for the declared use class, and it requires high-consequence use to have reconstructible and policy-compliant traces.

### 2.3 Dependency-indexed invalidation is the required implementation posture

A conforming runtime must not rely on global graph scans or wall-clock age alone as its freshness mechanism.

It must maintain, or be able to derive, dependency records that connect basis changes to affected materialization keys.

### 2.4 Materialization support is not production readiness

An implementation may support MaterializationBasis, MaterializationSnapshot, QueryPlanIR materialization policy, and freshness statuses while still lacking production or fleet-scale evidence.

The Capability Manifest must disclose that distinction.

### 2.5 This RFC is runtime/conformance law, not a truth-model rewrite

This RFC does not change:
- assertion/history-first canonical truth
- event grammar
- commit classes
- promotion law
- pack law
- authority law
- the Compliance Twin / Advisory Twin split
- freshness-state semantics
- PassportView / DocumentAssembly taxonomy

It adds a testable runtime evidence envelope around the existing law.

---

## 3. Affected active authority surfaces

On merge, this RFC affects:

- `00_active_baseline/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md`
- `02_accepted_rfcs/OFARM_Current_State_Materialization_RFC_v0_1.md`
- `02_accepted_rfcs/OFARM_QuerySpecification_Schema_RFC_v0_1.md`
- `02_accepted_rfcs/OFARM_Capability_Manifest_RFC_v0_1.md`
- `03_machine_contracts/` current-state, query, runtime-surface, and conformance contract families
- `04_implementation_and_conformance/` benchmark runners, hostile fixtures, and implementation notes

Default change classification:
- baseline law: narrow Platform clarification only, if later materialized
- RFC extension: yes
- supporting research implication: yes
- implementation/conformance implication: yes
- Constitution change: not required by default

---

## 4. New runtime contract family

This RFC defines the **Explainable Current-State Runtime Evidence** contract family.

The family contains the following contract objects:

1. `MaterializationKey`
2. `MaterializationDependencyIndex`
3. `MaterializationFreshnessVector`
4. `InvalidationEvaluationTrace`
5. `TraceExpansionPolicy`
6. `TraceExpansionRequest`
7. `TraceExpansionResult`
8. `MaterializationCostProfile`
9. `RuntimeQueryMixProfile`
10. `RuntimeMaterializationBenchmarkRun`
11. `RuntimeStorageAmplificationReport`
12. `ExplainableCurrentStateCapabilityClaim`

This RFC names and normatively constrains those objects.
Machine-readable schemas should be added in a follow-on machine-contract patch before any implementation claims schema-level conformance.

---

## 5. MaterializationKey

### 5.1 Purpose

A `MaterializationKey` identifies one governed current-state answer strongly enough for caching, invalidation, trace retrieval, and benchmark measurement.

It refines the Current-State Materialization RFC rule that one materialization instance equals one governed answer.

### 5.2 Minimum key dimensions

A valid `MaterializationKey` must include at least:

- deployment or tenant scope
- target twin
- anchor scope or anchor scope set
- evaluation time policy
- context snapshot reference or context basis digest
- materialization policy reference
- query/view/output profile reference where relevant
- use class
- result shape family
- policy version reference

### 5.3 Use class

The use class must distinguish at least:

- `EXPLORATORY_VIEW`
- `OPERATIONAL_DASHBOARD`
- `ADVISORY_SCENARIO`
- `COMPLIANCE_DECISION_SUPPORT`
- `ATTESTED_OUTPUT`
- `FORMAL_SUBMISSION`
- `EXTERNAL_RELIED_UPON_CLAIM`
- `FORENSIC_AUDIT`

The use class controls freshness tolerance, trace tier, retention, and refusal behavior.

### 5.4 Key discipline

A runtime must not collapse materially different materialization keys merely because they produce similar display output.

In particular, it must not silently collapse across:
- Compliance Twin and Advisory Twin
- NOW and AS_OF policies
- different active pack/profile contexts
- materially different evidence policies
- materially different authority contexts
- low-consequence and high-consequence use classes

---

## 6. MaterializationDependencyIndex

### 6.1 Purpose

A `MaterializationDependencyIndex` records which canonical or contextual inputs can affect which materialization keys.

It is the runtime mechanism that makes scoped invalidation practical.

### 6.2 Derived-only rule

The dependency index is derived runtime infrastructure.
It is not canonical truth.
It must be refreshable or recomputable from canonical substrate, active context state, materialization policies, and query/view/output plans.

A dependency-index entry may accelerate invalidation.
It may not become the only surviving explanation of truth.

### 6.3 Minimum dependency families

The index must support at least these dependency families:

- truth-basis dependency
- accepted event consequence dependency
- review decision dependency
- identity/lifecycle dependency
- context snapshot dependency
- pack/profile activation dependency
- rule/evidence-policy dependency
- reference snapshot dependency
- evaluation-time boundary dependency
- advisory model-output dependency where applicable
- output assembly dependency where materialized state feeds a compiled output

### 6.4 Minimum index entry fields

A dependency index entry should identify:

- dependency source reference
- dependency source family
- affected `MaterializationKey` or key pattern
- impact scope
- affected use classes
- invalidation trigger class
- expected status impact candidate: FRESH, STALE, INVALID, or RECOMPUTE_REQUIRED
- derivation source: QueryPlanIR, view profile, output assembly policy, materialization policy, or explicit runtime rule
- index generation time
- index policy version

### 6.5 Dependency broadening rule

When a runtime cannot determine a precise dependency boundary, it must broaden invalidation rather than narrow it unsafely.

A broader-than-necessary stale/invalid result is acceptable.
A narrower-than-justified fresh result is not acceptable for high-consequence use.

### 6.6 Index corruption rule

If the dependency index is missing, corrupted, stale beyond policy, or inconsistent with canonical replay checks, the platform must treat affected high-consequence materializations as not demonstrably FRESH.

The allowed outcomes are recompute, refuse, or review, subject to policy.

---

## 7. MaterializationFreshnessVector

### 7.1 Purpose

A `MaterializationFreshnessVector` records the source watermarks, sequence positions, version references, or digest refs that were observed when a materialization was generated or checked.

It lets a runtime answer: "Has any relevant basis advanced since this materialization?"

### 7.2 Minimum vector dimensions

A freshness vector should include, where applicable:

- canonical assertion/history sequence or digest
- accepted event consequence sequence or digest
- ReviewDecision sequence or digest
- identity/lifecycle revision sequence or digest
- PackActivationSet version or digest
- rule/evidence-policy version or digest
- ContextSnapshot reference or digest
- ReferenceSnapshot version or digest
- authority/delegation/revocation policy version where authority affects the result
- advisory model-output or scenario version where Advisory Twin materialization depends on it
- evaluation-time boundary reference for time-sensitive state
- QueryPlanIR/materialization policy version

### 7.3 Vector is not basis

A freshness vector is not a replacement for `MaterializationBasis`.

The vector proves what version envelope was seen.
The basis explains what authoritative material determined the result.

### 7.4 Wall-clock limitation

Clock age may be one freshness input.
It must not be the only freshness input for high-consequence use.

---

## 8. InvalidationEvaluationTrace

### 8.1 Purpose

An `InvalidationEvaluationTrace` explains why a materialization key stayed FRESH, became STALE, became INVALID, or required recomputation after a trigger.

### 8.2 Minimum trace fields

An invalidation trace should include:

- trigger identifier
- trigger family
- trigger source reference
- trigger scope
- evaluated materialization key or key pattern
- dependency-index evidence used
- freshness-vector comparison where applicable
- status before evaluation
- status after evaluation
- reason code
- policy reference
- decision time
- evaluator runtime version

### 8.3 Fanout disclosure

Benchmark and conformance traces must record invalidation fanout, including:

- number of materialization keys considered
- number marked STALE
- number marked INVALID
- number marked RECOMPUTE_REQUIRED
- number unaffected
- maximum scope expansion applied because of uncertain dependency boundaries

This lets reviewers distinguish precise invalidation from accidental global recomputation.

### 8.4 Redaction rule

Invalidation traces may be redacted for access-control or sovereignty reasons.

Redaction must not hide the fact that redaction occurred, and it must not allow a party to treat an unprovable materialization as FRESH for high-consequence use.

---

## 9. TraceExpansionPolicy

### 9.1 Purpose

A `TraceExpansionPolicy` defines how much explanation must be generated, retained, or made retrievable for a given use class.

This is the primary cost-control mechanism for explainable current state.

### 9.2 Trace tiers

OFARM defines three baseline trace tiers.

#### Tier 1 — qualification trace

A qualification trace must be available for every materialization used in any user-visible, API-visible, or output-visible current-state result.

It identifies:
- materialization key
- freshness status
- freshness vector summary
- basis reference or basis digest
- context snapshot reference
- policy references
- limitations and refusal/review flags

#### Tier 2 — reconstruction trace

A reconstruction trace must be available for high-consequence use.

It identifies enough basis references, context references, QueryPlanIR steps, policy decisions, and invalidation checks to reconstruct why the current-state result was relied upon.

Tier 2 may be generated lazily before high-consequence publication or decision, but the high-consequence action must not complete unless the Tier 2 trace is available or explicitly waived by a valid review policy.

#### Tier 3 — forensic replay trace

A forensic replay trace supports audit, dispute, regulator challenge, hostile conformance testing, and projection-corruption investigation.

It must be able to replay or independently reconstruct the materialization from canonical substrate and governed context.

Tier 3 need not be emitted on every normal query.
It must be available for declared audit/conformance paths and for retained high-consequence snapshots where policy requires it.

### 9.3 Trace retention rule

The runtime may discard recomputable low-consequence trace expansions.

It must retain, or be able to regenerate with the same relevant basis, traces for:
- accepted high-consequence decisions
- attested or frozen outputs
- formal submissions
- externally relied-upon current-state claims
- disputed or reviewed materialization decisions
- conformance benchmark evidence

### 9.4 Compact basis rule

A compact basis record may use references, hashes, digests, Merkle-style summaries, vector positions, and policy refs.

Compactness is allowed only if the expanded trace remains reconstructible under the declared retention policy.

---

## 10. QueryPlanIR extension

### 10.1 Required planning declarations

When a QueryPlanIR uses, creates, refreshes, or relies on current-state materialization, it must declare:

- materialization key or key derivation rule
- required freshness status
- required trace tier
- whether the use is high consequence
- materialization policy reference
- dependency-index strategy
- freshness-vector dimensions required
- trace-retention requirement
- fallback behavior: recompute, refuse, review, or disclose limitation

### 10.2 Projection equivalence declaration

If a query plan reads from a projection, cache, index, or read model, the plan must declare how projection trace-back and semantic equivalence are verified for the declared use class.

For high-consequence use, a projection-only result is insufficient unless the plan can demonstrate equivalence to the governed substrate/materialization basis under policy.

### 10.3 Cost-aware planning

QueryPlanIR may declare a cost-aware strategy, including lazy trace expansion or cached materialization reuse.

Cost-aware planning must not downgrade required freshness, trace tier, or refusal behavior.

---

## 11. Capability Manifest extension

### 11.1 Explainable-current-state capability claim

A Capability Manifest that claims current-state materialization support must distinguish:

- implemented contract support
- conformance test support
- benchmarked runtime envelope
- production-observed evidence, if any

### 11.2 Performance envelope

The manifest should include a `performanceEnvelope` or equivalent section for explainable current state, with:

- supported workload profile refs
- tested data scale
- tested tenant/farm/field/crop-cycle/lot counts
- tested event/assertion/evidence ingest rates
- tested query mix
- tested high-consequence output rate
- p50/p95/p99 freshness-check latency
- p50/p95/p99 materialization recompute latency
- p50/p95/p99 trace retrieval or expansion latency by tier
- invalidation fanout distribution
- projection lag distribution
- storage amplification report ref
- cold rebuild time
- benchmark run refs
- known limitations

### 11.3 Runtime evidence levels

A manifest may report one of these evidence levels for explainable current state:

- `IMPLEMENTED_NO_BENCHMARK_EVIDENCE`
- `CONFORMANCE_FIXTURE_PASSING`
- `SINGLE_TENANT_PILOT_BENCHMARKED`
- `MULTI_TENANT_PILOT_BENCHMARKED`
- `FLEET_SCALE_SYNTHETIC_BENCHMARKED`
- `PRODUCTION_OBSERVED_WITH_TELEMETRY`

A higher evidence level must not be claimed without corresponding evidence refs.

### 11.4 Negative claim rule

If no benchmark, load, storage-cost, or trace-retrieval evidence exists, the manifest must not imply fleet-scale readiness for explainable current state.

It may only claim implemented or unproven support at the appropriate lower evidence level.

---

## 12. Benchmark contract

### 12.1 RuntimeMaterializationBenchmarkRun

A `RuntimeMaterializationBenchmarkRun` records one executed benchmark of materialization, invalidation, and trace behavior.

It should include:

- runtime identity and version
- active artifact set reference
- dataset/workload generator reference
- workload profile
- hardware or deployment resource envelope
- storage backend class
- tenant/farm/field/crop-cycle/lot counts
- assertion/event/evidence volumes
- pack/profile count and churn rate
- authority/delegation/revocation churn rate
- external reference snapshot churn rate
- query mix by use class and trace tier
- benchmark duration
- warm/cold/cache state
- measured latency distributions
- measured throughput
- measured fanout
- measured storage amplification
- failures, refusals, and review-routed actions
- reproducibility notes

### 12.2 RuntimeQueryMixProfile

A benchmark must declare the query mix it exercised.

At minimum, standard query mixes should cover:

- low-consequence dashboard reads
- operational current-state reads
- Advisory Twin scenario reads
- Compliance Twin high-consequence reads
- PassportView input materialization
- DocumentAssembly input materialization
- formal submission materialization
- audit/reconstruction trace retrieval

### 12.3 Storage amplification report

A `RuntimeStorageAmplificationReport` should distinguish storage used by:

- canonical assertion/history substrate
- context/reference snapshots
- materialized current-state records
- retained MaterializationSnapshots
- dependency index
- freshness vectors
- trace records
- projections/read models/search indexes
- benchmark-generated auxiliary telemetry

The report should express amplification both absolutely and relative to canonical substrate size.

### 12.4 Cold rebuild requirement

Benchmarks must include a cold rebuild or replay case for at least one declared workload profile.

The rebuild must prove that materializations and dependency indexes can be regenerated from canonical substrate and governed context rather than only restored from hidden projection state.

---

## 13. Minimal benchmark fixture set

A conforming benchmark suite should include at least these fixtures.

### 13.1 Scoped assertion invalidation

An accepted assertion enters force in one field/crop-cycle scope.

Expected result:
- dependent materialization keys become STALE or RECOMPUTE_REQUIRED
- unrelated tenants and unrelated farms are not globally recomputed unless the implementation declares a deliberately broad strategy
- invalidation trace records fanout and scope reasoning

### 13.2 Review-decision supersession

A ReviewDecision supersedes an accepted consequence used by a Compliance Twin materialization.

Expected result:
- prior high-consequence materialization is not demonstrably FRESH
- PassportView or submission generation recomputes, refuses, or routes to review
- invalidation trace identifies the ReviewDecision basis

### 13.3 Pack/profile activation change

A PackActivationSet changes for a relevant scope.

Expected result:
- materializations under affected context become STALE, INVALID, or RECOMPUTE_REQUIRED according to policy
- materializations under unaffected context remain FRESH if dependency proof supports that result

### 13.4 Identity/lifecycle revision

A field revision changes boundary interpretation without creating a new field identity, or a crop-cycle replant creates a new cycle identity.

Expected result:
- affected scope materializations are invalidated according to identity/lifecycle policy
- lineage-sensitive traces identify the revision or new identity basis

### 13.5 Reference snapshot update

An external reference snapshot changes where a high-consequence output depends on it.

Expected result:
- affected materializations are not silently treated as current
- freshness vector and invalidation trace disclose reference snapshot advancement

### 13.6 Advisory stale display

An Advisory Twin exploratory view reads a stale materialization.

Expected result:
- view may display only with clear qualification
- bridge toward Compliance Twin forces stricter freshness evaluation

### 13.7 Compliance high-consequence block

A Compliance Twin high-consequence output attempts to rely on STALE current state.

Expected result:
- output recomputes, refuses, or routes to explicit review
- no external relied-upon claim is emitted as if FRESH

### 13.8 Trace tier enforcement

The same query is executed under low-consequence and high-consequence use classes.

Expected result:
- low-consequence path emits Tier 1 qualification trace
- high-consequence path requires Tier 2 reconstruction trace before completion
- forensic replay path can produce Tier 3 evidence under audit/conformance policy

### 13.9 Projection corruption detection

A projection/read model is deliberately corrupted while canonical substrate remains valid.

Expected result:
- high-consequence equivalence check fails or recomputes from canonical basis
- projection-only answer is not accepted as governed truth

### 13.10 Dependency-index failure

A dependency index partition is missing, stale, or inconsistent.

Expected result:
- affected high-consequence materializations are not considered demonstrably FRESH
- fallback behavior follows recompute/refuse/review policy

### 13.11 Permission and redaction boundary

A trace is requested by a party without authority to see all basis details.

Expected result:
- trace retrieval respects authority and data-sovereignty policy
- redaction is disclosed
- redaction does not upgrade freshness or evidence sufficiency

### 13.12 Cold rebuild equivalence

The runtime rebuilds materializations and dependency indexes from canonical substrate and governed context.

Expected result:
- rebuilt results match retained materialization snapshots within declared equivalence policy
- mismatches are surfaced as conformance failures or review-required conditions

---

## 14. Metrics required for evidence claims

A runtime claiming benchmarked explainable-current-state support should report at least:

- ingest throughput
- canonical commit latency where relevant
- projection/materialization lag
- freshness-check latency
- materialization recomputation latency
- invalidation fanout distribution
- query latency by use class
- trace expansion latency by tier
- trace retrieval latency by tier
- snapshot-retention overhead
- dependency-index storage overhead
- projection/index storage overhead
- total storage amplification
- write amplification
- cold rebuild time
- refusal/review-required rate
- false-fresh defects found by hostile fixtures
- false-stale or over-broad invalidation rate where measurable

The benchmark may report platform-specific cost estimates, but cost estimates must disclose the resource assumptions used.

---

## 15. Conformance claim rules

### 15.1 No evidence, no fleet-readiness claim

A deployment must not claim fleet-scale explainable-current-state readiness without benchmark results covering the declared workload envelope.

### 15.2 Implemented support is not enough

Passing schema validation or unit fixtures is not enough to claim runtime scalability.

The implementation must also produce benchmark evidence for materialization, invalidation, trace retrieval, storage amplification, and cold rebuild behavior.

### 15.3 High-consequence gate remains stronger than performance preference

A platform may choose to refuse high-consequence output when recomputation or trace expansion is too expensive.

It may not emit the output by silently weakening freshness or trace requirements.

### 15.4 Capability claims must name their envelope

A capability claim is meaningful only for a declared envelope.

The envelope must identify scale, workload mix, trace tiers, retention policy, and known exclusions.

### 15.5 Benchmark artifacts are evidence, not truth

Benchmark results are conformance evidence.

They do not become canonical farm truth, do not change materialization results, and do not override active baseline law.

---

## 16. Non-goals

This RFC does not require:

- one storage engine
- one graph database
- one stream processor
- one materialized-view technology
- full forensic trace emission on every query
- permanent retention of every low-consequence trace expansion
- fixed universal SLA targets in v0.1
- public disclosure of private benchmark internals where security or sovereignty policy forbids it

This RFC also does not make projections authoritative.

---

## 17. Risks and mitigations

### 17.1 Risk: benchmark theater

A vendor could create an easy benchmark that does not exercise real invalidation or trace expansion.

Mitigation:
- require workload profiles, hostile fixtures, fanout metrics, trace-tier metrics, and cold rebuild cases.

### 17.2 Risk: over-broad invalidation masks poor design

A runtime could mark everything stale on every change and still pass safety tests while failing cost expectations.

Mitigation:
- require fanout disclosure and benchmarked latency/storage metrics.
- allow safety-preserving broad invalidation, but prevent it from supporting fleet-readiness claims unless performance evidence supports it.

### 17.3 Risk: trace compression hides missing basis

A compact basis digest could become a fig leaf for unreconstructible state.

Mitigation:
- require trace expansion policy, reconstruction traces for high-consequence use, and cold rebuild equivalence tests.

### 17.4 Risk: Capability Manifest becomes marketing

A manifest could claim support without evidence.

Mitigation:
- require evidence levels and benchmark refs for higher readiness claims.

### 17.5 Risk: performance pressure weakens governance

Operators may want to bypass recomputation or trace expansion under load.

Mitigation:
- high-consequence outputs must recompute, prove freshness, refuse, or route to explicit review.
- performance failure is not authority to emit unqualified outputs.

---

## 18. Main patch consequences

After merge, follow-on patches should:

1. Add machine schemas for the Explainable Current-State Runtime Evidence contract family.
2. Extend QueryPlanIR schemas with materialization key, trace tier, dependency-index strategy, and fallback behavior fields.
3. Extend Capability Manifest schemas with `performanceEnvelope` and evidence-level fields.
4. Add conformance benchmark fixtures under `04_implementation_and_conformance/`.
5. Add hostile fixtures for dependency-index failure, projection corruption, stale high-consequence output, and cold rebuild mismatch.
6. Add implementation guidance for compact basis records, freshness vectors, trace retention, and redaction-safe trace retrieval.
7. Optionally patch the Platform baseline to state that production/fleet readiness for explainable current state requires declared benchmark evidence.

---

## 19. Minimal conformance expectations

A conforming implementation of this RFC should be able to answer:

- What materialization key was used?
- What dependency-index entries connect basis changes to that key?
- What freshness vector was observed?
- Which trigger made a materialization FRESH, STALE, INVALID, or RECOMPUTE_REQUIRED?
- Which trace tier was required by the use class?
- Was the trace generated, retained, or reconstructible under policy?
- What benchmark evidence supports the deployment's capability claim?
- What storage amplification and trace-retrieval costs were measured?
- What happens when the dependency index, projection, or trace store is corrupted?

---

## 20. Hard stop question

The RFC succeeds only if a reviewer can ask a deployment:

**Can you prove, under a declared workload envelope, that explainable current state is fresh, traceable, invalidated by dependency, reconstructible for high-consequence use, and benchmarked for latency, fanout, storage amplification, and cold rebuild cost?**
