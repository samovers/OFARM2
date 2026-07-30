# OFARM Temporal Governance Identity Promotion RFC v0.1

**Status:** package-local `CANDIDATE_ARTIFACT`; contract-only,
inactive, and without promotion effect

**Promotion schema version:**
`ofarm.temporal-governance-promotion-binding.v0.1`

**Promotion schema digest:**
`sha256:6f4545c4101d1b984e3eee55e89ff833184d5474ce1fa8e81b02a85753b8c5c2`

**Promotion binding identity:**
`ofarm.temporal-governance-promotion.issue176-foundation.v0.1`

**Promotion binding digest:**
`sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0`

## Decision

This contract defines the only lawful candidate-to-governed lifecycle decision
for exactly three issue #176 temporal-governance identities. A conforming
positive decision moves the exact reviewed set from `CANDIDATE_INACTIVE` to
the externally recorded lifecycle state `GOVERNED_INACTIVE`.

`GOVERNED_INACTIVE` means that the exact reviewed content is accepted as an
OFARM-governed artifact under Constitution RC2.1 section 6.16. It does not
mean active, current/default, deployed, executable, production-ready, or
admitted to a RuntimeBundle.

This candidate package does not issue that decision. Approval, merge,
manifest presence, and conformance success are not promotion. A separate
human-governed promotion decision and currentness trace are mandatory before
the effective lifecycle state can change.

## Trust boundary

The primary trust boundary is lifecycle authority over exactly three
temporal-governance identities.

This contract owns only:

- the exact promotion subjects and their content identities;
- the atomicity of the promotion set;
- the closed decision outcomes;
- the meaning of `GOVERNED_INACTIVE`; and
- the boundary between immutable creation-state metadata and a later
  effective lifecycle decision.

It does not own promotion-decision storage, human identity or credentials,
signing, RuntimeBundle activation, tenant selection, authorization, commands,
routes, materialization, reads, outputs, legacy behavior, or issue #192.

## Closed promotion set

Promotion is an atomic decision over exactly this set:

| Identity | Schema version | Canonical length | Canonical content digest |
|---|---|---:|---|
| `ofarm.temporal-carrier-matrix.adr0002.v0.1` | `ofarm.temporal-carrier-matrix.v0.1` | 9504 | `sha256:c404c0cd1e08f389664b5381c2c038cf65bac9a3b725fc2b1882990636eb179b` |
| `ofarm.temporal-carrier-selection.intervention.v0.1` | `ofarm.temporal-carrier-selection-binding.v0.1` | 1814 | `sha256:373a5f402ad077039946c1dfe7b972e4382d3c6a6805fbf0b271e4a0bc729bf1` |
| `ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1` | `ofarm.temporal-governed-command-binding.v0.1` | 9614 | `sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1` |

All three use `OFARM_CANONICAL_JSON_V1`.

The reviewed repository-file digests are:

1. `sha256:7cb26513b5abdbcadecaf6f9b47d874a742ba8fa05a332c9130deebe449d7fc6`;
2. `sha256:9886aace0670b6a83f17cd33cbc67aa62fafcfd0ea873faed9194c2aaa07efe5`;
3. `sha256:0909ec653cb99a94cd1b35afaf2d386258aac671c5f730960ed485df8a4b8f2e`.

The repository-file digest protects the exact reviewed candidate file. The
canonical digest and length identify the prospective immutable content under
`OFARM_CANONICAL_JSON_V1`. One identity may not be substituted for the other.

No schema, temporal-coordinate identity, RuntimeBundle carrier binding,
tenant RuntimeBundle-selection binding, matrix row, other command, alias,
successor, or future version is a promotion subject.

## Promotion meaning

The only positive outcome is:

```text
PROMOTE_GOVERNED_INACTIVE
```

Its only effect is:

```text
all three exact subjects become GOVERNED_INACTIVE
```

The subject files are not rewritten or relocated. Their embedded
`CANDIDATE_INACTIVE` values remain immutable creation-state attestations
describing the bytes when reviewed. A later versioned promotion decision and
currentness trace become the effective lifecycle authority for those exact
bytes.

This precedence is narrow:

- it may supersede only the subjects' lifecycle classification;
- it does not supersede their semantic content or execution posture;
- `CLASSIFICATION_ONLY_RUNTIME_UNSUPPORTED`,
  `PURE_LIBRARY_PRODUCTION_UNBOUND`, and
  `CONTRACT_ONLY_PRODUCTION_SURFACE_CLOSED` remain binding;
- absent an exact valid promotion decision, every subject remains effectively
  `CANDIDATE_INACTIVE`; and
- conflicting, incomplete, or ambiguous promotion evidence fails closed.

## Atomicity and dependency order

The promotion set is atomic. There is no lawful v0.1 outcome in which only the
command, only the selector, only the matrix, or any two of the three become
governed.

Verification preserves this dependency order:

```text
carrier matrix -> intervention selector binding -> governed command binding
```

The selector must still bind the exact matrix repository-file digest and the
`INTERVENTION_EVENT` row. The command must still bind the exact selector
identity and repository-file digest.

The binding's `dependencyConsistency` fields deliberately repeat identities
and digests from `subjectSet.subjects`. The subject set proves exact
membership; the repeated fields name the directed relationships. Conformance
requires both representations to agree.

Atomic promotion is lifecycle governance only. It does not alter the carrier
contract's rule that these identities form an allowed identity set rather
than a universal RuntimeBundle co-presence requirement.

## Required decision authority

A future positive decision must record:

- this exact promotion-contract identity and version;
- the exact three-subject set;
- each subject's identity, schema version, repository-file digest,
  canonicalization, canonical length, and canonical digest;
- `PROMOTE_GOVERNED_INACTIVE`;
- a unique promotion-decision reference;
- a human promotion-authority reference;
- the decision time;
- review-evidence references;
- a currentness-trace reference; and
- an assertion that no current/default, production, or RuntimeBundle
  activation is granted.

The closed alternative outcome is:

```text
REFUSE_PROMOTION
```

Refusal leaves all three subjects `CANDIDATE_INACTIVE`. It must not create a
partial, inferred, or implied promotion.

This contract does not define credentials, signatures, principal resolution,
decision storage, or currentness-trace storage. A later implementation that
needs one of those authorities must stop and propose that boundary
separately.

## Authority map

- The Constitution RC2.1 section 6.16 owns the candidate-to-governed
  promotion ladder.
- CP15 owns the requirement for explicit human-governed promotion authority
  and currentness trace.
- ADR 0002 owns temporal meanings, carrier classification, and half-open
  interval semantics.
- The three immutable subject artifacts own their reviewed semantic content
  and execution postures.
- This contract owns only the closed subject set, digest bindings, atomicity,
  and `GOVERNED_INACTIVE` outcome.
- The human promotion authority owns the decision to promote or refuse.
- The currentness trace owns evidence that a decision is the effective
  lifecycle head.
- The temporal carrier contract owns eligibility for
  `TEMPORAL_GOVERNANCE_ARTIFACT`; it does not promote or activate an identity.
- The tenant command RuntimeBundle-selection contract owns the future exact
  command component closure; it does not promote identities.
- RuntimeBundle, ActiveArtifactSet, profiles, Capability Manifest, storage,
  publisher, runtime selection, command authorization, and output governance
  retain their existing authority.
- Issue #192 retains sole authority over audit-runtime behavior.

## Invariants

- **TGP-001 — Exact subjects.** The promotion set contains exactly the three
  listed identities, once each.
- **TGP-002 — Exact content.** Identity, schema version, file digest,
  canonicalization, canonical length, and canonical digest all match.
- **TGP-003 — Atomic decision.** All three subjects are promoted together or
  none are.
- **TGP-004 — Immutable subjects.** Promotion never rewrites or relocates the
  reviewed subject bytes.
- **TGP-005 — External lifecycle authority.** Embedded candidate status is
  creation-state metadata. Only the reviewed promotion decision and
  currentness trace may establish a later effective lifecycle state.
- **TGP-006 — Governed but inactive.** The only positive target is
  `GOVERNED_INACTIVE`.
- **TGP-007 — Execution posture preserved.** Promotion does not weaken any
  subject's inactive, unbound, unsupported, or closed execution posture.
- **TGP-008 — No inference.** Review, merge, manifest presence, carrier
  eligibility, conformance success, or RuntimeBundle-selection documentation
  cannot imply promotion.
- **TGP-009 — No caller authority.** Caller data, configuration, environment,
  profile, route, tenant, principal, request, timestamp, or bundle contents
  cannot choose the subjects or outcome.
- **TGP-010 — No substitution.** An alias, successor, equivalent document,
  schema-only reference, digest-only reference without retained bytes, or
  legacy artifact cannot replace a subject.
- **TGP-011 — Post-promotion immutability.** Any semantic or canonical-content
  change requires a new artifact identity/version and promotion contract
  version.
- **TGP-012 — Fail closed.** Missing, malformed, conflicting, partial, or
  ambiguous authority or currentness evidence leaves every subject
  unpromoted.
- **TGP-013 — No current/default claim.** `GOVERNED_INACTIVE` must never be
  represented as active, current/default, deployed, executable,
  production-ready, or output-eligible.
- **TGP-014 — Firewall preserved.** No legacy semantic or output surface may
  become a promotion source, subject, verifier, or consumer.

## Required negative cases

Verification refuses:

- a missing, additional, duplicated, reordered-as-authoritative, or
  substituted subject;
- promotion of fewer than all three subjects;
- a changed identity, schema version, file digest, canonicalization, length,
  or canonical digest;
- a subject that fails its exact Draft 2020-12 schema;
- a selector whose matrix identity, digest, or `INTERVENTION_EVENT` row
  binding differs;
- a command whose intervention-selector prerequisite differs;
- a non-human, missing, or ambiguous promotion-authority reference;
- a missing or conflicting currentness trace;
- an outcome other than the two closed outcomes;
- a positive decision claiming a state stronger than `GOVERNED_INACTIVE`;
- inference of promotion from tests, review, merge, manifests, carrier
  eligibility, bundle membership, publication, or selection;
- promotion of a schema, carrier binding, RuntimeBundle-selection binding,
  another matrix row, another selector, or another command;
- any rewrite or relocation of the three subject files; and
- any production or legacy runtime import introduced by this package.

## Non-goals

This contract does not:

- promote the corresponding schemas;
- activate `TEMPORAL_GOVERNANCE_ARTIFACT`;
- change RuntimeBundle roles, models, catalogs, repositories, publishers, or
  database constraints;
- change an ActiveArtifactSet, profile, Capability Manifest, frozen contract,
  or production registry;
- create promotion-decision storage, migrations, roles, privileges, signing,
  or key custody;
- select or publish a tenant RuntimeBundle;
- implement the intervention selector in production;
- integrate or authorize `COMMIT_OPERATION_CLAIM_DRAFT`;
- open a route or production semantic surface;
- implement materialization, current-state reads, historical views, WINDOW
  behavior, qualification, outputs, or receipts;
- add another temporal carrier or command;
- import or modify the legacy semantic or output surface; or
- implement or change issue #192.

## Smallest coherent Phase A change

The approved candidate-governance package contains only:

- one exact inactive promotion-contract schema;
- one exact inactive binding for the three-subject atomic set;
- this RFC;
- manifest, digest, and ERRATA traceability; and
- focused positive, negative, digest, and non-activation conformance.

The schema and binding are governance support artifacts. They are not members
of the three-subject promotion set and issue no positive promotion decision.
Constitution RC2.1 section 6.16 directly governs their own candidate
lifecycle until a separately reviewed decision changes it; this contract
cannot promote itself.

## Re-pinning procedure

Before promotion, any reviewed subject revision must be re-pinned as one
coherent change:

1. recompute the subject repository-file digest, canonical length, and
   canonical digest;
2. update the promotion binding and its exact-schema `const`;
3. recompute the promotion schema and binding file digests;
4. update the contract manifest, RFC header, RFC subject table and digest
   list, and checker constants;
5. update the checker-owned RFC digest only after the RFC text is final; and
6. run the focused temporal-governance tests and package conformance gate.

Once a subject digest has received a positive promotion decision, TGP-011
applies instead: semantic or canonical-content change requires a new subject
identity/version and a new promotion-contract version. No regeneration script
may silently rewrite a promoted identity.

## Verification

Phase A verification must prove:

- complete Draft 2020-12 validation and exact schema-to-binding equality;
- exact recomputation of every repository and canonical digest;
- exact recomputation of every canonical length;
- exact three-member uniqueness, order, and atomicity;
- preservation of all three embedded statuses and execution postures;
- matrix-to-selector-to-command dependency consistency;
- refusal of every required negative case;
- unchanged subject files;
- absence from active RuntimeBundle, profile, ActiveArtifactSet, Capability
  Manifest, route, and production and legacy import closures;
- no database, migration, runtime, output, frozen-contract, or issue #192
  changes; and
- the package conformance gate and focused temporal-governance tests pass.

Conformance success is evidence only. It is not promotion authority.

## Stop conditions

Later work stops before:

1. issuing a positive promotion decision without explicit human approval and
   a currentness trace;
2. promoting a schema or identity outside the exact three-subject set;
3. activating `TEMPORAL_GOVERNANCE_ARTIFACT`;
4. changing RuntimeBundle model, database, catalog, publisher, or
   tenant-selection custody;
5. placing these identities in an active RuntimeBundle or production
   registry;
6. implementing command authorization or integration;
7. changing public refusal or output behavior;
8. opening routes, reads, historical views, WINDOW execution,
   materialization, or outputs; or
9. touching issue #192.

Current-state reads and outputs remain blocked. Their output-governance
prerequisites are outside this contract.
