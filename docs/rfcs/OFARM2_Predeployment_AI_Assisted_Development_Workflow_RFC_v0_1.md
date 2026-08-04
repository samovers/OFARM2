# OFARM2 Pre-Deployment AI-Assisted Development Workflow — Phase A Contract v0.1

**Status:** proposed and inactive; documentation-only; no workflow authority
until approved and implemented; no deployment or production effect

**Contract identity:**
`ofarm2.predeployment-ai-assisted-development-workflow.v0.1`

**Decision identity:** `PREDEPLOYMENT-WORKFLOW-001`, version `1`

**Motivating implementation programme:** #176

**Prior workflow evidence:** #218

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
or runtime outcome created by this RFC. Prior workflow evidence is recorded in
#218. This contract does not amend OFARM law, ADR 0002, an artifact lifecycle,
tenant knowledge order, runtime truth, or production governance.

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

## 4. Decision envelope

Every live decision card binds one prose-only decision envelope containing
exactly the following decision-bearing fields:

| Field | Meaning |
|---|---|
| `decisionId` and `version` | Stable identity of the task-user decision. |
| `problem` | The one problem being solved. |
| `recommendedDecision` | The outcome the AI recommends. |
| `primaryTrustBoundary` | The one authority or custody boundary changed. |
| `primaryRiskAndBound` | The main risk and the rule that contains it. |
| `permittedEffects` | Closed effects the approved work may create. |
| `nonEffects` | Closed effects it must not create. |
| `invariants` | Stable, falsifiable conditions that must remain true. |
| `implementationBoundary` | Closed repository path or path-prefix allowlist. |
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

## 5. Plain-English decision card and approval

Before requesting approval, the AI must show one complete card containing:

1. the identity, version, problem, and recommended decision;
2. the trust boundary, permitted effects, non-effects, and primary risk;
3. the invariants, path allowlist, and verification gates;
4. the reapproval triggers and provisional replacement posture;
5. that the AI may merge the one implementation PR after gates pass; and
6. the exact approval sentence.

Technical evidence may be linked below the card for reviewers, but it must not
be presented as something the task user must understand or confirm.

Only one card is live for an identity and version; a replacement withdraws its
predecessor. A semantic field change increments the version. Meaning-preserving
spelling, formatting, or wording corrections and unchanged redisplay may retain
it, but only the newest stable card-item reference remains live. An approved
card cannot be semantically changed under the same version.

Before soliciting approval, the AI must verify that the task surface assigned
the live card a directly retrievable stable item reference. If it cannot, the
workflow stops. The task user does not inspect or approve that reference.

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

## 6. Standing authority after approval

One valid approval may be assigned once to one implementation PR for that
decision. The first PR recorded against the approval consumes that assignment;
the approval cannot be transferred to or reused for another PR. Within that
one PR, it explicitly authorizes the AI, without additional user confirmation,
to:

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
base through the exact PR head with the card's implementation allowlist. Any
outside path stops execution. The AI posts one compact PR scope report naming
the decision and card reference, the changed paths, the allowlist result, the
verification and review result, and the cancellation check. This is reviewable
AI-attested evidence, not authority, and requires no task-user confirmation.

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
DRAFT
  -> AI_REVIEW_AND_COMPLETE_CARD
AWAITING_HUMAN_DECISION
  -> LATER_EXACT_USER_MESSAGE_IN_SAME_TASK
APPROVED
  -> BIND_ONCE_TO_ONE_IMPLEMENTATION_PR
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
- The live card owns the decision envelope; the approved Phase A contract owns
  its technical invariants, architecture, and path allowlist.
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
- **PDW-003 — One approval, one PR.** Approval is assigned once and covers only
  envelope-preserving work in that PR through merge.
- **PDW-004 — Material or path expansion stops.** A semantic envelope change
  requires a new version and approval; any path outside the allowlist stops.
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

## 12. Required negative cases

The workflow fails closed when:

- the card is incomplete, two cards remain live, or semantic wording changes
  without a version increment;
- approval is generic, wrapped, from another task, or not an exact later
  same-task Codex `userMessage`;
- approval is reused for another PR, version, trust boundary, or effect;
- a stop-like message is ignored, or only compacted summary evidence remains;
- any changed path is outside the allowlist, or a review fix changes the
  envelope while being described as mechanical;
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

After approval, Phase B may continue in the same PR and change only:

- this RFC, to mark the contract approved and append its compact approval
  evidence;
- `AGENTS.md`, to make the workflow operative for repository agents; and
- `TASK_PROMPT.md`, to add the simple decision card, standing-authority rule,
  material-change triggers, and automatic review/merge loop.

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

- the understandable live card, exact same-task approval, and one-PR binding;
- path-allowlist enforcement, cancellation, and compaction failure behavior;
- that mechanical work cannot change a decision-bearing field;
- exact-head review, scope reporting, required checks, and Blocker disposition;
- stronger-contract, domain-separation, and pre-deployment limits; and
- the three-file Phase B boundary, negative cases, and package conformance.

Current review disposition:

- Blockers: none known;
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

The next lawful action is plain-English review of this proposed contract. If
the reviewed design is accepted, the AI may then show one short live card for
`PREDEPLOYMENT-WORKFLOW-001` version `1` and request only:

```text
I approve OFARM2 decision PREDEPLOYMENT-WORKFLOW-001 version 1.
```
