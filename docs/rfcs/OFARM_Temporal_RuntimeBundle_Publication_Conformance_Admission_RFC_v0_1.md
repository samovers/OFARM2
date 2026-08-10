# OFARM2 Temporal RuntimeBundle Publication Conformance Admission — Phase A Contract v0.1

**Status:** proposed Phase A design; documentation-only, unapproved, and
without checker, adapter, database, RuntimeBundle, selection, runtime,
deployment, route, output, legacy, or #192 effect. Approval state is owned by
the active same-task decision workflow, not by this status line.

**Issue:** #176

**Contract identity:**
`ofarm.temporal-runtime-bundle-publication-conformance-admission.issue176.v0.1`

**Reviewed base:** `4e7aa838482b3b8525866185ba449e8766f835f2`

**Parent contract:**
`ofarm.temporal-runtime-bundle-catalog-publication-admission.issue176.v0.1`

**Primary trust boundary:** repository conformance classification of exactly
one future isolated temporal RuntimeBundle publication adapter

**Phase A pull-request boundary:** this RFC only

**Intended later conformance Phase B boundary:** one private classifier in the
existing temporal candidate checker, focused tests in its existing governance
test module, and canonical test-node inventory regeneration only when
mechanically required

## 1. Problem and goal

The merged parent contract chooses the complete sixteen-component temporal
command RuntimeBundle and defines one future isolated publication adapter. It
requires conformance to admit that adapter before the adapter may exist.

Current `main` correctly refuses a second production Python source containing
the tenant command-selection binding identity or digest. The only allowed
production Python owner of that exact pair is currently:

```text
deployment/postgresql/tenant_command_runtime_bundle_selection.py
```

The future publication adapter must contain the same binding identity and
digest together with the current lifecycle entry, expected bundle digest, and
the two existing SQL-function names. Adding it without a reviewed conformance
exception therefore fails the current marker classifier. Broadening the
existing exception would be unsafe: another Python source could then appear to
be a publication consumer, enter an import closure, or place temporal markers
in an active authority.

This contract establishes one narrow rule:

> The temporal checker may classify only
> `deployment/postgresql/temporal_runtime_bundle_publication.py` as the future
> temporal RuntimeBundle publication adapter. The checked-in adapter may be
> absent, or it may be present with the complete exact marker conjunction,
> exact module identity, and static import isolation. No other production
> source, active authority, or public conformance result changes.

This Phase A change does not implement the classifier or adapter.

## 2. Learning value

The contract proves that the accepted source-snapshot and temporal checker can
admit one new isolated control path without another scanner, manifest,
registry, service, public state, or runtime dependency. It reduces the
demonstrated risk of replacing a precise refusal with an open marker exception.

## 3. Exact decision

### 3.1 Complete merged parent authority

The exact parent authority is:

```text
path:
  docs/rfcs/
  OFARM_Temporal_RuntimeBundle_Catalog_Publication_Admission_RFC_v0_1.md
contract identity:
  ofarm.temporal-runtime-bundle-catalog-publication-admission.issue176.v0.1
merge commit:
  4e7aa838482b3b8525866185ba449e8766f835f2
repository bytes:
  47,814 bytes
  sha256:2161e9368f85b373b7cf54b6708edb7b291596defcf9683342e9583657a2298f
Git blob:
  9c180a782caac74501d0ed9ff9e75375b972adb5
```

Future conformance Phase B must authenticate the parent by exact relative
path, regular-file posture, byte length, SHA-256, and contract identity before
applying the publication exception. A missing, unreadable, symlinked,
length-mismatched, digest-mismatched, or identity-mismatched parent refuses.

This contract copies marker strings from the parent only to classify their
source ownership. It does not reinterpret the catalog, lifecycle, bundle,
transaction, target-tenant, or publication semantics owned by the parent.

### 3.2 Closed internal states and public composition

The publication classifier has exactly two private results:

```text
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_CLASSIFIED
```

They are checker-internal evidence only. They are not schema values, API
results, lifecycle states, RuntimeBundle fields, database states, routes,
outputs, or production claims.

The exact lawful composition is:

```text
EXACT V7 / SELECTION_STORAGE_CONFORMANT_ABSENT
  + PUBLICATION ADAPTER ABSENT
    -> PUBLICATION_ADAPTER_ABSENT
    -> PUBLIC RESULT REMAINS CONFORMANT_ABSENT

EXACT V8 / SELECTION_STORAGE_CONFORMANT_CLASSIFIED
  + GLOBAL_CONTENT_RETENTION_MIGRATION_ABSENT
  + PUBLICATION ADAPTER ABSENT
    -> PUBLICATION_ADAPTER_ABSENT
    -> PUBLIC RESULT REMAINS CONFORMANT_CLASSIFIED

EXACT V9 / SELECTION_STORAGE_CONFORMANT_CLASSIFIED
  + GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED
  + PUBLICATION ADAPTER ABSENT
    -> PUBLICATION_ADAPTER_ABSENT
    -> PUBLIC RESULT REMAINS CONFORMANT_CLASSIFIED

EXACT V9 / SELECTION_STORAGE_CONFORMANT_CLASSIFIED
  + GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED
  + EXACT PUBLICATION ADAPTER PRESENT
    -> PUBLICATION_ADAPTER_CLASSIFIED
    -> PUBLIC RESULT REMAINS CONFORMANT_CLASSIFIED

ANY OTHER COMPOSITION
    -> REFUSED
```

The target path must be absent in exact V7 and V8. Presence before the exact
version-9 retention foundation refuses even if every publication marker is
present. Within the existing selection-storage validator, private retention
evidence is initialized to `None`. Exact V7 leaves it `None`; exact V8 or V9
replaces it with the one result already returned by
`_classify_global_content_retention_migration()`. The validator then invokes
the publication classifier once with its private selection state and that
retention evidence. The classifier accepts `None` only for authenticated exact
V7 with the adapter absent. These values are created inside the same checker
invocation, never accepted from caller data. The publication classifier must
not reload migrations or recompute retention classification.

The public command-line output remains exactly:

```text
TEMPORAL CANDIDATE PASS: CONFORMANT_ABSENT
TEMPORAL CANDIDATE PASS: CONFORMANT_CLASSIFIED
```

No publication-specific output is added.

### 3.3 Exact adapter identity

The only classified publication source is:

```text
relative path:
  deployment/postgresql/temporal_runtime_bundle_publication.py
module identity:
  deployment.postgresql.temporal_runtime_bundle_publication
```

Presence and source bytes come only from the one authenticated public
`PythonSourceSnapshotV1`. The temporal checker does not open, stat, resolve,
glob, walk, import, execute, or reparse the path after snapshot construction.
The source-snapshot builder remains the owner of package-root custody,
regular-file posture, symlink refusal, UTF-8 decoding, module naming, AST,
import graph, and reachability.

No alias, renamed module, compatibility wrapper, generated path,
profile-specific copy, legacy copy, or second publisher qualifies.

### 3.4 Closed required marker conjunction

The exact ordered marker tuple is:

```text
PUBLICATION_ADAPTER_REQUIRED_MARKERS = (
  "ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1",
  "sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f",
  "sha256:ed48914f77bedacdfce32fb621819da7df7701b54d7862477db0a49ceee5cdc6",
  "sha256:c774100b13ad7d3f353148eeceeabd319167846825c7392ebbaca1f4ba62faea",
  "ofarm.retain_runtime_content",
  "ofarm.publish_runtime_bundle",
)
```

The future target source must contain all six case-sensitive strings. Zero or
an incomplete subset refuses. Their presence classifies the source; it does
not prove that the adapter correctly loads the binding, authenticates the
lifecycle entry, constructs the bundle, calls SQL, handles commit outcome, or
chooses a tenant. Those semantics remain owned by the parent contract and
future adapter tests.

Caller data, environment values, runtime discovery, documentation search,
newest-file selection, a mutable collection, or an alternate manifest cannot
add, remove, reorder, or substitute a marker.

### 3.5 Closed Python marker-ownership matrix

The classifier scans exactly `snapshot.modules_by_relative_path`. Every row is
classified by exact root-relative path before marker meaning is considered.

| Exact source class | Permitted publication-marker ownership | Classification effect |
| --- | --- | --- |
| `deployment/postgresql/temporal_runtime_bundle_publication.py` | all six markers, together | the only source that may satisfy `PUBLICATION_ADAPTER_CLASSIFIED` |
| `deployment/postgresql/tenant_command_runtime_bundle_selection.py` | exactly the binding identity and binding digest, as already required by inherited selection-storage law; none of the other four | remains only the selection adapter and never satisfies publication classification |
| `conformance/temporal_decision_log_check.py` | exactly the lifecycle-entry digest; none of the other five | remains only lifecycle conformance evidence and never satisfies publication classification |
| `conformance/temporal_contract_candidate_check.py` | enforcement constants | scanned non-production conformance owner; never satisfies publication classification |
| `kernel/tests/**` | synthetic verification occurrences | scanned non-production verification family; never satisfies publication classification |
| every other inventoried Python source, including `profile_si_ffs/tests/**` | none | any occurrence refuses |

The two inherited exact owners are not partial publication adapters. Their
permitted subsets are closed and path-specific. If the selection adapter gains
any of the other four markers, or the decision-log checker gains any of the
other five, conformance refuses. A copied marker in another conformance file is
not automatically exempt.

The checker and `kernel/tests/**` exemptions remain subject to production and
legacy reachability refusal. Their constants and fixtures cannot satisfy the
production adapter state.

This is a Python-source classification, not a repository-wide string scan.
Governance RFCs, candidate artifacts, the decision entry, and authenticated
SQL migrations retain their existing owners outside this inventory. Their
marker occurrences do not satisfy the adapter state.

### 3.6 Static isolation and active-surface closure

The future module must not be a key in either existing reachability map:

```text
production roots = kernel.api, kernel.application_runtime
legacy roots     = kernel.legacy_m1.api, kernel.legacy_m1.runtime
```

The checker must use the maps from the same public snapshot used for marker
classification. It must not rebuild an import graph or closure.

The existing single retained-AST inspection of
`deployment.postgresql/__init__.py` must be extended to reject either isolated
adapter module:

```text
deployment.postgresql.tenant_command_runtime_bundle_selection
deployment.postgresql.temporal_runtime_bundle_publication
```

The current architecture-v1 import resolution, every relative level, aliases,
star imports, nested scopes, classes, and `TYPE_CHECKING` remain controlling.
The complete temporal checker still makes exactly one
`snapshot.ast_for("deployment.postgresql")` call. A second AST copy, a second
source snapshot, or a private source read is forbidden.

The existing graph-edge check must also reject an initializer edge to the
publication module when the module is present. AST refusal remains required in
the absent state because an unresolved static import may not appear as a graph
edge.

The exact six marker strings plus the publication path and module identity
must remain absent from:

```text
kernel/runtime_bundle_components.json
profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json
profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json
```

The existing read of those three active authorities must be extended; a second
active-surface loader or dynamically discovered path is forbidden. Profiles,
routes, outputs, runtime roots, and other authorities remain stop conditions,
not new scan targets.

## 4. Authority map and exact reviewed state

| Authority | Exact reviewed identity | Authority retained |
| --- | --- | --- |
| Complete merged self-authority | this RFC path and contract identity; complete merged byte length and SHA-256 established only after exact-head review and merge | the internal adapter absent/classified rule, marker ownership matrix, validation order, Phase B envelope, and stop conditions |
| Complete merged parent | section 3.1; 47,814 bytes; `sha256:2161e9368f85b373b7cf54b6708edb7b291596defcf9683342e9583657a2298f` | exact catalog, lifecycle, bundle, target, transaction, result, and future adapter semantics |
| Global-content-retention conformance | `ofarm.runtime-bundle-global-content-retention-conformance-admission.issue176.v0.1`; 40,726 bytes; `sha256:7df5ebcb89e2a758c7906e9c4053228e5e151d049ff40e07f83d23a706d7a016` | exact V8/V9 internal retention states and version-9 repository classification |
| Selection-storage source-snapshot amendment | `ofarm.temporal-candidate-conformance-selection-storage-source-snapshot-amendment.issue176.v0.2`; 93,049 bytes; `sha256:820516d40956b6ea2a158413aea32a305aa078f20816ae35b257eb28491e5867` | one public Python snapshot, closed source inventories, static initializer law, import reachability, and active-surface evidence |
| Python-source architecture | `ofarm.architecture-python-source-snapshot-admission.issue176.v0.1`; 82,758 bytes; `sha256:6e4307077525f2bbb48992fa4c652ab75d279875063bd715cf21dc1f1d3216d5` | package-root custody, Python source units, module identities, AST custody, import graph, reachability, and CPython profile |
| Lifecycle decision | `governance/temporal-decision-log/ed48914f77bedacdfce32fb621819da7df7701b54d7862477db0a49ceee5cdc6.json`; exact parent pin and decision `PROMOTE_GOVERNED_INACTIVE` | lifecycle meaning and currentness for the exact three temporal subjects |
| Current temporal checker at reviewed base | `conformance/temporal_contract_candidate_check.py`; 173,792 bytes; `sha256:2ecf972dc85e4b6ee8080c0c808312b34ee42a44b7cc8573e94607d1f564a7f7` | reviewed-base classifier composition and public output; expected to change only in conformance Phase B |
| Current focused governance tests at reviewed base | `kernel/tests/test_temporal_contract_governance.py`; 128,880 bytes; `sha256:f874e3f2f88d2aa39d1933f07b5adbd72152f47b6ea41996baf6fa3aec983ac8` | reviewed-base focused evidence; expected to change only in conformance Phase B |
| Existing selection adapter occurrence | `deployment/postgresql/tenant_command_runtime_bundle_selection.py`; 10,712 bytes; `sha256:4fbb61f2f37bbab0a0d221220d864dc4ffef39ea7508fc82e797ceb9da4300f2` | inherited binding-marker ownership and selection-control behavior; not editable here |
| Existing lifecycle-checker occurrence | `conformance/temporal_decision_log_check.py`; 11,796 bytes; `sha256:e3242319582d43316f2c836ea44612267563f6d99320340ef393dcf53e0a98fc` | exact lifecycle-entry verification; not editable here |
| PostgreSQL initializer at reviewed base | `deployment/postgresql/__init__.py`; 7,803 bytes; `sha256:3fd65a1333d0dc16e62bbd024ed4b422d07cbeb21491ccb4582512092fbe931f` | package exports; neither isolated adapter may enter it |
| Active component authorities | the three exact paths in section 3.6 | closed application catalog, ActiveArtifactSet, and Capability Manifest |

The self, parent, global-content-retention, selection-snapshot, and
Python-source rows are versioned authorities future Phase B must authenticate.
The current checker and test identities are reviewed-base evidence because
those two files are expected to change in the separately approved
implementation. The selection adapter, lifecycle checker, initializer, and
active files are preservation evidence: Phase B cannot edit them, and their
existing owners remain controlling.

One authority owns each decision:

- this RFC owns only publication source classification;
- the parent owns adapter behavior and database ordering;
- the selection binding owns the sixteen source rows;
- the decision log owns lifecycle currentness;
- the RuntimeBundle model owns canonical construction and digest derivation;
- the two existing SQL functions own retention and tenant sealing;
- the global-content-retention classifier owns the V8/V9 prerequisite state;
- the selection-storage classifier owns the existing binding-marker pair;
- the public Python snapshot owns source and static reachability evidence;
- the active artifacts retain their current closed authorities;
- the production and legacy roots retain their existing import-firewall law;
  and
- issue #192 retains sole authority over audit-runtime behavior.

No caller, profile, environment variable, documentation file, filesystem
search, database target, alternate checker, or legacy repository may
substitute for those authorities.

## 5. Trust model

### 5.1 Protected assets

- the exact parent authority and six-marker conjunction;
- the distinction between the existing selection adapter, lifecycle checker,
  and future publication adapter;
- the exact V7/V8/V9 composition and unchanged public output;
- one public source snapshot and one initializer AST copy;
- static absence from production and legacy reachability;
- the closed active component authorities;
- the production-versus-legacy firewall; and
- the absence of publication, selection, command, runtime, output, or #192
  effect from conformance.

### 5.2 Trusted components and inputs

- checked-in exact RFC bytes after authentication;
- the fixed package root and accepted architecture snapshot builder;
- the retained authenticated tenant migration snapshot;
- the existing selection-storage and global-content-retention classifiers;
- the temporal checker after exact-head review; and
- SHA-256 and exact UTF-8 source bytes under the accepted execution profile.

### 5.3 Untrusted actors, inputs, and claims

- every repository byte until its owning authority authenticates it;
- caller-supplied roots, paths, module names, markers, digests, snapshots,
  states, catalogs, tenants, profiles, and environment values;
- aliases, symlinks, renamed or generated files, dynamic imports, wrappers,
  newest-file discovery, and documentation searches;
- a marker subset presented as complete publication authority; and
- a conformance pass presented as publication, selection, activation,
  deployment, current truth, or production readiness.

### 5.4 Excluded compromise capabilities

Compromise of the repository host, operating system, Git, CI, CPython,
accepted snapshot builder, accepted migration loader, SHA-256, reviewer
environment, or Codex platform is outside this boundary. Arbitrary in-process
mutation, undetectable filesystem substitution after authenticated snapshot
construction, practical hash collision, and operator compromise are excluded.

Ordinary source drift, visible path substitution, marker smuggling, partial
implementation, wrong composition, import reachability, active-surface drift,
and cross-boundary edits remain in scope and fail closed.

## 6. State machine and validation order

### 6.1 Governance ordering

```text
PROPOSED_PHASE_A_RFC
  -> EXACT_HEAD_REVIEWED_WITH_NO_BLOCKER
  -> DOCUMENTATION_ONLY_RFC_MERGED_WITH_NO_IMPLEMENTATION_AUTHORITY
  -> COMPLETE_MERGED_SELF_IDENTITY_AUTHENTICATED
  -> DRAFT_CONFORMANCE_PHASE_B_PR_CREATED_INSIDE_EXACT_ALLOWLIST
  -> COMPLETE_LIVE_DECISION_CARD_NAMES_THAT_PR
  -> LATER_EXACT_SAME_TASK_USER_APPROVAL
  -> CONFORMANCE_PHASE_B_IMPLEMENTED_AND_VERIFIED
  -> CONFORMANCE_PHASE_B_MERGED
  -> STOP BEFORE PUBLICATION ADAPTER PHASE B
```

No earlier state authorizes a later one. A merge, generic `go`, repository
credential, review comment, or passing check is not conformance implementation
approval. Publication-adapter Phase B remains a separate later approval under
the parent contract.

### 6.2 Future supported checker ordering

One supported temporal-checker invocation must execute in this order:

```text
FIXED PACKAGE ROOT
  -> AUTHENTICATE COMPLETE MERGED SELF-AUTHORITY
  -> AUTHENTICATE COMPLETE MERGED PARENT AUTHORITY
  -> AUTHENTICATE INHERITED GCRC / SELECTION-SNAPSHOT / PYTHON-SNAPSHOT AUTHORITIES
  -> LOAD ONE TENANT MIGRATION AUTHORITY SNAPSHOT
  -> BUILD ONE PUBLIC PYTHON SOURCE SNAPSHOT
  -> APPLY INHERITED SELECTION-STORAGE AND GCRC CLASSIFICATION
  -> PASS THE ALREADY-COMPUTED INTERNAL RETENTION STATE FORWARD
  -> CLASSIFY PUBLICATION PATH, MODULE, MARKER OWNERSHIP, AND FOUNDATION STATE
  -> EXTEND THE EXISTING ONE-AST INITIALIZER PROHIBITION
  -> VERIFY PRODUCTION AND LEGACY REACHABILITY FROM THE SAME SNAPSHOT
  -> EXTEND THE EXISTING THREE-PATH ACTIVE-SURFACE CHECK
  -> RUN ALL REMAINING CANDIDATE, MODEL, SEMANTIC, AND FIREWALL CHECKS
  -> RETURN ONLY THE INHERITED PUBLIC RESULT
```

Self and parent authentication happen before marker exceptions. Publication
classification happens only after inherited selection and retention evidence
is exact. Active and isolation checks happen before any pass is returned.

The checker is read-only. There is no database transaction, runtime time-of-
check/time-of-use boundary, or retained operational state in this contract.
The one immutable source snapshot is the source time boundary for one complete
invocation.

## 7. Invariants and acceptance criteria

- **TRBPC-001 — Self and parent first.** Future Phase B authenticates this
  complete merged RFC and then the exact merged parent before applying any
  publication exception.
- **TRBPC-002 — Closed composition.** Only the four V7/V8/V9 and
  adapter-absent/present compositions in section 3.2 pass.
- **TRBPC-003 — Foundation before adapter.** The checked-in publication
  adapter may be present only with exact V9 and
  `GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED`.
- **TRBPC-004 — One exact source identity.** Only the exact path and module in
  section 3.3 can satisfy publication classification.
- **TRBPC-005 — Complete marker conjunction.** The exact target contains all
  six ordered markers; zero, a subset, or a substitution refuses.
- **TRBPC-006 — Closed marker ownership.** Every inventoried Python source
  matches exactly one row of section 3.5; inherited subset owners cannot gain
  another publication marker.
- **TRBPC-007 — One source snapshot.** Marker, module, initializer, graph,
  reachability, and active composition use the existing one public snapshot
  and existing active-path reads; no second walker or path read exists.
- **TRBPC-008 — One initializer AST.** The complete temporal checker makes
  exactly one detached AST request for `deployment.postgresql` and refuses any
  static initializer reference to either isolated adapter in both absent and
  present states.
- **TRBPC-009 — Static reachability closed.** The publication module is absent
  from both fixed production and legacy reachability maps.
- **TRBPC-010 — Active surface closed.** Publication markers, path, and module
  remain absent from the exact component catalog, ActiveArtifactSet, and
  Capability Manifest.
- **TRBPC-011 — Inherited law preserved.** Selection-storage, retention,
  source-snapshot, temporal candidate, RuntimeBundle model, decision-log, and
  public output rules remain unchanged.
- **TRBPC-012 — No semantic duplication.** The checker does not parse or judge
  the target adapter's catalog loading, schema validation, bundle construction,
  SQL, target, transaction, replay, commit-outcome, or exception semantics.
- **TRBPC-013 — Classification only.** A pass creates no file, content row,
  bundle, selection, knowledge position, command authority, route, output, or
  current-truth effect.
- **TRBPC-014 — Production and legacy firewall.** Neither the checker nor the
  classified adapter becomes reachable from production or legacy roots, and
  no legacy-M1 authority becomes a dependency.
- **TRBPC-015 — Audit separation.** No #192 file, marker, event, receipt,
  failure behavior, service, or runtime authority changes.
- **TRBPC-016 — Closed implementation envelope.** Conformance Phase B changes
  only the paths in section 9.2.
- **TRBPC-017 — Fail closed.** Missing, malformed, ambiguous, unrecognized, or
  inconsistent evidence produces one conformance refusal and never falls
  through to a pass.
- **TRBPC-018 — Exact execution profile.** Verification uses the
  repository-required CPython 3.12.13 profile; an unsupported or ambiguous
  interpreter is not passing evidence.

## 8. Required negative cases

Every case starts from the supported temporal checker entry point and changes
only authenticated in-memory evidence or disposable test data unless the case
is a changed-file or hosted-gate assertion.

| Invariant | Concrete counterexample | Required result |
| --- | --- | --- |
| TRBPC-001 | Self RFC or parent is missing, symlinked, unreadable, wrong length, wrong digest, or lacks its exact contract identity | refuse before publication classification; self refuses before parent |
| TRBPC-002 | Adapter is present with exact markers in an otherwise exact V7 or V8 state | refuse; no fifth lawful composition |
| TRBPC-003 | Selection is classified but retention state is absent, unknown, recomputed, or not the already authenticated V9 classified state while the target exists | refuse |
| TRBPC-004 | A renamed file, alias module, profile copy, legacy copy, generated copy, symlink, or second publisher carries all six markers | source snapshot or exact identity classification refuses |
| TRBPC-005 | The exact target exists with zero markers, one missing marker, a changed digest, a changed function name, or reordered marker authority constant | refuse or exact constant-equality test fails |
| TRBPC-006 | Selection adapter gains the bundle digest; decision-log checker gains the binding digest; another conformance file gains one marker; or a `profile_si_ffs/tests/**` file gains any marker | refuse under the exact ownership matrix |
| TRBPC-007 | Implementation builds another snapshot, opens or stats the target, globs Python, resolves a path, imports a module, or rereads an active path through a second loader | focused source-structure or call-count test fails |
| TRBPC-008 | Initializer imports the target by absolute, relative, aliased, star, nested, class, or `TYPE_CHECKING` form while target source is absent or present | the one retained-AST check refuses |
| TRBPC-009 | A production or legacy root, wrapper, or re-export reaches the exact publication module | same-snapshot reachability check refuses |
| TRBPC-010 | Any active component authority contains a required marker, publication path, or module identity | existing extended active-path check refuses |
| TRBPC-011 | Existing V7/V8/V9 results, selection pair, retention classifier, required marker owner, source roots, decision evidence, or pass output differs | inherited conformance refuses; publication exception cannot legalize it |
| TRBPC-012 | Checker parses the target AST, imports it, validates function calls or exception hierarchy, or judges transaction correctness | source review and focused boundary test refuse the implementation |
| TRBPC-013 | A conformant result is used to create the adapter, publish a bundle, choose a tenant, create a selection, allocate knowledge, or admit a command | invalid claim with no effect |
| TRBPC-014 | Checker or target is added to a production/legacy closure, or imports quarantined legacy persistence as authority | architecture and temporal conformance refuse |
| TRBPC-015 | Implementation edits or depends on a #192 path or marker | changed-file and source-boundary checks refuse |
| TRBPC-016 | Any path outside section 9.2 changes, or inventory changes without a canonical node-ID difference | exact name-only and inventory gates refuse |
| TRBPC-017 | Source text, module identity, marker scan, AST, graph, reachability, state composition, or authority authentication crashes or is ambiguous | one fail-closed conformance error; no pass output |
| TRBPC-018 | Gate uses generic `python3`, a relative executable, a different implementation, or a patch version other than CPython 3.12.13 | invalid evidence; do not merge |

Focused tests must cover all four lawful compositions and every refusal family.
The adapter-present case uses an in-memory public-snapshot fixture or
disposable temporary source tree. Conformance Phase B must not create the
checked-in adapter path.

## 9. Proposed architecture and smallest coherent change

### 9.1 This Phase A PR

This RFC is the only changed file. It records the complete parent identity,
closed internal state, marker vocabulary, source ownership, reuse rules,
invariants, negative cases, later allowlist, and stops. It changes no checker
or repository classification.

### 9.2 Future conformance Phase B allowlist

After this complete merged RFC identity is authenticated and the active
same-task workflow explicitly approves an already-created draft Phase B PR,
that PR may edit only:

| Exact path | Permitted reason |
| --- | --- |
| `conformance/temporal_contract_candidate_check.py` | Authenticate this RFC and the parent, compose the existing internal retention state with the closed publication classifier, extend existing marker/initializer/reachability/active checks, and preserve public output. |
| `kernel/tests/test_temporal_contract_governance.py` | Add exact authority, lawful-state, marker-ownership, source-reuse, isolation, active-surface, output-preservation, and fail-closed tests. |
| `conformance/review_baseline_test_inventory.json` | Mechanical regeneration only when required by a change to the canonical collected test-node inventory, including a count or node-ID change. |

No other path is permitted. In particular, Phase B may not edit this RFC, the
parent, source-snapshot or architecture code, another conformance checker, the
selection adapter, lifecycle checker, PostgreSQL initializer, migration,
database code or test, candidate artifact, RuntimeBundle model, active
authority, profile, production/legacy module, route, output, or #192 file.

### 9.3 Types, ownership, and data flow

The implementation needs no new public type. It adds:

- one private immutable tuple containing the exact six markers;
- exact path and module constants;
- two private internal state strings; and
- one small private classifier consuming the retained public snapshot, the
  private selection state, and private retention evidence of either `None` for
  authenticated exact V7 or the one already-computed V8/V9 retention state.

The existing selection-storage composition should invoke the helper while its
internal retention evidence is still available. It must not accept either
state from caller data or expose the retention or publication state through
`validate_candidate_governance()`, the command line, a schema, or a result
wrapper.

The existing initializer and active-authority helpers should be extended with
the exact publication module and marker tuple. A parallel helper that repeats
their AST or file reads is larger and creates competing evidence.

### 9.4 Why this is the smallest coherent change

The current checker already loads every required authority and evidence class.
One subordinate classifier and extensions to existing exact checks are enough.
A second checker, source walker, import graph, schema, plugin, registry,
manifest, cache, service, or generalized publisher policy adds no capability
and would create another authority.

The publication adapter remains absent during conformance Phase B. Synthetic
present-state evidence proves the classifier before executable publisher code
exists, preserving the required ordering.

## 10. Non-goals

Neither this Phase A contract nor conformance Phase B will:

- create or edit `deployment/postgresql/temporal_runtime_bundle_publication.py`;
- retain content, publish a RuntimeBundle, choose a tenant, or connect to a
  database;
- add or change a migration, SQL function, role, grant, provisioner,
  readiness check, catalog verifier, or database test;
- modify the selection adapter, lifecycle checker, decision entry, binding,
  carrier, command, schema, candidate, or active registry;
- change `RuntimeBundle`, profiles, RuntimeBundle selection, knowledge
  allocation, governed command admission, authorization, materialization,
  qualification, current truth, routes, reads, historical views, WINDOW
  behavior, receipts, or outputs;
- parse or attest the future adapter's behavior;
- add a public conformance state, schema, result field, or output line;
- add another source snapshot, filesystem walker, AST owner, import graph,
  reachability builder, active-path registry, plugin, service, cache, daemon,
  environment option, or compatibility shim;
- claim arbitrary dynamic loading is impossible; the unchanged architecture
  checker remains the owner of dynamic-import policy;
- weaken the production-versus-legacy firewall;
- deploy or activate a temporal artifact; or
- implement or change #192 behavior.

## 11. Elegance audit

- New public states: zero.
- New schemas, manifests, registries, services, roles, credentials, or runtime
  modules: zero.
- New source snapshots, path walkers, AST builders, graphs, or active-path
  loaders: zero.
- New operational transition points: zero.
- Required publication markers: exactly six.
- Production publication paths: exactly one.
- Inherited marker-subset owners: exactly two.
- Lawful publication states: exactly absent and classified.
- Public conformance output changed: no.
- Future implementation files: two, plus conditional mechanical inventory.

No obsolete authority can be deleted in this boundary. A clean rewrite of the
temporal checker would disturb unrelated accepted conformance law; extending
the existing composition is smaller and clearer.

## 12. Provisional-design record

The classifier design is not a temporary semantic compromise. It is acceptable
before deployment because it is read-only, admits no checked-in adapter during
its own Phase B, changes no public state, and produces no operational effect.

The pre-deployment task-user approval evidence remains provisional. Before
deployment, it must be replaced or re-established through an independently
human-controlled and independently verifiable approval/signing system.

Evidence requiring redesign includes a need for another publication adapter,
a second catalog, mutable discovery, dynamic runtime loading, an initializer
export, a public publication conformance state, multiple publisher modules, or
active/runtime integration. Each requires a new reviewed authority rather than
a widened tuple or path set.

## 13. Traceability and verification

### 13.1 Invariant traceability

| Invariants | Future owning seam | Minimum negative evidence | Acceptance evidence |
| --- | --- | --- | --- |
| TRBPC-001 | exact self/parent authority constants and existing authority authenticator | self and parent missing, symlink, unreadable, length, digest, and identity cases | focused tests and package check |
| TRBPC-002–003 | existing selection/retention composition plus private publication classifier | all four lawful states; target present in V7/V8; unknown or recomputed prerequisite | temporal governance tests and unchanged CLI output |
| TRBPC-004–006 | exact path/module constants, six-marker tuple, and ownership matrix | alias, subset, substitution, alternate path, and inherited-owner expansion | exact constant-equality and snapshot mutation tests |
| TRBPC-007–009 | one public snapshot, existing one-AST initializer helper, graph, and reachability maps | second builder/read/AST, every initializer spelling, and production/legacy reachability | call-count, source-structure, architecture, and temporal tests |
| TRBPC-010–011 | existing active-path and inherited conformance composition | active marker injection and inherited state/output mutations | temporal checker, package checker, and exact active-path tests |
| TRBPC-012–015 | boundary review and unchanged runtime/legacy/#192 authorities | target parsing/import, operational claim, legacy dependency, or #192 edit | name-only diff, architecture check, and source review |
| TRBPC-016–018 | exact Phase B allowlist, fail-closed wrapper, and supported interpreter | extra path, unexplained inventory change, malformed evidence, crash, or wrong interpreter | diff gate, focused refusal tests, and CPython assertion |

### 13.2 Phase A verification

This documentation-only PR must prove:

- only this RFC changed;
- the parent identity in section 3.1 reconstructs exactly from merged `main`;
- every reviewed authority pin matches `4e7aa838482b3b8525866185ba449e8766f835f2`;
- the six-marker current occurrence inventory matches section 3.5;
- the future target path is absent;
- the three active authorities contain no temporal publication marker;
- the state composition, authority map, invariants, negative cases, non-goals,
  file boundary, and stop conditions are decision complete;
- `git diff --check` passes; and
- package conformance passes under exact CPython 3.12.13.

Minimum commands are:

```text
<absolute-cpython-3.12.13> -c "import platform,sys; assert platform.python_implementation() == 'CPython' and sys.version_info[:3] == (3,12,13)"
<absolute-cpython-3.12.13> conformance/temporal_contract_candidate_check.py
<absolute-cpython-3.12.13> conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --name-only origin/main...
```

The final command must list only this RFC. A generic or unsupported `python3`
is not substitute evidence.

### 13.3 Future conformance Phase B verification

Phase B must run under the same authenticated absolute CPython 3.12.13
executable and pass at least:

```text
<absolute-cpython-3.12.13> -m pytest -q kernel/tests/test_temporal_contract_governance.py
<absolute-cpython-3.12.13> -m pytest -q kernel/tests/test_rewrite_architecture_check.py
<absolute-cpython-3.12.13> conformance/rewrite_architecture_check.py
<absolute-cpython-3.12.13> conformance/temporal_contract_candidate_check.py
<absolute-cpython-3.12.13> conformance/ofarm_pkg_contract_check.py
<absolute-cpython-3.12.13> conformance/run_review_baseline.py
git diff --check
git diff --name-only <merged-self-base>...
```

Focused tests must prove one source-snapshot build; one initializer AST copy;
all four lawful compositions; unchanged public output; exact marker-tuple and
ownership-matrix equality; target path/module exactness; target absence in the
real conformance Phase B tree; synthetic exact-present classification; V7/V8
presence refusal; marker subset and alternate-owner refusal; both reachability
families; all initializer import forms; active-surface closure; no adapter
semantic parsing; and one conformance error for malformed evidence.

If canonical collected node IDs change, regenerate the inventory mechanically
and prove the diff is exactly the node-ID change. A count-only comparison is
insufficient.

Hosted PostgreSQL conformance, native amd64, native arm64, the canonical native
index, and exact-head review remain required where the repository workflow
requires them. Passing evidence is classification only.

## 14. Stop conditions and review disposition

Stop before conformance Phase B if:

1. this exact RFC has not merged or its complete path, identity, byte length,
   and SHA-256 cannot be authenticated;
2. the exact parent in section 3.1 cannot be authenticated;
3. current `main` is not an inherited lawful exact V9 state with the
   publication adapter absent;
4. a versioned source-snapshot, selection-storage, retention, lifecycle, or
   active authority differs;
5. no already-created draft Phase B PR is named in a complete live decision
   card followed by exact same-task user approval;
6. a path outside section 9.2 is needed;
7. a seventh marker, second publication path, new inherited subset owner, or
   dynamically discovered exception is needed;
8. a second source snapshot, path read, walker, AST copy, graph, reachability
   builder, active-path loader, schema, manifest, registry, plugin, or service
   is needed;
9. the existing selection or retention classifier, lifecycle meaning, public
   result, source roots, or active authority must change rather than be
   preserved;
10. adapter behavior, SQL, target selection, transaction, replay,
    commit-outcome, or exception hierarchy must be interpreted by conformance;
11. the checked-in adapter, a migration, database path, RuntimeBundle model,
    selection, knowledge ledger, command, route, read, output, profile,
    production/legacy runtime, or deployment file must change;
12. an arbitrary dynamic-loading guarantee is required;
13. testing would retain operational content, bundle, tenant, selection,
    knowledge, or command state; or
14. #192 behavior or authority must change.

Any such need is a contract amendment or a separate trust-boundary PR. The
conformance implementation stops after its exact Phase B merges. It does not
create the publication adapter or automatically resume parent Phase B.

Open decisions inside this boundary: none.

- **Blockers:** none identified in the author draft; exact-head review is
  required.
- **Follow-ups:** separately implement this conformance Phase B after explicit
  approval; only after it merges may the parent publication Phase B draft,
  live card, and separate approval sequence begin. Later production read-only
  selection, governed-command integration, and reads/outputs remain separate.
- **Preferences:** none recorded.

### Merge-stop rule

This documentation-only Phase A PR may merge when its acceptance criteria pass
and no demonstrated Blocker remains. Its merge grants no implementation or
publication authority. New ideas, Preferences, and non-blocking hardening
become Follow-ups and do not reopen this boundary.
