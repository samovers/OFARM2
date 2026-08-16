# OFARM Security-Audit HMAC Retirement Execution — Phase A Contract v0.2

**Status:** decision version 2 approved for Phase B repository implementation
in draft pull request #316; deployment and every real Cloud KMS mutation
remain unauthorized

**Draft pull request:** `https://github.com/samovers/OFARM2/pull/316`

**Contract identity:**
`ofarm2.security-audit-hmac-retirement-execution.v0.2`

The RFC filename remains `v0_1` because the already-published exact path
envelope does not authorize a rename. Contract version `v0.2` and decision
version `2` record the semantic replacement of the withdrawn version-1 card.

**Decision identity:**
`ISSUE192-SECURITY-AUDIT-HMAC-RETIREMENT-EXECUTION-001`, approved version `2`

Version `1` is historical evidence only and grants no authority. Owner review
[`4945455733`](https://github.com/samovers/OFARM2/pull/316#pullrequestreview-4945455733)
demonstrated that its exception boundary and timing premise were incomplete.

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
maximum absolute KMS-minus-database clock skew = 1 second
maximum admission-start-to-provider-acceptance elapsed time = 5 seconds
timestamp comparison error = 0 nanoseconds
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
   `DESTROY_SCHEDULED`, with a full-precision `destroy_time` inside the exact
   two-sided 86,400-second scheduling window and no later than an observed live
   database deadline;
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
- an in-process clock-health or provider-acceptance attestation mechanism, a
  caller-supplied timing token, or a claim that the five-second client timeout
  proves the provider cannot accept a write later;
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
  security waiver;
- a claim that a null current database deadline proves version `1` never had a
  retained event or met every historical deadline; and
- deployment when independently verifiable evidence cannot establish the exact
  one-second clock-skew and five-second provider-acceptance prerequisites.

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
- the exact 172,800-second admission lead, one-second absolute clock-skew bound,
  five-second admission-to-acceptance bound, and lossless timestamp comparison;
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
- the deployment-layer runner and fixed command adapter;
- Python's monotonic nanosecond clock for one-operation elapsed-time admission;
  and
- deployment-controlled endpoint routing, DNS, TLS, service files, secret
  injection, Application Default Credentials, and stdout destination.

The timing premise is exact. Let:

```text
D = 86,400 seconds  # immutable provider scheduled-destruction duration
M = 86,400 seconds  # fixed scheduling safety margin
S = 1 second        # maximum absolute KMS-minus-database clock skew
A = 5 seconds       # maximum admission-start-to-provider-acceptance elapsed
E = 0 nanoseconds   # comparison error after lossless integer conversion
```

Deployment is admissible only while independently verifiable evidence proves:

```text
S + A + E < M
1 second + 5 seconds + 0 nanoseconds < 86,400 seconds
```

The command captures a monotonic admission start immediately before requesting
the fresh database clock. Starting before the database observation is
conservative: provider acceptance within five seconds of that earlier point
also bounds acceptance within five seconds of the observation. Before entering
the destroy client method, elapsed monotonic time must remain strictly below
five seconds. The destroy RPC receives only the positive remaining portion of
that same five-second budget as a conservatively rounded-down timeout.

The client timeout is a client/RPC deadline, not proof that Cloud KMS cannot
apply a write after the client reports timeout or cancellation. A deployment
must additionally possess a current, independently controlled and verifiable
provider/transport guarantee that no accepted state change can occur after the
five-second admission budget, including ambiguous timeout and cancellation
paths. Historical latency samples, a successful preflight, the GAPIC timeout
argument, and the response validator are not that guarantee.

The clock evidence must bind the exact PostgreSQL route and configured Cloud
KMS endpoint to an authenticated common time reference, prove absolute skew no
greater than one second, carry its measurement instant and expiry, be measured
within the 60 seconds before invocation, and remain valid through the
operation. The acceptance evidence must be a current, versioned, independently
controlled verification artifact that binds the exact Cloud KMS endpoint,
service, method, client/transport version, and transmitted deadline semantics.
It must prove that no state change can be accepted more than five seconds after
the monotonic admission start, including ambiguous timeout and cancellation
paths, and its effective interval must cover the complete operation. If either
artifact is absent, expired, not independently verifiable, or does not cover
ambiguous completion, the external deployment gate must refuse before
launching this command. There is no command-line or environment override. This
RFC supplies no such artifact and grants no deployment authority.

The returned Cloud KMS `destroy_time`, compared without precision loss, is the
final scheduling-time evidence after a known response. It cannot repair an
unsafe submission, which is why the pre-invocation inequality is mandatory.

### 4.3 Untrusted actors and inputs

- every command-line token;
- missing, malformed, whitespace-only, multi-host, service-file, option-bearing,
  or hostile conninfo;
- a wrong database role or cross-service database route;
- missing, malformed, or hostile configured KMS parent text;
- ambient credentials that lack the required permissions;
- network availability, latency, RPC acknowledgement, and connection closure;
- every ordinary `Exception` and its message, arguments, cause, context, and
  traceback at each declared dependency, validation, rendering, and output
  seam;
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
- KMS service compromise, forged provider time, or violation of the externally
  established one-second clock-skew or five-second acceptance bounds;
- an independently authorized restore, update, import, reimport, delete, key
  creation, or IAM change racing the command; and
- simultaneous corruption of both PostgreSQL and Cloud KMS authorities.

Ordinary configuration mistakes, wrong credentials, wrong resource routes,
unsupported KMS state, response substitution at the supported client seam,
every ordinary `Exception`, RPC failure, duplicate invocation, and output
failure remain in scope. `KeyboardInterrupt`, `SystemExit`, `GeneratorExit`,
and other non-`Exception` process-control `BaseException` subclasses are outside
the closed protocol; arbitrary in-process code execution remains excluded.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Known correlation-HMAC versions | Checked-in security-audit contract; must equal `(1, 2)` |
| Active version | Checked-in contract plus database observer; must equal `2` |
| Retirement target | This approved decision; fixed to version `1` |
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
| Clock-skew and late-acceptance admissibility | External deployment evidence proving `S <= 1 second`, `A <= 5 seconds`, and no late commit after the transmitted deadline |
| One-operation elapsed bound | Runner-owned `time.monotonic_ns()` start before the fresh database-clock request |
| Timestamp arithmetic | Lossless signed integer epoch nanoseconds; PostgreSQL microseconds are exact multiples of 1,000 nanoseconds |
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
KMS read RPC timeout = 5 seconds per call
KMS destroy RPC timeout = conservatively rounded-down positive encoding of the remaining fixed 5-second admission budget
KMS retry = None for every call
KMS list page size = known version count + 1
```

Before parsing command input, the adapter creates the single operation-phase
carrier in `PRE_SUBMISSION` and passes it into the runner. Static failures
therefore have an unambiguous phase even if runner construction cannot
complete. Only the runner may advance that carrier; the adapter may only read
it when selecting the fixed exit protocol.

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

Finally, it captures `admission_started_monotonic_ns` immediately before opening
one short read-only audit-control transaction and reading exact `session_user`
plus `clock_timestamp()`. The session user must be
`ofarm_security_audit_control_login`; the timestamp must be finite and
timezone-aware. The previously observed greatest version-1 deadline cannot
increase because fresh version-1 append is migration-forbidden. Retention may
remove a row after observation, but using the earlier greatest deadline remains
conservative for this operation.

No database transaction remains open when the mutation RPC is attempted.

All timestamp validation and comparison uses signed integer epoch nanoseconds:

- a PostgreSQL aware `datetime` is normalized to UTC and converted as exact
  `whole_seconds = timedelta.days * 86,400 + timedelta.seconds`, then
  `epoch_nanoseconds = whole_seconds * 1,000,000,000 + microsecond * 1,000`,
  without calling the float-returning `timestamp()`;
  the stored database timestamp is the authority, so appending three zero
  nanosecond digits introduces no error;
- a protobuf `Timestamp` is range-validated and converted from its exact
  `seconds * 1,000,000,000 + nanos`, with canonical
  `0 <= nanos < 1,000,000,000`; the runner must not call `ToDatetime()` before
  comparison because Python `datetime` would discard nanoseconds; and
- duration and boundary arithmetic uses integer nanoseconds only. No float,
  truncation, rounding, tolerance, or rendered string participates in a
  decision. Therefore `E = 0 nanoseconds`.

### 6.3 Target states before mutation

Only these version-1 states are admitted:

| Observed state | Required time shape | Transition |
| --- | --- | --- |
| `ENABLED` | no destroy times | new scheduling path |
| `DISABLED` | no destroy times | new scheduling path |
| `DESTROY_SCHEDULED` | valid full-precision protobuf `destroy_time`; no `destroy_event_time` | validate and report; no mutation |
| `DESTROYED` | valid full-precision protobuf `destroy_event_time`; no `destroy_time` | validate and report; no mutation |

Every other state or time shape is fixed exit-`3` unavailable before mutation.

After obtaining `database_observed_at`, a pre-existing
`DESTROY_SCHEDULED` state is conforming only when its full-precision timestamp
satisfies:

```text
database_observed_at + S < destroy_time
destroy_time <= database_observed_at + D + S

# with fixed constants
database_observed_at + 1 second < destroy_time
destroy_time <= database_observed_at + 86,401 seconds
```

The strict lower bound refuses a scheduled carrier whose destruction time is
already due under the maximum permitted positive KMS clock lead. The upper
bound proves the existing schedule is consistent with the validated 86,400-
second parent duration. A pre-existing `DESTROYED` state additionally requires:

```text
destroy_event_time <= database_observed_at + S
```

A pre-existing scheduled or destroyed timestamp outside those provider-time
windows is a fixed exit-`3` unavailable observation, never success and never a
mutation. It is not repaired.

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
returns fixed exit `1` with no success report; it does not restore, delete, or
rewrite the KMS version to hide it.

### 6.4 New scheduling admission

For `ENABLED` or `DISABLED`, a non-null live deadline permits mutation only
when:

```text
database_observed_at + 172,800 seconds <= greatest_purge_after
```

The first 86,400 seconds cover the exact Cloud KMS scheduled-destruction delay.
The second 86,400 seconds are a fixed safety margin. The deployment prerequisite
requires `S + A + E < 86,400 seconds`, so a conforming provider acceptance is
strictly earlier than the admitted database deadline even when equality holds
in the admission formula.

If the live deadline is strictly closer than the exact 172,800-second
threshold, expired, infinite, naive, or otherwise invalid, the command reports
a no-mutation deadline refusal. Exact equality is admitted. It does not schedule
late and call the result compliant.

Immediately before submission, the runner computes:

```text
elapsed_ns = monotonic_ns() - admission_started_monotonic_ns
remaining_ns = 5,000,000,000 - elapsed_ns
timeout_seconds = nextafter(remaining_ns / 1,000,000,000, 0.0)
```

Non-monotonic, negative, overflowed, or `elapsed_ns >= 5,000,000,000`
observations produce fixed exit `1` before mutation. The division exists only
to adapt integer nanoseconds to the client's binary64 seconds API;
`math.nextafter(..., 0.0)` makes the transmitted positive finite timeout
strictly no greater than the exact remaining interval. A non-positive or
non-finite adapter result also refuses before mutation. No timestamp decision
uses that float. The destroy method receives this one conservative timeout and
`retry=None`. This locally bounds submission and client wait but does not
replace the external no-late-acceptance evidence required by section 4.2.

A null `greatest_purge_after` means only that the current database observation
found no retained pre-tenant failure naming version `1`. It does not prove that
there was never such a row or that a historical deadline was met. The command
may schedule immediately because there is no currently retained row whose live
deadline must remain bound. Its report preserves the null and makes no
historical-compliance claim.

Null does not relax the elapsed, clock-evidence, or two-sided provider-time
window.

### 6.5 Mutation transition

After every prerequisite passes, the runner creates exactly:

```text
DestroyCryptoKeyVersionRequest(
    name = configured_parent + "/cryptoKeyVersions/1"
)
```

It calls `destroy_crypto_key_version` once with `retry=None` and the
conservatively rounded-down positive timeout derived above. There is no
disable call, retry, fallback, alternate target, or second mutation.

The runner owns the transitions among three explicit phases:
`PRE_SUBMISSION`, `SUBMITTED`, and `RESULT_KNOWN`. A fully validated
pre-existing scheduled or destroyed observation advances directly from
`PRE_SUBMISSION` to `RESULT_KNOWN`. A mutation path changes from
`PRE_SUBMISSION` to `SUBMITTED` immediately before entering the client method,
then changes to `RESULT_KNOWN` only after the complete response, resource,
state, import posture, full-precision time window, deadline relation, and
immutable result carrier validate. From `SUBMITTED` until that exact
validation, any ordinary `Exception`, timeout, cancellation represented as an
ordinary exception, malformed response, wrong target, unsupported state,
missing time, or deadline conflict is `OUTCOME_UNKNOWN`. The command must not
automatically retry or attempt restoration.

A successful new result must be an exact `CryptoKeyVersion` with:

```text
name == configured_parent + "/cryptoKeyVersions/1"
state == DESTROY_SCHEDULED
algorithm == HMAC_SHA256
protection_level == HSM
reimport_eligible == false
import_job and import_time are absent
destroy_time is a valid full-precision protobuf Timestamp
destroy_event_time is absent
```

The returned time must satisfy the exact two-sided scheduling window:

```text
database_observed_at + D - S <= destroy_time
destroy_time <= database_observed_at + D + A + S

# with fixed constants
database_observed_at + 86,399 seconds <= destroy_time
destroy_time <= database_observed_at + 86,406 seconds
```

The lower bound rejects a stale or substituted historical carrier even when the
database deadline is null. The upper bound binds the response to the admitted
operation and exact provider duration. When a live database deadline exists,
the returned `destroy_time` must also be no later than it. Every comparison uses
the integer nanosecond representation before rendering. A conflicting response
is outcome-unknown because the remote side effect may already have occurred.
No report may call it compliant.

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
through the provider-owned terminal states. Exit `4` or exit `5` must never be
retried automatically. A later deliberate invocation starts with the complete
read-only prerequisite observation again.

### 6.7 Output and exit protocol

Known success emits one canonical ASCII JSON line to binary stdout:

```json
{"destructionTime":"2030-01-02T03:04:05.000000000Z","greatestPurgeAfter":"2030-01-03T03:04:05.000000000Z","outcome":"SCHEDULED","schema":"ofarm.security-audit-hmac-retirement-report.v2","targetKeyVersion":1}
```

The three successful outcomes are:

- `SCHEDULED` — this invocation obtained the exact scheduling response;
- `ALREADY_SCHEDULED` — read-only observation found a conforming scheduled
  target; and
- `ALREADY_DESTROYED` — read-only observation found a conforming destroyed
  target.

`destructionTime` carries the provider's scheduled `destroy_time` for scheduled
outcomes and completed `destroy_event_time` for the destroyed outcome.
Provider and database timestamps render in canonical UTC RFC 3339 with exactly
nine fractional digits after every decision has used full integer-nanosecond
precision. Database microseconds receive three trailing zeroes.
`greatestPurgeAfter` is either that normalized timestamp or JSON `null`. The
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
| `3` | the operation became unavailable through a dependency or unexpected ordinary exception before destroy submission |
| `4` | destroy was submitted but its exact outcome is unknown; never retry automatically |
| `5` | a known result existed but complete report delivery failed; never retry automatically |

The exact non-zero diagnostic lines are:

```text
exit 1: security-audit HMAC retirement refused\n
exit 2: security-audit HMAC retirement command invalid\n
exit 3: security-audit HMAC retirement unavailable before submission\n
exit 4: security-audit HMAC retirement outcome unknown; do not retry automatically\n
exit 5: security-audit HMAC retirement report delivery failed; do not retry automatically\n
```

The command adapter provides one final `except Exception` sanitizing boundary
around static validation, every declared dependency call, runner execution,
result rendering, and binary output. It never stores, formats, logs, chains, or
renders `str(exc)`, `repr(exc)`, `exc.args`, a cause, context, or traceback. No
ordinary `Exception` may reach `sys.excepthook`.

Closed policy/configuration exceptions retain exits `1` and `2` only while the
phase is `PRE_SUBMISSION`; any other ordinary exception in that phase becomes
exit `3`. Phase takes precedence over exception class: any ordinary exception
while `SUBMITTED` becomes only exit `4`. Once a complete result is validated and
the phase is `RESULT_KNOWN`, any rendering, write, or flush exception becomes
exit `5`; stdout may contain an untrusted partial or unconfirmed prefix and must
be ignored unless exit `0` is observed. Exits `1` through `4` require empty
stdout. Stderr contains only the applicable fixed line when delivery succeeds;
a stderr delivery failure is swallowed after the numeric exit is fixed and may
leave only an empty or partial fixed prefix. It never creates a traceback or
exposes exception content.

Direct `BaseException` subclasses named in section 4.4 remain outside this
boundary. The catch-all classifies by the runner-owned phase; it does not invent
commit ambiguity or success.

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
at least 172,800 seconds of database-observed lead. Exact equality is admitted;
a closer or expired deadline causes a no-mutation refusal. Deployment must also
prove `S <= 1 second`, `A <= 5 seconds`, `E = 0`, no provider commit after the
five-second acceptance bound, and `S + A + E < 86,400 seconds`. The monotonic
admission window expires before submission rather than weakening that premise.

### `HRET-006` — one irreversible transition

One admitted run submits at most one `DestroyCryptoKeyVersion` request with
`retry=None` and only the conservatively rounded-down positive encoding of the
remaining fixed five-second admission budget as timeout. It never disables,
enables, restores,
creates, deletes, rotates, imports, reimports, signs, or changes IAM.

### `HRET-007` — exact scheduled response

New scheduling succeeds only with the exact target resource in
`DESTROY_SCHEDULED`, correct algorithm and protection level, one valid
nanosecond-precision `destroy_time` inside the exact
`[database + 86,399 seconds, database + 86,406 seconds]` window, no
`destroy_event_time`, no import/reimport posture, and no deadline conflict.
Pre-existing scheduled and destroyed timestamps must satisfy their distinct
provider-time windows before they can be reported.

### `HRET-008` — ambiguity never becomes retry or success

The runner owns `PRE_SUBMISSION`, `SUBMITTED`, and `RESULT_KNOWN` phases. Every
unexpected ordinary exception before submission is sanitized to fixed exit
`3`, while the closed prerequisite-refusal and static-configuration classes
retain fixed exits `1` and `2`; once the destroy call is submitted, every
ordinary exception or invalid response produces only exit `4` /
`OUTCOME_UNKNOWN`; and an exception after a complete known result produces only
exit `5`. No ordinary exception reaches the default interpreter hook. The
command performs no automatic retry or compensating mutation and emits no
success report for an unknown outcome.

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
one bounded report, and a final ordinary-exception sanitizer. Output and
diagnostics disclose no resource path, credential, DSN, exception text,
traceback, HMAC, correlation value, tenant, principal, or request data. Time
comparisons retain every provider nanosecond and rendered timestamps use the
version-2 nine-digit protocol.

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
| `HRET-005` | Observe version `1` enabled with its deadline exactly 172,800 seconds ahead, then 172,799.999999 seconds ahead; separately omit, expire, or exceed the exact `S <= 1 second` / `A <= 5 seconds` external evidence, and advance monotonic elapsed to exactly five seconds before submission. | Equality admits; every closer deadline or expired monotonic window refuses in-process before the destroy method. Missing external evidence makes the deployment gate refuse before process launch; a direct invocation without it is unauthorized and supplies no compliant evidence. The client timeout alone is never accepted as provider-acceptance proof. |
| `HRET-006` | Run against enabled and disabled version `1` carriers while recording the public KMS protocol and the exact binary64 timeout. | At most one destroy call; `retry=None`; the timeout is positive and no greater than the remaining admission interval; no update/restore/create/delete/import/sign/IAM method exists. |
| `HRET-007` | Destroy returns version `2`, `ENABLED`, software protection, a missing/malformed time, a destroy event time, `1970-01-01T00:00:00Z`, one nanosecond outside either side of the new scheduling window, or a time one nanosecond after the live deadline. | Outcome unknown; no success report or retry, including when the database deadline is null. |
| `HRET-008` | Inject both a declared dependency-unavailable exception and an unexpected `RuntimeError("CANARY_RETIREMENT_CREDENTIAL")` before submission, inside `destroy_crypto_key_version`, during response validation, and after `RESULT_KNOWN`. | Exact exits `3`, `4`, `4`, and `5` respectively; fixed stderr protocol, required stdout shape, no traceback or canary, zero automatic retries or restoration calls. |
| `HRET-009` | Initial target is already scheduled with a time at/before `database + 1 second`, after `database + 86,401 seconds`, or one nanosecond after a live deadline; repeat with a destroyed event in the future beyond the skew bound. | Valid state reports without mutation; stale or impossible provider time is fixed exit `3`, while a valid provider time after the live deadline is fixed exit `1`; neither path mutates. |
| `HRET-010` | Database returns null after no retained version-1 row is visible. | Report preserves null; documentation and bytes make no never-used or historical-compliance claim. |
| `HRET-011` | Inspect the runner protocol and operator contract; attempt to use the runtime MAC principal as the documented retirement principal. | Mutation protocol exposes destroy only; documented identities and permission sets are disjoint. |
| `HRET-012` | Supply canary secrets in DSN, KMS parent, and expected and unexpected ordinary-exception text; force short stdout/stderr writes and flush/close failures; supply provider nanoseconds not divisible by 1,000. | No canary or traceback appears; comparisons preserve the nanoseconds; known result plus report failure exits `5`; submitted unknown remains exit `4`; no ordinary exception reaches `sys.excepthook`. |
| `HRET-013` | Inspect the base-to-head path diff and production imports; invoke existing append, retention, overflow, query, and readiness suites. | Only the approved paths change; other authorities and behavior remain unchanged. |
| `HRET-014` | Read the report after a later external restore or ask it for IAM/physical-erasure/production-readiness state. | Report contains no such claim or authority and cannot be reused as continuous state. |

Private-field mutation, monkeypatching a production singleton, and arbitrary
in-process corruption are not acceptance evidence. Client fakes are permitted
only at the explicit PostgreSQL, KMS, and binary-output protocol seams.

## 9. Proposed architecture and smallest change

### 9.1 Components

Approved Phase B adds:

1. `deployment.postgresql.security_audit_hmac_retirement`
   - immutable result carriers and closed exceptions;
   - fixed PostgreSQL and KMS protocol seams;
   - exact integer-nanosecond key, version, time, deadline, and report
     validation;
   - one explicit `PRE_SUBMISSION` / `SUBMITTED` / `RESULT_KNOWN` state machine
     around the existing lifecycle observer and monotonic admission budget; and
   - no environment access.
2. `deployment.postgresql.run_security_audit_hmac_retirement`
   - zero-argument command admission;
   - environment and conninfo validation;
   - creation of the Psycopg factory and Google KMS client;
   - binary stdout/stderr protocol and exit mapping; and
   - one final ordinary-exception sanitizer that classifies only from the
     runner-owned phase and never renders exception content.
3. One focused test module
   - deterministic seam/state tests;
   - subprocess canary tests for declared and unexpected ordinary exceptions in
     every phase plus exact stdout/stderr bytes;
   - nanosecond, two-sided window, equality, monotonic-expiry, and conservative
     timeout-encoding cases;
   - static operator-contract assertions that repository deployment remains
     unauthorized without the external timing evidence;
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
  -> capture monotonic admission start
  -> fresh audit-control session user + database clock
  -> lossless integer-nanosecond normalization
  -> state/deadline admission
       -> already scheduled/destroyed: render only
       -> enabled/disabled: require positive five-second remainder and encode a
          conservatively shorter client timeout
       -> set SUBMITTED; one DestroyCryptoKeyVersion(1)
  -> exact two-sided response/time validation; set RESULT_KNOWN
  -> one canonical version-2 report and flush
  -> final ordinary-exception sanitizer maps only from phase
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
86,400-second scheduling margin is not a vague latency allowance. It is governed
by the exact `S + A + E < M` proof and two-sided provider-time window. The
five-second client deadline alone never establishes `A`; until independent
deployment evidence establishes both `S` and no-late-commit `A`, this repository
operation is intentionally non-deployable.

## 10. Elegance audit

- **Version policy sources of truth:** one checked-in security-audit contract.
- **Live deadline sources of truth:** one existing PostgreSQL function.
- **Current KMS state sources of truth:** one exact provider observation.
- **Mutation transition points:** one fixed `DestroyCryptoKeyVersion` call.
- **Target selectors:** one reviewed literal version `1`; no caller selector.
- **Durations:** one exact provider-owned immutable 86,400-second value, one
  reviewed 172,800-second admission constant, and one five-second monotonic
  acceptance budget.
- **Clock/precision allowances:** one-second absolute skew and zero-nanosecond
  comparison error; neither is caller-configurable.
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
- deployment IAM evidence, invocation cadence, and the independently
  verifiable one-second clock-skew / five-second no-late-acceptance gate before
  production use of this command; and
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
- change `S = 1 second`, `A = 5 seconds`, `E = 0 nanoseconds`, the strict
  `S + A + E < 86,400 seconds` inequality, either two-sided time window, or the
  requirement for independently verifiable no-late-provider-acceptance
  evidence;
- add disable, enable, restore, update, create, delete, rotate, import,
  reimport, signing, IAM, or organization-policy authority;
- add a caller-selected version, action, deadline, duration, timeout, retry, or
  report field;
- add automatic retry, a second destroy call, compensating mutation, local
  receipt, scheduler, loop, or background process;
- weaken or remove the `PRE_SUBMISSION` / `SUBMITTED` / `RESULT_KNOWN` phase
  boundary, final ordinary-exception sanitizer, fixed diagnostics, or
  nanosecond-preserving version-2 report protocol;
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
destroy transition, exact timing inequality, two-sided timestamp validation,
ordinary-exception boundary, ambiguous-outcome protocol, and claim limits
remain valid if a separately governed deployment system proves every invocation
prerequisite.

The repository workflow and deployment posture are provisional:

- this Phase A decision may authorize repository implementation only in its
  named draft pull request;
- no production IAM principal, organization policy, KMS key, clock-health
  fence, invocation cadence, or deployment route is established here;
- a real deployment must independently prove the required credential split,
  exact 86,400-second immutable key setting, disable-before-destroy
  compatibility, one-second absolute clock bound, and provider guarantee that
  an ambiguous write cannot be accepted after the five-second admission budget;
  the GAPIC timeout and historical latency are explicitly insufficient; and
- before deployment, AI-attested task approval must be replaced by an
  independently human-controlled and independently verifiable approval or
  signing system.

Evidence requiring redesign includes a required disable-first organization
policy, inability to isolate `destroy` from the runtime MAC principal, an
immutable KMS duration other than 86,400 seconds, inability to establish either
timing prerequisite for the exact service and transport, provider behavior that
can commit after the admitted deadline, a need to repair a missed deadline, a
required restore procedure, or a demonstrated need for historical deadline
evidence after all version-1 rows are gone.

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
| `HRET-005` | Deadline and monotonic admission | Equality, boundary minus one microsecond, expired evidence, elapsed exactly five seconds | Exact 172,800-second threshold plus `S + A + E < M`; zero mutation on refusal | Deterministic wall/monotonic tests plus static deployment-contract review |
| `HRET-006` | Runner state machine and KMS protocol | Enabled/disabled target, method-surface, remaining-time and binary64 encoding capture | One destroy maximum, `retry=None`, positive timeout no greater than the remaining interval, no other mutation | Call-recording and numeric-boundary tests |
| `HRET-007` | Lossless timestamp and destroy-response validator | Historical, one-nanosecond window/deadline violations, null deadline | Exact two-sided scheduled response only | Parametrized nanosecond carrier tests |
| `HRET-008` | Three-phase runner and final CLI sanitizer | Declared and unexpected ordinary exceptions in every phase | Exact exits `3`/`4`/`5`, no retry/restore/success bytes or traceback | State and subprocess byte-protocol tests |
| `HRET-009` | Initial target classifier | Pre-existing stale/future/sound scheduled and destroyed states | Valid no-op report; impossible or late no-mutation refusal | Parametrized provider-time tests |
| `HRET-010` | Result carrier, renderer, README | Null database deadline | JSON null and explicit no-history claim | Byte and documentation tests |
| `HRET-011` | KMS Protocol and operator documentation | Forbidden method and identity review | Exact code method surface and disjoint documented permissions | Protocol introspection and documentation assertions |
| `HRET-012` | Fixed adapters, sanitizer, and lossless renderer | Canary exception contents, provider nanoseconds, short writes/flush failures | Bounded calls, canonical v2 report, exact exits, no secret/traceback echo | Subprocess CLI/output tests |
| `HRET-013` | Exact path allowlist | Base-to-head diff and affected regression suites | No unlisted path or authority change | Mechanical path check and focused regressions |
| `HRET-014` | RFC, README, report schema | Later restore and overclaim search | Point-in-time scheduled/destroyed claim only | Documentation and report assertions |

### 13.1 Phase A verification gates

Before the version-2 live decision card, the exact RFC head must pass:

```text
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

The exact head must receive one full Phase A review against this contract.
Every demonstrated in-scope Blocker must be corrected and the affected
invariants re-reviewed before a live card is shown. Phase A remains
documentation-only.

### 13.2 Phase B verification gates

The approved exact implementation head must pass at least:

```text
.venv/bin/pytest -q kernel/tests/test_security_audit_hmac_retirement.py
.venv/bin/pytest -q kernel/tests/test_security_audit_hmac_posture.py
.venv/bin/pytest -q kernel/tests/test_google_kms_correlation_hmac.py
.venv/bin/pytest -q kernel/tests/test_security_audit_runtime.py
.venv/bin/pytest -q kernel/tests/test_postgresql_audit_migration.py
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

None inside the proposed version-2 contract. The proposal deliberately chooses:

- direct `ENABLED`/`DISABLED` to `DESTROY_SCHEDULED` with no disable step;
- exact target version `1` and active version `2`;
- exact 86,400-second KMS destruction duration;
- exact 172,800-second live-deadline admission;
- exact `S = 1 second`, `A = 5 seconds`, `E = 0 nanoseconds`, strict
  `S + A + E < 86,400 seconds`, and two-sided provider-time windows;
- external proof that ambiguous provider acceptance cannot exceed `A`; absent
  proof, no deployment invocation;
- one destroy call and no automatic retry or compensation;
- three runner phases, one final ordinary-exception sanitizer, and exact
  phase-dependent exits without exception text or tracebacks;
- lossless integer-nanosecond comparison and version-2 nine-digit reporting;
- no historical-compliance claim for a null current deadline; and
- external, separately governed IAM and deployment ownership.

Changing any of those choices after a live version-2 card requires decision
version `3`.

### 14.2 Review disposition

- **Review evidence:** owner review
  [`4945455733`](https://github.com/samovers/OFARM2/pull/316#pullrequestreview-4945455733)
  at exact version-1 head `f5f8b2f46d8b5cb9b5a1f676c9b96b5987f6a2cd`
  superseded the earlier automated zero-Blocker disposition.
- **Version-1 Blockers:** unexpected ordinary exceptions could escape the
  closed protocol; and the informal clock premise did not make the 172,800-
  second admission arithmetic sufficient. The version-1 card is withdrawn.
- **Version-2 correction:** sections 4–9 now freeze the final sanitizer, runner
  phases, exact clock/acceptance inequality, lossless nanoseconds, two-sided
  time windows, equality behavior, evidence requirements, and refusal posture.
- **Version-2 review evidence:** owner review
  [`4945993429`](https://github.com/samovers/OFARM2/pull/316#pullrequestreview-4945993429)
  at exact semantic head `6976732dc1488daed6463380b095a99faccedfa6`
  passed `HRET-005`, `HRET-007`, `HRET-008`, and `HRET-012`, confirmed the
  one-RFC Phase A boundary, and found no remaining Blocker.
- **Blockers:** zero at the exact reviewed semantic head. This
  review-record-only update changes status and disposition metadata only; it
  changes no decision semantic, invariant, authority, effect, non-effect,
  output protocol, path envelope, or Phase B gate.
- **Follow-ups:** four already-external boundaries: IAM provisioning and
  verification, a timing-evidence gate, disable-before-destroy
  organization-policy compatibility, and durable retirement receipts. Sections
  11.5 and 12 keep them outside this pull request.
- **Preferences:** the equality wording defect is corrected; no open preference
  is carried as approval authority.
- **Phase B approval:** the owner explicitly approved OFARM2 decision
  `ISSUE192-SECURITY-AUDIT-HMAC-RETIREMENT-EXECUTION-001` version `2` in the
  live task on 2026-08-16 for repository implementation in named draft pull
  request #316.
- **Deployment:** unauthorized.

With Phase B explicitly approved, only a demonstrated in-scope Blocker may
delay merge after implementation and verification. New ideas, Preferences,
and non-blocking hardening become Follow-ups and do not reopen review.

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
  API before its destruction time;
- `destroy_time` is a protobuf `Timestamp` capable of nanosecond precision;
  Python `Timestamp.ToDatetime()` is not an admissible comparison path because
  `datetime` retains only microseconds;
- the Cloud KMS method and Python client document a request timeout but do not
  promise that an ambiguous timed-out write can never be accepted later. This
  contract therefore treats no-late-acceptance as external deployment evidence,
  not an API fact supplied by the timeout argument; and
- `cloudkms.cryptoKeyVersions.destroy` is an administrative write permission
  applied at the CryptoKey or a higher resource, not an individual version.

Informative provider references observed during Phase A:

- <https://docs.cloud.google.com/kms/docs/destroy-restore>
- <https://docs.cloud.google.com/kms/docs/key-states>
- <https://docs.cloud.google.com/kms/docs/control-key-destruction>
- <https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/destroy>
- <https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions>
- <https://docs.cloud.google.com/python/docs/reference/cloudkms/latest/google.cloud.kms_v1.services.key_management_service.KeyManagementServiceClient#destroy_crypto_key_version>
- <https://googleapis.dev/python/google-api-core/latest/retry.html>
- <https://protobuf.dev/reference/python/python-generated/#timestamp>
- <https://protobuf.dev/programming-guides/json/#format-description>
- <https://docs.cloud.google.com/kms/docs/reference/permissions-and-roles>
- <https://docs.cloud.google.com/kms/docs/consistency>
