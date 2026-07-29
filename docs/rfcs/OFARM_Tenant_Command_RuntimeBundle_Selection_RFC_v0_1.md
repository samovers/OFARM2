# OFARM Tenant Command RuntimeBundle Selection — Phase A Contract v0.1

**Status:** Candidate, inactive, production-unbound

**Issue:** #176

**Schema version:** `ofarm.tenant-command-runtime-bundle-selection-binding.v0.1`

**Binding identity:** `ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1`

**Governed command:** `COMMIT_OPERATION_CLAIM_DRAFT`

**Schema file digest:** `sha256:56604a52465ffc027382e99dea96f2c9bc1bd2479cbaff30dec6bd39c08e6b3d`

**Binding file digest:** `sha256:1500ffbbfdf11207a6657848fce12618347f767578e55dc070bb282dc5775aac`

**Binding canonical length:** `13287` bytes

**Binding canonical digest:** `sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f`

## Decision

This contract fixes the one trusted source, timing, custody, and exact
command-required component closure for selecting a tenant RuntimeBundle for
`COMMIT_OPERATION_CLAIM_DRAFT`.

It is a Phase A governance contract only. It does not create the source,
activate a RuntimeBundle component role, select a bundle at runtime, connect
the governed command, or open a production semantic surface.

The primary trust boundary is:

> selection of one exact sealed tenant RuntimeBundle for one governed command

The intended implementation boundary after approval is limited to the
inactive candidate schema and binding, this RFC, package manifest and ERRATA
traceability, and focused conformance. Database, RuntimeBundle authority,
selection control, read-only selector, authorization-provider, and command
integration changes remain separate boundaries.

## Scope

Version 0.1 governs exactly:

- command `COMMIT_OPERATION_CLAIM_DRAFT`;
- command binding
  `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1`;
- tenant command-selection binding
  `ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1`;
- one immutable tenant-owned selection record per tenant and selection-binding
  version; and
- the exact sixteen components required by this command.

No other command, carrier, route, profile, output, current-state read,
historical view, or WINDOW behavior is admitted by this contract.

## Trusted selection source

The only trusted source of the RuntimeBundle digest is one immutable tenant
command-selection record selected by:

1. `TenantBinding.tenant_id`; and
2. the literal selection-binding identity fixed by this reviewed, versioned
   artifact.

The selection-binding identity is never taken from caller data. The selector
must not accept a binding identity, bundle digest, tenant identity, command
identity, component identity, matrix, row, schema, or source-contract choice
from a request, route, header, profile, environment, capability, principal,
timestamp, or idempotency value.

Publication, bundle existence, package order, timestamp order, newest-bundle
status, sole-bundle status, profile membership, and loose component rows do not
select a command-time RuntimeBundle.

Version 0.1 permits one immutable selection for each
`(tenantId, selectionBindingId)` pair. Changing the selection requires a new
reviewed selection-binding version. A mutable current pointer, hot reload,
upgrade, supersession, replacement, rollback, and deletion are unsupported.

## Future trusted selection record

The future record has identity:

```text
(tenantId, selectionBindingId)
```

Its authority-bearing fields are exactly:

```text
tenantId
selectionBindingId
selectionBindingCanonicalDigest
commandId
commandBindingId
commandBindingCanonicalDigest
runtimeBundleDigest
selectionBatchId
selectionKnowledgePosition
```

Their authority is fixed as follows:

- `tenantId` comes from the already trusted `TenantBinding`;
- `selectionBindingId`, `commandId`, and `commandBindingId` come from this
  reviewed binding, never caller data;
- the binding digests identify the exact reviewed canonical binding bytes;
- `runtimeBundleDigest` is chosen by a dedicated tenant command-selection
  authority;
- `selectionBatchId` identifies the separately governed atomic selection
  activation; and
- `selectionKnowledgePosition` is allocated by the governed tenant knowledge
  allocator and must precede the command's `Kbefore`.

The record is tenant-owned and immutable. Its future state machine is:

```text
ABSENT -- exact governed activation --> SEALED
SEALED -- exact retry ----------------> SEALED (no-op)
SEALED -- unequal reuse/update/delete/replacement --> REFUSED (no write)
```

This contract does not create that record, storage, allocator call, or
activation controller.

## Resolution timing and result

Resolution occurs after trusted tenant binding and before command admission,
exact replay evaluation, or governed-batch allocation.

The closed seam is:

```text
trusted TenantBinding + fixed reviewed selection binding
  -> TrustedCommandRuntimeBundle
  |  RUNTIME_BUNDLE_SELECTION_REFUSED_NO_WRITE
```

The refusal name is internal to the future selection seam. This contract adds
no public `RuntimeProblem` reason code. Selection refusal writes no batch,
draft, evidence, idempotency claim, result, receipt, or #192 audit behavior.
Mapping this internal refusal to any public result or existing reason code
remains unsupported until a separate authorization-order and output-governance
review. A selector or command implementation must not choose that mapping.

On success, the selected RuntimeBundle digest is used unchanged for:

- command admission;
- exact replay equality;
- governed-batch provenance;
- authorization and temporal evidence;
- command results.

A command cannot re-resolve, replace, or reinterpret the selected digest
during execution.

## Exact command-required component closure

The selected sealed RuntimeBundle must contain this exact
command-required component subset. The subset is not a statement that the
whole RuntimeBundle contains only these components. Unrelated components may
exist, but they have no authority to satisfy, replace, widen, or influence
this command.

All thirteen schema components use role `CONTRACT_SCHEMA`,
canonicalization `EXACT_BYTES_V1`, and placement
`GLOBAL_IMMUTABLE_CONTENT`.

| Identity | Exact byte length | Content digest |
| --- | ---: | --- |
| `contract:ofarm.temporal-coordinate.v0.1` | 3943 | `sha256:b81e4c7b0aacebb11ff8bf0d186cdb36150fade31180552b46f7be9e13c551eb` |
| `contract:ofarm.temporal-carrier-matrix.v0.1` | 3088 | `sha256:cdb5c09ec033cc3b4de1dea9eb383c499045d8a3bfc5b80fd7abeab579a566ed` |
| `contract:ofarm.temporal-carrier-selection-binding.v0.1` | 3340 | `sha256:d252420507393d1d9816a0f20549faa8cf67c94bd1e2c10a3c509aadf4f3800a` |
| `contract:ofarm.temporal-governed-command-binding.v0.1` | 13132 | `sha256:afda003df90e2787cfdc97f5561e3e5b098177a5add91556af2e935a3b9711db` |
| `contract:ofarm.commitingressrequest.v0.1` | 3405 | `sha256:397ec3a61ed572b14f9916bc9e7b316ff48150c743c6b7aa2eab94a3be3e8ffc` |
| `contract:ofarm.semanticeventenvelope.v0.1` | 4238 | `sha256:75662a6c4952a62b7e8f8e9de99c23c98899c692914a98ba4b752873f48bd1a4` |
| `contract:ofarm.executionrecordpayload.v0.1` | 20245 | `sha256:ca62f01d056794ee588d55c3f5df652fc039124b76af5631d417714bc7059ff0` |
| `contract:ofarm.authorizationdecisionrequest.v0.1` | 4666 | `sha256:a62c7b8a269130a4c3b618ab029ffada97597626131bd45e2335ff31e95880fa` |
| `contract:ofarm.authorizationdecisionresult.v0.1` | 5538 | `sha256:f6d0de06e1bc6b8fc7a3f991abf28f2a3242942b50834b97292fa8e00fdd0127` |
| `contract:ofarm.authorizationdecisiontrace.v0.1` | 3606 | `sha256:1cc9886c3a9787a76657753fb682dd29337f2b8485e51557607bb6736de1571d` |
| `contract:ofarm.promotiontrace.v0.1` | 4759 | `sha256:07c073fba6fa023e4463339a383d4b0d881be38c17d626ec7d27caaa688d4e3f` |
| `contract:ofarm.commitingressresult.v0.1` | 5362 | `sha256:55a21c697a651cdff6ce8d64dd7c29dd2afaa329047b4ebd55c94497a411e7d5` |
| `contract:ofarm.runtimeproblem.v0.1` | 1319 | `sha256:873dbeda2932d48a54e5d08d22f4031c6a86b44712a3cec85f1c1008f4d6e95b` |

All three governance instances use role
`TEMPORAL_GOVERNANCE_ARTIFACT`, canonicalization
`OFARM_CANONICAL_JSON_V1`, and placement `GLOBAL_IMMUTABLE_CONTENT`.

| Identity | Canonical byte length | Canonical content digest | Required schema |
| --- | ---: | --- | --- |
| `ofarm.temporal-carrier-matrix.adr0002.v0.1` | 9504 | `sha256:c404c0cd1e08f389664b5381c2c038cf65bac9a3b725fc2b1882990636eb179b` | `contract:ofarm.temporal-carrier-matrix.v0.1` |
| `ofarm.temporal-carrier-selection.intervention.v0.1` | 1814 | `sha256:373a5f402ad077039946c1dfe7b972e4382d3c6a6805fbf0b271e4a0bc729bf1` | `contract:ofarm.temporal-carrier-selection-binding.v0.1` |
| `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1` | 9614 | `sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1` | `contract:ofarm.temporal-governed-command-binding.v0.1` |

Each governance instance must validate completely against the corresponding
schema retained in the same bundle. A digest reference without the retained
component bytes is unsupported.

The carrier-governance binding and this selection binding are external
governance prerequisites. They are not additional
`TEMPORAL_GOVERNANCE_ARTIFACT` members. Adding either identity to that role
requires a new reviewed carrier version.

## Authority map

- `TenantBinding` owns the trusted tenant and principal relationship. It does
  not supply a RuntimeBundle digest.
- A future dedicated tenant command-selection authority owns creation of the
  immutable selection record.
- A future production selector may read the record only after tenant binding.
- `RuntimeBundle` owns seal state, exact retained bytes, membership, component
  identity, and the tenant-scoped bundle digest.
- The RuntimeBundle publisher owns publication of an already reviewed
  component set. Publication does not select a tenant command bundle.
- `ofarm.temporal-governance-runtime-bundle-carrier.v0.1` owns the closed role
  vocabulary and allowed temporal-governance identities.
- `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1` owns
  command admission, replay, ordering, outcomes, and draft-only behavior.
- The source and evidence schemas own their structures.
- The deployment image digest owns executable code identity.
- The governed tenant knowledge allocator owns knowledge positions.
- A future separately reviewed production authorization provider owns the
  authorization decision.
- #192 retains sole authority over audit-runtime behavior.

The selection controller must be separate from the RuntimeBundle publisher,
tenant binder, application runtime, worker, authorizer, registrar, and identity
controller. None of those authorities may infer or substitute a selection.

## Invariants

- **TCRS-001 — One command.** Version 0.1 applies only to
  `COMMIT_OPERATION_CLAIM_DRAFT`.
- **TCRS-002 — One trusted source.** Only the immutable tenant command-selection
  record may supply the RuntimeBundle digest.
- **TCRS-003 — Separate custody.** The authority that creates the selection
  record is separate from publication, binding, execution, authorization,
  registration, and identity control.
- **TCRS-004 — Bound tenant only.** Resolution uses the already trusted
  `TenantBinding.tenant_id`; caller or record aliases cannot replace it.
- **TCRS-005 — Prior governed selection.** The selection record is created only
  by a separately governed activation batch before command use.
- **TCRS-006 — Immutable versioned selection.** One tenant and binding version
  identifies one sealed record; change requires a new binding version.
- **TCRS-007 — Selection first.** Resolution completes before admission, replay,
  or batch allocation.
- **TCRS-008 — Sealed bundle only.** Loose content and unsealed bundles are
  never command authority.
- **TCRS-009 — Exact closure.** The selected bundle contains the exact sixteen
  command-required components with their fixed roles, identities,
  canonicalizations, placements, lengths, and digests.
- **TCRS-010 — Schema and instance.** Each governance instance and its exact
  schema are retained and complete validation succeeds.
- **TCRS-011 — One digest end to end.** One selected bundle digest flows
  unchanged through admission, batch provenance, evidence, and result.
- **TCRS-012 — Replay coupling.** Exact replay requires the same request digest
  and the same trusted selected RuntimeBundle digest.
- **TCRS-013 — Extra components are inert.** Unrelated bundle components do not
  satisfy, replace, widen, or influence the command.
- **TCRS-014 — No implicit selection.** Newest, sole, existing, published,
  profile-listed, or loosely available bundles are not selected.
- **TCRS-015 — Candidate inactivity.** These artifacts remain outside active
  production registries and RuntimeBundles.
- **TCRS-016 — Production firewall.** No legacy Store, profile runtime, policy,
  gate, materializer, semantic route, or output module becomes an authority or
  dependency.
- **TCRS-017 — Safe refusal.** Selection failure is atomic no-write refusal and
  cannot become accepted, promoted, materialized, qualified, published,
  output, or current truth.
- **TCRS-018 — Audit separation.** This contract adds no #192 event, receipt,
  failure route, or attribution.

## Required negative cases

Conformance must refuse or prove unsupported:

- selection before trusted tenant binding;
- caller-supplied tenant, bundle digest, binding identity, command identity,
  component identity, matrix, row, schema, or source-contract choice;
- selection from a capability, principal, profile, environment, header, route,
  timestamp, request order, package order, or idempotency value;
- newest-bundle, sole-bundle, publication, existence, or loose-component
  inference;
- an absent, mutable, cross-tenant, unbatched, deleted, replaced, or unequally
  reused selection record;
- a missing or unsealed RuntimeBundle;
- bundle, membership, identity, canonicalization, placement, byte-length, or
  digest mismatch;
- a missing, wrong-role, aliased, digest-only, or substituted required
  component;
- governance-instance validation failure;
- an unlisted or differently versioned temporal identity;
- an unrelated component affecting command admission, replay, authority,
  temporal selection, evidence, outcome, or output;
- selection changing during a command;
- replay under a different selected bundle digest;
- any write on selection refusal;
- a legacy Store, configuration, profile, or semantic runtime selecting;
- selection by the publisher, binder, application, worker, authorizer,
  registrar, or identity controller; and
- any added #192 behavior.

## Non-goals

This contract does not:

- add a database relation, migration, role, privilege, storage adapter, or
  selection controller;
- activate `TEMPORAL_GOVERNANCE_ARTIFACT` in the RuntimeBundle model, catalog,
  repository, publisher, or database;
- promote, replace, or rewrite any temporal candidate;
- change a frozen active contract, RuntimeBundle selection, profile,
  ActiveArtifactSet, Capability Manifest, or production registry;
- implement a production selector or connect `ApplicationRuntime`;
- implement the command, authorization provider, carrier selection,
  knowledge-position allocation, or governed activation;
- add a route, materialization, current-state read, historical view, WINDOW
  execution, qualification, output, receipt, promotion, hot reload, upgrade,
  supersession, or rollback;
- open another command or carrier row;
- import or modify the legacy semantic surface; or
- implement or change #192.

## Smallest coherent Phase A change

The approved candidate-governance package contains only:

- one exact inactive candidate schema;
- one exact inactive selection binding;
- this RFC;
- manifest, digest, and ERRATA traceability; and
- focused conformance proving exactness and non-activation.

No active authority changes with this package.

## Verification

Phase A verification must prove:

- complete Draft 2020-12 schema validity and exact schema-to-binding equality;
- exact command, binding identity, trusted source, lookup key, record fields,
  custody, state transitions, resolution timing, and no-write refusal;
- reproducible bytes, lengths, and digests for all sixteen required
  components;
- complete validation of all three temporal-governance instances against
  their required schemas;
- exact component role, identity, canonicalization, placement, schema
  relationship, and closure semantics;
- mutation of a trusted source, caller-selectability rule, record field,
  authority, transition, timing, component, digest use, refusal, candidate
  posture, unsupported behavior, or stop condition is rejected;
- unrelated components cannot influence the command;
- candidate artifacts and role remain absent from every active RuntimeBundle,
  registry, profile, route, production import closure, and legacy import
  closure;
- no database, migration, RuntimeBundle authority, selector, application
  runtime, command, route, materialization, output, receipt, profile, frozen
  contract, legacy, or #192 change; and
- the focused temporal-governance and package conformance gates pass.

## Stop conditions for later boundaries

After this inactive package is approved, implementation still stops before:

1. promoting, replacing, or rewriting any inactive temporal identity;
2. adding `TEMPORAL_GOVERNANCE_ARTIFACT` to the active RuntimeBundle model,
   database constraints, catalog, repository, or publisher;
3. changing command-binding schema-version extraction to support a top-level
   `const.schemaVersion`;
4. creating selection storage, selection-control custody, or a governed
   activation batch;
5. implementing a production read-only selector or adding any legacy import;
6. mapping selection refusal to any public result or existing reason code
   without a separate authorization-order and output-governance review;
7. implementing the production authorization provider;
8. integrating `COMMIT_OPERATION_CLAIM_DRAFT`; or
9. opening a route, profile, materialization, current-state read, historical
   view, WINDOW behavior, qualification, output, receipt, or #192 behavior.

Each item requires a separately reviewed trust boundary and PR. Database and
RuntimeBundle carrier/model work, selection-control storage, production
provider integration, and governed-command integration must not be combined.

Current-state reads and outputs remain blocked by their own output-governance
prerequisites.
