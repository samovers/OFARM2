# OFARM Security-Audit Observer-Root Provider-Evidence Capture — Phase A Contract v0.1

**Status:** Phase A Draft; decision version 3 unapproved; no Phase B evidence
call, evidence publication, or Phase B authority

**Contract identity:**
ofarm2.security-audit-observer-root-provider-evidence-capture.v0.1

**Decision identity:**
ISSUE192-SECURITY-AUDIT-OBSERVER-ROOT-PROVIDER-EVIDENCE-CAPTURE-001,
proposed version 3; versions 1 and 2 are superseded after their external
fixture qualifications returned terminal HTTP 403 responses

**Issue relationship:** issue #192 remains open; this is a separate
provider-evidence prerequisite for the observer-root attachment-binding
decision

**Dependent draft pull request:**
[PR #322](https://github.com/samovers/OFARM2/pull/322)

**Draft pull request for this decision:**
[PR #323](https://github.com/samovers/OFARM2/pull/323)

**Reviewed base:** bdf636d155e45ecbf4d9ac828e232bbcf91e1d59

**Predecessor reviewed Phase A head:**
21cfcb770038aff0846cca2710dd4b7c2be9f2a9

**Primary trust boundary:** authenticated, read-only acquisition and
publication of controlled Google Policy Troubleshooter evidence

**Intended pull-request boundary:** this RFC only

**Phase B:** not authorized

## 1. Problem and exact goal

The observer-root attachment-binding draft needs live same-response evidence
that an IAM v2 deny-policy name and the containing
ExplainedDenyResource.fullResourceName identify the same project attachment.
Official type descriptions support that relationship, while published examples
have used contradictory spellings. Documentation and typed fixtures therefore
cannot close the provider-evidence gate in PR #322.

This decision defines one bounded acquisition:

1. send one request, D1, for a pre-existing controlled project-attached deny
   policy;
2. send one request, N1, for a pre-existing controlled project whose
   determinate deny result is NOT_DENIED and whose explainedResources member is
   explicitly present as an empty array;
3. use one exact self-contained program in a fresh isolated process;
4. accept one separately authorized, pre-materialized bearer only through a
   hidden controlling-terminal read after every public preflight input has
   been removed;
5. freeze and hash each complete response body before parsing;
6. require the strict parsed response object to equal the complete
   pre-approved response object in a canonical public manifest;
7. bind each returned access tuple to its exact request, inventory every
   relevant resource/policy pair, and publish the unchanged body bytes;
8. send the exact public quota-project header on both requests, bind one exact
   dedicated ancestor-clean fixture organization, and reject any expected
   response containing a human, group, domain, public principal, folder, other
   organization, or unapproved organization-scope spelling in any key or value;
9. render only this RFC, then leave hosted checks and both exact-head reviews
   as external GitHub records.

Version 3 can establish project evidence only. Its exact fixture-organization
visibility is a safety precondition, not organization-behavior evidence. A
successful capture transfers evidence, not implementation or deployment
authority, to PR #322.

## 2. Learning value

This slice tests the disputed relation at the provider boundary without
combining parser implementation, credential custody, fixture provisioning, or
provider acceptance. A successful record preserves the exact response bytes
and the derivation reviewers need. A mismatch or visibility omission records
only an approved confirmation code and safe metadata; it never publishes an
unexpected attachment spelling.

The result remains a point observation of two controlled v3beta responses. It
does not establish production support currentness, universal provider
behavior, least privilege, or future serialization stability.

## 3. Primary boundary and intended pull-request boundary

The one primary trust boundary is authenticated, read-only acquisition and
publication of controlled Policy Troubleshooter evidence.

PR #323 changes only this RFC. The embedded program is review material inside
the RFC, not a durable repository tool. Source extraction and the canonical
public manifest may exist only as temporary, non-secret launch inputs outside
the repository. The exact program removes both before it accepts the bearer.

PR #322 remains a separate consumer. Copying accepted evidence into that RFC,
narrowing its grammar, publishing its amendment, or authorizing its
implementation requires PR #322's own reviews, decision card, and approval.

Any requested parser, credential, IAM, fixture, runtime, deployment, database,
or provider-support change crosses this decision's primary trust boundary and
must be split into a prerequisite or follow-up decision.

## 4. Non-goals

This decision does not authorize:

- any project, folder, organization, service-account, KMS, role, IAM binding,
  deny-policy, PAB, allow-policy, or fixture creation, update, deletion, or
  discovery;
- any provider write, gcloud mutation, Terraform, Pulumi, Config Connector,
  deployment, release, or production operation;
- bearer creation, selection, lookup, refresh, exchange, impersonation,
  export, storage, rotation, revocation, or credential-custody change;
- ADC, metadata, STS, token commands, environment credentials, credential
  files, generic authenticated sessions, or proxy discovery;
- production resources, principals, policy contents, customer data, tenant
  data, personal data, or secret-bearing response publication;
- retries, redirects, replay, polling, list/search calls, hierarchy lookup,
  project-number lookup, testIamPermissions, stable-v3 fallback, or another
  endpoint;
- folder or organization evidence;
- allow, PAB, rule-membership, or overall-access semantic validation beyond
  complete response equality and the deny evidence defined here;
- observer-root parser or fixture code, semantic references, architecture
  gates, runtime integration, readiness, database, export, delivery, issue
  closure, or PR #322 publication; or
- a provider production-acceptance or support-currentness conclusion.

If either controlled fixture, the complete safe manifest, the pinned runtime,
or a separately authorized bearer is unavailable, the run stops. This
decision does not repair those prerequisites.

## 5. Trust model and preconditions

### 5.1 Protected assets

- the complete exact response entity bytes for D1 and N1;
- the binding between each body, request, endpoint, timestamps, length,
  digest, and derived deny inventory;
- the exact host, executable, separately linked Python runtime when present,
  source, manifest, RFC, fresh-process, renderer, and two-call identities;
- the complete publication allowlist, fixture-only public identity boundary,
  and the fact that no unapproved response value reaches Git or GitHub;
- the bearer and all credential/materialization details;
- the no-mutation boundary; and
- the absence of authority transfer to PR #322.

### 5.2 Trusted components and actors

Subject to later exact approval, this decision trusts only:

- the task user to approve one complete live card and declare every manifest
  value suitable for public repository publication;
- the separate credential authority to materialize one bearer before launch;
- the exact 1626-line source in section 7.2 at SHA-256
  0c8ebd287bee43c33e0b5aeda4563b45f7f6124ee8c7e3edc592629233350a68;
- the exact Darwin host system, kernel release, and machine, CPython 3.12.13
  executable path and digest, runtime build classification, and separately
  linked Python runtime-library path and digest when one exists, all fixed in
  the live manifest and invoked with -I -S -B;
- the operating system, terminal driver, host trust store, TLS stack,
  standard-library modules loaded by that isolated interpreter, SHA-256, and
  RFC 4648 base64 implementation; and
- two independent reviewers to inspect the immutable evidence commit through
  external GitHub review objects.

GitHub reviews, checks, commits, and this RFC are evidence and controls, not
task-user approval authority. Capture timestamps are provenance only and make
no trusted-time claim.

### 5.3 Untrusted inputs and behavior

- every manifest byte until exact hash, canonical encoding, schema, identity,
  request shape, expected response, and repository identity checks pass;
- every provider status, header, byte, JSON member, omission, ordering choice,
  enum, array, object, access tuple, resource, and policy;
- every response body that differs from its complete expected public object;
- compressed, redirected, empty, oversized, non-UTF-8, duplicate-member,
  non-JSON, error-shaped, indeterminate, or visibility-incomplete responses;
- every shell, environment, proxy, logger, debug trace, file, console, chat,
  temporary path, and error message as a possible disclosure path; and
- HTTP success as proof of credential identity, least privilege, parser
  correctness, production readiness, or provider currentness.

### 5.4 Explicitly excluded attacker capabilities

The decision does not defend against compromise of the operating system,
kernel, pinned interpreter or standard library on disk, Google, TLS, the host
trust store, SHA-256, Git, GitHub, the separately controlled bearer source, or
both independent reviewers. It does defend against ordinary malformed or
unexpected provider results, local launch drift, module injection through
normal Python startup paths, accidental HTTP debug output, response
substitution, unsafe publication, and repository scope expansion.

### 5.5 Complete public publication manifest

Before any provider call, one canonical compact UTF-8 JSON manifest must be
approved and published in the complete live card. It has exactly these
members, with no others:

- contractId, decisionId, decisionVersion exactly 3, launchProtocolId, and
  manifestSchema at their exact constants from section 7.2;
- maxPublishableBodyBytes exactly 131072; the same fixed value also bounds
  each canonical request body;
- programSourceSha256;
- hostSystem, hostRelease, and hostMachine equal to the live Darwin host
  identity;
- pythonExecutablePath and pythonExecutableSha256;
- pythonRuntimeBuildKind, pythonRuntimeLibraryPath, and
  pythonRuntimeLibrarySha256;
- workingDirectory;
- rfcPath and rfcPreCaptureSha256;
- quotaProjectId, the controlled public project ID sent in the exact
  x-goog-user-project header;
- fixtureOrganizationId, the positive-decimal public ID of the dedicated
  ancestor-clean non-production organization containing both fixture projects;
- publicServiceAccountEmails, a nonempty sorted unique list of the only
  controlled service-account email values that may occur anywhere in either
  complete response;
- d1Request, d1ExpectedPairs, and d1ExpectedResponse; and
- n1Request and n1ExpectedResponse.

pythonRuntimeBuildKind is exactly MONOLITHIC_EXECUTABLE, FRAMEWORK, or
SHARED_LIBRARY. A monolithic build has null runtime-library path and digest,
and the operator must independently establish through native binary-linkage
inspection that no separate Python runtime library is loaded. A framework or
shared-library build supplies the absolute real runtime-library path and its
complete SHA-256. The exact program no-follow reads and hashes the executable
and, when separate, that library. Their observed owner, group, mode, byte
length, and link count enter the record; a root owner or multiple hard links
does not itself invalidate an otherwise exact path-and-byte identity.

The file bytes are canonical JSON produced with ASCII escaping, sorted object
keys, separators comma and colon, no insignificant whitespace, and no terminal
newline. Its SHA-256 is a literal launch argument.

Each request has exactly one accessTuple. The access tuple has exactly
principal, fullResourceName, permission, and conditionContext. The condition
context has exactly one resource object with exactly nonempty name, service,
and type members. Caller-provided effectiveTags and all other context members
are forbidden.

d1ExpectedPairs is the nonempty ordered list of exact
fullResourceName/Policy.name pairs expected from the ancestor-clean controlled
fixture. d1ExpectedResponse and n1ExpectedResponse are the complete strict
parsed response objects, including all five success-response members and all
values that could otherwise be published. They are not schemas, excerpts, or
wildcards. The exact program validates their deny semantics before bearer
input. After each live response is parsed, its canonical JSON must equal the
canonical JSON of the corresponding complete expected object.

The D1 expected response must have a determinate DENIED outer state, deniable
permission, permitted relevance, at least one resource, complete visibility
fields, nonempty visible policy bodies, project-only policy names, exact
derived attachment equality, and the exact expected ordered pair list. The N1
expected response must have a determinate NOT_DENIED outer state, deniable
permission, permitted relevance, and an explicitly present empty
explainedResources array.

Both expected responses must also have the same closed no-applicable-PAB
semantic shape: principalAccessBoundaryAccessState exactly
PAB_ACCESS_STATE_NOT_ENFORCED, explainedBindingsAndPolicies omitted or exactly
the empty list, and permitted relevance. Any visible PAB binding, policy,
target, condition, rule, unknown state, or enforced state refuses.

Before bearer input, the exact source walks every object key and value in both
complete expected responses and applies closed validation to semantic
principal fields. accessTuple.principal and every members, memberships,
exemptedMembers, deniedPrincipals, and exceptionPrincipals entry must be
exactly one of the service-account email values, serviceAccount members, or
explicit service-account principal URIs derived from
publicServiceAccountEmails. A principalSet field is always forbidden. Every
other reserved IAM identity marker refuses even when embedded in an arbitrary
string key or value. The closed marker set is `//iam.googleapis.com/`,
`allAuthenticatedUsers`, `allUsers`, `deleted:`, `domain:`, `group:`,
`principal://`, `principalSet://`, `serviceAccount:`, and `user:`.
Bare IAM pool targets, principal.type or principal.subject conditions, folder,
human email, opaque semantic principal, and unapproved service accounts also
refuse. This covers Google's current
[principal identifier vocabulary](https://docs.cloud.google.com/iam/docs/principal-identifiers)
without treating resource strings as identities. Every folder spelling
refuses. Before scope matching, every percent sign must begin one complete
hexadecimal triplet. A single comparison pass uppercases percent-triplet hex
digits and decodes only percent-encoded URI-unreserved characters; malformed
triplets refuse and the comparison is never recursively decoded. Both the
original string and that comparison view are checked for folder and
organization scope. The only admitted organization-scope string values are
the exact
`//cloudresourcemanager.googleapis.com/organizations/<fixtureOrganizationId>`
and `organizations/<fixtureOrganizationId>` values; either spelling as an
object key, any embedded or different organization spelling, and every
organization-attached deny-policy name refuse. Each expected
allowPolicyExplanation must have determinate aggregate allow state and
permitted relevance. Every explained allow policy must expose a nonempty
resource name, determinate state and relevance, a nonempty visible policy
object, a binding-explanations list, and exact binding/explanation
cardinality. The exact full organization resource must occur exactly once and
have nonempty bindings. The two request principals must also be members of the
public-service-account list. Canonical equality then prevents the live
response from adding any identity or ancestor-scope value that was not
validated before bearer input.

The complete live card must also declare that all projects, resources,
principals, policy IDs, members, conditions, policy bodies, and response
objects are controlled non-production data approved for public GitHub
publication; that fixtureOrganizationId names one dedicated non-production
organization; that both fixture projects are its direct children with no
folder ancestor; and that the reader has complete visibility of every relevant
allow and deny policy. The organization and both project IAM allow policies
must contain only service accounts admitted by publicServiceAccountEmails,
with no human, group, domain, deleted, public, principal-set, or unrelated
member. The reader must have Security Reviewer and Deny Reviewer on exactly
that fixture organization and Service Usage Consumer on quotaProjectId. Every
permitted service account must be controlled non-production data. This RFC
does not discover, provision, or mutate those facts.

The manifest contains no token, authorization header, credential path,
credential subject, private key, client secret, cookie, or materialization
mechanism.

### 5.6 Failed qualification history and version-3 ancestor precondition

On 2026-08-21 the task user separately authorized exactly two read-only
fixture-qualification calls outside decision version 1, D1 then N1, solely to
obtain the complete expected objects. They were not evidence calls. D1 used
request SHA-256
9ea63b198d772a7a72e68bb1547e0523c0842420411d6717bf3ef7ccbeff3564;
N1 used request SHA-256
3132ca2078aac06a8a1e756fb741ee24569e494decf1c85679449ab7db5a2e48.
Both returned HTTP 403 with the same 126-byte PERMISSION_DENIED body at SHA-256
40f3d33677ad0f26654065ef873c25baab52a98dd9a074af065d901e3e942baa.
The two-call budget ended without retry. No expected object, manifest, evidence,
or publication was produced, and the temporary local response directory was
removed.

Google's current
[Policy Troubleshooter instructions](https://docs.cloud.google.com/policy-intelligence/docs/troubleshoot-access)
require a quota project on REST requests and Security Reviewer and Deny
Reviewer on the organization that contains the resource. The version-1 source
omitted x-goog-user-project, and its dedicated reader lacked Security Reviewer.
Because both calls used that same source and identity, the terminal response
did not isolate one defect as the sole cause.

Version 2 added the exact quota-project header but intentionally granted
Security Reviewer only on the two fixture projects. On 2026-08-22 two separate
exactly authorized version-2 replacement runs each sent D1 once from RFC head
fc264956f7c55ec0b7a7343183b00db7e8a32d7e. Each used the same 398-byte request
at SHA-256
9ea63b198d772a7a72e68bb1547e0523c0842420411d6717bf3ef7ccbeff3564
and received HTTP 403 with the same 126-byte body at SHA-256
40f3d33677ad0f26654065ef873c25baab52a98dd9a074af065d901e3e942baa.
Each run stopped before N1. The second followed a separate fixture-IAM
prerequisite that verified the enabled API, project Security Reviewer, project
Service Usage Consumer, organization Deny Reviewer, and successful controlled
reader credential issuance. No expected object, evidence, or publication was
produced, and all private response and credential material was removed.

The repeated exact response bytes equal Google's generic
`PERMISSION_DENIED` object. The remaining mismatch is structural: Google's
documented Security Reviewer scope is the containing organization, while
version 2 forbids that scope. Granting it in the existing shared organization
would make unrelated ancestor IAM identities visible and would contradict the
closed publication allowlist. Version 2 is therefore superseded rather than
weakened with a shared-organization exception.

Version 3 requires one separately provisioned dedicated ancestor-clean
non-production organization. Both fixture projects must be direct children
with no folder ancestor. The organization and both project IAM allow policies
may contain only controlled service accounts admitted by
publicServiceAccountEmails. The reader has Security Reviewer and Deny Reviewer
on exactly that organization and Service Usage Consumer on quotaProjectId.
fixtureOrganizationId binds the exact ancestor into the manifest, response
safety gate, record, and live card. Both expected allowPolicyExplanation
objects must expose exactly that organization resource, while every folder,
other organization, unapproved organization spelling, and unapproved identity
refuses before bearer input.

Any version-3 replacement qualification remains outside Phase B and needs a
new exact task-user authorization for exactly D1 then N1, without retry,
evidence use, or publication. It must use the future dedicated fixtures,
reader, quota project, endpoint, headers, and request bodies intended for the
live manifest. Its private responses may be used only to construct the
complete public expected objects and must then be removed. This RFC and its
publication authorize no such call, fixture provisioning, organization
creation, IAM change, or credential act.

### 5.7 Completed unauthenticated Phase A schema check

One malformed-path unauthenticated GET first returned HTTP 404 after shell
expansion removed the literal discovery path segment. It used no authorization
header, credential, API key, redirect, or iam:troubleshoot request and
produced no accepted evidence.

A second unauthenticated, redirect-disabled GET fetched Google's public
[Policy Troubleshooter v3beta discovery document](https://policytroubleshooter.googleapis.com/$discovery/rest?version=v3beta)
at 2026-08-20T09:02:18Z. It used no authorization header, credential, API key,
or iam:troubleshoot request. The entity body was 120285 bytes of
application/json; charset=UTF-8 with SHA-256
4a4b2bc765fd4deb8fc2417c1b5c3482aeb4d302e6e139d0690b7d35aae4a349.

That schema records the v3beta POST endpoint and cloud-platform scope; the
returned access tuple; output-only permissionFqdn and effectiveTags; determinate
and unknown deny states; permissionDeniable; hierarchy-spanning explained
resources; possible visibility omissions; and a distinct error-response
schema.

This public check closes only static shape questions. It does not establish
live attachment equality, visibility, empty-array emission, or either
controlled response.

## 6. Authority map

| Decision | Sole authority | Forbidden substitute |
| --- | --- | --- |
| Replacement fixture qualification | New exact task-user authorization for one private D1 then N1 pair using the version-3 dedicated-organization reader, quota project, headers, and bodies | This RFC, any failed version-1/version-2 call, generic go, or Phase B approval |
| Begin capture | Exact later task-user approval after one complete live card | This Draft, generic go, review, credential availability, or PR #322 approval |
| Public inputs | Exact complete canonical version-3 manifest, exact source, and literal hashes in the approved card | Discovery, defaults, unsafe qualification output, response-selected values, or caller improvisation |
| Authentication | One bearer already materialized by separate authority, read hidden from /dev/tty after public input removal | ADC, metadata, STS, impersonation, file, environment, refresh, replay, or command |
| Process identity | Exact Darwin host/release/machine, pinned executable and separate runtime-library identities, build kind, fresh minimal env, -I -S -B, source path/digest, and launch vector | Wrapper, inherited process, preloaded module, alternate interpreter, plugin, or adapter |
| Network effects | Exact source; fixed D1 then N1 direct HTTPS requests; exact public x-goog-user-project value; zero auth-side calls | Missing or different quota project, proxy, debug trace, redirect, retry, discovery, replay, or hidden call |
| Publication safety | Closed public-service-account validation plus one exact dedicated fixture-organization scope followed by canonical equality to each complete expected response object | Shared-organization, unrelated-member, human/group/domain, folder/other-ancestor data, human spot check, mutable inspector, redaction, excerpt, or permissive schema |
| Rendering | Exact renderer in the same source, one marker-delimited RFC replacement, immutable JSON bytes, and atomic replace | External formatter, mutable result callback, second file, log, or manual copy |
| Reviews | Two external GitHub review objects bound to the immutable evidence commit | Review IDs embedded into that commit, self-attestation, or a later attestation commit |
| Consumer authority | PR #322's separately governed decision and approval | This capture or its reviews |

## 7. Fixed call set and exact artifact

### 7.1 Call budget and ordering

Prospective Phase B permits exactly two provider calls, sequentially:

1. D1, the controlled deny-bearing request; then
2. N1, the controlled no-deny request.

There is no provider preflight, retry, redirect, replay, polling, discovery,
list, hierarchy, folder, organization, cleanup, or parallel call. A transport
failure, timeout, non-200 response, malformed response, or refusal consumes
the attempted call and stops. A later attempt requires a new explicit user
authorization identifying the stopped run.

The failed version-1 qualification calls in section 5.6 were external
prerequisite calls, not Phase B calls, and supplied no evidence. A future
replacement qualification is likewise a separately authorized prerequisite;
it cannot satisfy, consume, or expand this Phase B evidence budget.

### 7.2 Exact self-contained fresh-process program

Phase B may execute only the source below. The source-byte boundary is the
UTF-8 LF sequence beginning with the first f in from __future__ and ending
with the LF after the last source line. The Markdown fences are excluded.

It is exactly 1626 lines with SHA-256:

~~~text
0c8ebd287bee43c33e0b5aeda4563b45f7f6124ee8c7e3edc592629233350a68
~~~

~~~python
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import re
import ssl
import stat
import sys
import termios
from datetime import datetime, timezone
from typing import NoReturn

PROGRAM_ID = "ofarm2.issue192.provider-evidence-capture.v3"
RECORD_SCHEMA = "ofarm2.issue192.provider-evidence-record.v3"
RENDERER_ID = "ofarm2.issue192.provider-evidence-rfc-renderer.v3"
MANIFEST_SCHEMA = "ofarm2.issue192.provider-evidence-publication-manifest.v3"
LAUNCH_PROTOCOL_ID = "ofarm2.issue192.provider-evidence-fresh-process.v3"
CONTRACT_ID = "ofarm2.security-audit-observer-root-provider-evidence-capture.v0.1"
DECISION_ID = "ISSUE192-SECURITY-AUDIT-OBSERVER-ROOT-PROVIDER-EVIDENCE-CAPTURE-001"
DECISION_VERSION = 3
RFC_RELATIVE_PATH = (
    "docs/rfcs/OFARM_Security_Audit_Observer_Root_Provider_Evidence_Capture_RFC_v0_1.md"
)
HOST = "policytroubleshooter.googleapis.com"
PATH = "/v3beta/iam:troubleshoot"
ENDPOINT = "https://policytroubleshooter.googleapis.com/v3beta/iam:troubleshoot"
TIMEOUT_SECONDS = 5.0
MAX_BODY_BYTES = 131072
MAX_PUBLIC_INPUT_BYTES = 1048576
MAX_RFC_BYTES = 1048576
MAX_EXECUTABLE_BYTES = 67108864
RECORDABLE_FAILURE_CODES = {
    "D1_ATTACHMENT_MISMATCH",
    "D1_EXPLAINED_RESOURCES_OMITTED",
    "D1_RESOURCE_VISIBILITY_OMITTED",
    "N1_EXPLAINED_RESOURCES_OMITTED",
}
RELEVANCE = {"HEURISTIC_RELEVANCE_NORMAL", "HEURISTIC_RELEVANCE_HIGH"}
DETERMINATE_ALLOW_ACCESS_STATES = {
    "ALLOW_ACCESS_STATE_GRANTED",
    "ALLOW_ACCESS_STATE_NOT_GRANTED",
}
TOKEN = re.compile(r"[A-Za-z0-9._~+/=-]{1,8192}")
SHA256 = re.compile(r"[0-9a-f]{64}")
MODE = re.compile(r"[0-7]{4}")
CF_USER_TEXT_ENCODING = re.compile(r"0x[0-9A-F]+:0x0:0x0")
PROJECT_ID = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]")
ORGANIZATION_ID = re.compile(r"[1-9][0-9]*")
SERVICE_ACCOUNT_EMAIL = re.compile(
    r"[a-z][a-z0-9-]{0,62}@[a-z][a-z0-9-]{4,28}[a-z0-9]"
    r"\.iam\.gserviceaccount\.com"
)
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
FORBIDDEN_PUBLIC_IDENTITY_FRAGMENTS = (
    "//iam.googleapis.com/",
    "allAuthenticatedUsers",
    "allUsers",
    "deleted:",
    "domain:",
    "group:",
    "principal://",
    "principalSet://",
    "serviceAccount:",
    "user:",
)
FORBIDDEN_PUBLIC_PRINCIPAL_CONDITION_FRAGMENTS = (
    "principal.subject",
    "principal.type",
)
FORBIDDEN_PUBLIC_FOLDER_SCOPE_FRAGMENTS = (
    "//cloudresourcemanager.googleapis.com/folders/",
    "policies/cloudresourcemanager.googleapis.com%2Ffolders%2F",
    "folders/",
    "folders%2F",
)
CONTROLLED_PUBLIC_ORGANIZATION_SCOPE_FRAGMENTS = (
    "//cloudresourcemanager.googleapis.com/organizations/",
    "policies/cloudresourcemanager.googleapis.com%2Forganizations%2F",
    "organizations/",
    "organizations%2F",
)
URI_HEX_DIGITS = "0123456789ABCDEFabcdef"
URI_UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
PUBLIC_PRINCIPAL_FIELDS = {
    "deniedPrincipals",
    "exceptionPrincipals",
    "exemptedMembers",
    "members",
    "memberships",
    "principal",
}
MANIFEST_MEMBERS = (
    "contractId",
    "d1ExpectedPairs",
    "d1ExpectedResponse",
    "d1Request",
    "decisionId",
    "decisionVersion",
    "fixtureOrganizationId",
    "hostMachine",
    "hostRelease",
    "hostSystem",
    "launchProtocolId",
    "manifestSchema",
    "maxPublishableBodyBytes",
    "n1ExpectedResponse",
    "n1Request",
    "programSourceSha256",
    "publicServiceAccountEmails",
    "pythonExecutablePath",
    "pythonExecutableSha256",
    "pythonRuntimeBuildKind",
    "pythonRuntimeLibraryPath",
    "pythonRuntimeLibrarySha256",
    "quotaProjectId",
    "rfcPath",
    "rfcPreCaptureSha256",
    "workingDirectory",
)


class CaptureStop(Exception):
    def __init__(self, code: str, metadata: dict[str, object] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.metadata = {} if metadata is None else metadata


def _stop(code: str) -> NoReturn:
    raise CaptureStop(code) from None


def _runtime() -> dict[str, object]:
    environment = dict(os.environ)
    environment_keys = sorted(environment)
    cf_value = environment.get("__CF_USER_TEXT_ENCODING")
    flags = {
        "dontWriteBytecode": sys.flags.dont_write_bytecode,
        "ignoreEnvironment": sys.flags.ignore_environment,
        "isolated": sys.flags.isolated,
        "noSite": sys.flags.no_site,
        "safePath": sys.flags.safe_path,
    }
    uname = os.uname()
    if (
        sys.implementation.name != "cpython"
        or sys.version_info[:3] != (3, 12, 13)
        or sys.platform != "darwin"
        or flags
        != {
            "dontWriteBytecode": 1,
            "ignoreEnvironment": 1,
            "isolated": 1,
            "noSite": 1,
            "safePath": True,
        }
        or set(environment)
        not in (
            {"LC_ALL"},
            {"LC_ALL", "__CF_USER_TEXT_ENCODING"},
        )
        or environment.get("LC_ALL") != "C"
        or (cf_value is not None and CF_USER_TEXT_ENCODING.fullmatch(cf_value) is None)
        or http.client.HTTPConnection.debuglevel != 0
    ):
        _stop("WRONG_PYTHON_RUNTIME")
    return {
        "environmentEntryCount": len(environment),
        "environmentKeys": environment_keys,
        "httpDebugLevel": http.client.HTTPConnection.debuglevel,
        "implementation": sys.implementation.name,
        "osName": os.name,
        "platformMachine": uname.machine,
        "platformRelease": uname.release,
        "platformSystem": uname.sysname,
        "pythonExecutablePath": os.path.realpath(sys.executable),
        "pythonFlags": flags,
        "pythonVersion": ".".join(str(value) for value in sys.version_info[:3]),
        "pythonVersionText": sys.version,
        "sysPlatform": sys.platform,
        "userTextEncodingPresent": cf_value is not None,
        "userTextEncodingValue": cf_value,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _base64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _base64_lines(value: bytes) -> list[str]:
    encoded = _base64(value)
    return [encoded[index : index + 76] for index in range(0, len(encoded), 76)]


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


def _digest_text(value: object, code: str) -> str:
    text = _text(value, code)
    if SHA256.fullmatch(text) is None:
        _stop(code)
    return text


def _public_service_accounts(value: object) -> list[str]:
    if type(value) is not list or not value:
        _stop("INVALID_PUBLIC_SERVICE_ACCOUNTS")
    accounts: list[str] = []
    for item in value:
        account = _text(item, "INVALID_PUBLIC_SERVICE_ACCOUNTS")
        if SERVICE_ACCOUNT_EMAIL.fullmatch(account) is None:
            _stop("INVALID_PUBLIC_SERVICE_ACCOUNTS")
        accounts.append(account)
    if accounts != sorted(set(accounts)):
        _stop("INVALID_PUBLIC_SERVICE_ACCOUNTS")
    return accounts


def _validate_public_identity(
    item: str,
    permitted_identities: set[str],
    *,
    required: bool = False,
) -> None:
    if item in permitted_identities:
        return
    if any(fragment in item for fragment in FORBIDDEN_PUBLIC_IDENTITY_FRAGMENTS) or any(
        fragment in item for fragment in FORBIDDEN_PUBLIC_PRINCIPAL_CONDITION_FRAGMENTS
    ):
        _stop("UNSAFE_PUBLIC_RESPONSE_IDENTITY_OR_SCOPE")
    if ".iam.gserviceaccount.com" in item or "/serviceAccounts/" in item:
        _stop("UNAPPROVED_PUBLIC_SERVICE_ACCOUNT")
    if "@" in item or required:
        _stop("UNSAFE_PUBLIC_RESPONSE_IDENTITY_OR_SCOPE")


def _validate_principal_field(
    name: str,
    value: object,
    permitted_identities: set[str],
) -> None:
    if name == "principal":
        identities = [value]
    elif name in {"exemptedMembers", "members"}:
        if type(value) is not list:
            _stop("UNSAFE_PUBLIC_RESPONSE_IDENTITY_OR_SCOPE")
        identities = value
    elif name == "memberships":
        if type(value) is not dict:
            _stop("UNSAFE_PUBLIC_RESPONSE_IDENTITY_OR_SCOPE")
        identities = list(value)
    elif type(value) is list:
        identities = value
    elif type(value) is dict:
        identities = list(value)
    else:
        _stop("UNSAFE_PUBLIC_RESPONSE_IDENTITY_OR_SCOPE")
    for identity in identities:
        if type(identity) is not str or not identity:
            _stop("UNSAFE_PUBLIC_RESPONSE_IDENTITY_OR_SCOPE")
        _validate_public_identity(identity, permitted_identities, required=True)


def _uri_scope_comparison(value: str) -> str:
    normalized = []
    index = 0
    while index < len(value):
        if value[index] != "%":
            normalized.append(value[index])
            index += 1
            continue
        if (
            index + 2 >= len(value)
            or value[index + 1] not in URI_HEX_DIGITS
            or value[index + 2] not in URI_HEX_DIGITS
        ):
            _stop("UNSAFE_PUBLIC_RESPONSE_IDENTITY_OR_SCOPE")
        encoded = value[index + 1 : index + 3].upper()
        decoded = chr(int(encoded, 16))
        normalized.append(decoded if decoded in URI_UNRESERVED else "%" + encoded)
        index += 3
    return "".join(normalized)


def _validate_public_response(
    value: object,
    service_accounts: list[str],
    fixture_organization_id: str,
) -> None:
    permitted_identities = set(service_accounts)
    permitted_identities.update(
        "serviceAccount:" + account for account in service_accounts
    )
    permitted_identities.update(
        "principal://iam.googleapis.com/projects/-/serviceAccounts/" + account
        for account in service_accounts
    )
    permitted_organization_scopes = {
        "//cloudresourcemanager.googleapis.com/organizations/"
        + fixture_organization_id,
        "organizations/" + fixture_organization_id,
    }
    pending = [(value, False)]
    while pending:
        item, is_key = pending.pop()
        if type(item) is dict:
            for key, nested in item.items():
                if key == "principalSet":
                    _stop("UNSAFE_PUBLIC_RESPONSE_IDENTITY_OR_SCOPE")
                if key in PUBLIC_PRINCIPAL_FIELDS:
                    _validate_principal_field(key, nested, permitted_identities)
                pending.extend(((key, True), (nested, False)))
        elif type(item) is list:
            pending.extend((nested, False) for nested in item)
        elif type(item) is str:
            comparison = _uri_scope_comparison(item)
            if any(
                fragment in candidate
                for candidate in (item, comparison)
                for fragment in FORBIDDEN_PUBLIC_FOLDER_SCOPE_FRAGMENTS
            ):
                _stop("UNSAFE_PUBLIC_RESPONSE_IDENTITY_OR_SCOPE")
            if any(
                fragment in candidate
                for candidate in (item, comparison)
                for fragment in CONTROLLED_PUBLIC_ORGANIZATION_SCOPE_FRAGMENTS
            ) and (is_key or item not in permitted_organization_scopes):
                _stop("UNSAFE_PUBLIC_RESPONSE_IDENTITY_OR_SCOPE")
            _validate_public_identity(item, permitted_identities)


def _validate_fixture_organization_visibility(
    value: object,
    fixture_organization_id: str,
) -> None:
    expected = (
        "//cloudresourcemanager.googleapis.com/organizations/" + fixture_organization_id
    )
    document = _members(
        value,
        ("allowAccessState", "explainedPolicies", "relevance"),
    )
    policies = document["explainedPolicies"]
    if (
        document["allowAccessState"] not in DETERMINATE_ALLOW_ACCESS_STATES
        or document["relevance"] not in RELEVANCE
        or type(policies) is not list
        or not policies
    ):
        _stop("FIXTURE_ORGANIZATION_VISIBILITY_REQUIRED")
    matches = 0
    for value_item in policies:
        item = _members(
            value_item,
            (
                "allowAccessState",
                "bindingExplanations",
                "fullResourceName",
                "policy",
                "relevance",
            ),
        )
        full_resource_name = _text(
            item["fullResourceName"],
            "FIXTURE_ORGANIZATION_VISIBILITY_REQUIRED",
        )
        policy = item["policy"]
        explanations = item["bindingExplanations"]
        bindings = policy.get("bindings", []) if type(policy) is dict else None
        if (
            item["allowAccessState"] not in DETERMINATE_ALLOW_ACCESS_STATES
            or item["relevance"] not in RELEVANCE
            or type(policy) is not dict
            or not policy
            or type(bindings) is not list
            or type(explanations) is not list
            or len(explanations) != len(bindings)
        ):
            _stop("FIXTURE_ORGANIZATION_VISIBILITY_REQUIRED")
        if full_resource_name == expected:
            matches += 1
            if not bindings:
                _stop("FIXTURE_ORGANIZATION_VISIBILITY_REQUIRED")
    if matches != 1:
        _stop("FIXTURE_ORGANIZATION_VISIBILITY_REQUIRED")


def _validate_pab_explanation(value: object) -> None:
    document = _members(
        value,
        ("principalAccessBoundaryAccessState", "relevance"),
        ("explainedBindingsAndPolicies",),
    )
    if (
        document["principalAccessBoundaryAccessState"]
        != "PAB_ACCESS_STATE_NOT_ENFORCED"
        or document.get("explainedBindingsAndPolicies", []) != []
        or document["relevance"] not in RELEVANCE
    ):
        _stop("UNSAFE_PAB_EXPLANATION")


def _read_regular(
    path_value: str,
    maximum: int,
    code: str,
    *,
    require_owner: bool = True,
    require_single_link: bool = True,
) -> tuple[str, bytes, os.stat_result]:
    path = os.path.abspath(path_value)
    try:
        before = os.lstat(path)
        if (
            not stat.S_ISREG(before.st_mode)
            or (require_single_link and before.st_nlink != 1)
            or (require_owner and before.st_uid != os.getuid())
            or not hasattr(os, "O_NOFOLLOW")
        ):
            _stop(code)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                _stop(code)
            chunks: list[bytes] = []
            length = 0
            while True:
                chunk = os.read(descriptor, min(65536, maximum + 1 - length))
                if not chunk:
                    break
                chunks.append(chunk)
                length += len(chunk)
                if length > maximum:
                    _stop(code)
        finally:
            os.close(descriptor)
    except CaptureStop:
        raise
    except Exception:
        _stop(code)
    return path, b"".join(chunks), before


def _unlink_public_input(path: str, before: os.stat_result, code: str) -> None:
    try:
        current = os.lstat(path)
        if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
            _stop(code)
        os.unlink(path)
    except CaptureStop:
        raise
    except Exception:
        _stop(code)


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
    if label == "D1" and type(value) is dict and "explainedResources" not in value:
        _stop("D1_EXPLAINED_RESOURCES_OMITTED")
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
        if type(resource_value) is dict and (
            "fullResourceName" not in resource_value
            or "relevance" not in resource_value
        ):
            _stop("D1_RESOURCE_VISIBILITY_OMITTED")
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


def _validate_response(
    label: str,
    parsed: object,
    request_access: dict[str, object],
    expected_pairs: list[list[str]],
    fixture_organization_id: str,
) -> tuple[dict[str, object], dict[str, object]]:
    response = _members(
        parsed,
        (
            "accessTuple",
            "allowPolicyExplanation",
            "denyPolicyExplanation",
            "overallAccessState",
            "pabPolicyExplanation",
        ),
    )
    outputs = _bind_access_tuple(response["accessTuple"], request_access)
    _validate_fixture_organization_visibility(
        response["allowPolicyExplanation"],
        fixture_organization_id,
    )
    _validate_pab_explanation(response["pabPolicyExplanation"])
    inventory = _deny_inventory(
        label,
        response["denyPolicyExplanation"],
        expected_pairs,
    )
    return outputs, inventory


def _post(
    label: str,
    bearer_token: str,
    quota_project_id: str,
    fixture_organization_id: str,
    request_body: bytes,
    request_access: dict[str, object],
    expected_pairs: list[list[str]],
    expected_response: object,
    ledger: list[dict[str, object]],
) -> dict[str, object]:
    started_at = _utc_now()
    entry: dict[str, object] = {
        "ordinal": len(ledger) + 1,
        "label": label,
        "method": "POST",
        "endpoint": ENDPOINT,
        "quotaProjectId": quota_project_id,
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
        connection.set_debuglevel(0)
        if connection.debuglevel != 0:
            _stop("HTTP_DEBUG_NOT_DISABLED")
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
                "x-goog-user-project": quota_project_id,
            },
        )
        response = connection.getresponse()
        status = response.status
        content_types = response.headers.get_all("Content-Type", [])
        content_encodings = response.headers.get_all("Content-Encoding", [])
        body = response.read(MAX_BODY_BYTES + 1)
    except CaptureStop:
        raise
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
        access_outputs, inventory = _validate_response(
            label,
            parsed,
            request_access,
            expected_pairs,
            fixture_organization_id,
        )
        if _canonical(parsed) != _canonical(expected_response):
            _stop(label + "_UNAPPROVED_RESPONSE")
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
        "requestQuotaProjectId": quota_project_id,
        "requestSha256": _sha256(request_body),
        "responseBodyBase64Lines": _base64_lines(body),
        "responseByteLength": len(body),
        "responseSha256": body_sha256,
        "responseStatus": status,
        "responseContentType": "application/json",
        "responseContentEncoding": "identity" if content_encodings else "absent",
        "accessTupleOutputs": access_outputs,
        "denyInventory": inventory,
        "publicationManifestEquality": "EXACT_CANONICAL_JSON",
    }


def _expected_pairs(value: object) -> list[list[str]]:
    if type(value) is not list or not value:
        _stop("INVALID_EXPECTED_PAIRS")
    for pair in value:
        if type(pair) is not list or len(pair) != 2:
            _stop("INVALID_EXPECTED_PAIRS")
        _text(pair[0], "INVALID_EXPECTED_PAIRS")
        _text(pair[1], "INVALID_EXPECTED_PAIRS")
    return value


def _validate_runtime_manifest(document: dict[str, object]) -> None:
    for name in (
        "hostMachine",
        "hostRelease",
        "hostSystem",
        "pythonExecutablePath",
        "rfcPath",
        "workingDirectory",
    ):
        _text(document[name], "INVALID_MANIFEST_PATH")
    uname = os.uname()
    if (
        document["hostSystem"] != uname.sysname
        or document["hostMachine"] != uname.machine
        or document["hostRelease"] != uname.release
    ):
        _stop("WRONG_HOST_IDENTITY")
    build_kind = document["pythonRuntimeBuildKind"]
    library_path = document["pythonRuntimeLibraryPath"]
    library_sha256 = document["pythonRuntimeLibrarySha256"]
    framework = getattr(sys, "_framework", "")
    if build_kind == "MONOLITHIC_EXECUTABLE":
        if library_path is not None or library_sha256 is not None or framework:
            _stop("WRONG_PYTHON_RUNTIME_LINKAGE")
    elif build_kind in {"FRAMEWORK", "SHARED_LIBRARY"}:
        _text(library_path, "INVALID_PYTHON_RUNTIME_LIBRARY_PATH")
        _digest_text(library_sha256, "INVALID_PYTHON_RUNTIME_LIBRARY_DIGEST")
        if build_kind == "FRAMEWORK" and not framework:
            _stop("WRONG_PYTHON_RUNTIME_LINKAGE")
    else:
        _stop("WRONG_PYTHON_RUNTIME_LINKAGE")


def _validate_expected_responses(
    document: dict[str, object],
    public_service_accounts: list[str],
    fixture_organization_id: str,
    d1_access: dict[str, object],
    n1_access: dict[str, object],
    expected_pairs: list[list[str]],
) -> None:
    d1_response = document["d1ExpectedResponse"]
    n1_response = document["n1ExpectedResponse"]
    for response in (d1_response, n1_response):
        _validate_public_response(
            response,
            public_service_accounts,
            fixture_organization_id,
        )
    _validate_response(
        "D1",
        d1_response,
        d1_access,
        expected_pairs,
        fixture_organization_id,
    )
    _validate_response(
        "N1",
        n1_response,
        n1_access,
        [],
        fixture_organization_id,
    )
    if (
        len(_canonical(d1_response)) > MAX_BODY_BYTES
        or len(_canonical(n1_response)) > MAX_BODY_BYTES
    ):
        _stop("EXPECTED_RESPONSE_OVER_PUBLICATION_BOUND")


def _capture_plan(
    manifest: dict[str, object],
) -> tuple[
    dict[str, object],
    bytes,
    dict[str, object],
    bytes,
    dict[str, object],
    list[list[str]],
]:
    document = _members(manifest, MANIFEST_MEMBERS)
    if (
        document["contractId"] != CONTRACT_ID
        or document["decisionId"] != DECISION_ID
        or document["decisionVersion"] != DECISION_VERSION
        or document["launchProtocolId"] != LAUNCH_PROTOCOL_ID
        or document["manifestSchema"] != MANIFEST_SCHEMA
        or document["maxPublishableBodyBytes"] != MAX_BODY_BYTES
    ):
        _stop("WRONG_PUBLICATION_MANIFEST_IDENTITY")
    for name in (
        "programSourceSha256",
        "pythonExecutableSha256",
        "rfcPreCaptureSha256",
    ):
        _digest_text(document[name], "INVALID_MANIFEST_DIGEST")
    _validate_runtime_manifest(document)
    quota_project_id = _text(document["quotaProjectId"], "INVALID_QUOTA_PROJECT_ID")
    if PROJECT_ID.fullmatch(quota_project_id) is None:
        _stop("INVALID_QUOTA_PROJECT_ID")
    fixture_organization_id = _text(
        document["fixtureOrganizationId"],
        "INVALID_FIXTURE_ORGANIZATION_ID",
    )
    if ORGANIZATION_ID.fullmatch(fixture_organization_id) is None:
        _stop("INVALID_FIXTURE_ORGANIZATION_ID")
    public_service_accounts = _public_service_accounts(
        document["publicServiceAccountEmails"]
    )
    expected_pairs = _expected_pairs(document["d1ExpectedPairs"])
    d1_body, d1_access = _request(document["d1Request"])
    n1_body, n1_access = _request(document["n1Request"])
    if any(
        access["principal"] not in public_service_accounts
        for access in (d1_access, n1_access)
    ):
        _stop("UNAPPROVED_REQUEST_PRINCIPAL")
    if d1_body == n1_body:
        _stop("IDENTICAL_D1_N1_REQUESTS")
    if len(d1_body) > MAX_BODY_BYTES or len(n1_body) > MAX_BODY_BYTES:
        _stop("REQUEST_OVER_BOUND")
    _validate_expected_responses(
        document,
        public_service_accounts,
        fixture_organization_id,
        d1_access,
        n1_access,
        expected_pairs,
    )
    return document, d1_body, d1_access, n1_body, n1_access, expected_pairs


def _pretty_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _file_observation(
    path: str,
    value: bytes,
    info: os.stat_result,
) -> dict[str, object]:
    return {
        "byteLength": len(value),
        "groupId": info.st_gid,
        "linkCount": info.st_nlink,
        "mode": f"{stat.S_IMODE(info.st_mode):04o}",
        "ownerId": info.st_uid,
        "path": path,
        "sha256": _sha256(value),
    }


def _validated_file_observation(value: object) -> dict[str, object]:
    document = _members(
        value,
        ("byteLength", "groupId", "linkCount", "mode", "ownerId", "path", "sha256"),
    )
    _text(document["path"], "INVALID_PROVENANCE_PATH")
    _digest_text(document["sha256"], "INVALID_PROVENANCE_DIGEST")
    mode = _text(document["mode"], "INVALID_PROVENANCE_FILE_IDENTITY")
    if (
        MODE.fullmatch(mode) is None
        or type(document["byteLength"]) is not int
        or document["byteLength"] < 0
        or type(document["groupId"]) is not int
        or document["groupId"] < 0
        or type(document["ownerId"]) is not int
        or document["ownerId"] < 0
        or type(document["linkCount"]) is not int
        or document["linkCount"] < 1
    ):
        _stop("INVALID_PROVENANCE_FILE_IDENTITY")
    return {name: document[name] for name in document}


def _provenance(value: object) -> dict[str, object]:
    names = (
        "manifestSha256",
        "programSourceSha256",
        "pythonExecutableIdentity",
        "pythonRuntimeBuildKind",
        "pythonRuntimeLibraryIdentity",
        "rfcPreCaptureSha256",
        "temporaryInputObservation",
    )
    document = _members(value, names)
    for name in (
        "manifestSha256",
        "programSourceSha256",
        "rfcPreCaptureSha256",
    ):
        _digest_text(document[name], "INVALID_PROVENANCE_DIGEST")
    executable = _validated_file_observation(document["pythonExecutableIdentity"])
    build_kind = document["pythonRuntimeBuildKind"]
    library_value = document["pythonRuntimeLibraryIdentity"]
    if build_kind == "MONOLITHIC_EXECUTABLE":
        if library_value is not None:
            _stop("INVALID_PROVENANCE_RUNTIME_LINKAGE")
        library = None
    elif build_kind in {"FRAMEWORK", "SHARED_LIBRARY"}:
        library = _validated_file_observation(library_value)
    else:
        _stop("INVALID_PROVENANCE_RUNTIME_LINKAGE")
    temporary_value = _members(
        document["temporaryInputObservation"],
        ("directoryAbsent", "manifestAbsent", "sourceAbsent"),
    )
    if any(temporary_value[name] is not True for name in temporary_value):
        _stop("INVALID_PROVENANCE_TEMPORARY_INPUT_OBSERVATION")
    return {
        "manifestSha256": document["manifestSha256"],
        "programSourceSha256": document["programSourceSha256"],
        "pythonExecutableIdentity": executable,
        "pythonRuntimeBuildKind": build_kind,
        "pythonRuntimeLibraryIdentity": library,
        "rfcPreCaptureSha256": document["rfcPreCaptureSha256"],
        "temporaryInputObservation": {
            name: temporary_value[name] for name in temporary_value
        },
    }


def run_capture(
    bearer_token: str,
    manifest: dict[str, object],
    provenance: dict[str, object],
) -> bytes:
    runtime_observation = _runtime()
    provenance_document = _provenance(provenance)
    if type(bearer_token) is not str or TOKEN.fullmatch(bearer_token) is None:
        _stop("INVALID_PREMATERIALIZED_BEARER_TOKEN")
    document, d1_body, d1_access, n1_body, n1_access, expected_pairs = _capture_plan(
        manifest
    )
    auth_side_call_ledger: list[dict[str, object]] = []
    ledger: list[dict[str, object]] = []
    try:
        captures = [
            _post(
                "D1",
                bearer_token,
                document["quotaProjectId"],
                document["fixtureOrganizationId"],
                d1_body,
                d1_access,
                expected_pairs,
                document["d1ExpectedResponse"],
                ledger,
            ),
            _post(
                "N1",
                bearer_token,
                document["quotaProjectId"],
                document["fixtureOrganizationId"],
                n1_body,
                n1_access,
                [],
                document["n1ExpectedResponse"],
                ledger,
            ),
        ]
    except CaptureStop as error:
        error.metadata = {
            **error.metadata,
            "policyTroubleshooterCallLedger": ledger,
        }
        raise
    if [entry["label"] for entry in ledger] != ["D1", "N1"]:
        _stop("WRONG_CALL_LEDGER")
    record = {
        "authSideCallCount": len(auth_side_call_ledger),
        "authSideCallLedger": auth_side_call_ledger,
        "captures": captures,
        "decisionId": DECISION_ID,
        "decisionVersion": DECISION_VERSION,
        "externalReviewControl": {
            "evidenceAuthority": "GIT_COMMIT_CONTAINING_THIS_RECORD",
            "requiredExactHeadReviewCount": 2,
            "reviewObjectsStored": "EXTERNAL_GITHUB_RECORDS",
            "status": "PENDING_EXTERNAL_EXACT_HEAD_REVIEWS",
        },
        "fixtureOrganizationId": document["fixtureOrganizationId"],
        "launchProtocolId": LAUNCH_PROTOCOL_ID,
        "policyTroubleshooterCallLedger": ledger,
        "programId": PROGRAM_ID,
        "publicServiceAccountEmails": document["publicServiceAccountEmails"],
        "publicationSafety": "FULL_EXPECTED_RESPONSES_EXACT_CANONICAL_JSON",
        "quotaProjectId": document["quotaProjectId"],
        "recordSchema": RECORD_SCHEMA,
        "rendererId": RENDERER_ID,
        "runtimeObservation": runtime_observation,
        **provenance_document,
    }
    return _pretty_json(record)


def _private_input_directory(source_path: str, manifest_path: str) -> str:
    source_parent = os.path.dirname(source_path)
    manifest_parent = os.path.dirname(manifest_path)
    if source_parent != manifest_parent:
        _stop("PUBLIC_INPUT_DIRECTORY_MISMATCH")
    try:
        info = os.lstat(source_parent)
    except Exception:
        _stop("INVALID_PUBLIC_INPUT_DIRECTORY")
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        _stop("INVALID_PUBLIC_INPUT_DIRECTORY")
    return source_parent


def _runtime_file_identities(
    document: dict[str, object],
) -> tuple[dict[str, object], dict[str, object] | None]:
    executable_path, executable_bytes, executable_info = _read_regular(
        os.path.realpath(sys.executable),
        MAX_EXECUTABLE_BYTES,
        "INVALID_PYTHON_EXECUTABLE",
        require_owner=False,
        require_single_link=False,
    )
    if os.path.abspath(os.getcwd()) != os.path.abspath(document["workingDirectory"]):
        _stop("WRONG_WORKING_DIRECTORY")
    if executable_path != os.path.abspath(document["pythonExecutablePath"]):
        _stop("WRONG_PYTHON_EXECUTABLE_PATH")
    if _sha256(executable_bytes) != document["pythonExecutableSha256"]:
        _stop("WRONG_PYTHON_EXECUTABLE_DIGEST")
    executable_identity = _file_observation(
        executable_path,
        executable_bytes,
        executable_info,
    )
    library_identity: dict[str, object] | None = None
    if document["pythonRuntimeLibraryPath"] is not None:
        library_path, library_bytes, library_info = _read_regular(
            os.path.realpath(document["pythonRuntimeLibraryPath"]),
            MAX_EXECUTABLE_BYTES,
            "INVALID_PYTHON_RUNTIME_LIBRARY",
            require_owner=False,
            require_single_link=False,
        )
        if library_path != os.path.abspath(document["pythonRuntimeLibraryPath"]):
            _stop("WRONG_PYTHON_RUNTIME_LIBRARY_PATH")
        if _sha256(library_bytes) != document["pythonRuntimeLibrarySha256"]:
            _stop("WRONG_PYTHON_RUNTIME_LIBRARY_DIGEST")
        library_identity = _file_observation(
            library_path,
            library_bytes,
            library_info,
        )
    return executable_identity, library_identity


def _prepare_inputs(
    arguments: list[str],
) -> tuple[dict[str, object], bytes, str, os.stat_result, dict[str, object]]:
    _runtime()
    if len(arguments) != 5:
        _stop("WRONG_LAUNCH_ARGUMENTS")
    expected_source_sha = _digest_text(arguments[1], "INVALID_SOURCE_DIGEST")
    expected_manifest_sha = _digest_text(arguments[4], "INVALID_MANIFEST_DIGEST")
    source_path, source_bytes, source_info = _read_regular(
        arguments[0], MAX_PUBLIC_INPUT_BYTES, "INVALID_SOURCE_FILE"
    )
    rfc_path, rfc_bytes, rfc_info = _read_regular(
        arguments[2], MAX_RFC_BYTES, "INVALID_RFC_FILE"
    )
    manifest_path, manifest_bytes, manifest_info = _read_regular(
        arguments[3], MAX_PUBLIC_INPUT_BYTES, "INVALID_MANIFEST_FILE"
    )
    input_directory = _private_input_directory(source_path, manifest_path)
    if (
        stat.S_IMODE(source_info.st_mode) != 0o400
        or stat.S_IMODE(manifest_info.st_mode) != 0o400
        or _sha256(source_bytes) != expected_source_sha
        or _sha256(manifest_bytes) != expected_manifest_sha
    ):
        _stop("PUBLIC_INPUT_IDENTITY_MISMATCH")
    manifest_value = _strict_json(manifest_bytes)
    if type(manifest_value) is not dict or _canonical(manifest_value) != manifest_bytes:
        _stop("NONCANONICAL_PUBLICATION_MANIFEST")
    manifest = manifest_value
    document, *_ = _capture_plan(manifest)
    try:
        input_common = os.path.commonpath(
            (os.path.realpath(input_directory), os.path.realpath(os.getcwd()))
        )
    except ValueError:
        _stop("INVALID_PUBLIC_INPUT_DIRECTORY")
    if input_common == os.path.realpath(os.getcwd()):
        _stop("PUBLIC_INPUT_DIRECTORY_INSIDE_WORKTREE")
    executable_identity, library_identity = _runtime_file_identities(document)
    if rfc_path != os.path.abspath(document["rfcPath"]):
        _stop("WRONG_RFC_PATH")
    if os.path.relpath(rfc_path, os.getcwd()) != RFC_RELATIVE_PATH:
        _stop("WRONG_RFC_RELATIVE_PATH")
    if _sha256(rfc_bytes) != document["rfcPreCaptureSha256"]:
        _stop("WRONG_RFC_PRECAPTURE_DIGEST")
    if expected_source_sha != document["programSourceSha256"]:
        _stop("WRONG_PROGRAM_SOURCE_DIGEST")
    _render_rfc_bytes(rfc_bytes, _pretty_json({"preflight": "VALID"}))
    _unlink_public_input(source_path, source_info, "SOURCE_REMOVAL_FAILED")
    _unlink_public_input(manifest_path, manifest_info, "MANIFEST_REMOVAL_FAILED")
    try:
        os.rmdir(input_directory)
    except Exception:
        _stop("PUBLIC_INPUT_DIRECTORY_REMOVAL_FAILED")
    temporary_input_observation = {
        "directoryAbsent": not os.path.lexists(input_directory),
        "manifestAbsent": not os.path.lexists(manifest_path),
        "sourceAbsent": not os.path.lexists(source_path),
    }
    if any(value is not True for value in temporary_input_observation.values()):
        _stop("PUBLIC_INPUT_REMOVAL_NOT_OBSERVED")
    provenance = {
        "manifestSha256": expected_manifest_sha,
        "programSourceSha256": expected_source_sha,
        "pythonExecutableIdentity": executable_identity,
        "pythonRuntimeBuildKind": document["pythonRuntimeBuildKind"],
        "pythonRuntimeLibraryIdentity": library_identity,
        "rfcPreCaptureSha256": document["rfcPreCaptureSha256"],
        "temporaryInputObservation": temporary_input_observation,
    }
    return manifest, rfc_bytes, rfc_path, rfc_info, provenance


def _read_bearer() -> str:
    descriptor: int | None = None
    original: list[object] | None = None
    try:
        descriptor = os.open(
            "/dev/tty",
            os.O_RDWR | os.O_NOCTTY | os.O_CLOEXEC,
        )
        if not os.isatty(descriptor):
            _stop("BEARER_CHANNEL_NOT_TTY")
        original = termios.tcgetattr(descriptor)
        hidden = original.copy()
        hidden[3] &= ~termios.ECHO
        termios.tcsetattr(descriptor, termios.TCSAFLUSH, hidden)
        os.write(descriptor, b"Pre-materialized bearer (input hidden): ")
        value = bytearray()
        while len(value) <= 8192:
            character = os.read(descriptor, 1)
            if character in {b"\n", b"\r"}:
                break
            if not character:
                _stop("BEARER_CHANNEL_CLOSED")
            value.extend(character)
        if len(value) > 8192:
            _stop("INVALID_PREMATERIALIZED_BEARER_TOKEN")
        try:
            token = bytes(value).decode("ascii", "strict")
        except UnicodeDecodeError:
            _stop("INVALID_PREMATERIALIZED_BEARER_TOKEN")
        if TOKEN.fullmatch(token) is None:
            _stop("INVALID_PREMATERIALIZED_BEARER_TOKEN")
        return token
    except CaptureStop:
        raise
    except Exception:
        _stop("BEARER_CHANNEL_FAILURE")
    finally:
        if descriptor is not None:
            if original is not None:
                try:
                    termios.tcsetattr(descriptor, termios.TCSAFLUSH, original)
                    os.write(descriptor, b"\n")
                except Exception:
                    pass
            os.close(descriptor)


def _record_markers() -> tuple[bytes, bytes]:
    return (
        b"<!-- OPEC-" + b"RECORD-BEGIN -->",
        b"<!-- OPEC-" + b"RECORD-END -->",
    )


def _tilde_fence(record: bytes) -> bytes:
    longest = 0
    current = 0
    for value in record:
        if value == ord("~"):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return b"~" * max(3, longest + 1)


def _render_rfc_bytes(rfc: bytes, record: bytes) -> bytes:
    begin, end = _record_markers()
    if begin in record or end in record:
        _stop("RECORD_CONTAINS_RFC_MARKER")
    if rfc.count(begin) != 1 or rfc.count(end) != 1:
        _stop("WRONG_RFC_RECORD_MARKERS")
    start = rfc.index(begin) + len(begin)
    finish = rfc.index(end)
    if start >= finish:
        _stop("WRONG_RFC_RECORD_MARKER_ORDER")
    fence = _tilde_fence(record)
    replacement = b"\n\n" + fence + b"json\n" + record + fence + b"\n\n"
    rendered = rfc[:start] + replacement + rfc[finish:]
    if len(rendered) > MAX_RFC_BYTES:
        _stop("RENDERED_RFC_OVER_BOUND")
    return rendered


def _same_rfc_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev,
        left.st_ino,
        left.st_ctime_ns,
        left.st_mtime_ns,
        left.st_size,
        left.st_mode,
        left.st_uid,
        left.st_gid,
        left.st_nlink,
    ) == (
        right.st_dev,
        right.st_ino,
        right.st_ctime_ns,
        right.st_mtime_ns,
        right.st_size,
        right.st_mode,
        right.st_uid,
        right.st_gid,
        right.st_nlink,
    )


def _verify_rfc_unchanged(
    path: str,
    before: os.stat_result,
    expected_sha256: str,
) -> None:
    current_path, current_bytes, current_info = _read_regular(
        path,
        MAX_RFC_BYTES,
        "RFC_CHANGED_BEFORE_RENDER",
    )
    try:
        after = os.lstat(path)
    except Exception:
        _stop("RFC_CHANGED_BEFORE_RENDER")
    if (
        current_path != path
        or not _same_rfc_identity(before, current_info)
        or not _same_rfc_identity(current_info, after)
        or _sha256(current_bytes) != expected_sha256
    ):
        _stop("RFC_CHANGED_BEFORE_RENDER")


def _write_rfc(
    path: str,
    before: os.stat_result,
    expected_sha256: str,
    rendered: bytes,
) -> None:
    temporary = path + ".opec-render.tmp"
    descriptor: int | None = None
    replaced = False
    try:
        if os.path.lexists(temporary):
            _stop("RFC_CHANGED_BEFORE_RENDER")
        _verify_rfc_unchanged(path, before, expected_sha256)
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            stat.S_IMODE(before.st_mode),
        )
        view = memoryview(rendered)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                _stop("RFC_RENDER_WRITE_FAILED")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, stat.S_IMODE(before.st_mode))
        os.close(descriptor)
        descriptor = None
        _verify_rfc_unchanged(path, before, expected_sha256)
        os.replace(temporary, path)
        replaced = True
        directory = os.open(os.path.dirname(path), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except CaptureStop:
        raise
    except Exception:
        _stop("RFC_RENDER_FAILURE")
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except Exception:
                pass
        if not replaced and os.path.lexists(temporary):
            try:
                os.unlink(temporary)
            except Exception:
                pass


def _failure_record(
    error: CaptureStop,
    provenance: dict[str, object],
) -> bytes:
    if (
        error.code not in RECORDABLE_FAILURE_CODES
        or not _recordable_failure_has_provider_call(error)
    ):
        _stop("UNOBSERVED_RECORDABLE_FAILURE")
    provenance_document = _provenance(provenance)
    return _pretty_json(
        {
            "captureOutcome": "STOPPED_WITH_RECORDABLE_FAILURE_METADATA",
            "externalReviewControl": {
                "requiredExactHeadReviewCount": 2,
                "reviewObjectsStored": "EXTERNAL_GITHUB_RECORDS",
                "status": "PENDING_EXTERNAL_EXACT_HEAD_REVIEWS",
            },
            "failureCode": error.code,
            "failureMetadata": error.metadata,
            "launchProtocolId": LAUNCH_PROTOCOL_ID,
            "programId": PROGRAM_ID,
            "recordSchema": RECORD_SCHEMA,
            "rendererId": RENDERER_ID,
            **provenance_document,
        }
    )


def _recordable_failure_has_provider_call(error: CaptureStop) -> bool:
    ledger = error.metadata.get("policyTroubleshooterCallLedger")
    label = error.metadata.get("label")
    if type(ledger) is not list or not ledger or type(label) is not str:
        return False
    last_entry = ledger[-1]
    return (
        type(last_entry) is dict
        and error.code.startswith(label + "_")
        and last_entry.get("label") == label
        and last_entry.get("method") == "POST"
        and last_entry.get("endpoint") == ENDPOINT
        and type(last_entry.get("status")) is int
        and type(last_entry.get("completedAt")) is str
    )


def _main(arguments: list[str]) -> None:
    manifest, rfc, rfc_path, rfc_info, provenance = _prepare_inputs(arguments)
    bearer_token = _read_bearer()
    capture_error: CaptureStop | None = None
    record: bytes | None = None
    try:
        record = run_capture(bearer_token, manifest, provenance)
    except CaptureStop as error:
        capture_error = error
    finally:
        bearer_token = ""
    if capture_error is not None:
        if (
            capture_error.code not in RECORDABLE_FAILURE_CODES
            or not _recordable_failure_has_provider_call(capture_error)
        ):
            raise capture_error
        record = _failure_record(capture_error, provenance)
    if record is None:
        _stop("MISSING_RENDER_RECORD")
    _write_rfc(
        rfc_path,
        rfc_info,
        _sha256(rfc),
        _render_rfc_bytes(rfc, record),
    )
    if capture_error is not None:
        raise CaptureStop(
            "RECORDABLE_FAILURE_RENDERED",
            {"failureCode": capture_error.code},
        ) from None


def _emit_stop(error: CaptureStop) -> None:
    error.__context__ = None
    error.__cause__ = None
    error.__traceback__ = None
    payload = _canonical({"code": error.code, "metadata": error.metadata}) + b"\n"
    try:
        os.write(2, payload)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        _main(sys.argv)
    except CaptureStop as error:
        _emit_stop(error)
        raise SystemExit(2) from None
    except BaseException:
        try:
            os.write(2, b'{"code":"UNEXPECTED_FAILURE","metadata":{}}\n')
        except Exception:
            pass
        raise SystemExit(3) from None
~~~

This program is the launcher verifier, runtime verifier, manifest verifier,
response safety gate, evidence recorder, failure recorder, and RFC renderer.
There is no executable wrapper, imported project module, inspector callback,
or separate renderer. Version 3 also owns quota-project header construction,
the exact fixture-organization binding, and complete expected-response
identity/scope validation.

The embedded source is not a repository Python path, so hosted structural and
unit-test gates do not execute it. Reviewers must extract the exact bytes and
reproduce the section 12 checks. At the recorded line layout, _deny_inventory
occupies lines 624 through 743 inclusive, 120 lines, and _post occupies lines
777 through 889 inclusive, 113 lines. They are the only functions over the
repository's 80-line production-code structural threshold. This explicit
review exception applies only to the inert embedded artifact; it grants no
production-code exception.

### 7.3 Exact fresh-process launch protocol

The live card supplies literal absolute values for all angle-bracket fields.
Before bearer input, the operator:

1. enters the canonical repository worktree root recorded as workingDirectory;
2. creates one non-repository private input directory owned by the executing
   user with mode 0700;
3. extracts the exact section 7.2 source into capture.py in that directory and
   writes the exact canonical public manifest beside it;
4. sets both regular, single-link files to mode 0400;
5. independently verifies the Darwin host identity, native Python build
   linkage, source, manifest, pinned CPython executable, any separately linked
   Python runtime library, and pre-capture RFC digests; and
6. invokes the following argument vector directly, with no function, wrapper,
   pipeline, redirection, debugger, tracer, profiler, or command substitution:

~~~text
/usr/bin/env -i LC_ALL=C <absolute-pinned-cpython> -I -S -B <absolute-private-capture.py> <source-sha256> <absolute-rfc-path> <absolute-private-manifest.json> <manifest-sha256>
~~~

The script itself revalidates:

- CPython 3.12.13 on the exact Darwin host system, kernel release, and machine,
  isolated mode, ignore-environment, no-site, safe-path, and no-bytecode flags;
- a launch environment containing exactly LC_ALL=C, while permitting the
  operating system to inject __CF_USER_TEXT_ENCODING only when it matches the
  fixed numeric pattern;
- global and per-connection HTTP debug level zero;
- source and manifest ownership, regular-file type, single link, modes,
  bounded sizes, exact hashes, same private directory, directory mode, and
  resolution outside the repository worktree;
- canonical manifest bytes, the exact dedicated fixture organization, and
  every expected response semantic;
- the real pinned executable path and complete executable SHA-256, the exact
  build classification, and the complete path and SHA-256 of a framework or
  shared Python runtime library when present;
- exact working directory, absolute and repository-relative RFC path, RFC
  pre-capture digest, and unique ordered record markers; and
- exact source digest agreement between the argument and manifest.

The program then unlinks capture.py and manifest.json, removes their private
directory, and observes that all three paths are absent. Only after successful
removal does it open /dev/tty directly and verify it is a TTY. It disables
echo with TCSAFLUSH before emitting the prompt, so already typed input is
discarded before any prompt can expose an echo-enabled typeahead window, then
reads the pre-materialized ASCII bearer. The bearer is never a shell argument,
environment value, file value, return value, digest input, or record member.
Terminal attributes are restored on every path.

The fresh -I -S process prevents ordinary site customization, user-site,
script-directory import, Python environment, or preloaded application-module
injection. The exact program has no dynamic import or caller callback. The
record contains actual runtime observations, executable/runtime-library file
observations, computed auth-side ledger and count, and observed temporary-path
absence. It intentionally has no self-attested freshProcess boolean: freshness
is a property of the exact launch protocol, supported by the current-process
observations. After the calls it creates deterministic immutable UTF-8 JSON
record bytes; no mutable result object leaves the exact program.

Python does not provide reliable secure erasure of immutable strings or all
intermediate process memory. The source rebinds its bearer variable after use
and never serializes the bearer, but it does not claim that CPython heap pages,
TLS buffers, kernel buffers, or terminal-driver memory are scrubbed. Process
exit and the trusted host/operating-system precondition bound that residual
memory risk.

### 7.4 Exact request, transport, and authentication protocol

Each call uses:

~~~text
POST https://policytroubleshooter.googleapis.com/v3beta/iam:troubleshoot
HTTP/1.1 via http.client.HTTPSConnection
timeout: 5.0 seconds
redirects: disabled
query parameters: none
Accept: application/json
Content-Type: application/json; charset=utf-8
Accept-Encoding: identity
Connection: close
Authorization: Bearer <hidden pre-materialized value>
x-goog-user-project: <exact public manifest quotaProjectId>
~~~

Each request is canonical compact UTF-8 JSON of the exact manifest request,
with no terminal newline and a 131072-byte maximum. The record includes the
full request base64, byte length, SHA-256, request-controlled access tuple, and
public quotaProjectId. The quota project is not inferred, discovered, or read
from credentials, configuration, or environment. The source has one
HTTPSConnection constructor path and one request statement. A 401 or any
transport failure is terminal and cannot refresh or replay.

The response evidence boundary is the ordered entity-body octet sequence after
HTTP framing is removed. Headers and framing are excluded. Content-Encoding
must be absent or identity. The source reads at most 131073 bytes, rejects
empty or over-bound bodies, and freezes length and lowercase SHA-256 before
UTF-8 decoding or JSON parsing.

Status must be 200. Content-Type must have base media type application/json.
The body must be strict UTF-8 without BOM, exactly one JSON value, with no
duplicate member, non-JSON numeric constant, or trailing non-whitespace value.
Parsing never replaces the frozen bytes. Published Content-Type and
Content-Encoding fields are fixed normalized values, not uncontrolled header
strings.

### 7.5 Response binding and automated publication safety

Each strict parsed response has exactly accessTuple, allowPolicyExplanation,
denyPolicyExplanation, overallAccessState, and pabPolicyExplanation. The
returned request-controlled access tuple must equal the request's principal,
fullResourceName, permission, and complete conditionContext.resource.
permissionFqdn and optional effectiveTags are validated and recorded as
output-only values. pabPolicyExplanation must have
PAB_ACCESS_STATE_NOT_ENFORCED, permitted relevance, and an omitted or empty
explainedBindingsAndPolicies list. This is the only admitted PAB shape.

Before bearer input, the source recursively validates both complete expected
response objects. It interprets principal-bearing fields rather than relying
only on string substrings: principal is a scalar, members and exemptedMembers
are lists, memberships is a keyed map, and deniedPrincipals and
exceptionPrincipals may be lists or keyed maps. Every admitted entry must
equal one of the three exact service-account forms derived from the sorted
publicServiceAccountEmails manifest member. It rejects every principalSet
field, every other principal:// or principalSet:// spelling, bare IAM pool
targets, principal-bearing PAB conditions, human/group/domain/deleted/public
values, opaque semantic principals, ancestor scope, and unapproved service
accounts. Outside those exact admitted identities, every string key and value
is also
scanned for every embedded reserved IAM identity marker:
`//iam.googleapis.com/`, `allAuthenticatedUsers`, `allUsers`, `deleted:`,
`domain:`, `group:`, `principal://`, `principalSet://`,
`serviceAccount:`, and `user:`. Every folder scope spelling refuses. The
source validates every percent triplet and constructs one nonrecursive URI
comparison view by normalizing hex case and decoding only URI-unreserved
characters. It checks both the original and comparison strings. The only
admitted organization-scope string values are the exact full and bare resource
names derived from fixtureOrganizationId; either value as an object key, an
encoded, embedded, different, or malformed organization spelling, or an
organization-attached deny-policy name refuses. Each expected aggregate allow
state is determinate. Every explained allow policy has determinate state and
relevance, a visible nonempty policy object, a binding-explanations list, and
exact binding/explanation cardinality. The exact full organization resource
must occur once with nonempty bindings. Both request principals must be in the
manifest list. overallAccessState is preserved and compared as part of the
complete response but is not used as evidence of allow-policy visibility. This
gate is structural and precedes the complete-object canonical-equality gate;
it cannot be bypassed by approving an unsafe expected object.

For D1, every outer, resource, and policy deny state used by the inventory is
determinate; relevance is permitted; every explained resource has visible
fullResourceName and relevance; each resource has a nonempty explainedPolicies
array; every policy body is complete; every policy name is project-attached;
and every derived project spelling equals the containing fullResourceName.
The observed ordered pair list must equal d1ExpectedPairs.

For N1, the outer state is exactly NOT_DENIED, permissionDeniable is true,
relevance is permitted, and explainedResources is explicitly present as the
empty array.

Only after those checks does the source compare canonical JSON of the complete
actual parsed response with canonical JSON of the complete expected manifest
object. This is the automated publication allowlist. There is no human viewer
or inspector between provider input and publication. Any otherwise valid
difference produces an unapproved-response refusal and no RFC write.

Exactly four body-derived failures may write a stopped-run record:

- D1_ATTACHMENT_MISMATCH;
- D1_EXPLAINED_RESOURCES_OMITTED;
- D1_RESOURCE_VISIBILITY_OMITTED; and
- N1_EXPLAINED_RESOURCES_OMITTED.

The exact program renders one of those codes only when the captured exception
also carries a nonempty observed Policy Troubleshooter call ledger whose last
entry matches the failure label, POST method, fixed endpoint, response status,
and completion timestamp. A pre-call expected-manifest validation error or a
synthetic recordable code therefore cannot create provider-observation
metadata.

Those records contain only the fixed code, capture label, status, body length,
body digest, call ledger, and public provenance. They contain no response body,
returned attachment spelling, resource name, policy name, header value, or
token. D1 outer explainedResources omission has its own code rather than the
generic object-members code. D1 attachment mismatch is confirmation-only: it
records that exact equality failed but publishes no observed spelling.

### 7.6 Exact publication encoding and renderer

On success, each frozen body is stored as standard padded RFC 4648 base64 split
into a JSON array of strings no longer than 76 characters. Decoding the
concatenated strings reproduces the recorded byte length and SHA-256. The
parsed inventory is derived evidence; the decoded body controls.

run_capture returns deterministic pretty JSON bytes with sorted keys, two-space
indentation, ASCII escaping, and one terminal LF. The same exact source:

1. rejects any record containing either marker and locates exactly one ordered
   begin/end record-marker pair in the pre-capture RFC bytes;
2. chooses a tilde fence longer than any tilde run in the record;
3. replaces only the bytes between those markers;
4. refuses a rendered RFC over 1048576 bytes;
5. no-follow re-reads the current RFC and verifies both its complete SHA-256
   against the pre-capture bytes and its device, inode, ctime, mtime, size,
   mode, owner, group, and link-count identity;
6. creates only a sibling .opec-render.tmp with exclusive no-follow semantics
   and the original file mode;
7. writes and fsyncs the complete rendered bytes;
8. immediately no-follow re-reads and rehashes the current RFC, rechecks that
   complete original identity, atomically replaces only the RFC, and fsyncs
   its directory; and
9. removes an incomplete temporary file on failure.

No other durable repository path is produced. The renderer uses only its fixed
sibling temporary path for atomic replacement, and removes that path on a
pre-replacement failure. The source and manifest were already removed before
bearer input. A non-recordable refusal writes no RFC. Its stderr output is
deterministic JSON containing only a fixed code and approved safe metadata.

## 8. State machine

The only success path is:

~~~text
UNAPPROVED
  -> COMPLETE_LIVE_CARD_DISPLAYED
  -> EXACT_APPROVAL_RECEIVED
  -> PUBLIC_INPUTS_PREPARED
  -> FRESH_PROCESS_AND_IDENTITIES_VERIFIED
  -> PUBLIC_MANIFEST_AND_EXPECTED_RESPONSES_VALIDATED
  -> PUBLIC_IDENTITIES_AND_DEDICATED_ORGANIZATION_SCOPE_VALIDATED
  -> PUBLIC_TEMPORARY_INPUTS_REMOVED
  -> HIDDEN_PREMATERIALIZED_BEARER_RECEIVED
  -> D1_SENT_AND_FROZEN
  -> D1_BOUND_INVENTORIED_AND_ALLOWLISTED
  -> N1_SENT_AND_FROZEN
  -> N1_BOUND_INVENTORIED_AND_ALLOWLISTED
  -> IMMUTABLE_RECORD_RENDERED_ATOMICALLY
  -> EVIDENCE_COMMIT_E_PUBLISHED
  -> HOSTED_CHECKS_PASS_ON_E
  -> TWO_EXTERNAL_ZERO_BLOCKER_REVIEWS_OF_E
  -> E_MERGED_UNCHANGED
~~~

Any pre-call failure stops with zero calls. Any post-call non-recordable
failure stops with no RFC write. One of the four recordable failures writes
only its bounded confirmation record after a nonempty matching observed call
ledger proves that the named provider call occurred, then stops. No partial
result grants authority, and N1 cannot cure a failed D1.

## 9. Normative invariants and refusal cases

### 9.1 Normative invariants

- OPEC-001 — No Phase B evidence call occurs before one complete live card and
  exact later approval. The call ledger is exactly D1 then N1, with the exact
  public quota project on each entry, zero auth-side calls, and no retry or
  replay. A recordable failure requires a nonempty observed ledger ending in
  the matching D1 or N1 provider call.
- OPEC-002 — The process is a fresh exact CPython 3.12.13 process with the
  pinned executable digest, exact Darwin host and runtime linkage, -I -S -B,
  the minimal permitted environment, exact source digest, no wrapper, and no
  application-module injection path.
- OPEC-003 — The source and canonical version-3 public manifest, including
  decisionVersion, quotaProjectId, fixtureOrganizationId, and
  publicServiceAccountEmails, are private-mode non-secret temporary inputs;
  their removal and path absence are observed before the hidden bearer read.
- OPEC-004 — HTTP debug output is disabled and terminal echo is disabled and
  pending input flushed before the bearer prompt; the bearer has no argument,
  environment, file, return, logging, digest, or publication path. No secure
  process-memory erasure claim is made.
- OPEC-005 — Each complete response body is frozen before parsing and bound to
  its exact byte range, length, digest, and lossless base64.
- OPEC-006 — Each returned request-controlled access tuple equals its exact
  request. Output-only permissionFqdn and effectiveTags are separately
  validated.
- OPEC-007 — D1 inventories every resource and policy index, exact pair,
  cardinality, derived spelling, and determinate visibility field; every
  derived spelling exactly matches its containing project resource.
- OPEC-008 — N1 is determinate NOT_DENIED evidence only when
  explainedResources is explicitly present and empty.
- OPEC-009 — Both expected responses pass the no-human, controlled-service-
  account gate; admit exactly the dedicated fixture organization and no folder,
  other organization, shared-organization member, malformed percent triplet,
  URI-equivalent encoded scope, or unapproved organization spelling; require a
  determinate aggregate allow state and complete determinate visibility of
  every explained allow policy; expose that exact organization once in each
  allow explanation with nonempty bindings; and pass the exact no-applicable-
  PAB gate before bearer input. Each complete strict parsed response equals its
  complete pre-approved manifest object under canonical JSON before
  publication.
- OPEC-010 — The deterministic renderer can replace only this RFC's one
  marker-delimited record, re-reads and matches its complete pre-capture digest
  immediately before replacement, and returns no mutable capture result.
- OPEC-011 — The immutable evidence commit contains no embedded exact-head
  review IDs. Hosted checks and two reviews are external merge controls bound
  to that unchanged commit.
- OPEC-012 — The run performs no provider mutation, credential act, fixture
  provisioning, production acceptance, parser change, runtime integration, or
  authority transfer to PR #322. Organization visibility is admitted only for
  the exact dedicated ancestor-clean fixture organization; shared-organization
  or unrelated-member visibility cannot clear a qualification or capture
  failure.

### 9.2 Mandatory D1 derivation

For every complete policy name matching:

~~~text
policies/cloudresourcemanager.googleapis.com%2Fprojects%2F<positive-decimal>/denypolicies/<policy-id>
~~~

the source captures the positive decimal and constructs exactly:

~~~text
//cloudresourcemanager.googleapis.com/projects/<same-positive-decimal>
~~~

That spelling must equal the containing fullResourceName by exact string
equality. General URL decoding, lowercase escape acceptance, project-ID
substitution, lookup, normalization, ancestor inference, or logical
equivalence is forbidden.

### 9.3 Refusal matrix

| Condition | Required result |
| --- | --- |
| Missing card, approval, fixture, public manifest, pinned runtime, source identity, or separate bearer authority | Zero calls; stop |
| Missing, malformed, or different decisionVersion, quotaProjectId, fixtureOrganizationId, publicServiceAccountEmails, or quota-project header | Zero calls; stop |
| Expected response contains a human, group, domain, deleted, public, opaque or non-service-account semantic principal, any unapproved service account, any reserved IAM identity marker anywhere in any key or value other than one of the three exact allowlisted service-account forms, any principalSet field, any unapproved audit-log exemptedMembers identity, any principal-bearing PAB condition, any malformed percent triplet, any folder scope, any shared/other organization scope, an organization-attached deny-policy name, an organization scope in an object key, or an encoded, embedded, or otherwise unapproved organization spelling | Zero calls; stop before bearer input |
| Either expected allowPolicyExplanation has an indeterminate aggregate allow state or relevance; any explained allow policy omits its resource, has indeterminate state/relevance, has an empty policy object, omits binding explanations, or has inconsistent binding/explanation cardinality; or the exact full fixture organization does not occur once with nonempty bindings | Zero calls; stop before bearer input |
| Expected or actual PAB explanation is not exactly NOT_ENFORCED with permitted relevance and an omitted or empty binding/policy list | Zero calls when expected; otherwise stop with no accepted evidence or RFC write |
| Wrong environment, host, Python flag/path/digest/build linkage, separate runtime-library identity, source/manifest/RFC path or digest, private-input/RFC ownership/mode/link, marker count, or working directory | Zero calls; stop |
| Wrapper, debugger, profiler, callback, module injection, proxy, token lookup, refresh, replay, retry, redirect, debug trace, or hidden call | Stop; no accepted evidence |
| Wrong method, endpoint, call order, request, header, timeout, or request body over 131072 bytes | Stop; no accepted evidence |
| Transport failure, 401, other non-200 status, empty/oversized/compressed body, or invalid JSON | Stop; no refresh or retry |
| Response access tuple differs from its request or output-only values are malformed | Stop before deny evidence is used |
| D1 is indeterminate, invisible, empty, non-project, incomplete, unexpected, or outside the approved pair list | Stop; only the dedicated visibility or attachment confirmation may be rendered |
| D1 outer explainedResources is omitted | Render only D1_EXPLAINED_RESOURCES_OMITTED plus safe metadata; never infer empty |
| D1 derived attachment differs | Render only D1_ATTACHMENT_MISMATCH plus safe metadata; publish no spelling |
| D1 resource visibility field is omitted | Render only D1_RESOURCE_VISIBILITY_OMITTED plus safe metadata |
| N1 is indeterminate, denied, malformed, or nonempty | Stop; no no-deny evidence |
| N1 explainedResources is omitted | Render only N1_EXPLAINED_RESOURCES_OMITTED plus safe metadata; never infer empty |
| Complete parsed body differs from the approved expected object | Stop with no RFC write |
| A recordable code has no nonempty matching observed provider-call ledger | Stop with no RFC write; never claim a provider observation from preflight |
| RFC bytes, digest, or complete file identity change before render, or another path would be needed | Stop; do not overwrite or broaden scope |
| Evidence commit changes after either exact-head review | Reviews are stale; repeat checks and both external reviews on the new head |

## 10. Exact evidence record

### 10.1 Success and stopped-run schemas

A successful record contains:

- record, program, launch-protocol, renderer, manifest, source, executable,
  runtime-build, optional separate runtime-library, and pre-capture RFC
  identities;
- decision ID/version, the complete public service-account allowlist, the exact
  dedicated fixture organization bound to the top-level record and both
  expected allow explanations, and the exact public quota project bound to the
  top-level record, both request records, and both provider-call ledger entries;
- the observed executable and optional runtime-library byte lengths, digests,
  owners, groups, modes, and link counts;
- actual runtime environment keys and count, Python implementation, version,
  flags, platform and host values, executable path, HTTP debug level, and
  optional operating-system-injected text-encoding value;
- observed source, manifest, and private-directory absence before bearer input;
- the computed empty authSideCallLedger and authSideCallCount exactly zero;
- the two-entry D1/N1 ledger with ordinal, method, endpoint, timestamps, and
  status;
- for each call, exact request base64/length/digest and access tuple;
- exact response base64-line array/length/digest, normalized media fields,
  status, tuple-binding result, output-only fields, complete deny inventory,
  and publication-manifest equality result; and
- externalReviewControl stating that two exact-head review objects are
  required and stored externally on GitHub.

It does not assert freshProcess or temporary-input removal through hard-coded
booleans. Freshness is controlled by the launch protocol, while the record
publishes the available current-process observations and the independently
computed path-absence results.

It never contains a review ID or URL. The evidence authority is the Git commit
containing the record. After that commit, review objects refer to its immutable
head externally. This prevents a self-referential requirement to edit the
evidence commit with its own future review references.

A recordable stopped run contains the exact safe subset defined in section
7.5 and a nonempty observed provider-call ledger ending in the call that
produced the failure. It establishes only the named serialization or equality
observation. It does not establish accepted provider evidence.

### 10.2 Provisional execution record

<!-- OPEC-RECORD-BEGIN -->

~~~text
CAPTURE STATUS: UNEXECUTED
DECISION VERSION: 3; UNAPPROVED
PROGRAM SOURCE: EMBEDDED; 1626 LINES; SHA-256 0c8ebd287bee43c33e0b5aeda4563b45f7f6124ee8c7e3edc592629233350a68
FRESH PROCESS: NOT STARTED
PUBLIC MANIFEST: NOT SUPPLIED
PUBLIC SERVICE ACCOUNTS: NOT SUPPLIED
QUOTA PROJECT: NOT SUPPLIED
FIXTURE ORGANIZATION: NOT SUPPLIED
TEMPORARY INPUT REMOVAL: NOT PERFORMED
BEARER INPUT: NOT REQUESTED
AUTH SIDE CALLS: NOT PERFORMED
POLICY TROUBLESHOOTER CALL LEDGER: EMPTY
D1 RESPONSE: NOT CAPTURED
N1 RESPONSE: NOT CAPTURED
EXTERNAL EXACT-HEAD REVIEWS OF EVIDENCE COMMIT: NOT PERFORMED
CONSUMER AUTHORITY: NONE
~~~

<!-- OPEC-RECORD-END -->

### 10.3 Successful result semantics

A successful immutable record establishes only that, at the recorded time and
for the two complete pre-approved response objects:

- both returned request-controlled access tuples exactly matched their
  requests;
- every D1 visible project pair had exact derived attachment equality and the
  full ordered pair list matched the controlled fixture;
- D1 and N1 deny evidence was determinate and complete under this contract;
- both PAB explanations had the exact determinate no-applicable-PAB shape;
- N1 explicitly carried an empty explainedResources array; and
- the exact frozen response bytes were published.

It also establishes that both expected response objects passed the version-3
path-aware fixture-only identity, exact dedicated-organization scope, and
closed PAB gates before bearer input; exposed the exact fixture organization
once in each allow explanation; and used the exact public quotaProjectId. It
does not establish organization behavior, broader allow-policy semantics, or
PAB behavior beyond the exact no-applicable state.

It does not establish folder or organization behavior, broader project
behavior, behavior under incomplete policy visibility, credential identity,
least privilege, provider support currentness, parser correctness, production
acceptance, or deployment readiness.

## 11. Phase boundaries and finite publication sequence

### 11.1 Phase A

Phase A changes only this RFC. It performs zero iam:troubleshoot calls and uses
zero Google/provider credentials. Local drafting does not authorize staging,
commit, push, PR-description mutation, review reply, thread resolution, merge,
or Phase B. Each remote Phase A publication action requires task-user
authorization.

The failed version-1 and version-2 calls in section 5.6 occurred under
separate, exhausted qualification authorizations outside this decision.
Recording their safe confirmation metadata here does not convert them into
evidence or authorize a replacement qualification.

### 11.2 Prospective Phase B

Only the exact approval in section 13 may authorize:

1. preparation and verification of the non-secret temporary source and public
   manifest;
2. one fresh-process execution with one separately pre-materialized bearer;
3. exactly D1 then N1;
4. the exact program's one-RFC atomic evidence render;
5. inspection of the one-file diff;
6. commit and push of that evidence-only amendment as immutable evidence head
   E in Draft PR #323;
7. hosted checks on E;
8. two independent external GitHub reviews explicitly bound to E; and
9. merge of E unchanged after both reviews report zero demonstrated in-scope
   Blockers.

No attestation edit follows the reviews. Review identities and URLs remain
external. Any evidence-file edit creates a new head, invalidates both reviews,
and restarts steps 7 through 9. The PR description must identify the current
head and artifact accurately, but it is external metadata and never evidence
authority.

Phase B may not commit the extracted script, manifest, separate evidence file,
credential, header dump, log, screenshot, fixture, test harness, parser change,
or generated artifact.

### 11.3 Consumer sequence

Even after PR #323 merges, PR #322 remains blocked until it separately:

1. imports the immutable complete project-attachment evidence and its exact
   dedicated-fixture-organization limitation;
2. passes its own hosted checks;
3. receives two zero-Blocker exact-head reviews; and
4. displays and receives approval for its own complete implementation card.

No approval or review from this capture substitutes for a consumer gate.

## 12. Verification and review plan

### 12.1 Phase A artifact verification

Reviewers must independently:

- confirm this RFC is the only changed path and the trust boundary stayed
  acquisition/publication only;
- extract the first Python block exactly and reproduce 1626 LF-terminated
  lines and SHA-256
  0c8ebd287bee43c33e0b5aeda4563b45f7f6124ee8c7e3edc592629233350a68;
- compile it with exact CPython 3.12.13;
- run repository-pinned Ruff 0.15.5 check and format check;
- run an isolated fake-transport harness under an empty LC_ALL=C environment,
  -I -S -B, covering the valid two-call path; optional valid macOS text-encoding
  injection; runtime, host, flag, and environment refusal; global and
  per-connection debug-level control; connection failure; secret absence;
  terminal-call ordering; tuple swaps; each request-controlled field;
  effectiveTags present/absent; unknown
  N1; omitted N1 resources; omitted D1 outer resources; omitted D1 resource
  visibility; attachment mismatch; nonempty N1; unapproved complete response;
  missing/malformed/different quota project or fixture organization; missing
  or stale decision version;
  unsorted, duplicate, malformed, or incomplete public service-account lists;
  human/group/domain/deleted/public identities; opaque entries in every
  semantic principal field; nested
  auditConfigs[].auditLogConfigs[].exemptedMembers values rejecting opaque,
  user, group, domain, allUsers, deleted service-account, generic principal://,
  every principalSet://, and unapproved service-account identities; each closed
  reserved IAM identity marker embedded in an arbitrary nested nonsemantic
  string value, object key, and semantic principal field; all three exact
  allowlisted service-account forms and one harmless nonidentity control;
  generic workforce, workload, GKE workload, and agent principal:// forms;
  every principalSet:// form; bare workforce/workload pool and project
  principal-set targets at the PAB target path; principal.type and
  principal.subject PAB conditions; allowed project resource spellings outside
  principal fields; closed PAB list omission/empty equivalence; every
  nonempty, allowed, denied, unknown, unspecified, or malformed PAB posture; and
  every complete and bare folder scope; malformed percent triplets; all mixed-
  case `%2F` slash encodings; percent-encoded URI-unreserved letters;
  `organizations%2F`; and each encoded scope in an arbitrary value, object key,
  policy name, and wrong-organization case, with no recursive decoding; exact
  full and bare fixture-organization values; missing, duplicate, embedded,
  other, and malformed fixture-organization values; organization-attached
  deny-policy names; exact organization values used as object keys; and shared-
  organization members in arbitrary nested policies; plus aggregate
  ALLOW_ACCESS_STATE_UNKNOWN_INFO and UNKNOWN_CONDITIONAL; unknown state,
  omitted visibility fields, empty policy body, or binding/explanation
  mismatch on every non-organization explained policy; and missing/empty
  organization policy bindings or indeterminate organization state/relevance;
  source/manifest/executable/runtime-library/RFC identity checks; root-owned or
  hard-linked exact executable acceptance; monolithic and separate-runtime
  linkage rules; observed runtime, auth-side ledger/count, and temporary-path
  absence; rejection of a recordable code without a nonempty matching provider
  call ledger; record-marker injection; deterministic fence selection;
  wrong-current-digest and same-inode RFC mutation refusal; and atomic one-RFC
  replacement;
- run a real controlling-PTY regression that queues harmless input before echo
  suppression, supplies a bearer-shaped value after suppression but before
  prompt output, proves the queued input is discarded and the bearer never
  appears in terminal output, verifies the hidden value or fixed refusal, and
  compares complete terminal attributes before and after both success and
  refusal;
- inspect the exact fresh launch vector and verify no wrapper or callback is
  admitted;
- inspect the executable with the host's native linkage tool; establish a
  genuinely monolithic build or pin and hash the separately linked Python
  runtime library in the manifest;
- confirm _post and _deny_inventory are the only over-80-line functions and
  apply the explicit embedded-artifact review noted in section 7.2;
- confirm exactly one HTTPS constructor path, one request statement, fixed
  D1/N1 calls, no token/refresh/proxy/retry/redirect/logging path, and
  normalized publishable headers including the exact public
  x-goog-user-project value on both calls;
- confirm the marker strings occur exactly once as the ordered record pair;
- run git diff --check and the repository conformance command; and
- note explicitly that hosted repository checks do not execute the embedded
  Python, so independent extraction is mandatory.

### 12.2 Phase B evidence verification

Before publication and review:

- reproduce every OPEC invariant and every
  source/manifest/executable/runtime-library/RFC digest;
- reproduce the recorded absence of both temporary public inputs and their
  directory before bearer input;
- reproduce the exact D1/N1 call ledger and the independently computed empty
  auth-side ledger and count, including the same exact quotaProjectId on both
  provider-call and request records;
- decode every base64-line array and reproduce response lengths and digests;
- independently parse the complete bodies with duplicate-member refusal;
- reproduce request binding, all output-only fields, every D1 pair and
  cardinality, exact project derivations, and explicit empty N1 array;
- compare each complete parsed response to its complete expected manifest
  object;
- reproduce the path-aware no-human, public-service-account-only, exact
  dedicated-organization scope gate over every key and value in both complete
  expected response objects, including the scalar/list/map principal-field
  types, exact three admitted service-account forms, one exact full
  fixture-organization resource in each allow explanation, determinate
  aggregate state and complete visibility/cardinality for every explained
  allow policy, strict one-pass percent-triplet comparison, and refusal of
  every folder, encoded/other organization, shared-organization member,
  embedded organization spelling, and organization-attached deny-policy name;
- reproduce the exact NOT_ENFORCED, omitted-or-empty-binding, permitted-
  relevance PAB shape for both responses;
- inspect the one-file diff and prove no secret or unexpected value is
  present;
- run local conformance and hosted checks on evidence head E; and
- obtain two external exact-head reviews of E with zero demonstrated in-scope
  Blockers.

### 12.3 Review classification

An in-scope Blocker demonstrates that an OPEC invariant cannot hold, that
unapproved provider data can be published, that the bearer can escape, that
the two-call/result binding is incomplete, that the renderer can write beyond
this RFC, that the review sequence is circular, or that this PR crosses its
primary trust boundary.

Provisioning, credential custody, wider provider support, parser design,
runtime integration, deployment, folder or organization-behavior evidence,
and issue closure remain separate decisions unless the finding proves this
capture cannot stay bounded without one of them.

## 13. Proposed approval boundary

This Draft RFC, PR #323, checks, reviews, branch, commit, credential
availability, PR #322 approval, or generic go grants no Phase B authority.

Only after one published Phase A RFC head passes hosted checks and receives two
independent zero-Blocker reviews may one complete live decision card be
displayed in this same Codex task. The card must include:

- decision ID and proposed version;
- exact RFC head, source line count/digest, Darwin host system/kernel
  release/machine, pinned executable path/digest, Python build classification,
  separate runtime-library path/digest when applicable or the independently
  verified monolithic-linkage result, manifest bytes/digest, working directory,
  RFC path/pre-capture digest, and launch vector;
- the complete public manifest, including both full expected response objects;
- the controlled non-production publication, exact quota project, exact
  dedicated fixture organization, direct-child fixture projects, no folders,
  permitted public service accounts, organization-scoped Security Reviewer and
  Deny Reviewer, Service Usage Consumer on the quota project, complete
  allow/deny visibility declarations, absence of shared or unrelated members,
  and exact closed no-applicable-PAB expected-response shapes;
- the exhausted version-1 and version-2 qualification results and the separate
  successful version-3 qualification authority/reference that supplied the
  expected objects, without private response-storage or credential details;
- the separate non-secret bearer-authority reference, without materialization
  details;
- all twelve OPEC invariants, the two-call budget, renderer boundary, external
  evidence-review sequence, and every stop condition;
- the exact temporary and repository effects; and
- every excluded provider, credential, provisioning, parser, runtime,
  database, deployment, production, consumer, and issue-closure authority.

The required exact approval form is:

~~~text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-OBSERVER-ROOT-PROVIDER-EVIDENCE-CAPTURE-001 version 3.
~~~

Approval is recognized only when that sentence is the exact entire later
task-user message after the complete live card in this same task. No current
message supplies it.

That approval would authorize only the finite Phase B sequence in section
11.2. It would not authorize bearer materialization, lookup, refresh, replay,
fixture provisioning, provider mutation, production access, folder or
organization-behavior evidence, production support acceptance, PR #322
implementation, runtime integration, deployment, release, issue closure, or a
security waiver.

## 14. Stop rule and dependency handoff

Stop before any provider call if the complete card or exact approval is absent;
if any live-card public value is unsafe; if source, manifest, runtime,
executable, repository, RFC, environment, file, or marker identity differs; if
the bearer requires any unauthorized materialization path; if either controlled
fixture, exact quota project, exact dedicated fixture organization, direct-
child/no-folder declaration, public-service-account list, complete allow/deny
visibility declaration, or no-unrelated-member declaration is absent; if any
response value crosses the exact dedicated-organization public scope; or if a
wrapper, proxy, debug
trace, retry, replay, redirect, callback, or other call path exists.

After a call, enforce section 9 without retry, redaction, inference,
provisioning, mutation, or scope expansion. A non-recordable failure writes no
RFC. A recordable failure writes only its approved confirmation metadata when
its nonempty observed call ledger ends in the matching call; otherwise it
writes nothing. Every recordable failure still stops.

Stop before evidence publication if the diff includes another path or the
record contains anything outside the complete manifest allowlist. Stop before
merge unless E is unchanged, hosted checks pass on E, and two independent
external reviews of E report zero demonstrated in-scope Blockers.

Only the merged immutable record and its explicit dedicated-fixture-
organization limitation may be handed to PR #322. That handoff is evidence,
not authority.

## 15. Current disposition

- Reviewed base: bdf636d155e45ecbf4d9ac828e232bbcf91e1d59.
- Draft PR: [#323](https://github.com/samovers/OFARM2/pull/323).
- Predecessor reviewed Phase A head:
  21cfcb770038aff0846cca2710dd4b7c2be9f2a9.
- Formal [review 4985246172](https://github.com/samovers/OFARM2/pull/323#pullrequestreview-4985246172)
  reported zero demonstrated source-and-contract Blockers on that predecessor
  head. It did not reproduce live provider execution.
- The task user later approved decision version 1, but no Phase B evidence call
  occurred. The separately authorized version-1 and version-2 qualifications
  in section 5.6 returned four terminal HTTP 403 responses across their exact
  bounded call ledgers. Those results invalidated the predecessor request and
  reader-scope assumptions without producing evidence.
- This successor contract is proposed version 3. It retains the exact public
  quota-project header and adds fixtureOrganizationId, organization visibility
  in both expected allow explanations, organization-scoped Security Reviewer
  and Deny Reviewer on one dedicated ancestor-clean fixture organization, and
  a structural no-human, controlled-service-account, no-shared-organization
  publication gate. It requires separately authorized provisioning and a
  successful separately authorized replacement qualification before a live
  card.
- Version-1 approval and every predecessor review cannot authorize or review
  this successor source. The actual published successor head must be identified
  by the external PR description, pass hosted checks, and receive two new
  independent exact-head zero-Blocker reviews before a version-3 live card.
- Git and GitHub, rather than a self-referential claim inside this RFC, are
  authoritative for any successor published head and its review status. The PR
  description and external review objects must identify the actual remote head
  before that head is considered reviewed.
- Provider iam:troubleshoot calls under this decision: zero.
- External fixture-qualification calls: exactly four failed calls recorded in
  section 5.6; none is evidence and none authorizes a retry.
- Google/provider credentials used under decision version 3: none.
- Captured responses and observed attachment kinds: none.
- Decision version-3 approval and Phase B authority: absent.
- PR #322 authority changed: none.
- Primary trust-boundary scope: retained.
