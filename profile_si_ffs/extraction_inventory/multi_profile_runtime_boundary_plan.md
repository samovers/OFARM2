# Multi-Profile Runtime Boundary Plan

Status: documentation-only future architecture plan. This file does not change
runtime behavior, activate a second profile, update contracts, update generated
manifests, regenerate evidence, alter tests, move SI runtime support, or change
Core, Kernel, Platform, Netherlands profile, or Slovenia profile semantics.

## Goal

Define the smallest honest path from the current single-active-SI-runtime
architecture to a possible future runtime that can host more than one active
profile.

This is not an SI extraction follow-up. `si_extraction_practical_closeout.md`
records that ordinary SI extraction is practically complete under the current
architecture. This plan is for later multi-profile runtime work only.

## Current State

The repository currently has one active runtime profile:
`profile_si_ffs/`.

The active SI pilot is grounded by:

- `profile_si_ffs/runtime_profile_descriptor.json`;
- the generic loader in `kernel/profile_runtime.py`;
- active SI context assembly in `kernel/context.py`;
- active profile policy loading in `kernel/profile_policy.py`;
- profile-local SI adapters under `kernel/profiles/si_ffs/**`;
- profile engineering tests under `profile_si_ffs/tests/**` with root
  discovery bridges;
- root platform MVP tests and evidence under `kernel/tests/**` and
  `conformance/evidence/**`;
- the active SI manifest and active artifact set, with capability claims
  grounded in approved generated or generator-verified runtime outputs.

The Netherlands GO + GLMC 7 package remains a narrow legal-source/profile
slice. It is not active runtime support and must not be listed as active
runtime capability until a separate implementation provides the required
descriptor, adapters, tests, evidence lane, and generated or generator-verified
manifest grounding.

## Boundary Definitions

| Term | Meaning | Boundary |
| --- | --- | --- |
| Active runtime profile | A profile package the current runtime can actually load, execute, test, and ground in evidence. | May be claimed only after loader, context, policies, adapters, tests, evidence, and manifest grounding exist. |
| Profile package | Profile-owned law, descriptors, policies, fixtures, tests, adapters, and reference data. | Profile content does not become Core law merely because the runtime can load it. |
| Design-only profile slice | Profile-local source, law, design, or planning material without executable runtime support. | Must never appear in active profile refs, generated manifests, or executed evidence claims. |
| Runtime descriptor | Profile-local configuration that selects active runtime inputs for a profile. | Configuration resolution only; not a canonical contract and not a hidden truth store. |
| Active runtime manifest | Approved generated or generator-verified manifest describing what the current runtime can execute now. | Must not be hand-claimed; must stay grounded in actual active runtime surfaces. |
| Profile navigation index | Human navigation for profile-local docs and status artifacts. | Navigation-only, non-capability, not runtime support, not a manifest, and not evidence. |

## Future Work Lanes

| Lane | Current owner | Future target | Stop condition |
| --- | --- | --- | --- |
| Active profile selection | `kernel/config.py` and `profile_si_ffs/runtime_profile_descriptor.json` | Explicit configuration model for selecting one or more active runtime profiles. | Stop if selection can silently activate a design-only slice. |
| Descriptor loading | `kernel/profile_runtime.py` | Descriptor registry or loader shape that can validate multiple profile descriptors fail-closed. | Stop if descriptor content can redirect loading outside its profile root or bypass active-spine checks. |
| Context bootstrap | `kernel/context.py` | Profile-keyed context bootstrap and context snapshot assembly that preserves current SI behavior. | Stop if unchanged SI inputs produce different context records or refusal behavior. |
| Profile policy loading | `kernel/profile_policy.py`, `kernel/sufficiency.py`, `kernel/validators.py` | Profile-keyed evidence and validation policy lookup without SI text leaking into other active profiles. | Stop if policy values are treated as universal Core defaults. |
| Runtime adapters | `kernel/profiles/si_ffs/**` and future profile adapter packages | Profile-owned adapters discovered only for profiles that are actually active. | Stop if a claimed import/export surface lacks a real adapter and tests. |
| Views and query artifacts | `views/**` plus profile-local view plans | Active-profile view/query claims tied to real artifacts and tests. | Stop if view capability is claimed from navigation or design docs. |
| Test harness | `kernel/tests/**`, `profile_si_ffs/tests/**` | Root collection that can discover profile harnesses deliberately while keeping suite labels honest. | Stop if engineering tests are relabeled as platform MVP evidence. |
| Evidence lanes | `conformance/evidence/**` | Separate evidence lanes for root platform MVP evidence and any future profile executed evidence. | Stop if historical evidence is moved, renamed, overwritten, or relabeled. |
| Manifest generation | `kernel/manifest.py` and active artifact sets | Per-active-profile generated or generator-verified manifests, or a root aggregate index of active manifests. | Stop if a design-only profile slice is added to active capability claims. |

## Minimum Implementation Sequence

The smallest safe future path is staged. Later PRs should stop at the first
stage whose preconditions are not met.

| Stage | Purpose | Required proof |
| --- | --- | --- |
| MP0 | Planning only. | This document exists and does not change runtime behavior. |
| MP1 | Define active-profile selection. | The runtime can state which profile package or packages are active without changing current SI behavior. |
| MP2 | Generalize descriptor loading. | Multiple descriptors can be found and validated fail-closed, but only explicitly active descriptors are loaded. |
| MP3 | Profile-key context and policy lookup. | SI context and policy behavior remain byte-for-byte or assertion-equivalent for unchanged inputs. |
| MP4 | Generalize test harness discovery. | Profile engineering tests remain discoverable without becoming platform MVP evidence. |
| MP5 | Define profile executed-evidence writer. | Profile evidence has a distinct suite id, path, and honesty note. |
| MP6 | Generalize manifest generation. | Only active profiles with real descriptors, adapters, tests, evidence, and artifact grounding receive generated or generator-verified capability claims. |
| MP7 | Activate a second runtime profile. | The second profile has real runtime surfaces and passes the same grounding checks as SI. |

MP7 must not be used to activate the Netherlands GO + GLMC 7 design slice unless
that slice has first become an implemented runtime profile through separate,
reviewed work.

## MP1 Implementation Status

MP1 is implemented as explicit single-active-profile selection in
`kernel/config.py` and `kernel/profile_runtime.py`.

The runtime now exposes:

- `ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES`;
- `ACTIVE_PROFILE_PACKAGE_NAMES`;
- `ACTIVE_PROFILE_SELECTION`;
- `ACTIVE_PROFILE_ROOTS`;
- `ACTIVE_PROFILE`;
- `PROFILE_ROOT`.

The default and only enabled package remains `profile_si_ffs`. The selector
fails closed if selection is empty, unsafe, duplicated, names more than one
active package, names a package that is not enabled for this runtime, or points
to a profile directory without `runtime_profile_descriptor.json`.

This is still not multi-profile runtime readiness. MP1 does not activate a
second profile, does not add the Netherlands GO + GLMC 7 design slice to runtime
claims, does not change manifests, does not create profile-local executed
evidence, and does not change current SI pilot behavior.

MP2 is planned in `mp2_descriptor_registry_plan.md`. That plan is
documentation-only and does not implement descriptor registry loading or activate
a second profile.

## Preconditions Before Any Runtime PR

A runtime implementation PR must state which stage it targets and prove:

- current active SI behavior is unchanged unless the PR explicitly targets a
  deliberate SI runtime change;
- no design-only profile slice is promoted into active runtime capability;
- profile descriptors fail closed on missing, malformed, incoherent, or unsafe
  content;
- tenant or deployment identity does not become inherent profile package law;
- profile evidence and validation policy values stay profile-owned;
- generated or generator-verified manifests remain grounded in actual runtime
  surfaces;
- test and evidence labels stay honest;
- assertion/history-first truth and governed current-state materialization stay
  intact.

## Non-Claims

This plan does not claim:

- multi-profile runtime readiness;
- active Netherlands runtime support;
- Slovenia production readiness;
- Netherlands production readiness;
- L5 Core country/profile neutrality certification;
- generated manifest capability expansion;
- profile-local executed evidence;
- platform production readiness;
- a universal country abstraction layer.

## What Must Not Happen Next

- Do not reopen SI extraction micro-PRs under the name of multi-profile work.
- Do not move `kernel/context.py`, `kernel/demo.py`, `kernel/manifest.py`,
  root tests, or root conformance files merely to make the tree look cleaner.
- Do not edit generated manifests or active artifact sets in a planning PR.
- Do not modify contracts without explicit schema approval and migration notes.
- Do not turn `profile_navigation_index.json` into runtime discovery.
- Do not treat the current SI harness bridge as a generic profile discovery
  mechanism without a deliberate harness design.
- Do not run or write new evidence files unless the PR intentionally changes an
  executed evidence lane.

## Validation For This Plan

For this documentation-only plan, run:

```sh
python3 conformance/ofarm_profile_extraction_consistency_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

For future runtime implementation stages, also run:

```sh
.venv/bin/python -m pytest kernel/tests/ -q
```

If a documentation-only PR accidentally creates
`conformance/evidence/platform_mvp_results_*.json`, remove that new generated
evidence before commit unless the PR intentionally changes executable evidence
grounding.

## Definition Of Done For Multi-Profile Runtime Readiness

Multi-profile runtime readiness is done only when every active profile has:

- an explicit active runtime descriptor;
- profile-owned law, policy, reference, adapter, and fixture content;
- fail-closed context, policy, validation, and adapter loading;
- profile-aware tests that remain discoverable from the intended root command;
- an honest executed evidence lane if executed profile evidence is claimed;
- generated or generator-verified manifest claims grounded in actual runtime
  surfaces;
- no design-only profile slices presented as executable capability.

Until then, the runtime remains the current single-active-SI pilot plus
profile-local design slices.
