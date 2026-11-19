# Portable local draft execution environment

Design stage for Delivery #446. This draft PR does not yet contain the
implementation. Its Phase A and approval status are in the PR description;
this file does not authorize execution, publication or merge.

The delivery will package the existing selected Darwin arm64 verifier
environment with a reproducible producer and focused review checks. Explicit
input locations must still match fixed hashes. No original workstation path,
ambient Python fallback or shared-installation write is permitted.

Local reference archive SHA-256:
`bba90884d28e4ef6f15835d204fd68be5cd57a7fd06a6322e20d94af53970971`.
Reference candidate:
`d4325b754615e937a0f2d0f6ab5187e9e9f822e9299905cb796b3cd3870d76dc`.
These identify the local review candidate, not a released or approved artifact.

Primary trust boundary: execution dependency verification. Domain and owner
rules remain unchanged. The spray draft consumer is separate Delivery #447.
Live C4 stays NOT_EVALUATED; real approval and payload publication stay BLOCKED.

Next: obtain the named PR's required semantic approval, resolve the producer
path dependency, then verify the complete delivery in this same PR.
