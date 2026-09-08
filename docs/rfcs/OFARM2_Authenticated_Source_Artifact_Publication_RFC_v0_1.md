# Authenticated source-artifact publication — RFC v0.1

Status: proposed, awaiting same-task semantic approval before implementation.
Decision: `OFARM2-SOURCE-ARTIFACT-PUBLICATION-001`, version 1.
Delivery: [#381](https://github.com/samovers/OFARM2/issues/381), under Tracking Epic
[#167](https://github.com/samovers/OFARM2/issues/167). One complete Delivery PR.
Primary trust boundary: **evidence-publication custody**.

This is implementation and repository evidence policy, not OFARM law. It changes
no runtime truth, production authority, capability claim or deployment posture.

## Problem and independently reviewable outcome

The baseline producer hashes configured verified artifacts under its executed
source root. The trusted publisher currently recomputes those hashes under its
own default-branch policy checkout. A legitimate change to a verified artifact
therefore prevents publication even when both source envelopes correctly report
the exact executed bytes.

This occurred in [PR #380](https://github.com/samovers/OFARM2/pull/380): source run
[34149023176](https://github.com/samovers/OFARM2/actions/runs/34149023176), attempt 1,
passed both locked baselines, native verification and handoff at historical head
`64d3cbd60828c353bf284f2b7bbbfdbb6f5cd018`. Publisher
[34151241570](https://github.com/samovers/OFARM2/actions/runs/34151241570), attempt 1,
refused with `review baseline verified artifacts differ` and produced no final
artifacts or receipt. Those results are historical diagnosis, not evidence that
this proposed implementation or PR #380's repaired head passes its gates.

The outcome is precise: the publisher compares each trusted configured path's
producer hash with the authenticated bytes at the execution commit. Legitimate
source changes can pass; fabricated, stale or differently ordered claims refuse.
PR #380 depends on this separate capability. It contributes no code to this PR.

## Authority, assets and threat model

Protect the meaning of published evidence and its final receipt: exact source
identity, file hashes, complete passing results and faithful comparison.

| Owner | Authority retained |
| --- | --- |
| Task user | Semantic approval and later exact-head final merge authorization |
| Trusted default-branch publisher and configuration | Allowed paths, verification policy, authoritative staging and refusal |
| Existing admission, source-run and ticket chain | Repository, execution merge commit, run/attempt, source artifacts and revocation binding |
| Authenticated GitHub API | Raw source bytes at that bound repository/path/commit |
| Existing receipt machinery | Published artifact identities, digests and final custody record |
| Producer | Provisional claims only; no path selection or publication authority |

Treat admitted PR content, fetched source bytes, producer envelopes, archives and
comparison documents as untrusted data. A PR author may change source artifacts
or fabricate producer fields, including self-consistent false hashes. They may
not change trusted default policy, compromise publisher credentials or the
GitHub/TLS trust chain; those compromises are outside this bounded defect.

The supported entry is the existing trusted `stage-conformance` publication CLI
invoked after source/ticket/admission resolution. The primary risk is accepting a
producer-chosen hash or reading the wrong revision. Keep path selection in trusted
configuration and all raw reads on the already-authenticated execution commit.
No new credential owner, API scope, source resolver or execution authority arises.

## Proposed single path and custody sequence

Current main is `ff092c414db9fa24dbd6ab86c7722db89e0c95b5`. The proposal uses the
existing `stage_conformance_evidence`, `_download_authenticated_source_file` and
`_validate_baseline_evidence` in `conformance/evidence_publication_policy.py`.

1. Preserve current source coordinate, provisional inventory and admission checks.
2. Read baseline configuration from the trusted policy checkout. It alone owns
   `verifiedArtifacts` paths and ordering. Continue obtaining the test inventory
   through the existing authenticated source reader.
3. For each configured verified-artifact path, call that same bounded reader with
   the same API, repository, token and full execution merge SHA. Hash its raw
   bytes once. Construct one ordered expected path/hash list before validating
   either producer run or creating authoritative output.
4. Make that expected list a required argument to baseline validation. Use it for
   both source-run validations and both staged-run revalidations. Keep exact list
   equality; delete the policy-root artifact hash calculation, with no fallback.
5. Preserve producer comparison verification, canonical staging, staged-result
   checks, rebuilt comparison, platform evidence, native checks and final receipt.

The source reader already refuses invalid coordinates, redirects, non-200,
empty, oversized and failed reads. Preserve those checks and its existing bounds.
Fetched artifacts are raw hash inputs only: no parse-as-policy, checkout, import,
execution, evaluation or content-derived path selection. There is no content cache
or new durable representation. A failure is a publication refusal, not authority
to repair producer data or reuse another byte source.

## Falsifiable invariants and focused evidence

| ID | Invariant | Observable evidence at the existing staging boundary |
| --- | --- | --- |
| P01 | Trusted configuration alone selects artifact paths and order. | Producer-added, omitted, duplicated, changed or reordered entries refuse. Recorded requests contain only trusted paths. |
| P02 | Every read binds the existing checked API/repository/path and one authenticated full execution SHA. Source failures have no fallback. | Assert exact request URLs, ref and existing authentication headers using fictional tokens; missing/non-200/redirect/empty/oversized/read-error responses refuse before output creation. |
| P03 | One raw-byte expected hash list governs both source runs and staged revalidation. | Changed-source positive differs from policy checkout, stages successfully and retains exact source hashes; unchanged-source control passes. Old-policy, fabricated and other-revision hashes in either or both producer runs refuse. |
| P04 | Untrusted source bytes gain no execution or policy authority. Other policy-owned input checks stay intact. | Executable-looking fixture bytes remain inert hash inputs. Existing configuration, dependency/manager lock, schema, environment and result-tampering negatives continue to refuse. |
| P05 | Existing admission, run/attempt/ticket, artifact identities/digests, extraction, outcome/inventory, comparison, native reauthentication and receipt conditions remain mandatory. | Existing publication/admission regression suite stays passing, including revocation, archive and rerun refusal cases. Full required hosted publication provides the final custody receipt later. |
| P06 | This prerequisite starts from main and preserves both configured verified-artifact files. | Exact diff/hash checks prove those files are unchanged; the prerequisite obtains its own publication receipt through the unchanged default publisher before merge. |

Tests use fictional bytes, bounded fake HTTPS responses and temporary directories.
They exercise the real staging function with complete valid envelopes and a real
comparison so a negative cannot pass through an unrelated missing-evidence error.
For list/hash mutations, recompute the producer comparison when needed to prove
that artifact equality itself rejects a self-consistent false claim. Do not patch
out admission, validation, comparison or receipt decisions to obtain a positive.

The existing full staging fixture currently returns inventory for one request.
Adapt its response factory to dispatch by exact URL and prove exactly one read
per trusted source path: inventory plus the current two configured artifacts.
Reuse it for the bounded cases; avoid copying its large envelope construction.
A minimal shared fixture helper is justified only for these current test uses.

## Smallest complete change and code excellence

**EXC-001/002:** trusted configuration remains the single path authority; the
existing source reader is the only retrieval path; one expected list replaces the
wrong-revision comparison. No duplicate policy registry, resolver, fallback or
persistent state is added.

**EXC-003:** P01-P04 map directly to staging, the existing reader and the required
validator argument. P05 maps to unchanged custody machinery and its tests. P06
maps to source isolation and the prerequisite's own required publication.
**EXC-004:** remove the superseded local-policy artifact hash calculation.
**EXC-005:** no new runtime abstraction is planned; a required expected-list
parameter serves the existing producer and staged validators immediately.
**EXC-006:** trusting the producer's hash is simpler but loses independent binding;
retaining local hashes rejects lawful changes; adding a second reader duplicates
custody. Reusing the current authenticated reader is the smallest coherent fix.
EXC-007 Preferences remain non-blocking under AGENTS.md.

Expected implementation areas are the publisher, its current focused tests,
`conformance/REVIEW_BASELINE.md` if clarification is useful, this design, and the
mechanical policy SHA-256 pin in `.github/workflows/evidence-publication.yml`.
The workflow already supplies the execution commit. No workflow behavior change
is planned. Regenerate inventory only if actual root collection changes; focused
conformance tests already run in the existing lightweight check.

Implementation, tests, required pin and documentation belong in this one Delivery
PR because they jointly deliver and prove this custody correction. No schema,
migration, kernel, fixture-grant, capability-manifest or ActiveArtifactSet change
is needed. The decision binds the capability and invariants, not this path list.

## Bootstrap, verification and rollback

Branch from current main, not PR #380. Preserve both verified-artifact files and
policy-owned baseline input files. The unchanged default publisher can therefore
verify this prerequisite's own evidence; candidate unit tests prove the new
behavior before the new publisher becomes trusted main policy. Carrying PR #380's
manifest here would recreate the failure and create a circular dependency.

Run the mandatory package contract before each commit, focused publication and
admission tests, relevant lint and existing workflow/policy-pin checks. Record any
existing extraction diagnostic without calling it a pass. Phase-A-only heads get
no expensive admission. After implementation and cheap checks: exact-head content
review with zero Blockers, fresh admission, all required hosted baselines/native
verification/publication, final scope/excellence recheck, then a complete user
packet and later exact-head merge authorization. No prior result transfers.

If the unchanged default publisher still refuses the prerequisite, stop and
identify the demonstrated cause within the same gates. Do not replay the failed
publisher attempt, edit historical envelopes, stage through candidate code as a
substitute for trusted default policy, or waive a receipt. After the prerequisite
is accepted and merged, PR #380 needs its own fresh applicable admission, source
execution and publication sequence; the old failed attempt is never rerun.

No database migration or runtime rollout exists. A future revert must preserve
normal source review and publication custody; it would restore the old refusal
for changed artifacts, not authorize fallback evidence. Existing published
receipts are immutable historical records and are not rewritten.

## Decision and non-effects

High-risk version-1 approval is required after Phase A has zero design Blockers
and a complete card names the existing draft PR. The approval must be a later
exact task-user message in the same task. PR #380's semantic approval grants no
custody implementation authority here. This document is not that approval card.

No kernel semantic/retirement authority, identity or credential decisions,
database roles/transactions, runtime activation, manifests, contracts, canonical
content, deployment, release, current/default promotion or production access
changes. No GitHub permission changes, new runner, manual admission substitute,
workflow-attempt rerun, final receipt waiver or cross-boundary exception.

The correction is intended as the durable publisher behavior, not a temporary
workaround. Repository development remains pre-deployment and provisional;
independently human-controlled approval remains necessary before deployment.
A new source authority, dynamic producer-selected path set, changed publication
identity/receipt semantics or a required cross-boundary effect invalidates this
design and requires separate work or a new approved decision version.

Next: review this Phase A, bind it to the single draft Delivery PR, and obtain
same-task version-1 semantic approval before implementation.
