# Follow-Up PR Plan

This plan is for later work only. PR A is the inventory package and does not execute any move or rewording.

## PR B: Move Profile-Owned Authored Artifacts

Goal: move clearly SI-owned authored artifacts from Core-facing locations into `profile_si_ffs/` while preserving behavior and references.

Candidate work:

- Move SI view/query artifacts currently under `views/` to a profile-local destination such as `profile_si_ffs/views/`.
- Update only the references required to find those artifacts after the move.
- Keep the change documentation-only or artifact-location-only; do not change view semantics, gate behavior, runtime adapters, contracts, or manifests.
- Treat any test or loader dependency discovered during the move as a stop condition unless the same PR can preserve behavior with a narrow path update.

Out of scope for PR B:

- `kernel/context.py` active SI bootstrap extraction.
- `kernel/validators.py` or `kernel/sufficiency.py` policy refactors.
- Contract edits.
- Manifest regeneration.
- Moving `kernel/tests/**` into a new profile harness.

## PR C: Neutrality Hardening In Core-Facing Wording

Goal: remove unnecessary Slovenian examples from generic Core-facing explanations while preserving the same architecture and claim limits.

Candidate work:

- Reword `CORE.md` identity tables from KMG-MID and GERK examples to profile-specific holding and parcel identifiers.
- Reword `CORE.md` review-policy references from SI self-review policy to active-profile review policy where the sentence is generic.
- Reword `CORE.md` code-binding examples so concrete Slovenian authority/register names live only in the SI profile.
- Reword `PLATFORM.md`, `kernel/profile_policy.py`, and safe comments in `kernel/adapters.py` or `kernel/policy.py` from SI examples to active-profile wording.
- Optionally neutralize contract comments only if contract-comment-only edits are explicitly approved by maintainers.

Out of scope for PR C:

- Changing active runtime behavior.
- Changing the active SI pilot claim.
- Rewriting root README posture.
- Any change that requires generated manifest updates.

## Manual Review Backlog

These areas need design review before extraction:

- `kernel/context.py`: active SI context spine and profile bootstrap.
- `kernel/demo.py`: fictional SI examples used by demos or tests.
- `kernel/sufficiency.py`: SI evidence-floor messages and refusal rationale strings.
- `kernel/validators.py`: SI record-field and binding behavior.
- `kernel/manifest.py`: manifest metadata and generation rules.
- `kernel/tests/**`: current active-pilot tests and future profile test-harness placement.
- `conformance/**`: split between package-wide conformance and SI-profile design evidence.

## Stop Conditions

Stop and re-plan if a follow-up PR would require any of the following:

- Core, Kernel, or Platform semantic changes.
- Contract schema changes beyond explicitly approved comment-only neutralization.
- Generated manifest updates.
- Runtime adapter behavior changes.
- Loss of current SI pilot validation coverage.

