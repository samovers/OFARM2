# Authentication modes and pre-binding refusal policy

This is the application policy implemented for GitHub #172. It describes a
security boundary and does not claim that the legacy HTTP API is a production
tenant runtime. #173 owns transaction, pool, challenge, binder, and UnitOfWork
integration.

## Explicit startup modes

`OFARM_AUTH_MODE` is mandatory for the environment-driven application factory.
Its value is compared exactly and is never inferred from another setting.

| Mode | Credential path | Required startup state |
|---|---|---|
| `development` | `X-Acting-Party` shim | No verifier or binding resolver may be present. |
| `test` | Local HS256 fixture issuer | Exact issuer, audience, and test secret; only `HS256`. |
| `production` | Asymmetric OIDC bearer token | Deployment identity, maintained JWKS verifier, immutable principal-binding resolver, and KMS-backed TenantCapability issuer all initialize successfully. |

Production refuses `OFARM_OIDC_HS256_SECRET`. It requires
`OFARM_OIDC_ISSUER`, `OFARM_OIDC_AUDIENCE`, and `OFARM_OIDC_JWKS_URL`.
`OFARM_OIDC_ALGORITHMS` is an explicit comma-separated asymmetric allow-list
and defaults to `RS256`; whitespace is not normalized. The verifier fetches a
fresh JWKS at startup and caches one validated key-set generation for a bounded
interval. It never enables PyJWT's unbounded per-key cache. Each refresh rejects
duplicate usable `(kid, alg)` identities and keys not eligible for signature
verification before atomically replacing the generation. Token `alg` and `kid`
must select one exact usable key. RSA signing keys below 2048 bits refuse both
at JWKS-generation validation and again in PyJWT's strict verification path.
A miss can start only one provider refresh per
`OFARM_OIDC_JWKS_MISS_REFRESH_SECONDS` window, which defaults to five seconds;
other misses share that result and current-key verification does not wait on the
provider call. Missing configuration, JWKS outage, an empty or unsuitable key
set, or an unavailable binding resolver stops startup.
The deployment image digest is validated before the production composition is
constructed, so malformed deployment identity cannot trigger JWKS, database,
or KMS access.

## Exact principal policy

After signature, issuer, audience, expiry, not-before, and key checks, the
decoded `iss` and `sub` values are used exactly as received. They are never
trimmed, case-folded, Unicode-normalized, URI-normalized, or rewritten. The
issuer and subject must satisfy the byte grammar and bounds frozen for
`OIDC_EXACT_UTF8_V1`. Duplicate JSON members, noncanonical compact-JWS segments,
unsupported critical or key-directing JOSE headers, and non-finite NumericDate
values refuse. NumericDate integers and floats are bounded to the representable
UTC year-9999 range before key selection, so arbitrary-precision JSON integers
cannot escape the safe credential-refusal path.

Test mode maps `sub` directly to the test Store Party. Production does not.
Production calls the fixed `resolve_principal_binding_authority` database
function through the separately provisioned `ofarm_identity_resolver` login.
That read-only, non-assumable credential has no membership and only the minimum
cross-tenant read grants required to reconstruct the lifecycle fold and compare
the exact immutable binding, tenant registration, and pinned Party tuple. The
function never uses `principal_binding_current`; application, worker,
administrator-role-switch, and binder credentials cannot call it.
Production construction requires the exact sealed
`PostgreSQLPrincipalBindingResolver`; protocol fakes and wrappers are available
only through the explicit unit-test runtime factory.
The normal production verifier constructs its maintained PyJWT JWKS client and
monotonic clock internally. Injected JWKS clients and clocks exist only on the
explicit non-production test factory, and a production runtime rejects those
instances.
The active version must pin the immutable tenant registration and ACTIVE
`ofarm.party.v0.1` identity, schema, and payload digests. Missing, inactive,
expired, ambiguous, or digest-inconsistent state refuses.
Startup executes this complete fixed function with a reserved no-match identity,
so a wrong credential, missing grant, missing function, or unresolved database
dependency refuses before traffic is served.

Lifecycle mutations use only #174's digest functions and
`transition_principal_binding` with an expected lifecycle head. The controller
has no direct `INSERT`, `UPDATE`, or `DELETE` path to binding versions, lifecycle
acts, the projection, tenant registry, or Party records. Access stops through
`REVOKE`, `EXPIRE`, or `SUPERSEDE`; mutable tenant or Party eligibility is not a
V1 mechanism.

## Capability and signer policy

The production issuer mints the frozen binary TenantCapability only after an
exact active binding is resolved. It pins the equality policy, issuer, subject,
binding version and lifecycle head, tenant-registration digest, Party facts,
one database challenge and audience, a UUIDv4 nonce, and an expiry of at most 60
seconds.

The production signer accepts one pinned Google Cloud KMS HSM
`EC_SIGN_ED25519` key version and fresh authenticated startup evidence. Raw
evidence fields are accepted only by the explicit test factory. Normal
construction reads a bounded signed receipt from
`OFARM_SIGNING_EVIDENCE_RECEIPT_PATH`, obtains the separately pinned observer
key named by `OFARM_SIGNING_EVIDENCE_OBSERVER_KEY_VERSION` through the official
Cloud KMS client, verifies its HSM identity, CRC32C, and Ed25519 receipt
signature, and requires the receipt to name the exact signing key configured by
`OFARM_TENANT_CAPABILITY_SIGNING_KEY_VERSION`. The signing key and observer key
must belong to different Cloud KMS CryptoKeys, not merely different versions.
Before constructing any Cloud KMS client, application composition validates
both complete key-version resources and requires distinct absolute
`OFARM_SIGNING_EVIDENCE_RECEIPT_PATH` and
`OFARM_SIGNING_EVIDENCE_HIGH_WATER_PATH` values.
It then initializes authentication once, consumes the resolver's validated
database-pinned `tenant_binder_instance` audience, and only then constructs the
KMS boundary. The OIDC token audience is never reused as the binder audience,
and repeated application-runtime initialization performs no second
authentication initialization.
Raw private key
material and duck-typed signing clients are never accepted: construction
requires the sealed adapter to construct the maintained Google Cloud KMS client
with its default transport internally. Exact Google clients backed by
caller-supplied transports cannot be injected. The production capability issuer
also requires the exact sealed PostgreSQL principal-binding resolver; protocol
fakes remain confined to its explicit test factory.
It sends the exact JWS Signing Input through KMS's raw `data` field with CRC32C,
checks response resource identity, HSM protection, request-checksum
acknowledgement, the generated response's integer signature checksum, and then
independently verifies the returned Ed25519 signature before serializing the
token. Observer evidence is valid for no more than five minutes. Stale,
unsigned, incorrectly signed, or inconsistent KMS, IAM, attestation,
database-key, or lifecycle evidence disables signing. A previously accepted
receipt can remain in use only while it is still valid; expired or
non-monotonic evidence never becomes a fallback.

The application factory closes over the initialized authentication runtime
rather than dereferencing mutable Starlette state. Starlette state exposes only
frozen authentication mode and verifier-kind metadata; it exposes no verifier,
resolver, authentication runtime, or principal-dependency alias. Production
also refuses every authenticated legacy Store-backed endpoint with
`TENANT_BOUNDARY_BLOCKED`.
The full immutable principal-binding authority remains attached until that
refusal; it is never reduced to a Party reference and applied to an independently
selected Store. #173 must supply the tenant-bound UnitOfWork before this surface
can be enabled in production.

## Safe closed outcomes

Only these enum values may cross the future #192 pre-binding audit seam:

- `NO_CREDENTIAL`
- `INVALID_CREDENTIAL`
- `VERIFIER_UNAVAILABLE`
- `BINDING_UNAVAILABLE`
- `PRINCIPAL_UNBOUND`
- `BINDING_INTEGRITY_REFUSED`
- `CONFIGURATION_REFUSED`
- `SIGNER_UNAVAILABLE`
- `CAPABILITY_REFUSED`

They carry no token, issuer, subject, Party or tenant value, key or signature,
request value, SQL detail, provider response, stack trace, or raw exception
text. #192 may persist the closed outcome later; this implementation does not.
Malformed, unreachable, or expired-cache JWKS provider state is
`VERIFIER_UNAVAILABLE`; malformed tokens, unknown keys in a healthy generation,
bad signatures, and invalid claims are `INVALID_CREDENTIAL`.
