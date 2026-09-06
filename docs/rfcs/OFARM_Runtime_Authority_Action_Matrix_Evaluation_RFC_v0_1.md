# OFARM Production Authorization Provider — Phase A RFC v0.1

Date: 2026-09-06

Design revision: 3. This corrects the fresh-approval interface in revision 2 at
`1473a4c16d8e716b03a3c36c2e36114e6e9fb255`. The unapproved legacy proposal at
`178f150ce56f1bdad96330ba845d210ee0911f2a` remains superseded. No accepted OFARM
law changes.

Status: design review pending; scope amendment and implementation prerequisites
remain open. No OFARM2 semantic approval, runtime implementation, baseline
admission, merge, current/default promotion, or deployment is authorized.

Delivery issue: [OFARM2 #353](https://github.com/samovers/OFARM2/issues/353).
Tracking epic: [OFARM2 #175](https://github.com/samovers/OFARM2/issues/175).
The one existing draft PR is [#359](https://github.com/samovers/OFARM2/pull/359).
Inspected OFARM2 main: `fcac9ba505226e7e2fa2ede0aedb7585721b1841`.
Inspected canonical OFARM main: `71ca724a8b6ec23f1655b086a6f549496d10a47f`.

## 1. Outcome and place in the original work

Deliver one production authorization provider: a trusted runtime consumer can
obtain a current, rule-derived authorization evaluation and its complete
prepared evidence from an authenticated principal, validated effect intent,
trusted policy bindings, and tenant-bound facts. The consumer cannot weaken
the rule by choosing stage, actor posture, scope proof, or revocation inputs.

This is a system-facing capability, not an endpoint activation. The first
concrete consumer is the operation-claim path that motivated canonical
OFARM #25 / PR #26: one pending-review AssertionRecord, with atomic evidence
and truthful retry handling. The delivery order remains authorization #353,
command idempotency/coordination #178, then a separately selected temporal
Delivery under #176. Interface design for those consumers must happen before
this provider's implementation is approved; it does not authorize their code
inside this PR.

Authorization is necessary but insufficient for a write. This provider does
not validate the protected result, consume a decision, commit evidence, or
promise a durable outcome. Those distinctions are the proposed scope amendment
below, not a claim that the existing issue already accepts this narrower
completion condition.

## 2. Explicit proposed amendment to issue #353

The issue still requires a code-owned matrix, migration of existing callers,
SI behavior equivalence, and a durable decision trace. Its old PR also assumed
legacy callers were production. Do not silently mark those requirements met.

The recommendation for steward review is:

| Existing requirement | Proposed replacement and consequence |
|---|---|
| Independently authored code-owned action table | Execute the exact content-addressed canonical rule bundle. A compiled immutable view is permitted only as a verifiably equivalent representation, not a second policy source. |
| Migrate existing legacy evaluator and SI callers | Add the provider to the real production composition and prove its typed tenant-bound entry point. Keep the separate legacy surface quarantined and unchanged; legacy test success is not production evidence. |
| Provider delivers a durable decision trace | Provider delivers complete, schema-checked, digest-verifiable **prepared** evidence and explicit guard obligations. The consumer's transaction boundary owns persistence, complete-set atomicity, successful single use, and durable response. |
| Existing SI decisions remain equivalent | No SI behavior change in this PR. New production decisions follow the separately promoted canonical version; no compatibility interpretation of v0.1 evidence as v0.2. |

Full action-rule coverage is **not** narrowed to one operation-claim row. The
provider must cover the entire admitted canonical action set and all its
specified evaluation branches. It must not report completion because one row
works or because an unsupported implementation returns non-ALLOW everywhere.
The currently approved canonical candidate has twenty rows; the eventual
machine artifact, not a second handwritten count/list, supplies the exact set.

Keep policy coverage, provider implementation coverage, and enabled public
commands separate. No row becomes publicly executable merely because the
provider understands it. Applicable sharing and human-finalization checks are
part of evaluation coverage; creating sharing grants, running an approval
ceremony, disclosure, and protected effects remain separate capabilities.

These amendments are **proposed, not approved**. They must be accepted
explicitly in the later #353 decision scope before an implementation card is
ready. Until then the original criteria remain unsatisfied and #353 cannot
close on a prepared-evidence handoff. If the steward retains provider-owned
durable trace delivery, stop and re-plan the boundary/dependencies; do not add
a second transaction owner or quietly absorb #178.

## 3. Current production facts that change the old design

At the inspected base:

- `kernel/api.py` creates the production application from the environment.
  Governed writes, protected reads, review, and output routes return
  `GOVERNED_SURFACE_BLOCKED`.
- `kernel/application_runtime.py` exposes authentication and tenant
  UnitOfWork composition, but no production authorization provider.
- `kernel/tenant_uow.py` owns one bound PostgreSQL connection and its
  finalization. Its public work surface is binding, batch allocation, and
  fixed command RuntimeBundle resolution; there is no authority-record facade.
- The manager explicitly begins **READ COMMITTED**. Separate reads in that
  transaction are not automatically one immutable snapshot, and a read
  snapshot alone cannot guard a later effect.
- `kernel/principal.py` binds a verified identity to an exact active Party
  record and tenant. It does not by itself prove a natural-person
  representative or the complete CP3 agent evidence.
- `ofarm.kernel_record` and `ofarm.kernel_record_reference` are existing
  tenant-bound tables with immutable record/batch and typed-reference
  provenance. Their existence and SELECT privileges do not prove that all
  v0.2 source, currentness, snapshot, or guard contracts already exist.
- The architecture checker forbids production imports of `kernel.authority`,
  `kernel.policy`, `kernel.store`, the old gates/stages/validators, and
  legacy SI semantic/output modules. This prohibition remains intact.

The old RFC's twenty-row table, H/HA posture shortcuts, L lineage expansion,
legacy Store wiring, generic trace-field reuse, and serialized-transaction
claims are withdrawn as unapproved proposals. Existing historical code,
reviews, decisions, and evidence are not rewritten.

## 4. Primary trust boundary, authority map, and effects

Primary trust boundary: **production authorization evaluation**.

Intended PR boundary: one evaluator, exact rule interpretation, narrow typed
authority reads, prepared evidence construction, and mechanical production
composition/tests needed to prove that capability. No independent authority,
custody, persistence, or command-execution capability travels with it.

| Owned fact or operation | Owner |
|---|---|
| Action meaning, rule fields, actor/finalization semantics, path aggregation, reason ranks, evidence schemas and hash projections | Canonical OFARM; exact promoted/extracted versions |
| Credential verification, identity binding, tenant capability, key custody | Existing authentication, principal, binder, and KMS boundaries; unchanged |
| Party classification and authority/representation/CP3 proof evaluation | This provider applies the bound contracts to trusted identity and governed evidence; it cannot mint missing identity/actorship authority |
| Policy/command selection and immutable runtime component identity | Existing separately reviewed selection/RuntimeBundle owners |
| Database session, transaction identity/finalization, isolation, complete commit guard and uncertainty reconciliation | Existing transaction owners and later #178 work; no new owner here |
| One current evaluation, selected sufficient path, complete prepared decision evidence and read obligations | This provider |
| Protected-effect schema, mapping, gate PASS, assertion state and temporal mapping | Separately owned domain/temporal validators and command binding |
| Durable request/result/trace, consumption, attempt/receipt, original-result recovery and safe response after commit | Command/evidence coordinator; #178 and the applicable consumer |
| Requests, optional AI metadata, schema hints, candidate references | Caller-owned claims, never authoritative restrictions |

### High-risk trust model

Protected assets are allow/refuse integrity, tenant and scope containment,
human/agent attribution, effective revocation, complete decision evidence and
the downstream effects that must never consume unproved authority.

Trusted inputs are reviewed deployment code, verified content-addressed
canonical bindings, the existing authenticated identity and tenant boundary,
and the owning transaction policy's time and proof interfaces after their
own admission checks pass. Schema validity or a tenant-filtered database row
alone does not prove that a source is eligible, current or complete.

Untrusted inputs include public and internal request facts, optional metadata,
candidate hints, forged or stale references, malformed source records,
cross-tenant targets and incomplete indexes. Legitimate concurrent writers
and revocations are part of the threat model; they are not excluded to make
the READ COMMITTED assumption appear safe.

Excluded capabilities are arbitrary execution/mutation inside the trusted
process, substitution of admitted deployment/package bytes, database-superuser
bypass of the governed storage boundary, and compromise of credential/KMS,
host-clock or operating-system custody. This provider does not claim to repair
those separate boundaries. A missing or expired proof is not an excluded
attack and must fail closed.

Primary risk: an untrusted caller obtains ALLOW through a weaker rule, a false
actor/scope claim, stale authority, or incomplete negative/set evidence.
Containment: one exact bound rule, complete tenant-bound evidence, canonical
fail-closed aggregation, exact attempt/cutoff binding, and an explicit handoff
that confers neither durable status nor independent effect authority.

### Permitted effects and non-effects

Permitted future effects, only after the gates in section 13:

- construct one immutable verified rule view from the selected canonical bytes;
- evaluate actor, resource, scope, source, sharing, revocation, purpose,
  evidence and finalization constraints through one deterministic path;
- read through a typed facade on the existing bound connection, without
  exposing SQL or connection control;
- prepare exact request/result/full-trace evidence and bindings for the owning
  transaction consumer; and
- add the production composition hook, architecture registration, tests,
  documentation and mechanically necessary inventory changes.

Non-effects and non-goals:

- no domain writes, durable authorization ledger, operation/idempotency table,
  decision consumption, receipt writer, commit/retry/reconciliation engine,
  or temporal query implementation;
- no grant/delegation/sharing creation, narrowing, revocation, bootstrap or
  break-glass command;
- no authentication/principal-binding semantics, CP3 schema or actorship
  issuance, tenant isolation, roles, migrations, isolation mode, locking
  authority, signing, audit custody, or readiness change;
- no contract invention/extraction, reference edit, current/default promotion,
  runtime selection-authority change, public action activation, profile
  behavior change, disclosure/outbox/transport capability, or deployment.

A necessary new database permission, principal-resolution proof source,
snapshot/guard authority, or selector decision is not “just wiring.” Stop
before editing that boundary and identify separately reviewable Delivery
work. No such issue or exception is created by this design revision.

## 5. Canonical sources and readiness inventory

The following are exact semantic planning sources, **not executable authority**:

| Candidate | Exact reviewed source head | Relevance |
|---|---|---|
| [OFARM PR #11](https://github.com/samovers/OFARM/pull/11) | `03a21f669ee04f96d444e14f00ae7212cab04803` | Complete action rules, principal/CP3/finalization axes, paths, snapshot, v0.2 evidence and staged delivery |
| [OFARM PR #20](https://github.com/samovers/OFARM/pull/20) | `98f8c4fafbae42c8f7fd931f43f53adcb4733713` | Human-finalization transaction protocol; excludes NOT_REQUIRED |
| [OFARM PR #23](https://github.com/samovers/OFARM/pull/23) | `622376e2998cf8b3954ca19e81d2cce6fd57e5fe` | AssertionRecord submission protected-effect contract |
| [OFARM PR #26](https://github.com/samovers/OFARM/pull/26) | `e042efa2911b2ef0a61603b8e0adaa6911c03ac0` | NOT_REQUIRED atomic protocol and first operation-claim handoff |

The [PR #26 approval](https://github.com/samovers/OFARM/pull/26#issuecomment-5560085396)
closes that candidate's Phase A semantic review. It does not merge its bytes,
materialize contracts, promote currentness, or approve OFARM2 implementation.

Before code, replace this planning inventory with exact source paths, source
commits, byte digests, canonical currentness status, OFARM2 extraction paths,
and manifest entries for every required component:

| Required component family | Verified readiness at this revision |
|---|---|
| AuthorizationPolicyBundle v0.2, resolved ActionAuthorizationRules, rule/extractor/intent schemas, relevant-state projection and immutable binding manifest | Proposed semantics; required executable bytes and extraction not ready |
| AuthorityGrant, DelegationGrant, SharingGrant v0.2 | Proposed source semantics; required v0.2 packages/extraction not ready |
| AuthorizationDecisionEvidence and AuthorizationFinalizationEvidence v0.2, including applicable rejection/snapshot/consumption evidence | Proposed semantics; required machine packages/extraction not ready |
| Applicable protected-effect contracts, AssertionRecord result binding and Event Grammar classifications | Approved candidates cover some families; all-row prerequisites remain open |
| Human and NOT_REQUIRED transaction profiles, deadline/guard mappings and result-complete lifecycle | Semantic candidates approved; executable profiles and production interfaces not yet proved |
| CP2 authorization result/reasons and applicable retention, sovereignty, evidence and CP3 bindings | Must be inventoried and proven at exact admitted versions; no blanket readiness claim |

Existing v0.1 schemas are not substitutes. A missing digest is recorded as
missing, never filled with a placeholder that could become executable.

[OFARM #21](https://github.com/samovers/OFARM/issues/21) and approved PR #11
section 24 control the order: adjacent prerequisites; non-default policy,
source and bounded decision-evidence packages; exact binding review and
accepted law; hostile conformance; explicit current/default promotion;
byte-identical OFARM2 extraction; then OFARM2 runtime work. The older PR #359
comment's abbreviated order is not controlling. PR #26 did not complete all
of these steps.

## 6. Proposed production interface and data ownership

Use one small production-only provider and a narrow tenant read adapter.
Private names below describe ownership; they are not new machine contracts or
a frozen API while the exact source bindings remain absent.

The intended entry point is a typed authorization provider on the active
`TenantUnitOfWork`, reached through `ApplicationRuntime.tenant_unit_of_work`.
Composition constructs its private dependencies from the same connection.
It must be exercised through that actual composition, not only by importing
a pure helper. Its bounded preparation and final-evaluation operations share
one implementation of the canonical policy, path selection and cutoff rules.

The trusted input binds, as one immutable value:

- the authenticated principal and exact TenantBinding;
- the selected command/action and exact current policy/rule/binding manifest;
- the schema-valid full effect intent and canonical digest;
- current trusted attempt identity, time, exclusive deadline and snapshot
  provenance from the transaction-policy owner;
- applicable persisted prerequisites with exact immutable record/digest and
  snapshot-visibility proof, including challenge/display evidence for fresh
  approval; and
- for final evaluation, the separately typed, mode-correct prospective
  finalization evidence described below, constructed by the transaction
  consumer but not yet committed.

A request cannot construct that value by supplying a tenant, deadline, stage,
posture, policy URL, grant dictionary, or snapshot label. The provider applies
the rule-selected schema and identity-only JSON Pointer extraction; a second
caller-supplied authorization view is prohibited. Runtime-completed fields
must come from their owning command protocol, not a second completion
algorithm inside the evaluator.

The read facade returns typed immutable records and completeness evidence.
It uses only closed, parameterized queries through the bound connection and
checks family, schema/content digest, immutable identity, tenant, lifecycle,
visibility and relevant reference bindings. It does not accept a connection,
SQL expression, table name, transaction callback, or caller-filtered candidate
list. Existing Row-Level Security remains an independent backstop.

The read footprint includes principal/representation/CP3 evidence, target and
typed inputs, role/grant/delegation/sharing candidates, source records,
revocations, purpose/condition evidence, sovereignty, applicable policy and
currentness facts. It must cover absence and complete sets as well as positive
rows. Bounds may reject an oversized/incomplete evaluation; they may not
truncate a set and call the result complete.

The concrete PostgreSQL read plan, immutable snapshot representation,
transaction-policy input factory, and complete read/guard interface are a
**design gate**, not already implemented infrastructure. A series of ordinary
READ COMMITTED queries or caller-authored proof objects does not satisfy it.
A coherent single-statement read may help capture a snapshot, but is not by
itself a commit guard or authority to introduce a new snapshot contract.

### Preparation is distinct from a prepared decision

For the post-act `FRESH_HUMAN_APPROVAL_REQUIRED` protocol, the same provider
offers a bounded non-authoritative preparation operation before the consumer
can construct prospective approval evidence. It requires the trusted
rule-selected mode, admitted operation/generation and exact authenticated
human act, challenge/display bindings, final snapshot and complete guards.
It is not challenge issuance or a token retained across human think time.

Its immutable local preparation result binds the tenant, operation/generation,
attempt, requester and intended approver, human act, intent, policy/rule,
challenge/final snapshots and their equal authority-relevant-state digests.
It supplies the canonical candidate requester path and basis, independently
eligible natural-person approver path, complete cutoff inputs,
`approvalExpiresAt` and candidate `decisionValidUntil`, computed in section 7.
These values are inputs to evidence construction, not an authorization
outcome. Preparation emits no decision result, decision trace, decision-bundle
digest, consumption, effect, durable claim or portable path outcome. Failure
returns a typed preparation refusal, never a successful candidate with missing
proof or an invented authorization result.

The consumer uses those provider-derived values to construct and hash the
complete mode-correct finalization-evidence candidate. It does not duplicate
path selection or expiry calculation. The provider accepts that candidate
through a distinct prospective-evidence input bound to the same preparation
and attempt, not by pretending to load an already-persisted approval record.
The input carries the complete candidate bytes, deterministic identity and
digest, and their exact act, snapshot, intent, basis and cutoff bindings.

Persisted prerequisites and prospective finalization evidence are different
typed inputs with different verification rules. Neither a caller label nor
schema validity establishes their provenance. The prospective input is usable
only in its rule-selected finalization-evidence role; it cannot stand in for a
missing persisted grant, role, CP3 record or snapshot. Prior committed evidence
is not portable approval for another attempt. The local type distinction adds
no field or contract to canonical records and claims no persistence.

The final-evaluation operation returns a truthful ingress/infrastructure
refusal or, when canonical evaluation is possible, a prepared decision bundle
with its immutable basis and guard obligations. This is a different result
type from non-decision preparation. Both stay internal and non-durable; only
the final evaluation can construct the decision bundle. The consumer cannot
pass a preparation result as a decision or choose a generic “skip approval”
flag. Successful fresh-approval finalization requires the full handshake and
equality checks below, irrespective of which operation a caller invokes.

`DIRECT_HUMAN_ACTION_REQUIRED` instead supplies its exact prospective
direct-principal act/representation evidence to final evaluation. It creates
no synthetic challenge, separate approver or fresh-approval preparation.
`NOT_REQUIRED` follows its own bound protocol without human-finalization
evidence. Only the trusted rule selects these modes; a request cannot switch
modes to bypass approval.

Do not finalize an implementation card until this interface has a concrete
production-path test and an independently usable provider completion
criterion. “A future #178 will make this work” cannot justify closing #353.

## 7. Evaluation contract

The exact promoted counterpart of PR #11 controls field names, ordering and
outcomes. This section maps that meaning to implementation ownership; it does
not create a second action matrix.

### Ingress and policy

Reject malformed bytes and duplicate JSON names; validate the base request;
resolve the action and complete immutable rule/manifest; validate its selected
effect-intent schema; then execute its exact authorization-view extraction.
A missing/invalid rule, incompatible schema hint, invalid intent or extraction
is ingress rejection, not fabricated DENY evidence.

Validate the policy bundle and every required per-action semantic-closure
binding. Code may implement algorithms, but may not author independent
stage/posture/resource/inheritance rules. Source reuse compares the exact
action/rule ID/rule digest. The complete policy digest records evaluation
context; an unrelated action change must not alone invalidate a source whose
selected semantic closure is unchanged.

### Principal, resource and scope proof

Keep natural-person/software/unresolved principal kind, exact CP3 posture,
human-finalization requirement and AI disclosure separate. Optional AI
metadata is provenance only: adding, removing or retrying it cannot change
principal kind, authority basis or outcome. An organization alone is not a
natural-person final act, and sponsorship alone is not agent authority.

Use the existing principal binding as an identity anchor; verify the remaining
governed facts under the canonical contracts. Missing current representation
or CP3 evidence never becomes a human/self path. This provider checks evidence;
it does not issue actorship or expand the upstream identity resolver.

Derive exactly one authority target plus distinct typed inputs and effect
subject from the rule-selected intent. Resolve existing targets by exact
family, immutable revision/digest, lifecycle, twin, tenant and scope relation.
For prospective subjects, enforce the rule's existence posture and record the
required absence/currentness obligations. A real local scope cannot launder a
missing, wrong-kind or foreign target. Data-sovereignty references identify
actual sovereignty objects, never a generic proof bag.

### Complete source paths

Evaluate every candidate path independently. A role-targeted path must be
covered by both a current RoleAssignment anchor and the grant scope. A
delegated source obeys the same anchor limit, source authority, rule binding
and closed intersection of action, family, scope, inheritance, time, purpose,
conditions and cumulative evidence.

Do not union incomplete paths or choose the first database row. Require the
canonical exact tokens and supported condition/evidence semantics; legacy
free text or unresolved evidence is not silently ignored. All twenty proposed
rows exclude derived-lineage expansion. Enforce the selected row's actual
inheritance/delegation ceiling, including NO_INHERIT requirements.

Use the complete revocation index/snapshot, not caller candidate hints.
TERMINATE targets the exact immutable source family and ID. Apply the
canonical unsupported-narrowing disposition per path; do not invent narrowing
semantics or let an unrelated unsupported path automatically defeat a
different completely sufficient path.

For RECEIVE_READ_DATA, evaluate the applicable SharingGrant composition
inside the final authorization algorithm. There is no later hidden sharing
overlay that can turn an incomplete authorization trace into a final decision.
Output planning, redaction, retention custody and transport remain with their
own boundaries; ALLOW does not itself disclose data.

### Deterministic outcome and evidence

Implement PR #11 section 15 exactly: evaluate independent global checks under
their dependency order, mark dependent checks NOT_EVALUATED truthfully, and
give established global DENY precedence over global REQUIRE_REVIEW. Global
failure prevents path aggregation.

Otherwise aggregate complete path dispositions in this order: ALLOW,
REQUIRE_HUMAN_APPROVAL, REQUIRE_REVIEW, DENY, then no-applicable-path DENY.
Within the winning disposition select by the canonical direct-Party,
role-targeted, delegated, sharing path order and exact immutable source IDs.
Use the selected path's outcome-specific reason ranking. Preserve all other
evaluated paths as ordered diagnostics, not authority combined with that path.

Outstanding human approval can be reported only for an otherwise sufficient
path. A truthful non-ALLOW decision is not a substitute for the non-decision
post-act preparation below. Verify applicable persisted prerequisites and
prospective finalization evidence and cutoffs; this provider does not run the
human ceremony, reserve authority, or consume approval.

### Fresh-approval preparation and final equality

The interface follows [canonical PR #20 section 11 at its pinned head](https://github.com/samovers/OFARM/blob/98f8c4fafbae42c8f7fd931f43f53adcb4733713/package_meta/history/clean_baseline_migration/phase_reports/governed_human_approval_transaction_and_consumption_protocol_rfc_candidate_v0_1.md#11-required-post-act-revalidation).
After post-act revalidation and the exact challenge/final relevant-state
comparison pass, preparation performs this sequence under the same final
snapshot and guards:

1. Use the shared authorization implementation to evaluate every global and
   per-path condition except the still-outstanding fresh-approval condition.
   No authorization result or decision bundle is emitted.
2. Require global preconditions to pass and apply the canonical lattice and
   path tuple to otherwise-sufficient requester paths. Determine the candidate
   requester path and basis that would otherwise require fresh human approval.
3. Independently determine the canonical natural-person approver path that
   satisfies every non-finalization condition for the same action, target,
   effect subject, scope, purpose, Party posture and intent. Sponsor status
   alone remains insufficient.
4. Collect all rule-required cutoffs, including the trusted transaction and
   session deadlines, candidate requester and applicable approver paths,
   representation, sources, policy/snapshot, resources, evidence and
   sovereignty inputs. A required missing cutoff fails preparation.
5. Compute `approvalExpiresAt` under the exact approval profile, then compute
   candidate `decisionValidUntil` with the canonical minimum-cutoff function
   using that requester path and `approvalExpiresAt`.

The consumer binds the full preparation values into the prospective approval
profile before computing its identity and digest. The candidate is still
uncommitted and non-consumable. Raw human-act metadata or an approval ID alone
cannot replace the complete candidate.

Final evaluation verifies the candidate's schema, identity/digest and exact
tenant, operation/generation, attempt, authenticated act, principal and
representation, challenge/display, policy/rule, intent, snapshot/relevant-state,
requester/approver basis and expiry bindings. It then performs the complete
canonical evaluation, including fresh-approval validity, over the complete
current evidence. The candidate basis is a binding to verify, not a filter
that forces path selection or exempts any check. Invalid prospective evidence
cannot satisfy fresh approval or support ALLOW; it follows the canonical
refusal/failure protocol, not an ALLOW that the coordinator must overrule.

Successful finalization requires the final selected requester path and basis
to be identical to the preparation and hashed candidate, and returned
`decisionValidUntil` to equal the prebound value exactly. No different basis,
shorter or longer validity window, missing cutoff, or other-attempt evidence
can satisfy this equality. Do not repair a mismatch by choosing another path,
rewriting/re-hashing the approval or silently adopting a new window. It fails
finalization: no successful finalization handoff, effect or consumption is
permitted, and the consumer discards the prospective evidence. Any truthful
failure evidence belongs to the canonical failure protocol; it cannot turn
that candidate into a committed approval or authority token.

Preparation and final evaluation share the policy/path/cutoff implementation;
they differ in allowed outputs and the explicit protocol point at which the
prospective approval can be checked. No coordinator-owned policy engine or
caller-selectable condition mask is introduced.

### Final decision evidence

Build complete request/result/full-trace records and snapshot/basis bindings.
The decision-bundle projection removes only
`/result/decisionBundleDigest` and `/trace/decisionBundleDigest`; all other
schema-permitted content stays hashed. Apply the canonical pre-digest
sentinel validation, JCS/SHA-256 and final ordinary-schema validation. Do not
reuse v0.1 evidence fields to simulate v0.2 meaning.

## 8. Evaluation lifetime and transaction handoff

The ordinary decision-evaluation sequence is:

`BOUND_INPUT -> INGRESS_VALID -> CURRENT_FACTS_PROVEN -> EVALUATED
-> PREPARED_EVIDENCE -> HANDED_TO_OWNING_TRANSACTION`.

For post-act fresh-approval finalization, insert the explicit handshake before
EVALUATED: `CURRENT_FACTS_PROVEN -> NON_DECISION_PREPARATION ->
CONSUMER_BOUND_PROSPECTIVE_EVIDENCE -> FINAL_EVALUATION_AND_EQUALITY_CHECK`.
Only that final operation may construct the decision bundle; only a valid
ALLOW satisfying the equality checks is eligible for successful finalization.
The consumer-owned middle step constructs/hashes evidence; it does not persist
it, select authority or calculate a competing validity window.
NON_DECISION_PREPARATION is never interchangeable with PREPARED_EVIDENCE.

Ingress/infrastructure failure does not invent a valid authorization result.
A valid non-ALLOW result can reach PREPARED_EVIDENCE, but never an effect or
consumption transition. Closing/refusing the UnitOfWork invalidates further
provider use, including its preparation and prospective-evidence bindings.
There is no provider-owned COMMITTED state. Rollback discards prospective
evidence; a new attempt cannot reuse it even if its old expiry has not passed.

Every prepared decision binds the current transaction attempt and full
intent. Compute decisionValidUntil as the canonical minimum of the trusted
transaction deadline, session/principal, applicable source/representation,
policy/snapshot, resource/evidence/sovereignty and approval cutoffs. Ends are
exclusive. Required missing/unparseable ends or a minimum not later than the
evaluation time produce no consumable decision. A later retry needs a fresh
evaluation; retrieval of old evidence is not another use of old authority.

The provider describes every authority fact and absence/set predicate that
must remain valid. The transaction owner must protect and recheck that
complete footprint together with the other gates and writes. A changed or
unprotected footprint prevents consumption; a fresh evaluation cannot merely
relabel the stale trace.

This PR does not claim that READ COMMITTED, the tenant-binding lock, or batch
allocation already provides that protection. Changing isolation, adding a
guard protocol, or inventing authoritative commit-status lookup is outside
this PR. #178 must close its own concrete implementation design.

### Durable outcomes belong to the consumer

For the future NOT_REQUIRED operation-claim consumer:

1. #178 owns shared logical-operation lookup and bind-once intent. It resolves
   prior complete results or uncertainty before admitting another attempt.
2. The short guarded transaction supplies trusted current inputs to this
   provider, which prepares a fresh decision bundle.
3. The separately owned protected-effect validator and other applicable gates
   must pass. Authorization ALLOW is not a domain-gate PASS.
4. The coordinator constructs and atomically commits the exact required
   operation/mode/decision/snapshot/domain-trace/consumption/attempt/receipt
   set, with one permitted result. The canonical transaction profile owns
   hash order, single-use enforcement and uniqueness.
5. A valid refusal skips the protected effect and consumption. Its permitted
   complete no-effect evidence set must commit before a durable refusal is
   returned. Do not raise a public authorization exception inside the current
   UnitOfWork and then pretend its rolled-back trace survived.
6. A failed or uncertain commit is an infrastructure/reconciliation state,
   never proof of a durable ALLOW, denial, rollback or successful effect.
   Recovery distinguishes the protected-effect commit from a separate
   failure-evidence commit and preserves their actual identities.
7. Public results use the separately admitted CP2 surface and current
   disclosure policy. Full internal traces are not exposed by this provider.

Human-finalization actions consume their own PR #20 protocol. For fresh
approval, its consumer owns admission of the exact act/open generation and
the guarded final transaction, uses this provider's non-decision preparation,
constructs the prospective approval, and returns it to the same provider for
the complete final evaluation and exact basis/window equality checks. The
consumer then owns the remaining gates and atomic success set; the candidate
becomes durable only with that complete successful commit. Challenge issuance,
the human ceremony, persistence, approval/decision consumption and transaction
coordination remain outside this provider. Governed reads use their separately
owned buffered evidence/disclosure protocol. PR #26 cannot be used as a
universal coordinator for those modes.

This is an interface obligation for those later owners, not their
implementation or verification in #359. Provider tests can prove exact
non-decision preparation, prospective-evidence validation, final basis/window
equality, prepared evidence, transaction binding and no owned writes. Durable
refusal, lost-acknowledgement recovery, atomic effects and consumption require
consumer-owned integration tests; they cannot be reported as #353 evidence.

## 9. First consumer and the incompatible old command binding

For ASSERT_OPERATION_CLAIM, use the promoted counterpart of PR #23's
`ofarm.protectedeffect.assertionrecord.submit.v0.1` contract and PR #26 handoff.
The intent selects an OPERATION_ASSERTION; the protected result is one
OPERATION_CLAIM_ASSERTION in PENDING_REVIEW, with the governed OPERATION_CLAIM
classification. The domain owner, not this evaluator, implements that mapping.

The original online assertedAt is assigned by the trusted command before
validation/hashing and preserved by the operation binding. The selected
authority subject supplies assertion attribution. An alleged historical
performer is separate and is NOT_EVALUATED_BY_AUTHORIZATION; current
submission authority is not historical performer authority.

The inactive
`contracts/candidates/temporal_governed_command/OFARM_OperationClaimDraftTemporalCommand_candidate_v0_1.json`
requires SemanticEventEnvelope/ExecutionRecordPayload and explicitly forbids
ASSERTION_RECORD in its batch. The delivered selector pins that binding:
`ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1`,
digest
`sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1`.

It must not be silently reinterpreted, edited in place, or used to admit this
new result. A successor command/selection binding needs review in its owning
boundary before integration; any selector authority change is separately
classified. The existing intervention temporal carrier mapping is likewise
not an AssertionRecord mapping. None is modified here.

The next #178 design must also reconcile representation in operation
identity, the shared cross-handler/profile lookup, caller projection versus
bind-once full intent, original timestamps, exact key equality, complete
NO_EFFECT consequences, separate commit uncertainty, and original-result
recovery. Its older all-command-family criteria must not silently shrink to a
single claim example. #193 still owns disaster/store-loss recovery.

## 10. Falsifiable invariants and production-path verification

IDs below belong to this revision. They supersede the earlier unapproved
INV-001 through INV-012 proposals; no prior approval or passing test transfers.
“Production entry” means the proposed provider on a genuinely bound UnitOfWork
created through production composition, not an HTTP route opened by this PR.

| ID and invariant | Owning code area | Required negative case through the production entry |
|---|---|---|
| AUTH-001: one exact canonical rule source; full admitted action coverage | Verified rule loader and coverage checks | Wrong digest, missing/duplicate rule, invalid closure or mismatched caller schema hint cannot produce an executable rule; test every canonical row/branch, not a copied list. |
| AUTH-002: callers cannot choose restrictions or mirrored proof | Bound input and rule-selected ingress/extraction | Supply forged stage/posture, tenant, schema, time, scope or policy hints; none weakens evaluation. Invalid ingress creates no fabricated decision. |
| AUTH-003: identity, representation and CP3 are independently proven | Actor/path resolver | Organization without natural-person proof, sponsor without authority, missing CP3 snapshot, and AI-metadata omission/retry never manufacture an eligible path. |
| AUTH-004: target, typed input, effect subject and scope are distinct | Tenant resource reader and rule interpreter | Use a wrong-kind/foreign/missing target with a valid local scope, stale revision, or unproven prospective absence; no unproved eligibility. |
| AUTH-005: one independently sufficient source path | Role/grant/delegation evaluator | Role anchored to Farm A plus grant for Farm B, revoked delegation source, or two individually insufficient grants cannot authorize Farm B. |
| AUTH-006: every applicable closed constraint is evaluated | Rule/path constraint evaluation | Unsupported non-empty condition, wrong exact purpose/family token or unresolved required evidence cannot be ignored. |
| AUTH-007: complete current facts, revocation and rule ceilings | Typed snapshot/read footprint | Omit a revocation, truncate a grant set, widen inheritance to lineage, or present an incomplete watermark; no complete-proof claim. |
| AUTH-008: sharing is composed before final authorization | Same evaluator's read-sharing branch | A scoped grant without the required sharing basis cannot ALLOW RECEIVE_READ_DATA; a later overlay is not a substitute. |
| AUTH-009: deterministic canonical aggregation and selected evidence | Outcome/path/reason selection | Reverse database order; combine global failures, unrelated revoked paths and sufficient paths; result, chosen basis and reason order follow the canonical lattice. |
| AUTH-010: exact complete evidence, no proof-field misuse | Evidence constructor and hash verifier | Change nested digest-named content, omit an exact projection member, use false sovereignty refs or mismatched source bytes; reject invalid evidence. |
| AUTH-011: current attempt and exclusive validity only | Bound input/lifetime and cutoff computation | Reach a cutoff exactly, extend a caller deadline, change intent or move evidence to another/closed UnitOfWork; no consumable handoff. |
| AUTH-012: prepared is not durable; no effect/commit authority | Provider result envelope and composition | Inject read/hash failure or roll back the enclosing UnitOfWork; no durable receipt, evidence-commit claim, domain write or consumption is produced by the provider. |
| AUTH-013: complete guard obligations cannot be omitted | Read-footprint output and consumer contract | Drop a negative/set-valued obligation or alter a captured revision; the handoff fails its exact contract. Commit-race enforcement remains consumer-owned and cannot be claimed from this test alone. |
| AUTH-014: production is legacy-free and commands remain closed | Application/UoW composition and architecture checker | Exercise real composition and all governed route closures; a legacy import, public authority dependency/SQL escape, or newly enabled command fails verification. |
| AUTH-015: fresh-approval preparation is non-authoritative | Same provider's bound preparation operation and shared policy/path/cutoff implementation | With valid post-act inputs, obtain exact candidate requester/approver bases and expiry values, but no decision result/trace/bundle, consumption, effect or durable claim. Fail a global/path condition or omit a cutoff: no successful preparation. Passing preparation as a decision or requesting an approval-skip flag cannot authorize anything. |
| AUTH-016: prospective finalization evidence has an explicit, restricted input role | Same provider's final-evaluation input and evidence verifier | A correctly bound, hashed prospective approval not yet stored in the database reaches full final evaluation and can produce prepared ALLOW when every check passes, without a durable claim. Wrong bytes/digest, act, snapshot, intent or approver binding cannot support ALLOW. A prospective grant or caller assertion of persistence cannot replace governed prerequisite proof. |
| AUTH-017: candidate and final requester basis/window must match exactly | Shared canonical selection/cutoff logic and final equality checks | Substitute a different otherwise-eligible requester basis, or shorten/extend the prospective decisionValidUntil even within the transaction deadline. Final evaluation cannot force selection, rewrite the candidate or accept a different returned window; no ALLOW based on that candidate or successful finalization handoff. |
| AUTH-018: preparation and prospective evidence are attempt- and mode-bound | Bound provider lifetime, trusted mode and candidate admission | Reuse the same intent/preparation/approval in another attempt or after rollback, even before expiry; reject reuse as authority. Substitute NOT_REQUIRED or DIRECT_HUMAN_ACTION_REQUIRED, or supply a synthetic challenge/separate approver to direct-human mode; no bypass. |

Test setup uses fictional data and the existing separately owned provisioning
path. No production bootstrap or grant mutation is added to make fixtures
work. Relevant cases require real PostgreSQL tenant binding, two-tenant
isolation, exact currentness inputs and recorded read provenance; a pure
function fed caller-authored grant dictionaries is insufficient.

AUTH-015–018 exercise preparation and final evaluation through the same
production-bound provider and guarded attempt fixture. The fixture supplies
the transaction owner's trusted inputs and constructs prospective evidence
from the provider's output; it must not implement its own path-selection or
cutoff algorithm. Assertions inspect both returned types/bytes and the absence
of provider-owned writes. The valid prospective-approval case proves the
handshake is usable, not merely that every attempt can be refused.

The exact source schemas and trusted input/read interface must exist before
these proposed cases can count as implemented evidence. Consumer race tests
must additionally cover revocation/set changes between evaluation and commit,
exclusive deadlines, duplicate consumption, persistence failure, committed
refusal with lost response, and separately unknown evidence commits.

## 11. Disposition of the existing nine-blocker review

The [review at the old head](https://github.com/samovers/OFARM2/pull/359#pullrequestreview-5065359533)
remains historical evidence. The old “zero Blockers” wording was contradicted
by that review and is removed. This table is a correction map for re-review,
not reviewer approval or a claim that executable prerequisites now exist.

| Review finding | Revision and canonical owner | Remaining evidence/gate |
|---|---|---|
| B1: AI omission and incomplete CP3 | Sections 6–7; PR #11 section 6 separates principal, CP3, finalization and disclosure. No optional-metadata authority switch or blanket invented software policy. | Exact upstream evidence interface and AUTH-003; missing proof refuses. |
| B2: role anchor escape | Section 7; PR #11 sections 9–10 require role and source scope intersection, also for delegated sources. | AUTH-005 with real bound records. |
| B3: purpose/conditions/evidence undefined | Section 7; PR #11 sections 11–12 and 17 own closed source semantics. | Materialized v0.2 sources and AUTH-006. |
| B4: revocation narrowing | Section 7; PR #11 sections 14–15 own exact termination, unsupported narrowing and path aggregation. | AUTH-007/009; no locally invented narrowing. |
| B5: scope masquerading as target proof | Sections 6–7; PR #11 sections 7–8 define target/input/subject extraction and existence postures. | Exact rule bindings, typed reader and AUTH-004. |
| B6: trace cannot express promised proof | Sections 5 and 7; consume new canonical decision evidence, never misuse dataSovereigntyBoundaryRefs. | Machine materialization/extraction and AUTH-010. |
| B7: read SharingGrant overlay | Section 7 puts applicable sharing inside the one authorization evaluation. | AUTH-008; no disclosure/output implementation. |
| B8: refusal evidence rolled back by error | Sections 2 and 8 explicitly separate prepared evidence from consumer-owned durable refusal and response. | Steward must approve the #353 criterion amendment; consumer commit/recovery proof remains #178/applicable consumer work. |
| B9: six unsupported lineage expansions | Section 7 removes L; approved PR #11 section 7 supplies D/X/N ceilings and no derived-lineage row. | Exact artifact equivalence and AUTH-007. |

Fresh review must evaluate these corrections and the production/interface
changes. It must not treat the old review's recommendation to retain a
code-owned table as authority over the later canonical bundle ownership.

### Revision 2 review: bounded B1 correction

The [revision 2 review](https://github.com/samovers/OFARM2/pull/359#pullrequestreview-5125869052)
at `1473a4c16d8e716b03a3c36c2e36114e6e9fb255` identified one missing
fresh-approval provider handshake within G3. Sections 6–8 now distinguish
non-decision preparation, consumer-built uncommitted finalization evidence,
and complete final evaluation with exact requester-basis/window equality.
AUTH-015–018 specify focused verification through the same production-bound
provider. This is an interface/conformance correction to the existing pinned
PR #20 protocol, not new law or transaction-coordination ownership.

Re-review is limited to that fix and affected invariants unless new evidence
demonstrates a broader defect. The earlier nine findings are not reopened.
The scope, canonical-readiness and concrete-interface gates remain open; this
correction does not claim a new zero-Blocker review or implementation approval.

## 12. Expected implementation areas and code excellence

Only this existing RFC changes in the current design revision. It remains
useful after the PR because it records the authorization/transaction split
and why the old production assumptions were rejected.

Expected later areas, not a path allowlist:

- `kernel/production_authorization.py`: one small evaluator with immutable
  bound input/output and selected-proof values;
- a narrow production tenant authority-read adapter, plus the necessary typed
  hook in `kernel/tenant_uow.py`;
- mechanical composition in `kernel/application_runtime.py`, and exact
  architecture registration without weakening its legacy/SQL firewall;
- focused evaluator, PostgreSQL, composition, route-closure and UoW tests;
- Kernel navigation, this RFC, and mechanical test inventory changes.

No legacy caller migration/deletion, reference/schema/migration change,
command writer, runtime selector adaptation, principal/authentication edit,
audit-custody change or profile activation is included. Discovery of a file
inside the approved boundary can travel; discovery of a new authority cannot.

| Code-excellence invariant | Planned assessment |
|---|---|
| EXC-001 — one authoritative path | One canonical semantic source and one production authorization implementation shared by non-decision preparation and final evaluation; the transaction owner constructs evidence from those values, not a second path-selection/cutoff engine. |
| EXC-002 — no avoidable duplication | No handwritten second matrix, compatibility authority API, extra durable decision store, retry ledger, or copied schema inventory. |
| EXC-003 — direct invariant trace | AUTH-001–018 map the typed entry, bound reader, preparation/final-evaluation handshake and evidence constructor to focused tests. Missing real reachability blocks completion. |
| EXC-004 — delete superseded owned paths | Withdraw the old plan; introduce no legacy compatibility path. The quarantined legacy system is not an owned production path and is not deleted as an unrelated migration. |
| EXC-005 — abstractions pay rent now | Bound input/output prevent mixed tenant/rule/attempt facts; distinct preparation, prospective-evidence and prepared-decision values prevent authority/persistence confusion in the required fresh-approval handshake. A narrow reader contains existing connection authority. No generic policy engine, plugin registry, public SQL facade or future dispatcher. |
| EXC-006 — simpler credible alternative | Adding a table to kernel.authority fails production isolation and canonical ownership. A pure helper alone fails the bound production-read outcome. A new transaction owner is unnecessary and crosses into #178. The proposed provider plus typed reader is the smallest plausible slice, subject to gate G3. |

## 13. Gates, provisional posture, and review state

This is a **provisional design**, not permission for a temporary runtime.
Planning against exact approved candidate semantics is useful before
deployment, but executable bytes and concrete trusted interfaces are absent.
No fallback, weakened proof, old-schema compatibility or synthetic authority
path is authorized.

| Gate | What must be settled before implementation approval |
|---|---|
| G1 — Delivery scope | Steward explicitly accepts the issue amendments in section 2, including prepared-versus-durable evidence and production-only callers; full evaluation coverage remains explicit. |
| G2 — Canonical readiness | Complete the governing staged sequence and replace missing entries in section 5 with reviewed exact promoted/extracted bytes and provenance. Semantic approval alone is insufficient. |
| G3 — Concrete trusted interface | Close the production principal/representation/CP3 input mapping, policy selection compatibility, coherent typed read/snapshot plan, deadline source and complete guard handoff. Include the sections 6–8 fresh-approval handshake: non-decision preparation, distinct prospective uncommitted evidence, exact candidate/final requester-basis and validity equality, and cross-attempt/mode refusal, verified by AUTH-015–018 through the same provider. Demonstrate independently useful production-provider completion without inventing another authority owner. Split any demonstrated new boundary before editing it. |
| G4 — Fresh OFARM2 approval | Review this corrected Phase A to zero Blockers, then present a complete decision card naming existing PR #359 and obtain the required exact later task-user approval. No such card is issued by this revision. |

Evidence requiring redesign: a machine binding contradicts the approved
candidate; the exact reader/guard/proof needs a new authority; full admitted
coverage cannot be supplied by one coherent provider; or the durable-trace
criterion is retained. The upgrade path is a reviewed revision with exact
bindings and concrete interfaces, and a new semantic decision version where
required—not a compatibility fallback.

Separate downstream work: #178 command identity/atomic consumption/results;
#176 temporal Delivery selection after its prerequisites; #177 output and
disclosure planning; #175 grant mutation/bootstrap children; #193
disaster/store-loss recovery. The old command successor is a compatibility
gate for its consumer, not a reason to amend approved canonical PR #26.
No new Delivery issue is created in this revision.

Review disposition: REVIEW_PENDING, with G1–G4 preventing an implementation
approval packet. The old nine findings have proposed corrections, not a new
zero-Blocker sign-off. Exact private names and test-file partitioning are
Preferences only after the substantive interface is settled.

## 14. Verification and handoff

For this design-only head: mandatory package check, architecture check,
temporal candidate and decision-log checks, whitespace check, exact
base-to-head path inspection, canonical-source comparison, and review of the
issue-amendment/consumer ownership wording. Record actual results in the PR
description with the new head; do not reuse tests from the old Phase A head.

Do not request an expensive hosted baseline, admission, or publication for this
design-only revision. Automatically started jobs do not supply semantic
approval and are not monitored as implementation evidence.

After approved implementation: run the focused AUTH cases, real PostgreSQL
binding/currentness cases, production composition/route closures, package,
architecture, pinned Ruff, temporal and test-inventory checks. Then follow
root AGENTS.md: exact-head content review, applicable baseline admission,
complete deterministic review baseline and separate publication/receipt
verification, final scope/excellence packet, mandatory yield and later
exact-head user merge authorization. Phase A approval does not authorize
merge, and neither approval authorizes deployment.

Scope confirmation: the current PR revision changes authorization design only.
It proposes one production authorization boundary and explicitly leaves
transaction coordination, protected effects, selection authority and temporal
persistence with their own owners. No cross-boundary implementation is hidden
in this plan.

What is next: re-review the revision 2 B1 correction and affected invariants;
resolve the still-open scope, canonical-readiness and concrete-interface gates
before a fresh #359 decision approval and runtime edits.
