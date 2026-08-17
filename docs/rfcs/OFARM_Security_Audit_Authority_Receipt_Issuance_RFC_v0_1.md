# OFARM Security-Audit Authority-Receipt Issuance — Phase A Contract v0.1

**Status:** Phase A design draft; Phase B repository implementation,
deployment, and production operation are not authorized

**Draft pull request:** pending publication

**Contract identity:**
`ofarm2.security-audit-authority-receipt-issuance.v0.1`

**Proposed decision identity:**
`ISSUE192-SECURITY-AUDIT-AUTHORITY-RECEIPT-ISSUANCE-001`, version `1`

**Issue:** #192

**Reviewed base:** `3c24de33c27c0bbdaafe783769ed81d83f2c6bba`

**Primary trust boundary:** one independent Google Cloud KMS HSM Ed25519
observer key signs one fixed, short-lived security-audit approver-authority
receipt from one composition-pinned bounded manifest

**Phase A review-head boundary:** this RFC only

**Maximum prospective Phase B pull request boundary:** this RFC; one
library-only authority-receipt issuer; focused tests; minimal deployment
documentation; exact architecture-check registration; and the mechanically
regenerated review-baseline test inventory only

## 1. Problem and goal

The merged security-audit dual-approval verifier accepts an authority receipt
only when its exact canonical payload is signed by one composition-supplied
observer public key. That receipt is the verifier's sole authority for the
bounded mapping among approver IDs, Ed25519 public keys, derived key IDs, and
independence domains. Current `main` can verify such a receipt but cannot issue
one under an independent security-audit custody boundary.

This task establishes one stateless, library-only issuer that:

- accepts one exact observer KMS key-version resource and its matching raw
  32-byte Ed25519 public key from future trusted composition;
- accepts one exact canonical approver manifest at construction and derives
  every key ID itself;
- accepts one caller-owned trusted `now_us` for each issuance;
- constructs the exact authority payload already accepted by
  `SecurityAuditDualApprovalVerifier`, with an exact five-minute lifetime;
- sends only the exact domain-framed canonical payload to the configured Cloud
  KMS version through the raw `data` field with CRC32C, no retry, and one fixed
  timeout;
- validates the exact HSM response and independently verifies its returned
  64-byte Ed25519 signature against the configured public key; and
- returns one canonical bounded authority-receipt envelope.

The receipt authorizes keys named by the trusted composition-pinned manifest.
It does not create an approver signature, approve an export request, consume an
operation, create a credential, call PostgreSQL, export data, or deliver
output.

## 2. Learning value

This slice proves the missing byte-level compatibility seam between independent
observer-key custody and the merged dual-approval verifier. It demonstrates
that authority can be issued without importing tenant signing authority,
without permitting a carrier to select the observer root, and without mixing
database, credential, export, or output authority into the signing module.

It also makes the operational risk explicit: Cloud KMS constrains which key
version signs, not which approver roster is signed. The future composition that
pins the manifest and holds `useToSign` is therefore an authority root and must
be reviewed separately before deployment.

## 3. Non-goals

This pull request does not change or add:

- approver private-key generation, custody, registration ceremony, signing
  command, approval UI, hardware authentication, or approval statement;
- production observer-key creation, import, attestation, activation, rotation,
  disablement, destruction, IAM policy, principal credentials, or deployment;
- a mutable approver registry, manifest file loader, configuration parser,
  environment variable, secret manager, database source, latest-head service,
  immediate revocation service, or network fetch other than the one KMS signing
  call;
- multi-root verification, root IDs in the receipt, fallback roots, algorithm
  negotiation, tenant-authority fallback, tenant signer reuse, or correlation-
  HMAC key reuse;
- trusted clock acquisition, NTP, monotonic-time conversion, signing-time
  attestation, scheduler, refresh loop, cache, daemon, endpoint, CLI, or
  executable module;
- dual-approval request or statement creation, approval verification changes,
  durable single-operation admission, replay state, database migration,
  relation, function, role, grant, or write;
- temporary export-login creation, password or SCRAM-verifier generation,
  `VALID UNTIL`, membership, grant, revoke, session termination, role drop,
  credential transport, or crash-residue cleanup;
- an export call, access-intent commit, cumulative paging, result buffering,
  recipient binding, encryption, file/stdout write, or protected delivery;
- authentication, principal resolution, tenant binding, authorization,
  RuntimeBundle, issue #172, or issue #176 behavior;
- correlation-HMAC generation or custody, retention, gap/overflow, health,
  readiness, empty recreation, store loss, backup, replica, CDC, or recovery;
  or
- release, production operation, issue #192 closure, or a security waiver.

## 4. Trust model

### 4.1 Protected assets

- exclusive use of one exact independent observer KMS key version;
- exact binding between that key version and one configured raw public key;
- exact canonical representation of the configured approver roster;
- content-derived approver key IDs, ordering, and uniqueness;
- the fixed receipt schema, audience, signature domain, and five-minute
  lifetime;
- raw-data Ed25519 signing rather than prehash or algorithm substitution;
- transport-corruption detection for request data and returned signature;
- independent verification of the KMS signature before release;
- zero KMS calls for invalid configuration or invalid issuance time;
- exactly one non-retried KMS signing call for every request that reaches the
  signing transition;
- bounded parsing, serialization, signing input, response, and returned output;
- one fixed non-sensitive refusal with no dependency exception text; and
- absence of database, filesystem, environment, clock, random, process,
  logging, credential, export, or output effects.

### 4.2 Trusted components and actors

- future trusted composition that supplies the exact KMS key-version resource,
  matching observer public key, canonical approver manifest, KMS client, and
  honest current `now_us`;
- the future production principal allowed to use exactly that observer key
  version to sign;
- the future administrator and independent evidence path that provision and
  verify that key and its IAM posture;
- Google Cloud KMS v1's authenticated service boundary and HSM behavior;
- SHA-256, Ed25519, strict UTF-8 decoding, and the exact canonical JSON,
  base64url, RFC 7638-style key-ID, and CRC32C algorithms below;
- `cryptography==49.0.0`, `google-api-core==2.33.0`, and
  `google-cloud-kms==3.16.0`, already hash-pinned by the repository; and
- Python immutable `bytes`, `str`, `int`, tuple, and frozen-dataclass behavior
  under the supported runtime.

The manifest-pinning composition is an authorization authority. Anyone able to
replace that manifest, replace the configured observer key, or invoke the
observer key through another signing path can authorize a different roster.
KMS IAM alone cannot constrain signed bytes.

### 4.3 Untrusted inputs and behavior

- every byte, JSON member, array entry, public key, ID, order, and encoding in
  the constructor's manifest carrier;
- blank, malformed, duplicate, noncanonical, reordered, oversized, extra, or
  missing manifest content;
- malformed resource names, public keys, client surfaces, and issuance times;
- every KMS response field, signature byte, checksum, resource name,
  protection level, verification flag, and ordinary dependency exception;
- invocation frequency, repeated equal `now_us`, concurrent calls, latency,
  and ordinary process interruption; and
- a KMS client that returns a syntactically valid response signed by another
  key or responds from another resource.

No untrusted input selects the receipt schema, audience, signature domain,
algorithm, lifetime, JSON algorithm, base64url algorithm, key-ID algorithm,
checksum algorithm, KMS timeout, retry policy, output shape, or failure text.

### 4.4 Explicitly excluded attacker capabilities

This contract does not claim protection against:

- compromise or malicious use of the configured observer private key;
- a malicious trusted composition choosing an unauthorized manifest or false
  `now_us`;
- a KMS/IAM administrator granting a second signing path or substituting key
  evidence outside this module;
- compromise of an approver private key named by a valid receipt;
- arbitrary in-process mutation, reflective traversal, private-symbol access,
  or arbitrary code execution;
- local source, bytecode, dependency, interpreter, import-system, process
  memory, filesystem, host, operating-system, or hardware compromise; or
- later verifier, admission, credential, database, export, delivery, or
  recipient compromise.

Ordinary hostile constructor bytes, ordinary dependency failures, mismatched
KMS responses, and supported invocation ordering remain in scope.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Observer signing key | One exact KMS key-version resource fixed for the issuer instance by future trusted composition |
| Observer verification key | One exact 32-byte Ed25519 public key fixed for the same issuer instance |
| Approver roster | One canonical manifest fixed at issuer construction by future trusted composition |
| Approver key identity | Exact RFC 7638-style derivation from each manifest public key |
| Receipt schema and audience | Code-owned constants matching the merged verifier |
| Receipt start | Trusted caller-supplied `now_us` |
| Receipt end | Exactly `now_us + 300_000_000` microseconds |
| Signature input | Code-owned domain plus exact canonical payload |
| Signature production | One raw-data call to the exact configured KMS version |
| Signature acceptance | Exact response checks plus local verification under the configured public key |
| Point-in-time receipt acceptance | The existing verifier, not this issuer |
| Immediate revocation or latest head | No authority in this slice |
| Approval, durable admission, credential, disclosure, delivery | No authority in this slice |

There is no per-call roster, caller-supplied key ID, root in the manifest,
root in the returned envelope, generic signing callback, private-key input,
alternate signature algorithm, configurable lifetime, retry, tenant fallback,
or compatibility alias.

## 6. Protocol, state machine, and ordering

### 6.1 Exact public interface

The future production module exposes exactly:

```python
__all__ = (
    "SecurityAuditAuthorityReceiptIssuer",
    "SecurityAuditAuthorityReceiptRefused",
)
```

The supported interface is:

```python
class SecurityAuditAuthorityReceiptIssuer:
    def __init__(
        self,
        client: KmsAuthoritySigningClient,
        *,
        kms_key_version_resource: str,
        observer_public_key: bytes,
        approver_manifest_bytes: bytes,
    ) -> None: ...

    def issue(self, *, now_us: int) -> bytes: ...
```

`KmsAuthoritySigningClient` is a module-private `Protocol` containing only the
keyword-only Cloud KMS `asymmetric_sign(request=..., retry=None,
timeout=...)` method. It is not exported. Construction verifies that the
client has one callable `asymmetric_sign` attribute without invoking it.

Construction validates and normalizes the complete resource, public key, and
manifest before assigning the ready issuer state. It stores the manifest as
immutable private normalized entries. It does not call KMS. The issuer is
stateless across calls; `issue()` neither mutates the roster nor records an
issuance.

The refusal class is empty and has no custom constructor, fields, error code,
or dependency-derived message:

```python
class SecurityAuditAuthorityReceiptRefused(RuntimeError):
    pass
```

### 6.2 Exact constants and bounds

```text
APPROVER_MANIFEST_SCHEMA =
  "ofarm.security-audit-break-glass-approver-manifest.v1"

AUTHORITY_RECEIPT_SCHEMA =
  "ofarm.security-audit-break-glass-authority-receipt.v1"

AUDIENCE =
  "ofarm.security-audit-break-glass-export.v1"

AUTHORITY_SIGNATURE_DOMAIN =
  b"OFARM_SECURITY_AUDIT_BREAK_GLASS_AUTHORITY_RECEIPT_V1\x00"

KMS_RPC_TIMEOUT_SECONDS = 5.0
RECEIPT_LIFETIME_MICROSECONDS = 300_000_000
MAX_UNIX_MICROSECONDS = 9_223_372_036_854_775_807
```

| Resource | Exact bound |
| --- | ---: |
| Approver manifest carrier | 1 through 8,192 bytes |
| Constructed authority payload | 1 through 12,288 bytes |
| Raw KMS signing input | 58 through 12,345 bytes |
| Returned authority envelope | 1 through 16,384 bytes |
| Observer public key | 32 bytes |
| Each approver public key | 32 bytes |
| Returned Ed25519 signature | 64 bytes |
| Approver entries | 2 through 16 |
| Approver ID | 1 through 128 ASCII bytes |
| Independence domain | 1 through 128 ASCII bytes |
| Derived key ID | exactly 43 canonical base64url characters |
| Receipt lifetime | exactly 300,000,000 microseconds |
| KMS attempts | exactly 0 before signing; exactly 1 after transition |

`now_us` has exact non-boolean Python type `int` and lies from `0` through
`MAX_UNIX_MICROSECONDS - RECEIPT_LIFETIME_MICROSECONDS` inclusive. No float,
decimal, string, `bool`, negative value, or overflowing addition is accepted.

### 6.3 Canonical JSON

The manifest carrier and every constructed JSON value use one exact rule. An
input carrier must:

1. have exact Python type `bytes` and the applicable nonzero size bound;
2. decode as strict UTF-8 without a byte-order mark;
3. reject duplicate object members;
4. reject `NaN`, infinity, and every non-JSON constant;
5. have exact root type `dict`, exact member sets, and exact permitted JSON
   types; and
6. equal this exact byte-for-byte reserialization:

```python
dumps(
    value,
    ensure_ascii=True,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("ascii")
```

Whitespace, alternate escapes, raw non-ASCII source characters, reordered
members, alternate numeric forms, extra members, missing members, and duplicate
members therefore refuse.

### 6.4 Canonical base64url, key identity, resource, and CRC32C

A base64url value is a non-empty exact ASCII `str` matching
`[A-Za-z0-9_-]+`, contains no padding, decodes after only internally calculated
padding is added, has the required decoded length, and equals its unpadded
URL-safe re-encoding.

Every approver key ID is derived locally from its exact 32-byte public key:

```python
x = unpadded_base64url(public_key)
thumbprint_input = (
    b'{"crv":"Ed25519","kty":"OKP","x":"' + x + b'"}'
)
key_id = unpadded_base64url(sha256(thumbprint_input).digest())
```

The exact compatibility vector is:

```text
public key:
  000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
key ID:
  P7IdLIpiTZiFaIoOSqbX3JrSyps3hvZ4Y2SieP96XIY
```

Production reproduces this protocol machinery locally and must not import
tenant authority. Focused tests compare the result with the exact vector, the
merged verifier, and, test-side only, the existing
`derive_ed25519_key_id()` compatibility oracle.

The KMS key-version resource has exact Python type `str` and matches:

```text
^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/
locations/[a-z0-9](?:[a-z0-9-]*[a-z0-9])?/
keyRings/[A-Za-z0-9_-]{1,63}/
cryptoKeys/[A-Za-z0-9_-]{1,63}/
cryptoKeyVersions/[1-9][0-9]*$
```

The displayed line breaks are presentation only; the implementation uses one
anchored expression with no whitespace. Wildcards, aliases, parent resources,
version zero, leading-zero versions, empty segments, and trailing text refuse.

CRC32C is the standard reflected Castagnoli calculation with initial value
`0xffffffff`, reflected polynomial `0x82f63b78`, and final XOR
`0xffffffff`. The exact check vector is:

```text
CRC32C(b"123456789") == 0xe3069283
```

The issuer reproduces this small transport-integrity algorithm locally. CRC32C
is never key identity, signature authenticity, resource authority, protection-
level authority, or manifest authority.

### 6.5 Exact approver manifest

The canonical manifest has exactly:

```json
{
  "approvers": [
    {
      "approverId": "<closed-id>",
      "independenceDomain": "<closed-id>",
      "publicKey": "<canonical-base64url-32-byte-key>"
    }
  ],
  "audience": "ofarm.security-audit-break-glass-export.v1",
  "schemaVersion": "ofarm.security-audit-break-glass-approver-manifest.v1"
}
```

`approverId` and `independenceDomain` match
`[A-Za-z0-9][A-Za-z0-9._:-]{0,127}` exactly. The issuer derives each key ID
before order and uniqueness checks. Entries must already be sorted in ascending
ASCII lexicographic order by the derived tuple
`(approverId, keyId, independenceDomain)`.

Approver IDs are individually unique and derived key IDs are individually
unique. Independence domains may repeat in the full roster because the merged
verifier, not the issuer, requires the two selected approvals to have distinct
domains. Each decoded public key must also construct as an Ed25519 public key.
There are exactly 2 through 16 entries. Caller-supplied key IDs, private keys,
root keys, timestamps, receipt lifetimes, metadata, disabled flags, algorithms,
and signatures are not members and refuse as extras.

### 6.6 Exact authority payload

For each accepted call, the issuer constructs this exact canonical payload:

```json
{
  "approvers": [
    {
      "approverId": "<manifest-id>",
      "independenceDomain": "<manifest-domain>",
      "keyId": "<locally-derived-key-id>",
      "publicKey": "<manifest-canonical-public-key>"
    }
  ],
  "audience": "ofarm.security-audit-break-glass-export.v1",
  "expiresAtUnixMicroseconds": 300000000,
  "observedAtUnixMicroseconds": 0,
  "schemaVersion": "ofarm.security-audit-break-glass-authority-receipt.v1"
}
```

The example timestamps show `now_us == 0`. For every call:

```text
observedAtUnixMicroseconds = now_us
expiresAtUnixMicroseconds = now_us + 300_000_000
```

The approver entries preserve the already-validated manifest order and add
only the locally derived `keyId`. The resulting canonical payload must remain
within 12,288 bytes before KMS is called. No manifest digest, resource name,
observer key, observer key ID, algorithm, IAM evidence, or signing timestamp is
added because the merged verifier's fixed V1 receipt schema accepts none.

`observedAtUnixMicroseconds` is a trusted caller observation, not a KMS-
attested signing time. Signing latency shortens the receipt's remaining useful
life; it never moves either timestamp forward.

### 6.7 Exact signing input and KMS request

The only bytes submitted for signing are:

```text
AUTHORITY_SIGNATURE_DOMAIN + canonical_authority_payload
```

The issuer constructs exactly:

```python
kms_v1.AsymmetricSignRequest(
    name=configured_kms_key_version_resource,
    data=signing_input,
    data_crc32c=crc32c(signing_input),
)
```

It calls exactly:

```python
client.asymmetric_sign(
    request=request,
    retry=None,
    timeout=5.0,
)
```

The `digest` request field is left unset. There is no prehash, `Ed25519ph`,
retry, configurable timeout, alternate endpoint, metadata argument, fallback,
probe call, key observation call, or second signing attempt. Ed25519 signs the
raw domain-framed bytes.

Cloud KMS integrity guidance permits bounded retries after some transport
failures. This contract deliberately selects refusal instead: one invocation
has one unambiguous signing attempt, and a trusted caller must start a new
issuance call if policy permits another attempt. That availability tradeoff is
part of `ARI-006`, not an accidental omission of client defaults.

All resource, key, manifest, time, payload, and size validation completes
before constructing the request and before calling the client. An invalid
value therefore produces zero KMS calls. Once control enters
`asymmetric_sign`, any return or ordinary exception consumes the one allowed
attempt; the issuer never retries.

### 6.8 Exact KMS response acceptance

The return must be an instance of
`kms_v1.AsymmetricSignResponse` and satisfy every condition:

```text
response.name == configured_kms_key_version_resource
response.protection_level == kms_v1.ProtectionLevel.HSM
response.verified_data_crc32c is True
response.verified_digest_crc32c is False
type(response.signature) is bytes
len(response.signature) == 64
type(response.signature_crc32c) is int
not isinstance(response.signature_crc32c, bool)
0 <= response.signature_crc32c <= 0xffffffff
response.signature_crc32c == crc32c(response.signature)
```

The issuer then constructs an Ed25519 public key from the exact configured
32 bytes and independently verifies the returned signature over the exact
signing input. Response fields do not replace configuration. Another name,
software protection, absent or false data verification, true digest
verification, missing or wrong checksum, non-bytes or non-64-byte signature,
or signature from another key refuses without output.

The configured public key is validated during construction, but the returned
signature is verified after every KMS call. A matching resource string without
a matching signature is insufficient.

### 6.9 Exact returned envelope and verifier compatibility

Only after section 6.8 succeeds does the issuer construct this exact canonical
envelope:

```json
{
  "payload": "<canonical-base64url-of-exact-payload>",
  "signature": "<canonical-base64url-of-exact-64-byte-signature>"
}
```

The envelope must remain within 16,384 bytes and is returned as exact immutable
`bytes`. It contains no newline, whitespace, KMS resource, checksum, protection
level, error detail, manifest carrier, or public root.

The focused compatibility test must pass the returned bytes unchanged to the
merged `SecurityAuditDualApprovalVerifier`, build one otherwise-valid request
and two real Ed25519 approval statements for two distinct manifest entries,
and prove acceptance at a time inside the receipt interval. It must also prove
that a verifier configured with another observer public key refuses the same
receipt. No adapter, normalization, field translation, or private verifier
entry point is allowed.

### 6.10 Ordered state machine

Construction has this complete transition:

```text
UNVALIDATED
  -> validate client surface
  -> validate exact resource
  -> validate exact observer public key
  -> parse and canonicalize bounded manifest
  -> derive key IDs; validate order and uniqueness
  -> READY
```

Any ordinary failure before `READY` returns no object and raises one fresh
refusal. KMS is never called during construction.

Each `issue()` call has this complete transition:

```text
READY
  -> validate exact now_us and nonoverflowing fixed lifetime
  -> construct and bound exact canonical payload
  -> construct exact domain-framed signing input and CRC32C request
  -> KMS_ATTEMPTED (exactly one non-retried call)
  -> validate complete response
  -> independently verify exact signature
  -> construct and bound canonical envelope
  -> RETURNED
```

An ordinary failure at any transition raises one fresh refusal and returns no
partial value. A call does not change the issuer's `READY` state. Repeating an
equal call is permitted and makes another one-attempt KMS call; this module
does not claim issuance deduplication, receipt uniqueness, durable history, or
single-use admission.

### 6.11 Failure protocol

Every ordinary constructor, parser, serializer, dependency, response, key, or
signature failure becomes a newly created
`SecurityAuditAuthorityReceiptRefused()` outside the active exception handler.
The refusal has empty `str(exc)`, empty `exc.args`, no copied dependency field,
and no explicit cause. No signature, payload, roster, key, resource, checksum,
or dependency text is returned or logged.

`BaseException` subclasses such as `KeyboardInterrupt`, `SystemExit`, and
`GeneratorExit` propagate unchanged. The implementation catches `Exception`,
not `BaseException`, and raises the fixed refusal only after leaving the
handler. Tests exercise ordinary dependency exceptions and a
`KeyboardInterrupt` canary.

### 6.12 Side-effect and composition boundary

The only permitted external effect is the one `asymmetric_sign` call after all
local validation. Production code performs no database access, filesystem or
environment read, network call through another client, clock read, sleep,
random generation, process launch, stdout/stderr write, log emission, metric,
trace, cache, registry mutation, or receipt persistence.

The future production composition must supply:

- an independently governed security-audit observer key, never the tenant
  capability key or correlation-HMAC key;
- one signer principal whose effective authority is restricted to
  `cloudkms.cryptoKeyVersions.useToSign` on the exact configured version;
- an independently verified mapping from that exact version to the configured
  public key, algorithm `EC_SIGN_ED25519`, purpose `ASYMMETRIC_SIGN`, enabled
  state, and HSM protection;
- one reviewed canonical approver manifest; and
- a trusted current `now_us` observation.

Those production key, IAM, evidence, configuration, and clock-composition acts
are required before operation but are not implemented or authorized here.
Because the KMS signer can sign arbitrary bytes with its granted key, its
process and principal remain authority roots even when the library pins a
manifest per instance.

Manifest removal affects only later issuer instances or later receipts. A
previously issued receipt can remain accepted until its fixed expiration,
never more than five minutes after its claimed observed time. This is bounded-
latency revocation, not immediate revocation. Root compromise, root rotation,
and atomic verifier/issuer configuration handoff require a separate decision;
this V1 design does not add multiple roots or a latest-head channel.

### 6.13 External protocol basis

The Cloud KMS
[`asymmetricSign` API](https://cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/asymmetricSign)
defines the exact-version name, `cloudkms.cryptoKeyVersions.useToSign`
permission, mutually exclusive raw `data` and `digest` inputs, request CRC32C,
and the response name, signature CRC32C, verification flags, and protection
level used above. The Cloud KMS
[algorithm reference](https://cloud.google.com/kms/docs/algorithms)
defines `EC_SIGN_ED25519` as PureEdDSA taking raw data rather than a caller-
supplied digest. These sources establish provider protocol facts only; the
stricter one-attempt policy, canonical receipt, five-minute lifetime, and HSM-
only selection are this OFARM contract's decisions.

## 7. Stable invariants

### `ARI-001` — independent exact observer root

One issuer instance pins one canonical KMS key-version resource and one exact
32-byte Ed25519 public key. Neither the manifest, call, KMS response, tenant
authority, nor returned carrier can replace either value.

### `ARI-002` — one bounded canonical manifest

The complete 1-through-8,192-byte constructor carrier is strict canonical JSON
with the exact manifest schema, audience, members, types, 2-through-16 entry
bound, closed IDs, and 32-byte canonical public keys.

### `ARI-003` — derived identity, order, and uniqueness

The issuer derives every 43-character key ID from public-key bytes, requires
ascending `(approverId, keyId, independenceDomain)` order, and refuses repeated
approver IDs or key IDs. No carrier asserts a key ID.

### `ARI-004` — fixed receipt scope and lifetime

The payload has the merged verifier's exact schema and audience, the normalized
manifest entries, `observedAtUnixMicroseconds == now_us`, and
`expiresAtUnixMicroseconds == now_us + 300_000_000`, with no extra member.

### `ARI-005` — exact raw-data KMS request

The request names only the configured resource and places the exact signature
domain plus canonical payload in `data`, with exact CRC32C. `digest` remains
unset. Timeout is exactly `5.0` and retry is exactly `None`.

### `ARI-006` — zero-before-one signing work

Invalid configuration, manifest, time, or constructed size makes zero KMS
calls. Every call reaching the signing transition makes exactly one attempt,
with no retry, fallback, preflight, key observation, or second signature.

### `ARI-007` — complete HSM response validation

Success requires the exact response type, resource name, HSM protection, data
and digest verification flags, 64-byte signature, and exact uint32 signature
CRC32C. No response field changes configuration.

### `ARI-008` — independent signature verification

Before output, the issuer verifies the returned signature under the configured
public key over the exact submitted bytes. Resource equality and CRC32C alone
never authenticate the signature.

### `ARI-009` — exact verifier-compatible output

The only success is one canonical envelope of at most 16,384 bytes containing
only canonical base64url `payload` and `signature`. The merged verifier accepts
it unchanged under the configured public root.

### `ARI-010` — caller-owned time only

`now_us` is an exact bounded non-boolean integer, is never overwritten, and is
the sole timestamp source. Production contains no wall, monotonic, database,
KMS, filesystem, or environment clock acquisition.

### `ARI-011` — fixed refusal and interruption posture

Every ordinary failure maps to one fresh empty refusal outside the active
handler, without dependency text, logging, or partial output. Every
`BaseException` propagates unchanged.

### `ARI-012` — one permitted effect

The one non-retried KMS signing call is the only external effect. There is no
persistence, database, file, environment, output, log, clock, random, process,
sleep, credential, export, delivery, or mutable-registry effect.

### `ARI-013` — independent custody and no approver private keys

Production imports neither tenant signing authority nor correlation-HMAC
authority and accepts no private key. The observer key, future signer principal,
and production evidence path remain independent security-audit authorities.

### `ARI-014` — fixed repository and source surface

Implementation stays within the exact six-path envelope, one module-specific
import/effect guard, one mechanically exact finished module budget no greater
than 450 lines, and no group-budget, test-glob, shared test-line-limit, or
dependency-lock change.

## 8. Production-entry negative cases

Every counterexample enters through the public constructor, `issue()`, or its
injected KMS client. No monkeypatching of private fields establishes the
failure.

| Invariant | Concrete counterexample and required result |
| --- | --- |
| `ARI-001` | A manifest root field, response from a sibling version, signature from another observer key, tenant key, or malformed configured resource refuses. |
| `ARI-002` | Blank/oversized manifest, BOM, duplicate member, whitespace, padded base64url, raw non-ASCII, extra member, wrong type, invalid ID, or 1/17 entries refuses before KMS. |
| `ARI-003` | Caller key ID, unsorted entries, duplicate approver ID, duplicate public key/key ID, or disagreement with the exact compatibility vector refuses before KMS. |
| `ARI-004` | Caller lifetime/timestamp fields are extras and refuse; maximum-time overflow refuses; success produces the exact fixed interval. |
| `ARI-005` | Digest-field signing, missing/wrong data CRC, changed domain byte, alternate resource, timeout, or retry fails request-shape evidence. |
| `ARI-006` | Deterministic fakes prove invalid preconditions make 0 calls and every success or post-transition failure makes exactly 1 call. |
| `ARI-007` | Wrong response type/name/protection/flag/signature length/checksum type/checksum value refuses without output. |
| `ARI-008` | Correct response metadata and CRC with a signature from another key refuses. |
| `ARI-009` | Returned receipt passes the public merged verifier unchanged; any payload/signature byte mutation or alternate verifier root refuses. |
| `ARI-010` | `bool`, float, negative, overflowing, or overwritten `now_us`, or any clock-producing import/call, refuses or fails architecture evidence. |
| `ARI-011` | A KMS `RuntimeError` yields an empty unlinked refusal; `KeyboardInterrupt` propagates unchanged; no dependency text appears. |
| `ARI-012` | Runtime canaries and AST evidence prove no client method other than one `asymmetric_sign` and no database/file/environment/log/output/random/process/sleep effect. |
| `ARI-013` | Any production import of tenant signer, tenant contract, correlation-HMAC module, private-key API, or second signing backend fails conformance. |
| `ARI-014` | A seventh path, unregistered import, budget mismatch/overflow, group budget, test-glob/shared test-cap change, or lockfile change stops Phase B. |

## 9. Proposed architecture and smallest change

### 9.1 Components

Phase B would add one module,
`deployment/postgresql/security_audit_authority.py`, containing:

- the fixed schema, audience, domain, time, size, and KMS constants;
- one private KMS client `Protocol`;
- one private frozen normalized approver entry;
- strict canonical JSON and canonical base64url helpers;
- local key-ID, resource-name, and CRC32C validators;
- exact manifest normalization and payload/envelope construction;
- the one empty refusal class; and
- the one stateless issuer.

It does not modify or import the verifier. Exact wire compatibility is proved
from the test side through the verifier's public API. It does not extract a
generic KMS signer or canonical-carrier framework because either abstraction
would widen this security-audit boundary and create a signing surface with
authority not required here.

### 9.2 Exact source import confinement

The production module may contain only these import statements:

```python
from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as BinasciiError
from dataclasses import dataclass
from hashlib import sha256
from json import dumps, loads
from re import fullmatch
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)
from google.cloud import kms_v1
```

The architecture checker compares every `Import` and `ImportFrom` node with
that exact normalized statement-and-symbol allowlist. Any additional module,
symbol, alias, star import, whole-module import, relative import, or repository
import refuses. The direct repository import bound for the module is therefore
the exact empty set.

The module-specific check also forbids these names or call targets:

```text
__import__
eval
exec
compile
open
print
input
breakpoint
getenv
environ
system
popen
run
sleep
uuid1
uuid4
getnode
now
utcnow
today
time
time_ns
monotonic
perf_counter
token_bytes
randbytes
```

Focused AST evidence must additionally prove:

- `now_us` is never stored to or deleted;
- the only method called on the constructor-supplied client is
  `asymmetric_sign`;
- that call occurs exactly once in the source, with literal `retry=None` and
  the code-owned timeout constant whose exact value is `5.0`;
- the request constructor contains exact `name`, `data`, and `data_crc32c`
  keywords and no `digest` keyword;
- the manifest-to-payload transition assigns both timestamps only from the
  original `now_us` and the fixed lifetime constant; and
- no exception message or dependency value is passed to the refusal.

Arbitrary reflective traversal remains excluded under section 4.4. Within the
supported non-reflective source model, these checks make the public interface,
time source, signing effect, and import boundary mechanically closed.

### 9.3 Architecture-budget registration

After the production module is complete, Phase B must add one `MODULE_BUDGETS`
entry whose value equals the architecture checker's physical line count at the
exact implementation head and is no greater than `450`. The placeholder below
describes the mechanical substitution; no placeholder may be committed:

```text
MODULE_BUDGETS[
  "deployment/postgresql/security_audit_authority.py"
] = <FINISHED_MODULE_LINE_COUNT_NOT_GREATER_THAN_450>

DIRECT_IMPORT_BOUNDS[
  "deployment/postgresql/security_audit_authority.py"
] = frozenset()
```

The exact import and effect rules in section 9.2 belong to one check hard-coded
to that exact relative path and must not change another module's rules. Phase B
must not add a single-member `GROUP_BUDGETS` entry because it would duplicate
the module budget without constraining another source file. It must not change
`TEST_GLOBS` or `MAX_TEST_LINES`; the one exact test path in section 11.1 is
bounded by the closed path envelope and required evidence, not by an unrelated
shared test-family cap. It must not change a dependency lock because every
required dependency is already hash-pinned.

### 9.4 Why this is the minimum coherent design

The issuer needs one fixed roster, one independent root, one trusted time, one
canonical payload, one KMS call, and one returned envelope. Removing any of
those loses required authority or compatibility. Adding registry persistence,
key provisioning, IAM observation, a clock, approval generation, admission,
credentials, database access, export, or delivery crosses another trust
boundary.

Putting issuance in the dual-approval verifier would let verification code
create the authority it is supposed to authenticate. Reusing the tenant signer
would cross the pre-tenant/tenant boundary. Accepting a generic callback or a
per-call roster would create a broader signing oracle. One isolated fixed-
manifest issuer is the smallest coherent byte-level prerequisite.

## 10. Elegance audit

There is exactly one runtime authority for each decision:

- trusted composition for the manifest, root resource, public key, client, and
  `now_us`;
- local deterministic code for schema, audience, ordering, IDs, timestamps,
  bytes, checksum, and output shape;
- the exact KMS key version for signature production; and
- local Ed25519 verification for signature acceptance.

The manifest is normalized once at construction and represented once in each
receipt. Key-ID and CRC32C duplication is deliberate small protocol machinery,
not another authority source; exact vectors prevent drift. There is one
authoritative external transition point, one exact response path, and one
output path. There is no mutable registry, cache, compatibility layer, generic
signing abstraction, alternate root, duplicate currentness state, or fallback.

No existing production code is deleted. A clean new module preserves the
merged verifier as an independent consumer and makes accidental production
composition visible as a separate future decision.

## 11. Pull request and approval boundary

### 11.1 Normative technical path envelope

Phase B may change exactly these six paths:

1. `docs/rfcs/OFARM_Security_Audit_Authority_Receipt_Issuance_RFC_v0_1.md`
2. `deployment/postgresql/security_audit_authority.py`
3. `deployment/postgresql/README.md`
4. `kernel/tests/test_security_audit_authority.py`
5. `conformance/rewrite_architecture_check.py`
6. `conformance/review_baseline_test_inventory.json`

Phase A publication changes only path 1. Adding, renaming, or changing any
other path before exact approval, or any seventh path during Phase B, stops
work for a new decision version.

### 11.2 Dependencies

- current `main` at reviewed base
  `3c24de33c27c0bbdaafe783769ed81d83f2c6bba`;
- merged dual-approval verification PR #319 and its exact receipt wire
  contract;
- the existing hash-pinned Cloud KMS, Google API core, and cryptography
  dependencies; and
- issue #172 remains closed and unchanged.

No issue #176 branch, pull request, model, storage, approval workflow, or
temporal behavior is a dependency. The tenant KMS signer and tenant authority
are comparison evidence only and are not production dependencies.

### 11.3 Reviewer non-requirements

Reviewers must not require this pull request to:

- provision, activate, attest, observe, rotate, disable, destroy, or deploy the
  observer KMS key or change IAM;
- acquire production time, load a manifest from a production source, compose a
  service, refresh receipts, or expose a command or endpoint;
- add immediate revocation, a latest-head channel, multiple roots, rotation
  overlap, or root-compromise recovery;
- create approver private keys, approval statements, export requests, or an
  approval UI;
- change the merged verifier, add durable admission, migration, operation
  consumption, or replay state;
- create or close a temporary LOGIN or credential;
- call the bounded export runner, page cumulatively, or deliver output;
- change runtime health/readiness, HMAC retention, recovery, authentication,
  tenant, or deployment authority; or
- claim production readiness or close issue #192.

Those are follow-ups, not review fixes.

### 11.4 Ordered follow-ups

1. production observer-root provisioning, independent IAM/key evidence,
   trusted manifest/time loading, and issuer/verifier configuration handoff;
2. durable one-operation admission for `(operation_id, approval_digest)`;
3. temporary export-login creation, bounded credential custody, revocation,
   session termination, drop, and verified structural closure;
4. protected output delivery after closure;
5. verified empty-recreate/store-loss handling; and
6. final real-ASGI/PostgreSQL hostile and cross-slice closure evidence.

Follow-up 1 may require more than one trust-boundary PR if key/IAM custody and
runtime integration cannot remain one primary boundary. This RFC does not
pre-authorize either shape.

### 11.5 Stop and reapproval conditions

Stop before editing if implementation or review requires:

- another manifest or receipt member, schema, audience, signature domain,
  algorithm, key-ID rule, checksum rule, time source, lifetime, output form, or
  refusal protocol;
- a per-call roster, generic signing callback, private-key input, second KMS
  call, retry, configurable timeout, another backend, root fallback, or tenant
  authority import;
- production IAM, key observation, attestation, lifecycle, manifest loading,
  clock acquisition, runtime composition, or deployment configuration;
- approval creation or verification changes, database transition, credential,
  role, export call, output, or delivery;
- a path outside section 11.1 or a second authority-issuer test path;
- a finished module above 450 physical lines, a registered module budget
  different from its exact finished line count, a nonempty repository import
  bound, a group budget, or any `TEST_GLOBS` or `MAX_TEST_LINES` change; or
- an additional dependency or lockfile change.

Any such evidence requires a new Phase A decision version or a separate
stacked trust-boundary pull request.

## 12. Provisional design record

This design is provisional before deployment.

It is acceptable because Phase B would be library-only, uncomposed, and unable
to operate without an injected KMS client, exact key resource, matching public
key, manifest, and trusted time. It performs no action until explicitly called
and grants no database, credential, export, output, or deployment authority.
Its only output is the already-specified short-lived receipt carrier.

Evidence requiring redesign includes:

- a production requirement for immediate approver or observer-root revocation;
- inability to complete authority issuance and two approvals inside the
  five-minute window under bounded KMS latency;
- a requirement for KMS-attested signing time rather than trusted caller time;
- a requirement for simultaneous old/new observer roots during rotation;
- evidence that a static reviewed manifest cannot be safely composed without a
  mutable registry in the same boundary;
- a requirement to bind output recipients or admission state into the receipt;
  or
- a supported runtime that cannot enforce the exact canonical, KMS, or source-
  import rules.

The likely upgrade path is an intentionally new schema and decision version,
not a compatibility alias or permissive parser. Before production, a separate
review must establish the independent KMS key, exact-version IAM confinement,
public-key/currentness evidence, manifest authority, trusted time, and atomic
configuration handoff. Until then, no production-eligibility claim follows
from this library.

## 13. Traceability and verification

| Invariant | Owning prospective code | Negative evidence | Smallest verification |
| --- | --- | --- | --- |
| `ARI-001` | constructor resource/key validators | manifest/response root substitution, sibling resource, mismatched signature | constructor matrix plus real Ed25519 vectors |
| `ARI-002` | canonical manifest decoder | malformed, duplicate, noncanonical, oversized, wrong count/type/member | focused carrier matrix |
| `ARI-003` | key-ID/order/uniqueness normalizer | caller key ID, wrong order, duplicate identity/key | exact vector plus roster matrix |
| `ARI-004` | payload builder | extra time/lifetime input, overflow, wrong schema/audience/interval | boundary-value and decoded-payload tests |
| `ARI-005` | request builder | changed domain/resource/data/digest/CRC/retry/timeout | exact fake-client request assertion |
| `ARI-006` | ordered issue transition | each pre/post-call deterministic failure point | exact 0/1 call-count tests |
| `ARI-007` | response validator | wrong response type/name/HSM/flags/length/checksum | response-field mutation matrix |
| `ARI-008` | local Ed25519 verification | metadata-correct signature from another key | real mismatched-key vector |
| `ARI-009` | envelope builder | byte mutation, alternate root, translation requirement | public merged-verifier end-to-end test |
| `ARI-010` | time validator/payload builder | bool/float/negative/overflow and clock/name canaries | boundary tests plus AST guard |
| `ARI-011` | public constructor/issue wrappers | ordinary dependency exception and `KeyboardInterrupt` | exact args/string/context and propagation tests |
| `ARI-012` | complete module/source guard | second client call or forbidden I/O/environment/log/random/process operation | fake client plus AST guard |
| `ARI-013` | zero repository imports | tenant/HMAC/private-key/backend import mutation | direct-import and exact-import guards |
| `ARI-014` | architecture registration/path envelope | path/import/budget/group/test-cap/lock mutation | conformance plus exact diff audit |

### 13.1 Phase A verification gates

- RFC is the only changed path;
- reviewed base remains current `main`, or base movement is mechanical and
  explicitly recorded;
- every receipt member and signing byte matches the merged verifier contract;
- all required dependencies are already hash-pinned;
- the complete contract passes repository package conformance;
- the draft pull request receives one independent exact-head review;
- every demonstrated Phase A Blocker is corrected in this RFC; and
- a complete live decision card is shown only after exact-head review reports
  zero demonstrated in-scope Blockers.

### 13.2 Prospective Phase B verification gates

- reproduce this invariant table before editing;
- run the focused authority-issuer tests, including exact manifest, key-ID,
  CRC32C, KMS request/response, failure, and call-count matrices;
- run the public merged-verifier compatibility test using real Ed25519
  signatures and the returned issuer bytes unchanged;
- run architecture conformance with the exact module/import/effect guards;
- run Ruff or the repository's equivalent lint for all changed Python;
- regenerate the review-baseline inventory mechanically;
- run `python3 conformance/ofarm_pkg_contract_check.py` before every commit;
- inspect the exact six-path diff; prove the registered module budget equals
  the finished physical line count and is at most 450; and prove no group
  budget, test glob, shared test-line limit, or lockfile changed;
- obtain hosted exact-head conformance and required architecture lanes; and
- receive bounded implementation review with zero demonstrated in-scope
  Blockers before merge.

No live PostgreSQL fixture or live Cloud KMS call is required for this library
slice. A deterministic KMS protocol fake plus real Ed25519 signing exercises
the complete local trust transition. Live key, IAM, and runtime evidence belong
to the ordered production-composition follow-up.

## 14. Open decisions and review disposition

### 14.1 Open material decisions

No material decision remains open inside this proposed Phase A boundary. The
following are deliberately deferred and must not be answered by Phase B:

- production observer-key identity, provisioning, IAM, attestation,
  observation, rotation, and compromise response;
- production manifest source, change ceremony, trusted clock, and issuer/
  verifier configuration handoff;
- immediate revocation versus the selected maximum five-minute latency;
- durable consumption and exact replay-result protocol;
- temporary-login and credential lifecycle;
- output-recipient binding and protected delivery; and
- store-loss and final hostile closure evidence.

### 14.2 Review disposition

- **Prepublication review:** the draft adopts the merged verifier's exact
  receipt schema, audience, signature domain, canonical JSON, base64url,
  derived key-ID, entry ordering, entry bounds, and five-minute maximum. It
  closes the issuer side with one fixed manifest, exact resource/public key,
  raw-data KMS request, CRC32C, HSM response checks, independent signature
  verification, one-attempt ordering, fixed failure, and exact compatibility
  evidence. No known in-scope design Blocker remains before publication.
- **Independent pull-request review:** not yet received at this draft head.
- **Preferences:** none recorded.
- **Follow-ups:** section 11.4 only.

A future reviewer observation is a Blocker only when it demonstrates that an
`ARI-001` through `ARI-014` invariant cannot hold, the protocol is internally
contradictory, the proposed code cannot be verified inside the six paths, or
the slice crosses its primary trust boundary. New product ideas, alternative
styles, broader production composition, and unrelated hardening are follow-ups
or preferences unless they demonstrate one of those failures.

## 15. Phase A approval boundary

This RFC grants no Phase B authority by authorship, local review, commit, push,
pull-request creation, GitHub review, repository credentials, or a generic
`go`. It must first be bound to one already-created draft pull request and
receive an independent exact-head Phase A review with zero demonstrated
in-scope Blockers. The AI must then display one complete live decision card in
the same Codex task.

Only the exact entire text of a later task-user message matching the live
card's approval sentence can authorize Phase B. Generic approval, current
publication authority, GitHub activity, an AI message, delegation, another
task, or a summary of lost task items does not authorize implementation.

The prospective exact approval form is:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-AUTHORITY-RECEIPT-ISSUANCE-001 version 1.
```

If later shown in a complete live card and supplied as the exact entire later
task-user message, that approval would authorize only in-envelope repository
implementation, tests, documentation, mechanical inventory regeneration,
review handling, commits, pushes, and eventual merge in the one named draft
pull request after every gate passes. It would authorize no production key or
IAM act, manifest deployment, trusted-clock or runtime composition, approval
creation, durable admission, migration, temporary LOGIN, credential, export
operation, output delivery, deployment, release, issue #192 closure, or
security waiver.

## 16. Approval evidence

- **Decision:**
  `ISSUE192-SECURITY-AUDIT-AUTHORITY-RECEIPT-ISSUANCE-001`, version `1`.
- **Draft pull request:** pending publication.
- **Complete live card:** none.
- **Task-user Phase B approval:** none.
- **Evidence posture:** Phase B remains unauthorized. The task user's generic
  `go` authorized continuation of the Phase A workflow only and is not the
  exact prospective approval sentence in section 15.
