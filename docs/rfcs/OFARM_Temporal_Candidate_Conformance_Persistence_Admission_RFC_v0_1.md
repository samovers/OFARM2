# OFARM2 Temporal Candidate Conformance Persistence-Admission Posture — Phase A Contract v0.1

**Status:** architect-approved Phase A contract; documentation-only, pending
merge, and without conformance, database, runtime, publication, selection, or
activation effect

**Contract identity:**
`ofarm.temporal-candidate-conformance-persistence-admission.issue176.v0.1`

**Reviewed base:**
`2ce2a4d9ebfe672ef048338c5bd0dbc6058f86ee`

**RFC path:**
`docs/rfcs/OFARM_Temporal_Candidate_Conformance_Persistence_Admission_RFC_v0_1.md`

**Date:** 2026-08-01

**Primary ticket:** #176

**Primary trust boundary:** the temporal candidate conformance checker's
interpretation of production tenant-migration authority

**Phase A PR boundary:** this RFC only

**Future Phase B PR boundary:** the temporal candidate checker, its focused
tests, and mechanically required canonical test-inventory metadata only

## Approval record

- Approval channel: Codex task
  `019fa821-93c9-7ef1-8c94-1c0e92ea46b9`.
- Approval turn: `019fbd32-45e5-79b0-83dc-f7798bf591f9`.
- Stable user-message reference: `item-1377`.
- Exact user-message text: `Approved`.
- Architect action: the designated architect sent that later user-authored
  message in the same task immediately after the complete amended contract
  was returned and the no-blocker review was reported.
- Approval scope: this exact Phase A design and one documentation-only RFC
  publication. It does not authorize conformance implementation, migration
  implementation, publication, selection, runtime activation, or any later
  boundary.
- Review evidence: issue #176 comment `5151320081` reported no blockers and
  readiness for explicit architect approval. That review was not itself the
  approval authority.

AI-authored text, repository credentials, PR authorship, branch or commit
state, review conclusions, and PR merge do not count as architect approval.
This record is evidence of the preceding architect decision, not a substitute
for it.

## 1. Problem and goal

The merged persistence-admission contract permits a later migration to admit
exactly one persisted RuntimeBundle component-role value:

```text
TEMPORAL_GOVERNANCE_ARTIFACT
```

That admission may occur only in:

```text
kernel/migrations/0004_temporal_governance_runtime_bundle_role.sql
```

The current temporal checker prevents that later boundary in two ways:

1. `validate_runtime_bundle_carrier_role_posture()` refuses the role text in
   every checked-in tenant migration.
2. `_tenant_authoritative_migration_set_head()` returns the evolving complete
   `TENANT_AUTHORITATIVE_MIGRATION_SET.digest`, which the command validator
   incorrectly treats as the command candidate's fixed knowledge-storage
   prerequisite.

At migration version 3, the complete-set digest and knowledge-storage prefix
happen to be equal:

```text
sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0
```

After migration 0004, they intentionally differ.

The candidate must continue to identify the approved history through
migration 0003, while the production migration authority independently
authenticates the complete current release.

This contract defines only that conformance interpretation. It does not add
migration 0004, change production persistence, rewrite a candidate, or
activate temporal behavior.

## 2. Learning value

This boundary demonstrates that a fixed historical prerequisite can remain
stable while the independently authenticated production migration release
advances, without rewriting candidate bytes or weakening migration authority.

It also demonstrates that one authenticated migration snapshot can support:

- complete-release authentication;
- historical-prefix verification; and
- migration-role classification

without a second filesystem scan or a second migration authority.

## 3. Decision

After this contract is durably published in a documentation-only PR, one
separate Phase B conformance PR may make two related corrections.

### 3.1 One authenticated migration snapshot

The checker must authenticate and retain exactly one current tenant
`MigrationSet`.

The required sequence is:

1. Authenticate the merged persistence-admission RFC by fixed path, byte
   length, and SHA-256.
2. Load the exact fixed production migration-authority module at:

   ```text
   deployment/postgresql/migration_sets.py
   ```

3. Call exactly once:

   ```text
   load_authoritative_migration_set(PACKAGE_ROOT, TENANT_SERVICE)
   ```

4. Retain the returned authenticated `MigrationSet`.
5. Use that same object for:
   - version-3 migration identity;
   - `prefix_digest(3)`;
   - candidate prerequisite comparison; and
   - role classification from each authenticated `Migration.source_bytes`.
6. Perform no second migration-directory glob, source-file read, or
   migration-set load.

A normal import of `deployment.postgresql.migration_sets` executes
`deployment/postgresql/__init__.py`, which requires `psycopg`. The mandatory
package checker is zero-dependency.

The conformance implementation must therefore load the exact fixed
`migration_sets.py` module path using only the Python standard library. It
must not:

- import through `deployment.postgresql.__init__`;
- add `psycopg` or another dependency;
- edit `deployment/postgresql/__init__.py`; or
- copy the production migration loader into the checker.

The fixed module path is reviewed code, never caller data. Its source snapshot
must supply both the parsed literal and the executed production loader so
those observations cannot silently come from different module revisions.

Module-loading, authority-shape, or `MigrationSetError` failures must become
closed `TemporalCandidateError` refusals. They must not escape as an unhandled
checker crash.

### 3.2 Exact migration-0004 exception

The checker may permit the role text only in the authenticated migration whose
filename is exactly:

```text
0004_temporal_governance_runtime_bundle_role.sql
```

It must classify role occurrence from the retained authenticated:

```text
Migration.source_bytes
```

It must not reread the migration path from the filesystem.

The role-posture matrix is:

| Persistence RFC | Authenticated release | Exact 0004 | Other authenticated migrations | Result |
| --- | --- | --- | --- | --- |
| Exact | Authentic V3 | Missing | Role absent | Pass |
| Exact | Authentic current release | Present without role | Role absent | Pass this posture check |
| Exact | Authentic current release | Present with role | Role absent | Pass this posture check |
| Exact | Invalid or non-authoritative | Any | Any | Refuse |
| Exact | Authentic | Any | Role present | Refuse |
| Missing or mismatched | Any | Any | Any | Refuse before applying the exception |

An unlisted, renamed, extra, or otherwise non-authoritative 0004 never reaches
the exception because the production loader refuses it first.

Passing the role-posture check does not validate migration SQL. Constraint
replacement, publication-function behavior, ledger identity, rollback,
readiness, and real-role database tests remain owned by the later persistence
Phase B contract.

### 3.3 Stable authenticated V3 prerequisite

The checker must parse the source assignment named:

```text
TENANT_AUTHORITATIVE_MIGRATION_SET
```

and locate exactly one literal `AuthoritativeMigration` entry with:

```text
version               = 3
filename              = 0003_tenant_knowledge_position.sql
source_sha256         = sha256:d59af77e23fe012203696023ec343038dbcab5d5ffb9689be11ba67dca22f827
byte_length           = 6565
applied_prefix_digest = sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0
```

The named literal is necessary but not sufficient.

The retained authenticated `MigrationSet` must itself contain, at position
and version 3:

- filename `0003_tenant_knowledge_position.sql`;
- the exact source SHA-256 above;
- byte length `6565`; and
- computed `migration_set.prefix_digest(3)` equal to the literal's
  `applied_prefix_digest`.

The governed-command candidate's existing `migrationSetHead` must equal that
same computed prefix.

The required binding is:

```text
parsed named V3 literal applied_prefix_digest
= authenticated MigrationSet.prefix_digest(3)
= governed-command candidate migrationSetHead
```

The checker must not compare the candidate with:

```text
TENANT_AUTHORITATIVE_MIGRATION_SET.digest
```

The complete-set digest may advance. The authenticated V3 prefix must not.

### 3.4 Authority-substitution refusal

The checker must refuse if the named literal remains exact but the release
selected and authenticated by the production loader has a different:

- version-3 migration;
- version-3 source digest;
- version-3 byte length; or
- computed version-3 prefix.

This closes the possibility that `AUTHORITATIVE_MIGRATION_SETS` selects a
different tenant release while the historical named variable remains
unchanged.

## 4. Reviewed authority pins

This contract relies on:

- merged persistence-admission contract:
  `ofarm.temporal-governance-production-runtime-bundle-persistence-admission.issue176.v0.1`;
- persistence-admission RFC path:
  `docs/rfcs/OFARM_Temporal_Governance_Production_RuntimeBundle_Persistence_Admission_RFC_v0_1.md`;
- exact persistence-admission RFC byte length: `37254`;
- exact persistence-admission RFC digest:
  `sha256:40a20c5053857664cfbb2d6ac2814c6136125eb9908635495af9377e9d9f0870`;
- role: `TEMPORAL_GOVERNANCE_ARTIFACT`;
- exact future exception filename:
  `0004_temporal_governance_runtime_bundle_role.sql`;
- migration authority path: `deployment/postgresql/migration_sets.py`;
- named migration authority: `TENANT_AUTHORITATIVE_MIGRATION_SET`;
- complete-release loader: `load_authoritative_migration_set`;
- tenant service: `ofarm.tenant-postgresql.v1`;
- current complete migration version: `3`;
- current complete-set digest:
  `sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0`;
- knowledge-storage identity:
  `ofarm.tenant-knowledge-position-storage.v0.1`;
- knowledge-storage RFC digest:
  `sha256:6ddf1b6b289c9e638646cf7ddd356165f3ec8cbcc96b3c988e3f6585d11f26f8`;
- migration-0003 source digest:
  `sha256:d59af77e23fe012203696023ec343038dbcab5d5ffb9689be11ba67dca22f827`;
- migration-0003 byte length: `6565`;
- governed-command candidate path:
  `contracts/candidates/temporal_governed_command/OFARM_OperationClaimDraftTemporalCommand_candidate_v0_1.json`;
- governed-command candidate byte length: `11985`;
- governed-command candidate digest:
  `sha256:0909ec653cb99a94cd1b35afaf2d386258aac671c5f730960ed485df8a4b8f2e`;
- governed-command exact-schema digest:
  `sha256:afda003df90e2787cfdc97f5561e3e5b098177a5add91556af2e935a3b9711db`;
- checker path: `conformance/temporal_contract_candidate_check.py`;
- role-posture function:
  `validate_runtime_bundle_carrier_role_posture()`; and
- full-set-head helper to replace:
  `_tenant_authoritative_migration_set_head()`.

The RFC and candidate pins and authenticated V3 prefix were independently
recomputed at the reviewed base.

If any load-bearing identity changes before Phase B, implementation stops for
review.

## 5. Authority map

- The persistence-admission RFC owns permission for the exact future 0004
  exception.
- The fixed `migration_sets.py` source owns migration-service and
  complete-release definitions.
- Its existing loader owns complete migration-release authentication.
- One returned `MigrationSet` owns the authenticated source-byte snapshot used
  by this check.
- The parsed named literal owns the reviewed statement of the stable V3
  prerequisite.
- The authenticated `MigrationSet.prefix_digest(3)` proves that the current
  production release contains that same historical prefix.
- The governed-command candidate owns its unchanged `migrationSetHead`.
- The temporal checker owns only the equality among those three V3 values and
  the role classification over authenticated migration bytes.
- Migration 0004 SQL remains owned by the separate persistence Phase B
  contract.
- The RuntimeBundle model retains inert model-eligibility authority.
- Repository and SQL schema paths remain closed legacy or non-authoritative
  persistence surfaces.
- The runtime catalog retains active component authority and remains closed.
- The temporal decision log retains lifecycle-currentness authority.
- Tenant selection, commands, authorization, routes, reads, and outputs remain
  separate later authorities.
- ADR 0002 retains temporal meanings and half-open interval rules.
- #192 retains sole audit-runtime authority.

No caller, request, environment variable, profile, filesystem order, GitHub
state, or network source may alter this authority map.

## 6. Trust model and scope

### Protected assets

This boundary protects:

- exact authorizing RFC bytes;
- complete production migration-release authenticity;
- the exact authenticated V3 history;
- the stable command prerequisite;
- the exact 0004 exception;
- the prohibition on all other migration role occurrences;
- unchanged candidate bytes;
- the distinction between conformance and activation;
- the production-versus-legacy firewall; and
- the closed production semantic surface.

### In-scope mutation

Checked-in source or migration-file substitution before or during checker
execution is in scope.

The checker therefore:

- uses one fixed migration-authority source snapshot;
- obtains one authenticated `MigrationSet`;
- computes the V3 prefix from that object;
- compares the parsed literal against that object;
- classifies role occurrence from that object's authenticated source bytes;
  and
- performs no migration filesystem read after authentication.

A changed authority structure, changed V3 history, changed migration byte
sequence, changed candidate, or mismatch between the named literal and
authenticated release must refuse.

### Trusted components

Trusted components are:

- the exact checked-in checker;
- the fixed checked-in migration-authority module;
- its existing production migration loader and identity functions;
- Python's standard-library parsing, hashing, path, import-loading, and
  compilation facilities;
- the cryptographic hash implementation; and
- the operating system's file-descriptor and filesystem guarantees used by
  the production loader.

### Excluded compromise capabilities

Outside this boundary are:

- arbitrary in-process mutation after validation;
- a compromised Python interpreter or standard library;
- malicious replacement of trusted executable checker or migration-loader
  code;
- operating-system or cryptographic compromise;
- operator, repository-host, or workstation compromise; and
- database-owner or migrator compromise.

These exclusions do not excuse ordinary checked-in source drift, malformed
source, inconsistent release data, or filesystem changes detectable by the
existing loader.

## 7. State and ordering

```text
UNCHECKED_PACKAGE
  -> EXACT_PERSISTENCE_RFC_AUTHENTICATED
  -> EXACT_MIGRATION_AUTHORITY_SOURCE_SNAPSHOTTED
  -> ONE_CURRENT_TENANT_MIGRATION_SET_AUTHENTICATED
  -> EXACT_NAMED_V3_LITERAL_PARSED
  -> AUTHENTICATED_V3_MIGRATION_VERIFIED
  -> PARSED_AND_AUTHENTICATED_V3_PREFIXES_MATCHED
  -> COMMAND_CANDIDATE_PREFIX_MATCHED
  -> ROLE_CLASSIFIED_FROM_AUTHENTICATED_MIGRATION_BYTES
  -> EXISTING_FORBIDDEN_AUTHORITIES_PROVED_CLEAR
  -> CONFORMANCE_POSTURE_PASSED
```

All module-loading, parsing, authority-shape, migration-loading, and production
`MigrationSetError` failures must become:

```text
CONFORMANCE_REFUSED
```

`CONFORMANCE_POSTURE_PASSED` has no transition to migration execution,
publication, promotion, selection, command execution, routes, outputs,
historical behavior, or current truth.

## 8. Invariants

- **TCPA-001 — Exact authorizing RFC.** The 0004 exception is unavailable
  unless the fixed persistence RFC has exactly `37254` bytes and the pinned
  SHA-256.
- **TCPA-002 — One authority source snapshot.** Literal parsing and
  production-loader execution use the same fixed `migration_sets.py` source
  revision.
- **TCPA-003 — One authenticated migration snapshot.** Exactly one
  authenticated tenant `MigrationSet` supplies V3 identity, prefix
  computation, and role-classification bytes.
- **TCPA-004 — One exact migration exception.** Only authenticated filename
  `0004_temporal_governance_runtime_bundle_role.sql` may contain the role.
- **TCPA-005 — Absence remains valid.** An authentic V3 release with no 0004
  passes.
- **TCPA-006 — No ungoverned 0004.** An unlisted, extra, renamed, or otherwise
  non-authoritative 0004 is refused by complete-release authentication.
- **TCPA-007 — Every other migration remains closed.** The role in any other
  authenticated migration refuses.
- **TCPA-008 — Fixed exception authority.** Role and filename are reviewed
  constants, never caller data or a "latest migration" rule.
- **TCPA-009 — Authenticated V3 prerequisite.** The candidate equals the
  prefix computed from the authenticated `MigrationSet`.
- **TCPA-010 — Literal-to-release binding.** The parsed named V3 literal
  equals the authenticated migration's identity and computed prefix.
- **TCPA-011 — Stable history, advancing release.** The complete-set digest
  may advance without changing the authenticated V3 prefix.
- **TCPA-012 — Complete validation remains singular.** The production loader
  remains the only complete-release validator and digest authority.
- **TCPA-013 — No migration reread.** Role classification uses authenticated
  `Migration.source_bytes`; no later glob or source-file read is allowed.
- **TCPA-014 — Candidate bytes remain immutable.** Candidate, schema,
  knowledge-storage RFC, and migration 0003 do not change.
- **TCPA-015 — Ambiguity refuses.** Missing, duplicated, malformed,
  non-literal, or unexpected authority structures refuse.
- **TCPA-016 — Closed exception handling.** Production migration errors and
  module-loading failures become `TemporalCandidateError`.
- **TCPA-017 — Existing forbidden authorities remain closed.** Repository,
  legacy schema, active catalog, ActiveArtifactSet, and Capability Manifest
  rules remain unchanged.
- **TCPA-018 — SQL correctness is separate.** Allowed role text in exact 0004
  is not proof of migration correctness.
- **TCPA-019 — No lifecycle or activation inference.** Conformance success is
  not promotion, currentness, selection, execution, output, or truth.
- **TCPA-020 — Production and legacy remain separate.** No
  production-to-legacy persistence dependency is introduced.
- **TCPA-021 — Audit remains separate.** No #192 behavior or authority
  changes.
- **TCPA-022 — Zero-dependency posture remains.** The checker adds no
  third-party dependency and does not change PostgreSQL package
  initialization.
- **TCPA-023 — Read-only conformance.** The checker executes no SQL, opens no
  database connection, mutates no migration, and publishes no bundle.

## 9. Required negative cases

| Case | Required result |
| --- | --- |
| Persistence RFC missing | Refuse before exception |
| Persistence RFC wrong length | Refuse |
| Persistence RFC same length but wrong digest | Refuse |
| Migration-authority module missing, malformed, or missing required symbols | `TemporalCandidateError` refusal |
| Production loader raises `MigrationSetError` | `TemporalCandidateError` refusal |
| Authentic V3 release, missing 0004, role absent elsewhere | Pass |
| Authentic current release, exact 0004 without role | Pass this posture check |
| Authentic current release, role only in exact 0004 | Pass this posture check |
| 0004 exists but is not in the authenticated release | Refuse |
| Role occurs in another migration | Refuse |
| Caller supplies exception filename or role | No such seam may exist |
| Checker chooses newest migration as exception | Refuse the design |
| Named tenant authority assignment missing or duplicated | Refuse |
| Named V3 literal missing or duplicated | Refuse |
| Parsed V3 filename, digest, length, or applied prefix differs | Refuse |
| Authenticated migration at position/version 3 differs | Refuse |
| Named V3 literal remains exact but loader-selected release has a different V3 migration or prefix | Refuse |
| Candidate equals evolving complete-set digest rather than authenticated V3 prefix | Refuse |
| Migration 0003 is edited, renamed, removed, or reordered | Production loader refuses |
| Migration files change after authentication | Role classification remains bound to retained authenticated bytes |
| Checker performs a second migration glob or reread | Refuse the implementation design |
| Normal package import introduces a `psycopg` dependency | Refuse the implementation design |
| Role appears in repository, legacy schema, active catalog, ActiveArtifactSet, or Capability Manifest | Refuse |
| Conformance result is offered as persistence, promotion, selection, route, output, or truth authority | No effect |

A synthetic V4 test may demonstrate prefix stability but must not invent or
pin production migration-0004 SQL.

## 10. Non-goals

This contract and its future implementation do not:

- add migration 0004;
- edit `migration_sets.py` or any migration;
- change the migration runner, ledger, verifier, readiness, grants, or
  database roles;
- change the publication function;
- publish or retain a temporal RuntimeBundle;
- rewrite candidates, schemas, manifests, or digests;
- change temporal identities or carrier rows;
- change RuntimeBundle model behavior;
- add catalog membership or tenant selection;
- integrate the governed command;
- add authorization, routes, reads, outputs, or historical/WINDOW execution;
- change lifecycle decisions or currentness;
- amend ADR 0002 or frozen active contracts;
- change legacy persistence;
- add a service, registry, policy engine, plugin, or database;
- add a third-party dependency; or
- implement #192 behavior.

## 11. Smallest coherent change

### Phase A

The Phase A PR may add only:

```text
docs/rfcs/OFARM_Temporal_Candidate_Conformance_Persistence_Admission_RFC_v0_1.md
```

### Future Phase B

After Phase A merge, one separately reviewed conformance PR may:

1. add fixed persistence-RFC pins;
2. load the exact migration authority without package initialization;
3. call the existing production loader once;
4. parse the named literal from the same authority source revision;
5. bind parsed V3 identity to authenticated V3 identity and computed prefix;
6. compare the candidate with that computed prefix;
7. classify the role from authenticated migration bytes;
8. translate authority-loading failures into closed checker refusals;
9. preserve all existing catalog and activation refusals; and
10. add focused positive and negative tests.

No generalized authority framework is needed.

## 12. Elegance audit

```text
Production complete-release validators:           1
Authenticated MigrationSet objects per check:     1
Stable knowledge-prefix computations:             1
Migration filesystem scans after authentication: 0
Migration source rereads after authentication:    0
AST-extracted historical literals:                1
Exact migration exceptions:                       1
Third-party dependencies added:                   0
Dynamic registries or policy engines:             0
Database connections or SQL executions:           0
```

## 13. Pull-request boundaries

### Phase A contract PR

Allowed file:

```text
docs/rfcs/OFARM_Temporal_Candidate_Conformance_Persistence_Admission_RFC_v0_1.md
```

### Future Phase B conformance PR

Allowed files:

```text
conformance/temporal_contract_candidate_check.py
kernel/tests/test_temporal_contract_governance.py
conformance/review_baseline_test_inventory.json
```

The inventory may change only when mechanically required by a change to the
canonical collected test-node inventory, including a count or node-ID change.

Migration SQL and persistence implementation must remain separate.

## 14. Traceability

| Invariants | Future code seam | Required proof |
| --- | --- | --- |
| TCPA-001 | persistence-RFC authentication | Exact authority passes; missing, length-mismatched, and same-length digest-mismatched variants refuse |
| TCPA-002, 022 | fixed-path zero-dependency authority loading | Literal parser and loader use the same fixed authority revision without package initialization |
| TCPA-003, 012 | one call to the production loader | Exactly one authenticated `MigrationSet` is retained |
| TCPA-004–008 | role classifier over authenticated migrations | Missing 0004 passes; role only in exact 0004 passes; every other migration refuses |
| TCPA-009–011 | V3 literal and authenticated-prefix binding | Parsed literal, authenticated V3 identity, computed prefix, and candidate are equal |
| TCPA-013 | authenticated `Migration.source_bytes` scan | No second glob, migration load, or source read |
| TCPA-014 | unchanged candidate and prerequisite artifacts | Exact digests and boundary diff remain unchanged |
| TCPA-015, 016 | authority-shape parser and error translation | Missing, duplicate, malformed, substituted, and loader-error cases refuse as `TemporalCandidateError` |
| TCPA-017 | existing catalog/profile checks | Existing mutation tests remain green |
| TCPA-018 | boundary diff | No migration SQL or database behavior added |
| TCPA-019–021 | unchanged lifecycle, runtime, legacy, and audit authorities | No changed files or new imports in those boundaries |
| TCPA-023 | checker execution | No SQL, database connection, mutation, or publication seam |

## 15. Verification

Required future Phase B verification:

```text
python3 -m pytest -q kernel/tests/test_temporal_contract_governance.py
python3 -m pytest -q kernel/tests/test_migration_sets.py
python3 conformance/temporal_contract_candidate_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --name-only origin/main...HEAD
```

The final command may name only the checker, focused tests, and mechanically
required canonical inventory metadata.

The Phase A RFC PR must pass:

```text
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --name-only origin/main...HEAD
```

The final command must name only the new RFC.

The following pins were independently verified before this contract was
published:

```text
Persistence RFC bytes and digest: PASS
Governed-command candidate bytes and digest: PASS
Authenticated migration-0003 identity: PASS
Authenticated MigrationSet.prefix_digest(3): PASS
```

## 16. Provisional-design record

Not provisional.

The pre-deployment lifecycle-decision workflow remains provisional under its
own contract. The distinction between an authenticated complete migration
release and a stable historical prerequisite is not provisional.

## 17. Open decisions

None after binding the parsed literal, authenticated V3 migration, computed V3
prefix, candidate prerequisite, and role classification to one authenticated
migration snapshot.

## 18. Review disposition

- **Blockers:** any design that performs a second migration scan; permits
  another migration; compares the candidate with the evolving full-set
  digest; fails to bind the parsed literal to the authenticated release; adds
  dependencies; or crosses into persistence, runtime, legacy, output, or #192
  authority.
- **Follow-up:** after the conformance implementation merges, begin the
  separately approved production persistence Phase B boundary.
- **Preferences:** wording or naming changes that do not alter the authority
  map, invariants, negative cases, traceability, verification, or stop
  conditions.

## 19. Stop conditions

Stop and return for a new or amended contract if implementation or review
requires:

- changing the persistence-admission RFC;
- changing the exact 0004 filename;
- permitting the role in another migration;
- adding migration 0004 to the conformance PR;
- editing `deployment/postgresql/migration_sets.py` or package initialization;
- adding `psycopg` or another dependency;
- copying or reimplementing the complete migration loader or digest algorithm;
- performing a second migration glob or reread;
- changing migration 0003;
- changing candidate or schema bytes;
- weakening the parsed-literal-to-authenticated-release binding;
- changing RuntimeBundle model behavior;
- changing catalog, selection, command, authorization, route, read, output, or
  historical/WINDOW behavior;
- changing lifecycle currentness;
- opening a production-to-legacy dependency;
- implementing #192; or
- changing any file outside the future Phase B allowlist.

Approval or merge of this contract does not authorize implementation by
itself. Phase B begins only after the documentation-only RFC is merged and the
implementation remains inside its separately reviewed boundary.
