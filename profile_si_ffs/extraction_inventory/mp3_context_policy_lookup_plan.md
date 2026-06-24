# MP3 Context And Policy Lookup Plan

## Status / Boundary

This file began as a documentation-only MP3 plan. That original planning PR did
not change runtime code, tests, contracts, schemas, manifests, evidence files,
generated outputs, active artifact sets, adapters, profile substance, active SI
behavior, context snapshot behavior, policy decisions, validation routing, or
sufficiency outcomes.

The MP3a status section below records a later narrow runtime-helper
implementation for explicit profile-policy inputs. That status note does not
broaden MP3 into context assembly, active profile selection, descriptor registry,
manifest, evidence, adapter, second-profile, or Netherlands runtime work.

## Baseline And Stop Condition

This plan assumes PR #115 has merged and MP2 descriptor registry internals are
present on `main`. If PR #115 has not merged, this PR must not be based on
current `main`.

MP3 starts from the MP1/MP2 active-profile selection and descriptor-registry
surfaces:

- `config.ACTIVE_PROFILE`;
- `config.ACTIVE_PROFILE_SELECTION`;
- `config.ACTIVE_PROFILE_ROOTS`;
- `load_active_profile_selection(...)`;
- `ProfileDescriptorRegistry`;
- `ProfileDescriptorCandidate`;
- `load_profile_descriptor_registry(...)`.

MP3 must not reopen descriptor discovery, change active-profile selection, or
activate a second profile.

## Vocabulary

| Term | Meaning | Boundary |
| --- | --- | --- |
| Active profile descriptor | The `ProfileRuntimeDescriptor` selected through MP1/MP2 and currently represented by `config.ACTIVE_PROFILE`. | Descriptor input is configuration resolution, not Core law or a hidden truth store. |
| Profile-keyed context assembly | Context assembly that receives or derives its active profile descriptor explicitly instead of relying on unspoken SI globals. | Must preserve current SI context output for unchanged SI inputs. |
| Profile-keyed policy lookup | Policy loading that can receive an active descriptor or explicit policy path. | Policy values remain profile-owned; they do not become universal Kernel defaults. |
| Compatibility wrapper | A current-runtime wrapper that still uses `config.ACTIVE_PROFILE` / `config.EVIDENCE_POLICY_PATH`. | Exists only to preserve today's single-active-SI runtime behavior. |

## Future Implementation Boundary

Future MP3 implementation should add explicit-input internals while preserving
current config-backed wrappers.

Recommended future helpers:

- a context/bootstrap helper that accepts `ProfileRuntimeDescriptor`
  explicitly;
- NOW / AS_OF context assembly helpers that accept an active descriptor
  explicitly;
- profile-policy load functions that accept a descriptor or policy path
  explicitly;
- sufficiency internals that can receive loaded policy data explicitly;
- validator internals that can receive loaded policy data explicitly;
- compatibility wrappers that continue using `config.ACTIVE_PROFILE` and
  `config.EVIDENCE_POLICY_PATH` for the current single-active-SI runtime.

Compatibility wrappers may continue to use `config.ACTIVE_PROFILE` and
`config.EVIDENCE_POLICY_PATH` for the current single-active-SI runtime, but they
must not become hidden authorities for future multi-profile behavior.

`kernel/context.py` remains Kernel-owned mechanism code. A future MP3
implementation should stop treating active SI descriptor values as unspoken
globals where an explicit active-profile input is possible.

`kernel/profile_policy.py` remains the generic policy loader. A future MP3
implementation should support loading policy for a supplied active descriptor or
explicit policy path instead of only reading `config.EVIDENCE_POLICY_PATH`.

`kernel/sufficiency.py` and `kernel/validators.py` should keep default wrappers
for today's SI runtime, but future internals should be able to receive profile
policy data explicitly.

REGSR, GERK, and product-register behavior remain active SI runtime support for
the current single-active-SI runtime. MP3 may make their context/policy use
explicitly profile-keyed, but it must not move SI adapters, create a universal
country abstraction layer, or pretend those SI families are Core-generic
defaults.

## MP3a Implementation Status

MP3a implements explicit profile-policy input helpers only. It does not change
context assembly, active profile selection, descriptor registry behavior,
manifest generation, executed evidence, runtime adapters, active SI behavior, or
second-profile activation.

The MP3a helpers let future internals load policy content through an explicit
policy path or active profile descriptor while preserving the current
config-backed compatibility wrappers for the single-active-SI runtime.

## MP3b Implementation Status

MP3b implements explicit active-profile descriptor inputs for context bootstrap,
reference snapshot selection, and context assembly. It does not change active
profile selection, descriptor registry behavior, manifest generation, executed
evidence, runtime adapters, ProductRegister behavior, active SI behavior, or
second-profile activation.

The MP3b helpers let future internals assemble context from an explicit active
profile descriptor while preserving the current config-backed compatibility
wrappers for the single-active-SI runtime.

## Assertion-Equivalence Requirements

Future MP3 implementation must preserve assertion-equivalence for unchanged SI
inputs across:

- `ContextSnapshot` ids;
- `ContextSnapshot` payload shape;
- NOW / AS_OF refusal behavior;
- reference-family required/optional handling;
- REGSR/GERK/product-register context behavior;
- profile policy loading results;
- sufficiency case outcomes;
- validator routing and decision outcomes;
- error/refusal messages where they are part of existing tested behavior.

## Fail-Closed Rules

Future MP3 implementation must fail closed if:

- a context helper is called without an active profile descriptor where one is
  required;
- a supplied descriptor is malformed or not the active descriptor selected by
  MP1/MP2;
- a descriptor lacks a required reference family for the requested context mode;
- a required NOW or AS_OF reference family is missing;
- profile policy lookup is requested without an explicit descriptor or policy
  path where the helper requires one;
- a supplied policy path escapes the active profile root;
- loaded policy id does not match the active descriptor's `evidencePolicyRef`;
- sufficiency or validator internals receive no policy data where policy data
  is required;
- a profile-local policy value is accidentally treated as a universal Kernel
  default.

## Non-Claims

This plan and PR do not claim or create:

- MP3 runtime implementation;
- a second active profile;
- Netherlands runtime support;
- multi-profile runtime readiness;
- manifest generation changes;
- executed evidence changes;
- generated capability expansion;
- test harness discovery changes;
- production readiness;
- L5 Core country/profile neutrality certification;
- a universal country abstraction layer.

## Validation

Run from repository root:

```sh
python3 conformance/ofarm_profile_extraction_consistency_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --cached --check
```

Do not run pytest for this docs-only PR unless a reviewer asks. If pytest is run
and creates `conformance/evidence/platform_mvp_results_*.json`, remove the
generated evidence file before commit.
