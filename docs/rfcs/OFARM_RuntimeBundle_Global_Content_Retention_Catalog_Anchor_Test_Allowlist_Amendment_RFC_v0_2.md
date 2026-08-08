# OFARM2 RuntimeBundle Global Content Retention Catalog-Anchor Verification-Test Allowlist Amendment — Phase A Contract v0.2

**Status:** proposed Phase A contract; documentation-only, inactive, and
unapproved

**Contract identity:**
`ofarm.runtime-bundle-global-content-retention-catalog-anchor-test-allowlist-amendment.issue176.v0.2`

**Decision identity:**
`ISSUE176-RUNTIME-CONTENT-RETENTION-CATALOG-ANCHOR-TEST-ALLOWLIST-001`,
version `1`

**Reviewed base:** `95bf5919b6bd3894b4208ab7760e94b328c4173b`

**Phase A RFC path:**
`docs/rfcs/OFARM_RuntimeBundle_Global_Content_Retention_Catalog_Anchor_Test_Allowlist_Amendment_RFC_v0_2.md`

**Primary ticket:** #176

**Primary trust boundary:** versioned governance of the exact database Phase B
verification-path envelope

**Phase A pull-request boundary:** this RFC only

## 1. Problem and decision

The approved contract
`ofarm.runtime-bundle-global-content-retention-admission.issue176.v0.1`
requires database Phase B to replace the tenant catalog verifier/observer
trust anchor in `deployment/postgresql/catalog_identity.py` with the exact
mechanical version-9 identity.

Two existing tests must advance mechanically with that production change.
`kernel/tests/test_postgresql_catalog_identity_unit.py` independently pins
that production literal. Its current
`test_tenant_v8_external_catalog_anchor_is_literal` assertion must advance to
the exact V9 literal when the production anchor advances. The second,
`kernel/tests/test_temporal_contract_governance.py`, authenticates the exact V7
and V8 historical fixtures from the current migration authority and catalog
source. Its helpers currently accept only a seven- or eight-migration authority
and only an exact current V7 or V8 catalog source. Migration 0009 and the V9
production anchor therefore make both tests deterministically refuse. The
parent contract permits the production files but accidentally omits both test
paths. Leaving either test unchanged fails the baseline; editing either
violates parent section 17 stop condition 5. Implementation stopped before any
edit.

After this exact amendment is explicitly approved and merged, and after a
renewed explicit database Phase B request, add exactly these two paths to the
parent section 12.3 allowlist:

```text
kernel/tests/test_postgresql_catalog_identity_unit.py
kernel/tests/test_temporal_contract_governance.py
```

The catalog-identity unit test may change only to:

1. rename the exact tenant anchor test from its V8 posture to V9 when its node
   ID changes;
2. replace the expected tenant anchor literal with the value mechanically
   observed from the clean disposable V9 target; and
3. preserve all existing injected-anchor, one-byte mutation, unset-anchor,
   routine-pair, and fail-closed tests.

The temporal-governance test may change only to:

1. allow `_selection_storage_v7_authority()` to slice and authenticate the
   exact V7 prefix from a current authoritative release of length 7, 8, or 9;
2. add the mechanically observed exact V9 catalog digest and exact V9
   `catalog_identity.py` source SHA-256 as test-only evidence;
3. allow `_selection_storage_catalog_source(...)` to recognize the exact
   current V9 production source in addition to the exact current V7 and V8
   sources, before deriving the already fixed historical V7 and V8 sources;
4. update `_selection_storage_expected_current_state()` to apply only the
   following closed current-repository state rule:

   | Exact authenticated repository state | Independently expected public state |
   | --- | --- |
   | V7 authority and selection adapter absent | `CONFORMANT_ABSENT` |
   | V8 authority with exact migration 0008 selection pair and exact adapter | `CONFORMANT_CLASSIFIED` |
   | V9 authority with the exact preserved migration 0008 selection pair, exact adapter, and exact governed final migration 0009 | `CONFORMANT_CLASSIFIED` |

   A partial pair, migration count other than 7, 8, or 9, wrong migration-0008
   identity, wrong migration-0009 identity, or any other unrecognized state
   must refuse. A generic `len(migrations) >= 8`, newest-release,
   dynamic-current, future-version, or fallback rule is forbidden;
5. preserve the historical name and parameter identity of
   `test_selection_storage_current_state_is_exact_absent`, and preserve its
   controlled partial-pair refusal inside that same collected node;
6. preserve the existing exact V7 and V8 fixture identities rather than
   replacing them with a caller-selected, environment-selected, dynamic, or
   generic "current" identity; and
7. preserve all existing GCRC V7/V8/V9 state, marker, isolation, output, and
   refusal tests without changing the production checker, migration loader,
   runtime, database, or semantic behavior.

This amendment changes no parent semantic decision. It grants no SQL or
implementation effect by itself. The earlier implementation request named the
unamended nine-path envelope and must not silently authorize a tenth or
eleventh path.

## 2. Reviewed authority and authority map

| Authority | Exact reviewed identity | Authority retained |
| --- | --- | --- |
| Parent database contract | 38,116-byte `docs/rfcs/OFARM_RuntimeBundle_Global_Content_Retention_Admission_RFC_v0_1.md`; `sha256:aa5de04c08390e1439d59f39c4b6f5608e8b43b320fec531721d9c53b936873a` | SQL law, RBGC-001–018, original nine paths, and stop conditions |
| Merged conformance contract | 40,726-byte `docs/rfcs/OFARM_RuntimeBundle_Global_Content_Retention_Conformance_Admission_RFC_v0_1.md`; `sha256:7df5ebcb89e2a758c7906e9c4053228e5e151d049ff40e07f83d23a706d7a016` | exact V8-absent/V9-classified repository admission |
| Production anchor | 12,016-byte `deployment/postgresql/catalog_identity.py`; `sha256:130a96edc2b9f4ad92a640c1c34150fe6126bd3945a48704a96896bb88a0f1a7` | sole external tenant verifier/observer trust anchor |
| Existing unit test | 7,060-byte `kernel/tests/test_postgresql_catalog_identity_unit.py`; `sha256:1ba7d07a838f41722dc29f21907534d7e07366d542c4cfc686143a6daa2c1675` | exact literal and fail-closed anchor verification |
| Existing temporal-governance test | 127,404-byte `kernel/tests/test_temporal_contract_governance.py`; `sha256:fc7587b73fb490f4ac07b93b25af4931fdc00d00b919ab6f5940cd25d8eb0ee3` | exact historical V7/V8 fixture identity and V9 conformance evidence |
| Baseline-transition test admission | 26,314-byte `docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_Activation_Baseline_Transition_Test_Admission_RFC_v0_1.md`; `sha256:136318ac6dd49987b4652710ab55e68364ea5aa2f23f58d274a40f809fcb4168` | BTT-004/BTT-005 historical fixture law, BTT-006 current-state smoke rule, and BTT-009 node-ID preservation |
| Merged prerequisite | PR #296, merge `95bf5919b6bd3894b4208ab7760e94b328c4173b` | conformance completion only |

The parent remains sole authority for function semantics, migration behavior,
publisher custody, transactions, inertness, negative cases, and all original
paths. This amendment owns only two added test paths and their narrow edit
shapes. The merged conformance contract retains ownership of the temporal
test's historical identities, state model, marker law, isolation, output, and
refusal semantics; this amendment permits only their mechanical V9 fixture
continuation.
As later versioned test-boundary law, this amendment supersedes only the
BTT-006 rule that another migration count must fail, and only for the exact
governed V9 current-repository state defined in section 1. BTT-004 and BTT-005
retain the exact historical V7/V8 fixtures. BTT-006 retains its independent
expected-state comparison and controlled partial-pair refusal. BTT-009 retains
the historical current-state test node and parameter identities. No other BTT
rule is amended or reinterpreted, and the frozen BTT contract is not edited.
The existing catalog identity algorithm over a clean disposable target owns
the future V9 catalog digest. SHA-256 over the exact future production source
owns its source identity. The user, AI, environment, and this RFC choose
neither value.
The canonical test inventory remains mechanical node-ID evidence. Every other
database, runtime, temporal, legacy, output, and #192 authority is unchanged.

The reviewed repository is exact migration V8 with 0009 absent. The temporal
checker and package contract check pass. Authority drift stops the amendment;
there is no silent re-pin.

## 3. Trust model, state, and ordering

Protected assets are the closed Phase B path envelope, exact correspondence
between the production anchor and both test fixtures, the frozen historical
V7/V8 identities, all RBGC invariants, the closed production semantic surface,
and the production-versus-legacy firewall.

Trusted components are the exact merged parent and conformance contracts, the
existing catalog identity algorithm and tests, the supported collector and
package checker, and a later clean disposable PostgreSQL 17 target. Untrusted
inputs are copied, guessed, caller-, AI-, PR-, documentation-, or
environment-supplied digests and any claim that either exact test can be
ignored or weakened.

Repository-host, task-platform, database-owner, operating-system, PostgreSQL,
or hash compromise is outside this documentation boundary. The parent threat
model is unchanged.

```text
DATABASE_PHASE_B_REQUESTED_UNDER_NINE_PATH_ENVELOPE
  -> OMITTED_EXISTING_TEST_PATHS_DISCOVERED
  -> STOP_WITHOUT_IMPLEMENTATION
  -> VERSIONED_AMENDMENT REVIEWED AND APPROVED
  -> DOCUMENTATION_ONLY_AMENDMENT MERGED
  -> RENEWED EXPLICIT DATABASE_PHASE_B REQUEST
  -> ELEVEN_PATH DATABASE_PHASE_B MAY BEGIN
```

In future Phase B, the V9 target must be derived first. The production anchor,
catalog-unit-test literal, and temporal-governance V9 fixture evidence then
change in the same PR. Neither test may be weakened before the values exist,
and the three changes must never be split.

## 4. Invariants and negative cases

- **GCAA-001 — Parent law unchanged.** Parent bytes, RBGC-001–018, SQL law,
  non-goals, and stop conditions are not edited, relaxed, or reinterpreted.
- **GCAA-002 — Two added paths.** The only allowlist additions are the exact
  two test paths above.
- **GCAA-003 — Exact test purposes.** In the catalog unit test, only the tenant
  V8-to-V9 test name and expected literal may change. In the temporal-governance
  test, only the addition of exact V9 current-source evidence alongside
  preserved exact V7/V8 current-source recognition, the authenticated 7/8/9
  release-length fixture admission, and the closed current-state-helper
  extension in section 1 may change. That helper must return
  `CONFORMANT_CLASSIFIED` only for the exact V8 or V9 cases in section 1 and
  must retain exact V7/ABSENT and all refusal behavior. Existing V7/V8
  identities, production-checker behavior, and all fail-closed and GCRC tests
  remain intact.
- **GCAA-004 — Mechanical digest custody.** The V9 catalog digest comes only
  from the existing algorithm over a clean disposable V9 target; its source
  identity comes only from SHA-256 over the exact future production source.
- **GCAA-005 — Atomic verification.** Production anchor, catalog-unit-test
  literal, and temporal-governance V9 fixture evidence change in the same
  future implementation PR.
- **GCAA-006 — Mechanical inventory and historical smoke node.** The temporal
  current-state test name and parameter identity do not change. Inventory
  changes only for an actual canonical node-ID change caused by the separately
  permitted catalog-unit-test V8-to-V9 rename.
- **GCAA-007 — Phase A has no implementation.** This PR changes only this RFC.
- **GCAA-008 — Renewed request required.** Approval and merge do not widen the
  earlier implementation request.
- **GCAA-009 — Fail closed.** Another needed path or semantic change stops for
  another reviewed boundary.

| Counterexample | Required result |
| --- | --- |
| Parent RFC or an RBGC rule changes | Refuse under GCAA-001 |
| Another code, test, workflow, SQL, or documentation path is added | Refuse under GCAA-002/GCAA-007 |
| Anchor test is deleted, generalized, or loses a mutation/refusal case | Refuse under GCAA-003 |
| Temporal fixture uses dynamic/current identity or changes conformance semantics | Refuse under GCAA-003 |
| Exact V9 current state refuses or returns anything other than `CONFORMANT_CLASSIFIED` | Refuse under GCAA-003 |
| A partial pair, unknown migration count, wrong row identity, or future version is accepted | Refuse under GCAA-003 |
| Digest is guessed, copied, or selected through an input | Refuse under GCAA-004 |
| Production anchor and either test fixture are split | Stop merge under GCAA-005 |
| Temporal smoke node is renamed, parametrized, or loses its partial-pair refusal | Refuse under GCAA-006 |
| Inventory changes while collected node IDs do not | Refuse under GCAA-006 |
| Database work resumes without a renewed request | Stop under GCAA-008 |
| Another omitted path or unresolved semantic decision appears | Stop under GCAA-009 |

These are repository-governance entry points. Phase A creates no runtime entry
point and therefore does not invent a runtime negative case.

## 5. Exact boundaries and non-goals

This Phase A PR may change only this RFC. The amended future Phase B allowlist
is exactly:

1. `kernel/migrations/0009_runtime_bundle_global_content_retention.sql`;
2. `deployment/postgresql/migration_sets.py`;
3. `deployment/postgresql/catalog_identity.py`;
4. `deployment/postgresql/README.md`;
5. `kernel/tests/test_migration_sets.py`;
6. `kernel/tests/test_postgresql_tenant_migration.py`;
7. `kernel/tests/test_postgresql_readiness_unit.py`;
8. `kernel/tests/test_postgresql_structural_compatibility.py`;
9. `conformance/review_baseline_test_inventory.json`, only when mechanically
   required by changed canonical node IDs; and
10. `kernel/tests/test_postgresql_catalog_identity_unit.py`, only as defined
    in section 1; and
11. `kernel/tests/test_temporal_contract_governance.py`, only as defined in
    section 1.

No other path is permitted. All parent section 17 stop conditions remain
controlling.

This amendment does not implement or choose migration 0009, its function,
ACL, digest, structural identity, or catalog anchor. It does not alter the
content length bound, replay, transaction, role, login, membership,
provisioning, direct table grants, or publisher function. It retains no
content, publishes no bundle, chooses no tenant, creates no selection, and
adds no runtime, route, command, read, historical/WINDOW, materialization,
output, deployment, legacy, or #192 behavior. It does not change the production
temporal checker, migration loader, frozen V7/V8 evidence, or conformance law.
It does not edit the frozen baseline-transition contract; it lawfully replaces
only the exact BTT-006 restriction stated above. Unrelated parent wording
preferences remain outside this correction.

## 6. Smallest coherent change and provisional posture

Two existing test paths are the minimum coherent addition. One pins the
production anchor literal; the other authenticates the exact historical source
and migration fixtures from the current release. Deleting either assertion,
hiding values behind indirection, keeping stale values, adding compatibility
aliases, or dynamically selecting V8/V9 would weaken rather than verify the
production trust anchor and its historical conformance evidence.

Sources of semantic truth added: zero. Verification paths added: two. Schemas,
services, registries, roles, credentials, digest inputs, fallbacks, and runtime
seams added: zero. No rewrite is justified.

Not provisional. The semantic pairing of a production anchor and its exact
test is durable. The pre-deployment AI approval evidence remains provisional
and must be replaced by independently human-controlled, independently
verifiable approval or signing before deployment.

## 7. Traceability and verification

| Invariants | Owning seam | Negative evidence | Verification |
| --- | --- | --- | --- |
| GCAA-001 | exact parent identity | parent drift | byte length and SHA-256 |
| GCAA-002, 007 | changed-file boundary | any extra path | name-only diff |
| GCAA-003 | catalog-anchor and temporal-governance tests | weakened, dynamic, semantic, or non-closed current-state edit | focused diffs; exact V7/V8/V9 smoke cases; both test modules |
| GCAA-004, 005 | production anchor plus both exact tests | guessed or split value | disposable V9 observation, source hash, and equality |
| GCAA-006 | historical temporal smoke node and canonical inventory generator | renamed/parametrized smoke or changed inventory without changed nodes | collected-node comparison and controlled partial-pair refusal |
| GCAA-008 | task request record | absent renewed request | task evidence check |
| GCAA-009 | stop-condition review | another path or authority | implementation diff audit |

Phase A verification is:

```text
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --name-only <reviewed-base>...HEAD
```

Future Phase B retains all parent section 15.2 commands and hosted PostgreSQL
and native gates, plus:

```text
python3 -m pytest -q kernel/tests/test_postgresql_catalog_identity_unit.py
python3 -m pytest -q kernel/tests/test_temporal_contract_governance.py
```

Passing evidence is not deployment, publication, selection, activation, or
current truth.

## 8. Open decisions, review disposition, and stop conditions

Open decisions: none. The V9 digest is mechanical; parent SQL semantics are
closed and are not reopened here.

- **Blockers addressed:** the mandatory production-anchor and migration-release
  changes had two existing exact-evidence tests outside the allowlist, and the
  admitted temporal test's current-state helper required an exact V9 case.
- **Follow-up:** after approval and merge, obtain one renewed explicit Phase B
  request naming this amendment and the eleven-path envelope.
- **Preferences:** none.

Stop if an authority identity differs; reviewed `main` is not exact V8 with
0009 absent; another path is needed; parent semantics or RBGC invariants must
change; this RFC would pin the future digest; this PR changes another file; an
implementation effect enters Phase A; or exact-head review finds a
demonstrated unresolved blocker.

After merge, stop again until the architect sends a renewed explicit request
naming the parent contract, this amendment, the eleven-path envelope,
disposable targets, and the no-retained-state rule.
