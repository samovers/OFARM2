# Legacy review confirmation, version 0.2

Status: **proposed decision version 2; not approved** for existing draft
[PR #384](https://github.com/samovers/OFARM2/pull/384), Delivery
[#383](https://github.com/samovers/OFARM2/issues/383), under Tracking Epic #180.
Decision identity: `OFARM2-LEGACY-REVIEW-CONFIRMATION-001`.

This amendment proposes replacing the version-1 R04 guarantee and its proof
claims. It does not supply approval or merge authority. The original
[version-0.1 record](OFARM_Legacy_Review_Confirmation_RFC_v0_1.md), its user
approval and historical evidence remain unchanged. Its unqualified R04 is
refuted; PR384 remains blocked until a complete version-2 card is reviewed and
approved in a later exact task-user message, then implemented and verified.

## Problem and decision

K-03's confirmation correction is valid: present non-booleans must reject
before the legacy transaction, and only literal true supplies confirmation.
[Review 5178474311](https://github.com/samovers/OFARM2/pull/384#pullrequestreview-5178474311)
found a separate, pre-existing eligibility defect at base
`b6017da1dbfac80b5c2e98641aaa34d96691d087` and implementation
`f2a3930eab90037a21f8aa05c29f506a49037d6f`: an otherwise authorized and evidenced
compliance assertion with `confirmAccept: true` and `reviewerPartyRef: null`
can be accepted by its own asserter. The approved statement that true cannot
bypass disallowed existing self-review is therefore false at that head.

Recommend an explicit narrower guarantee for PR384 and separate reviewer
eligibility work, recorded in [Delivery #385](https://github.com/samovers/OFARM2/issues/385). PR384 remains one complete
capability: **strict optional boolean confirmation before governed legacy
ingress**. The primary trust boundary remains **legacy review-confirmation
admission**. This version proposes no additional runtime or test changes to
the existing K-03 implementation. It corrects the active design, explanatory
documentation and proof attribution without changing eligibility enforcement.

The proposed sequencing is explicit: after version-2 approval and fresh review,
admission, hosted evidence and final user acceptance, PR384 may merge before
the separate eligibility Delivery is complete. The nullable-reviewer defect
would remain in that repository state. This is the material tradeoff requiring
new semantic approval. A user who requires its removal before PR384 merges can
instead require the separately approved eligibility fix as a prerequisite;
that alternative must not be inferred from approval of this proposal.

This proposal does not permit compliance self-review, amend D8/D17 or accepted
OFARM review law, certify the legacy path as safe, authorize production access,
or waive a deployment requirement. It narrows the guarantee of this repository
change and makes the known implementation failure explicit. Existing production
governed routes remain closed. No claim of production readiness is made.

## Authority, threat and containment

| Owner | Authority retained |
| --- | --- |
| Canonical OFARM and accepted D8/D17 | Review meaning, eligible self-review classes and distinct-reviewer requirements |
| Existing transport | Authentication and actor binding, including 403 precedence |
| Existing ingress parser | Optional confirmation shape before transaction entry; no grant of review rights |
| Existing authority evaluator, validators and policies | Assertion/review/retirement rights, scope, evidence and eligibility; their complete correctness is not certified by this PR |
| Existing promotion gate and emitter | Confirmation consumption, named reviewer and server-time accountability; the null-reviewer defect remains separately owned |
| Existing Store | Transactions, persistence and raw-digest/replay ownership |
| Task user | Versioned semantic decision and later exact-head merge acceptance |
| Reviewers, CI, publisher and GitHub | Findings, mechanical verification, evidence custody and native PR state; no human authority |

Protected assets remain the draft/accepted distinction, accountable review
records, valid replay results and immutable history. Request bodies, confirmation
values, body-named reviewers and keys are untrusted, including from an otherwise
authorized party. Compromised in-process code, direct database writers, stolen
keys and database-owner compromise remain excluded attacker capabilities.

The corrected K-03 risk is mistaking arbitrary truthy data for confirmation.
One strict type admission before transaction entry is the load-bearing control
for supported callers. The function-local `is True` value gives the four
current consumers explicit common meaning, without adding another authority
path. The parser and gate do not jointly prove completeness of reviewer
eligibility. The residual risk is separately stated below, not hidden behind
the successful boolean tests or the closed production posture.

## Closed version-2 invariant set

| ID | Guarantee and falsifiable evidence |
| --- | --- |
| R01 | Omission and actual booleans are the only well-formed confirmation inputs on every commit class. Present null, strings, numbers, arrays and objects reject, including empty/zero values. Existing all-class parser and HTTP matrices verify it. No new required field, coercion or alias. |
| R02 | Malformed confirmation rejects before pipeline transaction entry, idempotency lookup, authority evaluation and governed writes, including an accepted-key replay. Preserve actor-binding 403 precedence and exact safe 422. No-transaction tests prove ordering; HTTP/Store snapshots prove no record changes for malformed fresh requests and accepted keys. |
| R03 | Valid non-confirming drafts and valid replay retain raw submissions, digests, records and ordering. Omitted/false are distinct inputs and can write existing pending records; literal-true confirmation does not normalize either. Existing digest/replay/history controls verify these outcomes. |
| R04 | Literal true supplies confirmation only; this change preserves existing authorization, evidence, retirement and review-routing code paths and their demonstrated controls, without certifying complete self-review eligibility. Missing REVIEW_ACCEPT, insufficient evidence, the existing omitted/self-named compliance controls, a distinct non-null reviewer string, and non-allow correction-retirement decisions remain non-acceptance controls. Eligible operation/structure positives and transport actor/server-time accountability remain covered. The present-null reviewer compliance bypass below is explicitly unresolved and is not covered by a universal self-review-safety guarantee. |
| R05 | Queued accept/reject/contest require no new confirmation field and retain existing action/outcome validation and authority behavior. Existing queued self-review refusals remain covered; no claim is made that direct and queued eligibility are fully consistent. |
| R06 | Historical record bytes, lineage, transaction ownership and closed production routes remain unchanged. No repair, rewriting or activation occurs. Existing history/correction/closure controls and a bounded diff check verify these non-effects. |

R01, R02, R03 and R06 retain their version-1 guarantees. R05's behavior is
unchanged; its final sentence makes the already excluded K-04 limit explicit.
R04 is a changed decision-level guarantee, not a wording-only correction. The
permitted integration sequence and known residual must appear prominently in
the complete same-task decision card and final packet.

## Known residual and separate Delivery

The reviewer reported real HTTP reproduction at both base and head using the
fictional demo fixture: omitted reviewer, self string and distinct string all
route for review, but present null produces `COMPLIANCE_STATUS_ACCEPTED` with
the asserter as reviewer. Queued self-acceptance refuses. The root agent checked
the exact source path and unchanged base/head conditions; it did not claim a
second HTTP reproduction of this review finding.

The path is specific: `sub.get("reviewerPartyRef", ctx.acting_party)` returns
None for a present null, so the compliance self-review comparison is false.
The distinct-reviewer predicate separately treats None as non-distinct. With
otherwise sufficient evidence, assertion authority and REVIEW_ACCEPT, no
review-routing reason is added and the direct branch emits self-acceptance.
This is a reachable accepted compliance consequence, not just an inaccurate
label or a missing log. It remains a defect under existing D8.

[Delivery #385](https://github.com/samovers/OFARM2/issues/385) owns the independently testable capability of preventing this
null-dependent compliance self-acceptance while preserving ordinary permitted
review behavior. Its primary boundary is **self-review eligibility enforcement**.
It must have its own high-risk design, exact semantic approval, implementation
PR and evidence before any fix is made. It does not inherit approval from
PR384. The issue must trace back to this review and forward from PR384.

That Delivery should cover direct/HTTP null, omitted, self and distinct reviewer
cases, queue consistency, authorized distinct acceptance, routine-operation
compatibility and unchanged history. It need not solve all K-04, add generic
reviewer typing, change authority grants or create an eligibility framework.
Neither adding a new reviewer type rule nor changing the null interpretation
belongs in this PR solely because it shares `kernel/stages.py`.

Do not add a permanent compatibility test that requires wrongful acceptance to
continue. Historical failure evidence identifies the residual; the separate
fix needs a negative regression that stops acceptance. Removing the defect in
its own Delivery is not a regression of PR384's guarantee.

## Smallest complete change and verification

Expected version-2 areas are this amendment and, after approval, the active
confirmation paragraph/link in `docs/REVIEW_DISPUTE_SEMANTICS.md`, PR/Delivery
metadata and the final evidence packet. Retain the original version-1 record
as history. Preserve runtime, tests and the 4475-entry inventory byte for byte
unless new demonstrated evidence requires an in-boundary change under the
existing approval rules. This plan adds no schema, migration, authority,
context field, stored state, fallback, gate or runtime abstraction.

EXC-001: existing parser and gate remain the sole confirmation path.
EXC-002: no duplicate validation, state or authority is introduced.
EXC-003: the corrected invariant set names its actual proof and known limit.
EXC-004: the earlier four truthiness reads remain removed; superseded public
readiness and universal safety claims must not remain active after approval.
EXC-005: no new runtime or test abstraction is proposed.
EXC-006: the simplest credible alternative is a separate eligibility prerequisite
while retaining unqualified R04. This proposal keeps the confirmed K-03 remedy
independently reviewable and exposes the residual explicitly. Combining the
eligibility fix adds an independently owned allow/deny decision and is not
necessary. No cross-boundary exception is requested.

P1 is non-blocking: over inputs admitted by the strict parser, truthiness and
`is True` have equivalent results. The latter is deliberate clarity; the
current tests do not independently pin it against a gate-only mutation.
Do not invoke a private transaction method with parser-invalid input as proof
of a supported entry-point guarantee. P2 is non-blocking: the stub's zero-lookup
and zero-authority assertions are consequences of no transaction entry, not
independent exercised controls. The real Store matrix supplies effect/replay
proof. Correct that attribution in active descriptions after approval.

Before each commit, run the mandatory package/architecture check and appropriate
cheap whitespace/changed-document checks. A proposed-design-only head receives
bounded Phase A review of this amendment and B1's disposition; it is not admitted
for expensive baselines. After exact version-2 approval, update active claims,
verify their correspondence with this contract, confirm unchanged runtime/test/
inventory hashes, and obtain a bounded exact-head review of the correction and
affected R04/proof claims. Do not restart the audit or a full unconstrained
content review.

A new final candidate still requires fresh unedited admission, two complete
hosted baselines, native/platform checks, trusted publication and verified
receipt under existing policy. Never rerun the old workflow attempts, remove
the old revocation, or reuse old evidence as the new head's admission. Only then
present a new complete exact-head final packet and yield for the later user
merge authorization.

Historical results remain historical: version1 passed162 local tests,243 hosted
lightweight tests,4475 tests twice with equivalence,23 platform tests and both
native architectures. Those executions missed B1. Their receipt/admission is
revoked for current use. Reviewer-reported112 focused and48 compatibility passes
used PG16.13 with incomplete dependency availability, not the prescribed Linux
baseline. No current claim of full eligibility correctness follows from either.
Extraction FAIL(2) remains disclosed under the existing applicability analysis;
this amendment does not waive it or modify extraction inventory/status records.

## Non-effects, provisional posture and approval

No canonical/reference/frozen-contract, credential/principal, grant/action,
signing/custody, database-role, transaction-ownership, audit/publication mechanism,
production activation, deployment, release or historical repair change is
proposed. No new reviewer shape contract, self-review eligibility fix, broad K-04,
plain subject validation, or #180/#184 lifecycle/graph work is implemented here.

The boolean input rule is intended to endure. The legacy development/conformance
surface and this proposed sequencing remain provisional before deployment. A
new confirmation contract, unsupported entry-path discovery, capability or
boundary expansion, changed owner/effect/non-effect/invariant, irreversible
behavior, different named PR or production posture needs a new decision version.
New evidence that contradicts the narrowed guarantee reopens the affected
invariant; preferences do not. Eliminating the separately recorded defect under
its own approval does not require preserving the defective behavior.

Only the entire visible text of a later task-user message in the same task may
approve the complete live card for this existing PR:

```text
I approve OFARM2 decision OFARM2-LEGACY-REVIEW-CONFIRMATION-001 version 2.
```

Next: review this proposed amendment to zero design Blockers, present the
complete version-2 card and obtain that later exact approval before activating
its changed guarantee. Version1 approval and a generic continuation do not
approve version2, and semantic approval never authorizes merge.
