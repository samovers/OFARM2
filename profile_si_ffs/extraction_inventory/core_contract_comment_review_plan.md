# Core Contract Comment Review Plan

Status: documentation-only contract-comment review record. This file does not
define schema behavior, update manifests, regenerate outputs, alter runtime
behavior, alter tests, certify Core, or change Core, Kernel, or Platform
semantics.

This record follows `core_country_term_audit_initial_review.md`, which classifies
the remaining Core contract country-term hits as `CONTRACT_COMMENT_REVIEW`.
The reviewed comments have since been neutralized without changing schema
semantics.

## Scope

Review only these former country-term hits:

| Contract | Former country-term hit | Applied neutral wording |
| --- | --- | --- |
| `contracts/core/OFARM_FarmIdentityPayload_schema_v0_1.json` | `KMG-MID` in the top-level `$comment`. | `Profile-specific holding identifiers are profile-governed scheme bindings, never universal core law.` |
| `contracts/core/OFARM_FieldIdentityPayload_schema_v0_1.json` | `GERK` in the top-level `$comment`. | `Profile-specific parcel identifiers are profile-governed scheme bindings with reference-snapshot support, never universal core law.` |

The former comments were not known semantic leaks. They were review blockers for
country-term certification because the terms appeared in Core contract files.
The applied neutral wording preserves the existing boundary while removing those
Core contract seed-term hits.

## Review Decision

The comments can be rewritten in profile-neutral language without changing:

- schema shape;
- required fields;
- validation behavior;
- contract IDs;
- generated manifests;
- digest expectations;
- active runtime behavior;
- profile binding semantics.

Any future rewrite must continue to preserve the existing meaning:
country/profile holding
and parcel identifiers are profile-governed scheme bindings, not universal Core
law.

## Applied Neutral Wording

The neutral wording is now applied in the two contract comments.

| Contract | Applied comment fragment |
| --- | --- |
| Farm identity payload | `Profile-specific holding identifiers are profile-governed scheme bindings, never universal core law.` |
| Field identity payload | `Profile-specific parcel identifiers are profile-governed scheme bindings with reference-snapshot support, never universal core law.` |

The rest of each `$comment` remains unchanged.

## Preconditions Satisfied

The neutralization PR should confirm these conditions:

1. The change is comment-only and non-semantic.
2. No generated manifest or reference law output needs regeneration.
3. Run the contract package check before and after the edit.
4. Confirm schema IDs, titles, required fields, properties, and validation
   behavior are unchanged.
5. Run the country-term scan and show that these two Core contract hits are
   removed.

## Stop Conditions

Stop and re-plan if any later contract-comment PR would:

- alter schema behavior or required fields;
- update generated manifests or generated outputs;
- move profile binding semantics into Core;
- hide active SI runtime support behind generic wording;
- claim Core certification before the full audit is reviewed;
- add Slovenia production readiness, Netherlands runtime readiness,
  multi-profile runtime readiness, or generated capability expansion claims.

## Validation For This Comment-Neutralization PR

Run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

Run the informational contract-term audit:

```sh
rg -n "KMG-MID|GERK" contracts/core/OFARM_FarmIdentityPayload_schema_v0_1.json contracts/core/OFARM_FieldIdentityPayload_schema_v0_1.json profile_si_ffs/extraction_inventory/core_contract_comment_review_plan.md
```

Expected hits should remain only in this review record, not in the two Core
contract files.
