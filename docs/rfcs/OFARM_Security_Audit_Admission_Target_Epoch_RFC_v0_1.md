# OFARM Security-Audit Admission Target Epoch — Phase A Contract v0.1

## Status

- **Parent issue:** #192
- **Draft pull request:** pending publication
- **Decision:** ISSUE192-SECURITY-AUDIT-ADMISSION-TARGET-EPOCH-001,
  proposed version 1
- **Phase:** Phase A design only; unapproved
- **Reviewed base:**
  5f51f80981599a0da4678d555a02a648b84a2304, the merge commit for PR #324
- **Primary trust boundary:** trusted selection, live binding, quiescence, and
  replacement activation of the one audit-store epoch eligible for
  break-glass authority operations
- **Phase A repository effect:** this RFC is the only changed path
- **Intended final PR boundary:** this RFC; one target-epoch module; one
  forward audit migration; exact structural and store-loss integration;
  focused tests; minimal deployment documentation; architecture registration;
  and mechanical review-inventory regeneration
- **Phase B:** not authorized

## 1. Problem and exact goal

### 1.1 Why a database row is not enough

Draft PR #325 deliberately narrows one-operation approval consumption to one
exact surviving audit store. A primary key in that store can serialize equal
and conflicting operation IDs on that store. It cannot prove which writable
copy a caller selected, and it disappears when the accepted empty-recreate
store-loss posture replaces the database.

The same limitation applies to the existing nonregressing audit-access clock.
Its high-water sequence is durable while the store survives, but an empty
replacement begins without the earlier floor. A still-valid authority receipt
could therefore appear current again if a replacement were published with an
earlier clock and empty replay state.

`pg_control_system().system_identifier` does not close the first gap. A
promoted physical clone shares it. An advisory lock does not close it either:
equal locks can be held independently on two postmasters. The merged store-loss
runner uses a live advisory-lock witness correctly for one invocation: every
connection must see locks held by one retained backend on one live server. That
witness ends when recovery ends and is not a durable deployment election.

### 1.2 Exact goal

This decision defines the smallest repository boundary that a later trusted
break-glass composition may use to:

1. install one deployment-selected audit-store epoch before any authority
   receipt, approval admission, credential, or export operation is permitted;
2. keep one live target witness held for the complete installed lifetime;
3. open operation connections only through the installed fixed route and
   prove on each connection that the same witness, database, server, epoch,
   and structural contract remain present;
4. prevent per-operation callers from supplying a target, route, connection,
   epoch, witness, lease, time, activation record, or positive result;
5. serialize authority-receipt issuance with quiescence so the retirement
   bound upper-bounds every receipt successfully released by that composition;
6. stop new issuance and break-glass work, drain in-flight work, and retire the
   live witness before a replacement can become eligible;
7. require a replacement activation record outside the lost audit store to
   carry the predecessor cutoff and maximum authority expiry;
8. refuse replacement activation until both the trusted authority-time domain
   and the replacement database clock are at or beyond that maximum expiry;
9. establish the replacement database's nonregressing access-clock floor at
   or beyond the same bound before inserting one immutable new epoch row; and
10. provide the exact private, source-pinned lease interface that PR #325 and
    a later credential-lifecycle composition must hold through their effects.

The result is fail closed. It is not a general database failover system. It
does not discover, elect, fence, promote, destroy, or route PostgreSQL servers.

### 1.3 Exact claim boundary

Within the stated trust model, an ACTIVE target-epoch installation means:

- one trusted deployment composition selected the fixed control route and
  supplied one exact activation capsule plus its separate 32-byte activation
  nonce;
- the capsule is bound to one immutable epoch row on the selected store;
- one module-owned session currently holds the capsule-derived live witness on
  that exact postmaster;
- every governed operation connection can see that witness locally and match
  the exact epoch row; and
- replacement activation cannot make a pre-cutoff signed approval current.

It does not mean PostgreSQL elected a global primary. Cross-process and
cross-host exclusivity is owned by the external deployment authority, which
must attach the current capsule and nonce to exactly one trusted break-glass
composition and must terminate and detach the predecessor before issuing a
replacement. The repository module makes route drift and copied-store use by
that composition mechanically visible; it does not invent a distributed
control plane.

Compromise or deliberate duplication by that deployment authority is outside
the claim. This limitation is explicit so a local row, system identifier,
nonce digest, or advisory lock is never misrepresented as global consensus.

### 1.4 Relationship to PR #325

This decision owns target and epoch eligibility. PR #325 owns only store-local
first consumption after it obtains the private lease defined here.

After this prerequisite is approved, implemented, and merged, PR #325 must
receive a new exact-head Phase A amendment that pins:

- the merged target-epoch decision and implementation head;
- the exact private lease and fixed control-connection methods;
- the resulting migration number shift from its provisional migration 4 to
  migration 5;
- the target-epoch clock-floor observation used by its verifier; and
- the still-separate trusted observer-public-key construction path.

This RFC does not edit PR #325 and does not make its current head card-eligible.

## 2. Learning value and smallest coherent change

The slice proves one previously missing chain:

```text
trusted deployment selection outside the audit store
  -> separate noncopyable activation nonce
  -> immutable store-local epoch row
  -> retained live-postmaster witness
  -> fixed-route operation lease
  -> quiesced receipt-expiry bound
  -> replacement clock floor
  -> new epoch eligibility
```

Each element has one job:

- the deployment authority decides which composition receives current
  activation material;
- the nonce is not copied with a physical database clone;
- the epoch row binds the capsule to the selected store and survives ordinary
  process restart;
- the live witness detects connection routing to another live postmaster;
- the issuance gate produces a cutoff from the same time source actually used
  by successful receipt issuance;
- the replacement barrier expires every predecessor receipt and request; and
- the database floor prevents a fresh store from moving verification time
  behind that barrier.

Removing any one reopens a demonstrated gap. Adding an election service,
provider lease, background controller, generic workflow engine, receipt-schema
epoch, observer-root rotation, or backup system is unnecessary for the V1
pre-deployment threat model and is excluded.

## 3. Non-goals

This decision does not authorize or add:

- Phase B implementation, merge, deployment, release, or production use;
- modification of PR #325 in this pull request;
- PostgreSQL discovery, election, failover, promotion, fencing, destruction,
  backup, restore, replica, WAL archive, snapshot, or CDC capability;
- a cloud control plane, provider API, IAM change, secret-manager call, network
  lease service, DNS mutation, route-publication command, KMS-client
  construction, or direct KMS operation outside the already merged issuer;
- creation or custody of observer, approver, KMS, database-login, export-login,
  output-encryption, or recipient credentials;
- observer-root admission, provider evidence, provider currentness, manifest
  provisioning, key rotation, or approver-roster selection;
- changes to authority-receipt, approval-request, approval-statement,
  signature-domain, signature, audience, or five-minute validity schemas;
- a signed epoch claim in an authority receipt or approval request;
- approval verification, durable operation consumption, temporary-login
  creation, password generation, role grants, export execution, paging,
  output delivery, or cleanup;
- producer, authentication, request-router, HMAC, retention, overflow, gap,
  health, HTTP readiness, tenant, UnitOfWork, or application-runtime behavior;
- a public target, route, lease, epoch, clock, activation, quiescence, or
  positive-authority API;
- a scheduler, daemon, background refresh, retry loop, wait loop, queue, spool,
  cache, registry, telemetry stream, or generic plugin seam;
- recovery of an ambiguous epoch-row commit in the same activation invocation;
- automatic store-loss detection or proof of the time before the first trusted
  post-loss observation; or
- issue #192 closure or a production-readiness claim.

If implementation or review requires any excluded authority, work stops before
editing that boundary and proposes a separate prerequisite or follow-up.

## 4. Trust model

### 4.1 Protected assets

- one eligible audit-store epoch for break-glass authority effects;
- no caller-selected writable clone or replacement target;
- no successful receipt after quiescence begins;
- an expiry barrier that upper-bounds every predecessor receipt released by
  the governed composition;
- no reappearance of predecessor approval validity on an empty replacement;
- live connection binding through commit and later credential effect;
- the activation nonce, DSN, witness keys, backend PID, system identifier,
  epoch details, capsule bytes, and retirement evidence;
- fixed, canary-free failures; and
- separation from observer-root, signing-key, database-login, credential,
  export, output, and deployment-mutation authority.

### 4.2 Trusted components and actors

- the external deployment authority that selects one fixed target, supplies
  one canonical capsule and separate nonce to exactly one trusted break-glass
  composition, and never concurrently supplies active predecessor and
  replacement material;
- that authority's protected storage and delivery of activation material
  outside the audit database;
- for abrupt loss, its proof that every predecessor composition is terminated
  before it observes the cutoff used for replacement;
- one deployment-certified UTC Unix-microsecond clock domain that does not
  regress across governed receipt issuance, orderly quiescence, or the
  post-termination loss cutoff;
- the exact production target-epoch module and Python process-lock semantics;
- Python `time.time_ns()` as the module's sole production observation of that
  certified authority-time domain;
- SHA-256 preimage and collision resistance, strict canonical JSON, and exact
  integer arithmetic;
- PostgreSQL 17 session advisory locks, `pg_locks`, transactions,
  synchronous-commit, system identity, database identity, role, and primary
  posture;
- the existing nonregressing audit-access clock primitive and serialization
  lock;
- the exact merged audit migration, provisioning, catalog, and structural
  authorities; and
- the merged authority-receipt issuer, but only when called through the
  private governed issuance wrapper in this decision.

The deployment authority is a real authority, not evidence manufactured by
the audit database. Before production, its operational implementation,
exclusive attachment, trusted-clock evidence, and protected input delivery
must be independently reviewed. Repository approval does not deploy it.

### 4.3 Untrusted inputs and behavior

- every receipt, approval bundle, request, cursor, operation ID, and future
  export argument;
- every per-operation attempt to supply or replace target information;
- copied, stale, reordered, malformed, oversized, or noncanonical capsule
  bytes presented outside trusted bootstrap;
- a capsule without its exact separate nonce, or a nonce with a copied store;
- a physical clone carrying the same system identifier, database OID, schema,
  epoch row, and replay rows;
- split routing of the witness, activation, operation, verification, commit,
  credential, or export connection;
- concurrent issuance, admission, quiescence, close, and operation attempts;
- ordinary connection, query, commit, close, clock, and cleanup failures;
- target loss at every state transition;
- a regressed process or PostgreSQL clock observation;
- ambiguous epoch-row commit acknowledgement;
- caller-created private-looking Python values; and
- canaries in activation material, DSNs, database errors, and dependency
  exceptions.

No untrusted request can choose the capsule, nonce, DSN, witness key, epoch,
clock, issuer, connection, lease, timeout, retry, replacement barrier, or
state transition.

### 4.4 Explicitly excluded attacker capabilities

- compromise or deliberate equivocation by the external deployment authority;
- attachment of the protected current nonce to two independent trusted
  compositions or writable copies;
- arbitrary in-process code execution, private-field mutation, source
  substitution, or memory corruption;
- operating-system, Python runtime, dependency, PostgreSQL, superuser, or
  protected-filesystem compromise;
- theft of the accepted audit-control credential or activation nonce;
- deliberate falsification of the certified UTC clock premise;
- a malicious observer, approver, or later credential authority acting in
  concert with the deployment authority; and
- forced process termination that prevents an orderly retirement report.

Forced termination and store loss remain supported operational events, but
their replacement path uses the conservative post-termination cutoff rather
than claiming an unavailable orderly report exists.

## 5. Authority map

| Decision | Sole authority | Forbidden substitute |
| --- | --- | --- |
| Which target may be installed | External deployment authority's one protected current capsule, nonce, and fixed bootstrap route | request DSN, environment fallback, database self-attestation, discovery, system identifier alone, or route availability |
| Cross-process exclusivity | External deployment authority's exclusive material attachment and predecessor termination | epoch row, nonce digest, advisory lock, PID, hostname, DNS, or process-local singleton |
| Store-local epoch identity | One immutable singleton row created by migration 4 and bound to the exact capsule and nonce digests | caller UUID, table emptiness, schema version, or recovery report alone |
| Live postmaster | One retained module-owned witness backend holding both nonce-derived advisory locks | system identifier, database OID, server version, connection success, or a lock acquired independently on another clone |
| Operation target | Fixed installed route plus the connection-local witness and epoch assertion | supplied connection, factory, pool, lease, result, or parsed capsule |
| Authority issuance time | Target-epoch module's sole `time.time_ns() // 1000` observation under its issuance gate | receipt caller, wall clock outside the certified domain, KMS response, database clock, or token timestamp |
| Successfully released receipt expiry | Exact issuance `now_us + 300_000_000`, registered under the gate before bytes leave the wrapper | KMS completion, caller report, log, or later receipt parsing |
| Orderly cutoff | First governed authority-time observation after issuance and all target leases are blocked and drained | unrelated operator timestamp or database wall clock |
| Abrupt-loss cutoff | Certified authority-time observation after external proof that all predecessor compositions are terminated | loss declaration time, recovery interval start, replacement creation time, or an unbounded clock |
| Replacement not-before | Exact cutoff plus 300,000,000 microseconds, also not less than every registered successful receipt expiry | sleep duration, store emptiness, process uptime, or operator assertion alone |
| Replacement database floor | Existing nonregressing access clock observed at or beyond not-before in the activation transaction | fresh sequence initial value, `clock_timestamp()` without floor persistence, or process time alone |
| Replacement activation | Acknowledged synchronous commit of one exact epoch row while the new live witness remains held | SQL returned row, recovery success alone, route publication, or ambiguous commit |
| Approval validity and consumption | Merged verifier and later PR #325, after this private lease is held | target-epoch row or lease itself |
| Future credential effect | Separate later credential decision while this same private lease remains held and its effect connection passes the live assertion | lease serialization, row presence, caller token, or prior admission result |

There is no database-only or advisory-lock-only global singleton claim.

## 6. Closed activation capsule and nonce

### 6.1 Trusted-bootstrap-only inputs

Future trusted composition supplies exactly once, before any governed call:

1. one canonical activation capsule of 1 through 4,096 bytes;
2. one exact 32-byte activation nonce delivered separately from the capsule
   and never stored in the audit database; and
3. one fixed audit-control DSN captured by trusted composition and never
   accepted by a governed operation.

These values enter only the module-private bootstrap function. They are not
request inputs and are not exposed by `__all__`. The production bootstrap has
no connection-factory, clock, nonce-source, parser, dependency bag, or callback
override. A separate private test helper may inject deterministic dependencies;
architecture conformance proves production never calls it.

### 6.2 Canonical capsule

The capsule uses strict canonical JSON: exact UTF-8 bytes, no BOM, no duplicate
members or non-JSON constants, exact types and member sets, ASCII-safe
serialization, sorted keys, and separators `(',', ':')`. Re-serialization must
equal the input bytes.

Its exact shape is:

```json
{
  "activationKind": "INITIAL",
  "activationNonceSha256": "sha256:<64 lowercase hexadecimal digits>",
  "databaseName": "ofarm_security",
  "epochId": "<canonical lowercase RFC 4122 UUIDv4>",
  "expectedServerVersion": "17.10 (Debian 17.10-1.pgdg13+1)",
  "expectedServerVersionNum": 170010,
  "expectedSystemIdentifier": "<nonzero ASCII decimal PostgreSQL system identifier>",
  "predecessorAuthorityNotAfterUnixMicroseconds": 0,
  "predecessorEpochId": null,
  "predecessorIssuanceCutoffUnixMicroseconds": 0,
  "recoveryReportSha256": null,
  "schemaVersion": "ofarm.security-audit-admission-target-epoch-activation.v1",
  "serviceIdentity": "ofarm-postgresql-security-audit-v1"
}
```

The exact supported PostgreSQL version strings and service identity are the
repository authorities at implementation head, not configurable values. The
example above is illustrative; Phase B pins them to the then-current accepted
version-policy and provisioning constants.

`activationKind` is exactly `INITIAL` or `REPLACEMENT`.

For `INITIAL`:

- predecessor epoch and recovery digest are null;
- cutoff and not-after are zero; and
- the trusted deployment authority asserts that no authority receipt has ever
  been released for this service before initial activation.

For `REPLACEMENT`:

- predecessor epoch is one canonical UUIDv4 different from the new epoch;
- cutoff is a positive bounded integer;
- not-after equals cutoff plus exactly 300,000,000 microseconds without
  overflow; and
- recovery report digest is the SHA-256 digest of the exact successful merged
  store-loss recovery report for the replacement target.

An orderly retirement report may prove a later successful-receipt expiry than
the first cutoff calculation only if a receipt escaped after cutoff, which the
state machine forbids. Phase B nevertheless computes the replacement bound as
`max(cutoff + 300_000_000, greatest_registered_expiry)` and requires equality
with the capsule. This defensive equality makes every successfully released
receipt explicit in evidence.

The capsule contains no DSN, host, port, username, password, raw nonce,
witness address, backend PID, KMS resource, approver, observer key, receipt,
approval, credential, cursor, event, or output location.

### 6.3 Nonce role and limit

The activation nonce is a deployment capability, not a signing key and not a
public epoch identifier. Phase B validates exact type and length and compares
`sha256(nonce).hexdigest()` with the capsule. It then computes exactly
`sha256(b"OFARM_SECURITY_AUDIT_TARGET_EPOCH_WITNESS_V1\x00" + nonce).digest()`
and drops the raw input reference after the witness is installed.

The first eight derived bytes form one signed big-endian two's-complement
64-bit advisory key. Bytes 8 through 11 and 12 through 15 form one pair of
signed big-endian two's-complement 32-bit keys. These are PostgreSQL's
non-overlapping advisory-lock namespaces. Both locks must be acquired
nonblockingly by one retained session.

A database clone copies the nonce digest and epoch row, not the protected
nonce or the live backend locks. If the deployment authority duplicates the
nonce attachment, two clones can each acquire local locks; that is the
explicitly excluded deployment-authority compromise, not a hidden global-lock
claim.

## 7. Closed migration-4 database contract

### 7.1 Forward-only migration

A later approved Phase B adds exactly:

```text
security_audit/migrations/0004_admission_target_epoch.sql
```

Migrations 1 through 3 remain byte-identical. Migration 4 advances the complete
security-audit migration, structural-observer, catalog, and contract identities
through the repository's existing forward-only mechanisms.

PR #325 must later rename its prospective consumption migration to version 5.

### 7.2 Immutable singleton relation

Migration 4 creates one owner-only relation:

```text
ofarm_security.security_audit_admission_target_epoch
```

It has exactly these columns:

| Column | Type | Rule |
| --- | --- | --- |
| singleton | boolean | primary key; must be true |
| epoch_id | uuid | canonical RFC 4122 UUIDv4 |
| activation_kind | text | `INITIAL` or `REPLACEMENT` |
| activation_capsule_digest | text | exact lowercase `sha256:` digest |
| activation_nonce_digest | text | exact capsule-bound lowercase `sha256:` digest |
| predecessor_epoch_id | uuid nullable | null only for initial; distinct UUIDv4 for replacement |
| predecessor_issuance_cutoff_us | bigint | zero for initial; positive for replacement |
| predecessor_authority_not_after_us | bigint | zero for initial; exact cutoff plus 300,000,000 for replacement |
| recovery_report_digest | text nullable | null for initial; exact lowercase `sha256:` digest for replacement |
| database_oid | oid | observed from the activation connection |
| system_identifier | text | observed nonzero ASCII decimal identifier |
| server_version_num | integer | exact accepted version policy |
| activated_at_us | bigint | nonregressing database high-water used by activation |

Checks encode every relationship above. `activated_at_us` must be at or beyond
`predecessor_authority_not_after_us`.

No target route, host, port, password, raw nonce, witness key, backend PID,
receipt, approval, operation, credential, event, cursor, actor, Party, tenant,
JSON, free text, or mutable status is stored.

No role receives direct SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES,
or TRIGGER authority. There is no update, delete, reset, rotation, purge,
repair, second-row, or conflict-overwrite path. A different epoch requires an
empty replacement store and a new capsule; it cannot replace the row in a
surviving store.

### 7.3 Activation function

Migration 4 creates one security-definer function:

```text
ofarm_security.activate_security_audit_admission_target_epoch(
  uuid, text, text, text, uuid, bigint, bigint, text
)
```

The arguments are, in order: epoch ID, activation kind, capsule digest, nonce
digest, predecessor epoch ID, predecessor cutoff, predecessor not-after, and
recovery report digest.

The function is owned by the exact audit owner. The caller-side transaction
assertion has `session_user = current_user =
ofarm_security_audit_control_login`; inside the security-definer body,
`session_user` remains that control login and `current_user` is exactly
`ofarm_security_audit_owner`. The function:

1. requires that exact session-user/definer-owner pair;
2. requires READ COMMITTED, read-write, `synchronous_commit=on`, UTC, the
   accepted DateStyle, and the fixed statement posture;
3. validates every scalar and cross-field rule before relation access;
4. calls the existing private nonregressing access-clock primitive exactly
   once under its existing serialized lock;
5. refuses if the database clock regressed or its high-water is below the
   predecessor not-after bound;
6. reads database OID, system identifier, version, and primary/read-write
   posture from that same live transaction;
7. inserts the one exact row only when the relation is empty;
8. on an existing row, returns an exact `PRESENT` outcome only when every
   supplied and live-observed field is equal, without mutation;
9. otherwise refuses without update or second row; and
10. returns one fixed row containing only `ACTIVATED` or `PRESENT`, epoch ID,
    and activated-at microseconds.

Only the audit-control capability role receives EXECUTE. A direct call can at
most install or preempt a row and cause denial of service. It cannot establish
the separate nonce possession, live witness, trusted composition, or private
positive lease required for break-glass effects.

### 7.4 Observation function

Migration 4 creates one security-definer observation function callable only by
the audit-control role. It returns the exact immutable epoch fields needed by
the private connection-local assertion and no secret or route detail.

It does not activate, update, delete, advance time, issue a lease, return a
public boolean, or authorize an operation. Row presence is negative
store-local state until the target-epoch module also proves its live witness.

### 7.5 Activation commit and ambiguity

The private activation runner commits with `synchronous_commit=on` while the
witness remains held. It enters ACTIVE only after commit acknowledgement and
one fresh connection-local observation of the exact row and witness.

Any commit exception is `OUTCOME_UNKNOWN`. The invocation closes its witness,
returns no authority, and is never retried. A later clean process may inspect
the exact immutable row under the same trusted capsule and nonce and receive
`PRESENT`; that is a new startup observation, not inference inside the
ambiguous invocation.

### 7.6 Structural and store-loss integration

Migration 4 is bound into the complete structural observer, migration set,
catalog digest, and readiness contract. Structural readiness binds the exact
relation and functions but does not treat row presence as positive authority
and does not require activation for the ordinary application runtime. This
Phase B library changes no current HTTP or application startup readiness
behavior.

The merged store-loss runner is mechanically amended so its fresh and final
state observations require the new epoch relation to contain zero rows. It
still returns success before replacement activation. It does not create the
epoch, advance the access clock, consume the activation capsule, or publish a
route. All prior store-loss witness, one-gap, no-retry, and quarantine
invariants remain unchanged.

If this exact zero-row integration cannot be made without changing another
store-loss authority, Phase B stops and requests a new decision rather than
silently widening this PR.

## 8. Closed private Python contract

### 8.1 Module and public surface

A later approved Phase B adds:

```text
deployment/postgresql/security_audit_target_epoch.py
```

Its exact public export surface contains only four empty negative error types:

```python
__all__ = (
    "SecurityAuditTargetEpochError",
    "SecurityAuditTargetEpochRefused",
    "SecurityAuditTargetEpochUnavailable",
    "SecurityAuditTargetEpochOutcomeUnknown",
)
```

There is no public activation class, target, route, capsule, nonce, epoch,
lease, witness, time, retirement report, result, factory, loader, decoder,
clock, connection, Protocol, function, method, or positive constructor.

### 8.2 Exact production-private interface

The module owns these exact production-private operations:

```python
_activate_security_audit_target_epoch(
    capsule_bytes: bytes,
    activation_nonce: bytes,
    control_dsn: str,
) -> None

_hold_security_audit_target_epoch() -> AbstractContextManager[_TargetEpochLease]

_issue_security_audit_authority_receipt(
    issuer: SecurityAuditAuthorityReceiptIssuer,
) -> bytes

_begin_security_audit_target_epoch_quiescence() -> None

_finish_security_audit_target_epoch_quiescence() -> bytes
```

Only a later approved trusted bootstrap composition may call `_activate`. The
activation bytes, nonce, and DSN are startup configuration, never operation
arguments. Architecture conformance forbids the future operation-admission,
credential, and export modules from importing or calling `_activate`,
`_begin_security_audit_target_epoch_quiescence`, or
`_finish_security_audit_target_epoch_quiescence`.

PR #325 may later import only the negative errors and
`_hold_security_audit_target_epoch`. It receives no activation inputs and
cannot replace the installed route.

The private lease is created only by the active module singleton. It has no
serializer, decoder, public constructor, equality authority, copy support, or
use after context exit. It can:

- open the fixed audit-control connection captured at activation;
- assert the exact witness, target, epoch, role, transaction, and structural
  posture on that connection;
- reassert the same facts immediately before mutation and after acknowledged
  commit; and
- assert that a separately owned future fixed credential-effect connection
  reaches the same witness, database, server, and epoch while leaving that
  connection's role and effect policy to the credential boundary.

The last method is not a generic connection-authority API. It is private,
accepts only a real psycopg connection inside the future closed composition,
performs the exact fixed SQL assertion, and never returns a reusable positive
value. A caller-supplied fake or per-operation connection is not production
reachable.

### 8.3 Production dependency closure

Production code uses direct repository imports, `psycopg.connect`,
`time.time_ns`, SHA-256, canonical JSON, and fixed SQL. It has no public or
production dependency injection.

Deterministic tests use one module-private dependency carrier reachable only
through a private test helper. Architecture checks prove:

- the production-private activation function constructs its real dependencies
  directly;
- no production path calls the test helper;
- no public function accepts a dependency;
- no operation path reads environment variables or files to replace an
  installed target; and
- no production source outside an exact later allowlist imports the private
  lease or installation operations.

### 8.4 Live witness

Activation opens one autocommit witness connection through the fixed control
route, validates exact audit-control role, database, supported server version,
system identifier, primary/read-write posture, and capsule target identity,
then acquires both nonce-derived locks nonblockingly.

The private witness carrier contains only the database OID, system identifier,
version, witness backend PID, epoch ID, capsule digest, nonce digest, and two
lock addresses. The raw nonce and DSN are not fields on a returned carrier.

Every activation, operation, issuance precheck, issuance postcheck, future
credential effect, and final retirement observation uses the same fixed
connection-local SQL assertion. It proves:

- the witness backend is present on that server;
- it holds exactly the two expected granted exclusive session locks in the two
  namespaces and no duplicate matching lock;
- current database, OID, system identifier, version, primary/read-write
  posture, and exact epoch row match; and
- the connection's separately owned role and transaction requirements hold.

A connection routed to an independently initialized service or promoted
physical clone cannot see the retained backend locks and refuses before its
first clock read, verifier call, mutation, KMS call, credential effect, or
export effect.

Loss of the witness is terminal for that installed process. It is not
reacquired, resampled, or replaced. Every later call refuses until a new trusted
process performs a complete activation.

## 9. Authority-time and receipt-issuance gate

### 9.1 One exact time source

The target-epoch module is the sole future production caller that may supply
`now_us` to `SecurityAuditAuthorityReceiptIssuer.issue`.

It obtains the value as:

```text
time.time_ns() // 1000
```

under its internal lock, requires a non-boolean integer in the issuer's exact
range, and keeps a process-local greatest observation. Any later smaller value
terminally quarantines the installation. Equal observations are allowed.

The KMS response does not attest time. The database clock is not receipt
issuance time. No other production source may invoke the issuer directly;
architecture conformance enforces the import and call boundary.

The external deployment authority must certify that this system UTC source
does not regress across every process allowed to issue and, for abrupt loss,
the post-termination cutoff observer. Without that evidence, production
activation is forbidden. The repository does not manufacture the premise.

### 9.2 Issuance ordering

For one issuance call, the wrapper:

1. acquires an active target lease and increments the in-flight count;
2. opens the fixed control route and proves the live witness and epoch;
3. observes exact governed `now_us` under the gate;
4. computes `expires_at_us = now_us + 300_000_000` without overflow;
5. calls the exact merged issuer once with that `now_us`;
6. after a normal return, reopens or reuses a fixed connection and re-proves
   the same live witness and epoch;
7. under the gate, records the greatest successful expiry and decrements the
   in-flight count; and
8. only then releases the canonical receipt bytes to its caller.

If KMS signs but the postcheck, expiry registration, cleanup, or lease release
fails, the signed bytes are discarded and never returned. A failed issuance
does not add an expiry. No retry occurs.

This ordering makes the greatest registered expiry an upper bound over every
receipt that successfully escaped the governed wrapper. It is not an unrelated
wall-clock estimate.

### 9.3 Direct-issuer prohibition

Future trusted composition may construct the exact merged issuer only after
the separate observer-root and approver-manifest prerequisites are satisfied.
It must hand that exact instance directly to the private target-epoch wrapper.

No production code may retain an alternate issuer reference, call `issue`
directly, inject a different clock, or expose the issuer through a public
service. Tests prove the architecture checker detects each bypass.

This decision does not construct the observer root, KMS client, key resource,
or approver manifest and does not call KMS in Phase A or its own activation.

## 10. State machine and replacement ordering

### 10.1 Installed-process states

The module has one closed state machine:

```text
UNINSTALLED
  -> ACTIVATING
  -> ACTIVE
  -> QUIESCING
  -> RETIRED

ACTIVATING | ACTIVE | QUIESCING
  -> QUARANTINED

ACTIVATING
  -> OUTCOME_UNKNOWN
```

Only ACTIVE grants private leases or begins issuance. RETIRED, QUARANTINED,
and OUTCOME_UNKNOWN are terminal for that process. There is no reset, fallback,
second installation, target swap, or automatic retry.

### 10.2 Activation sequence

Activation performs exactly:

1. local capsule and nonce validation before PostgreSQL I/O;
2. fixed control-route witness connection and both nonblocking locks;
3. live target identity comparison with the capsule;
4. module authority-time observation at or beyond predecessor not-after;
5. a separate control transaction that locally observes the witness before
   its first epoch or clock effect;
6. one activation-function call;
7. exact returned-row validation;
8. synchronous commit acknowledgement while the witness remains held; and
9. one fresh fixed-route connection-local witness and epoch observation.

Only then does state become ACTIVE. Early not-before refusal performs no epoch
insert and never sleeps. A later deployment invocation may try after the
barrier; production code contains no polling or wait loop.

### 10.3 Governed operation lease

`_hold_security_audit_target_epoch` increments one in-flight counter only in
ACTIVE. QUIESCING begins by changing state under the same lock, so no later
lease or issuance can start.

The context holds its count until every database commit acknowledgement,
future credential effect, export effect, and cleanup owned by the caller is
finished. The lease itself performs live pre- and post-assertions. A lost or
mismatched witness quarantines the process and no private success escapes.

PR #325 must hold this context from before its control connection opens through
its synchronous consumption commit. A later credential lifecycle must keep
the same context open through credential creation, use, revocation,
termination, drop, and structural closure as its own decision specifies. This
RFC grants none of those effects.

### 10.4 Orderly quiescence

Orderly quiescence has two nonblocking private calls. The begin call:

1. changes ACTIVE to QUIESCING under the gate;
2. blocks all new issuance and target leases; and
3. returns without waiting, sleeping, polling, closing the witness, observing
   cutoff, or producing a retirement report.

Already counted work finishes normally and decrements the count. The finish
call:

4. is valid only in QUIESCING;
5. refuses immediately and leaves the state QUIESCING if the count is not
   zero;
6. observes cutoff from the exact governed authority-time source only after it
   observes a zero count under the same lock;
7. computes not-after as the greater of cutoff plus 300,000,000 and the
   greatest registered successful receipt expiry;
8. requires the values to be equal under the issuance ordering proof;
9. performs one final live witness and epoch observation;
10. closes the witness session and proves cleanup completed; and
11. enters RETIRED before returning one canonical private retirement report.

Trusted composition coordinates worker shutdown and may invoke finish again in
a later control call after an earlier nonzero-count refusal. That is a bounded
state observation, not an effect retry. The module contains no deadline,
condition wait, background thread, sleep, or polling loop.

The retirement report contains only schema identity, epoch ID, capsule digest,
cutoff, greatest successful expiry, and not-after. It contains no nonce, DSN,
witness address, receipt, approval, credential, or target network detail. It is
not public authority and has no decoder in an operation path.

An external deployment authority may use the exact report to construct the
replacement capsule through its separately protected workflow.

### 10.5 Abrupt loss

When no orderly report can exist, replacement is allowed only after the
external deployment authority:

1. declares the predecessor target unavailable;
2. proves every process holding the predecessor capsule or nonce is terminated
   and cannot issue or perform another governed operation;
3. only then observes cutoff in the same certified UTC microsecond domain used
   by governed issuance;
4. sets not-after to cutoff plus exactly 300,000,000 microseconds;
5. completes the merged store-loss recovery on an unpublished fresh target;
6. binds the exact recovery report digest and predecessor/new epoch IDs into
   the replacement capsule; and
7. keeps every replacement route, credential, and activation input
   quarantined until both clocks and epoch activation pass.

Because termination precedes cutoff and the certified clock does not regress,
every successfully released predecessor receipt has issuance time at or below
cutoff and expiry at or below not-after. Approval requests cannot outlive their
authority receipt under the merged verifier.

If termination or clock currentness cannot be proved, there is no safe cutoff;
replacement activation remains forbidden. Recovery success alone is
insufficient.

### 10.6 Replacement activation

The replacement module refuses until:

- its own governed authority-time observation is at least not-after;
- the new control connection sees the exact recovery target and witness;
- the database nonregressing access clock observes a nonregressed high-water at
  least not-after; and
- the immutable replacement epoch row commits and is reobserved.

Only after ACTIVE may the external deployment authority attach future
break-glass composition. Route publication itself remains external and
unauthorized here.

The replacement store may later admit a newly signed bundle whose operation ID
happens to equal an operation ID from the lost store. The signed schema does not
carry an epoch and this decision does not claim global operation-ID uniqueness.
Safety comes from predecessor expiry and fresh signatures, not from an
unenforceable requirement to choose a never-before-used UUID. PR #325 must
remove its provisional “new operation ID after recovery” policy sentence or
state only the store-local claim.

## 11. Failure and data hygiene

- Every public error is empty and fixed.
- No exception message, traceback, `repr`, log, metric, telemetry event,
  stdout, stderr, file, queue, or report may contain capsule bytes, nonce,
  nonce digest, DSN, password, host, witness address, backend PID, system
  identifier, raw database error, receipt, approval, credential, or output.
- Ordinary activation, clock, database, issuer, commit, close, and cleanup
  failures map to one fixed negative type based only on the state transition.
- `KeyboardInterrupt`, `SystemExit`, and other `BaseException` values are not
  converted to success; cleanup runs and the value propagates where Python
  semantics permit.
- The raw nonce is never inserted, serialized, returned, or logged.
- The capsule and retirement report are protected control carriers, not public
  API documents.
- A witness or lease loss never triggers target discovery, failover, retry,
  reactivation, or a fallback clock.
- Ambiguous activation commit is terminal `OUTCOME_UNKNOWN`; ambiguous future
  consumption and credential effects remain owned by their decisions.

## 12. Invariants

- `ATE-001` — Phase A changes only this RFC and authorizes no implementation.
- `ATE-002` — exactly one external deployment authority selects and attaches
  current activation material; no database object claims to replace it.
- `ATE-003` — no operation caller supplies target, capsule, nonce, epoch,
  route, connection, clock, witness, or lease.
- `ATE-004` — an epoch row is immutable, singleton, and non-authorizing alone.
- `ATE-005` — raw activation nonce never enters the audit database or output.
- `ATE-006` — ACTIVE requires both nonce possession and two live witness locks
  on the capsule-pinned target.
- `ATE-007` — every governed effect connection proves the same live witness
  and epoch before its first authority observation or effect.
- `ATE-008` — a promoted physical clone with equal stored identity and epoch
  fails the original witness assertion.
- `ATE-009` — witness loss is terminal for the installed process.
- `ATE-010` — only the target-epoch wrapper supplies receipt issuer `now_us`.
- `ATE-011` — successful receipt expiry is registered before receipt bytes
  escape the wrapper.
- `ATE-012` — quiescence begin blocks new work; quiescence finish observes
  cutoff only after the counted-work total is zero.
- `ATE-013` — orderly cutoff upper-bounds every successfully released receipt
  issuance time from that composition.
- `ATE-014` — abrupt-loss cutoff occurs only after every predecessor
  composition is proven terminated.
- `ATE-015` — replacement not-after is exactly cutoff plus 300,000,000
  microseconds and no less than every known successful expiry.
- `ATE-016` — replacement activation requires both authority time and durable
  database clock floor at or beyond not-after.
- `ATE-017` — no predecessor receipt or request can become current on the
  replacement store.
- `ATE-018` — ACTIVE follows acknowledged synchronous epoch-row commit and
  fresh reobservation only.
- `ATE-019` — activation ambiguity returns no authority and is never retried in
  the same invocation.
- `ATE-020` — PR #325 receives only the private held lease and fixed control
  connection, never activation inputs or a positive public value.
- `ATE-021` — future credential effect must remain inside the same held lease;
  this decision performs no credential effect.
- `ATE-022` — operation IDs are not falsely claimed globally unique across
  lost stores.
- `ATE-023` — no cloud or KMS client is constructed and no signing policy,
  observer-root, approval, credential, export, output, failover, IAM, or
  deployment mutation occurs; the only prospective delegated signing effect is
  the merged issuer's existing one-call behavior under the governed wrapper.
- `ATE-024` — every failure and output is fixed and contains no protected
  target or activation detail.

## 13. Required Phase B evidence

### 13.1 Unit evidence

Focused tests must prove:

1. `__all__` contains only the four negative errors;
2. no public positive class, target, route, lease, epoch, clock, capsule,
   nonce, function, loader, decoder, Protocol, factory, or result exists;
3. malformed capsule or nonce refuses before connection or time work;
4. every exact initial/replacement cross-field and integer boundary is closed;
5. production constructs real time and connection dependencies directly and
   never calls the private test helper;
6. nonce-derived lock addresses are deterministic, domain-separated, and use
   both PostgreSQL namespaces;
7. either lock refusal closes the witness before activation;
8. system, database, version, role, transaction, recovery, and structural
   drift refuse;
9. ACTIVE is unreachable before acknowledged commit and fresh reobservation;
10. every activation commit exception is terminal outcome unknown and is not
    retried;
11. no lease begins outside ACTIVE and every context decrements exactly once;
12. quiescence begin wins the race against every later issuance and lease
    start;
13. in-flight issuance, admission, and cleanup delay retirement rather than
    escaping the count;
14. only exact `time.time_ns() // 1000` values reach issuer `now_us`;
15. time regression quarantines without receipt release;
16. a KMS-normal receipt is withheld until post-witness recheck and expiry
    registration;
17. failed or postcheck-refused signing returns no bytes and adds no expiry;
18. finish observes cutoff only after the count reaches zero, while an early
    finish refuses immediately without changing the cutoff;
19. replacement not-after equals the exact five-minute bound and greatest
    registered expiry;
20. early replacement activation refuses without sleep, retry, or epoch row;
21. lease and witness cleanup failure cannot become retirement or success;
22. no secret or canary reaches errors, reports, logs, or output; and
23. architecture, import, path, and line budgets are exact.

### 13.2 Live PostgreSQL evidence

Against isolated PostgreSQL 17 services, Phase B must prove:

1. migration 4 applies after exact migrations 1 through 3;
2. direct relation access and wrong-role function calls refuse;
3. exact initial activation inserts one immutable row and routine exact
   restart observes it without mutation;
4. different epoch, capsule, nonce digest, predecessor, cutoff, recovery
   digest, system, database, or server identity cannot replace that row;
5. database clock below not-after prevents insertion;
6. activation at the exact microsecond boundary succeeds and persists the
   nonregressing high-water;
7. two activation processes on one server using the same nonce contend for the
   same locks and at most one holds the live witness;
8. every operation connection observes the retained witness and exact row;
9. losing the witness session makes the next assertion fail before effect;
10. split each activation and operation connection independently between A and
    independently initialized B and prove no wrong-server effect;
11. repeat the split matrix with promoted physical clone B sharing system
    identifier, schema, and copied epoch row; B cannot see A's live locks;
12. commit ambiguity exposes no ACTIVE state;
13. migration, function, relation, constraint, ACL, observer, catalog, and
    ledger drift make structural verification fail; and
14. store-loss recovery on migration 4 proves the epoch relation remains empty
    through its exact success report and still publishes no replacement route.

The physical-clone test does not claim that copied activation nonce attachment
is safe. It proves route drift from the one trusted composition fails. A test
that deliberately supplies the protected nonce to two clone-local trusted
compositions demonstrates the documented external-authority limit and must not
be reported as PostgreSQL election success.

### 13.3 Cross-slice evidence

Before PR #325 can enter Phase B, its amended exact head must prove:

- it imports the merged private lease interface and no activation operation;
- it accepts no target or connection input;
- the lease remains held through synchronous consumption commit;
- its database time floor is the target-epoch-established nonregressing floor;
- migration 5 preserves the immutable epoch row and structural contract; and
- every clone, witness-loss, quiescing, retired, and replacement-before-floor
  case reaches no private committed state.

Before any production receipt composition, a separate exact decision must
prove that all issuer calls go through this wrapper and that the observer
public key comes from the approved observer-root composition. Before any
credential composition, its decision must prove the effect connection is
admitted by the same held lease.

### 13.4 Repository evidence

Phase B must pass:

- focused target-epoch and live PostgreSQL tests;
- affected migration, structural, store-loss, authority-receipt, and
  architecture suites;
- package-contract and rewrite-architecture conformance;
- both complete review baselines with clean-run equivalence;
- native verifier amd64 and arm64 jobs;
- canonical multi-platform index assembly;
- exact base-to-head path audit; and
- `git diff --check`.

## 14. Prospective Phase B repository boundary

Only the exact later decision approval may authorize edits to these fourteen
paths:

1. `docs/rfcs/OFARM_Security_Audit_Admission_Target_Epoch_RFC_v0_1.md`
2. `security_audit/migrations/0004_admission_target_epoch.sql`
3. `deployment/postgresql/migration_sets.py`
4. `deployment/postgresql/audit_contract.py`
5. `deployment/postgresql/security_audit_target_epoch.py`
6. `deployment/postgresql/security_audit_store_loss.py`
7. `deployment/postgresql/README.md`
8. `kernel/tests/test_security_audit_target_epoch.py`
9. `kernel/tests/test_postgresql_audit_migration.py`
10. `kernel/tests/test_postgresql_structural_compatibility.py`
11. `kernel/tests/test_postgresql_audit_reason_vocabulary.py`
12. `kernel/tests/test_security_audit_store_loss.py`
13. `conformance/rewrite_architecture_check.py`
14. `conformance/review_baseline_test_inventory.json`

Paths 2 through 4 and 9 through 11 are the mechanical forward migration and
complete structural binding. Paths 6 and 12 add only the new relation's exact
zero-row fresh/recovered assertion. They may not change store-loss state,
effects, report, witness, gap, ambiguity, or output behavior.

No runtime bootstrap, receipt issuer, observer-root, PR #325, credential,
export, application, provider, workflow, deployment, or infrastructure path is
in this PR. Unneeded allowlisted paths remain unchanged. Phase B stops before
touching a fifteenth path.

## 15. Budgets and architecture controls

- new production target-epoch module: at most 850 physical lines;
- every production function: at most 80 physical lines;
- new focused target-epoch test module: at most 1,600 physical lines;
- migration 4: at most 650 physical lines;
- store-loss production delta: at most 24 physical lines and only the epoch
  zero-row observation/validation;
- no dependency, lockfile, workflow, Dockerfile, command, service, endpoint,
  scheduler, test glob, shared test-line limit, or group budget change;
- the production-module architecture budget must equal its exact finished
  physical line count and remain at or below the ceiling;
- direct repository imports limited to the exact merged audit contract,
  authority-receipt issuer, migration/structural constants, and no other
  security-audit operation module;
- standard-library imports limited to contextlib, dataclasses, enum, hashlib,
  json, re, threading, time, typing, and uuid;
- third-party imports limited to psycopg and its already pinned submodules;
- no environment, file, network, cloud, KMS-client, IAM, subprocess, stdout,
  logging, telemetry, queue, or retry import/effect in the target-epoch module;
- no public positive surface or production dependency argument; and
- no source outside the exact later approved bootstrap, PR #325 admission, and
  credential-composition allowlists may import the module-private operations.

The architecture checker must prohibit direct production calls to
`SecurityAuditAuthorityReceiptIssuer.issue` outside the target-epoch wrapper,
operation access to activation inputs, arbitrary connection factories, clock
injection, route discovery, sleeps, retries, fallback targets, mutable epoch
rows, public lease construction, and protected-value output.

## 16. Review classification

An in-scope Blocker demonstrates that:

- the RFC or implementation claims a database row, system identifier,
  advisory lock, or nonce digest is a global election;
- an operation caller can select, replace, or fabricate target authority;
- copied-store routing can pass without seeing the original live witness;
- ACTIVE can precede committed and reobserved epoch state;
- an epoch row can be updated, deleted, reset, or replaced;
- raw nonce or protected target detail reaches storage or output;
- receipt issuance can bypass the governed time/witness wrapper;
- receipt bytes can escape before successful-expiry registration;
- quiescence can observe cutoff before blocking and draining earlier work;
- abrupt-loss cutoff can precede predecessor-process termination;
- cutoff is drawn from a clock domain not proven to upper-bound issuer time;
- replacement can activate before the exact maximum expiry or without a
  durable database floor;
- old approvals can become current on an empty replacement;
- PR #325 can receive activation inputs or a caller-supplied lease;
- future credential effect can outlive or bypass the same lease;
- the new migration changes an earlier migration or weakens structural or
  store-loss proof;
- a failure, ambiguous commit, witness loss, or clock regression can return
  success or retry; or
- implementation crosses into deployment mutation, observer-root, signing-key,
  approval, credential, export, output, failover, or another trust boundary.

Preferences for a provider lease, distributed consensus system, signed epoch
inside approval schemas, automatic wait service, general failover controller,
backup, or global operation-ID ledger are follow-ups unless they demonstrate
one stated invariant cannot hold under the explicit threat model.

## 17. Dependencies and ordered follow-ups

### 17.1 Satisfied dependencies

- PR #319 merged the exact dual-approval verifier.
- PR #320 merged the authority-receipt issuer with an exact five-minute
  lifetime and caller-owned trusted `now_us`.
- PR #321 merged observer-root admission but not its production runtime
  composition.
- PR #324 merged exact fresh-store recovery and its invocation-local live
  witness.
- Current `main` contains no production receipt composition, credential
  lifecycle, or deployment activation that this decision must preserve.

### 17.2 Conditional dependent decision

PR #325 is a conditional Phase A draft. Its current version 2 has zero
demonstrated in-scope blockers only because it grants no Phase B and names this
decision as mandatory. It must remain draft and unimplemented until the ordered
pinning amendment in section 1.4 passes exact-head review.

### 17.3 Ordered follow-ups

After this decision:

1. approve and implement this exact target-epoch boundary;
2. amend PR #325 to migration 5 and pin the merged private lease;
3. complete the separate observer-root signer-credential and runtime
   composition that constructs the exact issuer and verifier and routes every
   issuer call through this gate;
4. implement PR #325 only after its amended live card is approved;
5. define the temporary export-login lifecycle inside the same held lease;
6. define protected output delivery only after verified credential closure;
7. add independently witnessed surviving-store process-crash intervals;
8. run final real-ASGI/PostgreSQL hostile cross-slice evidence; and
9. perform the final issue #192 closure audit.

The observer-root provider-evidence PRs #322 and #323 remain separate. This
decision creates no dependency on a cloud fixture or provider call.

## 18. Stop and reapproval conditions

Stop and require a new decision version before implementation or merge if work
would:

- replace the explicit external deployment authority with an unreviewed
  assumption or claim local global election;
- add a provider, cloud lease, distributed coordinator, tenant-database lock,
  DNS mutation, or routing controller;
- change activation capsule fields, nonce size or derivation, witness SQL,
  database row, function, state machine, time source, cutoff, or floor rule;
- accept a per-operation target, config, connection, lease, time, issuer, or
  dependency;
- change the receipt or approval schemas, signatures, lifetime, approver rule,
  or observer-root contract;
- implement observer-root composition, KMS construction, credential effects,
  export, output, or deployment operation;
- change an earlier migration or more than the exact mechanical store-loss
  zero-row assertion;
- add a second epoch row, mutation, reset, repair, fallback, retry, polling, or
  automatic wait path;
- add a public positive surface or serialize a lease/witness;
- exceed the exact path or budget boundary;
- authorize Phase B without the complete live card; or
- claim production readiness or close issue #192.

Meaning-preserving RFC wording, fixed diagnostic wording, test clarity,
mechanical exact-budget registration, and inventory regeneration within the
allowlist do not require a new version.

## 19. Phase A publication and decision card

Publishing this RFC to its own draft pull request is Phase A only. A generic
`go`, checks, reviews, branch state, or repository credentials do not authorize
Phase B.

Before a live decision card may be displayed:

1. this RFC must be the only changed path;
2. exact-head hosted checks must pass;
3. two independent exact-head Phase A reviews must each report zero
   demonstrated in-scope Blockers;
4. every current-head review correction must be reflected in the RFC; and
5. the complete card must name the exact head, reviewed base, path boundary,
   capsule/nonce contract, migration 4, live witness, issuance cutoff,
   replacement floor, private interface, evidence, budgets, exclusions, and
   stop conditions.

Only after all five gates may the live card display this exact approval form:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-ADMISSION-TARGET-EPOCH-001 version 1.
```

That exact entire later task-user message after the complete live card would
authorize only the prospective Phase B repository paths. It would not
authorize deployment authority creation, activation-material provisioning,
provider or IAM action, production operation, PR #325 implementation,
observer-root composition, credentials, export, output, merge, or issue
closure.

## 20. Provisional design record

- Reviewed base: 5f51f80981599a0da4678d555a02a648b84a2304.
- Primary trust boundary: target selection, live epoch lease, quiescence, and
  replacement activation for security-audit break-glass authority.
- PR boundary: one Phase A RFC now; the exact fourteen-path maximum for a
  later approved Phase B; no cross-boundary exception.
- Cross-process singleton: external deployment authority, explicitly not
  PostgreSQL election.
- Store-local identity: immutable migration-4 epoch row.
- Clone-drift proof: separate protected nonce plus retained live witness on
  every governed connection.
- Issuance cutoff: same target-epoch time gate that supplies issuer `now_us`,
  after new work is blocked and in-flight work drains.
- Replacement barrier: cutoff plus exactly 300,000,000 microseconds, no less
  than every successfully released receipt expiry.
- Replacement floor: both governed authority time and durable database
  high-water at or beyond the barrier.
- PR #325: unchanged, conditional, draft, and not card-eligible.
- Observer-root runtime construction: separate unsatisfied prerequisite.
- Phase B, deployment, provider, IAM, direct KMS-client construction or real
  provider operation, credential, export, output, merge, and issue-closure
  authority: absent.
- Issue #192 remains open.
