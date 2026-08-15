# OFARM Security-Audit HMAC Retirement Execution — Phase A Contract v0.1

**Status:** proposed and unapproved; Phase B, deployment, and every Cloud KMS
mutation remain unauthorized

**Draft pull request:** this RFC will name the stable draft pull request after
GitHub assigns it

**Contract identity:**
`ofarm2.security-audit-hmac-retirement-execution.v0.1`

**Proposed decision identity:**
`ISSUE192-SECURITY-AUDIT-HMAC-RETIREMENT-EXECUTION-001`, version `1`

**Issue:** #192

**Reviewed base:** `b876736360313736d8da01802521ac2d9e2a37f0`

**Primary trust boundary:** deployment-owned scheduling of irreversible Cloud
KMS destruction for the one retired pre-tenant correlation-HMAC key version

**Phase A review-head boundary:** this RFC only

**Maximum final pull request boundary:** this RFC; one bounded deployment-layer
retirement runner; one fixed command adapter; focused tests; minimal operator
documentation; architecture-budget registration; and the mechanically
regenerated review-baseline test inventory only

## 1. Problem and goal

The accepted security-audit architecture has moved fresh correlation-HMAC
generation from key version `1` to version `2`. PostgreSQL now accepts version
`1` only when an exact event identity already committed under that version is
retried. The existing lifecycle observer reconciles the two migration-known
versions with Cloud KMS and returns each inactive version's greatest currently
retained `purge_after`, but it is deliberately read-only.

There is no supported repository operation that schedules the retired version
for destruction. A deployed version `1` can therefore remain `ENABLED` or
`DISABLED` indefinitely even after PostgreSQL stopped admitting fresh version
`1` events. Observation alone does not enforce the accepted rule that retired
correlation material reaches Cloud KMS logical destruction no later than the
greatest live retention deadline that names it.

This decision establishes one one-shot deployment operation for the exact
current rotation only:

```text
known versions = (1, 2)
active version = 2
retirement target = 1
Cloud KMS destroy-scheduled duration = 86,400 seconds
minimum live-deadline lead before a new destroy request = 172,800 seconds
```

The operation:

1. accepts no caller-selected version, deadline, state, duration, or action;
2. reuses the existing read-only database/KMS lifecycle observer to require
   exact version-set and active-version posture;
3. validates the exact configured Cloud KMS parent, MAC purpose, HSM
   HMAC-SHA-256 version template, and 86,400-second immutable destruction
   delay;
4. obtains a fresh database clock observation through the existing audit-control
   route;
5. schedules only version `1` by calling
   `DestroyCryptoKeyVersion` once with `retry=None` and a bounded timeout;
6. validates a successful response as the exact target in
   `DESTROY_SCHEDULED`, with a finite `destroy_time` no later than an observed
   live database deadline;
7. treats a pre-existing conforming `DESTROY_SCHEDULED` or `DESTROYED` target as
   a successful bounded observation without another mutation;
8. never disables, enables, restores, creates, deletes, rotates, imports,
   reimports, signs with, or changes IAM for any key; and
9. emits one non-sensitive canonical result only after the resulting target
   state is known.

Cloud KMS, not this process, performs the future automatic transition from
`DESTROY_SCHEDULED` to `DESTROYED` at `destroy_time`. This contract uses
"destruction" to mean Cloud KMS logical key-version destruction. It does not
claim immediate physical removal from every Google active system, backup, or
retired medium.

The operation is a technical primitive and point-in-time deployment gate. It is
not a scheduler, rotation controller, IAM provisioner, continuous monitor, or
authorization to invoke Cloud KMS in a deployed environment.

## 2. Learning value

The slice proves that the accepted database retention deadline can govern one
irreversible Cloud KMS transition without allowing an operator to select the
target version, supply a deadline, widen KMS authority, or mutate the active
version.

It reduces two demonstrated risks:

- retired correlation material remaining usable indefinitely because the
  read-only lifecycle posture has no mutation owner; and
- an executor bug, hostile configuration, or ambiguous RPC outcome being
  reported as successful destruction scheduling without exact resource,
  state, time, and active-version validation.

It also validates whether the current rotation can be operated through a
single fixed `destroy` transition. If a real deployment requires disable-first
organization policy, restore authority, a different destruction duration, or
historical deadline receipts, that evidence requires a separate decision
rather than widening this executor.

## 3. Non-goals

This pull request does not change or add:

- security-audit migrations, functions, types, relations, indexes, roles,
  grants, provisioning specifications, or database policy;
- correlation-HMAC key creation, version creation, rotation, active-version
  selection, primary-version selection, MAC framing, preimage generation, or
  `MacSign` execution;
- a call to `UpdateCryptoKeyVersion`, `RestoreCryptoKeyVersion`,
  `CreateCryptoKeyVersion`, `DeleteCryptoKeyVersion`, `ImportCryptoKeyVersion`,
  or any IAM API;
- support for an organization policy that requires disabling a version before
  destruction;
- a general key-retirement framework, caller-selected version, future version
  `3`, multiple retirement targets, configurable duration, or compatibility
  alias;
- a scheduler, daemon, service, background thread, loop, timer, queue, spool,
  cache, local receipt file, dead letter, or generic telemetry surface;
- production runtime composition, `RuntimeConfig`, application startup,
  `/health`, `/ready`, dynamic audit health, traffic withdrawal, or deployment
  topology;
- `AUDIT_GAP`, overflow, retention invocation, query, export, break-glass,
  temporary-login, store-loss, empty-recreate, backup, replica, CDC, or recovery
  operations;
- tenant, Party, principal, authorization, capability, signing-key, governed
  batch, RuntimeBundle, issue #172, or issue #176 authority;
- mutation or verification of Cloud IAM policy, service-account identity,
  Workload Identity, organization policy, Cloud Audit Logs, or deployment
  credentials;
- a guarantee that a later authorized administrator cannot restore the version
  or change the key after this point-in-time operation;
- physical-erasure timing across provider backups or media;
- deployment activation, release, production access, production operation,
  current/default promotion, production readiness, issue #192 closure, or a
  security waiver; or
- a claim that a null current database deadline proves version `1` never had a
  retained event or met every historical deadline.

The command deliberately does not disable version `1` first. Cloud KMS permits
an `ENABLED` or `DISABLED` version to enter `DESTROY_SCHEDULED` directly, and
that single transition requires only
`cloudkms.cryptoKeyVersions.destroy`. A deployment whose organization policy
requires disable-before-destroy is incompatible with this contract. Adding
`cloudkms.cryptoKeyVersions.update` and a second mutation state machine is not
a review fix for this pull request.

## 4. Trust model

### 4.1 Protected assets

- the active version `2` key material and its availability for governed
  correlation-HMAC generation;
- retired version `1` key material and its accepted destruction deadline;
- exact binding between the PostgreSQL-known version, configured Cloud KMS
  parent, and mutated Cloud KMS resource;
- the immutable 86,400-second Cloud KMS destruction delay;
- honest classification of no-mutation, known-scheduled, known-destroyed,
  refused, unavailable, outcome-unknown, and reporting-failed states;
- the audit-control DSN and deployment-owned Cloud KMS credential;
- absence of raw correlation values, HMAC bytes, credentials, DSNs, project or
  key names, exception text, tenant data, and request data from reports and
  diagnostics; and
- one-operation CPU, memory, connection, RPC, and output bounds.

### 4.2 Trusted components

- the accepted issue #174 security-audit migrations, roles, grants,
  constraints, and immutable migration ledger;
- `ofarm_security.observe_correlation_hmac_key_retention(integer)` and its
  exact `ofarm_security_audit_control_login` session-user check;
- PostgreSQL transaction semantics and database clock;
- the checked-in security-audit contract with known versions `(1, 2)` and
  active version `2`;
- the existing `CorrelationHmacLifecycleObserver`, including its exact KMS
  version-set, algorithm, protection-level, and active-state validation;
- the configured Google Cloud KMS service, resource identity, state machine,
  `destroy_scheduled_duration`, `destroy_time`, and `destroy_event_time`;
- Google Cloud KMS logical transition semantics for an HSM-backed MAC key;
- Psycopg 3.3.4, google-cloud-kms 3.16.0, the operating system, and Python
  runtime;
- the deployment-layer runner and fixed command adapter; and
- deployment-controlled endpoint routing, DNS, TLS, service files, secret
  injection, Application Default Credentials, and stdout destination.

The database clock and Cloud KMS clock are trusted not to differ by the entire
86,400-second safety margin. A deployment unable to establish that prerequisite
must not run the operation. The returned Cloud KMS `destroy_time`, rather than
the local process clock, is the final scheduling-time evidence.

### 4.3 Untrusted actors and inputs

- every command-line token;
- missing, malformed, whitespace-only, multi-host, service-file, option-bearing,
  or hostile conninfo;
- a wrong database role or cross-service database route;
- missing, malformed, or hostile configured KMS parent text;
- ambient credentials that lack the required permissions;
- network availability, latency, RPC acknowledgement, and connection closure;
- every database row, KMS page, KMS resource, timestamp, duration, enum, and
  response value until validated;
- invocation timing, frequency, duplicate invocation, and a concurrent
  invocation of the same fixed command;
- stdout and stderr availability, short writes, and flush failures; and
- an authorized audit producer limited to its existing ingest and `MacSign`
  permissions.

The deployment retirement principal is privileged. Cloud KMS IAM applies
version-destruction permission at the parent key or a higher resource rather
than at an individual version. Code confinement therefore prevents accidental
target selection, but it cannot contain a principal that deliberately bypasses
the command and calls Cloud KMS directly. That principal and its credential
must be independently controlled before deployment.

### 4.4 Explicitly excluded attacker capabilities

The following are out of scope:

- arbitrary in-process mutation or code execution;
- local source substitution or filesystem mutation;
- compromised Python, Psycopg, google-cloud-kms, gRPC, TLS, operating-system,
  PostgreSQL, or Google Cloud dependencies;
- database-owner, migrator, superuser, Cloud KMS administrator, organization
  policy administrator, or deployment-host compromise;
- direct misuse of a valid retirement credential outside this command;
- KMS service compromise, forged provider time, or a full-day database/KMS
  clock disagreement;
- an independently authorized restore, update, import, reimport, delete, key
  creation, or IAM change racing the command; and
- simultaneous corruption of both PostgreSQL and Cloud KMS authorities.

Ordinary configuration mistakes, wrong credentials, wrong resource routes,
unsupported KMS state, response substitution at the supported client seam,
RPC failure, duplicate invocation, and output failure remain in scope.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Known correlation-HMAC versions | Checked-in security-audit contract; must equal `(1, 2)` |
| Active version | Checked-in contract plus database observer; must equal `2` |
| Retirement target | This reviewed decision; fixed to version `1` |
| Greatest currently retained version-1 deadline | `observe_correlation_hmac_key_retention(1)` |
| Fresh operation time | PostgreSQL `clock_timestamp()` over the exact audit-control route |
| Configured KMS parent | `OFARM_CORRELATION_HMAC_KMS_KEY_RESOURCE`, validated as one exact parent |
| Parent key purpose and immutable destruction delay | Exact `GetCryptoKey` result |
| KMS version membership | Existing bounded `ListCryptoKeyVersions` observation |
| Version algorithm and protection | Exact `GetCryptoKeyVersion` results |
| Current target state | Last exact version-1 `GetCryptoKeyVersion` result before a possible mutation |
| Permission to request destruction | External deployment IAM; `cloudkms.cryptoKeyVersions.destroy` only for mutation |
| New scheduling transition | One `DestroyCryptoKeyVersion` call naming the fixed version-1 resource |
| Scheduled logical-destruction time | Cloud KMS response `destroy_time` |
| Completed logical-destruction time | Cloud KMS observation `destroy_event_time` |
| Live-deadline admission | Fixed 172,800-second minimum lead against database time |
| Automatic scheduled-to-destroyed transition | Cloud KMS |
| Transaction and call bounds | Runner-owned fixed connection/RPC options |
| Successful process report | Fixed canonical ASCII JSON protocol |
| Report delivery | Complete binary stdout write and flush |

There is no fallback version, caller deadline, local deadline cache, output
receipt used as authority, generic KMS action, or alternate mutation path.

Application Default Credentials select the Cloud principal outside the process.
The command cannot prove that principal's complete IAM permission set. Before
deployment, an independent authority must provision and verify a dedicated
principal with only:

- `cloudkms.cryptoKeys.get`;
- `cloudkms.cryptoKeyVersions.get`;
- `cloudkms.cryptoKeyVersions.list`; and
- `cloudkms.cryptoKeyVersions.destroy`

on the exact configured CryptoKey, with no `macSign`, restore, update, create,
delete, import, reimport, or IAM-management permission. The production audit
runtime identity must not receive `destroy`.

The existing audit-control database login has broader accepted control
functions than this operation needs. This command invokes only the existing
read-only lifecycle observation and database clock. It gains no KMS signing
permission and no database table privilege. Creating another database role or
grant is a separate database-authority change and is not hidden in this key-
custody pull request.

## 6. State machine and ordering

### 6.1 Static input admission

The fixed command accepts no positional or option arguments. Before opening a
database connection or creating a KMS client, it requires:

- exactly zero command-line tokens;
- one non-empty syntactically valid
  `OFARM_SECURITY_AUDIT_CONTROL_PG_DSN`; and
- one exact `OFARM_CORRELATION_HMAC_KMS_KEY_RESOURCE` parent matching the
  accepted resource grammar.

The caller cannot provide a version, action, state, deadline, duration, timeout,
retry count, report field, or output path.

Code-supplied connection and RPC options override or exclude caller values:

```text
PostgreSQL connect timeout = 5 seconds
PostgreSQL statement timeout = 2 seconds
PostgreSQL transaction = non-autocommit, repeatable read, read only
KMS RPC timeout = 5 seconds per call
KMS retry = None for every call
KMS list page size = known version count + 1
```

DSN endpoint expansion, TLS, service files, DNS, and multi-host selection remain
deployment-route concerns. They are not inferred as trusted from conninfo
syntax alone.

### 6.2 Read-only prerequisite observation

The runner first invokes the existing lifecycle observer. It must establish:

```text
contract known versions == (1, 2)
database active versions == (2,)
KMS numeric version set == {1, 2}
version 2 state == ENABLED
versions 1 and 2 algorithm == HMAC_SHA256
versions 1 and 2 protection level == HSM
```

The existing observer closes its database transaction before KMS RPCs. Any
missing, duplicate, extra, paginated, malformed, unknown-state, wrong-resource,
wrong-algorithm, wrong-protection, or active-version conflict refuses before a
mutation method is reachable.

The runner then calls `GetCryptoKey` for the exact configured parent and
requires:

```text
name == configured parent
purpose == MAC
version_template.algorithm == HMAC_SHA256
version_template.protection_level == HSM
destroy_scheduled_duration == 86,400 seconds
import_only == false
```

It obtains one new exact version-1 observation immediately before deciding the
state path. It validates the same resource, algorithm, and protection
requirements, requires `reimport_eligible == false` with no import job or
import time, and validates the state-specific time fields below. A destroyed
imported version that could be reconstituted from externally retained key
material is not an accepted retirement result.

Finally, it opens one short read-only audit-control transaction and reads exact
`session_user` plus `clock_timestamp()`. The session user must be
`ofarm_security_audit_control_login`; the timestamp must be finite and
timezone-aware. The previously observed greatest version-1 deadline cannot
increase because fresh version-1 append is migration-forbidden. Retention may
remove a row after observation, but using the earlier greatest deadline remains
conservative for this operation.

No database transaction remains open when the mutation RPC is attempted.

### 6.3 Target states before mutation

Only these version-1 states are admitted:

| Observed state | Required time shape | Transition |
| --- | --- | --- |
| `ENABLED` | no destroy times | new scheduling path |
| `DISABLED` | no destroy times | new scheduling path |
| `DESTROY_SCHEDULED` | finite aware `destroy_time`; no `destroy_event_time` | validate and report; no mutation |
| `DESTROYED` | finite aware `destroy_event_time`; no `destroy_time` | validate and report; no mutation |

Every other state or time shape refuses before mutation.

For a pre-existing scheduled or destroyed state with a non-null database
deadline:

```text
destroy_time <= greatest_purge_after
```

or:

```text
destroy_event_time <= greatest_purge_after
```

must hold. A later time is a terminal observed deadline violation. The command
does not restore, delete, or rewrite the KMS version to hide it.

### 6.4 New scheduling admission

For `ENABLED` or `DISABLED`, a non-null live deadline permits mutation only
when:

```text
database_observed_at + 172,800 seconds <= greatest_purge_after
```

The first 86,400 seconds cover the exact Cloud KMS scheduled-destruction delay.
The second 86,400 seconds are a fixed safety bound for the bounded RPC path and
the trusted cross-service clock prerequisite. This is intentionally much larger
than the five-second RPC timeout.

If the live deadline is closer, equal, expired, infinite, naive, or otherwise
invalid, the command reports a no-mutation deadline refusal. It does not
schedule late and call the result compliant.

A null `greatest_purge_after` means only that the current database observation
found no retained pre-tenant failure naming version `1`. It does not prove that
there was never such a row or that a historical deadline was met. The command
may schedule immediately because there is no currently retained row whose live
deadline must remain bound. Its report preserves the null and makes no
historical-compliance claim.

### 6.5 Mutation transition

After every prerequisite passes, the runner creates exactly:

```text
DestroyCryptoKeyVersionRequest(
    name = configured_parent + "/cryptoKeyVersions/1"
)
```

It calls `destroy_crypto_key_version` once with `retry=None` and a five-second
timeout. There is no disable call, retry, fallback, alternate target, or second
mutation.

The mutation is considered submitted immediately before entering the client
method. From that point until an exact valid response is obtained, any client
exception, timeout, cancellation represented as an ordinary exception,
malformed response, wrong target, unsupported state, missing time, or deadline
conflict is `OUTCOME_UNKNOWN`. The command must not automatically retry or
attempt restoration.

A successful new result must be an exact `CryptoKeyVersion` with:

```text
name == configured_parent + "/cryptoKeyVersions/1"
state == DESTROY_SCHEDULED
algorithm == HMAC_SHA256
protection_level == HSM
reimport_eligible == false
import_job and import_time are absent
destroy_time is finite and timezone-aware
destroy_event_time is absent
```

When a live database deadline exists, the returned `destroy_time` must be no
later than it. A conflicting response is outcome-unknown because the remote
side effect may already have occurred. No report may call it compliant.

### 6.6 Duplicate and concurrent invocation

The command takes no local or database lock across KMS. Two invocations may
both observe version `1` before either mutation. Cloud KMS remains the sole
transition authority:

- one invocation can receive the exact scheduled response and succeed;
- the other can receive a refusal or ambiguous exception and must follow its
  own honest outcome classification; and
- a later invocation that observes an exact conforming `DESTROY_SCHEDULED` or
  `DESTROYED` state performs no mutation and reports that state.

The command does not claim exactly-once RPC delivery. It is convergent only
through the provider-owned terminal states. Exit `4`, exit `5`, or an incomplete
process protocol must never be retried automatically. A later deliberate
invocation starts with the complete read-only prerequisite observation again.

### 6.7 Output and exit protocol

Known success emits one canonical ASCII JSON line to binary stdout:

```json
{"destructionTime":"2030-01-02T03:04:05.000000Z","greatestPurgeAfter":"2030-01-03T03:04:05.000000Z","outcome":"SCHEDULED","schema":"ofarm.security-audit-hmac-retirement-report.v1","targetKeyVersion":1}
```

The three successful outcomes are:

- `SCHEDULED` — this invocation obtained the exact scheduling response;
- `ALREADY_SCHEDULED` — read-only observation found a conforming scheduled
  target; and
- `ALREADY_DESTROYED` — read-only observation found a conforming destroyed
  target.

`destructionTime` carries the provider's scheduled `destroy_time` for scheduled
outcomes and completed `destroy_event_time` for the destroyed outcome.
`greatestPurgeAfter` is either the normalized timestamp or JSON `null`. The
outcome distinguishes scheduled from completed destruction; the common time
field does not collapse those states. The report includes no KMS parent,
project, location, key ring, key name, credential, DSN, exception, HMAC,
correlation, tenant, principal, request, or free text.

Exit and diagnostic bytes are fixed:

| Exit | Meaning |
| --- | --- |
| `0` | one complete known scheduled or destroyed report was flushed |
| `1` | prerequisite or deadline policy refused before mutation |
| `2` | command or static configuration was invalid before dependency use |
| `3` | a dependency was unavailable before the destroy call was submitted |
| `4` | destroy was submitted but its exact outcome is unknown; never retry automatically |
| `5` | a known result existed but complete report delivery failed; never retry automatically |

The adapter catches only the runner's closed exceptions. An unexpected
exception outside that protocol remains an incomplete process outcome; a
catch-all must not invent commit ambiguity or success. Diagnostics are fixed
ASCII bytes, contain no exception text, and go only to binary stderr.

## 7. Invariants and acceptance criteria

### `HRET-001` — exact current rotation only

The operation proceeds only when the checked contract and database identify
known versions `(1, 2)`, active version `2`, and retirement target `1`. No
argument, environment field, returned value, or future contract expansion can
select another target.

### `HRET-002` — active version is immutable

Every KMS mutation request names exact version `1`. Version `2` must be enabled,
HSM-backed HMAC-SHA-256 before the mutation path is reachable. No API capable of
changing version `2` exists in the command protocol.

### `HRET-003` — exact key and destruction policy

The configured parent must be one exact MAC CryptoKey with an HSM
HMAC-SHA-256 version template and an immutable `destroy_scheduled_duration` of
exactly 86,400 seconds. Version `1` must be non-imported and not reimport
eligible. A missing, substituted, imported or imported-only, reconstitutable,
differently purposed, differently protected, or differently timed key refuses
before mutation.

### `HRET-004` — database owns the live deadline

The caller cannot supply or widen a deadline. A non-null deadline comes only
from the existing control-only database function for version `1`; the fresh
operation clock comes only from the exact audit-control PostgreSQL route.

### `HRET-005` — lead-time admission precedes mutation

A target that still has a live deadline can enter a new destroy call only with
at least 172,800 seconds of database-observed lead. A closer or expired deadline
causes a no-mutation refusal.

### `HRET-006` — one irreversible transition

One admitted run submits at most one `DestroyCryptoKeyVersion` request with
`retry=None` and a bounded timeout. It never disables, enables, restores,
creates, deletes, rotates, imports, reimports, signs, or changes IAM.

### `HRET-007` — exact scheduled response

New scheduling succeeds only with the exact target resource in
`DESTROY_SCHEDULED`, correct algorithm and protection level, one finite aware
`destroy_time`, no `destroy_event_time`, no import/reimport posture, and no
deadline conflict.

### `HRET-008` — ambiguity never becomes retry or success

Once the destroy call is submitted, any exception or invalid response produces
only `OUTCOME_UNKNOWN`. The command performs no automatic retry or compensating
mutation and emits no success report.

### `HRET-009` — terminal observation is mutation-free

A pre-existing `DESTROY_SCHEDULED` or `DESTROYED` target is successful only
after exact state/time/deadline validation. That path invokes no mutation API.
An observed late state is reported as a violation, never repaired or relabeled.

### `HRET-010` — null deadline has a narrow meaning

Null means no currently retained version-1 event was observed. The operation
may schedule the fixed target, but neither code, report, nor documentation may
claim that version `1` never carried data or met every historical deadline.

### `HRET-011` — authority separation

The production MAC-signing identity never receives destroy authority, and the
retirement identity is specified without MAC-signing, restore, update, create,
delete, import, reimport, or IAM-management permission. Repository code neither
provisions nor self-attests IAM.

### `HRET-012` — bounded non-sensitive protocol

The operation has fixed connection/RPC bounds, no loop or local persistence,
and one bounded report. Output and diagnostics disclose no resource path,
credential, DSN, exception text, HMAC, correlation value, tenant, principal, or
request data.

### `HRET-013` — other authorities remain unchanged

The pull request changes no migration, role, grant, database function,
production runtime, active HMAC generation, audit append, gap, overflow,
retention, reader/export, break-glass, recovery, tenant, authorization, signing,
or issue #176 authority.

### `HRET-014` — claim limit remains explicit

A successful report proves only one point-in-time Cloud KMS scheduled or
destroyed state under the validated deadline relation. It does not authorize
deployment or prove continuous state, IAM correctness, historical deadline
compliance for a null deadline, provider physical-media erasure, service
readiness, or issue #192 closure.

## 8. Production-reachable negative cases

| ID | Supported entry and counterexample | Required result |
| --- | --- | --- |
| `HRET-001` | Invoke the fixed command after a future contract adds version `3`, or substitute a database row that marks version `1` active. | Refuse before `GetCryptoKey` or any mutation; no dynamic target selection. |
| `HRET-002` | Return version `2` as disabled, scheduled, destroyed, wrong algorithm, or wrong protection; separately inspect every constructed destroy request. | Refuse before mutation; every request target, if any, ends in `/cryptoKeyVersions/1`. |
| `HRET-003` | Configure another parent or return a key with `ENCRYPT_DECRYPT`, software protection, imported/import-only or reimport-eligible posture, or a 30-day destruction delay. | Refuse before mutation. |
| `HRET-004` | Supply a deadline or clock token as an argument/environment value, use a wrong-role DSN, or return a naive/infinite database timestamp. | Input has no such field; wrong authority or time shape refuses. |
| `HRET-005` | Observe version `1` enabled with its greatest live deadline exactly 172,799.999999 seconds ahead. | No destroy call; fixed deadline refusal. |
| `HRET-006` | Run against enabled and disabled version `1` carriers while recording the public KMS protocol. | At most one destroy call; no update/restore/create/delete/import/sign/IAM method exists. |
| `HRET-007` | Destroy returns version `2`, `ENABLED`, software protection, a missing/naive time, a destroy event time, or a destroy time one microsecond after the live deadline. | Outcome unknown; no success report or retry. |
| `HRET-008` | Destroy raises timeout, cancellation-as-ordinary-exception, service unavailable, permission denied, or an unexpected Google API error after entry. | Exit `4`, fixed secret-free diagnostic, zero automatic retries or restoration calls. |
| `HRET-009` | Initial target is already scheduled/destroyed with valid time; repeat with a time one microsecond after the live deadline. | Valid state reports without mutation; late state refuses without mutation. |
| `HRET-010` | Database returns null after no retained version-1 row is visible. | Report preserves null; documentation and bytes make no never-used or historical-compliance claim. |
| `HRET-011` | Inspect the runner protocol and operator contract; attempt to use the runtime MAC principal as the documented retirement principal. | Mutation protocol exposes destroy only; documented identities and permission sets are disjoint. |
| `HRET-012` | Supply canary secrets in DSN, KMS parent, and exception text; force short stdout/stderr writes and flush/close failures. | No canary appears; known result plus report failure exits `5`; unknown remains unknown. |
| `HRET-013` | Inspect the base-to-head path diff and production imports; invoke existing append, retention, overflow, query, and readiness suites. | Only the approved paths change; other authorities and behavior remain unchanged. |
| `HRET-014` | Read the report after a later external restore or ask it for IAM/physical-erasure/production-readiness state. | Report contains no such claim or authority and cannot be reused as continuous state. |

Private-field mutation, monkeypatching a production singleton, and arbitrary
in-process corruption are not acceptance evidence. Client fakes are permitted
only at the explicit PostgreSQL, KMS, and binary-output protocol seams.

## 9. Proposed architecture and smallest change

### 9.1 Components

Phase B, if approved, adds:

1. `deployment.postgresql.security_audit_hmac_retirement`
   - immutable result carriers and closed exceptions;
   - fixed PostgreSQL and KMS protocol seams;
   - exact key, version, time, deadline, and report validation;
   - one explicit state machine around the existing lifecycle observer; and
   - no environment access.
2. `deployment.postgresql.run_security_audit_hmac_retirement`
   - zero-argument command admission;
   - environment and conninfo validation;
   - creation of the Psycopg factory and Google KMS client;
   - binary stdout/stderr protocol and exit mapping; and
   - no catch-all that fabricates a closed result.
3. One focused test module
   - deterministic seam/state tests;
   - live PostgreSQL observation through the provisioned audit-control login
     when the pinned environment is available; and
   - no real Cloud KMS mutation.
4. Minimal operator documentation and mechanical conformance registration.

The production runner is limited to 450 source lines, the command adapter to
160 source lines, every function or method to 80 lines, and the focused test
module to 800 lines. The architecture check owns those fixed budgets; Phase B
cannot evade them by moving authority into an unregistered helper.

The operation imports and composes the existing
`CorrelationHmacLifecycleObserver`; it does not copy or widen its version-set,
algorithm, protection, or database-deadline validation. A second exact target
`GetCryptoKeyVersion` is intentional: the posture observer establishes the
complete cross-system prerequisite, while the last target observation owns the
immediate mutation decision and state-specific time fields.

### 9.2 Data flow

```text
fixed command
  -> validate zero argv + DSN + exact KMS parent
  -> existing lifecycle observer
       -> control-only PostgreSQL version/deadline rows
       -> exact bounded KMS version list and gets
  -> exact GetCryptoKey parent policy
  -> exact current GetCryptoKeyVersion(1)
  -> fresh audit-control session user + database clock
  -> state/deadline admission
       -> already scheduled/destroyed: render only
       -> enabled/disabled: one DestroyCryptoKeyVersion(1)
  -> exact response/time validation
  -> one canonical report and flush
```

No report becomes input to a later decision. Every invocation rebuilds posture
from PostgreSQL and Cloud KMS.

### 9.3 Why this is the minimum coherent design

A documentation-only warning would leave no supported executor. A generic KMS
administrator script would let the caller choose the target, duration, and
action and would bypass the database deadline. Adding destruction to the
production HMAC generator would combine MAC use with key destruction and make a
request-serving identity dangerously overprivileged. A database function
cannot call Cloud KMS and must not receive key custody.

One fixed deployment operation is the smallest component that can bind the
existing database deadline to the provider transition while keeping the active
runtime, database schema, and IAM provisioning unchanged.

Direct `ENABLED`/`DISABLED` to `DESTROY_SCHEDULED` is smaller than an automatic
disable-then-destroy sequence: it needs one mutation, one permission, one
ambiguous-outcome boundary, and no compensating transition. Restore remains a
separate human emergency authority rather than an implicit command fallback.

The 86,400-second delay is the minimum non-import Cloud KMS configuration and
leaves 29 days within the fixed 30-day event-retention duration. The separate
86,400-second scheduling margin makes the normal operation decisively earlier
than the database deadline instead of relying on a five-second network timeout
or an exact cross-system instant.

## 10. Elegance audit

- **Version policy sources of truth:** one checked-in security-audit contract.
- **Live deadline sources of truth:** one existing PostgreSQL function.
- **Current KMS state sources of truth:** one exact provider observation.
- **Mutation transition points:** one fixed `DestroyCryptoKeyVersion` call.
- **Target selectors:** one reviewed literal version `1`; no caller selector.
- **Durations:** one exact provider-owned immutable 86,400-second value plus one
  reviewed 172,800-second admission constant.
- **Mutation permissions exposed by code:** one.
- **Local durable state:** none.
- **Compatibility surfaces:** none.
- **Generic frameworks or registries:** none.
- **Duplicate validation:** state-specific destroy times are new; existing
  lifecycle validation is reused.
- **Deletions:** none in the current read-only posture. No obsolete mutation
  path exists.
- **Clean rewrite assessment:** a repository-wide or observer rewrite is not
  justified. One adjacent runner is smaller and preserves the reviewed
  read-only observer used by startup.

The exact version and duration make this intentionally non-generic. A future
rotation requires a new reviewed contract or an explicit general lifecycle
design; it must not silently inherit version-1 destruction authority.

## 11. Pull request and approval boundary

### 11.1 Exact technical path allowlist

The final implementation may change only these paths:

1. `docs/rfcs/OFARM_Security_Audit_HMAC_Retirement_Execution_RFC_v0_1.md`
2. `deployment/postgresql/security_audit_hmac_retirement.py`
3. `deployment/postgresql/run_security_audit_hmac_retirement.py`
4. `deployment/postgresql/README.md`
5. `kernel/tests/test_security_audit_hmac_retirement.py`
6. `conformance/rewrite_architecture_check.py`
7. `conformance/review_baseline_test_inventory.json`

The Phase A review head changes only path 1. Phase B may use a strict subset of
the other paths. The inventory is a mechanical change required only if the new
test module adds collected nodes. Architecture registration may add only fixed
line/test/import bounds for this operation.

### 11.2 Explicitly unchanged paths and authorities

Reviewers must treat every unlisted path as immutable for this decision,
especially:

- `security_audit/migrations/**`;
- `deployment/postgresql/audit_contract.py`, `provisioning.py`, and
  `provisioning_specs.py`;
- `kernel/security_audit_hmac_posture.py` and its existing tests;
- `kernel/google_kms_correlation_hmac.py` and its existing tests;
- `kernel/security_audit_runtime.py`, `kernel/runtime_config.py`,
  `kernel/application_runtime.py`, and `kernel/api.py`;
- every database role, grant, function, migration, and service identity;
- every tenant, authentication, authorization, signing, issue #172, and issue
  #176 path;
- `.github/**`, dependency locks, deployment manifests, IAM policy, and
  organization policy; and
- `docs/adr/**` and `reference/**`.

No accepted numbered migration may be edited.

### 11.3 Dependencies

- reviewed base `b876736360313736d8da01802521ac2d9e2a37f0`;
- merged PR #223 supplies HMAC version `2`, exact version-1 retry posture, and
  the control-only retention observer;
- merged PR #225 supplies active KMS correlation-HMAC custody;
- merged PR #226 supplies the read-only cross-system lifecycle observer;
- merged PRs #307 and #308 supply the one-shot logical-retention operation and
  elapsed-time correction without changing the deadline observer;
- merged PR #314 supplies dynamic runtime health but is not changed or invoked;
- no open or stacked pull request is a prerequisite; and
- issue #192 remains open.

### 11.4 Reviewer non-requirements

Reviewers must not require this pull request to:

- create, rotate, disable, enable, restore, import, reimport, or delete a key;
- support disable-before-destroy organization policy;
- make the executor generic for future rotations or multiple inactive versions;
- change a database migration, role, grant, observer, or retention function;
- provision or introspect IAM, service accounts, Workload Identity,
  organization policy, or Cloud Audit Logs;
- add runtime startup/readiness enforcement or continuous KMS polling;
- implement a scheduler, deployment cadence, or production invocation;
- prove historical compliance when the current database deadline is null;
- prove provider physical-media erasure;
- record an `AUDIT_GAP` or KMS act in the audit database;
- implement break-glass, store loss, or final hostile cross-slice evidence;
- change issue #172 or #176 work; or
- close issue #192.

Those requests change another authority, custody surface, irreversible
transition, or claim and require a separate prerequisite, follow-up, or new
decision version.

### 11.5 Follow-ups

Issue #192 continues to own separate decisions for:

- operational `AUDIT_GAP` recording and crash/unavailable-interval
  reconciliation;
- dual-approved break-glass export and temporary-login lifecycle;
- empty-recreate/store-loss operation;
- deployment IAM evidence, invocation cadence, and any external clock-health
  fence before production use of this command; and
- remaining real-ASGI/PostgreSQL hostile and cross-slice closure evidence.

A future correlation-HMAC rotation must separately decide whether to retain
this exact one-version operation, introduce a governed generic retirement
controller, or require disable-first policy. No new issue is created merely to
duplicate the existing #192 parent scope.

### 11.6 Stop and reapproval conditions

Stop and require a new decision version before implementation or merge if work
would:

- target any version other than `1` or mutate active version `2`;
- change the exact 86,400-second KMS destruction duration or 172,800-second
  live-deadline lead;
- add disable, enable, restore, update, create, delete, rotate, import,
  reimport, signing, IAM, or organization-policy authority;
- add a caller-selected version, action, deadline, duration, timeout, retry, or
  report field;
- add automatic retry, a second destroy call, compensating mutation, local
  receipt, scheduler, loop, or background process;
- change a migration, database role/grant/function, runtime module, HMAC
  generator, or lifecycle observer;
- add any path outside the exact allowlist;
- name a different pull request;
- materially change the trust boundary, authority map, state machine,
  permitted effects, non-effects, invariant, output protocol, or irreversible
  behavior; or
- authorize deployment, release, production access or operation, current/default
  promotion, production readiness, issue closure, or a security waiver.

Meaning-preserving wording, test clarity, mechanical inventory regeneration,
and line-budget headroom inside the allowlist do not require a new version.

## 12. Provisional design record

The one-shot technical operation is not provisional. Its fixed target, direct
destroy transition, deadline relation, ambiguous-outcome protocol, and claim
limits remain valid if a separately governed deployment system invokes it.

The repository workflow and deployment posture are provisional:

- this Phase A decision may authorize repository implementation only in its
  named draft pull request;
- no production IAM principal, organization policy, KMS key, clock-health
  fence, invocation cadence, or deployment route is established here;
- a real deployment must independently prove the required credential split,
  exact 86,400-second immutable key setting, disable-before-destroy
  compatibility, clock prerequisite, and timely invocation; and
- before deployment, AI-attested task approval must be replaced by an
  independently human-controlled and independently verifiable approval or
  signing system.

Evidence requiring redesign includes a required disable-first organization
policy, inability to isolate `destroy` from the runtime MAC principal, an
immutable KMS duration other than 86,400 seconds, inability to establish the
clock prerequisite, a need to repair a missed deadline, a required restore
procedure, or a demonstrated need for historical deadline evidence after all
version-1 rows are gone.

The likely upgrade path is a separately approved deployment/IAM prerequisite,
forward database migration for durable retirement receipts if required, or a
new general lifecycle decision. None may be appended to this PR merely to make
the initial operation deployable.

## 13. Traceability and verification

| ID | Owning code | Negative evidence | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `HRET-001` | Runner constants and existing lifecycle observer | Future version, wrong active row, extra/missing KMS version | Exact `(1, 2)` / active `2` / target `1` | Focused seam tests plus existing posture tests |
| `HRET-002` | Target builder and KMS protocol | Wrong active state and request capture | Every mutation names only version `1`; no active mutation method | Focused protocol tests |
| `HRET-003` | Parent validator | Wrong name/purpose/template/protection/import/duration | Exact MAC/HSM/HMAC-SHA-256/86,400-second parent | Focused KMS carrier tests |
| `HRET-004` | Existing DB observer plus fresh clock query | Caller deadline, wrong role, malformed time | Database-only deadline and clock | Seam tests plus live PostgreSQL role test |
| `HRET-005` | Deadline admission | Boundary minus one microsecond, expired deadline | Exact 172,800-second threshold, zero mutation on refusal | Deterministic time tests |
| `HRET-006` | Runner state machine and KMS protocol | Enabled/disabled target, method-surface inspection | One destroy maximum, `retry=None`, fixed timeout, no other mutation | Call-recording tests |
| `HRET-007` | Destroy-response validator | Wrong resource/state/algorithm/protection/time/deadline | Exact scheduled response only | Parametrized carrier tests |
| `HRET-008` | Submitted state and CLI mapping | Every ordinary destroy exception and malformed response | Exit `4`, no retry/restore/success bytes | State and byte-protocol tests |
| `HRET-009` | Initial target classifier | Pre-existing valid and late scheduled/destroyed states | Valid no-op report; late no-mutation refusal | Parametrized state tests |
| `HRET-010` | Result carrier, renderer, README | Null database deadline | JSON null and explicit no-history claim | Byte and documentation tests |
| `HRET-011` | KMS Protocol and operator documentation | Forbidden method and identity review | Exact code method surface and disjoint documented permissions | Protocol introspection and documentation assertions |
| `HRET-012` | Fixed adapters and renderer | Canary secrets, hostile input, short writes/flush failures | Bounded calls, canonical report, exits `2`–`5`, no secret echo | CLI/output tests |
| `HRET-013` | Exact path allowlist | Base-to-head diff and affected regression suites | No unlisted path or authority change | Mechanical path check and focused regressions |
| `HRET-014` | RFC, README, report schema | Later restore and overclaim search | Point-in-time scheduled/destroyed claim only | Documentation and report assertions |

### 13.1 Phase A verification gates

Before the version-1 live decision card, the exact RFC head must pass:

```text
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

The exact head must receive one full Phase A review against this contract.
Every demonstrated in-scope Blocker must be corrected and the affected
invariants re-reviewed before a live card is shown. Phase A remains
documentation-only.

### 13.2 Phase B verification gates

If later approved, the exact implementation head must pass at least:

```text
.venv/bin/pytest -q kernel/tests/test_security_audit_hmac_retirement.py
.venv/bin/pytest -q kernel/tests/test_security_audit_hmac_posture.py
.venv/bin/pytest -q kernel/tests/test_google_kms_correlation_hmac.py
.venv/bin/pytest -q kernel/tests/test_security_audit_runtime.py
.venv/bin/pytest -q kernel/tests/test_postgresql_audit_migration.py -k hmac
.venv/bin/pytest -q kernel/tests/test_rewrite_architecture.py
.venv/bin/ruff check deployment/postgresql/security_audit_hmac_retirement.py deployment/postgresql/run_security_audit_hmac_retirement.py kernel/tests/test_security_audit_hmac_retirement.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

PostgreSQL-backed skips are reported as skips and never presented as passing
evidence. No test may submit a real Cloud KMS mutation. The canonical test-node
inventory must be regenerated mechanically from the exact implementation tree.

Before merge, the AI must also:

1. compare every base-to-head changed path against section 11.1's exact
   technical allowlist;
2. verify that technical allowlist is a subset of the live card's maximum path
   envelope;
3. reject any path or subset failure;
4. post the compact PR scope report required by `AGENTS.md` with stable
   decision, card, approval, and pull-request references;
5. recheck the exact head, required hosted checks, exact-head review, live task
   evidence, named-PR binding, and absence of later cancellation; and
6. run `git diff --check` after the final change.

## 14. Open decisions and review disposition

### 14.1 Open material decisions

None inside the proposed version-1 contract. The proposal deliberately chooses:

- direct `ENABLED`/`DISABLED` to `DESTROY_SCHEDULED` with no disable step;
- exact target version `1` and active version `2`;
- exact 86,400-second KMS destruction duration;
- exact 172,800-second live-deadline admission;
- one destroy call and no automatic retry or compensation;
- no historical-compliance claim for a null current deadline; and
- external, separately governed IAM and deployment ownership.

Changing any of those choices after a live card requires decision version `2`.

### 14.2 Review disposition

- **Blockers:** Phase A exact-head review pending.
- **Follow-ups:** the separate issue #192 boundaries in section 11.5.
- **Preferences:** none recorded.
- **Phase B:** unauthorized.
- **Deployment:** unauthorized.

Once Phase B is explicitly approved, implemented, and verified, only a
demonstrated in-scope Blocker may delay merge. New ideas, Preferences, and
non-blocking hardening become Follow-ups and do not reopen review.

## 15. External semantics fixed by this contract

The contract incorporates the following Cloud KMS semantics as explicit
invariants rather than delegating authority to mutable prose:

- `DestroyCryptoKeyVersion` moves an enabled or disabled version to
  `DESTROY_SCHEDULED` and sets `destroy_time` from the CryptoKey's immutable
  `destroy_scheduled_duration`;
- the default provider duration is 30 days, while a non-import key may be
  configured from 24 hours through 120 days only when the key is created;
- an optional organization policy may require disable-before-destroy;
- a scheduled version may be restored to disabled by a separately permissioned
  API before its destruction time; and
- `cloudkms.cryptoKeyVersions.destroy` is an administrative write permission
  applied at the CryptoKey or a higher resource, not an individual version.

Informative provider references observed during Phase A:

- <https://docs.cloud.google.com/kms/docs/destroy-restore>
- <https://docs.cloud.google.com/kms/docs/key-states>
- <https://docs.cloud.google.com/kms/docs/control-key-destruction>
- <https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/destroy>
- <https://docs.cloud.google.com/kms/docs/reference/permissions-and-roles>
- <https://docs.cloud.google.com/kms/docs/consistency>
