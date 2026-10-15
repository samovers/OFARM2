# OFARM2 tenant transaction failure handling — RFC v0.1

Status: proposed Phase A for one Delivery implementation PR. Runtime implementation is not yet authorized.
Decision: `OFARM2-TENANT-TRANSACTION-FAILURE-001`, version 1.
Base: `301bf4aa3196b503ec114ebfa0f455be818627a4` (PR405 merged).
Delivery: #408, under Tracking Epic #167. Consumers: the existing ApplicationRuntime tenant boundary and future #178 command handling.
Primary trust boundary: **ordinary tenant transaction failure and finalization integrity**.
The named Delivery issue and draft implementation PR are recorded in the PR description and decision card.

## Problem and one capability

A caller can catch an error inside the current tenant UnitOfWork and still get
a normal return from its context manager. PR405's PS17 controls demonstrate two
different database outcomes behind that same misleading return:

- F1: PostgreSQL has entered a failed transaction. The driver COMMIT completes
  by rolling it back, and the manager returns normally.
- F2: batch INSERT succeeds, but validation of its returned metadata raises.
  If the caller catches that exception, the manager can commit the inserted
  batch even though `unit.batch` is absent.

This Delivery makes a failed tenant transaction terminal in its owning call.
Once the allocator fails, an existing rollback-only condition is set, or the
database reports a failed transaction, normal context exit must not be reported
as successful finalization. The manager refuses COMMIT, performs existing
rollback/discard cleanup, and delivers a bounded internal failure to the caller.

F1 and F2 belong together: they share the same transaction manager, original
connection, protected writes, lifecycle and rollback story. Changing only
allocation poisoning misses a database failure outside allocation; changing
only the PostgreSQL-state check misses an allocation-validation failure in an
otherwise committable transaction.

## Authority, actors and containment

| Fact or decision | Existing owner |
| --- | --- |
| Credentials, principal and tenant identity | Authentication, principal resolver and binder |
| Validated batch tuple and insertion | Existing allocator and database trigger |
| Whether this UnitOfWork may attempt COMMIT | TenantUnitOfWork and TenantUnitOfWorkManager |
| Actual database transaction state | Pinned psycopg/PostgreSQL connection |
| Ambiguous attempted-COMMIT observation | Existing PR405 observer, unchanged |
| RuntimeBundle selection result and refusal | Existing selector, unchanged |
| Entry refusal audit | Existing request-router audit owner, unchanged |
| Implementation and final merge acceptance | Task user under the Delivery Protocol |

Protected assets are atomic tenant writes, truthful ordinary completion,
same-call ownership, and separation of failed work from a successful command.
Trusted inputs are the existing manager-owned connection, validated binding,
allocator invocation and driver transaction status. Request values, caller
catching or reordering calls, and a caller-authored boundary error do not own
finalization. The supported actor is ordinary application/worker code using
`ApplicationRuntime.tenant_unit_of_work(principal)`; it gets no SQL handle.

Database/network errors, invalid allocator responses, caught exceptions,
process-control exceptions, and cleanup failure are in scope. Test seams may
inject returned-field corruption or database errors after real operations, but
must be named as seams. Arbitrary process reflection/monkeypatching in
production, malicious database-owner mutation, storage corruption and changes
to tenant topology are excluded compromise or separately owned work.

Primary risk: misclassifying a swallowed failure as success or implying that
a failed call proves no durable effect. Containment: terminal rollback-only
state, one owner of cleanup, and a failure classification that grants no
physical-outcome fact or retry permission.

## Permitted effects and explicit compatibility change

1. Any `BaseException` raised by the invoked private batch allocator marks the
   existing UnitOfWork rollback-only **before** the same exception is re-raised.
   This includes post-INSERT validation and process control. It does not
   retain the exception, its traceback, SQL, connection or request as new state.
2. A poisoned UnitOfWork cannot invoke another allocator or resolver callback.
   It may retain immutable binding/batch values for inspection; those values
   do not become authority after failure or closure. The existing public
   facade and its no-SQL/no-connection rule remain.
3. On normal body exit, the manager closes the facade and checks the existing
   rollback-only flag and the original connection's transaction state before
   attempting COMMIT.
4. A known rollback-only or PostgreSQL `INERROR` state follows existing
   rollback-or-discard cleanup and raises
   `TenantBoundaryError(TenantBoundaryOutcome.TRANSACTION_FAILED)`.
   Add this one internal outcome. It means this call did not complete normally;
   it is **not** a durable ABORTED, NO_EFFECT, domain refusal or retry receipt.
5. COMMIT is attempted only for a readable `INTRANS` state with no rollback-only
   flag. An unreadable state or another state refuses COMMIT, discards the
   original connection and raises the existing `FINALIZATION_UNKNOWN` outcome
   **without starting a physical observer**. There was no manager COMMIT attempt
   on this path, so no new PR405 recovery trigger is introduced.
6. Once an eligible ordinary COMMIT is attempted, its existing success,
   exception, non-idle result and PR405 observation paths remain unchanged.
   Body-authored boundary errors still propagate as body failures and cannot
   request observation.

**Compatibility change:** a caught selector refusal already marks the
UnitOfWork rollback-only and must prevent COMMIT. It currently allows a normal
context return after cleanup. This Delivery makes that exit raise
`TRANSACTION_FAILED`, just like other known rollback-only exits. It does not
change selection, validation, caching, no-retry or authority decisions.
The selector's accepted contract requires rollback instead of commit after a
caught refusal; the new wrapper-level error strengthens failure delivery.
Update existing tests that currently assert a silent rollback, preserving
their rollback/no-fallback assertions.

Pre-call type/lifecycle/duplicate-batch guards that reject before the private
allocator is invoked keep their existing behavior. A caught duplicate
`begin_batch` call must not silently roll back an already valid batch merely
because it was a caller programming error with no new database operation.
A prior rollback-only state is never cleared by those guards.

## State and ordering

The existing per-UnitOfWork rollback-only flag is the sole application
terminal-failure flag. Do not add a second failure registry, reason enum,
exception cache or recoverable handle.

| Event/state | Required next action |
| --- | --- |
| Healthy bound body, successful allocation | Retain validated result; no finalization yet |
| Invoked allocator raises | Set rollback-only first, re-raise exact exception; no validated result published |
| Caller catches allocation failure | Flag remains set; further database callbacks refused |
| Any body exception escapes | Close facade, existing rollback/discard, preserve escaping exception; no observer |
| Normal body exit, rollback-only | Close facade, one cleanup path, TRANSACTION_FAILED; no COMMIT or observer |
| Normal body exit, readable INERROR | Same failed path, even without an allocator failure |
| Normal body exit, unreadable/IDLE/ACTIVE/UNKNOWN status | Close/discard, FINALIZATION_UNKNOWN without observer; no COMMIT |
| Normal body exit, readable INTRANS and no failure | Existing one COMMIT and original finalization/observer behavior |
| All exits | Original lease returned once; failed/non-idle native discarded as today |

If rollback cannot be proved, discard the connection. Never turn cleanup
failure into an ABORTED or NO_EFFECT claim. Existing process-control precedence
during ordinary body/cleanup remains unchanged; do not swallow or newly retain
a process-control exception. If no independent process-control failure escapes
cleanup, a known failed normal exit reports TRANSACTION_FAILED.

A caught allocator failure cannot be rehabilitated by a later successful
statement or a test seam restoring INTRANS; the call-local flag is terminal.
No savepoint, retry, second COMMIT, later lookup or compensating write is added.

## Falsifiable acceptance

All production-path database controls run as both `ofarm_app` and
`ofarm_worker`, using the actual manager, binder, allocator and runtime.

| ID | Required negative and positive evidence |
| --- | --- |
| TF01 F1 | Allocate a real batch, cause and catch a real SQL error using a declared internal seam, exit normally: caller receives TRANSACTION_FAILED, no COMMIT was attempted, fresh qualified read confirms no batch, original lease released once. Also exercise real allocation SQL rejection. |
| TF02 F2 | After a real INSERT, force validation of a returned field to raise while the database remains INTRANS. Catch it: batch remains unpublished, normal exit fails, no COMMIT or observer occurs, fresh qualified read finds no inserted batch. Cover malformed/missing returned metadata and the existing PS17 timestamp-validation counterexample. |
| TF03 terminal failure | After either caught failure, try allocation and resolution, including a previously cached successful selection; no further database callback occurs. Restoring driver state cannot clear application poisoning. |
| TF04 error identity | Uncaught allocator/body errors and process control remain the exact original object through existing cleanup. Caught allocator process control poisons the call and prevents normal successful exit. Secondary cleanup failures cannot fabricate successful return or a physical fact. |
| TF05 cleanup failure | Inject ordinary rollback/close/return failures with actual ownership accounting. Assert cleanup/discard policy, one original return attempt, no new observer lease and no claimed ABORTED/NO_EFFECT. Do not claim a failed native return restores capacity. |
| TF06 existing selector | Caught expected/unexpected selector failures, re-entry and selector-after-batch retain existing terminal refusal and rollback. Normal outer exit now raises TRANSACTION_FAILED. No authority result, callback count or fallback capability changes. |
| TF07 state gate | Readable INTRANS succeeds. INERROR fails without COMMIT. IDLE/ACTIVE/UNKNOWN and a raising status read discard and fail without COMMIT/observer. A process-control interruption during state read keeps its existing propagation discipline. |
| TF08 healthy compatibility | Successful read-only/batch calls commit once; batch metadata is unchanged. Pre-invocation wrong-type/duplicate guards preserve the previously valid transaction. Closed-unit use stays refused. |
| TF09 observer compatibility | Real lost COMMIT reply still enters PR405 recovery, preserving matching COMMITTED, qualified ABORTED and UNKNOWN controls and exactly-one-lease ordering. No body-authored error, known rollback-only path or pre-COMMIT state refusal starts it. |
| TF10 audit/authority isolation | Through actual runtime/router composition, the new exit failure is not an entry audit event. Existing entry failures still route identically. No tenant/principal/binder/selector decision or public endpoint behavior is altered. |
| TF11 immutable scope | No role/grant/migration/trigger/schema/policy/lockfile/workflow change; existing pool8/waiter32/min1 and observer100ms/transport/provider/KMS bounds remain. Architecture public facade unchanged; no ceiling increase expected. |

Replace the existing PS17 expectations that deliberately preserve F1/F2 with
positive regressions and retain their historical evidence outside the new
source baseline. Do not weaken their real insertion/error/readback controls.
The former F2 ambiguous-COMMIT fixture must assert that the commit-loss hook is
never reached after poisoning; it must not invent an ambiguous attempted
commit when the corrected owner refuses to issue one.

Use fakes only for finite classification/control-flow seams, and real pinned
PostgreSQL for actual rollback, insertion and visibility claims. Reject
environment skips as acceptance. Preserve actual failures and evidence limits.

## Smallest implementation and review boundary

Expected changes: `kernel/tenant_uow.py`; focused unit/runtime tests plus
mechanical affected selector/audit/physical tests; `kernel/README.md`; this RFC;
the generated review inventory; architecture guards only if a strictly
mechanical assertion needs adjustment. The manager is currently 563/600 lines,
the observer 256/260 and the group 1231/1280. Keep those ceilings; simplify
owned code if necessary, without moving unrelated authority into this PR.

No change is expected in the physical observer, selector implementation,
signing reader, principal resolver, database roles/migrations, audit producer,
public routes, manifests, canonical/extracted contracts or deployment.
Tests/documentation that mechanically prove the unchanged accepted interfaces
may travel with this one transaction boundary.

EXC-001–006: use the existing rollback-only flag and one existing finalizer;
add no durable state or second authority path; link TF01–TF11 to exact owner
branches; delete obsolete silent-failure expectations rather than retaining a
compatibility mode; add no new helper abstraction without current need.
Only checking INERROR is simpler but misses F2's healthy post-INSERT state;
only poisoning the allocator misses F1's other SQL failures. Their combined
gate is the smallest complete correction.

## Approval and verification posture

This is high-risk transaction work. Phase A must receive zero-Blocker review,
then the task user must approve the complete live decision card naming the
existing draft PR before runtime or test implementation. This RFC stays in the
same eventual implementation PR; it is not a separate contract-only merge.

Before each commit: mandatory package check. Phase A uses package,
architecture and whitespace checks only; no expensive baseline admission.
After approved implementation: focused real-runtime verification, complete
exact-head zero-Blocker review, fresh admission, both complete pinned hosted
baselines, platform and native checks, sealed publication, final packet,
later exact-head authorization and native merge.

No new database setting, deployment, production probe, release, recovery
promise or platform-readiness claim is authorized. F3 pool shutdown, FU-4
connection-startup availability, #178 command identity/outcomes, #193
continuity, and domain contracts remain separate. A needed authority or
boundary expansion stops this PR before editing and receives separate work.

The design is provisional repository development before deployment. A
demonstrated conflict with the accepted selector/observer contracts, an
uncontained cleanup path, or inability to preserve authority and lifecycle
invalidates this version and requires redesign/review. There is no runtime
migration or data rewrite; previously stored batches are not deleted or
reinterpreted. A later rollback of this code would reintroduce F1/F2 and cannot
be described as restoring a safe compatibility mode.
