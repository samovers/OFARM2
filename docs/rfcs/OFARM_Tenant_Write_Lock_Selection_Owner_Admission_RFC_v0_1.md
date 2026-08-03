# OFARM2 Tenant Write-Lock Selection-Owner Admission — Phase A Contract v0.1

**Status:** architect-approved Phase A contract; documentation-only and without database, migration, grant, runtime, storage, output, deployment, legacy, or #192 effect

**Contract identity:** ofarm.tenant-write-lock-selection-owner-admission.issue176.v0.1

**Intended RFC path:** docs/rfcs/OFARM_Tenant_Write_Lock_Selection_Owner_Admission_RFC_v0_1.md

**Reviewed base:** a1a2ae2249b3578f1479d8a979eb84d5aab7c331

**Primary ticket:** #176

**Primary trust boundary:** admission of the existing unreachable tenant database owner to the existing lock-owner-owned, transaction-bound tenant write-lock wrapper

**Intended PR boundary:** one documentation-only child approval record first; one later, separately authorized Phase B implementation PR for this admission only

## 1. Problem and goal

A later, separately governed tenant selection-storage activation function must serialize tenant-scoped selection changes through the existing tenant write-lock authority. That future function is expected to execute as the existing unreachable ofarm_owner role. The existing no-argument lock wrapper is owned by ofarm_tenant_lock_owner and is not currently executable by ofarm_owner.

This contract governs the smallest admission that gives ofarm_owner exactly EXECUTE on:

ofarm.take_tenant_write_lock()

This boundary adds exactly one new permanent privilege to ofarm_owner. All V6 current-context privileges remain exact and unchanged.

The wrapper continues to derive the tenant only from the verified current TenantBinding, resolve the advisory-lock key only from ofarm.tenant_registry, and call only pg_catalog.pg_advisory_xact_lock(bigint). The admission does not grant raw advisory-lock authority to ofarm_owner, create the future activation function, select or store a RuntimeBundle, integrate a governed command, or activate temporal behavior.

The governing prerequisites are:

| Authority | Exact reviewed identity |
|---|---|
| Reviewed repository base | a1a2ae2249b3578f1479d8a979eb84d5aab7c331 |
| Architecture context | reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md, 96,406 bytes, sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256 |
| Migration and role architecture | docs/adr/0001-tenancy-and-schema-migrations.md, 147,112 bytes, sha256:bc49e566ddbdf98868162aa7ccca0940fa76fca1bfaaa261c8c831dbb5515a4d |
| Temporal separation | docs/adr/0002-valid-time-and-knowledge-time.md, 61,427 bytes, sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796 |
| Binder and current-context semantics | docs/adr/0003-tenant-capability-trust-and-binder.md, 93,419 bytes, sha256:b188f4d60e46887fde4231e73bb00adb9bd70b75e807627e8a3906389a0fa5be |
| Approved parent contract | docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_Activation_Admission_RFC_v0_1.md; ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1; 52,382 bytes; sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb |
| Merged V5 child contract | docs/rfcs/OFARM_Tenant_Binding_Selection_Control_Admission_RFC_v0_1.md; ofarm.tenant-binding-selection-control-admission.issue176.v0.1; 32,169 bytes; sha256:c1d02969811be0d5b02bdae158cb48e5d8148356ca9d4bac956c8861d529c37a |
| V5 implementation | head 79b2769e80fa530e19b642f0f7b3972fb331b338; merge c3adb8e47a01690920c539de9c54fb18c581cdaa |
| Exact five-migration set | sha256:ef2e85c150d7c445ae33d4c1cc63a06bbcf17c79f1e7bdaf070ae4819ed38288 |
| Migration 0005 source | 8,545 bytes; sha256:fde66e835f8c4456d7404eb00b99292e267f573f8b126f781f3ed55bd5e8df9a |
| Complete merged V6 child contract | docs/rfcs/OFARM_Tenant_Current_Context_Selection_Owner_Admission_RFC_v0_1.md; ofarm.tenant-current-context-selection-owner-admission.issue176.v0.1; 50,383 bytes; sha256:af85e259230b69edeba80ddc2eea2f070a601fd3888fd463ce595f9cc446b13d |
| V6 implementation | head 2694465e81ba0e646c663c5a769ccd6afe3505eb; merge a1a2ae2249b3578f1479d8a979eb84d5aab7c331 |
| Exact six-migration set | sha256:209990a8a9ac60ab096b11d418051127b7c891e4bfc6cefdf282d72f3875d0de |
| Migration 0006 source | 8,655 bytes; sha256:a61c668a2bae04026b8413385f8bc1b5fd43f08f8d5281501ff766a57d552b48 |
| Current tenant provisioning specification | ofarm.tenant-postgresql-provisioning.v1; sha256:54a86af2f0dfc5573a81de6e40b99e4f347f87fdf7a43b03a60e45e80e455fa9 |
| Current external tenant catalog verifier | deployment/postgresql/catalog_identity.py::TENANT_CATALOG_VERIFIER_DIGEST; sha256:683ee77aa8c9549f4ef284addbf204108e5d770530350b1d6258d13de912c75f |

The mandatory governance order is:

~~~text
MERGED_V6_IMPLEMENTATION_AVAILABLE
  -> EXACT_V7_CHILD_DESIGN_REVIEWED
  -> EXPLICIT_V7_CHILD_APPROVAL
  -> V7_CHILD_APPROVAL_RECORD_PUBLISHED_AND_MERGED
  -> COMPLETE_MERGED_V7_CHILD_IDENTITY_AUTHENTICATED
  -> EXPLICIT_PHASE_B_REQUEST
  -> V7_PHASE_B_PERMITTED
~~~

Explicit approval of this design authorizes only its documentation-only approval record. It does not authorize Phase B.

## 2. Learning value

This boundary demonstrates that OFARM2 can admit a future owner-executed selection function to one existing tenant-scoped lock wrapper without exposing a raw PostgreSQL lock primitive, transferring lock ownership, creating a login or role-assumption path, or introducing a generic privilege-grant mechanism.

It also extends the already accepted one-use V5 and V6 capsule lifecycle with a third independently governed admission while retaining one closed provisioning and recovery phase authority.

## 3. Non-goals

This contract does not authorize:

- implementation during Phase A;
- amendment of the architecture report, ADR 0001, ADR 0002, ADR 0003, the parent contract, or the merged V5 or V6 contracts;
- changes to the wrapper signature, body, owner, configuration, failure behavior, tenant derivation, lock-key derivation, or existing ACL rows;
- direct advisory-lock authority for ofarm_owner or any other new role;
- any new permanent login, role, membership, role-assumption edge, schema or relation privilege, object ownership, or database CONNECT grant;
- tenant knowledge-position or RuntimeBundle selection storage;
- migration 0008 or its owner-owned activation function;
- RuntimeBundle selection, activation, profiles, or RuntimeBundle changes;
- COMMIT_OPERATION_CLAIM_DRAFT integration;
- routes, APIs, materialization, qualification, promotion, publication, reads, outputs, or receipts;
- valid-time carrier selection, knowledge-time execution, historical views, current-state outputs, or windowed outputs;
- existing-target upgrade, repair, reconciliation, or backfill;
- production deployment activation;
- legacy integration; or
- #192 behavior.

## 4. Trust model

### Protected assets

Protected assets are tenant identity, TenantBinding custody, tenant advisory-lock keys, the lock-wrapper definition and ACL, raw advisory-lock ACLs, database ownership, role membership and role-assumption edges, provisioning and migration source identity, migration history and execution evidence, the structural catalog trust anchor, credentials, capabilities, signing keys, and commit-outcome classification.

### Trusted components

Trusted components are PostgreSQL 17; the exact accepted architecture, ADRs, parent, V5, and V6 identities in section 1; the unchanged binder and current-context functions; the unchanged tenant registry and lock wrapper; exact reviewed provisioning and migration sources; the migration loader and runner; the external catalog verifier; trusted Python, psycopg, and cryptographic implementations; and the external provisioning-superuser authority only while it creates and executes the closed V7 capsule through PostgreSQL SECURITY DEFINER custody.

Execution must use already authenticated immutable migration bytes. It must not reopen migration files after authentication.

### Untrusted actors and inputs

Every managed non-superuser role, every production login, an attacker holding any managed login credential, caller-supplied tenant or lock-key values, release identity, execution UUID, connection and retry timing, migration target state, and attempted caller-supplied schema, role, routine, privilege, digest, grant target, GUC, or temporary-table value are untrusted.

### In-scope failures and misuse

In scope are managed-role misuse; attempted role assumption; absent or invalid TenantBinding; reviewed source substitution; detectable filesystem mutation; filesystem mutation after authenticated bytes are loaded; capsule source substitution; ordinary interruption and rollback; backend loss before commit; successful commit with lost acknowledgement; retries; attempted use against an older head-6 target without the V7 capsule; and every mixed V5, V6, or V7 ledger, capsule, ACL, role, and verifier state.

### Explicitly excluded compromise capabilities

Out of scope are a compromised PostgreSQL implementation; arbitrary mutation of the trusted Python process after source authentication; compromised Python, psycopg, operating-system, or cryptographic dependencies; operating-system compromise; deliberate malicious action by the external provisioning superuser; coherent replacement of implementation and its independent integrity authority; signer-key theft; and deliberate compromise of the architect, migration operator, or deployment authority.

Operator mistakes that produce detectable source, role, ACL, history, capsule, or catalog disagreement remain in scope and must fail closed.

## 5. Authority map

| Decision | Sole authority |
|---|---|
| Migration, role, provisioning, and advisory-lock architecture | Exact ADR-0001 identity in section 1 |
| Temporal meaning and separation | Exact ADR-0002 identity in section 1 |
| TenantBinding and current-context semantics | Exact ADR-0003 identity and unchanged binder functions |
| Governing #176 command sequence | Complete approved-parent identity in section 1 |
| V5 and V6 admission prerequisites | Complete merged V5 and V6 identities and implementation merges in section 1 |
| V7 child design approval | Exact architect-authored approval in the designated Codex task |
| Durable V7 approval evidence | Complete merged V7 RFC approval appendix |
| Wrapper tenant identity | ofarm.current_tenant_id() under the unchanged ADR-0003 TenantBinding |
| Wrapper lock-key identity | Exact matching row in ofarm.tenant_registry |
| Wrapper definition and ownership | ofarm_tenant_lock_owner and the exact pre-V7 object identity in section 6.2 |
| Raw tenant advisory-lock authority | ofarm_tenant_lock_owner only, for pg_catalog.pg_advisory_xact_lock(bigint) |
| Exact V7 grant target | Closed one-row ACL addition in section 6.3 |
| Final ACL grantor | ofarm_tenant_lock_owner |
| Permanent provisioning state and transient capsule | Exact reviewed ProvisioningSpec |
| Migration order and ledger append | Migration runner |
| Complete ledger-row authentication | Migration runner |
| Capsule ordering marker | Closed static capsule query in section 6.4 |
| Final service structure | Migration-0007 structural verifier |
| Verifier authenticity | External catalog-verifier digest |
| Future owner-executed activation function | Separate migration-0008 contract and implementation |
| Selection storage, governed command, runtime, routes, and outputs | Their later reviewed contracts only |

ofarm_owner is an existing NOLOGIN role. This boundary adds exactly one new permanent privilege to it; all V6 current-context privileges and every other owner privilege remain exact and unchanged. There is no legacy fallback, caller-provided tenant or lock key, credential-derived tenant identity, alternate lock path, or generic privilege registry.

## 6. State machine and ordering

### 6.1 Byte-authenticated approval publication

The canonical child-design bytes are UTF-8, use LF line endings, begin with this document's first #, end after the merge-stop rule, and contain exactly one terminal LF. Before approval is solicited, the complete live decision card must state:

- the exact child-design byte length and SHA-256;
- its own canonical byte length and SHA-256;
- the exact approval sentence;
- the approval sentence's UTF-8 byte length and SHA-256, with no terminal LF included in the sentence identity;
- the exact prerequisite identities from section 1;
- the permitted effect, non-effects, preservation rules, and next sequence.

The designated architect must send that exact approval sentence as a later user-authored message in Codex task 019fa821-93c9-7ef1-8c94-1c0e92ea46b9. Typing it or copying it directly from the complete live decision card displayed earlier in that task is valid. Text or a card digest copied from another task, another card, another decision, documentation, a template, a PR, GitHub, or AI-authored or AI-sent text other than that complete live decision card is invalid. AI-generated messages, repository credentials, PR authorship, review, comment, reaction, merge, or generic approval never count.

Only after the exact user-authored message exists may one documentation-only PR publish this RFC. The publication must preserve the approved decision, trust model, authority map, phase model, transaction order, invariants, negative cases, architecture, non-goals, traceability, exact file boundary, stop conditions, and merge-stop rule byte-for-byte.

Only these differences from the approved design bytes are permitted:

1. status metadata may change from proposed and unapproved to architect-approved; and
2. one truthful approval appendix may be added.

The approval appendix must record:

- contract identity and intended path;
- reviewed base;
- exact approved-design byte length and SHA-256;
- every prerequisite identity in section 1;
- Codex task identifier;
- decision-card stable reference, canonical byte length, and SHA-256;
- architect user-message identifier or stable reference and timestamp;
- exact user-authored approval sentence, canonical byte length, and SHA-256;
- the single permitted effect;
- every non-effect;
- preservation rules; and
- next required sequence.

After that documentation PR merges, Phase B must authenticate and pin the complete merged RFC byte length and SHA-256. The pre-publication design digest cannot substitute for the complete merged-child identity. A separate explicit Phase B request remains required.

If the documentation PR changes any protected design text, omits required appendix evidence, records an inexact prerequisite, or includes any file other than the intended RFC path, it must not merge. The design must return to review as a new exact byte identity.

### 6.2 Exact pre-V7 wrapper and raw-lock state

The pre-V7 wrapper is closed:

| Property | Exact pre-V7 value |
|---|---|
| Schema and name | ofarm.take_tenant_write_lock |
| Identity arguments | none |
| Return | pg_catalog.void |
| Set-returning | false |
| Owner | ofarm_tenant_lock_owner |
| Language | plpgsql |
| Security | SECURITY DEFINER |
| Volatility | VOLATILE |
| Strict | false |
| Leakproof | false |
| Parallel | UNSAFE |
| Configuration | search_path=pg_catalog, pg_temp |
| prosrc SHA-256 | 38c75f051ee82b75c2e872fe2e191874e17984da7183add568f481d2eadb0de8 |
| PUBLIC execute | absent |
| Existing complete execute ACL rows | ofarm_tenant_lock_owner, ofarm_app, and ofarm_worker; each granted by ofarm_tenant_lock_owner with no grant option |
| Effective ofarm_app execute | true |
| Effective ofarm_worker execute | true |
| Effective ofarm_owner execute | false |
| Effective ofarm_runtime_bundle_publisher execute | false |
| Effective ofarm_tenant_lock_owner execute | true |
| Effective ofarm_migrator execute | false |
| Effective ofarm_readiness execute | false |

The wrapper has no parameters. Its body obtains the tenant through ofarm.current_tenant_id(), selects only tenant_id and advisory_lock_key from the exact matching ofarm.tenant_registry row, and invokes only pg_catalog.pg_advisory_xact_lock(bound_lock_key). Its definition, owner, configuration, tenant and key derivation, and existing ACL rows do not change in V7.

The exact raw advisory-lock boundary remains:

- PUBLIC and ordinary managed roles have no EXECUTE on any protected pg_catalog advisory-lock or advisory-unlock overload;
- ofarm_tenant_lock_owner alone among provisioned tenant roles has EXECUTE on pg_catalog.pg_advisory_xact_lock(bigint);
- the isolated tenant migration-lock owner retains only the separately governed pg_catalog.pg_advisory_xact_lock(integer, integer) execution edge;
- no raw advisory-lock or advisory-unlock privilege is added, removed, or reinterpreted by V7.

The complete structural catalog identity remains responsible for every advisory-function ACL row, including grantor and grant-option state.

### 6.3 Exact admission

The only admitted permanent ACL addition is:

| Object | Grantee | Privilege | Grantor | Grant option |
|---|---|---|---|---|
| ofarm.take_tenant_write_lock() | ofarm_owner | EXECUTE | ofarm_tenant_lock_owner | false |

After V7, the complete wrapper ACL inventory is exactly four execute rows: ofarm_tenant_lock_owner, ofarm_app, ofarm_worker, and ofarm_owner. Every row records ofarm_tenant_lock_owner as grantor and has no grant option. PUBLIC remains absent. The application and worker rows remain unchanged.

If the approved custody path does not produce ofarm_tenant_lock_owner as the durable PostgreSQL grantor, Phase B must stop. It may not accept the external provisioning superuser, ofarm_owner, ofarm_migrator, or another role as grantor without a versioned contract amendment.

ofarm_owner remains NOLOGIN. This boundary adds no role, membership, inheritance, SET ROLE, ownership, schema, relation, CONNECT, or raw advisory-lock authority. The existing release-time ofarm_migrator SET ROLE ofarm_owner edge remains the sole role-assumption path. No production login gains that edge.

### 6.4 Closed V7 capsule

Fresh provisioning adds exactly one V7 capsule alongside the independently governed V5 and V6 capsules:

ofarm_infrastructure.seal_tenant_write_lock_selection_owner_admission()

It is no-argument, returns pg_catalog.void, uses LANGUAGE plpgsql, is VOLATILE, PARALLEL UNSAFE, initially SECURITY DEFINER, initially owned by the external provisioning-superuser category, executable only by ofarm_migrator, inaccessible to PUBLIC and every other managed role, fully static, free of dynamic SQL, and configured with the existing constrained sealer search path.

It may name only the exact migration ledger, version 7, filename 0007_tenant_write_lock_selection_owner_admission.sql, service identity ofarm.tenant-postgresql.v1, ofarm.take_tenant_write_lock(), ofarm_owner, itself, ofarm_infrastructure, and ofarm_migrator.

Its only ledger check is the literal equivalent of:

~~~text
ledger row count = 7
maximum version = 7
version-7 filename = 0007_tenant_write_lock_selection_owner_admission.sql
version-7 service identity = ofarm.tenant-postgresql.v1
~~~

The capsule must not authenticate, derive, embed, or accept:

- source SHA-256;
- source byte length;
- applied-prefix digest;
- provisioning-spec digest;
- release identity;
- execution UUID;
- GUC values;
- temporary-table values;
- tenant identity;
- advisory-lock key;
- role, schema, routine, or privilege identifiers supplied by a caller; or
- any other dynamic authority input.

Those identities belong only to the runner's complete row and invocation authentication.

The capsule may perform only this fixed sequence:

~~~text
verify the literal four-part ordering marker
-> issue the one literal wrapper EXECUTE grant to ofarm_owner
-> grant temporary CREATE on ofarm_infrastructure to ofarm_migrator
-> change itself to SECURITY INVOKER
-> transfer itself to ofarm_migrator
-> revoke the temporary CREATE privilege
-> return
~~~

The runner must then verify the exact wrapper ACL, capsule SECURITY INVOKER state, ownership transfer, absence of temporary schema CREATE, and closed capsule ACL before dropping the capsule.

### 6.5 Complete V7 ledger authentication

After appending the V7 row and before invoking the capsule, the runner authenticates all nine fields:

1. version;
2. filename;
3. source SHA-256;
4. source byte length;
5. applied-prefix digest;
6. service identity;
7. provisioning-spec digest;
8. current release identity; and
9. current execution UUID.

After the capsule is dropped and ofarm_owner is restored as the fixed migration execution role, the runner authenticates the same nine fields again.

The capsule proves ordering only. It does not duplicate complete row authentication. Migration 0007 does not authenticate the current invocation.

### 6.6 Combined V5, V6, and V7 phase matrix

~~~text
A0 — NO LEDGER OR DURABLE HEADS 1–4
  V5 capsule: exact and present
  V6 capsule: exact and present
  V7 capsule: exact and present
  V5 binder grants: absent
  V6 owner grants: absent
  V7 owner lock-wrapper grant: absent

A1 — DURABLE HEAD 5
  V5 capsule: absent
  V5 binder grants: exact
  V6 capsule: exact and present
  V7 capsule: exact and present
  V6 owner grants: absent
  V7 owner lock-wrapper grant: absent

A2 — DURABLE HEAD 6
  V5 capsule: absent
  V6 capsule: absent
  V5 binder grants: exact
  V6 owner grants: exact
  V7 capsule: exact and present
  V7 owner lock-wrapper grant: absent

A3 — UNCOMMITTED V7 TRANSITION
  exact A2 starting state
  authenticated immutable migration-0007 bytes executed
  exact V7 row appended and all nine fields authenticated
  V7 wrapper grant: exact
  V7 capsule: self-demoted, transferred, verified, then removed
  fixed migration execution role: restored
  same nine V7 row fields: re-authenticated
  final V7 history, boundary, structure, and catalog: authenticated before commit

A4 — DURABLE HEAD 7
  V5 capsule: absent
  V6 capsule: absent
  V7 capsule: absent
  V5 binder grants: exact
  V6 owner grants: exact
  V7 owner lock-wrapper grant: exact
  exact V7 history and final verifier: valid
~~~

A3 is observable only inside the one protected migration transaction. Provisioning, readiness, recovery, startup, and no-op reconciliation must never accept A3 as durable or complete.

Every combination not listed above refuses. Fresh-target provisioning accepts all three exact capsules when the ledger is absent and through durable heads 1–4. Migration 0005 consumes only V5. Migration 0006 consumes only V6. Migration 0007 consumes only V7. Provisioning observation, migration-lock verification, readiness, recovery, structural verification, and tests use this one matrix. There is no second phase authority.

### 6.7 Exact V7 transaction order

The capsule lifecycle in section 6.4 is subordinate to, and must be executed only within, this single transaction order:

~~~text
EXACT_A2
  -> authenticate complete merged V7 RFC and prerequisite identities
  -> authenticate provisioning, migration-set, source, and catalog identities
  -> acquire the existing migration lock
  -> re-authenticate exact A2
  -> execute immutable verifier-only migration 0007
  -> append the exact V7 ledger row
  -> authenticate all nine row fields
  -> invoke only the V7 capsule as ofarm_migrator
  -> verify the exact wrapper grant
  -> verify capsule SECURITY INVOKER demotion
  -> verify capsule ownership transfer to ofarm_migrator
  -> verify temporary schema CREATE is absent
  -> drop only the V7 capsule
  -> restore ofarm_owner as the fixed migration execution role
  -> re-authenticate the same nine V7 row fields
  -> verify exact history, boundary, structure, and catalog identity
  -> COMMIT
~~~

Migration 0007 may modify only the final ofarm.verify_tenant_structure() definition. It must not perform a grant or revoke, change the wrapper, create or alter a role, create a capsule, change another verifier, or alter another object.

All transition effects occur in one PostgreSQL transaction. No durable intermediate state is lawful.

### 6.8 Commit outcome and retry

~~~text
PRE_COMMIT_FAILURE_OR_BACKEND_LOSS
  -> PostgreSQL rolls back the entire V7 transaction
  -> exact A2
  -> V7 capsule present
  -> owner wrapper grant absent
  -> retry migration 0007 from A2

COMMIT_CONFIRMED
  -> exact A4
  -> V7 capsule absent
  -> owner wrapper grant exact
  -> final verifier valid
  -> report committed

POST_COMMIT_ACKNOWLEDGEMENT_LOSS
  -> COMMIT reached PostgreSQL
  -> the successful response did not reach the client
  -> report MigrationOutcomeUnknown
  -> reconnect and authenticate exact durable state
~~~

After reconnection:

~~~text
exact A2
  -> retry migration 0007

exact A4
  -> return a verified no-op outcome
  -> preserve the uncertain execution UUID as the observed V7 head execution identity
  -> append no second V7 row
  -> recreate no capsule
  -> consume no capsule

anything else
  -> refuse automatic recovery
~~~

## 7. Stable invariants

- **TWLSO-001:** Phase B requires every exact prerequisite identity in section 1, explicit architect approval of the exact V7 design bytes, merge of its truthful approval record, authentication of the complete merged V7 RFC, and a separate explicit Phase B request.
- **TWLSO-002:** The architecture report, ADRs 0001–0003, parent contract, and merged V5 and V6 contracts remain unchanged and authoritative.
- **TWLSO-003:** The only new permanent privilege is the one exact owner EXECUTE row in section 6.3.
- **TWLSO-004:** The new row has the exact object, grantee, grantor, privilege, and no-grant-option state in section 6.3.
- **TWLSO-005:** No login, controller, application, worker, readiness, publisher, migrator, or other role receives new permanent authority.
- **TWLSO-006:** ofarm_owner remains NOLOGIN, and this boundary adds no role-assumption edge.
- **TWLSO-007:** The wrapper signature, return, body, prosrc digest, owner, language, security mode, volatility, strictness, leakproof setting, parallel setting, configuration, existing ACL rows, tenant derivation, lock-key derivation, and raw advisory-lock boundary remain exact.
- **TWLSO-008:** A connection authenticated as ofarm_migrator that executes SET ROLE ofarm_owner and then calls the wrapper without a verified TenantBinding reaches ofarm.current_tenant_id(), raises SQLSTATE 42501 with verified tenant context is absent, and acquires no advisory lock.
- **TWLSO-009:** No caller supplies or influences the tenant ID, advisory-lock key, role, schema, function, privilege, or capsule authority.
- **TWLSO-010:** The V7 capsule has the exact static identity, ordering query, body, owner transition, ACL, and security properties in section 6.4.
- **TWLSO-011:** The runner authenticates all nine V7 ledger fields before capsule invocation and again after capsule removal and restoration of the fixed migration execution role.
- **TWLSO-012:** The capsule authenticates only the closed four-part ordering marker.
- **TWLSO-013:** A0 through A4 are the sole phase authority for V5, V6, and V7 admission.
- **TWLSO-014:** Each migration consumes only its own capsule.
- **TWLSO-015:** Migration 0007 changes only the final structural verifier and cannot itself grant authority or alter the admitted target.
- **TWLSO-016:** Migration execution, ledger append, grant admission, capsule removal, second row authentication, and final verification are one atomic transaction.
- **TWLSO-017:** Any confirmed pre-commit failure or backend loss leaves exact A2 and permits a clean retry.
- **TWLSO-018:** Confirmed completion produces exact A4.
- **TWLSO-019:** Lost commit acknowledgement produces MigrationOutcomeUnknown until a fresh connection proves exact A2 or exact A4.
- **TWLSO-020:** Exact A4 after acknowledgement loss is a verified no-op that preserves the uncertain execution UUID and creates no second row or capsule.
- **TWLSO-021:** Every partial grant, stray capsule, wrong capsule state, wrong owner, wrong grantor, extra ACL, or ledger, boundary, structure, or catalog mismatch fails closed.
- **TWLSO-022:** Source bytes, migration-set digest, provisioning digest, prerequisite identities, complete merged V7 RFC, and external catalog identity must match their reviewed values before durable admission.
- **TWLSO-023:** A pre-deployment head-6 target created without the exact V7 capsule is refused and is not repaired or upgraded.
- **TWLSO-024:** Verification and errors expose no tenant data, binding data, lock key, credentials, capabilities, or secret-bearing connection material.
- **TWLSO-025:** Phase B introduces no reusable arbitrary-grant executor, generic capsule builder, alternate lock path, or generic privilege registry.
- **TWLSO-026:** The grant has no selection-storage, activation-function, RuntimeBundle, governed-command, route, output, temporal-execution, deployment, legacy, or #192 effect.
- **TWLSO-027:** Every structural-verifier replacement is preflighted for uniqueness: each old fragment occurs exactly once, each new fragment is absent, and the checks cover migration-head values, prefix digest, provisioning digest, the routine inventory, and the complete inserted ACL-check block.

## 8. Required production-reachable negative cases

| Invariant | Required negative case |
|---|---|
| TWLSO-001–002 | A missing, altered, unmerged, or unapproved prerequisite or V7 contract identity refuses Phase B before database mutation |
| TWLSO-003–005 | Any extra grantee, privilege, grant option, membership, or permanent authority fails structural and external catalog verification |
| TWLSO-006 | Any new login or production role-assumption path to ofarm_owner fails verification |
| TWLSO-007 | Any changed wrapper property, existing ACL row, tenant or key derivation, or raw advisory-lock ACL fails verification |
| TWLSO-008 | The exact migrator, SET ROLE owner, unbound wrapper call fails through current_tenant_id() with the expected message and leaves no advisory lock |
| TWLSO-009–010 | A parameterized, dynamic, wrongly owned, wrongly executable, or source-substituted capsule is refused |
| TWLSO-011 | Mutation of each of the nine authenticated row fields is refused at its owning boundary |
| TWLSO-012 | A correct four-part ledger position with incorrect source or invocation evidence is still refused |
| TWLSO-013–014 | Every unlisted phase or consumption of another migration's capsule is refused |
| TWLSO-015 | A grant, revoke, wrapper change, role change, capsule creation, or non-final-verifier change in migration 0007 fails conformance |
| TWLSO-016–018 | Failure before commit rolls back the row, grant, capsule changes, and verifier change to exact A2 |
| TWLSO-019–020 | Acknowledgement loss accepts only exact A2 retry or exact A4 verified no-op |
| TWLSO-021 | A partial grant, extra or missing capsule, wrong grantor, wrong owner, stray ACL, or mixed history fails closed |
| TWLSO-022 | Wrong RFC, source bytes, source length, prefix digest, provisioning digest, release, execution, service, or catalog identity refuses admission |
| TWLSO-023 | A head-6 target without the V7 capsule refuses without repair |
| TWLSO-024 | Failure and test evidence contain no tenant-sensitive or secret-bearing values |
| TWLSO-025 | Any caller-selected grant target, general grant executor, or alternate raw-lock path fails review and conformance |
| TWLSO-026 | Any activation, storage, command, route, output, RuntimeBundle, temporal, deployment, legacy, or #192 change stops the PR |
| TWLSO-027 | A missing, duplicate, or already-present old or new verifier fragment fails before rewriting |

The existing real connection-boundary substitution harness may test the nine row-field mutations. No production mutation hook may be added.

## 9. Smallest coherent architecture

The complete admitted transition is:

~~~text
exact A2
  -> authenticated immutable verifier-only migration
  -> authenticated exact V7 row
  -> one literal grant through one-use custody
  -> capsule removal and fixed-role restoration
  -> second exact row authentication
  -> exact final history, boundary, structure, and catalog
  -> exact A4
~~~

There is one new permanent privilege, one new migration position, one capsule, one combined phase authority, and no runtime path.

Literal V7 verification is preferred where it makes authority and refusal behavior obvious. Phase B must not refactor the accepted V5 or V6 capsules into a generic framework merely to reduce line count.

## 10. Exact Phase B file boundary

A later Phase B implementation PR may modify only:

1. kernel/migrations/0007_tenant_write_lock_selection_owner_admission.sql
2. deployment/postgresql/provisioning_specs.py
3. deployment/postgresql/provisioning.py
4. deployment/postgresql/migration_runner.py
5. deployment/postgresql/migration_sets.py
6. deployment/postgresql/catalog_identity.py
7. deployment/postgresql/README.md
8. kernel/tests/test_migration_sets.py
9. kernel/tests/test_postgresql_provisioning.py
10. kernel/tests/test_postgresql_migration_runner.py
11. kernel/tests/test_postgresql_tenant_migration.py
12. kernel/tests/test_postgresql_readiness_unit.py
13. kernel/tests/test_postgresql_structural_compatibility.py
14. kernel/tests/test_postgresql_catalog_identity_unit.py
15. conformance/review_baseline_test_inventory.json, only when mechanically required by a change to the canonical collected test-node inventory, including a count or node-ID change

No other file is authorized. A need for another file stops Phase B for a versioned amendment or a separate trust-boundary PR.

## 11. Elegance audit

The design preserves one authority chain:

~~~text
future separately governed owner-owned activation function
  -> existing no-argument tenant write-lock wrapper
  -> verified current TenantBinding
  -> exact tenant_registry key
  -> isolated lock-owner raw bigint transaction lock
~~~

This contract admits only the first execution edge and does not implement the future caller.

Code size is a warning signal. Growth caused by explicit verification of the one custody transition may be justified. Growth caused by abstraction, repair behavior, generic grants, runtime selection, another phase authority, or combined trust boundaries is not.

## 12. Verification and traceability

| Requirement | Required evidence |
|---|---|
| Exact prerequisites | Byte lengths, SHA-256 values, commits, migration-set digest, provisioning digest, and external catalog digest match section 1 |
| Exact wrapper object | Structural query proves every property and effective-execution value in section 6.2 |
| Complete wrapper ACL | Exhaustive aclexplode inventory proves the exact pre-V7 three rows and post-V7 four rows, grantor, privilege, and no grant option |
| Preserved raw-lock custody | Complete advisory-routine ACL inventory and external catalog digest remain exact except for no raw-lock change |
| Bound tenant dependence | Real connection test uses ofarm_migrator, SET ROLE ofarm_owner, unbound call, expected current-context 42501, and no acquired advisory lock |
| Static capsule | Source, signature, owner, ACL, security mode, ordering query, demotion, transfer, temporary CREATE removal, and drop are exact |
| Complete invocation identity | All nine fields are authenticated before capsule invocation and after capsule removal and role restoration |
| One phase authority | Provisioning, migration runner, readiness, recovery, and tests accept only A0, A1, A2, and A4 durably |
| Atomicity | Fault and backend-loss tests roll back to exact A2 |
| Uncertain outcome | Real connection-boundary substitution proves exact A2 retry, exact A4 verified no-op, and all-other-state refusal |
| Fresh-target-only | Existing head 6 without the exact V7 capsule refuses |
| Verifier-only migration | Conformance proves migration 0007 changes only the final structural verifier |
| Rewrite uniqueness | Tests prove every old fragment occurs exactly once and every new fragment is absent before replacement |
| Closed file boundary | Diff contains only section 10 paths |
| Privacy | Logs and failures disclose no protected tenant or secret material |
| Repository conformance | Focused tests, complete required tests, canonical inventory check, and python3 conformance/ofarm_pkg_contract_check.py pass |

The package conformance check must run before every commit. The canonical test inventory is regenerated only when its collected node count or node IDs change.

## 13. Provisional pre-deployment posture

This admission is fresh-target-only and pre-deployment. It creates no existing-target repair or upgrade promise. Before deployment, the provisional Codex approval mechanism must be replaced by independently human-controlled and independently verifiable signing or approval.

## 14. Stop conditions and review disposition

Stop and propose a versioned amendment or separate contract if Phase B requires:

- changing the wrapper, its owner, its tenant derivation, or its lock-key derivation;
- granting raw advisory-lock access to ofarm_owner;
- adding or changing a role-assumption path;
- changing existing application, worker, current-context, or other V6 privileges;
- adding a production file outside section 10;
- adding upgrade, repair, or reconciliation behavior;
- adding an activation function or selection storage;
- integrating a command, route, RuntimeBundle, profile, output, or temporal execution;
- modifying an active or frozen contract;
- changing legacy behavior or #192; or
- accepting a durable state other than A0, A1, A2, or A4.

There are no open design decisions inside this trust boundary. The contract remains unapproved until the exact canonical design receives final review, a complete live decision card is displayed in the designated Codex task, and the designated architect sends its exact approval sentence as a later user-authored message.

**Merge-stop rule:** the documentation-only approval record must not merge unless its sole changed path is the intended V7 RFC, its only differences from the approved design bytes are the truthful status transition and one complete approval appendix, and every recorded identity and approval reference verifies exactly.

## Appendix A — Architect approval record

This appendix is the one documentation-only child approval record authorized by the designated architect. The underlying approved design remains the exact 38,060-byte proposed design identified below. The approved-status metadata above and this appendix are the only differences permitted by section 6.1.

### A.1 Approved decision identity

- contract identity: ofarm.tenant-write-lock-selection-owner-admission.issue176.v0.1;
- intended path: docs/rfcs/OFARM_Tenant_Write_Lock_Selection_Owner_Admission_RFC_v0_1.md;
- reviewed base: a1a2ae2249b3578f1479d8a979eb84d5aab7c331;
- canonical approved-design encoding: UTF-8 with LF line endings and exactly one terminal LF;
- approved-design byte length: 38,060; and
- approved-design digest: sha256:9e03992988966415bd23368d9001f18a6105b270076238eb51d8ae319f2c83e4.

The proposed and unapproved status wording inside those approved design bytes is preserved by identity. Publication changes only the status metadata above as expressly permitted by section 6.1.

### A.2 Approval authority and provenance

- Codex task: 019fa821-93c9-7ef1-8c94-1c0e92ea46b9;
- live decision-card turn: 019fc6b9-32aa-7103-95f6-bd4933c201f7;
- live decision-card agent-message stable reference: item-1829;
- canonical decision-card extraction: UTF-8 with LF line endings, beginning with OFARM2 COMPLETE LIVE DECISION CARD and ending with END OF OFARM2 COMPLETE LIVE DECISION CARD, with no terminal LF;
- canonical decision-card byte length: 9,344;
- canonical decision-card digest: sha256:53ff18ff659815446bfa1cd046078bcc81c07f675d8fb7c1878016a7626c1676;
- architect approval turn: 019fc6bc-3af6-71e1-86b8-d1fa0627eb8c;
- architect user-message stable reference: item-1830;
- architect user-message timestamp: 2026-08-03T08:27:32Z;
- canonical approval-sentence encoding: UTF-8 with no terminal LF;
- canonical approval-sentence byte length: 529; and
- canonical approval-sentence digest: sha256:f6d4cb1262dc74f79bf67ef1f72bf706382b6524efbaa888e22aad93567c15b4.

The architect's exact user-authored approval sentence was:

> I explicitly approve the Phase A design of contract ofarm.tenant-write-lock-selection-owner-admission.issue176.v0.1 at sha256:9e03992988966415bd23368d9001f18a6105b270076238eb51d8ae319f2c83e4 (38,060 bytes) in Codex task 019fa821-93c9-7ef1-8c94-1c0e92ea46b9 and authorize one documentation-only child approval record with exactly the provenance, permitted effects, non-effects, preservation rules, and next required sequence stated in the complete decision card displayed immediately before this approval request in the same task.

The architect authored that exact sentence as a later message in the same task after the complete live decision card. Copying it directly from that card is valid under section 6.1. It was not inferred from repository credentials, GitHub activity, PR authorship, review, comment, reaction, merge, generic approval, or an AI-generated message.

### A.3 Exact prerequisite identities

- reviewed repository base: a1a2ae2249b3578f1479d8a979eb84d5aab7c331;
- architecture context: reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md, 96,406 bytes, sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256;
- ADR 0001: docs/adr/0001-tenancy-and-schema-migrations.md, 147,112 bytes, sha256:bc49e566ddbdf98868162aa7ccca0940fa76fca1bfaaa261c8c831dbb5515a4d;
- ADR 0002: docs/adr/0002-valid-time-and-knowledge-time.md, 61,427 bytes, sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796;
- ADR 0003: docs/adr/0003-tenant-capability-trust-and-binder.md, 93,419 bytes, sha256:b188f4d60e46887fde4231e73bb00adb9bd70b75e807627e8a3906389a0fa5be;
- approved parent: ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1, 52,382 bytes, sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb;
- merged V5 child: ofarm.tenant-binding-selection-control-admission.issue176.v0.1, 32,169 bytes, sha256:c1d02969811be0d5b02bdae158cb48e5d8148356ca9d4bac956c8861d529c37a;
- V5 implementation head: 79b2769e80fa530e19b642f0f7b3972fb331b338;
- V5 implementation merge: c3adb8e47a01690920c539de9c54fb18c581cdaa;
- exact five-migration set: sha256:ef2e85c150d7c445ae33d4c1cc63a06bbcf17c79f1e7bdaf070ae4819ed38288;
- migration 0005: 8,545 bytes, sha256:fde66e835f8c4456d7404eb00b99292e267f573f8b126f781f3ed55bd5e8df9a;
- complete merged V6 child: ofarm.tenant-current-context-selection-owner-admission.issue176.v0.1, 50,383 bytes, sha256:af85e259230b69edeba80ddc2eea2f070a601fd3888fd463ce595f9cc446b13d;
- V6 implementation head: 2694465e81ba0e646c663c5a769ccd6afe3505eb;
- V6 implementation merge: a1a2ae2249b3578f1479d8a979eb84d5aab7c331;
- exact six-migration set: sha256:209990a8a9ac60ab096b11d418051127b7c891e4bfc6cefdf282d72f3875d0de;
- migration 0006: 8,655 bytes, sha256:a61c668a2bae04026b8413385f8bc1b5fd43f08f8d5281501ff766a57d552b48;
- current tenant provisioning specification: ofarm.tenant-postgresql-provisioning.v1, sha256:54a86af2f0dfc5573a81de6e40b99e4f347f87fdf7a43b03a60e45e80e455fa9; and
- current external tenant catalog verifier: sha256:683ee77aa8c9549f4ef284addbf204108e5d770530350b1d6258d13de912c75f.

Review evidence includes issue comments 5163563247 and 5163841991 and the complete decision card at Codex task item item-1829.

### A.4 Permitted effects

The approval has exactly these effects:

1. the exact 38,060-byte Phase A design becomes architect-approved;
2. one documentation-only child approval-record PR may add this RFC at its intended path; and
3. this RFC may differ from the approved design only by the approved-status metadata and this truthful approval appendix.

### A.5 Non-effects

The approval does not authorize Phase B, migration 0007 implementation or execution, the wrapper EXECUTE grant, a database mutation, role or ownership changes, membership or role-assumption changes, schema or relation authority, raw advisory-lock authority, V7 capsule creation or consumption, changes to the lock wrapper, changes to V5 or V6 authority, tenant knowledge-position or RuntimeBundle selection storage, migration 0008, an owner-owned activation function, RuntimeBundle or profile activation, COMMIT_OPERATION_CLAIM_DRAFT integration, routes, semantic-surface expansion, materialization, qualification, promotion, publication, reads, outputs, receipts, valid-time or knowledge-time execution, historical, current-state, or windowed behavior, deployment, existing-target upgrade, repair, reconciliation, backfill, legacy integration, or #192 behavior.

### A.6 Preservation rules

This published RFC preserves the approved decision, trust model, authority map, phase model, transaction order, invariants, negative cases, architecture, non-goals, traceability, exact Phase B file boundary, stop conditions, and merge-stop rule byte-for-byte. Only the status metadata and this appendix differ from the approved design.

Phase B must authenticate the complete merged RFC byte length and SHA-256. The pre-publication approved-design digest cannot substitute for that complete merged identity.

Before deployment, this provisional Codex approval workflow must be replaced by an independently human-controlled and independently verifiable signing or approval system.

### A.7 Next required sequence

1. Publish and review this one-file documentation-only approval-record PR.
2. Merge it only if every identity, preservation rule, and approval reference verifies.
3. Compute and authenticate the complete merged RFC byte length and SHA-256.
4. Require a separate explicit architect request for Phase B.
5. Only then may the closed migration-0007 implementation boundary begin.
