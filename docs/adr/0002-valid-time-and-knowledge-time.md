# ADR 0002: Valid-time and knowledge-time semantics

**Status:** Accepted for implementation

**Decision class:** Package-local implementation architecture

**Date:** 2026-07-10

**Parent:** #167

**Depends on:** #168

**Primary implementation ticket:** #176

This ADR does not amend OFARM law, promote a contract, activate a profile, or
change a capability claim. It fixes the meanings that this implementation must
use when later storage, correction, materialization, replay, and output work is
implemented. The current runtime is not changed by this documentation-only
ticket.

## Decision

OFARM2 will use two independent temporal axes:

1. **Valid time** says when a domain fact applies in the represented world.
2. **Knowledge position** says which governed write batches were durably known
   to one tenant when an answer was produced.

A wall-clock timestamp is not a knowledge-order key. In particular,
`record_time`, `recordedAt`, `recordTime`, `acceptedAt`, `decidedAt`, capture
time, and ingestion time do not order knowledge.

A historical answer is defined only by a pair:

```text
(valid-time point or half-open window, tenant knowledge position)
```

The answer also pins the exact RuntimeBundle, code, database schema, policy,
reference inputs, and basis digests needed to reproduce it. A query that fixes
only one temporal axis is incomplete for historical or high-consequence use.

## Terms

| Term | Meaning |
| --- | --- |
| Valid instant | A timezone-aware UTC instant at which an event occurs or an observation applies. |
| Valid interval | A half-open UTC interval `[validFrom, validUntil)` during which a state fact applies. |
| Knowledge position | A tenant-scoped monotonic integer assigned to one committed governed write batch. |
| Governed operation | An accepted or refused command, review, import/activation, or read/authorization action that may produce durable authoritative or evidence-bearing state. |
| Governed write batch | One atomic transaction for exactly one tenant containing all durable writes caused by one governed operation. It may change domain truth or append only audit, authorization, or receipt evidence. |
| Valid cut | The valid instant or half-open valid window resolved for a query. |
| Knowledge cut | The greatest tenant knowledge position visible to a query. |
| Current-state read | Shorthand that resolves once to an explicit valid instant and knowledge cut; it is not a permanently floating `NOW`. |
| Replay | Re-evaluation using the same two cuts and the same immutable runtime/input identities. |

Knowledge positions are meaningful only inside one tenant. Position `42` for
tenant A has no ordering relationship to position `42` for tenant B.

Every durable write that can affect reconstruction, authorization, trace, or
proof belongs to exactly one tenant batch. This includes refusal audit logs,
scheduled import or activation decisions, reviews, disclosure decisions, and
read receipts even when no domain fact changes. A governed operation that
writes nothing durably receives no position.

An imported global blob may be stored as immutable content outside tenant
knowledge order, but it cannot affect a tenant answer until a tenant-scoped
activation or selection batch makes its identity visible to that tenant.
Cross-tenant operations publish independent per-tenant batches; they never
share or compare one position.

## Valid-time model

### State intervals

All state intervals use half-open bounds:

```text
[validFrom, validUntil)
```

- `validFrom` is inclusive.
- `validUntil` is exclusive.
- Missing `validUntil` means positive infinity.
- A state fact with temporal force must have a valid-time start. The runtime
  must not manufacture it from capture, ingestion, assertion, acceptance, or
  record time.
- `validUntil <= validFrom` is invalid.
- A point event is not encoded as an empty interval. It uses an explicit event
  or observation instant.

The canonical state-at predicate is:

```python
def state_at(fact, valid_at):
    return (
        fact.valid_from <= valid_at
        and (fact.valid_until is None or valid_at < fact.valid_until)
    )
```

The canonical state-overlap predicate is:

```python
def state_overlaps(fact, window_start, window_end):
    assert window_start < window_end
    return (
        fact.valid_from < window_end
        and (fact.valid_until is None or window_start < fact.valid_until)
    )
```

### Event instants and windows

An event window is also half-open:

```python
def event_in_window(event, window_start, window_end):
    assert window_start < window_end
    return window_start <= event.occurrence_time < window_end
```

A window query must state whether it asks for:

- state intervals that overlap the window; or
- event instants that occur within the window.

Those are different questions. An empty or reversed window is rejected rather
than treated as an empty successful result. Adjacent windows compose without a
duplicate at their shared boundary.

### Calendar dates

A calendar date is not an instant. A profile must supply the jurisdictional
timezone and the source rule for inclusive or exclusive end dates before a date
can become a UTC interval. The runtime must never guess by appending
`T00:00:00Z` or `T23:59:59Z`.

### Current state

`NOW` is request syntax, not durable temporal evidence. At the start of a
governed read, the runtime resolves it once and records the result, for example:

```json
{
  "validAt": "2026-07-10T12:34:56.123456Z",
  "knowledgePosition": 42
}
```

Every basis member, qualification, view, assembly, and receipt for that answer
uses the same resolved pair. Replay never asks the clock what `NOW` means again.

## Knowledge-time model

### Tenant-scoped monotonic positions

Every committed governed write batch receives one immutable tenant knowledge
position. All authoritative and evidence-bearing members emitted by that batch
share:

- `tenantId`;
- an immutable `governedBatchId`; and
- the same `knowledgePosition`.

This includes records, graph edges, gate/audit traces, review decisions,
promotion traces, receipts, and any durable dependency or output metadata
written in the transaction. There is no semantic order between members of the
same batch; dependencies use explicit references.

The allocator serializes the tenant's knowledge head for the lifetime of the
transaction. A later position cannot commit before an earlier position. The
initial allocator proposes `committedHead + 1` inside that transaction and
advances the head only in the atomic commit. A rollback publishes neither the
batch nor a position; its uncommitted candidate may be proposed again because
it never existed as a valid cut.

If an explicit restore/import design later advances the head across unused
integers, those gaps are permanently retired. A cut on a retired gap has the
same visible state as the greatest committed position below it, and no future
batch may fill any position at or below the committed head. A position exposed
by a committed batch is never reused. Therefore a previously valid cut can
never acquire new members later.

Stable identifiers may provide deterministic display ordering, but they never
select truth when valid times or decision times are equal.

### Atomic visibility

For tenant `T` and knowledge cut `K`, a record, edge, trace, or receipt is known
only when its governed batch has a committed position `<= K`.

A batch is visible all at once. A reader cannot observe some records from the
batch without its edges, decisions, traces, or other governed members. A failed
or cancelled transaction exposes none of them.

### Knowledge-cut validity

- A requested cut above the tenant's committed knowledge head fails closed.
- A requested gap below the head resolves to the previous committed state.
- Cross-tenant positions cannot be compared or reused as another tenant's cut.
- A diagnostic wall clock cannot be converted into a knowledge position by
  searching for the nearest row.

## Historical queries and replay

A historical point query pins:

```text
tenant + validAt + knowledgePosition
```

A historical window query pins:

```text
tenant + [windowStart, windowEnd) + window meaning + knowledgePosition
```

Both also bind:

- RuntimeBundle digest;
- application/code identity;
- database migration version and checksums;
- policy and active instance identities;
- reference-source identities and selected snapshots;
- canonical query/materialization/output plans; and
- immutable basis and result digests.

The historical knowledge cut applies transitively to reconstruction of tenant
truth. Filtering the starting consequence at `K` and then reading current
edges, reviews, disputes, historical authorization decisions, context,
references, or output metadata into that reconstructed content is forbidden.

Authorization to disclose or use the reconstructed answer is a separate,
request-time decision. Consistent with D12, sharing and authority are
re-evaluated against the tenant's current committed knowledge head for every
request. A grant that existed at historical cut `K` may explain why the original
action occurred, but it cannot authorize a new disclosure after it expires or
is revoked. The receipt records both decisions without conflating them:

- the historical content cut and the historical authority evidence used in the
  reconstruction; and
- the current disclosure/use authorization decision, decision trace, and
  current knowledge head at which it was evaluated.

The check and the release are one tenant-serialized operation, not a check-then-
act pair. Grant, revocation, and disclosure paths use the same tenant-scoped
release serialization guard. While holding it, the disclosure path re-reads the
committed head, evaluates current authority, durably commits its decision and
receipt batch, and hands the complete frozen artifact to the response sink. A
failed receipt commit releases nothing, and a revocation cannot commit between
the final check and that handoff.

This defines a total order: a handoff linearized before a later revocation is an
earlier authorized disclosure and cannot be retracted, while every handoff
linearized after the revocation is denied. Deferred/redeemable links and
streaming that outlives the guard are unsupported until they can reauthorize at
redemption or otherwise preserve the same ordering. The receipt must carry the
evaluated current head and its own governed batch position through an existing
immutable contract surface, or the contract stop condition below applies.

A later revocation can therefore deny a new read of unchanged historical
content. It does not rewrite the earlier content or a receipt proving that an
earlier disclosure was authorized when made.

Replay at the same two cuts and immutable inputs must reproduce the same
canonical historical basis, content/result, and content-qualification digests
even after later facts, corrections, disputes, or reference vintages arrive.
It can verify the bytes and digest of an output frozen by the original request.

A replay request does not inherit the original permission to release that
output. It performs a new current disclosure/use authorization evaluation. The
new authorization receipt or release wrapper may differ or deny release without
changing the reconstructed historical result or invalidating the old frozen
output's digest.

## Late arrival, future effect, and expiry

- A late-arriving fact is absent before its batch's knowledge position even when
  its valid time is in the past. It becomes visible for that past valid time at
  and after the batch position.
- A future-effective fact is known at its batch position but does not appear in
  current state before its valid-time start.
- A state fact is excluded at its exclusive `validUntil` boundary.
- Missing domain-valid time is a governed refusal when the claim requires it.
  Capture, ingestion, record, assertion, decision, or acceptance time cannot be
  substituted.

## Correction and supersession

Supersession operates on both axes without rewriting history:

1. The predecessor remains the answer at knowledge cuts before the correction
   batch.
2. The supersession edge and replacement set become visible together at the
   correction batch's position.
3. At and after that position, the replacement set is used for valid-time
   queries, including queries about the past.

A replacement batch emits the complete intended valid-time replacement:

- A pure correction may replace one interval with one corrected interval.
- A forward-effective successor emits any carry-forward slice needed to
  preserve the predecessor's earlier interval.
- A partial correction emits left, corrected, and right slices as applicable.
- Correcting a point event retires the old point and emits the corrected point.

The runtime does not perform implicit interval surgery. A correction with an
incomplete replacement set refuses rather than creating a hidden temporal hole.

## Dispute semantics

A dispute does not alter a fact's valid interval and does not remove the fact
from the append-only substrate.

- Before the dispute batch's knowledge position, the fact has its earlier
  dispute state.
- At and after that position, the fact remains visible and is marked disputed.
- High-consequence use refuses or qualifies according to the pinned policy.
- A later correction/supersession becomes visible at its own knowledge position
  and resolves the affected version according to the governed review policy.

This ADR refines only the temporal reconstruction described by
`docs/REVIEW_DISPUTE_SEMANTICS.md`. D20 and D21 and that document's settled
append-only REJECT and CONTEST state effects remain unchanged. Implementations
must read their state transitions together with this ADR's two-axis cuts; this
decision does not reopen or broadly supersede the earlier review decisions.

## Equal-time behavior

Equal valid times never mean "latest identifier wins."

- Non-exclusive facts may coexist when their governed semantics permit it.
- Mutually exclusive overlapping facts require explicit lineage or another
  governed resolution.
- An unresolved exclusive overlap is ambiguity and must refuse.
- Two mutually exclusive successors for the same interval in one batch are
  invalid.
- Equal diagnostic or decision timestamps do not order batches; knowledge
  positions do.

## Timestamp representation

- Timestamp inputs are RFC 3339 and timezone-aware.
- Aware non-UTC offsets may be accepted at a boundary, but are normalized before
  canonicalization, digesting, or persistence.
- Accepted timestamp precision is whole seconds through six fractional digits.
  Inputs with more than six fractional digits are rejected, never rounded or
  truncated differently by Python and PostgreSQL.
- RFC 3339's `-00:00` form is rejected because it denotes an unknown local
  offset, not a known timezone-aware instant.
- Leap-second values with seconds `60` are rejected. The runtime never lets
  Python and PostgreSQL normalize or reject them differently.
- Canonical persisted, digested, and output timestamps use UTC `Z` with exactly
  six fractional digits: `YYYY-MM-DDTHH:MM:SS.ffffffZ`.
- Naive timestamps are rejected. No parser may silently attach UTC.
- Instant comparison uses parsed instants, never strings.
- Calendar dates remain dates until a profile-owned rule converts them.

## Existing timestamp classification

This inventory classifies the semantic role of every current timestamp family.
Repeated occurrences of the same field in extracted schemas, candidate/draft
schemas, examples, manifests, or receipts inherit the classification below.
No existing timestamp is knowledge/order time. `knowledgePosition` is the only
field with that role.

### Domain-valid time

These fields describe when represented facts, events, states, or source
vintages apply:

- `AgronomicIdentityBinding.externalScheme.effectiveFrom/effectiveUntil`
- `AgronomicIdentityBinding.bindingValue.effectivePeriod.start/end`
- `AgronomicObservationContext.timeObject.instant/intervalStart/intervalEnd`
- `CropCycleIdentityPayload.startedAt/endedAt`
- `ExecutionRecordPayload.effectiveTimeInterval.start/end`
- `ExternalRegistryVerificationTrace.datesObserved.statusEffectiveFrom/statusEffectiveUntil`
- `InterventionIntentPayload.intendedTimeWindow.start/end`
- `MeasurementEvidence.calibration.calibratedAt/dueAt`
- `MeasurementEvidence.phenomenonTime.instant/intervalStart/intervalEnd`
- `MeasurementEvidence.procedureRef.effectiveAt`
- `NarrativeObservation.observedAt`
- `PartialExtent.timeObject.instant/intervalStart/intervalEnd`
- `PlannedIntervention.plannedWindowStart/plannedWindowEnd`
- `ReferenceSnapshot.effectiveFrom/effectiveUntil`
- `AcceptedEventConsequence.effectiveFrom/effectiveUntil`
- `AssertionRecord.occurrenceTime/effectiveFrom/effectiveUntil`
- `AuthorityGrant.validFrom/validUntil`
- `AuthorizationDecisionRequest.target.targetTime`
- `AuthorizationDecisionTrace.target.targetTime`
- `ContextSnapshot.evaluationTimePolicy.asOfTime/windowStart/windowEnd`
- `DelegationGrant.validFrom/validUntil`
- `IdentityLifecycleChange.effectiveFrom`
- `MaterializationBasis.evaluationTimePolicy.asOfTime/windowStart/windowEnd`
- `MaterializationRequest.evaluationTimePolicy.asOfTime/windowStart/windowEnd`
- `RevocationDecision.effectiveFrom`
- `RoleAssignment.validFrom/validUntil`
- `SemanticEventEnvelope.timeSemantics.observationTime/eventTime/effectiveFrom/effectiveUntil`
- `SharingGrant.validFrom/validUntil`
- `PackActivationSet.timeContext.asOfTime/windowStart/windowEnd`
- `QueryPlanIR.normalizedTarget.evaluationTimePolicy.*`
- `QuerySpecification` AS_OF and WINDOW fields
- `ResultQualificationEnvelope.asOf`
- draft `MaterializationKey.evaluationTimePolicy.*`
- `ProfileRouteRecord.effective_from/effective_until`

Source authorisation issue/validity dates are domain calendar dates. They stay
dates until profile rules establish timezone and inclusivity.

### Decision or governance-act time

These fields say when an assertion, plan, review, activation, evaluation, or
governance act was made. They do not determine knowledge visibility:

- `AgronomicCodeBindingProfile.issuedAt`
- `AgronomicIdentityBinding.createdAt`
- `InterventionIntentPayload.createdAt`
- `PlannedIntervention.plannedAt`
- `AcceptedEventConsequence.acceptedAt`
- `AssertionRecord.assertedAt`
- `AuthorizationDecisionResult.evaluatedAt`
- `AuthorizationDecisionTrace.evaluatedAt`
- `IdentityLifecycleChange.evaluatedAt`
- `MaterializationResult.evaluatedAt`
- `PromotionTrace.evaluatedAt`
- `ReviewDecision.decidedAt`
- `RevocationDecision.decidedAt`
- `SemanticEventEnvelope.timeSemantics.assertionTime/decisionTime`
- `PackActivationSet.evaluatedAt`
- `PublicationAssemblyResult.evaluatedAt`
- draft `ExplainableCurrentStateCapabilityClaim.declaredAt`
- draft `InvalidationEvaluationTrace.decisionTime`
- draft `RuntimeQueryMixProfile.declaredAt`

### Capture, access, or receipt time

These fields describe when material was captured, accessed, requested, or
received. They are provenance, not a fallback valid time:

- `AgronomicIdentityBinding.externalScheme.accessDate`
- `ExecutionRecordPayload.capturedAt`
- `ExecutionRecordPayload.sourcePayload.sourceRecordTime`
- `ExternalRegistryVerificationTrace.datesObserved.accessedAt/sourceUpdatedAt/sourceAccessDate`
- `MeasurementEvidence.source.sourceCapturedAt`
- `MeasurementEvidence.resultTime` (result availability, never phenomenon time)
- `CommitIngressRequest.ingestedAt`
- `EvidenceRecord.capturedAt`
- `AuthorizationDecisionRequest.requestedAt`
- `MaterializationRequest.requestedAt`
- `PublicationAssemblyRequest.requestedAt`
- draft `MaterializationFreshnessVector.observedAt`
- draft `TraceExpansionRequest.requestedAt`
- source/example `capturedAt` and source-access dates

An external `sourceUpdatedAt` remains observed provenance unless a profile
explicitly establishes it as a valid-time basis.

### Diagnostic, generated, output, or runtime time

These fields aid trace, operations, or presentation. They do not order truth:

- `AppliedResourceIdentityPayload.recordedAt`
- `CropCycleIdentityPayload.recordedAt`
- `EquipmentIdentityPayload.recordedAt`
- `FarmIdentityPayload.recordedAt`
- `FieldIdentityPayload.recordedAt`
- `ExternalRegistryVerificationTrace.createdAt`
- `PartialExtent.createdAt`
- `EvidenceRecord.recordedAt`
- `IdentityRecord.createdAt/recordedAt`
- `Party.recordedAt`
- `SemanticEventEnvelope.timeSemantics.recordTime`
- `CommitIngressResult.processedAt`
- `ContextSnapshot.generatedAt`
- `EvidenceSufficiencyCase.generatedAt`
- `MaterializationSnapshot.generatedAt`
- `ActiveArtifactSet.generatedAt`
- `CapabilityManifest.publishedAt`
- `DocumentAssemblyMetadata.generatedAt/frozenAt`
- `PassportViewMetadata.generatedAt`
- `ResultQualificationEnvelope.qualifiedAt`
- draft `RuntimeStorageAmplificationReport.measuredAt`
- draft `RuntimeMaterializationBenchmarkRun.executedAt`
- draft `MaterializationCostProfile.measuredAt`
- draft `MaterializationDependencyIndex.generatedAt`
- draft `TraceExpansionResult.generatedAt`
- SQL `kernel_record.record_time`
- SQL `kernel_edge.record_time`
- SQL `kernel_gate_log.record_time`
- SQL `kernel_idempotency.record_time`
- SQL `derived_materialization.generated_at`
- SQL `derived_dependency_index.generated_at`
- SQL `reference_snapshot_data.record_time`
- SQL `runtime_trace.record_time`
- SQL `export_artifact.record_time`
- package/source-manifest/conformance `generated*`, `checked*`,
  `canonicalized*`, `executedAt`, and publication metadata

`IdentityRecord.createdAt` is object-construction time. It does not establish
the real-world origin of a farm, field, equipment item, or other identity;
domain existence comes from explicit lifecycle/effective facts.

## Executable boundary examples

| Case | Query or cut | Required result |
| --- | --- | --- |
| State `[10:00, 11:00)` at `10:00` | point | Included. |
| State `[10:00, 11:00)` at `11:00` | point | Excluded. |
| Event at `11:00`, window `[10:00, 11:00)` | event window | Excluded. |
| Event at `11:00`, window `[11:00, 12:00)` | event window | Included. |
| Window `[10:00, 10:00)` | any | Reject as empty. |
| K10 late fact valid yesterday | yesterday at K9 | Absent. |
| K10 late fact valid yesterday | yesterday at K10 | Present. |
| K11 future fact valid tomorrow | today at K11 | Absent. |
| K11 future fact valid tomorrow | tomorrow at K11 | Present. |
| Fact expires at `12:00` | `11:59:59.999999` | Present. |
| Same fact | `12:00` | Absent. |
| K20 old value; K21 correction | past at K20 | Old value. |
| Same correction history | past at K21 | Corrected replacement set. |
| K30 dispute | valid point at K29 | Earlier clean dispute state. |
| Same dispute | valid point at K30 | Visible and disputed. |
| Whole batch at K40 | cut K39 | No emitted member. |
| Whole batch at K40 | cut K40 | Every emitted member. |
| Candidate K41 rolls back while head is K40 | cut K41 before another commit | Refuse as above head; no K41 was published. |
| Next serialized batch commits after that rollback | allocated position | It may become K41 because the rolled-back candidate was never a valid position. |
| Imported head K51 permanently retires unused K50 | later write attempting K50 | Refuse; no position at or below the head can be filled later. |
| Equal wall clocks in two batches | any | Knowledge positions decide visibility. |
| Exclusive overlap without lineage | any | Ambiguity and refusal. |
| Missing event/effective time with capture time | any | Refuse; no substitution. |
| Naive `2026-07-10T12:00:00` | parse | Reject. |
| Seven fractional digits | parse | Reject; never truncate or round. |
| Unknown offset `2026-07-10T12:00:00-00:00` | parse | Reject; the offset is not known. |
| Leap second `2026-12-31T23:59:60Z` | parse | Reject; no parser-specific normalization. |
| Historical content at K20; sharing revoked at K30 | new read at head K30 | Reconstruct content at K20, but current disclosure authorization denies release. |
| Disclosure check at K29 races a revocation at K30 | serialized release | Whichever acquires the tenant release guard first determines the order; no check at K29 can hand off after K30 commits. |

Replay acceptance test: materialize at `(validAt=V, knowledgePosition=K)`,
append later corrections, disputes, and a sharing revocation, then replay at the
same pair. Canonical historical basis, content/result, and content-qualification
digests must equal the original, and the original frozen output digest remains
verifiable. The new request's current authorization receipt must reflect the
revocation and deny a new release; it is not expected to equal the original
authorization receipt.

## Current implementation contradictions

The implementation ticket must address these known contradictions; this ADR
does not silently bless current behavior:

1. `Store.in_force_consequences(as_of=...)` uses one `as_of` value first as a
   SQL `record_time` knowledge filter and then as a domain-effective filter.
2. PostgreSQL `now()` is transaction-start time, not commit order. Current SQL
   `record_time` is neither monotonic nor tenant-scoped.
3. `context.parse_ts()` and authority parsing attach UTC to naive values.
4. Ingress, temporal validation, reverification, and materialization paths can
   substitute capture, ingestion, or acceptance time when domain time is absent.
5. Current-state consequence and identity reads do not consistently enforce
   `effectiveFrom/effectiveUntil`; future-effective and expired facts can enter
   a current answer.
6. WINDOW selection is closed at both ends and accepts empty windows.
7. Reference-snapshot equal-time ties can use lexicographic identifiers while
   other context selection refuses the tie.
8. Context history treats generated/decision timestamps as domain-effective
   time in places, including the lifecycle debt recorded by ERRATA E-007.
9. `NOW` can remain literal in durable keys and receipts rather than recording
   the resolved two-axis cut.
10. Qualification and output annex paths cannot consistently bind a knowledge
    cut and may read current disputes or claims into historical answers.
11. Freshness and invalidation use `max(record_time)` and comparisons against
    generated wall clocks.
12. Historical graph traversal is not transitively cut-aware.

## Contract and implementation stop condition

The relevant shipped JSON contracts are closed and do not currently expose a
tenant knowledge position on ContextSnapshot, MaterializationBasis,
ReviewDecision, qualification, and output receipts.

The historical-content cut and the separate current disclosure/use decision
must both be immutable and digest-bound in the resulting receipt. If the
existing receipt and authorization-trace surfaces cannot express both without
semantic distortion, that is the same governance stop.

#176 must not hide the knowledge cut in a mutable relational annotation or
invent an unreviewed field. It must either:

- use an already-governed immutable, digest-bound contract surface that can
  carry both cuts without semantic distortion; or
- stop and open the versioned candidate-contract/RFC/ERRATA governance path.

This is a design stop, not permission to edit `reference/**`, promote a draft,
or weaken replay evidence.

## Alternatives rejected

| Alternative | Reason rejected |
| --- | --- |
| One `asOf` timestamp for both axes | Collapses late arrival, correction knowledge, and valid-world state. |
| Wall clock or SQL `record_time` as knowledge order | Not tenant-scoped, not monotonic commit order, and ambiguous under concurrency. |
| Capture/ingestion time as missing valid time | Turns transport provenance into a domain claim. |
| Inclusive interval ends | Adjacent windows duplicate boundary facts and do not compose. |
| Identifier tie-break for exclusive facts | Makes arbitrary lexical order into hidden truth. |
| Floating `NOW` in receipts | Replay after time or knowledge advances cannot reproduce the original cut. |
| Mutable temporal sidecar | Breaks immutable, digest-bound replay evidence. |

## Verification plan for #176 and dependent tickets

At minimum, executable verification must cover:

- schema/SQL timestamp inventory coverage;
- point and window boundaries, including adjacent windows;
- UTC normalization plus naive, unknown-offset, and leap-second rejection;
- same-position whole-batch visibility;
- refused commands, imports/activations, reviews, and read receipts receiving
  positions when they write durable evidence;
- rollback, retired-gap immutability, and concurrent monotonic allocation;
- cross-tenant non-comparability;
- late arrival, future effect, and expiry;
- correction/supersession replacement sets;
- dispute state before and after its knowledge position;
- equal-wall-clock and equal-valid-time ambiguity;
- missing-domain-time refusal;
- transitive cut-aware graph, context, authority, and reference reads;
- current disclosure denial after a historical grant is revoked;
- concurrent revocation/disclosure serialization with no check-to-release gap;
- reconstruction replay after later changes with identical historical content
  digests, plus an independently current disclosure decision; and
- output annexes and qualifications using the same pinned cuts.

## Acceptance-criteria trace

| Issue #170 criterion | ADR section |
| --- | --- |
| Interval inclusivity and point/window/current reads | Valid-time model; Current state |
| Tenant monotonic position and whole write batch | Knowledge-time model |
| Every existing timestamp classified | Existing timestamp classification |
| Late/future/expiry/correction/supersession/dispute/equal-time behavior | Dedicated behavior sections; examples |
| UTC-aware representation and naive rejection | Timestamp representation |
| Historical query pins both axes; replay proves same cut | Historical queries and replay |
| No capture/ingestion substitution | Late arrival section; current contradictions |
| Executable examples and boundary cases | Executable boundary examples; verification plan |

## Consequences

- #176 owns the storage and query implementation of these meanings.
- #170 changes no runtime behavior.
- #171 supplies the immutable RuntimeBundle identity that historical receipts
  must pin.
- #181 and #182 must use the same valid and knowledge cuts for materialization,
  qualification, and persisted output assemblies.
- #184 must keep semantic references and graph traversal cut-aware.
- Existing single-axis behavior remains non-authoritative technical debt until
  the implementation and contract stop conditions are resolved.
