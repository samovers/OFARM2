# Validator Policy Hook Design Memo

Status: implemented design memo. The metadata boundary described here is now
implemented by `profile_si_ffs/evidence_review_policy_v0_1.json` plus generic
loader/use code in Kernel. This document remains the design rationale and does
not itself define OFARM law.

This is the PR D4 follow-up from `manual_review_backlog_plan.md`. It records the
profile validation hook boundary needed before SI-specific validation posture in
`kernel/validators.py` can move into profile-owned policy content.

## Goal

Define the smallest profile-owned policy surface for validator behavior that was
SI-specific in Kernel text/posture values but remains executed by generic Kernel
validator units.

The implementation keeps the Kernel as the gate orchestrator and validator
mechanism owner. The SI profile owns the profile policy values, operator-facing
validation text, and unresolved-binding review/refusal posture where those
values are country/profile-specific.

This memo is not an authorization to move validators or invent a universal
country abstraction layer.

## Current Surfaces

| Area | Current responsibility | D4 treatment |
| --- | --- | --- |
| `kernel/validators.py` module docstring | Previously named SI unresolved-binding behavior directly. | Now points to active profile validation policy while keeping the active SI pilot context visible. |
| `CarrierSemanticsValidator` | Enforces the SI quantity/unit policy: dose/rate parameters need UCUM unit code and quantity kind; implausible values route to review. | Keep validator mechanics in Kernel; move required quantity policy and messages into active profile validation policy. |
| `ExecutionExtentValidator` | Treats "size treated" as an SI required record field for non-whole extents. | Keep extent-bound mechanics in Kernel; move required record-field label/text into active profile validation policy. |
| `CodeBindingValidator` | Routes missing/unverified product binding and missing crop binding according to SI unresolved-binding posture. | Keep binding kind checks in Kernel; move binding-role posture, reason titles/text, and review/refusal disposition into profile validation policy. |
| `RegistryReverificationValidator` | Uses active SI REGSR snapshot semantics and decision-number reverification language. | Leave unchanged in D4 unless a later profile hook covers registry-family reverification policy. |
| `profile_si_ffs/evidence_review_policy_v0_1.json` | Already owned sufficiency floor composition, display metadata, and advisory rules. | D4 extends this file with validation policy metadata. |

## Proposed Policy Boundary

The D4 implementation introduces profile-owned validation policy metadata by
adding a `validation` block to
`profile_si_ffs/evidence_review_policy_v0_1.json`.

The policy should describe profile values only:

- quantity policy requirements;
- field-completeness requirements and labels;
- binding-role posture for missing, unresolved, wrong-kind, or stale bindings;
- review/refusal titles and rationale templates;
- allowed reason-code mappings from the existing runtime registry;
- profile-scoped rule refs or policy refs for validator decisions when needed.

It must not define generic Kernel mechanics such as gate order, transaction
boundaries, assertion emission, materialization, authority evaluation, or
contract validation.

## Suggested Metadata Shape

This is illustrative. The implementation may choose a flatter shape if it keeps
the same boundary and fail-closed guarantees.

```json
{
  "validation": {
    "quantityAndUnit": {
      "requireQuantityKindAndUnitCode": true,
      "unresolvedReasonCode": "UNIT_UNRESOLVED",
      "unresolvedTitle": "Dose unit unresolved",
      "unresolvedRationale": "dose without resolved UCUM unit code",
      "implausibleDoseReviewReasonCode": "EVIDENCE_INSUFFICIENT",
      "implausibleDoseTitle": "Implausible dose"
    },
    "recordFields": {
      "nonWholeExtentBound": {
        "requiredLabel": "size treated",
        "missingReasonCode": "EVIDENCE_INSUFFICIENT",
        "missingTitle": "Partial extent unquantified",
        "missingRationale": "non-whole extent carries no quantified bound"
      }
    },
    "bindings": {
      "product": {
        "bindingRole": "CROP_PROTECTION_PRODUCT",
        "missingOrUnverifiedDisposition": "REVIEW",
        "reasonCode": "PRODUCT_BINDING_UNRESOLVED",
        "title": "Product binding unresolved"
      },
      "crop": {
        "bindingRole": "CROP_SPECIES",
        "missingDisposition": "REVIEW",
        "reasonCode": "IDENTITY_UNRESOLVED",
        "title": "Crop binding missing"
      },
      "wrongKindRef": {
        "disposition": "REFUSE",
        "reasonCode": "PRODUCT_BINDING_UNRESOLVED",
        "title": "Binding ref is not a binding"
      }
    }
  }
}
```

## Validation Rules

The loader fails closed with `ProfilePolicyError` when validation policy
metadata is malformed. At minimum it validates:

- validation metadata is a JSON object when enabled;
- dispositions are from the small closed set implemented in D4: `REFUSE` and
  `REVIEW`;
- wrong-kind binding references are always fixed to `REFUSE` because a field
  that names agronomic identity bindings must not point to another record kind
  and continue as review-routed input;
- reason codes are registered runtime reason codes;
- required titles, rationales, and templates are non-empty strings;
- binding roles are from the Kernel-supported binding-role vocabulary used by
  the current carrier mechanics;
- any rule refs or policy refs match the same ref grammar used by the relevant
  contracts;
- numeric ranges, if declared for dose sanity, are numbers and ordered;
- unknown validation-policy keys fail closed; the only note/extension key
  currently allowed in the validation block is top-level `_note`;
- missing policy required by the active profile never falls back to permissive
  generic behavior.

## Runtime Use

The implementation keeps the runtime behavior unchanged at first:

1. `ValidationGate` continues to run the same validators in the same order.
2. Each validator continues to return `GateRefusal`, append review-route
   `RuntimeProblem` records, or pass exactly as it does today.
3. Profile policy only supplies profile-specific values and text.
4. Malformed or missing required validation policy fails closed before a
   validator can emit an invalid or permissive outcome.
5. Existing SI pilot behavior remains the compatibility baseline until profile
   tests prove each policy-owned value is read from the profile.

## Invariants To Preserve

- Validator order remains Kernel-owned and law-pinned.
- Assertion/history-first truth is unchanged.
- Governed materialization is unchanged.
- Authority, review, correction, freshness, refusal, and evidence rules are not
  weakened.
- A validation hook must not become a hidden truth store.
- Profile policy values must not be represented as OFARM Core law.
- The active SI pilot remains active runtime support, not Slovenia production
  readiness.
- No Netherlands profile, contracts, manifests, generated outputs, or runtime
  adapters are in scope.

## Required Tests For Implementation

A later implementation PR should add tests proving:

- existing SI operation-claim validation decisions are unchanged;
- quantity/unit policy text and reason codes are loaded from profile policy;
- missing quantity kind or unresolved UCUM unit still refuses;
- implausible dose still routes to review and never silently blocks;
- missing non-whole extent bound still refuses with the existing outcome;
- wrong-kind binding refs still refuse governably;
- missing or unverified product binding still routes to review;
- missing crop binding still routes to review;
- malformed validation policy fails closed as `PROFILE_NOT_ACTIVE` or the
  already-approved profile-policy fail-closed route;
- changing display text in policy does not change decisions;
- package self-check and full kernel tests still pass.

## Stop Conditions

Stop and re-plan if implementation would require:

- contract changes;
- generated manifest changes;
- a new reason-code vocabulary;
- changes to validation gate order;
- moving `kernel/validators.py` wholesale into the SI profile;
- broad multi-profile abstraction;
- weakening refusal-over-pretending behavior;
- any Slovenia production-readiness claim.

## Implemented D4 Scope

The implementation scope is limited to:

- adding active SI validation policy metadata to profile-owned policy content;
- extending the existing profile policy loader with fail-closed validation;
- replacing SI-specific validator text/posture values with profile-policy reads;
- adding focused tests proving behavior is unchanged and malformed policy fails
  closed.

Registry-family reverification policy, demo fixture relocation, test-harness
splitting, conformance lane splitting, and multi-profile manifest design belong
to later lanes.
