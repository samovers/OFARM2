# OFARM Security-Audit Logical Retention Execution Elapsed-Time Correction — Phase A Contract v0.2

**Status:** proposed Phase A correction in a contract-only draft pull request;
no Phase B implementation, deployment, database invocation, release, or
production authority

**Contract identity:**
`ofarm2.security-audit-logical-retention-execution-elapsed-time-correction.v0.2`

**Amended contract identity:**
`ofarm2.security-audit-logical-retention-execution.v0.1`

**Decision identity:**
`ISSUE192-SECURITY-AUDIT-LOGICAL-RETENTION-EXECUTION-001`, proposed version `2`

**Issue:** #192

**Reviewed base:** `273fafb5b18d2d6e432f755140ce6446cb616efc`

**Merged implementation:** PR #307, exact head
`0869f192c9c6cabc4c1e26b04a952d5c8b492e0e`

**Named draft pull request:** pending assignment after the contract bootstrap
commit is pushed; this field must be replaced by the stable draft-PR URL before
the version-2 live decision card is shown

**Primary trust boundary:** isolated security-audit logical-retention result
validation across timezone-offset transitions

**Phase A review-head boundary:** this RFC only

**Prospective Phase B pull-request boundary:** this RFC, the existing
deployment-layer retention validator, its focused test module, and the
mechanically regenerated test inventory only

## 1. Problem and goal

PR #307 added a supported one-shot command around the existing
database-owned security-audit retention function. The function returns
timezone-aware `observed_at` and `purge_after` values. The runner normalizes
both values to UTC for its returned result and report, but it validates their
duration using the original connection-timezone values:

```python
purge_after != observed_at + timedelta(seconds=RETENTION_SECONDS)
```

That comparison is representation-sensitive. Psycopg returns PostgreSQL
`timestamptz` values in the connection's `TimeZone` as Python `ZoneInfo`
datetimes. Python adds a `timedelta` to an aware datetime without applying a
timezone-transition adjustment. A PostgreSQL interval created only from the
`secs` field adds its microseconds component literally. A valid database result
whose exact 2,592,000-second interval crosses a daylight-saving transition can
therefore have a different local wall hour from Python's raw addition.

The current validator rejects that valid row, rolls back the transaction, and
the CLI reports refusal. This is fail-closed and cannot delete an ineligible
row, but it can make the supported retention command unavailable for valid
invocations whose thirty-day window crosses a connection-timezone offset
transition.

This correction establishes one rule:

> Validate the exact elapsed retention duration only after `observed_at` and
> `purge_after` have both been normalized to UTC.

The accepted comparison is:

```python
normalized_purge_after == (
    normalized_observed_at + timedelta(seconds=RETENTION_SECONDS)
)
```

The database remains the authority for the returned instants. The runner only
proves that the two returned instants are separated by the already accepted
literal duration.

Official behavior supporting the reproduction is documented by:

- Psycopg date/time adaptation:
  `https://www.psycopg.org/psycopg3/docs/basic/adapt.html#date-time-types-adaptation`;
- Python 3.12 datetime arithmetic:
  `https://docs.python.org/3.12/library/datetime.html#datetime-objects`; and
- PostgreSQL 17 interval arithmetic:
  `https://www.postgresql.org/docs/17/functions-datetime.html`.

## 2. Learning value

This correction proves that result validation follows elapsed instants rather
than connection-local wall-clock representation. It removes a demonstrated
production-reachable false refusal while preserving all destructive-policy,
transaction, retry, output, and authorization boundaries from version 1.

## 3. Review-finding disposition

The post-merge review contained two claimed Blockers.

### 3.1 Approval-provenance claim — not reproduced

The task platform directly preserves the opposite role sequence from the
review's claim:

- task: `codex-task:019ff570-c253-7d02-bbda-1ad8f4143f00`;
- complete assistant-authored live card: `item-75`; and
- later task-user approval message: `item-76`.

The entire visible text of `item-76` is:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-LOGICAL-RETENTION-EXECUTION-001 version 1.
```

The version-1 approval therefore satisfied the repository workflow. PR #307
does not require a governance revert or retrospective ratification. This
version-2 decision is prospective authority for the elapsed-time correction
only. It does not reinterpret, transfer, or replay version-1 approval.

### 3.2 Timezone-transition false refusal — reproduced Blocker

The finding reproduces at merged commit `273fafb5` with the supported validator
and a real IANA timezone:

```text
timezone: Europe/Belgrade
observed_at: 2026-03-15T12:00:00+01:00
database purge_after: 2026-04-14T13:00:00+02:00
elapsed seconds: 2592000
Python raw addition: 2026-04-14T12:00:00+02:00
current result: ValueError("retention result values are invalid")
```

**Classification:** Blocker.

**Violated invariant:** version-1 `RET-005` requires a valid result consistent
with `RETENTION_SECONDS` to be accepted and committed.

**Supported production entry point:**
`python -m deployment.postgresql.run_security_audit_retention` with a valid
retention DSN whose PostgreSQL connection `TimeZone` observes an offset change.

**In-scope actor and preconditions:** an authorized retention operator invokes
the supported command; the database function returns one otherwise valid row;
the exact duration crosses an offset transition.

**Material consequence:** the runner rolls back a valid logical-retention
batch and reports exit `1`, preventing the supported operation from making
progress for affected instants.

**Smallest fix:** compare the already normalized UTC values and add one
`ZoneInfo` regression. No revert, migration, route change, or timezone pin is
needed.

## 4. Non-goals

- Reverting merge commit `273fafb5` or rewriting PR #307 history.
- Reusing or retroactively changing version-1 approval.
- Deploying, invoking, releasing, or promoting the retention command.
- Changing the database function, migration bytes, relation constraints,
  roles, grants, provisioning, retention duration, cutoff, victim selection,
  ordering, cleanup, or 1,024-row ceiling.
- Pinning the connection `TimeZone` to UTC or changing any code-owned startup
  option, libpq route behavior, DSN semantics, or output representation.
- Changing the fixed SQL, transaction isolation, state machine, explicit
  commit/rollback boundary, ambiguity classification, or no-retry rule.
- Changing CLI arguments, environment variables, exit codes, stdout, stderr,
  or operator documentation.
- Adding a scheduler, readiness coupling, reconciliation route, reader/export
  authority, store-loss operation, key custody, physical-erasure claim, or
  issue #176 work.
- Generalizing datetime validation elsewhere in the repository.

## 5. Trust model

### 5.1 Protected assets

- Availability of valid logical-retention execution.
- Rejection of malformed or duration-inconsistent database results.
- The database-owned cutoff, victim set, deletion ceiling, cleanup, and atomic
  `AUDIT_RETENTION` event.
- Honest commit and terminal reporting outcomes.
- Isolation from tenant storage, application pools, and alternate audit roles.

### 5.2 Trusted components

- The accepted security-audit migration and zero-argument retention function.
- PostgreSQL `timestamptz` and literal-seconds interval semantics.
- The existing literal `RETENTION_SECONDS` authority.
- Psycopg date/time adaptation and Python's UTC conversion.
- The deployment-layer runner after the version-2 correction.
- The IANA timezone database supplied through Python `zoneinfo`.

### 5.3 Untrusted or variable inputs

- The connection's configured timezone and its offset on either returned
  instant.
- Every returned result shape and value until validated.
- Caller-supplied DSN text and ambient libpq route configuration under the
  unchanged version-1 threat model.
- Network, database, and output-channel availability.

### 5.4 Excluded attacker capabilities

Arbitrary in-process mutation, local source substitution, compromised
dependencies, filesystem mutation, malicious timezone-data replacement,
database-owner or superuser compromise, operating-system compromise, and
operator credential compromise remain outside this correction's threat model.
Their status is unchanged from version 1.

## 6. Authority map

| Decision | Sole authority after correction |
| --- | --- |
| Returned observed and purge instants | Existing PostgreSQL function |
| Exact elapsed duration | Existing `RETENTION_SECONDS` constant |
| Conversion of aware values to a common instant representation | Existing `_utc_timestamp()` helper |
| Duration-consistency acceptance | `_validated_result()` comparing normalized UTC values |
| Cutoff, victims, ordering, ceiling, cleanup, identity, and event | Existing PostgreSQL function |
| Transaction finality | Normal return from explicit `Connection.commit()` |
| Process protocol | Existing fixed CLI and renderer |
| Prospective repository authority | Exact later same-task approval of the unique version-2 live card |

There is no fallback comparison. Raw connection-timezone arithmetic is removed
from duration acceptance rather than retained as a second accepted rule.

## 7. State machine and ordering

The version-1 transaction states remain unchanged:

```text
NOT_SUBMITTED
    -> SUBMITTED
    -> RESULT_OBSERVED
    -> COMMITTING
    -> ACKNOWLEDGED
    -> REPORTED
```

Only the validation ordering inside `SUBMITTED` is clarified:

1. Fetch exactly one five-field result and prove no second row exists.
2. Require each timestamp to be a Python `datetime` with a defined UTC offset.
3. Normalize `cutoff`, `observed_at`, and `purge_after` to UTC exactly once.
4. Validate count and event identity under the unchanged version-1 rules.
5. Compare normalized `purge_after` with normalized `observed_at` plus
   `timedelta(seconds=RETENTION_SECONDS)`.
6. Refuse and explicitly roll back on any invalid value.
7. Preserve the normalized values in the immutable result.
8. Pre-render, commit, close, and report under the unchanged version-1 state
   and failure protocol.

No additional SQL, transaction, connection, retry, or output operation is
introduced.

## 8. Invariants and acceptance criteria

- **RET-DST-001 — Representation-independent acceptance.** Two aware values
  representing instants exactly `RETENTION_SECONDS` apart are accepted
  regardless of a connection-timezone offset change between them.
- **RET-DST-002 — Exact elapsed duration.** Acceptance compares normalized UTC
  instants; a value one microsecond early or late is refused.
- **RET-DST-003 — Existing type closure.** Naive timestamps, non-datetime
  values, invalid counts, nil event IDs, missing rows, and duplicate rows
  remain refused before commit.
- **RET-DST-004 — Transaction protocol unchanged.** One connection, one fixed
  SQL submission, explicit rollback on invalid result, explicit commit, every
  controlled commit exception unknown, and no retry remain exact.
- **RET-DST-005 — Output protocol unchanged.** Accepted values remain UTC,
  six-microsecond, sorted compact ASCII JSON; no new field or diagnostic is
  exposed.
- **RET-DST-006 — No policy transfer.** The caller still cannot choose cutoff,
  victims, duration, ordering, batch size, event identity, or cleanup.
- **RET-DST-007 — Pre-deployment only.** Repository correction creates no
  deployment, invocation, production, release, scheduler, or security-waiver
  authority.
- **RET-DST-008 — Historical evidence preserved.** Version-1 RFC and approval
  evidence are not edited, withdrawn, or repurposed; version 2 binds only its
  new named draft PR.

## 9. Production-reachable negative cases

| Invariant | Counterexample and required result |
| --- | --- |
| `RET-DST-001` | With connection `TimeZone=Europe/Belgrade`, the function returns `2026-03-15T12:00:00+01:00` and `2026-04-14T13:00:00+02:00`; the exact 2,592,000-second result is accepted. |
| `RET-DST-002` | Move the normalized purge instant by one microsecond; validation refuses, rolls back, and never commits. |
| `RET-DST-003` | Return a naive observed timestamp or a second row; the existing refusal path remains exact. |
| `RET-DST-004` | Make explicit `commit()` raise; the existing unknown outcome and no-retry behavior remains unchanged. |
| `RET-DST-005` | Accept the transition-spanning row; output uses the two normalized UTC instants and the existing exact byte shape. |
| `RET-DST-006` | Supply CLI arguments or a caller-selected duration; the unchanged CLI refuses before connection and no new parameter exists. |
| `RET-DST-007` | Merge the repository fix without deployment authority; no database command is run and no deployment state changes. |
| `RET-DST-008` | Attempt to apply version-2 approval to PR #307 or edit its merged RFC record; execution stops because the version and named PR do not match. |

The focused regression uses the runner's supported constructor-bound
connection-factory seam and real `ZoneInfo`, not private-field mutation. Live
PostgreSQL evidence from the full suite remains useful but is not required to
manufacture a clock date at the one-statement result seam.

## 10. Proposed architecture and smallest change

The production edit changes only the final duration operand inside
`_validated_result()`:

```python
or normalized_purge_after
!= normalized_observed_at + timedelta(seconds=RETENTION_SECONDS)
```

The focused test module imports `ZoneInfo`, constructs one spring-transition
case, routes it through `SecurityAuditRetentionRunner`, and proves:

- the exact elapsed duration is accepted and committed;
- the returned values are normalized to UTC;
- the existing canonical report is derived from normalized instants; and
- no rollback, second SQL submission, or second connection occurs.

One new collected test node requires mechanical inventory regeneration. The
existing fixed-offset test remains because it independently proves rendering
and normalization without an offset transition.

Pinning the connection timezone to UTC would hide this one representation but
would change connection options and acceptability of deployment routes. A
generic datetime abstraction would add a second authority for one comparison.
Comparing the already normalized values is the minimum coherent correction.

## 11. Elegance audit

- Elapsed-duration authorities: one, `RETENTION_SECONDS`.
- Instant-normalization paths: one, `_utc_timestamp()`.
- Duration comparisons: one, after UTC normalization.
- New production types, helpers, abstractions, or configuration: zero.
- New connection, SQL, transaction, retry, or output paths: zero.
- New collected regression nodes: one.
- Obsolete behavior removed: the raw connection-timezone duration comparison.

A clean rewrite is unnecessary. The existing validator already computes the
correct normalized operands and merely uses the wrong local variables in its
comparison.

## 12. Pull request boundary

### 12.1 Phase A bootstrap boundary

Before approval, the draft PR may change only:

```text
docs/rfcs/OFARM_Security_Audit_Logical_Retention_Execution_Elapsed_Time_Correction_RFC_v0_2.md
```

It may update that RFC only to bind the stable draft-PR URL and record
meaning-preserving exact-head review disposition before the live card.

### 12.2 Exact prospective Phase B allowlist

After valid version-2 approval, the same named draft PR may change exactly:

```text
docs/rfcs/OFARM_Security_Audit_Logical_Retention_Execution_Elapsed_Time_Correction_RFC_v0_2.md
deployment/postgresql/security_audit_retention.py
kernel/tests/test_security_audit_retention.py
conformance/review_baseline_test_inventory.json
```

The RFC may then change only to mark version-2 approval, append compact
AI-attested approval evidence, and record meaning-preserving implementation or
verification disposition. The inventory change is mechanical and must contain
the complete canonical collected test set.

Every other path is forbidden, including:

```text
docs/rfcs/OFARM_Security_Audit_Logical_Retention_Execution_RFC_v0_1.md
deployment/postgresql/run_security_audit_retention.py
deployment/postgresql/README.md
deployment/postgresql/audit_contract.py
security_audit/migrations/*
kernel production/runtime modules
AGENTS.md
TASK_PROMPT.md
```

### 12.3 Dependencies and reviewer non-requirements

- Reviewed base is merge commit `273fafb5b18d2d6e432f755140ce6446cb616efc`.
- PR #307 and its version-1 contract remain merged dependencies.
- There is no stacked pull request.
- Issue #192 remains open; this correction does not close it.
- PRs #305 and #306 remain parked and untouched.

Reviewers must not require a revert of PR #307, a migration, connection
timezone pin, route change, CLI change, scheduler, deployment action, or an
adjacent #192 operation from this correction.

### 12.4 Stop and reapproval conditions

Stop before editing another path or changing:

- database policy or accepted migration bytes;
- connection, transaction, retry, commit, or output semantics;
- CLI or operator protocol;
- another trust boundary or issue;
- the decision identity, version, named PR, effect, non-effect, invariant, or
  path envelope; or
- any deployment, invocation, release, production, or security-waiver state.

Those changes require a separate prerequisite, follow-up, or new decision
version. Closing the named PR unmerged expires version-2 authority.

## 13. Provisional design record

The technical correction is **not provisional**. Elapsed-time validation must
remain representation-independent.

The same-task AI-assisted approval mechanism is provisional repository-
development authority only. It grants no deployment or production authority
and must be replaced by an independently human-controlled and independently
verifiable approval or signing system before deployment.

Evidence requiring technical redesign would be proof that the database
duration is calendar-relative rather than literal seconds, or that Psycopg can
return the two fields under different instant semantics. The reviewed SQL,
constants, official documentation, and deterministic reproduction show the
opposite. If such evidence appears, stop rather than widening this PR.

## 14. Traceability and verification

| Invariant | Owning code | Negative evidence | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `RET-DST-001` | `_validated_result()` normalized comparison | Transition-spanning `ZoneInfo` values rejected by current code | Same row accepted and committed | Focused runner regression |
| `RET-DST-002` | `_validated_result()` | Purge instant shifted by one microsecond | Exact duration only | Existing invalid-result test plus focused regression |
| `RET-DST-003` | `_utc_timestamp()` and existing shape checks | Naive, malformed, missing, or duplicate result | Existing refusal suite unchanged | Focused module |
| `RET-DST-004` | Existing runner state machine | Commit exception or invalid result | Existing rollback/unknown/no-retry tests | Focused module and architecture check |
| `RET-DST-005` | Existing renderer | Local-time representation leaks into output | Exact normalized UTC report | Focused transition regression |
| `RET-DST-006` | Existing fixed CLI and SQL | Caller policy input | Existing argument and fixed-query tests | Focused module |
| `RET-DST-007` | PR boundary and workflow | Deployment or database invocation claim | Repository-only diff | Exact path checks |
| `RET-DST-008` | This RFC and live card | Version/PR replay | Stable version-2 card and later user approval | Task-evidence and named-PR recheck |

The package contract check must pass before every commit. The exact Phase A
head must pass:

```text
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
```

The exact final Phase B head must pass:

```text
.review-venv/bin/python -m pytest -q kernel/tests/test_security_audit_retention.py
.review-venv/bin/python -m pytest -q kernel/tests/test_postgresql_audit_migration.py -k retention
.review-venv/bin/python -m pytest -q kernel/tests/test_rewrite_architecture.py
.review-venv/bin/python -m ruff check deployment/postgresql/security_audit_retention.py kernel/tests/test_security_audit_retention.py
.review-venv/bin/python conformance/ofarm_pkg_contract_check.py
git diff --check
```

The final exact head must also pass the complete GitHub conformance and review
workflows. PostgreSQL-backed local skips remain skips and are never presented
as passing evidence. Before merge, mechanically compare every changed path
with section 12.2, prove section 12.2 is a subset of the live card's maximum
path envelope, post the required compact scope report, and recheck exact-head
review, live task evidence, approval binding, and absence of later
cancellation.

## 15. Open decisions and review disposition

- **Blockers:** the reproduced timezone-transition false refusal; Phase B is
  blocked pending a complete named draft PR, unique version-2 live card, and
  exact later task-user approval.
- **Follow-ups:** none.
- **Preferences:** none.
- **Open material decisions:** none.

The invalid-approval-provenance claim is rejected on direct task-role evidence
and is not a Blocker. The reproduced elapsed-time defect is the only technical
Blocker owned by this correction.

## 16. Merge stop rule

Once `RET-DST-001` through `RET-DST-008` pass, every exact-head gate is green,
and no demonstrated in-scope Blocker remains, the approved workflow permits
merging the named version-2 PR. New ideas and adjacent hardening remain outside
this boundary and do not reopen review.

## 17. Phase A approval boundary

This RFC grants no Phase B authority by authorship, commit, push, review, or
draft-PR creation. Before implementation:

1. create the one draft PR containing this complete RFC;
2. replace the pending named-PR field with its stable URL;
3. review the exact contract head;
4. present one complete live card for decision
   `ISSUE192-SECURITY-AUDIT-LOGICAL-RETENTION-EXECUTION-001`, version `2`,
   naming that draft PR and the maximum four-path envelope; and
5. wait for a later task-user message whose entire visible text is exactly:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-LOGICAL-RETENTION-EXECUTION-001 version 2.
```

No current message, attachment, review text, GitHub activity, AI message, tool
output, version-1 approval, or generic instruction supplies version-2
approval. Phase B remains stopped until that exact later user message is
directly retrievable in this task after the unique complete card.
