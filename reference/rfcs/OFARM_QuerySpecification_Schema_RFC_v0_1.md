# OFARM QuerySpecification Schema RFC v0.1

Date: 2026-04-08  
Status: accepted post-charter RFC  
Scope: formalize the machine-validatable contracts for QuerySpecification and QueryPlanIR so OFARM query law becomes executable rather than prose-only

---

## 1. Problem statement

RC2 correctly says:
- OFARM has a canonical internal query model
- QuerySpecification is the constitutional query artifact
- SemanticPathAlias is governed shorthand
- QueryPlanIR is the runtime planning representation

That is architecturally good.
It is not yet implementable enough.

The remaining gap is:
- no formal schema for QuerySpecification
- no formal schema for QueryPlanIR
- no explicit alias-resolution contract shape
- too much room for hidden runtime interpretation

This RFC closes that gap.

---

## 2. Core stance

### 2.1 Internal model first, public syntax later
OFARM still does **not** standardize a public expert textual query syntax in v2.

This RFC formalizes:
- a machine-validatable **QuerySpecification** contract
- a machine-validatable **QueryPlanIR** contract

That keeps the internal model hard without freezing the wrong public surface too early.

### 2.2 Query law versus runtime planning
- **QuerySpecification** remains the constitutional query artifact.
- **QueryPlanIR** remains a runtime planning contract derived from QuerySpecification.

The two must not collapse into one another.

### 2.3 Graph-pattern-first, path-aware
The formal contracts preserve the same architectural choice already made in RC2:
- graph-pattern-first for semantic relationships
- path-aware for archetype/template-bound content
- filter-rich for time, space, provenance, pack, authority, and review constraints

---

## 3. Formal artifacts produced by this RFC

This RFC creates:

- **OFARM QuerySpecification schema v0.1** (`ofarm.queryspec.v0.1`)
- **OFARM QueryPlanIR schema v0.1** (`ofarm.queryplanir.v0.1`)

Example fixtures included:
- field passport current-state query example
- lot-lineage query example
- field passport query-plan example

Schemas and example instances were validated against JSON Schema draft 2020-12.

---

## 4. QuerySpecification schema decisions

### 4.1 Minimum top-level structure
A valid QuerySpecification must include:
- schemaVersion
- target
- graphPattern
- selection
- resultProfile

Optional but governed blocks include:
- anchors
- semanticPathAliases
- filter
- ordering
- pagination

### 4.2 Target block
The target block formally binds:
- twin
- anchorScopes
- evaluationTimePolicy
- optional authority context

This is important because OFARM queries are not context-free.
The same graph pattern can mean different things under different:
- twin choices
- scopes
- time policies
- authority contexts

### 4.3 GraphPattern block
The graph pattern is now formalized through:
- node patterns
- relation patterns

This keeps graph-pattern semantics explicit and machine-checkable.

### 4.4 SemanticPathAlias block
Aliases are now explicit formal objects with:
- alias name
- rootVar
- pathRef
- resolvesTo type
- optional expected type
- aliasVersionRef

That last field matters.
Without alias versioning, path shorthand becomes a hidden schema drift source.

### 4.5 Filter block
The initial formal filter family supports:
- logical filters
- comparisons
- IN
- EXISTS
- spatial filters
- temporal filters

This is intentionally enough to make the contract real without pretending the v0.1 schema already solves every future analytical pattern.

### 4.6 Selection and result profile
Selection and result profile are now formalized enough to distinguish:
- raw bindings
- object-graph style outputs
- summary rows
- view-module outputs
- passport/document input modes

---

## 5. QueryPlanIR schema decisions

### 5.1 QueryPlanIR is not constitutional law
It remains a runtime planning contract.
But it is now formalized enough that the runtime cannot hide all planning inside uninspectable code.

### 5.2 Minimum top-level structure
A valid QueryPlanIR must include:
- schemaVersion
- sourceQuerySpecificationId
- normalizedTarget
- resolvedPathAliases
- executionSteps
- materializationPolicy
- outputAssembly

### 5.3 Resolved path aliases
Path aliases now resolve formally into:
- resolvedToType
- resolvedRef
- resolutionVersionRef

This matters because alias resolution is one of the biggest hidden query-drift risks.

### 5.4 Execution steps
Execution steps are intentionally abstract but formal enough to identify:
- executor type
- operation type
- input bindings
- output binding set
- freshness requirement where relevant

This keeps runtime freedom while still making equivalence and traceability testable.

### 5.5 Materialization policy
QueryPlanIR now carries explicit materialization-policy information, including:
- required freshness
- whether the use is high consequence

That ties this RFC cleanly to the current-state materialization RFC instead of ignoring it.

### 5.6 Equivalence requirements
QueryPlanIR now has an explicit place to declare:
- semantic equivalence requirement
- projection trace-back requirement

This does not fully solve executor equivalence.
It does create a place where the contract can require it.

---

## 6. What this RFC still does not try to solve

This RFC intentionally does **not** try to fully solve:
- a public expert textual syntax
- every future aggregate/group-by/windowing feature
- full optimizer semantics
- complete query cost/planning strategy
- full alias-evolution governance across every future content change

Those remain later concerns.

The goal here is narrower:
- stop query law from remaining only prose
- make validation and conformance possible
- reduce runtime drift

---

## 7. Main patch consequences

This RFC requires:
- Constitution patching in section 9, conformance direction, companion artifacts, and glossary
- Platform patching in query runtime, schema validation, plan equivalence requirements, and tests
- Alignment Register refinement for query concepts
- machine-readable schema artifacts
- example fixtures

---

## 8. Hard stop question

The RFC succeeds only if:

1. a validator can deterministically reject malformed QuerySpecifications and QueryPlanIR objects  
2. the runtime can no longer hide query meaning inside ungoverned conventions  
3. alias resolution is versioned enough to avoid silent drift
