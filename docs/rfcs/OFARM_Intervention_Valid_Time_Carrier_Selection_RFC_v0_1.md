# OFARM Intervention Valid-Time Carrier Selection RFC v0.1

**Status:** package-local `CANDIDATE_ARTIFACT`; executable pure library,
production-unbound and inactive

**Binding schema version:**
`ofarm.temporal-carrier-selection-binding.v0.1`

**Binding schema digest:**
`sha256:d252420507393d1d9816a0f20549faa8cf67c94bd1e2c10a3c509aadf4f3800a`

**Binding identity:**
`ofarm.temporal-carrier-selection.intervention.v0.1`

**Binding artifact digest:**
`sha256:9886aace0670b6a83f17cd33cbc67aa62fafcfd0ea873faed9194c2aaa07efe5`

**Primary implementation ticket:** #176

## Decision

This package defines one executable valid-time carrier binding and nothing
else. The supported source pair is:

- `ofarm.semanticeventenvelope.v0.1` with
  `primaryEventFamily=InterventionEvent`; and
- `ofarm.executionrecordpayload.v0.1` with
  `recordClass=OPERATION_CLAIM`.

The selector returns both reviewed carriers atomically:

1. `timeSemantics.eventTime` is a POINT with
   `EVENT_OCCURRENCE` window meaning.
2. `effectiveTimeInterval.start/end`, only with
   `timeBasis=EXECUTION_INTERVAL`, is the bounded half-open interval
   `[start,end)` with `STATE_OVERLAP` window meaning.

No other carrier-matrix row, event family, record class, time basis, source
field, or selector is supported.

## Identity authority

**Identity posture:** `REVIEWED_BINDING_ARTIFACT_NOT_CALLER_DATA`

The reviewed, versioned binding artifact fixes:

- its own schema version and binding identity;
- temporal-coordinate version and digest;
- carrier-matrix identity, digest, and `INTERVENTION_EVENT` row;
- both source-contract versions and digests;
- both discriminator values;
- every field path; and
- both window meanings.

These identities are never taken from caller data. A caller-provided
`schemaVersion` is only an untrusted claim checked for equality with the fixed
source-contract identity. The closed API accepts only the envelope and
execution payload; it accepts no binding, matrix, row, selector, field path,
window meaning, tenant, or knowledge-position argument.

## Fixed prerequisite identities

- Temporal coordinate:
  `ofarm.temporal-coordinate.v0.1`,
  `sha256:b81e4c7b0aacebb11ff8bf0d186cdb36150fade31180552b46f7be9e13c551eb`
- Carrier matrix:
  `ofarm.temporal-carrier-matrix.adr0002.v0.1`,
  `sha256:7cb26513b5abdbcadecaf6f9b47d874a742ba8fa05a332c9130deebe449d7fc6`
- SemanticEventEnvelope:
  `ofarm.semanticeventenvelope.v0.1`,
  `sha256:75662a6c4952a62b7e8f8e9de99c23c98899c692914a98ba4b752873f48bd1a4`
- ExecutionRecordPayload:
  `ofarm.executionrecordpayload.v0.1`,
  `sha256:ca62f01d056794ee588d55c3f5df652fc039124b76af5631d417714bc7059ff0`

## State and ordering

Selection is a pure, side-effect-free transition:

```text
UNBOUND -> BOUND -> VALIDATING -> SELECTED
                           \----> REFUSED
```

The selector validates exact source identities and discriminators before
extracting temporal values. It then validates canonical UTC instants,
`EXECUTION_INTERVAL`, and `start < end`. Any failure returns no partial
selection.

There is no transaction, database, tenant head, clock read, filesystem read,
network call, mutable registry, or runtime activation in this boundary.

## Half-open rules

```text
event in window:
windowStart <= eventTime < windowEnd

state at point:
start <= validAt < end

state overlaps window:
start < windowEnd and windowStart < end
```

Adjacent intervals `[A,B)` and `[B,C)` do not overlap. An event at `B` belongs
only to the second interval, and a state ending at `B` is absent at `B`.

## Required refusals

The selector refuses:

- a different binding or source-contract claim;
- any family other than `InterventionEvent`;
- any record class other than `OPERATION_CLAIM`;
- missing `eventTime`;
- naive, offset, unknown-offset, leap-second, non-real, or over-precision
  instants;
- missing interval bounds;
- any time basis other than `EXECUTION_INTERVAL`;
- empty or reversed intervals;
- envelope `effectiveFrom` or `effectiveUntil`, whose relationship to the
  payload interval is not governed by this version; and
- any attempt to substitute capture, assertion, record, ingestion, identifier,
  or wall-clock time.

The occurrence point and execution interval are independent carriers in this
version. The occurrence is not required to fall inside the execution interval,
and their non-overlap is not a refusal. Adding a relationship between them
would create new temporal law and requires a separately reviewed versioned
binding.

## Authority map

- ADR 0002 owns carrier meanings and half-open predicates.
- The inactive temporal-coordinate candidate owns UTC and window vocabulary.
- The inactive carrier matrix owns the `INTERVENTION_EVENT` classification.
- The frozen source contracts own their field names and shapes.
- This binding artifact alone owns the executable mapping between those fixed
  identities.
- `kernel.temporal_carriers` implements the mapping but cannot expand it.
- A later governed command owns whether it invokes this binding. Requests do
  not.

Legacy `kernel.context.parse_ts`, ingress normalization, and temporal
validation are not dependencies or alternate authorities.

## Invariants

- `VTC-001` through `VTC-014` are the approved Phase A invariants.
- Selection returns both the point and interval or neither.
- Every accepted interval is non-empty and half-open.
- No secondary timestamp can become a valid-time carrier.
- The selector is deterministic and immutable.
- The selector remains absent from production and legacy import closures.
- The artifacts remain absent from RuntimeBundle, profiles, active artifact
  sets, capability manifests, and production registries.

## Non-goals and stop conditions

This boundary adds no route, governed command, database work, migration,
knowledge cut, historical or WINDOW query, current-state read, materialization,
qualification, output, profile activation, RuntimeBundle component, other
carrier row, or #192 behavior.

If production integration requires changing RuntimeBundle selection, an active
artifact, a command contract, a route, a database authority, or a public
refusal vocabulary, implementation stops and proposes that boundary
separately. The pure library may execute in focused verification, but it
remains production-unbound.

## Verification

Verification proves:

- complete Draft 2020-12 schema validity;
- exact artifact, prerequisite, source-contract, matrix, and row identities;
- exact artifact-to-implementation discriminator and field-path mappings;
- the closed two-argument API;
- strict UTC refusals;
- temporal equality for lexically different forms of the same accepted instant;
- `EXECUTION_INTERVAL` enforcement;
- half-open point, state-at, overlap, and adjacency behavior;
- atomic selection and deterministic immutable output;
- production/legacy import isolation; and
- absence from RuntimeBundle and profile activation inputs.
