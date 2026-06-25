# MP7 Implementation Roadmap

Status: documentation-only roadmap. This file does not implement routing,
activate a second profile, widen active-profile selection, update runtime code,
write evidence, regenerate manifests, update active artifact sets, change tests,
change contracts or schemas, or add Netherlands, Serbia, or any other non-SI
runtime support.

This roadmap extends `mp7_multi_profile_runtime_readiness_plan.md`. It does not
supersede that MP7 design-gate plan and does not claim multi-profile runtime
readiness.

## Purpose

MP7 needs an endgame that is smaller than "make multi-profile runtime work."
The practical goal is to split future work into a fixed sequence of
implementation PRs, identify the first safe runtime slice, and keep stop
conditions strong enough that design-only packages cannot become active runtime
capability by accident.

## Current Baseline

The current runtime remains single-active-SI only.

- `profile_si_ffs` is the only allowed and selected runtime profile package.
- `profile_si_ffs/runtime_profile_descriptor.json` is the only active runtime
  descriptor.
- Descriptor discovery is not activation.
- Profile navigation indexes, README files, extraction inventory plans, source
  manifests, and harness descriptors are not runtime discovery or capability
  inputs.
- `profile_nl_go_glmc7_2026` and `profile_rs_organic_crop` remain design,
  legal-source, or implementation-candidate profile packages only. They have no
  runtime descriptor and must not become active runtime support.

## First Safe Runtime Slice

The first safe runtime slice should be:

> MP7.1: add a profile route record and resolver seam that still resolves only
> the current active SI descriptor.

MP7.1 is safe because it does not activate a second profile. It introduces the
runtime shape needed for future tenant/farm routing while preserving the current
single-active-SI behavior.

MP7.1 should be allowed to:

- define a small route record shape for governed tenant/farm context;
- add a resolver that returns exactly one descriptor;
- require every resolved route to point to an enabled, selected, descriptor-
  bearing package;
- default current demo/runtime paths to the existing SI route;
- fail closed for missing, ambiguous, descriptorless, disabled, or design-only
  routes;
- prove unchanged SI inputs remain assertion-equivalent.

MP7.1 must not:

- allow more than one active runtime profile;
- enable `profile_nl_go_glmc7_2026`, `profile_rs_organic_crop`, or any other
  design-only package;
- widen manifest claims;
- write profile executed evidence;
- change generated manifests or active artifact sets;
- introduce a generic country abstraction layer.

## MP7.1 Implementation Status

MP7.1 is implemented as an explicit profile route record and resolver seam. The
resolver still resolves only explicitly supplied route records against the
current descriptor registry and selection inputs. It is not wired into
`GatePipeline`, active-profile selection, manifests, evidence, adapters, or
design-only profile packages.

## Fixed Implementation Sequence

The MP7 runtime work should stop at this fixed sequence unless a reviewer finds
a blocker that directly affects one of these slices.

| Slice | Purpose | Allowed change | Required proof | Stop condition |
| --- | --- | --- | --- | --- |
| MP7.1 | Route record and resolver seam. | Add route model/resolver in single-SI compatibility mode. | Existing SI route resolves to `profile_si_ffs`; non-SI or descriptorless routes fail closed. | Stop if the slice enables a second profile, uses navigation docs as route input, or changes manifest/evidence claims. |
| MP7.2 | Route handoff into runtime gates. | Pass the resolved descriptor into pipeline, context, policy, validation, sufficiency, advisory, materialization, output, and profile-sensitive adapter paths where a descriptor is already expected. | Default routed SI behavior is assertion-equivalent to current behavior. | Stop if any stage falls back to hidden global profile state after a route has been resolved. |
| MP7.3 | Route isolation tests. | Add focused tests proving two active, overlapping route records cannot govern the same tenant/farm/effective-time context and that design-only packages fail closed. | Ambiguous, missing, disabled, and descriptorless routes refuse governably. | Stop if tests rely on Netherlands or Serbia profile packages becoming runtime profiles. |
| MP7.4 | Candidate second-profile runtime preconditions. | Define, in executable checks, what a second profile must provide before activation: descriptor, policy, adapters, tests, evidence lane, and manifest grounding. | Candidate profile without every required surface remains inactive. | Stop if missing adapters, missing evidence, or missing manifest grounding are treated as warnings. |
| MP7.5 | Manifest and evidence readiness gate. | Extend generator verification and evidence-lane checks only after a real candidate runtime profile exists. | Capability claims are generated or generator-verified from actual runtime surfaces. | Stop if profile engineering tests or design docs are relabeled as executed evidence. |
| MP7.6 | Deliberate second-profile activation. | Activate a second runtime profile only behind explicit selection, enablement, and tenant/farm route records. | SI assertion-equivalence plus second-profile isolation and fail-closed route behavior. | Stop if same-farm multi-profile merge semantics are needed; that is outside MP7. |

MP7.1 through MP7.5 may be completed without activating a second runtime profile.
MP7.6 is the first slice that may deliberately activate one, and only if every
earlier precondition is satisfied.

## Stop Conditions For The Whole Track

Stop and re-plan if a future PR would:

- activate a second profile before MP7.6;
- enable or select a descriptorless package;
- route to a design-only package;
- treat descriptor discovery as enablement;
- treat `profile_navigation_index.json`, README files, source manifests, or
  design plans as runtime activation input;
- add Netherlands or Serbia runtime support without a real descriptor, adapters,
  tests, evidence lane, and manifest grounding;
- add same-farm multi-profile merge behavior;
- expand generated manifest capability claims without generator verification;
- write profile executed evidence without a machine-checkable
  `PROFILE_EXECUTED_EVIDENCE` shape;
- relabel root platform MVP evidence as profile evidence;
- change Core law, canonical contracts, or schema semantics as a side effect of
  routing work;
- introduce a universal country abstraction layer.

## Non-Claims

This roadmap and PR do not claim or create:

- MP7 runtime implementation;
- second-profile activation;
- multi-profile runtime readiness;
- Netherlands runtime support;
- Serbia runtime support;
- Slovenia production readiness;
- Netherlands production readiness;
- Serbia production readiness;
- profile executed evidence;
- generated manifest updates;
- active artifact set updates;
- manifest capability expansion;
- root pytest collection changes;
- schema or contract changes;
- L5 Core country/profile neutrality certification;
- external standard readiness.

## Roadmap Definition Of Done

This roadmap is done when:

- MP7.1 is named as the first safe runtime slice;
- future MP7 work is split into the fixed MP7.1-MP7.6 sequence above;
- every slice has a purpose, allowed change, proof, and stop condition;
- design-only package activation remains explicitly forbidden;
- manifest expansion and evidence relabeling remain explicitly forbidden;
- validation for this docs-only roadmap passes.

This roadmap does not authorize implementation by itself. Each implementation
slice still needs its own plan, tests, validation results, and review.

## Validation For This Roadmap

For this documentation-only roadmap, run:

```sh
python3 conformance/ofarm_profile_extraction_consistency_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --cached --check
```

Do not run pytest unless a reviewer asks. If pytest is accidentally run and
creates `conformance/evidence/platform_mvp_results_*.json`, remove that new
generated evidence file before commit because this roadmap does not change
evidence grounding.
