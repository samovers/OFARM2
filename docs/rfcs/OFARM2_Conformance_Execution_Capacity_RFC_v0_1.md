# OFARM2 Conformance Execution Capacity RFC v0.1

**Status:** Version 1 implementation retained; version 2 consumer evidence amendment proposed, not approved. PR #411 is draft pending amendment review and the later user decision. CI activation and merge remain separate.
**Delivery:** [#410](https://github.com/samovers/OFARM2/issues/410), child of #167.
**PR:** [#411](https://github.com/samovers/OFARM2/pull/411), the single live implementation PR for Delivery #410.
**Decision:** `OFARM2-CONFORMANCE-EXECUTION-CAPACITY-001`, approved version `1`; proposed version `2` below.
**Primary boundary:** trusted CI execution-resource policy/currentness.
**Design path:** `docs/rfcs/OFARM2_Conformance_Execution_Capacity_RFC_v0_1.md`.

Sections 1–7 retain the approved version-1 design and its original evidence
route. Section 8 proposes the only changes to that route. It has no effect
until a complete version-2 card is reviewed and later approved by the task user.

## 1. Problem and confirmed evidence

The complete conformance job runs two unfiltered Kernel baselines, compares
their evidence, preserves the platform lane, and uploads provisional evidence.
Its existing finite 45-minute job allowance can expire before this completes.
[Source 38716305726](https://github.com/samovers/OFARM2/actions/runs/38716305726)
and [fresh source 38722919197](https://github.com/samovers/OFARM2/actions/runs/38722919197),
both attempt 1 at PR409 head `75d881159c4fe353fecc0cbbf3abb32309353926`,
were cancelled with GitHub's exact 45-minute job-limit annotation. Their first
pytest runs each passed 5,322 tests with one expected warning in 1,399.00 and
1,372.68 seconds respectively. Both repeat runs were cut off; equivalence and
the platform evidence lane did not complete, and publication handoff was skipped.
Both native architectures passed in each source. Neither source has complete
authenticated publication; these partial results cannot replace required gates.
Further identical attempts are stopped. This design does not authorize one.

Earlier unchanged test prefixes were substantially slower than
[successful main source 38698001002](https://github.com/samovers/OFARM2/actions/runs/38698001002).
The new 58-case runtime suite fits within a 44.9-second enclosing hosted window.
No sufficient fixture saving preserving coverage and isolation was demonstrated.
These observations support a capacity diagnosis, not proof of its root cause.

## 2. Capability and approved decision

Permit the existing conformance executor up to 60 minutes, retaining a finite
ceiling, the complete test/evidence contract, and all current authorities.
Observed throughput projects approximately 49–50 minutes for the job; 60 offers
margin, not a completion or production-readiness guarantee.
Maximum additional cost is 15 runner-minutes per affected job, a 33% ceiling
increase, with longer residence of its existing disposable database services.
No additional job, runner, parallel workload, retry, or production resource
is created. This is a separate prerequisite, not a PR409 transaction fix.

## 3. Scope: two implementation paths and one design record

1. `.github/workflows/conformance.yml`: change only
   `jobs.conformance.timeout-minutes` from `45` to `60`.
2. `deployment/postgresql/ofarm_ed25519/native_evidence_verification_currentness.json`:
   regenerate through the existing offline generator after the workflow edit;
   update only the workflow entry's SHA-256 and the aggregate authority-manifest
   digest. Byte length stays unchanged because `45` and `60` have equal length.
3. This RFC records the same-boundary decision and rationale.
   It adds no executable authority and does not expand the two-file implementation.

The full workflow belongs to `EVIDENCE_AUTHORITY_PATHS`; an unrefreshed sidecar
must refuse. Preserve all other authority entries and frozen receipt/identity
links. The [accepted currentness contract, §12](OFARM_Native_Evidence_GitHub_CLI_Pin_Execution_RFC_v0_2.md#12-provisional-design-record)
permits reviewed verifier changes to refresh only this sidecar; frozen release
evidence is not rewritten.
No exact-45 assertion/document claim requires another companion edit.

## 4. Authority, trust, effects, and non-effects

The task user owns semantic scope, any required approval, and final acceptance.
Trusted default-branch policy owns admission, cancellation, execution budget,
and evidence acceptance. The checked sidecar binds current verifier bytes.
Untrusted PR code and provisional artifacts confer no dispatch or publication
authority. CI supplies mechanical evidence; the independent publisher retains
custody; GitHub retains native merge; existing runtime owners remain unchanged.
Protected assets are finite runner resources and honest current evidence.
Trusted inputs are reviewed policy and exact checked bindings; PR source and
producer artifacts remain untrusted. Compromise of the user, trusted policy
repository, or GitHub control plane is outside this bounded threat model.
Primary risks are prolonged resource use and blessing unrelated verifier bytes;
containment is the finite ceiling, exact scope/hash checks, and existing gates.

Preserve admission/revocation, default-branch dispatch, two full clean runs,
equivalence, every test/SQL/signing deadline, dependency/image/action pins,
source and artifact limits, both native architectures, publication receipts,
and final human merge authorization. Gate 5m, handoff 10m, native 120m, and the
separate publisher's 45m remain unchanged. No runtime, tenant, migration,
release, deployment, credentials, verifier logic, or evidence-policy change.
Do not reuse partial results from a cancelled source.

## 5. Invariants and reachable negative cases

| Invariant | CI-reachable negative case and required evidence |
| --- | --- |
| Only the conformance ceiling increases, and remains 60m | Another timeout, retry, runner, or unbounded job appears: exact scope/value review rejects it. |
| Currentness is exact under its existing contract | Stale/extra authority entry or wrong frozen binding: currentness negative controls refuse. |
| Complete verification still precedes publication | Failed/timed-out run, filtered inventory, or failed comparison cannot produce accepted complete evidence. |
| Untrusted code gains no authority | Candidate workflow bytes cannot change their own active budget because trusted default-branch dispatch controls it; forged admission/artifacts refuse. |
| Other behavior and retained evidence stay identical | Unrelated code, test, inventory, pin, or frozen artifact changes fail scope/hash verification. |

## 6. Verification, bootstrap, and delivery

Cheap checks: exact three-path diff with only two executable/data changes;
whitespace; mandatory package check before commit; offline currentness
generation/validation and frozen-hash preservation; existing admission
`WorkflowPolicyTests`; focused currentness, transitive-policy and workflow
authentication controls in `kernel/tests/test_postgresql_native_evidence.py`.
Use existing meaningful controls; no mirror test or test inventory change.
Then exact-head zero-Blocker review, fresh admission, required hosted evidence
and publication, final packet, and later exact-head human merge authorization.
Delivery #410 uses the approval-governed path because this scope relies on the
checked currentness authority. The [Protocol](../development/DELIVERY_PROTOCOL.md#before-implementation)
excludes authority-dependent work from its routine carve-out and treats unclear
classification as high-risk until narrowed. This is its application to this
scope, not a literal rule requiring approval for every numeric CI change.
Review Phase A before presenting this decision's complete card naming the actual
draft PR. This RFC is not that card and grants no implementation or merge authority.

The dispatcher executes trusted default-branch policy: the capacity PR still
receives 45 minutes before merge. Its candidate bytes cannot increase its own
allowance. If its required gates cannot pass, report that bootstrap constraint;
no partial evidence, main-branch direct write, or merge bypass is authorized.
After authorized merge, PR409 needs fresh live-base/policy admission and a
complete source/publication chain. Keep PR409's separate semantic scope intact.

## 7. Simplicity, alternatives, and review point

EXC-001: retain one executor, one budget value, and one currentness path.
EXC-002: add no cache, duplicate state, registry, or alternative evidence path.
EXC-003: trace the timeout failure to the budget and scope/currentness checks.
EXC-004: replace the owned 45m value; introduce no compatibility or fallback path.
EXC-005: add no abstraction or framework; use the existing generator/validator.
EXC-006: the simpler unchanged-45m fresh attempt has now also timed out. Another
identical attempt has no new support. Removing coverage, sharing mutable fixtures,
sharding, or changing deadlines requires more change than this finite increase.

Sizing is provisional. Review measured completion and resource use after the
first complete PR409 source under any later authorized policy. Further timeout
or a need to alter verification/authority calls for a new scoped diagnosis,
not an automatic increase. This review point adds no gate or scheduled work.
The existing currentness model and retained release evidence stay unchanged.

A new decision version/approval is required for changed capability, boundary,
authority, permitted effects/non-effects, invariants, named PR, irreversible
behavior, or deployment posture; uncertain preservation also stops work.
Next: complete focused checks, exact-head implementation review, required hosted
evidence and publication, then present the final packet for separate human merge
authorization. This decision does not authorize merge or deployment.

## 8. Proposed consumer evidence amendment, version 2

### Recommendation, problem and capability

Make this same PR #411 eligible for complete pre-merge acceptance through the
separately approved [PR #417](https://github.com/samovers/OFARM2/pull/417)
version-4 transition, subject to a later, separate exact-root grant. Retain the
approved finite 60-minute conformance ceiling and its mechanical currentness
refresh. This amendment changes the permitted consumer evidence route only.
It adds no transition implementation to #411.

PR411 source [38734136285](https://github.com/samovers/OFARM2/actions/runs/38734136285)
passed its first 5,207-case baseline but exhausted 45 minutes during the repeat.
Source [38740690045](https://github.com/samovers/OFARM2/actions/runs/38740690045)
failed the existing test-owned password-rejection proxy before the time limit.
Both native architectures passed in both sources; neither source completed
accepted publication. These partial results cannot transfer to a fresh use.

The separate proxy repair [PR #413](https://github.com/samovers/OFARM2/pull/413)
merged as `73647ddb0037188f723c806f3689e617eec77630` after complete transition
acceptance and separate native merge authorization. Its grant
`pr413-20261018-490994e8c63b6b8d` is retired and its evidence archived.
Neither its successful runs nor its unused authority can transfer to #411.
This candidate is refreshed onto that main; the 53 added proxy controls come
from main, not a new capacity implementation or an inventory reduction.

The original version-1 card and approval were retrieved directly from chat
`01a0aab4-3ce9-7540-abf2-41bc78b859b3`: card
`msg_0a76f8c31f710916016ad0bea2c66887d2a78f152bd7b4d8f3` at
15 October 2026 11:53:18 UTC, then original user message
`msg_01a13f74-f7ae-7030-9ba3-367291fb6a0b` at 12:06:32 UTC.
The raw original text hashes match the retained approval record; the earlier
record used a different normalized user-message identifier. These references
are navigation, not approval. Version 1 explicitly required this PR's own
checks under main's 45-minute policy. It does not authorize this amendment;
the later version-2 decision must explicitly replace that requirement.

### Boundary, authority and exact replacement

The primary boundary remains **trusted CI execution-resource policy/currentness**.
PR411 owns the permanent budget and existing currentness record. PR417 alone
owns CI evidence policy selection, bounded use, revocation and recognition.
PR413's test transport repair is already on main. No runtime, tenant/database,
signing/key custody, credential, audit, release or deployment change joins #411.

The task user owns semantic approval, each exact-root grant, cancellation,
final acceptance and later exact-head merge authorization. The existing
executor owns the budget; the existing generator and validator own currentness.
The isolated operator retrieves original authority and maintains the external
single-writer journal. The selected root enforces admission and revocation;
CI produces mechanical evidence; the separate publisher owns evidence custody;
the external verifier authenticates the complete chain against the independently
selected root. Reviewers assess content, not human approval. GitHub retains
native merge. Candidate code, comments and artifacts cannot select their policy.

For PR411 alone, after version-2 approval and a separate valid exact-root grant,
replace three provenance requirements: default-main admission and same-main
policy selection; the default-main `workflow_run` publisher; and ordinary
receipt recognition. Their sole replacement is #417 v4's created transition
admission, externally selected reviewed T1, a real push source, a separate push
publisher at the same T1, distinct transition receipt and isolated external
verification. This permits the finite 60-minute conformance route before #411
merges. The candidate cannot authorize its own budget. Ordinary main policy
and ordinary receipts stay unchanged; no other PR acquires consumer permission.

### Risks, invariants and limits

The capacity risk remains up to 15 extra configured runner-minutes per affected
job and endorsing unrelated verifier bytes. Preserve the single scalar change,
the two generated hash fields, the other five authority entries and the frozen
receipt/release-identity bytes. Sixty minutes remains provisional, not a pass
guarantee. Every test/SQL/signing deadline, substantive validator, inventory,
dependency/image/action pin and unrelated job budget remains mandatory.

The additional risk is relying on reviewed but unmerged T1 before PR417's own
complete hosted acceptance. The proposed decision knowingly accepts only that
temporary bootstrap reliance, bounded by local controls, exact-head review,
independent root selection, one-use grants and fresh live verification. Shared
account identity, operator/credential/workspace custody and delegated journal
custody remain provisional limitations. An AI COMMENT is not independent human
approval. T1's private gh relay performs upstream TLS authentication and handles
forwarded credentials transiently; pinned configuration, isolation and cleanup
remain required. Revocation detection can take 135 seconds plus provider
cancellation latency; decisive stages must recheck live state.

Use #417's fixed version-4 operation coverage. Protected Python policy/evidence
reads, trusted Node/Git after bootstrap, four curl executions and five gh phases
retain first-403/429 and GraphQL-error refusal and complete protected accounting.
Existing recovery, fallback and valid content received under an error status
may succeed only in the enumerated provider setup/control/reporting, archive
installer/pip bootstrap and four canonical pip installs, Docker/Buildx/BuildKit
image/ADD/fallback, and pinned-scanner paths, with their original final checks.
Provider activity before observation is part of the disclosed exception. Bad or
incomplete content and failed final checks still fail. Candidate/unrelated
traffic is untrusted ambient activity. The 990 REST / 430 GraphQL-point envelope
is protected-operation planning with margin, not an all-traffic ceiling, quota
reservation or universal throttle guarantee. Unknown ambient use is not zero.
The immutable coverage declaration must bind T1 through receipt acceptance.

Any later grant must freeze full T1/tree/closure/coverage, reviewed PR411 head H,
current base B and execution merge M/parents, reviews, operator, unique grant ID,
exact source/publisher refs, external verifier, external journal/checkpoint
locations and format, immutable genesis hash and concrete creation/expiry times.
Its tail advances monotonically. Allow at most one source and one publisher,
both attempt 1; expiry is within 24 hours and no later than the unchanged
campaign sunset, **24 October 2026 00:00 UTC**. No renewal, automatic retry,
reuse of partial evidence or transfer from an earlier grant. Expiry, revocation,
head/base/history drift, missing authority, uncertain state, any required test
or validation failure, or incomplete protected-tool cleanup refuses use.

### Verification, sequence and reapproval

Before use require the complete refreshed PR411, mandatory and focused local
checks, fresh exact-head zero-Blocker content and amendment design reviews,
and the later complete version-2 card and user approval. Require PR417's current
root checks and exact-head review, followed by a separately prepared concrete
packet and later original exact-root user grant. Every new commit needs fresh
review. This proposal supplies no grant, admission, timestamped slot or CI trigger.

The required source must run two complete unfiltered baselines sequentially on
the same runner and actual database clusters/system IDs, the unchanged fixed
comparison, all 23 platform cases and both complete native architectures.
Require the complete successful source, guarded handoff, separate successful
publisher, exact authenticated artifact inventories and receipt last, external
verification, and current unrevoked authority. No filtering, test retry, relaxed
assertion, partial acceptance, main write, protection change or merge bypass.
Only then present the final packet and await separate exact-head native merge
authorization. Semantic approval and a root grant never authorize merge.

After separately authorized #411 merge, retire the bootstrap, rebase #417 onto
main60, remove its active activation/issuance paths while retaining historical
audit, and require #417's own complete ordinary acceptance before its merge.
PR409 then needs its own fresh admission and complete verification; neither
this amendment nor #413's results supply it.

EXC-001–006 remain satisfied: one permanent executor/currentness owner; consume
the separately owned temporary route without copying its logic; trace the
bootstrap failure to exact provenance and unchanged substantive validators;
retire the temporary route after use; add no abstraction or fallback. The simpler
unchanged-45-minute attempt already failed. Partial-evidence merge is excluded
by the retained acceptance invariant. No cross-boundary implementation is added.

Review actual sizing after the first complete PR409 run under later authorized
policy; no automatic increase or schedule is created. Before deployment replace
the shared-account approval arrangement with independently human-controlled,
verifiable approval/signing. Changed capability, boundary, authority, effects,
invariants, irreversible behavior, named PR or deployment posture requires a
new version and approval. Changed execution coordinates require fresh checks,
review/evidence and a new exact-root grant, never an inherited grant or sunset.

Next: obtain focused review of this proposed amendment and refreshed head, then
present the complete version-2 decision card for the user's later approval.
CI activation and merge remain separate and unapproved.
