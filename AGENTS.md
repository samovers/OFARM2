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
`docs/rfcs/OFARM2_Proportional_Delivery_Workflow_RFC_v0_2.md`.
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

Completed decisions and historical evidence are not rewritten. Already-approved
unmerged work keeps its approval unless it stops and seeks a new decision.

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
require a user approval stop. A high-risk or otherwise approval-governed change
uses the risk-shaped Phase A and decision workflow below. Prefer deletion,
direct code paths, explicit boundary contracts, immutable values, and small
modules over speculative abstractions, compatibility shims, and duplicate
validation.

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

- the task user owns approval, refusal, cancellation, and supersession through
  a new decision version;
- the live card owns the problem, approved capability, primary boundary,
  authority map, effects, non-effects, decision-level invariants, and named
  pull request;
- Phase A owns the detailed design, expected repository areas, and verification
  plan;
- reviewers own demonstrated Blocker findings, not scope expansion;
- CI and the existing publication system own mechanical verification and
  evidence custody only, not human approval;
- the AI owns in-boundary implementation, review handling, and merge only after
  every gate passes; and
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

A valid approval authorizes only the named pull request. Within its approved
boundary the AI may implement, test, document, regenerate mechanical evidence,
commit, push, address in-boundary Blockers, rerun checks, and merge after every
gate below passes. Any later stop-like task-user message pauses immediately.
Closing the named pull request unmerged expires authority and invokes the
recovery rule above.

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
  -> FINAL_SCOPE_AND_APPROVAL_RECHECK
  -> MERGE_AND_CLOSE_DELIVERY_ISSUE
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

Before merge, post one compact scope report. For approval-governed work, name
the decision, card, approval, and pull request references; for routine work,
name the Delivery task contract and pull request. Always list final changed
paths, verification and review results, and whether every path preserves the
declared capability, primary boundary, authority map when applicable,
permitted effects, non-effects, and invariants. Recheck the exact head,
required checks, any required publication receipt, and absence of a
demonstrated Blocker. For approval-governed work also recheck live task
evidence, named-pull-request binding, and absence of later cancellation. If
preservation is ambiguous, stop for a new decision version.

## Review classifications

Classify every finding as exactly one of:

- **Blocker:** a demonstrated in-scope correctness, security, data-integrity,
  contractual, or production-safety failure. Name the violated invariant and
  smallest acceptable fix. For high-risk work also name the supported
  production entry point, in-scope actor, exact execution or state-transition
  path, required preconditions, material consequence, and minimal reproduction
  or counterexample.
- **Follow-up:** valid work outside the pull request boundary. Record it as
  separate Delivery work; do not expand the current change.
- **Preference:** optional style or alternative-design advice. It never delays
  merging.

Only demonstrated Blockers delay merge. Once acceptance criteria pass, every
required gate is green, and no Blocker remains, merge the pull request. New
ideas, Preferences, and non-blocking hardening become Follow-ups and do not
reopen review.

## Review guard - Core neutrality

Treat these as Blocker findings in Core-facing material: country-specific identifiers, authority names, legal deadlines, evidence sources, currentness policies, or conformance fixtures being presented as universal OFARM law; profile examples becoming executable Core logic; or profile-local law leaking into Core, Kernel, Platform, runtime adapters, contracts, or generated manifests.

## Review guard - Netherlands GO + GLMC 7 slice

For `profile_nl_go_glmc7_2026/`, treat these as Blocker findings: country
law leaking into Core, Kernel, Platform, runtime adapters, or the SI profile; a
whole-Netherlands production claim; an automated 30-hectare GLMC 7 carve-out;
BAS, Ctgb, Bijlage Aa, manure-register, GLMC 4, or GLMC 10 scope creep; or any
promotion path that accepts public/current-state data alone as historical truth.
