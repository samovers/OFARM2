# OFARM Reference Resolution and Semantic Conformance RFC v0.1

Date: 2026-05-14  
Status: accepted RFC extension  
Change class: RFC extension + machine-contract/conformance implication  
Baseline impact: no direct RC2.1 baseline edit until later harmonisation

## 1. Purpose

This RFC closes a narrow but high-risk gap: schema-valid objects can still be semantically unsafe if package-local references are missing, type-wrong, stale, or externally unverified.

It does not change OFARM truth law. It makes already-required traceability more executable.

## 2. Conformance levels

Implementations and package validation must distinguish:

1. `SCHEMA_VALID` — object shape validates against JSON Schema.
2. `PACKAGE_LOCAL_REFERENCES_RESOLVED` — required package-local refs resolve to package-local objects of the expected class.
3. `EXTERNAL_REFERENCES_DECLARED` — external refs are explicit but not verified.
4. `EXTERNAL_REFERENCES_VERIFIED` — external refs have snapshot/live verification trace.
5. `RUNTIME_POLICY_GATES_PASSED` — authority, evidence, freshness, pack, materialization, and publication/export gates pass.
6. `HIGH_CONSEQUENCE_OUTPUT_ELIGIBLE` — a high-consequence PassportView, DocumentAssembly, export, or compliance result may proceed under policy.

Level 1 must not be presented as Level 6.

## 3. New carriers

This RFC introduces active machine contracts:

- `ReferenceResolutionManifest`
- `ReferenceResolutionFinding`
- `ReferenceResolutionReport`

These carriers record reference-resolution policy and outcomes. They do not create new canonical truth by themselves.

## 4. Package-local reference law

If a reference is declared package-local by prefix/policy, unresolved references must fail conformance or require review according to consequence level.

For v0.1, `reference-snapshot:` is hard-required for package-local resolution in the conformance runner because ReferenceSnapshot IDs are already used as package-local basis records in agronomic examples.

## 5. External-reference law

Externally anchored references may be declared without being package-local. They must not be treated as verified high-consequence identity unless a verified profile or verification trace exists.

Examples:

- free-text product name only: evidence, not compliance-grade identity;
- commercial GTIN only: useful product/batch evidence, not jurisdictional authorization proof by itself;
- active substance found but product authorization missing: require review or refuse high-consequence output;
- registry unavailable or stale at output time: require review or fail closed according to profile.

## 6. Output gating

Before high-consequence output, the runtime should have a reference-resolution report and must disclose or block unresolved/stale/unverified high-consequence bindings according to reconstruction policy.

## 7. Non-claims

This RFC does not claim live external registry verification, production runtime readiness, livestock coverage, or external-standard readiness.

---

## Baseline harmonisation note — ONT-SEMINT v0.3

On 2026-05-14, this RFC's supported closure was harmonised into the active RC2.1 baseline by ONT-SEMINT v0.3. The harmonisation is narrow: it incorporates the RFC's semantic-integrity rule into baseline posture while preserving all RFC non-claims around production readiness, live external registry verification, legal advice, external-standard readiness, livestock scope, and any profile-specific limitations.
