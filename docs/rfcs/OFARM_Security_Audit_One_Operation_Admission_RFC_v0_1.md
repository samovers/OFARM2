# OFARM Security-Audit One-Operation Admission — Phase A Contract v0.2

## Status

- **Parent issue:** #192
- **Draft pull request:** #325
- **Decision:** ISSUE192-SECURITY-AUDIT-ONE-OPERATION-ADMISSION-001,
  proposed version 2
- **Phase:** Phase A design correction only; unapproved
- **Reviewed base:**
  5f51f80981599a0da4678d555a02a648b84a2304, the merge commit for PR #324
- **Primary trust boundary:** store-local durable consumption of one
  independently verified break-glass export approval, conditional on one
  separately admitted live audit-store target and epoch
- **Separate prerequisite boundary:**
  ISSUE192-SECURITY-AUDIT-ADMISSION-TARGET-EPOCH-001
- **Phase A repository effect:** this RFC is the only changed path
- **Phase B:** not authorized and not card-eligible while the prerequisite is
  absent

## 1. Version-2 correction

Formal exact-head review 5003382592 demonstrated three version-1 failures:

1. caller-selected connection information made single use local to whichever
   database copy the caller selected;
2. replacement of a lost store erased both replay state and the earlier
   nonregressing clock floor; and
3. the public connection-factory seam and publicly constructible positive
   result allowed authority substitution or fabrication.

The zero-blocker issue comment 5388488026 on the same head did not disprove
those counterexamples. Passing hosted checks on
f0ad68e0a28ca5017aadb3beaf7298fce07cc197 therefore did not make version 1
safe to implement.

Version 2 makes the smallest boundary correction:

- this decision owns database-local consumption only while the exact admitted
  target store survives;
- a separate target/epoch prerequisite must prevent concurrent use of a
  clone, bind the production connection, and close replacement-store replay
  and clock rollback before this decision can enter Phase B; and
- the admission module has no public production entry point, positive result,
  target argument, connection string, or dependency-injection seam.

This correction does not change the merged signed approval schema and does
not add deployment or store-loss authority to PR #325.

## 2. Problem and exact goal

### 2.1 The missing local boundary

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

A durable relation in one audit database can remember the first use while
that exact store survives. It cannot, by itself, prove that a caller did not
select a writable clone or that an empty replacement store did not forget a
prior use. Version 2 treats those as a separate runtime, deployment, and
store-transition authority instead of claiming that a primary key solves
them globally.

### 2.2 Exact conditional goal

After the target/epoch prerequisite is approved, merged, and pinned, a later
approved Phase B may add one private library admission path and one forward
audit-database migration. For one call on one admitted target lease, the path
must:

1. accept the original authority-receipt and approval-bundle bytes, never a
   caller-supplied verified-result object;
2. obtain and hold the separately governed admitted target lease without
   accepting a connection string or target from the caller;
3. connect only through that lease to its exact live audit-control database;
4. obtain one nonregressing database-owned Unix time in microseconds whose
   floor satisfies the admitted epoch contract;
5. invoke the merged dual-approval verifier itself with that time;
6. recheck the complete verified validity interval immediately before
   consumption using a second observation of the same nonregressing database
   clock;
7. atomically consume the exact pair (operation_id, approval_digest) in that
   store;
8. commit with synchronous_commit=on while the target lease remains held; and
9. expose success only as private control flow inside the separately governed
   future credential composition.

Only the transaction that inserts the first exact pair in the admitted,
surviving target store may reach the private committed state. No replay,
conflict, invalid approval, expired approval, failed transaction, ambiguous
commit, lost lease, quarantined epoch, clone, or replacement-store transition
may authorize later credential or export work.

### 2.3 Exact claim boundary

This decision claims at-most-one committed admission only for one operation
ID within one exact admitted target epoch while its underlying store remains
the same durable store.

It does not claim:

- uniqueness across independently writable database copies;
- uniqueness after replay-state loss or store replacement;
- that PostgreSQL system_identifier distinguishes physical clones;
- that an advisory lock inside each clone creates a cross-clone singleton;
- that a database row is positive credential authority; or
- that a private Python value is a reusable authorization token.

The target/epoch prerequisite must make exactly one target eligible at a time
and must make old approvals unusable before an empty replacement target is
eligible. This RFC must not be used without that prerequisite.

### 2.4 Why this remains one PR boundary

The relation, database functions, private verification path, tests, and
structural checks all verify one store-local first-consumption transition.

The target selector, live lease, cutover quarantine, issuance cutoff,
replacement clock floor, and route publication decide which store may act.
They form a separate deployment and store-transition trust boundary and must
travel in a separate prerequisite PR.

The temporary export LOGIN, password custody, export invocation, and output
delivery remain later independent boundaries.

## 3. Learning value

This slice will prove the following conditional handoff:

    separately admitted live target and epoch
      -> original valid signed carriers
      -> target-owned nonregressing time
      -> fresh in-process verification
      -> one atomic store-local durable consumption
      -> private post-commit control flow only

Within that admitted target, it resolves:

1. equal approval replay;
2. operation-ID reuse with different approval bytes;
3. concurrent calls racing on the same operation ID; and
4. commit ambiguity after the consumption statement has been submitted.

The result is fail-closed. A crash or ambiguous commit after durable local
consumption may burn an approved operation without producing a credential.
It may not authorize a retry. Availability recovery requires a new operation
ID and a new independently approved bundle after the target/epoch authority
has declared the store safe.

## 4. Non-goals

This decision does not authorize:

- implementation of ISSUE192-SECURITY-AUDIT-ADMISSION-TARGET-EPOCH-001;
- target selection, route publication, lease issuance, lease custody, epoch
  transition, issuance quarantine, replacement-store cutoff, clock-floor
  initialization, or clone exclusion;
- creation, update, rotation, or use of an approver private key;
- production observer-root provisioning, Google Cloud IAM, KMS, Policy
  Troubleshooter, provider evidence, credential materialization, or PR #322
  or PR #323 work;
- changing the merged authority-receipt issuer, dual-approval verifier,
  signature domains, schemas, carrier limits, five-minute authority bound, or
  two-approver independence rule;
- a caller-supplied clock, target, connection string, connection factory,
  verified object, approval digest, operation ID, validity interval, cursor,
  approver roster, or positive admission result;
- a public admission constructor, method, function, decoder, loader, or
  authority-shaped return value;
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
  retention, overflow, gap, readiness, or runtime-composition changes;
- modification of the merged store-loss recovery implementation or contract;
- a general approval ledger, generic workflow engine, legal-hold mechanism,
  or reusable authorization token; or
- issue #192 closure or a production-readiness claim.

If implementation or review requires any excluded authority, work must stop
before editing that boundary and propose a separate prerequisite or follow-up.

## 5. Trust model

### 5.1 Protected assets

- store-local single-use meaning of one valid dual-approved operation;
- exact binding of operation ID to the SHA-256 digest of the complete approval
  bundle;
- validity against the admitted target's nonregressing time authority;
- the distinction between first admission, equal replay, and conflicting
  operation reuse in the surviving store;
- transaction and commit-outcome honesty;
- the absence of a public positive-authority surface;
- the absence of credential, export, and output authority in this slice;
- the original receipt, approval bundle, target details, and dependency
  details; and
- normal audit-database structural readiness.

### 5.2 Trusted components

- the merged SecurityAuditDualApprovalVerifier implementation and its pinned
  package/conformance surface;
- the immutable security-audit migration history through version 3;
- the accepted audit-control LOGIN and capability role;
- the existing nonregressing audit-access clock primitive and its serialized
  high-water sequence;
- PostgreSQL unique-index, transaction, session_user, and synchronous-commit
  behavior;
- the repository-pinned psycopg and Ed25519 dependencies; and
- only after its separate approval and merge, the exact target/epoch
  prerequisite interface that supplies and holds the admitted target lease.

The target/epoch prerequisite is not trusted merely because this RFC names
it. Its exact interface, implementation, tests, evidence, and decision must
be independently approved.

### 5.3 Untrusted inputs and behavior

- every receipt and approval-bundle byte;
- every caller attempt to choose or substitute a target, connection, lease,
  time, verifier, or database dependency;
- malformed, expired, reordered, substituted, oversized, or invalidly signed
  carriers;
- concurrent equal and conflicting calls;
- a regressed wall clock;
- a stale, lost, expired, mismatched, or forged target lease;
- every database row and result member until exact validation;
- connection, statement, lock, rollback, close, and commit failures;
- a commit exception after the insert may already be durable;
- every attempt to replay, retry, serialize, construct, or reuse a private
  implementation value; and
- canaries in carriers, target details, database errors, dependency
  exceptions, and tracebacks.

### 5.4 Explicitly excluded attacker capabilities

- arbitrary code execution inside the admitted process;
- mutation of installed source, bytecode, interpreter, dependencies, or CA
  roots;
- compromise of PostgreSQL or its bootstrap superuser;
- compromise of the accepted audit-control credential;
- compromise of the separately governed target/epoch authority;
- simultaneous compromise of all approver, observer, database, target/epoch,
  and future credential-lifecycle authorities; and
- arbitrary memory mutation after validation.

Audit-control credential compromise can consume guessed or observed operation
IDs and cause denial of service in the admitted target. It cannot by itself
create the temporary LOGIN or cause future composition to act, because row
presence and database function output are not positive approval authority.

## 6. Authority map

| Decision | Sole authority | Forbidden substitute |
| --- | --- | --- |
| Eligible live target and epoch | Separately approved target/epoch prerequisite holding one composition-owned lease through commit | caller DSN, per-call target, environment, writable clone, system_identifier alone, or clone-local advisory lock |
| Replacement-store eligibility | Prerequisite's quarantine, trusted issuance cutoff, five-minute drain, replacement clock floor, and explicit activation | empty database, successful recovery command, wall clock, operator assertion, or route availability alone |
| Receipt and approval validity | Fresh invocation of the merged verifier over the original bytes | caller-supplied result, digest, boolean, parsed JSON, or prior verification |
| Admission time | Nonregressing clock of the admitted target, with the prerequisite-established epoch floor | process time, caller time, token timestamp, receipt timestamp, or wall-clock rollback |
| Operation identity | Verifier-returned UUIDv4 operation ID | argument, environment, filename, row, or generated replacement |
| Approval identity | Verifier-returned digest of the complete canonical approval bundle | digest argument, request digest, signature digest, or receipt digest |
| Store-local single use | First committed insert into the closed relation on the admitted surviving target | in-memory set, log, cache, file, caller assertion, a different store, or row presence alone |
| Conflict | Same operation ID with a different stored approval digest in that store | last-write-wins, second row, update, delete, or replacement |
| Replay | Same operation ID and digest already present in that store | another committed state or credential authority |
| Commit outcome | Acknowledged synchronous commit while the lease remains held | returned SQL row before commit, retry, follow-up query, or inference |
| Future credential handoff | Direct private control flow in a later separately approved closed composition | public return, serialized object, database row, database outcome, public constructor, or replay result |

## 7. Required target/epoch prerequisite

### 7.1 Separate boundary

ISSUE192-SECURITY-AUDIT-ADMISSION-TARGET-EPOCH-001 must be designed,
reviewed, approved, implemented, and merged separately. PR #325 changes none
of its authority or implementation paths.

Its minimum acceptance contract, without selecting its implementation, must:

1. admit exactly one composition-pinned audit target at a time, bind it to
   concrete database, server, migration, and deployment identity plus a live
   witness that cannot be recovered from a physical clone, and keep that lease
   held through synchronous commit acknowledgement;
2. prevent callers from selecting a target or supplying a lease and prevent a
   second writable copy from being admitted concurrently;
3. quiesce receipt issuance, admission, credential creation, and export before
   replacement-store activation and record a trusted issuance cutoff outside
   the lost replay store;
4. wait until at least 300,000,000 microseconds after that cutoff, the merged
   maximum verified authority and request window;
5. establish a replacement nonregressing clock floor at or beyond cutoff plus
   300,000,000 microseconds so every pre-cutoff approval is expired; and
6. activate the replacement as a new epoch only after those checks pass and
   bind future credential effect to the same held target lease.

System_identifier is useful evidence but cannot be the sole identity because
a promoted physical clone shares it. A server-local advisory lock is useful
only as one witness on one selected target; equal locks can be acquired on two
independent clones and therefore cannot be the sole cross-clone singleton.

### 7.2 Gate on this decision

Before this decision may enter Phase B, the prerequisite must provide a
merged, concrete, source-pinned internal interface for:

- obtaining the composition-owned lease without caller input;
- opening the fixed audit-control connection through that lease;
- confirming target identity and epoch on that connection;
- holding and rechecking the lease through commit; and
- reporting closed refusal, unavailable, and ambiguous outcomes without
  target details.

After that interface exists, this RFC must be checked against it. Any change
to the assumptions or prospective path boundary below requires a new decision
version and exact-head review. No abstract Protocol, caller-created object, or
test double may stand in for the production prerequisite.

## 8. Closed database contract

### 8.1 Forward-only migration

A later approved Phase B adds exactly:

    security_audit/migrations/
      0004_one_operation_export_admission.sql

Migrations 0001, 0002, and 0003 remain byte-identical. Version 4 must refuse
unless the exact version-3 migration ledger, structural-verifier source, and
catalog digest are present.

The authoritative migration-set literal advances from version 3 to version 4.
No provisioning identity or existing migration digest changes.

### 8.2 Admission relation

Version 4 creates exactly one owner-only relation:

    ofarm_security.security_audit_export_admission

Its columns are:

| Column | Type | Rule |
| --- | --- | --- |
| operation_id | uuid | primary key; exact RFC 4122 UUIDv4 |
| approval_digest | text | exact lowercase sha256: plus 64 hexadecimal digits |
| admitted_at_microseconds | bigint | exact nonregressing target time used by first consumption |
| valid_from_microseconds | bigint | verifier-returned lower bound |
| valid_until_microseconds | bigint | verifier-returned exclusive upper bound |

Required checks:

- operation_id has UUID version bits 4 and RFC 4122 variant bits;
- approval_digest uses the exact closed digest grammar;
- admitted_at_microseconds is nonnegative;
- valid_from_microseconds is nonnegative;
- valid_until_microseconds is greater than valid_from_microseconds; and
- admitted_at_microseconds falls inside the stored half-open validity interval.

There is no target, epoch, tenant, Party, actor, approver, key, credential,
cursor, event, output, free text, JSON, raw carrier, or exception column. The
relation's containing admitted target and epoch provide its scope; the bundle
digest binds the complete canonical request, receipt digest, statements, and
signatures.

No role receives SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, or
TRIGGER on this relation. Only the owner function may access it.

The relation and both version-4 functions are owned by
ofarm_security_audit_owner.

### 8.3 Clock wrapper

Version 4 creates:

    ofarm_security.observe_security_audit_export_admission_clock()

It:

1. is SECURITY DEFINER with search_path fixed to pg_catalog and pg_temp;
2. requires exact session_user ofarm_security_audit_control_login;
3. invokes the existing private nonregressing access-clock primitive;
4. returns exactly one row containing observed_at,
   high_water_microseconds, and clock_regressed;
5. exposes no other row or state; and
6. is executable only by ofarm_security_audit_control.

The private runner uses high_water_microseconds as verifier now_us. A
regressed wall clock does not move time backward. Eligibility of a newly
replaced clock is not decided here; the target/epoch prerequisite must first
establish its required floor.

### 8.4 Atomic consume function

Version 4 creates:

    ofarm_security.consume_security_audit_export_admission(
      uuid, text, bigint, bigint
    )

It returns one row:

    outcome text,
    admitted_at_microseconds bigint,
    valid_until_microseconds bigint

The closed database outcomes are:

- ADMITTED — this transaction inserted the first exact operation/digest pair
  in this store;
- REPLAYED — the same operation ID and digest already exist in this store; and
- CONFLICT — the operation ID exists with a different digest in this store.

The function:

1. is SECURITY DEFINER with a fixed search_path;
2. requires the exact audit-control session_user;
3. validates UUIDv4, digest grammar, and integer interval before relation
   access;
4. reobserves the nonregressing access clock;
5. requires valid_from_microseconds <= high_water_microseconds
   < valid_until_microseconds;
6. attempts one INSERT with that exact high_water_microseconds and with
   ON CONFLICT DO NOTHING;
7. returns ADMITTED only from INSERT RETURNING;
8. otherwise reads the one existing primary-key row and returns REPLAYED or
   CONFLICT without updating or deleting it; and
9. returns no stored digest or carrier data.

The function is executable only by ofarm_security_audit_control. Public and
all other audit roles receive no authority. Its ADMITTED text is a private
database control result, not credential authority.

### 8.5 Store-local concurrency and durability

For one operation ID in one exact surviving target store, PostgreSQL
primary-key serialization is the authority.

- Two equal concurrent calls on that target produce at most one ADMITTED
  database result.
- The loser observes REPLAYED only after the winner is visible.
- Equal and conflicting concurrent calls on that target produce at most one
  stored row.
- A different digest never overwrites the first digest.
- Transaction abort removes an uncommitted first insert.
- A committed first insert has no delete, reset, expiry purge, or operator
  repair path while that store survives.

The row does not survive arbitrary store loss. A copy can contain older replay
state, and an empty replacement contains none. Cross-copy and replacement
safety comes only from section 7, not from this relation.

### 8.6 Structural readiness

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

## 9. Closed private Python contract

### 9.1 Module and public surface

A later approved Phase B may add:

    deployment/postgresql/security_audit_admission.py

Its exact public export surface is limited to negative errors:

~~~python
__all__ = (
    "SecurityAuditAdmissionError",
    "SecurityAuditAdmissionRefused",
    "SecurityAuditAdmissionUnavailable",
    "SecurityAuditAdmissionOutcomeUnknown",
)

class SecurityAuditAdmissionError(RuntimeError): ...
class SecurityAuditAdmissionRefused(SecurityAuditAdmissionError): ...
class SecurityAuditAdmissionUnavailable(SecurityAuditAdmissionError): ...
class SecurityAuditAdmissionOutcomeUnknown(SecurityAuditAdmissionError): ...
~~~

There is no public admission class, function, method, target type, constructor,
positive result, dataclass, Protocol, decoder, loader, or factory override.
There is no public path that accepts a target, connection string, connection
factory, verifier, clock, dependency carrier, already verified value, or
database result.

The production-private admission entry point must:

- accept only exact original receipt bytes and approval-bundle bytes;
- obtain the target lease through the concrete fixed prerequisite import;
- open the connection through the prerequisite's concrete fixed operation,
  backed by repository-pinned psycopg and with no replaceable production
  dependency argument;
- construct its verifier from the fixed merged implementation;
- return only a module-private committed carrier after acknowledged commit;
  and
- be callable only by the later closed credential composition in the same
  trusted call chain.

The exact private entry signature and prerequisite import are intentionally
not invented in this RFC. They must be pinned from the merged prerequisite
before a live version-2 decision card. Any interface difference requires this
RFC to be amended and re-reviewed.

The module-private committed carrier is not accepted by any public API and is
not authority on its own. The later credential decision must either consume
it immediately inside the same closed composition or define a stronger
handoff under a new review. No other repository module may import or construct
it under this decision.

### 9.2 Production dependency closure

Production code has no dependency-injection constructor or call argument.
Tests may exercise a separately named module-private test helper with private
fakes, or patch fixed module-private dependencies, only if conformance proves:

- the production entry never calls the test helper;
- the production entry accepts no dependency carrier;
- test-only values cannot construct the private committed carrier;
- the test helper is absent from __all__ and is not imported by production;
  and
- repository source outside the focused test cannot reference the helper.

This testing accommodation is not a production authority seam. Arbitrary code
execution inside the admitted process remains outside the threat model; a
publicly supported substitution seam does not.

### 9.3 Input preflight

Before obtaining a lease or opening a connection, the private entry validates:

- authority_receipt_bytes is an exact bytes value from 1 through 16,384 bytes;
  and
- approval_bundle_bytes is an exact bytes value from 1 through 16,384 bytes.

These bounds restate the merged verifier contract; they do not parse or
authenticate either carrier. Any later verifier-bound change is a stop-and-
reauthorize condition here.

### 9.4 Connection and lease policy

The target/epoch prerequisite, not the carrier caller, supplies the one
control connection. The connection uses:

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

No caller conninfo is parsed or rebuilt. There is no export conninfo and no
second connection. The target lease remains held across open, identity and
epoch confirmation, both clock observations, verification, consume, commit,
and close. Lease loss or mismatch returns no private success.

### 9.5 State machine

The minimum exact states are:

    TARGET_UNRESOLVED
      -> TARGET_LEASE_HELD
      -> CONTROL_OPEN
      -> TARGET_CONFIRMED
      -> CLOCK_OBSERVED
      -> APPROVAL_VERIFIED
      -> LEASE_RECONFIRMED
      -> CONSUME_SUBMITTED
      -> FIRST_INSERT_VALIDATED
      -> COMMITTING
      -> COMMITTED_PRIVATE

Before TARGET_LEASE_HELD, invalid carriers are REFUSED and prerequisite or
dependency failure is UNAVAILABLE.

After CONTROL_OPEN and before CONSUME_SUBMITTED, invalid carrier, signature,
approval, validity, target, epoch, or lease is REFUSED after rollback where a
transaction exists. A connection, statement, or malformed result failure is
UNAVAILABLE after rollback.

After CONSUME_SUBMITTED, REPLAYED and CONFLICT are REFUSED after rollback. A
connection, statement, lease, or malformed-result failure before commit is
UNAVAILABLE and returns no private success. Any commit exception or loss of
outcome after COMMITTING is OUTCOME_UNKNOWN.

Only COMMITTED_PRIVATE may return the module-private carrier. It never crosses
a public boundary under this decision.

### 9.6 Verification and time sequence

Inside one held target lease and one transaction, the private entry:

1. confirms the concrete target identity and active epoch;
2. sets READ COMMITTED;
3. calls the clock wrapper and validates one exact row;
4. passes high_water_microseconds to a fresh merged verifier instance;
5. accepts only the verifier's private normalized result;
6. requires valid_from_us <= high_water_microseconds < valid_until_us;
7. reconfirms that the same target lease remains active;
8. calls consume with only the verified operation ID, approval digest, and
   validity bounds;
9. accepts only one exact ADMITTED row whose time remains in the interval;
10. commits while the lease remains held; and
11. constructs the private carrier only after commit returns.

There is no verified-result parameter, dependency argument, public success
return, or way to bypass the fresh verifier call.

### 9.7 Replay and ambiguity

The private entry never retries:

- lease acquisition or confirmation;
- connection creation;
- clock observation;
- verification;
- consume execution;
- result fetch;
- rollback;
- close; or
- commit.

An exact replay is a fresh SecurityAuditAdmissionRefused. A conflict is the
same outward class. Neither exposes whether an operation ID exists.

SecurityAuditAdmissionOutcomeUnknown contains no operation ID, digest, target,
carrier, database text, cause, context, or retry instruction beyond the fixed
message that the operation must not be retried.

The exact public exception messages are:

    security-audit operation admission was refused
    security-audit operation admission is unavailable
    security-audit operation admission outcome is unknown; do not retry this operation

### 9.8 Failure hygiene

Every ordinary public error is freshly constructed outside the dependency
exception handler. Its arguments and message are fixed, its cause and context
are absent, and formatting with capture_locals=false contains no carrier,
target detail, SQL, database error, key, principal, cursor, or dependency
canary.

No module path may import logging, traceback, tempfile, subprocess, socket,
asyncio, queue, pathlib, os, sys, time, secrets, random, or a cloud client.

## 10. Invariants

- OOA-001 — original carriers, not a verified object, are the only approval
  inputs.
- OOA-002 — a separately admitted target lease supplies and holds the only
  eligible store and its nonregressing epoch time through commit.
- OOA-003 — exactly one fresh verifier call occurs per committed attempt.
- OOA-004 — only the verifier-returned operation ID and approval digest reach
  the consume call.
- OOA-005 — only the first committed exact pair in the admitted surviving
  target reaches COMMITTED_PRIVATE.
- OOA-006 — equal replay in that target never reaches private success.
- OOA-007 — different-digest reuse never changes the first row.
- OOA-008 — concurrent calls on that target commit at most one first insert.
- OOA-009 — a returned SQL row before commit is not authority.
- OOA-010 — commit ambiguity is terminal and never retried.
- OOA-011 — no direct relation privilege is granted.
- OOA-012 — row presence and database outcomes are replay state, not positive
  approval authority.
- OOA-013 — no public positive result, constructor, production dependency
  seam, caller target, or caller connection exists.
- OOA-014 — no credential, role, export, output, provider, or deployment
  effect occurs.
- OOA-015 — all failures are fixed, closed, and canary-free.
- OOA-016 — normal structural readiness remains exact after migration 4.
- OOA-017 — no cross-store, cross-clone, or post-loss uniqueness claim is
  made by this decision.
- OOA-018 — Phase B is unavailable until the target/epoch prerequisite is
  independently approved, merged, and concretely pinned here.

## 11. Required Phase B evidence

### 11.1 Prerequisite evidence gate

Before any evidence below can count, repository evidence must pin the merged
target/epoch prerequisite decision, implementation head, exact internal
interface, and hostile proof for clone exclusion and replacement cutoff. A
mock, Protocol, prose promise, or issue link is insufficient.

### 11.2 Unit evidence

Focused tests must prove:

1. __all__ contains only the four negative error types;
2. no public class, function, result, target, connection, Protocol, decoder,
   loader, or factory override can produce positive admission authority;
3. invalid carrier type or size refuses before lease or database work;
4. production accepts no dependency or target argument and never reaches the
   private test helper;
5. the fixed prerequisite interface supplies and holds the connection;
6. target and epoch confirmation precede database time and consume;
7. one clock row and one fresh verifier call precede consume;
8. no caller-supplied normalized value can reach consume;
9. every valid-interval boundary is exact to one microsecond;
10. private success is withheld until commit acknowledgement;
11. REPLAYED and CONFLICT are indistinguishable fixed refusals;
12. malformed or duplicate clock and consume rows refuse;
13. every pre-submit connection and statement failure maps correctly;
14. every commit exception is OUTCOME_UNKNOWN and is never retried;
15. rollback, close, and lease-release failures cannot turn failure into
    success;
16. no production source outside the later approved composition imports or
    constructs the private committed carrier; and
17. source, import, line, function, and public-surface budgets are exact.

### 11.3 Live PostgreSQL evidence

Against the real isolated audit service and the concrete prerequisite fixture,
tests must prove:

1. migration 4 applies after exact versions 1 through 3;
2. first valid admission on the admitted target commits one exact row and
   reaches COMMITTED_PRIVATE;
3. equal replay on that target reaches no private success and creates no
   second row;
4. same operation with a different valid bundle is a conflict and preserves
   the first row;
5. two concurrent equal calls on that target produce exactly one private
   committed state;
6. two concurrent conflicting calls preserve exactly one immutable digest;
7. wrong session_user and SET ROLE paths refuse before relation access;
8. direct SELECT, INSERT, UPDATE, DELETE, TRUNCATE, COPY, and function bypass
   attempts under runtime roles refuse;
9. exact not-before, expiry, and one-microsecond boundary cases use the target
   nonregressing clock;
10. a forced wall-clock rollback cannot make an expired operation current;
11. a lost or mismatched target lease returns no private success;
12. transaction rollback leaves no admission row;
13. table, constraint, function, source, ACL, migration-ledger, and catalog
    drift make structural readiness false; and
14. no temporary export LOGIN exists before or after every test.

Cross-clone singleton and replacement-store cutoff tests belong to the
prerequisite. This slice must consume their pinned real interface and may not
duplicate their authority.

All test-generated signing keys, receipts, bundles, and passwords remain
inside isolated test fixtures. Tests call no provider and access no production
resource.

### 11.4 Repository evidence

Phase B must pass:

- focused admission and audit migration tests;
- the target/epoch prerequisite's pinned conformance check;
- package-contract conformance;
- rewrite-architecture conformance;
- temporal candidate and decision-log checks;
- both complete review baselines with clean-run equivalence;
- native verifier amd64 and arm64 jobs;
- canonical multi-platform index assembly; and
- git diff --check.

## 12. Prospective Phase B repository boundary

Only a later exact approval, after section 7 is satisfied, may authorize edits
to these eleven paths:

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
and inventory are mechanical verification of the same store-local admission
boundary. The separate target/epoch prerequisite changes no path in this PR.

Phase B must stop before touching another path.

## 13. Budgets and architecture controls

- new production admission module: at most 420 physical lines;
- every production function: at most 80 physical lines;
- new focused test module: at most 1,300 physical lines;
- migration 4: at most 700 physical lines;
- no new dependency or lockfile;
- no test-glob widening beyond the exact new admission test;
- direct repository imports limited to:
  - deployment.postgresql.security_audit_approval;
  - deployment.postgresql.security_audit_access; and
  - the exact merged target/epoch prerequisite module pinned by a later RFC
    amendment;
- standard-library imports limited to dataclasses, enum, typing, and uuid;
- third-party imports limited to psycopg and its already pinned submodules;
- no public positive class, function, method, result, Protocol, target,
  connection, factory, decoder, or loader; and
- no production dependency argument or public construction from an already
  verified object.

The architecture checker must prohibit the forbidden effect names and imports
from section 9.8, direct export-runner use, credential or role SQL, output
writes, retry loops, sleeps, environment access, public target selection,
caller connection information, production dependency injection, and external
construction or import of the private committed carrier.

## 14. Review classification

An in-scope Blocker demonstrates that:

- the RFC or implementation claims cross-store, cross-clone, or post-loss
  uniqueness from the local relation;
- Phase B can begin without the approved concrete target/epoch prerequisite;
- a caller can select or substitute the production target, connection, lease,
  clock, verifier, or dependency;
- a public or externally accepted positive result can be constructed or
  replayed;
- an equal or conflicting replay on the admitted target can return private
  success;
- concurrent calls on the admitted target can commit more than one first row;
- caller-owned time or a supplied verified object can bypass verification;
- a regressed target clock can extend validity;
- the first row can be updated, deleted, or replaced while the store survives;
- a private committed state can precede acknowledged commit;
- an ambiguous commit can be retried or called successful;
- a runtime role can access the relation or functions outside the exact grant;
- row presence or a database outcome becomes positive authority;
- sensitive input reaches a public error or repository artifact;
- normal structural readiness does not bind the new objects; or
- the implementation crosses into target/epoch, store-loss, credential,
  export, output, provider, runtime, or deployment authority.

Preferences about a generic workflow engine, long-term admission history,
operator inspection, manual reset, credential creation, output delivery, or
process-crash recovery are follow-ups unless they demonstrate one invariant
cannot hold.

## 15. Dependencies and ordered follow-ups

### 15.1 Satisfied dependencies

- Issues #169, #170, #172, #173, and #174 are closed.
- PRs #318, #319, #320, #321, and #324 are merged.
- The merged dual-approval verifier is the only cryptographic verifier used.
- The merged nonregressing audit-access clock is the only database time
  authority.
- PRs #322 and #323 remain separate provider-evidence work and do not change
  this store-local admission boundary.

### 15.2 Unsatisfied prerequisite

ISSUE192-SECURITY-AUDIT-ADMISSION-TARGET-EPOCH-001 does not yet have the
approved, merged, concrete interface required by section 7. This makes Phase B
and the live decision card unavailable.

### 15.3 Ordered follow-ups

Issue #192 still separately owns, in order:

1. the target/epoch prerequisite, including clone exclusion and replacement-
   store cutoff and clock floor;
2. this store-local one-operation admission implementation after the
   prerequisite is pinned;
3. production observer-root provisioning and runtime composition;
4. temporary export-login creation, bounded credential custody, immediate
   private admission handoff, expiry, revocation, backend termination, drop,
   and verified structural closure;
5. protected output delivery only after structural closure;
6. independently witnessed surviving-store process-crash intervals;
7. final real-ASGI/PostgreSQL cross-slice hostile evidence; and
8. final parent-issue closure audit.

The future credential lifecycle must invoke the private admission path with
original carriers in the same closed call chain. It may not accept a public or
serialized admitted result or infer authority from an admission row.

## 16. Stop and reapproval conditions

Stop and require a new decision version before implementation or merge if work
would:

- begin Phase B before the section-7 prerequisite is approved and merged;
- invent or abstract the prerequisite interface instead of pinning its merged
  concrete form;
- change target selection, lease, epoch, cutoff, clock-floor, store-loss,
  deployment, or route-publication authority in this PR;
- change the receipt, approval, request, signature, or observer-root schema;
- change approver independence, receipt lifetime, or request lifetime;
- accept caller time, target, connection, dependency, supplied verifier
  result, or digest argument;
- add a public positive admission surface or externally accepted private
  carrier;
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

## 17. Phase A publication and decision card

Publishing this corrected RFC to Draft PR #325 is Phase A only. Publication,
checks, reviews, branch state, repository credentials, or a generic go do not
authorize Phase B.

Before a live decision card may be displayed:

1. this RFC must be the only changed path;
2. the exact RFC head must pass hosted checks;
3. two independent exact-head Phase A reviews must report zero demonstrated
   in-scope Blockers;
4. ISSUE192-SECURITY-AUDIT-ADMISSION-TARGET-EPOCH-001 must be independently
   approved and merged with its concrete interface pinned in this RFC; and
5. the complete card must name the exact head, reviewed base, path boundary,
   prerequisite, database transition, private state machine, invariants,
   evidence matrix, budgets, exclusions, and stop conditions.

Only after all five gates may the live card display this exact later approval
form:

~~~text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-ONE-OPERATION-ADMISSION-001 version 2.
~~~

That exact entire later task-user message after the complete live card would
authorize only the prospective Phase B paths. It would not authorize the
target/epoch prerequisite, deployment, production operation, credentials,
export, output delivery, provider actions, merge, or issue closure.

## 18. Provisional design record

- Reviewed base: 5f51f80981599a0da4678d555a02a648b84a2304.
- Superseded Phase A head:
  f0ad68e0a28ca5017aadb3beaf7298fce07cc197.
- Primary trust boundary: store-local one-operation approval consumption,
  conditional on one separately admitted target and epoch.
- PR boundary: one corrected RFC path only; no cross-boundary exception.
- Current decision version: proposed version 2, unapproved.
- Target/epoch prerequisite: absent and unsatisfied.
- Live decision card: unavailable.
- Phase B authority: absent.
- Cloud, IAM, KMS, credential, export, output, deployment, and production
  effects: absent.
- Issue #192 remains open.
