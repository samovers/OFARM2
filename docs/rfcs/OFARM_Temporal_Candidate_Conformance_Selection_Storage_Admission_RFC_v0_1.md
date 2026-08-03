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
conformance PR may add one new closed production-reference classifier for the
tenant selection binding.

The current checker does not have a repository-wide selection-marker scan. It
asserts the candidate binding's immutable creation-state stop strings and
checks isolation of `kernel.temporal_carriers`. Phase B adds the classifier
defined here. It does not rewrite the candidate's historical stop strings or
pretend to narrow a scanner that does not yet exist.

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
AUTHORITY_UNPROVED ------------------------------------> REFUSED
AUTHORITY_PROVED + EXACT V7 + BOTH PATHS ABSENT ------> CONFORMANT_ABSENT
AUTHORITY_PROVED + EXACT V7 PREFIX + EXACT V8 PAIR ---> CONFORMANT_CLASSIFIED
AUTHORITY_PROVED + ONLY ONE PATH PRESENT ------------> REFUSED
AUTHORITY_PROVED + ANY OTHER PRODUCTION USE ----------> REFUSED
```

Neither conformant state has a transition to publication, selection,
activation, command execution, current truth, or output.

## 2. Why this is one boundary

The temporal checker currently authenticates the inactive candidate package,
asserts its fixed creation-state stop strings, classifies the inert
RuntimeBundle model role, preserves the exact migration-0004 persistence
exception, and checks one carrier-selector module's import isolation. It does
not yet inventory production Python sources or classify tenant selection
markers across them.

Migration 0008 and its administrator-only adapter need a new fail-closed
classifier before they can lawfully appear. A broad or import-closure-only
classifier would let a dormant copy leak into deployment code, runtime,
profiles, routes, active registries, or legacy code without being noticed.

One conformance PR may therefore authenticate its own complete merged
authority, the approved parent, the existing migration-0004 persistence
authority, and the three merged custody prerequisites; build the exact source
inventories in section 5; declare the two-path exception; preserve the existing
forbidden authorities; and test that classification. It may not create either
allowed path or change any database, storage, runtime, candidate, or lifecycle
authority.

## 3. Trust model and protected distinction

The protected distinction is:

```text
reviewed reference eligibility != implemented storage != retained selection
!= runtime selection != command authority != current truth
```

### Trusted inputs

The future checker may trust only:

- this contract's complete merged path, contract identity, byte length, and
  SHA-256, pinned in Phase B after the approval-record PR merges;
- the exact fixed prerequisite paths, byte lengths, and SHA-256 values in
  section 4;
- the one authenticated tenant `MigrationSet` already loaded by the temporal
  checker from the fixed production migration authority;
- one retained Python source inventory returned by
  `conformance.rewrite_architecture_check._module_sources(PACKAGE_ROOT)`;
- the exact two allowed production paths in section 5;
- the exact two allowed selection markers in section 1;
- the fixed production and legacy import roots owned by
  `conformance/rewrite_architecture_check.py`;
- the exact active catalog, ActiveArtifactSet, and Capability Manifest paths
  already inspected by the temporal checker;
- the exact non-production authority classes in section 5.2; and
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

The future exception is unavailable unless its own merged authority and every
applicable fixed prerequisite below are present and exact.

### 4.1 Complete merged self-authority

The conformance Phase B must first authenticate this contract's complete
merged file at the exact RFC path named above. Phase B constants must pin:

- contract identity;
- exact path;
- complete merged-file byte length; and
- complete merged-file SHA-256.

Those complete-file values are established only after the architect-approved
status and truthful approval appendix merge under section 13. The approved
pre-publication design digest cannot substitute for the complete merged-file
identity. Missing, altered, multiply resolved, or inexact self-authority
refuses before any selection marker or path is classified.

### 4.2 Accepted architecture and temporal law

- architecture report:
  `reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md`,
  `96406` bytes,
  `sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256`;
- ADR 0001: `docs/adr/0001-tenancy-and-schema-migrations.md`, `147112`
  bytes,
  `sha256:bc49e566ddbdf98868162aa7ccca0940fa76fca1bfaaa261c8c831dbb5515a4d`;
- ADR 0002: `docs/adr/0002-valid-time-and-knowledge-time.md`, `61427`
  bytes,
  `sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796`;
  and
- ADR 0003: `docs/adr/0003-tenant-capability-trust-and-binder.md`, `93419`
  bytes,
  `sha256:b188f4d60e46887fde4231e73bb00adb9bd70b75e807627e8a3906389a0fa5be`.

### 4.3 Parent activation-admission authority

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

### 4.4 Exact selection package

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

### 4.5 Existing migration-0004 persistence authority

The existing persistence exception remains load-bearing and unchanged:

- persistence-admission contract:
  `docs/rfcs/OFARM_Temporal_Governance_Production_RuntimeBundle_Persistence_Admission_RFC_v0_1.md`;
- persistence-admission byte length: `37254`;
- persistence-admission SHA-256:
  `sha256:40a20c5053857664cfbb2d6ac2814c6136125eb9908635495af9377e9d9f0870`;
- exact migration filename:
  `0004_temporal_governance_runtime_bundle_role.sql`;
- migration byte length: `6464`; and
- migration SHA-256:
  `sha256:0c51948be7cebf2c1523d472ca44a57e32942bd358124e126ccaf2bad248ecc8`.

The future classifier must preserve the current check that authenticates this
RFC before allowing `TEMPORAL_GOVERNANCE_ARTIFACT` in exact migration 0004.
It may not remove, weaken, duplicate, or reinterpret that exception.

### 4.6 Merged custody prerequisites

| Boundary | Complete RFC identity | Merged implementation identity |
| --- | --- | --- |
| Selection-control tenant binding | `docs/rfcs/OFARM_Tenant_Binding_Selection_Control_Admission_RFC_v0_1.md`; `32169` bytes; `sha256:c1d02969811be0d5b02bdae158cb48e5d8148356ca9d4bac956c8861d529c37a` | head `79b2769e80fa530e19b642f0f7b3972fb331b338`; merge `c3adb8e47a01690920c539de9c54fb18c581cdaa` |
| Current-context selection-owner admission | `docs/rfcs/OFARM_Tenant_Current_Context_Selection_Owner_Admission_RFC_v0_1.md`; `50383` bytes; `sha256:af85e259230b69edeba80ddc2eea2f070a601fd3888fd463ce595f9cc446b13d` | head `2694465e81ba0e646c663c5a769ccd6afe3505eb`; merge `a1a2ae2249b3578f1479d8a979eb84d5aab7c331` |
| Tenant-write-lock selection-owner admission | `docs/rfcs/OFARM_Tenant_Write_Lock_Selection_Owner_Admission_RFC_v0_1.md`; `45758` bytes; `sha256:5745ad4b8b588be2b5a1b64b4b84aa757b23f8d2de00ca59e71de8ea304f51b0` | head `568b3a1db58fb97e61fdf5a22c4abd2adc6a15e6`; merge `d7d5f99e5677add8616510af4690cee210d75548` |

Commit identities are review provenance. Exact current source and catalog
identities below remain the executable integrity authority; a commit identity
alone never permits the exception.

### 4.7 Exact V7 prefix and two lawful conformance states

- stable tenant migration prefix through migration 0003:
  `sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0`;
- immutable migration prefix through version `7`:
  `sha256:5616797d1362c55c78175126edab29cc3e88c021ba0709e3766d3196d2b0126b`;
- migration 0005: `8545` bytes,
  `sha256:fde66e835f8c4456d7404eb00b99292e267f573f8b126f781f3ed55bd5e8df9a`;
- migration 0006: `8655` bytes,
  `sha256:a61c668a2bae04026b8413385f8bc1b5fd43f08f8d5281501ff766a57d552b48`;
- migration 0007: `7936` bytes,
  `sha256:cf8594b6c456953004912722b168d6bdda7c6dbfc903ba8099b018e2f270dff7`;
- tenant provisioning-spec digest, required in both lawful states:
  `sha256:2ac8487b64d4fb09d7576ef1ee09ac1f2a3cc5b20558f0d2137620b897c7157c`;
- V7 absent-state final tenant structural-verifier digest:
  `sha256:fcc0e96b4520ffe51ddb5537df24040e4d5948a22b3c387351346cc588e87ee5`;
- V7 absent-state external tenant catalog-verifier digest:
  `sha256:026bb61026a9f752fc8dde84bca0e3cbbab374d0ac8f0ba942a72654e44f5f1a`.

The two lawful database-source states are exact.

`CONFORMANT_ABSENT` requires:

1. the authoritative tenant migration set contains exactly contiguous
   versions 1 through 7;
2. the full-set digest and `prefix_digest(7)` both equal
   `sha256:5616797d1362c55c78175126edab29cc3e88c021ba0709e3766d3196d2b0126b`;
3. migrations 1 through 7 are byte-exact, including the exact migration 0004
   persistence exception and migrations 0005 through 0007 above;
4. the provisioning, final structural-verifier, and external catalog-verifier
   digests equal the exact V7 absent-state values above; and
5. migration 0008 and the adapter are both absent.

`CONFORMANT_CLASSIFIED` requires:

1. the authoritative tenant migration set contains exactly contiguous
   versions 1 through 8;
2. `prefix_digest(7)` still equals exact
   `sha256:5616797d1362c55c78175126edab29cc3e88c021ba0709e3766d3196d2b0126b`
   and migrations 1 through 7 remain byte-exact;
3. authenticated entry 8 has the exact reserved filename and supplies its
   source only through the retained authenticated snapshot;
4. the adapter is present as the exact regular, non-symlink file defined in
   section 5;
5. both implementation paths contain both exact selection markers and all
   other production authorities remain clear; and
6. the provisioning-spec digest remains exact
   `sha256:2ac8487b64d4fb09d7576ef1ee09ac1f2a3cc5b20558f0d2137620b897c7157c`.

Migration 0008 necessarily advances the complete migration-set digest and the
final structural verifier. The database Phase B also updates the external
catalog-verifier digest. This contract cannot predeclare those future values
without fabricating future implementation bytes. Their exact V8 identities,
live PostgreSQL evidence, and mutual agreement remain owned and tested by the
parent-authorized database Phase B. The old V7 structural and external catalog
digests are mandatory only in `CONFORMANT_ABSENT`; they are not silently treated
as current V8 values.

The conformance Phase B must merge while `CONFORMANT_ABSENT` is exact. After it
merges, only the transition to exact `CONFORMANT_CLASSIFIED` is admitted.
Any other prerequisite change requires a truthful contract amendment. A later
database change outside the parent's approved allowlist also stops; a passing
classifier cannot legalize it.

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

The two paths are a pair. Both absent is the only pre-implementation state;
both present and exact is the only implemented classification state; exactly
one present refuses.

### 5.2 Exact classifier inventories

The classifier evaluates four closed inventories.

**SQL production inventory.** Use only the one retained authenticated tenant
`MigrationSet` and each retained `Migration.source_bytes`. Do not glob the
migration directory again, reread a migration path after authentication, or
trust a filename found only on disk.

**Python source inventory.** Call exactly once:

```text
conformance.rewrite_architecture_check._module_sources(PACKAGE_ROOT)
```

Retain that one mapping for marker classification and import-graph
construction. Every returned Python path is production-classified for marker
purposes except:

- the exact checker path
  `conformance/temporal_contract_candidate_check.py`; and
- the fixed verification family under `kernel/tests/`.

The exact adapter remains production-classified even though it is an
administrator control module. Any selection marker in any other returned
non-test Python source refuses, whether the module is reachable, dormant,
imported, or copied.

**Active non-Python inventory.** Inspect only the three existing active
authorities already named by fixed path:

```text
kernel/runtime_bundle_components.json
profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json
profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json
```

**Non-production authority classes.** The only existing non-production
marker-bearing paths are:

```text
ERRATA.md
contracts/candidates/temporal_runtime_bundle_selection/OFARM_TenantCommandRuntimeBundleSelectionBinding_schema_v0_1.json
contracts/candidates/temporal_runtime_bundle_selection/OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json
docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_RFC_v0_1.md
docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_Activation_Admission_RFC_v0_1.md
docs/rfcs/OFARM_Temporal_Candidate_Conformance_Selection_Storage_Admission_RFC_v0_1.md
conformance/temporal_contract_candidate_check.py
kernel/tests/**
```

These paths carry candidate governance, authorizing law, conformance
constants, or synthetic verification. Their marker occurrences never satisfy
the implementation pair and never become production selection authority.
Adding another non-production class or marker-bearing governance path requires
a reviewed amendment; the classifier does not discover exemptions from file
contents.

### 5.3 Per-path marker and filesystem rules

In `CONFORMANT_CLASSIFIED`, each of the two authorized paths must contain both
the exact binding identity and its exact canonical digest. One marker without
the other refuses.

The migration occurrence is allowed only when:

1. the retained authenticated entry has version `8`;
2. its filename is exactly
   `0008_tenant_command_runtime_bundle_selection.sql`;
3. it is the eighth contiguous member of the same authenticated tenant set;
4. its source comes only from retained authenticated `Migration.source_bytes`;
   and
5. no other authenticated tenant migration contains either marker.

Version-8 source digest, byte length, applied-prefix digest, final structural
identity, and external catalog identity remain owned by the later database
Phase B. This conformance contract does not guess their values or validate the
migration's database semantics.

The adapter occurrence is allowed only in the exact fixed bytes at:

```text
deployment/postgresql/tenant_command_runtime_bundle_selection.py
```

That path must be a regular file and must not be a symbolic link. A symlink,
alias, renamed file, copied file, or second Python path carrying either marker
refuses. The checker must test the path without resolving an alternate path
into eligibility.

### 5.4 Adapter isolation

The adapter must remain outside both fixed import closures:

```text
production roots = kernel.api, kernel.application_runtime
legacy roots     = kernel.legacy_m1.api, kernel.legacy_m1.runtime
```

The import graph must be built from the same retained Python source inventory
used for marker classification. The adapter must never be imported or
re-exported from `deployment/postgresql/__init__.py`. That deliberate omission
is the mechanism that keeps this module outside the package's existing
production closure; package convention is not authority to add the re-export.
The parent database Phase B does not allow `deployment/postgresql/__init__.py`
to change.

Any import of the adapter from either closure refuses. A route, application,
worker, profile runtime, or legacy module cannot become an allowed reference
by re-exporting or wrapping the adapter.

The conformance checker proves only fixed-path presence, regular-file posture,
marker classification, and import isolation. It does not duplicate the parent
contract's exact binding validation, sixteen-component closure,
tenant-binding, SQL transaction, or activation semantics. Those belong to the
later database implementation and its focused tests.

### 5.5 Authorities and operational material that remain closed

Existing checks must continue to refuse the selection markers, candidate
paths, or temporal activation markers as applicable in:

- `kernel/runtime_bundle_components.json`;
- `profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json`;
- `profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json`;
- every authenticated tenant migration other than exact migration 0008;
- every production-classified Python source other than the exact adapter,
  regardless of reachability;
- every module reachable from the fixed production or legacy import roots,
  including the adapter if an import or re-export makes it reachable; and
- any newly proposed active catalog, profile, route, selector, command,
  materializer, read, output, or #192 authority.

The last item is a stop condition, not permission for dynamic filesystem
discovery. If a new active authority must be classified, its exact path and
meaning require a reviewed contract amendment.

The conformance PR must also prove from its exact changed-file boundary and
focused evidence that it introduces no checked-in operational selection row,
tenant capability, target-tenant choice, selected RuntimeBundle instance,
credential, secret, or retained test fixture. Focused tests may use only
obviously synthetic values created in temporary paths or at test runtime.
Synthetic values and checker constants never satisfy the production pair.

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
- The complete merged identity of this RFC owns permission for the exact
  static classification exception. The pre-publication design digest alone is
  insufficient.
- The existing RuntimeBundle persistence-admission RFC and authenticated
  migration 0004 retain their exact role-persistence exception. This contract
  does not amend it.
- The three merged admission boundaries in section 4 own only their exact
  control-login binding and owner-consumer grants. This contract neither
  widens nor reopens them.
- `deployment/postgresql/migration_sets.py` and its authenticated
  `MigrationSet` own production migration membership and bytes.
- `conformance/temporal_contract_candidate_check.py` owns the static
  production-reference classification defined here. It does not own selection
  semantics or database correctness.
- `conformance/rewrite_architecture_check.py` owns the fixed production and
  legacy import roots and the one Python source inventory used for marker and
  isolation proof. This contract does not edit that authority.
- The candidate schema and binding own the fixed selection vocabulary and
  remain governed inactive and production unbound.
- The future migration 0008 will own storage, RLS, the closed owner-executed
  function, allocator branch, and controller execute grant only after its
  separate database Phase B is explicitly requested and implemented.
- The future administrator adapter will own fixed local validation and one
  already-bound control transaction under that same later boundary. It is
  intentionally absent from `deployment/postgresql/__init__.py` and both
  runtime import closures.
- ActiveArtifactSet, Capability Manifest, profiles, routes, runtime catalog,
  current-state reads, historical/window execution, materialization, and
  outputs retain their existing closed authorities.
- `kernel/schema.sql`, `kernel/store.py`, and
  `kernel/runtime_bundle_repository.py` remain quarantined legacy-M1
  authorities and are not dependencies of this exception.
- #192 retains sole authority over audit-runtime behavior.

## 7. Invariants

- **TCSS-001 — Exact authority first.** No selection-storage exception is
  available until this complete merged RFC, the parent, the persistence
  authority, and all three custody RFC bytes are exact.
- **TCSS-002 — Two production paths only.** Only exact authenticated migration
  0008 and the exact deployment adapter may carry the two reviewed selection
  markers as production references.
- **TCSS-003 — Absence is conformant.** The conformance prerequisite passes
  before either future production path exists. One present without the other
  refuses; the implemented state requires the complete pair.
- **TCSS-004 — One SQL and one Python snapshot.** Migration classification uses
  one retained authenticated `MigrationSet`; Python classification and import
  isolation use one retained `_module_sources(PACKAGE_ROOT)` result. No second
  scan or read creates authority.
- **TCSS-005 — Stable prefixes.** The authenticated knowledge-storage prefix
  through migration 0003 remains the candidate's fixed knowledge prerequisite.
  The exact prefix through migration 0007 remains fixed when the complete set
  later advances to 8.
- **TCSS-006 — Prior exceptions and admissions remain exact.** The
  migration-0004 persistence authority, migrations 0005 through 0007, and
  their final V7 grants and structure are not amended by this boundary.
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
- **TCSS-011 — Python universe and isolation remain closed.** Every
  production-classified Python source other than the exact adapter refuses
  either marker. The regular, non-symlink adapter is absent from
  `deployment/postgresql/__init__.py` and unreachable from both fixed import
  closures.
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
- **TCSS-018 — No checked-in operational material.** The conformance boundary
  introduces no selection row, tenant capability, target-tenant choice,
  selected bundle instance, credential, secret, or retained fixture. Tests use
  synthetic temporary values only.
- **TCSS-019 — Byte-closed approval and publication.** Approval binds the exact
  canonical design bytes in the fixed Codex task; publication changes only
  truthful status metadata and adds one complete approval appendix; Phase B
  authenticates the complete merged RFC.

## 8. Required negative cases

The future Phase B conformance implementation must prove:

| Case | Required result |
| --- | --- |
| The complete merged self-authority is missing, length-mismatched, digest-mismatched, substituted, or multiply resolved | refuse before classifying paths |
| Exact V7 migration, provisioning, structural, and external catalog authorities are present and both future paths are absent | pass `CONFORMANT_ABSENT` |
| Exactly one of the two future paths is present | refuse the incomplete implementation pair |
| Both future paths are absent and a prerequisite RFC is missing | refuse before classifying paths |
| A prerequisite RFC has the wrong byte length | refuse before classifying paths |
| A prerequisite RFC has the expected length but different bytes or SHA-256 | refuse before classifying paths |
| The persistence-admission RFC or migration 0004 identity differs | refuse without weakening the existing exception |
| The selection schema or binding file, file digest, canonical length, or canonical digest differs | refuse |
| The absent state is not the exact contiguous version-7 set and exact V7 catalog baseline | refuse |
| The stable version-3 prefix differs | refuse |
| The version-7 prefix differs in either state | refuse |
| Exact authenticated migration 0008 and the exact isolated adapter are later present and each contains both exact markers | pass `CONFORMANT_CLASSIFIED` only |
| A file named like migration 0008 exists but is absent from the authenticated migration set | refuse; filesystem presence has no authority |
| The authenticated version-8 filename differs by any byte | refuse |
| The markers occur in an authenticated migration other than exact 0008 | refuse |
| Only one of the two markers occurs in either authorized path | refuse |
| The adapter is absent from `deployment/postgresql/__init__.py`, outside both import closures, and paired with exact authenticated migration 0008 | pass this classification only |
| The adapter is not a regular file or is renamed, copied, selected through a symlink, or loaded from another path | refuse |
| `deployment/postgresql/__init__.py` imports or re-exports the adapter | refuse |
| The exact adapter becomes reachable from a production import root | refuse |
| The exact adapter becomes reachable from a legacy import root | refuse |
| A dormant non-test Python module outside either import closure copies either marker | refuse from the retained source inventory |
| A production or legacy wrapper copies either marker without importing the adapter | refuse from the retained source inventory |
| A second Python source scan differs from the retained inventory | refuse the design; no second scan is permitted |
| A marker or candidate path enters the active runtime catalog | refuse |
| A temporal activation marker enters the ActiveArtifactSet | refuse |
| A temporal activation marker enters the Capability Manifest | refuse |
| A conformance change adds an operational selection row, tenant capability, target tenant, selected bundle instance, credential, secret, or retained fixture | refuse; synthetic temporary evidence only |
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

This draft PR is the review vehicle. Before approval it may change only:

```text
docs/rfcs/OFARM_Temporal_Candidate_Conformance_Selection_Storage_Admission_RFC_v0_1.md
```

No implementation, approval claim, or other repository change may travel with
the unapproved design. After final review and exact architect approval under
section 13, the same one-file PR may make only the truthful status transition
and add the one complete approval appendix. It must not merge before those
publication differences are exact.

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

The Phase B implementation legitimately requires:

1. direct constants and byte authentication for this complete merged RFC and
   every prerequisite;
2. the existing one retained authenticated migration snapshot;
3. one retained repository Python-source inventory from the existing
   architecture helper;
4. exact absent/classified state checks and regular-file/symlink checks;
5. per-path two-marker classification across the SQL and Python inventories;
6. the import graph built from that same Python inventory;
7. unchanged active non-Python checks; and
8. focused tests for every authority class and the no-operational-material
   rule.

Code size remains a warning signal, not a target. This explicit machinery is
required proof, not permission for a generalized policy engine, plugin,
configuration registry, dynamic path framework, repository-wide exemption
discovery, or second migration/Python loader.

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
| TCSS-001, TCSS-019 | complete merged self-authority and fixed prerequisite constants | exact bytes pass; missing, length-mismatched, same-length digest-mismatched, substituted, or multiply resolved bytes refuse |
| TCSS-002, TCSS-003 | explicit two-path and state classifier | exact V7 absence passes; exact V8 pair classifies; partial pair, aliases, symlinks, and third paths refuse |
| TCSS-004, TCSS-005 | retained authenticated migration and Python snapshots | no second read or scan; exact version-3 and version-7 prefixes pass; substitutions refuse |
| TCSS-006 | existing persistence and custody checks | persistence RFC, migration 0004, and migrations 0005 through 0007 remain exact in both states |
| TCSS-007, TCSS-008 | fixed marker constants and narrow classification | no caller/configuration seam and no duplicated storage/selection semantics |
| TCSS-009, TCSS-010 | unchanged candidate and active authorities | candidate bytes unchanged; catalog and active profile mutations refuse |
| TCSS-011, TCSS-014 | one retained Python inventory, existing architecture graph, and fixed roots | dormant copies refuse; `__init__.py` re-export refuses; adapter is regular/non-symlink and unreachable from both closures |
| TCSS-012, TCSS-013 | no changed runtime surface | boundary diff and package architecture checks |
| TCSS-015 | unchanged #192 authority | boundary diff and package checks |
| TCSS-016, TCSS-017 | closed Phase B allowlist | only checker, focused tests, and mechanically required inventory metadata change |
| TCSS-018 | exact changed-file boundary and synthetic focused evidence | no operational row, capability, tenant choice, selected instance, credential, secret, or retained fixture is checked in |

## 12. Stop conditions

Work stops before:

1. implementing conformance Phase B until the architect explicitly approves
   this exact contract and its truthful documentation record merges;
2. failing to authenticate the complete merged self-authority or changing any
   pinned authority, exact marker, allowed path, inventory class, or fixed
   import root outside the exact V7-to-V8 transition in section 4.7;
3. creating either future allowed production path in the conformance PR;
4. implementing migration 0008 until this separate conformance implementation
   merges and passes on current `main`;
5. adding a third production exception, alias, dynamic registry, environment
   switch, profile switch, second migration or Python scan, caller-selected
   path, or adapter import/re-export from `deployment/postgresql/__init__.py`;
6. changing a candidate, manifest, ERRATA row, promotion record, lifecycle
   decision, frozen contract, active registry, RuntimeBundle, or profile;
7. changing migrations 0001 through 0007 or any previously admitted role,
   grant, function, capsule, provisioning, readiness, recovery, or catalog
   authority; the parent-owned V8 final structural and external catalog
   identities are the only stated later transition and remain outside this
   conformance implementation;
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

## 13. Byte-authenticated approval, publication, and merge stop

This document is a proposal, not an approved contract. PR authorship, commit
authorship, branch state, review conclusions, GitHub comments or reactions,
repository credentials, mergeability, green checks, or merge do not approve it.

### 13.1 Canonical design and live decision card

The canonical design bytes:

- are UTF-8;
- use LF line endings;
- begin with this document's first `#`;
- end after the merge-stop rule at the end of section 13.5; and
- contain exactly one terminal LF.

After all review blockers are closed and before approval is solicited, one
complete live decision card must be displayed in Codex task
`019fa821-93c9-7ef1-8c94-1c0e92ea46b9`. It must state:

- this exact contract identity, intended path, and reviewed base;
- the canonical design byte length and SHA-256;
- its own canonical byte length and SHA-256;
- the exact approval sentence;
- the approval sentence's UTF-8 byte length and SHA-256, with no terminal LF
  included in the sentence identity;
- every exact prerequisite identity in sections 4.2 through 4.7;
- the one permitted effect and every non-effect;
- the preservation rules; and
- the next required sequence.

Canonical decision-card extraction begins with
`OFARM2 COMPLETE LIVE DECISION CARD` and ends with
`END OF OFARM2 COMPLETE LIVE DECISION CARD`, with no terminal LF in the card
identity.

The current draft does not self-declare an unstable byte identity. Its exact
canonical design length and SHA-256 are computed only after the final reviewed
wording is fixed, then displayed in the complete live card and preserved in
the approval appendix.

### 13.2 Human approval authority

The designated architect must send the exact approval sentence from that live
card as a later user-authored message in the same Codex task. Typing it or
copying it directly from that complete live card is valid.

An approval sentence or card digest copied from another task, another card,
another decision, documentation, a template, a PR, GitHub, or AI-authored or
AI-sent text other than the complete live decision card displayed earlier in
the same task is invalid. AI-generated messages, repository credentials, PR
authorship, review, comment, reaction, merge, or generic approval never count.

The exact user-authored message is the architect's decision. The repository
appendix is evidence of that decision, not a substitute for it.

### 13.3 Permitted publication differences and appendix

Only after the exact later user-authored approval message exists may this draft
review PR become the documentation-only approval record. It must preserve the
approved decision, trust model, authority pins, classifier inventories, state
model, authority map, invariants, negative cases, non-goals, verification,
file boundaries, stop conditions, and merge-stop rule byte-for-byte.

Only two publication differences from the approved design bytes are allowed:

1. status metadata may change from proposed and unapproved to
   architect-approved; and
2. one truthful `Appendix A — Architect approval record` may be added.

The appendix must record:

- contract identity, intended path, and reviewed base;
- canonical approved-design encoding, byte length, and SHA-256;
- every prerequisite identity in sections 4.2 through 4.7;
- Codex task identifier;
- decision-card turn and stable message reference;
- decision-card extraction rule, canonical byte length, and SHA-256;
- architect user-message turn, stable reference, and timestamp;
- exact user-authored approval sentence, canonical byte length, and SHA-256;
- review evidence references;
- the single permitted effect;
- every non-effect;
- preservation rules; and
- the next required sequence.

If approval changes any protected design text, the design returns to review as
a new exact byte identity and a new complete live card is required.

### 13.4 Effects, non-effects, and next sequence

The approval's only permitted effect is to make the exact canonical Phase A
design architect-approved and authorize its one-file documentation approval
record.

Approval does not authorize conformance implementation, a checker change,
migration 0008, the adapter, database storage or mutation, a role or grant,
selection, RuntimeBundle or profile activation, runtime integration,
`COMMIT_OPERATION_CLAIM_DRAFT`, authorization, routes, materialization,
qualification, current-state reads, historical or WINDOW execution, outputs,
receipts, deployment, legacy behavior, or #192.

After the truthful approval-record PR merges:

1. compute the complete merged RFC byte length and SHA-256;
2. require a separate explicit in-scope request for conformance Phase B;
3. make Phase B authenticate that complete merged identity before applying the
   exception;
4. implement and merge only the closed conformance allowlist in section 10;
5. rerun conformance on current `main`; and
6. stop before the separately authorized database Phase B.

Before deployment, this provisional Codex approval workflow must be replaced
by independently human-controlled and independently verifiable signing or
approval.

### 13.5 Merge-stop rule

This PR must not merge while the contract is proposed or unapproved. The
documentation-only approval record must not merge unless its sole changed path
is this intended RFC, its only differences from the approved canonical design
bytes are the truthful status transition and one complete approval appendix,
and every recorded byte identity, prerequisite, review reference, decision
card reference, and architect user-message reference verifies exactly.
