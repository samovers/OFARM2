# OFARM Production Authorization Provider — Phase A RFC v0.1

Date: 2026-09-07

Design revision: 6. This addresses the non-blocking reader-failure
clarification in the focused revision 5 review at
`87584f2e368fc791f0c12e4288885dc5425ea287`. The proposed interface, trusted-source
map and transaction handoff remain intact, including the earlier reviewed
approval handshake. Missing source factories, machine contracts and commit
guards remain prerequisites, not newly supplied infrastructure.
The unapproved legacy proposal at
`178f150ce56f1bdad96330ba845d210ee0911f2a` remains superseded. No accepted OFARM
law changes.

Status: revision 6 clarification review pending; G1 scope amendment applied;
G2 canonical readiness and G3 implementation prerequisites remain open.
No OFARM2 semantic approval, runtime implementation, baseline
admission, merge, current/default promotion, or deployment is authorized.

Delivery issue: [OFARM2 #353](https://github.com/samovers/OFARM2/issues/353).
Tracking epic: [OFARM2 #175](https://github.com/samovers/OFARM2/issues/175).
The one existing draft PR is [#359](https://github.com/samovers/OFARM2/pull/359).
Inspected/integrated OFARM2 main: `ff092c414db9fa24dbd6ab86c7722db89e0c95b5`.
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
promise a durable outcome. Issue #353 now explicitly distinguishes these
owners, while retaining full admitted action/evaluation coverage.

## 2. Applied amendment to issue #353

The task user directed applying the four-point scope amendment. The
[issue amendment record](https://github.com/samovers/OFARM2/issues/353#issuecomment-5566519997)
preserves the original issue text and that limited instruction. This is the
current work definition, not formal implementation approval:

| Superseded requirement | Applied replacement and consequence |
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

G1 is satisfied as an issue-scope editing step. The later complete #353
decision card must include this amended scope and receive its own exact
task-user approval. #353 cannot close on this RFC, types alone, one action, or
blanket refusal: it must prove an independently usable production provider
with the complete admitted coverage. Any later request for provider-owned
durability changes this boundary and requires re-planning, not a second
transaction owner or quiet absorption of #178.

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
- `kernel/production_oidc.py` verifies a required JWT `exp`, but the returned
  `VerifiedIdentity` carries only equality policy, issuer and subject.
  `PrincipalAuthority` carries its own `valid_from` / `valid_until`. Neither
  object supplies the complete human-session or protected-effect attempt
  interface. Credential expiry is not automatically a human-session deadline.
- Main includes the separately reviewed tenant-challenge observation and
  signing-deadline work. Challenge creation time and capability expiry are
  not a protected-effect transaction deadline or a complete commit guard.
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
authority reads, prepared evidence construction, a reviewed typed facade and
architecture-contract extension, and production composition/tests needed to
prove that capability. No independent authority, custody, persistence, or
command-execution capability travels with it.

| Owned fact or operation | Owner |
|---|---|
| Action meaning, rule fields, actor/finalization semantics, path aggregation, reason ranks, evidence schemas and hash projections | Canonical OFARM; exact promoted/extracted versions |
| Credential verification, identity binding, tenant capability, key custody | Existing authentication, principal, binder, and KMS boundaries; unchanged |
| Party classification and authority/representation/CP3 proof evaluation | This provider applies the bound contracts to trusted identity and governed evidence; it cannot mint missing identity/actorship authority |
| Policy/command selection and immutable runtime component identity | Existing separately reviewed selection/RuntimeBundle owners |
| Database session, transaction identity/finalization, isolation, complete commit guard and uncertainty reconciliation | Existing transaction owners and later #178 work; no new owner here |
| One current evaluation, selected sufficient path, complete prepared decision evidence and read obligations | This provider |
| Execute the rule-selected final authority-relevant projection, compute its JCS/SHA-256 digest, and compare it with the verified challenge digest | This provider, using its current typed authority snapshot; canonical OFARM owns the projection and JSON Pointer semantics |
| Capture the authenticated human act; render/retain its display; persist generation invalidation and issue a replacement challenge | Existing human-act, display/retention and transaction owners; the provider verifies their bound proof and reports invalidity, but does not perform these operations |
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
- add the reviewed typed facade/architecture-contract extension and production
  composition hook, tests, documentation and mechanical inventory changes.

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

Extending the checker's exact TenantUnitOfWork facade is also substantive,
not mechanical registration. It may remain inside this authorization boundary
only if it exposes the bounded provider without adding connection, tenant,
persistence or selection authority. Section 12 records the current shape and
size constraints; G3 requires a reviewed concrete extension before Phase B.

## 5. Canonical sources and readiness inventory

The following are exact semantic planning sources, **not executable authority**:

| Candidate | Exact reviewed source head | Relevance |
|---|---|---|
| [OFARM PR #11](https://github.com/samovers/OFARM/pull/11) | `03a21f669ee04f96d444e14f00ae7212cab04803` | Complete action rules, principal/CP3/finalization axes, paths, snapshot, v0.2 evidence and staged delivery |
| [OFARM PR #17](https://github.com/samovers/OFARM/pull/17) | `9ef08030b25eb3db1c2da14d6595300198384ff2` | Human final-review protected-effect planning source |
| [OFARM PR #20](https://github.com/samovers/OFARM/pull/20) | `98f8c4fafbae42c8f7fd931f43f53adcb4733713` | Human-finalization transaction protocol; excludes NOT_REQUIRED |
| [OFARM PR #23](https://github.com/samovers/OFARM/pull/23) | `622376e2998cf8b3954ca19e81d2cce6fd57e5fe` | AssertionRecord submission protected-effect contract |
| [OFARM PR #26](https://github.com/samovers/OFARM/pull/26) | `e042efa2911b2ef0a61603b8e0adaa6911c03ac0` | NOT_REQUIRED atomic protocol and first operation-claim handoff |
| [OFARM PR #28](https://github.com/samovers/OFARM/pull/28) | `4e186aab5c238215906fcf9b24ce74443abb6f72` | Exact SharingGrant TERMINATE protected-effect planning source; not a revocation command in this PR |

The [PR #26 approval](https://github.com/samovers/OFARM/pull/26#issuecomment-5560085396)
closes that candidate's Phase A semantic review. It does not merge its bytes,
materialize contracts, promote currentness, or approve OFARM2 implementation.
The [PR #28 approval](https://github.com/samovers/OFARM/pull/28#issuecomment-5570649266)
has the same limited effect for its candidate. Its completion does not change
the first implementation consumer from operation-claim submission to grant
revocation.

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

Use one production-only evaluator and one narrow tenant read adapter. The
following is a concrete local interface proposal for review, not executable
code or new canonical record schemas. Exact machine bindings and the named
upstream factories remain G2/G3 dependencies.

### Closed entry points and trusted construction

The public work surface gains exactly two synchronous methods:

```python
def prepare_authorization(self, call: AuthorizationCall) -> PreparationOutcome:
    ...

def evaluate_authorization(
    self,
    call: AuthorizationCall,
    finalization: ProspectiveFinalization | None = None,
) -> EvaluationOutcome:
    ...
```

They are reached through `ApplicationRuntime.tenant_unit_of_work`, its existing
security-audit wrapper, and the manager-created active `TenantUnitOfWork`.
The manager injects one private frozen pair of closed callables,
`_AuthorizationCalls`, bound to the authenticated principal, exact
TenantBinding and the same connection. The UoW exposes neither this pair nor
an independently usable provider handle. Both calls use the same evaluator
for policy, extraction, projection/comparison, paths and cutoffs.

Each method checks active and not rollback-only before invoking its private
callable. `_finish` seals the new dependency as well as the existing ones.
Retaining a bound method cannot bypass those checks. Results contain immutable
data only, never callables, cursors or a connection. Unexpected database or
adapter failures mark the existing `__rollback_only` flag before re-raising
into the UoW rollback/discard path. Catching that error in consumer code cannot
make the UoW committable again. The provider cannot swallow a broken transaction
and report a durable refusal.
Ordinary typed preparation/ingress refusals and canonical non-ALLOW decisions
do not themselves assert rollback or durability.

`AuthorizationCall` has three closed roles, not a general proof dictionary:

| Local member | Content and admission rule |
|---|---|
| `attempt` | Owner-issued protected-effect attempt frame: exact operation/generation where applicable, attempt/transaction binding, fixed transaction deadline, trusted time/session/act and final-snapshot/guard inputs required by the selected protocol. It must match this bound UoW. |
| `selection` | Owner-issued exact command/action, policy/rule and binding-manifest selection. Verify its provenance, content and compatibility; a matching action string alone is insufficient. |
| `effect_intent` | Exact full intent bytes and their claimed identity/digest. The provider validates and derives its authorization view itself. Owner-completed fields must already be bound by the command protocol. |

These names describe local envelopes around admitted contracts; they do not
duplicate the contracts' field inventories. Python type/frozen-object checks
prevent accidental mixing, not forgery by a caller. Production composition
must obtain `attempt` and `selection` from their reviewed owning factories,
and the provider verifies their binding to its privately held principal/UoW.
Those complete factories are not present at this base. A constructor in an
HTTP handler, test fixture or this evaluator is not a substitute.

There is no caller-set tenant, resolved actor kind, authority subject, stage,
condition mask, approval mode, policy URL, grant list or equality flag. The
principal comes only from composition. Party classification uses the exact
anchored governed Party; representation and CP3 need their own evidence.
Authority subject is derived per candidate path, never selected globally
before path resolution. Optional AI metadata remains authority-inert.

`ProspectiveFinalization` carries complete candidate bytes, immutable identity
and digest, plus their exact attempt and, for fresh approval, preparation
binding. It is the only prospective-proof role accepted by this API; it cannot
replace persisted authority sources. Supplying `None` never disables a rule's
human requirement. Whether an absent candidate permits a canonical
REQUIRE_HUMAN_APPROVAL decision or causes protocol refusal follows the admitted
rule/profile, not a caller-selected mode. Preparation is only for the post-act
fresh-approval handshake; direct-human and NOT_REQUIRED use final evaluation.

`PreparationOutcome` is either the complete non-decision view described below
or a typed preparation refusal. `EvaluationOutcome` is either a truthful
ingress/infrastructure refusal or a complete prepared decision with immutable
read/guard obligations. These are disjoint types: no shared `allowed` flag,
fabricated canonical DENY on malformed ingress, or `committed` field. Neither
successful result is portable to another attempt or a closed UoW.

### Trusted-source map and missing producers

| Required fact | Existing source and provider use | Remaining owner dependency |
|---|---|---|
| Authenticated Party and tenant anchor | `AuthenticatedPrincipal` / `PrincipalAuthority`, checked against `TenantBinding` and exact Party record identity/digest | Map the admitted principal-resolution revision and its validity interval to canonical evidence; do not treat the anchor as complete representation/CP3 proof. |
| Natural-person representation or software actorship | Read immutable governed evidence and apply the selected contracts; Party classification and sponsorship alone confer no representation/delegation | Inventory exact current representation/CP3 bindings and their provenance. PR #11 says the current CP3 envelope is semantically sufficient; this is not permission to change it. |
| Human session and exact act | The existing verifier establishes issuer/subject; owner-issued act proof must bind the authenticated session, act bytes and server-observed time | No complete session/act proof factory is present. Its owner must define the mapping and custody; this provider must not reparse an unverified JWT or copy verifier logic. |
| Transaction attempt, deadline, final snapshot and protection | Same bound connection supplies tenant/full-transaction identity; the protected-effect protocol owns admission and time/guard proof | Current UoW has no complete attempt/deadline/guard factory. Tenant challenge time, token lifetime, batch allocation and `bound_at` are not substitutes. #178 must resolve its transaction-side interface. |
| Command/action and authorization policy | Consume exact verified selections and content-addressed admitted bytes | Current fixed selector selects the incompatible old command in section 9, not a general v0.2 policy. Its owner must supply a compatible reviewed selection; this PR cannot reinterpret it. |
| Canonical authority snapshot/currentness and source visibility | Provider verifies canonical proof against coherent tenant reads and exact source/batch provenance | G2 must supply exact bindings; G3 must identify how existing sources prove every required watermark/visibility fact. A SQL snapshot label does not fill this gap. |
| Challenge, display and act prerequisites | Read exact immutable references and verify owner-supplied retrievable display bytes and metadata | Human protocol/display/retention owners supply real proof and lifecycle eligibility. No ceremony, renderer, retention store or generation writer is added here. |

For time, follow PR #11 section 18.2 precisely: principal-resolution/session
validity ends contribute where required; an explicitly unbounded governed
interval contributes no cutoff. A missing required end is not an unbounded
interval. JWT `exp`, JWKS cache expiry, capability expiry and interactive
session expiry are distinct facts; this RFC creates no rule equating them.
The owning policy must settle any required mapping. Once proof is available,
the provider computes the canonical minimum using exclusive UTC ends, not a
locally chosen authorization TTL. Missing producer authority prevents a usable
handoff; a proved expired fact follows the canonical evaluation disposition.

### Concrete tenant read plan and snapshot limits

The initial closed reader proposal is one parameterized SELECT on the bound
connection per authority observation. No public SQL, filter, table-name or
transaction callback is added. Start with complete tenant-visible canonical
record/reference sets, not a request's grant candidates. This deliberately
simple plan avoids depending on an unproven authority search index:

1. Capture `ofarm.current_tenant_context()` and the current full transaction
   identity in that statement; compare them with the privately held binding
   and admitted attempt. Existing RLS remains an independent backstop.
2. Read canonical-lane `ofarm.kernel_record` rows for that tenant, including
   exact record kind/ID, schema digest, payload/digest, batch ID/full XID,
   runtime-bundle digest and record time. Read their
   `ofarm.kernel_record_reference` rows and matching `governed_write_batch`
   provenance in the same statement. Do not discard revoked/rejected paths
   before evaluation. Draft-lane rows cannot become canonical authority.
3. Preserve exact reference role, JSON Pointer, ordinal, extractor
   version/digest and target lane. Verify the derived reference index against
   source payload and its admitted extractor; an index row is not authority
   independently of that source. Validate relevant global content against
   exact selected/manifest-bound content, never a caller URL.
4. Parse and validate required record families against admitted schemas;
   verify identity and digest under each family's exact hash projection.
   `payload` is JSONB, not preserved original wire bytes: do not hash arbitrary
   database serialization or trust `payload_digest` without verification.
   Missing, malformed or inconsistent required proof cannot be silently
   removed to make a set look complete.
5. From this coherent capture derive the complete rule-selected resource,
   principal/representation/CP3, role/grant/delegation/sharing, revocation,
   condition/evidence/purpose and sovereignty inputs. Include all facts
   required by rejected-path diagnostics and the relevant-state projection,
   plus exact absence and complete-set claims, not just the winning path.
6. Verify every source's required snapshot visibility/currentness proof.
   READ COMMITTED sees this transaction's own writes too: a same-attempt row
   cannot be labelled an already committed prerequisite. Use the separate
   prospective finalization input only in its admitted role. An MVCC label,
   maximum knowledge position or immutable row alone is not the governed
   `authorityEvaluationSnapshotRef` required by PR #11 section 16.1.
7. Return an immutable observation containing proved facts, explicit missing
   or invalid proof with its affected roles, and the actual read footprint.
   Assert snapshot availability, visibility and complete sets only where
   proven. Missing canonical proof is not a successful complete snapshot,
   even when SQL rows are internally consistent; preserve the failure facts
   for canonical evaluation rather than inventing snapshot evidence or a
   standalone canonical snapshot record family.

The reader distinguishes an observation from an operational failure; it does
not reduce every missing proof to a database error. The evaluator owns the
disposition under pinned PR #11 section 15:

| Observed situation | Reader-to-evaluator mapping |
|---|---|
| Global prerequisites pass and a completeness-proven observation contains no applicable path, including all candidates being inapplicable | Produce canonical `DENY` / `NO_AUTHORITY_BASIS`, with no selected path; not an infrastructure refusal. |
| An authorization-global prerequisite, such as authority-snapshot availability, is unproven | Preserve every independently established failure; apply canonical global DENY-before-REQUIRE_REVIEW ordering and mark dependent checks `NOT_EVALUATED`. Do not infer target or tenant failure from a prerequisite that was never proved. |
| One path is revoked, unsupported or otherwise fails while another is independently sufficient | Preserve the exact per-path dispositions and aggregate canonically. A path-local failure cannot become a whole-read infrastructure refusal or override another sufficient path. |
| The database or adapter actually fails to perform the observation | Preserve infrastructure failure and the existing rollback-only/discard discipline. Do not fabricate a canonical decision or durable result. |

An empty result without completeness proof, or an incomplete/overflowed read,
is not proof that no authority exists.
Likewise, malformed source evidence is not automatically a failed adapter:
report the affected fact/role and let its exact canonical binding determine
whether the failure is global or path-local. Ingress failures remain outside
this lattice as section 7 specifies. Any prepared non-ALLOW decision must
still meet its admitted failure-evidence contract truthfully; missing evidence
cannot be repaired with a placeholder snapshot. G3-READ must settle that exact
failure encoding when G2 supplies the machine bindings. These distinctions
add no reason code, schema, outcome or alternative authorization engine.

The statement must have deterministic ordering and server-side row/byte/work
bounds with explicit overflow detection. Overflow refuses the whole capture;
LIMIT without a completeness/overflow check is prohibited. Materialized
subsets and joins must not multiply or truncate away reference/negative proof.
The exact SQL, bounds and representative tenant-size evidence remain a G3
implementation-plan item once G2 fixes the record bindings. Optimizing to
smaller family/reference closures is acceptable only with the same provable
completeness. A tenant scan that makes the intended production workload
unusable does not satisfy #353 merely because it fails closed.

This is a concrete query shape and verification plan, not a claim of an
implemented or measured reader. Sequential ordinary READ COMMITTED queries
are not a substitute for one coherent observation. A coherent observation is
not a commit guard: the transaction owner must protect the complete footprint.
For preparation/final evaluation, its interface must establish the same final
snapshot and protection context required by PR #20. Merely running the SELECT
twice cannot prove that continuity. Any loss of that proof prevents successful
finalization; any relevant drift follows section 7. The provider still owns
final projection recomputation, never a consumer-supplied equality assertion.

### Preparation is distinct from a prepared decision

For the post-act `FRESH_HUMAN_APPROVAL_REQUIRED` protocol, the same provider
offers a bounded non-authoritative preparation operation before the consumer
can construct prospective approval evidence. It requires the trusted
rule-selected mode, admitted operation/generation and exact authenticated
human act, challenge/display bindings, final snapshot and complete guards.
It is not challenge issuance or a token retained across human think time.

Its immutable local preparation result supplies one bound authorization view
and all provider-derived bindings needed by the complete approval profile in
canonical PR #20 section 9.1 and PR #11 section 18.3:

- tenant, operation/generation, attempt, action/finalization mode, exact human
  act, effect-intent schema/ref/digest, extractor and policy/rule bindings;
- derived authority target, typed inputs, effect subject and extracted
  scope/twin/time/purpose, with their exact resource revisions/proof bindings
  and derived-view digest;
- requester and intended natural-person approver identities, represented Party
  and immutable representation basis where applicable, canonical candidate
  requester path/basis and independently eligible same-action approver path;
- the provider-computed final rule-selected relevant-state projection and
  `authorityRelevantStateDigest`, verified challenge digest, and both complete
  challenge/final snapshot refs and proof bindings;
- verified exact challenge/display/act and rule-selected separation bindings;
  and
- complete cutoff inputs, `approvalExpiresAt` and candidate
  `decisionValidUntil`, computed in section 7.

This is a typed view of the exact canonical profile requirements, not a second
handwritten schema or permission to omit any canonical field. A successful
preparation proves the required digest equality; it never copies a consumer's
assertion that the two projections match. These values are evidence-construction
inputs, not an authorization outcome. Preparation emits no decision result,
decision trace, decision-bundle digest, consumption, effect, durable claim or
portable path outcome. Failure returns a typed preparation refusal, never a
successful candidate with missing proof or an invented authorization result.

The consumer uses those provider-derived values to construct and hash the
complete mode-correct finalization-evidence candidate together with the exact
act/display/transaction prerequisites supplied by their owners. It does not
duplicate authorization-view extraction, relevant-state projection/comparison,
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

The interface follows [canonical PR #20 section 11 at its pinned head](https://github.com/samovers/OFARM/blob/98f8c4fafbae42c8f7fd931f43f53adcb4733713/package_meta/history/clean_baseline_migration/phase_reports/governed_human_approval_transaction_and_consumption_protocol_rfc_candidate_v0_1.md#11-required-post-act-revalidation)
and [PR #11 sections 16.1 and 18.3](https://github.com/samovers/OFARM/blob/03a21f669ee04f96d444e14f00ae7212cab04803/package_meta/history/clean_baseline_migration/phase_reports/authorization_constraints_and_decision_evidence_rfc_candidate_v0_2.md#161-authority-evaluation-snapshot).
With a verified rule and complete current authority facts, the provider
performs this post-act sequence under the same final snapshot and guards:

1. Revalidate the exact authenticated act/session, requester and intended
   natural-person approver, representation, immutable challenge and
   rule-selected separation/eligibility bindings. Verify the acknowledged
   display's exact retrievable bytes, ref/digest and media type, renderer
   identifier/version/digest, display-policy ref/digest, locale, timezone and
   evidence-retention policy binding. Unavailable or changed bytes, renderer
   or display metadata cannot support successful preparation. Verify trusted
   `humanActedAt` precedes the exclusive challenge and reservation cutoffs,
   and check all applicable current session/transaction validity. Client time
   cannot establish timeliness. This verifies owners' proof; it does not add
   rendering, act capture, storage, retention policy or key-custody operations.
2. Compute the final authority-relevant projection from the provider's current
   typed snapshot using the exact rule-owned projection/JSON Pointers, then
   compute JCS/SHA-256 and compare with the verified immutable challenge
   `authorityRelevantStateDigest`. Include every rule-selected authority-path
   and separation fact through the shared rule/path implementation, not a
   coordinator-supplied projection, digest or equality flag. Record the final
   projection/digest and both full snapshot refs. This comparison must pass
   before continuing to candidate requester/approver selection below.
3. Use the shared authorization implementation to evaluate every global and
   per-path condition except the still-outstanding fresh-approval condition.
   No authorization result or decision bundle is emitted.
4. Require global preconditions to pass and apply the canonical lattice and
   path tuple to otherwise-sufficient requester paths. Determine the candidate
   requester path and basis that would otherwise require fresh human approval.
5. Independently determine the canonical natural-person approver path that
   satisfies every non-finalization condition for the same action, target,
   typed inputs, effect subject, scope, twin, purpose, tenant/sovereignty, Party
   posture and intent/derived-view digests. Enforce the exact
   `approvalSeparationPolicy`; sponsor status alone remains insufficient.
6. Collect all rule-required cutoffs, including the trusted transaction and
   session deadlines, candidate requester and applicable approver paths,
   representation, sources, policy/snapshot, resources, evidence and
   sovereignty inputs. A required missing cutoff fails preparation.
7. Compute `approvalExpiresAt` under the exact approval profile, then compute
   candidate `decisionValidUntil` with the canonical minimum-cutoff function
   using that requester path and `approvalExpiresAt`.

A relevant-state digest mismatch returns a typed stale-challenge preparation
refusal: no successful preparation, prospective approval admission or ALLOW
from that act. This holds even if the requester basis and validity window
would otherwise remain sufficient. The transaction owner must invalidate the
act/generation through PR #20's failure protocol; only after the required
terminal record is durable may it issue an eligible replacement generation,
new challenge and new human act. The provider does not persist that transition.
Unrelated history outside the exact rule-owned projection does not invalidate
the challenge: full snapshot refs may differ while the relevant digests match,
provided every other final check, cutoff and commit guard passes.

`APPROVAL_CHALLENGE_STALE` identifies the canonical lifecycle diagnostic, not a
new authorization outcome or a decision emitted by preparation. If complete
canonical evaluation produces refusal evidence for an otherwise sufficient
path lacking approval, `HUMAN_FINAL_ACTION_REQUIRED` remains the sole primary
reason for `REQUIRE_HUMAN_APPROVAL`; stale-challenge detail is diagnostic only.
Other independently established failures still follow canonical aggregation.

Every current fresh-approval row selects `SAME_PRINCIPAL_ALLOWED`: the same
natural person may perform the challenged act if independently eligible under
the full lifecycle. `DISTINCT_APPROVER_REQUIRED` and its
`APPROVAL_SEPARATION_UNSATISFIED` diagnostic remain reserved; this plan neither
activates them nor requires an extra person for current rows. Direct-human
finalization instead verifies its exact direct-principal act and trusted
`humanActedAt` within the applicable session and final transaction cutoffs;
it gains no synthetic challenge, reservation or separate approver.

The consumer binds the full preparation values into the prospective approval
profile before computing its identity and digest. The candidate is still
uncommitted and non-consumable. Raw human-act metadata or an approval ID alone
cannot replace the complete candidate.

Final evaluation verifies the candidate's schema, identity/digest and exact
tenant, operation/generation, attempt, authenticated act, principal and
representation, challenge/display, policy/rule, intent, snapshot/relevant-state,
requester/approver basis and expiry bindings. The provider itself recomputes
the final rule-selected projection/digest from complete current facts and
requires equality with both the challenge and prepared/candidate values;
verifying consumer-recorded equality alone is insufficient. It revalidates
act timeliness, display and separation proof and performs the complete
canonical evaluation, including fresh-approval validity. Relevant drift
cannot be repaired by rehashing the candidate; it follows the stale-challenge
failure above. The candidate basis is a binding to verify, not a filter
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

Preparation and final evaluation share one implementation for policy,
extraction, projection, paths and cutoffs. They differ in allowed outputs and
the explicit protocol point at which prospective approval can be checked.
No coordinator-owned policy engine or caller-selectable condition mask is
introduced.

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

For post-act fresh-approval finalization, replace the ordinary EVALUATED step
with the handshake: `CURRENT_FACTS_PROVEN -> NON_DECISION_PREPARATION ->
CONSUMER_BOUND_PROSPECTIVE_EVIDENCE -> FINAL_EVALUATION_AND_EQUALITY_CHECK
-> PREPARED_EVIDENCE -> HANDED_TO_OWNING_TRANSACTION`.
Only that final operation may construct the decision bundle; only a valid
ALLOW satisfying the equality checks is eligible for successful finalization.
The consumer-owned middle step constructs/hashes evidence; it does not persist
it, derive another authorization view/projection, select authority or calculate
a competing validity window.
NON_DECISION_PREPARATION is never interchangeable with PREPARED_EVIDENCE.

Ingress/infrastructure failure does not invent a valid authorization result.
A valid non-ALLOW result can reach PREPARED_EVIDENCE, but never an effect or
consumption transition. Closing/refusing the UnitOfWork invalidates further
provider use, including its preparation and prospective-evidence bindings.
There is no provider-owned COMMITTED state. Rollback discards prospective
evidence; a new attempt cannot reuse it even if its old expiry has not passed.

That lifetime rule does not forbid an exact retry of the original human act
and intent when the consumer admits it under PR #20 sections 9.1, 9.2 and 16.
The same `humanActSubmissionId` must retain the same complete act bytes/digest
within the logical operation/generation. The consumer first looks up the
authoritative outcome: an already committed exact retry returns the stored
receipt without new evaluation, effect or consumption; an unresolved attempt
blocks reapplication. After conclusive rollback, an eligible retry repeats all
current checks and creates fresh attempt-bound preparation and prospective
evidence. It may reuse the original act only while its challenge/generation
and session remain eligible (or the direct-human session where applicable).
An invalidated challenge cannot be rescued by exact retry. Admission, lookup,
invalidation and persistence remain consumer-owned, not provider operations.

Every prepared decision binds the current transaction attempt and full
intent. Compute decisionValidUntil as the canonical minimum of the trusted
transaction deadline, session/principal, applicable source/representation,
policy/snapshot, resource/evidence/sovereignty and approval cutoffs. Ends are
exclusive; explicitly unbounded governed intervals add no cutoff. Required
missing/unparseable ends or a minimum not later than the
evaluation time produce no consumable decision. A newly admitted attempt needs
a fresh evaluation; returning an existing committed receipt is not another use
of old authority and does not require another evaluation.

The provider describes every authority fact and absence/set predicate that
must remain valid. The transaction owner must protect and recheck that
complete footprint together with the other gates and writes. A changed or
unprotected footprint prevents consumption; a fresh evaluation cannot merely
relabel the stale trace.

This PR does not claim that READ COMMITTED, the tenant-binding lock, or batch
allocation already provides that protection. Changing isolation, adding a
guard protocol, or inventing authoritative commit-status lookup is outside
this PR. #178 must close its own concrete implementation design.

### Closed read-to-guard handoff

The prepared decision's local handoff is bound to the exact tenant, operation
and attempt, intent, selected command/policy, canonical snapshot, complete
request/result/trace bytes and decision-bundle digest. It also carries
`decisionValidUntil` and the complete provider-observed footprint. The wrapper
is internal data, not another persisted ledger, a new canonical proof schema
or authority to execute SQL supplied by the provider.

The footprint has three closed forms; none can be replaced by a boolean
`guarded` supplied by the caller:

| Form | Required meaning | Owning transaction must establish |
|---|---|---|
| Exact record/content fact | Tenant, family, immutable ID/digest, relevant revision/lifecycle and source visibility; includes selected and rejected bases required by canonical evidence | The same fact remains admissible through the protected effect, or the consumer refuses/restarts under its protocol. |
| Absence or complete set | The rule-selected predicate, its exact tenant/resource scope, expected complete membership and canonical currentness proof; includes applicable revocation, competing authority and prospective-subject absence | Protection against insertions and other changes to that predicate, not just locks on the rows that happened to exist. |
| External binding or time | Exact selected policy/currentness, identity/session/act/display proof and every required exclusive cutoff not established by tenant rows | Its owning authority's admitted validity/recheck mechanism and timely final consumption; a database row lock alone is insufficient. |

These forms identify obligations, not new predicate semantics or a generic
query language. The bound rule/profile owns the exact predicates and canonical
evidence mapping. Provider completeness tests compare the entire handoff with
its observed footprint; the consumer must reject an omitted, unknown,
mismatched or unprotectable obligation before consumption. No successful
handoff may silently reduce this to the selected grant's ID and expiry.

Before Phase B, G3 must connect these forms to the transaction owner's actual
typed attempt/guard input and exact canonical profile. In particular it must
prove final-snapshot continuity across preparation and final evaluation,
external validity and set/absence protection under concurrency. No such
complete production interface exists at the inspected base. This RFC chooses
the producer/consumer split and required contents; it does not select locks,
change isolation or certify a fictional guard receipt. Tests with handcrafted
frames can exercise provider logic but cannot close this source/guard gate.

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
| AUTH-014: production is legacy-free and commands remain closed | Application/UoW composition and architecture checker | Exercise real composition and all governed route closures; a legacy import, unreviewed facade shape/dependency, raw-handle/SQL escape or newly enabled command fails verification. Verify the exact reviewed facade and module/group budgets without weakening tenant containment. |
| AUTH-015: fresh-approval preparation is non-authoritative | Same provider's bound preparation operation and shared rule/extraction/projection/path/cutoff implementation | With valid post-act inputs, obtain the complete bound view, projection/digest, candidate bases and expiry values, but no decision result/trace/bundle, consumption, effect or durable claim. Fail a global/path condition or omit a cutoff: no successful preparation. Passing preparation as a decision or requesting an approval-skip flag cannot authorize anything. |
| AUTH-016: prospective finalization evidence has an explicit, restricted input role and complete verified bindings | Same provider's preparation output, final-evaluation input and evidence verifier | Build the full canonical approval solely from provider-derived authority fields and exact owner-supplied act/display/transaction prerequisites; schema-check and hash it without a second extractor/projection/path/cutoff engine. The valid uncommitted candidate can produce prepared ALLOW when every check passes, with no durable claim. Wrong target/input/subject, representation, bytes/digest, act, snapshot, intent or approver cannot support ALLOW. Unavailable/changed display bytes, renderer/version/digest, display policy, locale/timezone or retention binding fail preparation/final validity. A trusted act at an exclusive cutoff fails; a client timestamp cannot repair it. A same-person independently eligible challenged act succeeds under SAME_PRINCIPAL_ALLOWED; omitting separation proof or activating the reserved DISTINCT_APPROVER_REQUIRED posture fails. A prospective grant cannot replace governed prerequisite proof. |
| AUTH-017: candidate and final requester basis/window must match exactly | Shared canonical selection/cutoff logic and final equality checks | Substitute a different otherwise-eligible requester basis, or shorten/extend the prospective decisionValidUntil even within the transaction deadline. Final evaluation cannot force selection, rewrite the candidate or accept a different returned window; no ALLOW based on that candidate or successful finalization handoff. |
| AUTH-018: preparation and prospective evidence are attempt- and mode-bound, without prohibiting canonical exact retries | Bound provider lifetime, trusted mode and candidate admission; consumer owns retry/receipt handling | Reuse an old preparation or prospective candidate in another attempt or after rollback, even before expiry: reject it as authority. In an admitted exact-retry fixture, keep the same original intent and humanActSubmissionId/act bytes but use a fresh attempt, current preparation and candidate; allow completion when every check still passes. Changed bytes under the same act ID cannot pass admission. Substitute NOT_REQUIRED or DIRECT_HUMAN_ACTION_REQUIRED, or supply a synthetic challenge/separate approver to direct-human mode: no bypass. Direct-human act time must meet its trusted session/transaction cutoffs. Consumer integration must separately prove that a committed exact retry returns its stored receipt with no provider call or second consumption. |
| AUTH-019: provider-owned challenge/final relevant-state equality | Same provider's typed read footprint, rule-selected projection/JCS digest, preparation refusal and final recheck | Change a rule-relevant target revision or representation fact between challenge and act while keeping an otherwise sufficient requester basis/window: no successful preparation or ALLOW from that act. Advance unrelated history outside the projection, changing only the full snapshot ref: preparation/final ALLOW remain possible if all other checks and guards pass. Verify exact provider-produced projection/digest; forged consumer digests or an equality flag cannot bypass recomputation. Relevant drift between preparation and final evaluation also fails. Preparation emits no decision; any canonical REQUIRE_HUMAN_APPROVAL refusal keeps HUMAN_FINAL_ACTION_REQUIRED primary and APPROVAL_CHALLENGE_STALE diagnostic. Consumer integration separately proves durable generation invalidation and a new challenge/act before retry after drift. |

Test setup uses fictional data and the existing separately owned provisioning
path. No production bootstrap or grant mutation is added to make fixtures
work. Relevant cases require real PostgreSQL tenant binding, two-tenant
isolation, exact currentness inputs and recorded read provenance; a pure
function fed caller-authored grant dictionaries is insufficient.

AUTH-015–019 exercise preparation and final evaluation through the same
production-bound provider and guarded attempt fixture. The fixture supplies
the transaction owner's trusted inputs and constructs prospective evidence
from the complete provider-derived view and owner-supplied prerequisites; it
must not implement its own extraction, relevant-state projection, path-selection
or cutoff algorithm. Inspect the schema-complete candidate and its derived
target/inputs/subject/representation bindings, not only a mocked approval ID.
Assertions inspect returned types/bytes and the absence of provider-owned
writes. The valid prospective-approval, unchanged-projection and admitted-retry
cases prove usability, not merely that every attempt can be refused. Fixture
admission does not prove the consumer's durable retry/invalidation protocol.

The exact source schemas and trusted input/read interface must exist before
these proposed cases can count as implemented evidence. Consumer race tests
must additionally cover revocation/set changes between evaluation and commit,
exclusive deadlines, duplicate consumption, persistence failure, committed
refusal with lost response, and separately unknown evidence commits.

### Focused verification for the revision 5 interface

These are planned cases under existing invariants, not new canonical rules or
claims of executed tests:

- AUTH-002/003/011: through the real runtime/UoW, substitute a frame from
  another tenant/attempt, a handler-constructed selection, a caller deadline,
  or a JWT cache/challenge expiry for required session proof. None becomes a
  trusted input. Separately prove that an explicitly unbounded governed
  interval is handled without inventing a cutoff.
- AUTH-007/010: capture two tenants, rejected and revoked paths, complete
  reference sets and a prospective absence. Tamper with a payload/digest,
  reference extractor, batch provenance or required watermark. Inject a
  same-transaction row claimed as a committed prerequisite. Each failure
  prevents the corresponding successful proof; no row is silently omitted.
- AUTH-007/009: reverse row order and exercise exact reader bounds plus one
  row/byte over the bound. Exact-bound complete data remains usable; overflow
  yields no partial complete-set claim. Demonstrate usable representative
  tenant sizes, not just refusal of every realistic capture.
- AUTH-007/009/010: contrast a complete no-path observation (`DENY` /
  `NO_AUTHORITY_BASIS`) with an incomplete read, a missing global snapshot
  prerequisite (canonical global ordering and dependent `NOT_EVALUATED`),
  and a revoked/unsupported path alongside a sufficient path (canonical
  aggregation). A real adapter/database fault follows infrastructure handling.
  Inspect truthful failure evidence without inventing a snapshot, suppressing
  path diagnostics or treating every failed authority proof as an exception.
- AUTH-011/012/014: retain both bound methods after closure and call them in a
  rollback-only UoW; no reader runs. Inject a database failure and verify the
  existing rollback/discard path, including a consumer that catches the error;
  no provider commit or false durable result follows. Verify exact
  constructor/slots/import edges and no raw handle.
- AUTH-013/019: delete a set/absence or external obligation from the returned
  handoff; completeness verification fails. Attempt the two-step approval
  handshake without proof of one final snapshot/protection context; no
  successful finalization. Actual race prevention still needs owner tests.
- AUTH-015–019: execute valid fresh-approval, direct-human and NOT_REQUIRED
  cases through the two methods, including same-person eligibility, exact
  candidate equality and admitted fresh-attempt retry. Preparation cannot
  masquerade as a decision; `None` cannot bypass the rule's human requirement.

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
| B8: refusal evidence rolled back by error | Sections 2 and 8 explicitly separate prepared evidence from consumer-owned durable refusal and response. | The issue amendment is applied; formal implementation approval and consumer-owned commit/recovery proof remain outstanding. |
| B9: six unsupported lineage expansions | Section 7 removes L; approved PR #11 section 7 supplies D/X/N ceilings and no derived-lineage row. | Exact artifact equivalence and AUTH-007. |

This table preserves the correction history. Current review is limited as
specified below; the old review's recommendation to retain a code-owned table
is not authority over the later canonical bundle ownership.

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
At revision 2 the scope, canonical-readiness and concrete-interface gates
remained open; that correction did not itself confer reviewer sign-off or
implementation approval.

### Revision 3 review: bounded B1 and related corrections

The [revision 3 review](https://github.com/samovers/OFARM2/pull/359#issuecomment-5560915672)
at `4f863fa98c4407d95b06642aaf9e8487088e9d7b` found one Blocker and four
related “Should fix” items, plus a state-sequence Preference. This revision
preserves the earlier handshake and addresses that focused review:

| Finding | Revision 4 correction | Required verification/gate |
|---|---|---|
| B1: challenge/final relevant-state comparison has no owner, output or invariant | Sections 4, 6 and 7 assign execution/recomputation to the provider, include its full projection/digest output and require typed stale-challenge refusal; unrelated history alone does not invalidate. | AUTH-019 and G3; no decision from preparation or invented primary reason. |
| S1: approval construction lacks provider-derived fields | Section 6 supplies the complete bound authorization view, including target, typed inputs, effect subject and representation, without a second consumer extractor. | AUTH-016 constructs a complete valid candidate solely from the provider view and exact owner-supplied prerequisites. |
| S2: separation, display and timely-act revalidation under-specified | Sections 6–7 name exact display/renderer/policy/locale/timezone/retention proof, trusted humanActedAt and current SAME_PRINCIPAL_ALLOWED posture; DISTINCT_APPROVER_REQUIRED remains reserved. | AUTH-016/018/019 and G3; no ceremony or retention/custody implementation. |
| S3: facade extension incorrectly called mechanical | Sections 4 and 12 name the exact current architecture shape and module/group budget constraints, and require a reviewed concrete extension and size outcome. | G3 and AUTH-014; no checker or automatic budget change in this revision. |
| S4: exact act retry confused with candidate portability | Section 8 and AUTH-018 distinguish admissible original-act reuse from forbidden old preparation/candidate reuse; committed retries return the existing receipt. | Provider fixture plus separately owned consumer retry/receipt tests. |
| Preference: final evaluation appears before EVALUATED | Section 8 replaces the ordinary evaluation step with the fresh-approval handshake. | One final decision-producing operation, with no extra evaluation step. |

The [focused revision 4 review](https://github.com/samovers/OFARM2/pull/359#pullrequestreview-5126174929)
at `263cd32722ff2b482910bd7bb880f91aa8391838` closed B1 at design level,
accepted the related corrections with its stated qualifications, and requested
no further patch. It did not close G2/G3 or approve implementation. That
exact-head disposition is historical evidence, not review of revision 5.

### Revision 5: concrete G3 proposal, not a new correction cycle

This revision follows the task user's instruction to return to the original
implementation work. It specifies the two closed entry points, dependency and
lifetime, an evidence-source ledger, the initial coherent tenant-read plan,
three read/guard obligation forms and focused verification. It identifies
missing producers instead of creating them in this boundary. It also records
G1's applied issue amendment and the later canonical planning sources.

The [focused revision 5 review](https://github.com/samovers/OFARM2/pull/359#pullrequestreview-5132918721)
at `87584f2e368fc791f0c12e4288885dc5425ea287` reported zero blocking findings
and one non-blocking S1 clarification: make the reader-to-evaluator failure
mapping explicit. It preserved the interface direction and prior handshake,
and did not close G2/G3 or approve implementation.

Revision 6 addresses S1 in the reader plan and AUTH-007/009/010 cases above.
Review only that clarification and its affected invariants; do not reopen the
earlier findings or architecture without new evidence of a defect. The
revision 5 zero-Blocker disposition remains historical, not review of this new
head. No new source producer, guard, runtime behavior or canonical law is added.

## 12. Expected implementation areas and code excellence

Only this existing RFC changes in the current design revision. It remains
useful after the PR because it records the authorization/transaction split
and why the old production assumptions were rejected.

Expected later areas, not a path allowlist:

- `kernel/production_authorization.py`: one small evaluator with immutable
  bound input/output and selected-proof values;
- a narrow production tenant authority-read adapter, plus the necessary typed
  hook in `kernel/tenant_uow.py`;
- production composition through the existing runtime/UoW path, and a reviewed
  exact facade/architecture-contract extension without weakening its
  legacy/SQL firewall;
- focused evaluator, PostgreSQL, composition, route-closure and UoW tests;
- Kernel navigation, this RFC, and mechanical test inventory changes.

No legacy caller migration/deletion, reference/schema/migration change,
command writer, runtime selector adaptation, principal/authentication edit,
audit-custody change or profile activation is included. Discovery of a file
inside the approved boundary can travel; discovery of a new authority cannot.

### Exact proposed facade extension and remaining size gate

At the inspected main, the architecture checker pins
the TenantUnitOfWork shape exactly, not merely by convention:

```text
public surface = {binding, batch, begin_batch,
                  resolve_commit_operation_claim_draft_runtime_bundle}
constructor = (self, binding, allocate_batch, resolve_bundle)
slots = {__binding, __active, __allocate_batch, __batch, __resolve_bundle,
         __selector_state, __selected_bundle, __rollback_only}
```

`_TENANT_UOW_PUBLIC_SURFACE`, `_TENANT_UOW_INIT_PARAMETERS` and
`_TENANT_UOW_SLOTS` in `conformance/rewrite_architecture_check.py` enforce
those values. Any additional method, dependency or slot needs explicit review
of the new accepted shape. The existing `_LEGACY_TENANT_UOW_SHAPE` and
`_TENANT_UOW_SHAPE` show a reviewed extension is possible; they do not approve
this extension. Even private raw connection/cursor/pool handles are prohibited.

The same checker's physical-line counts and budgets are:

| File/group | Current / limit | Remaining lines |
|---|---:|---:|
| `kernel/tenant_uow.py` | 520 / 520 | 0 |
| `kernel/tenant_command_runtime_bundle_selector.py` | 412 / 420 | 8 |
| tenant transaction group (the two files above) | 932 / 940 | 8 |
| `kernel/application_runtime.py` | 221 / 230 | 9 |
| application runtime group (runtime_config + application_runtime + deployment_identity) | 179 + 221 + 20 = 420 / 500 | 80 |

Adding eight lines to the UoW without removing others would mean 528/520 and
940/940 for its group; nine would also exceed the group. This arithmetic is
not a size estimate for a fully typed implementation. Moving work to another
module does not alone solve the facade's exact shape or its zero headroom.

Before Phase B, G3 must settle the exact typed provider entry, injected
dependency, constructor/slot/public-surface delta, lifecycle and permitted
import/query edges. The implementation plan must show the module/group size
outcome: either a reviewed simplification within this same boundary that fits
the existing budgets, or a specifically justified and reviewed budget change.
No automatic budget increase, generic facade escape or weakened raw-handle,
SQL, legacy-import or tenant-containment check is approved. A new module is not
automatically budgeted: MODULE_BUDGETS applies only to listed keys, so the plan
must explicitly settle its coverage and size bound and register focused test
coverage (the default covered test-module limit is 800 lines). Re-measure at
the implementation base. This design revision edits no checker or runtime.

Revision 5 proposes this exact new shape, replacing the earlier open-ended
provider-hook description:

```text
public surface = {binding, batch, begin_batch,
                  resolve_commit_operation_claim_draft_runtime_bundle,
                  prepare_authorization, evaluate_authorization}
constructor = (self, binding, allocate_batch, resolve_bundle, authorization)
slots = {__binding, __active, __allocate_batch, __batch, __resolve_bundle,
         __selector_state, __selected_bundle, __rollback_only,
         __authorization}
authorization = one private frozen _AuthorizationCalls pair
```

The pair contains only typed preparation/evaluation callables, not a generic
executor. The manager builds it against the same connection and privately held
principal/binding; `_finish` replaces it with closed callables. Public
`ApplicationRuntime` methods and existing authentication, audit and selector
semantics do not change. The two new UoW methods check lifetime/rollback-only;
they do not allocate a batch, commit, acquire locks or choose policy. Concrete
reader SQL stays in the private tenant authority adapter, not the facade or a
legacy module. Architecture verification must allow only those exact new
edges and preserve the existing raw-handle, generic-SQL and legacy firewalls.

Proposed implementation partition is the evaluator, narrow reader and closed
local input/output types needed by those two operations; no plugin registry,
generic policy framework or parallel authorization path. The type dependency
direction must avoid a circular import back into `tenant_uow`; place shared
values separately only when the concrete implementation needs it.

The measured current size outcome is **no UoW headroom**, not an approved size
for this extension. No code sketch or arbitrary allowance is presented as a
measured implementation. After G2 fixes the actual contracts and G3 fixes
trusted constructors/query bounds, the Phase A implementation plan must name
the final module partition, measure the facade/wiring delta and justify exact
module/group budgets, including explicit coverage of all new modules. If it
does not fit, bring the smallest in-boundary simplification or specific budget
proposal for review. Do not move existing transaction code merely to hide the
growth. The exact surface is now proposed; G3's size outcome is still open and
Phase B remains prohibited.

| Code-excellence invariant | Planned assessment |
|---|---|
| EXC-001 — one authoritative path | One canonical semantic source and one production authorization implementation shared by non-decision preparation and final evaluation; the transaction owner constructs evidence from those values, not a second extractor, relevant-state projection/comparison, path-selection or cutoff engine. |
| EXC-002 — no avoidable duplication | No handwritten second matrix, compatibility authority API, extra durable decision store, retry ledger, or copied schema inventory. |
| EXC-003 — direct invariant trace | AUTH-001–019 map the typed entry, bound reader, preparation/final-evaluation handshake, relevant-state comparison and evidence constructor to focused tests. Missing real reachability blocks completion. |
| EXC-004 — delete superseded owned paths | Withdraw the old plan; introduce no legacy compatibility path. The quarantined legacy system is not an owned production path and is not deleted as an unrelated migration. |
| EXC-005 — abstractions pay rent now | Bound input/output prevent mixed tenant/rule/attempt facts; distinct preparation, prospective-evidence and prepared-decision values prevent authority/persistence confusion in the required fresh-approval handshake. A narrow reader contains existing connection authority. No generic policy engine, plugin registry, public SQL facade or future dispatcher. |
| EXC-006 — simpler credible alternative | Adding a table to kernel.authority fails production isolation and canonical ownership. A pure helper alone fails the bound production-read outcome. A new transaction owner is unnecessary and crosses into #178. The proposed provider plus typed reader is the smallest plausible slice, subject to gate G3. |

## 13. Gates, provisional posture, and review state

This is a **provisional design**, not permission for a temporary runtime.
Planning against exact approved candidate semantics is useful before
deployment, but executable bytes and concrete trusted interfaces are absent.
No fallback, weakened proof, old-schema compatibility or synthetic authority
path is authorized.

| Gate | Current state and what remains before implementation approval |
|---|---|
| G1 — Delivery scope | Applied in issue #353 with the preserved amendment record in section 2. The later formal decision card must include this scope; full evaluation coverage remains explicit. This is not implementation approval. |
| G2 — Canonical readiness | Complete the governing staged sequence and replace missing entries in section 5 with reviewed exact promoted/extracted bytes and provenance. Semantic approval alone is insufficient. |
| G3 — Concrete trusted interface | Sections 6, 8 and 12 now propose the exact closed surface, trusted-source map, coherent read shape and guard handoff. Review those choices and close the specific unresolved items below; no production factories, canonical snapshot proof, measured query bounds or final module budget are implied. Preserve the revision 4 handshake and prove independently useful full-coverage production-provider completion. |
| G4 — Fresh OFARM2 approval | Review this corrected Phase A to zero Blockers, then present a complete decision card naming existing PR #359 and obtain the required exact later task-user approval. No such card is issued by this revision. |

The remaining G3 work is bounded, not a request to restart canonical design:

| Item | Required closure evidence | Boundary and sequencing |
|---|---|---|
| G3-INPUT | Exact mappings and real producers for principal/representation/CP3, session/act, attempt/deadline and compatible selection; reject forged/mixed frames through production composition | Consume existing accepted producers where sufficient. Any new authentication/session, selection or transaction authority needs separately scoped work and user direction before edits; do not mint proof in this provider. |
| G3-READ | Exact admitted schema/hash/extractor mapping, coherent SQL, source visibility/currentness and canonical snapshot proof, truthful global/path/infrastructure failure encoding, bounded representative workload, same final-snapshot/protection context for the handshake | Reader/projection implementation belongs here after G2. Missing storage, permission, snapshot authority or transaction protection belongs to its owner, not a database change hidden in the reader. |
| G3-HANDOFF | Actual typed transaction interface covering every record/set/absence/external/time obligation and attempt-bound prepared evidence, with an independently usable provider completion test | Settle the interface with #178's design before approving provider code. Durable command coordination, guards and consumer race/recovery tests remain #178/applicable consumer work. Their later delivery cannot excuse a provider that only accepts invented fixtures. |
| G3-SHAPE | Review the exact facade proposal and architecture edges in section 12, then a measured final partition/size and focused production-path test plan against the admitted bindings | One authorization boundary. Existing zero headroom is explicit; no automatic checker relaxation or budget increase. |

The #353 -> #178 -> #176 sequence describes capability completion; it cannot
postpone an indispensable input producer until after its consumer. If G3
requires an authority producer that exists only in unfinished #178 work, that
is a dependency cycle to resolve before approval, not permission to use fake
frames. First determine whether an already accepted interface suffices. If
not, propose an independently usable prerequisite in its own boundary and
reconcile the Delivery issue structure with the user before creating it.
Neither a type-only companion PR nor silently expanding #353 resolves this.

Evidence requiring redesign: a machine binding contradicts the approved
candidate; the exact reader/guard/proof needs a new authority; full admitted
coverage cannot be supplied by one coherent provider; or provider-owned
durability is requested again. The upgrade path is a reviewed revision with exact
bindings and concrete interfaces, and a new semantic decision version where
required—not a compatibility fallback.

Separate downstream work: #178 command identity/atomic consumption/results;
#176 temporal Delivery selection after its prerequisites; #177 output and
disclosure planning; #175 grant mutation/bootstrap children; #193
disaster/store-loss recovery. The old command successor is a compatibility
gate for its consumer, not a reason to amend approved canonical PR #26.
No new Delivery issue is created in this revision.

Review disposition: revision 6 is REVIEW_PENDING. G1 is applied; G2/G3 and the
later G4 card/approval remain outstanding. The revision 5 review stays attached
to its exact historical head and is not transferred to this revision. Exact
private names and test-file partitioning are Preferences only after the
substantive interface is settled.

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

What is next: review revision 6's bounded reader-failure clarification and
affected AUTH-007/009/010 invariants at its new head; close the listed G2/G3
prerequisites with their existing owners before presenting the fresh #359
decision card. No runtime edits, new Delivery issue, baseline or merge are
authorized by this design revision.
