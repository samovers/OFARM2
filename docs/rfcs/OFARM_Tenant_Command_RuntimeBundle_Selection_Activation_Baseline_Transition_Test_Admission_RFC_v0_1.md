# OFARM2 Tenant Command RuntimeBundle Selection Activation Baseline-Transition Test Admission — Phase A Contract v0.1

**Contract identity:**
`ofarm.tenant-command-runtime-bundle-selection-activation-baseline-transition-test-admission.issue176.v0.1`

**Decision identity:**
`ISSUE176-SELECTION-ACTIVATION-BASELINE-TRANSITION-TESTS-001`, proposed version `1`

**Status:** proposed and inactive; Phase A documentation only; not approved

**Issue:** #176

**Reviewed base:** OFARM2 `main` at
`a098527b8970b490a256e3da6d72fcd886135366`

**Blocked implementation PR:** #292 at the observed failing head
`7f0b0cd08ff6c1912a5aa6eadae6595aec61865a`

**Primary trust boundary:** verification evidence for the repository's
selection-storage transition from the exact V7/ABSENT baseline to the exact
V8/CLASSIFIED baseline

**Phase A review-head boundary:** this RFC only

**Maximum final pull-request path envelope:** this RFC and exactly two test
files named in section 11

## 1. Problem and goal

PR #292 lawfully changes the tenant selection-storage production authority
from the exact seven-migration absent state to the exact eight-migration
classified state. Its focused tests and both native verifiers pass, but the
complete Kernel baseline fails because two older test modules build synthetic
V7 and V8 cases from the repository's current migration set and current
catalog source. Those fixtures worked while the repository itself was V7 and
the adapter was absent. Once PR #292 makes V8 and the adapter current, the
fixtures accidentally append a synthetic eighth migration to an already
eight-migration set, use V8 catalog bytes in cases labelled V7, or run a V8
migration in helpers labelled V7. The intended negative assertion is then
masked by an earlier duplicate-function, incomplete-pair, or invalid-state
failure.

The observed result was 58 failures and 2,520 passes in the complete Kernel
baseline. The production SQL path was not the demonstrated cause. Changing
production loading to conceal V8 from tests would make authority
context-sensitive and is forbidden.

This contract establishes durable, state-explicit test fixtures that preserve
the exact meaning of V7/ABSENT and V8/CLASSIFIED before and after the real
repository transition. It creates a separate prerequisite pull request so PR
#292 keeps its approved eleven-path database boundary.

It does not approve PR #292, database Phase B, or any production behavior.

## 2. Learning value

The change proves that the accepted selection-storage conformance model can be
tested across its real `CONFORMANT_ABSENT` to `CONFORMANT_CLASSIFIED`
transition without deriving a synthetic state's meaning from the repository's
current state. It reduces the demonstrated risk that a negative test passes or
fails for the wrong reason after an authorized authority transition.

## 3. Non-goals

This boundary does not:

- change a migration, migration-set literal, catalog identity, provisioning
  verifier, conformance checker, source-snapshot implementation, or adapter;
- change the database Phase B design or widen PR #292's eleven-path allowlist;
- create, activate, read, retain, reconcile, or upgrade a tenant selection;
- change RuntimeBundle selection, profiles, commands, routes,
  materialization, qualification, current-state reads, historical or window
  behavior, outputs, deployment, legacy behavior, or #192;
- weaken or reorder production verification so an old test can pass;
- accept multiple production authorities, add a fallback, or make production
  behavior aware of a test environment;
- change canonical collected test node IDs or the canonical inventory; or
- amend an approved or frozen contract in place.

## 4. Trust model

### 4.1 Protected assets

The protected assets are:

1. the exact seven-row tenant migration prefix and its V7 digest;
2. the exact meaning of `CONFORMANT_ABSENT`: seven authenticated migrations,
   no selection-storage adapter, and the exact V7 catalog source;
3. the exact meaning of `CONFORMANT_CLASSIFIED`: the same seven-row prefix,
   one authenticated eighth migration, and the matching adapter;
4. the negative-case ordering that makes each test reach the condition named
   by that test; and
5. the truthfulness of the complete Kernel baseline before and after the real
   V8 transition.

### 4.2 Trusted components

The following existing components remain trusted and unchanged:

- `conformance/temporal_contract_candidate_check.py` owns selection-storage
  classification and refusal semantics;
- `deployment/postgresql/migration_sets.py` owns production migration-set
  identities;
- `deployment/postgresql/catalog_identity.py` owns the production catalog
  verifier literal;
- `deployment/postgresql/migration_runner.py` and
  `deployment/postgresql/provisioning.py` own production migration and
  structural verification behavior; and
- the normal Python, PostgreSQL, package, architecture, and native CI gates own
  mechanical execution evidence.

The two admitted test modules are trusted only to construct test evidence and
assert outcomes. They gain no production authority.

### 4.3 Untrusted inputs and actors

Treat as untrusted:

- a test helper's implicit assumption about the repository's current state;
- synthetic migration bytes, catalog bytes, import graphs, source snapshots,
  roles, and function shapes supplied by a negative test;
- test order, another test's database residue, and a caller-supplied label such
  as `V7`, `ABSENT`, or `CLASSIFIED`; and
- review advice that would change production behavior merely to satisfy a
  fixture.

### 4.4 Excluded attacker capabilities

Arbitrary in-process mutation outside the existing tests, compromised Python
or PostgreSQL dependencies, filesystem mutation during a trusted read,
compromised CI, operator compromise, repository-host compromise, and source
substitution outside the reviewed diff remain outside this test-only boundary.
Production code already owns its applicable refusal model; this contract does
not restate or weaken it.

## 5. Authority map

| Decision | Sole authority | Explicitly not authority |
| --- | --- | --- |
| Production migration state | Authenticated production migration set and its accepted literals | Test names, fixture labels, branch names, or repository credentials |
| Production selection-storage classification | `conformance/temporal_contract_candidate_check.py` | A new helper, a copied state string, or test order |
| Synthetic V7 test state | An explicit seven-row fixture built from the authenticated V7 prefix and exact V7 source pins | The unsliced current migration set or current catalog bytes |
| Synthetic V8 test state | The explicit V7 fixture plus exactly one controlled eighth migration and one matching adapter source | Appending to an unknown or already-V8 current set |
| Stable-V7 PostgreSQL target | A migration set containing exactly rows 1 through 7 and its prefix digest | A helper name or a full set that may contain row 8 |
| Expected result of the current-repository smoke case | An independent closed pair observation: exact V7 plus no adapter, or exact V8 plus adapter | Assuming the current repository is always absent or always classified |
| Whether PR #292 may merge | PR #292's own approved contract, live approval, exact-head review, and required gates | This prerequisite contract or its merge |

There is no legacy fallback, duplicate production state, alias, or alternate
write path added by this contract.

## 6. State machine and ordering

### 6.1 Test-evidence states

The prerequisite pull request has these states:

1. `PROPOSED`: only this RFC exists; no test change is authorized.
2. `APPROVED_FOR_IMPLEMENTATION`: a valid live decision-card approval names
   this pull request and exact maximum envelope.
3. `DUAL_STATE_TEST_READY`: both test modules construct explicit state and pass
   against the real V7/ABSENT base and a disposable PR-#292 V8/CLASSIFIED
   overlay.
4. `MERGED_PREREQUISITE`: the test-only pull request is merged.

Only `PROPOSED -> APPROVED_FOR_IMPLEMENTATION -> DUAL_STATE_TEST_READY ->
MERGED_PREREQUISITE` is valid. Merge without approval or without both-baseline
evidence is forbidden.

### 6.2 Repository transition ordering

The repository-level order is:

1. merge this test-only prerequisite while production remains V7/ABSENT;
2. update PR #292 from the new `main` without adding these test files to PR
   #292's diff;
3. run PR #292's full required verification against V8/CLASSIFIED; and
4. let PR #292's own authority determine whether it may merge.

This contract neither performs nor authorizes step 2, 3, or 4.

### 6.3 Validation before effects

Every helper must construct and authenticate the requested synthetic state
before invoking the behavior under test. A V7-labelled helper must never apply
row 8. A V8-labelled helper must first hold an exact seven-row prefix and must
add exactly one controlled row 8. A mixed or unrecognized pair must refuse
before the intended downstream assertion is evaluated.

All PostgreSQL verification uses disposable targets. No retained database
state is an effect of this contract.

## 7. Invariants and acceptance criteria

- **BTT-001 — Separate evidence boundary.** The prerequisite pull request is
  distinct from PR #292. PR #292 retains exactly its approved eleven-path
  database implementation diff.
- **BTT-002 — Closed path envelope.** The prerequisite pull request changes
  only the three exact paths in section 11. No wildcard or related-test family
  is implied.
- **BTT-003 — Production authorities unchanged.** No production,
  conformance, migration, catalog, provisioning, runtime, contract registry,
  route, output, legacy, or #192 authority changes.
- **BTT-004 — Exact V7 fixture.** A test case labelled V7 or ABSENT uses
  exactly migration rows 1 through 7, the exact V7 prefix digest, no adapter,
  and the exact V7 catalog source identity. It does not consume the unsliced
  current migration set or unnormalized current catalog source.
- **BTT-005 — Exact V8 fixture.** A test case labelled V8 or CLASSIFIED starts
  from the exact V7 fixture and adds exactly one controlled row 8 and one
  matching adapter source. It never appends row 8 to an already-eight-row set.
- **BTT-006 — Honest current-state smoke case.** The one test that inspects the
  real repository accepts only the two closed pairs V7/no-adapter and
  V8/adapter, independently derives the expected state from that pair, and
  requires the production checker to return the same state. A partial pair,
  another migration count, or another checker result fails. The same existing
  collected test node exercises a controlled partial pair and requires
  refusal; this adds no test function or parameter ID. Its historical name,
  `test_selection_storage_current_state_is_exact_absent`, is retained solely
  to preserve the canonical node ID and is not semantic authority for the
  expected current state.
- **BTT-007 — Named negative path is reached.** Existing negative tests still
  reach and assert their named refusal. They may not pass because an earlier
  incomplete-pair, invalid-state, catalog-pin, or duplicate-function error
  masks the intended condition.
- **BTT-008 — Stable-V7 database target is literal.** The PostgreSQL helper
  used by stable-V7 tests migrates only the exact seven-row prefix and returns
  that same prefix to its caller. Its ledger remains exactly `(7, 7)` before a
  controlled V8-transition test starts.
- **BTT-009 — No test inventory churn.** Existing test function names,
  parameter IDs, and collected node IDs remain unchanged. The canonical
  inventory is not regenerated in this boundary. No new test function or
  parametrized case is permitted; new helper logic must remain uncollected.
- **BTT-010 — Dual-baseline proof.** The admitted test modules and the complete
  applicable baseline pass once against current V7/ABSENT `main` and once in a
  disposable overlay of the same test change onto PR #292's exact
  V8/CLASSIFIED head.
- **BTT-011 — No compatibility shim.** Production code does not branch on
  tests, release labels, environment variables, call stacks, or repository
  state to emulate V7 after V8 becomes current.
- **BTT-012 — No authorization transfer.** Passing or merging this
  prerequisite does not approve, activate, or merge PR #292 and does not
  create a tenant selection.

## 8. Negative cases

| Invariant | Counterexample that must fail or stop |
| --- | --- |
| BTT-001 | The two test files are committed directly to PR #292, producing a twelfth path. |
| BTT-002 | A reviewer requests a change to `conformance/temporal_contract_candidate_check.py` in the prerequisite PR. |
| BTT-003 | A test failure is addressed by changing migration loading, catalog observation, or the production classifier. |
| BTT-004 | An ABSENT fixture calls the current authority loader after V8 and receives eight migrations, or reads the V8 catalog source unchanged. |
| BTT-005 | A CLASSIFIED fixture appends a synthetic row 8 to the current eight-row set and produces nine rows. |
| BTT-006 | A controlled row-8/no-adapter pair exercised inside the existing current-state test node reports ABSENT or CLASSIFIED instead of refusing. |
| BTT-007 | An initializer-import test expects `initializer imports` but receives `implementation pair is incomplete`; changing the regex alone is forbidden. |
| BTT-008 | A helper named `advance_to_v7` passes a full eight-row set to the migration runner and creates the real activation function. |
| BTT-009 | Renaming a test or adding a parameter changes a canonical node ID and would require inventory regeneration. |
| BTT-010 | Tests pass on current main but the disposable PR-#292 overlay still reports duplicate functions or invalid selection-storage state. |
| BTT-011 | Production loading checks `PYTEST_CURRENT_TEST`, a release suffix, or call-stack identity to hide row 8. |
| BTT-012 | This prerequisite's merge is treated as permission to merge PR #292 despite a failed gate or lost approval evidence. |

## 9. Proposed architecture and smallest coherent change

### 9.1 State-explicit conformance fixtures

`kernel/tests/test_temporal_contract_governance.py` will own small test-only
builders for:

- an exact V7 authority view obtained by selecting and authenticating only the
  first seven migrations;
- an exact synthetic V8 authority obtained only from that V7 view plus one
  controlled eighth migration;
- an ABSENT source snapshot containing no adapter and the exact V7 catalog
  bytes, even when the checked-out repository contains the equal-length V8
  catalog literal; and
- a CLASSIFIED source snapshot containing the controlled adapter source.

The builders must validate their own closed state. They may normalize the
single known equal-length V7/V8 catalog digest literal in test evidence, then
must prove the resulting bytes match the already-pinned V7 source identity.
They may not invent a second production catalog authority or relax the
production source pin.

The zero-node-ID rule is a structural implementation constraint: this boundary
may change existing test bodies and add only uncollected helper logic. It may
not add or rename a test function or add a parametrized case.

Synthetic negative cases will choose a state explicitly. The existing
`test_selection_storage_current_state_is_exact_absent` node keeps that
historical name only for inventory stability. Its body compares an
independently observed closed pair with the real classifier result and also
exercises one controlled partial pair that must refuse. Keeping the name does
not assert that the post-transition repository remains absent.

### 9.2 Literal stable-V7 PostgreSQL fixture

`kernel/tests/test_postgresql_migration_runner.py` will make its
stable-V7 helper construct a `MigrationSet` from exactly the first seven rows,
use the exact seven-row prefix digest, migrate only that set, and return that
same set. Controlled V8 tests may then add their own eighth source to the exact
prefix. No production runner behavior changes.

### 9.3 Why this is the minimum coherent design

Changing only expected error messages would preserve masked failures.
Changing production loading would weaken authority. Adding broad fixtures or a
compatibility framework would exceed the demonstrated problem. Two local,
state-explicit test-fixture corrections solve every observed failure class
while preserving the production and conformance authorities unchanged.

## 10. Elegance audit

- Production sources of truth introduced: **zero**.
- Production transition points introduced: **zero**.
- Test-state authorities: one explicit V7 builder and one V8 builder derived
  from it.
- Duplicated production fields: **none**; test literals are authenticated
  fixtures, not executable authority.
- Compatibility surfaces introduced: **none** in production.
- New abstraction used only once: **none required** beyond local fixture
  helpers.
- Deletion: implicit current-repository assumptions are removed from synthetic
  cases.
- Rewrite judgment: a focused fixture rewrite is clearer and smaller than
  preserving the current helpers with conditional patches.

## 11. Pull-request boundary

### 11.1 Primary boundary

The pull request changes only verification evidence for the V7/ABSENT to
V8/CLASSIFIED selection-storage transition. It does not alter authority.

### 11.2 Exact final allowlist

| Exact path | Permitted reason |
| --- | --- |
| `docs/rfcs/OFARM_Tenant_Command_RuntimeBundle_Selection_Activation_Baseline_Transition_Test_Admission_RFC_v0_1.md` | Phase A contract and compact approval/scope evidence required by the pre-deployment workflow. |
| `kernel/tests/test_postgresql_migration_runner.py` | Make the stable-V7 fixture apply and return the literal seven-row prefix. |
| `kernel/tests/test_temporal_contract_governance.py` | Make ABSENT and CLASSIFIED fixtures state-explicit and preserve the real-current-state smoke check. |

No other path is permitted. In particular,
`conformance/review_baseline_test_inventory.json` is outside the allowlist
because BTT-009 forbids collected-node changes.

### 11.3 Dependencies and sequence

This contract depends on, but does not amend:

- `ofarm.tenant-command-runtime-bundle-selection-activation-admission.issue176.v0.1`,
  52,382 bytes,
  `sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb`;
- `ofarm.tenant-command-runtime-bundle-selection-activation-test-allowlist-amendment.issue176.v0.2`,
  19,048 bytes,
  `sha256:83c396da78d4b3b7b7249b57552da35e54390882d793b46bb4126423978862df`;
  and
- `ofarm.temporal-candidate-conformance-selection-storage-source-snapshot-amendment.issue176.v0.2`,
  93,049 bytes,
  `sha256:820516d40956b6ea2a158413aea32a305aa078f20816ae35b257eb28491e5867`.

PR #292 is a downstream verification target, not this pull request's base and
not part of its diff.

Reviewers must not require a production fix, a conformance-checker change,
runtime integration, database activation, inventory regeneration, or #192
work from this pull request.

Follow-ups: resume PR #292 only after this prerequisite merges and its branch
is updated from `main` under PR #292's own authority.

## 12. Provisional design record

Not provisional. State-explicit fixtures remain correct on either side of the
transition and are simpler than fixtures that inherit current repository
state.

## 13. Traceability and verification

| Invariant | Owning implementation | Negative evidence | Required verification |
| --- | --- | --- | --- |
| BTT-001, BTT-002 | Git diff and exact allowlist | Any fourth path or change appearing in PR #292 | Mechanical changed-path check against both PRs |
| BTT-003, BTT-011 | No production file in diff | Production or conformance source changed to satisfy tests | Diff inspection and package conformance |
| BTT-004 | Conformance-test V7 authority and ABSENT snapshot builders | Current V8 set/catalog leaks into ABSENT fixture | Existing ABSENT negative cases reach their named refusals |
| BTT-005 | Conformance-test synthetic V8 builder | Nine-row set or duplicate adapter | Existing CLASSIFIED cases use exactly eight rows and one adapter |
| BTT-006 | Existing current-state test body and uncollected pair helper | Controlled partial pair or classifier disagreement | The same collected node refuses the partial pair and passes on the current V7 base and disposable V8 overlay |
| BTT-007 | Existing negative tests | Earlier error masks named assertion | Run the complete conformance-governance test module |
| BTT-008 | Migration-runner stable-V7 helper | Real row 8/function appears before controlled transition | Disposable PostgreSQL migration-runner tests and exact `(7, 7)` ledger assertion |
| BTT-009 | Existing test names and parameters | Canonical collected node IDs change | Compare collected node IDs before and after; inventory file remains untouched |
| BTT-010 | Dual-baseline execution | Either V7 or V8 overlay fails | Complete applicable Kernel/package gates on both states |
| BTT-012 | Workflow and PR separation | Prerequisite merge treated as database approval | Recheck PR #292 independently; no selection retained |

Focused verification after approval must include:

1. exact three-path diff and unchanged canonical collected node IDs;
2. formatting/lint for the two admitted Python test files;
3. the complete `test_temporal_contract_governance.py` module;
4. the affected migration-runner tests on a disposable PostgreSQL target;
5. `python3 conformance/ofarm_pkg_contract_check.py`;
6. the repository's complete applicable Kernel baseline on current
   V7/ABSENT `main`;
7. the same admitted test change applied without retention in a disposable
   worktree at PR #292 head, followed by the complete applicable
   V8/CLASSIFIED baseline; and
8. normal hosted conformance and review gates for the prerequisite pull
   request.

No test may leave a retained tenant selection or retained database target.

## 14. Open decisions and review disposition

Open decisions: none. BTT-009 selects node-ID preservation, so the historical
`is_exact_absent` test name is knowingly retained while its state-independent
body becomes authoritative test evidence. BTT-006 assigns the partial-pair
refusal to that same existing node. No new test or parameter may be collected.
The demonstrated failures identify exactly two stale test-fixture owners, and
the accepted stop condition forbids changing production or conformance
authority instead.

Review disposition at the proposed Phase A head:

- **Blocker:** the contract has not yet been reviewed and explicitly approved.
- **Follow-up:** PR #292 remains blocked until this prerequisite merges and its
  full gates pass on the updated base.
- **Preferences:** none.

## 15. Approval and implementation workflow

This proposed contract creates no implementation authority. PR authorship,
commit authorship, branch state, review conclusions, CI, repository
credentials, generic approval, or merging another pull request do not approve
it.

Under the accepted pre-deployment AI-assisted workflow:

1. the Phase A review head contains only this RFC;
2. review resolves every demonstrated Phase A Blocker;
3. the AI presents one complete live decision card in the designated Codex
   task naming the already-created draft pull request and the three-path
   maximum envelope;
4. a later user-authored message in the same task may approve only with:

   `I approve OFARM2 decision ISSUE176-SELECTION-ACTIVATION-BASELINE-TRANSITION-TESTS-001 version 1.`

5. after valid approval, the same pull request may implement only sections 9
   and 11, run section 13 verification, address in-boundary Blockers, and merge
   when every gate passes; and
6. PR #292 remains separately governed.

## 16. Stop conditions

Work stops before:

1. editing either test file until this exact Phase A contract is reviewed and
   the live decision is explicitly approved;
2. changing any path outside section 11;
3. changing a collected test node ID or regenerating the canonical inventory;
4. changing production, conformance, migration, catalog, provisioning,
   runtime, route, command, output, deployment, legacy, or #192 behavior;
5. adding a production compatibility shim or weakening a negative assertion
   to accept the wrong refusal;
6. retaining a test database or tenant selection;
7. adding these two test paths to PR #292's implementation diff;
8. treating this prerequisite as approval or merge authority for PR #292; or
9. continuing if dual-baseline evidence cannot be produced inside this closed
   three-path boundary.

Once this contract's acceptance criteria pass and no demonstrated Blocker
remains, the prerequisite pull request may merge under its live approved
decision. New ideas and optional hardening are Follow-ups and do not expand
this boundary.
