# OFARM2 Task Prompt

Use this prompt before starting OFARM2 Delivery work. Root `AGENTS.md` is the
canonical source for repository-development procedure; this file is its working
form.

Inputs:

- Work unit: `Delivery issue` / `Tracking Epic`
- Delivery issue: `[LINK OR TEXT]`
- Tracking Epic: `[LINK OR NONE]`
- One independently reviewable capability: `[CAPABILITY]`
- Primary trust boundary: `[ONE BOUNDARY]`
- Repository and base commit: `[REPOSITORY]` at `[SHA]`
- Existing live or draft pull request: `[LINK OR NONE]`
- Dependent Delivery issues: `[LIST OR NONE]`
- Abandoned-PR recovery status: `None` / `Replacing` / `Reopening`
- Known constraints: `[LIST]`
- Accepted exact-action requirements: `[LIST OR NONE]`

If the work unit contains more than one independently reviewable capability or
more than one primary trust boundary, classify it as a Tracking Epic, create or
identify one Delivery child issue for each capability, and stop until one child
is selected. A Tracking Epic does not receive an implementation pull request.

## Choose the contract

Use the routine contract for low-risk work that does not change, rely on, or
exercise authority. If inspection shows otherwise, stop and use a risk-shaped
Phase A.

Use a risk-shaped Phase A when a task materially changes authentication,
credential verification, principal resolution, authorization, signing, key
custody or authority, tenant isolation, database roles, transactions,
migrations or durability semantics, runtime integration or readiness,
security-audit behavior, or irreversible data behavior. If classification is
unclear, treat the task as high-risk until the boundary is explicitly narrowed.

Every Phase A has a small required core. Add state, custody, durability,
recovery, migration, or durable-architecture sections only when the stated risk
needs them.

## Rules for every task

One Delivery issue owns one user- or system-visible outcome, one independently
reviewable capability, and one primary trust boundary. It has one live
implementation pull request at a time and at most one merged implementation
pull request.

Implementation, owned migrations, tests, fixtures, compatibility bridges,
documentation, generated inventories, and mechanical evidence needed to
deliver or prove that capability travel in the same pull request. Do not split
out a contract, approval record, path-list change, fixture, inventory, or
evidence artifact whose only outcome is enabling another planned pull request.
A complete prerequisite in another boundary is valid only as its own Delivery
issue with an independently usable and testable outcome.

Same authority ownership does not justify bundling independent capabilities.
Cross-boundary bundling has no waiver. If another capability or authority-level
boundary is required, stop before editing it and create separate Delivery work.

Expected paths and repository areas are scope predictions, not human approval
authority. A newly discovered implementation, test, fixture, documentation, or
generated-evidence file does not require reapproval when it clearly preserves
the approved capability, authority, effects, invariants, and boundary. Explain
it in the final scope report. Genuine ambiguity stops for a new decision.

A stronger accepted procedure expressly governing an exact action remains
controlling. If it is ambiguous whether an older clause is a superseded
packaging mechanic or a substantive exact-action requirement, keep the older
requirement until an explicit amendment resolves it.

Prefer deletion, direct code paths, explicit boundary contracts, immutable
values, and small modules over framework layers, speculative abstractions,
compatibility shims, and duplicate validation.

Every task contract states:

- **Problem and capability:** the problem and one independently reviewable
  outcome that solves it.
- **Primary trust boundary:** the one authority-level boundary being changed or
  preserved.
- **Permitted effects and non-effects:** what may and may not change.
- **Acceptance criteria or invariants:** falsifiable conditions proving the
  capability is complete.
- **Non-goals:** adjacent systems and future concerns excluded from the change.
- **Expected areas and companions:** likely files plus the implementation,
  tests, fixtures, documentation, and evidence that must travel together.
- **Smallest complete change:** why this is the minimum coherent vertical
  slice.
- **Code excellence:** the authoritative path and sources of truth, avoidable
  duplication, deletions, abstractions added, direct invariant trace, and the
  simplest credible alternative.
- **Provisional posture:** `Not provisional`, or why a temporary design is
  acceptable before deployment, evidence requiring redesign, and the likely
  upgrade path.
- **Follow-ups:** separate Delivery issues instead of scope expansion, or
  `None`.
- **Verification:** the smallest checks needed for the stated boundary.
- **Review disposition:** remaining Blockers, Follow-ups, and Preferences.

## Routine contract

Complete this before editing low-risk work:

### Delivery identity

- Delivery issue: `[LINK]`
- Tracking Epic: `[LINK OR NONE]`
- Independently reviewable capability: `[ONE CAPABILITY]`
- Live implementation pull request: `[LINK OR NONE]`
- Recovery status: `None` / `[CLOSED-UNMERGED PR AND APPROVED RECOVERY]`

### Problem

`[ONE PROBLEM]`

### Primary trust boundary

`[ONE BOUNDARY; EXPLAIN WHY AUTHORITY DOES NOT CHANGE]`

### Permitted effects

- `[PERMITTED EFFECT]`

### Non-effects and non-goals

- `[EXCLUDED EFFECT, SYSTEM, OR CONCERN]`

### Acceptance criteria or invariants

- `[FALSIFIABLE CONDITION]`

### Expected repository areas and companions

- Expected areas: `[LIST]`
- Implementation or deletion: `[INCLUDED OR NOT NEEDED]`
- Tests and fixtures: `[INCLUDED OR NOT NEEDED]`
- Documentation: `[INCLUDED OR NOT NEEDED]`
- Generated inventories or evidence: `[INCLUDED OR NOT NEEDED]`

### Smallest complete change

`[WHY THIS IS THE MINIMUM COHERENT VERTICAL SLICE]`

### Code excellence

- Authoritative decision path and sources of truth: `[PATHS AND OWNERS]`
- Avoided or remaining duplicate authority, validation, state, compatibility,
  inventory, or framework paths: `[ASSESSMENT]`
- Superseded paths deleted or time-bounded duty and deletion trigger:
  `[DELETIONS OR NOT APPLICABLE]`
- Direct invariant-to-implementation-to-evidence trace: `[TRACE]`
- Abstractions added and current rent: `[ASSESSMENT OR NONE]`
- Simplest credible alternative and preventing invariant: `[ASSESSMENT]`

### Provisional posture

`Not provisional`, or:

- Acceptable before deployment because: `[REASON]`
- Evidence requiring redesign: `[EVIDENCE]`
- Likely upgrade path: `[PATH]`

### Follow-ups

- `[DELIVERY ISSUE OR NONE]`

### Verification

- `[SMALLEST CHECK]`

### Review disposition

- Blockers: `[LIST OR NONE]`
- Follow-ups: `[DELIVERY ISSUES OR NONE]`
- Preferences: `[LIST OR NONE]`

### Merge stop rule

Passing acceptance criteria and required checks with no demonstrated Blocker
makes the pull request technically ready for the final human-acceptance packet;
it does not authorize merge. Follow the packet, mandatory yield, later exact
task-user authorization, and native expected-head merge rules in root
`AGENTS.md`. New ideas, Preferences, and non-blocking hardening become
Follow-ups and do not reopen review.

## Phase A: risk-shaped design contract

Inspect the relevant code before writing Phase A. Put the contract in the
already-created draft pull request description by default. Add an RFC or ADR in
that same pull request only when the architectural decision must remain useful
after the pull request closes. Do not edit implementation during Phase A.

### Required core

#### 1. Problem and capability

- State the one problem.
- State the one independently reviewable capability and its user- or
  system-visible outcome.
- Identify the Delivery issue and any Tracking Epic.

#### 2. Primary boundary and effects

- Name one primary trust boundary.
- State permitted effects and non-effects.
- Name adjacent boundaries that must not change.
- Add an authority map whenever the work changes, relies on, or exercises
  authority.

#### 3. Invariants, acceptance criteria, and non-goals

- Give stable IDs such as `INV-001` to falsifiable invariants.
- Include fail-closed behavior.
- State explicit non-goals.

#### 4. Expected areas and complete-slice companions

- Name expected repository areas as scope prediction, not approval authority.
- Identify implementation and deletions, owned migrations, tests, fixtures,
  compatibility bridges, documentation, inventories, and mechanical evidence
  needed for the same capability.
- Name complete prerequisite Delivery issues, or `None`.

#### 5. Proposed architecture and smallest coherent change

- Describe ownership, data flow, and composition boundaries at the depth the
  risk requires.
- Prefer one bound object over correlated fields and deletion over duplicate
  authority or compatibility paths.
- Apply `EXC-001` through `EXC-006`: identify the authoritative path and owned
  sources of truth, duplicate paths or state, deletions, direct invariant
  trace, abstractions added and their current rent, and the simplest credible
  alternative.
- Explain why this is the smallest complete vertical slice.

#### 6. Verification

- Map each invariant to the smallest useful test or inspection.
- State required cheap checks and final hosted evidence.

#### 7. Provisional posture

State `Not provisional`, or explain why the design is acceptable before
deployment, what evidence would require redesign, and the likely upgrade path.

#### 8. Open decisions and review disposition

- List ambiguity that could materially change the design.
- Record Blockers, Follow-ups, and Preferences.

### Required high-risk trust floor

For high-risk work, also state:

- protected assets;
- trusted sides or components;
- untrusted actors, sides, and inputs;
- explicitly excluded attacker capabilities;
- the primary risk and its containment rule;
- at least one production-reachable negative case for every invariant; and
- invariant-to-implementation-to-test traceability.

A high-risk Blocker must name the violated invariant, supported production
entry point, in-scope actor, exact execution or state-transition path, required
preconditions, material consequence, and minimal reproduction or
counterexample. Do not manufacture impossible internal states or introduce a
new attacker model to block the pull request.

### Conditional modules

Add only the modules the risk requires:

- **State and ordering:** for stateful or transactional work, define states,
  transitions, forbidden transitions, validation-before-side-effect ordering,
  and time-of-check/time-of-use boundaries.
- **Custody:** for credentials, keys, or protected outputs, define custody,
  access, derivation, and handoff.
- **Durability and recovery:** for durable changes, define migration,
  transaction, rollback, failure recovery, and irreversible effects.
- **Durable architecture and elegance:** when the decision must outlive the
  pull request, record sources of truth, authoritative transitions, duplicated
  state, deletion opportunities, and why an RFC or ADR is needed.

Review Phase A to zero Blockers, then stop and present the decision card. Do not
implement or request an expensive hosted baseline for a design-only head.

## Pre-deployment decision card

For an approval-governed change, use the one existing draft pull request and
the reviewed Phase A. Show one complete plain-English card containing:

- decision identity and version;
- problem and one independently reviewable capability;
- recommended decision;
- primary trust boundary and authority map;
- primary risk and containment rule;
- permitted effects, non-effects, and decision-level invariants;
- the named draft pull request;
- verification gates and semantic reapproval triggers;
- provisional pre-deployment posture; and
- this exact approval sentence:

```text
I approve OFARM2 decision <DECISION_ID> version <VERSION>.
```

Approval is only the entire visible text of a later task-user message in the
same Codex task. Before recognizing it, verify that the unique live card and
approval remain directly retrievable with stable references in the required
order and that the named pull request is still open at the expected Phase A
head. Generic approval, GitHub activity, credentials, AI or tool output,
delegation, another task, or a summary of lost items never supplies approval.

Human approval binds the capability, effects, authority, invariants, and named
pull request rather than an exhaustive path list. It cannot be transferred to
another pull request or replayed for another decision. A new decision version
is required for a changed capability, primary boundary, authority map,
permitted effect, non-effect, invariant, irreversible behavior, named pull
request, or production/deployment posture, or when preservation is genuinely
ambiguous.

This semantic approval authorizes bounded implementation and evidence
collection, not merge. Every AI-operated Delivery merge still requires the
separate final exact-head task-user authorization owned by root `AGENTS.md`.

Closing the named pull request unmerged expires authority. Replacement or
reopening requires the recovery procedure in root `AGENTS.md`: a new decision
version and approval, fresh evidence, and no inheritance of earlier approval,
review, admission, checks, baselines, or publication.

## Phase B: complete implementation

Begin only after valid approval when approval is required.

- Reconfirm the declared capability, primary boundary, authority map when
  applicable, effects, non-effects, and invariants. When approval is required,
  also reconfirm the named pull request and absence of cancellation.
- Reproduce the applicable Phase A traceability when the risk requires it.
- Implement the complete vertical slice and its same-boundary companions.
- When approval is required, record compact pull-request navigation with stable
  references to the decision and approval. The task message remains authority;
  no committed approval appendix or separate approval-record pull request is
  required. For routine work, link the Delivery task contract and pull request.
- Treat final changed paths as scope evidence. Explain newly discovered files
  and prove that they add no capability, authority, effect, invariant, or
  boundary.
- Preserve every stronger accepted exact-action procedure.
- Stop before editing another capability or authority/custody boundary.
- For approval-governed work, stop for a new decision version on semantic
  expansion, genuine ambiguity, named-pull-request change, or approval
  conflict. For routine work, stop and amend or reclassify the task contract;
  use Phase A and a new decision if approval becomes required.
- Remove obsolete authority and fallback paths instead of leaving duplicate
  mechanisms active.
- Regenerate inventories and snapshots only when required by the completed
  capability.

If implementation invalidates the declared contract, stop. Approval-governed
work requires a new decision version; routine work must amend or reclassify its
contract before editing continues. At completion, report
invariant-to-implementation-to-test mapping, deleted authority or fallback
paths, duplicate paths or state, abstractions added and their current rent, the
simplest credible alternative, deviations, exact validation, and review
disposition.

## Phase C: bounded review and merge

For an approval-governed change, or when a stronger accepted exact-action
procedure requires hosted evidence, freeze the implemented candidate head and
use this order:

1. Run mandatory cheap local checks.
2. Obtain exact-head content review with zero Blockers.
3. After any Blocker fix, review only the fix and affected invariants unless new
   evidence demonstrates that the original scope is unsafe.
4. Create fresh baseline admission for that exact head.
5. Complete required hosted baselines and separate authoritative publication.
6. Confirm the final receipt, semantic scope, and `EXC-001` through `EXC-006`
   assessment. When semantic approval is required, also confirm approval
   preservation, named-PR binding, and absence of cancellation.
7. Prepare the complete exact-head final packet required by root `AGENTS.md`,
   including final paths and diff, effects and non-effects, evidence and review
   disposition, excellence assessment, deviations, same-task provenance, and
   the filled exact authorization sentence.
8. Present the packet and end the turn without merging.
9. Only after the task user supplies the entire exact sentence in a later
   message in the same task, retrieve both messages and recheck the authorized
   head, open/non-draft state, close/reopen history, scope, cancellation,
   Blockers, and every existing gate.
10. Use the normal GitHub pull-request merge with the authorized SHA as its
    expected-head condition. Do not use administrator bypass, auto-merge, or a
    direct target-branch push. A native rejection stops the merge.
11. Verify the merge and close the Delivery issue.

The exact later task-user message, owned by root `AGENTS.md`, is:

```text
I authorize the AI to merge samovers/OFARM2 PR #<NUMBER> at head <FULL_HEAD_SHA>.
```

Routine work omits the early semantic-decision steps but never omits steps 7
through 11. It follows any stronger accepted exact-action requirement. Do not
create admission or publication ceremony when neither root `AGENTS.md` nor an
accepted exact-action procedure requires it.

Classify every finding as exactly one of:

- **Blocker:** a demonstrated in-scope correctness, security, data-integrity,
  contractual, production-safety, or code-excellence failure. Name the
  violated invariant and smallest acceptable fix. A code-excellence Blocker
  must identify the concrete defect, its present maintenance, audit, testing,
  or isolation cost, the violated `EXC-001` through `EXC-006` rule, and the
  smallest correction.
- **Follow-up:** valid work outside the pull request boundary. Record separate
  Delivery work; do not expand this pull request.
- **Preference:** optional style or alternative-design advice. It never delays
  merging.

Only demonstrated Blockers delay technical readiness. Equivalent clean
alternatives, naming, formatting, and hypothetical future reuse are
Preferences. Perform at most one unconstrained full review at an exact head.
Preferences, hypothetical risks, and unrelated hardening do not reopen review.
The task user may still decline final authorization or request in-boundary
changes for any reason.

## Outcome measures

Measure delivery end to end:

- Delivery-issue open-to-close time;
- live and abandoned implementation pull requests per delivered capability;
- early semantic-approval and final exact-head authorization stops per
  capability;
- process-only pull requests;
- final implemented-head baseline cycles; and
- time from zero Blockers to merge as secondary operational data.

The normal target is one live and one merged implementation pull request, one
final exact-head authorization stop for every AI-operated merge plus one early
semantic-approval stop when the work requires it, zero process-only companion
pull requests, and one successful implemented-head baseline cycle. Recovery
from an abandoned unmerged pull request is recorded as recovery, not a second
capability.

Success means OFARM2 becomes more capable, reliable, and understandable without
unnecessary complexity. Repository approval, checks, evidence, or merge never
authorizes deployment, release, current/default promotion, production access,
or a security waiver.
