# OFARM Security-Audit Observer-Root Admission — Phase A Contract v0.1

**Status:** Phase A draft bound to PR #321; independent exact-head review is
not yet complete; Phase B repository implementation, deployment, and production
operation are not authorized

**Draft pull request:** https://github.com/samovers/OFARM2/pull/321

**Contract identity:**
`ofarm2.security-audit-observer-root-admission.v0.1`

**Decision identity:**
`ISSUE192-SECURITY-AUDIT-OBSERVER-ROOT-ADMISSION-001`, version `1`

**Issue:** #192

**Reviewed base:** `ff3537870003d33a12a65b2ffba8545b28cde6c2`

**Primary trust boundary:** non-provisioning admission of one independently
provisioned Google Cloud KMS HSM Ed25519 observer root and its exact effective
IAM authorization evidence

**Phase A review-head boundary:** this RFC only

**Maximum prospective Phase B pull request boundary:** this RFC; one
library-only non-mutating observer-root admission module; focused tests; minimal
deployment documentation; exact architecture-check registration; and the
mechanically regenerated review-baseline test inventory only

## 1. Problem and goal

Merged PR #320 can issue a security-audit approver-authority receipt with one
composition-supplied observer KMS key version and can verify the returned
signature against one composition-supplied observer public key. It deliberately
does not establish that the configured key is the intended independent HSM
root, that its public key and attestation match a reviewed provisioning record,
or that the signer and metadata observer have only their intended effective IAM
authority.

Accepting resource names and public-key bytes directly from future runtime
configuration would therefore make configuration a self-asserted custody root.
Using Cloud KMS `testIamPermissions` would not close that gap: Google documents
that operation as a UI aid that may fail open and not as an authorization
check.

This task establishes one fail-closed, non-provisioning admission function that:

- accepts one strict canonical provisioning manifest from future trusted
  composition;
- pins one exact KMS CryptoKeyVersion, raw Ed25519 public key, externally
  verified attestation-bundle digest, two dedicated service-account principals,
  and three exact custom-role etags;
- observes the exact CryptoKey, CryptoKeyVersion, DER public key, custom-role
  definitions, and effective allow/deny explanations through separate
  read-only clients;
- requires one dedicated signer principal with only
  `cloudkms.cryptoKeyVersions.useToSign` on the exact version;
- requires one different observer principal with only the three metadata
  permissions needed to inspect that exact key and version;
- uses Policy Troubleshooter v3, not `testIamPermissions`, and refuses every
  incomplete, unknown, indirect, wider, or unexplained result;
- submits one fixed non-production-shaped raw-data signing probe and verifies
  the HSM response under the observed public key;
- collects the complete normalized key/IAM evidence both before and after the
  probe and requires semantic equality;
- bounds collection duration and returns a 30-second immutable admission value;
  and
- performs no cloud, IAM, database, filesystem, environment, or runtime
  mutation.

The result is evidence for a later composition decision. It does not load
production configuration, make the authority-receipt issuer ready, or authorize
any deployment.

## 2. Learning value

This slice proves that the security-audit observer root can be admitted from
independent, provider-backed evidence rather than a resource string and public
key asserting their own authority. It also validates a precise least-privilege
split among the signer, metadata observer, evidence reader, and administrator.

The demonstrated risk reduction is bounded and falsifiable: a broader inherited
grant, changed role definition, substituted public key, missing HSM attestation,
unknown Policy Troubleshooter result, or non-working exact key makes admission
refuse before any result can reach later runtime composition.

## 3. Non-goals

This pull request does not change or add:

- key-ring, CryptoKey, CryptoKeyVersion, service-account, custom-role, IAM
  binding, deny-policy, or principal-access-boundary creation or mutation;
- a provisioning command, Terraform, Pulumi, Config Connector, `gcloud`
  wrapper, deployment, credential mint, service-account impersonation, token
  exchange, or secret distribution path;
- cryptographic verification of a new HSM attestation bundle or downloading
  Google or Marvell trust roots; the manifest may pin only a bundle that an
  independent provisioning ceremony has already verified with the provider's
  supported procedure;
- selection, loading, approval, storage, rotation, or publication of the
  provisioning manifest;
- trusted wall-clock acquisition, NTP, runtime refresh scheduling, cache,
  daemon, endpoint, CLI, startup wiring, health, liveness, or readiness;
- authority-receipt issuance changes, approver-manifest loading, dual-approval
  verification changes, approver-key generation, approver custody, approval
  statements, or export requests;
- multi-root verification, automatic root rotation, overlapping roots,
  fallback keys, emergency root replacement, or compromise recovery;
- durable one-operation admission, replay state, database migration, relation,
  function, role, grant, transaction, or PostgreSQL call;
- temporary export-login creation, credentials, export execution, output
  recipient binding, encryption, protected delivery, or store-loss handling;
- tenant capability signing, tenant key custody, correlation-HMAC custody,
  authentication, principal resolution, tenant binding, authorization,
  RuntimeBundle, issue #172, issue #174, or issue #176 behavior;
- a claim that Policy Troubleshooter is a transaction, that absence of an IAM
  change is permanent, or that a 30-second result provides immediate
  revocation; or
- release, production access, issue #192 closure, or a security waiver.

## 4. Trust model

### 4.1 Protected assets

- identity of the one intended security-audit observer CryptoKeyVersion;
- equality between that version, its exact 32-byte Ed25519 public key, and the
  public key used by the authority-receipt verifier;
- equality between the currently returned HSM attestation bundle and the
  externally verified bundle pinned by the manifest;
- HSM-only, enabled, non-imported, raw-data Ed25519 signing posture;
- exclusive effective `useToSign` authority, at the KMS policy layer, of one
  dedicated signer service account on only the exact version;
- separation of that signer from one dedicated metadata-observer service
  account;
- exact effective metadata authority of the observer on only the exact key and
  version;
- exact definitions and etags of the three custom roles used by those
  bindings;
- complete visibility of relevant allow and deny policy explanations;
- fixed, non-production-shaped signing-probe bytes and exact HSM response
  validation;
- equality of the complete normalized before/after evidence snapshots;
- bounded collection duration and a fixed 30-second result lifetime;
- zero mutable or serializable authority hidden outside the returned frozen
  value;
- a fixed, non-sensitive refusal with no copied provider text; and
- absence of key, policy, database, filesystem, environment, process, logging,
  or runtime mutation.

### 4.2 Trusted components and actors

- the future trusted composition that supplies the exact canonical manifest,
  three independently authenticated read/sign clients, and one trusted clock
  callable;
- an independently accountable provisioning reviewer who has already verified
  the exact Cloud HSM attestation bundle and approved its pinned digest;
- the dedicated signer service account named in the manifest;
- the distinct dedicated metadata-observer service account named in the
  manifest;
- a separate evidence-reader credential with complete organization-level
  visibility needed by Policy Troubleshooter and IAM `roles.get`;
- a separate Google Cloud administrator that created the resources and can
  later change key state, role definitions, or IAM policy;
- Google Cloud KMS v1 authenticated metadata and signing behavior;
- Google IAM v1 custom-role responses and Policy Troubleshooter v3 allow/deny
  evaluation;
- authenticated TLS, Google-issued credentials, SHA-256, Ed25519, strict JSON,
  strict UTF-8, canonical base64 encodings, and CRC32C;
- `cryptography==49.0.0`, `google-api-core==2.33.0`,
  `google-auth==2.56.2`, `google-cloud-kms==3.16.0`, and
  `requests==2.34.2`, already hash-pinned by the repository; and
- Python immutable `bytes`, `str`, `int`, tuple, and frozen-dataclass behavior
  under the supported runtime.

The provisioning manifest is a bootstrap authority input. Its attestation
digest is accepted only as evidence that a separate review already verified
the provider bundle; this module does not turn the digest into proof of a
ceremony that did not occur. The later manifest loader and runtime composition
must establish where those exact approved bytes come from.

This admission proves which IAM principal the KMS policy authorizes. It does
not prove who can obtain that service account's credentials, whether a
user-managed service-account key exists, which workload has the account
attached, or whether an impersonation path exists. Those credential-custody
facts require concrete runtime/deployment identities that this PR deliberately
does not select. The later composition prerequisite must admit them before it
may treat this KMS/IAM result as production-ready root custody.

The administrator, evidence reader, signer, metadata observer, and future
composition are separate trust roots. Compromise of any current trust root is
not repaired by this library. The design reduces accidental widening,
substitution, incomplete evidence, and stale handoff; it does not claim to
survive arbitrary behavior by every root at once.

### 4.3 Untrusted inputs and behavior

- every manifest byte, JSON member, resource segment, principal, key, digest,
  role etag, order, encoding, and extra field until fully validated;
- every KMS metadata and public-key response field;
- every IAM role response, Policy Troubleshooter response, policy, binding,
  membership result, condition result, error, omission, order, and unknown
  state;
- every HTTP status, header, body byte, redirect, content encoding, size, JSON
  duplicate, and ordinary transport exception;
- every KMS signing response field, checksum, signature byte, resource name,
  protection level, and ordinary dependency exception;
- a changed, reordered, duplicated, deleted, disabled, alpha, beta, deprecated,
  or permission-widened custom role;
- direct or inherited policy grants to the expected principals through another
  role, group, domain, project, folder, or organization;
- missing evidence caused by insufficient evidence-reader privileges;
- key, role, or policy drift during the collection window;
- a clock returning malformed, decreasing, overflowing, or overlong interval
  values; and
- repeated calls and concurrent callers.

### 4.4 Explicitly excluded attacker capabilities

- arbitrary in-process memory mutation after a frozen result is returned;
- replacement of installed Python source, bytecode, interpreter, trusted
  dependencies, CA roots, or Google client libraries;
- arbitrary mutation inside an authenticated Google service response after TLS
  and client verification;
- compromise of the future composition that supplies different clients while
  falsely claiming they are the approved credentials;
- forged approval of the provisioning manifest or forged evidence that the
  pinned attestation bundle was independently verified;
- simultaneous compromise or collusion of the administrator, evidence reader,
  signer, observer, and runtime host;
- malicious hypervisor, Google Cloud control-plane, HSM firmware, SHA-256,
  CRC32C, Ed25519, or TLS failure; and
- filesystem or environment mutation, because Phase B reads neither.

Local source substitution, dependency compromise, arbitrary operator
compromise, and arbitrary in-process mutation are outside this slice. Ordinary
malformed provider responses, incomplete policy visibility, independently
reachable policy widening, credential misuse through the supported clients,
and between-call drift are in scope and must refuse.

## 5. Authority map

| Decision | Sole authority in this slice | Explicit non-authorities |
| --- | --- | --- |
| Intended key version | Exact canonical manifest member | KMS primary, latest version, response-selected name, environment, caller argument |
| Expected public key | Exact manifest raw-key member, compared with strict DER response | PEM, certificate, KMS response alone, signature alone, tenant key |
| Attestation identity | Manifest's digest of one externally verified complete bundle, compared with current KMS bundle | Protection-level enum alone, a presence boolean, self-issued digest, test fixture |
| Signer identity | Exact manifest service-account email | active credential metadata, group, domain, response member |
| Metadata-observer identity | Different exact manifest service-account email | signer, administrator, evidence reader |
| Role identity and definition | Three fixed role names plus exact manifest etags and exact permission sets | role title, description, predefined role, similarly named role |
| Effective access | Complete Policy Troubleshooter v3 response for each closed tuple | `testIamPermissions`, one direct policy read, one successful RPC, local assumption |
| Expected binding provenance | One exact direct service-account binding on the exact CryptoKey policy with exact role and condition | inherited, group, domain, wildcard, sibling, unconditioned, second grant |
| Key metadata | Exact authenticated KMS `GetCryptoKey`, `GetCryptoKeyVersion`, and DER `GetPublicKey` responses | manifest assertion alone, primary alias, cached value |
| Functional private-key match | One fixed probe signature independently verified with observed raw key | metadata, resource equality, CRC32C, attestation digest alone |
| Evidence stability | Semantic equality of complete normalized snapshots A and B | timestamp alone, etag alone, one snapshot |
| Observation time | Exactly two values from the supplied trusted clock callable | KMS time, IAM time, manifest time, local default clock |
| Admission output | One frozen value constructed only after every gate | partial result, exception details, logged state, serialized cache |

There is no legacy observer-root admission path to preserve. Phase B adds no
fallback, alias, mutable registry, latest-key selection, alternate manifest,
or second output constructor.

## 6. State, ordering, and exact protocol

### 6.1 Exact public interface

The future production module exports exactly:

```python
__all__ = (
    "SecurityAuditObserverRootAdmission",
    "SecurityAuditObserverRootAdmissionRefused",
    "admit_security_audit_observer_root",
)
```

Its only success type and supported entry point are:

```python
@dataclass(frozen=True, slots=True)
class SecurityAuditObserverRootAdmission:
    kms_key_version_resource: str
    observer_public_key: bytes
    signer_principal: str
    observer_principal: str
    attestation_bundle_sha256: bytes
    manifest_sha256: bytes
    snapshot_sha256: bytes
    evidence_sha256: bytes
    observed_at_unix_microseconds: int
    expires_at_unix_microseconds: int


def admit_security_audit_observer_root(
    *,
    manifest_bytes: bytes,
    observer_client: KmsObserverClient,
    signer_client: KmsSignerClient,
    evidence_session: EvidenceHttpSession,
    trusted_clock: TrustedClock,
) -> SecurityAuditObserverRootAdmission: ...
```

The four dependency types are module-private protocols. The observer protocol
contains only the callable surfaces used for `get_crypto_key`,
`get_crypto_key_version`, and `get_public_key`; the signer protocol contains
only `asymmetric_sign`; the evidence-session and response protocols contain
only the fixed bounded GET/POST and response surfaces in section 6.6; and the
clock protocol contains only a zero-argument `__call__`. Local validation
checks each required surface is callable without invoking it. The function
never discovers, returns, or invokes another dependency member.

The refusal is exactly:

```python
class SecurityAuditObserverRootAdmissionRefused(RuntimeError):
    pass
```

All four digest fields are exact 32-byte SHA-256 outputs. The attestation field
is the 32 bytes decoded from the manifest's lower-case hexadecimal member. All
other fields have the exact immutable built-in types shown; `bool` is not an
accepted `int`. The admission function is the only supported authority-
producing path; a caller-constructed dataclass, subclass, tuple, mapping, or
partially populated carrier has no contractual authority and must not cross an
untrusted boundary into future composition.

### 6.2 Closed constants and bounds

```text
MANIFEST_SCHEMA =
  "ofarm.security-audit-observer-root-admission-manifest.v1"

ATTESTATION_DIGEST_DOMAIN =
  b"OFARM2_SECURITY_AUDIT_OBSERVER_ROOT_ATTESTATION_V1\x00"

EVIDENCE_DIGEST_DOMAIN =
  b"OFARM2_SECURITY_AUDIT_OBSERVER_ROOT_EVIDENCE_V1\x00"

PROBE =
  b"\x00OFARM2-SECURITY-AUDIT-OBSERVER-ROOT-ADMISSION-V1\x00"

KMS_RPC_TIMEOUT_SECONDS = 5.0
HTTP_TIMEOUT_SECONDS = 5.0
MAX_COLLECTION_SPAN_MICROSECONDS = 180_000_000
ADMISSION_LIFETIME_MICROSECONDS = 30_000_000
MAX_UNIX_MICROSECONDS = 9_223_372_036_854_775_807
MAX_MANIFEST_BYTES = 8_192
MAX_HTTP_RESPONSE_BYTES = 1_048_576
MAX_ATTESTATION_CONTENT_BYTES = 262_144
MAX_CERTIFICATES_PER_CHAIN = 16
MAX_CERTIFICATE_BYTES = 32_768
```

`PROBE` is exactly 50 bytes with this hexadecimal encoding:

```text
004f4641524d322d53454355524954592d41554449542d4f425345525645522d524f4f542d41444d495353494f4e2d563100
```

Its leading NUL, distinct text, and trailing NUL prevent it from being parsed
as the authority-receipt issuer's production signature domain plus JSON
payload. Phase B has no probe argument and no caller-selected signing bytes.

### 6.3 Canonical manifest

The manifest carrier has exact Python type `bytes`, length 1 through 8,192,
strict UTF-8 with no byte-order mark, no duplicate member, no non-JSON
constant, exact root/member types, and exact byte-for-byte equality with:

```python
dumps(
    value,
    ensure_ascii=True,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("ascii")
```

It has exactly this shape:

```json
{
  "attestationBundleSha256": "<64-lowercase-hex>",
  "attestationFormat": "CAVIUM_V1_COMPRESSED",
  "kmsKeyVersionResource": "projects/example/locations/europe-west1/keyRings/ofarm/cryptoKeys/security-audit-observer/cryptoKeyVersions/1",
  "observerKeyRoleEtag": "<canonical-padded-standard-base64>",
  "observerPrincipal": "security-audit-observer@example.iam.gserviceaccount.com",
  "observerPublicKey": "<canonical-unpadded-base64url-of-32-bytes>",
  "observerVersionRoleEtag": "<canonical-padded-standard-base64>",
  "schemaVersion": "ofarm.security-audit-observer-root-admission-manifest.v1",
  "signerPrincipal": "security-audit-signer@example.iam.gserviceaccount.com",
  "signerRoleEtag": "<canonical-padded-standard-base64>"
}
```

`attestationFormat` is exactly one of `CAVIUM_V1_COMPRESSED` or
`CAVIUM_V2_COMPRESSED` and must equal the KMS response. The selected format is
pinned per manifest; there is no fallback between them.

Each role etag decodes from canonical padded standard base64 to 1 through 128
bytes and re-encodes byte-identically. `observerPublicKey` decodes from
canonical unpadded base64url to exactly 32 bytes and must construct as an
Ed25519 public key. The attestation digest is exactly 64 lowercase hexadecimal
characters.

Both principals use this exact lower-case ASCII service-account grammar and
differ byte-for-byte:

```text
^[a-z][a-z0-9-]{4,28}[a-z0-9]@
[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$
```

The displayed line break is presentation only. User, group, domain, workforce,
workload-identity, principal-set, `allUsers`, and `allAuthenticatedUsers`
identities refuse.

The KMS version resource uses the exact grammar already frozen by the merged
authority issuer:

```text
^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/
locations/[a-z0-9](?:[a-z0-9-]*[a-z0-9])?/
keyRings/[A-Za-z0-9_-]{1,63}/
cryptoKeys/[A-Za-z0-9_-]{1,63}/
cryptoKeyVersions/[1-9][0-9]*$
```

The displayed line breaks are presentation only. The parent CryptoKey,
project ID, REST URLs, full resource names, three custom-role names, and all IAM
conditions are derived from that one value. No carrier repeats or overrides
them.

### 6.4 Fixed roles and conditions

For key project `PROJECT_ID`, the exact custom-role names are:

```text
projects/PROJECT_ID/roles/ofarmSecurityAuditObserverRootSignerV1
projects/PROJECT_ID/roles/ofarmSecurityAuditObserverRootVersionReaderV1
projects/PROJECT_ID/roles/ofarmSecurityAuditObserverRootKeyReaderV1
```

Their complete `includedPermissions` sets are respectively:

```text
{cloudkms.cryptoKeyVersions.useToSign}

{cloudkms.cryptoKeyVersions.get,
 cloudkms.cryptoKeyVersions.viewPublicKey}

{cloudkms.cryptoKeys.get}
```

Every role response must have its exact derived name, exact sorted permission
set, `stage == "GA"`, `deleted == false`, and the exact manifest etag. Missing,
empty, malformed, alpha, beta, deprecated, disabled, deleted, or differently
permissioned definitions refuse. Role title and description carry no
authority, but their exact returned values are included in snapshot equality
and the evidence digest so a concurrent change cannot pass unnoticed.

IAM policy attaches to the parent CryptoKey. The signer and version-reader
bindings each contain exactly one direct service-account member and use this
exact expression after substitution:

```text
resource.type == "cloudkms.googleapis.com/CryptoKeyVersion" &&
resource.name == "EXACT_KMS_KEY_VERSION_RESOURCE"
```

The key-reader binding contains exactly the observer service-account member and
uses:

```text
resource.type == "cloudkms.googleapis.com/CryptoKey" &&
resource.name == "EXACT_PARENT_CRYPTO_KEY_RESOURCE"
```

The expressions are exact single-line ASCII strings in implementation; the
line breaks above are display only. The exact condition titles are,
respectively:

```text
ofarm-security-audit-observer-root-signer-v1
ofarm-security-audit-observer-root-version-reader-v1
ofarm-security-audit-observer-root-key-reader-v1
```

A condition description is non-authoritative but included in the snapshot.

The signer appears directly only in the signer binding. The observer appears
directly only in the two reader bindings. Any second matching direct or
indirect membership through any policy in the resource hierarchy refuses even
if the extra role appears read-only, a deny policy currently masks it, or the
queried permission is not included in that role.

No other binding in any returned resource or ancestor policy may grant a role
that includes `cloudkms.cryptoKeyVersions.useToSign`, regardless of its member,
condition, or current deny result. This intentionally requires a dedicated key
hierarchy with one cryptographic signer; a project Owner, crypto operator,
second service account, group, domain, or condition for a sibling version is
not an acceptable latent signer. A separate administrator role may retain key
and IAM mutation permissions only when that role contains no signing
permission.

Other bindings for other principals are permitted only when their role does
not include `useToSign`. They remain part of the complete normalized policy
snapshot; a change to them between snapshots A and B refuses the call rather
than mixing evidence from two policy states.

### 6.5 KMS metadata observation

Each snapshot makes exactly these non-retried KMS calls through the dedicated
observer client, each with timeout `5.0`:

1. `GetCryptoKey` for the exact derived parent CryptoKey;
2. `GetCryptoKeyVersion` for the exact manifest version; and
3. `GetPublicKey` for the exact version with `public_key_format = DER`
   explicitly set.

The CryptoKey response must have the exact name, purpose
`ASYMMETRIC_SIGN`, `import_only == false`, no rotation period or next-rotation
time, and a version template with algorithm `EC_SIGN_ED25519` and protection
level `HSM`. Its `primary` field must be absent, as required by the provider
contract for a non-`ENCRYPT_DECRYPT` key. No alias or response-selected version
becomes authority.

The CryptoKeyVersion response must have the exact name, state `ENABLED`,
algorithm `EC_SIGN_ED25519`, protection level `HSM`, `reimport_eligible ==
false`, no import job or import time, and one present attestation in the exact
manifest format. Attestation content is non-empty and bounded. Each of the
three ordered certificate chains is non-empty, has at most 16 members, and each
strict UTF-8 PEM member is 1 through 32,768 bytes. The complete bundle is
canonicalized without reordering and hashed as:

```text
SHA-256(
  ATTESTATION_DIGEST_DOMAIN ||
  canonical_json({
    "caviumCerts": [...],
    "content": "<canonical-padded-standard-base64>",
    "format": "<exact-format>",
    "googleCardCerts": [...],
    "googlePartitionCerts": [...]
  })
)
```

Every `canonical_json` use in this contract uses the exact `dumps` settings in
section 6.3 and ASCII encoding; no whitespace, locale, alternate member order,
or serializer option is accepted.

That lowercase digest must equal `attestationBundleSha256`. This equality
proves that the live provider bundle is the independently reviewed bundle. It
does not replace certificate-chain, attestation-signature, key-ID,
non-extractability, or generated-in-HSM verification during provisioning.

The public-key response must have exact response type, name, algorithm
`EC_SIGN_ED25519`, protection level `HSM`, format `DER`, no PEM representation,
present `public_key.data`, and present uint32 CRC32C equal to the exact DER
bytes. The DER is exactly this 44-byte RFC 8410 SubjectPublicKeyInfo shape:

```text
30 2a 30 05 06 03 2b 65 70 03 21 00 || K
```

`K` is exactly 32 bytes and must equal the manifest public key. No general ASN.1
parser, PEM fallback, alternate OID, present parameters, trailing byte,
certificate, PKCS#8 value, or response-selected key is accepted. CRC32C is
transport-integrity evidence only.

These successful metadata reads prove that the supplied observer client can
reach the exact resources. Like the signer probe, they do not prove how future
composition obtained that client's credential or that it is the manifest-named
observer principal. Policy Troubleshooter establishes the named principal's
authorization; the later credential-custody prerequisite must bind the actual
client identity.

### 6.6 HTTP transport and role observation

The evidence client is a future composition-supplied authenticated HTTP
session using the independent evidence-reader credential. Phase B invokes only:

```text
GET https://iam.googleapis.com/v1/<exact-derived-role-name>
POST https://policytroubleshooter.googleapis.com/v3/iam:troubleshoot
```

Every request has fixed timeout `5.0`, permits no redirect, supplies no query
parameter except those fixed by the endpoint, and uses a bounded streaming
response. Success requires status 200, JSON content type, at most 1,048,576
decoded body bytes, strict UTF-8, no byte-order mark, no duplicate object
member, no non-JSON constant, and the exact response type/member rules in this
contract. Provider error text never reaches the public refusal.

After the three KMS reads, each snapshot fetches the signer, observer-version,
and observer-key role definitions in that fixed order. No list, wildcard,
search, project discovery, environment-derived host, alternate endpoint, or
`testIamPermissions` call exists.

### 6.7 Effective-IAM tuple matrix

For Policy Troubleshooter, the email form without a `serviceAccount:` prefix is
the `principal` request value. `fullResourceName` is exactly the KMS resource
prefixed by `//cloudkms.googleapis.com/`. The request body has only one exact
`accessTuple` and is strict canonical JSON. Because every expected binding uses
`resource.type` and `resource.name`, the tuple supplies this exact condition
context for a version query:

```json
{
  "resource": {
    "name": "EXACT_KMS_KEY_VERSION_RESOURCE",
    "service": "cloudkms.googleapis.com",
    "type": "cloudkms.googleapis.com/CryptoKeyVersion"
  }
}
```

For a key query, `name` is the exact parent CryptoKey resource and `type` is
`cloudkms.googleapis.com/CryptoKey`; `service` is unchanged. No destination,
request time, tag, caller-selected context, or other condition-context input is
sent. Omitting or changing this resource context is not permitted: it could
turn the exact expected conditional binding into `UNKNOWN_CONDITIONAL` or
evaluate a different resource.

Each snapshot then evaluates this closed matrix in displayed top-to-bottom
order:

| Principal | Resource | Permission | Required overall state |
| --- | --- | --- | --- |
| signer | exact version | `cloudkms.cryptoKeyVersions.useToSign` | `CAN_ACCESS` |
| signer | exact version | `cloudkms.cryptoKeyVersions.get` | `CANNOT_ACCESS` |
| signer | exact version | `cloudkms.cryptoKeyVersions.update` | `CANNOT_ACCESS` |
| signer | exact version | `cloudkms.cryptoKeyVersions.destroy` | `CANNOT_ACCESS` |
| signer | exact key | `cloudkms.cryptoKeys.setIamPolicy` | `CANNOT_ACCESS` |
| observer | exact version | `cloudkms.cryptoKeyVersions.get` | `CAN_ACCESS` |
| observer | exact version | `cloudkms.cryptoKeyVersions.viewPublicKey` | `CAN_ACCESS` |
| observer | exact key | `cloudkms.cryptoKeys.get` | `CAN_ACCESS` |
| observer | exact version | `cloudkms.cryptoKeyVersions.useToSign` | `CANNOT_ACCESS` |
| observer | exact key | `cloudkms.cryptoKeys.setIamPolicy` | `CANNOT_ACCESS` |

Every response must repeat the exact principal, full resource name, permission,
and resource condition context. Its output-only permission FQDN and effective
tags must be well-formed and are included in snapshot equality. `UNKNOWN_INFO`,
`UNKNOWN_CONDITIONAL`, an unspecified enum, an error, missing policy text,
missing full resource name, missing binding explanation, unknown role
permission, unknown membership, null or erroneous condition evaluation, or an
unexplained overall result refuses.

For every `CAN_ACCESS` tuple, allow state is exactly granted, deny state is
exactly not denied, and exactly one expected binding explains the grant. Its
role, direct singleton member, condition title/expression, permission-inclusion
state, combined membership, direct membership, and evaluated condition are all
exact and positive.

For every `CANNOT_ACCESS` tuple, allow state is exactly not granted or deny
state is exactly denied, with no unknown component. The complete binding roster
is still inspected. A forbidden extra matching grant refuses even when a deny
currently makes the overall state `CANNOT_ACCESS`; least privilege may not rely
on a masking deny. The positive signer query also inspects every binding's role
permission result and refuses every second role that includes `useToSign`, even
when its membership or condition would not grant the queried signer access.

Across the complete policies returned for all tuples, the only binding whose
membership matches the signer is the exact signer binding. The only bindings
whose membership matches the observer are the exact two reader bindings. Every
resource, policy version, etag, audit configuration, binding, member,
condition, explanation, role, and relevant enum is normalized with deterministic
ordering and included in the snapshot. No digest substitutes for validating
the underlying values first.

Policy Troubleshooter is authoritative here because v3 evaluates relevant
resource and inherited allow and deny policies and reports incomplete
visibility as unknown. The design does not infer authority from
`testIamPermissions`, a successful KMS call, or direct policy text alone.

### 6.8 Fixed live signing probe

After snapshot A passes, Phase B constructs exactly:

```python
kms_v1.AsymmetricSignRequest(
    name=exact_kms_key_version_resource,
    data=PROBE,
    data_crc32c=crc32c(PROBE),
)
```

It invokes the dedicated signer client exactly once:

```python
client.asymmetric_sign(
    request=request,
    retry=None,
    timeout=5.0,
)
```

The digest fields remain unset. There is no caller message, prehash, retry,
fallback, second key, second signature, production authority-receipt payload,
or database call.

The exact response must be `AsymmetricSignResponse` with the exact key-version
name, protection level `HSM`, `verified_data_crc32c is True`,
`verified_digest_crc32c is False`, an exact 64-byte signature, and an exact
uint32 signature CRC32C. The observed Ed25519 public key independently verifies
the signature over the exact 50 probe bytes before collection proceeds.

This proves that the configured signer client can reach a functioning private
key matching the admitted public key. Policy Troubleshooter remains authority
for the named principal's effective IAM. The probe cannot prove that a
malicious future composition supplied the intended signer credential; client
selection is explicitly that later composition's authority.

### 6.9 Double collection and currentness

The complete transition is:

```text
UNVALIDATED
  -> validate client surfaces, clock surface, and exact manifest locally
  -> READY
  -> clock call 1: STARTED
  -> collect and validate snapshot A
  -> one fixed signing probe
  -> collect and validate snapshot B
  -> clock call 2: FINISHED
  -> validate 0 <= STARTED <= FINISHED
  -> validate FINISHED - STARTED <= 180_000_000
  -> require normalized snapshot A == normalized snapshot B
  -> construct evidence digest and frozen admission
  -> RETURNED
```

The clock returns exact non-boolean Python `int` microseconds. Both values lie
from zero through `MAX_UNIX_MICROSECONDS`; all range checks occur before
subtraction or addition. `FINISHED + 30_000_000` must not overflow. The result
has:

```text
observed_at_unix_microseconds = FINISHED
expires_at_unix_microseconds = FINISHED + 30_000_000
```

Every returned admission has exactly two supplied-clock calls, and no
invocation can make more than two. The module never calls a default system
clock. A malformed first value makes zero network calls. An ordinary failure
during snapshot A, the probe, or snapshot B stops at that exact ordered prefix
and therefore has one clock call. A malformed second value refuses after
observation without returning partial evidence.

Snapshot equality is semantic, not raw response-byte equality. It covers every
validated KMS field, exact public key, attestation bundle, custom-role field,
complete IAM policy and binding roster, access decision, and explanation.
Response object ordering that has no IAM meaning is normalized; values and
list order with protocol meaning are not discarded.

The normalized snapshot is one closed canonical-JSON object with exactly these
top-level members:

```json
{
  "accessEvaluations": [],
  "cryptoKey": {},
  "cryptoKeyVersion": {},
  "publicKey": {},
  "roles": []
}
```

`cryptoKey`, `cryptoKeyVersion`, and `publicKey` contain every field validated
in section 6.5 under its documented lower-camel JSON name; attestation format,
content, and all three certificate chains remain nested under
`cryptoKeyVersion.attestation`. `roles` contains the three complete validated
role objects in fixed request order. `accessEvaluations` contains the ten full
validated v3 responses in matrix order, including the repeated access tuple,
allow explanation and complete policy text, deny explanation and complete
policy text, all binding/rule explanations, and overall access state.

Provider byte fields use canonical padded standard base64, enum values use
their exact documented names, and integers remain JSON integers. Semantically
unordered maps, members, permissions, audit configurations, policy rosters,
and binding/rule rosters use deterministic canonical-value sort order;
provider-defined certificate-chain order is preserved. No validated response
timestamp, etag, condition result, membership result, policy member, or other
validated authority field is omitted from equality or hashing.

The digest inputs are exact:

```text
MANIFEST_SHA256 = SHA-256(exact_manifest_bytes)
SNAPSHOT_SHA256 = SHA-256(canonical_json(equal_normalized_snapshot))
PROBE_REQUEST_SHA256 = SHA-256(canonical_json({
  "data": "<canonical-unpadded-base64url-of-PROBE>",
  "dataCrc32c": <exact-uint32>,
  "name": "<exact-key-version-resource>"
}))
PROBE_SIGNATURE_SHA256 = SHA-256(exact_64_byte_signature)
```

`EVIDENCE_SHA256` is SHA-256 over `EVIDENCE_DIGEST_DOMAIN` followed by this
exact canonical JSON object, with every digest encoded as 64 lower-case
hexadecimal characters:

```json
{
  "expiresAtUnixMicroseconds": 0,
  "manifestSha256": "<MANIFEST_SHA256>",
  "observedAtUnixMicroseconds": 0,
  "probeRequestSha256": "<PROBE_REQUEST_SHA256>",
  "probeSignatureSha256": "<PROBE_SIGNATURE_SHA256>",
  "snapshotSha256": "<SNAPSHOT_SHA256>",
  "startedAtUnixMicroseconds": 0
}
```

The displayed zeroes are replaced by the exact derived expiry, `FINISHED`, and
`STARTED` values respectively. The frozen result contains the exact version,
raw public key, principals, raw attestation digest, raw manifest digest, raw
snapshot digest, raw evidence digest, observed time, and expiry. It contains no
credential, session, client, policy body, certificate, raw attestation, probe
signature, or mutable collection.

A successful result says only that both observations agreed and the exact key
worked during this bounded call. Google IAM and key state can change after
`FINISHED`. Later runtime composition must reject at expiry and refresh; this
slice neither implements that composition nor claims immediate revocation.

### 6.10 Failure and side-effect protocol

Every ordinary constructor, parser, transport, provider, metadata, role,
policy, condition, time, checksum, key, or signature failure becomes one newly
created `SecurityAuditObserverRootAdmissionRefused()` outside the active
exception handler. It has empty `str(exc)`, empty `exc.args`, no copied field,
and no explicit cause. `BaseException` subclasses propagate unchanged.

The only permitted external effects are prefixes of this order:

- clock call 1;
- snapshot A's three read-only KMS calls, three IAM role GETs, and ten Policy
  Troubleshooter POSTs;
- one KMS signing probe;
- snapshot B's same read-only calls;
- clock call 2; and
- no other effect.

Invalid local configuration makes no external call. The module itself emits no
file, environment, database, application log, metric, trace, stdout, stderr,
cache, registry, secret, key, role, policy, process, socket outside the supplied
clients, or serialized admission artifact. Authenticated client internals and
provider-side access or audit records caused by the enumerated calls remain
trusted external-service behavior; they are neither suppressed nor consumed as
admission evidence. Phase B contains no executable module and no
`if __name__ == "__main__"` path.

### 6.11 External protocol basis

The Google Cloud KMS
[`getPublicKey`](https://cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/getPublicKey)
and
[`asymmetricSign`](https://cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/asymmetricSign)
references define the exact-version public-key/signing calls, DER response,
CRC32C fields, raw-data input, response identity, verification flags, and
protection level used here. The
[`CryptoKeyVersion` resource](https://cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions)
defines enabled state, algorithm, HSM protection, import fields, and the HSM
attestation bundle.

Google's
[`Verifying attestations`](https://cloud.google.com/kms/docs/attest-key)
guide establishes that complete cryptographic attestation verification needs
the signed statement and certificate chains; it is the required external
provisioning procedure, not a boolean invented by this module.

The IAM
[`roles.get`](https://cloud.google.com/iam/docs/reference/rest/v1/projects.roles/get)
reference defines the exact custom-role name, included permissions, stage,
etag, and deletion fields. Policy Troubleshooter
[`iam.troubleshoot` v3](https://cloud.google.com/policy-intelligence/docs/reference/policytroubleshooter/rest/v3/iam/troubleshoot)
defines complete inherited allow/deny evaluation and the `CAN_ACCESS`,
`CANNOT_ACCESS`, `UNKNOWN_INFO`, and `UNKNOWN_CONDITIONAL` states. Google's
[`ConditionContext` resource fields](https://cloud.google.com/policy-intelligence/docs/reference/policytroubleshooter/rest/v3/iam/troubleshoot#conditioncontext)
define the exact `resource.name`,
`resource.service`, and `resource.type` inputs needed to evaluate the fixed IAM
conditions rather than producing an unknown conditional result. Google's
[`testIamPermissions`](https://cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys/testIamPermissions)
reference explicitly says that method is not for authorization checking and
may fail open, which is why it is prohibited as evidence.

These sources establish provider protocol facts. The exact roles, conditions,
tuple matrix, double collection, probe, strict canonical forms, limits,
30-second lifetime, and refusal policy are OFARM decisions.

## 7. Stable invariants and acceptance criteria

### `ORA-001` — one manifest-pinned root

One call accepts one canonical manifest that pins one exact key version, raw
public key, attestation bundle digest and format, two distinct service-account
principals, and three role etags. No provider response or call argument can
replace them.

### `ORA-002` — exact HSM Ed25519 metadata

Both snapshots require the exact CryptoKey and CryptoKeyVersion identities,
asymmetric-sign purpose, `EC_SIGN_ED25519`, `HSM`, enabled state, no rotation,
no primary field, no import posture, and the complete bounded attestation
bundle.

### `ORA-003` — exact public-key extraction

Both explicit DER responses have correct resource, algorithm, format,
protection, CRC32C, exact 44-byte RFC 8410 shape, and the same 32-byte key as
the manifest. PEM or parser normalization never supplies authority.

### `ORA-004` — independently reviewed attestation identity

The complete current attestation format, content, and ordered certificate
chains hash to the exact manifest digest in both snapshots. Presence or HSM
metadata alone never substitutes for the externally verified pinned bundle.

### `ORA-005` — closed role definitions

The three project custom roles have exact derived names, exact permission sets,
GA state, non-deleted state, and exact manifest etags in both snapshots.

### `ORA-006` — exact direct and exclusive authorization bindings

The signer has exactly one matching direct binding and the observer exactly two,
all on the exact CryptoKey policy with singleton service-account membership,
fixed roles, exact resource conditions, and successful condition evaluation.
No other direct or inherited membership for either principal is accepted, and
no second binding in the applicable hierarchy may carry a role containing
`useToSign` for any principal.

### `ORA-007` — complete effective allow/deny evidence

Every closed Policy Troubleshooter v3 tuple has the required overall state,
complete visible policies and explanations, and no unknown, omitted, erroneous,
or unexplained component. Every request includes the exact derived resource
condition context; `testIamPermissions` is never called or consumed.

### `ORA-008` — signer least privilege

The signer can use only `useToSign` on the exact version within the admitted
KMS hierarchy and cannot observe metadata, mutate the version, destroy it, or
change key IAM through any accepted binding.

### `ORA-009` — observer separation and least privilege

The distinct observer can get only the exact key and exact version metadata and
view only that public key through the accepted bindings. It cannot sign or
change key IAM.

### `ORA-010` — one fixed non-production probe

After snapshot A and before snapshot B, exactly one non-retried KMS call signs
only the fixed 50-byte probe through raw `data` with exact CRC32C and timeout
5.0. Digest, caller message, fallback, and production-shaped signing are absent.

### `ORA-011` — complete HSM response and key match

Probe success requires the exact response type/name, HSM level, verification
flags, 64-byte signature, uint32 signature CRC32C, and independent Ed25519
verification under the observed manifest-equal key.

### `ORA-012` — stable bounded evidence window

A returned admission requires exactly two supplied-clock calls. No invocation
makes more than two. The successful interval is nonnegative and at most 180
seconds; normalized snapshots A and B are equal; and result expiry is exactly
30 seconds after the second observation.

### `ORA-013` — immutable minimal output

Only one frozen admission value is returned after all gates, with exact
identities, digests, and times and without clients, credentials, policies,
attestation bytes, certificates, or mutable members.

### `ORA-014` — fixed refusal and no partial authority

Every ordinary failure returns no value and becomes one fresh empty refusal
without provider text or explicit cause. `BaseException` propagates. No partial
snapshot, signature, digest, or manifest becomes authority.

### `ORA-015` — non-mutating isolated boundary

Phase B has only the enumerated clock, read, troubleshoot, and fixed-probe
effects. It makes no resource/IAM/database/filesystem/environment/runtime
mutation and imports no tenant, approver, HMAC, database, export, or issuer
authority.

### `ORA-016` — exact repository envelope

Phase A changes only this RFC. Prospective Phase B changes only the six exact
paths in section 11, adds no dependency, executable, migration, credential,
fixture secret, test-line-cap change, group-budget change, or lockfile change,
and passes every named verification gate.

## 8. Production-reachable negative cases

| Invariant | Supported entry point and counterexample | Required result |
| --- | --- | --- |
| `ORA-001` | Future composition calls admission with noncanonical JSON, a sibling version, repeated role name, equal principals, 31-byte key, changed etag, or extra member. | Refuse before the first clock or network call. |
| `ORA-002` | Observer client returns a software, disabled, imported, rotating, primary-bearing, wrong-purpose, wrong-algorithm, or differently named key/version. | Refuse; no probe and no admission. |
| `ORA-003` | `GetPublicKey` returns PEM, unspecified format, wrong name, wrong CRC, alternate DER, trailing byte, or another raw key. | Refuse before IAM evidence can become output. |
| `ORA-004` | KMS returns a missing chain, oversized content, different format, reordered certificate chain, or bundle whose digest was not approved. | Refuse; HSM enum alone does not pass. |
| `ORA-005` | IAM `roles.get` returns a changed etag, adds `destroy`, omits `get`, reports beta/disabled/deleted, or names an organization/predefined role. | Refuse the snapshot. |
| `ORA-006` | Policy Troubleshooter shows an unconditional project grant, group-derived signer membership, a second read-only observer binding, multiple members in the expected binding, a prefix condition, or another principal/role able to sign the exact key. | Refuse even if all positive tuples say `CAN_ACCESS`. |
| `ORA-007` | A request omits or changes the derived resource condition context, or the evidence reader lacks an ancestor policy or role permission and v3 returns `UNKNOWN_INFO`, missing policy text, null condition value, or an error. | Refuse; never substitute `testIamPermissions` or a KMS success. |
| `ORA-008` | Signer is also granted KMS admin at the folder, while a deny currently blocks `destroy`. | Refuse the extra matched binding despite the negative tuple. |
| `ORA-009` | Observer gains `useToSign`, set-IAM authority, or the signer role through another binding. | Refuse; role separation cannot be masked by a deny. |
| `ORA-010` | Supported admission call reaches a fake signer that records a digest request, different bytes, retry object, second call, changed resource, or timeout. | Refuse and tests prove the exact one-call contract. |
| `ORA-011` | HSM response has matching metadata and CRC but a signature from another Ed25519 key, wrong flags, wrong name, or 63 bytes. | Refuse without output. |
| `ORA-012` | Policy changes after snapshot A, role description changes, key disables, clock decreases, interval exceeds 180 seconds, or expiry addition overflows. | Refuse; unequal snapshots or invalid time never return admission. |
| `ORA-013` | Caller attempts to obtain a policy body, client, mutable list, raw attestation, or certificate from a successful result. | The frozen public type has no such field. |
| `ORA-014` | HTTP raises a detailed credential exception or KMS raises after the probe transition; a `KeyboardInterrupt` canary is also injected. | Ordinary error becomes fresh empty refusal; canary propagates. |
| `ORA-015` | A proposed implementation reads an env var, opens a file, logs a policy, calls `setIamPolicy`, updates a key, imports authority issuer code, or adds `__main__`. | Architecture conformance fails. |
| `ORA-016` | Phase B diff adds a seventh path, dependency, lockfile, test cap, group budget, migration, CLI, Terraform, or generated credential. | Mechanical path/envelope gate fails and merge stops. |

All counterexamples enter through the proposed public admission function and
its supported client/clock protocols. Tests use deterministic fakes at those
public boundaries, not private-field mutation or impossible runtime state.

## 9. Proposed architecture and smallest coherent change

### 9.1 One production module

`deployment/postgresql/security_audit_observer_root_admission.py` owns:

- one empty public refusal type;
- one frozen `SecurityAuditObserverRootAdmission` result;
- small typed protocols for the KMS observer client, KMS signer client,
  authenticated evidence HTTP session, bounded HTTP response, and clock;
- strict manifest, resource, service-account, base64, digest, DER, CRC32C, and
  time validation;
- exact KMS request/response validators;
- bounded role and Policy Troubleshooter v3 JSON transport/parsing;
- normalized complete snapshot construction and equality;
- the fixed probe and independent Ed25519 verification; and
- one public `admit_security_audit_observer_root(...)` function.

The public function accepts exactly the canonical manifest bytes, observer KMS
client, signer KMS client, evidence HTTP session, and trusted clock callable.
It has no optional authority bag, defaults, `Any`-typed client, global registry,
environment lookup, file path, callback that selects a resource, or
caller-supplied probe.

Protocol fakes are test-only. Production imports no tenant contract, tenant
signer, security-audit authority issuer, approver verifier, HMAC module,
database adapter, or runtime composition.

### 9.2 Data flow

```text
canonical reviewed manifest
  -> strict local parse and derived identities
  -> trusted clock STARTED
  -> observer KMS metadata/public-key snapshot A
  -> evidence-reader role/effective-IAM snapshot A
  -> fixed probe through signer client
  -> observer KMS metadata/public-key snapshot B
  -> evidence-reader role/effective-IAM snapshot B
  -> trusted clock FINISHED
  -> duration + semantic equality + digest
  -> one frozen 30-second admission
```

Future runtime composition may consume only that bound result, not its
correlated constructor inputs. That later work must verify unexpired time and
bind the same exact key/public key into issuer and verifier construction.

### 9.3 Why this is the smallest coherent solution

KMS metadata alone cannot establish IAM least privilege. Direct IAM policy text
alone omits inherited allow and deny evaluation. Policy Troubleshooter alone
does not prove that the private key works or that its public key matches the
manifest. A successful signing call alone does not show the named principal's
complete effective authority. One snapshot cannot detect ordinary drift across
the probe. `testIamPermissions` is explicitly unsuitable for authorization
evidence.

The proposed module is therefore the minimum unit that binds all four facts:
reviewed root identity, exact live KMS material, complete effective IAM, and
functional private-key possession. Splitting any one into a later PR would
return a partial admission that future composition could misuse.

The module deliberately does not create the resources or load the manifest.
Those acts hold different mutation and runtime-composition authorities and are
separated under the workspace trust-boundary policy.

## 10. Elegance audit

### 10.1 Sources of truth and transitions

- one manifest is authority for expected identity;
- one KMS version is authority for live key material;
- one complete Policy Troubleshooter/role snapshot is authority for effective
  IAM at each observation;
- one fixed probe establishes private-key/public-key function;
- one clock callable supplies exactly two time observations; and
- one public function has the sole transition to a frozen admission.

There is one output constructor and no alternate success path.

### 10.2 Duplication and compatibility

The KMS resource grammar, strict Ed25519 SPKI prefix, CRC32C, and raw-signing
response checks deliberately reproduce already frozen protocols without
importing tenant or issuer authority. Tests compare shared vectors and request/
response behavior with existing implementations; production code remains
independent.

No compatibility alias, manifest version fallback, PEM parser, role-name
option, endpoint option, default clock, mutable cache, or legacy result remains.

### 10.3 Abstractions and deletion

The client protocols exist only to state the authenticated external surfaces
and permit deterministic tests. No framework, provider registry, generic
policy engine, abstract evidence graph, or reusable HTTP SDK is introduced.

There is no old observer-root admission code to delete. A clean new module is
safer than modifying the merged authority issuer because root admission and
receipt issuance are separate trust boundaries with different effects.

## 11. Pull request boundary

### 11.1 Primary boundary

The one primary boundary is non-provisioning KMS key and effective-IAM
authorization admission for the security-audit observer root.

Tests, minimal documentation, exact architecture registration, and the
mechanical test inventory travel with that boundary. No other authority or
custody change may enter the PR.

### 11.2 Exact prospective Phase B allowlist

Phase B may change only these six paths:

1. `docs/rfcs/OFARM_Security_Audit_Observer_Root_Admission_RFC_v0_1.md`
2. `deployment/postgresql/security_audit_observer_root_admission.py`
3. `deployment/postgresql/README.md`
4. `kernel/tests/test_security_audit_observer_root_admission.py`
5. `conformance/rewrite_architecture_check.py`
6. `conformance/review_baseline_test_inventory.json`

Path 1 is the approved contract and later evidence record. Path 2 is the only
production code. Path 3 documents only the non-mutating admission and explicit
non-readiness. Path 4 contains focused deterministic tests. Path 5 registers
the exact module budget, direct-import boundary, prohibited side effects,
fixed probe/KMS/HTTP surfaces, and test glob without changing shared test-line
or function limits. Path 6 is mechanical output only.

The production module's architecture budget must equal its finished physical
line count and be at most 700 lines. The focused test remains under the existing
800-line per-test-file cap. No group budget, shared cap, dependency, lockfile,
Dockerfile, workflow, migration, command module, or seventh path may change.

### 11.3 Dependencies and ordering

- Merged PR #319 provides the dual-approval verifier and its exact observer
  public-key trust root.
- Merged PR #320 provides the authority-receipt issuer and fixes the production
  composition prerequisite this slice addresses.
- This PR branches from merge commit
  `ff3537870003d33a12a65b2ffba8545b28cde6c2`.
- No unmerged pull request is a code dependency.

Later trusted manifest/time loading and issuer/verifier runtime composition may
assume only the frozen result shape and invariants merged here. They may not
reach through it to reuse raw clients or partial evidence.

### 11.4 Ordered follow-ups, not scope expansion

1. A separate signer-credential and runtime-integration/readiness PR names the
   exact workload identity, proves there is no unaccounted user-managed
   service-account key, impersonation, token-creation, attachment, or alternate
   credential path, loads one approved manifest, constructs the independent
   clients and trusted clock, refreshes this admission, rejects it at expiry,
   binds its exact root into both issuer and verifier, and requires at least two
   usable approvers in two independence domains. If credential custody and
   runtime integration cannot remain one primary boundary, they must be two
   ordered PRs rather than one mixed PR.
2. A separate root-rotation and compromise-response decision defines manifest
   replacement, old/new handoff, revocation latency, and hostile evidence.
3. The already recorded #192 sequence then continues with durable
   one-operation admission, temporary export-login lifecycle, protected output
   delivery, store-loss handling, and final hostile closure evidence.

Actual cloud provisioning and IAM writes remain administrator acts requiring
separate deployment authority. They are not repository Phase B effects.

Reviewers must not require runtime wiring, cloud mutation, approver custody,
database admission, credentials, export execution, delivery, root rotation, or
issue closure from this PR. A demonstrated need to edit those boundaries stops
this PR and becomes a separate prerequisite or follow-up.

## 12. Provisional design record

Not provisional.

The 30-second admission is an explicit security property, not a temporary
cache guess. The pre-deployment AI-assisted approval workflow governing
repository implementation is separately provisional and never authorizes
deployment.

A future provider protocol change that removes complete v3 allow/deny
explanations, removes strict DER/CRC32C/HSM evidence, or changes supported HSM
attestation formats requires a new design decision. A product requirement for
immediate revocation, multiple simultaneous roots, another KMS, or a different
custody architecture also requires a new decision rather than widening V1.

## 13. Traceability and verification

| Invariant | Owning prospective code | Negative evidence | Smallest verification |
| --- | --- | --- | --- |
| `ORA-001` | manifest parser and derived identity types | malformed/canonical/size/member/resource/principal/key/etag matrix | focused constructor tests and shared resource vectors |
| `ORA-002` | KMS metadata normalizer | wrong identity/purpose/algorithm/protection/state/import/rotation | typed fake response matrix for both snapshots |
| `ORA-003` | public-key response validator | format/name/CRC/SPKI/key mutation matrix | RFC 8410 vector plus existing test-only extraction oracle |
| `ORA-004` | attestation bundle normalizer/digest | missing/oversized/reordered/changed bundle | exact canonical digest vectors for V1 and V2 formats |
| `ORA-005` | role response parser | name/permission/stage/deleted/etag mutations | three-role closed matrix in snapshots A and B |
| `ORA-006` | policy/binding normalizer | direct, inherited, group, second signer, wildcard, and condition mutations | complete-policy fixtures through public function |
| `ORA-007` | v3 request/response parser | unknown/error/omission/tuple/explanation mutations and `testIamPermissions` canary | ten-tuple matrix plus AST/transport guard |
| `ORA-008` | signer role/binding and tuple validators | metadata/mutation/IAM widening | exact role plus negative effective-access tests |
| `ORA-009` | observer role/binding and tuple validators | sign/set-IAM widening or principal equality | exact role separation and negative access tests |
| `ORA-010` | probe request builder and ordered transition | alternate message/resource/digest/retry/timeout/call count | captured KMS request and 0/1 probe-count tests |
| `ORA-011` | probe response validator | type/name/HSM/flags/length/CRC/mismatched-key matrix | real Ed25519 signature vectors |
| `ORA-012` | clock and snapshot equality transition | first/second time, overflow, duration, every A/B drift point | exact transition-prefix 0/1/2 clock counts and drift tests |
| `ORA-013` | frozen result constructor | public-field and mutability inspection | exact dataclass shape/value tests |
| `ORA-014` | public wrapper | every ordinary dependency failure plus `KeyboardInterrupt` | empty args/string/context and propagation tests |
| `ORA-015` | complete module and architecture guard | forbidden import/call/global/entrypoint mutations | AST conformance plus fake client effect ledger |
| `ORA-016` | architecture registration and diff gate | seventh path/dependency/budget/cap/lock mutation | exact allowlist comparison and package conformance |

### 13.1 Phase A verification gates

- RFC is the only changed path;
- reviewed base remains current `main`, or mechanical base movement is recorded
  without semantic conflict;
- every provider assertion is supported by current official Google Cloud
  documentation;
- the design explicitly rejects `testIamPermissions` as authorization evidence;
- the exact roles, conditions, tuple matrix, observation order, bounds, output,
  and failure protocol are internally consistent;
- all prospective dependencies are already hash-pinned;
- `python3 conformance/ofarm_pkg_contract_check.py` passes before every commit;
- the draft pull request receives independent exact-head Phase A review;
- every demonstrated Phase A Blocker is corrected in this RFC; and
- a complete live decision card is shown only after exact-head review reports
  zero demonstrated in-scope Blockers.

### 13.2 Prospective Phase B verification gates

- reproduce this invariant table before editing;
- run the focused observer-root admission tests with the complete manifest,
  KMS metadata, attestation, role, policy, tuple, probe, time, drift, failure,
  and side-effect matrices;
- compare the shared KMS resource grammar, CRC32C vector, RFC 8410 extraction,
  and raw Ed25519 request/response behavior with existing test-only oracles
  without creating a production import;
- prove invalid local inputs make zero clock/network calls, external failures
  preserve the exact 1-or-2-clock transition prefix, successful calls make
  exactly two clock calls, and each admitted call makes exactly one probe
  between two complete snapshots;
- prove no `testIamPermissions`, KMS/IAM mutation, file/environment/database,
  log/output, executable, fallback, retry, or alternate endpoint is reachable;
- run architecture conformance with the exact import/effect/probe/HTTP guards;
- run Ruff or the repository-equivalent lint for changed Python;
- regenerate the review-baseline inventory mechanically;
- run `python3 conformance/ofarm_pkg_contract_check.py` before every commit;
- inspect the exact six-path diff; prove the module budget equals finished
  physical lines and is at most 700; prove the test is below 800 lines; and
  prove no group budget, shared cap, dependency, lockfile, migration, command,
  or seventh path changed;
- obtain hosted exact-head conformance and required architecture lanes; and
- receive bounded implementation review with zero demonstrated in-scope
  Blockers before merge.

No live Cloud KMS or IAM account is required for repository Phase B. Typed
deterministic fakes plus real Ed25519 verification exercise the complete local
trust transition. Actual provisioning evidence and production credentials are
deployment inputs and remain unauthorized.

## 14. Open decisions and review disposition

### 14.1 Open material decisions

No material decision remains open inside this Phase A boundary. The following
are deliberately deferred and must not be answered by Phase B:

- exact production project, location, key ring, key, version, principals,
  credentials, role etags, and attestation digest;
- who approves and publishes the canonical provisioning manifest;
- exact signer credential custody, absence of user-managed keys or
  impersonation/attachment paths, and how the future runtime obtains its
  independent clients and trusted clock;
- refresh cadence, startup/readiness integration, failure publication, and
  atomic issuer/verifier handoff;
- root rotation, compromise response, and whether a later version supports
  simultaneous roots;
- approver provisioning and the two-domain usability gate; and
- every database, credential, export, delivery, and store-loss follow-up.

### 14.2 Review disposition

- **Initial design posture:** one non-provisioning admission binds a reviewed manifest
  to exact live KMS material, exact custom roles, complete effective allow/deny
  evidence, one fixed live probe, double collection, and a short frozen result.
- **Blockers:** none known before independent exact-head review.
- **Follow-ups:** section 11.4 only.
- **Preferences:** none recorded.

A review finding is a Blocker only when it demonstrates that an `ORA-001`
through `ORA-016` invariant cannot hold, that the protocol is internally
contradictory, that the six-path implementation cannot verify it, or that the
slice crosses its primary trust boundary. Broader runtime, deployment,
rotation, approver, database, export, delivery, or issue-closure work is a
follow-up unless it demonstrates one of those failures.

## 15. Phase A approval boundary

This RFC grants no Phase B authority by authorship, local review, commit, push,
pull-request creation, GitHub activity, repository credentials, or a generic
`go`. It must first be bound to one already-created draft pull request and
receive independent exact-head Phase A review with zero demonstrated in-scope
Blockers. The AI must then display one complete live decision card in the same
Codex task.

Only the exact entire text of a later task-user message matching the live
card's approval sentence can authorize Phase B. Generic approval, current
publication authority, an AI message, delegation, another task, or a summary of
lost task items does not authorize implementation.

The prospective exact approval form is:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-OBSERVER-ROOT-ADMISSION-001 version 1.
```

If later shown in a complete live card and supplied as the exact entire later
task-user message, that approval would authorize only in-envelope repository
implementation, tests, documentation, mechanical inventory regeneration,
review handling, commits, pushes, and eventual merge in the one named draft
pull request after every gate passes.

It would authorize no cloud resource or IAM mutation, credential act,
attestation-verification ceremony, manifest publication or deployment, runtime
composition, readiness, root rotation, approver key, approval statement,
database admission, migration, temporary login, export, output delivery,
deployment, release, security waiver, or issue #192 closure.

## 16. Approval evidence

- **Decision:** `ISSUE192-SECURITY-AUDIT-OBSERVER-ROOT-ADMISSION-001`, version
  `1`.
- **Draft pull request:** https://github.com/samovers/OFARM2/pull/321.
- **Exact reviewed Phase A head:** none yet; the immutable head is recorded in
  the PR review request and independent review comments rather than
  self-referentially inside that same commit.
- **Complete live card:** not yet displayed.
- **Task-user Phase B approval:** not supplied.
- **Evidence posture:** Phase B is stopped.
