# OFARM2 RuntimeBundle Global Content Retention Catalog-Anchor Test Allowlist Amendment — Phase A Contract v0.2

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

The existing test
`kernel/tests/test_postgresql_catalog_identity_unit.py` independently pins
that production literal. Its current
`test_tenant_v8_external_catalog_anchor_is_literal` assertion must advance to
the exact V9 literal when the production anchor advances. The parent contract
permits the production file but accidentally omits this test path. Leaving the
test unchanged fails the baseline; editing it violates parent section 17 stop
condition 5. Implementation stopped before any edit.

After this exact amendment is explicitly approved and merged, and after a
renewed explicit database Phase B request, add exactly this path to the parent
section 12.3 allowlist:

```text
kernel/tests/test_postgresql_catalog_identity_unit.py
```

That file may change only to:

1. rename the exact tenant anchor test from its V8 posture to V9 when its node
   ID changes;
2. replace the expected tenant anchor literal with the value mechanically
   observed from the clean disposable V9 target; and
3. preserve all existing injected-anchor, one-byte mutation, unset-anchor,
   routine-pair, and fail-closed tests.

This amendment changes no parent semantic decision. It grants no SQL or
implementation effect by itself. The earlier implementation request named the
unamended nine-path envelope and must not silently authorize a tenth path.

## 2. Reviewed authority and authority map

| Authority | Exact reviewed identity | Authority retained |
| --- | --- | --- |
| Parent database contract | 38,116-byte `docs/rfcs/OFARM_RuntimeBundle_Global_Content_Retention_Admission_RFC_v0_1.md`; `sha256:aa5de04c08390e1439d59f39c4b6f5608e8b43b320fec531721d9c53b936873a` | SQL law, RBGC-001–018, original nine paths, and stop conditions |
| Merged conformance contract | 40,726-byte `docs/rfcs/OFARM_RuntimeBundle_Global_Content_Retention_Conformance_Admission_RFC_v0_1.md`; `sha256:7df5ebcb89e2a758c7906e9c4053228e5e151d049ff40e07f83d23a706d7a016` | exact V8-absent/V9-classified repository admission |
| Production anchor | 12,016-byte `deployment/postgresql/catalog_identity.py`; `sha256:130a96edc2b9f4ad92a640c1c34150fe6126bd3945a48704a96896bb88a0f1a7` | sole external tenant verifier/observer trust anchor |
| Existing unit test | 7,060-byte `kernel/tests/test_postgresql_catalog_identity_unit.py`; `sha256:1ba7d07a838f41722dc29f21907534d7e07366d542c4cfc686143a6daa2c1675` | exact literal and fail-closed anchor verification |
| Merged prerequisite | PR #296, merge `95bf5919b6bd3894b4208ab7760e94b328c4173b` | conformance completion only |

The parent remains sole authority for function semantics, migration behavior,
publisher custody, transactions, inertness, negative cases, and all original
paths. This amendment owns only one added test path and its narrow edit shape.
The existing catalog identity algorithm over a clean disposable target owns
the future V9 digest; the user, AI, environment, and this RFC do not choose it.
The canonical test inventory remains mechanical node-ID evidence. Every other
database, runtime, temporal, legacy, output, and #192 authority is unchanged.

The reviewed repository is exact migration V8 with 0009 absent. The temporal
checker and package contract check pass. Authority drift stops the amendment;
there is no silent re-pin.

## 3. Trust model, state, and ordering

Protected assets are the closed Phase B path envelope, exact correspondence
between the production anchor and its test literal, all RBGC invariants, the
closed production semantic surface, and the production-versus-legacy
firewall.

Trusted components are the exact merged parent and conformance contracts, the
existing catalog identity algorithm and test, the supported collector and
package checker, and a later clean disposable PostgreSQL 17 target. Untrusted
inputs are copied, guessed, caller-, AI-, PR-, documentation-, or
environment-supplied digests and any claim that the existing exact test can be
ignored or weakened.

Repository-host, task-platform, database-owner, operating-system, PostgreSQL,
or hash compromise is outside this documentation boundary. The parent threat
model is unchanged.

```text
DATABASE_PHASE_B_REQUESTED_UNDER_NINE_PATH_ENVELOPE
  -> OMITTED_EXISTING_TEST_PATH_DISCOVERED
  -> STOP_WITHOUT_IMPLEMENTATION
  -> VERSIONED_AMENDMENT REVIEWED AND APPROVED
  -> DOCUMENTATION_ONLY_AMENDMENT MERGED
  -> RENEWED EXPLICIT DATABASE_PHASE_B REQUEST
  -> TEN_PATH DATABASE_PHASE_B MAY BEGIN
```

In future Phase B, the V9 target must be derived first. The production anchor
and exact test literal then change in the same PR. The test must never be
weakened before the value exists, and the two changes must never be split.

## 4. Invariants and negative cases

- **GCAA-001 — Parent law unchanged.** Parent bytes, RBGC-001–018, SQL law,
  non-goals, and stop conditions are not edited, relaxed, or reinterpreted.
- **GCAA-002 — One added path.** The only allowlist addition is the exact unit
  test path above.
- **GCAA-003 — Exact test purpose.** Only the tenant V8-to-V9 test name and
  expected literal may change; existing fail-closed tests remain intact.
- **GCAA-004 — Mechanical digest custody.** The V9 value comes only from the
  existing algorithm over a clean disposable V9 target.
- **GCAA-005 — Atomic verification.** Production anchor and test literal
  change in the same future implementation PR.
- **GCAA-006 — Mechanical inventory.** Inventory changes only for an actual
  canonical node-ID change.
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
| Digest is guessed, copied, or selected through an input | Refuse under GCAA-004 |
| Production anchor and test literal are split | Stop merge under GCAA-005 |
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
    in section 1.

No other path is permitted. All parent section 17 stop conditions remain
controlling.

This amendment does not implement or choose migration 0009, its function,
ACL, digest, structural identity, or catalog anchor. It does not alter the
content length bound, replay, transaction, role, login, membership,
provisioning, direct table grants, or publisher function. It retains no
content, publishes no bundle, chooses no tenant, creates no selection, and
adds no runtime, route, command, read, historical/WINDOW, materialization,
output, deployment, legacy, or #192 behavior. Unrelated parent wording
preferences remain outside this correction.

## 6. Smallest coherent change and provisional posture

One existing test path is the minimum coherent addition. Deleting its literal
assertion, hiding the value behind indirection, keeping a stale value, adding a
compatibility alias, or dynamically selecting V8/V9 would weaken rather than
verify the production trust anchor.

Sources of semantic truth added: zero. Verification paths added: one. Schemas,
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
| GCAA-003 | catalog-anchor unit test | weakened or unrelated edit | focused diff and unit test |
| GCAA-004, 005 | production anchor plus exact test | guessed or split value | disposable V9 observation and equality |
| GCAA-006 | canonical inventory generator | changed inventory without changed nodes | canonical comparison |
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
```

Passing evidence is not deployment, publication, selection, activation, or
current truth.

## 8. Open decisions, review disposition, and stop conditions

Open decisions: none. The V9 digest is mechanical; parent SQL semantics are
closed and are not reopened here.

- **Blocker addressed:** the mandatory production-anchor change had one
  existing exact-literal test outside the allowlist.
- **Follow-up:** after approval and merge, obtain one renewed explicit Phase B
  request naming this amendment and the ten-path envelope.
- **Preferences:** none.

Stop if an authority identity differs; reviewed `main` is not exact V8 with
0009 absent; another path is needed; parent semantics or RBGC invariants must
change; this RFC would pin the future digest; this PR changes another file; an
implementation effect enters Phase A; or exact-head review finds a
demonstrated unresolved blocker.

After merge, stop again until the architect sends a renewed explicit request
naming the parent contract, this amendment, the ten-path envelope, disposable
targets, and the no-retained-state rule.
