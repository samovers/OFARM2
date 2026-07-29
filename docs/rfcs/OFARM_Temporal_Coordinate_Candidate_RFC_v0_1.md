# OFARM Temporal Governance Candidate RFC v0.1

**Status:** package-local `CANDIDATE_ARTIFACT`; non-default and inactive

**Temporal coordinate schema version:** `ofarm.temporal-coordinate.v0.1`

**Temporal coordinate schema digest:** `sha256:b81e4c7b0aacebb11ff8bf0d186cdb36150fade31180552b46f7be9e13c551eb`

**Temporal carrier matrix schema version:** `ofarm.temporal-carrier-matrix.v0.1`

**Temporal carrier matrix schema digest:** `sha256:cdb5c09ec033cc3b4de1dea9eb383c499045d8a3bfc5b80fd7abeab579a566ed`

**Temporal carrier matrix instance:** `ofarm.temporal-carrier-matrix.adr0002.v0.1`

**Temporal carrier matrix instance digest:** `sha256:7cb26513b5abdbcadecaf6f9b47d874a742ba8fa05a332c9130deebe449d7fc6`

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

This package supplies the necessary coordinate vocabulary and an immutable
classification transcription of ADR 0002's carrier matrix. It does not
authorize temporal storage, executable carrier selection, historical queries,
materialization, outputs, or production activation.

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

`ValidCut` does not choose a record-family carrier. Every future governed
selection step must bind an immutable carrier-matrix version, matrix digest,
and executable selector approved by the later carrier-selection boundary.
Every WINDOW step must also declare exactly one meaning:

- `EVENT_OCCURRENCE`: `windowStart <= occurrenceTime < windowEnd`
- `STATE_OVERLAP`: the interval-overlap predicate above

The meaning belongs to each selection step because one assembly may select
both events and states.

## Candidate carrier matrix

`ofarm.temporal-carrier-matrix.adr0002.v0.1` transcribes the 15 rows in ADR
0002's “Governed carrier and window-meaning matrix.” Its schema closes the row
identity set and requires the authoritative-carrier, secondary-time consistency,
and window/refusal rule for each row. Conformance proves that every rule string
comes from that ADR section after markup removal and that the matrix binds this
exact coordinate-schema digest.

The matrix has execution posture
`CLASSIFICATION_ONLY_RUNTIME_UNSUPPORTED`. Its rule text is immutable
classification evidence, not executable field-selector syntax. It does not
amend any record schema, select a production field, activate a profile, or
permit runtime interpretation of a row. A later approved valid-time carrier
boundary must define closed executable selectors, bind each selector to the
applicable row and matrix digest, and carry that binding through the governed
query and evidence surfaces before any row can execute.

## KnowledgeCut

`KnowledgeCut` contains:

```json
{
  "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
  "position": 42
}
```

`tenantId` is the exact canonical, non-nil UUID installed by trusted
`TenantBinding`. ADR 0003's UUID encoding rule forbids the all-zero UUID.
Request-supplied tenant, Party, or farm aliases cannot substitute for it.

`position` is an exact JSON integer from zero through `9007199254740991`
(`2^53−1`, the IEEE-754 maximum safe integer). Zero means the tenant state
before its first committed governed batch. Positive positions order complete
committed batches for that tenant only. Cross-tenant positions are
incomparable. The portable contract bound prevents ordinary JSON runtimes from
rounding a valid position; a future database may use a wider internal integer
type but must refuse allocation above the contract maximum.

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
- missing, nil, or non-canonical tenant UUIDs;
- negative, non-integer, or larger-than-`9007199254740991` knowledge
  positions;
- using one tenant's cut for another tenant;
- a cut above the committed tenant head;
- missing, conflicting, or semantically unclassified valid-time carriers;
- WINDOW selection without a per-step `WindowMeaning`; and
- deriving knowledge order from a timestamp or identifier.

Contract validation alone cannot observe the tenant head, carrier matrix, or
batch visibility. Those checks remain mandatory future runtime boundaries; the
absence of their implementation keeps the operation unsupported.

## Versioning and currentness

Each candidate artifact is closed and digest-pinned. Before a specific digest
receives an explicit governed promotion/currentness decision, pre-promotion
candidate revisions may retain the `v0.1` candidate identity; every revision
must update all manifest and RFC digest bindings and remains reviewable by
digest. Once a reviewed digest is promoted to a governed artifact, any
semantic, field, enum, canonicalization, bound, predicate, carrier row, or
refusal change requires a new version and artifact identity. Test success or
this Phase A implementation approval is not a promotion/currentness decision.

The candidate package lives under `contracts/candidates/`, outside active
contract-registry directories. It is absent from `kernel/runtime_bundle_components.json`,
`profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json`, and
`profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json`. Those are the
only profile files inspected by this candidate check. Other profile trees are
neither inspected nor granted authority. Existing frozen v0.1 contracts remain
unchanged.

Future contracts must consume this exact version and digest rather than copy
similar fields or hide the meanings in notes, references, timestamp
conventions, or mutable relational annotations.

`validInterval` and `windowMeaning` are named vocabulary fragments, not root
instance fields. This candidate does not establish cross-document `$ref`
resolution, a production schema registry, or an executable carrier binding. A
future governed carrier contract must choose that binding mechanism, pin the
exact coordinate and matrix versions and digests, and make the applicable
fragment reachable from its own validation root before either fragment can
govern a production instance.

The package's deliberately small built-in schema validator does not implement
every Draft 2020-12 keyword used by these candidates. Before promotion or
registration of production instances, the package must bind a complete Draft
2020-12 validation path covering `$ref`, `$defs`, `format`, numeric bounds, and
`not`, with conformance fixtures proving the same refusal surface. The current
dedicated checker and pytest validation are candidate verification only; they
do not activate a general registry validator.

## Authority map

- ADR 0002 owns the two-axis meanings, half-open predicates, matrix row
  content, and downstream stop conditions.
- ADR 0003 and trusted `TenantBinding` own the canonical non-nil tenant
  identity consumed by `KnowledgeCut`.
- The candidate schemas own only the closed inactive serialization shapes.
- The candidate matrix owns only the digest-pinned ADR classification
  transcription; it owns no executable selector.
- `CONTRACTS_MANIFEST.json` and this RFC own candidate provenance, currentness,
  and digest binding.
- Existing frozen contracts, RuntimeBundle selection, production activation
  inputs, profiles, storage, runtime, output, and #192 authorities remain
  unchanged.

## Invariants

- `TemporalCoordinate` always contains independent `ValidCut` and
  tenant-scoped `KnowledgeCut` values.
- Valid intervals and query windows are non-empty and half-open.
- Knowledge positions are exact, tenant-local, whole-batch boundaries within
  the portable safe-integer range.
- Every carrier-matrix row is present exactly once and its rule text is
  traceable to ADR 0002.
- Every artifact is closed, digest-bound, inactive, and absent from production
  registries and activation inputs.
- Test or conformance success never promotes or activates a candidate.

## Non-goals

This phase does not add or alter database storage, allocation, migrations,
runtime temporal selection, executable carrier selectors, semantic routes,
materialization, historical or WINDOW execution, current-state output,
qualification, authorization, receipts, delivery, profile activation, frozen
contracts, or #192 audit-runtime behavior.

## Verification

Candidate verification must prove strict JSON parsing; complete Draft 2020-12
schema validity in the pinned pytest environment; exact schema and matrix
shape; shared positive and refusal vectors; ADR row transcription; manifest and
RFC digests; ERRATA linkage; production non-activation by contract path and
component path; and unchanged RuntimeBundle closure. The repository package
contract check must invoke the dedicated candidate checker before every commit.

## Required future boundaries

Separate approved Phase A contracts are required before:

- a migration stores or allocates tenant knowledge positions;
- code turns a carrier-matrix row into an executable record-family selector;
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
