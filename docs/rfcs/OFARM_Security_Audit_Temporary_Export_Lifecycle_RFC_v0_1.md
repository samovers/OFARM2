# OFARM Security-Audit Temporary Export Lifecycle — Phase A Contract v0.1

## Status

- Parent: issue #192.
- Decision: `ISSUE192-SECURITY-AUDIT-TEMPORARY-EXPORT-LIFECYCLE-001`,
  proposed version 1.
- Reviewed base: `5f51f80981599a0da4678d555a02a648b84a2304`.
- Phase A scope: this RFC only.
- Supersedes the unimplemented designs in draft PRs #325, #326, and #327.
- PRs #322 and #323 are deployment/provider-evidence follow-ups and are not
  dependencies of this decision.

This contract does not authorize Phase B, merge, deployment, production
operation, database mutation, role creation, credential issuance, provider
calls, IAM changes, or export disclosure.

## 1. Problem and goal

Current `main` has the pieces needed to authenticate and bound one break-glass
export, but no closed operation joins them:

- PR #318 commits one export access intent and buffers one bounded page;
- PR #319 verifies one five-minute request signed by two independent approvers;
- PR #320 can issue the verifier's authority receipt; and
- PR #324 recreates only an empty audit store after loss.

No accepted path currently consumes an approval, creates the deliberately
absent temporary export LOGIN, invokes the page runner, removes that LOGIN, or
withholds the buffered page until exact normal structure is restored.

The earlier PR #325–#327 design grew a store-local consumption decision into a
general live-target epoch, retained control channel, replacement protocol, and
new advisory-lock provisioning. ADR 0001 requires none of those mechanisms in
V1. It already forbids audit backup, replica, CDC, restore, and clone promotion.

This decision establishes one closed V1 operation:

1. bind the signed request to the current audit store's immutable migration-1
   execution UUID;
2. reverify the original authority receipt and dual-approval bundle using the
   existing verifier and database-owned non-regressing time;
3. durably consume the still-live operation at most once in that store;
4. create one exact expiring `ofarm_security_audit_export_login` with a
   memory-only random password and only the existing export capability;
5. invoke the existing one-page bounded export exactly once;
6. terminate that LOGIN's sessions, revoke its membership, drop it, and verify
   exact normal security-audit structure; and
7. expose the already-buffered canonical page to trusted output composition
   only after closure succeeds.

The lifecycle also exposes one fixed closure-only operation for an expired,
exact-shape LOGIN left by process death. It can terminate, revoke, drop, and
verify closure, but it cannot consume an approval, create a LOGIN, or export.

The operation makes no global-singleton, backup, replica, clone, failover, or
production-readiness claim.

## 2. Learning value

The slice delivers the missing temporary export-authority lifecycle and proves
that the existing verifier, access-intent protocol, export function, and normal
structural verifier can form one fail-closed operation without a target-election
subsystem.

It reduces three demonstrated risks:

- replay of one still-valid approval on the same live store;
- reuse of an old approval after the audit store is empty-recreated; and
- disclosure while an export credential or export session may still exist.

## 3. Non-goals

This decision does not:

- provision or admit the observer root;
- require Google Policy Troubleshooter, PR #322, PR #323, a cloud fixture, or
  provider evidence;
- issue an authority receipt or create approver signatures;
- define approver user interfaces or approval transport;
- deliver output to stdout, a file, object storage, email, or a network sink;
- support multiple pages, resume, retry, scheduling, or an export service;
- support audit backup, replica, CDC, restore, physical clone promotion, or
  two simultaneously selected audit stores;
- create a target epoch, lease, retained control connection, advisory witness
  lock, new PostgreSQL role capability, or new provisioning sidecar;
- change HMAC custody, retention, normal reader behavior, gap handling,
  runtime health thresholds, tenant authority, issue #176, or OFARM law; or
- authorize deployment, production access, merge, or issue #192 closure.

Protected external output delivery and final real-ASGI/PostgreSQL cross-slice
evidence remain later #192 work.

## 4. Trust model

### 4.1 Protected assets

- pre-tenant security-audit rows and their fixed bounded disclosure surface;
- the single-use meaning of one still-live approved export operation;
- the temporary password and conninfo;
- the absence of the export LOGIN in normal posture;
- the rule that no buffered page crosses the lifecycle boundary before exact
  closure; and
- the no-backup/no-replica/no-restore V1 boundary.

### 4.2 Trusted components and actors

- immutable accepted migrations and the append-only migration ledger;
- the migration-1 `execution_id` as the store-incarnation identifier inside
  the V1 no-clone boundary;
- the existing non-regressing audit access clock;
- the merged PR #319 verifier and existing PR #318 export runner;
- PostgreSQL transaction commit, role catalog, `VALID UNTIL`, function ACLs,
  and exact structural verifier;
- trusted deployment composition that pins one observer public key, one audit
  admin route, and one audit-control route to one selected audit service; and
- the security operator and database administrator for this break-glass act.

The database and authority clocks retain ADR 0001's existing operating-system
clock prerequisite. Clock regression refuses; this decision adds no new clock
claim.

### 4.3 Untrusted inputs and actors

- authority-receipt bytes, approval-bundle bytes, cursor values, UUID text,
  and every other external carrier;
- the holder of the temporary export credential;
- PostgreSQL rows and catalog observations until completely validated;
- connection failures, cancellation, ambiguous commit, process exit, and
  error text; and
- any attempt to replay, widen, reorder, substitute, or partially execute the
  operation.

The temporary credential holder may connect directly and call every granted
surface. Database ACLs and the existing export function, not caller behavior,
must keep disclosure inside the committed access intent.

### 4.4 Excluded attacker capabilities

The following are out of scope for this V1 decision:

- compromise of the trusted deployment selector, security operator, database
  administrator, observer private key, or both independent approvers;
- superuser mutation of the migration ledger, consumption relation, role
  catalog, or structural verifier;
- a backup, replica, restored database, promoted physical clone, or two active
  audit stores contrary to ADR 0001;
- arbitrary in-process mutation, local source substitution, compromised Python
  or PostgreSQL dependencies, filesystem mutation, debugger access, or process
  memory compromise; and
- operating-system or hypervisor compromise.

If deployment later admits backup, replication, clone promotion, or more than
one eligible store, the migration-1 UUID is insufficient and this design must
stop for a new external non-rewindable or consensus-backed authority.

## 5. Authority map

| Decision | Sole authority | Forbidden substitute |
| --- | --- | --- |
| Store incarnation | Migration-1 `schema_migration.execution_id` on the selected audit database | DSN text, database OID alone, caller label, target epoch, provider fixture |
| Approval authenticity and independence | Merged PR #319 verifier under the composition-pinned observer public key | parsed JSON, operator assertion, database row, public result constructor |
| Approval currentness | Existing database-owned non-regressing access-clock observation used as verifier `now_us` and rechecked by the consume function | caller time, receipt issue time alone, Python wall clock |
| First use while valid | First acknowledged insert by the migration-4 consume function | returned SQL row before commit, role presence, retry, follow-up inference |
| Export scope | Signed request plus the existing committed `AUDIT_ACCESS` intent and export function | temporary LOGIN, admin privilege, caller-selected SQL |
| Temporary credential | Exact PostgreSQL role catalog state created by the closed lifecycle | password possession as approval, environment text, a pre-existing role |
| Window end | Earliest enforced request/access expiry, followed by session termination, revoke, and drop | process success flag or `VALID UNTIL` without cleanup |
| Closure | Exact absence of the temporary LOGIN plus the accepted structural verifier's complete normal result | attempted cleanup, role expiry alone, partial catalog checks |
| Positive handoff | One private closed-lifecycle result constructed only after closure | consumed row, export result before cleanup, serialized admission token |

No approval digest, approver identity, public key, signature, tenant value,
request value, route, free text, JSON, credential, or output is persisted in the
consumption relation.

## 6. State machine and ordering

### 6.1 Store-bound request

Phase B replaces the pre-deployment V1 export-request schema rather than
accepting two schema versions. The canonical request adds exactly one member:

```text
storeMigrationExecutionId: nonnil canonical UUID
```

The request schema becomes
`ofarm.security-audit-break-glass-export-request.v2`. The existing approval
statements already sign the complete request digest, so their shape and the
authority-receipt shape do not change. No production V1 request exists to
preserve.

Trusted pre-approval inspection obtains the migration-1 UUID read-only from
the selected audit store. Execution obtains it again through the admin route
and refuses before consumption if it differs from the signed request.

An empty replacement store receives a new migration-1 execution UUID through
the accepted migration runner. An approval signed for the lost store therefore
cannot be consumed on the replacement. A physical clone would copy the UUID;
physical clones are forbidden in V1 and are not normalized into supported
behavior here.

### 6.2 Bounded active-consumption state

One forward migration 4 adds one owner-only relation containing only:

- `operation_id uuid` primary key;
- `valid_until timestamptz`; and
- `consumed_at timestamptz`.

The relation holds at most 1,024 still-live operations. The consume function:

1. is executable only by the existing audit-control capability;
2. verifies exact `session_user` through the existing control posture;
3. verifies the supplied store UUID equals migration 1's immutable UUID;
4. takes one non-regressing database-clock observation;
5. requires `valid_from <= now < valid_until` and a lifetime no greater than
   the already accepted five minutes;
6. takes one transaction-scoped lock on this relation before cleanup, count,
   and insert, without using any raw or advisory-lock authority;
7. deletes only rows with `valid_until <= now`;
8. refuses if 1,024 live rows remain;
9. inserts the operation UUID once; and
10. returns a positive first-use result only for that insert.

Expired rows are not replay authority: the verifier refuses their original
request before consumption. This bounds storage without a permanent global
operation ledger or a general evidence digest.

The function owns no role, password, export, output, retry, or cleanup effect.
A compromised control credential can burn IDs or fill the bounded relation for
at most the approval lifetime; it cannot create the export LOGIN or read data.

### 6.3 Closed operation states

The only positive sequence is:

```text
NORMAL
  -> PREFLIGHTED
  -> APPROVAL_VERIFIED
  -> CONSUMPTION_ACKNOWLEDGED
  -> LOGIN_COMMITTED
  -> PAGE_BUFFERED
  -> LOGIN_DISABLED
  -> SESSIONS_TERMINATED
  -> LOGIN_DROPPED
  -> STRUCTURE_VERIFIED
  -> CLOSED_RESULT
```

Ordering rules:

1. Validate carrier byte bounds, trusted routes, observer key, store UUID, and
   exact normal structure before any approval consumption or role effect.
2. Observe non-regressing database time and verify the original carriers.
3. Call the consume function with only the normalized private values and
   acknowledge its transaction commit before generating a password.
4. A consume-commit exception is terminal outcome-unknown. Do not create a
   role and do not retry the approval automatically.
5. Generate one high-entropy password in memory. Do not return, serialize,
   log, or place it in a process argument or environment variable.
6. In one admin transaction, require the fixed LOGIN to be absent, create it
   with the exact closed attributes, `CONNECTION LIMIT 1`, and `VALID UNTIL`
   no later than the verified request expiry, grant only
   `ofarm_security_audit_export`, and commit.
7. Derive the export conninfo internally from the trusted target route and the
   memory-only credential. No caller supplies a separate export target.
8. Invoke `SecurityAuditExportRunner.run(...)` exactly once with the signed
   cursor. It may commit one access intent and buffer one page only.
9. Whether export succeeds or fails, disable LOGIN, terminate every session
   for the fixed role, revoke membership, drop the role, and run the complete
   structural verifier.
10. Construct the private closed result only when the page is complete and the
    exact normal structure is restored. Otherwise expose no page.

Role creation, disable, revoke, terminate, and drop are never public reusable
helpers. They exist only inside this lifecycle's private state machine.

### 6.4 Failure and crash posture

- Before acknowledged consumption: refuse with no credential effect.
- Consumption outcome unknown: burn the attempt; no credential effect.
- After acknowledged consumption but before LOGIN commit: the approval is
  spent; require a new operation and approvals.
- LOGIN commit outcome unknown: inspect only the exact fixed role. If its
  complete expected temporary shape is present, close it; if absent, verify
  normal structure; any other shape quarantines and refuses.
- Export refusal or failure: close the LOGIN and expose no page.
- Process exit while LOGIN exists: `VALID UNTIL` and the export function's
  intent expiry bound new access, while structural readiness remains false.
  The fixed closure-only operation may close only an expired, exact-shape stale
  LOGIN. An unexpired or drifted LOGIN is never repaired or replaced.
- Page buffered but cleanup or structural verification fails: expose no page;
  the operation remains consumed and readiness remains false.
- Post-closure output failure belongs to the later output-custody boundary and
  cannot recreate a credential or replay this approval.

## 7. Invariants and acceptance criteria

- `TEL-001` — Every accepted request is canonical schema v2 and binds the exact
  migration-1 execution UUID observed again on the selected audit store.
- `TEL-002` — Approval authenticity, independence, bounds, and currentness are
  reverified from the original carriers before consumption or role effects.
- `TEL-003` — At most one acknowledged consume commit exists for an operation
  while its approval can authorize; the live-consumption relation never
  exceeds 1,024 rows.
- `TEL-004` — No credential effect follows verification failure, consumption
  refusal, or consumption outcome ambiguity.
- `TEL-005` — The temporary LOGIN has one exact name, exact closed attributes,
  one connection, no tenant or HMAC-key authority, one capability membership,
  and expiry no later than the signed request.
- `TEL-006` — The lifecycle invokes the accepted export runner at most once and
  can buffer at most one signed-cursor page under the existing 2,048-row and
  8,388,608-byte database bounds.
- `TEL-007` — Replaying equal carriers, changing the cursor, changing the store
  UUID, or substituting either route never creates a second authorized window.
- `TEL-008` — No page crosses the lifecycle boundary until all fixed-role
  sessions are gone, membership is revoked, the LOGIN is absent, and complete
  normal structural verification succeeds.
- `TEL-009` — Expiry alone never claims cleanup or restored compatibility; a
  stale exact LOGIN is closed only after expiry, and drift is quarantined.
- `TEL-010` — Ordinary failures emit only fixed non-sensitive outcomes and do
  not render carriers, keys, passwords, DSNs, SQL, page bytes, database rows,
  exception text, causes, contexts, tracebacks, or local variables.
- `TEL-011` — Store replacement changes the signed store UUID and therefore
  refuses every approval for the lost store without an epoch service, external
  ledger, or advisory witness lock.
- `TEL-012` — No provider evidence, root provisioning, output sink, backup,
  replica, clone, failover, scheduler, or tenant authority enters this PR.

## 8. Production-reachable negative cases

| Invariant | Supported entry and counterexample | Required outcome |
| --- | --- | --- |
| TEL-001 | Execute a validly signed request for the previous store after PR #324 empty recreation. | Store UUID mismatch before consumption; no LOGIN. |
| TEL-002 | Supply reordered JSON, a substituted receipt, one repeated approver, or an expired request. | Fixed refusal; no consume call or role SQL. |
| TEL-003 | Start two lifecycle calls with the same valid carriers. | One consume commit at most; the other refuses and creates no LOGIN. |
| TEL-003 | Present 1,025 distinct concurrently live approvals. | First 1,024 may consume; the next refuses until expiry cleanup. |
| TEL-004 | Drop the control connection during consume commit. | Outcome unknown, no password generation, no role SQL, no retry. |
| TEL-005 | Pre-create the fixed role with one changed attribute or extra membership. | Quarantine and refuse; no repair or export. |
| TEL-006 | Ask for another cursor/page or make the export function return 2,049 rows. | Existing runner refuses; cleanup still runs; no page handoff. |
| TEL-007 | Point admin and control routes at different independently provisioned stores. | Store UUID mismatch before role creation. |
| TEL-008 | Make session termination, revoke, drop, or structural verification fail after buffering. | No page handoff; readiness remains false. |
| TEL-009 | Restart while the exact LOGIN is present but unexpired. | Refuse and leave it closed to new lifecycle work; do not replace it. |
| TEL-010 | Raise exceptions containing canary carriers, DSNs, passwords, and page bytes at every dependency boundary. | Only the fixed lifecycle error is externally observable. |
| TEL-011 | Reuse a lost-store approval on a fresh empty replacement with the same role names and credentials. | New migration-1 UUID refuses the request. |
| TEL-012 | Attempt to require Policy Troubleshooter, a KMS mutation, a provider call, or output destination. | Stop as a Follow-up or new decision; no scope expansion. |

Physical-clone replay is not a negative test for this decision because backup,
replica, restore, and clone promotion are unsupported production entries in V1.

## 9. Proposed architecture and smallest change

Phase B introduces one direct module,
`deployment/postgresql/security_audit_break_glass.py`. It owns one private
state machine and calls the accepted verifier and export runner directly.

It does not introduce a framework, service locator, generic credential
manager, public admission result, reusable role helper, target object, epoch,
lease, or background worker. Production dependencies are fixed. Test seams are
private and cannot be selected by production composition.

The smallest database addition is one forward migration with:

- the bounded active-consumption relation;
- one exact consume function granted only to the existing control capability;
- the structural-verifier update needed to make the new relation and function
  part of exact readiness; and
- no new role, raw table grant, extension, provisioning manifest, or immutable
  migration edit.

The request-schema correction is a pre-deployment replacement, not a
compatibility layer. Schema v1 request acceptance is removed. Authority
receipts and approval statements retain their accepted shapes because the
signed request digest already binds every request member.

This is smaller than PR #325–#327 because store identity is existing immutable
ledger state, single use is limited to the only interval in which replay could
authorize, and unsupported clones remain unsupported.

## 10. Elegance audit

Authoritative sources of truth:

1. one migration-1 UUID for store incarnation;
2. one verifier result from original signed carriers;
3. one bounded consumption relation for still-live first use;
4. one fixed PostgreSQL role for the temporary window; and
5. one complete structural verifier for closure.

Authoritative positive transition points:

1. consume transaction commit;
2. exact temporary-LOGIN transaction commit;
3. existing access-intent commit and page validation; and
4. role removal plus structural verification before result construction.

There is no duplicated epoch, target registry, lease count, nonce lock pair,
provider response, admission token, or durable approval digest. No new
abstraction has more than one implementation.

Nothing on `main` must be deleted. The unimplemented RFCs in PRs #325–#327 are
superseded by closing those drafts rather than merging compatibility text.
A clean direct lifecycle module is preferable to modifying any historical
unmerged design.

## 11. Pull request boundary and cross-boundary exception

### 11.1 Primary trust boundary

The primary trust boundary is the temporary dual-approved security-audit
export authority window, from fresh carrier verification through credential
closure and private page handoff.

Phase A changes only this RFC.

The prospective Phase B maximum path set is:

1. `docs/rfcs/OFARM_Security_Audit_Temporary_Export_Lifecycle_RFC_v0_1.md`
2. `security_audit/migrations/0004_temporary_export_lifecycle.sql`
3. `deployment/postgresql/security_audit_approval.py`
4. `deployment/postgresql/security_audit_break_glass.py`
5. `deployment/postgresql/README.md`
6. `kernel/tests/test_security_audit_approval.py`
7. `kernel/tests/test_security_audit_break_glass.py`
8. `kernel/tests/test_postgresql_audit_migration.py`
9. `conformance/rewrite_architecture_check.py`
10. `conformance/review_baseline_test_inventory.json`

No other path is authorized by this proposed contract.

### 11.2 Exact exception requiring architect approval

Phase B would combine two normally separate authorities inside one PR:

- database migration authority for one bounded consumption relation, one
  control-only function, and exact structural verification; and
- temporary credential authority for create, expire, terminate, revoke, and
  drop of the already governed export LOGIN.

Separation is impractical because neither half independently delivers a usable
or safely reviewable capability. Splitting them was the direct cause of the
PR #325–#327 prerequisite chain: the database half produced no operation, while
the credential half could not safely act without first-use state.

The added audit risk is that reviewers must assess forward DDL, consumption
durability, role effects, and cleanup ordering together. The compensating
controls are the exact ten-path cap, no new provisioning role or raw grant, one
primary state machine, invariant traceability, and one unconstrained exact-head
review followed only by affected-invariant review.

The architect's later Phase B approval must expressly approve this exception.
A generic `go`, review success, CI success, or approval of a predecessor
decision is insufficient.

### 11.3 Dependencies and follow-ups

Required merged dependencies:

- PR #318 bounded export page;
- PR #319 dual-approval verifier; and
- PR #324 empty-recreate store-loss recovery.

PR #320 may issue compatible authority receipts but is not invoked here.
PR #321 may supply a separately admitted observer root but is not required by
this repository boundary. PRs #322 and #323 remain parked deployment evidence.

Follow-ups after this slice:

- protected output custody/delivery;
- process-crash and stale-window operator evidence;
- final real-ASGI/PostgreSQL hostile cross-slice evidence; and
- final issue #192 closure audit.

Reviewers must not require provider fixtures, cloud IAM, failover, clone
support, multi-page export, output delivery, scheduling, or issue closure from
this PR.

## 12. Provisional design record

Not provisional within ADR 0001's V1 no-backup/no-replica/no-restore boundary.

Evidence of an allowed backup, replica, restored database, promoted clone, two
eligible audit stores, or a requirement to survive administrator compromise
would invalidate the migration-1 UUID authority and require a new design. The
likely upgrade would use a separately governed non-rewindable external store
identity and consumption authority; it must not be anticipated in V1 code.

## 13. Traceability and verification

| Invariant | Owning implementation | Negative evidence | Smallest verification |
| --- | --- | --- | --- |
| TEL-001, TEL-011 | request v2 parser; migration-ledger observation | old-store and mismatched-route requests | focused verifier tests plus fresh-store PostgreSQL test |
| TEL-002 | merged verifier called with database time | malformed, substituted, duplicate, expired carriers | focused real-Ed25519 vectors and exact call-order tests |
| TEL-003 | migration-4 consume function | equal concurrency, capacity, expiry cleanup | live PostgreSQL serialization and 1,024-row bound tests |
| TEL-004 | lifecycle pre-effect states | commit ambiguity and controlled refusal | dependency call-count and no-role-effect tests |
| TEL-005 | private role transaction | pre-existing/drifted role and widened grants | live catalog/ACL tests under admin and export identities |
| TEL-006, TEL-007 | existing export runner plus private route derivation | page widening, repeated call, route substitution | runner call-count and existing live export suite |
| TEL-008, TEL-009 | private cleanup and structural gate | termination/revoke/drop/verify failures; stale role | live crash-boundary and full structural-report tests |
| TEL-010 | fixed lifecycle errors and private secret carriers | injected canaries at every dependency boundary | formatted-exception and observability-sink assertions |
| TEL-012 | path/import architecture checks | provider/output/epoch/lock imports or calls | exact path set, forbidden-symbol checks, Ruff, package contract |

Required Phase B verification:

- focused unit and live PostgreSQL tests for every table row above;
- existing approval, export, store-loss, migration, provisioning, and structural
  suites unchanged except for the deliberate request-schema replacement;
- two real concurrent lifecycle attempts with one positive consume at most;
- crash-boundary evidence before and after consumption, LOGIN commit, page
  buffering, disable, termination, revoke, and drop;
- exact absence of tenant, HMAC-key, table, COPY, role-assumption, and unbounded
  function authority under the temporary LOGIN;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- rewrite-architecture and temporal/decision-log gates;
- Ruff, `git diff --check`, exact path equality, and mechanically regenerated
  canonical test inventory; and
- hosted conformance plus native-verifier checks at the exact head.

## 14. Open decisions and review disposition

Open decisions: none that may silently change Phase B. A review finding that
requires another store identity, provider authority, output sink, role,
provisioning manifest, or background process is a Follow-up or a new decision,
not an in-scope fix.

Current disposition:

- Blockers: exact-head Phase A review and explicit architect approval of both
  decision version 1 and the section-11.2 cross-boundary exception are pending.
- Follow-ups: protected output, crash-operation evidence, final cross-slice
  hostile evidence, and provider evidence before any PR #321 production use.
- Preferences: none.

Merge stop rule: after Phase B is expressly authorized, merge only when every
approved invariant passes, exact-head hosted checks pass, and no demonstrated
in-scope Blocker remains. New ideas, Preferences, hypothetical clone/failover
risks, and deployment hardening remain Follow-ups and do not reopen review.

## 15. Phase A stop

Stop after publishing and reviewing this RFC. Phase B requires a later exact
approval that names:

`ISSUE192-SECURITY-AUDIT-TEMPORARY-EXPORT-LIFECYCLE-001 version 1`

and expressly approves the section-11.2 cross-boundary exception. No other
wording authorizes implementation.
