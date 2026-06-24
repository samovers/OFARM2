# MP2 Descriptor Registry Plan

## Status

This is a documentation-only MP2 plan for a later descriptor-registry
implementation PR.

This plan does not:

- change runtime behavior;
- activate a second profile;
- change Core, Kernel, Platform, Netherlands profile, or Slovenia profile
  semantics;
- change contracts, schemas, generated manifests, active artifact sets,
  adapters, tests, evidence files, generated outputs, or profile substance;
- create a generated manifest, executed evidence, conformance, production, or
  multi-profile runtime readiness claim.

## Baseline And Stop Condition

This plan assumes PR #113 has merged and MP1 active-profile selection is present
on `main`. If PR #113 has not merged, an MP2 descriptor-registry planning PR must
not be based on current `main`.

MP2 planning starts from the MP1 active-profile selection identifiers and
concepts:

- `OFARM_ACTIVE_PROFILE_PACKAGES`;
- `ACTIVE_PROFILE_PACKAGE_NAMES`;
- `ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES`;
- `ACTIVE_PROFILE_SELECTION`;
- `ACTIVE_PROFILE_ROOTS`;
- `ACTIVE_PROFILE`;
- `PROFILE_ROOT`.

MP2 must preserve current SI behavior unless a later, separately reviewed
runtime implementation PR explicitly changes it.

## Vocabulary

| Term | Meaning | Boundary |
| --- | --- | --- |
| Profile package | An immediate `profile_*` child directory of repository `PACKAGE_ROOT`. | Profile content does not become Core law merely because the package exists. |
| Discoverable package | A safe immediate `profile_*` directory, whether or not it has a runtime descriptor. | Discovery is filesystem package discovery only, not runtime activation. |
| Descriptor candidate | A discoverable package that contains `runtime_profile_descriptor.json`. | Candidacy means the descriptor must validate fail-closed if the registry loads it. |
| Enabled package | A package name allowed by `ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES`. | Enablement is a runtime allow-list decision, not a descriptor-discovery result. |
| Selected package | A package named by `OFARM_ACTIVE_PROFILE_PACKAGES` / `ACTIVE_PROFILE_PACKAGE_NAMES`. | Selection requests activation but does not bypass enablement or descriptor validation. |
| Loaded active descriptor | A selected, enabled descriptor candidate that passes descriptor validation. | MP1 still permits exactly one loaded active descriptor. |

These terms must not be collapsed. In particular, a package may be discoverable
without being a descriptor candidate, and a descriptor candidate may be present in
the registry without being enabled or selected for activation.

## Registry Source Rule

A later MP2 registry implementation must scan only immediate child directories of
repository `PACKAGE_ROOT`.

The registry must consider only simple repository-local directory names beginning
with `profile_`. It must not recursively scan nested directories, must not treat
non-`profile_*` names as profile packages, and must not follow any resolved path
outside `PACKAGE_ROOT`.

The registry must not use `profile_navigation_index.json`, README files,
navigation entries, design docs, profile indexes, or any other documentation
artifact as runtime discovery input. `profile_navigation_index.json` remains
navigation-only, non-capability, not runtime support, not a manifest, and not
evidence of active capability.

## Activation Rule

Descriptor candidacy is not runtime enablement. A package with a valid descriptor
may appear in the registry but still fail activation if it is not present in
`ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES`.

Activation remains sourced from `OFARM_ACTIVE_PROFILE_PACKAGES` and
`ACTIVE_PROFILE_PACKAGE_NAMES`. MP2 descriptor discovery must not implicitly add
packages to the active selection list and must not expand the enabled package
allow-list.

Current MP1 `load_active_profile_selection()` must still return exactly one
active profile until MP3 or a later deliberately scoped stage changes active
runtime behavior.

## Design-Only And Malformed Descriptor Rules

Descriptorless `profile_*` packages are discoverable packages, not descriptor
candidates.

For MP2, `profile_nl_go_glmc7_2026` remains design-only / legal-source material.
It must not appear in active profile refs, generated manifests, executed evidence
claims, adapter claims, active runtime support claims, or platform conformance
claims. If it or any other descriptorless package is selected, activation must
fail closed because selected runtime packages need runtime descriptors.

Descriptor-bearing `profile_*` packages are descriptor candidates. Registry
loading must fail closed on malformed descriptor candidates rather than silently
excluding them. A malformed descriptor candidate must not be treated as a
design-only package merely because validation failed.

Descriptor validation must continue to ensure descriptor content cannot redirect
loading outside the descriptor's profile root or bypass active-spine checks.

## Fail-Closed Conditions

The later MP2 implementation must fail closed for at least the following
conditions:

- unsafe path;
- non-`profile_*` name;
- non-immediate child path;
- path escape outside `PACKAGE_ROOT`;
- duplicate selected package names;
- duplicate discoverable or candidate package names after normalization or
  resolution;
- blank active-profile selection tokens;
- selected package has no descriptor;
- selected package is not enabled;
- malformed descriptor candidate;
- descriptor root escape;
- descriptor candidate whose profile-local file paths escape its profile root;
- duplicate `profileRef` among descriptor candidates;
- duplicate `packRef` among descriptor candidates;
- duplicate `packActivationSetRef` among descriptor candidates;
- duplicate `activeArtifactSetRef` among descriptor candidates;
- duplicate `contextSnapshotIdPrefix` among descriptor candidates;
- duplicate `codeBindingProfileRef` among descriptor candidates, unless a later
  accepted design explicitly permits sharing;
- duplicate `evidencePolicyRef` among descriptor candidates, unless a later
  accepted design explicitly permits sharing.

The duplicate-ref checks are registry-level collision checks. They do not make
non-selected descriptor candidates active, and they do not create manifest,
evidence, context, policy, or adapter claims.

## Future Implementation Shape

A later MP2 implementation PR should add registry-level types in
`kernel/profile_runtime.py`, likely:

- `ProfileDescriptorCandidate`;
- `ProfileDescriptorRegistry`;
- `load_profile_descriptor_registry(package_root, allowed_profile_package_names=None)`.

That implementation should make the current MP1 `load_active_profile_selection()`
use the registry internally. It must still return exactly one active profile
until MP3 or a later deliberately scoped stage expands active runtime behavior.

The registry should expose enough structured information for tests to prove that
SI is a descriptor candidate, descriptorless design-only packages remain
non-candidates, selected packages are explicit, enabled packages are explicitly
allowed, and loaded active descriptors are the only descriptors used by MP1
runtime selection.

## Non-Claims

This PR and plan do not claim or create:

- a second active profile;
- MP3 context or policy lookup changes;
- test harness discovery changes;
- manifest generation changes;
- executed evidence changes;
- generated capability expansion;
- Netherlands runtime support;
- Slovenia production readiness;
- Netherlands production readiness;
- multi-profile runtime readiness;
- L5 Core country/profile neutrality certification.

## Future Implementation Test Plan

A later MP2 implementation PR should include tests proving:

- the SI descriptor is discovered as a runtime descriptor candidate;
- the Netherlands GO + GLMC 7 package is discoverable as a package but not a
  runtime descriptor candidate;
- explicit SI activation remains unchanged;
- blank, unsafe, and duplicate active selections fail closed;
- duplicate descriptor refs across copied synthetic descriptor roots fail
  closed;
- duplicate `contextSnapshotIdPrefix` fails closed;
- selected design-only package fails closed;
- malformed descriptor candidate fails closed;
- descriptor root or file escape fails closed;
- full `kernel/tests/` still passes.

## Validation For This Docs-Only PR

Run from repository root:

```sh
python3 conformance/ofarm_profile_extraction_consistency_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --cached --check
```

Do not run pytest for this documentation-only PR unless a reviewer asks. If
pytest is accidentally run and creates
`conformance/evidence/platform_mvp_results_*.json`, remove the generated evidence
file before commit.
