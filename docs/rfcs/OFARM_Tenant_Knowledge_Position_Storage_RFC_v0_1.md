# OFARM Tenant Knowledge-Position Storage RFC v0.1

**Status:** approved implementation contract; implementation candidate

**Contract identity:** `ofarm.tenant-knowledge-position-storage.v0.1`

**Primary implementation ticket:** #176

**Primary trust boundary:** tenant-scoped database ordering and durability

**Temporal coordinate dependency:** `ofarm.temporal-coordinate.v0.1`,
`sha256:b81e4c7b0aacebb11ff8bf0d186cdb36150fade31180552b46f7be9e13c551eb`

**Authoritative migration:** `0003_tenant_knowledge_position.sql`,
`sha256:d59af77e23fe012203696023ec343038dbcab5d5ffb9689be11ba67dca22f827`,
6565 bytes

**Tenant migration-set head:**
`sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0`

**Tenant structural catalog fingerprint:**
`sha256:a975adc87f7706cffebdaedce8fef761a88bad1b7b7184ba919410e099492a25`

**Tenant catalog-verifier identity:**
`sha256:9e7bd92c602df519071e0bd2ecde3c9168b3bbc2d5c7e48ef7800ca1c6a2cc3b`

## Decision

The append-only `ofarm.governed_write_batch` ledger is the sole authoritative
tenant knowledge-position store. Every committed governed write batch has
exactly one positive tenant-local `knowledge_position`. The committed head is:

```text
MAX(governed_write_batch.knowledge_position) for the bound tenant
```

An empty ledger has committed head zero. Zero is a future query-cut meaning for
“before the first committed batch”; it is never stored on a batch.

Positions are exact integers from 1 through `9007199254740991`. They order
whole committed batches for one tenant only. Equal numbers in different
tenants have no ordering relationship.

This contract implements storage and allocation only. It does not activate the
inactive temporal-coordinate candidate, execute a `KnowledgeCut`, select a
valid-time carrier, or expose temporal behavior through a semantic or output
surface.

## Authority map

- ADR 0002 owns the meaning of knowledge time, its independence from valid
  time, tenant-local comparison, whole-batch visibility, and the prohibition on
  timestamp-derived ordering.
- The inactive `ofarm.temporal-coordinate.v0.1` candidate owns the closed
  portable `KnowledgeCut` vocabulary and safe-integer bound. This storage
  contract depends on its exact identity and digest without promoting it.
- Trusted `TenantBinding` and the existing protected transaction context own
  the runtime tenant and authenticated principal identity.
- `ofarm.tenant_registry.advisory_lock_key` and
  `ofarm.take_tenant_write_lock()` own the existing tenant serialization
  authority.
- `ofarm.governed_write_batch` owns durable committed positions. No other
  table, sequence, clock, transaction identifier, cache, or process variable
  is a head authority.
- `ofarm.allocate_tenant_knowledge_position()` owns database-side assignment
  for an authorized insert while holding the existing tenant transaction lock.
- `TenantUnitOfWork.begin_batch()` requests a governed batch and validates the
  returned position. It does not choose, reserve, or persist a position.
- The authoritative migration-set literal and external catalog-verifier digest
  own the exact database release and structural identity.
- Existing production semantic contracts, RuntimeBundle selection, profiles,
  outputs, and the separate #192 audit runtime retain their current
  authorities unchanged.

## State transition

For a bound `ofarm_app` or `ofarm_worker` transaction:

1. An empty UnitOfWork performs no batch insert and consumes no position.
2. `begin_batch()` inserts one governed batch without a caller-supplied
   position.
3. The database verifies the row's tenant and principal against protected
   transaction context.
4. The allocator takes the existing tenant transaction lock.
5. While holding that lock, it reads the committed ledger head and assigns
   `head + 1`.
6. The batch and all rows that reference it remain in the same database
   transaction.
7. Commit makes the whole batch and its position durable together. Rollback
   publishes neither and permits the same candidate number to be assigned by a
   later transaction.

The lock is held until transaction completion. A second allocator for the same
tenant cannot choose its position before the prior allocator commits or rolls
back. Different tenants use independent lock keys and independent position
spaces.

## Conformance-only genesis posture

There is no production pre-binding genesis API in this contract. Existing
target-admin provisioning and conformance fixtures may create exactly the
first batch for a registered tenant only when all of these conditions hold:

- the session user is a PostgreSQL superuser already used by the fixture;
- the operation is exactly `AUTHORITY_BOOTSTRAP`;
- the explicit position is exactly 1;
- the tenant registry supplies the existing advisory lock key; and
- the tenant has no governed batch.

The fixture takes that existing tenant lock directly because protected tenant
binding does not yet exist. It adds no role, login, grant, runtime route, or
control-plane authority. A second genesis batch refuses. Real production tenant
onboarding remains unsupported and requires a separately approved boundary.

## Invariants

- **KP-001 — Exact range.** Every stored position is an exact `int8` value in
  `[1, 9007199254740991]`; batch position zero and unsafe JSON integers refuse.
- **KP-002 — Tenant uniqueness.** `(tenant_id, knowledge_position)` is unique.
- **KP-003 — Serialized allocation.** Runtime assignment occurs only while
  holding the registered tenant's existing transaction lock.
- **KP-004 — Commit order.** For one tenant, committed positions are monotonic,
  gap-free whole-batch boundaries because a later assignment waits for the
  prior allocating transaction to commit or roll back.
- **KP-005 — Rollback neutrality.** A rolled-back candidate is absent from the
  ledger and may be reused; a committed position is never reused.
- **KP-006 — Bound authority.** Runtime allocation requires the exact tenant and
  principal installed in protected transaction context. Request data cannot
  select either authority.
- **KP-007 — Derived membership.** Batch-member tables retain their existing
  tenant-and-batch foreign keys. They do not copy `knowledge_position`; their
  position is derived from the one referenced batch.
- **KP-008 — Ledger head.** The append-only governed-batch ledger is the only
  committed head. No mutable head row or cached counter exists.
- **KP-009 — Tenant isolation.** Existing forced row-level security and tenant
  binding remain in force. Cross-tenant positions are incomparable.
- **KP-010 — No-write neutrality.** A UnitOfWork that creates no governed batch
  consumes no position.
- **KP-011 — No surrogate order.** A timestamp, `full_xid`, UUID, batch ID,
  sequence, or process-local counter never supplies or approximates knowledge
  order.
- **KP-012 — No inferred backfill.** Migration 0003 refuses if any governed
  batch already exists. It does not infer positions from timestamps,
  identifiers, transactions, or row order.
- **KP-013 — Exhaustion refusal.** Allocation above
  `9007199254740991` refuses before a batch is inserted.
- **KP-014 — Closed semantic surface.** Storage does not authorize a
  `KnowledgeCut` read, valid-time selection, historical/WINDOW execution,
  materialization change, output, route, profile change, RuntimeBundle
  component, or #192 behavior.

## Required refusals and negative cases

The database refuses:

- a runtime caller that supplies any explicit position;
- an unbound runtime caller or a tenant/principal mismatch;
- runtime allocation outside `READ COMMITTED`;
- an unregistered or ambiguous tenant lock authority;
- a stored position below 1 or above the portable maximum;
- a duplicate position inside one tenant;
- exhaustion at the maximum committed head;
- a target-admin insert that is not the exact first conformance
  `AUTHORITY_BOOTSTRAP` batch at position 1;
- mutation or deletion of a committed batch under the existing append-only
  guard; and
- migration 0003 against any nonempty governed-batch ledger.

An insert that later fails, a transaction that rolls back, and a UnitOfWork
that writes no batch do not advance the committed head.

## Smallest coherent change

This boundary consists only of:

- one forward-only tenant migration adding the batch column, range and
  tenant-unique constraints, allocator trigger, and exact catalog-verifier
  update;
- the matching authoritative migration and catalog-verifier identities;
- UnitOfWork removal of its redundant Python-side lock call, receipt and
  validation of the database-assigned position, and an internal immutable
  batch field;
- focused unit and real PostgreSQL conformance tests; and
- this RFC, the migration inventory documentation, and the E-008 traceability
  update.

No new database role, grant, table, sequence, production bootstrap authority,
contract-registry entry, or runtime surface is part of the change.

## Verification

Verification must prove:

- the exact migration source, byte length, prefix digest, migration-set digest,
  catalog fingerprint, and external verifier identity;
- an empty migration target reaches the exact structural head and a nonempty
  batch ledger refuses the migration guard;
- the batch column is `int8 NOT NULL` with no default, has the exact range and
  tenant-unique constraints, and is the only copied
  `knowledge_position` column;
- there is no knowledge-position head table or sequence and existing forced
  row-level security remains enabled;
- the first bound batch receives `head + 1`, consecutive committed batches
  advance, and a rollback's candidate is reused;
- same-tenant concurrent allocation blocks until the prior transaction
  commits, while tenant-local position spaces can contain equal values;
- explicit runtime assignment, second genesis, invalid database-returned
  positions, and migration onto existing data refuse;
- an empty UnitOfWork consumes no position and Python does not independently
  take the allocation lock; and
- package conformance and forbidden-surface review show no production contract,
  route, output, materialization, profile, RuntimeBundle, or #192 change.

## Non-goals

This contract does not implement or authorize valid-time carriers, half-open
runtime validation, `ValidCut` or `KnowledgeCut` execution, head-read APIs,
current-state reads, AS_OF or WINDOW behavior, correction or dispute
reconstruction, materialization, a governed production command, receipts,
outputs, semantic routes, production tenant onboarding, recovery or
reconciliation tooling, active contract promotion, profile changes, or audit
runtime integration.

## Stop conditions and later dependencies

Work stops and requires a separate approved boundary if it needs:

- a new role, grant, login, key, control plane, or production genesis API;
- a mutable head table, sequence, backfill, reconciliation, or recovery path;
- a batch position copied into a member table or exposed through an API,
  receipt, semantic result, or output;
- a read of the committed head for application semantics;
- an executable valid-time carrier or half-open interval validator;
- a production command port or a change to a frozen command contract;
- historical, WINDOW, current-state, materialization, qualification,
  authorization, or output behavior;
- activation of the temporal candidates, a profile, or RuntimeBundle
  component; or
- any #192 audit-runtime change.

The next #176 boundary may implement executable valid-time carrier selection
and half-open interval validation only after its own authority map, selectors,
refusals, and verification are approved. A later production command must depend
on both that contract and this exact storage-contract identity. Reads and
outputs remain stopped until their versioned output-governance prerequisites
are separately satisfied.
