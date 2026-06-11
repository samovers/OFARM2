# OFARM Kernel / Core / Platform Implementation Profile v0.1

Date: 2026-06-11
Status: supporting implementation note — implementation/conformance lane material, **not active OFARM law**
Change class: implementation/conformance packaging implication; no baseline rewrite, no RFC, no contract promotion

## Declaration

OFARM Kernel, OFARM Core, and OFARM Platform are an **implementation and conformance packaging profile** extracted from active OFARM law. They do not create a new source of authority and do not override the Constitution, accepted RFCs, companion artifacts, or machine contracts. The active baseline's semantic layers, artifact families, model law, runtime law, and conformance expectations remain the only authority; this profile is a packaging of them for implementation work.

- **Kernel** — reusable OFARM truth, authority, event, evidence, review, materialization, refusal, and trace substrate.
- **Core** — crop-farming domain semantics carried on that substrate.
- **Platform** — one concrete runtime/product that enforces both.

Whether "Kernel/Core" becomes official OFARM terminology is a decision reserved for the single consolidated post-pilot amendment, informed by whether the split survives implementation.

## Package location

`04_implementation_and_conformance/ofarm2_implementation_package/` — self-contained, designed to be lifted into its own repository. Extracted files are byte-identical to canonical sources (digest manifests included); new contracts are candidate artifacts per Constitution RC2.1 §6.16, **not** additions to the current/default schema lane and not currentness actions.

## Profile rulings recorded here (accepted during pre-implementation review)

1. **Twin metadata:** Kernel records carry target-twin / use-class / commit-class / review-state / promotion-state metadata sufficient to prevent Advisory material from becoming Compliance truth without a governed bridge. Not every substrate record is intrinsically COMPLIANCE or ADVISORY; `targetTwin` is required exactly where the contracts require it.
2. **Commit class:** remains on the ingress/result/trace boundary (`CommitIngressRequest`, `CommitIngressResult`, `PromotionTrace`), not on `AssertionRecord`. The store enforces: every authoritative record reachable from exactly one `PromotionTrace`. No schema revision.
3. **`ReviewDecision` reclassification:** logically Kernel truth/review material; canonical schema path preserved until contract indexes and maps are updated post-pilot. The package carries a verbatim copy.
4. **National identifiers:** KMG-MID, GERK, and FITO-INFO bind through the Slovenia pilot profile's governed identity/code-binding and reference-snapshot artifacts — profile law, never universal Core law.
5. **Query law:** not deferred. Platform v1 ships predefined, versioned query/view artifacts preserving reconstruction, freshness, authority, and output-disposition law; only the public authoring/compiler surface is unsupported.
6. **Pilot claim scope:** record-keeping completeness, not current-compliance (per the canonical Belgium-vs-Slovenia currentness research).
7. **Review on one-person farms:** policy-governed self-review for routine operation claims with a mechanically enforced evidence floor; insufficient for certification-grade claims; software-agent review reserved as a Phase-2 candidate.
8. **Operation contract:** deliberately not cut in v1; the event + execution-payload chain is the single representation until the post-pilot amendment decides.

## Non-claims

This note does not claim baseline amendment, contract promotion, currentness change, production readiness, external-standard readiness, or legal advice. The package's `ERRATA.md` is the sole accumulation point for implementation findings during the law freeze.
