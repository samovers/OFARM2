# OFARM Security-Audit Temporary Export Lifecycle Corrections — Decision v5

## Status

- Parent: issue #192.
- Decision: `ISSUE192-SECURITY-AUDIT-TEMPORARY-EXPORT-LIFECYCLE-001`,
  version 5.
- Reviewed base: `28cf73b859fc50bc810f53b0bdbf26848b7841aa`.
- Source implementation: merged PR #328.
- Demonstrated findings:
  https://github.com/samovers/OFARM2/pull/328#issuecomment-5406694620.
- Draft PR: https://github.com/samovers/OFARM2/pull/333.
- Initial Phase A publication head:
  `19c8c3dc0eb7f91cf91054b8e3e0dc4f34ec5be7`.
- Superseded decision-v2 review head:
  `23f441acd31262f41182c274f1b6b0fee94c7a96`.
- Decision-v2 ordering Blocker:
  https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5016552073.
- Superseded decision-v3 head:
  `556f65d3c513c3be353af1149304fcac1675c43b`.
- Decision-v3 whole-card review:
  https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5018236211.
- Decision-v3 differential-clock Blocker:
  https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5018366345.
- Superseded decision-v4 head:
  `761cc164d0e3cdc38b9c0398c2b304bb967c4c62`.
- Decision-v4 PostgreSQL authentication-semantics Blockers:
  https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5018892448.
- Phase A changes only this RFC. Phase B is not authorized before the exact
  task-user approval required by `AGENTS.md`.
- This version supersedes decision v4. Version 4 correctly bounded later
  authority-minus-database divergence, but it treated equality at PostgreSQL
  `VALID UNTIL` as expired and treated password-verifier retrieval as the end
  of SCRAM authentication. PostgreSQL 17 accepts equality and does not recheck
  expiry after the multi-message exchange. Version 5 retains the corrected
  `H3 -> A3` order and differential-growth reserve, subtracts one PostgreSQL
  timestamp quantum, and reserves the independently bounded authority-clock
  advance of a complete password-authentication exchange. Version 4 was never
  approved and its task-user card is withdrawn.
- Version 3 had already superseded version 2, whose `A3 -> H3` order could
  double-count inter-observation delay. Every predecessor card remains
  withdrawn.
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

Earlier correction drafts then exposed two further deadline defects:

4. PostgreSQL 17 expires a password only when `VALID UNTIL < database_now`, so
   equality remains admissible; and
5. PostgreSQL retrieves and checks the verifier before SCRAM, then performs no
   second expiry check when the exchange succeeds.

This decision establishes a narrow correction in the same primary trust
boundary. It makes closure provenance repository-private, carries raw
authority currentness through the state machine, observes the database
deadline origin before the final authority observation, translates the then
remaining authority time into the database clock domain, and subtracts three
source-fixed values: future differential-clock growth, complete-authentication
authority advance, and one PostgreSQL timestamp quantum. It proves those
properties with hostile regression, observation-delay, forward-step,
relative-rate, exact-equality, and delayed-SCRAM evidence.

The goal is not to add a new lifecycle or authority. It is to make the merged
implementation satisfy `TEL-002`, `TEL-005`, `TEL-008`, and `TEL-013` as they
were already approved.

## 2. Learning value

The correction demonstrates that one direct lifecycle can safely bridge the
authority clock, PostgreSQL wall clock, and PostgreSQL authentication timer
without treating their timestamp values or rates as interchangeable. It also
proves that a nominal positive carrier is not an admission authority:
repository composition must obtain it only from the closed runner path.

The work removes five concrete risks:

- arbitrary repository code presenting caller-created bytes as a
  closure-proven result;
- a lagging PostgreSQL clock extending the new-password-authentication window;
- an observed authority-time rollback passing silently between required
  observations;
- a later authority-clock step or faster authority-clock progression leaving
  PostgreSQL willing to retrieve the verifier after signed authority expiry;
  and
- equality at `VALID UNTIL` or an in-flight SCRAM exchange completing at or
  after signed authority expiry.

## 3. Non-goals

This decision does not:

- add or modify a SQL migration, relation, function, role capability, grant,
  audit contract, or catalog identity;
- change approval schemas, signatures, authority receipts, consumption
  durability, access-intent semantics, page bounds, or closure ordering;
- introduce a cryptographic admission token, serialized result, result
  validator, generic credential manager, clock synchronizer, evidence
  collector, caller-selected runtime configuration value, or background
  state;
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

The clock and complete-authentication evidence is also a deployment
prerequisite, not a new runtime authority. This PR fixes every reserve in
source and does not accept a caller, environment, file, database, or network
value for any reserve. Until a later deployment decision verifies current
independent evidence for the exact authority host, selected PostgreSQL route,
server build, authentication configuration, and timer topology, production
composition remains ineligible and unavailable.

## 4. Trust model

### 4.1 Protected assets

- the meaning that a returned page followed acknowledged consumption,
  credential closure, session termination, role removal, and exact normal
  structural verification;
- the signed request's remaining new-authentication authority;
- the guarantee that, under the exact deployment evidence premises, every
  successful temporary password authentication reaches PostgreSQL's
  `AuthenticationOk` state strictly before signed authority expires;
- the temporary password and database route;
- the absence of the fixed export LOGIN in normal posture; and
- the original decision-v1 page, replay, and failure-secrecy bounds.

### 4.2 Trusted components and actors

- every trusted component and external prerequisite accepted by decision v1;
- the production lifecycle module and its direct `time.time_ns()` binding;
- the selected database's existing non-regressing access-clock observation,
  accepted only when `clock_regressed` is exactly false so its returned value
  is the observing connection's live PostgreSQL `clock_timestamp()` rather
  than a stored high-water;
- PostgreSQL 17 password authentication, its strict
  `VALID UNTIL < database_now` expiry comparison, and its server-side
  `authentication_timeout` covering verifier retrieval through the complete
  SCRAM exchange and `AuthenticationOk` result;
- the source-fixed
  `_MAX_AUTHORITY_DATABASE_DIVERGENCE_GROWTH_US = 1_000_000` reserve;
- the source-fixed
  `_MAX_PASSWORD_AUTHORITY_ADVANCE_US = 61_000_000` complete-authentication
  reserve and `_POSTGRES_TIMESTAMP_QUANTUM_US = 1` equality guard;
- before any production composition, current independently controlled evidence
  that, for the exact lifecycle authority host and selected PostgreSQL route,
  authority-minus-database divergence can grow by at most 1,000,000
  microseconds over every interval no longer than the accepted 300-second
  approval lifetime, and that the exact server's `authentication_timeout` is
  no greater than 60 seconds while authority time can advance by at most
  61,000,000 microseconds from password-verifier retrieval through
  `AuthenticationOk` or timeout;
- the architecture source snapshot and exact lifecycle surface check; and
- trusted future output composition, which is not implemented here.

### 4.3 Untrusted inputs and actors

- every decision-v1 untrusted carrier and actor;
- caller-created Python objects, including any object with fields named
  `operation_id` or `page_bytes`;
- absolute timestamp equality across authority and database clock domains;
- caller-, environment-, file-, database-, or network-selected clock bounds;
- KMS/database timing evidence, an NTP-enabled label, or another clock pair
  presented as evidence for this lifecycle's authority-host/database bound;
- stale, ambiguous, topology-mismatched, or non-independent differential-clock
  evidence;
- a client that retrieves the verifier immediately before the role deadline
  and then delays its SCRAM response;
- stale, ambiguous, build-mismatched, hook-mismatched, or route-mismatched
  `authentication_timeout` and authority-advance evidence;
- an authority-clock forward step or authority-over-database relative-rate
  change beyond the fixed reserve;
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

The source-fixed reserves are not an assertion that current deployment
evidence already exists. They are the maximum admissible bounds for a future
deployment. Evidence that cannot prove the exact clock-pair ceiling, the
60-second PostgreSQL authentication-timeout ceiling, and the 61-second
authority-advance ceiling keeps production composition unavailable; it does
not widen a constant or permit a fallback. The one-second KMS/database premise
elsewhere in the repository is a numeric security-audit precedent only and
cannot supply these distinct authority-host/database/timer premises.

## 5. Authority map

| Decision | Sole authority | Forbidden substitute |
| --- | --- | --- |
| Verified approval and first raw currentness | Decision-v1 verifier result bound to the exact first fresh authority observation | parsed carriers, caller time, database time alone |
| Later raw authority currentness | Each direct fresh observation, accepted only when it is at least the immediately preceding raw authority observation | maximum with database time, caller assertion, an earlier observation reused after delay |
| Consumption | Existing acknowledged migration-4 consume commit using the second accepted raw authority observation | verifier success, returned SQL row before commit, retry inference |
| Differential-clock growth reserve `U` | Source-fixed 1,000,000 microseconds, admissible for production only with current independent evidence for the exact authority host and PostgreSQL route over every interval up to 300 seconds | caller/configured value, missing or stale evidence, another host/route, KMS/database evidence, an NTP label alone |
| Complete-authentication reserve `T` | Source-fixed 61,000,000 microseconds of maximum authority-clock advance from verifier retrieval through `AuthenticationOk` or timeout, admissible only when current independent evidence binds the exact PostgreSQL build, route, hooks, timer topology, and `authentication_timeout <= 60 seconds` | client or configured reserve, connect timeout, statement timeout, an unverified/default setting, another server or route |
| PostgreSQL timestamp quantum `Q` | Source-fixed 1 microsecond matching PostgreSQL 17 `timestamptz` precision and compensating for its strict `VALID UNTIL < database_now` expiry comparison | zero, caller precision, host-language datetime assumption, changing the comparison premise without source evidence |
| Live database deadline origin `H3` | Same-connection `_observe_nonregressing_access_clock()` result accepted only when `clock_regressed` is exactly false, proving the returned value is that connection's live `clock_timestamp()` | cached preflight `H1`, stored sequence high-water, direct sequence read, a regressed-clock result, later database observation |
| Remaining complete-authentication authority | `raw_remaining = signed_expiry - max(A3, H3)` followed by `safe_remaining = raw_remaining - U - T - Q` | raw remaining without every reserve, signed absolute expiry copied directly to PostgreSQL, either clock alone |
| PostgreSQL role deadline | `H3 + safe_remaining`, derived after `H3`, then `A3`, and retained unchanged for every exact-state comparison | authority-domain timestamp chosen directly, caller deadline, recomputation on commit ambiguity, a later database observation |
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
       observe accepted live database H3, require clock_regressed == false
       ADVANCE(A3), require A3 >= A2
       derive raw remaining
       subtract fixed differential-growth reserve U,
         complete-authentication reserve T, and timestamp quantum Q
       require safe remaining > 0
       derive database deadline
       create exact role
  -> LOGIN_COMMITTED
  -> EXPORT_AND_CLOSE
  -> PRIVATE_CLOSED_RESULT
```

Regression from `A1` to `A2` refuses before the consume SQL call. Regression
from `A2` to `A3` occurs after acknowledged consumption, so it produces the
fixed consumed-failure outcome and creates no role.

### 6.2 Database-domain role deadline and authentication-completion reserves

After acknowledged consumption, the role-creation function opens the trusted
admin transaction, verifies admin identity and store identity, and requires
the fixed role to be absent. Immediately before role SQL it:

1. calls the existing non-regressing access-clock helper on that same
   connection and accepts `H3` only when `clock_regressed` is exactly false,
   making `H3` the live PostgreSQL `clock_timestamp()` used by authentication;
2. then takes fresh authority observation `A3` and requires `A3 >= A2`;
3. computes `effective_now = max(A3, H3)`;
4. computes `raw_remaining = signed_valid_until - effective_now`;
5. computes `safe_remaining = raw_remaining - U - T - Q`, where source-fixed
   `U = 1_000_000` microseconds, `T = 61_000_000` microseconds, and
   `Q = 1` microsecond;
6. refuses with a consumed failure if `safe_remaining <= 0` or any source or
   derived value is outside supported integer/datetime bounds; and
7. computes `database_role_valid_until = H3 + safe_remaining`.

The `H3 -> A3 -> derive -> role SQL` order is authoritative. No database-time
observation may be substituted after `A3`. Time spent between `H3` and `A3`,
or between derivation and role creation, consumes the already bounded database
interval rather than being added to it. A hostile lagging-database test
deliberately delays between `H3` and `A3`, advances both simulated clocks, and
proves that a delay of `d` moves the absolute database cutoff earlier by `d`
and shortens the interval measured from role creation by `2d`. Reversing the
observations to `A3 -> H3` is a contract failure even when both raw
observations are individually non-regressing.

The rejected order still has the decision-v3 one-second-delay counterexample.
If `A3 = 60` is sampled first, the database is at `0`, signed expiry is `63`,
and `H3 = 1` is sampled one second later, omitting the corrected order and
reserves produces database deadline `4`; authority expires at real time `3`, but
database authentication can remain open until real time `4`. With the required
order and current fixed reserves, `H3 = 0` is sampled first, the authority
clock advances to `A3 = 61`, signed expiry is `125`, `U = 1`, `T = 61`, and
`Q = 0.000001` seconds. The database deadline is
`0 + (125 - 61 - 1 - 61 - 0.000001) = 1.999999`. At role creation the
database is already at `1`, leaving `0.999999` seconds rather than the
zero-delay `2.999999` seconds. Delay still moves the absolute cutoff earlier
by one second and shortens the interval from role creation by two seconds.

The post-`A3` bound is exact. Define the observed conservative divergence as
`G3 = A3 - H3`. Because the accepted database clock is nonregressing and `H3`
precedes `A3`, this is no smaller than the actual authority-minus-database
divergence at `A3`. For every later instant `t` through authority expiry,
verifier retrieval, or the latest possible password-authentication result,
deployment eligibility must independently prove:

```text
(A(t) - H(t)) - G3 <= U
U = 1_000_000 microseconds
```

This bound includes authority-clock forward steps, authority-over-database
rate or slew, and cross-host synchronization uncertainty. Let `E` be signed
authority expiry. The derived deadline is:

```text
D = H3 + E - max(A3, H3) - U - T - Q
```

PostgreSQL 17 returns the stored verifier whenever its lookup time `s` has
`H(s) <= D`; it treats the password as expired only when `D < H(s)`. The
differential bound gives `A(s) - H(s) <= G3 + U`, so every admitted lookup
satisfies:

```text
A(s) <= H(s) + G3 + U
     <= D + G3 + U
     <= E - T - Q
```

For every password exchange on the exact selected route, deployment
eligibility must also prove that PostgreSQL's still-active authentication
timer either refuses the exchange or reaches `AuthenticationOk` at instant `c`
with:

```text
A(c) - A(s) <= T
T = 61_000_000 microseconds
```

Therefore every successful exchange has `A(c) <= E - Q < E`. Equality at the
role deadline can still retrieve the verifier, but the one-microsecond `Q`
guard makes completion strictly pre-expiry at PostgreSQL's finite timestamp
precision. At authority expiry, the same differential bound gives
`H(t) >= E - A3 + H3 - U > D`, so a new verifier lookup refuses as well.

`U` is a maximum admissible reserve, not a measurement claim. Its one-second
ceiling is the numeric ceiling used by another security-audit cross-clock
decision, is one three-hundredth of the accepted maximum approval lifetime,
and leaves no path to silently accept a larger operational skew. Evidence for
that other clock pair does not transfer here.

`T` is also a maximum admissible authority-domain bound, not a claim that the
documented PostgreSQL default is sufficient by itself. It admits only an exact
server whose effective `authentication_timeout` is at most 60 seconds and for
which independent evidence bounds authority-clock advance by at most 61
seconds from verifier retrieval through `AuthenticationOk` or timeout. This
extra second must cover timer granularity, scheduling, authority slew, and
common-mode forward steps that the authority/database divergence bound alone
cannot see. `connect_timeout`, `statement_timeout`, a default-value assertion,
and a measurement against another server do not satisfy this premise.

`Q` is exactly one PostgreSQL 17 `timestamptz` microsecond. It exists because
PostgreSQL accepts equality at `VALID UNTIL`; it is not a configurable safety
margin.

The design evidence is pinned to upstream PostgreSQL 17 source commit
`a4eb938b33557193d90c1b396afd2c274e28b07e`: `crypt.c` performs the strict
expiry comparison, `auth.c` retrieves the verifier before `CheckSASLAuth`, and
`postinit.c` enables `AuthenticationTimeout` before `ClientAuthentication` and
disables it only after that function returns. PostgreSQL 17 documentation
defines `timestamptz` resolution as one microsecond and
`authentication_timeout` as the maximum time allowed to complete client
authentication. These references establish the Phase A model; they do not
replace the future evidence binding the exact deployed build and configuration.

Future deployment evidence must be independently controlled and verifiable.
It binds the exact lifecycle authority host; PostgreSQL 17 build, system, HBA
route, loaded authentication hooks, effective `authentication_timeout`, and
timer source; clock and virtualization topology; measurement error;
observation interval; issuance time; and evidence expiry. It must conclude
both `U <= 1_000_000` microseconds over every interval up to 300 seconds and
`A(c) - A(s) <= 61_000_000` microseconds for every password exchange admitted
by a server timeout no greater than 60 seconds. Missing fields, expired
evidence, server upgrade, hook or configuration change, topology change,
ambiguous measurement error, or a larger result makes deployment ineligible.
This PR adds no evidence loader or runtime bypass; its absence is enforced by
the five-path boundary and the no-production-caller architecture rule.

The exact derived database timestamp, not the signed authority timestamp, is
used in `CREATE ROLE ... VALID UNTIL`. All role settings and the sole
membership remain unchanged.

If the database is behind authority time, PostgreSQL receives the translated
raw interval minus `U + T + Q`. If the database is ahead, `effective_now`
equals `H3` and the derived deadline is exactly
`signed_expiry - U - T - Q`; numeric equality with the unreserved signed
expiry is neither required nor a valid architecture test. In both branches,
role SQL must receive the value flowing from the one derivation helper.
Observation delay and admissible differential growth are reserved rather than
added. Greater growth or complete-authentication advance invalidates
deployment eligibility instead of widening a source constant.

This security bound does not guarantee availability. Because consumption is
already acknowledged, a short-lived request or slow transaction may be spent
before `raw_remaining > U + T + Q` leaves a usable authentication window.
PostgreSQL's authentication timeout bounds only password authentication, not
role creation, connection setup before its server timer, export execution, or
output delivery. Phase B must demonstrate the consumed fail-closed outcome for
an exhausted combined reserve and record prompt use of the accepted maximum
300-second request lifetime as operational guidance.

The expected derived role shape is retained across LOGIN commit ambiguity so
the existing exact-state resolution, closure, and quarantine behavior remains
possible. `_create_login(...)` constructs and returns one private immutable
creation outcome binding the exact derived expected role and whether commit
acknowledgement was received. A pre-commit failure still raises consumed
failure and returns no outcome. A commit exception is absorbed into an outcome
with `commit_acknowledged = false`; it does not discard the expected role or
fall back to the signed expiry. `_create_or_resolve_login(...)` uses that exact
outcome for every `_role_observation(...)` and `_close_login(...)` comparison.
No recovery path recomputes the deadline. The outcome creates no public status.

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
- `TELC-004` — Inside the role-creation transaction, `H3` is accepted only from
  the same connection's live PostgreSQL `clock_timestamp()` with
  `clock_regressed == false`, and is observed before fresh authority
  observation `A3`; then `A3 >= A2` is required before derivation or role SQL.
  With source-fixed `U = 1_000_000`, `T = 61_000_000`, and `Q = 1`
  microseconds, `VALID UNTIL` equals
  `H3 + (signed_expiry - max(A3, H3) - U - T - Q)`. A
  `raw_remaining <= U + T + Q` or unrepresentable result refuses before role
  SQL. Every later exact-state comparison uses the identical derived value.
- `TELC-005` — Production composition is ineligible unless current independent
  evidence for the exact authority host and PostgreSQL 17 route proves both
  that authority-minus-database divergence grows by at most `U` and that the
  exact server timeout and timer topology limit authority-clock advance from
  verifier retrieval through `AuthenticationOk` or timeout to at most `T`.
  Under those premises, every successful password authentication reaches
  `AuthenticationOk` strictly before authority expiry, including a verifier
  retrieved at exact `VALID UNTIL` equality, forward authority steps, unequal
  clock rates, and a deliberately delayed SCRAM response. Missing, stale,
  ambiguous, build-, hook-, timer-, configuration-, or route-mismatched
  evidence never selects a larger reserve or fallback.
- `TELC-006` — Existing consumption, role shape, export bounds, closure,
  quarantine, failure secrecy, and decision-v1 external prerequisites remain
  unchanged. LOGIN commit ambiguity retains the exact derived expected role
  and never recomputes or substitutes the signed expiry.
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
| TELC-002 | Call the supported lifecycle, then observe `A2 < A1` while database high-water is lower. | Fixed refusal before consume SQL; no consumption row and no LOGIN. |
| TELC-003 | Call with non-regressing `A1`, `A2`, acknowledge consumption, then observe `A3 < A2` before role creation. | Fixed consumed failure; one consumed row may exist, no LOGIN or export call. |
| TELC-004 | Return `clock_regressed = true`, a stored high-water rather than live `clock_timestamp()`, `A3 >= expiry`, `raw_remaining <= U + T + Q`, or an unrepresentable derived value. | Fixed consumed failure before `CREATE ROLE`; no LOGIN. |
| TELC-004 | On the lagging-database role-creation path, observe live `H3`, deliberately delay one second while advancing both simulated clocks, and only then observe non-regressing `A3`; compare with equal offsets and no delay. | Source and runtime evidence show `H3 -> A3 -> derive -> role SQL`; the absolute cutoff is one second earlier and the interval from role creation is two seconds shorter. An `A3 -> H3` implementation fails. |
| TELC-004 | Make the database ahead so `H3 > A3`. | The helper-derived deadline is exactly `signed_expiry - U - T - Q`; role SQL uses helper provenance, and a test does not misclassify numeric proximity to the signed timestamp as direct copying. |
| TELC-004, TELC-005 | Use seconds `H3 = 0`, `A3 = 60`, signed expiry `E = 125`, `U = 1`, `T = 61`, and `Q = 0.000001`. Advance the live PostgreSQL clock to the former no-`Q` deadline `3`. | Role `VALID UNTIL` is `2.999999`; PostgreSQL's strict comparison now sees `2.999999 < 3` and refuses. Removing `Q`, changing it to zero, or expecting equality itself to refuse fails the live and architecture evidence. |
| TELC-005 | Retrieve the verifier at exact corrected equality `H(s) = D`, delay SCRAM near the exact server authentication timeout, and advance authority by the admissible bound. | Equality may retrieve the verifier, but every successful exchange reaches `AuthenticationOk` with `A(c) <= E - Q`; a response exceeding the server timeout fails and creates no authenticated session. |
| TELC-005 | Crash or close the lifecycle client after verifier retrieval while SCRAM is in progress. | No page is exposed and no authenticated export session survives; the server observes EOF or its authentication timeout, while any exact stale LOGIN retains the existing readiness and closure-only posture. |
| TELC-005 | After `A3`, step the authority clock forward, advance authority faster than the database, or grow divergence beyond `U`. | Within-`U` cases remain bounded by the subtracted reserve; beyond-`U`, missing-evidence, stale-evidence, and route-mismatch cases keep production composition ineligible and never widen the constant. |
| TELC-006 | Raise the LOGIN commit after role SQL. | The private creation outcome reports unacknowledged commit and carries the exact derived expected role into observation and closure; no recovery comparison uses signed expiry. |
| TELC-006 | Hold the access-clock lock when the in-transaction `H3` observation runs. | Fixed consumed failure with rollback, no role, and no lock-order inversion with catalog observation. |
| TELC-006 | Raise dependency exceptions containing carriers, routes, password, page, and derived timestamps at each corrected boundary. | Existing fixed non-sensitive public outcomes only. |
| TELC-007 | Require output custody, SQL migration, provider evidence, or another role capability to close a finding. | Stop and create a new decision or Follow-up; do not expand this PR. |

Arbitrary in-process construction through reflection is not a supported
production entry under the retained decision-v1 threat model. Repository source
that directly imports, names, or constructs the private carrier is in scope and
is mechanically rejected.

## 9. Proposed architecture and smallest change

The lifecycle module gains only four small private concepts:

1. an immutable current-approval carrier binding the verified approval to its
   latest accepted raw authority observation;
2. an immutable login-creation outcome retaining the translated expected role
   and commit acknowledgement across ambiguity;
3. the source-fixed `U`, `T`, and `Q` deadline-reserve constants; and
4. the renamed module-private closed-result carrier.

A pure bounded helper derives the database-domain role deadline and subtracts
the three fixed reserves in one expression. The helper is called only after
live `H3` and fresh `A3` are taken in the role-creation transaction.
`_create_login(...)` returns its exact expected role even when commit
acknowledgement is absent; recovery never recomputes it. Existing role SQL,
settings, membership, export invocation, closure, structural verification,
and fixed public exceptions remain direct.

The architecture checker extends its existing lifecycle rule instead of
creating a new framework. It checks class inventory, export surface, sole
construction ordering, the exact `H3 -> A3 -> derive -> role SQL` source
ordering and provenance, all three fixed reserves and the exact formula,
recovery use of the returned expected role, and repository-wide private-symbol
references using the already authenticated Python source snapshot. The
private-symbol rule is limited to Python AST `Name`, `Attribute`, and
`ImportFrom` references; the checker may contain the symbol as a string
constant without accusing itself. It also proves that no checked-in non-test
production module imports, references, or calls
`SecurityAuditBreakGlassRunner`; this PR cannot create the production
composition whose external clock and authentication-timer evidence is still
absent.

The lifecycle module is already 1,205 physical lines against its 1,250-line
architecture budget. Phase B may raise only that exact module budget in
`rewrite_architecture_check.py` to at most 1,325 physical lines to carry these
four private concepts and direct evidence. The repository-wide 80-line
function maximum and every other module or group budget remain unchanged. A
larger increase stops for a new decision version rather than silently weakening
the checker.

The focused test module replaces the arbitrary public-construction assertion
with a real-lifecycle result assertion and adds hostile raw-regression and
lagging-database authentication cases. It injects elapsed time after the `H3`
read and before `A3`; forward authority steps and unequal rates after `A3`;
exactly-at-`U`, beyond-`U`, combined-reserve exhaustion, the former unguarded
equality deadline, exact corrected equality, delayed SCRAM success and timeout,
in-flight client crash, regressed-live-clock, ambiguous-commit, and held-
access-clock-lock cases. An isolated live server may use a shorter known
`authentication_timeout` to exercise the timeout path without changing the
source-fixed `T`; the deterministic model proves the accepted 61-second bound.
The canonical inventory changes only by the mechanically collected test-count
delta.

This is the minimum coherent correction because:

- merely removing a name from `__all__` leaves the public class and arbitrary
  construction intact;
- comparing only verifier maxima would hide raw authority regression behind a
  higher database value;
- copying the authority timestamp remains unsafe even after another freshness
  check; the remaining interval must be translated into PostgreSQL's domain;
- translating without subtracting `U` assumes future clock-offset equality
  that the accepted trust model does not provide;
- omitting `Q` treats PostgreSQL's accepted equality as expired;
- omitting `T` confuses verifier retrieval with completed password
  authentication; and
- a new token, validator, service, database column, or migration would add
  authority not required by the retained threat model.

## 10. Elegance audit

Sources of truth remain:

1. the signed request expiry for total remaining authentication authority;
2. direct raw authority observations for authority-domain progression;
3. the accepted live PostgreSQL clock observed before final authority
   currentness for the database deadline origin;
4. the source-fixed `U`, `T`, and `Q` constants, with independent exact
   clock-pair, server-configuration, and timer evidence as production-
   eligibility prerequisites;
5. PostgreSQL 17 source semantics for password-expiry equality and complete
   password authentication;
6. acknowledged consumption commit for first use; and
7. complete role absence plus structural verification for closure.

There is one deadline translation, one combined reserve expression, one
authoritative observation order, and one positive result construction. The
current-approval carrier removes correlated `approval` and `authority_now`
arguments from the corrected transitions. The login-creation outcome retains
only state already required for ambiguous-commit resolution.

Deleted compatibility surface:

- the public `ClosedSecurityAuditBreakGlassExport` name and export;
- direct authority-expiry-to-PostgreSQL conversion;
- an unreserved assumption that two nonregressing clocks keep equal future
  rates;
- the false assumptions that `VALID UNTIL` equality refuses and that verifier
  retrieval completes password authentication; and
- independent second observations with no raw ordering relation.

No new abstraction has multiple implementations or selects a dependency at
runtime. A clean rewrite is not justified; the direct state machine remains
sound outside the merged findings and demonstrated prospective clock defects
corrected here.

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

There is no cross-boundary exception in version 5. Migration 4 and temporary
credential authority were already merged by decision v1; this PR changes only
the lifecycle's enforcement of the approved contract and its necessary
mechanical conformance evidence.

Dependencies: merged PR #328 and its accepted prerequisites. No stacked PR is
required.

Reviewers must not require output custody, deployment composition, collection
or storage of differential-clock or authentication-timer evidence, provider
evidence, a cryptographic result token, a global clock service, a new database
function, or unrelated lifecycle hardening from this PR. This decision defines
the exact future evidence prerequisites but does not implement deployment
eligibility. A demonstrated need for another path stops implementation for a
separate decision.

Follow-ups remain the decision-v1 protected output-custody, broader crash-
operation evidence beyond the required in-flight authentication case,
cross-slice evidence, production-prerequisite evidence, and issue-closure
work.

## 12. Provisional design record

Not provisional.

The retained decision-v1 external prerequisites and invalidation conditions
remain binding. Evidence that arbitrary in-process code execution must be in
scope would invalidate module privacy and require a cryptographic or
process-isolated admission design. Evidence that PostgreSQL authenticates
against a clock other than the observed selected database domain would require
a new deadline design. A PostgreSQL source change to expiry equality, timeout
coverage, or the point represented by `AuthenticationOk` requires a new
decision. Evidence that the exact authority host and PostgreSQL route cannot
keep differential growth at or below one second over every 300-second interval,
or cannot bound complete-authentication authority advance at or below 61
seconds with `authentication_timeout <= 60 seconds`, makes production
deployment ineligible and requires a new decision; it never widens `U` or `T`.
Any host, route, server build, authentication hook, configuration,
virtualization, timer, or time-sync topology change invalidates predecessor
evidence until independently renewed.

## 13. Traceability and verification

| Invariant | Owning implementation | Negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| TELC-001 | private result class; `_export_and_close`; lifecycle architecture rule | public/re-exported/external private-symbol AST; real result path | no public symbol, one constructor after `_close_login`, no external references | focused source test plus rewrite architecture check |
| TELC-002 | private current-approval carrier and advance function before `_consume` | `A2 < A1` | fixed refusal, no consume row, no role | focused deterministic live lifecycle test |
| TELC-003 | currentness advance inside role-creation transaction | `A3 < A2` after consume commit | fixed consumed failure, one consume row, no role/export | focused deterministic live lifecycle test |
| TELC-004 | accepted-live-`H3` observation, `A3` advance, fixed-`U/T/Q` deadline helper, and expected-role creation outcome | regressed/cached H3; reversed order; injected delay; combined-reserve exhaustion; leading, lagging, equality, and unrepresentable calculations | exact `H3 -> A3 -> derive -> role SQL` provenance; exact three constants and formula; same derived value in ambiguity resolution | architecture provenance/order check, deterministic delay and pure bound tests, live catalog and equality observations |
| TELC-005 | fixed `U/T/Q` reserves and translated PostgreSQL `VALID UNTIL`; no production runner composition; exact clock, server, configuration, and timer deployment premises | authority forward step; faster authority rate; exactly-at/beyond-`U`; exact-equality verifier retrieval; delayed/timeout/crashed SCRAM; missing/stale/mismatched evidence; add a production caller | every successful authentication reaches `AuthenticationOk` strictly before authority expiry; over-bound exchange refuses; current repository cannot compose production use | hostile deterministic clock/timer model, live raw-SCRAM probes, architecture caller check, future independent deployment-evidence audit |
| TELC-006 | private creation outcome; existing public exception mapping, export, closure, and quarantine paths | ambiguous commit, held access-clock lock, dependency canaries | derived role survives ambiguity; no lock inversion; fixed non-rendering errors; existing lifecycle regressions pass | focused suite plus full Kernel baselines |
| TELC-007 | Git diff path check, lifecycle module budget, and canonical inventory | any sixth path, budget above 1,325, changed global function cap, or unregenerated count | exact five-path diff, bounded lifecycle growth, unchanged other budgets, collected inventory equality | package contract plus exact path and budget comparison |

Required Phase B verification:

- focused unit and live PostgreSQL tests for every `TELC` invariant;
- existing security-audit approval, export, migration, lifecycle, structural,
  readiness, and observer-vocabulary regressions;
- architecture negative evidence for public result restoration, external
  private-symbol reference, duplicate construction, construction before
  closure, cached/regressed H3, missing or changed `U`, `T`, or `Q`, altered
  combined formula, `A3 -> H3` order, recovery recomputation, or private-symbol
  AST false positives from the checker's own string constant, plus any
  non-test production import, reference, or call to
  `SecurityAuditBreakGlassRunner`;
- deterministic hostile delay evidence that advances time between `H3` and
  `A3` and proves the lagging-database cutoff moves earlier by `d` and the
  interval from role creation shrinks by `2d`;
- deterministic forward-step and relative-rate evidence at, below, and above
  `U`; authority-time advance at, below, and above `T`; combined-reserve
  exhaustion refusal; and exact arithmetic for `Q`;
- live PostgreSQL 17 evidence that the former no-`Q` equality deadline refuses,
  corrected equality can retrieve the verifier, delayed SCRAM admitted near
  the exact configured authentication bound completes before authority expiry,
  a delay beyond the bound times out, and an in-flight client crash creates no
  authenticated session or page handoff;
- ambiguous LOGIN-commit evidence using the one returned derived role, and a
  held-access-clock-lock case proving rollback with no lock-order inversion;
- exact lifecycle module budget no greater than 1,325 physical lines, with the
  repository 80-line function cap and every other budget unchanged;
- Ruff over every changed Python path and `git diff --check`;
- mechanically regenerated canonical test inventory when collection changes;
- `python3 conformance/ofarm_pkg_contract_check.py` immediately before every
  commit;
- exact base-to-head five-path equality;
- an explicit report that differential-clock and complete-authentication
  deployment evidence is not supplied by this PR and production composition
  remains unauthorized;
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
  regression; and the decision-v2 `A3 -> H3` observation order that could
  double-count inter-observation delay; the decision-v3 absence of a bound on
  post-`A3` authority-minus-database divergence; and the decision-v4 false
  equality and pre-SCRAM-expiry-check assumptions.
- Whole-card review clarifications incorporated: commit-ambiguity carrier
  return semantics; the exact live-`clock_timestamp()` premise; database-ahead
  derivation provenance; lagging-database `2d` delay cost and consumed-failure
  posture; explicit module-budget change; unambiguous regression notation;
  held access-clock lock evidence; and AST node-kind scope for the private-
  symbol checker.
- Remaining Blockers: Phase A review pending.
- Follow-ups: unchanged decision-v1 output custody, broader crash-operation
  evidence beyond the required in-flight authentication case, final hostile
  cross-slice evidence, production prerequisite evidence, and issue #192
  closure audit. The future output-custody composition must resolve how it
  annotates the private result without widening this PR.
- Preferences: none.

### Required exact approval form

The only valid approval form is the entire visible text of a later task-user
message in this same Codex task:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-TEMPORARY-EXPORT-LIFECYCLE-001 version 5.
```

No generic approval, shortened version label, GitHub activity, review result,
CI result, tool message, or predecessor approval authorizes Phase B.

Merge stop rule: implementation begins only after the exact later task-user
approval for this decision version and its named draft PR. Merge remains
blocked until every approved invariant passes, all exact-head hosted gates pass,
an independent exact-head review demonstrates zero Blockers, and the complete
diff equals the approved technical allowlist. New ideas and Preferences remain
Follow-ups and do not widen this PR.
