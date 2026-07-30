# OFARM Temporal Governance Decision Log — Phase A Contract v0.1

**Status:** draft for plain-English review; no live decision card, approval
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
decision-record and currentness-trace layers. It defines one append-only
repository decision log.

A valid log entry is simultaneously:

- evidence of the architect's exact approval; and
- the effective current decision for pre-deployment OFARM2.

It is not current/default artifact promotion, runtime activation, deployment
authorization, or production authority.

## 2. Replacement scope

Once approved and landed as a versioned contract, this contract supersedes:

- contract identity
  `ofarm.temporal-lifecycle-approval-workflow.issue176-foundation.v0.1`;
- repository file
  `docs/rfcs/OFARM_Temporal_Lifecycle_Approval_Workflow_RFC_v0_1.md`;
- repository-file digest
  `sha256:165d55b92a3fabad54cdc7b8166ed56b2b0c38fb8367b181b0b799dcd1921c45`;
- its fixed card payload and
  `sha256:aa9d5b5fc8aa39745e5ffbd2b8b05e9edda59ab46df98ca61e2a91e02434b819`
  card digest;
- its exact approval sentence and
  `sha256:ed89c58b9b3c75e3f417982ffbece0f44667e8d8a53351f2dfb893febc20897f`
  sentence digest; and
- its requirement for separate technical-decision-record and
  currentness-trace artifacts.

The superseded contract remains historical review evidence only. It is not an
alternative approval source after this contract lands.

It preserves the existing:

- exact three-subject set;
- digest bindings;
- `PROMOTE_GOVERNED_INACTIVE` meaning;
- architect-only approval authority;
- inactive execution postures;
- production and legacy firewall; and
- closed non-effects.

This contract deliberately changes the architect's required action. The
architect still supplies the only approval authority through a later
user-authored message, but may type the exact sentence or copy it directly from
the complete live card shown earlier in the same Codex task. This is
attestation by the architect's later message, not a claim that the architect
authored the sentence's wording. No other copied source is valid.

The old invariants have these exact dispositions:

| Earlier invariant | Disposition under this contract |
|---|---|
| `TLAW-001` | Preserved → `TDL-002`, `TDL-007`, authority map. |
| `TLAW-002` | Preserved → `TDL-001`. |
| `TLAW-003` | Preserved → `TDL-002`. |
| `TLAW-004` | Modified → `TDL-002`; same-task live-card copy is valid. |
| `TLAW-005` | Preserved → `TDL-003`. |
| `TLAW-006` | Preserved → `TDL-004`. |
| `TLAW-007` | Restated → `TDL-005`; one entry replaces one record. |
| `TLAW-008` | Preserved → `TDL-006` and the negative cases. |
| `TLAW-009` | Preserved → `TDL-007`, `TDL-009`. |
| `TLAW-010` | Preserved → `TDL-002`, `TDL-008`, `TDL-011`. |
| `TLAW-011` | Superseded → one entry and chain replace two layers. |
| `TLAW-012` | Preserved → `TDL-011`, `TDL-012`. |
| `TLAW-013` | Preserved → `TDL-013`. |
| `TLAW-014` | Preserved → `TDL-012`. |
| `TLAW-015` | Preserved → `TDL-014`. |
| `TLAW-016` | Preserved → `TDL-013`, provisional design record. |

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

The card-digest input has exactly the closed logical JSON shape below. Keys
not shown are forbidden. The displayed placeholder strings are invalid and
make this documentation object incapable of authorizing an entry.

```json
{
  "contractIdentity": "ofarm.temporal-governance-decision-log.issue176-predeployment.v0.1",
  "codexTaskId": "<CODEX_TASK_ID>",
  "decision": "PROMOTE_GOVERNED_INACTIVE",
  "decisionEffect": "ALL_THREE_EXACT_SUBJECTS_ARE_CURRENT_PREDEPLOYMENT_GOVERNED_INACTIVE_DECISION",
  "nonEffects": [
    "RUNTIME_ACTIVATION",
    "CURRENT_DEFAULT_ARTIFACT_STATUS",
    "DEPLOYMENT_OR_PRODUCTION_EFFECT",
    "RUNTIME_BUNDLE_CHANGE",
    "PROFILE_OR_MANIFEST_ACTIVATION",
    "ROUTE_OR_COMMAND_INTEGRATION",
    "DATABASE_OR_MIGRATION_EFFECT",
    "READ_HISTORICAL_WINDOW_MATERIALIZATION_QUALIFICATION_OR_OUTPUT_EFFECT",
    "LEGACY_SEMANTIC_OR_OUTPUT_EFFECT",
    "ISSUE_192_EFFECT"
  ],
  "promotionContractIdentity": "ofarm.temporal-governance-promotion.issue176-foundation.v0.1",
  "promotionContractRepositoryFileDigest": "sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0",
  "subjects": [
    {
      "canonicalByteLength": 9504,
      "canonicalContentDigest": "sha256:c404c0cd1e08f389664b5381c2c038cf65bac9a3b725fc2b1882990636eb179b",
      "canonicalization": "OFARM_CANONICAL_JSON_V1",
      "identity": "ofarm.temporal-carrier-matrix.adr0002.v0.1",
      "repositoryFileDigest": "sha256:7cb26513b5abdbcadecaf6f9b47d874a742ba8fa05a332c9130deebe449d7fc6"
    },
    {
      "canonicalByteLength": 1814,
      "canonicalContentDigest": "sha256:373a5f402ad077039946c1dfe7b972e4382d3c6a6805fbf0b271e4a0bc729bf1",
      "canonicalization": "OFARM_CANONICAL_JSON_V1",
      "identity": "ofarm.temporal-carrier-selection.intervention.v0.1",
      "repositoryFileDigest": "sha256:9886aace0670b6a83f17cd33cbc67aa62fafcfd0ea873faed9194c2aaa07efe5"
    },
    {
      "canonicalByteLength": 9614,
      "canonicalContentDigest": "sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1",
      "canonicalization": "OFARM_CANONICAL_JSON_V1",
      "identity": "ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1",
      "repositoryFileDigest": "sha256:0909ec653cb99a94cd1b35afaf2d386258aac671c5f730960ed485df8a4b8f2e"
    }
  ],
  "supersedesEntryDigest": null
}
```

For a live first-entry card, `<CODEX_TASK_ID>` is replaced by the exact,
non-empty task identifier. For a successor card, the task identifier is
replaced and `null` is replaced by the exact lowercase
`sha256:<64-lowercase-hex>` digest of the current entry. Every other key,
value, JSON type, and array order is fixed by this contract.

The Codex task surface is the provisional source of `codexTaskId`. The valid
decision-log chain is the source of `supersedesEntryDigest`. This contract and
its pinned promotion contract are the source of every other payload value.
Caller, user, AI, route, profile, and environment data cannot select or alter
those values.

`OFARM_CANONICAL_JSON_V1` means UTF-8 JSON with object keys sorted
lexicographically, no insignificant whitespace, `,` and `:` separators, and
Unicode emitted without ASCII escaping. Arrays retain the displayed order.
No newline is appended. In Python terms, the exact operation is
`json.dumps(value, sort_keys=True, separators=(",", ":"),`
`ensure_ascii=False, allow_nan=False).encode("utf-8")`.

The card digest is `sha256:` plus the lowercase SHA-256 hexadecimal digest of
those canonical bytes. The logical payload excludes the displayed card digest
and approval sentence, avoiding a digest cycle.

This RFC does not publish a worked live digest because doing so would require
inventing live task evidence. A future card is reproducible only after its
exact task identifier and, for a successor, predecessor digest exist.

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

The entry-digest input has exactly the closed logical JSON shape below. The
`decisionCardPayload` object is embedded, not referenced. Keys not shown are
forbidden. Every placeholder string is invalid.

```json
{
  "approvalEvidence": {
    "approvalMessageOrder": "AI_ATTESTED_CARD_PRECEDES_APPROVAL_IN_SAME_TASK",
    "approvalMessageRole": "user",
    "approvalSentence": "<APPROVAL_SENTENCE>",
    "approvalSentenceDigest": "<APPROVAL_SENTENCE_DIGEST>",
    "approvalUserMessageIdOrStableRef": "<APPROVAL_USER_MESSAGE_ID_OR_STABLE_REF>",
    "codexTaskId": "<CODEX_TASK_ID>",
    "evidencePosture": "AI_ATTESTED_INDEPENDENTLY_UNVERIFIABLE_PREDEPLOYMENT"
  },
  "contractIdentity": "ofarm.temporal-governance-decision-log.issue176-predeployment.v0.1",
  "decisionCardDigest": "<CARD_DIGEST>",
  "decisionCardPayload": {
    "contractIdentity": "ofarm.temporal-governance-decision-log.issue176-predeployment.v0.1",
    "codexTaskId": "<CODEX_TASK_ID>",
    "decision": "PROMOTE_GOVERNED_INACTIVE",
    "decisionEffect": "ALL_THREE_EXACT_SUBJECTS_ARE_CURRENT_PREDEPLOYMENT_GOVERNED_INACTIVE_DECISION",
    "nonEffects": [
      "RUNTIME_ACTIVATION",
      "CURRENT_DEFAULT_ARTIFACT_STATUS",
      "DEPLOYMENT_OR_PRODUCTION_EFFECT",
      "RUNTIME_BUNDLE_CHANGE",
      "PROFILE_OR_MANIFEST_ACTIVATION",
      "ROUTE_OR_COMMAND_INTEGRATION",
      "DATABASE_OR_MIGRATION_EFFECT",
      "READ_HISTORICAL_WINDOW_MATERIALIZATION_QUALIFICATION_OR_OUTPUT_EFFECT",
      "LEGACY_SEMANTIC_OR_OUTPUT_EFFECT",
      "ISSUE_192_EFFECT"
    ],
    "promotionContractIdentity": "ofarm.temporal-governance-promotion.issue176-foundation.v0.1",
    "promotionContractRepositoryFileDigest": "sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0",
    "subjects": [
      {
        "canonicalByteLength": 9504,
        "canonicalContentDigest": "sha256:c404c0cd1e08f389664b5381c2c038cf65bac9a3b725fc2b1882990636eb179b",
        "canonicalization": "OFARM_CANONICAL_JSON_V1",
        "identity": "ofarm.temporal-carrier-matrix.adr0002.v0.1",
        "repositoryFileDigest": "sha256:7cb26513b5abdbcadecaf6f9b47d874a742ba8fa05a332c9130deebe449d7fc6"
      },
      {
        "canonicalByteLength": 1814,
        "canonicalContentDigest": "sha256:373a5f402ad077039946c1dfe7b972e4382d3c6a6805fbf0b271e4a0bc729bf1",
        "canonicalization": "OFARM_CANONICAL_JSON_V1",
        "identity": "ofarm.temporal-carrier-selection.intervention.v0.1",
        "repositoryFileDigest": "sha256:9886aace0670b6a83f17cd33cbc67aa62fafcfd0ea873faed9194c2aaa07efe5"
      },
      {
        "canonicalByteLength": 9614,
        "canonicalContentDigest": "sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1",
        "canonicalization": "OFARM_CANONICAL_JSON_V1",
        "identity": "ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1",
        "repositoryFileDigest": "sha256:0909ec653cb99a94cd1b35afaf2d386258aac671c5f730960ed485df8a4b8f2e"
      }
    ],
    "supersedesEntryDigest": null
  },
  "supersedesEntryDigest": null
}
```

The live values obey these rules:

- all placeholders are replaced by non-empty strings;
- both `codexTaskId` values are identical;
- `decisionCardPayload` is the exact payload whose digest is
  `decisionCardDigest`;
- `approvalSentence` is the exact one-sentence live approval from section 6;
- `approvalSentenceDigest` is `sha256:` plus the lowercase SHA-256 digest of
  the approval sentence's exact UTF-8 bytes, with no newline;
- `approvalUserMessageIdOrStableRef` is the exact stable reference observed
  for that later user-authored message;
- both `supersedesEntryDigest` values are identical; and
- the first entry uses `null`, while a successor uses the exact lowercase
  `sha256:<64-lowercase-hex>` predecessor digest in both locations.

The architect's user message is the source of `approvalSentence`. The Codex
task surface is the provisional source of its role, order, stable reference,
and task identifier. All digests are derived values. No caller or repository
credential supplies approval evidence.

The entry digest is `sha256:` plus the lowercase SHA-256 hexadecimal digest of
the entry-digest input serialized with `OFARM_CANONICAL_JSON_V1`. The final
entry adds one top-level `entryDigest` string containing that digest and
changes nothing else. The final six-field object is stored using the same
canonicalization with no appended newline.

The filename is the 64 lowercase hexadecimal characters from `entryDigest`,
without the `sha256:` prefix, followed by `.json`.

The governed log path is:

```text
governance/temporal-decision-log/
```

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
is no effective current decision after that predecessor. Version 0.1 defines
no fork-resolution entry. No entry governed by v0.1 may claim to recover the
chain. Recovery requires a separately reviewed and approved later contract
version that explicitly defines its authority and inputs.

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
- an entry governed by v0.1 claims to resolve a fork;
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
