# OFARM Native-Evidence GitHub CLI Pin Execution — Phase A Contract v0.2

**Status:** proposed; Phase A only; no implementation, merge, deployment,
release, or production authority

**Contract identity:**
`ofarm2.native-evidence-github-cli-pin-execution.v0.2`

**Decision identity:**
`ISSUE174-NATIVE-EVIDENCE-GITHUB-CLI-PIN-EXECUTION-001`, proposed version `2`

**Issue relationship:** issue #174 remains closed; this is bounded post-closure
maintenance of its retained native-evidence verification workflow

**Named draft pull request:**
[`samovers/OFARM2#313`](https://github.com/samovers/OFARM2/pull/313)

**Reviewed base:** `9c12c115bd29d9889234edd9e4c84377d9e332f8`

**Phase A amendment base:**
`d963bf45c030c08b89ff35dda893c77677a2a7a5`

**Demonstrating review:**
[`4943701301`](https://github.com/samovers/OFARM2/pull/312#pullrequestreview-4943701301)
at stopped pull-request head
`0c55770739c96234a5b6456dced048263398b328`

**Primary trust boundary:** native release-evidence verification currentness
and exact GitHub CLI selection, installation, credential isolation, and
workflow custody

**Phase A review-head boundary:** this RFC only after the amendment base; the
full pull-request diff also retains the rejected provisioning-witness v0.1 RFC
as an unchanged audit record

**Maximum final pull-request path envelope:** exactly the ten paths listed in
section 11

**Prior-decision posture:** version 1 remains stopped at pull request #312 and
cannot authorize this changed architecture, changed path envelope, or pull
request. The provisioning-witness decision proposed in #313 was never
approvable and supplies no authority. Only a later exact approval of this
version 2 card may authorize Phase B in #313.

## 1. Problem and goal

Hosted runners can replace their preinstalled `gh`. The retained native-release
evidence verifier requires the exact raw output bytes of GitHub CLI `2.96.0`.
Pull request #312 proved that an independently authenticated CLI installation
can satisfy that requirement: the exact archive, direct executable, raw stdout,
canonical path handoff, token boundary, provider verification, amd64 build,
arm64 build, and canonical index all passed.

That same exact-head review also proved that the version 1 receipt-refresh
design crossed an authority boundary. The checked frozen receipt is embedded
in `TENANT_PROVISIONING_SPEC.manifest()`. Refreshing only its
`verificationAuthorityInput` therefore changed the tenant provisioning digest
from the accepted
`sha256:2ac8487b64d4fb09d7576ef1ee09ac1f2a3cc5b20558f0d2137620b897c7157c`
to
`sha256:1f080c4d786f8f276bc89e29fcd7297b0c6b73b8906ab9cfbe94f69d6c02792e`.
Migration and structural verification correctly refused.

Version 2 keeps the accepted frozen receipt byte-identical and separates live
verification currentness into one canonical, checked sidecar. The sidecar
binds the exact release identity and exact frozen-receipt digest, and contains
the sole authority snapshot that must equal current verification-authority
files. It is validated before provider verification, tenant provisioning,
migration, readiness, conformance-environment observation, or another
production-reachable current-authority result.

This task establishes all of the following as one coherent native-evidence
boundary:

1. exact, token-free GitHub CLI installation and canonical handoff;
2. one immutable retained-evidence receipt;
3. one receipt-bound verification-currentness sidecar;
4. fail-closed currentness validation with no receipt or runner fallback; and
5. byte-for-byte preservation of the tenant provisioning manifest and digest.

No cross-boundary exception is required. No provisioning implementation,
migration, receipt refresh, or accepted-digest change is permitted.

The accepted checked receipt at the reviewed base is exactly 25,682 bytes with
canonical digest
`sha256:5a13f99a5252828da01df0e2d2e5b8d491b99ec795736e5becc2659616a575c3`.
Those values are reviewer evidence, not values the task user must verify.

## 2. Learning value

The change demonstrates that durable release evidence and live verifier
currentness can evolve on different lifecycles without weakening either one.

It removes three demonstrated risks:

- mutable runner software is no longer accepted as the verification CLI;
- repository-verifier maintenance no longer mutates database provisioning
  identity; and
- a frozen receipt's historical verification snapshot can no longer be
  mistaken for the sole live-currentness authority.

The result is more general than this CLI pin: future changes to the maintained
verification implementation can refresh the sidecar without rewriting retained
provider evidence or forcing a database migration.

## 3. Non-goals

This pull request does not:

- change `deployment/postgresql/provisioning_specs.py`, any migration, migration
  set, ledger row, structural digest, catalog identity, schema, role, grant,
  transaction, or durability behavior;
- change the checked `native_evidence_receipt.json` by one byte;
- add a provisioning witness or embed the currentness sidecar in the tenant
  provisioning manifest;
- change the accepted tenant provisioning manifest bytes or digest;
- change release identity, release assets, attestations, build pins, candidate
  evidence, platform evidence, retained provider verification, preservation
  evidence, signature semantics, or provider-comparison semantics;
- change or broaden the existing exact historical-v1 candidate finalization
  migration exception;
- add a runner-CLI fallback, package-manager fallback, receipt fallback,
  optional currentness capability, mutable registry, cache, environment
  selector, database selector, or network-selected authority;
- change token use inside an exact commit-pinned action's own action boundary;
- change security-audit behavior or any issue #192 authority;
- implement or merge pull request #312, transfer its version 1 approval, or
  reconstruct authority from its commits or review;
- implement unrelated work from pull request #311;
- address an independent arm64 network failure unless it is reproduced within
  this exact head and boundary; or
- authorize deployment, release publication, production access,
  current/default promotion, or a security or conformance waiver.

## 4. Trust model

### 4.1 Protected assets

The protected assets are:

- the exact frozen release identity and its current source-input validation;
- the byte-identical frozen native-evidence receipt, including retained assets,
  provider evidence, preservation evidence, and historical snapshots;
- the accepted tenant provisioning manifest bytes and digest;
- the exact set and bytes of current native verification-authority files;
- the binding from current verification authority to one release identity and
  one frozen receipt;
- canonical selection of the CLI executable used for provider verification;
- the verification-step-scoped GitHub token and absence of token custody in
  the installation shell; and
- honest refusal when installation, selection, binding, currentness, provider
  evidence, or source state is ambiguous.

### 4.2 Trusted components

This boundary trusts:

- the exact commit-pinned workflow actions;
- the conformance checkout action configured with
  `persist-credentials: false`;
- SHA-256 and the reviewed official GitHub CLI archive digest;
- the authenticated official GitHub CLI release archive;
- the pinned Python 3.12.13 environment;
- canonical JSON encoding and bounded regular-file reads;
- `load_native_release_identity(..., verify_current_sources=True)`;
- the frozen-receipt schema, candidate link, release link, build, platform,
  preservation, and provider validators;
- `evidence_authority_input_manifest()` as the sole current-file manifest
  constructor;
- the sidecar validator defined by this contract;
- the existing production callers that request
  `verify_current_authority=True` before protected work;
- the existing GitHub Release and Sigstore provider verification; and
- a later exact same-task approval of the complete version 2 decision card as
  provisional pre-deployment development authority.

### 4.3 Untrusted inputs and state

The boundary treats as untrusted:

- the runner-preinstalled `gh` and initial `PATH`;
- downloaded bytes before digest verification;
- every executable path before strict canonical resolution, regular-file, and
  executable checks;
- unexpected local Git credential configuration;
- the sidecar document before complete schema, canonical-byte, identity,
  receipt, and current-file validation;
- missing, malformed, non-canonical, symlinked, non-regular, oversized,
  substituted, or truncated identity, receipt, sidecar, archive, and source
  files;
- the frozen receipt's embedded `verificationAuthorityInput` as a claim about
  current repository bytes;
- caller-supplied paths used by supported tests and command entry points;
- network and GitHub API responses before existing cryptographic and exact
  provider checks; and
- GitHub PR metadata, branch names, comments, reviews, check labels,
  credentials, and tool output as approval authority.

### 4.4 Explicitly excluded attacker capabilities

The threat model excludes SHA-256 compromise, compromised official GitHub
release custody, runner-root compromise, arbitrary in-process mutation after a
validated object is returned, undetectable filesystem mutation between
validated reads, local source substitution outside the reviewed diff,
compromised Python, operating system, kernel, Git, GitHub, CI, cryptographic
dependencies, or storage capable of forging all reviewed evidence, malicious
task-user approval, and trusted operator or Codex-account compromise.

Ordinary runner drift, visible source substitution, stale checked files,
missing files, wrong file types, PATH ambiguity, checkout credential
persistence, network failure, archive substitution, wrong version bytes,
stderr output, sidecar substitution, wrong sidecar binding, and changed
provider evidence remain in scope and must fail closed.

## 5. Authority map

There is one source of authority for every decision:

| Decision | Sole authority | Explicitly not authority |
| --- | --- | --- |
| Accepted CLI stdout bytes | Existing `NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT` | Archive filename, URL version text, runner package metadata, or `gh` on initial `PATH` |
| Downloaded CLI archive identity | Official v2.96.0 URL plus SHA-256 `83d5c2ccad5498f58bf6368acb1ab32588cf43ab3a4b1c301bf36328b1c8bd60` | TLS alone, archive filename, redirect target, or version output alone |
| Expected executable path | Canonical temporary path recorded only after direct installation verification | Initial `PATH`, a symlink alias, or a later lookup alone |
| Executable selected by the verifier | Existing `shutil.which("gh")`, strict canonical resolution, regular-file check, executable check, and equality to the recorded path | A shell variable without canonical equality or runner-preinstalled CLI |
| Provider-API authentication | Existing verification-step-scoped `GH_TOKEN` consumed by the maintained verifier | Installation shell, checkout credentials, persisted auth, or an auth preflight |
| Frozen retained evidence | Checked `native_evidence_receipt.json` at canonical digest `sha256:5a13f99a5252828da01df0e2d2e5b8d491b99ec795736e5becc2659616a575c3` | Sidecar, current workflow, PR metadata, or fresh provider output alone |
| Current verification-authority match for a frozen receipt | Checked `native_evidence_verification_currentness.json` after exact binding and live `evidence_authority_input_manifest()` comparison | Frozen receipt's historical `verificationAuthorityInput`, successful historical CI, cache, or fallback |
| Sidecar-to-evidence binding | Exact `releaseIdentityDigest` and `evidenceReceiptDigest` inside the validated sidecar | Filename proximity, status text alone, caller assertion, or independently supplied digest |
| Candidate/provisional build-input currentness | Candidate or provisional receipt's `evidenceAuthorityInput` checked directly during its non-frozen lifecycle | Frozen-receipt sidecar or historical frozen snapshot |
| Release/provider acceptance | Existing complete receipt validation plus fresh exact provider comparison | Sidecar currentness alone |
| Tenant provisioning manifest and digest | Existing unchanged `ProvisioningSpec` policy embedding the unchanged frozen receipt | Sidecar, current verification manifest, replacement digest, or migration bypass |
| Temporal source authentication | Existing source-pin policy with only the final `native_release_identity.py` byte length and SHA-256 refreshed mechanically | New temporal state, classifier branch, or user assertion |
| Phase B authorization | Later exact same-task task-user approval of the complete version 2 card naming #313 | This RFC, the drafting authorization, version 1 approval, PR #312, GitHub activity, credentials, AI text, or checks |

The frozen receipt's `verificationAuthorityInput` is immutable historical
evidence of the authority snapshot present when the receipt was frozen. It is
not compared with current repository files after version 2. The sidecar is the
only live-currentness authority for a frozen checked receipt.

The sidecar is not retained release evidence and is never serialized into the
tenant provisioning manifest. The receipt is not a fallback when the sidecar
is absent or stale. The sidecar is not a fallback when the receipt is absent or
invalid. Both must validate for a production-reachable frozen-current result.

## 6. State machine and ordering

### 6.1 Frozen checked authority

```text
UNRESOLVED
  -> RELEASE_IDENTITY_CURRENT
  -> FROZEN_RECEIPT_CANONICAL_AND_VALID
  -> SIDECAR_CANONICAL
  -> SIDECAR_IDENTITY_BOUND
  -> SIDECAR_RECEIPT_BOUND
  -> SIDECAR_AUTHORITY_INPUT_CURRENT
  -> CURRENT_FROZEN_AUTHORITY_VALID
  -> PROTECTED_OPERATION_PERMITTED

Any missing, malformed, non-canonical, stale, wrong-type, wrong-identity,
wrong-receipt, provisional, or non-verified required input
  -> REFUSED
```

Ordering is strict:

1. load the release identity and validate its current source input;
2. read and completely validate the frozen receipt without treating its
   historical verification snapshot as current authority;
3. read the sidecar through a bounded, no-symlink regular-file path;
4. validate exact sidecar fields, canonical JSON bytes, schema, and status;
5. require the sidecar's release-identity digest to equal the already validated
   identity digest;
6. require the sidecar's receipt digest to equal the already validated frozen
   receipt digest;
7. require the sidecar's verification-authority manifest to equal a fresh
   manifest of the exact current authority paths; and
8. only then return the frozen receipt to the trusted caller or permit provider
   verification, manifest observation, migration, readiness, or external work.

The validation occurs in one loader stack. The sidecar result is not stored in
an optional capability bag, cache, mutable registry, or global currentness
flag. Existing callers continue to receive the fully validated receipt only
after the currentness gate succeeds.

### 6.2 Candidate and provisional lifecycle

A candidate or provisional receipt is not retained frozen evidence. Its
`evidenceAuthorityInput` continues to be compared directly with current files
when that lifecycle requests current validation. It cannot use the frozen
sidecar to become a candidate, frozen receipt, or current checked authority.

The existing finalization-only exception for the exact
`HISTORICAL_V1_CANDIDATE_RECEIPT_DIGEST` remains unchanged. It is a closed
historical migration replay, not currentness authority: it cannot select or
replace the sidecar, cannot authorize another candidate, and cannot produce a
production-reachable current frozen result without the exact bound sidecar.

Freezing a future candidate records its then-current verification snapshot as
historical receipt evidence. A separately generated sidecar must bind the new
frozen receipt before that receipt can become production-reachable current
authority.

This state-specific behavior is lifecycle separation, not a compatibility
fallback. A frozen receipt always requires the sidecar when current authority
is requested.

### 6.3 Exact CLI custody

```text
CHECKOUT_COMPLETED_WITHOUT_PERSISTED_CREDENTIAL
  -> TOKEN_FREE_INSTALLATION_SHELL_STARTED
  -> CHECKOUT_CREDENTIAL_ABSENCE_VERIFIED
  -> RUNNER_CLI_IGNORED
  -> ARCHIVE_DOWNLOADED
  -> ARCHIVE_DIGEST_VERIFIED
  -> EXECUTABLE_EXTRACTED_TO_FRESH_DIRECTORY
  -> DIRECT_VERSION_BYTES_VERIFIED
  -> CANONICAL_PATH_PUBLISHED
  -> VERIFIER_RESOLUTION_EQUAL
  -> CURRENT_FROZEN_AUTHORITY_VALID
  -> RELEASE_EVIDENCE_VERIFIED
```

The installation shell begins only after the exact pinned checkout returns
with `persist-credentials: false`. Before network access it verifies credential
configuration names and exit status without reading values. It receives no
`GH_TOKEN` or `GITHUB_TOKEN`, downloads without credentials, authenticates the
archive before extraction, invokes the direct canonical executable, requires
exit zero and empty stderr, compares stdout as raw bytes including the terminal
LF, and publishes PATH only after every check succeeds.

The following provider-verification step alone receives `GH_TOKEN`. It proves
that verifier-equivalent resolution selects the recorded canonical executable
before invoking the maintained verifier.

### 6.4 Forbidden transitions and time of check

There is no transition from a missing or invalid sidecar to historical receipt
currentness, from an invalid receipt to sidecar-only acceptance, from a stale
sidecar to provider verification, from an unverified archive to extraction,
from wrong version bytes to PATH publication, or from a red hosted lane to
merge.

No environment variable, database row, network result, PR label, package
resource, or caller-provided digest selects currentness authority. Existing
production gates remain before external database work. Importing
`provisioning_specs.py` remains free of native-authority file reads, and the
security-audit specification remains independent.

Undetectable mutation between validated reads is excluded by section 4.4.
Within the supported model, each current-authority observation performs fresh
checked-file reads and does not cache success.

## 7. Invariants and acceptance criteria

- **GHCLI-001 — Exact executable handoff.** Immediately before the maintained
  verifier is invoked, verifier-equivalent resolution selects the recorded
  canonical temporary `gh` path. Direct prepublication execution produced
  exactly `NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT`, including the terminal
  LF, with exit zero and empty stderr.
- **GHCLI-002 — Archive authentication before use.** No downloaded archive
  bytes are extracted, executed, selected, or published before their SHA-256
  matches the approved official archive digest.
- **GHCLI-003 — Token-free, non-disclosing, fail-closed installation.** The
  installation shell begins only after checkout with
  `persist-credentials: false`; before network access it checks only credential
  configuration names or exit status; it receives no GitHub token, reads no
  credential value, performs no authentication or credential mutation, and
  has no runner, package-manager, alternate-download, or auth fallback.
- **GHCLI-004 — Sidecar is the sole frozen-receipt currentness authority.** A
  production-reachable request for current frozen evidence requires one
  canonical checked sidecar whose verification-authority manifest equals the
  fresh exact current-file manifest. Missing, stale, malformed, provisional,
  symlinked, non-regular, or non-canonical sidecar input refuses before a
  protected result or external work. The frozen receipt's historical
  verification snapshot never substitutes.
- **GHCLI-005 — Exact provider reproduction.** After identity, receipt,
  sidecar, CLI, and token gates pass, fresh maintained provider verification is
  byte-equal to the retained provider-verification document.
- **GHCLI-006 — Complete exact-head gate.** Merge requires complete green
  hosted conformance at the exact pull-request head. No independent red lane,
  baseline failure, missing artifact, or pre-existing failure is waived.
- **GHCLI-007 — Closed ten-path envelope.** Every changed path between reviewed
  base `9c12c115bd29d9889234edd9e4c84377d9e332f8` and the exact head is one of the
  ten paths in section 11, and every path-specific restriction there holds.
- **GHCLI-008 — Frozen receipt and provisioning identity remain exact.** The
  checked receipt remains byte-for-byte equal to the reviewed-base 25,682-byte
  document with digest
  `sha256:5a13f99a5252828da01df0e2d2e5b8d491b99ec795736e5becc2659616a575c3`.
  Tenant provisioning canonical bytes and digest remain byte-for-byte equal to
  the reviewed base, including accepted digest
  `sha256:2ac8487b64d4fb09d7576ef1ee09ac1f2a3cc5b20558f0d2137620b897c7157c`.
- **GHCLI-009 — Exact binding and lifecycle separation.** The sidecar binds the
  exact validated release identity and exact validated frozen-receipt digest.
  A sidecar for another identity or receipt refuses. Candidate and provisional
  inputs cannot use a frozen sidecar, and frozen inputs cannot fall back to
  candidate direct-currentness semantics.

## 8. Production-reachable negative cases

| Invariant | Supported entry point | Counterexample that must refuse or fail |
| --- | --- | --- |
| `GHCLI-001` | Hosted retained-evidence verification step | Initial PATH selects runner `gh`, published PATH is ineffective, selected path is a symlink alias, stdout lacks its terminal LF, stderr is non-empty, or the direct command exits nonzero. Refuse before provider verification. |
| `GHCLI-002` | Hosted CLI installation step | The archive is truncated, substituted, redirected to wrong bytes, or extracted before digest comparison. Refuse before extraction or execution. |
| `GHCLI-003` | Checkout and installation steps | Checkout persists credentials; a local token-bearing extraheader remains; installation receives a token, reads a credential value, invokes `gh auth`, performs an authenticated preflight, or falls back after DNS failure. Refuse before download or authentication. |
| `GHCLI-004` | `verify-frozen-evidence-receipt`, `conformance-environment`, tenant provisioning, migration, readiness, CLI preflight, or `TENANT_PROVISIONING_SPEC.digest` | The checked frozen receipt is valid but the sidecar is absent or names an old workflow hash. The historical receipt snapshot still matches old files. Refuse before provider calls, manifest return, or database connection. |
| `GHCLI-005` | Maintained frozen-evidence verifier | GitHub release metadata, asset identity, attestation, immutable-release posture, or provider document differs. Refuse despite valid CLI and sidecar. |
| `GHCLI-006` | Pull-request merge gate | Arm64, Kernel baseline, package, artifact upload, or another hosted lane is red or missing. Merge stops. |
| `GHCLI-007` | Base-to-head pull-request audit | The receipt, provisioning implementation, migration, eleventh path, or unrestricted temporal change appears. Exact path review refuses approval and merge. |
| `GHCLI-008` | `TENANT_PROVISIONING_SPEC.canonical_manifest_bytes()`, `.digest`, tenant migration preflight, and receipt authentication | The sidecar is correct but the receipt changes, its historical snapshot is refreshed, or provisioning begins embedding the sidecar. Structured base/head byte comparison fails and merge stops. |
| `GHCLI-009` | Frozen current-authority loader and candidate/finalization entry points | A canonical sidecar binds another receipt or identity; a frozen receipt is accepted through direct historical-snapshot comparison; or a candidate is accepted through the checked frozen sidecar. Binding or lifecycle validation refuses. |

These counterexamples use checked-file or supported public behavior. Tests may
supply explicit temporary paths to production validators. Private-field
mutation and cached-state corruption are not acceptance evidence.

## 9. Proposed architecture and smallest coherent change

### 9.1 Preserve the frozen receipt

`deployment/postgresql/ofarm_ed25519/native_evidence_receipt.json` is removed
from the version 1 implementation diff and is not in the version 2 allowlist.
Its canonical bytes, digest, release link, candidate link, build pins, platform
evidence, retained provider verification, preservation evidence,
`evidenceAuthorityInput`, and `verificationAuthorityInput` remain unchanged.

For a frozen receipt, both embedded authority manifests are historical
evidence. The build snapshot remains authenticated by candidate reconstruction.
The verification snapshot remains authenticated as exact canonical receipt
content. Neither is compared with current repository files after version 2.

Candidate and provisional receipt validation still compares the candidate's
current build input where its lifecycle requires that check.

### 9.2 Add one canonical verification-currentness sidecar

Phase B adds exactly:

```text
deployment/postgresql/ofarm_ed25519/
  native_evidence_verification_currentness.json
```

Its exact schema is:

```json
{
  "evidenceReceiptDigest": "sha256:<exact frozen receipt digest>",
  "releaseIdentityDigest": "sha256:<exact release identity digest>",
  "schemaVersion": "ofarm.native-verifier-verification-currentness.v1",
  "status": "current",
  "verificationAuthorityInput": {
    "algorithm": "sha256",
    "digest": "sha256:<manifest digest>",
    "files": []
  }
}
```

The `files` value is the existing exact ordered `EVIDENCE_AUTHORITY_PATHS`
manifest with current byte lengths and SHA-256 values. The sidecar path is not
added to `EVIDENCE_AUTHORITY_PATHS`; including it would create a recursive
self-attestation. Its authority comes from checked source, exact binding, live
recomputation, review, and conformance—not from claiming its own digest.

The schema has no timestamp, actor, PR number, branch, environment selector,
optional field, signature claim, cached-success flag, or alternative receipt.
Its canonical document must be greater than zero bytes and no larger than
16 KiB. Phase B names that limit
`MAX_VERIFICATION_CURRENTNESS_BYTES = 16 * 1024`; no caller may raise or bypass
it.

### 9.3 Validate the sidecar in the existing current-authority loader

`deployment/postgresql/native_release_identity.py` adds:

- one exact checked-sidecar path constant;
- the exact 16 KiB maximum size and exact schema constant;
- one frozen, slot-backed validated sidecar value type;
- one canonical sidecar document constructor;
- one complete sidecar validator and regular-file loader; and
- the frozen-receipt currentness composition in
  `load_native_evidence_receipt()`.

When `verify_current_authority=True` and the receipt is frozen, the loader:

1. validates the receipt completely without comparing its historical
   verification snapshot with current files;
2. requires and loads the sidecar;
3. validates exact sidecar schema and canonical bytes;
4. binds it to the caller's already validated release identity and the loaded
   receipt digest; and
5. compares its verification-authority manifest with a fresh current manifest.

Only then does it return the existing `NativeEvidenceReceipt`. The return type
does not gain an optional currentness field. The sidecar result is a validation
gate, not mutable state that downstream callers can detach or reinterpret.

The checked sidecar path is the default for the checked receipt. Supported
custom-path tests and native-evidence commands pass their sidecar path
explicitly. No caller-supplied digest is accepted in place of loading the file.

When the receipt is candidate or provisional, its existing lifecycle-specific
current build-input validation applies and a frozen sidecar cannot authorize
it. When a frozen receipt requests current validation, absence of an explicit
or exact checked sidecar always refuses.

Version 2 does not change or broaden the exact historical-v1 candidate
finalization exception already enforced by `native_evidence.py`. That
finalization-only exception never substitutes for frozen-receipt sidecar
currentness.

### 9.4 Provide deterministic sidecar generation

`deployment/postgresql/native_evidence.py` adds one bounded offline command
that:

1. loads the current release identity with current-source verification;
2. loads and fully validates the frozen receipt without claiming currentness;
3. constructs the exact sidecar from those digests and the fresh existing
   authority manifest;
4. validates the constructed document through the production validator; and
5. writes canonical bytes to a caller-selected fresh output path without
   replacing the checked sidecar in place.

Maintainers generate to a fresh temporary path, review the exact document, and
replace the checked file through the ordinary repository diff. The command has
no network, provider, credential, database, receipt-rewrite, or approval side
effect.

Because the sidecar is excluded from its own authority manifest, it can be
generated after workflow, verifier, and test bytes are final without recursion.

### 9.5 Retain the proven exact CLI custody design

The conformance checkout keeps `fetch-depth: 0` and adds
`persist-credentials: false`. One token-free installation step:

1. checks credential-configuration names before network access without reading
   values;
2. creates one fresh dedicated directory under `RUNNER_TEMP`;
3. downloads the exact official `gh_2.96.0_linux_amd64.tar.gz`;
4. authenticates SHA-256 before extraction;
5. extracts only the executable;
6. canonicalizes and directly invokes it;
7. captures stdout and stderr into separate regular files;
8. requires exit zero, empty stderr, and exact raw stdout bytes; and
9. publishes the canonical executable and PATH only after validation.

The following verification step alone receives `GH_TOKEN`, repeats
verifier-equivalent path selection and equality, validates the frozen receipt
and currentness sidecar, and then performs the unchanged fresh provider
comparison.

Version 2 proposes reproducing the exact CLI implementation already
demonstrated green on #312, but only after independent version 2 approval in
#313. No implementation or authority transfers from #312. The reproduced
design does not weaken or redesign that proven custody mechanism.

### 9.6 Keep provisioning code unchanged

`deployment/postgresql/provisioning_specs.py` already requests
`verify_current_authority=True` before returning tenant native-authority
manifests or accepting frozen release authority. The loader's strengthened
composition makes that existing call validate the sidecar, while the returned
receipt remains the unchanged frozen receipt embedded in the existing manifest.

No provisioning production path changes. A focused provisioning-native-
authority test proves:

- stale or missing sidecar currentness refuses before a manifest or external
  database work;
- valid refreshed sidecar currentness permits the unchanged frozen receipt;
- canonical provisioning bytes equal the reviewed base; and
- the digest remains exactly
  `sha256:2ac8487b64d4fb09d7576ef1ee09ac1f2a3cc5b20558f0d2137620b897c7157c`.

Security-audit-only use continues to load neither tenant receipt nor sidecar.

### 9.7 Focused native-evidence evidence

`kernel/tests/test_postgresql_native_evidence.py` owns tests for:

- exact checkout, credential, archive, raw-byte, token, PATH, and fallback
  workflow properties;
- exact sidecar schema, canonical bytes, regular-file rules, and maximum size;
- exact identity and frozen-receipt binding;
- live current-authority equality;
- missing, stale, malformed, symlinked, non-regular, wrong-receipt, and
  wrong-identity refusal;
- historical frozen receipt snapshot non-authority;
- candidate/provisional versus frozen lifecycle separation;
- preservation of the exact historical-v1 finalization exception without
  broadening it or letting it authorize frozen currentness;
- deterministic generation and refusal to replace an existing output;
- unchanged receipt bytes and retained evidence; and
- fresh provider equality through the exact selected CLI.

The tests use supported loaders, commands, and checked-file copies. They do not
argue from private-field mutation.

### 9.8 Mechanical conformance integration

Changing `native_release_identity.py` requires mechanically refreshing only
its existing byte-length and SHA-256 entry in
`conformance/temporal_contract_candidate_check.py`.

No temporal state, branch, accepted migration, provisioning digest, marker,
source-path set, output, or classifier semantics may change.

`conformance/review_baseline_test_inventory.json` is mechanically regenerated
only for actual new or renamed test nodes.

### 9.9 No compatibility or fallback layer

Version 2 adds no accepted-receipt list, old/new currentness switch,
environment selector, optional sidecar, database fallback, migration adapter,
hard-coded replacement provisioning digest, mutable cache, or runtime
registry. The existing single historical-v1 candidate digest remains confined
to its unchanged finalization migration exception and is not a currentness
source.

For frozen evidence there is one receipt path and one sidecar path. Both are
required and exactly bound. The old receipt-refresh implementation is removed
from the final diff rather than supported alongside the sidecar.

## 10. Elegance audit

### 10.1 Sources of truth

There are six non-overlapping sources of truth:

1. one raw CLI version-output constant;
2. one official archive URL and authenticated archive digest;
3. one recorded canonical installed executable path;
4. one frozen receipt for retained release evidence and provisioning bytes;
5. one sidecar for live verification-authority currentness and exact binding;
   and
6. one maintained provider verifier for fresh-versus-retained equality.

Each owns one decision. The archive URL's version text cannot authorize stdout.
The receipt cannot authorize current repository bytes. The sidecar cannot
authorize retained provider evidence or provisioning bytes.

### 10.2 Authoritative transitions

There are six security-relevant transitions:

1. credential absence permits installation network access;
2. archive digest match permits extraction;
3. exact direct version bytes permit canonical PATH publication;
4. receipt validation permits sidecar binding;
5. exact sidecar binding and current manifest equality permit a current frozen
   authority result; and
6. canonical CLI equality plus current frozen authority permits fresh provider
   verification.

No transition skips or substitutes for another.

### 10.3 Duplicated fields, compatibility, and deletion

The frozen receipt still contains a field named `verificationAuthorityInput`
because deleting or rewriting it would mutate retained evidence. Its authority
role is deleted: it is historical content only. The sidecar field is the sole
live-currentness source.

Version 2 deletes the receipt refresh from the version 1 patch. It also deletes
the need for a provisioning witness, provisioning implementation edit, and
provisioning temporal pin refresh proposed by the rejected #313 design.

No compatibility shim or single-use wrapper is added. The sidecar type is a
durable independent authority document with its own lifecycle, validation,
generator, and negative cases.

A clean rewrite of release evidence is not justified. The smallest coherent
change preserves the accepted receipt, composes one sidecar into the existing
current-authority loader, and reuses the already proven CLI custody patch.

## 11. Pull-request boundary

The final pull request may change only these ten paths:

1. `docs/rfcs/OFARM_Native_Evidence_Provisioning_Witness_Execution_RFC_v0_1.md`
2. `docs/rfcs/OFARM_Native_Evidence_GitHub_CLI_Pin_Execution_RFC_v0_2.md`
3. `.github/workflows/conformance.yml`
4. `deployment/postgresql/native_release_identity.py`
5. `deployment/postgresql/native_evidence.py`
6. `deployment/postgresql/ofarm_ed25519/native_evidence_verification_currentness.json`
7. `kernel/tests/test_postgresql_native_evidence.py`
8. `kernel/tests/test_postgresql_provisioning_native_authority.py`
9. `conformance/temporal_contract_candidate_check.py`
10. `conformance/review_baseline_test_inventory.json`

Path 1 is the already published rejected witness RFC and remains an audit
record; Phase B must not alter it. Path 2 is the governing version 2 contract.
Path 9 may change only the existing `native_release_identity.py` source-pin
byte length and SHA-256. Path 10 is mechanical test-node inventory only.

The Phase A amendment changes only path 2 after amendment base
`d963bf45c030c08b89ff35dda893c77677a2a7a5`. Paths 3 through 10 remain
forbidden until the complete live card is shown and a later exact task-user
message approves version 2.

The following paths and effects are explicitly outside the envelope:

- `deployment/postgresql/ofarm_ed25519/native_evidence_receipt.json`;
- `deployment/postgresql/provisioning_specs.py`;
- every migration, catalog, tenant contract, release identity JSON, release
  asset, build source, security-audit path, and pull request #312 path not also
  reproduced inside the exact #313 allowlist;
- temporal classifier behavior or another source pin; and
- deployment, release publication, production data, or production authority.

This is one primary trust boundary. The provisioning test and mechanical
temporal source-pin update are verification/integration required to prove that
the native-evidence boundary did not change database authority. They do not
grant or modify provisioning, migration, or temporal authority.

Pull request #312 remains stopped and independently unmergeable. Its version 1
approval does not transfer. After a later approved and merged #313, #312 may be
closed as superseded only under separately valid GitHub write authority; this
decision does not close it.

Reviewers must not require a receipt refresh, provisioning implementation,
migration, accepted-digest change, security-audit change, release regeneration,
libsodium mirror, arm64 networking change, or cross-boundary exception in this
pull request.

## 12. Provisional design record

Not provisional.

The currentness sidecar is the intended durable authority model. Retained
release evidence is immutable; maintained verifier currentness is a separately
checked, exactly bound authority that may evolve without changing retained
evidence or database identity.

A future new release freezes a new receipt and requires a sidecar bound to that
receipt before it becomes current checked authority. A future verifier change
refreshes only the sidecar after its own review. A future receipt change remains
a release-evidence and provisioning-authority decision with the corresponding
analysis; it is not disguised as verifier maintenance.

The task approval mechanism remains provisional pre-deployment development
authority and must be replaced independently before deployment. That
procedural limitation does not make the technical sidecar temporary.

## 13. Traceability and verification

| Invariant | Owning change | Negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `GHCLI-001` | Two-step canonical executable handoff and raw-byte check | Runner CLI, wrong PATH, symlink alias, missing LF, stderr | Direct exact bytes and canonical equality | Focused workflow test plus hosted retained-evidence step |
| `GHCLI-002` | Archive SHA before extraction | Substituted or truncated archive | Approved digest precedes extraction | Focused workflow ordering assertion |
| `GHCLI-003` | Non-persisting checkout and token-free installation | Persisted extraheader, token env, auth command, network before check | Non-disclosing absence gate and no fallback | Focused checkout/installation negative assertions |
| `GHCLI-004` | Sidecar schema, loader, and frozen-current composition | Missing or stale sidecar with valid receipt | Refusal before provider, manifest, or database work | Focused sidecar tests plus provisioning-authority gate tests |
| `GHCLI-005` | Existing fresh provider comparison | Changed release or provider document | Fresh provider bytes equal retained bytes | Direct frozen-evidence verification |
| `GHCLI-006` | Exact-head merge gate | Any red or missing hosted lane | Complete exact-head green run | Hosted conformance |
| `GHCLI-007` | Ten-path allowlist and path-specific restrictions | Receipt, provisioning code, migration, or eleventh path | Base-to-head exact subset and restricted diffs | Git path and structured diff audit |
| `GHCLI-008` | Receipt exclusion plus unchanged provisioning consumer | Receipt refresh or sidecar serialization | Receipt and provisioning bytes/digests equal base | Structured base/head bytes plus existing digest tests |
| `GHCLI-009` | Exact sidecar identity/receipt links and lifecycle branch | Wrong receipt/identity or candidate-sidecar substitution | Binding and lifecycle refusal | Focused loader and generation tests |

### 13.1 Required Phase A verification

Before the live card:

- run `python3 conformance/ofarm_pkg_contract_check.py` under exact supported
  CPython 3.12.13;
- run `git diff --check`;
- prove that the amendment range changes only the version 2 RFC;
- prove that the complete PR Phase A diff contains only the rejected v0.1 audit
  RFC and this governing v0.2 RFC;
- confirm the reviewed base remains current `main`;
- bind and verify draft PR #313, its base, head, draft state, and description;
- review the complete exact RFC-only head once without constraint; and
- resolve every demonstrated in-scope Phase A Blocker before showing a card.

The known hosted CLI failure on the RFC-only base is not waived. It is the
problem Phase B must solve. Complete hosted conformance is required at the
implementation head, not used as fictional Phase A evidence.

### 13.2 Required Phase B verification

Before merge:

- focused workflow custody, archive ordering, token, raw-byte, and canonical
  path tests;
- exact sidecar schema, canonical encoding, size, regular-file, and binding
  tests;
- missing, stale, malformed, symlinked, non-regular, wrong-receipt, and
  wrong-identity sidecar negative cases;
- candidate/provisional versus frozen lifecycle negative cases;
- deterministic fresh-output generator tests;
- structured proof that `native_evidence_receipt.json` is byte-identical to the
  reviewed base with exact size and digest;
- structured proof that tenant provisioning canonical bytes and digest are
  byte-identical to the reviewed base;
- refusal-before-external-work tests for tenant provisioning, migration,
  readiness, and supported CLI paths;
- security-audit independence tests;
- fresh retained-provider verification using exact GitHub CLI `2.96.0`;
- exact diff proof that the temporal checker changed only the existing
  `native_release_identity.py` source-pin literals;
- mechanical canonical test-inventory regeneration;
- `python3 conformance/ofarm_pkg_contract_check.py` under CPython 3.12.13;
- `git diff --check`;
- exact base-to-head path and path-specific diff audit;
- complete hosted conformance at the exact head;
- exact-head technical review against `GHCLI-001` through `GHCLI-009`;
- compact PR scope, authority-evidence, check, review-disposition, and
  cancellation report; and
- direct retrieval of the original live card and later exact approval before
  merge.

## 14. Open decisions and review disposition

There are no open architecture decisions inside this proposed boundary.

- **Review 4943701301 Blocker 1:** addressed in the proposed design by keeping
  the frozen receipt byte-identical and making the receipt-bound sidecar the
  sole live-currentness authority. It is not closed until Phase B evidence and
  exact-head review pass.
- **Review 4943701301 Blocker 2:** acknowledged. Pull request #313 must record
  the actual approved/implemented posture, stable task/card/approval references,
  exact approval sentence, scope report, verification, disposition, and
  cancellation check before merge. Version 1 evidence from #312 is not reused.
- **Current Phase A gate:** no technical Blocker is presently demonstrated.
  Exact-head review remains required after this RFC is published and PR
  metadata is updated. Any violation of `GHCLI-001` through `GHCLI-009` found
  by that review is a Blocker.
- **Follow-ups:** administrative disposition of stopped PR #312 and independent
  arm64 network reliability only if separately authorized or demonstrated.
- **Preferences:** none.

Once every invariant passes, the exact allowlist and restrictions hold,
complete hosted conformance is green, approval evidence remains directly
retrievable and uncancelled, and no demonstrated in-scope Blocker remains, the
approved workflow permits merging only named draft pull request #313.

## 15. Pre-deployment decision workflow

The task-user message authorizing this version 2 Phase A draft is drafting
authority only. It is not Phase B approval. This RFC, commits, pushes, reviews,
checks, credentials, and GitHub activity also grant no Phase B authority.

The lawful sequence is:

1. add this RFC alone after amendment base
   `d963bf45c030c08b89ff35dda893c77677a2a7a5` in existing draft pull request
   #313;
2. update #313's title and description to the version 2 Phase A posture;
3. run the package, whitespace, amendment-path, full-PR-path, base, and PR
   binding checks;
4. review the exact RFC-only head;
5. display one complete live version 2 decision card in this same Codex task,
   naming #313 and the maximum ten-path envelope; and
6. wait for a later task-user message whose entire visible text is exactly:

```text
I approve OFARM2 decision ISSUE174-NATIVE-EVIDENCE-GITHUB-CLI-PIN-EXECUTION-001 version 2.
```

Only that later exact same-task message may authorize Phase B. The drafting
authorization, version 1 approval, generic approval, `go`, GitHub review,
comment, reaction, merge instruction, credentials, another task, AI text, tool
output, or a summary of unavailable task items never supplies approval.

Before recognizing approval, the AI must verify that the original complete
live card and later task-user approval remain directly retrievable in this task
in the required order, that the task-user role is exact, that no newer card
supersedes it, that #313 remains the named open draft PR, and that no later
stop, cancel, withdraw, pause, or do-not-merge message exists.

After valid approval, the AI may implement only paths 3 through 10 in #313.
It may update path 2 only to append compact AI-attested approval,
implemented-scope, check, review-disposition, and cancellation evidence without
changing the approved decision semantics. Path 1 remains immutable. Within
those restrictions, it may test, regenerate mechanical evidence, commit, push,
address in-boundary Blockers, update PR evidence, mark ready, and merge only
after every gate passes. It must not edit, merge, or close #312 under this
authority.

The future live card must state the decision identity and version, problem,
recommended decision, primary trust boundary, authority map, primary risk and
bound, permitted effects, non-effects, `GHCLI-001` through `GHCLI-009`, maximum
ten-path envelope, named draft PR, verification gates, reapproval triggers,
provisional posture, merge posture, and exact approval sentence.

A new decision version is required if the problem, recommended decision,
primary trust boundary, authority map, primary risk or bound, permitted effect,
non-effect, invariant, maximum path envelope, named pull request, irreversible
behavior, provisional posture, or merge posture changes. Closing #313 unmerged
expires authority.

Task messages remain approval authority. Any later repository approval record
is AI-attested evidence only and never deployment authority.
