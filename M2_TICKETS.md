# M2 implementation tickets — Core on Kernel

Companion to `M2_BRIEF.md`. Each ticket is a narrow, self-contained unit of work sized for a single coding agent and a single PR. Read `M2_BRIEF.md` first — its **Generic mechanism vs the SI package**, **Adapter discipline**, **Build order**, and **Ticket order** sections are binding here.

Tickets are cut in two phases (brief, *Ticket order*): **Phase 1 = generic Core/Platform mechanism** (G1–G7), **Phase 2 = SI-package content that exercises the mechanisms** (P1–P6). The mechanism-boundary stop rule applies to every Phase-2 ticket: if an SI specific cannot be expressed as `profile_si_ffs` package/profile content loaded through a generic mechanism, stop and fix the mechanism boundary first.

Claim limits are unchanged: record-keeping completeness only — never current-compliance, certification, or production readiness (AGENTS.md rule 6, D7). No personal data anywhere; fictional, format-true values only (AGENTS.md rule 1, D14).

## How to work a ticket (binding)

1. Branch per ticket (`m2/<ticket-id>-<slug>`); one ticket = one PR.
2. Read the ticket's **Read first** list before writing code. Do not touch anything in **Files NOT to touch**.
3. Keep the M1 conformance suite green **and** add the ticket's new tests. New M2 behavior tests go in their own engineering module (e.g. `kernel/tests/test_m2_<area>.py`), following the `test_review_fixes.py` / `test_stages.py` convention — they run in the same session but are **excluded from the named conformance evidence** by nodeid (only `test_conformance.py` results are attested). Never present a design fixture as executed evidence (AGENTS.md rule 7).
4. Run, before opening the PR (see `kernel/README.md` "Run it" for the Postgres scratch-cluster setup):
   - `.venv/bin/python -m pytest kernel/tests/ -q`
   - `python3 conformance/ofarm_pkg_contract_check.py` (must PASS — AGENTS.md rule 3)
5. Contracts in `contracts/**` and `reference/**` are extraction-only and frozen (AGENTS.md rules 2 & 4). A genuine contract gap goes to `ERRATA.md`, never an edit. Never invent a `RuntimeProblem` reason code: use the registry RFC's codes; a missing code is an ERRATA entry.
6. No slice starts until the slice before it (brief *Build order*) is green.

Ticket field key: **Goal · Serves · Depends on · Files likely touched · Files NOT to touch · Read first · Exact behavior change · Required tests · Acceptance · Non-goals.**

---

# Phase 1 — generic Core/Platform mechanism

These tickets contain **no** Slovenia specifics. A reviewer who finds a scheme name (REGSR, GERK, KMG-MID, FFSNaprave) hardcoded in a Phase-1 change should reject it.

## G1 — Governed structure-identity commit path

- **Goal:** commit Farm, Field, CropCycle, Equipment, AppliedResource identities through the full gate chain as `STRUCTURE_ASSERTION` commits carrying the typed identity payloads, producing `ACCEPTED_STRUCTURAL_STATE` consequences; the identity registry materializes the **current payload** per identity from in-force structure consequences. Replace the directly-bootstrapped identity records with committed structure assertions.
- **Serves:** slice M2a.
- **Depends on:** nothing (the `STRUCTURE_ASSERTION` vocabulary already wires end-to-end in `policy.py`).
- **Files likely touched:** `kernel/demo.py` (add structure-assertion submission builders per identity type, fictional values); `kernel/materializer.py` (materialize current identity payload per `IdentityRecord` from in-force `ACCEPTED_STRUCTURAL_STATE` consequences, basis-set invalidation per D12); new `kernel/tests/test_m2_identities.py`.
- **Files NOT to touch:** `kernel/authority.py` (authority semantics unchanged); `kernel/policy.py` `STRUCTURE_ASSERTION` rows (already correct — do **not** add per-identity-type branches); `contracts/**`, `reference/**`.
- **Read first:** `CORE.md` "Domain identities" + "the operation chain"; `KERNEL.md` (StructureEvent, IdentityRecord, append-only, derived-state-with-receipts); `contracts/core/OFARM_*IdentityPayload_schema_v0_1.json`; `kernel/policy.py` (`COMMIT_CLASS_TO_*`, `ACCEPTANCE_BY_ASSERTION_TYPE`, `CONSEQUENCE_SUBJECT_TYPES`); `kernel/store.py` (in-force queries); `kernel/demo.py`.
- **Exact behavior change:** a `STRUCTURE_ASSERTION` commit carrying a typed identity payload passes the gate chain and writes an `ACCEPTED_STRUCTURAL_STATE` consequence reachable from its `PromotionTrace`; the identity registry returns the current payload for that identity from in-force structure consequences; a superseding structure assertion updates the current payload without editing the prior record. Generic over identity type — no scheme logic.
- **Required tests:** commit each identity type → accepted + current payload materialized; supersede a Field payload → current payload updates, prior preserved, dependent materializations stale (D12); malformed/absent payload → governed refusal with a registry reason code, draft retained; a wrong-kind subject refuses governably (`CONSEQUENCE_SUBJECT_TYPES`), never a crash.
- **Acceptance:** the demo farm can be onboarded purely via committed structure assertions (no direct identity-record bootstrap for identities); `pytest kernel/tests/ -q` green; self-check PASS.
- **Non-goals:** SI scheme bindings (P4); parcel geometry/area ingestion (G7/P2); OIDC (G4).

## G2 — Governed adapter / import mechanism

- **Goal:** a generic, **serialized, governed** import mechanism that turns a parser's output into a dated `ReferenceSnapshot` plus governed import records (parser version, source digest, import time, effective date) and emits a refusal / `RuntimeProblem` trace on failure — never a silent or half-applied write. Scheme-agnostic.
- **Serves:** slice M2b (the generic half).
- **Depends on:** nothing.
- **Files likely touched:** new `kernel/adapters.py` (generic import runner; serialized commit/import lock shared with user commits; import-record + trace emission); `kernel/store.py` (confirm/establish the single serialized write path so a scheduled import cannot race a user commit); new `kernel/tests/test_m2_adapters.py`.
- **Files NOT to touch:** `tooling/**` (parsers are reused as libraries, not modified here); `profile_si_ffs/**` (SI snapshot files are package content/evidence); `contracts/**`.
- **Read first:** `PLATFORM.md` (components 5–6, storage posture, invalidation); `M2_BRIEF.md` *Adapter discipline*; `reference/rfcs/OFARM_RuntimeProblem_Reason_Code_Registry_RFC_v0_1.md`; `kernel/store.py`; `kernel/context.py` (`current_reference_snapshot`, snapshot-prefix pattern, `mint`, `parse_ts`).
- **Exact behavior change:** `adapters.run_import(parse_result, snapshot_meta)` writes one `ReferenceSnapshot` + import record(s) in a single serialized transaction; a failed/partial parse writes a refusal trace and **no** snapshot; an import and a user commit cannot interleave (single-writer invariant preserved by the shared lock). The lock may be lifted only after the freshness-vector watermark fix (M5/L2) — **out of scope here; the lock stays on.**
- **Folded-in hardening from G1 (PR #9 hostile-review H1):** the same serialized write path must also serialize **structure-identity commits**. D18 (DECISIONS.md) is read-before-write — two concurrent first `STRUCTURE_ASSERTION`s for the same `identityRecordRef` can both pass validation before either commits, and the loser then hits an ungoverned DB `UniqueViolation` on the `IdentityRecord` PK instead of a governed `RuntimeProblem`. In the single-writer pilot (D13, no concurrent public onboarding before 2027) the serial path is fully governed, so G1 deferred this here; G2 closes it by serializing user commits (e.g. a transaction advisory lock keyed on `(farmRef, identityRecordRef)` / the shared single-writer lock) so D18 is deterministic and the loser refuses governably. Add a test: two racing first structure assertions for one identity → exactly one promotes, the other gets a governed refusal (never a crash, never two in-force consequences).
- **Required tests:** a fake parser output imports as a dated snapshot with a governed import record; a simulated parse failure yields a refusal trace and no snapshot; two interleaved writes serialize deterministically.
- **Acceptance:** the mechanism is exercised with a **fixture scheme**, not REGSR/GERK; no scheme literals in `adapters.py`; self-check PASS.
- **Non-goals:** REGSR/GERK/FFSNaprave specifics (P1–P3); cron/runtime scheduler wiring beyond an injectable trigger; live network fetch in tests.

## G3 — Reference-resolution & verification-trace support

- **Goal:** a generic mechanism to resolve a candidate binding against an in-force `ReferenceSnapshot` and emit an `ExternalRegistryVerificationTrace` (lookup surface, query inputs, candidate count, selection rationale, snapshot refs, outcome). Surface the **identity-grade vs locator-only** distinction generically: locator-only matches route to review rather than pretending to verify.
- **Serves:** slice M2c (the generic half).
- **Depends on:** G2 (or the shipped M1 snapshots for fixtures).
- **Files likely touched:** `kernel/validators.py` (the reference-resolution and registry-re-verification units exist — extend generically); `kernel/sufficiency.py` (consume the trace); optionally new `kernel/verification.py`; `kernel/tests/test_m2_bindings.py`.
- **Files NOT to touch:** `profile_si_ffs/**`; `contracts/**`.
- **Read first:** `CAPTURE_MAPPING.md` (the `ExternalRegistryVerificationTrace` 19-field row); `contracts/core/OFARM_ExternalRegistryVerificationTrace_schema_v0_1.json`; `CORE.md` "code binding discipline"; `kernel/validators.py`; `profile_si_ffs/UNSUPPORTED_SURFACES.md` ("No live registry integration" — identity-grade only where the snapshot carries decision-number-style keys).
- **Exact behavior change:** given a candidate binding + snapshot, produce a verification trace; an identity-grade match (snapshot row carries a stable key) confirms; a locator-only match routes to review; an unavailable/absent snapshot is a governed refusal. Scheme and key-field passed as parameters.
- **Required tests:** identity-grade confirm; locator-only → review route; missing snapshot → governed refusal; trace carries all required fields.
- **Acceptance:** works against a generic snapshot fixture; no scheme literals; self-check PASS.
- **Non-goals:** REGSR/GERK/FFSNaprave specifics (P-tickets); live fetch.

## G4 — OIDC principal binding

- **Goal:** replace the `X-Acting-Party` development principal with an OIDC-derived **Party** principal, preserving the existing binding contract (the gate's actor is the transport's actor, or the commit refuses). Roles map to `RoleAssignment`; authority still comes **only** from `AuthorityGrant` / `DelegationGrant` / `SharingGrant`.
- **Serves:** slice M2d.
- **Depends on:** nothing (the slot is defined in `api.py`).
- **Files likely touched:** `kernel/api.py` (derive the principal from a verified OIDC token → Party; keep the `actingPartyRef` binding check and the read-path default deny); new `kernel/auth_oidc.py` (token validation + claims→Party mapping, Keycloak); `kernel/config.py` (issuer/audience config); `profile_si_ffs/UNSUPPORTED_SURFACES.md` (update the "API authentication posture" note); `kernel/tests/test_m2_oidc.py`.
- **Files NOT to touch:** `kernel/authority.py` (grant evaluation, default deny, non-human-actor rule — **roles do not grant authority**); `kernel/policy.py`.
- **Read first:** `PLATFORM.md` component 8; `profile_si_ffs/UNSUPPORTED_SURFACES.md` (API-auth posture); `kernel/api.py` `/commit` principal binding; `KERNEL.md` record families (RoleAssignment vs AuthorityGrant); D4.
- **Exact behavior change:** a verified token yields the Party id used as the transport principal; a mismatch with `submission.actingPartyRef` still refuses `ACTOR_BINDING_UNRESOLVED`; no/invalid token → no farm-scoped read or commit (default deny); role claims map to `RoleAssignment` only and **never** synthesize a grant.
- **Required tests:** valid token binds the principal; mismatch refuses; a role claim alone does not authorize an action that lacks a grant; absent/invalid token denied. Existing authority tests pass unchanged (via a test-principal shim).
- **Acceptance:** the header dev-principal path is replaced or gated behind config; authority semantics provably unchanged (`authority` tests untouched and green); self-check PASS.
- **Non-goals:** any new permissions model; SSO UI; agent runtime (D8 keeps `REQUIRE_HUMAN_APPROVAL` for non-human actors).

## G5 — Review / dispute state-transition mechanism

The generic governance state machine for REJECT and CONTEST. M1 shipped acceptance only. Semantics land **before** code (brief slice M2e). This is four tickets:

### G5-1 — Specify REJECT semantics (spec ticket)
- **Goal:** a written, reviewed spec of REJECT's exact effects: what happens to the queued assertion, its `PromotionTrace`, any materialization, and future acceptance attempts (re-submittable as a new capture, or terminal?).
- **Serves:** M2e-1. **Depends on:** nothing.
- **Deliverable / files:** a semantics section appended to `M2_BRIEF.md` (or a new `docs/REVIEW_DISPUTE_SEMANTICS.md`) — **no code**. Settle the open questions; record the decision (DECISIONS.md candidate or ERRATA if a contract gap surfaces).
- **Read first:** `CORE.md` (correction/dispute = new payload + supersession, never edit); `KERNEL.md` (append-only, capture ≠ commitment, refuse over pretend); `kernel/policy.py` (`ACCEPTANCE_BY_ASSERTION_TYPE`, `NEEDS_EVIDENCE_CODES`, `ROUTE_REASON_TO_INSUFFICIENCY`); `WORKLOG.md` review-queue entries.
- **Acceptance:** every state effect named; no behavior is left to "obvious default"; reviewed and merged before G5-2 starts.
- **Non-goals:** implementation; SI specifics.

### G5-2 — Implement REJECT
- **Goal:** implement REJECT per the G5-1 spec as a governed transition with a `RuntimeProblem`-coded outcome and a gate-log/trace record.
- **Serves:** M2e-2. **Depends on:** G5-1.
- **Files likely touched:** `kernel/stages.py` / `kernel/validators.py` / `kernel/emission.py` (governance-decision handling); `kernel/policy.py` (REJECT routing as a generic table entry); `kernel/api.py` (`/review/reject` or extend `/review`); `kernel/tests/test_m2_review.py`.
- **Files NOT to touch:** `kernel/authority.py`; `profile_si_ffs/**`.
- **Exact behavior change:** a rejected queued assertion reaches the spec's terminal/redraft state; no consequence is promoted; the rejection is reachable in the gate log + trace.
- **Required tests:** reject → no consequence, recorded outcome; the spec's future-acceptance rule holds; M1 suite green.
- **Acceptance:** matches the G5-1 spec exactly; self-check PASS. **Non-goals:** CONTEST; SI specifics.

### G5-3 — Specify CONTEST / dispute semantics (spec ticket)
- **Goal:** a written spec for CONTEST/dispute: which `recordClass` is emitted, what becomes `disputeStatus`-flagged, which materializations stale (D12), and how supersession resolves it. Closes the latent M4 `disputeStatus` over-claim conceptually.
- **Serves:** M2e-3. **Depends on:** G5-1.
- **Deliverable / files:** semantics doc (as G5-1) — **no code**.
- **Read first:** as G5-1, plus `contracts/platform/OFARM_ResultQualificationEnvelope_schema_v0_1.json` (`disputeStatus`); `PLATFORM.md` materialization sub-gate; `kernel/materializer.py` (basis-set invalidation).
- **Acceptance:** dispute lifecycle fully specified as new-payload + supersession (never edit); reviewed before G5-4.
- **Non-goals:** implementation; SI specifics.

### G5-4 — Implement CONTEST / dispute materialization
- **Goal:** implement CONTEST and the dispute materialization behavior per G5-3.
- **Serves:** M2e-4. **Depends on:** G5-3 (and G5-2 for the shared `/review` surface).
- **Files likely touched:** `kernel/materializer.py` (dispute staling), `kernel/stages.py`/`validators.py`/`emission.py`, `kernel/policy.py` (CONTEST routing table), `kernel/api.py`, `kernel/tests/test_m2_review.py`.
- **Files NOT to touch:** `kernel/authority.py`; `contracts/**`; `profile_si_ffs/**`.
- **Exact behavior change:** a CONTEST emits the spec's `recordClass` + supersession; affected materializations go STALE/INVALID per the spec; current state reflects the dispute without any edit to prior records.
- **Required tests:** contest flags `disputeStatus`, stales the right materialization, resolves by supersession; no record is edited in place; M1 suite green.
- **Acceptance:** matches G5-3; self-check PASS. **Non-goals:** SI advisory rules (P5).

## G6 — AS_OF reconstruction mechanism

- **Goal:** make `AS_OF` reconstruct the historical pack/profile/artifact-set context by `timeContext` (instead of refusing `MATERIALIZATION_INVALID`) **once** activation/profile/artifact-set history exists — and keep the refusal guard whenever history is not genuinely reconstructible (refuse over pretend, Kernel rule 7).
- **Serves:** slice M2f.
- **Depends on:** G1 (committed identities create real history) and the adapters (snapshot history).
- **Files likely touched:** `kernel/context.py` (extend the as-of selection — `current_reference_snapshot` is already as-of-aware — to activation/profile/artifact-set vintages by `effectiveFrom <= asOfTime`); `kernel/materializer.py` (AS_OF path); `kernel/tests/test_m2_asof.py`.
- **Files NOT to touch:** `kernel/authority.py`; `profile_si_ffs/**`.
- **Read first:** `kernel/context.py` (the `as_of` pattern, fail-closed on unparseable validity); `WORKLOG.md` AS_OF entries (the M1 guard, test 93/98z); `KERNEL.md` rule 6 (distinct times) + rule 7.
- **Exact behavior change:** with multiple in-force activation/profile/artifact-set versions, `AS_OF` selects the vintage in force at `asOfTime` and materializes against it; with insufficient history it still refuses; a future vintage is never applied to an earlier state.
- **Required tests:** AS_OF with history reconstructs the right vintage; AS_OF without sufficient history refuses (the M1 guard holds); future-vintage exclusion.
- **Acceptance:** the M1 no-history guard test still passes; the new with-history path passes; self-check PASS.
- **Non-goals:** SI specifics; any public query compiler (D11).

## G7 — Extent-carrier acceptance mechanism

- **Goal:** make a partial-extent `geometryRef` / `extentRef` / `scopeExtentBasisRef` that resolves to a **recognized extent-carrier kind** acceptable as a bound — not just inline `area`. `policy.M1_ALLOWED_EXTENT_BOUND_KINDS` is empty in M1; introduce the generic extent-carrier record kind and populate the allowed set. (The SI geometry *source* is P2.)
- **Serves:** slice M2f.
- **Depends on:** nothing generic (the SI geometry that feeds it is P2/GERK).
- **Files likely touched:** `kernel/policy.py` (populate `M1_ALLOWED_EXTENT_BOUND_KINDS`, kept single-homed; rename out of the `M1_` prefix if appropriate); `kernel/validators.py` (`ExecutionExtentValidator` already resolves against the set and kind-checks — confirm); `profile_si_ffs/UNSUPPORTED_SURFACES.md` (update the partial-extent block); `kernel/tests/test_m2_extent.py`.
- **Files NOT to touch:** `profile_si_ffs/**` instances; whole-scope carrier semantics; `contracts/**`.
- **Read first:** `WORKLOG.md` M3 extent entries; `profile_si_ffs/UNSUPPORTED_SURFACES.md` partial-extent block; `kernel/policy.py` (`NON_WHOLE_EXTENT_CLASSES`, `M1_ALLOWED_EXTENT_BOUND_KINDS`); `kernel/validators.py` `ExecutionExtentValidator`.
- **Exact behavior change:** a non-whole extent with a ref bound resolving to an allowed extent-carrier kind is accepted; a dangling or wrong-kind ref still refuses `EVIDENCE_REFERENCE_UNAVAILABLE`; no bound at all still refuses `EVIDENCE_INSUFFICIENT`; inline `area` still accepted.
- **Required tests:** accepted ref-bound; wrong-kind refused; dangling refused; inline area still accepted; all stay governed (no crash).
- **Acceptance:** generic extent-carrier kind, no SI geometry literals; self-check PASS.
- **Non-goals:** GERK geometry ingestion (P2); geometry math.

---

# Phase 2 — SI-package content (exercises the mechanisms)

Every ticket here is `profile_si_ffs` package/profile content riding a Phase-1 mechanism. If a ticket can't be expressed that way, invoke the **mechanism-boundary stop rule** and fix the Phase-1 mechanism first.

## P1 — REGSR scheduled snapshot import

- **Goal:** define the SI REGSR adapter as package content: a scheduled job running `tooling/regsr_snapshot/parse_regsr.py` weekly (monthly manual floor), plus a bound-product **detail-page fetch** capturing the *številka odločbe* + validity dates, feeding the generic G2 import → dated REGSR `ReferenceSnapshot` and G3 verification traces.
- **Serves:** M2b-1. **Depends on:** G2, G3.
- **Files likely touched:** an SI adapter definition under the package (e.g. `kernel/profiles/si_ffs/regsr_adapter.py` or a profile config that wires parser + cadence + lookup surface to G2 — **SI specifics live here, not in `kernel/adapters.py`**); a scheduler entry; `kernel/tests/test_m2_si_regsr.py`.
- **Files NOT to touch:** `kernel/adapters.py` (use it; never special-case REGSR inside it); `tooling/regsr_snapshot/parse_regsr.py` (reuse, don't fork); `contracts/**`.
- **Read first:** `profile_si_ffs/PROFILE.md` (REGSR row); `profile_si_ffs/M0_DESK_RESEARCH.md` §3/§4a; `tooling/regsr_snapshot/parse_regsr.py`; D9; tickets G2, G3.
- **Exact behavior change:** a scheduled trigger parses → G2 imports a REGSR snapshot with `effectiveFrom` + parser version + source digest; bound products carry the detail-page decision-number key enabling G3 identity-grade re-verification; parse/import failure → refusal trace, no snapshot.
- **Required tests:** a parse fixture imports as a REGSR snapshot via the generic mechanism; the decision-number key drives an identity-grade verify (not a review route); the weekly cadence config is honored. (Fixtures only — no live HTTP.)
- **Folded-in from G2 review (H2 — import-triggered staling):** G2's importer does not broad-stale materializations; it relies on **context-key drift** (a new in-force REGSR `ReferenceSnapshot` changes the `ContextSnapshot` → a new `MaterializationKey`, so a post-import NOW materialization never reuses a pre-import row — D12). Before this real scheduled import ships, **confirm context-key drift suffices** for affected farms, or add an explicit broad-stale (`materializer.invalidate_for_sources(..., farm_scope_ref=...)` for the reference family). Decide and record.
- **Acceptance:** upgrades **only** the scheduled snapshot-import capability in `kernel/manifest.py` `IMPORT_MAPPING`; no live-integration / production-currentness / current-compliance claim; self-check PASS.
- **Non-goals:** live HTML fetch in tests/CI; any current-compliance claim; an official-feed switch (outreach-gated to 2027, D13).

## P2 — GERK snapshot import

- **Goal:** SI GERK adapter as package content: import the open national Blok/GERK layer (OPSI `.dbf`/shapefile) via `tooling/gerk_roundtrip/gerk_roundtrip.py` through G2 → dated GERK `ReferenceSnapshot`. The layer's minimal attributes (`GERK_PID, RABA_ID, AREA, OPIS_RABE`) supply existence, geometry, area, and use code — and the extent-carrier source for G7.
- **Serves:** M2b-2. **Depends on:** G2 (and G7 for the extent-carrier kind it feeds).
- **Files likely touched:** SI GERK adapter config under the package; `kernel/tests/test_m2_si_gerk.py`.
- **Files NOT to touch:** `kernel/adapters.py`; `tooling/gerk_roundtrip/gerk_roundtrip.py`; `contracts/**`.
- **Read first:** `profile_si_ffs/PROFILE.md` (GERK row); `profile_si_ffs/M0_DESK_RESEARCH.md` §4/§4a; `tooling/gerk_roundtrip/gerk_roundtrip.py`; `profile_si_ffs/ONBOARDING_RKG_IZPIS.md` (the layer has no *domače ime*/BLOK/NUP — those come from the farmer/izpis).
- **Exact behavior change:** the layer imports as a dated GERK snapshot via G2; per-PID geometry/area are available to back Field identities (G1) and partial-extent bounds (G7); failure → refusal trace.
- **Required tests:** a small layer fixture imports as a GERK snapshot; a PID resolves to its geometry/area; missing PID handled governably. (Fixtures only.)
- **Folded-in from G2 review (H2):** as P1 — confirm context-key-drift invalidation suffices for the GERK reference family, or add an explicit broad-stale, before the real scheduled import ships.
- **Acceptance:** SI specifics confined to the package adapter; self-check PASS.
- **Non-goals:** per-farmer government export (open layer + farmer-confirmed PIDs only); personal KMG↔GERK linkage in-repo (D14).

## P3 — FFSNaprave equipment snapshot import

- **Goal:** SI FFSNaprave adapter as package content: yearly TXT/XLS/XML+XSD delimited import through G2 → dated `ReferenceSnapshot`; a farm sprayer matches by sticker number (`StevilkaZnaka` + `VeljavnostZnaka`) and the match populates `EquipmentIdentityPayload.inspectionEvidenceRefs` on the committed Equipment identity (G1).
- **Serves:** M2b-3. **Depends on:** G2, G1.
- **Files likely touched:** SI FFSNaprave adapter config under the package; `kernel/tests/test_m2_si_ffsnaprave.py`.
- **Files NOT to touch:** `kernel/adapters.py`; `contracts/**`.
- **Read first:** `profile_si_ffs/PROFILE.md` (FFS-NAPRAVE row); `profile_si_ffs/M0_DESK_RESEARCH.md` (FFSNaprave item); `contracts/core/OFARM_EquipmentIdentityPayload_schema_v0_1.json`.
- **Exact behavior change:** the yearly file imports as a dated snapshot via G2; a sticker-number match attaches inspection evidence to the Equipment identity; no match → equipment recorded without inspection evidence (advisory, never a silent pass as compliant).
- **Required tests:** a fixture file imports; sticker match attaches evidence; no-match path is governed. (Fixtures only.)
- **Acceptance:** SI specifics in the package; self-check PASS.
- **Non-goals:** the one strong-currentness surface is not a current-compliance claim for the whole pilot (D7).

## P4 — SI bindings (KMG-MID / GERK / REGSR / FFSNaprave / FFS-IZKAZNICA)

- **Goal:** package content binding the SI schemes to the committed identities via `AgronomicIdentityBinding` under the SI code-binding profile, resolved through G3: Farm `holdingIdentifiers` = `SI:KMG-MID`; Field `parcelIdentifiers` = `SI:GERK`; AppliedResource authorisation identity = REGSR decision number; Equipment = `SI:FFS-NAPRAVE` sticker; operator = `SI:FFS-IZKAZNICA`. Unresolved stays explicitly `UNRESOLVED` (advisory, never silent compliance identity).
- **Serves:** slice M2c. **Depends on:** G1, G3, and snapshots from P1–P3.
- **Files likely touched:** SI binding config under the package (scheme→role map already in `OFARM_AgronomicCodeBindingProfile_si_ffs_v0_1.json`); `kernel/tests/test_m2_si_bindings.py`.
- **Files NOT to touch:** `kernel/validators.py`/`sufficiency.py` generic resolution (use G3; no per-scheme branch); `contracts/**`.
- **Read first:** `CORE.md` "code binding discipline"; `profile_si_ffs/PROFILE.md` scheme role map; `profile_si_ffs/OFARM_AgronomicCodeBindingProfile_si_ffs_v0_1.json`; `CAPTURE_MAPPING.md`; D6.
- **Exact behavior change:** each scheme binds through the generic G3 resolution against the right snapshot; identity-grade where the snapshot carries a stable key (REGSR decision number), locator-only otherwise → review; unresolved → `UNRESOLVED` + advisory flag, claim still committable as a draft.
- **Required tests:** each scheme resolves identity-grade or routes correctly; an unknown product → `UNRESOLVED` + advisory, draft retained, promotion requires review.
- **Acceptance:** no scheme-specific logic leaked into Phase-1 modules (boundary check); self-check PASS.
- **Non-goals:** the evidence floor itself (P5); current-compliance.

## P5 — SI evidence floor & advisory behavior

- **Goal:** express `policy:si.ffs.evidence-review.v0_1` as **package/profile content** consumed by the generic sufficiency mechanism: the hard floor (dose-unit, operator, event-time, parcel), soft items (product/crop binding → advisor route), and the authorisation-mismatch + dose-range **advisories** (advisory twin — visible, never blocking, never auto-creating a compliance fact).
- **Serves:** slices M2c/M2e. **Depends on:** G3 (bindings), G5 (advisory/route interplay).
- **Mechanism-boundary note (read this first):** the floor currently lives as constants in `kernel/policy.py` (`OPERATION_FLOOR_HARD_ITEMS`, `OPERATION_FLOOR_SOFT_ITEMS`, and the UCUM allow-list hardening). Per the stop rule, **move the SI floor to profile/package content and have `kernel/sufficiency.py` read it from the active profile generically** — that boundary fix is part of this ticket, done before wiring SI values.
- **Files likely touched:** the SI policy instance under `profile_si_ffs/`; `kernel/sufficiency.py` (read floor from the active profile); `kernel/policy.py` (replace the SI-specific floor constant with a generic default/loader, single-homed); `kernel/tests/test_m2_si_floor.py`.
- **Files NOT to touch:** `contracts/**`; authority semantics.
- **Read first:** `profile_si_ffs/PROFILE.md` evidence/review policy; `kernel/policy.py` (`OPERATION_FLOOR_*`, `is_resolved_ucum_unit`); `kernel/sufficiency.py`; `CORE.md` advisory rule; D7/D8.
- **Exact behavior change:** the floor and advisory rules come from package content through the generic sufficiency builder; an authorisation mismatch or implausible dose raises an advisory and routes to the advisor without blocking; hard-floor failures refuse promotion; soft-floor failures route to review.
- **Required tests:** hard-floor miss refuses; soft-floor miss routes to review; authorisation-mismatch advisory raised and non-blocking; the floor is sourced from package content (changing the package floor changes behavior without touching `kernel/`).
- **Acceptance:** `kernel/` carries no SI-specific floor values after the move; self-check PASS.
- **Non-goals:** new advisory categories beyond the profile; certification-grade review (D8).

## P6 — SI ActiveArtifactSet / ContextSnapshot regeneration

- **Goal:** regenerate `OFARM_ActiveArtifactSet_*` and `OFARM_ContextSnapshot_*` against the **real M2 artifacts** (scheduled snapshots, adapter outputs, OIDC, views) using the generic `kernel/context.py` assembly + `kernel/manifest.py` generation, and re-run the grounding/self-check.
- **Serves:** slice M2c (closing the M2 definition of done). **Depends on:** P1–P5, G4.
- **Files likely touched:** the regenerated `profile_si_ffs/OFARM_ActiveArtifactSet_*` and `OFARM_ContextSnapshot_*` instances (package artifacts); regeneration driven by `kernel/manifest.py` + `kernel/context.py`; `conformance/ofarm_pkg_contract_check.py` re-run.
- **Files NOT to touch:** `contracts/**`; the generic generators' logic beyond what regeneration needs.
- **Read first:** `profile_si_ffs/PROFILE.md` (shipped instances); `kernel/manifest.py`; `kernel/context.py`; `profile_si_ffs/UNSUPPORTED_SURFACES.md`.
- **Exact behavior change:** the regenerated instances reference the real M2 artifacts and validate; manifest grounding re-verifies; the Capability Manifest conformance level stays `NONE` until benchmark evidence exists (explainable-evidence RFC §11.4).
- **Required tests / checks:** `ofarm_pkg_contract_check.py` PASS on the regenerated instances; manifest-grounding check passes; no over-claim above `NONE`.
- **Acceptance:** M2 definition of done met (brief); self-check PASS.
- **Non-goals:** any capability-level claim above `NONE` without benchmark evidence.

---

## Slice → ticket map

| Build-order slice | Generic (Phase 1) | Package (Phase 2) |
|---|---|---|
| M2a — governed structure identities | G1 | — |
| M2b — reference-snapshot adapters | G2, G3 | P1 (M2b-1), P2 (M2b-2), P3 (M2b-3) |
| M2c — code-binding enforcement | G3 | P4, P5, P6 |
| M2d — OIDC principal binding | G4 | — |
| M2e — review verbs & disputes | G5-1, G5-2, G5-3, G5-4 | (P5 advisory interplay) |
| M2f — AS_OF & extent carriers | G6, G7 | (P2 supplies GERK geometry) |

## Dependency order (build sequence)

`G1` → `G2` → `G3` → `P1, P2, P3` → `P4` → `G4` → `G5-1 → G5-2 → G5-3 → G5-4` → `P5` → `G6, G7` → `P6`.

Each arrow is a hard gate: the upstream ticket must be green against the M1 suite plus its own new tests before the downstream ticket starts (brief *Build order*).
