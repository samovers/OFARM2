# Installation and retirement runbook — proposed v1

This runbook is part of the proposed, unapproved [Phase A](OFARM2_CI_Policy_Transition_RFC_v0_1.md) for [Delivery #416](https://github.com/samovers/OFARM2/issues/416). It contains future operations, not commands to execute now. No policy SHA, grant, deadline or approval is implied by an example. `P` denotes this Delivery's sole draft implementation PR, linked from the Delivery issue. The publication steps below record the required order; their completion does not authorize implementation or activation.

## 1. Publish a reviewable proposal, then approve its meaning

1. Create one Delivery issue and one draft P for **temporary CI evidence policy transition for #411** after publication is authorized. Use the prepared issue/PR text. Link #410/#411 and the #412/#413 prerequisite. Put Phase A in P and the durable versioned RFC in the same P. Do not create a contract-only prerequisite PR.
2. Complete independent design review of the actual Phase A to zero Blockers. Present the complete P decision card naming the actual draft PR, this boundary, all new authority, the selected order and the temporary reliance before P's own hosted acceptance. Only a later prescribed same-task decision approval authorizes implementation.
3. Prepare complete versioned amendments for #413 and #411's permitted CI evidence route. Original cards and later approvals must be retrieved directly. Do not change their substantive repair/resource scope. Obtain the respective new approvals before their transition use. P's approval cannot substitute for either.

## 2. Build and freeze the root without starting expensive work

1. Re-read current main, actual PR heads/states and applicable instructions. Check Actions is enabled and the existing authorized operator credential can push workflow-bearing non-main refs and create required PR comments. Check branch protection/rulesets/branch rules and organization restrictions. Do not change settings or provision a new credential under this runbook. If access is unavailable, stop and report the exact missing permission.
2. Create/reuse an isolated worktree based on current main B. Use an ordinary preparation branch excluded from both activation filters. Implement the complete transition capability, including the real external verifier, grant journal, generation/parity checker and focused tests. No candidate or producer receives the operator's credential.
3. Preserve the normal workflows and substantive validators relative to B. Generate the transition workflows with the closed rewrite set. Use canonical producer and publication operations; commit their output for review. Pin the repository numeric ID/full name, one operator stable GitHub account ID, fixed consumer PR and maximum transition sunset into the root; each later grant has a shorter concrete deadline. Preserve all original tests and add the new transition tests to the complete inventory using the existing maintenance mechanism.
4. Run the mandatory package check before each commit and all cheap checks listed in the design. Use complete positive fixtures for all substantive paths and targeted negative cases. Prove ordinary main admission/publication still reject transition events and preserve their accepted tests. Do not request expensive runs while review is pending.
5. Freeze T and its full tree. Record B, each changed path/mode/digest, every executable/imported dependency, input workflow blobs, generated workflow hashes, allowed rewrites, test inventory and review/check results. The root closure is a dependency report plus exact-tree verification, not a mutable allowlist supplied by candidate artifacts.
6. Obtain exact-head independent content review with zero Blockers. Any new commit invalidates that review. A necessary different trust boundary stops before editing it.

## 3. Present the exact-root activation packet

The user must be able to inspect these concrete fields before selecting T:

| Field | Required value |
| --- | --- |
| Decision | P's live decision version, original card and same-task approval; consumer's amended decision/card/approval |
| Root | Full T, tree, closure digest, B; actual workflow paths/names and their hashes |
| Consumer | Exactly #413 for first use; later a new grant for exactly #411; each actual H, base B, execution merge M and exact parents |
| Review | Exact T review/checks and exact consumer H review/checks, all zero Blockers |
| Limits | One source and one publisher, attempt1 only; conformance60 and unchanged other substantive ceilings; binding/guard/seal overhead as designed |
| Time | Fixed created/not-before/expiry UTC values, expiry at most24h; root-wide sunset at most7 days after first activation |
| Identity | One unique grant ID; the operator account ID already pinned in T; source and publisher refs; fixed consumer concurrency group; repository and policy paths |
| Provenance | Isolated external verifier bytes/root; journal path, format and immutable genesis hash (subsequent hash-chained appends change the tail); original-message stable references |
| Reliance | T has focused checks/review, not P's own complete hosted acceptance; no #413/#411 result validates absent P tests |
| Writes | Non-main activation pushes, created unedited admission/binding records, bounded cancellation on revocation, provisional and authoritative artifact publication under the new schema |
| Exclusions | No automatic renewal, retry, other PR, merge, deployment, direct-main write, protection change or secret provisioning |

The future grant wording should identify the packet digest and full T, one consumer H/B/M, expiry and both one-use slots, while explicitly reserving merge. It is an exact-root activation approval under P's semantic decision, not a substitute for the protocol's decision or final merge forms. Do not present an approval sentence filled with placeholders as a live request.

Before the final packet is approved, create a journal genesis containing only the prospective grant ID, technical coordinates and format; the packet pins that genesis digest. Append the actual later approval reference afterward, avoiding a genesis/grant digest cycle. The operator then retrieves the original card and later approval/grant in order. It checks cancellation and conflicting later instructions. Save the immutable grant and its machine projection outside candidate trees. Original task-user evidence remains authority; the public projection is only a technical input. No root or GitHub comment can certify a missing original message.

## 4. Activate exactly one source at T

1. Hold the single-writer journal lock. Require this new grant is APPROVED and both refs are absent. Re-fetch main, candidate PR, its lifecycle/head history, execution merge parents, T/tree/closure, reviews, user instructions and settings. Any drift refuses before a write.
2. Create one transition admission comment on the consumer PR with the reviewed coordinates and distinct marker. Record its returned immutable ID, exact UTF-8 body digest and metadata, then re-read it. This marker must not end in the ordinary admission footer. Ambiguous write outcome is reconciled by exact digest/identity; never create a second admission to make uncertainty disappear.
3. Save `SOURCE_RESERVED` intent before pushing. Push exact T to the absent source activation ref. An empty-ref lease is required: conceptually `git push --force-with-lease=<exact-source-ref>: origin <full-T>:<exact-source-ref>`. This lease asserts absence; it is never changed to overwrite an existing ref. No `--force`, wildcard refspec or main target is allowed. The actual prepared command must use shell-safe explicit validated values and be reviewed as part of activation.
4. Observe the newly created run using its exact repository, ref, T, workflow path/name and push event. Do not select by latest success. Require one matching candidate run, actual workflow SHA T, expected created-ref event and attempt1, repository numeric ID, and provider-authenticated sender/run/triggering actor IDs equal to the operator pinned in T. If no unique matching run is available within the bounded gate window, stop; a refused gate is a consumed attempt, not permission to rerun.
5. Permanently save that run ID/attempt in the journal before creating its one source binding comment. The trusted gate waits no more than5 minutes for the created, unedited binding. The comment includes grant, root, consumer tuple, admission ID/digest and actual source identity. Re-read and bind its ID/digest. Persist each journal append and its independently retained tail checkpoint before treating the write as complete. A delayed response is reconciled to this identity; never rebind to another run.
6. The gate independently validates all technical facts and complete comment/history reads. It must refuse absence, ambiguity, duplicate binding, edited/minimized/deleted records, standing loss, ref drift, expiry or mismatched coordinates. The gate also verifies all admission/binding authors against the stable operator ID pinned in T; a standing collaborator or self-named projection cannot activate it. Only its success releases the expensive producers and isolated guard.

The first expensive job therefore starts from an unmerged but externally selected root. It does not require a file on main, a main-only dispatch, a successful old45-minute run, a native bypass or a prior merge of P. This is the actual installation path; all prior steps remain explicit gates.

## 5. Execute all evidence, then obtain the immutable handoff

1. Run both complete baselines sequentially on the same actual runner/clusters; compare with the original policy; run the23-case platform lane; finish both complete native lanes. No selection filters, missing cases, altered assertions, timing relaxations, retry success, partial evidence or data copied from an older source may pass.
2. Guard polls trusted live facts at most15 seconds apart while all expected producer jobs run. It never imports candidate code. If authority is revoked or state cannot be authenticated, fail and cancel its own run. Missing cancellation permission is itself a refusal. The guard's failure prevents handoff even if cancellation delivery is delayed.
3. After all producers and the guard succeed, start a fresh T-only handoff. Revalidate at start and preupload. Require the exact three provisional artifacts by identity/digest and complete inventory. Upload the versioned transition ticket last. No guard or diagnostic artifact may pollute the source inventory.
4. Independently observe success of the entire exact source run, attempt1, all expected jobs and ticket. A successful individual baseline/native job is not a successful source. Save `SOURCE_PASSED` with exact ticket ID/digest in the journal only after all checks pass.

On any failure, preserve honest results and refuse publication. Do not trigger the publisher or retry a source automatically. Diagnose from the admitted run as permitted; new code requires fresh review, and any fresh execution requires a new user root grant. A real new runtime or fixture defect is separate work.

## 6. Activate and seal a separate publisher

1. Require source success, the exact ticket, live grant/admission, an unused publisher slot and an absent publisher ref. Re-fetch original source identity and artifact inventory. Save `PUBLISHER_RESERVED` before pushing T to the publisher ref with the same absent-ref lease rule.
2. Observe the actual distinct publisher push run at T, attempt1, and bind exactly that ID before creating its immutable publisher binding record. It also names the successful source run/attempt and ticket ID/digest. The publisher gate has the same bounded, unique binding rules. A producer cannot provide the trigger credential or choose the publisher.
3. The publisher uses fresh T-only runners. Download by ID; authenticate digests before safe extraction; keep strict file inventories; independently run all substantive baseline/platform/source/native validations; publish the five existing evidence artifacts and derive the native index from re-authenticated published native inputs. No candidate executable, helper, configuration override or downloaded code runs here.
4. The isolated publisher guard waits for terminal successful validation and rechecks live facts. Only then can a fresh seal job proceed. It independently re-fetches source, grant/bindings and all five published IDs/digests and creates the distinct transition receipt. Upload it last. Record actual receipt ID/digest only after the publisher run itself succeeds.
5. Save `SEALED`. A publisher timeout, failed guard, extra artifact, missing receipt or success names without a successful sealed run is incomplete evidence. No rerun/second binding or new source substitution is allowed under the same grant.

## 7. Independently verify, then use normal human/native merge

1. In an isolated checkout of approved T, run the external verifier with T/closure and grant supplied independently of the downloaded receipt. Authenticate the entire provider chain, exact archived bytes, all substantive validators, current live state and journal tuple. Re-retrieve and check original task-user approval/grant separately. Refuse if either mechanical or human-authority validation is unavailable.
2. Record one accepted tuple in the journal. Produce the consumer's full normal final packet with boundaries, changes, decisions, checks/review, all evidence, receipt, new bootstrap reliance, EXC-001–006 and unresolved findings. Describe transition provenance truthfully; do not claim ordinary-main admission.
3. End the turn. Wait for the protocol's later exact-head merge authorization. Semantic approval, root selection and complete evidence alone do not authorize merge.
4. Immediately before merge, verify the original final packet and later authorization; PR open/non-draft/H, unchanged base/merge/lifecycle, scope, no Blockers, user cancellation, current grant/admission/receipt/journal and native settings. Never accept an expired grant for a new acceptance/merge. Use only normal native PR merge with expected H. A native rejection stops; do not try an alternate writer.
5. Verify the merge, record the consumed/retired grant and preserve verified Git bundles for exact T/T1 and dependencies (re-fetch into an empty repository and check expected commit/tree), raw downloaded archives with complete digest inventory, receipt/ticket, provider snapshots and original authority references outside candidate workspaces. Later historical audit must report unavailable provider facts honestly; it cannot create a new live acceptance. Retire source/publisher refs only after live acceptance checks finish; retaining a ref creates no authority. Never delete runs or artifacts as cleanup.

## 8. Repeat only for the newly approved #411 coordinates

After #413 merges, the base has changed. Retire the first grant. Rebase P onto new main; regenerate and review T1, preserving the same semantic boundary. Refresh #411 with the merged prerequisite and its separately approved evidence amendment. Complete its mandatory/cheap checks and exact-head review. Present a new concrete root packet for #411, not an extension of #413's grant. Then perform steps3–7 once for #411 with all new coordinates.

T1 must retain the original campaign sunset; a fresh root/grant does not restart the seven-day maximum. The unchanged currentness/validator dependencies must still match the new trusted base. If another actor changes main, the frozen tuple becomes stale and the operation stops. Updates cannot silently keep old baselines or grants. Existing expired/failed attempts remain historical, including the failed normal45-minute automatic main runs. Real newly demonstrated test failures require assessment even if a transition source passed.

## 9. Retire the bootstrap and finish P through normal main60

1. After native merge of #411, stop issuing all transition grants. Revoke any unfinished grant. Hard sunset remains a final backstop and never auto-extends.
2. Rebase P onto current main60. Remove its active activation workflows and grant-issuance entry point, retain explicit `audit-consumed` historical verification and regression fixtures (archive integrity and recorded provenance, never fresh live approval), and update the RFC/ledger to the actual used roots and outcomes. Its final diff must not introduce a permanent parallel admission authority. Original used roots remain immutable historical commits.
3. Run mandatory/cheap checks and independent exact-head review for P's final revision. The final tests must cover the retained verifier and recorded transition fixtures, and must not require a deleted active path. Update the full inventory by the accepted procedure. No historical claim can replace its tests.
4. Admit P through the ordinary main gate. Require its own two whole baselines, comparison, platform23, both native architectures and ordinary sealed publication. It now has the installed60-minute budget without relying on itself. Prepare P's final packet and obtain its own later exact-head authorization before native merge.
5. Review the first complete normal main60 results, including #409's later independent work, against the sizing decision. No further timeout increase or new transition consumer is authorized here. Deployment/production authority remains separate.

## Failure and ambiguity table

| Observation | Required response |
| --- | --- |
| Actions policy/credential cannot create the documented push run | Stop; record exact missing capability. No settings bypass or dispatch substitution. |
| Existing activation ref, duplicate run or lost journal | Refuse activation/acceptance; no force overwrite, recreation or guessed unused slot. |
| Push/comment outcome unknown | Reconcile exact intended identity; no additional write until resolved. If unresolved, retire/refuse the grant. |
| Grant/admission/binding edited, deleted, minimized, expired or revoked | Cancel/refuse; missing original state cannot be reconstructed as authority. |
| Head/base/merge/lifecycle change, or observed activation-ref drift | Revoke. PR timeline history prevents return-to-old-head shortcuts. An unseen activation-ref round trip cannot be asserted detected; immutable T and the fixed first run ID still reject any replacement use. |
| Timeout, real failed test or unavailable full evidence | Fail entire source. Preserve results; diagnose; no automatic retry or partial acceptance. |
| Publisher failed after some evidence uploads | No receipt authority; whole attempt incomplete. |
| Existing/native required45-minute status appears | Stop; no forged status, renamed check, admin merge or protection change. |
| User refuses provisional root reliance | Do not activate. Current policy remains and #411 stays blocked. |
| Need to change DB, comparator, native currentness or independent custody rules | Stop at that boundary and propose separate work; do not stretch P. |

Next: review this runbook together with the design and guarantee matrix before any live card, implementation or activation.
