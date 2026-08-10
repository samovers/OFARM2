# OFARM2 Temporal RuntimeBundle Catalog and Publication Admission — Phase A Contract v0.1

**Status:** proposed Phase A design; documentation-only and without active-
catalog, publication, selection, runtime, deployment, or production effect.
Approval state is owned by the active same-task decision workflow, not by this
status line.

**Issue:** #176

**Contract identity:**
`ofarm.temporal-runtime-bundle-catalog-publication-admission.issue176.v0.1`

**Reviewed base:** `25526bfea11210aebe92b6bb7d94c5923d304a5a`

**Primary trust boundary:** choosing the exact component set for one
tenant-sealed temporal command RuntimeBundle and invoking the existing
publisher custody for that exact set

**Phase A pull-request boundary:** this RFC only

## 1. Problem and goal

The accepted #176 foundation now has four separate capabilities:

1. the active `RuntimeBundle` model admits exactly three governed temporal
   identities under `TEMPORAL_GOVERNANCE_ARTIFACT` and requires their exact
   schemas;
2. the current pre-deployment lifecycle decision records those three exact
   identities as `GOVERNED_INACTIVE`;
3. production PostgreSQL admits the temporal role and can retain exact global
   content through `ofarm.retain_runtime_content(text,bytea)`; and
4. `ofarm.publish_runtime_bundle(uuid,text,jsonb)` can atomically seal a
   model-valid component set for one registered tenant.

None of those authorities chooses a complete temporal RuntimeBundle or
authorizes a control path to publish it. The tenant command-selection binding
fixes an exact sixteen-component command-required subset, but deliberately
states that it is not the whole-bundle publication decision. The active SI
component catalog contains no temporal component and must remain closed.

Without this boundary, a future caller would have to invent one of the most
important authority decisions: which files become the whole bundle, whether
extra components are allowed, which tenant receives the seal, and whether
retention and sealing are one atomic operation.

This contract establishes exactly one answer:

> For v0.1, the complete temporal command RuntimeBundle is all and only the
> sixteen exact global components already fixed by the reviewed tenant
> command-selection binding. A later isolated control adapter may authenticate
> that fixed catalog, construct the bundle through the existing model, and
> retain and seal it for one explicitly chosen registered tenant in one
> transaction.

This Phase A change does not implement that adapter and does not publish a
bundle.

## 2. Learning value

The contract demonstrates that the existing model and database foundation are
sufficient for exact publication without widening the active catalog, adding a
new schema or service, or combining publication with tenant selection. It
removes the remaining composition ambiguity before any bytes are retained for
a real tenant.

## 3. Decision

### 3.1 One fixed source catalog

The source catalog is the exact `requiredComponentClosure.components` array in:

```text
contracts/candidates/temporal_runtime_bundle_selection/
OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json
```

The authority is pinned as:

```text
binding identity:
  ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1
repository bytes:
  15,993 bytes
  sha256:1500ffbbfdf11207a6657848fce12618347f767578e55dc070bb282dc5775aac
canonical binding bytes:
  13,287 bytes
  sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f
schema bytes:
  17,252 bytes
  sha256:56604a52465ffc027382e99dea96f2c9bc1bd2479cbaff30dec6bd39c08e6b3d
```

This contract changes the meaning of no row in that binding. It makes one new,
closed publication decision: the existing sixteen-row command-required subset
is also the complete v0.1 temporal bundle. No seventeenth component and no
unrelated current catalog component is permitted.

The selection binding remains `CANDIDATE_INACTIVE`, production-unbound, and
outside every RuntimeBundle and active registry. This contract permits only an
isolated future publisher to authenticate its exact reviewed rows as the source
catalog. It does not activate the binding itself or make the binding a bundle
component.

The binding's source paths, roles, logical identities, canonicalization rules,
placements, byte lengths, content digests, schema relationships, command
identity, source-contract identity, matrix identity, and row identities are
fixed by that reviewed, versioned binding. They are never taken from caller
data. This RFC does not create a second row registry.

The sixteen identities are:

| Role | Exact identities | Count |
| --- | --- | ---: |
| `CONTRACT_SCHEMA` | `contract:ofarm.temporal-coordinate.v0.1`; `contract:ofarm.temporal-carrier-matrix.v0.1`; `contract:ofarm.temporal-carrier-selection-binding.v0.1`; `contract:ofarm.temporal-governed-command-binding.v0.1`; `contract:ofarm.commitingressrequest.v0.1`; `contract:ofarm.semanticeventenvelope.v0.1`; `contract:ofarm.executionrecordpayload.v0.1`; `contract:ofarm.authorizationdecisionrequest.v0.1`; `contract:ofarm.authorizationdecisionresult.v0.1`; `contract:ofarm.authorizationdecisiontrace.v0.1`; `contract:ofarm.promotiontrace.v0.1`; `contract:ofarm.commitingressresult.v0.1`; `contract:ofarm.runtimeproblem.v0.1` | 13 |
| `TEMPORAL_GOVERNANCE_ARTIFACT` | `ofarm.temporal-carrier-matrix.adr0002.v0.1`; `ofarm.temporal-carrier-selection.intervention.v0.1`; `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1` | 3 |

Every component uses `GLOBAL_IMMUTABLE_CONTENT`. The thirteen schemas use
`EXACT_BYTES_V1`. The three governance artifacts use
`OFARM_CANONICAL_JSON_V1` and are retained and identified by their canonical
bytes, not by their pretty-printed repository bytes.

The thirteen schema components are exact structural validation dependencies
required by the accepted RuntimeBundle model and selection binding. Their
membership does not independently promote a schema, make it current/default,
or place it in an active contract registry.

### 3.2 Exact derived bundle identity

The existing `RuntimeBundle` model canonically sorts the sixteen components by
`(role, logicalRef)` and derives this exact identity:

```text
schemaVersion:      ofarm.runtime-bundle.local.v1
canonicalization:   OFARM_CANONICAL_JSON_V1
component count:    16
document bytes:     4,510
bundle digest:      sha256:c774100b13ad7d3f353148eeceeabd319167846825c7392ebbaca1f4ba62faea
```

Those values are derived acceptance evidence. They do not replace component
validation. A later implementation must reconstruct them from the exact source
catalog and exact selected bytes on every call and refuse if the result differs.

### 3.3 Current lifecycle prerequisite

Publication is lawful only while the exact three temporal governance subjects
remain the current pre-deployment `GOVERNED_INACTIVE` decision.

The current entry is:

```text
path:
  governance/temporal-decision-log/
  ed48914f77bedacdfce32fb621819da7df7701b54d7862477db0a49ceee5cdc6.json
repository bytes:
  4,880 bytes
  sha256:72a2319430eb1a74c2e99f9ef68aab5c17081b37390b4488b8187bb698ebde80
entry identity:
  sha256:ed48914f77bedacdfce32fb621819da7df7701b54d7862477db0a49ceee5cdc6
decision:
  PROMOTE_GOVERNED_INACTIVE
```

A later implementation must authenticate that exact entry and require that no
other decision-log entry exists or supersedes it. Missing, changed, additional,
ambiguous, or superseding lifecycle evidence refuses before database effects.
This is a closed pre-deployment rule, not a general lifecycle engine.

Publishing the exact subjects does not reinterpret `GOVERNED_INACTIVE` as
active, current/default, deployed, executable, output-eligible, or
production-ready. The decision entry's statement that its lifecycle decision
itself has no RuntimeBundle effect remains true; this separate contract is the
only proposed authority for the later publication effect.

### 3.4 One closed publication operation

After this RFC merges as the reviewed design and after the separate
conformance prerequisite in section 10 is approved, implemented, and merged,
one draft Phase B PR may be created inside section 11.2's allowlist. Only a
complete live decision card naming that already-created PR and a later exact
same-task user approval under the active pre-deployment workflow may authorize
implementation. The resulting adapter may expose one operation equivalent to:

```text
publish_commit_operation_claim_draft_temporal_runtime_bundle(
    connection,
    tenant_id,
) -> exact bundle digest
```

The API accepts no catalog path, binding identity, component list, source path,
role, logical reference, content digest, bundle digest, command identity,
matrix identity, carrier row, profile, environment selector, request, route,
principal, selection record, or activation input.

`tenant_id` must be a non-nil UUID explicitly chosen by the trusted
pre-deployment control operator. It is not inferred from a request, credential
subject, profile, newest or sole bundle, tenant alias, registration order, or
existing selection. The database remains responsible for requiring that this
exact UUID names a registered tenant.

The connection must be an idle connection authenticated as the existing
`ofarm_runtime_bundle_control_login`. Application, worker, binder, selection,
authorization, and legacy credentials are unsupported. The operation reads no
credential, DSN, tenant, catalog, or source override from the environment.

The adapter is an isolated control module. It is not imported by
`deployment.postgresql`, `kernel.api`, `kernel.application_runtime`, the legacy
roots, an application, a worker, a route, or a startup hook. This contract
creates no CLI, service, automatic fleet loop, or deployment integration.

## 4. Reviewed authorities and exact current state

| Authority | Exact identity | Authority retained |
| --- | --- | --- |
| Frozen architecture report | `reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md`; 96,406 bytes; `sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256` | claim limits and governed runtime surfaces |
| Database architecture | `docs/adr/0001-tenancy-and-schema-migrations.md`; 147,112 bytes; `sha256:bc49e566ddbdf98868162aa7ccca0940fa76fca1bfaaa261c8c831dbb5515a4d` | publisher custody, global and tenant content carriers, bundle sealing, and startup-only posture |
| Temporal architecture | `docs/adr/0002-valid-time-and-knowledge-time.md`; 61,427 bytes; `sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796` | independent valid and knowledge time, half-open intervals, and inactive-content semantics |
| Tenant capability architecture | `docs/adr/0003-tenant-capability-trust-and-binder.md`; 93,419 bytes; `sha256:b188f4d60e46887fde4231e73bb00adb9bd70b75e807627e8a3906389a0fa5be` | trusted tenant binding and capability boundaries; not publisher target choice |
| Python source architecture | `ofarm.architecture-python-source-snapshot-admission.issue176.v0.1`; complete RFC 82,758 bytes; `sha256:6e4307077525f2bbb48992fa4c652ab75d279875063bd715cf21dc1f1d3216d5` | exact production and legacy import-graph evidence |
| RuntimeBundle model | `ofarm.temporal-governance-runtime-bundle-model-admission.issue176.v0.1`; complete RFC 33,787 bytes; `sha256:9dbe62b18f4214b93b02ae2ccd8d17ee40aed4e1925fff7482993b2eedc9fac8`; current `kernel/runtime_bundle.py` 63,311 bytes, `sha256:47a147942d580bde25c239467e0a62c82cca284b18d9a356422405e9ac45adaa` | component semantics, exact temporal role admission, schema relationship checks, canonical ordering, and bundle identity |
| Temporal role persistence | `ofarm.temporal-governance-production-runtime-bundle-persistence-admission.issue176.v0.1`; complete RFC 37,254 bytes; `sha256:40a20c5053857664cfbb2d6ac2814c6136125eb9908635495af9377e9d9f0870` | inert SQL admission of `TEMPORAL_GOVERNANCE_ARTIFACT` |
| Lifecycle decision | decision-log v0.1 RFC `sha256:958c4a3c2377515022bc1dd6483136e923b9bfa110b507f102a9ec623a0e5d89`; v0.2 amendment RFC `sha256:bfcfeb1858ec6bc08242e208221148b5fb77d5052b4571a3c8564983a81de5f6`; exact current entry in section 3.3 | current pre-deployment `GOVERNED_INACTIVE` state for exactly three subjects |
| Tenant command catalog source | `ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1`; exact schema and binding pins in section 3.1 | exact sixteen rows and their source paths and component properties |
| Selection activation | `ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1`; complete RFC 52,382 bytes; `sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb` | later immutable tenant selection; publication is not selection |
| Global content retention | `ofarm.runtime-bundle-global-content-retention-admission.issue176.v0.1`; complete RFC 38,116 bytes; `sha256:aa5de04c08390e1439d59f39c4b6f5608e8b43b320fec531721d9c53b936873a` | sole non-owner transition for exact global bytes |
| Tenant database release | `ofarm.tenant-postgresql.v1`; migration head 9; complete digest `sha256:cef599a81bda42f84c6c9718845b245ecfa7d97564f5c132b0f12dda526d1293`; migration 0009 is 14,567 bytes, `sha256:10e1966f8a2f25ccc8be077b1484807f03230aae116b352d23c9167e15e45c8c` | exact SQL functions, grants, constraints, triggers, and structural verification |
| Publisher provisioning posture | `TENANT_PROVISIONING_SPEC` digest `sha256:2ac8487b64d4fb09d7576ef1ee09ac1f2a3cc5b20558f0d2137620b897c7157c` | exact control login, publisher capability, inherited membership, connection custody, and privilege topology |
| Current external catalog verifier | `TENANT_CATALOG_VERIFIER_DIGEST = sha256:63439452af1358dcf717abf923e775f3d50f78fd8c8602b633b6dd4b838375c4` | authentication of the migration-owned verifier/observer pair at head 9 |

No authority in this table is amended by Phase A. A changed pin before later
implementation is a stop condition, not permission to silently update this
contract.

## 5. Authority map

- The architecture report owns claim limits. Publication evidence cannot
  become a production-readiness claim.
- ADR 0001 owns publisher credential custody, content placement, immutable
  database carriers, and the existing bundle-sealing transition.
- ADR 0002 owns temporal meanings and half-open interval rules. This contract
  does not interpret a valid or knowledge cut.
- The current temporal decision-log entry owns lifecycle currentness for the
  three governed subjects.
- The exact tenant command-selection binding owns the sixteen source rows. It
  is the only source catalog; caller data and this RFC do not duplicate them.
- This RFC owns the decision that all and only those sixteen rows form the
  complete v0.1 temporal command bundle and owns the closed publication
  ordering.
- `RuntimeComponent` and `RuntimeBundle` own canonicalization, role semantics,
  schema relationships, component identity, canonical ordering, and the
  derived bundle digest.
- `ofarm.retain_runtime_content(text,bytea)` owns exact global content
  retention. The later adapter does not write tables directly.
- `ofarm.publish_runtime_bundle(uuid,text,jsonb)` owns exact SQL document
  validation and atomic tenant bundle sealing. The later adapter does not
  reproduce that SQL authority.
- The trusted control operator, acting through the separately credentialed
  `ofarm_runtime_bundle_control_login`, owns the explicit target-tenant choice.
  That custody is global administrative custody already accepted by ADR 0001;
  application or request data is not promoted into publisher authority.
- The tenant command-selection controller retains sole authority to create a
  selection. Bundle existence and publication success never select one.
- The active SI component catalog, ActiveArtifactSet, Capability Manifest,
  profiles, and application RuntimeBundle retain their current closed
  authorities and remain unchanged.
- The temporal conformance checker owns package isolation. It must be amended
  under a separate reviewed boundary before the proposed adapter can exist.
- The Python source snapshot owns proof that the isolated adapter is outside
  production and legacy import reachability.
- `kernel/schema.sql`, `kernel/store.py`, and
  `kernel/runtime_bundle_repository.py` remain quarantined legacy-M1
  authorities and are not dependencies.
- Issue #192 retains sole authority over audit-runtime behavior.

## 6. Trust model

### 6.1 Protected assets

- the exact sixteen-component catalog and derived bundle digest;
- the distinction between repository bytes and canonical content bytes;
- the current `GOVERNED_INACTIVE` lifecycle state;
- the explicitly chosen registered target tenant;
- publisher credential custody;
- all-or-nothing retention and sealing;
- the absence of tenant selection or knowledge-position effects; and
- the closed active catalog, production semantic surface, and
  production-versus-legacy firewall.

### 6.2 Trusted components and inputs

- the reviewed immutable package image and fixed package root;
- the exact current decision-log entry, selection binding, schema, and source
  files after authentication;
- the existing `RuntimeBundle` model;
- the authenticated migration-head-9 database functions and constraints;
- an uncompromised `ofarm_runtime_bundle_control_login` connection; and
- the trusted control operator's explicit non-nil UUID target.

The target UUID is trusted administrative input only at this isolated control
boundary. It is not a general caller input and creates no authority for routes,
applications, workers, profiles, or later command execution.

### 6.3 Untrusted actors and inputs

- every package byte until its fixed identity is authenticated;
- parsed JSON before exact source authentication and schema validation;
- caller-supplied paths, catalogs, rows, identities, roles, digests, bundle
  documents, tenant aliases, strings, requests, profiles, and environment
  values;
- application, worker, binder, selector, authorizer, and legacy callers;
- pre-existing database rows and returned database values until checked; and
- publication existence, newest/sole ordering, timestamps, or registration
  order offered as selection or catalog authority.

### 6.4 Excluded compromise capabilities

This v0.1 threat model excludes compromise of the designated control operator,
publisher credential, database owner, migrator, DBA, PostgreSQL server,
reviewed package image, Python interpreter, `psycopg`, `jsonschema`, Git, CI, or
the Codex platform. It excludes arbitrary in-process mutation, undetectable
host/filesystem substitution, concurrent mutation of the trusted immutable
package during one call, and a practical SHA-256 collision.

Those exclusions do not excuse observable changed bytes, a changed decision
head, a wrong login, a path outside the package root, or a changed database
result; each must fail closed.

## 7. State machine and ordering

### 7.1 Governance ordering

```text
PROPOSED_PHASE_A_RFC
  -> EXACT_HEAD_REVIEWED_WITH_NO_BLOCKER
  -> DOCUMENTATION_ONLY_PHASE_A_RFC_MERGED_WITH_NO_IMPLEMENTATION_AUTHORITY
  -> SEPARATE_CONFORMANCE_CONTRACT_APPROVED_AND_MERGED
  -> SEPARATE_CONFORMANCE_IMPLEMENTATION_MERGED
  -> DRAFT_PHASE_B_PR_CREATED_INSIDE_EXACT_ALLOWLIST
  -> COMPLETE_LIVE_DECISION_CARD_NAMES_THAT_PR
  -> LATER_EXACT_SAME_TASK_USER_APPROVAL
  -> ISOLATED_ADAPTER_IMPLEMENTED_AND_VERIFIED
```

No earlier state authorizes a later one. Neither this RFC's presence nor its
merge is task-user approval or publication authority. Approval is one-use and
bound to the Phase B PR named before approval; generic `go`, review, merge, or
repository credentials do not count.

### 7.2 Future supported call ordering

Before its first SQL statement, the later adapter must:

1. require an exact non-nil UUID target and an idle connection;
2. authenticate the current decision-log directory and exact entry;
3. authenticate the selection schema and binding repository bytes;
4. completely validate the exact binding against its schema;
5. require its exact identity, posture, command, and sixteen-row closure;
6. resolve every fixed relative source path inside the fixed package root;
7. read each source once, authenticate its required repository or exact-byte
   identity, and construct its `RuntimeComponent` through the existing model;
8. construct the `RuntimeBundle` through the existing model; and
9. require the exact component count, canonical document length, and bundle
   digest from section 3.2.

Only then may it start database interaction. Inside one adapter-owned
transaction it must:

1. authenticate `SESSION_USER` as
   `ofarm_runtime_bundle_control_login` and refuse any other supported caller;
2. call `ofarm.retain_runtime_content(...)` once for each of the sixteen
   canonical components in canonical bundle order;
3. verify every returned content digest;
4. call `ofarm.publish_runtime_bundle(...)` once with only the explicit target,
   derived bundle digest, and exact canonical bundle document;
5. verify the single returned bundle digest; and
6. commit exactly once.

Any exception or mismatch rolls back exactly once. The adapter must not commit
inside either SQL function, use another connection, perform direct DML, or
continue after an uncertain result.

### 7.3 Database states

```text
ABSENT
  -- exact authorized call --> EXACT_GLOBALS_AND_TENANT_SEAL_COMMITTED

PARTIAL_EXACT_GLOBALS_ALREADY_RETAINED
  -- exact authorized call --> EXACT_GLOBALS_AND_TENANT_SEAL_COMMITTED

EXACT_GLOBALS_AND_TENANT_SEAL_COMMITTED
  -- exact replay ----------> SAME_STATE

ANY_STATE
  -- changed authority, bytes, target absence, unequal reuse, SQL refusal,
     invalid return, or transaction failure --> REFUSED; NO NEW COMMITTED STATE
```

Pre-existing exact global content remains valid shared content. A failed call
does not remove pre-existing rows, but it commits no new content or bundle row.

## 8. Invariants and acceptance criteria

- **TRBCP-001 — One catalog authority.** The exact pinned selection binding is
  the sole row catalog; no caller, second manifest, scan, or registry can add,
  remove, replace, or reinterpret a row.
- **TRBCP-002 — Exact whole bundle.** The whole v0.1 bundle contains exactly
  the binding's sixteen rows once each and no other component.
- **TRBCP-003 — Exact derived identity.** Construction yields 16 components,
  exactly 4,510 canonical document bytes, and
  `sha256:c774100b13ad7d3f353148eeceeabd319167846825c7392ebbaca1f4ba62faea`.
- **TRBCP-004 — Exact source bytes.** Schema components use the exact bytes and
  digests in the binding. Each temporal artifact first matches the repository
  file identity in the current decision and then matches its canonical length
  and digest in the binding and model.
- **TRBCP-005 — Lifecycle-current prerequisite.** The exact three subjects
  remain the sole current `PROMOTE_GOVERNED_INACTIVE` entry. Missing, changed,
  additional, ambiguous, or superseding decision evidence refuses.
- **TRBCP-006 — Caller cannot shape semantics.** The API exposes no catalog,
  path, component, role, identity, digest, bundle, command, matrix, row,
  profile, request, environment, or selection input.
- **TRBCP-007 — Explicit target authority.** The only variable semantic input
  is one trusted control-operator-selected non-nil UUID; aliases, inference,
  enumeration, bulk discovery, and application data are unsupported.
- **TRBCP-008 — Existing publisher custody only.** The supported database
  caller is exactly `ofarm_runtime_bundle_control_login`; no role, grant,
  membership, credential, or table privilege changes.
- **TRBCP-009 — Model before effects.** All lifecycle, binding, source,
  component, schema relationship, bundle, and derived-identity validation
  completes before the first database statement.
- **TRBCP-010 — One transaction.** All content-retention calls and the one
  bundle-sealing call commit together or no new state commits.
- **TRBCP-011 — Existing SQL transitions only.** The adapter uses only
  `ofarm.retain_runtime_content(...)` and
  `ofarm.publish_runtime_bundle(...)`; direct DML and alternate functions are
  forbidden.
- **TRBCP-012 — Exact replay only.** Equal retained content and an equal tenant
  seal are idempotent. Unequal reuse, invalid database return, or uncertain
  completion refuses and rolls back.
- **TRBCP-013 — Publication is inert.** A sealed bundle creates no tenant
  selection, governed batch, knowledge position, command admission,
  authorization, materialization, qualification, read, output, route, or
  current-truth effect.
- **TRBCP-014 — Lifecycle meaning preserved.** Published temporal subjects
  remain `GOVERNED_INACTIVE`; publication is not activation, current/default
  promotion, deployment, execution authority, or production readiness.
- **TRBCP-015 — Active catalog unchanged.** The active SI catalog,
  ActiveArtifactSet, Capability Manifest, profiles, and application
  RuntimeBundle remain byte-for-byte unchanged.
- **TRBCP-016 — Isolation preserved.** The adapter is absent from production
  and legacy import reachability and is not re-exported by the PostgreSQL
  package initializer.
- **TRBCP-017 — Conformance first.** The adapter path cannot exist until a
  separate reviewed conformance boundary admits exactly that isolated path
  while continuing to refuse every other temporal consumer and active
  registry.
- **TRBCP-018 — Disposable evidence only.** Phase B may retain and publish the
  exact bundle only on disposable test targets. It creates no real or retained
  tenant state and performs no deployment operation.
- **TRBCP-019 — Production and legacy firewall.** No legacy Store, schema,
  repository, semantic, materialization, output, or profile module becomes an
  authority or dependency.
- **TRBCP-020 — Audit separation.** No #192 event, route, receipt, failure
  mapping, attribution, table, service, or runtime behavior changes.

## 9. Required negative cases

| Invariant | Supported counterexample | Required result |
| --- | --- | --- |
| TRBCP-001, 002 | Pinned binding has 15 or 17 rows, a duplicate, changed order authority, or one substituted row | Refuse before SQL; no alternate catalog fallback |
| TRBCP-003 | Constructed count, canonical document, or digest differs | Refuse before SQL |
| TRBCP-004 | One schema byte changes; one temporal repository file changes only formatting; one canonical temporal value changes | Refuse before SQL in every case |
| TRBCP-005 | Decision entry is missing, changed, accompanied by another entry, or superseded | Refuse before SQL |
| TRBCP-006 | Caller attempts to supply a path, row, digest, command, matrix, bundle document, profile, request, or environment override | No such API field; any wrapper adding one is outside scope |
| TRBCP-007 | Nil UUID, string alias, inferred tenant, absent tenant, or bulk tenant enumeration | Refuse; absent tenant rolls back all new rows |
| TRBCP-008 | Application, worker, binder, selector, authorizer, migrator, or unrelated control login invokes the adapter or SQL functions | Refuse with no committed new state |
| TRBCP-009 | Source or binding failure occurs while an exact target and publisher connection are available | Zero SQL calls |
| TRBCP-010, 011 | The ninth retention call, publication call, or result check fails after earlier inserts | One rollback; no new content or bundle survives; no direct-DML retry |
| TRBCP-012 | Same digest names unequal existing bytes, existing seal differs, two result rows appear, or connection outcome is uncertain | Refuse and roll back; never report success |
| TRBCP-013 | Publication is followed by an attempt to resolve it as selected, allocate a knowledge position, or admit a command | No selection exists; later boundary remains required |
| TRBCP-014 | RuntimeBundle presence is presented as active/current/default/deployed | Refuse the claim; lifecycle remains `GOVERNED_INACTIVE` |
| TRBCP-015 | A temporal row is added to `kernel/runtime_bundle_components.json`, ActiveArtifactSet, Capability Manifest, or a profile | Changed-file and conformance gates refuse |
| TRBCP-016, 019 | Production or legacy root imports the adapter, or the adapter imports legacy runtime/repository code | Architecture and conformance gates refuse |
| TRBCP-017 | Adapter exists before its conformance exception, or the markers appear in another Python path | Temporal conformance refuses |
| TRBCP-018 | A non-disposable tenant target or retained bundle is requested during Phase B | Stop before invocation |
| TRBCP-020 | Publication emits or requires #192 behavior | Stop and separate the boundary |

## 10. Mandatory separate conformance prerequisite

The current temporal checker correctly refuses a new production Python source
that consumes temporal selection markers outside the already admitted
selection-control adapter. It also correctly requires the active component
catalog to contain no temporal governance artifact.

Before publication Phase B, a separate Phase A conformance contract and a
separate conformance implementation must:

1. authenticate this complete merged RFC by exact repository path, contract
   identity, mechanically derived byte length, and SHA-256;
2. classify only
   `deployment/postgresql/temporal_runtime_bundle_publication.py` as the future
   catalog/publication consumer;
3. accept both states: the adapter absent, or the exact adapter present;
4. require the exact catalog binding identity, binding digest, lifecycle entry,
   expected bundle digest, retention function, and publication function markers
   together in that one path;
5. refuse any subset of those markers, any alternate path, or another temporal
   publication consumer;
6. prove the adapter is absent from production and legacy reachability and is
   not imported or re-exported by `deployment/postgresql/__init__.py`;
7. continue to require zero temporal entries in the active catalog,
   ActiveArtifactSet, Capability Manifest, and profiles; and
8. preserve every existing temporal, migration, selection, retention,
   architecture, legacy-firewall, semantic-surface, and #192 invariant.

That prerequisite may classify the path. It must not implement the adapter,
retain content, publish a bundle, choose a tenant, create a selection, or
change runtime behavior. If the checker cannot admit the exact path without
changing another authority, work stops for another reviewed boundary.

## 11. Proposed architecture and smallest coherent change

### 11.1 This Phase A PR

This RFC is the only changed file. It freezes the exact catalog meaning,
derived bundle identity, target authority, transaction order, and later stop
conditions. It changes no executable authority.

### 11.2 Future publication Phase B allowlist

After all gates in section 7.1, publication Phase B is limited to:

| Path | Permitted change |
| --- | --- |
| `deployment/postgresql/temporal_runtime_bundle_publication.py` | Add the one isolated, fixed-authority construction and publication operation defined here. |
| `kernel/tests/test_temporal_runtime_bundle_publication.py` | Focused unit, authority, composition, transaction, result, and import-isolation tests. |
| `kernel/tests/test_postgresql_tenant_migration.py` | Disposable real-role PostgreSQL tests for exact publication, replay, rollback, ACL refusal, and no selection or knowledge-position effect. |
| `deployment/postgresql/README.md` | Document the isolated pre-deployment control adapter and its non-effects. |
| `conformance/review_baseline_test_inventory.json` | Mechanical regeneration only when required by a change to the canonical collected test-node inventory, including a count or node-ID change. |

No other file is permitted. In particular, Phase B may not change
`kernel/runtime_bundle.py`, `kernel/runtime_bundle_components.json`, an existing
selection adapter, a migration, provisioning, readiness, a catalog verifier,
an active artifact, an initializer, an application or worker module, or a
legacy path.

### 11.3 Types and data flow

The later module needs only:

- one immutable in-memory catalog value parsed from the authenticated binding;
- the existing immutable `RuntimeComponent` and `RuntimeBundle` values; and
- one small immutable publication result containing the exact target UUID and
  bundle digest, or just the exact digest.

It introduces no mutable registry, cache, service object, optional capability
bag, `Any`-typed authority value, background worker, or compatibility shim.

The data flow is:

```text
exact decision head + exact binding + exact fixed source bytes
  -> existing RuntimeComponent validation
  -> existing RuntimeBundle validation and digest
  -> existing publisher-control connection + explicit UUID
  -> retain each exact global component
  -> seal one exact tenant bundle
  -> verify result
  -> commit
```

### 11.4 Why this is the smallest coherent design

Reusing the selection binding as the source catalog avoids a second JSON
catalog and consistency authority. Making its sixteen rows the entire bundle
avoids tenant-content custody and avoids mixing the inactive temporal command
bundle with the 95-component active SI application bundle. Calling the two
existing SQL functions avoids a migration, role, grant, direct DML path, or
combined retention-and-sealing API. A new isolated module is safer and smaller
than adding publisher custody to the selection adapter.

## 12. Elegance audit

- Catalog row sources of truth: one—the exact selection binding.
- Whole-bundle closure decisions: one—this RFC's all-and-only-sixteen rule.
- Lifecycle heads: one—the exact current decision-log chain.
- Component and bundle validators: one—the existing RuntimeBundle model.
- Global retention transitions: one—the existing retention function.
- Tenant sealing transitions: one—the existing publication function.
- Target-tenant choices per call: one—the trusted control operator's explicit
  UUID.
- Orchestration transitions: one—the future isolated adapter.

The design adds no schema, migration, role, catalog artifact, service, startup
hook, or runtime registry. The only repeated values in future code are
mechanical trust pins and the expected derived bundle identity; tests must
compare them with their owning authorities. No current authority or fallback
can be deleted in this boundary. A clean small adapter is preferable to
modifying the existing selection-control module because publication and
selection remain different custodians.

## 13. Non-goals

This contract does not:

- implement the adapter, its conformance exception, or any database change;
- alter, promote, activate, rewrite, or add a temporal candidate or schema;
- add a component to the active catalog or application RuntimeBundle;
- create a second catalog manifest or modify the selection binding;
- publish to a real tenant or retain any non-disposable state;
- create, replace, supersede, roll back, delete, or read a tenant selection;
- allocate a tenant knowledge position or governed write batch;
- integrate `COMMIT_OPERATION_CLAIM_DRAFT`, authorization, replay, or batch
  provenance;
- add a startup hook, CLI, service, worker, route, API, environment option,
  fleet loop, deployment step, or operator credential workflow;
- implement a current-state read, historical view, WINDOW behavior,
  materialization, qualification, receipt, or output;
- change valid-time carrier selection or half-open interval rules;
- change the production semantic surface, the production-versus-legacy
  firewall, a profile, or a capability claim; or
- add or change #192 behavior.

## 14. Provisional-design record

This design is provisional for pre-deployment OFARM2 because the current
lifecycle currentness evidence and task-user approval workflow are
AI-attested repository evidence, not independently human-verifiable signing.
Phase B is limited to disposable targets, no automatic invocation exists, and
no real tenant state is retained, so this limitation cannot silently become a
deployment claim.

Before deployment, lifecycle approval and publication authorization must be
replaced or re-established through an independently human-controlled and
independently verifiable approval/signing system. That system should bind the
same exact catalog authority, component identities, bundle digest, target
tenant, and one-use publication act.

Evidence requiring redesign includes a need for multiple temporal bundles,
tenant-owned components, mutable current pointers, hot reload, bulk tenant
publication, automatic startup publication, bundle upgrade or rollback,
signed release manifests, or an independently operated publisher. Each changes
an authority or state transition and requires a new versioned contract.

## 15. Traceability and verification

| Invariants | Future owner | Required negative evidence | Smallest verification |
| --- | --- | --- | --- |
| TRBCP-001–006 | future adapter authority loader plus existing model | changed binding, decision, source, row, count, canonical identity, and caller-shaping tests | focused publication unit tests plus existing temporal RuntimeBundle and selection tests |
| TRBCP-007–012 | future adapter transaction boundary plus existing SQL functions | wrong target type, absent tenant, wrong login, mid-sequence failure, unequal replay, invalid/ambiguous result | fake-connection transaction tests and disposable real-role PostgreSQL tests |
| TRBCP-013–015 | unchanged selection tables, knowledge ledger, active artifacts, and runtime catalog | publication followed by implicit selection/position/currentness claim; active catalog mutation | database absence assertions, exact changed-file check, and temporal conformance |
| TRBCP-016, 017, 019 | architecture snapshot and separately admitted temporal checker | production/legacy/import-initializer reachability or marker in another path | architecture checker and temporal candidate checker |
| TRBCP-018 | test-target lifecycle and PR boundary | non-disposable connection or retained state request | disposable-target teardown plus no operational invocation |
| TRBCP-020 | unchanged #192 tree and import graph | any audit dependency or emitted behavior | changed-file and import-reachability checks |

### 15.1 Phase A verification

Phase A must prove:

- the diff contains only this RFC;
- every pinned file identity matches current `main`;
- the exact binding rows reconstruct the 16-component, 4,510-byte bundle with
  digest `sha256:c774100b13ad7d3f353148eeceeabd319167846825c7392ebbaca1f4ba62faea`;
- the active catalog still contains zero temporal governance artifacts; and
- package conformance passes.

Required checks include:

```text
python3 -m pytest -q kernel/tests/test_runtime_bundle.py -k temporal_governance
python3 -m pytest -q kernel/tests/test_tenant_command_runtime_bundle_selection.py
python3 conformance/temporal_contract_candidate_check.py
python3 conformance/ofarm_pkg_contract_check.py
```

### 15.2 Future Phase B verification

Phase B must additionally run:

```text
python3 -m pytest -q kernel/tests/test_temporal_runtime_bundle_publication.py
python3 -m pytest -q kernel/tests/test_postgresql_tenant_migration.py -k temporal_runtime_bundle_publication
python3 conformance/rewrite_architecture_check.py
python3 conformance/temporal_contract_candidate_check.py
python3 conformance/ofarm_pkg_contract_check.py
python3 conformance/run_review_baseline.py
```

Hosted PostgreSQL 17, native amd64, native arm64, and the canonical native
verifier remain required where the repository workflow requires them. Passing
checks are evidence, not deployment or publication authority.

## 16. Pull-request boundary and stop conditions

The Phase A PR changes this RFC only. Reviewers must not require implementation,
the conformance prerequisite, a database migration, active catalog membership,
selection, command integration, runtime activation, or output work from this
PR.

Work stops before later implementation if:

1. this RFC has not merged and its complete merged identity has not been
   mechanically authenticated;
2. the separate conformance contract or implementation has not merged;
3. no already-created draft Phase B PR is named by a complete live decision
   card under the active pre-deployment workflow;
4. no later exact same-task task-user approval is valid and currently bound to
   that one PR;
5. a reviewed authority pin or derived bundle identity differs;
6. the decision-log directory no longer has exactly the accepted current head;
7. any component outside the exact sixteen is needed;
8. any component needs tenant placement;
9. an active catalog, RuntimeBundle model, selection adapter, migration,
   function, role, grant, provisioning, readiness, or catalog-verifier change
   is needed;
10. an implementation path outside section 11.2 is needed;
11. a caller-selectable catalog, binding, source, row, bundle, or semantic
    identity is proposed;
12. target choice must come from application, worker, request, route, profile,
    environment, principal, binder, selector, or inferred data;
13. a combined retention-and-sealing SQL function, direct DML path, second
    connection, autonomous transaction, or uncertain-success translation is
    proposed;
14. a CLI, service, startup hook, deployment integration, bulk publisher, or
    real tenant publication is required;
15. publication must imply selection, activation, current/default status,
    execution, deployment, materialization, read, qualification, output, or
    current truth;
16. production or legacy runtime must import the adapter;
17. non-disposable content, bundle, selection, tenant, or knowledge state would
    remain after testing; or
18. #192 behavior or authority must change.

Any such need is a contract amendment or a separate trust-boundary PR. An
existing oversized change is not precedent for combining it here.

## 17. Open decisions and review disposition

Open design decisions inside this boundary: none.

The actual target UUID and invocation time are explicit trusted operational
inputs to a later invocation, not hidden catalog decisions. Phase B itself may
use only disposable targets and therefore makes no operational publication
decision.

- **Blockers:** none identified in the author draft; exact-head review is
  required.
- **Follow-ups:** separate conformance Phase A and implementation; then the
  bounded publication Phase B; later production read-only selection,
  authorization-provider, governed-command integration, and only then
  separately governed reads and outputs.
- **Preferences:** none recorded.

### Merge-stop rule

This documentation-only PR may merge when its Phase A acceptance criteria pass
and no demonstrated Blocker remains. Its merge does not authorize Phase B.
Implementation begins only after the merged-authority, conformance,
already-created Phase B PR, live-card, and exact-approval sequence in this
contract is satisfied.
