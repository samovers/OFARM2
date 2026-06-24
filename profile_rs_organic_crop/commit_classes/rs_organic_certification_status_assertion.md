# Commit Class: rs.organic.certification_status_assertion

Status: candidate / profile-local / production hold for
`commitclass:rs.organic.certification_status_assertion.v0_1`.

Release posture:
`RS_ORGANIC_CROP_FARM_REG_CERT_IMPLEMENTATION_CANDIDATE_PRODUCTION_HOLD`

| Field | Profile requirement |
|---|---|
| Commit class name | `rs.organic.certification_status_assertion` |
| Legal-source posture | Implementation-candidate profile rule based on the 2025 Serbian organic-law research posture; production closure is blocked by missing official packets |
| Competent authority | Ministry organic authority plus ATS accreditation gate, with certificate artefact from an authorised organic control/certification body |
| Submitter | Operator, farm holder, certificate holder, or documented authorised representative |
| Delegate | Allowed only with official authority evidence; eID/ConsentID or login proof is not enough |
| Required evidence | Organic certificate artefact, validity period, subject match, product category/scope, issuing body identity, Ministry authorised-body snapshot, ATS accreditation snapshot, and adverse-status snapshot |
| Freshness/currentness | Certificate, Ministry, ATS, and adverse-status evidence must align to the relevant date/scope and be snapshotted |
| Promotion rule | Accept candidate assertion only when certificate facts and Ministry/ATS/adverse-status gates are all complete and coherent |
| Refusal rule | Refuse on missing/expired certificate, subject mismatch, missing scope, missing Ministry snapshot, missing/wrong ATS scope, missing adverse-status snapshot, suspended/withdrawn certificate, or private-website-only proof |
| Correction/review path | Preserve certificate correction, control-body action, Ministry/inspection action, objection, court challenge, or unresolved review state |
| Privacy/sovereignty constraints | Do not commit real certificate numbers, operator identifiers, signatures, screenshots, or filenames containing identifiers |
| Conformance cases | `../conformance/rs_farm_registration_organic_certificate_cases.md` |

This candidate commit class does not certify organic status. It describes the
minimum profile-local evidence floor needed before a future runtime could safely
represent a candidate organic certificate status fact.
