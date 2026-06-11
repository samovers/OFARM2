# M0 desk research — Slovenia FFS pilot (2026-06-11)

Status: desk-research findings feeding `PROFILE.md` and `PILOT_SI.md`. Each finding carries a confidence label:
**VERIFIED-DESK** = consistent across multiple official-source search results; **TO-VERIFY** = needs human confirmation (call/email/manual site visit) before the profile instance is cut. Government and EUR-Lex pages block automated fetching from this environment, so verbatim legal text remains a human task.

## 1. EU layer — Regulation (EU) 2023/564

- **VERIFIED-DESK** Applies from **1 January 2026**; professional users must keep PPP-use records **electronically in a machine-readable format** (as defined in Art. 2(13) of Directive (EU) 2019/1024).
- **VERIFIED-DESK** Recording must happen **without undue delay**; records not initially created electronically must be transferred into the electronic format **within 30 days** of the use.
- **VERIFIED-DESK** Base record content (from Reg. 1107/2009 Art. 67): **product name, time of application, dose, area treated, crop**.
- **VERIFIED-DESK** 2023/564 Annex adds, for records from 2026: **product registration/authorisation number**, **crop name per EPPO code**, **spatial data of the treated area**, and **type of use** — one of: land treatment (e.g. agricultural, railway, forest); treatment in enclosed spaces (e.g. empty silos, permanent greenhouses); treatment of seeds/propagating material.
- **VERIFIED-DESK** **Regulation (EU) 2025/2203** softened the transition: records of uses up to **31 Dec 2026** may be kept without conversion to the required electronic format, with transition until **1 Jan 2027**. Member states may postpone electronic record-keeping introduction to 2027 (Finland has announced it will).
- **TO-VERIFY** The verbatim, complete Annex field list and the exact phasing dates of later waves (BBCH growth stage, equipment identification — believed 2027+). Source: EUR-Lex CELEX:32023R0564 (blocked to bots; read manually).
- Noted for later, not M0: **Regulation (EU) 2026/1123** (26 May 2026) introduces **digital labels** for PPPs (all labels digital by 1 Jan 2030, repealing 547/2011) — a future label-evidence source for the platform, not a record-keeping rule.

## 2. Slovenian layer — ZFfS-1 (as amended by ZFfS-1A, Ur. l. 2024)

- **VERIFIED-DESK** Slovenia is building a **central electronic FFS-use registry ("IS Evidenca FFS")**, maintained and managed by **UVHVVR**, for monitoring/analysis/supervision and statistics. Professional users (Art. 19 ZFfS-1) enter data per Articles 2–3 of 2023/564; record content = the **EU Annex plus nationally prescribed additions**.
- **VERIFIED-DESK** Timeline per the ZFfS-1A amendment: central registry to be established by **1 December 2026**; professional users must **first enter their (previous-year) use data by 31 January 2027**.
- **VERIFIED-DESK** The current official Slovenian record form is keyed by **KMG-MID** ("PRILOGA 1: Podatki o uporabi FFS v kmetijski pridelavi, KMG-MID: …", gov.si/UVHVVR). KGZS/SKP publish simplified record templates; rule: one line per FFS (or low-risk method) with all columns filled.
- **TO-VERIFY** (a) The exact national additions beyond the EU Annex (read ZFfS-1A text on PISRS); (b) whether Slovenia exercises the 2027 postponement for user-side electronic format; (c) **whether IS Evidenca FFS will expose a submission interface (API/file upload) for third-party apps** — a public tender for the system exists, so the procurement docs likely answer this. This question decides whether the pilot's frozen register export can become a direct `SubmissionAssembly` feed.

**Consequence for the pilot:** the value proposition strengthens. The farmer needs (1) a compliant electronic record from day one and (2) a way to submit the year's data to the state registry by 31 Jan 2027. The pilot's DocumentAssembly export is positioned to become exactly that submission artifact.

## 3. Product register — correction to the package

- **VERIFIED-DESK** **FITO-INFO has been shut down** and redirects to current GOV.SI records and registers. The live official register of authorized PPPs in Slovenia is the **UVHVVR "Seznam registriranih FFS" application** at `spletni2.furs.gov.si/FFS/REGSR/` (per-product pages with stable record numbers, e.g. `FFS_descr.asp?RecNr=…`; includes a distributor register).
- `PROFILE.md` updated accordingly: the binding scheme is now **SI:UVHVVR-FFS-REG** (was "FITO-INFO"). This is the exact class of error M0 exists to catch before the profile instance is cut.
- **TO-VERIFY** REGSR export mechanics: whether the app offers Excel/CSV export, its update cadence, and identifier stability across updates; whether any OPSI (podatki.gov.si) dataset mirrors the register. (OPSI currently lists adjacent FFS datasets, e.g. producers/importers; a register-of-products dataset was not confirmed from search results.)
- **VERIFIED-DESK** A **sprayer-inspection data download surface exists**: `spletni2.furs.gov.si/FFS/FFSNaprave/` ("Prevzem podatkov o pregledih naprav za nanašanje FFS") — directly useful for Equipment identity + inspection `EvidenceRecord`s. **TO-VERIFY** format and access terms.

## 4. Parcels — better than planned

- **VERIFIED-DESK** The **entire national GERK layer is open data**: shapefile download + WMS via the MKGP public viewer (`rkg.gov.si/GERK/WebViewer/`) and the OPSI dataset "Identifikacijski sistem za zemljišča (Blok/GERK)". Data reflects GERK state at the last collective subsidy application.
- **VERIFIED-DESK** Farmers access their own holding data through **eRKG** (official user manual on rkg.gov.si); the KMG↔GERK linkage is personal data, so the farmer supplies their KMG-MID and confirms their GERK list.
- **Onboarding design consequence:** the app ships/syncs the open GERK layer; onboarding = farmer enters KMG-MID, picks/confirms their GERKs (from their eRKG view or subsidy paperwork), geometry and areas come from the open layer. No per-farmer government export needed. `CAPTURE_MAPPING.md`'s "farmer-provided exports" fallback remains as fallback only.

## 4a. Human-verified findings (2026-06-11, steward browser session + real documents)

**Register (REGSR) — VERIFIED-HUMAN:**
- **No export endpoint exists.** Checked: main frameset, thematic list pages, full HTML list (`FFS_RegSezn.asp?top=1`), and all linked ASP pages for CSV/Excel/XML/JSON/TXT/MDB/DBF/ODS/izvoz/prenesi variants. Closest machine surface: the **full HTML list page**, parseable into structured rows.
- **Snapshot method decided:** scripted parse of the official HTML pages on a weekly cadence → `ReferenceSnapshot`. Declared honestly in the profile as an *unofficial surface over official content*: the `ExternalRegistryVerificationTrace.lookupSurface` records the HTML page; discrepancy risk is declared, not hidden. (UVHVVR outreach Q1 may still surface an official feed — if so, the adapter switches.)
- **Product detail pages are richer than the Belgium research assumed for Slovenia.** Verified field inventory from a live product page: product name; active substance table (name, %, customs group, CAS, **MoA/IRAC code**); formulation; GHS hazard group + signal word; use category (e.g. INSEKTICID); manufacturer; distributor(s); parallel-import field; validity date; **authorized crops as EPPO codes with use context** (e.g. `HORVX` ječmen, *tretiranje zrnja*); **target organisms as EPPO codes**; hazard/precaution phrases (EUH/H/P/SP); **karenca per crop**; linked subpages for **doses per use ("Uporabe in koncentracije"), surface-water buffer zones, and MRLs**; and a decisions table with **Številka odločbe** (e.g. format `U#####-##/##/##`), issue date, validity date.
- **Binding-key decision:** primary external key = **Številka odločbe** (registration decision number) + validity dates; the app-local page record number (`RecNr`) is a locator only, never identity. The native EPPO coding of crops and targets means the **authorisation-mismatch advisory check can run directly from the snapshot** — no extra mapping layer.

**RKG izpis — VERIFIED-HUMAN:** one real farm extract examined; structure, identifier formats (KMG-MID 9-digit, GERK-PID 7-digit, BLOK-ID), ha.a.m² area format, *domače ime* field names, vrsta-rabe codes, and the family-member/delegation reality are documented (anonymized) in `ONBOARDING_RKG_IZPIS.md`. Personal data excluded from the repository by rule. Legal-basis note: the extract cites **ZKme-2 (Ur. l. RS 100/25)** — the new agriculture act — as RKG's basis.

## 5. Updated M0 human checklist (what remains after desk research)

1. ~~Check REGSR for export~~ **DONE 2026-06-11** — no export; HTML-parse surface chosen; product-page field inventory captured (§4a).
2. ~~Obtain one real farm's parcel basis~~ **DONE 2026-06-11** — RKG izpis examined; structure + identifiers documented anonymized (`ONBOARDING_RKG_IZPIS.md`).
3. ~~Register HTML + parser~~ **DONE 2026-06-12** — steward uploaded the saved list page (623 products) and one detail page; `tooling/regsr_snapshot/parse_regsr.py` built and validated against them (zero row problems; register-day stamp, EPPO crops/targets, decision numbers extracted). First parsed snapshot: `examples/regsr_snapshot_2026-06-12.json`. Note: the register page **self-declares as unofficial/informational** — the legal record is the odločba; the snapshot and verification traces disclose the lookup surface accordingly.
4. **DEFERRED to 2027 (steward decision, 2026-06-12)** — UVHVVR outreach: official feed? IS Evidenca FFS submission interface? 2025/2203 transition choice? Interim posture: watch for published IS Evidenca FFS specs (the system is under public procurement); HTML-parse snapshot method stands. Drafts remain ready in `OUTREACH_DRAFTS.md`.
5. ~~Law transcription~~ **DONE 2026-06-12** via source packet (`source_packet_extracts/`, canonical copy in `06_active_supporting_research/source_inputs/working_extracts/`): 2023/564 Annex verbatim, 2025/2203 Art. 1 verbatim, ZFfS-1 Arts. 16/19/42/43/44/44.a/44.b/45 verbatim. Normative field spec: `SI_RECORD_FIELDS.md`. *(Note: 2025/2203 confirms member states **may allow** non-electronic records for pre-2027 uses — Slovenia's choice remains outreach Q3.)*
6. **DEFERRED to 2027 (steward decision, 2026-06-12)** — KGZS advisor + 3–5 farms. Consequences accepted and recorded: the live pilot (M4) moves to the 2027 season (aligned with the 2025/2203 transition end and the 31 Jan 2027 first state-registry entry); M1–M3 build proceeds without farms; **the self-review policy and inspector-facing outputs remain externally unvalidated until the 2027 outreach — treat that outreach as non-negotiable.** Advisor-queue flows are built but exercised with synthetic actors until then.
7. ~~GERK open-data round-trip~~ **DONE 2026-06-12, report retained** — executed by the steward with a local standard-library equivalent of the package tool against `GERK_RKG_30jun_2025` (.dbf from the OPSI Blok/GERK archive): **856,677 records scanned, 0 deleted; 4/4 farm PIDs found, 1 record each, 0 duplicates; all attributes populated.** PID field auto-detect target confirmed (`GERK_PID`). Three design facts from the report:
   - **Layer attribute set is minimal:** `GERK_PID, RABA_ID, AREA, OPIS_RABE, ENGLISH` — **no domače ime, no BLOK-ID, no NUP/GrPov split** in the open layer. Farmer field names and BLOK/NUP detail come from the farmer/izpis at onboarding; the layer supplies existence, geometry, area, and use code. (Onboarding design already assumed this; now it's evidence.)
   - **Layer vintage is yearly** (this archive: 2025-06-30, reflecting the last collective application) — it can lag a fresh izpis. Onboarding records the layer vintage as a `ReferenceSnapshot`; izpis-vs-layer discrepancies route to review with the izpis as the fresher farm-side evidence.
   - `RABA_ID` in the layer matches the izpis vrsta-rabe code family → crop-cycle defaults can come from either source.
8. ~~FFSNaprave~~ **DONE 2026-06-12** — official yearly TXT/XLS/XML+XSD downloads verified with field-description PDF; samples + XSD in the packet; adapter = delimited import; equipment matches by sticker number.
9. ~~Profile instance~~ **DONE 2026-06-12** — `OFARM_AgronomicCodeBindingProfile_si_ffs_v0_1.json` cut from verified facts and schema-validated; first real `ReferenceSnapshot` instance cut from the parsed register; `ActiveArtifactSet`/`ContextSnapshot` examples regenerated.

---

## M0 STATUS: **CLOSED 2026-06-12**

Closed with two deliberate deferrals (items 4 and 6 → 2027 outreach, consequences recorded above). Everything the build needs is verified and in-package: the legal field basis, the register snapshot pipeline, the parcel onboarding path, the equipment-evidence source, and the cut profile instance. **Next: M1 — Kernel store, gate pipeline, materializer, against `conformance/CONFORMANCE.md`.**

**Source packet provenance:** `slovenia_ffs_gerk_eu_recordkeeping_packet_2026-06-12` (sha256 manifest included), generated by the steward's local agent 2026-06-11; curated copy (large samples excluded by checksum reference) at `06_active_supporting_research/source_inputs/working_extracts/`; key verbatim extracts mirrored in `profile_si_ffs/source_packet_extracts/`.

## Sources (search-result evidence; fetches blocked from this environment)

- EUR-Lex: [Reg. 2023/564](https://eur-lex.europa.eu/eli/reg_impl/2023/564/oj/eng) · [CELEX PDF](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32023R0564) · [Reg. 2026/1123 (digital labels)](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ%3AL_202601123)
- [Tukes: amendments to PPP record-keeping](https://tukes.fi/en/-/amendments-to-the-record-keeping-requirements-for-the-use-of-plant-protection-products) · [DAERA grace period](https://www.daera-ni.gov.uk/news/grace-period-transition-mandatory-digital-record-keeping-plant-protection-products)
- Slovenia: [ZFfS-1 (PISRS)](https://pisrs.si/pregledPredpisa?id=ZAKO6355) · [ZFfS-1A amendment (Uradni list 2024)](https://www.uradni-list.si/glasilo-uradni-list-rs/vsebina/2024-01-2874/) · [UVHVVR record form PRILOGA 1 (gov.si)](https://www.gov.si/assets/organi-v-sestavi/UVHVVR/FFS/Trajnostna-raba-FFS/podatki-o-uporabi-FFS.pdf) · [SKP.si Evidenca FFS](https://skp.si/wp-content/uploads/2025/03/Evidenca-FFS.pdf) · [eUprava draft-regulation record](https://e-uprava.gov.si/si/drzava-in-druzba/e-demokracija/predlogi-predpisov/predlog-predpisa.html?id=16127)
- Registers: [UVHVVR Seznam FFS (REGSR)](https://spletni2.furs.gov.si/FFS/REGSR/) · [FITO-INFO shutdown notice](http://www.fito-info.si/) · [Sprayer-inspection data download](https://spletni2.furs.gov.si/FFS/FFSNaprave/)
- Parcels: [OPSI Blok/GERK dataset](https://podatki.gov.si/dataset/identifikacijski-sistem-za-zemljisca-blok-gerk) · [eRKG user manual](https://rkg.gov.si/GERK/eRKG/docs/UporabniskaNavodila_eRKG.pdf) · [MKGP public viewer resource](https://podatki.gov.si/dataset/identifikacijski-sistema-za-zemljisca-blok-gerk/resource/b9b0d055-b274-42e1-a891-c1d45e95269c)
