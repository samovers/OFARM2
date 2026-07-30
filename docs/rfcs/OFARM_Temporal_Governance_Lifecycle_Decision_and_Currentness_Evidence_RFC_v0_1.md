# OFARM Temporal-Governance Lifecycle Evidence — Phase A Contract v0.1

**Status:** draft for review; documentation-only; no lifecycle effect

**Contract identity:**
`ofarm.temporal-governance-lifecycle-evidence.issue176-foundation.v0.1`

**Primary implementation ticket:** #176

**Primary trust boundary:** custody and precedence of lifecycle-decision
evidence for three exact temporal-governance identities

**Promotion-contract dependency:**
`ofarm.temporal-governance-promotion.issue176-foundation.v0.1`,
`sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0`

**Reserved decision-carrier version:**
`ofarm.temporal-governance-promotion-decision.v0.1`

**Reserved currentness-trace version:**
`ofarm.temporal-governance-currentness-trace.v0.1`

**Subject repository review basis:** `samovers/OFARM2` commit
`6d41de1fff50f652688f582fd88a5bd8fed9b92a`

**PR boundary:** this RFC only

## Decision

OFARM2 may recognize the three exact issue #176 temporal-governance
identities as `GOVERNED_INACTIVE` only from two separate, matching records:

1. an explicit human promotion decision; and
2. an exact currentness trace establishing that decision as the effective
   lifecycle head.

Neither record may originate in the OFARM2 implementation repository.
Canonical lifecycle authority must be recorded in `samovers/OFARM`. OFARM2
may later consume only a digest-pinned, byte-identical extraction from that
canonical authority under a separately approved extraction boundary.

The fixed canonical authority locations for version 0.1 are:

```text
decision:
  02_accepted_rfcs/OFARM_OFARM2_Temporal_Governance_Promotion_Decision_v0_1.md

currentness trace:
  03_machine_contracts/OFARM2_TEMPORAL_GOVERNANCE_CURRENTNESS_v0_1.json
```

The decision path is the human-governed disposition. The currentness path is
the machine-readable lifecycle-head control map. Neither path substitutes for
the other. Their repository, paths, contract identity, subject identities,
and required fields are fixed by this reviewed contract, never by caller
data.

This RFC does not create either canonical record, amend canonical OFARM
authority, extract either record into OFARM2, or issue a promotion decision.
Until both exact records exist and pass their future governed verification,
all three identities remain effectively `CANDIDATE_INACTIVE`.

## Problem

The approved temporal-governance promotion contract fixes the only lawful
subject set and the only positive outcome, but deliberately does not define
decision storage or currentness-trace storage.

OFARM2 is an implementation and conformance package. Its repository
instructions state that it does not promote contracts or change currentness.
Changing a package manifest entry, merging a pull request, or passing
conformance therefore cannot lawfully establish `GOVERNED_INACTIVE`.

This contract closes only the missing authority-location, record-shape,
precedence, and fail-closed relationship needed before a promotion decision
can be proposed.

## Closed subject set

Version 0.1 governs exactly these subjects:

1. `ofarm.temporal-carrier-matrix.adr0002.v0.1`
   - schema version: `ofarm.temporal-carrier-matrix.v0.1`
   - subject directory: `contracts/candidates/temporal_coordinate/`
   - subject filename:
     `OFARM_TemporalCarrierMatrix_ADR0002_candidate_v0_1.json`
   - repository-file digest:
     `sha256:7cb26513b5abdbcadecaf6f9b47d874a742ba8fa05a332c9130deebe449d7fc6`
   - canonicalization: `OFARM_CANONICAL_JSON_V1`
   - canonical byte length: `9504`
   - canonical content digest:
     `sha256:c404c0cd1e08f389664b5381c2c038cf65bac9a3b725fc2b1882990636eb179b`
2. `ofarm.temporal-carrier-selection.intervention.v0.1`
   - schema version: `ofarm.temporal-carrier-selection-binding.v0.1`
   - subject directory:
     `contracts/candidates/temporal_carrier_selection/`
   - subject filename:
     `OFARM_InterventionValidTimeCarrierSelection_candidate_v0_1.json`
   - repository-file digest:
     `sha256:9886aace0670b6a83f17cd33cbc67aa62fafcfd0ea873faed9194c2aaa07efe5`
   - canonicalization: `OFARM_CANONICAL_JSON_V1`
   - canonical byte length: `1814`
   - canonical content digest:
     `sha256:373a5f402ad077039946c1dfe7b972e4382d3c6a6805fbf0b271e4a0bc729bf1`
3. `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1`
   - schema version: `ofarm.temporal-governed-command-binding.v0.1`
   - subject directory: `contracts/candidates/temporal_governed_command/`
   - subject filename:
     `OFARM_OperationClaimDraftTemporalCommand_candidate_v0_1.json`
   - repository-file digest:
     `sha256:0909ec653cb99a94cd1b35afaf2d386258aac671c5f730960ed485df8a4b8f2e`
   - canonicalization: `OFARM_CANONICAL_JSON_V1`
   - canonical byte length: `9614`
   - canonical content digest:
     `sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1`

The decision and currentness records must repeat the exact ordered set. The
order is evidence of dependency:

```text
carrier matrix
  -> intervention carrier-selection binding
  -> operation-claim draft temporal-command binding
```

No schema, RuntimeBundle carrier binding, tenant RuntimeBundle-selection
binding, temporal-coordinate vocabulary, other carrier row, other command,
alias, successor, or future version is admitted.

## Canonical promotion decision

The canonical accepted decision must contain one machine-readable canonical
JSON block with exactly these authority-bearing fields:

```text
decisionVersion
promotionDecisionRef
canonicalization
promotionContractIdentity
promotionContractRepositoryFileDigest
subjectRepository
subjectRepositoryCommit
subjects
outcome
humanPromotionAuthorityRef
decidedAt
reviewEvidenceRefs
currentnessTraceRef
activationAssertions
```

Their meanings are:

- `decisionVersion` is exactly
  `ofarm.temporal-governance-promotion-decision.v0.1`.
- `promotionDecisionRef` is globally unique and immutable.
- `canonicalization` is exactly `OFARM_CANONICAL_JSON_V1`.
- `promotionContractIdentity` and
  `promotionContractRepositoryFileDigest` bind the merged promotion contract.
- `subjectRepository` is exactly `samovers/OFARM2`.
- `subjectRepositoryCommit` is exactly
  `6d41de1fff50f652688f582fd88a5bd8fed9b92a`. It retains all three exact
  reviewed files and cannot select newer bytes.
- `subjects` repeats the exact atomic set, paths, schema versions,
  repository-file digests, canonicalization, canonical lengths, and
  canonical content digests from the promotion contract.
- `outcome` is exactly `PROMOTE_GOVERNED_INACTIVE` or `REFUSE_PROMOTION`.
- `humanPromotionAuthorityRef` refers to the separately governed human
  promotion authority that issued the disposition.
- `decidedAt` records the decision time. It never selects currentness.
- `reviewEvidenceRefs` identify the reviewed contract, subject, conformance,
  and approval evidence.
- `currentnessTraceRef` is the exact identity expected at the fixed canonical
  currentness path.
- `activationAssertions` states that the decision creates no current/default,
  active, production, RuntimeBundle, route, command, read, output, or
  deployment status.

The decision document must expose the canonical JSON block digest and its
canonical byte length under `OFARM_CANONICAL_JSON_V1`. Prose cannot override
the block.

This contract does not define credentials, signing, steward membership, or
principal resolution for `humanPromotionAuthorityRef`. A positive decision
must not be issued until that authority-verification boundary is separately
approved.

## Canonical currentness trace

The currentness control map must contain exactly one trace for this contract
version with these authority-bearing fields:

```text
traceVersion
currentnessTraceRef
canonicalization
promotionContractIdentity
promotionDecisionRef
promotionDecisionRepositoryFileDigest
promotionDecisionCanonicalDigest
subjectSetDigest
effectiveOutcome
effectiveLifecycleState
headSemantics
recordedAt
supersedes
activationAssertions
```

Their meanings are:

- `traceVersion` is exactly
  `ofarm.temporal-governance-currentness-trace.v0.1`.
- `canonicalization` is exactly `OFARM_CANONICAL_JSON_V1`.
- `currentnessTraceRef` is globally unique and equals the reference named by
  the decision.
- `promotionDecisionRef` and both decision digests bind the exact accepted
  decision bytes and canonical JSON block.
- `subjectSetDigest` binds the ordered, canonical subject set. It cannot be a
  digest of identities without the subject content metadata.
- `effectiveOutcome` exactly repeats the accepted decision outcome.
- `effectiveLifecycleState` is `GOVERNED_INACTIVE` only for
  `PROMOTE_GOVERNED_INACTIVE`; it is `CANDIDATE_INACTIVE` for
  `REFUSE_PROMOTION`.
- `headSemantics` is exactly
  `SINGLE_VERSIONED_HEAD_NOT_TIMESTAMP_SELECTED`.
- `recordedAt` is diagnostic evidence only. It does not select a head.
- `supersedes` is `null` in version 0.1.
- `activationAssertions` exactly repeats the decision's closed non-activation
  posture.

In both records, `activationAssertions` is exactly:

```text
currentDefaultPromotion: false
runtimeActivation: false
productionReadiness: false
runtimeBundleAdmission: false
routeActivation: false
commandActivation: false
readOrOutputEligibility: false
deploymentEffect: false
```

Version 0.1 permits one decision and one trace only. It defines no latest-wins
rule, replacement, revocation, rollback, supersession, or mutable pointer.
Any unequal second decision or trace creates a conflict and fails closed.
A future lifecycle change requires a new reviewed contract version.

## Effective-state resolution

The only lawful resolver is:

```text
exact canonical decision
  + exact canonical currentness trace
  + exact promotion contract
  + exact retained subject bytes
  -> one atomic effective lifecycle result
```

Resolution is closed:

- An exact positive decision and exact matching trace make all three subjects
  `GOVERNED_INACTIVE`.
- An exact refusal decision and exact matching trace leave all three subjects
  `CANDIDATE_INACTIVE`.
- A missing decision or trace leaves all three subjects
  `CANDIDATE_INACTIVE`.
- Malformed, partial, mismatched, ambiguous, or conflicting evidence refuses
  resolution. No subject may be treated as promoted.

An OFARM2 package mirror, manifest, checker, test, RuntimeBundle, profile,
route, environment variable, caller field, timestamp, issue comment, pull
request status, merge commit, or release tag cannot independently establish
the result.

## Authority map

- The OFARM Constitution RC2.1 section 6.16 owns the candidate-to-governed
  promotion ladder.
- CP15 owns the requirement for explicit human promotion authority and a
  currentness trace.
- ADR 0002 owns temporal meanings and half-open interval semantics. This
  contract does not reinterpret them.
- The merged promotion contract owns the exact subject set, content bindings,
  atomicity, and closed outcomes.
- The canonical accepted decision owns the human-governed disposition only.
- The separately governed human promotion authority owns whether the decision
  reference is authentic and authorized.
- The canonical currentness control map owns which exact decision is the
  effective lifecycle head.
- Canonical `samovers/OFARM` repository governance owns publication of those
  two authority records at their fixed paths.
- OFARM2 candidate files own their immutable reviewed bytes and embedded
  creation-state attestations.
- A future OFARM2 extraction manifest may prove byte-identical custody of
  canonical evidence. It cannot originate or widen that evidence.
- Active RuntimeBundle, profile, ActiveArtifactSet, Capability Manifest,
  database, command, route, read, materialization, output, and publisher
  authorities remain unchanged.
- Issue #192 retains sole authority over audit-runtime behavior.

## Invariants

- **TGLE-001 — External authority only.** OFARM2 never originates its own
  promotion decision or currentness head.
- **TGLE-002 — Exact subjects.** Both records bind exactly the three
  subjects, once each, with all reviewed content identities.
- **TGLE-003 — Atomic result.** Effective state changes for all three
  subjects together or for none.
- **TGLE-004 — Separate records.** A decision never substitutes for a
  currentness trace, and a trace never issues a decision.
- **TGLE-005 — Exact cross-binding.** Contract, decision, trace, subject-set,
  repository-file, and canonical-content identities all agree.
- **TGLE-006 — Fixed authority locations.** Repository and path identities
  come from this contract, never from caller data or a package mirror.
- **TGLE-007 — No timestamp authority.** `decidedAt`, `recordedAt`, commit
  time, merge time, and file modification time never select currentness.
- **TGLE-008 — Immutable creation state.** Promotion does not rewrite,
  relocate, or edit the three candidate files or their embedded statuses.
- **TGLE-009 — Governed but inactive.** The strongest positive state is
  `GOVERNED_INACTIVE`.
- **TGLE-010 — Closed version.** Version 0.1 has one decision, one trace, no
  supersession, and no mutable current pointer.
- **TGLE-011 — Fail closed.** Missing, unequal, partial, malformed,
  ambiguous, or conflicting evidence never produces effective promotion.
- **TGLE-012 — No inference.** Approval, review, merge, manifest presence,
  conformance, extraction, or retained bytes alone never creates promotion.
- **TGLE-013 — No activation.** Lifecycle recognition grants no execution,
  RuntimeBundle, profile, route, read, output, or production authority.
- **TGLE-014 — Firewall preserved.** Under version 0.1, production and legacy
  semantic and output surfaces cannot produce, select, verify, or consume
  lifecycle authority.
- **TGLE-015 — Human authority remains separate.** This contract does not
  define credentials, signatures, principals, or steward membership.
- **TGLE-016 — Audit separation.** No lifecycle evidence becomes #192 audit
  input, output, delivery, health, or attribution behavior.

## Required negative cases

Future conformance must reject or fail closed for:

- a decision or trace originating only in OFARM2;
- a canonical record at any repository or path other than the two fixed here;
- a missing, additional, duplicated, reordered-as-authoritative, or
  substituted subject;
- a changed subject path, identity, schema version, file digest,
  canonicalization, canonical length, or canonical digest;
- a decision naming another promotion contract or digest;
- an outcome outside the two closed outcomes;
- a trace without the exact decision, or a decision without the exact trace;
- unequal decision references, decision digests, subject-set digests,
  outcomes, lifecycle states, or activation assertions;
- a positive decision or trace stronger than `GOVERNED_INACTIVE`;
- selection by newest timestamp, commit, merge, tag, filename, package order,
  or sole-record inference;
- a second unequal decision, trace, replacement, revocation, rollback,
  supersession, or mutable current pointer;
- caller, request, route, profile, environment, tenant, principal, timestamp,
  RuntimeBundle, or idempotency data choosing any authority identity;
- an OFARM2 extraction that is not byte-identical and digest-pinned to a
  canonical commit;
- a package manifest or conformance result presented as authority;
- any rewrite or relocation of the three candidate subject files; and
- any production or legacy runtime import or #192 behavior.

## Non-goals

This contract does not:

- issue, approve, refuse, sign, or store a promotion decision;
- create or update canonical OFARM active authority;
- define human credentials, principal resolution, signatures, keys, steward
  membership, or approval policy;
- create decision or currentness schemas, JSON instances, manifests,
  extraction mirrors, digests, or conformance code;
- edit `CONTRACTS_MANIFEST.json`, candidate statuses, frozen contracts, active
  registries, or canonical currentness maps;
- promote a schema or any identity outside the exact three-subject set;
- activate `TEMPORAL_GOVERNANCE_ARTIFACT`;
- change a RuntimeBundle role, model, catalog, repository, publisher,
  selection record, profile, ActiveArtifactSet, or Capability Manifest;
- add storage, a database migration, role, grant, route, selector, command,
  authorization mapping, materialization, read, output, or receipt;
- open current-state, historical, AS_OF, WINDOW, qualification, replay, or
  output behavior;
- import or change the legacy semantic or output surface; or
- implement or change issue #192.

## Smallest coherent Phase A change

The Phase A PR contains this RFC only.

It records the proposed external authority locations, separate record
meanings, exact fields, precedence, state resolution, invariants, negative
cases, and stop conditions. It creates no machine artifact and changes no
effective lifecycle state.

## Verification

Review of this Phase A contract must prove:

- exact agreement with the merged promotion contract's identity, digest,
  subjects, atomicity, outcomes, and non-activation posture;
- exact agreement with OFARM2's rule that this repository cannot originate
  contract promotion or currentness;
- explicit separation of human decision, human-authority verification,
  currentness-head control, candidate content, and runtime authorities;
- fixed canonical repository and path identities that caller data cannot
  select;
- no timestamp, merge, manifest, extraction, or conformance inference;
- complete fail-closed handling for every missing, partial, mismatched,
  conflicting, or stronger-state case;
- no schema, JSON instance, manifest, runtime, database, route, output,
  legacy, frozen-contract, or #192 change in the PR; and
- ordinary documentation hygiene and package conformance remain clean.

## Stop conditions and later boundaries

After this Phase A contract is approved, work still stops before:

1. implementing decision or currentness carrier schemas;
2. defining or verifying human promotion credentials, principal identity,
   signatures, steward membership, or approval policy;
3. adding the canonical decision or currentness files to `samovers/OFARM`;
4. issuing `PROMOTE_GOVERNED_INACTIVE` or `REFUSE_PROMOTION`;
5. extracting canonical lifecycle evidence into OFARM2;
6. changing an OFARM2 manifest or effective lifecycle resolver;
7. promoting a schema or another temporal identity;
8. activating a RuntimeBundle role, component, profile, command, selector, or
   route;
9. adding database, materialization, read, historical, WINDOW, output,
   receipt, legacy, or #192 behavior.

The next boundary after approval may implement only inactive candidate schemas
for the decision and currentness records plus focused conformance. Human
authority verification, canonical issuance, canonical currentness
publication, OFARM2 extraction, and effective lifecycle recognition remain
separate later boundaries.
