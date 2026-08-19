# OFARM Security-Audit Observer-Root Attachment Binding RFC v0.1

## Status

- **Parent issue:** [#192](https://github.com/samovers/OFARM2/issues/192)
- **Decision:**
  `ISSUE192-SECURITY-AUDIT-OBSERVER-ROOT-ATTACHMENT-BINDING-001`, proposed
  version `1`
- **Phase:** Phase A design only; unapproved
- **Reviewed base:**
  `bdf636d155e45ecbf4d9ac828e232bbcf91e1d59`, the merge commit for PR
  [#321](https://github.com/samovers/OFARM2/pull/321)
- **Draft pull request:**
  [#322](https://github.com/samovers/OFARM2/pull/322)
- **Primary trust boundary:** non-provisioning validation of Policy
  Troubleshooter deny-resource evidence for the security-audit observer root
- **Phase A repository effect:** this RFC is the only changed path
- **Phase B:** not authorized
- **Provider-evidence gate:** unresolved; no live decision card or Phase B
  authorization is permitted until section 5.1 passes on one exact RFC head

## 1. Problem and goal

### 1.1 One problem

Merged observer-root admission validates each IAM v2 deny-policy body and
independently recomputes its rule, policy, resource, and overall deny states.
It does not bind the containing `ExplainedDenyResource.fullResourceName` to the
attachment point encoded in those validated policy names.

At reviewed base `bdf636d155e45ecbf4d9ac828e232bbcf91e1d59`, private
`_deny(...)` accepts an explained-resource name when it is merely a nonempty
string beginning with `//`. A response can therefore put a project-attached
policy under the queried KMS version name, under a different project, folder,
or organization name, or under any other `//...` string. If both snapshots
repeat the same mismatch, snapshot equality does not detect it.

The focused positive deny fixture currently demonstrates that gap. Its policy
name encodes this attachment point:

```text
cloudresourcemanager.googleapis.com/projects/123456789012
```

but its explained-resource field contains the queried KMS version:

```text
//cloudkms.googleapis.com/projects/.../cryptoKeyVersions/...
```

Review [4962514064](https://github.com/samovers/OFARM2/pull/321#pullrequestreview-4962514064)
classified exact attachment binding as a required follow-up before production
composition. PR #321 deliberately preserved it as a separate semantic decision
instead of mixing it with the behavior-preserving source reformat.

### 1.2 Exact goal

This decision strengthens the existing closed deny parser so that every
present explained resource is admitted only when:

1. it contains at least one completely validated deny policy;
2. the attachment point derived from every contained policy name is identical;
3. its `fullResourceName` is exactly the `//`-prefixed, decoded form of that
   one attachment point; and
4. every existing rule, policy, resource, overall-state, two-snapshot, time,
   effect, and refusal invariant still passes.

No caller, client, endpoint, request, public type, result, side effect, role,
permission, cloud resource, or runtime composition changes. The accepted
effect is only that inconsistent or ungrounded deny-resource evidence refuses
instead of becoming part of an observer-root admission.

Exact equality is the proposed local protocol, not yet an established
provider fact. Section 5.1 must establish it from complete authenticated
same-response evidence before this goal can receive implementation authority.

## 2. Learning value

This slice closes one demonstrated evidence-integrity gap in issue #192's
requirement for complete effective IAM evidence. It proves that a deny-policy
explanation is bound not only to its independently evaluated policy body but
also to the resource to which that policy says it is attached.

The risk reduction is concrete and production-reachable: an authenticated but
malformed, incomplete, stale, or incorrectly assembled Policy Troubleshooter
response cannot make a resource label look consistent merely by repeating the
same lie in snapshots A and B.

This is the last recorded semantic hardening prerequisite on the merged
observer-root parser only if section 5.1 first establishes the proposed
provider relation. Separately governed provider-currentness,
credential-custody, and runtime-composition decisions may not rely on it
before then.

## 3. Non-goals

This pull request does not change or add:

- the Policy Troubleshooter request resource, principal, permission,
  condition context, v3beta endpoint, timeout, response size, or call order;
- allow-policy, PAB, deny-rule, principal, permission, condition, relevance,
  or access-state semantics other than the named attachment equality gate;
- a hierarchy lookup or a claim that a project, folder, or organization is an
  ancestor of the queried KMS resource;
- a project-ID-to-project-number lookup, Cloud Resource Manager call, resource
  inventory, or caller-supplied attachment roster;
- provider-currentness or production acceptance of the Preview v3beta PAB
  dependency;
- executing the separately authorized provider-evidence capture required by
  section 5.1; this RFC may later record its publication-safe result, but this
  decision grants no cloud credentials, cloud provisioning, IAM mutation,
  deny-policy creation, or deployment authority;
- signer, observer, or evidence-reader credential custody; user-managed key,
  impersonation, token-creation, workload attachment, or alternate-credential
  inspection;
- manifest selection, loading, approval, storage, publication, or rotation;
- trusted clock acquisition, refresh scheduling, concurrency, cache, atomic
  publication, application startup, health, liveness, or readiness;
- authority-receipt issuance, dual-approval verification, approver custody,
  root rotation, compromise response, export lifecycle, output delivery,
  store-loss recovery, or final hostile closure evidence;
- a migration, database role, grant, transaction, PostgreSQL call, CLI,
  service, daemon, queue, spool, file, environment lookup, logging path, or
  telemetry surface;
- issue #172, issue #174, or issue #176 behavior;
- deployment, release, a production-readiness claim, issue #192 closure, or a
  security waiver; or
- cleanup of unrelated source-snapshot provenance or review-tool
  documentation follow-ups from PR #321.

If implementation or review requires any of those authorities, this pull
request stops before editing them and records a separate prerequisite or
follow-up.

## 4. Trust model

### 4.1 Protected assets

- the truth that each explained deny policy is attached to the exact resource
  named by its containing `ExplainedDenyResource`;
- the existing complete effective allow/deny/PAB evidence used by observer-root
  admission;
- the distinction between the queried KMS key or version and a project,
  folder, or organization deny-policy attachment point;
- the equality and stability of both complete normalized snapshots;
- the one frozen, short-lived observer-root admission returned only after all
  gates pass;
- the fixed empty refusal and absence of provider text in failure output; and
- the existing no-mutation and no-runtime-composition boundary.

### 4.2 Trusted components and actors

This amendment preserves the trust model approved and merged in PR #321. In
particular it trusts:

- the future composition to supply the already specified clients, canonical
  manifest, and clock;
- authenticated Google Cloud KMS and IAM service behavior within the existing
  model;
- the repository-pinned interpreter and dependencies;
- Python exact `str` equality after the existing strict UTF-8 and JSON gates;
  and
- the approved observer-root module, its architecture guard, and bounded
  review process.

The provider response is not trusted merely because transport authentication
succeeded. Each relevant field remains untrusted until the closed parser has
validated and related it to the other fields that give it meaning.

### 4.3 Untrusted inputs and behavior

- every Policy Troubleshooter response byte and JSON member;
- each `ExplainedDenyResource.fullResourceName`;
- every deny-policy name, attachment kind, numeric identifier, policy ID,
  order, omission, duplicate, and encoding;
- an explained resource with no policy, policies from different attachment
  points, or a valid policy placed beneath the wrong resource;
- a queried KMS key/version name substituted for a deny-policy attachment
  point;
- a mismatch repeated identically in both snapshots;
- ordinary provider, transport, decoding, and dependency errors; and
- concurrent or repeated callers.

### 4.4 Explicitly excluded attacker capabilities

- arbitrary in-process memory mutation after validation;
- replacement of installed source, bytecode, interpreter, pinned dependency,
  or CA roots;
- compromise of the authenticated Google control plane such that it lies
  consistently about both the policy name and its actual control-plane
  attachment;
- compromise of future runtime composition or the credentials it supplies;
- arbitrary filesystem, environment, or operator mutation; and
- simultaneous compromise of all existing observer-root trust roots.

Local source substitution, dependency compromise, arbitrary operator
compromise, and arbitrary in-process mutation remain outside this slice.
Malformed or internally inconsistent authenticated provider evidence remains
inside scope and must refuse.

## 5. Authority map

| Decision | Sole authority in this slice | Explicit non-authorities |
| --- | --- | --- |
| Eligibility to authorize exact-equality implementation | The completed same-response provider-evidence gate in section 5.1 | Normative prose alone, either illustrative sample alone, typed fixtures, inference, or a generic `go` |
| Deny-policy attachment point | The attachment segment of each fully validated IAM v2 `Policy.name` | Queried KMS resource, manifest project text, caller argument, environment, resource label by itself |
| Attachment resource spelling | Exact deterministic transformation of that validated segment: prepend `//` and replace each exact `%2F` separator with `/` | General URL decoder, case folding, normalization library, heuristic prefix match |
| Containing resource identity | Exact equality between the derived spelling from every contained policy and `ExplainedDenyResource.fullResourceName` | `startswith("//")`, first policy alone, outer reported deny state |
| Presence of explainable attachment evidence | At least one completely validated deny policy in every present explained-resource object | Empty `explainedPolicies`, omitted policy text, resource name alone |
| Policy and resource deny conclusions | Existing independent rule/policy/resource recomputation | Attachment equality alone, provider-reported aggregate alone |
| Whole response stability | Existing complete normalized snapshot equality | Repeated malformed attachment in both snapshots |
| Failure result | Existing one fresh empty public refusal | Provider body, attachment name, policy name, logged detail |

The policy name remains constrained by the existing one grammar:

```text
policies/cloudresourcemanager.googleapis.com%2F
  {projects|folders|organizations}%2F{positive-decimal-id}/
  denypolicies/{policy-id}
```

That grammar admits exactly the two `%2F` separators needed here and no other
percent encoding. Phase B must not add a general percent decoder, accept
lowercase `%2f`, decode arbitrary octets, accept an alphanumeric project ID in
a response, or obtain attachment authority from a second source.

The exact derived resource form is:

```text
//cloudresourcemanager.googleapis.com/
  {projects|folders|organizations}/{positive-decimal-id}
```

Normative Google API descriptions say that `ExplainedDenyResource` represents
a resource whose attached policies were evaluated, that its policies are
policies attached to that resource, and that IAM v2 deny-policy names encode
their URL-encoded attachment point. The official references observed for this
Phase A decision are:

- [Policy Troubleshooter v3beta `iam.troubleshoot`](https://cloud.google.com/policy-intelligence/docs/reference/policytroubleshooter/rest/v3beta/iam/troubleshoot);
- [Troubleshoot IAM permissions](https://cloud.google.com/policy-intelligence/docs/troubleshoot-access);
- [IAM deny policies and attachment points](https://cloud.google.com/iam/docs/deny-overview); and
- [IAM v2 policy name format](https://cloud.google.com/iam/docs/reference/rest/v2/policies/update).

Those descriptions support the proposed deterministic repository protocol,
but the current official troubleshooting guide contains two internally
contradictory illustrative responses. In its first complete response, one
explained deny resource contains this pair:

```text
fullResourceName:
  //cloudresourcemanager.googleapis.com/projects/123456789012
Policy.name attachment:
  cloudresourcemanager.googleapis.com%2Fprojects%2F546942305807
```

In its later REST response, both fields identify project `546942305807`:

```text
fullResourceName:
  //cloudresourcemanager.googleapis.com/projects/546942305807
Policy.name attachment:
  cloudresourcemanager.googleapis.com%2Fprojects%2F546942305807
```

The first sample would refuse under this RFC and the second would pass. The
repository must not assume that the first is merely a documentation error.
Neither the normative descriptions nor either illustrative response alone
establish the provider relation required for Phase B.

### 5.1 Ordered provider-evidence gate before Phase B authorization

Before a complete live decision card may be displayed or Phase B may be
authorized, a separately authorized actor with appropriate provider
credentials must complete this gate without using authority from this RFC:

1. capture one complete authenticated Policy Troubleshooter v3beta response
   involving a controlled project-attached IAM v2 deny policy;
2. have both bounded reviewers inspect the complete response and record in
   this RFC the capture time, exact endpoint and API version, a SHA-256 digest
   of the complete response, and the exact `fullResourceName` and full
   `Policy.name` taken from the same `ExplainedDenyResource` object;
3. capture a complete no-deny control whose top-level
   `explainedResources` is empty, and confirm in the deny-bearing response
   that every present explained resource contains at least one visible policy;
4. verify whether exact prefix and suffix removal plus exact uppercase `%2F`
   replacement makes the policy attachment byte-for-byte equal to the outer
   `fullResourceName`; and
5. record which attachment kinds have been observed with that same-response
   equality.

Credentials, access tokens, and sensitive response data must not be committed.
The complete responses must nevertheless be available to the two bounded
reviewers; a digest or extracted pair alone is not a substitute for their
inspection of the complete evidence.

The gate has only these outcomes:

- If the controlled project response matches exactly, the normative type
  descriptions plus captured provider behavior control this repository
  protocol. The mismatched guide sample remains recorded as an inconsistent
  illustrative example rather than being silently ignored.
- If the controlled response does not match, or if the two fields identify the
  same logical resource in different forms such as project ID versus project
  number, implementation stops. A new decision version must revise the
  authority model; no lookup or fallback may be added as a review fix.
- Folder and organization attachment kinds may proceed only after matching
  same-response evidence is recorded for each kind. An unobserved kind is
  deferred, not inferred from project behavior; this all-three-kind version
  must be narrowed and re-reviewed before authorization if either kind remains
  unobserved.
- If a complete response contains a present explained resource with zero
  visible policies, implementation stops for a new decision version.

Completing this narrow evidence gate does not accept Preview v3beta or PAB for
production. Provider support currentness and production acceptance remain a
separate trust boundary and later decision.

## 6. State machine and ordering

### 6.1 Existing outer admission state machine

The public state machine remains exactly:

```text
UNVALIDATED
  -> MANIFEST_VALIDATED
  -> STARTED
  -> SNAPSHOT_A_VALIDATED
  -> PROBE_VALIDATED
  -> SNAPSHOT_B_VALIDATED
  -> FINISHED
  -> ADMITTED

any ordinary failure after entry -> REFUSED
```

No new state, network call, retry, mutation, output, or partial authority is
introduced.

### 6.2 Exact deny-resource transition

Within each existing Policy Troubleshooter response, Phase B performs this
closed transition for every `explainedResources[]` item:

```text
raw explained resource
  -> exact member/type/enum validation
  -> require a nonempty explainedPolicies list
  -> completely validate and normalize every deny policy
  -> derive one attachment resource from each validated policy name
  -> require all derived resources to equal fullResourceName exactly
  -> recompute each policy deny state
  -> recompute the containing resource deny state
  -> include the bound normalized resource in the snapshot
```

Derivation occurs only after the policy body and its exact name have passed the
existing closed parser. Equality occurs before the resource can contribute to
the outer deny state or normalized snapshot.

`explainedResources: []` remains accepted when the response reports no
evaluated deny-policy resource. Once a resource object is present, an empty
`explainedPolicies` list cannot establish its attachment or contribution and
must refuse.

Subject to section 5.1's observed-kind gate, multiple resource objects remain
supported. Each attachment kind retained by the evidence-bearing approved
version may appear, but each object is checked only against the policies it
contains. This slice does not independently reconstruct or query the resource
hierarchy.

### 6.3 Exact transformation

Given this already validated policy name:

```text
policies/cloudresourcemanager.googleapis.com%2Fprojects%2F123456789012/
denypolicies/security-audit-deny
```

the only accepted containing resource is:

```text
//cloudresourcemanager.googleapis.com/projects/123456789012
```

The implementation strips only the exact `policies/` prefix and
`/denypolicies/{policy-id}` suffix established by the existing grammar,
replaces only the exact `%2F` separators with `/`, and prepends `//`. It does
not use a generic URL parser or decoder.

Exact Python string equality is intentional. A trailing slash, query, fragment,
case change, Unicode lookalike, extra separator, encoded separator, queried KMS
resource, or otherwise equivalent-looking spelling refuses.

### 6.4 Time-of-check and side effects

Attachment validation is local and side-effect free. It happens while each of
the two existing snapshots is built. A mismatch in snapshot A refuses before
the probe. A mismatch in snapshot B refuses after the one already authorized
probe but before the second clock value or any admission result. Existing
ordinary-error normalization and exact effect-prefix tests continue to govern
both paths.

The time-of-check boundary remains the approved double-snapshot window. This
slice does not claim a transaction or permanent IAM state.

## 7. Invariants and acceptance criteria

### `ORAB-001` — one closed attachment derivation

Every attachment resource is derived only from a deny-policy name that passed
the existing exact IAM v2 policy-name grammar. The transformation is fixed to
the exact prefix/suffix removal, exact `%2F` separator replacement, and `//`
prefix described in section 6. No general URL decoding, alternate grammar,
caller input, manifest field, or provider-selected fallback exists. This
derivation receives no implementation authority until section 5.1 passes.

### `ORAB-002` — exact resource-to-policy binding

Every present `ExplainedDenyResource.fullResourceName` equals the attachment
resource derived from every contained policy. One matching policy cannot mask
another policy from a different attachment point. Prefix, suffix, normalized,
case-folded, or first-policy-only comparison is forbidden.

### `ORAB-003` — no ungrounded explained resource

Every present explained resource contains at least one completely validated
deny policy. An empty top-level `explainedResources` list remains valid, but a
resource object with an empty, omitted, malformed, or inaccessible policy list
cannot contribute evidence or authority.

### `ORAB-004` — mismatch cannot become stable evidence

Attachment validation occurs independently in both snapshots before snapshot
equality can support admission. A mismatch repeated identically in A and B
refuses. An ordinary attachment failure returns no partial result and becomes
the existing fresh empty public refusal without provider text or explicit
cause.

### `ORAB-005` — existing observer-root protocol is unchanged

All merged `ORA-001` through `ORA-016` invariants continue to hold. In
particular, requests, endpoints, roles, permissions, PAB posture, KMS reads,
probe bytes, clock calls, snapshot ordering, lifetime, public types, no-mutation
surface, and production non-readiness do not change. `ORA-007` is strengthened
only by the attachment binding defined here.

### `ORAB-006` — exact repository and auditability envelope

Phase A changes only this RFC. Prospective Phase B changes only the five exact
paths in section 11. It adds no dependency, lockfile, workflow, migration,
command, credential, service, test glob, group budget, shared numeric-limit
change, or sixth path.

The section 5.1 result is recorded only in this RFC on a new exact Phase A
head. The separately authorized provider capture is not performed by this PR,
does not add a repository path, and cannot import credential or cloud-mutation
authority into Phase B.

The production module keeps the 1,800-line ceiling, exact finished-count
budget, pinned Ruff check and format check, 120-character physical-line limit,
and prohibitions on `noqa`, semicolon statement joining, and one-line compound
bodies.

`MAX_FUNCTION_LINES` remains exactly 80 for every registered production path
other than the one exact observer-root module. This decision expressly
re-authorizes that sole exact-path exception after the semantic change only
when conformance pins the new semantic implementation reference and immutable
location-free AST digest and every replacement source-shape gate passes. The
exception may not be generalized, parameterized, moved, or reused.

The existing `_allow_policy` and `_deny_policy` functions are not decomposed or
semantically changed. The new private attachment derivation is at most 20
physical lines, and the changed `_deny` function remains at most 80 physical
lines. Any need to refactor an existing long policy parser stops Phase B for a
new decision rather than becoming a review fix.

## 8. Production-reachable negative cases

| Invariant | Supported entry point and counterexample | Required result |
| --- | --- | --- |
| `ORAB-001` | The public admission function receives an authenticated v3beta response whose policy name uses lowercase `%2f`, an encoded percent, a missing separator, an alphanumeric response project ID, a zero identifier, a KMS attachment, or an extra suffix. | Existing closed policy-name validation refuses; no attachment is derived. |
| `ORAB-002` | A valid project-attached policy is placed under the queried KMS key/version, a different project, a folder, an organization, a trailing-slash spelling, or another valid-looking `//` resource. | Refuse before the resource contributes to the normalized snapshot. |
| `ORAB-002` | One explained resource contains two otherwise valid policies whose names encode different project, folder, or organization attachments. | Refuse even if one policy matches the outer field and all reported deny states are internally consistent. |
| `ORAB-003` | A v3beta response contains a present explained-resource object with `explainedPolicies: []`. | Refuse; a resource label alone cannot establish attachment evidence. |
| `ORAB-003` | A normal no-deny response contains `explainedResources: []` and every existing outer state is valid. | Preserve current acceptance; do not invent a resource or policy requirement when no resource object is present. |
| `ORAB-004` | The same project-policy/KMS-resource mismatch appears in both complete snapshots. | Refuse in snapshot A before the probe; snapshot equality never legitimizes the mismatch. |
| `ORAB-004` | Snapshot A is valid, the fixed probe succeeds, and snapshot B changes only the attachment resource. | Refuse after the probe and before admission through the existing fresh empty refusal. |
| `ORAB-005` | A proposed fix changes the request tuple, calls a hierarchy API, accepts stable v3, relaxes PAB evidence, changes probe or clock behavior, exposes provider text, or adds a side effect. | Existing focused or architecture conformance fails and merge stops. |
| `ORAB-006` | A proposed Phase B diff decomposes `_deny_policy`, changes `_allow_policy`, raises or generalizes a function limit, omits the new immutable AST reference, exceeds the module ceiling, adds a sixth path, dependency, workflow, migration, runtime file, credential file, or cloud configuration. | Mechanical envelope or bounded review fails and merge stops. |

All runtime counterexamples enter through the existing public
`admit_security_audit_observer_root(...)` function and supported fake client
protocols. Tests mutate response documents at those boundaries, not private
production state.

## 9. Proposed architecture and smallest coherent change

### 9.1 One private derivation and one gate

The existing production module remains the sole owner. Prospective Phase B
adds one small private attachment-derivation function and one fail-closed gate
inside `_deny(...)`:

```text
validated normalized policy name
  -> exact attachment segment
  -> exact //-prefixed resource spelling

all derived spellings + outer fullResourceName
  -> exact all-member equality
  -> existing deny-state recomputation
```

The helper has no public export, configuration, dependency, I/O, cache, global
registry, parser framework, generic resource-name abstraction, or second
validation path. It consumes only the already validated policy name and
returns one immutable string.

The positive deny fixture is corrected to use its project attachment point.
Focused tests add the hostile cases in section 8 and one valid multi-policy or
multi-resource case proving that equality is checked per containing resource.

### 9.2 No output or snapshot schema change

The normalized snapshot keeps the same fields and shape. A valid
`fullResourceName` remains present exactly as returned because it has now been
bound to the enclosed policy names. No derived attachment field, boolean,
receipt, diagnostic, or second copy is added to the public result or snapshot.

This avoids creating correlated state that future composition could separate.

### 9.3 Function-span and immutable-AST decision

PR #321 accepted one exact-path exception from the generic 80-line physical
function-span heuristic because `_allow_policy` and `_deny_policy` are 84 and
127 formatted physical lines while the entire module is constrained by a
pinned semantic AST and stronger source-shape gates.

This semantic change necessarily invalidates the old whole-module AST digest.
The new decision makes the consequence explicit:

1. do not decompose or otherwise edit `_allow_policy` or `_deny_policy`;
2. after section 5.1 and exact approval pass, create **Commit A** containing
   only the approved helper and `_deny` semantic changes, their tests, the
   resulting exact module budget and guards, the mechanically regenerated
   inventory, and the new location-free whole-module AST digest;
3. require the package contract to pass on Commit A against that one new
   digest; Commit A intentionally remains non-merge-eligible because its own
   immutable SHA cannot be embedded in itself as its reference identity;
4. create **Commit B** that pins Commit A's exact immutable SHA as
   `SECURITY_AUDIT_OBSERVER_ROOT_REFERENCE_HEAD` and changes no production or
   test semantics; Commit B is the first merge-eligible conformance head;
5. require the package contract to pass again on Commit B and every later
   head, with exactly one accepted AST digest and Commit A as the one semantic
   reference; and
6. re-authorize the existing exception for only the exact observer-root path
   beginning at Commit B while all replacement gates pass.

Commit A replaces the old AST digest; it may not preserve the old digest as an
alternative. The transition may not use a temporary digest bypass, dual
accepted digests, a candidate-derived oracle, a weakened comparison, `noqa`,
or an unreviewed suppression. Commit B may change only the immutable reference
identity and mechanically necessary evidence for that identity. Any semantic
change after Commit A requires another reference sequence and bounded review.

The semantic reference commit cannot contain runtime, credential, deployment,
or unrelated refactoring work. Conformance and review must compare it with base
`bdf636d155e45ecbf4d9ac828e232bbcf91e1d59` and verify that the only
location-free production AST changes are the one private derivation and the one
`_deny` gate.

### 9.4 Why this is the minimum coherent design

Checking only that `fullResourceName` begins with `//` does not establish which
resource owns the policies. Checking only the first policy permits a second
policy from another attachment. Allowing an empty policy list leaves no source
from which attachment truth can be derived. Comparing only snapshots permits a
stable lie.

A hierarchy API or manifest project-number field would add another authority,
network effect, provider surface, and trust boundary. A generic URL decoder
would accept syntax outside the already closed policy-name grammar. Refactoring
the two long policy parsers would widen the review surface without helping the
attachment equality.

One local derivation from every already validated policy name plus one exact
all-member equality gate is therefore the minimum coherent correction.

## 10. Elegance audit

### 10.1 Sources of truth and transition points

- deny-policy attachment sources of truth: one, each policy's validated name;
- attachment derivation algorithms: one;
- equality transition points: one, inside `_deny(...)` before state
  aggregation;
- public success constructors: unchanged at one;
- public refusal types and construction paths: unchanged;
- new network, storage, credential, or time sources: zero; and
- new mutable registries or optional capability bags: zero.

### 10.2 Duplication and compatibility

The outer resource field is evidence checked against policy-name authority; it
does not become a second authority. The normalized snapshot retains that field
only in its existing provider shape. There is no legacy loose-attachment mode,
feature flag, compatibility alias, fallback parser, warning-only path, or
caller override.

The incorrect positive fixture is replaced rather than preserved as a legacy
shape.

### 10.3 Abstractions and deletion

One private helper is justified because the security-sensitive transformation
must be named and tested once. A generic resource or URL framework is not.

No production path is deleted because there is only one deny parser. The loose
`startswith("//")` acceptance is removed. A clean rewrite of the 1,747-line
module is less safe than the bounded local correction.

## 11. Pull request boundary

### 11.1 Primary boundary

The one primary trust boundary is non-provisioning validation of Policy
Troubleshooter deny-resource evidence for the security-audit observer root.

Tests, the exact architecture re-pin, the RFC evidence record, and the
mechanical test inventory may travel with that boundary. Credential custody,
cloud mutation, provider production acceptance, runtime integration,
readiness, rotation, database authority, export lifecycle, store-loss handling,
and deployment may not.

### 11.2 Exact prospective Phase B path allowlist

Phase B may change only these five paths:

1. `docs/rfcs/OFARM_Security_Audit_Observer_Root_Attachment_Binding_RFC_v0_1.md`
2. `deployment/postgresql/security_audit_observer_root_admission.py`
3. `kernel/tests/test_security_audit_observer_root_admission.py`
4. `conformance/rewrite_architecture_check.py`
5. `conformance/review_baseline_test_inventory.json`

Path 1 is the approved contract and later evidence record. Path 2 contains the
only production semantic change. Path 3 verifies supported-entry-point positive
and hostile cases. Path 4 updates only the exact line budget, semantic
reference identity/digest, and narrowly necessary guards for this same module;
it does not change a shared limit or general rule. Path 5 is generated
mechanical output only.

No README change is needed because the public interface, operational posture,
and non-readiness statement are unchanged. No sixth path may enter Phase B.

### 11.3 Dependencies and ordering

- PR #321 merged the observer-root admission at exact merge commit
  `bdf636d155e45ecbf4d9ac828e232bbcf91e1d59`.
- PR #319 supplies the existing dual-approval verifier root surface.
- PR #320 supplies the existing authority-receipt issuer surface.
- No open pull request is a code dependency.
- Issue #172 and parked issue #176 work are not dependencies and must not be
  modified or imported.

Section 5.1 is a non-repository evidence prerequisite to Phase B authority.
Its provider call and credentials require separate explicit authority and do
not belong to this PR. Its publication-safe result may be recorded only in
this RFC, after which the new exact RFC head must rerun hosted checks and both
bounded Phase A reviews. No implementation commit may precede that sequence.

Later provider-currentness, credential-custody, and runtime-integration work
may assume the attachment invariant only after this separate pull request
merges. This pull request may not assume authority from those future slices.

### 11.4 Ordered follow-ups, not scope expansion

After this boundary merges, the remaining observer-root path must still be
split under the workspace one-boundary rule:

1. a separate provider-currentness and support-status decision completes the
   provider work beyond section 5.1, verifies the full v3beta allow/deny/PAB
   response contract, and decides whether Preview is acceptable for
   production;
2. a separate credential-custody decision names exact workload identities and
   proves the absence of unaccounted user-managed keys, impersonation,
   token-creation, workload attachment, or alternate credential paths;
3. a separate runtime-integration/readiness decision loads the approved
   manifest and trusted clock, constructs independent clients, pipelines
   overlapping admissions, publishes only newly completed unexpired results,
   binds one root into issuer and verifier, and requires two usable approvers
   in independent domains;
4. a separate root-rotation and compromise-response decision defines old/new
   handoff and revocation latency; and
5. issue #192 then continues through the already recorded one-operation,
   temporary-login, delivery, store-loss, and final closure boundaries.

Credential custody and runtime integration are distinct primary trust
boundaries and may not share one PR merely because section 11.4 of the earlier
RFC described them together conditionally.

Reviewers must not require any follow-up above to clear this PR. A demonstrated
need to edit one stops this PR and becomes a separate prerequisite. Section
5.1 is not one of these post-merge follow-ups: it is an explicit pre-Phase-B
gate created by the contradictory official evidence.

## 12. Provisional design record

The attachment equality is not a speculative convenience: normative API type
descriptions relate an `ExplainedDenyResource` to policies attached to that
resource, and IAM v2 policy names encode their attachment point. It is also not
yet an established provider fact, because section 5 records contradictory
official illustrative responses.

The wider provider dependency remains provisional:

- **Evidence required before Phase B authority:** section 5.1 must establish
  exact same-response equality for every attachment kind retained by this
  version, prove the no-deny empty-list control, and show that every present
  deny resource contains visible policy evidence.
- **Evidence requiring redesign:** a complete response pairs different
  resources; pairs the same logical resource in different identifier forms,
  including project ID versus project number; uses a policy-name encoding
  outside the closed grammar; lawfully contains a present explained resource
  with zero visible policies; or changes the v3beta/PAB contract.
- **Unobserved attachment kinds:** folder or organization behavior may not be
  inferred from a project capture. An unobserved kind must be removed or
  deferred by a new exact decision head and re-reviewed before Phase B.
- **Likely upgrade path:** a new provider-currentness decision chooses and
  pins the supported response contract before production composition. It may
  revise this parser only through another reviewed semantic decision.

Stable v3 is not an authorized fallback because the accepted observer-root
contract requires complete PAB evidence. Phase A approval or a later merge of
this parser hardening does not accept Preview for production. Until section
5.1 passes, even repository Phase B implementation is forbidden.

## 13. Traceability and verification

| Invariant | Owning prospective code | Negative evidence | Smallest verification |
| --- | --- | --- | --- |
| `ORAB-001` | one private attachment derivation beside the closed deny parser | malformed prefix/suffix, encoding, kind, identifier, and policy-name matrix | focused pure derivation cases plus public admission refusal cases |
| `ORAB-002` | `_deny(...)` all-policy equality gate | KMS resource, sibling project, folder/organization mismatch, trailing slash, and mixed-policy attachments | public admission tests with complete v3beta response fixtures |
| `ORAB-003` | `_deny(...)` explained-policy presence gate | present resource with zero, omitted, malformed, or inaccessible policies | empty-resource-list positive control and present-empty-resource refusal |
| `ORAB-004` | both snapshot construction calls and existing public wrapper | same mismatch in both snapshots; valid A and mismatched B | exact probe/clock/effect-prefix assertions and empty-refusal assertions |
| `ORAB-005` | unchanged request, parser, probe, time, result, and architecture surfaces | endpoint/request/PAB/probe/clock/output/effect mutation canaries | existing focused suite plus architecture conformance |
| `ORAB-006` | exact path allowlist, module budget, semantic reference/digest, formatter/source-shape gates, and exact-path function-span decision | sixth path, changed shared limit, broadened exception, parser decomposition, over-budget/compressed/unformatted source, missing AST re-pin | diff allowlist, function measurements, Ruff check/format check, AST comparison, architecture and package conformance |

### 13.1 Phase A verification gates

- this RFC is the only changed path;
- the reviewed base and `origin/main` both remain
  `bdf636d155e45ecbf4d9ac828e232bbcf91e1d59`, or a later base movement is
  inspected and recorded before review;
- the two contradictory official Google examples and their exact
  `fullResourceName`/`Policy.name` pairs remain recorded rather than being
  resolved by assumption;
- before a complete live card, section 5.1 is completed and this RFC records
  the complete-response digests, exact same-response field pairs, cardinality
  controls, and observed attachment kinds;
- a matching capture expressly identifies the normative type contract and
  captured provider behavior as controlling, while a mismatch, identifier-form
  difference, empty present resource, or unobserved retained kind stops this
  version;
- the contract distinguishes the request's KMS resource from each deny-policy
  attachment resource;
- the five-path prospective boundary contains no credential, runtime, cloud,
  database, export, rotation, deployment, or issue #176 path;
- `python3 conformance/ofarm_pkg_contract_check.py` passes before every commit;
- the draft PR receives two independent reviews of one exact RFC head;
- every demonstrated Phase A Blocker is corrected in this RFC; and
- no complete live decision card is displayed until the final evidence-bearing
  exact head passes hosted checks and both exact-head reviews report zero
  demonstrated in-scope Blockers.

### 13.2 Prospective Phase B verification gates

- reproduce this invariant table before editing;
- verify section 5.1 passed on the exact approved RFC head and that no
  attachment kind retained by the implementation is unobserved;
- verify the original live card and exact later approval remain directly
  retrievable in the same task and bind this one named draft PR;
- implement only the one private derivation and one `_deny` equality/presence
  gate authorized in section 9;
- correct the existing deny fixture and test every section 8 counterexample
  through the public admission function;
- prove a mismatch in snapshot A makes zero probe calls and a mismatch only in
  snapshot B preserves the exact one-probe effect prefix but returns no result;
- prove the same mismatch in both snapshots refuses before equality;
- prove empty top-level `explainedResources` still accepts under an otherwise
  valid no-deny response, while a present resource with no policies refuses;
- prove valid project, folder, and organization attachment spellings retained
  by the evidence-bearing approved version and a valid multi-policy or
  multi-resource response bind per resource;
- run the complete focused observer-root admission suite;
- prove requests, call counts, endpoint, PAB posture, policy-state
  recomputation, probe, clocks, output, and ordinary-refusal behavior are
  unchanged;
- execute section 9.3's exact two-commit sequence: Commit A pins the one new
  AST digest and passes the package contract; Commit B pins Commit A's exact
  SHA, changes no production or test semantics, and passes again as the first
  merge-eligible conformance head;
- compare the semantic reference with base and verify the only production AST
  changes are the approved helper and `_deny` gate;
- prove `_allow_policy` and `_deny_policy` remain semantically unchanged, the
  new helper is at most 20 lines, and `_deny` remains at most 80 lines;
- keep `MAX_FUNCTION_LINES == 80`, retain the exact observer-root path as the
  sole exception, and reject any broadened exception or alternate limit;
- keep the exact module budget equal to finished physical lines and at most
  1,800;
- run repository-pinned Ruff check and `ruff format --check`; reject `noqa`,
  semicolon joining, one-line compound bodies, over-120-character lines, or AST
  drift after the new semantic reference;
- regenerate the review-baseline inventory mechanically;
- run architecture conformance and
  `python3 conformance/ofarm_pkg_contract_check.py`;
- inspect the exact five-path diff and prove no dependency, lockfile, workflow,
  migration, command, test glob, group budget, shared numeric limit, credential,
  runtime, cloud, database, export, rotation, deployment, or sixth path changed;
- obtain hosted exact-head checks; and
- receive two bounded exact-head implementation reviews with zero demonstrated
  in-scope Blockers before merge.

Repository Phase B performs no live Cloud KMS or IAM call. Its typed
deterministic fixtures exercise the local trust transition, but they are not a
substitute for the separately authorized section 5.1 capture that must precede
Phase B authority. That narrow capture does not decide wider provider support
currentness or production acceptance.

## 14. Open decisions and review disposition

### 14.1 Closed design choices in proposed version 1

- Subject to section 5.1, policy names, not the request resource or outer
  field, are attachment authority.
- Every contained policy must agree; first-policy comparison is insufficient.
- A present explained resource must contain at least one validated policy.
- No hierarchy or project-number lookup is added.
- No generic URL decoder is added.
- The existing two long policy parsers are not refactored.
- The exact-path function-span exception is expressly re-decided against a new
  semantic reference through the exact Commit A/Commit B sequence instead of
  silently surviving an AST re-pin.
- Credential custody, provider-currentness, and runtime integration remain
  separate later decisions.

### 14.2 Material decisions still deferred

- production acceptance or replacement of Preview v3beta/PAB evidence;
- provider support currentness beyond section 5.1's narrow prerequisite;
- exact production resources, principals, credentials, and role etags;
- manifest publication and trusted-time custody;
- workload credential custody and absence of alternate access paths;
- concurrent refresh, atomic publication, readiness, and issuer/verifier
  composition;
- root rotation and compromise response; and
- remaining export, delivery, store-loss, and issue-closure work.

### 14.3 Current review disposition

- **Prior exact head:** `19762d0babeb2c99d585d4b562d78a4e29250e5c`.
- **Review 1:** [comment 5343407461](https://github.com/samovers/OFARM2/pull/322#issuecomment-5343407461)
  reported zero Blockers and required the identifier-form redesign trigger and
  same-response evidence pair now specified in sections 5.1, 12, and 13.1.
- **Review 2:** [review 4973238325](https://github.com/samovers/OFARM2/pull/322#pullrequestreview-4973238325)
  reported one in-scope Blocker: the contradictory official examples. It also
  required the cardinality controls and exact two-commit semantic-reference
  sequence now specified in sections 5.1 and 9.3.
- **Current Blockers:** the previous exact-head control gaps are amended, but
  section 5.1's provider evidence is not yet recorded and the amended exact
  head has not received its two superseding reviews.
- **Follow-ups:** wider provider currentness and the ordered, separately
  governed boundaries in section 11.4.
- **Preferences:** none recorded.
- **Active baseline files affected:** none; this is not OFARM baseline law.
- **Change classification:** high-risk supporting security evidence-validation
  decision under issue #192.

A review finding is a Blocker only when it demonstrates that an `ORAB-001`
through `ORAB-006` invariant cannot hold, that the five-path implementation is
internally contradictory, or that the slice crosses its primary trust
boundary. Credential, runtime, provider acceptance, deployment, rotation,
database, export, delivery, store-loss, or issue-closure work is a follow-up
unless it proves one of those failures.

## 15. Proposed approval boundary

This RFC, its draft pull request, local analysis, reviews, commits, pushes,
repository credentials, or a generic `go` grant no Phase B authority.

Only after section 5.1 passes and its evidence record is present on one exact
RFC head may that same head run hosted checks and receive the two independent
Phase A reviews used for approval. If both reviews report zero demonstrated
in-scope Blockers, one complete live decision card may be displayed in the
same Codex task. The card must include:

- decision ID and version;
- parent issue;
- stable RFC and draft-PR references;
- the one primary trust boundary;
- all six invariants;
- the exact five-path prospective Phase B allowlist;
- the authorized repository effects;
- the excluded credential, provider-acceptance, runtime, cloud, database,
  export, rotation, deployment, and issue-closure authorities;
- the complete-response digests, exact same-response field pairs, observed
  attachment kinds, and remaining provisional-evidence limitation;
- review disposition and stop conditions; and
- the exact approval sentence below.

The required exact approval form is:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-OBSERVER-ROOT-ATTACHMENT-BINDING-001 version 1.
```

Approval is recognized only if that sentence is supplied as the exact entire
later task-user message after the complete live card, in this same task and in
that order. No current message supplies it.

When those conditions are satisfied, approval authorizes only the five-path
repository implementation, tests, mechanical evidence, commits, pushes,
bounded review handling, and merge described here. It authorizes no cloud or
IAM mutation, credential act, live provider acceptance, runtime integration,
readiness, root rotation, database admission, export lifecycle, delivery,
deployment, production operation, release, security waiver, or closure of
issue #192.

## 16. Merge stop rule

Once the approved acceptance criteria pass on one exact five-path head, hosted
checks pass, and two exact-head implementation reviews report zero demonstrated
in-scope Blockers, merge the named draft pull request under normal repository
controls. New ideas, Preferences, and out-of-boundary hardening become
follow-ups and do not expand this PR.

Stop and require a new decision version before implementation or merge if:

- the original live card or exact later approval cannot be retrieved and
  verified in order;
- another trust boundary or sixth path is needed;
- section 5.1 is incomplete, unavailable for bounded review, or absent from the
  exact approved RFC head;
- the controlled capture contradicts exact attachment equality, represents the
  same logical resource in a different identifier form, or leaves an
  attachment kind retained by this version unobserved;
- official provider documentation changes beyond the two contradictory
  examples already recorded here;
- an explained resource with zero policies must be accepted as complete;
- a hierarchy lookup, generic URL decoder, alternate policy-name grammar, or
  second attachment authority is needed;
- `_allow_policy` or `_deny_policy` must be refactored or semantically changed;
- the exact-path function-span exception must be broadened, moved, or left
  unbound to the new immutable semantic reference;
- the production module cannot remain within the 1,800-line and source-shape
  envelope;
- a material change is needed to the trust model, authority map, state machine,
  invariants, side effects, or named draft PR; or
- deployment or another production-authority act is requested.
