# OFARM Security-Audit Dual-Approval Verification — Phase A Contract v0.1

**Status:** unapproved Phase A draft; independent exact-head review is pending;
Phase B, deployment, and production operation are not authorized

**Draft pull request:** `https://github.com/samovers/OFARM2/pull/319`

**Contract identity:**
`ofarm2.security-audit-dual-approval-verification.v0.1`

**Proposed decision identity:**
`ISSUE192-SECURITY-AUDIT-DUAL-APPROVAL-VERIFICATION-001`, version `1`

**Issue:** #192

**Reviewed base:** `a203110ed049de93695922aefb750588e895caf2`

**Primary trust boundary:** verification of two independently authorized
Ed25519 signatures over one fixed, one-page security-audit break-glass export
request

**Phase A review-head boundary:** this RFC only

**Maximum prospective Phase B pull request boundary:** this RFC; one
library-only approval verifier; focused tests; minimal deployment
documentation; exact architecture-check registration; and the mechanically
regenerated review-baseline test inventory only

## 1. Problem and goal

The accepted security-audit database exposes a separate bounded break-glass
function. It requires the exact temporary session user
`ofarm_security_audit_export_login`, a committed access intent with the closed
purpose `DUAL_APPROVED_BREAK_GLASS_EXPORT_V1`, the exact export-function
identity, one immutable cursor, at most 2,048 rows, and at most 8,388,608
database-encoded bytes. Normal provisioning intentionally creates neither the
temporary LOGIN nor its membership.

The merged bounded-export runner commits one equal access intent and calls the
accepted export function exactly once. It deliberately does not verify
approvals, create credentials, prevent approval reuse, write output, or
implement the complete break-glass lifecycle. Current `main` therefore has no
repository component that can independently verify that two authorized and
independent approver keys signed the same exact operation.

This task establishes one side-effect-free, library-only verifier that returns
one immutable normalized result only when:

- a bounded canonical authority receipt is signed by the verifier's one
  composition-supplied observer trust root;
- the presented authority receipt and bound export request are current at the
  caller-supplied trusted time;
- exactly two authority-receipt entries sign canonical statements binding the
  same exact authority receipt, export request, and operation ID;
- the selected entries have distinct approver IDs, key IDs, and independence
  domains; and
- the request fixes the accepted purpose, callable, newest-page or canonical
  cursor, one-page count, row ceiling, and byte ceiling.

The returned value is normalized verification evidence. It is not a bearer
credential, admission grant, proof of signature time, durable consumption
record, or permission to create a temporary LOGIN or export data.

## 2. Learning value

This slice proves that the accepted two-person operational precondition can be
cryptographically bound to the exact existing export request without relying
on caller assertions, tenant authority, GitHub activity, mutable registries,
database credentials, or a boolean `approved` input.

It validates a narrow architectural seam: approval verification can remain
independent from the persistence authority that later consumes an operation,
the credential authority that opens and closes the structurally incompatible
temporary-login window, the bounded disclosure primitive, and protected output
delivery.

## 3. Non-goals

This pull request does not change or add:

- approval creation, an approval UI or command, approver private-key custody,
  hardware authentication, signing service, or signing-time authority;
- observer-key provisioning, rotation, revocation, KMS/IAM policy, authority
  receipt issuance, latest-head lookup, or immediate revocation;
- durable single-operation consumption, replay storage, admission transaction,
  migration, relation, function, index, role, grant, or database write;
- temporary export-login creation, password or SCRAM-verifier generation,
  `VALID UNTIL`, membership, grant, revoke, session termination, role drop,
  credential transport, or crash-residue cleanup;
- an export call, access-intent commit, cumulative paging, result buffering,
  output recipient, encryption, file/stdout write, or protected delivery;
- a CLI, executable module, web endpoint, daemon, scheduler, loop, queue,
  spool, cache, service, or production runtime composition;
- authentication, principal resolution, tenant binding, authorization,
  RuntimeBundle, tenant storage, issue #172, or issue #176 behavior;
- correlation-HMAC generation or custody, retention, gap/overflow, runtime
  health, readiness, store loss, empty recreation, backup, replica, CDC, or
  recovery;
- deployment activation, production trust-root selection, production approval,
  production credential issuance, release, issue #192 closure, or a security
  waiver; or
- a claim that an authorized operator, observer-root holder, approver-key
  holder, database owner, superuser, or later output recipient cannot bypass or
  copy data through authority they independently possess.

## 4. Trust model

### 4.1 Protected assets

- the requirement for two independently authorized signatures;
- exact binding of those signatures to one authority receipt, operation ID,
  request, cursor, purpose, callable, and fixed disclosure ceilings;
- the distinction between point-in-time verification and durable single-use
  admission;
- the five-minute maximum authority and request windows;
- honest bounded-latency revocation semantics;
- one fixed canonical representation and digest for every signed carrier;
- a single trusted currentness input, `now_us`;
- bounded carrier parsing, authority-set work, and cryptographic work;
- fixed non-sensitive refusal behavior without dependency exception text; and
- absence of database, credential, export, output, clock-acquisition, random-ID,
  filesystem, network, process, or logging effects.

### 4.2 Trusted components

- the future composition-supplied exact 32-byte observer Ed25519 public key;
- the existing checked-in export purpose, function identity, row ceiling, and
  byte ceiling;
- the existing `SecurityAuditAccessCursor` canonical parser;
- SHA-256, Ed25519, strict UTF-8 decoding, and the exact canonical JSON and
  base64url algorithms selected below;
- `cryptography==49.0.0`, already hash-pinned by the repository;
- Python exact immutable `bytes`, `str`, `int`, tuple, UUID, and frozen
  dataclass behavior under the supported runtime; and
- the future trusted caller that supplies `now_us` and does not substitute an
  attacker-selected clock.

The observer public key authenticates the presented authority receipt. The
receipt is the sole authority for the bounded set of presented approver keys,
principal identities, and independence domains. An approver signature proves
only that the corresponding private key signed the exact statement bytes. It
does not independently prove when the signature was produced.

### 4.3 Untrusted actors and inputs

- both input carriers and every byte, JSON member, array entry, encoded
  segment, key, signature, identity, timestamp, UUID, cursor, and digest they
  contain;
- missing, blank, malformed, duplicate, noncanonical, substituted, reordered,
  oversized, expired, future, or conflicting carriers;
- an authority receipt that is valid but not the latest receipt;
- invocation timing, frequency, duplicate verification, and concurrent
  verification;
- every ordinary decoding, parsing, validation, and cryptographic exception;
  and
- a caller-supplied object that resembles the private verified-result type.

No untrusted input selects the observer key, signature algorithm, signature
domain, digest algorithm, JSON algorithm, audience, schema, purpose, callable,
page count, row ceiling, byte ceiling, public result surface, retry count, or
external effect.

### 4.4 Explicitly excluded attacker capabilities

This contract does not claim protection against:

- compromise of the observer private key or either selected approver private
  key;
- malicious or incorrect authority-receipt issuance by the trusted observer;
- a compromised trusted caller supplying false `now_us`;
- arbitrary in-process mutation, reflective object traversal, private-symbol
  access, or arbitrary code execution;
- local source, bytecode, interpreter, dependency, import-system, or filesystem
  substitution after repository/package admission;
- debugger, ptrace, process-memory, core-dump, host, operating-system, or
  hardware compromise; or
- later admission, credential, database, export, or output-authority compromise.

Ordinary hostile carrier bytes, stale but unexpired receipts, duplicate
verification, malformed cryptographic material, and supported invocation
ordering remain in scope.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Observer trust root | One exact 32-byte public key fixed for the verifier instance by future trusted composition |
| Presented approver set and identity/domain mapping | One valid observer-signed authority receipt |
| Authority currentness | Receipt interval compared with trusted `now_us` |
| Operation identity and scope | One canonical export-request payload |
| Export purpose, callable, page count, row and byte ceilings | Existing checked-in audit-contract constants plus fixed page count `1` |
| Cursor | `null` or exact `SecurityAuditAccessCursor.parse()` round trip |
| Each approval | One Ed25519 signature over one exact domain-framed canonical statement |
| Two-person independence | Pairwise inequality of selected approver ID, key ID, and independence domain |
| Receipt/request/statement binding | Exact SHA-256 digests defined below |
| Point-in-time verification | Trusted `now_us` supplied to `verify()` |
| Durable single-use admission | No authority in this slice |
| Temporary credential lifecycle | No authority in this slice |
| Disclosure and output delivery | No authority in this slice |

There is no unsigned authority list, per-invocation observer-key override,
latest-head fallback, tenant-authority fallback, algorithm negotiation,
compatibility alias, mutable registry, self-attested verified object, alternate
request schema, generic signature surface, or boolean approval input.

## 6. Protocol, state machine, and ordering

### 6.1 Exact public interface

The module exposes exactly:

```python
__all__ = (
    "SecurityAuditApprovalRefused",
    "SecurityAuditDualApprovalVerifier",
)
```

The supported interface is:

```python
class SecurityAuditDualApprovalVerifier:
    def __init__(self, observer_public_key: bytes) -> None: ...

    def verify(
        self,
        authority_receipt_bytes: bytes,
        approval_bundle_bytes: bytes,
        *,
        now_us: int,
    ) -> _VerifiedSecurityAuditApproval: ...
```

Construction accepts only exact `bytes` of length 32. Any ordinary
construction failure uses the fixed refusal protocol in section 6.11.

`_VerifiedSecurityAuditApproval` is module-private, frozen, slotted, omitted
from `__all__`, and has exactly these normalized fields and Python types:

```python
schema_version: str
operation_id: UUID
authority_receipt_digest: str
request_digest: str
approval_digest: str
valid_from_us: int
valid_until_us: int
cursor: SecurityAuditAccessCursor | None
approver_ids: tuple[str, str]
key_ids: tuple[str, str]
independence_domains: tuple[str, str]
```

Its private naming is source-surface hygiene, not an authorization mechanism.
A later admission boundary must never trust a supplied result object.

### 6.2 Exact protocol constants and bounds

```text
AUTHORITY_RECEIPT_SCHEMA =
  "ofarm.security-audit-break-glass-authority-receipt.v1"

EXPORT_REQUEST_SCHEMA =
  "ofarm.security-audit-break-glass-export-request.v1"

APPROVAL_STATEMENT_SCHEMA =
  "ofarm.security-audit-break-glass-export-approval.v1"

APPROVAL_BUNDLE_SCHEMA =
  "ofarm.security-audit-break-glass-approval-bundle.v1"

VERIFIED_APPROVAL_SCHEMA =
  "ofarm.security-audit-break-glass-verified-approval.v1"

AUDIENCE =
  "ofarm.security-audit-break-glass-export.v1"

AUTHORITY_SIGNATURE_DOMAIN =
  b"OFARM_SECURITY_AUDIT_BREAK_GLASS_AUTHORITY_RECEIPT_V1\x00"

APPROVAL_SIGNATURE_DOMAIN =
  b"OFARM_SECURITY_AUDIT_BREAK_GLASS_EXPORT_APPROVAL_V1\x00"
```

| Resource | Exact bound |
| --- | ---: |
| Authority envelope | 1 through 16,384 bytes |
| Decoded authority payload | 1 through 12,288 bytes |
| Approval bundle | 1 through 16,384 bytes |
| Decoded export request | 1 through 4,096 bytes |
| Each decoded approval statement | 1 through 2,048 bytes |
| Observer public key | 32 bytes |
| Each approver public key | 32 bytes |
| Each Ed25519 signature | 64 bytes |
| Authority entries | 2 through 16 |
| Approval entries | exactly 2 |
| Authority lifetime | 1 through 300,000,000 microseconds |
| Request lifetime | 1 through 300,000,000 microseconds |

Every timestamp and `now_us` has exact non-boolean Python type `int` and lies
from `0` through `9_223_372_036_854_775_807` inclusive.

### 6.3 Canonical JSON

Every outer carrier and decoded JSON segment must:

1. decode as strict UTF-8 without a byte-order mark;
2. reject duplicate object members;
3. reject `NaN`, infinity, and every non-JSON constant;
4. have exact root type `dict` and the exact member set selected below;
5. use only the permitted exact JSON types; and
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
object members, alternate numeric forms, extra members, and missing members
therefore refuse.

### 6.4 Canonical base64url, digests, and identities

A base64url segment is a non-empty exact ASCII `str` matching
`[A-Za-z0-9_-]+`, contains no padding, decodes with URL-safe base64 after only
internal calculated padding is added, and equals its unpadded URL-safe
re-encoding. Required decoded key and signature lengths are checked after
canonical decoding.

Every digest is exact text matching `sha256:[0-9a-f]{64}` and is computed as:

```text
"sha256:" + sha256(exact_bytes).hexdigest()
```

| Digest | Exact input bytes |
| --- | --- |
| `authorityReceiptDigest` | Entire canonical authority envelope |
| `requestDigest` | Decoded canonical export-request payload |
| `approvalDigest` | Entire canonical approval bundle |

Because both outer carriers must already be canonical, raw and canonical
carrier bytes cannot differ.

An approver key ID uses the repository's accepted RFC 7638-style Ed25519
thumbprint algorithm, reproduced locally without importing tenant authority:

```python
x = unpadded_base64url(public_key)
thumbprint_input = (
    b'{"crv":"Ed25519","kty":"OKP","x":"' + x + b'"}'
)
key_id = unpadded_base64url(sha256(thumbprint_input).digest())
```

The key ID is exactly 43 canonical base64url characters.

`approverId` and `independenceDomain` contain 1 through 128 ASCII bytes and
match `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}` exactly. An operation ID is a
lowercase canonical RFC 4122 UUIDv4 string that round-trips through `UUID` and
has version `4` and the RFC 4122 variant.

The request cursor is exactly one of:

```text
null
canonical 64-byte SecurityAuditAccessCursor text
```

A non-null cursor must parse and render through the existing cursor type
without any byte change.

### 6.5 Authority receipt

The canonical outer authority envelope has exactly:

```json
{
  "payload": "<canonical-base64url>",
  "signature": "<canonical-base64url>"
}
```

Its decoded canonical payload has exactly:

```json
{
  "approvers": [
    {
      "approverId": "<closed-id>",
      "independenceDomain": "<closed-id>",
      "keyId": "<derived-key-id>",
      "publicKey": "<canonical-base64url-32-byte-key>"
    }
  ],
  "audience": "ofarm.security-audit-break-glass-export.v1",
  "expiresAtUnixMicroseconds": 0,
  "observedAtUnixMicroseconds": 0,
  "schemaVersion": "ofarm.security-audit-break-glass-authority-receipt.v1"
}
```

Authority entries are sorted in ascending ASCII lexicographic order by
`(approverId, keyId, independenceDomain)`. Approver IDs are individually
unique, key IDs are individually unique, and independence domains may repeat
in the complete authority set. Every key ID must equal the exact derivation
from its decoded public key.

The interval must satisfy:

```text
observedAtUnixMicroseconds < expiresAtUnixMicroseconds
1 <= expiresAtUnixMicroseconds - observedAtUnixMicroseconds
    <= 300_000_000
observedAtUnixMicroseconds <= now_us < expiresAtUnixMicroseconds
```

The exact observer verification input is:

```text
AUTHORITY_SIGNATURE_DOMAIN + decoded_canonical_authority_payload
```

The observer signature must decode to exactly 64 bytes and verify under the
one configured observer public key. The key is never read from either carrier.

### 6.6 Export request

The approval bundle's decoded canonical request has exactly:

```json
{
  "audience": "ofarm.security-audit-break-glass-export.v1",
  "authorityReceiptDigest": "sha256:<lowercase-hex>",
  "cursor": null,
  "expiresAtUnixMicroseconds": 0,
  "functionIdentity": "ofarm_security.export_operational_security_events(uuid, timestamptz, uuid, integer, bigint)",
  "maxBytes": 8388608,
  "maxPages": 1,
  "maxRows": 2048,
  "notBeforeUnixMicroseconds": 0,
  "operationId": "<canonical-uuidv4>",
  "purpose": "DUAL_APPROVED_BREAK_GLASS_EXPORT_V1",
  "schemaVersion": "ofarm.security-audit-break-glass-export-request.v1"
}
```

The example shows the newest-page `null` cursor. The field's exact type is
`null | canonical 64-byte SecurityAuditAccessCursor text`; both forms are
supported.

The request must satisfy:

```text
authority.observed_at_us <= request.not_before_us
request.not_before_us <= now_us < request.expires_at_us
request.expires_at_us <= authority.expires_at_us
1 <= request.expires_at_us - request.not_before_us <= 300_000_000
```

Its authority digest must equal the digest of the exact presented authority
envelope. Purpose, function identity, page count, row ceiling, and byte ceiling
must equal the code-owned existing constants and fixed page count. No carrier
value selects an alternative.

### 6.7 Approval statements and bundle

Each decoded canonical approval statement has exactly:

```json
{
  "approverId": "<closed-id>",
  "audience": "ofarm.security-audit-break-glass-export.v1",
  "authorityReceiptDigest": "sha256:<lowercase-hex>",
  "independenceDomain": "<closed-id>",
  "keyId": "<derived-key-id>",
  "operationId": "<same-request-uuidv4>",
  "requestDigest": "sha256:<lowercase-hex>",
  "schemaVersion": "ofarm.security-audit-break-glass-export-approval.v1"
}
```

The statement's approver ID, domain, key ID, and verification key must resolve
to one exact presented authority entry. Its receipt digest, request digest, and
operation ID must equal the verified request values. There is intentionally no
claimed approval timestamp.

The exact approver verification input is:

```text
APPROVAL_SIGNATURE_DOMAIN + decoded_canonical_approval_statement
```

The canonical bundle has exactly:

```json
{
  "approvals": [
    {
      "signature": "<canonical-base64url-64-byte-signature>",
      "statement": "<canonical-base64url-statement>"
    },
    {
      "signature": "<canonical-base64url-64-byte-signature>",
      "statement": "<canonical-base64url-statement>"
    }
  ],
  "request": "<canonical-base64url-request>",
  "schemaVersion": "ofarm.security-audit-break-glass-approval-bundle.v1"
}
```

Approval entries are sorted in ascending ASCII lexicographic order by their
decoded `(approverId, keyId, independenceDomain)`. The two entries must have
different approver IDs, different key IDs, and different independence domains.
Both statements bind the same exact receipt, request, and operation.

### 6.8 Validation and signature-check ordering

The verifier has these valid states:

```text
UNVERIFIED
  -> AUTHORITY_VERIFIED
  -> REQUEST_AND_PAIR_VALIDATED
  -> FIRST_SIGNATURE_VERIFIED
  -> SECOND_SIGNATURE_VERIFIED
  -> VERIFIED

Any ordinary failure -> REFUSED
Any BaseException -> propagated unchanged
```

Ordering is exact:

1. validate exact input types, byte bounds, and `now_us` range;
2. decode and canonicalize the authority envelope and payload;
3. validate every authority field, entry, key ID, order, uniqueness, and time;
4. perform the one observer-signature check;
5. only after observer success, decode and canonicalize the approval bundle,
   request, both statements, and both signatures;
6. validate every request, digest, entry resolution, ordering, independence,
   and currentness rule before any approver-signature check;
7. verify approver signatures once in canonical approval order;
8. stop at the first invalid signature; and
9. after both succeed, compute the approval digest and return the private frozen
   result.

The deterministic cryptographic counts are:

| Outcome | Observer checks | Approver checks |
| --- | ---: | ---: |
| Invalid constructor key | 0 | 0 |
| Invalid input type/size or authority canonicalization | 0 | 0 |
| Structurally valid authority with invalid observer signature | 1 | 0 |
| Valid authority with malformed request or approval content | 1 | 0 |
| First canonical approver signature invalid | 1 | 1 |
| First valid and second invalid | 1 | 2 |
| Successful verification | 1 | 2 |

There are no retries or repeated signature checks. Every other iteration is
bounded by the carrier ceilings, at most 16 authority entries, and exactly two
approval entries.

### 6.9 Verified result and future admission handoff

The result contains normalized values only and computes:

```text
valid_from_us = request.not_before_us
valid_until_us = min(authority.expires_at_us, request.expires_at_us)
```

Repeated verification of equal bytes at an admissible `now_us` is
side-effect-free and returns equal normalized values. It does not consume the
operation or establish single use.

A future durable admission boundary must:

1. receive the original authority-receipt and approval-bundle bytes;
2. invoke this verifier itself using admission-owned trusted current time;
3. never accept a caller-supplied verified object as sufficient authorization;
4. immediately before atomic consumption require
   `valid_from_us <= trusted_admission_now_us < valid_until_us`;
5. atomically consume the exact pair `(operation_id, approval_digest)` before
   any credential creation; and
6. ensure an already consumed identical pair creates no second credential and
   authorizes no second export, while a different digest for the same operation
   ID is a conflict.

These are interface requirements for the later admission decision. This RFC
implements no persistence or credential transition.

### 6.10 Bounded revocation latency

This contract intentionally selects the smaller bounded-latency model. A key
is authorized when it appears in the presented, correctly signed, currently
valid authority receipt. The verifier does not prove that the receipt is the
newest issued receipt.

Removing a key from newly issued receipts becomes fully effective only after
every previously issued receipt containing that key has expired. Because the
verifier refuses any receipt whose lifetime exceeds five minutes, stale
authorization can survive for at most five minutes after removal. Immediate
revocation requires a separately approved latest-head design with another
trusted current epoch or receipt digest.

### 6.11 Exact refusal protocol

There is one ordinary outward failure:

```python
class SecurityAuditApprovalRefused(RuntimeError):
    pass
```

Construction and verification emit only the exact class, never a subclass:

```text
type(error) is SecurityAuditApprovalRefused
error.args == ()
str(error) == ""
error.__cause__ is None
error.__context__ is None
```

For each ordinary dependency or validation failure, implementation must
classify refusal inside the handler, discard the dependency exception, leave
the handler, and only then construct and raise a fresh
`SecurityAuditApprovalRefused()`.

The null-context guarantee applies when construction and verification are
invoked outside every unrelated active exception handler. The contract does
not claim an impossible unconditional null context when a caller deliberately
invokes the API while handling another exception.

`KeyboardInterrupt`, `SystemExit`, and every other `BaseException` subclass
propagate unchanged. Production code performs no logging or diagnostic
formatting. Tests may format the fresh error with `capture_locals=False` and
must prove runtime-generated canaries are absent. No structural
non-reachability claim is made about locals in the fresh error's own active
traceback frame.

## 7. Invariants and acceptance criteria

### `DAV-001` — exact bounded carriers

Every outer carrier and decoded segment follows the exact schemas,
canonicalization, ordering, type, grammar, and size rules in section 6. No
alternate representation is accepted.

### `DAV-002` — one observer authority

The authority payload verifies under the verifier instance's exact configured
observer key, signature domain, schema, and audience. A carrier cannot select
or replace that key.

### `DAV-003` — point-in-time currentness only

The presented authority receipt and request are current and nested within the
fixed five-minute bounds at trusted `now_us`. No signature-production-time or
latest-head claim is made.

### `DAV-004` — fixed export request

The request fixes the accepted purpose, callable, `null` or canonical cursor,
one page, 2,048 rows, and 8,388,608 bytes. Any widening or substitution
refuses.

### `DAV-005` — transitive exact-byte binding

Receipt, request, statements, and bundle bind through the exact digest inputs
in section 6.4. No raw/canonical ambiguity or caller-supplied digest authority
exists.

### `DAV-006` — exactly two signatures

Exactly two domain-separated Ed25519 signatures verify over their exact
canonical statements, and both statements bind the same receipt, request, and
operation.

### `DAV-007` — three-way independence

The two selected authority entries have different approver IDs, key IDs, and
independence domains.

### `DAV-008` — honest presented-receipt authority

Each selected key is present in the presented valid receipt. The verifier
claims no latest-head state and exposes the maximum five-minute stale
authorization interval.

### `DAV-009` — substitution refusal

Changing any bound byte, member, identity, key, cursor, timestamp, UUID,
constant, order, signature, or digest refuses without a result.

### `DAV-010` — one fixed ordinary failure

Every ordinary construction or verification failure emits the exact fresh
empty refusal protocol under the supported invocation posture. `BaseException`
is never converted.

### `DAV-011` — no effects

Construction and verification perform no database, filesystem, network,
process, clock-acquisition, random-ID, logging, credential, export, or output
operation.

### `DAV-012` — evidence is not admission

The private frozen result is normalized evidence only. Later admission must
reverify the original carriers with admission-owned time, recheck the complete
validity interval, and durably consume the exact operation/digest pair.

### `DAV-013` — fixed cryptographic work

Every success performs exactly one observer-signature check and two
approver-signature checks. Every refusal performs at most one observer check
and at most two approver checks. Observer failure permits no approver check.
Approver signatures are checked once in canonical order and short-circuit at
the first invalid signature. There are no retries or repeated signature
checks; every other iteration is bounded by the fixed carrier ceilings, at
most 16 authority entries, and exactly two approval entries.

## 8. Production-entry negative cases

Every counterexample enters through the public constructor or `verify()`; no
private-field mutation or monkeypatching establishes the failure.

| Invariant | Concrete counterexample and required result |
| --- | --- |
| `DAV-001` | Blank/oversized carrier, duplicate JSON member, whitespace, padded base64url, extra member, wrong JSON type, unsorted entry, or overlong ID refuses. |
| `DAV-002` | A canonical authority receipt signed by an attacker key or naming another audience refuses before any approver check. |
| `DAV-003` | A future, expired, zero-duration, over-five-minute, or non-nested receipt/request refuses. |
| `DAV-004` | `maxPages=2`, `maxRows=2049`, another byte ceiling, purpose, function, or noncanonical cursor refuses. |
| `DAV-005` | Valid statements moved to another authority envelope or request refuse because exact digests differ. |
| `DAV-006` | One approval, three approvals, cross-request statements, or an invalid first/second signature refuses with the fixed count. |
| `DAV-007` | Two keys for one approver, one key reused, or two approvers in one independence domain refuse before approver crypto. |
| `DAV-008` | A key absent from the presented receipt refuses; a key in an older still-valid receipt remains accepted only until that receipt expires. |
| `DAV-009` | Changing one cursor, timestamp, operation-ID, identity, key, order, or signature byte after signing refuses. |
| `DAV-010` | Invalid root bytes, JSON, base64url, key, or signature produces the exact empty unlinked refusal; `KeyboardInterrupt` propagates. |
| `DAV-011` | Runtime and AST canaries prove zero external calls, alternate clocks, random UUID generation, logging, output, or persistence. |
| `DAV-012` | Equal bytes may verify twice, but the result has no consumption claim; a simulated later caller-supplied result is explicitly insufficient. |
| `DAV-013` | Deterministic fakes record `0/0`, `1/0`, `1/1`, `1/2`, and success `1/2` at the selected failure points without retry. |

## 9. Proposed architecture and smallest change

### 9.1 Components

Phase B would add one module,
`deployment/postgresql/security_audit_approval.py`, containing:

- fixed protocol constants and bounds;
- one private duplicate-member-rejecting canonical JSON decoder;
- one private canonical base64url decoder/encoder;
- exact digest, UUID, ID, cursor, authority, request, statement, bundle, and
  signature validators;
- immutable private normalized carriers and verified result as needed;
- the one fixed refusal class; and
- the one verifier configured with the observer public key.

It imports the existing export constants and cursor type without modifying
them. It does not import tenant signing authority or extract a generic crypto
framework.

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
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)

from deployment.postgresql.audit_contract import (
    EXPORT_ACCESS_PURPOSE_IDENTITY,
    EXPORT_FUNCTION_IDENTITY,
    EXPORT_MAX_BYTES,
    EXPORT_MAX_ROWS,
)
from deployment.postgresql.security_audit_access import (
    SecurityAuditAccessCursor,
)
```

The architecture checker compares every `Import` and `ImportFrom` node against
that exact normalized statement-and-symbol allowlist. Any additional module,
symbol, alias, star import, whole-module internal import, or relative import
refuses.

It also forbids these names or calls:

```text
__import__
eval
exec
compile
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
```

Focused AST evidence must prove that only `UUID` is imported from `uuid`, only
`SecurityAuditAccessCursor` is imported from the shared access module, only the
four fixed constants are imported from the audit contract, no dynamic import
or clock-producing call exists, `now_us` is not overwritten, and every
authority/request freshness comparison uses that parameter.

Within the supported non-reflective source model, `now_us` is therefore the
sole currentness authority. Arbitrary reflective traversal remains explicitly
out of scope under section 4.4.

### 9.3 Architecture-budget registration

Phase B must add one mechanically derived production-module budget and the
exact direct-import bound below. After the production module is complete, its
registered `MODULE_BUDGETS` value must equal the architecture checker's
physical line count for that module at the exact Phase B head and must be no
greater than `700`. The placeholder below describes that mechanical
substitution; no placeholder may be committed:

```text
MODULE_BUDGETS[
  "deployment/postgresql/security_audit_approval.py"
] = <FINISHED_MODULE_LINE_COUNT_NOT_GREATER_THAN_700>

DIRECT_IMPORT_BOUNDS[
  "deployment/postgresql/security_audit_approval.py"
] = {
  "deployment.postgresql.audit_contract",
  "deployment.postgresql.security_audit_access",
}
```

The exact import-statement allowlist and forbidden-name checks in section 9.2
also belong to this module's architecture registration. Phase B must not add a
single-member `GROUP_BUDGETS` entry: it would duplicate the exact module
budget without constraining another source file. Phase B must not change
`TEST_GLOBS` or `MAX_TEST_LINES` for this slice. The one exact test path in
section 11.1 is bounded by the closed path envelope and required evidence, not
by the shared 800-line cap used for existing test families. No dependency-lock
path is permitted because the required cryptography version is already pinned.

### 9.4 Why this is the minimum coherent design

The verifier needs one authority carrier, one request, two signatures, one
trusted time, and one result. Removing any of those loses a required authority
or binding. Adding persistence, role mutation, credential custody, output, or
runtime composition would cross an independent trust boundary.

Embedding approval logic in the bounded export runner would combine
authorization and privileged disclosure and make it possible to mistake an
in-memory result for durable admission. Importing tenant signing authority
would cross the pre-tenant/tenant boundary. A small isolated verifier is the
minimum coherent prerequisite.

## 10. Elegance audit

There is exactly one source of truth for each decision:

- observer key for receipt authenticity;
- presented signed receipt for the bounded approver mapping;
- canonical request for the operation;
- two canonical signed statements for approvals;
- checked-in constants for export scope;
- `now_us` for point-in-time currentness; and
- the future admission store, explicitly absent here, for durable single use.

There is one authoritative verification transition point: `verify()`. There
is no duplicate request state, mutable registry, generic capability bag,
compatibility surface, caller-selected protocol, identity comparison used as a
bearer capability, or alternate write path.

No existing production code is deleted. A clean new module is better than
modifying the export runner because the accepted runner deliberately owns only
one access-intent-plus-page disclosure transition.

## 11. Pull request and approval boundary

### 11.1 Normative technical path envelope

Phase B may change exactly these six paths:

1. `docs/rfcs/OFARM_Security_Audit_Dual_Approval_Verification_RFC_v0_1.md`
2. `deployment/postgresql/security_audit_approval.py`
3. `deployment/postgresql/README.md`
4. `kernel/tests/test_security_audit_approval.py`
5. `conformance/rewrite_architecture_check.py`
6. `conformance/review_baseline_test_inventory.json`

Phase A publication changes only path 1. Adding, renaming, or changing any
other path before exact approval or any seventh path during Phase B stops work
for a new decision version.

### 11.2 Dependencies

- current `main` at reviewed base
  `a203110ed049de93695922aefb750588e895caf2`;
- merged bounded-export PR #318 and its existing fixed constants, cursor, and
  one-page primitive;
- the accepted security-audit migration and provisioning posture, unchanged;
  and
- the already pinned cryptography dependency.

Issue #172 is closed. No issue #176 branch, pull request, model, storage,
approval workflow, or temporal behavior is a dependency.

### 11.3 Reviewer non-requirements

Reviewers must not require this pull request to:

- implement approval issuance, immediate revocation, latest-head authority, or
  production observer-root composition;
- add durable admission, migration, operation-consumption state, or replay
  semantics beyond the future interface requirement;
- create or close a temporary LOGIN or credential;
- call the export runner, page cumulatively, or deliver output;
- change runtime health/readiness, recovery, KMS, authentication, tenant, or
  deployment authority; or
- claim production readiness or close issue #192.

Those are Follow-ups, not review fixes.

### 11.4 Follow-ups

- trusted observer-root and authority-receipt issuance/currentness composition;
- durable one-operation admission for `(operation_id, approval_digest)`;
- temporary export-login creation, bounded credential custody, revocation,
  session termination, drop, and verified structural closure;
- protected output delivery after closure;
- verified empty-recreate/store-loss handling; and
- final real-ASGI/PostgreSQL hostile and cross-slice closure evidence.

### 11.5 Stop and reapproval conditions

Stop before editing if implementation or review requires:

- another carrier member, schema, signature domain, digest input, algorithm,
  time source, authority input, validity model, or revocation claim;
- immediate revocation or latest-head authority;
- a database transition, credential, role, export call, output, runtime
  composition, deployment configuration, or production key;
- importing tenant signing authority or an additional dependency;
- a path outside section 11.1 or a second approval-verification test path;
- a finished production module above 700 physical lines, a registered module
  budget different from its exact finished line count, a new single-member
  group budget, or any `TEST_GLOBS` or `MAX_TEST_LINES` change for this slice;
  or
- changing the primary trust boundary or materially altering an invariant.

Such evidence requires a new Phase A decision version or a separate stacked
trust-boundary pull request.

## 12. Provisional design record

This design is provisional before deployment.

It is acceptable because the verifier remains library-only, has no configured
production trust root, performs no I/O or mutation, cannot create a database
route or credential, and cannot disclose data. It provides a concrete
cryptographic carrier and verification seam for later decisions without
claiming that those decisions exist.

Evidence requiring redesign includes:

- inability to obtain two approvals within the five-minute receipt/request
  window;
- a production requirement for immediate key revocation;
- evidence that protected delivery must be bound into this approval schema;
- a requirement for an independently trusted signature-production timestamp;
  or
- a supported runtime that cannot enforce the exact canonical or source-import
  rules.

The likely upgrade path is an intentionally new schema and decision version,
not a compatibility alias or permissive parser. Production observer-root
composition, durable admission, credentials, disclosure, and delivery remain
separate reviewed boundaries.

## 13. Traceability and verification

| Invariant | Owning prospective code | Negative evidence | Smallest verification |
| --- | --- | --- | --- |
| `DAV-001` | canonical carrier helpers | malformed, duplicate, noncanonical, oversized carriers | focused unit matrix |
| `DAV-002` | authority validator/verifier | attacker root, wrong domain/schema/audience | real Ed25519 vectors |
| `DAV-003` | exact time validators | future, expired, overlong, non-nested windows | boundary-value unit matrix |
| `DAV-004` | request validator plus existing constants/cursor | every constant/cursor substitution | focused unit matrix |
| `DAV-005` | digest helpers and binding validator | cross-receipt/request/bundle substitution | exact digest vectors |
| `DAV-006` | statement and signature verifier | wrong count, cross-request, invalid signatures | real Ed25519 vectors |
| `DAV-007` | pair validator | same approver, key, or domain | focused pair matrix |
| `DAV-008` | presented-receipt validator | absent key and older-receipt expiry | bounded-latency time matrix |
| `DAV-009` | complete validation pipeline | mutate every bound field/byte/order | hostile substitution matrix |
| `DAV-010` | public constructor/verifier refusal mapping | dependency canaries and active-handler posture | exact error/trace formatting tests |
| `DAV-011` | module source and architecture guard | forbidden imports/names/calls and runtime canaries | AST plus runtime tests |
| `DAV-012` | private result and documentation | supplied fake result and repeated verification | public-surface/type/docs tests |
| `DAV-013` | ordered signature state machine | each deterministic failure point | exact call-count tests |

### 13.1 Phase A verification gates

- RFC is the only changed path;
- reviewed base remains current `main` or integration changes are mechanical
  and explicitly recorded;
- the complete contract passes repository package conformance;
- the draft pull request receives one independent exact-head review;
- every demonstrated Phase A Blocker is corrected in this RFC; and
- a live decision card is shown only after exact-head review reports zero
  demonstrated Blockers.

### 13.2 Prospective Phase B verification gates

- reproduce this invariant table before editing;
- run focused approval-verification tests;
- run architecture conformance with the exact module/group/import guards;
- run Ruff or the repository's equivalent Python lint for all changed Python;
- regenerate the review-baseline inventory mechanically;
- run `python3 conformance/ofarm_pkg_contract_check.py` before every commit;
- inspect the exact six-path diff; prove the registered production-module
  budget equals the finished line count and is at most 700; and prove no group
  budget, test glob, or shared test-line limit changed for this slice;
- obtain hosted exact-head conformance and required architecture lanes; and
- receive bounded implementation review with zero demonstrated in-scope
  Blockers before merge.

No live PostgreSQL fixture is required for this pure verifier. Adding database
I/O to prove it would violate `DAV-011` rather than strengthen this slice.

## 14. Open decisions and review disposition

### 14.1 Open material decisions

No material decision remains open inside this Phase A boundary. The following
are deliberately deferred and must not be answered by implementation:

- production observer-root selection and authority-receipt issuance;
- immediate revocation versus the selected maximum five-minute latency;
- durable consumption and exact replay-result protocol;
- temporary-login and credential lifecycle;
- output-recipient binding and protected delivery; and
- store-loss and final hostile closure evidence.

### 14.2 Review disposition

- **Prepublication Blockers:** successive review found four underspecified wire,
  revocation, admission-handoff, and refusal issues; one signature-count
  contradiction; and one static-currentness loophole. This consolidated RFC
  adopts exact schemas and bytes, bounded revocation latency, non-bearer
  handoff, one fixed refusal, deterministic short-circuit counts, and exact
  imported-symbol enforcement. No known design Blocker remains.
- **Independent exact-head review:** two reviewers disagreed at published head
  `e4a00083e0f556062f783de28ee7042882311c07`. One found no demonstrated
  Blocker. The other identified the predicted 520-line production budget and
  the single permitted test file's inherited 800-line cap as a Phase B stop
  risk. This revision replaces the predicted production number with an exact
  finished line count under a fixed 700-line ceiling, removes the redundant
  group registration, and forbids test-glob or shared-cap changes. Focused
  exact-head re-review of that correction is pending.
- **Follow-ups:** section 11.4 only.
- **Preferences:** none.

Once every `DAV-001` through `DAV-013` invariant passes and no demonstrated
in-scope Blocker remains, the approved workflow may permit Phase B only after
the exact later task-user approval described below. New ideas, Preferences,
and unrelated hardening remain Follow-ups and do not widen this decision.

## 15. Phase A approval boundary

This RFC grants no Phase B authority by authorship, local review, commit, push,
pull-request creation, GitHub review, or repository credentials. It must first
be bound to one already-created draft pull request and receive an independent
exact-head Phase A review with zero demonstrated in-scope Blockers. The AI must
then display one complete live decision card in the same Codex task.

Only the exact entire text of a later task-user message matching the live
card's approval sentence can authorize Phase B. Generic approval, the current
publication authorization, GitHub activity, an AI message, delegation, another
task, or a summary of lost task items does not authorize implementation.

The prospective exact approval form is:

```text
I approve OFARM2 decision ISSUE192-SECURITY-AUDIT-DUAL-APPROVAL-VERIFICATION-001 version 1.
```

If later shown in a complete live card and supplied as the exact entire later
task-user message, that approval would authorize only in-envelope repository
implementation, tests, documentation, mechanical inventory regeneration,
review handling, commits, pushes, and eventual merge in the one named draft
pull request after every gate passes. It would authorize no approval issuance,
production trust root, durable admission, migration, temporary LOGIN,
credential, export operation, output delivery, deployment, release, issue #192
closure, or security waiver.
