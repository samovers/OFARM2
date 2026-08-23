# OFARM Security-Audit One-Operation Admission — Phase A Contract v0.1

## Status

- **Parent issue:** #192
- **Decision:**
  ISSUE192-SECURITY-AUDIT-ONE-OPERATION-ADMISSION-001, proposed version 1
- **Phase:** Phase A design only; unapproved
- **Reviewed base:**
  5f51f80981599a0da4678d555a02a648b84a2304, the merge commit for PR #324
- **Primary trust boundary:** durable consumption and replay refusal for one
  independently verified break-glass export approval
- **Phase A repository effect:** this RFC is the only changed path
- **Phase B:** not authorized

## 1. Problem and exact goal

### 1.1 The missing boundary

Merged PR #319 verifies two independent approval statements over one exact
security-audit export operation. The verified result includes:

- one UUIDv4 operation ID;
- the SHA-256 digest of the complete canonical approval bundle;
- the authority-receipt digest and request digest;
- the exact validity interval;
- the bounded export cursor, if present; and
- the two approver, key, and independence-domain identities.

That verifier is intentionally side-effect free. Equal valid bytes may be
verified repeatedly and return equal normalized values. Verification alone
does not consume an operation.

Merged PR #318 provides a one-page bounded export runner. It intentionally
does not verify approval, create a credential, or prevent the same approved
operation from being used more than once.

Without a durable admission boundary, a caller could present the same valid
approval bundle to a future temporary-login lifecycle more than once. Point-
in-time dual approval would then be mistaken for single-use authority.

### 1.2 Exact goal

This decision adds one library-only admission runner and one forward audit-
database migration. For one call, the runner must:

1. accept the original authority-receipt and approval-bundle bytes, never a
   caller-supplied verified-result object;
2. open only the existing audit-control database route;
3. obtain one nonregressing database-owned Unix time in microseconds;
4. invoke the merged dual-approval verifier itself with that time;
5. recheck the complete verified validity interval immediately before
   consumption using a second observation of the same nonregressing database
   clock;
6. atomically consume the exact pair
   (operation_id, approval_digest);
7. commit with synchronous_commit=on before returning an admitted result; and
8. make an equal replay non-authorizing and a different digest for the same
   operation ID a conflict.

Only the transaction that inserts the first exact pair may return ADMITTED.
No replay, conflict, invalid approval, expired approval, failed transaction,
or ambiguous commit may authorize a credential or export.

### 1.3 Why this is one trust boundary

The database relation is negative replay state, not a positive approval
oracle. The Python runner owns verification and the single first-insert
transition. The relation is not readable by runtime roles and its mere
presence must never be treated as authority by a future lifecycle.

This pull request does not create the temporary export LOGIN, hold a password,
call the export runner, or deliver output. Those are later authority and
credential boundaries.

## 2. Learning value

This slice proves the exact handoff promised by the merged dual-approval
contract:

    valid signed carriers
      -> admission-owned nonregressing time
      -> fresh in-process verification
      -> one atomic durable consumption
      -> one first-call-only admitted result

It resolves four concrete failure classes:

1. equal approval replay;
2. operation-ID reuse with different approval bytes;
3. concurrent calls racing on the same operation ID; and
4. commit ambiguity after the consumption statement has been submitted.

The result is deliberately fail-closed. A crash or ambiguous commit after
durable consumption may burn an approved operation without producing a
credential. It may not authorize a retry. Availability recovery requires a
new operation ID and a new independently approved bundle.

## 3. Non-goals

This decision does not authorize:

- creation, update, rotation, or use of an approver private key;
- production observer-root provisioning, Google Cloud IAM, KMS, Policy
  Troubleshooter, provider evidence, credential materialization, or PR #322
  or PR #323 work;
- changing the merged authority-receipt issuer, dual-approval verifier,
  signature domains, schemas, carrier limits, five-minute authority bound, or
  two-approver independence rule;
- a caller-supplied clock, verified object, approval digest, operation ID,
  validity interval, cursor, approver roster, or admission result;
- a temporary LOGIN, password, SCRAM verifier, VALID UNTIL, membership, grant,
  revoke, backend termination, role drop, or crash-residue cleanup;
- a new database role or login, a new DSN, or a new credential;
- calling the bounded export runner, opening the export route, paging,
  resuming, retrying, or returning audit event data;
- output-recipient selection, encryption, stdout, file, object-store, network,
  or protected delivery;
- a service, command, endpoint, scheduler, queue, spool, daemon, deployment,
  release, or production operation;
- tenant database, tenant UnitOfWork, authentication, routing, HMAC custody,
  retention, overflow, gap, store-loss, readiness, or runtime-composition
  changes;
- a general approval ledger, generic workflow engine, legal-hold mechanism,
  or reusable authorization token; or
- issue #192 closure or a production-readiness claim.

If implementation or review requires any excluded authority, stop before
editing that boundary and propose a separate prerequisite or follow-up.

## 4. Trust model

### 4.1 Protected assets

- single-use meaning of one valid dual-approved operation;
- exact binding of operation ID to the SHA-256 digest of the complete approval
  bundle;
- validity against one database-owned nonregressing time authority;
- the distinction between first admission, equal replay, and conflicting
  operation reuse;
- transaction and commit-outcome honesty;
- the absence of credential, export, and output authority in this slice;
- the original receipt, approval bundle, conninfo, and dependency details; and
- normal audit-database structural readiness.

### 4.2 Trusted components

- the merged SecurityAuditDualApprovalVerifier implementation and its pinned
  package/conformance surface;
- the immutable security-audit migration history through version 3;
- the accepted audit-control LOGIN and capability role;
- the existing nonregressing audit-access clock primitive and its serialized
  high-water sequence;
- PostgreSQL unique-index, transaction, session_user, and synchronous-commit
  behavior;
- the repository-pinned psycopg and Ed25519 dependencies; and
- future in-process composition only to pass the first-call admitted result
  directly to the separately governed credential lifecycle.

### 4.3 Untrusted inputs and behavior

- every receipt and approval-bundle byte;
- the control conninfo string and all embedded parameters;
- malformed, expired, reordered, substituted, oversized, or invalidly signed
  carriers;
- concurrent equal and conflicting calls;
- a regressed wall clock;
- every database row and result member until exact validation;
- connection, statement, lock, rollback, close, and commit failures;
- a commit exception after the insert may already be durable;
- caller attempts to replay, retry, serialize, forge, or reuse a returned
  result; and
- canaries in carriers, conninfo, database errors, dependency exceptions, and
  tracebacks.

### 4.4 Explicitly excluded attacker capabilities

- arbitrary code execution inside the admitted process;
- mutation of installed source, bytecode, interpreter, dependencies, or CA
  roots;
- compromise of PostgreSQL or its bootstrap superuser;
- compromise of the accepted audit-control credential;
- simultaneous compromise of all approver, observer, database, and future
  credential-lifecycle authorities; and
- arbitrary memory mutation after validation.

Audit-control credential compromise can consume guessed or observed operation
IDs and cause denial of service. It cannot by itself create the temporary
LOGIN or cause future composition to act, because database row presence is
not positive approval authority.

## 5. Authority map

| Decision | Sole authority | Forbidden substitute |
| --- | --- | --- |
| Receipt and approval validity | Fresh invocation of the merged verifier over the original bytes | caller-supplied result, digest, boolean, parsed JSON, or prior verification |
| Admission time | Existing nonregressing audit-access clock, observed by the new database wrapper | process time, caller time, token timestamp, receipt timestamp, or wall-clock rollback |
| Operation identity | verifier-returned UUIDv4 operation ID | argument, environment, filename, row, or generated replacement |
| Approval identity | verifier-returned digest of the complete canonical approval bundle | digest argument, request digest, signature digest, or receipt digest |
| Single use | first committed insert into the closed admission relation | in-memory set, log, cache, file, queue, caller assertion, or row presence alone |
| Conflict | same operation ID with a different stored approval digest | last-write-wins, second row, update, delete, or replacement |
| Replay | same operation ID and same digest already present | another ADMITTED result or credential authority |
| Commit outcome | acknowledged synchronous commit only | returned SQL row before commit, retry, follow-up query, or inference |
| Future credential handoff | direct in-process use of the one fresh ADMITTED return plus the future boundary's own authority | serialized result, database row presence, public constructor, or replay result |

## 6. Closed database contract

### 6.1 Forward-only migration

Phase B adds exactly:

    security_audit/migrations/
      0004_one_operation_export_admission.sql

Migrations 0001, 0002, and 0003 remain byte-identical. Version 4 must refuse
unless the exact version-3 migration ledger, structural-verifier source, and
catalog digest are present.

The authoritative migration-set literal advances from version 3 to version 4.
No provisioning identity or existing migration digest changes.

### 6.2 Admission relation

Version 4 creates exactly one owner-only relation:

    ofarm_security.security_audit_export_admission

Its columns are:

| Column | Type | Rule |
| --- | --- | --- |
| operation_id | uuid | primary key; exact RFC 4122 UUIDv4 |
| approval_digest | text | exact lowercase sha256: plus 64 hexadecimal digits |
| admitted_at_microseconds | bigint | exact nonregressing high-water time used by first consumption |
| valid_from_microseconds | bigint | verifier-returned lower bound |
| valid_until_microseconds | bigint | verifier-returned exclusive upper bound |

Required checks:

- operation_id has UUID version bits 4 and RFC 4122 variant bits;
- approval_digest uses the exact closed digest grammar;
- admitted_at_microseconds is nonnegative;
- valid_from_microseconds is nonnegative;
- valid_until_microseconds is greater than valid_from_microseconds; and
- admitted_at_microseconds falls inside the stored half-open validity interval.

There is no tenant, Party, actor, approver, key, credential, cursor, event,
output, free text, JSON, raw carrier, or exception column. The bundle digest
already binds the complete canonical request, receipt digest, statements, and
signatures.

No role receives SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, or
TRIGGER on this relation. Only the owner function may access it.

### 6.3 Clock wrapper

Version 4 creates:

    ofarm_security.observe_security_audit_export_admission_clock()

It:

1. is SECURITY DEFINER with search_path fixed to pg_catalog and pg_temp;
2. requires exact session_user
   ofarm_security_audit_control_login;
3. invokes the existing private nonregressing access-clock primitive;
4. returns exactly one row containing observed_at,
   high_water_microseconds, and clock_regressed;
5. exposes no other row or state; and
6. is executable only by ofarm_security_audit_control.

The runner uses high_water_microseconds as verifier now_us. A regressed wall
clock does not move admission time backward.

### 6.4 Atomic consume function

Version 4 creates:

    ofarm_security.consume_security_audit_export_admission(
      uuid, text, bigint, bigint
    )

It returns one row:

    outcome text,
    admitted_at_microseconds bigint,
    valid_until_microseconds bigint

The closed outcomes are:

- ADMITTED — this transaction inserted the first exact operation/digest pair;
- REPLAYED — the same operation ID and digest already exist; and
- CONFLICT — the operation ID exists with a different digest.

The function:

1. is SECURITY DEFINER with a fixed search_path;
2. requires the exact audit-control session_user;
3. validates UUIDv4, digest grammar, and integer interval before relation
   access;
4. reobserves the nonregressing access clock;
5. requires
   valid_from_microseconds <= high_water_microseconds
   < valid_until_microseconds;
6. attempts one INSERT with that exact high_water_microseconds and with
   ON CONFLICT DO NOTHING;
7. returns ADMITTED only from INSERT RETURNING;
8. otherwise reads the one existing primary-key row and returns REPLAYED or
   CONFLICT without updating or deleting it; and
9. returns no stored digest or carrier data.

The function is executable only by ofarm_security_audit_control. Public and
all other audit roles receive no authority.

### 6.5 Concurrency

For any operation ID, PostgreSQL primary-key serialization is the authority.

- Two equal concurrent calls produce at most one ADMITTED result.
- The loser observes REPLAYED only after the winner is visible.
- Equal and conflicting concurrent calls produce at most one stored row.
- A different digest never overwrites the first digest.
- Transaction abort removes an uncommitted first insert.
- A committed first insert is permanent in V1. There is no delete, reset,
  expiry purge, or operator repair path.

### 6.6 Structural readiness

Version 4 extends the existing complete structural verifier through an exact-
source-pinned forward amendment. The final catalog fingerprint includes:

- the new relation, columns, primary key, and checks;
- both new function identities, language, volatility, security mode, source,
  configuration, result shapes, arguments, and ACLs;
- the unchanged owner/control role postures;
- absence of direct relation grants;
- migration ledger versions 1 through 4; and
- the new complete catalog digest.

The contract observer reports migration version 4, the authoritative version-
4 prefix digest, and the amended security-audit contract digest.

Normal posture remains structurally ready. This migration does not create the
temporary export LOGIN whose presence intentionally makes readiness false.

## 7. Closed Python contract

### 7.1 Module and public surface

Phase B adds:

    deployment/postgresql/security_audit_admission.py

Its exact public surface is:

~~~python
class SecurityAuditAdmissionError(RuntimeError): ...
class SecurityAuditAdmissionRefused(SecurityAuditAdmissionError): ...
class SecurityAuditAdmissionUnavailable(SecurityAuditAdmissionError): ...
class SecurityAuditAdmissionOutcomeUnknown(SecurityAuditAdmissionError): ...

@dataclass(frozen=True, slots=True)
class AdmittedSecurityAuditOperation:
    operation_id: UUID
    approval_digest: str
    authority_receipt_digest: str
    request_digest: str
    valid_until_microseconds: int
    cursor: SecurityAuditAccessCursor | None

class SecurityAuditOperationAdmission:
    def __init__(
        self,
        observer_public_key: bytes,
        connection_factory: ConnectionFactory = psycopg.connect,
    ) -> None: ...

    def admit(
        self,
        control_conninfo: str,
        authority_receipt_bytes: bytes,
        approval_bundle_bytes: bytes,
    ) -> AdmittedSecurityAuditOperation: ...
~~~

The constructor creates one SecurityAuditDualApprovalVerifier. admit invokes
that verifier itself. The method accepts no time, operation, digest, interval,
cursor, role, retry, or effect callback.

The returned dataclass is a normalized in-process handoff, not a serializable
authorization token. A future credential lifecycle must call admit in the
same call chain and must not expose a constructor, decoder, loader, or
row-presence shortcut.

### 7.2 Connection policy

The runner opens one control connection with:

- autocommit=false;
- connect_timeout=5;
- statement_timeout=5000ms;
- lock_timeout=500ms;
- idle_in_transaction_session_timeout=10000ms;
- transaction_timeout=15000ms;
- synchronous_commit=on;
- TimeZone=UTC;
- DateStyle=ISO,MDY; and
- application_name fixed by code.

Caller-supplied conninfo options are removed and replaced by the fixed
options. There is no export conninfo and no second connection.

### 7.3 State machine

The exact states are:

    CONTROL_UNOPENED
      -> CONTROL_OPEN
      -> CLOCK_OBSERVED
      -> APPROVAL_VERIFIED
      -> CONSUME_SUBMITTED
      -> FIRST_INSERT_VALIDATED
      -> COMMITTING
      -> ADMITTED

Before CONTROL_OPEN, invalid public arguments are REFUSED and connection or
dependency failure is UNAVAILABLE.

After CONTROL_OPEN and before CONSUME_SUBMITTED, invalid carrier, signature,
approval, or validity is REFUSED after rollback. A connection, statement, or
malformed database-result failure is UNAVAILABLE after rollback.

REPLAYED and CONFLICT are REFUSED and never commit an admission mutation.

After CONSUME_SUBMITTED, REPLAYED and CONFLICT are REFUSED after rollback. A
connection, statement, or malformed database-result failure before commit is
UNAVAILABLE and returns no authority. Any commit exception or loss of outcome
after COMMITTING is OUTCOME_UNKNOWN.

Only ADMITTED returns a value.

### 7.4 Verification and time sequence

Inside one transaction the runner:

1. sets READ COMMITTED;
2. calls the clock wrapper and validates one exact row;
3. passes high_water_microseconds to the merged verifier;
4. accepts only the verifier's private normalized result;
5. requires
   valid_from_us <= high_water_microseconds < valid_until_us;
6. calls consume with only the verified operation ID, approval digest, and
   validity bounds;
7. accepts only one exact ADMITTED row whose time remains in the interval;
8. commits; and
9. constructs the public result only after commit returns.

There is no verification result parameter and no way to bypass the fresh
verifier call.

### 7.5 Replay and ambiguity

The runner never retries:

- connection creation;
- clock observation;
- verification;
- consume execution;
- result fetch;
- rollback;
- close; or
- commit.

An exact replay is a fixed fresh SecurityAuditAdmissionRefused. A conflict is
the same outward class. Neither exposes whether an operation ID exists.

SecurityAuditAdmissionOutcomeUnknown contains no operation ID, digest,
conninfo, carrier, database text, cause, context, or retry instruction beyond
the fixed message that the operation must not be retried.

### 7.6 Failure hygiene

Every ordinary public error is freshly constructed outside the dependency
exception handler. Its arguments and message are fixed, its cause and context
are absent, and formatting with capture_locals=false contains no carrier,
conninfo, SQL, database error, key, principal, cursor, or dependency canary.

No module path may import logging, traceback, tempfile, subprocess, socket,
asyncio, queue, pathlib, os, sys, time, secrets, random, or a cloud client.

## 8. Invariants

- OOA-001 — original carriers, not a verified object, are the only approval
  inputs.
- OOA-002 — admission-owned nonregressing database time drives verification
  and consumption.
- OOA-003 — exactly one verifier call occurs per admitted attempt.
- OOA-004 — only the verifier-returned operation ID and approval digest reach
  the consume call.
- OOA-005 — only the first committed exact pair returns ADMITTED.
- OOA-006 — equal replay never returns authority.
- OOA-007 — different digest reuse never changes the first row.
- OOA-008 — concurrent calls admit at most one transaction.
- OOA-009 — a returned SQL row before commit is not authority.
- OOA-010 — commit ambiguity is terminal and never retried.
- OOA-011 — no direct relation privilege is granted.
- OOA-012 — row presence is replay state, not positive approval authority.
- OOA-013 — no credential, role, export, output, or deployment effect occurs.
- OOA-014 — all failures are fixed, closed, and canary-free.
- OOA-015 — normal structural readiness remains exact after migration 4.

## 9. Required Phase B evidence

### 9.1 Unit evidence

Focused tests must prove:

1. every invalid constructor key refuses before database work;
2. invalid conninfo or carrier type/size refuses before connection;
3. caller conninfo options are replaced by fixed code-owned options;
4. one clock row and one verifier call precede consume;
5. no caller-supplied normalized value can reach consume;
6. every valid-interval boundary is exact to one microsecond;
7. ADMITTED is withheld until commit acknowledgement;
8. REPLAYED and CONFLICT are indistinguishable fixed refusals;
9. malformed or duplicate clock/consume rows refuse;
10. every pre-submit connection and statement failure maps correctly;
11. every commit exception is OUTCOME_UNKNOWN and is never retried;
12. rollback and close failures cannot turn failure into success;
13. result and error objects expose no forbidden value; and
14. source/import/line/function budgets are exact.

### 9.2 Live PostgreSQL evidence

Against the real isolated audit service, tests must prove:

1. migration 4 applies after exact versions 1 through 3;
2. first valid admission commits one exact row and returns ADMITTED;
3. equal replay returns no authority and creates no second row;
4. same operation with a different valid bundle is a conflict and preserves
   the first row;
5. two concurrent equal calls produce exactly one admitted result;
6. two concurrent conflicting calls preserve exactly one immutable digest;
7. wrong session_user and SET ROLE paths refuse before relation access;
8. direct SELECT, INSERT, UPDATE, DELETE, TRUNCATE, COPY, and function bypass
   attempts under runtime roles refuse;
9. exact not-before, expiry, and one-microsecond boundary cases use the
   nonregressing database clock;
10. a forced wall-clock rollback cannot make an expired operation current;
11. transaction rollback leaves no admission row;
12. table, constraint, function, source, ACL, migration-ledger, and catalog
   drift make structural readiness false; and
13. no temporary export LOGIN exists before or after every test.

All test-generated signing keys, receipts, bundles, and passwords remain
inside isolated test fixtures. Tests call no provider and access no production
resource.

### 9.3 Repository evidence

Phase B must pass:

- focused admission and audit migration tests;
- package-contract conformance;
- rewrite-architecture conformance;
- temporal candidate and decision-log checks;
- both complete review baselines with clean-run equivalence;
- native verifier amd64 and arm64 jobs;
- canonical multi-platform index assembly; and
- git diff --check.

## 10. Prospective Phase B repository boundary

Only a later exact approval may authorize edits to these eleven paths:

1. docs/rfcs/OFARM_Security_Audit_One_Operation_Admission_RFC_v0_1.md
2. security_audit/migrations/0004_one_operation_export_admission.sql
3. deployment/postgresql/migration_sets.py
4. deployment/postgresql/audit_contract.py
5. deployment/postgresql/security_audit_admission.py
6. deployment/postgresql/README.md
7. kernel/tests/test_security_audit_admission.py
8. kernel/tests/test_postgresql_audit_migration.py
9. kernel/tests/test_postgresql_audit_reason_vocabulary.py
10. conformance/rewrite_architecture_check.py
11. conformance/review_baseline_test_inventory.json

The RFC, tests, README, contract, migration authority, structural conformance,
and inventory are mechanical verification of the same durable-admission
boundary. No independent authority or custody change is included.

Phase B must stop before touching another path.

## 11. Budgets and architecture controls

- new production admission module: at most 420 physical lines;
- every production function: at most 80 physical lines;
- new focused test module: at most 1,300 physical lines;
- migration 4: at most 700 physical lines;
- no new dependency or lockfile;
- no test-glob widening beyond the exact new admission test;
- direct repository imports limited to:
  - deployment.postgresql.security_audit_approval;
  - deployment.postgresql.security_audit_access; and
- standard-library imports limited to dataclasses, enum, typing, and uuid;
- third-party imports limited to psycopg and its already pinned submodules.

The architecture checker must prohibit the forbidden effect names and imports
from section 7.6, direct export-runner use, credential or role SQL, output
writes, retry loops, sleeps, environment access, and public construction from
an already verified object.

## 12. Review classification

An in-scope Blocker demonstrates that:

- an equal or conflicting replay can return authority;
- concurrent calls can admit more than one row;
- caller-owned time or a supplied verified object can bypass verification;
- a regressed clock can extend validity;
- the first row can be updated, deleted, or replaced;
- a returned result can precede acknowledged commit;
- an ambiguous commit can be retried or called successful;
- a runtime role can access the relation or functions outside the exact grant;
- row presence becomes positive authority;
- sensitive input reaches a public error or repository artifact;
- normal structural readiness does not bind the new objects; or
- the implementation crosses into credential, export, output, provider,
  runtime, or deployment authority.

Preferences about a generic workflow engine, long-term admission history,
operator inspection, manual reset, credential creation, output delivery, or
process-crash recovery are follow-ups unless they demonstrate one invariant
cannot hold.

## 13. Dependencies and ordered follow-ups

### 13.1 Dependencies

- Issues #169, #170, #172, #173, and #174 are closed.
- PRs #318, #319, #320, #321, and #324 are merged.
- The merged dual-approval verifier is the only cryptographic verifier used.
- The merged nonregressing audit-access clock is the only time authority.
- PRs #322 and #323 remain separate provider-evidence work and do not change
  this local admission boundary.
- No production observer root, credential, or provider call is required for
  repository implementation or isolated tests.

### 13.2 Follow-ups

After this boundary, issue #192 still separately owns:

1. production observer-root provisioning and runtime composition;
2. temporary export-login creation, bounded credential custody, one-time
   claim of an immediately admitted result, expiry, revocation, backend
   termination, drop, and verified structural closure;
3. protected output delivery only after structural closure;
4. independently witnessed surviving-store process-crash intervals;
5. final real-ASGI/PostgreSQL cross-slice hostile evidence; and
6. final parent-issue closure audit.

The future credential lifecycle must invoke this runner itself with original
carriers in the same call chain. It may not accept a serialized admitted
result or infer authority from an admission row.

## 14. Stop and reapproval conditions

Stop and require a new decision version before implementation or merge if work
would:

- change the receipt, approval, request, signature, or observer-root schema;
- change approver independence, receipt lifetime, or request lifetime;
- accept caller time, a supplied verifier result, or a digest argument;
- add a role, login, DSN, credential, random capability, token, or secret;
- create an admission inspection, reset, delete, expiry-purge, or repair API;
- allow replay to resume or continue an operation;
- call the export runner or return audit event bytes;
- write output or choose a recipient;
- change runtime health/readiness behavior outside structural binding;
- change another migration, provisioning identity, or tenant service;
- add provider, KMS, IAM, network, environment, filesystem, log, queue,
  process, or deployment effects;
- exceed the exact path or budget boundary; or
- claim production readiness or close issue #192.

## 15. Phase A publication and decision card

Publishing this RFC and a Draft pull request is Phase A only. Publication,
checks, reviews, branch state, repository credentials, or a generic go do not
authorize Phase B.

Before a live decision card may be displayed:

1. this RFC must be the only changed path;
2. the exact RFC head must pass hosted checks;
3. two independent exact-head Phase A reviews must report zero demonstrated
   in-scope Blockers; and
4. the complete card must name the exact head, reviewed base, path boundary,
   database transition, state machine, invariants, evidence matrix, budgets,
   exclusions, and stop conditions.

The required exact later approval form is:

~~~text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-ONE-OPERATION-ADMISSION-001 version 1.
~~~

Only that exact entire later task-user message after the complete live card
authorizes prospective Phase B. It does not authorize deployment, production
operation, credentials, export, output delivery, provider actions, merge, or
issue closure.

## 16. Provisional design record

- Reviewed base: 5f51f80981599a0da4678d555a02a648b84a2304.
- Primary trust boundary: durable one-operation approval consumption.
- Phase A repository effect: one new RFC path only.
- Current decision version: proposed version 1, unapproved.
- Phase B authority: absent.
- Cloud, IAM, KMS, credential, export, output, deployment, and production
  effects: absent.
- Issue #192 remains open.
