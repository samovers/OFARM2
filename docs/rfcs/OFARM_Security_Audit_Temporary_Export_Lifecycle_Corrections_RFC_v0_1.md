# OFARM Security-Audit Temporary Export Lifecycle Corrections — Decision v2

## Status

- Parent: issue #192.
- Decision: `ISSUE192-SECURITY-AUDIT-TEMPORARY-EXPORT-LIFECYCLE-001`,
  version 2.
- Reviewed base: `28cf73b859fc50bc810f53b0bdbf26848b7841aa`.
- Source implementation: merged PR #328.
- Demonstrated findings:
  https://github.com/samovers/OFARM2/pull/328#issuecomment-5406694620.
- Draft PR: https://github.com/samovers/OFARM2/pull/333.
- Initial Phase A publication head:
  `19c8c3dc0eb7f91cf91054b8e3e0dc4f34ec5be7`.
- Phase A changes only this RFC. Phase B is not authorized before the exact
  task-user approval required by `AGENTS.md`.
- This decision retains every unaffected decision-v1 invariant, exclusion,
  and trust premise. It replaces only the result-provenance, authority-time
  ordering, and database-clock authentication-deadline mechanics named below.

## 1. Problem and goal

Merged PR #328 implements the direct temporary security-audit export
lifecycle, but its exact head has two material contract violations and one
high-severity enforcement gap:

1. the nominally closed result is a public exported dataclass that any caller
   can construct without running or closing the lifecycle;
2. the signed authority-domain expiry is copied directly into PostgreSQL
   `VALID UNTIL`, so a lagging database clock can accept new authentication
   after authority expiry; and
3. the second required authority-time observation is never compared with the
   first raw observation, despite the accepted contract requiring observed
   regression to refuse.

This decision establishes a narrow correction in the same primary trust
boundary. It makes closure provenance repository-private, carries raw
authority currentness through the state machine, translates remaining
authority time into the database clock domain inside the role-creation
transaction, and proves those properties with hostile regression evidence.

The goal is not to add a new lifecycle or authority. It is to make the merged
implementation satisfy `TEL-002`, `TEL-005`, `TEL-008`, and `TEL-013` as they
were already approved.

## 2. Learning value

The correction demonstrates that one direct lifecycle can safely bridge two
clock domains without treating their absolute timestamp values as
interchangeable. It also proves that a nominal positive carrier is not an
admission authority: repository composition must obtain it only from the
closed runner path.

The work removes three concrete risks:

- arbitrary repository code presenting caller-created bytes as a
  closure-proven result;
- a lagging PostgreSQL clock extending the new-password-authentication window;
  and
- an observed authority-time rollback passing silently between required
  observations.

## 3. Non-goals

This decision does not:

- add or modify a SQL migration, relation, function, role capability, grant,
  audit contract, or catalog identity;
- change approval schemas, signatures, authority receipts, consumption
  durability, access-intent semantics, page bounds, or closure ordering;
- introduce a cryptographic admission token, serialized result, result
  validator, generic credential manager, clock service, or background state;
- implement protected output custody or allow an output layer to accept a
  caller-supplied nominal result;
- change provider, IAM, observer-root, recovery, backup, replica, clone,
  failover, tenant, HMAC, or retention boundaries;
- authorize deployment, production operation, export disclosure, issue #192
  closure, or merge without exact-head review; or
- reopen the abandoned PR #325-#327 target/epoch architecture.

Protected output custody remains a separate later trust boundary. It must call
the runner in its own trusted composition or receive the private carrier only
through a separately reviewed source-pinned composition rule. This PR creates
no output consumer and no allowlist entry for one.

## 4. Trust model

### 4.1 Protected assets

- the meaning that a returned page followed acknowledged consumption,
  credential closure, session termination, role removal, and exact normal
  structural verification;
- the signed request's remaining new-authentication authority;
- the temporary password and database route;
- the absence of the fixed export LOGIN in normal posture; and
- the original decision-v1 page, replay, and failure-secrecy bounds.

### 4.2 Trusted components and actors

- every trusted component and external prerequisite accepted by decision v1;
- the production lifecycle module and its direct `time.time_ns()` binding;
- the selected database's existing non-regressing access-clock observation;
- PostgreSQL password authentication and `VALID UNTIL` evaluation in the
  database server's clock domain;
- the architecture source snapshot and exact lifecycle surface check; and
- trusted future output composition, which is not implemented here.

### 4.3 Untrusted inputs and actors

- every decision-v1 untrusted carrier and actor;
- caller-created Python objects, including any object with fields named
  `operation_id` or `page_bytes`;
- absolute timestamp equality across authority and database clock domains;
- a raw authority-time observation that is lower than the previous raw
  observation; and
- a PostgreSQL server clock that is non-regressing but behind or ahead of the
  certified authority-time domain.

### 4.4 Excluded attacker capabilities

The decision-v1 exclusions remain unchanged. In particular, arbitrary
in-process mutation, local source substitution, compromised Python or
PostgreSQL dependencies, filesystem mutation, debugger access, process-memory
compromise, database-superuser corruption, and trusted-operator compromise are
out of scope.

Because arbitrary in-process execution is excluded, a module-private carrier
plus repository-wide static import/reference enforcement is the smallest
sufficient provenance boundary. This decision does not pretend that Python
module privacy is a cryptographic sandbox.

## 5. Authority map

| Decision | Sole authority | Forbidden substitute |
| --- | --- | --- |
| Verified approval and first raw currentness | Decision-v1 verifier result bound to the exact first fresh authority observation | parsed carriers, caller time, database time alone |
| Later raw authority currentness | Each direct fresh observation, accepted only when it is at least the immediately preceding raw authority observation | maximum with database time, caller assertion, an earlier observation reused after delay |
| Consumption | Existing acknowledged migration-4 consume commit using the second accepted raw authority observation | verifier success, returned SQL row before commit, retry inference |
| Remaining new-authentication authority | Signed request expiry minus the exact maximum of the third fresh authority observation and the role-creation transaction's immediate database high-water | signed absolute expiry copied directly to PostgreSQL, either clock alone |
| PostgreSQL role deadline | The same transaction's database high-water plus the remaining new-authentication authority | authority-domain absolute timestamp, process wall-clock conversion, caller deadline |
| Closure provenance | The sole module-private carrier construction after `_close_login(...)` returns successfully | a public constructor, imported private class, caller-created lookalike, serialized token |
| Positive output entry | A future trusted composition invoking this runner or a separately approved source-pinned private-carrier composition | accepting a caller-supplied nominal result |

No new durable authority, database column, signature, token, registry, or
alternate result constructor is introduced.

## 6. State machine and ordering

### 6.1 Current approval carrier

Verification returns one private immutable current-approval carrier containing:

- the exact `_VerifiedSecurityAuditApproval`; and
- the first raw certified authority observation `A1` used in the verifier
  maximum.

The carrier is advanced only by a private function that reads the production
time dependency directly and requires the new raw observation to be greater
than or equal to the carrier's prior raw observation. It returns a new
immutable carrier; it does not mutate or keep global clock state.

The lifecycle ordering becomes:

```text
PREFLIGHT(database H1)
  -> VERIFY(max(A1, H1))
  -> CURRENT_APPROVAL(approval, A1)
  -> ADVANCE(A2), require A2 >= A1
  -> CONSUME(approval, A2)
  -> CONSUMPTION_ACKNOWLEDGED
  -> inside role-creation transaction:
       ADVANCE(A3), require A3 >= A2
       observe immediate database H3
       derive remaining and database deadline
       create exact role
  -> LOGIN_COMMITTED
  -> EXPORT_AND_CLOSE
  -> PRIVATE_CLOSED_RESULT
```

Regression from `A1` to `A2` refuses before the consume SQL call. Regression
from `A2` to `A3` occurs after acknowledged consumption, so it produces the
fixed consumed-failure outcome and creates no role.

### 6.2 Database-domain role deadline

After acknowledged consumption, the role-creation function opens the trusted
admin transaction, verifies admin identity and store identity, and requires
the fixed role to be absent. Immediately before role SQL it:

1. takes fresh authority observation `A3` and requires `A3 >= A2`;
2. takes the immediate database high-water `H3` on that same connection;
3. computes `effective_now = max(A3, H3)`;
4. computes `remaining = signed_valid_until - effective_now`;
5. refuses with a consumed failure if `remaining <= 0` or the derived value is
   outside supported integer/datetime bounds; and
6. computes `database_role_valid_until = H3 + remaining`.

The exact derived database timestamp, not the signed authority timestamp, is
used in `CREATE ROLE ... VALID UNTIL`. All role settings and the sole
membership remain unchanged.

If the database is behind authority time, PostgreSQL receives only the true
remaining interval. If the database is ahead, `effective_now` equals the
database high-water and the deadline cannot become later than the signed
absolute expiry. Either direction fails closed.

The expected derived role shape is retained across LOGIN commit ambiguity so
the existing exact-state resolution, closure, and quarantine behavior remains
possible. A private immutable creation outcome binds the expected role and
whether commit acknowledgement was received; it creates no public status.

### 6.3 Private closed result

`ClosedSecurityAuditBreakGlassExport` is removed. One module-private
`_ClosedSecurityAuditBreakGlassExport` remains immutable and non-rendering.
It is absent from `__all__` and cannot be imported, referenced, or constructed
by any other checked-in Python module.

The sole production construction site moves into `_export_and_close(...)`.
It appears after `_close_login(...)` returns and after export completeness is
validated. `_execute(...)`, the fixed public runner, and the private test seam
may return the instance but do not construct another one.

The architecture check proves:

- exactly one private result class and no public predecessor class;
- the private class is absent from `__all__`;
- exactly one constructor call exists in the lifecycle module;
- that call follows the `_close_login(...)` call in `_export_and_close(...)`;
  and
- no other repository Python AST imports or references the private symbol.

Tests obtain a real result through the lifecycle path and never construct or
import the private type.

## 7. Invariants and acceptance criteria

- `TELC-001` — No public closed-result class or constructor exists. The sole
  private-result construction occurs after successful credential closure in
  `_export_and_close(...)`, and every other repository module is statically
  forbidden from importing or referencing that private symbol.
- `TELC-002` — The raw authority observation immediately before consumption is
  greater than or equal to the raw observation used for verification. A lower
  value refuses before consume SQL or role effects.
- `TELC-003` — The raw authority observation inside role creation is greater
  than or equal to the consumption observation. A lower value after
  acknowledged consumption yields a fixed consumed failure and no role effect.
- `TELC-004` — `VALID UNTIL` equals the role-creation transaction's database
  high-water plus `signed_expiry - max(fresh_authority, database_high_water)`.
  Non-positive or unrepresentable remaining authority refuses before role SQL.
- `TELC-005` — With a database clock behind authority time, a new password
  authentication succeeds only during the translated remaining interval and
  fails afterward even while the signed absolute timestamp remains future in
  the database clock domain.
- `TELC-006` — Existing consumption, role shape, export bounds, closure,
  quarantine, failure secrecy, and decision-v1 external prerequisites remain
  unchanged.
- `TELC-007` — The complete PR diff is exactly the five approved paths in
  section 11. No migration, output consumer, provider, deployment, or other
  authority enters the correction.

These correction invariants refine decision-v1 `TEL-002`, `TEL-005`,
`TEL-008`, `TEL-010`, `TEL-012`, and `TEL-013`. Every unaffected decision-v1
invariant remains binding.

## 8. Production-reachable negative cases

| Invariant | Supported entry and counterexample | Required outcome |
| --- | --- | --- |
| TELC-001 | Add repository code that imports or constructs `_ClosedSecurityAuditBreakGlassExport`, or re-export a public `ClosedSecurityAuditBreakGlassExport`. | Architecture/package gate fails; no merge. |
| TELC-001 | Run the supported lifecycle successfully and inspect the positive carrier. | The carrier is non-rendering and came from the sole post-closure construction site; no public constructor is available. |
| TELC-002 | Call the supported lifecycle with `A1 = T-1`, then observe `A2 = T-2` while database high-water is lower. | Fixed refusal before consume SQL; no consumption row and no LOGIN. |
| TELC-003 | Call with non-regressing `A1`, `A2`, acknowledge consumption, then observe `A3 < A2` before role creation. | Fixed consumed failure; one consumed row may exist, no LOGIN or export call. |
| TELC-004 | Call near signed expiry with `A3 >= expiry`, or with an unrepresentable derived database deadline. | Fixed consumed failure before `CREATE ROLE`; no LOGIN. |
| TELC-004, TELC-005 | Use a certified authority observation 60 seconds ahead of database high-water and a request with three seconds remaining. | Role `VALID UNTIL` is approximately database high-water plus three seconds, not the signed absolute timestamp approximately 63 database seconds ahead. Immediate new authentication may succeed; a new authentication after the remaining interval fails while the role still exists. |
| TELC-006 | Raise dependency exceptions containing carriers, routes, password, page, and derived timestamps at each corrected boundary. | Existing fixed non-sensitive public outcomes only. |
| TELC-007 | Require output custody, SQL migration, provider evidence, or another role capability to close a finding. | Stop and create a new decision or Follow-up; do not expand this PR. |

Arbitrary in-process construction through reflection is not a supported
production entry under the retained decision-v1 threat model. Repository source
that directly imports, names, or constructs the private carrier is in scope and
is mechanically rejected.

## 9. Proposed architecture and smallest change

The lifecycle module gains only three small private concepts:

1. an immutable current-approval carrier binding the verified approval to its
   latest accepted raw authority observation;
2. an immutable login-creation outcome retaining the translated expected role
   across commit ambiguity; and
3. the renamed module-private closed-result carrier.

A pure bounded helper derives the database-domain role deadline. The helper is
called only after the fresh observations are taken in the role-creation
transaction. Existing role SQL, settings, membership, export invocation,
closure, structural verification, and fixed public exceptions remain direct.

The architecture checker extends its existing lifecycle rule instead of
creating a new framework. It checks class inventory, export surface, sole
construction ordering, and repository-wide private-symbol references using the
already authenticated Python source snapshot.

The focused test module replaces the arbitrary public-construction assertion
with a real-lifecycle result assertion and adds hostile raw-regression and
lagging-database authentication cases. The canonical inventory changes only by
the mechanically collected test-count delta.

This is the minimum coherent correction because:

- merely removing a name from `__all__` leaves the public class and arbitrary
  construction intact;
- comparing only verifier maxima would hide raw authority regression behind a
  higher database value;
- copying the authority timestamp remains unsafe even after another freshness
  check; the remaining interval must be translated into PostgreSQL's domain;
  and
- a new token, validator, service, database column, or migration would add
  authority not required by the retained threat model.

## 10. Elegance audit

Sources of truth remain:

1. the signed request expiry for total remaining authentication authority;
2. direct raw authority observations for authority-domain progression;
3. the database high-water for the PostgreSQL deadline origin;
4. acknowledged consumption commit for first use; and
5. complete role absence plus structural verification for closure.

There is one deadline translation and one positive result construction. The
current-approval carrier removes correlated `approval` and `authority_now`
arguments from the corrected transitions. The login-creation outcome retains
only state already required for ambiguous-commit resolution.

Deleted compatibility surface:

- the public `ClosedSecurityAuditBreakGlassExport` name and export;
- direct authority-expiry-to-PostgreSQL conversion; and
- independent second observations with no raw ordering relation.

No new abstraction has multiple implementations or selects a dependency at
runtime. A clean rewrite is not justified; the direct state machine remains
sound outside the three demonstrated findings.

## 11. Pull request boundary

### 11.1 Primary trust boundary

The primary trust boundary is the temporary dual-approved security-audit
export lifecycle, specifically positive-result provenance and the bounded
new-authentication interval between approval verification and credential
closure.

### 11.2 Exact maximum path envelope

The draft and any authorized Phase B implementation are limited to exactly:

1. `docs/rfcs/OFARM_Security_Audit_Temporary_Export_Lifecycle_Corrections_RFC_v0_1.md`
2. `deployment/postgresql/security_audit_break_glass.py`
3. `kernel/tests/test_security_audit_break_glass.py`
4. `conformance/rewrite_architecture_check.py`
5. `conformance/review_baseline_test_inventory.json`

Phase A changes only path 1. The technical Phase B allowlist may equal or
narrow this envelope but may not add another path.

There is no cross-boundary exception in version 2. Migration 4 and temporary
credential authority were already merged by decision v1; this PR changes only
the lifecycle's enforcement of the approved contract and its necessary
mechanical conformance evidence.

Dependencies: merged PR #328 and its accepted prerequisites. No stacked PR is
required.

Reviewers must not require output custody, deployment composition, provider
evidence, a cryptographic result token, a global clock service, a new database
function, or unrelated lifecycle hardening from this PR. A demonstrated need
for any of those stops implementation for a separate decision.

Follow-ups remain the decision-v1 protected output-custody, crash-operation,
cross-slice evidence, production-prerequisite evidence, and issue-closure work.

## 12. Provisional design record

Not provisional.

The retained decision-v1 external prerequisites and invalidation conditions
remain binding. Evidence that arbitrary in-process code execution must be in
scope would invalidate module privacy and require a cryptographic or
process-isolated admission design. Evidence that PostgreSQL authenticates
against a clock other than the observed selected database domain would require
a new deadline design. Neither condition is anticipated in this correction.

## 13. Traceability and verification

| Invariant | Owning implementation | Negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| TELC-001 | private result class; `_export_and_close`; lifecycle architecture rule | public/re-exported/external private-symbol AST; real result path | no public symbol, one constructor after `_close_login`, no external references | focused source test plus rewrite architecture check |
| TELC-002 | private current-approval carrier and advance function before `_consume` | `A2 < A1` | fixed refusal, no consume row, no role | focused deterministic live lifecycle test |
| TELC-003 | currentness advance inside role-creation transaction | `A3 < A2` after consume commit | fixed consumed failure, one consume row, no role/export | focused deterministic live lifecycle test |
| TELC-004 | in-transaction deadline translation and expected-role creation outcome | expired, leading, lagging, and unrepresentable calculations | exact derived database-domain expiry; no direct signed-expiry role SQL | pure bound tests plus live catalog observation |
| TELC-005 | translated PostgreSQL `VALID UNTIL` | authority 60 seconds ahead with three seconds remaining | immediate authentication allowed and later new authentication refused before signed absolute database timestamp | focused live PostgreSQL authentication probe |
| TELC-006 | existing public exception mapping, export, closure, and quarantine paths | dependency canaries across corrected states | fixed non-rendering errors; existing lifecycle regressions pass | focused suite plus full Kernel baselines |
| TELC-007 | Git diff path check and canonical inventory | any sixth path or unregenerated count | exact five-path diff and collected inventory equality | package contract plus exact path comparison |

Required Phase B verification:

- focused unit and live PostgreSQL tests for every `TELC` invariant;
- existing security-audit approval, export, migration, lifecycle, structural,
  readiness, and observer-vocabulary regressions;
- architecture negative evidence for public result restoration, external
  private-symbol reference, duplicate construction, or construction before
  closure;
- Ruff over every changed Python path and `git diff --check`;
- mechanically regenerated canonical test inventory when collection changes;
- `python3 conformance/ofarm_pkg_contract_check.py` immediately before every
  commit;
- exact base-to-head five-path equality;
- two clean full Kernel baseline runs against the same isolated PostgreSQL
  clusters if the focused live suite passes; and
- hosted review, conformance, native amd64, native arm64, and canonical native
  index at the exact implementation head.

## 14. Open decisions and review disposition

Open decisions: none that may silently change implementation. Phase A review
may demonstrate a Blocker in this contract; any material authority, invariant,
path-envelope, or PR-binding change requires a new version.

Current review disposition:

- Blockers addressed by this proposed contract: public forgeable closed
  result; cross-clock authentication extension; unobserved raw authority-time
  regression.
- Remaining Blockers: Phase A review pending.
- Follow-ups: unchanged decision-v1 output custody, crash-operation evidence,
  final hostile cross-slice evidence, production prerequisite evidence, and
  issue #192 closure audit.
- Preferences: none.

Merge stop rule: implementation begins only after the exact later task-user
approval for this decision version and its named draft PR. Merge remains
blocked until every approved invariant passes, all exact-head hosted gates pass,
an independent exact-head review demonstrates zero Blockers, and the complete
diff equals the approved technical allowlist. New ideas and Preferences remain
Follow-ups and do not widen this PR.
