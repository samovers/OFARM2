# SI Migration Map

This map translates the inventory findings into follow-up decisions. It is intentionally conservative: ambiguous runtime, test, contract, and manifest surfaces stay out of move-ready buckets.

## Classification Map

| Inventory ID | Current path or area | Classification | Candidate destination or action | Follow-up lane |
| --- | --- | --- | --- | --- |
| SI-CORE-001 | `CORE.md` | `REWORD_CORE_GENERICALLY` | Replace KMG-MID example with `profile-specific holding identifier`; keep SI detail in `profile_si_ffs/`. | PR C |
| SI-CORE-002 | `CORE.md` | `REWORD_CORE_GENERICALLY` | Replace GERK example with `profile-specific parcel identifier`; keep SI detail in `profile_si_ffs/`. | PR C |
| SI-CORE-003 | `CORE.md` | `REWORD_CORE_GENERICALLY` | Replace SI self-review policy wording with active-profile review policy wording. | PR C |
| SI-CORE-004 | `CORE.md` | `KEEP_IN_CORE_AS_GENERIC_WITH_EXAMPLE_REMOVED` | Keep code-binding discipline; move or remove concrete Slovenian register example. | PR C |
| SI-PLATFORM-001 | `PLATFORM.md` | `REWORD_CORE_GENERICALLY` | Say adapters follow active-profile cadence. | PR C |
| SI-PLATFORM-002 | `PLATFORM.md` | `AMBIGUOUS_MANUAL_REVIEW` | Review pilot-specific activation wording before any neutral rewrite. | Manual review |
| SI-ROOT-001 | `README.md` | `DO_NOT_TOUCH` | Preserve current implementation-package claim limits unless a broader repo repositioning is approved. | None |
| SI-ROOT-002 | `AGENTS.md` | `AMBIGUOUS_MANUAL_REVIEW` | Preserve privacy and review guards; only reword if a future instruction update asks for it. | Manual review |
| SI-VIEWS-001 | `views/OFARM_QuerySpecification_si_ffs_*` | `MOVE_TO_SI_PROFILE` | Candidate destination: `profile_si_ffs/views/` with any doc references updated in the same PR. | PR B |
| SI-KERNEL-001 | `kernel/adapters.py` | `KEEP_IN_CORE_AS_GENERIC_WITH_EXAMPLE_REMOVED` | Keep generic adapter discipline; remove or move Slovenian examples if comments are touched later. | PR C |
| SI-KERNEL-002 | `kernel/profile_policy.py` | `REWORD_CORE_GENERICALLY` | Use active-profile evidence-floor wording. | PR C |
| SI-KERNEL-003 | `kernel/sufficiency.py` | `AMBIGUOUS_MANUAL_REVIEW` | Do not move until tests and user-visible rationale strings are reviewed. | Manual review |
| SI-KERNEL-004 | `kernel/validators.py` | `AMBIGUOUS_MANUAL_REVIEW` | Decide whether SI policy belongs in active profile adapters or generic validators. | Manual review |
| SI-KERNEL-005 | `kernel/policy.py` | `KEEP_IN_CORE_AS_GENERIC_WITH_EXAMPLE_REMOVED` | Preserve invariant comments; consider neutral examples only. | PR C |
| SI-KERNEL-006 | `kernel/demo.py` | `AMBIGUOUS_MANUAL_REVIEW` | Candidate profile example destination exists in principle, but runtime and tests may depend on this demo. | Manual review |
| SI-KERNEL-007 | `kernel/context.py`, `kernel/README.md` | `AMBIGUOUS_MANUAL_REVIEW` | Needs active-profile bootstrapping design before extraction. | Manual review |
| SI-KERNEL-008 | `kernel/profiles/si_ffs/**` | `DO_NOT_TOUCH` | Already profile-specific in the current runtime layout. | None |
| SI-KERNEL-009 | `kernel/manifest.py` | `AMBIGUOUS_MANUAL_REVIEW` | Protected generated-manifest surface; no change without separate governance. | Manual review |
| SI-TEST-001 | `kernel/tests/**` | `AMBIGUOUS_MANUAL_REVIEW` | Split only after a profile test-harness plan exists. | Manual review |
| SI-CONFORMANCE-001 | `conformance/**` | `AMBIGUOUS_MANUAL_REVIEW` | Separate package-wide conformance from active SI pilot evidence only after harness review. | Manual review |
| SI-CONTRACT-001 | `contracts/core/OFARM_FarmIdentityPayload_schema_v0_1.json` | `KEEP_IN_CORE_AS_GENERIC_WITH_EXAMPLE_REMOVED` | Optional future comment neutralization; contracts remain untouched here. | PR C or manual review |
| SI-CONTRACT-002 | `contracts/core/OFARM_FieldIdentityPayload_schema_v0_1.json` | `KEEP_IN_CORE_AS_GENERIC_WITH_EXAMPLE_REMOVED` | Optional future comment neutralization; contracts remain untouched here. | PR C or manual review |

## Move-Ready Boundary

Only `MOVE_TO_SI_PROFILE` items are candidates for PR B. Even there, PR B must update references and tests only as needed to preserve behavior. Anything marked `AMBIGUOUS_MANUAL_REVIEW` is not move-ready.

## Protected Surfaces

This map does not authorize changes to contracts, generated manifests, `kernel/manifest.py` outputs, active runtime configuration, or the current SI runtime adapter behavior.

