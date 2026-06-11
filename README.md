# OFARM2 Implementation Package (pre-implementation baseline)

**What this is:** the self-contained working surface for implementing OFARM2 — a Kernel/Core/Platform implementation and conformance packaging profile plus the Slovenia plant-protection record-keeping pilot definition. Designed to be lifted into its own repository unchanged.

**For agents and new contributors:** start with `AGENTS.md` (binding working rules), `DECISIONS.md` (settled decisions), and `M1_BRIEF.md` (the current work order: build the Kernel). M0 — verification and grounding — is CLOSED as of 2026-06-12; see `profile_si_ffs/M0_DESK_RESEARCH.md` for the ledger.

**What this is not:** OFARM law. This package is a derived implementation/conformance artifact under `PROJECT_AUTHORITY.md` (carried verbatim in `reference/law/`). It creates no new authority, overrides nothing, and promotes nothing. New schemas here are **candidate artifacts** (Constitution RC2.1 §6.16) pending post-pilot governance.

## Claim limits (distilled from the canonical hostile reviews and readiness memos)

No production readiness of any kind is claimed: not software-delivery, model-deployment, certification, legal/security/compliance advice, external-standard readiness, live-registry integration, autonomous anything, or current/default schema promotion. The pilot claims **record-keeping completeness** only — explicitly **not** current-compliance against the authorisation register (see `PILOT_SI.md`).

## Read order

1. `KERNEL.md` — the truth machine: 12 record families, 7 rules, the reachability invariant, conformance definition
2. `CORE.md` — crop-farming semantics on the Kernel; the operation chain; code-binding discipline
3. `PLATFORM.md` — the pilot runtime: components, gate pipeline, storage posture, invalidation, unsupported surfaces
4. `PILOT_SI.md` — Slovenia pilot: claim scope, review policy, milestones M0–M4, success/kill criteria
5. `CAPTURE_MAPPING.md` — the five things a farmer touches; everything else auto-populated
6. `profile_si_ffs/PROFILE.md` — scheme roles, currentness posture, evidence/review policy, shipped + deferred instances
7. `views/VIEWS.md` — the two governed outputs, specified; JSON artifacts due M1
8. `conformance/CONFORMANCE.md` — package self-check + the 15-test platform MVP suite

## Layout

```
KERNEL.md CORE.md PLATFORM.md PILOT_SI.md CAPTURE_MAPPING.md ERRATA.md
contracts/   kernel/ (23 extracted + 3 candidate)  core/ (11 extracted + 5 candidate)
             platform/ (10 extracted)              CONTRACTS_MANIFEST.json (digests + provenance)
profile_si_ffs/   PROFILE.md + 3 validated example instances (activation set, artifact set, context snapshot)
views/            VIEWS.md (normative specs; QuerySpec/QueryPlanIR JSON due M1)
conformance/      ofarm_pkg_contract_check.py + CONFORMANCE.md + fixtures/gate_sequencing/ (9 inherited)
reference/        REFERENCE_MANIFEST.json + law/ (4) + rfcs/ (14) + research/ (1) + companions/
```

Honest count: ~52 contracts and instances, ~20 reference files, ~95 files total — small next to the canonical repository's ~4,800, not "tiny."

## Discipline

- **Law freeze (this repository):** findings go to `ERRATA.md` only — never into reference copies or as new law. The canonical repository evolves in parallel under steward governance; its changes are absorbed here by extraction with provenance (see `DECISIONS.md` D15).
- **Reference lane:** verbatim, read-only, non-normative within the package, budget ≤ 30 files; additions require a manifest entry with a reason.
- **Verification:** `python3 conformance/ofarm_pkg_contract_check.py` must pass before any commit touching the package.
- **Provenance:** every extracted file's source path, repo commit, and sha256 live in the manifests. Within the parent repository the reference copies are redundant by design — the package is built to travel.
