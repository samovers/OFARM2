# OFARM2 Task Prompt

Use this prompt before starting an OFARM2 task.

You are working on `[ISSUE/TASK]` in `[REPOSITORY]` at base commit
`[SHA]`.

Inputs:

- Issue or acceptance criteria: `[LINK OR TEXT]`
- Base commit: `[SHA]`
- Related or stacked pull requests: `[LIST OR NONE]`
- Known constraints: `[LIST]`
- Existing architectural decisions: `[LIST OR NONE]`

## Choose the contract

Use the complete Phase A design contract when the task materially changes an
area in the canonical high-risk trigger list in `AGENTS.md`. If classification
is unclear, treat the task as high-risk until the boundary is explicitly
narrowed.

Use the routine contract for documentation, generated files, and mechanical
work that does not change authority or a trust boundary. If inspection shows
that a routine task does change one, stop and use the complete Phase A contract.

## Rules for every task

Solve one defined problem and keep the change inside one primary trust
boundary. Tests, documentation, and mechanical integration needed to verify
that boundary may travel with the change. Independent authority or custody
changes may not.

Prefer deletion, direct code paths, explicit boundary contracts, immutable
values, and small modules over framework layers, speculative abstractions,
compatibility shims, and duplicate validation.

Every task contract must state:

- **Problem:** the one problem being solved.
- **Acceptance criteria or invariants:** falsifiable conditions proving it is
  solved.
- **Out of scope:** adjacent systems and future concerns excluded from the
  change.
- **Smallest change:** why the proposed implementation is the minimum coherent
  solution.
- **Learning value:** the capability delivered, demonstrated risk reduced, or
  architectural decision validated. Do not start work that provides none of
  these.
- **Provisional design record:** if temporary, why it is acceptable before
  deployment, what evidence would require redesign, and the likely upgrade
  path. Otherwise state `Not provisional`.
- **Follow-ups:** linked issues created instead of expanding the change, or
  `None`.
- **Verification:** the smallest tests or checks needed for the stated
  boundary.
- **Review disposition:** remaining Blockers, Follow-ups, and Preferences.
- **Merge stop rule:** once acceptance criteria pass and no demonstrated
  Blocker remains, merge. New ideas, Preferences, and non-blocking hardening
  become Follow-ups and do not reopen review.

## Routine contract

Complete this contract before editing:

### Problem

`[ONE PROBLEM]`

### Primary trust boundary

`[ONE BOUNDARY; STATE THAT THE CHANGE DOES NOT ALTER AUTHORITY]`

### Acceptance criteria or invariants

- `[FALSIFIABLE CONDITION]`

### Out of scope

- `[EXCLUDED SYSTEM OR CONCERN]`

### Smallest change

`[WHY THIS IS THE MINIMUM COHERENT CHANGE]`

### Learning value

`[CAPABILITY, DEMONSTRATED RISK REDUCTION, OR ARCHITECTURAL DECISION]`

### Provisional design record

`Not provisional`, or:

- Acceptable before deployment because: `[REASON]`
- Evidence requiring redesign: `[EVIDENCE]`
- Likely upgrade path: `[PATH]`

### Follow-ups

- `[LINKED ISSUE OR NONE]`

### Verification

- `[SMALLEST CHECK]`

### Review disposition

- Blockers: `[LIST OR NONE]`
- Follow-ups: `[LINKED ISSUES OR NONE]`
- Preferences: `[LIST OR NONE]`

### Merge stop rule

Once the acceptance criteria pass and no demonstrated Blocker remains, merge
the pull request. New ideas, Preferences, and non-blocking hardening become
Follow-ups and do not reopen review.

## Phase A: complete design contract

Inspect the relevant code and produce the design contract below. Do not edit
files, create commits, or propose line-level patches during Phase A.

### 1. Problem and goal

- State the one problem being solved.
- State precisely what the task establishes.

### 2. Learning value

- Name the capability delivered, demonstrated risk reduced, or architectural
  decision validated.

### 3. Non-goals

- State what is explicitly deferred.
- Name adjacent systems and trust boundaries that must not change.

### 4. Trust model

- Name protected assets, trusted components, untrusted actors, and untrusted
  inputs.
- Name explicitly excluded attacker capabilities.
- State whether arbitrary in-process mutation, local source substitution,
  compromised dependencies, filesystem mutation, and operator compromise are
  in or out of scope.

### 5. Authority map

- Identify exactly one authoritative source for every decision.
- Identify legacy fallbacks, duplicate state, aliases, and alternate write
  paths to remove.
- Do not let a receipt name one authority while execution uses another.

### 6. State machine and ordering

- Define valid states, transitions, and forbidden transitions.
- Identify validation that must happen before side effects.
- Define transaction and time-of-check/time-of-use boundaries.

### 7. Invariants and acceptance criteria

- Assign stable IDs such as `INV-001`.
- Make every invariant falsifiable and implementation-independent.
- Include fail-closed behavior.

### 8. Negative cases

- Give at least one concrete counterexample for each invariant.
- Start each counterexample from a supported production entry point.
- Do not use private-field mutation or monkeypatching unless runtime-state
  corruption is explicitly in scope.

### 9. Proposed architecture and smallest change

- Describe types, ownership, data flow, and composition boundaries.
- Prefer one bound object over multiple correlated fields.
- Prefer deletion over compatibility shims.
- Avoid `Any`-typed authority objects, optional capability bags, identity
  comparisons used as security boundaries, self-attestation, and mutable global
  registries.
- Explain why this is the minimum coherent design.

### 10. Elegance audit

- Count sources of truth and authoritative transition points.
- Identify duplicated fields, compatibility surfaces, and abstractions
  introduced for only one implementation.
- State what can be deleted.
- State whether a clean rewrite is better than modifying the current patch.

### 11. Pull request boundary

- Name the primary trust boundary and files expected to change.
- List dependencies on stacked pull requests and what later work may assume.
- State what reviewers must not require from this pull request.
- List linked Follow-up issues instead of expanding this boundary.

### 12. Provisional design record

State `Not provisional`, or explain:

- Why the temporary design is acceptable before deployment.
- What evidence would require redesign.
- The likely upgrade path.

### 13. Traceability and verification

Provide a table mapping each invariant to its owning code, negative test,
acceptance evidence, and smallest verification.

### 14. Open decisions and review disposition

- List ambiguity that could materially change the design.
- Record current Blockers, Follow-ups, and Preferences.

Stop after Phase A and wait for explicit approval.

### Pre-deployment decision card

For a prospective pre-deployment decision governed by the AI-assisted workflow
in `AGENTS.md`, first create or reuse the one draft pull request containing the
reviewed Phase A contract. Show one complete plain-English card containing all
decision fields required by that workflow, including the draft PR's stable
reference and the exact approval sentence. Then wait.

Recognize approval only from that exact later task-user message in the same
Codex task. Before implementation, verify that the original card and approval
items remain directly retrievable with stable references and in the required
order. The task user does not verify hashes, bytes, inventories, or repository
mechanics. If the original items, role, task, order, or named PR cannot be
verified, stop without recognizing approval.

## Phase B: implementation

Only begin after the complete design contract is approved.

### Standing authority for an approved pre-deployment card

An approved card authorizes work only in its already-named draft pull request.
Record compact AI-attested evidence containing the decision identity and
version, task/card/approval stable references, exact approval sentence,
observed role and order, named PR, and the provisional-evidence limitation.
The task message remains authority; the record is evidence only.

Without another confirmation, the AI may perform only the in-envelope
implementation, tests, documentation, mechanical evidence, commits, pushes,
review handling, and merge authorized by the card and approved technical
contract. The technical contract's exact path allowlist must be a subset of the
card envelope, and every changed path must be inside that exact allowlist.

Before merge, post the compact scope report required by `AGENTS.md`, show any
bootstrap diff required by the approved contract, and recheck exact-head
review, all required checks, no demonstrated Blocker, the live original task
items, the named-PR binding, and absence of later cancellation. Material
expansion, another trust boundary or PR, lost evidence, ambiguity, or conflict
with the card stops for a new decision version. A stronger accepted procedure
continues to control its exact action. This authority is pre-deployment only
and never authorizes deployment or another production authority action.

Before editing, reproduce the approved invariant traceability table. Implement
the approved architecture, not a historical patch.

- If implementation reveals that the approved design is wrong or incomplete,
  stop and request a contract amendment.
- If a change is needed in another trust boundary, stop before editing it and
  propose a prerequisite, Follow-up, or stacked pull request.
- Keep production changes as small as the invariants permit.
- Remove obsolete authority and fallback paths instead of leaving old and new
  mechanisms active.
- Map every negative test to an approved invariant.
- Do not manufacture impossible production states and call them Blockers.
- Regenerate inventories and snapshots only when required by the completed
  runtime design.

At completion, report the invariant-to-implementation-to-test mapping, deleted
authority or fallback paths, deviations from the approved design, exact
validation, and review disposition.

## Phase C: bounded review

Review the exact head against the approved contract and use exactly these
classifications:

- **Blocker:** a demonstrated in-scope correctness, security, data-integrity,
  contractual, or production-safety failure. Name the violated invariant and
  the smallest acceptable fix.
- **Follow-up:** valid work outside the pull request boundary. Record it as a
  linked issue or small future pull request; do not expand the current change.
- **Preference:** optional style or alternative-design advice. It never delays
  merging.

Only Blockers delay a merge. Do not turn Preferences, hypothetical risks, or
unrelated hardening into required changes.

A Blocker is valid only when it states the violated invariant, supported
production entry point, in-scope actor, exact execution or state-transition
path, required preconditions, material consequence, and minimal reproduction or
counterexample.

Perform at most one unconstrained full review at an exact head. After a Blocker
is fixed, review only the fix and affected invariant unless new evidence
demonstrates that the original scope is unsafe.

For a pilot pull request, record the number of full reviews, Blocker-fix
reviews, Follow-ups, Preference-only suggestions, post-review commits, and the
time from zero Blockers to merge in [the governance tracking issue](https://github.com/samovers/OFARM2/issues/218).

## Success measure

Success means OFARM2 becomes more capable, reliable, and understandable without
unnecessary complexity. Each merged change must deliver a clear capability,
reduce a demonstrated risk, or validate an architectural decision. Before
deployment, a later redesign is acceptable when it is supported by evidence
and improves the platform.
