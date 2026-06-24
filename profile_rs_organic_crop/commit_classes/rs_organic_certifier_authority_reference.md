# Commit Class: rs.organic.certifier_authority_reference

Status: candidate / profile-local / production hold for
`commitclass:rs.organic.certifier_authority_reference.v0_1`.

Release posture:
`RS_ORGANIC_CROP_FARM_REG_CERT_IMPLEMENTATION_CANDIDATE_PRODUCTION_HOLD`

| Field | Profile requirement |
|---|---|
| Commit class name | `rs.organic.certifier_authority_reference` |
| Legal-source posture | Implementation-candidate authority reference; production closure requires packeted Ministry and ATS source artefacts |
| Competent authority | Serbian Ministry for annual organic control-body authorisation and ATS for accreditation status/scope |
| Submitter | Operator, certifier, reviewer, or profile steward with preserved source evidence |
| Delegate | Delegation is relevant only when a person asserts or submits the authority reference for a farm/operator |
| Required evidence | Ministry annual authorised-control-body list snapshot, ATS accreditation record snapshot, certifier identity/code reconciliation, and date/scope alignment |
| Freshness/currentness | Ministry list must be year-versioned; ATS evidence must be date/scope-specific and snapshotted |
| Promotion rule | Accept candidate reference only when Ministry and ATS sides both identify the same certifier and cover the relevant date/scope |
| Refusal rule | Refuse if either side is missing, identity/code mismatches, ATS scope is unclear or wrong, status is suspended/withdrawn/expired, or evidence is live-only |
| Correction/review path | Preserve newer source snapshots, correction notices, suspension/withdrawal notices, or review artefacts without overwriting history |
| Privacy/sovereignty constraints | Authority references should avoid personal identifiers and use source-preserved institutional evidence only |
| Conformance cases | `../conformance/rs_farm_registration_organic_certificate_cases.md` |

This candidate commit class is an authority reference, not a live integration or
a generic country abstraction.
