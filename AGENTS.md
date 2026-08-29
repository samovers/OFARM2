# Agents

This is the **OFARM2 implementation repository**: the working surface for building the OFARM2 Kernel, Core, and Platform, and the Slovenia plant-protection record-keeping pilot. It was extracted from the canonical OFARM repository and is designed to stand alone.

## What this repository is, and is not

- It is an **implementation and conformance packaging profile** plus pilot material. It is **not OFARM law** and creates no authority.
- Canonical authority lives in the **OFARM repository** (`samovers/OFARM`); verbatim snapshots of the law this package implements are in `reference/` (read-only, non-normative within this package, digest-pinned in `reference/REFERENCE_MANIFEST.json`).
- New schemas here are **candidate artifacts** (Constitution RC2.1 §6.16). Nothing in this repository promotes contracts or changes currentness.
- `contracts/drafts_reference/` carries DRAFT_NON_DEFAULT contracts from canonical main for implementation reference only — implementing their shapes never promotes them.

## Read path

1. `README.md` — package map and claim limits
2. `DECISIONS.md` — settled decisions; do not re-litigate them
3. `KERNEL.md` → `CORE.md` → `PLATFORM.md` — what to build
4. `M1_BRIEF.md` — the current work order
5. `PILOT_SI.md` + `profile_si_ffs/` — the pilot's verified ground
6. `conformance/CONFORMANCE.md` — the definition of done

## Working rules (binding for agents)

1. **Privacy is absolute.** Never commit personal data: no names, birth dates, addresses, phones, real KMG-MID, GERK-PID, parcel names, real document dates/areas, or document filenames containing identifiers. Real farm documents are evidence held farm-side only. Examples use fictional, format-true values. Reports about real data must be paste-safe (counts, masked IDs, booleans). When in doubt, leave it out and ask.
2. **The law freeze holds for this repository.** Implementation findings go to `ERRATA.md` — never into `reference/` copies, never as new law. (The canonical repository evolves in parallel under the steward's governance; absorb its changes by extraction with provenance, never by editing.)
3. **Run `python3 conformance/ofarm_pkg_contract_check.py` before every commit.** It must PASS.
4. **Provenance discipline:** every file extracted from the canonical repository gets a manifest entry (source path, commit, sha256). Extracted files are byte-identical — never edited.
5. **No silent truth.** Honor the seven Kernel rules in `KERNEL.md` in everything you build: append-only, default deny, capture ≠ commitment, no shortcut to truth, derived current state with receipts, distinct times, refusal over pretending.
6. **Claim limits:** this project claims record-keeping completeness for the pilot — never current-compliance, certification, production readiness, or legal advice. Do not generate text that claims more.
7. **Country/profile separation:** Country-specific identifiers, law, evidence sources, currentness rules, authority names, and conformance fixtures belong in profile/package layers. Core-facing material must use profile-neutral terms unless explicitly presenting a non-normative example. Non-normative examples must not become executable Core law.
8. **Honest reporting:** failing tests are reported as failing; design fixtures are never presented as executed evidence; skipped steps are named.
9. **Commit style:** imperative subject, body explains what and why, reference the M1 brief task where applicable.

## Standing repository-development authority

This root `AGENTS.md` is the canonical source for standing
repository-development procedure only. It is not OFARM law and cannot
supersede an accepted technical, security, authority, custody,
evidence-sufficiency, currentness, runtime, deployment, or domain invariant.
The durable design and evidence for this procedure are in
`docs/rfcs/OFARM2_Proportional_Delivery_Workflow_RFC_v0_2.md` and its closed
final-acceptance amendment,
`docs/rfcs/OFARM2_Human_Final_Quality_Acceptance_Workflow_RFC_v0_1.md`.
`TASK_PROMPT.md` is its working form, `CONTRIBUTING.md` is contributor guidance,
and `.github/PULL_REQUEST_TEMPLATE.md` is the capture surface for one pull
request; none is a competing source of repository-development rules.

For new, unapproved work, this procedure prospectively supersedes only this
closed list of older packaging and sequencing mechanics:

- exact repository paths as human approval authority;
- reapproval caused only by unambiguously in-boundary file discovery;
- one fixed Phase A section structure regardless of risk;
- a required committed approval appendix;
- contract-, approval-, fixture-, inventory-, or evidence-only companion pull
  requests whose artifact has no independently usable and testable outcome
  beyond enabling another planned pull request; and
- expensive baselines on a Phase A-only head.

A stronger accepted procedure expressly governing an exact action remains
controlling. Domain and technical decisions may define substantive evidence,
review, approval, security, authority, custody, currentness, runtime,
deployment, or domain requirements for their exact actions. They do not create
new general repository packaging or sequencing gates. A new durable
repository-wide process gate needs its own complete workflow-governance
Delivery issue and pull request, a demonstrated current failure or threat, a
named consumer, and an expiry or review point. If classification is ambiguous,
the older requirement remains binding until an explicit versioned amendment
resolves it.

Completed decisions and historical evidence are not rewritten. An
already-approved unmerged pull request keeps AI merge authority only when its
directly retrievable governing approval explicitly granted that authority.
Pull-request age, branch age, and GitHub activity create no authority.

## Proportional delivery workflow

### Delivery units

A **Tracking Epic** describes a programme with more than one independently
reviewable capability or more than one primary trust boundary. It owns the
outcome map and dependency order, not an implementation pull request. Each
coherent capability receives its own Delivery child issue.

A **Delivery issue** states one user- or system-visible outcome, one
independently reviewable capability, one primary trust boundary, falsifiable
acceptance criteria, and explicit non-goals. It has one live implementation
pull request at a time and at most one merged implementation pull request. If
an issue needs multiple independently reviewable capabilities or boundaries,
reclassify it as a Tracking Epic and split Delivery issues before
implementation.

A **Delivery pull request** contains the smallest complete vertical slice for
that capability. Implementation, owned migrations, tests, fixtures,
compatibility bridges, documentation, generated inventories, and mechanical
evidence travel together when they are needed to implement or prove the same
boundary. Do not create a separate pull request merely to publish a contract,
record approval, amend a path list, bridge a fixture, update an inventory, or
publish evidence when it has no independently usable and testable outcome. A
complete prerequisite in a distinct boundary is valid only with its own
Delivery issue, acceptance outcome, and complete vertical slice.

Small diff size is not an acceptance criterion. Coherence, reviewability, one
capability, and one authority-level boundary are.

Changes belong together only when they are owned by the same authority, share
one threat model and atomic failure or rollback story, and jointly deliver the
one capability. Adjacent code may travel when it consumes an already accepted
interface and cannot independently change an allow/deny or identity decision,
credential or key access, tenant attribution or isolation, durable write or
transaction authority, runtime activation, readiness or audit authority,
evidence-publication custody, deployment or currentness, or an irreversible
effect. If it can change one of those decisions, stop before editing it and
create separate Delivery work. This workflow has no cross-boundary waiver.

Only an unmerged implementation pull request is eligible for recovery. An
open-but-unusable pull request must close unmerged before a replacement opens,
and old and new pull requests must carry reciprocal supersession links.
Reopening a closed-unmerged pull request creates no authority. Replacement or
reopening requires a new decision version, new task-user approval, and fresh
review, checks, admission, baselines, and publication; no earlier authority or
evidence transfers. Recovery for the same capability does not make it a
Tracking Epic. A merged pull request is never recoverable; later correction is
new Delivery work.

### Before implementation

OFARM2 is pre-deployment development work. Prefer the best coherent design now
over preserving a temporary implementation. Preserve accepted contracts,
evidence, explicit invariants, and stated boundaries, and verify in proportion
to risk.

Before editing, state:

- the problem and independently reviewable capability;
- the one primary trust boundary;
- permitted effects, non-effects, falsifiable invariants, and non-goals;
- the expected repository areas, as scope prediction rather than approval
  authority;
- why the change is the smallest complete vertical slice;
- whether the design is provisional and, if so, why it is acceptable before
  deployment, what evidence would require redesign, and the likely upgrade
  path; and
- the focused verification for the boundary.

Routine work that does not change, rely on, or exercise authority does not
require an early semantic-approval stop. Every AI-operated Delivery merge still
requires the final exact-head task-user stop below. A high-risk or otherwise
approval-governed change uses the risk-shaped Phase A and decision workflow.
Prefer deletion, direct code paths, explicit boundary contracts, immutable
values, and small modules over speculative abstractions, compatibility shims,
and duplicate validation.

## Risk-shaped Phase A

Every Phase A states the capability, primary boundary, permitted effects,
non-effects, falsifiable invariants, non-goals, smallest coherent change, and
verification. Add an authority map whenever the change changes, relies on, or
exercises authority.

Treat a task as high-risk when it materially changes any of these areas:

- authentication, credential verification, principal resolution, or
  authorization;
- signing, key custody, or key authority;
- tenant isolation;
- database roles, transactions, migrations, or durability semantics;
- runtime integration, startup readiness, or security-audit behavior; or
- irreversible data behavior.

If classification is unclear, treat the task as high-risk until the boundary
is explicitly narrowed. Every high-risk Phase A also states protected assets,
trusted and untrusted sides or inputs, excluded attacker capabilities, the
primary risk and containment rule, and at least one production-reachable
negative case for every invariant. Add a state machine and ordering model only
for stateful or transactional work; a custody model only for credentials, keys,
or protected outputs; and migration, rollback, or recovery analysis only when
durability changes.

Put Phase A in the draft pull request description by default. Add a versioned
RFC or ADR in that same pull request only when the architectural decision must
remain useful after the pull request closes. A committed approval appendix is
not required: the task-user message remains authority, while a compact pull
request reference is navigation evidence only. Never create a separate
contract or approval-record pull request merely to enable another planned pull
request when it has no independently usable and testable outcome.

Review Phase A to zero Blockers before presenting a decision card. Do not
implement until the required approval is valid. If implementation invalidates
the approved design, stop and request a new decision version.

## Pre-deployment decision and approval

Authority ownership is closed:

- the task user owns semantic approval, final quality acceptance, refusal,
  requested changes, cancellation, supersession through a new decision
  version, and exact-head merge authorization;
- the live card owns the problem, approved capability, primary boundary,
  authority map, effects, non-effects, decision-level invariants, and named
  pull request;
- Phase A owns the detailed design, expected repository areas, and verification
  plan;
- reviewers own demonstrated Blocker findings, not scope expansion;
- CI and the existing publication system own mechanical verification and
  evidence custody only, not human approval;
- the AI owns in-boundary implementation, review handling, checks, existing
  admission and publication coordination, and final-packet preparation. It may
  invoke the existing GitHub-native pull-request merge only after the later
  exact-head authorization and every existing gate are valid;
- GitHub owns native pull-request state, merge eligibility, and the merge
  transition; and
- existing OFARM, runtime, database, tenant, key, audit, deployment, and
  publication authorities retain their current owners.

For a prospective high-risk or otherwise approval-governed Delivery change,
use one already-created draft pull request. Its live card must state the
decision identity and version, problem, one independently reviewable
capability, recommended decision, primary trust boundary, authority map,
primary risk and containment rule, permitted effects, non-effects,
decision-level invariants, named draft pull request, verification gates,
reapproval triggers, provisional posture, and this exact approval form:

```text
I approve OFARM2 decision <DECISION_ID> version <VERSION>.
```

Approval is only the entire visible text of a later task-user message in the
same Codex task. Before recognizing it, verify that the original card and
approval remain directly retrievable with stable references in the required
order and that the card names the existing draft pull request. Generic
approval, GitHub activity, credentials, AI or tool messages, delegation,
another task, or a summary of lost original items never supplies approval.

Only the unique, most recent, unsuperseded complete card for a decision identity
and version is live. A replacement withdraws its predecessor; a semantic card
change requires a new version. A valid approval binds the capability, effects,
authority, invariants, and named pull request, not exact bytes or an exhaustive
file inventory. It cannot be transferred to another pull request or replayed
for another decision.

The Phase A contract names expected repository areas so reviewers can judge
scope. Discovering another implementation, test, fixture, documentation, or
generated-evidence file inside the same approved boundary does not require a
new decision. The final scope report must explain the addition and prove it
adds no authority, effect, independently reviewable capability, or boundary.

A new decision version and approval are required when the capability, primary
trust boundary, authority map, permitted effect, non-effect, decision-level
invariant, irreversible behavior, named pull request, or production/deployment
posture changes. A path change triggers reapproval only when it proves one of
those semantic changes or makes preservation genuinely ambiguous.

A valid semantic approval authorizes only the named pull request. Within its
approved boundary the AI may implement, test, document, regenerate mechanical
evidence, commit, push, address in-boundary Blockers, rerun checks, and prepare
the final packet. It does not authorize merge. Any later stop-like task-user
message pauses immediately. Closing the named pull request unmerged expires
authority and invokes the recovery rule above.

This authority is provisional repository development only. It never authorizes
deployment, release, current/default promotion, production access, or a
production security waiver. Before deployment it must be replaced by an
independently human-controlled and independently verifiable approval or signing
system.

## Review, baseline, publication, and merge ordering

For an approval-governed Delivery change, use this fail-closed order:

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
  -> FINAL_SCOPE_EVIDENCE_AND_EXCELLENCE_RECHECK
  -> READY_FOR_USER_FINAL_REVIEW
  -> AI_YIELDS_WITH_EXACT_HEAD_PACKET
  -> USER_AUTHORIZED_EXACT_HEAD_MERGE
  -> AI_RECHECKS_HEAD_STATE_GATES_AND_CANCELLATION
  -> GITHUB_NATIVE_PR_MERGE_WITH_EXPECTED_HEAD
  -> VERIFY_MERGED_AND_CLOSE_DELIVERY_ISSUE
```

Treat the full hosted conformance and native-verifier workflows as expensive
baselines. Do not request, monitor, diagnose, or rerun them for a pull-request
head before implementation and an exact-head content review with zero
Blockers. Automatically started expensive jobs may finish unattended, but they
do not replace this order.

Every new candidate head starts in `REVIEW_PENDING`, including a head produced
only by documentation or a Blocker fix. While review is pending or reports a
Blocker, run only mandatory and cheap local checks, push the correction, and
obtain the next exact-head review. A zero-Blocker review must identify the full
commit SHA and is stale after any new commit. Perform at most one unconstrained
full content review at an exact head. After a Blocker fix, review only the fix
and affected invariants unless new evidence demonstrates that the original
scope is unsafe.

After a zero-Blocker exact-head review, a repository owner, member, or
collaborator may create one admission issue comment on the pull request. The
comment must end with this exact footer:

```text
OFARM2_BASELINE_ADMISSION
head=<FULL_COMMIT_SHA>
blockers=0
```

The admission comment is a separate technical trigger, not content review or
human approval. Never edit it. The default-branch gate must verify live that
the comment is created and unedited, its exact UTF-8 body digest is bound, its
author still has repository standing, the pull request is open, the footer SHA
equals the current head, and the execution merge commit binds the live base and
head. Only then may it call the same-commit expensive executor.

A new commit, close/reopen transition, or deletion/edit of an admission comment
revokes admitted work. A standing reviewer may also create this exact-head
revocation comment:

```text
OFARM2_BASELINE_REVOCATION
head=<FULL_COMMIT_SHA>
```

Public or ordinary comments never share the executor's cancellation group. The
dispatcher must run only trusted default-branch policy and must never check out
pull-request code. Never create admission while content review has a Blocker.
Labels, earlier-head reviews, results from another SHA, agent memory, manual
workflow runs, formal-review events, and pull-request-controlled workflows are
not substitutes for live admission.

Jobs that execute pull-request code may upload only explicitly provisional
artifacts. Their final fresh handoff job must run trusted policy only, reject
unexpected or pre-squatted artifact names, bind the exact source
workflow/run/attempt and provisional artifact IDs and digests, and upload the
immutable publication ticket last.

Normal success artifact names may be published only after the substantive jobs
and live admission proofs succeed.

Established authoritative names belong only to the separate default-branch
`workflow_run` publication workflow. Its fresh runners must never check out or
execute the admitted merge or downloaded content. They must resolve the exact
successful source run and ticket by artifact ID, recheck live admission and
revocation, and validate downloads as untrusted data with trusted policy code.
Producer artifacts must be downloaded by exact ID, digest-checked before
extraction, and extracted only by trusted policy into a fresh empty root that
rejects traversal, links, special files, duplicates, and size excess. Exact
file inventories are required before and after trusted metadata is added. Git
policy checks must ignore system and global configuration and disable hooks and
filesystem monitors. The publisher must re-authenticate both architecture
artifacts and derive the native index only from those re-authenticated
artifacts.

Artifact names alone are never authoritative. Authority requires a successful
publication run plus its final receipt binding source and publisher workflow
refs, policy SHAs, run IDs and attempts, all four source artifact IDs and
digests, and all five published evidence artifact IDs and digests. Upload the
receipt artifact last. A failed run that populated established names without
sealing that receipt is incomplete and untrusted. Until a repository consumer
is added, the receipt is write-only evidence and external consumers must
validate it before trusting an artifact. A main-branch post-merge source run is
not pull-request admission, has no live PR revocation to recheck, and remains
automatic, but it uses the same separate publisher. Because the artifact API
is not attempt-scoped, source and publisher workflow reruns fail closed; start
a fresh reviewed and admitted source run instead.

The admission comment must be created with a user or GitHub App credential
whose event can start the default-branch gate; the repository `GITHUB_TOKEN`
does not supply that trigger. Admission does not imply branch protection.
Verify repository settings before describing hosted baselines as a
GitHub-enforced merge requirement.

### Final human acceptance and native merge

After every applicable technical and evidence gate passes, prepare one final
packet for any Delivery pull request the AI would merge. It must contain:

- the Delivery issue, repository, pull request, and full current head SHA;
- the capability, primary trust boundary, final changed paths, and material
  diff summary;
- permitted effects, non-effects, unresolved Follow-ups, and any Phase A
  deviations with proof that semantic scope stayed intact;
- cheap checks, exact-head review, hosted evidence, publication, and receipt
  results as applicable;
- Blockers, Follow-ups, and Preferences;
- the `EXC-001` through `EXC-006` assessment, including deletions, duplicate
  paths or state, abstractions added, and the simplest credible alternative;
- for approval-governed work, the decision, live card, semantic approval, and
  named-pull-request references;
- same-task provenance sufficient to retrieve the packet later; and
- this exact authorization sentence with the pull request number and full head
  SHA filled in:

```text
I authorize the AI to merge samovers/OFARM2 PR #<NUMBER> at head <FULL_HEAD_SHA>.
```

Present the complete packet and end the turn without merging. Only the entire
visible text of that exact sentence in a later task-user message in the same
Codex task authorizes merge. The packet and authorization must remain directly
retrievable in that order. Earlier semantic approval, routine classification,
GitHub activity, reviews, checks, admission, publication, credentials, AI or
tool messages, delegation, silence, elapsed time, paraphrases, and summaries do
not authorize merge.

Immediately before merge, retrieve the packet and later authorization and
recheck that the pull request is open, non-draft, at the authorized full head,
has not been closed and reopened since the packet, has no demonstrated
Blocker, still preserves semantic scope, and satisfies every existing check,
admission, publication, and receipt gate. A new commit or head change, semantic
expansion, later stop or cancellation, conflicting later task-user message, or
close/reopen transition invalidates the authorization. Requested in-boundary
changes return the pull request to implementation, fresh review and applicable
evidence, a new packet, yield, and later authorization. No response leaves the
pull request open and unmerged.

Use GitHub's normal pull-request merge operation with its expected-head
condition set to the authorized SHA, such as `--match-head-commit` or the API
`sha` field. Never pass `--admin` or `--auto`, bypass a native requirement, or
push the target branch directly. A native rejection is a stop, not permission
to use another writer. This final authorization binds the pull-request head,
not an exact base, integrated tree, merge commit, merge message, or target
write. Existing base-sensitive controls decide whether evidence must be
refreshed.

The task user may decline final authorization or request in-boundary changes
for any reason. The review classifications below constrain reviewers, not the
user's final decision.

## Code excellence

Every Delivery task contract, Phase A, pull request, review, and final packet
applies these invariants at the depth appropriate to its capability:

- **EXC-001 — One authoritative path.** The capability has one authoritative
  decision path and one source of truth for each owned fact.
- **EXC-002 — No avoidable duplication.** Do not add duplicate authority,
  validation, durable or derived state, compatibility paths, field inventories,
  or framework layers.
- **EXC-003 — Direct invariant trace.** Each material invariant traces through
  its owning implementation to focused evidence without a hidden fallback.
- **EXC-004 — Delete superseded paths.** Remove obsolete owned code, shims,
  flags, and fallbacks unless a current time-bounded compatibility duty and
  deletion trigger are explicit.
- **EXC-005 — Abstractions pay rent now.** A new abstraction must isolate the
  current boundary, remove concrete duplication, or serve multiple current
  consumers. Hypothetical reuse is insufficient.
- **EXC-006 — Consider the simpler path.** Any material increase in concepts,
  indirection, state, or bespoke machinery names the simplest credible
  alternative and the invariant that prevents using it.
- **EXC-007 — Taste is not a Blocker.** Naming, formatting, and preference
  among designs satisfying `EXC-001` through `EXC-006` remain non-blocking.

A code-excellence Blocker must name the concrete duplicate source, path, state,
validation, compatibility layer, unnecessary abstraction, or obscured
invariant; its present maintenance, audit, testing, or isolation cost; the
violated `EXC-001` through `EXC-006` invariant; and the smallest acceptable
correction. Line counts or automated complexity scores may support that
finding, but never replace it.

## Review classifications

Classify every finding as exactly one of:

- **Blocker:** a demonstrated in-scope correctness, security, data-integrity,
  contractual, production-safety, or code-excellence failure under the rules
  above. Name the violated invariant and smallest acceptable fix. For high-risk
  work also name the supported
  production entry point, in-scope actor, exact execution or state-transition
  path, required preconditions, material consequence, and minimal reproduction
  or counterexample.
- **Follow-up:** valid work outside the pull request boundary. Record it as
  separate Delivery work; do not expand the current change.
- **Preference:** optional style or alternative-design advice. It never delays
  merging.

Only demonstrated Blockers delay technical readiness. Once acceptance criteria
pass, every required gate is green, and no Blocker remains, prepare the final
packet and yield; do not merge without the later exact-head task-user
authorization. New ideas, Preferences, and non-blocking hardening become
Follow-ups and do not reopen review.

## Review guard - Core neutrality

Treat these as Blocker findings in Core-facing material: country-specific identifiers, authority names, legal deadlines, evidence sources, currentness policies, or conformance fixtures being presented as universal OFARM law; profile examples becoming executable Core logic; or profile-local law leaking into Core, Kernel, Platform, runtime adapters, contracts, or generated manifests.

## Review guard - Netherlands GO + GLMC 7 slice

For `profile_nl_go_glmc7_2026/`, treat these as Blocker findings: country
law leaking into Core, Kernel, Platform, runtime adapters, or the SI profile; a
whole-Netherlands production claim; an automated 30-hectare GLMC 7 carve-out;
BAS, Ctgb, Bijlage Aa, manure-register, GLMC 4, or GLMC 10 scope creep; or any
promotion path that accepts public/current-state data alone as historical truth.
