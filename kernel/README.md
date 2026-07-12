# OFARM2 Kernel — M1 implementation

The running Kernel from `M1_BRIEF.md`: PostgreSQL append-only truth store +
the gate pipeline + the materializer, with the two governed outputs and the
generated Capability Manifest. Implementation and conformance packaging
profile — not OFARM law; claims record-keeping completeness only.

## Run it (no canonical-repository knowledge required)

For the exact evidence-only review environment and the single complete Kernel
test command, use `conformance/REVIEW_BASELINE.md`. The live RuntimeBundle uses
that same executable boundary: Linux x86_64, CPython 3.12.13, PostgreSQL 17.10,
the retained pip/dependency locks, source-only imports, and the exact read-only
Python Bookworm image pinned in `.github/workflows/conformance.yml`. There is
currently no looser host-Python, macOS, Python 3.11, or unpinned
live-development mode. The commands below assume they are already running
inside that pinned image; matching `python --version` on a host is insufficient.

```bash
# 1. exact source-only environment (Linux x86_64; this command must report
#    Python 3.12.13)
python3.12 --version
python3.12 -m venv .venv
mkdir -p .venv/.ofarm-wheelhouse
.venv/bin/python -m pip download --require-hashes --only-binary=:all: \
  --no-deps --dest .venv/.ofarm-wheelhouse -r requirements-review-pip.lock
.venv/bin/python -m pip install --no-compile --no-index \
  --find-links .venv/.ofarm-wheelhouse --require-hashes \
  --only-binary=:all: --no-deps -r requirements-review-pip.lock
.venv/bin/python -m pip download --require-hashes --only-binary=:all: \
  --no-deps --dest .venv/.ofarm-wheelhouse \
  -r requirements-review-baseline.lock
.venv/bin/python -m pip install --no-compile --no-index \
  --find-links .venv/.ofarm-wheelhouse --require-hashes \
  --only-binary=:all: --no-deps -r requirements-review-baseline.lock
.venv/bin/python -m pip check
find .venv -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
find .venv -depth -type d -name __pycache__ -empty -delete

# The retained runtime requires these process settings and rejects ambient
# Python import customization.
export TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8
unset PYTHONCASEOK PYTHONEXECUTABLE PYTHONHASHSEED PYTHONHOME PYTHONINSPECT
unset PYTHONMALLOC PYTHONPATH PYTHONPLATLIBDIR PYTHONPYCACHEPREFIX PYTHONSAFEPATH
unset PYTHONSTARTUP PYTHONWARNINGS LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT
unset GLIBC_TUNABLES GCONV_PATH

# 2. an exact PostgreSQL 17.10 scratch cluster on a unix socket (no TCP listener)
PGBIN=$(dirname "$(command -v initdb)")
"$PGBIN/initdb" -D .pgrun/data -U ofarm --no-locale -E UTF8
"$PGBIN/pg_ctl" -D .pgrun/data -o "-p 54317 -k $(pwd)/.pgrun -c listen_addresses=''" -l .pgrun/pg.log start
"$PGBIN/createdb" -h "$(pwd)/.pgrun" -p 54317 -U ofarm ofarm_kernel

# 3. the API (live binding requires the exact locked environment and the
#    retained isolated launcher; an ordinary Python/uvicorn entry point refuses)
.venv/bin/python -I -B -S tooling/ofarm_isolated.py --venv-root .venv \
  -m uvicorn --factory kernel.api:create_app --port 8800

# 4. the test suites: root conformance (tests 1-15 + regressions + the
#    8 fixtures replayed live; uses its own database ofarm_kernel_test,
#    recreated per run; writes a JSON evidence file under conformance/evidence/)
#    plus the stage-contract tests (policy tables, validator dispositions)
.venv/bin/python -I -B -S tooling/ofarm_isolated.py --venv-root .venv \
  -m pytest kernel/tests/ -q --assert=plain --import-mode=importlib

# 5. the package self-check (before every commit — AGENTS.md rule 3)
python3 conformance/ofarm_pkg_contract_check.py
```

Environment overrides: `OFARM_PG_DSN` (full DSN) or `OFARM_PG_SOCKET_DIR` /
`OFARM_PG_PORT` / `OFARM_PG_DBNAME` / `OFARM_PG_USER`; the test harness
additionally honors `OFARM_PG_ADMIN_DSN` (admin connection used to recreate
the test database, e.g. a CI service container).

The launcher rejects `PYTHONPATH`, `PYTHONHOME`, startup customization,
`.pth` files, project/dependency bytecode caches, unknown `sys.path` roots,
native loader variables (including empty values), and distributions that do
not exactly match both retained locks. Mutable
installed `RECORD` metadata is not trusted: every import-root member is checked
directly against its hash-locked wheel archive, and extra data, files,
directories, symlinks, or wheels are refused. The launcher adds only the
manifest-verified standard library, locked virtual-environment site-packages,
and reviewed project root, in that order.

Live RuntimeBundle selection also seals
the exact module objects (including `None` entries), import-container objects,
and canonical `sys.path_importer_cache` keys, finders, loader configuration,
and mutable finder state. Bootstrap rechecks that seal before commit and after
commit activation; every governed transaction then refuses any widening,
replacement, reload state, or importer-cache drift. The live receipt also inventories
every executable `/proc/self/maps` file and refuses any mapping not owned by
the pinned image or a retained wheel; every governed transaction checks that
mapping/stat identity again before commit.

### Transitional schema/runtime role

Before #174 supplies separately applied numbered migrations and stable grants,
this pre-deployment prototype deliberately uses one elevated schema-owner/runtime
identity. It must be able to take `SHARE` locks on every fingerprinted
`pg_catalog` relation during the one proven-empty install and for the complete
life of every outer governed transaction. Those locks close the race between a
catalog check and decision SQL. A legacy, partial, or drifted development
database must be recreated; the runtime never adopts, repairs, or forward-
migrates it.

This is not the deployment role model. Do not infer that an ordinary application
role can run the current startup or transaction guard: it cannot take the
required catalog locks. #174 must separate migration ownership from the
least-privilege runtime role, install its grants as reviewed migration state,
and remove schema installation from application startup before deployment.

## Client surface

| Endpoint | What |
|---|---|
| `POST /commit` | one capture through the full gate chain; body `{"submission": {...}}`; requires `X-Acting-Party` matching `submission.actingPartyRef` (transport-principal binding — a development principal pending OIDC at M2, see `profile_si_ffs/UNSUPPORTED_SURFACES.md`); always returns the `CommitIngressResult` envelope (refusals are data with registry reason codes, not transport errors) |
| `GET /views/passport/{farmRef}` | the live spray register (View 1) — freshness, exception rows, advisory flags; header `X-Acting-Party` |
| `POST /review/accept` | governed queue acceptance: body `{farmRef, assertionRef, rationale, evidenceRefs?, idempotencyKey?}`; the rationale is mandatory and routed insufficiencies additionally require reviewer-attached durable evidence (gate-enforced) |
| `POST /views/inspection-register/freeze` | freeze the exportable inspection register (View 2); body `{farmRef, windowStart, windowEnd}` |
| `GET /records/{id}` | record + payload + digests; default deny per request |
| `GET /manifest` | the generated Capability Manifest |
| `GET /health` | liveness + the reachability-invariant check |

### HTTP receipt byte contract

Every non-HEAD successful response from the governed routes in `api.py`, plus
every non-HEAD authorization refusal, handled HTTP error, and request-validation
error, plus the generic non-leaking envelope for an unexpected server failure,
is emitted as `Content-Type: application/json; charset=utf-8`. The body is the
exact UTF-8 byte sequence produced by `OFARM_CANONICAL_JSON_V1`;
FastAPI/Pydantic does not serialize it again after receipt construction. The
response identifies that policy in `X-OFARM-Receipt-Canonicalization`.

`X-OFARM-Receipt-Payload-Digest` is lowercase `sha256:` plus the SHA-256 of the
exact delivered body bytes (`response.content`), including for refusal and
validation envelopes. It is not a digest of a reparsed JSON value. The
separate `X-OFARM-Runtime-Bundle-Digest` identifies the verified runtime that
constructed those bytes.

HTTP suppresses every response body for a HEAD request. A handled HEAD error
therefore omits `Content-Length`, identifies `EXACT_BYTES_V1`, and receipts the
SHA-256 of the empty byte sequence actually delivered; it never hashes a JSON
representation that the client did not receive. Omitting `Content-Length`
avoids claiming a corresponding GET representation length for a method-level
error.

The submission shape `POST /commit` accepts is the runtime boundary, not a
contract; `kernel/demo.py:spray_submission()` is the canonical worked example
(fictional, format-true — privacy rule 1). For an operation claim, `payload`
is a complete `ExecutionRecordPayload` per `contracts/core/`.

## Module map

| Module | Role |
|---|---|
| `schema.sql` | DDL: append-only record/edge/gate-log tables (statement-level mutation triggers), reachability constraint trigger (deferred, same-transaction — D3), derived materialization tables, draft-lane `runtime_trace` |
| `contracts.py` | contract registry: every write validated against `contracts/` (canonical lane) or `contracts/drafts_reference/` (draft lane, D16) |
| `profile_runtime.py` | active profile runtime descriptor loader: validates profile-local runtime inputs fail-closed while keeping tenant/demo binding outside the descriptor |
| `runtime_bundle.py` | immutable runtime selection plus exact interpreter, import-origin, dependency-file, and standard-runtime attestation |
| `store.py` | the append-only truth store; edges, gate log, idempotency, in-force queries, reachability check |
| `problems.py` | `RuntimeProblem` factory; reason codes verbatim from the registry RFC — unknown codes refuse loudly |
| `config.py` | deployment constants: tenant/profile/pack/policy refs, runtime version, database DSN assembly |
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
| `api.py` | the FastAPI surface above |
| `demo.py` | fictional format-true onboarding + spray submission builders (the package's worked example) |
| `tests/` | conformance suite (tests 1–15, fixtures replayed live, JSON evidence) + stage-contract tests (`test_stages.py`; engineering tests, excluded from the conformance evidence file) |

## Deliberately not here (do not drift — M1_BRIEF.md)

Mobile app (M3) · registry adapter scheduling (M2; `tooling/regsr_snapshot/`
is the parser) · GERK importer (M2) · OIDC wiring (M2; parties/grants are
bootstrapped) · dynamic packs · public query compiler · AI/agent runtime ·
everything in `profile_si_ffs/UNSUPPORTED_SURFACES.md`.
