# Slovenia pilot: small-farm plant-protection record keeping

Status: pilot definition — not OFARM law, not legal advice.

## Claim scope (read this first)

The pilot's outputs claim **record-keeping completeness**:

> "This register faithfully and traceably reflects what the farm recorded, with gaps, disputes, and unresolved bindings visible."

The pilot does **not** claim current-compliance against the authorisation register. Authorisation status renders as **advisory context from a dated snapshot** — a warning that helps the farmer, never a compliance fact and never a silent block. Reason: the canonical research (`reference/research/`) found Slovenian public registry surfaces do not yet document the currentness mechanics (export files, change history, update cadence) that a high-consequence current-compliance claim requires; Belgium's Phytoweb profile is the reference pattern the SI profile must converge to before that claim is ever made. (Hostile-review finding F1.)

## Regulatory anchors (verify in M0 before building the capture form)

- Commission Implementing Regulation (EU) 2023/564: professional users keep plant-protection application records **electronically (machine-readable) from 1 January 2026**; recording without undue delay, electronic transfer within 30 days. 2026 record content: product name **and registration number**, time, dose, **crop per EPPO code**, **spatial data of the treated area**, **type of use**. Regulation (EU) 2025/2203 grants a transition: pre-2027 records need not be converted until 1 Jan 2027, and member states may postpone the electronic obligation to 2027. **M0 verifies the verbatim Annex list and Slovenia's transition choice.**
- Slovenian layer (ZFfS-1/ZFfS-1A): UVHVVR runs a **central electronic FFS-use registry (IS Evidenca FFS)** — established by **1 Dec 2026**, first mandatory farmer data entry **by 31 Jan 2027 for the 2026 year**; record content = EU Annex **plus national additions (M0 verifies)**. The pilot's frozen register export is positioned to become that submission.
- Identifiers: KMG-MID (holding), GERK (parcel). The **national GERK layer is open data** (shapefile + WMS); onboarding = farmer's KMG-MID + confirmed GERK list against the open layer.
- Product register: **UVHVVR "Seznam registriranih FFS"** (FITO-INFO is shut down — see `profile_si_ffs/M0_DESK_RESEARCH.md`). **M0 verifies export mechanics**; fallback is scripted/manual snapshots at the declared cadence. Sprayer-inspection data has its own download surface (equipment evidence).

## Review policy (the one-person-farm answer)

Every acceptance requires a `ReviewDecision` with a named decider — the contracts allow no exception. The pilot declares **policy-governed self-review for routine operation claims**:

- the farmer holds `REVIEW_ACCEPT` scoped to their own farm;
- the app's deliberate "confirm & accept" step **is** the review act;
- the gates still enforce the evidence floor mechanically (resolved product binding, plausible dose, valid parcel, sane times) — self-review cannot bypass them;
- exceptions (unresolved binding, implausible dose, dispute, late evidence after sync conflict) route to the advisor review queue;
- self-review is declared sufficient for record-keeping use and **insufficient for certification-grade claims** — that upgrade (second-party review) is exactly what a future certification pack adds.

Software-agent auto-review is the named Phase-2 candidate (the agent actorship contracts are already current-lane; review is not on the human-only default list). (Hostile-review finding F2.)

## Users and roles

3–5 farms + one KGZS advisor contact. Farmer (asserts + self-reviews), family worker / machine-ring contractor (acts via `DelegationGrant`), advisor (review queue, advisory outputs), inspector (read-only via `SharingGrant` — optional path; the primary inspection artifact is the exportable frozen DocumentAssembly the farmer hands over).

## The two demonstrations

1. **Compliance demo:** the inspection register is generated from governed records and **refuses to render a clean register the data doesn't support** — it shows what's missing instead. Enter once in the field, never re-enter for anyone.
2. **Advisory-twin demo:** product-not-authorised-for-crop (per the dated snapshot) raises an advisory flag — visible help, never a block, never a generated compliance fact. The constitutional wall, visible in a UI.

## Milestones

| Milestone | Duration | Definition of done |
|-----------|----------|--------------------|
| **M0 — grounding** | 2–3 wks | EU 2023/564 Annex fields + SI rules verified with UVHVVR guidance; FITO-INFO access path established (or fallback declared); GERK data path confirmed; 3–5 farms + 1 advisor recruited; SI `AgronomicCodeBindingProfile` instance drafted from verified facts. |
| **M1 — Kernel running** | 4–6 wks | Store + gates + materializer green against `conformance/`; static view artifacts (QuerySpec + QueryPlanIR) authored per `views/VIEWS.md`; Capability Manifest instance generated; a second person builds a client from this package alone. |
| **M2 — Core on Kernel** | 3–4 wks | Identities, registry snapshots, GERK onboarding, code bindings enforced; `ActiveArtifactSet` regenerated against real artifacts. |
| **M3 — the app** | 4–6 wks | Offline capture → sync → review → materialized register, end to end on a real phone on a real farm; ≤ 90 s per record. |
| **M4 — pilot** | rest of season | Late-season 2026 shadow trial (orchards/vineyards/vegetables); full-season validation 2027. Done = advisor or inspector confirms the generated register meets the record-keeping obligation. |

## Success / kill criteria

**Success:** farmers enter records in the field without paper backup; the register export is accepted in at least one real advisory/inspection interaction; zero silent acceptances in the gate log (every promotion has its trace).
**Pivot signals:** farmers won't enter data even at ≤ 90 s (capture UX or value problem — fix before adding anything); no lawful machine or manual path to register data (escalate snapshot cadence honestly, never fake currentness).

## Law discipline during the pilot

The freeze holds. Implementation findings go to `ERRATA.md` only. One consolidated amendment after the pilot, written by reality.
