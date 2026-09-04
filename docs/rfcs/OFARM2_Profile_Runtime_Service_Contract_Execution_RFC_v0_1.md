# OFARM2 Profile-Runtime Service Contract Execution — Phase A Contract v0.1

**Status:** revised proposed Phase A contract; documentation-only, unapproved,
without runtime effect, and awaiting a new exact-head review

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
validation, exact Store/context ownership, exact runtime-selected policy and
capability-bound reference-input provenance, a mutation-free profile-neutral
registry-reverification request and closed outcome handling, generic stage
result validation, synthetic non-SI evidence, focused tests, and mechanically
required test inventory or architecture checks defined here.

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

A later exact-head review demonstrated two further composition gaps in that
design. Descriptor identity alone does not prove that context assembly,
materialization, output assembly, or registry reverification is wired to the
Store whose descriptor was selected; two Stores can share the same exact
descriptor object. Nor does it prove that the materializer calls the exact
context assembler carried by the bundle. In addition, admitting a provider-
constructed `GateRefusal` would let provider-controlled mutable fields choose
the gate, outcome, final outcome, problem list, and apparent log correlation.
That would validate a shape while leaving governance and trace truth outside
the generic gate.

The next exact-head review demonstrated that log-delta inspection still did
not close the mutation surface. The provider received the complete mutable
`GateContext`, including its transaction cursor, Store, gate sequence, and
review-reason list. It could write only the durable gate row, write only the
in-memory entry, remove or rewrite a prior entry, or append a malformed review
reason that failed later. Validating one returned envelope and one list delta
could not prove that all correlated state stayed lawful. The same review also
showed that matching descriptor and policy refs did not bind the executing
policy to the exact selected `PROFILE_POLICY` component, and that a detached
product lookup loaded from Store B could be paired with Store A when both
Stores shared a descriptor. A path-backed or foreign-byte policy with the same
`policyId` likewise passed the proposed checks.

The latest exact-head review then found that the attempted lookup-provenance
fix had drifted beyond the ticket. It made every common registry service expose
an SI-shaped `lookup_by_decision(snapshot_id, decision_number)` API and made
generic `ValidationGate` interpret `CROP_PROTECTION_PRODUCT`,
`registrationRef`, and product-register snapshot advance. That would prevent a
legitimate holding- or certificate-oriented provider from executing unless it
fabricated a product register. The same design accepted any descriptor family;
an otherwise truthful SI graph could therefore wire GERK or FFSNaprave data to
product reverification. This revision removes product lookup and product
applicability from the common contract. The admitted profile provider owns one
explicit optional capability-family binding, the common validator proves its
object and selected-input coherence, and the profile service alone decides
whether a detached neutral request has an effect.

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
3. every Store-owning service is bound to the exact expected Store, the
   materializer is bound to the bundle's exact context assembler, and policy
   plus registry-reverification services prove exact runtime-selected
   provenance without a common lookup API;
4. registry reverification receives no `GateContext`, transaction cursor,
   Store, gate sequence, or review-reason container; its profile-owned service
   decides applicability from one detached neutral request and returns one
   exact closed private outcome whose generic consumer alone applies effects;
5. generic stages validate the minimal result fields before recording success;
6. a synthetic non-SI graph executes through the real generic applicability
   and materialization stages; and
7. unchanged SI behavior, receipts, outputs, identities, and gate order remain
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
- the exact Store ownership of every Store-backed service and the exact context
  assembler used by the materializer;
- the exact immutable RuntimeBundle policy component parsed by the policy
  service, the exact profile-owned reference family governing registry
  reverification when one exists, and the exact selected reference-source
  identities used by that service;
- the materialization and output specifications actually used by their bound
  service instances;
- profile policy identity and the minimum recognized rule set;
- the integrity and ordering of `APPLICABLE` and `UPDATED` gate entries;
- the integrity of registry-validation control flow, governed refusal logging,
  review routing, and the `VALIDATION/PASS` entry;
- transaction rollback when a provider violates its runtime result contract;
- SI materialization identities, outputs, receipts, and gate order for
  unchanged inputs;
- profile neutrality of the generic Kernel stages; and
- the single-active-SI and descriptorless/unregistered Serbia posture.

### Trusted components

- a startup-complete, tenant-bound `Store` and its exact
  `Store.active_descriptor`, `Store.runtime_bundle`, and selected reference
  source data;
- exact frozen `RuntimeComponent` and `RuntimeBundle` values already admitted
  by startup verification;
- `resolve_bound_descriptor(...)` for selecting that descriptor;
- the code-owned registration and source-only import posture already settled by
  #159, D22, and #240;
- the exact `ProfileRuntimeServices`, `MaterializationSpecification`,
  `OutputSpecification`, and `ProfileManifestEvidenceSpecification` types;
- one private service-graph validator after it has accepted a graph;
- generic gate ordering, `ValidationGate`'s fixed refusal semantics, the trusted
  RuntimeProblem registry and code-owned reason-code set, and the enclosing
  `Store.serialized_tx()` transaction; and
- reviewed in-process Python source and ordinary Python signature semantics.

### Untrusted actors and inputs

- every object returned by an admitted provider factory until common graph
  validation succeeds;
- every explicitly injected `runtime_services` object until the same validation
  succeeds;
- service attributes, descriptor bindings, specification bindings, materializer
  bindings, Store bindings, context-assembler bindings, registry capability-
  family bindings, selected-input bindings, policy refs, recognized rule refs,
  callables, and callable signatures presented by those candidate graphs;
- applicability and materialization values returned at runtime;
- values returned by the provider-owned registry-reverification service,
  including its disposition, rationale, and problem mapping;
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

The registry service is deliberately denied the generic mutable carrier. Its
frozen request contains detached canonical bytes for the semantic submission
and its already resolved generic identity bindings, the current snapshot ref
for its one profile-owned family if any, and normalized event time. It contains
no `GateContext`, cursor, Store, gate sequence, review-reason list, mutable
claim mapping, or mutation callback. Its ordinary implementation therefore
cannot directly write either side of a gate log or mutate review-routing state.
A provider that captures a `GateContext` or Store through undeclared globals,
closures, private introspection, or monkeypatching has exercised the admitted-
source compromise capability excluded above. This contract narrows the
callable boundary; it is not an in-process security sandbox.

Object identity checks here bind one in-process composition graph; they are not
a substitute for source, process, operator, or filesystem trust. Exact identity
is required so a bundle cannot name one descriptor or specification while the
executing service retains an equal-but-distinct object. This is graph-coherence
proof under the current private composition model, not external attestation.
The immutable provenance retained by policy and registry services is checked
against the expected Store's exact RuntimeBundle and selected components; a
matching logical ref or digest alone is insufficient.

## 5. Authority map

| Decision | Sole authority after implementation | Non-authoritative inputs or fallbacks |
| --- | --- | --- |
| Active descriptor | `Store.active_descriptor` returned by `resolve_bound_descriptor(...)` | provider claims, equal copies, injected bundle claims |
| Provider and factory source | existing code-owned registration plus D22/#240 import posture | descriptor paths, dynamic imports, test switches |
| Explicit-injection source provenance | trusted internal composition caller; production injects only the immediately loader-returned graph | common graph validator, arbitrary test injection, object identity alone |
| Complete graph admission | one private validator in `kernel/profile_runtime_provider.py` | Protocol annotations alone, provider self-attestation, `GatePipeline`'s current two-field shortcut |
| Runtime Store ownership | the exact expected `Store` passed to the common validator and retained by context, materializer, and output services | a shared descriptor, equal Store state, provider claims, implicit closure provenance |
| Materializer context owner | the exact context assembler carried by the admitted bundle | another compatible assembler, matching descriptor, shared Store alone |
| Materialization identities | the provider-owned exact `MaterializationSpecification` instance bound to its materializer | duplicate or merely equal specifications |
| Output identities | the provider-owned exact `OutputSpecification` instance bound to its output assembler | duplicate or merely equal specifications |
| Output materializer | the exact materializer instance carried by the admitted bundle | another compatible materializer instance |
| Registry capability family | the exact `registry_reference_family` object carried by the outer service bundle and selected by admitted profile-provider source; both the SI factory and SI service constructor require `descriptor.reference_family(SI_REGSR_FAMILY_ID)` | generic product-role inference, any merely equal family, arbitrary descriptor-family membership, snapshot-prefix similarity, or the registry service's uncorroborated choice |
| Registry-reverification owner | its exact `active_profile` and exact outer-bundle `reference_family` binding (including exact `None`); a bound family additionally requires the expected Store RuntimeBundle and exact selected-input identity tuple | a decorative RuntimeBundle for a familyless service, a Store attribute on the service, lookup shape, a shared descriptor, family text alone, or a detached family-bound service from another Store/profile |
| Selected registry data | `expected_store.selected_reference_source_data(reference_family.snapshot_prefix)`, compared as the exact ordered `(snapshot_ref, artifact_ref, source_digest)` tuple retained by the registry service from the inputs used by its private implementation; exact empty tuple when no family is bound | copied payload contents, lookup results, provider claims, a foreign RuntimeBundle, or decorative data for a familyless capability |
| Profile policy identity | the exact frozen `PROFILE_POLICY` RuntimeComponent returned by `expected_store.runtime_bundle.component(...)`, retained and parsed by the policy service, plus descriptor-derived required rule refs | a matching `policyId`, ref or digest alone, path-backed loading, foreign or stale bytes, provider aliases |
| Callable compatibility | Python's inspected bound-call signature against every production-reachable private call form inventoried in this contract | one maximally populated call, `runtime_checkable` presence checks alone, annotations, method-name presence without callability |
| Registry-reverification applicability and classification | the admitted profile-owned service, using detached semantic-submission bytes, resolved-binding bytes, normalized event time, its exact capability family, and the current snapshot ref for that family | generic interpretation of `CROP_PROTECTION_PRODUCT`, `registrationRef`, decision number, certificate or holding semantics, or snapshot advance |
| Registry-reverification input construction | `ValidationGate`, which supplies the exact frozen neutral request but does not interpret profile-specific fields | the provider receiving a `GateContext`, cursor, Store, gate sequence, review-reason list, mutable claim mapping, or generic product lookup |
| Registry-reverification result | `ValidationGate` acceptance of one exact private frozen `RegistryReverificationOutcome` with an exact closed disposition and disposition-specific fields | provider truthiness, `None`, annotations, mappings, arbitrary objects, `GatePass`, provider-constructed `GateRefusal` |
| Registry effects | `ValidationGate`, which alone turns `NO_EFFECT`, `REVERIFIED`, `REVIEW_REQUIRED`, or `REFUSED` into no effect, one correlated success log, one validated copied review reason, or one fixed governed refusal | provider-selected gate/outcome/final outcome, mutable problem containers after copying, provider-written log or review mutation |
| Applicability success ref | generic `ProfileApplicabilityGate` validation of returned `contextSnapshotId` | provider return annotation or truthiness of the outer result |
| Materialization success refs | generic `MaterializationGate` validation of returned `basisRef` and `snapshotRef` | provider return annotation or incidental dictionary indexing |
| Gate success ordering | generic stages after result validation | provider logging, caller claims, inferred success |

The provider loader's existing `_validate_services(...)` logic becomes the one
reusable validator rather than a second authority. Its private contract is
`_validate_services(services, descriptor, expected_store)` (or an assertion-
equivalent name and argument order). The partial injected-graph condition in
`GatePipeline` is deleted. Both paths call that same validator with the exact
Store-bound descriptor and exact Store.

`runtime_checkable` protocols remain useful type documentation and structural
screening, but they do not inspect signatures and therefore do not own callable
admission. No legacy fallback or alternate validation path remains.

The outer capability-family binding is profile-owned configuration in reviewed
provider source, not descriptor-driven discovery. The common validator proves
that the outer bundle, registry service, exact descriptor family object, and
selected Store inputs agree; it does not decide what that family means. A
malicious admitted provider that changes both the outer binding and its service
coherently is an admitted-source compromise, just as one that coherently changes
a materialization specification. The focused SI factory test therefore pins
its profile-owned choice to the exact REGSR family, while both composition-path
hostile tests prove that substituting GERK or FFSNaprave beneath that binding is
rejected.

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
  -> DESCRIPTOR_STORE_CONTEXT_SPECIFICATION_MATERIALIZER_CROSS_BINDINGS
  -> EXACT_SELECTED_POLICY_AND_CAPABILITY_REFERENCE_PROVENANCE
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

1. require the exact `ProfileRuntimeServices` outer type, exact Store-bound
   descriptor identity, and an exact expected Store supplied by the composition
   root;
2. require exact trusted specification value types;
3. require each capability service and every inventoried callable;
4. prove each callable can independently bind every production-reachable call
   form, both minimal/default-dependent and keyword-rich, without invoking it;
5. require context assembler, materializer, and output assembler `.store`
   identities to be the expected Store; require the materializer's `.context`
   identity to be the bundle's exact context assembler;
6. require descriptor, specification, materializer, registry-reverification,
   and exact optional capability-family object cross-bindings;
7. resolve the expected `PROFILE_POLICY` component from the expected Store's
   RuntimeBundle and require the policy service to retain that exact component;
8. require the registry service's `reference_family` to be the exact outer
   binding and, when non-`None`, the identical object in the descriptor tuple;
   a bound family requires the exact expected RuntimeBundle and an immutable
   selected-input identity tuple equal to the tuple freshly derived from the
   expected Store, while a `None` family requires exact `None` RuntimeBundle
   provenance and an exact empty tuple; and
9. require the policy ref to equal the descriptor evidence-policy ref and the
   policy service's recognized refs to include the descriptor's evidence
   policy, profile, pack, and code-binding profile refs.

Missing attributes, non-callables, opaque or incompatible signatures,
inspection failures, missing provenance, path-backed policy providers, foreign
or stale policy components, foreign registry services, wrong family objects,
and selected-input tuple mismatches are normalized to `ProfileRuntimeError`.
Provider methods are not invoked during composition. For a bound family, the
validator's one read-only selected-reference-source query asks the trusted
Store for its already selected inputs; a familyless service makes no such
query. Neither branch calls a provider method or selects new data.

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
| registry reverification | operation validation | `run(request)` |
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

### 6.3 Registry-reverification result and refusal ownership

The provider-owned registry-reverification service is the only untrusted
individual validator supplied by the runtime-services graph. Code-owned
validators retain their existing internal `GateRefusal | None` convention;
this change does not create a second result model for them.

`ValidationGate` keeps the service in its existing position immediately after
`CodeBindingValidator`. Every operation claim that reaches that position calls
the service exactly once; the generic gate does not decide whether product,
certificate, holding, or any other profile-specific reverification applies.
It constructs an exact private frozen/slotted
`RegistryReverificationRequest` with these fields:

- `claim_canonical_bytes`, the non-empty exact built-in bytes produced by the
  existing `kernel.contracts.canonical_json(ctx.sub).encode("utf-8")` path;
- `resolved_binding_canonical_bytes`, an exact built-in tuple containing the
  non-empty exact built-in canonical bytes of every already resolved
  `AgronomicIdentityBinding` payload, in the submitted reference order;
- `current_reference_snapshot_ref`, either a non-empty exact built-in string
  selected by `current_reference_snapshot(...)` for the exact bound capability
  family, or exact `None` when the service has no family or no current snapshot;
  and
- `event_time`, the same non-empty exact built-in normalized event-time string
  the current SI validator uses.

The existing deterministic JSON serializer is reused only to detach immutable
call data. These bytes are not persisted, hashed into a new identity, admitted
as a RuntimeBundle component, or promoted to a canonicalization authority. The
resolved-binding tuple uses the existing generic, kind-checked
`sufficiency.resolved_bindings(...)` result after `ReferenceResolutionValidator`
and `CodeBindingValidator`; it adds no product role or field interpretation to
generic code. A provider that does not use agronomic identity bindings may
ignore the empty or irrelevant tuple and classify from its other neutral
inputs.

The request deliberately contains no `GateContext`, transaction cursor,
Store, gate sequence, review-reason list, generic mutation callback, mutable
claim mapping, or common lookup object. Generic request construction and
current-snapshot selection remain code-owned orchestration; applicability,
captured-snapshot interpretation, profile field meaning, private lookup, and
classification remain profile-owned.

The request constructor enforces these exact field shapes; a generic coding
error cannot silently widen what crosses the boundary.

At this private boundary every call must return the exact frozen/slotted
`RegistryReverificationOutcome`. It contains an exact
`RegistryReverificationDisposition` enum value from this closed vocabulary and
only the two optional payload fields shown here:

```text
NO_EFFECT       -> problem=None, rationale=None
REVERIFIED      -> problem=None, rationale=non-empty built-in string
REVIEW_REQUIRED -> problem=exact RuntimeProblem dict, rationale=None
REFUSED         -> problem=exact RuntimeProblem dict, rationale=None
```

`None`, a mapping, a provider-constructed `GatePass` or `GateRefusal`, an enum
lookalike, a subclassed envelope, an unknown disposition, an extra or
disposition-inconsistent payload, and an arbitrary falsey or truthy object are
all invalid. `ValidationGate` catches ordinary `Exception` from the provider
call and normalizes it, like every invalid outcome, to `ProfileRuntimeError`;
`BaseException` control-flow signals are not swallowed.

The generic gate validates the complete outcome before applying any effect:

```text
DETACHED_REQUEST_BUILT
  -> REGISTRY_SERVICE_CALLED
  -> EXACT_OUTCOME_AND_CLOSED_DISPOSITION
  -> DISPOSITION_FIELDS_VALIDATED
  -> ONE_CODE_OWNED_EFFECT
       NO_EFFECT       -> NO LOG, REVIEW REASON, OR REFUSAL
       REVERIFIED      -> ONE VALIDATION/REGISTRY_REVERIFIED LOG
       REVIEW_REQUIRED -> ONE VALIDATED COPIED REVIEW REASON
       REFUSED         -> ONE FIXED VALIDATION REFUSAL AND LOG
```

`NO_EFFECT` is a provider-selected applicability result with no generic side
effect. It is not a generic pre-call skip. This lets a provider with no product
register execute and lawfully decide that a claim has no registry effect, and
lets another provider perform certificate- or holding-style classification
without implementing or naming a decision-number lookup.

For `REVIEW_REQUIRED` and `REFUSED`, the generic gate requires `problem` to be
an exact built-in dictionary, validates it as
`ofarm.runtimeproblem.v0.1` through `ctx.store.registry`, requires its
`reasonCode` to belong to `kernel.problems.REGISTERED_REASON_CODES`, and
deep-copies the validated JSON tree before retaining it. `REVIEW_REQUIRED`
requires severity `WARNING` and appends exactly that copy to
`ctx.review_route_reasons`. `REFUSED` requires severity `ERROR` and uses the
existing `_refusal(...)` path to emit exactly one
`VALIDATION/FAIL_REFERENCE_RESOLUTION` entry and return a `GateRefusal` with
fixed `RETAIN_DRAFT` final outcome and the one copied problem. `REVERIFIED`
passes its validated rationale to the existing `ctx.log(...)` path, which
alone writes the correlated in-memory and durable success entries.

The provider cannot choose or mutate the gate, gate outcome, final outcome,
problem-list cardinality, log correlation, or review-routing container through
the declared request. The old log-delta exception is removed: no provider-
written gate entry is valid or necessary. Malformed outcomes fail before
`VALIDATION/PASS`, `APPLICABLE`, or `UPDATED`; the enclosing transaction rolls
back earlier code-owned effects from the attempt.

These private request, enum, and outcome types are implementation mechanics,
not new schemas, reason codes, canonical records, or provider-owned governance
decisions. Return annotations document the contract but never replace runtime
validation of provider-controlled data.

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
- **PRSC-003 — One coherent Store-owned graph.** Policy, context, materializer,
  registry-reverification, and output services bind the Store descriptor;
  context, materializer, and output services bind the exact expected Store; the
  materializer binds the bundle's exact context assembler; the materializer
  and output assembler bind the bundle's exact specifications; the output
  assembler binds the bundle's exact materializer; the policy provider retains
  the expected Store RuntimeBundle's exact selected policy component; the
  registry service retains the exact outer capability-family object and, for a
  bound family, that RuntimeBundle plus the exact selected-input identity tuple
  (or, for no family, exact `None` bundle provenance plus an empty tuple); the
  SI factory and service constructor choose and require the exact REGSR
  `ReferenceFamily`; and policy ref plus required recognized rule refs match
  the descriptor.
- **PRSC-004 — One composition validator.** Provider factory results and
  explicitly injected graphs pass the same complete private validator. An
  injected refusal occurs before a transaction can start.
- **PRSC-005 — Truthful applicability success.** `APPLICABLE` is logged only
  after the assembler returns a non-empty built-in string
  `contextSnapshotId`.
- **PRSC-006 — Truthful materialization success.** `UPDATED` is logged and
  `materialization_triggered` becomes true only after recomputation returns
  non-empty built-in string `basisRef` and `snapshotRef` values.
- **PRSC-007 — Explicit implementation failures and generic refusal
  ownership.** Malformed graphs, incompatible signatures, malformed
  applicability or materialization result shapes, and any registry-
  reverification request or result outside the exact closed request/outcome
  model raise `ProfileRuntimeError`, not incidental `AttributeError`,
  `TypeError`, or `KeyError`. The profile service receives no generic mutable
  carrier and owns the applicability decision. Only `ValidationGate` mutates
  review reasons or assigns and logs registry success/refusal gate state;
  `NO_EFFECT` is the only silent result, and no misleading success, malformed
  review reason, provider-authored refusal, or mismatched log is committed.
- **PRSC-008 — Executable profile neutrality.** A test-only synthetic non-SI
  graph passes real `ProfileApplicabilityGate` and `MaterializationGate`
  execution, receives every invalidation keyword, and produces only synthetic
  profile-local context, materialization, output, package, policy, view, and
  result-shape identifiers. Its familyless registry service is called and may
  return `NO_EFFECT` without a product binding, decision number, lookup, or
  decorative reference data. It never enters the production registration
  tuple.
- **PRSC-009 — SI assertion equivalence.** For unchanged inputs, provider-
  loaded and explicitly injected SI services preserve decision outcomes,
  problems, gate names and order, materialization key/specification identities,
  basis/snapshot reference families, output identities and qualifications, and
  receipt structure. Existing SI tests remain green; the permitted provenance,
  request/outcome, and constructor wiring changes no SI runtime behavior,
  selected data, or policy value.
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
| PRSC-003 | either path receives an exact dataclass with a foreign service descriptor, a different materialization/output specification instance, a different output materializer, wrong policy ref, or one missing required recognized rule ref | composition raises `ProfileRuntimeError` before transaction entry; the foreign service cannot execute |
| PRSC-003 | loader and explicit-injection tests each compose Store A with a coherent graph built for Store B while both Stores deliberately share the exact descriptor object | common validation rejects the graph before transaction entry; Store B's context, materialization, output, policy, or registry selected-input state cannot execute under Store A |
| PRSC-003 | either path receives a same-Store, same-descriptor bundle whose materializer retains context assembler A while the bundle carries distinct compatible assembler B | common validation rejects the split graph before transaction entry; the unrepresented assembler cannot drive recomputation |
| PRSC-003 | provider-loaded and explicit-injection tests each receive a descriptor-path policy provider, a provider retaining an equal-but-distinct or foreign/stale `PROFILE_POLICY` component with the same `policyId`, or a policy component from another RuntimeBundle | common validation rejects before any policy method is invoked; only the exact expected Store RuntimeBundle component can execute |
| PRSC-003 | provider-loaded and explicit-injection tests each compose for Store A with a registry service retaining RuntimeBundle B, absent/mismatched selected-input identities, an equal-but-distinct family, or selected inputs for a family other than its exact outer binding | common validation rejects before transaction entry or service invocation; no detached or cross-family registry data can execute |
| PRSC-003 | the otherwise normal SI outer bundle retains its exact REGSR capability-family binding, while a substituted registry service is coherently backed by truthful GERK or FFSNaprave selected inputs and names that wrong family | both provider-loaded and explicit-injection paths reject the exact same-descriptor wrong-family graph before transaction entry; descriptor membership and truthful digests cannot override the profile-owned REGSR binding |
| PRSC-003 | direct construction of the real SI registry service is attempted with the descriptor's exact GERK or FFSNaprave family, a private lookup whose loaded prefix differs from exact REGSR, or a compatibility lookup with no runtime provenance | the SI-owned constructor raises `ProfileRuntimeError`; a coherent wrong-family or detached SI service cannot be produced by the admitted factory |
| PRSC-004 | the same malformed graph is returned by the provider loader and supplied explicitly | both paths refuse through the common validator; an injected-store transaction counter remains zero |
| PRSC-005 | `GatePipeline.commit(...)` reaches a signature-compatible context assembler returning `{}`, `{"contextSnapshotId": ""}`, or a non-string ref | `ProfileRuntimeError`; transaction rollback; no committed `APPLICABLE` entry or promotion trace from the attempt |
| PRSC-006 | an accepted commit reaches a signature-compatible materializer returning a missing, empty, or non-string `basisRef` or `snapshotRef` | `ProfileRuntimeError`; no `UPDATED` entry, false success flag, or committed promotion/materialization effects |
| PRSC-007 | either composition path receives an absent/non-callable service or a callable whose inspected signature cannot prove every call form | composition raises one explicit `ProfileRuntimeError`; no incidental exception type becomes the boundary contract |
| PRSC-007 | `GatePipeline.commit(...)` for an operation claim reaches an admitted registry-reverification service returning `None`, `{}`, a non-empty dictionary, an arbitrary falsey/truthy object, `GatePass`, `GateRefusal`, a disposition lookalike, or an exact envelope with an unknown or field-inconsistent disposition | `ProfileRuntimeError` before `VALIDATION/PASS`, `APPLICABLE`, or `UPDATED`; no provider-selected refusal or promotion commits and the transaction leaves no durable effect from the attempt |
| PRSC-007 | five hostile legacy-style services separately try to write only a durable log through `request.store/request.cur`, append only to `request.gate_sequence`, log then remove the sequence entry, append a malformed value to `request.review_route_reasons`, or mutate an existing review-reason prefix | the exact request exposes none of those carriers; the attempted access is normalized to `ProfileRuntimeError`, prior generic state and both log carriers remain unchanged, and the transaction commits no trace from the attempt |
| PRSC-007 | an operation reaches a familyless service returning `NO_EFFECT`, or a service returns `REVERIFIED` with a non-empty rationale, `REVIEW_REQUIRED` with a schema-valid registered `WARNING` RuntimeProblem, or `REFUSED` with a schema-valid registered `ERROR` RuntimeProblem | every service is called once; respectively: no registry effect; exactly one correlated `VALIDATION/REGISTRY_REVERIFIED` entry; exactly one deep-copied review reason with the existing prefix unchanged; or exactly one logged `VALIDATION/FAIL_REFERENCE_RESOLUTION` and one `RETAIN_DRAFT` refusal problem |
| PRSC-007 | registry reverification raises an ordinary exception, returns malformed rationale/problem data, uses an unregistered reason code or wrong severity, or retains and later mutates its original problem dictionary | exceptions and malformed results become `ProfileRuntimeError` before a registry effect; accepted review/refusal state owns a deep copy and never aliases the provider dictionary |
| PRSC-007 | the exact SI service receives a claim whose captured-against ref is GERK or FFSNaprave while its current ref is REGSR | the service proves both refs belong to its exact REGSR family before private lookup/classification, returns the existing warning-shaped `PRODUCT_BINDING_UNRESOLVED` review result for the cross-family claim, and cannot report `REVERIFIED` |
| PRSC-008 | the synthetic provider is loaded and its real generic stages execute; its familyless registry service observes the detached request and returns `NO_EFFECT` | both stages pass; the registry service is called without product roles, a decision number, a lookup, or reference-source decoration; the observed invalidation arguments are complete; recursive request/result/log inspection finds no SI or production package identifier; production registrations remain unchanged |
| PRSC-008 | a profile-neutral test service with no product lookup reads a neutral claim marker and returns a valid certificate-style `REVIEW_REQUIRED` outcome | generic code calls it and applies exactly one copied review reason; neither composition nor request construction demands `CROP_PROTECTION_PRODUCT`, `registrationRef`, `decision_number`, or `lookup_by_decision` |
| PRSC-009 | the SI factory is inspected through its real loader, and the same SI scenario is composed through default loading and explicit injection | the factory and service bind the exact descriptor REGSR `ReferenceFamily`; stable semantic assertions, identities, outputs, receipts, and gate order are equivalent after normalizing only minted IDs/timestamps that were already volatile |
| PRSC-010 | production loader or route is asked for `profile_rs_organic_crop`, or a test inspects allowed/active registrations | no descriptor, registration, route, or execution exists; only `profile_si_ffs` remains active and registered |

The full commit-path cases for PRSC-005 and PRSC-006 must inspect committed
state after the raised error, not merely an in-memory log list, so rollback is
demonstrated. Small direct-stage tests may additionally pin the exact pre-log
ordering.

## 9. Proposed architecture and smallest change

### 9.1 Private value and service types

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

The context, materializer, and output protocols each declare their existing
`store` owner. The materializer also declares its existing `context` assembler.
The policy protocol declares the exact retained `RuntimeComponent` parsed by
the runtime-bundle construction path. The direct descriptor-path policy
constructor remains available to existing compatibility/readiness callers but
retains no runtime component and is therefore ineligible for executable graph
composition.

`DescriptorPolicyProvider.from_runtime_bundle(...)` accepts the exact frozen
`RuntimeComponent`, requires its `PROFILE_POLICY` role and descriptor policy
ref, retains that same object as `runtime_component`, and passes only its
`canonical_bytes` into the unchanged policy parser. The descriptor-path
constructor exposes `runtime_component = None`; it cannot manufacture an
executable provenance claim from a path or caller-supplied byte string.

`ProfileRuntimeServices` adds one field adjacent to
`registry_reverification`: `registry_reference_family`, whose exact value is
either one descriptor-owned `ReferenceFamily` object or `None`. It is a single
private binding for the existing single registry-reverification capability,
not a capability bag, registry, descriptor extension, discovery key, or claim
that every provider needs reference data.

`ProfileRegistryReverification` declares only the generic composition bindings
and call that its consumer needs:

- exact `active_profile`;
- exact `reference_family`, identical to the outer binding including `None`;
- exact `runtime_bundle` for a bound family or exact `None` for no family;
- immutable `selected_input_bindings`, an ordered tuple of exact
  `(snapshot_ref, artifact_ref, source_digest)` triples, or an exact empty tuple
  for `None`; and
- `run(request) -> RegistryReverificationOutcome`.

It does not declare a product lookup, decision number, snapshot prefix, Store,
or generic context. Payloads are not duplicated into the selected-input marker.
The selected-input tuple states which already selected immutable inputs back
the service; it is not a lookup API or a second selection authority.

The SI factory and the existing SI-specific registry service constructor are
the profile-owned semantic authorities for the current capability. They obtain
and require `descriptor.reference_family(SI_REGSR_FAMILY_ID)`; construction
with GERK, FFSNaprave, an equal copy, or any other family raises
`ProfileRuntimeError`. The factory places that exact REGSR object in both the
outer bundle and registry service. The SI service keeps its existing
`SIProductRegister` as a private implementation detail. Narrow changes
to `SIProductRegister.load_from_store(...)` let it obtain the selected rows
once, build the unchanged private indexes, and retain the exact RuntimeBundle
and identity tuple from that same local row sequence. The SI registry service
constructor derives its generic provenance attributes from that exact private
lookup rather than accepting parallel caller claims, and refuses a lookup whose
runtime-loaded REGSR prefix is not its exact family's prefix or whose provenance
is absent. The common protocol never exposes or signature-checks
`lookup_by_decision(...)`.

Direct compatibility construction has no runtime-bundle provenance and cannot
compose until this exact Store-loading path has completed; existing direct SI
lookup callers remain otherwise unchanged. A familyless synthetic service
retains `reference_family = None`, `runtime_bundle = None`, and an empty
selected-input tuple. It needs no reference snapshot, source component, or
decorative RuntimeBundle binding.

`RegistryReverificationRequest`, `RegistryReverificationDisposition`, and
`RegistryReverificationOutcome` are the private frozen/slotted request and
closed result types specified in section 6.3. Their annotations are
documentation; exact request field, exact-type outcome, disposition-field,
problem-contract, reason-code, severity, and copy validation remain mandatory
at runtime. They do not add a durable type or change code-owned validator
results.

### 9.2 One graph validator

`kernel/profile_runtime_provider.py` refactors the existing validator into one
reusable private function. It retains every current exact-type, identity,
cross-binding, policy-ref, and required-rule check, then adds inventoried
callability and independent binding of every production call form. The loader
and `GatePipeline` pass the exact expected Store as well as its bound descriptor.
The validator requires:

- `context_assembler.store is expected_store`;
- `materializer.store is expected_store`;
- `output_assembler.store is expected_store`; and
- `materializer.context is context_assembler`.

It also requires the registry-reverification service's exact `active_profile`
identity to be the Store-bound descriptor. It resolves the descriptor-named
`PROFILE_POLICY` component from
`expected_store.runtime_bundle`, requires
`policy_provider.runtime_component is expected_component`, and therefore
rejects descriptor-path, equal-but-distinct, foreign, or stale policy data even
when `policyId` matches.

For registry capability provenance, the validator first requires the outer
`registry_reference_family` to be exact `None` or exact trusted
`ReferenceFamily`. A non-`None` value must be the identical object, not merely
an equal value or matching prefix, of one member of
`descriptor.reference_families`. It then requires:

- `registry_reverification.reference_family is
  services.registry_reference_family`;
- `registry_reverification.runtime_bundle` has the conditional value described
  below; and
- an exact built-in `selected_input_bindings` tuple containing only exact
  three-item built-in tuples of non-empty built-in strings.

For a bound family, `runtime_bundle` must be the exact
`expected_store.runtime_bundle`, and the tuple must exactly equal the ordered
identities freshly derived from
`expected_store.selected_reference_source_data(family.snapshot_prefix)`. For
`None`, `runtime_bundle` must also be exact `None` and the tuple must be exactly
empty. A list, tuple subclass, missing field, equal-but-distinct family,
truthful tuple for another family, foreign or decorative RuntimeBundle, or
provider-shaped lookalike is refused. No private lookup is in
the common protocol, signature inventory, or validator, and no service method
is invoked during composition. Missing provenance and all
inspection/admission failures become `ProfileRuntimeError`.

This cross-binding deliberately does not infer that a descriptor family's
meaning is suitable for a capability. The admitted profile factory owns that
semantic selection, and the SI implementation enforces its own exact REGSR
choice. The SI factory's focused assertion requires its outer binding to be
`descriptor.reference_family(SI_REGSR_FAMILY_ID)`; construction tests refuse
GERK and FFSNaprave, while common hostile tests keep the authoritative outer
binding fixed and prove that wrong-family service substitution fails on both
composition paths. Inventing a generic family-role vocabulary or duplicating
the SI identifier in common Kernel validation would create a second semantic
authority and is forbidden.

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

`kernel/validators.py` isolates the provider-owned registry-reverification call
from the code-owned validator-result convention. After the existing
`CodeBindingValidator`, a code-owned boundary helper builds the detached
request, invokes the service exactly once, validates the exact closed outcome
from section 6.3, and alone applies no effect, the corresponding success log,
copied review reason, or fixed refusal. It does not inspect product roles,
decision numbers, certificates, holdings, captured snapshot refs, or snapshot
advance. All provider exceptions, malformed envelopes, dispositions,
rationale, problem payloads, reason codes, or severities become
`ProfileRuntimeError` and rely on the existing transaction owner for rollback.

The SI registry-reverification service is descriptor-, exact-REGSR-family-,
and selected-input-bound when constructed. Its private product lookup was
populated from the exact Store-selected rows whose RuntimeBundle and immutable
source identities the service exposes. Within the SI service, and nowhere in
generic Kernel code,
the existing D9 logic decodes the detached claim and binding bytes, selects the
verified `CROP_PROTECTION_PRODUCT` binding, derives its captured-against ref,
extracts `registrationRef`, and invokes `lookup_by_decision(...)`.

Before any lookup or product classification, the SI service proves that a
present current ref and a present captured ref both equal its exact REGSR
family root or begin with that root plus `.`. A cross-family captured ref
returns `REVIEW_REQUIRED` with the existing warning-severity
`PRODUCT_BINDING_UNRESOLVED` problem family and can never produce
`REVERIFIED`; an impossible wrong-family current ref is a
`ProfileRuntimeError`. Missing/unverified product binding, missing current or
captured ref, or no snapshot advance returns `NO_EFFECT`. The existing
confirmable, expired, and unconfirmable branches respectively become
`REVERIFIED`, `REVIEW_REQUIRED` with `SUPERSEDED_RECORD_USED`, and
`REVIEW_REQUIRED` with `PRODUCT_BINDING_UNRESOLVED`, preserving their current
observable rationale/problem content. `REFUSED` is a supported private outcome
but no unchanged SI branch is reclassified to it.

Code-owned validators keep their existing results, all validator and gate
positions remain unchanged, and no provider can return a nominal `GateRefusal`
or mutate generic gate/review carriers through its declared input.

### 9.4 Synthetic evidence and SI preservation

`kernel/tests/_synthetic_profile_runtime.py` is upgraded to the exact private
contract. Its assembler and materializer return synthetic refs, and its
materializer exposes test-only observation of the complete invalidation call.
Its fake RuntimeBundle contains the exact synthetic policy component already
needed for policy provenance and no decorative reference-source component. Its
policy provider retains that exact component. Its registry service binds the
synthetic descriptor, declares no reference family or RuntimeBundle provenance,
retains an empty selected-input tuple, observes only the detached request, and
returns `NO_EFFECT`. Every actually Store-backed synthetic service retains that
same Store, and its materializer retains the exact synthetic context assembler.
It remains absent from `_REGISTRATIONS`.

Focused tests exercise actual generic stages, both composition paths, hostile
cross-wires/signatures/results, transaction rollback, SI equivalence, legacy-
policy exclusion, and Serbia refusal. Existing Kernel and architecture tests
provide the broad regression boundary.

This is the minimum coherent design because each defect is corrected at its
owner:

- declared shape in the private protocol;
- graph coherence at composition;
- exact runtime-selected policy and capability-bound reference-input
  provenance at composition;
- mutation-free registry request and result truth at the generic validation
  consumer;
- returned-value truth at the generic consumer; and
- neutrality through executable test evidence.

No new module, registry, schema, durable type, adapter, lookup service,
capability bag, or public surface is needed. The existing
`ProfileRegistryReverification` service gains a precise private call contract;
no second service abstraction is introduced.

## 10. Elegance audit

- Store-bound descriptor sources of truth: one.
- Provider source/import authorities: one existing D22/#240 path, unchanged.
- Complete graph validators: one.
- Composition entry points: two, converging on that validator.
- Runtime policy component authorities: the expected Store's one RuntimeBundle.
- Registry selected-input authorities: one existing Store method; the service
  retains only immutable provenance for comparison.
- Registry-reverification request builders and closed-outcome interpreters: one
  generic validation gate.
- Registry log, review-reason, and refusal authors: one generic validation gate;
  the provider supplies only classification, rationale, or problem data.
- Applicability success-transition points: one generic gate.
- Materialization success-transition points: one generic gate.
- Runtime result-reference validation helpers: one private consumer helper.
- New mutable production state: none.
- New private frozen values: one detached request and one outcome plus its
  closed enum; nested mappings remain untrusted until validation and copying.
- New public abstractions: none.
- Compatibility surfaces: none.
- Duplicate semantic payload state: none. The service's selected-input tuple is
  a narrow immutable identity attestation, not a second payload or selection
  authority. Detached canonical request bytes exist only for one call and are
  not retained or persisted. `TypedDict` shapes document existing returned
  fields and do not create runtime copies.

Deletable duplication is the partial type/descriptor validation branch in
`GatePipeline`. Incidental dictionary indexing at the two success log sites is
replaced by explicit extraction. Existing richer SI result fields are neither
copied nor narrowed.

The base commit leaves too little measured headroom for the proposed slice. The
partial validation branch deleted from `kernel/gates.py` cannot pay for the
work because that file, like `kernel/stages.py` and `kernel/validators.py`, is
not in the profile-runtime group. An earlier design was measured at about 255
service-protocol lines and about 931 complete production-group lines before
closed request/outcome and selected-input provenance were added. The now-
rejected product-lookup protocol expanded those ceilings further. Removing
that common lookup and its synthetic decoration makes a smaller authorization
possible; retaining its 300/1,060/1,250 limits would preserve avoidable
headroom for the drift this revision removes.

If this exact contract is approved, Phase B authorizes only these explicit
ceiling changes in
`conformance/rewrite_architecture_check.py`:

| Guard | Base lines | Current ceiling | Contract ceiling after approval |
| --- | ---: | ---: | ---: |
| `GROUP_BUDGETS["profile runtime"]` | 867 | 900 | 1,050 |
| `MODULE_BUDGETS["kernel/profile_runtime_services.py"]` | 237 | 250 | 295 |
| `TEST_MODULE_BUDGETS["kernel/tests/test_profile_runtime_services.py"]` | 769 | shared 800 | 1,200 |

The earlier 975/265 design no longer fits the closed request/outcome types and
exact selected-component provenance required by review. The 295-line service
ceiling permits at most 58 added lines for the two minimum result shapes,
complete signatures and ownership declarations, optional family binding,
detached request, closed enum, and outcome; it does not budget a lookup
protocol. This PR additionally caps its final
`kernel/profile_runtime_provider.py` count at 340 and
`kernel/profiles/si_ffs/runtime_provider.py` at 100 even though their existing
repository ceilings are looser. The two group members outside the Phase B file
boundary remain fixed at their base counts: 251 lines for
`provider_import_policy.py` and 44 for `manifest_inputs.py`. The resulting
maximum authorized group spend is therefore 1,030 lines
(`295 + 340 + 100 + 251 + 44`); the 1,050-line aggregate guard is jointly
usable and leaves 20 lines of measurement margin without authorizing either
in-scope module to consume its unrelated historical headroom.

The service-test override provides 431 lines beyond the base for the complete
parameterized signature, cross-wire, policy/registry provenance, wrong-family,
neutral-applicability, legacy-mutation, closed-outcome, result, transaction,
and equivalence programme without moving
cohesive service-admission evidence into unrelated files or compressing it to
satisfy a physical-line accident. That allowance may contain only evidence
mapped to PRSC-001 through PRSC-010 and supporting test helpers used by that
evidence.

`kernel/profile_policy.py` and `kernel/context.py` are outside the profile-
runtime aggregate and receive no new module ceiling. Their permitted
provenance edits must fit every existing file, function, import, and
architecture guard.

These are maximum guardrails, not growth targets. All other production,
module, test, function, import, and architecture constraints remain unchanged.
Phase B must still delete duplication where coherent, may not pack statements
or introduce a framework to spend the headroom, and must report final counts.
Exceeding any revised ceiling or either PR-specific module cap is a stop
condition requiring a new contract.

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
- `kernel/profile_policy.py`, only to make the runtime-bundle constructor accept,
  retain, and parse the exact already selected frozen `RuntimeComponent` while
  leaving descriptor-path compatibility behavior unchanged outside executable
  service composition;
- `kernel/context.py`, only to retain the exact RuntimeBundle and immutable
  source-identity tuple already used by `SIProductRegister.load_from_store(...)`
  so its enclosing SI service can expose generic provenance, without changing
  selected rows, payloads, indexes, or lookup behavior;
- `kernel/gates.py`;
- `kernel/stages.py`;
- `kernel/validators.py`;
- `kernel/profiles/si_ffs/runtime_provider.py`, only to pass the exact selected
  policy component into the policy provider, select the exact descriptor-owned
  REGSR `ReferenceFamily`, and bind the existing registry-reverification
  service plus outer bundle to that same family and generic provenance;
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

The permitted `profile_policy.py` and `context.py` edits expose provenance that
their existing runtime construction paths already possess. They do not move
policy parsing, reference selection, Store, or RuntimeBundle authority and do
not make compatibility loaders executable. The SI provider construction edit
may only thread those exact retained values and the descriptor/family binding;
its product lookup remains an undeclared SI-private implementation detail. It
may not change snapshot prefixes, product-lookup contents or lookup
behavior, policy values or parsing, reference behavior, service ordering,
active defaults, or any SI result. A test-support edit outside the named files
requires proof that it is purely mechanical and inside this boundary;
otherwise implementation stops for an amendment.

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
| PRSC-003 | common Store-aware validator; exact policy-component retention; outer capability-family binding; registry RuntimeBundle/family/selected-input retention; SI constructor invariant | each descriptor/Store/context/spec/materializer/output/registry/policy/rule cross-wire, including path/foreign/stale policy, foreign registry bundle, equal or wrong family, wrong selected-input tuple, a Store-B graph sharing Store A's descriptor, a split materializer context, and direct real-SI GERK/FFSNaprave construction | every ownership, provenance, or graph mismatch refuses before a transaction or provider call; SI factory and service bind exact REGSR | focused two-module pytest |
| PRSC-004 | loader and explicit-injection branch | same validator reached from both; injected transaction counter stays zero | equivalent `ProfileRuntimeError` admission behavior | focused two-module pytest |
| PRSC-005 | `ProfileApplicabilityGate`; result-ref helper | missing/empty/non-string context ref | no `APPLICABLE`; full transaction rollback | focused hostile tests plus complete Kernel suite |
| PRSC-006 | `MaterializationGate`; result-ref helper | missing/empty/non-string basis or snapshot ref | no success flag/`UPDATED`; full transaction rollback | focused hostile tests plus complete Kernel suite |
| PRSC-007 | private request/enum/outcome types; detached neutral request construction; exact outcome/problem validation; provider applicability; sole generic effect application; result-ref helper | opaque/incompatible callable; malformed runtime mappings; every invalid registry result; five legacy mutation attempts covering durable-only, sequence-only, log/remove, malformed review append, and review-prefix mutation; provider exception; aliasing; valid no-effect, success, review, and refusal outcomes; SI cross-family captured ref | invalid cases expose only `ProfileRuntimeError` and roll back with generic carriers unchanged; every operation service is called once; lawful outcomes produce exactly their code-owned effect and copied problems; SI classifies only after same-family proof; no misleading success survives | focused hostile tests plus complete Kernel suite |
| PRSC-008 | synthetic fixture; neutral registry service; real generic stages | execute applicability/materialization; familyless `NO_EFFECT`; certificate-style review service without product API; recursive identifier scan | synthetic refs logged; complete invalidation args observed; neutral services execute without product bindings/lookups or decorative reference data; no SI leakage or production registration | `test_profile_runtime_neutrality.py` |
| PRSC-009 | SI provider's exact policy/registry provenance, exact REGSR outer/service binding, private lookup, and unchanged generic ordering | exact SI factory-family assertion; default-loaded versus explicit-injected SI scenario | stable normalized results, materializations, selected data, outputs, receipts, validation outcomes, and gate order; full Kernel suite passes | focused equivalence test plus complete Kernel suite |
| PRSC-010 | existing registration/selection/architecture authorities | Serbia load/route refusal; registration/default assertions; forbidden-file diff; asymmetric extraction failure-set comparison | single-active-SI, no new extraction failure path, only explained removals caused by permitted edits, revised architecture ceilings, and all non-effects preserved | architecture, manifest, extraction, package, inventory, and diff checks |

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
and the review was posted by the PR-author account. The supporting evidence is
retained in [PR #362 comment 5539699935](https://github.com/samovers/OFARM2/pull/362#issuecomment-5539699935).
The local unavailability and the review's non-pinned corroboration are both
reported rather than merged into a false authoritative PASS.

### 13.2 Required Phase B verification

Run and report the exact issue commands plus the required mechanical inventory
command, using `.venv/bin/python` when available or the exact repository-
supported interpreter path otherwise:

```sh
.venv/bin/python conformance/run_review_baseline.py update-inventory

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
signature, exact policy/registry provenance, exact REGSR and wrong-family
bindings, detached neutral request, `NO_EFFECT`, certificate-style non-product
classification, closed registry outcome, five legacy registry-mutation
attempts, problem-copy, result-shape, rollback, synthetic neutrality, SI
equivalence, legacy-policy exclusion, and Serbia cases. The
complete Kernel run is required for unchanged SI materialization, output,
receipt, and gate-order evidence. Generated historical executed-evidence files
must not change as a test side effect.

The extraction command is already non-zero at the exact base. Its Phase B
acceptance criterion is an asymmetric base/head comparison, not a false PASS
claim. The exact base reports these three seed-scan hit paths:

```text
conformance/review_baseline_test_inventory.json
kernel/tests/_synthetic_profile_runtime.py
kernel/tests/test_rewrite_architecture_check.py
```

The head failure-path set must be a subset of that exact base set. Any added
path, unexplained retained-path diagnostic-category change, or inability to
reproduce the base set is a stop condition. A removed path is allowed only when
the final report explains the precise permitted Phase B edit that removed its
seed hit. In particular, `_synthetic_profile_runtime.py` is currently a failing
path solely because its module docstring contains the term `non-SI`; the
required fixture edits may legitimately remove that token without creating
extraction evidence or authority. Inventory regeneration may likewise remove a
base hit only if the generated diff is mechanical and traceable to the approved
test changes.

The final report must show both exact path sets, preserve the extraction
command's actual exit status, and explain every allowed removal. This PR does
not authorize editing
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
- Pass the exact expected Store to the one common validator; bind every Store-
  backed service to it and bind the materializer to the bundle's exact context
  assembler.
- Require the policy provider to retain the expected Store RuntimeBundle's
  exact selected `PROFILE_POLICY` component; matching refs, ids, digests, paths,
  or foreign bytes are not substitutes for exact component identity.
- Bind registry reverification to the exact active descriptor and exact outer
  optional `ReferenceFamily`; require the expected RuntimeBundle and selected-
  input identity tuple only for a bound family, and exact absent/empty
  provenance for no family. Keep every lookup and domain interpretation
  private to the profile service.
- Make admitted profile source the semantic authority for the optional
  capability family, pin the SI factory and SI service constructor to the
  descriptor's exact REGSR family, and let generic validation prove only outer/
  service/descriptor/Store coherence. Do not add a common family-role or
  product vocabulary.
- Give registry reverification only a frozen detached request with no generic
  mutable carrier, call it for every operation that reaches its fixed position,
  and admit only the exact closed outcome states `NO_EFFECT`, `REVERIFIED`,
  `REVIEW_REQUIRED`, and `REFUSED`.
- Let `ValidationGate` validate every outcome and copied problem and exclusively
  author the corresponding no-op, success log, review reason, or fixed refusal.
- Treat explicit injection as a private graph handoff whose production caller
  owns source provenance; the common validator does not attest injected source.
- Preserve the existing `descriptor` policy binding and `active_profile`
  bindings on the other four services; naming unification is outside this PR.
- Authorize only the three jointly usable measured architecture ceilings and
  two stricter PR-specific production-module caps in section 10, and require an
  asymmetric extraction baseline: no new failure path and only explained
  removals caused by permitted edits.
- Validate returned references at the generic consumer immediately before
  success logging.
- Raise the existing `ProfileRuntimeError`; add no domain reason or schema.
- Demonstrate rollback through the real commit transaction in addition to
  direct stage ordering.
- Keep the synthetic provider test-only and the production registry unchanged.
- Preserve SI behavior and use #161 only as a later follow-up.

### Open decisions

None. The exact-head review choices about default-dependent call forms, Store
and context ownership, exact policy and capability-bound selected-input
provenance, profile-owned applicability/family choice, mutation-free neutral
registry input, closed outcome/effect semantics, registry descriptor identity,
explicit-injection provenance, jointly usable architecture ceilings, and
asymmetric extraction-baseline handling are closed above.

### Review disposition

- Blockers: the review of head
  `4de682c493ae2d39cd29ae6c897f928791a14a57` identified three: incomplete
  default-dependent call admission, an unenforced registry-reverification
  result contract, and an unbound registry-reverification service. This revised
  contract addressed those findings. Reviews of head
  `c47639972fc26a8bad72a212aafb5c0fb706f710` then identified the omitted
  zero-argument `evidence_policy()` call and an already-determined architecture-
  budget conflict. Head `646d24e7c4c46061b60369fc6771271208301468`
  then received a [formal review with two Blockers](https://github.com/samovers/OFARM2/pull/362#pullrequestreview-5113097179):
  the validator did not bind the graph to its exact Store or the materializer to
  its exact context assembler, and nominal `GateRefusal` acceptance did not
  prove a lawful logged refusal. This revision addresses both through sections
  5 through 9 and their hostile tests. Head
  `8848d089de01b941cd1f30272ecd5bb624724e70` then received a
  [formal review with two Blockers](https://github.com/samovers/OFARM2/pull/362#pullrequestreview-5113776610):
  the full mutable `GateContext` plus partial log-delta validation left durable
  log, in-memory log, and review-reason mutations unproved; and matching refs
  did not bind the policy bytes or product lookup to the exact runtime-selected
  components. This revision removes the generic mutable carrier from the
  service call, makes the generic gate the sole effect author, and adds exact
  policy-component and lookup-provenance checks plus the requested hostile
  cases. Head `e23872030e02d119a5695cb6c49cdd52d730847e` then received a
  [formal review with two Blockers](https://github.com/samovers/OFARM2/pull/362#pullrequestreview-5114622747):
  the common boundary had become an SI-shaped product-decision lookup and the
  capability had no authoritative exact-family binding. This revision removes
  all product lookup, product role, decision-number, and generic applicability
  logic from the common contract; adds provider-owned `NO_EFFECT`; binds the
  service to one exact optional outer `ReferenceFamily` plus Store-selected
  input identities; pins the SI provider and service constructor to exact
  REGSR; and adds familyless, certificate-style, GERK, FFSNaprave, and cross-
  family hostile evidence. It
  makes no claim of clearance before a new exact-head review.
- Should-fixes: the [same-head focused review comment](https://github.com/samovers/OFARM2/pull/362#issuecomment-5540642541)
  found that the 950/265 ceilings were not jointly spendable and that exact
  extraction-set equality could stop a correct synthetic-fixture edit. The
  following revision used 975/265 coupled ceilings; the latest blocker-driven
  type/provenance additions first required bounded 1,060/300 limits. Removal of
  the rejected common lookup now reduces those to the jointly usable 1,050/295
  limits and the 1,200 focused-test cap in section 10. Section 13.2 permits only
  explained removals while refusing every new failure path.
- Account provenance: these review artifacts were posted by the PR-author
  account. Their findings are incorporated as exact-head technical review, but
  they are not represented as independent authorship. The task user's explicit
  approval remains the separate Phase B authority required by this workflow.
- Follow-ups: #161, only after #160 is implemented, reviewed, and merged.
  Optional unification of `descriptor` and `active_profile` naming is a separate
  future refactor, is not required here, and has no issue or implementation in
  this PR.
- Preferences: the extraction-baseline criterion and descriptor-name
  clarification requested at the prior head are incorporated.

### Merge stop rule

Phase B must not begin until an exact-head Phase A review finds no demonstrated
in-scope Blocker and the task user explicitly approves this exact contract.
Approval authorizes only bounded implementation in the same named draft PR; it
does not authorize merge.

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
   mutable registry, capability bag, generic family-role vocabulary,
   multi-family registry capability, or profile composition becomes necessary;
4. a Serbian descriptor, provider, fixture, or activation becomes necessary;
5. D22/#240 provider import or bytecode authority must change;
6. a schema, migration, manifest, `ActiveArtifactSet`, evidence lane,
   capability, activation, canonical-law, or readiness change becomes
   necessary;
7. authorization, database, deployment, security-audit, or key-custody
   authority must change;
8. an SI policy value or parsing rule, RuntimeBundle or Store selection rule,
   selected reference source or payload, registry lookup/indexing behavior,
   adapter, output claim, or active default must change;
9. the only solution is a broad rewrite of materialization, output assembly,
   provider routing, or profile selection;
10. a new runtime module, an architecture-budget change beyond the three exact
    section 10 ceilings, or a final count beyond either PR-specific module cap
    is required;
11. `kernel/profile_policy.py` or `kernel/context.py` needs any change beyond
    the exact mechanical provenance retention authorized in section 11, or a
    different file outside the approved PR boundary needs a non-mechanical
    change; or
12. the extraction check adds a head failure path, changes a retained-path
    diagnostic without explanation, removes a path without a permitted-edit
    explanation, or cannot reproduce the exact base set in section 13.2.

The exact reviewed Phase A head and RFC digest must be recorded in the review
request. Any material change to the problem, trust model, authority map,
ordering, invariant, permitted effect, non-effect, PR boundary, stop condition,
or production posture requires another exact-head Phase A review and explicit
approval.
