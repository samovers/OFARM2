# OFARM2 Tenant Current-Context Selection-Owner Admission — Phase A Contract v0.1

**Status:** architect-approved Phase A contract; documentation-only and without database, migration, grant, runtime, storage, output, deployment, legacy, or #192 effect

**Contract identity:** `ofarm.tenant-current-context-selection-owner-admission.issue176.v0.1`

**Intended RFC path:** `docs/rfcs/OFARM_Tenant_Current_Context_Selection_Owner_Admission_RFC_v0_1.md`

**Reviewed base:** `c3adb8e47a01690920c539de9c54fb18c581cdaa`

**Primary ticket:** #176

**Primary trust boundary:** admission of the existing unreachable tenant database owner to two existing binder-owned, transaction-bound current-context readers

**Intended PR boundary:** one documentation-only child approval record first; one later, separately authorized Phase B implementation PR for this admission only

## 1. Problem and goal

A later, separately governed tenant selection-storage function must execute as the existing database owner while reading the already verified tenant and authenticated-principal context. The two required readers are owned by `ofarm_binder` and are not executable by `ofarm_owner`.

This contract governs the smallest admission that gives `ofarm_owner` exactly `EXECUTE` on:

- `ofarm.current_tenant_id()`; and
- `ofarm.current_authenticated_principal_ref()`.

The admission does not choose a tenant, establish a `TenantBinding`, grant a production login the ability to assume `ofarm_owner`, create selection storage, or authorize the future owner-owned `SECURITY DEFINER` activation function.

The governing prerequisites are:

| Authority | Exact reviewed identity |
|---|---|
| Architecture context | `reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md`, 96,406 bytes, `sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256` |
| Migration and role architecture | ADR 0001, 147,112 bytes, `sha256:bc49e566ddbdf98868162aa7ccca0940fa76fca1bfaaa261c8c831dbb5515a4d` |
| Temporal separation | ADR 0002, 61,427 bytes, `sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796` |
| Binder and current-context semantics | ADR 0003, 93,419 bytes, `sha256:b188f4d60e46887fde4231e73bb00adb9bd70b75e807627e8a3906389a0fa5be` |
| Approved parent contract | `ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1`, 52,382 bytes, `sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb` |
| Merged V5 child contract | `ofarm.tenant-binding-selection-control-admission.issue176.v0.1`, 32,169 bytes, `sha256:c1d02969811be0d5b02bdae158cb48e5d8148356ca9d4bac956c8861d529c37a` |
| V5 implementation | head `79b2769e80fa530e19b642f0f7b3972fb331b338`, merge `c3adb8e47a01690920c539de9c54fb18c581cdaa` |
| Exact V5 migration set | five migrations, `sha256:ef2e85c150d7c445ae33d4c1cc63a06bbcf17c79f1e7bdaf070ae4819ed38288` |
| Migration 0005 source | 8,545 bytes, `sha256:fde66e835f8c4456d7404eb00b99292e267f573f8b126f781f3ed55bd5e8df9a` |
| Current tenant provisioning spec | `ofarm.tenant-postgresql-provisioning.v1`, `sha256:e15a5d5903681e2796c70ca2cac19b1aa85d3538589f99046a01c3663f5d8556` |
| Current external catalog verifier | `sha256:9d75e28bd8083348becd0e95a6873b5dece22c01a6f5fef2bdcae09fb609acf8` |

The mandatory governance order is:

```text
APPROVED_PARENT_AND_MERGED_V5_IDENTITY_AVAILABLE
  -> EXACT_V6_CHILD_DESIGN_REVIEWED
  -> EXPLICIT_V6_CHILD_APPROVAL
  -> V6_CHILD_APPROVAL_RECORD_PUBLISHED_AND_MERGED
  -> COMPLETE_MERGED_V6_CHILD_IDENTITY_AUTHENTICATED
  -> EXPLICIT_PHASE_B_REQUEST
  -> V6_PHASE_B_PERMITTED
```

Explicit approval of this design authorizes only its documentation-only approval record. It does not authorize Phase B.

## 2. Learning value

This boundary demonstrates that OFARM2 can let a future owner-executed storage function consume an already verified transaction-bound identity without exposing the readers to a new login, making tenant identity derive from a database role, or introducing a reusable privileged-grant mechanism.

It also validates ordered coexistence and one-use consumption of independently governed V5 and V6 capsules, including rollback and post-commit acknowledgement loss, while leaving no durable privileged capsule.

## 3. Non-goals

This contract does not authorize:

- implementation during Phase A;
- amendment of ADR 0001, ADR 0002, ADR 0003, the parent contract, or the merged V5 contract;
- changes to either current-context reader's signature, body, owner, configuration, failure behavior, or existing ACLs;
- capability minting, signing, acquisition, transport, caching, or key custody;
- challenge, capability, principal-resolution, or binder changes;
- any new permanent login, role, membership, role-assumption edge, schema or relation privilege, object ownership, or database `CONNECT` grant; the only transient schema and ownership changes authorized are the V6 capsule’s temporary `CREATE` grant and self-transfer expressly defined in section 6.7;
- tenant-lock admission or migration `0007`;
- tenant knowledge-position or RuntimeBundle selection storage;
- migration `0008` or its owner-owned activation function;
- RuntimeBundle selection, activation, profiles, or `RuntimeBundle` changes;
- `COMMIT_OPERATION_CLAIM_DRAFT` integration;
- routes, APIs, materialization, qualification, promotion, publication, reads, outputs, or receipts;
- valid-time carrier selection, knowledge-time execution, historical views, current-state outputs, or windowed outputs;
- an existing-target upgrade, repair, reconciliation, or backfill path;
- production deployment activation, existing-target upgrade, repair, or reconciliation behavior;
- legacy integration; or
- #192 behavior.

## 4. Trust model

### Protected assets

Protected assets are tenant identity, authenticated-principal identity, `TenantBinding` custody, current-context function definitions and ACLs, database ownership, role membership and role-assumption edges, provisioning and migration source identity, migration history and execution evidence, the structural catalog trust anchor, tenant relations, current context, credentials, capabilities, signing keys, and commit-outcome classification.

### Trusted components

Trusted components are PostgreSQL 17; the exact accepted ADRs and prerequisite contracts; the unchanged ADR-0003 binder and current-context functions; the independently governed signer; exact reviewed provisioning and migration sources; the migration loader and runner; the external catalog verifier; trusted Python, psycopg, and cryptographic implementations; and the external provisioning-superuser authority while it creates the closed V6 capsule.

Execution must use already authenticated immutable migration bytes. It must not reopen migration files after authentication.

### Untrusted actors and inputs

Every managed non-superuser role, every production login, an attacker holding any managed login credential, caller-supplied tenant or principal values, release identity, execution UUID, connection and retry timing, migration target state, and attempted caller-supplied schema, role, routine, privilege, digest, or grant target are untrusted.

The future selection-control login may establish a `TenantBinding` only through the unchanged signed-capability protocol. It is not trusted to choose the context returned by either reader.

### In-scope failures and misuse

In scope are managed-role misuse; attempted role assumption; invalid, absent, replayed, wrong-backend, wrong-incarnation, or wrong-transaction binding state; reviewed source substitution; detectable filesystem mutation; filesystem mutation after authenticated migration bytes are loaded; capsule source substitution; ordinary interruption and rollback; backend loss before commit; successful commit with lost acknowledgement; retries; misuse against an existing target; and every mixed V5/V6 ledger, capsule, ACL, role, and verifier state.

### Explicitly excluded compromise capabilities

Out of scope are a compromised PostgreSQL implementation; arbitrary mutation of the trusted Python process after source authentication; compromised Python, psycopg, operating-system, or cryptographic dependencies; operating-system compromise; deliberate malicious action by the external provisioning superuser; coherent replacement of implementation and its independent integrity authority; signer-key theft; and deliberate compromise of the architect, migration operator, or deployment authority.

Operator mistakes that produce detectable source, role, ACL, history, capsule, or catalog disagreement remain in scope and must fail closed. The compromise exclusions never permit inconsistent durable state to be accepted.

## 5. Authority map

| Decision | Sole authority |
|---|---|
| Migration, role, and provisioning architecture | Exact ADR-0001 identity in section 1 |
| Temporal meaning and separation | Exact ADR-0002 identity in section 1 |
| Binder, TenantBinding, and current-context semantics | Exact ADR-0003 identity and unchanged target functions |
| Governing command sequence | Complete approved-parent identity in section 1 |
| V5 role and admission prerequisite | Complete merged V5 child identity and V5 implementation merge in section 1 |
| V6 child design approval | Exact architect-authored approval in the designated Codex task |
| Durable V6 child approval evidence | Complete merged V6 RFC approval appendix |
| Tenant and Party identity | Existing binder verification of the independently signed capability |
| Target function definitions | Exact pre-V6 function identity table in section 6 |
| Permanent provisioning state and transient capsule | Exact reviewed `ProvisioningSpec` |
| Exact V6 grant targets | Closed two-row ACL set in section 6 |
| Final ACL grantor | `ofarm_binder` |
| Migration order and ledger append | Migration runner |
| Complete ledger-row authentication | Migration runner |
| Capsule ordering marker | Closed static capsule query |
| Final service structure | Migration-0006 structural verifier |
| Verifier authenticity | External catalog-verifier digest |
| Future owner-executed selection function | Separate migration-0008 contract and implementation |
| Tenant-lock consumer | Separate migration-0007 contract and implementation |
| Selection storage | Separate conformance and migration-0008 boundaries |
| Runtime, command, and output behavior | Their later reviewed contracts only |

There is no legacy fallback, alias, caller-provided tenant field, database-credential-derived tenant identity, duplicate current-context state, alternate grant path, or generic privilege registry.

## 6. State machine and ordering

### 6.1 Byte-authenticated approval publication

The canonical child-design bytes are UTF-8, use LF line endings, begin with this document's first `#`, end after the merge-stop rule, and contain exactly one terminal LF. The live decision card must state their exact byte length and SHA-256 before approval is solicited.

The designated architect must then send the exact approval sentence from that complete live card as a later user-authored message in Codex task `019fa821-93c9-7ef1-8c94-1c0e92ea46b9`. Typing it or copying it directly from that live card is valid. Text or a card digest copied from another task, another card, another decision, documentation, a template, a PR, GitHub, or AI-authored or AI-sent text other than the complete live decision card displayed earlier in the same task is invalid. AI-generated messages, repository credentials, PR authorship, review, comment, reaction, merge, or a generic approval never count.

Only after the exact user-authored message exists may one documentation-only PR publish this RFC. The publication must preserve the approved decision, trust model, authority map, states, invariants, negative cases, architecture, non-goals, traceability, file boundary, and merge-stop rule byte-for-byte.

Only these differences from the approved design bytes are permitted:

1. status metadata may change from proposed and unapproved to architect-approved; and
2. one approval appendix may be added.

The appendix must record:

- contract identity and intended path;
- reviewed base;
- exact approved design byte length and SHA-256;
- parent and merged V5 prerequisite identities;
- Codex task identifier;
- architect user-message identifier or stable reference and timestamp;
- exact user-authored approval sentence and its canonical byte length and digest;
- live decision-card canonical byte length and digest;
- permitted effects and non-effects;
- preservation rules; and
- next required sequence.

After that PR merges, Phase B must authenticate and pin the complete merged RFC byte length and SHA-256. The pre-publication design digest cannot substitute for the complete merged-child identity. A separate explicit Phase B request remains required.

### 6.2 Exact pre-V6 function state

The pre-V6 definitions are closed:

| Property | `ofarm.current_tenant_id()` | `ofarm.current_authenticated_principal_ref()` |
|---|---|---|
| Return | `pg_catalog.uuid` | `ofarm.tenant_local_ref` |
| Owner | `ofarm_binder` | `ofarm_binder` |
| Language | `plpgsql` | `plpgsql` |
| Security | `SECURITY DEFINER` | `SECURITY DEFINER` |
| Volatility | `STABLE` | `STABLE` |
| Strict | false | false |
| Leakproof | false | false |
| Parallel | `UNSAFE` | `UNSAFE` |
| Configuration | `search_path=pg_catalog, pg_temp` | `search_path=pg_catalog, pg_temp` |
| `prosrc` SHA-256 | `2dea636af9e5cd14b7fcb406fd556934ffd8ab408dae965aa318e4120beb0ab0` | `6b0b3abc610609988a965cb7b8671603b0c8bdd8fde62d5aafdc465507182df7` |
| Existing direct execute grantees | `ofarm_app`, `ofarm_worker`, `ofarm_graph_validator`, `ofarm_tenant_lock_owner` | `ofarm_app`, `ofarm_worker` |
| Public execute | absent | absent |
| `ofarm_owner` execute | absent | absent |

Every existing direct ACL row records `ofarm_binder` as grantor and has no grant option. Phase B may add the two owner rows but may not remove, reinterpret, or expand the existing rows.

Both functions derive context only from the exact current backend PID, backend incarnation, current full transaction ID, and `BOUND` row in `ofarm.tenant_binding_context`. Missing or multiple matching rows raise SQLSTATE `42501` with `verified tenant context is absent`.

### 6.3 Exact admission

The only admitted ACL additions are:

| Object | Grantee | Privilege | Grantor | Grant option |
|---|---|---|---|---|
| `ofarm.current_tenant_id()` | `ofarm_owner` | `EXECUTE` | `ofarm_binder` | false |
| `ofarm.current_authenticated_principal_ref()` | `ofarm_owner` | `EXECUTE` | `ofarm_binder` | false |

They are one atomic admission. No direct current-context grant is added to a login, controller, migrator, future storage role, or any other role.

`ofarm_owner` remains an existing `NOLOGIN` database and object owner. This contract adds no new relation privilege, ownership, membership, inheritance, or role-assumption edge.

No production runtime login may inherit `ofarm_owner`. No production runtime login may `SET ROLE ofarm_owner`. No membership path may make `ofarm_owner` assumable by a role that can establish TenantBinding. The existing release-time `ofarm_migrator` `SET ROLE` edge remains the sole role-assumption path; `ofarm_migrator` receives no challenge or binding-function privilege.

A later, separately approved function owned by `ofarm_owner` may be `SECURITY DEFINER` and executable by a tenant-bound selection-control login. Invoking that function would execute its body with `CURRENT_USER = ofarm_owner` without conferring membership, inheritance, `SET ROLE`, object ownership, or general owner authority. That future function and its grant are not authorized here.

### 6.4 Closed V6 capsule

Fresh provisioning adds exactly one new capsule, alongside the independently governed V5 capsule:

`ofarm_infrastructure.seal_tenant_current_context_selection_owner_admission()`

It is no-argument, returns `pg_catalog.void`, uses `LANGUAGE plpgsql`, is `VOLATILE`, `PARALLEL UNSAFE`, initially `SECURITY DEFINER`, initially owned by the external provisioning-superuser category, executable only by `ofarm_migrator`, inaccessible to `PUBLIC` and every other managed role, fully static, free of dynamic SQL, and configured with the existing constrained sealer search path.

It may name only the exact migration ledger, version `6`, filename `0006_tenant_current_context_selection_owner_admission.sql`, service identity `ofarm.tenant-postgresql.v1`, the two exact target functions, `ofarm_owner`, itself, `ofarm_infrastructure`, and `ofarm_migrator`.

Its only ledger check is:

```text
ledger row count = 6
head version = 6
head filename = 0006_tenant_current_context_selection_owner_admission.sql
head service identity = ofarm.tenant-postgresql.v1
```

It must not embed or accept its provisioning-spec digest, migration-0006 source digest or length, applied-prefix digest, release identity, execution UUID, GUC, temporary-table value, function argument, role name, routine name, privilege, or other dynamic authority input.

### 6.5 Complete V6 ledger authentication

Immediately after appending its own row and before invoking the V6 capsule, the runner authenticates all nine fields:

1. version;
2. filename;
3. source SHA-256;
4. source byte length;
5. applied-prefix digest;
6. service identity;
7. provisioning-spec digest;
8. current release identity; and
9. current execution UUID.

The capsule proves ordering only. It does not duplicate complete row authentication.

### 6.6 Capsule coexistence and durable phase matrix

```text
P0 — NO LEDGER OR DURABLE HEAD 1–4
  V5 capsule: exact and present
  V6 capsule: exact and present
  V5 binder grants: absent
  V6 owner grants: absent

P1 — DURABLE HEAD 5
  V5 capsule: absent
  V5 binder grants: exact
  V6 capsule: exact and present
  V6 owner grants: absent

P2 — UNCOMMITTED V6 TRANSITION
  exact V5 durable starting state
  migration 0006 verifier change executed
  exact V6 row appended and all nine fields authenticated
  V6 owner grants: both exact
  V6 capsule: self-demoted, transferred, verified, then removed
  final V6 structure: authenticated before commit

P3 — DURABLE HEAD 6
  V5 capsule: absent
  V6 capsule: absent
  V5 binder grants: exact
  V6 owner grants: exact
  exact V6 history and final verifier: valid
```

Every other combination refuses.

Fresh-target provisioning must accept both exact capsules when the ledger is absent and through durable heads 1–4. Migration 0005 consumes only the V5 capsule. Exact durable V5 retains only the V6 capsule. Migration 0006 consumes only the V6 capsule. Exact durable V6 retains neither.

Provisioning observation, unmigrated-object classification, migration-lock capsule verification, final structural verification, and focused tests must all use this same phase matrix. There is no second phase source.

### 6.7 V6 transaction order

```text
P1_EXACT_DURABLE_V5
  -> authenticate complete merged V6 child identity
  -> authenticate exact provisioning, migration-set, source, and catalog identities
  -> acquire the existing migration lock
  -> re-authenticate exact P1 state
  -> execute authenticated immutable migration-0006 bytes
  -> append the V6 row
  -> authenticate all nine V6 row fields
  -> invoke only the V6 capsule
  -> grant both owner ACL rows
  -> grant temporary CREATE on ofarm_infrastructure to ofarm_migrator
  -> change V6 capsule to SECURITY INVOKER
  -> transfer V6 capsule to ofarm_migrator
  -> revoke temporary CREATE
  -> verify exact ACLs and demoted capsule
  -> drop only the V6 capsule
  -> restore the fixed migration role
  -> re-authenticate the V6 row
  -> run final structural verification
  -> COMMIT
```

Migration 0006 itself changes only the final structural verifier. It must not perform the grants, change either target function, create a role, or create the capsule.

All V6 transition effects occur in one PostgreSQL transaction. No durable intermediate state is lawful.

### 6.8 Commit outcome and retry

```text
PRE_COMMIT_FAILURE_OR_BACKEND_LOSS
  -> PostgreSQL rolls back the entire V6 transaction
  -> exact P1 durable V5
  -> V6 capsule present
  -> both owner grants absent
  -> retry migration 0006 from P1

COMMIT_CONFIRMED
  -> exact P3 durable V6
  -> V6 capsule absent
  -> both owner grants exact
  -> final verifier valid
  -> report committed

POST_COMMIT_ACKNOWLEDGEMENT_LOSS
  -> COMMIT reached PostgreSQL
  -> PostgreSQL durably committed V6
  -> successful response did not reach the client
  -> report MigrationOutcomeUnknown
  -> reconnect and authenticate exact durable state
```

After reconnection:

```text
exact P1 durable V5
  -> retry migration 0006

exact P3 durable V6
  -> return a verified no-op outcome
  -> preserve the uncertain execution UUID as the observed V6 head execution identity
  -> append no second V6 row
  -> recreate no capsule
  -> consume no capsule

anything else
  -> refuse automatic recovery
```

A disconnect after the client already received successful commit acknowledgement is not an uncertain outcome and is not the required failure case.

## 7. Invariants and acceptance criteria

- **TCCO-001:** Phase B requires the exact accepted prerequisite identities, explicit architect approval of the exact V6 child-design bytes, merge of its truthful approval record, authentication of the complete merged-child identity, and a separate explicit Phase B request.
- **TCCO-002:** ADR 0001 alone owns migration and role architecture, ADR 0003 alone owns binder and current-context semantics, and this contract does not amend either.
- **TCCO-003:** The only new permanent privileges are the two exact `ofarm_owner` `EXECUTE` rows in section 6.3.
- **TCCO-004:** Both owner grants exist atomically or neither exists.
- **TCCO-005:** Each owner ACL row records `ofarm_binder` as grantor and has no grant option.
- **TCCO-006:** `ofarm_owner` remains `NOLOGIN`, and this boundary adds no role, membership, inheritance, `SET ROLE`, ownership, schema, relation, or `CONNECT` authority.
- **TCCO-007:** No production runtime login may inherit or `SET ROLE ofarm_owner`; the existing migrator edge remains the sole role-assumption path.
- **TCCO-008:** A future owner-owned `SECURITY DEFINER` call is not role assumption and is neither prohibited nor authorized by this contract.
- **TCCO-009:** Both target signatures, returns, bodies, `prosrc` digests, owners, languages, security modes, volatility, strictness, leakproof settings, parallel settings, configurations, existing ACL rows, and failure semantics remain exact.
- **TCCO-010:** Without one exact backend-, incarnation-, and transaction-bound `BOUND` context row, each target reader fails with SQLSTATE `42501`; owner execution cannot manufacture tenant or principal identity.
- **TCCO-011:** No login, controller, migrator, future storage role, or other role receives a direct current-context grant through this boundary.
- **TCCO-012:** The V6 capsule is one exact static no-argument function with no caller-selected or dynamic authority input.
- **TCCO-013:** The runner authenticates all nine V6 ledger fields before V6 capsule invocation.
- **TCCO-014:** The V6 capsule checks only the closed non-circular V6 ordering marker.
- **TCCO-015:** The P0–P3 phase matrix is the sole authority for V5/V6 capsule and grant coexistence.
- **TCCO-016:** Migration 0005 consumes only the V5 capsule; migration 0006 consumes only the V6 capsule.
- **TCCO-017:** Migration 0006 changes only the final structural verifier; grant custody remains in the provisioning-superuser-created capsule.
- **TCCO-018:** V6 row append, complete authentication, both grants, capsule self-demotion and removal, and final verification occur in one transaction.
- **TCCO-019:** Pre-commit failure or backend loss restores exact P1 and permits a clean V6 retry.
- **TCCO-020:** Confirmed commit produces only exact P3 and reports committed only after final verification.
- **TCCO-021:** Post-commit acknowledgement loss reports `MigrationOutcomeUnknown`, reconnects, and classifies exact P1 or P3 only.
- **TCCO-022:** Exact P3 recovery returns a verified no-op, preserves the uncertain execution UUID, appends no second V6 row, and performs no capsule action.
- **TCCO-023:** Every mixed history, capsule, grant, role, source, or verifier state fails closed.
- **TCCO-024:** Detectable source, filesystem, digest, provisioning, migration-set, prerequisite, or catalog disagreement fails before durable admission.
- **TCCO-025:** The boundary is fresh-target-only; an existing target lacking the exact P0 or P1 provisioning state is not reconciled.
- **TCCO-026:** Credentials, capabilities, tenant identifiers, principal identifiers, and signing material are absent from repository and migration evidence.
- **TCCO-027:** No generic privileged-grant hook, registry, callback, reusable capsule framework, or alternate transition source is introduced.
- **TCCO-028:** This admission creates no storage, tenant-lock, migration-0008, runtime, command, route, materialization, read, output, legacy, deployment, or #192 effect.

## 8. Negative cases

| Invariant | Supported entry and concrete counterexample | Required result |
|---|---|---|
| TCCO-001 | Phase B runner starts with a missing approval appendix, wrong merged-child digest, or no separate Phase B request | Refuse before target mutation |
| TCCO-002 | Authenticated migration source changes a reader body or binder ownership | Source and structural verification refuse |
| TCCO-003 | V6 capsule or migration attempts a third privilege or grantee | ACL verification refuses and transaction rolls back |
| TCCO-004 | Disposable P1 target is mutated to contain only one owner grant | Phase observation and recovery refuse |
| TCCO-005 | Owner ACL records a different grantor or grant option | Final verifier refuses |
| TCCO-006 | Provisioning adds a role edge, schema grant, relation grant, ownership transfer, or `CONNECT` grant | Provisioning verification refuses |
| TCCO-007 | App, worker, or selection-control login attempts `SET ROLE ofarm_owner` | PostgreSQL denies role assumption |
| TCCO-008 | Migration 0006 adds an owner-owned activation function or executable grant | Source allowlist and review refuse as migration-0008 scope |
| TCCO-009 | Target reader has changed `prosrc`, owner, security mode, configuration, or existing ACL | Pre-transition structural verification refuses |
| TCCO-010 | Migrator uses its existing release-time edge, sets `ofarm_owner`, and calls either reader without a verified binding | SQLSTATE `42501`; no tenant or principal returned |
| TCCO-011 | Selection-control login receives direct execute on either reader | ACL verification refuses |
| TCCO-012 | Provisioned V6 capsule accepts an argument, role, routine, GUC, temporary-table value, or dynamic SQL | Provisioning verification refuses |
| TCCO-013 | V6 ledger row substitutes the release identity or execution UUID | Capsule is never invoked |
| TCCO-014 | V6 capsule is invoked before an exact V6 row exists | Capsule refuses with no grant |
| TCCO-015 | Fresh target at head 1–4 lacks either capsule, or durable V5 lacks the V6 capsule | Phase observer refuses |
| TCCO-016 | Migration 0005 removes V6 capsule, or migration 0006 targets V5 capsule | Capsule-specific verification refuses and transaction rolls back |
| TCCO-017 | Migration 0006 directly executes `GRANT` or changes a target routine | Source identity and focused structural test refuse |
| TCCO-018 | Failure occurs after either owner grant and before commit | Entire V6 transaction rolls back to exact P1 |
| TCCO-019 | Backend is terminated before `COMMIT` reaches PostgreSQL | Reconnect observes exact P1 and retry succeeds |
| TCCO-020 | Client receives successful commit acknowledgement but final V6 structure differs | Commit path cannot report success; verifier failure rolls back before commit |
| TCCO-021 | TCP proxy forwards `COMMIT` and drops the successful server response | Runner reports outcome unknown and reconnects |
| TCCO-022 | Retry after acknowledgement loss observes exact P3 | Verified no-op; one V6 row; original uncertain execution UUID; no capsule action |
| TCCO-023 | Reconnect sees V5 with a grant, V5 without V6 capsule, V6 with capsule, V6 with one grant, or V6 with wrong grantor | Refuse automatic recovery |
| TCCO-024 | Loaded migration bytes or current provisioning/catalog digest differs from the reviewed literal | Refuse before target mutation |
| TCCO-025 | Runner targets an existing V5 database created without the V6 capsule | Refuse; no repair or reconciliation |
| TCCO-026 | Real capability, tenant ID, principal ID, credential, or key appears in a fixture or report | Reject evidence and fail privacy review |
| TCCO-027 | Implementation introduces a generic grant list or shared capsule dispatcher | Review blocker and package check failure |
| TCCO-028 | V6 change adds storage, lock, activation, route, output, legacy, or #192 behavior | File-boundary and conformance review refuse |

All database counterexamples start through fresh provisioning, the production migration runner, managed-role connections, or real reconnection. Tests may use supported SQL mutations on disposable databases to create durable mixed states. They must not use monkeypatching or private-field mutation as production evidence.

## 9. Proposed architecture and smallest coherent change

The minimum coherent Phase B consists of:

1. one V6 `TenantCurrentContextSelectionOwnerAdmissionSealerSpec` value in the existing immutable provisioning specification;
2. phase-aware observation of the exact V5 and V6 capsules using the single P0–P3 matrix;
3. one explicit migration-runner V6 transition that authenticates the complete V6 row and consumes only the V6 capsule;
4. one verifier-only migration `0006_tenant_current_context_selection_owner_admission.sql` that updates the final structural contract;
5. one updated authoritative migration-set identity and external catalog-verifier identity; and
6. focused provisioning, runner, live migration, structural, catalog, and inventory verification.

The capsule is necessary because the target functions are binder-owned while migration SQL runs as `ofarm_owner`. PostgreSQL records `ofarm_binder` as grantor when the external provisioning-superuser issues the grant over the binder-owned functions, preserving exact ACL attribution without a new binder-membership or role-assumption edge.

The migration remains verifier-only so its authenticated SQL cannot silently become an alternate grant authority. The runner owns sequencing and complete ledger authentication. The capsule owns only two grants, its non-circular ordering marker, and self-removal. Provisioning owns its exact source and pre-migration custody. The external verifier owns final structural identity.

This reuses the already accepted V5 sealer, immutable migration-byte, migration-lock, outcome-unknown, and structural-verification composition points. A generic V6 framework is larger, less auditable, and creates speculative authority. Editing either reader or granting a login directly collapses the intended boundary.

## 10. Elegance audit

| Measure | Count |
|---|---:|
| Tenant/principal authority sources | 1 unchanged binder |
| New roles or logins | 0 |
| New memberships or role-assumption edges | 0 |
| New permanent ACL rows | 2 |
| Changed target function bodies or owners | 0 |
| New permanent functions | 0 |
| New relations | 0 |
| New transient capsules | 1 |
| Capsules coexisting before V5 | 2 exact independently governed capsules |
| Capsules remaining at durable V6 | 0 |
| Authoritative V5/V6 phase matrices | 1 |
| Authoritative V6 transition points | 1 runner branch |
| Generic grant mechanisms | 0 |
| Runtime, legacy, or #192 integrations | 0 |

The only duplicated values are deliberate integrity literals: exact migration and catalog identities independently checked by their owning components. No compatibility shim, optional capability bag, mutable registry, identity-comparison security boundary, or self-attestation is added.

The V6 capsule deletes itself transactionally. Nothing else can be deleted because the existing V5 capsule and transition remain required for fresh targets before durable V5. A clean rewrite is not justified: the merged V5 implementation already supplies the correct narrow composition points, and V6 is one explicit sibling transition rather than a generalized abstraction.

## 11. Pull request boundary

### Documentation-only child approval-record PR

After exact approval, one documentation-only PR may add only:

`docs/rfcs/OFARM_Tenant_Current_Context_Selection_Owner_Admission_RFC_v0_1.md`

It must preserve the approved design except for the two publication differences allowed by section 6.1. It may not implement anything.

### Later Phase B implementation PR

The primary trust boundary is the two-row current-context selection-owner admission. The closed expected file allowlist is:

- `kernel/migrations/0006_tenant_current_context_selection_owner_admission.sql`
- `deployment/postgresql/provisioning_specs.py`
- `deployment/postgresql/provisioning.py`
- `deployment/postgresql/migration_runner.py`
- `deployment/postgresql/migration_sets.py`
- `deployment/postgresql/catalog_identity.py`
- `deployment/postgresql/README.md`
- `kernel/tests/test_migration_sets.py`
- `kernel/tests/test_postgresql_provisioning.py`
- `kernel/tests/test_postgresql_migration_runner.py`
- `kernel/tests/test_postgresql_tenant_migration.py`
- `kernel/tests/test_postgresql_readiness_unit.py`
- `kernel/tests/test_postgresql_structural_compatibility.py`
- `kernel/tests/test_postgresql_catalog_identity_unit.py`
- `conformance/review_baseline_test_inventory.json` only when mechanically required by a change to the canonical collected test-node inventory, including a count or node-ID change

No other file may change. If implementation requires another authority or file, work stops for a versioned contract amendment or separate trust-boundary PR.

The Phase B PR depends on the complete merged V6 child RFC, the merged V5 implementation, and the exact authority pins in section 1. Later work may assume only that the exact two owner ACLs and exact durable V6 structural evidence exist.

Reviewers must not require migration 0007, selection-storage conformance, migration 0008, owner-function execution, a RuntimeBundle change, command integration, routes, reads, outputs, legacy behavior, deployment upgrade behavior, or #192 work from this PR.

Follow-ups remain separately bounded and ordered:

1. tenant-lock selection-owner admission and migration 0007;
2. tenant selection-storage conformance;
3. database selection implementation and migration 0008;
4. one governed production command; and
5. current-state reads and outputs only after their output-governance prerequisites are satisfied.

## 12. Provisional design record

The capsule is transient rather than provisional architecture. Successful V6 consumption deletes it because the two exact durable ACL rows replace it.

The fresh-target-only rule is provisional before deployment. It is acceptable because OFARM2 has no deployed V5 target requiring upgrade or repair, and a single fresh-provisioning specification can establish both exact capsules before migrations run.

Redesign is required if:

- a deployed or independently created target must advance from V5;
- recovery needs human mixed-state repair;
- PostgreSQL no longer records `ofarm_binder` as the required grantor;
- either capsule cannot remain static, closed, and independently identified;
- the P0–P3 phase matrix cannot remain the sole phase authority;
- production roles gain an owner role-assumption path;
- source authentication can no longer prevent detectable substitution; or
- operational evidence defeats fresh provisioning or commit recovery.

Before deployment, existing-target evolution must either remain unnecessary or receive a separate reviewed infrastructure-upgrade and human-controlled operational-approval contract. No compatibility path is reserved here.

## 13. Traceability and verification

| Invariant | Owning code or authority | Production-reachable negative test | Acceptance evidence and smallest verification |
|---|---|---|---|
| TCCO-001 | merged RFC pin and runner gate | wrong/missing merged identity | governance review and runner refusal |
| TCCO-002 | exact ADR pins and unchanged functions | authenticated source changes binder law | migration-set and structural refusal |
| TCCO-003 | V6 capsule and final verifier | third ACL row | exact `aclexplode` result |
| TCCO-004 | V6 capsule transaction | one owner grant only | mixed-state live test refuses |
| TCCO-005 | capsule and final verifier | wrong grantor or grant option | exact `aclexplode` grantor/grantable rows |
| TCCO-006 | provisioning spec | new role, membership, schema, relation, ownership, or `CONNECT` authority | exact role and ACL catalogs |
| TCCO-007 | existing role graph | runtime login attempts owner assumption | real `SET ROLE` denial and exact `pg_auth_members` |
| TCCO-008 | migration allowlist | V6 source adds owner-owned activation | source review and migration-set refusal |
| TCCO-009 | pre-V6 structural identity and V6 verifier | reader body/owner/config/ACL substitution | exact `pg_proc`, `prosrc` digest, and ACL comparison |
| TCCO-010 | unchanged readers | migrator sets owner and calls unbound reader | live SQLSTATE `42501` test |
| TCCO-011 | final ACL verifier | direct login/controller/migrator grant | exact ACL inventory refuses |
| TCCO-012 | V6 sealer spec and provisioning verifier | argument, GUC, temp table, or dynamic source | exact source-manifest test |
| TCCO-013 | V6 runner | any of nine row fields differs | nine substitution cases stop before capsule |
| TCCO-014 | V6 capsule | invoke before exact V6 row | live capsule refusal |
| TCCO-015 | provisioning observer and runner | invalid P0, P1, or P3 capsule combination | complete phase-matrix live tests |
| TCCO-016 | explicit V5 and V6 runner transitions | either transition targets the other's capsule | capsule-specific refusal and rollback |
| TCCO-017 | migration 0006 and source identity | SQL contains grant or target alteration | migration-set and focused source test |
| TCCO-018 | runner transaction | failure after first or second grant | exact P1 rollback evidence |
| TCCO-019 | runner and real backend loss | terminate backend before commit reaches PostgreSQL | exact P1 then successful retry |
| TCCO-020 | runner final verifier | final state differs before confirmed commit | no success report and exact rollback |
| TCCO-021 | outcome-unknown reconciliation | proxy forwards commit and drops success response | `MigrationOutcomeUnknown` then reconnect |
| TCCO-022 | no-op reconciliation | retry observes exact P3 | one V6 row, preserved execution UUID, no capsule action |
| TCCO-023 | phase-aware verifier | every enumerated mixed V5/V6 state | automatic recovery refuses |
| TCCO-024 | immutable loader, literals, and external verifier | source/filesystem/digest substitution | refusal before target mutation |
| TCCO-025 | provisioning verifier and runner | existing V5 target lacks V6 capsule | refuse without reconciliation |
| TCCO-026 | fixtures and reports | real protected value appears | privacy scan and evidence rejection |
| TCCO-027 | provisioning and runner architecture | generic grant registry or dispatcher appears | code review and package check |
| TCCO-028 | closed file and behavior boundary | route, storage, lock, output, legacy, or #192 effect appears | diff review and conformance refusal |

Focused Phase B verification is:

```text
python3 -m pytest kernel/tests/test_migration_sets.py -q
python3 -m pytest kernel/tests/test_postgresql_provisioning.py -q
python3 -m pytest kernel/tests/test_postgresql_migration_runner.py -q
python3 -m pytest kernel/tests/test_postgresql_tenant_migration.py -q
python3 -m pytest kernel/tests/test_postgresql_readiness_unit.py -q
python3 -m pytest kernel/tests/test_postgresql_structural_compatibility.py -q
python3 -m pytest kernel/tests/test_postgresql_catalog_identity_unit.py -q
python3 conformance/ofarm_pkg_contract_check.py
```

The live database suite must prove:

- fresh provisioning through migrations 1–4 with both capsules present;
- migration 0005 consumes only the V5 capsule;
- exact durable V5 retains only the V6 capsule;
- migration 0006 consumes only the V6 capsule;
- exact durable V6 retains neither capsule;
- both exact owner ACL rows and unchanged target functions;
- denial of runtime owner role assumption;
- unbound owner calls fail with `42501`;
- all nine V6 ledger substitutions refuse before capsule use;
- pre-commit backend termination returns exact P1 and retries;
- commit acknowledgement loss returns exact P3 and a verified no-op retry; and
- every enumerated mixed state refuses.

The complete canonical collected test inventory must pass. Its inventory file changes only when mechanically required by a count or node-ID change.

## 14. Open decisions and review disposition

The technical decisions are closed by this proposal:

- exact two-row admission;
- `ofarm_binder` grantor and no grant option;
- role-assumption reachability distinguished from later owner-owned `SECURITY DEFINER` execution;
- unchanged current-context semantics;
- two independently governed capsules coexist through durable head 4;
- the V5 capsule alone is consumed at V5;
- the V6 capsule alone is consumed at V6;
- one P0–P3 phase matrix governs all observers;
- migration 0006 is verifier-only;
- the runner authenticates all nine ledger fields;
- the capsule checks ordering only;
- pre-commit loss retries from exact P1;
- lost post-commit acknowledgement reconciles exact P3 as a no-op while preserving the uncertain execution UUID; and
- the Phase B file allowlist is closed.

Current disposition:

```text
PARENT APPROVAL: SATISFIED
MERGED V5 PREREQUISITE: SATISFIED
V6 CHILD DESIGN REVIEW: PENDING RE-REVIEW
V6 CHILD EXPLICIT APPROVAL: NOT ISSUED
V6 CHILD APPROVAL RECORD: NOT PUBLISHED
COMPLETE MERGED V6 CHILD IDENTITY: NOT AVAILABLE
PHASE B: FORBIDDEN
```

- Blockers: re-review of these five corrections, explicit approval of the exact design, and merge of the truthful child approval record.
- Follow-ups: migration 0007 owner admission, selection-storage conformance, migration 0008, governed command integration, and later read/output boundaries.
- Preferences: none.
- Baseline-law amendment: none.
- Active-baseline files affected in Phase A: none.

No open ambiguity may be resolved during Phase B. Any material change to grant custody, role assumption, capsule coexistence, durability, file scope, or the future `SECURITY DEFINER` relationship requires a versioned contract amendment.

## 15. Approval and merge gate

This proposed child contract authorizes no implementation, grant, migration, publication, or approval record by itself.

After final review, the AI must display one complete plain-English decision card in the designated Codex task. The card must include this design's exact canonical byte length and digest, the exact approval sentence, the approval-sentence digest, all prerequisite identities, permitted effects and non-effects, preservation rules, and the next required sequence.

Only the designated architect's later user-authored exact sentence in that same task may authorize one documentation-only approval record. The approval record is evidence of that decision, not a substitute for it.

Phase B remains forbidden until the truthful approval record merges, the complete merged RFC identity is authenticated, no demonstrated Blocker remains, and the architect separately requests Phase B implementation.

Once the approved Phase B acceptance criteria pass and no demonstrated Blocker remains, merge that implementation PR. New ideas, Preferences, and non-blocking hardening become Follow-ups and do not reopen review. A cross-boundary request stops work and becomes a separate prerequisite, amendment, or stacked PR.

## Appendix A — Architect approval record

This appendix is the one documentation-only approval record authorized by the designated architect. The underlying approved design remains the exact 44,159-byte proposed design identified below. The approved-status metadata above and this appendix are the only differences permitted by section 6.1.

### A.1 Approved decision identity

- contract identity: `ofarm.tenant-current-context-selection-owner-admission.issue176.v0.1`;
- intended path: `docs/rfcs/OFARM_Tenant_Current_Context_Selection_Owner_Admission_RFC_v0_1.md`;
- reviewed base: `c3adb8e47a01690920c539de9c54fb18c581cdaa`;
- canonical approved-design encoding: UTF-8 with LF line endings and exactly one terminal LF;
- approved-design byte length: `44159`; and
- approved-design digest: `sha256:a77daed8b06f88ce163f9778684ae87d9a404cc27f15548df965e1cc9f7d1585`.

The proposed and unapproved status wording inside those approved design bytes is preserved by identity. Publication changes only the status metadata above as expressly permitted by section 6.1.

### A.2 Approval authority and provenance

- Codex task: `019fa821-93c9-7ef1-8c94-1c0e92ea46b9`;
- live decision-card agent-message reference: `item-1691`;
- architect approval turn: `019fc236-bde3-7333-bde7-ded1eb996fd8`;
- architect user-message stable reference: `item-1692`;
- architect user-message timestamp: `2026-08-02T11:23:15Z`;
- canonical decision-card encoding: UTF-8 with no terminal LF;
- canonical decision-card byte length: `6058`;
- canonical decision-card digest: `sha256:fd44f5d1a740507c0db362062be812ba49a2b5b00f87cbe57aa713d3d478aa97`;
- canonical approval-sentence encoding: UTF-8 with no terminal newline;
- canonical approval-sentence byte length: `528`; and
- canonical approval-sentence digest: `sha256:dfe0fac7c8e067469d2f2c4fac42163b428433fb5d18ca304bc438ee319f4c47`.

The architect's exact user-authored approval sentence was:

> I explicitly approve the Phase A design of contract ofarm.tenant-current-context-selection-owner-admission.issue176.v0.1 at sha256:a77daed8b06f88ce163f9778684ae87d9a404cc27f15548df965e1cc9f7d1585 (44,159 bytes) in Codex task 019fa821-93c9-7ef1-8c94-1c0e92ea46b9 and authorize one documentation-only approval record with exactly the provenance, permitted effects, non-effects, preservation rules, and next required sequence stated in the complete decision card displayed immediately before this approval request in the same task.

The user authored that exact sentence as a later message in the same task after the complete live decision card. It was not inferred from repository credentials, GitHub activity, PR authorship, review, comment, reaction, merge, or an AI-generated message.

### A.3 Prerequisite identities

- architecture context: `reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md`, 96,406 bytes, `sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256`;
- ADR 0001: 147,112 bytes, `sha256:bc49e566ddbdf98868162aa7ccca0940fa76fca1bfaaa261c8c831dbb5515a4d`;
- ADR 0002: 61,427 bytes, `sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796`;
- ADR 0003: 93,419 bytes, `sha256:b188f4d60e46887fde4231e73bb00adb9bd70b75e807627e8a3906389a0fa5be`;
- complete approved parent: 52,382 bytes, `sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb`;
- complete merged V5 child: 32,169 bytes, `sha256:c1d02969811be0d5b02bdae158cb48e5d8148356ca9d4bac956c8861d529c37a`;
- V5 implementation head: `79b2769e80fa530e19b642f0f7b3972fb331b338`;
- V5 implementation merge: `c3adb8e47a01690920c539de9c54fb18c581cdaa`;
- exact five-migration V5 set: `sha256:ef2e85c150d7c445ae33d4c1cc63a06bbcf17c79f1e7bdaf070ae4819ed38288`;
- migration 0005: 8,545 bytes, `sha256:fde66e835f8c4456d7404eb00b99292e267f573f8b126f781f3ed55bd5e8df9a`;
- current tenant provisioning specification: `ofarm.tenant-postgresql-provisioning.v1`, `sha256:e15a5d5903681e2796c70ca2cac19b1aa85d3538589f99046a01c3663f5d8556`; and
- current external tenant catalog verifier: `sha256:9d75e28bd8083348becd0e95a6873b5dece22c01a6f5fef2bdcae09fb609acf8`.

Review evidence includes issue-comment `5157011168`, bounded re-review issue-comment `5157374763`, and the complete decision card displayed in Codex task item `item-1691`.

### A.4 Permitted effects

The approval has exactly these effects:

1. the exact 44,159-byte Phase A design becomes architect-approved;
2. one documentation-only approval-record PR may add this RFC at its intended path; and
3. this RFC may differ from the approved design only by the approved-status metadata and this truthful approval appendix.

### A.5 Non-effects

The approval does not authorize Phase B, migration 0006, either `EXECUTE` grant, a database mutation, capsule creation or consumption, a new permanent role or login, a membership or `SET ROLE` edge, permanent schema or relation authority, tenant-lock admission, migration 0007, selection storage or migration 0008, an owner-owned activation function, RuntimeBundle selection, command integration, routes, reads, outputs, production deployment activation, existing-target upgrade or repair, legacy behavior, or #192 behavior.

### A.6 Preservation rules

This published RFC preserves the approved decision, trust model, authority map, state machine, invariants, negative cases, architecture, non-goals, traceability, file boundary, and merge-stop rule byte-for-byte. Only the status metadata and this appendix differ from the approved design.

Phase B must authenticate the complete merged RFC byte length and SHA-256. The pre-publication approved-design digest cannot substitute for that complete merged identity.

### A.7 Next required sequence

1. Publish and review this one-file documentation-only approval-record PR.
2. Merge that PR.
3. Compute and authenticate the complete merged RFC byte length and SHA-256.
4. Require the architect to request Phase B implementation separately.
5. Only then may the closed migration-0006 implementation boundary begin.
6. Keep migration 0007, selection conformance, migration 0008, governed command integration, and output work in their separately reviewed boundaries.

This approval record does not authorize any implementation.
