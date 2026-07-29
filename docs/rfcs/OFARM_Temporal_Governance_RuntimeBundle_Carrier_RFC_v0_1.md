# OFARM2 Temporal-Governance RuntimeBundle Carrier — Phase A Contract v0.1

**Status:** package-local `CANDIDATE_ARTIFACT`; vocabulary-only,
runtime-unsupported and inactive

**Binding schema version:**
`ofarm.temporal-governance-runtime-bundle-carrier-binding.v0.1`

**Binding schema digest:**
`sha256:6a04b0c3a68428ca0b505e70ba056a4295bde31a3c510fb75191222d8dc228bf`

**Binding identity:**
`ofarm.temporal-governance-runtime-bundle-carrier.v0.1`

**Binding artifact digest:**
`sha256:391c8110029f004375e668e5e902864c0b4aaf6f650005abed8a206d4049e5b4`

**Date:** 2026-07-29

**Primary implementation ticket:** #176

**Primary trust boundary:** RuntimeBundle provenance for reviewed
temporal-governance artifacts

**PR boundary:** inactive candidate contract and conformance only

## Decision

OFARM2 needs one closed RuntimeBundle component vocabulary for reviewed,
versioned temporal-governance artifacts before a production runtime may claim
that a RuntimeBundle pins the temporal meaning used by a governed command.

The new component role is:

```text
TEMPORAL_GOVERNANCE_ARTIFACT
```

The role means only this:

- the component bytes are one reviewed temporal matrix or binding instance;
- the bytes use `OFARM_CANONICAL_JSON_V1`;
- the placement is `GLOBAL_IMMUTABLE_CONTENT`;
- the logical reference and schema version identify one member of the closed
  artifact family in this contract; and
- the component digest is computed from the exact canonical instance bytes.

This role is not a valid-time carrier, a RuntimeBundle selector, an activation
flag, a policy engine, a command registry, or permission to execute an
artifact. A published RuntimeBundle containing such a component proves only
that the exact bytes are retained in that bundle's immutable provenance
closure.

No existing RuntimeBundle role may be reused for this purpose:

- `CONTRACT_SCHEMA` and `DRAFT_CONTRACT_SCHEMA` carry schemas, not governed
  instance choices;
- `PROFILE_INSTANCE` carries one of its already closed profile instance
  families;
- `REFERENCE_SOURCE` carries retained reference-source bytes, not governance
  authority; and
- `ADAPTER_SOURCE`, `VALIDATOR_SOURCE`, and `QUERY_OUTPUT_SOURCE` carry
  executable source bytes, not reviewed semantic selections.

Using any of those roles for a temporal matrix or binding instance would
combine authorities and is refused.

## Closed Phase A identity set

The version 0.1 allowed identity set for
`TEMPORAL_GOVERNANCE_ARTIFACT` contains exactly these candidate artifact
identities:

| Artifact kind | Schema version | Exact instance identity |
|---|---|---|
| Temporal carrier matrix | `ofarm.temporal-carrier-matrix.v0.1` | `ofarm.temporal-carrier-matrix.adr0002.v0.1` |
| Temporal carrier-selection binding | `ofarm.temporal-carrier-selection-binding.v0.1` | `ofarm.temporal-carrier-selection.intervention.v0.1` |
| Temporal governed-command binding | `ofarm.temporal-governed-command-binding.v0.1` | `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1` |

The role's allowed identity set is closed. Another matrix, matrix row,
selector, source contract, command, ingress channel, outcome, artifact kind,
or schema version requires a new reviewed contract version before it may use
this role.

Eligibility for this role is not a component-closure rule. This contract does
not require every RuntimeBundle, or every use of
`TEMPORAL_GOVERNANCE_ARTIFACT`, to contain all three allowed identities. A
later reviewed governed-command contract and tenant RuntimeBundle-selection
contract must define the exact component closure required for
`COMMIT_OPERATION_CLAIM_DRAFT`.

The exact merged candidate review basis is:

| Artifact | Repository file digest | Canonical instance digest |
|---|---|---|
| Temporal-coordinate schema | `sha256:b81e4c7b0aacebb11ff8bf0d186cdb36150fade31180552b46f7be9e13c551eb` | not applicable; a schema is retained as exact `CONTRACT_SCHEMA` bytes |
| Temporal carrier-matrix schema | `sha256:cdb5c09ec033cc3b4de1dea9eb383c499045d8a3bfc5b80fd7abeab579a566ed` | not applicable; a schema is retained as exact `CONTRACT_SCHEMA` bytes |
| ADR 0002 temporal carrier-matrix instance | `sha256:7cb26513b5abdbcadecaf6f9b47d874a742ba8fa05a332c9130deebe449d7fc6` | `sha256:c404c0cd1e08f389664b5381c2c038cf65bac9a3b725fc2b1882990636eb179b` |
| Temporal carrier-selection binding schema | `sha256:d252420507393d1d9816a0f20549faa8cf67c94bd1e2c10a3c509aadf4f3800a` | not applicable; a schema is retained as exact `CONTRACT_SCHEMA` bytes |
| Intervention carrier-selection binding instance | `sha256:9886aace0670b6a83f17cd33cbc67aa62fafcfd0ea873faed9194c2aaa07efe5` | `sha256:373a5f402ad077039946c1dfe7b972e4382d3c6a6805fbf0b271e4a0bc729bf1` |
| Temporal governed-command binding schema | `sha256:afda003df90e2787cfdc97f5561e3e5b098177a5add91556af2e935a3b9711db` | not applicable; a schema is retained as exact `CONTRACT_SCHEMA` bytes |
| Operation-claim draft command binding instance | `sha256:0909ec653cb99a94cd1b35afaf2d386258aac671c5f730960ed485df8a4b8f2e` | `sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1` |

The repository file digest protects the reviewed candidate file. The canonical
instance digest is the prospective RuntimeBundle content identity under
`OFARM_CANONICAL_JSON_V1`. They are different identities and may not be
substituted for one another.

This Phase A contract does not place these candidate instances in a
RuntimeBundle. Their present `CANDIDATE_INACTIVE` status remains authoritative.
It only fixes the future carrier vocabulary and the exact allowed identity set.
Promotion of any allowed identity would need a separate activation decision.

## Required schema relationship

Each temporal-governance instance requires two distinct RuntimeBundle
components before production use can be proposed:

1. its exact schema as a `CONTRACT_SCHEMA` component; and
2. its exact instance as a `TEMPORAL_GOVERNANCE_ARTIFACT` component.

The schema component owns structural validity. The governance-artifact
component owns the selected matrix or binding bytes. Neither substitutes for
the other.

The instance must pass complete Draft 2020-12 validation against the exact
schema component in the same RuntimeBundle. Its declared schema version,
logical reference, canonical bytes, byte length, and content digest must all
agree. A digest reference to bytes that are not retained as an exact component
is not RuntimeBundle closure.

The command binding's references to the temporal-coordinate contract, carrier
matrix, intervention selector binding, knowledge-position storage authority,
source contracts, and evidence contracts remain governed by that binding.
This carrier contract does not alter or re-interpret them.

## Authority map

- ADR 0002 owns `ValidCut`, `KnowledgeCut`, the independence of the two axes,
  the half-open interval rule, the temporal carrier matrix meanings, and the
  prohibition on capture-time substitution.
- The temporal-coordinate candidate owns the versioned cut vocabulary.
- The ADR 0002 carrier-matrix candidate owns the classified rows and window
  meanings.
- The intervention carrier-selection candidate owns its exact source
  contracts, matrix row, field paths, required time basis, and atomic refusal
  behavior.
- The operation-claim draft command candidate owns its exact command,
  admission, ordering, replay, outcome, and draft-only rules.
- Each exact schema owns validation of its corresponding instance.
- `RuntimeBundle` owns immutable component identity, canonical bytes, content
  digest, membership, and tenant-scoped provenance-root digest.
- This contract alone owns the meaning and closed admission rules of
  `TEMPORAL_GOVERNANCE_ARTIFACT`.
- The startup RuntimeBundle publisher may retain an already reviewed exact
  component set. Publication does not choose a tenant's command-time
  RuntimeBundle, authorize a command, or activate a route.
- A later, separately reviewed RuntimeBundle-selection authority must choose
  the exact sealed tenant bundle used by a governed command. Caller data,
  request payloads, headers, timestamps, or idempotency keys cannot choose it.
- A later, separately reviewed production authorization provider must decide
  `ASSERT_OPERATION_CLAIM` at `DRAFT_PREPARATION`.
- #192 retains sole authority over audit-runtime behavior.

## Invariants

- **TGRB-001 — Exact role.** A temporal matrix or binding instance uses only
  `TEMPORAL_GOVERNANCE_ARTIFACT`; no existing component role is reinterpreted.
- **TGRB-002 — Exact bytes.** The component digest is the SHA-256 of the exact
  `OFARM_CANONICAL_JSON_V1` instance bytes retained by the RuntimeBundle.
- **TGRB-003 — Global content only.** The component contains no tenant,
  principal, Party, request, batch, knowledge position, deployment secret, or
  mutable activation state and uses `GLOBAL_IMMUTABLE_CONTENT`.
- **TGRB-004 — Schema and instance both present.** A governance instance is
  incomplete unless its exact `CONTRACT_SCHEMA` is present in the same bundle.
- **TGRB-005 — Closed allowed identity set, not required closure.** Only the
  three artifact identities listed in this contract may use
  `TEMPORAL_GOVERNANCE_ARTIFACT` under version 0.1. Their eligibility does not
  require any RuntimeBundle or use of the role to contain all three. A later
  reviewed command and tenant RuntimeBundle-selection contract owns the exact
  required component closure for `COMMIT_OPERATION_CLAIM_DRAFT`.
- **TGRB-006 — No transitive omission.** Naming an instance digest from another
  component does not replace retaining that exact instance as its own
  component.
- **TGRB-007 — Candidate remains inactive.** Candidate status, manifest
  classification, and absence from active RuntimeBundles remain unchanged in
  Phase A.
- **TGRB-008 — Presence is provenance, not execution.** Component membership
  alone never opens a route, registers a command, selects a carrier at runtime,
  grants authority, allocates a knowledge position, or produces an output.
- **TGRB-009 — Tenant bundle remains exact.** A component is selected only
  through one sealed RuntimeBundle. Loose content rows and package files are
  inert.
- **TGRB-010 — Caller cannot select governance.** No caller field may supply or
  override the role, schema, matrix, row, binding, logical reference, component
  digest, or RuntimeBundle digest.
- **TGRB-011 — Production firewall.** No legacy Store, profile runtime, policy,
  gate, materializer, semantic route, or output module becomes an authority or
  dependency.
- **TGRB-012 — Audit separation.** The carrier defines no #192 event, receipt,
  failure route, or attribution.

## Required negative cases

Conformance for a future candidate package must refuse or prove unsupported:

- a temporal matrix or binding carried as `CONTRACT_SCHEMA`,
  `DRAFT_CONTRACT_SCHEMA`, `PROFILE_INSTANCE`, `REFERENCE_SOURCE`,
  `ADAPTER_SOURCE`, `VALIDATOR_SOURCE`, or `QUERY_OUTPUT_SOURCE`;
- a `TEMPORAL_GOVERNANCE_ARTIFACT` using exact-byte canonicalization,
  tenant placement, or any canonicalization or placement not fixed here;
- a component containing tenant, principal, Party, request, batch, knowledge
  position, credential, secret, or mutable activation data;
- an unlisted, duplicate, or differently versioned identity being admitted
  under `TEMPORAL_GOVERNANCE_ARTIFACT`; absence of one or more allowed
  identities is not a carrier-contract failure;
- a logical reference that differs from the exact instance identity;
- an absent schema component, a schema/instance version mismatch, incomplete
  Draft 2020-12 validation, or changed canonical instance bytes;
- a declared byte length or content digest that differs from the retained
  bytes;
- a digest-only reference whose exact instance bytes are not a component;
- loose global or tenant content being treated as selected without sealed
  RuntimeBundle membership;
- bundle membership being treated as a route, command registration,
  authorization decision, runtime selector call, profile activation,
  output permission, or semantic success;
- a caller-supplied component role, logical reference, artifact identity,
  digest, matrix, row, selector, command binding, or RuntimeBundle digest;
- admission of another carrier row, selector, command, channel, outcome, or
  artifact kind under version 0.1; and
- any production import from the legacy semantic or output surface.

## Non-goals

This contract does not:

- change `RuntimeComponentRole`, `runtime_bundle_components.json`, the
  RuntimeBundle model, publisher, repository, database constraints, migrations,
  roles, or privileges;
- add an active contract registry, promote a candidate, alter a frozen
  contract, change an ActiveArtifactSet, profile, Capability Manifest, or
  RuntimeBundle;
- choose or load a tenant RuntimeBundle;
- implement RuntimeBundle publication, selection, activation, hot reload,
  upgrade, rollback, or lifecycle behavior;
- implement a command, authorization provider, temporal selector call,
  knowledge-position allocation, route, materialization, current-state read,
  historical view, WINDOW behavior, output, or receipt;
- add another temporal matrix row or carrier meaning; or
- implement or change #192.

## Smallest coherent Phase A change

After approval, the smallest candidate-governance PR may contain only:

- one exact candidate schema for the closed
  `TEMPORAL_GOVERNANCE_ARTIFACT` role and its three admitted identities;
- one exact inactive candidate binding that records the role,
  canonicalization, placement, schema relationship, closed allowed identity
  set, and
  non-activation rules;
- this RFC in approved form;
- package manifest, digest, and ERRATA traceability; and
- focused conformance proving exactness and absence from every active
  RuntimeBundle, registry, profile, route, and production import closure.

That PR must not edit runtime code or any active RuntimeBundle authority.

## Verification

Phase A candidate verification must prove:

- complete Draft 2020-12 schema validity and exact schema-to-binding equality;
- exact role spelling, canonicalization, placement, allowed identities,
  non-requirement of all-three co-presence, schema relationship, invariants,
  negative cases, non-goals, and stop conditions;
- mutation of a role, placement, canonicalization, identity, schema
  relationship, activation posture, or admission of an unlisted identity is
  refused;
- the existing candidate schemas and instances remain byte-for-byte unchanged;
- no candidate artifact appears in `kernel/runtime_bundle_components.json`,
  an active contract registry, profile, ActiveArtifactSet, Capability Manifest,
  route, or production import closure;
- no database, migration, RuntimeBundle model/repository/publisher, application
  runtime, semantic runtime, materialization, output, legacy, or #192 file
  changes; and
- the package conformance gate and focused temporal-governance tests pass.

## Stop conditions

Runtime implementation of this role must not start until this Phase A contract
and its inactive candidate package are separately approved.

After that approval, implementation still stops if it would:

1. place any current `CANDIDATE_INACTIVE` artifact in an active RuntimeBundle;
2. promote or rewrite a temporal candidate without a separate versioned
   activation decision;
3. change database component-role constraints or publisher custody without a
   separately approved database boundary;
4. change an active RuntimeBundle catalog or production RuntimeBundle model
   without a separately approved RuntimeBundle-authority boundary;
5. choose the tenant's command-time RuntimeBundle digest;
6. connect the governed command or authorization provider;
7. open a route, profile, materialization, read, historical, WINDOW, or output
   surface; or
8. add #192 behavior.

The production RuntimeBundle-digest source for
`COMMIT_OPERATION_CLAIM_DRAFT` remains blocked until:

- temporal governance artifacts have a reviewed active carrier and promoted
  identities;
- a separately reviewed tenant-bound RuntimeBundle-selection contract defines
  who chooses the exact sealed bundle and when; and
- the production authorization-provider contract is approved.

Current-state reads and outputs remain blocked by their own output-governance
prerequisites.
