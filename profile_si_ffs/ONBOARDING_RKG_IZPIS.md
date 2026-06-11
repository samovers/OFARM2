# Farm onboarding from the RKG izpis (M0 human-verified)

Source: one real "Izpis iz registra kmetijskih gospodarstev" (RKG extract, ZKme-2 legal basis, Ur. l. RS 100/25), examined privately by the steward during M0.
**Privacy rule (absolute):** the document itself and **all** values from it — identifiers, names, dates, places, areas, field names — stay outside the repository, its history, and all derived bundles. Everything below is **fictional placeholder data preserving only the format**. The original is retained by the farm; in the app it becomes an `EvidenceRecord` (DOCUMENT) held under the farm's own scope and is never committed to any shared repository.

## Document structure (what the app can parse or transcribe)

```
Header:        case number, date, issuing ministry, legal basis
Title:         IZPIS IZ REGISTRA KMETIJSKIH GOSPODARSTEV za KMG-MID <9 digits>
Session:       številka sestanka, datum in čas izpisa
Holding:       KMG-MID; domače ime + naslov; upravna enota; OMD classification
               (areas + %, points/ha); dopolnilne dejavnosti flag; standardni
               prihodek EUR + economic size class + main farming type
Holder:        name, birth date, address, phone        [PERSONAL — never stored in repo]
Family:        members with birth dates                [PERSONAL — never stored in repo]
Land:          BLOK-ID groups, each with GERK rows:
               GERK-PID | Domače ime | Vrsta rabe code | NUP (ha.a.m2) | GrPov (ha.a.m2) | change date
Legend:        full vrsta-rabe code list (1100 njiva, 1211 vinograd, 1221/1222 sadovnjak,
               1230 oljčnik, 1300 trajni travnik, 1190 rastlinjak, …)
Totals:        per vrsta-rabe sums
```

## Design consequences (bound into the pilot)

1. **Farmers name their fields — use those names.** Every GERK row carries a *domače ime* (a local field name like "Spodnja njiva"). `FieldIdentityPayload.displayName` = the domače ime; the GERK-PID is the binding, not the label the farmer sees. The capture screen's parcel picker shows the farmer's own names.
2. **Identifiers:** `parcelIdentifiers = [{scheme: "SI:GERK-PID", value}, {scheme: "SI:BLOK-ID", value}]`; holding = `{scheme: "SI:KMG-MID", value}` (9-digit). GERK-PID observed as 7-digit; BLOK-ID 8-digit.
3. **Area format is ha.a.m²** ("0.43.21" = 0 ha 43 a 21 m² = 4 321 m²). The importer must convert; `declaredArea` uses **NUP** (largest eligible area) with GrPov retained in the payload notes when they differ.
4. **Vrsta rabe drives crop-cycle defaults:** 1211 → grapevine cycle suggested; 1221/1222 → orchard; 1100 → annual crop chosen at first record. This makes `CropCycleIdentityPayload.autoCreated` concrete.
5. **The izpis itself is onboarding evidence:** scanned/photographed → `EvidenceRecord` (DOCUMENT, sha256) → referenced by the structure assertions that create Farm + Field identities — held farm-side, never in shared repositories. Inspector-grade provenance for "where did these parcels come from" at zero extra farmer effort.
6. **Family members are the real operators.** The examined holding matches the target persona: a small specialized holding with an older holder and adult family members doing the work. Family members become `Party` records with `RoleAssignment` (family worker) and act via `DelegationGrant` — the kernel decision to include delegation is validated by the very first real document examined.
7. The izpis warns it is **not reissued on every change** (annual reconciliation, satellite-monitoring updates via SOPOTNIK, minor zbirna-vloga corrections) — so onboarding records the izpis date as the parcel snapshot basis, and the open-data GERK layer (see `M0_DESK_RESEARCH.md` §4) provides the refresh path.

## Fictional onboarding example (format-true, every value invented)

```json
{
  "holding": {"scheme": "SI:KMG-MID", "value": "100000001",
               "domaceIme": "PRIMER", "upravnaEnota": "VZOREC"},
  "parcels": [
    {"gerkPid": "1000001", "blokId": "20000001", "domaceIme": "ZA HIŠO",
     "vrstaRabe": "1211", "nup_m2": 4321, "grpov_m2": 4321, "changed": "2026-01-15"},
    {"gerkPid": "1000002", "blokId": "20000002", "domaceIme": "SPODNJA NJIVA",
     "vrstaRabe": "1300", "nup_m2": 6250, "grpov_m2": 6250, "changed": "2026-01-15"}
  ],
  "evidence": {"class": "DOCUMENT", "kind": "RKG_IZPIS", "issuedAt": "2026-01-15"}
}
```
