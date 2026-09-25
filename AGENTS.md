# AGENTS.md — OFARM2

OFARM2 implements the Kernel, Core, Platform, and profile packages. This
repository is an implementation and conformance surface, not OFARM law.

## Start with the actual task

A request to review, explain, or propose is not permission to edit repository
files, create issues, post comments, or merge. Produce the requested result.
For implementation work, continue from the accepted architecture rather than
starting a redesign.

Read `README.md` for the current repository map and claim limits, then the issue,
plan, or brief governing the task. Read relevant decisions in `DECISIONS.md`
and follow references needed to establish the applicable requirements.

Use task-based reading rather than a mandatory tour of the repository:

- **Runtime:** start with `kernel/README.md`, then the relevant parts of
  `KERNEL.md`, `CORE.md`, or `PLATFORM.md`. Keep production and legacy M1 paths
  separate.
- **Profile work:** read the affected profile's instructions, status, evidence
  policy, and conformance requirements. Read `PILOT_SI.md` for SI pilot work,
  not as a universal requirement for unrelated profiles.
- **Implementation and verification:** read `conformance/CONFORMANCE.md` and
  applicable instructions in `conformance/REVIEW_BASELINE.md`.
- **Repository delivery:** use the mandatory procedure below at the relevant
  stage.

`M1_BRIEF.md` is historical. M2 and M3 provide later sequencing context; the
actual task determines the work order. Read governing source material before
changing its behavior. A summary or search excerpt is not a substitute when
an exact requirement matters.

## Communication

Explain decisions and findings in plain English. Keep routine updates brief.
Explain technical terms when needed, without losing precision. Preserve the
required content and any mandated exact wording of decision cards, approval
forms, and final packets.

## Authority and mandatory procedure

This root file remains the canonical source for standing repository-development
procedure only. It incorporates
[`docs/development/DELIVERY_PROTOCOL.md`](docs/development/DELIVERY_PROTOCOL.md)
as its mandatory detailed procedure, not a competing authority. The summaries
here do not waive that procedure or expand its closed precedence rules.

Before Delivery implementation or review, read its **Standing
repository-development authority**, **Proportional delivery workflow**, and
**Risk-shaped Phase A** sections. Before reviewing or re-reviewing Delivery
work, also read [Content review and re-review](docs/development/DELIVERY_PROTOCOL.md#content-review-and-re-review).

Before preparing, relying on, or evaluating approval, read **Pre-deployment
decision and approval**. Before performing or evaluating admission, hosted
baselines, publication, final acceptance, or merge, read **Review, baseline,
publication, and merge ordering**, including its final-acceptance subsection.
These reading requirements cover mechanisms under review, not just actions you
execute. For replacement or reopened pull requests, apply the recovery rules
first. Read the complete applicable sections and follow their prerequisites.

A missing procedure, unresolved conflict, or unavailable approval evidence is
not permission to improvise the affected action. Stronger accepted
exact-action requirements remain controlling. If classification is ambiguous,
the older requirement remains binding until a versioned amendment resolves it.
`TASK_PROMPT.md`, `CONTRIBUTING.md`, and the pull-request template are working
surfaces, not independent sources of procedure.

Canonical OFARM authority lives in `samovers/OFARM`. The snapshots in
`reference/` are read-only, non-normative within this package, and pinned in
`reference/REFERENCE_MANIFEST.json`. Do not edit them. Record findings against
implemented law in `ERRATA.md`; absorb accepted canonical changes through
provenance-preserving extraction. Every extraction must remain byte-identical
and record its source path, commit, and SHA-256 in the appropriate manifest.
New schemas are candidates. Implementing `contracts/drafts_reference/` never
promotes its draft/non-default contracts.

Follow accepted decisions. Do not reopen them for preference alone. When
concrete evidence reveals a defect, contradiction, or missing executable
contract, report it and propose the smallest correction. Do not silently
replace the decision or implement an unapproved change to its meaning.

## Permanent safeguards

**Privacy.** Never commit personal data: names, birth dates, addresses, phones,
real KMG-MID or GERK-PID, parcel names, real document dates or areas, or filenames
containing identifiers. Real farm documents remain farm-side evidence.
Examples must be fictional and format-true. Reports about real data must be
paste-safe: counts, masked identifiers, or booleans. When uncertain, leave the
data out and ask. Never put secrets or credentials in commits or reports.

**No silent truth.** Preserve the seven Kernel rules in `KERNEL.md`: append-only,
default deny, capture is not commitment, no shortcut to truth, derived current
state with receipts, distinct times, and refusal over pretending.

**Profile separation.** Country-specific identifiers, law, authorities,
evidence sources, currentness policies, and conformance fixtures belong in
profile/package layers. Core-facing material must use profile-neutral terms
unless explicitly presenting a non-normative example. Such an example must
never become executable Core law.

**Claim limits.** Preserve the limits in `README.md` and the affected profile.
The SI pilot claims record-keeping completeness, not current compliance.
Do not claim production readiness, certification, external-standard readiness,
autonomous release authority, legal/security/compliance advice, or automatic
schema promotion. Passing tests does not grant authority or expand readiness.

**Honest evidence.** Report failing, skipped, unavailable, and unexecuted checks
accurately. Distinguish design fixtures from executed evidence and local results
from required hosted evidence. Do not weaken a check merely to obtain a pass.

## Complete authorized work

Deliver one independently reviewable capability within one primary trust
boundary. Include the implementation, tests, necessary documentation, and
mechanical companion changes that jointly deliver that capability. Do not
fragment them into pull requests with no independently usable outcome. Do not
combine independent authority changes. Apply the protocol's Delivery issue,
scope, and recovery requirements.

Before editing, state the problem, capability, boundary, permitted effects,
non-effects, invariants, non-goals, expected areas, smallest complete solution,
provisional posture, and verification. Keep the explanation proportionate to
the risk; brevity does not remove required content.

Qualifying routine work that does not change, rely on, or exercise authority
needs no early semantic-approval stop. High-risk or otherwise approval-governed
work requires the protocol's reviewed Phase A and valid approval before
implementation. Treat a task as high-risk when it materially changes
authentication, credential verification, principal resolution, authorization,
signing, key custody or authority, tenant isolation, database roles,
transactions, migrations or durability semantics, runtime integration, startup
readiness, security-audit behavior, or irreversible data behavior. Unclear
classification is high-risk until explicitly narrowed.

Within valid task authority, complete implementation, focused testing,
documentation, and in-boundary fixes without repeatedly asking permission.
Commit, push, and coordinate evidence only as the applicable procedure permits.
Finding another necessary file inside the same approved boundary does not
itself require reapproval; explain it in the final scope report.

Use authorized, read-only repository inspection to resolve technical uncertainty
before asking the user. Choose ordinary implementation details within the
approved design without requesting repeated permission. When a requirement
blocks progress, identify the exact rule, the blocked action, and the missing
decision or evidence. This does not expand access, authorize implementation
before required approval, or permit continued work after a user stop.

Stop for a changed capability, boundary, authority map, permitted effect,
non-effect, decision-level invariant, irreversible behavior, named pull request,
or production/deployment posture; uncertain preservation of those limits;
unavailable required approval; or a later user stop. Apply the protocol's exact
reapproval and cancellation rules. Confidence in a design never grants authority.

## Verification and merge

Before every commit, run:

```sh
python3 conformance/ofarm_pkg_contract_check.py
```

It must pass. Run focused tests for changed behavior and affected invariants;
required conformance and hosted checks are not optional. Do not substitute a
convenient local environment for the pinned evidence baseline.

Once the required checks pass for the current revision, continue to the next
required stage. Add or repeat optional checks only when changed inputs, stale
evidence, failures, or a specific unresolved concern justify them. This does
not waive the mandatory package check before each commit, fresh exact-head
review after a new commit, required conformance or hosted checks, live pre-merge
rechecks, or the protocol's ordering rules.

Every new commit makes the previous exact-head review stale. While review is
pending or has Blockers, run only mandatory and cheap local checks. Do not
request, monitor, diagnose, or rerun expensive hosted baselines before complete
implementation and a zero-Blocker review naming the full current commit SHA.
Follow the protocol for admission, revocation, evidence custody, and publication.

For prospective Delivery work, implementation approval is not merge approval.
After the applicable gates pass, present the protocol's complete final packet
and end the turn without merging. Only the entire text of this exact sentence
in a later task-user message in the same Codex task authorizes that merge:

```text
I authorize the AI to merge samovers/OFARM2 PR #<NUMBER> at head <FULL_HEAD_SHA>.
```

The packet and authorization must remain directly retrievable in that order.
Immediately before merge, recheck the authorized head, user instructions, live
pull-request state, and every applicable gate. Use only native pull-request
merge with the expected-head condition. Never use `--admin`, `--auto`, direct
target-branch writes, or another writer after native rejection. Historical
approvals retain only the authority explicitly preserved by the protocol;
age and GitHub activity establish nothing. Development approval never
authorizes deployment, release, production access, or a security waiver.

Use imperative commit subjects; explain what and why in the body and reference
the governing task rather than automatically citing an old milestone.

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
