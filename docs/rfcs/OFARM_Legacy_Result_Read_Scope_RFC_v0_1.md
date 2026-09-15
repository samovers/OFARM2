# Legacy result and trace read scope

Status: **Phase A proposal; implementation is not approved**.
Decision identity: `OFARM2-LEGACY-RESULT-READ-SCOPE-001`, version 2.
Delivery: [#394](https://github.com/samovers/OFARM2/issues/394), under #179.
Draft implementation PR: [#395](https://github.com/samovers/OFARM2/pull/395).
Related broader authorization work: [#177](https://github.com/samovers/OFARM2/issues/177).
Base: `47610badaf171bee7ac83c3430bad561073c7e14`, tree
`b7e94ea19ad56fe8db9320cadea044263dc37997` (merged PR #393).
This is design evidence, not approval, OFARM law, or executed candidate evidence.

Version 2 corrects [B1](https://github.com/samovers/OFARM2/pull/395#pullrequestreview-5214770925):
both replay branches must prove an index-bound original `NEW_REQUEST`.
A conflicting receipt with a missing original index now explicitly remains
unreadable, including historical receipts that version 1 could have admitted
through request/event links alone. No version-1 implementation approval exists.

## Problem, capability and boundary

An explicit nonempty FIELD-only submission retains those scopes on its event
and ingress request. The legacy record reader recognizes FARM scopes, so it
cannot identify a farm for the commit result or promotion trace and returns
403 before evaluating a legitimate reader's grant. Empty or omitted scopes
receive a FARM default and are not this counterexample. PR #393 described this
limitation; its completed documentation boundary is not reopened here.

Deliver one capability: an authorized reader can retrieve the immutable result
and trace of a validated FIELD-only operation or observation attempt, including
its matching replay, through the existing legacy GET route. A later evidence
or acceptance refusal does not disqualify an otherwise validated attempt.
Early refusals and conflicting replays have the explicit limits below.

The primary trust boundary is **farm resolution for legacy result/trace read
authorization**. This is high-risk: choosing the wrong farm could expose a
record to someone who only holds permission on another farm. The containment
rule is a closed, consistent stored relationship followed by the existing fresh
read decision. Association never supplies current permission.

## Authority and threat model

| Owner | Responsibility |
| --- | --- |
| Task user | This semantic decision and later exact-head merge authorization |
| Existing transport | Resolve an active Party; bind commit actor; no new credentials |
| Existing Store | Tenant-visible immutable records and append-only idempotency index |
| Existing commit pipeline | Server-authored links, initial authority decision and validation history |
| Result/trace resolver | Establish only the farm association described below; fail closed |
| Existing `evaluate_read` | Fresh `RECEIVE_READ_DATA` / `QUERY_READ`, current grants, sharing and revocation |
| #177 | General provenance, complete sharing restrictions, typed permission/redaction and atomic protected reads |
| Review, CI, publisher, GitHub | Findings, mechanical evidence/custody and native PR state; no semantic approval |

Protected assets are result/trace payload confidentiality, tenant separation,
immutable history and present read authority. Callers may choose submission
fields, farm/field references, idempotency keys and requested record IDs, and
may hold legitimate permission on another farm. Submitted FARM identifiers and
historical `ALLOW` alone are not sufficient for the new FIELD-only path.
Changing server code, arbitrary database writes and host compromise are outside
the attacker model. Malformed stored-link fixtures are defensive tests, not
claims that those records can be emitted through the supported HTTP route.

The reachable counterexample is legacy `POST /commit` then
`GET /records/{record_id}` through `kernel/legacy_m1/api.py`. Production governed
routes remain closed in `kernel/api.py`; no production exploit, activation or
readiness claim is made. Production negative checks must show that closure.

## Existing evidence and the selected provenance

`AuthorityGate` persists its request/trace/result and attaches the result to the
promotion trace. The request's `target.scope` names the evaluated FARM, copied
from submission `farmRef`. This happens **before** validation, so the target
alone does not establish containment. The common `ScopeContainmentValidator`
checks submitted scopes; successful operation/observation validation records
`VALIDATION / PASS`. These two existing decisions together establish the
association used for the new FIELD-only path; neither decides a later read.

`PromotionTraceWriter` stores the result, trace and idempotency claim in the
commit transaction. `ReplayWriter` stores fresh result/request/trace records
but no new promotion authority decision. The existing tenant/key idempotency
entry is append-only and points directly to the original result, even after
many replays. Reuse that one index lookup for both replay branches; add no reverse
search, new record, field-ownership lookup, schema or durable cache.

The prior six fictional HTTP probes passed on CPython 3.12.13/PostgreSQL 17.10
and reproduced FIELD-only operation 403 versus FARM+FIELD 200. FIELD-only
observation was not repeated in those six probes. Earlier reviewer observation
measurements used a different environment. Neither is #394 implementation
evidence. This proposal adds source inspection only and does not restart the audit.

## Smallest complete implementation

Give exactly two root kinds a bounded resolver:
`ofarm.commitingressresult.v0.1` and `ofarm.promotiontrace.v0.1`.
The GET route must dispatch them to it before the generic helper, with no
generic fallback after it refuses. Other record kinds keep their current path.
Use one small legacy-local module if that makes the two consumers' shared
logic easier to inspect; no resolver registry, framework or new policy service.

1. A result names its trace; a trace is already the starting point. Load only
   the expected typed trace, ingress request and semantic event. Check row kind,
   payload schema/id and the forward identities that bind result, trace,
   request and event. Request/event, class/family, disposition and outcome must
   agree where those fields exist. A referenced wrong kind, absent record,
   malformed identity or disagreement denies the read.
2. Collect explicit FARM associations from the owned event/request scope lists.
   For an ordinary request, those lists must agree. A single consistent FARM
   preserves existing FARM and FARM+FIELD behavior, including early refusals.
   Multiple different farms are ambiguous and deny even if the reader has both
   grants. If the trace names an authority result, its typed request FARM must
   agree with any explicit FARM; a broken named authority link cannot be rescued
   by explicit scopes. Historical records with no authority link may still use
   the consistent explicit-FARM path.
3. Without an explicit FARM, the new path is limited to ordinary `NEW_REQUEST`
   `OPERATION_CLAIM` and `OBSERVATION_ASSERTION` with nonempty, well-shaped
   FIELD-only event/request scopes. Other FARM-less scope types stay denied.
   Require one initial
   `AUTHORITY / ALLOW` followed by `VALIDATION / PASS`, with the authority
   entry naming the trace's authority result and its request. That result and
   request must be the expected kinds, agree on `PROMOTION` and the existing
   class-to-action mapping, and name the ingress actor and one FARM target.
   Result `ALLOW` must agree with the gate entry. Do not use a later review,
   attribution or read authorization decision. Missing proof means 403.
   These records establish this attempt's evaluated and validated farm, not
   exclusive ownership of each field. Do not reread present field identities
   or repeat containment policy: the immutable recorded validation is the
   accepted historical evidence, and the initial authority target is the
   single farm for this attempt.
4. For **both matching and conflicting replays**, first bind the attempt's
   result/trace/request and original event. Use its stored key once with
   `Store.idempotency_lookup`. The index must bind `replayOfRequestId` to the
   original request and its `result_record_id` to the typed original result.
   Load that result's trace and request through step 1. Require both original
   result and trace to say `NEW_REQUEST`; an ingress request alone has no
   replay disposition and cannot prove this. Bind index, original request,
   result and trace IDs, key, event and class/family where carried. The original
   request's nonempty server-generated digest must equal the index digest.
   Missing index, inconsistent proof or an original that is itself a replay
   means 403; no second replay hop or reverse search is allowed.

   For a **matching** replay, additionally require the attempt's nonempty
   digest to equal the original/index digest, producing-bundle equality as
   below, identical request scopes and agreement of reused output references
   where carried. Resolve the bound original using steps 2–3.
5. A **conflicting** replay uses the same original-index proof in step 4 but
   gains no FIELD-only resolution. Resolve only one consistent explicit FARM
   through the bound original's request/event (step 2) and the attempt's own
   request. A foreign FARM, absent original FARM or malformed link denies.
   Do not impose matching-replay digest or producing-bundle equality on this
   branch, or require the digests to differ: an identical body in a different
   bundle is a valid conflict. This preserves a correctly linked same-farm
   explicit-FARM conflict receipt without treating it as acceptance. Historical
   conflicting receipts missing the index are denied, not rescued by scopes.
6. All lookups use the existing tenant-bound Store. Records written together
   must agree on their stored tenant/bundle receipt; matching replay and the
   original/index also agree on producing bundle. Historical producing bundles
   need not equal the active Store bundle: same-tenant history remains readable.
   Bind the original request/result/trace, original event, any used authority
   records and index to the original producing receipt. Bind the replay
   request/result/trace to its attempt receipt. The shared event belongs to the
   original group, not the attempt group. Conflicting replays can have different
   attempt and original bundles; their explicit-FARM-only rule still applies.
7. Return one resolved FARM or unresolved. The existing route then makes and
   persists the fresh read decision and returns the original record only on
   permission. Do not cache it or reuse promotion authority as access authority.

This is fixed typed traversal, not recursive graph discovery. No arbitrary
`semanticEventRef`, `requestId` or other reference on a terminal record is
followed. Repeated/cyclic identities or an original that is itself a replay
deny; a two-node cycle cannot grow the traversal. Valid repeated references
such as replay and original pointing at the same event are expected equality
checks, not extra traversal. The broader helper's behavior for other kinds is
unchanged and remains #177's responsibility.

## Provenance and outcome matrix

All 200 outcomes below also require a fresh read permission. Otherwise use the
existing 403 `PERMISSION_REDACTED`, without protected payload in the response.

| Attempt and anchors | Accepted source | Required result/trace GET |
| --- | --- | --- |
| FIELD-only operation with initial ALLOW + validation PASS; accepted, queued or later refused | Bound ordinary authority request FARM plus recorded validation | 200, unchanged payload |
| FIELD-only observation with initial ALLOW + validation PASS; retained capture or later refusal | Same source; observation remains unaccepted | 200, unchanged payload |
| Either FIELD-only class denied at authority or refused before validation PASS | No qualified containment history | 403, including when the reader separately has read permission |
| Either qualified FIELD-only class, identical body/key matching replay | One append-only index hop to the qualified original | 200 for the new replay result and trace, not merely the original |
| FIELD-only original with conflicting replay, including a newly supplied FARM hint | No accepted conflicting-attempt FIELD-only source | 403 |
| Consistent explicit FARM / FARM+FIELD, including omitted/empty raw scopes that default to FARM | Typed event/request explicit FARM; validate any named authority link | Existing read permission outcome retained |
| Matching replay of the preceding explicit-FARM row | Bound original/index and matching request identity | 200 if currently permitted; incomplete historical replay proof stays denied |
| Explicit-FARM original, same-farm explicit-FARM payload or bundle conflict, including identical body in another bundle | One index-bound original NEW_REQUEST plus consistent original/attempt FARM | 200 if currently permitted; commit outcome remains DENY |
| Conflicting receipt points to a replay request as its supposed original, or lacks its original index | No proved original NEW_REQUEST | 403 even when request/event/key/class/FARM values agree |
| Conflicting replay with different original/attempt farms, or inconsistent ordinary associations | No unambiguous source | 403 even with both farms' grants |
| Pre-existing same-tenant records with the complete selected proof | Same rules; no backfill or current-bundle equality requirement | Same outcome as new records |
| Old FIELD-only records missing links, validation proof or required replay index | No invented relationship or inferred current field ownership | 403 |

## #177 ownership and non-effects

**#394 may precede #177.** It owns only the two legacy receipt kinds and their
closed farm association. It consumes the current `evaluate_read` interface.
#177 retains general durable tenant/scope/provenance resolution, all sharing
dimensions and grantor authority, typed redaction plans, and authority plus
protected read in one UnitOfWork. No part of #177 is claimed complete here.

In particular, the current route reads rows, evaluates permission and persists
receipts in separate operations. A completed revocation must deny the next GET;
this proposal does not fix or claim atomicity against a concurrent revocation.
The existing evaluator's incomplete sharing semantics also remain a material
limit, even for newly resolvable records. It remains the sole permission path.

No change to grants, sharing rules, subject ownership, field identities,
idempotency/replay emission, acceptance eligibility, corrections, contracts,
stored records, SQL/schema, transaction ownership, signing, custody, audit,
production routes or deployment. No changes to generic record reads, views,
exports, field-parent traversal or public/Party access rules.

Provisional posture: a deliberately limited legacy development repair. It is
acceptable while production governed reads remain closed and the stated
limitations are explicit. Extending it to other roots, promising complete
sharing or atomic reads, or enabling production requires separate approved
work. #177 should absorb or replace this narrow association logic when its
general provenance capability is delivered; do not maintain parallel policies.

## Invariants and verification after approval

| ID | Invariant and focused negative/control evidence |
| --- | --- |
| R01 | Both ordinary qualified FIELD-only classes return exact original result/trace payloads to a permitted reader; operation acceptance and observation capture remain unchanged. Base reproduces 403, candidate returns 200. |
| R02 | Typed, consistent server-authored provenance is required. Wrong kind/id, missing links, mixed farms, absent PASS and mismatched authority decision fail closed; another farm's granted reader cannot obtain the payload. |
| R03 | Both replay branches use exactly one index-bound original NEW_REQUEST result/trace. Missing/corrupt index, inconsistent original identity/digest and replay chains deny. Matching additionally requires attempt/original digest and bundle equality. Conflicting gains no FIELD-only access; correctly bound same-farm explicit-FARM conflicts remain readable, including equal-body/different-bundle attempts. Missing-index historical conflicts deny. |
| R04 | Consistent FARM/FARM+FIELD/default-scope reads with the selected complete proof and other record-kind paths keep their permission outcomes. Ambiguous result/trace associations and incomplete historical replay proof intentionally become denied, even if the old first-link helper returned a farm. |
| R05 | Every resolved read uses fresh existing permission and receipts. A dedicated reader with no alternative permission reads successfully, then loses a direct grant or SharingGrant by completed revocation and receives 403 on the next GET. Old ALLOW cannot override this. |
| R06 | Existing same-tenant history with sufficient proof remains readable across active bundle changes. Foreign-tenant links are unavailable; incomplete historical proof stays denied. All stored payloads/edges/idempotency entries remain unchanged apart from existing fresh read-decision receipts. |
| R07 | Traversal is bounded to the named kinds and one proved original attempt for both replay branches. Self-links, two-node cycles, a replay request substituted for the original, and wrong-kind reference redirection terminate as unresolved/403 without a 500 or arbitrary graph search. |
| R08 | No new authority evaluator, durable state, transaction owner or activated production endpoint. Production GET stays closed; package/architecture, focused tests, reviewed implementation head and required hosted evidence pass. |

Run real legacy HTTP cases using fictional `kernel.demo` records and existing
function-isolated disposable PostgreSQL fixtures. Cover the matrix for both
operation and observation, including early authority refusal, validation
refusal, later refusal, direct/FARM controls and new replay wrapper IDs.
Use separate fictional actors for successful read, wrong-farm read, no grant,
and sequential revocation with no alternative grant/delegation/sharing path.
Malformed graph shapes may use clearly labelled defensive test doubles;
they do not replace real HTTP/Store positive and denial cases.

B1's defensive fixture has an original O and matching-replay request R with the
same key, event, class and explicit FARM. A conflicting result/trace C both name
R as `replayOfRequestId`. Require 403 for each C root: R's request shape cannot
replace index proof of O. Also test a missing-index historical conflict as 403.
Positive real-writer controls must include a correctly linked same-farm payload
conflict and an identical-body/different-bundle conflict with equal digests;
both remain readable with current permission and retain their DENY outcome.
These are planned tests, not executed Phase A evidence.

For history, create real original attempts/replays using unmodified base bytes
in an owned disposable database, then run the candidate against the retained
database and compare payload/edge/index snapshots. Do not fabricate accepted
history or weaken guards. Include an existing cross-bundle history fixture or
the accepted bundle setup path; do not bypass Store binding to construct it.

Expected implementation areas: `kernel/legacy_m1/api.py`, one small
legacy-local read-scope module if needed, focused legacy read tests, this RFC,
the reader limitation in `docs/REVIEW_DISPUTE_SEMANTICS.md`, and generated test
inventory when tests are added. Store, authority and emitters are consumers of
existing interfaces, not planned edits. These are scope predictions, not path
approval tokens. Runtime scope expansion requires a new semantic decision.

Before each commit run the mandatory package/architecture/temporal check under
CPython 3.12.13. Implementation evidence uses PostgreSQL 17.10 and the pinned
review baseline environment. After focused checks, require exact-head content
review with zero Blockers before admission, fresh hosted baseline/publication
and final receipt verification. No expensive baseline is requested for Phase A.
All failures/skips and evidence limits remain visible. Merge needs a later
complete packet and exact-head same-task authorization.

## Code excellence and decision control

EXC-001/002: one result/trace association path feeds one existing permission
evaluator; the existing immutable records/index remain the only durable facts.
EXC-003: R01–R07 map directly to the bounded resolver and real route tests; R08
to scope, closure and existing checks. EXC-004: remove result/trace use of the
generic recursive route; no fallback remains for these roots. EXC-005: a small
shared resolver serves these two actual roots; no speculative framework.
EXC-006: a single added recursive reference is smaller in text but lacks kind,
identity, conflict and replay guarantees. Denying every FIELD-only retry leaves
the ordinary client retry unusable. Both replay branches share one existing
append-only lookup to prove the original; no duplicate resolver or new state is
needed. Direct request/event checks alone cannot distinguish a replay request
from the original and cannot meet R03/R07.

The task card must name the already-created draft PR after Phase A review has
zero Blockers. A change to capability, R01–R08, authority, effects/non-effects,
boundary, named PR or production posture requires a new decision version and
exact later same-task approval. Reviewer comments and prior PR approvals do not
authorize implementation. Next: review this design, then present that card.
