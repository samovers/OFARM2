# M2 kickoff prompt (paste into a fresh thread)

> Copy everything below the line into a new thread to start M2 implementation.

---

You are implementing **Milestone M2 — Core on Kernel** of the OFARM2 implementation package. M1 (the Kernel) is complete and merged on `main`. Your job is to build Core on top of it, **slice by slice, exactly per the plan already written in the repo** — not to redesign anything.

**Repo:** `/Users/einstein/Documents/Codex/OFARM2-implementation/OFARM2`

## Read first (in this order), before writing any code
1. `AGENTS.md` — binding working rules. **Privacy rule 1 is absolute.**
2. `DECISIONS.md` — settled decisions; do not re-litigate them.
3. `M2_BRIEF.md` — the work order. Its **Generic mechanism vs the SI package**, **Adapter discipline**, **Build order**, and **Ticket order** sections are binding.
4. `M2_TICKETS.md` — the fully specified tickets (Phase 1 generic G1–G7; Phase 2 package P1–P6) with per-ticket file boundaries and the build sequence.
5. `KERNEL.md` → `CORE.md` → `PLATFORM.md` — the law you're implementing on.
6. `kernel/README.md` — how to run the store, the test suites, and the self-check.

## Prime directives (non-negotiable)
- **Claim limits:** record-keeping completeness only — never current-compliance, certification, or production readiness. Do not write prose or capability claims that say more.
- **Privacy (D14):** no personal data anywhere; fictional, format-true values only. Real KMG-MID / GERK / parcel / document values never enter the repo.
- **Law freeze:** implementation findings go to `ERRATA.md`. `contracts/**` and `reference/**` are extraction-only and frozen — never edit them. Never invent a `RuntimeProblem` reason code; use the registry RFC, and a missing code is an ERRATA entry.
- **Generic before package + mechanism-boundary stop rule:** build the generic Core/Platform mechanism (Phase 1, G-tickets) before the SI-package content (Phase 2, P-tickets). No ticket may implement a Slovenia-specific register, cadence, identifier, or evidence rule as Core/Platform law. If an SI specific cannot be expressed as `profile_si_ffs` package/profile content loaded through a generic mechanism, **stop and fix the mechanism boundary first** — do not code around it.
- **No silent truth:** honor the seven Kernel rules — append-only, default deny, capture ≠ commitment, no shortcut to truth, derived state with receipts, distinct times, refuse over pretending.
- **Honest reporting:** failing tests are reported as failing; a design fixture is never presented as executed evidence.

## Workflow — one ticket = one branch = one PR
1. **Confirm the M1 baseline is green before touching anything.** Bring up the Postgres scratch cluster (`kernel/README.md` "Run it"), then run `.venv/bin/python -m pytest kernel/tests/ -q` and `python3 conformance/ofarm_pkg_contract_check.py`. Both must pass. If either fails, stop and report — do not build on a red baseline.
2. Take the next ticket in the build sequence below. Read its **Read first** list; respect its **Files NOT to touch** exactly.
3. Implement only that ticket. Add its tests in a new engineering module `kernel/tests/test_m2_<area>.py`, excluded from the named conformance evidence by nodeid (follow the `test_review_fixes.py` / `test_stages.py` pattern).
4. Re-run the suite + the package self-check. Both green; the M1 suite must be unregressed.
5. Open a narrow PR named for the ticket. Do not start the next ticket until this one is green/merged.

## Build sequence (hard-gated — each arrow requires the upstream ticket green)
`G1` → `G2` → `G3` → `P1, P2, P3` → `P4` → `G4` → `G5-1 → G5-2 → G5-3 → G5-4` → `P5` → `G6, G7` → `P6`

G5-1 and G5-3 are **spec tickets**: write and get the REJECT and CONTEST/dispute semantics agreed (as a doc + decision) before implementing G5-2 and G5-4.

## Start now
Begin with **G1 — Governed structure-identity commit path** (full spec in `M2_TICKETS.md`):
1. First verify the M1 baseline is green (step 1 above).
2. Then implement G1: commit Farm / Field / CropCycle / Equipment / AppliedResource identities through the full gate chain as `STRUCTURE_ASSERTION` commits carrying the typed identity payloads (`contracts/core/OFARM_*IdentityPayload_schema_v0_1.json`), producing `ACCEPTED_STRUCTURAL_STATE` consequences, with the identity registry materializing the **current payload** per identity. Replace the directly-bootstrapped identities in `kernel/demo.py` with committed structure assertions.
3. Keep it generic — no SI scheme logic (KMG-MID/GERK bindings are P4). Do not touch `kernel/authority.py` or the `STRUCTURE_ASSERTION` rows in `kernel/policy.py` (they already wire end-to-end).
4. Add `kernel/tests/test_m2_identities.py` per the ticket's Required tests; run the suite + self-check; open the G1 PR.

Work through one ticket at a time; report progress per ticket and stop at any mechanism-boundary question rather than guessing.

**Environment note:** if your environment cannot write or delete inside the repo's `.git` (some sandboxes block unlink), do the code and tests normally but hand the final `git add` / `commit` / `push` commands back to the user to run on their machine.
