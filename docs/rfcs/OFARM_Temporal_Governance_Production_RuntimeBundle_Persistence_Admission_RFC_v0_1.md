# OFARM2 Temporal-Governance Production RuntimeBundle Persistence Admission — Phase A Contract v0.1

**Status:** architect-approved Phase A contract; documentation-only, pending
merge, and without implementation, persistence, publication, selection, or
activation effect

**Contract identity:**
`ofarm.temporal-governance-production-runtime-bundle-persistence-admission.issue176.v0.1`

**Reviewed base:** `ef2c7f13882dc57aea158bd7a19c8e62d023423b`

**Phase A RFC path:**
`docs/rfcs/OFARM_Temporal_Governance_Production_RuntimeBundle_Persistence_Admission_RFC_v0_1.md`

**Date:** 2026-08-01

**Primary ticket:** #176

**Primary trust boundary:** the production tenant PostgreSQL schema's closed
RuntimeBundle component-role vocabulary and atomic publication function

**Important boundary:** production persistence is owned by the numbered
PostgreSQL migrations and `ofarm.publish_runtime_bundle(...)`.
`kernel/schema.sql`, `kernel/store.py`, and
`kernel/runtime_bundle_repository.py` remain quarantined legacy-M1
authorities.

## Approval record

- Approval channel: Codex task
  `019fa821-93c9-7ef1-8c94-1c0e92ea46b9`.
- Stable approval reference:
  `codex-task:019fa821-93c9-7ef1-8c94-1c0e92ea46b9;user-message-exact-text:approve;immediately-after-complete-amended-contract-approval-request`.
- Architect action: the designated architect sent a later user-authored message
  consisting exactly of `approve` in that same task immediately after the
  complete amended contract and explicit approval request.
- Approval scope: the exact Phase A design below and one documentation-only RFC
  publication. It does not authorize conformance implementation, migration
  implementation, publication, selection, runtime activation, or any later
  boundary.

AI-authored text, repository credentials, PR authorship, branch or commit
state, review conclusions, and PR merge do not count as architect approval.
This record is evidence of the preceding architect decision, not a substitute
for it.

## 1. Problem and goal

The merged RuntimeBundle model can validate and retain:

```text
TEMPORAL_GOVERNANCE_ARTIFACT
```

The production PostgreSQL boundary still refuses that component-role value in:

1. `ofarm.runtime_bundle_component_role_check`; and
2. the closed component-role list inside
   `ofarm.publish_runtime_bundle(uuid,text,jsonb)`.

A future reviewed publication boundary therefore cannot durably retain a
model-valid RuntimeBundle containing temporal-governance provenance.

This contract permits one later production-database implementation to admit
that exact component-role value into the existing immutable RuntimeBundle
storage protocol.

Admission remains inert. It stores no production temporal bundle, installs no
production candidate bytes, chooses no tenant bundle, and activates no temporal
behavior.

## 2. Learning value

This boundary demonstrates that production PostgreSQL can retain an already
model-validated temporal-governance component without:

- duplicating temporal identity semantics in SQL;
- crossing into catalog or publisher custody;
- reusing legacy persistence;
- treating persistence as lifecycle currentness or runtime selection; or
- opening commands, routes, reads, outputs, or #192 behavior.

## 3. Decision

After this contract is durably published as the RFC named above and followed
by the separate conformance prerequisite, one Phase B PR may add exactly one
persisted RuntimeBundle component-role value:

```text
TEMPORAL_GOVERNANCE_ARTIFACT
```

It may be added only to:

- the check constraint on
  `ofarm.runtime_bundle_component.component_role`;
- the closed component-role check inside
  `ofarm.publish_runtime_bundle(...)`; and
- migration and readiness identities mechanically affected by those changes.

The database does not acquire a temporal identity registry. Exact identity,
canonical bytes, digest, schema relationship, placement, and same-bundle
schema validation remain owned by the merged RuntimeBundle model.

Phase B must not publish or select a temporal RuntimeBundle in any checked-in
package configuration or production deployment.

Disposable real-role PostgreSQL tests must publish one exact model-valid
temporal component and its exact required schema through
`ofarm.publish_runtime_bundle(...)`. That evidence proves V4 admission,
complete atomic membership, and idempotent replay. It creates no checked-in or
deployed selection.

## 4. Durable Phase A authority and required sequence

The Phase A decision must become a durable, digest-pinnable repository
authority before conformance may permit persistence Phase B.

The required order is:

1. the designated architect explicitly approves this exact amended contract
   in the Codex task, as recorded above;
2. a documentation-only PR publishes the approved contract at the exact RFC
   path named above;
3. that PR changes only this RFC and merges before any conformance or database
   implementation;
4. one separate Phase A conformance-posture contract pins the merged
   persistence RFC's exact path, byte length, and SHA-256;
5. that conformance contract explicitly governs both:
   - the exact future migration-0004 component-role exception; and
   - stable interpretation of the governed-command candidate's
     knowledge-storage prerequisite as the exact migration prefix through
     version 3;
6. one separate conformance implementation applies both corrections with
   independent focused tests;
7. the conformance implementation continues to validate the complete current
   authoritative tenant migration set independently from the stable V3
   prerequisite prefix; and
8. only after that conformance implementation merges may persistence Phase B
   begin.

The governed-command candidate and schema must not change. Their pinned:

```text
migrationSetHead =
sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0
```

means the exact approved knowledge-storage migration prefix through
`0003_tenant_knowledge_position.sql`. It does not prohibit later tenant
migrations and must not be compared with the evolving full migration-set
digest.

The RFC PR and merge retain the approved contract bytes. They are not
substitutes for the architect's preceding explicit approval.

## 5. Mandatory separate conformance prerequisite

The active checker has two incompatible assumptions that must be corrected
before persistence Phase B:

1. it refuses the temporal component-role value in every
   `kernel/migrations/*.sql` file; and
2. it compares the governed-command candidate's V3 knowledge-storage
   prerequisite with the evolving full tenant migration-set digest.

The separate conformance amendment must correct both within the checker's
trust boundary.

### 5.1 Exact migration-0004 exception

The checker must apply this matrix:

| Persistence RFC | Exact 0004 path | Other migration | Result |
| --- | --- | --- | --- |
| exact and digest-valid | missing | component-role absent | pass |
| exact and digest-valid | present without the component-role | component-role absent | pass |
| exact and digest-valid | component-role occurs | component-role absent | pass |
| exact and digest-valid | any posture | component-role occurs | refuse |
| missing or mismatched | any posture | any posture | refuse before applying the exception |

The exact 0004 path being absent is valid before persistence Phase B begins.

The checker must continue to refuse the component-role value in:

- every migration other than exact 0004;
- `kernel/schema.sql`;
- `kernel/runtime_bundle_repository.py`;
- `kernel/runtime_bundle_components.json`;
- the active ActiveArtifactSet; and
- the active Capability Manifest.

### 5.2 Stable knowledge-storage prerequisite prefix

The checker must parse the literal `TENANT_AUTHORITATIVE_MIGRATION_SET` and
locate exactly one migration with:

```text
version              = 3
filename             = 0003_tenant_knowledge_position.sql
source digest        = sha256:d59af77e23fe012203696023ec343038dbcab5d5ffb9689be11ba67dca22f827
byte length          = 6565
applied prefix digest =
sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0
```

The checker must require the governed-command candidate's `migrationSetHead`
to equal that exact version-3 applied prefix digest.

It must not compare the candidate value with:

```text
TENANT_AUTHORITATIVE_MIGRATION_SET.digest
```

because that value identifies the evolving complete migration set.

The checker must still validate the complete current authoritative migration
set independently. A valid V3 prefix does not excuse a malformed,
non-authoritative, or inconsistent V4 migration set.

The required meaning is:

```text
candidate migrationSetHead
= exact approved knowledge-storage prefix through migration 0003
= stable after later migrations are appended
≠ current full tenant migration-set digest
```

### 5.3 Required conformance tests

The conformance implementation must independently prove:

- missing authorizing persistence RFC refuses;
- wrong RFC length refuses;
- same-length but wrong-digest RFC refuses;
- exact RFC with missing 0004 passes;
- exact RFC with 0004 present but component-role absent passes;
- component-role occurring only in exact 0004 passes;
- component-role occurring in another migration refuses;
- component-role occurring in each existing forbidden authority refuses;
- V3 as the current full migration-set head passes;
- appending an exact migration 0004 passes while the V3 prefix remains
  unchanged;
- editing, renaming, removing, reordering, or changing migration 0003 refuses;
- changing the V3 applied prefix digest refuses;
- zero or multiple version-3 migration entries refuse;
- changing the candidate's pinned V3 value refuses;
- substituting the later V4 full-set digest into the candidate refuses; and
- the complete current authoritative migration set remains independently
  validated.

The conformance authority must not change inside persistence Phase B.

## 6. Reviewed authority pins

This contract relies on:

- production migration service: `ofarm.tenant-postgresql.v1`;
- current migration head: version `3`;
- current full migration-set digest at the reviewed base:
  `sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0`;
- stable knowledge-storage prefix through version 3:
  `sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0`;
- migration 0003 source digest:
  `sha256:d59af77e23fe012203696023ec343038dbcab5d5ffb9689be11ba67dca22f827`;
- migration 0003 byte length: `6565`;
- model-admission contract:
  `ofarm.temporal-governance-runtime-bundle-model-admission.issue176.v0.1`;
- model-admission RFC byte length: `33787`;
- model-admission RFC digest:
  `sha256:9dbe62b18f4214b93b02ae2ccd8d17ee40aed4e1925fff7482993b2eedc9fac8`;
- merged model implementation head:
  `580afd7d5749c0a7dbc0547cf432694367f9b03c`;
- carrier contract:
  `ofarm.temporal-governance-runtime-bundle-carrier.v0.1`;
- current decision-log entry identity:
  `sha256:ed48914f77bedacdfce32fb621819da7df7701b54d7862477db0a49ceee5cdc6`;
- current decision-log file digest:
  `sha256:72a2319430eb1a74c2e99f9ef68aab5c17081b37390b4488b8187bb698ebde80`;
- production publication function:
  `ofarm.publish_runtime_bundle(uuid,text,jsonb)`;
- production at-rest constraint:
  `runtime_bundle_component_role_check`; and
- external tenant catalog-verifier trust anchor:
  `deployment/postgresql/catalog_identity.py::TENANT_CATALOG_VERIFIER_DIGEST`.

At the reviewed V3 base, the full-set digest and V3 prefix digest happen to be
equal. After migration 0004, they intentionally differ.

If the model's identity set, role semantics, lifecycle decision, migration
architecture, or publication trust model changes before Phase B,
implementation stops for review.

## 7. Trust model

### Protected assets

- The closed persisted RuntimeBundle component-role vocabulary.
- Exact RuntimeBundle identity bytes and digest.
- Exact component bytes, digest, length, canonicalization, and placement.
- Immutable bundle membership after publication.
- Publisher-only production write custody.
- Numbered migration history and readiness identity.
- The stable knowledge-storage prefix through migration 0003.
- The independently evolving complete migration-set identity.
- The locked provisioning boundary during migration.
- The migration-owned structural verifier.
- The external final-state verifier-pair trust anchor.
- The distinctions between model validation, persistence, publication,
  selection, activation, and execution.
- The production-versus-legacy firewall.

### Trusted components

- The merged RuntimeBundle model for complete temporal component validation.
- The separately governed startup publisher, once a later contract activates
  it.
- `ofarm.publish_runtime_bundle(...)` for closed SQL admission and atomic
  sealing.
- PostgreSQL constraints, foreign keys, digest checks, and transaction
  atomicity.
- The authoritative migration loader, runner, ledger, migration lock, and
  structural verifier.
- `MigrationSet.prefix_digest(version)` semantics for stable history-prefix
  identity.
- Migration 0004's exact guards over the prior definitions it changes.
- `deployment/postgresql/catalog_identity.py` for authenticating the final V4
  verifier and observer pair.
- The unreachable database owner and reviewed migrator boundary.

### Untrusted actors and inputs

- `requested_tenant_id`, expected digest, and bundle document before SQL
  validation.
- Arbitrary component-role values and logical references.
- Application and worker roles attempting publication or direct DML.
- Request fields, headers, claims, profiles, environment values, routes, and
  caller-selected registries.
- Existing content or bundle rows presented as proof of lifecycle currentness,
  selection, activation, or command authority.
- An evolving full migration-set digest presented as a substitute for the
  stable V3 prerequisite prefix.

### Excluded compromise capabilities

Database-owner, migrator, DBA, operating-system, PostgreSQL implementation,
cryptographic-hash, or trusted startup-publisher compromise is outside this
boundary.

Bypassing model validation while exercising the publisher credential is
compromised publisher custody. SQL deliberately does not duplicate the
model's three-identity validator.

Supported migration interruption and concurrent ordinary-role access remain
in scope and must be atomic or fail closed.

## 8. Authority map

- ADR 0001 owns production migrations, database roles, immutable RuntimeBundle
  storage, and publisher custody.
- ADR 0002 owns `ValidCut`, `KnowledgeCut`, half-open intervals, and temporal
  meanings.
- The temporal carrier contract owns the component-role's meaning and closed
  allowed identity family.
- The model-admission contract and `kernel/runtime_bundle.py` own exact
  identity, digest, schema, canonicalization, placement, and same-bundle
  validation.
- The governed-command candidate pins its knowledge-storage prerequisite to
  the exact history through migration 0003.
- `MigrationSet.prefix_digest(3)` supplies the stable identity of that
  approved history prefix.
- The complete `TENANT_AUTHORITATIVE_MIGRATION_SET.digest` independently
  identifies the current full release and may advance after later migrations.
- The current decision log owns lifecycle currentness. Its state remains
  `GOVERNED_INACTIVE`.
- Numbered tenant migrations own production SQL structure and functions.
- `runtime_bundle_component_role_check` owns the durable at-rest
  component-role vocabulary.
- `ofarm.publish_runtime_bundle(...)` owns the non-owner production transition
  from retained bytes to a sealed RuntimeBundle.
- Migration 0004 owns exact guarded replacement of the V3 definitions it
  changes.
- `ofarm.verify_tenant_structure()` owns complete migration-owned symbolic
  catalog verification.
- `ofarm.observe_tenant_contract()` exposes the structural result to
  readiness.
- `TENANT_CATALOG_VERIFIER_DIGEST` authenticates the final V4 verifier and
  observer pair.
- The unchanged migration runner owns:
  - authoritative local migration-set validation;
  - infrastructure observation and migrator connection;
  - the protected transaction and migration lock;
  - catalog-output settings;
  - locked provisioning-boundary verification;
  - migration-ledger contract and history verification;
  - proof that migration SQL did not alter the ledger or widen provisioning;
  - ledger insertion;
  - final V4 verification; and
  - commit.
- The separate conformance contract owns checker interpretation of the stable
  V3 prerequisite prefix and the exact 0004 exception.
- A later catalog/publication contract will own which bytes and bundle
  composition the publisher may submit.
- The tenant command-selection contract owns future tenant selection and
  command-required closure.
- The governed-command contract owns future command behavior.
- `kernel/schema.sql`, `kernel/store.py`, and
  `kernel/runtime_bundle_repository.py` remain legacy-only.
- #192 retains sole authority over audit-runtime behavior.

No SQL table, caller input, or environment value becomes a second temporal
identity authority.

## 9. State machine and ordering

### Phase A

```text
PROPOSED_CONTRACT
  -> EXPLICIT_ARCHITECT_APPROVAL
  -> EXACT_RFC_PUBLISHED
  -> MERGED_DIGEST_PIN_AVAILABLE
```

A PR merge without preceding explicit approval is not a valid transition.

### Conformance prerequisite

```text
MERGED_PERSISTENCE_RFC
  -> EXACT_RFC_PATH_LENGTH_DIGEST_PINNED
  -> STABLE_V3_KNOWLEDGE_PREFIX_RULE_IMPLEMENTED
  -> EXACT_0004_PATH_EXCEPTION_IMPLEMENTED
  -> COMPLETE_CURRENT_MIGRATION_SET_STILL_VALIDATED
  -> CONFORMANCE_PREREQUISITE_MERGED
```

The prefix correction and 0004 exception may share one separately reviewed
conformance contract and implementation because they change one primary trust
boundary: temporal candidate conformance interpretation of migration
authority. They must remain independently specified and tested.

### Migration state

```text
PRODUCTION_SCHEMA_V3_COMPONENT_ROLE_CLOSED
  -> AUTHORITATIVE_LOCAL_V4_SET_VALIDATED
  -> ONE_PROTECTED_RUNNER_TRANSACTION_OPEN_AND_LOCKED
  -> EXACT_V3_LEDGER_HISTORY_AND_BOUNDARY_VERIFIED
  -> PRIOR_DEFINITIONS_GUARDED_AND_V4_DDL_APPLIED
  -> EXACT_V4_LEDGER_ROW_APPENDED
  -> EXACT_V4_VERIFIER_PAIR_AND_STRUCTURE_AUTHENTICATED
  -> PRODUCTION_SCHEMA_V4_COMPONENT_ROLE_ADMISSIBLE_INERT
```

The normative ordering is:

1. the runner validates and preflights the authoritative local V4 migration
   set before connecting;
2. the runner observes the fixed infrastructure and opens the migrator route;
3. the runner begins the protected migration transaction, acquires the
   migration lock, and fixes the catalog-output settings;
4. inside that locked transaction, the runner verifies:
   - the locked provisioning boundary;
   - the exact migration-ledger contract; and
   - the exact V3 migration-history prefix;
5. migration 0004 refuses unless the expected V3:
   - component-role constraint;
   - publication-function definition; and
   - verifier source markers needed for controlled replacement
   are exact;
6. migration 0004 applies the component-role constraint,
   publication-function, and migration-owned verifier changes;
7. the runner proves migration SQL did not alter the ledger or widen the
   provisioning boundary;
8. the runner appends the exact V4 ledger row with the authoritative source
   identity and V4 prefix digest;
9. the runner authenticates the final V4 verifier and observer pair using the
   new `TENANT_CATALOG_VERIFIER_DIGEST`;
10. the runner executes the complete V4 structural verifier; and
11. only then does the runner commit.

The existing runner does not externally authenticate the V3 verifier pair
before an additive migration. This contract does not require that behavior and
does not change the runner.

Any failure rolls back the DDL and ledger append together. A tampered unchanged
observer changes the final V4 verifier-pair digest and causes rollback. A
tampered constraint, publication function, or verifier source required for
replacement is refused by migration 0004's prior-definition guards.

### Future publication state

```text
MODEL_VALIDATED_RUNTIME_BUNDLE
  + EXACT_CONTENT_ALREADY_RETAINED
  + AUTHORIZED_PUBLISHER
  -> SQL_DOCUMENT_AND_DIGEST_VALIDATED
  -> COMPONENT_REFERENCES_VERIFIED
  -> BUNDLE_AND_COMPLETE_MEMBERSHIP_INSERTED_ATOMICALLY
  -> PERSISTED_INERT_RUNTIME_BUNDLE
```

Phase B exercises this transition only in a disposable real-role PostgreSQL
test. It does not perform it in checked-in configuration or production
deployment.

There is no transition from persistence to lifecycle promotion, tenant
selection, command execution, materialization, output, or current truth.

## 10. Invariants and acceptance criteria

- **TGPDA-001 — One new persisted RuntimeBundle component-role value.** V4
  adds only `TEMPORAL_GOVERNANCE_ARTIFACT`; existing values remain unchanged
  and unknown values refuse.
- **TGPDA-002 — Production boundary only.** Only the numbered migration and
  its mechanical release/readiness authorities change; no legacy persistence
  authority changes.
- **TGPDA-003 — Immutable forward history.** Existing migrations remain
  byte-identical. Admission occurs only through
  `0004_temporal_governance_runtime_bundle_role.sql`.
- **TGPDA-004 — Atomic version transition.** A database exposes either
  complete V3 refusal or authenticated complete V4 admission, never a partial
  combination.
- **TGPDA-005 — Publisher custody unchanged.** Only the existing publisher
  capability or owner may call the publication function. No PostgreSQL
  principal role, grant, login, membership, ownership, or direct-DML privilege
  changes.
- **TGPDA-006 — Existing exactness preserved.** Bundle digest, canonical
  ordering, length, placement, content-digest foreign keys, exact replay, and
  unequal-reuse refusal remain unchanged.
- **TGPDA-007 — No duplicated temporal semantics.** SQL admits the
  component-role value but introduces no three-identity list, schema validator,
  carrier matrix, selector, lifecycle check, or command-closure validator.
- **TGPDA-008 — Persistence is inert.** A stored component or bundle is not
  promotion, current/default status, tenant selection, activation,
  authorization, registration, execution, materialization, qualification,
  output, or truth.
- **TGPDA-009 — Caller data cannot widen authority.** Caller values cannot
  alter the component-role set, migration identity, fingerprints, publication
  authority, or model rules.
- **TGPDA-010 — Catalog and selection remain closed.** No temporal component
  enters the catalog, package-loading configuration, active bundle, tenant
  selection record, selector, profile, or capability manifest.
- **TGPDA-011 — Final V4 readiness has both trust anchors.** Before commit,
  the runner proves:
  1. the exact V4 migration history and prefix digest;
  2. the exact V4 component-role constraint;
  3. the changed publication-function fingerprint;
  4. the complete migration-owned structural catalog fingerprint; and
  5. the external digest of the exact V4 `verify_tenant_structure()` and
     `observe_tenant_contract()` pair.
- **TGPDA-012 — Prior definitions are guarded inside the locked
  transaction.** Migration 0004 refuses unless the exact V3 constraint,
  publication-function definition, and verifier source markers it replaces are
  present after the runner acquires the migration lock and verifies V3 history.
- **TGPDA-013 — Lifecycle state is unchanged.** The three temporal identities
  remain `GOVERNED_INACTIVE`; database admission creates no lifecycle decision
  or currentness evidence.
- **TGPDA-014 — Production firewall remains closed.** No production module
  imports the legacy Store or persistence path.
- **TGPDA-015 — Audit separation.** This boundary emits no #192 event,
  receipt, reason, readiness rule, or delivery behavior.
- **TGPDA-016 — Positive evidence is disposable and bounded.** Test
  publication uses one exact model-valid temporal component and its required
  schema, proves complete membership and idempotent replay, and creates no
  checked-in or deployed selection.
- **TGPDA-017 — Knowledge-storage prerequisite remains a stable prefix.** The
  governed-command candidate's `migrationSetHead` continues to equal the exact
  prefix through migration 0003 after migration 0004 is appended. It never
  floats to the later full-set digest.

## 11. Required negative cases

| Invariant | Counterexample | Required result |
| --- | --- | --- |
| TGPDA-001 | Publisher submits `TEMPORAL_GOVERNANCE_ARTIFACT_V2` | Refuse; no bundle row |
| TGPDA-002 | Change adds the value to legacy schema or repository | Boundary and conformance refuse |
| TGPDA-003 | Existing migration is edited, renamed, removed, or reordered | Authoritative loader refuses |
| TGPDA-004 | Migration or final verification fails after DDL begins | Protected transaction rolls back DDL and ledger append |
| TGPDA-005 | App or worker calls publication or directly inserts membership | Insufficient privilege |
| TGPDA-006 | Publisher supplies missing bytes, wrong length, wrong digest, unsorted or duplicate components, or unequal replay | Existing refusal remains; no partial membership |
| TGPDA-007 | Proposal adds temporal identity rows or schemas to SQL | Scope expansion refuses |
| TGPDA-008 | Request presents a persisted digest as runtime selection | No production seam accepts it |
| TGPDA-009 | Caller supplies a component-role list, RFC path, migration digest, or fingerprint | No such parameter exists |
| TGPDA-010 | Manifest loading encounters the temporal value or candidate path | It continues to refuse |
| TGPDA-011 | Final verifier, observer, constraint, function, grant, or ledger differs | External identity or structural verification refuses and rolls back |
| TGPDA-012 | Locked V3 definition required for replacement is altered | Migration 0004 refuses before replacement |
| TGPDA-013 | Persisted membership is offered as activation or currentness evidence | No effect |
| TGPDA-014 | Production gains an import path to legacy persistence | Architecture conformance refuses |
| TGPDA-015 | Persistence admission attempts to emit audit behavior | Boundary and package conformance refuse |
| TGPDA-016 | Positive test evidence appears in catalog, profile, selection, deployment, decision log, command, route, or output | Boundary review refuses |
| TGPDA-017 | Checker substitutes the V4 full-set digest for the candidate's pinned V3 value | Conformance refuses; candidate bytes remain unchanged |

## 12. Proposed architecture and smallest coherent change

### Phase A RFC publication

This PR may add only this RFC. The approval record above may record the
preceding architect message without changing the approved decision.

### Separate conformance prerequisite

One separately approved conformance contract and implementation may change the
temporal checker and focused tests to:

- authenticate the merged persistence RFC;
- permit the component-role value only in exact future migration 0004;
- preserve the V3 knowledge-storage prerequisite as an exact stable prefix;
  and
- continue independently validating the complete current migration set.

It must not modify candidate, schema, model, lifecycle, or decision-log bytes.

### Future persistence Phase B

After the conformance prerequisite merges, Phase B may change only:

- `kernel/migrations/0004_temporal_governance_runtime_bundle_role.sql`;
- `deployment/postgresql/migration_sets.py`;
- `deployment/postgresql/catalog_identity.py`, limited to the mechanically
  recomputed `TENANT_CATALOG_VERIFIER_DIGEST`;
- `deployment/postgresql/README.md`, with the exact V4 migration inventory;
- `kernel/tests/test_migration_sets.py`;
- `kernel/tests/test_postgresql_tenant_migration.py`;
- `kernel/tests/test_postgresql_readiness_unit.py`;
- `kernel/tests/test_postgresql_structural_compatibility.py`; and
- canonical test-node inventory metadata only when mechanically required by a
  count or node-ID change.

Updating `deployment/postgresql/README.md` is required.

Migration 0004 must use guarded prior-definition replacement inside the
runner's existing locked transaction and leave ledger insertion to the
unchanged runner.

It must not edit:

- `deployment/postgresql/migration_runner.py`;
- `kernel/migrations/0001_initial.sql`;
- `kernel/schema.sql`;
- `kernel/runtime_bundle_repository.py`;
- `kernel/store.py`;
- `kernel/runtime_bundle.py`;
- `kernel/runtime_bundle_components.json`;
- temporal candidates or schemas;
- profiles, manifests, decision logs, routes, outputs, or #192 files.

## 13. Elegance audit

- Temporal semantic truth: one—the merged RuntimeBundle model.
- Knowledge-storage prerequisite identity: one stable version-3 prefix.
- Current database-release identity: one independently evolving full
  migration-set digest.
- Database component-role enforcement points: two existing intentional checks.
- Publication transition: one—`ofarm.publish_runtime_bundle(...)`.
- Migration transaction and lock authority: the unchanged runner.
- Prior-definition authority: exact migration-local guards after locking.
- Final structural verifier: one.
- Final external verifier-pair trust anchor: one.
- Candidate or schema rewrite: none.
- Historical external digest selection added: none.
- Runner changes: none.
- New tables, services, registries, switches, or aliases: none.
- Legacy authority introduced: none.

The stable-prefix correction uses the migration framework's existing identity
semantics. It does not introduce another migration registry.

## 14. Pull-request boundaries and dependencies

### Phase A RFC PR

Allowed file:

- `docs/rfcs/OFARM_Temporal_Governance_Production_RuntimeBundle_Persistence_Admission_RFC_v0_1.md`.

### Conformance prerequisite

A separate approved contract and separate implementation own both:

1. the exact migration-0004 component-role exception; and
2. stable V3 knowledge-storage prerequisite-prefix interpretation.

Both must merge before persistence Phase B.

### Persistence Phase B PR

One primary trust boundary: production PostgreSQL RuntimeBundle component-role
admission.

Mandatory dependencies:

1. explicit approval of this exact amended contract;
2. merged documentation-only RFC;
3. merged conformance-posture contract;
4. merged conformance implementation covering both corrections;
5. conformance proof that an exact V4 full set coexists with the unchanged V3
   prerequisite prefix;
6. unchanged candidate and schema bytes;
7. unchanged model-admission authority; and
8. unchanged current temporal decision entry.

Reviewers must not require catalog membership, publisher-process changes,
production candidate installation, tenant selection, commands, routes, reads,
outputs, historical/WINDOW behavior, legacy changes, or #192 behavior.

## 15. Provisional-design record

Not provisional.

The pre-deployment decision-log mechanism remains provisional under its own
contract. Production migration architecture, immutable RuntimeBundle storage,
publisher custody, stable migration-prefix identity, and the model/database
authority split are not temporary.

## 16. Traceability and verification

### Conformance prerequisite

| Required rule | Owning future seam | Required evidence |
| --- | --- | --- |
| Persistence RFC authority | temporal checker | exact path, length, and digest; missing and mutation refusals |
| Exact 0004 exception | temporal checker | missing, role-absent, exact-role-present, and other-migration cases |
| Stable V3 prerequisite prefix | temporal checker | exact version, filename, source digest, byte length, and applied prefix |
| Full-set independence | temporal checker | V3 full head passes; exact V4 append passes without changing candidate |
| Prefix mutation refusal | focused checker tests | edit, rename, remove, reorder, duplicate, digest change, and candidate substitution refuse |
| Candidate immutability | boundary diff | candidate and exact schema bytes unchanged |

The conformance prerequisite must pass:

```text
python3 -m pytest -q kernel/tests/test_temporal_contract_governance.py
python3 conformance/temporal_contract_candidate_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

### Persistence Phase B

| Invariants | Owning future seam | Required evidence | Smallest verification |
| --- | --- | --- | --- |
| TGPDA-001, 003, 004 | migration 0004, unchanged runner, migration set | V3→V4 upgrade, unknown-value refusal, rollback proof | migration-set and tenant-migration tests |
| TGPDA-002, 014 | boundary diff and architecture checker | no legacy change or production-to-legacy import | package conformance |
| TGPDA-005 | grants and publication function | app/worker refusal; publisher-only success | real-role tests |
| TGPDA-006, 016 | publication function and disposable fixture | exact component plus schema, complete membership, replay, mutation refusals | focused publication tests |
| TGPDA-007 | model and SQL diff | no temporal semantic validator in SQL | model tests and review |
| TGPDA-008, 010, 013 | unchanged catalog, selector, runtime, and decision log | no activation or selection path | temporal conformance |
| TGPDA-009 | fixed migration SQL and function signature | no caller-selected authority seam | review and mutation tests |
| TGPDA-011 | V4 verifier, observer, and external digest | exact final success and tamper rollback | readiness and structural tests |
| TGPDA-012 | locked migration-0004 guards | altered V3 constraint, function, or verifier markers refuse | tenant-migration tests |
| TGPDA-015 | unchanged #192 authorities | no audit change | scoped diff and package conformance |
| TGPDA-017 | merged conformance prerequisite | unchanged candidate passes against V4 set using V3 prefix | temporal checker |

Mechanically derived persistence Phase B outputs are:

- migration 0004 byte length and SHA-256;
- V4 prefix and full migration-set digests;
- changed `publish_runtime_bundle(...)` fingerprint;
- complete V4 structural catalog fingerprint; and
- V4 `TENANT_CATALOG_VERIFIER_DIGEST`.

Minimum persistence Phase B verification:

```text
python3 -m pytest -q kernel/tests/test_migration_sets.py
python3 -m pytest -q kernel/tests/test_postgresql_tenant_migration.py -k 'runtime_bundle or temporal_governance'
python3 -m pytest -q kernel/tests/test_runtime_bundle.py -k temporal_governance
python3 -m pytest -q kernel/tests/test_postgresql_readiness_unit.py
python3 -m pytest -q kernel/tests/test_postgresql_structural_compatibility.py -k tenant
python3 conformance/temporal_contract_candidate_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

The Phase B handoff must prove no forbidden path changed and that disposable
publication caused no selection, lifecycle, activation, command, route,
output, or audit effect.

## 17. Open decisions and review disposition

### Open decisions

None inside this boundary.

The following are mechanical outputs rather than design decisions:

- V4 migration source identity;
- V4 prefix and full-set digests;
- publication-function fingerprint;
- complete structural catalog fingerprint; and
- final V4 verifier-pair digest.

### Review disposition

- **Blockers:** none in the approved design. The stable V3
  prerequisite-prefix correction is a mandatory part of the separate
  conformance boundary.
- **Follow-ups:** separate conformance contract and implementation;
  catalog/publication admission; tenant selection storage and controller;
  read-only selector; authorization provider; governed command integration;
  later read/output contracts.
- **Preferences:** the component-role terminology correction is incorporated.

## 18. Stop conditions

Stop before persistence Phase B if:

- this RFC is not merged;
- the separate conformance contract does not explicitly govern both the exact
  0004 exception and stable V3 prefix;
- the conformance implementation is not merged;
- the checker still compares the candidate prerequisite with the evolving
  full migration-set digest;
- candidate or schema bytes would need to change;
- the complete current authoritative migration set is no longer independently
  validated;
- implementation requires changing the migration runner;
- implementation requires historical external-verifier digest selection;
- implementation requires changing legacy persistence;
- implementation requires catalog or publisher-process custody;
- SQL would duplicate temporal identity or carrier semantics;
- a PostgreSQL principal role, grant, login, membership, privilege, or
  credential must change;
- tenant selection, authorization, command, route, materialization, read,
  output, historical/WINDOW, or #192 behavior is required;
- the temporal lifecycle decision is superseded;
- the model's component-role or identity rules differ; or
- an existing migration would need editing.

Outside the expressly permitted disposable real-role PostgreSQL test,
implementation must stop if any temporal candidate byte or temporal
RuntimeBundle must be published.

The production semantic surface remains closed throughout this boundary.
