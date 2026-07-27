# OFARM2 Kernel — production foundation and legacy M1 prototype

The Kernel contains two deliberately separate runtime generations:

- `kernel.api:create_app` is the production trust and storage foundation.
  Its governed semantic endpoints remain closed.
- `kernel.legacy_m1.api` is the injected development and conformance surface
  for the pre-tenancy M1 Store, gates, materializer, and SI outputs.

The architecture checker walks the production import closure and refuses any
dependency on the legacy package, Store, prototype startup path, legacy
authentication, or SI semantic/output modules. The legacy surface is evidence
for record-keeping completeness, not production authority or OFARM law.

## Production authentication runtime

`kernel.api:create_app` is environment-only. `RuntimeConfig.from_env()` reads
the environment once, then the production builder validates the deployment
image, constructs the graph, initializes RS256 OIDC/JWKS, validates the
database authentication contract and principal resolver, proves that the
tenant and security-audit structures use separate PostgreSQL services, checks
every startup connection's exact database role, observes the correlation-HMAC
lifecycle, performs the HMAC and signing KMS preflights, and opens the tenant
pool. FastAPI is created only after every step succeeds.

Required settings:

- `OFARM_AUTH_MODE=production`
- `OFARM_DEPLOYMENT_IMAGE_DIGEST`
- `OFARM_OIDC_ISSUER`, `OFARM_OIDC_AUDIENCE`, `OFARM_OIDC_JWKS_URL`
- `OFARM_PG_DSN`
- `OFARM_TENANT_READINESS_PG_DSN`
- `OFARM_SECURITY_AUDIT_READINESS_PG_DSN`
- `OFARM_SECURITY_AUDIT_AUTHENTICATION_PG_DSN`
- `OFARM_SECURITY_AUDIT_REQUEST_ROUTER_PG_DSN`
- `OFARM_SECURITY_AUDIT_CONTROL_PG_DSN`
- `OFARM_CORRELATION_HMAC_KMS_KEY_RESOURCE`
- `OFARM_TENANT_CAPABILITY_KID`
- `OFARM_SIGNING_EVIDENCE_RECEIPT_PATH`
- `OFARM_SIGNING_EVIDENCE_OBSERVER_PUBLIC_KEY_B64`

The external OIDC audience and database binder audience are distinct values.
The first verifies credentials; the second binds database authority and signed
capabilities. Production OIDC v1 accepts only RS256.

Database locations and credentials come from the environment, but database
authority does not. Production code requires these exact `SESSION_USER`
identities:

| Connection | Required role |
|---|---|
| Tenant readiness | `ofarm_readiness` |
| Security-audit readiness | `ofarm_security_audit_readiness_login` |
| Authentication producer | `ofarm_security_authentication_producer_login` |
| Request-router producer | `ofarm_security_request_router_producer_login` |
| Audit control | `ofarm_security_audit_control_login` |

Authority-probe connections use a code-owned five-second libpq timeout per host
attempt and install `statement_timeout=2000` before their first SQL statement.
Those startup options replace any `options` embedded in a DSN. The audit-control
connection remains open, idle, and outside a transaction during the bounded KMS
posture calls so its database observation does not require a sixth connection.

Every connection is queried during startup and any different role prevents
application publication. Startup performs no audit append or control mutation.
Authentication and request-router refusals append synchronously through their
distinct producer credentials. Those request-time connections replace any DSN
timeout options with a code-owned five-second connect timeout per host attempt,
`statement_timeout=2000`, and `lock_timeout=250`. Failure never falls back to an
unaudited tenant write.

Production owns a bounded connection pool and one transaction-bound
`TenantUnitOfWork` per verified tenant operation. The UnitOfWork creates and
spends the database challenge on one backend, exposes the exact protected
`TenantBinding`, and proves an idle transaction before pool return.

Governed production handlers are still downstream work, so protected endpoints
return `GOVERNED_SURFACE_BLOCKED`. `/health` and `/manifest` expose immutable
runtime metadata only. Authoritative services are held by route closures and
are never published through `app.state`.

Production exports no dependency-injection constructor. Importing
`kernel.api` does not load the legacy Store, startup posture, HS256 verifier,
gate pipeline, or SI output generator.

## Legacy M1 development runner

This section runs the pre-tenancy M1 prototype against a disposable `public`
schema. It is not an issue #174 tenant or security-audit deployment path and
must never be pointed at either provisioned service. Its historical startup
DDL and ambient Store remain permanently quarantined to this explicit legacy
surface; production tenant work uses `TenantUnitOfWork`. The #174 production
database boundary uses only the external numbered runners and independent
read-only structural observations documented in
`deployment/postgresql/README.md`.

For the exact evidence-only review environment and the single complete Kernel
test command, use `conformance/REVIEW_BASELINE.md`. That Linux x86_64 baseline
pins Python 3.12.13, PostgreSQL 17.10, pip, every dependency wheel hash, and CI
actions. The development setup below remains convenient but is not evidence of
an exact baseline match.

```bash
# 1. environment (Python 3.11+, PostgreSQL 15+)
python3 -m venv .venv
.venv/bin/pip install fastapi uvicorn pytest "psycopg[binary,pool]" jsonschema rfc3339-validator httpx

# 2. a scratch cluster on a unix socket (no TCP listener)
PGBIN=$(dirname "$(which initdb)")        # e.g. /opt/homebrew/opt/postgresql@17/bin
"$PGBIN/initdb" -D .pgrun/data -U ofarm --no-locale -E UTF8
"$PGBIN/pg_ctl" -D .pgrun/data -o "-p 54317 -k $(pwd)/.pgrun -c listen_addresses=''" -l .pgrun/pg.log start
"$PGBIN/createdb" -h "$(pwd)/.pgrun" -p 54317 -U ofarm ofarm_kernel

# 3. the test suites construct the injected legacy surface through
#    kernel.legacy_m1.api:create_test_app and install the disposable prototype schema.
#    Root conformance includes tests 1-15 + regressions + the
#    8 fixtures replayed live; uses its own database ofarm_kernel_test,
#    recreated per run; writes a JSON evidence file under conformance/evidence/)
#    plus the stage-contract tests (policy tables, validator dispositions)
.venv/bin/python -m pytest kernel/tests/ -q

# 4. the package self-check (before every commit — AGENTS.md rule 3)
python3 conformance/ofarm_pkg_contract_check.py
```

Environment overrides: `OFARM_PG_DSN` (full DSN) or `OFARM_PG_SOCKET_DIR` /
`OFARM_PG_PORT` / `OFARM_PG_DBNAME` / `OFARM_PG_USER`; the test harness
additionally honors `OFARM_PG_ADMIN_DSN` (admin connection used to recreate
the test database, e.g. a CI service container).

`kernel.legacy_m1.api:create_test_app` and
`kernel.legacy_m1.api:create_development_app` are the only injected legacy
constructors. They accept a full lowercase OCI digest (`sha256:` plus 64
hexadecimal digits) as an explicit argument and never read production
configuration. HS256 exists only in the test runtime.

## Client surface

| Endpoint | What |
|---|---|
| `POST /commit` | legacy test/development capture through the gate chain; requires an injected test principal or `X-Acting-Party`; production returns `GOVERNED_SURFACE_BLOCKED` until the governed handlers land |
| `GET /views/passport/{farmRef}` | the live spray register (View 1) — freshness, exception rows, advisory flags; header `X-Acting-Party` |
| `POST /review/accept` | governed queue acceptance: body `{farmRef, assertionRef, rationale, evidenceRefs?, idempotencyKey?}`; the rationale is mandatory and routed insufficiencies additionally require reviewer-attached durable evidence (gate-enforced) |
| `POST /views/inspection-register/freeze` | freeze the exportable inspection register (View 2); body `{farmRef, windowStart, windowEnd}` |
| `GET /records/{id}` | record + payload + digests; default deny per request |
| `GET /manifest` | the generated Capability Manifest |
| `GET /health` | liveness + the reachability-invariant check |

The submission shape `POST /commit` accepts is the runtime boundary, not a
contract; `kernel/demo.py:spray_submission()` is the canonical worked example
(fictional, format-true — privacy rule 1). For an operation claim, `payload`
is a complete `ExecutionRecordPayload` per `contracts/core/`.

Before opening a transaction, the legacy pipeline requires non-empty string
values for `commitClass`, `farmRef`, `actingPartyRef`, and `idempotencyKey`.
Unusable transport shape receives a fixed HTTP 422 response; it is not a
governed `RuntimeProblem`, trace, receipt, or domain outcome. Usable strings
remain exact and continue to the existing normalization and contract checks.

## Module map

| Module | Role |
|---|---|
| `schema.sql` / `schema_posture.py` | Legacy M1 disposable-schema DDL and posture verification; not an issue #174 production migration or startup path |
| `contracts.py` | contract registry: every write validated against `contracts/` (canonical lane) or `contracts/drafts_reference/` (draft lane, D16) |
| `profile_runtime.py` | active profile runtime descriptor loader: validates profile-local runtime inputs fail-closed while keeping tenant/demo binding outside the descriptor |
| `store.py` | the append-only truth store; edges, gate log, idempotency, in-force queries, reachability check |
| `problems.py` | `RuntimeProblem` factory; reason codes verbatim from the registry RFC — unknown codes refuse loudly |
| `config.py` | deployment constants: tenant/profile/pack/policy refs, runtime version, database DSN assembly |
| `api.py` | production-only FastAPI composition; governed semantics remain blocked |
| `deployment_identity.py` | pure deployment-image identity validation shared without database authority |
| `runtime_config.py` | the single immutable production environment snapshot |
| `application_runtime.py` | ordered production graph construction and public runtime methods |
| `security_audit_runtime.py` | pre-tenant audit composition, fixed database-role admission, and HMAC readiness |
| `authentication_audit.py` / `request_router_audit.py` | synchronous fail-closed production of classified pre-tenant failure evidence |
| `production_oidc.py` | production RS256/JWKS credential verification |
| `principal_resolver.py` | exact database principal-authority resolution |
| `signing_authority.py` / `tenant_capability_issuer.py` | fresh signing evidence and tenant capability minting |
| `legacy_m1/api.py` / `legacy_m1/runtime.py` | explicit injected legacy development and conformance composition |
| `auth_oidc.py` | quarantined legacy HS256 verifier; test-only |
| `context.py` | SI profile instance bootstrap, in-force reference snapshots, per-farm `ContextSnapshot` assembly with content-addressed reuse (basis drift mints, sameness reuses) |
| `authority.py` | default-deny evaluator: roles, grants, delegations bounded by live source authority, sharing, prospective revocation, party lifecycle, non-human actor rule |
| `policy.py` | runtime policy as data: commit-class ↔ action-class/promotion/consequence tables, freshness-use policy, floor items, routing-resolution rules (issue #3) |
| `gates.py` | the orchestration shell: wires the stage chain; one commit = one transaction (D3); no embedded policy branches |
| `stages.py` | the named gate stages with typed results (`GatePass`/`GateRefusal`/`GateReplay`) sharing one transaction-scoped `GateContext` |
| `validators.py` | the named validation units (temporal, target, containment, supersession, governance acceptance, compliance claim, carrier, references, attribution, code binding, registry re-verification) in law-pinned order |
| `sufficiency.py` | `EvidenceSufficiencyCase` builders — floor cases, acceptance cases, routing amendments — auto-generated, never hand-authored |
| `emission.py` | every record emission: `PromotionEmitter` (both promotion flavors share it), `PromotionTraceWriter` (reachability accounting), `ReplayWriter` |
| `materializer.py` | deterministic recompute with `MaterializationBasis` receipts; basis-set invalidation (D12); the four explainable-evidence draft shapes behind Kernel law (D16) |
| `views.py` | View 1 (PassportView) + View 2 (DocumentAssembly freeze/file) with `ResultQualificationEnvelope`s and refusal behavior |
| `manifest.py` | Capability Manifest + ActiveArtifactSet generation from actual runtime surfaces + grounding verification |
| `demo.py` | fictional format-true onboarding + spray submission builders (the package's worked example) |
| `tests/` | conformance suite (tests 1–15, fixtures replayed live, JSON evidence) + stage-contract tests (`test_stages.py`; engineering tests, excluded from the conformance evidence file) |

## Deliberately not here (do not drift — M1_BRIEF.md)

Dynamic audit health, gap, retention, and recovery operations · mobile app
(M3) · registry adapter scheduling · dynamic packs · public query compiler ·
AI/agent runtime · everything in
`profile_si_ffs/UNSUPPORTED_SURFACES.md`.
