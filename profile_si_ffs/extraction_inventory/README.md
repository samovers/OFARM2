# SI Extraction Inventory

This directory is a documentation-only inventory for future work that moves Slovenian profile material out of Core-facing surfaces or rewrites Core-facing text so it is profile-neutral.

This PR does not move files, change runtime behavior, update contracts, update manifests, regenerate kernel outputs, or change Core, Kernel, or Platform semantics. It records what is visible today and separates safe follow-up work from items that need manual review.

## Scope

- Source branch assumption: `main` after PR #27 merge.
- Destination assumption: `profile_si_ffs/` remains the Slovenian profile package.
- Inventory scope: Core-facing areas such as root docs, `CORE.md`, `PLATFORM.md`, `KERNEL.md`, `contracts/`, `kernel/`, `views/`, and `conformance/`.
- Profile-local material already under `profile_si_ffs/` is treated as already in the correct package unless another document in this directory says otherwise.

## Files

- `si_core_leakage_inventory.md` lists observed Slovenian-specific material visible from Core-facing areas.
- `si_migration_map.md` classifies each finding as move, generic rewording, keep-with-example-removed, manual review, or do-not-touch.
- `core_neutral_rewording_candidates.md` proposes neutral replacement wording for later PRs.
- `followup_pr_plan.md` splits follow-up work into a move-focused PR B and a neutrality-hardening PR C.
- `manual_review_backlog_plan.md` expands the ambiguous/manual-review backlog into future design lanes, required preconditions, stop conditions, and validation expectations.
- `active_profile_loader_design.md` records the implemented D1 active-profile loader boundary for the current SI runtime descriptor.
- `evidence_policy_metadata_display_design.md` records the implemented D3 metadata/display boundary for SI sufficiency rule refs and profile-owned text.
- `validator_policy_hook_design.md` records the implemented D4 validation-policy boundary for SI-specific validator values and text.
- `test_harness_split_plan.md` records the implemented D6 test-harness boundary for profile-local SI engineering tests, demo fixtures, and root discovery bridges.
- `conformance_lane_split_plan.md` records the PR D7 boundary between root conformance, executed evidence, profile engineering tests, and profile design cases.
- `demo_fixture_migration_plan.md` records the implemented D2a-D2d demo fixture boundary and remaining D2e facade guardrails.
- `multi_profile_manifest_design.md` records the D5 manifest boundary and D5b navigation-only, non-capability index status.
- `manifest_implementation_checklist.md` records the D5a checklist and terminology for future manifest implementation work.
- `profile_navigation_index.json` is a machine-labeled navigation-only, non-capability index for these profile-local planning documents.

## Classification Vocabulary

- `MOVE_TO_SI_PROFILE`: candidate for relocation into `profile_si_ffs/` in a later PR.
- `REWORD_CORE_GENERICALLY`: candidate for neutral Core-facing wording without moving code or data.
- `KEEP_IN_CORE_AS_GENERIC_WITH_EXAMPLE_REMOVED`: Core-facing concept can stay, but Slovenian examples should be removed or moved.
- `AMBIGUOUS_MANUAL_REVIEW`: may affect tests, manifests, runtime bootstrapping, or intended pilot behavior; do not move blindly.
- `DO_NOT_TOUCH`: already correctly placed, protected by prior governance, or outside the intended extraction.

## Validation Intent

Run the package checks and diff hygiene checks after changes. The manual `rg` audit is an inventory input: hits are expected and should be reviewed against the tables here, not treated as automatic failures.
