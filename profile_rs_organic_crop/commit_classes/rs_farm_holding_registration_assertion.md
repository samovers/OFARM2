# Commit Class: rs.farm_holding.registration_assertion

Status: candidate / profile-local / production hold for
`commitclass:rs.farm_holding.registration_assertion.v0_1`.

Release posture:
`RS_ORGANIC_CROP_FARM_REG_CERT_IMPLEMENTATION_CANDIDATE_PRODUCTION_HOLD`

| Field | Profile requirement |
|---|---|
| Commit class name | `rs.farm_holding.registration_assertion` |
| Legal-source posture | Implementation-candidate profile rule based on the Serbia source posture in `../law/organic_2025_transition_and_minimum_certificate_floor.md` |
| Competent authority | Directorate for Agrarian Payments / UAP and official eRPG/eAgrar/eSanduce artefacts for registration status |
| Submitter | Farm holder/operator or documented authorised representative |
| Delegate | Allowed only with farm-law delegation evidence; authentication alone is insufficient |
| Required evidence | Evidence floor in `../evidence/farm_registration_and_organic_certificate_evidence_floor.md` |
| Freshness/currentness | Currentness policy in `../currentness/source_snapshot_and_freshness_policy.md` |
| Promotion rule | Accept candidate assertion only when official transaction-date or claim-year registration/status artefacts, holding identifier, actor identity, and actor authority are complete |
| Refusal rule | Refuse on live-lookup-only proof, missing BPG or accepted identifier, unreadable active/passive status, missing status date, missing renewal proof when needed, or authentication without authority |
| Correction/review path | Preserve updated official artefacts, submissions, inbox messages, corrections, objections, or review events as append-only evidence |
| Privacy/sovereignty constraints | Use fictional placeholders only; no real Serbian identifiers or document filenames containing identifiers |
| Conformance cases | `../conformance/rs_farm_registration_organic_certificate_cases.md` |

This candidate commit class is Serbia profile material. It does not add a Core
commit class or runtime adapter.
