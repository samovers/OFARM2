# MP7 Multi-Profile Runtime Readiness Plan

Status: documentation-only MP7 design-gate plan. This file does not change
runtime behavior, active profile selection, descriptor loading, context assembly,
policy lookup, adapters, tests, evidence, manifests, active artifact sets,
contracts, schemas, Core, Kernel, Platform, Slovenia profile, Netherlands
profile, or any other profile semantics.

Change class: implementation/conformance planning implication. This is not
baseline law, not an accepted RFC extension, and not a capability claim.

Active authority surfaces considered:

- Constitution pack/profile law and PackActivationSet discipline;
- Platform pack/profile applicability gate;
- Platform package/runtime activation, conflict handling, and Capability Manifest
  discipline.

MP7 asks one question:

> What exact runtime behavior must change before OFARM2 can safely run more than
> one active profile, without confusing design-only profile packages with runtime
> capability?

MP7 is a design gate. It is not the implementation stage that activates a second
runtime profile.

## Current State

The current runtime remains single-active-SI only.

Current behavior and status:

- `profile_si_ffs/` is the only active runtime profile package;
- `profile_si_ffs/runtime_profile_descriptor.json` is the only loaded active
  runtime descriptor;
- `OFARM_ACTIVE_PROFILE_PACKAGES` may request active package selection, but MP1
  still permits exactly one active package;
- `ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES` still enables only `profile_si_ffs`;
- descriptor registry discovery may see other immediate `profile_*` packages,
  but discovery is not activation;
- descriptorless legal/design slices such as `profile_nl_go_glmc7_2026/` remain
  design-only and are not active runtime support;
- root platform MVP evidence remains under `conformance/evidence/` and is not
  profile executed evidence;
- generated or generator-verified manifests must continue to claim only actual
  active runtime surfaces.

## Vocabulary

MP7 separates five states that must not be collapsed.

| Term | Meaning | Boundary |
| --- | --- | --- |
| Discoverable profile package | Any safe immediate `profile_*` directory under repository `PACKAGE_ROOT`. | Filesystem discovery only. It is not descriptor candidacy, enablement, selection, routing, evidence, or manifest capability. |
| Descriptor-bearing runtime profile | A discoverable package that contains a valid `runtime_profile_descriptor.json`. | Descriptor candidacy means the descriptor must validate fail-closed; it does not make the package enabled, selected, routed, or claimed. |
| Enabled profile | A descriptor-bearing package allowed by runtime configuration. | Enablement is an explicit runtime allow-list decision; it is not automatic from discovery, navigation, README text, or descriptor presence. |
| Selected active profile | A package requested by `OFARM_ACTIVE_PROFILE_PACKAGES` / active-selection config. | Selection requests activation but must still pass enablement, descriptor validation, and future routing rules. |
| Runtime-routed profile | The profile descriptor actually used for a specific tenant/farm/commit/materialization/output request. | Routing must resolve exactly one enabled and selected descriptor before high-consequence gates run. |

Additional MP7 terms:

| Term | Meaning | Boundary |
| --- | --- | --- |
| Governed context | The tenant/farm/scope/time basis for a request that may affect canonical truth, materialization, or attested output. | It is the routing input; it is not itself a profile package. |
| Profile route | A future governed mapping from tenant/farm context to one enabled profile package and descriptor. | It must be explicit, auditable, time-aware where needed, and fail closed on ambiguity. |
| Design-only profile package | A profile-local legal, source, design, planning, or research slice without executable runtime support. | It may be discoverable for navigation, but it must never become enabled, selected, routed, evidenced, or manifested as active runtime support. |

## Design Questions Answered

### Is active profile selection global, tenant-scoped, farm-scoped, or request-scoped?

MP7 recommends tenant/farm-scoped routing.

The future runtime should treat profile discovery and active package selection as
candidate inputs only. An authoritative request must then resolve a route from
its governed context, at minimum `tenantRef` plus `farmRef` or an equivalent
farm-scoped anchor.

Recommended posture:

- not global discovery-based;
- not global selection-only;
- not ad-hoc request-profile override for authoritative operations;
- tenant/farm scoped by default;
- request input supplies governed context, not arbitrary profile law.

A future implementation may allow explicit administrative dry-run routing, but
that must remain non-authoritative unless a later accepted design says otherwise.

### Can one tenant have multiple active profiles?

Yes, but only across disjoint routed governed contexts.

A tenant may later have Farm A routed to one active profile and Farm B routed to
another active profile if both profiles satisfy activation preconditions. This
does not mean a single farm or commit is governed by multiple profiles at once.

### Can one farm be governed by multiple profiles at once?

No. MP7 keeps one runtime-routed profile per farm/governed context for the same
scope and effective time.

Multiple simultaneous profiles for one farm are out of scope until a later design
solves overlapping law, policy, evidence, event, materialization, and manifest
semantics with deterministic merge and trace behavior.

### How does a commit choose its profile?

A commit must not choose profile law by free-form request preference.

A future commit path must:

1. identify the governed tenant/farm context before profile-sensitive gates run;
2. resolve exactly one runtime-routed descriptor from that context;
3. verify that the resolved descriptor is discoverable, descriptor-bearing,
   enabled, and selected for this deployment/runtime;
4. assemble profile-specific context, evidence policy, validation policy,
   adapters, and materialization basis from that descriptor;
5. fail closed if the request-supplied profile, commit metadata, context snapshot,
   pack activation set, or active artifact set conflicts with the route.

The pack/profile applicability gate must run after routing resolution and before
profile-sensitive validation, evidence sufficiency, promotion, materialization,
or compiled-output generation.

### What happens if two profiles claim the same commit class?

For disjoint routed contexts, the overlap is not a runtime conflict: each commit
uses the one profile routed for its tenant/farm context.

For the same governed context, two profiles claiming the same commit class must
fail closed unless a later accepted implementation design provides explicit
surface-family merge law, precedence, conflict trace, and tests for that overlap.
MP7 does not define or allow same-farm multi-profile merge behavior.

### Can two profiles share refs?

Not by default.

Descriptor-bearing profiles intended for runtime activation must keep these refs
unique across descriptor candidates unless a later accepted design explicitly
allows sharing and proves deterministic traceability:

- `profileRef`;
- `packRef`;
- `packActivationSetRef`;
- `activeArtifactSetRef`;
- `contextSnapshotIdPrefix`;
- `evidencePolicyRef`;
- `codeBindingProfileRef`;
- policy refs, artifact set refs, and other descriptor-owned runtime refs that
  materially affect interpretation.

A future profile may reuse underlying public standards, source data, or code
libraries, but runtime descriptor refs must not collapse provenance or make two
profiles look like one active governance basis.

### Do profile-local tests become discoverable automatically?

No automatic runtime or evidence effect follows from profile-local tests.

Current profile engineering tests remain discoverable through root bridges and
approved harness descriptors. Future generalized harness discovery may discover
profile-local harness descriptors only through deliberate runtime/test harness
design. README files, navigation indexes, design docs, and source manifests must
not cause test execution, evidence writing, activation, or capability claims.

Profile-local tests remain engineering tests unless a later evidence-lane PR
executes them and writes clearly labeled profile executed evidence.

### Does platform evidence remain root-only?

Yes. Root platform MVP evidence remains root-owned under `conformance/evidence/`.
It must not be moved, overwritten, renamed, or relabeled as profile evidence.

Profile evidence, if later implemented, must use a distinct profile-local path,
suite id, evidence kind, honesty note, and non-claims.

### Do profile evidence artifacts become required before activation?

For a second active runtime profile, yes where executable profile behavior is
claimed.

Descriptor candidacy and design-only package discovery do not require executed
profile evidence. Runtime activation of a second profile must require enough
profile-specific tests and executed evidence to support every claimed runtime
surface. If a profile has no executed evidence for a claimed adapter, policy,
view/query, materialization, or output behavior, the runtime must not activate or
manifest that behavior as supported.

### What manifest claim is allowed for a second active profile?

Only a generated or generator-verified claim grounded in real active runtime
surfaces is allowed.

A future manifest may claim a second active runtime profile only after the
profile has:

- a valid descriptor;
- explicit enablement;
- explicit tenant/farm route;
- profile-owned context, policy, validation, adapter, view/query, and output
  grounding for every claimed surface;
- tests and, where claimed, executed profile evidence;
- generated or generator-verified manifest and active artifact set references;
- no unresolved design-only package contamination.

MP7 does not regenerate manifests, update active artifact sets, change
`minimumConformanceLevel`, expand capability claims, or create a root aggregate
active-profile manifest.

### What must remain impossible for design-only packages?

Design-only packages, including NL/RS-style legal/source/design slices, must not:

- be enabled as active runtime profiles;
- be selected successfully by `OFARM_ACTIVE_PROFILE_PACKAGES`;
- be runtime-routed for a tenant, farm, commit, materialization, or output;
- appear in active profile refs, active artifact sets, generated manifests, or
  capability claims;
- generate or receive executed profile evidence;
- contribute adapters, policy refs, context snapshot prefixes, code-binding refs,
  views, queries, or output claims;
- bypass descriptor, route, test, evidence, or manifest preconditions through a
  navigation index, README, source manifest, or design note.

## Routing Model Options

| Option | Description | MP7 assessment |
| --- | --- | --- |
| Global active profile | One profile selection applies to all tenants and farms. | Safe for current single-SI only; insufficient for real multi-profile runtime because it hides tenant/farm governance. |
| Global active profile list | Several profiles are selected globally and the runtime chooses later. | Rejected for MP7 unless paired with explicit tenant/farm routing; otherwise it creates ambiguity and capability overclaim risk. |
| Tenant-only routing | One profile per tenant. | Possible but too coarse where one tenant may operate farms under different legal/profile contexts. |
| Farm-only routing | One profile per farm without tenant boundary. | Better than global selection but weak for data-sovereignty and authority boundaries. |
| Tenant/farm routing | One explicit profile route per tenant/farm governed context. | Recommended conservative model. |
| Request-selected profile | Each request names the desired profile directly. | Rejected for authoritative operations because it can bypass governance unless constrained by tenant/farm route resolution. |

## Recommended Routing Model

MP7 recommends:

> Active profile routing is tenant/farm scoped, not automatic and not global
> discovery-based.

Required semantics for a later implementation:

1. Discovery finds safe immediate `profile_*` package candidates only.
2. Descriptor loading validates descriptor-bearing candidates fail-closed.
3. Runtime config enables an explicit allow-list of descriptor-bearing packages.
4. Runtime config selects the set of packages this deployment may activate.
5. A governed route maps each tenant/farm context to exactly one enabled and
   selected descriptor for an effective time/scope.
6. Commit, materialization, query, PassportView, DocumentAssembly, and adapter
   paths resolve the runtime-routed descriptor before profile-sensitive gates run.
7. The route result is included in context/materialization/output trace where it
   materially affects interpretation.
8. Zero routes, multiple routes, disabled routes, design-only routes, descriptor
   mismatch, or conflicting refs fail closed.

## Future Route Record Preconditions

A later route record or equivalent configuration object should include at least:

- route id;
- tenant ref;
- farm ref or governed farm-scope anchor;
- profile package name;
- descriptor identity or descriptor hash;
- `profileRef`;
- `packRef`;
- `packActivationSetRef`;
- `activeArtifactSetRef`;
- effective time interval or explicit timeless demo/deployment boundary;
- status such as DRAFT, ACTIVE, RETIRED, or REVOKED;
- approval or activation trace ref;
- route owner/steward;
- reason/refusal metadata for failed activation where relevant.

The route source must not be `profile_navigation_index.json`, README text,
source manifests, design notes, or tests.

## Activation Preconditions For A Second Runtime Profile

A second active runtime profile must not be activated until all of the following
are true.

### Descriptor and package preconditions

- The package is a safe immediate `profile_*` directory.
- It has a valid `runtime_profile_descriptor.json`.
- Descriptor paths remain inside the profile root.
- Descriptor refs are unique unless a later accepted design explicitly permits a
  shared ref.
- Required profile-local artifact files exist and validate fail-closed.
- Descriptor candidacy is separate from enablement, selection, and routing.

### Enablement and selection preconditions

- The package is explicitly enabled by runtime configuration.
- The package is explicitly selected by active-profile runtime configuration.
- Enabling or selecting a descriptorless package fails closed.
- Selecting more profiles than the runtime can route safely fails closed.
- Selection cannot be inferred from discovery, navigation, README files, or source
  manifests.

### Routing preconditions

- A tenant/farm route exists for every authoritative governed context that uses
  the profile.
- Each authoritative request resolves exactly one runtime-routed descriptor.
- Route ambiguity fails closed.
- Route absence fails closed for profile-sensitive authoritative operations.
- A request-supplied profile hint cannot override the tenant/farm route.
- Same-farm multi-profile governance remains out of scope.

### Runtime-surface preconditions

- Context assembly accepts an explicit routed descriptor.
- Evidence and validation policy lookup accepts explicit routed policy inputs.
- Sufficiency, validators, materialization, advisories, adapters, and output
  generation use the routed descriptor rather than hidden globals.
- Profile-owned values do not become universal Kernel defaults.
- No generic country abstraction is introduced by default.

### Test, evidence, and manifest preconditions

- Profile-local engineering tests are deliberately discoverable through an
  approved harness or root bridges.
- Executed profile evidence exists for claimed executable profile behavior.
- Root platform MVP evidence remains root-only and is not relabeled.
- Generated or generator-verified manifest output is grounded in actual active
  runtime surfaces.
- Unsupported surfaces remain unclaimed.

## Fail-Closed Conditions

A future implementation must fail closed for at least:

- unsafe profile package names or path escapes;
- descriptorless selected packages;
- malformed descriptor-bearing packages;
- enabled package without descriptor;
- selected package not enabled;
- selected package not routable for the governed tenant/farm context;
- route resolves zero profiles;
- route resolves more than one profile;
- request profile hint conflicts with the tenant/farm route;
- duplicate descriptor refs that materially affect interpretation;
- context snapshot prefix collision;
- active artifact set collision;
- evidence policy or code-binding ref collision unless later explicitly allowed;
- two profiles claiming the same commit class for the same governed context;
- missing profile-local policy required by a claimed gate;
- missing adapter for a claimed import/export surface;
- missing view/query artifact for a claimed view/query surface;
- missing executed profile evidence for a claimed executable profile surface;
- any attempt to use a navigation index, README, design doc, or source manifest as
  activation or capability grounding.

## MP7 Certification Levels

| Level | Meaning | Current MP7 posture |
| --- | --- | --- |
| MP7-L0 | Current state: single-active-SI only. | Current repository state. |
| MP7-L1 | Routing design accepted. | This document proposes the conservative tenant/farm routing model. |
| MP7-L2 | Profile activation preconditions defined. | This document defines preconditions but does not implement them. |
| MP7-L3 | Tests, harness, and evidence requirements defined in executable detail. | Not claimed by this PR. |
| MP7-L4 | Manifest requirements implemented or specified in generator-verifiable detail. | Not claimed by this PR. |
| MP7-L5 | Implementation may begin. | Not claimed by this PR. |

This documentation-only PR may support review toward MP7-L1/L2. It does not
certify MP7-L3, MP7-L4, MP7-L5, multi-profile runtime readiness, or second-profile
activation.

## Preserved Non-Claims

MP7 preserves:

- no generic country abstraction by default;
- no automatic activation from navigation indexes;
- no active NL/RS runtime support;
- no second active profile until a later implementation PR;
- no manifest capability expansion;
- no platform evidence relabeling;
- no production-readiness claim.

This plan also does not claim:

- generated manifest updates;
- active artifact set updates;
- platform MVP conformance changes;
- profile executed evidence;
- root pytest collection changes;
- schema or contract changes;
- Slovenia production readiness;
- Netherlands production readiness;
- L5 Core country/profile neutrality certification;
- external standard readiness.

## Implementation Split For Later PRs

A later implementation sequence should be split rather than bundled:

1. route data model and resolver contract;
2. config allow-list and selected-package widening, still fail-closed;
3. tenant/farm route lookup integrated before commit/materialization gates;
4. profile-keyed context, policy, validation, sufficiency, materialization, and
   output route plumbing;
5. profile harness/evidence execution lane for the second profile;
6. generated or generator-verified manifest updates;
7. end-to-end tests proving SI assertion-equivalence and second-profile isolation.

Each implementation PR must state whether it changes runtime behavior, generated
outputs, active artifact sets, tests, evidence, schema, or manifest claims.

## Validation For This Plan

For this documentation-only plan, run:

```sh
python3 conformance/ofarm_profile_extraction_consistency_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --cached --check
```

Do not run pytest unless a reviewer asks. If pytest is accidentally run and
creates `conformance/evidence/platform_mvp_results_*.json`, remove that new
generated evidence file before commit because this plan does not change evidence
grounding.
