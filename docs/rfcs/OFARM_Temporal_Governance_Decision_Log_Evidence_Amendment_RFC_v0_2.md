# OFARM Temporal Governance Decision Log Evidence Amendment v0.2

**Status:** draft for plain-English review; no live decision card, approval
solicitation, decision-log entry, promotion, or runtime change

**Contract identity:**
`ofarm.temporal-governance-decision-log.issue176-predeployment.v0.2`

**Primary ticket:** #176

**Primary trust boundary:** pre-deployment promotion-decision evidence mapping
for the provisional repository decision log

**PR boundary:** this RFC only

## 1. Problem

The landed v0.1 decision-log contract defines one digest-pinned entry as both
approval evidence and the effective current pre-deployment decision. Its exact
entry shape does not explicitly carry every field required by the pinned
promotion contract:

| Required field | v0.1 disposition |
|---|---|
| `promotionDecisionRef` | Absent. |
| `humanPromotionAuthorityRef` | Indirect in two approval fields. |
| `decidedAt` | Absent. |
| `reviewEvidenceRefs` | Absent. |
| `currentnessTraceRef` | Represented indirectly by the predecessor chain. |

The pinned promotion contract fails closed on missing or ambiguous decision or
currentness evidence. No v0.1 entry may therefore be prepared.

This amendment makes all five fields explicit without adding a separate
record, separate currentness artifact, schema, service, database, signer, or
runtime.

## 2. Pinned authorities

This amendment depends on:

1. Promotion contract
   - identity:
     `ofarm.temporal-governance-promotion.issue176-foundation.v0.1`
   - repository-file digest:
     `sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0`
2. Base decision-log contract
   - identity:
     `ofarm.temporal-governance-decision-log.issue176-predeployment.v0.1`
   - repository file:
     `docs/rfcs/OFARM_Temporal_Governance_Decision_Log_RFC_v0_1.md`
   - repository-file digest:
     `sha256:958c4a3c2377515022bc1dd6483136e923b9bfa110b507f102a9ec623a0e5d89`

The promotion contract owns the required evidence-field names, the exact
promotion subjects and content pins, atomicity, the closed outcome, and the
meaning of `GOVERNED_INACTIVE`.

The base decision-log contract owns the same-task card, exact user approval,
canonicalization, entry digest, explicit predecessor chain, provisional
currentness rule, effects, non-effects, and deployment stop.

## 3. Amendment decision

Once reviewed and landed, v0.2 supersedes v0.1 as the operative decision-log
contract. V0.1 remains pinned historical evidence and supplies the rules
preserved by reference in this amendment.

V0.2 preserves every v0.1 rule except:

- the operative decision-log contract identity becomes v0.2;
- the card payload gains its governing contract file digest, each subject's
  schema version, and an exact decision-evidence mapping;
- the exact approval sentence binds that evidence mapping;
- the entry gains the five promotion-contract evidence fields; and
- the final entry contains eleven top-level fields instead of six.

No valid v0.1 entry exists. There is no entry migration, predecessor rewrite,
or currentness conversion.

The earlier live card with digest
`sha256:6f8d61738483ad75c56292297696a3724950d2e170fab6032a2eea6736e3a759`
is withdrawn. It cannot authorize any entry and must not be approved.

## 4. Exact evidence-field mapping

Each final v0.2 entry records the five fields at its top level.

### `promotionDecisionRef`

The exact value is:

```json
{
  "decisionCardDigest": "<CARD_DIGEST>",
  "decisionLogContractIdentity": "ofarm.temporal-governance-decision-log.issue176-predeployment.v0.2"
}
```

The card digest includes the Codex task identifier, exact decision, exact
subjects, evidence mapping, effects, non-effects, and predecessor. Together
with the v0.2 identity it is the unique non-circular promotion-decision
reference.

### `humanPromotionAuthorityRef`

The exact value is:

```json
{
  "codexTaskId": "<CODEX_TASK_ID>",
  "userMessageIdOrStableRef": "<APPROVAL_USER_MESSAGE_ID_OR_STABLE_REF>"
}
```

Both values come from the approval turn in the Codex task surface. They must
equal `approvalEvidence.codexTaskId` and
`approvalEvidence.approvalUserMessageIdOrStableRef`.

This is provisional AI-attested evidence. It does not make repository
credentials, GitHub activity, or the AI a human promotion authority.

### `decidedAt`

`decidedAt` is the decision time of the architect's exact approval message.
Its only lawful source is:

```text
x-codex-turn-metadata.turn_started_at_unix_ms
```

observed on the later user-authored approval turn in the same Codex task.

The integer milliseconds are converted to UTC using the equivalent of
`new Date(value).toISOString()`. The stored form is exactly
`YYYY-MM-DDTHH:mm:ss.sssZ`.

AI clock time, tool time, commit time, merge time, filesystem time, PR time,
and entry-publication time are forbidden substitutes. Missing, malformed, or
inconsistent approval-turn time stops entry preparation.

`decidedAt` describes the human decision act. It never orders entries or
establishes currentness. If a future governance envelope describes the same
act, ADR 0002 requires its decision time to equal this value.

### `reviewEvidenceRefs`

The exact ordered array is:

```json
[
  {
    "contractIdentity": "ofarm.temporal-governance-promotion.issue176-foundation.v0.1",
    "repositoryFileDigest": "sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0"
  },
  {
    "contractIdentity": "ofarm.temporal-governance-decision-log.issue176-predeployment.v0.1",
    "repositoryFileDigest": "sha256:958c4a3c2377515022bc1dd6483136e923b9bfa110b507f102a9ec623a0e5d89"
  },
  {
    "contractIdentity": "ofarm.temporal-governance-decision-log.issue176-predeployment.v0.2",
    "repositoryFileDigest": "<V0_2_CONTRACT_REPOSITORY_FILE_DIGEST>"
  }
]
```

The v0.2 digest is SHA-256 over the exact merged RFC bytes on repository
`main`. It cannot be filled from branch bytes, a PR head, or caller data.

This is a closed contract-evidence set, not a review-history list. PR numbers,
PR heads, comments, reactions, model reviews, and merge commits are not
decision evidence and cannot appear in this array.

### `currentnessTraceRef`

The exact value is:

```json
{
  "decisionCardDigest": "<CARD_DIGEST>",
  "mechanism": "CONTAINING_ENTRY_AND_EXPLICIT_PREDECESSOR_CHAIN",
  "supersedesEntryDigest": null
}
```

For a successor, `null` is replaced by the exact predecessor entry digest and
must equal the entry's top-level and card-payload
`supersedesEntryDigest`.

This reference resolves to the containing final entry only when:

1. `decisionCardDigest` recomputes from the embedded card payload;
2. the approval and all five decision-evidence fields validate;
3. the final `entryDigest` and filename recompute;
4. the entry is present in the governed log on repository `main`;
5. every predecessor is present and valid; and
6. the entry is the unforked terminal entry in that explicit chain.

The containing entry and predecessor chain are the currentness trace. Physical
co-location does not combine authority: the architect's message owns the
decision, while successful chain validation owns effective-head evidence.
Neither can substitute for the other.

`decidedAt`, timestamp order, filename order, branch order, merge order, and
"latest" inference never establish currentness.

## 5. Exact v0.2 card construction

The v0.2 card payload is constructed from the standalone exact card JSON in
the pinned v0.1 RFC by applying only these closed changes:

1. Replace `contractIdentity` with
   `ofarm.temporal-governance-decision-log.issue176-predeployment.v0.2`.
2. Add top-level string `contractRepositoryFileDigest`, equal to the exact
   merged v0.2 RFC repository-file digest.
3. Add top-level object `decisionEvidenceMapping` with this exact value:

```json
{
  "currentnessTraceRef": "CONTAINING_ENTRY_AND_EXPLICIT_PREDECESSOR_CHAIN",
  "decidedAt": "APPROVAL_USER_MESSAGE_TURN_STARTED_AT_UTC_MILLISECONDS",
  "humanPromotionAuthorityRef": "CODEX_TASK_AND_APPROVAL_USER_MESSAGE_STABLE_REF",
  "promotionDecisionRef": "DECISION_LOG_CONTRACT_IDENTITY_AND_CARD_DIGEST",
  "reviewEvidenceRefs": "PINNED_PROMOTION_BASE_AND_AMENDMENT_CONTRACTS"
}
```

4. Add each subject's exact `schemaVersion`:
   - `ofarm.temporal-carrier-matrix.adr0002.v0.1`:
     `ofarm.temporal-carrier-matrix.v0.1`
   - `ofarm.temporal-carrier-selection.intervention.v0.1`:
     `ofarm.temporal-carrier-selection-binding.v0.1`
   - `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1`:
     `ofarm.temporal-governed-command-binding.v0.1`

5. Replace `<CODEX_TASK_ID>` with the exact current task identifier.
6. Use `null` for the first `supersedesEntryDigest`, or the exact current
   predecessor digest for a successor.

All other keys, values, JSON types, array order, subject order, and
canonicalization rules remain exactly as pinned in v0.1. Keys not produced by
this construction are forbidden.

The governing contract file digest and the Codex task identifier come from
their named authorities. The current valid chain supplies the predecessor.
Caller, user, AI, profile, route, environment, and repository credentials
cannot select any other card value.

The exact v0.2 approval-sentence template is:

```text
I explicitly approve decision card <CARD_DIGEST> in Codex task <CODEX_TASK_ID> and authorize one matching repository decision-log entry as the current pre-deployment OFARM2 decision, with exactly the decision-evidence mapping, effects, and non-effects stated in that card.
```

The user message must contain only the filled single sentence. Every v0.1
approval sentence and digest is invalid for v0.2.

## 6. Exact v0.2 entry construction

Start from the pinned v0.1 entry-digest input and apply only these changes:

1. Replace `contractIdentity` with the v0.2 identity.
2. Replace `decisionCardPayload` with the exact v0.2 card payload.
3. Replace `decisionCardDigest` and the approval sentence with their exact
   v0.2 values.
4. Add the five top-level fields defined in section 4.

The entry-digest input therefore contains exactly these ten top-level fields:

1. `approvalEvidence`
2. `contractIdentity`
3. `currentnessTraceRef`
4. `decidedAt`
5. `decisionCardDigest`
6. `decisionCardPayload`
7. `humanPromotionAuthorityRef`
8. `promotionDecisionRef`
9. `reviewEvidenceRefs`
10. `supersedesEntryDigest`

The final entry adds only `entryDigest`, producing eleven top-level fields.
The v0.1 canonicalization, digest, filename, path, approval exactness, one-use,
and explicit-chain rules remain binding.

`approvalEvidence`, `humanPromotionAuthorityRef`, and `decidedAt` must describe
the same user-authored approval turn. `promotionDecisionRef`,
`currentnessTraceRef`, and `decisionCardDigest` must describe the same card.
Both predecessor fields must be identical.

No self-digest appears inside the entry-digest input. The decision and
currentness references are unique logical references that resolve through the
validated final entry, avoiding a digest cycle.

## 7. Authority map

- The pinned promotion contract owns the five required evidence-field names,
  exact promotion set, content pins, atomicity, and outcome.
- The v0.1 base contract owns the preserved card, approval, entry, digest,
  chain, effect, non-effect, provisional, and deployment-stop rules.
- This v0.2 amendment owns only the explicit five-field mapping and the closed
  card and entry transformations.
- The designated architect's later exact user-authored message owns the
  promote-or-refuse decision.
- The Codex approval turn is the provisional source of the task identifier,
  user-message stable reference, message role, order, and `decidedAt`.
- The AI may display the card, derive fields, and prepare an entry. It has no
  decision or currentness authority.
- Validation of the containing entry and explicit predecessor chain owns
  currentness-trace resolution.
- Repository `main` preserves the entry and chain but supplies neither human
  approval nor timestamp authority.
- RuntimeBundle, profile, database, route, command, read, output, deployment,
  legacy, and #192 authorities remain unchanged.

## 8. Invariants

- `TDE-001` — Every valid entry carries all five required fields explicitly.
- `TDE-002` — Every subject carries its exact promotion-contract schema
  version as well as its existing content pins.
- `TDE-003` — `promotionDecisionRef` is the exact v0.2 identity and card
  digest pair.
- `TDE-004` — `humanPromotionAuthorityRef` identifies the same task and user
  message as `approvalEvidence`.
- `TDE-005` — `decidedAt` comes only from the approval turn's task metadata
  and has exact UTC millisecond form.
- `TDE-006` — `decidedAt` never orders entries or establishes currentness.
- `TDE-007` — `reviewEvidenceRefs` is the exact three-contract set and never
  a GitHub or model-review history.
- `TDE-008` — `currentnessTraceRef` explicitly binds the containing decision
  card and predecessor chain without a self-digest cycle.
- `TDE-009` — Human-decision authority and chain-currentness authority remain
  separate even though their evidence is co-located.
- `TDE-010` — Missing, conflicting, malformed, or caller-selected evidence
  fails closed with all three subjects unpromoted.
- `TDE-011` — V0.1 cards, sentences, and entries cannot authorize v0.2.
- `TDE-012` — No v0.2 live card exists before the exact amendment bytes are
  reviewed and present on repository `main`.
- `TDE-013` — The workflow remains provisional and forbidden for deployment.
- `TDE-014` — No runtime, storage, output, legacy, or #192 authority changes.

## 9. Required negative cases

Entry preparation stops when:

- any of the five required fields is absent, additional, or malformed;
- any decision-evidence field appears only indirectly;
- any subject lacks or changes its exact `schemaVersion`;
- the v0.2 contract repository-file digest does not match merged `main`;
- `promotionDecisionRef` differs from the v0.2 identity or card digest;
- the authority reference differs from the approval task or user message;
- `decidedAt` is missing, inferred, rounded, reformatted, or sourced from any
  clock or repository event;
- `decidedAt` is used to select a current entry;
- review evidence is missing, reordered, additional, branch-derived, or
  replaced by PR, GitHub, model, test, or merge evidence;
- the currentness reference differs from the card or predecessor;
- the currentness reference is treated as resolved before final entry and
  chain validation on `main`;
- approval or currentness authority substitutes for the other;
- a v0.1 card, sentence, digest, or entry is reused;
- a card is shown before v0.2 is reviewed and landed;
- caller, user, AI, environment, profile, route, or timestamp data selects a
  decision-bearing value; or
- an entry is treated as active, current/default, deployed, executable,
  RuntimeBundle-admitted, output-eligible, or production authority.

## 10. Smallest coherent change and verification

The smallest coherent change is this one versioned amendment RFC. It leaves
the landed v0.1 bytes, pinned promotion artifacts, manifests, ERRATA, checkers,
and all executable surfaces unchanged.

Review and mechanical verification must confirm:

- the promotion and v0.1 repository-file digests recompute;
- all five promotion evidence fields appear exactly once at entry top level;
- every subject gains the exact pinned `schemaVersion`;
- the card construction is deterministic under the merged v0.2 file digest;
- the entry-digest input has exactly ten top-level fields;
- the final entry rule adds only `entryDigest`;
- decision, approval-turn, review, and currentness references agree;
- no timestamp participates in currentness;
- no self-digest cycle exists;
- no live card, approval, log path, entry, or promotion is created; and
- package conformance and Markdown hygiene still pass.

## 11. Non-goals and stop conditions

This amendment does not:

- display or create a live decision card;
- solicit or record architect approval;
- create a decision-log entry or governed log path;
- issue promotion or change any lifecycle state;
- add a schema, manifest, checker constant, ERRATA entry, service, database,
  migration, role, signer, key, webhook, or GitHub automation;
- change RuntimeBundle, profile, active registry, current/default state,
  route, command, selector, materialization, read, history, WINDOW,
  qualification, output, receipt, legacy behavior, or #192; or
- authorize deployment use of the provisional workflow.

After this RFC is reviewed and landed, work still stops before:

1. recomputing and displaying the complete v0.2 live card from merged `main`;
2. soliciting the exact approval sentence;
3. preparing an entry from approval-turn metadata;
4. creating the governed log path or entry;
5. issuing promotion; or
6. changing any runtime or production authority.
