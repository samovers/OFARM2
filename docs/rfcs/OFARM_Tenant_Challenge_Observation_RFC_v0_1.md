# Current-transaction tenant challenge observation

Status: proposed Phase A; no implementation or approval claimed.

Decision: `OFARM2-TENANT-CHALLENGE-OBSERVATION-001`, version `1`.
Base: `samovers/OFARM2` at `fcac9ba505226e7e2fa2ede0aedb7585721b1841`.
Delivery and draft PR: assigned during Phase A preparation.
Parent Tracking Epic: #167. Recovery status: None.

## Problem and one capability

The capability issuer calculates expiry from its signing observation, but the
binder limits expiry to protected challenge creation plus 60 seconds. Audit
K-01 demonstrated refusal after even a one-microsecond observation delay when
the current key remains valid beyond that interval. The issuer cannot read the
protected challenge time through the present two-column creation API.

This Delivery provides one independently usable database capability: app and
worker sessions can observe the original creation time of their own current,
unconsumed transaction challenge. It does not correct issuance itself. The
separate issuer Delivery consumes this accepted observation and remains a
required follow-up before K-01 is closed.

## Primary boundary and permitted effects

Primary trust boundary: **tenant database challenge metadata observation**.

Add one no-argument `ofarm.current_tenant_challenge()` function returning:

| Field | PostgreSQL type | Meaning |
|---|---|---|
| `challenge_id` | `uuid` | UUID of this transaction's protected CHALLENGE row. |
| `challenge_created_at_unix_microseconds` | `bigint` | Exact original database creation time converted with the binder's existing epoch-microsecond expression. |

The new function is a read-only SECURITY DEFINER routine owned by the existing
`ofarm_owner`. Revoke PUBLIC execution; grant execution only to the existing
application and worker roles. Ordinary owner/migrator authority retains its
existing administrative scope; this design grants no new membership or raw
relation access. The database-owner boundary owns this narrow observation.

The protected row and its creation timestamp remain the sole source of truth.
There is no new table, cached deadline, renewal, clock read, lifecycle state,
configuration, caller-selected grace, or acceptance policy.

## Authority map and trust model

| Owner | Existing authority preserved |
|---|---|
| OFARM canonical law | Domain authority and truth semantics; untouched. |
| `ofarm_binder` | Sealed challenge creation, capability verification, consumption and binding. |
| `ofarm_owner` / governed migrator | Owned schema and the new read-only metadata projection; existing protected relation ownership. |
| Database observer role | Backend-incarnation observation; no new observer grants. |
| App and worker sessions | Request creation and read only their current transaction's metadata; cannot author it. |
| Signing reader and KMS signer | Key observation and signed capability construction; untouched in this Delivery. |
| Existing migration/readiness system | Exact released schema, digest, inventory and compatibility enforcement. |

Protected assets are challenge identity/time, transaction isolation, binder
custody and migration history. PostgreSQL identity functions, the protected
context table, immutable binder instance, governed migration owner and sealed
binder are trusted. Application and worker SQL callers and their session
settings are untrusted. A compromised superuser, migration owner, altered
PostgreSQL binary, arbitrary protected-table corruption or forked database
restore is not added to the threat model. Existing unsupported recovery stays
unsupported.

The primary risk is disclosing or substituting another transaction's metadata.
Containment is a no-argument reader keyed entirely by server-observed identity,
strict single-row selection, minimal output and unchanged binder verification.

## Identity, state and ordering

The reader obtains `pg_catalog.pg_current_xact_id_if_assigned()`. NULL refuses
with SQLSTATE `55000`; the reader does not assign an xid. It selects exactly
one protected row with current `pg_catalog.pg_backend_pid()`, that full xid8,
and `context_state = 'CHALLENGE'`. Missing or ambiguous selection also refuses
with a fixed `55000` message and no protected values in the error.

Full xid8 identifies the top-level transaction over the installation lifetime;
it is not a 32-bit wrapped xid. The additional PID restricts it to the executing
backend. Consequently a stale row from an earlier backend incarnation cannot
match the current full xid. The reader does not need observer access to
`pg_stat_activity` or `ofarm.current_backend_start()`. This is a narrower
observation lookup, not a change to the binder's existing PID/start/full-xid
checks. See [PostgreSQL 17 transaction identity documentation](https://www.postgresql.org/docs/17/functions-info.html#FUNCTIONS-PG-SNAPSHOT).

Use a schema-qualified, fixed-search-path (`pg_catalog, pg_temp`), STABLE,
PARALLEL UNSAFE function with no dynamic SQL and strict single-row handling.
All referenced relations and non-implicit functions are qualified. Call it in
a **separate statement after** `create_tenant_challenge()`, in the same open
transaction; no same-statement creation/observation visibility is promised.
Observation uses the calling statement's snapshot. A read after binding also
means a separate statement; binding and observation in one SQL expression is
outside this interface's sequencing contract.

The read acquires no row or advisory lock and does not create, consume, bind,
extend or delete the challenge. Normal SELECT relation locks still apply.
Repeated reads return the same original time. An expired CHALLENGE still has
observable original metadata: expiry decisions remain solely in the existing
capability validator/binder, not duplicated in this reader. The later issuer
must validate that window. BOUND context is refused. Rollback removes the
uncommitted row; committing or starting another transaction cannot make the
old full xid current again. Subtransactions retain the top-level xid; rollback
to a savepoint removes a challenge created after that savepoint normally.

## Invariants and executable acceptance

These are required future tests, not claimed execution evidence.

| ID | Invariant | Owning implementation | Supported-entry negative case / proving test |
|---|---|---|---|
| INV-001 | Output equals the exact stored challenge UUID and creation time. | New observation function. | Create as app/worker, compare with trusted fixture inspection; delay and repeat reads, proving no renewal; expired metadata still reports original time. |
| INV-002 | Only the executing backend's current unconsumed transaction can be observed. | No-argument PID/full-xid/CHALLENGE selector with strict cardinality. | Before creation, another connection, post-rollback/new transaction, and after successful bind all refuse; independent simultaneous sessions each see only their own UUID. |
| INV-003 | Observation has no state or clock-policy effect. | Read-only function and `pg_current_xact_id_if_assigned`. | Verify NULL xid before/after a refused read using savepoint handling, unchanged context/count/time over repeated reads, no renewals, and no challenge from a rolled-back savepoint. |
| INV-004 | Observation creates no wider table, observer or binder privilege. | Function ownership, exact EXECUTE ACL and fixed qualified source. | Runtime roles still cannot SELECT context or observer data, assume binder or replace routines; unrelated login roles cannot execute reader; temp-object/search-path shadowing cannot change output. |
| INV-005 | Existing creation, signed contract and binding acceptance remain byte/behavior identical. | Frozen migrations 0001–0010, capability manifest and unchanged issuer/binder code. | Existing time vectors and live binding tests retain results; the initial two-column creator still returns exactly two columns; owner cannot replace sealed binder functions. |
| INV-006 | Only an exact, transactional version-11 schema is admitted. | Forward migration, structural verifier and release/compatibility inventory. | Fresh install and exact 10→11 upgrade pass; replay is a verified no-op; dirty prefix, altered function/owner/ACL or interrupted migration refuses/rolls back with the old ledger and schema intact. |

A genuine missing or ambiguous internal match refuses. Arbitrary protected-row
corruption is not needed to manufacture a production-reachable attacker case;
strict cardinality remains a cheap defensive database property.

## Smallest coherent change and custody constraint

The existing creator is sealed to `ofarm_binder`. Ordinary migrations cannot
replace it or change its return type. ADR 0001's initial owner sealer must never
be recreated after version 1. Returning a third column from that sealed routine
would therefore require an independent custody change, not a small migration.

One owner-controlled read-only function uses privileges the schema owner already
has. It exposes only currently inaccessible metadata to the named caller roles.
This independently testable SQL capability is the complete database prerequisite,
not a contract-only companion. The later issuer change has a distinct owner and
changes signed validity; it belongs in its own Delivery.

The original creator and reader serve different operations; neither is a second
writer or fallback. No UOW compatibility shim is needed because the existing
creator is unchanged. Reordering key observation or choosing a shorter TTL does
not provide the exact protected challenge time and introduces assumptions about
delay or clock movement. Widening direct table access would expose more than the
two fields needed and weaken complete mediation.

Code excellence: EXC-001 retains one protected source; EXC-002 adds no duplicate
state or expiry validator; EXC-003 is traced in the invariant table; EXC-004 has
no superseded writer to delete in this prerequisite; EXC-005 adds one concrete
SQL observation boundary for an identified issuer consumer, not a framework;
EXC-006 rejects broader custody or raw-table access for this minimal outcome.
No line-count target is used.

## Migration, recovery and expected areas

Append `kernel/migrations/0011_tenant_challenge_observation.sql` through the
existing ordinary tenant migration lane. Require the exact version-10 source,
ledger/prefix and structural observation before changing it. Install the
reader, its closed ACL and the corresponding structural expectations in the
same transaction; use the existing ledger append and rollback mechanism.
Preserve every released migration byte and every earlier prefix digest.

Update `deployment/postgresql/migration_sets.py` and the exact release,
structural/readiness expectations and inventory that describe this one schema
addition. Do not broaden the migration state classifier or bypass exact-version
compatibility. Before migration, old code may operate only under its own exact
version. After migration, stale code/structure must fail compatibility; no
rolling mixed-version operation is promised. Interrupted DDL rolls back; later
correction is forward-only. No restore, resealing, superuser callback or raw
privilege escalation belongs here.

Tests are expected in the PostgreSQL tenant migration/contract/operations
suites and focused new observation tests. Their fixtures and the locked test
inventory travel with this PR. Update the relevant ADR 0001/0003 companion
navigation and an ERRATA K-01 entry with partial-remediation status. Preserve
the cryptographic `tenant_capability_contract_v1.json` bytes: the added metadata
reader is documented by this narrow companion, not a new signed payload field
or mutation of the frozen V1 binder entry-point contract.

No edits to issuer, UOW, principal, KMS, audit, canonical/extracted references,
legacy semantics, production routes, profile admission or provisioning-role
custody are permitted. If the ordinary owner cannot deliver this reader without
such a change, stop for a separate prerequisite/new decision.

## Verification and review gates

Phase A requires independent source review of ownership, identity selection,
frozen-contract compatibility and completeness to zero design Blockers. Only
cheap documentation/package checks run before approval; no expensive baseline
is requested for this design head.

After approval, execute focused real PostgreSQL tests under production role
shapes and the package checker. Freeze the implemented head and obtain a
zero-Blocker content review before existing baseline admission. The final
hosted evidence must use the repository's locked Linux x86_64/Python 3.12.13/
PostgreSQL 17.10 baseline, three distinct clusters, prescribed two-run
comparison and separate authoritative publication receipt. Local ARM or
emulated execution is supplemental and must be labelled. Keep untouched old
evidence historical; do not relabel it as a new-head pass.

## Decision status, non-goals and follow-ups

Not provisional. This observation has a permanent, narrow contract; there is no
temporary adapter or deletion timer. Pre-deployment repository approval does
not authorize deployment, release, production access or readiness claims.

Two independent source/design reviews found zero substantive design Blockers.
They checked the PID/full-xid identity argument, existing owner read privileges
and frozen-contract separation. Wording clarifications distinguish ordinary
SELECT locks, backend-observer authority and STABLE statement snapshots.
Delivery/PR publication and implementation evidence are pending.

The separate issuer Delivery must compare the reader UUID with the creator UUID
and bind this timestamp to the same immutable challenge object,
cap expiry by challenge deadline/lifetime/key end, invoke the existing validator
with protected creation time before KMS signing, and prove the real
issuer-to-binder flow with delayed observations and exhausted windows. Legacy
promotion findings and production import simplification remain separate work.

Next: review this Phase A, create the named draft PR, and present decision
version 1 for the required same-task approval before implementation.
