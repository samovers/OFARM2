# Physical transaction outcome recovery — Phase A candidate v1

**Disposition: ready for independent design review; not yet cleared for an implementation card.** Deliver a real, bounded recovery operation for the accepted tenant UnitOfWork after its COMMIT response is lost. Use the original database-derived full xid8 and the existing immutable governed batch ledger. No second journal, new ticket relation, new role, capability signer, clock policy or canonical action contract is necessary for this bounded capability.

Primary trust boundary: **physical transaction outcome integrity**. Intended PR boundary: manager-owned capture of original physical identity, one private status-observation path, integration into current finalization failure handling, meaningful PostgreSQL tests and necessary documentation. Scope is one complete capability under the current accepted tenant architecture. It does not admit a logical operation or close the future transaction profile's durable cross-process uncertainty fence.

## Problem, consumer and supported failure horizon

At OFARM2 main `bccb7a1f0cd5d4c81d21898e4b0978830904b716`, `TenantUnitOfWorkManager._run()` closes the exposed unit, calls `connection.commit()`, and discards the connection with `FINALIZATION_UNKNOWN` after a commit exception or an unproven final state. The manager already owns the original transaction and its batch allocator. A committed response-loss case is therefore distinguishable in principle, but no owned observation path currently recovers it.

The new path is:

`ApplicationRuntime.tenant_unit_of_work(principal)` → existing security-audit composition → accepted manager → original bound transaction and optional real batch → finalization → private physical-outcome observer on a different freshly bound connection.

The original process, manager instance and trusted recovery context must survive. No caller may reconstruct a context from request IDs, xid strings, JSON, a receipt or a batch name. Process loss, manager/pool replacement, missing identity, disallowed service continuity, old unavailable transaction status without matching retained batch proof, and failed fresh binding return an explicitly unresolved result. This finite horizon is deliberate. Successful recovery of real COMMITTED and ABORTED cases makes the capability useful now; storing an in-memory type alone is not delivery.

The first production-composition consumer is the current manager's commit-error branch. It performs at most one immediate bounded observation and preserves the original failure qualification together with the observed physical fact. An internal caller holding the same trusted context may request another bounded observation later. It cannot re-enter, commit again, resubmit the command or allocate a new attempt through this interface. Public HTTP routes and public error vocabulary remain unchanged. A recovered physical commit never becomes a domain-success response by itself.

## Permitted effects, non-effects and provisional posture

Permitted effects: capture facts from the original live connection; close/discard it through the existing owner; obtain a fresh legitimate TenantBinding; read exact physical status and existing batch metadata; return a private typed observation; preserve pool cleanup and audit routing. The observer rolls back its own temporary binder transaction. It writes no business records, status journal, receipt or canonical evidence.

Non-effects: no logical operation key or attempt sequence; no NO_EFFECT/retry consequence; no ALLOW; no protected-effect/domain verdict; no decision consumption; no 30-second cutoff or M0/T proof; no scheduled TERMINATE guard; no cross-process recovery, history continuity or restore admission; no release of saved domain content. No preallocated row is proposed.

The support horizon is provisional pre-deployment engineering, not provisional truth. Extend it only when a real consumer requires durable identity/status retention and a separately reviewed design supplies that complete capability. Do not grow a generic transaction platform in anticipation. A requirement to authorize another logical attempt after process loss, to repair history, or to provide a permanent rollback proof invalidates this scope and returns to the appropriate owner.

## Authority and threat map

| Fact or action | Sole authority / treatment |
| --- | --- |
| Authenticated principal, tenant and Party attribution | Existing identity/principal and binder owners; the observer obtains a fresh binding, preserves exact equality and rejects incompatible tenant/principal/registration identity |
| Original top-level xid8 | `pg_current_xact_id()` on the original bound connection before yielding work; the existing returned batch full_xid must equal it |
| Original backend | Database-derived PID, backend-start identity and challenge/binder context, retained privately. PID alone is never the key |
| Installation/service identity | The existing admitted manager/pool and binder audience/installation context. Matching audience does not prove clone/PITR continuity; existing refusal policy remains controlling |
| Physical transaction outcome | PostgreSQL `pg_xact_status(original_xid8)`, or an exact committed original batch observed independently under enforced database provenance |
| Batch occurrence | Exact existing `governed_write_batch` row, including original full_xid, compared to the captured batch tuple under a fresh bound read |
| Semantic success, retry and disclosure | Not decided here; later/current owning consumers must apply their own contracts |
| Finalization and cancellation | Existing manager only. The exposed unit is closed before possible COMMIT, and the original connection is never returned to work after ambiguity |

Untrusted inputs include external requests, authored batch/request identifiers, caller-reported status, supplied xids, receipt copies, stale capabilities and observations from another manager/tenant. Ordinary application/worker SQL cannot override the database-stamped full xid or mutate the immutable batch. The private observer does not expose arbitrary transaction-status lookup to callers. Arbitrary in-process code execution, database owner/superuser compromise, server corruption and an undeclared physical clone are outside this bounded threat model; no protection from them is claimed.

## Exact identity capture and interface

After successful original binding and before yielding the unit, the manager reads the original top-level `pg_current_xact_id()`, `pg_backend_pid()` and own backend-start identity on that connection. It retains the exact protected tenant/registration identity, authenticated principal equality data, binder audience, capability nonce, manager-instance identity and pool generation. It does not use database wall time for ordering or infer a deadline from binder/challenge time.

The private recovery context contains those immutable facts and, if allocation succeeds, the complete returned batch tuple: tenant_id, batch_id, full_xid, authenticated_principal_ref, governed_operation, request_id, runtime_bundle_digest and knowledge_position. Creation time is descriptive metadata only. Retain the actual source-returned object; never rebuild it from caller arguments. The allocator rejects a returned full_xid that differs from the original captured xid. Request/principal/operation/bundle comparisons remain byte-exact under their accepted contracts.

Proposed private signatures are `capture_physical_context(original_connection, verified_binding, manager_identity)` and `observe_physical_outcome(trusted_context, fresh_principal)`. They are implementation names, not public extensibility points. The manager alone mints and retains contexts; it checks object provenance against its private live-context registry, not merely a dataclass shape or a forgeable boolean. No deserialization, caller clock, connection injection or arbitrary SQL callback is admitted. Registry loss yields UNKNOWN; it creates no durable history.

Return a product with separate fields:

- `physical_status`: COMMITTED, ABORTED or UNKNOWN;
- `batch_observation`: MATCHING_COMMITTED, ABSENT_AT_OBSERVATION, NOT_ALLOCATED, CONFLICT or UNAVAILABLE;
- `basis`: exact original xid/status observation and/or exact retained batch identity, with the observer's own identity kept distinct;
- `integrity_problem`: absent or an explicit contradiction that prevents consumer use;
- `observer_cleanup`: completed or connection discarded; never used to rewrite the original outcome.

These are private physical vocabulary, not new canonical transaction outcomes or public RuntimeProblem codes. In particular, ABORTED is a PostgreSQL transaction fact and not a durable logical NO_EFFECT consequence. COMMITTED with ABSENT_AT_OBSERVATION is valid after a savepoint removed the batch; it is not an assertion that a batch or command succeeded.

The owned context state machine is `CAPTURED → ACTIVE → CLOSED_FOR_FINALIZATION → OBSERVED_TERMINAL | UNRESOLVED`; UNRESOLVED may receive further bounded observations, never return to ACTIVE. A conclusive original COMMITTED or ABORTED fact is retained with its basis for the context's remaining lifetime and is not downgraded by later status unavailability. Contradictory evidence is preserved as an integrity problem. Registry eviction, process loss or pool replacement invalidates future use of the context; it does not change the historical transaction. There is no context-to-new-transaction transition.

## One observation algorithm

1. Require a closed original unit, a manager-owned context, unchanged manager/pool generation and a supported admitted service lineage. Before COMMIT dispatch, ensure the identity capture completed. If capture fails, close/roll back or discard the original and claim only what is proven.
2. After an ambiguous finalization, detach/discard the original connection before observing. Closing a socket does not prove server rollback. There is no second COMMIT, callback, same-context resume or automatic command retry.
3. Check out a different connection through the accepted bounded pool. Begin READ COMMITTED and bind the current authenticated principal through the ordinary capability/binder path. Use a new capability/challenge; never replay the original one. Exact tenant, registration and requesting-principal identity must match; changed lifecycle heads are evaluated by their existing owner rather than silently overwritten in the historical context.
4. Read `pg_xact_status(original_full_xid)` with one fixed parameterized statement. Inputs come only from the trusted context. NULL, an exception or in-progress is not terminal negative evidence.
5. If the context contains an allocated batch, perform a separate fresh READ COMMITTED query for its tenant/batch identity and compare all captured fields including full xid. The database's insertion trigger stamps full_xid and immutability prevents later reassignment. Do not read any protected result payload. If physical status was COMMITTED, this fresh statement follows that terminal observation and avoids a pre-commit absence snapshot.
6. Combine observations using the table below. Do not acquire the tenant write lock: this design never uses lock-plus-absence as a negative proof and needs no additional writer participation. A matching committed batch can be observed even if the earlier status read raced completion. Record the evidence order honestly.
7. Roll back the observer's temporary transaction, prove idle or discard it, and return only fully received/validated observations. A later cleanup exception does not change an already proved original commit. A partial query response supplies no fact. No observer evidence commit is needed, so there is no recursive commit-recovery chain.

| PostgreSQL status | Exact batch observation | Physical conclusion |
| --- | --- | --- |
| committed | matching / absent / not allocated | COMMITTED. Batch occurrence remains its separate observed fact |
| aborted | absent / not allocated | ABORTED. Never infer a logical retry consequence |
| in progress or NULL | matching committed original batch | COMMITTED, using immutable authoritative row provenance; earlier status may have raced the commit |
| in progress or NULL | absent / not allocated / unavailable | UNKNOWN. Original work may still run; old status may be unavailable |
| aborted | matching original committed batch | Preserve both raw observations as a contradiction; return integrity_problem and no usable success/negative conclusion |
| any | same authored batch ID with different xid or mismatched captured fields | CONFLICT, never another transaction's outcome; retain independently established physical status but disallow batch-success use |
| unavailable binding, lost context, partial response, unsupported continuity | any | UNKNOWN; caller-supplied copies do not repair identity or access |

If no batch exists and PostgreSQL has discarded the status, there is no fallback. If the batch is retained but the process loses the trusted context, this interface still refuses caller reconstruction. This is why PS-1 does not close PR26 retention, cross-process discovery or uncertainty-fence obligations.

The native status primitive, its old-status NULL result and top-level xid semantics are documented in [PostgreSQL 17 transaction information](https://www.postgresql.org/docs/17/functions-info.html#FUNCTIONS-PG-SNAPSHOT). The observer's separate-command read order follows [READ COMMITTED semantics](https://www.postgresql.org/docs/17/transaction-iso.html#XACT-READ-COMMITTED). The combination and private support horizon above are this design's proposed use of those primitives, not PostgreSQL guarantees about OFARM outcomes.

## Queued work, live backends, locks and savepoints

The only negative proof is a terminal PostgreSQL abort of the exact original top-level xid. An original transaction still running, including one with queued INSERT/COMMIT work, returns UNKNOWN unless an independently committed matching batch proves later completion. A backend that remains alive can start another transaction, but the new xid cannot match the sealed original context. This observer grants no permission for new work.

The original manager closes allocator/selector callbacks before finalization; its private connection is detached on uncertainty. Existing code cannot reuse the old unit. This is an in-process ownership fence, not a durable logical-operation admission fence. Ordinary SQL actors remain subject to the existing binder, RLS, full-xid stamping, foreign keys and immutability. No advisory-lock compliance assumption is used to decide outcome.

A savepoint before batch allocation can be rolled back, removing the batch and releasing a subsequently acquired lock while the outer transaction stays live or commits. Therefore neither missing batch nor acquiring that lock proves whole-transaction rollback. PS-1 reports the outer xid status and separate batch observation. A savepoint after allocation may preserve the batch but remove later rows; a matching batch still proves no more than the batch's physical commitment. Tests must exercise both cases using ordinary SQL without pretending that the public facade offers savepoint control. No new savepoint API is added.

The lock/savepoint distinction is supported by [PostgreSQL 17 explicit locking](https://www.postgresql.org/docs/17/explicit-locking.html). No runtime reproduction is claimed in this design pass.

## Privileges, migration and enforcement classification

Selected design: **no migration and no privilege, role, RLS or readiness change**. Reuse SELECT already granted on governed_write_batch, existing current-context/binder functions and the catalog status function available under the accepted PostgreSQL role configuration. The immutable batch's existing triggers stamp the current top-level xid and refuse update/delete/truncate. Its tenant policy and batch/member provenance remain unchanged. No `pg_monitor`, `pg_read_all_stats`, backend cancellation, replication, superuser or BYPASSRLS grant is needed. Own-backend identity is captured before loss; recovery does not inspect arbitrary backend sessions.

Ordinary app/worker SQL tests must verify actual permissions, stamping and row isolation on the exact migrated baseline. If the accepted role contract disallows the narrowly needed catalog call, do not add a broad grant silently: report the exact refusal and amend the Phase A with the smallest status-only function/grant if it stays within this same capability. A status-owned function, table constraint or narrow access grant is not automatically a separate boundary. Split only if it changes independent tenant/principal attribution, role identity/elevation, existing-table rights, continuity or readiness authority. There is no automatic P0 database prerequisite in this selected design.

No schema upgrade is planned, so no migration rollback claim is needed. Existing migrations and expected structural digests must remain exact. Implementation rollback removes the new observation path and restores the existing unresolved error behavior; it must not delete historical batches or reinterpret already observed commits. The older unresolved path is retained only as the honest UNKNOWN branch, not as a second competing verdict source.

## Retention, resource bounds and failure behavior

Existing batch retention/immutability stays with its owner. The private context lives only in the originating manager's bounded in-flight/recovery registry. Use the existing maximum pool concurrency (8) and waiting bound (32) to bound retained active contexts; keep only the needed detached contexts while their trusted internal caller owns them. Do not create an unbounded global xid cache. Releasing a context means later recovery through this interface is unavailable, not aborted or safe to retry.

One automatic observation uses at most one additional connection and a fixed status read plus one batch read. Pool wait retains the existing five-second bound. Proposed observer-only local statement timeout is 2,000 ms and lock timeout 500 ms; neither changes the original transaction, its role defaults, an authority cutoff or PR38 policy. Capability acquisition retains its existing bounded owner path. Cancellation closes/discards the observer and returns UNKNOWN for any unreceived facts; no polling/retry loop runs inside the observer. No hard physical-commit or universal end-to-end latency promise is made. Implementation must demonstrate network cancellation and connection disposal, not merely rely on a SQL timeout for a broken transport.

Do not change the original connection's deadlines or cancel its backend from the observer. An original backend that cannot be proven ended remains unresolved. If observer binding is refused because a principal was revoked or a signer is unavailable, the original outcome is not reclassified. No new pre-tenant audit producer or changed security-audit payload is introduced; existing safe failures route through existing composition.

Observer response loss: rerun the read-only observation with a valid surviving context and fresh binding. No durable observation was promised. If a complete terminal observation was received before cleanup failed, preserve it with that qualification; if its reply was lost, no terminal fact is delivered until a later valid observation. The observer transaction's own commit/rollback is not evidence of the original outcome and does not require a new status ledger.

## Focused falsifiable evidence, not yet executed

Each control runs through the real manager/binder/pool and real PostgreSQL, using fictional accepted fixture data and the actual app/worker roles. Fault injection may lose replies or block execution; it may not manufacture a successful status/provider. Required baseline remains Linux x86_64, Python 3.12.13 and PostgreSQL 17.10.

| ID / invariant | Supported path, hostile change and required observation |
| --- | --- |
| PS01 original identity | Real original manager transaction captures xid before work; forged/copied context or same batch name on another xid refuses association |
| PS02 lost success reply | Original real batch commits; drop reply before manager receives it; fresh observer returns COMMITTED with the exact original batch. No second business transaction or duplicated batch |
| PS03 conclusive abort | Original transaction fails/aborts, acknowledgement is lost; actual pg_xact_status is aborted; observer reports ABORTED, with no retry or logical NO_EFFECT value |
| PS04 still executing | Pause original before executing queued work/COMMIT; observer reads in-progress and absent batch → UNKNOWN. Release it and show a later observation can recover actual commit |
| PS05 status horizon | Exercise NULL/old-status handling as a clearly labelled fault of the status adapter, alongside real DB reads: absent batch → UNKNOWN; real exact retained batch may still prove COMMITTED. Do not claim a naturally aged xid was produced unless it was |
| PS06 savepoint before allocation | Ordinary-role SAVEPOINT, allocate batch, ROLLBACK TO, then outer COMMIT: physical COMMITTED and batch absent. Never ABORTED or command success |
| PS07 savepoint after allocation | Preserve batch, roll back later writes and commit; batch matches, but observation supplies no complete semantic success claim |
| PS08 ordinary SQL forgery | Supply another full_xid in a batch insert: existing trigger stamps actual xid; copied authored IDs cannot match the captured original. Update/delete/truncate and cross-tenant selection fail under actual roles |
| PS09 current binding | Revoke/change principal or tenant registration after original ambiguity; new binder refuses incompatible evidence; observer returns unavailable/UNKNOWN without replaying old capability or leaking another tenant's row |
| PS10 pool and ownership | Closed unit, repeated finalize, pool reuse, old backend PID with different start/xid and manager replacement cannot reuse the context. Cancellation/failed idle verification discards the right connection |
| PS11 observer failure | Drop status or batch reply; cancel while binding/querying; lose observer rollback response. Unreceived data never produces a fact; fully received original commit stays committed; observer is not returned dirty |
| PS12 contradictions | Independently inject inconsistent provider observations only in the explicit fault seam; actual DB controls remain real. Preserve contradiction, suppress usable batch-success claim and do not overwrite history |
| PS13 no migration/authority drift | Exact applied migration, grants/RLS/catalog contract, selected bundles and public endpoints remain unchanged; private API cannot query a caller-supplied xid |
| PS14 positive bounded use | Real COMMITTED, ABORTED and unresolved cases all occur through intended composition, with finite connection use and cancellation. An all-UNKNOWN implementation fails acceptance |

Mandatory package check precedes every implementation commit. Run focused manager, architecture and PostgreSQL controls before complete exact-head content review; expensive baseline admission/publication follows zero-Blocker review in the live protocol's order. This local design executed no runtime tests or databases and grants no implementation permission.

## Smallest complete implementation and issue ownership

Likely owned areas: a small private physical-outcome module, targeted manager/application-runtime composition changes, existing manager/PostgreSQL tests and Kernel documentation. Do not expose SQL on TenantUnitOfWork or increase its architecture budget merely to fit code. Capture/status comparison should have one authoritative implementation; reuse the existing batch representation and binder. A separate module is justified by the closed facade boundary and the existing size constraint, not hypothetical plug-ins.

This is independently usable because it fixes an existing physical finalization ambiguity without needing the authorization evaluator, any unpromoted selected-action schema or a successful domain write. It is neither a receipt checker nor a type-only attempt factory. The simpler existing batch/status approach was selected over a second durable journal because the support horizon does not require cross-process discovery. A broader journal would add retention, registration, fencing and privilege obligations that belong to a different capability.

Live #173 is closed; reopening its completed implementation is inappropriate. #193 concerns non-forking restore/import recovery, not same-process lost-COMMIT observation. #178 remains the shared logical command Delivery and does not become completed through PS-1. Bounded searches found no existing physical-status Delivery. Recommend a new prerequisite Delivery under #167, with #178 consuming it. #178 need not become an epic merely to depend on an independently useful sibling. If the coordinator instead puts this and other implementations under #178 itself, the live protocol requires epic reclassification and separate Delivery children first. No issue or PR was created.

## Review and approval posture

No canonical owner-policy amendment is required for the limited physical facts in this design. OD-T1 and the future durable operation fence remain outside it. No demonstrated in-scope design blocker is asserted here; independent review must judge the complete proposal, especially actual-role catalog access, context provenance and bounded network cancellation. These are mandatory implementation acceptance proofs, not claimed results.

The design is not technically cleared and no approval is requested in this file. The coordinator first creates the concrete Delivery and draft implementation PR carrying this Phase A. Independent review then names that exact draft head and must reach zero Blockers before the live decision card is presented. A later valid same-task approval remains required before implementation. If review finds that correct status needs a broader role, durable registration or new continuity authority, return that exact expansion for a separate scoped decision instead of silently growing this capability.

Next: publish this design in its named Delivery draft, complete independent review at that exact head, and present the implementation card only after zero-Blocker clearance.
