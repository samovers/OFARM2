# Core Country-Term Audit Initial Review

Status: documentation-only initial review snapshot. This file does not implement
a machine guard, certify Core, change runtime behavior, alter tests, update
contracts, update generated outputs, or change Core, Kernel, or Platform
semantics.

This review follows `core_country_term_audit_allowlist_plan.md`. It records the
current file-level shape of the seed country-term scan so future work can move
from an informational scan toward a reviewed allowlist.

This is not the L5 machine guard. It is not a line-level allowlist. It is a
coarse review input.

## Scan Command

```sh
rg -n "KMG-MID|GERK|REGSR|FFSNaprave|Slovenia|Slovenian|\bSI\b|Dutch GO|GLMC 7|Gecombineerde Opgave" CORE.md PLATFORM.md KERNEL.md contracts kernel views conformance README.md AGENTS.md
```

## High-Level Result

| Surface | Initial result | Review category |
| --- | --- | --- |
| `CORE.md` | No seed-term hits in this scan. | `APPARENTLY_NEUTRAL_PENDING_AUDIT` |
| `KERNEL.md` | No seed-term hits in this scan. | `APPARENTLY_NEUTRAL_PENDING_AUDIT` |
| Root `README.md` | Profile navigation, profile slice pointers, and package cut-date text. | `PROFILE_LOCAL_POINTER` plus `REVIEW_GUARD_OR_NON_CLAIM` |
| `AGENTS.md` | Repository description, privacy guard examples, and Netherlands review guard text. | `REVIEW_GUARD_OR_NON_CLAIM` |
| `PLATFORM.md` | Current active SI pilot flow wording. | `ACTIVE_RUNTIME_SI_SUPPORT` |
| `views/VIEWS.md` | Pointer to profile-local SI view artifacts. | `PROFILE_LOCAL_POINTER` |
| `conformance/CONFORMANCE.md` | Conformance lane labels, profile design-case pointers, and manual audit command. | `PROFILE_LOCAL_POINTER` plus `REVIEW_GUARD_OR_NON_CLAIM` |
| `contracts/core/*IdentityPayload*` | No seed-term hits after the contract-comment neutralization recorded in `core_contract_comment_review_plan.md`. | `APPARENTLY_NEUTRAL_PENDING_AUDIT` for the current scan |
| `kernel/profiles/si_ffs/**` | SI profile adapter and binding content. | `PROFILE_LOCAL_CONTENT` |
| `kernel/context.py`, `kernel/config.py`, `kernel/manifest.py` | Active SI runtime spine, shipped snapshot refs, and generated active-pilot artifact grounding. | `ACTIVE_RUNTIME_SI_SUPPORT` |
| `kernel/demo.py` | Public compatibility facade for fictional SI-shaped demo payloads. | `ACTIVE_RUNTIME_SI_SUPPORT` pending future harness work |
| `kernel/sufficiency.py`, `kernel/validators.py`, `kernel/profile_policy.py` | Generic mechanics that read active profile policy or still document active SI policy context. | `ACTIVE_RUNTIME_SI_SUPPORT` |
| `kernel/adapters.py`, `kernel/verification.py`, `kernel/policy.py` | Generic mechanics with SI boundary comments, negative examples, or review guards. | `REVIEW_GUARD_OR_NON_CLAIM` |
| `kernel/tests/test_m2_si_*`, `kernel/tests/test_profile_si_demo_*` | Root collection bridges or active SI profile engineering tests. | `PROFILE_LOCAL_POINTER` plus `ACTIVE_RUNTIME_SI_SUPPORT` |
| `kernel/tests/test_profile_runtime_loader.py`, `kernel/tests/test_m2_manifest.py`, `kernel/tests/test_conformance.py` | Root tests pinning active profile loader, manifest grounding, and active-pilot conformance behavior. | `ACTIVE_RUNTIME_SI_SUPPORT` |
| Other generic root tests with SI terms | Negative examples, fixture-boundary comments, or no-SI assertions. | `REVIEW_GUARD_OR_NON_CLAIM` |

## Initial Findings

- The scan did not find seed terms in `CORE.md` or `KERNEL.md`.
- The former Core contract comment hits have been neutralized and now remain
  only in the profile-local review record.
- The remaining hits are expected for the current repository state and are
  mostly root navigation, review guards, active SI pilot runtime support,
  profile-local SI adapter content, or profile engineering test bridges.
- No hit in this snapshot should be treated as proof of Core certification.
- No hit in this snapshot should be promoted into a runtime capability claim.
- The contract-comment review is no longer a current Core contract seed-term
  blocker, but the full audit remains below L5 until every remaining hit is
  reviewed and an enforcing guard exists.

## Candidate Future Actions

1. Convert this file-level snapshot into a line-level review record only after
   the review record shape is approved.
2. Keep active SI runtime support visible until profile-loader, harness, and
   generated-output designs make a move safe.
3. Add an enforcing check only after every seed-term hit is removed,
   profile-local, or assigned to an approved category.

## Stop Conditions

Stop and re-plan if a future PR would:

- make this snapshot the enforcing machine guard;
- treat `APPARENTLY_NEUTRAL_PENDING_AUDIT` as certification;
- hide active SI runtime support behind generic wording;
- update contracts, generated outputs, runtime behavior, or evidence files;
- add Slovenia production readiness, Netherlands runtime readiness,
  multi-profile runtime readiness, or generated capability expansion claims.

## Validation For This Review Snapshot

Run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

Run the informational audit:

```sh
rg -n "KMG-MID|GERK|REGSR|FFSNaprave|Slovenia|Slovenian|\bSI\b|Dutch GO|GLMC 7|Gecombineerde Opgave" CORE.md PLATFORM.md KERNEL.md contracts kernel views conformance README.md AGENTS.md profile_si_ffs/extraction_inventory/core_country_term_audit_initial_review.md
```

Expected hits are review inputs. This review snapshot should not make the audit
enforcing.
