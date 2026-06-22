# Evidence Policy Metadata Display Status

Status: implemented boundary memo. The metadata boundary described here is
implemented by `profile_si_ffs/evidence_review_policy_v0_1.json` plus generic
loader/use code in Kernel. This file does not change runtime behavior, define
OFARM law, update contracts or generated manifests, alter tests, regenerate
evidence, or claim Slovenia production readiness.

This began as the PR D3 follow-up from `manual_review_backlog_plan.md`. It now
records the implemented profile policy metadata/display boundary for SI
operation-floor sufficiency cases.

## Goal

Record the profile-owned metadata/display boundary for evidence sufficiency
cases.

The active SI profile owns the operation-floor composition and display metadata:
`hardItems`, `softItems`, display strings, rule refs, item labels, and selected
reason-code mappings live in
`profile_si_ffs/evidence_review_policy_v0_1.json`.

The Kernel still owns generic evidence-case mechanics. It computes floor checks,
builds `EvidenceSufficiencyCase` records, and reads profile-owned policy data
through `kernel/profile_policy.py`.

## Implemented Boundary

| Area | Current responsibility | Implemented D3 treatment |
| --- | --- | --- |
| `profile_si_ffs/evidence_review_policy_v0_1.json` | Owns the active SI hard/soft floor composition, advisory rule values, and display metadata. | Contains `display` metadata for rule refs, claim statements, rationale templates, durable-proof label, floor item labels, and floor item reason-code mappings. |
| `kernel/profile_policy.py` | Loads and validates the active profile policy. | Validates display metadata fail-closed and exposes typed helpers such as `operation_floor_display`, `floor_item_rule_ref`, and `format_display_template`. |
| `kernel/sufficiency.py` | Builds `EvidenceSufficiencyCase` records. | Reads rule refs, claim statements, rationale strings, durable-proof label, and selected reason codes from active profile display metadata. |
| `profile_si_ffs.tests.m2_si_floor_tests` | Profile-local engineering tests for SI floor policy behavior. | Proves display metadata is sourced from package content, malformed metadata fails closed, and clean operation claims keep the same decisions. |

## Implemented Policy Metadata

The D3 implementation adds a profile-local `display` block to
`evidence_review_policy_v0_1.json`.

The metadata is package content, not a canonical contract and not OFARM Core
law. It describes display and trace identifiers only; it does not change
promotion rules, evidence requirements, authority, correction, review, or
currentness behavior.

Implemented metadata concepts:

- `ruleRefPrefix` for profile-scoped operation-floor rule refs;
- `operationFloorClaimStatement`;
- `operationFloorAllowRationale`;
- `hardMissingRationaleTemplate`;
- `softMissingRationaleTemplate`;
- `durableProofBundleLabel`;
- `floorItems` metadata keyed by the active floor item names;
- per-floor-item `ruleRef` and `label`;
- optional per-floor-item `insufficiencyReasonCode` and `reviewReasonCode`
  mappings where the runtime already emits those codes.

## Validation Rules

The loader fails closed with `ProfilePolicyError` when display metadata is
malformed. The implemented validation checks that:

- display metadata is a JSON object;
- required display text fields are non-empty strings;
- `ruleRefPrefix` is a valid rule ref prefix and starts with `rule:`;
- rationale templates expose only the bounded `{missing}` placeholder;
- `display.floorItems` is a JSON object;
- every configured hard/soft floor item has metadata;
- display metadata does not name non-floor items;
- per-item rule refs are non-empty, grammar-valid strings under the configured
  rule-ref prefix;
- optional insufficiency and review reason codes are from registered runtime
  vocabularies;
- malformed metadata produces the same governed fail-closed route as malformed
  floor composition, never a permissive default.

## Runtime Use

The Kernel remains the generic case builder:

1. `kernel/sufficiency.py` computes the same operation-floor checks.
2. `kernel/profile_policy.py` loads the active profile floor composition and
   display metadata.
3. `EvidenceSufficiencyCase.arguments[*].ruleRef` comes from metadata.
4. Operation-floor claim statements and outcome rationale strings come from
   metadata.
5. Missing or malformed display metadata is not optional for the active profile;
   it fails closed before sufficiency can silently invent generic text.

## Invariants To Preserve

- The profile owns display semantics; Kernel owns generic evidence-case
  mechanics.
- Metadata is not OFARM Core law and is not a canonical contract.
- No metadata field may become a hidden truth store.
- Decisions must not change: `ALLOW`, `REQUIRE_REVIEW`, and `REFUSE` outcomes
  remain driven by the existing check results, hard/soft composition, and
  durable evidence floor.
- Existing review/refusal/correction/currentness behavior must stay unchanged.
- RVO/NL profile content, SI runtime adapters, manifests, and contracts are out
  of scope.

## Implemented Test Coverage

D3 coverage proves:

- current SI floor cases emit the same decisions with metadata in place;
- rule refs are loaded from metadata;
- claim statements and allow/review/refusal rationale are loaded from metadata;
- missing display metadata fails closed;
- unknown floor metadata items fail closed;
- missing metadata for a configured floor item fails closed;
- malformed templates fail closed;
- invalid rule refs and out-of-scope rule refs fail closed;
- invalid display reason codes fail closed;
- changing display labels does not change promotion decisions.

## Stop Conditions For Future Work

Stop and re-plan if later work would require:

- canonical contract changes;
- generated manifest updates;
- new problem-code vocabulary;
- validator, authority, correction, or review behavior changes;
- moving `kernel/sufficiency.py` wholesale into the SI profile;
- broad multi-profile abstraction;
- any Slovenia production-readiness claim.

## Implemented D3 Scope

The implemented scope is limited to:

- adding display metadata to `profile_si_ffs/evidence_review_policy_v0_1.json`;
- extending `kernel/profile_policy.py` validation/helpers;
- replacing SI hard-coded rule refs and display text in `kernel/sufficiency.py`
  with profile-policy metadata reads;
- adding focused tests for metadata loading and unchanged decisions.

Validator-owned SI policy behavior is tracked separately in
`validator_policy_hook_design.md`. Demo fixture status is tracked separately in
`demo_fixture_migration_plan.md`.

## Validation Expectations

For documentation-only status updates to this file, run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

For implementation PRs touching profile policy display metadata, sufficiency
case generation, or profile policy validation, also run:

```sh
.venv/bin/python -m pytest kernel/tests/ -q
```
