# Validator Policy Hook Status

Status: implemented boundary memo. The validation-policy boundary described
here is implemented by `profile_si_ffs/evidence_review_policy_v0_1.json` plus
generic loader/use code in Kernel. This file does not change runtime behavior,
define OFARM law, update contracts or generated manifests, alter tests,
regenerate evidence, or claim Slovenia production readiness.

This began as the PR D4 follow-up from `manual_review_backlog_plan.md`. It now
records the implemented profile validation-policy boundary for SI-specific
validator values and operator-facing text.

## Goal

Record the smallest profile-owned policy surface for validator behavior that was
SI-specific in Kernel text or posture values while remaining executed by generic
Kernel validator units.

The Kernel remains the gate orchestrator and validator mechanism owner. The SI
profile owns profile policy values, operator-facing validation text, and
unresolved-binding review/refusal posture where those values are
country/profile-specific.

This memo is not an authorization to move validators or invent a universal
country abstraction layer.

## Implemented Boundary

| Area | Current responsibility | Implemented D4 treatment |
| --- | --- | --- |
| `kernel/validators.py` module docstring | Describes active profile validation policy while keeping the active SI pilot context visible. | Validator mechanics remain Kernel-owned. SI text/posture values are read through active profile policy helpers. |
| `CarrierSemanticsValidator` | Enforces quantity/unit checks for dose/rate parameters and routes implausible values to review. | Reads required quantity policy, reason codes, titles, details, rationales, and templates from active profile validation policy. |
| `ExecutionExtentValidator` | Checks non-whole execution extents for a quantified bound. | Reads required record-field label/text and refusal problem metadata from active profile validation policy. |
| `CodeBindingValidator` | Routes missing/unverified product binding, missing crop binding, and wrong-kind binding refs. | Reads binding-role posture, reason titles/text, and review/refusal disposition from active profile validation policy. |
| `RegistryReverificationValidator` | Uses active SI REGSR snapshot semantics and decision-number reverification language. | Remains unchanged by D4; any registry-family reverification policy hook belongs to a later lane. |
| `profile_si_ffs/evidence_review_policy_v0_1.json` | Owns sufficiency floor composition, display metadata, advisory rules, and validation policy metadata. | Contains the active SI `validation` block. |
| `profile_si_ffs.tests.m2_si_validation_policy_tests` | Profile-local engineering tests for validation policy behavior. | Proves values are sourced from package content, existing decisions are unchanged, and malformed policy fails closed. |

## Implemented Policy Boundary

D4 adds profile-owned validation policy metadata through the `validation` block
in `profile_si_ffs/evidence_review_policy_v0_1.json`.

The policy describes profile values only:

- quantity policy requirements;
- field-completeness requirements and labels;
- binding-role posture for missing, unresolved, wrong-kind, or stale bindings;
- review/refusal titles and rationale/detail templates;
- allowed reason-code mappings from the existing runtime registry.

It does not define generic Kernel mechanics such as gate order, transaction
boundaries, assertion emission, materialization, authority evaluation, or
contract validation.

Implemented metadata groups:

- `quantityAndUnit`;
- `recordFields.nonWholeExtentBound`;
- `bindings.wrongKindRef`;
- `bindings.product`;
- `bindings.crop`.

## Validation Rules

The loader fails closed with `ProfilePolicyError` when validation policy
metadata is malformed. The implemented validation checks that:

- validation metadata is a JSON object;
- only the supported top-level validation keys are present, with `_note` as the
  only extension/note key;
- dispositions are from the closed set implemented in D4: `REFUSE` and
  `REVIEW`;
- wrong-kind binding references are fixed to `REFUSE`;
- reason codes are registered runtime reason codes;
- required titles, rationales, details, and templates are non-empty strings;
- template placeholders are bounded to the fields each validator supplies;
- product binding role is exactly `CROP_PROTECTION_PRODUCT`;
- crop binding role is exactly `CROP_SPECIES`;
- missing policy required by the active profile never falls back to permissive
  generic behavior.

## Runtime Use

The implementation keeps runtime decisions unchanged:

1. `ValidationGate` continues to run the same validators in the same order.
2. Each validator continues to return `GateRefusal`, append review-route
   `RuntimeProblem` records, or pass exactly as before.
3. Profile policy supplies profile-specific values and text.
4. Malformed or missing required validation policy fails closed before a
   validator can emit an invalid or permissive outcome.
5. Existing SI pilot behavior remains the compatibility baseline.

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

## Implemented Test Coverage

D4 coverage proves:

- validation policy values are sourced from profile package content;
- unresolved dose/unit failures use profile validation policy text and reason
  codes;
- non-whole extent missing-bound failures use profile validation policy text and
  reason codes;
- missing or unverified product binding still routes to review through profile
  policy values;
- wrong-kind binding refs still refuse governably through profile policy values;
- malformed validation policy fails closed through the approved profile-policy
  fail-closed route;
- unknown validation-policy keys fail closed;
- product binding role must be `CROP_PROTECTION_PRODUCT`;
- crop binding role must be `CROP_SPECIES`;
- changing display text in policy does not change decisions.

## Stop Conditions For Future Work

Stop and re-plan if later work would require:

- contract changes;
- generated manifest changes;
- a new reason-code vocabulary;
- changes to validation gate order;
- moving `kernel/validators.py` wholesale into the SI profile;
- broad multi-profile abstraction;
- weakening refusal-over-pretending behavior;
- any Slovenia production-readiness claim.

## Implemented D4 Scope

The implemented scope is limited to:

- adding active SI validation policy metadata to profile-owned policy content;
- extending the existing profile policy loader with fail-closed validation;
- replacing SI-specific validator text/posture values with profile-policy reads;
- adding focused tests proving behavior is unchanged and malformed policy fails
  closed.

Registry-family reverification policy, demo fixture status, test-harness
status, conformance lane status, and multi-profile manifest design remain in
their separate lanes.

## Validation Expectations

For documentation-only status updates to this file, run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

For implementation PRs touching profile validation metadata, validator policy
reads, or validation gate behavior, also run:

```sh
.venv/bin/python -m pytest kernel/tests/ -q
```
