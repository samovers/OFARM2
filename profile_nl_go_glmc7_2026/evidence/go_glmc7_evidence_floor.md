# GO + GLMC 7 Evidence Floor

Status: profile evidence policy for `policy:nl.go-glmc7.evidence-floor.2026.v0_1`.
This is package material, not OFARM Core law.

## Hard Floor

A `nl.glmc7.crop_rotation_compliance_assertion` may promote only when the
evidence bundle contains the source-preserved artefacts needed to evaluate the
2026 claim-year slice.

| Evidence item | Required when | Refusal if missing |
|---|---|---|
| Filed GO artefact or submission proof | Always | Yes. No transaction-time GO filing anchor exists. |
| 2026 parcel snapshot | Always | Yes. The 15 May 2026 parcel scope cannot be reconstructed. |
| 2026 Gewascodelijst snapshot or used-code subset | Always | Yes. Crop codes and GLMC 7/rustgewas classes are unversioned. |
| 2023-2025 crop history | Always | Yes. Annual and four-year logic cannot be evaluated. |
| Parcel lineage for split, merge, transfer, overlap, or boundary change | When any geometry or identity change affects the history window | Yes. The parcel history is not auditable. |
| Sand/loess source | When any parcel may be on sand or loess | Yes for affected parcels. The rustgewas rule cannot be scoped. |
| Rustgewas proof | When sand/loess rustgewas compliance or exemption is asserted | Yes. The 2023-2026 rustgewas window cannot be proven. |
| Exemption proof | When any GLMC 7 exemption is claimed | Yes. Unsupported exemptions do not promote. |
| Skal or equivalent organic/in-conversion proof | When Article 32 organic or in-conversion route is claimed | Yes. The deemed-compliance route is unproven. |
| Delegation or `machtiging` proof | When a delegate files or asserts the claim | Yes. The filer authority path is unresolved. |
| RVO decision, `bezwaar`, or `beroep` artefacts | When review state is asserted | Yes for finality claims. Review status cannot be closed silently. |

## Evidence Posture

Public or current-state parcel data may corroborate the assertion, but it is not
sufficient by itself for high-consequence promotion. The filed GO artefact and
claim-year/historical evidence remain the canonical evidence path for this
profile slice.

Evidence must preserve source identity, capture time, claim year, and enough
parcel lineage to explain why the 2026 parcel and crop facts belong to the same
GLMC 7 evaluation history.

