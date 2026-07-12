# M3 brief — platform MVP: capture, sync, review, and governed output refusal

Status: proposed execution brief for M3. This is an implementation/conformance planning artifact, not OFARM law, not a schema or contract promotion, and not a production-readiness claim.

Change class: implementation/product execution on the existing OFARM2 package.

Affected files expected:

- New: `M3_BRIEF.md`.
- New: `M3_TICKETS.md`.
- Likely implementation areas: `kernel/api.py`, `kernel/tests/`, a new `app/` or `frontend/` surface, local deployment scripts/docs, and scenario fixtures.
- Forbidden unless a separate reviewed PR explicitly justifies them: `reference/`, `reference/law/`, extracted contracts, canonical law copies, generated manifests, active artifact sets, Capability Manifest capability expansion, and profile activation changes.

## 1. Starting state

M3 starts from the current OFARM2 implementation package after M1/M2 closure.

Assumed starting facts:

- The Kernel/Core/Platform prototype exists with append-only truth, gate-chain commits, materialization, and SI output surfaces. Its current authentication, persistence, temporal, and output paths predate ADR 0001/0002 and are not M3 runtime foundations.
- M2 has closed the Core-on-Kernel path for repo-facing currentness: governed structure identities, reference snapshots/imports, code bindings, the prototype OIDC/development principal binding, review/dispute verbs, AS_OF reconstruction, and extent-carrier handling. ADR 0001 supersedes that prototype for future tenant-bound M3 runtime work.
- MP7.1–MP7.6 have added route/readiness infrastructure, but the runtime remains single-active-SI. M3 must not activate a second profile.
- E-006 remains deferred: durable Advisory Twin records are not implemented. M3 may display non-blocking advisory/warning result problems, but it must not claim durable `ADVISORY_OUTPUT` records or PassportView `_advisory_flags` unless E-006 is resolved in a separate trace-safe slice.

## 2. M3 target

M3 delivers a bounded capture/sync/review/output-refusal milestone:

> A farmer can enter a plant-protection spray record on a phone/PWA with five primary inputs, offline if needed; sync it through the tenant-bound governed OFARM backend; have the commit pass through authority, validation, profile applicability, evidence sufficiency, and review/promotion; then request the live SI spray-register PassportView or frozen inspection-register DocumentAssembly and receive the correct centralized governed refusal until each output's distinct prerequisites are accepted and activated.

M3 is successful when this works end to end on a real device or browser profile against a local/sandbox deployment using fictional, format-true data.

M3 does not require a real farm, real advisor, official submission, production authentication, or production operations. Those belong to M4 or later.

## 3. Claim boundary

M3 may claim only:

- platform MVP usability for the bounded SI capture, sync, review, and output-refusal loop;
- traceable record-keeping completeness for the fictional/sandbox pilot flow;
- visible refusal and disclosure behavior;
- offline draft/sync behavior through the governed backend;
- non-blocking advisory warnings as result problems, if surfaced honestly.

M3 must not claim:

- current compliance against the authorisation register;
- certification readiness;
- legal advice;
- production readiness;
- cybersecurity certification;
- live-registry integration;
- autonomous review or software-agent review;
- public QuerySpecification authoring;
- dynamic pack installation or profile extension support;
- second-profile activation;
- organic production/runtime readiness;
- official IS Evidenca FFS submission support;
- Capability Manifest level above the current supported claim without generated verification and explicit review.

## 4. MVP users

M3 supports the following MVP users with fictional/synthetic identities:

1. Farmer: asserts operation claims and performs bounded self-review for routine records.
2. Family worker or contractor: submits via DelegationGrant; revocation is rechecked on sync.
3. Advisor: sees exception/review queue for records that cannot self-accept.
4. Read-only inspector/export recipient: may exercise SharingGrant, but the spray-register PassportView and frozen inspection-register DocumentAssembly remain blocked on their separately stated prerequisites.

Real farmers/advisors/inspectors are M4/M5 scope unless the steward explicitly authorizes a privacy-safe shadow trial.

## 5. Product scope

### In scope

- PWA client as the default M3 client choice.
- Local offline draft queue.
- Cached product-register snapshot and farm parcel list.
- Five-input spray capture: Product, Dose, Parcel, Crop, Time, plus optional photo.
- Idempotent sync to the existing commit path.
- Display of `RuntimeProblem`s, warnings, retained-draft decisions, review-required decisions, and accepted decisions.
- Deliberate “confirm & accept” self-review for routine operation claims.
- Advisor exception queue sufficient to accept/reject/contest synthetic cases already supported by backend semantics.
- Output requests through versioned, predefined surfaces only: the NOW-based spray-register PassportView and the WINDOW-based inspection-register DocumentAssembly remain centrally guarded for their distinct dependency gaps.
- Scenario tests proving offline, authority, binding, review, materialization, output, and refusal behavior.

### Out of scope

- Native Flutter unless PWA is proven insufficient.
- Public query builder/compiler.
- AI/agent runtime, voice capture, farm-memory, world models, farm-to-farm intelligence, autonomous execution, dynamic packs, and profile extensions.
- Real personal data or real farm documents.
- Current-compliance decisions from registry snapshots.
- Production auth hardening, backup/restore operations, support desk workflows, billing, multi-tenant administration, or production observability beyond MVP logs.
- A multi-tenant administration product is out of scope, but tenant isolation,
  trusted tenant binding, tenant-qualified persistence, and migration readiness
  are mandatory runtime foundations rather than optional product features.
- Official government filing/submission.
- Second runtime profile activation or organic-on-top-of-SI composition.

## 6. Architecture posture

### Backend

Use the existing FastAPI/Python backend and PostgreSQL truth store. All state-affecting writes must enter through the governed commit/review paths. No UI endpoint may write directly to projections, caches, materialization tables, or report stores.

M3 runtime work is downstream of the accepted package architecture in
`docs/adr/0001-tenancy-and-schema-migrations.md` and
`docs/adr/0002-valid-time-and-knowledge-time.md`. A request operates in one
trusted tenant-bound UnitOfWork; every durable tenant outcome belongs to one
atomic governed write batch and tenant knowledge position. Every governed
current-state read resolves and records one explicit valid instant and tenant
knowledge cut. Historical and high-consequence reads likewise bind both axes
and their exact runtime/context basis. Numbered
migrations, tenant-qualified storage, and the separate pre-tenant operational
security lane are prerequisites where the relevant M3 surface depends on them.
These package-local decisions implement canonical OFARM constraints and do not
amend or promote canonical law.

The backend may add an M3 API façade, but that façade is only transport/product ergonomics. It must preserve canonical commit payloads and route all authoritative effects through `GatePipeline` or the existing governed review/output mechanisms.

### Client

Default client: PWA.

The PWA may store:

- local drafts;
- pending photo/blob references;
- local idempotency keys;
- cached reference snapshots;
- cached parcel/crop/equipment picker data;
- display-only sync results.

The PWA must not store or assert authoritative truth. Offline records are drafts until the server commits them.

### Auth

M3 does not use the existing `X-Acting-Party` fallback or the pre-ADR OIDC shim
as a runtime foundation. Tenant-bound M3 requests start only after #172, #173,
and #174 provide the explicit authentication mode, immutable principal-binding
lifecycle, transaction-bound TenantCapability, same-backend challenge/binder,
transaction-local TenantBinding, request UnitOfWork, forced RLS, and
tenant-qualified persistence. #192 must provide the isolated pre-tenant audit
client and producer integration before tenant-bound endpoints are enabled.

Authentication establishes the exact transport Party and tenant binding; it
never authorizes by role name. `AuthorityGrant`, `DelegationGrant`,
`SharingGrant`, and revocation state remain the authority basis. Missing or
failed foundations are readiness failures, not permission to fall back to a
header, default tenant, or unbound connection.

Only closed security-relevant authentication, verifier, binding, or
pre-binding routing failures classified by ADR 0001 enter the isolated audit
lane. Ordinary unmatched routes/404s are not automatically durable. Failure of
the audit lane never authorizes a request or permits fallback to tenant storage.

### Outputs

No public query authoring is added. The centralized guard lives at the shared
`OutputGenerator` boundary, before a blocked query, materialization,
qualification, assembly, persistence, or release path executes. It covers the
new M3 façade, existing `GET /views/passport/{farm_ref}` and
`POST /views/inspection-register/freeze` routes, and direct service calls.

The two current outputs have different blockers:

- `view:si.ffs.spray-register.passportview.v0_1` is the live NOW-based
  spray-register PassportView. It remains blocked until the current-read path
  resolves and records valid/knowledge cuts and the versioned qualification and
  release surfaces separate stable content qualification from request-time
  permission/redaction.
- `view:si.ffs.inspection-register.documentassembly.v0_1` is the frozen
  WINDOW-based inspection-register DocumentAssembly. Freeze has the shared
  qualification/release blockers plus ADR 0002's carrier selector,
  `EVENT_OCCURRENCE`/`STATE_OVERLAP` window meaning, calendar-date conversion,
  versioned query/plan, and separately governed SI active-artifact replacement.

Until those paths land, the shared guard returns the existing refusal shape
`{"refused": true, "problem": <RuntimeProblem>, "qualification": null}` with
registered reason code `HIGH_CONSEQUENCE_BLOCKED`. A freeze refusal occurs
before any materialization or publication request and creates no partial
DocumentAssembly, frozen-artifact receipt, qualification, published reference,
wrapper, enqueue, or bytes.

Release is a separate future operation and is not exposed by M3 while the
versioned release contract is absent. Once governed, a denied release must
commit its denial decision/receipt at its own `Kreceipt`, while creating no
wrapper, enqueue, handoff, or bytes. If `HIGH_CONSEQUENCE_BLOCKED` cannot
accurately describe a later release denial, reason-code governance is a
prerequisite; M3 must not invent a code.

### Advisory behavior

Default M3 posture: display non-blocking advisory/warning result problems returned by commit/review/output calls.

Do not persist or claim durable Advisory Twin records unless a separate E-006 slice creates a trace-safe advisory emission path with reachability-compatible linkage and an honest evidence/result channel.

## 7. Candidate M3 API surface

Endpoint names are implementation candidates, not new OFARM contracts. Keep payloads canonical and small.

Minimum backend façade:

- `GET /m3/bootstrap` — returns tenant/farm/profile bootstrap state for the logged-in party: farm refs, role/grant summary, current snapshot ids, active profile refs, and supported output refs.
- `GET /m3/reference-cache` — returns the current cache bundle for product, parcel, crop, equipment, and unit pickers, including source `ReferenceSnapshot` refs.
- `POST /m3/draft-assets` — stores pre-authoritative local photo/blob uploads and returns draft asset refs; final EvidenceRecord authority is created only through the governed commit path.
- `POST /commit` or existing equivalent — submits canonical `CommitIngressRequest` payloads with idempotency key and source payload digest.
- `GET /m3/sync-status/{idempotencyKey}` — returns replay/current sync status without creating new truth.
- `POST /review/accept` or existing equivalent — records deliberate self-review/advisor acceptance through the governed review path.
- `POST /review/reject` and `POST /review/contest` if existing backend support is exposed to the M3 exception queue.
- `GET /m3/register/passport` — reaches the shared `OutputGenerator` guard and returns `HIGH_CONSEQUENCE_BLOCKED` for the NOW-based spray-register PassportView while its current-read and qualification/release prerequisites remain unmet.
- `POST /m3/register/document-assembly/freeze` — reaches the same shared guard and returns `HIGH_CONSEQUENCE_BLOCKED` before the WINDOW query/materialization/publication path; it may freeze only after its additional temporal and active-artifact prerequisites are accepted and activated.

No M3 release endpoint is exposed until the versioned release contract can
record `Kauth`, `Kreceipt`, the denial decision/receipt, and the required digest
bindings without semantic distortion.

Stop if any endpoint requires new law, hidden profile selection, direct projection writes, request-chosen profile law, or a current-compliance claim.

### Runtime dependency order

| M3 surface | Must land first |
|---|---|
| Any tenant-bound M3 endpoint | #172 authentication and TenantCapability; #173 request UnitOfWork/binding; #174 migrations, RLS, tenant-qualified storage, and binding primitives; #192 isolated pre-tenant audit integration; governed-batch/knowledge-position portion of #176 |
| M3.1 output exposure | The centralized M3.6 `OutputGenerator` guard and its route/direct-call regression tests; output helpers stay out of M3.1 until this exists |
| M3.3–M3.5 temporal behavior | Applicable #176 valid-time carrier and governed replacement-set behavior |
| Spray-register PassportView success | #176 current-read dual cuts; versioned stable content-qualification and release surfaces; #177, #181, and #182 as applicable |
| Inspection-register DocumentAssembly freeze success | All shared output dependencies plus ADR 0002 carrier/window/date semantics, versioned contracts, #177/#181/#182, and separately governed SI query/plan and active-artifact replacement |

The centralized M3.6 guard is the first M3 runtime change. M3.1 may expose
tenant-bound bootstrap/cache/status/commit/review helpers only after its
foundation row is green, and may not expose any output helper until that guard
is installed. Successful outputs are later completion gates, not M3 completion
claims.

## 8. Ordered implementation slices

Each slice should be a narrow PR with: goal, touched files, forbidden files, behavior change, tests, validation commands, non-claims, and rollback/stop conditions.

### M3.0 — Brief, baseline, and ticket map

Allowed change:

- Add `M3_BRIEF.md` and `M3_TICKETS.md`.
- Record the current M2/MP7/E-006 boundaries.
- Run the baseline checks and record whether they pass.

Required proof:

- `python3 conformance/ofarm_pkg_contract_check.py`
- `.venv/bin/python -m pytest kernel/tests/ -q`
- `.venv/bin/python -m kernel.manifest --verify-generated`
- `python3 conformance/ofarm_profile_runtime_readiness_check.py`
- `git diff --check`

Stop if:

- the brief changes law, contracts, manifests, active artifact sets, profile activation, or capability claims.

### M3.1 — Minimal backend API façade

Allowed change:

- After #172/#173/#174/#192 and the governed-batch/knowledge-position portion
  of #176 are green, add tenant-bound M3 façade endpoints over governed backend
  behavior.
- Return bootstrap/cache/status data needed by the PWA.
- Preserve canonical commit/review payloads. Output helpers remain excluded
  until the centralized M3.6 guard is installed.

Required proof:

- API tests show no direct authoritative writes outside governed paths.
- API tests prove rejected/retained/accepted outcomes are surfaced as machine-readable `RuntimeProblem`/result payloads.
- Transport principal still binds to Party; role name alone never authorizes.

Stop if:

- API code bypasses `GatePipeline`, review governance, materializer freshness rules, or output qualification.
- any path uses `X-Acting-Party`, a default tenant, an unbound connection, or
  exposes an output helper before the M3.6 shared-service guard exists.

### M3.2 — PWA shell, local draft queue, and reference cache

Allowed change:

- Add PWA skeleton with local draft store.
- Add offline cache for product snapshot, parcel list, crop defaults, equipment defaults, and current snapshot ids.
- Add local idempotency key generation and retry state.

Required proof:

- Offline draft survives reload and sync retry.
- Same idempotency key replay returns the prior result rather than creating duplicate truth.
- Cached reference data is displayed with snapshot identity.

Stop if:

- local cache is treated as authoritative current state.
- draft edits after server commit mutate server truth instead of creating a new correction/supersession path.

### M3.3 — Five-input spray capture

Allowed change:

- Implement capture screen for Product, Dose, Parcel, Crop, Time, optional Photo.
- Auto-populate all non-farmer-facing fields from app state, active profile constants, cached snapshots, and session identity.
- Enforce that event time and record time remain distinct.

Required proof:

- UI test or scenario test proves a routine spray record can be prepared without required free-text fields beyond the five planned inputs.
- Generated commit payload maps to the expected contract destinations.
- Capture target is measured: five consecutive fictional records each entered in 90 seconds or less, or the failure is recorded with UX findings.

Stop if:

- the farmer is asked to type KMG-MID, GERK, profile refs, policy refs, schema refs, or other auto-populated governance fields per record.

### M3.4 — Sync, refusal, and advisory/warning display

Allowed change:

- Sync queued drafts to backend.
- Display outcomes: replay, retained draft, review required, denied, accepted, warnings.
- Show advisory warnings as warnings only; never as compliance facts.

Required proof:

- Unresolved product binding remains explicit and visible.
- Changed/stale reference snapshot routes to review or warning per policy, never silent acceptance.
- Revoked delegation on offline sync denies/reviews governably.
- Advisory warning does not enter Compliance materialization.

Stop if:

- warnings block or promote compliance state without governed policy.
- unresolved bindings are hidden or coerced into resolved compliance identities.

### M3.5 — Review and exception queue

Allowed change:

- Expose deliberate self-review accept for routine operation claims.
- Expose advisor queue for retained/review-required synthetic exceptions.
- Expose reject/contest only if already supported by backend semantics and tests.

Required proof:

- Self-review works only within the bounded policy for routine operation claims.
- Distinct reviewer is required where self-review is not allowed.
- REJECT/CONTEST, if exposed, preserve append-only semantics and do not edit queued assertions or in-force consequences.
- Review/reject/contest preserve the underlying fact's valid-time carrier and
  bounds. A correction may change valid time only through a complete governed
  replacement set, including left/corrected/right slices for an interval or a
  corrected point where applicable; it never edits the prior fact.

Stop if:

- “review” becomes a UI flag without `ReviewDecision`, authority trace, and PromotionTrace linkage.

### M3.6 — Centralized output guards and governed refusals

Allowed change:

- Add one shared `OutputGenerator` guard before blocked query, materialization,
  qualification, assembly, persistence, or release work.
- For `view:si.ffs.spray-register.passportview.v0_1`, return the registered
  `HIGH_CONSEQUENCE_BLOCKED` RuntimeProblem in the existing refusal shape while
  NOW/current-read dual-cut and qualification/release prerequisites are absent.
- For `view:si.ffs.inspection-register.documentassembly.v0_1`, refuse freeze
  with the same registered code and response shape before publication state is
  written, while the additional WINDOW carrier/meaning/date and SI artifact
  prerequisites are absent.
- Do not expose release. A future denied release records its denial receipt at
  `Kreceipt` but emits no wrapper, enqueue, handoff, or bytes.

Required proof:

- The M3 façade, both existing `/views/**` routes, and direct `OutputGenerator`
  calls all reach the same guard.
- PassportView refusal does not execute its NOW query, materialize, qualify, or
  render and does not claim the DocumentAssembly WINDOW defect.
- Freeze refusal creates no publication request/result, DocumentAssembly,
  frozen-artifact receipt, qualification, export artifact, published reference,
  wrapper, enqueue, or bytes.
- The exact response is `{"refused": true, "problem": <RuntimeProblem with
  reasonCode HIGH_CONSEQUENCE_BLOCKED>, "qualification": null}`.
- No release surface exists. A later release-denial test must prove its denial
  decision/receipt commits at `Kreceipt` while delivery side effects remain absent.

Stop if:

- the output UI renders a clean register when the governed output path refuses or qualifies it.
- an endpoint or direct service call can bypass the centralized guard.
- freeze refusal and release denial are represented as the same operation or
  M3 invents an unregistered reason code.

### M3.7 — End-to-end MVP scenario runner

Allowed change:

- Add scenario tests or scripted demo runs for the full capture-to-centralized-refusal path.
- Produce an M3 demo run record only if clearly labeled as M3 demo evidence, not root platform conformance evidence and not profile executed evidence.

Required scenarios:

1. Bootstrap fictional farm and cache refs.
2. Capture routine spray offline.
3. Sync and self-review to accepted.
4. Request the live spray-register PassportView and receive the centralized `HIGH_CONSEQUENCE_BLOCKED` refusal without executing its NOW/current-read or qualification path.
5. Request inspection-register DocumentAssembly freeze and receive the centralized `HIGH_CONSEQUENCE_BLOCKED` refusal before its WINDOW/materialization/publication path, with no partial output state or bytes.
6. Replay same idempotency key without duplicate truth.
7. Revoked worker sync refuses or routes governably.
8. Product binding mismatch raises warning/review without creating a compliance fact.
9. Missing/stale/disputed basis refuses a clean output.
10. Privacy audit passes: no real identifiers, names, document filenames, addresses, dates, or images.
11. At the same valid cut and `Kcontent`, replay reproduces the same historical
    basis, content/result, and stable content-qualification digests; a new
    request independently reevaluates `Kauth`, permission/redaction, wrapper or
    denial, and commits its own `Kreceipt` when the governed release path exists.

Stop if:

- demo evidence is mislabeled as conformance evidence, profile evidence, production evidence, or capability-manifest grounding.

### M3.8 — Minimal deployment envelope

Allowed change:

- Add local/sandbox deployment instructions for the completed #172/#173/#174
  authentication, TenantCapability, TenantBinding, UnitOfWork, migration, and
  RLS architecture; no development-header fallback.
- Include seeded fictional data only.
- Include operational notes for resetting the sandbox.

Required proof:

- A fresh contributor can run the backend, load fictional data, open the PWA, capture/sync/review one record, exercise the governed register/freeze refusals, and re-run the baseline checks.

Stop if:

- deployment docs imply production readiness, real-farm onboarding, legal compliance, or official filing readiness.

## 9. Acceptance test matrix

| ID | Scenario | Required outcome |
| --- | --- | --- |
| M3-T01 | Bootstrap logged-in farmer | Returns farm/profile/cache context without granting authority by role name alone. |
| M3-T02 | Offline routine spray capture | Local draft persists, has idempotency key, records event time separately from server record time. |
| M3-T03 | Idempotent sync replay | Retrying the same draft returns prior result; no duplicate authoritative records. |
| M3-T04 | Routine self-review accept | Accepted consequence emitted only after governed review; register materializes from in-force basis. |
| M3-T05 | Unresolved product | Binding remains `UNRESOLVED`; UI shows warning/review path; no silent compliance identity. |
| M3-T06 | Reference snapshot drift | Sync re-verifies against current snapshot and records discrepancy/review/warning, not silent accept. |
| M3-T07 | Revoked delegation | Worker’s offline draft synced after revocation denies or routes governably. |
| M3-T08 | Advisory boundary | Warning visible; no Advisory material enters Compliance materialization. |
| M3-T09 | Centralized blocked outputs | Spray-register PassportView and inspection-register freeze return the exact `HIGH_CONSEQUENCE_BLOCKED` refusal through façade, existing routes, and direct service calls; no blocked work or partial output state executes. Release is not exposed. |
| M3-T10 | Privacy audit | Fixtures and run records contain fictional, format-true data only. |
| M3-T11 | No direct projection writes | Tests prove UI/API cannot write authoritative facts into derived tables/caches. |
| M3-T12 | Claim honesty | Docs, UI labels, manifests, and evidence files do not claim production/current-compliance/certification readiness. |

## 10. Validation commands

Baseline for every M3 backend PR:

```sh
python3 conformance/ofarm_pkg_contract_check.py
.venv/bin/python -m pytest kernel/tests/ -q
.venv/bin/python -m kernel.manifest --verify-generated
python3 conformance/ofarm_profile_runtime_readiness_check.py
git diff --check
git diff --cached --check
```

Additional frontend/PWA commands should be added after the PWA stack is created. Use the smallest stable set, for example:

```sh
npm test
npm run lint
npm run build
```

Only include these once the corresponding project exists.

## 11. Evidence and reporting rules

- Root `conformance/evidence/platform_mvp_results_*.json` remains the root platform MVP evidence lane only.
- Profile-local engineering tests remain engineering coverage unless a future profile executed-evidence lane is deliberately implemented.
- M3 demo run records, if added, must be clearly labeled as M3 demo/product evidence, not conformance evidence, profile evidence, production evidence, or manifest grounding.
- If running pytest creates a timestamped platform evidence file unintentionally, keep it only when the PR intentionally updates platform evidence and the suite meaning remains honest. Otherwise remove it before commit.
- Do not change Capability Manifest claims unless generated or generator-verified grounding proves the exact new runtime surface.

## 12. Stop conditions for the whole M3 track

Stop and re-plan if a PR would:

- edit OFARM law or extracted reference files;
- promote draft/candidate schemas or contracts;
- activate a second runtime profile;
- implement organic/profile-extension semantics;
- make a current-compliance, certification, production-readiness, legal-advice, or official-filing claim;
- use real personal/farm data in the repo;
- let UI, cache, projection, or report storage become authoritative truth;
- bypass GatePipeline/review/materialization/output qualification;
- collapse event time, record time, assertion time, or effective time;
- hide unresolved bindings, stale state, open disputes, or missing evidence;
- let advisory warnings become Compliance Twin materialization inputs;
- expose public query authoring, dynamic packs, AI/agent runtime, voice capture, farm memory, farm-to-farm intelligence, or other unsupported Platform v1 surfaces;
- broaden generated manifests or active artifact sets without generator verification and explicit review.

## 13. MVP definition of done

M3 is done when all of the following are true:

1. `M3_BRIEF.md` and the ticket map are committed.
2. A fresh contributor can run the local/sandbox backend and PWA.
3. The PWA can bootstrap fictional farm context and cache reference data.
4. The PWA can capture a routine spray record with five primary inputs plus optional photo.
5. The draft can be captured offline, synced later, and retried idempotently.
6. A routine record can pass through governed self-review and promote to accepted state.
7. Exceptions are visible and route to retained draft, review, denial, or warning without silent acceptance.
8. The live spray-register PassportView and frozen inspection-register DocumentAssembly refuse centrally for their distinct blockers; release is not exposed.
9. The M3 scenario runner or manual acceptance script proves the end-to-end flow with fictional data.
10. Baseline backend checks pass.
11. Frontend tests/build pass once the PWA exists.
12. Privacy audit passes.
13. Claim limits remain unchanged: record-keeping completeness only; no current-compliance, certification, production, official-filing, second-profile, or durable-advisory-output claim unless separately implemented and reviewed.

## 14. First ticket to open

Title: `M3.0 — Add platform MVP brief and ticket map`

Goal:

- Add this brief as `M3_BRIEF.md`.
- Add `M3_TICKETS.md` with the ordered M3.0–M3.8 ticket stubs.
- Record the E-006 default posture: M3 displays warning result problems only; durable Advisory Twin output remains deferred unless a separate implementation slice resolves it.

Validation:

```sh
python3 conformance/ofarm_pkg_contract_check.py
python3 conformance/ofarm_profile_extraction_consistency_check.py
git diff --check
git diff --cached --check
```

Non-claims:

- No runtime behavior change.
- No app implementation.
- No evidence writing.
- No manifest, active artifact set, schema, contract, profile activation, or capability-claim change.
- No production, current-compliance, certification, legal-advice, or official-filing readiness claim.
