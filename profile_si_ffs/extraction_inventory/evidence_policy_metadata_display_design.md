# Evidence Policy Metadata Display Design Memo

Status: design memo only. This document does not move code, change runtime
behavior, update contracts or manifests, alter tests, or change Core, Kernel, or
Platform semantics.

This is the PR D3 follow-up from `manual_review_backlog_plan.md`. It records the
profile policy metadata needed before `kernel/sufficiency.py` and
`kernel/profile_policy.py` can stop carrying SI-facing rule refs, claim
statements, and rationale text directly.

## Goal

Define a profile-owned metadata/display boundary for evidence sufficiency cases.

Today, the active SI profile already owns the operation-floor composition:
`hardItems` and `softItems` live in `profile_si_ffs/evidence_review_policy_v0_1.json`.
The Kernel still emits several SI-specific display values:

- `rule:si.ffs.floor.<item>` rule refs;
- `this operation claim meets the SI record-keeping evidence floor`;
- `all SI evidence-floor items satisfied`;
- floor/rationale text that assumes the active SI policy shape.

A later implementation PR should move those display and rule-ref values into
profile-owned policy metadata while preserving current behavior exactly.

## Current Surfaces

| Area | Current responsibility | D3 treatment |
| --- | --- | --- |
| `profile_si_ffs/evidence_review_policy_v0_1.json` | Owns the active SI hard/soft floor composition and advisory rule values. | Add display metadata in a later implementation PR, still profile-local and not a canonical contract. |
| `kernel/profile_policy.py` | Loads and validates the active profile policy. | Extend validation to metadata/display fields, fail-closed on malformed metadata, and expose typed helpers. |
| `kernel/sufficiency.py` | Builds `EvidenceSufficiencyCase` records and currently hard-codes SI rule refs and some SI-facing text. | Keep case-building mechanics in Kernel, but read rule refs, claim statements, labels, and rationale templates from the active profile policy. |
| `kernel/tests/test_m2_si_floor.py` | Proves floor composition is profile/package content and malformed policy fails closed. | Add metadata tests in the later implementation PR without weakening existing floor behavior. |

## Proposed Policy Metadata

A later implementation may add a profile-local metadata block to
`evidence_review_policy_v0_1.json`. This memo does not add it.

The metadata should be package content, not a canonical contract and not OFARM
Core law. It should describe display and trace identifiers only; it must not
change promotion rules, evidence requirements, authority, correction, review, or
currentness behavior.

Suggested shape:

```json
{
  "display": {
    "ruleRefPrefix": "rule:si.ffs.floor",
    "operationFloorClaimStatement": "this operation claim meets the SI record-keeping evidence floor",
    "operationFloorAllowRationale": "all SI evidence-floor items satisfied",
    "hardMissingRationaleTemplate": "evidence floor unmet: missing {missing}; the claim lacks the required durable proof for governed promotion",
    "softMissingRationaleTemplate": "floor items need review: {missing}",
    "durableProofBundleLabel": "durable proof bundle",
    "floorItems": {
      "product-binding": {
        "ruleRef": "rule:si.ffs.floor.product-binding",
        "label": "resolved product binding",
        "missingReasonCode": "AMBIGUOUS_PRODUCT_ID"
      }
    }
  }
}
```

The implementation can choose a flatter or more compact JSON shape, but it must
preserve these concepts:

- rule-ref prefix or explicit per-item rule refs;
- operation-floor claim statement;
- allow/review/refusal rationale text;
- durable-proof-bundle label;
- per-floor-item display labels;
- any item-specific insufficiency reason-code mapping that is currently emitted
  by Kernel behavior.

## Validation Rules

The future loader should fail closed when metadata is malformed. At minimum it
should validate:

- display metadata is an object when present;
- every hard/soft floor item has either an explicit rule ref or can be safely
  resolved from a valid rule-ref prefix;
- rule refs are non-empty strings and remain profile-scoped for the active
  profile;
- claim/rationale strings are non-empty strings;
- templates expose only a bounded placeholder set, such as `{missing}`;
- floor item metadata does not name items outside the kernel-supported floor
  vocabulary;
- missing reason codes, when declared, are from existing runtime problem
  vocabulary or are omitted;
- malformed metadata produces the same governed fail-closed route as malformed
  floor composition, never a crash or permissive default.

## Runtime Use

The later implementation should keep the Kernel as the generic case builder:

1. `kernel/sufficiency.py` computes the same checks it computes today.
2. `kernel/profile_policy.py` loads the active profile floor composition and
   display metadata.
3. `EvidenceSufficiencyCase.arguments[*].ruleRef` comes from metadata rather
   than `rule:si.ffs.floor.<item>` hard-coding.
4. Operation-floor claim statements and outcome rationale strings come from
   metadata with the same decisions as today.
5. If metadata is absent during the first implementation, either preserve the
   current SI strings through explicit compatibility defaults in the SI profile
   implementation path, or make metadata required in the profile file. Do not
   silently invent generic text.

## Invariants To Preserve

- The profile owns display semantics; Kernel owns generic evidence-case
  mechanics.
- Metadata is not OFARM Core law and is not a canonical contract.
- No metadata field may become a hidden truth store.
- Decisions must not change: `ALLOW`, `REQUIRE_REVIEW`, and `REFUSE` outcomes
  remain driven by the existing check results, hard/soft composition, and durable
  evidence floor.
- Existing review/refusal/correction/currentness behavior must stay unchanged.
- RVO/NL profile content, SI runtime adapters, manifests, and contracts are out
  of scope.

## Required Tests For Implementation

A later implementation PR should add tests proving:

- current SI floor cases emit the same decisions after metadata is introduced;
- rule refs are loaded from metadata;
- claim statements and allow/review/refusal rationale are loaded from metadata;
- unknown floor metadata items fail closed;
- missing metadata for a configured floor item fails closed, unless the PR
  deliberately keeps explicit SI compatibility defaults and tests them;
- malformed templates fail closed;
- changing display labels does not change promotion decisions;
- package self-check and full kernel tests still pass.

## Stop Conditions

Stop and re-plan if the implementation would require:

- canonical contract changes;
- generated manifest updates;
- new problem-code vocabulary;
- validator, authority, correction, or review behavior changes;
- moving `kernel/sufficiency.py` wholesale into the SI profile;
- broad multi-profile abstraction;
- any Slovenia production-readiness claim.

## Suggested Future PR

PR D3 implementation should be limited to:

- adding display metadata to `profile_si_ffs/evidence_review_policy_v0_1.json`;
- extending `kernel/profile_policy.py` validation/helpers;
- replacing SI hard-coded rule refs and display text in `kernel/sufficiency.py`
  with profile-policy metadata reads;
- adding focused tests for metadata loading and unchanged decisions.

Anything involving validator-owned SI policy behavior belongs to PR D4. Demo
payload movement belongs after the future profile fixture harness lane.
