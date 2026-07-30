# OFARM Temporal Lifecycle Approval Workflow — Phase A Contract v0.1

**Status:** draft for plain English review; no implementation or promotion

**Contract identity:**
`ofarm.temporal-lifecycle-approval-workflow.issue176-foundation.v0.1`

**Primary ticket:** #176

**Primary trust boundary:** capture of the architect's exact approval intent
for one immutable, AI-presented lifecycle decision

**Promotion-contract dependency:**
`ofarm.temporal-governance-promotion.issue176-foundation.v0.1`,
`sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0`

**PR boundary:** this RFC only

## Decision

Before any temporal lifecycle decision record may be created, the AI must show
the designated architect one plain English decision card. The card must state
the exact decision, exact subjects, exact effect, non-effects, and the one
approval sentence that can authorize the record.

Only the architect's verbatim reply with that sentence authorizes creation of
the matching decision record.

A pull-request approval, merge, reaction, "LGTM", "approved", "go", generic
instruction, earlier approval, or AI-generated text is not decision
authorization.

The approval authorizes one exact decision record. It does not itself promote
an identity. Effective lifecycle recognition still requires the separately
governed decision record and matching currentness trace required by the
promotion contract.

This contract defines the pre-deployment human workflow only. It adds no
service, credential system, schema, storage, runtime, or promotion behavior.

## Pre-deployment trust model

Version 0.1 uses the existing GitHub pull-request conversation as the review
surface. No new approval service is introduced.

- The AI prepares and displays the card. The AI has no approval authority.
- GitHub user `samovers` is the designated pre-deployment architect for this
  decision.
- The architect approves only by posting the exact sentence as a standalone
  top-level pull-request comment after the card is shown.
- GitHub owns authentication and comment authorship for this pre-deployment
  workflow. This contract adds no credential or principal-resolution logic.
- The eventual decision record must retain the stable approval-comment
  reference plus a snapshot of its actor, time, exact text, and text digest.
- A future currentness trace must bind the exact authorized decision record.

This is a repository-development workflow, not a production authorization
system. A future multi-steward, delegated, signed, or production approval
model requires a separate contract.

## Exact decision card

The AI must show this structure in plain English:

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

What approval authorizes:
One decision record with outcome PROMOTE_GOVERNED_INACTIVE for exactly
the three digest-pinned subjects above.

What approval does not authorize:
No current/default status, runtime activation, RuntimeBundle admission,
profile change, route, command integration, database work, read, output,
deployment, production claim, legacy behavior, or issue #192 behavior.

Who may approve:
GitHub user samovers.

Exact approval sentence:
I explicitly approve PROMOTE_GOVERNED_INACTIVE under
ofarm.temporal-governance-promotion.issue176-foundation.v0.1 at
sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0
for exactly its three digest-pinned subjects, with no activation or
current/default effect.
```

Line wrapping is presentation only. The exact approval text is this single
sentence:

```text
I explicitly approve PROMOTE_GOVERNED_INACTIVE under ofarm.temporal-governance-promotion.issue176-foundation.v0.1 at sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0 for exactly its three digest-pinned subjects, with no activation or current/default effect.
```

The architect must post that sentence alone. Leading or trailing whitespace
may be removed when comparing text. No other normalization, abbreviation,
Markdown markup, quotation, prefix, suffix, or substituted wording is
allowed.

The SHA-256 digest of the exact UTF-8 sentence, with no leading whitespace,
trailing whitespace, or newline, is:

```text
sha256:cea8151ed5a3662a58be38e56fc408e9338ee7a89a66703e27bfb53b69b11d7d
```

## Digest-pinned subjects

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

All three use `OFARM_CANONICAL_JSON_V1`. The card may not abbreviate this set
as "the temporal package" without also showing the exact identities above.

## Closed workflow

The workflow is:

```text
DRAFT_CARD
  -> AI_SHOWS_EXACT_CARD
SHOWN_UNAPPROVED
  -> ARCHITECT_POSTS_EXACT_SENTENCE
RECORD_AUTHORIZED
  -> future separately approved record implementation
```

Rules:

1. The AI validates the card against this exact contract before showing it.
2. The AI shows the whole card and exact approval sentence together.
3. Approval must occur after that card in the same pull-request conversation.
4. The approval must be a top-level comment by GitHub user `samovers`.
5. The comment must contain only the exact approval sentence.
6. Exact approval authorizes one matching decision record only.
7. An edited or deleted approval comment is invalid before the authorized
   decision record is created.
8. Any card change returns the workflow to `DRAFT_CARD` and requires a new
   card and a new exact approval.
9. The future record must copy the outcome, subject set, authority identity,
   approval reference, architect reference, approval text, and text digest
   without reinterpretation.
10. A separate matching currentness trace remains mandatory before effective
   lifecycle recognition.

No merge, commit, timestamp, branch, tag, latest-file rule, environment value,
or caller field advances this state machine.

## Authority map

- The merged promotion contract owns the exact subjects, digests, atomicity,
  allowed outcomes, and meaning of `GOVERNED_INACTIVE`.
- This workflow contract owns the decision-card presentation, exact approval
  sentence, approval ordering, and record-authorization transition.
- The AI owns preparation and exactness checks only. It has no authority to
  approve, infer approval, or alter the decision.
- GitHub user `samovers` owns the pre-deployment architect decision.
- GitHub owns existing authentication, actor attribution, ordering, and the
  immutable approval-comment reference.
- The future decision record owns the authorized disposition after it is
  created under a separately approved implementation contract.
- The future currentness trace owns effective lifecycle-head evidence. It is
  not replaced by the approval comment or decision record.
- Candidate artifacts retain ownership of their reviewed bytes and inactive
  execution postures.
- RuntimeBundle, profile, database, runtime, route, command, read, output,
  deployment, legacy, and #192 authorities remain unchanged.

## Invariants

- **TLAW-001 — AI is not authority.** AI output can present a decision but
  cannot approve or authorize it.
- **TLAW-002 — Plain English card.** The architect sees the exact decision,
  subjects, effect, non-effects, and approval sentence before acting.
- **TLAW-003 — Exact human text.** Only the verbatim standalone sentence from
  the designated architect authorizes the record.
- **TLAW-004 — Approval follows presentation.** Earlier or context-free text
  cannot authorize a later card.
- **TLAW-005 — Exact subjects.** Authorization covers all three digest-pinned
  subjects atomically and no other identity.
- **TLAW-006 — Exact outcome.** The only authorized positive outcome is
  `PROMOTE_GOVERNED_INACTIVE`.
- **TLAW-007 — One authorization.** One exact approval authorizes one
  matching decision record only.
- **TLAW-008 — Mutation invalidates.** Any card, subject, digest, outcome,
  authority, or non-effect change requires a new card and approval.
- **TLAW-009 — Merge is not approval.** Review state, merge, commit, checks,
  reactions, and generic prose never authorize the record.
- **TLAW-010 — Approval is not promotion.** Approval permits record creation
  only; effective state still requires the decision and currentness trace.
- **TLAW-011 — No activation.** Neither approval nor a later
  `GOVERNED_INACTIVE` record grants active or production authority.
- **TLAW-012 — Closed pre-deployment identity.** Version 0.1 admits only the
  designated GitHub architect and defines no delegation or quorum.
- **TLAW-013 — Production firewall.** No production or legacy runtime
  consumes this approval workflow.
- **TLAW-014 — Audit separation.** The workflow adds no #192 behavior.

## Required negative cases

The workflow refuses record authorization when:

- the AI omits or changes part of the card;
- the subjects, digests, outcome, authority, or non-effects differ;
- the sentence appears before the exact card;
- the comment is not from GitHub user `samovers`;
- the comment is a reply instead of a standalone top-level comment;
- the text says "approve", "approved", "go", "LGTM", or similar generic words;
- the sentence contains added explanation, a quotation, Markdown, or changed
  wording;
- the AI, bot, automation, reviewer, merge actor, or another user posts it;
- the pull request is approved or merged without the sentence;
- the card changes after approval;
- one approval is reused for another record, contract version, subject set, or
  outcome;
- the future record omits or changes approval evidence; or
- the approval comment is edited or deleted before record creation; or
- approval is treated as a currentness trace, activation, or promotion by
  itself.

## Non-goals

This contract does not:

- create a decision card artifact, schema, decision record, or currentness
  trace;
- post, approve, sign, store, extract, or promote anything;
- add a service, database, migration, role, key, signature, webhook, bot, or
  runtime approval component;
- change GitHub authentication, permissions, branch protection, or review
  settings;
- edit a candidate, manifest, frozen contract, active registry, RuntimeBundle,
  profile, ActiveArtifactSet, or Capability Manifest;
- activate a selector or command;
- add a route, materialization, current-state read, historical view, WINDOW
  behavior, qualification, output, receipt, or deployment behavior;
- import or change the legacy semantic or output surface; or
- implement or change issue #192.

## Smallest coherent Phase A change

The Phase A PR contains this RFC only. It establishes a reviewable approval
protocol without implementing or executing it.

## Verification

Review must prove:

- the card agrees exactly with the merged promotion contract;
- all three subject identities and digests are present;
- the exact approval sentence binds the promotion contract identity, digest,
  outcome, atomic subject set, and non-activation posture;
- only the designated architect's later standalone exact comment can
  authorize a record;
- merge, review state, reactions, checks, timestamps, and AI output have no
  approval authority;
- approval authorizes one record but does not create promotion or currentness;
- every negative case fails closed;
- the PR changes only this RFC; and
- package conformance and documentation hygiene remain clean.

## Stop conditions

After this contract is approved, work still stops before:

1. showing a live decision card for approval;
2. posting or soliciting the exact approval sentence;
3. defining or implementing a decision-record schema;
4. defining or implementing a currentness-trace schema;
5. creating either record;
6. changing a manifest or effective lifecycle state;
7. activating a RuntimeBundle role, profile, selector, command, or route;
8. adding database, read, historical, WINDOW, output, deployment, legacy, or
   #192 behavior.

The next boundary may draft the inactive decision-record carrier for this
workflow. The currentness-trace carrier remains a separate following
boundary. Neither boundary may request live approval or create a record until
its own contract is separately approved.
