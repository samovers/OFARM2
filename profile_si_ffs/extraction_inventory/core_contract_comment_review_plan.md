# Core Contract Comment Review Plan

Status: documentation-only contract-comment review plan. This file does not
edit contracts, change schemas, update manifests, regenerate outputs, alter
runtime behavior, alter tests, certify Core, or change Core, Kernel, or Platform
semantics.

This plan follows `core_country_term_audit_initial_review.md`, which classifies
the remaining Core contract country-term hits as `CONTRACT_COMMENT_REVIEW`.

## Scope

Review only these current country-term hits:

| Contract | Current country-term hit | Current boundary posture |
| --- | --- | --- |
| `contracts/core/OFARM_FarmIdentityPayload_schema_v0_1.json` | `KMG-MID` in the top-level `$comment`. | Already says national holding identifiers are profile-governed scheme bindings, never universal core law. |
| `contracts/core/OFARM_FieldIdentityPayload_schema_v0_1.json` | `GERK` in the top-level `$comment`. | Already says parcel identifiers are profile-governed scheme bindings with reference-snapshot support, never universal core law. |

The current comments are not known semantic leaks. They are review blockers for
country-term certification because the terms appear in Core contract files.

## Review Goal

The future goal is to decide whether the comments can be rewritten in
profile-neutral language without changing:

- schema shape;
- required fields;
- validation behavior;
- contract IDs;
- generated manifests;
- digest expectations;
- active runtime behavior;
- profile binding semantics.

Any future rewrite must preserve the existing meaning: country/profile holding
and parcel identifiers are profile-governed scheme bindings, not universal Core
law.

## Candidate Neutral Wording

These are candidates only. This PR does not apply them.

| Contract | Candidate comment fragment |
| --- | --- |
| Farm identity payload | `Profile-specific holding identifiers are profile-governed scheme bindings, never universal core law.` |
| Field identity payload | `Profile-specific parcel identifiers are profile-governed scheme bindings with reference-snapshot support, never universal core law.` |

The future implementation PR should keep the rest of each `$comment` unchanged
unless review shows another wording change is needed.

## Preconditions Before Editing Contracts

Before a future PR edits these comments, it should:

1. Confirm the change is comment-only and non-semantic.
2. Confirm no generated manifest or reference law output needs regeneration.
3. Run the contract package check before and after the edit.
4. Confirm schema IDs, titles, required fields, properties, and validation
   behavior are unchanged.
5. Run the country-term scan and show that these two Core contract hits are
   removed or reclassified.

## Stop Conditions

Stop and re-plan if the future contract-comment PR would:

- alter schema behavior or required fields;
- update generated manifests or generated outputs;
- move profile binding semantics into Core;
- hide active SI runtime support behind generic wording;
- claim Core certification before the full audit is reviewed;
- add Slovenia production readiness, Netherlands runtime readiness,
  multi-profile runtime readiness, or generated capability expansion claims.

## Validation For This Planning PR

Run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

Run the informational contract-term audit:

```sh
rg -n "KMG-MID|GERK" contracts/core/OFARM_FarmIdentityPayload_schema_v0_1.json contracts/core/OFARM_FieldIdentityPayload_schema_v0_1.json profile_si_ffs/extraction_inventory/core_contract_comment_review_plan.md
```

Expected hits remain because this PR is planning only. A later implementation PR
may remove the Core contract hits if it follows the preconditions above.
