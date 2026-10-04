# Bounded signing-authority observation — approved design and implementation candidate

**Recommendation:** retain one `SigningAuthorityReader` and its validators. Bound pinned psycopg 3.3.4's normal query execution through a small `Connection.wait` override. Add only the connect-ownership bridge needed to dispose an incomplete connection explicitly. Reuse psycopg's query generators, cursor and Transformer; do not implement a second query protocol or scalar loader.

Primary trust boundary: **signing-authority observation integrity and availability**. Delivery [#406](https://github.com/samovers/OFARM2/issues/406), under [#167](https://github.com/samovers/OFARM2/issues/167), is the separate prerequisite blocking [#404](https://github.com/samovers/OFARM2/issues/404) / [PR405](https://github.com/samovers/OFARM2/pull/405) PS11. Decision `OFARM2-SIGNING-AUTHORITY-OBSERVATION-001` version 2 received the exact task-user approval on 4 October 2026, after the corrected Phase A at `6ca04c8ef92523e4c73c3fd1d2a42f192c2b6b3b` and its zero-blocker focused design review. That approval accepts H1 for provisional development and authorizes this complete PR407 implementation candidate. It does not grant final technical acceptance, baseline admission, merge or deployment. Runtime code, focused controls and mechanical companions remain one candidate in the same draft.

## Problem, capability and boundary

The current reader opens a blocking connection during startup and capability minting. Losing the authority-query response, or the connection-context COMMIT response, can prevent the caller from regaining control. PR405's observer also depends on this mint path. The capability is a fresh, fully validated authority observation or a finite refusal with all owned client I/O resources disposed under the supported profile.

Permit one total reader deadline, cancellation input, bounded socket waiting, owned connection/file disposal, an early static support check and narrow issuer/runtime wiring. Preserve the database observation function, column inventory, authority predicates, receipt signature/canonicalization/freshness/equality checks, credentials, KMS custody and existing runtime observation refusal classes. The new static configuration refusal is distinguished below. No database writes, grants, migrations, key changes, principal or tenant decisions, audit mapping, public routes, readiness predicates or authority clocks change.

The complete proposed slice owns the reader, its transport/file helper, the mechanical wait, issuer keyword propagation and pre-sign check, and necessary construction in `application_runtime.py`. PR405 owns its caller integration and observer policy. A mechanical wait may be shared; signing and transaction decisions may not. No worker, process, asynchronous application conversion, cache, retry, alternate authority path or general transport framework is selected.

## H1 is a whole-runtime support choice

`application_runtime.py` supplies the same `config.pg_dsn` to the principal resolver's factory, the signing reader and the tenant pool. Startup calls the reader. **H1 therefore constrains the existing shared `OFARM_PG_DSN` and can prevent the entire production runtime from starting.** Today `RuntimeConfig` checks DSN syntax, not this support profile. A hostname-only or multi-route DSN accepted today may fail H1. No claim is made that current deployments already comply.

Propose exactly one explicit DNS-free endpoint and numeric port: a numeric `hostaddr` paired with the original hostname, a literal numeric host, or one explicit absolute Unix socket directory. A paired hostname remains the TLS/authentication identity for that endpoint; it must never be replaced by its IP or stripped to obtain a connection. Preserve credentials and requested TLS checks. Refuse host/hostaddr/port lists, empty or default routes, mismatched pairs, service expansion and environment-only or unresolved endpoint selection. Never choose a list's first member, resolve/cache a hostname, invent deployment values, weaken authentication or mutate the process environment.

The side-effect-free signing-support preflight parses the DSN and relevant `PG*` inputs, freezes explicit admitted reader parameters and rejects hidden service, DNS or external credential work before calling libpq. Its closed profile must account for libpq defaults and authentication settings as well as route text; `hostaddr` alone is insufficient. GSS/Kerberos, OAuth, interactive TLS-key callbacks or other external facilities are outside this profile unless their absence of blocking external work is established by the admitted configuration. Unsupported or uncertain configuration refuses; it is not silently downgraded. Credentials/TLS/password configuration and receipt files must use healthy local storage and noninteractive facilities. No remote/FUSE-storage guarantee is claimed.

Place this pure preflight at the beginning of `build_application_runtime`, after config type/mode validation and **before image checks, HTTP/KMS clients, connection factories, pools, resolver/verifier/audit initialization or file/network I/O**. A private `SigningObservationConfigError` maps there to the existing `RuntimeConfigurationError`, using a safe message without the DSN. Do not defer this to `current()` and report generic database unavailability. The generic `RuntimeConfig` syntax parser stays unchanged. No new DSN setting is selected; the principal resolver and tenant pool retain their original shared DSN/factory and decision logic. `create_app` builds this runtime before constructing the production FastAPI application, so a static H1 refusal creates no application or published readiness state. This is a configuration support restriction, not a new server-readiness or deployment-admission authority.

Pure parsing cannot attest a mount's locality or health. Healthy local open/read/close, finite driver CPU work and host scheduling are explicit support assumptions; a socket deadline cannot interrupt a hung kernel or storage device. Later receipt absence, bad file kind or I/O failure remains an observation refusal. Supported-route connection/TLS/credential failures likewise remain runtime unavailability, not static configuration errors. Actual configuration-file opens must remain within the admitted local profile. The preflight and frozen explicit parameters must not leave a later ambient route/default expansion that can escape H1.

**Approved version 2 H1 scope:** the entire production runtime may require its shared `OFARM_PG_DSN` to identify one explicit DNS-free endpoint, refuse multi-route/service/environment-only routing and external authentication callbacks, and require healthy local receipt/configuration storage, with unsupported static configuration rejected before startup resources exist. The approved version 2 decision also authorizes provisional implementation in PR407. Wider support requires a new design/support decision. The earlier reader-only question and version 1 are superseded; final technical acceptance remains separate.

## One deadline and mechanical wait

Retain `current(kid)` with optional keyword-only `cancel_event` and `deadline_monotonic`. Every call receives a mandatory **5-second total reader budget**, shortened by an earlier caller deadline. Reject invalid timing inputs; they must never disable or extend the owner limit. The same absolute monotonic deadline covers connection setup, query/drain, disposal checkpoints, receipt read and validation. It never restarts per stage, wait or address. Database `observed_at_us`, not monotonic time, continues to govern authority/receipt time validation.

Propose `kernel/postgres_wait.py`: one small function taking a Wait-yielding generator, a current-socket getter, an absolute deadline and an optional cancellation event. It owns the generator and selector, not a connection, lease, SQL statement, identity or refusal policy. Poll for at most `min(50 ms, remaining budget)`, checking before and after waits and generator advancement. Handle read/write combined readiness, empty polls and descriptor changes by refreshing registrations from the getter after every relevant yield. Close the generator and selector on every exit, including `BaseException`, without letting failure in one cleanup skip the other. A private stop exception lets each consumer apply its own refusal policy.

Psycopg has two generator protocols: stock connect yields `(fd, Wait)` and returns a PGconn; established query generators yield `Wait`. Do not pass the stock connect generator into the query driver. S1's connect-only bridge instead yields `Wait`, with a getter for its explicitly owned handle's changing socket, and returns no newly hidden resource. Query completion returns through psycopg's normal cursor path. Any resource-bearing completion must already have a disposal owner before a final deadline/cancel check can raise. No last-moment expiry may strand a just-completed result or connection.

`_BoundedConnection.wait` delegates directly to this function and never enters stock `Connection.wait`'s interrupt/cancel-and-wait-again handler. Preserve psycopg's normal connection locking. A calling thread exclusively owns each S1 connection; no timer thread closes it while libpq executes. No cancellation request or remote acknowledgement is needed to stop this disposable read. PR405 may reuse the same mechanical wait under its own connection wrapper, deadline and lease/disposal policy. S1's connection subclass is not installed into the principal factory or tenant pool by this Delivery.

## Explicit connect ownership and ordinary query execution

Pinned Python `_connect` and the actual exported Cython `connect` create a PGconn internally and expose it only after success. Their timeout path lacks an unconditional finish-finally; the initial BAD error can retain `.pgconn`. `_connect_gen` constructs a Connection only after that return. Closing an outer Connection cannot dispose a handle it has not received. Generator destruction or eventual garbage collection is insufficient while a generator, exception or traceback remains reachable.

The narrow adaptation is therefore an outer owner that calls `pq.PGconn.connect_start` and immediately holds the returned handle, then drives a small `connect_poll` bridge. The reader creates a nullable raw-handle/wrapper owner and activates its cleanup scope before the helper acquires anything. The helper assigns directly into that owner; ownership covers the first poll, bad status, descriptor changes, expiry, cancellation, success and Connection construction. Failed `connect_start` itself is subject to the pinned binding's allocation contract; test that boundary too. Do not inspect generator frames or recover ownership from exception internals. The bridge issues no SQL and duplicates no query/result machinery.

On successful polling, set nonblocking mode and construct the reader-owned `_BoundedConnection` with that same handle. Keep the same reader-owned cleanup responsibility active across construction and helper return. The returned wrapper is borrowed within that scope; there is no transfer flag or unowned return window. Cleanup selects wrapper close after construction, otherwise native finish. Construction failure, a boundary cancellation or an exception retaining the handle must still leave it explicitly disposed. Keep an established connection nonblocking through finish; partial-connect sockets retain libpq's nonblocking setup. Actual loaded libpq/TLS disposal under failure is an acceptance obligation, not proved merely by a source reading.

Configure autocommit and `prepare_threshold=None`; use an explicit cursor and the unchanged parameterized `_SIGNING_AUTHORITY_QUERY` with `(kid,)`. Psycopg performs query conversion, send/flush/consume, result drain and normal loading through its cursor/Transformer. Disable access to pipeline, COPY, streaming, executemany, arbitrary SQL callbacks and connection sharing in this fixed reader path. No custom OID map, encoding conversion, raw result parser or copied field list is introduced.

Require one complete result, exact projection derived from the existing column inventory, exactly one row, no extra result set and transaction status IDLE. Use ordinary cursor description/cardinality/nextset checks and the existing `SigningAuthority.from_database_row(row, kid)`. A row and CommandComplete without ReadyForQuery is incomplete: psycopg's query generator has not finished draining. No authority is eligible until normal execution completes. This single SELECT runs in autocommit; the observation function remains read-only. Use `closing(connection)` or explicit `finally`, never the Connection transaction context manager, which could add COMMIT/ROLLBACK waits.

Close the cursor, generator/selector and connection on every exit with nested cleanup so one failure cannot skip another. One owner invokes native finish; closed wrappers may remain in retained exceptions but must contain no live connection or descriptor. Connection close is local disposal, not proof that the remote backend immediately stopped. Do not retry SQL, reconnect, return this connection to a pool or await remote cancellation. Receipt work begins only after database disposal. Cleanup failure suppresses success and must be covered against the actual binding; it is not evidence that a retained live resource is acceptable.

Preserve a safe public refusal without retaining a raw driver exception, DSN or its traceback as the public error's context/cause. Complete cleanup and exit the handler before raising the sanitized refusal; `raise ... from None` alone does not remove `__context__`. Retained internal failure objects must also refer only to disposed I/O objects. Immutable result/diagnostic memory may remain referenced; the guarantee is explicit disposal of live client I/O, not immediate garbage collection of every Python object. Process-control exceptions such as KeyboardInterrupt/SystemExit clean up and propagate.

## Receipt, publication and real callers

Read the configured receipt afresh after database disposal. Activate a nullable descriptor cleanup scope before open. Open with nonblocking and close-on-exec flags; `fstat` must identify a regular file. Read at most `SIGNING_EVIDENCE_MAX_BYTES + 1` (16,385 bytes) and close the descriptor in `finally`. Check cancellation/deadline around admitted local operations. A symlink's resolved target must meet H1; file kind alone cannot prove locality. Keep existing size limits, `SigningEvidenceVerifier.verify(receipt_bytes, now_us=authority.observed_at_us)` and `authority.require_receipt(receipt)` unchanged. No cached-good, startup-only or remote receipt fallback is allowed.

Check cancellation/deadline again after validation and cleanup, immediately before returning the immutable authority. Timeout/cancellation and supported transport/file failures map to `SigningAuthorityUnavailable`, with the existing issuer `CapabilityMintError` translation. Preserve exact authority/receipt refusal predicates. Never log credentials, raw evidence, DSNs or raw SQL errors.

`TenantCapabilityIssuer.mint` forwards the optional timing/cancellation keywords and checks them again immediately before KMS dispatch. An observed stop prevents dispatch; cancellation after dispatch cannot undo the existing finite KMS RPC. No custody or KMS timeout policy changes. The existing minter protocol at `tenant_uow.py:38–45` and production mint call at `:436` currently lack these keywords. **#404/PR405 owns that protocol, call-site handoff and tenant-group budget**, including its real observer acceptance. This RFC establishes the producer interface only and does not edit those files or prescribe whether an observer is reserved or fresh.

Remove the proposed separate eight-reader semaphore. Current production mint calls run under the eight-lease tenant pool; startup is sequential. Each call owns at most one authority connection, one selector and one receipt descriptor, with no worker after return. This is per-call ownership, not a new global admission guarantee. Test the reachable production concurrency and repeated failure disposal. A future independent caller must own its admission rather than inherit a claimed ninth-call rejection that production does not currently need.

## Threats and complete implementation budget

Trusted inputs are the admitted route/local storage, pinned driver, host scheduling, existing database function and receipt verification key. Treat network availability, partial/malformed/duplicate results, stale/conflicting receipts, supplied kid and cancellation races as untrusted. Timing may shorten work but never authorize signing. Database-owner or in-process compromise and a hung local kernel are outside H1. Network response loss is included. One reader, one authority fact and one validator path remain; no principal, binder, signer or receipt authority moves.

The source measurement is **997/1,000 lines** in the capability-signing group. The complete prospective budget includes all owned integration, not just a new helper:

| Group member | Measured lines | Proposed contribution/ceiling |
| --- | ---: | ---: |
| `signing_receipt.py` | 221 | 221 unchanged |
| `signing_authority.py` | 212 | existing 250 ceiling |
| `google_kms_signer.py` | 89 | 89 unchanged |
| `tenant_capability_issuer.py` | 161 | existing 180 ceiling |
| `key_control.py` | 314 | 314 unchanged |
| new `postgres_wait.py` | 0 | 70 |
| new `signing_authority_io.py` | 0 | 180 |
| Complete owned allowance | 997 | 1,304 within proposed **1,310** group ceiling |

The 180-line S1 I/O allowance covers the pure H1 guard/frozen parameters, connect ownership/transfer, Connection wrapper, receipt file handling and imports; indicative allocation is 60/45/20/30/25. The 70-line mechanical helper covers deadline checkpoints, readiness/descriptor handling, generator/selector cleanup and imports. These are prospective engineering ceilings, **not measured implementation or a claimed line-count reduction**. The earlier 1,260 ceiling omitted reader/issuer growth. The reviewer prototype also omitted complete route/file/partial-connect ownership integration. Reusing protocol/loading removes duplicated logic despite the more honest complete allowance.

`application_runtime.py` measures 221/230; its group measures 420/500. Keep those caps, offsetting early preflight and reader construction by deleting the superseded `_receipt_source` and old reader factory wiring. Keep the shared principal factory and generic configuration parser. Retain existing function/import/authority guards; no compression or broad exemption to make code fit. Return measured evidence and a revised budget if clear complete code cannot fit. Mechanical RuntimeBundle coverage, if required by its existing owner, records this same capability without granting readiness authority. Tests and architecture accounting travel with implementation in this draft; independent authority changes do not.

## Alternatives and finding dispositions

| Alternative | Decision and concrete invariant |
| --- | --- |
| Bounded wait over pinned psycopg | Selected for query execution. Reuses the protocol, result loading and existing locks. One helper can serve S1 and PR405 without sharing decisions |
| Direct reuse of stock `generators.connect` | Its internal PGconn is unavailable to the outer cleanup owner during incomplete connect. Use only the small explicit-ownership bridge above; no wholesale raw-PGconn query implementation |
| Raw-PGconn query/result/loader loop from v0.1 | Removed: duplicates psycopg's tested send/drain/Transformer path without supplying a missing authority invariant |
| Existing connect/statement timeouts | Psycopg already enforces a monotonic connect timeout per attempt; raw libpq poll does not. Neither a per-attempt budget nor server statement timeout supplies total query/drain/receipt cancellation or delivery of a lost response |
| TCP keepalive / `tcp_user_timeout` | Does not cover Unix sockets or an acknowledging proxy that withholds database responses. It cannot replace the client operation deadline |
| Stock interrupt/cancel or transaction context cleanup | Stock wait may cancel and wait again; Connection context may commit/roll back. Both add remote waits outside the selected disposal contract |
| Stop waiting for a blocking thread | Leaves the operation/worker alive and permits accumulation or late results |
| Isolated per-call process | Could own broader blocking facilities but adds lifecycle and result transfer. Not needed for proposed H1; reconsider explicitly if that support profile is rejected |

B1 is addressed by the selected wait/normal-query path and the specific partial-connect exception. B2 is addressed by the whole-runtime H1 statement and early pure configuration refusal. FU-1 is addressed by complete measured/prospective accounting; FU-2 is traced to #404/PR405's actual minter protocol/call site. P-1 removes the semaphore, P-2 corrects connect-timeout claims, and P-3 records TCP limits. The focused exact-head Phase A review at `6ca04c8ef92523e4c73c3fd1d2a42f192c2b6b3b` reported zero design blockers. Runtime evidence and independent implementation review remain distinct obligations.

## S1 falsifiable acceptance controls

Required implementation acceptance uses pinned Python 3.12.13 and psycopg/psycopg-binary 3.3.4 in the required Linux baseline against PostgreSQL 17.10, the real `ofarm_app` function/role and signed fixture receipts. Record the actual loaded libpq/TLS versions and supported platform. Local inspection found libpq 180000; that is not all-platform acceptance. No test may replace authority verification with unconditional success.

| ID / invariant | Required control |
| --- | --- |
| S1-01 equivalent authority | Positive admitted route returns the same complete immutable authority using normal psycopg UUID/int/bytea/text and connection encoding. Existing negative authority/receipt cases still refuse. Pin the wait/generator contract so a driver upgrade cannot silently change it |
| S1-02 partial-connect ownership | Interrupt before first yield, during TCP/startup/TLS, at poll success and Connection construction/transfer. Cover external stop, generator-raised error/timeout, BAD OperationalError with `.pgconn`, KeyboardInterrupt/SystemExit and cleanup failure. Retain exceptions, context/cause/tracebacks and generators while proving all PGconn/client descriptors and selectors already disposed. Exercise changing fds and connect_start failure; no GC or frame-inspection disposal |
| S1-03 lost authority reply | After real connect/query dispatch, withhold the reply. Refuse at the 5-second total limit, allowing documented scheduler/local-disposal overhead, with no reconnect, worker or signing. Earlier caller deadline shortens the same budget |
| S1-04 complete result | Withhold ReadyForQuery after row/CommandComplete: refuse. Normal psycopg drain plus shape/cardinality/IDLE checks rejects duplicate rows, extra result sets, wrong columns, malformed/NULL values and partial/fatal results. No prepared/pipeline/implicit explicit-transaction path bypasses the bound |
| S1-05 cancellation and wait | Set the event before connect, at every poll/local boundary, after row receipt and before publication. Poll observes it within 50 ms plus scheduling; no result/signature. Exercise read/write combined readiness and empty polls; stop and selector errors still close generator/selector and their connection owner |
| S1-06 local disposal with TLS | Withhold completion and black-hole peer reception during finish on the actual loaded libpq/TLS. Keep established connection nonblocking. No COMMIT/ROLLBACK/cancel exchange, open client fd or selector survives, including retained query failures. Check nested cleanup failures. Do not infer remote backend termination |
| S1-07 final race | Race generator completion/ownership transfer, validation, deadline and event. Owned completion is transferred or disposed before a final stop can raise; no late result revives a failed call. Authority clocks stay database-derived. Returned authority/KMS dispatch is not falsely described as retroactively revoked |
| S1-08 exact receipt | Fresh read every call. Preserve signature, canonical JSON, duplicate-member, size, freshness and full equality checks. Replacement/stale/corrupt/conflicting/oversized/missing evidence refuses without cached fallback |
| S1-09 local-file contract | Real admitted regular files, replacement, short reads and I/O errors; FIFO/device/directory refuse without blocking open. Close fd on every exit, including retained exceptions. Record the healthy-local-mount assumption; fstat alone cannot pass remote/FUSE/storage-hang support |
| S1-10 real concurrency and retention | Exercise eight real tenant callers under existing pool leases and sequential startup, then cancellation/disposal. Repeated failures with retained exceptions/generators must not retain live client I/O or workers. No ninth-reader admission promise or new semaphore is asserted |
| S1-11 early H1 refusal | URI/keyword forms admit one explicit endpoint/port or socket directory. Refuse lists, empty/default/service/environment-only/hostname-only DNS routes and hidden external credential/default expansion. Spy on all startup factories/clients, DNS and file/network I/O: static refusal occurs before any call. Paired numeric hostaddr retains original hostname/TLS identity; credential/certificate failure never downgrades protection or mutates environment |
| S1-12 real startup and issuer | Through `create_app`/builder, unsupported static shared DSN produces safe RuntimeConfigurationError before app/resources exist. Supported-route runtime failure retains existing unavailable/mint refusal. Positive authority reaches existing KMS verification; final cancellation prevents dispatch. Already dispatched KMS retains its current finite RPC behavior |
| S1-13 independent owners | Function/migrations, receipt predicates, keys, shared principal factory/resolver, tenant/audit decisions, readiness and generic RuntimeConfig parser remain unchanged. One reader path, no arbitrary SQL callback, unsafe driver-error exposure or unbounded fallback. H1's whole-runtime compatibility effect is explicit in the decision |
| S1-14 downstream dependency | After independently accepted S1, #404/PR405 supplies its actual event/deadline through CapabilityMinter and the real mint call. PS11 black-holes this actual reader during observer binding and regains control with both authority connection and observer disposed. Fake minter/private-state assertions alone do not pass; PR405 owns its observer and budget |

These controls remain the acceptance requirements. Focused local implementation results are recorded separately from authoritative hosted acceptance. A source/control-flow probe executed pinned Python `_connect` with a fake PGconn and clock: a retained timeout traceback kept the handle reachable, and generator.close did not invoke finish. Explicit fake-owner disposal did. This was no real socket, binary-generator, TLS, database or runtime leak test. The exact-tag Cython source independently shows the same internal ownership/timeout shape. The published reviewer reports seven fault probes on Python 3.12.3/PG16.15, loopback trust/no TLS and a stand-in authority function; those support the smaller query-wait choice but do not satisfy the real-role, retained-failure, H1 or complete-runtime controls here.

## Source provenance and review posture

Source anchors are repository `dfbceac403ac42399b0c0be06c5d6d9f92874551` (runtime equals base `bccb7a1f0cd5d4c81d21898e4b0978830904b716`) and installed psycopg 3.3.4 binary/libpq 180000. Inspected driver sources include `generators.py`, `connection.py`, `_connection_base.py`, `cursor.py`, `_cursor_base.py`, `waiting.py` and `pq/abc.py`. The [exact-tag Cython connect/query generators](https://github.com/psycopg/psycopg/blob/3.3.4/psycopg_c/psycopg_c/_psycopg/generators.pyx) confirm the loaded implementation's protocol/ownership shape; [PGconn source](https://github.com/psycopg/psycopg/blob/3.3.4/psycopg_c/psycopg_c/pq/pgconn.pyx) distinguishes explicit finish from destruction. PostgreSQL's [nonblocking connection contract](https://www.postgresql.org/docs/17/libpq-connect.html#LIBPQ-PQCONNECTSTARTPARAMS) explains DNS restrictions, changing sockets and caller polling; its [asynchronous query contract](https://www.postgresql.org/docs/17/libpq-async.html) requires complete drain. Source arguments do not replace the loaded-library TLS/disposal controls.

The prior local conditional review and original packaging checkpoint are historical. The [public review at the original head](https://github.com/samovers/OFARM2/pull/407#pullrequestreview-5405007874) raised B1/B2; neither earlier clearance nor reviewer prototype authenticates this corrected head. The corrected Phase A stayed inside signing-authority observation integrity and availability. Its checkpoint recorded the one-file design diff, source hashes, findings and package/architecture/whitespace checks. That historical design checkpoint did not claim runtime tests or H1 acceptance; the later decision and implementation state are recorded below.

## Implementation candidate record

The approved design source SHA-256 was
`516fa6a5e2f187aa481c56ed861bc3c7dbf2c207df7d82e764d8e35577fe5789`.
Original approval references are card turn `01a1060a-c89a-7461-8938-8318973eb258`
and later approval turn `01a1064a-d9d1-7ef3-8f9d-6b2668d4c48d` in coordinator
chat `01a0aab4-3ce9-7540-abf2-41bc78b859b3`. The implementation stays inside
signing-authority observation integrity and availability; there is no
cross-boundary exception.

The reader now uses one explicitly owned partial-connect bridge, normal psycopg
query/cursor loading, the mechanical wait and a fresh bounded regular-file receipt.
`read_signing_receipt(path, *, deadline, cancel_event=None)` checks the same owner
budget around every short read. A small shared disposal context always attempts
cleanup and preserves an active process-control BaseException through ordinary
cleanup errors; cleanup error after success still refuses. Sorted prepared parameters are stable when checked
again at connection time. Numeric host/hostaddr mismatches refuse before startup
resources. The concrete admitted credentials/defaults profile is documented in
`kernel/README.md`; local configuration-file health remains an H1 assumption.

Measured complete source sizes are 221 receipt, 234 reader, 89 KMS signer,
179 issuer, 314 key control, 69 mechanical wait and 179 signing I/O: **1,285/1,310**
for the signing group. Runtime is **218/230**, with its group **417/500**.
The largest changed functions are `_prepared_options` at 70 lines,
`TenantCapabilityIssuer.mint` at 68 and `build_application_runtime` at 80;
existing function limits remain unchanged. The earlier table records the
pre-implementation measurement and prospective allocation, not current sizes.

Existing signing/issuer/runtime tests use explicit test-only I/O seams. Real
signing fixtures now write a receipt in pytest-owned temporary storage and use
the production prepared-conninfo reader. New independent acceptance tests target
S1-01 through S1-13. S1-14 stays with Delivery #404 / PR405. No production
`tenant_uow.py`, database function/grant/migration, generic configuration parser,
receipt predicate, key custody, audit or readiness authority changes.

Focused local evidence uses Python 3.12.13, psycopg/psycopg-binary 3.3.4,
libpq 180000 and its bundled OpenSSL 3.5.4 on macOS arm64 against isolated
PostgreSQL 17.10 with the real function/role and signed fixture receipts. It is
not the authoritative Linux x86_64 hosted baseline or final human acceptance.
The complete candidate handoff records exact commands, outcomes, source hashes,
size measurements and remaining controls; no hosted baseline was launched here.

### B1 acquisition and handoff correction

The one full implementation review of `3f43bbdce6ae0f27423c5a921b31affb2a45d7f5`
found one Blocker: actual SIGINT could arrive after native acquisition but before
cleanup scope entry, or after a transfer flag disabled cleanup before return.
The correction installs nullable connection/cursor/selector/receipt ownership
before acquisition and keeps the connection owner in the caller throughout helper
return. It removes the transfer flag rather than moving it. Existing cleanup
exception precedence, H1, query/validator behavior and authority boundaries remain.

Twelve added controls use native resources and retained errors: eight actual SIGINT
acquisition/return cases (including the Python return event and cursor), plus four
pre-acquisition failures with empty slots. Probe containment runs only after
product-disposal assertions. This correction requires focused B1 re-review at its
new exact head; the earlier full review and local passes do not close B1 themselves.

The existing pinned-driver acceptance case emits exactly one fixed JSON record
with marker `OFARM2_SIGNING_OBSERVATION_CLIENT_RUNTIME ` through
`capsys.disabled()`. It records libpq version, psycopg implementation/version,
platform system/machine and OpenSSL_version resolved through the already loaded
`psycopg_binary.pq` extension's dependency handle, after asserting that handle's
PQlibVersion equals psycopg's loaded version. It records no DSN, credential or host
path and does not substitute Python ssl's separate library version. The unchanged
baseline runner inherits stdout; both admitted Linux run records must be retained
and authenticated with their job-log digests by the existing evidence process.
No baseline envelope/schema, workflow or publication-policy change is introduced.

Next: finish correction checks, freeze its exact head for B1 and the runtime-metadata
companion's focused re-review, and obtain the required later acceptance.
