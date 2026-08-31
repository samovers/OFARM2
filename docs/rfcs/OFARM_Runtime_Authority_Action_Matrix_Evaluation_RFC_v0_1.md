# OFARM Runtime Authority Action-Matrix Evaluation RFC v0.1

Date: 2026-08-31

Status: proposed Phase A design; no implementation authority

Delivery issue: samovers/OFARM2#353

Tracking epic: samovers/OFARM2#175

Repository base: samovers/OFARM2 at
88b10a5acac466a1ea3ee85c3006f919c3f97327

## 1. Problem and capability

The current runtime authority evaluator accepts an action stage from its
caller, infers software posture partly from caller-supplied fields, treats some
scope relationships as true without durable proof, and lets each caller choose
an incomplete target shape. A caller can therefore ask the evaluator to reason
inside a weaker authority context than the accepted action requires.

This Delivery issue adds one independently reviewable capability: every
supported runtime authority decision selects one immutable action-class rule,
derives the action stage and actor posture, validates the target against that
rule, proves scope from tenant-bound governed data, and applies grants,
delegations, inheritance, and revocations through one fail-closed evaluator.

The system-visible outcome is that a caller supplies an authenticated Party,
an action class, and target facts. It cannot supply an authoritative stage,
posture, inheritance rule, or delegability decision. Every final allow has one
selected matrix rule, one proved scope path, and one durable decision trace.

The learning value is direct: hostile evidence will show which decisions were
previously dependent on caller-controlled stage or unproved scope. The same
closed interface then becomes the stable input for the later grant-mutation
and bootstrap Delivery issues under #175.

## 2. Primary boundary and effects

### Primary trust boundary

The only primary trust boundary changed by this pull request is runtime
authority evaluation: the boundary that turns an authenticated principal, a
governed action class, target facts, live authority records, and durable scope
evidence into an ALLOW or non-allow decision.

### Permitted effects

This pull request may:

- replace caller-selected action stage and software posture with values derived
  by one executable action-class matrix and governed Party evidence;
- validate the action target against the selected row;
- require tenant-bound durable proof for exact, descendant, and derived-lineage
  scope coverage;
- cap grant inheritance and delegation by the selected row;
- select one deterministic live authority path;
- refuse unknown, incomplete, unsupported, stale, revoked, cross-tenant, or
  ambiguous cases before ALLOW;
- persist the selected rule, derived values, selected authority basis, and
  scope-evidence references through the existing authorization contracts;
- migrate current callers with no compatibility overload; and
- move evaluation inside a caller's already-owned serialized write transaction
  when necessary to keep the check before its governed side effect.

### Non-effects and adjacent boundaries

This pull request must not:

- create, narrow, revoke, rotate, recover, or bootstrap an AuthorityGrant or
  DelegationGrant;
- change authentication, credential verification, principal resolution,
  TenantBinding, database roles, schema, migration, isolation level, advisory
  lock ownership, or transaction ownership;
- add a new action class, contract field, schema, profile, RuntimeBundle
  component, active capability, law statement, or deployment claim;
- implement sponsor-bound software-agent actorship contracts;
- implement sharing-grant mutation, output redaction, output delivery
  permission, or the complete sharing/output permission plan owned by #177;
- change signing, key custody, evidence custody, production bootstrap,
  recovery, or break-glass authority; or
- make production-readiness, legal, certification, or current-compliance
  claims.

Moving an evaluator call inside an existing serialized transaction is
mechanical integration for this authorization boundary. If implementation
would require a new transaction, lock, database role, mutation command, or
isolation rule, work stops and that change becomes separate Delivery work.

### Authority map

| Fact or decision | Authority owner |
|---|---|
| Accepted action vocabulary and semantics | Digest-pinned accepted OFARM Authority Policy Model and Authority Action Matrix in reference |
| One row per accepted action, derived stage, targets, posture, inheritance, and delegability | New immutable kernel action-policy table |
| Current runtime reachability | Existing commit-to-action bindings and non-commit action inventory in kernel policy; the full matrix does not activate an unwired action |
| Authenticated human Party | Existing authentication and principal-resolution boundary, unchanged |
| Party class, lifecycle, and agent-instance reference | Tenant-bound governed Party record |
| Tenant observation and RuntimeBundle receipt | Existing ready Store binding |
| Target containment and lineage | Tenant-filtered, current governed IdentityRecord data and its persisted record row |
| Grant, role, delegation, time, and revocation facts | Existing validated governed records |
| Rule selection, scope proof, path selection, outcome, and trace | AuthorityEvaluator |
| Requested action and target facts | Caller; never authority over derived restrictions |
| Commit, review, evidence, output, and read effects | Existing callers after an ALLOW; unchanged except for the new derived evaluator interface |
| Sharing overlay and output permission plan | #177, not this pull request |
| Grant mutation and production bootstrap | Later #175 Delivery issues |

## 3. Trust model

### Protected assets

- the integrity of every ALLOW or refusal;
- tenant isolation and farm/descendant containment;
- the effective power of live grants and delegations;
- human accountability and the distinction between human, AI-assisted human,
  and autonomous software action;
- revocation effectiveness at the final authority check;
- the integrity of authorization request, result, and trace records; and
- downstream governed truth, evidence, materialization, read, and output
  effects that depend on an ALLOW.

### Trusted sides and components

- the exact source and digest-pinned accepted reference artifacts;
- the reviewed immutable action table after its construction checks pass;
- the existing authenticated principal and tenant binding supplied by upstream
  boundaries;
- a ready Store whose tenant and RuntimeBundle binding already passed startup;
- schema-validated, tenant-filtered governed records returned by that Store;
- the existing append-only store and serialized transaction owner; and
- the process clock under the repository's present time model.

### Untrusted actors, sides, and inputs

- public request bodies and all action, target, target-kind, target-ref, and
  AI-assistance values carried by them;
- internal callers attempting to pass old stage or posture fields;
- unknown action strings and malformed enum-shaped values;
- a Party reference that is missing, inactive, cross-tenant, or of a different
  class from the claimed posture;
- grants, roles, delegations, revocations, target records, anchor scopes, and
  lineage that are missing, expired, revoked, malformed, stale, ambiguous, or
  unrelated to the request;
- a broad tenant or farm grant presented without durable membership evidence;
  and
- extra caller-authored anchors, role IDs, grant IDs, inheritance modes, or
  alleged scope evidence.

### Explicitly excluded attacker capabilities

This boundary does not claim to withstand:

- arbitrary code execution or object mutation inside the trusted Python
  process;
- substitution of reviewed source code, the accepted reference snapshot, or a
  dependency after startup;
- direct database-superuser mutation that bypasses the Store, constraints, and
  append-only controls;
- compromise of credential verification, principal resolution, TenantBinding,
  the host clock, operating system, filesystem, or RuntimeBundle custody; or
- a production authority-mutation writer that ignores the existing serialized
  write discipline. No such supported writer is introduced here.

Those are separate trust boundaries. Excluding them does not make request
fields, caller posture, or unresolved scope evidence trusted.

### Primary risk and containment

The primary risk is an ALLOW reached by selecting a weaker stage or posture, or
by treating an asserted tenant/farm relationship as proof.

Containment is one closed immutable action table, no stage or posture parameter
on the evaluator, posture derived from governed Party evidence, target rules
selected from the action row, durable tenant-filtered scope proof, row-capped
inheritance and delegation, mandatory revocation evaluation, and an outcome
order in which no missing or ambiguous prerequisite can reach ALLOW.

## 4. Executable action-policy contract

### 4.1 Construction

The production source is one tuple of frozen AuthorityActionRule values in a
small authority-policy module. Each accepted action string appears once in
that tuple. The builder returns a read-only mapping and rejects duplicate
keys, missing fields, empty target or posture sets, invalid enums, internally
inconsistent inheritance/delegation combinations, or a row count other than
the accepted twenty.

Repository conformance parses the accepted reference matrix and proves exact
set equality with the code table. The runtime does not parse Markdown and does
not accept an injected table from a caller. If table construction fails,
authority evaluation is unavailable and startup/import refuses. If a runtime
request names no row, it receives a typed input refusal and cannot create an
ALLOW or a fabricated schema-valid decision.

The full twenty-row table describes accepted policy but does not activate
unwired runtime behavior. The existing runtime-supported action inventory
remains a separate reachability fact and must be a subset of the full table.
An accepted but currently unwired action selects its row and returns an
explicit unsupported non-allow.

### 4.2 Target policies

The table uses the existing AuthorizationDecisionRequest target-kind and scope
vocabularies. No parallel contract vocabulary is added.

Target policy O permits CANONICAL_TRUTH at FARM, SITE, FIELD, ZONE,
CROP_CYCLE, LOT, or FACILITY.

Target policy E permits CANONICAL_TRUTH or SUBMISSION_ASSEMBLY at every O scope
and OPERATION.

Target policy S permits CANONICAL_TRUTH at FARM, SITE, FIELD, ZONE, or
FACILITY.

Target policy C permits CANONICAL_TRUTH or SUBMISSION_ASSEMBLY at FIELD,
CROP_CYCLE, or LOT.

Target policy P permits CANONICAL_TRUTH at FIELD, ZONE, CROP_CYCLE, or
OPERATION.

Target policy R permits CANONICAL_TRUTH or CURRENT_STATE_MATERIALIZATION at
FARM, SITE, FIELD, ZONE, CROP_CYCLE, LOT, FACILITY, or OPERATION.

Target policy PI permits PACK_ACTIVATION at FARM, SITE, FIELD, or CROP_CYCLE.

Target policy PA permits PACK_ACTIVATION at FARM, SITE, FIELD, CROP_CYCLE, LOT,
or OPERATION.

Target policy OD permits DOCUMENT_ASSEMBLY, DOSSIER_ASSEMBLY, or
SUBMISSION_ASSEMBLY at FARM, SITE, FIELD, CROP_CYCLE, or LOT.

Target policy OS permits SUBMISSION_ASSEMBLY at FARM, SITE, FIELD,
CROP_CYCLE, or LOT.

Target policy SH permits CANONICAL_TRUTH, PASSPORT_VIEW, DOCUMENT_ASSEMBLY,
DOSSIER_ASSEMBLY, SUBMISSION_ASSEMBLY, or
CURRENT_STATE_MATERIALIZATION at any governed scope except DEPLOYMENT.

Target policy RD permits every SH target plus QUERY_EXECUTION at any governed
scope except DEPLOYMENT.

Permitting a kind/scope pair is not proof that the target exists or belongs to
the grant scope. Scope proof remains mandatory. OPERATION is therefore
refused until its supplied reference resolves through an existing governed
record shape that this implementation can prove; no operation-shaped string is
treated as proof.

### 4.3 Posture policies

Posture H means:

- an active non-SOFTWARE_AGENT Party with no valid AI-assistance facts is an
  accountable human or organization;
- an active non-SOFTWARE_AGENT Party with valid AI-assistance facts is an
  AI-assisted accountable human;
- the AI-assisted posture may ALLOW only after the ordinary live authority
  path succeeds; and
- autonomous software is unsupported and DENY.

Posture HA is the same except a valid AI-assisted human path returns
REQUIRE_HUMAN_APPROVAL, never ALLOW. The later final action must be made under a
fresh accountable-human decision. A missing grant still returns DENY rather
than manufacturing an approval route.

AI-assistance metadata never supplies authority. When present it must name an
active SOFTWARE_AGENT Party consistently with the existing governed Party
record and is traced. A SOFTWARE_AGENT acting Party remains autonomous even if
the caller omits or forges assistant fields. This pull request expressly
enables no autonomous action because the implementation lacks the complete
sponsor, agent-instance, actorship-basis, authority-snapshot, and result
qualification proof required by the active CP3 law.

### 4.4 Inheritance policies

Inheritance policy X permits only an exact target. No descendant or lineage
expansion occurs.

Inheritance policy D permits exact or proven descendant containment. A grant's
stored DESCENDANT_SCOPES value does not bypass target proof.

Inheritance policy L permits exact, proven descendant containment, or an
explicit unique DERIVED_FROM lineage path when the stored grant mode selects
the matching mechanism.

Inheritance policy N applies the action as NO_INHERIT. An exact grant target
can still authorize that exact target even if an older broad grant stores a
more permissive inheritance mode; the selected rule caps the effective mode to
NO_INHERIT and never uses the broader setting. This preserves exact existing
authority while preventing it from flowing.

No policy permits upward inheritance. No policy treats DESCENDANT_SCOPES and
DERIVED_LINEAGE_SCOPES as interchangeable.

### 4.5 Complete row set

Runtime support below means reachable through current production code. A
known but unwired row remains explicit non-allow until a separate approved
caller activates it.

| Action class | Family | Derived stage | Target | Posture | Inheritance | Delegable | Runtime support |
|---|---|---|---|---|---|---|---|
| OBSERVE_CREATE_OBSERVATION | OBSERVE_REPORT | DRAFT_PREPARATION | O | H | L | yes | yes |
| OBSERVE_ATTACH_EVIDENCE | OBSERVE_REPORT | DRAFT_PREPARATION | E | H | L | yes | yes |
| ASSERT_STRUCTURE | ASSERT_SUBMIT | DRAFT_PREPARATION | S | HA | X | yes | yes |
| ASSERT_OPERATION_CLAIM | ASSERT_SUBMIT | DRAFT_PREPARATION | P | H | L | yes | yes |
| ASSERT_COMPLIANCE | ASSERT_SUBMIT | DRAFT_PREPARATION | C | HA | X | yes | yes |
| OPERATE_PLAN_INTERVENTION | OPERATE_INTERVENE | DRAFT_PREPARATION | P | H | L | yes | no |
| OPERATE_REPORT_EXECUTION | OPERATE_INTERVENE | DRAFT_PREPARATION | P | H | L | yes | no |
| REVIEW_REQUEST | REVIEW | DRAFT_PREPARATION | R | H | X | yes | no |
| REVIEW_ACCEPT | GOVERN_DECIDE | PROMOTION | R | HA | N | no | yes |
| REVIEW_REJECT_OR_CONTEST | GOVERN_DECIDE | PROMOTION | R | HA | N | no | yes |
| REVIEW_SUPERSEDE | GOVERN_DECIDE | PROMOTION | R | HA | N | no | no |
| CONTEXT_INSTALL_PACK | CONTEXT_GOVERNANCE | CONTEXT_ACTIVATION | PI | HA | N | no | no |
| CONTEXT_ACTIVATE_PACK | CONTEXT_GOVERNANCE | CONTEXT_ACTIVATION | PA | HA | N | no | no |
| CONTEXT_DEACTIVATE_PACK | CONTEXT_GOVERNANCE | CONTEXT_ACTIVATION | PA | HA | N | no | no |
| OUTPUT_APPROVE_DOCUMENT_ASSEMBLY | ATTEST_SIGN | PUBLICATION | OD | HA | N | no | yes |
| OUTPUT_ATTEST_DOCUMENT_ASSEMBLY | ATTEST_SIGN | ATTESTATION | OD | HA | N | no | no |
| OUTPUT_FILE_SUBMISSION_ASSEMBLY | ATTEST_SIGN | PUBLICATION | OS | HA | N | yes | yes |
| SHARE_GRANT_ACCESS | SHARE_REVOKE | PROMOTION | SH | HA | X | yes | no |
| SHARE_REVOKE_ACCESS | SHARE_REVOKE | PROMOTION | SH | HA | X | yes | no |
| RECEIVE_READ_DATA | RECEIVE_USE | QUERY_READ | RD | H | L | yes | yes |

ATTEST_SIGN is deliberately selected for
OUTPUT_FILE_SUBMISSION_ASSEMBLY. The accepted source permits attest/sign or
assert/submit depending on governance; the stricter existing output-governance
family prevents this implementation from silently widening filing authority.

## 5. Falsifiable invariants and acceptance criteria

### INV-001 — one complete immutable matrix

Exactly the twenty accepted action classes have exactly one complete frozen
row. Duplicate, incomplete, invalid, mutable, or missing construction input
cannot produce a usable evaluator. Unknown and currently unwired action
classes cannot ALLOW.

Production-reachable negative cases: start the production builder with a
duplicate, incomplete, or invalid row and observe startup refusal; invoke the
supported evaluator boundary with an unknown or accepted-but-unwired action
and observe no governed effect.

### INV-002 — callers cannot choose derived restrictions

The evaluator interface has no action-stage, actor-posture, inheritance,
delegability, revocation-check-required, or caller-scope-evidence parameter.
Request and result stages, authority family, posture, effective inheritance,
and delegation eligibility come only from the selected row and governed
records. No compatibility overload remains.

Production-reachable negative cases: send an API request containing a forged
stage or posture field and observe ingress refusal; call the internal
production interface with an old keyword and observe a pre-evaluation type
refusal; compare a valid call's persisted stage with its matrix row.

### INV-003 — posture is governed and cannot create authority

Unknown or inactive Parties refuse. Party class and agent instance come from
the governed Party record. Valid AI assistance preserves the authenticated
human as accountable actor and can only retain or narrow the outcome.
Autonomous software never ALLOWs in this version. REQUIRE_HUMAN_APPROVAL is
possible only after a valid live human-side authority path exists.

Production-reachable negative cases: evaluate an inactive Party, a
SOFTWARE_AGENT Party with omitted or forged human metadata, mismatched
assistant evidence, an AI-assisted high-governance action with a live grant,
and the same action without a grant. Outcomes are respectively non-allow,
non-allow, non-allow, REQUIRE_HUMAN_APPROVAL, and DENY.

### INV-004 — target policy is selected by the action

Every known action accepts only the target kinds and scope types in its row.
Malformed refs, absent required target facts, wrong kinds, DEPLOYMENT, and
unsupported kind/scope combinations refuse before grant matching.

Production-reachable negative cases: request REVIEW_ACCEPT on PACK_ACTIVATION,
OUTPUT_FILE_SUBMISSION_ASSEMBLY on DOCUMENT_ASSEMBLY, an observe action at
DEPLOYMENT, and a malformed target ref. None reaches ALLOW.

### INV-005 — scope coverage requires current durable proof

An exact target must itself resolve as a current governed target. A tenant
grant covers only a target returned under the same tenant-bound Store. A farm
grant covers a descendant or derived target only through one complete,
same-tenant, active, acyclic, unambiguous containment or lineage path.
Missing, wrong-kind, inactive, stale, cross-tenant, cyclic, or multiply
anchored evidence refuses. Caller-authored anchors are ignored.

Production-reachable negative cases: use a missing target, an ended IdentityRecord,
a FIELD ref that resolves to a Party, a target stored only in another tenant,
a target with two farm anchors, a cyclic lineage, and a same-shaped caller
anchor with no stored record. None reaches ALLOW.

### INV-006 — every ALLOW has one live grant path

The selected path has an active Party, a current role when used, an active and
time-valid grant for the exact action, target coverage under the row, and no
effective revocation. Revocation checking is mandatory. Missing or revoked
only paths refuse.

Production-reachable negative cases: evaluate with no grant, an expired grant,
an inactive grant, a grant for a different action, an expired role-targeted
grant, and a revoked grant. None reaches ALLOW.

### INV-007 — inheritance never widens the row

The row caps the stored inheritance mode. Exact, descendant, and derived
lineage remain distinct; upward inheritance never occurs. An invalid mode,
unsupported mode/action pair, absent containment proof, or ambiguous lineage
refuses.

Production-reachable negative cases: use a FIELD grant for a FARM target, a
NO_INHERIT farm grant for a field, DERIVED_LINEAGE_SCOPES with no DERIVED_FROM
path, and a broad review grant against a child target. None reaches ALLOW.

### INV-008 — delegation cannot manufacture or widen authority

A delegated path exists only when the row permits delegation, the delegation
is active and time-valid for the action and target, and every named source
grant is still controlled by the delegator, live, unrevoked, and independently
covers both the delegation scope and the requested target. Delegation cannot
widen action, time, target, inheritance, posture, or purpose.

Production-reachable negative cases: delegate REVIEW_ACCEPT, use a missing
source grant, revoke the source, expire the delegation, change the delegated
action, request beyond either scope, and use lineage inheritance forbidden by
the row. None reaches ALLOW.

### INV-009 — outcome ordering is fail closed

Input, matrix, actor, target, scope, grant, source authority, and revocation
validation all precede posture disposition. Human approval cannot resurrect a
missing or revoked path. Only outcome ALLOW permits the caller's governed
effect.

Production-reachable negative cases: request an autonomous output action with
no grant and an AI-assisted output action backed only by a revoked grant.
Both DENY; neither returns a misleading approval route or writes the output.

### INV-010 — the durable trace contains only derived proof

For a known action the persisted request, result, and trace identify the exact
action-row key, derived stage and authority family, target scope/time, selected
role/grant/delegation basis, effective inheritance, revocation result, actor
classification, and the durable tenant/containment/lineage record refs used.
Only one deterministic least-authority path is recorded as used. Caller-
authored authority facts never appear as proof.

Production-reachable negative cases: submit fake role, grant, anchor, and
inheritance facts alongside a valid request; create two live candidate paths
in opposite insertion orders. The fake facts are absent and both orders select
the same proved path and decision.

### INV-011 — all callers use one interface without capability expansion

Every current evaluator call names only the authenticated Party, action,
typed target facts, and non-authoritative purpose/assistance facts. Old stage
and acting-agent authority arguments are deleted. The manifest's supported
action set remains unchanged and is proven to be a subset of the complete
table. Existing accepted SI outcomes remain assertion-equivalent except where
the old outcome depended on caller stage/posture or unproved scope; those
become explicit refusals.

Production-reachable negative cases: repository search and architecture tests
find an old argument or alternate evaluator path; manifest grounding detects a
newly activated action; existing SI conformance detects any unapproved outcome
change.

### INV-012 — check, trace, and effect stay ordered

Every write-capable current caller evaluates and persists the authorization
request, trace, and result inside its already-owned serialized transaction
before its governed effect. A non-ALLOW writes no governed effect. Read access
is re-evaluated on each request. No new lock, transaction owner, database role,
or mutation path is added.

Production-reachable negative cases: exercise commit, actor attribution,
FFSNaprave evidence attachment, document freeze, submission freeze, and read
through their supported entry points while observing transaction state and
record order. Inject each non-allow condition before the final evaluation and
prove the governed effect is absent while the refusal trace is durable.

## 6. Proposed architecture and data flow

### 6.1 Small policy module

A new kernel/authority_policy.py owns only frozen policy values:

- closed enums for stage, authority family, target kind, scope type, actor
  posture, posture disposition, and inheritance policy;
- a frozen AuthorityTarget value that binds target kind, scope type, scope ref,
  and optional governed target ref;
- a frozen AuthorityActionRule value;
- the single twenty-row source tuple;
- strict construction into a read-only action-to-rule mapping; and
- a lookup that returns a rule or a typed refusal, never a fallback row.

It does not read the database, mutate grants, parse Markdown, know SI profile
content, or dispatch effects.

### 6.2 Scope proof

A focused resolver inside the authority boundary accepts the selected rule,
the target, a candidate grant scope and mode, the evaluation time, and the
tenant-bound Store.

It:

1. validates the target against the row;
2. confirms the grant's tenant/farm anchor is itself valid;
3. loads the target only through tenant-filtered Store methods;
4. validates record kind, IdentityRecord type, lifecycle state, and row tenant;
5. walks only explicit anchor scopes for descendant containment;
6. walks only explicit DERIVED_FROM edges for lineage mode;
7. bounds traversal, detects cycles, and requires one unambiguous path;
8. refuses unsupported OPERATION proof rather than guessing; and
9. returns a frozen ScopeProof containing the effective inheritance mode and
   ordered durable evidence refs.

FARM, SITE, FIELD, CROP_CYCLE, LOT, and FACILITY map to the corresponding
active IdentityRecord type. ZONE maps only to active MANAGEMENT_ZONE or
MICROCLIMATE_ZONE. TENANT proof uses the Store's persisted RuntimeBundle tenant
selection plus the target record's tenant-filtered row. DEPLOYMENT is
unsupported. No identifier prefix is evidence.

### 6.3 Actor and authority paths

AuthorityEvaluator resolves the active Party and derives:

- accountable human/organization from a non-SOFTWARE_AGENT Party;
- AI-assisted accountable human only from consistent assistance facts whose
  assistant resolves to an active SOFTWARE_AGENT Party; or
- autonomous software from a SOFTWARE_AGENT acting Party and its governed
  agent-instance reference.

It gathers validated roles, direct grants, delegations, source grants, and
revocations. Each candidate becomes an immutable AuthorityPath only after its
own scope proof succeeds. A delegated path contains both source and delegation
proof.

When more than one live path exists, the evaluator selects deterministically:
exact before inherited, direct before delegated, shorter scope proof before
longer proof, then stable record IDs. It records only the selected path as
used. Other candidates do not create ambiguity because they are independent
ways to prove the same authority; ambiguous scope evidence inside any selected
path still refuses that path.

### 6.4 Decision interface

The replacement interface is conceptually:

    evaluate(
        acting_party_ref,
        action_class,
        target,
        ai_assistance=None,
        use_purpose=None,
        refusal_context=None,
    )

There is no action_stage, acting_agent_ref, actor_posture, inheritance_mode,
delegable, revocation_check_required, role basis, grant basis, anchor scope, or
scope-evidence argument.

refusal_context may carry an existing non-authoritative routing fact such as
offline replay. It may choose only between non-allow dispositions already
permitted by policy and can never produce ALLOW or REQUIRE_HUMAN_APPROVAL.

The evaluator populates the existing AuthorizationDecisionRequest,
AuthorizationDecisionResult, and AuthorizationDecisionTrace shapes. The
requestedActionClass is the unique selected matrix-row key. The request carries
the derived actionStage and requiredAuthorityFamily. Existing trace basis
fields carry only the selected path. Existing
dataSovereigntyBoundaryRefs carries the ordered durable tenant and scope proof
refs. No contract edit is required.

Malformed input for which no honest contract stage or rule exists returns a
typed boundary refusal rather than minting a misleading authorization
envelope.

### 6.5 Caller composition

- GatePipeline derives the target from normalized governed submission facts.
  Operation claims use their governed execution target rather than a blanket
  farm string. Structure and review cases use their governed case/anchor scope.
- ActorAttributionValidator evaluates the same ASSERT_OPERATION_CLAIM row and
  governed operation target; it cannot select DRAFT_PREPARATION separately.
- FFSNaprave evidence attachment uses the E target and evaluates inside its
  existing serialized transaction before evidence insertion.
- SI output freeze uses DOCUMENT_ASSEMBLY or SUBMISSION_ASSEMBLY and evaluates
  inside its existing serialized transaction before publication records or
  frozen output.
- evaluate_read uses the RD target and re-evaluates on each request. Its
  existing SharingGrant overlay remains bounded pending #177 and receives no
  new mutation, redaction, or delivery authority here.
- Runtime manifest construction keeps the current reachable action inventory
  and proves it is a subset of the complete matrix.

No adapter preserves the old evaluator signature.

## 7. State and ordering

### 7.1 Evaluation state machine

    REQUEST_FACTS
      -> RULE_SELECTED
      -> ACTOR_RESOLVED
      -> TARGET_VALIDATED
      -> SCOPE_PROVED
      -> AUTHORITY_PATHS_EVALUATED
      -> LIVE_PATH_SELECTED
      -> POSTURE_APPLIED
      -> DECISION_MINTED
      -> DECISION_PERSISTED
      -> EFFECT_PERMITTED only when outcome is ALLOW

Any failed transition goes to REFUSED. There is no transition from REFUSED,
REQUIRE_REVIEW, or REQUIRE_HUMAN_APPROVAL to EFFECT_PERMITTED.

Forbidden orderings include:

- grant matching before a complete rule and target exist;
- posture selection from a caller enum or stage;
- human-approval routing before a live path exists;
- descendant or lineage inheritance before durable proof;
- delegation before source authority is proved;
- an effect before the decision records are persisted; and
- reuse of a decision across a later final action or read request.

### 7.2 Time-of-check/time-of-use boundary

Authority is re-evaluated at the final supported gate. Existing commit and
review work already runs under the Store's serialized transaction. The
FFSNaprave and output callers move the evaluation into their existing
serialized transaction so target evidence and authority are checked before the
same transaction's effect.

This issue does not invent a grant-mutation control plane. A later governed
mutation command must use the same serialization and force a fresh evaluation;
that is separate #175 Delivery work. Complete sharing/output atomic permission
planning remains #177.

### 7.3 Durability, rollback, and recovery

No schema, migration, or stored-record shape changes. Decision envelopes and
effects continue to commit or roll back under their current transaction owner.
The new table and proof objects are derived, immutable process values and need
no recovery. Rollback is code rollback before deployment; there is no data
rewrite. Existing historical traces remain truthful records of the evaluator
version that produced them and are not rewritten.

## 8. Expected areas and complete-slice companions

Expected production areas:

- kernel/authority_policy.py — new immutable table and bound value types;
- kernel/authority.py — derived evaluator, scope proof, deterministic path,
  outcome ordering, and trace population;
- kernel/policy.py — retain caller reachability and routing facts while
  deleting duplicated authority semantics;
- kernel/stages.py and kernel/validators.py — migrated generic callers;
- kernel/profiles/si_ffs/ffsnaprave_adapter.py and
  kernel/profiles/si_ffs/outputs.py — migrated profile callers and check/effect
  ordering;
- kernel/manifest.py — grounding only if needed to prove current supported
  actions remain a subset; and
- kernel/legacy_m1/api.py only if the supported public boundary needs an
  explicit old-field refusal beyond its existing closed request schema.

Expected tests and fixtures:

- a focused kernel/tests/test_authority_action_matrix.py;
- focused updates in kernel/tests/test_stages.py,
  kernel/tests/test_conformance.py, and
  kernel/tests/test_runtime_bundle_receipts.py;
- affected SI FFSNaprave and output tests;
- gate fixture expectations only where a formerly caller-controlled stage or
  unproved scope becomes an explicit refusal; and
- conformance/review_baseline_test_inventory.json regenerated only because the
  canonical collected node inventory changes.

Expected documentation and mechanical evidence:

- this durable RFC in the same implementation pull request;
- the draft pull request Phase A and later compact approval navigation;
- conformance/rewrite_architecture_check.py only if its existing exact source
  inventory requires mechanical registration of the new module or deleted
  path; and
- no reference, contract, profile descriptor, RuntimeBundle component,
  migration, claim, or deployment file.

Complete prerequisites: #172, #173, and #174 are merged. No additional
prerequisite is required.

The expected path list is a scope prediction, not approval authority. A newly
discovered test, fixture, documentation, or mechanical inventory file may
travel only when it proves this same evaluator boundary and adds no authority,
effect, capability, or trust boundary.

## 9. Smallest coherent change and code excellence

This is the smallest complete vertical slice because a table without evaluator
enforcement leaves caller authority intact; evaluator changes without scope
proof still permit unproved targets; scope proof without caller migration
leaves the bypass; and behavior without focused hostile tests and durable
design evidence is not independently reviewable.

### EXC-001 — one authoritative path

There is one code-owned action-rule table, one rule lookup, one target/scope
proof path, one grant/delegation evaluator, and one decision constructor.
Current runtime reachability remains a distinct fact, not a second semantic
matrix.

### EXC-002 — no avoidable duplication

Stage, posture, target rules, inheritance, and delegability disappear from
callers. The production table does not parse or copy the reference Markdown at
runtime. Tests compare the table keys to the reference artifact rather than
maintaining another handwritten expected action list.

### EXC-003 — direct invariant trace

Each invariant below maps directly to the table builder, target/scope resolver,
path evaluator, outcome ladder, decision constructor, migrated callers, and
focused hostile evidence. There is no permissive fallback.

### EXC-004 — delete superseded paths

Delete the old action_stage, acting_agent_ref, and
revocation_check_required authority parameters; the stage-sensitive software
branch; blanket tenant/farm scope assumptions; all-candidate trace basis; and
every old caller argument. No compatibility shim, feature flag, or alternate
evaluator remains.

### EXC-005 — abstractions pay rent now

AuthorityActionRule isolates the accepted row and removes five correlated
caller decisions. AuthorityTarget binds target facts now used by all current
callers. ScopeProof prevents repeated or guessed containment logic. AuthorityPath
binds the selected direct or delegated proof and prevents mismatched trace
lists. No generic policy framework, plugin registry, dependency injection, or
future action dispatcher is added.

### EXC-006 — simplest credible alternative

The simplest alternative is a dictionary added directly to authority.py plus a
few conditional checks. It is rejected because it leaves correlated raw
dictionaries mutable, mixes policy construction with database evaluation, and
cannot give one bound target, scope proof, or selected path to the trace without
duplicated validation. The proposed single small policy module and focused
immutable values are the minimum additional concepts that directly enforce
INV-001, INV-004, INV-005, and INV-010.

### Elegance audit

- semantic sources of truth added: one action table;
- runtime reachability sources retained: one existing caller inventory;
- authoritative decision transition points after the change: one evaluator;
- compatibility paths retained: zero;
- durable state added: zero;
- migrations added: zero;
- abstractions added: four small immutable values plus one strict builder;
- superseded authority inputs deleted: stage, agent-posture proxy, optional
  revocation check, caller inheritance, caller delegability, and caller scope
  proof;
- rewrite decision: a focused evaluator rewrite is safer and smaller than
  layering row lookups over the current first-candidate and blanket-scope
  branches.

## 10. Verification and traceability

| Invariant | Owning implementation | Smallest hostile evidence | Final verification |
|---|---|---|---|
| INV-001 | authority_policy builder and lookup | duplicate, missing, invalid, unknown, and unwired action cases | focused pure tests plus exact reference/table set comparison |
| INV-002 | evaluator signature and decision constructor | forged stage/posture public input and old internal keywords | API, signature, repository-search, and architecture checks |
| INV-003 | actor resolver and posture map | inactive Party, forged assistant, autonomous Party, assisted high action with/without grant | focused PostgreSQL authority tests |
| INV-004 | AuthorityTarget and row target policy | wrong target kinds, DEPLOYMENT, malformed refs | focused pure and PostgreSQL tests |
| INV-005 | scope resolver | missing, wrong-kind, inactive, foreign-tenant, multi-anchor, cyclic-lineage targets | two-tenant and hostile containment tests |
| INV-006 | direct path evaluator | absent, expired, inactive, wrong-action, role-expired, revoked grants | focused authority tests |
| INV-007 | scope resolver plus row cap | upward, no-inherit descendant, missing-lineage, broad review descendant | focused inheritance tests |
| INV-008 | delegated path evaluator | nondelegable action, missing/revoked source, expiry, action/scope/mode widening | focused delegation tests |
| INV-009 | outcome ladder | no-grant autonomous output and revoked assisted output | outcome-order tests plus absent-effect assertions |
| INV-010 | path selector and trace builder | caller fake bases and reversed insertion order | exact request/result/trace assertions and contract validation |
| INV-011 | all evaluator callers and manifest grounding | old signature scan, new action claim, SI outcome drift | caller tests, manifest tests, SI conformance |
| INV-012 | GatePipeline and profile caller composition | non-allow at each write entry point with transaction/order observation | commit, FFSNaprave, output, read, rollback, and record-order tests |

Required cheap local checks after implementation:

1. focused pure action-table tests;
2. focused authority, caller, SI FFSNaprave, output, and runtime-receipt tests;
3. the full PostgreSQL-backed test suite;
4. python3 conformance/ofarm_pkg_contract_check.py;
5. the standalone architecture check at the repository-pinned Python and Ruff
   versions;
6. canonical test-inventory verification after mechanical regeneration;
7. Ruff over every changed Python file;
8. git diff --check; and
9. an exact base-to-head scope and forbidden-area inspection.

Final hosted evidence after implementation requires the repository's normal
lightweight checks, exact-head zero-Blocker content review, baseline admission,
required hosted baselines and publication, and final receipt. Phase A alone
does not request expensive baselines.

The design-only baseline observation was limited and honest: three pure tests
in kernel/tests/test_stages.py passed at the exact base. Seven database-backed
tests did not execute because the isolated Phase A snapshot had no PostgreSQL
socket. That is environment absence, not passing database evidence.

## 11. Non-goals and follow-ups

Non-goals are the non-effects in section 2, especially grant/delegation
mutation, production bootstrap/recovery/break-glass, complete sharing/output
authorization, new actorship contracts, new actions, law/contracts, schema,
profiles, capabilities, deployment, and production-readiness.

Follow-ups:

- after #353 settles the interface, #175 may create one Delivery child for
  governed grant/delegation creation, narrowing, and revocation;
- a separate later #175 child owns production bootstrap, recovery, and
  break-glass custody;
- #177 owns complete sharing and output permission plans, redaction, and
  delivery authorization; and
- positive autonomous-software support requires separate Delivery work that
  implements and proves the accepted CP3 sponsor-bound actorship evidence.

No follow-up is a prerequisite for this evaluator slice. None may be appended
to this pull request merely to clear review.

## 12. Provisional posture

Not provisional.

The implementation remains pre-deployment and does not authorize deployment,
but the evaluator design itself is not a temporary semantic compromise. It is
the conservative implementation of the currently accepted action vocabulary:
unknown and autonomous cases refuse, current runtime reachability does not
expand, and later mutation or actorship work must consume this interface rather
than replace its fail-closed ownership.

## 13. Open decisions and review disposition

Resolved design decisions:

- ASSERT_OPERATION_CLAIM derives DRAFT_PREPARATION, matching the accepted
  temporal governed-command requirement and the fact that assertion is
  distinct from REVIEW_ACCEPT promotion.
- all observation, assertion, operation-report, and review-request preparation
  rows derive DRAFT_PREPARATION; governance review rows own PROMOTION.
- OUTPUT_FILE_SUBMISSION_ASSEMBLY uses the conservative ATTEST_SIGN family.
- no autonomous software posture is enabled.
- DERIVED_LINEAGE_SCOPES is accepted only where row policy L permits it and
  only with a unique durable DERIVED_FROM path.
- accepted-but-unwired rows are known policy and explicit non-allow, not new
  runtime capability.
- exact high-governance use may be preserved while its effective inheritance is
  capped to NO_INHERIT.

Open decisions: none that materially change this design.

Review disposition:

- Blockers: none found in Phase A review.
- Follow-ups: the separate Delivery work listed in section 11.
- Preferences: exact private helper names and test-file partitioning may change
  without changing the approved architecture or invariants.

## 14. PR boundary confirmation

The intended pull request changes one primary trust boundary: runtime authority
evaluation. Its complete slice is the immutable matrix, derived evaluator,
durable scope proof, migrated callers, check/effect ordering inside existing
transactions, decision trace, focused hostile tests, durable RFC, and
mechanical evidence.

Scope remains inside that boundary. If implementation requires principal
resolution, database role/schema/migration/transaction ownership, grant
mutation, bootstrap/key custody, complete sharing/output permission, new
actorship contracts, new actions, law, profile activation, deployment, or
another authority owner, implementation stops before editing that boundary and
the work is split.
