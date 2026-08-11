# OFARM2 Architecture Legacy-Resource Normalization Admission — Phase A Contract v0.1

**Status:** proposed Phase A design; documentation-only, unapproved, and
without temporal checker, publication adapter, database, RuntimeBundle,
selection, runtime, route, output, deployment, legacy-activation, or #192
effect

**Issue:** #176

**Contract identity:**
`ofarm.architecture-legacy-resource-normalization-admission.issue176.v0.1`

**Reviewed base:** `c33778c46c09141a624b97db4f9a69cfb527f645`

**Primary trust boundary:** architecture-owned normalization and exact identity
classification of static legacy resource string literals

**Phase A boundary:** this RFC only

**Intended later Phase B boundary:** this RFC, the existing architecture
checker, its focused architecture test module, and canonical test-node
inventory regeneration only when mechanically required

## 1. Problem and goal

The architecture checker is the single owner of the legacy resource vocabulary:

```text
LEGACY_RESOURCE_NAMES = {"schema.sql"}
```

Its existing static AST evaluator normalizes backslashes and refuses the bare
literal `schema.sql` and paths ending in `/kernel/schema.sql`. It does not
refuse the direct repository-relative spelling `kernel/schema.sql`, because
that spelling has no leading slash. The backslash form normalizes to the same
unmatched spelling.

This is a demonstrated vocabulary-normalization gap. It prevents a later
temporal publication conformance boundary from refusing the direct static
reference without copying or changing architecture meaning. The later temporal
boundary is not part of this contract.

This contract establishes one decision only:

> The existing architecture legacy-resource evaluator must recognize exactly
> the normalized spellings `schema.sql`, `kernel/schema.sql`, and every path
> ending in `/kernel/schema.sql` for each existing exact legacy resource name.
> Backslashes are normalized once, by the existing evaluator. No resource name
> is added and no broader suffix or prefix rule is introduced.

For the current singleton vocabulary, the required accepted spellings are:

```text
schema.sql
kernel/schema.sql
kernel\\schema.sql
./kernel/schema.sql
/absolute/path/kernel/schema.sql
```

This is lexical classification only. It neither reads `kernel/schema.sql` nor
changes any publisher, checker consumer, or operational authority.

## 2. Learning value

The change removes the normalization ambiguity at its sole authority instead
of creating a temporal workaround. It preserves one source of resource meaning
and makes a later isolated consumer able to reuse that meaning without a
second list, path normalizer, or resource scanner.

## 3. Authority map

| Decision | Sole authority |
| --- | --- |
| Governance-before-automation and default-deny posture | Architecture report: `reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md`; 96,406 bytes; `sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256` |
| Valid/knowledge time semantics | ADR 0002; unchanged: `docs/adr/0002-valid-time-and-knowledge-time.md`; 61,427 bytes; `sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796` |
| Quarantined legacy-M1 status of `kernel/schema.sql` | Merged catalog-publication contract `ofarm.temporal-runtime-bundle-catalog-publication-admission.issue176.v0.1`; 47,814 bytes; `sha256:2161e9368f85b373b7cf54b6708edb7b291596defcf9683342e9583657a2298f` |
| Existing architecture legacy resource vocabulary, normalization, and static AST evaluator | `conformance/rewrite_architecture_check.py`; 73,266 bytes; `sha256:6893e9f658b84e2539e5734d9d694000a9847e06f3cb9d1e87b6622fb67cb806` |
| Focused architecture evidence | `kernel/tests/test_rewrite_architecture_check.py`; 56,696 bytes; `sha256:575488d43e0b2f64a9cdc66e28e77e840337746939e28f06a7c08140958f0505` |
| Exact module legacy classification | Merged PR #304 and its contract; `docs/rfcs/OFARM_Architecture_RuntimeBundle_Repository_Legacy_Classification_Admission_RFC_v0_1.md`; 23,142 bytes; `sha256:a2e82f2486a71a88f2f9ddb5cff02e5b32abbf1d652003a23572c9e119a01648`; unchanged |
| Temporal publication resource-consumer design | PR #305 only; outside and unapproved until this prerequisite is merged and re-pinned |
| Audit-runtime behavior | #192 only; outside this contract |

No temporal checker, caller, profile, environment value, file path, adapter,
or database object may define, expand, or normalize a legacy resource identity.

## 4. State, invariants, and negative cases

There is no runtime or database state transition. The closed classifier order
is:

```text
AST string constant
  -> replace backslash with slash once
  -> exact architecture-owned resource-name comparison
  -> legacy-resource violation or no violation
```

- **ALRN-001 — One authority.** `LEGACY_RESOURCE_NAMES` remains the sole
  resource vocabulary and `_legacy_resource_violations()` remains its only
  evaluator. No duplicate collection or external policy exists.
- **ALRN-002 — Exact normalized forms.** For every existing name, the
  normalized value matches only the bare name, `kernel/<name>`, or a value
  ending in `/kernel/<name>`.
- **ALRN-003 — Backslash equivalence.** `kernel\\schema.sql` has exactly the
  same classification as `kernel/schema.sql`; no second normalizer exists.
- **ALRN-004 — No over-classification.** `schema.sql.bak`,
  `kernel/schema.sqlx`, `not_kernel/schema.sql`, and an unrelated string
  literal remain non-violations.
- **ALRN-005 — Existing firewall preservation.** A production-reachable
  module containing any recognized form remains refused with the source line,
  normalized resource text, and complete production import path. Existing
  module-import and dynamic-import refusal behavior remains unchanged.
- **ALRN-006 — Closed implementation boundary.** Only section 6 paths may
  change; inventory changes only follow canonical node-ID changes.
- **ALRN-007 — No operational effect.** No temporal conformance, adapter,
  schema, repository, database, RuntimeBundle, selection, command, route,
  output, deployment, legacy activation, historical/window, or #192 behavior
  changes.

| Invariant | Supported counterexample | Required result |
| --- | --- | --- |
| ALRN-001 | Phase B adds a temporal resource list, caller override, or second normalizer | changed-path/source review refuses |
| ALRN-002 | Static AST literal is `kernel/schema.sql` | evaluator reports `kernel/schema.sql` as a legacy resource |
| ALRN-003 | Static AST literal is `kernel\\schema.sql` | evaluator reports the same normalized legacy resource result |
| ALRN-004 | Static AST literal is `schema.sql.bak` or `not_kernel/schema.sql` | evaluator reports no legacy-resource violation |
| ALRN-005 | Temporary production tree has a helper with `kernel/schema.sql` | architecture firewall reports the full production path and fails |
| ALRN-006 | A non-allowlisted path changes or inventory has an unexplained delta | diff/inventory gate refuses |
| ALRN-007 | Work requires a temporal checker, adapter, SQL, migration, row, selection, or output change | stop and propose that boundary separately |

## 5. Non-goals and stop conditions

This contract does not:

- add, remove, rename, or promote a legacy resource;
- introduce resource wildcard, directory, extension, substring, glob, or
  filesystem matching;
- read, parse, execute, migrate, or edit `kernel/schema.sql`;
- create or modify a temporal publication adapter or its conformance code;
- change source snapshot construction, module legacy classification,
  production/legacy roots, active artifacts, profiles, routes, runtime,
  database, selection, command, materialization, output, deployment, or #192.

Stop for a new boundary if the requested form is not one of the three exact
normalized forms, a second resource name is needed, dynamic resolution is
needed, source snapshot semantics must change, or a temporal consumer needs to
be edited. A later consumer must use the merged corrected evaluator; it may
not carry this change as a local workaround.

## 6. Smallest coherent Phase B change

After exact-head Phase A review and a valid same-task decision approval, the
same draft pull request may change only:

| Exact path | Permitted reason |
| --- | --- |
| `docs/rfcs/OFARM_Architecture_Legacy_Resource_Normalization_Admission_RFC_v0_1.md` | Preserve the reviewed contract and append only approval evidence/status transition required by the active workflow. |
| `conformance/rewrite_architecture_check.py` | Extend the existing evaluator's exact normalized comparison to recognize `kernel/<name>` without altering vocabulary or evaluator ownership. |
| `kernel/tests/test_rewrite_architecture_check.py` | Add focused evaluator and production-firewall cases for recognized and near-miss forms. |
| `conformance/review_baseline_test_inventory.json` | Regenerate only when mechanically required by a change to the canonical collected test-node inventory, including a count or node-ID change. |

The temporal checker and PR #305 RFC are deliberately excluded. The later
temporal boundary must rebase, authenticate this merged authority, and obtain
its own exact-head approval before it consumes the result.

## 7. Traceability and verification

| Invariant | Owning seam | Focused evidence |
| --- | --- | --- |
| ALRN-001–003 | existing vocabulary and evaluator | AST-literal cases for bare, repository-relative, backslash, and absolute kernel forms |
| ALRN-004 | unchanged exact comparison | near-miss AST-literal cases remain clear |
| ALRN-005 | existing import firewall | temporary production helper reports exact line/resource/path |
| ALRN-006 | exact allowlist and inventory | name-only diff and canonical inventory comparison |
| ALRN-007 | unchanged authorities | diff review, package check, and hosted conformance |

Phase A verification must show only this RFC changed; all authority pins match
reviewed `main`; the direct `kernel/schema.sql` and backslash forms are absent
from current predicate matches; architecture, temporal, and package gates pass
under exact CPython 3.12.13; and `git diff --check` passes.

Later Phase B verification must run focused architecture tests, architecture
and temporal conformance entry points, the package check immediately before
every commit, Ruff 0.15.5 for changed Python, canonical inventory comparison,
exact allowlist/card-envelope comparison, fresh hosted conformance and native
verifier lanes, and exact-head review with no Blocker.

## 8. Provisional posture and review disposition

This is pre-deployment architecture hardening. It is safe before deployment
because it changes only deterministic static classification and refuses more
precisely identified legacy resource spellings. Evidence requiring redesign is
a second resource identity, a dynamic path requirement, or a need for an
operational resource consumer; each requires a new versioned boundary.

Open decisions: none. The exact vocabulary, evaluator behavior, gap, and
minimal comparison change are observable at the reviewed base.

- Blockers: none known before exact-head Phase A review.
- Follow-up: PR #305 may be rebased and re-pinned only after this prerequisite
  merges; its temporal-consumer approval remains separate.
- Preferences: none.

This Phase A stops before architecture implementation, temporal conformance
work, a decision card, adapter creation, and every operational change. The
next lawful action is exact-head plain-English review of this one-file contract
in its already-created draft pull request.
