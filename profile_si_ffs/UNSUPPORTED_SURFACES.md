# Unsupported surfaces — `manifest:si.ffs.pilot.v0_1`

The Capability Manifest contract (`ofarm.capabilitymanifest.v0.1`) is closed
(`additionalProperties: false`) and carries no free-text surface, so the
PLATFORM.md unsupported-surface declaration lives here, referenced from the
regenerated `ActiveArtifactSet` notes. The manifest never claims any surface
below; this file makes the posture explicit rather than implicit.

**Unsupported in Platform v1** (PLATFORM.md "Unsupported surfaces"; the
already-active governance boundaries apply in full if any is ever exposed):

- dynamic pack installation / merging
- public QuerySpecification authoring / compiler (predefined versioned views only — manifest: `supportsGuidedQueryUI: false`, `supportsAIMediatedQuery: false`, `supportsPublicExpertQuery: false`)
- AI / agent runtime, including software-agent review (Phase-2 candidate, D8; the authority gate returns `REQUIRE_HUMAN_APPROVAL` for any non-human actor at promotion/publication/attestation stages)
- voice capture (`VOICE_CAPTURE` ingress channel exists in the contract enum; this deployment does not accept it)
- world models
- farm-to-farm intelligence
- learning / farm-memory
- cyber-physical mission execution
- sustainability-charter claim features
- livestock semantics

**Use types beyond surface-areas** (Reg. 2023/564 Annex): closed-space and
seed-treatment record rows are not implemented in pilot v1
(`SI_RECORD_FIELDS.md` §D.1).

**No live registry integration** (D9, PILOT_SI claim limits): the product
register enters only as dated `ReferenceSnapshot`s from scripted HTML parses;
the manifest's `IMPORT_MAPPING` surface is declared `PARTIAL` because the
parser exists and produced the shipped snapshot while scheduled adapter
cadence is M2. No current-compliance claim follows from any of this. Register
re-verification is identity-grade only where the snapshot carries decision
numbers (detail pages); list rows are locators, and locator-only
re-verification routes to review instead of pretending.

**Runtime evidence level** (Performance & Explainable Current-State Evidence
RFC §11.3): `CONFORMANCE_FIXTURE_PASSING` at most once the M1 suite is green —
no benchmark, load, storage-amplification, or production evidence exists, so
no fleet-scale or production readiness is claimed for explainable current
state or anything else (RFC §11.4, README claim limits).
