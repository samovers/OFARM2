## Delivery identity

<!-- A Tracking Epic does not receive an implementation PR. Link its selected Delivery child issue. -->

- Delivery issue:
- Tracking Epic: `None`
- Problem:
- Independently reviewable capability:
- PR posture: `Normal` / `Replaces closed-unmerged PR` / `Reopens closed-unmerged PR`
- [ ] This issue has one live implementation PR and no merged implementation PR.

## Primary trust boundary

<!-- Name one authority-level boundary. Same ownership is not enough to combine independent capabilities. -->

- Boundary:
- Containment:
- [ ] This PR contains one capability in one primary boundary with no cross-boundary waiver.

## Permitted effects, non-effects, and non-goals

### Permitted effects

- `[PERMITTED EFFECT]`

### Non-effects and non-goals

- `[EXCLUDED EFFECT, SYSTEM, OR CONCERN]`

## Acceptance criteria or invariants

<!-- Use falsifiable conditions. Use stable invariant IDs for high-risk work. -->

- [ ] `[FALSIFIABLE CONDITION]`

## Code excellence

<!-- Apply EXC-001 through EXC-007 from root AGENTS.md. Evidence, not taste, determines a Blocker. -->

- Authoritative decision path and sources of truth:
- Avoided or remaining duplicate authority, validation, state, compatibility,
  inventory, or framework paths: `None`
- Superseded paths deleted, or time-bounded duty and deletion trigger: `None`
- Direct invariant-to-implementation-to-evidence trace:
- Abstractions added and their current rent: `None`
- Simplest credible alternative and preventing invariant:
- [ ] Any code-excellence Blocker names the concrete defect, present cost,
  violated `EXC-001` through `EXC-006` invariant, and smallest correction.

## Smallest complete change

<!-- Explain why this is the minimum coherent vertical slice, not merely a small diff. -->

## Expected areas and complete vertical slice

<!-- Paths are scope evidence, not human approval authority. -->

- Expected repository areas:

| Companion | `Included` or `Not needed` | Reason or location |
| --- | --- | --- |
| Phase A or durable design navigation |  |  |
| Implementation and deletion of superseded paths |  |  |
| Owned schema or migration changes |  |  |
| Tests |  |  |
| Fixtures or compatibility bridges |  |  |
| Documentation |  |  |
| Generated inventories or mechanical evidence |  |  |

- [ ] No companion was split into an enabling-only pull request without an independently usable and testable outcome.

## Provisional posture

<!-- State "Not provisional", or complete all three lines. -->

- Status: `Not provisional`
- Acceptable before deployment because:
- Evidence requiring redesign:
- Likely upgrade path:

## Decision and precedence

<!-- These fields record navigation evidence. They do not create approval; only the same-task task-user message can do that. -->

- Risk class: `Routine` / `High-risk` / `Otherwise approval-governed`
- Phase A location: `PR description` / `[RFC OR ADR]` / `Not required`
- Decision identity and version: `Not required`
- Approval navigation: `Not required`
- Stronger accepted exact-action requirements: `None`
- Ambiguous process precedence: `No` / `Stopped pending explicit amendment`

## High-risk trust floor

<!-- Complete or link the trust-floor fields for high-risk work. An authority map is also required whenever work changes, relies on, or exercises authority. State "Not applicable" only when the field truly does not apply. -->

- Protected assets: `Not applicable`
- Trusted sides or components: `Not applicable`
- Untrusted actors, sides, or inputs: `Not applicable`
- Excluded attacker capabilities: `Not applicable`
- Primary risk and containment rule: `Not applicable`
- Authority map: `Not applicable`
- Production-reachable negative cases: `Not applicable`
- Invariant-to-implementation-to-test traceability: `Not applicable`

## Abandoned-PR recovery

<!-- Complete only for replacement or reopening. A merged predecessor is never eligible. -->

- Previous closed-unmerged PR: `Not applicable`
- Recovery mode: `Replacement` / `Reopening` / `Not applicable`
- Reciprocal supersession links: `Not applicable`
- New decision version and approval navigation: `Not applicable`
- [ ] No approval, review, admission, check, baseline, publication, or receipt evidence was reused.
- [ ] The predecessor is unmerged.

## Follow-ups

<!-- Link separate Delivery work instead of expanding this PR, or state "None". -->

- `None`

## Verification and review

<!-- Root AGENTS.md owns exact admission and publication controls; record results here without redefining them. -->

- Candidate full SHA:
- Cheap checks and results:

| Classification | Finding or `None` | Evidence, smallest fix, or Delivery issue |
| --- | --- | --- |
| Blocker | None | |
| Follow-up | None | |
| Preference | None | |

- Exact-head review reference:
- Admission and hosted baseline reference: `Not required under root AGENTS.md — basis:`
- Authoritative publication and receipt reference: `Not required under root AGENTS.md — basis:`

## Final semantic scope and cancellation check

- Final changed paths:
- Material diff summary:
- Permitted effects, non-effects, and unresolved Follow-ups:
- Phase A deviations and semantic-preservation evidence: `None`
- Newly discovered paths and in-boundary explanation: `None`
- [ ] Every changed path preserves the approved capability, primary boundary, authority map, effects, non-effects, and invariants.
- [ ] Acceptance criteria and required checks pass with no demonstrated Blocker.
- [ ] The exact head, named-PR binding, approval when required, and absence of later cancellation were rechecked.

## Final human acceptance

<!--
This section records navigation evidence only. It cannot create task-user
authority. Root AGENTS.md owns the complete packet and exact authorization
rules.
-->

- Repository and PR:
- Final full head SHA:
- Final packet navigation: `Pending`
- Same-task semantic decision and approval navigation: `Not required`
- Same-task later exact-head authorization navigation: `Pending`
- Required later task-user message:

```text
I authorize the AI to merge samovers/OFARM2 PR #<NUMBER> at head <FULL_HEAD_SHA>.
```

- [ ] The final packet covers Delivery identity, capability and boundary,
  paths and material diff, effects and non-effects, evidence and receipt,
  review disposition, code excellence, deviations, and same-task provenance.
- [ ] The AI presented the packet and ended its turn without merging.
- [ ] The later authorization is the entire exact task-user message in the same
  task and names this PR and current full head.
- [ ] Immediately before merge, the PR is open, non-draft, at that head, was
  not closed and reopened after the packet, has no invalidating user or scope
  change, and still passes every existing gate.
- [ ] The native merge uses the authorized SHA as its expected-head condition,
  with no administrator bypass, auto-merge, or direct target-branch push.

## Authority non-effects

Repository approval, checks, admission, baselines, publication, receipts, and
merge do not authorize deployment, release, current/default promotion,
production access, or a security waiver.
