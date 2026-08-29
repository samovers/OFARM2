# OFARM2 Human Final Quality Acceptance Workflow Amendment v0.1

**Status:** Phase A candidate; inactive until the task user approves decision
version 1 and the resulting implementation pull request later receives exact-head
merge authorization and merges

**Contract identity:** `ofarm2.human-final-quality-acceptance-workflow.v0.1`

**Decision identity:** `HUMAN-FINAL-QUALITY-ACCEPTANCE-001`

**Proposed decision version:** `1`

**Parent workflow:** `ofarm2.proportional-delivery-workflow.v0.2`

**Delivery issue:** #355

**Primary trust boundary:** the task user's final acceptance of one implemented
pull-request head versus the AI's authority to merge that head

**Phase A boundary:** this RFC only

**Prospective complete PR boundary:** this RFC, root `AGENTS.md`,
`TASK_PROMPT.md`, `CONTRIBUTING.md`, and `.github/PULL_REQUEST_TEMPLATE.md`

## 1. Problem and evidence

The proportional workflow fixed artifact-level fragmentation, but it retained
the earlier model in which one pre-implementation approval grants the AI
standing implementation and merge authority. After implementation, agent
content review, checks, and any required publication, the AI posts a scope
report and may merge immediately. The task user has no mandatory opportunity to
inspect the finished diff.

The word “review” is therefore ambiguous. Exact-head content review proves an
agent or reviewer found no demonstrated Blocker. It does not mean the task user
has seen or accepted the implementation.

Routine Delivery work has an even wider gap: it may require no task-user stop
before merge.

The current repository also recommends excellent code shape but does not make
it an acceptance condition. Root procedure prefers deletion, direct paths,
explicit boundary contracts, immutable values, and small modules, while the
Blocker definition is limited to correctness, security, data integrity,
contracts, and production safety. An implementation can therefore be correct
but needlessly complicated, and a materially simpler design can be classified
as a non-blocking Preference.

Observed evidence on 2026-08-29:

- the task user reported that agents merge before personal review is possible;
- root procedure expressly assigns in-boundary merge to the AI after gates;
- the normal metric targets one approval stop for high-risk work, before
  implementation;
- GitHub reports no branch protection and no repository ruleset on `main`;
- the agent-authenticated GitHub identity and the human account are both
  `samovers`, so GitHub cannot distinguish their actions; and
- merged PR #349 delivered one narrow diagnostic-representation capability with
  1,992 additions and 12 deletions, including a 724-line RFC and 342 added lines
  in an already large architecture checker; post-merge issue #352 then found an
  unhandled class-scope binding path. This does not prove the implementation is
  bad, but it proves that extensive machinery and review do not themselves
  establish simplicity or completeness.

## 2. Goal and recommended decision

Return final merge authority to the task user and make code excellence an
explicit acceptance invariant without restoring micro-PRs or repeated
artifact-level approvals.

The recommended decision has one outcome: **the task user accepts the quality
of the exact completed implementation before the AI may merge it.** The user
receives one compact final packet that includes both technical evidence and a
concrete simplicity/elegance assessment. The AI then stops. A later exact
task-user message authorizes only that pull request and head.

This is one coherent capability because the quality invariants define what the
final human acceptance covers; they do not create an independent linting,
review, or publication system.

## 3. Non-goals

This amendment does not:

- restore one-contract, one-fixture, one-test-inventory, or one-evidence PRs;
- change the one-capability or one-primary-boundary rule;
- require an independent human content reviewer in addition to the task user;
- add a subjective score, line-count target, complexity threshold, style gate,
  or automated “elegance” classifier;
- authorize reviewers to block on naming, formatting, taste, or hypothetical
  future reuse;
- change executable admission, CI, baseline, publication, or receipt custody;
- change GitHub accounts, credentials, permissions, branch protection, or
  rulesets;
- change OFARM law, contracts, runtime behavior, profiles, schemas, data,
  deployment, production, or capability claims;
- silently revoke an approval granted in another task or reinterpret a merged
  pull request; or
- introduce an automatic-merge opt-out or exception in version 1.

## 4. Authority map

- The task user owns semantic approval, refusal, cancellation, requested
  changes, final quality acceptance, and exact-head merge authorization.
- A pre-implementation decision card owns the approved capability, primary
  boundary, effects, non-effects, and invariants. Its approval authorizes
  implementation and evidence collection only.
- The Phase A contract owns detailed architecture, risk, expected areas,
  verification, and code-excellence invariants.
- The AI owns in-boundary implementation, commits, pushes, review handling,
  checks, admission, publication coordination, and preparation of the final
  packet. It owns no merge action before exact-head authorization.
- Reviewers own demonstrated correctness, safety, and code-excellence Blocker
  findings. They do not own scope expansion or aesthetic vetoes.
- CI and publication systems own mechanical evidence only.
- GitHub activity cannot provide task-user intent because the current human and
  agent operations share one repository identity.
- The task user may merge manually outside the AI task. The AI must not infer
  authorization from that possibility or from any GitHub event.
- Existing OFARM, runtime, database, tenant, key, audit, deployment, and
  publication authorities retain their current owners.

## 5. Trust model

### Protected assets

- the task user's real opportunity to inspect the completed change;
- the exact implementation the user accepts;
- clear, direct, maintainable code within the approved capability;
- one source of truth and one authoritative path per decision; and
- the existing substantive safety and evidence gates.

### Trusted sides

- the same Codex task's ordered task-user messages for final authorization;
- the non-malicious AI for stopping at the final gate;
- reviewers for evidence-backed findings; and
- existing CI/publication mechanisms for their current mechanical claims.

### Untrusted inputs

- the earlier semantic approval as purported final quality acceptance;
- an agent-authored statement that the user “would approve”;
- GitHub reviews, comments, labels, mergeability, or credentials as proof of a
  human decision;
- green tests or zero-Blocker agent review as proof that the user inspected the
  code;
- silence, elapsed time, or an unattended task;
- line counts and automated complexity numbers as substitutes for architecture
  judgment; and
- aesthetic review feedback presented as a demonstrated design failure.

### Explicitly excluded compromise

A compromised task-user account, malicious AI, compromised Codex platform,
repository host, CI system, or GitHub account remains outside this procedural
pre-deployment threat model. Mechanical separation requires a future distinct
agent identity and protected branch; this amendment makes no such credential or
repository-setting change.

## 6. Primary risk and containment

The primary risk is replacing silent AI merge authority with an unbounded,
subjective review loop that recreates the delay this workflow removed.

Containment has four parts:

1. the final user gate is exactly one packet and one later exact-head decision;
2. code-excellence Blockers must identify a concrete duplicate source, path,
   state, validation, compatibility layer, unnecessary abstraction, or obscured
   invariant and its actual maintenance, audit, testing, or isolation cost;
3. the reviewer must name the smallest correction, while style and equivalent
   clean alternatives remain Preferences; and
4. a requested change outside the approved capability or boundary becomes
   separate Delivery work or a new decision rather than expanding the PR.

## 7. Stable invariants

### Human final acceptance

- **HFQ-001 — Final packet before merge.** Every new Delivery PR reaches a
  complete exact-head final packet before any AI merge action.
- **HFQ-002 — Mandatory yield.** The AI presents the packet and ends its turn.
  It cannot present the packet and merge in one turn.
- **HFQ-003 — Exact later authorization.** Only the entire visible text of a
  later task-user message in the same task, naming the PR and full current head,
  authorizes AI merge.
- **HFQ-004 — No inherited merge authority.** Semantic approval authorizes
  implementation and evidence collection, not merge. Routine classification,
  GitHub activity, reviews, checks, admission, publication, credentials, or
  silence never authorizes merge.
- **HFQ-005 — Stale means no merge.** A new commit, head change, close/reopen,
  semantic expansion, later cancellation, or conflicting user message revokes
  final authorization.
- **HFQ-006 — User changes remain bounded.** In-boundary requested changes
  return the PR to implementation and fresh exact-head review. Out-of-boundary
  requests stop for reclassification or a new decision.
- **HFQ-007 — Existing authority is historical.** The amendment applies to new
  Delivery work after activation. It does not silently cancel or reinterpret
  authority in another already-approved task.

### Code excellence

- **EXC-001 — One authoritative path.** The capability has one authoritative
  decision path and one source of truth for each owned fact.
- **EXC-002 — No avoidable duplication.** The change adds no avoidable duplicate
  authority, validation, durable or derived state, compatibility path, field
  inventory, or framework layer. Independent test expectations may repeat facts
  only when their independence is the evidence and the maintenance cost is
  explicit.
- **EXC-003 — Direct invariant trace.** A reviewer can trace each material
  invariant through the owning implementation to focused evidence without an
  undocumented side path or hidden fallback.
- **EXC-004 — Delete superseded paths.** Obsolete code, shims, flags, and
  fallbacks owned by the same boundary are removed in the Delivery PR unless a
  time-bounded compatibility duty and deletion trigger are explicit.
- **EXC-005 — Abstractions pay rent now.** A new abstraction or framework layer
  must isolate the current boundary, eliminate concrete duplication, or serve
  more than one current consumer. Speculative reuse is not sufficient.
- **EXC-006 — Simpler alternative considered.** Any material increase in
  concepts, indirection, state, or bespoke conformance machinery identifies the
  simplest credible alternative and the invariant that prevents using it.
- **EXC-007 — Taste is not a Blocker.** Naming, formatting, and preference among
  designs satisfying EXC-001 through EXC-006 remain non-blocking.

## 8. Final packet and authorization

The final packet is compact and contains:

- Delivery issue and PR;
- full candidate head SHA;
- capability and primary trust boundary;
- final changed paths and material diff summary;
- permitted effects, non-effects, and unresolved Follow-ups;
- cheap checks, exact-head review, hosted evidence, and publication results as
  applicable;
- Blockers, Follow-ups, and Preferences;
- EXC-001 through EXC-006 assessment, including deletions, remaining duplicate
  state or paths, abstractions added, and the simpler alternative considered;
- deviations from Phase A; and
- the exact authorization sentence with the PR number and full head filled in.

The AI then stops. Authorization is only this entire later task-user message:

```text
I authorize merge of OFARM2 PR #<NUMBER> at <FULL_COMMIT_SHA>.
```

The AI must re-read the live PR head and the later message before merging. An
authorization for another PR, another head, an earlier candidate, or an
abbreviated SHA has no effect.

There is no automatic-merge authorization path in version 1. If evidence later
shows a need, it requires its own explicit workflow amendment rather than an
informal exception.

## 9. Review classification

The existing Blocker/Follow-up/Preference model remains, with one addition.

A **code-excellence Blocker** is a demonstrated in-scope violation of EXC-001
through EXC-006. It must name:

- the violated invariant;
- the exact implementation path;
- the duplicated authority/state/path, unnecessary concept, obscured
  transition, retained obsolete path, or unjustified machinery;
- the concrete maintenance, audit, testing, or change-isolation consequence;
- a credible simpler alternative that preserves all accepted requirements; and
- the smallest acceptable correction.

Without those elements, design advice is a Preference. A reviewer cannot block
merely because a different pattern, name, module split, or style is personally
preferred.

The task user is not limited to reviewer classifications at the final gate.
The user may decline authorization or request in-boundary changes for any
reason. The AI still must enforce scope and reapproval boundaries.

## 10. State and ordering

For approval-governed work:

```text
DELIVERY_ISSUE_DEFINED
  -> DRAFT_PR_WITH_PHASE_A
  -> PHASE_A_DESIGN_REVIEWED
  -> USER_SEMANTIC_DECISION_CARD
  -> USER_APPROVED_IMPLEMENTATION
  -> IMPLEMENT_COMPLETE_VERTICAL_SLICE
  -> CHEAP_LOCAL_CHECKS
  -> EXACT_HEAD_CONTENT_AND_EXCELLENCE_REVIEW_ZERO_BLOCKERS
  -> REQUIRED_ADMISSION_BASELINES_AND_PUBLICATION
  -> FINAL_SCOPE_EVIDENCE_AND_EXCELLENCE_RECHECK
  -> READY_FOR_USER_FINAL_REVIEW
  -> AI_YIELDS_WITH_FINAL_PACKET
  -> USER_AUTHORIZED_EXACT_HEAD_MERGE
  -> AI_RECHECKS_HEAD_AUTHORIZATION_AND_CANCELLATION
  -> MERGE_AND_CLOSE_DELIVERY_ISSUE
```

Routine work omits the semantic decision-card states but never omits the final
packet, yield, and exact-head authorization states.

If the user requests an in-boundary correction:

```text
READY_FOR_USER_FINAL_REVIEW
  -> USER_REQUESTED_CHANGES
  -> IMPLEMENT_AND_VERIFY_CORRECTION
  -> FRESH_EXACT_HEAD_REVIEW_AND_REQUIRED_EVIDENCE
  -> NEW_FINAL_PACKET
```

No response leaves the PR open and unmerged. Waiting is not approval, failure,
or authority to create a replacement PR.

## 11. Proposed architecture and smallest coherent change

Root `AGENTS.md` remains the one source of standing procedure. Phase B makes a
closed semantic edit across the four active surfaces:

1. `AGENTS.md` changes AI merge authority, the state machine, final scope step,
   and Blocker definition; it adds the final packet and authorization rule plus
   the excellence invariants.
2. `TASK_PROMPT.md` makes Phase A and Phase C collect the same invariants and
   stop at the final packet.
3. `CONTRIBUTING.md` explains the human merge hold and concrete design-quality
   review standard.
4. `.github/PULL_REQUEST_TEMPLATE.md` captures the excellence assessment and
   exact-head final packet fields.

This RFC is the durable amendment and evidence. It does not become a competing
active instruction surface.

No automation, new status store, GitHub check, comment protocol, quality score,
or compatibility shim is needed. The state already exists in the task and PR;
the correction changes who may perform the final transition.

## 12. Failure cases and negative evidence

| Case | Required result |
| --- | --- |
| AI posts the packet and merges before a later user message | Refuse; HFQ-002 violation |
| User approved Phase A but never saw the implementation | PR remains open; HFQ-004 |
| User writes “looks good” without PR and full SHA | No merge authority; HFQ-003 |
| User authorizes head A and a documentation commit creates head B | Authorization stale; new packet and message required |
| GitHub shows an approval or green merge button | Evidence only; no task-user authority |
| Routine typo PR passes tests | Still stops for final packet and authorization |
| Reviewer prefers another name or module layout | Preference unless an EXC invariant is concretely violated |
| Change adds a second validator with overlapping authority and no deletion plan | Code-excellence Blocker under EXC-001/EXC-002 |
| New helper isolates a real boundary and removes repeated logic | Allowed even with one public caller when the boundary justification is concrete |
| Final user request adds another capability | Stop for a separate Delivery issue or new semantic decision |
| Another task previously authorized an open PR to auto-merge | Not silently revoked; user must stop or supersede it in that owning task |

## 13. Verification

Phase A verification:

- wording audit against v0.2 authority, state, review, and merge clauses;
- confirm the proposed rule distinguishes agent review from task-user review;
- confirm every negative case maps to HFQ or EXC invariants;
- confirm the five-path PR boundary contains one workflow capability; and
- `git diff --check`.

Phase B verification:

- search all four active surfaces for stale AI standing merge authority,
  one-stop target language, and merge-without-yield instructions;
- search for competing final-authorization sentences;
- verify every active surface contains the same default no-merge posture;
- verify the PR template records exact head and excellence evidence but does not
  claim to create task-user authority;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- mandatory cheap workflow checks;
- exact-head content and excellence review with zero Blockers;
- existing hosted admission, baseline, and publication evidence required for a
  workflow-governance change; and
- the new final packet and exact-head task-user merge authorization for this PR
  itself.

## 14. Provisional posture and review point

This is acceptable only for pre-deployment repository development. It changes
repository merge authority and code-quality review, not production authority or
GitHub identity separation.

The procedural hold depends on a non-malicious AI because the agent and user
share one GitHub identity and `main` is unprotected. Strong mechanical
separation would require a distinct least-privilege agent identity and a branch
rule requiring the human identity. That is a separate custody/permissions
capability and is not silently added here.

Review this amendment after the next three merged Delivery PRs under it. Record:

- whether any AI merge occurred without exact task-user authorization;
- whether any authorization became stale and was handled correctly;
- whether code-excellence Blockers cited concrete EXC invariants or became taste;
- whether final review found material issues missed by agent review;
- the waiting time introduced by the final hold; and
- whether teams attempted process-only PRs or hidden auto-merge workarounds.

The rule remains active after the review point unless an explicit amendment
changes it. The review creates evidence; it does not automatically relax the
human gate.

## 15. Decision and reapproval triggers

Version 1 recommends:

- mandatory exact-head final user authorization for every new Delivery PR;
- no automatic-merge exception;
- concrete EXC invariants as merge-blocking acceptance conditions; and
- the five-path prospective implementation boundary.

A new decision version is required if Phase B proposes:

- optional or inferred auto-merge;
- authorization without the full head SHA;
- GitHub activity as human authority;
- a different primary trust boundary or additional active policy surface;
- an automated subjective quality score or new CI gate;
- independent human reviewer requirements;
- GitHub identity, credential, permission, ruleset, or branch-protection work;
- retroactive cancellation of another task's approval; or
- any runtime, production, deployment, law, contract, or publication-control
  effect.

## 16. Phase A review disposition

Blockers, Follow-ups, and Preferences are recorded after review of this exact
Phase A head. Phase B must not begin until the visible version-1 decision card
has zero Blockers and the task user supplies the exact approval sentence named
by that card.

What is next: review this RFC as the Phase A contract, open the one draft PR,
and present the complete version-1 decision card only after zero Blockers.
