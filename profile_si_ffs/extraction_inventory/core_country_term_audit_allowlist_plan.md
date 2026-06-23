# Core Country-Term Audit Allowlist Plan

Status: documentation-only audit planning. This file does not implement a
machine guard, certify Core, change runtime behavior, alter tests, update
contracts, update generated outputs, or change Core, Kernel, or Platform
semantics.

This plan follows `core_country_neutrality_certification_plan.md` and describes
the future review layer needed before the proposed country-term scan can become
an enforcing L5 machine guard.

## Purpose

The country-term audit should make country/profile-specific terms visible in
Core-facing surfaces and force every hit into an explicit review category. The
goal is not zero text matches. The goal is zero hidden country law, hidden
authority assumptions, hidden evidence-source assumptions, hidden profile
identifiers, or hidden profile fixtures in Core, Kernel, Platform, and root
conformance surfaces.

Until this review layer is implemented, the scan remains informational.

## Seed Scan

Use this scan as the starting point:

```sh
rg -n "KMG-MID|GERK|REGSR|FFSNaprave|Slovenia|Slovenian|\bSI\b|Dutch GO|GLMC 7|Gecombineerde Opgave" CORE.md PLATFORM.md KERNEL.md contracts kernel views conformance README.md AGENTS.md
```

Future implementations may split the expression into named term groups, but
must preserve at least these seed terms unless a later certification PR explains
why a term is no longer needed.

## Allowlist Categories

| Category | Meaning | Example surfaces |
| --- | --- | --- |
| `PROFILE_LOCAL_POINTER` | Root text points to profile-owned material without restating profile law or claiming runtime capability. | Root README pointers, `views/VIEWS.md`. |
| `ACTIVE_RUNTIME_SI_SUPPORT` | SI-specific text remains because the current active runtime is still the SI pilot. | `kernel/context.py`, `kernel/manifest.py`, selected root tests. |
| `PROFILE_LOCAL_CONTENT` | The hit is already inside a profile package or profile-local test module. | `kernel/profiles/si_ffs/**`, `profile_si_ffs/**`. |
| `CONTRACT_COMMENT_REVIEW` | Contract comments contain country/profile examples and need explicit review before neutral wording changes. | Core identity payload schema comments. |
| `CONFORMANCE_EVIDENCE_HISTORY` | The hit appears in historical or executed evidence context and must not be silently relabeled. | `conformance/evidence/**`, root evidence writer references. |
| `REVIEW_GUARD_OR_NON_CLAIM` | The hit exists only to warn against a claim or document an out-of-scope boundary. | `AGENTS.md`, certification plans. |
| `APPARENTLY_NEUTRAL_PENDING_AUDIT` | The surface appears neutral, but the classification is not certified until the allowlist review is complete. | `CORE.md`, `KERNEL.md` when no country-specific semantics are embedded. |

## Disallowed Hits

A future machine guard should reject or require manual review for hits that:

- encode country law, authority, evidence source, identifier, or fixture data as
  Core law;
- describe SI pilot behavior as universal OFARM behavior;
- add a Netherlands profile slice to active runtime capability claims;
- treat profile-local design cases as executed platform evidence;
- add or imply Slovenia production readiness;
- add or imply multi-profile runtime readiness without an implemented loader,
  harness, generated-output design, and evidence lane;
- weaken assertion/history-first truth, governed materialization, authority,
  evidence, freshness, review, correction, promotion, or refusal rules.

## Future Allowlist Record Shape

If this becomes a machine-readable allowlist later, each allowed hit should carry
at least:

| Field | Purpose |
| --- | --- |
| `id` | Stable review-record identity for diffs and follow-up references. |
| `path` | File or glob where the hit is allowed. |
| `term` | Exact term or term group. |
| `category` | One of the allowlist categories above. |
| `reason` | Short reviewer-facing explanation. |
| `owner` | Review lane or package responsible for the hit. |
| `expiresWhen` | Condition that should remove the allowance, such as profile harness completion. |
| `forbiddenUse` | The specific overclaim or semantic leak this allowance must not permit. |

The future record must be a guardrail, not a capability declaration. It must not
be named, described, or consumed as a runtime manifest.

An initial file/glob-level review record now lives in
`core_country_term_audit_review_records.json`. It is intentionally not
line-level, not enforcing, and not an L5 machine guard. A later certification PR
must still convert the reviewed hits into an approved line-level record before
any certification claim.

The current manual consistency check validates this initial record's boundary
flags, stable ids, required-field and category vocabularies, seed term
vocabulary, seed-scan command alignment, file/glob path coverage, and
`seed_terms_absent` no-hit records. Those checks are file/glob-level review
guards only. They are not a line-level allowlist and not an enforcing L5 machine
guard.

## Review Flow

1. Run the seed scan.
2. Group hits by path and term.
3. Assign each hit to an allowlist category or mark it as a blocker.
4. For blockers, decide whether the safe fix is profile-local movement,
   profile-neutral wording, contract-comment review, or a future loader/harness
   design.
5. Re-run package validation and diff hygiene.
6. Only after the review record is stable, implement an enforcing machine check.

## Stop Conditions

Stop and re-plan if the future check would:

- require contract edits or generated-output changes in the same PR;
- hide active SI runtime support behind generic wording;
- classify a profile source, law, identifier, or evidence source as Core truth;
- mark Core certified before every hit is removed, profile-local, or explicitly
  classified;
- make the profile navigation index look like runtime support or capability
  evidence.

## Validation For This Planning PR

Run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

Run the informational audit:

```sh
rg -n "KMG-MID|GERK|REGSR|FFSNaprave|Slovenia|Slovenian|\bSI\b|Dutch GO|GLMC 7|Gecombineerde Opgave" CORE.md PLATFORM.md KERNEL.md contracts kernel views conformance README.md AGENTS.md profile_si_ffs/extraction_inventory/core_country_term_audit_allowlist_plan.md
```

Expected hits are review inputs. This planning PR should not make the audit
enforcing.
