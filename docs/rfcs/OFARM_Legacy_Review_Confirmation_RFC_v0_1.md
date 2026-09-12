# Legacy review confirmation, version 0.1

Status: approved version-1 implementation decision for
[PR #384](https://github.com/samovers/OFARM2/pull/384).
Delivery: [#383](https://github.com/samovers/OFARM2/issues/383), a bounded child
of Tracking Epic #180 under #167. Decision:
`OFARM2-LEGACY-REVIEW-CONFIRMATION-001`, version 1. The draft PR description
records review and approval navigation; only the ordered same-task user message
can supply approval under root `AGENTS.md`. In task
`01a07cc8-4157-7b33-a0ca-becb772e0e8b`, the complete card
`msg_0d813f8071772f9a016aa3d86fad3487d283546b17f4ff3d58` precedes exact approval
`msg_01a0900a-37f8-74c1-b1d9-53951b117473`. Both original items were directly
retrieved in that order. These identifiers are navigation, not substitute
approval or merge authority.

## Problem, capability and boundary

Recorded audit K-03 identifies Python truthiness being treated as a review act
by legacy `/commit`. At merged main
`b6017da1dbfac80b5c2e98641aaa34d96691d087`, a valid operation submitted with
`"false"`, `1` or `["confirm"]` can produce an accepted consequence. Capturing
an arbitrary JSON value must not establish explicit acceptance confirmation.

The capability is strict optional boolean confirmation before governed legacy
ingress. The single primary trust boundary is **legacy review-confirmation
admission**: untrusted submission input becomes a confirmation consumed by the
existing promotion gate. This is high-risk because the input participates in
accepted-force decisions. It does not change who can assert, review or retire
state. K-02 is completed by PR #380; this is new Delivery work, not recovery of
that merged PR or a restart of the audit.

## Authority and containment

Canonical OFARM owns the distinction between capture, review and accepted
consequence. Constitution RC2.1 sections 10.14 and 11.5-11.6 and the accepted
Source Truth Record Closure RFC sections 4.2-4.3 require accountable review
before accepted force. They do not prescribe a Python type or HTTP status.
The boolean/null/transport behavior below is this implementation decision,
not new canonical law. `docs/REVIEW_DISPUTE_SEMANTICS.md` identifies
`confirmAccept` as an internal submission field, not a property of the closed
`CommitIngressRequest` contract. D8 and D17 remain unchanged.

| Owner | Authority retained |
| --- | --- |
| Existing transport principal resolution | Authentication and actor binding, including the existing 403 precedence |
| Existing ingress parser | Shape validation before the pipeline transaction; it does not grant review authority |
| Existing authority evaluator, validators and policies | Assertion/review/retirement rights, scope, evidence and self-review eligibility |
| Existing promotion gate and emitter | Confirmation consumption, named reviewer, server decision time and accepted records |
| Existing Store | Transaction ownership, persistence and replay; no database authority change |
| Task user | Semantic decision and later exact-head merge authorization |
| Reviewers, CI, publisher and GitHub | Findings, mechanical evidence, publication custody and native PR state; no user approval |

Protected assets are the distinction between draft capture and accepted force,
accountable review records, immutable history and valid replay results. The
trusted implementation is the parser-to-gate path and its existing identity,
authority, evidence and storage services. Request bodies, confirmation values,
body-named reviewers and idempotency keys are untrusted, even from a caller
holding otherwise sufficient assertion and review rights. Arbitrary code
execution, in-process object mutation by compromised code, direct database
writes, compromised keys and database-owner compromise are excluded.

The primary risk is treating a truthy transport value as deliberate acceptance.
Contain it with one type check before transaction entry and one exact-true
interpretation at the existing review gate. A valid confirmation remains
necessary only on the existing direct-confirmation path and is never sufficient
authority to accept.

## Input contract and ordering

| Input | Proposed interpretation |
| --- | --- |
| Field omitted | Valid non-confirming input; preserve existing draft/queue behavior |
| Literal JSON `false` | Valid non-confirming input; preserve existing draft/queue behavior |
| Literal JSON `true` | Confirmation supplied; all existing gates still apply |
| Present null, string, number, array or object | Malformed input, including empty/zero values; never coerce or silently treat it as a draft |

The optional-field type rule applies to every submitted commit class, including
non-promoting and governance submissions that otherwise ignore the field.
No class gains a required confirmation field. Existing queued review adapters
omit it and continue to operate without it. No alias such as `confirmReview`
is introduced.

Keep authentication and actor binding first at HTTP. Then, inside the existing
`parse_ingress_header`, reject a present non-boolean with the existing
payload-free `IngressHeaderViolation`. `GatePipeline.commit` already invokes
that parser before opening the transaction. The existing HTTP mapping remains
422 with exactly `{"detail":"malformed ingress submission header"}` after
identity binding succeeds; raw supplied values are not reflected.

Malformed confirmation therefore causes no pipeline transaction, idempotency
lookup, authority evaluation, request/trace/replay record, assertion, review,
consequence, supersession or materialization. An already accepted idempotency
key does not turn malformed input into a valid replay. Existing transport
authentication behavior and its own effects are outside this claim.

Valid requests continue through the unchanged transaction and lookup ordering.
Do not mutate or normalize the submission, change source-digest calculation,
or collapse omission and false into one input identity. Otherwise valid
omitted/false operation claims can still write their existing pending assertion
and inert intent; they do not gain a direct accepted consequence. Existing
routing or refusal gates may determine a different non-acceptance outcome.

At `ReviewPromotionGate.run`, derive one local
`confirmed = sub.get("confirmAccept") is True` and use it for all four existing
confirmation consumers: compliance routing, bounded structural routing,
body-named distinct-reviewer routing and the final direct-confirmation branch.
Do not add a context field, stored flag, policy table or second validator.
Queued accept/reject/contest selection and all downstream acceptance checks
remain unchanged.

## Invariants and focused proof

Normal legacy HTTP requests are reachable through the supported development
and conformance adapter; direct callers enter through `GatePipeline.commit`.
Production governed HTTP routes remain closed. The negative cases below use
the real supported HTTP path where available and separately preserve production
closure; they do not claim exposure of a deployed production route.

| ID | Invariant | Owning seam and falsifiable negative/compatibility evidence |
| --- | --- | --- |
| R01 | Only omission and actual booleans are well-formed confirmation input, for every commit class. | Existing parser: null, false/true strings, empty string, integer/float zero and one, empty/non-empty arrays and objects reject. Test supported commit classes and direct callers; omitted/false/true remain valid shapes. |
| R02 | Malformed input stops before governed side effects or replay, with the existing safe HTTP response and actor-binding precedence. | Parser and existing route: a no-transaction Store proves the early boundary; real HTTP/PostgreSQL snapshots prove no governed record changes. Reuse an accepted key with malformed confirmation and require 422 without lookup/replay writes. A mismatched actor still receives existing 403. |
| R03 | Valid non-confirming input and valid replay retain their existing meaning and raw digest. | Pipeline/gate: omitted and false valid operation controls remain pending/draft; verify distinct raw input digests, repeated valid-key behavior and no accepted records. |
| R04 | Literal true cannot bypass existing acceptance requirements or accountability. | Review gate: otherwise sufficient positive operation/structure controls accept; true with missing review authority, insufficient evidence, disallowed existing self-review or a body-named distinct reviewer cannot directly accept. Keep compatible correction retirement-authority negatives and named reviewer/server-time checks. |
| R05 | Queue decisions need no new flag and retain their existing validation and authority. | Existing review adapters and tests: accept/reject/contest without the field retain their outcomes; invalid review action and unauthorized/self-review negatives remain governed refusals under current rules. |
| R06 | History, lineage, transaction ownership and production closure remain unchanged. | Real Store comparisons around malformed requests and valid replay show prior bytes unchanged; existing correction/dispute and production-activation tests preserve their negative controls. Diff inspection confirms no independent authority or transaction changes. |

## Smallest complete slice and code excellence

Expected edits are `kernel/stages.py`, focused tests in the existing ingress
module and an owned review-confirmation module if useful, the review-semantics
documentation, this RFC and the prescribed collected-test inventory. Existing
conformance/review/correction tests provide compatibility coverage. Test and
documentation discovery within this boundary does not itself expand approval.
The selected runtime-bundle catalog does not include `stages.py` or `gates.py`;
no bundle component or capability claim change is predicted. There is no schema,
migration or fixture-authority companion to split into another PR.

EXC-001/002: the existing pre-transaction parser owns input shape, and one
function-local value gives the four current consumers the same literal-true
meaning. There is no new stored or cached authority, duplicate registry or
validation framework. EXC-003: R01-R06 trace directly to the owning seams and
negative controls above. EXC-004: remove the four owned truthiness reads when
replacing them; no compatibility fallback remains. EXC-005: add no abstraction.
EXC-006: a late `is True` check alone would retain malformed-input writes and
replay before the review stage; HTTP-only typing would miss direct pipeline
callers; `== True` would still accept integer one. The existing early parser
plus local exact-true interpretation is the smallest complete remedy.
EXC-007: naming and layout preferences are not blockers.

## Evidence, verification and decision limits

On the baseline above, 15 real HTTP requests using fictional demo fixtures and
the real pipeline/Store all returned 200. Six malformed non-booleans accepted:
`"false"`, `"true"`, `1`, `1.0`, `["confirm"]` and `{"confirm":true}`. Literal
true accepted; omission and false retained drafts. Falsey malformed values
also retained drafts instead of rejecting. There were no unreachable
authoritative records. This proves the defect, not remediation success.

The local run used CPython 3.12.13, Darwin ARM64 and PostgreSQL 17.10 ARM64 in one
uniquely identified disposable tmpfs container. One known Starlette/httpx
deprecation warning occurred. An initial missing-psycopg import failure occurred
before database access; a verified existing environment completed the run.
The container was removed after evidence capture and unrelated resources were
preserved. Local `reproduction.json` SHA-256:
`9d2154658ecd1ffcd4af3b8c33f5db778e09be43167b7f5725fa64b4cedf3469`.
This is supplemental evidence, not the prescribed Linux x86_64 baseline.

The [Phase A review](https://github.com/samovers/OFARM2/pull/384#issuecomment-5633091839)
reported zero design Blockers before the complete same-task card and approval.
Implementation uses the existing parser and gate with four net runtime lines
added and no new abstraction. Focused local execution passed 91 parser/transport
cases, 21 real HTTP/Store cases and 50 existing compatibility cases: 162 distinct
cases. The HTTP matrix proves malformed fresh requests and accepted-key replays
leave all nine governed/derived/evidence tables unchanged. Valid controls retain
drafts, exact raw digests, replay receipts, reviewer identity and server times;
authority, evidence, correction, queue and production-closure controls pass.
These runs use the same supplemental platform above and each reports the known
Starlette/httpx warning. Generated capability artifacts match the committed
files; no capability manifest or selected bundle component changed.

Run mandatory package/architecture and applicable cheap checks before commit,
and regenerate the test inventory using the prescribed runner.
Collection is not execution. Obtain exact-head review before existing baseline
admission, hosted baselines/native checks and trusted publication. Report the
existing extraction diagnostic honestly under its applicable requirements.
Prepare the final exact-head packet only after applicable gates pass, then
yield for later merge authorization. Never reuse PR #380/#382 approval or
evidence as approval or fresh verification of this PR.

No canonical/reference/frozen-contract, principal, grant/action, signing,
custody, database-role, transaction-ownership, audit or publication change is
permitted. No production activation, deployment, historical repair, new review
right, subject-validation expansion, K-04 self-review fix or broader #180/#184
lifecycle/graph work is included. Scope stays inside the named boundary.

The boolean contract is intended to endure; the legacy development/conformance
environment remains provisional before deployment. Different accepted input
semantics, evidence that the shared parser fails to mediate a supported entry
path, or a production integration requirement would require redesign or a
separate Delivery, not a fallback. Future typed production ingress must be
approved within its own activation boundary. A change to capability, boundary,
authority, effects/non-effects, R01-R06, named PR, irreversible behavior or
deployment posture requires a new decision version and approval.

Next: obtain exact-head implementation review and the existing admitted hosted
evidence, then present the final packet for a separate user merge decision.
