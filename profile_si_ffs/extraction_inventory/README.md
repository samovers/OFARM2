# SI Extraction Inventory

This directory is a documentation-only inventory and status area for work that moves Slovenian profile material out of Core-facing surfaces or rewrites Core-facing text so it is profile-neutral.

These documents do not move files, change runtime behavior, update contracts, update manifests, regenerate kernel outputs, or change Core, Kernel, or Platform semantics. They preserve initial inventory findings, record what has already landed, and identify which follow-up work still needs manual review.

## Scope

- Source branch assumption: `main` after PR #27 merge.
- Destination assumption: `profile_si_ffs/` remains the Slovenian profile package.
- Inventory scope: Core-facing areas such as root docs, `CORE.md`, `PLATFORM.md`, `KERNEL.md`, `contracts/`, `kernel/`, `views/`, and `conformance/`.
- Profile-local material already under `profile_si_ffs/` is treated as already in the correct package unless another document in this directory says otherwise.

## Files

- `si_core_leakage_inventory.md` records the initial Slovenian-specific Core-facing leakage snapshot for traceability.
- `si_migration_map.md` records the initial migration classification for each finding.
- `core_neutral_rewording_candidates.md` records the initial neutral wording candidates for traceability.
- `followup_pr_plan.md` records the original move-focused PR B and neutrality-hardening PR C split for traceability.
- `manual_review_backlog_plan.md` records the SI manual-review backlog status, implemented D-lane follow-ups, remaining guarded work, stop conditions, and validation expectations.
- `active_profile_loader_design.md` records the implemented D1 active-profile loader boundary for the current SI runtime descriptor.
- `evidence_policy_metadata_display_design.md` records the implemented D3 metadata/display boundary for SI sufficiency rule refs and profile-owned text.
- `validator_policy_hook_design.md` records the implemented D4 validation-policy boundary for SI-specific validator values and text.
- `test_harness_split_plan.md` records the implemented D6 test-harness boundary for profile-local SI engineering tests, demo fixtures, and root discovery bridges.
- `conformance_lane_split_plan.md` records the PR D7 boundary between root conformance, executed evidence, profile engineering tests, and profile design cases.
- `demo_fixture_migration_plan.md` records the implemented D2a-D2d demo fixture boundary and remaining D2e facade guardrails.
- `multi_profile_manifest_design.md` records the D5 manifest boundary and D5b navigation-only, non-capability index status.
- `manifest_implementation_checklist.md` records the D5a checklist and terminology for future manifest implementation work.
- `core_country_neutrality_certification_plan.md` records the planned certification track for proving Core-facing country/profile neutrality without claiming it is complete yet.
- `core_country_term_audit_allowlist_plan.md` records the planned review layer for a future country-term scan allowlist and L5 machine guard.
- `core_country_term_audit_initial_review.md` records the initial file-level review snapshot for the country-term audit hits.
- `core_country_term_audit_review_records.json` is an initial machine-readable file/glob-level review record for the seed country-term scan. The manual consistency check validates its file/glob-level hygiene. It is not a line-level allowlist and not an enforcing L5 machine guard.
- `si_extraction_practical_closeout.md` records the practical closeout decision for the SI extraction track under the current single-active-SI-runtime architecture.
- `multi_profile_runtime_boundary_plan.md` records the future multi-profile runtime boundary plan without activating a second profile or changing runtime behavior.
- `mp2_descriptor_registry_plan.md` records the docs-only MP2 descriptor registry plan for future multi-descriptor loading without activating a second profile.
- `mp3_context_policy_lookup_plan.md` records the docs-only MP3 context and policy lookup plan without changing runtime behavior, active SI behavior, or activating a second profile.
- `core_contract_comment_review_plan.md` records the docs-only review plan for neutralizing Core contract comment country-term hits without changing schema semantics.
- `profile_navigation_index.json` is a machine-labeled navigation-only, non-capability index for these profile-local inventory and status documents.

## Initial Classification Vocabulary

- `MOVE_TO_SI_PROFILE`: initial candidate for relocation into `profile_si_ffs/`.
- `REWORD_CORE_GENERICALLY`: initial candidate for neutral Core-facing wording without moving code or data.
- `KEEP_IN_CORE_AS_GENERIC_WITH_EXAMPLE_REMOVED`: initial finding where the Core-facing concept could stay, but Slovenian examples should be removed or moved.
- `AMBIGUOUS_MANUAL_REVIEW`: may affect tests, manifests, runtime bootstrapping, or intended pilot behavior; do not move blindly.
- `DO_NOT_TOUCH`: already correctly placed, protected by prior governance, or outside the intended extraction.

## Validation Intent

Run the package checks and diff hygiene checks after changes. The manual `rg` audit is an inventory input: hits are expected and should be reviewed against the tables here, not treated as automatic failures.
