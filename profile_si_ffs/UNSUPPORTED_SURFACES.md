# Unsupported surfaces — `manifest:si.ffs.pilot.v0_1`

The Capability Manifest contract (`ofarm.capabilitymanifest.v0.1`) is closed
(`additionalProperties: false`) and carries no free-text surface, so the
PLATFORM.md unsupported-surface declaration lives here, referenced from the
regenerated `ActiveArtifactSet` notes. The manifest never claims any surface
below; this file makes the posture explicit rather than implicit.

**Unsupported in Platform v1** (PLATFORM.md "Unsupported surfaces"; the
already-active governance boundaries apply in full if any is ever exposed):

- dynamic pack installation / merging
- public QuerySpecification authoring / compiler (predefined versioned views only — manifest: `supportsGuidedQueryUI: false`, `supportsAIMediatedQuery: false`, `supportsPublicExpertQuery: false`)
- AI / agent runtime, including software-agent review (Phase-2 candidate, D8; the authority gate returns `REQUIRE_HUMAN_APPROVAL` for any non-human actor at promotion/publication/attestation stages)
- voice capture (`VOICE_CAPTURE` ingress channel exists in the contract enum; this deployment does not accept it)
- world models
- farm-to-farm intelligence
- learning / farm-memory
- cyber-physical mission execution
- sustainability-charter claim features
- livestock semantics

**Partial-extent geometry ingestion (SI source, declared):** the extent-carrier
acceptance *mechanism* now exists (M2 G7). A non-whole `executionExtent`
(`PARTIAL_TARGET_SCOPE` / `FAILED_PASS` / `RETREATMENT_AREA` / `DISPUTED_AREA`
/ `EXTERNAL_GEOMETRY_REFERENCE`) may carry either an inline `area` (value + unit)
or a `geometryRef` / `extentRef` / `scopeExtentBasisRef` that **resolves to a
recognized extent-carrier kind** — the generic `PartialExtent`
(`ofarm.partialextent.v0.1`), now in `policy.ALLOWED_EXTENT_BOUND_KINDS`.
`ExecutionExtentValidator` still refuses a dangling or wrong-kind ref
(`EVIDENCE_REFERENCE_UNAVAILABLE`) and an unquantified non-whole extent
(`EVIDENCE_INSUFFICIENT`, ERRATA E-004); it also refuses a carrier that resolves
to the right kind but does **not declare itself usable** as a bound — its
`extentState` is not `ACCEPTED_FOR_DECLARED_USE`, or its own `promotionBoundary`
forbids the promotion (`mayDriveMaterialization=false`, or `mustNotPromoteTo`
names a target this accepted operation drives/feeds: `ACCEPTED_EXECUTION` /
`WHOLE_FIELD_TRUTH` / `CURRENT_STATE_DIRECTLY` / `PASSPORT_VIEW_DEFAULT`) —
honoring the carrier's declared boundary (Kernel rule 4/7). `COMPLIANCE_FACT` and
`DURABLE_IDENTITY` are excluded by decision (the claim drives neither). All
not-usable cases stay RETAIN_DRAFT. **Deliberately deferred
(beyond G7 kind-recognition):** *scope-containment* of the carrier — whether the
carrier's `anchorScope`/`parentScope` must be the `executionExtent.targetScope`
or contained within it — is a coherence relation left for a follow-up (steward's
call). **Still unsupported in this SI pilot:** the *ingestion* that populates
PartialExtent carriers from real geometry — the GERK layer supplies per-PID
existence + raw `AREA` only (attribute import), not coordinate geometry parsed
into extent magnitudes/carriers (P2). Until that source ships, SI partial-extent
claims rely on the inline `area` bound; the ref-bound mechanism is exercised by
generic fixtures, not SI geometry literals.

**Use types beyond surface-areas** (Reg. 2023/564 Annex): closed-space and
seed-treatment record rows are not implemented in pilot v1
(`SI_RECORD_FIELDS.md` §D.1).

**No live registry integration** (D9, PILOT_SI claim limits): the product
register enters only as dated `ReferenceSnapshot`s from scripted HTML parses.
The manifest's `IMPORT_MAPPING` surface is `SUPPORTED` as of M2 P1 — the
governed snapshot-import mechanism exists and the SI REGSR adapter rides it
(parse → dated `ReferenceSnapshot` → store-backed reference data → identity
verify), with the weekly/monthly-floor cadence declared (D19). `SUPPORTED`
covers that snapshot-import mechanism ONLY: live HTTP fetch, scheduled cron
execution, production currentness, and current-compliance are NOT claimed and
remain out of scope (an official-feed switch is outreach-gated to 2027, D13).
No current-compliance claim follows from any of this. Register re-verification
is identity-grade only where the snapshot carries decision numbers (detail
pages); list rows are locators, and locator-only re-verification routes to
review instead of pretending.

**API authentication posture (M2 G4, declared):** the HTTP surface remains a
**conformance/development surface, not a production-authenticated runtime**.
The transport principal is derived by `get_principal` and bound to the
submitted/acting party — a mismatch is refused (`ACTOR_BINDING_UNRESOLVED`) and
an absent principal is a default-deny (`401`), so body-level actor spoofing is
denied. Two principal sources:
- **OIDC (configured)** — a verified bearer token yields the Party principal.
  G4 ships a **zero-dependency HS256 verifier** for this development/conformance
  path (fail-closed: enforces issuer/audience/exp/nbf, rejects `alg=none`,
  non-HS256, malformed, missing-claim and bad-signature tokens, constant-time
  compare). **Production RS256 / JWKS (Keycloak per PLATFORM.md) verification is
  NOT implemented** — it is a deliberate `NotImplemented` verifier path
  (`kernel/auth_oidc.py`), and the verifier **never silently falls back** from
  RS256 to HS256. HS256-here is a posture/binding stand-in, never a claim of
  production Keycloak support; no PyJWT/jose/cryptography dependency is added.
- **`X-Acting-Party` header (OIDC disabled)** — the development/conformance shim;
  the header is **not authentication**, but the binding contract is identical.

Roles in a token map to `RoleAssignment` only and **never** synthesize a grant —
authority still comes solely from AuthorityGrant / DelegationGrant / SharingGrant
(D4); a role claim alone authorizes nothing. Distinct-reviewer acceptance happens
ONLY through `/review/accept` (a `GOVERNANCE_DECISION` commit under the reviewer's
own principal); a reviewer named inside the submitter's request never promotes —
that inline path was removed after the second hostile review.

**Freshness mode `NO_CURRENT_STATE_DEPENDENCY` (M1, declared):** inside
`Materializer.resolve_for_use` this mode is **conservatively narrowed to
stale-allowed** (the same satisfaction set as `ALLOW_STALE_EXPLORATORY`);
with no live materialization and recomputation disabled it refuses with
`MATERIALIZATION_BASIS_MISSING` (Kernel rule 7) rather than serving without
a basis. This is deliberate, twice over: the mode is an **undescribed enum
value** in the candidate contracts (defined nowhere in `reference/` — ERRATA
E-003), and the `MaterializationResult` contract admits **no lawful no-basis
outcome** (closed `decisionOutcome` enum; `allOf` forbids `ALLOW_REUSE` on an
INVALID state) — a "true no-materialization path" through the materializer
would have to misreport freshness. The mode's actual no-current-state intent
is honored at the **QueryPlanIR step layer**: the two shipped views mark
exactly their direct-substrate-read steps (pending claims, advisory flags)
with this requirement, and those steps never touch the materializer
(`kernel/views.py`). No production caller routes this mode through
`resolve_for_use`.

**Runtime evidence level** (Performance & Explainable Current-State Evidence
RFC §11.3): `CONFORMANCE_FIXTURE_PASSING` at most once the M1 suite is green —
no benchmark, load, storage-amplification, or production evidence exists, so
no fleet-scale or production readiness is claimed for explainable current
state or anything else (RFC §11.4, README claim limits).
