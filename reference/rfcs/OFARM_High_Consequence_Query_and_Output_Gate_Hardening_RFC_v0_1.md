# OFARM High-Consequence Query and Output Gate Hardening RFC v0.1

Date: 2026-05-14  
Status: accepted RFC extension  
Change class: RFC extension + conformance implication  
Baseline impact: no direct RC2.1 baseline edit until later harmonisation

## 1. Purpose

This RFC hardens the already-accepted internal query and output reconstruction model. It prevents stale or unpinned aliases, unresolved code bindings, stale materialization, or disputed records from silently driving high-consequence outputs.

## 2. Alias pinning rule

A `QuerySpecification` must use version-pinned aliases when any of the following apply:

- `status` is `APPROVED` and the target is Compliance Twin;
- `resultProfile.mode` is `PASSPORT_INPUT`, `DOCUMENT_ASSEMBLY_INPUT`, or equivalent view/module input for PassportView or compliance dossier;
- `reconstructionPolicyRef` is present;
- the query is used at a publication/export gate;
- the query feeds a high-consequence PassportView, DocumentAssembly, compliance output, or regulated submission.

For such queries, each `semanticPathAliases[]` item must carry `aliasVersionRef`.

## 3. Output gate package

Before high-consequence output, the runtime must have or be able to produce:

- reference-resolution report;
- alias-resolution trace;
- reconstruction policy and trace;
- materialization freshness check;
- code-binding status/currentness check;
- geometry/partial-extent policy check;
- dispute/correction policy check;
- evidence-sufficiency outcome;
- authority decision outcome.

## 4. Output behavior

If any required gate is unresolved, stale, ambiguous, or conflicting, the output must be `REQUIRE_REVIEW` or `REFUSE_OUTPUT` according to policy. It must not pass silently.

`PassportView` and `DocumentAssembly` remain distinct output classes. DocumentAssembly may annex unresolved/disputed material without promoting it. PassportView must not represent unresolved/disputed material as accepted truth.

## 5. Non-claims

This RFC does not define a public query language. It hardens the internal `QuerySpecification`, `QueryPlanIR`, alias catalog, alias-resolution trace, reconstruction policy, and reconstruction trace chain.

---

## Baseline harmonisation note — ONT-SEMINT v0.3

On 2026-05-14, this RFC's supported closure was harmonised into the active RC2.1 baseline by ONT-SEMINT v0.3. The harmonisation is narrow: it incorporates the RFC's semantic-integrity rule into baseline posture while preserving all RFC non-claims around production readiness, live external registry verification, legal advice, external-standard readiness, livestock scope, and any profile-specific limitations.
