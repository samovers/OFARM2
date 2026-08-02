# OFARM2 Tenant-Binding Selection-Control Admission — Phase A Contract v0.1

**Status:** architect-approved Phase A contract; documentation-only and without database, migration, runtime, selection, output, deployment, legacy, or #192 effect

**Contract identity:** `ofarm.tenant-binding-selection-control-admission.issue176.v0.1`

**Intended RFC path:** `docs/rfcs/OFARM_Tenant_Binding_Selection_Control_Admission_RFC_v0_1.md`

**Reviewed base:** `33c7ce69fd2b960be1f6c4d3600154a6032b9e0f`

**Primary ticket:** #176

**Primary trust boundary:** admission of one isolated selection-control database login to the existing verified `TenantBinding` entry points

**Intended PR boundary:** one documentation-only child approval record first; one later, separately authorized Phase B implementation PR for this admission only

## 1. Problem and goal

The proposed RuntimeBundle selection-control login cannot establish a verified `TenantBinding`. The existing challenge and capability-binding functions are executable only by already admitted application and worker roles.

This contract governs the smallest admission that lets one isolated control login call exactly those existing entry points without giving it tenant-selection authority, signer custody, binder membership, application or worker authority, tenant data access, current-context access, tenant-lock authority, selection storage, or runtime behavior.

The governing parent is architect-approved:

- contract identity: `ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1`;
- path: `docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_Activation_Admission_RFC_v0_1.md`;
- approval-record merge: `33c7ce69fd2b960be1f6c4d3600154a6032b9e0f`;
- complete approved-parent byte length: `52382`; and
- complete approved-parent digest: `sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb`.

The parent approval appendix records approval of its underlying 49,259-byte design at `sha256:137fc69f203ff18229efd0c97ada8affae209c0e64dd3e8c464d7627937de44b` through decision card `sha256:d0782493042dc2b6dd782a2a8dcced1315ad2474c5b305da1a54ae7ab775fc28`.

The mandatory governance order is:

```text
APPROVED_PARENT_IDENTITY_AVAILABLE
  -> EXACT_CHILD_DESIGN_REVIEWED
  -> EXPLICIT_CHILD_APPROVAL
  -> CHILD_APPROVAL_RECORD_PUBLISHED_AND_MERGED
  -> CHILD_PHASE_B_PERMITTED
```

Explicit child approval authorizes only its documentation record. It does not itself authorize Phase B implementation.

## 2. Learning value

This boundary demonstrates that OFARM2 can widen access to an existing principal-resolution protocol without creating another tenant-authority source, granting binder membership, changing binder bodies, introducing a generic privileged-grant mechanism, or treating a database login as tenant identity.

It also proves that one migration-specific grant capsule can be consumed safely across ordinary rollback and uncertain commit outcomes while leaving no reusable privileged mechanism.

## 3. Non-goals

This contract does not authorize:

- implementation during Phase A;
- amendment of the approved parent;
- capability minting, signing, acquisition, transport, caching, or key custody;
- changes to challenge, capability, principal-resolution, or binder semantics;
- current-context or tenant-lock grants;
- tenant knowledge-position or selection storage;
- migrations `0006`, `0007`, or `0008`;
- RuntimeBundle selection or activation;
- a control adapter, service, route, profile, or public API;
- `COMMIT_OPERATION_CLAIM_DRAFT` integration;
- materialization, qualification, promotion, publication, reads, outputs, or receipts;
- valid-time, knowledge-time, historical, current-state, or window execution;
- an existing-target upgrade, repair, or reconciliation path;
- deployment behavior;
- legacy integration; or
- #192 behavior.

## 4. Trust model

### Protected assets

Protected assets are tenant and authenticated-principal identity, binder custody, binder definitions and ACLs, role membership, migration history and evidence, provisioning and migration source identity, structural-verifier identity, tenant relations, current context, tenant locks, credentials, capabilities, and signing keys.

### Trusted components

Trusted components are PostgreSQL 17; the unchanged ADR-0003 binder functions; the independently governed signer; exact reviewed provisioning and migration sources; the migration loader and runner; the external catalog verifier; the trusted Python, psycopg, and cryptographic implementations; and the external provisioning-superuser authority while it creates the closed capsule.

### Untrusted actors and inputs

The controller, control login, an attacker holding the control credential, every other managed non-superuser role, caller-supplied capability text, release identity, execution UUID, connection timing, retry timing, and attempted caller-supplied role, schema, routine, tenant, or grant target are untrusted.

A stolen control credential is in scope and remains insufficient to choose a tenant. A valid independently signed capability accepted through the unchanged challenge protocol is still required.

### In scope

In scope are managed-role misuse; invalid, expired, replayed, wrong-audience, wrong-backend, wrong-incarnation, or wrong-transaction capabilities; reviewed source changes; source or filesystem mutation detectable by exact loaders and digests; filesystem mutation after authenticated migration bytes are loaded; ordinary interruption and rollback; connection loss before or during commit; commit-outcome uncertainty; misuse against an existing target; and every mixed durable V4/V5 state.

Execution must use the already authenticated immutable migration bytes rather than reopening source files after authentication.

### Excluded compromise capabilities

Out of scope are a compromised PostgreSQL implementation; arbitrary mutation of the trusted Python process after source authentication; compromised Python, psycopg, or cryptographic dependencies; operating-system compromise; deliberate malicious action by the external provisioning superuser; coherent replacement of implementation and its independent code-integrity authority; signer-key theft; and deliberate compromise of migration or deployment authority.

These exclusions never permit inconsistent catalog, digest, ACL, or history state to be accepted.

## 5. Authority map

| Decision | Sole authority |
|---|---|
| Governing parent | Complete approved-parent file identity pinned in section 1 |
| Child design approval | Exact architect-authored approval in the designated Codex task |
| Durable child approval evidence | Merged child RFC approval appendix |
| Tenant and Party identity | Existing binder verification of the signer-produced capability |
| Capability minting | Independently governed signer |
| Challenge and binding semantics | ADR 0003 and unchanged binder functions |
| Permanent role definitions and inert grants | `ProvisioningSpec` |
| Database `CONNECT` grantee | Control login only |
| Schema `USAGE` grantee | Controller only, inherited by the login |
| Binder-function grant targets | Exact two-function closed set in this contract |
| Final ACL grantor | `ofarm_binder` |
| Migration order and ledger append | Migration runner |
| Complete ledger-row authentication | Migration runner |
| Capsule ordering marker | Closed static capsule query |
| Final service structure | Migration-0005 structural verifier |
| Verifier authenticity | External catalog-verifier digest |
| Current-context and lock consumers | Separate migration-0006 and migration-0007 contracts |
| Selection storage | Separate conformance and migration-0008 contracts |

There is no legacy fallback, alias, caller-provided tenant field, alternate write path, or database-credential-derived tenant authority.

## 6. State machine and ordering

### 6.1 Child approval publication

After explicit approval of the exact child-design bytes, one documentation-only PR may publish this RFC. The published RFC must preserve the approved decision, authority map, trust model, state machine, invariants, negative cases, architecture, non-goals, traceability, and PR boundaries byte-for-byte.

Only two non-material differences are permitted:

1. status metadata changing the child from proposed and unapproved to architect-approved; and
2. an approval-record appendix.

The appendix must record the Codex task identifier, user-message identifier or stable reference, exact user-authored approval sentence, user-message timestamp, approved child-design byte length and digest, child decision-card byte length and digest, approved-parent complete length and digest, permitted effects and non-effects, preservation rules, and next required sequence.

After merge, Phase B must pin the complete merged child-file identity. It may not rely only on the pre-publication design digest.

### 6.2 Inert fresh-provisioning state

Fresh-target provisioning creates the controller, login, sole membership, hardened login settings, database `CONNECT` for the login, schema `USAGE` for the controller, and one exact temporary grant capsule.

`CONNECT` and schema `USAGE` are pre-migration inert custody. They are not part of migration `0005` or its rollback because the controller has no execute privilege on either binder entry point and no relation privilege.

### 6.3 Exact roles

`ofarm_command_runtime_bundle_selection_controller` is `NOLOGIN`, `NOINHERIT`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, and `NOBYPASSRLS`. It owns no object and belongs to no role.

`ofarm_command_runtime_bundle_selection_control_login` is `LOGIN`, `INHERIT`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, and `NOBYPASSRLS`, has connection limit one, owns no object, and uses the existing complete `_CONTROL_SETTINGS`:

```text
statement_timeout = 5000 ms
lock_timeout = 500 ms
idle_in_transaction_session_timeout = 5000 ms
transaction_timeout = 10000 ms
temp_file_limit = 0 KiB
work_mem = 1024 KiB
jit = off
max_parallel_workers_per_gather = 0
row_security = on
search_path = pg_catalog
synchronous_commit = on
```

Its sole membership is:

```text
ROLE ofarm_command_runtime_bundle_selection_controller
INHERIT TRUE
SET FALSE
ADMIN FALSE
```

Only the login receives the new database `CONNECT`. Only the controller receives the new schema `USAGE`. The login inherits controller privileges only through this membership.

### 6.4 Exact permanent admission

The only admission grants are `EXECUTE` on:

- `ofarm.create_tenant_challenge()`; and
- `ofarm.bind_tenant_capability(text)`.

Both grants go to the controller, record `ofarm_binder` as grantor, omit grant option, and are not duplicated directly to the login. They are the atomic admission gate.

No other binder, current-context, tenant-lock, raw-lock, relation, publication, or selection privilege is admitted.

### 6.5 Closed grant capsule

Fresh provisioning creates exactly:

`ofarm_infrastructure.seal_tenant_binding_selection_control_admission()`

It is no-argument, returns `pg_catalog.void`, uses `LANGUAGE plpgsql`, is `VOLATILE`, `PARALLEL UNSAFE`, initially `SECURITY DEFINER`, initially owned by the external provisioning-superuser category, executable only by `ofarm_migrator`, inaccessible to `PUBLIC` and every other managed role, fully static, free of dynamic SQL, and configured with the existing constrained sealer search path.

It may name only the exact migration ledger, version `5`, filename `0005_tenant_binding_selection_control_admission.sql`, service identity `ofarm.tenant-postgresql.v1`, the two binder functions, the controller, itself, the infrastructure schema, and `ofarm_migrator`.

Its only ledger check is this non-circular transaction-visible marker:

```text
ledger row count = 5
head version = 5
head filename = 0005_tenant_binding_selection_control_admission.sql
head service identity = ofarm.tenant-postgresql.v1
```

It must not embed or accept its enclosing provisioning-spec digest, migration-0005 source digest or length, applied-prefix digest, release identity, execution UUID, GUC, temporary-table value, function argument, or other dynamic authority seam.

### 6.6 Complete ledger authentication

Immediately after its own append and before capsule invocation, the runner authenticates version, filename, source SHA-256, source byte length, applied-prefix digest, service identity, provisioning-spec digest, current release identity, and current execution UUID.

The capsule proves ordering only. It does not duplicate the runner's complete row authentication.

### 6.7 Capsule consumption

After making the two grants, the capsule follows the existing sealer order:

1. grant temporary `CREATE` on `ofarm_infrastructure` to `ofarm_migrator`;
2. change itself to `SECURITY INVOKER`;
3. transfer itself to `ofarm_migrator`;
4. revoke the temporary `CREATE`;
5. return;
6. let the runner verify the ACLs and demoted capsule;
7. let the runner drop the capsule;
8. restore the fixed migration role; and
9. authenticate and run final structural verification.

No generic capsule consumer, callback, hook, or grant registry is introduced.

### 6.8 Migration transaction

```text
D0_FRESH_PROVISIONED_INERT
  roles, membership, CONNECT, schema USAGE, capsule present
  binder grants absent

D1_EXACT_V4_READY
  exact V4 history under the new fresh-target provisioning specification
  capsule exact and present
  binder grants absent

D2_V5_SQL_EXECUTED
  migration SQL executed
  ledger still exact V4
  capsule present
  binder grants absent

D3_V5_ROW_AUTHENTICATED
  complete runner-owned V5 row appended and authenticated

D4_GRANTS_AND_CAPSULE_TRANSITIONED
  exact two grants present
  capsule self-demoted and transferred

D5_V5_PRECOMMIT_VERIFIED
  capsule absent
  exact grants and final structure authenticated

D6_V5_COMMIT_CONFIRMED
  durable exact V5 state
```

The runner alone owns the brief uncommitted state in which the ledger reports V5 while the capsule remains. It must consume the capsule before final boundary verification.

### 6.9 Failure and recovery

```text
PRE_COMMIT_FAILURE
  -> rollback required
  -> exact V4 history
  -> original capsule present
  -> binder grants absent
```

The inert provisioned roles, membership, `CONNECT`, settings, and schema `USAGE` remain because they predate the transaction.

```text
COMMIT_CONFIRMED
  -> exact V5 history
  -> exact two binder grants
  -> capsule absent
  -> final structure authenticated
```

```text
COMMIT_OUTCOME_UNKNOWN
  -> no rollback or success claim
  -> reconnect
  -> authenticate exact durable state
```

Only two reconnection states are lawful:

1. exact V4, original capsule present, both grants absent: retry migration `0005`; or
2. exact V5, capsule absent, both grants exact, final verifier valid: return a verified committed/no-op outcome.

Every mixed state refuses and requires separately authorized recovery. Durable head V4 requires the exact capsule and absent binder grants. Durable head V5 forbids the capsule and requires the exact grants.

## 7. Invariants and acceptance criteria

- **TBSA-001:** Phase B requires the exact approved-parent identity, explicit architect approval of the exact child design, and merge of the child RFC containing its truthful approval record. Status metadata and the approval appendix are the only permitted differences from the approved child-design bytes.
- **TBSA-002:** Tenant and principal authority come only from a capability accepted by the unchanged binder.
- **TBSA-003:** The controller and login have exactly the defined attributes and own no objects.
- **TBSA-004:** The login has exactly one membership with `INHERIT TRUE`, `SET FALSE`, and `ADMIN FALSE`.
- **TBSA-005:** Only the login receives the new database `CONNECT`; only the controller receives the new schema `USAGE`.
- **TBSA-006:** Pre-provisioned `CONNECT` and schema `USAGE` remain inert until both binder grants exist.
- **TBSA-007:** The only new binder-function privileges are the two exact controller grants without grant option.
- **TBSA-008:** Both final ACL entries record `ofarm_binder` as grantor.
- **TBSA-009:** No binder, challenge, binding, context, or lock body or ownership changes.
- **TBSA-010:** The capsule is one exact no-argument static function with no dynamic authority input.
- **TBSA-011:** The runner authenticates every complete migration-0005 ledger field before capsule invocation.
- **TBSA-012:** The capsule checks only the closed non-circular V5 ordering marker.
- **TBSA-013:** Ledger append, both binder grants, capsule transition and removal, and final verification are one transaction.
- **TBSA-014:** Pre-commit failure restores exact V4 history, the original capsule, and absence of both binder grants.
- **TBSA-015:** Commit uncertainty makes no success or rollback claim and requires exact reconnection classification.
- **TBSA-016:** Every mixed V4/V5, capsule, grant, or verifier state fails closed.
- **TBSA-017:** The capsule is present through durable V4 and absent from durable V5.
- **TBSA-018:** The controller and login receive no current-context, tenant-lock, raw-lock, relation, signing, application, worker, publication, selection, ownership, or migration authority.
- **TBSA-019:** Detectable source, digest, provisioning, migration-history, or catalog disagreement fails before durable admission.
- **TBSA-020:** The boundary is fresh-target-only and creates no runtime, storage, output, legacy, or #192 effect.
- **TBSA-021:** Credentials, capabilities, tenant identifiers, and signing material are absent from repository and migration evidence.
- **TBSA-022:** No generic privileged-grant hook, registry, callback, or reusable capsule framework is introduced.

## 8. Negative cases

| Invariant | Supported entry and counterexample | Required result |
|---|---|---|
| TBSA-001 | Child approval exists, but its record has not merged or pins the proposed-parent digest | Phase B refuses |
| TBSA-002 | Control login submits a tenant name without a signed capability | No binding |
| TBSA-003 | Provisioning gives the controller `LOGIN` or ownership | Provisioning verification refuses |
| TBSA-004 | Login receives app membership or `SET TRUE` | Role verification refuses |
| TBSA-005 | Controller receives `CONNECT`, or login receives direct schema `USAGE` | ACL verification refuses |
| TBSA-006 | Control login calls either binder function at durable V4 | Permission denied |
| TBSA-007 | A third binder grant or grant option appears | Transaction refuses |
| TBSA-008 | ACL records an unexpected grantor | Transaction refuses |
| TBSA-009 | Migration changes a binder body or owner | Digest and structural verification refuse |
| TBSA-010 | Capsule accepts a role, routine, GUC, argument, or temporary-table value | Provisioning verification refuses |
| TBSA-011 | V5 row has the wrong release identity or execution UUID | Capsule is never invoked |
| TBSA-012 | Capsule runs before the V5 row exists | Capsule refuses |
| TBSA-013 | Failure occurs after either grant but before commit | Entire transaction rolls back |
| TBSA-014 | Pre-commit recovery finds V4 without the capsule | Refuse as mixed state |
| TBSA-015 | Connection is terminated during commit acknowledgement | Raise outcome unknown and reconnect |
| TBSA-016 | Reconnect finds V5 with one grant, V4 with a grant, or V5 with capsule | Refuse recovery |
| TBSA-017 | Durable V5 retains the capsule | Final verification refuses |
| TBSA-018 | Control login calls context, lock, relation, publication, or selection entry points | Permission denied |
| TBSA-019 | Loaded migration bytes disagree with their declared digest | Refuse before database side effects |
| TBSA-020 | Runner targets an existing V4 target lacking the new provisioning state | Refuse; no reconciliation |
| TBSA-021 | A real capability or credential appears in evidence | Reject evidence |
| TBSA-022 | Implementation introduces a generic privileged-grant list | Review blocker |

Commit-disconnection verification must use a real disposable PostgreSQL connection-loss mechanism, not only private-field mutation or monkeypatching.

## 9. Proposed architecture and smallest change

The minimum coherent Phase B is one controller, one isolated login, one membership, one login `CONNECT`, one controller schema `USAGE`, two binder grants, one migration-specific temporary capsule, one explicit migration-0005 runner transition, phase-aware capsule observation, one updated final structural-verifier identity, and focused tests.

The capsule belongs in this admission boundary because the protected functions are binder-owned while migration SQL runs as `ofarm_owner`. It preserves binder attribution without adding a role-assumption edge. A generic grant framework is larger and creates an unnecessary extension point. Direct binder membership collapses the boundary. Editing binder bodies moves policy into the wrong authority.

## 10. Elegance audit

| Measure | Count |
|---|---:|
| Tenant-authority sources | 1 |
| New login roles | 1 |
| New capability roles | 1 |
| New memberships | 1 |
| New permanent binder grants | 2 |
| New permanent functions | 0 |
| New relations | 0 |
| Changed binder bodies or owners | 0 |
| Temporary capsules | 1 |
| Capsules remaining at V5 | 0 |
| Generic grant mechanisms | 0 |
| Runtime or legacy integrations | 0 |

The capsule is deleted after successful use. Its runner branch is an explicit V5 transition, not a reusable abstraction. A rewrite is unnecessary because the existing provisioning, sealer, ledger, outcome-unknown, and verifier mechanisms provide the required composition points.

## 11. Pull request boundaries

### Child approval-record PR

After explicit approval of the exact child-design bytes, one documentation-only PR may add only:

`docs/rfcs/OFARM_Tenant_Binding_Selection_Control_Admission_RFC_v0_1.md`

It must contain the approved child design unchanged except for the permitted approved-status metadata and exact approval appendix. It may not implement anything.

### Later Phase B implementation PR

The closed expected allowlist is:

- `kernel/migrations/0005_tenant_binding_selection_control_admission.sql`
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
- `conformance/review_baseline_test_inventory.json` only when mechanically required by a canonical test-node count or node-ID change

If another production authority or non-mechanical file is required, work stops for a contract amendment or separate PR. Reviewers must not require current-context, tenant-lock, selection storage, runtime, route, output, legacy, or #192 work here.

## 12. Provisional-design record

The capsule is intentionally transient, not provisional architecture. Nothing replaces it after successful migration because the durable exact ACLs replace it.

The fresh-target-only infrastructure rule is provisional before deployment. It is acceptable because OFARM2 has no deployed target requiring role reconciliation. Redesign is required if an existing deployed target needs these roles or grants, recovery requires human mixed-state repair, PostgreSQL no longer records the required binder grantor, the capsule cannot remain closed and static, or operational evidence defeats fresh provisioning.

Before deployment, existing-target evolution must either remain unnecessary or receive a separate reviewed infrastructure-upgrade contract.

## 13. Traceability and verification

| Invariant | Owner | Concrete negative test and evidence | Smallest verification |
|---|---|---|---|
| TBSA-001 | RFC approval evidence | missing or wrong parent/child record refuses | governance review |
| TBSA-002 | existing binder | tenant name without capability cannot bind | tenant-migration test |
| TBSA-003 | provisioning spec and generator | role drift refuses; exact catalog rows | provisioning test |
| TBSA-004 | provisioning spec and generator | membership drift refuses; exact `pg_auth_members` | provisioning test |
| TBSA-005 | provisioning spec and verifier | database/schema ACL drift refuses | provisioning test |
| TBSA-006 | provisioning and V4 target | pre-V5 function call denied | tenant-migration test |
| TBSA-007 | capsule and runner | third grant or grant option refuses | tenant-migration test |
| TBSA-008 | capsule and structural verifier | wrong grantor refuses; exact `aclexplode` rows | structural test |
| TBSA-009 | migration 0005 and verifier | body or owner substitution refuses | structural test |
| TBSA-010 | capsule spec | dynamic source form refuses | provisioning test |
| TBSA-011 | migration runner | wrong complete-row value stops before capsule | runner test |
| TBSA-012 | capsule | early call refuses | live tenant-migration test |
| TBSA-013 | runner V5 transition | injected pre-commit failure rolls back all V5 state | runner/live test |
| TBSA-014 | runner recovery | V4 missing capsule refuses | runner/live test |
| TBSA-015 | outcome-unknown reconciliation | real commit disconnect yields verified V4 or V5 | live failure test |
| TBSA-016 | phase-aware verifier | every enumerated mixed state refuses | runner test |
| TBSA-017 | provisioning observer and verifier | capsule required at V4 and forbidden at V5 | structural test |
| TBSA-018 | role ACLs | adjacent protected calls denied | tenant-migration test |
| TBSA-019 | migration set and catalog identity | source/catalog substitution refuses | migration-set/catalog tests |
| TBSA-020 | provisioning observer and runner | old existing target refuses | provisioning/runner test |
| TBSA-021 | fixtures and review evidence | real secret material is absent | repository scan |
| TBSA-022 | runner architecture and package check | generic registry is absent | package check |

Required verification is:

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

The complete canonical test inventory must also pass.

## 14. Open decisions and review disposition

The approved parent gate is satisfied by the 52,382-byte file at `sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb`.

The technical design decisions are closed: schema `USAGE` is inert provisioning state; the runner owns complete ledger authentication; the capsule owns only the non-circular ordering marker; commit uncertainty requires reconnection classification; capsule observation is V4/V5 phase-aware; self-demotion follows the existing sealer order; only the login receives `CONNECT`; and the test files are pinned.

Current disposition:

```text
PARENT APPROVAL: SATISFIED
CHILD DESIGN REVIEW: PENDING FINAL REVIEW
CHILD EXPLICIT APPROVAL: NOT ISSUED
CHILD APPROVAL RECORD: NOT PUBLISHED
PHASE B: FORBIDDEN
```

- Blockers: child design review, explicit child approval, and merged child approval record.
- Follow-ups: separately governed current-context admission, tenant-lock admission, selection-storage conformance, and migration `0008`.
- Preferences: none.
- Baseline-law amendment: none.

## 15. Approval and merge gate

This document is a proposed child contract and authorizes no implementation.

The designated architect must approve the exact child-design bytes in the designated Codex task. That approval may authorize only one documentation-only child approval record with the metadata differences defined in section 6.1.

A generic approval, PR authorship, commit authorship, review conclusion, GitHub credential, mergeability, parent approval, or PR merge does not approve this child.

Phase B remains forbidden until the truthful child approval record merges, its complete merged-file identity is authenticated, and no demonstrated blocker remains. A later implementation still requires an explicit in-scope implementation request.

## Appendix A. Architect approval record

This appendix is the documentation-only child approval record required by
sections 6.1 and 15. The proposal-state and pending-approval wording above
records the state of the exact approved design bytes before the later approval
recorded here. That wording is preserved as part of those approved bytes and
is not a competing current status.

The designated architect approved this exact child Phase A design:

- contract identity:
  `ofarm.tenant-binding-selection-control-admission.issue176.v0.1`;
- intended repository path:
  `docs/rfcs/OFARM_Tenant_Binding_Selection_Control_Admission_RFC_v0_1.md`;
- repository review base:
  `33c7ce69fd2b960be1f6c4d3600154a6032b9e0f`;
- approved child-design byte length: `28794`; and
- approved child-design digest:
  `sha256:9541ae41207cbe3a15b8fe5b7257ccf4c936c99febee810c40da905d1d83fb33`.

The governing approved parent is:

- complete approved-parent byte length: `52382`;
- complete approved-parent digest:
  `sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb`;
  and
- approval-record merge:
  `33c7ce69fd2b960be1f6c4d3600154a6032b9e0f`.

The complete live child decision card preceded the approval in the same Codex
task. Its evidence is:

- Codex task identifier:
  `019fa821-93c9-7ef1-8c94-1c0e92ea46b9`;
- decision-card canonical byte length: `2137`;
- decision-card digest:
  `sha256:5911512d8a25d448fca3b3d7db38efe7ebc949bd613c8328be39d2ed706f8b04`;
- approval turn stable reference:
  `019fc108-d388-7a72-ab4e-e7e0989135d1`;
- user-authored approval-message stable reference: `item-1570`;
- user-authored approval-message timestamp: `2026-08-02T05:53:28Z`;
- approval-sentence canonical byte length: `509`; and
- approval-sentence digest:
  `sha256:a30e103e23553fa6785875563b0cc4eca8bf8e674dade99b9878bad633de0060`.

The exact user-authored approval sentence was:

> I explicitly approve the Phase A design of contract ofarm.tenant-binding-selection-control-admission.issue176.v0.1 at sha256:9541ae41207cbe3a15b8fe5b7257ccf4c936c99febee810c40da905d1d83fb33 (28,794 bytes) in Codex task 019fa821-93c9-7ef1-8c94-1c0e92ea46b9 and authorize one documentation-only child approval record with exactly the provenance, effects, non-effects, preservation rules, and next required sequence stated in decision card sha256:5911512d8a25d448fca3b3d7db38efe7ebc949bd613c8328be39d2ed706f8b04.

The approval has exactly two effects:

1. the pinned child Phase A design is architect-approved; and
2. this one documentation-only child approval record is authorized.

The only permitted differences from the approved child-design bytes are the
status metadata and this appendix. The decision, authority map, trust model,
state machine, invariants, negative cases, architecture, non-goals,
traceability, and pull-request boundaries remain byte-for-byte unchanged.

The approval does not authorize Phase B, a migration, database storage, a role
or grant change, runtime selection or activation, a RuntimeBundle or profile
change, command or route integration, materialization, output, legacy
behavior, or #192 behavior.

After this approval record merges, later work must compute and authenticate
the complete approved-child file length and digest before evaluating the child
Phase B gate. Phase B implementation still requires a separate explicit
in-scope implementation request.
