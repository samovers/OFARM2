# SI Extraction Practical Closeout

Status: documentation-only closeout decision. This file does not move code,
change runtime behavior, update contracts, update generated manifests,
regenerate evidence, alter tests, or change Core, Kernel, or Platform
semantics.

## Decision

SI extraction is practically complete under the current single-active-SI-runtime
architecture.

This means the ordinary extraction track should stop. Slovenian-specific
material that remains in Core-facing areas is either already profile-local,
root navigation, explicit review-guard text, active SI pilot runtime support, or
future multi-profile architecture work. It is not ordinary cleanup leakage.

This does not certify whole Core country/profile neutrality at L5. It does not
claim multi-profile runtime readiness, Slovenia production readiness, generated
manifest capability expansion, or profile-local executed evidence.

## True Extraction Blockers

None are known for the current single-active-SI-runtime architecture.

The current review-record and consistency-check path already classifies the
remaining country-term surfaces at file/glob level. Future blockers should be
opened only when a concrete new leak appears, such as country law, authority,
evidence source, identifier, fixture, or profile policy being presented as
universal Core law or default runtime behavior.

## Active SI Runtime Support To Keep

| Surface | Why it remains |
| --- | --- |
| `kernel/context.py` | Assembles the current active SI context spine, descriptor-backed profile instances, REGSR/GERK reference families, and per-farm `ContextSnapshot`s. |
| `kernel/config.py` | Holds active SI profile runtime binding and deployment/demo configuration. |
| `kernel/demo.py` | Public compatibility facade for root callers, API examples, and fictional SI-format demo payloads. |
| `kernel/manifest.py` | Generates and verifies the active SI pilot Capability Manifest and ActiveArtifactSet from actual runtime surfaces. |
| `kernel/sufficiency.py` | Owns generic sufficiency mechanics while reading active profile-owned evidence policy metadata. |
| `kernel/validators.py` | Owns generic validator order and mechanics while reading active profile-owned validation policy values and text. |
| `kernel/profile_policy.py` | Generic loader for active profile evidence-review and validation policy content. |
| `kernel/tests/**` | Root conformance, active SI integration coverage, and root bridges that preserve default test discovery. |
| `conformance/**` | Root package checks, platform MVP executed evidence lane, inherited fixtures, and extraction consistency tooling. |
| `kernel/profiles/si_ffs/**` | Already profile-specific SI runtime adapter material. |

These surfaces should not be moved as extraction cleanup. Moving them requires a
future runtime, harness, manifest, or evidence-lane design.

## Future Architecture Work

These are future implementation tracks, not SI extraction leftovers:

| Track | Required preconditions |
| --- | --- |
| Multi-profile active loader/generalization | Explicit active-profile selection design, context-spine equivalence tests, and fail-closed behavior for missing profile content. |
| Multi-profile manifest generation | Active descriptors, generated or generator-verified manifests, tests, and evidence lanes for every claimed active profile. |
| Profile-local executed evidence | Separate suite id, writer shape, output path, honesty note, and no relabeling of root platform MVP evidence. |
| Test harness generalization | Profile-local collection that preserves root command coverage without treating SI bridges as universal discovery. |
| `kernel.demo` facade shrink | Root callers and API examples migrated or proven unaffected, with payload and decision outcomes unchanged. |

## Optional Comment Or Doc Cleanup

These may be cleaned later only when they are tied to a concrete readability or
review need:

- `kernel/README.md`;
- `kernel/adapters.py`;
- `kernel/verification.py`;
- `kernel/policy.py`;
- root navigation wording in `README.md`, `AGENTS.md`, or
  `conformance/CONFORMANCE.md` if future work changes the claim boundary.

Optional comment/doc cleanup must not hide active SI runtime support behind
generic wording.

## Stop Rule

Stop the SI extraction micro-PR loop here.

Do not add more non-blocking checker hardening, review-record grooming, or
classification churn unless it blocks this closeout decision or a concrete
future PR claim. The next SI-related work should be one of:

- a real multi-profile runtime/manifest/evidence design or implementation;
- a concrete bug or new country/profile leak;
- a targeted product/runtime task that explicitly accepts the active SI pilot
  boundary.

## Must Not Be Done Next

- Do not move `kernel/context.py`, `kernel/demo.py`, `kernel/manifest.py`,
  root conformance, or root tests merely as extraction cleanup.
- Do not create a universal country abstraction layer.
- Do not regenerate manifests or active artifact sets.
- Do not edit contracts.
- Do not move, rename, delete, or relabel `conformance/evidence/**`.
- Do not change runtime behavior, adapter behavior, tests, or evidence writers
  in a closeout PR.
- Do not claim Slovenia production readiness, multi-profile runtime readiness,
  L5 Core country/profile-neutral certification, generated capability
  expansion, or profile-local executed evidence.
- Do not weaken assertion/history-first truth, governed materialization,
  authority, evidence, freshness, review, correction, refusal, or promotion
  rules.

## Validation For Closeout PRs

Run:

```sh
python3 conformance/ofarm_profile_extraction_consistency_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

Run the informational country-term audit:

```sh
rg -n "KMG-MID|GERK|REGSR|FFSNaprave|Slovenia|Slovenian|\bSI\b|Dutch GO|GLMC 7|Gecombineerde Opgave" CORE.md PLATFORM.md KERNEL.md contracts kernel views conformance README.md AGENTS.md profile_si_ffs/extraction_inventory/si_extraction_practical_closeout.md || true
```

Audit hits are expected. They are acceptable only as profile-local material,
root navigation, review guards, active SI runtime support, future-work
boundaries, or this closeout decision text.
