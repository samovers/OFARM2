# OFARM2 RuntimeBundle Repository Legacy Classification Admission — Phase A Contract v0.1

**Status:** architect-approved Phase A design; pre-deployment only, with no
architecture-checker, temporal-checker, repository, runtime, database, route,
output, deployment, legacy-activation, or #192 effect until the separately
bounded implementation is completed and verified

**Issue:** #176

**Contract identity:**
`ofarm.architecture-runtime-bundle-repository-legacy-classification-admission.issue176.v0.1`

**Reviewed base:** `03acc06547a87a322f43c239de9617c4fd81e0c2`

**Originating evidence:** PR #303 exact-head re-review comment
`5250373713`

**Primary trust boundary:** executable architecture classification of the exact
Python module `kernel.runtime_bundle_repository` as a quarantined legacy-M1
dependency that production code and the future isolated temporal RuntimeBundle
publisher may not import

**Phase A boundary:** this RFC only

**Intended complete pull-request boundary after approval:** this RFC, one
exact-module addition to the existing architecture classifier, focused
architecture and temporal-consumer tests, and mechanical test-inventory
regeneration only when canonical node IDs change

## 1. Problem and goal

The merged catalog-publication and publication-conformance contracts say that
`kernel/runtime_bundle_repository.py` is a quarantined legacy-M1 authority and
must not become a dependency of the future isolated temporal RuntimeBundle
publisher. The temporal publication classifier correctly delegates outbound
legacy-import decisions to the architecture checker's one existing predicate,
`_is_legacy_module()`.

The predicate does not currently include
`kernel.runtime_bundle_repository`. A future publisher could therefore import
that exact module without triggering the new outbound legacy-dependency
refusal. Duplicating the identity in the temporal checker would close one case
while creating a second source of architecture truth.

The governed source snapshot at the reviewed base establishes all three facts
needed for the narrow decision:

```text
production reachability: absent
legacy reachability through kernel.store from fixed roots:
  kernel.legacy_m1.api -> kernel.store -> kernel.runtime_bundle_repository
  kernel.legacy_m1.runtime -> kernel.store -> kernel.runtime_bundle_repository
current architecture legacy classification: false
```

This contract establishes one decision only:

> Add the exact module identity `kernel.runtime_bundle_repository` to the
> architecture checker's existing exact `LEGACY_MODULES` set. Both the
> architecture firewall and its already-implemented temporal consumer must use
> that same predicate. Do not add a prefix, another identity, or a duplicate
> temporal list.

This is trust-boundary membership, not a judgment that the repository module
is poorly implemented. Its immutable persistence behavior, tests, callers,
and database semantics remain unchanged. This Phase A does not implement the
decision.

## 2. Learning value

The change will close a demonstrated production-versus-legacy firewall gap
with one authority-owned identity rather than a temporal special case. It also
proves that an isolated future adapter can reuse the architecture classifier
without allowing the classifier and its consumer to drift.

## 3. Governing authority and non-goals

The reviewed inputs are:

| Authority | Exact reviewed identity |
| --- | --- |
| Repository base and merged PR #303 | `03acc06547a87a322f43c239de9617c4fd81e0c2` |
| Architecture report | `reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md`; 96,406 bytes; `sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256` |
| ADR 0002 | `docs/adr/0002-valid-time-and-knowledge-time.md`; 61,427 bytes; `sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796` |
| Source-snapshot contract | `ofarm.architecture-python-source-snapshot-admission.issue176.v0.1`; 82,758 bytes; `sha256:6e4307077525f2bbb48992fa4c652ab75d279875063bd715cf21dc1f1d3216d5` |
| Catalog-publication contract | `ofarm.temporal-runtime-bundle-catalog-publication-admission.issue176.v0.1`; 47,814 bytes; `sha256:2161e9368f85b373b7cf54b6708edb7b291596defcf9683342e9583657a2298f` |
| Publication-conformance contract | `ofarm.temporal-runtime-bundle-publication-conformance-admission.issue176.v0.1`; 42,596 bytes; `sha256:17014b754f7401a5ccf809dd8bb4281875592bfc0732abf08ca47dc378fb7cb1` |
| Current architecture checker | `conformance/rewrite_architecture_check.py`; 73,222 bytes; `sha256:8e0b3c7b4de3ab499726585a687c600476458d00ae18cc66864ac875d3536836` |
| Exact classified target | `kernel/runtime_bundle_repository.py`; 20,445 bytes; `sha256:9f176a754579ebd7b92403d693532b7b8673dc659f3fcc20ae01f64596605a79` |

Neither this Phase A nor its intended implementation will:

- amend the architecture report, ADR 0002, or a merged RFC;
- edit, move, wrap, deprecate, execute, or delete
  `kernel/runtime_bundle_repository.py`;
- change `kernel.store`, `kernel.runtime_bundle`, `kernel.schema.sql`, a
  migration, SQL function, database role, grant, transaction, or durable row;
- create the publication adapter or change the temporal checker;
- create another legacy predicate, set, prefix, registry, manifest, schema,
  service, plugin, compatibility alias, or caller-selectable policy;
- classify `kernel.runtime_bundle` or every repository-shaped module as
  legacy;
- change RuntimeBundle selection, command integration, valid or knowledge
  time, current-state reads, historical or window execution, routes,
  materialization, outputs, profiles, or active artifacts;
- activate or deploy production or legacy behavior; or
- implement, depend on, or change #192 behavior.

## 4. Trust model

Protected assets are the closed production import graph, the production-versus-
legacy firewall, the future publisher's isolation, the exact legacy M1 path
that still uses the repository, the single source of legacy classification,
and every unchanged temporal, database, RuntimeBundle, output, and #192
authority.

Trusted inputs are the exact reviewed authorities above, the existing fixed
Python source-snapshot descriptor and builder, the snapshot's immutable module
identities, import graph, and reachability maps, and the current architecture
and temporal conformance entry points under the repository-required CPython
3.12.13 execution profile.

Untrusted inputs are proposed Python source, import statements, alternate
paths or module names, caller data, environment configuration, generated
claims, repository credentials, and any request that says a dependency is safe.
None may choose, remove, or extend legacy classification.

In scope are an accidental direct or indirect production import of the exact
module, a direct import from the future publisher, omission or duplication of
the exact identity, source substitution visible to the snapshot, and an
out-of-boundary implementation edit. Static imports are evaluated from one
authenticated snapshot, so there is no second file-read time-of-check/time-of-
use boundary in this change.

Out of scope are a compromised interpreter, dependency, operating system,
Git/CI service, repository host, or reviewer; arbitrary in-process mutation
after snapshot construction; undetectable filesystem replacement; and a
malicious operator able to replace both implementation and independent review
evidence coherently. Detectable source, graph, identity, or path disagreement
remains in scope and must not produce a pass.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Governance-before-automation, deterministic enforcement, and default-deny posture | Exact architecture report in section 3 |
| Meaning of valid time and tenant knowledge order | ADR 0002; unchanged here |
| Decision that the legacy Store, schema, and RuntimeBundle repository are not future publisher dependencies | Merged catalog-publication contract |
| Requirement that the future publisher refuse outbound legacy dependencies | Merged publication-conformance contract |
| Python module identity, static import edges, and production/legacy reachability | Existing `PythonSourceSnapshotV1` authority |
| Exact-module membership in the executable architecture legacy classifier | `LEGACY_MODULES` in `conformance/rewrite_architecture_check.py` |
| One executable answer for prefix and exact-module legacy membership | Existing `_is_legacy_module()` predicate |
| Production import-path refusal | Existing architecture firewall consuming that predicate |
| Future publisher's direct outbound legacy-import refusal | Existing temporal publication classifier consuming that same predicate |
| Existing legacy use of the repository | `kernel.legacy_m1.api -> kernel.store -> kernel.runtime_bundle_repository`; unchanged |
| Approval and bounded pre-deployment execution | Active AI-assisted same-task decision workflow |
| Audit-runtime behavior | #192; outside this contract |

There is no fallback classifier. In particular, the temporal checker must not
copy the module identity, and caller data cannot claim that an import is
production-safe.

## 6. State and ordering

This contract has no runtime or database state machine. Its repository
transition is closed:

```text
REVIEWED_BASE_OMITS_EXACT_IDENTITY
  -> PHASE_A_REVIEW
  -> EXPLICIT_SAME_TASK_APPROVAL
  -> ADD_EXACT_IDENTITY_ONCE
  -> FOCUSED_ARCHITECTURE_AND_CONSUMER_VERIFICATION
  -> EXACT_HEAD_REVIEW_AND_HOSTED_GATES
  -> MERGE
```

After implementation, a conformance run orders evidence as follows:

1. the existing source-snapshot authority authenticates and captures one
   package tree;
2. it derives exact module identities, static import edges, and reachability;
3. `_is_legacy_module()` resolves the exact target from the architecture-owned
   set;
4. the architecture firewall refuses any production path reaching it; and
5. the already-existing temporal publication classifier refuses a direct edge
   from the future publisher to it.

The current legacy path remains lawful because the firewall prevents
production from reaching a classified legacy module; it does not prohibit a
legacy root from using its own legacy dependency. Adding a prefix, classifying
the shared RuntimeBundle model, editing either consumer, or changing an
operational authority is a forbidden transition and stops this boundary.

## 7. Invariants and acceptance criteria

- **RBRLC-001 — One exact identity.** The architecture exact-module set contains
  `kernel.runtime_bundle_repository` exactly once. No new prefix or related
  module is admitted by this contract.
- **RBRLC-002 — One classifier.** The architecture firewall and temporal
  publication classifier continue to consume the same existing
  `_is_legacy_module()` predicate; no duplicate legacy list or temporal special
  case exists.
- **RBRLC-003 — Production refusal.** A supported production import path that
  reaches the exact repository module makes the architecture gate fail with
  the complete discovered path.
- **RBRLC-004 — Publisher refusal.** The supported temporal conformance entry
  point refuses a future exact publication adapter that directly imports the
  repository module.
- **RBRLC-005 — Legacy preservation.** The reviewed current tree remains
  architecture-conformant: the repository is absent from production
  reachability and present only in legacy reachability through `kernel.store`.
- **RBRLC-006 — Classification only.** The target module's bytes, behavior,
  callers, persistence semantics, database objects, and public APIs do not
  change.
- **RBRLC-007 — Fail closed.** Missing, malformed, substituted, or ambiguous
  snapshot or classifier evidence cannot be accepted as proof of a safe
  dependency. Existing source-snapshot and gate refusal behavior remains the
  owner of detailed failures.
- **RBRLC-008 — Closed implementation boundary.** Every changed path is in the
  exact allowlist in section 9.2; inventory changes are only the mechanical
  consequence of canonical node-ID changes.
- **RBRLC-009 — No operational effect.** No runtime, database, selection,
  command, temporal execution, route, read, materialization, output, profile,
  deployment, or active-artifact state changes.
- **RBRLC-010 — Audit separation.** No #192 path, behavior, event, service,
  receipt, health rule, or authority changes.

## 8. Required negative cases

| Invariant | Counterexample from a supported gate | Required result |
| --- | --- | --- |
| RBRLC-001 | The exact identity remains absent, appears twice in generated source, a prefix is added, or `kernel.runtime_bundle` is classified | focused exact-membership/scope test or review fails |
| RBRLC-002 | The temporal checker gains a private repository-name exception or another legacy collection | exact changed-path/source review refuses; existing consumer must remain unchanged |
| RBRLC-003 | Temporary production tree: `kernel.api -> kernel.helper -> kernel.runtime_bundle_repository` | architecture gate reports the full path and fails |
| RBRLC-004 | Temporary exact publication adapter imports `kernel.runtime_bundle_repository` | temporal candidate conformance raises its existing legacy-authority refusal |
| RBRLC-005 | The current snapshot reports the target in production reachability, loses legacy reachability through `kernel.store`, or the architecture checker fails after the set addition | stop; do not merge or alter another module to make the test pass |
| RBRLC-006 | Implementation edits the repository, Store, RuntimeBundle model, schema, migration, or either checker consumer | changed-path gate refuses |
| RBRLC-007 | Snapshot authority is unavailable, substituted, malformed, or inconsistent | existing architecture or temporal entry point returns non-success; never treat the dependency as safe |
| RBRLC-008 | Any non-allowlisted path changes, or inventory changes without a canonical node-ID change | exact diff/inventory gate refuses |
| RBRLC-009 | The change creates an adapter, row, selection, route, output, activation, or deployment claim | invalid out-of-boundary effect; stop before editing |
| RBRLC-010 | A #192 file or behavior is needed to complete or test the classification | stop and propose that boundary separately |

## 9. Proposed architecture and smallest coherent change

### 9.1 Phase A

This RFC is the only Phase A change. It records the demonstrated gap, exact
authority, invariants, negative cases, implementation allowlist, verification,
and stops. It does not alter the active classifier.

### 9.2 Exact complete pull-request allowlist

After exact-head Phase A review and a valid same-task decision approval, the
same named draft PR may change only:

| Exact path | Permitted reason |
| --- | --- |
| `docs/rfcs/OFARM_Architecture_RuntimeBundle_Repository_Legacy_Classification_Admission_RFC_v0_1.md` | Preserve the reviewed contract and append only the compact approval evidence/status transition required by the active workflow. |
| `conformance/rewrite_architecture_check.py` | Add the one exact module string to the existing `LEGACY_MODULES` set. |
| `kernel/tests/test_rewrite_architecture_check.py` | Prove the supported production-path refusal and exact scope. |
| `kernel/tests/test_temporal_contract_governance.py` | Extend the existing direct-legacy-dependency case with this exact architecture-classified module, without changing temporal checker code. |
| `conformance/review_baseline_test_inventory.json` | Regenerate only when mechanically required by a change to the canonical collected test-node inventory, including a count or node-ID change. |

No other path is permitted.

### 9.3 Implementation shape

The implementation is one set member, one focused architecture negative test,
and one added row in the existing temporal consumer's parametrized negative
test. The inventory records only resulting canonical node-ID changes. No new
type, helper, state, output, API, or abstraction is needed.

This is the smallest coherent change because `LEGACY_MODULES` already owns
exact-module membership and `_is_legacy_module()` already has both required
consumers. A second temporal list, a generalized persistence classifier, a new
prefix, or a semantic source scanner would create more authority than the
demonstrated gap requires.

## 10. Elegance audit

- Sources of exact-module legacy truth after implementation: one.
- New classifier functions, registries, schemas, services, or runtime states:
  zero.
- New production or legacy modules: zero.
- Active set additions: one exact string.
- Consumer code changes: zero.
- Operational transition points: zero.
- Compatibility paths or fallbacks: zero.

Nothing is deleted because the defect is one omitted identity. Rewriting the
architecture checker or temporal classifier would be larger and would disturb
accepted source-snapshot and temporal conformance law.

## 11. Pull-request boundary and dependencies

The primary trust boundary is executable architecture classification of one
already-governed quarantined module. Tests and mechanical inventory evidence
travel with that boundary; no independent authority does.

This contract depends on merged PRs #301, #302, and #303. Later publication-
adapter work may assume only that the architecture predicate refuses this
exact dependency after this PR merges. It may not assume that the adapter is
authorized, implemented, production-reachable, selected, deployed, or allowed
to publish.

Reviewers must not require the publication adapter, a temporal-checker rewrite,
database work, broader repository classification, runtime integration, or
#192 work from this PR. Such work is a separate boundary.

## 12. Provisional design record

The technical classification is not provisional: it makes executable the
current reviewed contract decision that this exact module remains a
quarantined legacy-M1 dependency. If a later reviewed architecture promotes or
replaces that repository for production use, it must explicitly amend this
classification and its consumers in a new versioned boundary.

The same-task approval evidence is provisional pre-deployment evidence. Before
deployment, it must be replaced by an independently human-controlled and
independently verifiable approval or signing system.

Evidence requiring redesign is a legitimate production dependency on this
repository, a second repository identity needing classification, or a need for
semantic/dynamic-import analysis. None may be folded into this exact-module
change.

## 13. Traceability and verification

| Invariants | Owning seam | Negative evidence | Acceptance evidence |
| --- | --- | --- | --- |
| RBRLC-001–002 | existing `LEGACY_MODULES` and `_is_legacy_module()` | omitted/extra identity or duplicate consumer list | exact constant and source review |
| RBRLC-003 | existing architecture import firewall | production temporary tree reaches repository | focused architecture test and checker pass on real tree |
| RBRLC-004 | unchanged temporal publication consumer | future adapter directly imports repository | focused temporal governance case |
| RBRLC-005 | governed source snapshot reachability | real target becomes production-reachable or loses legacy path | snapshot assertion and architecture checker |
| RBRLC-006–008 | exact path allowlist and canonical inventory | operational path edit or unexplained inventory delta | name-only diff, inventory comparison, package check |
| RBRLC-009–010 | unchanged operational and #192 authorities | claimed runtime effect or #192 edit | diff review and hosted conformance |

Phase A verification must show:

- only this RFC changed;
- every authority identity in section 3 reconstructs from reviewed `main`;
- the target is absent from production reachability;
- it is legacy-reachable through `kernel.store` from both fixed legacy roots;
- the current predicate returns false, demonstrating the gap;
- the current architecture, temporal, and package conformance gates pass under
  exact CPython 3.12.13;
- `git diff --check` passes; and
- the Phase A changed-file set is exactly this RFC.

After approval, implementation verification must additionally include:

- focused architecture tests;
- focused temporal-governance tests;
- the architecture and temporal conformance entry points;
- package conformance immediately before every commit;
- Ruff 0.15.5 for changed Python;
- exact current-snapshot reachability assertions;
- canonical test inventory comparison; and
- hosted conformance and native verifier lanes at the exact head.

## 14. Open decisions, review disposition, and stop conditions

Open decisions: none. The exact target, authority owner, consumer, and minimal
implementation are already observable at the reviewed base.

Current review disposition:

- Blockers: none known before exact-head Phase A review;
- Follow-ups: the separately governed publication adapter after this boundary
  merges;
- Preferences: normalizing a missing private predicate into one temporal
  conformance exception remains the non-blocking preference recorded in PR
  #303 and is not needed to close this identity gap.

Stop without implementation or merge if:

1. Phase A exact-head review finds a demonstrated Blocker;
2. the active workflow approval is absent, invalid, superseded, cancelled, or
   no longer directly retrievable;
3. the reviewed base changes such that the target is production-reachable,
   its legacy reachability through `kernel.store` differs, or the governing
   contracts no longer name the module as quarantined;
4. implementation requires a new prefix, another identity, duplicate
   classifier, consumer edit, or another changed path;
5. adding the exact identity makes the real current architecture checker fail;
6. a database, migration, repository, Store, RuntimeBundle, adapter, runtime,
   selection, command, route, read, materialization, output, profile,
   deployment, production/legacy activation, or #192 change is required;
7. inventory changes are not exactly explained by canonical node-ID changes;
   or
8. an exact-head required check fails or a demonstrated Blocker remains.

This Phase A authorizes only the separately bounded implementation in its
already-created draft pull request. It does not authorize another boundary.

## Appendix A — Compact approval evidence

- **Decision:**
  `ISSUE176-RUNTIME-BUNDLE-REPOSITORY-LEGACY-CLASSIFICATION-001`, version `1`.
- **Codex task:** `019fa821-93c9-7ef1-8c94-1c0e92ea46b9`.
- **Complete live card:** stable reference `item-5467` in that task.
- **Architect approval:** stable reference `item-5468`, observed as a later
  task-user message in the same task.
- **Exact approval sentence:**
  `I approve OFARM2 decision ISSUE176-RUNTIME-BUNDLE-REPOSITORY-LEGACY-CLASSIFICATION-001 version 1.`
- **Implementation PR:** `https://github.com/samovers/OFARM2/pull/304`.
- **Evidence posture:** these task references and role/order observations are
  provisional AI-attested evidence of the architect's decision. This appendix
  is not approval authority, deployment authority, or an independently
  verifiable identity claim.
