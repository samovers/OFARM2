# OFARM2 RuntimeBundle Global Content Retention Baseline-Transition Test Admission — Phase A Contract v0.1

**Contract identity:**
`ofarm.runtime-bundle-global-content-retention-baseline-transition-test-admission.issue176.v0.1`

**Decision identity:**
`ISSUE176-RUNTIME-CONTENT-RETENTION-BASELINE-TRANSITION-TESTS-001`, proposed version `1`

**Status:** proposed and inactive; Phase A only; no test implementation or
database authority

**Issue:** #176

**Reviewed base:** OFARM2 `main` at
`9b1c0a4479958f50d3d186235ae54468fc5a1ac9`

**Blocked downstream pull request:** PR #299 at the observed failing head
`2110186a2a447d24318a2af0debc812147aea3c5`

**Draft pull request:** `DRAFT_PR_TO_BE_PINNED_BEFORE_EXACT_HEAD_REVIEW`

**Primary trust boundary:** test authority for the authenticated tenant
migration-release transition from exact R8 to exact R9, including historical
V7-prefix fixtures

**Phase A review-head boundary:** this RFC only

**Maximum final pull-request path envelope:** this RFC and exactly the two test
files in section 8

## 1. Problem and goal

The merged provisioning-classifier prerequisite correctly recognizes only the
literal eight-migration release (`R8`) and the literal nine-migration release
(`R9`). It preserves the existing selection-controller projection and makes no
special migration-runner branch. Current `main` remains R8.

PR #299 lawfully adds migration 0009 inside its separate eleven-path database
boundary. At exact head `2110186a2a447d24318a2af0debc812147aea3c5`, the
retention tests and both native verifier architectures pass, but the complete
Kernel baseline reports 47 failures and 2,648 passes. All 47 failures originate
from two test-only assumptions that were true on R8 and become false on R9:

1. `kernel/tests/test_postgresql_provisioning.py` assumes the checked-out
   literal release contains exactly eight migrations before it constructs a
   controlled R9 release. Its real-current-release assertion also assumes the
   authoritative ninth row is absent.
2. `kernel/tests/test_postgresql_migration_runner.py` allows its historical V7
   fixture to slice only a seven- or eight-row checked-out release, even though
   the fixture itself still executes exactly the first seven rows.

The production classifier is not the demonstrated cause. Its exact R8/R9
recognition is already correct. The defect is that test evidence derives a
historical or controlled state from an implicit assumption about the current
repository head. This also reaches the classifier contract's GCPV-004 negative
case: an exact R9 release must not be defeated by a test helper that still
requires total length eight.

This contract admits one separate test-only prerequisite. It makes the two
fixtures state-explicit on both sides of the R8-to-R9 transition while leaving
PR #299 and every production authority unchanged.

## 2. Trust model and authority map

### 2.1 Protected assets

The protected assets are:

1. the exact production meanings of R8 and R9;
2. the exact first-eight prefix that owns the accepted V8 selection transition;
3. the exact first-seven prefix used by historical stable-V7 tests;
4. the truthfulness of malformed-release and migration-transition negative
   cases; and
5. the independence of PR #299's database boundary from this test boundary.

### 2.2 Authority map

| Decision | Sole authority | Explicitly not authority |
| --- | --- | --- |
| Literal production release | `deployment/postgresql/migration_sets.py` and the authenticated `TENANT_AUTHORITATIVE_MIGRATION_SET` | Test labels, branch names, PR state, or a controlled replacement object |
| Exact R8/R9 classification | `deployment/postgresql/provisioning.py` at reviewed Git blob `0b16131fdd964598bd64d75fc3369e642292af86` | Test helpers, caller flags, environment values, or repository credentials |
| Controlled R8 test release | Exactly the authenticated first eight rows and their eighth prefix digest | An unsliced current release or a copied migration count |
| Controlled R9 test release | The controlled R8 test release plus exactly one controlled row 9 | Appending row 9 to an already-nine-row release |
| Historical V7 runner fixture | Exactly authenticated rows 1 through 7 and the seventh prefix digest | The total checked-out release or the helper's name |
| Whether PR #299 may continue | PR #299's merged parent contracts, its own approval, exact-head review, and required gates | This prerequisite, its approval, or its merge |

The trusted production classifier, migration loader, migration runner, SQL
sources, catalog verifier, and provisioning specifications remain unchanged.
The two admitted test modules may construct evidence and assert results only;
they gain no production authority.

Treat implicit repository-state assumptions, synthetic migration objects,
fixture labels, test order, and review advice that changes production merely to
satisfy a test as untrusted. Compromised dependencies, CI, repository hosting,
or arbitrary mutation outside the admitted test process remain outside this
test-only boundary.

## 3. State and ordering

The prerequisite pull request has four valid states:

1. `PROPOSED`: only this RFC changes; no test edit is authorized.
2. `APPROVED_FOR_IMPLEMENTATION`: a valid same-task decision-card approval is
   bound to the exact draft pull request named in this RFC and the live card.
3. `DUAL_BASELINE_VERIFIED`: the exact three-path implementation passes on
   current R8 `main` and on a disposable R9 overlay of PR #299.
4. `MERGED_PREREQUISITE`: the test-only pull request is merged.

Only `PROPOSED -> APPROVED_FOR_IMPLEMENTATION -> DUAL_BASELINE_VERIFIED ->
MERGED_PREREQUISITE` is valid.

Repository ordering is:

1. review and approve this contract;
2. implement and merge this test-only prerequisite;
3. update PR #299 from the new `main` without adding either test file to PR
   #299's diff;
4. rerun PR #299's complete gates; and
5. let PR #299's separate authority determine whether it may merge.

This contract authorizes only steps 1 and 2. It neither approves nor performs
steps 3 through 5.

## 4. Invariants and acceptance criteria

- **RCBTT-001 — Separate trust boundary.** This prerequisite remains a pull
  request distinct from PR #299. The database PR retains its approved
  eleven-path envelope.
- **RCBTT-002 — Exact three-path closure.** The final prerequisite diff is a
  subset of the three exact paths in section 8. No wildcard, related-test
  family, or inventory exception is implied.
- **RCBTT-003 — Production authority unchanged.** No production classifier,
  migration loader, migration runner, migration, SQL verifier, catalog,
  provisioning specification, runtime, or conformance authority changes.
- **RCBTT-004 — Closed current-release family.** Test setup accepts the
  checked-out literal release only when it is exact R8 or exact R9. Length 7,
  length 10, a gap, reorder, wrong service, wrong version, or wrong filename
  refuses rather than selecting a fallback.
- **RCBTT-005 — Controlled R8 is explicit.** A controlled R8 object contains
  exactly authenticated rows 1 through 8 and the eighth applied-prefix digest,
  regardless of whether the checked-out release is R8 or R9.
- **RCBTT-006 — Controlled R9 is explicit.** A controlled R9 object contains
  the controlled R8 prefix plus exactly one controlled ninth row. It never
  appends a ninth row to an unsliced R9 release.
- **RCBTT-007 — Honest current-release assertion.** The existing release-family
  test requires the production helper to return row 8 for exact R8 and R9,
  return no row 9 for exact R8, and return the literal row 9 for exact R9.
  The expected result is independently derived only after the closed release
  shape is authenticated.
- **RCBTT-008 — Historical V7 remains literal.** Stable-V7 runner tests execute
  exactly rows 1 through 7 and use the seventh prefix digest. Row 8 or 9 is not
  applied merely because it exists in the checked-out release.
- **RCBTT-009 — Named negative case is reached.** Every existing malformed
  release, substitution, transition, and rollback test reaches the condition
  named by that test. A stale total-count assertion may not mask it.
- **RCBTT-010 — Canonical node inventory unchanged.** No test function name,
  parameter ID, or collected node ID changes. The canonical inventory file is
  not edited.
- **RCBTT-011 — Dual-baseline proof.** The affected modules and complete
  applicable baseline pass on exact R8 `main` and in a disposable overlay on
  exact R9 PR #299.
- **RCBTT-012 — No authority transfer.** Approval, passing tests, or merge of
  this prerequisite does not approve, activate, update, or merge PR #299.
- **RCBTT-013 — Disposable evidence only.** PostgreSQL verification uses only
  disposable targets and retains no content, tenant state, selection, bundle,
  role, or database.

## 5. Required negative cases

| Invariant | Counterexample | Required result |
| --- | --- | --- |
| RCBTT-001, RCBTT-002 | Either test file is committed directly to PR #299, or a fourth path enters this prerequisite | Stop and preserve separate pull requests |
| RCBTT-003 | A failing fixture is addressed by editing `provisioning.py`, `migration_runner.py`, migration 0009, or a catalog verifier | Stop for the owning production boundary |
| RCBTT-004 | The checked-out release has 7, 10, duplicate, reordered, wrong-service, wrong-version, or wrong-filename rows | Test setup refuses before constructing controlled evidence |
| RCBTT-005 | Controlled R8 retains the unsliced ninth row when run on PR #299 | Test fails; controlled R8 must be exactly eight rows |
| RCBTT-006 | Controlled R9 appends a synthetic row to the unsliced R9 set and produces ten rows | Test fails before classifier invocation |
| RCBTT-007 | Exact R9 is classified while the test still requires the authoritative ninth helper to return `None` | Current-release assertion fails as stale |
| RCBTT-008 | A stable-V7 helper passes the complete R8 or R9 set to the runner | Exact ledger and prefix assertions fail |
| RCBTT-009 | A malformed-row test fails first at `assert len(...) == 8` | The fixture is incomplete; the named negative case must be restored |
| RCBTT-010 | A test is renamed, parametrized differently, added, or removed | Stop; do not regenerate inventory in this boundary |
| RCBTT-011 | Tests pass on R8 but fail on the disposable R9 overlay, or vice versa | Do not merge the prerequisite |
| RCBTT-012 | This decision is cited as authority to merge PR #299 | Refuse; PR #299 remains separately governed |
| RCBTT-013 | A verification target survives the test run | Remove the disposable target and fail the boundary evidence |

## 6. Smallest coherent change

After valid approval, `kernel/tests/test_postgresql_provisioning.py` may make
only these test-evidence corrections:

1. authenticate that the checked-out authority is exact R8 or R9;
2. derive a controlled R8 view from exactly its first eight authenticated rows;
3. construct controlled R9 from that R8 view plus one controlled ninth row;
4. make the existing real-current-release assertion closed over exact R8 and
   exact R9; and
5. preserve every existing test function name, parameter, production call,
   negative outcome, and assertion meaning.

After valid approval, `kernel/tests/test_postgresql_migration_runner.py` may
change only its historical V7 fixture setup so it authenticates an exact R8 or
R9 checked-out family, slices exactly rows 1 through 7, and binds the seventh
prefix digest before running existing tests.

No generic release builder, compatibility framework, future-version fallback,
production hook, environment switch, or duplicate classifier is permitted.
Changing two local fixture seams is smaller and clearer than weakening
production authority or preserving current-state assumptions with aliases.

Code-size warning: the implementation should be a small net change. If it
requires broad helper families, new tests, copied migration literals, or
production edits, the design has failed and work stops.

## 7. Non-goals and provisional posture

This contract does not:

- add, edit, execute, or approve migration 0009;
- change content retention, digest validation, replay, ownership, ACL,
  transaction, catalog, or provisioning semantics;
- retain content, publish or seal a RuntimeBundle, choose a tenant, create a
  selection, or claim current/default truth;
- add a command, route, runtime integration, materialization, read, historical
  or window execution, output, deployment, legacy behavior, or #192 behavior;
- change the production semantic surface or production-versus-legacy firewall;
- accept migration 10 or an unspecified future release;
- weaken a negative assertion, change test inventory, or hide a production
  defect behind test-only branching; or
- amend an accepted or frozen contract in place.

The fixture design is **not provisional**. Explicit R8, R9, and V7-prefix test
states remain correct after the transition. The task-message approval evidence
is provisional pre-deployment evidence and must be replaced by independently
human-controlled, independently verifiable approval or signing before
deployment.

## 8. Pull-request boundary

### 8.1 Exact final allowlist

| Exact path | Permitted reason |
| --- | --- |
| `docs/rfcs/OFARM_RuntimeBundle_Global_Content_Retention_Baseline_Transition_Test_Admission_RFC_v0_1.md` | This Phase A contract, truthful approval status, and compact approval evidence only |
| `kernel/tests/test_postgresql_provisioning.py` | Remove implicit R8-current assumptions from controlled and current-release classifier evidence only |
| `kernel/tests/test_postgresql_migration_runner.py` | Make the historical V7 helper slice the exact seven-row prefix from only an authenticated R8/R9 current family |

No other path is permitted. In particular,
`conformance/review_baseline_test_inventory.json` is outside the allowlist
because RCBTT-010 forbids collected-node changes.

### 8.2 Governing dependencies

This contract depends on, but does not amend:

- `ofarm.runtime-bundle-global-content-retention-admission.issue176.v0.1`,
  38,116 bytes,
  `sha256:aa5de04c08390e1439d59f39c4b6f5608e8b43b320fec531721d9c53b936873a`;
- `ofarm.runtime-bundle-global-content-retention-catalog-anchor-test-allowlist-amendment.issue176.v0.2`,
  19,491 bytes,
  `sha256:b126e49f6c86bfe6bdac81480c6af6ed9c719d9abecbcd13535a7aa326e8e9a3`;
  and
- `ofarm.runtime-bundle-global-content-retention-provisioning-classifier-admission.issue176.v0.1`,
  27,497 bytes,
  `sha256:5661b264525e31df6c8b0b17cc9566862a2219daf10e003d8d6f25593e9f2804`.

The reviewed base test blobs are:

- `kernel/tests/test_postgresql_provisioning.py`:
  `f65ef4160b867ff44bfc80685dbcb7015f0d0e06`; and
- `kernel/tests/test_postgresql_migration_runner.py`:
  `9387b7bfcac9ab2a1b63a5d9aa1e502b238d2330`.

If either test blob or the production classifier blob changes before Phase B,
work stops for exact-head assessment. A semantics-preserving rebase may proceed
only when these decisions and the three-path closure remain unchanged.

## 9. Traceability and verification

| Invariant | Owning seam | Verification |
| --- | --- | --- |
| RCBTT-001, RCBTT-002, RCBTT-012 | Git diff and separate PR metadata | Mechanical three-path check; confirm PR #299 contains neither test path |
| RCBTT-003 | Absence of production paths | Exact diff inspection and package contract check |
| RCBTT-004–RCBTT-007 | Existing provisioning test helpers and test bodies | Complete provisioning test module on exact R8 and disposable R9 |
| RCBTT-008, RCBTT-009 | Existing V7 migration-runner helper and negative tests | Complete migration-runner test module on disposable PostgreSQL targets in both baselines |
| RCBTT-010 | Canonical collected-node comparison | Before/after node-ID equality; inventory path absent from diff |
| RCBTT-011 | Dual-baseline execution | Complete applicable Kernel baseline on current `main` and PR #299 overlay |
| RCBTT-013 | Disposable target lifecycle | Explicit cleanup and absence check after each PostgreSQL run |

Required Phase A verification is:

1. this RFC is the sole changed path;
2. `python3 conformance/ofarm_pkg_contract_check.py` passes;
3. `git diff --check` passes; and
4. exact-head review finds no demonstrated decision-level Blocker.

After approval, Phase B verification must include:

1. exact three-path diff and technical-allowlist subset checks;
2. unchanged collected node IDs and no inventory diff;
3. lint or formatting checks for both admitted Python files;
4. the complete provisioning and migration-runner test modules on disposable
   PostgreSQL targets against R8 `main`;
5. the same test-only diff and complete affected modules in a disposable
   overlay of PR #299's exact R9 head;
6. the complete applicable Kernel baseline in both states;
7. package, architecture, migration-release, and ordinary hosted conformance
   gates; and
8. exact-head review, compact PR scope report, live approval recheck, and no
   later cancellation immediately before merge.

Passing evidence is not database approval, runtime activation, output, current
truth, or deployment.

## 10. Open decisions and review disposition

Open decisions: none. The design deliberately accepts only the two already
governed current-release shapes, R8 and R9, and preserves exact historical
prefixes. It does not pre-decide R10.

Initial review disposition:

- **Blocker:** exact-head Phase A review and explicit task-user approval are
  still required.
- **Follow-up:** after this prerequisite merges, PR #299 may be updated from
  `main` and reverified only under its own approved contracts.
- **Preference:** none.

## 11. Approval workflow and stop conditions

This proposal creates no test implementation or merge authority. PR authorship,
commit authorship, review, CI, repository credentials, generic approval, or PR
#299's existing approval cannot approve this separate boundary.

Before a live card is shown:

1. the draft pull request placeholder in this RFC must be replaced by the exact
   already-created draft PR reference;
2. the Phase A head must contain only this RFC;
3. the exact head must be reviewed; and
4. every demonstrated Phase A Blocker must be resolved.

The complete live decision card must use this exact approval sentence:

```text
I approve OFARM2 decision ISSUE176-RUNTIME-CONTENT-RETENTION-BASELINE-TRANSITION-TESTS-001 version 1.
```

Only the entire visible text of a later user-authored message in the same Codex
task may approve it. After valid approval, the same named pull request may
change only section 8's three paths, run section 9 verification, address
in-boundary Blockers, post the required compact scope report, and merge after
every gate passes. That standing authority never transfers to PR #299.

Work stops before:

1. editing either test file before valid approval;
2. changing a path outside section 8;
3. changing a collected node ID or the canonical inventory;
4. changing production, migration, database, catalog, provisioning, runtime,
   conformance, route, output, deployment, legacy, or #192 authority;
5. accepting R10, adding a fallback, or adding caller- or environment-selected
   release posture;
6. weakening a negative assertion instead of restoring its named path;
7. retaining a PostgreSQL target or any content, selection, bundle, or tenant
   state;
8. adding either test file to PR #299;
9. treating this decision as authority to update or merge PR #299;
10. continuing when either reviewed test blob or the production classifier
    changes incompatibly; or
11. merging without dual-baseline evidence, exact-head review, live approval,
    the scope report, every required green gate, and an absence-of-cancellation
    check.

Once this contract is approved and every bounded acceptance criterion passes,
this prerequisite may merge under the accepted pre-deployment workflow. It
does not authorize another boundary.
