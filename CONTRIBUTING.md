# Contributing to OFARM2

OFARM2 changes should deliver a complete, reviewable capability without
combining independent authority or custody changes. Root `AGENTS.md` is the
canonical source for repository-development procedure only. This guide
explains how contributors apply it.

## Classify the work

A **Tracking Epic** describes a programme with more than one independently
reviewable capability or more than one primary trust boundary. It owns the
outcome map and dependency order, not an implementation pull request. Create or
identify one Delivery child issue for each coherent capability.

A **Delivery issue** states one user- or system-visible outcome, one
independently reviewable capability, one primary trust boundary, falsifiable
acceptance criteria, and non-goals. It has one live implementation pull request
at a time and at most one merged implementation pull request.

Same authority ownership is not enough to combine independent capabilities.
There is no cross-boundary waiver. If inspection reveals another capability or
authority-level boundary, stop and create separate Delivery work rather than
continuing several pull requests under one undifferentiated issue.

## Before implementation

Start with [the OFARM2 task prompt](TASK_PROMPT.md). State the problem,
capability, primary boundary, permitted effects, non-effects, invariants,
non-goals, expected repository areas, smallest coherent solution, provisional
posture, and verification.

Use a risk-shaped Phase A for high-risk or approval-governed work. Keep Phase A
in the already-created draft pull request description by default. Add a durable
RFC or ADR in that same pull request only when the architectural decision must
outlive it. Review Phase A and obtain any required semantic approval before
implementation. Do not run expensive hosted baselines merely to validate a
design-only head.

Add an authority map whenever work changes, relies on, or exercises authority.
For high-risk work, also record protected assets, trusted and untrusted sides or
inputs, excluded attacker capabilities, the primary risk and containment rule,
production-reachable negative cases, and invariant traceability in that same
pull request.

A complete prerequisite in a different boundary is valid only when it has its
own Delivery issue, independently usable and testable outcome, and complete
vertical slice.

## Complete Delivery pull requests

A Delivery pull request contains the smallest complete vertical slice for its
capability. Include these when needed for the same boundary:

- Phase A, durable design, and compact decision navigation;
- implementation and deletion of superseded paths;
- owned schema or migration changes;
- unit, integration, hostile, and regression tests;
- fixtures and historical compatibility bridges;
- documentation;
- generated inventories, snapshots, and mechanical evidence; and
- focused fixes for in-boundary Blockers.

Do not create a separate contract-only, approval-only, allowlist-only,
fixture-only, inventory-only, or evidence-only pull request whose artifact has
no independently usable and testable outcome beyond enabling another planned
pull request. Small diff size is not an acceptance criterion; completeness,
reviewability, one capability, and one boundary are.

Prefer deletion, direct code paths, explicit boundary contracts, immutable
values, and small modules over framework layers, speculative abstractions,
compatibility shims, and duplicate validation.

## Semantic approval

When approval is required, the task user approves the capability, effects,
authority, invariants, and one already-created draft pull request. Exact paths,
GitHub activity, reviews, checks, admission, publication, and the pull request
template do not supply human approval.

A newly discovered implementation, test, fixture, documentation, or
generated-evidence file inside the approved boundary is scope evidence, not an
automatic reapproval trigger. Explain it in the final scope report. A new
decision version is required for a changed capability, boundary, authority map,
effect, non-effect, invariant, irreversible behavior, named pull request, or
production/deployment posture, or when preservation is ambiguous.

The same-task task-user message remains authority. A compact pull request
reference is navigation evidence only; no committed approval appendix or
separate approval-record pull request is required.

## Pull request contract

Complete [the pull request template](.github/PULL_REQUEST_TEMPLATE.md). It
records:

- the Delivery issue and optional Tracking Epic;
- the problem;
- one independently reviewable capability;
- one primary trust boundary and its containment;
- acceptance criteria, non-goals, and the smallest complete change;
- companion-artifact completeness;
- provisional posture and applicable stronger exact-action requirements;
- risk class, Phase A location, applicable authority map and high-risk trust
  floor, and decision navigation when required;
- abandoned-pull-request recovery when applicable;
- verification and exact-head review disposition; and
- final changed paths, semantic scope preservation, and cancellation check.

The template records evidence. It does not create approval or redefine the
admission and publication controls in root `AGENTS.md`.

## Review protocol

Every review finding uses exactly one classification:

- **Blocker:** a demonstrated in-scope correctness, security, data-integrity,
  contractual, or production-safety failure. It names the violated invariant
  and smallest acceptable fix.
- **Follow-up:** valid work outside the pull request boundary. Record separate
  Delivery work; do not expand the current change.
- **Preference:** optional style or alternative-design advice. It never delays
  merging.

Only Blockers delay merge. After a Blocker fix, review only the fix and affected
invariants unless new evidence demonstrates that the original scope is unsafe.
Preferences, hypothetical risks, and unrelated hardening do not reopen review.

For an approval-governed Delivery change, freeze the implemented candidate head
before expensive verification. After cheap checks, obtain exact-head
zero-Blocker review, create fresh admission, complete required hosted baselines
and separate authoritative publication, then recheck semantic scope, approval,
cancellation, and exact head before merge.

## Abandoned pull requests

Only unmerged implementation pull requests are eligible for recovery. An
open-but-unusable pull request closes unmerged before a replacement opens.
Replacement requires reciprocal supersession links. Reopening creates no
authority.

Replacement or reopening requires a new decision version naming the live pull
request, new task-user approval, and fresh review, checks, admission, baselines,
publication, and receipt. No previous approval or evidence transfers. A merged
pull request is never recoverable; later correction is new Delivery work.
Recovery for the same capability does not turn it into a Tracking Epic.

## Process precedence and authority limits

Root `AGENTS.md` is canonical only for standing repository-development
procedure. For new, unapproved work, the proportional workflow supersedes only
its closed list of packaging and sequencing mechanics. OFARM law and accepted
technical, security, authority, custody, evidence-sufficiency, currentness,
runtime, deployment, and domain requirements remain binding. A stronger
accepted procedure for an exact action remains controlling. Ambiguity keeps the
older requirement in force until explicit amendment.

A new general standing process gate needs its own workflow-governance Delivery
issue and pull request, a demonstrated current failure or threat, a named
consumer, and an expiry or review point.

Repository approval, review, checks, admission, successful baselines,
publication, receipts, or merge do not authorize deployment, release,
current/default promotion, production access, or a security waiver. Before
deployment, the provisional task-message approval model must be replaced by an
independently human-controlled and independently verifiable approval or signing
system.

## Outcome measures

Evaluate delivery end to end rather than counting small pull requests as
progress. Useful measures are Delivery-issue open-to-close time, live and
abandoned implementation pull requests per capability, approval stops,
process-only pull requests, final-head baseline cycles, and time from zero
Blockers to merge.

The normal target is one live and one merged implementation pull request, one
approval stop for high-risk work, zero process-only companion pull requests,
and one successful implemented-head baseline cycle. The completed manual pilot
and its original evidence remain available in
[governance issue #218](https://github.com/samovers/OFARM2/issues/218) as
historical rationale, not an active reporting requirement.
