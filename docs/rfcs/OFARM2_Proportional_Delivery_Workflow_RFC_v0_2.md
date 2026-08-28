# OFARM2 Proportional Delivery Workflow — Phase A Contract v0.2

**Status:** Phase A draft; no implementation or merge authority; this workflow
is inactive until its adoption pull request merges

**Contract identity:** `ofarm2.proportional-delivery-workflow.v0.2`

**Decision identity:** `PROPORTIONAL-DELIVERY-WORKFLOW-001`, proposed version
`1`

**Primary trust boundary:** the task user's approval of one repository
development decision versus the AI's bounded authority to implement, review,
and merge one coherent delivery pull request

**Phase A boundary:** this RFC only

**Prospective adoption boundary:** this RFC, `AGENTS.md`, `TASK_PROMPT.md`,
`CONTRIBUTING.md`, and `.github/PULL_REQUEST_TEMPLATE.md`

## 1. Problem and goal

OFARM2's one-primary-trust-boundary rule was introduced to stop scope creep and
unbounded review. That rule is sound. Practice has nevertheless treated an
individual contract, approval record, file allowlist, fixture bridge, test
inventory update, or evidence transition as if each were a separate delivery
boundary.

The result is locally safe but globally slow. Large programme issues remain
open while tens of serial pull requests each repeat design, approval, review,
and hosted-baseline ceremony. Exact path lists also make ordinary discovery of
a necessary test or fixture look like authority expansion.

This decision establishes a proportional workflow:

- one delivery issue describes one coherent capability in one primary trust
  boundary and closes through exactly one repository-changing pull request;
- a programme containing several boundaries is a tracking epic with delivery
  child issues;
- implementation, migrations, tests, fixtures, documentation, generated
  inventories, and mechanical evidence needed for one capability travel in the
  same pull request;
- human approval binds semantic effects, authority, invariants, and one named
  pull request rather than an exact list of files; and
- Phase A depth follows the actual risk instead of forcing every change through
  the same fixed document structure; and
- expensive hosted baselines run on the implemented, reviewed head rather than
  on a design-only head.

The goal is shorter end-to-end delivery time without combining independent
authority or custody changes.

## 2. Evidence and learning value

Governance issue #218 validated the original manual protocol on three
substantive pull requests. It found that one-problem, one-boundary changes and
Blocker / Follow-up / Preference review substantially reduced churn. It also
said not to add strict enforcement or inventory machinery without evidence.

The later v0.1 pre-deployment workflow RFC recorded that issue-176-specific
exact-byte cards, publication-only pull requests, and private-task provenance
re-reviews had made development slow. The repository history since then shows
the same pattern recurring through contract-only, approval-only, fixture-only,
allowlist-amendment, and evidence-only pull requests.

This v0.2 decision tests whether semantic boundary control can preserve the
validated safety properties while removing artifact-level fragmentation. The
useful outcome is a delivery unit that reviewers can assess end to end.

## 3. Non-goals

This decision does not:

- weaken the one-primary-trust-boundary rule;
- combine authentication, principal resolution, tenant isolation, database
  authority, key custody, runtime integration, security-audit behavior, or
  artifact-publication custody when they are independently owned;
- change OFARM law, contracts, runtime behavior, deployment state, or any
  profile;
- change baseline-admission comment validation or secure evidence-publication
  implementation;
- waive required tests, exact-head review, conformance, or demonstrated
  Blockers;
- authorize production, deployment, release, current/default promotion,
  production data access, or a security waiver; or
- reinterpret completed approvals or alter the historical content of accepted
  RFCs.

## 4. Trust model

### Protected assets

- the task user's decision, refusal, and cancellation;
- separation of independent authority and custody boundaries;
- the declared invariants and non-effects of a delivery change;
- the integrity of exact-head review and required verification; and
- the existing artifact-publication custody chain.

### Trusted components

- the same Codex task surface for provisional user-message role and ordering;
- the non-malicious AI for following the approved semantic boundary;
- reviewers for technical findings; and
- existing CI and publication policy for mechanical evidence.

### Untrusted inputs

- GitHub activity as evidence of human intent;
- AI-authored approval text;
- caller-controlled runtime input;
- generated evidence before its existing validation; and
- a file path, branch name, issue label, or PR title as proof that a semantic
  boundary was preserved.

### Explicitly excluded compromise

A compromised task-user account, Codex platform, malicious AI process,
repository host, GitHub, CI platform, dependency chain, or operator remains
outside this provisional pre-deployment process threat model. This workflow is
procedural evidence, not production-grade signing.

### Primary risk and bound

The primary risk is that replacing exact file authority with a semantic
boundary could let a large PR hide an independent authority or custody change.
The containment rule is the authority-level boundary definition and adjacent
decision classifier in section 6: any independently changed allow/deny,
identity, credential/key, tenant, durability, activation/readiness/audit,
publication, deployment/currentness, or irreversible decision stops for its
own complete delivery issue and PR unless the task user explicitly approves the
existing cross-boundary exception.

## 5. Authority map

- The task user owns approval, refusal, cancellation, and any approved
  cross-boundary exception.
- The decision card owns the problem, primary trust boundary, permitted
  effects, non-effects, and decision-level invariants for one named pull
  request.
- The Phase A contract owns the technical architecture, detailed invariants,
  expected repository areas, and verification plan.
- The AI owns in-boundary implementation, mechanical companion changes, review
  handling, and merge only after every gate passes.
- Reviewers own Blocker findings; they do not own scope expansion.
- CI owns mechanical verification; it does not own human approval.
- The final base-to-head path list is scope evidence. It does not independently
  grant or remove authority.
- Existing runtime, database, tenant, key, audit, deployment, and publication
  authorities retain their current owners.

### Standing process authority

Root `AGENTS.md` is the single canonical authority for standing repository
development procedure. On any conflict, it controls.

- This RFC is the durable design and evidence for the v0.2 decision. It does
  not compete with `AGENTS.md` as an instruction surface.
- `TASK_PROMPT.md` is the working form agents use to apply the canonical rule.
- `CONTRIBUTING.md` is contributor guidance derived from the canonical rule.
- `.github/PULL_REQUEST_TEMPLATE.md` is the capture surface for a particular
  pull request.

Phase B must remove contradictions rather than layer another procedure beside
them. The following v0.1 guarantees remain: a unique live card; an exact later
same-task user approval bound to one already-created PR; non-transfer and
non-replay; easier cancellation; standing in-envelope implementation and merge
authority; exact-head Blocker/check gates; the pre-deployment limit; and the
independent human-controlled replacement duty before deployment.

The following v0.1 mechanics are prospectively superseded: exact paths as
approval authority; reapproval for an in-boundary file discovery; a fixed
section structure regardless of risk; a required committed approval appendix;
contract-, approval-, fixture-, inventory-, or evidence-only companion PRs;
expensive baselines on a Phase A-only head; and inheritance of standing process
ceremony from domain contracts.

## 6. Delivery units

### Primary trust boundary

A primary trust boundary is the place that decides or exercises authority or
custody: for example, one credential-verification authority, one database
privilege owner, one key custodian, or one runtime admission decision. It is
not an individual file, function, test, contract artifact, invariant, or
lifecycle step.

Changes owned by the same authority, governed by one threat model, and sharing
one atomic failure or rollback story belong in one delivery pull request when
they jointly deliver the capability. Independent owners, threat models, or
irreversible effects remain separate boundaries.

Adjacent code may travel only when it consumes an already accepted interface
and cannot independently change the adjacent area's allow/deny or identity
decision, credential or key access, tenant attribution or isolation, durable
write or transaction authority, runtime activation, readiness or audit
authority, evidence-publication custody, deployment or currentness, or an
irreversible effect. If it can change one of those decisions, it needs its own
delivery issue and complete pull request, or the task user's existing explicit
cross-boundary exception. A compatibility bridge may preserve an accepted
interface but may not broaden its accepted semantics.

### Tracking epic

A tracking epic describes a programme with more than one primary trust
boundary or more than one independently reviewable capability. It owns the
outcome map and dependency order. It does not pretend that all child work is
one delivery issue.

Before implementation begins, create or identify one delivery child issue for
each coherent capability. Existing broad issues such as #176 and #192 may stay
as historical trackers; new work under them uses delivery child issues.

### Delivery issue

A delivery issue states one user- or system-visible outcome, one primary
trust boundary, falsifiable acceptance criteria, and explicit non-goals. It
has exactly one repository-changing pull request. If any second pull request is
necessary, including a contract, approval, test, fixture, evidence, or
implementation pull request, the original issue is a tracking epic and each
complete outcome receives its own delivery child issue.

If inspection shows that an issue contains multiple independent boundaries,
reclassify it as a tracking epic and split child issues before implementation.
Do not hide the split behind many pull requests that all claim to advance one
undifferentiated issue.

### Delivery pull request

A delivery pull request contains the smallest complete vertical slice for its
capability. The following travel with it when they are necessary to implement
or prove the same boundary:

- design contract and approval evidence;
- production implementation and deletion of superseded paths;
- schema or migration changes owned by that boundary;
- unit, integration, hostile, and regression tests;
- test fixtures and historical compatibility bridges;
- documentation;
- generated inventories, digests, snapshots, and other mechanical evidence;
  and
- focused Blocker corrections.

Do not create a separate pull request merely to publish a contract, amend a
file allowlist, record approval, bridge a fixture, update a test inventory, or
regenerate mechanical evidence. Such a pull request is invalid when the
artifact has no independently usable and testable outcome beyond enabling
another planned pull request. A complete prerequisite in a distinct boundary
is valid when it has its own delivery issue, acceptance outcome, and complete
vertical slice, even when a later capability depends on it.

Small diff size is not an acceptance criterion. Coherence, reviewability, and
one-boundary containment are.

### Risk-shaped Phase A

Every Phase A states the capability, primary boundary, permitted effects,
non-effects, falsifiable invariants, non-goals, and verification. Add an
authority map whenever the change changes, relies on, or exercises authority.
Every high-risk Phase A also states the protected asset, trusted and untrusted
sides or inputs, excluded attacker capabilities, primary risk and containment
rule, and at least one production-reachable negative case per invariant. Add a
state machine and ordering model only for stateful or transactional work; a
custody model only for credentials, keys, or protected outputs; and migration,
rollback, or recovery analysis only when durability changes.

Put Phase A in the draft pull request description by default. Add a versioned
RFC or ADR in that same pull request only when the architectural decision must
remain useful after the pull request closes. A committed approval appendix is
not required: the same-task user message remains authority, while a compact PR
reference is navigation evidence only. Never create a separate contract or
approval-record pull request.

## 7. Approval envelope

The v0.1 same-task approval and cancellation model remains. One approval binds
one already-created draft pull request and cannot be transferred or replayed.

The user approves semantic authority, not an exact file inventory. A live card
must name:

- the decision identity and version;
- the problem and recommended decision;
- the primary trust boundary and authority map;
- the primary risk and its containment rule;
- permitted effects and non-effects;
- decision-level invariants;
- the named draft pull request;
- verification gates and reapproval triggers; and
- the provisional pre-deployment posture.

The Phase A contract names expected repository areas so reviewers can judge
scope. Discovering another implementation, test, fixture, documentation, or
generated-evidence file inside the same approved boundary does not require a
new decision. The final scope report explains the addition and proves that it
does not add authority, effects, or another boundary.

A new decision version and approval are required when the proposed work
changes the primary trust boundary, authority map, permitted effect,
non-effect, decision-level invariant, irreversible behavior, named pull
request, or production/deployment posture. A path change is a reapproval
trigger only when it is evidence of one of those semantic changes or makes the
determination genuinely ambiguous.

## 8. State and ordering

For a prospective high-risk delivery change after this workflow is active:

```text
DELIVERY_ISSUE_DEFINED
  -> DRAFT_PR_WITH_PHASE_A
  -> PHASE_A_DESIGN_REVIEWED
  -> USER_DECISION_CARD
  -> USER_APPROVED
  -> IMPLEMENT_COMPLETE_VERTICAL_SLICE
  -> CHEAP_LOCAL_CHECKS
  -> EXACT_HEAD_CONTENT_REVIEW_ZERO_BLOCKERS
  -> BASELINE_ADMISSION
  -> REQUIRED_HOSTED_BASELINES_AND_PUBLICATION
  -> FINAL_SCOPE_AND_APPROVAL_RECHECK
  -> MERGE_AND_CLOSE_DELIVERY_ISSUE
```

Phase A design review happens before approval. Expensive hosted baselines do
not run merely to validate a design-only head. After implementation, freeze the
candidate head, obtain the exact-head zero-Blocker review, and then admit the
expensive baselines once.

If a Blocker requires a new commit, obtain a focused exact-head review of the
fix and affected invariants, then admit baselines for the new head. Do not
restart open-ended design review. Follow-ups and Preferences do not expand or
delay the pull request.

The current v0.1 workflow governs this v0.2 adoption. Therefore the adoption
pull request itself follows the old bootstrap order, including any design-head
baseline required before its approval card. The new sequence becomes active
only after adoption merges.

Outcome evaluation uses end-to-end measures: delivery-issue open-to-close
time, pull requests and approval stops per delivered capability, process-only
pull requests, and final-head baseline cycles. The target is one delivery pull
request, one approval stop for high-risk work, zero process-only companion pull
requests, and one successful implemented-head baseline cycle. Per-PR time from
zero Blockers to merge remains useful operational data but cannot by itself
show that a programme is moving.

## 9. Stable invariants

- **PDW2-001 — One complete capability.** A delivery pull request implements
  and proves one coherent capability rather than publishing one intermediate
  artifact.
- **PDW2-002 — One primary boundary.** Independent authority or custody
  changes remain in separate delivery issues and pull requests unless the task
  user approves the repository's existing cross-boundary exception procedure.
  Adjacent changes may travel only when they consume an accepted interface and
  cannot independently alter an authority, custody, activation, durability, or
  irreversible decision.
- **PDW2-003 — Mechanical companions travel together.** Required tests,
  fixtures, migrations, documentation, inventories, and evidence stay with the
  capability and do not become standalone process pull requests.
- **PDW2-004 — Epic and delivery work are distinct.** A multi-boundary
  programme is tracked as an epic with delivery child issues; one delivery
  issue has exactly one repository-changing pull request.
- **PDW2-005 — Semantic approval.** Human approval binds effects, authority,
  invariants, and one named pull request, not exact bytes or an exhaustive file
  list.
- **PDW2-006 — Material expansion stops.** A new boundary, authority owner,
  effect, invariant change, irreversible behavior, PR transfer, or ambiguous
  expansion requires a new decision.
- **PDW2-007 — One implemented-head baseline cycle.** Expensive baselines are
  admitted only after implementation and exact-head zero-Blocker review,
  except for the one-time v0.1-governed adoption of this workflow.
- **PDW2-008 — Review remains fail-closed.** Demonstrated Blockers delay merge;
  failed required checks remain failures; later commits require affected
  exact-head review and verification.
- **PDW2-009 — Approval and cancellation remain human-owned.** GitHub activity,
  AI text, CI, and repository credentials do not substitute for the same-task
  user decision, and a later stop-like message pauses work.
- **PDW2-010 — Publication custody is unchanged.** Existing baseline admission,
  provisional artifact handling, trusted publication, and receipt validation
  retain their current technical controls.
- **PDW2-011 — Historical semantics remain.** Completed approvals and accepted
  technical or domain invariants are not rewritten.
- **PDW2-012 — Process rules do not become permanent by inheritance.** For new,
  unapproved work, this v0.2 workflow prospectively supersedes older
  repository-development mechanics such as exact-file approval, separate
  approval publication, and contract-only PR requirements. Repository workflow
  policy is the only source of standing process gates. A delivery decision may
  request a user-approved exception for its one PR, but the exception expires
  at that PR's merge and cannot require companion PRs. A durable stronger gate
  requires its own complete workflow-governance delivery issue and PR, a
  demonstrated current failure or threat, a named consumer, an expiry or review
  point, and evidence that it removes more process decisions than it adds.
- **PDW2-013 — Ceremony follows risk without dropping the trust floor.** Every
  high-risk change records protected assets, trust and input sides, the primary
  risk and bound, applicable authority, and production-reachable negatives.
  State, custody, durability, and durable architecture sections are required
  only when that risk is actually present. Phase A and any durable design
  record stay in the delivery pull request.

## 10. Required negative cases

The workflow must stop or reject the proposed course when:

- **NC-001 — Cross-boundary bundle:** one delivery PR changes both tenant
  authorization and key custody merely
  because both belong to the same tracking epic;
- **NC-002 — Path paperwork:** an agent opens an allowlist-amendment PR only
  because implementation revealed
  a necessary test file;
- **NC-003 — Artifact relabeling:** an agent labels a contract, approval
  record, fixture bridge, or evidence
  receipt as its own system-visible capability when it has no independently
  usable and testable outcome beyond enabling another planned pull request;
- **NC-004 — Companion split:** a migration, its owned fixtures, and its
  compatibility tests are split even
  though they prove the same database boundary;
- **NC-005 — Second delivery PR:** a delivery issue receives any second
  repository-changing PR before the work
  is reclassified as an epic with separate complete delivery child outcomes;
- **NC-006 — Hidden semantic expansion:** a new path changes authority or
  effects while being described as mechanical;
- **NC-007 — Review bypass:** exact-head review reports a Blocker and an
  admission comment or merge is
  attempted anyway;
- **NC-008 — Premature baseline:** a design-only head is sent through expensive
  baselines under the new workflow
  before user approval and implementation;
- **NC-009 — Ceremony inheritance:** an older contract's process ceremony is
  inherited without identifying a
  concrete threat that still requires it; or
- **NC-010 — Domain process ratchet:** a domain contract creates a standing
  process gate instead of using a one-PR exception or proposing a
  workflow-governance delivery issue;
- **NC-011 — Custody weakening:** this workflow is used to weaken artifact
  publication, runtime authority,
  production controls, or deployment approval.
- **NC-012 — Approval substitution or ignored cancellation:** an agent treats
  GitHub activity or AI-authored text as user approval, or continues after a
  later same-task stop-like user message.
- **NC-013 — Historical rewrite:** a new workflow decision claims to replace a
  completed approval or discards an accepted technical or domain invariant
  merely because its old process ceremony was superseded.
- **NC-014 — Missing high-risk trust floor:** a high-risk Phase A proceeds
  without protected assets, trusted and untrusted sides or inputs, the primary
  risk and bound, applicable authority, or a production-reachable negative for
  each invariant.

## 11. Proposed architecture and smallest coherent change

The workflow remains documentation-governed. No new service, bot, database,
signer, workflow trigger, or policy engine is introduced.

Phase B will:

1. update `AGENTS.md` to define tracking epics, delivery issues, complete
   delivery pull requests, semantic approval, and the corrected order of Phase
   A, approval, implementation, review, baseline, and merge;
2. update `TASK_PROMPT.md` so task contracts plan a complete vertical slice,
   use the risk-shaped Phase A contract, list expected areas rather than an
   exact authority-bearing allowlist, and distinguish semantic expansion from
   ordinary file discovery;
3. update `CONTRIBUTING.md` to replace the completed three-PR pilot text with
   the adopted delivery model and outcome-oriented review guidance;
4. update the pull request template to record delivery issue versus tracking
   epic, completeness of companion changes, and any justified split; and
5. mark this RFC approved and append compact approval evidence in the same
   pull request.

This is the smallest coherent change because the fragmentation is created by
human/agent instructions and templates. Existing CI already supports the
desired final-head admission order. Changing artifact-publication code would
cross into a separate custody boundary and is unnecessary.

## 12. Elegance audit

There is one source of truth for standing process: root `AGENTS.md`. The RFC,
task prompt, contributor guide, and PR template have four distinct supporting
roles and may not define competing rules.

There are four authoritative transition owners, each with one decision:

1. the task user approves or cancels the semantic delivery decision;
2. reviewers declare demonstrated Blockers or an exact-head zero-Blocker
   disposition;
3. the existing admission and CI system validates and runs required baselines;
   and
4. the merge actor confirms current approval, scope, checks, and zero Blockers.

Current duplication comes from the same process being restated differently in
`AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md`, the PR template, v0.1, and
many domain RFCs. Phase B deletes contradictory current instructions and stale
pilot fields from the four active policy surfaces. It does not edit historical
RFCs or add a compatibility shim. Prospective precedence in root `AGENTS.md`
makes their process-only clauses inert for new work while preserving their
technical and domain decisions.

A clean rewrite of the affected active sections is safer and shorter than
appending another exception layer. Unaffected privacy, law, claim, review,
baseline-admission, artifact-publication, profile, and runtime rules remain
byte-for-byte or semantically unchanged as appropriate.

No new abstraction, registry, attestation store, automation, or duplicate
validator is introduced.

## 13. Pull request boundary

Phase A changes only this RFC.

After approval, Phase B may change only:

- `docs/rfcs/OFARM2_Proportional_Delivery_Workflow_RFC_v0_2.md`;
- `AGENTS.md`;
- `TASK_PROMPT.md`;
- `CONTRIBUTING.md`; and
- `.github/PULL_REQUEST_TEMPLATE.md`.

The one already-created draft adoption pull request is
`https://github.com/samovers/OFARM2/pull/348`. Approval cannot be transferred to
or consumed by another pull request.

No workflow YAML, conformance executor, admission checker, evidence publisher,
runtime code, migration, schema, test inventory, or historical RFC may change.
If review demonstrates that executable enforcement must change, stop and
propose a separate governance-enforcement boundary.

## 14. Prospective precedence and migration

After adoption merges, v0.2 is the default repository-development procedure
for new decisions, including new delivery work under open tracking epics #176
and #192.

Completed pull requests, approval evidence, and technical decisions remain
historical facts. Their domain invariants, database rules, runtime boundaries,
and security requirements remain binding where applicable.

For work that has not yet received user approval, older clauses requiring
exact-file approval, contract-only publication, approval-only publication,
fixture-only prerequisites, or process evidence as separate PRs are superseded
by v0.2. A domain decision may request a stronger one-PR exception in its user
decision card, but it cannot create a standing rule or require companion PRs.
A standing stronger procedure must amend the repository workflow through its
own complete workflow-governance delivery issue and pull request. Merely citing
an older workflow or copying its ceremony is insufficient.

Already-approved but unmerged work remains governed by its approval. It may
finish under that approval or stop and seek a new v0.2 decision; authority is
never silently rewritten.

## 15. Provisional design record

This workflow is acceptable before deployment because it preserves one-boundary
scope, same-task human approval, exact-head review, required checks, and the
existing publication chain while changing only how work is packaged.

Evidence requiring redesign includes a delivery PR silently crossing an
authority boundary, repeated review inability to assess complete vertical
slices, process-only PRs continuing after adoption, or hosted baselines running
repeatedly because candidate heads are not frozen before review.

Before deployment, the provisional Codex-message approval model still requires
replacement by an independently human-controlled and independently verifiable
approval or signing system. This v0.2 decision does not change that duty.

## 16. Traceability and verification

| Invariant | Owning policy | Negative case | Concrete Phase B acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| PDW2-001 | `AGENTS.md`, `CONTRIBUTING.md` | NC-003, NC-004 | complete-capability rule includes code and every companion artifact | wording audit against the delivery definition |
| PDW2-002 | `AGENTS.md`, `TASK_PROMPT.md` | NC-001, NC-006 | authority-level boundary definition and adjacent-decision classifier | inspect boundary examples and cross-boundary stop |
| PDW2-003 | `AGENTS.md`, `CONTRIBUTING.md`, PR template | NC-002–004 | explicit same-PR list and companion-artifact prohibition | search active policy for each named companion type |
| PDW2-004 | `AGENTS.md`, `CONTRIBUTING.md`, PR template | NC-005 | Epic/Delivery taxonomy and exactly-one-PR field | inspect issue classification and PR completeness fields |
| PDW2-005 | `AGENTS.md`, `TASK_PROMPT.md` | NC-002, NC-006 | card binds semantic fields and names one PR; paths are evidence | inspect card fields and remove exact-path authority wording |
| PDW2-006 | `AGENTS.md`, `TASK_PROMPT.md` | NC-001, NC-006 | reapproval triggers list semantic expansion only | compare trigger list with the approved invariant |
| PDW2-007 | `AGENTS.md`, `TASK_PROMPT.md` | NC-008 | sequence places approval before implementation and one baseline after final review | line-order audit against the state machine |
| PDW2-008 | `AGENTS.md`, `TASK_PROMPT.md` | NC-007 | final exact-head zero-Blocker disposition and focused fix review remain | review-rule audit and unchanged admission mechanics |
| PDW2-009 | `AGENTS.md`, `TASK_PROMPT.md` | NC-012 | retained same-task approval, non-transfer, and cancellation rules | approval-state and cancellation wording audit |
| PDW2-010 | unchanged workflow/publication implementation | NC-011 | every custody file is byte-identical to base | base-to-head path audit and blob comparison |
| PDW2-011 | `AGENTS.md`, this RFC | NC-013 | prospective-only clause preserves completed and technical decisions | historical/prospective boundary review |
| PDW2-012 | `AGENTS.md`, this RFC | NC-009, NC-010 | canonical-authority and one-PR exception rules replace stronger-process inheritance | conflict/precedence wording audit |
| PDW2-013 | `AGENTS.md`, `TASK_PROMPT.md`, PR template | NC-014 | mandatory high-risk trust floor plus conditional risk sections in the same PR | conditional-section and trust-floor audit |

Required checks for adoption:

- exact base-to-head path audit;
- focused text audit for contradictory exact-file authority and stale pilot
  instructions in the four adopted policy surfaces;
- `git diff --check`;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- exact-head content review with zero Blockers; and
- the current v0.1-governed hosted baselines and publication sequence.

## 17. Open decisions and review disposition

Open decisions: none. This design intentionally leaves executable baseline
admission and artifact publication unchanged.

Current review disposition:

- Blockers: none known; exact-head Phase A review is still required;
- Follow-ups: independently verifiable human approval before deployment; and
- Preferences: none.

## 18. Stop conditions

This Phase A stops before:

- changing any existing policy file;
- presenting an approval card;
- treating v0.2 as active;
- changing workflow or publication custody;
- changing runtime, database, tenant, key, audit, or deployment behavior; or
- implementing anything beyond this contract draft.

The next lawful actions are to create the draft adoption pull request, bind its
stable reference into section 13, complete exact-head Phase A review and the
currently required hosted gates, then present one plain-English decision card.
