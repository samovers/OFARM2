# OFARM2 Temporal Candidate Conformance Selection-Storage Source-Snapshot Amendment — Phase A Contract v0.2

**Status:** proposed and inactive Phase A amendment; documentation-only,
unapproved, and without conformance, database, selection, runtime, deployment,
legacy, output, or #192 effect

**Contract identity:**
`ofarm.temporal-candidate-conformance-selection-storage-source-snapshot-amendment.issue176.v0.2`

**Amended contract identity:**
`ofarm.temporal-candidate-conformance-selection-storage-admission.issue176.v0.1`

**Reviewed base:** `aadbcd7a77e1647bf8ee6e2dfd74e69fb2f31517`

**RFC path:**
`docs/rfcs/OFARM_Temporal_Candidate_Conformance_Selection_Storage_Source_Snapshot_Amendment_RFC_v0_2.md`

**Date:** 2026-08-05

**Primary ticket:** #176

**Governed command:** `COMMIT_OPERATION_CLAIM_DRAFT`

**Primary trust boundary:** temporal candidate conformance ownership of the
static Python-source evidence used to classify the exact selection-storage
production references and prove that the exact administrative adapter is
outside the fixed production and legacy import closures

**Phase A PR boundary:** this RFC only

**Future temporal B2 PR boundary:**

```text
conformance/temporal_contract_candidate_check.py
kernel/tests/test_temporal_contract_governance.py
kernel/tests/test_temporal_carriers.py
conformance/review_baseline_test_inventory.json
```

The test inventory may change only when mechanically required by a change to
the canonical collected test-node inventory, including a count or node-ID
change.

## 1. Decision

This contract is a versioned amendment, not an informal edit to the approved
v0.1 selection-storage admission contract. It replaces only v0.1's private
architecture-helper dependency and the directly dependent Phase B integration
rules. All v0.1 selection-storage decisions not explicitly replaced in section
2 remain exact and authoritative.

After this exact Phase A amendment is reviewed, explicitly approved, published
truthfully, and merged, a separate explicitly requested temporal B2 PR may:

1. implement the closed selection-storage classifier already specified by the
   approved v0.1 contract;
2. obtain all Python inventory, retained source, fixed-root, graph, and
   reachability evidence from exactly one governed public
   `PythonSourceSnapshotV1` per complete temporal-checker invocation;
3. migrate the two remaining temporal-owned consumers away from the
   architecture checker's temporary private adapters; and
4. add only the focused conformance tests and mechanically required canonical
   test-inventory update needed to verify those acts.

The governed public builder and interface are exactly:

```python
from conformance.rewrite_architecture_check import (
    PythonSourceSnapshotV1,
    build_python_source_snapshot,
)

snapshot = build_python_source_snapshot(PACKAGE_ROOT)
```

The caller supplies only `PACKAGE_ROOT`. The snapshot's source-contract
identity, execution profile, inventory rules, module naming, source bytes,
graph semantics, production roots, legacy roots, and reachability are fixed by
the reviewed and versioned architecture authority carried by the returned
snapshot. They are never accepted from caller data, configuration,
environment, repository content outside that authority, or a lookalike object.

Temporal B2 directly uses:

```text
snapshot.modules_by_relative_path
snapshot.production_reachability
snapshot.legacy_reachability
```

It does not call, alias, wrap, or reproduce:

```text
_module_sources
_import_graph
_reachable_paths
PRODUCTION_IMPORT_ROOTS
LEGACY_IMPORT_ROOTS
```

The marker vocabulary, exact allowed production paths, two-path state model,
SQL migration inventory, three named active non-Python authorities, catalog
and provisioning decisions, and all non-effects remain owned by v0.1. This
amendment does not add a carrier row, migration, adapter, selected binding,
route, command integration, output, or runtime behavior.

## 2. Amendment scope and precedence

### 2.1 Exact authorities

The complete amended v0.1 authority is:

```text
docs/rfcs/OFARM_Temporal_Candidate_Conformance_Selection_Storage_Admission_RFC_v0_1.md
62540 UTF-8 bytes
sha256:716a45927846d068f595f81288b8d29ecc07891bcaf848e0284eb91ece4abc8d
contract: ofarm.temporal-candidate-conformance-selection-storage-admission.issue176.v0.1
```

The complete architecture source-snapshot authority is:

```text
docs/rfcs/OFARM_Architecture_Python_Source_Snapshot_Admission_RFC_v0_1.md
82758 UTF-8 bytes
sha256:6e4307077525f2bbb48992fa4c652ab75d279875063bd715cf21dc1f1d3216d5
contract: ofarm.architecture-python-source-snapshot-admission.issue176.v0.1
interface: ofarm.architecture-python-source-snapshot.v1
```

Architecture B1 merged on current `main` as:

```text
PR: #286
B1 implementation head: e8f5fc77f5e318b24133b9e33c370b24a2c3ae28
merge commit: aadbcd7a77e1647bf8ee6e2dfd74e69fb2f31517
```

The PR and commit identities are review and sequencing evidence. They do not
replace the complete contract identities or grant temporal authority.

This amendment's complete merged path, contract identity, UTF-8 byte length,
and SHA-256 must be pinned in temporal B2 only after its exact approval record
is published and merged. A proposed-design digest, Git commit, PR state,
branch, caller claim, or approval prose cannot substitute for that complete
merged authority.

### 2.2 Clauses replaced by v0.2

In the approved v0.1 contract, this amendment replaces only:

- the Python-source trusted input in section 3;
- the Python source inventory paragraph in section 5.2;
- the graph, root, and reachability mechanism in section 5.4;
- invariants TCSS-003 and TCSS-004 only to the extent that they name the
  private inventory and graph helpers;
- the private-helper negative case in section 8;
- the future Phase B file boundary and verification steps in sections 10 and
  11 only as stated in sections 10 and 11 here; and
- the private-helper stop condition in section 12.

If wording in those exact clauses conflicts with this amendment, this v0.2
amendment controls. No other v0.1 clause is replaced, relaxed, widened, or
reinterpreted.

### 2.3 Clauses preserved exactly from v0.1

The following remain exact, including every named path, marker, digest, state,
and refusal rule:

- the protected distinction between static conformance classification and
  operational selection storage;
- `SELECTION_STORAGE_ALLOWED_PRODUCTION_PATHS` and its exact two-path pair;
- the exact binding identity and canonical binding digest;
- the exact V7 prefix and the only two conformant states,
  `CONFORMANT_ABSENT` and `CONFORMANT_CLASSIFIED`;
- the authenticated tenant `MigrationSet` and retained
  `Migration.source_bytes` as the sole SQL inventory;
- every per-path marker and filesystem rule;
- the exact active catalog and profile authorities;
- the catalog, provisioning, active-authority, and outside-inventory
  governance classifications;
- the production-marker classification of every inventoried Python source
  except the exact checker path and `kernel/tests/**` verification family;
- the rule that the two verification exemptions never satisfy the production
  implementation pair;
- all authority pins and prerequisite checks not replaced here;
- all runtime, database, route, command, output, deployment, legacy, and #192
  non-effects; and
- the later database Phase B's separate authority and separate explicit
  implementation request.

No marker, path, state, exception, catalog authority, provisioning authority,
or operational effect may be inferred from this amendment.

## 3. Why this is one temporal boundary

The approved v0.1 contract specifies one static classifier, but its Phase B
design named private architecture helpers as the Python inventory and
reachability mechanism. Architecture B1 replaced the path-based internal
pipeline with a sealed public snapshot while preserving temporary adapters so
current consumers would not break. The two remaining external consumers are:

```text
conformance/temporal_contract_candidate_check.py
kernel/tests/test_temporal_carriers.py
```

Both are owned by the temporal conformance boundary. The architecture contract
requires a later temporal-owner contract to migrate them before architecture
B3 may remove the private adapters.

Implementing the approved classifier and migrating its evidence source are one
coherent temporal change. Both acts decide whether the same fixed temporal
markers occur in the same retained Python inventory and whether the same exact
adapter is statically unreachable from the same fixed roots. One snapshot
prevents a second walker, a second read, or two inconsistent observations.

This boundary does not change how the architecture checker builds or seals the
snapshot. It consumes the existing public architecture capability under a
temporal contract. If correct temporal behavior requires changing that public
interface, the work crosses into architecture ownership and must stop for a
separate reviewed boundary.

### 3.1 Learning value

This change demonstrates that the temporal classifier can use one retained,
architecture-governed source observation without executing checked modules or
creating its own inventory and graph authority. It removes the temporary
private-helper coupling, closes the source time-of-check/time-of-use gap in the
approved classifier design, and validates that the architecture snapshot is a
usable public evidence boundary for a separately governed consumer.

## 4. Trust model

### 4.1 Protected distinctions

Temporal B2 protects all of these distinctions:

```text
authenticated static source evidence != caller-selected source evidence
permitted marker classification       != operational selection storage
static import unreachability           != runtime activation prevention
conformance result                     != current/default tenant truth
test exemption                         != production implementation path
```

`CONFORMANT_CLASSIFIED` means only that the exact two production-reference
paths satisfy the closed v0.1 static classifier. It does not mean that a
migration exists in a deployed database, an adapter has run, a tenant has a
selected binding, a RuntimeBundle has changed, or a governed command can use
temporal behavior.

### 4.2 Trusted authority and components

Within this narrow boundary, temporal B2 trusts:

- the complete merged bytes of this amendment after exact publication;
- the complete merged v0.1 selection-storage authority in section 2.1;
- the complete merged architecture source-snapshot authority and exact public
  v1 interface in section 2.1;
- all v0.1 prerequisite authorities and fixed classifier values preserved by
  section 2.3;
- the architecture-owned `build_python_source_snapshot` implementation to
  authenticate its authority and return the exact sealed
  `PythonSourceSnapshotV1` described by that authority;
- the retained authenticated tenant migration authority used by v0.1;
- the temporal checker implementation and its fixed constants after review;
- CPython 3.12.13, the operating system, descriptor semantics, SHA-256, and
  memory integrity under the architecture authority's stated trust model; and
- the focused tests and mandatory package check as verification evidence, not
  as an independent source of law.

### 4.3 Untrusted inputs and claims

Temporal B2 does not trust:

- a caller-supplied contract identity, interface identity, root set,
  reachability map, marker exception, path eligibility, or conformance state;
- caller-constructed lookalikes, subclasses, mocks, monkeypatches, or mutable
  mappings offered as a source snapshot;
- repository filenames, contents, symlinks, marker text, comments, generated
  files, test fixtures, or dormant modules to define their own eligibility;
- environment variables, configuration, profiles, database contents, network
  data, Git metadata, PR metadata, branch state, or GitHub credentials as
  conformance authority;
- a second filesystem walk or path read performed after the governed snapshot
  is sealed; or
- runtime import behavior as evidence that a static source is unreachable.

The filesystem and repository source tree are evidence to be authenticated by
their owning authorities. They do not choose the rules used to authenticate
themselves.

Repository authors and local operators may substitute or mutate source and
authority files before or during a supported checker invocation; that
capability is in scope as untrusted filesystem input. The architecture builder
and temporal checker must authenticate or refuse it under their stated
time-of-check/time-of-use rules. The operator cannot supply different policy,
roots, exceptions, or a conformant result through the supported entry point.

### 4.4 Excluded compromise capabilities

Compromise of the trusted temporal checker, the architecture snapshot builder,
CPython, the operating system, descriptor guarantees, SHA-256, or in-process
memory integrity is outside this contract's threat model. Deliberate mutation
of trusted module globals or monkeypatching trusted code in the same process is
a trusted-code compromise, not an untrusted caller capability.

A compromised dependency or an operator who can replace trusted checker or
interpreter code is also outside scope. Operator control of ordinary repository
and authority-file contents remains in scope as the untrusted source
substitution described in section 4.3.

This exclusion does not permit caller data to choose an authority. Supported
entry points must still construct and retain their own evidence exactly as this
contract requires.

## 5. Authority map

| Decision or evidence | Sole authority | Temporal B2 use | Explicitly not authoritative |
| --- | --- | --- | --- |
| Selection-storage markers, paths, states, catalog and provisioning classifications | approved v0.1 selection-storage contract | preserve and implement exactly | this amendment, caller data, snapshot contents |
| Python inventory, retained Python bytes and text, module names, AST graph semantics, fixed root tuples, and reachability | architecture source-snapshot v0.1 contract and its authenticated public builder | consume one sealed public snapshot | temporal constants, private helper aliases, a second walker |
| Marker occurrence classification in retained Python sources | temporal checker under v0.1 as amended here | inspect `PythonSourceUnitV1.source_text` from `modules_by_relative_path` | filesystem rereads, module execution, reachability alone |
| SQL production inventory | v0.1 retained authenticated tenant `MigrationSet` | preserve unchanged | Python snapshot, SQL glob, later path read |
| Active non-Python inventory | the three exact v0.1 fixed paths | preserve unchanged | repository-wide discovery, caller list |
| Static adapter isolation | snapshot-owned production and legacy reachability maps | require exact adapter module absent from both closures | temporary root aliases, runtime observation |
| Dynamic-import prohibition | existing architecture checker and its accepted architecture law | require that checker to pass as a separate merge gate | temporal duplicate scanner or a claim derived only from static reachability |
| Database migration 0008 semantics and adapter behavior | later approved database Phase B | no use or effect | classifier result, this amendment |
| Tenant selection and governed command activation | later RuntimeBundle-selection and command authorities | no use or effect | marker presence, conformance state |

The temporal checker owns the decision that a marker occurrence is allowed or
refused. The architecture builder owns how Python evidence is acquired and
sealed. Neither owner may silently absorb the other's authority.

## 6. Exact temporal B2 state and ordering

One supported invocation of
`conformance/temporal_contract_candidate_check.py` follows this order:

1. Authenticate the complete merged identity of this amendment. Refuse on a
   missing path, wrong length, wrong digest, or wrong contract identity.
2. Authenticate the complete merged v0.1 selection-storage authority and every
   prerequisite it requires. No classifier exception exists before that
   succeeds.
3. Establish the retained authenticated tenant migration authority exactly as
   v0.1 requires. This remains the sole SQL source inventory.
4. Call `build_python_source_snapshot(PACKAGE_ROOT)` exactly once. Propagate a
   builder refusal as temporal-checker refusal. Do not fall back to a private
   helper, path walk, partial scan, or previously cached result.
5. Require the returned value to be the exact architecture-governed
   `PythonSourceSnapshotV1`, with the exact contract authority and descriptor
   interface identity in section 2.1. A lookalike, subclass, wrong authority,
   wrong interface, or caller-provided value refuses.
6. Retain that one snapshot for the remainder of the complete invocation.
7. Apply the v0.1 marker classifier to retained
   `snapshot.modules_by_relative_path` source units. Marker detection uses the
   retained `source_text`; it does not reopen or resolve `relative_path`.
8. Apply the unchanged v0.1 SQL classifier to retained
   `Migration.source_bytes`.
9. Inspect the three exact active non-Python authorities using the unchanged
   v0.1 rules.
10. For adapter isolation, use the retained snapshot's
    `production_reachability` and `legacy_reachability` directly. Do not
    recompute a graph or closure and do not supply root tuples.
11. Return only the v0.1 lawful result: `CONFORMANT_ABSENT`,
    `CONFORMANT_CLASSIFIED`, or refusal. No result creates an operational state
    transition.

The same retained source observation therefore governs Python marker
classification and static adapter isolation. SQL and active non-Python
evidence remain separate because they have separate existing owners.

The amended state machine remains:

```text
START
  -> AMENDMENT_AUTHENTICATED
  -> V0_1_AND_PREREQUISITES_AUTHENTICATED
  -> SQL_AUTHORITY_RETAINED
  -> PYTHON_SNAPSHOT_RETAINED
  -> CLOSED_INVENTORIES_CLASSIFIED
  -> CONFORMANT_ABSENT | CONFORMANT_CLASSIFIED | REFUSED
```

Any failure transitions directly to `REFUSED`. No transition leaves either
conformant state for storage, activation, command execution, current truth, or
output. A later filesystem change requires a new checker invocation; it cannot
mutate the sealed evidence or prior result.

## 7. Closed Python classification and isolation rules

### 7.1 Marker inventory

The Python marker inventory is exactly the keys and values of:

```text
snapshot.modules_by_relative_path
```

Each key is the architecture-governed root-relative `/` path. Each value is the
exact retained `PythonSourceUnitV1` for that path. The checker may read only the
immutable fields needed for v0.1 classification. It does not call `ast_for`,
because marker classification is exact retained text matching and requires no
detached AST custody.

The v0.1 production and verification classifications remain exact:

- `conformance/temporal_contract_candidate_check.py` is a scanned
  non-production exemption because it owns conformance constants;
- `kernel/tests/**` is a scanned non-production verification family;
- every other inventoried Python source is production-classified for marker
  purposes, including `profile_si_ffs/tests/**`; and
- the exact adapter path remains production-classified and is the only Python
  path that may satisfy the adapter half of the v0.1 implementation pair.

The two exemptions do not satisfy either production path. They are still
subject to the fixed import-closure rule: if an exempt test or checker module
is reachable from a fixed production or legacy root, the existing architecture
law or this contract's isolation rule refuses as applicable.

### 7.2 Static adapter isolation

The exact adapter module name is derived only by the architecture snapshot's
fixed module-naming law from the exact v0.1 allowed path:

```text
deployment/postgresql/tenant_command_runtime_bundle_selection.py
```

Temporal B2 must bind one implementation constant to the exact expected module
identity and verify that the snapshot's source unit for the allowed path has
that module identity. Path and module disagreement refuses; the checker does
not guess an alias.

The adapter module must not appear in any closure tuple in either:

```text
snapshot.production_reachability
snapshot.legacy_reachability
```

The map keys are the snapshot-owned fixed roots. Temporal B2 neither declares
nor passes roots. It verifies that the snapshot descriptor and returned maps
carry the exact architecture v1 fixed families, then uses every closure in
both maps. A missing root, extra root, narrowed map, wrong descriptor, or
adapter occurrence refuses through the governed snapshot or the temporal
check.

The adapter must remain absent from
`deployment/postgresql/__init__.py` re-exports exactly as v0.1 requires. Any
static import or re-export that places it in a production or legacy closure
refuses.

### 7.3 Dynamic-import authority remains separate

The public snapshot is static AST evidence. Temporal B2 claims only static
unreachability from the fixed production and legacy roots. It does not claim
that arbitrary runtime loading is impossible.

The existing architecture checker remains the sole owner of the accepted
production dynamic-import prohibition. Temporal B2 must run that checker as a
separate merge gate. It does not import a private architecture policy helper,
copy its dynamic-import vocabulary, create a second dynamic scanner, or turn a
green static reachability result into a broader runtime guarantee.

If a later use needs a runtime guarantee against dynamic loading, a reviewed
owner and enforcement boundary must be established separately. That need is a
stop condition here.

### 7.4 Catalog and provisioning authority remain unchanged

This amendment makes no new catalog, provisioning, or active-profile decision.
The exact V7 prefix, absent/classified states, three named active non-Python
paths, existing migration authority, and provisioning classifications remain
the v0.1 law.

Temporal B2 does not import or execute a repository catalog or provisioning
module to prove its own result. It does not discover new catalog paths. If the
v0.1 exact authorities cannot be verified without changing their owner or
executing checked repository code, temporal B2 stops for a separately reviewed
contract rather than widening this amendment.

## 8. Invariants

- **TCSSS-001 — Exact amendment first.** No amended selection-storage
  classification exists unless the complete merged identity of this v0.2
  amendment authenticates before classification.
- **TCSSS-002 — v0.1 remains law.** Every marker, path, state, SQL inventory,
  catalog, provisioning, and non-effect rule not explicitly replaced in
  section 2 remains exact.
- **TCSSS-003 — One public snapshot.** Each complete supported temporal-checker
  invocation calls `build_python_source_snapshot(PACKAGE_ROOT)` exactly once
  and retains that exact result.
- **TCSSS-004 — No private bridge.** Neither temporal consumer calls, aliases,
  wraps, reflects over, or reproduces `_module_sources`, `_import_graph`,
  `_reachable_paths`, `PRODUCTION_IMPORT_ROOTS`, or `LEGACY_IMPORT_ROOTS`.
- **TCSSS-005 — No second source observation.** Python marker classification
  and static isolation use only the one retained snapshot. No later path open,
  stat, resolve, glob, walk, import, parse, graph rebuild, or reachability
  rebuild supplies evidence.
- **TCSSS-006 — Authority is snapshot-owned.** The source contract, interface,
  descriptor, root sets, and reachability identities come from the reviewed
  architecture binding carried by the exact returned snapshot, never caller
  data.
- **TCSSS-007 — Same evidence.** The source unit inspected for an adapter marker
  and the graph/reachability evidence used for its isolation belong to the same
  retained snapshot.
- **TCSSS-008 — Static claim only.** Temporal B2 proves only static closure
  absence. Dynamic-import policy remains architecture-owned and separately
  verified.
- **TCSSS-009 — Exact classifier closure.** Both allowed paths absent is the
  only conformant pre-implementation state; both exact is the only conformant
  classified state; one present or any other production occurrence refuses.
- **TCSSS-010 — Verification is not eligibility.** Checker constants and
  `kernel/tests/**` synthetic values never satisfy the production pair.
- **TCSSS-011 — SQL custody is unchanged.** SQL markers are classified only
  from the retained authenticated `MigrationSet`; the Python snapshot grants
  no SQL authority.
- **TCSSS-012 — Active authorities are closed.** Only the three exact v0.1
  active non-Python paths are inspected in that class. A newly relevant active
  authority requires an amendment.
- **TCSSS-013 — No operational transition.** A conformant result never becomes
  an applied migration, selected binding, active RuntimeBundle, accepted
  command, materialized fact, current truth, route response, or output.
- **TCSSS-014 — Closed implementation boundary.** Temporal B2 edits only the
  four paths named in the header, with the inventory file changed only for a
  mechanical canonical node-inventory difference.
- **TCSSS-015 — Architecture ownership is preserved.** Temporal B2 does not
  edit the architecture checker or its tests and does not alter the public
  snapshot interface.
- **TCSSS-016 — Private-consumer deletion is complete.** At B2 completion,
  repository search finds none of the five private names in either current
  temporal consumer.
- **TCSSS-017 — Production-versus-legacy firewall remains closed.** The exact
  fixed production and legacy closure families are both checked; neither may
  import, re-export, or wrap the adapter.
- **TCSSS-018 — Fail closed.** Missing, inexact, unsupported, ambiguous, or
  multiply classified evidence refuses. No fallback path produces a conformant
  state.

## 9. Required negative cases

Focused verification must prove these outcomes through supported entry points:

| Case | Required outcome |
| --- | --- |
| This amendment is missing or has the wrong complete length, digest, path, or contract identity | refuse before building or classifying source evidence |
| The v0.1 selection-storage authority is missing or inexact | refuse before applying its exception |
| The architecture source-snapshot authority or interface is missing or inexact | builder or temporal checker refuses; no fallback scan |
| The public builder refuses for any governed filesystem, profile, resource, encoding, parse, graph, or authority reason | temporal checker refuses with no partial classifier result |
| A lookalike, subclass, mock, wrong-authority snapshot, or caller-provided map is offered | refuse; do not classify it |
| A second builder call occurs during one complete invocation | focused test fails |
| Marker classification opens, resolves, stats, globs, walks, imports, or reparses a Python path after snapshot construction | focused test fails |
| Marker classification and isolation use different snapshots | focused test fails |
| Either temporal consumer refers to any of the five private architecture names | repository-search and focused tests fail |
| A temporal implementation declares its own production or legacy root tuple | review and focused contract test fail |
| A snapshot root map is missing, narrowed, widened, or inconsistent with its exact descriptor | builder or temporal checker refuses |
| The exact adapter path maps to an unexpected module identity | refuse |
| The adapter appears in any production reachability closure | refuse |
| The adapter appears in any legacy reachability closure | refuse |
| The adapter is imported or re-exported by `deployment/postgresql/__init__.py` | refuse |
| A temporal change adds a duplicate dynamic-import detector or claims runtime loading is impossible from static reachability | stop; architecture authority remains separate |
| Only one of migration 0008 and the adapter exists | refuse under unchanged v0.1 state law |
| Either marker occurs in any other production-classified Python source | refuse, regardless of reachability |
| A verification exemption carries the markers | it never satisfies the production pair; existing exemption rules apply |
| A marker occurs in an authenticated migration other than exact 0008 | refuse |
| A new active catalog, profile, provisioning, route, command, materializer, output, or #192 authority needs classification | stop for a separately reviewed amendment |
| Temporal B2 requires an edit to `conformance/rewrite_architecture_check.py` or its tests | stop for the architecture-owner boundary |
| Temporal B2 requires a database path, migration, adapter, candidate artifact, active registry, RuntimeBundle, profile, route, output, or #192 edit | stop before editing it |

All v0.1 negative cases not replaced by section 2.2 remain required.

## 10. Non-goals

Neither this Phase A amendment nor temporal B2 will:

- edit, supersede, or restate the frozen v0.1 contract in place;
- edit the architecture source-snapshot RFC, implementation, public interface,
  tests, roots, graph semantics, execution profile, limits, or refusal codes;
- create database storage, migration 0008, its adapter, SQL, roles, grants,
  policies, catalog rows, provisioning behavior, or database tests;
- select a tenant binding or change a RuntimeBundle, profile, active registry,
  current/default claim, deployment, or readiness decision;
- integrate `COMMIT_OPERATION_CLAIM_DRAFT` or any other production command;
- add a semantic route, materialization behavior, current-state read,
  historical view, valid-time or knowledge-time execution, window behavior,
  publication, or output;
- activate a candidate artifact or add a carrier row;
- add a generic repository scanner, source service, cache, daemon, plugin,
  registry, configuration option, network protocol, or alternate snapshot;
- execute checked repository modules as conformance evidence;
- claim repository-wide marker coverage outside the closed v0.1 inventories;
- broaden the dynamic-import vocabulary or duplicate its architecture owner;
- change the production-versus-legacy firewall; or
- change audit-runtime work under #192.

## 11. Smallest coherent changes and PR boundaries

### 11.1 This Phase A PR

The only permitted changed path is:

```text
docs/rfcs/OFARM_Temporal_Candidate_Conformance_Selection_Storage_Source_Snapshot_Amendment_RFC_v0_2.md
```

This PR may review and, after exact architect approval, truthfully publish this
contract. It may not implement any conformance behavior.

### 11.2 Future temporal B2 PR

After the complete merged amendment identity is known and the user separately
requests temporal B2 implementation, that PR may edit only:

```text
conformance/temporal_contract_candidate_check.py
kernel/tests/test_temporal_contract_governance.py
kernel/tests/test_temporal_carriers.py
conformance/review_baseline_test_inventory.json
```

The inventory file is permitted only when mechanically required by a change to
the canonical collected test-node inventory, including a count or node-ID
change.

The smallest coherent implementation:

1. pins the complete merged identity of this amendment;
2. authenticates the unchanged complete v0.1 authority;
3. calls the public architecture builder once;
4. implements the closed v0.1 Python marker classifier on retained source
   units;
5. uses the same snapshot's owned reachability maps for static adapter
   isolation;
6. preserves the v0.1 SQL and active non-Python classifiers;
7. removes all five private architecture references from both temporal
   consumers; and
8. verifies refusal and unchanged non-effects.

It adds no new public temporal type, generic abstraction, compatibility layer,
second walker, second graph, cache, service, configuration surface, or runtime
dependency. Direct use of the governed public snapshot is the intended design.

### 11.3 Later boundaries remain separate

Temporal B2 does not authorize:

- architecture B3 removal of temporary private adapters;
- the database Phase B that creates migration 0008 and its administrator-only
  adapter;
- tenant storage or RuntimeBundle selection;
- governed command integration;
- routes, reads, historical/window execution, or outputs; or
- any #192 behavior.

Architecture B3 may be requested only after temporal B2 is merged on current
`main`, repository search proves no external use of the five private names,
and the complete package check passes. The database Phase B remains subject to
its own approved contract and separate explicit request. Neither may travel in
the temporal B2 PR.

### 11.4 Elegance audit

The design has three evidence owners because the evidence classes are already
separate authorities: v0.1 owns temporal classification law and retained SQL,
the architecture public snapshot owns Python source and reachability, and the
three exact active files retain their existing v0.1 ownership. It introduces
no duplicate source of truth and no new operational transition point.

One public snapshot is the only new composition edge. No field is copied into a
second authority object; the temporal checker consumes immutable public maps
directly. No new generic abstraction is introduced for this single use.

Temporal B2 deletes five private-name dependencies from two consumers. The
architecture owner may delete the temporary adapters later in B3. A clean
rewrite of either checker is not smaller: it would combine unrelated
architecture policies or disturb accepted temporal package checks. The direct
consumer migration within the existing temporal checker is the smaller
coherent design.

## 12. Verification

### 12.1 Phase A verification

This documentation-only PR must pass:

```bash
python3 conformance/ofarm_pkg_contract_check.py
git diff --check origin/main...
git diff --name-only origin/main...
```

The final command must list only this RFC. Review must confirm that the
authority map, invariants, negative cases, non-goals, file boundary, and stop
conditions are decision-complete and introduce no implementation authority.

### 12.2 Future temporal B2 verification

Temporal B2 must run under the exact execution profile required by the public
snapshot authority and pass at least:

```bash
python3 -m pytest -q kernel/tests/test_temporal_contract_governance.py
python3 -m pytest -q kernel/tests/test_temporal_carriers.py
python3 -m pytest -q kernel/tests/test_rewrite_architecture_check.py
python3 conformance/rewrite_architecture_check.py
python3 conformance/temporal_contract_candidate_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check origin/main...
git diff --name-only origin/main...
```

Repository search must prove the two temporal consumers have no reference to
the private names:

```bash
rg -n '_module_sources|_import_graph|_reachable_paths|PRODUCTION_IMPORT_ROOTS|LEGACY_IMPORT_ROOTS' \
  conformance/temporal_contract_candidate_check.py \
  kernel/tests/test_temporal_carriers.py
```

That search must return no match. Focused tests must also prove one public
builder call, shared-snapshot evidence, exact v0.1 absent/classified states,
all new refusal cases, and unchanged SQL and active-authority classification.

If collected node IDs change, regenerate the canonical inventory mechanically
and prove the change contains exactly the canonical node-ID difference. A
count-only comparison is insufficient.

### 12.3 Traceability

| Invariants | Owning future code | Negative or structural evidence | Acceptance evidence |
| --- | --- | --- | --- |
| TCSSS-001/002/009/011/012 | `conformance/temporal_contract_candidate_check.py` authority and classifier functions | altered amendment/v0.1/prerequisite, partial pair, other-path marker, wrong migration, or changed active authority refuses | temporal governance tests and package check |
| TCSSS-003/006 | temporal checker's single snapshot acquisition | exact call-count/source structure test; altered architecture authority refuses through supported CLI | temporal governance tests and exact CPython profile |
| TCSSS-004/016 | both named temporal consumers | private-name repository search must return no match | search, temporal tests, and package check |
| TCSSS-005/007 | marker and isolation functions sharing one retained snapshot | source-structure test rejects a path reader, second builder, graph builder, reachability builder, or separate evidence parameter | temporal governance tests |
| TCSSS-008 | unchanged architecture checker; temporal checker contains no duplicate policy | source-structure and diff review reject a temporal dynamic-import detector; altered dynamic-import case is refused by the architecture checker | architecture checker and its focused tests |
| TCSSS-010 | v0.1 classifier implementation | synthetic marker in checker/test inventory never satisfies implementation pair | temporal governance tests |
| TCSSS-013 | temporal result API remains conformance-only | changed-file and import scans show no storage/runtime consumer; conformant vectors create no side effect | focused tests and diff review |
| TCSSS-014/015 | PR boundary | any out-of-allowlist path fails changed-file gate | exact name-only diff |
| TCSSS-017 | snapshot reachability use in temporal checker and carrier test | adapter imported from either fixed family refuses | temporal carrier tests |
| TCSSS-018 | all supported checker entry points | each missing, altered, ambiguous, or unsupported evidence vector returns refusal and no conformant result | temporal tests and both conformance CLIs |

## 13. Stop conditions

Work stops before editing outside the applicable boundary if any of these is
true:

1. temporal B2 is requested before this exact amendment is technically
   reviewed, explicitly approved, truthfully published, merged, and pinned by
   its complete merged byte identity;
2. the implementation request is generic rather than a separate explicit
   request for temporal B2 under this amendment;
3. v0.1 marker, digest, path, state, SQL, catalog, provisioning, exemption, or
   non-effect semantics must change;
4. the architecture public interface, builder, roots, graph, reachability,
   execution profile, resource limits, or refusal behavior must change;
5. a second filesystem walker, source read, parser, graph, reachability
   calculation, dynamic-import detector, or snapshot is proposed;
6. checked repository code must be imported or executed as conformance
   evidence;
7. a path outside the exact Phase A or B2 allowlist must change;
8. a database schema, migration, adapter, catalog, provisioner, role, grant,
   policy, or stored row must change;
9. a candidate artifact, carrier matrix row, active registry, RuntimeBundle,
   profile, selector, command, route, materializer, read, output, deployment,
   legacy, or #192 authority must change;
10. a new production, legacy, active non-Python, catalog, provisioning, or
    outside-inventory occurrence class must be recognized;
11. static reachability is asked to prove a runtime dynamic-loading guarantee;
12. a conformant result is asked to become current truth, activation,
    publication, materialization, or output;
13. temporal B2 cannot remove all five private references from both named
    consumers within its exact allowlist; or
14. architecture B3, database Phase B, or another later boundary is proposed in
    the same PR.

When a stop condition occurs, report the authority expansion and propose a
separate prerequisite, follow-up, or stacked PR. Do not append the other trust
boundary merely to clear a review or conformance failure.

## 14. Approval, publication, and later execution sequence

The approved v0.1 contract's exact-action approval procedure is stronger than
the general pre-deployment workflow and remains binding for this amendment.
This proposed draft is not an approval request and grants no implementation
authority.

The required sequence is:

1. publish this one-file proposed Phase A draft in a draft PR;
2. obtain technical review of the exact design head;
3. resolve review findings within this one-file boundary;
4. compute the final canonical proposed-design UTF-8 byte length and SHA-256;
5. display one complete live plain-English decision card in the designated
   Codex task, binding the exact design, effects, non-effects, preservation
   rules, and next sequence;
6. receive the exact approval sentence as a later user-authored message in that
   same task;
7. add only the truthful approval-status transition and one approval record to
   this RFC;
8. re-review that publication to prove the approved design was preserved;
9. merge the documentation-only Phase A PR;
10. compute the complete merged RFC UTF-8 byte length and SHA-256, including
    the approval record;
11. receive a separate explicit request to implement temporal B2 under that
    complete merged authority;
12. implement, review, and merge only the section 11.2 allowlist; and
13. stop before architecture B3, database Phase B, governed command
    integration, routes, reads, outputs, or #192 work.

Typing or copying the exact approval sentence from the complete live decision
card displayed earlier in the same Codex task is valid. An approval sentence
or card digest copied from another task, another decision card, another
decision, documentation, a template, a PR, a GitHub review/comment/reaction,
repository credentials, or AI-authored or AI-sent text other than that complete
live decision card is invalid. PR authorship, commit authorship, mergeability,
merge, GitHub credentials, and generic words such as "approve" or "go" do not
substitute for the exact approval transition.

The approval record is evidence of the architect's decision, not a substitute
for it. Until the sequence reaches step 11, temporal B2 remains unauthorized.

## 15. Provisional design record and review disposition

**Provisional design record:** Not provisional. This is a proposed, inactive,
documentation-only Phase A amendment. It makes no repository artifact active
and no temporal behavior available. The future B2 integration is the permanent
public-evidence replacement planned by the architecture contract.

The design is reviewable only as one closed temporal conformance boundary:

- **authority:** approved v0.1 classifier law plus the governed public
  architecture snapshot;
- **invariants:** one retained snapshot, no private bridge, unchanged closed
  classifier, static-only reachability, and no operational transition;
- **non-goals:** every database, runtime, command, route, output, deployment,
  legacy, and #192 authority;
- **smallest coherent change:** one Phase A RFC, then one separately requested
  temporal B2 PR over the exact four-path allowlist; and
- **verification:** authenticated authorities, focused refusal tests, both
  conformance checkers, package verification, private-name search, and exact
  changed-file checks.

No open design choice is delegated to temporal B2. If review identifies a need
to change another authority, this Phase A draft must stop and name that
boundary separately.

**Open decisions:** none. Review must not delegate an authority, path class,
dynamic-import guarantee, or operational effect to implementation judgment.

**Current review disposition:**

- Blockers: none known before external technical review.
- Follow-ups: architecture B3 and the separately governed database Phase B,
  each only after its own prerequisites and explicit request.
- Preferences: none recorded.

**Merge-stop rule:** the Phase A PR may merge only after its exact design is
approved and the stronger publication procedure in section 14 passes with no
demonstrated Blocker. New ideas, preferences, and non-blocking hardening remain
separate Follow-ups and do not expand or reopen this boundary.
