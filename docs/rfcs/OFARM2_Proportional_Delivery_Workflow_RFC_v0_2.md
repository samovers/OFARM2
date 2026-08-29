# OFARM2 Proportional Delivery Workflow — Phase A Contract v0.2

**Status:** approved for Phase B under decision version 2; authority is limited
to draft PR #348 and the five-path adoption boundary, subject to every final
gate; decision version 1 was withdrawn without approval and grants no
authority; this workflow remains inactive until PR #348 merges

**Contract identity:** `ofarm2.proportional-delivery-workflow.v0.2`

**Decision identity:** `PROPORTIONAL-DELIVERY-WORKFLOW-001`, approved version
`2`

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
  boundary, has one live implementation pull request at a time, and closes
  through at most one merged implementation pull request;
- a programme containing several boundaries or independently reviewable
  capabilities is a tracking epic with delivery child issues;
- implementation, migrations, tests, fixtures, documentation, generated
  inventories, and mechanical evidence needed for one capability travel in the
  same pull request;
- human approval binds semantic effects, authority, invariants, and one named
  pull request rather than an exact list of files;
- Phase A depth follows the actual risk instead of forcing every change through
  the same fixed document structure;
- expensive hosted baselines run on the implemented, reviewed head rather than
  on a design-only head; and
- root `AGENTS.md` becomes canonical only for standing repository-development
  procedure, with a closed, prospective amendment of named packaging and
  sequencing mechanics rather than a transfer of OFARM, technical, security,
  authority, custody, evidence, currentness, runtime, deployment, or domain
  authority.

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

The repository's pinned, package-non-normative CP15 reference view reinforces
that generated prompt or policy artifacts remain candidates; high-consequence
CP15 deployment and currentness actions are human-governed or human-approval-
required by default; and agent/tool, build, test, or conformance success does
not by itself create deployment, runtime, or current/default-promotion
authority or production readiness. That supports explicit human disclosure and
non-bypass of substantive OFARM requirements. CP15 does not itself establish a
universal precedence rule between repository documents; the limited process
precedence in this decision therefore requires its own explicit task-user
approval and cannot be inferred from successful tooling or review evidence.
The relevant pinned sections are CP15-C.1, CP15-C.5, and section 7.10e.

## 3. Non-goals

This decision does not:

- weaken the one-primary-trust-boundary rule;
- combine authentication, principal resolution, tenant isolation, database
  authority, key custody, runtime integration, security-audit behavior, or
  artifact-publication custody when they are independently owned;
- change OFARM law, runtime behavior, deployment state, any profile, or the
  substantive meaning of an accepted contract;
- supersede accepted technical, security, authority, custody,
  evidence-sufficiency, currentness, runtime, deployment, or domain invariants;
- change executable baseline-admission validation, workflow custody, secure
  evidence-publication implementation, or receipt validation; repository
  policy for when baseline admission is requested does change;
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
- the continued authority of OFARM law and accepted technical, security,
  authority, custody, evidence-sufficiency, currentness, runtime, deployment,
  and domain invariants;
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
- generated evidence before its existing validation;
- a file path, branch name, issue label, or PR title as proof that a semantic
  boundary was preserved; and
- an agent's unsupported classification of an older requirement as mere
  process ceremony.

### Explicitly excluded compromise

A compromised task-user account, Codex platform, malicious AI process,
repository host, GitHub, CI platform, dependency chain, or operator remains
outside this provisional pre-deployment process threat model. This workflow is
procedural evidence, not production-grade signing.

### Primary risk and bound

The primary risk is that consolidating delivery and standing process authority
could be misread as permission either to hide an independent capability or
authority/custody change in a large pull request, or to discard a stronger
substantive requirement as ceremony. The containment rule has two closed
parts. First, one delivery pull request may contain only one independently
reviewable capability in one authority-level trust boundary. Any independently
changed allow/deny, identity, credential/key, tenant, durability,
activation/readiness/audit, publication, deployment/currentness, or
irreversible decision stops for its own complete delivery issue and pull
request; this workflow never permits combining independent boundaries. Any
future mechanism to combine them would require a separate workflow-governance
decision and receives no authority from this RFC. Second, root `AGENTS.md`
controls only the expressly enumerated repository-development packaging and
sequencing mechanics amended by this decision. It cannot
supersede OFARM law or accepted technical, security, authority, custody,
evidence-sufficiency, currentness, runtime, deployment, or domain invariants.
Where classification is ambiguous, the older requirement remains binding until
it is explicitly amended.

## 5. Authority map

- The task user owns approval, refusal, cancellation, and explicit supersession
  of an abandoned pull request through a new decision version.
- The decision card owns the problem, one independently reviewable capability,
  primary trust boundary, permitted effects, non-effects, and decision-level
  invariants for one named pull request.
- The Phase A contract owns the technical architecture, detailed invariants,
  expected repository areas, and verification plan.
- The AI owns in-boundary implementation, mechanical companion changes, review
  handling, and merge only after every gate passes.
- Reviewers own Blocker findings; they do not own scope expansion.
- CI owns mechanical verification; it does not own human approval.
- The final base-to-head path list is scope evidence. It does not independently
  grant or remove authority.
- Root `AGENTS.md` owns standing repository-development procedure only within
  the limited prospective precedence rule below.
- OFARM law and accepted technical, security, authority, custody,
  evidence-sufficiency, currentness, runtime, deployment, and domain invariants
  retain their existing authority and cannot be downgraded by process policy.
- Existing runtime, database, tenant, key, audit, deployment, and publication
  authorities retain their current owners.

### Standing process authority

After adoption, root `AGENTS.md` is the canonical authority for standing
repository-development procedure only. It controls an older process clause
only when the clause is unambiguously one of the packaging or sequencing
mechanics expressly enumerated below. It cannot supersede OFARM law or an
accepted technical, security, authority, custody, evidence-sufficiency,
currentness, runtime, deployment, or domain invariant. When classification is
ambiguous, the older requirement remains binding until an explicit versioned
amendment resolves it.

- This RFC is the durable design and evidence for the v0.2 decision. It does
  not compete with `AGENTS.md` as an instruction surface.
- `TASK_PROMPT.md` is the working form agents use to apply the canonical rule.
- `CONTRIBUTING.md` is contributor guidance derived from the canonical rule.
- `.github/PULL_REQUEST_TEMPLATE.md` is the capture surface for a particular
  pull request.

This RFC is the versioned workflow-governance amendment to the v0.1
pre-deployment development workflow for the closed list of mechanics below.
Phase B must remove contradictions rather than layer another procedure beside
them. The following v0.1 guarantees remain: a unique live card; an exact later
same-task user approval bound to one already-created PR; non-transfer and
non-replay; easier cancellation; standing in-envelope implementation and merge
authority; exact-head Blocker/check gates; the pre-deployment limit; stronger
substantive requirements for their exact actions; and the independent
human-controlled replacement duty before deployment.

Only the following v0.1 repository-development mechanics are prospectively
superseded for new, unapproved work: exact repository paths as human approval
authority; reapproval for an unambiguously in-boundary file discovery; a fixed
Phase A section structure regardless of risk; a required committed approval
appendix; contract-, approval-, fixture-, inventory-, or evidence-only
companion pull requests when the artifact has no independently usable and
testable outcome beyond enabling another planned pull request; and expensive
baselines on a Phase A-only head. This closed list does not turn a contract-
specific evidence, review, approval, security, authority, custody, currentness,
runtime, deployment, or domain requirement into disposable ceremony.

## 6. Delivery units

### Primary trust boundary

A primary trust boundary is the place that decides or exercises authority or
custody: for example, one credential-verification authority, one database
privilege owner, one key custodian, or one runtime admission decision. It is
not an individual file, function, test, contract artifact, invariant, or
lifecycle step.

Changes owned by the same authority, governed by one threat model, sharing one
atomic failure or rollback story, and jointly delivering one independently
reviewable capability belong in one delivery pull request. Independent
capabilities, owners, threat models, or irreversible effects remain separate
delivery work.

Adjacent code may travel only when it consumes an already accepted interface
and cannot independently change the adjacent area's allow/deny or identity
decision, credential or key access, tenant attribution or isolation, durable
write or transaction authority, runtime activation, readiness or audit
authority, evidence-publication custody, deployment or currentness, or an
irreversible effect. If it can change one of those decisions, it needs its own
delivery issue and complete pull request. Cross-boundary bundling has no waiver
under this workflow. A compatibility bridge may preserve an accepted interface
but may not broaden its accepted semantics.

### Tracking epic

A tracking epic describes a programme with more than one primary trust
boundary or more than one independently reviewable capability. It owns the
outcome map and dependency order. It does not pretend that all child work is
one delivery issue.

Before implementation begins, create or identify one delivery child issue for
each coherent capability. Existing broad issues such as #176 and #192 may stay
as historical trackers; new work under them uses delivery child issues.

### Delivery issue

A delivery issue states one user- or system-visible outcome, one primary trust
boundary, one independently reviewable capability, falsifiable acceptance
criteria, and explicit non-goals. It has one live implementation pull request
at a time and at most one merged implementation pull request. If concurrent
live implementation pull requests or more than one merged pull request would
be needed for a contract, approval, test, fixture, evidence, implementation, or
other separately deliverable outcome, the original issue is a tracking epic
and each complete outcome receives its own delivery child issue.

If inspection shows that an issue contains multiple independent boundaries or
independently reviewable capabilities, reclassify it as a tracking epic and
split child issues before implementation. Do not hide the split behind many
pull requests that all claim to advance one undifferentiated issue.

Only an unmerged implementation pull request is eligible for recovery. An
open-but-operationally-unusable pull request must first close unmerged. A merged
pull request is never eligible; later correction is new Delivery work.

A closed-unmerged pull request may be replaced without falsely reclassifying
one capability as an epic. The old pull request must close before the
replacement opens, and the old and replacement pull requests must carry
explicit reciprocal supersession links. The replacement requires a new
decision version and task-user approval naming it, followed by fresh review,
checks, baselines, and publication.

A closed-unmerged pull request may instead be reopened. Reopening the same pull
request creates no authority. A later task-user-approved new decision version,
if any, supersedes the expired card rather than superseding the pull request
itself. Reopening therefore requires that new decision version and approval,
plus fresh review, checks, baselines, and publication. Neither recovery path can
revive or inherit approval, review, admission, check, baseline, or publication
evidence.

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
one-capability and one-boundary containment are.

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
approval-record pull request merely to enable another planned pull request when
the artifact has no independently usable and testable outcome. A complete
independently usable prerequisite retains its own Delivery issue and pull
request.

## 7. Approval envelope

The v0.1 same-task approval and cancellation model remains. One approval binds
one already-created draft pull request and cannot be transferred or replayed.

The user approves semantic authority, not an exact file inventory. A live card
must name:

- the decision identity and version;
- the problem, one independently reviewable capability, and recommended
  decision;
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
does not add authority, effects, another independently reviewable capability,
or another boundary.

A new decision version and approval are required when the proposed work
changes the primary trust boundary, authority map, permitted effect,
non-effect, independently reviewable capability, decision-level invariant,
irreversible behavior, named pull request, or production/deployment posture. A
path change is a reapproval trigger only when it is evidence of one of those
semantic changes or makes the determination genuinely ambiguous.

Closing the named pull request unmerged expires its authority. Replacing or
reopening it requires the abandoned-pull-request recovery rule in section 6;
the replacement or reopened pull request starts again at
`DRAFT_PR_WITH_PHASE_A` with a new decision version and no inherited approval,
review, admission, check, baseline, or publication evidence.

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

If the named pull request is abandoned, replacement follows:

```text
NAMED_PR_OPEN_BUT_UNUSABLE
  -> NAMED_PR_CLOSED_UNMERGED
  -> NEW_DRAFT_PR_WITH_PHASE_A
  -> OLD_AND_NEW_PR_RECIPROCAL_SUPERSESSION_LINKS
  -> PHASE_A_DESIGN_REVIEWED
  -> USER_DECISION_CARD_NEW_VERSION
  -> USER_APPROVED
  -> NORMAL_IMPLEMENTATION_REVIEW_CHECKS_BASELINES_AND_PUBLICATION
```

If it was already closed unmerged, replacement starts at
`NAMED_PR_CLOSED_UNMERGED`. Reopening follows:

```text
NAMED_PR_CLOSED_UNMERGED_AND_AUTHORITY_EXPIRED
  -> REOPENED_DRAFT_PR_WITH_PHASE_A
  -> PHASE_A_DESIGN_REVIEWED
  -> USER_DECISION_CARD_NEW_VERSION
  -> USER_APPROVED
  -> NORMAL_IMPLEMENTATION_REVIEW_CHECKS_BASELINES_AND_PUBLICATION
```

Replacement or reopening is recovery for the same capability, not evidence of
another capability. A merged pull request cannot enter either recovery path,
and no authority or evidence crosses it.

The current v0.1 workflow governs this v0.2 adoption. Therefore the adoption
pull request itself follows the old bootstrap order, including any design-head
baseline required before its approval card. The new sequence becomes active
only after adoption merges.

Outcome evaluation uses end-to-end measures: delivery-issue open-to-close
time, live and abandoned pull requests and approval stops per delivered
capability, process-only pull requests, and final-head baseline cycles. The
normal target is one live and one merged delivery pull request, one approval
stop for high-risk work, zero process-only companion pull requests, and one
successful implemented-head baseline cycle. An abandoned replacement is an
explicitly recorded recovery event, not a second delivered capability. Per-PR
time from zero Blockers to merge remains useful operational data but cannot by
itself show that a programme is moving.

## 9. Stable invariants

- **PDW2-001 — One complete capability.** A delivery pull request implements
  and proves one coherent capability rather than publishing one intermediate
  artifact.
- **PDW2-002 — One primary boundary without waiver.** Independent authority
  or custody changes remain in separate delivery issues and pull requests.
  This workflow never permits combining independent boundaries. Adjacent
  changes may travel only when they consume an accepted interface and cannot
  independently alter an authority, custody, activation, durability, or
  irreversible decision.
- **PDW2-003 — Mechanical companions travel together.** Required tests,
  fixtures, migrations, documentation, inventories, and evidence stay with the
  capability and do not become standalone process pull requests.
- **PDW2-004 — Epic and delivery work are distinct.** A multi-boundary or
  multi-capability programme is tracked as an epic with delivery child issues;
  one delivery issue has one live implementation pull request at a time and at
  most one merged implementation pull request.
- **PDW2-005 — Semantic approval.** Human approval binds effects, authority,
  invariants, and one named pull request, not exact bytes or an exhaustive file
  list.
- **PDW2-006 — Material expansion stops.** A new independently reviewable
  capability, boundary, authority owner, effect, invariant change, irreversible
  behavior, named-PR change, or ambiguous expansion requires a new decision.
- **PDW2-007 — One implemented-head baseline cycle.** Expensive baselines are
  admitted only after implementation and exact-head zero-Blocker review,
  except for the one-time v0.1-governed adoption of this workflow.
- **PDW2-008 — Review remains fail-closed.** Demonstrated Blockers delay merge;
  failed required checks remain failures; later commits require affected
  exact-head review and verification.
- **PDW2-009 — Approval and cancellation remain human-owned.** GitHub activity,
  AI text, CI, and repository credentials do not substitute for the same-task
  user decision, and a later stop-like message pauses work.
- **PDW2-010 — Admission and publication implementation are unchanged.**
  Existing admission validation, workflow custody, provisional artifact
  handling, trusted publication, and receipt validation retain their current
  executable controls. Only repository policy for when admission is requested
  changes under PDW2-007.
- **PDW2-011 — Historical semantics remain.** Completed approvals and accepted
  technical or domain invariants are not rewritten.
- **PDW2-012 — Process precedence is closed and limited.** Root `AGENTS.md` is
  canonical only for repository-development procedure. For new, unapproved
  work, this versioned amendment prospectively supersedes only the expressly
  enumerated packaging and sequencing mechanics. It cannot supersede OFARM law
  or accepted technical, security, authority, custody, evidence-sufficiency,
  currentness, runtime, deployment, or domain invariants. A stronger accepted
  procedure expressly governing an exact action remains controlling unless an
  explicit versioned amendment changes it. Where classification is ambiguous,
  the older requirement remains binding until explicitly amended. A new
  durable repository-wide process gate requires its own complete workflow-
  governance delivery issue and pull request, a demonstrated current failure
  or threat, a named consumer, and an expiry or review point.
- **PDW2-013 — Ceremony follows risk without dropping the trust floor.** Every
  high-risk change records protected assets, trust and input sides, the primary
  risk and bound, applicable authority, and production-reachable negatives.
  State, custody, durability, and durable architecture sections are required
  only when that risk is actually present. Phase A and any durable design
  record stay in the delivery pull request.
- **PDW2-014 — Abandoned pull requests fail closed.** A delivery issue may
  replace or reopen an unmerged implementation pull request without becoming
  an epic. An unusable open pull request must first close unmerged. Replacement
  requires reciprocal PR supersession links; reopening itself creates no
  authority, and only a later approved new decision version supersedes the
  expired card. Both paths require that new decision version and task-user
  approval and inherit no approval, review, admission, check, baseline, or
  publication evidence. A merged pull request is never eligible.

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
- **NC-005 — Concurrent or second delivered PR:** a delivery issue has two live
  implementation pull requests or attempts to merge an implementation pull
  request after another implementation pull request for that issue has already
  merged;
- **NC-006 — Hidden semantic expansion:** a new path changes authority or
  effects while being described as mechanical;
- **NC-007 — Review bypass:** exact-head review reports a Blocker and an
  admission comment or merge is
  attempted anyway;
- **NC-008 — Premature baseline:** a design-only head is sent through expensive
  baselines under the new workflow
  before user approval and implementation;
- **NC-009 — Precedence misclassification:** an agent either preserves one of
  the closed-list superseded mechanics merely because an older document states
  it, or discards a stronger substantive requirement as ceremony; uncertainty
  must keep the older requirement binding until explicit amendment;
- **NC-010 — Domain process ratchet:** a new domain contract creates a general
  repository packaging or sequencing gate instead of proposing a workflow-
  governance delivery issue; exact-action substantive evidence, review,
  approval, security, authority, custody, currentness, runtime, deployment, and
  domain requirements remain valid;
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
- **NC-015 — Same-authority capability bundle:** several independently
  reviewable capabilities are placed in one pull request merely because they
  share an authority owner.
- **NC-016 — Unsafe abandoned-PR replacement:** a replacement pull request is
  opened before the old one closes unmerged, lacks reciprocal supersession
  links, treats a merged pull request as recoverable, or a replacement or
  reopened pull request keeps the old decision version or reuses approval,
  review, admission, check, baseline, or publication evidence.

## 11. Proposed architecture and smallest coherent change

The workflow remains documentation-governed. No new service, bot, database,
signer, workflow trigger, or policy engine is introduced.

The approved Phase B implementation:

1. updates `AGENTS.md` to define tracking epics, delivery issues, complete
   delivery pull requests, semantic approval, abandoned-pull-request recovery,
   the limited prospective precedence rule, and the corrected order of Phase
   A, approval, implementation, review, baseline, and merge;
2. updates `TASK_PROMPT.md` so task contracts plan a complete vertical slice,
   use the risk-shaped Phase A contract, list expected areas rather than an
   exact authority-bearing allowlist, and distinguish semantic expansion from
   ordinary file discovery;
3. updates `CONTRIBUTING.md` to replace the completed three-PR pilot text with
   the adopted delivery model and outcome-oriented review guidance;
4. updates the pull request template to record delivery issue versus tracking
   epic, one-capability and one-boundary containment, completeness of companion
   changes, and any abandoned-pull-request supersession; and
5. marks this RFC approved for decision version 2 and appends compact approval
   evidence in the same pull request.

This is the smallest coherent change because the fragmentation is created by
human/agent instructions and templates. Existing CI already supports the
desired final-head admission order. Changing artifact-publication code would
cross into a separate custody boundary and is unnecessary.

## 12. Elegance audit

There is one source of truth for standing repository-development procedure:
root `AGENTS.md`. It is not a source of OFARM law and cannot downgrade accepted
technical, security, authority, custody, evidence-sufficiency, currentness,
runtime, deployment, or domain invariants. The RFC, task prompt, contributor
guide, and PR template have four distinct supporting roles and may not define
competing repository-development rules.

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
RFCs or add a compatibility shim. The limited prospective precedence rule
supersedes only the closed list of packaging and sequencing mechanics for new,
unapproved work. It preserves stronger accepted exact-action procedures and
all substantive requirements; uncertainty leaves the older requirement
binding until explicit amendment.

A clean rewrite of the affected active sections is safer and shorter than
appending another exception layer. Unaffected privacy, law, claim, review,
exact-head Blocker gates, executable admission and artifact-publication
controls, profile rules, and runtime rules remain byte-for-byte or semantically
unchanged as appropriate. Repository policy for when admission is requested
changes as stated in sections 3, 8, and 9.

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
and #192. It is a versioned amendment to the v0.1 repository-development
workflow only for the closed list of mechanics in section 5.

Completed pull requests, approval evidence, and technical decisions remain
historical facts. Root `AGENTS.md` is canonical only for repository-development
procedure. It cannot supersede OFARM law or accepted technical, security,
authority, custody, evidence-sufficiency, currentness, runtime, deployment, or
domain invariants.

For work that has not yet received user approval, older clauses are superseded
only when they unambiguously require one of these named mechanics: exact paths
as human approval authority; reapproval for an in-boundary file discovery; a
fixed Phase A structure regardless of risk; a committed approval appendix;
contract-, approval-, fixture-, inventory-, or evidence-only companion pull
requests when the artifact has no independently usable and testable outcome
beyond enabling another planned pull request; or expensive baselines on a Phase
A-only head. No other requirement is implicitly superseded.

A stronger accepted procedure expressly governing an exact action remains
controlling and may be changed only by an explicit versioned amendment. A
domain or technical decision may define substantive evidence, review,
approval, security, authority, custody, currentness, runtime, deployment, or
domain requirements for its exact action. It cannot create a new general
repository-wide packaging or sequencing gate. A new durable repository-wide
process gate must amend the repository workflow through its own complete
workflow-governance delivery issue and pull request. Where it is ambiguous
whether an older clause is a superseded mechanic or a substantive exact-action
requirement, the older requirement remains binding until explicitly amended.

Already-approved but unmerged work remains governed by its approval. It may
finish under that approval or stop and seek a new v0.2 decision; authority is
never silently rewritten.

An unmerged pull request follows the recovery rule in sections 6 and 7. An
open-but-unusable pull request must first close unmerged; a merged pull request
is not recoverable. Reopening or replacing a closed-unmerged pull request
requires a new decision version and approval plus fresh review and
verification; no earlier evidence transfers.

## 15. Provisional design record

This workflow is acceptable before deployment because it preserves one-
capability and one-boundary scope, same-task human approval, exact-head review,
required checks, and the existing publication chain while changing delivery
packaging, approval scoping, baseline-admission sequencing, and a closed list of
standing repository-process mechanics. It grants no authority over OFARM law
or accepted substantive requirements.

Evidence requiring redesign includes a delivery PR silently crossing an
authority boundary, bundling independently reviewable capabilities, discarding
a substantive requirement as process ceremony, repeated review inability to
assess complete vertical slices, process-only PRs continuing after adoption,
or hosted baselines running repeatedly because candidate heads are not frozen
before review.

Before deployment, the provisional Codex-message approval model still requires
replacement by an independently human-controlled and independently verifiable
approval or signing system. This v0.2 decision does not change that duty.

## 16. Traceability and verification

| Invariant | Owning policy | Negative case | Concrete Phase B acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| PDW2-001 | `AGENTS.md`, `CONTRIBUTING.md` | NC-003, NC-004, NC-015 | complete-capability rule includes code and every companion artifact but excludes a second independently reviewable capability | wording audit against the delivery definition |
| PDW2-002 | `AGENTS.md`, `TASK_PROMPT.md` | NC-001, NC-006 | authority-level boundary definition, adjacent-decision classifier, and no cross-boundary allowance | inspect boundary examples and unconditional cross-boundary stop |
| PDW2-003 | `AGENTS.md`, `CONTRIBUTING.md`, PR template | NC-002–004 | explicit same-PR list and companion-artifact prohibition | search active policy for each named companion type |
| PDW2-004 | `AGENTS.md`, `CONTRIBUTING.md`, PR template | NC-005, NC-015, NC-016 | Epic/Delivery taxonomy, one-live/at-most-one-merged rule, and recovery field | inspect issue classification, capability, and PR status fields |
| PDW2-005 | `AGENTS.md`, `TASK_PROMPT.md` | NC-002, NC-006 | card binds semantic fields and names one PR; paths are evidence | inspect card fields and remove exact-path authority wording |
| PDW2-006 | `AGENTS.md`, `TASK_PROMPT.md` | NC-001, NC-006, NC-015, NC-016 | reapproval triggers include capability and named-PR change while ordinary in-boundary path discovery remains evidence | compare trigger list with the approved invariant |
| PDW2-007 | `AGENTS.md`, `TASK_PROMPT.md` | NC-008 | sequence places approval before implementation and one baseline after final review | line-order audit against the state machine |
| PDW2-008 | `AGENTS.md`, `TASK_PROMPT.md` | NC-007 | final exact-head zero-Blocker disposition and focused fix review remain | review-rule audit and unchanged admission mechanics |
| PDW2-009 | `AGENTS.md`, `TASK_PROMPT.md` | NC-012 | retained same-task approval, non-transfer, and cancellation rules | approval-state and cancellation wording audit |
| PDW2-010 | unchanged workflow/publication implementation plus `AGENTS.md` sequencing | NC-008, NC-011 | every executable admission/publication file is byte-identical to base and policy distinguishes request timing from implementation | base-to-head path audit, blob comparison, and wording audit |
| PDW2-011 | `AGENTS.md`, this RFC | NC-013 | prospective-only clause preserves completed and technical decisions | historical/prospective boundary review |
| PDW2-012 | `AGENTS.md`, this RFC | NC-009, NC-010, NC-013 | closed superseded-mechanics list, substantive-authority preservation, and ambiguity fallback | conflict/precedence wording audit against v0.1 and accepted exact-action requirements |
| PDW2-013 | `AGENTS.md`, `TASK_PROMPT.md`, PR template | NC-014 | mandatory high-risk trust floor plus conditional risk sections in the same PR | conditional-section and trust-floor audit |
| PDW2-014 | `AGENTS.md`, `TASK_PROMPT.md`, `CONTRIBUTING.md`, PR template | NC-005, NC-016 | reciprocal supersession links for replacement or expired-authority handling for reopening, one-live/at-most-one-merged rule, new decision version, and no evidence reuse | abandoned-PR recovery wording and state-transition audit |

Required checks for adoption:

- exact base-to-head path audit;
- focused text audit for contradictory exact-file authority and stale pilot
  instructions in the four adopted policy surfaces;
- focused text audit for the closed precedence rule, one-capability condition,
  unconditional cross-boundary stop, abandoned-PR recovery, and distinction
  between admission sequencing and executable admission controls;
- `git diff --check`;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- exact-head content review with zero Blockers; and
- the current v0.1-governed hosted baselines and publication sequence.

## 17. Open decisions and review disposition

Open decisions: none. This design intentionally leaves executable baseline
admission and artifact publication unchanged while changing the policy timing
for requesting admission.

Current review disposition:

- Decision version 1: withdrawn without approval after review identified a
  material undisclosed precedence effect, an undefined cross-boundary
  carve-out, an incomplete capability envelope, an unstable card path, an
  admission-sequencing ambiguity, and missing abandoned-PR recovery.
- Earlier hosted run `33195040223` and publication run `33196992666` are
  historical Phase A successes at head
  `d3ad94fc33087947ff2cd816ad40397d995f98c3` and then-live base
  `24d0b7e794caa28ede03e171119c8a86f4898470`; they are not merge-current or
  reusable for the corrected version 2 head. The earlier repository owner
  comment proves that a zero-Blocker disposition was recorded, not reviewer
  independence, and that disposition is superseded by the later Blockers.
- Corrected version 2 Phase A head
  `a02216a9414c814d95f414f6febde3a17c7200c5` received an agent-assisted
  exact-head review with zero Blockers, Follow-ups, or Preferences, followed by
  fresh immutable admission.
- Source run `33213748351` passed two clean conformance baselines, clean-run
  equivalence, and both native architectures. Separate publication run
  `33215536879` reauthenticated and published the evidence and sealed receipt
  artifact `9703219890`. These are coordinate-bound technical evidence, not
  user approval, deployment authority, or reusable final-head evidence.
- Decision version 2 was approved by the task user after the unique complete
  corrected card in the same Codex task. The exact entire visible approval
  message was:

  ```text
  I approve OFARM2 decision PROPORTIONAL-DELIVERY-WORKFLOW-001 version 2.
  ```

  Stable Codex references are task
  `01a04934-594d-7d50-b963-6a629d45be7b`; corrected-card turn
  `01a04c99-34b5-7ab0-b56e-f25abeecb1e9`, item
  `msg_03234fc5dcf11e01016a9295e8dd7887d2b7eb182b2f67bdc2`; and approval
  turn `01a04ca0-4189-70c2-9e13-834230da5da2`, task-user message item
  `msg_01a04ca0-4249-7052-9b22-408b86c5534f`. It binds only draft PR #348
  and the five paths in section 13. The original task message remains
  authority; this committed record is AI-attested navigation evidence only and
  is non-transferable and non-replayable.
- At the Phase B start check, PR #348 remained open and draft at the reviewed
  Phase A head, and no later cancellation was present. This is a point-in-time
  observation and must be checked again before merge.
- Follow-ups: none.
- Retained duty, not a Follow-up: independently human-controlled and
  independently verifiable approval or signing remains required before
  deployment.
- Preferences: none.

## 18. Phase B bounds and final gates

Phase B authority permits only the approved implementation in draft PR #348
and the five paths in section 13. It stops before:

- changing any path outside that adoption boundary;
- adding another independently reviewable capability or primary trust
  boundary;
- changing the approved authority map, effect, non-effect, invariant,
  irreversible behavior, named pull request, or production/deployment posture;
- treating v0.2 as active;
- changing workflow or publication custody;
- changing runtime, database, tenant, key, audit, or deployment behavior; or
- claiming that approval, review, checks, evidence, or merge authorizes
  deployment or production activity.

After the five surfaces are implemented, freeze the candidate head and rerun
the cheap checks. That exact head must receive zero-Blocker content review,
fresh immutable admission, all required hosted baselines, and a separate
successful authoritative publication receipt. Then perform the base-to-head
path audit, semantic-boundary audit, live approval and cancellation recheck,
named-PR and merge-coordinate check, and required-check review. Phase A review,
admission, baseline, and publication evidence cannot be reused for these final
gates. Merge PR #348 only when every final gate passes; the standing workflow
becomes active only through that merge.
