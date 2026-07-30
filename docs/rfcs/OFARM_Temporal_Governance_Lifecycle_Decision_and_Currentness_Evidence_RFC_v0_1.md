# OFARM Temporal Lifecycle Approval Workflow — Phase A Contract v0.1

**Status:** draft for plain English review; no implementation or promotion

**Contract identity:**
`ofarm.temporal-lifecycle-approval-workflow.issue176-foundation.v0.1`

**Primary ticket:** #176

**Primary trust boundary:** provisional capture of the architect's exact
approval intent in one Codex task

**Promotion-contract dependency:**
`ofarm.temporal-governance-promotion.issue176-foundation.v0.1`,
`sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0`

**PR boundary:** this RFC only

## Decision

Before any temporal lifecycle decision record may be prepared, the AI must
show the designated architect one complete plain English decision card in the
same Codex task.

The architect must then send the exact approval sentence as a user-authored
message in that same task. Only that later message authorizes the AI to prepare
one matching technical decision record.

The technical record is evidence of the architect's decision. It does not
replace the user-authored decision and cannot create authority by itself.

An AI-authored message, copied approval from another card or task, generic
approval, pull-request approval, merge, GitHub review, comment, reaction,
repository credential, commit, check, tag, or release never counts as
architect approval.

Approval authorizes preparation of one exact technical decision record only.
It does not itself promote an identity. Effective lifecycle recognition still
requires the separately governed decision record and matching currentness
trace required by the promotion contract.

This is a provisional pre-deployment workflow. Before any deployment, it must
be replaced by an independently human-controlled signing or approval system.
The Codex task workflow must never become a production control.

## Provisional trust model

Version 0.1 uses the existing Codex task as the provisional approval channel.
No new service is introduced.

- The AI prepares and displays the decision card. It has no approval
  authority.
- The designated architect is the human user participating in that task.
- Only a message whose task role is `user` can carry approval.
- The approval message must follow the exact card in the same task.
- The approval message must contain only the exact approval sentence.
- Codex task and message metadata provide the provisional task, author-role,
  message-order, and stable-reference evidence.
- Repository ownership, GitHub credentials, commits, comments, reviews,
  reactions, and merges provide no architect-approval evidence.
- A future decision record must snapshot the task and user-message evidence.
- A future currentness trace must bind the exact authorized decision record.

The workflow assumes only that the task surface distinguishes user-authored
messages from assistant, tool, automation, and repository actions. It does not
treat the AI's access to the user's repository credentials as access to the
user-message role.

If the task surface cannot provide a stable task identifier and stable
user-message identifier or reference, record preparation must stop.

## Fixed decision-card payload

The card represents exactly one fixed payload with:

- card payload version
  `ofarm.temporal-lifecycle-decision-card.v0.1`;
- workflow contract identity
  `ofarm.temporal-lifecycle-approval-workflow.issue176-foundation.v0.1`;
- the exact promotion-contract identity and repository-file digest above;
- outcome `PROMOTE_GOVERNED_INACTIVE`;
- the exact ordered three-subject set below;
- decision effect
  `ALL_THREE_EXACT_SUBJECTS_TARGET_GOVERNED_INACTIVE`;
- approval effect
  `AUTHORIZE_ONE_MATCHING_TECHNICAL_DECISION_RECORD_ONLY`;
- effective-lifecycle prerequisite
  `MATCHING_CURRENTNESS_TRACE_REQUIRED`; and
- the closed non-effects listed in the card.

The payload uses `OFARM_CANONICAL_JSON_V1`. Its canonical byte length and
digest are:

```text
1893
sha256:aa9d5b5fc8aa39745e5ffbd2b8b05e9edda59ab46df98ca61e2a91e02434b819
```

The exact digest input is:

```json
{
  "cardPayloadVersion": "ofarm.temporal-lifecycle-decision-card.v0.1",
  "workflowContractIdentity": "ofarm.temporal-lifecycle-approval-workflow.issue176-foundation.v0.1",
  "promotionContractIdentity": "ofarm.temporal-governance-promotion.issue176-foundation.v0.1",
  "promotionContractRepositoryFileDigest": "sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0",
  "outcome": "PROMOTE_GOVERNED_INACTIVE",
  "subjects": [
    {
      "identity": "ofarm.temporal-carrier-matrix.adr0002.v0.1",
      "repositoryFileDigest": "sha256:7cb26513b5abdbcadecaf6f9b47d874a742ba8fa05a332c9130deebe449d7fc6",
      "canonicalization": "OFARM_CANONICAL_JSON_V1",
      "canonicalByteLength": 9504,
      "canonicalContentDigest": "sha256:c404c0cd1e08f389664b5381c2c038cf65bac9a3b725fc2b1882990636eb179b"
    },
    {
      "identity": "ofarm.temporal-carrier-selection.intervention.v0.1",
      "repositoryFileDigest": "sha256:9886aace0670b6a83f17cd33cbc67aa62fafcfd0ea873faed9194c2aaa07efe5",
      "canonicalization": "OFARM_CANONICAL_JSON_V1",
      "canonicalByteLength": 1814,
      "canonicalContentDigest": "sha256:373a5f402ad077039946c1dfe7b972e4382d3c6a6805fbf0b271e4a0bc729bf1"
    },
    {
      "identity": "ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1",
      "repositoryFileDigest": "sha256:0909ec653cb99a94cd1b35afaf2d386258aac671c5f730960ed485df8a4b8f2e",
      "canonicalization": "OFARM_CANONICAL_JSON_V1",
      "canonicalByteLength": 9614,
      "canonicalContentDigest": "sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1"
    }
  ],
  "decisionEffect": "ALL_THREE_EXACT_SUBJECTS_TARGET_GOVERNED_INACTIVE",
  "approvalEffect": "AUTHORIZE_ONE_MATCHING_TECHNICAL_DECISION_RECORD_ONLY",
  "effectiveLifecyclePrerequisite": "MATCHING_CURRENTNESS_TRACE_REQUIRED",
  "nonEffects": [
    "CURRENT_DEFAULT_STATUS",
    "RUNTIME_ACTIVATION",
    "RUNTIME_BUNDLE_ADMISSION",
    "PROFILE_CHANGE",
    "ROUTE_OR_COMMAND_INTEGRATION",
    "DATABASE_WORK",
    "READ_OR_OUTPUT_BEHAVIOR",
    "DEPLOYMENT_OR_PRODUCTION_CLAIM",
    "LEGACY_BEHAVIOR",
    "ISSUE_192_BEHAVIOR"
  ]
}
```

The digest excludes task and message identifiers. Those identify the approval
context and evidence; they do not change the decision being approved.

Any change to a payload field, subject, digest, effect, or non-effect creates a
different card and requires a new contract version, new digest, new displayed
card, and new user-authored approval.

## Exact decision card

The AI must show this complete card in the Codex task:

```text
TEMPORAL LIFECYCLE DECISION CARD

Decision:
Promote exactly three reviewed temporal-governance identities from
CANDIDATE_INACTIVE to GOVERNED_INACTIVE.

Applies only to:
1. ofarm.temporal-carrier-matrix.adr0002.v0.1
2. ofarm.temporal-carrier-selection.intervention.v0.1
3. ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1

Authority:
ofarm.temporal-governance-promotion.issue176-foundation.v0.1
sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0

Card digest:
sha256:aa9d5b5fc8aa39745e5ffbd2b8b05e9edda59ab46df98ca61e2a91e02434b819

What approval authorizes:
Preparation of one technical decision record with outcome
PROMOTE_GOVERNED_INACTIVE for exactly the three digest-pinned subjects.

What approval does not authorize:
No promotion by the message alone, current/default status, runtime activation,
RuntimeBundle admission, profile change, route, command integration, database
work, read, output, deployment, production claim, legacy behavior, or issue
#192 behavior.

Approval channel:
One later user-authored message in this same Codex task.

Exact approval sentence:
I explicitly approve decision card
sha256:aa9d5b5fc8aa39745e5ffbd2b8b05e9edda59ab46df98ca61e2a91e02434b819
under ofarm.temporal-governance-promotion.issue176-foundation.v0.1 at
sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0
for exactly its three digest-pinned subjects, authorizing one technical
decision record for PROMOTE_GOVERNED_INACTIVE with no activation or
current/default effect.
```

Line wrapping is presentation only. The exact approval text is this single
sentence:

```text
I explicitly approve decision card sha256:aa9d5b5fc8aa39745e5ffbd2b8b05e9edda59ab46df98ca61e2a91e02434b819 under ofarm.temporal-governance-promotion.issue176-foundation.v0.1 at sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0 for exactly its three digest-pinned subjects, authorizing one technical decision record for PROMOTE_GOVERNED_INACTIVE with no activation or current/default effect.
```

Leading or trailing whitespace may be removed before comparison and
digesting. No other normalization, abbreviation, Markdown markup, quotation,
prefix, suffix, or substituted wording is allowed.

The SHA-256 digest of the exact UTF-8 approval sentence, with no leading
whitespace, trailing whitespace, or newline, is:

```text
sha256:ed89c58b9b3c75e3f417982ffbece0f44667e8d8a53351f2dfb893febc20897f
```

This contract displays the sentence for review. It is not a live card and
must not be treated as an approval request.

## Exact three-subject set

The card's phrase "three digest-pinned subjects" means exactly:

1. `ofarm.temporal-carrier-matrix.adr0002.v0.1`
   - repository-file digest:
     `sha256:7cb26513b5abdbcadecaf6f9b47d874a742ba8fa05a332c9130deebe449d7fc6`
   - canonical byte length: `9504`
   - canonical content digest:
     `sha256:c404c0cd1e08f389664b5381c2c038cf65bac9a3b725fc2b1882990636eb179b`
2. `ofarm.temporal-carrier-selection.intervention.v0.1`
   - repository-file digest:
     `sha256:9886aace0670b6a83f17cd33cbc67aa62fafcfd0ea873faed9194c2aaa07efe5`
   - canonical byte length: `1814`
   - canonical content digest:
     `sha256:373a5f402ad077039946c1dfe7b972e4382d3c6a6805fbf0b271e4a0bc729bf1`
3. `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1`
   - repository-file digest:
     `sha256:0909ec653cb99a94cd1b35afaf2d386258aac671c5f730960ed485df8a4b8f2e`
   - canonical byte length: `9614`
   - canonical content digest:
     `sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1`

All three use `OFARM_CANONICAL_JSON_V1`.

## Closed workflow

The provisional workflow is:

```text
DRAFT_CARD
  -> AI_SHOWS_EXACT_CARD_IN_TASK
SHOWN_UNAPPROVED
  -> LATER_EXACT_USER_MESSAGE_IN_SAME_TASK
RECORD_PREPARATION_AUTHORIZED
  -> future separately approved technical-record implementation
```

Rules:

1. The AI validates the card against this contract before showing it.
2. The AI shows the whole card and exact approval sentence together.
3. Approval must be a later message in the same task.
4. The message must be authored with task role `user`.
5. The message must contain only the exact approval sentence.
6. Exact approval authorizes preparation of one matching record only.
7. Any card change returns the workflow to `DRAFT_CARD`.
8. A message from another task, before the card, or for another digest is
   invalid.
9. An assistant, tool, automation, delegated agent, or repository action
   cannot author the approval.
10. The future record must preserve every required evidence field below.
11. A separate matching currentness trace remains mandatory before effective
    lifecycle recognition.

No merge, GitHub action, repository credential, commit, timestamp, branch,
tag, latest-file rule, environment value, or caller field advances this state
machine.

## Future technical decision-record evidence

After exact approval, a future separately approved implementation may prepare
one technical decision record. That record must preserve:

```text
workflowContractIdentity
cardPayloadVersion
cardDigest
promotionContractIdentity
promotionContractRepositoryFileDigest
outcome
subjects
codexTaskId
approvalUserMessageIdOrStableRef
approvalMessageRole
approvalSentence
approvalSentenceDigest
approvalMessageOrder
```

The required values are:

- `cardDigest` is the exact digest shown above;
- `outcome` is `PROMOTE_GOVERNED_INACTIVE`;
- `subjects` repeats the exact ordered identity and digest set;
- `codexTaskId` identifies the task where the card and approval appeared;
- `approvalUserMessageIdOrStableRef` identifies the later user message;
- `approvalMessageRole` is exactly `user`;
- `approvalSentence` is the exact sentence above;
- `approvalSentenceDigest` is the exact digest above; and
- `approvalMessageOrder` proves the user message followed the card.

The record must not accept these fields from repository state, a request,
environment, profile, caller, or AI assertion. They are copied from the task
evidence and fixed contract.

The record is a technical preservation of the architect's decision. Its
existence, commit, review, or merge cannot cure missing or invalid user
approval and cannot substitute for the user-authored message.

## Currentness remains separate

The approval message and technical decision record do not establish an
effective lifecycle head.

A separate matching currentness trace remains mandatory. It must bind the
exact authorized decision record under a separately approved contract. No
technical record, approval message, merge, or latest-file inference may stand
in for that trace.

## Authority map

- The merged promotion contract owns the exact subjects, digests, atomicity,
  allowed outcomes, and meaning of `GOVERNED_INACTIVE`.
- This workflow contract owns the card, digest, exact sentence, same-task
  ordering, and record-preparation authorization rule.
- The AI owns preparation and exactness checks only. It has no authority to
  approve or infer approval.
- The designated architect owns the user-authored decision message.
- The Codex task surface provisionally owns user-role attribution, task and
  message identity, and ordering evidence.
- GitHub credentials and repository actions own no approval authority.
- The future technical record preserves evidence but does not create or
  replace the architect's authority.
- The future currentness trace separately owns effective lifecycle-head
  evidence.
- Candidate artifacts retain ownership of their reviewed bytes and inactive
  execution postures.
- RuntimeBundle, profile, database, runtime, route, command, read, output,
  deployment, legacy, and #192 authorities remain unchanged.

## Invariants

- **TLAW-001 — AI is not authority.** AI output can present a decision but
  cannot approve or authorize it.
- **TLAW-002 — Same-task card first.** The complete card precedes approval in
  the same Codex task.
- **TLAW-003 — User role only.** Only a later user-authored task message can
  carry architect approval.
- **TLAW-004 — Exact human text.** The message contains only the exact
  sentence bound to the card digest.
- **TLAW-005 — Exact subjects.** Authorization covers all three digest-pinned
  subjects atomically and no other identity.
- **TLAW-006 — Exact outcome.** The only authorized positive outcome is
  `PROMOTE_GOVERNED_INACTIVE`.
- **TLAW-007 — One authorization.** One exact approval authorizes preparation
  of one matching technical record only.
- **TLAW-008 — Mutation invalidates.** Any card, subject, digest, outcome,
  authority, or non-effect change requires a new card and approval.
- **TLAW-009 — Repository credentials are not human authority.** GitHub
  credentials, comments, reviews, reactions, commits, and merges never approve.
- **TLAW-010 — Record is evidence only.** The technical record preserves but
  never substitutes for the architect's user-authored decision.
- **TLAW-011 — Approval is not promotion.** Effective state still requires
  the valid decision record and separate currentness trace.
- **TLAW-012 — No activation.** Neither approval nor a later
  `GOVERNED_INACTIVE` record grants active or production authority.
- **TLAW-013 — Provisional only.** This workflow is forbidden for deployment
  and must be replaced by independently human-controlled approval or signing.
- **TLAW-014 — Production firewall.** No production or legacy runtime
  consumes this approval workflow.
- **TLAW-015 — Audit separation.** The workflow adds no #192 behavior.

## Required negative cases

Record preparation remains unauthorized when:

- the AI omits or changes part of the card;
- the card digest does not match the fixed payload;
- the user message appears before the exact card;
- the user message is in another task;
- the task or message stable reference is missing;
- the message role is not `user`;
- the text is generic, copied from another card or task, abbreviated, quoted,
  wrapped in Markdown, prefixed, suffixed, or otherwise changed;
- the assistant, a tool, automation, delegated agent, bot, repository action,
  reviewer, merge actor, or GitHub account emits the text;
- a pull request is approved or merged without the user-authored task message;
- repository credentials are treated as evidence of human intent;
- the card changes after approval;
- one approval is reused for another record, contract version, subject set, or
  outcome;
- the record omits or changes task, message, sentence, card, contract, or
  subject evidence;
- the record is treated as the architect's decision rather than evidence of
  it;
- approval or the record is treated as a currentness trace; or
- the provisional workflow is proposed for deployment or production.

## Non-goals

This contract does not:

- show a live decision card or solicit approval;
- create a decision-card artifact, schema, decision record, or currentness
  trace;
- post, approve, sign, store, extract, or promote anything;
- add a service, database, migration, role, key, signature, webhook, bot, or
  runtime approval component;
- change Codex or GitHub authentication, permissions, settings, or task
  behavior;
- edit a candidate, manifest, frozen contract, active registry, RuntimeBundle,
  profile, ActiveArtifactSet, or Capability Manifest;
- activate a selector or command;
- add a route, materialization, current-state read, historical view, WINDOW
  behavior, qualification, output, receipt, or deployment behavior;
- import or change the legacy semantic or output surface; or
- implement or change issue #192.

## Smallest coherent Phase A change

The Phase A PR contains this RFC only. It establishes a reviewable provisional
approval protocol without implementing or executing it.

## Verification

Review must prove:

- the card agrees exactly with the merged promotion contract;
- the card digest recomputes from the fixed payload;
- all three subject identities and digests are present;
- the exact sentence binds the card, promotion contract, outcome, atomic
  subject set, record-only authorization, and non-activation posture;
- only a later user-authored message in the same task can authorize record
  preparation;
- AI messages, copied generic approval, PR state, GitHub activity, repository
  credentials, checks, timestamps, and merges have no approval authority;
- the technical record preserves the decision evidence without replacing it;
- currentness remains separate and mandatory;
- deployment requires replacement by independent human control;
- every negative case fails closed;
- the PR changes only this RFC; and
- package conformance and documentation hygiene remain clean.

## Stop conditions

After this contract is approved, work still stops before:

1. showing a live decision card or soliciting the exact sentence;
2. defining or implementing a technical decision-record schema;
3. defining or implementing a currentness-trace schema;
4. preparing or creating either record;
5. changing a manifest or effective lifecycle state;
6. activating a RuntimeBundle role, profile, selector, command, or route;
7. adding a service, database, read, historical, WINDOW, output, deployment,
   legacy, or #192 behavior; or
8. using this provisional workflow in any deployed environment.

The next boundary may draft the inactive technical decision-record carrier.
The currentness-trace carrier remains a separate following boundary. Neither
may request live approval or create a record until its own contract is
separately approved.
