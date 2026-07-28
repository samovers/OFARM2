# OFARM Temporal Coordinate Candidate RFC v0.1

**Status:** package-local `CANDIDATE_ARTIFACT`; non-default and inactive

**Schema version:** `ofarm.temporal-coordinate.v0.1`

**Schema digest:** `sha256:040183984d7c64194b5e5dad3ef080f4677fafffe59aaa8f66ed02d99350e003`

**Primary implementation ticket:** #176

**Authority:** ADR 0002 defines the package-local temporal meaning. The OFARM
Constitution and Platform Architecture retain governance authority. This
candidate neither amends OFARM law nor promotes a machine contract.

## Decision

An authoritative historical or high-consequence evaluation requires one
immutable `TemporalCoordinate` containing two independent axes:

1. `ValidCut` states when a fact applies in the represented world.
2. `KnowledgeCut` states the greatest committed governed-batch position visible
   for exactly one tenant.

Neither cut may be omitted, derived from the other, or replaced by an
unclassified `as_of`, `record_time`, capture time, or other wall clock.

This candidate is a necessary vocabulary only. It does not authorize temporal
storage, carrier selection, historical queries, materialization, or outputs.

## Canonical UTC instants

Durable instants are real Gregorian UTC timestamps serialized with uppercase
`Z` and zero through six fractional digits. Validation rejects naive values,
non-UTC durable encodings, unknown `-00:00` offsets, leap seconds, more than six
fractional digits, and rounding or truncation.

A calendar date is not an instant. Converting a date requires a separately
governed jurisdictional timezone and inclusive/exclusive date rule.

## Valid intervals

A state fact with temporal force uses:

```text
[validFrom, validUntil)
```

`validFrom` is required and inclusive. `validUntil` is optional and exclusive;
absence means positive infinity. A present end must be strictly later than the
start. A point event is not encoded as an empty interval.

The canonical point predicate is:

```text
validFrom <= validAt
and
(validUntil is absent or validAt < validUntil)
```

The canonical overlap predicate is:

```text
validFrom < windowEnd
and
(validUntil is absent or windowStart < validUntil)
```

No capture, ingestion, assertion, acceptance, decision, record, generation, or
identifier time may supply a missing valid-time carrier.

## ValidCut

`ValidCut` has exactly one of two closed forms.

Point:

```json
{
  "cutType": "POINT",
  "validAt": "2026-07-28T10:30:00Z"
}
```

Window:

```json
{
  "cutType": "WINDOW",
  "windowStart": "2026-01-01T00:00:00Z",
  "windowEnd": "2027-01-01T00:00:00Z"
}
```

WINDOW is always the non-empty half-open interval
`[windowStart, windowEnd)`. Point and WINDOW fields cannot be mixed. `NOW` is
request syntax, not a durable cut; a future current-read boundary must resolve
it exactly once to a POINT.

`ValidCut` does not choose a record-family carrier. A later governed carrier
contract must bind every selection step to an immutable carrier-matrix version
and digest. Every WINDOW step must also declare exactly one meaning:

- `EVENT_OCCURRENCE`: `windowStart <= occurrenceTime < windowEnd`
- `STATE_OVERLAP`: the interval-overlap predicate above

The meaning belongs to each selection step because one assembly may select
both events and states.

## KnowledgeCut

`KnowledgeCut` contains:

```json
{
  "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
  "position": 42
}
```

`tenantId` is the exact canonical UUID installed by trusted `TenantBinding`.
Request-supplied tenant, Party, or farm aliases cannot substitute for it.

`position` is an exact integer from zero through signed int64 maximum. Zero
means the tenant state before its first committed governed batch. Positive
positions order complete committed batches for that tenant only. Cross-tenant
positions are incomparable.

A future storage implementation must make each batch wholly visible at its
position, publish no position on rollback, never reuse a committed position,
and refuse a requested cut above the committed tenant head. A wall clock or
nearest-row search cannot create or approximate a position.

`KnowledgeCut` is a query boundary. A future batch receipt must separately bind
its positive position to the exact governed batch identifier.

## Evaluation relationship

Future temporal execution must:

1. bind the exact tenant;
2. validate the knowledge cut against that tenant's committed head;
3. reconstruct only complete batches at positions less than or equal to the
   cut;
4. apply correction, supersession, and dispute state visible at that cut; and
5. apply the valid cut through the governed carrier and per-step window
   meaning.

A late-arriving fact can therefore be valid in the past but absent from an
earlier knowledge cut.

The cut pair is necessary but not sufficient replay evidence. Replay also pins
the RuntimeBundle, database schema, carrier matrix, policy, reference inputs,
basis, and applicable content digests.

## Required refusals

Contract or semantic validation refuses:

- missing, unknown, or mixed POINT/WINDOW fields;
- empty, reversed, or open-ended query windows;
- empty or reversed state intervals;
- literal `NOW` in durable temporal evidence;
- naive, unknown-offset, leap-second, non-real, or over-precision instants;
- missing or non-canonical tenant UUIDs;
- negative, non-integer, or larger-than-int64 knowledge positions;
- using one tenant's cut for another tenant;
- a cut above the committed tenant head;
- missing, conflicting, or semantically unclassified valid-time carriers;
- WINDOW selection without a per-step `WindowMeaning`; and
- deriving knowledge order from a timestamp or identifier.

Contract validation alone cannot observe the tenant head, carrier matrix, or
batch visibility. Those checks remain mandatory future runtime boundaries; the
absence of their implementation keeps the operation unsupported.

## Versioning and currentness

The schema is closed and digest-pinned. Any semantic, field, enum,
canonicalization, bound, or predicate change requires a new schema version and
artifact identity.

The candidate lives outside active contract-registry directories. It is absent
from the production RuntimeBundle, ActiveArtifactSet, Capability Manifest, and
all profiles. Existing frozen v0.1 contracts remain unchanged.

Future contracts must consume this exact version and digest rather than copy
similar fields or hide the meanings in notes, references, timestamp
conventions, or mutable relational annotations.

## Required future boundaries

Separate approved Phase A contracts are required before:

- a migration stores or allocates tenant knowledge positions;
- code selects a record-family valid-time carrier;
- a production command emits a governed batch position;
- QuerySpecification, QueryPlanIR, context, basis, key, result, or snapshot
  supports AS_OF or WINDOW;
- qualification, authorization, output, wrapper, receipt, or delivery binds
  `Kcontent`, `Kauth`, `Kreceipt`, or `releaseEvaluationAt`; or
- the incompatible SI inspection-register v0.1 artifacts are replaced and
  activated.

Until those boundaries are approved and implemented, production semantic
routes remain closed and historical/WINDOW execution and output are
unsupported.
