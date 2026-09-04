# OFARM2 Profile-Runtime Service Contract Execution — Phase A Contract v0.1

**Status:** proposed Phase A contract; documentation-only, unapproved, and
without runtime effect

**Contract identity:**
`ofarm2.profile-runtime-service-contract-execution.issue160.v0.1`

**Date:** 2026-09-04

**Primary implementation ticket:** #160

**Base commit:** `0c55f5cc6665ffef4c57591dafe014ad9bc44524`

**Merged prerequisites:** #159, #239, #240, and #241

**Named draft pull request:** pending assignment; the assigned number must be
recorded in this contract before exact-head Phase A review

**Primary trust boundary:** runtime integration and readiness at the private
profile-runtime service/composition boundary

**Intended pull-request boundary:** Phase A changes only this RFC. After exact-
head Phase A review and explicit task-user approval, the same named draft pull
request may implement only the private service contracts, common composition
validation, generic stage result validation, synthetic non-SI evidence, focused
tests, and mechanically required test inventory or architecture checks defined
here.

## 1. Problem and goal

Generic orchestration currently makes stronger calls than the private service
protocols declare. `MaterializationGate` supplies `trigger_source_ref`,
`farm_scope_ref`, and `reason_code` to `invalidate_for_sources(...)`, but
`ProfileMaterializer` and the synthetic non-SI materializer do not declare or
accept those keywords. The generic applicability and materialization stages
also index provider-returned dictionaries without first requiring the exact
minimal references that their success logs consume.

Composition has a second path disagreement. Provider-loaded graphs pass
`profile_runtime_provider._validate_services(...)`, while an explicitly
injected `GatePipeline(runtime_services=...)` graph is checked only for the
outer bundle type and descriptor identity. A cross-wired graph can therefore
be accepted by the production composition root and fail only after governed
work begins.

Inspection at the base commit reproduced the three concrete gaps without
editing runtime code:

- the real `ProfileApplicabilityGate` raises `KeyError('contextSnapshotId')`
  on the current synthetic result;
- the real `MaterializationGate` raises `TypeError` when it supplies
  `trigger_source_ref` to the current synthetic materializer; and
- `GatePipeline` accepts an injected exact `ProfileRuntimeServices` value whose
  materialization specification is not the materializer's specification.

This task establishes one executable private boundary:

1. every declared callable accepts the call shape used by its existing
   consumer;
2. provider-loaded and explicitly injected graphs cross the same complete
   composition validator;
3. generic stages validate the minimal result fields before recording success;
4. a synthetic non-SI graph executes through the real generic applicability
   and materialization stages; and
5. unchanged SI behavior, receipts, outputs, identities, and gate order remain
   assertion-equivalent.

## 2. Learning value

The change proves that the existing structural service seam is an executable
composition contract before a second runtime provider is registered. It
reduces the demonstrated risk of late `TypeError`, `KeyError`, cross-profile
execution, or misleading gate success after a commit has entered the governed
transaction.

It also validates the architectural decision that one private, capability-
specific graph is sufficient. No public plugin API, universal country model,
dynamic discovery mechanism, or profile composition layer is needed.

## 3. Non-goals

Neither Phase A nor its approved implementation will:

- change OFARM baseline law, an accepted RFC, an extracted contract, a schema,
  a migration, or `reference/**`;
- accept, promote, extract, or mark current/default canonical OFARM PRs #11,
  #17, #20, or #23;
- reopen or implement blocked issue #353 or PR #359;
- add a public extension SDK, plugin API, `Country` abstraction, mutable
  registry, capability bag, dynamic discovery, descriptor-controlled import,
  or profile composition;
- change provider source import, bytecode, cache, or module authority settled
  by D22 and #240;
- add, edit, enable, select, route, or execute a Serbian descriptor, provider,
  adapter, policy, validator, fixture, materializer, output assembler, view,
  manifest, or evidence file;
- edit `profile_rs_organic_crop` runtime artifacts;
- change the active SI descriptor, policy values, evidence floors, reference-
  source behavior, adapter behavior, materialization semantics, output claims,
  output identities, active defaults, or Store selection semantics;
- change `ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES`, a Capability Manifest,
  `ActiveArtifactSet`, evidence lane, capability claim, activation rule, or
  production-readiness result;
- restore `PROFILE_EXECUTED_EVIDENCE` admission withdrawn by D23;
- add a canonical record type, reason code, result schema, or durable developer-
  wiring error record;
- redesign the provider registry, materializer, output assembly, profile
  routing, transaction owner, database, authorization, deployment, or security-
  audit boundary; or
- claim second-profile, multi-profile, country-compliance, or production
  readiness.

Issue #161 remains a later follow-up and must be rewritten only after #160 is
implemented, reviewed, and merged.

## 4. Trust model

### Protected assets

- the exact relationship between the Store-bound profile descriptor and every
  service in the executable graph;
- the materialization and output specifications actually used by their bound
  service instances;
- profile policy identity and the minimum recognized rule set;
- the integrity and ordering of `APPLICABLE` and `UPDATED` gate entries;
- transaction rollback when a provider violates its runtime result contract;
- SI materialization identities, outputs, receipts, and gate order for
  unchanged inputs;
- profile neutrality of the generic Kernel stages; and
- the single-active-SI and descriptorless/unregistered Serbia posture.

### Trusted components

- a startup-complete, tenant-bound `Store` and its exact
  `Store.active_descriptor`;
- `resolve_bound_descriptor(...)` for selecting that descriptor;
- the code-owned registration and source-only import posture already settled by
  #159, D22, and #240;
- the exact `ProfileRuntimeServices`, `MaterializationSpecification`,
  `OutputSpecification`, and `ProfileManifestEvidenceSpecification` types;
- one private service-graph validator after it has accepted a graph;
- generic gate ordering and the enclosing `Store.serialized_tx()` transaction;
  and
- reviewed in-process Python source and ordinary Python signature semantics.

### Untrusted actors and inputs

- every object returned by an admitted provider factory until common graph
  validation succeeds;
- every explicitly injected `runtime_services` object until the same validation
  succeeds;
- service attributes, descriptor bindings, specification bindings, materializer
  bindings, policy refs, recognized rule refs, callables, and callable
  signatures presented by those candidate graphs;
- applicability and materialization values returned at runtime; and
- missing, empty, non-string, or otherwise malformed references in those
  runtime results.

A provider is trusted to execute only after its source and graph have crossed
their existing admission boundaries. It is not trusted to self-attest that its
graph is coherent or that a returned mapping contains the fields a generic gate
will log.

### Excluded compromise capabilities

Arbitrary in-process mutation after graph validation, private-field mutation,
runtime monkeypatching, compromised Python or third-party dependencies,
operator compromise, and concurrent filesystem or module substitution are out
of scope. D22's exclusions for provider import remain unchanged. Local source
substitution before provider admission remains owned by #240, not this task.

The graph contains mutable service instances, but validation is a composition-
time boundary rather than a continuing integrity monitor. Revalidating before
every call would duplicate authority and would not defend against the excluded
arbitrary in-process mutation capability.

Object identity checks here bind one in-process composition graph; they are not
a substitute for source, process, operator, or filesystem trust. Exact identity
is required so a bundle cannot name one descriptor or specification while the
executing service retains an equal-but-distinct object. This is graph-coherence
proof under the current private composition model, not external attestation.

## 5. Authority map

| Decision | Sole authority after implementation | Non-authoritative inputs or fallbacks |
| --- | --- | --- |
| Active descriptor | `Store.active_descriptor` returned by `resolve_bound_descriptor(...)` | provider claims, equal copies, injected bundle claims |
| Provider and factory source | existing code-owned registration plus D22/#240 import posture | descriptor paths, dynamic imports, test switches |
| Complete graph admission | one private validator in `kernel/profile_runtime_provider.py` | Protocol annotations alone, provider self-attestation, `GatePipeline`'s current two-field shortcut |
| Materialization identities | the provider-owned exact `MaterializationSpecification` instance bound to its materializer | duplicate or merely equal specifications |
| Output identities | the provider-owned exact `OutputSpecification` instance bound to its output assembler | duplicate or merely equal specifications |
| Output materializer | the exact materializer instance carried by the admitted bundle | another compatible materializer instance |
| Profile policy identity | Store-bound descriptor `evidence_policy_ref` plus the descriptor-derived required rule refs | config-backed policy fallbacks, provider aliases |
| Callable compatibility | Python's inspected bound-call signature against the closed private call matrix in this contract | `runtime_checkable` presence checks alone, annotations, method-name presence without callability |
| Applicability success ref | generic `ProfileApplicabilityGate` validation of returned `contextSnapshotId` | provider return annotation or truthiness of the outer result |
| Materialization success refs | generic `MaterializationGate` validation of returned `basisRef` and `snapshotRef` | provider return annotation or incidental dictionary indexing |
| Gate success ordering | generic stages after result validation | provider logging, caller claims, inferred success |

The provider loader's existing `_validate_services(...)` logic becomes the one
reusable validator rather than a second authority. The partial injected-graph
condition in `GatePipeline` is deleted. Both paths call the same validator with
the exact Store-bound descriptor.

`runtime_checkable` protocols remain useful type documentation and structural
screening, but they do not inspect signatures and therefore do not own callable
admission. No legacy fallback or alternate validation path remains.

## 6. State machine and ordering

### 6.1 Composition

The only valid composition states are:

```text
STORE_READY
  -> STORE_BOUND_DESCRIPTOR
  -> PROVIDER_SOURCE_VERIFIED -> FACTORY_RESULT_CANDIDATE
       or
     EXPLICIT_INJECTION_CANDIDATE
  -> EXACT_OUTER_AND_SPECIFICATION_TYPES
  -> REQUIRED_SERVICE_SHAPES_AND_CALL_SIGNATURES
  -> DESCRIPTOR_SPECIFICATION_MATERIALIZER_POLICY_CROSS_BINDINGS
  -> COMPOSED
```

Any failed transition raises `ProfileRuntimeError` and no `GatePipeline` is
constructed. The provider path verifies and imports source under the existing
D22 boundary before factory construction; this contract does not reorder or
weaken that work. The explicit path performs no provider import.

Validation order is fail-closed:

1. require the exact `ProfileRuntimeServices` outer type and exact Store-bound
   descriptor identity;
2. require exact trusted specification value types;
3. require each capability service and every closed-matrix callable;
4. prove each callable can bind the complete supported call shape without
   invoking it;
5. require descriptor, specification, and materializer object cross-bindings;
6. require the policy ref to equal the descriptor evidence-policy ref; and
7. require the policy service's recognized refs to include the descriptor's
   evidence policy, profile, pack, and code-binding profile refs.

Missing attributes, non-callables, opaque or incompatible signatures, and
inspection failures are normalized to `ProfileRuntimeError`. Provider methods
are not invoked during composition.

`GatePipeline.__init__` completes validation before assigning the graph for
use and before `commit()` can enter `Store.serialized_tx()`. A refused injected
graph therefore starts no transaction and performs no gate, materialization,
output, or durable-record side effect.

### 6.2 Closed callable matrix

Signature admission proves that a bound callable can accept these existing
consumer shapes. It does not require exact parameter annotations, exact default
values, or rejection of additional optional parameters.

| Capability | Required accepted call shape |
| --- | --- |
| policy evidence | `evidence_policy(supported_checks=value)` |
| policy validation | `validation_policy()` |
| context assembly | `assemble(cur, farm_ref, target_twin=value, evaluation_time_policy=value)` |
| source invalidation | `invalidate_for_sources(cur, source_refs, trigger_family=value, trigger_source_ref=value, farm_scope_ref=value, reason_code=value)` |
| recomputation | `recompute(cur, farm_ref, twin=value, time_policy=value)` |
| materialization resolution | `resolve_for_use(cur, farm_ref, twin=value, use_class=value, time_policy=value, required_freshness=value, high_consequence=value, recompute_if_needed=value)` |
| registry reverification | `run(context)` |
| passport output | `passport_view(farm_ref, requesting_party_ref, allow_recompute=value)` |
| frozen output | `freeze_document_assembly(farm_ref, requesting_party_ref, window_start, window_end, as_submission=value)` |

`inspect.signature(bound_callable).bind(...)` or an assertion-equivalent
private mechanism is sufficient. A callable with an uninspectable signature is
refused because compatibility is not demonstrated. The matrix is private and
closed; adding a capability requires a new reviewed change.

### 6.3 Applicability result

Inside `GatePipeline.commit()`'s existing serialized transaction:

```text
CONTEXT_ASSEMBLER_CALLED
  -> RESULT_RECEIVED
  -> NON_EMPTY_STRING_CONTEXT_SNAPSHOT_ID
  -> APPLICABLE_LOGGED
  -> GATE_PASS
```

`ContextNotReconstructible` keeps its existing governed
`NOT_APPLICABLE/PROFILE_NOT_ACTIVE` path. Any other result that lacks a non-
empty built-in string `contextSnapshotId` is an implementation contract
failure: `ProfileRuntimeError` escapes, the transaction rolls back, and no
`APPLICABLE` entry commits. No new domain reason code or refusal record is
created.

### 6.4 Materialization result

Only after the unchanged gate chain sets `PROMOTE_ACCEPTED`:

```text
INVALIDATE_WITH_COMPLETE_KEYWORDS
  -> RECOMPUTE
  -> NON_EMPTY_STRING_BASIS_REF
  -> NON_EMPTY_STRING_SNAPSHOT_REF
  -> MATERIALIZATION_TRIGGERED_TRUE
  -> UPDATED_LOGGED
  -> GATE_PASS
```

If either ref is missing, empty, or not a built-in string,
`ProfileRuntimeError` escapes before the success flag and log. The enclosing
serialized transaction rolls back invalidation, materialization, promotion,
gate-log, trace, and other writes from that attempt. This task adds no partial-
commit or compensating path.

### 6.5 Time-of-check/time-of-use boundary

Composition validation occurs once immediately before a graph becomes usable.
The graph object is then retained by that pipeline or runtime composition root.
Ordinary calls occur later inside their existing transaction boundaries.
Arbitrary mutation between validation and use is excluded by the trust model;
there is no new lock, hash, copy, proxy, cache, or per-call revalidation.

Result validation is deliberately at time of use because result content cannot
be proven from a callable signature. The required references are checked in the
same transaction and immediately before the generic success side effect.

## 7. Invariants and acceptance criteria

- **PRSC-001 — Executable declared calls.** Every callable in the closed matrix
  is present, callable, and signature-compatible at composition. In particular,
  `ProfileMaterializer.invalidate_for_sources(...)` declares and accepts
  `trigger_family`, `trigger_source_ref`, `farm_scope_ref`, and `reason_code`.
- **PRSC-002 — Exact descriptor and trusted values.** Only the exact
  `ProfileRuntimeServices` type, exact Store-bound descriptor object, and exact
  trusted specification value types can compose.
- **PRSC-003 — One coherent graph.** Policy, context, materializer, and output
  services bind the Store descriptor; the materializer and output assembler
  bind the bundle's exact specifications; the output assembler binds the
  bundle's exact materializer; and policy ref plus required recognized rule refs
  match the descriptor.
- **PRSC-004 — One composition validator.** Provider factory results and
  explicitly injected graphs pass the same complete private validator. An
  injected refusal occurs before a transaction can start.
- **PRSC-005 — Truthful applicability success.** `APPLICABLE` is logged only
  after the assembler returns a non-empty built-in string
  `contextSnapshotId`.
- **PRSC-006 — Truthful materialization success.** `UPDATED` is logged and
  `materialization_triggered` becomes true only after recomputation returns
  non-empty built-in string `basisRef` and `snapshotRef` values.
- **PRSC-007 — Explicit implementation failures.** Malformed graphs,
  incompatible signatures, and malformed consumed result shapes raise
  `ProfileRuntimeError`, not incidental `AttributeError`, `TypeError`, or
  `KeyError`; no misleading generic gate success is committed.
- **PRSC-008 — Executable profile neutrality.** A test-only synthetic non-SI
  graph passes real `ProfileApplicabilityGate` and `MaterializationGate`
  execution, receives every invalidation keyword, and produces only synthetic
  profile-local context, materialization, output, package, policy, view, and
  result-shape identifiers. It never enters the production registration tuple.
- **PRSC-009 — SI assertion equivalence.** For unchanged inputs, provider-
  loaded and explicitly injected SI services preserve decision outcomes,
  problems, gate names and order, materialization key/specification identities,
  basis/snapshot reference families, output identities and qualifications, and
  receipt structure. Existing SI tests remain green without changing SI
  runtime artifacts or policy values.
- **PRSC-010 — Closed activation and authority posture.** Active runtime stays
  single-active-SI; Serbia remains descriptorless, unregistered, and
  unexecutable; no public API, discovery, composition, schema, migration,
  manifest, `ActiveArtifactSet`, evidence-lane, capability, activation,
  canonical-law, or production-readiness authority changes.

## 8. Production-reachable negative cases

Each counterexample begins at an existing loader, composition, or commit path.
Test-only service implementations are supplied through the already supported
private provider-registration seam or explicit-injection argument; no private
field mutation, mutable production registry, or production switch is used.

| Invariant | Supported entry point and counterexample | Required result |
| --- | --- | --- |
| PRSC-001 | `load_profile_runtime_services(...)` receives an admitted test provider whose invalidator omits `reason_code` or whose context assembler requires an extra positional argument | composition raises `ProfileRuntimeError` before returning services |
| PRSC-002 | `GatePipeline(store, runtime_services=...)` receives a lookalike bundle, an equal-but-distinct descriptor, or a non-trusted specification value | constructor raises `ProfileRuntimeError`; no pipeline exists |
| PRSC-003 | `GatePipeline(...)` receives an exact dataclass with a foreign service descriptor, a different materialization/output specification instance, a different output materializer, wrong policy ref, or one missing required recognized rule ref | constructor raises `ProfileRuntimeError` before transaction entry |
| PRSC-004 | the same malformed graph is returned by the provider loader and supplied explicitly | both paths refuse through the common validator; an injected-store transaction counter remains zero |
| PRSC-005 | `GatePipeline.commit(...)` reaches a signature-compatible context assembler returning `{}`, `{"contextSnapshotId": ""}`, or a non-string ref | `ProfileRuntimeError`; transaction rollback; no committed `APPLICABLE` entry or promotion trace from the attempt |
| PRSC-006 | an accepted commit reaches a signature-compatible materializer returning a missing, empty, or non-string `basisRef` or `snapshotRef` | `ProfileRuntimeError`; no `UPDATED` entry, false success flag, or committed promotion/materialization effects |
| PRSC-007 | any required service attribute is absent/non-callable, signature inspection cannot prove binding, or a consumed result is malformed | one explicit `ProfileRuntimeError`; no incidental exception type becomes the boundary contract |
| PRSC-008 | the synthetic provider is loaded and its real generic stages execute | both stages pass; the observed invalidation arguments are complete; recursive result/log inspection finds no SI or production package identifier; production registrations remain unchanged |
| PRSC-009 | the same SI scenario is composed through default loading and explicit injection | stable semantic assertions, identities, outputs, receipts, and gate order are equivalent after normalizing only minted IDs/timestamps that were already volatile |
| PRSC-010 | production loader or route is asked for `profile_rs_organic_crop`, or a test inspects allowed/active registrations | no descriptor, registration, route, or execution exists; only `profile_si_ffs` remains active and registered |

The full commit-path cases for PRSC-005 and PRSC-006 must inspect committed
state after the raised error, not merely an in-memory log list, so rollback is
demonstrated. Small direct-stage tests may additionally pin the exact pre-log
ordering.

## 9. Proposed architecture and smallest change

### 9.1 Private minimum result types

`kernel/profile_runtime_services.py` adds two narrow `TypedDict` contracts or
assertion-equivalent private static shapes:

- applicability requires `contextSnapshotId: str`; and
- a materialization update requires `basisRef: str` and `snapshotRef: str`.

`ProfileContextAssembler.assemble(...)` and
`ProfileMaterializer.recompute(...)` return those minimum shapes. Richer SI
dictionaries remain valid and unchanged. The materializer protocol adds the
three currently missing invalidation keywords and keeps the existing defaults
and capability-specific methods.

### 9.2 One graph validator

`kernel/profile_runtime_provider.py` refactors the existing validator into one
reusable private function. It retains every current exact-type, identity,
cross-binding, policy-ref, and required-rule check, then adds closed-matrix
callability and signature binding. It converts inspection/admission failures to
`ProfileRuntimeError` without invoking provider methods.

`load_profile_runtime_services(...)` uses it after factory construction.
`GatePipeline` imports and uses the same function whenever services are
explicitly supplied. The current partial `elif` check is deleted rather than
kept as a compatibility layer.

This does not move or duplicate D22 provider import authority. The validator
accepts a constructed graph; it does not discover, import, register, or select
providers.

### 9.3 Generic result validation

`kernel/stages.py` owns one small private helper that extracts a required result
ref, requires a mapping shape and non-empty built-in string field, and raises
`ProfileRuntimeError` with a developer-facing message. Both generic stages call
it before their success state/log side effects. Domain refusal handling remains
unchanged.

### 9.4 Synthetic evidence and SI preservation

`kernel/tests/_synthetic_profile_runtime.py` is upgraded to the exact private
contract. Its assembler and materializer return synthetic refs, and its
materializer exposes test-only observation of the complete invalidation call.
It remains absent from `_REGISTRATIONS`.

Focused tests exercise actual generic stages, both composition paths, hostile
cross-wires/signatures/results, transaction rollback, SI equivalence, legacy-
policy exclusion, and Serbia refusal. Existing Kernel and architecture tests
provide the broad regression boundary.

This is the minimum coherent design because each defect is corrected at its
owner:

- declared shape in the private protocol;
- graph coherence at composition;
- returned-value truth at the generic consumer; and
- neutrality through executable test evidence.

No new module, registry, schema, durable type, adapter, service abstraction, or
public surface is needed.

## 10. Elegance audit

- Store-bound descriptor sources of truth: one.
- Provider source/import authorities: one existing D22/#240 path, unchanged.
- Complete graph validators: one.
- Composition entry points: two, converging on that validator.
- Applicability success-transition points: one generic gate.
- Materialization success-transition points: one generic gate.
- Runtime result-reference validation helpers: one private consumer helper.
- New mutable production state: none.
- New public abstractions: none.
- Compatibility surfaces: none.
- Duplicate state: none; `TypedDict` shapes document existing returned fields
  and do not create runtime copies.

Deletable duplication is the partial type/descriptor validation branch in
`GatePipeline`. Incidental dictionary indexing at the two success log sites is
replaced by explicit extraction. Existing richer SI result fields are neither
copied nor narrowed.

The profile-runtime architecture group is 867 lines against its existing 900-
line budget at the base commit. Phase B must refactor compactly within that
existing group budget; it must not add a framework module or relax the budget
to hide unnecessary growth. The services module must also remain within its
existing 250-line budget. If the approved design cannot fit after deleting the
duplicate validation branch, implementation stops for an amendment rather than
silently widening architecture policy.

A clean rewrite of the provider loader, materializer, output assembler, or
profile router is not justified. The present graph is the correct unit; its
contracts and admission path need completion.

## 11. Pull request boundary

Phase A changes only:

- `docs/rfcs/OFARM2_Profile_Runtime_Service_Contract_Execution_RFC_v0_1.md`.

After exact-head Phase A review and explicit task-user approval, the same named
draft PR may change only:

- `kernel/profile_runtime_services.py`;
- `kernel/profile_runtime_provider.py`;
- `kernel/gates.py`;
- `kernel/stages.py`;
- `kernel/tests/_synthetic_profile_runtime.py`;
- `kernel/tests/test_profile_runtime_services.py`;
- `kernel/tests/test_profile_runtime_neutrality.py`;
- this RFC to record approved/reviewed implementation status; and
- narrowly necessary mechanical test inventory or architecture-check files if
  the exact test additions require them.

No change to architecture budgets is expected or authorized by this contract.
No SI provider-owned runtime artifact is expected to change. A test-support
edit outside the named files requires proof that it is purely mechanical and
inside this boundary; otherwise implementation stops for an amendment.

The merged prerequisites #159, #239, #240, and #241 are contained in the base.
This task does not modify their authority. Blocked PR #359/issue #353 and the
Phase-A-only canonical OFARM PRs #11, #17, #20, and #23 are neither
prerequisites nor implementation authority for this task.

Reviewers must not require this PR to add a second production provider,
activate Serbia, change provider import posture, introduce public extension
machinery, change contracts or manifests, or prove production readiness.

The only linked follow-up is #161 after this issue is merged. Any independent
authority, database, deployment, security-audit, manifest, evidence, canonical-
law, or profile-activation finding becomes a separate prerequisite or follow-
up and cannot be appended to this PR.

## 12. Provisional design record

Not provisional.

The private call matrix and result minima are the calls and fields consumed by
the existing runtime. The common validator is the permanent single composition
authority for this graph model. A future new capability must extend this
private contract through a separately reviewed change; it does not justify a
generic plugin framework now.

This is pre-deployment implementation work and does not authorize deployment or
claim production readiness.

## 13. Traceability and verification

| Invariant | Owning code | Required negative/neutral test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| PRSC-001 | `ProfileMaterializer`; private signature validator | missing keyword, extra required arg, absent/non-callable method | both composition paths reject incompatible signatures | focused two-module pytest |
| PRSC-002 | common validator; `GatePipeline.__init__` | lookalike outer type, copied descriptor, wrong spec type | `ProfileRuntimeError` before pipeline construction | focused two-module pytest |
| PRSC-003 | common validator | each descriptor/spec/materializer/output/policy/rule cross-wire | every graph mismatch refuses at composition | focused two-module pytest |
| PRSC-004 | loader and explicit-injection branch | same validator reached from both; injected transaction counter stays zero | equivalent `ProfileRuntimeError` admission behavior | focused two-module pytest |
| PRSC-005 | `ProfileApplicabilityGate`; result-ref helper | missing/empty/non-string context ref | no `APPLICABLE`; full transaction rollback | focused hostile tests plus complete Kernel suite |
| PRSC-006 | `MaterializationGate`; result-ref helper | missing/empty/non-string basis or snapshot ref | no success flag/`UPDATED`; full transaction rollback | focused hostile tests plus complete Kernel suite |
| PRSC-007 | common validator and result-ref helper | opaque/incompatible callable and malformed runtime mappings | only `ProfileRuntimeError` crosses the boundary | focused two-module pytest |
| PRSC-008 | synthetic fixture; real generic stages | execute applicability and materialization; recursive identifier scan | synthetic refs logged; complete invalidation args observed; no SI leakage or production registration | `test_profile_runtime_neutrality.py` |
| PRSC-009 | unchanged SI provider and generic orchestration | default-loaded versus explicit-injected SI scenario | stable normalized results, materializations, outputs, receipts, and gate order; full Kernel suite passes | focused equivalence test plus complete Kernel suite |
| PRSC-010 | existing registration/selection/architecture authorities | Serbia load/route refusal; registration/default assertions; forbidden-file diff | single-active-SI and all non-effects preserved | architecture, manifest, extraction, package, and diff checks |

### 13.1 Phase A verification

Before every Phase A commit:

```sh
python3 conformance/ofarm_pkg_contract_check.py
```

The exact Phase A head must also show:

```sh
python3 conformance/rewrite_architecture_check.py
python3 conformance/ofarm_profile_extraction_consistency_check.py
python3 -m kernel.manifest --verify-generated
git diff --check
git diff --name-only origin/main...HEAD
git status --short
```

The changed-file list must contain only this RFC. Manifest verification may
require local PostgreSQL; unavailable evidence must be reported, not replaced
with a fixture claim.

Base inspection used the repository-pinned Python 3.14.5 environment available
at
`/Users/einstein/Documents/Codex/OFARM2-implementation/worktrees/issue-171/.venv/bin/python`
because this isolated worktree has no `.venv`. The untouched focused suite
reported 13 passed, 3 failed, and 19 errors; every failure/error was database
setup blocked by the overlong default Unix-socket path, and no active
`.s.PGSQL.54317` socket was available. This is not test acceptance evidence.

### 13.2 Required Phase B verification

Run and report the exact issue commands, using `.venv/bin/python` when
available or the exact repository-supported interpreter path otherwise:

```sh
.venv/bin/python -m pytest \
  kernel/tests/test_profile_runtime_services.py \
  kernel/tests/test_profile_runtime_neutrality.py \
  -q

.venv/bin/python -m pytest kernel/tests/ -q
python3 conformance/rewrite_architecture_check.py
python3 -m kernel.manifest --verify-generated
python3 conformance/ofarm_profile_extraction_consistency_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git status --short
```

The focused command must contain the hostile composition, signature, result-
shape, rollback, synthetic neutrality, SI equivalence, legacy-policy exclusion,
and Serbia cases. The complete Kernel run is required for unchanged SI
materialization, output, receipt, and gate-order evidence. Generated historical
executed-evidence files must not change as a test side effect.

Final scope inspection must compare the exact base to exact head, name every
changed path, prove forbidden paths are absent, and report any refused,
unavailable, skipped, or unrun evidence honestly. The final committed head must
be clean; temporary ignored test artifacts do not count as committed evidence
and must not conceal a dirty tracked worktree.

## 14. Open decisions and review disposition

### Closed decisions

- Use narrow minimum result shapes, not a replacement SI output model.
- Keep the boundary private and capability-specific.
- Use one reusable validator for provider-loaded and injected graphs.
- Prove call compatibility by binding inspected bound signatures without
  invoking provider methods.
- Validate returned references at the generic consumer immediately before
  success logging.
- Raise the existing `ProfileRuntimeError`; add no domain reason or schema.
- Demonstrate rollback through the real commit transaction in addition to
  direct stage ordering.
- Keep the synthetic provider test-only and the production registry unchanged.
- Preserve SI behavior and use #161 only as a later follow-up.

### Open decisions

None.

### Review disposition

- Blockers: none known before independent exact-head Phase A review.
- Follow-ups: #161, only after #160 is implemented, reviewed, and merged.
- Preferences: none.

### Merge stop rule

Phase B must not begin until an independent exact-head Phase A review finds no
demonstrated in-scope Blocker and the task user explicitly approves this exact
contract. Approval authorizes only bounded implementation in the same named
draft PR; it does not authorize merge.

After implementation, the PR must not merge until every invariant has the
mapped evidence and no demonstrated Blocker remains. New ideas, Preferences,
and out-of-boundary hardening become Follow-ups and do not reopen or expand the
approved boundary.

## 15. Stop conditions and approval boundary

Stop before editing runtime code and request a new or amended contract if:

1. a canonical or extracted contract must change;
2. unchanged SI behavior, output, materialization identity, receipt, or gate
   order cannot remain assertion-equivalent;
3. a public plugin system, dynamic discovery, descriptor-controlled import,
   mutable registry, capability bag, or profile composition becomes necessary;
4. a Serbian descriptor, provider, fixture, or activation becomes necessary;
5. D22/#240 provider import or bytecode authority must change;
6. a schema, migration, manifest, `ActiveArtifactSet`, evidence lane,
   capability, activation, canonical-law, or readiness change becomes
   necessary;
7. authorization, database, deployment, security-audit, or key-custody
   authority must change;
8. an SI policy value, reference source, adapter, output claim, or active
   default must change;
9. the only solution is a broad rewrite of materialization, output assembly,
   provider routing, or profile selection;
10. a new runtime module or architecture-budget relaxation is required; or
11. a file outside the approved PR boundary needs a non-mechanical change.

The exact reviewed Phase A head and RFC digest must be recorded in the review
request. Any material change to the problem, trust model, authority map,
ordering, invariant, permitted effect, non-effect, PR boundary, stop condition,
or production posture requires another exact-head Phase A review and explicit
approval.
