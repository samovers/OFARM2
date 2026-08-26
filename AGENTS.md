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

## Default change workflow

Use this workflow for ordinary tasks. Routine work does not require the full
design contract or an approval stop.

OFARM2 is pre-deployment development work. Prefer the best coherent design now
over preserving a temporary implementation. Do not defer a justified redesign,
rewrite, or refactor solely to avoid changing existing code; change is
comparatively cheap before production. It is not free: preserve accepted
contracts, evidence, explicit invariants, and stated boundaries, and verify
changes in proportion to their risk.

Before editing, state:

- the one problem being solved and the primary boundary being changed;
- falsifiable acceptance criteria or invariants;
- non-goals and adjacent systems that will not change;
- why the proposed change is the smallest coherent solution;
- the capability delivered, demonstrated risk reduced, or architectural
  decision validated;
- a provisional-design record only when the design is intentionally temporary,
  covering why it is acceptable before deployment, evidence that would require
  redesign, and the likely upgrade path; otherwise state `Not provisional`;
- the focused verification needed for the stated boundary.

Keep implementation, tests, documentation, and necessary mechanical
integration inside that boundary. If another boundary must change, stop before
editing it and propose a separate prerequisite, Follow-up, or stacked pull
request. Prefer deletion, direct code paths, explicit boundary contracts,
immutable values, and small modules over speculative abstractions,
compatibility shims, and duplicate validation.

Classify every review finding as exactly one of:

- **Blocker:** a demonstrated in-scope correctness, security, data-integrity,
  contractual, or production-safety failure. Name the violated invariant and
  the smallest acceptable fix.
- **Follow-up:** valid work outside the pull request boundary. Record it as a
  separate issue or future pull request; do not expand the current change.
- **Preference:** optional style or alternative-design advice. It never delays
  merging.

Only demonstrated Blockers delay a merge. Once the acceptance criteria pass
and no Blocker remains, merge the pull request. New ideas, Preferences, and
non-blocking hardening become Follow-ups and do not reopen review.

## Review-before-baseline sequencing (binding for agents)

Treat the full hosted conformance and native-verifier workflows as expensive
baselines. Do not start, monitor, diagnose, or rerun them for a pull-request
head until an exact-head content review reports zero Blockers.

Use this fail-closed sequence:

1. Every new pull-request head starts in `REVIEW_PENDING`, including a head
   produced only by documentation or review-fix commits.
2. While review is pending or reports a Blocker, run only mandatory and cheap
   local checks, push the correction, and obtain the next exact-head review.
   Automatically started expensive jobs may finish unattended, but an agent
   must not spend time monitoring, diagnosing, or retrying them.
3. A zero-Blocker exact-head content review must identify the full reviewed
   commit SHA. Do not treat the review as current after another commit, and do
   not infer currentness from an automatically running or previously green
   workflow.
4. After that review is complete, a repository owner, member, or collaborator
   may create one admission issue comment on the pull request. The comment must
   end with this exact footer:

   ```text
   OFARM2_BASELINE_ADMISSION
   head=<FULL_COMMIT_SHA>
   blockers=0
   ```

   The admission comment is a separate technical trigger, not the content
   review itself. Never edit it. The default-branch gate must verify live that
   the comment is created and unedited, its exact UTF-8 body digest is bound,
   its author still has repository standing, the pull request is open, the
   footer SHA equals the current head, and the execution merge commit binds the
   live base and head. Only then may it call the same-commit expensive executor.
5. A new commit, close/reopen transition, or deletion/edit of an admission
   comment revokes admitted work. A standing reviewer may also create this
   explicit exact-head revocation comment:

   ```text
   OFARM2_BASELINE_REVOCATION
   head=<FULL_COMMIT_SHA>
   ```

   Public or ordinary comments never share the executor's cancellation group.
   The dispatcher must run only trusted default-branch policy and must never
   check out pull-request code.
6. Present an approval card only after the exact same reviewed head has both the
   zero-Blocker review and every required hosted baseline result. Normal success
   artifact names may be published only after the substantive jobs and live
   admission proofs succeed. Jobs that execute pull-request code may upload only
   explicitly provisional artifacts. Their final fresh handoff job must run
   trusted policy only, reject every unexpected or pre-squatted artifact name,
   bind the exact source workflow/run/attempt and provisional artifact IDs and
   digests, and upload the immutable publication ticket last.
7. Established authoritative names belong only to the separate default-branch
   `workflow_run` publication workflow. Its fresh runners must never check out
   or execute the admitted merge or any downloaded content. They must resolve
   the exact successful source run and ticket by artifact ID, recheck live
   admission and revocation, and validate downloaded files as untrusted data
   with trusted policy code. Producer artifacts must be downloaded by exact ID,
   digest-checked before extraction, and extracted only by trusted policy into a
   fresh empty root that rejects traversal, links, special files, duplicates,
   and size excess. Exact file inventories are required both before and after
   trusted metadata is added. Git policy checks must ignore system and global
   configuration and disable hooks and filesystem monitors. The publisher must
   re-authenticate both architecture artifacts and derive the native index only
   from those re-authenticated artifacts. Artifact names alone are never
   authoritative. Authority requires a successful publication run plus its
   final receipt binding the source and publisher workflow refs, policy SHAs,
   run IDs/attempts, all four source artifact IDs/digests, and all five published
   evidence artifact IDs/digests. The receipt artifact must be uploaded last in
   that successful publisher run. A failed run that populated established names
   but did not seal that receipt is incomplete and untrusted. Until a repository
   consumer is added, this receipt is write-only evidence and external consumers
   must validate it before trusting an artifact. A main-branch post-merge source
   run is not a pull-request admission, has no live PR revocation to recheck, and
   remains automatic, but it uses the same separate publisher. Because the
   artifact API is not attempt-scoped, source and publisher workflow reruns fail
   closed; start a fresh reviewed and admitted source run instead.

Never create the admission comment while the content review has a remaining
Blocker. Do not use labels, earlier-head reviews, green results from another
SHA, or agent memory as substitutes for exact-head review. Until a technical
admission workflow is merged and active, this is an agent-enforced ordering
rule: existing automatic jobs may run unattended, but they do not authorize
monitoring, retries, an approval card, or merge. This sequencing rule controls
workflow timing only; it does not weaken any required verification or merge
gate.

An admission comment must be created with a user or GitHub App credential whose
event can start the default-branch gate; a comment created with the repository
`GITHUB_TOKEN` does not supply that trigger. A manual workflow run, a
formal-review event, and a pull-request-controlled workflow are not substitutes
for the live admission proof. Workflow admission also does not imply branch
protection. Verify repository settings before describing hosted baselines as a
GitHub-enforced merge requirement.

## Full design contract for high-risk trust-boundary work

The full Phase A design contract in `TASK_PROMPT.md` is required when a task
materially changes any of these areas:

- authentication, credential verification, principal resolution, or
  authorization;
- signing, key custody, or key authority;
- tenant isolation;
- database roles, transactions, migrations, or durability semantics;
- runtime integration, startup readiness, or security-audit behavior;
- irreversible data behavior.

If classification is unclear, treat the task as high-risk until the boundary
is explicitly narrowed.

OFARM2 is pre-deployment development work. Prefer the best coherent design now
over preserving a temporary implementation. Do not defer a justified redesign,
rewrite, or refactor solely to avoid changing existing code; change is
comparatively cheap before production. It is not free: preserve accepted
contracts, evidence, explicit invariants, and stated boundaries, and verify
changes in proportion to their risk.

For those tasks, inspect first and write a Phase A design contract before
editing. It must define the problem and non-goals, trust model, authority map,
state and ordering, stable falsifiable invariants, production-reachable
negative cases, smallest coherent architecture, pull request boundary,
invariant-to-code-to-test traceability, provisional-design record when
relevant, and open decisions. Wait for explicit approval before implementation.
If implementation invalidates the approved contract, stop and request an
amendment.

Review the exact head against the approved contract. A Blocker must name the
violated invariant, supported production entry point, in-scope actor, exact
execution or state-transition path, required preconditions, material
consequence, and minimal reproduction or counterexample. Do not invent a new
attacker model or use unrelated future scope to block the pull request. Perform
at most one unconstrained full review at an exact head; after a fix, review only
the fix and affected invariants unless new evidence demonstrates that the
original scope is unsafe.

## Pre-deployment AI-assisted decision workflow

Use this workflow prospectively for complete Phase A contracts while OFARM2 is
pre-deployment, unless an accepted contract explicitly requires a stronger
procedure for the exact action. Complete and review Phase A in one
already-created draft pull request before showing a decision card.

The complete live card must state the decision identity and version, problem,
recommended decision, primary trust boundary, authority map, primary risk and
bound, permitted effects, non-effects, decision-level invariants, maximum path
envelope, named draft pull request, verification gates, reapproval triggers,
provisional posture, and this exact approval form:

```text
I approve OFARM2 decision <DECISION_ID> version <VERSION>.
```

Approval is only the entire visible text of a later task-user message in the
same Codex task. Before recognizing it, verify that the original card and user
message remain directly retrievable with stable references and that the card
names the existing draft pull request. Generic approval, GitHub activity,
credentials, AI or tool messages, delegation, another task, or a summary of
lost original items never supplies approval.

Only the unique, most recent, unsuperseded complete card for a decision identity
and version is live. A replacement withdraws its predecessor; a semantic card
change requires a new version.

A valid approval binds only the card and named pull request. Within that pull
request, the AI may implement, test, document, regenerate mechanical evidence,
commit, push, address in-boundary Blockers, rerun checks, and merge after every
gate passes. The approved technical contract owns the exact implementation
allowlist and may narrow the card's maximum path envelope, but may never widen,
relax, or contradict it.

Before merge, mechanically reject every path outside the technical allowlist
and verify that allowlist is a subset of the card envelope. Post one compact PR
scope report naming the decision, card, approval, and PR references; changed
paths and both path checks; envelope-preservation determination; verification
and review results; and cancellation check. Recheck the exact head, live task
evidence, absence of later cancellation, required checks, and absence of a
demonstrated Blocker immediately before merge.

Stop for a new decision version when a material effect, trust boundary,
authority, invariant, path envelope, irreversible behavior, or named pull
request changes. Stop when the technical contract conflicts with the card, a
stronger rule applies, original task evidence is lost, or preservation is
ambiguous. Any later stop-like task-user message pauses immediately; closing
the named pull request unmerged expires authority.

This is provisional repository-development authority only. It never authorizes
deployment, release, current/default promotion, production access, or a
production security waiver, and it does not replace stronger accepted rules.
Before deployment it must be replaced by an independently human-controlled and
independently verifiable approval or signing system. The governing design is
`docs/rfcs/OFARM2_Predeployment_AI_Assisted_Development_Workflow_RFC_v0_1.md`.

## Review guard - Core neutrality

Treat these as Blocker findings in Core-facing material: country-specific identifiers, authority names, legal deadlines, evidence sources, currentness policies, or conformance fixtures being presented as universal OFARM law; profile examples becoming executable Core logic; or profile-local law leaking into Core, Kernel, Platform, runtime adapters, contracts, or generated manifests.

## Review guard - Netherlands GO + GLMC 7 slice

For `profile_nl_go_glmc7_2026/`, treat these as Blocker findings: country
law leaking into Core, Kernel, Platform, runtime adapters, or the SI profile; a
whole-Netherlands production claim; an automated 30-hectare GLMC 7 carve-out;
BAS, Ctgb, Bijlage Aa, manure-register, GLMC 4, or GLMC 10 scope creep; or any
promotion path that accepts public/current-state data alone as historical truth.
