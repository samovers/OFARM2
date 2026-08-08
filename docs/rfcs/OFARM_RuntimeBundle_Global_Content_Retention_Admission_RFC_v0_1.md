# OFARM2 RuntimeBundle Global Content Retention Admission — Phase A Contract v0.1

**Status:** proposed Phase A contract; documentation-only, unapproved, and
without database, content-retention, bundle-publication, selection, runtime,
deployment, route, output, legacy, or #192 effect

**Contract identity:**
`ofarm.runtime-bundle-global-content-retention-admission.issue176.v0.1`

**Decision identity:**
`ISSUE176-RUNTIME-BUNDLE-GLOBAL-CONTENT-RETENTION-001`, version `1`

**Reviewed base:** `78ab624a9a72311f2a3cfacf2ab46a18193f2508`

**Phase A RFC path:**
`docs/rfcs/OFARM_RuntimeBundle_Global_Content_Retention_Admission_RFC_v0_1.md`

**Primary ticket:** #176

**Primary trust boundary:** production PostgreSQL publisher custody for
append-only, globally immutable RuntimeBundle component bytes

**Phase A pull-request boundary:** this RFC only

**Intended later database Phase B boundary:** one migration-owned global
content-retention function, its exact execute grant to the unchanged publisher
capability, mechanical tenant migration/readiness identities, and focused
verification only

## 1. Problem and goal

The production tenant schema already has:

- `ofarm.runtime_content_blob`, an immutable global content-addressed carrier;
- `ofarm.runtime_bundle` and `ofarm.runtime_bundle_component`, which seal one
  exact component set for one tenant;
- the `NOLOGIN` capability `ofarm_runtime_bundle_publisher` and separately
  credentialed `ofarm_runtime_bundle_control_login`; and
- `ofarm.publish_runtime_bundle(uuid,text,jsonb)`, the only non-owner bundle
  sealing transition.

The sealing function deliberately requires every selected global component's
exact digest and byte length to exist already in
`ofarm.runtime_content_blob`. No production non-owner function can create that
row. The publisher role has no direct table DML. Current PostgreSQL tests make
publication possible only by inserting content as the database administrator.
That is valid disposable test setup, but it is not a lawful production
publisher path.

The missing capability is therefore narrower than temporal RuntimeBundle
composition and narrower than tenant selection:

> allow the already isolated RuntimeBundle publisher capability to retain one
> exact, content-addressed global byte string without gaining direct table
> access or any selection, lifecycle, tenant, command, or runtime authority.

This contract defines that capability. It does not decide which package bytes
belong in the temporal RuntimeBundle, choose a tenant, publish a RuntimeBundle,
create a selection, or activate any semantic behavior.

The exact temporal bundle remains a later catalog/publication decision. The
current command-selection binding fixes a sixteen-component command-required
subset, not the production custody transition that makes global bytes
available and not, by itself, the exact whole-bundle publication decision.

## 2. Learning value

This boundary closes one demonstrated production-path gap while preserving the
accepted authority split:

- Python RuntimeBundle and future catalog authorities validate semantic
  identity, canonicalization, placement, and composition;
- PostgreSQL validates only content addressing, immutability, caller custody,
  and transaction behavior; and
- the existing bundle publisher continues to seal membership only after exact
  content exists.

It demonstrates that global content can enter the production carrier through
one reviewable non-owner transition instead of administrator DML, legacy
repository code, or an application/worker shortcut.

## 3. Decision

After this exact RFC is approved and merged, and after the separate conformance
prerequisite in section 6 is approved, implemented, and merged, one later
database Phase B may add exactly this function:

```text
ofarm.retain_runtime_content(
    expected_content_digest text,
    canonical_bytes bytea
) -> ofarm.sha256_id
```

The function is:

- owned by `ofarm_owner`;
- `SECURITY DEFINER`;
- `VOLATILE`;
- `CALLED ON NULL INPUT` so nulls are explicitly refused;
- `PARALLEL UNSAFE`;
- not leakproof; and
- fixed to `search_path = pg_catalog, pg_temp`.

Only `ofarm_runtime_bundle_publisher` receives `EXECUTE`. The existing
`ofarm_runtime_bundle_control_login` reaches that capability only through its
already provisioned inherited, non-assumable membership. No role, login,
membership, credential, database-connect rule, schema-use rule, table grant,
or provisioning specification changes.

Migration 0009 must revoke the default `PUBLIC` function privilege before it
grants `EXECUTE` to the publisher capability. It must admit no overload or
alias of the function.

### 3.1 Closed input and validation order

For each supported call, the function must perform this order inside the
caller's transaction:

1. require `SESSION_USER` to have the existing
   `ofarm_runtime_bundle_publisher` capability, or to be the already governed
   database owner;
2. refuse null input;
3. require `expected_content_digest` to be exactly lower-case
   `sha256:` followed by 64 hexadecimal characters;
4. derive byte length from `canonical_bytes`; there is no caller-supplied
   length;
5. require the derived length to be between `0` and `1073741823` inclusive,
   matching the existing RuntimeBundle component bound;
6. compute SHA-256 over the exact supplied bytes and require equality with the
   expected digest;
7. insert exactly `(digest, bytes, derived length)` into
   `ofarm.runtime_content_blob`, or enter the exact-replay check when that
   digest already exists;
8. require the retained row's exact bytes and length to equal this call; and
9. return the exact `ofarm.sha256_id` digest.

Every validation that can be completed before insertion occurs before
insertion. A failure raises and leaves no row from that call. The function does
not commit, open another connection, or start an autonomous transaction.

### 3.2 Exact replay and conflict

The state transition is:

```text
ABSENT
  -- exact authorized content-addressed insert --> RETAINED_INERT

RETAINED_INERT
  -- same digest + same bytes -----------------> RETAINED_INERT (no-op)

RETAINED_INERT
  -- claimed same digest + unequal bytes ------> REFUSED (no change)
```

The existing primary key, digest constraint, byte-length constraint, and
mutation-rejection trigger remain authoritative. Concurrent equal calls may
serialize and both return the same digest. A serialization or visibility
conflict refuses or retries at the transaction owner; it must never create a
second row or treat an unverified conflict as success.

Cryptographic SHA-256 collision resistance is trusted. The explicit read-back
comparison remains required so an existing row is never accepted merely
because its key text matches.

### 3.3 Retention is inert

A retained global blob has no tenant, bundle membership, lifecycle state,
selection state, command authority, valid-time meaning, knowledge position,
route, output, or current-truth effect.

The function accepts no tenant identifier, logical reference, component role,
canonicalization label, placement label, schema identity, temporal identity,
RuntimeBundle digest, command identity, selection binding, request identity,
principal, credential, profile, or activation field.

A later reviewed catalog/publication authority must choose exact source bytes,
validate their global placement, construct the complete RuntimeBundle, choose
the authorized target tenant, and call content retention followed by
`ofarm.publish_runtime_bundle(...)` in one caller-owned transaction. This
contract grants none of those later decisions.

## 4. Reviewed authorities and current state

This design is based on current `main` at the reviewed base and these exact
authorities:

| Authority | Exact current identity | Authority retained |
| --- | --- | --- |
| Database architecture | `docs/adr/0001-tenancy-and-schema-migrations.md`, 147,112 bytes, `sha256:bc49e566ddbdf98868162aa7ccca0940fa76fca1bfaaa261c8c831dbb5515a4d` | global content carrier, publisher custody, migrations, and sealed bundle publication |
| Temporal architecture | `docs/adr/0002-valid-time-and-knowledge-time.md`, 61,427 bytes, `sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796` | independent temporal axes and the rule that global bytes are inert until tenant-scoped activation or selection |
| Frozen architecture reference | `reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md`, 96,406 bytes, `sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256` | production-versus-aspirational claims and governed runtime surfaces |
| Merged Python-source architecture | `ofarm.architecture-python-source-snapshot-admission.issue176.v0.1`, complete RFC 82,758 bytes, `sha256:6e4307077525f2bbb48992fa4c652ab75d279875063bd715cf21dc1f1d3216d5` | exact source inventory and production/legacy import-graph evidence |
| RuntimeBundle model | `kernel/runtime_bundle.py`, 63,311 bytes, `sha256:47a147942d580bde25c239467e0a62c82cca284b18d9a356422405e9ac45adaa` | component and bundle semantic validation and identity construction |
| Temporal role persistence | `ofarm.temporal-governance-production-runtime-bundle-persistence-admission.issue176.v0.1`, complete RFC 37,254 bytes, `sha256:40a20c5053857664cfbb2d6ac2814c6136125eb9908635495af9377e9d9f0870` | inert database admission of `TEMPORAL_GOVERNANCE_ARTIFACT` |
| Selection activation admission | `ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1`, complete RFC 52,382 bytes, `sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb` | immutable tenant selection activation, not publication |
| Current tenant migration set | service `ofarm.tenant-postgresql.v1`, head version 8, exact prefix/full digest `sha256:7231c869066c56f7c642460d33391bab00456daecdb04530b34da7210e8e8a54` | production SQL structure and append-only migration history |
| Current provisioning posture | `sha256:2ac8487b64d4fb09d7576ef1ee09ac1f2a3cc5b20558f0d2137620b897c7157c` | exact roles, memberships, connection custody, and privileges |
| Current external tenant catalog verifier | `sha256:28aaa41651c1338fec9f8ca6aa7f252b7bef4ef2f3b1760d399306aba69c8719` | final verifier/observer authentication at migration head 8 |

No authority above is amended by Phase A. If a pin changes before database
Phase B, implementation stops for review rather than silently re-pinning.

## 5. Authority map

- ADR 0001 owns the global content carrier, publisher custody, migration
  ownership, append-only storage, and the rule that bundle sealing requires
  exact content already retained.
- ADR 0002 owns valid time, tenant knowledge order, and the rule that global
  content cannot affect a tenant answer until a tenant-scoped activation or
  selection makes its identity visible.
- Numbered tenant migrations own production relations, functions, triggers,
  grants, and structural verification.
- `ofarm.runtime_content_blob` owns the one immutable row for each global
  content digest.
- The new `ofarm.retain_runtime_content(text,bytea)` function would own the
  sole non-owner transition from exact supplied bytes to one retained global
  content row.
- The unchanged `ofarm_runtime_bundle_publisher` capability and its control
  login own invocation custody. This contract does not widen that custody.
- The RuntimeBundle model owns semantic component validity, canonicalization,
  placement, exact component identity, and complete bundle identity. SQL does
  not duplicate those decisions.
- A later catalog/publication contract must own exact source paths and bytes,
  exact whole-bundle composition, target-tenant choice, and one-transaction
  ordering from retention through bundle sealing.
- The unchanged `ofarm.publish_runtime_bundle(uuid,text,jsonb)` owns exact
  bundle-document validation and atomic sealing after content exists.
- The tenant command-selection binding owns the command-required component
  subset. It does not authorize global content retention or whole-bundle
  publication.
- The selection-control authority owns tenant selection activation. Publisher
  custody must not create or infer a selection.
- The active component catalog, ActiveArtifactSet, Capability Manifest, and
  profiles retain their current closed authorities and remain unchanged.
- The architecture source snapshot and architecture checker own production and
  legacy import evidence. This database boundary adds no Python runtime module.
- The temporal candidate checker owns temporal conformance interpretation. It
  must be amended separately before migration 0009 can be admitted.
- `kernel/schema.sql`, `kernel/store.py`, and
  `kernel/runtime_bundle_repository.py` remain quarantined legacy-M1
  authorities and are not dependencies.
- #192 retains sole authority over audit-runtime behavior.

There is no alias, environment registry, caller-supplied policy, fallback
table, legacy repository, or administrator adapter that may substitute for
these authorities.

## 6. Mandatory separate conformance prerequisite

The current temporal checker authenticates the exact migration history through
version 8 and deliberately refuses another migration count. Database Phase B
must not change that checker in the database PR.

Before database Phase B, one separate reviewed conformance contract and one
separate conformance implementation must:

1. authenticate this complete merged RFC by exact path, byte length, and
   SHA-256;
2. preserve the exact version-3 knowledge-storage prefix;
3. preserve the exact version-8 selection-storage prefix
   `sha256:7231c869066c56f7c642460d33391bab00456daecdb04530b34da7210e8e8a54`;
4. accept exactly two lawful repository states:
   - the exact authenticated version-8 state with migration 0009 absent; and
   - an exact contiguous version-9 state whose final filename is
     `0009_runtime_bundle_global_content_retention.sql`;
5. refuse another migration-0009 filename, a gap, reorder, edit, replacement,
   or another migration containing the new function identity;
6. require migration 0009 to contain no temporal candidate path, temporal
   identity, carrier row, selection binding, tenant selection, route, output,
   or #192 marker;
7. keep candidate artifacts absent from the active RuntimeBundle catalog,
   ActiveArtifactSet, Capability Manifest, profiles, routes, production import
   closure, and legacy import closure;
8. continue authenticating the complete current migration set independently
   from the stable version-3 and version-8 prefixes; and
9. update canonical collected test-node inventory metadata only when
   mechanically required by a count or node-ID change.

That conformance boundary may classify the exact future migration path. It may
not define the SQL function, change publisher custody, select source bytes,
publish a bundle, or make any temporal artifact active.

If the conformance checker cannot express this absent/present transition
without changing another active authority, work stops for another reviewed
boundary.

## 7. Trust model

### 7.1 Protected assets

- Exact global content bytes, digest, and derived length.
- One immutable row per global content digest.
- Publisher-only non-owner write custody.
- Absence of application, worker, readiness, binder, selection controller, or
  legacy write access.
- Existing role, membership, connection, schema-use, and provisioning posture.
- Existing RuntimeBundle semantic and bundle-sealing authorities.
- The distinction among content retention, bundle membership, tenant
  selection, runtime use, lifecycle state, and current truth.
- Append-only migration history and final readiness identity.
- The production-versus-legacy firewall.

### 7.2 Trusted components

- The existing publisher control login and inherited publisher capability.
- The new fixed SQL function after migration and structural authentication.
- PostgreSQL SHA-256, constraints, primary-key conflict handling, transaction
  isolation, and the immutable-row trigger.
- The unchanged migration runner, lock, ledger, migration-local prior-state
  guards, structural verifier, observer, and external verifier-pair anchor.
- The RuntimeBundle model and future reviewed catalog/publication authority for
  semantic validation before a real call.

### 7.3 Untrusted actors and inputs

- Application, worker, readiness, binder, registrar, identity, authorization,
  selection-control, and ordinary database sessions.
- The expected digest and supplied bytes until the function validates them.
- Direct DML, copied SQL, fixtures, environment values, package order, newest
  files, profiles, request data, and caller-supplied registries.
- An existing blob row presented as proof of bundle membership, tenant
  selection, activation, currentness, or execution authority.

### 7.4 Excluded compromise capabilities

Compromise of the publisher control credential or trusted startup publisher
process, database owner, migrator, DBA, operating system, PostgreSQL engine,
cryptographic hash, migration runner, or trusted dependency is outside this
boundary.

This exclusion is explicit because a compromised publisher could submit
arbitrary global bytes and already holds the separate bundle-sealing
capability. SQL intentionally does not become a package-semantic validator.
The supported ordinary-role threat model remains in scope and fail closed.

Local source substitution and compromised package dependencies are outside
the SQL function's semantic competence. The later catalog/publication boundary
must authenticate exact source bytes before calling this function.

## 8. State machine and ordering

### 8.1 Phase A and prerequisite ordering

```text
PROPOSED_PHASE_A_RFC
  -> EXPLICIT_ARCHITECT_APPROVAL
  -> DOCUMENTATION_ONLY_RFC_MERGED
  -> SEPARATE_CONFORMANCE_CONTRACT_APPROVED
  -> ABSENT_OR_EXACT_0009_CONFORMANCE_IMPLEMENTED_AND_MERGED
  -> DATABASE_PHASE_B_MAY_BE_REQUESTED
```

A PR merge, review, commit, repository credential, or passing check is not
architect approval.

### 8.2 Database release ordering

```text
AUTHENTICATED_VERSION_8
  -> AUTHORITATIVE_LOCAL_VERSION_9_SET_VALIDATED
  -> PROTECTED_MIGRATION_TRANSACTION_OPEN_AND_LOCKED
  -> VERSION_8_HISTORY_BOUNDARY_AND_PRIOR_DEFINITIONS_VERIFIED
  -> RETENTION_FUNCTION_AND_EXACT_GRANT_CREATED
  -> EXACT_VERSION_9_LEDGER_ROW_APPENDED_BY_RUNNER
  -> FINAL_VERSION_9_VERIFIER_PAIR_AND_STRUCTURE_AUTHENTICATED
  -> COMMIT
```

Migration SQL does not append its own ledger row. The unchanged migration
runner owns the ledger transition. Any failure rolls back the function, grant,
verifier change, and ledger append together.

### 8.3 Supported call ordering

```text
AUTHORIZED_CALL
  -> INPUT_SHAPE_VALIDATED
  -> LENGTH_DERIVED_AND_BOUNDED
  -> DIGEST_RECOMPUTED_AND_MATCHED
  -> INSERT_OR_EXACT_REPLAY_CHECK
  -> EXACT_ROW_READ_BACK
  -> DIGEST_RETURNED
```

There is no transition from retained content to bundle membership, selection,
activation, command execution, output, or current truth in this contract.

## 9. Invariants and acceptance criteria

- **RBGC-001 — One write seam.** The only new non-owner global-content write
  transition is `ofarm.retain_runtime_content(text,bytea)`.
- **RBGC-002 — Existing non-owner custody only.** The existing RuntimeBundle
  publisher capability is the only non-owner capability granted execute;
  `PUBLIC` has no execute privilege, no overload or alias exists, and the
  existing owner/migrator authority and all role and provisioning topology
  remain unchanged.
- **RBGC-003 — Content-addressed equality.** The retained digest is SHA-256 of
  the exact supplied bytes and the stored length is derived from those bytes.
- **RBGC-004 — No correlated length input.** The caller supplies no byte
  length, component identity, role, placement, tenant, or bundle identity.
- **RBGC-005 — Exact replay only.** Equal replay returns the same digest without
  mutation; unequal reuse refuses without mutation.
- **RBGC-006 — Append only.** The function cannot update, delete, truncate, or
  replace a retained row.
- **RBGC-007 — No direct DML widening.** Publisher, control-login,
  application, worker, and selection roles receive no table DML.
- **RBGC-008 — Transaction owned by caller.** The function never commits or
  escapes the caller transaction; rollback leaves no row from that call.
- **RBGC-009 — Globally inert content.** Retention creates no tenant fact,
  knowledge position, bundle membership, selection, lifecycle state, runtime
  activation, command authority, output, or truth.
- **RBGC-010 — No semantic duplication in SQL.** SQL contains no temporal
  identity set, carrier matrix, schema validator, command closure, source-path
  registry, or package catalog.
- **RBGC-011 — Bundle publisher unchanged.** This boundary does not alter the
  signature, validation, custody, or sealing semantics of
  `ofarm.publish_runtime_bundle(uuid,text,jsonb)`.
- **RBGC-012 — Immutable migration history.** Existing migrations remain
  byte-identical; the function enters production structure only through exact
  migration 0009.
- **RBGC-013 — Final readiness is exact.** Version 9 is accepted only after
  exact history, function properties, ACL, constraints, triggers, structural
  fingerprint, and external verifier-pair identity pass.
- **RBGC-014 — Production/legacy firewall.** No production module imports or
  consults legacy Store, schema, or RuntimeBundle repository authority.
- **RBGC-015 — Active semantic surface remains closed.** The active catalog,
  profiles, manifests, RuntimeBundle selection, application and worker runtime,
  commands, routes, reads, materialization, and outputs remain unchanged.
- **RBGC-016 — Temporal identities remain governed inactive.** No temporal
  subject, schema, carrier row, selection binding, or decision-log state is
  changed or activated.
- **RBGC-017 — Audit separation.** This boundary adds no #192 event, receipt,
  attribution, health, delivery, or failure behavior.
- **RBGC-018 — Disposable evidence only.** Phase B tests may retain fictional
  content only on disposable targets or transactions and must leave no
  checked-in or deployed content or bundle state.

## 10. Required negative cases

Every function case begins at the supported SQL call or direct-DML boundary:

| Invariant | Counterexample | Required result |
| --- | --- | --- |
| RBGC-001 | Another function, trigger shortcut, or adapter writes global content | Changed-file and structural verification refuse |
| RBGC-002 | Application, worker, readiness, binder, selection controller, or an unrelated login calls the function | `42501`; no row |
| RBGC-003 | Digest syntax is malformed, uppercase, wrong, or names different bytes | `22023`; no row |
| RBGC-004 | Proposal adds caller length, tenant, role, logical ref, placement, bundle digest, or policy fields | Contract and signature verification refuse |
| RBGC-005 | Caller presents an existing digest as the expected digest but supplies different bytes | Digest recomputation refuses before conflict handling; original row unchanged |
| RBGC-006 | Caller attempts update, delete, truncate, replacement, or conflict update | Privilege or immutable trigger refuses |
| RBGC-007 | Publisher or control login directly inserts into `runtime_content_blob` | Insufficient privilege |
| RBGC-008 | Caller rolls back after a new retain call | No row visible after rollback |
| RBGC-009 | Retained digest is offered as selected, active, current, or command authority | No supported seam accepts that inference |
| RBGC-010 | Migration adds temporal identity, schema, carrier, command, or source-path validation | Boundary and conformance refuse |
| RBGC-011 | Migration changes `publish_runtime_bundle` | Prior-definition and boundary checks refuse |
| RBGC-012 | Migration 0001–0008 is edited, reordered, renamed, or removed | Migration and conformance authority refuse |
| RBGC-013 | Function owner, security mode, volatility, null-input posture, parallel posture, search path, signature, return, ACL, verifier, or observer differs | Final structural verification refuses and rolls back |
| RBGC-014 | New production code imports legacy persistence | Architecture conformance refuses |
| RBGC-015 | Retention adds an active catalog row, RuntimeBundle, selection, runtime import, route, read, or output | Boundary review and conformance refuse |
| RBGC-016 | A temporal artifact or lifecycle decision is rewritten or treated as active | Temporal conformance refuses |
| RBGC-017 | Implementation adds an audit event or #192 dependency | Changed-file boundary refuses |
| RBGC-018 | A test fixture or package retains content on a non-disposable target | Test-boundary review refuses |

Null digest or bytes must be an explicit invalid-parameter refusal, not a
successful null return. Zero-length non-null bytes remain structurally valid
when their exact SHA-256 is supplied; SQL must not invent a different semantic
rule.

## 11. Non-goals

Neither this Phase A contract nor its later database Phase B will:

- retain any real, checked-in, deployed, or non-disposable content row;
- choose temporal source paths or duplicate the sixteen component rows;
- define the exact whole temporal RuntimeBundle composition or its digest;
- publish, select, activate, replace, upgrade, roll back, or hot-reload a
  RuntimeBundle;
- choose a tenant or create a tenant selection record or governed batch;
- change `kernel/runtime_bundle.py`, `kernel/runtime_bundle_components.json`,
  `ofarm.publish_runtime_bundle(...)`, or a candidate artifact;
- change a role, login, membership, password, credential, connection limit,
  database-connect rule, schema-use rule, provisioning digest, or existing
  table grant;
- add a Python publisher, startup hook, service, worker, administrator API,
  route, environment switch, or mutable registry;
- change an active contract, ActiveArtifactSet, Capability Manifest, profile,
  current/default status, or lifecycle decision;
- implement the read-only tenant RuntimeBundle selector, authorization
  provider, `COMMIT_OPERATION_CLAIM_DRAFT`, public refusal mapping, current
  state, historical or WINDOW behavior, materialization, qualification, output,
  or receipt;
- add garbage collection or deletion of global content;
- reconcile an unknown production target or bypass the normal migration
  runner;
- import or modify legacy-M1 persistence or semantic behavior; or
- implement or change #192.

## 12. Proposed architecture and smallest coherent change

### 12.1 Phase A

The current draft PR changes only this RFC. It creates no implementation
authority and no repository or database state.

### 12.2 Separate conformance prerequisite

The conformance prerequisite owns only authentication and absent/present
classification of exact migration 0009 while preserving all current temporal
and architecture closures. It must merge before database Phase B.

### 12.3 Later database Phase B

The database Phase B exact path allowlist is:

| Exact path | Permitted reason |
| --- | --- |
| `kernel/migrations/0009_runtime_bundle_global_content_retention.sql` | Create the one function and exact grant; update only migration-owned final structural verification with guarded prior-state replacement. |
| `deployment/postgresql/migration_sets.py` | Append the exact migration-0009 identity and recomputed complete migration-set digest. |
| `deployment/postgresql/catalog_identity.py` | Update only `TENANT_CATALOG_VERIFIER_DIGEST` to the exact version-9 verifier/observer pair. |
| `deployment/postgresql/README.md` | Record migration 0009 and the inert publisher-custody boundary. |
| `kernel/tests/test_migration_sets.py` | Exact migration identity, order, prefix, and mutation tests. |
| `kernel/tests/test_postgresql_tenant_migration.py` | Disposable real-role function, ACL, atomicity, replay, refusal, concurrency, and no-publication tests. |
| `kernel/tests/test_postgresql_readiness_unit.py` | Mechanically affected version-9 readiness identity tests. |
| `kernel/tests/test_postgresql_structural_compatibility.py` | Exact final function and catalog posture verification. |
| `conformance/review_baseline_test_inventory.json` | Mechanical regeneration only when canonical collected node IDs change. |

No other path is permitted. In particular, database Phase B may not edit the
active temporal checker, architecture checker, provisioning specifications,
migration runner, an earlier migration, RuntimeBundle model, active component
catalog, publisher-process code, selection adapter, application or worker
runtime, a candidate, route, output, legacy file, or #192 file.

One two-argument function is smaller and clearer than direct table grants, an
owner-run loader, a generic catalog service, or a combined content-and-bundle
API. Deriving length removes one correlated caller field. Reusing the existing
publisher capability avoids another role or credential. Keeping bundle sealing
in the existing function preserves its already reviewed atomic membership
transition.

If exact implementation requires changing the existing bundle publication
function, provisioning topology, a Python publisher, or another authority, the
database Phase B stops. That change must be reviewed in the later
catalog/publication boundary or another explicit prerequisite.

## 13. Elegance audit

- Global content row sources of truth: one, `ofarm.runtime_content_blob`.
- Non-owner global content write transitions after Phase B: one.
- Bundle-sealing transitions: one, unchanged.
- Caller-supplied correlated length fields: zero.
- New roles, logins, credentials, services, registries, tables, or mutable
  pointers: zero.
- Temporal identity lists or schema validators in SQL: zero.
- Production Python modules added: zero.
- Legacy dependencies added: zero.
- Existing authorities deleted: none; there is no lawful non-owner content
  retention transition to remove.
- Compatibility aliases or fallback paths: none.

A rewrite of RuntimeBundle persistence is not justified. The missing state
transition is one small function over an existing immutable relation and an
existing publisher capability.

## 14. Provisional-design record

Not provisional.

The repository's pre-deployment human-approval evidence is provisional under
its own workflow contract. The content-addressed equality rule, publisher
custody, append-only row, migration ownership, and separation from publication
and selection are not temporary design compromises.

## 15. Traceability and verification

### 15.1 Phase A verification

Phase A must prove:

- only this RFC changed;
- every reviewed authority pin matches current `main`;
- the demonstrated administrator-DML gap is described truthfully;
- the trust boundary, function signature, authority map, state machine,
  invariants, negative cases, non-goals, file allowlist, and stop conditions
  are internally consistent;
- no implementation, migration, content, bundle, selection, runtime, route,
  output, legacy, or #192 file changed;
- `git diff --check` passes; and
- `python3 conformance/ofarm_pkg_contract_check.py` passes under the
  repository-supported CPython profile.

### 15.2 Future database Phase B traceability

| Invariants | Owning future seam | Negative evidence | Smallest verification |
| --- | --- | --- | --- |
| RBGC-001, 004, 010 | exact migration-0009 function signature and body | alternate function or extra authority fields refuse | structural compatibility and migration review |
| RBGC-002, 007 | function ACL and unchanged role topology | every non-publisher role and direct DML refuse | disposable real-role PostgreSQL tests |
| RBGC-003, 005 | digest validation, insert/conflict path, exact read-back | malformed, wrong, unequal, and concurrent conflict cases | focused tenant-migration tests |
| RBGC-006 | existing mutation trigger and no update/delete path | update, delete, truncate, and conflict-update attempts refuse | real-role tests and structural verification |
| RBGC-008, 018 | caller transaction and disposable target | rollback removes new row; no retained fixture | transactional PostgreSQL tests and scoped diff |
| RBGC-009, 015, 016 | unchanged publication, selection, runtime, catalog, and lifecycle authorities | retained blob causes no bundle or semantic state | temporal conformance and absence assertions |
| RBGC-011 | unchanged `publish_runtime_bundle` fingerprint | any function drift refuses | migration prior-definition guard and final verifier |
| RBGC-012, 013 | migration set, runner, verifier, observer, and external digest | history, ACL, body, or identity mutation rolls back or refuses | migration-set, readiness, and structural tests |
| RBGC-014 | architecture source snapshot and checker | production-to-legacy import refuses | architecture and package conformance |
| RBGC-017 | exact path allowlist | any #192 path fails boundary check | name-only diff and package conformance |

Minimum future database Phase B verification is:

```text
python3 -m pytest -q kernel/tests/test_migration_sets.py
python3 -m pytest -q kernel/tests/test_postgresql_tenant_migration.py -k 'runtime_content or runtime_bundle'
python3 -m pytest -q kernel/tests/test_postgresql_readiness_unit.py
python3 -m pytest -q kernel/tests/test_postgresql_structural_compatibility.py -k tenant
python3 conformance/temporal_contract_candidate_check.py
python3 conformance/rewrite_architecture_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

Hosted PostgreSQL 17 and native architecture lanes remain required. Passing
tests are evidence, not publication, deployment, selection, or current truth.

## 16. Open decisions and review disposition

### Open decisions

None inside this trust boundary.

The exact migration-0009 byte length, source digest, version-9 prefix/full-set
digest, structural catalog fingerprint, and final verifier-pair digest are
mechanical Phase B outputs, not caller choices or Phase A semantic decisions.

The exact temporal whole-bundle composition, its derived bundle digest, target
tenant, publication trigger, startup integration, and operational publication
act are deliberately unresolved here because they belong to the later
catalog/publication trust boundary.

### Review disposition

- **Blockers:** none identified in the author draft; independent exact-head
  review is required before a decision card.
- **Follow-ups:** the separate conformance prerequisite; then database Phase B;
  then the exact temporal catalog/publication boundary; then the read-only
  selector, authorization provider, and governed-command integration as
  separately reviewed boundaries.
- **Preferences:** none recorded.

## 17. Stop conditions

Stop before database Phase B if:

1. this exact RFC has not received explicit architect approval and merged;
2. the separate conformance contract or implementation has not merged;
3. the checker does not preserve exact version-3 and version-8 prefixes while
   authenticating the complete current migration set;
4. a reviewed authority pin differs;
5. implementation needs a path outside section 12.3;
6. an existing migration, migration runner, provisioning specification, role,
   login, membership, credential, connection rule, or table grant must change;
7. the existing bundle publication function must change;
8. semantic component identity, canonicalization, placement, schema, temporal,
   command, or catalog validation would enter SQL;
9. a Python publisher, startup hook, service, route, environment input, or
   administrator API is required;
10. a real or non-disposable content row or RuntimeBundle would be retained;
11. a temporal source path, temporal identity, whole-bundle composition,
    target tenant, bundle publication, or tenant selection must be chosen;
12. an active catalog, ActiveArtifactSet, Capability Manifest, profile,
    application/worker runtime, route, read, materialization, output, or
    current/default authority must change;
13. legacy Store, schema, repository, semantic, or output behavior must be
    imported or changed;
14. the current temporal lifecycle decision must be changed or interpreted as
    active; or
15. #192 behavior or authority must change.

If a combined content-retention and bundle-sealing API is proposed, stop. It
would change the already reviewed publication transition and requires a
separate contract rather than an expansion of this database boundary.

The production semantic surface remains closed throughout Phase A,
conformance, and database Phase B.
