# OFARM Native-Evidence GitHub CLI Pin Execution — Phase A Contract v0.1

**Status:** Phase A draft for exact-head review; no Phase B implementation,
merge, deployment, release, or production authority

**Contract identity:**
`ofarm2.native-evidence-github-cli-pin-execution.v0.1`

**Decision identity:**
`ISSUE174-NATIVE-EVIDENCE-GITHUB-CLI-PIN-EXECUTION-001`, proposed version `1`

**Issue relationship:** issue #174 remains closed; this is bounded post-closure
maintenance of its retained native-evidence verification workflow

**Reviewed base:** `9c12c115bd29d9889234edd9e4c84377d9e332f8`

**Named draft pull request:** pending initial RFC-only publication; this field
must name the created draft pull request before exact-head Phase A review or a
live decision card

**Primary trust boundary:** native release-evidence verifier toolchain
selection and workflow custody

**Phase A head boundary:** this RFC only

**Maximum final pull-request path envelope:** exactly the five paths listed in
section 11

**Dependent pull request:** draft pull request #311 may consume this correction
only after this prerequisite merges to `main`; #311 is not the named pull
request for this decision

## 1. Problem and goal

Hosted runners can replace their preinstalled `gh`. The retained native-release
evidence verifier requires the exact raw output bytes of GitHub CLI `2.96.0`.
Conformance run 922 for pull request #311 failed before pull-request-specific
tests because the hosted runner's CLI did not satisfy that frozen requirement.

This task establishes one independently authenticated CLI installation for the
existing retained-evidence verification step. The workflow will download the
official CLI archive, authenticate its exact bytes, select one canonical
executable path, and prove that the unchanged verifier resolves that exact path.

GitHub CLI provider-API authentication means only the existing verification-
step-scoped `GH_TOKEN`. The installation shell receives neither `GH_TOKEN` nor
`GITHUB_TOKEN` and executes only after the exact pinned checkout action returns
with `persist-credentials: false`. The installation shell must not invoke
`gh auth login`, `gh auth setup-git`, write a credential store, persist
authentication state, or perform an additional authenticated preflight.

Pinned actions may consume `github.token` inside their own action boundaries.
They do not authorize token exposure or persistence into the later installation
shell.

## 2. Learning value

The change removes mutable runner software and persisted checkout credentials
from the CLI installation boundary while preserving the accepted frozen release
identity, assets, provider evidence, verification semantics, and fail-closed
behavior.

## 3. Non-goals

This pull request does not:

- change the accepted GitHub CLI version or the verifier's selection, process,
  API, Sigstore, or provider-comparison behavior;
- change release identity, release assets, attestations, build pins, candidate
  evidence, build evidence, or retained provider verification;
- reopen issue #174's database scope, migrations, provisioning, or accepted
  release-evidence semantics;
- address the independent arm64 DNS timeout that affected run 922;
- change security-audit behavior or add hosted-conformance implementation to
  pull request #311;
- add a package manager, runner-CLI fallback, runtime module, verifier option,
  compatibility path, credential store, or alternate evidence authority;
- change token use inside an exact pinned action's own execution boundary;
- change any active OFARM baseline, semantic contract, artifact set, or
  capability claim; or
- authorize deployment, release, production access, current/default promotion,
  or a production security waiver.

## 4. Trust model

### 4.1 Protected assets

- the frozen native release identity and retained release assets;
- the retained provider-verification document and exact fresh-equality check;
- canonical selection of the executable used for provider verification;
- the step-scoped GitHub token and absence of token custody in installation;
- the current verification-authority snapshot; and
- honest refusal when installation, selection, authentication, download, or
  provider verification is ambiguous.

### 4.2 Trusted components

- the exact commit-pinned workflow actions;
- the conformance checkout action configured with
  `persist-credentials: false`;
- SHA-256 and the reviewed official archive digest;
- the authenticated official GitHub CLI release archive;
- the pinned Python 3.12.13 environment;
- the existing `native_evidence.py` verifier and
  `native_release_identity.py` constants;
- GitHub Release and Sigstore verification; and
- the hosted runner's basic download, regular-file, permission, hashing, and
  extraction tools.

### 4.3 Untrusted inputs and state

- the runner-preinstalled `gh` and initial `PATH`;
- downloaded bytes before digest verification;
- every executable path before strict canonical resolution and file checks;
- unexpected local Git credential configuration;
- network and GitHub API responses before the existing cryptographic and exact
  provider checks; and
- missing, malformed, substituted, redirected, truncated, or unavailable
  archive responses.

### 4.4 Explicitly excluded attacker capabilities

Compromised official GitHub release custody, SHA-256 compromise, runner-root
compromise, arbitrary undetectable filesystem mutation, local source
substitution outside the reviewed diff, compromised dependencies, and trusted
operator compromise are out of scope.

Ordinary runner-image drift, PATH ambiguity, stale checkout credential
persistence, network failure, archive substitution, wrong version bytes,
stderr output, stale authority receipts, and changed provider evidence remain
in scope and must fail closed.

## 5. Authority map

| Decision | Sole authority |
| --- | --- |
| Accepted CLI stdout bytes | Existing `NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT` |
| Downloaded archive identity | Official v2.96.0 URL and SHA-256 `83d5c2ccad5498f58bf6368acb1ab32588cf43ab3a4b1c301bf36328b1c8bd60` |
| Expected executable path | Canonical temporary path recorded after direct installation verification |
| Executable selected by the verifier | `shutil.which("gh")`, strict canonical resolution, regular-file check, and executable check |
| GitHub CLI provider-API authentication | Existing verification-step-scoped `GH_TOKEN` consumed by the unchanged verifier |
| Checkout credential persistence | Exact pinned conformance checkout action with `persist-credentials: false` |
| Current authority snapshot | Existing `evidence_authority_input_manifest()` |
| Release/provider acceptance | Existing native-evidence verifier and frozen receipt |
| Pull-request path boundary | Exact five-path allowlist in section 11 |

The version string present in the archive URL is only an installation selector.
The existing raw-byte constant remains the sole acceptance authority for the
executable's version output. A mismatched selector cannot become permission
because both the installation step and unchanged verifier refuse it.

## 6. State machine and ordering

```text
CHECKOUT_COMPLETED_WITHOUT_PERSISTED_CREDENTIAL
→ TOKEN_FREE_INSTALLATION_SHELL_STARTED
→ CHECKOUT_CREDENTIAL_ABSENCE_VERIFIED
→ RUNNER_CLI_IGNORED
→ DOWNLOADED
→ DIGEST_VERIFIED
→ EXTRACTED_TO_FRESH_DIRECTORY
→ VERSION_BYTES_VERIFIED
→ PATH_ENTRY_PUBLISHED_FOR_SUBSEQUENT_STEPS
→ VERIFIER_RESOLUTION_VERIFIED
→ RELEASE_EVIDENCE_VERIFIED
```

The conformance job's exact pinned checkout step must retain `fetch-depth: 0`
and add:

```yaml
persist-credentials: false
```

### 6.1 Installation step

The installation shell begins only after that checkout action returns. It:

1. receives neither `GH_TOKEN` nor `GITHUB_TOKEN`;
2. before any network access, download, archive processing, PATH publication,
   or executable invocation, verifies that no checkout token-bearing local Git
   configuration remains;
3. inspects only configuration names or command exit status during that check
   and never reads, prints, captures, or otherwise exposes credential values;
4. creates one fresh, dedicated subdirectory under `RUNNER_TEMP`;
5. downloads the exact archive without credentials;
6. verifies the approved SHA-256 before extraction;
7. extracts only the required executable into the dedicated directory;
8. canonicalizes its direct path and verifies that it is a regular executable;
9. invokes that direct canonical path, never `gh` through `PATH`;
10. captures stdout and stderr into separate regular files without shell
    command substitution;
11. requires exit status zero and empty stderr;
12. uses the pinned Python environment to compare stdout bytes with
    `NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT`, including both ASCII lines and
    the terminal LF;
13. records the canonical path through a dedicated `GITHUB_ENV` variable; and
14. writes its containing directory to `GITHUB_PATH` only after every preceding
    check succeeds.

### 6.2 Frozen-evidence verification step

The subsequent verification step alone receives `GH_TOKEN`. Immediately before
invoking the existing verifier, it:

1. reads the recorded canonical path;
2. resolves `gh` using verifier-equivalent `shutil.which`, strict
   `Path.resolve`, regular-file, and executable checks;
3. requires the observed canonical path to equal the recorded path; and
4. invokes the unchanged verifier, which repeats its own selection and exact-
   byte checks and retains that selected path for every CLI call.

### 6.3 Forbidden transitions

The workflow must not download before the non-disclosing credential-absence
check, extract before digest verification, publish PATH before exact version-
byte verification, invoke provider verification before canonical path equality,
or recover through a runner CLI, package manager, authentication path,
credential mutation, alternate download, or version fallback.

## 7. Invariants and acceptance criteria

- **GHCLI-001 — Exact executable handoff.** Immediately before the existing
  verifier is invoked, the canonical path obtained using the verifier's
  selection semantics equals the recorded canonical temporary `gh` path. The
  direct prepublication version command produced exactly
  `NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT`, including the terminal LF, with
  exit zero and empty stderr.
- **GHCLI-002 — Archive authentication before use.** No downloaded bytes are
  extracted, executed, or selected before the archive digest matches the
  approved SHA-256.
- **GHCLI-003 — Token-free, non-disclosing, fail-closed installation.** The
  installation shell begins only after the exact pinned checkout action
  completes with `persist-credentials: false`. Before any network access,
  download, archive processing, PATH publication, or execution, that shell
  verifies that no checkout token-bearing local Git configuration remains. The
  check inspects only configuration names or exit status and never reads,
  prints, captures, or otherwise exposes credential values. The shell receives
  no `GH_TOKEN` or `GITHUB_TOKEN` and performs no authentication or credential
  mutation. Any failure stops without fallback.
- **GHCLI-004 — Current authority receipt.** The frozen receipt's
  `verificationAuthorityInput` exactly matches the resulting current authority
  files. Every retained release, candidate, build, platform, preservation, and
  provider-verification field remains unchanged.
- **GHCLI-005 — Exact provider reproduction.** Fresh provider verification
  under the selected exact CLI remains byte-equal to retained provider
  verification.
- **GHCLI-006 — Complete exact-head gate.** Merge requires complete green
  hosted conformance at the exact pull-request head. An independent red lane is
  not waived.
- **GHCLI-007 — Closed path allowlist.** Every changed path between reviewed
  base `9c12c115bd29d9889234edd9e4c84377d9e332f8` and the exact head belongs to
  the five-path allowlist in section 11.

## 8. Production-reachable negative cases

- A hosted runner supplies another `gh`, PATH publication is ineffective, or a
  different symlink is resolved: `GHCLI-001` refuses before the verifier.
- Version stdout lacks its terminal LF, adds bytes, exits nonzero, or writes
  stderr: `GHCLI-001` refuses before PATH publication.
- The `gh_2.96.0_linux_amd64.tar.gz` archive is substituted or truncated:
  `GHCLI-002` refuses before extraction.
- Checkout omits `persist-credentials: false`, enables credential persistence,
  or leaves a token-bearing local Git configuration: `GHCLI-003` refuses before
  download without reading or exposing the credential value.
- Installation receives a token, invokes `gh auth`, performs an authenticated
  preflight, or writes authentication state: `GHCLI-003` refuses.
- Download or DNS fails: `GHCLI-003` fails closed without using the runner CLI.
- Workflow or test bytes change while the receipt remains stale: `GHCLI-004`
  refuses.
- Release metadata, asset identity, attestation, or provider document differs:
  `GHCLI-005` refuses.
- Arm64 or another hosted lane remains red: `GHCLI-006` prevents merge.
- Any changed path falls outside the exact allowlist: `GHCLI-007` refuses
  approval and merge.

## 9. Proposed architecture and smallest change

The conformance job's exact pinned checkout keeps `fetch-depth: 0` and adds
`persist-credentials: false`.

One installation step immediately before retained-evidence verification will:

1. prove checkout credential absence without inspecting credential values;
2. create a fresh dedicated `RUNNER_TEMP` subdirectory;
3. download the official `gh_2.96.0_linux_amd64.tar.gz` archive;
4. verify its approved SHA-256 before extraction;
5. verify exact version stdout bytes through direct invocation and regular
   output files; and
6. publish the verified canonical path through `GITHUB_ENV` and its containing
   directory through `GITHUB_PATH`.

Shell command substitution is not sufficient for version output and is
forbidden for that comparison.

The following verification step reproduces the existing verifier's executable-
selection semantics and compares its canonical result with the recorded path
before calling the unchanged verifier.

One focused workflow test will enforce:

- `persist-credentials: false` on the exact pinned conformance checkout action;
- credential-absence verification before installation network access, without
  reading or printing credential values;
- no installation-step `GH_TOKEN` or `GITHUB_TOKEN`;
- the exact archive URL and digest;
- a fresh dedicated extraction directory;
- digest verification before extraction;
- direct canonical executable invocation;
- regular-file stdout and stderr capture;
- exit-zero, empty-stderr, and imported raw-byte comparison;
- no command-substitution-only version check;
- state publication only after byte verification;
- verifier-equivalent path resolution in the subsequent step;
- `GH_TOKEN` only on the provider-verification step; and
- absence of CLI, package-manager, alternate-download, credential, and
  authentication fallbacks.

After the workflow and test bytes are final, the frozen receipt mechanically
refreshes only `verificationAuthorityInput`. A dedicated new test node makes
the invariant-to-test ownership explicit; the canonical test inventory is
regenerated mechanically.

No verifier code changes. No new helper module. No release regeneration.

## 10. Elegance audit

### 10.1 Sources of truth

There are five non-overlapping sources of truth:

1. the existing raw CLI version-output constant;
2. the workflow's exact official archive URL and digest;
3. the recorded canonical installed path;
4. the existing current-authority manifest function; and
5. the existing frozen receipt plus fresh exact provider comparison.

The URL's version component selects an archive but cannot authorize its output;
the raw-byte constant remains acceptance authority. No duplicated field can
independently grant permission.

### 10.2 Authoritative transitions

Three transitions confer new workflow state:

1. digest match permits extraction;
2. exact direct version bytes permit PATH publication; and
3. canonical path equality permits existing provider verification.

No fallback or alternate transition remains active.

### 10.3 Compatibility and deletion

The runner-preinstalled CLI is ignored rather than wrapped. No compatibility
surface or single-use abstraction is added. Nothing in the existing verifier
is obsolete. A clean rewrite is less coherent than the bounded workflow
installation and test change.

## 11. Pull-request boundary

The pull request may change only the following five paths:

1. `docs/rfcs/OFARM_Native_Evidence_GitHub_CLI_Pin_Execution_RFC_v0_1.md`
2. `.github/workflows/conformance.yml`
3. `kernel/tests/test_postgresql_native_evidence.py`
4. `conformance/review_baseline_test_inventory.json`
5. `deployment/postgresql/ofarm_ed25519/native_evidence_receipt.json`

Mechanical absence is permitted when inventory regeneration produces unchanged
bytes. No sixth path is permitted.

The Phase A draft head changes only path 1. Paths 2 through 5 remain forbidden
until a valid live card and later exact task-user approval authorize Phase B in
the named draft pull request.

Issue #174 remains closed. This decision is bounded post-closure maintenance of
the #174-owned retained native-evidence verification workflow. It does not
reopen #174's database scope, accepted migrations, release identity, release
assets, provider evidence, or accepted release-evidence semantics.

This prerequisite pull request merges to `main` first. Pull request #311 is then
updated onto that main head without adding hosted-conformance implementation to
its semantic diff. Its canonical test inventory is mechanically regenerated
against the combined tree, and all exact-head review and complete hosted-
conformance gates are rerun. The CLI repair must remain absent from #311's own
resulting diff.

Reviewers must not require security-audit changes, release regeneration,
libsodium mirroring, arm64 networking changes, or another #174 database change
in this pull request.

## 12. Provisional design record

Not provisional at the technical boundary. GitHub CLI `2.96.0` is already part
of the frozen verification contract, and this change supplies that existing
requirement without relaxing it.

The approval mechanism is provisional pre-deployment repository-development
authority. Before deployment it must be replaced by an independently human-
controlled and independently verifiable approval or signing system. This
decision never supplies deployment authority.

## 13. Traceability and verification

| Invariant | Owning change | Negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `GHCLI-001` | Two-step path handoff and raw-byte version check | Runner CLI, wrong PATH, symlink, missing LF, stderr | Exact direct bytes and canonical equality | Focused workflow test plus exact-head hosted run |
| `GHCLI-002` | SHA before extraction | Substituted or truncated archive | Approved digest precedes extraction | Focused workflow ordering assertion |
| `GHCLI-003` | Non-persisting checkout and token-free installation | Persisted extraheader, token env, auth command, network before check | Non-disclosing absence gate and no fallback | Checkout and installation negative assertions |
| `GHCLI-004` | Mechanical receipt refresh | Stale authority snapshot or changed retained field | Current manifest equality and retained-field preservation | Receipt current-authority test and structured before/after comparison |
| `GHCLI-005` | Existing verifier unchanged | Changed release or provider document | Fresh provider bytes equal retained bytes | Direct frozen-evidence verification |
| `GHCLI-006` | Merge gate | Any red hosted lane | Complete exact-head green run | Hosted conformance |
| `GHCLI-007` | Five-path allowlist | Any sixth changed path | Base-to-head diff subset | Exact path comparison |

Required Phase A verification before the live card:

- `python3 conformance/ofarm_pkg_contract_check.py`;
- `git diff --check`;
- exact Phase A path check proving that only this RFC changed; and
- exact-head Phase A review after the named draft PR is recorded in this RFC.

Required Phase B verification before merge:

- focused native-evidence workflow tests;
- checkout credential-persistence and installation-token assertions;
- receipt current-authority validation;
- structured confirmation that only `verificationAuthorityInput` changed
  inside the frozen receipt;
- canonical test-inventory regeneration;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- `git diff --check`;
- exact path comparison equivalent to
  `git diff --name-only 9c12c115bd29d9889234edd9e4c84377d9e332f8...HEAD`;
- direct frozen-evidence verification using exact CLI `2.96.0`; and
- complete hosted conformance at the exact head.

## 14. Open decisions and review disposition

There are no open architecture decisions inside this trust boundary.

- **Blockers:** none in the proposed technical design; Phase B remains
  unauthorized until the RFC-only draft PR is created, bound here, reviewed at
  its exact head, followed by one complete live card and the exact later task-
  user approval.
- **Follow-up:** arm64 download reliability only if separately demonstrated;
  it cannot expand this pull request.
- **Preferences:** none.

Once `GHCLI-001` through `GHCLI-007` pass, the exact path allowlist holds,
complete hosted conformance is green, and no demonstrated in-scope Blocker
remains, the approved workflow permits merging only the named pull request.

## 15. Pre-deployment decision workflow

This RFC grants no Phase B authority by authorship, commit, push, draft pull-
request creation, review, or GitHub activity.

The lawful sequence is:

1. publish this RFC alone in one new draft pull request created from reviewed
   base `9c12c115bd29d9889234edd9e4c84377d9e332f8`;
2. bind that stable pull-request URL into this RFC;
3. rerun the package-contract check, `git diff --check`, and exact Phase A path
   check;
4. review the exact RFC-only head;
5. display one complete live decision card in the same Codex task, naming that
   draft pull request and the maximum five-path envelope; and
6. wait for a later task-user message whose entire visible text is exactly:

```text
I approve OFARM2 decision ISSUE174-NATIVE-EVIDENCE-GITHUB-CLI-PIN-EXECUTION-001 version 1.
```

Only that later same-task message may authorize Phase B. Generic approval,
`go`, GitHub review, comment, reaction, merge, credentials, another task, AI or
tool output, or a summary of unavailable task items never supplies approval.

After valid approval, the AI may implement paths 2 through 5 in the same named
draft pull request, test, regenerate mechanical evidence, commit, push, address
in-boundary Blockers, mark ready, and merge only after every gate passes. No
additional confirmation is required for those in-envelope actions.

The future live card must state the decision identity and version, problem,
recommended decision, primary trust boundary, authority map, primary risk and
bound, permitted effects, non-effects, `GHCLI-001` through `GHCLI-007`, maximum
five-path envelope, named draft pull request, verification gates, reapproval
triggers, provisional posture, merge posture, and exact approval sentence.

Reapproval under a new decision version is required if the problem,
recommended decision, primary trust boundary, authority map, primary risk or
bound, permitted effect, non-effect, invariant, maximum path envelope, named
pull request, irreversible behavior, provisional posture, or merge posture
changes. Closing the named pull request unmerged expires authority. Any later
same-task stop, cancel, withdraw, or pause message pauses work immediately.

The task messages remain approval authority. Any later repository approval
evidence is AI-attested evidence only.
