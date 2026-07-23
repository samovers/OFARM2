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
| `production` | Asymmetric OIDC bearer token | Maintained JWKS verifier and immutable principal-binding resolver both initialize successfully. |

Production refuses `OFARM_OIDC_HS256_SECRET`. It requires
`OFARM_OIDC_ISSUER`, `OFARM_OIDC_AUDIENCE`, and `OFARM_OIDC_JWKS_URL`.
`OFARM_OIDC_ALGORITHMS` is an explicit comma-separated asymmetric allow-list
and defaults to `RS256`; whitespace is not normalized. The verifier fetches a
fresh JWKS at startup and caches one validated key-set generation for a bounded
interval. It never enables PyJWT's unbounded per-key cache. Each refresh rejects
duplicate usable `(kid, alg)` identities and keys not eligible for signature
verification before atomically replacing the generation. Token `alg` and `kid`
must select one exact usable key. A miss can start only one provider refresh per
`OFARM_OIDC_JWKS_MISS_REFRESH_SECONDS` window, which defaults to five seconds;
other misses share that result and current-key verification does not wait on the
provider call. Missing configuration, JWKS outage, an empty or unsuitable key
set, or an unavailable binding resolver stops startup.

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
Production resolves the exact `(equality policy, issuer, subject)` through
`fold_principal_binding_authority`, then reads only the immutable binding version
named by that authoritative fold. It does not use `principal_binding_current`.
Production construction requires the exact sealed
`PostgreSQLPrincipalBindingResolver`; protocol fakes and wrappers are available
only through the explicit unit-test runtime factory.
The active version must pin the immutable tenant registration and ACTIVE
`ofarm.party.v0.1` identity, schema, and payload digests. Missing, inactive,
expired, ambiguous, or digest-inconsistent state refuses.
Startup executes this complete query with a reserved no-match identity and
separately prepares its exact digest call, so missing grants, relations,
columns, functions, or types refuse before traffic is served.

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
`EC_SIGN_ED25519` key version and fresh startup evidence. Raw private key
material and duck-typed signing clients are never accepted: construction
requires the exact maintained Google Cloud KMS client behind the sealed adapter.
It sends the exact JWS Signing Input through KMS's raw `data` field with CRC32C,
checks response resource identity, HSM protection, request-checksum
acknowledgement, signature checksum, and then independently verifies the
returned Ed25519 signature before serializing the token. Observer evidence is
valid for no more than five minutes. Stale or inconsistent KMS, IAM,
attestation, database-key, or lifecycle evidence disables signing without a
cached-authority fallback.

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
