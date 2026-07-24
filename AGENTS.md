# Agents

This is the **OFARM2 implementation repository**: the working surface for building the OFARM2 Kernel, Core, and Platform, and the Slovenia plant-protection record-keeping pilot. It was extracted from the canonical OFARM repository and is designed to stand alone.

## What this repository is, and is not

- It is an **implementation and conformance packaging profile** plus pilot material. It is **not OFARM law** and creates no authority.
- Canonical authority lives in the **OFARM repository** (`samovers/OFARM`); verbatim snapshots of the law this package implements are in `reference/` (read-only, non-normative within this package, digest-pinned in `reference/REFERENCE_MANIFEST.json`).
- New schemas here are **candidate artifacts** (Constitution RC2.1 §6.16). Nothing in this repository promotes contracts or changes currentness.
- `contracts/drafts_reference/` carries DRAFT_NON_DEFAULT contracts from canonical main for implementation reference only — implementing their shapes never promotes them.

## Read path

1. `README.md` — package map and claim limits
2. `DECISIONS.md` — settled decisions; do not re-litigate them
3. `KERNEL.md` → `CORE.md` → `PLATFORM.md` — what to build
4. `M1_BRIEF.md` — the current work order
5. `PILOT_SI.md` + `profile_si_ffs/` — the pilot's verified ground
6. `conformance/CONFORMANCE.md` — the definition of done

## Working rules (binding for agents)

1. **Privacy is absolute.** Never commit personal data: no names, birth dates, addresses, phones, real KMG-MID, GERK-PID, parcel names, real document dates/areas, or document filenames containing identifiers. Real farm documents are evidence held farm-side only. Examples use fictional, format-true values. Reports about real data must be paste-safe (counts, masked IDs, booleans). When in doubt, leave it out and ask.
2. **The law freeze holds for this repository.** Implementation findings go to `ERRATA.md` — never into `reference/` copies, never as new law. (The canonical repository evolves in parallel under the steward's governance; absorb its changes by extraction with provenance, never by editing.)
3. **Run `python3 conformance/ofarm_pkg_contract_check.py` before every commit.** It must PASS.
4. **Provenance discipline:** every file extracted from the canonical repository gets a manifest entry (source path, commit, sha256). Extracted files are byte-identical — never edited.
5. **No silent truth.** Honor the seven Kernel rules in `KERNEL.md` in everything you build: append-only, default deny, capture ≠ commitment, no shortcut to truth, derived current state with receipts, distinct times, refusal over pretending.
6. **Claim limits:** this project claims record-keeping completeness for the pilot — never current-compliance, certification, production readiness, or legal advice. Do not generate text that claims more.
7. **Country/profile separation:** Country-specific identifiers, law, evidence sources, currentness rules, authority names, and conformance fixtures belong in profile/package layers. Core-facing material must use profile-neutral terms unless explicitly presenting a non-normative example. Non-normative examples must not become executable Core law.
8. **Honest reporting:** failing tests are reported as failing; design fixtures are never presented as executed evidence; skipped steps are named.
9. **Commit style:** imperative subject, body explains what and why, reference the M1 brief task where applicable.

## Default change workflow

Use this workflow for ordinary tasks. Routine work does not require the full
design contract or an approval stop.

OFARM2 is pre-deployment development work. Prefer the best coherent design now
over preserving a temporary implementation. Do not defer a justified redesign,
rewrite, or refactor solely to avoid changing existing code; change is
comparatively cheap before production. It is not free: preserve accepted
contracts, evidence, explicit invariants, and stated boundaries, and verify
changes in proportion to their risk.

Before editing, state:

- the one problem being solved and the primary boundary being changed;
- falsifiable acceptance criteria or invariants;
- non-goals and adjacent systems that will not change;
- why the proposed change is the smallest coherent solution;
- the capability delivered, demonstrated risk reduced, or architectural
  decision validated;
- a provisional-design record only when the design is intentionally temporary,
  covering why it is acceptable before deployment, evidence that would require
  redesign, and the likely upgrade path; otherwise state `Not provisional`;
- the focused verification needed for the stated boundary.

Keep implementation, tests, documentation, and necessary mechanical
integration inside that boundary. If another boundary must change, stop before
editing it and propose a separate prerequisite, Follow-up, or stacked pull
request. Prefer deletion, direct code paths, explicit boundary contracts,
immutable values, and small modules over speculative abstractions,
compatibility shims, and duplicate validation.

Classify every review finding as exactly one of:

- **Blocker:** a demonstrated in-scope correctness, security, data-integrity,
  contractual, or production-safety failure. Name the violated invariant and
  the smallest acceptable fix.
- **Follow-up:** valid work outside the pull request boundary. Record it as a
  separate issue or future pull request; do not expand the current change.
- **Preference:** optional style or alternative-design advice. It never delays
  merging.

Only demonstrated Blockers delay a merge. Once the acceptance criteria pass
and no Blocker remains, merge the pull request. New ideas, Preferences, and
non-blocking hardening become Follow-ups and do not reopen review.

## Full design contract for high-risk trust-boundary work

The full Phase A design contract in `TASK_PROMPT.md` is required when a task
materially changes any of these areas:

- authentication, credential verification, principal resolution, or
  authorization;
- signing, key custody, or key authority;
- tenant isolation;
- database roles, transactions, migrations, or durability semantics;
- runtime integration, startup readiness, or security-audit behavior;
- irreversible data behavior.

If classification is unclear, treat the task as high-risk until the boundary
is explicitly narrowed.

OFARM2 is pre-deployment development work. Prefer the best coherent design now
over preserving a temporary implementation. Do not defer a justified redesign,
rewrite, or refactor solely to avoid changing existing code; change is
comparatively cheap before production. It is not free: preserve accepted
contracts, evidence, explicit invariants, and stated boundaries, and verify
changes in proportion to their risk.

For those tasks, inspect first and write a Phase A design contract before
editing. It must define the problem and non-goals, trust model, authority map,
state and ordering, stable falsifiable invariants, production-reachable
negative cases, smallest coherent architecture, pull request boundary,
invariant-to-code-to-test traceability, provisional-design record when
relevant, and open decisions. Wait for explicit approval before implementation.
If implementation invalidates the approved contract, stop and request an
amendment.

Review the exact head against the approved contract. A Blocker must name the
violated invariant, supported production entry point, in-scope actor, exact
execution or state-transition path, required preconditions, material
consequence, and minimal reproduction or counterexample. Do not invent a new
attacker model or use unrelated future scope to block the pull request. Perform
at most one unconstrained full review at an exact head; after a fix, review only
the fix and affected invariants unless new evidence demonstrates that the
original scope is unsafe.

## Review guard - Core neutrality

Treat these as Blocker findings in Core-facing material: country-specific identifiers, authority names, legal deadlines, evidence sources, currentness policies, or conformance fixtures being presented as universal OFARM law; profile examples becoming executable Core logic; or profile-local law leaking into Core, Kernel, Platform, runtime adapters, contracts, or generated manifests.

## Review guard - Netherlands GO + GLMC 7 slice

For `profile_nl_go_glmc7_2026/`, treat these as Blocker findings: country
law leaking into Core, Kernel, Platform, runtime adapters, or the SI profile; a
whole-Netherlands production claim; an automated 30-hectare GLMC 7 carve-out;
BAS, Ctgb, Bijlage Aa, manure-register, GLMC 4, or GLMC 10 scope creep; or any
promotion path that accepts public/current-state data alone as historical truth.
