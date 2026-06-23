# SI Core Leakage Inventory

Status: initial PR A inventory snapshot retained for traceability. Some rows
describe surfaces that later PRs moved, neutralized, or reclassified; current
remaining work is tracked by `si_migration_map.md`,
`manual_review_backlog_plan.md`, and the D-lane status records in this
directory.

This inventory records Slovenian-specific terms, assumptions, examples, and
fixtures that were visible in Core-facing areas during the initial audit. It is
not a migration itself. No row authorizes moving a file, changing runtime
behavior, or changing contract semantics without a later PR.

The initial audit command was:

```sh
rg -n "KMG-MID|GERK|KMG|Slovenia|Slovenian|\bSI\b|Sloven" CORE.md PLATFORM.md KERNEL.md contracts kernel views conformance README.md AGENTS.md
```

## Findings

| ID | Current surface | Observed material | Profile-boundary concern | Initial disposition |
| --- | --- | --- | --- | --- |
| SI-CORE-001 | `CORE.md` farm identity table | `KMG-MID` described as a Slovenia profile binding | Core identity language should describe profile-specific holding identifiers generically. | `REWORD_CORE_GENERICALLY` |
| SI-CORE-002 | `CORE.md` field identity table | `GERK` described as a Slovenia profile binding | Core field identity language should describe profile-specific parcel identifiers generically. | `REWORD_CORE_GENERICALLY` |
| SI-CORE-003 | `CORE.md` operation-chain review text | Review language points to the SI self-review policy | Core operation-chain review should point to the active profile review policy. | `REWORD_CORE_GENERICALLY` |
| SI-CORE-004 | `CORE.md` code-binding discipline | Example names UVHVVR, the Slovenian plant-protection register, and SI register identifiers | The code-binding concept is generic, but the concrete authority and register example belongs in the SI profile. | `KEEP_IN_CORE_AS_GENERIC_WITH_EXAMPLE_REMOVED` |
| SI-PLATFORM-001 | `PLATFORM.md` overview | Platform wording says adapters follow the SI profile cadence | Platform can describe active-profile cadence without embedding one country profile as the general case. | `REWORD_CORE_GENERICALLY` |
| SI-PLATFORM-002 | `PLATFORM.md` gate and activation sections | Static SI activation and SI self-review wording | Some wording is pilot-specific and may be intentional; reword only where it claims generic Platform behavior. | `AMBIGUOUS_MANUAL_REVIEW` |
| SI-ROOT-001 | `README.md` | Repository described as a Slovenia plant-protection pilot package | Root readme is allowed to describe the current implementation package, but later neutralization must avoid changing current claim limits. | `DO_NOT_TOUCH` |
| SI-ROOT-002 | `AGENTS.md` | Privacy examples include KMG-MID and GERK-PID; review guard mentions the SI profile | Agent instructions are operational guardrails and are not part of Core semantics. Any rewording should preserve privacy and scope guards. | `AMBIGUOUS_MANUAL_REVIEW` |
| SI-VIEWS-001 | `views/OFARM_QuerySpecification_si_ffs_*` and related view artifacts | SI profile query specifications and query plans were stored under top-level `views/` during the initial audit. | Authored SI views are profile material; later docs preserve only the legacy pointer needed for old references. | `MOVE_TO_SI_PROFILE` |
| SI-KERNEL-001 | `kernel/adapters.py` comments and adapter examples | Comments mention REGSR, GERK, FFSNaprave, and SI adapter reuse | Mostly explanatory examples around generic adapter discipline; future rewording should not change adapter behavior. | `KEEP_IN_CORE_AS_GENERIC_WITH_EXAMPLE_REMOVED` |
| SI-KERNEL-002 | `kernel/profile_policy.py` docstrings | Loader language references the SI evidence floor | Loader mechanism appears profile-generic; docstrings can likely say active profile evidence floor. | `REWORD_CORE_GENERICALLY` |
| SI-KERNEL-003 | `kernel/sufficiency.py` docstrings, rationale strings, and tests | Evidence sufficiency messages name SI evidence floors and Slovenian source expectations | User-visible or test-asserted strings may encode active pilot behavior; this needs test-aware review. | `AMBIGUOUS_MANUAL_REVIEW` |
| SI-KERNEL-004 | `kernel/validators.py` messages and comments | Validation paths mention SI profile unresolved bindings, crop binding, SI record field requirements, and SI quantity policy | Some behavior may be active-profile logic and some may be SI-only policy in Kernel-facing code. Needs design review before extraction. | `AMBIGUOUS_MANUAL_REVIEW` |
| SI-KERNEL-005 | `kernel/policy.py` comments | Comments say KMG-MID/GERK are not core, mention SI geometry and SI evidence floor | The comments mostly protect the model/runtime split, but examples can be made profile-neutral later. | `KEEP_IN_CORE_AS_GENERIC_WITH_EXAMPLE_REMOVED` |
| SI-KERNEL-006 | `kernel/demo.py` | Fictional SI identifiers, SI schemes, KMG-MID, GERK-PID, SI jurisdiction, and SI source examples | Demo payloads may be tests or examples for the active SI pilot; relocation needs test and API review. | `AMBIGUOUS_MANUAL_REVIEW` |
| SI-KERNEL-007 | `kernel/context.py` and `kernel/README.md` | SI context spine, GERK snapshot prefix, SI bootstrap, and GERK importer wording | This may reflect the current active runtime being SI-specific. Extraction likely needs profile-loader design, not a docs-only move. | `AMBIGUOUS_MANUAL_REVIEW` |
| SI-KERNEL-008 | `kernel/profiles/si_ffs/**` | SI adapters and profile runtime helpers already under a profile-named kernel package | These are already segregated as SI profile adapter code inside the current runtime structure. | `DO_NOT_TOUCH` |
| SI-KERNEL-009 | `kernel/manifest.py` | Comments and manifest metadata mention SI import surfaces and KMG-MID vocabulary | Manifest generation is protected in this PR and likely needs separate governance before changes. | `AMBIGUOUS_MANUAL_REVIEW` |
| SI-TEST-001 | `kernel/tests/**` | Tests exercise SI bindings, SI evidence floors, GERK, REGSR, FFSNaprave, and KMG-MID examples | Tests protect current behavior. Moving them requires a profile test harness decision. | `AMBIGUOUS_MANUAL_REVIEW` |
| SI-CONFORMANCE-001 | `conformance/**` | Conformance docs and checks reference the SI evidence floor and current pilot evidence | Some conformance material is package-wide while some is active SI pilot evidence. Split only after harness review. | `AMBIGUOUS_MANUAL_REVIEW` |
| SI-CONTRACT-001 | `contracts/core/OFARM_FarmIdentityPayload_schema_v0_1.json` | Contract comment cites KMG-MID as an example of profile-governed holding identifiers | The contract concept is generic. Comment rewording may be possible but contracts are protected from this PR. | `KEEP_IN_CORE_AS_GENERIC_WITH_EXAMPLE_REMOVED` |
| SI-CONTRACT-002 | `contracts/core/OFARM_FieldIdentityPayload_schema_v0_1.json` | Contract comment cites GERK as an example of profile-governed parcel identifiers | The contract concept is generic. Comment rewording may be possible but contracts are protected from this PR. | `KEEP_IN_CORE_AS_GENERIC_WITH_EXAMPLE_REMOVED` |

## Category Coverage

- KMG-MID and KMG findings: `SI-CORE-001`, `SI-KERNEL-006`, `SI-CONTRACT-001`, `SI-TEST-001`.
- GERK findings: `SI-CORE-002`, `SI-KERNEL-005`, `SI-KERNEL-006`, `SI-KERNEL-007`, `SI-CONTRACT-002`, `SI-TEST-001`.
- Slovenia and SI terminology findings: `SI-CORE-001` through `SI-ROOT-002`, plus kernel and test rows.
- SI authority, evidence, and currentness assumptions: `SI-CORE-004`, `SI-KERNEL-002`, `SI-KERNEL-003`, `SI-KERNEL-004`, `SI-CONFORMANCE-001`.
- SI fixtures and examples in Core-facing areas: `SI-VIEWS-001`, `SI-KERNEL-006`, `SI-TEST-001`.
