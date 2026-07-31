# OFARM2 Temporal Candidate Conformance Model-Admission Posture — Phase A Contract v0.1

**Status:** architect-approved Phase A contract; documentation-only, pending
merge, and without implementation, lifecycle, or activation effect

**Contract identity:**
`ofarm.temporal-candidate-conformance-model-admission.issue176.v0.1`

**Date:** 2026-07-31

**Base commit:** `4322655db26645abd5da90dcfb8f7318464aedcf`

## Approval record

- Approval channel: Codex task
  `019fa821-93c9-7ef1-8c94-1c0e92ea46b9`.
- Stable approval reference:
  `codex-task:019fa821-93c9-7ef1-8c94-1c0e92ea46b9;user-message-exact-text:approved;immediately-after-final-contract-approval-request`.
- Architect action: the designated architect sent a later user-authored message
  consisting exactly of `approved` in that same task, immediately after the
  assistant returned the amended contract and stated that final review and
  explicit approval were next.
- Exact approved snapshot byte length: `25931`.
- Exact approved snapshot SHA-256:
  `sha256:fdc52f8727f4c90564feb8f6680846e663cc03138c8742fe0507e9d47a133af6`.

The approved snapshot is this contract before approval bookkeeping. Its status
was exactly:

```text
proposed Phase A contract; documentation-only, unapproved, and without
implementation, lifecycle, or activation effect
```

After that explicit user-authored approval, the assistant changed only the
status metadata to record the satisfied approval and then published the
contract. This approval-record section is evidence of that already completed
transition; it changes no decision, authority, invariant, negative case,
non-goal, PR boundary, verification requirement, or stop condition.

AI-authored text, PR authorship, branch or commit state, mergeability, GitHub
credentials, and review conclusions do not count as architect approval.

**Primary implementation ticket:** #176

**Primary trust boundary:** the temporal candidate conformance checker's
classification of inert RuntimeBundle model eligibility versus catalog,
persistence, selection, and activation

**Intended contract PR boundary:** this RFC only

**Intended future implementation PR boundary:** the temporal candidate
conformance checker, its focused conformance tests, and mechanically required
test-inventory metadata only

## Problem and goal

The temporal candidate conformance checker currently treats these four
different authorities as one blanket RuntimeBundle activation surface:

1. the in-memory RuntimeBundle model;
2. the RuntimeBundle persistence repository;
3. the RuntimeBundle SQL schema; and
4. every tenant migration.

It refuses `TEMPORAL_GOVERNANCE_ARTIFACT` text in any of them. That rule was
correct while the role was an inactive candidate vocabulary with no approved
model admission. It became too broad when the architect approved
`ofarm.temporal-governance-runtime-bundle-model-admission.issue176.v0.1`.
That contract permits a later, closed model-only admission of the role while
expressly leaving catalog, persistence, selection, activation, command,
output, legacy, and #192 authorities unchanged.

The obsolete blanket check now prevents that approved model boundary from
passing package conformance. Removing the whole check would be unsafe because
the prohibitions outside the model are still required.

This contract defines the smallest lawful replacement: the conformance
checker may treat occurrence of the role in `kernel/runtime_bundle.py` as
inert model vocabulary, while continuing to refuse the role in persistence,
database, active catalog, and the two exact active profile and capability
artifacts already inspected by the checker.

This contract does not add the role to the model. It creates no lifecycle
decision, component, bundle, selection, runtime behavior, or production
semantic effect.

## Decision

After explicit architect approval, one separate Phase B conformance PR may
replace only the checker's obsolete blanket classification.

The replacement must apply this exact posture:

| Observed posture | Conformance meaning | Required result |
| --- | --- | --- |
| The exact authorizing model-admission RFC is present and digest-valid; the role is absent from `kernel/runtime_bundle.py` and from every explicitly classified forbidden path | The prerequisite conformance change is merged before model admission | pass |
| The exact authorizing model-admission RFC is present and digest-valid; the role occurs in `kernel/runtime_bundle.py` and remains absent from every explicitly classified forbidden path | Inert model eligibility may exist; its correctness is owned by the model-admission contract and model tests | pass this posture check |
| The role occurs in `kernel/runtime_bundle_repository.py`, `kernel/schema.sql`, any checked-in `kernel/migrations/*.sql`, `kernel/runtime_bundle_components.json`, `profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json`, or `profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json` | The role crossed one of this checker's explicitly classified forbidden paths | refuse |
| The authorizing model-admission RFC is missing or its exact byte length or SHA-256 differs | The reviewed authority for the model-path exception is not present | refuse before applying the exception |

Passing the posture check means only that the checker did not mistake a
model-vocabulary occurrence for activation. It is not proof that the model
implementation is correct. It is never evidence of lifecycle currentness,
catalog membership, persistence support, tenant selection, command authority,
deployment, runtime activation, output eligibility, or current truth.

The checker must not require the role to occur in the model. This lets the
conformance prerequisite merge safely before the separately approved model
PR. Once the model PR adds the role, that PR's exact role, identity,
reservation, digest, schema, and bundle semantics remain governed and tested
under the model-admission contract.

Selection, command, route, output, legacy, and #192 authorities remain
unchanged and outside this posture check. If implementation needs to inspect
or permit the role in any such authority or in another production authority,
it must stop for a new or amended contract rather than broaden this check.

## Reviewed authority pins

This contract relies on these fixed authorities:

- approved model-admission contract:
  `ofarm.temporal-governance-runtime-bundle-model-admission.issue176.v0.1`;
- reviewed model-admission contract path:
  `docs/rfcs/OFARM_Temporal_Governance_RuntimeBundle_Model_Admission_RFC_v0_1.md`;
- exact model-admission contract byte length: `33787`;
- exact model-admission contract digest:
  `sha256:9dbe62b18f4214b93b02ae2ccd8d17ee40aed4e1925fff7482993b2eedc9fac8`;
- temporal role vocabulary: `TEMPORAL_GOVERNANCE_ARTIFACT`;
- checker path: `conformance/temporal_contract_candidate_check.py`;
- current blanket-check function:
  `validate_runtime_bundle_carrier_role_is_inactive()`; and
- existing focused test path:
  `kernel/tests/test_temporal_contract_governance.py`;
- exact active ActiveArtifactSet path:
  `profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json`;
  and
- exact active Capability Manifest path:
  `profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json`.

The model-admission contract, not this contract and not the conformance
checker, owns the role's exact three-identity allowed set, reservation rules,
canonical bytes and digests, schema relationships, component validation, and
same-bundle validation.

Any change to those model semantics requires amendment of the model-admission
authority. It must not be smuggled into the conformance checker.

## Authority map

- The approved model-admission contract owns permission for one later
  model-only implementation and its exact invariants.
- `kernel/runtime_bundle.py` owns in-memory RuntimeComponent and RuntimeBundle
  model vocabulary and validation. Under this contract it is the sole allowed
  model-eligibility exception to the old blanket role-text prohibition.
- `conformance/temporal_contract_candidate_check.py` owns package-level
  classification that distinguishes inert model eligibility from forbidden
  activation or persistence posture. It does not own model correctness.
- `kernel/tests/test_runtime_bundle.py` remains the future model-admission
  implementation's authority for focused behavioral proof. This contract does
  not change it.
- `kernel/runtime_bundle_components.json` and its publisher retain sole
  authority over active catalog membership. Candidate paths and the temporal
  role remain forbidden there.
- `kernel/runtime_bundle_repository.py`, `kernel/schema.sql`, and
  `kernel/migrations/*.sql` retain persistence and database authority. The
  temporal role remains forbidden in all of them.
- `profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json` and
  `profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json` retain the
  exact active profile and capability authority inspected here. Existing
  temporal activation-marker prohibitions remain unchanged.
- The current temporal decision log retains lifecycle currentness authority.
  The checker must not read it dynamically, reinterpret it, or create a
  decision.
- The tenant command RuntimeBundle-selection contract retains future tenant
  selection and exact command-closure authority. It remains inactive and
  production unbound.
- The governed-command contract retains future command behavior and safe
  draft-retention semantics. It remains unimplemented and production unbound.
- ADR 0002 retains temporal meanings, independent valid and knowledge axes,
  and half-open interval authority.
- #192 retains sole authority over audit-runtime behavior.

No caller, request, environment value, profile, file discovery order, newest
artifact, dynamic registry, or network source may change this authority map.

## Trust model

### Protected distinctions

This boundary protects the differences among:

- candidate creation-state attestations;
- external `GOVERNED_INACTIVE` lifecycle currentness;
- inert RuntimeBundle model eligibility;
- active catalog membership;
- database and repository persistence support;
- tenant RuntimeBundle selection;
- command integration and authorization;
- deployment and runtime activation; and
- publication, outputs, or current truth.

None of these states proves another.

### Trusted inputs

The only trusted inputs for the future checker amendment are:

- the fixed role string named by this contract;
- the exact allowed model path `kernel/runtime_bundle.py`;
- the exact forbidden paths `kernel/runtime_bundle_repository.py`,
  `kernel/schema.sql`, and `kernel/runtime_bundle_components.json`;
- every checked-in SQL file matched by the fixed
  `kernel/migrations/*.sql` authority family;
- the exact model-admission contract path, byte length, and SHA-256 pin above;
- the exact active ActiveArtifactSet path
  `profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json`;
- and the exact active Capability Manifest path
  `profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json`.

Before it permits the model-path exception, the checker must prove that the
authorizing RFC exists, has exactly `33787` bytes, and has exactly digest
`sha256:9dbe62b18f4214b93b02ae2ccd8d17ee40aed4e1925fff7482993b2eedc9fac8`.
The path, byte length, and digest are fixed constants, never caller data.

### Untrusted claims

The following are untrusted and cannot widen the allowance:

- caller-supplied paths, roles, identities, digests, or registries;
- a component or bundle claiming that it is governed, current, selected, or
  active;
- PR approval, merge state, branch names, GitHub credentials, or comments;
- environment or profile switches;
- candidate status text treated as runtime authority; and
- conformance success presented as promotion, deployment, or execution
  authority.

## State and ordering

The conformance classification is intentionally small:

```text
CHECKED_IN_PACKAGE
  -> EXACT_AUTHORIZING_RFC_PROVED
  -> EXPLICIT_AUTHORITY_PATHS_CLASSIFIED
  -> MODEL_OCCURRENCE_ALLOWED_OR_ABSENT
  -> ALL_EXPLICITLY_CLASSIFIED_FORBIDDEN_PATHS_PROVED_CLEAR
  -> CONFORMANCE_POSTURE_PASSED
```

A missing or mismatched authorizing RFC, or any role occurrence in an
explicitly classified forbidden path, transitions directly to
`CONFORMANCE_REFUSED`.

`CONFORMANCE_POSTURE_PASSED` has no outgoing transition to lifecycle,
catalog, persistence, selection, activation, command execution, output, or
truth. Those transitions do not exist in this boundary.

The required implementation order is:

1. approve and merge this Phase A contract;
2. implement and merge the separate conformance-classification Phase B PR;
3. rerun package conformance on unchanged `main` and prove it remains green;
4. rebase the preserved model-admission implementation on that merged
   prerequisite;
5. review and verify the model-admission PR only against its own approved
   contract; and
6. stop before catalog, persistence, selection, command, route, output, or
   #192 work.

The conformance implementation must not be combined with step 4.

## Invariants

- **TCMA-001 — One exact model exception.** Only
  `kernel/runtime_bundle.py` may be exempted from the old blanket
  role-occurrence prohibition, and only because role text there denotes inert
  model eligibility. The exception is path-specific and not caller supplied.
- **TCMA-002 — Absence remains valid.** The posture check passes when the
  authorizing RFC is exact and the role is absent from the model and every
  explicitly classified forbidden path. The prerequisite must be
  independently mergeable before model implementation.
- **TCMA-003 — Persistence remains closed.** The role must be refused in
  `kernel/runtime_bundle_repository.py`, `kernel/schema.sql`, and every
  checked-in `kernel/migrations/*.sql` file.
- **TCMA-004 — Catalog remains closed.** Existing refusal of the role and all
  temporal candidate paths in `kernel/runtime_bundle_components.json` remains
  unchanged.
- **TCMA-005 — Activation remains closed.** Existing temporal activation-marker
  refusals for the exact ActiveArtifactSet and Capability Manifest paths named
  above remain unchanged.
- **TCMA-006 — Checker is not a model oracle.** The checker must not duplicate,
  weaken, or replace the approved model's exact three-row identity,
  reservation, digest, schema, placement, or bundle validation. Model
  correctness stays in model code and focused model tests.
- **TCMA-007 — Candidate bytes remain immutable.** No candidate schema,
  candidate instance, manifest digest, embedded `CANDIDATE_INACTIVE`
  creation-state attestation, ERRATA row, or decision-log entry changes under
  this contract.
- **TCMA-008 — No lifecycle inference.** Model role occurrence, model validity,
  or conformance success cannot create, replace, supersede, or prove a
  lifecycle decision or currentness chain.
- **TCMA-009 — No activation inference.** Model role occurrence or conformance
  success cannot add catalog membership, persistence support, tenant
  selection, command authority, deployment, route reachability, output
  eligibility, or current truth.
- **TCMA-010 — Fail closed in the explicitly classified forbidden set.** The
  role must be refused in `kernel/runtime_bundle_repository.py`,
  `kernel/schema.sql`, every checked-in `kernel/migrations/*.sql`,
  `kernel/runtime_bundle_components.json`, the exact active ActiveArtifactSet
  path, and the exact active Capability Manifest path. Selection, command,
  route, output, legacy, and #192 authorities remain unchanged and outside
  this posture check. Any implementation need to inspect or permit the role in
  another production authority is a stop condition requiring a new or amended
  contract.
- **TCMA-011 — Production and legacy stay separate.** This change opens no
  production semantic surface and changes no legacy Store, legacy import
  closure, or profile runtime.
- **TCMA-012 — Audit stays separate.** The checker emits no #192 event,
  receipt, reason, delivery, or runtime behavior and changes no #192 authority.
- **TCMA-013 — Deterministic authority.** The allowance and forbidden paths
  are fixed in reviewed, versioned code. They are never selected from caller
  data, configuration, environment values, profiles, or filesystem discovery
  beyond the already explicit checked-in migration set.
- **TCMA-014 — Exact authorizing bytes required.** The model-path exception may
  be applied only after the checker proves the fixed model-admission RFC path,
  exact byte length `33787`, and exact SHA-256
  `9dbe62b18f4214b93b02ae2ccd8d17ee40aed4e1925fff7482993b2eedc9fac8`.
  Missing or changed authority bytes refuse before role-path classification.

## Required negative cases

The future Phase B conformance change must prove all of these cases:

| Case | Required result |
| --- | --- |
| The exact authorizing RFC is present and digest-valid; the role is absent from the model and all explicitly classified forbidden paths | pass |
| The exact authorizing RFC is present and digest-valid; the role occurs only in `kernel/runtime_bundle.py` among the classified runtime authorities | pass the posture check without claiming model correctness |
| The authorizing RFC path is missing | refuse before applying the model exception |
| The authorizing RFC has the wrong byte length | refuse before applying the model exception |
| The authorizing RFC has the expected length but different bytes and SHA-256 | refuse before applying the model exception |
| The role occurs in `kernel/runtime_bundle_repository.py` | refuse |
| The role occurs in `kernel/schema.sql` | refuse |
| The role occurs in any checked-in `kernel/migrations/*.sql` file | refuse |
| The migration authority directory is missing or its checked-in SQL set is empty | refuse |
| The role occurs in `kernel/runtime_bundle_components.json` | refuse |
| A temporal candidate path enters catalog contract schemas or components | refuse |
| A temporal activation marker enters `profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json` | refuse |
| A temporal activation marker enters `profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json` | refuse |
| A caller, environment value, profile, or dynamic registry attempts to select the model exception or forbidden path set | no such seam may exist; refuse if introduced |
| The checker tries to validate or redefine the role's three exact admitted identities | refuse the scope expansion; model tests own it |
| A candidate, ERRATA row, manifest digest, or decision-log entry is rewritten to make the check pass | refuse the scope expansion |
| A passing check is presented as promotion, currentness, catalog admission, persistence support, tenant selection, command integration, deployment, output, or truth | invalid claim with no effect |

The focused tests must distinguish the allowed model path from each forbidden
path. A single test that replaces the whole path set with one temporary file
is insufficient because it cannot prove the trust-boundary split.

## Non-goals

This contract and its future conformance implementation do not:

- add `TEMPORAL_GOVERNANCE_ARTIFACT` to the RuntimeBundle model;
- implement or retest the three-row model admission rules;
- add a component to a RuntimeBundle or require all three temporal identities;
- change a candidate schema, binding, matrix, manifest, digest, RFC, ERRATA
  row, lifecycle decision, or currentness chain;
- change `RuntimeBundleRepository`, SQL schema, migrations, database roles,
  transactions, or storage;
- change the active RuntimeBundle catalog, publisher, RuntimeBundle selection,
  profiles, ActiveArtifactSet, or capability manifest;
- implement a selector, governed command, authorization provider, route,
  materialization, current-state read, historical or WINDOW behavior, output,
  or production semantic activation;
- amend ADR 0002 or any frozen active contract;
- change legacy behavior or combine production and legacy imports; or
- implement or modify #192 behavior.

## Smallest coherent change

The Phase A PR contains only this RFC.

After explicit approval, the smallest coherent Phase B conformance PR may:

1. split the RuntimeBundle model path from the checker's role-forbidden
   persistence and database authority paths;
2. add fixed authorizing-RFC path, expected-byte-length, and expected-SHA-256
   constants and refuse missing or mismatched authority bytes before applying
   the model-path exception;
3. replace `validate_runtime_bundle_carrier_role_is_inactive()` with a focused
   posture check that allows the role to be absent from or occur in the exact
   model path while refusing it in the repository, SQL schema, and every
   migration;
4. preserve `validate_non_activation(...)` and all existing active catalog,
   ActiveArtifactSet, capability-manifest, candidate-path, and activation-marker
   refusals;
5. update the focused temporal conformance tests to prove the authorizing-RFC,
   allowed-model, and forbidden-path cases independently; and
6. mechanically regenerate test-inventory metadata only when mechanically
   required by a change to the canonical collected test-node inventory,
   including a count or node-ID change.

It must not edit the model or any other authority. Code size is a warning
signal: one explicit path classification, one focused check, and direct tests
are preferred over a generalized policy engine, registry, plugin, or dynamic
configuration surface.

## Pull request boundaries

### Phase A contract PR

Allowed file:

- `docs/rfcs/OFARM_Temporal_Candidate_Conformance_Model_Admission_RFC_v0_1.md`.

No other file may change.

### Future Phase B conformance PR

Allowed files:

- `conformance/temporal_contract_candidate_check.py`;
- `kernel/tests/test_temporal_contract_governance.py`; and
- `conformance/review_baseline_test_inventory.json` only when mechanically
  required by a change to the canonical collected test-node inventory,
  including a count or node-ID change.

The model-admission implementation remains a separate dependent PR limited by
its own approved contract. An existing preserved worktree is not permission to
combine it with this prerequisite.

## Traceability and verification

| Invariant | Owning future seam | Required proof | Verification |
| --- | --- | --- | --- |
| TCMA-001, TCMA-002 | explicit model-path classification and focused posture check | role absent passes; role in exact model path passes | focused pytest cases |
| TCMA-003, TCMA-010 | exact repository, schema, migration, catalog, ActiveArtifactSet, and Capability Manifest forbidden paths | one refusal case per exact authority type; missing and empty migration-set refusals remain | focused pytest cases |
| TCMA-004 | unchanged `validate_non_activation(...)` | role and candidate paths in catalog refuse | existing and focused pytest cases |
| TCMA-005 | unchanged checks for the exact ActiveArtifactSet and Capability Manifest paths | every existing activation marker remains absent and mutations refuse independently at both paths | temporal candidate checker and focused tests |
| TCMA-006 | unchanged model authority | conformance diff contains no three-row model validator and no model file change | boundary diff review |
| TCMA-007, TCMA-008 | unchanged candidates, manifests, ERRATA, and decision log | exact files are unchanged | boundary diff review and package check |
| TCMA-009, TCMA-011 | unchanged catalog, runtime, profiles, routes, outputs, and legacy paths | no changed file in those authorities and package architecture checks pass | package check and boundary diff |
| TCMA-012 | unchanged #192 paths | no changed #192 file or audit behavior | boundary diff and package check |
| TCMA-013 | fixed constants and explicit checked-in paths | no caller, environment, profile, registry, or network lookup seam | code review and focused tests |
| TCMA-014 | fixed authorizing-RFC path, byte length, digest, and pre-exception check | exact authority passes; missing, length-mismatched, and same-length digest-mismatched authority refuses | focused pytest cases and temporal candidate checker |

Minimum Phase B verification:

```text
python3 -m pytest -q kernel/tests/test_temporal_contract_governance.py
python3 conformance/temporal_contract_candidate_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

The Phase B handoff must also show a path-scoped diff proving no change to:

```text
kernel/runtime_bundle.py
kernel/runtime_bundle_repository.py
kernel/schema.sql
kernel/migrations/
kernel/runtime_bundle_components.json
contracts/candidates/
governance/temporal-decision-log/
profile_si_ffs/
```

The Phase A contract PR is verified by:

```text
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --name-only origin/main...HEAD
```

The final command must name only this RFC.

## Provisional-design record

Not provisional.

The pre-deployment decision-log workflow remains provisional under its own
contract, but this conformance classification is not. Model eligibility and
activation are distinct authorities. Any future attempt to merge them requires
a new versioned contract.

## Review disposition

- **Blocker:** any wording that permits the role in persistence, database,
  catalog, profile, capability, selection, command, output, legacy, or #192
  authority; requires model presence in the prerequisite; treats conformance
  as lifecycle or activation evidence; or duplicates model-admission rules.
- **Follow-up:** the separate Phase B conformance amendment, followed by the
  preserved model-admission implementation after this prerequisite merges.
- **Preference:** naming or prose changes that do not alter the authority map,
  invariants, negative cases, PR boundary, or stop conditions.

## Stop conditions

Stop and return for a new or amended Phase A contract if implementation or
review requires any of the following:

- editing `kernel/runtime_bundle.py` or changing model behavior;
- changing the exact three temporal identity rows or their validation;
- requiring role presence before the model-admission PR merges;
- weakening, removing, or failing to verify the exact authorizing
  model-admission RFC path, byte length, or digest;
- changing a candidate, manifest, digest, ERRATA row, decision log, or
  lifecycle/currentness rule;
- admitting the role to the catalog, repository, SQL schema, migration,
  publisher, profile, ActiveArtifactSet, or capability manifest;
- needing to inspect or permit the role in selection, command, route, output,
  legacy, #192, or any other production authority outside the exact classified
  path set;
- changing a command, authorization provider, route, materializer, read,
  historical/WINDOW behavior, output, or production semantic surface;
- changing a frozen active contract or ADR 0002;
- combining production and legacy behavior;
- implementing or changing #192; or
- needing any file outside the future Phase B allowlist other than mechanical
  test-inventory metadata already named above.

Approval or merge of this RFC authorizes no implementation by itself. Phase B
may begin only after the architect explicitly approves this exact contract.
