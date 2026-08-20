# OFARM Security-Audit Observer-Root Provider-Evidence Capture — Phase A Contract v0.1

**Status:** local Phase A draft only; unapproved; unpublished; no provider call,
credential use, repository publication, or Phase B authority

**Contract identity:**
`ofarm2.security-audit-observer-root-provider-evidence-capture.v0.1`

**Decision identity:**
`ISSUE192-SECURITY-AUDIT-OBSERVER-ROOT-PROVIDER-EVIDENCE-CAPTURE-001`,
proposed version `1`

**Issue relationship:** issue #192 remains open; this is a separate prerequisite
for the provider-evidence gate in the observer-root attachment-binding decision

**Dependent draft pull request:**
[PR #322](https://github.com/samovers/OFARM2/pull/322)

**Draft pull request for this decision:** none; this file is a local draft

**Reviewed base:** `bdf636d155e45ecbf4d9ac828e232bbcf91e1d59`

**Primary trust boundary:** authenticated, read-only acquisition and
publication of controlled Google Policy Troubleshooter response evidence

**Phase A review-head boundary:** this RFC only

**Prospective Phase B effect boundary:** exactly two authenticated read-only
`POST` requests to the fixed Policy Troubleshooter v3beta endpoint, bounded
temporary custody of their response bodies, and an evidence-only amendment to
this RFC

**Phase B:** not authorized

## 1. Problem and exact goal

The observer-root attachment-binding draft proposes that an IAM v2 deny-policy
name and its containing
`ExplainedDenyResource.fullResourceName` identify the same attachment point.
Official type descriptions support that relation, but the official guide also
contains two contradictory illustrative response pairs. PR #322 therefore
cannot receive Phase B implementation approval from documentation or typed
fixtures alone.

The remaining gate needs live, same-response provider evidence. That work is a
different trust boundary from changing the repository parser: it needs an
existing credential, a controlled provider fixture, an authenticated external
read, temporary evidence custody, and publication of the complete response
bytes. It must not be appended to PR #322 as an informal review fix.

This decision defines one narrow acquisition:

1. capture one complete response for a pre-existing, controlled
   **project-attached** IAM v2 deny policy;
2. capture one complete response for a pre-existing controlled project whose
   deny explanation has an explicitly present empty `explainedResources`
   array;
3. freeze and hash each complete response body before UTF-8 decoding or JSON
   parsing;
4. publish the exact complete bytes without redaction or reserialization;
5. enumerate every relevant explained-resource/policy pair and every required
   cardinality from those same bytes; and
6. transfer no implementation, provider-acceptance, credential-custody, or
   deployment authority to PR #322.

Version 1 captures project evidence only. It does not call a folder or
organization fixture and cannot establish either attachment kind. If it
succeeds, the consuming attachment-binding decision must refuse folder and
organization policy names unless a later separately reviewed capture decision
establishes each kind from controlled same-response evidence.

## 2. Learning value

This slice tests one disputed provider relation at the actual API boundary
without broadening parser implementation or provisioning authority. A
successful record lets reviewers distinguish an observed provider fact from a
repository assumption. A mismatch, empty present resource, identifier-form
difference, unexpected attachment kind, incomplete publication channel, or
oversized response becomes visible and stops the consumer rather than being
normalized away.

The evidence is deliberately provisional. It records what one controlled
v3beta response did at one capture time. It does not establish v3beta support
currentness, production suitability, global provider behavior, or a guarantee
that Google will preserve the relation.

## 3. Primary boundary and intended pull-request boundary

The one primary trust boundary is authenticated, read-only acquisition and
publication of controlled Policy Troubleshooter evidence.

The intended Phase A pull request changes only this RFC. After exact approval,
the same pull request may perform the two external reads and amend only this
RFC with the complete result described in section 10. It may not add a capture
tool, dependency, workflow, credential file, fixture provisioner, parser
change, runtime path, or second repository artifact. Any durable capture tool
would be a separately reviewed implementation decision.

PR #322 remains a separate consumer. Copying accepted evidence into its RFC,
narrowing its attachment grammar to observed kinds, publishing that amendment,
or authorizing its Phase B implementation requires that PR's own actions,
reviews, decision card, and approval. This decision grants none of them.

## 4. Non-goals

This decision does not authorize or change:

- project, folder, organization, service account, KMS resource, custom role,
  IAM binding, deny policy, PAB, or allow policy creation, update, deletion, or
  discovery;
- any provider write, `gcloud` mutation, Terraform, Pulumi, Config Connector,
  deployment, release, or production operation;
- credential creation, selection, impersonation, export, printing, storage,
  refresh, rotation, revocation, or alternate-credential inspection;
- access-token, authorization-header, cookie, private-key, client-secret, or
  application-default-credential publication;
- production resources, production principals, production policy contents,
  customer data, tenant data, personal data, or secret-bearing responses;
- folder- or organization-attached evidence in version 1;
- a hierarchy lookup, project-ID-to-number lookup, Resource Manager call,
  policy list, search, enumeration, retry, redirect, fallback endpoint, stable
  v3 call, or `testIamPermissions` call;
- validation of allow-policy, deny-rule, PAB, principal, permission,
  membership, condition, relevance, or overall-access semantics beyond the
  exact evidence inventory in this RFC;
- acceptance of Policy Troubleshooter Preview v3beta or PAB evidence for
  production, provider support currentness, SLA, deprecation monitoring, or
  replacement-provider design;
- observer-root parser implementation, typed fixture changes, semantic
  reference changes, architecture checks, runtime composition, health,
  readiness, refresh, caching, or admission-result publication;
- signer, observer, evidence-reader, or approver custody and least-privilege
  proof;
- database, migration, role, grant, transaction, export, delivery, rotation,
  store-loss, issue #176, or issue-closure work; or
- approval, merge, deployment, or publication of PR #322.

If a usable controlled fixture or already-authorized read-only credential does
not exist, this decision stops. It does not provision the missing fixture or
change credential custody as a review fix.

## 5. Trust model and preconditions

### 5.1 Protected assets

- the exact response-body bytes returned for both controlled requests;
- the binding between each body, its request tuple, endpoint, API version,
  capture interval, byte length, and SHA-256 digest;
- the completeness of every resource/policy pair and cardinality inventory;
- the distinction between controlled project evidence and unobserved folder or
  organization behavior;
- all credentials and authorization material used only to authenticate the
  reads;
- the no-mutation boundary; and
- the absence of authority transfer from evidence capture to parser
  implementation or production acceptance.

### 5.2 Trusted components and actors

Subject to later exact approval, this slice trusts only:

- the task user to identify the exact pre-existing controlled fixtures and to
  state that their complete response contents are suitable for public
  repository review;
- a pre-existing authenticated HTTP session whose credential is already
  separately authorized for these two reads;
- TLS authentication of
  `policytroubleshooter.googleapis.com` through the host trust store;
- the operating system and HTTP stack to deliver the response entity bytes
  after transport framing is removed;
- SHA-256 and standard RFC 4648 base64 implementations;
- strict UTF-8 and duplicate-aware JSON parsing performed only after the bytes
  are frozen; and
- both bounded reviewers to inspect the same published bytes and independently
  check the inventory.

Git, GitHub, CI, comments, reviews, branch names, hashes, and this RFC are
evidence and controls, not user approval authority. Capture timestamps are
provenance metadata only and establish no trusted-time or currentness claim.

### 5.3 Untrusted inputs and behavior

- every request-fixture value until it matches the approved preflight record;
- every response status, header, byte, JSON member, string, enum, number,
  array, object, omission, duplicate, and ordering choice;
- every `fullResourceName`, `Policy.name`, resource count, policy count, and
  attachment kind;
- compressed, redirected, truncated, oversized, non-UTF-8, duplicate-member,
  or non-JSON responses;
- a provider response containing identifiers or policy material outside the
  publication-safe fixture;
- a project response that contains a folder or organization attachment;
- local console, shell history, logs, chat output, temporary files, and error
  messages as possible disclosure surfaces; and
- success of the HTTP call as evidence of parser correctness, credential
  identity, least privilege, support currentness, or production readiness.

### 5.4 Explicitly excluded attacker capabilities

- compromise of Google, TLS, the operating system, kernel, HTTP stack, SHA-256,
  base64 implementation, Git, GitHub, or both independent reviewers;
- arbitrary in-process mutation after the complete bytes and digests have been
  frozen;
- compromise of the pre-existing credential or the system that supplies it;
  and
- malicious task-user approval of knowingly unsafe publication.

Ordinary provider errors, malformed evidence, accidental disclosure risk,
identifier mismatch, incomplete visibility, and repository scope expansion
remain in scope and must stop fail-closed.

### 5.5 Mandatory preflight supplied before any provider call

A future complete live card must contain one closed, publication-safe fixture
manifest with:

- the exact deny-bearing request's principal, permission, KMS full resource
  name, and complete condition-context object;
- the exact expected project number, complete project attachment resource, and
  complete IAM v2 deny-policy name;
- the exact no-deny request's principal, permission, KMS full resource name,
  and complete condition-context object;
- a statement that both projects, resources, principals, policy IDs, member
  identities, conditions, and policy contents are controlled non-production
  data approved for public repository publication;
- a non-secret label for the already-authorized authenticated session; and
- confirmation that the credential itself, tokens, headers, local credential
  paths, and credential metadata will not be captured or published.

The fixture manifest contains no secret. If displaying any required fixture
value would itself be unsafe, no complete live card may be displayed and this
decision cannot be approved.

The deny-bearing fixture must already contain exactly one intentionally simple
project-attached deny policy relevant to its closed access tuple. The no-deny
fixture must already be free of relevant deny policies at the project and all
ancestors so the returned deny explanation can contain an explicitly present
empty `explainedResources` list. This RFC does not establish those facts by
discovery; the response either demonstrates the required shape or the capture
fails.

## 6. Authority map

| Decision | Sole authority | Forbidden substitute |
| --- | --- | --- |
| Whether capture may begin | Exact later task-user approval after the complete live card | This draft, a generic `go`, GitHub review, credential availability, or PR #322 approval |
| Request tuple | Exact publication-safe fixture manifest in the approved card | Environment discovery, provider search, response-selected value, default project, or caller improvisation |
| Endpoint and version | Exact `POST https://policytroubleshooter.googleapis.com/v3beta/iam:troubleshoot` | Stable v3, alternate host, redirect, proxy rewrite, query parameter, or `testIamPermissions` |
| Authentication | One pre-existing separately authorized session supplied at execution | New credential, impersonation, token command, credential file, or response metadata |
| Complete response identity | Frozen entity-body byte sequence, byte length, and SHA-256 | Parsed JSON, pretty printing, selected fields, screenshot, log, or digest without bytes |
| Publishable evidence | Complete bytes from the approved controlled fixture after the safety gate | Redaction, pseudonym substitution, truncation, excerpt, or informal out-of-band view |
| Attachment observations | Every pair found in the same complete deny-bearing body | Documentation example, pair from another response, inferred kind, or first policy only |
| Capture result | One complete section 10 record satisfying every invariant | HTTP 200 alone, successful parser, reviewer preference, or provider reputation |
| Consumer authority | PR #322's later exact evidence-bearing decision and approval | This capture result or approval |

## 7. Fixed call set and ordering

### 7.1 Call budget

Prospective Phase B permits exactly two provider calls, sequentially and once
each:

1. `D1`: the controlled project-attached deny-bearing access tuple; then
2. `N1`: the controlled no-deny access tuple.

There is no retry, redirect, polling, discovery, list, preflight provider call,
parallel call, folder call, organization call, or cleanup provider call. A
transport failure, timeout, non-200 response, malformed response, or refused
result consumes that call and stops the run. A later attempt requires a new
explicit user authorization identifying the failed run; it is not an automatic
retry under the original approval.

### 7.2 Exact request protocol

Each call uses:

```text
POST https://policytroubleshooter.googleapis.com/v3beta/iam:troubleshoot
timeout: 5.0 seconds
redirects: disabled
query parameters: none
Accept: application/json
Content-Type: application/json; charset=utf-8
Accept-Encoding: identity
```

The request body contains only the one exact `accessTuple` and exact condition
context from the approved fixture manifest. It is encoded once as strict UTF-8
JSON with sorted object keys, separators `,` and `:`, no insignificant
whitespace, no byte-order mark, and no terminal newline. The receipt records
the complete request body in standard base64, its byte length, and its SHA-256
digest so reviewers can bind the response to the exact public request.

The authentication header and all credential material are supplied below the
capture boundary. They are never included in the request-body record, console
output, shell history, RFC, error, or digest input.

### 7.3 Exact response-byte boundary

The captured response body is the ordered octet sequence delivered by the HTTP
stack after HTTP/1.1 chunk framing or HTTP/2 framing is removed. Response
headers and framing bytes are excluded. Because the request requires identity
encoding, `Content-Encoding` must be absent or exactly `identity`; any other
value refuses before publication. No decompression is performed inside the
evidence boundary.

The capture accumulates the entity-body octets once, in order, with a hard
maximum of `1048576` bytes. Zero bytes and any byte beyond that limit refuse.
Before decoding, parsing, newline handling, or copying, it freezes:

- the exact byte length; and
- lowercase hexadecimal SHA-256 over bytes `0` through `byteLength - 1`.

No HTTP header, marker, code fence, base64 whitespace, appended newline, or
decoded character participates in that digest. No byte is normalized. In
particular, CRLF, LF, spaces, object-member order, escape spelling, and the
presence or absence of a terminal newline remain part of the evidence.

Only after freezing does the capture require status `200`, JSON content type,
strict UTF-8 without a byte-order mark, exactly one JSON value, no duplicate
object member, no non-JSON numeric constant, and no trailing non-whitespace
content. Parsing never replaces the frozen bytes.

### 7.4 Publication encoding

Each complete frozen body is published in this RFC as standard padded RFC 4648
base64, wrapped at exactly 76 ASCII characters per line except the final line.
Removing only ASCII line breaks from that block and base64-decoding must
produce exactly `byteLength` bytes and the recorded SHA-256 digest.

The RFC also publishes a readable parsed inventory. That inventory is derived
evidence only; if it disagrees with the decoded body, the body controls and the
capture fails. Pretty-printed JSON, an excerpt, a redacted body, or only a hash
cannot replace the base64 block.

## 8. State machine and safety gate

The only permitted transition is:

```text
UNAPPROVED
  -> APPROVED
  -> PREFLIGHT_VALIDATED
  -> D1_REQUEST_FROZEN
  -> D1_RESPONSE_FROZEN
  -> D1_PARSED_AND_INVENTORIED
  -> N1_REQUEST_FROZEN
  -> N1_RESPONSE_FROZEN
  -> N1_PARSED_AND_INVENTORIED
  -> PUBLICATION_SAFETY_VALIDATED
  -> RFC_RECORD_RENDERED
  -> CAPTURE_COMPLETE

any failure after APPROVED -> STOPPED_WITH_NO_ACCEPTED_EVIDENCE
```

No partial state grants authority. `D1` cannot be accepted without `N1`, and a
valid `N1` cannot cure a failed `D1`.

Before a body is printed to a terminal, included in a tool result, sent through
chat, staged, committed, or pushed, the operator must inspect it through a
local disclosure-controlled view and confirm that every identifier, member,
policy, condition, justification, and other value belongs to the approved
controlled publication-safe fixture. Authorization headers and tokens are not
body evidence and their presence anywhere refuses.

If either body includes an unexpected identifier, production-shaped value,
personal data, secret, credential material, provider diagnostic that is unsafe
to publish, or content outside the approved fixture, the run stops. The body
must not be redacted and then accepted. It remains unaccepted local material
and requires a separate evidence-custody or replacement-fixture decision.

Temporary response storage, if the HTTP client requires it, must be one newly
created owner-readable regular file in an execution-specific temporary
directory, never a repository path, symlink, log, shell variable displayed by
the shell, or shared cache. It may contain only the two bodies and fixed local
metadata, never a credential or authorization header. Accepted evidence moves
only through the complete base64 publication record. Rejected temporary
material is removed without being displayed; this decision establishes no
durable evidence store or secure-erasure claim.

## 9. Invariants and refusal cases

### 9.1 Normative invariants

- `OPEC-001` — No call occurs before exact approval and complete preflight;
  exactly `D1` then `N1` may occur, once each, with no retry or other provider
  operation.
- `OPEC-002` — Both requests use the fixed endpoint, v3beta version, headers,
  canonical public body, timeout, no-query, no-redirect, and identity-encoding
  contract.
- `OPEC-003` — Each complete response body is frozen before parsing and bound
  to its exact byte range, length, SHA-256, and lossless base64 publication.
- `OPEC-004` — The `D1` inventory includes every
  `denyPolicyExplanation.explainedResources[]` index, exact
  `fullResourceName`, every enclosed `explainedPolicies[]` index and complete
  `policy.name`, the per-resource policy counts, total policy count, resource
  count, derived attachment spelling, and attachment kind.
- `OPEC-005` — Every present `D1` explained resource has at least one visible
  policy; all policy names are project-attached; all derived attachment
  spellings equal their containing full resource names byte-for-byte; and all
  pairs belong to the approved fixture.
- `OPEC-006` — `N1` contains an explicitly present exact empty
  `denyPolicyExplanation.explainedResources` array, with resource and policy
  cardinalities both zero.
- `OPEC-007` — Both complete bodies are publication-safe and both bounded
  reviewers inspect the exact same decoded bytes; no redaction, extraction,
  digest-only, or out-of-band substitute is accepted.
- `OPEC-008` — The run creates no provider mutation, credential act, durable
  secret store, production acceptance, parser implementation, runtime effect,
  or authority transfer to PR #322.

### 9.2 Mandatory `D1` derivation

For every complete policy name matching:

```text
policies/cloudresourcemanager.googleapis.com%2Fprojects%2F<positive-decimal>/
denypolicies/<policy-id>
```

the inventory removes only the exact `policies/` prefix and exact
`/denypolicies/<policy-id>` suffix, replaces only the two exact uppercase
`%2F` separators with `/`, and prepends `//`.

The derived spelling must be exactly:

```text
//cloudresourcemanager.googleapis.com/projects/<same-positive-decimal>
```

It must equal the containing `fullResourceName` by exact UTF-8 string equality.
General URL decoding, lowercase `%2f`, project ID substitution, numeric lookup,
case folding, trailing-slash removal, Unicode normalization, ancestor
inference, or logical-equivalence comparison is forbidden.

### 9.3 Refusal matrix

| Condition | Required result |
| --- | --- |
| Missing approval, fixture value, publication statement, or authenticated session | Zero calls; stop |
| Fixture requires provisioning, discovery, credential change, or production data | Zero calls; split prerequisite |
| Wrong method, host, path, version, query, redirect, timeout, body, or call order | Stop; no evidence accepted |
| Timeout, transport failure, status other than 200, retry request, compressed body, empty body, or body over 1 MiB | Stop; no retry |
| Invalid UTF-8, BOM, duplicate JSON member, non-JSON constant, trailing value, or unsafe content | Stop; do not publish |
| `D1` has zero explained resources, a present resource with zero policies, or an omitted required field | Stop; revise the consumer design |
| Any `D1` policy is folder-attached, organization-attached, malformed, unrecognized, or outside the controlled fixture | Stop; do not treat it as incidental evidence |
| Any derived attachment differs, including project ID versus project number | Stop; new attachment-binding decision version required |
| `N1.explainedResources` is omitted, nonempty, null, malformed, or not an array | Stop; do not infer empty |
| Any pair or cardinality is omitted from the record | Stop; record is incomplete |
| Complete bytes cannot be published or both reviewers cannot inspect the same bytes | Stop; separate reviewer-channel/evidence-custody decision |
| A reviewer can reproduce the digest but not the inventory, or vice versa | Stop; no partial acceptance |

## 10. Exact evidence record

### 10.1 Record shape

Prospective Phase B replaces the provisional marker in section 10.2 with one
complete record containing, for each of `D1` and `N1`:

- capture ID;
- UTC start and completion timestamps in `YYYY-MM-DDTHH:MM:SS.ffffffZ` form;
- method, complete endpoint, and API version `v3beta`;
- response status, media type, and content-encoding disposition;
- the exact response hash boundary stated in section 7.3;
- complete canonical request-body base64, byte length, and SHA-256;
- complete response-body base64, byte length, and SHA-256;
- parsed `denyPolicyExplanation.explainedResources` presence and count;
- one policy count for every resource and the total policy count;
- every indexed exact `fullResourceName` / complete `Policy.name` pair;
- the derived attachment spelling and attachment kind for every pair;
- the sorted unique attachment kinds observed;
- publication-safety outcome; and
- capture outcome.

The record then states the combined observed-kind set, both reviewer identities
and exact-head review references, and whether each reviewer independently
decoded both bodies, reproduced both hashes, checked every pair, and checked
every cardinality. Review references are filled only after review; blank or
self-attested reviewer fields do not pass.

The record must not contain authorization headers, tokens, credential paths,
credential subject metadata, private keys, cookies, or complete response
headers. Status, media type, and content encoding are the only response-header
semantics this decision records. The complete-body hash intentionally excludes
all headers.

### 10.2 Provisional execution record

```text
CAPTURE STATUS: UNEXECUTED
D1 REQUEST: NOT SENT
D1 RESPONSE: NOT CAPTURED
N1 REQUEST: NOT SENT
N1 RESPONSE: NOT CAPTURED
OBSERVED ATTACHMENT KINDS: NONE
REVIEWER 1 SAME-BYTE VERIFICATION: NOT PERFORMED
REVIEWER 2 SAME-BYTE VERIFICATION: NOT PERFORMED
CONSUMER AUTHORITY: NONE
```

No current local edit, branch, review, user message, or generic `go` changes
that record.

### 10.3 Successful result semantics

A complete successful record establishes only these provisional facts:

- at the recorded time, the controlled `D1` response used exact matching
  project attachment spellings for every visible same-response pair;
- every present `D1` resource had at least one visible policy;
- the controlled `N1` response explicitly carried an empty explained-resource
  array; and
- both reviewers inspected the same complete published bodies.

It does not establish folder behavior, organization behavior, all possible
project behavior, policy completeness outside the controlled fixture,
credential identity, least privilege, provider support currentness, parser
correctness, production acceptance, deployment readiness, or any runtime
authority.

## 11. Phase boundaries and repository effects

### 11.1 Phase A

Phase A may draft, review, correct, commit, push, and merge only this RFC after
the task user separately authorizes each remote publication action. It performs
zero provider calls and uses zero credentials. The proposed decision remains
unapproved until section 13's ordered approval gate completes.

### 11.2 Prospective Phase B

After exact decision approval, prospective Phase B may:

1. validate the fixed public preflight manifest without a provider call;
2. use the already-authorized authenticated session for exactly `D1` and `N1`;
3. hold the two bounded bodies temporarily under section 8;
4. amend only this RFC by replacing section 10.2 with the complete record;
5. run repository conformance and hosted checks;
6. commit and push that one evidence-only amendment under the approved draft
   pull request; and
7. request two bounded exact-head evidence reviews.

It may not commit a script, raw credential, separate evidence file, response
header dump, log, screenshot, test fixture, parser change, or generated
artifact. If the complete base64 evidence makes this single RFC exceed a
reviewer's bounded capacity, the capture stops before publication and requires
a separately reviewed complete-byte artifact/channel design. It may not split,
truncate, summarize, or redact the evidence to fit.

### 11.3 Consumer sequence

Even after this decision completes:

1. PR #322 remains blocked and unapproved;
2. its RFC must separately copy the exact complete accepted bytes and digests,
   enumerate the same pairs/cardinalities, and narrow implementation to project
   attachments only;
3. its final evidence-bearing head must pass hosted checks and receive two
   superseding zero-Blocker reviews; and
4. only its own complete live card followed by its own exact task-user
   approval can authorize attachment-binding implementation.

No approval or review from this decision substitutes for any consumer gate.

## 12. Verification and review plan

### 12.1 Phase A verification

- exact reviewed base remains recorded;
- this RFC is the only changed path;
- the primary acquisition/publication boundary is not mixed with parser,
  credential, provisioning, provider-acceptance, runtime, database, or
  deployment work;
- the call budget, byte boundary, publication encoding, inventory, refusal
  matrix, and consumer non-authority are internally consistent;
- `python3 conformance/ofarm_pkg_contract_check.py` passes;
- hosted checks pass on one exact RFC head;
- two independent bounded reviewers inspect that same head; and
- all demonstrated in-scope Blockers are corrected before a live card.

### 12.2 Phase B verification

- reproduce `OPEC-001` through `OPEC-008` before any call;
- match every preflight value to the approved card without discovery;
- prove the HTTP client has redirects and retries disabled before supplying
  authentication;
- prove request bodies match their recorded base64, lengths, and hashes;
- freeze response bytes before parsing and enforce the exact size/encoding
  boundary;
- decode each published response base64 independently and reproduce its length
  and SHA-256;
- parse with duplicate-member and non-JSON-constant refusal;
- enumerate all resources and all policies, preserving array indices in the
  evidence inventory;
- independently recompute every project attachment and exact equality;
- prove `N1` has an explicitly present empty array;
- prove no response, token, header, credential path, or temporary body entered
  console, chat, log, shell history, Git, or GitHub before the publication
  safety gate;
- inspect the exact one-file diff;
- run `git diff --check` and
  `python3 conformance/ofarm_pkg_contract_check.py`;
- obtain hosted exact-head checks; and
- obtain two exact-head reviews in which both reviewers attest that they
  inspected the same complete decoded bodies and found zero demonstrated
  in-scope Blockers.

### 12.3 Review classification

A Phase A finding is an in-scope Blocker when it demonstrates that an
`OPEC-001` through `OPEC-008` invariant cannot hold, that the two-call capture
is internally contradictory, that complete same-byte review is impossible, or
that this decision crosses its primary trust boundary.

Provisioning, credential custody, wider provider currentness, parser design,
runtime integration, deployment, folder/organization capture, and issue
closure remain separate decisions unless the finding proves this capture
cannot stay bounded without one of them.

## 13. Proposed approval boundary

This local draft, any future draft pull request, checks, reviews, branch, commit,
credential availability, PR #322 approval, or generic `go` grants no Phase B
authority.

Only after one exact Phase A RFC head passes hosted checks and receives two
independent reviews reporting zero demonstrated in-scope Blockers may one
complete live decision card be displayed in this same Codex task. The card
must include:

- decision ID and version;
- parent issue and dependent PR #322;
- exact RFC, draft-PR, reviewed-base, and review-head references;
- the one primary trust boundary;
- the complete publication-safe fixture manifest from section 5.5;
- all eight invariants;
- the exact two-call budget and ordering;
- the complete hash boundary, size bound, and publication channel;
- the authorized temporary and repository effects;
- every excluded provisioning, credential, mutation, production,
  provider-acceptance, parser, runtime, database, deployment, and consumer
  authority;
- review disposition and all stop conditions; and
- the exact approval sentence below.

The required exact approval form is:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-OBSERVER-ROOT-PROVIDER-EVIDENCE-CAPTURE-001 version 1.
```

Approval is recognized only when that sentence is the exact entire later
task-user message after the complete live card, in this same task and in that
order. No current message supplies it.

That approval would authorize only the two read-only provider calls, bounded
temporary evidence custody, one-RFC evidence amendment, commits, pushes,
bounded review handling, and merge described here. It would not authorize
fixture provisioning, provider mutation, credential creation or custody
change, production access, folder/organization capture, provider production
acceptance, PR #322 publication or implementation, runtime integration,
deployment, release, issue closure, or a security waiver.

## 14. Stop rule and dependency handoff

Stop before any provider call if:

- the exact live card, two zero-Blocker reviews, or exact later approval is
  absent or not retrievable in order;
- either controlled fixture, its publication-safe declaration, or its
  separately authorized authenticated session is absent;
- a preflight value requires discovery or is not safe to publish; or
- `main` moves in a way that changes this decision's dependency or scope.

Stop after a call with no accepted evidence if any section 9 refusal occurs.
Do not retry, redact, infer, provision, mutate, or expand scope. Report only
non-sensitive failure metadata and request a separate decision or new exact
authorization as applicable.

Stop before merge if:

- the complete base64 bodies, hashes, inventories, and cardinalities are not
  all present on one exact RFC head;
- either reviewer did not inspect the same decoded complete bytes;
- any accepted attachment kind is not controlled and observed in this run;
- the diff contains any path other than this RFC;
- a provider, credential, parser, runtime, database, or deployment mutation
  appears; or
- either exact-head reviewer reports a demonstrated in-scope Blocker.

After a successful merge, hand only the immutable complete-byte record and its
explicit project-only limitation to the separately governed attachment-binding
decision. That handoff is evidence, not authority. PR #322 must remain stopped
until its own evidence-bearing contract, hosted checks, reviews, decision card,
and exact approval complete.

## 15. Current disposition

- **Local draft base:** `bdf636d155e45ecbf4d9ac828e232bbcf91e1d59`.
- **Provider calls made under this decision:** zero.
- **Credentials used under this decision:** none.
- **Responses captured:** none.
- **Attachment kinds observed:** none.
- **Remote publication:** none.
- **Phase A reviews:** none.
- **Decision approval:** absent.
- **Phase B authority:** absent.
- **PR #322 authority changed:** none.
- **Primary trust-boundary scope:** retained as read-only controlled evidence
  acquisition and publication only.
