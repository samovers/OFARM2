# OFARM2 Temporal Publication Legacy-Resource Conformance Admission — Phase A Contract v0.1

**Status:** proposed Phase A design; documentation-only, unapproved, and
without checker, adapter, architecture-classifier, database, RuntimeBundle,
selection, runtime, route, output, deployment, legacy-activation, or #192
effect

**Issue:** #176

**Contract identity:**
`ofarm.temporal-publication-legacy-resource-conformance-admission.issue176.v0.1`

**Reviewed base:** `c33778c46c09141a624b97db4f9a69cfb527f645`

**Primary trust boundary:** temporal conformance refusal of an exact static
legacy resource reference from the one future isolated temporal RuntimeBundle
publication adapter

**Phase A boundary:** this RFC only

**Intended later Phase B boundary:** this RFC, the existing temporal candidate
checker, its existing focused governance test module, and canonical test-node
inventory regeneration only when mechanically required

## 1. Problem and goal

Merged publication law keeps `kernel/schema.sql`, `kernel/store.py`, and
`kernel/runtime_bundle_repository.py` as quarantined legacy-M1 authorities.
The current publication classifier already refuses a future adapter's static
Python import of the latter two modules through the architecture-owned exact
module predicate. PR #304 closes the repository-module omission.

`kernel/schema.sql` is not a Python module. The architecture checker already
owns its exact resource vocabulary and AST interpretation:

```text
LEGACY_RESOURCE_NAMES = {"schema.sql"}
_legacy_resource_violations(ast)
```

but the future publication-adapter classifier does not currently consume that
evidence. Consequently, a future adapter could contain a static string literal
such as `"kernel/schema.sql"` without the adapter-specific conformance refusal.
This is a conformance coverage gap; no adapter exists and no resource is read,
loaded, or executed today.

This contract establishes one decision only:

> When and only when the exact future publication adapter is present and has
> passed its existing exact path, module, marker, and import-isolation checks,
> the temporal classifier must obtain one authenticated AST copy of that
> adapter and refuse if the unchanged architecture-owned
> `_legacy_resource_violations()` reports any legacy resource reference.

The decision reuses the existing architecture resource authority. It neither
adds a resource name nor changes the architecture classifier, publication
adapter, database, catalog, or RuntimeBundle.

## 2. Learning value

This closes the third demonstrated legacy-M1 publication dependency without
inventing a temporal resource list or opening a repository-wide string scan. It
proves that the source-snapshot custody already accepted for the future
publisher can carry one additional, bounded AST consumer while preserving its
closed production and legacy surface.

## 3. Authority map

| Decision | Sole authority |
| --- | --- |
| Governance-before-automation and default-deny posture | Architecture report: `reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md`; 96,406 bytes; `sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256` |
| Valid/knowledge time meaning and interval rules | ADR 0002; unchanged: `docs/adr/0002-valid-time-and-knowledge-time.md`; 61,427 bytes; `sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796` |
| Future publisher identity, behavior, SQL ordering, and legacy non-dependency rule | Catalog-publication contract `ofarm.temporal-runtime-bundle-catalog-publication-admission.issue176.v0.1`; 47,814 bytes; `sha256:2161e9368f85b373b7cf54b6708edb7b291596defcf9683342e9583657a2298f` |
| Existing future-publication source classification, markers, state composition, and import refusal | Publication-conformance contract `ofarm.temporal-runtime-bundle-publication-conformance-admission.issue176.v0.1`; 42,596 bytes; `sha256:17014b754f7401a5ccf809dd8bb4281875592bfc0732abf08ca47dc378fb7cb1` |
| Exact legacy resource vocabulary and normalized static AST-string interpretation | `conformance/rewrite_architecture_check.py`; 73,266 bytes; `sha256:6893e9f658b84e2539e5734d9d694000a9847e06f3cb9d1e87b6622fb67cb806` |
| One authenticated Python package, exact module identity, AST custody, graph, and reachability | Existing `PythonSourceSnapshotV1` authority; unchanged |
| Temporal composition and the one new target-resource refusal | Existing `conformance/temporal_contract_candidate_check.py`; 184,327 bytes; `sha256:ec332e296558a1ac645550e19a9795d5bfc970cb5730db2585fc7e2d5f087bea`, amended only by a later approved Phase B |
| Focused temporary source evidence | `kernel/tests/test_temporal_contract_governance.py`; 160,368 bytes; `sha256:7ff863d4e2bd0eeed3e30b3f66eeed651f471cefe49ddf1c0b0764e502655dc7`, amended only by a later approved Phase B |
| Exact repository-module legacy membership | Merged PR #304, `c33778c46c09141a624b97db4f9a69cfb527f645`; unchanged here |
| Audit-runtime behavior | #192 only; outside this contract |

There is no temporal resource list, caller-selected policy, environment
override, second source snapshot, path walk, raw-file read, or fallback
classifier. This contract does not amend any frozen authority informally.

## 4. State, ordering, and invariants

The existing publication classifier retains its two private states and public
result. This contract adds no state value or public output. Its required order
within the already-classified target-present branch is:

```text
authenticated source snapshot
  -> exact publication path and module identity
  -> complete existing marker conjunction
  -> existing static legacy-module import refusal
  -> one target-adapter AST copy
  -> architecture-owned legacy-resource evaluation
  -> CLASSIFIED or REFUSED
```

The target AST may be copied only after the existing target identity and marker
checks pass, only when the target is present, and only once in an invocation.
The existing initializer AST copy remains separate and unchanged. An absent
adapter takes no target AST copy. The AST is never obtained from caller data,
the filesystem, a loader, a reparsed string, or a second snapshot.

- **PLRC-001 — One resource authority.** The exact names and normalization
  remain owned by the unchanged architecture resource predicate. No temporal
  constant, prefix, list, glob, or alternate normalizer exists.
- **PLRC-002 — Exact target only.** Resource inspection applies only to
  `deployment/postgresql/temporal_runtime_bundle_publication.py` after its
  existing identity/marker checks. A string in another file has no new
  publication-classification meaning.
- **PLRC-003 — Static refusal.** A legacy resource reported by the architecture
  predicate makes the existing temporal entry point non-success; it cannot
  become classified, selected, published, current, or output truth.
- **PLRC-004 — Bounded source custody.** The classifier uses the existing
  authenticated snapshot and exactly one additional target AST copy only in
  the target-present branch. No direct resource read or second snapshot occurs.
- **PLRC-005 — Existing module and initializer law survives.** The exact
  module-import refusal, marker ownership, reachability, one initializer AST
  copy, active-surface closure, private states, and public output are unchanged.
- **PLRC-006 — Closed implementation boundary.** Only the exact Phase B
  allowlist in section 7 may change. Inventory regeneration is only the
  mechanical consequence of canonical node-ID change.
- **PLRC-007 — No operational effect.** No adapter, SQL, database, migration,
  persistence, RuntimeBundle, selection, command, route, output, deployment,
  historical/window, production activation, legacy behavior, or #192 change.

## 5. Required negative cases

| Invariant | Supported counterexample | Required result |
| --- | --- | --- |
| PLRC-001 | Phase B adds `schema.sql` to a temporal list, copies the normalizer, or changes the architecture resource predicate | changed-path/source review refuses; stop for an architecture boundary |
| PLRC-002 | A test, selection adapter, or unrelated source contains `schema.sql` | no new publication state or scan is created; only the exact target is evaluated |
| PLRC-003 | A synthetic, otherwise conformant target adapter has `"kernel/schema.sql"` or a backslash-normalized equivalent string literal | existing temporal conformance entry point raises a resource-refusal error |
| PLRC-004 | Target AST is requested while the target is absent, before its markers qualify, more than once, or after rereading a path | focused custody/count test refuses; no pass result |
| PLRC-005 | Target imports `kernel.store` or `kernel.runtime_bundle_repository`, initializer imports target, or a target marker is incomplete | existing inherited refusal remains controlling |
| PLRC-006 | A non-allowlisted path changes, or inventory differs without canonical node-ID change | diff/inventory gate refuses |
| PLRC-007 | Phase B adds an adapter, migration, row, selection, route, output, or activation claim | stop before editing and propose the separate boundary |

## 6. Non-goals and stop conditions

This contract does not:

- create, register, import, execute, or publish the future adapter;
- read, parse, modify, migrate, or otherwise use `kernel/schema.sql`;
- modify `LEGACY_RESOURCE_NAMES`, `_legacy_resource_violations()`, source
  snapshot construction, its descriptor, or architecture import-firewall code;
- change the already-merged exact module classifier, `kernel.store`,
  `kernel.runtime_bundle_repository`, `kernel.runtime_bundle`, any SQL,
  migration, database role, grant, function, tenant, retained content, or
  RuntimeBundle state;
- reinterpret the sixteen-component catalog, lifecycle decision, carrier
  semantics, valid time, knowledge time, selection, command, or output law;
- change active artifacts, profiles, runtime imports, routes, materialization,
  historical/window execution, deployment, production/legacy activation, or
  #192.

Stop for a separate boundary if implementation needs an architecture predicate
change, a second resource identity, dynamic resource resolution, a source
snapshot change, a wider repository scan, an adapter file, database work, or
any operational authority.

## 7. Smallest coherent Phase B change

After exact-head Phase A review and a valid same-task decision approval, the
same draft pull request may change only:

| Exact path | Permitted reason |
| --- | --- |
| `docs/rfcs/OFARM_Temporal_RuntimeBundle_Publication_Legacy_Resource_Conformance_Admission_RFC_v0_1.md` | Preserve the reviewed contract and append only approval evidence/status transition required by the active workflow. |
| `conformance/temporal_contract_candidate_check.py` | In the existing exact target-present branch, obtain one target AST from the existing snapshot and apply the unchanged architecture-owned resource predicate; refuse on any result. |
| `kernel/tests/test_temporal_contract_governance.py` | Add focused temporary-source proof of exact-target resource refusal and bounded AST custody, without an adapter file or checker-owner rewrite. |
| `conformance/review_baseline_test_inventory.json` | Regenerate only when mechanically required by a change to the canonical collected test-node inventory, including a count or node-ID change. |

The architecture checker is deliberately not in this allowlist. This is the
minimum coherent change because the resource vocabulary, normalization, source
snapshot, and future publication branch already exist. A new resource registry,
another scanner, an adapter stub, or a general source-policy abstraction would
create authority beyond the demonstrated gap.

## 8. Traceability and verification

| Invariant | Owning seam | Focused evidence |
| --- | --- | --- |
| PLRC-001 | existing architecture resource predicate | exact source review; no architecture path changes |
| PLRC-002–004 | existing publication classifier's target-present branch | temporary target source with a legacy literal, AST-count/custody test, and temporal refusal |
| PLRC-005 | existing publication tests and classifier | module-import, absent-target, initializer, marker, output, and reachability regressions remain passing |
| PLRC-006 | exact allowlist and canonical inventory | name-only diff and inventory comparison |
| PLRC-007 | unchanged operational authorities | diff review and hosted conformance |

Phase A verification must show that only this RFC changed; the reviewed base
is exact; the architecture predicate recognizes `schema.sql`; the current
publication classifier has no target-resource check; the current temporal,
architecture, and package gates pass under exact CPython 3.12.13; and
`git diff --check` passes.

Later Phase B verification must additionally run focused temporal-governance
tests, architecture and temporal conformance entry points, the package check
immediately before every commit, Ruff 0.15.5 for changed Python, canonical
inventory comparison, exact allowlist/card-envelope comparison, fresh hosted
conformance and native verifier lanes, and exact-head review with no Blocker.

## 9. Provisional posture and review disposition

The decision is pre-deployment conformance hardening. It is acceptable because
the adapter is absent, no resource is consumed, and the proposed refusal is
static, deterministic, and default-deny. Evidence requiring redesign is a
need to support a second resource identity, a dynamic resource reference, or
a publisher that legitimately depends on legacy persistence; each needs a new
versioned boundary.

Open decisions: none. The exact resource identity and the existing authority
are observable at the reviewed base.

- Blockers: none known before exact-head Phase A review.
- Follow-up: the future adapter implementation remains separately governed;
  publication semantics and any database work are not implied by this contract.
- Preferences: none.

This Phase A stops before conformance implementation, adapter creation, and a
live decision card. The next lawful action is exact-head plain-English review
of this one-file contract in its already-created draft pull request.
