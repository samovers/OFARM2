# OFARM2 Human Final Quality Acceptance Workflow Amendment v0.1

**Status:** Phase A candidate; inactive until the task user approves decision
version 1 and the completed implementation later passes its own final human
merge gate

**Contract identity:** `ofarm2.human-final-quality-acceptance-workflow.v0.1`

**Decision identity:** `HUMAN-FINAL-QUALITY-ACCEPTANCE-001`

**Proposed decision version:** `1`

**Parent workflow:** `ofarm2.proportional-delivery-workflow.v0.2`

**Delivery issue:** #355

**Primary trust boundary:** the task user's final acceptance of one implemented
pull-request head versus the AI's authority to merge it

**Phase A boundary:** this RFC only

**Prospective complete PR boundary:** this RFC, root `AGENTS.md`,
`TASK_PROMPT.md`, `CONTRIBUTING.md`, and `.github/PULL_REQUEST_TEMPLATE.md`

## 1. Problem and decision

The parent workflow asks the task user to approve semantics before
implementation, then gives the AI standing authority to merge after agent
review and mechanical gates. The task user is not guaranteed a chance to
inspect the completed code. Routine Delivery work can merge without any user
stop.

The workflow also recommends deletion, direct paths, explicit boundaries,
immutable values, and small modules, but those qualities are not acceptance
conditions. A needlessly complicated implementation can be technically correct
while a materially simpler design is treated as a non-blocking Preference.

Version 1 makes one change: **before any AI-operated Delivery PR merge, the task
user accepts or refuses the named PR at its full current head SHA.** The final
packet includes concrete simplicity and maintainability evidence. The AI posts
that packet and ends its turn. Only a later exact task-user message in the same
task permits the native GitHub PR merge.

The excellence rules define what that same final acceptance covers; they do not
create a second reviewer, gate service, or implementation capability.

This amendment does not create an immutable integrated-candidate or target-ref
custody system. The authorized object is the pull-request head, exactly as issue
#355 states. Existing GitHub merge eligibility, admission, baseline,
publication, and receipt controls keep their current owners.

## 2. Closed amendment and precedence

On activation, this RFC prospectively supersedes only these parent-workflow
mechanics:

- semantic approval no longer grants the AI merge authority;
- the AI no longer moves directly from the final scope/evidence recheck to
  merge;
- routine AI-operated Delivery work also requires the final user stop;
- the normal approval-stop count includes this deliberate final decision; and
- demonstrated code-excellence failures defined here may be Blockers.

All one-capability, one-boundary, Phase A, approval provenance, review,
admission, publication, recovery, cancellation, native merge, and substantive
OFARM requirements remain unchanged.

An already-approved unmerged PR keeps merge authority only when its directly
retrievable governing approval explicitly granted that authority. This
amendment does not silently rewrite historical approvals. PR age, branch age,
or GitHub activity creates no authority.

Approval of decision version 1 authorizes the in-boundary Phase B edits and
evidence collection, not merge. PR #356 itself must later stop at the final
packet and obtain exact-head merge authorization.

## 3. Scope, authority, and risk

### Authority map

- The task user owns semantic approval, final quality acceptance, refusal,
  requested changes, cancellation, and exact-head merge authorization.
- The decision card owns the approved capability, effects, non-effects,
  invariants, and named PR.
- This RFC owns the detailed final-gate and code-excellence rules.
- The AI owns in-boundary implementation, review handling, checks, existing
  admission/publication coordination, and final-packet preparation. It may
  invoke the existing GitHub-native PR merge only after the final authority and
  every existing gate are valid.
- Reviewers own demonstrated Blocker findings, not scope expansion or aesthetic
  vetoes.
- GitHub owns native PR state, merge eligibility, and the merge transition. CI,
  admission, and publication systems own only their existing mechanical claims.
- Existing OFARM, runtime, database, tenant, key, audit, deployment, and
  publication authorities retain their current owners.

### Protected assets and trust

The protected assets are the user's real opportunity to inspect completed work,
the exact PR head accepted, maintainable code, and the existing safety gates.
Ordered same-task user messages and immutable full Git head SHAs are trusted for
this procedural authority. GitHub reviews, comments, labels, checks,
credentials, agent statements, silence, and elapsed time are not human intent.

The user and AI currently share one GitHub identity and `main` has no independent
human-enforcement rule. This is therefore a pre-deployment procedural control,
not cryptographic identity separation. A compromised user, AI, task platform,
GitHub account, repository host, or CI system is outside this amendment's threat
model.

### Primary risk and containment

The primary delivery risk is replacing silent AI merge authority with a vague
subjective veto that recreates endless review. Containment is one exact-head,
one-message human gate plus concrete excellence rules: a reviewer must identify
an actual duplicate source, unnecessary concept, obscured authority path,
avoidable state, or unjustified abstraction, explain its real cost, and name
the smallest correction. Style remains non-blocking.

The authority risk is inferred permission. Containment is a complete packet,
mandatory yield, one exact later sentence, and fail-closed invalidation on head
or meaning changes. GitHub activity and the earlier semantic approval never
substitute for that sentence.

The supported entry point is the AI invoking GitHub's native merge operation on
a Delivery PR. The reachable failure is that all technical gates are green but
the AI merges without the later task-user authorization, placing unaccepted
code on the default branch and normal path toward deployment. The packet,
yield, exact sentence, and final authority recheck block that transition.

### Non-goals

Version 1 does not:

- change runtime, domain, OFARM law, contracts, schemas, profiles, data,
  deployment, production, database, tenant, key, audit, or publication
  behavior;
- change GitHub accounts, credentials, permissions, branch protection,
  rulesets, merge methods, merge queues, or repository settings;
- replace the native GitHub PR merge path, construct or authorize a synthetic
  merge commit, write a target ref directly, or add a merge executor;
- authorize an exact base SHA, integrated tree, merge-commit SHA, merge message,
  or target-write command;
- add a merge bot, workflow, status store, policy inventory, lifecycle-episode
  identity, quality score, line-count gate, or subjective linter;
- require another independent human content reviewer;
- restore micro-PRs or repeated artifact approvals; or
- reinterpret merged work or silently cancel authority accepted in another
  task.

## 4. Stable invariants

### Human final acceptance

- **HFQ-001 — Complete final packet.** Every Delivery PR that the AI would
  merge reaches one complete packet bound to the named repository, PR, and full
  current head SHA.
- **HFQ-002 — Mandatory yield.** The AI presents the packet and ends its turn.
  It cannot first present the packet and merge in the same turn.
- **HFQ-003 — Exact later authority.** Only the entire visible text of a later
  task-user message in the same task, naming the same PR and full head SHA,
  authorizes merge. The packet and authorization remain directly retrievable in
  that order; summaries and paraphrases are not authority.
- **HFQ-004 — Stale authority fails closed.** A new commit or head change,
  close/reopen after the packet, semantic expansion, later stop or cancellation,
  or conflicting later task-user message invalidates authorization.
- **HFQ-005 — No inferred authority.** Earlier semantic approval, routine
  classification, GitHub activity, reviews, checks, admission, publication,
  credentials, agent messages, silence, and elapsed time never authorize merge.
- **HFQ-006 — Native merge controls remain native.** Immediately before merge,
  the AI must find the PR open, non-draft, at the authorized full head, free of
  demonstrated Blockers, and eligible under every existing repository gate. It
  uses the normal GitHub PR merge path with an expected-head guard and never
  uses administrator bypass, auto-merge, or a direct target-ref write.
- **HFQ-007 — Historical authority is preserved exactly.** Activation does not
  revoke a directly retrievable valid approval that explicitly granted the old
  merge authority. Age or an unrelated approval preserves nothing.
- **HFQ-008 — Corrections remain bounded.** In-boundary requested changes create
  a new head and require fresh review, applicable evidence, a new packet, yield,
  and later authorization. Out-of-boundary changes stop for separate Delivery
  work or a new decision.

### Code excellence

Every Delivery issue, Phase A contract, PR description, review, and final packet
states the excellence invariants appropriate to its capability, including at
least the following rules:

- **EXC-001 — One authoritative path.** The implemented capability has one
  authoritative decision path and one source of truth for each owned fact.
- **EXC-002 — No avoidable duplication.** The change adds no avoidable duplicate
  authority, validation, durable or derived state, compatibility path, field
  inventory, or framework layer.
- **EXC-003 — Direct invariant trace.** Each material invariant traces directly
  through its owning implementation to focused evidence, without a hidden
  fallback.
- **EXC-004 — Delete superseded paths.** Obsolete code, shims, flags, and
  fallbacks owned by the same boundary are removed unless a current,
  time-bounded compatibility duty and deletion trigger are explicit.
- **EXC-005 — Abstractions pay rent now.** A new abstraction must isolate the
  current boundary, remove concrete duplication, or serve multiple current
  consumers. Speculative reuse is insufficient.
- **EXC-006 — Simpler alternative considered.** A material increase in concepts,
  indirection, state, or bespoke machinery names the simplest credible
  alternative and the invariant that prevents using it.
- **EXC-007 — Taste is not a Blocker.** Naming, formatting, and preference among
  designs satisfying EXC-001 through EXC-006 remain non-blocking.

## 5. Final packet, authorization, and native merge

The final packet contains:

- Delivery issue and PR;
- repository identity and full current head SHA;
- capability and primary trust boundary;
- final changed paths and material diff summary;
- permitted effects, non-effects, and unresolved Follow-ups;
- cheap checks, exact-head review, hosted evidence, publication, and receipt
  results as applicable under existing rules;
- Blockers, Follow-ups, and Preferences;
- an EXC-001 through EXC-006 assessment, including deletions, duplicate paths or
  state, abstractions added, and the simpler alternative considered;
- deviations from Phase A and final semantic-scope preservation;
- same-task provenance sufficient to retrieve the packet later; and
- the exact authorization sentence with the repository, PR, and full head
  filled in.

The AI then ends its turn. Authorization is only this entire later task-user
message:

```text
I authorize the AI to merge samovers/OFARM2 PR #<NUMBER> at head <FULL_HEAD_SHA>.
```

Before merge, the AI retrieves the original packet and later authorization and
rechecks the current PR head, open/non-draft state, close/reopen history since
the packet, semantic scope, same-task messages, required checks, existing
admission/publication evidence, and review disposition. Any invalidating change
returns to fresh evidence and a new packet or stops for reclassification.

The AI uses GitHub's normal pull-request merge operation with its expected-head
condition set to the authorized full SHA, such as the native
`--match-head-commit` option. The merge method remains whatever the existing
task and repository rules otherwise permit; this amendment neither selects nor
changes it. The AI must not pass `--admin` or `--auto`, bypass a native
requirement, or push the target branch directly. A native rejection is a stop,
not permission to use a different writer.

This amendment intentionally authorizes the PR head, not a particular base or
resulting merge commit. Base movement remains governed by existing GitHub
mergeability and OFARM2 admission/publication rules. If those existing rules
make evidence stale, that evidence must be refreshed. Version 1 adds no second
base or merge-candidate authority.

## 6. State and user changes

For approval-governed Delivery work:

```text
DELIVERY_ISSUE_DEFINED
  -> DRAFT_PR_WITH_PHASE_A
  -> PHASE_A_REVIEWED_ZERO_BLOCKERS
  -> USER_SEMANTIC_DECISION
  -> IMPLEMENT_AND_RUN_CHEAP_CHECKS
  -> EXACT_HEAD_CONTENT_AND_EXCELLENCE_REVIEW_ZERO_BLOCKERS
  -> REQUIRED_ADMISSION_BASELINES_AND_PUBLICATION
  -> FINAL_SCOPE_EVIDENCE_AND_EXCELLENCE_RECHECK
  -> READY_FOR_USER_FINAL_REVIEW
  -> AI_YIELDS_WITH_EXACT_HEAD_PACKET
  -> USER_AUTHORIZED_EXACT_HEAD_MERGE
  -> AI_RECHECKS_HEAD_STATE_GATES_AND_CANCELLATION
  -> GITHUB_NATIVE_PR_MERGE_WITH_EXPECTED_HEAD
  -> VERIFY_MERGED_AND_CLOSE_DELIVERY_ISSUE
```

Routine AI-operated work omits the semantic-decision states but never omits the
final packet, yield, later exact-head authorization, or native eligibility
checks.

If the user requests an in-boundary correction, the PR returns to implementation
and receives a fresh exact-head review and packet. No response leaves the PR
open and unmerged. Waiting is not approval, failure, or permission to create a
replacement PR.

## 7. Review classification and excellence

A code-excellence Blocker is a demonstrated in-scope violation of EXC-001
through EXC-006. It must name:

1. the concrete duplicate source, path, state, validation, compatibility layer,
   unnecessary abstraction, or obscured invariant;
2. the present maintenance, audit, testing, or isolation consequence;
3. the violated invariant; and
4. the smallest acceptable correction.

Equivalent clean alternatives, naming, formatting, and hypothetical future
reuse remain Preferences. Valid improvements outside the capability or primary
boundary become Follow-ups rather than expanding the PR. The task user may
decline final authorization or request in-boundary changes for any reason; the
Blocker classification constrains reviewers, not the user's final decision.
Line counts and automated complexity metrics may support a finding but never
replace this design judgment.

## 8. Smallest coherent Phase B change

After decision approval, the same PR makes one closed edit across the four
existing active surfaces:

1. `AGENTS.md` removes standing AI merge authority, inserts the final packet,
   yield, exact-head authorization, native expected-head merge, and concrete
   excellence Blockers.
2. `TASK_PROMPT.md` makes routine and approval-governed Phase C stop at the same
   packet and records the same invalidation rule.
3. `CONTRIBUTING.md` explains the human hold and evidence-backed excellence
   standard.
4. `.github/PULL_REQUEST_TEMPLATE.md` records the final packet and excellence
   evidence without pretending to create task-user authority.

The RFC is the durable amendment, not a competing active instruction surface.
No workflow, script, merge mechanism, credential, repository setting, policy
checker, evidence format, or runtime component is added.

## 9. Negative cases and traceability

Each case below is reachable through the normal task → Delivery PR → default
branch → later deployment path. The last column traces the invariant to its
Phase B instruction surface and smallest verification.

| Invariant | Reachable counterexample | Required result | Phase B owner and verification |
| --- | --- | --- | --- |
| HFQ-001 | Packet omits the PR, full head, changed paths, or excellence assessment | Refuse merge and complete a fresh packet | `AGENTS.md`, `TASK_PROMPT.md`, PR template; packet audit |
| HFQ-002 | AI presents the packet and merges in the same turn | End the turn without merging | `AGENTS.md`, `TASK_PROMPT.md`; ordering walkthrough |
| HFQ-003 | User says “go,” abbreviates the SHA, changes the PR/head, or the packet is no longer retrievable | Treat as no authority | `AGENTS.md`, `TASK_PROMPT.md`; exact-message hostile cases |
| HFQ-004 | A new commit, close/reopen, semantic expansion, cancellation, or conflicting message follows the packet | Invalidate and require fresh state | `AGENTS.md`, `TASK_PROMPT.md`; stale-authority walkthrough |
| HFQ-005 | Green checks, a GitHub approval, or earlier decision approval is treated as merge permission | Refuse; only the later exact task message authorizes | All four surfaces; authority-source search |
| HFQ-006 | PR is draft, head changed, a gate fails, or native merge rejects; AI proposes `--admin`, auto-merge, or direct push | Stop without bypass; refresh only through existing controls | `AGENTS.md`, `TASK_PROMPT.md`; native-path audit |
| HFQ-007 | An old PR has no approval explicitly granting merge, but age is claimed as authority | Apply the new final gate | `AGENTS.md`, `TASK_PROMPT.md`; authority-not-date audit |
| HFQ-008 | User requests an independent deployment or second-capability change | Stop and split or seek a new decision | `AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md`; boundary walkthrough |
| EXC-001 | Two paths make the same authority decision | Consolidate to one owner | All four surfaces; path trace |
| EXC-002 | A new checker or adapter copies owned state or validation | Derive from the owner or delete the duplicate | All four surfaces; duplicate-state search |
| EXC-003 | A hidden fallback bypasses the cited implementation | Remove or govern and test it directly | All four surfaces; invariant trace |
| EXC-004 | A superseded shim or flag remains without a current duty | Delete it or state duty and deletion trigger | All four surfaces; deletion inventory |
| EXC-005 | A framework layer serves only hypothetical reuse | Inline or demonstrate current rent | All four surfaces; abstraction inventory |
| EXC-006 | Bespoke machinery is added without considering the direct alternative | Use the simpler path or demonstrate the preventing invariant | All four surfaces; final assessment |
| EXC-007 | Review blocks only on naming, formatting, or an equivalent layout | Reclassify as Preference | Review protocol; disposition audit |

## 10. Verification

Phase A verification:

- compare this amendment with issue #355 and the parent workflow;
- confirm the authorized object is only the named PR and full head SHA;
- confirm the amendment preserves native GitHub merge and existing
  admission/publication controls;
- confirm every HFQ and EXC invariant has one reachable negative case and Phase
  B owner;
- confirm the complete PR boundary remains the five named paths;
- search for synthetic merge candidates, target-ref writers, exact-base leases,
  policy inventories, ready-episode identities, and other removed custody
  machinery; and
- `git diff --check` plus existing cheap package and workflow checks.

Phase B verification:

- search all four active surfaces for stale standing AI merge authority,
  merge-without-yield language, or inferred authorization;
- verify the same packet fields, later exact sentence, invalidation rule, and
  native expected-head merge appear without a competing authority path;
- verify no direct target writer, administrator bypass, auto-merge, new policy
  checker, or second merge-candidate system was introduced;
- verify every excellence Blocker cites EXC-001 through EXC-006 and concrete
  present cost;
- run existing mandatory cheap checks;
- obtain exact-head content and excellence review with zero Blockers;
- complete the existing admission, baseline, publication, and receipt evidence
  required for this workflow-governance change; and
- present this PR's own final exact-head packet, end the turn, and wait for its
  later exact merge authorization.

## 11. Provisional posture and review point

This is acceptable only for pre-deployment repository development. Because the
AI and user share one GitHub identity, the final hold depends on the AI obeying
the same-task procedure. Strong mechanical identity separation would require a
different credential and repository rule, which is separate Delivery work and
not implied here.

Review the amendment after the next three merged Delivery PRs. Record:

- whether any AI merge occurred without exact-head task-user authorization;
- whether stale authority was handled correctly;
- whether final review found material issues missed by agent review;
- whether excellence Blockers cited concrete invariants or became taste;
- the waiting time introduced by the hold; and
- whether the rule caused abandonment or an unsafe workaround.

The review point creates evidence; it does not automatically relax the gate.

## 12. Decision and reapproval triggers

Version 1 recommends:

- a mandatory final task-user decision for every AI-operated Delivery merge;
- one exact PR-and-head packet, mandatory yield, and one exact later sentence;
- the existing GitHub-native PR merge path with an expected-head guard and no
  bypass;
- concrete EXC-001 through EXC-006 failures as Blockers; and
- the five-path implementation boundary.

A new decision version or separate Delivery issue is required for inferred or
optional authorization, another authorization source, direct target-ref
custody, an exact integrated-candidate guarantee, a merge bot or executor,
identity or repository-policy changes, an automated quality score, an
independent-human reviewer mandate, a different primary boundary, or any
runtime, production, deployment, law, contract, or publication-control effect.

## 13. Phase A review disposition

Blockers, Follow-ups, and Preferences are recorded after review of this exact
Phase A head. Phase B must not begin until a fresh complete review reports zero
Blockers, the complete decision card is displayed, and the task user supplies
the card's exact version-1 approval sentence.

What is next: review this narrowed Phase A amendment in existing draft PR #356.
