# OFARM2 Kernel — M1 implementation

The running Kernel from `M1_BRIEF.md`: PostgreSQL append-only truth store +
the gate pipeline + the materializer, with the two governed outputs and the
generated Capability Manifest. Implementation and conformance packaging
profile — not OFARM law; claims record-keeping completeness only.

## Run it (no canonical-repository knowledge required)

```bash
# 1. environment (Python 3.11+, PostgreSQL 15+)
python3 -m venv .venv
.venv/bin/pip install fastapi uvicorn pytest "psycopg[binary]" jsonschema rfc3339-validator httpx

# 2. a scratch cluster on a unix socket (no TCP listener)
PGBIN=$(dirname "$(which initdb)")        # e.g. /opt/homebrew/opt/postgresql@17/bin
"$PGBIN/initdb" -D .pgrun/data -U ofarm --no-locale -E UTF8
"$PGBIN/pg_ctl" -D .pgrun/data -o "-p 54317 -k $(pwd)/.pgrun -c listen_addresses=''" -l .pgrun/pg.log start
"$PGBIN/createdb" -h "$(pwd)/.pgrun" -p 54317 -U ofarm ofarm_kernel

# 3. the API (migrates + bootstraps the SI context spine on startup)
.venv/bin/uvicorn --factory kernel.api:create_app --port 8800

# 4. the conformance suite (tests 1-15 + the 8 fixtures replayed live;
#    uses its own database ofarm_kernel_test, recreated per run;
#    writes a JSON evidence file under conformance/evidence/)
.venv/bin/python -m pytest kernel/tests/test_conformance.py -q

# 5. the package self-check (before every commit — AGENTS.md rule 3)
python3 conformance/ofarm_pkg_contract_check.py
```

Environment overrides: `OFARM_PG_DSN` (full DSN) or `OFARM_PG_SOCKET_DIR` /
`OFARM_PG_PORT` / `OFARM_PG_DBNAME` / `OFARM_PG_USER`.

## Client surface

| Endpoint | What |
|---|---|
| `POST /commit` | one capture through the full gate chain; body `{"submission": {...}}`; always returns the `CommitIngressResult` envelope (refusals are data with registry reason codes, not transport errors) |
| `GET /views/passport/{farmRef}` | the live spray register (View 1) — freshness, exception rows, advisory flags; header `X-Acting-Party` |
| `POST /views/inspection-register/freeze` | freeze the exportable inspection register (View 2); body `{farmRef, windowStart, windowEnd}` |
| `GET /records/{id}` | record + payload + digests; default deny per request |
| `GET /manifest` | the generated Capability Manifest |
| `GET /health` | liveness + the reachability-invariant check |

The submission shape `POST /commit` accepts is the runtime boundary, not a
contract; `kernel/demo.py:spray_submission()` is the canonical worked example
(fictional, format-true — privacy rule 1). For an operation claim, `payload`
is a complete `ExecutionRecordPayload` per `contracts/core/`.

## Module map

| Module | Role |
|---|---|
| `schema.sql` | DDL: append-only record/edge/gate-log tables (statement-level mutation triggers), reachability constraint trigger (deferred, same-transaction — D3), derived materialization tables, draft-lane `runtime_trace` |
| `contracts.py` | contract registry: every write validated against `contracts/` (canonical lane) or `contracts/drafts_reference/` (draft lane, D16) |
| `store.py` | the append-only truth store; edges, gate log, idempotency, in-force queries, reachability check |
| `problems.py` | `RuntimeProblem` factory; reason codes verbatim from the registry RFC — unknown codes refuse loudly |
| `context.py` | SI profile instance bootstrap, in-force reference snapshots, per-farm `ContextSnapshot` assembly with content-addressed reuse (basis drift mints, sameness reuses) |
| `authority.py` | default-deny evaluator: roles, grants, delegations, sharing, prospective revocation, non-human actor rule |
| `gates.py` | the EnforcementChain: ingress → authority → validation sub-gates → applicability → evidence sufficiency → review/promotion (self-review, D8) → materialization |
| `materializer.py` | deterministic recompute with `MaterializationBasis` receipts; basis-set invalidation (D12); the four explainable-evidence draft shapes behind Kernel law (D16) |
| `views.py` | View 1 (PassportView) + View 2 (DocumentAssembly freeze/file) with `ResultQualificationEnvelope`s and refusal behavior |
| `manifest.py` | Capability Manifest + ActiveArtifactSet generation from actual runtime surfaces + grounding verification |
| `api.py` | the FastAPI surface above |
| `demo.py` | fictional format-true onboarding + spray submission builders (the package's worked example) |
| `tests/` | conformance suite (tests 1–15, fixtures replayed live, JSON evidence) |

## Deliberately not here (do not drift — M1_BRIEF.md)

Mobile app (M3) · registry adapter scheduling (M2; `tooling/regsr_snapshot/`
is the parser) · GERK importer (M2) · OIDC wiring (M2; parties/grants are
bootstrapped) · dynamic packs · public query compiler · AI/agent runtime ·
everything in `profile_si_ffs/UNSUPPORTED_SURFACES.md`.
