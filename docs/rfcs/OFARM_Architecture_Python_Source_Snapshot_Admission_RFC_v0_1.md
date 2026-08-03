# OFARM2 Architecture Python Source Snapshot Admission — Phase A Contract v0.1

**Status:** proposed Phase A contract; documentation-only and unapproved

**Contract identity:**
`ofarm.architecture-python-source-snapshot-admission.issue176.v0.1`

**Snapshot interface identity:**
`ofarm.architecture-python-source-snapshot.v1`

**Reviewed base:** `b81fd35aa88ae57172c9c68688367dd3a584e0be`

**RFC path:**
`docs/rfcs/OFARM_Architecture_Python_Source_Snapshot_Admission_RFC_v0_1.md`

**Date:** 2026-08-03

**Primary ticket:** #176

**Review evidence:** PR #283 review `4847814084`, exact reviewed head
`9ee9f6856bafd26cfef6914074bffc230bb0c599`

**Primary trust boundary:** architecture-checker ownership and integrity of the
repository Python-source inventory, retained source evidence, parsed syntax,
static import graph, and fixed production and legacy root sets

**Phase A PR boundary:** this RFC only

**Future architecture Phase B PR boundary:**
`conformance/rewrite_architecture_check.py`, its focused existing test module,
and canonical test-inventory metadata only when mechanically required

## 1. Decision

After the designated architect explicitly approves this exact contract and a
documentation-only publication truthfully records that approval, one separate
architecture-owned Phase B may replace the path-only, rereading Python-source
helpers in `conformance/rewrite_architecture_check.py` with one versioned,
contract-authenticated, immutable source snapshot.

The snapshot is constructed by exactly one supported interface:

```text
build_python_source_snapshot(root: Path) -> PythonSourceSnapshotV1
```

The caller supplies only the lexical absolute source-tree location. The caller
does not supply the source contract, inventory rules, module naming rules,
encoding, graph rules, production roots, legacy roots, or any exception. Those
values are fixed by this reviewed, versioned contract and are carried in every
successful snapshot.

One successful snapshot contains, at minimum:

- the exact snapshot interface identity;
- the authenticated complete merged identity of this RFC;
- the exact fixed source-contract descriptor in section 5;
- the lexical absolute root used for acquisition;
- one immutable record for every included Python source, keyed uniquely by
  module name and by root-relative POSIX path;
- each record's module name, exact root-relative path, retained source bytes,
  strict UTF-8 text, byte length, and SHA-256;
- one privately retained parsed `ast.Module` derived from those exact bytes;
- one immutable normalized static import graph derived only from the retained
  AST set;
- the exact production and legacy root tuples; and
- immutable production-root and legacy-root reachability paths derived only
  from that graph and those fixed tuples.

The snapshot builder does not execute, import, evaluate, compile to executable
bytecode, or otherwise ask any inventoried repository module to describe
itself. Once the snapshot is sealed, filesystem paths are evidence of origin
only. Every architecture observation in the same checker invocation uses
retained bytes, retained text, detached copies of the retained AST, or
immutable graph products; no consumer rereads a repository Python path.

This contract does not authorize PR #283 to resume. It does not amend the
temporal selection-storage contract's exact `_module_sources(PACKAGE_ROOT)`
coupling. After this architecture interface is implemented and merged, a
separate reviewed temporal-contract amendment must decide whether and how the
temporal checker may consume it and must separately close the remaining
catalog, provisioning, and dynamic-import findings.

## 2. Problem and goal

### 2.1 One problem

The architecture checker currently discovers Python modules as mutable paths.
Its import-graph builder rereads those paths, its provider-policy check builds a
separate inventory and rereads source, and other architecture checks read some
of the same Python files again. A consumer can therefore combine module
membership from one filesystem observation with syntax or marker evidence from
another. The helper also leaves inventory semantics and import-root values as
separate mutable module state rather than returning one bound authority.

PR #283 exposed the material consequence. Its proposed temporal classifier
used one path mapping for membership, reread paths for graph and marker scans,
and executed repository modules for other observations. Different bytes could
therefore decide different parts of one conformance result, and checked code
could participate in deciding whether it passed.

### 2.2 Goal

This contract establishes one architecture-owned authority object that binds
source membership, exact retained bytes, parsed syntax, static graph semantics,
and exact root sets for one checker invocation. It makes source transitions
simple and reviewable:

```text
untrusted filesystem tree
-> authenticated source contract
-> validated single acquisition
-> immutable retained snapshot
-> deterministic read-only observations
```

The result is an architecture capability, not a temporal exception. Later
consumers may rely on it only under their own reviewed contracts.

## 3. Learning value

The change validates that multiple static conformance decisions can share one
retained repository-source authority without executing checked modules or
creating a second walker. It removes the demonstrated time-of-check/time-of-use
gap between source membership, parsed syntax, and import reachability, and it
makes semantic drift in roots or inventory rules an explicit contract event.

## 4. Non-goals

Neither this Phase A contract nor its future architecture Phase B will:

- edit PR #283 or make PR #283 mergeable;
- amend, reinterpret, approve, or implement the temporal candidate
  conformance selection-storage contract;
- scan for temporal identities, digests, carrier rows, migration markers, or
  selection markers;
- decide whether any temporal marker occurrence is allowed;
- define or enforce the temporal adapter's production or legacy isolation;
- define a new dynamic-import policy or expand the existing architecture
  checker's current dynamic-import vocabulary;
- prove the runtime value of `TENANT_CATALOG_VERIFIER_DIGEST`;
- compute a provisioning digest or define a static replacement for repository
  module execution;
- import or execute `deployment/postgresql` or `kernel` modules as evidence;
- create or edit a database schema, migration, adapter, role, grant, function,
  policy, row, tenant selection, or knowledge position;
- change `RuntimeBundle`, RuntimeBundle selection, profiles, active registries,
  semantic routes, commands, materialization, reads, outputs, deployment, or
  #192 behavior;
- alter the production-versus-legacy firewall's policy meaning;
- create a general repository snapshot service, daemon, cache, database,
  plugin system, file watcher, hot reload path, or network protocol;
- support historical source snapshots, multiple roots in one snapshot,
  incremental refresh, or snapshot merging; or
- amend frozen reference law, ADR 0002, or any active or candidate artifact.

The snapshot records a static AST graph. Dynamic loading is not represented as
an import edge. Any later consumer that needs a claim about dynamic loading
must obtain a reviewed policy for that consumer and inspect only detached AST
copies from this snapshot. Absence of a static edge is never proof that dynamic
loading is absent.

## 5. Exact source contract and authority map

### 5.1 Governing authority

The future Phase B implementation must authenticate the complete merged bytes
of this RFC before source acquisition. Its fixed constants must pin:

- contract identity;
- exact RFC path;
- complete merged-file UTF-8 byte length; and
- complete merged-file SHA-256.

Those complete-file values are known only after truthful approval publication.
The pre-publication design digest, status prose, PR state, GitHub review, merge,
branch, caller claim, or returned interface identity cannot substitute for the
complete merged RFC identity.

The implementation reads that authority only from the exact fixed RFC path
under its module-owned package root. The path and every component below that
root must be regular and non-symbolic-link, and the fixed path must identify
one file. Missing, aliased, multiply resolved, or inexact authority refuses
before the caller's source root is inventoried.

The accepted architecture context remains:

```text
reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md
96406 bytes
sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256
```

That report retains governance-before-automation and deterministic enforcement
law. This RFC does not amend it.

The exact problem baseline is:

```text
conformance/rewrite_architecture_check.py
28594 bytes
sha256:23c0584bdf0f0acdf89c7b80cb861f1a2515372affbb3f9b11fccf31637222c1
```

The baseline digest is review evidence, not a permanent implementation pin.
The separately approved temporal selection-storage contract remains:

```text
docs/rfcs/OFARM_Temporal_Candidate_Conformance_Selection_Storage_Admission_RFC_v0_1.md
62540 bytes
sha256:716a45927846d068f595f81288b8d29ecc07891bcaf848e0284eb91ece4abc8d
```

It is an unchanged dependent contract, not an authority that may edit this
architecture interface.

### 5.2 Exact immutable source-contract descriptor

Every successful snapshot carries one value-equal immutable descriptor with
exactly these reviewed fields:

| Field | Exact value |
| --- | --- |
| `interface_identity` | `ofarm.architecture-python-source-snapshot.v1` |
| `encoding` | `UTF-8-STRICT` |
| `included_suffix` | the string `".py"` |
| `excluded_component_exact` | the one-element tuple `("__pycache__",)` |
| `excluded_component_prefix` | the string `"."` |
| `module_naming` | `ROOT_RELATIVE_DOTTED_DROP_PY_AND_TERMINAL_INIT_V1` |
| `source_acquisition` | `ONE_DESCRIPTOR_BYTE_ACQUISITION_WITH_PRE_POST_INVENTORY_V1` |
| `graph_semantics` | `STATIC_AST_EXACT_KNOWN_MODULE_V1` |
| `production_import_roots` | ordered tuple `("kernel.api", "kernel.application_runtime")` |
| `legacy_import_roots` | ordered tuple `("kernel.legacy_m1.api", "kernel.legacy_m1.runtime")` |

No descriptor field is an argument to the builder. No caller, environment,
profile, request, route, configuration file, dynamically discovered registry,
module global changed after acquisition, or inventoried source file may choose
or widen it. The builder rejects rather than returning a snapshot with any
other value.

The descriptor is authenticated by the complete merged RFC bytes and enforced
by the architecture implementation and focused tests. It is not sufficient
for a later consumer merely to accept a returned identity string. A later
consumer must be authorized by its own contract, authenticate this complete
merged RFC identity, and compare every descriptor field and required root
value before using snapshot evidence.

### 5.3 Authority map

| Decision | Sole authority | Explicitly non-authoritative inputs |
| --- | --- | --- |
| Snapshot interface meaning | complete merged identity of this RFC | caller prose, PR state, interface self-claim |
| Source-tree location for the architecture checker | fixed `ROOT` passed by `rewrite_architecture_check.main()` | command line, environment, profile, route |
| Source-tree location in focused tests | explicit absolute temporary root passed directly to the builder | production authority or exception selection |
| Included source membership | section 6 inventory algorithm executed once under the fixed descriptor | directory order, module contents, importability |
| Module identity | section 6.3 naming rule applied to exact relative path | `__name__`, package metadata, module execution |
| Source evidence | exact bytes retained from the one descriptor byte acquisition | later path contents, imported module object |
| Parsed syntax | strict UTF-8 decode and `ast.parse` of retained bytes | a reparse of reread path contents |
| Static import graph | section 7 algorithm over the complete retained AST set | `sys.modules`, importlib, runtime imports |
| Production and legacy roots | exact ordered tuples in section 5.2 | caller, profile, mutable registry |
| Reachability | exact graph plus its exact fixed root tuple | caller-selected roots, runtime imports |
| Temporal marker and adapter policy | a later reviewed temporal-contract amendment | this snapshot and its passing tests |
| Catalog and provisioning meaning | their existing owners and a later temporal amendment | import or execution by this snapshot builder |

The old path-only `_module_sources` result and rereading `_import_graph` flow
must not remain as alternate authorities after the architecture Phase B. No
compatibility adapter may expose the old mutable path mapping to a production
consumer. Internal pure functions may remain only when they consume retained
records and cannot read a source path.

## 6. Source inventory and acquisition rules

### 6.1 Root rules

`build_python_source_snapshot` accepts one explicit `pathlib.Path`. The path
must be absolute, must name an existing directory, and must not itself be a
symbolic link. The builder preserves this lexical absolute root; it does not
resolve an alternate root into eligibility.

Production `rewrite_architecture_check.main()` passes only its module-owned
fixed `ROOT` and calls the builder once. The root parameter exists to retain the
current focused temporary-tree test seam. It is a location input, not authority
to change the source contract or root tuples. No runtime, route, request,
environment, profile, or command-line seam is added.

### 6.2 Closed inventory algorithm

The builder walks the root recursively in sorted root-relative POSIX-path order
without following symbolic links. It considers only entries whose leaf name
ends exactly in `.py`.

A relative path is excluded before source classification when any relative
component:

- equals `__pycache__`; or
- begins with `.`.

All other `.py` entries are in the candidate inventory. Each candidate must be
a regular non-symbolic-link file, every component below the root must be
non-symbolic-link, and no two included paths may identify the same device and
inode. A symbolic-link directory in an otherwise included namespace, a
symbolic-link `.py` file, a FIFO or device named `.py`, or a hard-linked second
Python path refuses the whole build. The builder never follows one into an
allowed source.

Files without the exact `.py` suffix are outside this snapshot. Their absence
from the inventory gives them no conformance allowance.

### 6.3 Exact module naming and uniqueness

For each included relative path:

1. remove the terminal `.py` suffix;
2. if the final remaining component is exactly `__init__`, remove it; and
3. join remaining components with `.` without changing case or characters.

An empty result or two relative paths producing the same module name refuses
the whole snapshot. The important collision is `package.py` with
`package/__init__.py`; neither may silently overwrite the other.

The builder does not import a path to verify that Python would import it. The
exact path-derived name is the only module identity in this static inventory.

### 6.4 One retained byte acquisition

The builder first records a complete pre-acquisition inventory fingerprint for
all included candidates. Each fingerprint contains at least the relative path,
entry kind, device, inode, size, modification time in nanoseconds, and change
time in nanoseconds.

It then opens each exact candidate without following a symbolic link, proves
from the open descriptor that it is the same regular device/inode recorded in
the pre-inventory, performs one sequential byte acquisition from that
descriptor through stable EOF, and proves from the descriptor's post-read
metadata that the source did not change during the acquisition. The sequential
acquisition may require multiple operating-system read calls; it may not reopen
or rewind the source. No text-mode path read is permitted.

After all bytes are retained, the builder performs one metadata-only
post-acquisition inventory validation. The ordered fingerprint set must equal
the pre-acquisition set exactly. This validation is not a second source
authority and reads no source bytes. It exists only to refuse membership,
identity, or metadata changes during acquisition.

Any open or stable-EOF failure, metadata mismatch, added or removed candidate,
renamed path, kind change, symlink substitution, hard-link alias, or pre/post
inventory mismatch refuses. No partial snapshot is returned.

The builder decodes each retained byte string once with strict UTF-8 and parses
that exact text once as
`ast.parse(source_text, filename=relative_path, mode="exec", type_comments=False, feature_version=None)`.
An invalid UTF-8 sequence or syntax error refuses the whole build. Byte length
is the exact retained byte count. The `sha256` field is the prefix `sha256:`
followed by 64 lowercase hexadecimal characters derived from the retained
bytes, not from a path or later read.

After acquisition, an ordinary local edit, deletion, rename, or replacement of
a source path cannot change the snapshot. A new builder call observes a new
tree and creates a distinct snapshot or refuses; snapshots are never refreshed
in place.

## 7. Parsed syntax, graph, and immutability

### 7.1 Retained module record

Each public module record is a frozen value containing:

```text
module_name
relative_path
source_bytes
source_text
byte_length
sha256
```

The two public lookup maps—module name to record and relative path to
record—are immutable and have no mutable backing alias retained by the
builder. Source bytes and text are immutable values.

The parsed `ast.Module` is retained privately by the snapshot. A consumer may
request only a detached deep copy for an exact module. Mutating that copy must
not alter the retained AST, import graph, reachability, later copies, or any
other snapshot value. A consumer may not provide a replacement AST.

Arbitrary hostile introspection or mutation of trusted checker process memory
is outside the trust model in section 8. Ordinary caller access through the
supported interface must not expose a mutable retained object.

### 7.2 Exact normalized static import graph

The graph contains one key for every retained module and an immutable sorted
tuple of unique edges for that module. Each edge contains exact target module
name and source line.

Graph derivation walks the retained AST only:

- `import X` creates an edge only when `X` exactly equals a retained module
  name;
- absolute `from X import Y` creates an edge to retained `X`, when present,
  and to retained `X.Y`, when present;
- relative `from` imports derive their base as follows: split the source module
  name on `.`, remove its final component unless the source leaf is exactly
  `__init__.py`, calculate `keep = len(package_parts) - level + 1`, use an
  empty base when `keep < 0`, otherwise retain the first `keep` package parts,
  and append `node.module` parts when present; then apply the same
  exact-known-name rules to the base and each `base.alias` candidate;
- repeated equal `(target, line)` edges are deduplicated; and
- edges sort first by source line and then by target name.

The graph is static syntax evidence. Imports nested under functions, classes,
or `TYPE_CHECKING` are included because the AST contains them. Calls to
`importlib`, `__import__`, `exec`, reflection, plugin registries, or computed
module names do not create guessed edges. They remain visible in detached AST
copies for a separately governed policy.

### 7.3 Fixed reachability products

The snapshot derives breadth-first paths separately from the exact production
and legacy root tuples. A root present in the graph has the one-element path to
itself. A missing root produces no invented node. Each module retains the first
path discovered under graph edge order. Both reachability maps are immutable.

The snapshot does not claim that a missing fixed root is acceptable. The
architecture checker and any later governed consumer own their own required
root-presence rules. A consumer may not substitute a caller-selected root set
and call that result the snapshot's production or legacy closure.

## 8. Trust model

### 8.1 Protected assets

The protected assets are:

- completeness and uniqueness of the Python-source inventory;
- identity of the exact bytes used for every observation;
- agreement between retained bytes, parsed syntax, graph, and reachability;
- exact production and legacy root semantics;
- the production-versus-legacy firewall's existing closed surface; and
- separation between checked repository code and the checker authority that
  decides whether it passes.

### 8.2 Trusted components

Trusted components are the exact approved and complete merged contract, the
future reviewed architecture implementation, trusted Python and standard
library implementations, operating-system file-descriptor and metadata
semantics, SHA-256, and the checker process before it handles untrusted source
bytes.

### 8.3 Untrusted inputs and actors

Repository Python bytes, filenames, directory order, symlinks, hard links,
invalid text, invalid syntax, import statements, module-level code, runtime
self-description, and the caller-supplied source-tree location are untrusted.
They may cause a retained snapshot or a refusal. They cannot choose inventory
semantics, root tuples, exceptions, or contract identity.

An ordinary contributor may add, remove, rename, or edit repository files.
Those changes are in scope and must be captured consistently or refused. Local
source substitution before acquisition is in scope. Ordinary mutation during
acquisition is in scope when it changes the candidate inventory, file identity,
kind, size, modification time, change time, or descriptor state. Mutation after
sealing is in scope and must not alter the returned snapshot.

### 8.4 Explicitly excluded compromise capabilities

Compromise of Python, the operating system, SHA-256, trusted dependencies, the
checker implementation, the designated architect, or repository review and
release custody is outside this static boundary. Arbitrary hostile in-process
memory mutation, kernel-level metadata forgery, and an attacker that changes
and restores source plus all observed file identities and nanosecond metadata
during one acquisition are also outside scope.

These exclusions do not permit repository modules to execute, mutate checker
state, select roots, provide digests, or self-attest through ordinary Python
interfaces.

## 9. State machine and ordering

The only externally observable terminal states are `SEALED` and `REFUSED`.
Internal acquisition ordering is:

```text
UNBUILT
-> CONTRACT_AUTHENTICATED
-> ROOT_VALIDATED
-> PRE_INVENTORY_FIXED
-> BYTES_RETAINED
-> POST_INVENTORY_MATCHED
-> TEXT_AND_AST_DERIVED
-> GRAPH_AND_REACHABILITY_DERIVED
-> SEALED
```

Any failure transitions directly to `REFUSED`. `REFUSED` and `SEALED` are
terminal. The builder returns exactly one complete `PythonSourceSnapshotV1`
only at `SEALED`; it returns no partial inventory, module record, AST, graph, or
closure at any earlier state.

Contract authentication happens before inspecting the caller root. All source
bytes are retained and the inventory is revalidated before parsing or graph
derivation. Graph and reachability are derived before public exposure. Sealing
removes every mutable construction alias.

The builder's only side effects are bounded filesystem reads and allocation of
in-process immutable evidence. It creates no file, cache, registry entry,
database row, import, module object, network call, subprocess, or runtime
activation.

Refusal uses one architecture-owned typed exception carrying a stable refusal
category and optional relative path. The exact human diagnostic wording is not
governed. Categories must distinguish at least contract mismatch, invalid
root, forbidden link or file kind, duplicate file identity, duplicate or empty
module identity, read or inventory change, invalid UTF-8, and invalid syntax.

## 10. Invariants and acceptance criteria

- **APSS-001 — Complete contract first.** No snapshot acquisition begins until
  the complete merged RFC path, byte length, and SHA-256 authenticate exactly.
- **APSS-002 — Fixed descriptor.** Every sealed snapshot carries the exact
  descriptor in section 5.2; callers cannot supply or alter any descriptor
  field or either root tuple.
- **APSS-003 — Closed inventory.** Membership follows only section 6.2;
  excluded components are absent, included regular `.py` sources are complete,
  and aliases, links, non-regular candidates, empty names, or collisions
  refuse.
- **APSS-004 — One byte authority.** Each included source is read to EOF once
  from one validated descriptor. Retained bytes alone own text, length, digest,
  AST, graph, reachability, and later source observations.
- **APSS-005 — Acquisition consistency.** Any observed source or inventory
  change between the pre-inventory and post-inventory refuses without a
  partial snapshot.
- **APSS-006 — No checked-code execution.** Building or consuming a snapshot
  never imports, executes, evaluates, compiles to executable bytecode, or loads
  an inventoried module.
- **APSS-007 — Immutable public authority.** Public records, lookups, graph,
  roots, and reachability are immutable; returned ASTs are detached copies and
  cannot change retained state.
- **APSS-008 — Deterministic static graph.** Equal retained module records
  produce equal normalized graph and reachability values under section 7,
  independent of directory order, `sys.path`, `sys.modules`, or runtime import
  behavior.
- **APSS-009 — One architecture snapshot per run.** The supported architecture
  checker entry point constructs one snapshot and supplies it to every Python
  source, AST, line-count, provider-policy, firewall, graph, and reachability
  observation in that run. No such observation rereads a Python path.
- **APSS-010 — Old authorities removed.** The path-only `_module_sources`
  result and any graph builder that reads paths are absent after Phase B; no
  compatibility seam or second Python walker remains.
- **APSS-011 — Static evidence is not runtime proof.** The snapshot never
  presents absence of a static edge as absence of dynamic loading and never
  presents retained source as catalog, provisioning, temporal, selection, or
  runtime authority.
- **APSS-012 — Production/legacy policy preserved.** The exact root tuples are
  bound into the snapshot, but their existing firewall meaning is not widened,
  weakened, or moved to a temporal owner by this boundary.
- **APSS-013 — Closed semantic and runtime surface.** No database, migration,
  adapter, RuntimeBundle, profile, route, command, materialization, read,
  output, deployment, legacy behavior, or #192 authority changes.
- **APSS-014 — Fail closed on expansion.** A needed second root, alternate
  encoding, new inventory class, dynamic-import classifier, temporal exception,
  catalog rule, provisioning rule, or file outside the Phase B allowlist stops
  for its owning reviewed contract.

## 11. Required negative cases

The future architecture Phase B must prove these cases through the supported
builder or architecture-checker entry point and ordinary temporary filesystem
fixtures. Tests do not manufacture authority by mutating private snapshot
state.

| Case | Required result |
| --- | --- |
| The complete merged RFC is missing, length-mismatched, digest-mismatched, substituted, or multiply resolved | refuse before root inventory |
| A caller attempts to pass encoding, inventory rules, graph rules, production roots, or legacy roots | the closed builder API accepts no such argument |
| A successful snapshot is inspected | every descriptor field and both ordered root tuples equal section 5.2 exactly |
| Root is relative, missing, not a directory, or itself a symlink | refuse without following or normalizing it into eligibility |
| A regular `.py` file exists in an included ordinary directory | include it exactly once under its derived module and relative path |
| A `.py` file is under a component beginning `.` or equal to `__pycache__` | exclude it; it creates no module or edge |
| A `.py` file is under `kernel/tests` or `profile_si_ffs/tests` | include it; this interface has no test-family exception |
| An included directory component or `.py` leaf is a symlink | refuse the snapshot without following it |
| An included `.py` path is a FIFO, device, socket, or other non-regular entry | refuse |
| Two included `.py` paths are hard links to one device/inode | refuse the duplicate source identity |
| `package.py` and `package/__init__.py` coexist | refuse the duplicate module name instead of overwriting |
| A root-level `__init__.py` produces an empty module name | refuse |
| A source is invalid UTF-8 | refuse with no graph or partial inventory |
| A source is valid UTF-8 but invalid Python syntax | refuse with no graph or partial inventory |
| A candidate is added, removed, renamed, relinked, or observably edited during acquisition | pre/post mismatch refuses |
| A source path is edited, deleted, or replaced after `SEALED` | retained bytes, text, digest, AST copies, graph, and reachability remain unchanged |
| A caller attempts to mutate a lookup, module record, graph edge tuple, root tuple, or reachability path | mutation is unavailable or refused |
| A caller mutates a returned AST copy and requests another copy | the later copy and all snapshot-derived values remain unchanged |
| Two trees have equal retained bytes and paths but different directory enumeration order | normalized records, graph, and reachability are equal |
| A source uses absolute and relative static imports, including repeated imports | only exact known-module edges appear, deduplicated and sorted as section 7.2 requires |
| A source contains `importlib`, `__import__`, `exec`, reflection, or a computed module name | builder does not execute it and does not invent a static edge; the syntax remains available to a separate policy through a detached AST copy |
| A module raises at import time or would write a sentinel if imported | snapshot succeeds when syntax is valid and no sentinel or module execution occurs |
| `sys.path` or `sys.modules` contains a competing module name | retained inventory and graph remain path/AST-derived and unchanged |
| The architecture checker runs its complete supported entry point | exactly one snapshot supplies all Python source and AST observations |
| A proposed implementation retains `_module_sources` or rereads a path for graph, line count, provider policy, or firewall checks | refuse the implementation as duplicate authority |
| A consumer treats a missing static edge as proof that dynamic import is absent | invalid claim; stop for that consumer's policy contract |
| A temporal checker, catalog check, or provisioning check tries to consume this interface without its own reviewed amendment | stop; this contract grants no such authority |

## 12. Proposed architecture and smallest coherent change

### 12.1 Types and composition

The future implementation adds only the minimum bound values needed by the
decision:

- one frozen source-contract descriptor;
- one frozen public module record;
- one frozen edge value;
- one sealed `PythonSourceSnapshotV1` with immutable lookups and private AST
  custody;
- one typed refusal; and
- one builder function.

`rewrite_architecture_check.main()` constructs one snapshot, then passes that
bound object through existing checks. Existing source consumers use record
text, record bytes, line counts derived from record text, or detached AST
copies. Existing provider and firewall checks consume the snapshot's graph and
fixed reachability products. Focused temporary-tree tests call the same builder
through the existing test seams.

The implementation deletes `_module_sources` and the path-reading form of
`_import_graph`. It does not retain a compatibility dictionary of paths. A
small internal pure graph or breadth-first helper may remain only behind the
builder and only over retained immutable values.

### 12.2 Why this is the smallest coherent change

Returning only bytes would leave callers to duplicate parsing and graph rules.
Returning only an AST would omit exact byte and digest evidence. Returning
correlated dictionaries would leave roots and membership separable. One bound
snapshot removes all three failure modes with one construction and one
transition to sealed state.

A service, cache, database, generic policy engine, file-watcher abstraction,
or cross-repository framework would add authority and lifecycle without solving
the reviewed issue more directly. A local architecture object is sufficient.

### 12.3 Elegance audit

- Authoritative source contracts: one complete merged RFC.
- Authoritative acquisition transitions: one builder call per checker run.
- Authoritative source-byte values: one retained byte string per module.
- Authoritative graph: one derivation inside the builder.
- Authoritative production and legacy root sets: one fixed descriptor.
- Mutable global registries introduced: zero.
- Alternate walkers or path readers retained: zero.
- Runtime or temporal authorities introduced: zero.

The old path-only mapping and path-reading graph helper can be deleted. A clean
replacement of that small helper cluster is clearer than layering a new reader
beside it. Existing policy visitors remain because this contract does not
change what they mean.

## 13. Pull request boundaries and stop conditions

### 13.1 This Phase A PR

This proposal changes only:

```text
docs/rfcs/OFARM_Architecture_Python_Source_Snapshot_Admission_RFC_v0_1.md
```

Before approval it remains proposed and unapproved. After exact approval under
section 15, the same one-file documentation PR may change only truthful status
metadata and append one complete approval record. It may not contain code,
tests, temporal amendments, or generated inventory changes.

### 13.2 Future architecture Phase B

Only after this exact contract is approved, truthfully published, merged, and
followed by a separate explicit implementation request may one architecture
Phase B change:

```text
conformance/rewrite_architecture_check.py
kernel/tests/test_rewrite_architecture_check.py
conformance/review_baseline_test_inventory.json
```

The inventory file may change only when mechanically required by a change to
the canonical collected test-node inventory, including a count or node-ID
change.

No other file is allowed. If the interface requires a schema, manifest,
registry, second module, package-checker edit, temporal checker edit, database
file, runtime file, or additional test family, Phase B stops for an amended or
separate contract.

### 13.3 Later temporal work

Architecture Phase B does not satisfy or amend the temporal contract. After it
merges, later work must proceed in this order:

```text
authenticate the merged architecture implementation and contract
-> draft a versioned temporal selection-storage contract amendment
-> replace the private-helper coupling in that contract
-> decide exhaustive catalog and provisioning observations
-> decide dynamic-import refusal for both fixed closures and the package initializer
-> obtain exact architect approval
-> resume a separately requested temporal Phase B
```

PR #283 is not the architecture Phase B and remains stopped. Whether it is
amended, replaced, or closed is a later temporal-owner decision.

### 13.4 Stop conditions

Work stops before:

1. implementing architecture Phase B without exact architect approval,
   truthful publication, merge, and a separate explicit implementation
   request;
2. editing PR #283 or the temporal selection-storage RFC in this boundary;
3. adding caller-selected source semantics, roots, policies, exclusions, or
   exceptions;
4. retaining a second Python walker, path reread, importlib loader, module
   execution path, or mutable snapshot authority;
5. defining a temporal marker rule, catalog binding rule, provisioning rule,
   or dynamic-import policy;
6. changing production or legacy firewall meaning instead of only its source
   authority;
7. changing a database, migration, adapter, RuntimeBundle, profile, active
   registry, route, command, read, output, deployment, legacy behavior, or
   #192 authority;
8. changing frozen reference law, ADR 0002, a candidate artifact, ERRATA,
   manifest, digest, or lifecycle decision; or
9. editing any file outside the applicable Phase A or Phase B allowlist.

Each stopped item requires its owning reviewed boundary. No cross-boundary
review fix may be appended merely to clear PR #283.

## 14. Verification and traceability

### 14.1 Phase A verification

This documentation-only contract requires:

```text
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --name-only origin/main...HEAD
```

The final command must name only this RFC.

### 14.2 Future architecture Phase B verification

Minimum verification is:

```text
python3 -m pytest -q kernel/tests/test_rewrite_architecture_check.py
python3 conformance/rewrite_architecture_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

The Phase B handoff must show that only its three allowed files changed and
must state whether canonical test inventory changed by count, node ID, or both.

### 14.3 Traceability

| Invariant | Owning future seam | Negative evidence | Smallest verification |
| --- | --- | --- | --- |
| APSS-001 | fixed RFC authentication before builder acquisition | missing, length mismatch, same-length digest mismatch, substitution | focused contract-authentication tests and package check |
| APSS-002 | fixed descriptor constructed internally | caller attempts alternate encoding, rules, or roots; exact returned-value checks | focused API and descriptor tests |
| APSS-003 | one closed inventory and naming implementation | hidden/cache exclusions, ordinary test inclusion, symlink, FIFO, hard link, empty name, collision | temporary-tree inventory tests |
| APSS-004, APSS-005 | descriptor byte acquisition and pre/post fingerprints | path mutation after sealing; observable mutation during acquisition refuses | retained-evidence and acquisition-refusal tests plus code review |
| APSS-006 | builder with no import or execution seam | import-time raise and sentinel-writing module remain unexecuted | focused no-execution test |
| APSS-007 | frozen records, immutable maps, private AST custody | mapping mutation and returned-AST mutation cannot alter snapshot | focused immutability tests |
| APSS-008 | one graph and reachability derivation | relative/absolute/repeated imports, directory order, competing `sys.modules` | focused deterministic graph tests |
| APSS-009, APSS-010 | `main()` composition and deleted path readers | complete checker uses one snapshot; path-reading helpers absent | focused composition test, source review, architecture check |
| APSS-011 | explicit static-only interface | dynamic forms create no guessed edge or runtime claim | focused static-boundary test and later consumer stop |
| APSS-012 | exact root tuple fields and unchanged policy visitors | altered/missing root values refuse consumer use; existing firewall cases remain green | descriptor tests and existing architecture tests |
| APSS-013, APSS-014 | exact changed-file allowlist | any runtime, temporal, database, legacy, or #192 file changes | boundary diff and package check |

## 15. Byte-authenticated approval and publication

This document is a proposal, not an approved contract. PR authorship, commit
authorship, branch state, review conclusions, GitHub comments, reviews,
reactions, repository credentials, mergeability, green checks, or merge do not
approve it.

Before any implementation, the AI must display one complete plain-English
decision card in Codex task
`019fa821-93c9-7ef1-8c94-1c0e92ea46b9`. The card must identify the exact
canonical design bytes, their byte length and SHA-256, this contract and
interface identity, trust boundary, decision, effects, non-effects,
invariants, negative cases, Phase B allowlist, stop conditions, verification,
and the exact approval sentence.

The designated architect must then send that exact sentence as a later
user-authored message in the same task. It may be typed or copied directly from
the complete live card displayed earlier in that task. An approval sentence or
card digest from another task, another card, another decision, documentation,
a template, a PR, GitHub, or AI-authored or AI-sent text other than that
complete live card is invalid.

Only after the exact user-authored approval exists may the one-file Phase A PR
truthfully change status and append one approval record. The record must bind
the task reference, stable card and approval references, exact approved design
byte length and digest, exact approval sentence and digest, contract and
interface identities, reviewed head, timestamp, permitted effect, non-effects,
and next required sequence. The record is evidence of the architect's decision;
it is not a substitute for it.

Publication may change only the truthful status metadata and append that one
record. The approved decision, source contract, trust model, authority map,
inventory and acquisition rules, graph rules, state machine, invariants,
negative cases, architecture, non-goals, verification, PR boundaries, stop
conditions, and merge-stop rule must otherwise remain byte-for-byte unchanged.
Any substantive correction requires new canonical design bytes, a new live
card, and a new exact approval.

This Codex approval workflow is provisional and pre-deployment. Before
deployment, it must be replaced by an independently human-controlled and
independently verifiable signing or approval system.

## 16. Provisional design record, review disposition, and merge stop

### Provisional design record

The snapshot architecture is **not provisional**. It is a versioned static
checker interface with explicit replacement through a later reviewed version.
The pre-deployment Codex approval transport is provisional only as stated in
section 15.

Evidence requiring a contract revision includes an operating environment that
cannot provide the stated descriptor and file-identity checks, a demonstrated
need for a different Python encoding, a required second source root, or a
consumer that needs semantics beyond retained bytes, AST, static graph, and
fixed reachability. The upgrade path is a new versioned architecture contract,
not a silent change under the v1 identity.

### Open decisions

None. The contract intentionally leaves temporal catalog, provisioning,
dynamic-import, and marker decisions to the later temporal amendment.

### Review disposition

- **Blockers:** explicit architect approval of the exact canonical design has
  not yet occurred.
- **Follow-ups:** architecture Phase B after approval and publication; then a
  separate temporal selection-storage contract amendment before PR #283 may
  resume or be replaced.
- **Preferences:** none recorded.

### Merge stop rule

Before approval, this proposal must not merge. After exact approval and
truthful one-file publication, once the Phase A acceptance criteria pass and no
demonstrated in-scope Blocker remains, merge the documentation PR. New ideas,
Preferences, and non-blocking hardening become Follow-ups and do not reopen
review.

Architecture Phase B remains separately blocked until the merged contract is
authenticated and the user gives a separate explicit implementation request.
