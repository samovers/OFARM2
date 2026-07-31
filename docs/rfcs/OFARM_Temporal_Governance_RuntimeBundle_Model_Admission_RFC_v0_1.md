# OFARM2 Temporal-Governance RuntimeBundle Model Admission — Phase A Contract v0.1

**Status:** amended proposed Phase A contract; documentation-only, awaiting
re-review and explicit approval, and without implementation or activation
effect

**Contract identity:**
`ofarm.temporal-governance-runtime-bundle-model-admission.issue176.v0.1`

**Date:** 2026-07-31

**Primary implementation ticket:** #176

**Primary trust boundary:** active RuntimeBundle model admission of exact
temporal-governance provenance components

**Intended future implementation PR boundary:** RuntimeBundle model vocabulary,
component validation, bundle validation, and focused tests only

## Problem and goal

The active RuntimeBundle model has no role or validation path for retaining the
three exact temporal-governance provenance components. A future governed
command therefore cannot bind those reviewed bytes into its immutable runtime
provenance without either misusing an existing role or widening another
authority.

This contract establishes one closed, model-only admission rule for those
three identities. It does not place them in a bundle or give them lifecycle,
selection, command, or output effect.

## Learning value

The boundary demonstrates that temporal governance can become exact,
content-addressed RuntimeBundle provenance while remaining inert and separate
from lifecycle currentness, command closure, publication, persistence,
selection, authorization, execution, outputs, legacy behavior, and #192.

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

## Mandatory separate prerequisite

Review 4826614068 demonstrated that the governed-command schema cannot enter
the current RuntimeBundle model. Its version is declared at top-level
`const.schemaVersion`, while `_contract_schema_version(...)` currently accepts
only `properties.schemaVersion.const`.

That separate trust boundary is governed by:

- contract:
  `ofarm.runtime-bundle-contract-schema-version-extraction.issue176.v0.1`;
- Phase A contract PR: #265; and
- future implementation boundary: the Phase B PR explicitly authorized by the
  approved #265 contract.

This contract neither duplicates nor implements that extraction rule. Phase B
for this temporal model-admission contract must not begin until the #265
contract is approved and its separate Phase B implementation is merged.

If that prerequisite changes the supported declaration forms, logical-reference
rule, owning model seam, or refusal behavior described here, this contract
must return for amendment before implementation.

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
- The separate contract
  `ofarm.runtime-bundle-contract-schema-version-extraction.issue176.v0.1`
  owns extraction of one schema version from exact retained schema bytes. It
  does not own temporal identity eligibility.
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

## Trust model

### Protected assets

- the exact relationship among each temporal-governance instance, its logical
  identity, canonical bytes, digest, declared schema, and retained schema
  component;
- the closed RuntimeBundle role vocabulary and the three-identity eligibility
  set;
- RuntimeBundle component and bundle identity;
- the distinction between model eligibility, lifecycle governance, component
  closure, publication, persistence, selection, and execution; and
- the production-versus-legacy firewall and closed production semantic
  surface.

### Trusted components and authorities

- the reviewed authority pins and closed rows in this contract;
- the exact carrier, selector, governed-command, schema, promotion, and
  decision-log artifacts named by those pins;
- the separately approved schema-version extraction prerequisite;
- `RuntimeComponent` for exact canonical bytes, digest, role, placement,
  logical-reference, schema-version, and identity-field validation;
- `RuntimeBundle.create(...)` and bundle semantic validation for same-bundle
  schema retention and complete instance validation; and
- the unchanged external authorities in the authority map for lifecycle,
  catalog, persistence, tenant selection, authorization, execution, and #192.

### Untrusted actors and inputs

- all component bytes, logical references, roles, placements, and component
  tuples before model validation;
- unknown, aliased, changed, malformed, or partially validated temporal
  artifacts and schemas;
- request data, headers, claims, profiles, environment values, timestamps,
  routes, idempotency values, and caller-selected registries; and
- component presence offered as proof of lifecycle currentness, deployment,
  command authority, or output eligibility.

### Excluded compromise capabilities

Arbitrary in-process or private-field mutation, compromised Python or
third-party validation dependencies, concurrent filesystem mutation during one
builder operation, compromised repository or publisher custody, database or
operator compromise, and cryptographic hash compromise are outside this
boundary.

Local source substitution before component construction remains an untrusted
input and must fail unless the resulting exact canonical bytes satisfy the
closed identity row, digest, schema relationship, and complete validation.
This model boundary does not decide whether an otherwise valid component is
published, persisted, selected, or lifecycle-current.

## State machine and ordering

The future model path has these states:

```text
UNTRUSTED_SELECTED_BYTES
  -> EXACT_COMPONENT_VALID
  -> SAME_BUNDLE_SCHEMA_BOUND
  -> MODEL_ADMISSIBLE_INERT
```

Any failure transitions directly to `REFUSED_NO_BUNDLE`. There is no state in
which a temporal-governance component is partially admitted.

Validation order is fixed:

1. construct every `RuntimeComponent` from selected bytes;
2. require the exact new role, canonical JSON, global immutable placement,
   one listed logical identity, its declared schema version and identity
   field, exact byte length, and exact canonical content digest;
3. canonically order components and refuse duplicate component identities;
4. for each temporal-governance component, locate the one exact
   `CONTRACT_SCHEMA` component required by its closed row;
5. require that schema component's exact logical reference, byte length, and
   content digest;
6. complete Draft 2020-12 validation of the instance against those retained
   exact schema bytes;
7. complete existing bundle semantic validation; and
8. return one immutable RuntimeBundle whose temporal membership remains inert.

Temporal schema binding and validation must occur inside
`_validate_runtime_bundle_semantics(...)` before its existing
profile-selection branch can return. The constructor may compute candidate
canonical identity bytes and a digest, but no RuntimeBundle object is returned
and no external side effect occurs until every semantic check succeeds.

No database transaction, publication, persistence, lifecycle transition,
selection, authorization, command execution, route, output, or audit write
exists in this boundary. There is therefore no external time-of-check/time-of-use
window to govern here.

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
- Phase B beginning, or TGRMA-004 being claimed as satisfied, before the #265
  contract is approved and its separate Phase B implementation is merged;
- a schema-version extraction change added to this temporal model-admission
  boundary; and
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
- change contract-schema version extraction governed separately by
  `ofarm.runtime-bundle-contract-schema-version-extraction.issue176.v0.1`;
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

## Proposed architecture

After the separate schema-version extraction prerequisite is implemented,
Phase B may make one direct RuntimeBundle model change:

1. add `TEMPORAL_GOVERNANCE_ARTIFACT` to the closed
   `RuntimeComponentRole` enum;
2. define one immutable, compiled three-row rule set containing the exact
   identity, schema version, identity field, byte length, canonical digest,
   and required schema component pinned above;
3. route the new role through one focused temporal-governance component
   validator from `_validate_runtime_component_semantics(...)`;
4. permit that role through the existing explicit component-spec construction
   path without adding it to `RuntimeBundleBuilder.from_manifest(...)`, the
   checked-in catalog, or active package-loading configuration;
5. call one focused same-bundle schema validator from
   `_validate_runtime_bundle_semantics(...)` before the existing
   profile-selection branch; and
6. add focused tests for every invariant and negative case.

The component validator proves row membership and exact component identity.
The bundle validator proves exact schema retention and complete Draft 2020-12
instance validation. Neither helper reads a file path, package registry,
decision log, environment value, request, profile, database, or network
source.

## Elegance audit

- Runtime sources of allowed temporal identity truth: one immutable compiled
  three-row rule set.
- Authoritative validation transitions: component validation and same-bundle
  schema validation, each owning a distinct necessary question.
- Dynamic registries, configuration switches, plugin hooks, and compatibility
  aliases introduced: none.
- Mutable state introduced: none.
- Existing fields duplicated: none beyond the deliberate cross-check among
  logical identity, declared schema version, identity field, digest, and exact
  retained schema.
- Existing authority or fallback to delete: none; no temporal model path
  exists yet.

A clean RuntimeBundle rewrite is not justified. One enum member, one closed
rule set, two focused validation seams, and tests are smaller and clearer than
a temporal subsystem or generalized plugin mechanism.

## Pull request boundary

This amended Phase A PR changes only this RFC.

The future Phase B PR may change only:

- `kernel/runtime_bundle.py`;
- `kernel/tests/test_runtime_bundle.py`; and
- mechanically required test inventory or baseline metadata.

It depends on the approved #265 contract and its merged separate Phase B
implementation. It must not stack schema-version extraction changes into the
temporal model-admission branch.

Reviewers must not require catalog membership, publisher or repository
custody, database admission, tenant selection, authorization, command
integration, routes, outputs, current-state reads, historical or WINDOW
behavior, legacy changes, or #192 behavior from this PR or its Phase B.

Later boundaries remain tracked by #176. They are prerequisites or Follow-ups,
not reasons to combine authorities here.

## Provisional design record

Not provisional.

The role and its three-row allowed identity set are versioned and closed.
Widening the role, changing any row, or changing an authority pin requires a
new reviewed contract rather than a compatibility hook.

## Traceability and verification

The future Phase B implementation must reproduce this table before editing:

| Invariant | Owning model function/type | Supported construction path | Required negative test | Acceptance evidence | Smallest verification command |
| --- | --- | --- | --- | --- | --- |
| TGRMA-001 | `RuntimeComponentRole`, `RuntimeComponentSpec.from_document(...)`, `RuntimeBundleBuilder._component_from_spec(...)` | direct component and explicit builder spec | unknown role and temporal bytes under an existing role refuse | focused enum/spec tests | `python3 -m pytest -q kernel/tests/test_runtime_bundle.py -k temporal_governance` |
| TGRMA-002 | proposed immutable three-row rule set and temporal component validator | `RuntimeComponent.from_selected_bytes(...)` and explicit builder spec | unlisted, aliased, or differently versioned identity refuses | one acceptance case per row plus mutations | `python3 -m pytest -q kernel/tests/test_runtime_bundle.py -k temporal_governance` |
| TGRMA-003 | `RuntimeComponent`, temporal component validator | direct component and builder | bytes, length, digest, logical ref, schema version, or identity-field mismatch refuses | exact-row and mutation tests | `python3 -m pytest -q kernel/tests/test_runtime_bundle.py -k temporal_governance` |
| TGRMA-004 | `_contract_schema_version(...)` under the separate prerequisite and proposed same-bundle validator | `RuntimeBundle.create(...)` and builder | missing, wrong-role, changed, ambiguous-version, or validation-failing schema refuses | prerequisite top-level-version regression plus three schema-bound acceptance cases | `python3 -m pytest -q kernel/tests/test_runtime_bundle.py -k temporal_governance` |
| TGRMA-005 | temporal component validator | direct component and builder | tenant, principal, request, batch, position, credential, secret, or mutable lifecycle field changes exact bytes and refuses | field-injection mutation tests | `python3 -m pytest -q kernel/tests/test_runtime_bundle.py -k temporal_governance` |
| TGRMA-006 | proposed same-bundle validator | `RuntimeBundle.create(...)` and builder | each single allowed identity can form a model-valid schema-bound bundle without the other two | three independent bundle tests | `python3 -m pytest -q kernel/tests/test_runtime_bundle.py -k temporal_governance` |
| TGRMA-007 | `_validate_runtime_bundle_semantics(...)` | direct bundle and builder | temporal membership neither requires nor changes profile components | profile-free and unchanged-profile bundle tests | `python3 -m pytest -q kernel/tests/test_runtime_bundle.py -k temporal_governance` |
| TGRMA-008 | `RuntimeBundle` model only; unchanged external authorities | direct bundle | component presence produces no activation, selection, execution, output, or current-truth state | inert bundle assertion plus boundary diff | `python3 conformance/ofarm_pkg_contract_check.py` |
| TGRMA-009 | immutable rule set and temporal component validator | direct component and builder | caller-shaped identity, schema, row, binding, or digest substitution refuses | mutation tests and absence of runtime input seam | `python3 -m pytest -q kernel/tests/test_runtime_bundle.py -k temporal_governance` |
| TGRMA-010 | unchanged repository and database authorities | all model paths | current persistence vocabulary remains unchanged | boundary diff and existing repository tests | `git diff --exit-code origin/main...HEAD -- kernel/runtime_bundle_repository.py kernel/migrations` |
| TGRMA-011 | production import and architecture guards | all model paths | no legacy Store, profile gate, materializer, route, or output dependency | architecture conformance | `python3 conformance/ofarm_pkg_contract_check.py` |
| TGRMA-012 | unchanged #192 authority | all model paths | model admission emits no audit event, receipt, or delivery behavior | boundary diff and audit isolation | `python3 conformance/ofarm_pkg_contract_check.py` |
| TGRMA-013 | immutable compiled rules and focused validators | direct component and builder | package scan, environment registry, newest-file, or caller registry cannot widen admission | unknown-identity tests and boundary diff | `python3 -m pytest -q kernel/tests/test_runtime_bundle.py -k temporal_governance` |

Phase A review must verify:

- the authority pins and three admitted rows match the merged carrier,
  promotion, and decision-log artifacts byte-for-byte;
- #265 is named as a separate prerequisite and this PR contains none of its
  implementation;
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

Future Phase B verification is:

- `python3 -m pytest -q kernel/tests/test_runtime_bundle.py -k temporal_governance`;
- the complete `kernel/tests/test_runtime_bundle.py` module;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- `git diff --check`; and
- review of the exact head against this traceability table.

## Open decisions and review disposition

### Open decisions

None inside this trust boundary.

PR #265 is a mandatory external prerequisite, not an undecided alternative.
Its contract must be approved and its separate implementation merged before
this contract's Phase B can begin.

### Review disposition

- Blockers: review 4826614068 requires re-review of these amendments at the
  new exact head; no other design Blocker is known.
- Follow-ups: #265 and its future Phase B implementation are mandatory
  prerequisites for this contract's Phase B. All persistence, catalog,
  selection, authorization, command, route, output, historical or WINDOW, and
  #192 work remains in later separate boundaries under #176 or #192.
- Preferences: none.

### Merge stop rule

This amended Phase A contract must not be treated as approved or merged until
the designated architect explicitly approves the amended contract after
review and no demonstrated Blocker remains.

After approval, the future Phase B PR must not merge until every invariant has
the acceptance evidence in the traceability table. New ideas, Preferences, and
out-of-boundary hardening become Follow-ups and do not expand that PR.

## Stop conditions

Phase B model work must not start until:

1. this exact amended contract is explicitly approved;
2. the #265 contract is explicitly approved; and
3. the separate Phase B implementation authorized by #265 is merged.

Even after approval, implementation stops before editing another authority:

1. Contract-schema version extraction beyond the merged #265 implementation
   requires its own new contract amendment and PR.
2. PostgreSQL role constraints, migrations, privileges, or
   `RuntimeBundleRepository` require a separate database/persistence contract.
3. `kernel/runtime_bundle_components.json`, publisher custody, checked-in
   package-loading configuration, or active bundle contents require a separate
   catalog/publication contract.
4. Tenant selection storage, its activation controller, or knowledge-position
   allocation require a separate selection-control contract.
5. A production read-only tenant bundle selector requires its own
   implementation boundary and approved lifecycle posture.
6. Authorization-provider integration and command integration remain separate
   boundaries.
7. Public refusal mapping, results, receipts, current-state reads, historical
   views, WINDOW behavior, materialization, qualification, and outputs remain
   blocked by their own reviewed contracts.
8. Any need to change the current decision entry, admitted identity set,
   carrier matrix, selector, command binding, or frozen active contract
   requires a new versioned contract.
9. Any #192 change remains outside #176.

The production semantic surface remains closed throughout this boundary.
