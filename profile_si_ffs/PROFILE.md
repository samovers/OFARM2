# Slovenia FFS pilot profile (`profile:si.ffs.recordkeeping.v0_1`)

Status: profile definition — candidate material, not OFARM law. National registers and identifiers are **anchors and bindings under this profile**, never universal OFARM core law (Constitution RC2.1 §3.4).

## Claim scope

Record-keeping completeness only. No current-compliance claim, no certification claim, no legal advice. See `../PILOT_SI.md`.

## Scheme role map (feeds the `AgronomicCodeBindingProfile` instance)

| Scheme | Role under this profile | Currentness posture |
|---|---|---|
| **SI:UVHVVR-FFS-REG** — UVHVVR "Seznam registriranih FFS" (`spletni2.furs.gov.si/FFS/REGSR/`) | Mandatory binding source for plant-protection product authorisation identity; **primary external key = Številka odločbe (registration decision number) + validity dates**; trade name is captured evidence, never sole identity; page record numbers are locators, never identity. Product pages natively carry **EPPO-coded crops with use context and EPPO-coded target organisms**, karenca, and dose/buffer/MRL subpages — the authorisation-mismatch advisory check runs directly from the snapshot. *(M0 corrections: FITO-INFO is shut down; register verified by human browser session — `M0_DESK_RESEARCH.md` §3–4a.)* | Snapshot-based: **no official export exists (verified)**; weekly scripted parse of the official HTML list/detail pages → dated `ReferenceSnapshot`; monthly manual floor. Verification traces record the HTML lookup surface so the unofficial-surface risk is declared, not hidden. **Weaker than the Belgium reference pattern and declared so.** |
| **IS Evidenca FFS** — UVHVVR central FFS-use registry (live by 1 Dec 2026) | Future **submission target**, not a binding scheme: the pilot's frozen register export is positioned to become the farmer's annual submission (first due 31 Jan 2027 for 2026). Interface TO-VERIFY (M0 outreach Q2). | Not applicable until the state publishes its interface; tracked in `M0_DESK_RESEARCH.md` §2. |
| **GERK** | Parcel identifier scheme for Field identities (`parcelIdentifiers.scheme = "SI:GERK"`) | **National GERK layer is open data** (OPSI shapefile + WMS, MKGP viewer): the app carries the layer; farmer supplies KMG-MID and confirms their GERK list (eRKG / subsidy paperwork). Layer snapshot-stamped per sync; farmer-provided export remains fallback only. |
| **KMG-MID** | Holding identifier scheme for Farm identities (`holdingIdentifiers.scheme = "SI:KMG-MID"`) | Captured at onboarding as registered identifier + evidence |
| **EPPO** | Crop and target-organism codes | Pinned code-list version per package release |
| **BBCH** | Growth stage codes (where label/rules cite stages) | Pinned version |
| **UCUM / QUDT** | Unit codes / quantity kinds for dose, area, volume | Pinned version |
| **SI:FFS-NAPRAVE** — UVHVVR sprayer-inspection register (`spletni2.furs.gov.si/FFS/FFSNaprave/`) | Equipment inspection evidence source: yearly **TXT/XLS/XML+XSD downloads (verified)** with official 20-field dictionary; a farm's sprayer matches by the **inspection-sticker number on the machine** (`StevilkaZnaka` + `VeljavnostZnaka`). | Machine-readable official downloads — the one strong-currentness surface in the SI profile. Yearly files; import as dated `ReferenceSnapshot`s. |
| **SI:FFS-IZKAZNICA** — FFS training-card number (ZFfS-1 Art. 45 register) | Required record field per Art. 44.b(3): captured once per operator at onboarding as a `Party.registeredIdentifiers` entry; auto-attached to every record. | Card number is farmer-supplied evidence (photo of card = `EvidenceRecord`); no public lookup assumed. |
| **EU Pesticides Database** | EU active-substance **context only** — informational, no legal value, never product authorisation identity | Optional context snapshots |

Reference pattern: `../reference/rfcs/OFARM_External_Code_Binding_Currentness_and_Verification_RFC_v0_1.md` (Belgium/Phytoweb). The SI profile mirrors its structure with an honestly weaker declared currentness class; converging to Phytoweb-grade mechanics is the precondition for any future current-compliance claim.

## Evidence and review policy (`policy:si.ffs.evidence-review.v0_1`)

**Evidence floor for promoting an operation claim to accepted execution:**
resolved product binding (against a dated snapshot) · dose with valid UCUM unit · valid parcel ref (GERK-bound field or explicit `PartialExtent`) · crop binding (EPPO, may come from auto-created cycle) · operator party (with `DelegationGrant` if not the holder) · event time within plausibility window. Photo evidence: encouraged, never required for the floor.

**Sufficiency cases** are auto-generated from this policy template at three points: operation-claim promotion, DocumentAssembly freeze, and review-queue acceptance (the acceptance leg of promotion — its case evaluates whether the original route-to-review reasons are actually resolved). Drafts and notes never generate cases.

**Review:** farmer self-review for routine claims meeting the floor (the deliberate "confirm & accept" step). Exceptions — unresolved binding, implausible dose, dispute, post-sync discrepancy, late evidence — route to the advisor queue. Self-review is sufficient for record-keeping use, insufficient for certification-grade claims. Software-agent review: Phase-2 candidate, not in this profile version.

**Advisory rule:** authorisation-mismatch and dose-range warnings are `advisory output` commit-class records (Advisory twin). They never block, never auto-create compliance facts, and are never silently dropped from farmer view.

> **Implementation status (M2 P5, partial — ERRATA E-006):** P5 raises authorisation-mismatch and dose-range as **non-blocking `WARNING` warnings on the operation-claim commit result** (computed from this policy's `advisories` rules; never blocking, never a compliance fact, never an accepted consequence). The **durable** Advisory-twin *record* (a trace-safe `advisory output` surfaced in the passport `_advisory_flags`) is **not yet implemented** — emitting it inside the operation-claim commit needs a second `PromotionTrace` (the reachability invariant has no advisory slot) plus an advisory reason-code family. Durable advisory emission is a recorded follow-up.

## Runtime descriptor

- `runtime_profile_descriptor.json` — profile-local runtime descriptor consumed
  by `kernel.profile_runtime`; not a canonical contract, not OFARM Core law, and
  not tenant or deployment binding.

## Test harness

- `tests/profile_test_harness.json` — profile-local engineering-test harness.
  It now owns the SI adapter/import, policy metadata, and binding wrapper test
  modules through root collection bridges, writes no evidence, and is not
  platform MVP conformance.
- `tests/m2_si_binding_fixtures.py` — profile-local fictional fixture builders
  used by the root-owned SI binding tests; this is fixture support, not a moved
  test module or conformance evidence.

## Shipped instances (validated by `../conformance/ofarm_pkg_contract_check.py`)

- `OFARM_PackActivationSet_example_si_ffs_pilot_v0_1.json` — static single-profile activation (no overlap → no merge trace needed)
- `OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json` — pilot artifact state; **regenerated at M1** against the real artifacts (views, manifest, snapshots)
- `OFARM_ContextSnapshot_example_si_ffs_pilot_compliance_v0_1.json` — demo-tenant Compliance-twin context spine; runtime generates per-farm snapshots referencing the same activation/artifact sets
- `OFARM_AgronomicCodeBindingProfile_si_ffs_v0_1.json` (`codebindingprofile:si.ffs.v0_1`) — cut at M0 from verified registry facts (REGSR lookup surface, no-official-export posture, weekly-parse cadence); ACTIVE within the pilot pack
- `OFARM_ReferenceSnapshot_example_si_uvhvvr_ffs_reg_2026-06-11.json` — first real REGSR snapshot (623 products parsed)
- `OFARM_ReferenceSnapshot_example_si_gerk_layer_2025-06-30.json` — national GERK open-data layer vintage
- `OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json` (`manifest:si.ffs.pilot.v0_1`) — generated at M1 from the actual runtime surfaces; conformance level deliberately `NONE`; unsupported-surface posture in `UNSUPPORTED_SURFACES.md`
- `views/` — SI pilot view specification plus the four authored QuerySpecification/QueryPlanIR artifacts

## Deferred instances

None remain — every instance deferred at package cut shipped by M1 (2026-06-12; the
code-binding profile and both reference snapshots at M0 close, the Capability Manifest at
M1). Earlier revisions of this section listed the code-binding profile as deferred after it
had already shipped — recorded in `../ERRATA.md` alongside E-002's currentness sweep.

## Reserved identifiers

`pack:si.ffs.pilot.v0_1` · `profile:si.ffs.recordkeeping.v0_1` · `policy:si.ffs.evidence-review.v0_1` · `codebindingprofile:si.ffs.v0_1` · `manifest:si.ffs.pilot.v0_1` · `view:si.ffs.spray-register.passportview.v0_1` · `view:si.ffs.inspection-register.documentassembly.v0_1` · `registry:ofarm2-implementation-package.v0_1` · `tenant:si.ffs.pilot.demo`
