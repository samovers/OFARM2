# OFARM2 trusted review-baseline rfc8785 adoption RFC v0.1

Status: Phase A design draft. No route, exception, dependency adoption,
implementation, hosted execution, additional paid spend, purchase, top-up,
quota expansion, recovery, ready transition or merge is authorized by this
document or by opening its draft pull request. The bounded automatic
existing-plan review in Section 15 is the only review-plan use proposed for
opening.

## 1. Capability and problem

This RFC designs one governed route for a possible future adoption of the exact
`rfc8785==0.1.4` wheel into OFARM2's trusted review baseline.

Draft [#456](https://github.com/samovers/OFARM2/pull/456) needs that package.
The current executor can install dependencies from the authenticated candidate
merge, but the independent publisher rebuilds its expected lock digest and
installed set from trusted `main`. Candidate execution therefore has 50
baseline pins while the current publisher policy has 49. A lock-only pull
request cannot produce its own authoritative publication under that mismatch.

The design opening is the smallest independently reviewable step. It creates no
trusted package state and selects no alternative below.

## 2. Primary trust boundary

The primary trust boundary is the **trusted CI/conformance
verification-environment dependency policy**.

The initial draft changes only this RFC. A later approved implementation in
this same Delivery may change the qualified baseline lock, its exact contract,
a local dependency qualifier and tests, mechanically regenerated test
inventory, and factual baseline documentation. That later implementation is
not authorized now.

The boundary excludes Event Ingress meaning, #456/#458 implementation,
independent publisher authority, receipt semantics, workflow selection,
runtime deployment, key custody, database authority and production package
installation.

## 3. Risk classification and protected assets

This is high-risk Phase A because the accepted dependency environment produces
conformance evidence.

Protected assets are:

- the exact dependency environment used by both complete baselines;
- independent validation by trusted default-branch publisher policy;
- the binding among policy revision, execution tree, locks, installed set,
  source artifacts and final publication;
- the rule that candidate content cannot define the policy used to validate
  itself.

The primary risk is circular trust: treating evidence produced with a candidate
lock as authority to adopt that same lock. The containment rule is that no
candidate evidence changes publisher policy, no route is selected without the
later reviewed human decision, and dependent work remains blocked until the
selected route completes authenticated acceptance.

## 4. Authority map

- The task owner selects or refuses a route, approves any later implementation,
  authorizes recovery, and later authorizes an exact-head native merge.
- The named draft and this RFC own Phase A design only.
- Independent reviewers own demonstrated design or implementation Blockers.
- Trusted default-branch admission and publication code own mechanical
  verification and evidence custody, not human approval.
- GitHub owns provider state and any native merge transition.
- The CI/conformance owner may implement only the later approved in-boundary
  slice.
- Independent publisher, runtime, database, tenant, key, audit and deployment
  authorities retain their existing owners.

## 5. Trusted and untrusted inputs

Trusted inputs for the later delivery are the authenticated default-branch
policy revision, exact reviewed head, live base and test merge, pinned lock
bytes, the retrieved wheel bytes after digest verification, repository-owned
schemas and validators, and provider records independently re-read through the
trusted path.

Untrusted inputs include candidate pull-request content, downloaded artifacts
before exact identity and digest validation, package metadata before binding to
the accepted wheel, issue or review prose as machine evidence, and any receipt
field without independent artifact validation.

This RFC does not claim to contain compromise of GitHub's identity provider,
repository-owner credentials, the configured runner image, or the SHA-256
algorithm. It must not weaken existing controls for those risks.

### 5.1 State and ordering model

The state machine is fail-closed:

```text
LOCAL_PREPARED
  -- later exact design-opening authority --> PUBLIC_PHASE_A_DRAFT
  -- no authority / changed live fact -----> STOPPED

PUBLIC_PHASE_A_DRAFT
  -- expected opening checks + zero-Blocker Phase A review
                                            -> ROUTE_DECISION_PENDING
  -- check failure / Blocker / scope drift / unexpected execution
                                            -> STOPPED

ROUTE_DECISION_PENDING
  -- no owner reply -----------------------> WAITING
  -- owner selects merge-first route ------> ROUTE_A_APPROVED
  -- owner requires pre-merge publication -> SEPARATE_DELIVERY_REQUIRED
  -- changed card or named PR -------------> STOPPED

ROUTE_A_APPROVED
  -- later implementation authority -------> IMPLEMENTING
  -- absent authority / boundary expansion -> STOPPED

IMPLEMENTING
  -- cheap checks + exact-head review -----> MERGE_DECISION_PENDING
  -- failure / changed head / Blocker ------> STOPPED

MERGE_DECISION_PENDING
  -- later exact-head native merge authority
                                            -> ADOPTED_UNVERIFIED_MAIN
  -- no authority / changed live fact -----> STOPPED

ADOPTED_UNVERIFIED_MAIN
  -- automatic main acceptance + unchanged publisher receipt
                                            -> ADOPTION_COMPLETE
  -- missing or failed acceptance ---------> RECOVERY_DECISION_REQUIRED

SEPARATE_DELIVERY_REQUIRED, STOPPED, RECOVERY_DECISION_REQUIRED
  -- no retry, repair, transition, revert or continuation without new authority
```

The design-opening choice can advance only from `LOCAL_PREPARED` to
`PUBLIC_PHASE_A_DRAFT`. It cannot select a route or enter implementation.

### 5.2 Protected-output custody model

| Protected item | Custodian and binding | Fail-closed rule |
| --- | --- | --- |
| Trusted policy revision | GitHub/Git default-branch commit, workflow SHA and independently verified tree | Candidate content cannot choose or rewrite the policy coordinate used to validate itself. |
| Wheel bytes | Untrusted until filename, length, SHA-256, metadata, tag and installed module bytes match the later approved qualification record | Any byte, metadata, tag or implementation mismatch refuses qualification. |
| Baseline evidence | Producer creates provisional archives bound to source run, attempt, commit and artifact identity | Producer claims are never authoritative by themselves. |
| Publication ticket | Trusted handoff seals the exact provisional artifact IDs/digests and source identity, then uploads the ticket last | Missing, ambiguous, unexpected or re-run identity refuses publication. |
| Authoritative artifacts | Independent publisher downloads exact IDs, verifies archive digests and validates extracted content under trusted policy | Publisher never executes candidate code or accepts unbound content. |
| Final receipt | Independent publisher binds admission, source/publisher workflow identities and exact artifact IDs/digests; external verification re-reads provider state and bytes | Receipt text alone does not establish package, tree or human authority. |
| Human decision and merge authority | Original DECISIONS card and later owner reply, each directly retrievable in required order | Copies, summaries, GitHub activity or AI messages never substitute for the owner reply. |

## 6. Exact public dependency evidence

Current trusted policy is `dd791229cce4888366c332a334df71e1e856dd41`.
The candidate comparison coordinate is authenticated test merge
`4d6edfa9b3841a4a82739596c9ca2a0be9b266bb`, tree
`75b8f0f5e600caf952d4ac53dc2c607c400830ac`.

The only baseline-lock delta is:

```text
rfc8785==0.1.4 \
    --hash=sha256:520d690b448ecf0703691c76e1a34a24ddcd4fc5bc41d589cb7c58ec651bcd48
```

The accepted wheel is
`rfc8785-0.1.4-py3-none-any.whl`, 9,240 bytes, published at the
[PyPI file coordinate](https://files.pythonhosted.org/packages/4d/78/119878110660b2ad709888c8a1614fce7e2fab39080ab960656dc8605bf6/rfc8785-0.1.4-py3-none-any.whl).
Its embedded name/version are `rfc8785`/`0.1.4`, its tag is `py3-none-any`,
`Requires-Python` is `>=3.8`, and it has no non-extra runtime dependency.

| Evidence | Current trusted policy | Proposed future policy |
| --- | --- | --- |
| Baseline pins | 49 | 50 |
| Baseline lock raw SHA-256 | `c634822a164f456a5d0e1280d2b47d737bc3a6629f67cd47ac7543670ae2f3f7` | `8593b897470c797ae6029420d2c86843dc50a9ff4d6cb8a505fb3791114fff74` |
| Package-manager lock raw SHA-256 | `549d9ca34c7e72097b0e135cb11039cf7a9a560dd4d9159ef6626d9fb4ad8679` | unchanged |
| Installed distributions including `pip==26.1` | 50 | 51 |
| Canonical installed-set SHA-256 | `43b758b3f385c4f366e64407f299977d0bfb3861fb7b6ca2ac5841b90f4dc341` | `2e5ad948974eed282b0f8b640b67f3888779438a911021acce6c28daa739b984` |

This is design evidence, not a trusted adoption result. A later implementation
must reproduce it in the repository's exact Python 3.12.13 Linux x86_64
baseline and complete authenticated acceptance.

## 7. Current execution and publication behavior

The [conformance workflow](../../.github/workflows/conformance.yml) checks out
the authenticated execution merge and installs its two locks with hashes,
binary-only packages and no dependency resolution. The
[baseline runner](../../conformance/run_review_baseline.py) records raw lock
digests, the sorted installed array, its canonical digest, missing/mismatched
and unexpected distributions, and `pip check`.

The [publication policy](../../conformance/evidence_publication_policy.py)
reconstructs the expected lock digest and installed set from its trusted policy
checkout. The [admission code](../../conformance/review_baseline_admission.py)
requires a successful source and publisher policy identity. These checks are
intentional and remain unchanged.

The former [CI policy transition](OFARM2_CI_Policy_Transition_RFC_v0_1.md) is
retired and audit-only. It supplies precedent, not reusable authority.

## 8. Alternative A: merge-first evidence sufficiency

The smallest in-boundary alternative is an explicit, one-time exception for an
exact reviewed dependency-policy revision. Before merge it would require exact
wheel qualification, exact lock and installed-set evidence, permitted cheap
checks, and exact-head zero-Blocker content review.

The later decision would have to name the precise procedural deviation: this
policy pull request cannot satisfy the normal pre-merge
`REQUIRED_HOSTED_BASELINES_AND_PUBLICATION` and corresponding receipt recheck.
After a separately authorized native merge, the automatic `main` push would
authenticate the adopted commit as source, execution and policy revision. The
unchanged independent publisher could then reconstruct the same 50-pin lock
and 51-item installed set.

This alternative creates a finite interval in which `main` contains the policy
before its complete authoritative acceptance exists. A failed or missing
automatic acceptance stops dependents and requires separately reviewed and
authorized recovery or native revert. A revert cannot erase that historical
interval or supply missing pre-merge evidence.

This RFC does not select or authorize the exception.

## 9. Alternative B: separate policy-transition prerequisite

If authoritative publication is required before the lock reaches `main`, a
separate Delivery must create bounded publisher recognition of an unmerged
policy. That crosses into evidence-publication custody and CI policy selection,
bounded use, revocation and recognition.

Such a delivery would require its own authority map, one-use grant, source and
policy authentication, use journal, refusal semantics, external verification,
sunset and retirement. It cannot be appended to this dependency adoption, #456
or #458.

This RFC does not select or authorize that authority.

## 10. Decision-level invariants and non-effects

- Publisher policy and workflow remain unchanged in an in-boundary adoption.
- Candidate evidence never defines the policy that validates itself.
- The exact wheel and all installed distributions remain hash/version pinned.
- Both complete baselines must report identical raw locks and installed arrays.
- Missing, mismatched or unexpected distributions and failed `pip check` refuse
  acceptance.
- #456 remains blocked until the prerequisite completes.
- Opening or reviewing this RFC selects no route.
- No direct-main write, admin merge, automatic merge, manual evidence forgery,
  rerun substitution or partial baseline success is acceptable.

Each invariant has a reachable refusal or stop case:

| Invariant | Reachable negative case | Required result |
| --- | --- | --- |
| Publisher policy/workflow stay unchanged | The proposed implementation diff touches a publisher or workflow path. | Scope check stops before implementation or push and requires a separate Delivery. |
| Candidate evidence cannot define validating policy | Source execution SHA or policy SHA differs from the authenticated trusted coordinate. | Admission/publication policy refuses the run. |
| Exact wheel and installed distributions remain pinned | Wheel digest, embedded version/tag, module bytes or a lock hash differs. | Hash installation or the qualifier refuses before baseline credit. |
| Both baselines report identical locks and installed arrays | One envelope changes a raw lock digest, package version or canonical installed-set digest. | Strict equivalence and publisher validation refuse acceptance. |
| Missing/mismatched/unexpected packages or failed `pip check` refuse | A baseline omits `rfc8785`, adds an extra distribution or records failed `pip check`. | Baseline/publisher policy reports refusal; no receipt is authoritative. |
| #456 remains blocked until prerequisite completion | #456 is admitted while trusted policy still has 49 pins or before the adopted-policy receipt verifies. | Publisher refuses the dependency mismatch or coordination stops admission; #456 receives no authoritative acceptance. |
| Opening/reviewing the RFC selects no route | The design-opening diff contains a lock/code change, an admission comment is proposed, or a route is represented as approved without the owner reply. | Opening scope or authority check stops; the draft remains design-only. |
| No direct-main/admin/auto merge, forged evidence, rerun substitution or partial credit | A proposed operation uses any of those paths or substitutes an earlier/partial run. | The coordinator does not issue the provider mutation and the final packet cannot be prepared. |

## 11. Future implementation areas

Only a later valid decision may authorize changes in these expected areas:

- `requirements-review-baseline.lock`;
- `kernel/tests/test_review_baseline.py`;
- a local-only dependency qualifier and hostile tests under `conformance/`;
- a mechanically regenerated `conformance/review_baseline_test_inventory.json`
  if test node IDs change;
- `conformance/REVIEW_BASELINE.md` and this RFC.

No workflow or publisher-policy file belongs to the in-boundary slice.
Discovering a need to change one is a stop and separate Delivery proposal.

## 12. Qualification and hostile tests

A later implementation must bind the wheel filename, size, raw digest, embedded
name/version/tag/metadata, non-extra dependency set, installed implementation
file digests, canonicalization vector, target lock digest and complete target
installed array/digest.

Hostile controls must refuse:

- absent, duplicate, renamed, differently versioned or differently hashed lock
  entries;
- wrong wheel bytes, embedded metadata, tag or installed module bytes;
- missing `rfc8785`, extra distributions, wrong versions or wrong canonical
  installed-set digest;
- failed `pip check`, non-empty missing/mismatched data or unexpected packages;
- evidence from the wrong commit, tree, policy, run attempt or artifact;
- a candidate pull-request result presented as authoritative adopted-policy
  evidence.

## 13. Future completion evidence

For one exact adopted `main` commit `T`, a later accepted implementation must
show:

1. GitHub/Git binds `T` to the intended reviewed head, parents and tree.
2. Main-push admission binds source, execution, workflow and policy SHAs to
   `T`, with clean and unchanged Git state.
3. Both complete baselines report dependency-lock SHA-256
   `8593b897470c797ae6029420d2c86843dc50a9ff4d6cb8a505fb3791114fff74`,
   unchanged package-manager lock, the identical 51-item installed array and
   digest `2e5ad948974eed282b0f8b640b67f3888779438a911021acce6c28daa739b984`,
   empty mismatch maps and passing `pip check`.
4. The tracked test inventory passes twice without failures, skips,
   deselections or unavailable cases; strict equivalence passes.
5. Platform and both native verifier lanes pass and bind their provisional
   archives and ticket to the same source run/attempt.
6. The unchanged publisher authenticates policy, source, ticket, artifact IDs
   and downloaded archive digests and uploads its receipt last.
7. The receipt directly binds `T` through admission and workflow SHAs,
   run/attempt IDs and artifact IDs/digests. Git/GitHub separately establishes
   the tree/parents and original decision messages establish authority. Receipt
   plus authenticated artifact contents collectively establish dependency
   evidence.

## 14. Recovery and reapproval

A real failure, missing automatic acceptance, unexpected publication, changed
route, publisher-authority need, new protected asset, expanded effect, changed
named pull request or changed decision-level invariant stops work. It requires
a new decision version or separate Delivery as applicable.

No failure authorizes a rerun, repair in place, override or revert. Recovery and
revert require their own current evidence and authority.

## 15. Design-opening plan and limits

The approved opening, if any, is limited to one Delivery issue, branch
`design/rfc8785-trusted-baseline-adoption`, one push, one draft pull request and
this single RFC file.

The issue body must not contain a bot mention. The non-main branch push starts
no workflow. Opening the draft is expected to start, once each:

- `pull-request-lightweight / package and workflow policy`, maximum 10 standard
  x64 runner-minutes;
- `reviewed-head baseline gate / gate`, maximum 5 standard x64 runner-minutes,
  with executor dispatch false;
- `evidence-publication / authenticate exact producer run and publication
  ticket`, maximum 10 standard x64 runner-minutes, with publication false;
- `claude-review / review`, maximum 30 standard x64 runner-minutes using the
  already configured Claude plan.

The cap is 55 standard x64 runner-minutes, one automatic attempt per job, one
existing-plan Claude review attempt, no purchase or top-up, and zero additional
paid spend. Public-repository standard runner use is expected to have no
incremental charge, but account balances and Claude quota are not repository
settings and are not claimed. If the limit cannot be honored, stop before
opening.

There is no admission comment, ready transition, manual dispatch or rerun. The
expensive executor, native verifier and authoritative publisher must skip. An
unexpected job, artifact publication, automatic failure or review Blocker
stops further action and is reported without a repair push.

## 16. Decision status

No route is selected. No semantic implementation card is live merely because
this RFC exists. The draft remains open and design-only after its initial
review. Only after Phase A reaches zero Blockers may DECISIONS present the
separate complete route card to the owner.

The governing process is the
[Delivery Protocol](../development/DELIVERY_PROTOCOL.md). The existing
[review-baseline documentation](../../conformance/REVIEW_BASELINE.md) remains
authoritative for current behavior.
