# OFARM2 Temporal Candidate Conformance Selection-Storage Admission — Phase A Contract v0.1

**Status:** proposed Phase A contract; documentation-only, unapproved, and
without conformance, database, selection, runtime, or deployment effect

**Contract identity:**
`ofarm.temporal-candidate-conformance-selection-storage-admission.issue176.v0.1`

**Reviewed base:** `d7d5f99e5677add8616510af4690cee210d75548`

**RFC path:**
`docs/rfcs/OFARM_Temporal_Candidate_Conformance_Selection_Storage_Admission_RFC_v0_1.md`

**Date:** 2026-08-03

**Primary ticket:** #176

**Governed command:** `COMMIT_OPERATION_CLAIM_DRAFT`

**Primary trust boundary:** the temporal candidate conformance checker's
classification of the exact production paths in which the governed tenant
RuntimeBundle-selection binding may later be referenced

**Phase A PR boundary:** this RFC only

**Future Phase B PR boundary:** the temporal candidate checker, its focused
tests, and canonical test-inventory metadata only when mechanically required

## 1. Decision

After the designated architect explicitly approves this exact contract and a
documentation-only PR truthfully records that approval, one separate Phase B
conformance PR may replace the current blanket selection-storage prohibition
with one closed, path-specific production exception.

The exception is limited to these exact future paths:

```text
kernel/migrations/0008_tenant_command_runtime_bundle_selection.sql
deployment/postgresql/tenant_command_runtime_bundle_selection.py
```

Only the exact reviewed selection-binding identity and canonical digest may be
classified there:

```text
ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1
sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f
```

The exception does not require either future path to exist. It must merge and
pass while both are absent. Once implementation begins, the two paths form one
closed implementation pair: both must be present and conformant, or neither
may be present. The checker may classify the two markers as permitted
production references only after it authenticates the authorities in section
4 and proves the path rules in section 5.

This classification is not selection storage, a selected RuntimeBundle, or
runtime activation. It authorizes no migration, adapter, database write,
command integration, route, output, or deployment act. The later database
Phase B remains governed by the already approved parent contract and still
requires a separate explicit implementation request after this conformance
prerequisite merges.

The state model is:

```text
AUTHORITY_UNPROVED ------------------------------> REFUSED
AUTHORITY_PROVED + BOTH FUTURE PATHS ABSENT ----> CONFORMANT_ABSENT
AUTHORITY_PROVED + BOTH EXACT PATHS CONFORM -----> CONFORMANT_CLASSIFIED
AUTHORITY_PROVED + ONLY ONE PATH PRESENT --------> REFUSED
AUTHORITY_PROVED + ANY OTHER PRODUCTION USE ----> REFUSED
```

Neither conformant state has a transition to publication, selection,
activation, command execution, current truth, or output.

## 2. Why this is one boundary

The temporal checker currently owns both the candidate package's inactive
posture and the classification of narrowly admitted production exceptions.
It already distinguishes the inert RuntimeBundle model role and the exact
migration-0004 persistence exception from forbidden activation authorities.

Migration 0008 and its administrator-only adapter cannot lawfully appear while
the checker still treats every production reference to the tenant selection
binding as proof of an unsupported activation. Conversely, a broad exception
would let the binding leak into runtime, profiles, routes, active registries,
or legacy code.

One conformance PR may therefore authenticate the approved parent and its
three merged custody prerequisites, declare the two-path exception, preserve
the existing forbidden authorities, and test that classification. It may not
create either allowed path or change any database, storage, runtime, candidate,
or lifecycle authority.

## 3. Trust model and protected distinction

The protected distinction is:

```text
reviewed reference eligibility != implemented storage != retained selection
!= runtime selection != command authority != current truth
```

### Trusted inputs

The future checker may trust only:

- the exact fixed authority paths, byte lengths, and SHA-256 values in section
  4;
- the one authenticated tenant `MigrationSet` already loaded by the temporal
  checker from the fixed production migration authority;
- the exact two allowed production paths in section 5;
- the exact two allowed selection markers in section 1;
- the fixed production and legacy import roots owned by
  `conformance/rewrite_architecture_check.py`;
- the exact active catalog, ActiveArtifactSet, and Capability Manifest paths
  already inspected by the temporal checker; and
- checked-in repository bytes from the reviewed source tree.

Paths, identities, digests, import roots, authority sets, and exceptions are
reviewed constants. None may come from a caller, command line, environment,
profile, request, route, database row, newest-file rule, directory order,
network source, or dynamically discovered registry.

### Untrusted claims

The following have no authority to widen the exception:

- candidate status text, a manifest note, or lifecycle wording;
- a RuntimeBundle or component claiming to be selected or active;
- a migration or adapter naming itself as trusted;
- a tenant, principal, capability, credential, profile, or operator assertion;
- PR authorship, review, merge, branch state, commit authorship, repository
  credentials, or green CI; and
- conformance success presented as database, runtime, command, output, or
  deployment authority.

### Excluded compromise capabilities

Deliberate coherent replacement of reviewed source and its independent
integrity authority, compromise of PostgreSQL, Python, the operating system,
or the designated architect, and malicious use of database-owner or external
provisioning-superuser authority remain outside this static checker boundary.
Those exclusions do not authorize weaker ordinary-role or source-classification
tests.

## 4. Exact prerequisite authority pins

The future exception is unavailable unless every fixed prerequisite below is
present and exact.

### 4.1 Parent activation-admission authority

- contract identity:
  `ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1`;
- path:
  `docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_Activation_Admission_RFC_v0_1.md`;
- byte length: `52382`;
- SHA-256:
  `sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb`.

The checker authenticates these exact merged bytes before applying this
exception. It does not parse approval from prose, query GitHub, or infer
authority from file presence.

### 4.2 Exact selection package

- schema path:
  `contracts/candidates/temporal_runtime_bundle_selection/OFARM_TenantCommandRuntimeBundleSelectionBinding_schema_v0_1.json`;
- schema file byte length: `17252`;
- schema file SHA-256:
  `sha256:56604a52465ffc027382e99dea96f2c9bc1bd2479cbaff30dec6bd39c08e6b3d`;
- binding path:
  `contracts/candidates/temporal_runtime_bundle_selection/OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json`;
- binding file byte length: `15993`;
- binding file SHA-256:
  `sha256:1500ffbbfdf11207a6657848fce12618347f767578e55dc070bb282dc5775aac`;
- binding canonical byte length: `13287`;
- binding canonical SHA-256:
  `sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f`.

The candidate files stay unchanged and retain their governed-inactive,
production-unbound posture. This conformance contract admits references to the
fixed identity; it does not rewrite, promote, activate, or register the
candidate artifacts.

### 4.3 Merged custody prerequisites

| Boundary | Complete RFC identity | Merged implementation identity |
| --- | --- | --- |
| Selection-control tenant binding | `docs/rfcs/OFARM_Tenant_Binding_Selection_Control_Admission_RFC_v0_1.md`; `32169` bytes; `sha256:c1d02969811be0d5b02bdae158cb48e5d8148356ca9d4bac956c8861d529c37a` | head `79b2769e80fa530e19b642f0f7b3972fb331b338`; merge `c3adb8e47a01690920c539de9c54fb18c581cdaa` |
| Current-context selection-owner admission | `docs/rfcs/OFARM_Tenant_Current_Context_Selection_Owner_Admission_RFC_v0_1.md`; `50383` bytes; `sha256:af85e259230b69edeba80ddc2eea2f070a601fd3888fd463ce595f9cc446b13d` | head `2694465e81ba0e646c663c5a769ccd6afe3505eb`; merge `a1a2ae2249b3578f1479d8a979eb84d5aab7c331` |
| Tenant-write-lock selection-owner admission | `docs/rfcs/OFARM_Tenant_Write_Lock_Selection_Owner_Admission_RFC_v0_1.md`; `45758` bytes; `sha256:5745ad4b8b588be2b5a1b64b4b84aa757b23f8d2de00ca59e71de8ea304f51b0` | head `568b3a1db58fb97e61fdf5a22c4abd2adc6a15e6`; merge `d7d5f99e5677add8616510af4690cee210d75548` |

Commit identities are review provenance. Exact current source and catalog
identities below remain the executable integrity authority; a commit identity
alone never permits the exception.

### 4.4 Current authenticated database prerequisite

- stable tenant migration prefix through migration 0003:
  `sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0`;
- current production migration head: version `7`;
- current complete production migration-set digest:
  `sha256:5616797d1362c55c78175126edab29cc3e88c021ba0709e3766d3196d2b0126b`;
- migration 0005: `8545` bytes,
  `sha256:fde66e835f8c4456d7404eb00b99292e267f573f8b126f781f3ed55bd5e8df9a`;
- migration 0006: `8655` bytes,
  `sha256:a61c668a2bae04026b8413385f8bc1b5fd43f08f8d5281501ff766a57d552b48`;
- migration 0007: `7936` bytes,
  `sha256:cf8594b6c456953004912722b168d6bdda7c6dbfc903ba8099b018e2f270dff7`;
- current tenant provisioning-spec digest:
  `sha256:2ac8487b64d4fb09d7576ef1ee09ac1f2a3cc5b20558f0d2137620b897c7157c`;
- current final tenant structural-verifier digest:
  `sha256:fcc0e96b4520ffe51ddb5537df24040e4d5948a22b3c387351346cc588e87ee5`;
- external tenant catalog-verifier digest:
  `sha256:026bb61026a9f752fc8dde84bca0e3cbbab374d0ac8f0ba942a72654e44f5f1a`.

The complete migration-set digest is expected to advance only in the later
database Phase B when exact migration 0008 is added. The conformance Phase B
must authenticate the current version-7 set and preserve the already fixed
version-3 prefix. It must not predeclare a version-8 source digest or fabricate
future migration bytes.

If any prerequisite in this section changes before conformance Phase B, work
stops for review and a truthful contract amendment. If the later database
Phase B changes an authority outside its approved allowlist, it also stops; a
passing classifier cannot legalize that expansion.

## 5. Closed production-path classification

### 5.1 Exact allowed paths

The complete allowed production-reference set is:

```text
SELECTION_STORAGE_ALLOWED_PRODUCTION_PATHS = {
    "kernel/migrations/0008_tenant_command_runtime_bundle_selection.sql",
    "deployment/postgresql/tenant_command_runtime_bundle_selection.py",
}
```

No alias, symlink-selected path, renamed migration, generated path, alternate
adapter, compatibility module, test fixture, profile-specific copy, or legacy
copy qualifies.

The candidate artifacts, their RFCs, this authorizing RFC, the checker, and
focused checker tests are governance and verification authorities. Their
necessary marker occurrences are not production exceptions and must not be
mistaken for migration or adapter eligibility.

### 5.2 Authenticated migration classification

The checker already loads one authenticated tenant `MigrationSet`. It must use
that same retained snapshot for migration classification. It must not perform a
second migration glob, reread migration files after authentication, or trust a
filename found only on disk.

Before migration 0008 exists in the authoritative set, absence passes only
while the adapter is also absent. After a separately authorized database PR
adds the complete implementation pair, a selection marker may occur in a
migration only when all of these are true:

1. the authenticated entry has version `8`;
2. its filename is exactly
   `0008_tenant_command_runtime_bundle_selection.sql`;
3. it is the eighth contiguous member of the same authenticated tenant set;
4. its source bytes are the authenticated `Migration.source_bytes`; and
5. every other authenticated tenant migration remains free of the two exact
   selection markers, except pre-existing documentary SQL comments explicitly
   pinned by an amended contract.

Version, filename, source digest, byte length, and applied-prefix digest remain
owned by `deployment/postgresql/migration_sets.py` and the later database PR.
This conformance contract does not guess or reserve their values.

### 5.3 Adapter classification and isolation

Before the exact adapter exists, absence passes only while migration 0008 is
also absent. If it exists, marker occurrence is allowed only in its fixed bytes
at:

```text
deployment/postgresql/tenant_command_runtime_bundle_selection.py
```

The adapter must remain outside both fixed import closures:

```text
production roots = kernel.api, kernel.application_runtime
legacy roots     = kernel.legacy_m1.api, kernel.legacy_m1.runtime
```

The conformance checker proves only the fixed path, marker classification, and
import isolation. It does not duplicate the parent contract's exact binding
validation, sixteen-component closure, tenant-binding, SQL transaction, or
activation semantics. Those belong to the later database implementation and
its focused tests.

Any import of the adapter from either closure refuses. A route, application,
worker, profile runtime, or legacy module cannot become an allowed reference
by re-exporting or wrapping the adapter.

### 5.4 Authorities that remain closed

Existing checks must continue to refuse the selection markers, candidate
paths, or temporal activation markers as applicable in:

- `kernel/runtime_bundle_components.json`;
- `profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json`;
- `profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json`;
- every authenticated tenant migration other than exact migration 0008;
- every module reachable from the fixed production import roots;
- every module reachable from the fixed legacy import roots; and
- any newly proposed active catalog, profile, route, selector, command,
  materializer, read, output, or #192 authority.

The last item is a stop condition, not permission for dynamic filesystem
discovery. If a new active authority must be classified, its exact path and
meaning require a reviewed contract amendment.

## 6. Authority map

- The accepted platform architecture retains governance-before-automation,
  deterministic enforcement, canonical truth, and output-traceability law.
- ADR 0001 owns tenant placement, `TenantBinding`, immutable RuntimeBundle
  publication, and tenant-owned selection/context separation.
- ADR 0002 owns `ValidCut`, `KnowledgeCut`, their independence, tenant-local
  knowledge ordering, carrier meaning, and half-open interval rules. This
  contract neither implements nor redefines them.
- ADR 0003 and the binder implementation own signed capability verification,
  principal resolution, and protected current tenant/Party context.
- The approved parent activation-admission RFC owns the exact future record,
  state transition, function signature, fixed binding validation, knowledge
  allocation, lock use, storage Phase B allowlist, and database verification.
- The three merged admission boundaries in section 4 own only their exact
  control-login binding and owner-consumer grants. This contract neither
  widens nor reopens them.
- `deployment/postgresql/migration_sets.py` and its authenticated
  `MigrationSet` own production migration membership and bytes.
- `conformance/temporal_contract_candidate_check.py` owns the static
  production-reference classification defined here. It does not own selection
  semantics or database correctness.
- `conformance/rewrite_architecture_check.py` owns the fixed production and
  legacy import roots used for isolation proof. This contract does not edit
  that authority.
- The candidate schema and binding own the fixed selection vocabulary and
  remain governed inactive and production unbound.
- The future migration 0008 will own storage, RLS, the closed owner-executed
  function, allocator branch, and controller execute grant only after its
  separate database Phase B is explicitly requested and implemented.
- The future administrator adapter will own fixed local validation and one
  already-bound control transaction under that same later boundary.
- ActiveArtifactSet, Capability Manifest, profiles, routes, runtime catalog,
  current-state reads, historical/window execution, materialization, and
  outputs retain their existing closed authorities.
- `kernel/schema.sql`, `kernel/store.py`, and
  `kernel/runtime_bundle_repository.py` remain quarantined legacy-M1
  authorities and are not dependencies of this exception.
- #192 retains sole authority over audit-runtime behavior.

## 7. Invariants

- **TCSS-001 — Exact authority first.** No selection-storage exception is
  available until the parent and all three prerequisite RFC bytes are exact.
- **TCSS-002 — Two production paths only.** Only exact authenticated migration
  0008 and the exact deployment adapter may carry the two reviewed selection
  markers as production references.
- **TCSS-003 — Absence is conformant.** The conformance prerequisite passes
  before either future production path exists. One present without the other
  refuses; the implemented state requires the complete pair.
- **TCSS-004 — One migration snapshot.** Migration classification uses the
  checker's one retained authenticated `MigrationSet` and its retained source
  bytes; no second scan or read creates authority.
- **TCSS-005 — Version 3 remains stable.** The authenticated knowledge-storage
  prefix through migration 0003 remains the candidate's fixed knowledge
  prerequisite even when the complete production set later advances to 8.
- **TCSS-006 — Prior admissions remain exact.** Migrations 0005, 0006, and
  0007 and their final grants/structure are not amended by this boundary.
- **TCSS-007 — Fixed marker meaning.** Identity, canonical digest, and allowed
  paths are reviewed constants, never caller or configuration data.
- **TCSS-008 — Checker is not the selection oracle.** The checker does not
  duplicate the selection binding, sixteen-component closure, SQL function,
  tenant context, RLS, allocator, retry, or lock rules.
- **TCSS-009 — Candidate bytes remain unchanged.** No candidate schema,
  binding, manifest digest, ERRATA row, promotion record, or lifecycle decision
  changes.
- **TCSS-010 — Catalog and profiles remain closed.** No marker or candidate
  path enters the runtime catalog, ActiveArtifactSet, Capability Manifest, or
  another profile authority.
- **TCSS-011 — Runtime and legacy remain isolated.** The adapter is unreachable
  from both fixed import closures and no production or legacy module gains
  selection authority.
- **TCSS-012 — No activation inference.** An allowed reference or passing
  check creates no relation, row, batch, selected bundle, command authority,
  route, read, output, current truth, or deployment state.
- **TCSS-013 — Closed production semantic surface.** No command, selector,
  route, materialization, current-state read, historical view, WINDOW behavior,
  qualification, or output opens.
- **TCSS-014 — Production/legacy firewall.** The conformance change imports no
  legacy storage, profile runtime, semantic route, materializer, or output
  authority into production.
- **TCSS-015 — Audit separation.** No #192 event, receipt, reason, producer,
  delivery, health, or runtime behavior is added.
- **TCSS-016 — No database mutation.** Conformance Phase B creates no migration
  0008, adapter, relation, role, grant, function, policy, batch, knowledge
  position, or selection row.
- **TCSS-017 — Fail closed on expansion.** A needed third production path,
  new active authority, changed prerequisite, or altered import root stops for
  a versioned amendment rather than broadening the checker.

## 8. Required negative cases

The future Phase B conformance implementation must prove:

| Case | Required result |
| --- | --- |
| All exact authorities are present and both future paths are absent | pass |
| Exactly one of the two future paths is present | refuse the incomplete implementation pair |
| Both future paths are absent and a prerequisite RFC is missing | refuse before classifying paths |
| A prerequisite RFC has the wrong byte length | refuse before classifying paths |
| A prerequisite RFC has the expected length but different bytes or SHA-256 | refuse before classifying paths |
| The selection schema or binding file, file digest, canonical length, or canonical digest differs | refuse |
| The current authenticated migration set is not the exact contiguous version-7 prerequisite | refuse |
| The stable version-3 prefix differs | refuse |
| Exact authenticated migration 0008 and the exact isolated adapter are later present and contain the exact markers | pass this classification only |
| A file named like migration 0008 exists but is absent from the authenticated migration set | refuse; filesystem presence has no authority |
| The authenticated version-8 filename differs by any byte | refuse |
| The markers occur in an authenticated migration other than exact 0008 | refuse |
| The markers occur in the exact adapter, it is outside both import closures, and exact authenticated migration 0008 is also present | pass this classification only |
| The adapter is renamed, copied, selected through a symlink, or loaded from another path | refuse |
| The exact adapter becomes reachable from a production import root | refuse |
| The exact adapter becomes reachable from a legacy import root | refuse |
| A production or legacy wrapper copies the marker without importing the adapter | refuse the marker occurrence in that closure |
| A marker or candidate path enters the active runtime catalog | refuse |
| A temporal activation marker enters the ActiveArtifactSet | refuse |
| A temporal activation marker enters the Capability Manifest | refuse |
| A profile, environment, route, caller, request, newest-file rule, or dynamic registry selects the exception | no such seam may exist; refuse if introduced |
| The checker attempts to validate or redefine the future relation, SQL function, RLS, allocator, lock, retry, or sixteen-component closure | refuse the scope expansion |
| A candidate, manifest, ERRATA row, decision record, or frozen contract is rewritten to make conformance pass | refuse the scope expansion |
| Passing conformance is presented as approval to run migration 0008, create a retained selection, integrate the command, open a route/read/output, or change #192 | invalid claim with no effect |

Focused tests must exercise each authority class independently. Replacing all
paths with one temporary file or one generic marker-search test is insufficient
because it does not prove the trust-boundary split.

## 9. Non-goals

This contract, its Phase A PR, and the future conformance Phase B do not:

- create or edit migration 0008 or any SQL;
- create the deployment adapter or any database connection code;
- add a relation, column, key, trigger, RLS policy, function, role, login,
  membership, privilege, capsule, or structural verifier;
- allocate a knowledge position or write a governed batch or selection row;
- invoke a selection operation on a disposable or retained target;
- change migrations 0001 through 0007, migration authority, provisioning,
  readiness, recovery, or catalog identity;
- change tenant capability, principal resolution, current-context, or lock
  authority;
- edit a candidate schema, binding, matrix, manifest, digest, ERRATA entry,
  promotion decision, or active/frozen contract;
- promote, publish, select, or activate a RuntimeBundle;
- implement a production read-only selector or authorization provider;
- integrate `COMMIT_OPERATION_CLAIM_DRAFT`;
- add a public refusal or `RuntimeProblem` mapping;
- add a route, profile, active registry, materialization, qualification,
  current-state read, historical view, WINDOW execution, output, receipt,
  deployment, upgrade, repair, reconciliation, backfill, or hot reload;
- change legacy behavior or cross the production/legacy firewall; or
- implement or change #192.

## 10. Smallest coherent change and PR boundaries

### Phase A contract PR

The only allowed file is:

```text
docs/rfcs/OFARM_Temporal_Candidate_Conformance_Selection_Storage_Admission_RFC_v0_1.md
```

No implementation, approval claim, or other repository change may travel with
it.

### Future Phase B conformance PR

After explicit architect approval and truthful publication of this contract,
the only allowed files are:

```text
conformance/temporal_contract_candidate_check.py
kernel/tests/test_temporal_contract_governance.py
conformance/review_baseline_test_inventory.json
```

The inventory file may change only when mechanically required by a change to
the canonical collected test-node inventory, including a count or node-ID
change.

The Phase B implementation should add direct constants, one small authority
authentication step, one explicit path classifier, reuse the retained
authenticated migration snapshot, reuse the architecture import graph, and add
focused tests. Code size is a warning signal. A generalized policy engine,
plugin, configuration registry, dynamic path framework, or second migration
loader is outside scope.

No other path is permitted. If implementation requires a production,
deployment, database, migration, candidate, contract, profile, route, output,
legacy, or #192 file, work stops and proposes that boundary separately.

The later database Phase B remains the separate allowlist in the parent RFC.
It may not be stacked into the conformance PR.

## 11. Verification

### Phase A

This documentation-only contract is verified by:

```text
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --name-only origin/main...HEAD
```

The final command must name only this RFC.

### Future Phase B conformance

Minimum verification is:

```text
python3 -m pytest -q kernel/tests/test_temporal_contract_governance.py
python3 conformance/temporal_contract_candidate_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

The Phase B handoff must also show a path-scoped diff proving no change to:

```text
kernel/migrations/
deployment/postgresql/tenant_command_runtime_bundle_selection.py
deployment/postgresql/migration_sets.py
deployment/postgresql/provisioning_specs.py
deployment/postgresql/catalog_identity.py
kernel/runtime_bundle.py
kernel/runtime_bundle_repository.py
kernel/runtime_bundle_components.json
kernel/schema.sql
contracts/
ERRATA.md
governance/
profile_si_ffs/
```

Traceability is:

| Invariant | Future seam | Required proof |
| --- | --- | --- |
| TCSS-001, TCSS-006 | fixed RFC and prerequisite constants | exact bytes pass; missing, length-mismatched, and same-length digest-mismatched bytes refuse |
| TCSS-002, TCSS-003 | explicit two-path classifier | absence passes; exact future paths classify; aliases and third paths refuse |
| TCSS-004, TCSS-005 | retained authenticated migration snapshot | no second read; exact version-7 set and version-3 prefix pass; substitutions refuse |
| TCSS-007, TCSS-008 | fixed marker constants and narrow classification | no caller/configuration seam and no duplicated storage/selection semantics |
| TCSS-009, TCSS-010 | unchanged candidate and active authorities | candidate bytes unchanged; catalog and active profile mutations refuse |
| TCSS-011, TCSS-014 | existing architecture graph and fixed roots | adapter unreachable from both closures; direct or wrapped reachability refuses |
| TCSS-012, TCSS-013 | no changed runtime surface | boundary diff and package architecture checks |
| TCSS-015 | unchanged #192 authority | boundary diff and package checks |
| TCSS-016, TCSS-017 | closed Phase B allowlist | only checker, focused tests, and mechanically required inventory metadata change |

## 12. Stop conditions

Work stops before:

1. implementing conformance Phase B until the architect explicitly approves
   this exact contract and its truthful documentation record merges;
2. changing any pinned authority, exact marker, allowed path, or fixed import
   root without a reviewed amendment;
3. creating either future allowed production path in the conformance PR;
4. implementing migration 0008 until this separate conformance implementation
   merges and passes on current `main`;
5. adding a third production exception, alias, dynamic registry, environment
   switch, profile switch, second migration scan, or caller-selected path;
6. changing a candidate, manifest, ERRATA row, promotion record, lifecycle
   decision, frozen contract, active registry, RuntimeBundle, or profile;
7. changing migrations 0001 through 0007 or any previously admitted role,
   grant, function, capsule, provisioning, readiness, recovery, or catalog
   authority;
8. defining or executing storage, tenant selection, current-pointer behavior,
   runtime selection, authorization, or command integration;
9. mapping selection refusal to a public result or reason code;
10. opening a route, materialization, qualification, current-state read,
    historical view, WINDOW behavior, output, receipt, or deployment;
11. importing or changing legacy production behavior;
12. implementing or changing #192; or
13. changing a file outside the applicable Phase A or Phase B allowlist.

Each stopped item requires its own reviewed trust boundary and PR. Current-state
reads and outputs remain blocked by their separate output-governance
prerequisites.

## 13. Approval gate

This document is a proposal, not an approved contract. PR authorship, commit
authorship, branch state, review conclusions, GitHub comments or reactions,
repository credentials, mergeability, green checks, or merge do not approve it.

The designated architect must explicitly approve the exact reviewed contract
in the designated Codex task. Any later documentation record must identify the
exact approved contract bytes and approval provenance truthfully.

Approval of this Phase A contract authorizes only its documentation record. It
does not authorize conformance implementation, migration 0008, database work,
selection, runtime integration, routes, reads, outputs, deployment, or #192.
A later Phase B conformance implementation still requires a separate explicit
in-scope request after the approval record merges.
