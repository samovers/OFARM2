# Manifest Implementation Checklist

Status: planning checklist only. This file does not change `kernel/manifest.py`,
regenerate manifests, update contracts, move runtime adapters, change tests, or
alter Core, Kernel, Platform, or active SI pilot semantics.

This is the D5a follow-up to `multi_profile_manifest_design.md`. It defines the
terminology and review checklist a later implementation PR must satisfy before
touching generated manifest behavior or manifest tests.

## Terminology

| Term | Meaning | Claim boundary |
| --- | --- | --- |
| `active runtime manifest` | Approved generated or generator-verified manifest that describes what the current runtime can execute now. | Must not be hand-claimed; may claim only grounded active runtime capability. |
| `active profile manifest` | Future per-profile manifest for a profile with an active descriptor, adapters, tests, and evidence lane. | May exist only after profile runtime support is real and tested. |
| `root aggregate manifest` | Future package-level index of active runtime manifests and package-wide Kernel capability. | Must not upgrade design-only slices into runtime support. |
| `profile navigation index` | Navigation-only package index for profile docs or slices. | Must be labeled navigation-only and non-capability in machine-visible metadata and prose. |
| `design-only profile slice` | Profile-local law, design, source, or planning material without active runtime support. | Must not appear as active runtime capability. |

## Implementation Preconditions

A future implementation PR that changes manifest generation must prove all of
the following before adding a profile to active manifest outputs:

- an active profile descriptor exists and is loaded fail-closed;
- active pack refs and profile refs match the selected active artifact set;
- claimed import, export, view, and query surfaces exist on disk and are wired;
- profile evidence and validation policies are loaded from profile-owned data;
- root or profile harness coverage exists for the claimed surfaces;
- an executed evidence lane exists if the PR claims executed profile evidence;
- design-only profile slices are excluded from active runtime claims;
- no country law is moved into Core, Kernel, Platform, or generated manifests.

## Review Checklist

Before implementation starts, reviewers should confirm:

- the PR states whether it is docs-only, generated-output, or runtime behavior;
- active runtime capability manifests are approved generated or
  generator-verified, never hand-claimed or hand-edited;
- any schema or contract change has explicit approval and migration notes;
- `minimumConformanceLevel` is not strengthened without accepted evidence;
- SI active-pilot behavior remains unchanged unless the PR explicitly targets it;
- the NL GO + GLMC 7 profile slice remains legal-source/profile material only;
- any `profile navigation index` uses machine-visible labels such as
  `artifactKind: "profile_navigation_index"`, `navigationOnly: true`, and
  `capabilityClaim: false`, or an approved equivalent;
- no navigation-only artifact is described as runtime support.

## Stop Conditions

Stop and re-plan if the proposed implementation would:

- add a design-only profile slice to `activeProfileRefs`;
- claim import, export, view, or query support before the surface exists;
- change manifest schema without explicit approval;
- update generated outputs in a planning PR;
- bypass the active-profile loader or profile policy boundary;
- weaken assertion/history-first truth, governed materialization, evidence,
  authority, freshness, correction, review, or refusal rules;
- claim Slovenia production readiness or whole-Netherlands runtime readiness.

## Validation Expectations

For this checklist PR, run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

For any future implementation touching `kernel/manifest.py`, active artifact
sets, generated manifest outputs, or manifest tests, also run:

```sh
.venv/bin/python -m pytest kernel/tests/ -q
```

If a docs-only planning PR accidentally creates
`conformance/evidence/platform_mvp_results_*.json`, remove that new generated
evidence before commit unless the PR intentionally changes executable evidence
grounding.
