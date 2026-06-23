# Active Profile Loader Status

Status: prior implementation status record. The active SI runtime descriptor
and loader described here are recorded as present, but this file does not move
files, change runtime behavior, update contracts or generated manifests, alter
tests, or change Core, Kernel, or Platform semantics.

This began as the PR D1 follow-up from `manual_review_backlog_plan.md`. It now
records the implemented boundary that moved active SI runtime bootstrap inputs
into `profile_si_ffs/runtime_profile_descriptor.json` while keeping the Kernel
loader generic and fail-closed.

## Goal

Record the current active-profile loader boundary that preserves the active SI
pilot behavior while making the profile/package ownership line explicit.

The implementation keeps exactly one active runtime profile:
`profile_si_ffs/`. It does not create a universal country abstraction, switch
the active runtime to another profile, claim Slovenia production readiness, or
make multi-profile pack selection dynamic.

## Implemented Boundary

| Area | Current responsibility | Implemented D1 treatment |
| --- | --- | --- |
| `profile_si_ffs/runtime_profile_descriptor.json` | Profile-local runtime descriptor for the active SI pilot. | Names active profile, pack, spine refs, evidence policy path/ref, ordered profile instance files, reference families, shipped snapshots, and context snapshot id prefix. |
| `kernel/profile_runtime.py` | Generic active-profile descriptor loader. | Loads and validates the descriptor fail-closed, resolves profile-local paths, validates active-spine coherence, validates evidence policy identity, and exposes a typed `ProfileRuntimeDescriptor`. |
| `kernel/config.py` | Runtime configuration and active deployment/demo binding. | Loads `ACTIVE_PROFILE` from the descriptor. Tenant identity remains separate as deployment/demo binding and is not descriptor content. |
| `kernel/context.py` `PROFILE_INSTANCE_FILES` | Shipped profile instance bootstrap file order. | Reads the ordered file list from `config.ACTIVE_PROFILE.profile_instance_files`. |
| `kernel/context.py` reference families | REGSR and GERK reference snapshot prefixes and REGSR data family. | Reads reference-family metadata from the descriptor while keeping register-specific lookup mechanics in Kernel runtime code. |
| `kernel/context.py` `ContextAssembler` | Selects active spine records and reference snapshots, then builds per-farm `ContextSnapshot` records. | Keeps the assembly algorithm Kernel-owned, but selects descriptor-pinned active spine refs and descriptor-declared reference families. |
| `kernel/profile_policy.py` | Generic loader for active profile evidence-review policy content. | Continues to load policy content from the descriptor-backed path exposed through `config.EVIDENCE_POLICY_PATH`. |
| `kernel/api.py` and tests | Call `context.bootstrap(store)` and assume the active SI spine is available. | Public bootstrap shape remains unchanged; tests pin descriptor-backed equivalence and fail-closed behavior. |

## Runtime Descriptor

`profile_si_ffs/runtime_profile_descriptor.json` is package content, not a
canonical contract and not OFARM Core law. It describes active profile-owned
runtime inputs for the current SI pilot.

The descriptor deliberately does not contain tenant authority or tenant
identity. `tenantRef` remains separate deployment/demo binding in
`kernel/config.py`.

The descriptor is discovered from the configured profile package root. It does
not contain `profilePackageRoot`; the loader rejects unknown fields rather than
allowing descriptor content to redirect loading.

Implemented fields:

| Field | Purpose |
| --- | --- |
| `descriptorVersion` | Local descriptor shape version, not a canonical contract version. |
| `profileRef` | Active profile ref, currently `profile:si.ffs.recordkeeping.v0_1`. |
| `packRef` | Active pack ref, currently `pack:si.ffs.pilot.v0_1`. |
| `packActivationSetRef` | Explicit PackActivationSet record expected in the active spine. |
| `activeArtifactSetRef` | Explicit ActiveArtifactSet record expected in the active spine. |
| `codeBindingProfileRef` | Active AgronomicCodeBindingProfile ref. |
| `evidencePolicyRef` | Active evidence-review policy ref. |
| `evidencePolicyPath` | Profile-local policy file path. |
| `profileInstanceFiles` | Ordered files bootstrapped by `context.bootstrap`. |
| `referenceFamilies` | Context-relevant reference snapshot families, including family id, snapshot prefix, optional data family, required/optional behavior, missing-family behavior for NOW and AS_OF, and shipped snapshot refs. |
| `contextSnapshotIdPrefix` | Current SI context snapshot id stem, preserving `contextsnapshot:si.ffs`. |

The descriptor does not contain country-law rules, validation semantics, or
promotion rules. Those stay in profile-authored policy files, profile runtime
hooks, or existing Kernel mechanisms as appropriate.

## Active Spine Coherence

The implemented loader requires explicit `packActivationSetRef`,
`activeArtifactSetRef`, and `codeBindingProfileRef`. It also checks the shipped
profile instance payloads before `context.bootstrap` can treat them as the
active spine.

The descriptor fails closed unless all of these are true:

- the selected PackActivationSet declares exactly one active pack matching
  `packRef`;
- the selected PackActivationSet declares exactly one active profile matching
  `profileRef`;
- the selected ActiveArtifactSet declares exactly one active pack and one active
  profile matching the descriptor;
- the selected ActiveArtifactSet records the selected PackActivationSet in
  `sourcePackActivationSetRefs`;
- the selected ActiveArtifactSet and PackActivationSet carry matching active
  pack and active profile refs;
- the selected code-binding profile ref is present in the selected
  ActiveArtifactSet's deployed artifact refs;
- the selected evidence policy ref is present in the selected ActiveArtifactSet;
- the selected code-binding profile is active for the selected pack.

These checks protect the rule that a `ContextSnapshot` cannot be synthesized
from profile, pack, and artifact vintages that never existed together.

## Reference Family Currentness

The descriptor distinguishes spine vintages from reference families.

Spine vintages are required for context reconstruction. If the PackActivationSet,
ActiveArtifactSet, or AgronomicCodeBindingProfile vintage cannot be selected
unambiguously for NOW or AS_OF, the context is not reconstructible and the
runtime refuses rather than guessing.

Reference families are separate. The current SI runtime can assemble a context
with only the reference snapshot families that are in force at the evaluation
bound when the descriptor declares those families optional. Downstream
validation or verification may still refuse a specific operation that needs a
missing family.

Each descriptor reference family states:

- whether the family is required for NOW context assembly;
- whether the family is required for AS_OF context assembly;
- whether absence means `OMIT_FROM_CONTEXT` or `REFUSE_CONTEXT`;
- which data family, if any, backs lookup content for selected snapshots;
- which shipped snapshot ref, if any, is expected in the profile instance files.

The implementation preserves the existing SI behavior: missing spine vintages
and missing optional reference snapshots do not collapse into the same error
path.

## Loader Shape

The implemented loader:

1. Reads exactly one active profile descriptor from the configured SI profile
   package root.
2. Keeps tenant/demo binding separate from the descriptor.
3. Validates descriptor version, required refs, relative paths, known fields,
   active-spine coherence inputs, evidence policy identity, reference-family
   metadata, and file existence.
4. Resolves profile instance file paths without changing payloads.
5. Exposes a typed active profile object to `config`, `context.bootstrap`,
   `ContextAssembler`, `profile_policy`, and tests.
6. Fails closed on missing, unreadable, malformed, or incoherent descriptor and
   profile instance content.

The loader does not edit records, synthesize profile instance payloads, or
materialize current state. It is configuration resolution only.

Implemented hardening rules:

- reject absolute paths;
- reject `..` path segments and any path escape outside the configured profile
  package root;
- reject malformed refs for every required ref field;
- reject unknown descriptor fields;
- reject missing required files and duplicate profile instance file entries;
- reject duplicate reference family ids and duplicate reference snapshot
  prefixes;
- reject inconsistent required/missing-family behavior;
- reject shipped snapshot refs that do not match their declared family prefix;
- reject profile instance JSON read and parse failures through
  `ProfileRuntimeError`;
- reject `tenantRef` and `profilePackageRoot` as unknown descriptor fields.

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
  preserved until a later implementation PR proves a deliberate change.

## Non-Goals

- No Core, Kernel, Platform, contract, or generated manifest semantic changes in
  this status update.
- No multi-profile activation, dynamic pack overlap, or merge-trace design.
- No extraction of `kernel/validators.py`, `kernel/sufficiency.py`,
  `kernel/manifest.py`, root conformance evidence, or remaining root-owned
  active-runtime tests.
- No movement of SI demo payloads beyond the already documented D2a-D2d fixture
  boundary.
- No whole-Slovenia production-readiness claim.
- No Netherlands profile change.

## Stop Conditions For Future Work

Stop and re-plan if later work would require any of these without an explicit
implementation design and tests:

- Generated manifest updates.
- Contract schema edits.
- Changed `ContextSnapshot` payload content or ids for the existing SI pilot.
- Changed materialization keys for unchanged SI pilot inputs.
- Tenant identity embedded in a required profile package descriptor.
- Changed evidence sufficiency, validation, review, correction, refusal, or
  authority behavior.
- Dropped test coverage or reclassified executed evidence as design evidence.
- A generic country abstraction that absorbs profile law into Kernel.

## Evidence References

This status record points to prior implementation evidence. It is not, by
itself, a fresh validation run.

| Evidence type | Reference |
| --- | --- |
| Implementation/status commits | `d0a2d50` added the active profile loader design memo; `1c85b22` tightened the loader memo; `a79bf53` refreshed D1 loader design status. |
| Root test entrypoint | `kernel/tests/test_profile_runtime_loader.py` |
| Implementation validation command | `.venv/bin/python -m pytest kernel/tests/ -q` |
| Package validation command | `python3 conformance/ofarm_pkg_contract_check.py` |

## Validation Expectations

For documentation-only status updates to this file, run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

For implementation PRs touching the descriptor loader, context bootstrap, active
spine selection, or reference-family currentness, also run:

```sh
.venv/bin/python -m pytest kernel/tests/ -q
```

Implementation validation should continue to cover:

- `context.bootstrap(store)` inserts the same shipped profile instance records.
- NOW context assembly selects the descriptor-pinned active artifact set,
  activation set, profile, evidence policy, and current reference snapshots.
- AS_OF context assembly keeps the same vintage-selection and refusal behavior.
- Active-spine coherence tests fail closed when selected pack activation,
  artifact set, active pack/profile refs, or code-binding profile do not match.
- Reference-family tests cover required missing, optional missing, NOW, and
  AS_OF behavior.
- Existing operation-claim, materialization, view, and manifest tests still
  pass.
- The descriptor loader fails closed on missing files, unknown required fields,
  unknown fields, malformed refs, absolute paths, `..`, path escapes, invalid
  relative paths, malformed profile instance JSON, and unreadable profile
  instance files.

## Remaining Future Work

D1 does not authorize a wider profile-loader architecture. Any future
multi-profile loader, profile manifest generation, validator hook extraction,
sufficiency text neutralization, demo facade shrink, or conformance evidence
split must stay in its own scoped PR lane.
