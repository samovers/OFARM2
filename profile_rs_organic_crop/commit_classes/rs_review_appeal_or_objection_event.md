# Commit Class: rs.review.appeal_or_objection_event

Status: candidate / profile-local / production hold for
`commitclass:rs.review.appeal_or_objection_event.v0_1`.

Release posture:
`RS_ORGANIC_CROP_FARM_REG_CERT_IMPLEMENTATION_CANDIDATE_PRODUCTION_HOLD`

| Field | Profile requirement |
|---|---|
| Commit class name | `rs.review.appeal_or_objection_event` |
| Legal-source posture | Implementation-candidate review-state preservation for Serbia profile claims; direct route details remain production blockers where not packeted |
| Competent authority | Challenged authority or certifier, Ministry/inspection route, and Administrative Court / upravni spor layer when applicable |
| Submitter | Operator, farm holder, certificate holder, authorised representative, reviewer, or profile steward preserving review evidence |
| Delegate | Delegated review action requires official authority evidence; authentication alone is insufficient |
| Required evidence | Challenged act or finding, service/delivery proof where applicable, appeal/objection/comment/waiver/court artefact, authority addressed, and review status |
| Freshness/currentness | Review status must be source-preserved and cannot be inferred from current public state alone |
| Promotion rule | Preserve the review event and its status when the challenged act and official review artefact are present |
| Refusal rule | Refuse finality claims when review window/status is unresolved, when no challenged act exists, or when only a generic under-review note exists |
| Correction/review path | Append subsequent review artefacts; do not collapse pending, waived, final, challenged, or unknown states into a single clean status |
| Privacy/sovereignty constraints | Do not commit real names, addresses, signatures, screenshots, dates from private farm documents, or filenames containing identifiers |
| Conformance cases | `../conformance/rs_farm_registration_organic_certificate_cases.md` |

This candidate commit class preserves review state. It does not decide the
underlying organic or registration outcome.
