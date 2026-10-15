# OFARM Production Authorization Provider — Phase A RFC v0.1

Date: 2026-09-12

Design revision: 9 — bounded evidence-reference and policy-failure correction.
This retains revision 7's complete two-action scope and revision 8's provider/
consumer evidence-ownership split. Required evidence is resolved, not accepted
as proof values from an attempt frame. It consumes
renewed canonical Phase A approval at PR #11 head
`4494924998183fe3fa7bc1b63b76a85893335044` and the aligned #353 scope. It proposes
complete evaluation of ASSERT_OPERATION_CLAIM and RECEIVE_READ_DATA through
one evaluation-only facade. Neither selected rule is weakened. The other
eighteen action evaluations and human-finalization execution remain explicit
later work under #175, not passed or implemented.

Revision 6 at `725df163ddcd4f93b4675a3041724b1f59ab8151` preserves the previous
full-programme design, human-approval handshake and reader-failure correction
as history. Their reviews do not transfer to this new scope/interface.
Missing source factories, machine contracts, read protocols and commit guards
remain prerequisites, not newly supplied infrastructure.
The unapproved legacy proposal at
`178f150ce56f1bdad96330ba845d210ee0911f2a` remains superseded. No accepted OFARM
law changes.

Revision 7 at `feffb585ec569c6aaa8b5d085e94583d1eb9aeca` has two exact-head
reviews; the later review identified B1's read-evidence ownership ambiguity.
Revision 8 at `f97fe8f73d956d2dd6c0f82f133d6800b71055fe` corrected that ownership;
its focused review identified B2's proof-carrier gap and F3's policy-failure
ambiguity. Section 11 records the bounded corrections and prior follow-up
dispositions. Prior reviews do not approve this new head.

Status: revision 9 is REVIEW_PENDING; G1 first-release scope alignment applied;
G2 canonical readiness, including source-history closure, and G3 implementation
prerequisites remain open. The sufficiency of two executable actions is unproved.
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
and truthful retry handling, plus currently authorized readback through its
separately owned read/disclosure protocol. The delivery order remains
authorization #353, command idempotency/coordination #178, then a separately selected temporal
Delivery under #176. Interface design for those consumers must happen before
this provider's implementation is approved; it does not authorize their code
inside this PR.

That order names completed capabilities, not permission to postpone a real
write/read attempt producer until after its evaluator. G3 must settle both
consumer interfaces and their actual production ordering before implementation.
Ordinary saved-result retrieval or exact retry is not the independent
valid-time/knowledge-position capability required by the later #176 child.

Authorization is necessary but insufficient for a write. This provider does
not validate the protected result, consume a decision, commit evidence, or
promise a durable outcome. Issue #353 now explicitly distinguishes these
owners, while retaining full admitted action/evaluation coverage.

## 2. Applied amendments to issue #353

The task user directed applying the four-point scope amendment. The
[issue amendment record](https://github.com/samovers/OFARM2/issues/353#issuecomment-5566519997)
preserves the original issue text and that limited instruction. This is the
retained ownership definition, not formal implementation approval:

| Superseded requirement | Applied replacement and consequence |
|---|---|
| Independently authored code-owned action table | Execute the exact content-addressed canonical rule bundle. A compiled immutable view is permitted only as a verifiably equivalent representation, not a second policy source. |
| Migrate existing legacy evaluator and SI callers | Add the provider to the real production composition and prove its typed tenant-bound entry point. Keep the separate legacy surface quarantined and unchanged; legacy test success is not production evidence. |
| Provider delivers a durable decision trace | Provider delivers complete, schema-checked, digest-verifiable **prepared** evidence and explicit guard obligations. The consumer's transaction boundary owns persistence, complete-set atomicity, successful single use, and durable response. |
| Existing SI decisions remain equivalent | No SI behavior change in this PR. New production decisions follow the separately promoted canonical version; no compatibility interpretation of v0.1 evidence as v0.2. |

The 2026-09-11 first-release alignment in [issue #353](https://github.com/samovers/OFARM2/issues/353)
consumes [renewed canonical scope approval](https://github.com/samovers/OFARM/pull/11#issuecomment-5634389303)
at `4494924998183fe3fa7bc1b63b76a85893335044`. Its previous body is preserved as
history. The full catalogue still has twenty unchanged rows; the proposed
initial executable package admits exactly ASSERT_OPERATION_CLAIM and
RECEIVE_READ_DATA. The eventual verified manifest, not a second handwritten
runtime matrix, supplies that set. The provider verifies exact admitted-set
and resolved-rule equality and covers every selected resource alternative
and authority path. A missing, duplicate, extra or invalid member cannot be
repaired by evaluating a working subset.

A claim-only read evaluator, one successful row or blanket non-ALLOW is not
completion. The other eighteen evaluations and their applicable human-approval
flows remain open under #175. This scope does not remove sharing, delegation,
representation, CP3, revocation, evidence or disclosure obligations needed by
the two complete selected rules. Unknown/excluded actions stop before the
authorization outcome lattice; no caller-selected bundle, old schema or
full-policy fallback is permitted.

Keep policy coverage, provider implementation coverage, and enabled public
commands separate. No row becomes publicly executable merely because the
provider understands it. Both selected rules retain NOT_REQUIRED. The first
facade has no preparation operation or prospective-human input; it does not
implement empty methods or synthetic approval evidence. Selected read sharing
and current source checks remain full evaluation requirements; creating grants,
running an approval ceremony, disclosure and protected effects remain separate
capabilities. Section 10 explicitly disposes every AUTH invariant.

G1 is satisfied as an issue-scope editing step. The later complete #353
decision card must include this amended scope and receive its own exact
task-user approval. #353 cannot close on this RFC, types alone, one action, or
blanket refusal: it must prove an independently usable production provider
with the complete admitted coverage. Any later request for provider-owned
durability changes this boundary and requires re-planning, not a second
transaction owner or quiet absorption of #178.

The full dependency closure is not yet established. In particular, canonical
PR #11 section 24.1 leaves open whether complete history classification and
historical-admission verification can work without executable qualifying-record
authoring. Scope approval neither answers that question nor admits an extra
action. No dependency or approval transfers automatically to another candidate.

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
| Database session, transaction identity/finalization, isolation, complete commit guard and uncertainty reconciliation | Existing transaction owners, later #178 write work and the separately owned governed-read protocol; no new owner here |
| One current evaluation, selected sufficient path, complete prepared decision evidence and read obligations | This provider |
| Evaluation of the selected action-level evidence policy, including CP2 read-qualification evidence | This provider verifies the exact rule-bound policy and its required proof before ALLOW. The separately owned read/evidence producer supplies proof inputs; result qualification, redaction, persistence and release remain consumer-owned. Neither ownership substitutes for the other. |
| Execute every projection/comparison required by the selected rules and complete evidence closure | This provider, using its current typed authority observation; canonical OFARM owns projection and JSON Pointer semantics. Human challenge/final equality execution is deferred, not a first-release API. |
| Human-act capture, display/retention, generation invalidation and challenge replacement | Separate human/transaction owners; their runtime workflows and the provider's corresponding future handshake remain deferred under #175, with revision 6 preserved as history. |
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
- evaluate all selected actor, resource, scope, source, sharing, revocation,
  purpose, evidence and NOT_REQUIRED rule obligations through one deterministic path;
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
- no first-release human-preparation API, prospective-human-finalization input,
  approval ceremony, synthetic approval evidence or successful deferred stub;
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

| Candidate | Exact planning source head | Relevance |
|---|---|---|
| [OFARM PR #11](https://github.com/samovers/OFARM/pull/11) | `4494924998183fe3fa7bc1b63b76a85893335044` | Approved complete catalogue and exact initial release-scope semantics, paths, snapshot/evidence, scoped staging and open history checkpoint |
| [OFARM PR #17](https://github.com/samovers/OFARM/pull/17) | `9ef08030b25eb3db1c2da14d6595300198384ff2` | Retained human final-review programme source; not a declared first-release effect |
| [OFARM PR #20](https://github.com/samovers/OFARM/pull/20) | `98f8c4fafbae42c8f7fd931f43f53adcb4733713` | Retained human-finalization programme source; excludes NOT_REQUIRED and does not supply the selected write/read protocols |
| [OFARM PR #23](https://github.com/samovers/OFARM/pull/23) | `622376e2998cf8b3954ca19e81d2cce6fd57e5fe` | AssertionRecord submission protected-effect contract |
| [OFARM PR #26](https://github.com/samovers/OFARM/pull/26) | `e042efa2911b2ef0a61603b8e0adaa6911c03ac0` | NOT_REQUIRED atomic protocol and first operation-claim handoff |
| [OFARM PR #28](https://github.com/samovers/OFARM/pull/28) | `4e186aab5c238215906fcf9b24ce74443abb6f72` | Exact SharingGrant TERMINATE protected-effect planning source; not a revocation command in this PR |
| [OFARM PR #29](https://github.com/samovers/OFARM/pull/29) | `8e0994cae5610ac9c0d2652e02c8a8a2dd7b45c5` | Retention and honest retained-versus-digest-only proof; no custody implementation here |
| [OFARM PR #31](https://github.com/samovers/OFARM/pull/31) | `092be94f3a67497ba619295932cd0b2b1e9443f3` | Approved public-result design with CP2A-DEP01 still open; not a complete history producer |
| [OFARM PR #34](https://github.com/samovers/OFARM/pull/34) | `69682c2f918ef18756261a1186294cc3a5ebe44d` | Unapproved qualifying-record proposal with QG-DEP01; not an admitted source/writer or additional selected action |

The [PR #11 approval](https://github.com/samovers/OFARM/pull/11#issuecomment-5634389303)
approves the release-scope model at that exact head. The previous approval at
`03a21f669ee04f96d444e14f00ae7212cab04803` remains history; this revision's
planning pin is intentionally updated, without approving any dependent candidate
or changing the complete per-rule digest/source-consent law.

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
| Selected protected-effect contracts, AssertionRecord result binding and Event Grammar classifications | Selected complete dependency closure still required; unselected effects may be deferred only with a reviewed closure disposition |
| NOT_REQUIRED write and separately owned governed-read transaction profiles, deadline/guard mappings and result-complete lifecycle | PR #26 is a write-only semantic candidate, not a governed-read protocol; executable profiles and real production interfaces remain unproved |
| CP2 result/reasons, retention, sovereignty, evidence and CP3 bindings | Exact selected bindings and current source checks remain required; approved designs are not promoted/extracted contracts |
| Rule-bound `EP_CP2_READ_QUALIFICATION_V0_2` and its required evidence | Required by PR #11 sections 7.7–7.8, 12 and 18.5, separately from CP2 result qualification. The exact policy ref/digest, evidence schemas, eligible source/producer bindings and extraction remain G2; the real pre-evaluation input producer and same-snapshot interface remain G3. No executable profile or proof source is supplied here. |
| CP2A-DEP01 source-history classification, completeness and historical-admission proof | Open under #32 and its actual source dependencies; inactive writing, empty lookup or an individually valid qualifier is not complete history |

Existing v0.1 schemas are not substitutes. A missing digest is recorded as
missing, never filled with a placeholder that could become executable.

[OFARM #21](https://github.com/samovers/OFARM/issues/21) and approved PR #11
section 24 control the order: adjacent prerequisites; non-default policy,
source and bounded decision-evidence packages; exact binding review and
accepted law; hostile conformance; explicit current/default promotion;
byte-identical OFARM2 extraction; then OFARM2 runtime work. The older PR #359
comment's abbreviated order is not controlling. PR #26 did not complete all
of these steps. All stages apply to the complete selected dependency closure,
not the whole catalogue by default and not a sample of either selected rule.
No family-level currentness pointer may silently activate the other eighteen
actions or omitted profiles. If history closure requires another action, stop
for a separately reviewed scope amendment; neither a second policy nor a
permanently unavailable classifier is a workaround.

## 6. Proposed production interface and data ownership

Use one production-only evaluator and one narrow tenant read adapter. The
following is a concrete local interface proposal for review, not executable
code or new canonical record schemas. Exact machine bindings and the named
upstream factories remain G2/G3 dependencies.

### Closed evaluation entry and trusted construction

The public work surface gains exactly one synchronous method:

```python
def evaluate_authorization(self, call: AuthorizationCall) -> EvaluationOutcome:
    ...
```

It is reached through `ApplicationRuntime.tenant_unit_of_work`, its existing
security-audit wrapper and the manager-created active `TenantUnitOfWork`.
The manager injects one private closed typed evaluation callable, bound to the
authenticated principal, exact TenantBinding and same connection. The UoW
exposes neither that callable nor an independently usable provider handle.
One evaluator implements both selected rules' complete semantics.

The method checks active and not rollback-only before invoking its private
callable. `_finish` seals that dependency with a closed sentinel as well as
the existing ones. Retaining a bound method cannot bypass those checks.
Results contain immutable data only, never callables, cursors or a connection.
Unexpected database/adapter failures mark the existing `__rollback_only` flag
before re-raising into the UoW rollback/discard path. Catching the error cannot
make the UoW committable again. The provider cannot swallow a broken transaction
and report a durable refusal. Ordinary typed ingress refusals and canonical
non-ALLOW decisions do not themselves assert rollback or durability.

There is no `prepare_authorization` method, `ProspectiveFinalization` input or
`PreparationOutcome` in this first-release interface. Deferral removes proposed
unused surface; it does not replace it with empty methods or success stubs.
These methods do not exist in the inspected production code.

`AuthorizationCall` has three closed roles, not a general proof dictionary:

| Local member | Content and admission rule |
|---|---|
| `attempt` | Owner-issued write or governed-read attempt frame: exact operation where applicable, protocol/attempt/transaction binding, fixed deadline and trusted time, required principal/session validity and snapshot/guard inputs. The read form also carries the rule-bound qualification-evidence observation described below. It must match this bound UoW and selected action; no human-act or approval role is admitted here. |
| `selection` | Owner-issued exact operation/action, policy/rule and binding-manifest selection. Verify its provenance, content and compatibility; a matching action string alone is insufficient. A write-command selection cannot substitute for a governed-read binding. |
| `effect_intent` | Exact full intent bytes and their claimed identity/digest. The provider validates and derives its authorization view itself. Owner-completed fields must already be bound by the admitted write or governed-read protocol. |

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

`EvaluationOutcome` is either a truthful ingress/infrastructure refusal or a
complete prepared decision with immutable read/guard obligations. The types
are disjoint: no shared `allowed` flag, fabricated canonical DENY on malformed
ingress or `committed` field. No successful result is portable to another
attempt or closed UoW. A complete prepared non-ALLOW still needs truthful
failure evidence under its exact admitted contract.

The `attempt` role has two closed owner-supplied forms: a state-affecting
NOT_REQUIRED write attempt and a governed-buffered-read attempt. Each binds
its own admitted protocol, transaction identity, deadline and snapshot/protection
context. The provider verifies the form against the selected action and the
privately bound UoW. A write attempt cannot authorize a read or substitute for
its read-coverage/evidence protocol; a read attempt cannot authorize a write.
These are local envelope roles, not newly invented canonical schemas or
caller-selected approval modes. Exact machine fields and real factories
remain G2/G3 work.

The proposed carrier for read-qualification proof is the closed governed-read
`attempt` role, supplied by its separately owned read/evidence producer before
final authorization evaluation. It carries exact immutable
revision/digest references and truthful missing/invalid observations, not a
caller-set `qualified` flag or an asserted prior ALLOW. Every required evidence
reference must resolve through the provider's typed tenant reader in the bound
snapshot to the exact revision/digest recorded by the decision and satisfy
canonical section 12.5's full eligibility checks under the selected policy.
No evidence fact is accepted from the frame itself. The provider verifies the
resolved evidence's exact effect-intent binding and the same governed
snapshot/protection context.

This is a local input-role proposal, not a new canonical schema, evidence kind
or producer implementation. G2 must supply the exact active/current policy,
schemas and source admission; G3 must settle the real producer, field mapping,
pre-evaluation availability and truthful failure representation. If the proof
cannot be produced in the required order/context, that gate remains open:
no unbound payload supplied after evaluation, completed receipt from the same
read, synthetic proof or premature disclosure can fill the gap. Producing a
proof observation does not itself grant read authority or permission to release.

### Trusted-source map and missing producers

| Required fact | Existing source and provider use | Remaining owner dependency |
|---|---|---|
| Authenticated Party and tenant anchor | `AuthenticatedPrincipal` / `PrincipalAuthority`, checked against `TenantBinding` and exact Party record identity/digest | Map the admitted principal-resolution revision and its validity interval to canonical evidence; do not treat the anchor as complete representation/CP3 proof. |
| Natural-person representation or software actorship | Read immutable governed evidence and apply the selected contracts; Party classification and sponsorship alone confer no representation/delegation | Inventory exact current representation/CP3 bindings and their provenance. PR #11 says the current CP3 envelope is semantically sufficient; this is not permission to change it. |
| Required principal/session validity | Existing identity/principal bindings supply only their admitted facts; the provider applies every selected rule's required validity cutoff | Exact required mappings/producers remain open. The provider cannot reparse an unverified JWT, copy verifier logic or replace session validity with a token/challenge expiry. Human-act capture and interactive approval evidence are deferred, not substitutes for these current checks. |
| Write or read attempt, deadline, snapshot and protection | Same bound connection supplies tenant/full-transaction identity; each owning protocol supplies its admitted time/guard context | Current UoW has no complete write/read attempt/deadline/guard factories. Tenant challenge time, token lifetime, batch allocation and `bound_at` are not substitutes. Settle #178's write interface and the separately owned governed-read interface before their respective use. |
| Command/action and authorization policy | Consume exact verified selections and content-addressed admitted bytes | Current fixed selector selects the incompatible old command in section 9, not a general v0.2 policy. Its owner must supply a compatible reviewed selection; this PR cannot reinterpret it. |
| Canonical authority snapshot/currentness and source visibility | Provider verifies canonical proof against coherent tenant reads and exact source/batch provenance | G2 must supply exact bindings; G3 must identify how existing sources prove every required watermark/visibility fact. A SQL snapshot label does not fill this gap. |
| Rule-selected CP2 read-qualification evidence | The read owner's closed attempt supplies exact immutable revision/digest references or explicit missing/invalid observations, never authoritative proof values. The typed reader resolves every required evidence reference in the bound snapshot; the provider applies canonical section 12.5 eligibility and `EP_CP2_READ_QUALIFICATION_V0_2`, recording individual evidence dispositions before ALLOW. | The separately owned read/evidence producer owes real, same-context inputs before evaluation. Its exact schema/source eligibility and policy bytes remain G2; factory/transport/order are G3. No existing table, CP2 public-result implementation or PR #34 writer is presumed to supply them. |
| Public result/read qualification and source history | Consume exact admitted evidence/history semantics where the selected closure requires them; the provider does not classify public history or release traces | CP2A-DEP01 and #32's completeness/historical-admission proof remain open; #34's proposed writer is not admitted by this plan. Required retention and disclosure bindings also remain real owner dependencies. |

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
   condition/evidence/purpose and sovereignty inputs, including the referenced
   evidence for the selected action-level read-qualification profile. For
   RECEIVE_READ_DATA, bind those evidence reads to its closed read-attempt
   observation; neither source replaces policy verification. Include all facts
   required by rejected-path diagnostics and the relevant-state projection,
   plus exact absence and complete-set claims, not just the winning path.
6. Verify every source's required snapshot visibility/currentness proof.
   READ COMMITTED sees this transaction's own writes too: a same-attempt row
   cannot be labelled an already committed prerequisite. No prospective-human
   input is accepted by this first facade. An MVCC label,
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
For the selected write or read, the owning protocol must prove that the
authority observation and protected effect or buffered retrieval/coverage
share the required snapshot/protection context. Merely running the SELECT
twice cannot prove continuity. Loss of that proof prevents consumption or
disclosure. The provider reports its complete authority footprint; the read
consumer owns payload coverage, result qualification, receipt/evidence
persistence and release, including the additional obligations introduced by
its retrieval. That does not move evaluation of rule-bound qualification
evidence out of this provider or let result qualification repair missing authority.

### Deferred human-interface history

Revision 6's [preparation/candidate design](https://github.com/samovers/OFARM2/blob/725df163ddcd4f93b4675a3041724b1f59ab8151/docs/rfcs/OFARM_Runtime_Authority_Action_Matrix_Evaluation_RFC_v0_1.md#6-proposed-production-interface-and-data-ownership)
and [fresh-approval equality protocol](https://github.com/samovers/OFARM2/blob/725df163ddcd4f93b4675a3041724b1f59ab8151/docs/rfcs/OFARM_Runtime_Authority_Action_Matrix_Evaluation_RFC_v0_1.md#fresh-approval-preparation-and-final-equality)
remain explicit future programme design, not implemented first-release APIs.
Their exact human-act/display, independent approver, prospective-evidence,
relevant-state and basis/window safeguards are not weakened or marked passed.
A later action/package expansion needs its own reviewed dependency closure,
facade design and approval; no generic hook activates those flows now.

Do not finalize an implementation card until the selected interface has a
concrete production-path test plan and independently usable provider completion
criterion. “A future #178 will make this work” cannot justify closing #353.
Both write and read owners must supply genuine admitted inputs first.

## 7. Evaluation contract

The exact promoted counterpart of PR #11 controls field names, ordering and
outcomes. This section maps that meaning to implementation ownership; it does
not create a second action matrix.

### Ingress and policy

Reject malformed bytes and duplicate JSON names; validate the base request;
verify the selected immutable package and exact admitted-set/resolved-rule
equality, require action membership and its complete rule; validate its selected
effect-intent schema; then execute its exact authorization-view extraction.
A missing/duplicate/extra/invalid rule, excluded action, incompatible schema
hint, invalid intent or extraction is ingress rejection, not fabricated DENY
evidence. The runtime cannot repair an invalid package with a subset, fall back
to another bundle/old schema or admit a caller-selected policy.

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

### Rule-bound action-level evidence

The verified selected rule supplies `evidenceRequirementPolicyRefs`; code does
not choose an evidence policy. PR #11 sections 7.7–7.8 bind
`ASSERT_OPERATION_CLAIM` to `EP_NONE` and `RECEIVE_READ_DATA` to
`EP_CP2_READ_QUALIFICATION_V0_2`. `EP_NONE` is an explicit empty action-level
requirement, not missing policy and not a waiver of source evidence groups.
Every selected action-level policy and every source-path evidence requirement
must pass cumulatively under canonical section 12, including delegated and
SharingGrant paths. One sufficient grant cannot replace the read evidence.

This provider evaluates the read profile before preparing ALLOW. It verifies
the exact eligible evidence, intent/target/scope/tenant/sovereignty/purpose
bindings, time and state, records individual evidence dispositions, and carries
the necessary snapshot/guard obligations into its handoff. An otherwise valid
admitted actual read with the required qualification evidence absent yields
canonical DENY, including the agent-read case in PR #11 section 22; preflight
posture or later result qualification cannot bypass that requirement. Other
invalid or unsupported evidence follows its exact canonical disposition, not
a newly invented reason or an indiscriminate infrastructure exception.

Missing or invalid executable-package bindings still block admission/readiness;
malformed ingress does not become fabricated decision evidence. In an otherwise
admitted evaluation, an evidence policy that is not active/current or whose
exact revision is not retrievable has canonical `UNSUPPORTED_EVIDENCE_POLICY`
(default `REQUIRE_REVIEW`, rank 240), with individual evidence dispositions and
the canonical aggregation rules, not an ingress rejection. This distinction
does not close the outstanding G2 readiness gate. The read/evidence owner
produces the proof inputs described in section 6 and the read consumer owns
result qualification/redaction/coverage and release. Neither produces authority
merely by qualifying a result. No new producer, release order or canonical
contract is implemented or approved by this clarification.

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

The canonical outcome lattice is retained, but each reported disposition must
be justified by the complete selected rule and current facts. Both admitted
rules select NOT_REQUIRED. The implementation cannot invent a human-approval
requirement, select a deferred lifecycle or construct synthetic approval evidence
to cover missing source proof. Canonical missing-proof/global/path behavior
still applies; deferring human execution does not turn unknown facts into
authority.

### Final validity for the selected scope

The provider computes the canonical minimum cutoff from every required trusted
transaction, principal/session, representation/source, policy/snapshot,
resource/evidence and sovereignty validity end. Ends are exclusive. It does
not invent `approvalExpiresAt`, a challenge or a prospective human candidate
for a NOT_REQUIRED rule. Missing required time or source proof prevents a
consumable handoff under the owning contract.

The full human-preparation, projection equality and candidate/final basis/window
protocol is retained at the revision 6 links in section 6 and the unchanged
canonical source. It is deferred, not a second path or current implementation
requirement for this first facade. Human-act-specific cases in section 10 are
explicitly not passed by selected-scope conformance.

### Final decision evidence

Build complete request/result/full-trace records and snapshot/basis bindings.
The decision-bundle projection removes only
`/result/decisionBundleDigest` and `/trace/decisionBundleDigest`; all other
schema-permitted content stays hashed. Apply the canonical pre-digest
sentinel validation, JCS/SHA-256 and final ordinary-schema validation. Do not
reuse v0.1 evidence fields to simulate v0.2 meaning.

## 8. Evaluation lifetime and transaction handoff

The ordinary decision-evaluation sequence is:

`BOUND_INPUT -> INGRESS_VALID -> CURRENT_FACTS_OBSERVED -> EVALUATED
-> PREPARED_EVIDENCE -> HANDED_TO_OWNING_TRANSACTION`.

Only evaluation constructs a prepared decision bundle. There is no first-release
preparation/candidate handshake or provider-owned COMMITTED state.
Ingress/infrastructure failure does not invent a valid authorization result.
A valid non-ALLOW may reach PREPARED_EVIDENCE but never an effect or consumption
transition. Closing/refusing the UoW invalidates further provider use. Rollback
discards attempt-bound prepared evidence; it cannot be reused in another attempt
even when its former expiry has not passed.

For the write consumer, logical-operation lookup and original-result recovery
precede another protected-write evaluation under PR #26's exact rules. A
committed exact retry recovers the verified original outcome without repeating
or re-authorizing that write or its successful consumption. An unresolved
outcome blocks reapplication. After conclusive rollback, a newly admitted
attempt needs fresh current evaluation under its exact protocol. Comparison
uses the original caller-submission projection and lookup tuple; the bind-once
full intent and original assertedAt stay unchanged. A fresh attempt timestamp
must not manufacture a retry conflict.

Saved-outcome equality does not guarantee identical outward disclosure today.
Returning protected saved information requires the separately owned current
read/qualification checks, which may use a fresh governed-read attempt and
this provider's complete RECEIVE_READ_DATA evaluation. Revocation after the
original success can prevent disclosure without changing the original durable
outcome or repeating its write. “No new provider call on committed retry”
means no re-evaluation of the original protected write, not a ban on currently
required read authorization.

Every prepared decision binds the current write or read attempt and its full
intent. Compute decisionValidUntil using PR #11 section 18.2: the canonical
minimum of all applicable trusted deadlines and validity ends, with no invented
human-approval cutoff. Required missing/unparseable ends or a minimum not later
than evaluation time produce no consumable decision. Runtime lookup, admission,
persistence and uncertainty reconciliation remain consumer-owned.

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

The prepared decision's local handoff is bound to the exact tenant, admitted
protocol and attempt, operation/command binding where applicable, full intent,
selected action/policy, canonical snapshot, complete
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
| External binding or time | Exact selected policy/currentness, required identity/session/representation proof and every applicable exclusive cutoff not established by tenant rows | Its owning authority's admitted validity/recheck mechanism and timely final consumption; a database row lock alone is insufficient. Deferred human-act/display evidence is not a substitute. |

These forms identify obligations, not new predicate semantics or a generic
query language. The bound rule/profile owns the exact predicates and canonical
evidence mapping. Provider completeness tests compare the entire handoff with
its observed footprint; the consumer must reject an omitted, unknown,
mismatched or unprotectable obligation before consumption. No successful
handoff may silently reduce this to the selected grant's ID and expiry.

Before Phase B, G3 must connect these forms to both owning transaction interfaces
and their exact canonical profiles. In particular they must prove the required
continuity from authority observation to protected write or buffered read,
external validity and set/absence protection under concurrency. No such
complete production interface exists at the inspected base. This RFC chooses
the producer/consumer split and required contents; it does not select locks,
change isolation or certify a fictional guard receipt. The read owner combines
this full authority footprint with its own payload/coverage obligations; the
provider does not author a redaction plan or read receipt. Tests with handcrafted
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

The governed-read consumer uses its own complete buffered-read protocol:
coherent authorization and retrieval, full result coverage, redaction and
result qualification, exact buffered payload and proof posture, atomic decision/consumption/read-evidence
and receipt persistence, then permitted release. PR #26 is explicitly write-only
and cannot stand in for that protocol. This provider neither retrieves a public
payload nor persists its receipt or authorizes release on the strength of a
prepared ALLOW alone.

That result-qualification ownership does not include this provider's check of
the rule-bound qualification evidence in section 7. Required proof must be
available to final evaluation in the admitted same-snapshot protocol; a later
consumer check cannot retrospectively make an incomplete ALLOW valid.

Human-finalization runtime flows and the provider's corresponding handshake
remain deferred under #175. Their canonical obligations and revision 6 design
are preserved, not verified by this delivery.

These are interface obligations for separately owned consumers, not their
implementation or verification in #359. Provider tests prove complete selected
evaluation, prepared evidence, truthful failures, attempt/role binding, full
guard obligations and no owned writes. Durable refusal, lost-acknowledgement
recovery, atomic effects/consumption and current disclosure after retry require
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
recovery with current disclosure permission. The amended #178 explicitly scopes
the first delivery to the common protocol with one real claim consumer; all
other command-family integrations remain open under #167. The whole #175 epic
is no longer its blanket predecessor, but the concrete first-consumer authority
and producer prerequisites remain. No cyclic blanket #353 replacement or fake
attempt closes that ordering. #193 still owns disaster/store-loss recovery.

## 10. Falsifiable invariants and production-path verification

IDs below belong to this revision. They supersede the earlier unapproved
INV-001 through INV-012 proposals; no prior approval or passing test transfers.
“Production entry” means the proposed provider on a genuinely bound UnitOfWork
created through production composition, not an HTTP route opened by this PR.

The following applicability ledger controls the initial release. It preserves
every invariant's programme disposition; deferred human-specific rows below
are retained design obligations, not current executable cases or passing tests.

| Invariants | Initial claim/read disposition |
|---|---|
| AUTH-001 | Complete coverage of the exact canonical admitted set, both full rules and all branches; exact membership equality and excluded-action rejection. The other eighteen catalogue rows are not passed. |
| AUTH-002–014 | Retained in full for the selected scope, including current representation/CP3/sharing/revocation, truthful failure evidence, attempt/guard binding, prepared-only output and closed production composition. |
| AUTH-015–017 and AUTH-019 | Human preparation, prospective-finalization and challenge/candidate equality execution is deferred under #175. No first-release API, synthetic proof, success stub or passing claim. Exact detailed design remains at revision 6. |
| AUTH-018 | Retain current attempt/protocol-role isolation and truthful original-write retry. Current disclosure authorization remains required; human-act/challenge-specific execution is deferred, not passed. |
| EXC-001–007 | Retained: one source/path, no duplicate matrix or durable state, no speculative deferred API, complete invariant evidence, no automatic size increase; taste alone is not a Blocker. |

| ID and invariant | Owning code area | Required negative case through the production entry |
|---|---|---|
| AUTH-001: one exact canonical rule source; full selected admission and evaluation coverage | Verified rule loader and coverage checks | Wrong digest, missing/duplicate/extra rule, altered admitted set, invalid closure, excluded action or mismatched caller schema hint cannot produce an executable rule or fallback outcome. Test every branch of both complete selected rules, including all read-resource alternatives; one claim example or blanket refusal fails completion. |
| AUTH-002: callers cannot choose restrictions or mirrored proof | Bound input and rule-selected ingress/extraction | Supply forged stage/posture, tenant, schema, time, scope or policy hints; none weakens evaluation. Invalid ingress creates no fabricated decision. |
| AUTH-003: identity, representation and CP3 are independently proven | Actor/path resolver | Organization without natural-person proof, sponsor without authority, missing CP3 snapshot, and AI-metadata omission/retry never manufacture an eligible path. |
| AUTH-004: target, typed input, effect subject and scope are distinct | Tenant resource reader and rule interpreter | Use a wrong-kind/foreign/missing target with a valid local scope, stale revision, or unproven prospective absence; no unproved eligibility. |
| AUTH-005: one independently sufficient source path | Role/grant/delegation evaluator | Role anchored to Farm A plus grant for Farm B, revoked delegation source, or two individually insufficient grants cannot authorize Farm B. |
| AUTH-006: every applicable closed constraint is evaluated | Rule/path and action-level evidence-policy evaluation | Unsupported non-empty condition, wrong exact purpose/family token or unresolved required evidence cannot be ignored. With valid ingress, current globals and an otherwise sufficient read path, omit the rule-selected CP2 qualification evidence: canonical DENY, never prepared ALLOW. A later result qualification, preflight posture or caller flag cannot repair it. Wrong-context or ineligible proof follows the exact canonical failure disposition. |
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
| AUTH-018: evaluation evidence is attempt- and protocol-role-bound, with truthful original-write retry and current disclosure | Bound provider lifetime and write/read frame admission; consumers own lookup, retry, receipts and release | Reuse an old prepared decision in another attempt/closed UoW or substitute a write frame for a read (or the reverse): no consumable handoff. A newly admitted attempt needs fresh current proof. A committed exact retry must not re-evaluate or repeat its original write/consumption, but current protected readback may require a new read evaluation and may refuse after revocation. Consumer integration separately proves unchanged original outcome, original caller projection/bind-once intent, no second write and no forbidden disclosure. Human-act-specific variants remain deferred at revision 6. |
| AUTH-019: provider-owned challenge/final relevant-state equality | Same provider's typed read footprint, rule-selected projection/JCS digest, preparation refusal and final recheck | Change a rule-relevant target revision or representation fact between challenge and act while keeping an otherwise sufficient requester basis/window: no successful preparation or ALLOW from that act. Advance unrelated history outside the projection, changing only the full snapshot ref: preparation/final ALLOW remain possible if all other checks and guards pass. Verify exact provider-produced projection/digest; forged consumer digests or an equality flag cannot bypass recomputation. Relevant drift between preparation and final evaluation also fails. Preparation emits no decision; any canonical REQUIRE_HUMAN_APPROVAL refusal keeps HUMAN_FINAL_ACTION_REQUIRED primary and APPROVAL_CHALLENGE_STALE diagnostic. Consumer integration separately proves durable generation invalidation and a new challenge/act before retry after drift. |

Test setup uses fictional data and the existing separately owned provisioning
path. No production bootstrap or grant mutation is added to make fixtures
work. Relevant cases require real PostgreSQL tenant binding, two-tenant
isolation, exact currentness inputs and recorded read provenance; a pure
function fed caller-authored grant dictionaries is insufficient.

The applicability ledger above governs these cases. The retained human-specific
rows describe future obligations, not methods to expose or tests to mark passed
in this release. Current positive cases must exercise both complete selected
rules, every admitted read-resource alternative and every applicable authority
path through the same production-bound evaluator. Excluded actions and invalid
dependencies cannot be repaired by a smaller admitted set, fabricated proof or
an always-refusing implementation.

The fixture supplies real owner-issued write or governed-read inputs. It must
not implement a second extraction, projection, path-selection or cutoff engine,
mint an authority frame or bypass the source-history gate. An inactive writer,
empty history lookup or individually valid qualifier is not completeness proof.
Inspect returned types/bytes and the absence of provider-owned writes. Usable
selected paths must succeed when every requirement is met; missing executable
sources and trusted producers remain gates, not evidence of passing tests.

Separate consumer integration must cover a committed write, later permission
loss and an exact retry: the stored original outcome remains unchanged, the
original write/consumption is not repeated or re-evaluated, and a fresh governed
read may refuse protected disclosure. That fresh read evaluation is not a
second authorization of the original write.

The exact source schemas and trusted input/read interface must exist before
these proposed cases can count as implemented evidence. Consumer race tests
must additionally cover revocation/set changes between evaluation and commit,
exclusive deadlines, duplicate consumption, persistence failure, committed
refusal with lost response, and separately unknown evidence commits.

### Focused verification for the selected interface, including B1/B2 and F3

These are planned cases under existing invariants, not new canonical rules or
claims of executed tests:

- AUTH-006/008/010/013: through the real bound read attempt, use an otherwise
  sufficient direct, role-targeted, delegated or SharingGrant path but omit
  `EP_CP2_READ_QUALIFICATION_V0_2` evidence; each actual read is DENY, including
  the software-agent case. Substitute wrong-tenant/intent/snapshot or ineligible
  evidence, or an unbound later payload/consumer `qualified` flag: no ALLOW
  bypass; inspect canonical dispositions, exact refs/digests and the footprint.
  With the full eligible profile proof and every other requirement met, obtain
  prepared ALLOW without owned persistence or release. `EP_NONE` on a claim
  must not bypass required source evidence. These cases require the actual
  G2/G3 producer/bindings; a mock qualified flag proves nothing.
- AUTH-002/006/009/010/013: put proof values in an owner-issued read frame
  without resolvable exact evidence references; they cannot satisfy the policy.
  The positive case above must use evidence resolved in the bound snapshot.
  Contrast invalid package admission (no decision) with an admitted evaluation
  whose read evidence policy is inactive or its exact revision unretrievable:
  with all other checks satisfied, require `UNSUPPORTED_EVIDENCE_POLICY` /
  `REQUIRE_REVIEW` and individual evidence dispositions, not an ingress refusal.
  Combined failures retain canonical aggregation, including global DENY precedence.
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
- AUTH-011/012/014: retain the bound evaluation method after closure and call
  it in a rollback-only UoW; no reader runs. Inject a database failure and verify
  the existing rollback/discard path, including a consumer that catches the error;
  no provider commit or false durable result follows. Verify exact
  constructor/slots/import edges and no raw handle.
- AUTH-013: delete a set/absence or external obligation from either selected
  write/read handoff; completeness verification fails. Missing proof of
  continuity between the authority observation and protected write or buffered
  read cannot be replaced by a context label. Actual race prevention, read
  coverage, result qualification, receipt and release still need their owners'
  tests; rule-bound qualification-evidence verification remains provider-tested.
- AUTH-001/018: cover every selected rule branch and read target/path, reject
  excluded actions and cross-role write/read frames, and isolate attempts.
  Consumer integration proves that an exact committed-write retry preserves
  the original result without repeating its write or consumption, while a
  required current read authorization can independently refuse disclosure.
  Human preparation/finalization cases remain deferred under #175, not passed.

## 11. Disposition of the existing nine-blocker review

This section preserves revisions 2–8 and their exact-head review history. Its
older section references and human-handshake language describe those revisions,
not first-release APIs or review of revision 9. The complete previous design is
retained at `725df163ddcd4f93b4675a3041724b1f59ab8151`. The revision 7 entry
below records the new scope; prior findings are not silently erased or promoted
to approval of this changed design.

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

Revision 6 addressed S1 in the reader plan and AUTH-007/009/010 cases. It
requested focused review of that clarification and affected invariants, with
earlier findings kept closed absent new evidence. Its source-failure mapping
is retained here. The revision 5 zero-Blocker disposition is historical, not
review of revision 7; neither revision added a producer or runtime behavior.

### Revision 7: approved release-scope alignment, pending runtime-design review

The task user approved canonical PR #11 at
`4494924998183fe3fa7bc1b63b76a85893335044`; the
[approval record](https://github.com/samovers/OFARM/pull/11#issuecomment-5634389303)
is semantic Phase A approval only. The subsequent issue amendments retain the
full programme while selecting exactly two complete rules for the initial
executable policy. This revision applies that scope to the existing #359 design:

- keep the twenty-row catalogue separate from exact executable membership,
  including all `RECEIVE_READ_DATA` target alternatives and authority paths;
- remove human-preparation and prospective-finalization APIs from the proposed
  initial facade, retaining their complete history and deferred obligations;
- retain one evaluator, with closed and separately owned write/read input roles,
  complete current proof, guard obligations and truthful prepared-only output;
- separate original-write result recovery from current disclosure permission;
- account for all AUTH-001–019 and EXC-001–007 obligations without treating
  deferred execution as passed or weakening source-history completeness.

Revision 7 at `feffb585ec569c6aaa8b5d085e94583d1eb9aeca` received
[an initial zero-Blocker review](https://github.com/samovers/OFARM2/pull/359#pullrequestreview-5187397905)
and [a later B1 finding with F1/F2 follow-ups](https://github.com/samovers/OFARM2/pull/359#pullrequestreview-5187464763).
Both retained the two-action scope and open G2/G3/G4 gates. The later finding
requires the bounded correction below; the earlier disposition does not
override it or approve this new head.

### Revision 8: B1 read-evidence ownership correction

The user directed the bounded correction after reading both reviews. Sections
4–7 now identify the read rule's exact evidence profile, distinguish provider
evaluation from consumer result qualification, propose its closed input role
and retain the missing machine-binding/producer gates. Section 8 preserves
that split through handoff; AUTH-006 and its focused positive/negative cases
make missing or substituted proof testable without inventing an evidence source.

F1's existing `AUTHORIZATION_TRACE` read-target coverage remains under G3-READ;
F2's reported facade experiments inform G3-SHAPE. Their unresolved implementation
work is not added to this PR. The revision-4 human-handshake correction and
review closure remain historical facts; the later scope defers that execution,
not its safeguards or past evidence.

The [focused revision 8 review](https://github.com/samovers/OFARM2/pull/359#pullrequestreview-5187572304)
at `f97fe8f73d956d2dd6c0f82f133d6800b71055fe` accepted the ownership correction
and F1/F2 records, while reporting B2 on the direct-value proof carrier and F3
on the package-versus-evidence-policy failure wording. Accepting those records
did not close the underlying G3 work or approve implementation.

### Revision 9: B2 evidence resolution and F3 failure distinction

The user directed these bounded design corrections after reading that review.
Section 6 removes the direct-value carrier mode: required evidence references
must resolve through the provider's typed tenant reader in the bound snapshot
and satisfy canonical section 12.5. The attempt frame supplies no authoritative
evidence fact. Section 7 distinguishes invalid package admission from an
unavailable/inactive evidence policy during an admitted evaluation, preserving
its canonical reason, default outcome, evidence disposition and aggregation.
The focused verification above covers both distinctions under existing AUTH
invariants; these are planned cases, not executed runtime evidence.

Revision 9 is REVIEW_PENDING. Review only B2/F3 and affected invariants absent
new evidence of a broader defect. G2/G3 and later exact G4 approval remain open.
No canonical semantics, evidence producer, runtime method, budget or workflow
gate is changed by this revision.

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

F2 in the [later revision-7 review](https://github.com/samovers/OFARM2/pull/359#pullrequestreview-5187464763)
reports two untyped facade probes: 20 added lines in a straightforward version
and 17 in a compressed version. The latter reached 537/520 UoW lines and
949/940 group lines; the existing checker also rejected its public surface,
slots and non-facade dependency. These are the reviewer's specific experiments,
not a universal minimum, a typed implementation estimate or an approved budget.
This revision does not reproduce or adopt the probe code. G3-SHAPE must measure
the actual typed partition and review both shape and size; no automatic budget
increase or relocation to hide growth is authorized. Moving work to another
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

Revision 7 proposes this exact selected-scope shape. The prior two-method
proposal remains at revision 6; it is not a speculative initial-release API:

```text
public surface = {binding, batch, begin_batch,
                  resolve_commit_operation_claim_draft_runtime_bundle,
                  evaluate_authorization}
constructor = (self, binding, allocate_batch, resolve_bundle, authorization)
slots = {__binding, __active, __allocate_batch, __batch, __resolve_bundle,
         __selector_state, __selected_bundle, __rollback_only,
         __authorization}
authorization = one private, closed typed evaluation callable
```

The callable evaluates only the exact admitted selected rules; it is not a
generic executor. The manager builds it against the same connection and
privately held principal/binding; `_finish` replaces it with a closed callable.
Public `ApplicationRuntime` methods and existing authentication, audit and selector
semantics do not change. The one new UoW method checks lifetime/rollback-only;
it does not allocate a batch, commit, acquire locks or choose policy. Concrete
reader SQL stays in the private tenant authority adapter, not the facade or a
legacy module. Architecture verification must allow only those exact new
edges and preserve the existing raw-handle, generic-SQL and legacy firewalls.

Proposed implementation partition is the evaluator, narrow reader and closed
local input/output types needed by this one evaluation operation for both
selected rules; no plugin registry, generic policy framework or parallel
authorization path. The type dependency
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
| EXC-001 — one authoritative path | One canonical semantic source and one production authorization evaluator for both complete selected rules; no second extractor, relevant-state projection, path-selection or cutoff engine in consumers. |
| EXC-002 — no avoidable duplication | No handwritten second matrix, compatibility authority API, extra durable decision store, retry ledger, or copied schema inventory. |
| EXC-003 — direct invariant trace | The AUTH-001–019 ledger maps each obligation to retained selected evaluation or explicit deferred human execution. Current typed entry, bound reader, evidence and handoff require real production-path tests; deferred rows are not passing evidence. Missing real reachability blocks completion. |
| EXC-004 — delete superseded owned paths | Withdraw the old plan; introduce no legacy compatibility path. The quarantined legacy system is not an owned production path and is not deleted as an unrelated migration. |
| EXC-005 — abstractions pay rent now | Closed bound input/output and write/read roles prevent mixed tenant/rule/attempt facts and authority/persistence confusion. A narrow reader contains existing connection authority. No deferred preparation/prospective-evidence API, generic policy engine, plugin registry, public SQL facade or future dispatcher. |
| EXC-006 — simpler credible alternative | Adding a table to kernel.authority fails production isolation and canonical ownership. A pure helper alone fails the bound production-read outcome. A new transaction owner is unnecessary and crosses into #178. The proposed provider plus typed reader is the smallest plausible slice, subject to gate G3. |
| EXC-007 — taste alone is not a Blocker | Private naming and test partitioning are Preferences after the authority, lifetime, exact surface and measured size constraints are satisfied. A demonstrable invariant failure is not dismissed as taste. |

## 13. Gates, provisional posture, and review state

This is a **provisional design**, not permission for a temporary runtime.
Planning against exact approved candidate semantics is useful before
deployment, but executable bytes and concrete trusted interfaces are absent.
No fallback, weakened proof, old-schema compatibility or synthetic authority
path is authorized.

| Gate | Current state and what remains before implementation approval |
|---|---|
| G1 — Delivery scope | First-release amendment applied in issue #353 with the preserved record in section 2. The later formal decision card must include both complete selected rules and every read target/path, with eighteen evaluations and human workflows deferred. This is not implementation approval. |
| G2 — Canonical readiness | Satisfy the pre-runtime stages over the full selected transitive closure, including CP2A-DEP01 source-history/historical-admission proof, and replace missing entries in section 5 with reviewed exact promoted/extracted bytes and provenance. All eleven stages remain required: stage 11 is the later runtime work, not a prerequisite to its own approval. Whether history closure can be proved with qualifying-record authoring non-executable remains unresolved; semantic approval or an individually valid qualifier does not close it. |
| G3 — Concrete trusted interface | Sections 6, 8 and 12 propose one closed evaluation entry, distinct write/read input roles, the trusted-source map, coherent reads and complete guard handoff. Review those choices and close the items below; no production factories, snapshot proof, measured query bounds or final module budget are implied. Prove independently useful full selected coverage through real production composition, not human APIs or fabricated fixtures. |
| G4 — Fresh OFARM2 approval | Review this corrected Phase A to zero Blockers, then present a complete decision card naming existing PR #359 and obtain the required exact later task-user approval. No such card is issued by this revision. |

The remaining G3 work is bounded, not a request to restart canonical design:

| Item | Required closure evidence | Boundary and sequencing |
|---|---|---|
| G3-INPUT | Exact mappings and real producers for principal/representation/CP3, required principal/session validity, closed write/read attempts and deadlines, and compatible selection; reject forged/mixed frames through production composition | Consume existing accepted producers where sufficient. Human-act capture is deferred, not a substitute for required current validity. Any new authentication/session, selection or transaction authority needs separately scoped work and user direction before edits; do not mint proof here. |
| G3-READ | Exact admitted schema/hash/extractor mapping, coherent SQL, complete source visibility/history/currentness and canonical snapshot proof, truthful global/path/infrastructure failure encoding, bounded representative workload, and continuity from authority observation to protected write or buffered read; include the exact rule-bound qualification-evidence source/producer and F1's full read-target coverage below | Reader/projection and evidence evaluation belong here after G2. Missing storage, permission, source-history/snapshot authority, qualification-evidence producer or transaction protection belongs to its owner, not a hidden provider capability. |
| G3-HANDOFF | Actual write and governed-read interfaces covering every record/set/absence/external/time obligation and attempt-bound evidence, with independently usable provider completion tests; prove read-qualification inputs reach final evaluation in the required context/order | Settle with #178 and the separately owned governed-read design before approving provider code. Durable write coordination and read coverage/result qualification/receipts/release stay with their owners; rule-bound qualification-evidence evaluation stays with this provider. Required real producers must precede their use; later consumer delivery cannot excuse invented fixtures or a type-only prerequisite. |
| G3-SHAPE | Review the exact facade proposal and architecture edges in section 12, then a measured final partition/size and focused production-path test plan against the admitted bindings | One authorization boundary. Existing zero headroom is explicit; no automatic checker relaxation or budget increase. |

F1 is recorded under G3-READ, not a narrowed release scope: full
`RP_READ_TARGET_ONE` coverage includes an existing `AUTHORIZATION_TRACE` target
and a separate `RECEIVE_READ_DATA` decision for that read. An eligible trace-read
case and a missing-authority/evidence refusal belong in the eventual AUTH-001/006
coverage. This does not expose the provider's own internal output, activate a
trace endpoint or waive redaction/qualification/release controls. F2 remains
under G3-SHAPE with the qualified probe measurements in section 12; no runtime
or checker change is made to close either follow-up in this design correction.

The #353 -> #178 -> #176 sequence describes capability completion, not the
separate governed-read protocol's ownership. It cannot postpone an indispensable
write/read input producer until after its consumer. If G3 requires an authority
producer that exists only in unfinished #178 work, that
is a dependency cycle to resolve before approval, not permission to use fake
frames. First determine whether an already accepted interface suffices. If
not, propose an independently usable prerequisite in its own boundary and
reconcile the Delivery issue structure with the user before creating it.
Neither a type-only companion PR nor silently expanding #353 resolves this.

Evidence requiring redesign: a machine binding contradicts the approved
candidate; the exact reader/guard/proof needs a new authority; full admitted
coverage cannot be supplied by one coherent provider; source-history closure
requires an additional executable action or writer; or provider-owned durability
is requested again. Stop and obtain a separately reviewed scope decision where
required; no extra action/writer, blanket UNAVAILABLE or weaker proof is implied.
The upgrade path is a reviewed revision with exact bindings and concrete
interfaces, and a new semantic decision version where
required—not a compatibility fallback.

Separate downstream work: #178 command identity/atomic consumption/results;
#176 temporal Delivery selection after its prerequisites; #177 output and
disclosure planning; #175 grant mutation/bootstrap children; #193
disaster/store-loss recovery. The old command successor is a compatibility
gate for its consumer, not a reason to amend approved canonical PR #26.
No new Delivery issue is created in this revision.

Review disposition: revision 9 is REVIEW_PENDING. G1 is applied; G2/G3 and the
later G4 card/approval remain outstanding. Previous reviews stay attached to
their exact historical heads and are not transferred to this revision. Review
the bounded B2/F3 corrections and affected evidence/failure invariants;
do not restart unaffected findings without new evidence. Exact private names and test-file
partitioning are Preferences only after the
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

What is next: focused review of revision 9's B2 evidence-reference resolution
and F3 package-versus-policy failure distinction at its new head;
close the listed G2/G3 prerequisites with their existing owners before presenting the fresh #359
decision card. No runtime edits, new Delivery issue, baseline or merge are
authorized by this design revision.
