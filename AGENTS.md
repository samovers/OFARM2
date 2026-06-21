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

## Review guard - Core neutrality

Treat these as blocking review issues in Core-facing material: country-specific identifiers, authority names, legal deadlines, evidence sources, currentness policies, or conformance fixtures being presented as universal OFARM law; profile examples becoming executable Core logic; or profile-local law leaking into Core, Kernel, Platform, runtime adapters, contracts, or generated manifests.

## Review guard - Netherlands GO + GLMC 7 slice

For `profile_nl_go_glmc7_2026/`, treat these as blocking review issues: country
law leaking into Core, Kernel, Platform, runtime adapters, or the SI profile; a
whole-Netherlands production claim; an automated 30-hectare GLMC 7 carve-out;
BAS, Ctgb, Bijlage Aa, manure-register, GLMC 4, or GLMC 10 scope creep; or any
promotion path that accepts public/current-state data alone as historical truth.
