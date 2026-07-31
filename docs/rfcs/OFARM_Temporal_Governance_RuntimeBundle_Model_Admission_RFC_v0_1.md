# OFARM2 Temporal-Governance RuntimeBundle Model Admission — Phase A Contract v0.1

**Status:** architect-approved Phase A contract; documentation-only, pending
merge, and without implementation or activation effect

**Contract identity:**
`ofarm.temporal-governance-runtime-bundle-model-admission.issue176.v0.1`

**Date:** 2026-07-31

**Primary implementation ticket:** #176

**Primary trust boundary:** active RuntimeBundle model admission of exact
temporal-governance provenance components

**Intended future implementation PR boundary:** RuntimeBundle model vocabulary,
component validation, bundle validation, and focused tests only

## Decision

OFARM2 may not port `COMMIT_OPERATION_CLAIM_DRAFT` into production while the
active RuntimeBundle model cannot represent the exact temporal-governance
artifacts that govern that command.

After this contract is approved, one later Phase B PR may add exactly one
RuntimeBundle component role:

```text
TEMPORAL_GOVERNANCE_ARTIFACT
```

That role may admit only the three exact temporal-governance identities already
recorded as the current pre-deployment `GOVERNED_INACTIVE` decision:

1. `ofarm.temporal-carrier-matrix.adr0002.v0.1`;
2. `ofarm.temporal-carrier-selection.intervention.v0.1`; and
3. `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1`.

Model admission means only that `RuntimeComponent` and `RuntimeBundle` can
validate and retain those exact immutable provenance bytes under the closed
role. It does not add a component to a catalog, publish or persist a bundle,
select a tenant bundle, activate an artifact, authorize or register a command,
or open a production semantic surface.

The role's source contract, allowed identities, schema relationships, identity
fields, canonical digests, and lifecycle basis come only from the reviewed,
versioned artifacts pinned below. They are never taken from caller data.

This contract does not amend ADR 0002, any frozen active contract, any existing
temporal candidate, or the current decision-log entry.

## Reviewed authority pins

The future model implementation must pin these authorities:

- temporal carrier contract:
  `ofarm.temporal-governance-runtime-bundle-carrier.v0.1`;
- carrier contract repository digest:
  `sha256:391c8110029f004375e668e5e902864c0b4aaf6f650005abed8a206d4049e5b4`;
- current pre-deployment decision entry identity:
  `sha256:ed48914f77bedacdfce32fb621819da7df7701b54d7862477db0a49ceee5cdc6`;
- current pre-deployment decision entry exact file digest:
  `sha256:72a2319430eb1a74c2e99f9ef68aab5c17081b37390b4488b8187bb698ebde80`;
- approved decision-card digest:
  `sha256:aef1d628bb1b54c03f020aef5cec05c7ca7d1f00556004f89204ae13d416fa03`;
- decision-log contract:
  `ofarm.temporal-governance-decision-log.issue176-predeployment.v0.2`.

The `CANDIDATE_INACTIVE` value embedded in each immutable candidate instance
remains its creation-state attestation. The decision log separately owns the
current external `GOVERNED_INACTIVE` lifecycle decision. The model must not
rewrite either representation or infer a stronger state.

If the decision entry is superseded or ceases to be current before Phase B,
implementation stops until the new currentness chain and subject set receive a
fresh review.

## Closed model admission set

Every admitted component uses:

```text
role             = TEMPORAL_GOVERNANCE_ARTIFACT
canonicalization = OFARM_CANONICAL_JSON_V1
placement        = GLOBAL_IMMUTABLE_CONTENT
```

The admitted set is exactly:

| Logical reference and instance identity | Declared schema version | Identity field | Canonical byte length | Canonical content digest | Required schema component |
| --- | --- | --- | ---: | --- | --- |
| `ofarm.temporal-carrier-matrix.adr0002.v0.1` | `ofarm.temporal-carrier-matrix.v0.1` | `matrixId` | 9504 | `sha256:c404c0cd1e08f389664b5381c2c038cf65bac9a3b725fc2b1882990636eb179b` | `contract:ofarm.temporal-carrier-matrix.v0.1` |
| `ofarm.temporal-carrier-selection.intervention.v0.1` | `ofarm.temporal-carrier-selection-binding.v0.1` | `bindingId` | 1814 | `sha256:373a5f402ad077039946c1dfe7b972e4382d3c6a6805fbf0b271e4a0bc729bf1` | `contract:ofarm.temporal-carrier-selection-binding.v0.1` |
| `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1` | `ofarm.temporal-governed-command-binding.v0.1` | `bindingId` | 9614 | `sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1` | `contract:ofarm.temporal-governed-command-binding.v0.1` |

The required schema components are pinned separately because exact schema bytes
and canonical instance bytes have different identities:

| Schema component | Exact byte length | Exact content digest |
| --- | ---: | --- |
| `contract:ofarm.temporal-carrier-matrix.v0.1` | 3088 | `sha256:cdb5c09ec033cc3b4de1dea9eb383c499045d8a3bfc5b80fd7abeab579a566ed` |
| `contract:ofarm.temporal-carrier-selection-binding.v0.1` | 3340 | `sha256:d252420507393d1d9816a0f20549faa8cf67c94bd1e2c10a3c509aadf4f3800a` |
| `contract:ofarm.temporal-governed-command-binding.v0.1` | 13132 | `sha256:afda003df90e2787cfdc97f5561e3e5b098177a5add91556af2e935a3b9711db` |

For each component:

- `logicalRef` must equal the exact instance identity;
- the declared schema version and identity field must equal the table values;
- byte length and SHA-256 must equal the exact canonical instance bytes;
- the required schema must be retained in the same RuntimeBundle as exact
  `CONTRACT_SCHEMA` bytes; and
- complete Draft 2020-12 validation against that exact schema must succeed.

The repository file digest of a candidate is not its RuntimeBundle content
digest and cannot substitute for it.

The set is an allowed identity set, not a required component closure. A
RuntimeBundle or one use of the role need not contain all three identities.
The tenant command RuntimeBundle-selection contract remains the sole owner of
the exact component closure required by `COMMIT_OPERATION_CLAIM_DRAFT`.

## Authority map

- ADR 0002 owns `ValidCut`, `KnowledgeCut`, their independence, the half-open
  interval rule, temporal carrier meanings, and the ban on capture-time
  substitution.
- The current temporal decision-log entry owns the external lifecycle state of
  the three exact subject digests.
- `ofarm.temporal-governance-runtime-bundle-carrier.v0.1` owns the new role's
  meaning, canonicalization, placement, allowed identities, and
  schema-to-instance relationship.
- Each exact schema owns structural validation of its corresponding instance.
- The active RuntimeBundle model owns its closed role enum, component
  validation, canonical bytes, content digest, bundle membership, and bundle
  digest.
- This contract owns permission for a future model-only PR to recognize the
  one role under the exact rules above.
- `kernel/runtime_bundle_components.json` and its publisher retain authority
  over catalog membership. They remain unchanged and contain no temporal
  component under this contract.
- PostgreSQL constraints and `RuntimeBundleRepository` retain authority over
  persistence. They remain unchanged and continue to refuse the new role until
  a separate database boundary is approved.
- The tenant command RuntimeBundle-selection binding owns future command-time
  selection and exact command closure. It remains inactive and production
  unbound.
- The governed command binding owns command admission, replay, ordering,
  outcomes, and draft-only behavior. Model admission does not execute it.
- A separately reviewed production authorization provider must own
  `ASSERT_OPERATION_CLAIM` authorization at `DRAFT_PREPARATION`.
- #192 retains sole authority over audit-runtime behavior.

## Invariants

- **TGRMA-001 — One new role.** Phase B may add only
  `TEMPORAL_GOVERNANCE_ARTIFACT`; no existing role is reinterpreted.
- **TGRMA-002 — Closed identities.** Only the three exact identities and
  digests in this contract are model-admissible under version 0.1.
- **TGRMA-003 — Exact provenance.** Canonical bytes, byte length, content
  digest, logical reference, schema version, and identity field must all agree.
- **TGRMA-004 — Schema retained.** Each admitted instance requires its exact
  `CONTRACT_SCHEMA` component in the same bundle and complete validation.
- **TGRMA-005 — Global immutable content.** A temporal-governance component
  contains no tenant, principal, Party, request, batch, knowledge position,
  credential, secret, or mutable activation state.
- **TGRMA-006 — Eligibility is not closure.** The model must not require all
  three allowed identities merely because one uses the role.
- **TGRMA-007 — Profile neutrality.** Temporal provenance does not require,
  select, or modify a profile descriptor, manifest, policy, active artifact
  set, query plan, view, or output source.
- **TGRMA-008 — Presence is inert.** Model-valid component membership is not
  lifecycle promotion, current/default status, deployment, selection,
  authorization, command registration, route activation, materialization,
  qualification, publication, output, or current truth.
- **TGRMA-009 — Caller cannot choose governance.** Request data, headers,
  claims, profiles, environment values, timestamps, idempotency values, and
  route parameters cannot supply or override the role, identity, schema,
  matrix, row, binding, digest, or bundle.
- **TGRMA-010 — No persistence implication.** In-memory model support does not
  authorize database admission or repository persistence.
- **TGRMA-011 — Production firewall.** No legacy Store, profile runtime,
  policy, gate, materializer, semantic route, or output module becomes a
  temporal authority or dependency.
- **TGRMA-012 — Audit separation.** Model admission creates no #192 event,
  receipt, refusal mapping, tenant attribution, or delivery behavior.
- **TGRMA-013 — No dynamic authority discovery.** Runtime validation uses the
  exact reviewed rules compiled into the model boundary. It does not scan the
  package, query the decision log, consult an environment value, or accept a
  registry supplied by a caller.

## Required negative cases

Phase B verification must refuse or prove absent:

- an unknown role or any temporal instance carried under an existing role;
- an unlisted, differently versioned, duplicated, or aliased identity;
- caller-supplied identity, schema, matrix row, binding, digest, lifecycle
  state, or RuntimeBundle choice;
- non-canonical bytes, wrong placement, wrong length, wrong content digest,
  wrong logical reference, or a mismatched identity field;
- a repository file digest used as the canonical instance digest;
- a missing schema, wrong schema role, changed schema bytes, schema-version
  mismatch, partial validation, or validation failure;
- a digest-only reference whose exact instance bytes are not retained;
- requiring all three eligible identities in every RuntimeBundle or role use;
- an unrelated component influencing temporal meaning or command authority;
- component membership being treated as artifact activation, command
  registration, authorization, selection, replay success, materialization,
  qualification, output, or current truth;
- a temporal component added to the active catalog or loaded from a caller,
  profile, package scan, newest-file rule, or environment configuration;
- persistence of the new role through current PostgreSQL constraints or
  repository code;
- modification of a frozen contract, candidate artifact, decision-log entry,
  active profile authority, or lifecycle record; and
- any import from the legacy semantic/output surface or any #192 behavior.

## Non-goals

This Phase A contract does not:

- change `RuntimeComponentRole`, `RuntimeComponent`, `RuntimeBundle`, the
  component catalog, publisher, repository, database, migrations, roles, or
  privileges;
- add a schema, candidate binding, manifest entry, digest record, ERRATA
  promotion, active registry entry, profile component, or RuntimeBundle
  component;
- promote, supersede, replace, or rewrite any temporal identity or decision;
- publish, persist, choose, activate, upgrade, roll back, or hot-reload a
  RuntimeBundle;
- create tenant command-selection storage or selection-control custody;
- implement a production selector, authorization provider, temporal command,
  route, materialization, current-state read, historical view, WINDOW
  behavior, qualification, output, or receipt;
- change command-binding schema-version extraction;
- open another temporal carrier row or command; or
- implement or change #192.

## Smallest coherent Phase A change

The contract-review PR contains only this document.

It must not include a schema, candidate artifact, manifest or ERRATA change,
test inventory change, model code, catalog entry, migration, repository change,
runtime integration, route, output, or decision-log entry.

After explicit approval, the smallest coherent Phase B model PR may contain
only:

- the new closed `RuntimeComponentRole` enum value;
- exact component validation for the three admitted identities;
- exact same-bundle schema validation before the existing profile-selection
  branch;
- focused model and bundle negative tests; and
- the mechanically regenerated test inventory.

That Phase B PR must not change the database, catalog, publisher, repository,
selection authority, command runtime, routes, outputs, legacy surface, or
#192.

## Verification

Phase A review must verify:

- the authority pins and three admitted rows match the merged carrier,
  promotion, and decision-log artifacts byte-for-byte;
- the contract distinguishes model admission from lifecycle promotion,
  component closure, catalog membership, persistence, selection, execution,
  and output;
- authority, custody, caller-data refusal, production firewall, and #192
  separation are explicit;
- future Phase B scope is limited to the active RuntimeBundle model and focused
  verification;
- only this RFC changes; and
- `python3 conformance/ofarm_pkg_contract_check.py` and `git diff --check`
  pass.

## Stop conditions

Phase B model work must not start until this exact contract is explicitly
approved.

Even after approval, implementation stops before editing another authority:

1. PostgreSQL role constraints, migrations, privileges, or
   `RuntimeBundleRepository` require a separate database/persistence contract.
2. `kernel/runtime_bundle_components.json`, publisher custody, package loading,
   or active bundle contents require a separate catalog/publication contract.
3. Tenant selection storage, its activation controller, or knowledge-position
   allocation require a separate selection-control contract.
4. A production read-only tenant bundle selector requires its own
   implementation boundary and approved lifecycle posture.
5. Authorization-provider integration and command integration remain separate
   boundaries.
6. Public refusal mapping, results, receipts, current-state reads, historical
   views, WINDOW behavior, materialization, qualification, and outputs remain
   blocked by their own reviewed contracts.
7. Any need to change the current decision entry, admitted identity set,
   carrier matrix, selector, command binding, or frozen active contract
   requires a new versioned contract.
8. Any #192 change remains outside #176.

The production semantic surface remains closed throughout this boundary.
