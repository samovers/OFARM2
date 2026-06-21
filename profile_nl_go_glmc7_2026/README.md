# Netherlands GO + GLMC 7 2026 profile slice

Status: profile/package material only. This is not OFARM law and it does not
change OFARM Core, Kernel, Platform, runtime adapters, generated manifests, or
the Slovenia profile.

Release posture:
`NL_GO_GLMC7_2026_CONFORMANCE_READY_AMENDMENT_CHAIN`

> This package is a conformance-ready narrow profile slice under the official amendment-chain source standard. It is not a whole-Netherlands production profile, not runtime production readiness, and not an external standard-readiness claim.

## Slice Boundary

This profile covers only the 2026 `Gecombineerde Opgave` plus GLMC 7 crop
rotation compliance for Dutch arable land (`bouwland`). It does not claim that
the whole Netherlands profile is production-ready, that this repository is
runtime-production-ready, or that any external standard is production-ready.

The accepted legal source standard for this slice is official amendment-chain
reconstruction. Direct Wettenbank/Wetten.nl consolidated text capture remains an
audit-hardening TODO, not a blocker under this release posture.

No automated 30-hectare GLMC 7 carve-out is encoded. The source packet found no
official support for that carve-out. Any assertion relying on it must refuse or
enter legal hold rather than promote.

Public or current-state parcel and crop data is corroborative only unless it has
been captured as transaction-time evidence for the relevant claim-year fact.
Public current state may never silently replace filed GO history.

## Profile Contents

- `law/go_2026_and_glmc7_2026.md` - legal and guidance source split for the
  2026 GO and GLMC 7 rule.
- `evidence/go_glmc7_evidence_floor.md` - hard evidence floor for promotion.
- `currentness/go_glmc7_currentness_policy.md` - freshness and source-preserving
  currentness posture.
- `commit_classes/nl_glmc7_crop_rotation_compliance_assertion.md` - profile
  contract for the narrow compliance assertion.
- `conformance/nl_glmc7_2026_cases.md` - design conformance case inventory.
- `source_packet_extracts/source_manifest.json` - parse-only authored source
  index for this profile slice.

## Reserved Identifiers

| Identifier | Meaning |
|---|---|
| `profile:nl.go-glmc7.2026.v0_1` | Narrow Netherlands GO + GLMC 7 2026 profile slice |
| `pack:nl.go-glmc7.2026.v0_1` | Package reference for this profile slice |
| `policy:nl.go-glmc7.evidence-floor.2026.v0_1` | Evidence floor policy described in this package |
| `policy:nl.go-glmc7.currentness.2026.v0_1` | Currentness policy described in this package |
| `commitclass:nl.glmc7.crop_rotation_compliance_assertion.2026.v0_1` | Profile commit-class contract |
| `source:nl.stcrt.2026.3657.go` | Stcrt 2026, 3657, `Regeling Landbouwtelling en Gecombineerde opgave 2026` |
| `source:nl.stcrt.2026.1855.uglb-amendment` | Stcrt 2026, 1855, January 2026 UGLB amendment |
| `source:nl.rvo.glmc7.2026` | RVO GLMC 7 operational guidance |
| `source:nl.rvo.conditionaliteiten.2026` | RVO 2026 conditionality guidance |
| `source:nl.rvo.gecombineerde-opgave.2026` | RVO GO operational guidance |
| `source:nl.rvo.gewascodelijst.2026` | RVO crop-code reference data |
| `source:nl.rvo.rustgewassen.2026` | RVO rustgewas guidance |
| `source:nl.rvo.landbouwareaal.2026` | RVO agricultural-area guidance |
| `source:nl.rvo.bezwaar` | RVO objection-route guidance |
| `source:nl.rechtspraak.cbb` | Rechtspraak / CBb appeal-route guidance |
