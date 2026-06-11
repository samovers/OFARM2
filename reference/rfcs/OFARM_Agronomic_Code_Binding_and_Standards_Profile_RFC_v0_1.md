# OFARM Agronomic Code Binding and Standards Profile RFC v0.1

Status: Accepted RFC extension; active substance unless overridden by the active baseline or a later accepted RFC.
Date: 2026-05-13
Phase: AGR-P5 agronomic code-binding and standards profile closure
Change class: RFC extension and machine-contract patch

## 1. Purpose

This RFC closes the agronomic code-binding gap at carrier-shell level. It gives OFARM a small executable way to bind local agronomic subjects to external schemes, registries, and profile rules without importing external ontologies as OFARM truth or allowing packs to mutate core meaning.

The closure is intentionally narrow. It does not create a private OFARM taxonomy for crops, pests, products, units, methods, or thresholds. It creates two OFARM-owned shells:

1. `AgronomicIdentityBinding` — a governed binding from a local subject to an external scheme, registry, product authority, code list, profile scheme, or attestation surface.
2. `AgronomicCodeBindingProfile` — a profile-level declaration of which schemes, roles, versions, evidence floors, and unresolved-binding behaviors apply to a pack, pilot, jurisdiction, or product surface.

## 2. Authority and non-goals

This RFC is active only as an accepted RFC extension. It does not edit `00_active_baseline/` text in this phase. Baseline harmonisation remains a later phase after the code-binding, query/output, and scenario closures prove stable.

This RFC must not be read to:

- make AIM, O&M JSON, ISOXML, EFDI, ADAPT, EPPO, BBCH, AGROVOC, Crop Ontology, UPOV, CPVO, GS1, QUDT, UCUM, or jurisdictional registries into OFARM law;
- let a registry lookup become canonical farm truth;
- let a local free-text label become accepted identity for high-consequence outputs;
- let packs redefine core concepts by changing external bindings;
- collapse crop-protection products, fertilizer blends, seed lots, and irrigation water sources into one product catalogue abstraction;
- weaken assertion/history-first truth, promotion law, authority gates, evidence sufficiency, or governed materialisation.

External schemes provide anchors, bindings, exchange mappings, runtime lookup surfaces, or attestation wrappers. OFARM truth remains assertion/history-first and promotion-governed.

## 3. Core rules

### 3.1 Scheme-bound identity rule

Any agronomic identity used for high-consequence promotion, materialisation, PassportView, SubmissionAssembly, regulatory filing, buyer-facing output, or compliance reconstruction must be scheme-bound or explicitly marked unresolved.

A binding must declare at least:

- local subject reference;
- binding role;
- scheme reference;
- scheme role;
- issuer or registry;
- captured label;
- binding state;
- evidence references;
- promotion boundary.

### 3.2 Free-text evidence rule

A crop name, product brand, pest name, variety label, method label, threshold number, or unit text captured from a human or source payload is evidence. It is not accepted identity unless a binding profile and evidence policy resolve it.

### 3.3 Role separation rule

The binding role must remain explicit. The following are not interchangeable:

- observed organism;
- suspected causal organism;
- treatment target;
- crop species;
- variety or cultivar;
- seed lot;
- crop-protection product;
- active substance;
- fertilizer or nutrient input;
- irrigation water source;
- sampling method;
- measurement method;
- threshold source;
- quantity kind;
- unit code.

### 3.4 Quantity and unit rule

Numeric agronomic quantities that may drive promotion or output must carry both:

- a quantity-kind reference; and
- a unit-code reference.

The original reported value and lexical unit must be retained as evidence when normalization occurs.

### 3.5 Product identity rule

Crop-protection product identity is jurisdiction-scoped and regulatory when compliance is affected. A GTIN or commercial identifier may support supply-chain identity, but it is not sufficient as the sole regulatory identity where a product authorization, registration, label, or active-substance constraint matters.

Fertilizer, nutrient input, seed lot, and irrigation water source identity are profiled separately. A local blend, on-farm mixture, water source, and PPP registration do not share the same identity semantics.

### 3.6 Threshold source rule

A threshold must bind to a source, issuer, effective period, and role. A bare number cannot be used as a high-consequence threshold. Threshold roles include legal threshold, label constraint, buyer specification, certification rule, advisory threshold, and model-derived threshold.

### 3.7 Pack merge and conflict rule

Packs may constrain allowed schemes, required roles, jurisdictions, versions, unresolved-binding behavior, and evidence floors. Packs must not mutate core field meanings. If code-binding profiles conflict, runtime merge must fail closed or require governed review unless a specific accepted precedence rule exists.

## 4. Standards role map

OFARM distinguishes external roles as follows:

- `SEMANTIC_ANCHOR`: a conceptual anchor used for alignment and interpretation.
- `CODE_BINDING`: a source of codes, concept schemes, identifiers, or units.
- `EXCHANGE_MAPPING`: an interchange surface or payload vocabulary.
- `RUNTIME_SURFACE`: a lookup, registry, or runtime verification surface.
- `ATTESTATION_WRAPPER`: an external certificate, accreditation, or provenance wrapper.
- `LOCAL_PROFILE_SCHEME`: an OFARM profile-scoped scheme used only when no suitable public code exists.

The role map is declared by `AgronomicCodeBindingProfile` and may be referenced by packs, capability manifests, mapping coverage statements, query specifications, document assemblies, and evidence sufficiency cases.

## 5. Minimum binding expectations by agronomic area

### Crop species

Use a scheme-bound crop-species binding. Crop-protection and plant-health profiles should prefer EPPO plant codes where appropriate; AGROVOC or UPOV/GENIE may be used as crosswalk support.

### Variety or cultivar

Capture the denomination as observed and bind to a registry where available. The binding must include issuer or registry context, because denomination text alone is not globally unique.

### Seed lot

Treat a seed lot as issuer-scoped. Carry issuer, lot number, evidence, and, when available, seed certificate and GS1 batch/lot identifiers. Parent or derived lot lineage must remain explicit.

### Crop stage

Use BBCH where the stage is standardised. Tie the stage to observation time, extent, and evidence; free-text stage labels remain evidence until explicitly mapped.

### Pest, weed, disease, and target organism

Use role-specific bindings. EPPO codes are preferred where available. Observed organism, suspected causal organism, treatment target, and damage subject must not be collapsed.

### Crop-protection product

For compliance or high-consequence output, use jurisdictional registration or authorization binding, product name, registrant, and active-substance references where available. Supply-chain identifiers may be additional evidence but not sole regulatory truth.

### Fertilizer or nutrient input

Use GTIN or manufacturer identity when packaged, and local issuer-scoped blend identity when mixed locally. Declared nutrient analysis is separate from product identity. Applied nutrient consequences are derived accepted consequences, not the product binding itself.

### Irrigation water source

Do not force irrigation water into crop-protection product semantics. Bind the water source or permit identity and separately record water quality, delivery method, pressure or flow, and treated extent.

### Sampling and measurement methods

Bind to method/protocol references with issuer, version, and effective date. Use a local profile scheme only where public coding is unavailable or too coarse.

### Threshold source

Bind thresholds to a source document, issuer, jurisdiction or profile scope, effective period, threshold role, and evidence basis.

## 6. Machine contracts introduced

This RFC introduces:

- `03_machine_contracts/schemas/agronomic/OFARM_AgronomicIdentityBinding_schema_v0_1.json`
- `03_machine_contracts/schemas/agronomic/OFARM_AgronomicCodeBindingProfile_schema_v0_1.json`

It also introduces examples for crop species, variety, seed lot, crop stage, weed/target organism, crop-protection product, unresolved marketing-only product identity, fertilizer blend, unit/quantity-kind binding, sampling method, and threshold source.

## 7. Promotion and materialisation effects

A code binding alone does not create truth. It may support promotion only when:

- the binding profile allows the role and scheme;
- evidence sufficiency passes;
- the binding state is compatible with the requested consequence;
- authority, delegation, and event promotion gates pass where applicable;
- current-state materialisation remains derivative and fresh enough for the requested output.

Ambiguous or stale bindings may be retained in history and DocumentAssembly annexes, but must not silently support high-consequence PassportView or SubmissionAssembly output.

## 8. Conformance expectations

Phase AGR-P5 adds fixtures and a runner that must prove:

- scheme-bound crop, variety, seed-lot, crop-stage, weed, product, method, threshold, quantity-kind, and unit bindings validate;
- free-text-only product identity blocks compliance-grade product consequences;
- verified bindings cannot be identifier-empty;
- ambiguous bindings fail closed or require review;
- profiles require both quantity kind and unit code;
- profile conflicts do not become pack-driven semantic mutation.

## 9. Relationship to prior agronomic phases

This RFC depends on the carrier closures from:

- `OFARM_Agronomic_Observation_and_Measurement_Context_RFC_v0_1.md`
- `OFARM_Quantity_Bearing_Intervention_and_As_Applied_RFC_v0_1.md`
- `OFARM_Partial_Extent_and_Geometry_Basis_RFC_v0_1.md`

It prepares the next phase: agronomic query and output reconstruction.
