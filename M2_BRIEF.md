# M2 brief — Core on Kernel

Status at handoff (2026-06-18): **M1 CLOSED and merged** (PR #7 on `main`). The Kernel runs — PostgreSQL append-only store + gate pipeline + materializer, the two governed views, and the generated Capability Manifest — green at **49/49** (25 conformance incl. `test_08b`, 8 stage, 16 review-fix regressions) with `ofarm_pkg_contract_check.py` PASS. The Core identity payload contracts are cut (candidate, `contracts/core/`); the SI profile instance, both real `ReferenceSnapshot`s, the `ActiveArtifactSet`, and the Capability Manifest are shipped. Both parsers exist and are validated against real data — `tooling/regsr_snapshot/parse_regsr.py` (623 products) and `tooling/gerk_roundtrip/gerk_roundtrip.py` (856,677 records, 4/4 PIDs) — but **neither is wired into the runtime**, and onboarding identities/grants are **bootstrapped** in `kernel/context.py`/`kernel/demo.py`, not committed through the gate chain. Pilot season is 2027 (D13) — build carefully, not hastily.

## The target

Core enforced on the running Kernel: domain identities committed **through the gate chain** (not bootstrapped); the registry and GERK adapters feeding dated `ReferenceSnapshot`s on the cadence the SI profile declares; code bindings verified against those real snapshots at **identity grade**; OIDC binding the transport principal; and the `ActiveArtifactSet` regenerated against the live artifacts. The M1 conformance suite stays green throughout — M2 adds cases, it never regresses them. Record-keeping completeness only; **no current-compliance claim** (D7).

Stack (unchanged, D10): Python 3.11+ / FastAPI / PostgreSQL / pytest. Adds Keycloak OIDC (`PLATFORM.md` component 8) and an adapter scheduler for the weekly REGSR parse and the yearly FFSNaprave / on-update GERK imports. The mobile client (Flutter/PWA) stays M3.

## Generic mechanism vs the SI package (binding)

M2 builds **generic** Core-on-Kernel support plus the SI FFS pilot as the **first installed profile** — it does not turn OFARM into a Slovenia-specific platform. Slovenia-specific identifiers, registers, evidence floors, adapter definitions, and snapshot cadences are **not** Core or Platform law (D6; Constitution RC2.1 §3.4); they are package/profile artifacts loaded by the SI FFS deployment. The split:

- **Core** provides the generic farming semantics and the binding mechanism — identities as `IdentityRecord` + typed payloads, `AgronomicIdentityBinding`, and the code-binding discipline (`CORE.md`).
- **Platform** provides the generic governed import / scheduler / adapter mechanism and the gate pipeline (`PLATFORM.md`).
- **The `profile_si_ffs` package** supplies the concrete schemes and rules: REGSR, GERK, FFSNaprave, KMG-MID, EPPO/BBCH/UCUM/QUDT bindings, the SI evidence floor and review policy, the parser jobs, source mappings, and snapshot cadences.

A task below that names a Slovenia specific (a register, a cadence, a field) is naming the **SI package's instance** of a generic capability — never extending Core or Platform law. If a capability cannot be expressed generically with the SI specifics living in the package, that is a design smell: stop and resolve it before building.

## Adapter discipline (binding — tasks 1–3)

M2 introduces scheduled adapter writers (REGSR, GERK, FFSNaprave) that the M1 build did not have. Two rules keep them from quietly bypassing the Kernel or weakening the single-writer pilot assumption:

- **Serialized writes.** Every adapter write runs through the same serialized commit/import lock as user commits, preserving the single-writer invariant by construction. That lock may be lifted **only after** freshness-vector snapshot-isolation / watermark handling is fixed (the M5/L2 item, promoted here out of deferred housekeeping) — a scheduled REGSR/GERK snapshot write changes reference/currentness basis and can otherwise race a user commit or a materialization (D12 stales any materialization whose basis member or context component changes).
- **Governed, not scheduler-side magic.** Adapters may fetch and parse external data, but the runtime records each import as **append-only governed records**: the `ReferenceSnapshot` plus parser version, source digest, import time, effective date, and the `ExternalRegistryVerificationTrace`s. A failed or partial import emits a refusal / `RuntimeProblem` trace — never a silent or half-applied state change. Projections, caches, and report stores are never authoritative (`PLATFORM.md` storage posture).

## Ordered tasks

1. **Registry adapter scheduling.** Wrap `tooling/regsr_snapshot/parse_regsr.py` in a scheduled job (weekly HTML parse → dated `ReferenceSnapshot`; monthly manual floor per the profile). For every product a farm has bound, **fetch the REGSR detail page** so the *številka odločbe* + validity dates are captured (D9): identity-grade re-verification becomes confirmable instead of locator-only and review-routed. Each check emits an `ExternalRegistryVerificationTrace` recording the HTML lookup surface (unofficial-surface-over-official-content posture — D9, ERRATA E-002). Writes obey the adapter discipline above. Upgrade **only** the scheduled snapshot-import capability in the Capability Manifest `IMPORT_MAPPING` surface (`kernel/manifest.py`, currently `PARTIAL`); do **not** claim live registry integration, production currentness, or current-compliance support.

2. **GERK importer + parcel onboarding.** Wrap `tooling/gerk_roundtrip/gerk_roundtrip.py`; import the open national GERK layer (OPSI Blok/GERK `.dbf`/shapefile) as a dated `ReferenceSnapshot`. The layer attribute set is minimal (`GERK_PID, RABA_ID, AREA, OPIS_RABE` — no *domače ime*, no BLOK-ID, no NUP/GrPov), so it supplies existence, geometry, area, and use code only. Onboarding: farmer enters KMG-MID, confirms their GERK list (eRKG / subsidy paperwork), field names + BLOK/NUP come from the farmer/izpis (`profile_si_ffs/ONBOARDING_RKG_IZPIS.md`). Personal data stays farm-side (D14). The layer import obeys the adapter discipline above.

3. **Identities through the gate chain.** Replace the bootstrapped onboarding (`kernel/context.py`, `kernel/demo.py`) with real `structure assertion` commits for Farm / Field / CropCycle / Equipment / AppliedResource (`contracts/core/` payloads); `CropCycle` auto-creates on first record (`autoCreated: true`). Sprayer identities from the **FFSNaprave** yearly TXT/XLS/XML+XSD import (delimited adapter), matched by sticker number (`StevilkaZnaka` + `VeljavnostZnaka`) → `EquipmentIdentityPayload.inspectionEvidenceRefs`.

4. **Code bindings enforced.** `AgronomicIdentityBinding` records (scheme + value + evidence + state) resolve against the real snapshots; unresolved stays explicitly `UNRESOLVED` — free text never silently becomes compliance identity. EPPO crops/targets and decision numbers from the detail pages drive the authorisation-mismatch advisory (advisory twin; never blocks, never auto-creates compliance facts). Regenerate `OFARM_ActiveArtifactSet_*` and `OFARM_ContextSnapshot_*` against the live artifacts; re-run the manifest-grounding check.

5. **OIDC — principal binding, not authority.** Keycloak authenticates the transport principal and maps it to a **Party** (D4); it fills the `X-Acting-Party` development-principal slot (`kernel/api.py`, declared in `profile_si_ffs/UNSUPPORTED_SURFACES.md`). It does **not** authorize action by role name alone — a role is contextual identity; Kernel `AuthorityGrant` / `DelegationGrant` / `SharingGrant` remains the sole source of permission. Roles: farmer, family worker / contractor (`DelegationGrant`), advisor, read-only inspector (`SharingGrant`). Default-deny and the non-human-actor rule unchanged (`kernel/authority.py`).

6. **Review queue verbs + advisor flow.** Implement REJECT and CONTEST (M1 shipped acceptance only); the advisor queue is exercised with **synthetic actors** until the 2027 outreach (D13). These are state transitions, not UI verbs — **specify the exact effects before building**: for **REJECT**, what happens to the queued assertion, its `PromotionTrace`, any materialization, and future acceptance attempts (re-submittable as a new capture, or terminal?); for **CONTEST**, which `recordClass` is emitted, what becomes `disputeStatus`-flagged, which materializations stale (D12), and how supersession resolves it. Dispute and correction stay a **new payload + supersession, never an edit** (CORE.md; Kernel append-only rule). The latent M4 `disputeStatus` over-claim closes here.

7. **AS_OF over real history.** Once activation / profile / artifact-set history exists, make `AS_OF` reconstruct the historical pack/profile context by `timeContext` instead of refusing (`MATERIALIZATION_INVALID` guard in M1). Extend `kernel/context.py` snapshot selection; **keep the guard** until the history is genuinely reconstructible — refuse over pretend (Kernel rule 7).

8. **Extent carrier ingestion.** Populate `policy.M1_ALLOWED_EXTENT_BOUND_KINDS` (empty in M1) once GERK geometry provides a real extent carrier, so `geometryRef` / `extentRef` / `scopeExtentBasisRef` partial-extent bounds become acceptable — not just inline `area`. Update `profile_si_ffs/UNSUPPORTED_SURFACES.md` to match.

## Status

Current main is merged through **P6** (PR #24). The table below is a
repo-currentness view of that merged state, not a production-readiness or
current-compliance claim. The package still claims record-keeping completeness
only, the Capability Manifest conformance level remains `NONE`, and no
certification, legal, production, or current-compliance readiness is claimed.

| Brief task | Status |
|---|---|
| 1 — Registry adapter scheduling + detail-page identity verification | DONE / P1 (on G2+G3) |
| 2 — GERK importer + parcel onboarding | DONE / P2 for the implemented attribute-import scope; G7 supplies the generic extent-carrier acceptance mechanism |
| 3 — Identities through the gate chain (incl. FFSNaprave) | DONE / G1 + P3 |
| 4 — Code bindings enforced against real snapshots; regenerate artifacts | DONE / G3 + P4 + P6 |
| 5 — OIDC onto Party/RoleAssignment/AuthorityGrant | DONE / G4 for the conformance/development OIDC binding; production authentication is not claimed |
| 6 — Review queue REJECT/CONTEST + dispute handling | DONE / G5-1 through G5-4 |
| 7 — AS_OF reconstruction over real history | DONE / G6, with non-reconstructible profile lifecycle cases still refused per E-007 |
| 8 — Extent carrier ingestion (allowed-kinds table) | DONE / G7 |

### Remaining follow-up: E-006 durable advisory output

P5 implemented authorisation-mismatch and dose-range advisories as
non-blocking `WARNING` result problems sourced from the SI package policy. The
durable Advisory Twin record is still deferred: no trace-safe `ADVISORY_OUTPUT`
emission into PassportView `_advisory_flags` exists yet.

That follow-up must be treated as advisory infrastructure, not a Compliance
Twin shortcut. Advisory material must not enter Compliance materialization, and
any durable advisory emission needs its own trace-safe emission path,
appropriate reason-code/result channel, and reachability-compatible linkage
before it can be stored or surfaced as a record.

## Build order (completed slice map)

M2 was built and merged as controlled slices, each kept green against
`conformance/` before the next began:

1. **M2a — governed structure identities.** Farm, Field, CropCycle, Equipment, AppliedResource committed through `STRUCTURE_ASSERTION`; drop the demo/bootstrap dependence only after tests prove the committed path (task 3).
2. **M2b — reference-snapshot adapters** (tasks 1, 2). Each adapter lands alone, under the adapter discipline (parser version, source digest, effective date, import + failure traces):
   - **M2b-1** — REGSR scheduled snapshot import (+ bound-product detail-page identity fetch).
   - **M2b-2** — GERK snapshot import.
   - **M2b-3** — FFSNaprave equipment snapshot import.
3. **M2c — code-binding enforcement.** Product / crop / parcel / equipment / operator bindings verified against the live M2 snapshots; unresolved stays review-routed (task 4).
4. **M2d — OIDC principal binding.** Replace the `X-Acting-Party` development principal with an OIDC-derived Party binding, authority semantics unchanged (task 5).
5. **M2e — review verbs and disputes** (task 6). Semantics land before code:
   - **M2e-1** — specify REJECT semantics (state effects on assertion, `PromotionTrace`, materialization, future acceptance).
   - **M2e-2** — implement REJECT.
   - **M2e-3** — specify CONTEST / dispute semantics (`recordClass` emitted, `disputeStatus` scope, materialization staling, supersession resolution).
   - **M2e-4** — implement CONTEST / dispute materialization.
6. **M2f — AS_OF and extent carriers.** Only after artifact/profile/snapshot history and GERK geometry carrier records exist (tasks 7, 8).

Each M2 slice was opened as one or more **narrow implementation tickets** before
coding started. Every ticket declared: goal · likely-touched files · forbidden
files (the explicit "do not touch" list) · contracts/docs to read first · exact
behavior change · required tests · acceptance criteria · non-goals. No slice
proceeded until the previous slice was green against the M1 suite **plus** its
own new M2 tests. This is what kept agents from mixing SI package-specifics
into generic Core/Platform code, or implementing review/dispute behavior before
its semantics were settled.

### Ticket order: generic mechanism before package content (binding)

Cut tickets in two phases, never interleaved:

1. **Phase 1 — generic Core/Platform mechanism tickets only:** governed structure-identity commit path · governed adapter/import mechanism · reference-resolution / verification-trace support · OIDC principal binding · review/dispute state-transition semantics · AS_OF reconstruction · extent-carrier acceptance. No Slovenia specifics.
2. **Phase 2 — SI-package tickets that exercise those mechanisms:** REGSR / GERK / FFSNaprave scheduled imports · KMG-MID / GERK / REGSR / FFSNaprave bindings · the SI evidence floor and advisory behavior · `ActiveArtifactSet` / `ContextSnapshot` regeneration.

**Mechanism-boundary stop rule.** No ticket may implement a Slovenia-specific register, cadence, identifier, or evidence rule directly as Core or Platform law. If an SI ticket cannot be expressed as `profile_si_ffs` package/profile content loaded through a generic mechanism, **stop and fix the mechanism boundary before coding**. This keeps Core generic farming semantics, Platform generic runtime enforcement, and `profile_si_ffs` the first installed profile rather than hidden universal law. The completed ticket plan lives in `M2_TICKETS.md`.

## Deferred M1 review items folded into M2 housekeeping

Each was deferred with a recorded rationale (WORKLOG 2026-06-14): H2 profile-pinned UCUM code allow-list; narrow the `api.py` `except (…, KeyError)` catch-all (M2's root cause is fixed, but the broad catch can still mask unrelated KeyErrors); the M1 revocation narrowing (fails closed today); and the issue-#3 elegance leftovers (typed route-reason objects vs. stringly dicts, the `find_by_kind(...)[-1]` latest-instance convention, the `_store_case` boolean-keyword split). None changes behavior; none is a blocker.

## Definition of done (PILOT_SI M2)

Identities, registry snapshots, GERK onboarding, and code bindings enforced; `ActiveArtifactSet` regenerated against real artifacts. Concretely: a fresh agent can onboard the fictional, format-true farm by committing its structure assertions through the gate chain; the scheduled REGSR adapter produces a dated snapshot and the detail-page fetch lets a bound product re-verify at decision-number grade instead of routing to review; a spray claim binds product/crop/parcel/operator against the real snapshots and self-reviews to accepted; an authorisation mismatch raises a non-blocking warning advisory; a worker authenticates via OIDC and a delegation revoked while offline denies on sync; the inspection register exports and refuses when it should. The M1 suite stays green, `ofarm_pkg_contract_check.py` PASSes, and benchmark evidence is captured per the explainable-evidence RFC before any Capability Manifest level above `NONE` is claimed.

M2 is closed for repo-facing currentness after P6, subject to the explicit
E-006 durable-advisory follow-up above. That follow-up does not weaken the claim
limits: no current-compliance, certification, production-readiness, or
Capability Manifest level above `NONE` is claimed.

## Out of scope for M2 (do not drift)

Mobile app and the ≤ 90 s field-capture target (M3) · live pilot with real farms/advisor (M4 — 2027 season, D13; synthetic actors until then) · IS Evidenca FFS submission feed (outreach-gated to 2027 — watch the procurement specs, don't build) · dynamic packs · public query compiler · AI/agent runtime including software-agent review (D8) · anything in `profile_si_ffs/UNSUPPORTED_SURFACES.md` · any law edit (`ERRATA.md` only) · any personal data (AGENTS.md rule 1, D14) · any current-compliance, certification, or production-readiness claim.
