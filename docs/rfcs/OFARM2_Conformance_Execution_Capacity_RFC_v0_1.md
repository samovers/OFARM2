# OFARM2 Conformance Execution Capacity RFC v0.1

**Status:** Phase A design proposal; not approved or implemented.
**Delivery:** [#410](https://github.com/samovers/OFARM2/issues/410), child of #167.
**Draft PR:** the single live draft PR linked from Delivery #410; its number is bound in the PR description and decision card.
**Decision:** `OFARM2-CONFORMANCE-EXECUTION-CAPACITY-001`, version `1`.
**Primary boundary:** trusted CI execution-resource policy/currentness.
**Design path:** `docs/rfcs/OFARM2_Conformance_Execution_Capacity_RFC_v0_1.md`.

## 1. Problem and confirmed evidence

The complete conformance job runs two unfiltered Kernel baselines, compares
their evidence, preserves the platform lane, and uploads provisional evidence.
Its existing finite 45-minute job allowance can expire before this completes.
[Source 38716305726](https://github.com/samovers/OFARM2/actions/runs/38716305726)
and [fresh source 38722919197](https://github.com/samovers/OFARM2/actions/runs/38722919197),
both attempt 1 at PR409 head `75d881159c4fe353fecc0cbbf3abb32309353926`,
were cancelled with GitHub's exact 45-minute job-limit annotation. Their first
pytest runs each passed 5,322 tests with one expected warning in 1,399.00 and
1,372.68 seconds respectively. Both repeat runs were cut off; equivalence and
the platform evidence lane did not complete, and publication handoff was skipped.
Both native architectures passed in each source. Neither source has complete
authenticated publication; these partial results cannot replace required gates.
Further identical attempts are stopped. This design does not authorize one.

Earlier unchanged test prefixes were substantially slower than
[successful main source 38698001002](https://github.com/samovers/OFARM2/actions/runs/38698001002).
The new 58-case runtime suite fits within a 44.9-second enclosing hosted window.
No sufficient fixture saving preserving coverage and isolation was demonstrated.
These observations support a capacity diagnosis, not proof of its root cause.

## 2. Capability and proposed decision

Permit the existing conformance executor up to 60 minutes, retaining a finite
ceiling, the complete test/evidence contract, and all current authorities.
Observed throughput projects approximately 49–50 minutes for the job; 60 offers
margin, not a completion or production-readiness guarantee.
Maximum additional cost is 15 runner-minutes per affected job, a 33% ceiling
increase, with longer residence of its existing disposable database services.
No additional job, runner, parallel workload, retry, or production resource
is created. This is a separate prerequisite, not a PR409 transaction fix.

## 3. Scope: two implementation paths and one design record

1. `.github/workflows/conformance.yml`: change only
   `jobs.conformance.timeout-minutes` from `45` to `60`.
2. `deployment/postgresql/ofarm_ed25519/native_evidence_verification_currentness.json`:
   regenerate through the existing offline generator after the workflow edit;
   update only the workflow entry's SHA-256 and the aggregate authority-manifest
   digest. Byte length stays unchanged because `45` and `60` have equal length.
3. This RFC records the same-boundary decision and rationale.
   It adds no executable authority and does not expand the two-file implementation.

The full workflow belongs to `EVIDENCE_AUTHORITY_PATHS`; an unrefreshed sidecar
must refuse. Preserve all other authority entries and frozen receipt/identity
links. The [accepted currentness contract, §12](OFARM_Native_Evidence_GitHub_CLI_Pin_Execution_RFC_v0_2.md#12-provisional-design-record)
permits reviewed verifier changes to refresh only this sidecar; frozen release
evidence is not rewritten.
No exact-45 assertion/document claim requires another companion edit.

## 4. Authority, trust, effects, and non-effects

The task user owns semantic scope, any required approval, and final acceptance.
Trusted default-branch policy owns admission, cancellation, execution budget,
and evidence acceptance. The checked sidecar binds current verifier bytes.
Untrusted PR code and provisional artifacts confer no dispatch or publication
authority. CI supplies mechanical evidence; the independent publisher retains
custody; GitHub retains native merge; existing runtime owners remain unchanged.
Protected assets are finite runner resources and honest current evidence.
Trusted inputs are reviewed policy and exact checked bindings; PR source and
producer artifacts remain untrusted. Compromise of the user, trusted policy
repository, or GitHub control plane is outside this bounded threat model.
Primary risks are prolonged resource use and blessing unrelated verifier bytes;
containment is the finite ceiling, exact scope/hash checks, and existing gates.

Preserve admission/revocation, default-branch dispatch, two full clean runs,
equivalence, every test/SQL/signing deadline, dependency/image/action pins,
source and artifact limits, both native architectures, publication receipts,
and final human merge authorization. Gate 5m, handoff 10m, native 120m, and the
separate publisher's 45m remain unchanged. No runtime, tenant, migration,
release, deployment, credentials, verifier logic, or evidence-policy change.
Do not reuse partial results from a cancelled source.

## 5. Invariants and reachable negative cases

| Invariant | CI-reachable negative case and required evidence |
| --- | --- |
| Only the conformance ceiling increases, and remains 60m | Another timeout, retry, runner, or unbounded job appears: exact scope/value review rejects it. |
| Currentness is exact under its existing contract | Stale/extra authority entry or wrong frozen binding: currentness negative controls refuse. |
| Complete verification still precedes publication | Failed/timed-out run, filtered inventory, or failed comparison cannot produce accepted complete evidence. |
| Untrusted code gains no authority | Candidate workflow bytes cannot change their own active budget because trusted default-branch dispatch controls it; forged admission/artifacts refuse. |
| Other behavior and retained evidence stay identical | Unrelated code, test, inventory, pin, or frozen artifact changes fail scope/hash verification. |

## 6. Verification, bootstrap, and delivery

Cheap checks: exact three-path diff with only two executable/data changes;
whitespace; mandatory package check before commit; offline currentness
generation/validation and frozen-hash preservation; existing admission
`WorkflowPolicyTests`; focused currentness, transitive-policy and workflow
authentication controls in `kernel/tests/test_postgresql_native_evidence.py`.
Use existing meaningful controls; no mirror test or test inventory change.
Then exact-head zero-Blocker review, fresh admission, required hosted evidence
and publication, final packet, and later exact-head human merge authorization.
Delivery #410 uses the approval-governed path because this scope relies on the
checked currentness authority. The [Protocol](../development/DELIVERY_PROTOCOL.md#before-implementation)
excludes authority-dependent work from its routine carve-out and treats unclear
classification as high-risk until narrowed. This is its application to this
scope, not a literal rule requiring approval for every numeric CI change.
Review Phase A before presenting this decision's complete card naming the actual
draft PR. This RFC is not that card and grants no implementation or merge authority.

The dispatcher executes trusted default-branch policy: the capacity PR still
receives 45 minutes before merge. Its candidate bytes cannot increase its own
allowance. If its required gates cannot pass, report that bootstrap constraint;
no partial evidence, main-branch direct write, or merge bypass is authorized.
After authorized merge, PR409 needs fresh live-base/policy admission and a
complete source/publication chain. Keep PR409's separate semantic scope intact.

## 7. Simplicity, alternatives, and review point

EXC-001: retain one executor, one budget value, and one currentness path.
EXC-002: add no cache, duplicate state, registry, or alternative evidence path.
EXC-003: trace the timeout failure to the budget and scope/currentness checks.
EXC-004: replace the owned 45m value; introduce no compatibility or fallback path.
EXC-005: add no abstraction or framework; use the existing generator/validator.
EXC-006: the simpler unchanged-45m fresh attempt has now also timed out. Another
identical attempt has no new support. Removing coverage, sharing mutable fixtures,
sharding, or changing deadlines requires more change than this finite increase.

Sizing is provisional. Review measured completion and resource use after the
first complete PR409 source under any later authorized policy. Further timeout
or a need to alter verification/authority calls for a new scoped diagnosis,
not an automatic increase. This review point adds no gate or scheduled work.
The existing currentness model and retained release evidence stay unchanged.

A new decision version/approval is required for changed capability, boundary,
authority, permitted effects/non-effects, invariants, named PR, irreversible
behavior, or deployment posture; uncertain preservation also stops work.
Next: publish the single draft PR's Phase A for exact-head design review, then
present its complete decision card before changing workflow or sidecar bytes.
