# OFARM External Code Binding Currentness and Verification RFC v0.1

Date: 2026-05-14  
Status: accepted RFC extension  
Amendment line: ONT-SEMINT v0.2 / Phase 4  
Authority posture: extends accepted agronomic code-binding, ReferenceSnapshot, query/output reconstruction, and reference-resolution law; does not amend RC2.1 baseline directly.

## 1. Purpose

This RFC closes the Phase 4 external-code-binding currentness gap for one narrow profile: Belgian crop-protection product authorisation identity. It turns the Deep Research evidence into an OFARM-owned verification trace, a profile example, conformance fixtures, and fail-closed rules.

The amendment preserves the existing OFARM model/runtime split:

- OFARM truth remains assertion/history-first.
- Current state remains governed materialization.
- External registries and standards may act as runtime surfaces, code bindings, semantic anchors, exchange mappings, or attestation wrappers.
- External registries and standards do not become hidden OFARM law.
- PassportView remains a governed, derivative view.
- DocumentAssembly may annex unresolved evidence without promoting it.

## 2. Research basis

The supporting research identifies Belgium as the best immediate jurisdictional profile target because Belgium's Phytoweb surfaces expose stronger public currentness mechanics than the researched Slovenian public sources. Phytoweb documents search by name, authorisation number, crop and enemy, status filtering, daily refreshed lists, authorisation history, Excel export, and raw JSON distribution with monthly full exports and daily changes.

The research also concludes that a high-consequence crop-protection product identity binding must use a jurisdictional product authorisation record as the mandatory runtime/checking surface. EU active-substance resources are contextual anchors, not replacements for Member State product authorisation. Free-text product name, GTIN-only identity, active-substance-only identity, EU-only identity, missing snapshot, missing access date, wrong jurisdiction, stale source, registry unavailability, and prescription/as-applied identity mismatch must not silently produce a current-compliant PassportView.

## 3. New OFARM-owned carrier

This RFC introduces `ExternalRegistryVerificationTrace` as a small OFARM-owned carrier.

`ExternalRegistryVerificationTrace` records:

- which external authority and jurisdiction were checked;
- which lookup surface was used;
- the exact query inputs;
- how many candidates were returned;
- the selected external identifier;
- the observed status and dates;
- whether label or certificate evidence was correlated;
- whether active-substance context was cross-checked;
- the ReferenceSnapshot objects used;
- registry availability;
- discrepancies;
- final outcome;
- downstream output disposition.

The trace is evidence and gate support. It is not canonical farm truth by itself.

## 4. Belgium profile rule

The active machine-contract example `BE-CropProtection-AuthorisationIdentity-Currentness` establishes this profile posture:

1. Belgian Phytoweb authorisation is the mandatory jurisdictional runtime/checking surface for Belgian crop-protection product authorisation identity.
2. The Belgian authorisation number or equivalent official permit identifier is the primary external binding key.
3. Product/trade name remains captured evidence, but not sole identity.
4. GTIN and Digital Link remain commercial evidence or exchange surfaces, not regulatory authorisation keys.
5. The EU Pesticides Database is EU-level active-substance or emergency-authorisation context only.
6. EPPO and, where applicable, BBCH support crop, pest, target, and stage semantics but do not replace the authorisation record.
7. UCUM carries operational unit codes; QUDT carries quantity-kind semantics where needed.
8. CPVO, UPOV, OECD Seed Schemes, AGROVOC, and Crop Ontology remain adjunct context where relevant, not crop-protection product authorisation law.

## 5. Required snapshot classes for high-consequence use

For this profile, the following snapshot classes are required or allowed:

| Snapshot class | OFARM posture |
|---|---|
| JurisdictionalProductAuthorisationSnapshot | Required for high-consequence current-compliance PassportView. |
| AuthorisationLabelOrCertificateSnapshot | Required when the output claims label-level compliance, pack-level labelling alignment, or certificate-backed proof. |
| EUActiveSubstanceContextSnapshot | Recommended when active-substance reasoning is used; not sufficient for product authorisation identity. |
| CommercialIdentityEvidenceSnapshot | Optional adjunct for GTIN, Digital Link, invoice, pack scan, or lot context; never sufficient alone. |

The existing `ReferenceSnapshot` schema carries the snapshot basis. `ExternalRegistryVerificationTrace` carries the detailed verification procedure and outcome.

## 6. Fail-closed and review-required rules

For a high-consequence current-compliance PassportView under this profile:

| Condition | Required OFARM disposition |
|---|---|
| Free-text product name only | REVIEW_REQUIRED; REFUSE_OUTPUT when no official authorisation identifier can be verified. |
| GTIN only | REVIEW_REQUIRED; never a regulatory authorisation pass. |
| Product name matches multiple registry entries | FAIL_CLOSED or REFUSE_OUTPUT until a single authorisation identifier is resolved. |
| Expired, withdrawn, suspended, selling-out, or using-out status | Preserve history; FAIL_CLOSED or REVIEW_REQUIRED for current-compliance output according to policy. |
| Active substance found but product authorisation missing | FAIL_CLOSED for product-authorisation identity. |
| Source stale or `accessedAt` missing | REVIEW_REQUIRED; prefer REFUSE_OUTPUT for high-consequence current views. |
| Registry unavailable at output time | REFUSE_OUTPUT for PassportView; DocumentAssembly may annex the failure trace. |
| Product bound to wrong jurisdiction | FAIL_CLOSED. |
| Required ReferenceSnapshot missing | FAIL_CLOSED. |
| Prescription product identity differs from as-applied product identity | REVIEW_REQUIRED; do not flatten into one identity. |

## 7. Output behavior

A high-consequence PassportView may rely on the profile only when:

- the profile is active;
- the authorisation binding uses the mandatory jurisdictional source;
- a ReferenceSnapshot exists and has a current access basis;
- an ExternalRegistryVerificationTrace records `PASS`;
- candidate count and selected identifier are unambiguous;
- status/date context supports the currentness claim;
- required label/certificate correlation is present when the output claims label-level compliance;
- no blocking discrepancy exists.

DocumentAssembly may include annexes when PassportView is refused. Annexes must clearly mark unresolved, failed, or unavailable verification traces and must not promote the annexed material into accepted compliance truth.

## 8. Non-claims

This RFC does not claim:

- legal advice;
- live registry integration;
- production runtime readiness;
- external-standard readiness;
- Slovenia profile closure;
- baseline harmonisation;
- livestock scope expansion.

## 9. Machine contracts and conformance

This RFC is supported by:

- `03_machine_contracts/schemas/evidence/OFARM_ExternalRegistryVerificationTrace_schema_v0_1.json`
- `04_implementation_and_conformance/examples_and_fixtures/examples/machine_contracts/agronomic/OFARM_AgronomicCodeBindingProfile_example_be_crop_protection_authorisation_currentness_v0_1.json`
- `04_implementation_and_conformance/examples_and_fixtures/examples/machine_contracts/agronomic/OFARM_AgronomicIdentityBinding_example_crop_protection_product_be_authorisation_verified_v0_1.json`
- `04_implementation_and_conformance/examples_and_fixtures/examples/machine_contracts/agronomic/OFARM_AgronomicIdentityBinding_example_crop_protection_product_be_gtin_only_review_required_v0_1.json`
- `04_implementation_and_conformance/examples_and_fixtures/examples/machine_contracts/agronomic/OFARM_AgronomicIdentityBinding_example_crop_protection_product_be_eu_active_substance_only_review_required_v0_1.json`
- Belgium ReferenceSnapshot examples
- ExternalRegistryVerificationTrace examples
- `04_implementation_and_conformance/historical_archive/historical_archive/historical/ofarm_external_code_binding_currentness_runner_v0_1.py`
- `04_implementation_and_conformance/historical_archive/historical_archive/historical/ofarm_operational_break_test_suite_runner_v0_1.py`

## 10. Promotion posture

The RFC is accepted as an extension and conformance closure. Baseline harmonisation remains a separate Phase 6 action after the package has accumulated sufficient support evidence.

---

## Baseline harmonisation note — ONT-SEMINT v0.3

On 2026-05-14, this RFC's supported closure was harmonised into the active RC2.1 baseline by ONT-SEMINT v0.3. The harmonisation is narrow: it incorporates the RFC's semantic-integrity rule into baseline posture while preserving all RFC non-claims around production readiness, live external registry verification, legal advice, external-standard readiness, livestock scope, and any profile-specific limitations.
