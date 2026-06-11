# OFARM 2 external code-binding currentness profile for crop-protection product authorisation

## Executive summary

Use date: **2026-05-14** in Europe/Ljubljana.

For the narrow OFARM amendment requested here, the best-supported jurisdiction is **Belgium**, not Slovenia. Slovenia does have official government pages for phytopharmaceutical product registration and an official register link, and the EPPO index still points to a Slovenian official list. However, the official Slovenian pages I could verify publicly expose much less explicit documentation about search semantics, export/currentness behaviour, identifier handling, and machine-readable access than Belgium’s official **Phytoweb** service. Belgium’s official source documents searchable authorisations, status filters, daily refresh behaviour, authorisation history, export to Excel, and a raw JSON data distribution with a published update cadence. That makes Belgium the clearer fit for an **OFARM currentness profile** where ReferenceSnapshot and verification traceability matter. citeturn1view1turn1view2turn6view0turn7view0turn7view1turn8view0turn9view0

The strongest design conclusion is simple: for **high-consequence crop-protection identity binding**, OFARM should treat the **jurisdictional product authorisation record** as the mandatory runtime/checking surface. In this report that means the Belgian Phytoweb authorisation record, with the authorisation number as the primary external binding key, and with label/certificate context captured in a snapshot. The **EU Pesticides Database** is useful, but only as an EU-level active-substance and emergency-authorisation lookup layer; the Commission explicitly says the database is **for information only**, has **no legal value**, and does **not** replace Member State product authorisation. citeturn36view0turn36view2turn36view3

Two fail-closed implications follow directly from the official sources. First, **free-text product name is not enough** for high-consequence binding, because Belgium explicitly allows cases in which **parallel products may share an identical trade name** with the Belgian reference product or with other parallel products. Second, a **commercial GTIN is not enough** either, because GS1 defines GTIN as a trade-item identifier, not a regulatory authorisation identifier; it can support commercial or packaging identity, but not prove that a product is currently authorised for Belgian use. citeturn15view2turn31search0turn31search2turn31search5

Accordingly, the narrow OFARM profile recommended here is: **Belgium crop-protection product authorisation / product identity profile**, using Phytoweb as the mandatory jurisdictional binding surface; EU pesticide resources as contextual semantic anchors; EPPO, BBCH, UCUM, and QUDT as controlled vocabularies and unit/quantity anchors; GS1 as commercial identity adjunct only; and CPVO/UPOV/OECD seed resources as denomination or attestation side-context, never as hidden product-authorisation law. This is an architecture recommendation, not legal advice. citeturn7view0turn7view1turn8view0turn9view0turn36view0turn36view2turn36view3turn18view0turn24view0turn26search0turn42view0turn31search0turn34view0turn35view0

## Jurisdictional source selection and source table

### Why Belgium is the selected jurisdiction

Slovenia remains a plausible future profile target. Official Slovenian government pages show that registration is handled by the competent authority, that a Slovenian register exists, and that only approved phytopharmaceutical products may be used in Slovenia. EPPO also still indexes a Slovenian official list. But the official Slovenian public material I could verify did not expose the kind of explicit currentness and export mechanics that OFARM needs for a narrow external currentness profile. Belgium’s official Phytoweb does. citeturn1view1turn1view2turn6view0turn7view0turn7view1turn8view0turn9view0

### Source table

| Source | Type | Responsible authority | Jurisdiction | Access and currentness behaviour | What it covers | Practical OFARM use | Main limitations |
|---|---|---|---|---|---|---|---|
| **Slovenia SPOT / gov.si registration page and FFS register link** | Law-and-process portal plus registry pointer | Government of Slovenia; registration page names the competent authority and points to the Slovenian FFS register | Slovenia | Public web pages; registry linked from SPOT; page shows last modification date; customs page states only approved FFS may be used in Slovenia | Registration process, legal basis, link to Slovenian FFS register, national use requirement | Useful as evidence that an official Slovenian source exists, but not strong enough here as the currentness profile base | Publicly verified pages did not document search/export/update semantics to the same degree as Belgium in the material reviewed | citeturn1view1turn1view2turn6view0 |
| **Phytoweb consult authorisations** | Official jurisdictional registry and runtime surface | Belgian **FPS Health, Food Chain Safety and Environment**; Phytoweb states it is an official website of that authority | Belgium | Public web search; search by name, authorisation number, crop, enemy; status filters; Excel export; lists refreshed daily; profile pages include authorisation history | Authorised plant protection products, authorisation statuses, crops, enemies/pests, holders, dates, profile history | **Primary OFARM runtime surface and code-binding source** for Belgian product authorisation | JavaScript-backed public interface; not a formal public API page; history visibility has limits for some withdrawn records | citeturn7view0turn8view0turn9view0 |
| **Phytoweb raw authorisation data service** | Official file-based registry export | Belgian **FPS Health, Food Chain Safety and Environment** | Belgium | JSON raw data; monthly full export on first day of month; daily change files; suspension file when relevant; access via registration and FTP; CC BY 4.0; foreign access requires specific IP handling | Non-confidential authorisation data for third-party implementation | Best source for **ReferenceSnapshot canonical artefact references** where a file-based snapshot is available | FTP access is controlled and geographically constrained; not an open anonymous API | citeturn7view1 |
| **Phytoweb label / authorisation certificate guidance** | Regulatory implementation guidance tied to authorisations | Belgian **FPS Health, Food Chain Safety and Environment** | Belgium | Public web guidance | Certificate-to-label correspondence, label adaptation deadlines, packaging listed on authorisation, application technique on label from 2025 | Important for **label-checked** and **packaging-checked** snapshot fields | Guidance, not the authorisation record itself | citeturn15view0turn15view1 |
| **EU Pesticides Database** | EU-level lookup database | European Commission, DG SANTE | EU | Public search; links to downloads/APIs; latest updates pages for active substances; includes active substances, MRLs, emergency authorisations | EU active-substance status, MRLs, emergency authorisations from June 2016 onward | **Semantic anchor / runtime lookup** for active-substance context and emergency-authorisation context | Commission states database is **informational only**, has **no legal value**, and official information is in the Official Journal; cannot replace national product authorisation | citeturn36view0turn36view4 |
| **Commission PPP approval and authorisation pages** | Primary regulatory context | European Commission, DG SANTE | EU | Public web pages | EU-level approval of active substances; Member State authorisation of products; emergency-authorisation context | Establishes the split between EU active-substance approval and Member State product authorisation | Not itself a national product register | citeturn36view1turn36view2turn36view3 |

### Selected jurisdiction source findings for Belgium

Belgium’s official registry is strong enough for an OFARM high-consequence binding profile because its official documentation says the registry can be searched by **name, authorisation number, crop, enemy**, and several filters including **status**, **authorisation type**, **nature**, **formulation type**, and user category. The same guidance says the list pages are **refreshed daily**, the results can be **exported to Excel**, and profile pages expose **authorisation history**, including modifications after 1 December 2020. citeturn8view0turn9view0

Belgium also publishes an official raw-data route that is unusually useful for OFARM: **monthly full JSON exports**, **daily change files**, and, when applicable, a **suspensions file**, all under **CC BY 4.0**. That is exactly the sort of official artefact surface that supports a strong `ReferenceSnapshot` / `ExternalRegistryVerificationTrace` pair without turning the external registry into “hidden OFARM law.” OFARM can snapshot the external artefact while still governing its own truth model internally. citeturn7view1

Product name alone is officially unsafe as a high-consequence key in Belgium. The parallel-trade guidance says a parallel product may have the **same trade name** as the Belgian reference product, and different parallel products based on the same reference product may also share an identical trade name. That means trade name is useful evidence, but not a sufficient binding key. The authorisation number must therefore be treated as the primary jurisdictional binding identifier in this profile. citeturn15view2

The Belgian official materials also make clear that the authorisation record contains or governs more than a mere product label. Phytoweb guidance refers to **authorisation holders**, **crops**, **pests**, **relevant dates**, **conditions of use**, **risk mitigation**, **packaging listed on the authorisation**, and the requirement that the market label correspond with the authorisation certificate. This supports an OFARM stance that high-consequence compliance views must check more than just a product name and should capture both product identity and authorisation context. citeturn9view0turn14search2turn15view0turn15view1

## Scheme-role table

The roles below are **recommended OFARM roles**, not claims that the sources dictate OFARM semantics.

| Scheme or source | Category | Owner or issuer | Recommended OFARM role | Identifier or coding behaviour | Versioning and licensing behaviour | Best fit in OFARM |
|---|---|---|---|---|---|---|
| **Belgium Phytoweb authorisations** | Jurisdictional registry | Belgian FPS Health, Food Chain Safety and Environment | **RUNTIME_SURFACE** + **CODE_BINDING** | Search by authorisation number, name, crop, enemy; statuses and history are part of the official runtime surface | Daily-refreshed lists on web; raw JSON monthly full export plus daily changes; CC BY 4.0 for raw non-confidential data | **High-consequence compliance use** and current product identity binding | citeturn8view0turn9view0turn7view1 |
| **EU Pesticides Database** | EU regulatory lookup | European Commission, DG SANTE | **SEMANTIC_ANCHOR** + **RUNTIME_SURFACE** | Covers active substances, MRLs, and emergency authorisations; can identify only part of the product-regulatory chain | Latest-update pages exist; database links to downloads/APIs; but Commission says it is informational only and not legally authoritative | Active-substance context, emergency-authorisation context, cross-checking | citeturn36view0turn36view4turn36view2turn36view3 |
| **EPPO Codes / EPPO Global Database** | Standard vocabulary | EPPO | **SEMANTIC_ANCHOR** + **CODE_BINDING** | Codes are unique harmonised identifiers; plants usually use **5 letters**, pests/pathogens **6 letters**; non-taxonomic entities are also included | Continuously updated; monthly newsletter; freely downloadable under an open-data licence; requests for new taxonomic codes are fee-based | Crosswalk and controlled coding for crops, pests, weeds, diseases, target organisms, and PPP-use classification | citeturn18view0turn18view1 |
| **BBCH Scale** | Growth-stage coding publication | Julius Kühn Institute hosting BBCH publication series | **SEMANTIC_ANCHOR**; sometimes **CODE_BINDING** when the authorisation/label actually uses BBCH | Numeric crop-growth stages from the BBCH system; Belgian Phytoweb explicitly provides BBCH crop-code overviews | Publication-style source hosted by JKI; public PDF/e-paper access; no open-data licence stated on the reviewed JKI page | Advisory and evidence use generally; compliance-supporting only when the jurisdictional authorisation or label references BBCH | citeturn24view0turn20search0turn8view0 |
| **UCUM** | Unit code system | UCUM / Regenstrief Institute | **CODE_BINDING** | ASCII unit expressions with formally defined syntax; terminal symbol tables are fixed per revision and expressions are machine-verifiable | Current release artefacts documented as **version 2.2 (June 2024)**; licence page shows **version 1.1, June 2024** | **High-consequence unit coding** for dose, concentration, area-rate, volume-rate, mass, time | citeturn26search0turn26search1turn27search8 |
| **QUDT Quantity Kinds** | Semantic quantity vocabulary | QUDT.org | **SEMANTIC_ANCHOR** | Quantity-kind IRIs under `http://qudt.org/vocab/quantitykind/…`; schema defines quantity kind as a measurable observable property | Current quantity-kind vocabulary metadata shows **Version 3.2.1**, modified **2026-04-02**; unversioned URLs resolve to latest release; **CC BY 4.0** | Quantity-kind anchoring and crosswalks; not needed as the legal unit authority | citeturn42view0turn42view1turn42view2 |
| **CPVO Variety Finder** | Variety denomination and register aggregation | CPVO | **SEMANTIC_ANCHOR** + **EXCHANGE_MAPPING** | Search over registers from more than 70 countries; includes PBR, listings, trademarks, patents, and other registers | Updated “as soon as data are officially published” according to CPVO; public web access; API capability is referenced in CPVO material | Variety denomination context and register cross-checking; **not** a seed-lot or crop-protection product authorisation key | citeturn34view0turn34view1turn29search12 |
| **UPOV PLUTO and GENIE** | Variety denomination and taxon-code context | UPOV | **SEMANTIC_ANCHOR** | PLUTO is a denomination and plant-variety database; GENIE is the official repository of **UPOV Codes** for plant taxa | Public search; PLUTO offers denomination-similarity checks; UPOV databases are public information resources | Denomination context and species/taxon normalisation; **not** product authorisation | citeturn34view3turn34view4 |
| **OECD Seed Schemes** | Seed certification framework | OECD | **ATTESTATION_WRAPPER** | Scheme-level certification framework for varietal identity and purity; implemented through National Designated Authorities | OECD states seeds are officially controlled under harmonised procedures in participating countries; public rules, variety lists, and country/NDA lists | Seed certification attestation and evidence context; **not** crop-protection product compliance | citeturn35view0 |
| **GS1 GTIN / Digital Link** | Commercial identifier and web-linking standard | GS1 | **EXCHANGE_MAPPING** + **RUNTIME_SURFACE** for commercial lookup, but only **evidence-only** for compliance | GTIN uniquely identifies trade items; AI **01** identifies GTIN; GS1 AIs carry batch/lot, expiry and other attributes; Digital Link expresses GS1 identifiers in URIs | Standards are maintained through GS1’s reference directory; official standards are versioned there | Commercial product/pack identity, lot/expiry transport, resolver surface; **not** a regulatory authorisation key | citeturn31search0turn31search1turn31search2turn31search12 |
| **AGROVOC** | Agricultural vocabulary | FAO | **SEMANTIC_ANCHOR** | Controlled multilingual concept identifiers for agriculture; REST and SPARQL access are available | FAO-managed linked open data; public access and official APIs through AGROVOC/Skosmos | Crosswalks, indexing, multilingual labels; not compliance authority | citeturn32search0turn32search16turn32search24 |
| **Crop Ontology** | Trait and variable ontology | CGIAR-origin community resource, maintained via cropontology.org and the Alliance context | **SEMANTIC_ANCHOR** + **EXCHANGE_MAPPING** | Variables are modelled as trait + method + scale; official API exists; crop-specific ontologies expose stable ontology/term identifiers | Official API; site states **CC BY 4.0**; community-curated crop ontologies | Agronomic and phenotypic context; evidence and crosswalk use, not compliance authority | citeturn33search2turn33search3turn33search0 |

### EU-level product-regulatory context

The Commission’s pages draw a clear boundary that is important for OFARM. **Active substances** are approved at EU level, but **plant protection products themselves must be authorised in the EU country concerned**. The EU Pesticides Database can therefore support `AgronomicIdentityBinding` as a contextual active-substance anchor, but it cannot replace a Member State product authorisation binding where the compliance question is “was this product authorised here, at this time, for this use?” citeturn36view2turn36view3

## Snapshot and verification trace requirements

The field recommendations below are **OFARM design recommendations inferred from the official source behaviours**. The inference is necessary because the sources are mutable, date-sensitive, and in several cases status-bearing. citeturn7view1turn9view0turn15view0turn36view0turn36view3

### ReferenceSnapshot field recommendations

| Field | Recommendation | Why this should be mandatory for high-consequence Belgian crop-protection binding |
|---|---|---|
| `issuingAuthority` | Required | The registry is official only because it is issued by the Belgian FPS Health, Food Chain Safety and Environment; this must be explicit in the snapshot. citeturn7view0turn7view1 |
| `jurisdiction` | Required | Product authorisation is Member-State-specific; Commission pages say PPPs must be authorised in the EU country concerned. citeturn36view3 |
| `sourceName` | Required | Distinguish Phytoweb consult page, Phytoweb raw export, label/certificate guidance, EU database, and any annexed artefact. citeturn7view0turn7view1turn36view0 |
| `sourceClass` | Required | Mark whether the snapshot is from a jurisdictional registry, label/certificate artefact, EU-level semantic anchor, or commercial evidence source, so OFARM does not confuse registry law with adjunct evidence. citeturn36view0turn31search0 |
| `canonicalVersionLabel` | Required when exposed; otherwise explicit `notExposed` | Belgium raw-data service has monthly full exports and daily change files, so a captured export/file label is strong evidence; if using only the live web view, OFARM should record that no canonical release label was exposed in the captured source. citeturn7view1turn9view0 |
| `effectiveInterval` | Required | Belgian records are status- and date-sensitive; relevant dates and expiry behaviour matter for authorisation and use. citeturn9view0turn15view2 |
| `accessedAt` | Required | Currentness matters because Belgian lists refresh daily and raw data changes daily. citeturn7view1turn9view0 |
| `sourceArtifactReference` | Required | OFARM needs a stable pointer to the live record, exported file, annexed label, or certificate that was actually checked. citeturn7view1turn15view0turn15view1 |
| `lookupMethod` | Required | Distinguish web search, exported list, raw JSON file, certificate, or label review. That matters because different source surfaces have different evidentiary weight. citeturn8view0turn7view1turn14search6 |
| `identifierChecked` | Required | In Belgium, the authorisation number should be the primary checked identifier. Trade name should be secondary evidence only. citeturn8view0turn15view2 |
| `productNameChecked` | Required | The trade name used in the prescription or evidence should still be preserved, even though it is insufficient alone. citeturn8view0turn15view2 |
| `labelChecked` | Required for high consequence | Belgian guidance ties the market label to the authorisation certificate and sets label-update deadlines. citeturn15view0turn15view1 |
| `authorisationContextChecked` | Required | Record status, type, holder, crop/pest/use filters, relevant dates, and user category as checked context. citeturn9view0 |
| `activeSubstanceContextChecked` | Required | Belgium authorisations and EU active-substance approval are different layers; high-consequence views should record whether both were checked. citeturn7view0turn36view2turn36view3 |
| `verificationResult` | Required | Values should be explicit, for example `PASS`, `FAIL`, `REVIEW_REQUIRED`, `UNAVAILABLE`. citeturn7view1turn36view0 |
| `staleSupersededWithdrawnBehaviour` | Required | Belgium exposes withdrawn, selling-out and using-out states, and history; OFARM must preserve how those states were handled. citeturn9view0 |
| `confidenceOrReviewRequirement` | Required | Needed because some official sources are richer than others, and some live statuses or label/certificate checks may remain ambiguous. citeturn9view0turn36view0 |
| `unresolvedReason` | Required when not cleanly pass/fail | Lets OFARM preserve uncertainty without inventing current state. citeturn36view0turn15view2 |

### ExternalRegistryVerificationTrace field recommendations

| Field | Recommendation | Why it matters |
|---|---|---|
| `traceAuthority` | Required | Makes clear which external issuer was interrogated. citeturn7view0turn36view0 |
| `traceJurisdiction` | Required | Product legality is jurisdiction-bound. citeturn36view3 |
| `queryInputs` | Required | Preserve exactly what was used: authorisation number, trade name, crop, pest, holder, status filters. citeturn8view0turn9view0 |
| `lookupSurface` | Required | E.g. `phytoweb-live-search`, `phytoweb-json-export`, `eu-pesticides-active-substances`, `label-certificate-review`. citeturn7view1turn36view0 |
| `candidateCount` | Required | The trace needs to show whether the lookup returned one clean match or multiple candidates. That matters because trade names can collide. citeturn15view2 |
| `selectedExternalId` | Required | Usually the Belgian authorisation number or parallel-trade permit number, not merely a trade name. citeturn8view0turn15view2 |
| `selectionRationale` | Required | Record how ambiguity was resolved, especially when names or pack identities collide. citeturn15view2 |
| `statusObserved` | Required | Explicitly store authorised / selling out / using out / withdrawn / emergency / parallel trade / suspended as seen. citeturn9view0turn7view1 |
| `datesObserved` | Required | Relevant dates in the search result or profile page support currentness decisions. citeturn9view0turn15view2 |
| `historyObserved` | Required when used | Belgian profile pages expose authorisation history after 1 December 2020. citeturn9view0 |
| `labelCertificateCorrelated` | Required for high consequence | Because Belgian guidance binds the market label to the authorisation certificate. citeturn15view0turn15view1 |
| `activeSubstanceCrossCheck` | Required | Makes clear whether the EU-level active-substance layer was merely noted or actually compared. citeturn36view2turn36view3 |
| `snapshotRef` | Required | Bind the process trace to the ReferenceSnapshot used in evaluation. citeturn7view1 |
| `registryAvailability` | Required | A failed or unavailable registry lookup should be explicit rather than silently ignored. citeturn7view1turn36view0 |
| `discrepancies` | Required | Preserve mismatches between prescription, label, authorisation record, GTIN, or as-applied evidence. citeturn15view2turn31search0 |
| `finalOutcome` | Required | `PASS`, `FAIL`, `REVIEW_REQUIRED`, `UNVERIFIED_DUE_TO_SOURCE_UNAVAILABLE`, and similar controlled outcomes are preferable to silent nulls. citeturn36view0turn9view0 |

## Fail-closed rules

The table below is a recommendation for **high-consequence PassportView** materialisation. It does **not** say the underlying OFARM assertions should be deleted or denied; it says the current, high-consequence external-binding view should fail closed or require review when external authorisation evidence is not good enough.

| Situation | Recommended OFARM behaviour | Why |
|---|---|---|
| **Free-text product name only** | **Require review** by default; **refuse current-compliant PassportView** if no official authorisation-number match is supplied or verified | Belgium states that identical trade names can exist in parallel-trade contexts, so trade name alone is unsafe. citeturn15view2 |
| **Commercial GTIN only** | **Require review**; GTIN may be stored as auxiliary commercial evidence but must not drive compliance identity | GS1 defines GTIN as a trade-item identifier, not a regulatory authorisation key. citeturn31search0turn31search2turn31search5 |
| **Product name matches multiple registry entries** | **Fail closed** until a single authorisation number is resolved | Trade-name collisions are officially possible. citeturn15view2 |
| **Product authorisation expired, withdrawn, suspended, selling out, or using out** | For a **current-compliance view**, **fail closed or require review** depending on the exact downstream rule; for historical evidence, preserve the claim but do not materialise it as currently compliant without explicit temporal reconciliation | Official Belgian statuses are time-sensitive and materially alter whether a product is marketable or usable. citeturn9view0turn15view2 |
| **Active substance found but product authorisation missing** | **Fail closed** for compliance identity | EU active-substance approval does not replace Member State product authorisation. citeturn36view2turn36view3 |
| **Source is stale or `accessedAt` missing** | **Require review**; for high-consequence current views, prefer refusal | Belgian source surfaces update daily; OFARM should not infer “current” without an access date. citeturn7view1turn9view0 |
| **Registry unavailable at output time** | **Refuse high-consequence PassportView**; allow DocumentAssembly annex to carry the failure trace and existing evidence | The absence of a current check is itself material. citeturn7view1turn36view0 |
| **Product bound to the wrong jurisdiction** | **Fail closed** | Commission guidance is explicit that PPPs must be authorised in the EU country concerned. citeturn36view3 |
| **Profile requires ReferenceSnapshot but none is available** | **Fail closed** for high-consequence views | Without a captured external reference, OFARM cannot demonstrate exactly what was checked. This is the core purpose of the snapshot in a mutable registry environment. citeturn7view1turn9view0 |
| **Discrepancy between prescription product identity and as-applied product identity** | **Require review**; do not flatten to a single compliant identity | OFARM should preserve the discrepancy and keep prescription and as-applied evidence separate until authoritative reconciliation exists. Trade name, authorisation status, or GTIN may diverge. citeturn15view2turn31search0 |

## Narrow Belgium profile blueprint

### Profile scope

**Profile name:** `BE-CropProtection-AuthorisationIdentity-Currentness`

**Scope:** Belgian crop-farming use of plant protection products where OFARM needs a high-consequence product-identity binding for recommendation, prescription, execution-claim review, as-applied evidence review, or PassportView materialisation. The profile binds to the Belgian jurisdictional authorisation layer; it does not redefine OFARM truth or replace OFARM’s assertion/history-first model. citeturn7view0turn8view0turn36view3

### Standard role map

| Role | Source(s) | Blueprint rule |
|---|---|---|
| **Mandatory jurisdictional binding** | Belgium Phytoweb live registry and, where available, Phytoweb raw export | Must bind by Belgian authorisation number or equivalent official permit identifier, with snapshot and trace. citeturn8view0turn9view0turn7view1 |
| **EU active-substance context** | EU Pesticides Database and Commission approval/authorisation pages | Optional but strongly recommended contextual cross-check; may inform review decisions but cannot replace Belgian product authorisation. citeturn36view0turn36view2turn36view3 |
| **Crop/pest/use semantics** | EPPO Codes and, where actually used by the authorisation/label, BBCH | Recommended code binding for crops, targets, and growth stages; use as semantic anchors and exchange mappings, not as the legal authorisation itself. citeturn18view0turn18view1turn24view0turn8view0 |
| **Units and quantity kinds** | UCUM and QUDT | UCUM should carry operational unit codes; QUDT should carry quantity-kind semantics when OFARM needs machine-readable quantity reasoning. citeturn26search0turn26search1turn42view0turn42view2 |
| **Commercial pack identity** | GS1 GTIN / Digital Link | Evidence-only adjunct; never primary compliance key. citeturn31search0turn31search1turn31search2 |
| **Variety denomination context** | CPVO Variety Finder; UPOV PLUTO / GENIE | Optional semantic annex context only. citeturn34view0turn34view3turn34view4 |
| **Seed certification attestation** | OECD Seed Schemes | Attestation wrapper / evidence-only context, outside crop-protection product authorisation. citeturn35view0 |

### Binding requirements by role

For a **PASS** in this profile, OFARM should require at minimum: Belgian issuing authority; jurisdiction `BE`; checked Belgian authorisation number; checked trade name; snapshot access date; observed status/date context; and a verification trace that records how the match was made. Where the use claim is high consequence, the label or certificate should also be correlated because Belgian guidance ties label content to the authorisation certificate. citeturn7view0turn9view0turn15view0turn15view1

The following should be treated as **supporting but not governing**: EU active-substance approval status, GS1 commercial identifiers, CPVO or UPOV denomination records, OECD seed certification artefacts, AGROVOC subject terms, and Crop Ontology trait terms. They can enrich evidence, exchange, and semantics, but none of them should silently replace the jurisdictional authorisation record. citeturn36view2turn31search0turn34view0turn35view0turn32search16turn33search2

### Unresolved behaviour

If the binding evidence resolves only to **trade name**, only to **active substance**, only to **GTIN**, or only to an **EU-level record**, OFARM should materialise the binding as **unresolved** and require review for any high-consequence PassportView. That keeps OFARM’s assertion layer intact while preventing external ambiguity from being mistaken for governed current state. citeturn15view2turn36view0turn36view3turn31search0

### Required ReferenceSnapshot classes

The narrow profile should require, at minimum, these snapshot classes:

| Snapshot class | Minimum rule |
|---|---|
| **JurisdictionalProductAuthorisationSnapshot** | Mandatory for any high-consequence current-compliance PassportView; source must be Belgium Phytoweb search/profile or Phytoweb raw export. citeturn8view0turn9view0turn7view1 |
| **AuthorisationLabelOrCertificateSnapshot** | Mandatory when the output claims label-level compliance, pack-level labelling alignment, or certificate-backed proof. citeturn15view0turn15view1turn14search6 |
| **EUActiveSubstanceContextSnapshot** | Recommended, not mandatory, when the reasoning uses active-substance approval or emergency-authorisation context. citeturn36view0turn36view2turn36view3 |
| **CommercialIdentityEvidenceSnapshot** | Optional adjunct for GTIN/Digital Link, invoice, pack scan, or lot context; never sufficient alone. citeturn31search0turn31search1turn31search2 |

### Required ExternalRegistryVerificationTrace behaviour

Every verification trace in this profile should record the query inputs, lookup surface, candidate count, selected authorisation identifier, observed authorisation status/dates, correlation to any label/certificate reviewed, registry availability outcome, and final decision. If the source used is a raw export, the trace should also point to the exact file/export identity that was captured. If the source used is live search only, the trace should say so explicitly. citeturn7view1turn9view0turn15view0turn36view0

### Quantity and unit policy

Operational quantities in this profile should be represented with **UCUM unit codes**; quantity-kind semantics may be attached through **QUDT** where machine reasoning or cross-domain consistency is needed. OFARM should preserve the **verbatim source expression** as evidence, then add normalised coded units separately. If a Belgian authorisation/label refers to BBCH growth stages, OFARM should preserve both the stage code and the original wording. citeturn26search0turn26search1turn42view0turn42view2turn8view0

### Evidence floor

For a high-consequence **PASS**, the evidence floor should be:

1. a Belgian jurisdictional authorisation match by official identifier;
2. a captured ReferenceSnapshot with access date and artefact reference;
3. a verification trace showing the exact search or export surface used;
4. the observed status/date context; and
5. where the output claims label-level current compliance, a checked label/certificate correlation. citeturn7view1turn9view0turn15view0turn15view1

### Pack merge conflict posture

Do **not** merge products by trade name alone. Belgium’s official guidance makes that unsafe. Merge pack-level records into one OFARM external binding only when the **same Belgian authorisation number** is verified and there is no conflict in authorisation type, formulation, user category, or status. GTINs may differ across commercial packs under one authorisation and should therefore be treated as subordinate commercial identities, not the governing regulatory key. citeturn15view2turn31search0

### PassportView refusal and review rules

A high-consequence PassportView should be **refused** or **sent to review** whenever the profile lacks a current Belgian authorisation-number match, lacks a required snapshot, lacks an access date, or encounters ambiguity between multiple records or between prescription and as-applied identity. EU-only evidence, active-substance-only evidence, or GTIN-only evidence should not pass. citeturn36view3turn36view0turn15view2turn31search0

### DocumentAssembly annex rules

DocumentAssembly should be allowed to include annexes even when PassportView is refused. The annex set should include the ReferenceSnapshot metadata, verification trace, copied search inputs, any raw export filename or live-record URL reference, label/certificate references, and discrepancy notes. If the registry is unavailable at output time, the annex should carry an explicit **verification failure record** rather than silently omitting the check. citeturn7view1turn15view0turn36view0

### Limitations and non-claims

This blueprint is deliberately narrow. It is **not** a proposal to rewrite OFARM, **not** a legal opinion, and **not** a claim that OFARM is externally standard-ready. It is only a research-grounded profile for externally binding Belgian crop-protection product identity to current official source surfaces while keeping OFARM’s governing semantics internal. The strongest uncertainties are around a future Slovenia-specific profile and around the exact field sets exposed inside every Belgian raw-data file without registered FTP access. citeturn1view1turn7view1

## Open questions and confidence

### Open questions and limitations

The main unresolved question is whether the Slovenian official FFS register, beyond the public pages verified here, exposes enough official and durable metadata on identifier stability, change history, export files, and currentness to support a Slovenia-first OFARM profile at the same standard as Belgium. The official Slovenian pages do prove that the registry exists and is the relevant source, but they do not document as much public currentness mechanics as Belgium’s Phytoweb in the material reviewed. citeturn1view1turn1view2turn6view0turn7view1

A second open question is how much of the Belgian raw JSON field inventory should be made mandatory in OFARM if the production implementation has registered access to the FTP server. The official data page says a field-description sheet exists, but the public page does not enumerate those fields inline. That means the recommended OFARM fields above are conservative and based on the publicly documented behaviours rather than a verified field-by-field raw-export schema. citeturn7view1

A third open question is whether a future OFARM jurisdiction profile should capture **Belgian authorisation certificates** directly as annexed source artefacts in every high-consequence case, or only when the output asserts label-conformant current use. The Belgian guidance strongly links label content to the certificate, but public web guidance alone does not prescribe an OFARM-level mandatory capture rule. citeturn15view0turn15view1

### Confidence ratings

| Topic | Confidence | Reason |
|---|---|---|
| Belgium as the clearer currentness-oriented jurisdiction profile | **High** | Official Phytoweb pages document searchability, statuses, daily refresh, history, and raw JSON provision. citeturn7view0turn7view1turn8view0turn9view0 |
| Slovenia official-source existence but weaker public verification for this task | **Medium** | Good evidence of an official Slovenian source exists, but weaker public documentation of currentness mechanics in reviewed material. citeturn1view1turn1view2turn6view0 |
| EU Pesticides Database role as contextual anchor, not compliance replacement | **High** | Commission pages are explicit that the database is informational only and that PPP authorisation is national. citeturn36view0turn36view2turn36view3 |
| EPPO / UCUM / QUDT role recommendations | **High** | Official source materials clearly describe their nature, identifiers, and release behaviour. citeturn18view0turn26search0turn26search1turn42view0turn42view1 |
| BBCH role recommendation | **Medium-High** | Official BBCH hosting is clear; exact OFARM binding strength depends on whether the jurisdictional label/authorisation actually cites BBCH in a given case. citeturn24view0turn8view0turn20search0 |
| CPVO / UPOV and OECD Seed Schemes as adjunct context only | **High** | Official pages clearly position them as denomination repositories and certification frameworks, not crop-protection authorisation sources. citeturn34view0turn34view3turn34view4turn35view0 |
| Fail-closed rules and narrow profile blueprint | **Medium-High** | These are design recommendations inferred from strong official evidence, not dictated word-for-word by any single external source. citeturn15view2turn36view0turn36view3turn31search0turn7view1 |