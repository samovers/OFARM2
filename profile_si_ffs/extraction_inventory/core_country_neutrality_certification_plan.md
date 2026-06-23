# Core Country/Profile Neutrality Certification Plan

Status: documentation-only certification plan. This file does not certify Core
yet, move files, change runtime behavior, update contracts, update generated
outputs, alter tests, or change Core, Kernel, or Platform semantics.

This plan turns the SI extraction work into an explicit endgame for certifying
that OFARM Core-facing surfaces are country/profile agnostic. It is profile-local
planning material under `profile_si_ffs/` because it follows the Slovenian
extraction inventory. It is not Slovenia production readiness, not multi-profile
runtime readiness, and not a capability expansion.

## Certification Meaning

Core is country/profile agnostic when Core-facing surfaces define OFARM
mechanisms and invariants without embedding country law, country authorities,
profile evidence sources, profile identifiers, profile fixtures, or profile
policy text as canonical truth.

Country/profile-specific material belongs in a profile package or in explicitly
labeled active-runtime support for the current SI pilot. Core and Kernel may
own generic mechanisms such as assertion/history-first truth, governed
current-state materialization, freshness checks, evidence sufficiency mechanics,
validation order, refusal/review/correction routing, and artifact grounding.
Profiles own legal sources, authority names, profile identifiers, reference
data, evidence-source names, display text, fixtures, adapters, and policy values.

An active SI pilot reference is not automatically a neutrality failure if it is
needed by the current runtime, is explicitly labeled as active-runtime SI
support, and is not presented as Core law or general OFARM behavior.

## Lane Vocabulary

| Lane | Meaning |
| --- | --- |
| `APPARENTLY_NEUTRAL_PENDING_AUDIT` | The surface appears profile-neutral but is not certified until the audit and allowlist review are complete. |
| `PROFILE_LOCAL` | The material already lives under a profile package or is only a profile-local pointer. |
| `ACTIVE_RUNTIME_SI_SUPPORT` | The surface still carries SI-specific runtime content because the active pilot is SI-specific. It must stay explicit and must not be generalized by implication. |
| `NEEDS_PROFILE_LOADER_OR_HARNESS` | Future movement depends on loader, fixture, test, or evidence-harness support that does not exist yet. |
| `COMMENT_ONLY_NEUTRALIZATION` | Only explanatory comments or docs appear to need neutral wording; no behavior change is intended. |
| `CONTRACT_COMMENT_REVIEW` | Contract text or comments mention SI terms and require careful review before any neutral wording change. |
| `DO_NOT_TOUCH` | The surface is protected, already correctly placed, or outside the certification move. |

## Mechanism And Content Boundary

| Root-owned mechanism | Profile-owned content |
| --- | --- |
| Assertion and history-first truth rules. | Country law, source packets, and operational guidance. |
| Governed current-state materialization. | Country authorities and appeal/review routes. |
| Freshness and transaction-time requirements. | Country or profile evidence-source names. |
| Evidence sufficiency mechanics and fail-closed loading. | Profile evidence floor values, display strings, and rule refs. |
| Validation order, refusal/review/correction routing, and invariants. | Profile validation policy values, role labels, and operator-facing text. |
| Generic adapter and verification interfaces. | Profile adapters, profile binding roles, fixtures, and demo records. |
| Generated capability grounding for the current active runtime. | Profile-local planning docs and design-only profile slices. |

## Surfaces To Certify

| Surface | Certification lane | Certification question |
| --- | --- | --- |
| `CORE.md` | `APPARENTLY_NEUTRAL_PENDING_AUDIT` | Does it define OFARM law and invariants without country identifiers, authorities, or evidence sources except neutral examples? |
| `PLATFORM.md` | `COMMENT_ONLY_NEUTRALIZATION` plus `ACTIVE_RUNTIME_SI_SUPPORT` where needed | Are any country references limited to active-runtime pilot explanation or neutralized pointers? |
| `KERNEL.md` | `APPARENTLY_NEUTRAL_PENDING_AUDIT` or `COMMENT_ONLY_NEUTRALIZATION` | Does it describe Kernel mechanisms without making SI fixtures or refs sound generic? |
| `contracts/**` | `CONTRACT_COMMENT_REVIEW` | Do schemas or comments still mention KMG-MID/GERK as examples, and can they be neutralized without changing contract semantics? |
| `kernel/**` | Mixed: see blocker table | Are SI references either profile-loaded values, profile-local adapters, explicit active-runtime SI support, or comments queued for neutralization? |
| `views/**` | `PROFILE_LOCAL` for moved SI artifacts; root pointer review | Are root view docs limited to navigation and not active capability overclaims? |
| `conformance/**` | `ACTIVE_RUNTIME_SI_SUPPORT` and `NEEDS_PROFILE_LOADER_OR_HARNESS` | Are root checks/evidence still package-wide or active SI pilot support, with profile design cases clearly separated from executed platform evidence? |
| Root `README.md` and `AGENTS.md` | `COMMENT_ONLY_NEUTRALIZATION` | Do root pointers avoid whole-Core certification, Slovenia readiness, and multi-profile runtime claims? |
| Profile pointers | `PROFILE_LOCAL` | Are profile package links navigation-only unless backed by active runtime support? |

## Likely Remaining Blockers

| Surface | Current issue | Lane | Preconditions before certification can advance |
| --- | --- | --- | --- |
| `kernel/context.py` | Active SI context spine, descriptor-backed SI profile instance loading, REGSR/GERK snapshot families, and per-farm context assembly. | `ACTIVE_RUNTIME_SI_SUPPORT` plus `NEEDS_PROFILE_LOADER_OR_HARNESS` | Multi-profile loader design, context-spine equivalence tests, and freshness/currentness regression coverage. |
| `kernel/demo.py` | Public compatibility facade for SI-shaped fictional demo payloads and bootstrap examples. | `NEEDS_PROFILE_LOADER_OR_HARNESS` | Profile fixture/demo harness that preserves root callers and privacy-safe examples. |
| `kernel/manifest.py` | Generated active SI pilot artifact grounding and capability checks. | `ACTIVE_RUNTIME_SI_SUPPORT` | Separate multi-profile generated-output design, active descriptors, and evidence lanes before any runtime capability expansion. |
| `kernel/tests/**` | Mix of generic mechanism tests, root bridges, and active SI pilot tests. | `NEEDS_PROFILE_LOADER_OR_HARNESS` | Machine check that profile-local tests are reachable from root collection, and no loss of current regression coverage. |
| `conformance/evidence/**` | Executed platform evidence is root-owned and currently active-pilot grounded. | `ACTIVE_RUNTIME_SI_SUPPORT` | Approved profile evidence writer and suite id before any profile-local executed evidence lane. |
| Root platform evidence writer | Produces root platform evidence, not profile-local evidence. | `ACTIVE_RUNTIME_SI_SUPPORT` | Profile evidence-lane design that avoids relabeling existing evidence. |
| Contract comments mentioning KMG-MID/GERK | SI examples may remain in Core contract comments. | `CONTRACT_COMMENT_REVIEW` | Contract review that proves wording changes are non-semantic and do not update schemas or manifests. |
| Active SI pilot runtime assumptions | Current runtime remains the SI pilot. | `ACTIVE_RUNTIME_SI_SUPPORT` | A later runtime plan must externalize profile content without hiding current active behavior. |

## Certification Levels

| Level | Name | Exit criteria |
| --- | --- | --- |
| L0 | Inventory exists | Country/profile-specific Core-facing hits are recorded and mapped. |
| L1 | Docs neutralized | Core-facing prose no longer presents country/profile content as generic OFARM law. |
| L2 | Profile artifacts moved or pointed | Profile-owned artifacts live under profile packages, or root surfaces point to them without capability overclaim. |
| L3 | Tests and harness separated | Profile-specific engineering tests, fixtures, and design cases are separated or bridged without coverage loss. |
| L4 | Runtime profile content externalized | Active runtime profile values are loaded from profile-owned content, while Kernel keeps only generic mechanisms. |
| L5 | Machine guard enforced | A repeatable audit blocks new unclassified country/profile terms in Core-facing surfaces. |

Current status is below L5. This file is a planning artifact for reaching that
end state, not proof that the end state has been reached.

## Proposed Machine Audit

Use an `rg`-based country-term scan as the first machine guard:

```sh
rg -n "KMG-MID|GERK|REGSR|FFSNaprave|Slovenia|Slovenian|\bSI\b|Dutch GO|GLMC 7|Gecombineerde Opgave" CORE.md PLATFORM.md KERNEL.md contracts kernel views conformance README.md AGENTS.md
```

The audit should fail only after an allowlist/review layer exists. Until then,
it is a manual certification input.

Allowed hits must be classified as one of:

- profile-local pointers;
- explicit active-runtime SI support;
- contract comments under review;
- conformance evidence history;
- root navigation or review guards;
- country-neutral wording that happens to mention the term as a prohibited or
  historical example.

The audit goal is: no country law, country authority, profile evidence source,
profile identifier, or profile fixture may appear in Core, Kernel, Platform, or
root conformance as hidden canonical truth.

## Non-Claims

This plan must not be read as claiming:

- whole-Core country/profile neutrality is already certified;
- multi-profile runtime readiness;
- Slovenia production readiness;
- Netherlands runtime readiness;
- generated capability expansion;
- platform production readiness;
- any weakening of assertion/history-first truth, governed materialization,
  evidence, review, correction, freshness, refusal, or authority rules.

## Files Not To Touch For This Planning PR

- `contracts/**`;
- `kernel/**`;
- runtime behavior;
- generated outputs or generated manifests;
- `conformance/evidence/**`;
- `profile_nl_go_glmc7_2026/**`;
- `reference/**`;
- active baseline law copies.

## Validation

Run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

Run the manual audit:

```sh
rg -n "KMG-MID|GERK|REGSR|FFSNaprave|Slovenia|Slovenian|\bSI\b|Dutch GO|GLMC 7|Gecombineerde Opgave" CORE.md PLATFORM.md KERNEL.md contracts kernel views conformance README.md AGENTS.md profile_si_ffs/extraction_inventory/core_country_neutrality_certification_plan.md
```

The audit is informational for this PR. Hits are expected and should be checked
against the lanes in this document.

## Definition Of Done For Certification

Core country/profile neutrality is certified only when all of the following are
true:

1. Every Core-facing country/profile hit is removed, profile-local, or assigned
   to an explicit allowed lane.
2. Core, Kernel, and Platform contain no country law, country authority,
   profile evidence source, profile identifier, or profile fixture as hidden
   canonical truth.
3. Active SI runtime support is either externalized into profile-owned content
   or clearly labeled as current active-runtime support with regression tests.
4. Profile-specific tests, fixtures, views, and design cases are profile-local
   or bridged through an approved harness without coverage loss.
5. Contract comments have been reviewed without changing contract semantics.
6. Root conformance evidence and any profile-local evidence lanes are clearly
   separated.
7. A machine guard enforces the country-term allowlist in CI or an equivalent
   required validation path.
8. No certification artifact claims multi-profile runtime readiness, Slovenia
   production readiness, Netherlands runtime readiness, or generated capability
   expansion unless separately implemented and proven.
