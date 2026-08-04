<!-- BEGIN OFARM2 ARCHITECTURE PYTHON SOURCE SNAPSHOT PHASE A DESIGN -->
# OFARM2 Architecture Python Source Snapshot Admission — Phase A Contract v0.1

**Status:** proposed Phase A contract; documentation-only and unapproved

**Contract identity:**
`ofarm.architecture-python-source-snapshot-admission.issue176.v0.1`

**Snapshot interface identity:**
`ofarm.architecture-python-source-snapshot.v1`

**Reviewed base:** `b81fd35aa88ae57172c9c68688367dd3a584e0be`

**RFC path:**
`docs/rfcs/OFARM_Architecture_Python_Source_Snapshot_Admission_RFC_v0_1.md`

**Date:** 2026-08-04

**Primary ticket:** #176

**Review evidence:** PR #283 review `4847814084` at
`9ee9f6856bafd26cfef6914074bffc230bb0c599`, and PR #284 review
`4850399233` at `5688cec0d17bacbdbb0adbef1fea0931673c25d5`

**Primary trust boundary:** architecture-checker ownership and integrity of the
repository Python-source inventory, retained source evidence, parsed syntax,
static import graph, and fixed production and legacy root sets

**Phase A PR boundary:** this RFC only

**Future B1 architecture PR boundary:**
`conformance/rewrite_architecture_check.py`, its focused existing test module,
and canonical test-inventory metadata only when mechanically required

## 1. Decision

After the designated architect explicitly approves this exact contract and a
documentation-only publication truthfully records that approval, one separate
architecture-owned B1 implementation may add exactly one versioned,
contract-authenticated Python-source snapshot to
`conformance/rewrite_architecture_check.py`.

The supported builder is exactly:

```python
def build_python_source_snapshot(
    root: pathlib.Path,
) -> PythonSourceSnapshotV1:
    ...
```

The caller supplies only the lexical absolute source-tree location. The caller
does not supply the source contract, execution profile, inventory rules, module
naming rules, encoding, graph rules, resource limits, production roots, legacy
roots, or any exception. Those values are fixed by this reviewed v1 descriptor.

A successful snapshot exposes exactly the public authority surface in section
5. It binds:

- this contract's complete merged authority;
- the exact v1 descriptor and execution profile;
- one validated lexical root;
- one closed Python-source inventory;
- every retained source's exact bytes, strict UTF-8 text, byte length, digest,
  path identity, and bounded syntax measurements;
- one privately retained parsed AST per source;
- one normalized static import graph derived only from those ASTs;
- the exact production and legacy root tuples; and
- one deterministic reachability map for each fixed root tuple.

The builder does not execute, import, evaluate, compile to executable bytecode,
or otherwise ask an inventoried repository module to describe itself. Once
sealed, paths are evidence of origin only. Every architecture observation in
that checker invocation uses retained data or a bounded detached AST copy; it
does not reread a Python path.

B1 also migrates the architecture checker's own Python observations to the
sealed snapshot. It temporarily preserves the two exact private adapter names
required by current merged consumers, but changes them so neither returns a
path mapping nor rereads source bytes. Section 12 defines this staged custody
precisely.

This contract does not authorize PR #283 to resume and does not amend the
temporal selection-storage contract. A later temporal-owner contract must
migrate the two current external consumers and close the separate catalog,
provisioning, and dynamic-import findings. Only after both external consumers
are gone may a later architecture cleanup remove the temporary adapters.

## 2. Problem and goal

### 2.1 One problem

The architecture checker currently discovers Python modules as mutable paths.
Its graph builder rereads those paths; provider policy builds another inventory
and rereads source; and other architecture checks read some sources again.
Inventory membership, syntax, line counts, policy scans, and reachability can
therefore come from different filesystem observations. Inventory semantics and
root tuples also remain separable module globals rather than one bound value.

PR #283 exposed the material consequence. Its proposed temporal classifier
combined a path inventory, later graph and marker reads, and execution of four
repository modules. Different bytes could decide different parts of one
conformance result, and checked code could participate in deciding whether it
passed.

Current `main` also proves why replacement must be staged. These exact external
consumers call the private architecture helper chain:

```text
conformance/temporal_contract_candidate_check.py
kernel/tests/test_temporal_carriers.py
```

Deleting the helpers in B1 would break the mandatory package check before the
later temporal amendment could lawfully migrate them.

### 2.2 Goal

This contract establishes one architecture-owned authority object that binds
source membership, retained bytes, parsed syntax, graph semantics, fixed root
sets, deterministic reachability, and resource bounds for one checker
invocation. The transition is:

```text
untrusted filesystem tree
-> authenticated v1 contract and execution profile
-> bounded validated acquisition
-> sealed retained snapshot
-> deterministic read-only observations
```

The result is an architecture capability, not a temporal exception. A later
consumer may rely on it only under its own reviewed contract.

## 3. Learning value

The change proves that multiple static conformance decisions can share one
retained repository-source authority without executing checked modules or
creating a second walker. It removes the demonstrated time-of-check/time-of-use
gap and turns drift in source semantics, execution profile, limits, or roots
into an explicit versioned contract event.

## 4. Non-goals

Neither this Phase A contract nor architecture B1 will:

- edit PR #283 or make PR #283 mergeable;
- edit either current external consumer named in section 2;
- amend or implement the temporal selection-storage contract;
- scan for temporal identities, digests, carrier rows, migration markers, or
  selection markers;
- decide whether a temporal marker occurrence is allowed;
- define the temporal adapter's production or legacy isolation policy;
- define a new dynamic-import policy or widen the current architecture
  checker's dynamic-import vocabulary;
- prove the runtime value of `TENANT_CATALOG_VERIFIER_DIGEST`;
- compute a provisioning digest or define the later static replacement for
  repository module execution;
- import or execute `deployment/postgresql` or `kernel` modules as evidence;
- create or edit a database schema, migration, adapter, role, grant, function,
  policy, row, tenant selection, or knowledge position;
- change RuntimeBundle selection, profiles, active registries, semantic routes,
  commands, materialization, reads, outputs, deployment, or #192 behavior;
- change the production-versus-legacy firewall's policy meaning;
- create a service, daemon, cache, database, generic policy engine, plugin
  system, file watcher, hot reload path, or network protocol;
- support historical snapshots, multiple roots in one snapshot, incremental
  refresh, or snapshot merging; or
- amend frozen reference law, ADR 0002, or any active or candidate artifact.

The graph is static AST evidence. Dynamic loading does not create a guessed
edge. Any later consumer that needs a claim about dynamic loading must obtain a
reviewed policy and scan only retained AST evidence. Absence of a static edge
is never proof that dynamic loading is absent.

## 5. Closed public v1 interface and authority map

### 5.1 Governing contract authority

Before checking the execution profile or caller root, B1 must authenticate the
complete merged bytes of this RFC at the exact fixed path under the
architecture module's package root. B1 constants pin:

- contract identity;
- exact RFC path;
- complete merged-file UTF-8 byte length; and
- complete merged-file SHA-256.

Those complete-file values are established only after exact approval,
publication re-review, and merge. The approved pre-publication design digest,
status prose, returned interface identity, PR state, GitHub activity, caller
claim, or branch state cannot substitute for the complete merged identity.

Custody of that authority path uses the same descriptor-relative, no-follow
filesystem profile as source acquisition. The architecture package root is the
lexical absolute `Path(__file__).parent.parent` supplied by exact CPython; it
must already be absolute and is never passed through `resolve()` or realpath.
Its ancestors are opened from the filesystem anchor under section 6.3. Every
component below the retained package-root descriptor is a real directory
except the final RFC target, which is one regular file. No component may be a
symbolic link. A missing, aliased, multiply resolved, non-regular, or inexact
authority refuses before the caller root is inspected.

The accepted architecture context remains:

```text
reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md
96406 bytes
sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256
```

The exact problem baseline is review evidence, not a permanent source pin:

```text
conformance/rewrite_architecture_check.py
28594 bytes
sha256:23c0584bdf0f0acdf89c7b80cb861f1a2515372affbb3f9b11fccf31637222c1
```

The unchanged dependent temporal contract remains:

```text
docs/rfcs/OFARM_Temporal_Candidate_Conformance_Selection_Storage_Admission_RFC_v0_1.md
62540 bytes
sha256:716a45927846d068f595f81288b8d29ecc07891bcaf848e0284eb91ece4abc8d
```

It grants no authority to edit this interface and is not amended here.

### 5.2 Exact public types

The public v1 authority-bearing schema is closed to these names and signatures:

```python
class PythonSourceSnapshotRefusalCodeV1(str, enum.Enum): ...

class PythonSourceSnapshotRefusal(RuntimeError):
    code: PythonSourceSnapshotRefusalCodeV1
    relative_path: str | None

    def __init__(
        self,
        code: PythonSourceSnapshotRefusalCodeV1,
        relative_path: str | None = None,
    ) -> None: ...

@dataclasses.dataclass(frozen=True, slots=True)
class PythonSourceSnapshotDescriptorV1:
    interface_identity: str
    python_implementation: str
    python_version: tuple[int, int, int]
    ast_feature_version: tuple[int, int]
    filesystem_profile: str
    encoding: str
    included_suffix: str
    excluded_component_exact: tuple[str, ...]
    excluded_component_prefix: str
    module_naming: str
    source_acquisition: str
    graph_semantics: str
    production_import_roots: tuple[str, ...]
    legacy_import_roots: tuple[str, ...]
    maximum_source_files: int
    maximum_source_bytes_per_file: int
    maximum_total_source_bytes: int
    maximum_relative_path_bytes: int
    maximum_ast_nodes_per_file: int
    maximum_total_ast_nodes: int
    maximum_ast_depth: int
    maximum_import_edges_per_module: int
    maximum_total_import_edges: int
    maximum_ast_copy_calls: int

@dataclasses.dataclass(frozen=True, slots=True)
class PythonSourceContractAuthorityV1:
    contract_identity: str
    rfc_relative_path: str
    byte_length: int
    sha256: str

@dataclasses.dataclass(frozen=True, slots=True)
class PythonSourceUnitV1:
    module_name: str
    relative_path: str
    source_bytes: bytes
    source_text: str
    byte_length: int
    sha256: str
    ast_node_count: int
    ast_depth: int

@dataclasses.dataclass(frozen=True, slots=True, order=True)
class PythonImportEdgeV1:
    line: int
    target: str

class PythonSourceSnapshotV1:
    descriptor: PythonSourceSnapshotDescriptorV1
    contract_authority: PythonSourceContractAuthorityV1
    root_path: pathlib.Path
    modules_by_name: collections.abc.Mapping[str, PythonSourceUnitV1]
    modules_by_relative_path: collections.abc.Mapping[str, PythonSourceUnitV1]
    import_graph: collections.abc.Mapping[
        str, tuple[PythonImportEdgeV1, ...]
    ]
    production_reachability: collections.abc.Mapping[
        str, tuple[str, ...]
    ]
    legacy_reachability: collections.abc.Mapping[str, tuple[str, ...]]
    source_file_count: int
    total_source_bytes: int
    total_ast_nodes: int
    total_import_edges: int
    content_sha256: str

    def ast_for(self, module_name: str) -> ast.Module: ...

def build_python_source_snapshot(
    root: pathlib.Path,
) -> PythonSourceSnapshotV1: ...
```

Every listed snapshot attribute is a read-only property or a frozen value.
Both module maps, the graph map, and both reachability maps are
`types.MappingProxyType` views over construction dictionaries whose mutable
aliases are discarded before sealing. Map keys and relative paths are strings;
paths always use `/`. Graph edges and reachability paths are tuples.

The snapshot retains parsed ASTs only in a private mapping. `ast_for` accepts
exactly one `str` module name, raises `KeyError(module_name)` without consuming
copy budget when the name is unknown, and otherwise returns
`copy.deepcopy` of that module's retained `ast.Module`. The copy may be mutated
without changing later copies or any snapshot value. Each successful call
consumes one private, non-authoritative copy-budget unit. Call 513 refuses with
`AST_COPY_LIMIT_EXCEEDED`; failed lookups consume none. The private count does
not enter equality, content digest, or source authority and cannot change a
record, graph, root, or reachability value.

No other public authority-bearing field, map, accessor, constructor argument,
refusal code, or alias is permitted under v1. Diagnostic `__str__` or `__repr__`
text is non-authoritative. Caller-constructed lookalikes and subclasses are not
builder evidence.

### 5.3 Exact descriptor fields and values

Every successful snapshot carries one structurally equal frozen descriptor
with exactly these fields and values:

| Field | Exact v1 value |
| --- | --- |
| `interface_identity` | `ofarm.architecture-python-source-snapshot.v1` |
| `python_implementation` | `CPython` |
| `python_version` | `(3, 12, 13)` |
| `ast_feature_version` | `(3, 12)` |
| `filesystem_profile` | `POSIX_DESCRIPTOR_RELATIVE_NOFOLLOW_STAT_NS_V1` |
| `encoding` | `UTF-8-STRICT` |
| `included_suffix` | `.py` |
| `excluded_component_exact` | `("__pycache__",)` |
| `excluded_component_prefix` | `.` |
| `module_naming` | `ROOT_RELATIVE_DOTTED_DROP_PY_AND_TERMINAL_INIT_V1` |
| `source_acquisition` | `ONE_DESCRIPTOR_BYTE_ACQUISITION_WITH_PRE_POST_INVENTORY_V1` |
| `graph_semantics` | `STATIC_AST_EXACT_KNOWN_MODULE_V1` |
| `production_import_roots` | `("kernel.api", "kernel.application_runtime")` |
| `legacy_import_roots` | `("kernel.legacy_m1.api", "kernel.legacy_m1.runtime")` |
| `maximum_source_files` | `512` |
| `maximum_source_bytes_per_file` | `524288` |
| `maximum_total_source_bytes` | `8388608` |
| `maximum_relative_path_bytes` | `256` |
| `maximum_ast_nodes_per_file` | `65536` |
| `maximum_total_ast_nodes` | `1048576` |
| `maximum_ast_depth` | `64` |
| `maximum_import_edges_per_module` | `128` |
| `maximum_total_import_edges` | `4096` |
| `maximum_ast_copy_calls` | `512` |

No descriptor field is a builder argument. A caller, environment, profile,
request, route, configuration file, repository module, dynamic registry, or
mutable compatibility alias cannot select or widen a value.

### 5.4 Closed refusal codes

`PythonSourceSnapshotRefusalCodeV1` contains exactly:

```text
CONTRACT_AUTHORITY_MISMATCH
UNSUPPORTED_PYTHON_IMPLEMENTATION
UNSUPPORTED_PYTHON_VERSION
UNSUPPORTED_AST_FEATURE_VERSION
UNSUPPORTED_FILESYSTEM_PROFILE
INVALID_ROOT
SYMLINK_COMPONENT
NON_DIRECTORY_COMPONENT
NON_REGULAR_SOURCE
DUPLICATE_FILE_IDENTITY
EMPTY_MODULE_NAME
DUPLICATE_MODULE_NAME
SOURCE_ACQUISITION_FAILED
SOURCE_CHANGED
INVENTORY_CHANGED
INVALID_UTF8
INVALID_PYTHON_SYNTAX
MISSING_REQUIRED_IMPORT_ROOT
RESOURCE_LIMIT_EXCEEDED
AST_COPY_LIMIT_EXCEEDED
UNSUPPORTED_REACHABILITY_ROOTS
```

`PythonSourceSnapshotRefusal` is the sole governed refusal exception. Its
constructor accepts exactly `code` and optional root-relative POSIX
`relative_path`. Human diagnostic text is not authority. Expected untrusted
input failures, `UnicodeDecodeError`, `SyntaxError`, bounded `MemoryError`, and
bounded `RecursionError` are translated to this closed enum. A trusted-code bug
is not relabelled as an input refusal.

Every enum member's string value is exactly its listed uppercase name.

Adding or renaming a public field, method, type, descriptor field, or refusal
code requires a reviewed v2 or a reviewed v1 amendment before implementation.

### 5.5 Equality and digest rules

Frozen descriptor, contract-authority, source-unit, and import-edge equality is
ordinary exact dataclass structural equality. `PythonSourceSnapshotV1`
equality compares every public field above except the private AST-copy counter;
it compares source bytes and text, not only digests. A snapshot is unhashable.
The private AST mapping is not compared separately because the exact execution
profile and retained bytes deterministically own it.

Every `sha256` value is `sha256:` followed by 64 lowercase hexadecimal
characters. A source-unit digest covers its exact retained bytes.

`content_sha256` covers the UTF-8 bytes returned by:

```python
json.dumps(
    content_manifest,
    ensure_ascii=False,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
```

`content_manifest` is exactly:

```text
{
  "contractAuthority": {
    "byteLength", "contractIdentity", "rfcRelativePath", "sha256"
  },
  "descriptor": {every section 5.3 field under its exact snake_case name},
  "modules": [
    {
      "astDepth", "astNodeCount", "byteLength", "moduleName",
      "relativePath", "sha256"
    }
  ],
  "importGraph": [
    {"moduleName", "edges": [{"line", "target"}]}
  ],
  "productionReachability": [
    {"moduleName", "path": [module names]}
  ],
  "legacyReachability": [
    {"moduleName", "path": [module names]}
  ],
  "sourceFileCount", "totalSourceBytes", "totalAstNodes",
  "totalImportEdges"
}
```

Object braces above describe exact keys, not unordered omission. Module and
graph entries sort by `moduleName`; reachability entries sort by module name;
edge order is the exact section 8 order. Descriptor tuples encode as JSON
arrays. Source bytes and text are represented by their exact unit byte length
and source digest; SHA-256 collision resistance is trusted. `root_path`,
private AST objects, and the private copy counter are excluded so the content
identity is checkout-location independent.

### 5.6 Authority map

| Decision | Sole authority | Explicitly non-authoritative inputs |
| --- | --- | --- |
| Interface meaning | complete merged identity of this RFC | interface self-claim, PR state, caller prose |
| Execution semantics | exact descriptor runtime and filesystem profile | host convenience, newest installed Python |
| Architecture source root | fixed `ROOT` passed by `main()` | command line, environment, profile, route |
| Focused-test source root | explicit absolute temporary root | production exception or policy selection |
| Inventory membership | section 7 algorithm under exact limits | directory order, module contents, importability |
| Module identity | exact relative-path naming rule | `__name__`, package metadata, execution |
| Source evidence | exact retained bytes | later path contents, imported module object |
| Parsed syntax | exact CPython and feature-version parse of retained text | path reparse or runtime import |
| Static graph | section 8 over the retained AST set | `sys.modules`, importlib, runtime imports |
| Root sets | exact descriptor tuples | caller, profile, mutable registry |
| Reachability | exact graph and reviewed tuple order | caller-selected roots, runtime imports |
| Temporal marker and adapter policy | later temporal amendment | this snapshot and passing B1 tests |
| Catalog and provisioning meaning | existing owners and later temporal amendment | module execution by this builder |

## 6. Exact execution and filesystem profile

### 6.1 Python and grammar profile

Before root inspection, the builder requires:

```text
platform.python_implementation() == "CPython"
sys.version_info[:3] == (3, 12, 13)
descriptor.ast_feature_version == (3, 12)
```

Parsing is exactly:

```python
ast.parse(
    source_text,
    filename=relative_path,
    mode="exec",
    type_comments=False,
    feature_version=(3, 12),
)
```

The hosted conformance workflow pins CPython 3.12.13. The local Codex bundled
runtime also provides CPython 3.12.13. A different implementation, patch
version, or feature version refuses independently before the source root is
inspected. A later Python upgrade changes the reviewed descriptor rather than
silently changing retained AST meaning.

### 6.2 Filesystem capability profile

`POSIX_DESCRIPTOR_RELATIVE_NOFOLLOW_STAT_NS_V1` requires all of:

- `os.name == "posix"`;
- usable `O_RDONLY`, `O_DIRECTORY`, `O_CLOEXEC`, and `O_NOFOLLOW` flags;
- descriptor-relative directory and file opens;
- `lstat` and `fstat` results containing `st_dev`, `st_ino`, `st_mode`,
  `st_size`, `st_mtime_ns`, and `st_ctime_ns`;
- no-follow inspection of every path component;
- stable regular-file and directory mode classification; and
- exact root-relative POSIX path encoding under strict UTF-8.

The builder performs a capability preflight with no caller source path. A
missing flag, field, descriptor-relative operation, or no-follow guarantee
refuses as `UNSUPPORTED_FILESYSTEM_PROFILE` before root inspection. Linux and
Darwin may satisfy this one capability contract; operating-system name alone
does not self-attest compliance.

The trusted operating system owns the stated descriptor and metadata
semantics. A filesystem or kernel that lies about them is an excluded
compromise, not a second execution profile.

### 6.3 Root and authority ancestor custody

The caller root must be absolute. Beginning at its filesystem anchor, the
builder opens every lexical ancestor component in order using the previously
opened directory descriptor with `O_DIRECTORY | O_NOFOLLOW`. Every ancestor
and the final root must be a real directory and must match its no-follow
metadata. No `resolve()`, realpath substitution, or symlinked ancestor can turn
another tree into the requested root.

The fixed contract authority path uses the same component walk relative to the
trusted architecture package root: intermediate components are real
directories; the final RFC target is one regular non-symlink file. Included
source paths use the retained root descriptor: intermediate components are real
directories; final sources are regular non-symlink files.

## 7. Inventory, resource limits, and acquisition

### 7.1 Measurement basis and fixed limits

The limits in section 5.3 are based on the reviewed base under CPython 3.12.13:

| Measurement | Base value | v1 limit |
| --- | ---: | ---: |
| included Python files | 191 | 512 |
| largest source file | 298900 bytes | 524288 bytes |
| total source bytes | 4085162 | 8388608 |
| longest relative path | 69 UTF-8 bytes | 256 bytes |
| largest AST | 26156 nodes | 65536 nodes |
| total AST nodes | 446545 | 1048576 |
| maximum AST depth | 19 | 64 |
| most static edges in one module | 20 | 128 |
| total static edges | 740 | 4096 |

The headroom is deliberate and finite. A limit change is a versioned contract
change, not a caller configuration or automatic response to repository growth.

### 7.2 Closed inventory

The builder walks once from the retained root descriptor without following
symbolic links. Candidate paths sort by root-relative POSIX path. Only leaf
names ending exactly in `.py` are considered.

A relative path is excluded when any relative component equals `__pycache__`
or begins with `.`. Every other `.py` entry is a candidate. Each intermediate
component must be a real directory. Each final candidate must be a regular
non-symlink file. Two included paths may not identify the same `(st_dev,
st_ino)`. A symlink directory in an included namespace, symlink `.py`, FIFO,
device, socket, or hard-linked second Python path refuses the whole build.

Files without the exact `.py` suffix are outside this snapshot. Their absence
creates no conformance allowance.

### 7.3 Module naming and required roots

For each included relative path:

1. remove terminal `.py`;
2. if the final remaining component is exactly `__init__`, remove it; and
3. join remaining components with `.` without changing case or characters.

An empty result or two paths producing the same module name refuses. In
particular, `package.py` with `package/__init__.py` is a collision, not an
overwrite.

All four exact fixed root modules must be present in `modules_by_name` before
graph derivation. A missing production or legacy root refuses with
`MISSING_REQUIRED_IMPORT_ROOT`; it never creates a silently empty closure.

### 7.4 Preflight before bulk allocation

The pre-inventory records for every candidate:

```text
relative path
entry kind
device
inode
size
mtime_ns
ctime_ns
```

Before reading source bytes, it refuses when file count, any relative-path
UTF-8 byte length, any nonnegative regular-file size, or total declared size
exceeds its exact descriptor limit. It also refuses negative or unrepresentable
metadata. This prevents bulk source retention outside the reviewed envelope.

### 7.5 One retained byte acquisition

Each candidate is opened descriptor-relative with no-follow flags. The open
descriptor must match the pre-inventory regular `(device, inode)`. The builder
performs one sequential byte acquisition through stable EOF; multiple
operating-system read calls are allowed, but reopen and rewind are not. The
retained length must equal the preflight size and remain within both byte
limits. Post-read descriptor metadata must equal the pre-inventory fingerprint.

After all bytes are retained, one metadata-only post-inventory validation must
equal the ordered pre-inventory exactly. It reads no source bytes and grants no
second authority. An open failure, stable-EOF failure, added, removed, renamed,
relinked, observably edited, or kind-changed candidate refuses without a
partial snapshot.

### 7.6 Decode, parse, and bounded AST

Each byte string decodes once with strict UTF-8 and parses once under section
6.1. `byte_length` is the exact retained count. `sha256` covers those bytes.

AST node count is `sum(1 for _ in ast.walk(tree))`. AST depth treats the
`ast.Module` as depth 1 and adds one along each `ast.iter_child_nodes` edge.
Per-file node count and depth are checked before retaining the tree. Total AST
nodes are checked monotonically. Exceeding any limit, or `MemoryError` or
`RecursionError` while processing an otherwise bounded source, refuses as
`RESOURCE_LIMIT_EXCEEDED` with no partial snapshot.

A later filesystem edit, deletion, rename, or replacement cannot change a
sealed snapshot. A new builder call creates a new snapshot or refusal;
snapshots are never refreshed.

## 8. Static graph, reachability, and AST custody

### 8.1 Exact graph derivation

The graph has one key for every retained module and a tuple of unique edges.
Derivation walks only retained ASTs:

- `import X` creates an edge only when `X` exactly equals a retained module;
- absolute `from X import Y` creates an edge to retained `X`, when present,
  and retained `X.Y`, when present;
- a relative import splits the source module on `.`, removes its final part
  unless the source leaf is `__init__.py`, calculates
  `keep = len(package_parts) - level + 1`, uses an empty base when `keep < 0`,
  otherwise retains the first `keep` parts, appends `node.module` parts when
  present, then evaluates the base and each `base.alias` as exact known names;
- equal `(line, target)` edges deduplicate; and
- edges sort by `line` then `target`, matching `PythonImportEdgeV1` order.

Per-module and total edge limits are enforced while deriving the graph. A
limit breach refuses before sealing.

Imports nested under functions, classes, or `TYPE_CHECKING` remain static
edges. Calls to importlib, `__import__`, `exec`, reflection, registries, or
computed module names create no guessed edge. Their syntax remains available
through bounded detached AST copies for a separately governed policy.

### 8.2 Ordered breadth-first reachability

Production and legacy maps are derived separately. For each tuple, roots are
seeded into the queue in their exact reviewed tuple order. Each present root
receives its one-element path. Since all roots are required, absence has already
refused.

Traversal processes each module's exact sorted edge tuple. The first discovered
path to a module is retained permanently; a later path never replaces it.
Neither roots nor queue contents are resorted. This fixes deterministic BFS and
reviewed root precedence.

### 8.3 AST copy custody and bounds

Private retained ASTs never leave the snapshot. Each successful `ast_for` call
deep-copies one tree whose node count and depth already satisfy v1. The snapshot
does not retain returned copies. The exact 512-call budget bounds allocation
requests through the supported object. Architecture composition must share a
returned copy among non-mutating visitors when more than one observation of a
module is needed.

An arbitrary loop inside trusted checker code, retention of all returned
copies beyond their intended observation, or bypass of the supported API is a
trusted-code compromise. It is not contributor-controlled source input. The
closed per-tree, total-tree, and call limits prevent source content alone from
widening the supported allocation envelope.

## 9. Trust model

### 9.1 Protected assets

The protected assets are complete and unique inventory membership; exact bytes
used for every observation; agreement between bytes, text, AST, graph, roots,
and reachability; bounded processing of contributor input; and separation
between checked repository code and checker authority.

### 9.2 Trusted components

Trusted components are the exact approved and complete merged contract, future
reviewed architecture implementation, exact CPython runtime, standard library,
filesystem capability profile, operating-system descriptor semantics, SHA-256,
and checker process before handling untrusted source.

### 9.3 Untrusted inputs and actors

Repository Python bytes, filenames, directory order, symlinks, hard links,
invalid text, invalid syntax, large or deeply nested valid syntax, import
statements, module-level code, runtime self-description, and caller root are
untrusted. They may produce one sealed bounded snapshot or one closed refusal.
They cannot select semantics, profiles, roots, limits, exceptions, or contract
identity.

Ordinary source addition, removal, rename, edit, or substitution before,
during, or after acquisition is in scope under the observations defined in
sections 6 and 7.

### 9.4 Excluded compromise capabilities

Compromise of CPython, the operating system, filesystem guarantees, SHA-256,
trusted dependencies, checker implementation, architect, or repository review
and release custody is outside this static boundary. Hostile in-process memory
mutation, kernel metadata forgery, and an attacker that changes and restores
source plus all observed identities and nanosecond metadata within one
acquisition are also excluded.

These exclusions do not allow ordinary repository modules to execute, mutate
checker state, select roots or limits, supply digests, or self-attest.

## 10. State machine and ordering

The only terminal outcomes are `SEALED` and `REFUSED`:

```text
UNBUILT
-> CONTRACT_AUTHENTICATED
-> EXECUTION_PROFILE_AUTHENTICATED
-> ROOT_CUSTODY_ESTABLISHED
-> PRE_INVENTORY_BOUNDED
-> BYTES_RETAINED
-> POST_INVENTORY_MATCHED
-> TEXT_AND_AST_BOUNDED
-> REQUIRED_ROOTS_PROVED
-> GRAPH_BOUNDED
-> REACHABILITY_DERIVED
-> CONTENT_DIGEST_DERIVED
-> SEALED
```

Any expected untrusted-input failure transitions to `REFUSED`. `SEALED` and
`REFUSED` are terminal for the build. Exactly one complete snapshot is returned
only at `SEALED`; no partial inventory, record, AST, graph, or closure is
returned earlier.

Contract and execution-profile authentication happen before caller-root
inspection. Source bounds precede bulk retention. Inventory validation precedes
parsing. AST bounds precede graph derivation. Required root presence precedes
graph derivation and reachability. Sealing discards mutable construction
aliases.

The builder's only external effects are bounded filesystem reads. It creates no
file, cache, registry entry, database row, import, module object, network call,
subprocess, or runtime activation. The private AST-copy count after sealing is
non-authoritative resource accounting and cannot change snapshot equality or
content.

## 11. Invariants and required negative cases

### 11.1 Invariants

- **APSS-001 — Complete merged contract first.** No execution-profile or root
  inspection begins until the complete merged RFC authority authenticates.
- **APSS-002 — Closed interface and descriptor.** Every public type, field,
  method, refusal code, profile, root, and limit equals section 5; callers
  cannot add or select authority.
- **APSS-003 — Exact execution profile.** CPython, patch version, grammar
  feature version, and filesystem capabilities authenticate independently
  before root inspection.
- **APSS-004 — Closed bounded inventory.** Section 7 alone owns membership,
  naming, link posture, required roots, and resource limits.
- **APSS-005 — One byte authority.** Each source has one descriptor-relative
  byte acquisition; retained bytes alone own text, digest, AST, graph,
  reachability, and later source observations.
- **APSS-006 — Acquisition consistency.** Any observed source or inventory
  transition refuses without a partial snapshot.
- **APSS-007 — No checked-code execution.** No snapshot operation imports,
  executes, evaluates, or compiles an inventoried module to executable
  bytecode.
- **APSS-008 — Immutable bounded authority.** Public source authority is
  immutable; AST copies are detached and call-bounded; mutation cannot affect
  retained state.
- **APSS-009 — Deterministic graph and BFS.** Equal retained records under the
  exact profile produce equal graph and ordered first-discovered reachability.
- **APSS-010 — One architecture snapshot per run.** B1 `main()` builds one
  snapshot and supplies every Python source, line-count, AST, policy, graph,
  and reachability observation from it.
- **APSS-011 — Temporary adapters have no authority.** B1 adapters accept and
  return only sealed-snapshot evidence, perform no path read, and disappear
  after both named consumers migrate.
- **APSS-012 — Static evidence is not runtime proof.** No missing edge becomes
  proof of absent dynamic loading or catalog, provisioning, temporal,
  selection, or runtime authority.
- **APSS-013 — Existing firewall policy is preserved.** Exact roots and source
  custody are bound; policy meaning is neither widened nor moved to a temporal
  owner.
- **APSS-014 — Closed production surface.** No database, migration, adapter,
  RuntimeBundle, profile, route, command, materialization, read, output,
  deployment, legacy behavior, or #192 authority changes.
- **APSS-015 — Fail closed on expansion.** A new public field, profile, limit,
  root, inventory class, policy, consumer file, or authority stops for its
  reviewed owner.

### 11.2 Required negative cases

Future B1 must prove:

| Case | Required result |
| --- | --- |
| Complete merged RFC missing, wrong length, same-length wrong digest, symlinked, aliased, or multiply resolved | `CONTRACT_AUTHORITY_MISMATCH` before profile or root inspection |
| Python implementation differs | `UNSUPPORTED_PYTHON_IMPLEMENTATION` before root inspection |
| CPython patch version differs | `UNSUPPORTED_PYTHON_VERSION` before root inspection |
| AST feature version differs | `UNSUPPORTED_AST_FEATURE_VERSION` before root inspection |
| One required filesystem capability is absent | `UNSUPPORTED_FILESYSTEM_PROFILE` before root inspection |
| Caller supplies descriptor, roots, limits, encoding, graph rules, or profile | closed builder signature accepts no such argument |
| Returned descriptor or public schema is inspected | exact section 5 names, types, values, maps, and no extra authority-bearing field |
| Root is relative, absent, or non-directory | `INVALID_ROOT` |
| Any root ancestor is a symlink | `SYMLINK_COMPONENT`; no resolution into eligibility |
| An intermediate source component is not a real directory | `NON_DIRECTORY_COMPONENT` |
| Included directory or `.py` leaf is a symlink | `SYMLINK_COMPONENT`; never followed |
| Included `.py` is FIFO, device, socket, or other non-regular entry | `NON_REGULAR_SOURCE` |
| Two included paths share device/inode | `DUPLICATE_FILE_IDENTITY` |
| `package.py` and `package/__init__.py` coexist | `DUPLICATE_MODULE_NAME` |
| Root `__init__.py` produces an empty name | `EMPTY_MODULE_NAME` |
| Hidden or `__pycache__` Python source exists | excluded with no module or edge |
| `kernel/tests` or `profile_si_ffs/tests` source exists | included; interface has no test-family exception |
| One fixed production or legacy root is missing | `MISSING_REQUIRED_IMPORT_ROOT`; no empty closure |
| File count exceeds 512 | preflight `RESOURCE_LIMIT_EXCEEDED` |
| Relative path exceeds 256 UTF-8 bytes | preflight `RESOURCE_LIMIT_EXCEEDED` |
| One file declares more than 524288 bytes | preflight `RESOURCE_LIMIT_EXCEEDED` |
| Declared total exceeds 8388608 bytes | preflight `RESOURCE_LIMIT_EXCEEDED` |
| Retained size differs from preflight | `SOURCE_CHANGED` |
| Candidate is added, removed, renamed, relinked, or observably edited during acquisition | `INVENTORY_CHANGED` or `SOURCE_CHANGED` |
| Invalid strict UTF-8 | `INVALID_UTF8` with no partial AST or graph |
| Invalid Python 3.12 syntax | `INVALID_PYTHON_SYNTAX` with no partial graph |
| Per-file or total AST nodes, AST depth, per-module edges, or total edges exceed v1 | `RESOURCE_LIMIT_EXCEEDED` |
| Bounded parse or deep-copy raises `MemoryError` or `RecursionError` | `RESOURCE_LIMIT_EXCEEDED`; no partial public state |
| Path changes after `SEALED` | retained fields, equality, digest, AST copies, graph, and reachability remain unchanged |
| Public mapping, tuple, frozen record, descriptor, or root tuple mutation is attempted | mutation unavailable or refused |
| Returned AST copy is mutated and another copy requested | later copy and snapshot fields remain unchanged |
| `ast_for` succeeds 512 times and is called again | `AST_COPY_LIMIT_EXCEEDED`; authority fields unchanged |
| Unknown module is requested | exact `KeyError`; copy budget unchanged |
| Equal trees enumerate directories differently | equal units, content digest, graph, and reachability |
| Repeated, absolute, and relative static imports occur | only exact known edges, deduplicated and sorted |
| Multiple roots reach one module | tuple-order seeded BFS permanently retains first discovered path |
| Source contains importlib, `__import__`, `exec`, reflection, or computed name | no execution and no guessed edge; AST remains available to later policy |
| Module would raise or write a sentinel if imported | valid syntax snapshots without import or sentinel |
| `sys.path` or `sys.modules` has a competing name | no effect on inventory, graph, or digest |
| Complete architecture checker runs | one builder call supplies all Python observations |
| B1 `_module_sources(root)` is called by a current consumer | returns one sealed `PythonSourceSnapshotV1`, never a path mapping |
| B1 `_import_graph(snapshot)` is called | returns snapshot graph and detached AST views without source read |
| A temporary root alias is rebound or altered before `_reachable_paths` | `UNSUPPORTED_REACHABILITY_ROOTS`; no narrowed closure |
| Temporary adapter receives a path mapping or non-snapshot | refuse; old input contract is gone |
| A consumer treats static non-reachability as dynamic-import proof | invalid claim; stop for consumer contract |
| Temporal, catalog, or provisioning checker consumes public v1 without reviewed authorization | stop; B1 grants none |

## 12. Staged architecture and smallest coherent change

### 12.1 B1 — architecture snapshot admission

After exact approval, publication, merge, complete merged-RFC authentication,
and a separate explicit B1 request, B1 may:

1. add the exact public v1 types and builder in
   `conformance/rewrite_architecture_check.py`;
2. construct one snapshot in architecture `main()`;
3. migrate all of that checker's Python source, line-count, AST, provider
   policy, firewall, graph, and reachability observations to the snapshot;
4. replace old helper internals with these exact temporary adapters:

```python
def _module_sources(root: pathlib.Path) -> PythonSourceSnapshotV1:
    return build_python_source_snapshot(root)

def _import_graph(
    snapshot: PythonSourceSnapshotV1,
) -> tuple[
    collections.abc.Mapping[str, tuple[PythonImportEdgeV1, ...]],
    collections.abc.Mapping[str, ast.Module],
]:
    ...
```

`_import_graph` requires the exact snapshot type, returns its immutable graph
and one bounded detached AST copy for every module, and performs no open, stat,
walk, parse, or path read. `_reachable_paths` may remain temporarily as the
existing pure graph function. `PRODUCTION_IMPORT_ROOTS` and
`LEGACY_IMPORT_ROOTS` may remain only as exact tuple aliases equal to the v1
descriptor; snapshot construction and architecture `main()` do not read those
mutable aliases as authority.

During B1, `_reachable_paths` accepts a root tuple only when it is value-equal
to one of the descriptor's exact production or legacy tuples. Any altered,
empty, reordered, or third tuple refuses with
`UNSUPPORTED_REACHABILITY_ROOTS`. This keeps the current call shape from
silently narrowing a closure while B2 is pending. The function performs only
pure traversal over the graph argument and reads no source path.

This is a compatibility call shape, not a compatibility authority. The old
path-mapping return type and path-reading graph input are deleted in B1.

### 12.2 B2 — separate temporal-owner migration

B1 does not edit or authorize B2. A later reviewed temporal contract must
authorize migration of exactly the existing external consumers:

```text
conformance/temporal_contract_candidate_check.py
kernel/tests/test_temporal_carriers.py
```

That temporal contract must bind the complete merged architecture RFC and
interface, use snapshot-owned roots and reachability, and separately decide
catalog, provisioning, marker, and dynamic-import rules. Its implementation
must remove all calls from those files to `_module_sources`, `_import_graph`,
`_reachable_paths`, `PRODUCTION_IMPORT_ROOTS`, and `LEGACY_IMPORT_ROOTS`.

### 12.3 B3 — architecture adapter cleanup

Only after B2 is merged on current `main`, repository search proves no external
call to the five private names or root aliases, and the complete package check
passes may a separate architecture cleanup remove the two temporary adapters
and any no-longer-needed aliases. B3 remains limited to the architecture
checker, its focused test, and mechanically required test inventory.

No PR combines B1, B2, or B3 across architecture and temporal trust boundaries.

### 12.4 Types, composition, and deletion

B1 adds one descriptor, one contract-authority record, one source unit, one
edge, one snapshot, one refusal enum and exception, and one builder. One bound
object replaces correlated paths, source reads, AST dictionaries, graph roots,
and closures.

The old path-returning `_module_sources` behavior and path-accepting,
path-reading `_import_graph` behavior are deleted in B1. The exact temporary
names remain only because current merged consumers are load-bearing. B3 deletes
those names after the named removal condition; no permanent compatibility
surface remains.

### 12.5 Smallest-change and elegance audit

Returning only bytes would duplicate parsing and graph semantics. Returning
only ASTs would omit exact byte evidence. Correlated dictionaries would leave
roots, profiles, limits, and membership separable. One bound snapshot is the
smallest object that closes all reviewed authority gaps.

- Governing source contracts: one complete merged RFC.
- Source acquisition transitions: one builder call per checker run.
- Source-byte authorities: one retained byte string per unit.
- Graph authorities: one bounded derivation.
- Root sets and limits: one exact descriptor.
- Mutable registries, services, caches, or policy engines: zero.
- Permanent compatibility surfaces: zero after B3.
- Runtime or temporal authorities introduced: zero.

## 13. Pull request boundaries and stop conditions

### 13.1 This Phase A PR

This proposal changes only:

```text
docs/rfcs/OFARM_Architecture_Python_Source_Snapshot_Admission_RFC_v0_1.md
```

Before approval it remains proposed and unapproved. After exact approval under
section 15, the same one-file PR may make only the truthful status transition
and append one complete approval appendix. It may not contain code, tests,
temporal amendments, or generated inventory changes.

### 13.2 Future B1 and B3 architecture allowlist

Each separately requested architecture implementation may change only:

```text
conformance/rewrite_architecture_check.py
kernel/tests/test_rewrite_architecture_check.py
conformance/review_baseline_test_inventory.json
```

The inventory file changes only when mechanically required by a change to the
canonical collected test-node inventory, including count or node-ID change.
B1 and B3 are separate PRs divided by B2.

If implementation needs a schema, manifest, registry, second module,
package-checker edit, temporal checker edit, database file, runtime file, or
another test family, it stops for the owning boundary.

### 13.3 Exact later sequence

```text
approve, publish, re-review, and merge this Phase A RFC
-> compute complete merged RFC identity
-> receive separate explicit architecture B1 request
-> implement, review, and merge only B1
-> draft and approve the temporal-owner amendment
-> implement, review, and merge temporal B2
-> prove both external consumers and five private references are absent
-> receive separate explicit architecture B3 request
-> remove temporary adapters in B3
-> only then reconsider a replacement for PR #283
```

### 13.4 Stop conditions

Work stops before:

1. implementing B1 without exact approval, truthful publication,
   publication-byte/provenance re-review, merge, complete merged identity, and
   separate explicit request;
2. editing PR #283 or a temporal consumer in Phase A or B1;
3. deleting temporary adapters before both named consumers migrate and package
   conformance passes on current `main`;
4. adding a caller-selected profile, root, rule, limit, exclusion, or
   exception;
5. adding a second walker, path reread, importlib loader, module execution
   path, global snapshot cache, or independently authoritative adapter;
6. defining temporal marker, catalog, provisioning, or dynamic-import policy;
7. changing firewall policy instead of only its source authority;
8. changing database, migration, adapter, RuntimeBundle, profile, active
   registry, route, command, read, output, deployment, legacy behavior, or
   #192 authority;
9. changing frozen law, ADR 0002, a candidate, ERRATA, manifest, digest, or
   lifecycle decision; or
10. editing a file outside the applicable Phase A, B1, B2, or B3 owner
    allowlist.

Each stopped item requires its own reviewed owner. No cross-boundary review fix
is appended merely to clear PR #283.

## 14. Verification and traceability

### 14.1 Phase A verification

```text
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --name-only origin/main...HEAD
```

The final command names only this RFC.

### 14.2 Future B1 verification

Verification runs under exact CPython 3.12.13 and includes:

```text
python3 -m pytest -q kernel/tests/test_rewrite_architecture_check.py
python3 conformance/rewrite_architecture_check.py
python3 conformance/temporal_contract_candidate_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

The B1 handoff shows only its three allowed files, states canonical test
inventory changes by count and node ID, and proves both current external
consumers still pass through the temporary adapters without path reads.

### 14.3 Traceability

| Invariant | Future seam | Required evidence |
| --- | --- | --- |
| APSS-001 | fixed complete-RFC authenticator | missing, length mismatch, same-length digest mismatch, symlink, alias refuse before profile/root |
| APSS-002 | exact public types and descriptor constant | schema inspection, rejected extra args, exact values, no extra authority field |
| APSS-003 | execution-profile validator | implementation, patch, grammar, and filesystem capabilities substituted independently and refused |
| APSS-004 | inventory, naming, preflight limits, required roots | exclusions, included tests, links, kinds, hard links, collisions, absent roots, every limit boundary |
| APSS-005, APSS-006 | descriptor-relative acquisition and pre/post fingerprints | retained mutation isolation and observable acquisition transitions |
| APSS-007 | builder with no import/execution seam | raising and sentinel-writing source never executes |
| APSS-008 | frozen public values and bounded `ast_for` | map/record/copy mutation, unknown module, 513th copy call |
| APSS-009 | exact graph and ordered BFS | static forms, edge bounds, root order, first-path preservation, directory-order independence |
| APSS-010 | B1 `main()` composition | exactly one builder call; no Python path read outside builder |
| APSS-011 | exact B1 adapters and later B3 search | snapshot return, no path input/read, both existing consumers green, exact removal condition |
| APSS-012, APSS-013 | static-only interface and unchanged visitors | dynamic syntax makes no guessed edge; existing firewall cases remain green |
| APSS-014, APSS-015 | changed-file boundaries and stop checks | no temporal, runtime, database, legacy, or #192 file in B1/B3 |

## 15. Byte-authenticated approval, publication, and re-review

### 15.1 Canonical proposed design

Canonical design extraction is exact:

- the file is UTF-8 with LF line endings;
- no CR byte or UTF-8 BOM is allowed;
- the begin marker is the complete first line
  `<!-- BEGIN OFARM2 ARCHITECTURE PYTHON SOURCE SNAPSHOT PHASE A DESIGN -->`;
- extraction begins at the first `#` byte immediately after that marker's LF;
- the end marker is the complete line
  `<!-- END OFARM2 ARCHITECTURE PYTHON SOURCE SNAPSHOT PHASE A DESIGN -->`;
- extraction ends immediately before the first byte of the end marker; and
- the extracted design contains exactly one terminal LF.

The mechanically derived design byte length, SHA-256, exact approval sentence,
and approval-sentence identity are recorded after the end marker in section 17.
That derived block is outside canonical design bytes to avoid self-reference.
It is fixed review evidence and may not change during approval publication.

### 15.2 Complete live decision card

After all technical blockers close, the AI must display one card in Codex task
`019fa821-93c9-7ef1-8c94-1c0e92ea46b9`. Card extraction:

- uses UTF-8 and LF with no CR or BOM;
- begins with the exact first line
  `OFARM2 COMPLETE LIVE DECISION CARD`;
- ends with the exact last bytes
  `END OF OFARM2 COMPLETE LIVE DECISION CARD`; and
- includes no terminal LF.

The card states the exact contract, path, reviewed base and head, design length
and digest, exact approval sentence and its length/digest, trust boundary,
decision, execution profile, resource limits, staged effects, non-effects,
invariants, negative cases, preservation rules, allowlists, stop conditions,
verification, review evidence, and next sequence.

Immediately after the extracted card, outside its canonical bytes, the AI must
display the card's exact UTF-8 byte length and SHA-256 and then solicit only the
exact approval sentence. The approval request is invalid if the card identity
does not recompute or if another card or changed design intervenes.

### 15.3 Human approval authority

The designated architect must send the exact section 17 approval sentence as a
later user-authored message in the same task. Typing it or copying it directly
from that complete live card is valid.

An approval sentence or digest copied from another task, card, decision,
documentation, template, PR, GitHub, or AI-authored or AI-sent text other than
that complete live card is invalid. AI messages, repository credentials, PR
authorship, review, comment, reaction, merge, or generic approval never count.

The user message is the architect's decision. The repository appendix is
evidence, not a substitute.

### 15.4 Permitted publication differences

Only after exact approval may the one-file Phase A PR:

1. change the status metadata from proposed and unapproved to
   architect-approved; and
2. append one `Appendix A — Architect approval record` after section 17.

No derived identity in section 17 changes. No decision, interface, descriptor,
profile, limit, trust rule, authority map, state, invariant, negative case,
architecture, non-goal, verification rule, boundary, stop condition, or
merge-stop rule changes. A substantive edit creates new canonical design bytes,
requires recalculated section 17 evidence, technical re-review, a new live card,
and new approval.

The appendix records exact design and approval-sentence identities, task/card
and user-message stable references and timestamps, exact card extraction and
identity, reviewed base/head, review evidence, one permitted effect, every
non-effect, preservation rules, and next sequence.

### 15.5 Mandatory publication-byte and provenance re-review

Before merge, a reviewer with direct task access must verify:

1. proposed design reconstructed from the publication equals section 17's
   exact bytes;
2. only the status transition and one appendix differ;
3. card bytes and identity recompute under section 15.2;
4. the exact later message is user-authored by the designated architect in the
   same task and equals section 17's sentence bytes;
5. the card immediately preceded the approval request with no competing card
   or changed design;
6. all stable references, timestamps, reviewed heads, effects, non-effects,
   preservation rules, and next sequence are truthful; and
7. hosted conformance passes at the publication head.

GitHub cannot substitute for inaccessible Codex evidence. If direct provenance
cannot be verified, the PR remains unmergeable without a repository patch.

### 15.6 Complete merged authority and separate B1 request

After publication merges, compute the entire merged RFC's UTF-8 byte length and
SHA-256, including the status transition, markers, section 17, and appendix.
The B1 implementation constants pin those complete values. B1 refuses before
profile/root inspection when they differ. The pre-publication design digest
cannot substitute.

Merge and complete identity still do not authorize B1. A separate explicit
user request naming architecture B1 under this contract is required.

This Codex approval workflow is provisional and pre-deployment. Before
deployment it must be replaced by independently human-controlled and
independently verifiable signing or approval.

## 16. Provisional status, review disposition, and merge stop

### 16.1 Provisional design record

The current document is **proposed, unapproved, and therefore not yet an
accepted design**. If its exact canonical bytes are approved and published, the
v1 snapshot architecture is intended to be non-provisional and may be replaced
only through a later reviewed version or amendment. The Codex approval
transport remains provisional before deployment.

Evidence requiring redesign includes inability to provide the exact execution
profile, demonstrated need for another encoding or root, repository growth
beyond a fixed limit, or a consumer needing semantics beyond retained bytes,
AST, static graph, and fixed reachability. The upgrade path is reviewed
descriptor/version change, never silent widening.

### 16.2 Open decisions and review disposition

Open design decisions: none. Temporal catalog, provisioning, dynamic-import,
and marker rules are deliberately owned by the later temporal amendment.

- **Blockers:** exact technical re-review and architect approval have not yet
  occurred.
- **Follow-ups:** B1 after approval/publication and separate request; temporal
  B2 after its own contract; architecture B3 after exact consumer removal.
- **Preferences:** none recorded.

### 16.3 Merge-stop rule

This PR must not merge while proposed or unapproved. After exact approval, the
documentation publication must not merge until the mandatory publication-byte
and provenance re-review passes, its sole changed path is this RFC, its only
differences are the truthful status transition and one complete appendix, and
every design, card, approval, review, and provenance identity verifies exactly.

Once those conditions pass and no demonstrated in-scope Blocker remains, merge
the Phase A documentation PR. New ideas, Preferences, and non-blocking
hardening become Follow-ups and do not reopen review. B1 remains separately
blocked until the complete merged authority is pinned and an explicit B1
request exists.
<!-- END OFARM2 ARCHITECTURE PYTHON SOURCE SNAPSHOT PHASE A DESIGN -->

## 17. Derived canonical design and approval-sentence identity

This section is mechanically derived review evidence outside the canonical
design bytes. It is not an approval record.

- canonical design encoding: UTF-8, LF only, no BOM, exactly one terminal LF;
- canonical extraction: section 15.1;
- canonical design byte length: `57444`;
- canonical design SHA-256:
  `sha256:31cacaf2089a4bafccb2eab369525fc275142600638545eec3817d55a5acb562`;
- approval-sentence encoding: UTF-8 with no terminal LF;
- approval-sentence byte length: `524`;
- approval-sentence SHA-256:
  `sha256:2f19e9cea4fe966cf276a35188973017888b4cb0faeb368cb285b7bed0285010`.

The exact approval sentence is:

> I explicitly approve the Phase A design of contract ofarm.architecture-python-source-snapshot-admission.issue176.v0.1 at sha256:31cacaf2089a4bafccb2eab369525fc275142600638545eec3817d55a5acb562 (57,444 bytes) in Codex task 019fa821-93c9-7ef1-8c94-1c0e92ea46b9 and authorize one documentation-only approval record with exactly the provenance, permitted effect, non-effects, preservation rules, and next required sequence stated in the complete decision card displayed immediately before this approval request in the same task.
