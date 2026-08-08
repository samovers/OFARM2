# OFARM2 RuntimeBundle Global Content Retention Conformance Admission — Phase A Contract v0.1

**Status:** architect-approved Phase A contract; documentation-only and without
checker, migration, database, content-retention, bundle-publication, selection,
runtime, deployment, route, output, legacy, or #192 effect

**Contract identity:**
`ofarm.runtime-bundle-global-content-retention-conformance-admission.issue176.v0.1`

**Decision identity:**
`ISSUE176-RUNTIME-BUNDLE-GLOBAL-CONTENT-RETENTION-CONFORMANCE-001`, version `1`

**Reviewed base:** `93d01c60420a055fae6a632acb7f4e5fe7f549b5`

**Phase A RFC path:**
`docs/rfcs/OFARM_RuntimeBundle_Global_Content_Retention_Conformance_Admission_RFC_v0_1.md`

**Primary ticket:** #176

**Primary trust boundary:** repository conformance authority for admitting
exactly the future migration-0009 absent/present transition without changing
the active temporal semantic surface

**Phase A pull-request boundary:** this RFC only

**Intended later conformance Phase B boundary:** one additive internal
classifier in the existing temporal candidate checker, focused tests in its
existing governance test module, and mechanical canonical test-node inventory
regeneration only when required

## 1. Problem and goal

The merged global-content-retention contract establishes a narrow future
database boundary for one publisher-custody function. It also requires the
temporal candidate checker to admit migration 0009 before that database work
may begin.

Current `main` is an exact version-8 tenant migration release. The checker
authenticates the selection-storage transition through version 8 and returns
`CONFORMANT_CLASSIFIED`. Its selection-storage implementation currently binds
the complete migration count to three decisions: the outer V7/V8 count gate,
presence of the version-8 migration, and equality between the complete
migration-set digest and `prefix_digest(8)`. Appending an unrelated version 9
therefore first refuses at the outer count gate and, if only that gate were
relaxed, would later make the already complete version-8 pair look incomplete
and then fail the complete-digest comparison even though version 8 and its
adapter remain exact.

The required change is not a new database authority and not temporal
activation. It is this closed conformance rule:

> preserve the exact version-8 selection-storage cut as an authenticated
> prefix, then accept either exact version 8 with migration 0009 absent or one
> exact contiguous version 9 whose final filename and trace markers identify
> the governed global-content-retention migration.

Within the subordinate retention-classifier domain, the checker must continue
returning the existing selection-storage result `CONFORMANT_CLASSIFIED`. The
global-content-retention migration state is an internal guard only. It creates
no new public conformance vocabulary, registry, runtime input, or lifecycle
state. Exact V7 remains outside that domain and retains its inherited
`CONFORMANT_ABSENT` result.

## 2. Decision

After this exact RFC is approved and merged, a separately requested
conformance Phase B may amend the existing checker so that one invocation:

1. authenticates this complete merged conformance RFC as its self-authority;
2. authenticates the complete merged parent global-content-retention Phase A
   RFC;
3. authenticates the already accepted selection-storage and Python-source
   snapshot authorities;
4. loads one authoritative tenant migration snapshot and one public Python
   source snapshot;
5. applies the inherited selection-storage classifier first;
6. preserves exact V7 `CONFORMANT_ABSENT` without selecting the retention
   classifier;
7. only after selection storage is exact and `CONFORMANT_CLASSIFIED`, proves
   the immutable version-8 prefix and classifies one of exactly two internal
   global-content-retention states;
8. preserves all existing active-surface and import-closure checks; and
9. returns the unchanged inherited public selection-storage result.

The two internal states are:

```text
GLOBAL_CONTENT_RETENTION_MIGRATION_ABSENT
GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED
```

These names are checker-internal evidence. They are not schema values,
RuntimeBundle components, database states, API results, lifecycle states, or
output fields.

### 2.1 Lawful repository states and classifier domain

The inherited selection-storage classifier remains the first state decision.
The new retention classifier is subordinate to it and has no domain when the
selection result is `CONFORMANT_ABSENT`:

```text
AUTHENTICATED AUTHORITIES
  + EXACT V7 COMPLETE RELEASE
  + EXACT V7 SELECTION PATHS ABSENT
    -> DO NOT INVOKE THE RETENTION CLASSIFIER
    -> PUBLIC RESULT REMAINS CONFORMANT_ABSENT
```

Within the subordinate retention-classifier domain, the parent contract's
exact two absent/present states are:

```text
AUTHENTICATED AUTHORITIES
  + EXACT V8 PREFIX AND COMPLETE V8 RELEASE
  + EXACT V8 SELECTION PAIR CLASSIFIED
  + MIGRATION 0009 ABSENT
    -> GLOBAL_CONTENT_RETENTION_MIGRATION_ABSENT
    -> PUBLIC RESULT REMAINS CONFORMANT_CLASSIFIED

AUTHENTICATED AUTHORITIES
  + EXACT V8 PREFIX
  + EXACT CONTIGUOUS COMPLETE V9 RELEASE
  + EXACT V8 SELECTION PAIR CLASSIFIED
  + EXACT MIGRATION 0009 PRESENT AND CLASSIFIED
    -> GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED
    -> PUBLIC RESULT REMAINS CONFORMANT_CLASSIFIED

ANY OTHER STATE
    -> REFUSED
```

Exact V7 is an inherited complete-checker state, not a third retention state.
Version 10 or later, a gap, a reorder, a second version-9 file, an untracked
migration, or a self-consistent but non-exact version-8 prefix is neither an
inherited state nor a third lawful retention state.

### 2.2 Exact version-8 cut

The stable cut is:

- service: `ofarm.tenant-postgresql.v1`;
- versions: `0001` through `0008`, contiguous;
- version-8 filename:
  `0008_tenant_command_runtime_bundle_selection.sql`;
- version-8 source: 37,933 bytes,
  `sha256:635e476fb4eb93073ed353397a977ea887c42e1be11b42f9a4782a76f88ab765`;
- version-3 prefix:
  `sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0`;
- version-8 prefix and complete version-8 digest:
  `sha256:7231c869066c56f7c642460d33391bab00456daecdb04530b34da7210e8e8a54`.

The fixed version-8 prefix authenticates all first-eight filenames, source
bytes, lengths, ordering, and prefix framing through the authoritative
migration-set loader. The new classifier must recompute and compare the prefix;
it must not trust a copied digest literal alone.

### 2.3 Exact version-9 migration identity

In the classified state, version 9 must be the final and only additional
migration, with exact filename:

```text
0009_runtime_bundle_global_content_retention.sql
```

The authoritative migration-set loader must authenticate the checked-in
version-9 bytes, byte length, source SHA-256, applied prefix digest, complete
set digest, exact directory contents, and contiguous ordering. The classifier
then requires:

- `prefix_digest(8)` equals the fixed version-8 digest;
- `prefix_digest(9)` equals the complete migration-set digest;
- the complete digest differs from the version-8 digest; and
- the exact final migration carries the required trace markers in section 3.

This contract intentionally does not hard-code a future version-9 source
digest, byte length, prefix digest, catalog fingerprint, or verifier digest.
Those are mechanical outputs of the separately reviewed database Phase B.
The conformance classifier authenticates their internally consistent,
authoritative repository representation; the database contract, migration
review, and database tests own SQL correctness.

### 2.4 Selection-storage compatibility

The existing selection-storage law remains controlling for version 8 and its
adapter. The smallest lawful compatibility amendment is:

- preserve exact V7 `CONFORMANT_ABSENT` and do not invoke the retention
  classifier in that inherited state;
- relax the outer migration-count gate only enough to preserve exact V7 and
  admit exact V8 or exact contiguous V9 evidence;
- determine presence of the selection migration from exact version 8, not
  from equality between the total migration count and `8`;
- allow one later version 9 only after the first-eight prefix remains exact;
- in exact V8, continue requiring the complete migration-set digest to equal
  the fixed `prefix_digest(8)`;
- in exact V9, stop comparing the complete migration-set digest to
  `prefix_digest(8)`; keep the selection validator bound to the fixed
  version-8 prefix, then require the subordinate retention classifier to prove
  that the complete digest equals `prefix_digest(9)`, equals
  `prefix_digest(len(migrations))`, and differs from the version-8 digest;
- keep scanning every migration, including version 9, for misplaced
  selection-storage markers;
- keep the exact adapter identity, source snapshot, initializer prohibition,
  and production/legacy import-closure rules;
- keep both inherited selection-storage internal states,
  `SELECTION_STORAGE_CONFORMANT_ABSENT` and
  `SELECTION_STORAGE_CONFORMANT_CLASSIFIED`; and
- keep the command-line pass lines exactly
  `TEMPORAL CANDIDATE PASS: CONFORMANT_ABSENT` for exact V7 and
  `TEMPORAL CANDIDATE PASS: CONFORMANT_CLASSIFIED` for exact V8 or V9.

No version-8 marker, binding, adapter, selection invariant, or output meaning
may be relaxed. Version 9 is a suffix outside the selection pair, not a new
selection component.

## 3. Closed marker law

### 3.1 Required version-9 trace markers

The exact migration 0009 must contain both case-sensitive byte strings:

```text
ofarm.runtime-bundle-global-content-retention-admission.issue176.v0.1
ofarm.retain_runtime_content
```

The first marker binds the migration to the merged design authority. The
second identifies the governed database seam. Their presence classifies the
file; it does not validate the function body or authorize execution.

Neither required marker may occur in authenticated migrations 0001 through
0008. No other authenticated migration may carry either marker.

### 3.2 Forbidden migration-0009 markers

The checker must refuse migration 0009 if its exact bytes contain any member
of the closed, case-sensitive values enumerated below. These values are the
contract vocabulary; live implementation collections are not the authority.

1. Any of these exact package paths:
   - `contracts/candidates/temporal_coordinate/OFARM_TemporalCoordinate_schema_v0_1.json`;
   - `contracts/candidates/temporal_coordinate/OFARM_TemporalCarrierMatrix_schema_v0_1.json`;
   - `contracts/candidates/temporal_coordinate/OFARM_TemporalCarrierMatrix_ADR0002_candidate_v0_1.json`;
   - `contracts/candidates/temporal_carrier_selection/OFARM_TemporalCarrierSelectionBinding_schema_v0_1.json`;
   - `contracts/candidates/temporal_carrier_selection/OFARM_InterventionValidTimeCarrierSelection_candidate_v0_1.json`;
   - `contracts/candidates/temporal_governed_command/OFARM_TemporalGovernedCommandBinding_schema_v0_1.json`;
   - `contracts/candidates/temporal_governed_command/OFARM_OperationClaimDraftTemporalCommand_candidate_v0_1.json`;
   - `contracts/candidates/temporal_runtime_bundle_carrier/OFARM_TemporalGovernanceRuntimeBundleCarrierBinding_schema_v0_1.json`;
   - `contracts/candidates/temporal_runtime_bundle_carrier/OFARM_TemporalGovernanceRuntimeBundleCarrier_candidate_v0_1.json`;
   - `contracts/candidates/temporal_runtime_bundle_selection/OFARM_TenantCommandRuntimeBundleSelectionBinding_schema_v0_1.json`;
   - `contracts/candidates/temporal_runtime_bundle_selection/OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json`;
   - `contracts/candidates/temporal_governance_promotion/OFARM_TemporalGovernancePromotionBinding_schema_v0_1.json`; and
   - `contracts/candidates/temporal_governance_promotion/OFARM_TemporalGovernancePromotion_candidate_v0_1.json`.
2. any of these temporal identities or role values:
   - `ofarm.temporal-coordinate.v0.1`;
   - `ofarm.temporal-carrier-matrix.adr0002.v0.1`;
   - `ofarm.temporal-carrier-selection.intervention.v0.1`;
   - `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1`;
   - `ofarm.temporal-governance-runtime-bundle-carrier.v0.1`;
   - `TEMPORAL_GOVERNANCE_ARTIFACT`;
   - `ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1`;
   - `ofarm.temporal-governance-promotion.issue176-foundation.v0.1`;
3. Any of these exact carrier-row identities or discriminators:
   - `STRUCTURE_EVENT`;
   - `OBSERVATION_EVENT`;
   - `OCCURRENCE_EVENT`;
   - `INTERVENTION_EVENT`;
   - `MATERIAL_EVENT`;
   - `EVIDENCE_EVENT`;
   - `GOVERNANCE_EVENT`;
   - `ASSERTION_RECORD`;
   - `ACCEPTED_EVENT_CONSEQUENCE`;
   - `REVIEW_AND_GOVERNANCE_RECORDS`;
   - `POINT_OBSERVATION_PAYLOADS`;
   - `PARTIAL_EXTENT_TEMPORAL_APPLICABILITY`;
   - `INTERVAL_STATE_OR_OBSERVATION`;
   - `PENDING_OR_DISPUTED_ANNEX_ENTRY`;
   - `EVIDENCE_SUFFICIENCY_CASE`; and
   - `OPERATION_CLAIM`.
4. the existing selection-storage binding digest
   `sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f`;
5. any of these selection, command, route, output, legacy, or #192 markers:
   - `0008_tenant_command_runtime_bundle_selection.sql`;
   - `deployment/postgresql/tenant_command_runtime_bundle_selection.py`;
   - `tenant_command_runtime_bundle_selection`;
   - `activate_tenant_command_runtime_bundle_selection`;
   - `COMMIT_OPERATION_CLAIM_DRAFT`;
   - `kernel.api`;
   - `kernel.application_runtime`;
   - `kernel.profiles.si_ffs.outputs`;
   - `contracts/kernel/OFARM_RuntimeProblem_schema_v0_1.json`;
   - `kernel.legacy_m1.api`;
   - `#192`;
   - `ofarm.security-audit-postgresql.v1`; and
   - `security_audit/`.

The checker must use these exact strings, not broad words such as `route`,
`output`, `audit`, `current`, `window`, or `temporal`. Broad word matching
would create accidental policy and false authority.

Conformance Phase B must copy these exact ordered values into one private,
immutable GCRC marker constant and test exact equality with this frozen
v0.1 vocabulary. It must not permanently iterate whichever values happen to
exist in `CANDIDATE_RELATIVE_PATHS`, `CARRIER_ROW_IDS`, or successor
collections. Changing, adding, removing, or substituting a value is a contract
change. Caller data, environment variables, newest files, documentation
searches, runtime discovery, or unrelated checker edits may not change the
set.

### 3.3 Python-source isolation

The two required trace markers must be absent from every retained Python
source unit except:

- `conformance/temporal_contract_candidate_check.py`; and
- paths below `kernel/tests/`.

The existing authenticated Python-source snapshot supplies the source bytes,
module identities, import graph, and production/legacy reachability. The
checker must not rescan the filesystem through a private alternative.

The checker and tests must remain outside both production and legacy import
closures. No Python publisher, startup hook, service adapter, package
initializer export, or runtime call site is admitted by this exception.

## 4. Exact authority map

| Authority | Exact reviewed identity | Authority retained |
| --- | --- | --- |
| Complete merged self-authority | `docs/rfcs/OFARM_RuntimeBundle_Global_Content_Retention_Conformance_Admission_RFC_v0_1.md`; `ofarm.runtime-bundle-global-content-retention-conformance-admission.issue176.v0.1`; complete merged byte length and SHA-256 established only after the approval record is published and the RFC merges | exact subordinate classifier composition, internal states, frozen marker vocabulary, shared-evidence rule, prefix/full-digest split, implementation envelope, and stop conditions defined here |
| Parent global-content-retention contract | `ofarm.runtime-bundle-global-content-retention-admission.issue176.v0.1`, 38,116 bytes, `sha256:aa5de04c08390e1439d59f39c4b6f5608e8b43b320fec531721d9c53b936873a` | function contract, publisher custody, future database allowlist, inertness, and stop conditions |
| Selection-storage conformance authority | `ofarm.temporal-candidate-conformance-selection-storage-admission.issue176.v0.1`, 62,540 bytes, `sha256:716a45927846d068f595f81288b8d29ecc07891bcaf848e0284eb91ece4abc8d` | version-8 selection pair, marker law, and conformance states |
| Selection-storage source-snapshot amendment | `ofarm.temporal-candidate-conformance-selection-storage-source-snapshot-amendment.issue176.v0.2`, 93,049 bytes, `sha256:820516d40956b6ea2a158413aea32a305aa078f20816ae35b257eb28491e5867` | public Python-source evidence and closed conformance implementation posture |
| Python-source architecture | `ofarm.architecture-python-source-snapshot-admission.issue176.v0.1`, 82,758 bytes, `sha256:6e4307077525f2bbb48992fa4c652ab75d279875063bd715cf21dc1f1d3216d5` | production/legacy source and reachability evidence |
| Current temporal checker at reviewed base | `conformance/temporal_contract_candidate_check.py`, 164,601 bytes, `sha256:2cb91219b59f6313b54ea9e33e506e2bf05987c778f8acefb50d92631d5714a8` | current classifier composition and public pass output |
| Current tenant migration-set source at reviewed base | `deployment/postgresql/migration_sets.py`, 25,888 bytes, `sha256:20e69aa394b76e2a7b3479c8d31a1fc6062a6865186b2eaae0cff95d0415f8dd` | authoritative directory, bytes, lengths, prefixes, and complete-set identity |
| Exact version-8 migration | `kernel/migrations/0008_tenant_command_runtime_bundle_selection.sql`, 37,933 bytes, `sha256:635e476fb4eb93073ed353397a977ea887c42e1be11b42f9a4782a76f88ab765` | final member of the immutable version-8 prefix |

The first five rows are versioned authorities that future conformance Phase B
must authenticate. The self-authority row is not permission to guess its final
bytes: after the truthful approval record is published and this RFC merges,
Phase B must pin its complete merged path, contract identity, byte length, and
SHA-256. The current checker and migration-set source identities are
reviewed-base evidence, not permanent pins: those two files are expected to
change in their separately approved implementation boundaries. The fixed
version-8 prefix, parent RFC identity, and inherited conformance authorities
remain permanent inputs to this classifier version.

Authority ownership is:

- this RFC owns only the new absent/classified conformance rule;
- the temporal candidate checker owns enforcement after Phase B;
- the authoritative migration-set loader owns exact repository migration
  bytes, directory membership, order, lengths, source digests, and prefixes;
- the existing selection-storage contracts own version-8 selection meaning;
- the public Python-source snapshot owns source and import-closure evidence;
- the parent retention contract owns future SQL behavior and database custody;
- migration 0009 and database tests will own the actual SQL implementation;
- the active RuntimeBundle catalog, ActiveArtifactSet, Capability Manifest,
  profiles, application runtime, worker runtime, routes, and outputs retain
  their current closed authorities; and
- #192 retains sole authority over audit-runtime behavior.

No caller, profile, environment registry, untracked file, legacy repository,
or database target may substitute for these authorities.

## 5. Validation order and evidence flow

The supported checker path must execute in this order:

```text
FIXED PACKAGE ROOT
  -> AUTHENTICATE COMPLETE MERGED SELF-AUTHORITY
  -> AUTHENTICATE COMPLETE MERGED PARENT RFC
  -> AUTHENTICATE EXISTING SELECTION/SNAPSHOT AUTHORITIES
  -> LOAD ONE AUTHORITATIVE TENANT MIGRATION SNAPSHOT
  -> BUILD ONE PUBLIC PYTHON SOURCE SNAPSHOT
  -> APPLY INHERITED SELECTION-STORAGE CLASSIFIER
       -> EXACT V7 / CONFORMANT_ABSENT
            -> DO NOT SELECT RETENTION CLASSIFIER
       -> EXACT V8 PAIR / CONFORMANT_CLASSIFIED
            -> PROVE FIXED V8 PREFIX
            -> CLASSIFY RETENTION MIGRATION ABSENT OR CLASSIFIED
            -> PROVE REQUIRED/FORBIDDEN MARKER OWNERSHIP
  -> PRESERVE ACTIVE-SURFACE AND IMPORT-CLOSURE CHECKS
  -> RUN EXISTING CANDIDATE AND SEMANTIC VALIDATION
  -> RETURN INHERITED CONFORMANT_ABSENT OR CONFORMANT_CLASSIFIED RESULT
```

Self-authority authentication occurs before the parent or any inherited
authority is trusted. A missing, symlinked, unreadable, length-mismatched,
digest-mismatched, or identity-mismatched complete merged self-authority
refuses before parent authentication or state classification. The same
failure classes for the parent RFC refuse before state classification.

The same migration snapshot and Python snapshot must be shared with the
selection-storage and new retention validators. A second loader, private
filesystem scan, imported production module, environment-selected root, or
caller-supplied snapshot would create competing evidence and is forbidden.

## 6. Trust model

### Protected assets

- This complete merged RFC as the exact authority for its new exception.
- The exact merged parent design authority.
- The immutable version-3 and version-8 migration prefixes.
- The inherited exact-V7 absent result and the exact version-8 selection pair
  and classified result.
- One closed migration-0009 filename and marker exception.
- The unchanged public checker output.
- The absence of temporal activation, Python publication code, runtime imports,
  route/output behavior, legacy coupling, and #192 behavior.

### Trusted components

- Checked-in exact RFC bytes after explicit approval.
- The authoritative migration-set loader and its fixed package root.
- The existing public Python-source snapshot interface.
- The temporal checker after exact-head review and tests.
- SHA-256 and the migration-set framing already governed by the database
  architecture.

### Untrusted inputs and claims

- Filenames or bytes outside the authoritative migration set.
- Caller-provided paths, state names, digests, markers, roots, or snapshots.
- Environment variables, current working directory, import side effects,
  newest-file discovery, profiles, runtime registries, and documentation
  searches.
- A passing internal state presented as database correctness, publication,
  selection, activation, deployment, or current truth.

### Excluded compromise capabilities

Compromise of the repository host, operating system, Python interpreter,
cryptographic hash, accepted migration-set loader, accepted source-snapshot
builder, or reviewer environment is outside this boundary. Ordinary source
drift, path substitution, incomplete implementation, marker smuggling, and
cross-boundary edits remain in scope and fail closed.

## 7. Invariants and acceptance criteria

- **GCRC-001 — Self and parent first.** This complete merged RFC is
  authenticated by exact path, contract identity, byte length, and SHA-256
  before the parent or the migration-0009 exception is considered. The exact
  merged parent RFC is then authenticated before state classification.
- **GCRC-002 — Subordinate two-state domain.** Exact V7 remains the inherited
  `CONFORMANT_ABSENT` complete-checker state and does not select this
  classifier. Only exact V8/0009-absent and exact V9/0009-classified pass the
  subordinate retention classifier.
- **GCRC-003 — Stable prefixes.** Version-3 and version-8 prefix digests remain
  exact in both states.
- **GCRC-004 — Exact suffix identity.** The classified state contains exactly
  one final version 9 with the exact governed filename.
- **GCRC-005 — Authoritative bytes.** Migration state comes only from the
  authoritative migration-set loader over the fixed package root.
- **GCRC-006 — Closed trace ownership.** Both required markers occur in exact
  migration 0009 and in no earlier or alternative migration.
- **GCRC-007 — Closed forbidden vocabulary.** Exact migration 0009 contains no
  marker from the frozen, enumerated section-3.2 vocabulary; live checker
  collections cannot change that vocabulary.
- **GCRC-008 — Selection meaning preserved.** Version-8 selection storage and
  its adapter remain the exact classified pair; version 9 is not a selection
  component.
- **GCRC-009 — Public output preserved.** Successful supported invocation
  still prints only the inherited result: exact V7 prints
  `TEMPORAL CANDIDATE PASS: CONFORMANT_ABSENT`; exact V8 or V9 prints
  `TEMPORAL CANDIDATE PASS: CONFORMANT_CLASSIFIED`. No retention state is
  public.
- **GCRC-010 — Shared evidence.** Selection and retention validation share one
  authenticated migration snapshot and one public Python-source snapshot.
- **GCRC-011 — No Python publisher.** Required retention markers enter no
  production or legacy Python source or import closure.
- **GCRC-012 — Active surface closed.** Candidate artifacts remain absent from
  the active catalog, ActiveArtifactSet, Capability Manifest, profiles,
  routes, and production/legacy runtime closures.
- **GCRC-013 — No SQL semantic duplication.** The checker does not parse or
  judge function body, ACL, transaction, replay, or structural SQL correctness.
- **GCRC-014 — Classification only.** A pass creates no migration, function,
  content row, bundle, selection, command authority, route, output, or truth.
- **GCRC-015 — Production/legacy firewall.** No production source imports or
  consults legacy-M1 persistence or semantics.
- **GCRC-016 — Audit separation.** No #192 marker, dependency, receipt, event,
  delivery, or failure behavior is admitted.
- **GCRC-017 — Closed implementation envelope.** Conformance Phase B changes
  only the paths in section 10.2.
- **GCRC-018 — Fail closed.** Ambiguity, malformed evidence, unrecognized state,
  or incomplete classification raises one conformance refusal and never falls
  through to a pass.

## 8. Required negative cases

| Invariant | Counterexample | Required result |
| --- | --- | --- |
| GCRC-001 | Complete merged self-authority is absent, symlinked, unreadable, wrong length, wrong digest, or lacks the exact contract identity | refuse before parent authentication or migration classification |
| GCRC-001 | Parent RFC is absent, symlinked, unreadable, wrong length, wrong digest, or lacks the exact contract identity | refuse after self-authentication and before migration classification |
| GCRC-002 | Exact V7 complete invocation | pass inherited `CONFORMANT_ABSENT`; retention classifier is not selected |
| GCRC-002 | Migration count is not 7, 8, or 9, or V7 is not the exact inherited absent state | refuse; no third retention state |
| GCRC-003 | Any first-eight migration, filename, byte, length, order, or prefix differs while literals are updated self-consistently | fixed version-8 prefix comparison refuses |
| GCRC-004 | Version 9 has another filename, is not final, is duplicated, or is accompanied by an untracked migration file | authoritative loader or exact suffix check refuses |
| GCRC-005 | Caller supplies a migration set, path, digest, or state | no supported input accepts it |
| GCRC-006 | One required marker is missing from 0009, or either marker occurs in 0001–0008 | refuse |
| GCRC-007 | Exact 0009 contains any frozen forbidden marker, or implementation derives the vocabulary from a live mutable collection | refuse or source/equality test refuses |
| GCRC-008 | Appended 0009 makes version-8 selection appear absent, compares the complete V9 digest to `prefix_digest(8)`, or changes binding/adapter law | focused compatibility tests refuse |
| GCRC-009 | Exact V7 does not retain its absent result, or the checker prints an internal retention state or a new compound public state | exact V7/V8/V9 stdout tests refuse |
| GCRC-010 | Implementation builds a second snapshot, privately rescans source, imports migration authority normally, or uses environment-selected evidence | source/evidence tests refuse |
| GCRC-011 | A Python publisher, startup hook, service, initializer export, production source, or legacy source contains a required retention marker | source snapshot and closure checks refuse |
| GCRC-012 | Candidate path or identity enters an active registry, profile, route, or import closure | existing candidate and architecture checks refuse |
| GCRC-013 | Checker attempts to validate SQL body, grants, function properties, or runtime behavior | boundary and source review refuse |
| GCRC-014 | A pass is treated as authority to implement or execute migration 0009, retain bytes, publish a bundle, select a tenant bundle, or run a command | invalid claim with no effect |
| GCRC-015 | Checker or new code imports legacy persistence | architecture conformance refuses |
| GCRC-016 | Implementation changes or depends on #192 | changed-path boundary refuses |
| GCRC-017 | A fourth implementation path changes, or inventory changes without a canonical node-ID change | path-envelope verification refuses |
| GCRC-018 | Marker decoding, source read, AST evidence, prefix computation, or state composition is ambiguous or crashes | one fail-closed conformance error; no pass |

Tests must cover the inherited exact-V7 state, both lawful retention states,
and every refusal family above. Exact-V7 evidence must prove the retention
helper is not selected. Mutation tests may use in-memory migration and source
snapshots or disposable temporary files only. They must not create migration
0009 in the checked-in tree or run SQL against PostgreSQL.

## 9. Non-goals

Neither this Phase A contract nor its later conformance Phase B will:

- create, edit, or execute migration 0009;
- implement `ofarm.retain_runtime_content` or validate its SQL body;
- change `deployment/postgresql/migration_sets.py`, catalog identity,
  provisioning, readiness, migration runner, or any database test;
- hard-code speculative version-9 source, prefix, catalog, or verifier digests;
- retain content, publish a RuntimeBundle, choose source bytes, choose a tenant,
  or create a tenant selection;
- change the selection-storage binding, adapter, function, database state, or
  command-required component closure;
- add a Python publisher, startup integration, service, package export,
  registry, profile, or environment switch;
- change the public checker result or add a conformance schema;
- activate a temporal candidate, active catalog row, RuntimeBundle component,
  profile, route, command, read, historical view, WINDOW behavior,
  materialization, output, or current/default claim;
- deploy, upgrade, reconcile, or inspect an existing database;
- import or amend legacy-M1 behavior; or
- implement or change #192.

## 10. Smallest coherent change

### 10.1 Phase A

The current Phase A draft changes only this RFC. It adds no implementation
authority and changes no checker or repository classification.

### 10.2 Later conformance Phase B

The exact implementation allowlist is:

| Exact path | Permitted reason |
| --- | --- |
| `conformance/temporal_contract_candidate_check.py` | Authenticate this merged RFC, preserve the exact V8 selection cut, and enforce the internal V8-absent/V9-classified retention state and marker law. |
| `kernel/tests/test_temporal_contract_governance.py` | Add focused lawful-state, refusal, compatibility, output-preservation, evidence-source, and isolation tests. |
| `conformance/review_baseline_test_inventory.json` | Mechanical regeneration only when required by a change to the canonical collected test-node inventory, including a count or node-ID change. |

No other path is permitted. In particular, Phase B may not change this RFC,
the parent RFC, an earlier conformance authority, a migration, migration-set
authority, catalog identity, database code or test, RuntimeBundle model,
candidate artifact, active registry, application or worker runtime, route,
output, legacy file, or #192 file.

The implementation should add one small internal classifier and reuse the
already loaded authorities. A second checker, plugin, schema, manifest,
service, registry, or generalized migration-policy engine is not justified.

## 11. Verification and traceability

### 11.1 Phase A verification

Phase A must prove:

- only this RFC changed;
- every exact authority pin matches reviewed `main`;
- the inherited V7 state, the two subordinate retention states, validation
  order, frozen marker sets, selection compatibility, authority map,
  invariants, negative cases, non-goals, allowlist, and stop conditions are
  decision complete;
- no implementation, migration, database, runtime, route, output, legacy, or
  #192 path changed;
- `git diff --check` passes; and
- `python3 conformance/ofarm_pkg_contract_check.py` passes under the
  repository-supported CPython profile.

### 11.2 Future Phase B traceability

| Invariants | Future owning seam | Minimum evidence |
| --- | --- | --- |
| GCRC-001 | complete merged self-authority and exact parent-RFC constants and authenticators | self and parent missing, symlink, unreadable, length, digest, and identity mutation tests; self must refuse before parent |
| GCRC-002–005 | subordinate internal retention classifier over authenticated migration snapshot | exact V7 passes absent without selecting the helper; exact V8 and synthetic exact V9 pass; count, filename, order, prefix, full-digest, and caller-input refusals |
| GCRC-006–007 | closed required markers and one private immutable forbidden-marker tuple | exact equality with the frozen RFC vocabulary; missing, moved, duplicated-location, and every forbidden-marker mutation test |
| GCRC-008–009 | selection-storage compatibility and unchanged entrypoint | exact V7 preserves absent output; V8 and V9 yield classified output; V9 authenticates fixed prefix 8 and complete prefix 9 separately |
| GCRC-010–012 | public source snapshot, import closures, and existing active-surface checks | one-builder evidence, private-source prohibitions, production/legacy marker injection, and active-authority mutation tests |
| GCRC-013–016 | boundary review and existing package/architecture composition | source inspection, no database imports, no runtime paths, package and architecture gates |
| GCRC-017–018 | exact path checks and fail-closed errors | name-only diff, inventory comparison, malformed-evidence and crash-to-refusal tests |

Minimum future conformance Phase B commands are:

```text
python3 -m pytest -q kernel/tests/test_temporal_contract_governance.py
python3 conformance/temporal_contract_candidate_check.py
python3 conformance/rewrite_architecture_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

The repository-supported interpreter, complete hosted conformance baseline,
amd64 and arm64 native verification, canonical native index, and exact-head
review remain required. Passing evidence is classification only.

## 12. Elegance audit

- New public state values: zero.
- New schemas, manifests, services, registries, roles, or credentials: zero.
- New source snapshots or migration loaders: zero.
- New production Python modules: zero.
- New runtime or legacy imports: zero.
- Inherited exact-V7 behavior changed: no; the retention classifier is not
  selected in `CONFORMANT_ABSENT`.
- Lawful retention states: exactly V8/absent and V9/classified inside the
  subordinate classifier domain.
- Existing selection state changed: no.
- Exact implementation files: two, plus conditional mechanical inventory.

The design keeps migration semantics with the database contract and uses
conformance only to authenticate the narrow repository exception it owns.

## 13. Provisional posture

The design is not a temporary semantic compromise. The AI-assisted approval
evidence used before deployment is provisional under the repository workflow.
Before deployment, independently human-controlled and independently
verifiable approval or signing must replace that workflow.

## 14. Open decisions and review disposition

### Open decisions

None inside this trust boundary.

Future version-9 byte length, source digest, prefix/full-set digest, catalog
fingerprint, and verifier digest are deliberately mechanical database Phase B
outputs. Choosing them in this contract would be speculative and would combine
conformance with database authority.

This RFC's complete merged byte length and SHA-256 are likewise mechanical
publication outputs, not an open semantic decision. They are established only
after the truthful approval record is published and the RFC merges, and then
become mandatory self-authority inputs to conformance Phase B.

### Review disposition

- **Blockers addressed in this revision:** preserve inherited V7 composition;
  freeze the exact forbidden-marker vocabulary; authorize separate fixed
  V8-prefix versus complete-V9-digest authentication; and require complete
  merged self-authority before the parent or exception, with the opening
  output statement confined to the subordinate classifier domain. Independent
  exact-head re-review remains required before a replacement decision card.
- **Follow-ups:** after this Phase A merges, separately request the closed
  conformance Phase B; only after that implementation merges may database
  Phase B for migration 0009 be requested.
- **Preferences:** none recorded.

## 15. Stop conditions

Stop before conformance Phase B if:

1. this exact RFC has not received explicit architect approval and merged, or
   its complete merged path, contract identity, byte length, and SHA-256
   cannot be established and authenticated;
2. current `main` is not the exact lawful version-8/0009-absent state;
3. the merged parent RFC cannot be authenticated at its exact identity;
4. the existing selection-storage or Python-source snapshot authority differs;
5. implementation needs a path outside section 10.2;
6. selection-storage meaning, binding, adapter authority, or public result must
   change rather than merely tolerate one authenticated suffix migration;
7. a second migration loader, source snapshot, filesystem scan, schema,
   manifest, service, registry, or plugin is required;
8. a future version-9 digest must be guessed or pinned before database Phase B;
9. SQL body, function, ACL, transaction, replay, structural verifier, or
   database behavior must be implemented or interpreted;
10. migration 0009, migration-set authority, catalog identity, provisioning,
    readiness, migration runner, or database tests must change;
11. a Python publisher, startup hook, package export, application/worker path,
    route, read, output, profile, or environment switch is required;
12. an active temporal artifact, RuntimeBundle component, selection,
    current/default state, historical view, or WINDOW behavior must change;
13. production code must import legacy-M1 authority; or
14. #192 behavior or authority must change.

If the checker cannot preserve the exact existing public
`CONFORMANT_ABSENT` result for V7 and `CONFORMANT_CLASSIFIED` result for V8 or
V9 while admitting only the fixed version-9 suffix, stop. A public state-model
redesign is a separate trust boundary.

Conformance Phase B stops after its exact implementation merges. It does not
create migration 0009 or resume database work automatically.

## Appendix A — Compact approval evidence

This appendix is provisional, AI-attested evidence of the task user's
decision. The user message is the authority; this appendix, repository
credentials, reviews, checks, and merge metadata are not substitutes for it.

- decision:
  `ISSUE176-RUNTIME-BUNDLE-GLOBAL-CONTENT-RETENTION-CONFORMANCE-001`,
  version `1`;
- Codex task: `019fa821-93c9-7ef1-8c94-1c0e92ea46b9`;
- complete live card: assistant-authored `item-4396` in turn
  `019fe1a4-faa9-71c1-8a3c-605924f3a975`;
- approval: later user-authored `item-4397` in turn
  `019fe1a6-91ca-7ed1-8082-fceb23cef56e`;
- exact approval sentence:
  `I approve OFARM2 decision ISSUE176-RUNTIME-BUNDLE-GLOBAL-CONTENT-RETENTION-CONFORMANCE-001 version 1.`;
- observed ordering: `item-4396` preceded `item-4397` in the same task;
- named Phase A PR: `https://github.com/samovers/OFARM2/pull/295`;
- permitted effect: record approval and merge only this documentation Phase A
  contract so its final merged self-authority may be established and a
  separate conformance Phase B may later be requested; and
- limitation: no checker implementation, migration 0009, SQL function,
  database storage, retained content, RuntimeBundle composition or
  publication, tenant selection, runtime activation, route, command, read,
  historical or window behavior, output, deployment, legacy, or #192 effect.
  This provisional workflow must be replaced by independently human-controlled
  and independently verifiable approval or signing before deployment.

No later cancellation, replacement card, or stop instruction was present when
this approval evidence was recorded.
