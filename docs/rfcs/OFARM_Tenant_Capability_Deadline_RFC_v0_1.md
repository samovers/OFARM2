# Tenant capability issuance bounded by protected challenge time

Status: proposed Phase A; implementation is not authorized by this document.
Decision: `OFARM2-TENANT-CAPABILITY-DEADLINE-001`, version `1`.
Delivery: [#377](https://github.com/samovers/OFARM2/issues/377), under #167.
Base: `bb3fe718f16721165fcd1ac9cb634cf8fb2815c7`.
Primary trust boundary: signing and capability issuance.

## Problem and authority

Audit K-01 found that the production issuer derives expiry from a later
signing-authority observation plus 60 seconds. The binder requires expiry no
later than protected challenge creation plus 60 seconds. A positive observation
delay therefore produces an invalid capability unless key retirement caps it
earlier. This is an implementation defect, not a change to OFARM law.

ADR 0003's Time contract and the frozen V1 capability validator own the existing
time predicates. The merged [challenge observation contract](OFARM_Tenant_Challenge_Observation_RFC_v0_1.md)
provides the missing protected creation time. This design consumes those
interfaces; it adds no time policy, clock authority or signed payload field.
The PR description owns the complete Phase A threat model and verification
plan. This document preserves the cross-statement binding and time rationale
that remain useful after that PR closes.

## One immutable challenge value

On the already checked-out READ COMMITTED transaction, execute the unchanged
two-column `ofarm.create_tenant_challenge()` call, followed by a separate
`ofarm.current_tenant_challenge()` statement. The latter returns the protected
UUID and exact integer Unix microseconds of original creation. Its STABLE
snapshot contract requires the separate statement. Do not combine the calls
into one SQL expression or use the signing reader's separate connection to
observe this transaction's challenge.

Replace the incomplete two-field `TenantChallenge` with one frozen, required
three-field value: challenge UUID, installation audience, and protected creation
time. Its database-row factory owns the existing creator-row decoding plus the
observer-row shape and UUID join. Require the same exact nonzero UUID in both
rows; never coerce a string into a UUID or supply a missing timestamp. Keep the
current ValueError-to-binding-refusal behavior for invalid database rows. Mint
also rejects an invalid challenge or non-integer creation time before arithmetic
and before KMS signing; Python booleans are not accepted as integer timestamps.

The UOW only transports the accepted metadata. Its transaction ownership,
principal binding, pool, reset/discard logic, selector, failure mappings and
governed-write behavior remain unchanged. No caller chooses a challenge time,
deadline, grace or alternate source. The observer has no expiry-policy role:
an expired unconsumed challenge may still have observable original metadata.

## Deadline calculation

Let C be protected challenge creation, S be the existing database
signing-authority observation, and E be the observed key issuance end. Retain:

```text
issued_at = not_before = S
expires_at = min(
    C + TENANT_CHALLENGE_MAX_AGE_MICROSECONDS,
    S + TENANT_CAPABILITY_MAX_TTL_MICROSECONDS,
    E,
)
```

Use the two existing named limits even though both are currently 60 seconds.
Pass both `now_unix_microseconds=S` and
`challenge_created_at_unix_microseconds=C` to the existing
`validate_tenant_capability` before serialization for signing or a KMS RPC.
That validator remains the single owner of integer bounds, skew, strict
nonempty interval, expiry and challenge-age checks. No second time validator,
magic shorter TTL, renewal, retry, fallback clock or compatibility mode is added.

Candidate additions use Python's non-wrapping integers after the exact-type
guard, without float conversion, int64 casts or packing. The validator checks
the selected signed times and original C, including the bounds that permit
its own challenge arithmetic, before encoding or signing. Even an out-of-range
C whose candidate loses the minimum must refuse. This preserves checked V1
arithmetic without copying its range policy into the issuer.

Both C and S originate in the tenant service's database `clock_timestamp()`;
they are sampled at different statements. `SigningAuthorityReader` gets S from
`ofarm.observe_signing_authority()` and checks the observer receipt against S.
The receipt's own timestamp is not the issuance clock. Preserve that separation,
receipt freshness checks, pinned key and KMS custody.

Pre-sign validation evaluates the observation it has. It cannot guarantee that
a later bind succeeds: KMS or lock delay, database-clock movement, principal
revocation, admission closure or key retirement can intervene. The unchanged
binder rechecks its protected challenge, current authority and its own later
database-clock observation. Refusal never causes transparent reissuance or
reuse in a replacement transaction.

## Containment and simplicity

Move the existing inline UOW row decoding into the existing challenge value's
factory, and replace that block with the observer query and factory call. This
keeps the integration within the present 520-line UOW budget. Keep the issuer
within its existing 180-line budget without unrelated cleanup, line stuffing,
new modules or increased budgets. The factory isolates one real boundary; it
does not add a general decoding framework or a second challenge representation.

Preserve the frozen creator, binder, signed manifest, migrations, roles, key
lifecycle, receipt verifier, signer, principal resolver, runtime composition,
readiness and closed production governed routes. This Delivery changes no
database schema or durable recovery behavior. Its prerequisite is already
merged, so no mixed-version adapter or rollout protocol is needed or promised.

The smallest credible alternative, shortening the old 60-second TTL by a fixed
margin, still fails for longer observation delays and obscures the protected
deadline. Moving key observation earlier or using a receipt/local clock cannot
supply the original protected creation time. A new TTL configuration or extra
database function has no present consumer or required invariant.

## Evidence required before closure

Prove exact boundary values and hostile row shapes before KMS signing. Exercise
positive delay with a long-lived key, a shorter key issuance end, exhausted
windows, backward clock observations inside and outside the existing skew,
integer limits, immutable value transport and unchanged identity/audience
refusals. Test statement order, observer failures and cancellation before yield;
no invalid admission may expose a unit of work or contaminate a reused session.
Before yield, cancellation may terminate the open transaction by closing and
discarding its connection under existing UOW behavior; it need not issue an
explicit ROLLBACK. Cancellation after a dispatched KMS RPC cannot guarantee
that the external service produced no signature. Zero KMS calls are required
for invalid inputs refused before signing, not for later binding failures.

Use the production issuer, signing reader, signer and UOW with a provisioned
native database binder. External KMS and observer services may be deterministic
test fixtures; label that limit explicitly. Existing live tests that substitute
a fixture minter cannot alone demonstrate K-01 remediation. Retain existing
binder/key/principal concurrency evidence for final revalidation.

After semantic approval and implementation, run cheap checks and obtain a
zero-Blocker exact-head content review before the existing admitted Linux
x86_64/Python 3.12.13/PostgreSQL 17.10 three-cluster, two-run baseline and separate
publication receipt. Old PR #376 evidence remains historical. There are no
executed implementation results at this Phase A head.

Not provisional: there is no temporary compatibility path. Repository approval
does not authorize deployment, release, production access or a readiness claim.

Next: complete Phase A review and present the named draft PR's decision card
before implementing this capability.
