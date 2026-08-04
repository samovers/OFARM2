# OFARM2 Pre-Deployment AI-Assisted Development Workflow — Phase A Contract v0.1

**Status:** architect-approved; Phase B implementation authorized only in PR
`https://github.com/samovers/OFARM2/pull/285`; workflow inactive until that PR
merges; no deployment or production effect

**Contract identity:**
`ofarm2.predeployment-ai-assisted-development-workflow.v0.1`

**Decision identity:** `PREDEPLOYMENT-WORKFLOW-001`, proposed version `2`

**Superseded decision attempt:** version `1` was displayed and the task user
sent its approval sentence, but approval recognition and Phase B did not begin
before exact-head review found the incomplete trust and authority model. Version
`1` is withdrawn, creates no implementation or merge authority, and cannot be
reused. No repository approval record or workflow change resulted.

**Motivating implementation programme:** #176

**Review-and-merge loop evidence:** #218

**Primary trust boundary:** a same-task Codex `userMessage` as provisional
authority for a pre-deployment repository decision versus the AI's bounded
authority to carry out, verify, review, and merge that approved decision

**Phase A review-head boundary:** this RFC only

**Final workflow PR boundary:** this RFC, `AGENTS.md`, and `TASK_PROMPT.md`
only

## 1. Decision in plain English

The task user should approve understandable effects, risks, and boundaries.
The task user should not be required to verify hashes, byte counts, test-node
inventories, review-comment mechanics, or implementation details.

For a materially authority-bearing development change, the AI must first show
one short plain-English decision card. One later exact same-task Codex
`userMessage`, not created or relayed by AI, tooling, or delegation, authorizes
the AI to complete the approved repository change through the card's declared
merge boundary. Under the normal merge-after-gates posture, that standing
authority includes mechanical evidence, implementation, review fixes, PR
maintenance, and merge after the declared gates pass. This v0.1 defines no
second approval at merge time.

No additional task-user confirmation is required while the work stays inside
the approved decision envelope. A new approval is required only when the
trust boundary, authority map, permitted effect, non-effect, invariant, file
boundary, or irreversible behavior changes materially.

This contract governs pre-deployment repository development only. It never
authorizes deployment, current/default promotion, release approval, a
high-consequence runtime binding, a security waiver, production data access,
or another production authority action.

## 2. Problem and learning value

Current `AGENTS.md` and `TASK_PROMPT.md` do not mandate exact-byte cards,
publication-only PRs, or private-task provenance re-reviews. Those mechanics
arose in #176-specific contracts and review practice. They have made
development slow and ask the task user to confirm technical evidence the task
user cannot reasonably evaluate.

Those mechanics protect a real boundary: AI can act through the repository
owner's GitHub credentials, so GitHub activity cannot prove human intent. The
same boundary can be preserved more simply by keeping the same-task Codex
`userMessage` as provisional human-intent evidence while delegating mechanical
follow-through to AI and CI.

This contract validates a simpler design:

- one task-user decision per material trust boundary;
- one understandable approval sentence;
- one bounded execution envelope;
- automatic technical follow-through through merge; and
- a new task-user decision only for material authority expansion.

Current repository policy already requires Phase A approval for high-risk work
and directs agents to merge when acceptance criteria pass with no demonstrated
Blocker. This contract adds simpler approval evidence, standing authority for
in-boundary follow-through, and explicit material-change and cancellation
rules. It prevents future contracts from adding stronger ceremony without a
specific reason.

## 3. Scope and relationship to existing authority

This is a package-local, repository-wide development-workflow contract. Issue
#176 is its motivating implementation programme, not the owner of a temporal
or runtime outcome created by this RFC. Issue #218 is evidence that the
repository's review-and-merge loop can operate; it does not validate human
approval, task provenance, or the workflow proposed here. This contract does
not amend OFARM law, ADR 0002, an artifact lifecycle, tenant knowledge order,
runtime truth, or production governance.

When implemented, it governs prospective OFARM2 pre-deployment development
decisions unless an accepted contract explicitly requires a stronger approval
procedure for that exact later action.

It does not supersede or modify:

- `ofarm.temporal-governance-decision-log.issue176-predeployment.v0.2` at
  `docs/rfcs/OFARM_Temporal_Governance_Decision_Log_Evidence_Amendment_RFC_v0_2.md`;
- the existing temporal decision-log entry or its currentness chain;
- completed approval records or their historical evidence;
- the meanings of `CANDIDATE_INACTIVE`, `GOVERNED_INACTIVE`, active,
  current/default, or deployed;
- the approved architecture Python-source snapshot design;
- ADR 0002's temporal semantics or ownership boundaries;
- the production-versus-legacy firewall; or
- issue #192.

An existing contract-specific approval rule remains controlling when it
expressly governs the future action being requested. It may be simplified only
by a versioned amendment to that contract. Completed decisions are never
retroactively re-approved or rewritten by this workflow.

New Phase A contracts should use this workflow and must not introduce an
exact-byte approval sentence, approval digest in human text, separate
publication-only PR, or private-task provenance re-review unless a specific
production, deployment, currentness, legal, or authority requirement makes
that stronger ceremony necessary.

This workflow does not govern its own adoption. The current `AGENTS.md` and
`TASK_PROMPT.md` rules govern this RFC's review, explicit approval,
implementation, exact-head technical review, and merge. The simple approval
sentence is only a convenient way to satisfy the current explicit-approval
rule. The workflow becomes active only after its adoption PR merges; it cannot
authorize that adoption or weaken its review.

### 3.1 Closed trust model

This provisional workflow protects:

- the task user's expressed decision, cancellation, and refusal;
- the association between that decision and one complete live card;
- one-approval/one-PR consumption; and
- every stronger accepted contract and production boundary.

It provisionally trusts the named Codex task surface to expose message roles,
ordering, task identity, and stable directly retrievable item references. It
also trusts a non-malicious AI to read and report those facts accurately and
to obey this contract. Git, GitHub, reviewers, and CI are trusted only to
provide ordinary mechanical commit, diff, review, and check evidence. They do
not supply human authority.

The following are untrusted as approval or scope authority: repository-owner
credentials, GitHub records or metadata, PR state, AI-authored text, messages
from another task, implementation code, generated evidence, caller data, and
any digest or reference supplied by those sources.

The threat model includes accidental card or approval misbinding, a stale or
superseded card, loss of directly retrievable original task items, replay
across PRs, a later cancellation, task-surface unavailability, and observable
changes to the reviewed head, source paths, or governing files. Those cases
must fail closed under this contract.

The threat model excludes a compromised Codex platform or transport, a
compromised task-user account, a malicious or compromised AI process, and a
compromised Git, GitHub, CI, dependency, filesystem, or operator capable of
forging the evidence on which the workflow relies. Process mutation or source
substitution observable through the ordinary reviewed diff is in scope;
undetectable platform or host compromise is not.

The result is procedural pre-deployment evidence, not independent proof
against fabrication by the AI or platform. Before deployment it must be
replaced by an independently human-controlled and independently verifiable
approval or signing system.

## 4. Decision envelope

Every live decision card binds one prose-only decision envelope containing
exactly the following decision-bearing fields:

| Field | Meaning |
|---|---|
| `decisionId` and `version` | Stable identity of the task-user decision. |
| `problem` | The one problem being solved. |
| `recommendedDecision` | The outcome the AI recommends. |
| `primaryTrustBoundary` | The one authority or custody boundary changed. |
| `authorityMap` | Closed ownership of the decision, technical law, execution, review, mechanical evidence, and preserved authorities. |
| `primaryRiskAndBound` | The main risk and the rule that contains it. |
| `permittedEffects` | Closed effects the approved work may create. |
| `nonEffects` | Closed effects it must not create. |
| `invariants` | Stable, falsifiable conditions that must remain true. |
| `implementationBoundary` | Closed maximum repository path or path-prefix envelope that the technical contract may narrow. |
| `implementationPr` | Stable reference of the already-created draft PR that alone may consume the approval. |
| `verificationGates` | Checks that must pass before merge. |
| `reapprovalTriggers` | Material changes that stop execution. |
| `provisionalPosture` | Why the design is acceptable before deployment and its replacement path. |

The user decision binds the unique, most recent, unsuperseded complete live
card identified by decision identity, version, and stable card-item reference
in the same task. No canonical byte representation, card digest, envelope
digest, byte count, or human verification of mechanical identity is required.

Technical contracts, code diffs, commit hashes, generated manifests, test
inventories, and review records are supporting evidence. They do not expand
the decision envelope and are not separate task-user decisions.

The live card owns the maximum user-approved effects, non-effects, primary
trust boundary, authority map, decision-level invariants, maximum repository
path envelope, and named implementation PR. The approved Phase A technical
contract owns detailed architecture, detailed invariants, and the exact
implementation path allowlist. It may narrow or refine the card, but may never
widen, relax, or contradict it. The merge-time path authority is the technical
contract's exact allowlist, which must be a subset of the card's maximum path
envelope. Any conflict, widening, relaxation, or unclear refinement stops for
a new decision version.

## 5. Plain-English decision card and approval

Before requesting approval, the AI must show one complete card containing:

1. the identity, version, problem, and recommended decision;
2. the trust boundary, authority map, permitted effects, non-effects, and
   primary risk;
3. the invariants, maximum path envelope, and verification gates;
4. the stable reference of the already-created draft implementation PR;
5. the reapproval triggers and provisional replacement posture;
6. that the AI may merge only that named PR after gates pass; and
7. the exact approval sentence.

Technical evidence may be linked below the card for reviewers, but it must not
be presented as something the task user must understand or confirm.

Only one card is live for an identity and version; a replacement withdraws its
predecessor. A semantic field change increments the version. Meaning-preserving
spelling, formatting, or wording corrections and unchanged redisplay may retain
it, but only the newest stable card-item reference remains live. An approved
card cannot be semantically changed under the same version.

Before recognizing a later message as approval or beginning implementation,
the AI must verify that the task surface assigned the live card a directly
retrievable stable item reference. If it cannot, the workflow stops. The task
user does not inspect or approve that reference.

The exact approval sentence is:

```text
I approve OFARM2 decision <DECISION_ID> version <VERSION>.
```

The placeholders must be replaced by the values on the complete live card.
The task user may type the sentence or copy it from that card. It is valid only
as a later same-task Codex `userMessage` not created or relayed by AI, tooling,
or delegation. The entire visible message must equal that sentence: Markdown
fences, quotations, prefixes, suffixes, or other decision text make it invalid.
Codex transport metadata is not part of the visible message.

Generic approval, `go`, PR approval, merge, GitHub review, comment, reaction,
repository credential, commit, check, AI message, tool message, automation, or
delegated-agent message never counts as the task-user decision.

The Codex user-message role, task identifier, stable item reference, and order
are provisional approval evidence. Approval resolves only to the unique, most
recent, unsuperseded earlier card with the matching identity and version. If
the task surface cannot distinguish or preserve those facts, execution stops.

The named draft PR must exist before the card is displayed. Its stable PR
reference is decision-bearing and cannot be first assigned or replaced after
approval. Closing that PR unmerged expires the authority; using another PR
requires a new decision version and approval.

## 6. Standing authority after approval

One valid approval is bound directly to the draft implementation PR named on
the complete live card. It cannot be transferred to or reused for another PR.
Within that one PR, it explicitly authorizes the AI, without additional user
confirmation, to:

- implement the allowed paths and add their necessary tests and documentation;
- regenerate required mechanical digests, manifests, snapshots, and test
  inventories;
- commit, push, maintain truthful PR metadata, and manage review requests;
- classify and address review, fixing in-envelope Blockers while leaving
  Follow-ups outside and declining valueless Preferences;
- rerun checks and perform semantics-preserving rebases or conflict resolution;
  and
- mark ready and merge the exact verified head after every gate passes and no
  demonstrated Blocker remains.

The AI then reports the merged outcome, verification, and any Follow-ups. The
task user is not asked to confirm each intermediate action.

Any later unambiguous same-task Codex `userMessage` to stop, cancel, withdraw
approval, or not merge ends the authority immediately. No exact cancellation
sentence is required. Anything reasonably read as stop-like and not clearly
about something else pauses execution; the AI asks rather than continuing.

Authority also expires if the live card is superseded, the implementation PR
closes unmerged, or the task surface can no longer preserve the required role,
reference, and ordering evidence. Context compaction alone does not expire
authority when the original card and approval items remain directly
retrievable and recheckable. A summary or paraphrase without those original
items is insufficient and expires authority. Resumption after cancellation or
expiry requires a new decision version and approval.

Before merge, the AI mechanically compares every changed path from the reviewed
base through the exact PR head with the technical contract's exact path
allowlist, and verifies that allowlist is a subset of the card's maximum path
envelope. Any outside path or subset failure stops execution. The AI posts one
compact PR scope report naming the decision, card, and PR references, the
changed paths, both allowlist results, its explicit determination that every
semantic change preserves the approved envelope, the verification and review
result, and the cancellation check. This is reviewable AI-attested evidence,
not authority, and requires no task-user confirmation.

Immediately before merge, the AI must confirm that the approval is still bound
to that PR, the task contains no later cancellation, the card remains live,
the scope report describes the exact head, and all review and verification
gates pass.

## 7. Changes that do not require another approval

No new task-user approval is required for:

- meaning-preserving wording, documentation, implementation, or refactoring
  inside the approved envelope and paths;
- focused tests and Blocker fixes that preserve every invariant;
- mechanically derived bytes, hashes, manifests, snapshots, or test inventory;
- PR metadata, review handling, check reruns, and semantics-preserving rebases
  or conflict resolution; or
- the compact approval and merge evidence this workflow requires.

Technical reviewers and CI own verification of these facts. The task user does
not become the verifier by approving the decision.

## 8. Changes that require a new approval

Execution stops and a new card/version is required when any proposed change:

- changes the trust boundary, authority map, effect, non-effect, or invariant;
- expands the path allowlist into another authority or custody surface;
- adds unstated irreversible behavior, database or durability change, runtime
  activation, current/default or deployment effect, or high-consequence output;
- transfers or reuses approval for another PR;
- waives a Blocker or requires unapproved production credentials, data,
  secrets, infrastructure, or external coordination; or
- makes envelope preservation genuinely ambiguous.

A reviewer comment, failing check, or implementation surprise does not itself
require human approval. Only the material boundary change needed to address it
does.

## 9. State machine and review loop

```text
PHASE_A_DRAFT_PR_IDENTIFIED
  -> AI_REVIEW_AND_COMPLETE_CARD_NAMING_THAT_PR
COMPLETE_LIVE_CARD_NAMES_THAT_PR
  -> LATER_EXACT_USER_MESSAGE_IN_SAME_TASK
APPROVAL_BOUND_TO_CARD_AND_NAMED_PR
  -> AI_BEGIN_APPROVED_WORK_IN_NAMED_PR
IMPLEMENTING
  -> AI_IMPLEMENT_AND_VERIFY
REVIEWING
  -> IN_BOUNDARY_BLOCKER_FIX -> REVIEWING
  -> ALL_GATES_PASS_AND_NO_BLOCKER
MERGE_READY
  -> FINAL_APPROVAL_VALIDITY_AND_GATE_CHECK -> MERGED

Any material envelope change -> STOPPED_FOR_NEW_DECISION
Any cross-boundary requirement -> STOPPED_FOR_SEPARATE_BOUNDARY
Any later user stop/cancel/withdraw instruction -> USER_CANCELLED
Card superseded, task evidence lost, or PR closed unmerged -> AUTHORITY_EXPIRED
```

Drafting, inspection, review, and evidence collection may happen before human
approval. For a high-risk boundary, implementation that changes repository
behavior begins only after approval.

Review follows `AGENTS.md`: one unconstrained full review at an exact head,
then review of fixes and affected invariants. Only demonstrated Blockers delay
merge. Follow-ups and Preferences do not create user-confirmation gates.

No separate publication-byte review or direct private-task provenance review
is required for this provisional pre-deployment workflow. The repository
approval record is AI-attested evidence of the user message. This is a
deliberate pre-deployment tradeoff, not a production-grade signing claim.

## 10. Authority map

- The later same-task Codex `userMessage` owns the provisional approve-or-refuse
  decision. This contract claims only that platform-visible role and does not
  claim independent proof of the author's real-world identity.
- The live card owns the maximum user-approved effects, non-effects, primary
  trust boundary, authority map, decision-level invariants, maximum path
  envelope, and named implementation PR.
- The approved Phase A technical contract owns detailed architecture, detailed
  invariants, and the exact implementation path allowlist. It may only narrow
  or refine the live card. Its exact allowlist is merge-time path authority and
  must remain a subset of the card envelope.
- The AI owns drafting, implementation, evidence preparation, review handling,
  and merge only within the approved envelope.
- Reviewers own Blocker findings and CI owns mechanical checks; neither owns
  user approval or scope expansion.
- Repository `main` preserves the result, but records, checks, credentials,
  reviews, and merge do not create decision authority.
- Existing domain, temporal, database, RuntimeBundle, output, deployment,
  legacy, and #192 authorities retain their existing ownership.
- Before deployment, an independently human-controlled and independently
  verifiable signing or approval system must replace Codex task attestation.

## 11. Invariants

- **PDW-001 — Understandable decision.** The task user is asked to approve
  effects, risks, and boundaries, never to verify technical evidence.
- **PDW-002 — One platform-bounded card.** Only the exact later same-task
  `userMessage` approves the unique live card; no stronger identity claim or
  unstated effect follows.
- **PDW-003 — One approval, one PR.** Approval is bound once and covers only the
  already-created draft PR named by the live card; it cannot be assigned after
  approval, transferred, or replayed.
- **PDW-004 — Material or path expansion stops.** A semantic envelope change
  requires a new version and approval; the technical allowlist must be a subset
  of the card envelope, and any path outside that exact allowlist stops.
- **PDW-005 — Cancellation is easier than approval.** A stop-like message
  pauses immediately, and lost original task evidence expires authority.
- **PDW-006 — Deterministic merge gate.** The exact reviewed head, path check,
  required checks, no demonstrated Blocker, and current approval must all pass;
  Blockers are fixed rather than waived.
- **PDW-007 — Evidence is not authority.** AI, CI, GitHub activity, credentials,
  records, reviews, and merge never substitute for the task-user decision.
- **PDW-008 — Stronger explicit contract wins.** The workflow cannot bypass an
  accepted stronger rule or authorize deployment, production, current/default
  promotion, release approval, or a high-consequence security waiver.
- **PDW-009 — Production replacement.** Independently human-controlled and
  independently verifiable approval or signing is mandatory before deployment.
- **PDW-010 — Domain separation.** ADR 0002, temporal decision currentness,
  production/legacy separation, outputs, and #192 are unchanged.
- **PDW-011 — Closed provisional trust.** The workflow relies only on the
  explicitly trusted pre-deployment facilities in section 3.1 and makes no
  independent identity, anti-compromise, or production-signing claim.

## 12. Required negative cases

The workflow fails closed when:

- the card is incomplete, two cards remain live, or semantic wording changes
  without a version increment;
- approval is generic, wrapped, from another task, or not an exact later
  same-task Codex `userMessage`;
- a card names no existing draft PR, a PR is first assigned after approval, or
  approval is transferred or reused for another PR, version, trust boundary,
  or effect;
- a stop-like message is ignored, or only compacted summary evidence remains;
- the technical path allowlist exceeds the card envelope, any changed path is
  outside the technical allowlist, or a review fix changes the envelope while
  being described as mechanical;
- the Phase A technical contract widens, relaxes, or contradicts the card, or
  their authority relationship is ambiguous;
- a Blocker is waived, a Preference blocks merge, a check fails, or the head
  changes without affected checks and review being repeated;
- the task user is asked to verify hashes, bytes, inventories, or review
  mechanics; or
- a stronger contract is ignored or the workflow is used to claim deployment,
  production, current/default, runtime, legacy, or #192 authority.

## 13. Compact approval evidence

After approval, the AI records only:

- decision identity and version;
- Codex task, live-card, and user-message stable references;
- the exact simple approval sentence;
- the AI-observed user role and ordering;
- the one implementation PR's stable reference; and
- a statement that the evidence is provisional and AI-attested.

The record may be an appendix to the governing Phase A contract. It travels
with the same trust-boundary PR and requires no separate publication PR,
currentness trace, or private-task provenance re-review.

GitHub PR and merge metadata preserve the exact final head and resulting merge
commit. The AI reports them after merge. Neither is back-written into the
approval record, and neither creates a post-merge confirmation or record PR.

The record is evidence of the user decision, not authority by itself. It never
becomes a domain lifecycle record, runtime input, deployment authorization, or
current/default decision.

This AI-attested appendix is a deliberate provisional exception to
`TASK_PROMPT.md`'s preference against self-attestation. The exception is
bounded because the original task message remains the decision, the appendix
only reports platform-visible evidence, and no independent pre-deployment
signer exists. Treating the appendix itself as authority is forbidden, and the
exception ends before deployment.

## 14. Non-goals

This contract does not:

- approve, implement, or activate itself;
- change an existing temporal decision-log entry or lifecycle state;
- amend ADR 0002 or any accepted temporal, database, RuntimeBundle, command,
  route, read, output, deployment, legacy, or #192 contract;
- create an approval service, database, signer, key, bot, webhook, GitHub App,
  or runtime component;
- eliminate review, CI, conformance, invariant traceability, or boundary
  separation;
- permit deployment, current/default promotion, production claims, security
  waivers, production data access, or secret use;
- make AI or repository credentials the task-user decision authority; or
- retroactively validate, replace, or reinterpret completed approvals.

## 15. Smallest coherent implementation boundary

The Phase A review head changes only this RFC and stops for plain-English
review.

Adoption is governed by the current, pre-workflow rules at these reviewed
inputs:

- reviewed base commit:
  `c59a03727fb3346b51fc639622abad28a1ba052c`;
- `AGENTS.md` Git blob:
  `581c6bb56dcfeb5d568ef7bc3e253e2486f30938`; and
- `TASK_PROMPT.md` Git blob:
  `84682633cd440f0619898bbadc44faed2c31e0da`.

The one already-created draft implementation PR for this bootstrap decision is
`https://github.com/samovers/OFARM2/pull/285`. The version `2` live card must
name that exact stable PR reference. Approval cannot be assigned later or
consumed by another PR.

After version `2` approval, Phase B may continue only in that PR and make these
closed insertions:

1. In this RFC, change only the status from proposed/inactive to approved and
   append one compact approval-evidence appendix described by section 13.
2. In `AGENTS.md`, add one new top-level workflow section immediately before
   the existing heading `## Review guard - Core neutrality`. That section may
   state only: when this workflow applies; the required live-card fields and
   exact approval form; prior naming and one-time binding of the draft PR;
   standing in-envelope implementation/review/merge authority; cancellation,
   expiry, and material-change stops; technical-allowlist and scope-report
   gates; stronger-contract precedence; and the pre-deployment limit and
   replacement duty. Do not remove, replace, or semantically change any
   existing text.
3. In `TASK_PROMPT.md`:
   - add one Phase A decision-card subsection immediately after the existing
     sentence `Stop after Phase A and wait for explicit approval.` and before
     `## Phase B: implementation`. It may state only the card contents, the
     existing named-draft-PR requirement, the exact approval form, stable task
     evidence, and the requirement to wait; and
   - add one standing-authority subsection immediately after the existing
     sentence `Only begin after the complete design contract is approved.`
     under Phase B. It may state only the in-envelope actions, compact approval
     record, exact-allowlist and scope-report checks, review and merge gates,
     cancellation and expiry, material-change stops, stronger-contract
     precedence, and the no-deployment limit.
   Do not remove, replace, or semantically change any existing text.

No other file or text change is permitted. The inserted rules must preserve
all existing trust-boundary separation, review, conformance, Blocker, and
deployment restrictions. They may implement only the workflow defined by this
RFC and may not silently alter its decision envelope.

Before merge, the AI must display the exact resulting diff to `AGENTS.md` and
`TASK_PROMPT.md` in the same Codex task. This is a one-time bootstrap
transparency requirement because the new text will govern future agents. It is
not a second approval sentence or confirmation gate; any later stop-like task
user message still cancels under section 6.

The reviewed base may advance only when the exact `AGENTS.md` and
`TASK_PROMPT.md` blobs above remain unchanged and no conflict touches either
file. Any upstream change to either blob, any merge conflict in either file,
or any need to alter an existing rule stops this adoption for exact-head
review and a new decision version. The ordinary semantics-preserving rebase or
conflict-resolution authority in sections 6 and 7 does not apply to these two
bootstrap files.

No checker, schema, service, runtime component, temporal artifact, or active
registry is required. If implementation demonstrates that executable workflow
enforcement is necessary, work stops and proposes that separate boundary.

## 16. Provisional design record

This workflow is acceptable before deployment because repository work does not
deploy or promote current/default state, one same-task user decision bounds
each material trust boundary, AI and CI own mechanical evidence, and merge
still requires review and conformance.

Evidence requiring redesign includes misattributed Codex user roles, an
envelope-changing patch merged without a new decision, inability to keep PRs
inside one trust boundary, or any attempt to use the workflow for deployment.

The required upgrade path is an independently human-controlled approval or
signing system that signs the decision envelope, exposes verification to
reviewers, and preserves the same material-change and authority-separation
rules.

## 17. Verification and review disposition

Review must verify:

- the closed trust model and its explicit excluded compromises;
- the understandable live card, exact same-task approval, named-draft-PR
  binding, cancellation, and compaction failure behavior;
- the card/technical-contract refinement law and both path-allowlist checks;
- that mechanical work cannot change a decision-bearing field or relax a
  technical invariant;
- exact-head review, scope reporting, required checks, and Blocker disposition;
- stronger-contract, domain-separation, and pre-deployment limits; and
- the pinned bootstrap inputs, exact insertion points, exact-diff display,
  rebase stop, three-file Phase B boundary, negative cases, and package
  conformance.

Current review disposition:

- Blockers: the prior exact-head review identified four; this revision is
  intended to close them and requires exact-head re-review before a live card;
- Follow-ups: independent signing or approval before deployment;
- Preferences: none; and
- open decisions: none.

## 18. Stop conditions

This Phase A stops before:

1. presenting a live approval card for this workflow;
2. soliciting its simple approval sentence;
3. changing `AGENTS.md` or `TASK_PROMPT.md`;
4. treating the workflow as active;
5. starting architecture snapshot B1;
6. changing any temporal, database, runtime, route, command, read, output,
   deployment, legacy, or #192 behavior; or
7. creating or changing any production authority.

The next lawful action is exact-head plain-English review of this proposed
contract. If the reviewed design is accepted, the AI may then show one short
live card for `PREDEPLOYMENT-WORKFLOW-001` version `2`, naming
`https://github.com/samovers/OFARM2/pull/285`, and request only:

```text
I approve OFARM2 decision PREDEPLOYMENT-WORKFLOW-001 version 2.
```

## Appendix A — Compact architect-approval evidence

- **Decision:** `PREDEPLOYMENT-WORKFLOW-001`, version `2`.
- **Codex task:** `019fa821-93c9-7ef1-8c94-1c0e92ea46b9`.
- **Complete live card:** stable reference `item-2363` in that task.
- **Architect approval:** stable reference `item-2364`, observed as a later
  task-user message in the same task.
- **Exact approval sentence:** `I approve OFARM2 decision PREDEPLOYMENT-WORKFLOW-001 version 2.`
- **Implementation PR:** `https://github.com/samovers/OFARM2/pull/285`.
- **Evidence posture:** these task references and role/order observations are
  provisional AI-attested evidence of the architect's decision. This appendix
  is not approval authority, deployment authority, or an independently
  verifiable identity claim.
