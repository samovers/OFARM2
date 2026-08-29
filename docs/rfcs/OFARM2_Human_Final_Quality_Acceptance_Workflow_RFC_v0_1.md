# OFARM2 Human Final Quality Acceptance Workflow Amendment v0.1

**Status:** Phase A candidate; inactive until the task user approves decision
version 1 and the resulting implementation pull request later receives exact
merge-commit authorization and merges

**Contract identity:** `ofarm2.human-final-quality-acceptance-workflow.v0.1`

**Decision identity:** `HUMAN-FINAL-QUALITY-ACCEPTANCE-001`

**Proposed decision version:** `1`

**Parent workflow:** `ofarm2.proportional-delivery-workflow.v0.2`

**Delivery issue:** #355

**Primary trust boundary:** the task user's final acceptance of one immutable
integrated merge candidate versus the AI's authority to merge that candidate

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

Return final control over AI merge actions to the task user and make code
excellence an explicit acceptance invariant without restoring micro-PRs or
repeated artifact-level approvals.

The recommended decision has one outcome: **the task user accepts the quality
of one exact merge-commit candidate before the AI may write it to the target
branch.** The user receives one compact final packet that includes both
technical evidence and a concrete simplicity/elegance assessment. The AI then
stops. A later exact task-user message authorizes only the immutable commit
named in that packet, and the Git server accepts the write only while the target
still equals the authorized base.

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
- support AI-operated squash or rebase merging in version 1;
- preserve the ordinary PR-title merge message for AI-operated merges; version
  1 writes the already-created authoritative candidate object unchanged;
- add a merge bot, hosted merge executor, status store, or second candidate
  producer;
- change OFARM law, contracts, runtime behavior, profiles, schemas, data,
  deployment, production, or capability claims;
- silently revoke an approval granted in another task or reinterpret a merged
  pull request; or
- introduce an automatic-merge opt-out or exception in version 1.

## 4. Closed amendment to the parent workflow

On activation, this RFC prospectively supersedes only these parent-workflow
mechanics for every AI-operated Delivery pull request that is not already
governed by a valid task-user approval explicitly carrying the parent
workflow's previous AI merge authority:

- the AI's standing authority to merge after technical gates;
- the rule that pre-implementation semantic approval also authorizes merge;
- the direct transition from final scope recheck to merge;
- the routine-work rule permitting AI merge without a task-user stop;
- the normal target of one user approval stop for high-risk work;
- the Blocker definition's omission of demonstrated code-excellence failures;
  and
- ordinary AI-operated pull-request merge calls that guard the head but do not
  atomically bind the target ref to the authorized base.

Creation date, task start date, branch age, or pull-request age does not
preserve the old rule. An open or planned pull request that lacks such a valid
approval is governed by this amendment at activation. Valid already-approved
work retains its accepted authority only in its owning task and only until that
authority is cancelled, superseded, or expires under the accepted workflow; a
replacement or reopened pull request does not inherit it.

The normal target becomes two task-user decisions for approval-governed work—
semantic approval before implementation and exact merge-commit authorization
after the final packet—and one final authorization for routine AI-operated
work. The extra decision is the capability this amendment deliberately adds,
not process drift.

The first named consumer is this amendment's own PR #356: despite the parent
workflow still being active, the task user's instruction is narrower and this
PR will stop for the proposed exact merge-commit authorization before merge.
Any current or future implementation pull request for #353 or #160 is governed
according to its actual accepted authority at activation, not its creation
date.

All one-capability, one-boundary, risk-shaped Phase A, approval provenance,
review, admission, publication, recovery, cancellation, and substantive OFARM
requirements remain. The final task-user gate controls AI merge actions. It
does not prevent the repository owner from manually merging outside the AI
task, and the AI may not infer permission from such an external possibility.

## 5. Authority map

- The task user owns semantic approval, refusal, cancellation, requested
  changes, final quality acceptance, and exact merge-commit
  authorization.
- A pre-implementation decision card owns the approved capability, primary
  boundary, effects, non-effects, and invariants. Its approval authorizes
  implementation and evidence collection only.
- The Phase A contract owns detailed architecture, risk, expected areas,
  verification, and code-excellence invariants.
- The AI owns in-boundary implementation, commits, pushes, review handling,
  checks, admission, publication coordination, and preparation of the final
  packet. After exact merge-commit authorization it owns only the exact
  base-leased merge-commit write defined in section 9; it owns no ordinary
  pull-request merge call or alternative write path.
- Reviewers own demonstrated correctness, safety, and code-excellence Blocker
  findings. They do not own scope expansion or aesthetic vetoes.
- GitHub's read-only `refs/pull/<NUMBER>/merge` ref is the sole mechanical
  candidate producer. The Git receive-pack transaction owns the exact-base ref
  comparison and target write. Neither provides human intent.
- CI and publication systems own mechanical evidence only and, when required,
  must bind the same candidate produced by that ref.
- GitHub activity cannot provide task-user intent because the current human and
  agent operations share one repository identity.
- The task user may merge manually outside the AI task. The AI must not infer
  authorization from that possibility or from any GitHub event.
- Existing OFARM, runtime, database, tenant, key, audit, deployment, and
  publication authorities retain their current owners.

## 6. Trust model

### Protected assets

- the task user's real opportunity to inspect the completed change;
- the exact implementation the user accepts;
- clear, direct, maintainable code within the approved capability;
- one source of truth and one authoritative path per decision; and
- the existing substantive safety and evidence gates.

### Trusted sides

- the same Codex task's ordered task-user messages for final authorization;
- GitHub's read-only pull-request merge ref as the sole candidate producer;
- immutable Git commit, parent, and tree identities for candidate content;
- the Git server's explicit expected-base lease for the atomic target write;
- live pull-request transition history for procedural lifecycle checks, not for
  atomic candidate identity or human intent;
- the non-malicious AI for stopping at the final gate;
- reviewers for evidence-backed findings; and
- existing CI/publication mechanisms for their current mechanical claims.

### Untrusted inputs

- the earlier semantic approval as purported final quality acceptance;
- an agent-authored statement that the user “would approve”;
- GitHub reviews, comments, labels, mergeability, or credentials as proof of a
  human decision;
- a head SHA without its target, live base, exact merge commit, integrated tree,
  and open episode as proof that the reviewed candidate is unchanged;
- an ordinary `gh pr merge`, REST merge, GraphQL merge, bare `git push`, bare
  `--force`, implicit lease, locally constructed merge, or second candidate
  producer as a substitute for the one authorized transition;
- a successful pre-write read as proof that the target cannot change before a
  later ordinary merge call;
- current open state without transition history as proof that no close/reopen
  cycle occurred;
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

## 7. Primary risk and containment

The primary authority risk is a time-of-check/time-of-write race: the user
accepts candidate `M1` over base `B1`, the AI verifies it, another change moves
the target to `B2`, and an ordinary merge call then creates a different result
`M2`. A final reread only narrows that race; it does not close it.

Containment has one authoritative producer and one authoritative writer.
GitHub's read-only `refs/pull/<NUMBER>/merge` produces the only eligible
merge-commit candidate. The candidate's exact commit, ordered parents, and tree
are validated and authorized. The AI may then write only that commit with a
single-ref `git push` using the explicit
`--force-with-lease=<TARGET_REF>:<FULL_BASE_SHA>` form. Git receive-pack compares
the current target ref with the authorized base and performs the write as one
server-side ref transaction; if the base changed after every preceding read,
the target remains unchanged.

Pull-request head/ref state, open/close history, and same-task cancellation
cannot participate in that target-ref transaction. Version 1 therefore
guarantees atomic candidate content, while non-target PR state and cancellation
remain procedural checks immediately before and after the write. A head/ref,
close/reopen, or cancellation transition racing inside the single push may not
prevent the already-authorized exact candidate from landing. That narrow
residual is provisional debt and must be reported, not misrepresented as
absolute stale-state enforcement.

The secondary delivery risk is replacing silent AI merge authority with an
unbounded, subjective review loop that recreates the delay this workflow
removed. Its containment has three parts:

1. code-excellence Blockers must identify a concrete duplicate source, path,
   state, validation, compatibility layer, unnecessary abstraction, or obscured
   invariant and its actual maintenance, audit, testing, or isolation cost;
2. the reviewer must name the smallest correction, while style and equivalent
   clean alternatives remain Preferences; and
3. a requested change outside the approved capability or boundary becomes
   separate Delivery work or a new decision rather than expanding the PR.

## 8. Stable invariants

### Human final acceptance

- **HFQ-001 — Final packet before AI merge.** Every Delivery PR in which the AI
  would perform the merge reaches a complete immutable merge-commit packet
  first.
- **HFQ-002 — Mandatory yield.** The AI presents the packet and ends its turn.
  It cannot present the packet and merge in one turn.
- **HFQ-003 — Exact later authorization.** Only the entire visible text of a
  later task-user message in the same task, naming every field of the immutable
  merge commit and its procedural open episode, authorizes the exact target
  write. The original packet and later authorization must remain directly
  retrievable with stable references in that order; a summary, paraphrase, or
  reconstructed item is not authority.
- **HFQ-004 — No inherited merge authority.** Semantic approval authorizes
  implementation and evidence collection, not merge. Routine classification,
  GitHub activity, reviews, checks, admission, publication, credentials, or
  silence never authorizes merge.
- **HFQ-005 — Atomic candidate integrity; procedural non-target refusal.** The
  authorized merge commit and tree are immutable, and an exact-base lease must
  reject target drift without writing. An observed live-head, candidate-ref,
  target-identity, close/reopen, semantic, cancellation, or task-message change
  before the write revokes authority. Such a non-target transition racing
  inside the one server operation is detected and reported afterward; it cannot
  change the exact Git candidate that lands.
- **HFQ-006 — User changes remain bounded.** In-boundary requested changes
  return the PR to implementation and fresh exact-head review. Out-of-boundary
  requests stop for reclassification or a new decision.
- **HFQ-007 — Existing authority is historical.** At activation, the amendment
  applies to every AI-operated Delivery pull request not governed by a valid
  task-user approval explicitly carrying the previous AI merge authority.
  Creation date alone preserves nothing. Valid already-approved work keeps its
  accepted authority in its owning task until that authority is cancelled,
  superseded, or expires; this amendment does not silently reinterpret it.
- **HFQ-008 — One producer and one writer.** Only GitHub's live read-only
  pull-request merge ref may produce the merge-commit candidate, and only the
  explicit exact-base leased single-ref push may write it. Missing merge refs,
  squash, rebase, ordinary PR merge APIs, local candidate construction,
  implicit leases, bare `--force`, `+` refspecs, and fallback writers fail
  closed in version 1.

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

## 9. Final packet and authorization

### One authoritative candidate

Version 1 supports only the merge-commit path. GitHub's live read-only
`refs/pull/<NUMBER>/merge` ref is the sole authoritative candidate producer.
[GitHub documents](https://docs.github.com/en/pull-requests/reference/pull-requests#pull-request-refs-and-merge-branches)
that this ref is its simulated current merge result and that it updates when
either base or head changes. Existing admission code already validates this
same ref; it is a verifier and evidence consumer, not a second producer.

No `git merge-tree`, locally created merge commit, squash commit, rebased
commit, ordinary merge-API result, or “equivalent” construction is eligible.
If the authoritative ref is absent, stale, unavailable, or not a commit, the AI
must refuse to prepare a final packet.

The immutable candidate identity is:

- repository identity `samovers/OFARM2`;
- pull-request number;
- full target ref `refs/heads/<TARGET_BRANCH>`;
- full live base commit SHA `B`;
- full pull-request head commit SHA `H`;
- full authoritative merge-commit SHA `M` from
  `refs/pull/<NUMBER>/merge`;
- the ordered parent list of `M`, which must equal exactly `[B, H]`; and
- full tree SHA `T` owned by `M`.

The commit SHA also binds the candidate's existing author, committer,
timestamps, and message. They land unchanged and the packet must display the
commit subject. Version 1 accepts GitHub's test-merge message format. Rewording
it would create a different commit and require an additional candidate builder,
so that option is deliberately deferred.

The authorization context separately includes the open-episode marker:
`initial:<PR_CREATED_AT>` when the pull request has never been closed, otherwise
`reopened:<REOPEN_EVENT_ID>` naming the immutable event that began the current
open episode. It supports procedural cancellation checks but is not falsely
claimed to be part of the atomic Git ref transaction.

When hosted evidence is required, its admitted base and execution-merge SHA
must equal `B` and `M`. Evidence for another base, head, merge commit, or tree is
stale even if the pull-request head did not change.

The final packet is compact and contains:

- Delivery issue and PR;
- the complete immutable candidate identity above;
- the procedural open-episode marker and the disclosed lifecycle-race residual;
- capability and primary trust boundary;
- final changed paths and material diff summary;
- permitted effects, non-effects, and unresolved Follow-ups;
- cheap checks, exact-head review, hosted evidence, and publication results as
  applicable;
- Blockers, Follow-ups, and Preferences;
- EXC-001 through EXC-006 assessment, including deletions, remaining duplicate
  state or paths, abstractions added, and the simpler alternative considered;
- deviations from Phase A;
- same-task provenance sufficient to retrieve the original packet after it is
  posted;
- the one exact, fully substituted target-write command; and
- the exact authorization sentence with every candidate and open-episode field
  filled in.

The AI then stops. Authorization is only this entire later task-user message:

```text
I authorize merge of samovers/OFARM2 PR #<NUMBER> into <FULL_TARGET_REF> by writing merge commit <FULL_MERGE_COMMIT_SHA> with base <FULL_BASE_SHA>, head <FULL_HEAD_SHA>, tree <FULL_TREE_SHA>, and open episode <OPEN_EPISODE_MARKER>.
```

### One authoritative target writer

Before writing, the AI must re-read the live target, base, head, candidate ref,
candidate commit, parents, tree, current pull-request state, transition history,
same-task messages, original packet, and later authorization. Every SHA and ref
in the packet, authorization, and command must be a literal full value. Any
pre-write mismatch, observed close/reopen, cancellation, missing original item,
or abbreviated value requires a fresh packet, yield, and later authorization.

The only AI-operated version-1 merge primitive is one Git smart-protocol push
with one refspec and the explicit expected-value lease:

```text
git push --force-with-lease=<FULL_TARGET_REF>:<FULL_BASE_SHA> origin <FULL_MERGE_COMMIT_SHA>:<FULL_TARGET_REF>
```

The displayed placeholder form must never be executed. The final packet must
contain the fully substituted literal command. Bare `--force-with-lease`, bare
`--force`, a `+` refspec, variables, command substitution, an implicit remote-
tracking expectation, multiple refspecs, `gh pr merge`, and REST or GraphQL
merge mutations are forbidden.

Before displaying or executing the literal command, the AI must verify that
`origin` resolves to `samovers/OFARM2`, the full target ref is the PR's target
in that repository, and no branch rule, merge queue, or server policy requires
a different transition or an explicit bypass. The AI never changes or bypasses
such policy. Rejection or incompatibility stops for a new decision.

The explicit lease makes the server compare the current target ref with `B` in
the same ref transaction that writes `M`. Because `M` has first parent `B`, the
accepted transition is also a fast-forward merge-commit write. If another pull
request advances the target to `B2` after the AI's final read, the lease rejects
the command and the target remains `B2`; the AI must not retry under the old
packet. This uses the only stable explicit-expectation form documented by
[`git push`](https://git-scm.com/docs/git-push#Documentation/git-push.txt---force-with-leaseltrefnamegtltexpectgt);
it never relies on a mutable remote-tracking ref.

After any command result, the AI reads the target ref. Success means the target
equals exactly `M`. If the result was ambiguous but the target equals `M`, the
write succeeded and must not be repeated. Any other target means no success may
be claimed and requires fresh state. Server policy rejection is final for that
attempt; the AI must not bypass it.

Pushing the exact merge commit makes `H` reachable from the target. GitHub's
[documented indirect-merge behavior](https://docs.github.com/en/pull-requests/reference/pull-request-merges#indirect-merges)
should mark the pull request merged. The AI must verify target `M`, pull-request
disposition, and issue closure afterward. If GitHub does not mark the PR merged,
the AI reports the mismatch and performs no second target write or manual close
disguised as merge.

The final pre-write and post-write checks preserve procedural head/ref,
close/reopen, and cancellation handling. They cannot be atomic with the target
Git ref write. If such a non-target transition races within the one push, the
exact authorized content may land; the AI must report the provisional state
breach. Version 1 makes no stronger claim. Eliminating that residual would
require a future trusted executor that owns PR/task state and target-ref custody
in one transition.

There is no automatic-merge authorization path in version 1. If evidence later
shows a need, it requires its own explicit workflow amendment rather than an
informal exception.

## 10. Review classification

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

## 11. State and ordering

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
  -> AUTHORITATIVE_MERGE_REF_CANDIDATE_BOUND_TO_EVIDENCE
  -> READY_FOR_USER_FINAL_REVIEW
  -> AI_YIELDS_WITH_FINAL_PACKET
  -> USER_AUTHORIZED_IMMUTABLE_CANDIDATE_MERGE
  -> AI_RECHECKS_CANDIDATE_HISTORY_AUTHORIZATION_AND_CANCELLATION
  -> EXACT_BASE_LEASED_SINGLE_REF_WRITE
  -> VERIFY_TARGET_EQUALS_AUTHORIZED_MERGE_COMMIT
  -> RECHECK_AND_REPORT_LIFECYCLE_STATE
  -> VERIFY_PR_MERGED_AND_CLOSE_DELIVERY_ISSUE
```

Routine AI-operated work omits the semantic decision-card states but never
omits the final packet, yield, and immutable-candidate authorization states.

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

A lease rejection or a pre-write candidate mismatch changes no target ref and
returns the work to fresh integration evidence and a new final packet. Content
review may remain valid for the same head, but any base-sensitive review,
admission, baseline, publication, or candidate claim must be refreshed. The old
authorization is never replayed.

## 12. Proposed architecture and smallest coherent change

Root `AGENTS.md` remains the one source of standing procedure. Phase B makes a
closed semantic edit across the four active surfaces:

1. `AGENTS.md` changes AI merge authority, the state machine, final scope step,
   and Blocker definition; it adds the sole candidate producer, exact-base
   leased writer, final packet, authorization rule, and excellence invariants.
2. `TASK_PROMPT.md` makes Phase A and Phase C collect the same invariants and
   stop at the final packet; it carries the same candidate and write refusal.
3. `CONTRIBUTING.md` explains the human merge hold and concrete design-quality
   review standard.
4. `.github/PULL_REQUEST_TEMPLATE.md` captures the excellence assessment and
   immutable merge-commit, lease, lifecycle-residual, and final-packet fields.

This RFC is the durable amendment and evidence. It does not become a competing
active instruction surface.

An explicit new merge primitive is necessary: the exact-base leased single-ref
push in section 9 replaces ordinary AI-operated PR merge calls. It needs no new
script, workflow, bot, status store, GitHub check, comment protocol, credential,
permission, setting, quality score, or compatibility shim. GitHub already
produces the read-only candidate; the Git server already supplies the exact
expected-ref transaction; and existing admission code already consumes the same
candidate ref when hosted evidence is required.

This is the simplest credible version-1 design:

- ordinary GitHub merge calls are rejected because they condition only on the
  head and leave the base race open;
- squash and rebase are deferred because they do not expose one already-created
  authorized commit object with the required parent semantics;
- a new hosted executor is unnecessary because an explicit Git ref lease
  already performs the required compare-and-write; and
- a locally constructed fallback is rejected because it would create a second
  authority-critical candidate path.

The five-path PR boundary therefore remains complete: the merge primitive is a
standing instruction implemented in the existing active policy surfaces, not a
new executable component. If Phase B discovers that the server or repository
cannot honor the exact literal lease, work stops for a new decision rather than
adding automation or another writer.

## 13. Failure cases and negative evidence

For this pre-deployment governance boundary, every case below is reachable
through the normal task → Delivery PR → default branch → later deployment path.
No case depends on a fabricated internal state. Every invariant has a reverse
trace from its reachable counterexample to the Phase B policy surface and
verification.

| Invariant | Reachable counterexample | Required refusal or correction | Phase B owning surface | Verification |
| --- | --- | --- | --- | --- |
| HFQ-001 | A real Delivery PR reaches green checks but its packet omits the authoritative merge commit, ordered parents, tree, or another candidate field | Refuse the write and produce a complete fresh packet | `AGENTS.md`, `TASK_PROMPT.md`, PR template | Packet-field and merge-object audit on the final candidate |
| HFQ-002 | The AI posts a complete packet and invokes merge in the same turn | End the turn without merge; require a later task-user message | `AGENTS.md`, `TASK_PROMPT.md` | Ordering walkthrough proves a mandatory yield state |
| HFQ-003 | The user writes “looks good,” abbreviates a SHA, changes a commit/parent/tree field, or the original packet is no longer directly retrievable | Treat it as no authority and redisplay a fresh packet | `AGENTS.md`, `TASK_PROMPT.md` | Exact-sentence and same-task retrieval hostile cases |
| HFQ-004 | Phase A approval, a GitHub approval, green checks, or silence is treated as permission to merge | Refuse; only the later exact merge-commit sentence authorizes the write | `AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md` | Search active surfaces for inherited or inferred merge authority |
| HFQ-005 | Base `B1`, head `H`, and merge commit `M1` pass the final reread; another PR advances the target to `B2` before the write | The exact `B1` lease rejects without changing `B2`; no retry or replay, and a new candidate and packet are required | `AGENTS.md`, `TASK_PROMPT.md`, PR template | Bare-repository hostile transition proves an after-check base move cannot write `M1` |
| HFQ-005 non-target residual | The live head or candidate ref moves, the PR closes/reopens, or a cancellation arrives after the final procedural read but during the one leased push | The exact authorized Git candidate may land; post-write recheck detects and reports the provisional state breach, with no additional write | `AGENTS.md`, `TASK_PROMPT.md`, PR template | Review confirms the contract claims atomic target content, not atomic PR/task state |
| HFQ-006 | During final review the user requests an independent deployment-authority or second-capability change in the same PR | Stop; split the work or require a new semantic decision before editing | `AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md` | Scope-expansion walkthrough against the one-boundary rule |
| HFQ-007 | A PR existed before activation but had no valid approval, and the AI claims its age preserves standing merge authority | Apply this amendment; grandfather only a directly retrievable valid approval explicitly carrying the old authority | `AGENTS.md`, `TASK_PROMPT.md` | Inventory pre-activation open work by accepted authority, not date |
| HFQ-008 | The merge ref is missing, or the AI proposes a local merge, squash/rebase, `gh pr merge`, REST/GraphQL merge, bare push, implicit lease, or fallback writer | Refuse; only the live merge-ref commit and exact-base leased single-ref push are eligible | `AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md`, PR template | Search active surfaces for alternate producers/writers and audit the literal final command |
| EXC-001 | Two candidate constructors, validators, or dispatch paths can each make the same authoritative decision | Block and consolidate to one authoritative path or clearly separate ownership | `AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md`, PR template | Final packet names the one GitHub merge-ref producer and one leased writer; exact-head review traces both |
| EXC-002 | A new checker copies a field inventory, validation rule, or derived state already owned elsewhere | Block and derive from the owner or delete the duplicate unless independent repetition is explicit evidence | `AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md`, PR template | Duplicate-state/path search plus final excellence assessment |
| EXC-003 | A hidden fallback or undocumented side path lets production behavior bypass the implementation cited for an invariant | Block; remove the bypass or make the complete path explicit and directly tested | `AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md`, PR template | Invariant → implementation → negative-test trace for every material path |
| EXC-004 | A superseded shim, feature flag, compatibility branch, or old implementation remains with no current duty or deletion trigger | Block and delete it, or record the time-bounded duty and objective deletion trigger | `AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md`, PR template | Deleted-path inventory and retained-path justification |
| EXC-005 | A helper or framework layer is introduced only for hypothetical future reuse and removes no current duplication | Block and inline/remove it unless it isolates the present boundary, removes concrete duplication, or has multiple current consumers | `AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md`, PR template | Abstraction inventory with present-tense rent for each item |
| EXC-006 | A change adds material concepts, indirection, state, or bespoke conformance machinery without addressing a simpler credible design | Block until the simpler alternative is adopted or the preventing invariant is demonstrated | `AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md`, PR template | Final packet records the alternative, tradeoff, and evidence |
| EXC-007 | A reviewer blocks an implementation solely for a preferred name, formatting choice, or equivalent clean module layout | Reclassify as Preference; do not delay merge on taste | `AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md` | Review-disposition audit requires a concrete EXC-001–EXC-006 violation for every excellence Blocker |

## 14. Verification

Phase A verification:

- wording audit against v0.2 authority, state, review, and merge clauses;
- confirm the proposed rule distinguishes agent review from task-user review;
- confirm every HFQ and EXC invariant has a reachable negative row and every row
  maps back to its invariant;
- confirm the sole merge-ref candidate binds target, base, head, exact merge
  commit, ordered parents, and tree;
- confirm the explicit expected-base lease is part of the same server ref
  transaction as the exact candidate write;
- confirm ordinary merge calls, local candidates, squash/rebase, fallback
  writers, and implicit leases fail closed;
- confirm lifecycle checks and their disclosed in-command residual are not
  described as atomic;
- confirm the original packet and later authorization must remain directly
  retrievable in the same task and in order;
- confirm the five-path PR boundary contains one workflow capability; and
- `git diff --check`.

The Phase A mechanics prototype uses two isolated bare repositories. With the
target at `B1`, the explicit `B1` lease accepts candidate `M1`. After a competing
commit advances the target to `B2`, the identical command is rejected as stale
and the target remains exactly `B2`. The prototype also checks that `M1` has
ordered parents `[B1, H]` and records its tree. This is negative evidence for
the primitive, not authorization to write a real repository target.

Phase B verification:

- search all four active surfaces for stale AI standing merge authority,
  one-stop target language, and merge-without-yield instructions;
- search for competing authorization sentences, candidate producers, and merge
  writers;
- verify every active surface contains the same default no-merge posture;
- verify the PR template records the exact merge commit, ordered parents, tree,
  explicit lease, lifecycle residual, and excellence evidence but does not
  claim to create task-user authority;
- run a temporary bare-repository hostile transition: accept `M1` only when the
  target equals `B1`; then advance the target to `B2` after the final read and
  prove the same `B1` lease rejects while the target remains `B2`;
- prove the literal success-path candidate has parents `[B1, H]`, tree `T`, and
  target result exactly `M1`;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- mandatory cheap workflow checks;
- exact-head content and excellence review with zero Blockers;
- existing hosted admission, baseline, and publication evidence required for a
  workflow-governance change, with admitted base and execution merge equal to
  the final `B` and `M`; and
- the new final packet and exact merge-commit task-user authorization for
  this PR itself.

## 15. Provisional posture and review point

This is acceptable only for pre-deployment repository development. It changes
repository merge authority and code-quality review, not production authority or
GitHub identity separation.

The procedural hold depends on a non-malicious AI because the agent and user
share one GitHub identity and `main` is unprotected. Strong mechanical
separation would require a distinct least-privilege agent identity and a branch
rule requiring the human identity. That is a separate custody/permissions
capability and is not silently added here.

Candidate content has a narrower mechanical guarantee: the explicit target-ref
lease atomically refuses base drift. Pull-request head/ref/lifecycle and
task-message state remain outside the Git transaction. A transition racing
within the one push is accepted provisional debt only because it cannot alter
the exact authorized commit; it must still be detected and reported after the
write.

Review this amendment after the next three merged Delivery PRs under it. Record:

- whether any AI merge occurred without exact merge-commit task-user
  authorization;
- whether any authorization became stale and was handled correctly;
- whether any exact-base lease rejected a raced target update without changing
  the target;
- whether any head/ref, close/reopen, or task-message transition raced inside
  the push and how the residual was reported;
- whether code-excellence Blockers cited concrete EXC invariants or became taste;
- whether final review found material issues missed by agent review;
- the waiting time introduced by the final hold; and
- whether teams attempted process-only PRs or hidden auto-merge workarounds.

The rule remains active after the review point unless an explicit amendment
changes it. The review creates evidence; it does not automatically relax the
human gate.

## 16. Decision and reapproval triggers

Version 1 recommends:

- mandatory exact merge-commit final user authorization before every AI merge
  of a Delivery PR;
- one merge-commit-only candidate producer and one exact-base leased target
  writer for AI-operated version-1 merges;
- unchanged retention of the authoritative candidate's GitHub test-merge
  metadata and message in target history;
- no automatic-merge exception;
- concrete EXC invariants as merge-blocking acceptance conditions; and
- the five-path prospective implementation boundary.

A new decision version is required if Phase B proposes:

- optional or inferred auto-merge;
- authorization without the complete candidate identity or open-episode
  marker;
- squash, rebase, a local or alternate candidate producer, an ordinary PR merge
  API, an implicit lease, a fallback writer, or removal of the exact-base
  server comparison;
- a claim of atomic PR head/ref/lifecycle or task-message cancellation without a
  trusted executor that owns those states and the target write together;
- GitHub activity as human authority;
- a different primary trust boundary or additional active policy surface;
- an automated subjective quality score or new CI gate;
- independent human reviewer requirements;
- GitHub identity, credential, permission, ruleset, or branch-protection work;
- retroactive cancellation of another task's approval; or
- any runtime, production, deployment, law, contract, or publication-control
  effect.

## 17. Phase A review disposition

Blockers, Follow-ups, and Preferences are recorded after review of this exact
Phase A head. Phase B must not begin until the visible version-1 decision card
has zero Blockers and the task user supplies the exact approval sentence named
by that card.

What is next: resolve this Phase A review in existing draft PR #356 and present
the complete version-1 decision card only after zero Blockers.
