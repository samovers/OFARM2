# OFARM Temporal Governance Decision Log — Phase A Contract v0.1

**Status:** approved plain-English contract; no live decision card, approval
solicitation, log entry, promotion, or runtime change

**Contract identity:**
`ofarm.temporal-governance-decision-log.issue176-predeployment.v0.1`

**Primary ticket:** #176

**Primary trust boundary:** provisional pre-deployment capture and currentness
of one architect-approved temporal-governance decision

**PR boundary:** this RFC only

## 1. Problem and goal

OFARM2 needs a lightweight way to preserve one architect decision before
deployment.

This contract replaces the unimplemented split design involving separate
carrier, decision-record, and currentness-trace layers. It defines one
append-only repository decision log.

A valid log entry is simultaneously:

- evidence of the architect's exact approval; and
- the effective current decision for pre-deployment OFARM2.

It is not current/default artifact promotion, runtime activation, deployment
authorization, or production authority.

## 2. Replacement scope

Once approved and landed as a versioned contract, this contract supersedes
only the earlier requirement for separate technical-decision-record and
currentness-trace artifacts in the pre-deployment temporal-governance workflow.

It preserves the existing:

- exact three-subject set;
- digest bindings;
- `PROMOTE_GOVERNED_INACTIVE` meaning;
- architect-only approval authority;
- inactive execution postures;
- production and legacy firewall; and
- closed non-effects.

Until this replacement contract is landed, nothing changes.

## 3. Decision

The workflow is:

1. The AI shows one complete live decision card in a Codex task.
2. The designated architect sends the exact approval sentence as a later
   user-authored message in that same task.
3. The AI may prepare exactly one matching repository decision-log entry.
4. The entry becomes the current pre-deployment decision only when it is
   present in the governed log on repository `main`.
5. A later valid entry may supersede it only by naming the exact earlier entry
   digest and stating the newly approved decision.

The architect's message provides decision authority. Repository publication
preserves that decision but does not supply or replace the approval.

## 4. Exact decision scope

The only decision allowed by v0.1 is:

```text
PROMOTE_GOVERNED_INACTIVE
```

It applies atomically to exactly:

1. `ofarm.temporal-carrier-matrix.adr0002.v0.1`
2. `ofarm.temporal-carrier-selection.intervention.v0.1`
3. `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1`

The card and entry must bind each identity's exact repository-file digest,
canonical length, and canonical content digest from:

`ofarm.temporal-governance-promotion.issue176-foundation.v0.1`

at:

`sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0`

No schema, other carrier row, RuntimeBundle binding, alias, successor,
command, or future version is included.

## 5. Decision effect and non-effects

The entry's only effect is:

```text
the three exact identities are the current pre-deployment
GOVERNED_INACTIVE decision
```

`GOVERNED_INACTIVE` does not mean active, current/default, deployed,
executable, production-ready, or admitted to a RuntimeBundle.

The entry has no:

- runtime activation;
- current/default claim;
- deployment or production effect;
- RuntimeBundle role, membership, or selection change;
- profile or manifest activation;
- route or command integration;
- database or migration effect;
- read, historical, WINDOW, materialization, qualification, or output effect;
- legacy semantic or output effect; or
- issue #192 effect.

## 6. Live card and exact approval

This contract contains no live card. Any displayed template containing
placeholders is incomplete and cannot authorize a log entry.

A live card must include:

- `LIVE TEMPORAL GOVERNANCE DECISION CARD`;
- the exact Codex task identifier;
- decision `PROMOTE_GOVERNED_INACTIVE`;
- the exact three identities and their pinned digests;
- `supersedes: NONE` for the first entry, or one exact earlier entry digest
  for a successor;
- the complete decision effect and non-effects;
- the decision-log contract identity; and
- the decision-card digest.

The card digest is SHA-256 over the canonical card payload using
`OFARM_CANONICAL_JSON_V1`. The payload includes the task identifier, decision,
subjects, superseded-entry digest, effects, and non-effects. It excludes the
displayed digest and approval sentence to avoid a digest cycle.

The exact approval-sentence template is:

```text
I explicitly approve decision card <CARD_DIGEST> in Codex task <CODEX_TASK_ID> and authorize one matching repository decision-log entry as the current pre-deployment OFARM2 decision, with only the effects and non-effects stated in that card.
```

For a live request, both placeholders are replaced with the exact values shown
on that card. The resulting user message must contain only that single
sentence.

The architect may type the exact sentence or copy it directly from the
complete live decision card displayed earlier in the same Codex task. Either
method is valid when the architect sends the sentence as a later user-authored
message in that task.

Copying does not transfer approval authority. An approval is invalid when its
sentence or card digest is copied from another task, another decision card,
another decision, documentation, a template, AI-authored or AI-sent text other
than the complete live decision card displayed earlier in the same Codex task,
a pull request, a GitHub comment, or any other source. Generic approval and
repository activity never qualify.

## 7. Decision-log entry

A valid entry is one canonical JSON document containing only:

- `contractIdentity`;
- `decisionCardPayload`;
- `decisionCardDigest`;
- `approvalEvidence`;
- `supersedesEntryDigest`; and
- `entryDigest`.

`approvalEvidence` contains:

- `codexTaskId`;
- `approvalUserMessageIdOrStableRef`;
- `approvalMessageRole`, exactly `user`;
- `approvalSentence`;
- `approvalSentenceDigest`;
- `approvalMessageOrder`, exactly
  `AI_ATTESTED_CARD_PRECEDES_APPROVAL_IN_SAME_TASK`; and
- `evidencePosture`, exactly
  `AI_ATTESTED_INDEPENDENTLY_UNVERIFIABLE_PREDEPLOYMENT`.

The entry digest is SHA-256 over the canonical entry excluding `entryDigest`.
The filename and `entryDigest` field must repeat that digest.

The governed log path is:

```text
governance/temporal-decision-log/
```

The first entry has `supersedesEntryDigest: null`.

No review-history list, PR-head list, mutable "latest" pointer, timestamp
ordering, branch ordering, or filename ordering determines the current
decision.

## 8. Current-decision rule

A decision is current for pre-deployment OFARM2 when:

- its entry is valid and present on repository `main`;
- its complete predecessor chain is present and valid;
- no later valid entry explicitly supersedes it; and
- the chain has no fork or conflict.

A later entry becomes current only when it:

1. names the exact digest of the current entry;
2. contains a new complete live card;
3. carries a new exact user-authored approval from the same-task workflow; and
4. states the new decision explicitly.

This v0.1 contract authorizes only `PROMOTE_GOVERNED_INACTIVE`. Any different
future decision requires a separately approved version of the decision-log
contract, but not a separate record or currentness mechanism.

Two successors naming the same predecessor create a fork. A fork means there
is no effective current decision after that predecessor. V0.1 cannot resolve a
fork silently.

## 9. Authority map

- The promotion contract owns the exact subjects, digests, atomicity, and
  meaning of `GOVERNED_INACTIVE`.
- This decision-log contract owns the card-to-approval-to-entry workflow and
  explicit supersession rule.
- The architect's later user-authored message owns the decision.
- The Codex task surface presents provisional task, role, message, and
  ordering evidence.
- The AI prepares the card, observes the provisional evidence, and prepares
  the entry. It has no approval authority.
- Repository `main` preserves the append-only decision sequence. A merge
  publishes evidence but does not approve it.
- The terminal valid entry in the explicit linear chain is the current
  pre-deployment decision.
- RuntimeBundle, profile, database, route, command, read, output, deployment,
  legacy, and #192 authorities remain unchanged.

## 10. Invariants

- `TDL-001` — Only a complete live card in the same Codex task can precede
  approval.
- `TDL-002` — Only the later exact user-authored sentence carries architect
  authority.
- `TDL-003` — The decision covers exactly the three pinned identities
  atomically.
- `TDL-004` — The only v0.1 decision is `PROMOTE_GOVERNED_INACTIVE`.
- `TDL-005` — One approval authorizes at most one matching entry.
- `TDL-006` — Card and entry digests bind all decision-bearing content.
- `TDL-007` — Caller, environment, profile, route, GitHub, or AI data cannot
  alter the decision.
- `TDL-008` — Currentness follows only the valid explicit supersession chain.
- `TDL-009` — Timestamp, filename, branch, merge order, or "latest" inference
  never establishes currentness.
- `TDL-010` — Missing predecessors, invalid entries, or forks fail closed.
- `TDL-011` — A valid entry has only the stated pre-deployment lifecycle
  effect.
- `TDL-012` — Production and legacy runtime surfaces cannot consume the log.
- `TDL-013` — The workflow is provisional and forbidden for deployment.
- `TDL-014` — No #192 behavior or authority changes.

## 11. Required negative cases

No entry is valid when:

- the card is incomplete, templated, reconstructed from documentation, or
  from another task;
- the approval precedes the card;
- the message role is not `user`;
- the message contains generic, abbreviated, quoted, prefixed, suffixed,
  reformatted, or otherwise changed approval;
- the approval sentence or card digest was copied from another task, another
  decision card, another decision, documentation, a template, AI-authored or
  AI-sent text other than the complete live decision card displayed earlier in
  the same Codex task, a pull request, a GitHub comment, or any other source;
- the task identifier, card digest, sentence, or sentence digest differs;
- a subject, digest, decision, effect, or non-effect differs;
- caller data selects any decision-bearing value;
- one approval is reused for a second entry;
- an entry digest does not recompute;
- an entry omits its predecessor or names the wrong predecessor;
- two entries supersede the same predecessor;
- a branch-only entry is treated as current;
- a PR approval or merge is treated as architect approval;
- an entry is treated as active, current/default, deployed, executable, or
  output-eligible; or
- production or legacy code imports or consumes the log.

## 12. Non-goals

This contract does not:

- display a live card or solicit approval;
- create an actual log entry;
- issue a promotion decision;
- add a schema, carrier artifact, decision-record layer, or currentness-trace
  layer;
- add a service, database, migration, role, signer, key, webhook, or GitHub
  automation;
- implement a writer, route, API, runtime selector, or command;
- change RuntimeBundle, profile, manifest, active registry, or current/default
  state;
- add reads, history, WINDOW behavior, materialization, qualification,
  outputs, or receipts;
- change frozen active contracts or SI artifacts; or
- change #192.

## 13. Provisional design record

This repository decision log is acceptable only before deployment because:

- the architect's task message remains the human authority;
- the entry is digest-pinned and append-only;
- the effects are limited to inactive pre-deployment governance; and
- no runtime consumes the decision.

Its task and message evidence remains AI-attested and independently
unverifiable.

Before deployment, this workflow must be replaced by independently
human-controlled and independently verifiable approval or signing. The
replacement must preserve the decision chain and explicit supersession
semantics without relying on repository credentials or AI testimony.

## 14. Verification and stop conditions

Plain-English review must verify:

- one card, one approval, and one entry form one understandable transition;
- the exact three subjects and decision are fixed;
- the entry is both approval evidence and pre-deployment current decision;
- currentness depends only on explicit supersession;
- merge and repository credentials provide no human authority;
- every non-effect remains closed;
- every negative case fails closed; and
- the provisional workflow cannot reach deployment or runtime.

This Phase A changes only this RFC.

After approval, work still stops before:

1. showing a live card;
2. soliciting the approval sentence;
3. creating a decision-log entry;
4. issuing promotion;
5. implementing schemas, services, databases, automation, or runtime
   behavior; or
6. changing RuntimeBundle, routes, commands, outputs, legacy behavior, or
   #192.

## Review disposition

- Blockers: none identified in this replacement contract.
- Follow-ups: independently controlled deployment-grade approval/signing.
- Preferences: none.

Once the acceptance criteria pass and no demonstrated Blocker remains, merge
the documentation-only pull request. New ideas, Preferences, and non-blocking
hardening become Follow-ups and do not reopen review.
