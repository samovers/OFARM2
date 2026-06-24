# Serbia Farm Registration And Organic Certificate Evidence Floor

Status: profile evidence policy for
`policy:rs.farm-reg-cert.evidence-floor.v0_1`. This is profile/package material,
not OFARM Core law.

Release posture:
`RS_ORGANIC_CROP_FARM_REG_CERT_IMPLEMENTATION_CANDIDATE_PRODUCTION_HOLD`

## General Evidence Posture

Promotion is allowed only when the source-preserved evidence floor is complete
for the asserted date, actor, operator, certificate scope, and review state.
Live public register state is corroborative only unless captured as
transaction-time evidence.

## `rs.farm_holding.registration_assertion`

Required evidence:

- BPG or accepted holding identifier;
- official UAP, eRPG, eAgrar, or eSanduce artefact proving registration, active
  status, submission status, or renewal status for the relevant date or year;
- public BPG lookup snapshot only as corroboration, not sole proof;
- actor identity evidence;
- actor authority evidence.

Refuse if:

- only live eRPG or public lookup exists;
- BPG or accepted holding identifier is missing;
- active/passive status is unreadable;
- status date is missing;
- current-year renewal is needed but absent;
- actor is authenticated but not authorised.

## `rs.organic.certification_status_assertion`

Required evidence:

- organic certificate artefact;
- certificate validity period covering the transaction date;
- operator identity matching farm or operator evidence;
- product category or certificate scope;
- issuing control body identity or code if present;
- Ministry annual authorised-control-body snapshot for the relevant year;
- ATS accreditation snapshot for the issuing body and relevant scope/date;
- suspended or withdrawn certificate adverse-status snapshot.

Refuse if:

- certificate is missing;
- certificate is expired on the transaction date;
- certificate subject does not reconcile to the farm/operator;
- certificate scope is missing;
- Ministry authorisation snapshot is missing;
- ATS accreditation snapshot is missing or has the wrong scope;
- adverse-status snapshot is missing for a high-consequence claim;
- certificate is suspended or withdrawn;
- private website evidence is offered as sole proof.

## `rs.organic.certifier_authority_reference`

Required evidence:

- Ministry annual authorised-control-body list snapshot;
- ATS accreditation record snapshot;
- certifier identity or code reconciliation;
- date and scope alignment.

Refuse if:

- either the Ministry or ATS side is missing;
- certifier identity or code does not reconcile;
- ATS scope is not clearly organic product certification or the relevant scope;
- status is suspended, withdrawn, or expired;
- source is live-only without a snapshot.

## `rs.review.appeal_or_objection_event`

Required evidence:

- challenged act or finding;
- service or delivery proof where applicable;
- appeal, objection, comment, waiver, or court-challenge artefact;
- authority addressed;
- review status: pending, waived, final, challenged in court, or unknown.

Refuse if:

- finality is claimed while review window or status is unresolved;
- review event has no challenged act;
- a generic under-review note is supplied without an official artefact.

## Privacy Floor

Use fictional, format-true examples only. Do not commit real farm, person,
company, BPG, JMBG, MB, PIB, address, certificate number, parcel ID, document
date, signature, screenshot, or filename containing identifiers.
