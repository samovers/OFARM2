# Authenticated source-artifact publication — RFC v0.2

Status: proposed revision after review B1; requires bounded design review and
new same-task semantic approval before implementation.
Decision: `OFARM2-SOURCE-ARTIFACT-PUBLICATION-001`, version 2.
Delivery: [#381](https://github.com/samovers/OFARM2/issues/381), under Tracking Epic
[#167](https://github.com/samovers/OFARM2/issues/167). One complete Delivery PR: [#382](https://github.com/samovers/OFARM2/pull/382).
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

## Version-2 correction to the withdrawn design

[Review B1](https://github.com/samovers/OFARM2/pull/382#pullrequestreview-5168801319)
showed that the existing Contents response reader authenticates a bounded HTTP
response but does not establish file kind. The Contents API can return metadata
for non-file objects and can dereference symlinks. Hashing such a response is not
proof of artifact-file content. The local Python 3.12.13 reader probe accepted
three fictional directory/link/submodule metadata responses; this was not a live
provider capture or an end-to-end publication exploit.

Version 1 and its approval card are withdrawn. Version 2 keeps the same Delivery,
PR, custody boundary and source authority, but adds an explicit supported-file
contract for the shared reader. It applies to the existing source test inventory
as well as the two verified artifacts. All symlinks are unsupported, including
links to ordinary in-repository files and links in parent path components.

The second review point is a mechanical dependency: changing publisher policy
requires its pin in `evidence-publication.yml`, then that workflow's pin in
`conformance.yml`. Both travel in this same PR. No workflow behavior changes.

## Authority, assets and threat model

Protect the meaning of published evidence and its final receipt: exact source
identity, file hashes, complete passing results and faithful comparison.

| Owner | Authority retained |
| --- | --- |
| Task user | Semantic approval and later exact-head final merge authorization |
| Trusted default-branch publisher and configuration | Allowed paths, verification policy, authoritative staging and refusal |
| Existing admission, source-run and ticket chain | Repository, execution merge commit, run/attempt, source artifacts and revocation binding |
| Authenticated GitHub API | Commit/tree object metadata and blob bytes bound to the selected repository and execution commit |
| Existing receipt machinery | Published artifact identities, digests and final custody record |
| Producer | Provisional claims only; no path selection or publication authority |

Treat admitted PR content, fetched source bytes, producer envelopes, archives and
comparison documents as untrusted data. A PR author may change source artifacts
or fabricate producer fields, including self-consistent false hashes. They may
not change trusted default policy, compromise publisher credentials or the
GitHub/TLS trust chain; those compromises are outside this bounded defect.

The supported entry is the existing trusted `stage-conformance` publication CLI
invoked after source/ticket/admission resolution. The primary risk is accepting a
producer-chosen hash, reading the wrong revision, or treating non-file metadata
as artifact bytes. Keep path selection in trusted configuration and prove each
file through the authenticated execution commit. The same source-reader entry
point is strengthened; no parallel reader, credential owner, API scope or source
execution authority is added.

## Proposed single path and custody sequence

Current main is `ff092c414db9fa24dbd6ab86c7722db89e0c95b5`. The proposal uses the
existing `stage_conformance_evidence`, `_download_authenticated_source_file` and
`_validate_baseline_evidence` in `conformance/evidence_publication_policy.py`.

1. Preserve current source coordinate, provisional inventory and admission checks.
2. Read baseline configuration from the trusted policy checkout. It alone owns
   `verifiedArtifacts` paths and ordering, plus the source test-inventory path.
3. Strengthen `_download_authenticated_source_file` as the single supported-file
   reader for inventory and verified artifacts, using the object proof below.
   Reuse its existing authenticated bounded HTTP transport in a small private
   helper for metadata and raw bytes; delete the old Contents response path.
4. For each trusted configured artifact, hash the proven file bytes once into one
   ordered expected path/SHA-256 list before validating either producer run or
   creating authoritative output. The existing inventory parser still validates
   the separately obtained, now-proven regular inventory file.
5. Require that expected list in baseline validation. Use it for both source-run
   validations and both staged-run revalidations. Preserve exact equality and
   delete the obsolete policy-root artifact calculation, with no fallback.
6. Preserve comparison verification, canonical staging, staged-result checks,
   rebuilt comparison, platform evidence, native checks and the final receipt.

### Supported-file contract within the existing reader

For each canonical trusted path, use the existing checked API, repository, token,
full lowercase execution SHA, authentication headers and API version. Construct
all request URLs locally from those checked values and validated object IDs;
never follow response-provided URLs, download URLs, branches or tags.

1. Request `GET /repos/{repository}/git/commits/{execution_sha}` as JSON. Parse with
   the publisher's existing strict JSON-object decoder. Require the returned
   commit SHA to equal the supplied execution SHA and a valid full root-tree SHA.
   The existing admission/ticket chain remains the authority for that execution
   SHA; this reader does not select or approve it.
2. Walk only the trusted path's components. For each component request the current
   tree with `GET /repos/{repository}/git/trees/{tree_sha}`, **omitting the recursive
   parameter entirely**. Require matching returned tree SHA, `truncated` exactly
   false, valid array/entry shapes, and exactly one child with the exact component
   name. Consume one component per step; never recurse over unrelated entries.
3. Each selected parent must be `type=tree`, `mode=040000`, with a valid full child
   SHA. The terminal must be `type=blob`, with mode `100644` or `100755`, a valid
   full blob SHA and a non-boolean integer size in `1..MAX_SOURCE_INPUT_BYTES`.
   Refuse directory terminals, submodules (`160000`), symlinks (`120000`) anywhere
   on the selected path, missing or duplicate selected entries and unsupported
   type/mode combinations. Unrelated symlink entries in a tree are not traversed.
4. Request `GET /repos/{repository}/git/blobs/{proved_blob_sha}` using the raw blob
   media type. Require the received byte count to equal the terminal size and its
   Git blob object ID to equal the proved SHA:
   `SHA1(b"blob " + ASCII(length) + b"\0" + payload) == proved_blob_sha`.
   This verifies Git's existing object binding; it does not replace SHA-256
   evidence hashes or create signing authority. Only these verified raw bytes
   return from the reader. Metadata documents are never returned as content.

Preserve HTTP 200, exact final URL, no redirects, nonempty bounded reads, existing
30-second request timeout and existing authentication handling. Bound each commit,
tree and blob response by the existing 8 MiB `MAX_SOURCE_INPUT_BYTES` before
parsing or hashing; malformed/duplicate-key/non-finite metadata uses the existing
strict decoder and refuses. Do not raise the raw-file size limit for this change.

A depth-d trusted path requires at most d+2 reads: one commit, d trees and one
blob. Trusted configuration fixes both path count and depth. There is no recursive
listing, pagination, retry fallback or cache; truncated or oversized metadata
refuses. The current three two-component paths therefore require twelve reads,
not the withdrawn version-1 three-read assertion. A failed proof stops before
its blob fetch or before authoritative output, as applicable.

Use provider object information, never a guess based on content shape or MIME.
A regular file whose bytes resemble directory/link metadata remains a legitimate
inert hash input. Fetched bytes are never checked out, imported, executed,
evaluated as code or used to select policy. No new durable state is introduced.

Provider contracts checked for this design:
[Contents API](https://docs.github.com/en/rest/repos/contents?apiVersion=2026-03-10),
[Git commit API](https://docs.github.com/en/rest/git/commits?apiVersion=2026-03-10),
[Git tree API](https://docs.github.com/en/rest/git/trees?apiVersion=2026-03-10),
[Git blob API](https://docs.github.com/en/rest/git/blobs?apiVersion=2026-03-10), and
[Git object format](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects).

## Falsifiable invariants and focused evidence

| ID | Invariant | Observable evidence at the existing staging boundary |
| --- | --- | --- |
| P01 | Trusted configuration alone selects artifact paths and order. | Producer-added, omitted, duplicated, changed or reordered entries refuse. Recorded requests contain only trusted paths. |
| P02 | Every inventory/artifact read proves a supported regular file through the authenticated execution commit, selected parent trees and terminal blob; all symlinks and submodules on the path are unsupported. | Assert exact commit/tree/blob requests, object IDs, modes, sizes and hashes. Directory terminals, parent/terminal links, submodules, missing/duplicate names, truncated/malformed metadata and content mismatches refuse. Transport failures have no fallback and no authoritative output. |
| P03 | One ordered SHA-256 list of proven raw file bytes governs both source runs and staged revalidation. | Changed-source positive differs from policy checkout and retains exact hashes after staging; unchanged-source control passes. Stale/fabricated/other-revision claims in either or both runs refuse. Self-consistent hashes of non-file metadata refuse at file proof even with recomputed producer comparison. |
| P04 | Untrusted source bytes gain no execution or policy authority. Other policy-owned input checks stay intact. | Executable-looking fixture bytes remain inert hash inputs. Existing configuration, dependency/manager lock, schema, environment and result-tampering negatives continue to refuse. |
| P05 | Existing admission, run/attempt/ticket, artifact identities/digests, extraction, outcome/inventory, comparison, native reauthentication and receipt conditions remain mandatory. | Existing publication/admission regression suite stays passing, including revocation, archive and rerun refusal cases. Full required hosted publication provides the final custody receipt later. |
| P06 | This prerequisite starts from main and preserves both configured verified-artifact files. | Exact diff/hash checks prove those files are unchanged; the prerequisite obtains its own publication receipt through the unchanged default publisher before merge. |

Tests use fictional bytes, bounded fake HTTPS responses and temporary directories.
They exercise the real staging function with complete valid envelopes and a real
comparison so a negative cannot pass through an unrelated missing-evidence error.
For list/hash mutations, recompute the producer comparison when needed to prove
that artifact equality itself rejects a self-consistent false claim. Do not patch
out admission, validation, comparison or receipt decisions to obtain a positive.

Extend the existing complete staging fixture with fictional commit/tree/blob
responses dispatched by exact request URL. Its graph supplies each file's mode,
size and blob identity. Keep complete valid inventory, results, environment and
comparison evidence. Run directory-terminal, submodule, resolved/unresolved
terminal-symlink and parent-symlink negatives with both envelopes claiming the
same non-file metadata hash and a recomputed comparison. Assert the specific
unsupported-object refusal and absence of authoritative output; do not mock out
the file proof or any later verification to make these cases pass.

Reader negatives cover wrong commit/tree/blob identity, missing or duplicate
selected names, malformed or truncated trees, invalid mode/type/size including
boolean sizes, oversized metadata/raw bytes, redirects and failed reads. For
all configured files, assert the exact bounded request sequence and refusal of
response-provided URL substitution. Include an inventory non-file case to prove
that both present consumers use the same supported-file contract.

Positive controls cover regular and executable-mode files treated only as data,
changed and unchanged artifacts, and regular JSON blobs whose bytes look like
API metadata. Verify exact source hashes survive staging and comparison. Reuse
minimal fixture construction helpers for these present cases; do not duplicate
the large envelope construction or introduce a generic Git transport framework.

## Smallest complete change and code excellence

**EXC-001/002:** trusted configuration remains the single path authority; the
strengthened source reader is the only file-proof path, with one bounded HTTP
transport helper; one expected list replaces the wrong-revision comparison. No duplicate policy registry, resolver, fallback or
persistent state is added.

**EXC-003:** P01-P04 map directly to staging, the existing reader and the required
validator argument. P05 maps to unchanged custody machinery and its tests. P06
maps to source isolation and the prerequisite's own required publication.
**EXC-004:** remove both the superseded local-policy artifact hash calculation
and the untyped Contents response path.
**EXC-005:** the private bounded HTTP helper serves commit/tree/blob requests
inside the existing reader; its object proof serves inventory and artifacts now.
The required expected-list parameter serves producer and staged validators.
**EXC-006:** trusting the producer's hash is simpler but loses independent binding;
retaining local hashes rejects lawful changes; adding a second reader duplicates
custody. Contents metadata alone can dereference links and lacks the required
mode proof. A direct component walk within the existing reader is the smallest
credible path that also rejects parent links without checkout or a full tree scan.
EXC-007 Preferences remain non-blocking under AGENTS.md.

Expected implementation areas are the publisher, its current focused tests,
`conformance/REVIEW_BASELINE.md` if clarification is useful, this design, and the
mechanical policy SHA-256 pin in `.github/workflows/evidence-publication.yml`,
and that workflow's transitive SHA-256 pin in `.github/workflows/conformance.yml`.
`kernel/tests/test_postgresql_native_evidence.py` already checks both pin
relationships and their enforcement. Both workflows keep their existing behavior.
The publication workflow already supplies the execution commit. No workflow behavior change
is planned. Regenerate inventory only if actual root collection changes; focused
conformance tests already run in the existing lightweight check.

Implementation, tests, both required pins and documentation belong in this one Delivery
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
packet and later exact-head merge authorization. No prior result transfers. The v1 design-only checks and 70 unchanged publication
tests remain historical; they are not evidence that this new reader is implemented.

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

High-risk version-2 approval is required after the affected Phase A has zero design Blockers
and a complete card names existing draft PR #382. Version 1 remains withdrawn. The approval must be a later
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
Changing the explicit no-symlink/regular-file contract, accepting other source
object kinds, a new source authority, dynamic producer-selected path set, changed publication
identity/receipt semantics or a required cross-boundary effect invalidates this
design and requires separate work or a new approved decision version.

Next: review this Phase A, bind it to the single draft Delivery PR, and obtain
same-task version-2 semantic approval before implementation.
