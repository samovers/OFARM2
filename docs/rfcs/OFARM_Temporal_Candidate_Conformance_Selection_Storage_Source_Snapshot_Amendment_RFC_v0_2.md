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

Both temporal consumers derive the lexical package root without filesystem
canonicalization:

```python
# conformance/temporal_contract_candidate_check.py
PACKAGE_ROOT = Path(__file__).parent.parent

# kernel/tests/test_temporal_carriers.py
PACKAGE_ROOT = Path(__file__).parents[2]
```

Under the fixed CPython profile, each `__file__` is an absolute lexical path.
Neither consumer calls `resolve()`, `absolute()`, realpath, or another
normalizer before the public builder obtains descriptor-relative no-follow
custody. A non-absolute root refuses through the architecture builder; the
temporal consumer does not repair or replace it.

Temporal B2 directly uses:

```text
snapshot.contract_authority
snapshot.descriptor
snapshot.modules_by_relative_path
snapshot.import_graph
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
- the graph, root, reachability, initializer-import, and static-only isolation
  mechanism in section 5.4;
- invariant TCSS-004 only to the extent that it names the private inventory
  and graph helpers;
- invariant TCSS-011 and the directly related section 8 negative cases only to
  clarify that closure reachability is static AST evidence and to bind the
  initializer-import evidence defined here;
- the private-helper negative case in section 8;
- the future Phase B file boundary and verification steps in sections 10 and
  11 only as stated in sections 10 and 11 here; and
- the private-helper stop condition in section 12; and
- implicit use of v0.1 section 13 for this amendment's own approval and
  publication. Section 14 here is the complete amendment-specific adaptation;
  it does not alter v0.1's completed approval record.

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
  mappings as source authority; no supported temporal entry point accepts a
  snapshot or evidence parameter;
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
| Static adapter isolation | snapshot-owned import graph plus production and legacy reachability maps | refuse an initializer edge to the exact adapter and require the adapter key absent from both closures | temporal graph reconstruction, temporary root aliases, runtime observation |
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
5. Apply defensive compatibility assertions to the trusted builder's direct
   return: exact `PythonSourceSnapshotV1` type, exact contract authority, and
   exact descriptor interface identity and root fields in sections 2.1 and
   7.2. A type, authority, interface, or root-field mismatch refuses. Remaining
   descriptor semantics stay trusted builder evidence and are not copied into
   a second temporal descriptor. No supported caller supplies a snapshot
   parameter, and temporal B2 neither calls nor reproduces the private
   architecture seal guard `_is_builder_snapshot`.
6. Retain that one snapshot for the remainder of the complete invocation.
7. Apply the v0.1 marker classifier to retained
   `snapshot.modules_by_relative_path` source units. Marker detection uses the
   retained `source_text`; it does not reopen or resolve `relative_path`.
8. Apply the unchanged v0.1 SQL classifier to retained
   `Migration.source_bytes`.
9. Inspect the three exact active non-Python authorities using the unchanged
   v0.1 rules.
10. For adapter isolation, use the retained snapshot's `import_graph`,
    `production_reachability`, and `legacy_reachability` directly under section
    7.2. Do not reparse source, recompute a graph or closure, or supply root
    tuples.
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

The exact identities are:

```text
initializer path:
deployment/postgresql/__init__.py

initializer module:
deployment.postgresql

adapter path:
deployment/postgresql/tenant_command_runtime_bundle_selection.py

adapter module:
deployment.postgresql.tenant_command_runtime_bundle_selection
```

The module names follow only from the architecture snapshot's fixed module-
naming law. Temporal B2 binds the four exact path/module constants above; it
does not infer or accept an alias.

In `CONFORMANT_CLASSIFIED`, the adapter path must exist in
`snapshot.modules_by_relative_path`, and its retained source unit's
`module_name` must equal the exact adapter module. A missing unit or mismatch
refuses. In `CONFORMANT_ABSENT`, the adapter path and module are absent by
definition; the module-identity check is not run and absence does not become a
refusal.

The fixed root families are carried only by the exact descriptor:

```text
snapshot.descriptor.production_import_roots
  = ("kernel.api", "kernel.application_runtime")

snapshot.descriptor.legacy_import_roots
  = ("kernel.legacy_m1.api", "kernel.legacy_m1.runtime")
```

The two reachability maps do not map roots to closures. Each is a complete
union closure keyed by every reachable module name. Each value is the exact
first-discovered ordered path from one fixed root to its key, as sealed by the
architecture builder:

```text
snapshot.production_reachability:
  reachable production module -> first-discovered production path

snapshot.legacy_reachability:
  reachable legacy module -> first-discovered legacy path
```

Temporal B2 verifies the exact descriptor interface identity and the two exact
root fields. The remaining descriptor fields stay architecture-owned. As
structural compatibility assertions, it verifies that every fixed root is
present in its corresponding map with value `(root,)` and that every retained
path is non-empty, begins with one exact root from that family, and ends with
its mapping key. It then refuses if the exact adapter module is a key in either
map. It does not scan path values for eligibility and does not reconstruct
reachability.

Semantic closure completeness, deterministic first discovery, and absence of a
narrowed or widened map remain trusted architecture-builder evidence. A
trusted builder returning a structurally plausible but incomplete or expanded
closure is an architecture defect or trusted-code compromise under section
4.4, not a temporal input that B2 independently detects.

The initializer rule is independent of fixed-root reachability. When the
initializer path is present in `snapshot.modules_by_relative_path`, its source
unit must name the exact initializer module and `snapshot.import_graph` must
contain that module's graph entry. Any `PythonImportEdgeV1` in that entry whose
`target` is the exact adapter module refuses.

The architecture graph records the exact edge for all of these static forms
when the retained adapter exists, including aliases and statements nested under
functions, classes, or `TYPE_CHECKING`:

```python
import deployment.postgresql.tenant_command_runtime_bundle_selection
from deployment.postgresql import tenant_command_runtime_bundle_selection
from . import tenant_command_runtime_bundle_selection
from .tenant_command_runtime_bundle_selection import selected_binding
```

In `CONFORMANT_ABSENT`, the adapter is not a retained module and therefore
cannot be an architecture-v1 graph target. Running the same exact edge check
does not turn lawful pair absence into refusal. The unchanged architecture
checker still owns syntax and dynamic-import policy.

This section replaces v0.1 section 5.4 and clarifies v0.1 TCSS-011 only for
static AST evidence. It preserves the refusal for a static initializer import
or re-export and for static reachability from either fixed family. It neither
adds nor implies a runtime or computed-loading guarantee.

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
  fixed production and legacy closure families are both checked by exact
  adapter-key absence, and the initializer graph entry carries no exact adapter
  edge.
- **TCSSS-018 — Fail closed.** Missing, inexact, unsupported, ambiguous, or
  multiply classified evidence refuses. No fallback path produces a conformant
  state.
- **TCSSS-019 — Lexical root custody.** Both temporal consumers derive their
  exact absolute lexical package root from `__file__` without `resolve()`,
  realpath, or normalization before the public builder takes custody.
- **TCSSS-020 — Byte-closed approval.** Approval binds this amendment's exact
  canonical design bytes in the fixed Codex task; publication changes only the
  exact status block and appends one complete approval record; temporal B2
  authenticates the complete merged amendment before applying it.

## 9. Required negative cases

Focused verification must prove these outcomes through supported entry points:

| Case | Required outcome |
| --- | --- |
| This amendment is missing or has the wrong complete length, digest, path, or contract identity | refuse before building or classifying source evidence |
| The v0.1 selection-storage authority is missing or inexact | refuse before applying its exception |
| The architecture source-snapshot authority or interface is missing or inexact | builder or temporal checker refuses; no fallback scan |
| The public builder refuses for any governed filesystem, profile, resource, encoding, parse, graph, or authority reason | temporal checker refuses with no partial classifier result |
| The trusted builder's direct return has the wrong exact public type, contract authority, descriptor interface, or root fields | defensive compatibility assertion refuses; no caller-supplied evidence seam exists |
| A second builder call occurs during one complete invocation | focused test fails |
| Marker classification opens, resolves, stats, globs, walks, imports, or reparses a Python path after snapshot construction | focused test fails |
| Marker classification and isolation use different snapshots | focused test fails |
| Either temporal consumer refers to any of the five private architecture names | repository-search and focused tests fail |
| A temporal implementation declares its own production or legacy root tuple | review and focused contract test fail |
| Either consumer uses `resolve()`, realpath, `absolute()`, or another pre-builder normalizer to derive `PACKAGE_ROOT` | source-structure test fails; no alternate root is admitted |
| A descriptor root tuple differs from the exact v1 family | defensive compatibility assertion refuses |
| A fixed root is missing from its corresponding map or does not map to `(root,)` | defensive compatibility assertion refuses |
| A retained reachability path is empty, begins outside its exact root family, or ends somewhere other than its mapping key | defensive compatibility assertion refuses |
| The trusted builder returns a structurally plausible but semantically narrowed or widened closure | architecture defect or trusted-code compromise; temporal B2 does not recompute or independently accept it |
| `CONFORMANT_ABSENT` has no adapter source unit | pass the module-identity and initializer-edge subchecks; absence alone never refuses |
| In `CONFORMANT_CLASSIFIED`, the exact adapter path is missing or maps to an unexpected module identity | refuse |
| The exact adapter module is a key in the production reachability map | refuse |
| The exact adapter module is a key in the legacy reachability map | refuse |
| A present initializer path maps to a module other than exact `deployment.postgresql` or lacks its graph entry | defensive compatibility assertion refuses |
| The initializer graph entry contains the exact adapter target through an absolute import, package import, relative import, alias, nested scope, or `TYPE_CHECKING` | refuse |
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
5. uses the same snapshot's owned import graph and reachability maps for static
   adapter isolation;
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
`main`, repository search proves no external call or use of the three private
helpers or the two root aliases (the five exact names in section 1), and the
complete package check passes. The database Phase B remains subject to its own
approved contract and separate explicit request. Neither may travel in the
temporal B2 PR.

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
exact descriptor-root and reachability-entry structure, exact adapter-key
absence, all four initializer import forms plus aliases and nested imports,
lexical root derivation without normalization, all other new refusal cases,
and unchanged SQL and active-authority classification.

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
| TCSSS-017 | snapshot import-graph and reachability use in temporal checker and carrier test | initializer edge or adapter key in either fixed family refuses | temporal carrier and governance tests |
| TCSSS-018 | all supported checker entry points | each missing, altered, ambiguous, or unsupported evidence vector returns refusal and no conformant result | temporal tests and both conformance CLIs |
| TCSSS-019 | package-root constants in both temporal consumers | source-structure test rejects `resolve`, realpath, `absolute`, or another pre-builder normalizer | temporal governance and carrier tests |
| TCSSS-020 | this RFC's publication record and temporal checker authority constants | reconstructed design, card, approval, publication, or complete merged identity mismatch stops or refuses | publication re-review and package check |

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
    the same PR;
15. temporal B2 needs the private architecture seal guard or another private
    architecture API; or
16. either temporal consumer needs path resolution or normalization before the
    public builder takes lexical root custody.

When a stop condition occurs, report the authority expansion and propose a
separate prerequisite, follow-up, or stacked PR. Do not append the other trust
boundary merely to clear a review or conformance failure.

## 14. Amendment-specific byte-authenticated approval and publication

This section is the complete amendment-specific adaptation of the stronger
v0.1 section 13 procedure. It governs approval and publication of this v0.2
amendment only. It neither rewrites nor substitutes for v0.1's completed
approval record. Before the exact transition below, this design grants no
implementation authority.

### 14.1 Canonical design bytes

The canonical design:

- is UTF-8;
- uses LF line endings only;
- contains no CR byte and no UTF-8 BOM;
- begins with this document's first `#` byte;
- ends after the final period of the merge-stop rule at the end of section
  15.1; and
- includes the LF ending that final line, with exactly one terminal LF in the
  extracted design identity.

The exact canonical design byte length and SHA-256 are computed only after all
technical Blockers are resolved at one reviewed design head. They are not
self-declared while wording is still changing. Any later protected-design edit
creates a different design identity and requires a replacement review, card,
and approval.

The proposed top-level status block in the canonical design is the exact old
block reproduced in section 14.3. The Appendix A publication record is not part
of the canonical design identity.

### 14.2 Complete live card and human authority

Approval may be solicited only in Codex task:

```text
019fa821-93c9-7ef1-8c94-1c0e92ea46b9
```

The AI must first display one complete live plain-English decision card in that
task. Canonical card extraction:

- is UTF-8 with LF only and no CR or BOM;
- begins with the exact line
  `OFARM2 COMPLETE LIVE DECISION CARD`;
- ends with the exact line
  `END OF OFARM2 COMPLETE LIVE DECISION CARD`; and
- excludes a terminal LF from the card byte identity.

The card must state:

- this exact contract identity, RFC path, reviewed base, draft PR, and final
  reviewed design head;
- the canonical design encoding, byte length, and SHA-256;
- the card's extraction rule;
- the problem, recommended decision, primary trust boundary, and authority map;
- the primary risk and its bound;
- the one permitted approval effect and every non-effect;
- the decision-level invariants and exact future B2 maximum path envelope;
- the verification gates, reapproval triggers, provisional posture, and next
  required sequence; and
- the exact approval sentence, its UTF-8 byte length, and SHA-256, excluding a
  terminal LF from the sentence identity.

The card's reapproval triggers are any changed protected-design byte, decision
identity or version, trust boundary, authority, material effect or non-effect,
invariant, maximum path envelope, named draft PR, or final reviewed design
head; a replacement card or later cancellation; or loss of directly
inspectable task evidence. A triggered change requires a replacement technical
review and complete card before any new approval request.

Immediately after the extracted card, outside its canonical bytes, the AI must
display the card's exact UTF-8 byte length and SHA-256 and then solicit only the
exact approval sentence. The approval request is invalid if that external card
identity does not recompute or if another card or changed design intervenes.

The exact approval sentence is derived by replacing the two angle-bracketed
placeholders in this one-line template and changing no other byte:

```text
I explicitly approve the Phase A design of contract ofarm.temporal-candidate-conformance-selection-storage-source-snapshot-amendment.issue176.v0.2 at sha256:<CANONICAL_DESIGN_SHA256> (<CANONICAL_DESIGN_BYTE_LENGTH_WITH_COMMAS> bytes) in Codex task 019fa821-93c9-7ef1-8c94-1c0e92ea46b9 and authorize one documentation-only approval record with exactly the provenance, permitted effect, non-effects, preservation rules, and next required sequence stated in the complete decision card displayed immediately before this approval request in the same task.
```

`<CANONICAL_DESIGN_SHA256>` is replaced by the exact 64-character lowercase
hexadecimal digest. `<CANONICAL_DESIGN_BYTE_LENGTH_WITH_COMMAS>` is replaced by
the exact positive decimal byte length with standard three-digit comma
grouping. The live card contains the fully substituted sentence with no angle
brackets.

The designated architect must send that exact sentence as the entire text of a
later user-authored message in the same task. Typing it or copying it directly
from that complete live card is valid. An approval sentence or card digest
copied from another task, card, decision, document, template, AI output other
than that complete live card, PR, GitHub review/comment/reaction, or any other
source is invalid. AI/tool messages, repository credentials, PR or commit
authorship, mergeability, merge, and generic words such as `approve` or `go`
never count.

Before recognizing approval, the AI must directly retrieve the complete card
and later user message with stable task references; verify their exact bytes,
task, ordering, user authorship, and timestamps; verify no intervening
replacement card, changed design, or later cancellation; and fail closed if
the original task evidence has been compacted, summarized, lost, or cannot be
independently inspected. The user message is the architect's decision. The
repository appendix is evidence of that decision, not a substitute for it.

### 14.3 Exact publication differences and closed appendix

Only after valid approval may the exact top-level status block immediately
after the document title change from:

```text
**Status:** proposed and inactive Phase A amendment; documentation-only,
unapproved, and without conformance, database, selection, runtime, deployment,
legacy, output, or #192 effect
```

to:

```text
**Status:** architect-approved Phase A amendment; documentation-only and
without conformance, database, selection, runtime, deployment, legacy, output,
or #192 effect
```

No other occurrence of either block changes. After the section 15.1 merge-stop
rule and its canonical terminal LF, publication appends exactly one additional
LF and one `## Appendix A — Architect approval record`. The appendix has this
closed field set:

1. contract identity, RFC path, reviewed base, draft PR, and exact approved
   design head;
2. canonical approved-design encoding, byte length, and SHA-256;
3. complete v0.1 and architecture-RFC identities from section 2.1, architecture
   interface identity, and B1 merge sequencing evidence;
4. Codex task identifier; card turn, stable item and underlying message
   references, timestamp, extraction rule, byte length, and SHA-256;
5. architect-approval turn, stable item and underlying message references,
   timestamp, observed user authorship, exact sentence, sentence byte length,
   and sentence SHA-256;
6. exact-head technical review evidence that preceded the live card;
7. the sole permitted effect and every non-effect;
8. protected-design preservation and publication-byte reconstruction rules;
   and
9. the exact next required sequence through the separate temporal B2 request
   and the stop before every later boundary.

No schema, second record, currentness layer, service, database, or GitHub
automation is created. The approval appendix is the only repository record.
Publication-byte/provenance re-review is later external merge-gate evidence at
the publication head; it is not written back into Appendix A and therefore
does not create a circular publication identity.

To reconstruct the approved canonical design from publication bytes, take the
bytes from the document's first `#` through the LF ending section 15.1, exclude
the following blank line and Appendix A, and replace only the first top-level
approved status block with the exact proposed block above. The reconstructed
bytes must equal the card's canonical design length and SHA-256 exactly.

Any change to protected design text, a second status change, a different
appendix heading, a missing or extra appendix field, an inexact reconstructed
design, or a false provenance field invalidates publication and requires a new
reviewed design and approval.

### 14.4 Mandatory publication-byte and provenance re-review

The documentation-only publication must receive a focused re-review at its
exact head before merge. That reviewer must:

1. prove that the only changed path remains this RFC;
2. reconstruct and authenticate the complete canonical design under section
   14.3;
3. prove that the only publication differences are the exact status-block
   replacement and one Appendix A;
4. directly verify the complete live card and approval message in the fixed
   Codex task, including stable references, exact bytes, ordering, authorship,
   timestamps, and absence of a replacement or cancellation;
5. verify every appendix field against repository and task evidence;
6. verify all required hosted gates at the exact publication head; and
7. state whether any demonstrated Blocker remains.

GitHub credentials, a green workflow, or an internally consistent appendix
cannot prove private Codex provenance. If direct task evidence is unavailable,
merge remains conditional until a reviewer with direct access verifies it. No
repository patch is required when the recorded evidence is exact; any mismatch
requires corrected publication through this same byte-authenticated process.

### 14.5 Permitted effect, non-effects, and next sequence

Approval's sole permitted effect is to make this exact canonical Phase A design
architect-approved and authorize the one-file status transition and Appendix A
publication record.

Approval does not authorize temporal B2 implementation, a checker or test
change, migration 0008, the administrator adapter, database storage or
mutation, a role or grant, tenant selection, RuntimeBundle or profile
activation, runtime integration, `COMMIT_OPERATION_CLAIM_DRAFT`, a route,
materialization, qualification, current-state read, historical or window
execution, output, receipt, deployment, legacy behavior, architecture B3, or
#192.

After the truthful publication merges:

1. compute the complete merged RFC UTF-8 byte length and SHA-256, including the
   approved status and Appendix A;
2. authenticate that complete merged identity against current `main`;
3. receive a separate explicit request to implement temporal B2 under this
   exact complete merged authority;
4. reproduce the approved invariant traceability and implement only the
   section 11.2 allowlist;
5. review and merge temporal B2 only after all section 12 gates pass; and
6. stop before architecture B3, database Phase B, governed-command
   integration, routes, reads, outputs, or #192 work.

Before deployment, this provisional Codex approval channel must be replaced by
independently human-controlled and independently verifiable approval or
signing.

## 15. Provisional design record and review disposition

**Provisional design record:** Not provisional. The future B2 integration is
the permanent public-evidence replacement planned by the architecture
contract. At canonical design freeze, the repository record uses the proposed
and inactive status block reproduced in section 14.3. A valid later publication
may replace only that top-level block and append Appendix A; this historical
statement remains true in either state.

The design is one closed temporal conformance boundary:

- **authority:** approved v0.1 classifier law plus the governed public
  architecture snapshot;
- **invariants:** one retained snapshot, no private bridge, unchanged closed
  classifier, exact public graph/reachability semantics, static-only isolation,
  byte-closed approval, and no operational transition;
- **non-goals:** every database, runtime, command, route, output, deployment,
  legacy, and #192 authority;
- **smallest coherent change:** one Phase A RFC, then one separately requested
  temporal B2 PR over the exact four-path allowlist; and
- **verification:** authenticated authorities, focused refusal tests, both
  conformance checkers, package verification, private-name search, exact
  changed-file checks, and publication-byte/provenance re-review.

**Open decisions:** none. Review must not delegate an authority, path class,
dynamic-import guarantee, approval substitution, or operational effect to
implementation judgment. If review identifies a need to change another
authority, work stops and names that boundary separately.

**Review disposition required before a live card:**

- Blockers: none demonstrated at the final reviewed design head.
- Follow-ups: architecture B3 and the separately governed database Phase B,
  each only after its own prerequisites and explicit request.
- Preferences: do not delay approval or expand this boundary.

### 15.1 Merge-stop rule

The Phase A PR must not merge while its top-level status is proposed or
unapproved. Its publication must not merge unless the exact canonical design
has valid architect approval, the only publication differences are the exact
status-block replacement and one complete Appendix A, the focused re-review in
section 14.4 passes at the exact head, every hosted gate passes, and no
demonstrated Blocker remains. New ideas, preferences, and non-blocking
hardening remain separate Follow-ups and do not expand or reopen this boundary.
