# Checking that a claim ID is free

Phase A design for review. The proposed cap is eight focused hours for this check, including tests and review. Implementation requires a separate decision.

## Who owns the check

The tenant transaction layer establishes whether the ID was free at the start, checks it again after taking the lock, and protects it from then until the save ends. The command coordinator supplies the original attempt and proposed assertion ID. It alone decides whether to commit, roll back or recover an uncertain result. The claim writer can stage the checked record inside that transaction. [Tenant transaction foundation](https://github.com/samovers/OFARM2/issues/173) · [Command coordinator](https://github.com/samovers/OFARM2/issues/178) · [Writer call design](https://github.com/samovers/OFARM2/pull/425)

## How the check would work

1. On the original connection, capture PostgreSQL’s view of committed work in the first query after the transaction begins, alongside the existing tenant challenge. Keep that snapshot, the database session ID and the full transaction ID private to the attempt. Once the tenant is verified, bind these values and the challenge to the tenant, the original attempt, the selected storage owner and the boundary within which all writes commit together. Pin the snapshot by both reference and content digest. A reconnect starts a different transaction.
2. Take the proposed ID from the bound command and require it to match the record to be staged. Check the database key consisting of the verified tenant and that ID, across all record types and lanes. Records are append-only. The transaction ID stamped on each row tells PostgreSQL whether that row was visible in the original snapshot. An ID already occupied at the start fails.
3. Take the existing tenant write lock. **After the lock is granted**, issue a separate query for that same key. Under the existing `READ COMMITTED` setting this query can see a writer that committed during the wait. Applying the start snapshot as a filter here would hide that writer. Refuse an occupied key before attempting an insert.
4. Derive the two versions separately from the start observation and the fresh observation. Each version binds the storage owner, atomic boundary, tenant, exact ID-absence predicate and committed occupancy count. Both counts must be zero and the versions must match. In the #51 evidence, the snapshot’s `guardVersion` must equal both `snapshotVersion` and `observedVersion` in the proof. The attempt and proof must identify the same snapshot by reference and digest. The domain checker selects the required predicate independently. [Pinned protection contract](https://github.com/samovers/OFARM/blob/538d04075881b885ed370d14326acfab7aaf429e/03_machine_contracts/drafts_non_default/authorization_finalization_evidence/protected_state_evidence/PROPOSAL.md)
5. Hold the lock on that connection through the staged insert and the coordinator’s commit or rollback. After staging, check that the row belongs to this attempt’s batch and transaction. Missing evidence, a mismatch or a lock timeout must stop the write. A failure after staging must force rollback even if application code catches it. Only the coordinator may resolve an uncertain commit.

## What the two tests showed

Both cases used synthetic claims on a disposable PostgreSQL 17.10 database provisioned from [the tested OFARM2 revision](https://github.com/samovers/OFARM2/commit/92b3c462058a7d1d483225091a84326702d82c32), with all eleven tenant migrations and the usual two-second lock timeout. Both writers connected as the application role, `ofarm_app`. A third connection confirmed the original writer was waiting on the competitor’s lock before and after the competing insert, then checked which transaction owned the saved row.

| What the competing writer did | What the original writer saw after the wait | Final result |
| --- | --- | --- |
| Committed its insert | One row. The ID had been free at the start, but its version had changed. | The original writer attempted zero inserts. Only the competitor’s pending claim remained. |
| Rolled back its insert | Zero rows. The version still matched the original one. | The original writer inserted once. Only its pending claim remained. |

The four database functions the application role could run were `pg_current_snapshot()`, `pg_current_xact_id()`, `pg_backend_pid()` and `pg_visible_in_snapshot(xid8, pg_snapshot)`. The probe used test values for the storage owner and atomic boundary. A saved claim still awaits review.

## Before production integration

The real command path must supply the independently selected ID, storage owner, atomic boundary and original attempt. Verify the first-query capture and the fresh lookup through the tenant transaction manager. Preserve the existing tenant binder and its public interface. [Current transaction manager](../../kernel/tenant_uow.py)

Acceptance at that entry point still needs to cover an ID held by another record type or lane, the same ID under a different tenant, a competitor held off until this transaction ends, and rejection of a copied or stale snapshot after connection reuse or recovery. Verify that a caught error after staging leaves no committed row. Trust rests on the database’s enforced write path and tenant lock. Host or database administrator compromise is outside this check.

Next, review this design at the draft PR head. Stop for a revised proposal if it needs new database privileges, a different locking rule, another trust boundary or more than eight hours.
