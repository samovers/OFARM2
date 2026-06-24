# Serbia Authority Map

Status: profile-local authority map for
`profile:rs.organic-crop.farm-reg-cert.v0_1`. This is implementation-candidate
material under production hold.

Release posture:
`RS_ORGANIC_CROP_FARM_REG_CERT_IMPLEMENTATION_CANDIDATE_PRODUCTION_HOLD`

| Authority or surface | Profile role | Evidence issued or exposed | Status | Currentness risk | Production blocker |
|---|---|---|---|---|---|
| Ministry of Agriculture, Forestry and Water Management | Organic-law competent authority and organic control-body authorisation source | Organic register context, annual authorised-control-body list, inspection or non-compliance material | Binding authority for organic administration | Annual and decision-specific artefacts must be snapshotted | Exact official 2026 authorised-control-body roster is not packeted |
| Ministry group or function responsible for organic production | Operational organic-production function | Organic-subject register context, certificate and control-body administration context | Binding or official administrative function when source-packeted | Function names and responsibilities can change | Function-specific official packet is not closed |
| Directorate for Agrarian Payments / UAP | Farm/holding registration and agricultural administration channel | eRPG/eAgrar registration or status artefacts, submission or renewal evidence | Binding public authority surface when artefact-preserved | Live account or register state is not historical proof | Durable transaction-date active/passive proof is not closed |
| eAgrar / eRPG / eSanduce / ePodsticaji | Digital service surfaces for farm registration and agricultural artefacts | Official messages, registration status artefacts, submissions, inbox/service records | Official service surfaces, not law by themselves | Portal state changes; artefacts must be preserved | Required transaction-time artefact formats are not fully packeted |
| eUprava / eID / ConsentID | Authentication layer | Login, identity, and consent/authentication traces | Authentication surface only | Authentication can be current but not delegated authority | Generic adviser/delegate authority is unresolved |
| ATS, Accreditation Body of Serbia | Accreditation authority for certification bodies | Accreditation status, scope, suspension, withdrawal, and validity evidence | Accreditation authority | Scope and status must be date-specific and snapshotted | Named 2026 body records and scopes are not packeted |
| Organic control/certification bodies | Private or delegated certification actors | Organic certificate artefacts, control findings, refusal/withdrawal notices | Certifier material; authority depends on Ministry authorisation plus ATS accreditation | Private websites and current lists can drift | Ministry and ATS dual-gate evidence must be packeted |
| Ministry or inspection route for organic non-compliance | Organic non-compliance and enforcement route | Inspection findings, adverse status, suspension, withdrawal, or enforcement artefacts | Binding authority when official artefact-preserved | Review/finality status must be preserved | Official suspended/withdrawn certificate artefact source is not packeted |
| Administrative Court / upravni spor review layer | Judicial review preservation layer | Court challenge, administrative dispute, status, and finality artefacts | Review authority | Finality cannot be assumed from live status alone | Farmer-side review route for control-body certificate actions is not fully pinned |

## Authority Rules

- Ministry authorisation and ATS accreditation are a dual gate for certifier
  authority. One side alone is insufficient for high-consequence promotion.
- eID, ConsentID, or portal access proves authentication only. It does not prove
  the actor is authorised to act for the farm or operator.
- Private certifier material may support a claim but cannot alone prove public
  authority status.
- Review state must remain explicit: pending, waived, final, challenged in
  court, or unknown.
