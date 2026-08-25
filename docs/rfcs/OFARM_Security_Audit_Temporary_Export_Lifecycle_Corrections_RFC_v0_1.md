# OFARM Security-Audit Temporary Export Lifecycle Corrections — Decision v9

## Status

- Parent: issue #192.
- Decision: `ISSUE192-SECURITY-AUDIT-TEMPORARY-EXPORT-LIFECYCLE-001`,
  version 9.
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
- Superseded initial decision-v5 review head:
  `b3fdb2b0b036391faaa5c084a43f81e6f2d5b3a3`.
- Decision-v5 PostgreSQL source-provenance Blocker and bounded review
  clarifications:
  https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5019281156.
- Superseded corrected decision-v5 head:
  `2a5b37b1a2d0ebe991429e83bea4e44a7b3a5fc6`.
- Decision-v5 corrected whole-card review:
  https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5020396231.
- Decision-v5 proof-domain and production-composition Blockers:
  https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5021156140.
- Superseded decision-v6 head:
  `ccbdac820f7a3c8788eced48dca04c775177e3f2`.
- Decision-v6 dynamic-loading production-composition Blocker:
  https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5021821735.
- Superseded decision-v7 head:
  `05633f1db8b56432f4ed9eaa464531489313b288`.
- Decision-v7 regular-package-initializer Blocker:
  https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5022772708.
- Superseded decision-v8 head:
  `727b28fc789632be6651439cd20de77af2e1874c`.
- Decision-v8 incomplete-production-root Blocker:
  https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5023619512.
- Decision-v8 source-integrity scope objection:
  https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5023671963.
- Phase A changes only this RFC. Phase B is not authorized before the exact
  task-user approval required below.
- Decision v5 superseded decision v4. Version 4 correctly bounded later
  authority-minus-database divergence, but it treated equality at PostgreSQL
  `VALID UNTIL` as expired and treated password-verifier retrieval as the end
  of SCRAM authentication. PostgreSQL 17 accepts equality and does not recheck
  expiry after the multi-message exchange. Version 5 retains the corrected
  `H3 -> A3` order and differential-growth reserve, subtracts one PostgreSQL
  timestamp quantum, and reserves the independently bounded authority-clock
  advance of a complete password-authentication exchange. Version 4 was never
  approved and its task-user card is withdrawn.
- The initial version-5 head correctly established that formula, but cited an
  unrelated PostgreSQL development commit rather than the supported server
  release. The corrected decision-v5 head pinned the same semantics to
  PostgreSQL `REL_17_10`, matching repository version policy, and made the
  already required verification boundaries explicit. That correction changed
  no authority, formula, invariant, or path envelope, so the head remained
  decision version 5. The earlier version-5 task-user card was withdrawn
  pending exact-head review.
- This version supersedes decision v5. Version 5 bounded differential growth
  over 300 seconds of real time but applied that premise through a role's
  potentially longer real lifetime. Version 6 requires the same fixed `U`
  bound over the complete credential-relevant interval without a real-duration
  cap. That material external-premise correction remains binding; version 5
  was never approved, and its task-user card is withdrawn. Version 6 also began
  a production-source composition rule whose later expansion is withdrawn by
  version 9 as a separate trust boundary.
- This version supersedes decision v6. Version 6 closed the complete-interval
  proof domain and ordinary authenticated import reachability, but a fixed-root
  production module could still execute the lifecycle through a source-visible
  dynamic loader such as split-string `runpy.run_module(...)` without creating
  a repository import edge. Version 7 retains the version-6 proof and static
  graph, then adds one closed production-source execution policy over every
  fixed-root-reachable module. The policy admits only the source-fixed current
  external imports and narrowly enumerated harmless reflection and `os`
  operations, while rejecting dynamic module/code loading and process launch
  through aliases, re-exports, reflection, and equivalent unresolved
  provenance. This is a material conformance-invariant change. Version 6 was
  never approved, and its task-user card is withdrawn.
- This version supersedes decision v7. Version 7 closed dynamic module, code,
  cache, loader, interpreter, and process execution for the 36 modules already
  represented in explicit production reachability, but that subject set did
  not require every regular-package `__init__.py` that Python implicitly
  executes before a reached submodule. At the reviewed base, `kernel` and
  `deployment.postgresql` happen to be explicitly reachable, while the regular
  parent package `deployment` is not, even though importing
  `deployment.postgresql` executes `deployment/__init__.py`. Version 8 derives
  a fixed-point production import-execution closure from fixed roots, every
  retained regular-package initializer ancestor, and every explicit repository
  import. The reviewed-base closure contains 37 modules and the closed source-
  execution policy applies to all of them. This is a material production-set,
  graph-semantics, inventory, and conformance-invariant change. Version 7 was
  never approved, and its task-user card is withdrawn.
- This version supersedes decision v8. Exact-head review demonstrated that the
  37-member application import-execution closure omitted documented production
  release and operator entrypoints, including
  `deployment.postgresql.run_security_audit_migrations`. A complete correction
  would require governed classification of production, operator, console,
  test, conformance, and non-production execution roots plus capability
  profiles for their closures. The accompanying scope review correctly
  identified that work as repository-wide source-integrity governance, not the
  temporary export lifecycle boundary. Version 9 therefore withdraws the
  universal repository-composition and source-admissibility guarantee instead
  of appending another cross-boundary fix. It preserves the complete-interval
  clock premise and every other lifecycle correction established after version
  5. The reachability-framework residue is tracked by issue #334; complete
  execution-root classification and any closed source-capability policy require
  their own reviewed decision and PR. Version 8 was never approved, and its
  task-user card is withdrawn.
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

Exact-head review of decision v5 then demonstrated one further lifecycle gap:

6. a bound quantified over 300 seconds of real time was applied through a
   credential interval whose real duration was not bounded by the request's
   300-second authority-domain lifetime.

The same review also challenged a voluntarily added repository-composition
rule:

7. its runner-name scan did not cover the private test seam,
   dependency carrier, aliases, re-exports, reflection through an ordinary
   module import, or nominal test modules reachable from production roots.

Later reviews correctly demonstrated that the expanding source-governance rule
remained incomplete:

8. authenticated static import reachability did not cover checked-in dynamic
   module loading, code execution, module-cache resolution, or interpreter and
   process launch, so split strings passed to `runpy.run_module(...)` could
   execute the lifecycle without an import-graph edge.
9. explicit-import reachability did not require every retained regular-package
   initializer that Python executes implicitly before a root or reached
   submodule, leaving `deployment/__init__.py` outside the 36-module production
   policy even though normal loading of `deployment.postgresql` executes it;
   and
10. the resulting 37-member application closure omitted supported production
    release and operator entrypoints, so a documented `python -m` command could
    execute source outside the closed policy.

Items 7 through 10 are sound observations about repository source governance,
but they do not belong to this lifecycle-correction trust boundary. Closing
them coherently requires a complete execution-root inventory and policy across
application, release, operator, console, test, conformance, build, and tooling
source. Version 9 removes the over-broad guarantee and records that work as a
separate source-integrity decision rather than redefining this PR's boundary.

This decision establishes a narrow correction in the same primary trust
boundary. It makes closure provenance repository-private, carries raw
authority currentness through the state machine, observes the database
deadline origin before the final authority observation, translates the then
remaining authority time into the database clock domain, and subtracts three
source-fixed values: future differential-clock growth, complete-authentication
authority advance, and one PostgreSQL timestamp quantum. It proves those
properties with hostile regression, observation-delay, forward-step,
relative-rate, slow-clock, exact-equality, and delayed-SCRAM evidence. It grants
no deployment or production-composition authority. It does not claim that an
application import graph, AST policy, or incomplete execution-root inventory
can prove the lifecycle unreachable from every supported repository command.

The goal is not to add a new lifecycle or authority. It is to make the merged
implementation satisfy `TEL-002`, `TEL-005`, `TEL-008`, and `TEL-013` as they
were already approved.

## 2. Learning value

The correction demonstrates that one direct lifecycle can safely bridge the
authority clock, PostgreSQL wall clock, and PostgreSQL authentication timer
without treating their timestamp values or rates as interchangeable. It also
proves that a nominal positive carrier is not an admission authority:
any later approved composition must obtain it from the closed runner path.

The work removes six concrete lifecycle risks:

- arbitrary repository code presenting caller-created bytes as a
  closure-proven result;
- a lagging PostgreSQL clock extending the new-password-authentication window;
- an observed authority-time rollback passing silently between required
  observations;
- a later authority-clock step or faster authority-clock progression leaving
  PostgreSQL willing to retrieve the verifier after signed authority expiry;
- equality at `VALID UNTIL` or an in-flight SCRAM exchange completing at or
  after signed authority expiry;
- two slowly progressing clocks accumulating unsafe divergence after the first
  300 real seconds while the role remains.

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
- introduce a Python, operating-system, container, or process sandbox; attest
  arbitrary post-snapshot runtime mutation; or govern checked-in dynamic module,
  code, loader, cache, interpreter, or process capabilities;
- define a complete application, release, operator, console, test, conformance,
  build, or tooling execution-root inventory; change the repository import-
  reachability framework tracked by issue #334; or claim every supported
  repository command is covered by one source-execution policy;
- implement protected output custody or allow an output layer to accept a
  caller-supplied nominal result;
- change provider, IAM, observer-root, recovery, backup, replica, clone,
  failover, tenant, HMAC, or retention boundaries;
- authorize deployment, production operation, export disclosure, issue #192
  closure, or merge without exact-head review; or
- reopen the abandoned PR #325-#327 target/epoch architecture.

Protected output custody remains a separate later trust boundary. It must call
the runner in its own separately reviewed trusted composition and treat the
returned private instance as opaque. This PR creates no output consumer,
deployment entrypoint, production composition, or source allowlist.

No absence claim over checked-in production execution is used as deployment
authority. The application-root graph omits supported release and operator
commands, and a complete governed root inventory is separate work. Until a
later decision supplies the required external evidence and explicitly approves
a composition, production operation remains unauthorized and non-deployable;
this RFC does not claim it is mechanically unreachable from all repository
source.

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
- upstream PostgreSQL tag `REL_17_10` as the Phase A semantic reference for the
  repository-supported PostgreSQL 17.10 pgdg artifact, its strict
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
  microseconds over the complete credential-relevant interval, irrespective of
  real duration, and that the exact server's `authentication_timeout` is no
  greater than 60 seconds while authority time can advance by at most 61,000,000
  microseconds from password-verifier retrieval through `AuthenticationOk` or
  timeout;
- the authenticated architecture source snapshot only for the exact lifecycle
  surface, private-result symbol, observation-order, formula, and path-envelope
  checks defined by this decision; it is not trusted as a complete production
  execution-root inventory; and
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
- two nonregressing clocks that progress slowly together for more than 300 real
  seconds while accumulating authority-minus-database divergence beyond `U`;
- a client that retrieves the verifier immediately before the role deadline
  and then delays its SCRAM response;
- stale, ambiguous, build-mismatched, hook-mismatched, or route-mismatched
  `authentication_timeout` and authority-advance evidence;
- an authority-clock forward step or authority-over-database relative-rate
  change beyond the fixed reserve;
- a raw authority-time observation that is lower than the previous raw
  observation;
- a PostgreSQL server clock that is non-regressing but behind or ahead of the
  certified authority-time domain; and
- a caller attempting to substitute a public, imported, serialized, or
  caller-constructed object for the runner's private post-closure result.

### 4.4 Excluded attacker capabilities

The decision-v1 exclusions remain unchanged. In particular, arbitrary
in-process mutation, local source substitution, compromised Python or
PostgreSQL dependencies, filesystem mutation, debugger access, process-memory
compromise, database-superuser corruption, and trusted-operator compromise are
out of scope.

Because arbitrary in-process execution is excluded, a module-private carrier
plus the exact repository-wide private-symbol import/reference check is the
smallest sufficient result-provenance boundary. This decision does not pretend
that Python module privacy or AST analysis is a cryptographic sandbox, and it
does not use a partial production import graph as proof that all supported
execution origins are safe. Broader source-admissibility and execution-root
governance require a separate trust model and review.

The source-fixed reserves are not an assertion that current deployment
evidence already exists. They are the maximum admissible bounds for a future
deployment. Evidence that cannot prove the exact clock-pair ceiling, the
60-second PostgreSQL authentication-timeout ceiling, and the 61-second
authority-advance ceiling keeps production composition unavailable; it does
not widen a constant or permit a fallback. The clock-pair ceiling covers the
entire time the exact role exists plus any still-unresolved password exchange;
it does not reset every 300 real seconds. The one-second KMS/database premise
elsewhere in the repository is a numeric security-audit precedent only and
cannot supply these distinct authority-host/database/timer premises.

## 5. Authority map

| Decision | Sole authority | Forbidden substitute |
| --- | --- | --- |
| Verified approval and first raw currentness | Decision-v1 verifier result bound to the exact first fresh authority observation | parsed carriers, caller time, database time alone |
| Later raw authority currentness | Each direct fresh observation, accepted only when it is at least the immediately preceding raw authority observation | maximum with database time, caller assertion, an earlier observation reused after delay |
| Consumption | Existing acknowledged migration-4 consume commit using the second accepted raw authority observation | verifier success, returned SQL row before commit, retry inference |
| Differential-clock growth reserve `U` | Source-fixed 1,000,000 microseconds, admissible for production only with current independent evidence for the exact authority host and PostgreSQL route over the complete credential-relevant interval without a real-duration cap | a repeating 300-real-second window, caller/configured value, missing or stale evidence, another host/route, KMS/database evidence, an NTP label alone |
| Complete-authentication reserve `T` | Source-fixed 61,000,000 microseconds of maximum authority-clock advance from verifier retrieval through `AuthenticationOk` or timeout, admissible only when current independent evidence binds the exact PostgreSQL build, route, hooks, timer topology, and `authentication_timeout <= 60 seconds` | client or configured reserve, connect timeout, statement timeout, an unverified/default setting, another server or route |
| PostgreSQL timestamp quantum `Q` | Source-fixed 1 microsecond matching PostgreSQL 17.10 `timestamptz` precision and compensating for its strict `VALID UNTIL < database_now` expiry comparison | zero, caller precision, host-language datetime assumption, changing the comparison premise without source evidence |
| Live database deadline origin `H3` | Same-connection `_observe_nonregressing_access_clock()` result accepted only when `clock_regressed` is exactly false, proving the returned value is that connection's live `clock_timestamp()` | cached preflight `H1`, stored sequence high-water, direct sequence read, a regressed-clock result, later database observation |
| Remaining complete-authentication authority | `raw_remaining = signed_expiry - max(A3, H3)` followed by `safe_remaining = raw_remaining - U - T - Q` | raw remaining without every reserve, signed absolute expiry copied directly to PostgreSQL, either clock alone |
| PostgreSQL role deadline | `H3 + safe_remaining`, derived after `H3`, then `A3`, and retained unchanged for every exact-state comparison | authority-domain timestamp chosen directly, caller deadline, recomputation on commit ambiguity, a later database observation |
| Closure provenance | The sole module-private carrier construction after `_close_login(...)` returns successfully | a public constructor, imported private class, caller-created lookalike, serialized token |
| Positive output entry | A future separately approved trusted composition invoking this runner and treating its returned private instance as opaque | accepting a caller-supplied nominal result or importing a result constructor |
| Production composition | A later decision after current independent clock, PostgreSQL artifact, route, hook, configuration, and authentication-timer evidence is accepted | this RFC, runner existence, merge, CI, an application-root reachability result, absence from a partial source graph, or an unclassified release/operator command |

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

The post-`A3` proof is conditional on a complete-interval deployment premise,
not a repeating short-window premise. Let the credential-relevant interval
begin at the real instant `r2` where `A3` is sampled. It continues for as long
as the exact role exists or any password exchange that retrieved its verifier
remains unresolved. Successful closure ends it only after the role is absent
and every such exchange has reached `AuthenticationOk`, refused, observed EOF,
or timed out. A lifecycle stall or crash that leaves the role present leaves
the interval open. For every later real instant `t` in that interval,
irrespective of its real duration, independent evidence for the exact authority
host and selected PostgreSQL route must prove:

```text
(A(t) - H(t)) - (A(r2) - H(r2)) <= U
U = 1_000_000 microseconds
```

Let the database observation occur at real instant `r1`, so `H3 = H(r1)`, and
the later authority observation occur at `r2`, so `A3 = A(r2)`. Define the
observed conservative divergence as `G3 = A3 - H3`. Because the accepted
database clock is nonregressing, `H(r2) >= H3`, and therefore
`G3 >= A(r2) - H(r2)`. Applying the complete-interval premise derives for
every relevant `t`:

```text
(A(t) - H(t)) - G3 <= U
```

The premise and derivation include authority-clock forward steps,
authority-over-database rate or slew, and cross-host synchronization
uncertainty. Let `E` be signed authority expiry. The derived deadline is:

```text
D = H3 + E - max(A3, H3) - U - T - Q
```

PostgreSQL 17.10 returns the stored verifier whenever its lookup time `s` has
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
that other clock pair does not transfer here. The maximum approval lifetime
does not cap real elapsed time, so the `U` premise never resets after 300 real
seconds.

A hostile slow-clock sequence makes that distinction executable. With seconds
`A3 = H3 = 0`, `E = 300`, `U = 1`, `T = 61`, and `Q = 0.000001`, the deadline
is `D = 237.999999`. Over 19,000 real seconds, clocks ending at `A = 300.1` and
`H = 237.9` grow divergence by only about `0.9821` seconds in every 300-real-
second window, yet total divergence grows by `62.2` seconds and PostgreSQL can
retrieve the verifier after authority expiry. This decision rejects that
deployment because complete-interval growth exceeds `U`; a sequence of
individually acceptable 300-second windows is not admissible evidence.

`T` is also a maximum admissible authority-domain bound, not a claim that the
documented PostgreSQL default is sufficient by itself. It admits only an exact
server whose effective `authentication_timeout` is at most 60 seconds and for
which independent evidence bounds authority-clock advance by at most 61
seconds from verifier retrieval through `AuthenticationOk` or timeout. This
extra second must cover timer granularity, scheduling, authority slew, and
common-mode forward steps that the authority/database divergence bound alone
cannot see. The lifecycle's five-second client `connect_timeout` is an
availability control, not the authoritative server cutoff; a stalled or
descheduled client, client crash, or network partition cannot make it replace
the server-side `T` premise. A query `statement_timeout`, a default-value
assertion, and a measurement against another server do not satisfy this
premise.

`Q` is exactly one PostgreSQL 17.10 `timestamptz` microsecond. It exists because
PostgreSQL accepts equality at `VALID UNTIL`; it is not a configurable safety
margin.

Repository policy in `deployment/postgresql/version_policy.py` fixes supported
server version `17.10`, `server_version_num = 170010`, and accepted artifact
identity `17.10 (Debian 17.10-1.pgdg13+1)`. The Phase A semantic model is
pinned to upstream tag `REL_17_10`, commit
[`25c49f3a4a742ba283f5cc43cc7f1d361552e917`](https://github.com/postgres/postgres/commit/25c49f3a4a742ba283f5cc43cc7f1d361552e917).
In [`src/backend/libpq/crypt.c::get_role_password`](https://github.com/postgres/postgres/blob/25c49f3a4a742ba283f5cc43cc7f1d361552e917/src/backend/libpq/crypt.c),
PostgreSQL performs the strict expiry comparison. In
[`src/backend/libpq/auth.c::CheckPWChallengeAuth`](https://github.com/postgres/postgres/blob/25c49f3a4a742ba283f5cc43cc7f1d361552e917/src/backend/libpq/auth.c),
it retrieves the verifier before entering `CheckSASLAuth`. In
[`src/backend/utils/init/postinit.c::PerformAuthentication`](https://github.com/postgres/postgres/blob/25c49f3a4a742ba283f5cc43cc7f1d361552e917/src/backend/utils/init/postinit.c),
it uses the internal timeout slot named `STATEMENT_TIMEOUT` for
`AuthenticationTimeout`, enables that timer before `ClientAuthentication`, and
disables it only after that function returns. The lifecycle's startup option
`statement_timeout=5000` applies to authenticated statements after this phase;
it is independent of, and cannot shorten or replace, the server authentication
timer. PostgreSQL 17.10 documentation defines `timestamptz` resolution as one
microsecond and `authentication_timeout` as the maximum time allowed to
complete client authentication. Upstream `REL_17_10` establishes the Phase A
semantic model; the artifact accepted by repository version policy is the pgdg
Debian build of that release, not the upstream source tree itself. Phase B live
evidence must run against that exact pgdg artifact and verify that its packaging
patch series leaves the three named functions and timer behavior unchanged.

Future deployment evidence must be independently controlled and verifiable.
It binds the exact lifecycle authority host; exact accepted pgdg PostgreSQL
artifact and packaging patch series; system, HBA route, loaded authentication
hooks, effective `authentication_timeout`, authentication-timer slot behavior,
post-authentication query timeout, and timer source; clock and virtualization
topology; measurement error; observation scope; issuance time; and evidence
expiry. It must conclude both that complete-interval differential growth never
exceeds `U = 1_000_000` microseconds while the role or a retrieved exchange
remains, without a real-duration cap, and that `A(c) - A(s) <= 61_000_000`
microseconds for every password exchange admitted by a server timeout no
greater than 60 seconds. Per-window measurements, missing fields, expired
evidence, server or packaging revision, hook or configuration change, topology
change, ambiguous measurement error, or a larger result makes deployment
ineligible. This PR adds no evidence loader or runtime bypass; its absence is
enforced only within this correction by the five-path boundary. Production
composition remains unauthorized by decision governance, not proven
unreachable from every repository execution origin by source analysis.

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

This security bound does not guarantee availability. The exact reserve floor
is `U + T + Q = 62_000_001` microseconds, or `62.000001` seconds. Because
consumption is already acknowledged, `raw_remaining <= 62.000001` seconds is
a consumed failure and creates no role. Even a maximum 300-second authority-
domain request can leave at most `237.999999` seconds usable after `A3`, and
every preceding operation reduces that window. PostgreSQL's authentication
timeout bounds only password authentication, not role creation, connection setup
before its server timer, export execution, or output delivery. This paragraph
is the authoritative operational guidance for this correction: request the full
allowed 300-second authority-domain lifetime and invoke the approved lifecycle
promptly. Phase B must demonstrate the exhausted-reserve outcome. No additional
operations or deployment-document path is added; production remains non-
deployable until a separate follow-up supplies and approves the exact clock and
authentication evidence.

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
- `TELC-005` — Production use is ineligible unless current independent
  evidence for the exact authority host and PostgreSQL 17.10 route proves both
  that authority-minus-database divergence grows by at most `U` throughout the
  complete credential-relevant interval without a real-duration cap and that
  the exact server timeout and timer topology limit authority-clock advance
  from verifier retrieval through `AuthenticationOk` or timeout to at most
  `T`. This decision defines neither a complete repository execution-root
  inventory nor a production composition and grants no authority to deploy or
  invoke one. Under the evidence premises and a later separately approved
  composition, every successful password authentication reaches
  `AuthenticationOk` strictly before authority expiry, including a verifier
  retrieved at exact `VALID UNTIL` equality, forward authority steps, unequal
  clock rates, and a deliberately delayed SCRAM response. Missing, stale,
  ambiguous, build-, hook-, timer-, configuration-, or route-mismatched
  evidence never selects a larger reserve or fallback. A green source check,
  application-root reachability result, or absence from a partial import graph
  never substitutes for that evidence or the later composition decision.
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

## 8. Lifecycle negative cases

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
| TELC-005 | Over 19,000 real seconds use two nonregressing slow clocks that satisfy `U` in every 300-real-second window but grow total divergence by `62.2` seconds while the role remains. | Complete-interval evidence fails and production remains ineligible. A repeating-window implementation or model fails. |
| TELC-006 | Raise the LOGIN commit after role SQL. | The private creation outcome reports unacknowledged commit and carries the exact derived expected role into observation and closure; no recovery comparison uses signed expiry. |
| TELC-006 | Hold the access-clock lock when the in-transaction `H3` observation runs. | Fixed consumed failure with rollback, no role, and no lock-order inversion with catalog observation. |
| TELC-006 | Raise dependency exceptions containing carriers, routes, password, page, and derived timestamps at each corrected boundary. | Existing fixed non-sensitive public outcomes only. |
| TELC-007 | Require output custody, SQL migration, provider evidence, or another role capability to close a finding. | Stop and create a new decision or Follow-up; do not expand this PR. |

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

The architecture checker extends its authenticated source-snapshot structural
checks. It checks class inventory, export surface, sole
construction ordering, the exact `H3 -> A3 -> derive -> role SQL` source
ordering and provenance, all three fixed reserves and the exact formula, and
recovery use of the returned expected role.

The checker does not derive or enforce a production import-execution closure,
classify executable repository roots, pin unrelated external-import or `os`
capability inventories, or prohibit general reflection, loaders, evaluation,
or process launch. Those are source-integrity controls outside this decision.
The existing authenticated snapshot may supply files and ASTs to the exact
lifecycle checks above, but its application roots are not treated as a complete
inventory of supported production, release, or operator execution origins.

The Phase B checker fixes only the lifecycle-local structural and provenance
rules named here. The repository-wide check for the private result symbol is
targeted to `TELC-001`: no other Python AST may import or reference the exact
private class name. It is not generalized into a runner, lifecycle-module,
dynamic-execution, package-initializer, operator-root, or capability policy.
The checker and focused test must not imply that passing this bounded rule
proves production composition impossible. A future complete source-integrity
policy must be designed and reviewed separately against its full execution-
root and capability inventory.

The lifecycle module is already 1,205 physical lines against its 1,250-line
architecture budget. Phase B may raise only that exact module budget in
`rewrite_architecture_check.py` to at most 1,325 physical lines to carry these
four private concepts and direct evidence. The repository-wide 80-line
function maximum and every other module or group budget remain unchanged. A
larger increase stops for a new decision version rather than silently weakening
the checker.

Phase B must preserve that function cap by splitting `_create_login(...)`, not
by raising the cap. Small private helpers in the same connection and
transaction separately derive the exact expected role after `H3`, `A3`, and
the three reserves, and execute the existing role SQL, settings, and grants.
The outer `_create_login(...)` handles commit outcome construction, while
`_create_or_resolve_login(...)` retains ambiguity resolution. Both outer
functions and every new helper remain at or below 80 lines; the split does not
introduce another transaction, authority, or recomputation path.

The focused test module replaces the arbitrary public-construction assertion
with a real-lifecycle result assertion and adds hostile raw-regression and
lagging-database authentication cases. It injects elapsed time after the `H3`
read and before `A3`; forward authority steps and unequal rates after `A3`;
exactly-at-`U`, beyond-`U`, slow clocks whose per-300-second growth is admissible
but complete-interval growth exceeds `U`, combined-reserve exhaustion, the
former unguarded equality deadline, exact corrected equality, delayed SCRAM
success and timeout, in-flight client crash, regressed-live-clock, ambiguous-
commit, held-access-clock-lock, public-result restoration, external private-
symbol import/reference, duplicate construction, and construction before
closure. An isolated live server may use a shorter known
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
- bounding `U` only in repeating 300-real-second windows leaves a slowly
  progressing persistent role outside the proof domain;
- omitting `Q` treats PostgreSQL's accepted equality as expired;
- omitting `T` confuses verifier retrieval with completed password
  authentication;
- claiming universal production-source exclusion from application import roots
  would require a separate complete execution-root and capability-governance
  boundary; and
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
5. PostgreSQL 17.10 `REL_17_10` source semantics for password-expiry equality
   and complete password authentication;
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

Withdrawn prospective cross-boundary surface:

- the claim that application import roots form a complete production execution-
  root inventory;
- the 37-member import-execution closure and its external-import inventory;
- the closed reflection, `os`, loader, code, cache, interpreter, and process-
  capability policy; and
- the claim that those checks prove the lifecycle unreachable from every
  supported release or operator command.

No new abstraction has multiple implementations or selects a dependency at
runtime. A clean rewrite is not justified; the direct state machine remains
sound outside the merged findings and demonstrated prospective clock defects
corrected here.

## 11. Pull request boundary

### 11.1 Primary trust boundary

The primary trust boundary is the temporary dual-approved security-audit
export lifecycle, specifically positive-result provenance and the bounded new-
authentication interval between approval verification and credential closure.

### 11.2 Exact maximum path envelope

The draft and any authorized Phase B implementation are limited to exactly:

1. `docs/rfcs/OFARM_Security_Audit_Temporary_Export_Lifecycle_Corrections_RFC_v0_1.md`
2. `deployment/postgresql/security_audit_break_glass.py`
3. `kernel/tests/test_security_audit_break_glass.py`
4. `conformance/rewrite_architecture_check.py`
5. `conformance/review_baseline_test_inventory.json`

Phase A changes only path 1. The technical Phase B allowlist may equal or
narrow this envelope but may not add another path.

There is no cross-boundary exception in version 9. Migration 4 and temporary
credential authority were already merged by decision v1; this PR changes only
the lifecycle's enforcement of the approved contract and its necessary
mechanical conformance evidence.

Dependencies: merged PR #328 and its accepted prerequisites. No stacked PR is
required.

Reviewers must not require output custody, deployment composition, collection
or storage of differential-clock or authentication-timer evidence, provider
evidence, a cryptographic result token, a global clock service, a new database
function, a complete production execution-root inventory, package-initializer
reachability repair, repository-wide source-capability policy, or unrelated
lifecycle hardening from this PR. This decision defines the exact future
evidence prerequisites but does not implement deployment eligibility. A
demonstrated need for another path or trust boundary stops implementation for a
separate decision.

Follow-ups remain the decision-v1 protected output-custody, broader crash-
operation evidence beyond the required in-flight authentication case,
cross-slice evidence, production-prerequisite evidence, and issue-closure
work. Issue #334 owns the package-initializer reachability-framework residue;
complete production/operator execution-root classification and any closed
source-capability policy require separate source-integrity work.

## 12. Provisional design record

Not provisional.

The retained decision-v1 external prerequisites and invalidation conditions
remain binding. Evidence that arbitrary post-snapshot in-process code execution
must be in scope would invalidate module privacy and require a cryptographic or
process-isolated admission design. Evidence that PostgreSQL authenticates
against a clock other than the observed selected database domain would require
a new deadline design.

Any change to `SUPPORTED_POSTGRESQL_VERSION`,
`SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM`, or
`SUPPORTED_POSTGRESQL_SERVER_VERSION` in
`deployment/postgresql/version_policy.py` requires re-verification of
`get_role_password`, `CheckPWChallengeAuth`, and `PerformAuthentication` against
the new upstream release and accepted packaging patch series. A semantic change
to expiry equality, authentication-timer coverage, or the point represented by
`AuthenticationOk` requires a new decision. A packaging revision, server build,
host, route, authentication hook, configuration, virtualization, timer, or
time-sync topology change invalidates predecessor live evidence until
independently renewed.

Evidence that the exact authority host and PostgreSQL route cannot keep total
differential growth at or below one second throughout the complete credential-
relevant interval, without a real-duration cap, or cannot bound complete-
authentication authority advance at or below 61 seconds with
`authentication_timeout <= 60 seconds`, makes production deployment ineligible
and requires a new decision; it never widens `U` or `T`. Any explicit or
implicit production composition of the lifecycle module before a separate
approved composition is unauthorized and non-deployable. This decision does
not claim that such composition is mechanically unreachable from every
application, release, operator, console, test, conformance, build, or tooling
entrypoint.

If implementation or review requires a complete execution-root inventory,
package-initializer reachability model, or closed source-capability policy,
work must stop at this boundary and move to the separate source-integrity
decision tracked with issue #334. That need does not relax the lifecycle
invariants here and cannot be satisfied by silently restoring the withdrawn
decision-v8 policy.

## 13. Traceability and verification

| Invariant | Owning implementation | Negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| TELC-001 | private result class; `_export_and_close`; lifecycle architecture rule | public/re-exported/external private-symbol AST; real result path | no public symbol, one constructor after `_close_login`, no external references | focused source test plus rewrite architecture check |
| TELC-002 | private current-approval carrier and advance function before `_consume` | `A2 < A1` | fixed refusal, no consume row, no role | focused deterministic live lifecycle test |
| TELC-003 | currentness advance inside role-creation transaction | `A3 < A2` after consume commit | fixed consumed failure, one consume row, no role/export | focused deterministic live lifecycle test |
| TELC-004 | accepted-live-`H3` observation, `A3` advance, fixed-`U/T/Q` deadline helper, and expected-role creation outcome | regressed/cached H3; reversed order; injected delay; combined-reserve exhaustion; leading, lagging, equality, and unrepresentable calculations | exact `H3 -> A3 -> derive -> role SQL` provenance; exact three constants and formula; same derived value in ambiguity resolution | architecture provenance/order check, deterministic delay and pure bound tests, live catalog and equality observations |
| TELC-005 | fixed `U/T/Q` reserves and translated PostgreSQL `VALID UNTIL`; complete-interval clock premise; exact clock, pgdg server, configuration, and timer premises | authority forward step; faster or slowly progressing clocks; per-window-pass/complete-interval-fail growth; exact-equality verifier retrieval; delayed/timeout/crashed SCRAM; missing, stale, or mismatched evidence | every successful authentication reaches `AuthenticationOk` strictly before authority expiry; over-bound or absent evidence is ineligible; this invariant does not authorize production composition | hostile full-interval clock/timer model, live raw-SCRAM probes, and future independent deployment-evidence audit |
| TELC-006 | private creation outcome; existing public exception mapping, export, closure, and quarantine paths | ambiguous commit, held access-clock lock, dependency canaries | derived role survives ambiguity; no lock inversion; fixed non-rendering errors; existing lifecycle regressions pass | focused suite plus full Kernel baselines |
| TELC-007 | Git diff path check, lifecycle module budget, and canonical inventory | any sixth path, budget above 1,325, changed global function cap, or unregenerated count | exact five-path diff, bounded lifecycle growth, unchanged other budgets, collected inventory equality | package contract plus exact path and budget comparison |

Required Phase B verification:

- focused unit and live PostgreSQL tests for every `TELC` invariant;
- existing security-audit approval, export, migration, lifecycle, structural,
  readiness, and observer-vocabulary regressions;
- architecture negative evidence for public result restoration, external
  private-symbol reference, duplicate construction, construction before
  closure, cached/regressed H3, missing or changed `U`, `T`, or `Q`, altered
  combined formula, `A3 -> H3` order, recovery recomputation, or false positives
  from string constants and unrelated same-spelling local definitions;
- deterministic hostile delay evidence that advances time between `H3` and
  `A3` and proves the lagging-database cutoff moves earlier by `d` and the
  interval from role creation shrinks by `2d`;
- deterministic forward-step and relative-rate evidence at, below, and above
  `U` across the complete credential-relevant interval without a duration cap;
  the 19,000-real-second slow-clock counterexample must pass every 300-second
  window but fail complete-interval eligibility; authority-time advance at,
  below, and above `T`; combined-reserve exhaustion at the exact `62.000001`-
  second floor; maximum-window arithmetic leaving no more than `237.999999`
  seconds after `A3`; and exact arithmetic for `Q`;
- live evidence against the exact accepted PostgreSQL
  `17.10 (Debian 17.10-1.pgdg13+1)` artifact, including a verified packaging-
  patch comparison to the `REL_17_10` functions named in section 6.2, that the
  former no-`Q` equality deadline refuses,
  corrected equality can retrieve the verifier, delayed SCRAM admitted near
  the exact configured authentication bound completes before authority expiry,
  a delay beyond the bound times out, and an in-flight client crash creates no
  authenticated session or page handoff; the evidence must also distinguish
  the server authentication timer's internal `STATEMENT_TIMEOUT` slot from the
  independent post-authentication `statement_timeout=5000` option and show why
  the five-second client `connect_timeout` is not an authoritative cutoff;
- ambiguous LOGIN-commit evidence using the one returned derived role, and a
  held-access-clock-lock case proving rollback with no lock-order inversion;
- exact lifecycle module budget no greater than 1,325 physical lines, with
  `_create_login(...)`, `_create_or_resolve_login(...)`, and their private
  helpers split under the unchanged repository 80-line function cap and every
  other budget unchanged;
- Ruff over every changed Python path and `git diff --check`;
- mechanically regenerated canonical test inventory when collection changes;
- `python3 conformance/ofarm_pkg_contract_check.py` immediately before every
  commit;
- exact base-to-head five-path equality;
- an explicit report that differential-clock and complete-authentication
  deployment evidence is not supplied by this PR and production composition
  remains unauthorized and non-deployable pending the separate production-
  evidence and composition follow-ups; this RFC makes no universal
  reachability claim;
- two clean full Kernel baseline runs against the same isolated PostgreSQL
  clusters if the focused live suite passes; and
- hosted review, conformance, native amd64, native arm64, and canonical native
  index at the exact implementation head.

## 14. Open decisions and review disposition

Open decisions: none that may silently change implementation. Phase A review
may demonstrate a Blocker in this contract; any material authority, invariant,
path-envelope, or PR-binding change requires a new version.

Current review disposition:

- Blockers addressed inside the retained lifecycle boundary: public forgeable
  closed result; cross-clock authentication extension; unobserved raw
  authority-time regression; the decision-v2 `A3 -> H3` observation order that
  could double-count inter-observation delay; the decision-v3 absence of a
  bound on post-`A3` authority-minus-database divergence; the decision-v4 false
  equality and pre-SCRAM-expiry-check assumptions; the initial decision-v5
  PostgreSQL source-provenance gap, now pinned to the supported `REL_17_10` tag
  and exact authentication functions; and the decision-v5 300-real-second
  proof-domain gap, now corrected by the complete credential-relevant interval
  premise.
- Whole-card review clarifications incorporated: commit-ambiguity carrier
  return semantics; the exact live-`clock_timestamp()` premise; database-ahead
  derivation provenance; lagging-database `2d` delay cost and consumed-failure
  posture; explicit module-budget change; unambiguous regression notation;
  held access-clock lock evidence; and AST node-kind scope for the private-
  symbol checker. The decision-v5 bounded clarifications also specify the
  runner-rule AST and test-module scope, authentication timer-slot
  independence, the exact availability floor and its RFC-local operator
  guidance, client `connect_timeout` limits, the interval-form divergence
  premise, and the required under-cap `_create_login(...)` helper split.
  Decision-v6 clarifications distinguish upstream `REL_17_10` from the accepted
  pgdg artifact and make repository version-policy changes the mechanically
  checkable source-semantic re-verification trigger.
- Review
  [#5023619512](https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5023619512)
  is a valid Blocker against decision v8: its application-only root set omitted
  documented release and operator entrypoints, including
  `deployment.postgresql.run_security_audit_migrations`. Extending that rule
  correctly would require a governed classification of all relevant execution
  roots and a capability policy across them, so decision v8 is withdrawn rather
  than patched across a second trust boundary.
- Review
  [#5023671963](https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5023671963)
  correctly identifies repository-wide source admissibility as a separate
  trust boundary. Its suggestion to return to decision v5 is not safe because
  review
  [#5021156140](https://github.com/samovers/OFARM2/pull/333#pullrequestreview-5021156140)
  found the complete-interval B-6 gap in that version. Decision v9 therefore
  retains the complete-interval premise and all other lifecycle corrections,
  while withdrawing—not claiming to satisfy—the broader B-7 through B-10
  source-governance surface introduced in decisions v6 through v8.
- Remaining Blockers: no known version-9 Blocker; independent exact-head Phase
  A review is pending and may demonstrate one.
- Follow-ups: unchanged decision-v1 output custody, broader crash-operation
  evidence beyond the required in-flight authentication case, final hostile
  cross-slice evidence, production prerequisite evidence, and issue #192
  closure audit. The future output-custody composition must resolve how it
  annotates the private result without widening this PR. Section 6.2 is the
  authoritative home for prompt-use guidance; no additional path is required.
  Issue #334 retains its reachability-residue work. A separate source-integrity
  decision must define the complete execution-root classification, package-
  initializer reachability model, and source-capability policy before any such
  guarantee can authorize production composition.
  Phase B remains non-deployable until the separate production-evidence
  follow-up is complete.
- Preferences: none.

### Required exact approval form

The only valid approval form is the entire visible text of a later task-user
message in this same Codex task:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-TEMPORARY-EXPORT-LIFECYCLE-001 version 9.
```

No generic approval, shortened version label, GitHub activity, review result,
CI result, tool message, or predecessor approval authorizes Phase B.

Decision-draft sequencing is mandatory: run only required cheap local checks;
push and freeze the exact head; obtain an independent exact-head content review
with zero Blockers; only then run or monitor expensive hosted baselines; and
present the approval form only after those hosted gates are green.

Merge stop rule: Phase B implementation begins only after the exact later task-
user approval for this decision version and its named draft PR. Merge remains
blocked until every approved invariant passes, an independent exact-head review
demonstrates zero Blockers, all subsequent exact-head hosted gates pass, and the
complete diff equals the approved technical allowlist. New ideas and
Preferences remain Follow-ups and do not widen this PR.
