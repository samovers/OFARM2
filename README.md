# OFARM2 Implementation Package

**What this is:** the self-contained working surface for implementing OFARM2 — a Kernel/Core/Platform implementation and conformance packaging profile plus the Slovenia plant-protection record-keeping pilot definition. Designed to be lifted into its own repository unchanged.

**For agents and new contributors:** start with `AGENTS.md` (binding
working rules), `DECISIONS.md` (settled decisions), and `kernel/README.md`
(the current production-versus-legacy runtime map). `M1_BRIEF.md` is the
historical semantic-prototype brief; `M2_BRIEF.md` and `M3_BRIEF.md` describe
the later production and product work. M0 — verification and grounding — is
CLOSED as of 2026-06-12; see `profile_si_ffs/M0_DESK_RESEARCH.md` for the
ledger.

**What this is not:** OFARM law. This package is a derived implementation/conformance artifact under `PROJECT_AUTHORITY.md` (carried verbatim in `reference/law/`). It creates no new authority, overrides nothing, and promotes nothing. New schemas here are **candidate artifacts** (Constitution RC2.1 §6.16) pending post-pilot governance.

## Claim limits (distilled from the canonical hostile reviews and readiness memos)

The repository now contains a production trust and storage foundation, but no
governed semantic production surface is open. Protected production endpoints
remain blocked. No whole-system production readiness, certification,
legal/security/compliance advice, external-standard readiness, live-registry
integration, autonomous behavior, or current/default schema promotion is
claimed. The pilot claims **record-keeping completeness** only — explicitly
**not** current-compliance against the authorisation register (see
`PILOT_SI.md`).

`profile_nl_go_glmc7_2026/` is a narrow legal-source/conformance-ready profile slice for 2026 Netherlands GO + GLMC 7 under its own release posture. That posture is limited to the profile/source standard and does not change the repository's runtime, platform, external-standard, or whole-country claim limits.

## Read order

1. `kernel/README.md` — current production and legacy runtime boundaries
2. `KERNEL.md` — the truth machine: record families, rules, reachability, and conformance
3. `CORE.md` — crop-farming semantics and code-binding discipline
4. `PLATFORM.md` — the pilot runtime and unsupported surfaces
5. `M2_BRIEF.md` / `M3_BRIEF.md` — production foundation and product sequencing
6. `PILOT_SI.md` — Slovenia pilot claims, review policy, and milestones
7. `CAPTURE_MAPPING.md` — the five things a farmer touches
8. `profile_si_ffs/PROFILE.md` — SI roles, evidence, and review policy
9. `conformance/REVIEW_BASELINE.md` — the pinned complete Kernel verification path

## Layout

```
KERNEL.md CORE.md PLATFORM.md PILOT_SI.md CAPTURE_MAPPING.md ERRATA.md
contracts/        extracted and candidate contracts with provenance
profile_si_ffs/   PROFILE.md + 6 descriptor-bootstrapped validated instances (activation set,
                  artifact set, context snapshot, code-binding profile, 2 reference snapshots)
                  + generated/verified Capability Manifest + UNSUPPORTED_SURFACES.md
                  + views/ (SI view specs/artifacts) + extraction_inventory/ (documentation-only inventory)
profile_nl_go_glmc7_2026/  narrow Netherlands GO + GLMC 7 2026 profile/source slice
views/            VIEWS.md pointer to profile-local SI view material
kernel/           production trust/storage foundation plus the quarantined legacy M1 prototype;
                  see kernel/README.md before changing runtime composition
deployment/       external PostgreSQL provisioning, immutable tenant/audit migrations, and read-only readiness
conformance/      package checks, pinned complete-suite runner, fixtures, and evidence
reference/        read-only law, RFC, research, and companion sources
```

## Discipline

- **Currentness note (package cut date):** `2026-06-12` is the **Slovenia-local** package cut date. The source packet was generated `2026-06-11T22:41:01Z` UTC (= 00:41 CEST, 2026-06-12) — see `profile_si_ffs/source_packet_extracts/source_manifest.json`. M0-closure and handoff dates throughout the package use the Slovenia-local date; the UTC timestamp is preserved in the source manifest. The package is not future-dated.
- **Law freeze (this repository):** findings go to `ERRATA.md` only — never into reference copies or as new law. The canonical repository evolves in parallel under steward governance; its changes are absorbed here by extraction with provenance (see `DECISIONS.md` D15).
- **Reference lane:** verbatim, read-only, non-normative within the package, budget ≤ 30 files; additions require a manifest entry with a reason.
- **Verification:** `python3 conformance/ofarm_pkg_contract_check.py` must pass before any commit touching the package.
- **Provenance:** every extracted file's source path, repo commit, and sha256 live in the manifests. Within the parent repository the reference copies are redundant by design — the package is built to travel.
