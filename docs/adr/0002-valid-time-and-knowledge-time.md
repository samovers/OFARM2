# ADR 0002: Valid-time and knowledge-time semantics

**Status:** Accepted for implementation

**Decision class:** Package-local implementation architecture

**Date:** 2026-07-10

**Parent:** #167

**Depends on:** #168

**Primary implementation ticket:** #176

**Required design and implementation coordination:** #169, #172, #173, #174,
#177, #181, and #182

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

After trusted tenant binding, every durable write that can affect tenant
reconstruction, authorization, trace, or proof belongs to exactly one tenant
batch. This includes refusal audit logs, scheduled import or activation
decisions, reviews, disclosure decisions, and read receipts even when no domain
fact changes. A governed operation that writes nothing durably receives no
position.

An imported global blob may be stored as immutable content outside tenant
knowledge order, but it cannot affect a tenant answer until a tenant-scoped
activation or selection batch makes its identity visible to that tenant.
Cross-tenant operations publish independent per-tenant batches; they never
share or compare one position.

### Pre-tenant operational security audit

Tenant knowledge ordering begins only after the hardened database binder has
verified a transaction-bound `TenantCapability`, its immutable binding version
and lifecycle head, the exact immutable tenant-registry digest and pinned ACTIVE
`ofarm.party.v0.1` record-kind identity/record identity/schema digest/payload
digest, and has installed the resulting
`TenantBinding` in protected transaction context. The authentication boundary only mints the
capability. Missing or malformed credentials, verifier failures, unknown or
revoked principals, immutable registry/Party mismatch, binder or actor-binding
failures, and routing failures before successful binder completion are not
tenant facts and cannot lawfully enter a tenant batch. V1 has no mutable tenant
or Party eligibility transition; access cessation uses the principal-binding
lifecycle defined by ADR 0001.

Such failures enter a separate append-only operational security-audit lane that
is outside every tenant's truth, reconstruction, and knowledge head. A
pre-tenant event:

- receives no tenant identifier, governed tenant batch, or tenant knowledge
  position;
- is attributed only from trusted server/verifier context, never from a tenant,
  farm, party, role, header, token claim, or body field supplied by the request;
- never falls back to a default tenant;
- records only a server-generated event identifier, diagnostic time, safe reason
  class and component, protected correlation data, and redacted or digested
  evidence needed for security operations; and
- stores no credential, bearer token, secret, or unredacted attacker-controlled
  identity material.

The lane is globally operational, separately access-controlled, and never read
as tenant history. It is not an exception inside tenant-scoped
`kernel_gate_log`, `runtime_trace`, or another tenant relation. Once a trusted
binding exists, a durable refusal belongs only to that bound tenant's governed
batch and receives that tenant's position.

#176 must stop rather than invent this lane or reuse a tenant table. ADR 0001
classifies the separate bounded audit service and freezes its trust, event,
access, retention, redaction, and failure boundaries. #172 owns fail-closed
authentication outcomes, #173 owns the binding boundary, #174 owns the
classified PostgreSQL storage/provisioning slice, and #192 owns the isolated
client, all producer integrations, delivery/health behavior, security-
operations execution, and end-to-end verification. None may move pre-tenant
evidence into tenant history.
Persistence of a separate pre-tenant security event does not make a refused
tenant transaction partially commit: the attempted tenant batch still rolls
back as a unit.

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

### Governed carrier and window-meaning matrix

Every temporal selection step must bind one authoritative valid-time carrier.
Every WINDOW selection step must additionally bind one window meaning. The two
required WINDOW meanings are:

- `EVENT_OCCURRENCE`: select an authoritative point instant with
  `windowStart <= instant < windowEnd`; and
- `STATE_OVERLAP`: select an authoritative interval with the overlap predicate
  above.

These names state required candidate-contract semantics; they do not amend a
shipped enum. A point/AS_OF step applies its selected carrier at the exact
`validAt`; it does not carry a WINDOW meaning. References to `EVENT_OCCURRENCE`
and `STATE_OVERLAP` in the matrix apply when that carrier is selected by a
WINDOW. A heterogeneous assembly declares the carrier for every selection step
and the meaning for every WINDOW step. It cannot inherit one undocumented
query-wide convention.

| Record or event family | Authoritative valid-time carrier | Allowed secondary time and consistency rule | Window/refusal rule |
| --- | --- | --- | --- |
| `StructureEvent` | Envelope `eventTime` for the change act; `effectiveFrom/effectiveUntil` for resulting state. | `assertionTime` and `recordTime` remain decision/diagnostic data. A payload lifecycle bound describing the same state must equal the normalized envelope bound. | The act uses `EVENT_OCCURRENCE`; resulting state uses `STATE_OVERLAP`. Missing or conflicting required carriers refuse. |
| `ObservationEvent` | Envelope `observationTime` for a point observation; the governed payload's phenomenon/time-object interval for an interval observation. | `eventTime` is allowed only for a distinct source act. If it purports to be the observation instant it must equal `observationTime`. | Point observations use `EVENT_OCCURRENCE`; interval observations use `STATE_OVERLAP`. Ambiguous point-versus-interval posture refuses. |
| `OccurrenceEvent` | Envelope `eventTime`. | `assertionTime` and `recordTime` do not select the occurrence. | Uses `EVENT_OCCURRENCE`; absent `eventTime` refuses. |
| `InterventionEvent` | Envelope `eventTime` for the intervention occurrence; `ExecutionRecordPayload.effectiveTimeInterval` for an execution span only when `timeBasis` is the governed `EXECUTION_INTERVAL`. | Capture, assertion, and record times remain provenance. `PRESCRIPTION_WINDOW`, `PLANNED_WINDOW`, `OBSERVED_INTERVAL`, or `EFFECTIVE_INTERVAL` may be used only by a separately governed carrier rule for that distinct meaning. When envelope effective bounds describe the same span, they must equal the payload bounds. | A point act uses `EVENT_OCCURRENCE`; a governed execution span uses `STATE_OVERLAP`. Absent, `UNKNOWN`, planned/prescription, or otherwise incompatible basis refuses as execution validity. No capture-time fallback. |
| `MaterialEvent` | Envelope `eventTime` for the material act; explicit effective bounds for resulting custody or state. | Secondary provenance fields are allowed only for their named meanings. Duplicate representations of one bound must match. | The act uses `EVENT_OCCURRENCE`; resulting state uses `STATE_OVERLAP`. Unclassified material time refuses. |
| `EvidenceEvent` | Envelope `eventTime` for the governed capture, issue, receipt, or signing act. | `capturedAt`, `resultTime`, source-access time, and `recordTime` remain provenance unless a governed profile rule explicitly makes one the act time and the envelope records the same instant. | Uses `EVENT_OCCURRENCE`; the runtime never silently promotes capture or receipt provenance into valid time. |
| `GovernanceEvent` | Envelope `decisionTime`; an independently effective outcome uses explicit `effectiveFrom/effectiveUntil`. | Decision-record fields such as `ReviewDecision.decidedAt` must equal envelope `decisionTime` when they describe the same act. | The act uses `EVENT_OCCURRENCE`; an effective state uses `STATE_OVERLAP`. Decision time never substitutes for missing effect. |
| `AssertionRecord` | `occurrenceTime` for a point/event claim; `effectiveFrom/effectiveUntil` for a state claim. | `assertedAt` is assertion-act time only. When carried by an envelope, corresponding occurrence/effective values must match after normalization. | Point claims use `EVENT_OCCURRENCE`; state claims use `STATE_OVERLAP`. A claim that needs valid time and supplies neither refuses. |
| `AcceptedEventConsequence` | `effectiveFrom/effectiveUntil` for state applicability; the immutable source event's classified carrier for an event-occurrence view. | `acceptedAt` is the acceptance act and never selects domain validity. Source and consequence bounds that claim the same state must match. | State selection uses `STATE_OVERLAP`; event selection uses the source carrier and `EVENT_OCCURRENCE`. No `acceptedAt` fallback. |
| Review and governance records | `ReviewDecision.decidedAt` or the record's governed decision field for the act; explicit effective bounds for a separately effective outcome. | A linked `GovernanceEvent.decisionTime` must match the record's normalized decision time. | Decision-act views use `EVENT_OCCURRENCE`; outcome-state views use `STATE_OVERLAP`. |
| Point-observation payloads | `MeasurementEvidence.phenomenonTime.instant` or `AgronomicObservationContext.phenomenonTime.instant`, with `timeType=INSTANT` and a present, governed `timeBasis` compatible with the selected observation meaning. `OBSERVED_TIME` and `SAMPLE_TIME` may qualify for their named meanings; `ESTIMATED_TIME` requires an explicit policy and qualification. | `resultTime`, `createdAt`, `generatedAt`, capture fields, and a phenomenon time whose basis is `RESULT_TIME` or `RECORD_TIME` are secondary and never valid carriers. Equivalent point fields must match. | A WINDOW view uses `EVENT_OCCURRENCE`; absent or incompatible basis, a mismatched shape, or multiple unequal candidate instants refuses. |
| `PartialExtent` temporal applicability | `temporalApplicability.instant` for a governed point-applicability view, or `intervalStart/intervalEnd` for a governed interval-applicability view, only when `timeType`, `timeBasis`, extent role, and selected use are compatible. | `OBSERVED_TIME`, `SAMPLE_TIME`, `PRESCRIPTION_WINDOW`, `EXECUTION_INTERVAL`, `DAMAGE_WINDOW`, and `REPLANT_WINDOW` retain only their named meanings. `RECORD_TIME` is never a valid carrier; `ESTIMATED_TIME` requires explicit policy and qualification. | A point WINDOW view uses `EVENT_OCCURRENCE`; an interval WINDOW view uses `STATE_OVERLAP`. Absent or incompatible basis, mismatched instant/interval shape, or contradictory values refuses. |
| Interval state or interval observation | The record's explicit start/end pair, with an open end only where that contract permits it. A time object must declare an interval-compatible `timeType` and, where exposed, a present `timeBasis` compatible with the selected state or observation meaning. | Creation, generation, assertion, decision, result, and record times remain secondary. A `RESULT_TIME` or `RECORD_TIME` basis never supplies domain validity; an estimated basis requires explicit policy and qualification. Equivalent bounds must match. | A WINDOW view uses `STATE_OVERLAP`; incompatible basis, incomplete, empty, reversed, shape-mismatched, or contradictory intervals refuse. |
| Pending/disputed annex entry | The underlying assertion or consequence carrier selected by the applicable row above. Dispute state is reconstructed at the tenant knowledge cut. | Review/decision time explains the annex state but does not replace the underlying valid carrier. | Uses the underlying carrier's meaning. An unclassified entry blocks high-consequence freeze rather than being silently included or omitted. |
| `EvidenceSufficiencyCase` | Inherits the exact valid cut, carrier selections, and per-step meanings of its governed basis. | `generatedAt` is diagnostic and never a valid carrier. | It cannot widen or reinterpret the basis window. Missing inheritance blocks use. |

Secondary fields remain allowed only for their distinct named meanings. If two
fields claim the same instant or interval bound, their normalized values must
match. A missing, contradictory, or semantically unclassified carrier refuses
commit or high-consequence assembly. The runtime never falls back to capture,
ingestion, assertion, acceptance, decision, record, generation, or identifier
order.

The authoritative carrier selector is always immutable and digest-bound; a
WINDOW step's meaning is too. Query specification chooses the carrier and, for
WINDOW, the meaning. The plan preserves every applicable value; requests,
context, basis, keys, results, qualification, and output receipts carry them
without reinterpretation. The shipped contracts do not yet provide those
selector/meaning surfaces, so the stop condition below applies.

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

Every historical basis member, stable content qualification, content view, and
assembly uses the same resolved pair. A release decision and receipt also bind
that pair, plus the two request-time positions defined below. Replay never asks
the clock what `NOW` means again.

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

A position exposed by a committed batch is never reused, even if the database
that stored it is later lost. Only a future #193 recovery design with an
external non-rewindable witness may advance a recovered head across skipped
integers. Every such gap is permanently retired: a cut on it has the same
visible state as the greatest committed position below it, and no future batch
may fill any position at or below the witnessed high-water mark. V1 has no such
witness or recovery path. Therefore a previously valid cut can never acquire
new or different members later.

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

### Recovery boundary

Only an uncommitted candidate rolled back by its allocating transaction may be
proposed again. A committed position remains consumed forever, including when
its rows are absent from an older backup.

V1 provides no tenant-service backup restore, point-in-time or snapshot
promotion, database logical restore, or tenant-history logical import. A
restored, copied, imported, forked, or provenance-unknown database cannot serve
governed traffic merely because its schema and application build match. It has
no V1 recovery-readiness path. An ordinary domain import is different: it
enters through a governed command and publishes new batches at new positions.

#193 must distinguish recovery of the whole shared tenant service from a
tenant-specific logical history operation and must reconcile the external
knowledge high-water mark, all authorization-relevant heads, idempotency and
release receipts, outbox/delivery state, and already released outputs. Until
that design and implementation exist, neither form of history recovery is
supported and destructive migrations are forbidden by ADR 0001.

### Prototype-data transition

Nothing is deployed. Consistent with the #169 migration architecture, #174
drops and recreates development and conformance databases from a proven-empty
target under the reviewed initial migration. Current prototype rows are
re-emitted through governed batches where fixtures remain needed; they are not
backfilled in place.

`record_time`, equal timestamps, nearby timestamps, insertion order, and current
transaction grouping must never be used to infer a historical batch identity or
knowledge position. If any non-disposable data is discovered before that
rebuild, implementation stops for an explicit loss-disclosing genesis-import
decision. Such a decision must state what history cannot be recovered and assign
new governed batches without pretending to reconstruct unknown historical
atomicity or order.

## Historical queries and replay

A historical point query pins:

```text
tenant + validAt + canonical per-step carrier map + Kcontent
```

A historical window query pins:

```text
tenant + [windowStart, windowEnd)
       + canonical per-step {carrier selector, window meaning} map
       + Kcontent
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

### Three named knowledge positions

Historical reconstruction and a later release use three distinct tenant
positions:

1. **`contentKnowledgeCut` (`Kcontent`)** is the historical knowledge cut used
   with the valid cut to reconstruct the basis, content/result, and stable
   content qualification.
2. **`releaseAuthorizationCut` (`Kauth`)** is the tenant's current committed head
   re-read under the release serialization guard for this request's authority,
   revocation, current-use, permission, and redaction evaluation at the resolved
   request-time instant below.
3. **`releaseReceiptPosition` (`Kreceipt`)** is the position allocated to the
   durable batch containing that release decision, trace, wrapper metadata, and
   receipt. Evaluation at `Kauth` does not see its own `Kreceipt` batch.

**`releaseEvaluationAt`** is the exact canonical UTC valid-time instant resolved
and rechecked at the end of the guarded evaluation for current validity, expiry,
staleness, and other time-derived release/use rules. It is not a fourth
knowledge position. It is immutable and digest-bound with the three positions.

For an allowed release, the atomic `Kreceipt` commit also writes the exact
wrapper to a trusted durable response-sink/outbox enqueue. That commit/enqueue is
the release linearization point. The implementation rechecks every relevant
effective/expiry boundary immediately before it; a boundary crossed before the
commit rolls the batch back and restarts with a new instant and `Kauth`. A
boundary crossed after the commit is ordered after the already-authorized
release and cannot retract it. If receipt and enqueue cannot commit atomically,
release is unsupported. The receipt proves the authorized durable enqueue;
successful transport delivery requires separate evidence if it is claimed.

These are required semantic fields for the versioned contract-governance work
below, not permission to add unreviewed properties to a shipped contract.

### Stable content qualification and current release/use decision

Content qualification is part of historical reconstruction. It describes only
the content and reliance posture evaluated at the same valid cut, `Kcontent`,
immutable basis, RuntimeBundle, and policy inputs as the content. It may carry
historical truth, candidate, dispute, staleness, evidence-sufficiency, and
data-absence posture. Later facts, disputes, corrections, grants, revocations,
or requests do not mutate its bytes or digest.

Request-time release/use qualification, permission, and redaction are a separate
decision. It evaluates current authority plus any later supersession, dispute,
staleness, or other governed current-use prohibition without changing the
historical qualification. It owns current `authorityLevel`, `permissionClass`,
`highConsequenceUseAllowed`, allowed/blocked use classes, redactions, and current
authorization/use traces. Those fields cannot enter the stable content
qualification. In particular, the current closed `ResultQualificationEnvelope`
mixes both responsibilities and cannot serve as either new surface without a
versioned split.

The binding and digest rules are:

| Evidence or digest | Must bind | Must not bind or imply |
| --- | --- | --- |
| Historical basis and content/result digest | Tenant, exact valid cut, canonical per-step carrier map and applicable WINDOW meanings, `Kcontent`, RuntimeBundle and other immutable inputs, canonical plan, and basis. | `Kauth`, `Kreceipt`, or a later request's permission/redaction result. |
| `contentQualificationDigest` | Canonical content-qualification bytes, content/result digest, exact valid cut, per-step carrier map, applicable WINDOW meanings, `Kcontent`, immutable qualification policy and basis digests. | Current grants, revocations, principal, permission classes, redactions, `Kauth`, or `Kreceipt`. |
| `releaseAuthorizationDigest` | Exact content/result and content-qualification digests, `Kcontent`, `Kauth`, `releaseEvaluationAt`, authenticated principal and binding version, current authority/revocation/current-use evidence and policy, decision outcome, and redaction plan. | `Kreceipt`, a floating head or clock, mutable target reference, or the later receipt payload. Its persisted record envelope is additionally bound to the `Kreceipt` batch. |
| Allowed-release wrapper digest | Exact released or redacted bytes, content/result, content-qualification, and release-authorization digests, all three positions, `releaseEvaluationAt`, and the preallocated receipt identifier. | The receipt digest itself, which would create a digest cycle. |
| Release receipt digest | Outcome, all three positions, `releaseEvaluationAt`, content/result, content-qualification, and release-authorization digests, plus the allowed-release wrapper and durable enqueue identity/digest when the outcome is allow. | A wrapper, enqueue, or handoff on denial. |

Authorization and current suitability to disclose or use the reconstructed
answer are therefore a separate request-time decision. Consistent with D12,
sharing, authority, and current-use prohibitions are re-evaluated at `Kauth` and
`releaseEvaluationAt` for every request. A grant or clean dispute/staleness
posture that existed at `Kcontent` may explain the original action, but it cannot
authorize or qualify a new use after later revocation, supersession, dispute,
staleness, or time-derived expiry.

The check and release are one tenant-serialized operation, not a check-then-act
pair. Every governed writer whose commit can change release/use posture shares
the same tenant-scoped release serialization guard. This includes grant,
revocation, dispute/resolution, correction/supersession, invalidation/staleness,
applicable activation/policy/reference changes, and disclosure paths. While
holding it, the disclosure path re-reads `Kauth`, resolves
`releaseEvaluationAt`, evaluates current authority/use posture, preallocates
`Kreceipt`, constructs the wrapper where allowed, durably commits the
decision/trace/receipt and atomic durable response-sink enqueue at that position.
A failed commit or a time boundary crossed before it releases nothing, and no
release-relevant writer can commit between the final check and the release
linearization point. Delivery after that point executes the already-ordered
release rather than creating a new authorization event.

This defines a total order: a release commit/enqueue linearized before a later
release-relevant change is an earlier authorized release and cannot be
retracted, while a release linearized after that change is denied.
Deferred/redeemable links and streaming that are not the exact durably enqueued
bytes are unsupported until they can reauthorize at redemption or otherwise
preserve the same ordering.

A later revocation can therefore deny a new read of unchanged historical
content. It does not rewrite the earlier content qualification or a receipt
proving that an earlier disclosure was authorized when made.

Replay at the same valid cut, `Kcontent`, and immutable inputs must reproduce the
same canonical historical basis, content/result, and content-qualification
digests even after later facts, corrections, disputes, or reference vintages
arrive. It can verify the bytes and digest of an output frozen by the original
request.

A replay request does not inherit the original permission to release that
output. It evaluates a new `Kauth` and commits a new `Kreceipt`. Its release
authorization, wrapper, or denial receipt may differ without changing the
historical content or content-qualification digests.

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
- `AgronomicObservationContext.phenomenonTime.instant/intervalStart/intervalEnd`
- `CropCycleIdentityPayload.startedAt/endedAt`
- `ExecutionRecordPayload.effectiveTimeInterval.start/end`
- `ExternalRegistryVerificationTrace.datesObserved.statusEffectiveFrom/statusEffectiveUntil`
- `InterventionIntentPayload.intendedTimeWindow.start/end`
- `MeasurementEvidence.calibration.calibratedAt/dueAt`
- `MeasurementEvidence.phenomenonTime.instant/intervalStart/intervalEnd`
- `MeasurementEvidence.procedureRef.effectiveAt`
- `NarrativeObservation.observedAt`
- `PartialExtent.temporalApplicability.instant/intervalStart/intervalEnd`
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
| Future #193-witnessed recovery head K51 permanently retires unused K50 | later write attempting K50 | Refuse; no position at or below the witnessed head can be filled later. V1 cannot create this recovery state. |
| K41-K45 were published, then an operator restores K40 | attempt to promote or allocate a new K41 | Refuse the recovery target before governed traffic; the original K41 remains consumed. |
| A principal or grant was revoked after the restored image | current authorization on that image | Refuse recovery promotion; absence of the revocation tail cannot reactivate authority. |
| One tenant's old rows are copied into the shared service | attempt to preserve or splice their old cuts | Unsupported tenant-history recovery; domain facts must enter new governed batches instead. |
| Equal wall clocks in two batches | any | Knowledge positions decide visibility. |
| Exclusive overlap without lineage | any | Ambiguity and refusal. |
| Missing event/effective time with capture time | any | Refuse; no substitution. |
| Naive `2026-07-10T12:00:00` | parse | Reject. |
| Seven fractional digits | parse | Reject; never truncate or round. |
| Unknown offset `2026-07-10T12:00:00-00:00` | parse | Reject; the offset is not known. |
| Leap second `2026-12-31T23:59:60Z` | parse | Reject; no parser-specific normalization. |
| Invalid bearer token claims tenant A | pre-tenant failure | Append only a redacted operational security event with no tenant or position; tenant A's head and tables are unchanged. |
| Bound tenant A command refuses durably | post-binding refusal | Append the refusal in one tenant-A batch at its allocated position; no other tenant changes. |
| One event instant and one state interval meet the same window | two governed selection steps | Apply `EVENT_OCCURRENCE` to the event and `STATE_OVERLAP` to the state; never one hidden query-wide predicate. |
| Active SI inspection-register v0.1 artifacts | high-consequence freeze | Stop until new versioned profile artifacts carry correct converted bounds and per-step meanings. |
| Historical content at K20; sharing revoked at K30 | new read at head K30 | Reconstruct content at K20, but current disclosure authorization denies release. |
| Disclosure check at K29 races a revocation at K30 | serialized release | Whichever acquires the tenant release guard first determines the order; no K29 decision can commit its receipt/enqueue after K30 commits. Delivery of an already-enqueued wrapper may occur later. |
| Disclosure check races a dispute, correction, or invalidation writer | serialized release | The same guard orders every release-relevant writer; no stale decision can commit its receipt/enqueue after the competing change commits. Delivery of an already-enqueued wrapper may occur later. |
| Release evaluation crosses an authority expiry boundary before release commit/enqueue | time-derived release rule | Roll back with no enqueue and restart with a new `releaseEvaluationAt` and `Kauth`. |
| Content and qualification at K20; release evaluated at instant R and K30; receipt commits at K31 | allowed replay release | Content and qualification remain bound to K20; authorization binds K20/K30/R; wrapper and receipt bind K20/K30/K31/R. |
| Same content, but release denies at K30 | denied replay release | Commit a denial receipt at its own position; create no release wrapper and hand off no bytes. |

Replay acceptance test: materialize at `(validAt=V, contentKnowledgeCut=K)`,
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
13. Pre-pipeline authentication, principal, actor-binding, and routing failures
    have no classified pre-tenant security-audit lane, while current tenant
    storage still permits a demo-tenant default.
14. Closed query, plan, request, context, basis, key, result, qualification, and
    output surfaces do not carry the authoritative per-step carrier selector;
    their WINDOW shapes also do not carry window meaning.
15. `SemanticEventEnvelope` permits several time fields across every
    `primaryEventFamily`; current runtime fallbacks do not enforce the carrier
    matrix above.
16. The active SI inspection-register QuerySpecification and QueryPlanIR use an
    incompatible end instant and carry neither per-step carrier selectors nor
    window meanings.
17. `ResultQualificationEnvelope` mixes historical content/reliance posture
    with request-time authority, permission, use-class, and redaction posture.

## Active SI inspection-register migration stop

The active artifacts
`queryspec:si.ffs.inspection-register.documentassembly.v0_1` and
`queryplan:si.ffs.inspection-register.documentassembly.v0_1` currently contain:

```json
{
  "windowStart": "2026-01-01T00:00:00Z",
  "windowEnd": "2026-12-31T23:59:59Z"
}
```

Under half-open semantics, that end excludes the instant itself, the remainder
of the final second, and every later instant on December 31. The pair also
cannot be treated as an inclusive calendar-year conversion because the active
profile supplies no governed jurisdictional timezone/inclusivity rule for that
conversion. Both artifacts also lack per-step carrier selectors and window
meaning.

Their bytes and identities are historical inputs. #176 must stop rather than
reinterpret, mutate, round, or silently replace them. The versioned
contract/schema governance path below must land first because the current
closed QuerySpecification and QueryPlanIR schemas reject added carrier/meaning
fields. A subsequent separately authorized profile-artifact patch must:

1. govern the jurisdictional timezone and inclusive/exclusive calendar-date
   conversion rule;
2. publish new versioned QuerySpecification and QueryPlanIR identities using
   `[start-of-first-local-date, start-of-day-after-last-local-date)` normalized
   to UTC;
3. declare the carrier for every temporal selection step and the window meaning
   for every WINDOW step, including accepted execution, state eligibility,
   pending/disputed annex entries, and inherited sufficiency basis;
4. update runtime constants and conformance bindings;
5. regenerate ActiveArtifactSet, Capability Manifest, and applicable contract or
   source-manifest grounding through their governed workflows; and
6. retire the v0.1 query and plan from the active set while preserving their
   historical bytes and identities.

Until that patch is accepted and activated, the SI inspection-register
high-consequence freeze is unsupported under this ADR. No implementation ticket
may claim conformance by applying new semantics to the old artifact identifiers.

## Contract and implementation stop condition

Inspection of the shipped closed contracts establishes two present gaps; this
is no longer a conditional implementation choice.

First, QuerySpecification, QueryPlanIR, MaterializationRequest,
ContextSnapshot, and MaterializationBasis do not carry an authoritative per-step
carrier selector. Their WINDOW shapes carry bounds but no event-occurrence
versus state-overlap discriminator. Materialization keys, results/snapshots,
qualification, and output receipts likewise cannot prove that the carrier or
applicable WINDOW meaning was preserved.

Second, the closed qualification, authorization, and output surfaces cannot
carry the three positions, `releaseEvaluationAt`, and digest matrix above. In
particular:

- `ResultQualificationEnvelope` mixes stable content/reliance fields with
  current permission, use-class, and redaction fields and exposes neither the
  required cuts nor their digest bindings;
- AuthorizationDecision request/trace/result surfaces do not bind exact target
  content and content-qualification digests, `Kcontent`, `Kauth`, and their
  governed batch; and
- Passport/Document metadata plus PublicationAssembly request/result surfaces
  are reference-oriented and cannot bind the released bytes, authorization
  digest, `Kreceipt`, wrapper, and receipt without semantic distortion.

Therefore #176 must stop and open the versioned
candidate-contract/RFC/ERRATA governance path before enabling a WINDOW query,
historical materialization, qualification, output freeze, or release under this
ADR. That path must provide:

1. an immutable authoritative carrier selector for every temporal selection,
   plus a discriminator for every WINDOW step with the exact
   `EVENT_OCCURRENCE` and `STATE_OVERLAP` semantics defined above, carried from
   QuerySpecification through plan, request, context, basis, key, result,
   qualification, wrapper, and receipt;
2. a stable content-qualification surface separated from request-time release
   permission and redaction;
3. immutable fields for `Kcontent`, `Kauth`, `Kreceipt`, and
   `releaseEvaluationAt`, plus the content, qualification, authorization,
   wrapper, and receipt digest bindings in the matrix above; and
4. an allowed release shape whose receipt and exact-wrapper durable
   response-sink/outbox enqueue commit atomically as the release linearization
   point, plus a denied shape that creates no wrapper, enqueue, digest cycle, or
   byte delivery.

#176 must not hide any of these meanings in mutable relational annotations,
`traceRefs`, notes, identifier naming, `durableArtifactRef`, timestamp
conventions, or other unreviewed fields. The same stop applies to the pre-tenant
security-audit lane until its storage and privilege model is governed.

This is a design stop, not permission to edit `reference/**`, promote a draft,
mutate active artifacts, or weaken replay evidence.

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
| Infer prototype batches from equal or nearby timestamps | Fabricates atomicity and order that the old store never recorded; disposable data is rebuilt instead. |
| Promote an older backup because schema/build digests match | Compatibility does not prove timeline continuity; the image can reuse published positions and erase revocations, receipts, or released-output history. |
| Splice one tenant's old history into the shared service | Global control state and tenant cuts cannot be reconciled independently, and old positions cannot be reused. |
| One hidden WINDOW predicate for a heterogeneous assembly | Event occurrence and state overlap answer different questions and must remain explicit per step. |
| Reuse one qualification envelope for stable content and current release | Later revocation/redaction would either mutate historical evidence or make current permission false. |

## Verification plan for #176 and dependent tickets

At minimum, executable verification must cover:

- schema/SQL timestamp inventory coverage;
- point and window boundaries, including adjacent windows;
- every `primaryEventFamily` and record-family carrier in the matrix, including
  matching secondary representations and fail-closed missing/mismatch cases;
- per-step authoritative carrier propagation through every temporal query,
  plan, materialization, qualification, and output surface, plus
  `EVENT_OCCURRENCE`/`STATE_OVERLAP` propagation for every WINDOW step;
- UTC normalization plus naive, unknown-offset, and leap-second rejection;
- same-position whole-batch visibility;
- refused commands, imports/activations, reviews, and read receipts receiving
  positions when they write durable evidence;
- pre-tenant credential, verifier, principal, actor-binding, and routing
  failures producing only safe operational audit while every tenant head and
  table remains unchanged, regardless of attacker-supplied tenant context;
- a post-binding refusal affecting only the bound tenant;
- rollback, retired-gap immutability, and concurrent monotonic allocation;
- restore K40 after publishing K41-K45 and prove V1 cannot promote the target,
  reuse K41, mint/bind authority, allocate, read, release, or deliver; a matching
  schema/build alone never passes recovery readiness;
- restore an image predating principal/grant revocation and attempt a one-tenant
  history import; both refuse before current authorization or timeline splice;
- cross-tenant non-comparability;
- prototype rebuild from a proven-empty target with no timestamp-derived batch
  grouping or fabricated historical position;
- late arrival, future effect, and expiry;
- correction/supersession replacement sets;
- dispute state before and after its knowledge position;
- equal-wall-clock and equal-valid-time ambiguity;
- missing-domain-time refusal;
- transitive cut-aware graph, context, authority, and reference reads;
- current disclosure denial after a historical grant is revoked;
- concurrent release against grant/revocation, dispute/resolution,
  correction/supersession, invalidation/staleness, and other release-relevant
  writers with no check-to-release gap, plus restart on a crossed time boundary;
- stable content qualification across later release decisions, plus exact
  `Kcontent`/`Kauth`/`Kreceipt`/`releaseEvaluationAt` and digest-matrix
  assertions for allow and deny;
- refusal to execute the active SI inspection-register v0.1 freeze, followed by
  acceptance only for separately governed versioned artifacts with converted
  date bounds, explicit carriers for every temporal selection step, and
  meanings for every WINDOW step;
- reconstruction replay after later changes with identical historical content
  digests, plus an independently current disclosure decision; and
- output annexes and stable content qualification using the historical cut,
  with release evidence binding the separate request-time positions.

## Acceptance-criteria trace

| Issue #170 criterion | ADR section |
| --- | --- |
| Interval inclusivity and point/window/current reads | Valid-time model; governed carrier/window matrix; Current state |
| Tenant monotonic position, non-reuse across recovery, and whole write batch | Pre-tenant operational security audit; Knowledge-time model; Recovery boundary |
| Every existing timestamp classified | Existing timestamp classification |
| Late/future/expiry/correction/supersession/dispute/equal-time behavior | Dedicated behavior sections; examples |
| UTC-aware representation and naive rejection | Timestamp representation |
| Historical query pins both axes; replay proves same cut | Historical queries and replay; three named positions; stable content qualification |
| No capture/ingestion substitution | Late arrival section; current contradictions |
| Executable examples and boundary cases | Executable boundary examples; verification plan |

## Consequences

- #176 owns the storage and query implementation of these meanings.
- #170 changes no runtime behavior.
- #171 supplies the immutable RuntimeBundle identity that historical receipts
  must pin.
- ADR 0001 classifies the pre-tenant audit lane. #172 owns closed authentication
  outcomes, #173 the binding boundary, #174 the isolated PostgreSQL storage and
  privileges, and #192 the client, producers, delivery/health behavior,
  operations, and end-to-end verification. #176 consumes that completed
  boundary and may not invent another.
- #193 owns any later non-forking recovery design. Until it lands, the tenant
  service has no restore/import promotion or recovery-readiness path and no
  destructive migration may rely on one.
- A separately authorized SI profile-artifact patch must replace and retire the
  incompatible inspection-register v0.1 query and plan before #176 enables that
  freeze under these semantics.
- The versioned candidate-contract/RFC/ERRATA path must provide the carrier
  selector for every temporal selection step and the meaning for every WINDOW
  step, stable content qualification, release permission, the three positions,
  `releaseEvaluationAt`, and their digest bindings before the affected #176
  surfaces can proceed.
- #177 owns current permission/redaction evaluation and serialization against
  revocation and other release-relevant authority changes. #181 and #182 must
  use the same valid cut and `Kcontent` for materialization, stable
  qualification, and persisted content; #182 binds the frozen assembly and
  qualification, while release evidence binds the additional `Kauth` and
  `Kreceipt` positions. If the atomic durable response enqueue is outside those
  accepted scopes, a separately accepted delivery-owner ticket must implement
  it rather than expanding them implicitly.
- #184 must keep semantic references and graph traversal cut-aware.
- Existing single-axis behavior remains non-authoritative technical debt until
  the implementation and contract stop conditions are resolved.
