# OFARM2 Architecture Package Initializer Reachability — Phase A Contract v0.1

**Status:** proposed and unapproved; Phase A documentation only; Phase B is
unauthorized

**Contract identity:**
`ofarm2.architecture-package-initializer-reachability.issue334.v0.1`

**Decision identity:**
`ISSUE334-ARCHITECTURE-PACKAGE-INITIALIZER-REACHABILITY-001`, version `1`

**Reviewed base:** `24d0b7e794caa28ede03e171119c8a86f4898470`

**Issue:** `https://github.com/samovers/OFARM2/issues/334`

**Draft pull request:** `https://github.com/samovers/OFARM2/pull/347`

**Primary trust boundary:** architecture-checker accuracy for retained Python
source that CPython implicitly executes as regular-package initializers

**Current Phase A path:**
`docs/rfcs/OFARM_Architecture_Package_Initializer_Reachability_RFC_v0_1.md`

**Maximum implementation path envelope:**

1. `docs/rfcs/OFARM_Architecture_Package_Initializer_Reachability_RFC_v0_1.md`
2. `conformance/rewrite_architecture_check.py`
3. `kernel/tests/test_rewrite_architecture_check.py`
4. `conformance/review_baseline_test_inventory.json`

This contract creates no runtime, database, deployment, release, production,
current-compliance, certification, issue-#192, or issue-closure authority.

## 1. Problem and goal

### 1.1 One problem

`conformance/rewrite_architecture_check.py` currently derives its production
and legacy reachability maps only from explicit imports retained in the static
AST graph. CPython also executes each regular-package `__init__.py` on the path
to an imported submodule before executing the submodule. A namespace-package
ancestor has no initializer source and contributes no executable module.

The current checker therefore can inspect a reached submodule while omitting a
retained initializer that necessarily executes on the same import path. On the
reviewed base, `deployment.postgresql` is statically production-reachable while
the retained `deployment/__init__.py` is not in the public production map. The
present initializer is harmless; the defect is that architecture-policy claims
do not necessarily cover all retained source implied by the fixed roots.

The accepted Python-source snapshot contract intentionally defines its public
`import_graph`, `production_reachability`, `legacy_reachability`, descriptor,
digest, and refusal vocabulary as exact v1 static evidence. Silently changing
those public values here would cross into the separately governed snapshot and
temporal-consumer boundary.

### 1.2 Goal

Add one checker-private, deterministic import-execution closure derived only
from a builder-sealed `PythonSourceSnapshotV1` and its bounded detached AST
copies. The closure must:

1. include every retained regular-package initializer implied by each fixed
   production or legacy root and every reached retained module;
2. follow explicit retained-module imports from newly included initializers to
   a fixed point;
3. recognize namespace-package prefixes without inventing executable source;
4. fail the checker before policy evaluation when reachable internal import or
   package topology is unresolved or ambiguous; and
5. supply the architecture import firewall and tenant UnitOfWork scan without
   changing the public snapshot contract or any temporal consumer.

Passing establishes only the static, checked-in import-execution closure under
the existing fixed root tuples. It does not establish complete production
composition or complete execution-root/source-capability governance.

## 2. Learning value

The change validates that the existing sealed snapshot is sufficient to model
regular-package execution semantics honestly without executing repository
code, rereading paths, widening a public authority interface, or combining the
separate execution-root governance boundary. It reduces the demonstrated risk
that an architecture policy passes while skipping retained initializer source
that CPython necessarily executes.

## 3. Non-goals

This decision does not:

- change `PythonSourceSnapshotV1`, its public types or properties, its builder
  signature, descriptor, graph semantics, root tuples, limits, refusal codes,
  equality, content digest, or public reachability maps;
- edit or amend
  `docs/rfcs/OFARM_Architecture_Python_Source_Snapshot_Admission_RFC_v0_1.md`;
- change `conformance/temporal_contract_candidate_check.py`, temporal contracts,
  or any test that consumes the public v1 reachability maps;
- reclassify the public v1 reachability maps as import-execution closure;
- add, remove, or select production or legacy roots;
- inventory console, operator, build, test, tool, worker, migration, plugin, or
  other execution entry points;
- define a closed dynamic-execution capability policy or infer dynamic imports;
- model custom import hooks, editable installs, external namespace portions,
  installed-package shadowing, arbitrary `sys.path` composition, or a
  compromised interpreter;
- import, execute, evaluate, or compile retained repository source to executable
  bytecode;
- change runtime Python, security-audit behavior, SQL, migrations, roles,
  transactions, credentials, providers, secrets, routes, outputs, deployment,
  release, or production authority;
- reopen or close issue #192; or
- claim production readiness, deployment authority, certification, or current
  compliance.

Complete execution-root/source-capability governance remains an independent
Follow-up. A future owner may amend the public snapshot or temporal semantics,
but that work cannot be appended to this pull request.

## 4. Trust model

### 4.1 Protected assets

- The architecture checker's claim that every retained Python source implied by
  its fixed production and legacy imports is inspected by the policies that use
  execution reachability.
- The existing sealed snapshot's authority over inventory, retained bytes,
  parsed syntax, explicit graph, roots, and resource limits.
- Separation between this checker-private correction and the public snapshot,
  temporal, runtime, deployment, and issue-#192 boundaries.
- Deterministic, reviewable diagnostics that do not invent source lines or
  namespace modules.

### 4.2 Trusted components

- CPython 3.12.13 import semantics within the exact execution profile already
  authenticated by the accepted source-snapshot contract.
- The accepted contract
  `ofarm.architecture-python-source-snapshot-admission.issue176.v0.1` and public
  interface `ofarm.architecture-python-source-snapshot.v1`.
- The builder-sealed `PythonSourceSnapshotV1`, including retained module names,
  relative paths, exact public import graph, fixed root tuples, and bounded
  detached AST copies.
- Reviewed checker code implementing the private topology classifier,
  validation pass, closure derivation, and policy composition.
- The repository's existing review, package-conformance, and baseline-admission
  controls.

### 4.3 Untrusted actors and inputs

Repository contributors and pull-request source are untrusted for purposes of
the architecture result. In-scope untrusted input includes:

- retained Python bytes and syntax;
- dotted module layout and regular- versus namespace-package topology;
- absolute and relative `import` and `from ... import ...` operands;
- import cycles, duplicate paths, multiple discovery paths, and source ordering;
- unresolved internally rooted imports and plain-module/package conflicts; and
- filesystem mutation during snapshot acquisition, as already governed by the
  accepted source-snapshot contract.

Local source substitution before or during acquisition is in scope and must be
captured or refused by the existing snapshot. Later source substitution cannot
alter the sealed evidence used by this closure.

### 4.4 Explicitly excluded capabilities

- arbitrary in-process mutation or bypass of the builder seal;
- compromised CPython, standard library, dependencies, checker code, CI policy,
  operating-system primitives, or filesystem primitives;
- custom import finders or loaders and external namespace-package contents;
- operator, repository-owner, or trusted-review compromise; and
- deployment or runtime configuration not represented by the fixed checked-in
  root tuples.

An excluded compromise does not become a reason to widen this pull request.

## 5. Authority map

| Decision | Sole authority in this boundary | Rejected alternate authority |
| --- | --- | --- |
| Retained source membership and exact bytes | builder-sealed `PythonSourceSnapshotV1` | second walk, path reread, live import, cache, caller map |
| Dotted module identity and relative path | `modules_by_name` and each retained `PythonSourceUnitV1.relative_path` | filesystem probing after seal, `sys.modules`, `sys.path` |
| Explicit edges to retained modules | public `snapshot.import_graph` | a second independently authoritative graph |
| Import operands needed only for internal-resolution and namespace validation | one private normalizer over the shared detached AST mapping | regexes, source-text rescans, runtime imports |
| Regular initializer identity | exact retained unit path equals the dotted module path plus `/__init__.py` | naming convention alone, directory existence alone |
| Namespace prefix | a proper dotted prefix of a retained module with no retained unit at that identity | synthetic module record or executable placeholder |
| Plain module | retained unit at an identity whose path is not an initializer path | treating it as a package because descendants exist |
| Production and legacy roots | exact immutable tuples in the authenticated snapshot descriptor | caller-selected roots, aliases, globals, environment |
| Private import-execution closure | this contract's fixed-point rules applied to the sealed snapshot | public v1 reachability redefinition, temporal consumer |
| Architecture policy decision | one complete private closure derived before policy evaluation | partial closure, fallback to public reachability on failure |

No duplicate state is writable. No compatibility alias, fallback closure,
second inventory, mutable registry, or alternate root-selection path is added.

## 6. Package topology and import resolution

### 6.1 Closed topology classification

For each retained module identity `M`, its unit is classified exactly once:

- **regular package:** its relative path is `M` translated from dots to `/`
  followed by `/__init__.py`;
- **plain module:** every other retained path for `M`; or
- **namespace prefix:** not a retained module itself, but a proper dotted prefix
  of at least one retained module.

Every proper dotted prefix of a reached identity is examined outermost first.
A retained regular package contributes its initializer module to the closure.
A namespace prefix contributes no module or AST. A retained plain module that
would need to act as an ancestor of another internal identity is an ambiguity
and fails the complete closure.

The existing snapshot already rejects `package.py` together with
`package/__init__.py` as a duplicate module identity. This contract additionally
rejects reachable topology such as `package.py` together with
`package/submodule.py`, because CPython cannot treat the retained plain module
as the required package ancestor.

### 6.2 Internal-root classification

The set of internal top-level names is derived only from the first component of
retained module identities. An absolute import operand whose first component is
in that set is internally rooted. A relative import operand is always internal.
An absolute operand under any other top-level name remains external and creates
no repository edge or resolution claim.

### 6.3 Exact import rules

The private normalizer retains source module, source relative path, source line,
import form, normalized base, and candidate targets. It uses the same relative
base calculation as the public v1 graph.

- `import X`:
  - if `X` is externally rooted, it contributes no repository member;
  - if internally rooted, `X` must resolve to an exact retained module or a
    known namespace prefix;
  - every retained regular-package ancestor of `X` is included;
  - an exact retained `X` is followed through the corresponding public graph
    edge; and
  - a namespace-only `X` contributes no synthetic member.
- `from X import Y`:
  - the normalized base `X` is resolved first under the same internal/external
    rules and its regular-package ancestry is included;
  - an exact retained base is followed through its public graph edge;
  - each exact retained or known-namespace candidate `X.Y` contributes its
    regular-package ancestry, and an exact retained candidate is followed
    through its public graph edge;
  - an absent `Y` is permitted after a resolved base because it may be an
    attribute rather than a submodule; and
  - a missing internally rooted base, invalid above-root relative base, or
    descendant beneath a retained plain module fails closed.

`from X import *` resolves only `X`; no guessed member is created. Syntax under
functions, classes, or `TYPE_CHECKING` remains static evidence exactly as in the
public graph. Dynamic loading syntax creates no guessed target.

For every exact retained-module target found by the normalizer, the public graph
must contain the same `(line, target)` edge. A mismatch is a trusted-code defect
and fails the checker; the implementation may not choose whichever graph is
more permissive. The public graph remains the only authority for explicit
retained-module traversal.

## 7. State machine and ordering

One checker invocation follows this sequence:

```text
UNOBSERVED
  -> existing authenticated snapshot acquisition
SNAPSHOT_SEALED
  -> one bounded detached AST map
ASTS_DETACHED
  -> classify topology and normalize validation operands
TOPOLOGY_VALIDATED
  -> derive production and legacy closures from exact descriptor roots
CLOSURES_SEALED
  -> run every execution-reachability architecture policy
POLICIES_COMPLETE
  -> PASS or FAIL
```

For production and legacy independently:

1. Seed the exact descriptor roots in tuple order with root transitions.
2. Pop pending retained modules in first-discovered order.
3. Add every retained regular-package ancestor required by that module,
   outermost first; reject a retained plain-module ancestor.
4. Validate each normalized import operand in line/form/target order.
5. Add namespace-implied regular ancestors without inventing a namespace
   member.
6. Follow each exact retained target through its corresponding sorted public
   graph edge.
7. Enqueue a retained module only on first discovery.
8. Repeat until the queue is empty, then seal immutable path provenance.

The closure is complete before the import firewall or tenant UnitOfWork policy
runs. Any topology, resolution, graph-agreement, or resource failure forbids all
policy evaluation and returns a failed checker result; no partial map and no
public-map fallback is permitted.

Each retained module appears at most once in a pending queue. Membership is
bounded by the snapshot's maximum 512 sources, ancestry by its maximum depth,
known edges by its maximum 4,096 total edges, and validation work by its maximum
total AST nodes. Exceeding an existing snapshot ceiling refuses before closure;
the correction adds no caller-selectable or unbounded resource profile.

The transition has no side effect beyond existing diagnostic output. It reads
no source path, executes no repository module, writes no file, opens no network
or database connection, and changes no runtime state.

## 8. Private closure and diagnostic model

The implementation adds one checker-private immutable closure value containing
the production and legacy maps. Each map binds a retained module identity to an
ordered tuple of provenance transitions. A transition records only:

- kind: fixed root, explicit retained-module import, or required initializer;
- predecessor identity when present;
- target retained module identity; and
- source line only for an explicit import.

Namespace prefixes never appear as closure members. Initializer transitions do
not invent line zero or another source line. Diagnostics render the transition
kind and exact retained relative path; they render a line only when the public
graph supplies one. The object is private, ephemeral, and excluded from the
public snapshot equality and content digest.

The checker-private failure surface distinguishes at least:

- unresolved internally rooted import operand;
- retained plain-module/package ancestry conflict; and
- disagreement between normalized exact targets and the authenticated public
  graph.

These are architecture-check failures, not new public
`PythonSourceSnapshotRefusalCodeV1` members. A failure includes the retained
source relative path and import line when one exists, and it prevents policy
execution.

## 9. Invariants and acceptance criteria

- **PIR-001 — Complete regular-package ancestry.** Every retained module in a
  production or legacy closure causes every retained regular-package
  initializer on its dotted ancestry to be a member of the same closure.
- **PIR-002 — Fixed-point expansion.** Explicit retained-module imports from a
  newly included initializer or module are followed until neither closure can
  add another retained member.
- **PIR-003 — Namespace honesty.** A known namespace prefix contributes no
  executable member, while every retained regular-package ancestor around it
  is included. No synthetic AST, source, or path is invented.
- **PIR-004 — Fail-closed internal resolution.** A reachable relative or
  internally rooted module operand must resolve to a retained module or known
  namespace prefix. A required descendant beneath a retained plain module and
  an invalid relative base fail before policy evaluation.
- **PIR-005 — One explicit-edge authority.** Every retained-module import
  transition is backed by the exact public `(line, target)` edge. Validation
  syntax cannot silently add, remove, or override a public edge.
- **PIR-006 — Deterministic and bounded provenance.** Equal sealed snapshots,
  detached trees, and fixed root tuples produce equal closure membership and
  equal first-discovered transition paths within existing snapshot limits.
- **PIR-007 — No execution, reread, or partial fallback.** Closure derivation
  uses only sealed snapshot values and shared detached ASTs. Failure produces a
  nonzero checker result without repository execution, source reread, partial
  policy run, or fallback to explicit-only public reachability.
- **PIR-008 — Complete architecture-policy adoption.** The production and
  reverse import firewall use the corresponding import-execution closures, and
  the tenant UnitOfWork private-state scan uses the production closure.
- **PIR-009 — Public-contract preservation.** Public snapshot types, fields,
  descriptor values, explicit graph, public reachability maps, content digest,
  refusal vocabulary, external temporal consumers, and their accepted RFCs are
  unchanged.
- **PIR-010 — Honest claim limit.** Passing proves only retained static
  import-execution closure under the existing fixed roots. It does not prove
  complete repository, deployment, dynamic capability, or production
  composition governance.
- **PIR-011 — Closed change boundary.** Every semantic and mechanical change is
  within the four exact paths in this contract, and the inventory changes only
  as the mechanical consequence of added or renamed test nodes.

## 10. Required negative cases

Every case begins through the supported checker composition over a normal
temporary source tree with the exact fixed root identities. No case relies on
private-field mutation, module execution, or a fabricated production runtime
state.

| Invariant | Minimal counterexample | Required result |
| --- | --- | --- |
| PIR-001 | `kernel.api` is a fixed root, no incidental explicit edge reaches `kernel`, and `kernel/__init__.py` contains a forbidden dynamic-import form | `kernel` enters the production closure and the firewall fails at the initializer's real line |
| PIR-002 | A reached initializer imports `kernel.helper`, which imports `kernel.deep` containing a forbidden legacy-resource literal | both modules enter through fixed-point expansion and the deepest violation fails with complete provenance |
| PIR-003 | `kernel.api` imports `deployment.namespace.worker`; `deployment/__init__.py` exists, `deployment/namespace/__init__.py` does not, and the worker exists | `deployment` and the worker are members; no synthetic `deployment.namespace` member or AST exists |
| PIR-004 | A reached module executes `import deployment.missing` while `deployment` is internally rooted | closure derivation fails at that source line before any policy result |
| PIR-004 | `package.py` and `package/submodule.py` are retained and a fixed-root path reaches `package.submodule` | closure derivation fails for plain-module/package ancestry ambiguity |
| PIR-004 | A reached module uses an above-root relative import | closure derivation fails rather than treating it as external or empty |
| PIR-004 | A reached module imports `external_dependency.missing` and no retained module has that top-level name | the operand remains external and does not create a repository failure or member |
| PIR-005 | A normalized exact retained target lacks the matching public graph edge, represented by a focused trusted-code consistency fixture | the checker fails; it does not traverse a second graph or ignore the mismatch |
| PIR-006 | Equivalent trees are created in reverse directory order and contain cycles plus two root paths to the same helper | both closures and first-discovered transition paths are equal |
| PIR-007 | A reached initializer would write a sentinel if imported | analysis fails or passes according to syntax while the sentinel remains absent and no path is reread |
| PIR-007 | Internal resolution fails after another valid member was discovered | no firewall or tenant policy runs on the partial discovery and the checker returns nonzero |
| PIR-008 | `deployment/__init__.py` contains a forbidden production dynamic import or legacy resource | the production firewall fails even though the public production map remains explicit-only |
| PIR-008 | A legacy-reached initializer explicitly reaches a production composition module | the reverse firewall fails with initializer-aware provenance |
| PIR-008 | A newly included production initializer accesses `_TenantUnitOfWork__connection` | the tenant UnitOfWork scan reports the private-state access |
| PIR-009 | The post-change public snapshot is compared with the pre-change fixture for types, descriptor, graph, reachability, equality, and digest | every public value remains equal; any difference stops the pull request |
| PIR-009 | Existing temporal checks and temporal reachability fixtures run unchanged | they pass without path, contract, or assertion edits |
| PIR-010 | An unclassified operator or console entry point imports a module outside both fixed closures | it remains outside this claim and is recorded only as the separate governance Follow-up |
| PIR-011 | Any changed path is outside the exact allowlist, or inventory bytes change without a canonical node-ID change | merge stops |

## 11. Proposed architecture and smallest coherent change

### 11.1 Composition

`main()` continues to build exactly one authenticated source snapshot and one
detached AST mapping. It then derives one private object containing both fixed
closures. That object is passed to the two architecture-policy consumers that
currently interpret public reachability as execution coverage:

1. the production and reverse import firewall; and
2. the tenant UnitOfWork architecture scan.

Direct-import bounds continue to consume the public explicit graph. Provider,
profile-neutrality, source-budget, security-audit surface, and fixed-module
checks continue to consume their current exact modules or shared ASTs. The
temporal checker and its tests continue to consume the public snapshot under
their existing accepted contract.

### 11.2 Single normalization rule

One private import-operand normalizer owns relative-base calculation and
validation-only operands. The existing public graph remains authoritative for
exact retained-module edges. The implementation must either reuse the same
normalization primitive without changing public graph output or mechanically
cross-check every exact target; it may not leave two disagreeing parsers.

### 11.3 Diagnostics

Initializer-aware transition provenance replaces the assumption in
`_incoming_edge` that every reachability step is a public graph edge. Explicit
steps preserve the current file-and-line evidence. Initializer steps name the
required initializer path and transition kind without a fabricated line.

### 11.4 Why this is the minimum coherent design

Changing the public v1 snapshot would require an accepted snapshot amendment,
content-digest and authority change, temporal-owner review, and changes to
external consumers. Ignoring unresolved internal imports or using only ancestor
insertion over the old graph would leave namespace-only imports and malformed
internal operands under-modeled. A second filesystem walker or runtime import
would recreate the authority and execution defects that the sealed snapshot was
designed to remove.

One private closure over the existing sealed evidence is therefore the smallest
change that corrects the architecture checker while staying inside one trust
boundary.

## 12. Elegance audit

- Source inventories: one existing sealed inventory.
- Source-byte authorities: one retained byte string per module.
- Public explicit graphs: one, unchanged.
- Fixed root authorities: one authenticated descriptor.
- Private import-execution derivations: one object containing two fixed maps.
- Import-operand normalization rules: one.
- Architecture transition points: one derivation before policy evaluation.
- New public fields, refusal codes, roots, limits, services, caches, registries,
  compatibility shims, or runtime components: zero.
- Source rereads or repository-module executions: zero.
- Duplicated writable fields: zero.

Nothing can be deleted from the public v1 snapshot in this boundary. The
existing checker assumption that reachability paths contain only explicit graph
edges can be deleted from the two affected policy paths. A clean rewrite of the
snapshot or checker is not justified; the sealed snapshot is already the right
substrate and the affected consumer surface is narrow.

## 13. Pull request boundary

### 13.1 Primary boundary

The one primary trust boundary is architecture-checker accuracy for retained
regular-package initializer execution. Tests, this design record, and
mechanically regenerated test-node inventory may travel with it.

### 13.2 Exact technical allowlist

After valid decision approval, the named draft pull request may change exactly:

```text
docs/rfcs/OFARM_Architecture_Package_Initializer_Reachability_RFC_v0_1.md
conformance/rewrite_architecture_check.py
kernel/tests/test_rewrite_architecture_check.py
conformance/review_baseline_test_inventory.json
```

The RFC may change after approval only to record the compact AI-attested
approval evidence, mark the decision approved, and truthfully record the
implemented invariant mapping without changing the approved envelope. The
inventory may change only when canonical collection adds or renames focused
test node IDs.

The exact allowlist equals and therefore is a subset of the maximum card path
envelope. Before merge, both the local base-to-head diff and GitHub changed-file
list must contain no other path.

### 13.3 No stacked dependency

No stacked prerequisite is required. The accepted source-snapshot contract and
its current implementation are immutable inputs, not files in this pull
request.

### 13.4 Review boundaries and stops

Reviewers must not require this pull request to:

- modify the public snapshot or temporal consumers;
- add execution roots or dynamic capability governance;
- change runtime, database, provider, secret, output, deployment, or issue-#192
  behavior; or
- close the separate complete execution-root/source-capability Follow-up.

If implementation requires any such change, or any fifth path, work stops for a
new decision version or separate owner. A cross-boundary review fix is not
appended merely to clear a Blocker.

Issue #334 may close only when the approved implementation has merged and the
architecture-policy execution closure, negative cases, exact-head review, and
required verification all pass. This Phase A contract alone does not close it.

## 14. Traceability and verification

| Invariant | Owning implementation | Negative evidence | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| PIR-001 | private topology classifier and closure builder | fixed root with otherwise-unreached forbidden initializer | every retained regular ancestor appears and is scanned | focused checker tests |
| PIR-002 | one first-discovered work queue | initializer-to-helper-to-deep chain and cycle | complete fixed point with no duplicate processing | focused checker tests |
| PIR-003 | namespace-prefix classifier | nested namespace between regular ancestor and worker | no synthetic namespace member; regular ancestor included | focused checker tests |
| PIR-004 | private import-operand validator | missing internal base, above-root relative import, plain-module ancestor, allowed external import | all invalid internal cases fail before policies; external case remains external | focused checker tests and checker execution |
| PIR-005 | public-edge agreement check | exact normalized target without corresponding edge | no independently authoritative retained-module transition | focused consistency tests plus existing graph tests |
| PIR-006 | ordered immutable transition paths | reversed enumeration, cycles, competing root paths | equal membership and first provenance | deterministic snapshot/closure tests |
| PIR-007 | snapshot/AST-only composition and fail-before-policy gate | sentinel initializer and partial-discovery failure | no sentinel, reread, execution, or partial fallback | focused tests plus existing one-snapshot/no-reread test |
| PIR-008 | import firewall and tenant UnitOfWork composition | production initializer, legacy initializer, tenant private access | all three policy families consume corrected closures | focused policy tests and full architecture checker |
| PIR-009 | unchanged public snapshot code contract and external consumers | exact public-value and temporal regression fixtures | public contract and temporal suites unchanged and green | focused snapshot tests, temporal tests, temporal checker |
| PIR-010 | RFC claim language and final scope report | unclassified operator entry point | no complete-governance or production claim | diff and review |
| PIR-011 | exact path and inventory gates | fifth path or unexplained inventory delta | allowlist equality and canonical inventory reproduction | Git diff, GitHub file list, inventory comparison |

### 14.1 Cheap local Phase A checks

Before each Phase A commit:

- `python3 conformance/ofarm_pkg_contract_check.py`;
- Markdown/path inspection;
- `git diff --check`; and
- exact one-path Phase A diff verification.

No expensive hosted baseline is admitted or monitored during Phase A review.

### 14.2 Required Phase B local checks

After valid approval and implementation, use CPython 3.12.13 for:

- the focused `kernel/tests/test_rewrite_architecture_check.py` suite;
- existing snapshot public-contract and deterministic graph tests;
- unchanged temporal carrier/governance tests that consume public reachability;
- `python3 conformance/rewrite_architecture_check.py`;
- `python3 conformance/temporal_contract_candidate_check.py`;
- Ruff format and lint for changed Python paths;
- Python compilation for changed Python paths;
- canonical test-node collection and inventory reproduction;
- `python3 conformance/ofarm_pkg_contract_check.py` before every commit; and
- `git diff --check`, exact allowlist, and RFC status/evidence checks.

If the required exact CPython profile is unavailable locally, the check is
reported unavailable rather than simulated under another version.

### 14.3 Review-before-baseline sequence

1. Keep the pull request Draft and `REVIEW_PENDING` for every new head.
2. Run only mandatory and cheap local checks before review.
3. Perform at most one unconstrained Phase A design review at an exact head;
   later reviews are limited to fixes and affected invariants unless new
   evidence demonstrates broader unsafety.
4. Display a complete live decision card only after the reviewed Phase A head
   has zero design Blockers.
5. Begin Phase B only after the exact later same-task approval sentence.
6. Obtain one zero-Blocker exact-head Phase B content review before creating any
   baseline admission comment or monitoring an expensive hosted run.
7. After valid admission, run one required hosted source baseline and its
   trusted publication workflow.
8. Recheck approval, cancellation, exact paths, review, checks, scope report,
   and merge stop immediately before merge.

Automatically started workflows may finish unattended. They create no review,
approval, admission, merge, production, or deployment authority.

## 15. Pre-deployment decision and approval workflow

This proposed contract is recorded and technically reviewed in the one draft
pull request named at the top of this file. Only after its exact reviewed head
has zero design Blockers may the AI display one complete live decision card in
the current Codex task.

The card must state the decision identity and version, problem, recommended
decision, primary trust boundary, authority map, primary risk and bound,
permitted effects, non-effects, decision-level invariants, maximum path
envelope, named draft pull request, verification gates, reapproval triggers,
provisional posture, and this exact approval form:

```text
I approve OFARM2 decision ISSUE334-ARCHITECTURE-PACKAGE-INITIALIZER-REACHABILITY-001 version 1.
```

Approval is valid only when the entire visible text of a later task-user
message in the same Codex task equals that sentence. Generic approval, “go,” a
GitHub action, credentials, review, comment, tool output, AI message, delegation,
another task, or a summary does not approve Phase B.

Before recognizing approval, the AI must verify that the unique live card and
later user message remain directly retrievable with stable references, remain
in the required order, name this already-created draft pull request, and have
not been superseded or followed by a stop-like task-user message.

After valid approval, the same pull request may implement, test, document,
regenerate mechanical inventory evidence, commit, push, address only
in-boundary Blockers, obtain exact-head review and admission, run required
checks, post the compact scope report, and merge when every gate passes. That
standing authority never extends outside the card envelope and this contract's
exact allowlist.

The RFC must then record compact AI-attested evidence containing decision and
version, Codex task/card/approval stable references, the exact sentence, the
observed user role and ordering, the named PR, and the provisional-evidence
limit. The user message remains authority; repository text is evidence only.

## 16. Reapproval triggers, provisional posture, and stop conditions

### 16.1 Reapproval triggers

A new decision version and exact approval are required if any of these changes:

- material problem, permitted effect, non-effect, trust boundary, authority map,
  invariant, or claim limit;
- maximum path envelope or named pull request;
- public snapshot interface, semantics, authority, digest, or refusal behavior;
- temporal-consumer behavior;
- fixed root selection or execution-entry inventory;
- irreversible, runtime, database, deployment, production, secret, provider,
  output-custody, or issue-#192 effect; or
- any ambiguity about whether implementation preserves this envelope.

Meaning-preserving wording, in-envelope implementation, focused tests,
mechanical inventory regeneration, and Blocker fixes that preserve every
decision-bearing field do not require another approval, but every new head
requires affected review and checks.

### 16.2 Provisional design record

**Not provisional.** Within the stated static trust model, regular-package
initializer inclusion and fail-closed internal topology are intended to remain
the architecture checker's stable behavior.

The same-task AI-assisted approval transport is provisional repository-
development authority. It must be replaced by independently human-controlled
and independently verifiable approval or signing before deployment. This
decision itself creates no deployment path.

### 16.3 Immediate stop conditions

Work stops before:

1. Phase B implementation without the exact valid approval message;
2. a fifth changed path or any change outside the technical allowlist;
3. changing public snapshot or temporal semantics;
4. adding roots, runtime discovery, dynamic-import inference, source execution,
   another walker, or a path reread;
5. accepting a partial closure, fallback map, unresolved internal operand, or
   ambiguous package ancestry;
6. admitting or monitoring an expensive hosted baseline before zero-Blocker
   exact-head Phase B review;
7. waiving a demonstrated Blocker;
8. changing runtime, database, provider, secret, output, deployment, production,
   certification, current-compliance, or issue-#192 authority; or
9. continuing after a later task-user stop, cancellation, or withdrawal.

## 17. Review disposition and merge stop

Open decisions: none.

- **Phase A design Blockers:** review pending.
- **Follow-ups:** complete execution-root/source-capability governance remains a
  separate boundary; no new issue is created by this contract.
- **Preferences:** none recorded.
- **Cross-boundary exception:** none.
- **Phase B:** unauthorized.
- **Production composition:** unauthorized and non-deployable.

The pull request must remain Draft and must not implement while Phase A review
is pending or reports a Blocker. After a zero-Blocker exact-head Phase A review,
the AI may display the complete live card and wait for the exact approval
sentence.

After approval and Phase B, merge only when every invariant passes, the one
unconstrained exact-head Phase B review reports zero Blockers, required local
and admitted hosted checks pass, both exact-path checks pass, the compact scope
report describes the exact head, approval remains live and bound to the named
PR, and no later cancellation or revocation exists. New ideas, Preferences, and
non-blocking hardening remain Follow-ups and do not widen or reopen review.

No result of this pull request establishes production readiness, deployment or
release authority, certification, provider or secret custody, current
compliance, complete execution governance, or authority to reopen or close
issue #192.
