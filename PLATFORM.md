# OFARM2 Platform (pilot runtime)

Status: implementation and conformance packaging profile — not OFARM law. One small, boring system that enforces Kernel and Core law. Storage layout is explicitly optimizable under Platform RC2.1 §1.3; semantic law is not.

## Components

1. **Truth store** — PostgreSQL, append-only record tables, JSONB payloads validated against the package contracts on write. Not a triple store; RDF export is a later derived projection.
2. **Gate pipeline** — the EnforcementChain as literal middleware. Every authoritative write crosses it; every refusal emits a `RuntimeProblem` with a registry reason code.
3. **Materializer** — deterministic: in-force records in → current state + `MaterializationBasis` + freshness out.
4. **Mobile capture app** — offline-first (local draft queue; drafts are drafts until the server commits). Photos as `EvidenceRecord`s. Target: spray record entered in the field in ≤ 90 seconds (see `CAPTURE_MAPPING.md`).
5. **Registry adapter** — imports the product register into `ReferenceSnapshot`s on the cadence the SI profile declares; generates `ExternalRegistryVerificationTrace`s at binding time. Snapshot-based; no live-integration claim.
6. **Offline registry cache** — the device carries the current product-register snapshot (with its `ReferenceSnapshot` id) and the farm's parcel list, so offline bindings reference the exact snapshot they were made against. At sync, ingress re-verifies bindings against the then-current snapshot; discrepancies route to review, never silent acceptance.
7. **Output generator** — one PassportView (live register view with freshness and gaps visible) and one DocumentAssembly (frozen, exportable inspection register). Both carry `ResultQualificationEnvelope`s; both refuse or disclose per `views/VIEWS.md`.
8. **Auth** — ordinary OIDC (e.g. Keycloak) mapped onto Party / RoleAssignment / AuthorityGrant. Roles: farmer, family worker / contractor (via `DelegationGrant`), advisor, read-only inspector (via `SharingGrant`).

## Gate pipeline (with named sub-gates)

```
ingress normalization
→ authority                  (AuthorizationDecisionRequest/Result/Trace; default deny;
                              revocation re-check on sync — see fixture: revoked recheck denies)
→ validation                 sub-gates, each with own reason codes:
                              schema validation · semantic/carrier validation ·
                              reference-resolution · temporal-conformance ·
                              code-binding / currentness · external-registry verification
→ profile applicability      (static SI activation; ContextSnapshot assembly)
→ evidence sufficiency       (auto-generated EvidenceSufficiencyCase where policy requires)
→ review / promotion         (per SI self-review policy; exceptions to advisor queue)
→ materialization            sub-gate: dispute/correction/supersession handling
→ publication / export       sub-gates: reconstruction policy+trace ·
                              output disposition / result qualification ·
                              sharing / redaction (re-evaluated per request)
```

Every gate outcome that affects promotion, rejection, review, activation, or publication lands in the gate log and the `PromotionTrace`.

## Storage posture (binding for the pilot)

- append-only record tables; immutable payload digests (sha256)
- schema version + schema hash stored per record
- explicit relation/edge table — authority, evidence, review, lineage, and materialization references are durable edges, not JSON-path conventions
- materialization tables marked **derived**; projection tables marked **derived/recomputable**
- no authoritative writes into projections, caches, or report stores — ever
- outbox/gate-log tables for enforcement traces
- the `PromotionTrace` reachability link written in the same transaction as the commit

## Invalidation (one mechanism, law-complete)

> Any change to truth basis, identity/lifecycle basis, context basis, time-policy basis, reference/currentness basis, dispute/correction basis, or relevant twin policy invalidates or stales affected materializations according to policy.

Implemented as **basis-set invalidation**: a materialization goes STALE when any member of its `MaterializationBasis` is superseded, revoked, or version-bumped; when its `ContextSnapshot`'s components (profile version, reference snapshot, evidence policy) change; or when its time policy expires. Authority/sharing changes do **not** stale truth — they are re-evaluated per request at the sharing/redaction gate, so a revoked inspector loses access instantly, not at next recompute.

## Unsupported surfaces (capability posture)

The following are **unsupported in Platform v1** and must be declared unsupported or non-default in the deployment's Capability Manifest (M1 deliverable — see `profile_si_ffs/PROFILE.md`). The already-active governance boundaries apply in full if any such surface is ever exposed:

dynamic pack installation/merging · public QuerySpecification authoring/compiler (predefined versioned views only) · AI/agent runtime (including software-agent review) · voice capture · world models · farm-to-farm intelligence · learning/farm-memory · cyber-physical mission execution · sustainability-charter claim features · livestock semantics.

## Technology recommendation (swappable; pick once, stop deciding)

Python/FastAPI backend (reuses the canonical conformance-runner style and JSON-schema tooling) · PostgreSQL · Flutter or PWA client · Keycloak OIDC. One engineer plus the steward builds the MVP; two build it comfortably — **only** within the strict MVP scope in `PILOT_SI.md`. Production hardening (security review, backups, audit operations, conflict UX beyond draft-sync-refusal) is a separate later line item.
