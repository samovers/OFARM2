# Active Profile Loader Design Memo

Status: design memo only. This document does not move files, change runtime
behavior, update contracts or manifests, alter tests, or change Core, Kernel, or
Platform semantics.

This is the PR D1 follow-up from `manual_review_backlog_plan.md`. It records the
minimum design needed before `kernel/context.py` and `kernel/config.py` can stop
being the implicit SI pilot bootstrap surface.

## Goal

Define a future active-profile loader boundary that preserves the current SI
pilot behavior while making the profile/package ownership line explicit.

The first implementation after this memo should keep exactly one active runtime
profile: `profile_si_ffs/`. It should not create a universal country abstraction,
switch the active runtime to another profile, claim Slovenia production
readiness, or make multi-profile pack selection dynamic.

## Current Surfaces

| Area | Current responsibility | Future loader treatment |
| --- | --- | --- |
| `kernel/config.py` | Holds `PROFILE_ROOT`, tenant/profile/pack/policy refs, the shipped REGSR snapshot ref, and the evidence-policy path. | Split package descriptor content from active deployment/demo binding. Profile refs and paths can come from the descriptor; tenant identity stays deployment/fixture binding, not inherent profile package content. |
| `kernel/context.py` `PROFILE_INSTANCE_FILES` | Names the SI PackActivationSet, ActiveArtifactSet, ContextSnapshot, AgronomicCodeBindingProfile, and ReferenceSnapshot records to bootstrap. | Move the authored file list into the active profile descriptor or a profile-local runtime index. |
| `kernel/context.py` reference families | Hard-codes REGSR and GERK snapshot prefixes and the REGSR data family used by `ProductRegister`. | Let the descriptor name reference families required for context assembly, while keeping register-specific lookup code in profile/runtime hooks until validation hooks exist. |
| `kernel/context.py` `ContextAssembler` | Selects in-force spine vintages and reference snapshots, builds a per-farm `ContextSnapshot`, and reuses it when basis content is unchanged. | Keep the algorithm in Kernel, but supply active profile refs, evidence-policy refs, and reference-family prefixes from the descriptor. |
| `kernel/profile_policy.py` | Already loads the active profile evidence-review policy from `config.EVIDENCE_POLICY_PATH`. | Keep the generic loader shape; later code can receive the path from the active profile descriptor instead of a hard-coded config constant. |
| `kernel/api.py` and tests | Call `context.bootstrap(store)` and assume the active SI spine is available. | Preserve the public call shape until a harness PR can update tests without coverage loss. |

## Proposed Descriptor

Future implementation may add a profile-local authored descriptor, for example
`profile_si_ffs/runtime_profile_descriptor.json`. This memo does not create it.

The descriptor should be package content, not a canonical contract and not OFARM
Core law. It describes profile-owned runtime inputs. It must not carry tenant
authority or tenant identity as inherent package content.

Any `tenantRef` belongs in a separate active deployment/demo binding, such as a
local config value, fixture harness setting, or environment-selected demo
binding. If a future fixture descriptor names a tenant, that tenant is
fixture-only and must not be part of the required `ProfileRuntimeDescriptor`.

The descriptor should be discovered from the configured profile package root. It
should not need a `profilePackageRoot` field. If an implementation keeps such a
field for diagnostics, it must equality-check it against the containing package
root and reject any mismatch rather than use it to redirect loading.

A future Kernel loader can validate the descriptor fail-closed before bootstrap.

Minimum fields:

| Field | Purpose |
| --- | --- |
| `descriptorVersion` | Local descriptor shape version, initially a profile-loader implementation version, not a canonical contract version. |
| `profileRef` | Active profile ref currently `profile:si.ffs.recordkeeping.v0_1`. |
| `packRef` | Active pack ref currently `pack:si.ffs.pilot.v0_1`. |
| `packActivationSetRef` | Explicit PackActivationSet record expected in the active spine. |
| `activeArtifactSetRef` | Explicit ActiveArtifactSet record expected in the active spine. |
| `codeBindingProfileRef` | Active AgronomicCodeBindingProfile ref. |
| `evidencePolicyRef` | Active evidence-review policy ref. |
| `evidencePolicyPath` | Profile-local policy file path. |
| `profileInstanceFiles` | Ordered files bootstrapped by `context.bootstrap`. |
| `referenceFamilies` | Context-relevant reference snapshot families, including family id, snapshot prefix, optional data family, whether the family is required or optional for context assembly, and the explicit missing-family behavior for NOW and AS_OF. |
| `contextSnapshotIdPrefix` | Current SI context snapshot id stem, initially preserving `contextsnapshot:si.ffs`. |

The descriptor must not contain country-law rules, validation semantics, or
promotion rules. Those stay in profile-authored policy files, profile runtime
hooks, or existing Kernel mechanisms as appropriate.

## Active Spine Coherence

The descriptor must make the active spine explicit. `profileRef`, `packRef`, and
`profileInstanceFiles` are not enough by themselves.

A future loader must either:

- require explicit `packActivationSetRef`, `activeArtifactSetRef`, and
  `codeBindingProfileRef`; or
- define an equally deterministic resolution rule that selects exactly one
  PackActivationSet, ActiveArtifactSet, and AgronomicCodeBindingProfile and then
  proves the same coherence checks now enforced by `ContextAssembler`.

The coherence rule must fail closed unless all of these are true:

- the selected ActiveArtifactSet records the selected PackActivationSet in
  `sourcePackActivationSetRefs`;
- the selected ActiveArtifactSet and PackActivationSet carry the same active
  pack refs;
- the selected ActiveArtifactSet and PackActivationSet carry the same active
  profile refs;
- the selected code-binding profile ref is present in the selected
  ActiveArtifactSet's deployed artifact refs;
- the selected code-binding profile is active for the selected runtime bound.

These checks protect the existing rule that a `ContextSnapshot` cannot be
synthesized from profile, pack, and artifact vintages that never existed
together.

## Reference Family Currentness

The future descriptor must distinguish spine vintages from reference families.

Spine vintages are required for context reconstruction. If the PackActivationSet,
ActiveArtifactSet, or AgronomicCodeBindingProfile vintage cannot be selected
unambiguously for NOW or AS_OF, the context is not reconstructible and the loader
or assembler must refuse rather than guess.

Reference families are different. The current SI runtime can honestly assemble a
context with only the reference snapshot families that are in force at the
evaluation bound. A missing reference family can be acceptable when the family is
declared optional for that context; downstream validation or verification may
still refuse a specific operation that needs that family.

Each descriptor reference family should therefore state:

- whether the family is required for NOW context assembly;
- whether the family is required for AS_OF context assembly;
- whether absence means `OMIT_FROM_CONTEXT` or `REFUSE_CONTEXT`;
- which data family, if any, backs lookup content for selected snapshots;
- which tests prove both required and optional missing-family behavior.

The first implementation should preserve the existing SI behavior unless tests
prove a deliberate change. In particular, missing spine vintages and missing
optional reference snapshots must not be collapsed into the same error path.

## Loader Shape

A future loader can be small:

1. Read exactly one active profile descriptor from a configured package root.
2. Read tenant/demo binding separately when a fixture or deployment needs it.
3. Validate descriptor version, required refs, relative paths, known fields,
   active-spine coherence inputs, and file existence.
4. Resolve profile instance file paths without changing payloads.
5. Expose a typed active profile object to `context.bootstrap`,
   `ContextAssembler`, `profile_policy`, and later manifest/test harness work.
6. Fail closed on missing or malformed descriptor content.

The loader should not edit records, synthesize profile instance payloads, or
materialize current state. It is configuration resolution only.

Hardening rules:

- reject absolute paths;
- reject `..` path segments and any path escape outside the configured profile
  package root;
- reject malformed refs for every required ref field;
- reject unknown descriptor fields until a descriptor version explicitly
  introduces them;
- reject missing required files and duplicate active-spine refs;
- reject `profilePackageRoot` unless it exactly equals the containing profile
  package root when normalized.

## Invariants To Preserve

- The model/runtime split remains intact: the descriptor configures runtime
  loading; it does not become OFARM law.
- Country-specific law and source assumptions stay in profile packages, not
  Core, Kernel, or Platform.
- Assertion/history-first truth remains canonical; no loader output becomes a
  hidden truth store.
- `ContextSnapshot` materialization remains governed and basis-addressed.
- AS_OF reconstruction must keep the current refuse-over-pretend posture for
  missing, ambiguous, non-active, or incoherent spine vintages.
- Required and optional reference families must have explicit missing-family
  behavior for NOW and AS_OF.
- Mutable reference layers remain snapshots before use.
- Current SI pilot behavior, emitted records, and validation coverage must be
  preserved until a later implementation PR proves equivalence.

## Non-Goals

- No Core, Kernel, Platform, contract, or manifest semantic changes in this PR.
- No multi-profile activation, dynamic pack overlap, or merge-trace design.
- No extraction of `kernel/validators.py`, `kernel/sufficiency.py`,
  `kernel/manifest.py`, `kernel/tests/**`, or `conformance/**`.
- No movement of SI demo payloads before a profile fixture harness exists.
- No whole-Slovenia production-readiness claim.
- No Netherlands profile change.

## Stop Conditions For Implementation

Stop and re-plan if the first implementation would require any of these:

- Generated manifest updates.
- Contract schema edits.
- Changed `ContextSnapshot` payload content or ids for the existing SI pilot.
- Changed materialization keys for unchanged SI pilot inputs.
- Tenant identity embedded in a required profile package descriptor.
- Changed evidence sufficiency, validation, review, correction, refusal, or
  authority behavior.
- Dropped test coverage or reclassified executed evidence as design evidence.
- A generic country abstraction that absorbs profile law into Kernel.

## Validation Expectations

A future implementation PR should run the normal package check and the kernel
test suite. It should also prove equivalence for the existing SI pilot:

- `context.bootstrap(store)` inserts the same shipped profile instance records.
- NOW context assembly selects the same active artifact set, activation set,
  profile, evidence policy, and current reference snapshots.
- AS_OF context assembly keeps the same vintage-selection and refusal behavior.
- Active-spine coherence tests fail closed when selected pack activation,
  artifact set, active pack/profile refs, or code-binding profile do not match.
- Reference-family tests cover required missing, optional missing, NOW, and
  AS_OF behavior.
- Existing operation-claim, materialization, view, and manifest tests still pass.
- The descriptor loader fails closed on missing files, unknown required fields,
  unknown fields, malformed refs, absolute paths, `..`, path escapes, and
  invalid relative paths.

## Suggested Future PR

PR D1 implementation should be limited to:

- adding the profile-local descriptor;
- keeping tenant/demo binding separate from the required descriptor;
- adding a small Kernel loader for that descriptor;
- replacing hard-coded config/context reads with descriptor-backed values only
  where equivalence is pinned by tests.

Anything involving validators, sufficiency messages, manifest generation, demo
payload movement, or conformance lane splitting belongs to the later D3-D7 lanes.
