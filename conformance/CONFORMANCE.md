# Pilot conformance plan

Two layers: **package self-check** (runs now) and the **platform MVP suite** (runs against the M1+ implementation).

## Conformance lanes

These lanes keep root conformance, profile design material, and profile
engineering tests from being read as the same kind of evidence:

| Lane | Owner | Current artifact(s) | Meaning |
|---|---|---|---|
| `PACKAGE_SELF_CHECK` | Root `conformance/` | `conformance/ofarm_pkg_contract_check.py` | Repository/package parse, digest, and authored-instance validation. |
| `PLATFORM_MVP_EXECUTED_EVIDENCE` | Root `conformance/evidence/` | `platform_mvp_results_*.json` | Timestamped output from the named platform MVP suite only. |
| `PLATFORM_MVP_FIXTURES` | Root `conformance/fixtures/` | Gate-sequencing fixtures | Canonical fixtures executed by root platform tests. |
| `PROFILE_DESIGN_CASES` | Profile packages | NL GO + GLMC 7 design cases | Profile design inventories, not executed evidence. |
| `PROFILE_ENGINEERING_TESTS` | Profile packages with root bridges | SI profile pytest modules | Engineering coverage discovered by root pytest, not platform MVP evidence. |
| `EXTRACTION_PLANNING` | `profile_si_ffs/extraction_inventory/` | SI extraction plans and inventories | Planning material, not runtime behavior or evidence. |

The detailed D7 lane design lives in
`profile_si_ffs/extraction_inventory/conformance_lane_split_plan.md`. This root
document is only the navigation and guard surface. It does not rename the
platform MVP suite, move evidence, change pytest collection, or create a
profile-local evidence writer.

## Package self-check (now)

```
python3 conformance/ofarm_pkg_contract_check.py
```

Verifies: every JSON parses · extracted files match manifest sha256 digests · authored profile instances validate against their schemas (zero-dependency subset validator; fails loudly on unsupported schema keywords).

## Profile-slice design cases

`profile_nl_go_glmc7_2026/conformance/nl_glmc7_2026_cases.md` lists the design
cases for the Netherlands GO + GLMC 7 2026 profile slice. These are profile
inventory cases, not executed platform evidence and not part of the M1 platform
MVP suite.

## Country-profile leakage audit

For PRs touching Core-facing material, run a profile-leakage audit such as:

```
rg -n "KMG-MID|GERK|Dutch GO|GLMC 7|Gecombineerde Opgave|Slovenia|Slovenian|\bSI\b" CORE.md PLATFORM.md KERNEL.md contracts kernel views conformance README.md AGENTS.md || true
```

Matches are acceptable only as explicit profile-layer references, review-guard
examples of what not to place in Core, or root navigation pointers. They are not
acceptable as Core contracts, Core semantics, runtime adapters, or default
conformance assumptions.

## Inherited fixtures

`fixtures/gate_sequencing/` — extracted verbatim from the canonical suite (digests in `contracts/CONTRACTS_MANIFEST.json`):

| Fixture | What it pins down |
|---|---|
| `operation_claim_missing_evidence_stays_draft` | Evidence floor blocks promotion; claim stays draft |
| `operation_claim_reviewed_accept_promotes` | Full chain: authority → validation → applicability → evidence → review → materialization (a spray scenario) |
| `compliance_assertion_reviewed_accept_promotes` | Compliance claims need review to become facts |
| `capture_note_no_compliance_shortcut` | A note never becomes compliance state |
| `capture_advisory_output_no_hard_truth_shortcut` | Advisory output never mutates compliance state |
| `revoked_submission_promotion_recheck_denies` | Revocation re-check at promotion denies (the offline-worker case) |
| `ai_assisted_submission_requires_human` | AI assistance never substitutes for the accountable human |
| `submission_filing_full_gate_chain_allow` | The full chain allows when everything is satisfied |

## Platform MVP suite (M1–M3 definition of done)

| # | Test | Source |
|---|------|--------|
| 1 | Append-only: update/delete attempts on record tables fail; correction = supersession | Kernel rule 1 |
| 2 | Default deny: no grant path → DENY with `AuthorizationDecisionTrace` | Kernel rule 2 |
| 3 | Offline draft sync: idempotency (replayed `idempotencyKey` is a no-op); event time ≠ record time preserved | `CAPTURE_MAPPING.md` sync rules |
| 4 | Operation claim ≠ accepted execution (gate-sequencing fixtures replayed against the live store) | inherited fixtures |
| 5 | Free-text product refusal: a record with no scheme-bound product binding cannot reach accepted state; binding state `UNRESOLVED` routes to review | Core code-binding discipline |
| 6 | Stale registry snapshot recheck: binding captured offline against snapshot N, synced when snapshot N+1 changes the authorisation → discrepancy recorded → review, not silent accept | F7 / sync rule 2 |
| 7 | Revoked delegation recheck: worker's offline record synced after revocation → review/deny, never silent accept | inherited fixture, live |
| 8 | Materialization basis trace: every current-state answer resolves to a complete `MaterializationBasis` + `ContextSnapshot`; basis-set change flips freshness to STALE | Kernel rule 5; PLATFORM invalidation |
| 9 | PassportView refusal/disclosure: unresolved/disputed render as exceptions; STALE bars export; missing basis refuses | `profile_si_ffs/views/VIEWS.md` |
| 10 | DocumentAssembly freeze/trace: frozen doc carries snapshot/basis/context/sufficiency refs; annex never promotes | `profile_si_ffs/views/VIEWS.md` |
| 11 | Inspector read-only: `SharingGrant` grants read, never write/review; revocation cuts access on next request | Kernel rule family 4 |
| 12 | Temporal conformance: delayed entry preserves distinct event/record/effective times end to end | Kernel rule 6 |
| 13 | Reference resolution: package-local refs in any authoritative record resolve; dangling refs are conformance failures | reference-resolution sub-gate |
| 14 | Reachability: every authoritative record reachable from exactly one `PromotionTrace` | Kernel reachability invariant |
| 15 | Manifest grounding: Capability Manifest claims match the `ActiveArtifactSet` it references (adapt canonical manifest-grounding runners) | PLATFORM capability posture |

Result reporting follows the canonical runner style: one JSON results file per run, checked into the pilot evidence lane — design fixtures must never be presented as executed evidence (readiness-gate condition 4).

Profile-local engineering tests may be collected by root bridge files, but they
remain engineering coverage unless a future D7 implementation deliberately
creates a distinct profile executed-evidence lane and writer.
