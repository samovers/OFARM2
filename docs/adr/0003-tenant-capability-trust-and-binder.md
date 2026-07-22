# ADR 0003: TenantCapability trust and database binder

**Status:** Accepted for implementation

**Decision class:** Package-local security and implementation architecture

**Date:** 2026-07-19

**Decision issue:** GitHub #200

**Accepted proposal head:** `a721a7d3a51feb07e09abfd00d237b7d1a72afd3`

**Parent architecture:** GitHub #169 and ADR 0001

**Implementation coordination:** GitHub #172, #173, and #174

**Operational-security consumer:** GitHub #192

**Recovery follow-on:** GitHub #193

This ADR does not amend OFARM law, promote a contract, activate a profile, or
change a capability claim. It selects the production trust model needed to
finish ADR 0001's hardened tenant binder. It is accepted for implementation,
but production tenant binding remains unavailable and fails closed until its
implementation evidence passes.

## Context

ADR 0001 requires a short-lived, signed, single-use `TenantCapability`. The
capability connects three separately owned steps:

1. #172 verifies an external identity and resolves one exact immutable
   principal-binding version and authoritative lifecycle head.
2. #174's database binder independently verifies the resulting capability and
   installs one transaction-local `TenantBinding`.
3. #173 keeps challenge creation, binder invocation, governed work, commit or
   rollback, and connection-pool return on one checked-out PostgreSQL backend
   and one full transaction identity.

The capability cannot be replaced by caller-supplied fields marked "verified".
An attacker with application SQL access could forge those fields. Nor can the
database verifier hold a symmetric MAC secret: a component able to verify an
HMAC can also mint one. That would put signing authority inside the database
trust boundary and would make compromise revocation difficult to distinguish
from graceful rotation.

PostgreSQL 17's supplied `pgcrypto` module provides hashes, HMACs, encryption,
and random-data functions, but exposes no detached asymmetric-signature
verification API. A database-verifiable asymmetric capability therefore needs
a narrowly scoped verification implementation in addition to the supplied
module.

## Decision summary

V1 uses Ed25519 over one exact JWS Signing Input. The JWS payload is a closed
binary frame, not JSON. The 64-byte signature is appended only after signing;
it is not part of the bytes being signed. #172's signer holds a non-exportable
private key outside PostgreSQL. #174 stores only public verification keys and
installs a minimal verification-only PostgreSQL extension plus the hardened
binder.

Public keys are immutable candidates. Authority comes only from an append-only,
digest-chained key lifecycle with expected-head transitions and fixed database-
time rules. The lifecycle supports initial activation, atomic rotation, and no-
overlap emergency revocation effective at its serialized commit boundary.
Graceful rotation permits the retiring key to verify capabilities carrying its
bounded old-key times for exactly the half-open window defined below; production
minting stops before the cutover, but the binder cannot observe physical signing
time.
A durable append-only admission-close act commits before an emergency
revocation wait begins, so cancellation or backend loss cannot reopen
admission.

Every capability is bound to one fresh database challenge, one installation
audience, one backend incarnation, and one full xid8. It has a maximum lifetime
of 60 seconds and at most five seconds of future-clock leeway. A signature is
necessary but never sufficient: the binder also reconstructs the authoritative
principal-binding and key lifecycle state and compares every immutable tenant
and Party identity and digest.

## Trust boundary and custody

### Private signing key

The only accepted V1 production custody profile is a Google Cloud KMS HSM
asymmetric-signing key version with purpose `ASYMMETRIC_SIGN`, algorithm
`EC_SIGN_ED25519`, and protection level `HSM`. Cloud KMS generates the key
inside its boundary; raw private material cannot be viewed or exported. The
exact project, location, key ring, key, key-version resource, public key,
attestation, algorithm, purpose, protection level, and enabled/disabled state
are pinned in #172's startup evidence. Another cloud KMS, software key, external
key manager, local HSM, Vault, file, environment secret, or isolated signer is
not an equivalent fallback; adopting one requires a new architecture decision.

The signing call supplies the exact JWS Signing Input through the Cloud KMS
raw `data` field, never the `digest` field, and includes CRC32C. #172 accepts a
response only when the returned key-version name and protection level are
exact, `verifiedDataCrc32c` is true, and the signature CRC32C matches. It then
independently verifies the returned 64 bytes against the registered public key
before constructing the Compact token. `Ed25519ph`, a prehashed input, a KMS-
selected alternate algorithm, and a response from another key version refuse.

The production authentication principal has a custom role containing only
`cloudkms.cryptoKeyVersions.useToSign`. Google Cloud IAM policy is attached to
the parent CryptoKey because policy cannot be attached directly to a
CryptoKeyVersion. Its binding uses this exact condition after substituting the
pinned canonical version resource name:

```text
resource.type == "cloudkms.googleapis.com/CryptoKeyVersion" &&
resource.name == "projects/PROJECT_ID/locations/LOCATION/keyRings/KEY_RING/cryptoKeys/KEY/cryptoKeyVersions/VERSION"
```

No unconditional or inherited grant may give that principal `useToSign` on
this key, a sibling version, or another key. Deployment admission and every
rotation handoff inspect the effective policy through a separate read-only IAM
evidence path and refuse a missing, wider, differently conditioned, or
unaccounted grant. Hostile evidence must prove that the exact active version
signs while a sibling version and another key refuse. The signer cannot create,
import, export, inspect, enable, disable, destroy, rotate, administer, or change
policy for a key and cannot call PostgreSQL key-control functions.

A different lifecycle-observer principal has a custom role containing only
`cloudkms.cryptoKeyVersions.get` and
`cloudkms.cryptoKeyVersions.viewPublicKey`, under the identical exact-version
condition. A second binding, conditional on the exact parent resource type
`cloudkms.googleapis.com/CryptoKey` and its exact canonical resource name,
grants it only `cloudkms.cryptoKeys.get` so it can verify purpose. It validates
the exact names, purpose `ASYMMETRIC_SIGN`, state, algorithm, HSM protection,
HSM attestation, public-key CRC32C, and registered public key. It cannot sign,
change state, destroy, or change IAM policy. #172 consumes only a fresh verified
observer result; missing, stale, inconsistent, or wider evidence stops minting.

Public-key observation uses only Cloud KMS v1
`cryptoKeyVersions.getPublicKey` for the exact canonical key-version name with
`publicKeyFormat = DER` set explicitly. It accepts only an exact response
`name`, `algorithm = EC_SIGN_ED25519`, `protectionLevel = HSM`,
`publicKeyFormat = DER`, and present `publicKey.data` and
`publicKey.crc32cChecksum`. The default or
`PUBLIC_KEY_FORMAT_UNSPECIFIED` path, PEM, `pem`/`pemCrc32c`, an empty or second
key representation, and every format fallback refuse.

`publicKey.data` means the protobuf `ChecksummedData.data` octets after
transport decoding. REST base64 text is transport only, not key material; when
used, it must be canonical padded standard base64 whose decode and re-encode
are byte-identical. `publicKey.crc32cChecksum` must be present, parse as an
unsigned value from zero through `2^32 - 1`, and equal CRC-32C/Castagnoli over
the exact decoded DER octets. A checksum over JSON/base64 spelling, a missing,
negative, out-of-range, byte-swapped, or mismatched value refuses the whole
observation. A bounded retry fetches a wholly new response; fields from
different responses are never mixed and there is no PEM fallback. CRC32C is
transport-corruption evidence only, never resource, algorithm, protection,
state, IAM, purpose, attestation, or key-identity authority.

A separate audited KMS administrator controls key generation, state, IAM, and
destruction; a separate PostgreSQL key-control LOGIN controls database
candidate/lifecycle acts. These two control credentials and any administrator
able to widen inherited IAM are trust roots, are never shared with the signer
or observer, and must participate in activation, rotation, or compromise
response as applicable.

### Candidate-key preflight actor

The sole V1 candidate-key preflight actor is that already classified audited
KMS administrator, using its separate hardware-authenticated, time-bounded
control credential. It never uses the production authentication signer,
lifecycle observer, application, database, migrator, CI, or PostgreSQL
key-controller credential. The administrator has no standing `useToSign`
grant. KMS cannot constrain the bytes signed by this temporary authority; a
malicious administrator remains the signing-authority trust-root compromise
already accepted above, and any suspected compromise disqualifies and destroys
the candidate.

For one preflight only, an IAM Policy version-3 read/modify/write binds the
existing custom role containing only
`cloudkms.cryptoKeyVersions.useToSign` to the administrator's exact member
identity at the parent CryptoKey. Both addition and removal first call
`getIamPolicy` with exact `requestedPolicyVersion = 3`. A complete GET response
with any conditional binding must be version 3. A version-1 GET response is
accepted only when the authenticated request/response trace proves that exact
version-3 request and the complete returned policy contains no conditional
binding; version 0, an omitted version, or any other request/response pairing
refuses. This permits Google's documented lower version for a condition-free
policy without permitting a lower-version read to hide conditions.

Each mutation submits the complete policy through `setIamPolicy` with exact
`version = 3` and the returned etag, even when the preceding GET was the valid
condition-free version-1 case. The update changes only the exact preflight
binding and preserves every unrelated binding, member, condition, and audit
configuration without semantic change. It accepts only a complete mutation
response with a new etag and independently verifies a fresh GET made with exact
`requestedPolicyVersion = 3` under the same response-version rule. A mutation
response with conditions but a version below 3, missing etag, partial policy,
changed unrelated entry, stale write or retry without a complete fresh read,
or blind overwrite refuses.

The temporary condition contains both the candidate's exact CryptoKeyVersion
resource type/name test and a
`request.time < timestamp("PROBE_DEADLINE")` bound no later than ten minutes
after the grant. No unconditional, inherited, sibling-version, other-key, or
renewable permission is accepted.

```text
resource.type == "cloudkms.googleapis.com/CryptoKeyVersion" &&
resource.name == "projects/PROJECT_ID/locations/LOCATION/keyRings/KEY_RING/cryptoKeys/KEY/cryptoKeyVersions/CANDIDATE_VERSION" &&
request.time < timestamp("PROBE_DEADLINE_RFC3339_UTC")
```

The receipt fixes the substituted canonical resource and whole-second UTC
deadline bytes; a differently spelled, rounded, extended, or caller-rewritten
condition refuses.

The preflight signing input is exactly these 43 octets:

```text
004f4641524d322d54454e414e542d4341504142494c4954592d4b4d532d505245464c494748542d563100
```

This is `0x00 || ASCII("OFARM2-TENANT-CAPABILITY-KMS-PREFLIGHT-V1") ||
0x00`. The closed runner has no message argument and sends only these bytes in
the KMS raw `data` field with CRC32C; `digest` is absent. The NUL delimiters and
absence of JWS segment separators make the input structurally impossible to
parse as a TenantCapability JWS Signing Input. It is never base64url-wrapped,
combined with a protected header or capability payload, given a tenant
challenge, or passed to the binder.

The returned resource identity, protection level, data-verification flag,
signature CRC32C, 64-byte signature, and signature result are checked exactly
as for production signing. #172's independent verifier and the pinned database
extension both verify the signature against the extracted candidate key. This
proves the KMS key and two verification paths; it is not a live-binder success
and cannot be represented as one.

The executable preflight protocol is:

1. Create the non-exportable candidate with no production or temporary signing
   grant. Enable it only long enough for the observer to perform the exact DER
   public-key extraction below, register the resulting PostgreSQL candidate as
   inactive and never activated, then disable it. Prove neither the
   administrator nor production signer can sign with it.
2. Add the exact temporary binding through the full version-3 policy protocol
   using the current etag. A condition-free initial GET may validly return
   version 1 only under the response rule above; the `setIamPolicy` request is
   still version 3. Enable only the candidate version, and independently
   observe its exact resource, algorithm, HSM protection, and state.
3. Sign the fixed probe once and verify it through both independent paths.
   Prove the preflight actor cannot sign with the old version, another sibling,
   or another key, and that the production signer still cannot sign with the
   candidate.
4. While the PostgreSQL candidate remains inactive and the KMS version remains
   enabled, remove the exact binding through the same complete, version-3-write,
   etag-guarded policy protocol. If it was the sole conditional binding, the
   condition-free fresh GET may validly return version 1 under the response
   rule above. Inspect effective and inherited policy, then repeat the fixed
   probe with the same credential until KMS returns authorization refusal. A
   successful or uncertain call blocks rotation.
5. Disable the candidate, independently observe `DISABLED`, end the operational
   session and zeroize its bearer credential, and wait until both the recorded
   credential expiry and `PROBE_DEADLINE` have passed. Persist one canonical
   removal receipt. Any
   incomplete or uncertain cleanup blocks that candidate from activation until
   reconciliation; compromise disqualifies it permanently.

The removal receipt binds the candidate resource, `kid`, raw-key digest,
administrator member and operational-session identity without bearer material,
custom role and condition, parent CryptoKey, policy etags and canonical digests
before/during/after the grant including each exact GET request version, each
version-3 SET request, every actual GET and mutation response version, and every
preserved unrelated binding/audit configuration, enable/disable observations,
probe-byte digest, KMS response identity and CRC results, both verification
results, every negative-signing result, audit-log operation identities and
observer times, and its own canonical digest. `ROTATE` requires that exact
receipt digest. Reusing the existing administrator creates no new principal or
ADR 0001 role; the temporary raw-sign exception does not make it a production
signer.

Private material is absent from:

- PostgreSQL and every database role;
- application configuration, environment variables, migrations, fixtures, and
  release evidence;
- capability manifests, logs, traces, metrics, receipts, crash reports,
  queues, and pre-tenant security events; and
- the application, worker, readiness, migrator, binder, identity-control, and
  key-controller credential sets.

#174's test-only reference signer uses only published non-secret RFC test-vector
seeds or ephemeral keys generated inside the test process. No production key or
reusable production-like private fixture is checked in or built into an image.

Production and development/test use different audiences and different keys.
The fixture signer and its keys are structurally unavailable in production.
If the exact HSM key version, attestation, conditional permission evidence,
state, public key, raw-signature known-answer test, or database activation
receipt cannot be verified at startup and observed at its required cadence
through the fixed retirement time, #172 does not mint a capability. Reaching
the database-derived issuance end disables production signing before the
boundary; database refusal is not the sole expiry control. No FIPS or other
compliance claim follows merely from selecting HSM protection.

A fully compromised production signer can sign attacker-chosen bytes. A
compromised KMS administrator or PostgreSQL key controller can authorize an
attacker-controlled replacement key. Each is an explicit privileged-boundary
compromise. The database still checks its own challenge, current key lifecycle,
principal-binding lifecycle, tenant registration, and pinned Party tuple. These
checks limit accidental or stale output; they do not claim to defend against
arbitrary behavior by a trust root with current signing or key-control
authority.

### Public verification key

#174 adds exactly four non-tenant control relations to ADR 0001's closed list:

| Relation | Purpose |
| --- | --- |
| `tenant_binder_instance` | Immutable installation UUID, audience, creation evidence, and row digest. |
| `tenant_capability_verification_key` | Immutable public-key candidates and their exact KMS/HSM evidence. |
| `tenant_capability_key_lifecycle` | Append-only authoritative key and admission acts. |
| `tenant_capability_keyring` | One mutable reservation/fence and disposable projection of the append-only key/admission lifecycle head per audience. |

For `EC_SIGN_ED25519`, the accepted DER value is exactly this 44-byte RFC 8410
`SubjectPublicKeyInfo` encoding:

```text
30 2a 30 05 06 03 2b 65 70 03 21 00 || K
```

`K` is exactly 32 octets. The fixed prefix encodes one outer SEQUENCE, one
AlgorithmIdentifier containing only OID `1.3.101.112` (`id-Ed25519`) with
parameters absent, and one primitive BIT STRING with zero unused bits. The
extractor consumes the complete input. Wrong tags or OIDs, present parameters
including ASN.1 NULL, indefinite, long-form or otherwise non-minimal lengths,
a constructed or malformed BIT STRING, nonzero unused bits, a key other than
32 octets, truncation, trailing bytes, a certificate, PKCS#8/PrivateKeyInfo,
another BER/DER shape, or PEM refuses. No general-purpose parser normalization
or reserialization can create accepted bytes.

Only after metadata, CRC32C, and exact SPKI checks pass does unchanged `K`
become the public key. PostgreSQL stores exactly that raw 32-byte value per
immutable `tenant_capability_verification_key` row. A key candidate is not
authority merely because it exists. The candidate also stores:

- its derived key identity;
- the fixed algorithm identity `Ed25519`;
- the exact binder audience;
- the exact Google Cloud KMS resource identity, purpose, algorithm, protection
  level, SHA-256 digest of raw `K`, and independently verified attestation
  digest;
- a database-generated candidate identity and registration time;
- a canonical row digest covering every stored field; and
- no secret, mutable state, or caller-selected validity endpoint.

The same unchanged `K` is passed to strict point validation, the independent
verifier, the database extension, PostgreSQL candidate registration, and every
identity derivation:

```text
public_key_digest = SHA-256(K)
x = unpadded-base64url(K)
```

The key identity is the unpadded base64url SHA-256 JWK thumbprint defined by
RFC 7638 over the RFC 8037 Ed25519 public JWK. Its ASCII thumbprint input is
exactly:

```text
{"crv":"Ed25519","kty":"OKP","x":"<unpadded-base64url-public-key>"}
```

The member order, spelling, quoting, absence of whitespace, `x`, SHA-256
operation, and unpadded base64url output are fixed. The resulting `kid` is 43
ASCII bytes. A digest of the 44-byte DER value, PEM/base64 text, parsed library
object, or attestation evidence cannot substitute. PostgreSQL recomputes
`public_key_digest`, `x`, and `kid` from stored `K`, and compares raw bytes as
well as identities; digest equality alone is never authority.

### Verification-only database extension

#174 installs the content-addressed C extension `ofarm_ed25519` version `1.0`
against PostgreSQL 17.10 from the current exact base image:

```text
postgres@sha256:5f050f770b427fbd477edee6c3968a72e5c6be97e050a7e368b2b74a9494a285
```

The derived image builds libsodium 1.0.22 from the official
`libsodium-1.0.22.tar.gz` source archive with exact SHA-256
`adbdd8f16149e81ac6078a03aca6fc03b592b89ef7b5ed83841c086191be3349`.
The extension privately links the resulting static library. Its compilation
fails through explicit preprocessor `#error` guards if `ED25519_COMPAT` or
`ED25519_NONDETERMINISTIC` is defined. No package-manager version range,
dynamically replaceable libsodium, or unpinned replacement library is accepted.

Adding the shared library creates a new OCI artifact. A reproducible multi-stage
build produces one reviewed multi-platform derived image, and CI, provisioning,
runtime configuration, and evidence pin that image by its new digest. Production
never installs or compiles the extension at container startup.

The extension exposes exactly one SQL-callable function:

```sql
ofarm_crypto.ed25519_verify(
    public_key bytea,
    signed_bytes bytea,
    signature bytea
) RETURNS boolean
```

The function is `STRICT`, `IMMUTABLE`, `SECURITY INVOKER`, `PARALLEL UNSAFE`,
and not `LEAKPROOF`. It accepts exactly 32 public-key bytes, at most 8192 signed
bytes, and exactly 64 signature bytes. It returns only success or refusal.

The function first requires libsodium's
`crypto_core_ed25519_is_valid_point()` to accept both the public key and the
signature's 32-byte `R` value. Each must be a canonical curve point in the main
prime-order subgroup and not a small-order point. It then calls
`crypto_sign_verify_detached()` for PureEdDSA verification; that path also
requires a canonical scalar `S`. This deliberately rejects RFC 8032's more
permissive cofactored-verification edge cases, including identity, small-order,
or mixed-order public keys and `R` values. The narrower rule intentionally
refuses even an otherwise valid signature whose `R` is the identity point; V1
interoperability requires this strict-subgroup profile, not every signature that
the RFC equation could accept.

The non-SQL-callable `_PG_init` module-load hook calls `sodium_init()` and
accepts only its documented initialized/already-initialized results. An
initialization failure raises the fixed infrastructure error before the verifier
can be used.

It accepts no algorithm, library, key path, file, network, SQL, schema,
function, or configuration selector. It has no sign, key-generation,
private-key import, generic cryptography, dynamic loading, or diagnostic-detail
API. Wrong lengths, a non-prime-subgroup point, or an invalid signature return
false. Initialization, allocation, library-state, or other internal failures
raise fixed SQLSTATE `58000` with one constant safe message, abort the tenant
transaction, and map to a closed infrastructure-failure outcome; they never
masquerade as a bad credential or expose libsodium details.

The extension control file fixes `default_version = '1.0'`,
`module_pathname = '$libdir/ofarm_ed25519'`, `superuser = true`,
`trusted = false`, `relocatable = false`, schema `ofarm_crypto`, and an empty
`requires` set. The final ELF export allowlist is exactly `Pg_magic_func`,
`_PG_init`, `pg_finfo_ofarm_ed25519_verify`, and `ofarm_ed25519_verify`.
Static-library symbols are hidden and the final link export map admits no
libsodium API. The SQL function has exact `probin` `$libdir/ofarm_ed25519` and
exact `prosrc` `ofarm_ed25519_verify`.

One-time infrastructure provisioning creates
`ofarm_crypto_installer` as `SUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`,
`NOREPLICATION`, `NOBYPASSRLS`, `NOLOGIN`, and `NOINHERIT`, with no members or
administration path from any runtime or migrator role. A separately
authenticated cluster DBA may assume it only during the reviewed provisioning
step. That role creates and owns the locked `ofarm_crypto` schema, extension,
and function. Only it and an already trusted cluster superuser can install,
alter, replace, update, load, or drop them; both are explicit privileged
boundaries. `ofarm_migrator` cannot assume the role and the numbered migration
verifies rather than installs or repairs the extension.

PUBLIC access is revoked, and only `ofarm_binder` receives the exact EXECUTE
needed by the migration-owned binder. No other runtime role can invoke the
primitive directly. Database catalog attestation fingerprints extension
membership/version, schema, function signature/properties, `probin`, `prosrc`,
owner, grants, dependencies, and absence of unapproved SQL objects. Separate
deployment attestation pins both source archives and digests, exact libsodium
configure/compiler/linker flags, preprocessor guards, each per-platform static
library/shared-object/control/SQL digest, the final exported-symbol allowlist,
SBOM, OCI manifest and child digests, and a live known-answer test. PostgreSQL
self-reporting is not treated as proof of its own OCI or on-disk binary
identity.

If this extension or exact crypto build is absent, altered, wider than the
accepted surface, or not independently reviewed, production binding refuses.
There is no HMAC, application-only verification, or caller-asserted fallback.
The C function executes inside the trusted PostgreSQL process. A memory-safety
failure that gains arbitrary backend execution is process compromise, not an
RLS-contained event; that is why reproducible builds, fuzzing, sanitizers, and
independent C review are acceptance requirements.

## Exact JWS envelope

V1 accepts only JWS Compact Serialization with exactly three non-empty
unpadded-base64url segments separated by exactly two ASCII periods:

```text
BASE64URL(protected-header) || "." || BASE64URL(payload) || "." ||
BASE64URL(signature)
```

The complete serialized capability is at most 8192 ASCII bytes. The protected
header bytes are exactly this template, substituting the 43-byte key identity:

```text
{"alg":"Ed25519","kid":"<kid>","typ":"ofarm-tenant-capability+jws"}
```

The exact bytes passed to PureEd25519 are the JWS Signing Input:

```text
ASCII(BASE64URL(protected-header) || "." || BASE64URL(payload))
```

Only after signing are `"." || BASE64URL(signature_64)` appended to create the
Compact token. No implementation signs the signature segment, the decoded
payload alone, a digest of the Signing Input, or a reserialized header.

The fixed `Ed25519` value is the fully specified JOSE algorithm registered by
RFC 9864. The older polymorphic `EdDSA` value is not accepted. The `typ` value
is exact and case-sensitive. The binder rejects:

- `none`, HMAC, Ed448, `EdDSA`, or any other algorithm;
- an absent, unknown, malformed, or noncanonical key identity;
- an unprotected header or JWS JSON serialization;
- duplicate, missing, additional, reordered, differently cased, or
  whitespace-varied header members;
- `jku`, `jwk`, `x5u`, `x5c`, `x5t`, `crit`, or any indirect key selector;
- base64 padding, whitespace, alternate alphabets, non-zero trailing bits, or
  any encoding that does not round-trip to the identical canonical segment;
  and
- a wrong segment count, empty segment, non-ASCII input, or oversized token.

The database never retrieves a key from a token-supplied URL or embedded JWK.
It selects one locally registered public candidate by the untrusted header
`kid`, verifies the exact signature, then requires the identically framed
payload key identity and current authoritative lifecycle state before trusting
any capability field.

## Canonical payload

The JWS payload is an arbitrary octet sequence as allowed by RFC 7515. It is not
a JWT claims object and is never parsed as JSON. Its canonical bytes are:

```text
ASCII("OFARM_TENANT_CAPABILITY_V1") || 0x00
|| lp32(contract_digest)
|| lp32(challenge_id)
|| lp32(audience)
|| lp32(key_id)
|| lp32(equality_policy)
|| lp32(issuer)
|| lp32(subject)
|| lp32(binding_version_id)
|| lp32(binding_version_digest)
|| lp32(lifecycle_head_id)
|| lp32(lifecycle_head_digest)
|| lp32(tenant_id)
|| lp32(tenant_registration_digest)
|| lp32(party_ref)
|| lp32(party_record_kind)
|| lp32(party_record_id)
|| lp32(party_schema_digest)
|| lp32(party_payload_digest)
|| lp32(issued_at)
|| lp32(not_before)
|| lp32(expires_at)
|| lp32(nonce)
```

`lp32(x)` is the unsigned 32-bit big-endian byte length of `x`, followed by the
exact bytes of `x`. It applies even to fixed-width fields. There is no field
count, delimiter, optional field, implicit value, or trailing byte.

The encodings are:

| Field class | Exact bytes |
| --- | --- |
| Contract and content digests | Raw 32-byte SHA-256 values. |
| UUID | 16-byte RFC 4122 network order, equal to PostgreSQL `uuid_send`. The all-zero UUID is forbidden. |
| Audience, key identity, equality policy, Party fields | Exact governed ASCII bytes. |
| Issuer and subject | Exact UTF-8 bytes accepted under the binding version's frozen equality policy; no normalization or rewriting. |
| Time | Signed 64-bit two's-complement big-endian UTC microseconds since the Unix epoch. |
| Nonce | One cryptographically random UUIDv4 minted by #172 for this capability. |

### Exact V1 principal grammar

This ADR narrows ADR 0001's prose `OIDC_EXACT_UTF8_V1` issuer rule to one
closed ASCII subset so PostgreSQL and #172 cannot accept different principal
streams. The decoded issuer string is 1 to 2048 bytes and has this exact byte
grammar:

```text
issuer      = "https://" host [ ":" port ] path
host        = label *( "." label )
label       = ALNUM / ( ALNUM *61( ALNUM / "-" ) ALNUM )
port        = NONZERO-DIGIT *4DIGIT
path        = *( "/" *pchar )
pchar       = ALNUM / "-" / "." / "_" / "~" / pct-encoded /
              "!" / "$" / "&" / "'" / "(" / ")" / "*" / "+" /
              "," / ";" / "=" / ":" / "@"
pct-encoded = "%" HEXDIG HEXDIG
```

`ALNUM`, `DIGIT`, `NONZERO-DIGIT`, and `HEXDIG` are their ASCII byte sets.
Each label is at most 63 bytes, the complete host is at most 253 bytes, and the
base-ten port value must be at most 65535. A port has no sign, whitespace, or
leading zero. The grammar permits no userinfo, bracketed IP literal, query,
fragment, non-ASCII byte, control, NUL, backslash, or malformed percent escape.
An IPv4-looking value is treated only as dot-separated labels; V1 performs no
separate IP parser. All accepted spelling, host case, path bytes, and percent-
escape hex case remain exact and are never decoded, normalized, or rewritten.

The decoded subject is 1 to 255 bytes, each in ASCII `%x21-7E`, with no space,
control, NUL, normalization, or rewriting. #174's manifest supplies an
independent bounded byte scanner and tables, not a permissive POSIX regex or a
platform URL parser. #172 independently implements the same grammar. Shared
vectors run against live PostgreSQL and Python and include every boundary plus
`https://issuer.example.test:70000`, `https://[invalid`, userinfo, empty or
64-byte labels, leading-zero ports, query, fragment, non-ASCII, malformed
percent escapes, and all port values around 1 and 65535. Any outcome difference
blocks the migration baseline.

The contract digest is SHA-256 over the exact checked-in UTF-8 bytes of the V1
framing and validation manifest, excluding any self-digest field. That manifest
fixes the header template, payload order, field encodings and limits, time
constants, algorithm, audience and principal grammars, and shared accept/refuse
vectors. #174
owns these package-local manifest bytes, an independent reference codec, a
test-only fixture signer, and the live-PostgreSQL vectors required to freeze the
initial migration. That fixture is not production issuance and is absent from
the production image. #172 later consumes the same frozen bytes/digest and must
prove its independently implemented production codec and KMS signer produce
the same vectors; #172 is not a prerequisite for #174 to close. The payload key
identity must equal the protected-header `kid`. The audience must equal the
database's protected audience.
`party_record_kind` is exactly `ofarm.party.v0.1`, and `party_record_id` must
equal `party_ref`.

All digest inputs compare their source fields as well as their digests. JSON
serialization, delimiter joining, canonical JSON payloads, implicit database
casts, alternate UUID or time text, floating-point dates, omitted fields, and
unknown fields are forbidden.

## Audience and installation identity

Fresh provisioning creates one immutable random binder-instance UUID through a
hardened no-caller-value function. The exact audience is:

```text
urn:ofarm:tenant-binder:v1:<lowercase-canonical-uuid>
```

The protected singleton stores the instance UUID, derived audience, database
creation evidence, and a canonical row digest. Direct DML is denied and
mutation-forbid enforcement rejects update or deletion. The challenge function
returns the challenge and this derived audience; it does not accept an audience
argument. The binder derives and compares the expected audience from the
protected singleton, never from a setting, environment value, request, token
role, route, or caller-selected database field.

One production signing key is dedicated to one audience and environment. #172
verifies its configured audience and active signing-key receipt before enabling
issuance. A key or capability for development, test, another installation,
another service, or another token type refuses even if its signature is
cryptographically valid.

A physical clone carries the audience and public-key history. Audience equality
therefore proves neither continuity nor recovery safety. ADR 0001's negative V1
recovery posture still controls.

## Time contract

The database clock is authoritative for capability acceptance. The binder
observes `clock_timestamp()` exactly once, after the shared admission lock, all
row-lock waits, signature and payload validation, and fresh key/admission and
principal folds. It converts that observation to checked integer UTC
microseconds without floating-point arithmetic. No potentially blocking lock or
authority read occurs after this observation; the binder immediately evaluates
all time-derived key and capability rules and performs its guarded context
transition. A pre-wait observation or a value copied from transaction/statement
start refuses structural compatibility.

The fixed V1 bounds are:

| Bound | Value |
| --- | --- |
| Maximum capability lifetime | 60,000,000 microseconds |
| Maximum future-clock leeway | 5,000,000 microseconds |
| Maximum database challenge lifetime | 60,000,000 microseconds |
| Grace after capability expiry | None |

For database-observed `now` and protected `challenge_created_at`, every bind
requires:

```text
issued_at <= not_before < expires_at
expires_at - issued_at <= 60 seconds
challenge_created_at - 5 seconds <= issued_at
issued_at <= now + 5 seconds
not_before <= now + 5 seconds
now < expires_at
expires_at <= challenge_created_at + 60 seconds
now < challenge_created_at + 60 seconds
```

The implementation performs range checks before arithmetic so int64 extrema,
timestamp conversion, subtraction, or addition cannot wrap. Equality at the
five-second future boundary is accepted. Equality at `expires_at` or the
60-second challenge boundary refuses. There is no caller-selected leeway,
unbounded endpoint, post-expiry grace, refresh, or silent retry with changed
times.

## Public-key lifecycle

### Authority model

An immutable public-key candidate has no active flag. Authority is the fold of
one append-only, digest-chained keyring lifecycle. Each act contains:

- a database-generated act UUID and monotonic sequence;
- the exact prior act identity and digest;
- one of the closed kinds `ACTIVATE`, `ROTATE`, `CLOSE_ADMISSION`, `REVOKE`,
  or `RESUME_ADMISSION`;
- the affected old and/or new key identities and candidate-row digests;
- the incident identity, exact close receipt, and required KMS/IAM evidence
  digests for admission acts;
- for `ROTATE`, the exact candidate-key preflight removal-receipt digest;
- the exact audience and algorithm identity;
- database-observed decision and effective times, equal in V1;
- a derived accountable controller identity and closed reason code; and
- its own canonical digest.

The binder and every key or principal lifecycle transition require transaction
isolation exactly `READ COMMITTED`; their hardened entry points check and refuse
every other isolation level before reading security state. This requirement is
part of the security contract, not a performance default.

The binder is exactly `VOLATILE` and `PARALLEL UNSAFE`. Its advisory-lock call
and authoritative admission reconstruction are separate SQL statements, so the
reconstruction receives a fresh `READ COMMITTED` command snapshot after any
wait. A `STABLE` or `IMMUTABLE` binder, one statement combining the lock and
fold read, or a caller query snapshot retained across both steps refuses
structural compatibility. Provisioning and startup also require
`max_prepared_transactions = 0`; tenant transactions cannot become prepared
transactions that retain an admission lock without a live backend.

Except for the denial-only close operation defined below, before any row lock
or authority read those entry points acquire one reserved, database-local,
transaction-level advisory admission lock identified by the two signed int32
values `(1330004306, 1413694001)`, the ASCII domains `OFAR` and `TCB1`. The
binder calls only
`pg_catalog.pg_advisory_xact_lock_shared(integer, integer)`. Candidate
registration, `ACTIVATE`, `ROTATE`, `REVOKE`, `RESUME_ADMISSION`, every
principal lifecycle transition, and deterministic projection rebuild call only
`pg_catalog.pg_advisory_xact_lock(integer, integer)`. The shared or exclusive
lock is held until commit or rollback.

PostgreSQL's heavyweight lock manager checks a new request against conflicting
previously requested modes, not only granted modes. A later shared admission
therefore queues behind an already queued exclusive transition. PostgreSQL's
documented same-session re-entry exception cannot apply here: ADR 0001 revokes
every raw advisory acquisition function from PUBLIC and LOGIN roles; only the
fixed SECURITY DEFINER entry points receive the exact shared or exclusive
function privilege; no caller supplies a lock key; and no permitted entry point
acquires this reserved pair before its one required mode. Session-level, try,
unlock, bigint-key, alternate-key, and caller-visible admission functions are
forbidden. The exact grants, reserved pair, function bodies, and absence of any
other executable path are structurally fingerprinted.

The binder checks the one-way context before requesting the shared lock. After
that lock is acquired, every non-success raises an error that escapes the
binder; it cannot catch the error or return a normal refusal while retaining the
lock and `CHALLENGE`. Without a caller savepoint the transaction is aborted. If
a hostile caller catches the error by rolling back a surrounding subtransaction,
PostgreSQL releases the lock and every context change made in that
subtransaction before any retry. A retry therefore makes a fresh shared request
and cannot use same-holder re-entry to pass a queued exclusive transition.

Fresh provisioning creates one protected keyring fence row per audience. It may
carry the projected head identity/digest, but it is not lifecycle authority and
row locking it does not provide admission fairness. Every lock-taking entry
uses this global order:

1. the reserved transaction-level advisory admission lock;
2. the audience's keyring fence;
3. affected immutable public-key candidates in bytewise ascending `kid` order;
   and
4. the exact principal reservation, when the operation touches a principal.

The binder takes `FOR KEY SHARE` on the fence, its selected candidate, and the
principal reservation. A key transition takes `FOR UPDATE` on the same fence
and each affected candidate. A principal transition takes `FOR UPDATE` on its
reservation. No function may acquire an earlier class after a later class.

Admission is another output of the same authoritative act fold, never a mutable
flag. An empty key lifecycle is `CLOSED`. The first successful `ACTIVATE` makes
it `OPEN`; `ROTATE` preserves `OPEN`; `CLOSE_ADMISSION` makes it `CLOSED`;
`REVOKE` preserves `CLOSED`; and only a later `RESUME_ADMISSION` can make it
`OPEN` again. A replacement `ACTIVATE` after any earlier key history preserves
`CLOSED`. Missing, forked, malformed, overflowed, ambiguous, or projected-only
admission state denies binding. `OPEN` is not sufficient authority: the
signature, key eligibility, and principal fold still must pass.

`close_tenant_capability_admission(expected_head_identity,
expected_head_digest, affected_key, reason)` is the sole lock-order exception
and is denial-only. The incident, close-act, and receipt UUIDs are generated
inside PostgreSQL. In one exact `READ COMMITTED` transaction it reconstructs
the current fold, requires the caller's exact head and `OPEN` state, appends one
database-time
`CLOSE_ADMISSION` act, and conditionally updates the disposable projected head
only where it still equals the expected predecessor. It acquires no advisory,
candidate, or principal lock and uses no explicit tuple lock. The conditional
update changes no key column, so its `FOR NO KEY UPDATE` row change does not
conflict with binders' `FOR KEY SHARE`. A losing conditional update rolls back
the act. A binder that reconstructed `OPEN` before the close commit is ordered
earlier because it already holds the shared advisory lock; the following
exclusive transition must drain it. A binder's reconstruction whose command
snapshot begins after the close commit sees `CLOSED` and refuses.

`RESUME_ADMISSION` is not a generic update. Under the exclusive advisory lock,
it requires the exact unresolved incident, close act and expected current head,
one sole eligible uncompromised issuing key, verified KMS lifecycle and IAM
evidence, and a closed reason permitting resumption. It then appends one act;
there is no other reopen path. A failed, cancelled, rolled-back, uncertain, or
partially completed response cannot append it. Direct act/projection DML is
denied, and the exact kinds, transition matrix, owners, grants, conditional
head update, and denial behavior are structurally fingerprinted.

For closed reason `ROTATION_HANDOFF`, resumption additionally requires the
exact authoritative chain `ROTATE(old, new)`, `CLOSE_ADMISSION(old)`, then
`REVOKE(old)`, with the close incident and every expected head linked without a
gap. It recomputes that `old` is ineligible and `new` is the sole eligible key.
A close alone cannot reopen admission while the retiring key remains eligible,
even if KMS reports that key disabled or an active sign probe currently fails.

PostgreSQL verifies the registered candidate, evidence identities and digests,
and append-only transition; it cannot independently query Google Cloud. The
separate observer and deployment evidence path validate the external facts
before the key controller invokes resumption, and #172 revalidates them before
minting. A lying or compromised key controller can authorize an attacker key
and is already classified as a signing-authority trust-root compromise.

Each ordinary hardened key transition requires the caller's expected head
identity and digest. It first acquires those exact locks, then reconstructs and
validates the authoritative chain in a separate SQL statement, checks every
candidate, appends one act, and version-updates the fence's projected head in
one transaction. The binder reconstructs the key/admission fold in a separate
SQL statement immediately after its shared advisory call returns, and
reconstructs the principal fold in another statement after its row-lock waits.
Under
`READ COMMITTED`, those post-lock statements receive fresh command snapshots;
the fence and reservation must then equal the authoritative folds or the
operation refuses. A stale expected head, fork, gap, ambiguous fold, projection
mismatch, deadlock,
serialization anomaly, cancellation, or concurrent losing transition refuses.
Rollback publishes no candidate authority, act, or projection change.

The authoritative key and admission state is the complete act fold plus the
fixed time policy below at one database-time observation. The projection is a
disposable locator and concurrency fence only. Missing, corrupt, stale,
deleted, or time-obsolete projection state cannot authorize a signature and
can be rebuilt only from immutable candidates and acts. Direct SELECT or DML
is denied to the
application, worker, readiness, end-user, signer, and ordinary identity roles.
Only separate hardened registration, transition, and deterministic rebuild
functions are callable by the narrowly provisioned
`ofarm_capability_key_controller` role. It is exactly `NOSUPERUSER`,
`NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, `NOBYPASSRLS`, `NOLOGIN`, and
`NOINHERIT`. The distinct `ofarm_capability_key_control_login` is exactly the
same except `LOGIN` and `INHERIT`; its sole membership is the controller grant
with `INHERIT TRUE`, `SET FALSE`, and `ADMIN FALSE`. It can invoke only those
closed functions. It cannot sign, bind, read tenant truth, assume
`ofarm_binder`, administer `ofarm_crypto_installer`, or access private
material; the signer and KMS credentials have no PostgreSQL membership.

This control LOGIN is an explicit signing-authority trust root: possession can
register an attacker public key and make it database-active. Its credential is
separate, hardware-authenticated, time-bounded for transitions, dual-approved
operationally, and fully audited with expected-head receipts. Those controls do
not turn its compromise into an RLS-protected event. The accepted architecture
explicitly includes that residual privileged boundary.

### Activation and cryptoperiod

The first `ACTIVATE` is allowed only for an empty lifecycle in derived `CLOSED`
state. It changes one never-activated candidate to `ISSUING` and derives
`OPEN`. Every later `ACTIVATE` requires admission already `CLOSED`, no eligible
`ISSUING` key, and one exact unresolved close incident; it activates a new
candidate but preserves `CLOSED` until `RESUME_ADMISSION`. Natural retirement
does not silently authorize a replacement activation while admission is
`OPEN`: the bounded verification tail may finish, then the controller must
append `CLOSE_ADMISSION`, replacement `ACTIVATE`, and `RESUME_ADMISSION` in
their governed order. A key can be activated once and cannot be reactivated
after rotation, expiry, or revocation.

The issuance cryptoperiod is exactly `7,776,000,000,000` microseconds (90 times
24 hours), added to the database activation microsecond with checked integer
arithmetic. It is not a calendar interval and cannot vary with session timezone
or daylight-saving rules. The caller cannot choose, extend, or replace the
resulting issuance end.

For activation time `A`, retirement time `R`, and verification end `V`, the
authoritative half-open rules are:

```text
natural retirement: R = A + 7,776,000,000,000 microseconds
graceful rotation:  R = database rotation cutover
verification end:   V = R + 65,000,000 microseconds

issued_at >= A - 5,000,000 microseconds
issued_at <= R + 5,000,000 microseconds
expires_at <= V
database_now < V
```

The lower issuance bound applies to an initially activated or newly rotated
key. The upper bounds apply to natural expiry and graceful rotation. The key is
`ISSUING` only while `database_now < R`, is `VERIFY_ONLY` only while
`R <= database_now < V`, and is ineligible when `database_now == V`. These
fixed time rules apply even if a stale projection still says `ISSUING`. A
committed revocation makes the key immediately ineligible at the serialized
commit boundary and overrides every time window.

### Graceful rotation

`ROTATE(old, new)` is one atomic act. It requires `old` to be the sole
`ISSUING` key and `new` to be an inactive, never-activated candidate for the
same audience and algorithm. On commit:

- `new` becomes the sole database-eligible `ISSUING` key with its own 90-day
  issuance end;
- `old` becomes `VERIFY_ONLY` at the database cutover time; and
- `old` has a fixed verification end at cutover plus exactly `65,000,000`
  microseconds.

An old-key capability must satisfy the exact `A`, `R`, and `V` inequalities
above. The binder refuses the old key when database time equals `V`, even if
the capability carries a later expiry. A new-key capability must have
`issued_at >= cutover - 5,000,000` microseconds as well as satisfying the
ordinary capability-time contract. Neither database eligibility nor this lower
bound authorizes minting: the new KMS version, its production `useToSign`
binding, and #172 issuance remain disabled until the handoff barrier below.
The committed `ROTATE` receipt fixes `R`, `V`, both candidates, the resulting
head, and the exact preflight removal receipt.

The rotation procedure is:

1. Complete the candidate-key preflight protocol and receipt above. The
   candidate is registered but inactive, its KMS version is `DISABLED`, the
   temporary binding is absent, its deadline and credential have expired,
   active authorization refusal is proven, and the production signer has no
   candidate permission.
2. Quiesce #172 capability minting under `old` and record that state before the
   database cutover. A delayed worker, retry, or ambiguous quiescence blocks the
   transition.
3. Commit `ROTATE` with the exact expected lifecycle head and preflight receipt,
   then have #172 and the key controller verify the committed act receipt,
   derived `R` and `V`, and new head.
4. Request disablement of the old KMS version and removal of its production
   signing binding. Collect fresh metadata, effective/inherited-policy, audit,
   and active negative-signing evidence, but keep minting and the new KMS
   version disabled.
5. Choose the drain timing. For a graceful drain, keep the new signer and
   minting disabled while admission remains `OPEN` until a fresh observation
   from the intended PostgreSQL binder instance matches the exact `ROTATE` head,
   instance UUID, audience, `old`, `new`, `R`, and `V`, and reports database
   `clock_timestamp() >= old.V`. For an expedited cutover, do not wait for `V`.
   This observation preserves the intended verification tail but is not the
   handoff barrier.
6. In both timings, commit `CLOSE_ADMISSION` with the exact `ROTATE` head,
   `old`, and reason `ROTATION_HANDOFF`, then commit `REVOKE(old)` with that
   exact close incident and resulting head. Verify both committed receipts.
   This durable revocation is the sole V1 handoff barrier and remains
   authoritative across later clock movement. Admission stays `CLOSED`.
7. Only after the barrier and all required external evidence pass, enable the
   new KMS version, install its exact production signing binding, and verify its
   resource, policy, HSM, public key, raw-probe signature, and observer evidence.
   The old version may still sign despite provider metadata; committed database
   revocation, not that metadata or one time observation, makes its signatures
   ineligible.
8. Append and verify `RESUME_ADMISSION` under its exact rotation-handoff
   preconditions, recheck the authoritative head, and only then enable #172
   capability minting. No production-shaped preflight or live binder token is
   created before this point.
9. Schedule permanent destruction of the old private key; retain its public row
   and lifecycle acts permanently.

Cloud KMS key-state and IAM changes are eventually consistent. Their receipts,
observations, and negative probes are required operational evidence and may
prolong an outage, but they cannot shorten or substitute for step 6. The
65-second interval is a database verification tail equal to the 60-second
maximum capability lifetime plus five-second future-clock leeway, never a
period in which both production signers may mint binder-acceptable
capabilities. Availability does not justify enabling the new signer early.

### Emergency revocation

`REVOKE(key)` can target an `ISSUING` or `VERIFY_ONLY` key. For closed reason
`ROTATION_HANDOFF` it can also target the exact unrevoked `old` named by the
immediately governing `ROTATE(old, new)` after time has already made `old`
ineligible at `V`; no other expired-key selector is accepted. It has no
graceful overlap. Once the revocation transition requests the conflicting
exclusive admission lock, later bind attempts queue behind it. As soon as the
transaction commits, all queued and later binds under that key reconstruct the
new head and refuse regardless of `issued_at`, `not_before`, `expires_at`,
nonce, challenge, prior validity, or later clock movement.

`REVOKE` additionally requires the exact committed `CLOSE_ADMISSION` act, head,
and incident produced for this response. It refuses an open, stale, mismatched,
or caller-invented close. The close act authoritatively denies new admission but
does not itself claim the key is revoked; it is the durable fail-closed
precondition while the revocation act waits to commit.

The compromise procedure is:

1. Disable the affected KMS key version, its production signing permission,
   capability issuance, and tenant admission before requesting the database
   lock. Verify every disabled state; a suspected stolen key is not treated as
   neutralized merely because the managed signer is disabled.
2. Commit `close_tenant_capability_admission` in its own transaction and verify
   its exact act, head, and receipt. From this boundary every new binder refuses,
   even if the later revocation transaction is cancelled or loses its backend.
   An uncertain close commit is treated as closed until authoritative
   reconciliation proves its outcome.
3. Begin `REVOKE` with that close receipt and the current expected lifecycle
   head, then request the reserved exclusive advisory admission lock before the
   keyring row. Later binds queue behind that heavyweight-lock waiter.
4. Inspect the earlier bound transactions that block the transition and use the
   separately authorized, audited termination procedure when waiting is unsafe.
5. Commit the revocation, then independently verify its act receipt and new
   lifecycle head before changing the outage posture.
6. Schedule permanent destruction of the compromised KMS key version. Register
   and activate a fresh key only after the compromise boundary is understood;
   replacement activation preserves `CLOSED`.
7. After all `RESUME_ADMISSION` preconditions pass, append that separate act
   under the exclusive admission lock and verify its receipt before restoring
   tenant admission or production issuance.
8. Preserve the compromised public row and every incident act; never edit,
   delete, backdate, extend, or reactivate them.

Revocation does not require a replacement and may leave zero issuing keys. If
the revocation wait is cancelled, rolls back, times out, or has an uncertain
commit, issuance and tenant admission remain disabled until an operator proves
the head and safely retries or completes reconciliation. An unavailable
controller or signer likewise leaves a declared outage; no last-known-good or
unkeyed fallback exists.

The common advisory admission lock, row locks, global order, `READ COMMITTED`
requirement, and post-lock fresh statements above give bind versus revoke or
supersede one database order. A revocation requested after an earlier bind
waits for that already-bound UnitOfWork; later bind attempts cannot pass the
queued exclusive transition. Revocation does not retroactively rewrite a
completed binding. Inspecting and terminating blocking, already-bound sessions
is a separate audited emergency operational action and is required when
waiting is unsafe. Cancellation or rollback before commit means revocation has
not taken effect; the committed close act remains authoritative and the
declared outage continues until a committed head and separately proven resume
act exist.

## Binder protocol

After #173 begins an exact `READ COMMITTED` transaction on one checked-out
backend:

1. `create_tenant_challenge()` derives backend PID, backend start, and full
   xid8 inside PostgreSQL, creates a random challenge UUID, records database
   challenge time, and returns only the challenge and protected audience.
2. #172 verifies the external identity under its explicit production mode,
   exact issuer/audience/algorithm/key/time policy, and the
   `OIDC_EXACT_UTF8_V1` principal equality policy.
3. #172 resolves exactly one active immutable principal-binding version and
   authoritative lifecycle head, constructs the canonical payload, and asks
   only the active external private key to sign the exact JWS signing input.
4. #173 passes the complete JWS bytes unchanged as the binder's sole caller-
   supplied argument on the same backend and full xid8. The binder accepts no
   typed tenant, principal, public-key, time, digest, or "verified" argument.
5. The binder first verifies isolation, one-bind context, size, and syntax. It
   acquires the shared advisory admission lock in its own statement, then
   reconstructs the key/admission fold in a fresh statement. A non-`OPEN` or
   ambiguous fold aborts the transaction before any context becomes bound. It
   then acquires the fence/candidate locks, selects one local public candidate,
   verifies the Ed25519 signature, parses the canonical payload, acquires the
   principal reservation, and reconstructs the principal fold in a fresh
   post-lock statement. After every blocking operation and authority read, it
   takes the one database-clock observation and validates audience, times,
   time-derived key eligibility, exact lifecycle heads, version bytes/digest,
   tenant registration, and the pinned ACTIVE Party kind/identity/schema/payload
   tuple before the guarded context transition.
6. The binder changes exactly one protected current context row from
   `CHALLENGE` to `BOUND`, recording the verified tenant-binding fields,
   capability nonce and key identity, and the exact key and principal
   lifecycle heads used. It returns no tenant row, Party payload, public key,
   lifecycle data, or signature material.

The binder is fixed SQL with a fixed trusted search path and no dynamic SQL. It
executes as the reserved `ofarm_binder` NOLOGIN, NOINHERIT, BYPASSRLS role and
has only the minimum columns and functions required for this protocol. No LOGIN
role can inherit, assume, or administer that role. The application receives
EXECUTE only on the exact challenge, binder, current-context, and protected
tenant-lock functions.

Signature verification happens before untrusted payload fields can select a
principal stream, tenant, Party, or lifecycle row. The untrusted `kid` may
select only one public-key candidate from the closed key relation. All
authority-bearing fields are trusted only after signature verification and
then must equal authoritative database state.

## Replay, rollback, and concurrency semantics

The capability nonce is a random UUIDv4, but V1 does not need a database-global
nonce-consumption table. Single use comes from all of these conditions:

- the challenge is random and unique;
- its row is keyed by database-derived backend PID, backend start, and full
  xid8;
- the binder accepts only the challenge for its current backend and full xid8;
- the context permits exactly one `CHALLENGE` to `BOUND` transition; and
- a committed, rolled-back, restarted, or different-backend transaction cannot
  match that context identity.

The first successful bind is final. A second call, same or different nonce,
principal change, tenant change, reset, wrong challenge, cross-backend use,
cross-xid use, or use after backend restart refuses.

Rollback removes an uncommitted challenge or bound context. A replacement
transaction creates a new challenge, so the old capability cannot be retried.
Commit changes the full xid before any later checkout; a physically retained
UNLOGGED row cannot authorize a later transaction. An ambiguous commit does not
make capability replay idempotent: replay under a new xid refuses, and the
caller resolves the governed command through its separate durable idempotency
receipt.

A principal revocation/supersession or key rotation/revocation racing a bind is
serialized by the protected reservation locks. The binder rechecks both
authoritative folds after acquiring its locks. Exactly one ordering wins; a
stale snapshot or disposable projection cannot authorize.

#173 rolls back on binder refusal, exception, cancellation, timeout,
serialization retry, or finalization failure. It proves the connection is idle
before pool return and discards a connection whose state cannot be proven. Raw
capability bytes, credentials, identity fields, SQL details, and exception text
are not logged or sent to #192. Only a closed safe pre-binding outcome class
may cross to that separate audit lane.

## Recovery and rollback posture

A physical clone, snapshot, PITR target, or restored database can carry the
same audience, public keys, lifecycle acts, principal bindings, and migration
ledger. Those facts prove compatibility only. They do not prove that a key or
principal revocation tail, consumed challenge, receipt, or released output was
not lost.

V1 therefore exposes structural compatibility only. #174 returns no binder-
startup, continuity, recovery-readiness, service-ready, or promotion bit. The
deployment control plane must explicitly classify every clone, snapshot, PITR,
or restored target and refuse signer routing and tenant-service admission for
it. The database cannot detect a deliberately undeclared physical clone from
its copied state; matching signatures, schema, build, system identifier,
audience, or key head are not continuity proof. #193 must supply a separately
accepted non-rewindable witness before recovery promotion is supported.
The advisory admission lock is database-local and volatile; it is neither WAL
evidence nor cross-database coordination. The append-only admission close
survives an ordinary crash, but a copied or rewound close history remains the
same #193-owned continuity problem.

An older application binary against a newer key or binder contract fails
structural compatibility. A cryptographic algorithm, payload frame, key
lifecycle, or verifier implementation change requires a reviewed forward
migration and a new contract/domain identity; existing migration bytes and
historical acts are never rewritten.

## Ownership

### GitHub #172

#172 owns:

- explicit development, test, and production authentication modes;
- maintained external OIDC verification, including exact issuer, audience,
  algorithm, key, expiry, and not-before checks;
- exact principal equality and immutable binding-version resolution;
- production non-exportable signer integration and signer startup refusal;
- independently implemented production capability construction and KMS
  signature creation that exactly match #174's frozen manifest and vectors;
- key registration, rotation, admission close, revocation, replacement, and
  resumption orchestration through #174's hardened control API; and
- production signer-side and cross-layer golden-vector evidence.

#172 does not own #174 migration bytes, roles, database extension, key tables,
lifecycle authority, binder function, or transaction context.

### GitHub #174

#174 owns:

- the pinned verification-only Ed25519 extension and catalog confinement;
- the package-local framing/validation manifest, independent reference codec,
  test-only fixture signer, and baseline golden vectors;
- immutable binder installation identity and audience;
- immutable public-key candidates and append-only lifecycle acts;
- hardened registration, admission-close, transition, projection-rebuild,
  challenge, binder, current-context, and cleanup functions;
- exact key-controller and binder roles, grants, and denial posture;
- database-side canonical parsing, signature verification, lifecycle folds,
  and authoritative tenant/Party comparison;
- structural compatibility fingerprints; and
- real-role, live-PostgreSQL binder and hostile direct-SQL evidence.

### GitHub #173

#173 owns:

- one checked-out backend and transaction per UnitOfWork;
- challenge invocation after `BEGIN`;
- byte-exact delivery between #172 and #174 without reinterpretation;
- binder invocation on the same backend and full xid8;
- keeping bound context available through deferred checks and commit;
- rollback, cancellation, retry, finalization, and idle pool-return behavior;
  and
- real ASGI/pool concurrency and reuse evidence.

### Other boundaries

#192 consumes only closed safe pre-binding outcomes and does not persist
capabilities, identities, signatures, keys, or crypto errors. #193 owns any
future recovery promotion. This ADR adds no #184 reference semantics and makes
no production-readiness or deployment claim.

## Threat model

| Threat | Required control |
| --- | --- |
| Application SQL forges verified fields | Binder accepts only one Ed25519-signed canonical envelope and independently compares all authority fields. |
| Database verifier mints capabilities | PostgreSQL holds public keys only and exposes no signing primitive. |
| Algorithm or token-type confusion | Exact RFC 9864 `Ed25519`, exact `typ`, dedicated audience and key, and strict canonical protected header. |
| Header-directed key retrieval | No `jku`, embedded `jwk`, X.509 header, dynamic provider, file, or network selector. |
| Encoding ambiguity | Exact header template, canonical unpadded base64url, binary `lp32` payload, fixed field order and widths, and cross-layer vectors. |
| Cross-installation or fixture token reuse | Per-installation audience plus environment-dedicated keys; production fixture paths are absent. |
| Old or compromised key remains valid | One-use activation, exact integer issuance/verification bounds, a disabled replacement signer until committed close-plus-revoke, and no-overlap revocation at the serialized commit boundary. Provider metadata or a time observation alone is never the barrier. Earlier bound transactions are not retroactively cancelled. |
| Lifecycle projection is stale, forged, or time-obsolete | Authoritative digest-chain-plus-time fold and expected-head check; projection is disposable and never authority. |
| Capability replay | Protected random challenge bound to backend PID/start/full xid8 and one-way context transition. |
| Bind races key/principal revocation | One reserved heavyweight advisory admission lock, exact row-lock order, `READ COMMITTED` only, and fresh post-lock fold statements. Raw advisory acquisition is unavailable to callers, preventing same-session re-entry bypass. |
| Attacker substitutes tenant or Party bytes | Signed exact fields must equal immutable binding, tenant-registry, and pinned Party source fields and digests. |
| Restored database erases revocation | #174 exposes structural compatibility only; deployment refuses an explicitly declared restored target, while #193 owns the external continuity witness needed to detect a copied or undeclared fork. |
| Extension or crypto surface widens | Exact build and callable-surface fingerprint; missing or changed evidence refuses. |
| Signer, KMS administrator, PostgreSQL key controller, crypto installer, binder, migrator, or DBA compromise | Explicit privileged-boundary compromise, controlled operationally; not an RLS guarantee. A controller can authorize an attacker key and is not described as unable to grant signing authority. |

## Hostile evidence plan

All production-path evidence uses the exact pinned PostgreSQL and libsodium
builds and actual provisioned roles. Mocks and fixture signers do not satisfy
production evidence.

### Cryptography and wire

1. Freeze one cross-standard extraction vector with raw `K`
   `d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a`,
   DER
   `302a300506032b6570032100d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a`,
   transport base64
   `MCowBQYDK2VwAyEA11qYAYKxCrfVS/7TyWQHOg7hcvPapiMlrwIaaPcHURo=`,
   CRC32C decimal `3927069631`, raw-key SHA-256
   `21fe31dfa154a261626bf854046fd2271b7bed4b6abe45aa58877ef47f9721b9`,
   `x` `11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo`, and `kid`
   `kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k`. Independent observer,
   reference, and #172 extraction code must agree on every KMS/SPKI mapping;
   PostgreSQL recomputes the raw-key digest, `x`, and `kid` from `K`, and the
   extension consumes the same `K` in its signature known-answer test.
2. Mutate DER without changing CRC, then mutate DER and recompute CRC. Test a
   missing, negative, greater-than-uint32, byte-swapped, or base64-text CRC;
   default/unspecified or explicit PEM; absent or duplicate key data; and wrong
   response name, algorithm, protection level, or format. Each fails at its
   exact layer without fallback or response-field mixing.
3. With a correct recomputed CRC, refuse ASN.1 NULL parameters; X25519, Ed448,
   and unknown OIDs; every outer, inner, or BIT STRING tag/length mutation;
   indefinite, long-form, or non-minimal lengths; nonzero unused bits; 31- or
   33-byte keys; truncation, trailing data, certificates, PKCS#8, and alternate
   BER/PEM forms. Run one live HSM `EC_SIGN_ED25519`
   `getPublicKey(publicKeyFormat=DER)` path during controlled enabled preflight.
4. Substitute DER hash for raw-key digest, DER for `x`, padded base64url or
   standard base64, reordered or whitespace-bearing JWK, or an old digest/`kid`
   after flipping one bit in `K`. Each refuses and proves raw-key/digest/JWK
   lockstep.
5. Execute identical RFC, signer, independent-verifier, libsodium-extension, and
   live-binder golden vectors.
6. Flip one bit independently in protected header, payload, signature, public
   key, every digest, every UUID, every time, and every text field; each bind
   refuses.
7. Refuse short/long/malformed public keys and signatures, noncanonical `R` or
   `S`, `S >= L`, identity/small-order/mixed-order/invalid public keys and `R`
   values, otherwise valid identity-`R` signatures, negative-zero encodings,
   and all-zero inputs. Include libsodium's checked-in
   `not_main_subgroup_p` regression points. Invalid signatures return false;
   injected initialization, allocation, and internal failures abort with only
   the fixed infrastructure outcome and no diagnostic detail.
8. Refuse `none`, HMAC algorithms, `EdDSA`, Ed448, unknown algorithms, duplicate
   or extra header members, reordered members, whitespace, alternate case,
   unprotected headers, JWS JSON serialization, and `jku`/`jwk`/X.509 headers.
9. Refuse padded or noncanonical base64url, wrong segment counts, empty
   segments, non-ASCII input, non-zero trailing bits, and tokens over 8192
   bytes.
10. Mutate every `lp32` length, field order, encoding, UTF-8 sequence, UUID byte
   order, digest width, timestamp width, omission, duplication, and trailing
   byte. Python and live PostgreSQL must produce identical accept/refuse
   results.
11. Maintain RFC 8032 plus Wycheproof-equivalent adversarial vectors, fuzz the
   SQL and C input boundaries, and run the native suite under ASan and UBSan on
   every supported architecture. Every crash, undefined behavior report, or
   sanitizer finding blocks release.

### Audience, identity, and substitution

1. Present validly signed capabilities for a test issuer, another production
   installation, another service, another binder type, and another audience.
2. Vary issuer and subject case, whitespace, Unicode, byte length, URI form,
   equality policy, and delimiter-like content across OIDC verification,
   capability construction, database uniqueness, and binder comparison.
3. Substitute binding version/head, tenant ID/registration digest, Party ref,
   record kind/id, schema digest, or payload digest one at a time.
4. Use an unknown, wrong-kind, non-ACTIVE, floating newer, cross-tenant, or
   digest-equal-but-byte-different Party candidate. Every case refuses.

### Time boundaries

1. Test one microsecond below, equal to, and above every `issued_at`,
   `not_before`, `expires_at`, five-second skew, 60-second lifetime, and
   60-second challenge boundary.
2. Prove `expires_at == now` and `now == challenge_created_at + 60s` refuse,
   while exact permitted future-skew equality is consistent in signer and
   database implementations.
3. Test int64 minima/maxima, subtraction/addition overflow candidates,
   PostgreSQL timestamp limits, clock rollback/advance, and time changing
   between parse and bind. The binder's single observation remains decisive.
4. Test one microsecond below, equal to, and above activation, the exact
   `7,776,000,000,000`-microsecond natural retirement, rotation cutover,
   issuance skew, and each exact `65,000,000`-microsecond verification end.
   Repeat under multiple session timezones and across daylight-saving changes;
   integer results remain identical.
5. Hold each advisory and row lock long enough to cross capability expiry,
   challenge expiry, natural retirement, and the 65-second verification end.
   The post-wait clock observation refuses at every closed boundary; a fixture
   that observes before waiting must fail evidence.

### Key lifecycle

1. Refuse unknown, unregistered, inactive, wrong-audience, wrong-algorithm,
   expired, retired-beyond-tail, and revoked keys.
2. Roll back candidate registration, activation, rotation, admission close,
   revocation, and resumption and prove no partial authority or projection
   state becomes visible.
3. Race activation, rotation, close, revocation, and resumption with stale and
   identical expected heads; exactly one valid chain results and forks refuse.
4. Attempt repeated activation, reactivation, backdating, validity extension,
   old-key restoration, direct DML, mutation-guard removal under runtime roles,
   and projection-only authorization.
5. Accept an otherwise valid retiring-key capability one microsecond before
   its 65-second verification end and refuse it exactly at and after the end.
   Refuse old-key issuance outside the cutover/skew bound.
6. Reach the exact natural retirement without a replacement and prove the key
   becomes time-derived `VERIFY_ONLY`, accepts only the exact bounded tail, and
   refuses at the verification end. A later `ACTIVATE` while admission remains
   `OPEN` refuses; close, replacement activation, and resumption succeed only in
   that exact order. Race natural retirement with rotation and revocation.
7. Delete, corrupt, and stale the current projection under a privileged hostile
   fixture, including leaving it `ISSUING` across natural retirement and the
   verification end. The binder never authorizes from it, and deterministic
   rebuild reproduces the authoritative fold at the same database time.
8. Revoke an issuing and a verify-only key. Every capability under it refuses
   after the committed boundary, including one minted earlier with future
   expiry. Revocation without replacement leaves a safe outage.
9. Make the signer, key controller, or lifecycle observer unavailable or
   inconsistent. No last-known-good or unkeyed fallback is permitted.
10. Reconstruct the authoritative state at every earlier act/head after later
    rotation, close, revocation, and resumption. Later projection contents do
    not change the historical fold.
11. Hold bind A after its shared advisory admission lock, commit the durable
    close receipt. Start bind B before requesting the exclusive mode and prove
    its fresh fold reads `CLOSED` and aborts. Then queue `REVOKE` and start bind
    C. Inspect `pg_locks` and prove C cannot join A ahead of the exclusive
    waiter, finishing or terminating A permits revocation to commit, and C
    still refuses. Repeat the anti-barging order for a principal revocation.
    Cancel and roll back a queued key revocation: no act appears, no false
    revocation receipt is emitted, and the committed close remains authoritative
    across controller disconnect and PostgreSQL restart.
12. Assert the preflight probe is exactly the frozen 43 octets. Every JWS and
    capability parser refuses it before signature processing, both before and
    after candidate activation. The runner exposes no caller message, JWS,
    payload, or challenge input; no tenant challenge row or binder call occurs.
    Flip each probe/signature bit and prove both verification paths refuse.
13. Exercise the preflight grant and cleanup with real identities. A disabled
    candidate refuses signing. During the bounded window only that candidate
    accepts the fixed probe for the KMS administrator; old/sibling/other keys
    refuse, and the production signer refuses the candidate. Remove the binding
    while the candidate remains enabled and simulate delayed IAM propagation;
    any continued signing, unexpired credential/deadline, inherited grant,
    uncertain policy etag, or missing disable observation blocks `ROTATE`.
    Accept condition-free version-1 GET responses before addition and after
    removal only when the corresponding request proves
    `requestedPolicyVersion = 3`; bind those actual versions into the receipt.
    Omit/lower that request option, submit a version-1 SET, return version 1
    while any condition remains, seed an unrelated condition and omit it from
    a response or write, send a partial policy, alter an unrelated binding/audit
    config, or retry an etag conflict without a complete requested-version-3
    reread; every hostile case refuses without changing policy. Cancel after
    every step and prove an incomplete receipt never activates the candidate.
14. Delay every post-rotation handoff step and keep the old signing oracle
    working even after provider metadata reports `DISABLED` and policy no longer
    shows its grant. In graceful drain, new signing stays disabled until a fresh
    intended-database observation reaches `old.V`, then the exact
    `CLOSE_ADMISSION(ROTATION_HANDOFF)` and `REVOKE(old)` acts commit before the
    replacement is enabled. Repeat the same close-plus-revoke sequence before
    `V` for expedited cutover. In both paths old signatures refuse after the
    durable revocation even if the clock later moves backward; #172 minting
    remains disabled and every new-key capability remains binder-ineligible
    while admission is `CLOSED`; only the exact `RESUME_ADMISSION` chain permits
    new minting. Provider success or failure is evidence, never the safety
    assertion.

### Transaction binding and concurrency

1. Attempt a wrong or used nonce, second bind, different principal or tenant,
   wrong challenge, cross-backend replay, cross-full-xid replay, and replay
   after commit, rollback, cancellation, backend restart, or pool reset.
2. Race bind with key revocation/rotation and principal revocation,
   supersession, or expiry. Verify one serialized order and no stale-snapshot
   authorization.
3. Commit a context row and reuse the backend under a new full xid8; alternate
   tenants through the same backend; create dead-backend orphans; and prove
   cleanup never makes stale context authoritative.
4. Inject failure after signature verification, after lifecycle verification,
   during the guarded context update, during governed work, and during commit.
   The complete tenant transaction rolls back and no capability becomes
   reusable.
5. Run real ASGI requests for two principals and two tenants through #173's
   pool with cancellation, timeout, serialization retry, exception, and
   finalizer failure.
6. Attempt binder and lifecycle entry at `REPEATABLE READ` and `SERIALIZABLE`;
   each refuses before reading security state. At `READ COMMITTED`, prove the
   fold is read in a separate post-lock statement and sees the committed head.
7. Exercise the global fence/candidate/principal lock order, inverse-order
   hostile calls, deadlock detection, waiter cancellation, statement timeout,
   and backend termination. No cancellation leaks a lock, context, lifecycle
   act, or authorized stale snapshot.
8. Attempt every session, transaction, shared, exclusive, try, bigint, and
   two-int raw advisory-lock overload as every LOGIN role. Each refuses. Prove
   only the fixed entry points can obtain the reserved pair, a caller cannot
   pre-acquire it to trigger PostgreSQL's same-session re-entry exception, and
   no unrelated advisory key can substitute for admission.
9. Flood later shared admissions behind one queued exclusive transition and
   prove none barges. Demonstrate PostgreSQL's same-holder re-entry exception
   only with a privileged hostile fixture, then prove the production binder's
   one-bind context and privilege graph make it unreachable.
10. Prove the binder is `VOLATILE` and `PARALLEL UNSAFE`, its lock and fold
    reads are separate statements, and a deliberately stale-snapshot variant
    fails evidence. Verify `max_prepared_transactions = 0` and that
    `PREPARE TRANSACTION` cannot retain a bound shared admission lock.
11. Invoke binding before, inside, after release of, and after rollback to a
    savepoint. Any subtransaction rollback removes both context mutation and
    locks acquired within it; no path retains bound context after losing its
    shared admission lock.
12. After acquiring the shared lock, inject each signature, key, admission,
    principal, time, tenant, Party, context-update, and infrastructure failure.
    Prove each error escapes the binder. Retry with a valid token before and
    after queuing an exclusive transition, both with and without an outer
    exception-catching savepoint; no retry retains the earlier shared hold or
    passes the waiter.

### Roles, extension, and release evidence

1. Prove application, worker, readiness, signer, key controller, tenant,
   support, and audit roles cannot read or mutate public-key/lifecycle tables,
   obtain private material, call the verifier directly, or assume binder
   authority.
2. Prove the signer cannot register, activate, rotate, or revoke a key and the
   key controller cannot invoke the KMS signer, bind, or read tenant truth.
   Separately demonstrate that controller takeover can authorize an attacker
   public key, classify it as privileged signing-authority compromise, and
   exercise the audited outage/revocation response rather than claiming RLS
   prevents it.
3. Prove the signer has only the exactly conditioned `useToSign` permission,
   the lifecycle observer has only the exact version/key read permissions, and
   neither can use the other's capability. A sibling version, another key, an
   unconditional binding, or a wider inherited binding makes deployment
   evidence refuse. Prove the KMS administrator has no standing signing grant;
   its one preflight binding is exact, etag-guarded, deadline-bounded, and absent
   with active authorization refusal before `ROTATE`. The removal receipt,
   expired control credential/deadline, disabled candidate, and negative
   production-signer check must all agree. Both IAM mutations use complete
   version-3 SET requests with etags; every GET requests version 3 and accepts
   an actual version 1 only for a complete condition-free response. Every
   unrelated binding, condition, member, and audit configuration is preserved.
4. Attempt function/schema/operator shadowing, search-path substitution,
   dynamic library replacement, unapproved libsodium source or compile-time
   flags, callable sign/keygen addition, argument-default change, binary-path
   change, and PUBLIC grant. Structural compatibility must fail.
5. Inventory the compiled extension for exactly the accepted exported and SQL
   callable surface and run independent memory-safety and malformed-input
   review. Prove exact installer attributes, extension control settings,
   ownership, grants, and that migrator/runtime roles cannot create, update,
   replace, load, or drop the extension or library.
6. Clone and promote a physical database carrying the same audience, public
   keys, and lifecycle heads. It may report structural compatibility only;
   #174 exposes no continuity, recovery-readiness, service-ready, binder-startup,
   or promotion result, and the deployment policy refuses the explicitly
   declared restored target. Record that an undeclared clone is not detectable
   without #193's external witness.

## Alternatives rejected

### Symmetric HMAC in PostgreSQL

Rejected. The verifier would hold signing authority, database compromise would
mint capabilities, and graceful rotation would not provide credible emergency
revocation separation.

### Application-only verification or caller-asserted fields

Rejected. An attacker with application process or SQL execution could invoke
the privileged binder with forged "verified" values. The database must verify
an authenticator it cannot create.

### Verification on another database connection

Rejected. A separate verifier connection cannot atomically install context for
the application's uncommitted challenge on the same backend and full xid8.

### Generic JWT JSON claims

Rejected for this internal capability. Multiple JSON representations, number
handling, duplicate members, and cross-library normalization add authority
ambiguity. JWS protects an arbitrary binary payload, so the closed `lp32` frame
retains standard signature wrapping without JSON claim semantics.

### Dynamic JWKS retrieval inside PostgreSQL

Rejected. It adds network, cache, TLS, URL-selection, refresh, and outage
authority to the binder. Public keys enter only through the governed append-only
control path.

### Indefinite old-key acceptance after rotation

Rejected. It preserves compromised authority and makes key replacement
cosmetic. The graceful verification tail is fixed at 65 seconds; suspected
compromise uses immediate revocation.

### PostgreSQL core or `pgcrypto`

Rejected. PostgreSQL core supplies hashes but no asymmetric-signature SQL API,
and `pgcrypto` exposes no detached asymmetric-signature verification API.
Neither can authenticate a capability with public verification material only.

### Full `pgsodium`

Rejected for this boundary. Although it uses libsodium and can verify Ed25519
signatures, it is absent from the pinned image and introduces signing, key
generation, symmetric crypto, key-management roles and tables, and
event-trigger surfaces that the binder must not expose. The directly linked
one-function verifier has a smaller SQL and privilege surface.

### A signature verifier written in PL/pgSQL

Rejected. Implementing RSA or another signature scheme with PostgreSQL numeric
operations would create bespoke cryptographic, padding, encoding, performance,
and denial-of-service risk. The accepted verifier delegates strict PureEdDSA
point validation and verification to the pinned libsodium implementation
through one bounded native function.

## Standards and implementation references

- [RFC 7515](https://www.rfc-editor.org/rfc/rfc7515.html), JSON Web Signature,
  defines Compact Serialization and permits arbitrary payload octets.
- [RFC 7638](https://www.rfc-editor.org/rfc/rfc7638.html), JSON Web Key
  Thumbprint, defines the canonical SHA-256 key identity.
- [RFC 8032](https://www.rfc-editor.org/rfc/rfc8032.html), Ed25519.
- [RFC 8037](https://www.rfc-editor.org/rfc/rfc8037.html), Ed25519 JWK and JOSE
  representation.
- [RFC 8410](https://www.rfc-editor.org/rfc/rfc8410.html), Ed25519
  `SubjectPublicKeyInfo`, fixes OID `1.3.101.112`, absent parameters, and the
  public-key BIT STRING.
- [RFC 8725](https://www.rfc-editor.org/rfc/rfc8725.html), JWT Best Current
  Practices, supplies the fixed-algorithm, audience, explicit-type, and
  cross-token-confusion guidance applied here even though the binary payload is
  not a JWT claims object.
- [RFC 9864](https://www.rfc-editor.org/rfc/rfc9864.html), fully specified JOSE
  algorithms, registers `Ed25519` rather than the polymorphic `EdDSA` value.
- [libsodium point validation](https://doc.libsodium.org/advanced/point-arithmetic)
  defines the canonical, main-prime-subgroup, and non-small-order checks used
  for both public key and signature `R`.
- [libsodium detached signatures](https://doc.libsodium.org/public-key_cryptography/public-key_signatures)
  defines the PureEdDSA verification API used after strict point validation.
- [PostgreSQL 17 `pgcrypto`](https://www.postgresql.org/docs/17/pgcrypto.html)
  inventories the supplied module, which has no detached asymmetric-signature
  verification API.
- [Google Cloud KMS key algorithms](https://docs.cloud.google.com/kms/docs/algorithms)
  specifies `EC_SIGN_ED25519` as PureEdDSA over raw input and supports HSM
  protection; the
  [key-version API](https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions)
  states that raw private key material cannot be viewed or exported.
- [Cloud KMS `getPublicKey`](https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/getPublicKey)
  defines explicit DER selection, `publicKey.data`, its CRC32C field, and the
  returned resource, algorithm, protection, and format metadata.
- [Google Cloud KMS permissions and roles](https://docs.cloud.google.com/kms/docs/reference/permissions-and-roles)
  fixes the policy hierarchy and relevant custom-role permissions; the
  [IAM Conditions attribute reference](https://docs.cloud.google.com/iam/docs/conditions-resource-attributes)
  defines exact CryptoKey and CryptoKeyVersion resource-type/name conditions.
- [Cloud KMS IAM Policy](https://docs.cloud.google.com/kms/docs/reference/rest/v1/Policy)
  requires policy version 3 and an etag for operations affecting conditional
  bindings, and defines complete-policy replacement semantics; IAM's
  [`GetPolicyOptions`](https://docs.cloud.google.com/iam/docs/reference/rest/v1/GetPolicyOptions)
  permits a requested-version-3 GET to return version 1 when the policy has no
  conditional binding.
- [Cloud KMS key-version states](https://docs.cloud.google.com/kms/docs/key-states)
  requires an enabled version for asymmetric signing; the
  [resource-consistency contract](https://docs.cloud.google.com/kms/docs/consistency)
  explains why state and IAM observations are operational evidence rather than
  the database handoff barrier.
- [PostgreSQL 17 advisory-lock functions](https://www.postgresql.org/docs/17/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS)
  define transaction-level shared and exclusive locks; the exact 17.10
  [`lockfuncs.c`](https://github.com/postgres/postgres/blob/REL_17_10/src/backend/utils/adt/lockfuncs.c),
  [`lock.c`](https://github.com/postgres/postgres/blob/REL_17_10/src/backend/storage/lmgr/lock.c),
  and [`proc.c`](https://github.com/postgres/postgres/blob/REL_17_10/src/backend/storage/lmgr/proc.c)
  map those modes and prevent a fresh shared requester from passing a conflicting
  earlier waiter.
- [PostgreSQL function volatility](https://www.postgresql.org/docs/17/xfunc-volatility.html)
  supplies the snapshot rule requiring a `VOLATILE` binder, while
  [`PREPARE TRANSACTION`](https://www.postgresql.org/docs/17/sql-prepare-transaction.html)
  explains why V1 disables prepared transactions for bound work.

## Accepted scope

GitHub #200 independently accepted:

1. Ed25519 and the verification-only in-database extension trust surface;
2. non-exportable external private-key custody, strict DER-to-raw-key
   extraction, the bounded preflight actor, and role separation;
3. the exact JWS header, RFC-thumbprint key identity, and binary payload frame;
4. the 60-second lifetime, five-second skew, installation audience, 90-day key
   issuance bound, and 65-second verification tail;
5. append-only activation, atomic rotation, durable admission close,
   database-authoritative rotation handoff, anti-barging advisory admission,
   emergency revocation, resumption, and their transaction ordering;
6. replay, rollback, pool-reuse, and negative recovery semantics; and
7. the #172/#174/#173 implementation ownership split and hostile evidence
   plan.

This acceptance authorizes implementation work only. It does
not make the implementation complete, close #174, enable production binding,
or establish production readiness.

## Validation for this documentation decision

The acceptance transition is validated with:

```text
python3 conformance/ofarm_pkg_contract_check.py
python3 conformance/ofarm_profile_extraction_consistency_check.py
git diff --check
git diff --cached --check
git status --short
```

The accepted review confirmed that the change was documentation-only, every new
relation and role was classified in ADR 0001, all local links resolved, and the
#172/#173/#174/#192/#193 owner accounting remained exact. GitHub #200 records
the independent architecture and security acceptance.
