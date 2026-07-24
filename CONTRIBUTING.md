# Contributing to OFARM2

OFARM2 changes should be minimal, coherent, clear, and manageable for both
humans and AI. A pull request solves one defined problem, preserves its stated
invariants, and contains only the smallest coherent change needed to do so.

Success means OFARM2 becomes more capable, reliable, and understandable without
unnecessary complexity. Each merged change must deliver a clear capability,
reduce a demonstrated risk, or validate an architectural decision. Before
deployment, a later redesign is acceptable when it is supported by evidence
and improves the platform.

## Before implementation

Start with [the OFARM2 task prompt](TASK_PROMPT.md).

Name one problem and one primary trust boundary. Keep implementation, tests,
documentation, and necessary mechanical integration inside that boundary. If
work in another trust boundary becomes necessary, stop before editing it and
propose a separate prerequisite, Follow-up, or stacked pull request.

Use the complete Phase A design contract for trust-boundary or authority
changes. Use the routine contract for documentation and mechanical work that
does not change authority. Do not begin a task that has no learning value:
every change must deliver a capability, reduce a demonstrated risk, or validate
an architectural decision.

Prefer deletion, direct code paths, explicit boundary contracts, immutable
values, and small modules over framework layers, speculative abstractions,
compatibility shims, and duplicate validation.

## Pull request contract

Every pull request must complete
[the pull request template](.github/PULL_REQUEST_TEMPLATE.md) with:

- **Problem:** the one problem being solved.
- **Acceptance criteria or invariants:** falsifiable conditions proving it is
  solved.
- **Out of scope:** adjacent systems and future concerns excluded from the
  change.
- **Smallest change:** why the implementation is the minimum coherent solution.
- **Learning value:** the capability delivered, demonstrated risk reduced, or
  architectural decision validated.
- **Provisional design record:** if temporary, why it is acceptable before
  deployment, what evidence would require redesign, and the likely upgrade
  path. Otherwise state `Not provisional`.
- **Follow-ups:** linked issues created instead of expanding the pull request,
  or `None`.
- **Verification:** the smallest tests or checks needed for the stated
  boundary.
- **Review disposition:** remaining Blockers, Follow-ups, and Preferences.
- **Merge stop rule:** once acceptance criteria pass and no demonstrated
  Blocker remains, merge. New ideas, Preferences, and non-blocking hardening
  become Follow-ups and do not reopen review.

## Review protocol

Every review finding must use exactly one classification:

- **Blocker:** a demonstrated in-scope correctness, security, data-integrity,
  contractual, or production-safety failure. It names the violated invariant
  and the smallest acceptable fix.
- **Follow-up:** valid work outside the pull request boundary. Record it as a
  linked issue or small future pull request; do not expand the current change.
- **Preference:** optional style or alternative-design advice. It never delays
  merging.

Only Blockers delay a merge. Preferences, hypothetical risks, and unrelated
hardening are not required changes.

When a Blocker is fixed, recheck only the fix and affected invariant. Do not
restart open-ended design or threat review unless new evidence demonstrates
that the original scope is unsafe.

## Three-pull-request pilot

Apply this protocol manually to the next three substantive platform pull
requests after the governance change merges. Process-only and trivial
documentation pull requests do not count.

For each pilot pull request:

- Declare one problem, one primary trust boundary, and learning value before
  implementation.
- Keep implementation and verification inside that boundary.
- Classify every finding as Blocker, Follow-up, or Preference.
- Convert every Follow-up into a linked issue before merge.
- Do not make implementation commits for Preferences unless separately chosen
  as a new scoped task.
- After Blocker fixes, review only the fix and affected invariant unless new
  evidence demonstrates that the original scope is unsafe.
- Merge as soon as acceptance criteria and focused verification pass with zero
  Blockers.
- Record full reviews, Blocker-fix reviews, Follow-ups, Preference-only
  suggestions, post-review commits, and time from zero Blockers to merge in
  [governance issue #218](https://github.com/samovers/OFARM2/issues/218).

Claude may review with `samovers` credentials during the pilot. Record that as
same-account review evidence, not independent GitHub approval.

After the third pilot pull request merges, use issue #218 to decide whether to
keep, simplify, or revise the protocol based on the recorded evidence.

## Optional process improvements

CI splitting, inventory pinning, strict branch rules, auto-merge requirements,
review-attestation checks, and `CODEOWNERS` enforcement are not prerequisites.
Do not enable strict enforcement until the manual protocol has worked on
several substantive pull requests.

Consider CI splitting only if at least two pilot pull requests show that CI
duration or reruns materially delayed review or merge.

Consider inventory pinning only if generated inventory changes in at least two
pilot pull requests obscure meaningful changes, cause conflicts, or create
review errors.

Consider strict merge enforcement only if at least two pilot pull requests
violate the manual merge-stop rule, omit required contract information, or
remain open more than one business day after reaching zero Blockers.

Each optional improvement needs its own problem statement, learning value,
acceptance criteria, and evidence that it will reduce ambiguity or review
churn. Automation must not introduce more process decisions than it removes.
