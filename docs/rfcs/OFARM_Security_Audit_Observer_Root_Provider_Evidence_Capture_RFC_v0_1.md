# OFARM Security-Audit Observer-Root Provider-Evidence Capture — Phase A Contract v0.1

**Status:** changes required after exact-head Phase A review; local RFC-only
amendment prepared and uncommitted; unapproved; no `iam:troubleshoot` call,
Google/provider credential use, or Phase B authority

**Contract identity:**
`ofarm2.security-audit-observer-root-provider-evidence-capture.v0.1`

**Decision identity:**
`ISSUE192-SECURITY-AUDIT-OBSERVER-ROOT-PROVIDER-EVIDENCE-CAPTURE-001`,
proposed version `1`

**Issue relationship:** issue #192 remains open; this is a separate prerequisite
for the provider-evidence gate in the observer-root attachment-binding decision

**Dependent draft pull request:**
[PR #322](https://github.com/samovers/OFARM2/pull/322)

**Draft pull request for this decision:**
[PR #323](https://github.com/samovers/OFARM2/pull/323)

**Published review head before this amendment:**
`51244a804d05448e2d34c2c5a8debc49b7ddb2db`

**Reviewed base:** `bdf636d155e45ecbf4d9ac828e232bbcf91e1d59`

**Primary trust boundary:** authenticated, read-only acquisition and
publication of controlled Google Policy Troubleshooter response evidence

**Phase A review-head boundary:** this RFC only

**Prospective Phase B effect boundary:** execution of the exact review-bound
non-refreshing capture source in section 7.2 for exactly two authenticated
read-only `POST` requests to the fixed Policy Troubleshooter v3beta endpoint,
bounded in-memory custody of their response bodies, and an evidence-only
amendment to this RFC

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
2. capture one complete, determinate response for a pre-existing controlled
   project whose deny explanation is exactly `NOT_DENIED`, supports the
   selected deny permission, has permitted relevance, and has an explicitly
   present empty `explainedResources` array;
3. use one exact review-bound program that accepts only a bearer value already
   materialized in memory and has no refresh, replay, proxy-discovery,
   credential-discovery, environment, application-level credential/evidence
   filesystem, subprocess, or logging path;
4. freeze and hash each complete response body before UTF-8 decoding or JSON
   parsing;
5. bind each returned `accessTuple` exactly to its frozen request tuple before
   using its deny explanation;
6. publish the exact complete bytes without redaction or reserialization;
7. enumerate every relevant explained-resource/policy pair, determinate outer
   deny field, and required cardinality from those same bytes; and
8. transfer no implementation, provider-acceptance, credential-custody, or
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

Draft PR #323 changes only this RFC and remains Draft and unmerged through
Phase A review, exact approval, both external reads, the evidence amendment,
hosted checks, and two exact-head evidence reviews. It may merge only after the
complete accepted record passes section 14.

The exact ephemeral capture source is published inside this RFC, not as a
second repository path. Phase B may extract and execute only those exact bytes
after verifying their SHA-256. It may not add a durable capture tool,
dependency, workflow, credential file, fixture provisioner, parser change,
runtime path, or second repository artifact. Any different or durable capture
tool is a separately reviewed implementation decision.

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
- credential creation, selection, materialization, impersonation, export,
  printing, storage, refresh, rotation, revocation, or alternate-credential
  inspection;
- access-token, authorization-header, cookie, private-key, client-secret, or
  application-default-credential publication;
- production resources, production principals, production policy contents,
  customer data, tenant data, personal data, or secret-bearing responses;
- folder- or organization-attached evidence in version 1;
- a hierarchy lookup, project-ID-to-number lookup, Resource Manager call,
  policy list, search, enumeration, retry, redirect, fallback endpoint, stable
  v3 call, or `testIamPermissions` call;
- validation of allow-policy, deny-rule, PAB, membership, or overall-access
  semantics beyond the exact request binding and determinate deny-evidence
  inventory in this RFC;
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
- the binding between each body, its exact repeated request tuple, endpoint,
  API version, capture interval, byte length, and SHA-256 digest;
- the exact source identity and two-entry network-effect ledger used to obtain
  those bodies without refresh, replay, proxy, or hidden authentication I/O;
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
- one bearer authorization value that a separate credential authority has
  already materialized in memory and authorized for these two reads before the
  capture program is entered;
- the exact 483-line, review-bound Python source in section 7.2 at its recorded
  SHA-256, executed by CPython 3.12.13 with `-I -S -B`, using only the named
  standard-library modules and direct `http.client.HTTPSConnection` transport;
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
- any generic authenticated session, `google-auth`, `requests`, ADC, metadata
  lookup, token exchange, impersonation, refresh hook, 401 replay, retry
  adapter, redirect handler, proxy discovery, or environment-derived network
  configuration;
- every response status, header, byte, JSON member, string, enum, number,
  array, object, omission, duplicate, and ordering choice;
- every returned `accessTuple`, `fullResourceName`, `Policy.name`, deny state,
  visibility field, resource count, policy count, and attachment kind;
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
  name, and complete selected condition-context object;
- the exact expected project number, complete project attachment resource, and
  complete IAM v2 deny-policy name;
- the exact ordered `D1` resource/policy pair list and expected determinate
  outer deny state `DENY_ACCESS_STATE_DENIED`;
- the exact no-deny request's principal, permission, KMS full resource name,
  and complete selected condition-context object;
- the exact expected `N1` outer values
  `DENY_ACCESS_STATE_NOT_DENIED`, `permissionDeniable: true`, an outer
  relevance in the permitted set, and an explicitly present empty
  `explainedResources` list;
- `maxPublishableBodyBytes: 131072`, which is both the transport and complete
  publication bound for each response;
- section 7.2's program ID, exact source line count, source-byte boundary, and
  SHA-256;
- exact CPython `3.12.13` and `-I -S -B` runtime identity, plus confirmation
  that the source is hashed, compiled, and executed only in memory;
- a statement that both projects, resources, principals, policy IDs, member
  identities, conditions, and policy contents are controlled non-production
  data approved for public repository publication;
- a non-secret reference to the separate credential authority that can
  materialize and supply one bearer value in memory immediately before program
  entry without using authority from this decision;
- confirmation that capture begins only after materialization and that the
  exact program receives the bearer value directly as its sole secret
  function argument;
- confirmation that the execution process has no proxy, auth-discovery,
  credential, token, or retry environment/configuration and that no wrapper
  adds network I/O, logging, refresh, replay, or headers;
- confirmation that `SSL_CERT_FILE`, `SSL_CERT_DIR`, `SSLKEYLOGFILE`,
  `OPENSSL_CONF`, and `OPENSSL_MODULES` are absent so the explicitly trusted TLS
  stack uses only the host default trust store and writes no key log; and
- confirmation that the bearer value, authorization header, local credential
  path, credential metadata, and materialization mechanism will not be
  captured, hashed, logged, printed, or published.

The fixture manifest contains no secret. If displaying any required fixture
value would itself be unsafe, no complete live card may be displayed and this
decision cannot be approved.

The exact object supplied as the program's `manifest` argument has only
`d1ExpectedPairs`, `d1Request`, `maxPublishableBodyBytes`, and `n1Request`.
Expected outer deny states, permission deniability, relevance-set membership,
explicit N1 array presence, endpoint, ordering, and size limit are hard-coded
in the reviewed source rather than caller-selectable switches.

For both requests, the complete caller-supplied condition context is exactly
one `resource` object with exactly nonempty `name`, `service`, and `type`
members. `destination`, `request`, caller-supplied `effectiveTags`, and every
other context member are forbidden. This closed shape makes equality of the
complete caller-controlled context equivalent to the resource-object equality
enforced by section 7.2.

The deny-bearing fixture must already contain exactly one intentionally simple
project-attached deny policy relevant to its closed access tuple and must be
free of every other relevant project, folder, or organization deny policy at
the resource and every ancestor. The no-deny fixture must already be free of
relevant deny policies at the project and all ancestors. The separately
authorized reader must have complete visibility of every relevant deny policy
for both fixtures. This RFC does not establish those facts by discovery; the
response either demonstrates the required complete shape or the capture fails.

The pre-materialized bearer value is a prerequisite, not an effect. If it is
absent, stale, expired, or cannot be supplied in memory without a token command,
metadata lookup, file, environment value, impersonation, or refresh, the run
does not begin. Any HTTP 401 consumes the attempted call and stops without
refresh or replay.

### 5.6 Completed unauthenticated Phase A schema check

One malformed-path unauthenticated `GET` first returned HTTP 404 after shell
expansion removed the literal `$discovery` path segment. It used no
authorization header, credential, API key, redirect, or
`iam:troubleshoot` request and produced no accepted schema evidence.

A second unauthenticated, redirect-disabled `GET` fetched Google's public
[Policy Troubleshooter v3beta discovery document](https://policytroubleshooter.googleapis.com/$discovery/rest?version=v3beta)
at `2026-08-20T09:02:18Z`. No authorization header, credential, API key, or
`iam:troubleshoot` request was used. The complete HTTP entity body was
`120285` bytes of `application/json; charset=UTF-8` with SHA-256
`4a4b2bc765fd4deb8fc2417c1b5c3482aeb4d302e6e139d0690b7d35aae4a349`.

That exact schema records:

- service ID `policytroubleshooter:v3beta`, base URL
  `https://policytroubleshooter.googleapis.com/`, method `POST`, path
  `v3beta/iam:troubleshoot`, and the `cloud-platform` OAuth scope;
- a response `accessTuple` described as the tuple from the request, including
  supplied condition context;
- output-only `permissionFqdn` and condition-context `effectiveTags`;
- determinate deny states `DENIED` and `NOT_DENIED`, plus unspecified,
  unknown-conditional, and unknown-information states;
- `permissionDeniable`, outer deny relevance, and an array of explained
  resources that climbs from the resource through project, folder, and
  organization ancestors;
- the fact that explained-resource `fullResourceName` and `relevance` may be
  omitted when the requester lacks policy access; and
- a distinct `TroubleshootIamPolicyErrorResponse` schema.

This public schema check closes only static shape questions. It does not prove
runtime attachment equality, complete visibility, empty-array emission, or the
two controlled responses. `D1` and `N1` remain separately approved Phase B
calls. A status-200 body with the error-response shape, a missing visibility
field, or any unknown state refuses.

## 6. Authority map

| Decision | Sole authority | Forbidden substitute |
| --- | --- | --- |
| Whether capture may begin | Exact later task-user approval after the complete live card | This draft, a generic `go`, GitHub review, credential availability, or PR #322 approval |
| Request tuple | Exact publication-safe fixture manifest in the approved card | Environment discovery, provider search, response-selected value, default project, or caller improvisation |
| Endpoint and version | Exact `POST https://policytroubleshooter.googleapis.com/v3beta/iam:troubleshoot` | Stable v3, alternate host, redirect, proxy rewrite, query parameter, or `testIamPermissions` |
| Authentication | One separately authorized bearer value fully materialized in memory before program entry; section 7.2 only adds its fixed `Authorization` header | Generic session, ADC, metadata, STS, impersonation, token command, file, environment, refresh, replay, or response metadata |
| Execution and network effects | Exact section 7.2 source and SHA-256; two-entry `D1`,`N1` ledger and zero auth-side calls | Wrapper, changed source, plugin, adapter, proxy, retry, redirect, refresh hook, or self-attested response bodies |
| Response/request binding | Exact equality of returned request-controlled access-tuple fields, with output-only fields validated and recorded separately | Request hash beside an unbound body, operator association, label, order alone, or response-selected tuple |
| Deny-evidence completeness | Known outer deny state, `permissionDeniable: true`, permitted relevance, complete resource fields and visible policy bodies | Empty array alone, `UNKNOWN_INFO`, `UNKNOWN_CONDITIONAL`, omission, or successful HTTP status |
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

### 7.2 Exact review-bound execution program

Phase B may execute only the complete source below. Its source bytes are the
UTF-8 LF sequence beginning with the `f` in `from __future__` and ending with
the LF immediately after the final `}`. The Markdown fences are excluded. The
source is exactly `483` lines and has SHA-256:

```text
53f65037d1b34fcde78f602a81189d4e6ce80f87d29d29e98d0126ce849db54f
```

It passed CPython 3.12.13 compilation, repository-pinned Ruff 0.15.5 check and
format check, and focused fake-transport execution under `-I -S -B` for the
valid two-call path, effective-tags presence, swapped D1/N1, every
request-controlled response-tuple field, `UNKNOWN_INFO` N1, omitted N1 resource
array, and guarded connection construction before inclusion in this amendment.
Those tests are local Phase A evidence only and do not substitute for review or
either live response.

```python
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import re
import ssl
import sys
from datetime import datetime, timezone
from typing import NoReturn

PROGRAM_ID = "ofarm2.issue192.provider-evidence-capture.v1"
HOST = "policytroubleshooter.googleapis.com"
PATH = "/v3beta/iam:troubleshoot"
ENDPOINT = "https://policytroubleshooter.googleapis.com/v3beta/iam:troubleshoot"
TIMEOUT_SECONDS = 5.0
MAX_BODY_BYTES = 131072
RELEVANCE = {"HEURISTIC_RELEVANCE_NORMAL", "HEURISTIC_RELEVANCE_HIGH"}
TOKEN = re.compile(r"[A-Za-z0-9._~+/=-]{1,8192}")
PERMISSION_FQDN = re.compile(r"[a-z0-9.-]+\.googleapis\.com/[A-Za-z][A-Za-z0-9.]+")
TAG_KEY = re.compile(r"tagKeys/[1-9][0-9]*")
TAG_VALUE = re.compile(r"tagValues/[1-9][0-9]*")
TAG_PARENT = re.compile(r"(?:organizations|projects)/[1-9][0-9]*")
NAMESPACED_TAG_KEY = re.compile(r"[A-Za-z0-9_-]+/[A-Za-z0-9._-]+")
NAMESPACED_TAG_VALUE = re.compile(r"[A-Za-z0-9_-]+/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")
PROJECT_POLICY = re.compile(
    r"policies/cloudresourcemanager\.googleapis\.com%2Fprojects%2F"
    r"([1-9][0-9]*)/denypolicies/[a-z0-9.-]+"
)


class CaptureStop(Exception):
    def __init__(self, code: str, metadata: dict[str, object] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.metadata = {} if metadata is None else metadata


def _stop(code: str) -> NoReturn:
    raise CaptureStop(code) from None


def _runtime() -> None:
    if (
        sys.implementation.name != "cpython"
        or sys.version_info[:3] != (3, 12, 13)
        or sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_site != 1
        or sys.flags.safe_path != 1
        or sys.flags.dont_write_bytecode != 1
    ):
        _stop("WRONG_PYTHON_RUNTIME")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _base64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _stop("DUPLICATE_JSON_MEMBER")
        result[key] = value
    return result


def _constant(_: str) -> NoReturn:
    _stop("NON_JSON_CONSTANT")


def _strict_json(value: bytes) -> object:
    if value.startswith(b"\xef\xbb\xbf"):
        _stop("JSON_BOM")
    try:
        text = value.decode("utf-8", "strict")
        return json.loads(
            text,
            object_pairs_hook=_object,
            parse_constant=_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        _stop("INVALID_JSON")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _members(
    value: object,
    required: tuple[str, ...],
    optional: tuple[str, ...] = (),
) -> dict[str, object]:
    if type(value) is not dict:
        _stop("WRONG_OBJECT_TYPE")
    document = value
    if not set(required).issubset(document) or not set(document).issubset(
        set(required) | set(optional)
    ):
        _stop("WRONG_OBJECT_MEMBERS")
    return document


def _text(value: object, code: str) -> str:
    if type(value) is not str or not value:
        _stop(code)
    return value


def _request(value: object) -> tuple[bytes, dict[str, object]]:
    document = _members(value, ("accessTuple",))
    access = _members(
        document["accessTuple"],
        ("conditionContext", "fullResourceName", "permission", "principal"),
    )
    context = _members(access["conditionContext"], ("resource",))
    resource = _members(context["resource"], ("name", "service", "type"))
    for key in ("fullResourceName", "permission", "principal"):
        _text(access[key], "INVALID_REQUEST_ACCESS_TUPLE")
    for key in ("name", "service", "type"):
        _text(resource[key], "INVALID_REQUEST_RESOURCE_CONTEXT")
    body = _canonical(document)
    return body, access


def _effective_tags(value: object) -> list[dict[str, object]]:
    if type(value) is not list:
        _stop("INVALID_EFFECTIVE_TAGS")
    names = (
        "inherited",
        "namespacedTagKey",
        "namespacedTagValue",
        "tagKey",
        "tagKeyParentName",
        "tagValue",
    )
    result = []
    for value_item in value:
        item = _members(value_item, names)
        if (
            type(item["inherited"]) is not bool
            or any(type(item[name]) is not str or not item[name] for name in names[1:])
            or TAG_KEY.fullmatch(item["tagKey"]) is None
            or TAG_VALUE.fullmatch(item["tagValue"]) is None
            or TAG_PARENT.fullmatch(item["tagKeyParentName"]) is None
            or NAMESPACED_TAG_KEY.fullmatch(item["namespacedTagKey"]) is None
            or NAMESPACED_TAG_VALUE.fullmatch(item["namespacedTagValue"]) is None
        ):
            _stop("INVALID_EFFECTIVE_TAGS")
        result.append(item)
    return result


def _bind_access_tuple(
    response_value: object,
    request_value: dict[str, object],
) -> dict[str, object]:
    response = _members(
        response_value,
        (
            "conditionContext",
            "fullResourceName",
            "permission",
            "permissionFqdn",
            "principal",
        ),
    )
    for key in ("fullResourceName", "permission", "principal"):
        if response[key] != request_value[key]:
            _stop("RESPONSE_ACCESS_TUPLE_MISMATCH")
    permission_fqdn = _text(response["permissionFqdn"], "INVALID_PERMISSION_FQDN")
    if PERMISSION_FQDN.fullmatch(permission_fqdn) is None:
        _stop("INVALID_PERMISSION_FQDN")
    request_context = _members(request_value["conditionContext"], ("resource",))
    response_context = _members(
        response["conditionContext"],
        ("resource",),
        ("effectiveTags",),
    )
    if response_context["resource"] != request_context["resource"]:
        _stop("RESPONSE_RESOURCE_CONTEXT_MISMATCH")
    effective_tags_present = "effectiveTags" in response_context
    effective_tags = (
        _effective_tags(response_context["effectiveTags"])
        if effective_tags_present
        else []
    )
    return {
        "permissionFqdn": permission_fqdn,
        "effectiveTagsPresent": effective_tags_present,
        "effectiveTags": effective_tags,
    }


def _derive_project(policy_name: str) -> str:
    match = PROJECT_POLICY.fullmatch(policy_name)
    if match is None:
        _stop("NON_PROJECT_POLICY")
    return "//cloudresourcemanager.googleapis.com/projects/" + match.group(1)


def _deny_inventory(
    label: str,
    value: object,
    expected_pairs: list[list[str]],
) -> dict[str, object]:
    if label == "N1" and type(value) is dict and "explainedResources" not in value:
        _stop("N1_EXPLAINED_RESOURCES_OMITTED")
    document = _members(
        value,
        ("denyAccessState", "explainedResources", "permissionDeniable", "relevance"),
    )
    if document["permissionDeniable"] is not True:
        _stop(label + "_PERMISSION_NOT_DENIABLE")
    if document["relevance"] not in RELEVANCE:
        _stop(label + "_INVALID_RELEVANCE")
    resources = document["explainedResources"]
    if type(resources) is not list:
        _stop(label + "_INVALID_EXPLAINED_RESOURCES")
    if label == "N1":
        if document["denyAccessState"] != "DENY_ACCESS_STATE_NOT_DENIED":
            _stop("N1_INDETERMINATE_OR_DENIED")
        if resources:
            _stop("N1_NONEMPTY_EXPLAINED_RESOURCES")
        return {
            "denyAccessState": document["denyAccessState"],
            "permissionDeniable": True,
            "relevance": document["relevance"],
            "resourceCount": 0,
            "policyCounts": [],
            "totalPolicyCount": 0,
            "pairs": [],
        }
    if document["denyAccessState"] != "DENY_ACCESS_STATE_DENIED" or not resources:
        _stop("D1_NOT_DETERMINATELY_DENIED")
    pairs: list[list[object]] = []
    policy_counts: list[int] = []
    for resource_index, resource_value in enumerate(resources):
        resource = _members(
            resource_value,
            ("denyAccessState", "explainedPolicies", "fullResourceName", "relevance"),
        )
        if (
            resource["denyAccessState"]
            not in {
                "DENY_ACCESS_STATE_DENIED",
                "DENY_ACCESS_STATE_NOT_DENIED",
            }
            or resource["relevance"] not in RELEVANCE
        ):
            _stop("D1_INDETERMINATE_RESOURCE")
        full_name = _text(resource["fullResourceName"], "D1_MISSING_RESOURCE_NAME")
        policies = resource["explainedPolicies"]
        if type(policies) is not list or not policies:
            _stop("D1_MISSING_VISIBLE_POLICY")
        policy_counts.append(len(policies))
        for policy_index, explained_value in enumerate(policies):
            explained = _members(
                explained_value,
                ("denyAccessState", "policy", "relevance", "ruleExplanations"),
            )
            if (
                explained["denyAccessState"]
                not in {
                    "DENY_ACCESS_STATE_DENIED",
                    "DENY_ACCESS_STATE_NOT_DENIED",
                }
                or explained["relevance"] not in RELEVANCE
            ):
                _stop("D1_INDETERMINATE_POLICY")
            policy = _members(
                explained["policy"],
                ("createTime", "etag", "kind", "name", "rules", "uid", "updateTime"),
                ("annotations", "displayName"),
            )
            rules = policy["rules"]
            explanations = explained["ruleExplanations"]
            if (
                policy["kind"] != "DenyPolicy"
                or type(rules) is not list
                or not rules
                or type(explanations) is not list
                or len(explanations) != len(rules)
            ):
                _stop("D1_MISSING_POLICY_BODY")
            policy_name = _text(
                policy["name"],
                "D1_MISSING_POLICY_NAME",
            )
            derived = _derive_project(policy_name)
            if derived != full_name:
                _stop("D1_ATTACHMENT_MISMATCH")
            pairs.append(
                [
                    resource_index,
                    policy_index,
                    full_name,
                    policy_name,
                    derived,
                    "project",
                ]
            )
    observed_pairs = [[item[2], item[3]] for item in pairs]
    if observed_pairs != expected_pairs:
        _stop("D1_FIXTURE_PAIR_MISMATCH")
    return {
        "denyAccessState": document["denyAccessState"],
        "permissionDeniable": True,
        "relevance": document["relevance"],
        "resourceCount": len(resources),
        "policyCounts": policy_counts,
        "totalPolicyCount": sum(policy_counts),
        "pairs": pairs,
    }


def _post(
    label: str,
    bearer_token: str,
    request_body: bytes,
    request_access: dict[str, object],
    expected_pairs: list[list[str]],
    ledger: list[dict[str, object]],
) -> dict[str, object]:
    started_at = _utc_now()
    entry: dict[str, object] = {
        "ordinal": len(ledger) + 1,
        "label": label,
        "method": "POST",
        "endpoint": ENDPOINT,
        "startedAt": started_at,
    }
    ledger.append(entry)
    connection: http.client.HTTPSConnection | None = None
    try:
        connection = http.client.HTTPSConnection(
            HOST,
            443,
            timeout=TIMEOUT_SECONDS,
            context=ssl.create_default_context(),
        )
        connection.request(
            "POST",
            PATH,
            body=request_body,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "Authorization": "Bearer " + bearer_token,
                "Connection": "close",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        response = connection.getresponse()
        status = response.status
        content_types = response.headers.get_all("Content-Type", [])
        content_encodings = response.headers.get_all("Content-Encoding", [])
        body = response.read(MAX_BODY_BYTES + 1)
    except Exception:
        _stop(label + "_TRANSPORT_FAILURE")
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
    entry["completedAt"] = _utc_now()
    entry["status"] = status
    if len(body) == 0 or len(body) > MAX_BODY_BYTES:
        _stop(label + "_BODY_SIZE")
    body_sha256 = _sha256(body)
    if status != 200:
        _stop(label + "_HTTP_STATUS")
    if (
        len(content_types) != 1
        or content_types[0].split(";", 1)[0].strip().lower() != "application/json"
    ):
        _stop(label + "_CONTENT_TYPE")
    if len(content_encodings) > 1 or (
        content_encodings and content_encodings[0].strip().lower() != "identity"
    ):
        _stop(label + "_CONTENT_ENCODING")
    try:
        parsed = _strict_json(body)
        response_document = _members(
            parsed,
            (
                "accessTuple",
                "allowPolicyExplanation",
                "denyPolicyExplanation",
                "overallAccessState",
                "pabPolicyExplanation",
            ),
        )
        access_outputs = _bind_access_tuple(
            response_document["accessTuple"], request_access
        )
        inventory = _deny_inventory(
            label,
            response_document["denyPolicyExplanation"],
            expected_pairs,
        )
    except CaptureStop as error:
        error.metadata = {
            "label": label,
            "responseByteLength": len(body),
            "responseSha256": body_sha256,
            "responseStatus": status,
        }
        raise
    return {
        "label": label,
        "requestAccessTuple": request_access,
        "requestBinding": "EXACT",
        "requestBodyBase64": _base64(request_body),
        "requestByteLength": len(request_body),
        "requestSha256": _sha256(request_body),
        "responseBodyBase64": _base64(body),
        "responseByteLength": len(body),
        "responseSha256": body_sha256,
        "responseStatus": status,
        "responseContentType": content_types[0],
        "responseContentEncoding": content_encodings[0]
        if content_encodings
        else "absent",
        "accessTupleOutputs": access_outputs,
        "denyInventory": inventory,
    }


def run_capture(
    bearer_token: str,
    manifest: dict[str, object],
) -> dict[str, object]:
    _runtime()
    if type(bearer_token) is not str or TOKEN.fullmatch(bearer_token) is None:
        _stop("INVALID_PREMATERIALIZED_BEARER_TOKEN")
    document = _members(
        manifest,
        ("d1ExpectedPairs", "d1Request", "maxPublishableBodyBytes", "n1Request"),
    )
    if document["maxPublishableBodyBytes"] != MAX_BODY_BYTES:
        _stop("WRONG_PUBLICATION_BOUND")
    expected_pairs = document["d1ExpectedPairs"]
    if type(expected_pairs) is not list or not expected_pairs:
        _stop("INVALID_EXPECTED_PAIRS")
    for pair in expected_pairs:
        if type(pair) is not list or len(pair) != 2:
            _stop("INVALID_EXPECTED_PAIRS")
        _text(pair[0], "INVALID_EXPECTED_PAIRS")
        _text(pair[1], "INVALID_EXPECTED_PAIRS")
    d1_body, d1_access = _request(document["d1Request"])
    n1_body, n1_access = _request(document["n1Request"])
    ledger: list[dict[str, object]] = []
    captures = [
        _post("D1", bearer_token, d1_body, d1_access, expected_pairs, ledger),
        _post("N1", bearer_token, n1_body, n1_access, [], ledger),
    ]
    if [entry["label"] for entry in ledger] != ["D1", "N1"]:
        _stop("WRONG_CALL_LEDGER")
    return {
        "programId": PROGRAM_ID,
        "authSideCallCount": 0,
        "policyTroubleshooterCallLedger": ledger,
        "captures": captures,
    }
```

The source receives the bearer value only as an already populated Python
function argument. It contains no token materializer, auth object, generic
session, environment access, proxy support, filesystem call, subprocess,
logger, print, redirect, retry, or recursive request path. Its only network
constructor is direct `http.client.HTTPSConnection`, and `_post` contains the
only request statement. Static review must confirm `run_capture` invokes
`_post` exactly in fixed `D1`, `N1` order and records the ledger before each
send.

The execution process is exact CPython 3.12.13 started with `-I -S -B`.
Isolated mode ignores Python environment configuration, excludes the script
directory and user site from import resolution, and enables safe-path mode;
`-S` suppresses `site` initialization, and `-B` suppresses bytecode writes.
The source's `_runtime` check revalidates all six resulting identity/flag
values at function entry.

The execution wrapper may do only four things: verify the runtime flags and
exact extracted source SHA-256 before bearer supply; compile and execute those
source bytes only in memory; call `run_capture(bearer_token, manifest)` with
the already materialized in-memory bearer value and exact public manifest; and
retain the returned object in memory for the section 8 safety gate. It may not
perform network, credential, environment, filesystem, formatting, logging, or
output work. Any different source, wrapper, import, runtime, header, transport,
or invocation stops before the bearer value is supplied.

### 7.3 Exact request and authentication protocol

Each call uses:

```text
POST https://policytroubleshooter.googleapis.com/v3beta/iam:troubleshoot
HTTP protocol: HTTP/1.1 via http.client
timeout: 5.0 seconds
redirects: disabled
query parameters: none
Host: policytroubleshooter.googleapis.com
Accept: application/json
Content-Type: application/json; charset=utf-8
Accept-Encoding: identity
Connection: close
Content-Length: exact canonical request-body byte length
```

The request body contains only the one exact `accessTuple` and exact condition
context from the approved fixture manifest. It is encoded once as strict UTF-8
JSON with sorted object keys, separators `,` and `:`, no insignificant
whitespace, no byte-order mark, and no terminal newline. The receipt records
the complete request body in standard base64, its byte length, and its SHA-256
digest so reviewers can bind the response to the exact public request.

The exact source validates the already materialized bearer value in memory and
adds only `Authorization: Bearer <value>` as authentication behavior. It has no
refresh interface. A 401, timeout, exception, or other status is terminal and
cannot replay the request. The authorization value is never included in the
request-body record, returned object, ledger, console output, shell history,
RFC, error text, or digest input.

### 7.4 Exact response-byte boundary

The captured response body is the ordered octet sequence delivered by the HTTP
stack after HTTP/1.1 framing is removed. Response headers and framing bytes are
excluded. Because the request requires identity encoding, `Content-Encoding`
must be absent or exactly `identity`; any other value refuses before
publication. No decompression is performed inside the evidence boundary.

The capture accumulates the entity-body octets once, in order, with a hard
maximum of `131072` bytes, identical to the pre-approved complete-publication
bound. Zero bytes and any byte beyond that limit refuse.
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

### 7.5 Exact response/request and deny-evidence binding

After byte freezing and strict JSON parsing, each response must have exactly
the five documented top-level members `accessTuple`, `allowPolicyExplanation`,
`denyPolicyExplanation`, `overallAccessState`, and `pabPolicyExplanation`.
This rejects the distinct error-response shape even if an intermediary returns
it with status 200.

The returned `accessTuple` must repeat the frozen request's exact `principal`,
`fullResourceName`, `permission`, and complete caller-supplied
`conditionContext.resource` object. The only admitted output additions are a
present, well-formed `permissionFqdn` and an optional `effectiveTags` array.
The exact presence of that optional member and its complete validated array in
response order are recorded separately. Neither output is compared as a
caller-supplied field.
A swapped D1/N1 body, changed principal, sibling resource, changed permission,
omitted context, or changed resource name, service, or type refuses before the
deny explanation is used.

For `D1`, outer `denyAccessState` is exactly `DENY_ACCESS_STATE_DENIED`,
`permissionDeniable` is exactly `true`, and relevance is exactly
`HEURISTIC_RELEVANCE_NORMAL` or `HEURISTIC_RELEVANCE_HIGH`. Every present
resource has a determinate deny state, permitted relevance, exact
`fullResourceName`, and a nonempty list of visible complete policy bodies. The
ordered observed pair list must equal the approved fixture manifest exactly.

For `N1`, outer `denyAccessState` is exactly
`DENY_ACCESS_STATE_NOT_DENIED`, `permissionDeniable` is exactly `true`,
relevance is permitted, and `explainedResources` is explicitly present as the
exact empty array. Unknown, unspecified, conditional, inaccessible, omitted,
null, malformed, or error-shaped evidence refuses. Empty cardinality without
those determinate outer fields is never no-deny evidence.

### 7.6 Publication encoding

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
  -> PROGRAM_AND_WRAPPER_VERIFIED
  -> PREFLIGHT_VALIDATED
  -> PREMATERIALIZED_BEARER_RECEIVED_IN_MEMORY
  -> D1_REQUEST_FROZEN
  -> D1_RESPONSE_FROZEN
  -> D1_TUPLE_BOUND_AND_DENY_INVENTORIED
  -> N1_REQUEST_FROZEN
  -> N1_RESPONSE_FROZEN
  -> N1_TUPLE_BOUND_AND_DENY_INVENTORIED
  -> PUBLICATION_SAFETY_VALIDATED
  -> RFC_RECORD_RENDERED
  -> CAPTURE_COMPLETE

any failure after APPROVED -> STOPPED_WITH_NO_ACCEPTED_EVIDENCE
publication-safe N1 array omission -> also RECORDABLE_FAILURE_METADATA
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

The exact source holds requests, responses, ledgers, and results in memory and
contains no application-level filesystem API. The explicitly trusted TLS stack
may access the host default trust store under sections 5.2 and 5.5; that access
is outside the evidence and credential paths. No wrapper may introduce a
temporary file, repository path, symlink, log, shell variable displayed by the
shell, shared cache, or durable evidence store. Accepted evidence moves only
from the in-memory returned object through the complete base64 publication
record. This decision makes no secure-erasure claim over process memory.

## 9. Invariants and refusal cases

### 9.1 Normative invariants

- `OPEC-001` — No call occurs before exact approval and complete preflight;
  exactly `D1` then `N1` may occur, once each, with no retry or other provider
  operation and with an explicit zero authentication-side-call count.
- `OPEC-002` — Only section 7.2's exact source and inert invocation wrapper may
  execute under exact CPython 3.12.13 `-I -S -B`. Authentication accepts one
  already materialized in-memory bearer value, performs zero I/O, and has no
  discovery, proxy, refresh, 401 replay, retry, redirect, environment, file,
  subprocess, or logging path.
- `OPEC-003` — Each complete response body is frozen before parsing and bound
  to its exact byte range, length, SHA-256, and lossless base64 publication.
- `OPEC-004` — The `D1` inventory includes every
  `denyPolicyExplanation.explainedResources[]` index, exact
  `fullResourceName`, every enclosed `explainedPolicies[]` index and complete
  `policy.name`, the per-resource policy counts, total policy count, resource
  count, derived attachment spelling, attachment kind, outer deny state,
  `permissionDeniable`, relevance, and complete-visibility outcome.
- `OPEC-005` — Every present `D1` explained resource has at least one visible
  complete policy body; outer and per-resource deny states are determinate;
  all policy names are project-attached; all derived attachment spellings
  equal their containing full resource names byte-for-byte; and the ordered
  pair list equals the approved ancestor-clean fixture exactly.
- `OPEC-006` — `N1` contains an explicitly present exact empty
  `denyPolicyExplanation.explainedResources` array, outer state exactly
  `DENY_ACCESS_STATE_NOT_DENIED`, `permissionDeniable` exactly true, permitted
  relevance, and resource and policy cardinalities both zero.
- `OPEC-007` — Both complete bodies are publication-safe and both bounded
  reviewers inspect the exact same decoded bytes; no redaction, extraction,
  digest-only, or out-of-band substitute is accepted.
- `OPEC-008` — The run creates no provider mutation, credential act, durable
  secret store, production acceptance, parser implementation, runtime effect,
  or authority transfer to PR #322.
- `OPEC-009` — Each response's request-controlled `accessTuple` fields equal
  its frozen request exactly. Output-only `permissionFqdn`, effective-tags
  presence, and the complete effective-tags array in response order are
  validated and recorded separately; none can substitute for request equality.
- `OPEC-010` — The final record contains the exact program identity and source
  digest, a two-entry `D1`,`N1` Policy Troubleshooter ledger, zero auth-side
  calls, every determinate deny field, and any publication-safe stopped-run
  metadata. HTTP 200 or an empty array alone never establishes completeness.

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
| Missing approval, exact source/wrapper verification, fixture value, publication statement, or pre-materialized in-memory bearer value | Zero calls; stop |
| Fixture requires provisioning, discovery, credential change, or production data | Zero calls; split prerequisite |
| Source digest or runtime mismatch, non-isolated/site-enabled/bytecode-writing execution, wrapper I/O, generic auth session, token lookup, refresh, proxy, hidden side call, replay, retry adapter, or environment-derived transport | Zero calls if found preflight; otherwise stop with no accepted evidence |
| Wrong method, host, path, version, query, redirect, timeout, header, body, or call order | Stop; no evidence accepted |
| Timeout, transport failure, status other than 200 including 401, retry request, compressed body, empty body, or body over 131072 bytes | Stop; no refresh or retry |
| Invalid UTF-8, BOM, duplicate JSON member, non-JSON constant, trailing value, or unsafe content | Stop; do not publish |
| Status 200 with the error-response shape or without the exact five success members | Stop; no evidence accepted |
| Returned access tuple swaps D1/N1, changes principal, resource, permission, context, resource service/name/type, or omits a required request field | Stop before deny evidence is used |
| Output-only permission FQDN or effective tags are malformed or presented as request authority | Stop; response is unbound |
| `D1` has unknown/unspecified outer or resource state, unsupported permission, missing relevance, zero resources, a present resource with zero policies, an omitted policy body, or another omitted required field | Stop; visibility is incomplete |
| Any `D1` policy is folder-attached, organization-attached, malformed, unrecognized, or outside the controlled fixture | Stop; do not treat it as incidental evidence |
| Any derived attachment differs, including project ID versus project number | Stop; new attachment-binding decision version required |
| `N1` state is unknown, unspecified, conditional, denied, omitted, or malformed; permission is not deniable; or relevance is absent/unsupported | Stop; empty cardinality is not complete no-deny evidence |
| `N1.explainedResources` is omitted | Stop; do not infer empty; retain only publication-safe failure code, response length/digest, status, and capture label for redesign |
| `N1.explainedResources` is nonempty, null, malformed, or not an array | Stop; no accepted evidence |
| Any pair or cardinality is omitted from the record | Stop; record is incomplete |
| Complete bytes cannot be published or both reviewers cannot inspect the same bytes | Stop; separate reviewer-channel/evidence-custody decision |
| A reviewer can reproduce the digest but not the inventory, or vice versa | Stop; no partial acceptance |

## 10. Exact evidence record

### 10.1 Record shape

Prospective Phase B replaces the provisional marker in section 10.2 with one
complete record. Before the per-call records it contains:

- program ID, exact 483-line source-byte boundary, source SHA-256, CPython
  `3.12.13`, and `-I -S -B` runtime verification;
- execution-wrapper inspection outcome;
- `authSideCallCount: 0`;
- the complete two-entry Policy Troubleshooter call ledger, including ordinal,
  label, method, endpoint, start, completion, and response status; and
- confirmation that the bearer value was materialized before entry and never
  captured, while recording no bearer value, expiry, subject, header, or
  materialization metadata.

For each of `D1` and `N1`, it then contains:

- capture ID;
- UTC start and completion timestamps in `YYYY-MM-DDTHH:MM:SS.ffffffZ` form;
- method, complete endpoint, and API version `v3beta`;
- response status, media type, and content-encoding disposition;
- the exact response hash boundary stated in section 7.4;
- complete canonical request-body base64, byte length, and SHA-256;
- complete response-body base64, byte length, and SHA-256;
- the exact request-controlled access tuple and an exact-equality result for
  principal, full resource name, permission, condition context, and resource
  service/name/type;
- returned output-only `permissionFqdn`, effective-tags member presence, and
  complete effective-tags array in response order, recorded separately from
  request equality;
- outer deny state, `permissionDeniable`, and relevance;
- parsed `denyPolicyExplanation.explainedResources` presence and count;
- one policy count for every resource and the total policy count;
- every indexed exact `fullResourceName` / complete `Policy.name` pair;
- the derived attachment spelling and attachment kind for every pair;
- the sorted unique attachment kinds observed;
- complete-policy-visibility and determinate-state outcomes;
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

If `N1` omits `explainedResources`, no capture succeeds and no response body is
accepted or published under the success channel. After the ordinary safety
gate, the RFC may record only fixed failure code
`N1_EXPLAINED_RESOURCES_OMITTED`, label, status, response byte length, and
response SHA-256. That stopped-run metadata establishes neither empty
cardinality nor no-deny evidence, but preserves the serialization observation
needed for a new parser decision.

### 10.2 Provisional execution record

```text
CAPTURE STATUS: UNEXECUTED
PROGRAM SOURCE: EMBEDDED; 483 LINES; SHA-256 53f65037d1b34fcde78f602a81189d4e6ce80f87d29d29e98d0126ce849db54f
AUTH SIDE CALLS: NOT PERFORMED
POLICY TROUBLESHOOTER CALL LEDGER: EMPTY
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
- both returned access tuples exactly repeated their frozen request-controlled
  fields;
- all accepted deny states were determinate and all required policy evidence
  was visible;
- the controlled `N1` response explicitly carried a determinate not-denied
  result and an empty explained-resource array; and
- both reviewers inspected the same complete published bodies.

It does not establish folder behavior, organization behavior, all possible
project behavior, policy completeness outside the ancestor-clean controlled
fixture, behavior when `fullResourceName` or resource relevance is omitted for
lack of policy access, credential identity, least privilege, provider support
currentness, parser correctness, production acceptance, deployment readiness,
or any runtime authority.

## 11. Phase boundaries and repository effects

### 11.1 Phase A

Phase A may draft, review, correct, commit, and push only this RFC after the
task user separately authorizes each remote publication action. PR #323 stays
Draft and unmerged through exact approval and the evidence amendment because
the same PR owns the complete capture record. Phase A performs zero
`iam:troubleshoot` calls and uses zero Google/provider credentials. Its
completed public discovery-schema GET is recorded in section 5.6. The proposed
decision remains unapproved until section 13's ordered approval gate completes.

### 11.2 Prospective Phase B

After exact decision approval, prospective Phase B may:

1. verify section 7.2's exact source and inert wrapper before supplying a
   bearer value;
2. validate the fixed public preflight manifest without an
   `iam:troubleshoot` call;
3. receive the already materialized bearer value directly in memory and
   execute exactly `D1` then `N1` with zero auth-side calls;
4. hold the two bounded bodies only in memory under section 8;
5. amend only this RFC by replacing section 10.2 with the complete record;
6. run repository conformance and hosted checks;
7. commit and push that one evidence-only amendment under the approved draft
   pull request; and
8. request two bounded exact-head evidence reviews.

It may not commit a script, raw credential, separate evidence file, response
header dump, log, screenshot, test fixture, parser change, or generated
artifact. The pre-approved `131072`-byte per-body transport bound is also the
maximum publication capacity accepted by both reviewers before execution. If
that fixed capacity is unacceptable, no live card is displayed. A body above
the bound stops during its one call. The evidence may not be split, truncated,
summarized, or redacted to fit.

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
- PR #323, current published review head, and Draft/unmerged posture remain
  recorded accurately;
- the primary acquisition/publication boundary is not mixed with parser,
  credential, provisioning, provider-acceptance, runtime, database, or
  deployment work;
- section 5.6's unauthenticated discovery body digest, method/path, response
  tuple, deny-state, hierarchy, omission, and error-shape facts are
  independently reproducible from the public schema;
- section 7.2's exact source block extracts to 483 UTF-8 LF lines with the
  recorded SHA-256, compiles under CPython 3.12.13, passes repository-pinned
  Ruff check/format, and passes the focused fake-transport matrix under
  `-I -S -B` as stated in section 7.2;
- static source review confirms one direct HTTPS constructor, one request
  statement, fixed D1/N1 invocation, no auth/session/environment/proxy/retry/
  redirect/application-level credential-or-evidence-file/subprocess/log path,
  and no secret in a result or failure;
- the call budget, request/response binding, determinate visibility checks,
  byte boundary, publication encoding, inventory, refusal matrix, and consumer
  non-authority are internally consistent;
- `python3 conformance/ofarm_pkg_contract_check.py` passes;
- hosted checks pass on one exact RFC head;
- two independent bounded reviewers inspect that same head; and
- all demonstrated in-scope Blockers are corrected before a live card.

### 12.2 Phase B verification

- reproduce `OPEC-001` through `OPEC-010` before any call;
- extract section 7.2 and prove its exact line count and SHA-256; prove exact
  CPython 3.12.13 `-I -S -B`; inspect the invocation wrapper, in-memory source
  execution, and process configuration before bearer supply;
- match every preflight value to the approved card without discovery;
- prove the bearer value was already materialized by separate authority and
  that the exact capture code cannot discover, refresh, replay, proxy, retry,
  redirect, log, or persist it;
- prove the process and wrapper add zero auth-side or other hidden network
  calls and that any 401 stops without replay;
- prove request bodies match their recorded base64, lengths, and hashes;
- freeze response bytes before parsing and enforce the exact size/encoding
  boundary;
- decode each published response base64 independently and reproduce its length
  and SHA-256;
- parse with duplicate-member and non-JSON-constant refusal;
- bind every response's request-controlled access-tuple field exactly to its
  request and separately validate/record permission FQDN, effective-tags
  presence, and the complete effective-tags array in response order;
- reject the distinct error-response shape even at status 200;
- prove D1 and N1 have their exact determinate outer states,
  `permissionDeniable: true`, permitted relevance, and complete required
  visibility before interpreting resource cardinality;
- enumerate all resources and all policies, preserving array indices in the
  evidence inventory;
- independently recompute every project attachment and exact equality;
- prove `N1` has an explicitly present empty array;
- reproduce the two-entry D1/N1 call ledger and zero auth-side-call assertion;
- if N1 omits the array, prove the run stopped and retained only the permitted
  fixed failure metadata without treating omission as empty;
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
`OPEC-001` through `OPEC-010` invariant cannot hold, that the two-call capture
is internally contradictory, that complete same-byte review is impossible, or
that this decision crosses its primary trust boundary.

Provisioning, credential custody, wider provider currentness, parser design,
runtime integration, deployment, folder/organization capture, and issue
closure remain separate decisions unless the finding proves this capture
cannot stay bounded without one of them.

## 13. Proposed approval boundary

This published Draft RFC, PR #323, checks, reviews, branch, commit, credential
availability, PR #322 approval, or generic `go` grants no Phase B authority.

Only after one exact Phase A RFC head passes hosted checks and receives two
independent reviews reporting zero demonstrated in-scope Blockers may one
complete live decision card be displayed in this same Codex task. The card
must include:

- decision ID and version;
- parent issue and dependent PR #322;
- exact RFC, draft-PR, reviewed-base, and review-head references;
- the one primary trust boundary;
- the complete publication-safe fixture manifest from section 5.5;
- section 5.6's completed public-schema evidence and its exact limitation;
- section 7.2's exact program ID, 483-line source boundary, source SHA-256,
  CPython 3.12.13 `-I -S -B`, test evidence, inert wrapper, and
  pre-materialized-bearer interface;
- all ten invariants;
- the exact two-call budget and ordering;
- zero auth-side calls, no refresh/replay/proxy behavior, the required
  two-entry call ledger, and terminal 401 behavior;
- exact response/request tuple binding and determinate deny-visibility rules;
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

That approval would authorize only execution of section 7.2's exact source with
one already materialized in-memory bearer value, its two read-only provider
calls, bounded in-memory evidence custody, one-RFC evidence amendment, commits,
pushes, bounded review handling, and merge described here. It would not
authorize bearer materialization, token lookup, refresh, replay, generic auth
session, proxy, wrapper network I/O, fixture provisioning, provider mutation,
credential creation or custody change, production access,
folder/organization capture, provider production acceptance, PR #322
publication or implementation, runtime integration, deployment, release,
issue closure, or a security waiver.

## 14. Stop rule and dependency handoff

Stop before any provider call if:

- the exact live card, two zero-Blocker reviews, or exact later approval is
  absent or not retrievable in order;
- the exact section 7.2 source or wrapper does not match its reviewed identity;
- exact CPython 3.12.13 `-I -S -B` and in-memory-only source execution are not
  established before bearer supply;
- either controlled ancestor-clean fixture, its publication-safe declaration,
  its complete-visibility prerequisite, or its separately authorized
  pre-materialized in-memory bearer value is absent;
- the bearer would need discovery, metadata, exchange, impersonation, file,
  environment, refresh, replay, or any auth-side network call;
- the process or wrapper can use a proxy, retry, redirect, alternate header,
  filesystem, subprocess, logger, or environment-derived network setting;
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
- either returned access tuple is not exactly request-bound, any accepted deny
  field is indeterminate, any required policy visibility is absent, the call
  ledger is not exactly D1/N1, or auth-side calls are not exactly zero;
- the diff contains any path other than this RFC;
- a provider, credential, parser, runtime, database, or deployment mutation
  appears; or
- either exact-head reviewer reports a demonstrated in-scope Blocker.

Only after the successful evidence amendment, hosted checks, both exact-head
evidence reviews, and merge may the immutable complete-byte record and its
explicit project-only limitation be handed to the separately governed
attachment-binding decision. That handoff is evidence, not authority. PR #322
must remain stopped until its own evidence-bearing contract, hosted checks,
reviews, decision card, and exact approval complete.

## 15. Current disposition

- **Reviewed base:** `bdf636d155e45ecbf4d9ac828e232bbcf91e1d59`.
- **Draft pull request:** [#323](https://github.com/samovers/OFARM2/pull/323),
  open, Draft, and unmerged.
- **Published review head before this amendment:**
  `51244a804d05448e2d34c2c5a8debc49b7ddb2db`.
- **Published review 1:** [comment 5353652259](https://github.com/samovers/OFARM2/pull/323#issuecomment-5353652259)
  reported zero Blockers, three should-fixes, two Preferences, and the stale
  provenance follow-up. Section 5.6, the omission limitation, ancestor-clean
  D1 preflight, stopped-run N1 omission metadata, fixed publication bound, and
  PR provenance address them.
- **Published review 2:** [review 4980860540](https://github.com/samovers/OFARM2/pull/323#pullrequestreview-4980860540)
  reported three Blockers: hidden auth refresh/retry and unbound execution,
  missing response/request tuple equality, and incomplete N1 visibility. The
  exact source/auth boundary and ledger, OPEC-009 tuple binding, and determinate
  OPEC-005/OPEC-006 semantics address them.
- **Provider calls made under this decision:** zero.
- **Google/provider credentials used under this decision:** none.
- **Unauthenticated public schema GET attempts:** two, section 5.6; one
  malformed-path HTTP 404 and one successful schema read; no
  `iam:troubleshoot` call.
- **Responses captured:** none.
- **Attachment kinds observed:** none.
- **Remote publication:** PR #323 at the published review head above; this
  amendment is local and uncommitted.
- **Phase A reviews:** two on the published review head; the stricter
  three-Blocker disposition controls until a corrected exact head is reviewed.
- **Decision approval:** absent.
- **Phase B authority:** absent.
- **PR #322 authority changed:** none.
- **Primary trust-boundary scope:** retained as read-only controlled evidence
  acquisition and publication only.
