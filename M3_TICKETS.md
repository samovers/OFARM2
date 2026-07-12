# M3 implementation tickets - platform MVP

Companion to `M3_BRIEF.md`. This is a planning and execution-control document for the M3 platform MVP track. It is not OFARM law, not a schema or contract promotion, not generated evidence, and not a production-readiness claim.

M3 is claim-limited to the fictional/sandbox SI plant-protection record-keeping MVP loop: phone/PWA capture, offline draft, governed sync, review/promotion, materialized register view, and honest refusal/disclosure. It does not claim current compliance, certification readiness, legal advice, production readiness, official filing support, second-profile activation, profile-extension support, organic runtime readiness, or durable Advisory Twin output.

Endpoint names in `M3_BRIEF.md` are implementation candidates only and do not create public API commitments in M3.0.

E-006 remains deferred. M3 may display non-blocking warning result problems returned by governed calls, but it must not claim durable `ADVISORY_OUTPUT` records or PassportView `_advisory_flags` unless a separate trace-safe slice resolves E-006.

## Forward-development conformance baseline

These tickets are implementation control, not canonical OFARM law. Before an
M3 runtime ticket starts, its design and acceptance evidence must remain
conformant with the digest-pinned canonical material in `reference/` and with
the package-local implementation decisions in `DECISIONS.md` and
`docs/adr/0001-tenancy-and-schema-migrations.md` / `0002-valid-time-and-knowledge-time.md`.
The ADRs narrow how this package implements canonical OFARM; they do not amend,
promote, or replace canonical law.

The forward tickets share these hard requirements:

- Canonical truth remains assertion/history-first. Drafts, caches, imports,
  projections, materializations, UI state, and generated outputs never become
  truth merely because they exist.
- Every authoritative or evidence-bearing tenant write is atomic inside one
  tenant-scoped governed write batch after trusted tenant binding. No default,
  request-chosen, or inferred tenant is allowed.
- Tenant-owned and tenant-bearing derived state uses tenant-qualified identity,
  references, idempotency, locks, traces, caches, and output keys. Cross-tenant
  references and disclosure fail closed.
- Historical or high-consequence reads bind both an authoritative valid-time
  cut and a tenant knowledge position, plus the exact runtime and governed
  context basis. Wall-clock record, capture, assertion, acceptance, or decision
  time never substitutes for either axis.
- Database schema readiness comes from immutable numbered migrations and their
  migration ledger, not application-startup DDL or a record contract version.
- Pre-tenant authentication or routing failures never enter tenant history.
  They use only the separately governed operational-security lane defined by
  ADR 0001; a ticket must stop if that lane is unavailable rather than invent a
  default tenant or reuse a tenant table.
- Claim limits remain record-keeping completeness for fictional/sandbox use:
  no current-compliance, certification, official filing, production-readiness,
  or capability-level claim follows from completing an M3 ticket.

If an M3 ticket conflicts with this baseline, the ticket must be revised before
implementation. Passing a UI or scenario test does not waive a canonical or
package-architecture stop condition.

## How to work an M3 ticket

1. One ticket should be one narrow PR unless the steward explicitly approves a split or merge.
2. Read the ticket's **Read first** list before writing code.
3. Do not touch anything in **Forbidden files** unless a separate reviewed PR explicitly justifies the change.
4. All authoritative writes must enter through the governed commit, review, materialization, or output paths.
5. Fixtures and demo records must be fictional and format-true. No real people, farms, documents, identifiers, addresses, dates, filenames, or images.
6. Keep M3 demo/product evidence separate from root platform conformance evidence and profile executed evidence.
7. Stop and re-plan when a ticket would change law, contracts, manifests, profile activation, capability claims, or claim boundaries.

Ticket field key: **Status · Goal · Likely touched files · Forbidden files · Read first · Behavior change · Required tests · Acceptance criteria · Non-goals · Stop conditions · Validation.**

---

## M3.0 - Add platform MVP brief and ticket map

Status: implemented by this docs-only PR / no runtime behavior.

Goal:

- Add `M3_BRIEF.md`.
- Add this `M3_TICKETS.md`.
- Record the M3 claim boundary and E-006 default posture before implementation begins.

Likely touched files:

- `M3_BRIEF.md`
- `M3_TICKETS.md`

Forbidden files:

- `reference/`
- `contracts/`
- `conformance/evidence/`
- generated manifests
- active artifact sets
- profile descriptors or activation files
- runtime code
- PWA/frontend code

Read first:

- `AGENTS.md`
- `README.md`
- `M2_BRIEF.md`
- `M2_TICKETS.md`
- `M3_BRIEF.md`

Behavior change:

- None. This is a documentation-only control slice.

Required tests:

- Baseline validation only.
- No new runtime, API, schema, manifest, profile, or frontend tests.

Acceptance criteria:

- Only `M3_BRIEF.md` and `M3_TICKETS.md` are added.
- `M3_BRIEF.md` lists `M3_TICKETS.md` as a new file, not an optional future file.
- This ticket map includes M3.0 and the planned M3.1-M3.8 tickets.
- No evidence files, generated files, manifests, active artifact sets, contracts, reference files, or runtime files are changed.

Non-goals:

- No runtime behavior.
- No app implementation.
- No API commitments.
- No evidence update.
- No contract, manifest, profile activation, or capability-claim change.

Stop conditions:

- Stop if the slice would edit law, contracts, manifests, active artifact sets, profile activation, runtime behavior, or capability claims.
- Stop if validation produces files that would broaden the M3.0 diff beyond the two root docs.

Validation:

- `python3 conformance/ofarm_pkg_contract_check.py`
- `python3 conformance/ofarm_profile_extraction_consistency_check.py`
- `.venv/bin/python -m pytest kernel/tests/ -q`
- `.venv/bin/python -m kernel.manifest --verify-generated`
- `python3 conformance/ofarm_profile_runtime_readiness_check.py`
- `git diff --check`
- `git diff --cached --check`
- `git status --short`

---

## M3.1 - Minimal backend API facade

Status: planned.

Goal:

- Add the smallest backend facade needed by the PWA to bootstrap, cache references, check sync status, and access predefined outputs.
- Preserve canonical commit, review, materialization, and output behavior.

Likely touched files:

- `kernel/api.py`
- `kernel/tests/test_m3_api.py`
- small support modules only if existing API structure requires them

Forbidden files:

- `reference/`
- `contracts/`
- generated manifests
- active artifact sets
- profile activation files
- direct projection/cache/report writers

Read first:

- `M3_BRIEF.md`
- `docs/adr/0001-tenancy-and-schema-migrations.md`
- `docs/adr/0002-valid-time-and-knowledge-time.md`
- `kernel/api.py`
- `kernel/gates.py`
- `kernel/stages.py`
- `kernel/materializer.py`
- `kernel/auth_oidc.py`
- `docs/REVIEW_DISPUTE_SEMANTICS.md`

Behavior change:

- Expose product-facing read/status/output helpers over existing governed behavior.
- Keep `/commit` and review calls canonical.
- Keep transport principal binding to Party; role names alone never authorize.

Required tests:

- Facade endpoints do not create authoritative truth outside governed paths.
- Rejected, retained, review-required, accepted, and warning outcomes are machine-readable.
- Role claims without grants do not authorize farm-scoped actions.
- A trusted tenant binding lasts exactly one request UnitOfWork; caller input
  cannot choose or replace it, and tenant-scoped identifiers and idempotency do
  not collide across tenants.
- Durable endpoint outcomes share the request's governed batch and knowledge
  position; pre-tenant failures create no tenant record, trace, or batch.

Acceptance criteria:

- PWA bootstrap/cache/status needs are served without bypassing `GatePipeline`, review governance, materializer freshness, or output qualification.
- Candidate endpoint names remain implementation-local and do not become promoted contracts.

Non-goals:

- No public query builder.
- No new schema or contract promotion.
- No current-compliance or production-readiness claim.

Stop conditions:

- Stop if an endpoint writes directly to projections, caches, materialization tables, or report stores.
- Stop if request-chosen profile law or hidden profile selection is needed.
- Stop if the required tenant binding, UnitOfWork, governed-batch, numbered-
  migration, or pre-tenant audit foundations are not implemented and green.

Validation:

- `.venv/bin/python -m pytest kernel/tests/ -q`
- `python3 conformance/ofarm_pkg_contract_check.py`
- `python3 conformance/ofarm_profile_runtime_readiness_check.py`
- `.venv/bin/python -m kernel.manifest --verify-generated`
- `git diff --check`

---

## M3.2 - PWA shell, local draft queue, and reference cache

Status: planned.

Goal:

- Add the PWA shell with local offline drafts, cached picker data, local idempotency keys, and sync retry state.

Likely touched files:

- a new `app/` or `frontend/` surface
- frontend tests
- minimal local development docs for the new app surface

Forbidden files:

- `reference/`
- `contracts/`
- generated manifests
- active artifact sets
- profile activation files
- backend authoritative write paths except through M3.1 endpoints when needed

Read first:

- `M3_BRIEF.md`
- `docs/adr/0001-tenancy-and-schema-migrations.md`
- `docs/adr/0002-valid-time-and-knowledge-time.md`
- `profile_si_ffs/PROFILE.md`
- `profile_si_ffs/UNSUPPORTED_SURFACES.md`
- `kernel/api.py`
- `kernel/auth_oidc.py`

Behavior change:

- A user can load the PWA, cache fictional farm/reference context, create offline drafts, reload, and retry sync later.
- Local cache and drafts remain non-authoritative until the server commits them.

Required tests:

- Offline draft survives reload.
- Cached reference data displays snapshot identity.
- Retry state preserves the same idempotency key.
- Draft edits after server acceptance create a new correction/supersession path instead of mutating server truth.
- Local drafts, caches, and retry keys are partitioned by the trusted session's
  tenant and principal context and are cleared or made inaccessible when that
  context changes.

Acceptance criteria:

- The PWA can be run locally against the sandbox backend.
- The frontend validation command set is documented once the stack exists.

Non-goals:

- No native Flutter client.
- No production auth hardening.
- No real farm data or real documents.

Stop conditions:

- Stop if local cache is treated as authoritative current state.
- Stop if frontend code needs direct database/projection access.
- Stop if tenant context is accepted from editable draft data or one tenant's
  local state can be displayed or submitted under another tenant binding.

Validation:

- Backend baseline validation from M3.1.
- Add stable frontend commands after the PWA stack exists, such as test, lint, and build.
- `git diff --check`

---

## M3.3 - Five-input spray capture

Status: planned.

Goal:

- Implement the capture flow for Product, Dose, Parcel, Crop, Time, plus optional Photo.
- Auto-populate governance fields from app state, active profile context, cached snapshots, and session identity.

Likely touched files:

- PWA capture components and state
- frontend tests
- backend fixture/scenario tests only where needed to verify payload mapping

Forbidden files:

- `reference/`
- `contracts/`
- generated manifests
- active artifact sets
- profile activation files
- backend policy shortcuts

Read first:

- `M3_BRIEF.md`
- `docs/adr/0001-tenancy-and-schema-migrations.md`
- `docs/adr/0002-valid-time-and-knowledge-time.md`
- `CAPTURE_MAPPING.md`
- `profile_si_ffs/SI_RECORD_FIELDS.md`
- `profile_si_ffs/PROFILE.md`
- `kernel/contracts.py`
- `kernel/tests/test_profile_si_demo_payloads.py`

Behavior change:

- A routine fictional spray record can be prepared from five primary user inputs.
- Event time and server record time remain distinct.
- Governance identifiers are not typed by the farmer per record.

Required tests:

- Routine spray draft can be prepared without required free-text fields beyond the five planned inputs.
- Generated commit payload maps to expected contract destinations.
- Generated payload selects the governed valid-time carrier for the represented
  act; capture time, local persistence time, sync time, and server record time
  cannot silently supply occurrence or effective time.
- Five consecutive fictional records can be entered in 90 seconds or less, or the failure is recorded with UX findings.

Acceptance criteria:

- Capture is usable on a phone-sized viewport.
- Optional photo remains draft/pre-authoritative until governed commit evidence handling accepts it.

Non-goals:

- No voice capture.
- No AI/agent runtime.
- No current-compliance decision.

Stop conditions:

- Stop if users must type KMG-MID, GERK, profile refs, policy refs, schema refs, or other governance fields per record.
- Stop if event time, record time, assertion time, or effective time are collapsed.
- Stop if a required valid-time carrier is absent, contradictory, or inferred
  from capture, sync, ingestion, assertion, acceptance, decision, or record time.

Validation:

- Frontend test/lint/build once available.
- Backend payload/scenario tests where touched.
- `git diff --check`

---

## M3.4 - Sync, refusal, and advisory/warning display

Status: planned.

Goal:

- Sync queued drafts to the governed backend.
- Display replay, retained draft, review required, denied, accepted, and warning outcomes honestly.

Likely touched files:

- PWA sync state and result display
- backend M3 API tests
- scenario fixtures for sync outcomes

Forbidden files:

- `reference/`
- `contracts/`
- generated manifests
- active artifact sets
- profile activation files
- Compliance materialization inputs for advisory warnings

Read first:

- `M3_BRIEF.md`
- `docs/adr/0001-tenancy-and-schema-migrations.md`
- `docs/adr/0002-valid-time-and-knowledge-time.md`
- `kernel/problems.py`
- `kernel/gates.py`
- `kernel/sufficiency.py`
- `kernel/profile_policy.py`
- `profile_si_ffs/evidence_review_policy_v0_1.json`

Behavior change:

- Offline drafts sync idempotently and show governed outcomes.
- Unresolved bindings, stale snapshots, revoked delegation, and advisory warnings are visible.
- Advisory warnings are warnings only, not compliance facts.

Required tests:

- Same idempotency key replay returns the prior result without duplicate truth.
- Unresolved product binding remains explicit and visible.
- Reference snapshot drift routes to warning/review/refusal per policy, not silent acceptance.
- Revoked worker sync denies or routes governably.
- Advisory warning does not enter Compliance materialization.
- A committed refusal, acceptance, or warning-bearing result is visible only
  with its complete tenant batch; retries preserve tenant/principal-scoped
  idempotency and never create a second knowledge position.

Acceptance criteria:

- Users can understand whether a record was accepted, retained, denied, routed to review, replayed, or accepted with warnings.

Non-goals:

- No durable Advisory Twin output.
- No autonomous review.
- No live-registry current-compliance claim.

Stop conditions:

- Stop if warnings block or promote compliance state without governed policy.
- Stop if unresolved bindings are hidden or coerced into resolved identities.

Validation:

- `.venv/bin/python -m pytest kernel/tests/ -q`
- Frontend test/lint/build once available.
- `python3 conformance/ofarm_pkg_contract_check.py`
- `git diff --check`

---

## M3.5 - Review and exception queue

Status: planned.

Goal:

- Expose deliberate self-review for routine operation claims.
- Expose an advisor exception queue for synthetic retained/review-required cases already supported by backend semantics.

Likely touched files:

- PWA review/queue components
- `kernel/api.py` only if existing review endpoints need product-facing exposure
- review-focused frontend and backend tests

Forbidden files:

- `reference/`
- `contracts/`
- generated manifests
- active artifact sets
- profile activation files
- authority semantics

Read first:

- `M3_BRIEF.md`
- `docs/adr/0001-tenancy-and-schema-migrations.md`
- `docs/adr/0002-valid-time-and-knowledge-time.md`
- `docs/REVIEW_DISPUTE_SEMANTICS.md`
- `kernel/tests/test_m2_review.py`
- `kernel/stages.py`
- `kernel/emission.py`
- `kernel/authority.py`

Behavior change:

- Routine records can be deliberately self-accepted only where policy allows.
- Exceptions can be accepted, rejected, or contested only when existing backend semantics support that action.

Required tests:

- Self-review works only within bounded policy.
- Distinct reviewer is required where self-review is not allowed.
- Reject/contest preserve append-only semantics and do not edit queued assertions or in-force consequences.
- Review, correction, rejection, and contest outcomes preserve the original
  valid-time meaning while receiving their own atomic tenant knowledge position.

Acceptance criteria:

- Review UI state maps to actual `ReviewDecision`, authority trace, and `PromotionTrace` linkage.

Non-goals:

- No software-agent review.
- No new review semantics hidden in UI code.
- No production advisor workflow.

Stop conditions:

- Stop if review becomes only a UI flag without governed review records and trace linkage.
- Stop if role name alone authorizes review.

Validation:

- `.venv/bin/python -m pytest kernel/tests/ -q`
- Frontend test/lint/build once available.
- `python3 conformance/ofarm_pkg_contract_check.py`
- `git diff --check`

---

## M3.6 - Governed inspection-register output refusal

Status: planned.

Goal:

- Return a governed unsupported/refusal outcome for the active SI inspection-register PassportView while its v0.1 WINDOW query/plan lacks ADR 0002's required carrier and window-meaning surfaces.
- Return a governed unsupported/refusal outcome for inspection-register DocumentAssembly freeze/release while ADR 0002's required versioned contracts, temporal carrier/window semantics, qualification/release surfaces, and SI query/plan artifacts remain unavailable.
- Refuse or disclose unsupported output states.

Likely touched files:

- PWA register/freeze refusal views
- backend output facade tests
- scenario fixtures for output qualification

Forbidden files:

- `reference/`
- `contracts/`
- generated manifests
- active artifact sets
- profile activation files
- public query authoring

Read first:

- `M3_BRIEF.md`
- `docs/adr/0001-tenancy-and-schema-migrations.md`
- `docs/adr/0002-valid-time-and-knowledge-time.md`
- `PLATFORM.md`
- `views/VIEWS.md`
- `profile_si_ffs/views/VIEWS.md`
- `kernel/views.py`
- `kernel/materializer.py`

Behavior change:

- SI inspection-register PassportView and DocumentAssembly freeze/release requests return governed unsupported/refusal outcomes without reinterpreting the v0.1 artifact identities.

Required tests:

- A register-view request does not render a clean PassportView or reinterpret the v0.1 query/plan identities.
- A freeze request produces no DocumentAssembly, wrapper, receipt, enqueue, or released bytes and identifies the unmet ADR 0002 governance dependency.
- Both outcomes identify the unmet dependency without claiming canonical, profile, or runtime conformance.

Acceptance criteria:

- The UI renders neither a clean SI inspection register nor a frozen/released assembly while the governed output path refuses it.
- Inspection-register view and freeze/release remain unavailable until a separate reviewed governance change provides and activates every ADR 0002 prerequisite.

Non-goals:

- No public query builder/compiler.
- No official government filing.
- No production export workflow.

Stop conditions:

- Stop if output UI bypasses the governed unsupported/refusal outcome.
- Stop if stale, disputed, missing-basis, or incomplete states are hidden.
- Stop if this ticket adds or reinterprets temporal fields, applies new semantics to the v0.1 query/plan identities, renders a clean SI inspection register, or emits any frozen/released artifact before the separate contract and active-artifact governance path is complete.

Validation:

- `.venv/bin/python -m pytest kernel/tests/ -q`
- Frontend test/lint/build once available.
- `python3 conformance/ofarm_pkg_contract_check.py`
- `.venv/bin/python -m kernel.manifest --verify-generated`
- `git diff --check`

---

## M3.7 - End-to-end MVP scenario runner

Status: planned.

Goal:

- Add scenario tests or scripted demo runs for the full phone-to-register path using fictional, format-true data.

Likely touched files:

- scenario runner or demo scripts
- scenario fixtures
- backend/frontend test harness files
- M3 demo run docs if needed

Forbidden files:

- `reference/`
- `contracts/`
- generated manifests
- active artifact sets
- profile activation files
- root platform conformance evidence unless separately approved

Read first:

- `M3_BRIEF.md`
- `docs/adr/0001-tenancy-and-schema-migrations.md`
- `docs/adr/0002-valid-time-and-knowledge-time.md`
- `conformance/CONFORMANCE.md`
- `conformance/evidence/README.md`
- `kernel/demo.py`
- existing profile SI demo tests

Behavior change:

- A repeatable local/sandbox scenario proves bootstrap, offline capture, sync, review, governed register/freeze refusals, replay, revoked delegation, binding mismatch, and privacy audit.

Required tests:

- Bootstrap fictional farm and cache refs.
- Capture routine spray offline.
- Sync and self-review to accepted.
- Request the SI inspection-register PassportView and receive the governed unsupported/refusal outcome without rendering a clean register.
- Request DocumentAssembly freeze and receive the governed unsupported/refusal outcome with no artifact or released bytes.
- Replay idempotency key without duplicate truth.
- Revoked worker sync refuses or routes governably.
- Product binding mismatch warns/reviews without compliance fact.
- Missing/stale/disputed basis refuses a clean output.
- Privacy audit finds no real identifiers or documents.
- Isolation scenarios cover cross-tenant identifiers, references, idempotency,
  caches, traces, and outputs; temporal scenarios replay the same valid and
  knowledge cuts and obtain the same qualified result.

Acceptance criteria:

- Demo evidence is labeled as M3 demo/product evidence only.
- Scenario can be rerun locally without real data or live services.

Non-goals:

- No production evidence.
- No profile executed-evidence lane.
- No Capability Manifest grounding.

Stop conditions:

- Stop if demo output is mislabeled as conformance evidence, profile evidence, production evidence, or manifest grounding.
- Stop if fixtures contain real personal/farm data.
- Stop if the scenario claims a successful SI inspection-register view or freeze/release before ADR 0002's separately governed prerequisites are accepted and activated.

Validation:

- Scenario runner command added by this ticket.
- `.venv/bin/python -m pytest kernel/tests/ -q`
- Frontend test/lint/build once available.
- `python3 conformance/ofarm_pkg_contract_check.py`
- `git diff --check`

---

## M3.8 - Minimal deployment envelope

Status: planned.

Goal:

- Add local/sandbox deployment instructions for backend, PostgreSQL, PWA, and development OIDC/principal binding.
- Include seeded fictional data and reset notes.

Likely touched files:

- local deployment docs
- local scripts only if needed for repeatable sandbox startup/reset
- fictional seed fixtures

Forbidden files:

- `reference/`
- `contracts/`
- generated manifests
- active artifact sets
- profile activation files
- production operations material
- real farm data

Read first:

- `M3_BRIEF.md`
- `README.md`
- `docs/adr/0001-tenancy-and-schema-migrations.md`
- `docs/adr/0002-valid-time-and-knowledge-time.md`
- `kernel/README.md`
- `profile_si_ffs/UNSUPPORTED_SURFACES.md`
- existing local run scripts and docs

Behavior change:

- A fresh contributor can run the sandbox backend and PWA, load fictional data, capture/sync/review one record, exercise the governed register/freeze refusals, and rerun baseline checks.

Required tests:

- Fresh-run instructions are verified from a clean local checkout or equivalent clean environment.
- Reset instructions remove only sandbox/generated local state.
- Baseline backend checks pass after setup.
- Startup refuses a missing, unknown, reordered, or digest-mismatched numbered
  migration; application startup does not mutate the schema.
- Sandbox reset cannot cross tenant boundaries or erase canonical source inputs.

Acceptance criteria:

- Deployment docs are explicitly local/sandbox only.
- No production readiness, real-farm onboarding, legal compliance, or official filing readiness is implied.

Non-goals:

- No production authentication hardening.
- No backup/restore operations.
- No billing, support desk, or multi-tenant administration.

Stop conditions:

- Stop if docs imply production operations or real-farm onboarding.
- Stop if setup needs live registry integration or real personal/farm data.
- Stop if setup relies on a default tenant, application-startup DDL, shared
  tenant/audit credentials, or a database whose migration readiness is unknown.

Validation:

- Fresh contributor run-through command list added by this ticket.
- `.venv/bin/python -m pytest kernel/tests/ -q`
- Frontend test/lint/build once available.
- `python3 conformance/ofarm_pkg_contract_check.py`
- `git diff --check`
