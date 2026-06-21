# Commit Class: nl.glmc7.crop_rotation_compliance_assertion

Status: profile contract document for
`commitclass:nl.glmc7.crop_rotation_compliance_assertion.2026.v0_1`.
This is profile/package material only.

## Contract Fields

| Field | Profile requirement |
|---|---|
| Commit class name | `nl.glmc7.crop_rotation_compliance_assertion` |
| Legal basis | Stcrt 2026, 3657 for the GO filing basis; `Uitvoeringsregeling GLB 2023` Article 32 and Annex 4 GLMC 7 as reconstructed through Stcrt 2026, 1855 and official 2026 RVO guidance |
| Competent authority | Ministerie van LVVN, operationally administered by RVO; review path through RVO `bezwaar` and CBb `beroep` |
| Submitter | Farmer or other party with recorded authority for the 2026 GO filing |
| Delegate | Allowed only with valid RVO/eHerkenning authorisation or `machtiging` evidence |
| Claim year | Fixed to 2026 |
| Parcel scope | Dutch arable land (`bouwland`) in the 2026 GO scope, using the 15 May 2026 `peildatum` |
| Required evidence | Evidence floor in `../evidence/go_glmc7_evidence_floor.md` |
| Freshness/currentness | Currentness policy in `../currentness/go_glmc7_currentness_policy.md` |
| Promotion rule | Promote only when the 2026 GO filing anchor, parcel scope, crop-code version, crop history, parcel lineage, relevant sand/loess and rustgewas facts, exemption proof, and delegation authority are complete and fresh for the claim |
| Refusal rule | Refuse on missing GO proof, missing 2026 parcel snapshot, missing crop-code version, missing 2023-2025 crop history, unresolved parcel lineage, missing sand/loess source for affected parcels, missing rustgewas proof, unsupported exemption, missing delegated-filing authority, or public-current-state-only proof |
| Correction route | Before final decision, correct and re-send the GO through the official filing workflow where allowed; after RVO decision, preserve the `bezwaar` and `beroep` route |
| Appeal route | RVO decision -> `bezwaar` -> `beslissing op bezwaar` -> `beroep` at CBb |
| Sovereignty/currentness constraint | Filed GO history and source-preserved evidence remain canonical. Public current-state data may corroborate but never silently replaces the history-first truth path |
| Unsupported carve-out | A 30-hectare GLMC 7 carve-out is not encoded. Any assertion relying on it refuses or enters manual legal hold |
| Audit-hardening note | Direct Wettenbank/Wetten.nl consolidated text capture remains a TODO; official amendment-chain reconstruction is accepted under this release posture |

## OFARM Boundary

This commit class does not add a new generic Core commit class and does not
modify Kernel promotion logic. It describes a Netherlands profile-layer
assertion that a later runtime implementation may map onto existing governed
commit and review mechanisms.

This profile does not yet cut a deterministic calculation contract for follow-on
crop routes, denominator and rounding rules, crop-code changes between years,
parcel split/merge lineage math, or parcel-level versus holding-level exemption
precedence. Those details are required before any future rule-engine readiness
claim.
