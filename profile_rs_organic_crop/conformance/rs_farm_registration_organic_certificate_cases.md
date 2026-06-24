# Serbia Farm Registration And Organic Certificate Conformance Design Cases

Status: profile-slice design cases. These are not executed platform evidence.

Release posture:
`RS_ORGANIC_CROP_FARM_REG_CERT_IMPLEMENTATION_CANDIDATE_PRODUCTION_HOLD`

| # | Case | Input facts | Evidence present | Expected result | Reason | OFARM invariant protected |
|---|---|---|---|---|---|---|
| A1 | Valid farm registration artefact | BPG or accepted holding identifier and active registration/status for the relevant date/year | Preserved official eRPG/UAP/eAgrar/eSanduce artefact plus matching holder/legal-entity authority | Accept candidate farm-registration assertion | Registration and actor authority floor is complete | No shortcut to truth |
| A2 | Valid organic certificate status | Certificate covers transaction date and matches operator/scope | Certificate artefact, Ministry annual list snapshot, ATS scope/status snapshot, and clear adverse-status snapshot | Accept candidate organic-certification status assertion | Certificate status and dual authority gate are complete | Explicit authority and evidence |
| A3 | Certifier authority reconciles | Same control body appears in Ministry annual list and ATS accreditation for relevant date/scope | Ministry snapshot and ATS snapshot with identity/code reconciliation | Accept certifier authority reference | Certifier authority has both public-authority and accreditation sides | Default deny until authority is proven |
| A4 | Review pending preserved | Inspector, Ministry, control-body, or court review remains pending | Challenged act and preserved review artefact | Preserve review event; do not collapse to final state | Review state is part of the truth record | Review and correction remain append-only |
| R1 | Live public lookup only | BPG appears in a live public lookup today | Live lookup only | Refuse high-consequence registration assertion | Current state is not historical proof | History-first truth |
| R2 | Passive holding status | Holding status is passive for the relevant date/year | Official status artefact shows passive state | Refuse | Active registration predicate fails | Refusal over pretending |
| R3 | Renewal absent | Current-year renewal is required but absent | Identifier and older status exist, no renewal artefact | Refuse | Freshness floor is incomplete | Freshness discipline |
| R4 | Certificate missing | Organic status is asserted without certificate artefact | Authority or marketing material only | Refuse | Certificate floor is missing | Evidence floor blocks promotion |
| R5 | Certificate expired | Certificate validity does not cover transaction date | Certificate artefact present but outside validity period | Refuse | Validity predicate fails | Distinct event and valid-time |
| R6 | Subject mismatch | Certificate subject cannot be reconciled to farm/operator | Certificate and farm evidence identify different subjects | Refuse | Identity reconciliation fails | No hidden identity merge |
| R7 | Ministry list missing | Certificate appears valid but certifier is absent from preserved Ministry annual list | Certificate and ATS material only | Refuse | Ministry authorisation gate is missing | Explicit authority |
| R8 | ATS snapshot missing | Certifier appears on Ministry list but no ATS record is preserved | Ministry snapshot only | Refuse | Accreditation gate is missing | Default deny |
| R9 | ATS wrong scope | ATS record exists but does not cover organic product certification or relevant scope | Ministry snapshot and wrong-scope ATS snapshot | Refuse | Accreditation scope predicate fails | Evidence specificity |
| R10 | Adverse-status snapshot missing | Certificate is otherwise plausible but no suspended/withdrawn check is preserved | Certificate, Ministry, and ATS evidence only | Refuse high-consequence certification claim | Adverse-status floor is incomplete | Refusal over pretending |
| R11 | Certificate suspended or withdrawn | Adverse-status artefact shows suspended or withdrawn status | Certificate plus adverse-status evidence | Refuse | Clean certificate status is contradicted | Source-preserved correction |
| R12 | Authenticated adviser lacks delegation | Adviser or consultant logs in through eID/ConsentID but no official delegation exists | Authentication proof only | Refuse high-consequence action | Authentication is not authority | Authority-first governance |
| R13 | Review pending but final clean status claimed | Review exists but finality is asserted | Challenged act and pending review artefact | Refuse final promotion; preserve review state | Review cannot be flattened | Append-only review state |
| R14 | Marketing claim only | Public/private website claims organic status | Website or private marketing material only | Refuse | Private/public marketing is not official proof | Capture is not commitment |
| R15 | Real farm data appears | Example uses real farm, person, company, BPG, JMBG, MB, PIB, address, certificate number, parcel ID, document date, signature, screenshot, or identifying filename | Any real identifier or document artefact | Fail review | Privacy floor is breached | Privacy is absolute |
