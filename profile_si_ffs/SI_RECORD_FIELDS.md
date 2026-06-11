# SI record fields — verified normative basis for the capture form

Status: verified field specification (M0 closure item). Sources: verbatim extracts in `source_packet_extracts/` (EUR-Lex OJ captures + PISRS consolidated ZFfS-1 NPB2), packet `slovenia_ffs_gerk_eu_recordkeeping_packet_2026-06-12`, canonical copy in `06_active_supporting_research/source_inputs/working_extracts/`. Not legal advice.

## A. EU Annex — Reg. (EU) 2023/564, verbatim column set

Records are kept **per use**, electronically, machine-readable (Dir. 2019/1024 Art. 2(13) definition), recorded **without undue delay**, transferred to electronic form **≤ 30 days**; per Reg. (EU) 2025/2203 (Art. 1), member states **may allow** that records of uses **before 1 Jan 2027** are not transferred into the prescribed electronic format.

Seven columns × three use types:

| Column | Surface areas (fields, amenity, railways, non-crop) | Closed spaces (stores, empty grain rooms, permanent greenhouses) | Seeds / plant reproductive material |
|---|---|---|---|
| Type of use | (this row) | (this row) | (this row) |
| Product | **Name + authorisation number** | same | same |
| Time | **Date + start hour where relevant** (fn 4) | Date | Date |
| Dose | kg or l **per hectare** (fn 1: units adjustable) | kg/l per m³ or m² | kg/l per kg, tonne, or seed count (fn 9) |
| Location / identification | **IACS geo-spatial aid-application unit where available** (Reg. 2022/1173 Art. 8(3)(b)) — in Slovenia: **GERK**; else the Art. 1(2) identification method. **Fn 2: indicate the fraction of the unit treated, if appropriate** | store/greenhouse number + Art. 1(2) method | Art. 1(2) method |
| Size / amount treated | hectares (fn 3: units adjustable) | m³ or m² (fn 8: multi-layer = total area) | kg, tonnes, or seed count |
| Crop / situation | **EPPO codes** where applicable + **BBCH stage where relevant** (fn 7) | EPPO codes + BBCH where relevant | EPPO codes + **batch number where applicable** |

Model mapping notes: fn 2 (*fraction of unit*) is contract-realized by `PartialExtent`; the IACS-unit preference makes GERK-bound `Field` identities the legally preferred location identification; BBCH "where relevant" enters via `AgronomicObservationContext`/payload stage fields, not as a universally required input.

## B. Slovenian additions — ZFfS-1 (consolidated NPB2), verbatim grounding

- **Art. 19(1):** the professional user ensures traceability of each FFS *from purchase to use* by entering use data **directly into the state FFS-use record (Art. 44.b)** — noted start date **01.01.2026** (EU rules may provide otherwise; see 2025/2203 cushion above).
- **Art. 19(3):** retention **≥ 3 years** from purchase/treatment (44.b(4): three years after the year of use).
- **Art. 44.b(3): national additions on top of the EU Annex:**
  1. personal name and address of the professional user;
  2. **KMG-MID** or tax number of the legal person;
  3. **FFS training-card number** of the professional user (izkaznica, from the Art. 45 training register).
- **Art. 44.b(5):** UVHVVR must give professional users **access** to the state use-record (portal/interface posture: outreach Q2).
- **Art. 44.a (purchase register):** sellers record every sale to a professional user (buyer, KMG-MID/tax no., training-card no., trade name, quantity, purchase date). *Phase-2 opportunity: purchase-driven product-picker pre-population once user-side access is clarified.*
- **Art. 42 (product register):** legally defined register content — holder, trade name, FFS type, active substances + quantities, registered uses, **decision number + type, issue + validity dates**; retention 10 years past lapse. This is the legal column basis for the REGSR `ReferenceSnapshot` schema.

## C. Equipment register (FFSNaprave) — verified machine-readable

Official downloads per year (2001→2026): **TXT (semicolon-delimited, quoted headers), XLS, XML + XSD**, plus an official field-description PDF (20 fields: `NapravaID`, `StatusNaprave`, `SkladnostNaprave`, sticker number `StevilkaZnaka` + validity `VeljavnostZnaka`, last inspection, device type/manufacturer/year/model/serial, owner municipality, inspection rows…). Adapter = trivial delimited import; a farm's sprayer matches by the **sticker number physically on the machine**, yielding inspection-validity evidence for the spray record's equipment field.

## D. Capture-form consequences (binding for M3 UI)

1. Pilot v1 implements the **surface-areas row only**; closed-space and seed-treatment record types are declared unsupported in the Capability Manifest (law allows adding them later without model change).
2. New auto-filled fields from the operator's `Party` record: name + address; KMG-MID (farm); **training-card number** (`registeredIdentifiers`, scheme `SI:FFS-IZKAZNICA`) — captured once at onboarding, never typed per record.
3. "Start hour where relevant" = optional time field, defaulted, surfaced when the product's authorisation carries time-of-day restrictions (snapshot data).
4. Dose units: per-hectare default with UCUM codes; fn 1 unit adjustability is honored by the quantity model, not by free text.
