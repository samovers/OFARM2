# OFARM Operation-Claim Draft Temporal Command RFC v0.1

**Status:** package-local `CANDIDATE_ARTIFACT`; contract-only,
production-surface-closed and inactive

**Binding schema version:**
`ofarm.temporal-governed-command-binding.v0.1`

**Binding schema digest:**
`sha256:afda003df90e2787cfdc97f5561e3e5b098177a5add91556af2e935a3b9711db`

**Binding identity:**
`ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1`

**Binding artifact digest:**
`sha256:0909ec653cb99a94cd1b35afaf2d386258aac671c5f730960ed485df8a4b8f2e`

**Primary implementation ticket:** #176

**Primary trust boundary:** versioned governance for one inactive production
command specialization

## Decision

This contract governs exactly one future command:
`COMMIT_OPERATION_CLAIM_DRAFT`.

The command accepts one already-authenticated, tenant-bound, manual submission
composed of:

- one `CommitIngressRequest` with `commitClass=OPERATION_CLAIM`,
  `ingressChannel=MANUAL_UI`, no acting agent, and no requested promotion;
- one `SemanticEventEnvelope` with
  `primaryEventFamily=InterventionEvent`; and
- one `ExecutionRecordPayload` with `recordClass=OPERATION_CLAIM` and
  `recordState=CLAIMED`.

The three artifacts must each pass complete Draft 2020-12 validation against
their fixed frozen contract. Their request, event, payload, party, subject, and
target identities must also satisfy every cross-artifact admission rule in the
binding artifact. Only that exact, linked tuple becomes this command.

`RETAIN_DRAFT` means safe persistence of an unpromoted draft, not semantic
success. It is the defined disposition both when valid-time selection succeeds
and when an authorized request reaches the explicit selector-refusal branch.
The command never emits an assertion, review decision, accepted consequence,
materialization, qualification, output, or receipt. `PROMOTE_ACCEPTED` is
unsupported.

The binding artifact is exact by design. Its schema contains one complete
`const`, rather than an extensible command family, so adding another command,
channel, carrier row, outcome, or authority requires a separately reviewed
version.

## Trust boundary and intended later PR

This Phase A boundary freezes command meaning only. It adds no executable
command and changes no active authority.

A later implementation PR may implement this exact specialization only after
both missing production authorities named under “Stop conditions” have their
own reviewed bindings. That PR may connect:

- trusted tenant and principal binding;
- trusted RuntimeBundle selection;
- a reviewed production authorization provider;
- the approved intervention valid-time selector;
- the approved tenant knowledge-position allocator; and
- writes of the already frozen source and evidence contracts.

If that work needs a route, active registry, profile, RuntimeBundle selection
change, database change, frozen-contract edit, public refusal-vocabulary
change, output behavior, or #192 audit behavior, it is a different trust
boundary and must not be added to the command implementation PR.

## Closed admission seam

The command API is not opened by this contract. The future internal
application service has one closed admission seam:

```text
trusted TenantBinding
+ trusted RuntimeBundle binding
+ CommitIngressRequest
+ SemanticEventEnvelope
+ ExecutionRecordPayload
-> admitted command or NOT_THIS_COMMAND_NO_WRITE
```

The binding identity, schema identities and digests, temporal-coordinate
identity, carrier-matrix identity and row, selector paths, action class,
action stage, governed operation, and result policy come only from this
reviewed versioned artifact. None is accepted from caller data.

`NOT_THIS_COMMAND_NO_WRITE` is a seam result, not a new public
`RuntimeProblem.reasonCode`. It applies when any source artifact is malformed,
has the wrong discriminator, or fails a required cross-artifact identity
relationship. No governed batch, knowledge position, record, idempotency
claim, or output is created.

The exact cross-artifact rules are:

- request `actingPartyRef` equals the trusted bound party;
- request `actingAgentRef` is absent;
- request `requestedPromotionTarget` is absent;
- request `semanticEventRef` equals event `semanticEventId`;
- event `executionRecordPayloadRefs` is the exact singleton payload id;
- payload `sourceEventRef`, when present, equals the event id;
- request `targetScopes` is the exact singleton payload execution target;
- event `anchorScopes` is the exact singleton payload execution target;
- event `subjectRefs` is the exact singleton payload subject ref;
- payload subject equals the payload execution target;
- payload `anchorScopes` contains the exact payload execution target;
- payload actor party equals the trusted bound party; and
- payload `recordState` is `CLAIMED`.

The source tuple may carry other fields already allowed by the frozen source
contracts. Such fields do not acquire temporal, authority, promotion, or
output meaning unless this binding explicitly assigns it.

## Authority map

- ADR 0002 owns the independence of valid time and knowledge time, carrier
  meaning, half-open interval law, and tenant-local knowledge ordering.
- `ofarm.temporal-coordinate.v0.1` owns the versioned `ValidCut` and
  `KnowledgeCut` vocabulary. This command does not activate query-cut
  execution.
- `ofarm.tenant-knowledge-position-storage.v0.1` and the database allocator
  own batch knowledge positions. Caller data and application code do not
  choose them.
- `ofarm.temporal-carrier-selection.intervention.v0.1` owns the exact
  intervention occurrence and execution-interval selection. The command
  cannot substitute another matrix, row, field, or timestamp.
- The frozen request, event, payload, authorization, promotion-trace, command
  result, and runtime-problem contracts own their existing shapes.
- Trusted `TenantBinding` owns tenant, authenticated principal, and bound
  party. Request identity is only compared with that authority.
- A separately reviewed production RuntimeBundle-selection authority must own
  the digest written on the batch and records. Request data cannot supply it.
- A separately reviewed production authorization provider must evaluate
  `ASSERT_OPERATION_CLAIM` at `DRAFT_PREPARATION`. Legacy policy code is not an
  alternate production authority.
- A trusted server clock resolved once after tenant binding owns the command
  evaluation instant used for generated evidence. Source event, execution,
  capture, assertion, record, and ingestion timestamps cannot replace it.
- This binding owns the exact command specialization, ordering, replay rule,
  result mapping, draft-only posture, and stop conditions.
- A future implementation may enforce these authorities but may not enlarge
  them.
- #192 retains sole authority over audit-runtime behavior. This contract adds
  none.

## State transitions

```text
BOUND
  -> admit exact source tuple
     -> not this command / no write
     -> exact replay / return prior result unchanged / no write
     -> conflicting replay / refuse / no write
     -> new request / allocate one governed batch
        -> evaluate authority
           -> deny or review-required / record result
           -> allow / select both valid-time carriers
              -> selected or refused / record draft and evidence
        -> commit once
```

Admission and replay checks occur before batch allocation. A new request
allocates exactly one batch before authorization or valid-time outcome is
known. Authorization denial, review-required disposition, and temporal
refusal therefore remain reconstructible in the same tenant transaction as
their source drafts and decision evidence.

The valid-time selector runs only after authorization returns `ALLOW`. A
denied or review-required caller cannot cause temporal interpretation.

There is no retry loop, nested governed batch, partial commit, or second
knowledge position. Any storage, identity, contract, evidence, or commit
failure rolls back the entire new-request batch.

## Idempotency

The idempotency key is the exact tuple:

```text
trusted tenant id
+ trusted bound party ref
+ COMMIT_OPERATION_CLAIM_DRAFT
+ request idempotencyKey
```

The request digest is the OFARM canonical digest of the admitted
`CommitIngressRequest`, `SemanticEventEnvelope`, and
`ExecutionRecordPayload` tuple. Replay equality requires both that digest and
the trusted RuntimeBundle digest to equal the prior committed claim.

- An exact replay returns the prior committed `CommitIngressResult` unchanged.
  It creates no batch, position, record, trace, result, or idempotency claim.
- A different source digest or RuntimeBundle digest is a conflicting replay.
  It refuses before batch allocation and creates no record or second
  idempotency claim.

This Phase A contract does not create a durable replay-attempt audit record.
Adding one would enter #192 or another separately approved audit boundary.
The existing `REPLAY_REUSED_RESULT` vocabulary is not removed, but this
specialization does not create a new result merely to report an exact replay.

## Valid-time carrier

On authorization `ALLOW`, the command calls only the approved closed
intervention selector with the admitted event and payload. The selector's
source-contract, matrix, row, field-path, discriminator, and window-meaning
identities are fixed by its reviewed binding artifact, never caller data.

The selector must return both carriers or refuse atomically:

- event `timeSemantics.eventTime` as an occurrence POINT with
  `EVENT_OCCURRENCE` meaning; and
- payload `effectiveTimeInterval` with
  `timeBasis=EXECUTION_INTERVAL` as a bounded interval with
  `STATE_OVERLAP` meaning.

The interval is non-empty and half-open:

```text
[start,end) where start < end
```

Consequently, a point is in the interval exactly when
`start <= point < end`; adjacent `[A,B)` and `[B,C)` intervals do not overlap.
Envelope `effectiveFrom` and `effectiveUntil` remain unsupported.

This command selects source carriers. It does not execute a caller-supplied
`ValidCut`, perform an AS_OF or WINDOW query, or persist a new temporal
selection artifact.

## Knowledge position

For a new request, `TenantUnitOfWork.begin_batch()` obtains one database-owned
tenant knowledge position `Kbatch`. The caller, command, authorization
provider, and valid-time selector cannot choose or override it.

The command's pre-state knowledge boundary is:

```text
Kbefore = Kbatch - 1
```

`Kbefore` is zero for the first tenant batch. Any database state consulted to
decide the command must be visible no later than `Kbefore`; records written in
the command's own batch cannot justify the command that writes them.

On commit, every batch member becomes visible together at `Kbatch`. On
rollback, neither the batch nor the candidate position is published. Positions
remain tenant-local and incomparable across tenants.

This command does not accept or execute a caller `KnowledgeCut`, expose a head
read, or implement historical reconstruction.

## Outcome rules

| Condition | Authorization | Valid-time selection | Durable command outcome |
|---|---|---|---|
| Exact replay | not evaluated | not evaluated | Return prior committed result unchanged; no write |
| Conflicting replay | not evaluated | not evaluated | Refuse before the command; no write |
| New request, authority denies | `DENY` | not evaluated | One refusal batch; `DENY` |
| New request, authority requires review or human approval | `REQUIRE_REVIEW` or `REQUIRE_HUMAN_APPROVAL` | not evaluated | One refusal batch; `REQUIRE_REVIEW` |
| New request, authority allows and selector refuses | `ALLOW` | refused | One safe unpromoted draft batch; `RETAIN_DRAFT` |
| New request, authority allows and selector succeeds | `ALLOW` | both carriers selected | One draft batch; `RETAIN_DRAFT` |

Selector refusal is not a success path. It may produce only the explicitly
defined safe `RETAIN_DRAFT` branch above. That retained draft must never become
accepted, promoted, materialized, qualified, published, output, or current
truth.

`REQUIRE_HUMAN_APPROVAL` maps to the existing command-result
`REQUIRE_REVIEW`; the frozen command-result contract has no separate human
approval outcome.

Until the runtime-problem registry gains separately governed temporal reason
codes, selector refusal uses existing `EVIDENCE_INSUFFICIENT` with specific
detail that cites ERRATA E-001. This is the already recorded interim handling,
not an informal amendment or a new reason code.

## Durable batch

Every new-request branch writes one atomic batch containing:

- the exact admitted command request, semantic event, and execution payload in
  the `draft` lane;
- one complete authorization request, result, and trace;
- one promotion trace whose gate sequence stops at the actual terminal gate;
  and
- one commit result.

Generated evidence uses the same trusted tenant, bound party, command
evaluation instant, governed operation, request identity, RuntimeBundle
digest, and batch provenance. The result and trace may report only
`RETAIN_DRAFT`, `DENY`, or `REQUIRE_REVIEW`.

The batch cannot contain an `AssertionRecord`, `ReviewDecision`,
`AcceptedEventConsequence`, derived materialization, output receipt, or any
artifact that presents the claim as accepted or current truth.

## Invariants

- **GCT-001 — Exact command.** Only the one schema-valid, fully linked source
  tuple named by this binding is admitted.
- **GCT-002 — Trusted identity.** Tenant, principal, party, RuntimeBundle,
  authorization provider, command evaluation instant, knowledge position, and
  valid-time binding are not caller-selectable.
- **GCT-003 — Closed temporal authority.** The command cannot select a matrix,
  row, source contract, field path, timestamp substitute, or window meaning.
- **GCT-004 — Independent axes.** Valid-time carriers never become knowledge
  positions; database positions and timestamps never become valid-time
  carriers.
- **GCT-005 — Half-open interval.** Every selected execution interval is
  non-empty `[start,end)`.
- **GCT-006 — Pre-state decision.** Command decisions use knowledge no later
  than `Kbatch - 1`.
- **GCT-007 — Whole-batch visibility.** New source drafts and decision evidence
  become visible together at one tenant position or not at all.
- **GCT-008 — Draft only.** No branch promotes, materializes, qualifies,
  publishes, or emits an in-force artifact.
- **GCT-009 — Default refusal and safe retention.** Unknown discriminator,
  identity mismatch, missing authority, or ungoverned outcome cannot be
  admitted or fall through. An unsupported temporal field or selector refusal
  may reach only the explicitly defined safe `RETAIN_DRAFT` branch after
  authorization `ALLOW`; that retained draft must never become accepted,
  promoted, materialized, qualified, published, output, or current truth.
- **GCT-010 — Replay before allocation.** Exact and conflicting replays consume
  no batch or knowledge position.
- **GCT-011 — Cross-bundle refusal.** A prior idempotency claim made under a
  different trusted RuntimeBundle is never reused.
- **GCT-012 — Complete evidence.** Every new-request batch contains all three
  authorization artifacts plus one promotion trace and one command result.
- **GCT-013 — Production firewall.** No legacy module, route, registry, or
  profile becomes an authority or dependency.
- **GCT-014 — Audit separation.** No replay-attempt or other #192 audit behavior
  is introduced.
- **GCT-015 — Candidate isolation.** This contract remains outside active
  production registries and RuntimeBundle selection.

## Required negative cases

Conformance must refuse or prove unsupported:

- a malformed source artifact or a changed source schema identity or digest;
- another commit class, event family, execution record class, record state,
  ingress channel, action class, action stage, or governed operation;
- an acting party different from the bound party, any acting agent, or any
  requested promotion target;
- missing, duplicate, additional, or mismatched event, payload, subject, actor,
  anchor, or target links;
- a caller-supplied tenant, principal, RuntimeBundle, knowledge position,
  matrix, row, binding, selector, field path, window meaning, or command
  evaluation instant;
- missing `eventTime`, missing execution bounds, wrong time basis, invalid UTC,
  empty or reversed interval, or envelope effective bounds;
- a selector result that is partial or differs from the reviewed binding;
- selector refusal producing anything other than the one safe unpromoted
  `RETAIN_DRAFT` batch, including any accepted, promoted, materialized,
  qualified, published, output, or current-truth state;
- authority `DENY`, `REQUIRE_REVIEW`, or `REQUIRE_HUMAN_APPROVAL` reaching
  valid-time selection;
- exact replay allocating a batch or writing evidence;
- a replay under different source or RuntimeBundle identity being treated as
  exact;
- any new-request result outside `RETAIN_DRAFT`, `DENY`, or
  `REQUIRE_REVIEW`;
- any batch member in the forbidden promotion, materialization, output, or
  audit classes; and
- any appearance of this candidate in an active contract directory,
  RuntimeBundle catalog, profile, active artifact set, capability manifest,
  route, or production import closure.

## Non-goals

This contract does not implement a command service, route, database change,
migration, storage adapter, RuntimeBundle or profile activation, authorization
provider, public refusal mapping, caller `ValidCut` or `KnowledgeCut`, current
state, historical or WINDOW query, correction or dispute behavior,
materialization, qualification, output, receipt, promotion, another command,
another ingress channel, another carrier row, legacy integration, or #192
behavior.

It does not amend any frozen active contract. It does not make the temporal
coordinate, carrier matrix, carrier selector, or this command active.

## Smallest coherent Phase A change

This boundary contains only:

- one exact inactive command-binding candidate;
- one exact candidate schema;
- this RFC;
- package manifest and ERRATA traceability; and
- focused conformance proving exact identity, decision completeness, and
  non-activation.

Code size is a warning signal. The later implementation should remain a small
state transition over existing trusted services. If it needs a broad
framework, generalized command family, route, registry, policy engine,
storage redesign, or output layer, the boundary has expanded and work stops.

## Verification

Verification must prove:

- complete Draft 2020-12 schema validity and exact schema-to-instance equality;
- exact candidate, prerequisite, source-contract, and evidence-contract
  identities and current file digests;
- exact admission rules, trusted-authority map, state transitions, replay
  equality, outcome table, batch membership, forbidden members, non-goals, and
  stop conditions;
- mutation of any command, route, authority, temporal, outcome, or activation
  field is refused by the exact schema;
- the approved temporal-coordinate, knowledge-position, and intervention
  selector prerequisites remain independently governed;
- the candidate is present only as `NEW_CANDIDATE` /
  `CANDIDATE_ARTIFACT`;
- no frozen active contract, database file, RuntimeBundle selection, profile,
  route, materialization, output, production semantic module, legacy module,
  or #192 file changes; and
- the package conformance gate and focused temporal governance tests pass.

## Stop conditions

Phase B command implementation must not start until separate review identifies
and approves:

1. the production authorization provider that owns
   `ASSERT_OPERATION_CLAIM` at `DRAFT_PREPARATION`; and
2. the production source of the trusted RuntimeBundle digest for this command
   and the approved temporal binding.

Implementation stops again if either authority cannot be connected without
changing an active registry, RuntimeBundle selection, profile, route, frozen
contract, database boundary, public refusal vocabulary, production semantic
surface, or #192 behavior. The required change must be proposed as a separate
prerequisite or stacked PR.

Current-state reads, historical views, WINDOW behavior, materialization, and
outputs remain blocked by their own later Phase A contracts and output-
governance prerequisites.
