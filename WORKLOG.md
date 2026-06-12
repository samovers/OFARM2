# Worklog

## 2026-06-12 — Preflight-review cleanup (branch `m1/kernel`, commit 1c623c3)

- **Done:** investigated the external preflight review's five findings against the M1 kernel — implementation verified unaffected (zero FITO references in `kernel/`/`views/`; binding path already REGSR + decision-number identity per D9); landed the minimum controlled patch set: ERRATA E-002 (stale FITO-INFO wording), five doc locations re-worded to SI:UVHVVR-FFS-REG/REGSR, PROFILE.md shipped/deferred status corrected (nothing deferred remains), CONTRACTS_MANIFEST profileInstances 3→9 to match the checker, README counts + Slovenia-local cut-date currentness note.
- **Red:** nothing new; the two open items from the M1 entry below stand.
- **Next:** PR #2 review/merge; then M2 per the M1 entry below.

## 2026-06-12 — M1 Kernel build (branch `m1/kernel`)

- **Done:** full M1 brief tasks 1–7 — PostgreSQL append-only truth store + gate pipeline + materializer with the explainable-evidence draft shapes (D16, draft lane only), two view artifact pairs + output generator with refusal behavior, Capability Manifest (level `NONE`, no over-claim), conformance tests 1–15 with the 8 gate-sequencing fixtures replayed live (17/17 green, executed evidence in `conformance/evidence/`), package self-check PASS; multi-agent adversarial review confirmed 44 findings (3 blockers: D9 locator-as-identity re-verification, unvalidated cross-farm supersession, authz-result contract crash) — all fixed and pinned by regression test 97; ERRATA E-001 filed (registry has no temporal-conformance reason code).
- **Red:** freshness-vector watermarks are not snapshot-isolated under concurrent multi-process writers (accepted for the single-writer pilot; revisit at M2); steward question: the pre-existing M0 parse `profile_si_ffs/examples/regsr_snapshot_2026-06-12.json` carries sole-proprietor business names in public-register representative fields — confirm the D14 posture (file untouched: it is provenance evidence).
- **Next:** M2 — registry adapter scheduling (reuse `tooling/regsr_snapshot/`, fetch detail pages for bound products so D9 identity re-verification is confirmable instead of review-routed), GERK importer, OIDC onto Party/RoleAssignment; benchmark evidence per the explainable-evidence RFC before any capability claim above `NONE`.
