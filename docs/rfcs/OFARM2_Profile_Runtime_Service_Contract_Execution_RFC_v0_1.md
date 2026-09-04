# OFARM2 Profile-Runtime Service Contract Execution — Phase A Contract v0.1

**Status:** revised proposed Phase A contract; documentation-only, unapproved,
without runtime effect, and awaiting a new independent exact-head review

**Contract identity:**
`ofarm2.profile-runtime-service-contract-execution.issue160.v0.1`

**Date:** 2026-09-04

**Primary implementation ticket:** #160

**Base commit:** `0c55f5cc6665ffef4c57591dafe014ad9bc44524`

**Merged prerequisites:** #159, #239, #240, and #241

**Named draft pull request:** #362

**Primary trust boundary:** runtime integration and readiness at the private
profile-runtime service/composition boundary

**Intended pull-request boundary:** Phase A changes only this RFC. After exact-
head Phase A review and explicit task-user approval, the same named draft pull
request may implement only the private service contracts, common composition
validation, registry-reverification result validation and descriptor binding,
generic stage result validation, synthetic non-SI evidence, focused tests, and
mechanically required test inventory or architecture checks defined here.

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

Three additional admission gaps were demonstrated by exact-head Phase A
review. First, binding only one keyword-rich call does not prove that the
minimal calls made by gates and HTTP routes are executable: a provider can make
an omitted optional parameter required, pass the keyword-rich binding, and
still fail late. The current recomputation protocol also omits the supported
`use_class` keyword used by `resolve_for_use(...)`. The production SI policy's
`validation_policy()` also delegates to zero-argument `evidence_policy()`, so
that default-dependent form must be admitted separately from
`evidence_policy(supported_checks=...)`. Second,
`ProfileRegistryReverification.run(...)` has no executable result contract, so
the validation gate can mistake an arbitrary falsey value for success or ignore
an arbitrary truthy value after returning it. Third, the registry-
reverification service is profile-owned but has no descriptor binding, which
allows an otherwise coherent non-SI graph to execute the SI snapshot family
and product lookup.

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
   consumers, including each minimal call that relies on declared defaults;
2. provider-loaded and explicitly injected graphs cross the same complete
   composition validator;
3. registry reverification is descriptor-bound and its return is interpreted
   only as `None | GateRefusal`;
4. generic stages validate the minimal result fields before recording success;
5. a synthetic non-SI graph executes through the real generic applicability
   and materialization stages; and
6. unchanged SI behavior, receipts, outputs, identities, and gate order remain
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
- the integrity of registry-validation control flow and its `VALIDATION/PASS`
  entry;
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
- applicability and materialization values returned at runtime;
- values returned by the provider-owned registry-reverification service; and
- missing, empty, non-string, or otherwise malformed references in those
  runtime results.

A provider-loaded graph is trusted to execute only after its source and graph
have crossed their existing admission boundaries. It is not trusted to self-
attest that its graph is coherent or that a returned value satisfies a generic
gate contract.

Explicit injection is a private composition handoff, not an alternate source-
admission mechanism. The existing production caller in
`kernel/legacy_m1/runtime.py` may inject only the graph it just received from
`load_profile_runtime_services(...)`; that trusted caller owns the fact that
D22/#240 source admission already occurred. Direct construction and arbitrary
injection are test-only. The common graph validator proves graph coherence for
both paths, but it does not and must not claim to prove executable-source
provenance for an arbitrary injected object.

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
| Explicit-injection source provenance | trusted internal composition caller; production injects only the immediately loader-returned graph | common graph validator, arbitrary test injection, object identity alone |
| Complete graph admission | one private validator in `kernel/profile_runtime_provider.py` | Protocol annotations alone, provider self-attestation, `GatePipeline`'s current two-field shortcut |
| Materialization identities | the provider-owned exact `MaterializationSpecification` instance bound to its materializer | duplicate or merely equal specifications |
| Output identities | the provider-owned exact `OutputSpecification` instance bound to its output assembler | duplicate or merely equal specifications |
| Output materializer | the exact materializer instance carried by the admitted bundle | another compatible materializer instance |
| Registry-reverification profile | its exact `active_profile` identity, equal to the Store-bound descriptor | snapshot-prefix similarity, lookup shape, or an executable service from another profile |
| Profile policy identity | Store-bound descriptor `evidence_policy_ref` plus the descriptor-derived required rule refs | config-backed policy fallbacks, provider aliases |
| Callable compatibility | Python's inspected bound-call signature against every production-reachable private call form inventoried in this contract | one maximally populated call, `runtime_checkable` presence checks alone, annotations, method-name presence without callability |
| Registry-reverification result | `ValidationGate` acceptance of exactly `None` or `GateRefusal` before truthiness or branching | provider truthiness, annotations, arbitrary mappings or objects, `GatePass` |
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
     CALLER_OWNED_SOURCE_PROVENANCE
       -> EXPLICIT_INJECTION_CANDIDATE
  -> EXACT_OUTER_AND_SPECIFICATION_TYPES
  -> REQUIRED_SERVICE_SHAPES_AND_EVERY_CALL_FORM
  -> DESCRIPTOR_SPECIFICATION_MATERIALIZER_REGISTRY_POLICY_CROSS_BINDINGS
  -> COMPOSED
```

Any failed transition raises `ProfileRuntimeError` and no `GatePipeline` is
constructed. The provider path verifies and imports source under the existing
D22 boundary before factory construction; this contract does not reorder or
weaken that work. The explicit path performs no provider import and asserts no
new source authority: its production caller has already obtained the exact
graph from that loader, while arbitrary injected constructions remain test-
only candidates.

Validation order is fail-closed:

1. require the exact `ProfileRuntimeServices` outer type and exact Store-bound
   descriptor identity;
2. require exact trusted specification value types;
3. require each capability service and every inventoried callable;
4. prove each callable can independently bind every production-reachable call
   form, both minimal/default-dependent and keyword-rich, without invoking it;
5. require descriptor, specification, materializer, and registry-
   reverification object cross-bindings;
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

### 6.2 Production call-form inventory

Signature admission proves that a bound callable can accept every existing
consumer form below. Each row is bound independently. A single maximally
populated call is not evidence for a minimal call, because supplying an
argument cannot prove that the same parameter may be omitted. Where a consumer
omits a parameter, the corresponding row therefore proves that the
implementation supplies a usable default. Admission does not require exact
annotations, exact default values, or rejection of additional optional
parameters.

`value` below means a type-appropriate private sentinel used only for
`Signature.bind(...)`; no provider method is invoked.

| Service method | Existing production consumer or supported private form | Required accepted bound call |
| --- | --- | --- |
| policy evidence | `EvidenceSufficiencyGate` | `evidence_policy(supported_checks=value)` |
| policy evidence | `DescriptorPolicyProvider.validation_policy()` delegation, relying on the `supported_checks` default | `evidence_policy()` |
| policy validation | `ValidationGate` | `validation_policy()` |
| context assembly | `ProfileApplicabilityGate`, relying on both defaults | `assemble(cur, farm_ref)` |
| context assembly | materializer recomputation, identity materialization, and use resolution | `assemble(cur, farm_ref, target_twin=value, evaluation_time_policy=value)` |
| source invalidation | `MaterializationGate` and dispute emission | `invalidate_for_sources(cur, source_refs, trigger_family=value, trigger_source_ref=value, farm_scope_ref=value, reason_code=value)` |
| recomputation | `MaterializationGate`, relying on `twin`, `use_class`, and `time_policy` defaults | `recompute(cur, farm_ref)` |
| recomputation | `resolve_for_use(...)` recomputation | `recompute(cur, farm_ref, twin=value, use_class=value, time_policy=value)` |
| materialization resolution | passport output, relying on `twin` and `time_policy` defaults | `resolve_for_use(cur, farm_ref, use_class=value, required_freshness=value, high_consequence=value, recompute_if_needed=value)` |
| materialization resolution | frozen output, relying on `twin` and `recompute_if_needed` defaults | `resolve_for_use(cur, farm_ref, use_class=value, time_policy=value, required_freshness=value, high_consequence=value)` |
| registry reverification | operation validation | `run(context)` |
| passport output | HTTP route, relying on `allow_recompute` default | `passport_view(farm_ref, requesting_party_ref)` |
| passport output | supported explicit render mode | `passport_view(farm_ref, requesting_party_ref, allow_recompute=value)` |
| frozen output | HTTP route, relying on `as_submission` default | `freeze_document_assembly(farm_ref, requesting_party_ref, window_start, window_end)` |
| frozen output | supported explicit submission mode | `freeze_document_assembly(farm_ref, requesting_party_ref, window_start, window_end, as_submission=value)` |

The `ProfileMaterializer` declaration is corrected to include every keyword
used by generic orchestration. In particular,
`invalidate_for_sources(...)` adds `trigger_source_ref`, `farm_scope_ref`, and
`reason_code`, and `recompute(...)` adds `use_class`. The declared defaults
must permit every omission shown above.

`inspect.signature(bound_callable).bind(...)` or an assertion-equivalent
private mechanism is sufficient when applied separately to every row. A
callable with an uninspectable signature is refused because compatibility is
not demonstrated. This inventory is private and closed; adding a capability or
a production call form requires a new reviewed change.

### 6.3 Registry-reverification result

For every individual validator result interpreted by `ValidationGate`, and in
particular the provider-owned registry-reverification result, the only valid
private result is exactly:

```text
None | GateRefusal
```

The gate validates that result before any truthiness test or control-flow
branch. `None` means that validation continues. A `GateRefusal` follows the
existing governed-refusal path. Every other value, including `{}`, a non-empty
mapping, an arbitrary falsey or truthy object, and `GatePass`, raises
`ProfileRuntimeError`. The enclosing serialized transaction rolls back, no
successful `VALIDATION/PASS` entry commits, promotion does not occur, and no
durable effects from that attempt survive.

This is an implementation-contract failure, not a new domain refusal, reason
code, or durable record. Return annotations document the contract but do not
replace runtime validation of the provider-controlled result.

### 6.4 Applicability result

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

### 6.5 Materialization result

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

### 6.6 Time-of-check/time-of-use boundary

Composition validation occurs once immediately before a graph becomes usable.
The graph object is then retained by that pipeline or runtime composition root.
Ordinary calls occur later inside their existing transaction boundaries.
Arbitrary mutation between validation and use is excluded by the trust model;
there is no new lock, hash, copy, proxy, cache, or per-call revalidation.

Result validation is deliberately at time of use because result content cannot
be proven from a callable signature. The required references are checked in the
same transaction and immediately before the generic success side effect.

## 7. Invariants and acceptance criteria

- **PRSC-001 — Executable declared calls.** Every callable in the call-form
  inventory is present and callable, and every inventoried production call
  form binds independently at composition. In particular,
  `ProfilePolicyService.evidence_policy(...)` accepts both its zero-argument
  default-dependent form and its `supported_checks` keyword form;
  `ProfileMaterializer.invalidate_for_sources(...)` declares and accepts
  `trigger_family`, `trigger_source_ref`, `farm_scope_ref`, and `reason_code`;
  `ProfileMaterializer.recompute(...)` declares and accepts `use_class`; and
  each minimal call proves that its omitted parameters have usable defaults.
- **PRSC-002 — Exact descriptor and trusted values.** Only the exact
  `ProfileRuntimeServices` type, exact Store-bound descriptor object, and exact
  trusted specification value types can compose.
- **PRSC-003 — One coherent graph.** Policy, context, materializer, registry-
  reverification, and output services bind the Store descriptor; the
  materializer and output assembler bind the bundle's exact specifications;
  the output assembler binds the bundle's exact materializer; and policy ref
  plus required recognized rule refs match the descriptor.
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
  incompatible signatures, malformed applicability or materialization result
  shapes, and any registry-reverification result other than `None` or
  `GateRefusal` raise `ProfileRuntimeError`, not incidental `AttributeError`,
  `TypeError`, or `KeyError`; no misleading generic gate success is committed.
- **PRSC-008 — Executable profile neutrality.** A test-only synthetic non-SI
  graph passes real `ProfileApplicabilityGate` and `MaterializationGate`
  execution, receives every invalidation keyword, and produces only synthetic
  profile-local context, materialization, output, package, policy, view, and
  result-shape identifiers. It never enters the production registration tuple.
- **PRSC-009 — SI assertion equivalence.** For unchanged inputs, provider-
  loaded and explicitly injected SI services preserve decision outcomes,
  problems, gate names and order, materialization key/specification identities,
  basis/snapshot reference families, output identities and qualifications, and
  receipt structure. Existing SI tests remain green; the permitted descriptor-
  only constructor wiring changes no SI runtime behavior or policy value.
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
| PRSC-001 | either composition path receives a graph whose policy makes `supported_checks` required, whose invalidator omits `reason_code`, whose recomputer omits `use_class`, or whose nominally optional context, recompute, passport, frozen-output, or resolution parameter is made required despite a production caller omitting it | composition raises `ProfileRuntimeError` before returning services or constructing a pipeline; no transaction begins |
| PRSC-002 | `GatePipeline(store, runtime_services=...)` receives a lookalike bundle, an equal-but-distinct descriptor, or a non-trusted specification value | constructor raises `ProfileRuntimeError`; no pipeline exists |
| PRSC-003 | `GatePipeline(...)` receives an exact dataclass with a foreign service descriptor (including a registry-reverification service from another profile), a different materialization/output specification instance, a different output materializer, wrong policy ref, or one missing required recognized rule ref | constructor raises `ProfileRuntimeError` before transaction entry; the foreign snapshot family or product lookup cannot execute |
| PRSC-004 | the same malformed graph is returned by the provider loader and supplied explicitly | both paths refuse through the common validator; an injected-store transaction counter remains zero |
| PRSC-005 | `GatePipeline.commit(...)` reaches a signature-compatible context assembler returning `{}`, `{"contextSnapshotId": ""}`, or a non-string ref | `ProfileRuntimeError`; transaction rollback; no committed `APPLICABLE` entry or promotion trace from the attempt |
| PRSC-006 | an accepted commit reaches a signature-compatible materializer returning a missing, empty, or non-string `basisRef` or `snapshotRef` | `ProfileRuntimeError`; no `UPDATED` entry, false success flag, or committed promotion/materialization effects |
| PRSC-007 | either composition path receives an absent/non-callable service or a callable whose inspected signature cannot prove every call form | composition raises one explicit `ProfileRuntimeError`; no incidental exception type becomes the boundary contract |
| PRSC-007 | `GatePipeline.commit(...)` for an operation claim reaches an admitted registry-reverification service returning `{}`, a non-empty dictionary, an arbitrary falsey object, an arbitrary truthy object, or `GatePass` | `ProfileRuntimeError` before `VALIDATION/PASS` is logged; no promotion occurs and the transaction leaves no durable effect from the attempt |
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
three currently missing invalidation keywords and the currently omitted
`recompute(..., use_class=...)` keyword, and it declares defaults sufficient for
every omission in the production call-form inventory.

`ProfileRegistryReverification` gains an `active_profile` binding and declares
`run(context) -> GateRefusal | None`. The annotation is private documentation;
the runtime result check remains mandatory. This does not abstract or transfer
the existing snapshot-prefix or product-lookup authority.

### 9.2 One graph validator

`kernel/profile_runtime_provider.py` refactors the existing validator into one
reusable private function. It retains every current exact-type, identity,
cross-binding, policy-ref, and required-rule check, then adds inventoried
callability and independent binding of every production call form. It also
requires the registry-reverification service's exact `active_profile` identity
to be the Store-bound descriptor. It converts inspection/admission failures to
`ProfileRuntimeError` without invoking provider methods.

The validator preserves the existing private attribute names: the policy
service binds its profile as `descriptor`, while context, materializer,
registry-reverification, and output services bind it as `active_profile`. This
contract adds no alias or rename; naming unification is an out-of-scope future
refactor and cannot change which exact identities are checked here.

`load_profile_runtime_services(...)` uses it after factory construction.
`GatePipeline` imports and uses the same function whenever services are
explicitly supplied. The current partial `elif` check is deleted rather than
kept as a compatibility layer.

This does not move or duplicate D22 provider import authority. The validator
accepts a constructed graph; it does not discover, import, register, or select
providers.

### 9.3 Generic and validator result validation

`kernel/stages.py` owns one small private helper that extracts a required result
ref, requires a mapping shape and non-empty built-in string field, and raises
`ProfileRuntimeError` with a developer-facing message. Both generic stages call
it before their success state/log side effects. Domain refusal handling remains
unchanged.

`kernel/validators.py` enforces the existing individual-validator result model
before truthiness or branching. `None` and `GateRefusal` keep their current
meanings; any other value raises `ProfileRuntimeError` and relies on the
existing transaction owner for rollback. The registry-reverification service
is descriptor-bound when constructed. No validation outcome, gate order,
domain refusal, or logging convention changes for conforming SI results.

### 9.4 Synthetic evidence and SI preservation

`kernel/tests/_synthetic_profile_runtime.py` is upgraded to the exact private
contract. Its assembler and materializer return synthetic refs, and its
materializer exposes test-only observation of the complete invalidation call.
Its registry-reverification service binds the synthetic descriptor. It remains
absent from `_REGISTRATIONS`.

Focused tests exercise actual generic stages, both composition paths, hostile
cross-wires/signatures/results, transaction rollback, SI equivalence, legacy-
policy exclusion, and Serbia refusal. Existing Kernel and architecture tests
provide the broad regression boundary.

This is the minimum coherent design because each defect is corrected at its
owner:

- declared shape in the private protocol;
- graph coherence at composition;
- registry-result truth at the generic validation consumer;
- returned-value truth at the generic consumer; and
- neutrality through executable test evidence.

No new module, registry, schema, durable type, adapter, service abstraction, or
public surface is needed.

## 10. Elegance audit

- Store-bound descriptor sources of truth: one.
- Provider source/import authorities: one existing D22/#240 path, unchanged.
- Complete graph validators: one.
- Composition entry points: two, converging on that validator.
- Registry-reverification result interpreters: one generic validation gate.
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

The base commit leaves too little measured headroom for the approved slice. The
partial validation branch deleted from `kernel/gates.py` cannot pay for the
work because that file, like `kernel/stages.py` and `kernel/validators.py`, is
not in the profile-runtime group. Exact-head review measured the idiomatic
service-protocol portion at about 255 lines and the complete production group
at about 931 lines before tests. Requiring the old ceilings would therefore
approve an implementation that is already expected to stop.

Phase B authorizes only these explicit ceiling changes in
`conformance/rewrite_architecture_check.py`:

| Guard | Base lines | Current ceiling | Approved Phase B ceiling |
| --- | ---: | ---: | ---: |
| `GROUP_BUDGETS["profile runtime"]` | 867 | 900 | 950 |
| `MODULE_BUDGETS["kernel/profile_runtime_services.py"]` | 237 | 250 | 265 |
| `TEST_MODULE_BUDGETS["kernel/tests/test_profile_runtime_services.py"]` | 769 | shared 800 | 1,100 |

The 950-line group ceiling leaves 19 lines beyond the measured 931-line
production design; the 265-line service ceiling leaves 10 beyond the measured
255-line protocol design. The service-test override provides 331 lines beyond
the base for the full parameterized signature, cross-wire, result, transaction,
and equivalence programme without moving cohesive service-admission evidence
into unrelated files or compressing it to satisfy a physical-line accident.
That allowance may contain only evidence mapped to PRSC-001 through PRSC-010
and supporting test helpers used by that evidence.

These are maximum guardrails, not growth targets. All other production,
module, test, function, import, and architecture constraints remain unchanged.
Phase B must still delete duplication where coherent, may not pack statements
or introduce a framework to spend the headroom, and must report final counts.
Exceeding any revised ceiling is a stop condition requiring a new contract.

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
- `kernel/validators.py`;
- `kernel/profiles/si_ffs/runtime_provider.py`, only to pass the already selected
  descriptor into the existing registry-reverification service;
- `kernel/tests/_synthetic_profile_runtime.py`;
- `kernel/tests/test_profile_runtime_services.py`;
- `kernel/tests/test_profile_runtime_neutrality.py`;
- `conformance/rewrite_architecture_check.py`, only for the three exact ceiling
  changes stated in section 10;
- this RFC to record approved/reviewed implementation status; and
- `conformance/review_baseline_test_inventory.json` only if the exact test
  additions require a mechanical inventory update.

No architecture-budget change other than the three exact section 10 ceilings
is authorized by this contract.

The one permitted SI provider construction edit may add only the exact
descriptor binding; it may not change snapshot prefixes, product lookup,
policy values, reference behavior, service ordering, active defaults, or any SI
result. A test-support edit outside the named files requires proof that it is
purely mechanical and inside this boundary; otherwise implementation stops for
an amendment.

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

The private call-form inventory and result minima are the calls and fields
consumed by the existing runtime. The common validator is the permanent single
composition authority for this graph model. A future new capability must
extend this private contract through a separately reviewed change; it does not
justify a generic plugin framework now.

This is pre-deployment implementation work and does not authorize deployment or
claim production readiness.

## 13. Traceability and verification

| Invariant | Owning code | Required negative/neutral test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| PRSC-001 | service protocols; private signature validator | missing keyword, absent/non-callable method, required policy `supported_checks`, or another default-dependent parameter made required for any minimal call | every inventoried call form binds independently; both composition paths reject incompatible signatures | focused two-module pytest |
| PRSC-002 | common validator; `GatePipeline.__init__` | lookalike outer type, copied descriptor, wrong spec type | `ProfileRuntimeError` before pipeline construction | focused two-module pytest |
| PRSC-003 | common validator; descriptor-bound registry reverification | each descriptor/spec/materializer/output/registry/policy/rule cross-wire | every graph mismatch, including a foreign registry service, refuses at composition | focused two-module pytest |
| PRSC-004 | loader and explicit-injection branch | same validator reached from both; injected transaction counter stays zero | equivalent `ProfileRuntimeError` admission behavior | focused two-module pytest |
| PRSC-005 | `ProfileApplicabilityGate`; result-ref helper | missing/empty/non-string context ref | no `APPLICABLE`; full transaction rollback | focused hostile tests plus complete Kernel suite |
| PRSC-006 | `MaterializationGate`; result-ref helper | missing/empty/non-string basis or snapshot ref | no success flag/`UPDATED`; full transaction rollback | focused hostile tests plus complete Kernel suite |
| PRSC-007 | common validator; `ValidationGate` result check; result-ref helper | opaque/incompatible callable, malformed runtime mappings, and each falsey/truthy non-`GateRefusal` registry result including `GatePass` | only `ProfileRuntimeError` crosses the implementation boundary; no validation success or durable effect survives | focused hostile tests plus complete Kernel suite |
| PRSC-008 | synthetic fixture; real generic stages | execute applicability and materialization; recursive identifier scan | synthetic refs logged; complete invalidation args observed; no SI leakage or production registration | `test_profile_runtime_neutrality.py` |
| PRSC-009 | SI provider's descriptor-only registry construction wiring and unchanged generic orchestration | default-loaded versus explicit-injected SI scenario | stable normalized results, materializations, outputs, receipts, validation outcomes, and gate order; full Kernel suite passes | focused equivalence test plus complete Kernel suite |
| PRSC-010 | existing registration/selection/architecture authorities | Serbia load/route refusal; registration/default assertions; forbidden-file diff; extraction failure-set comparison | single-active-SI, exact three-path extraction baseline, revised architecture ceilings, and all non-effects preserved | architecture, manifest, extraction, package, and diff checks |

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

The repository `.python-version` pins Python 3.12.13. This isolated worktree
has no `.venv`; the Phase A package-contract and architecture checks used an
available compatible 3.12.13 environment. An initial untouched-base focused
observation used a separate local Python 3.14.5 environment, which is
unsupported and non-
authoritative. That observation reported 13 passed, 3 failed, and 19 errors;
every failure/error was database setup blocked by the overlong default Unix-
socket path, and no active `.s.PGSQL.54317` socket was available. No unrelated
machine-specific virtual-environment path is durable contract evidence, and
the observation is not test acceptance evidence.

A later review of exact head
`c47639972fc26a8bad72a212aafb5c0fb706f710` reports that a lock-built Python
3.12.3 environment with PostgreSQL 16.13 passed manifest verification and all
35 focused base tests. Those results supersede the earlier assumption that the
cases themselves were failing, but they do not replace pinned-environment
acceptance evidence: the repository pins Python 3.12.13 and PostgreSQL 17.10,
and the review was posted by the PR-author account. The local unavailability
and the review's non-pinned corroboration are both reported rather than merged
into a false authoritative PASS.

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

The focused command must contain the hostile composition, default-dependent
signature, registry-result, result-shape, rollback, synthetic neutrality, SI
equivalence, legacy-policy exclusion, and Serbia cases. The complete Kernel run
is required for unchanged SI materialization, output, receipt, and gate-order
evidence. Generated historical executed-evidence files must not change as a
test side effect.

The extraction command is already non-zero at the exact base. Its Phase B
acceptance criterion is baseline equivalence, not a false PASS claim. Running
the command at both base and head must report exactly these three seed-scan hit
paths and no others:

```text
conformance/review_baseline_test_inventory.json
kernel/tests/_synthetic_profile_runtime.py
kernel/tests/test_rewrite_architecture_check.py
```

Any added path, removed path, changed diagnostic category, or inability to
reproduce the base set is a stop condition. The final report must retain the
command's non-zero status and show the base/head comparison. This PR does not
authorize editing
`profile_si_ffs/extraction_inventory/core_country_term_audit_review_records.json`
to manufacture a green result.

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
- Prove call compatibility by independently binding every inventoried minimal
  and keyword-rich bound signature without invoking provider methods; one
  maximal bind is insufficient.
- Admit both `evidence_policy()` and
  `evidence_policy(supported_checks=value)` so the SI-style
  `validation_policy()` delegation cannot fail late.
- Bind registry reverification to the exact active descriptor and validate its
  result as only `None | GateRefusal` before truthiness.
- Treat explicit injection as a private graph handoff whose production caller
  owns source provenance; the common validator does not attest injected source.
- Preserve the existing `descriptor` policy binding and `active_profile`
  bindings on the other four services; naming unification is outside this PR.
- Authorize only the three measured architecture ceilings in section 10 and
  require exact three-path extraction-baseline equivalence.
- Validate returned references at the generic consumer immediately before
  success logging.
- Raise the existing `ProfileRuntimeError`; add no domain reason or schema.
- Demonstrate rollback through the real commit transaction in addition to
  direct stage ordering.
- Keep the synthetic provider test-only and the production registry unchanged.
- Preserve SI behavior and use #161 only as a later follow-up.

### Open decisions

None. The exact-head review choices about default-dependent call forms,
registry result semantics, registry descriptor identity, and explicit-
injection provenance, measured architecture ceilings, and extraction baseline
handling are closed above.

### Review disposition

- Blockers: the review of head
  `4de682c493ae2d39cd29ae6c897f928791a14a57` identified three: incomplete
  default-dependent call admission, an unenforced registry-reverification
  result contract, and an unbound registry-reverification service. This revised
  contract addressed those findings. Reviews of head
  `c47639972fc26a8bad72a212aafb5c0fb706f710` then identified the omitted
  zero-argument `evidence_policy()` call and an already-determined architecture-
  budget conflict. This revision addresses both but makes no claim of clearance
  before a new exact-head review.
  Both review artifacts were posted by the PR-author account; their findings
  are incorporated but they do not supply independent Phase A clearance.
- Follow-ups: #161, only after #160 is implemented, reviewed, and merged.
  Optional unification of `descriptor` and `active_profile` naming is a separate
  future refactor, is not required here, and has no issue or implementation in
  this PR.
- Preferences: the extraction-baseline criterion and descriptor-name
  clarification requested at the prior head are incorporated.

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
10. a new runtime module or an architecture-budget change beyond the three
    exact section 10 ceilings is required;
11. a file outside the approved PR boundary needs a non-mechanical change; or
12. the extraction check's head failure set differs from the exact base set in
    section 13.2.

The exact reviewed Phase A head and RFC digest must be recorded in the review
request. Any material change to the problem, trust model, authority map,
ordering, invariant, permitted effect, non-effect, PR boundary, stop condition,
or production posture requires another exact-head Phase A review and explicit
approval.
