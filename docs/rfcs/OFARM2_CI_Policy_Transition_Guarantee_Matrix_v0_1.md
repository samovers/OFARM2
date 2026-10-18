# Version-4 guarantees, explicit limits and required controls

This is the implementation acceptance plan for the approved [transition decision v4](OFARM2_CI_Policy_Transition_RFC_v0_1.md), [Delivery #416](https://github.com/samovers/OFARM2/issues/416). The rows remain implementation acceptance obligations. Local controls and tool diagnostics do not replace complete hosted acceptance. Every positive fixture must be complete enough to reach the named real validator; a negative earns credit only for the intended refusal. Synthetic admission, grant, workflow and identity fixtures must use fictional identities/data. Separately identified measurements of authenticated public dependencies retain their real public facts and provenance; they do not alone earn complete-G25 credit or permit fabricated signatures, secret disclosure or real personal/farm data in fixtures.

| ID | Guarantee and owner | Reachable negative case and expected refusal |
| --- | --- | --- |
| G01 | Human owns semantic/root authority; T pins the delegated operator numeric ID and repo ID; external verifier consumes original same-task evidence | A standing collaborator self-names in a plausible projection or supplies an admission/binding, or a different account pushes: the cheap gate refuses before producers. Missing original ordered user approval also prevents operator activation and external acceptance even with a valid receipt. |
| G02 | External packet fixes T/tree/closure and B | Candidate receipt chooses another root; activation ref moves; an imported helper differs; generator input changes: gate/consumer refuses rather than following branch/latest receipt. |
| G03 | Only named #413/#411 at exact H/B/M is eligible | Other PR, another repo, swapped base/head, wrong parents, returning head after mutation, close/reopen: admission, guard, handoff, seal and final consumer refuse. |
| G04 | Closed true workflow provenance | Forged main ref/event; wrong workflow/path/SHA; old ordinary gate supplied transition event; new wrapper triggered on prep/main/tag: refuse. Old path still rejects transition evidence. |
| G05 | At most one source and one publisher per grant, attempt1 | Concurrent activations, recreated ref, deleted/replaced binding, repeated acceptance for another tuple, attempt2, lost journal: refuse; original durable run binding cannot be rebound. |
| G06 | Immutable created admission/bindings with current standing | Edit/delete/minimize after gate; author loses standing; duplicate/late binding or incomplete pagination: refuse/cancel and no valid ticket/receipt. |
| G07 | Explicit live revocation for actual transition event class | New transition class reaches old `_ensure_no_live_revocation` early-return hazard: dedicated negative must prove the transition's real shared/adapter check refuses instead. Existing exact-head revocation is also a veto. |
| G08 | Current grant state at every decisive transition | Revoke between admission and producers, producer completion and handoff, source and publisher, validation and seal, packet and merge: no later stage accepts. Poll/cancel/API failure cannot become success. |
| G09 | Fixed lifetime and fail-closed cancellation; explicit 120-second tick/15-second sweep deadline | Clock after expiry/sunset; guard hangs, skips or lacks cancel permission; publisher guard finishes too early: fail overall source/seal. A missed tick or deadline fails; no stale-success continuation. Detection is bounded to 135 seconds plus provider cancellation latency. No guard/handoff dependency cycle. |
| G10 | Producer/privileged-runner isolation | Candidate attempts to read trigger credential, write policy checkout, use guard token/cancel another run, inject job-output commands or share workspace/cache: no credential/path exists; typed bounded data only. Structural workflow checks verify permissions and checkout roots. `actions: write` is repository-wide; only T code confines its use to the current run, and actor pins cannot distinguish sessions sharing that account. |
| G11 | Original complete workload and finite60 envelope, with the retained version-3 tool controls and fixed version-4 coverage declaration | Generator changes anything beyond the closed event/provenance and tool-control rewrites, narrows pytest, adds retry/continue-on-error, changes a pin or substantive validator, widens a timeout, splits clusters or reorders substantive work: generation/parity fails. Exact checks enumerate the Node/Git controls, four curl retry removals, private gh relay steps/environment and root-bound coverage assertions. A hostname, candidate label or failure cannot reclassify a protected operation. |
| G12 | Every candidate test, warning, phase and source attribution is accounted for | Missing selected node, added unreviewed inventory drift, deselection, skip, unavailable, xfail/xpass/error/warning mismatch, dirty/mutated Git tree: unchanged baseline validator refuses. P's own additions must later be tested in P. |
| G13 | Two independent full executions on same actual environment | Reused first output, second missing/failed, different DB system IDs or runner image, altered produced artifact, false producer `equivalent:true`: unchanged comparator and independent publisher refuse. Fixed four volatile pointers stay fixed. |
| G14 | Original platform23 and both native architectures required | Missing platform case; one missing/failed native architecture; invalid sanitizer/attestation/reproducibility/currentness; native index built from producer assertions: unchanged validators refuse. |
| G15 | Frozen release/currentness claims stay within their accepted contract | Native sidecar or frozen identity altered to make wrapper appear current, transition closure used to broaden release authority, stale authority file: refuse/scope stop. Additional CI closure does not replace native checks. |
| G16 | Exact source inventory and trusted ticket last | Producer pre-squats ticket; extra guard/debug artifact; missing provisional; ticket before producers/guard finish; source not wholly successful: handoff/publisher refuses. |
| G17 | Separate successful publisher at identical approved T | Publisher in same source run, other T, attempt2, unbound source/ticket, latest-success lookup, another run's artifacts: refuse. |
| G18 | Download custody and untrusted archive safety | Bad digest/size, non-HTTPS artifact redirect, any authenticated source-reader redirect, traversal, symlink, hardlink, special file, duplicate, extra file or source blob mismatch: existing download/extraction/source-reader validators refuse before any executable content is used. |
| G19 | Published native index comes only from re-authenticated evidence | Substitute architecture artifact after upload; wrong published ID/digest; stale/fabricated index: publisher/seal/consumer refuses. |
| G20 | Receipt last, exact and complete, with real transition authority | Five labels exist but seal/publisher fails; wrong source or published digest; forged success; extra/missing artifact; ordinary receipt schema used: external consumer refuses. |
| G21 | External acceptance cannot trust itself into authority | Receipt supplies its own root/grant or consumer imports candidate code; original approval unavailable; journal says a different/spent tuple: refuse despite data validation passing. |
| G22 | Native merge remains human-gated and expected-head | No later exact authorization, expired/changed packet, changed base/head, new required status or native rejection: no merge; no admin/direct writer/status forgery. |
| G23 | Retirement is effective and auditable | New grant after411 merge; reuse after consumer merge; old activation branch after sunset; missing archived root: no new live acceptance. Preserve history; retire active workflow paths in P's final normal-tested revision. |
| G24 | No substitution among PRs, roots or acceptance runs | #413 suite credited for P's new tests, old45 partials combined, P accepted without its own main60 run, old grant reused after rebase: final packet refuses. |
| G25 | Complete protected-operation accounting, first-403/429 refusal and live quota headroom; explicit dependency/provider and ambient limits | Actual generated source60 + handoff10 + publisher/seal protected positive path, long-guard ceilings and adversarial windows must fit 15 REST/5 points per periodic sweep plus whole-grant450/200 nonperiodic pools. At most31 sweeps plus75/75 margin gives a990 REST/430-point protected planning envelope, not a verified all-traffic ceiling. Missing/insufficient headroom, protected extra page/cost/call, deadline or403/429, GraphQL errors/incomplete required data even at HTTP200 and protected secondary throttling refuse. Exception forgery or coverage drift refuses. Unknown provider/dependency totals are disclosed, never assigned zero or counted as proven inside the margin. |

For revised G25, exit0 of a protected tool is not proof of no throttle. Reach first403/429 in every actual protected tool path, including a losing REST/GraphQL lookup and a genuine signed blob under a failed HTTP status; trusted step/job disposition must refuse. Prove complete positives through the unchanged native helper with actual pinned gh and no stderr filter. Exercise missing/changed private config/socket, direct-route fallback, wrong TLS identity or supplied CA, unknown/hostile route/header/body/trace, pagination and point overruns, canceled/late requests, supervisor failure and cleanup. Preserve every actual CLI stderr byte and the authenticated underlying path. T's relay now authenticates upstream HTTPS and sees forwarded credentials transiently; no new root/principal or credential persistence is allowed. The full frozen native check and complete generated source/publisher G25 controls still must pass before activation.

The pool-overrun rule refuses acceptance; it does not claim that asynchronous observers prevent every excess dispatch by a failed attempt. Actual primary quota headers remain mandatory for the workflow token and every known applicable bucket. Other protected transports have separate request/byte/time caps without fabricated provider headroom. Every actual protected call still needs conservative attribution, including failed/in-flight work and cancellation. Fresh quota snapshots do not attribute hidden traffic or reserve capacity. Provider use of the job token and ambient consumption may exhaust headroom and cause refusal; no universal request bound or availability guarantee remains.

## Required version-4 coverage and exception controls

The RFC's closed operation inventory is authoritative for this implementation. Protected operations are T-owned Python policy/API/source/artifact/publication/acceptance readers; pinned Node Actions and selected child Git after trusted bootstrap, including reachable post paths; the four retry-zero curl executions; and the complete native command, including its five gh phases, surrounding API metadata reads, GraphQL, TUF, signed blobs and assets. Setup-python's Node manifest/tree/blob/archive downloads stay protected. There is no dependency exception for evidence transport or native authentication.

The named exceptions are provider-process provisioning, runner/image/tool-cache/Action preparation and control/logging/reporting before, during and after steps; the Python archive installer and unversioned pip bootstrap plus the four canonical conformance pip installs; Docker daemon/Buildx's retained BuildKit bootstrap/local-image fallback; BuildKit's pinned frontend/base/scanner acquisition and checksum ADD inputs; and the pinned scanner's existing internal analysis. Preserve the RFC's exact commands/pins/configuration, including both architecture operations, core-only scan target and existing image/file/SBOM catalogers. No new enrichment, selector, URL, credential forwarding, retry loop or timeout is added. Arbitrary candidate/unrelated traffic is untrusted ambient activity, not an authorized dependency exception. Candidate outputs can depend on network input; the original validators, not an asserted egress sandbox, decide their acceptability.

| Control | Required result and evidence limit |
| --- | --- |
| First error response at a named pip index/wheel or BuildKit registry/checksum ADD path; separately invalid/truncated content | Existing recovery or valid content under an error status may pass only with all original final checks. Wrong hash/digest, incomplete output or final tool failure refuses through the actual owning validator. Reuse existing measured cases only at their recorded versions; do not invent resumption or all-path proof. |
| The same response in setup-python Node manifest/archive, checkout/Git, evidence upload/download, curl, gh/TUF/signed bundle or trusted policy reader | Protected disposition refuses even if bytes authenticate and child exits0. HTTP200 GraphQL errors/incomplete required data refuse too. No fallback into a dependency label. |
| Candidate/receipt changes coverage, hostname selects exception, or a new scanner option, pin, secret, remote enrichment or input authority appears | Closure/parity/external comparison refuses. The exact coverage declaration is fixed by reviewed T and bound in ticket/receipt. Evidence of inconsistent behavior stops recognition; unseen scanner/provider traffic is not claimed observed. |
| Provider preparations/reporting, installer bootstrap or scanner internals are not observable | Record the named reliance/limit. Missing all-provider telemetry is not an impossible preactivation gate. Still require genuine run/provenance facts and original final content checks; never assert all downloads are independently hash-pinned or scanner egress is zero. |
| Low/changing workflow-token headroom, hidden/background consumption, protected budget overrun or cancellation failure | Fresh required checks refuse as specified. No PAT substitution, quota reservation claim, all-traffic attribution by header subtraction, fresh per-job pool or wait-through-throttle success. |
| Short supervisor lifetime, startup crash, late/in-flight request, failed drain or cleanup | Refuse the protected disposition and authority. Complete generated-path controls cover source guard135/publisher guard60, all original job/gate/handoff/seal limits and one fixed grant/campaign lifetime. Deadlines do not prove internal request counts or instantaneous provider cancellation. |

G01–G24's substantive authority, custody, test and acceptance guarantees remain. G11 gains the fixed coverage declaration; G25 explicitly gives up universal first-throttle refusal, complete all-traffic accounting and an all-traffic990/430 ceiling. The known mutable Python version manifest and unpinned pip bootstrap remain disclosed provider/dependency reliance, without weakening their existing final checks. The later original version-4 approval recorded in the RFC authorizes this meaning; the earlier choice of assessment direction alone did not.

The focused suite must include one complete source→handoff→publisher→external-consumer positive chain using the existing substantive validator implementations, an ordinary-main positive chain to prove preservation, and a transition refusal through each real entry point. Workflow parity must compare generated output to its canonical input, not merely search for test command names. Review must inspect the allowlisted differences and the full authority/import closure.

Implementation needs an integration control for two gate instances competing for one grant; a durable write/read failure, torn append, stale checkpoint or rollback around every journal/public-write boundary; edited/deleted binding after its first observation; an observed replaced/deleted ref; an unobserved activation-ref move-away-and-back which must not change T or permit a second run; and guard failure/cancellation API failure while producers are active. This establishes the proposed one-use and fail-closed mechanics, not a generalized distributed lock service. The authorized single operator remains the only writer of the external journal.

After exact approval/review, real hosted installation must demonstrate actual push provenance, one source and separate publisher at the same T, all substantive jobs, complete ticket/receipt and external acceptance. No mock, source inspection, local unfiltered suite or prior historical hosted result substitutes for that evidence.

## Local implementation verification

The implemented entry points and focused controls are below. All are collected
through `kernel/tests/test_ci_policy_transition.py`; the reviewed baseline
inventory adds their node IDs and source attribution without removing an
existing test. Fictional provider responses, clocks and authority messages
remain fixtures. Existing substantive validation code runs unchanged.

| Guarantees | Owning implementation | Focused local evidence |
| --- | --- | --- |
| G01–G10, G21 | `ci_policy_transition.py`, `ci_policy_transition_operator.py` | Core and operator tests cover original exact approval, actor/root/closure selection, one-use binding, journal intent/reconciliation, torn writes and rollback, mutable or revoked authority, guarded cancellation and typed output. |
| G01, G06 comment identity | Core source/publisher gate tests | Complete positives allow endpoint-specific avatar/profile presentation while both REST responses and GraphQL independently retain the pinned numeric author. Each bound record has wrong/missing/malformed author controls and immutable-field disagreement controls which reach their intended refusal. Request counts remain unchanged. |
| G11, G25 coverage | `ci_policy_transition_coverage.py`, `ci_policy_transition_workflows.py` | Coverage cannot be widened by input or receipt. Exact canonical/generated workflow parity checks every allowed rewrite, all five bootstrap asset hashes, lifecycle entry/post steps, job isolation and retained command ordering. |
| G12–G20 | `ci_policy_transition_publication.py` | Publication tests reconstruct complete baseline/platform/native fixtures through the original validators, detect targeted source/artifact substitutions, preserve ordinary-main receipt behavior and refuse provider exceptions without printing their context. |
| G21, G23–G24 | Operator and external publication verifier | Acceptance test creates a real isolated selected Git root and durable journal, loads that root's actual authority modules, executes the generated policy sequence, verifies the complete receipt, consumes the exact tuple, retires it and audits the archived roots. A verifier from another checkout, foreign cached validator or changed executing source refuses before provider work. Low headroom, forged coverage, generic approval and mismatched journal receipt each reach their intended refusal. |
| G09, G25 schedule | `test_ci_policy_transition_integration.py` | Complete source60/handoff10/publication45 sequence, reset positions, long guards and every inclusive hour-boundary placement retain fresh checks, a single120-second grid and at most31 sweeps. Exact135/60-minute guard ceilings refuse even when the provider completes at the ceiling. |
| G25 remaining headroom | Core and integration controls | Replay measured conformance19 REST/21 conservative points and native2 REST each through their owning shared-tool ledgers into the same provider quota as policy calls. Complete positive chains include window ages1,60,120 seconds. An exact-boundary completed periodic sweep is not forecast twice; initial, unproven, foreign and future ticks cannot earn that exclusion. Tool-share overruns and insufficient fresh headroom still refuse. |
| G25 protected tools | `ci_policy_transition_tools.py`, `ci_policy_transition_execution.py`, Node/Git hooks, curl observer and gh relay | Real supervisor startup/drain/cleanup, failed and late completion accounting, missing/changed configuration, route/identity/body failures, first403/429, unknown GraphQL cost, quota/pagination overruns and fixed pool conservation. External acceptance uses the same56/10 share, not a new450/200 allowance. |
| G11, G25 workflow environment | Generator and workflow/Node tests | Independent case-insensitive mapping-key checks cover both consumers. Fixed lowercase proxy clearing uses the trusted bootstrap environment file before supervisor startup; uppercase clearing stays in step mappings. Actual bootstrap, hook and final cleanup execute with a runner-order environment model. Every later proxy override refuses before dispatch; open and partial-write failure start no process and remove created assets. The official GitHub parser separately reproduced the old validation errors and accepts both corrected workflows; this is local syntax evidence, not hosted acceptance. |

The [first exact-head implementation review](https://github.com/samovers/OFARM2/pull/417#pullrequestreview-5558535455)
identified three in-scope defects. The verifier now binds its executing modules
and imported validators to selected T, including their closure bytes. The
source-admission supervisor now retains the full600-second job lifetime.
GraphQL error, throttle and late-response paths settle independently known
costs or conservative bounds for existing requests while terminal failure
continues to prevent new dispatch and authority. Unavailable cost remains
explicit uncertainty. Focused controls cover these cases; the complete positive
acceptance fixture executes actual selected-T modules without mocking the new
binding check. These corrections preserve the approved boundary and ceilings.

Pre-admission provider inspection on 17 October exposed a separate lifecycle
count defect before either execution attempt. GitHub returned whole-history
`totalCount: 17` with no nodes for the exact lifecycle-type/since filters. The
frozen root refused this unchanged response as omitted events. Independent
queries confirmed `filteredCount: 0`, and separate type/time controls confirmed
that it follows both filters. The adapter now requests that count and retains
the complete-page check. Only an empty complete first page can pass: every
matching event still revokes, irrespective of its reported count. The provider
fixture includes unrelated history and returns the new count only when queried.
Both admission positives failed before the fix; controls cover every lifecycle
type, missing/invalid/positive counts with empty nodes, incomplete pagination,
malformed pages and inconsistent timestamps. The failed old grant is terminal;
the corrected root requires fresh review and a new exact-root user grant.

The [B7 finding](https://github.com/samovers/OFARM2/pull/417#pullrequestreview-5561838042)
followed a source-gate failure on 18 October. Authenticated list and exact-comment
responses differed only in the admission and source-binding authors' avatar URLs.
An offline replay of saved provider responses reproduces the frozen root's
whole-author-object comparison failure; the corrected validator accepts those
same responses while retaining numeric identity and immutable-field checks.
This mixed-time diagnostic establishes a sufficient defect, not the precise
internal branch behind the hosted gate's generic refusal. Fictional complete
fixtures reproduce it and cover every required record in both gate phases.
The failed grant remains terminal with one source used and no publisher used;
the repair requires fresh exact-head review and a new exact-root grant.

A further source-gate failure at root `b00c303b4d49125205a4715b1ff8abb577b71502`
remains unexplained by its generic log. Mixed-time provider-fact replay and an
offline core replay pass; the latter uses fictional event/context, quota and
transport inputs and does not reconstruct the hosted runner or token. Separate
fictional controls reproduce a discovery-clock defect: a scan starting at
second10 can return a binding created at second11 at second12, then falsely
reject it against the old time. Discovery now samples time after the complete
scan, retaining the original window and grant expiry. Source and publisher
controls cover arrivals during one- and two-page scans, the exact deadline,
late/backwards completion, grant expiry, edits and genuinely future records.
Existing immutable-binding and full-gate controls remain required.

Bounded refusal diagnostics identify only allowlisted T-owned source file/line
locations and validated integer HTTP statuses. Controls exercise the real
reader/CLI failure path, secret text in exception chains and filenames, malformed
status values, cycles, depth/frame bounds and formatting failure. Nonzero exit,
permanent refusal, accounting and absence of authority output remain decisive.
These corrections do not establish the historical refusal's cause or restore
the failed grant. The changed root needs fresh review and a new exact-root grant.

The [focused re-review](https://github.com/samovers/OFARM2/pull/417#pullrequestreview-5558614492)
resolved root binding and lifetime, then identified one remaining accounting
case across quota reset. Structural same-window validation now retains the
historical point bound before the separate fresh-headroom check refuses the
expired observation. Production begin/response controls for200/403/429 retain
the21-point bound and completion bytes while refusing headroom and new dispatch.

The [B4 review](https://github.com/samovers/OFARM2/pull/417#pullrequestreview-5559141060)
exposed missing concurrent tool traffic in the pipeline fixture. The unchanged
core refused the measured19-request conformance traffic at the first periodic
source sweep in a fresh window. The new fixture also includes the two measured
REST calls from each native job before the guard starts. All23 requests and the
21-point conservative bound now lower the shared provider quota during the
pipeline, rather than only appearing in a later aggregate report.

The correction excludes only the periodic sweep this isolated guard has just
completed from its future schedule. At an exact tick the old formula counted
that already charged sweep again; once time advanced fractionally it did not.
The guard supplies completion only after full live and producer-state checks,
bound to its own current periodic pool. Full allowances for active siblings
remain conservative because their remaining spend is unknown. An earlier gate
does not reserve capacity and provider-counter differences do not attribute
spend. This preserves version4's current remaining-plan check, fixed ceilings
and75/75 margin; some within-ceiling schedules can still refuse conservatively.
The measured complete positive path passes without removing those safeguards.

The complete local policy and external-verifier path was composed with actual
pinned Action entry/post observations, all four actual curl commands and the
complete unchanged `verify-frozen-evidence-receipt` command. The native command
validated genuine signed release bytes, current source/authority inputs and OCI
archives, returning the exact frozen provider verification digest with empty
stderr. It made56 gh requests:17 REST,1 GraphQL,33 TUF and5 blob. The former
51-request five-phase probe omitted repository identity, two release metadata
and two peeled-commit reads and is not the full-native result.

The conformance owning-supervisor composition accounts73 protected requests,
332,269,034 bytes and19 REST/21 conservatively charged points inside20/40.
The query does not return its actual point cost. The21 is an explicitly proven
same-bucket/window absolute-used upper bound, not a header-difference estimate
or an invented cost of one. Publication spends6/0 of its8/8 shared-tool share.
The complete grant composition, including external acceptance, measures324
nonperiodic REST requests and41 conservatively charged points within450/200.
Its54 periodic sweeps across the complete schedule spend640 REST/54 points;
these are lifetime totals, not a single-hour charge. Each sweep fits15/5, and
the maximum31 sweeps in an inclusive hour preserves the990/430 protected
planning envelope including75/75 margin. Separately tracked protected
transports total1,188 requests and339,980,958 bytes; primary-quota requests are
a subset of that count.

These measurements have explicit limits. The44 actual pinned Action main/post
processes across11 owning jobs ran with local TLS fixtures on macOS; the pinned
Linux gh ran with genuine signed bytes and explicitly coherent fixture quota
headers. Action/curl observations were replayed through the same production
supervisor as the full native command, with fixture liveness and quota facts.
This is protocol/accounting composition, not one generated hosted workflow.
The four curl fixtures prove transport and cleanup with small fictional bodies,
not the final binary checks. Those checks remain unchanged in the workflows.
Earlier real-provider attempts returned contradictory still-live quota windows
and correctly refused. Their cause is unknown; no final shared positive with
unmodified provider quota facts is claimed. Dependency/provider/ambient totals
remain unknown, not zero or proven inside the margin. Local observations do
not establish future workflow-token headroom or reserve quota.

The full-native composition report has SHA-256
`16b45bfb8cbd30868e9715c7d90fae125c5bf478654903399f1702dcf21a58b2`.
The review record retains the local measurement index, source hashes and
commands. Exact-head independent implementation review remains a separate
gate; all hosted provenance, substantive jobs and final acceptance obligations
above remain required before their corresponding use or merge.

Next: complete exact-head implementation review, clear the separate #413
test-harness prerequisite and consumer amendment, then prepare the distinct
exact-root activation packet. No activation or hosted acceptance is recorded
by this local verification section.
