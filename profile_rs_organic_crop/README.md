# Serbia organic crop farm registration + organic certificate profile slice

Status: profile/package material only; implementation candidate; production hold.

Release posture:
`RS_ORGANIC_CROP_FARM_REG_CERT_IMPLEMENTATION_CANDIDATE_PRODUCTION_HOLD`

This package is a non-production Serbia profile slice for organizing evidence,
refusal gates, and conformance design cases for one narrow topic: Serbian
farm/holding registration status plus organic certificate status for a Serbian
organic crop farm.

## Slice Boundary

This profile covers only:

- farm/holding registration status;
- organic certificate status;
- certifier authority reference;
- appeal, objection, or review event preservation.

It is not a whole-Serbia profile, not a production-grade organic certification
service, not legal advice, not live-registry integration, and not an
external-standard readiness claim.

## Claim Limits

- Serbia law, authorities, identifiers, registers, currentness rules, examples,
  and conformance fixtures stay inside this profile package.
- No OFARM Core, Kernel, Platform, runtime adapter, generated manifest, contract,
  or existing country profile change is implied.
- A live eRPG, BPG, Ministry, ATS, or private website lookup is current-state
  corroboration only unless preserved as transaction-time evidence.
- Public registers must not become hidden truth stores.
- AI or advisory interpretation never promotes Compliance Twin state.
- eID, ConsentID, or similar authentication proof is not farm-law delegation
  authority.
- Examples must be fictional and format-true only. Do not commit real farm,
  farmer, company, BPG, JMBG, MB, PIB, address, certificate number, parcel ID,
  document date, signature, screenshot, or filename containing identifiers.

## Production Hold

The current source posture supports an implementation candidate, not production
closure. Production blockers include unpacketed official source artefacts for
the 2026 authorised organic control-body roster, named ATS accreditation records,
the post-2025 certificate form, suspended or withdrawn certificate status,
transaction-date eRPG active/passive proof, direct farmer-side review routes
against control-body certificate actions, and generic adviser or delegate
authority.

Any claim depending on those blockers must refuse or preserve review state
rather than promote.

## Profile Contents

- `law/organic_2025_transition_and_minimum_certificate_floor.md` - research
  basis, transition posture, and minimum certificate field floor.
- `authority/serbia_authority_map.md` - profile-local authority and evidence
  source map.
- `evidence/farm_registration_and_organic_certificate_evidence_floor.md` -
  minimum evidence and refusal floor.
- `currentness/source_snapshot_and_freshness_policy.md` - source snapshot and
  freshness posture.
- `commit_classes/*.md` - candidate profile-local commit-class contracts.
- `conformance/rs_farm_registration_organic_certificate_cases.md` - design
  conformance case inventory.
- `source_packet_extracts/source_manifest.json` - parse-only source posture
  manifest; no official local source packets are claimed.
- `adapter_boundary/serbian_database_copy_adapter_boundary_plan.md` - docs-only
  boundary for private Serbian database-copy adapter rehearsal.

## Reserved Identifiers

| Identifier | Meaning |
|---|---|
| `profile:rs.organic-crop.farm-reg-cert.v0_1` | Serbia organic crop farm registration plus organic certificate profile slice |
| `pack:rs.organic-crop.farm-reg-cert.v0_1` | Package reference for this profile slice |
| `policy:rs.farm-reg-cert.evidence-floor.v0_1` | Evidence floor policy described in this package |
| `policy:rs.farm-reg-cert.currentness.v0_1` | Currentness policy described in this package |
| `commitclass:rs.farm_holding.registration_assertion.v0_1` | Candidate farm/holding registration assertion |
| `commitclass:rs.organic.certification_status_assertion.v0_1` | Candidate organic certificate status assertion |
| `commitclass:rs.organic.certifier_authority_reference.v0_1` | Candidate certifier authority reference |
| `commitclass:rs.review.appeal_or_objection_event.v0_1` | Candidate appeal, objection, or review event |
