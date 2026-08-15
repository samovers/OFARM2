# OFARM Native-Evidence Provisioning Witness Execution — Phase A Contract v0.1

**Status:** proposed; Phase A only; no implementation, database, release, or
deployment authority

**Contract identity:**
`ofarm2.native-evidence-provisioning-witness-execution.v0.1`

**Decision identity:**
`ISSUE174-NATIVE-EVIDENCE-PROVISIONING-WITNESS-EXECUTION-001`, proposed
version `1`

**Issue relationship:** issue #174 remains closed; this is bounded
post-closure repair of a newly demonstrated provisioning-authority coupling

**Demonstrating pull request:**
`https://github.com/samovers/OFARM2/pull/312`

**Implementation pull request:** to be bound after the RFC-only branch is
published as one draft pull request

**Reviewed base:** `9c12c115bd29d9889234edd9e4c84377d9e332f8`

**Primary trust boundary:** tenant PostgreSQL provisioning authority that
selects which validated native release-evidence bytes enter the immutable
provisioning manifest and digest

**Phase A review-head boundary:** this RFC only

## 1. Problem and goal

Pull request #312 demonstrated a coupling that did not exist the last time the
native evidence receipt was refreshed. The tenant provisioning manifest loads
the complete current `native_evidence_receipt.json`, including its
`verificationAuthorityInput`, and hashes that complete document into the
tenant provisioning-spec digest.

The current receipt has two different jobs:

1. prove that the checked release evidence is still verified by the current
   workflow and test authority; and
2. provide immutable release-evidence bytes to the tenant provisioning
   manifest.

Those jobs have different change lifecycles. A workflow-only authority refresh
must update job 1. It must not silently create a new database provisioning
identity for job 2.

On #312, the intended workflow and test change mechanically updates only the
receipt's `verificationAuthorityInput`. That changes the tenant provisioning
digest from the accepted
`sha256:2ac8487b64d4fb09d7576ef1ee09ac1f2a3cc5b20558f0d2137620b897c7157c`
to
`sha256:1f080c4d786f8f276bc89e29fcd7297b0c6b73b8906ab9cfbe94f69d6c02792e`.
Hosted conformance then repeatably refuses migration 0009 because the version-8
tenant structure carries the accepted digest.

This contract establishes two explicit authorities:

- the current receipt remains the mandatory live-currentness gate; and
- one immutable provisioning witness supplies the receipt bytes embedded in
  the tenant provisioning manifest.

The initial witness is an exact copy of the already accepted receipt at the
reviewed base. Therefore this repair changes authority ownership in code but
does not change one byte of the resulting provisioning manifest, its digest,
the migration ledger, or the database catalog.

## 2. Learning value

This change validates that repository verification currentness and durable
database identity can be separated without weakening either one.

It reduces a demonstrated risk: routine maintenance of the hosted verifier can
no longer force a database migration merely because current workflow or test
bytes changed. At the same time, a stale current receipt, a substituted
provisioning witness, or a new release identity still fails closed.

## 3. Non-goals

This contract does not:

- change any PostgreSQL migration, migration set, prefix digest, structural
  digest, catalog identity, schema, role, grant, transaction, or durability
  behavior;
- change the accepted tenant provisioning manifest bytes or digest;
- change native release identity, release artifacts, candidate evidence,
  provider verification, preservation evidence, build pins, or signature
  semantics;
- change `native_release_identity.py`, `native_evidence.py`, or their receipt
  schemas and validators;
- change the conformance workflow or implement the GitHub CLI repair from
  pull request #312;
- authorize, amend, merge, or transfer the approval attached to pull request
  #312;
- change the temporal classifier's states, accepted migrations, marker law,
  authority contracts, or production/legacy reachability rules;
- change security-audit provisioning or any #192 authority;
- update pull request #311;
- deploy, publish a release, promote current/default state, access production
  data, or waive a security or conformance failure.

Pull request #312 remains draft and independently governed. After this
prerequisite merges, #312 must obey its own stronger base, approval, exact-path,
review, and reapproval rules before it can continue.

## 4. Trust model

### 4.1 Protected assets

The protected assets are:

- the accepted tenant provisioning manifest bytes and digest;
- the exact release identity and frozen provider evidence already admitted to
  tenant provisioning;
- the requirement that the current native evidence receipt match current
  verification-authority files before tenant provisioning, migration,
  readiness, or manifest observation can proceed;
- the distinction between current verification authority and an immutable
  provisioning witness;
- the accepted migration and catalog identities; and
- security-audit independence from tenant native-release files.

### 4.2 Trusted components

This boundary trusts:

- `load_native_release_identity(..., verify_current_sources=True)` to validate
  the checked release identity and its current source input;
- `load_native_evidence_receipt(..., verify_current_authority=True)` to
  validate the current receipt against current authority files;
- the same receipt loader without current-authority comparison to validate the
  immutable witness's canonical schema, release-identity link, build pins,
  candidate link, platform evidence, and preservation evidence;
- canonical JSON encoding and SHA-256 already used by `ProvisioningSpec`;
- the existing pre-external-work tenant authority gates in provisioning,
  migration, readiness, and CLI entry points;
- Git diff, review, and CI only as mechanical evidence, never as approval
  authority; and
- the later exact same-task user approval defined in section 15 as
  provisional pre-deployment decision authority.

### 4.3 Untrusted actors and inputs

The boundary treats as untrusted:

- missing, malformed, non-canonical, symlinked, non-regular, or substituted
  identity, current-receipt, and witness files;
- a current receipt whose authority manifest is stale;
- a witness linked to another release identity or carrying changed release,
  build, candidate, platform, provider, or preservation evidence;
- caller-supplied paths used by focused tests;
- repository branch names, credentials, PR metadata, comments, reviews, and
  check labels as authority;
- the fact that the initial current receipt and witness have identical bytes;
  that equality does not make either file a fallback for the other; and
- mechanically calculated file hashes until the reviewed implementation and
  tests confirm them.

### 4.4 Explicitly excluded capabilities

The threat model excludes:

- arbitrary in-process mutation after a bound authority object is created;
- undetectable filesystem mutation between validated reads;
- compromised Python, operating system, kernel, cryptographic dependencies,
  Git, GitHub, CI, or storage capable of forging all reviewed evidence;
- a malicious operator or task user intentionally approving a harmful design;
- compromise of the Codex platform, transport, or user account; and
- production deployment, production credentials, and production data.

Repository source substitution visible in the ordinary diff, stale checked
files, missing files, wrong file types, and inconsistent identity links remain
in scope and must refuse.

## 5. Authority map

There is one source of authority for each decision:

| Decision | Sole authority | Explicitly not authority |
| --- | --- | --- |
| Native release identity | Checked `native_release_identity.json` validated against its current source input | Witness filename, current receipt filename, PR metadata, or branch name |
| Current verification-authority match | Checked `native_evidence_receipt.json` loaded with current-authority verification | Provisioning witness, cached digest, or successful historical CI |
| Receipt bytes embedded in tenant provisioning | Checked `native_evidence_provisioning_witness.json` loaded as an immutable receipt witness | Current receipt, a fallback copy, runtime environment, or database row |
| Tenant provisioning manifest and digest | Existing canonical `ProvisioningSpec` manifest and SHA-256 policy after the bound authority set validates | A hard-coded replacement digest or migration bypass |
| Frozen release readiness | The bound identity, current receipt, and witness all have the exact frozen/verified posture | Any one document alone |
| Temporal provisioning source pin | Existing temporal checker constant mechanically refreshed from final `provisioning_specs.py` bytes | New temporal state, classifier branch, or user assertion |
| Phase B authorization | Later exact same-task user message approving the complete live card and named draft PR | This RFC, `go`, GitHub activity, credentials, AI text, or checks |

The current receipt and witness are not aliases. The current receipt answers
whether repository verification authority is current. The witness answers
which already accepted receipt bytes are part of the durable provisioning
identity. Both are mandatory; neither can substitute for the other.

The witness at this reviewed base is exactly 25,682 bytes with SHA-256
`9636997d7985153af627ee6764db31f67dba7604a64697a56ab74c970b875e82`.
These are reviewer evidence, not values the task user must verify.

## 6. State machine and ordering

The authority-loading state machine is:

```text
UNRESOLVED
  -> RELEASE_IDENTITY_CURRENT
  -> CURRENT_RECEIPT_CURRENT
  -> PROVISIONING_WITNESS_VALID
  -> FROZEN_AUTHORITY_SET
  -> MANIFEST_READY

Any missing, malformed, current-receipt-stale, identity-mismatched,
provisional, or non-verified input
  -> REFUSED
```

Ordering is strict:

1. load the release identity and verify its current source input;
2. load the current receipt with `verify_current_authority=True`;
3. load the immutable witness with `verify_current_authority=False`, using the
   same already validated identity;
4. bind the three validated objects into one immutable authority object;
5. require frozen identity, frozen current receipt, frozen witness, and
   verified preservation posture where the existing gate requires it;
6. construct the existing provisioning manifest using the release identity
   and witness, not the current receipt; and
7. return canonical bytes or a digest only after every required validation
   succeeds.

No fallback from a missing witness to the current receipt exists. No fallback
from a stale current receipt to the witness exists. No environment variable,
database value, network read, or package resource selects either path.

The existing normal tenant entry points already call the frozen-authority gate
before external work. This contract preserves that ordering. Importing
`provisioning_specs.py` remains free of native-authority file I/O, and the
security-audit spec remains independent.

The bound object is immutable. This design does not add caching or a mutable
registry. Each public manifest or digest observation performs the current
validated reads, matching the existing lazy behavior.

## 7. Invariants and acceptance criteria

- **NPW-001 — Currentness remains mandatory.** Every production-reachable
  tenant native-authority gate and every tenant provisioning manifest or digest
  observation refuses when the current receipt does not match current
  verification-authority files, even when the witness is valid.
- **NPW-002 — One immutable embedded witness.** Exactly one checked witness
  path supplies the evidence-receipt digest and document embedded in tenant
  provisioning. The witness must pass the complete frozen receipt schema and
  release-identity validation that does not assert current repository bytes.
- **NPW-003 — One bound release identity.** The identity, current receipt, and
  witness are validated through one immutable bound object and both receipts
  must link to that exact identity. No independently supplied digest can join
  them.
- **NPW-004 — Provisioning identity is byte-stable.** On the reviewed base,
  the new implementation produces byte-for-byte identical tenant provisioning
  canonical bytes and the exact accepted digest
  `sha256:2ac8487b64d4fb09d7576ef1ee09ac1f2a3cc5b20558f0d2137620b897c7157c`.
  A current receipt refresh limited to `verificationAuthorityInput` also
  produces those same bytes and digest after currentness validation succeeds.
- **NPW-005 — No fallback or silent witness rotation.** A missing, malformed,
  stale, provisional, non-verified, or identity-mismatched current receipt
  refuses. A missing, malformed, provisional, non-verified, or
  identity-mismatched witness also refuses. The witness is deliberately not
  compared with current verification-authority bytes; that historical
  difference is not staleness. Updating the witness changes the provisioning
  manifest and is not an allowed mechanical receipt refresh.
- **NPW-006 — Database authority is unchanged.** No migration, migration set,
  ledger row, provisioning digest, structural verifier, catalog identity,
  schema, role, grant, or durability behavior changes in this pull request.
- **NPW-007 — Mechanical conformance integration only.** The temporal checker
  may change only the byte length and SHA-256 source pin for the final
  `provisioning_specs.py`. Its states, branches, accepted migrations, source
  paths, marker law, and outputs remain byte-for-byte semantically unchanged.
- **NPW-008 — Closed implementation envelope.** Phase B changes only the exact
  allowlist in section 11, every focused and package gate passes, complete
  hosted conformance is green at the exact head, and no demonstrated in-scope
  Blocker remains.

## 8. Production-reachable negative cases

| Invariant | Supported entry point | Counterexample that must refuse or fail |
| --- | --- | --- |
| `NPW-001` | Tenant provisioning, migration, readiness, CLI preflight, or `TENANT_PROVISIONING_SPEC.digest` | The current receipt has an old workflow hash while the witness is exact. No database connection or manifest result is permitted. |
| `NPW-002` | `TENANT_PROVISIONING_SPEC.manifest()` | The witness is absent, non-regular, non-canonical, truncated, or linked to another release identity. The current receipt must not replace it. |
| `NPW-003` | Bound authority loader | A valid current receipt and valid witness are loaded against different release identities or one caller-supplied digest is substituted. Binding must fail. |
| `NPW-004` | `TENANT_PROVISIONING_SPEC.canonical_manifest_bytes()` and `.digest` | A valid current receipt differs only in current verification-authority bytes and causes any canonical provisioning byte or digest to change. The focused comparison fails. |
| `NPW-005` | Frozen tenant native-authority gate | The witness is silently refreshed from the current receipt, or the current receipt is used when the witness path is missing. Exact witness authentication and digest tests fail. |
| `NPW-006` | Full migration/provisioning tests and hosted conformance | Any migration, ledger, catalog, schema, role, or accepted digest changes to make the suite green. The exact path check rejects the change. |
| `NPW-007` | Package temporal checker | The integration edit changes a classifier branch, accepted state, migration pin, marker, path, or output instead of only the provisioning source length/hash. Exact diff review rejects it. |
| `NPW-008` | Pull-request merge gate | A seventh path, red hosted lane, unresolved Blocker, changed trust boundary, or lost approval evidence is present. Merge stops. |

These cases use real checked-file and public tenant-entry-point behavior. Tests
may supply explicit temporary paths to the production loader. Private-field
mutation is not an acceptance argument.

## 9. Proposed architecture and smallest coherent change

### 9.1 Immutable witness file

Phase B adds:

```text
deployment/postgresql/ofarm_ed25519/native_evidence_provisioning_witness.json
```

Its initial bytes are copied exactly from the reviewed-base
`native_evidence_receipt.json`. It is not generated during a workflow-only
authority refresh. Changing it later is a database provisioning-authority
decision and requires the migration and catalog analysis appropriate to the
resulting provisioning-digest change.

The witness is not added to native release `EVIDENCE_AUTHORITY_PATHS`. It is a
consumer-side durable witness, not an input that authorizes its own currentness
or causes recursive receipt refresh.

### 9.2 One bound authority object

`deployment/postgresql/provisioning_specs.py` adds one private frozen,
slot-backed value object that contains exactly:

- the validated current release identity;
- the validated current receipt; and
- the validated provisioning witness.

The existing lazy loader returns that object instead of a correlated tuple. It
loads the current receipt with current-authority verification and the witness
without current-repository comparison. Both receipt loads use the same
validated release identity.

The object owns the frozen/verified posture check and the exact
`checkedReleaseAuthority` manifest fragment. The fragment keeps its existing
shape and uses the witness's canonical digest and document. Because the witness
equals the receipt previously embedded at the reviewed base, existing manifest
bytes remain exact.

The current receipt is still consumed by the bound object's validation before
the fragment can be returned. It is not serialized into the provisioning
manifest and is never optional.

### 9.3 No compatibility branch

There is no old/new digest switch, accepted-digest list, environment selector,
database fallback, or migration adapter. The result has one manifest shape,
one current receipt path, and one witness path.

The initially identical documents are not two active sources for one
decision. Their roles are distinct and future current-authority refreshes are
expected to make their `verificationAuthorityInput` values differ.

### 9.4 Focused evidence

`kernel/tests/test_postgresql_provisioning_native_authority.py` owns focused
proof that:

- audit-only imports and use load neither tenant receipt nor witness;
- one tenant manifest observation performs one identity load, one current
  receipt load, and one witness load;
- the embedded fragment comes only from the witness;
- a stale current receipt refuses even with a valid witness;
- a missing or invalid witness refuses without current-receipt fallback;
- both receipts must link to the same identity and be frozen/verified;
- a current-only verification-authority refresh preserves exact manifest bytes
  and digest; and
- normal tenant entry points continue to refuse before external work.

The canonical review test inventory is regenerated only for actual new or
renamed test nodes.

### 9.5 Mechanical temporal pin

`conformance/temporal_contract_candidate_check.py` changes only the numeric
byte-length and SHA-256 values in the existing provisioning-spec source pin.
No classifier code, authority path, temporal state, migration identity, marker,
or output changes. This is mechanical integration required to authenticate the
reviewed production source within the existing temporal contract.

## 10. Elegance audit

### 10.1 Sources of truth

There are three non-overlapping document authorities:

1. one release identity for release artifacts and source input;
2. one current receipt for live verification-authority currentness; and
3. one immutable witness for the receipt bytes embedded in database
   provisioning identity.

Each owns one decision. No duplicated field independently grants permission.
The current receipt and witness must both validate against the same identity.

### 10.2 Authoritative transitions

There are four transitions:

1. current identity validation permits receipt validation;
2. current receipt validation permits currentness to be considered satisfied;
3. witness validation permits witness bytes to be embedded; and
4. complete bound-object validation permits manifest serialization.

No one transition skips another.

### 10.3 Compatibility and deletion

No compatibility shim, digest allowlist, migration branch, optional capability
bag, mutable cache, or runtime registry is introduced. No existing production
fallback remains to delete.

The old correlated identity/receipt tuple is replaced by one bound object. The
current receipt ceases to be an implicit database-digest source, which deletes
the demonstrated cross-boundary coupling.

Copying the accepted receipt once is intentional evidence preservation, not a
generic abstraction. A clean rewrite of receipt validation would cross into
native release authority and is less coherent than this consumer-side split.

## 11. Pull-request boundary

The implementation pull request may change only these six paths:

1. `docs/rfcs/OFARM_Native_Evidence_Provisioning_Witness_Execution_RFC_v0_1.md`
2. `deployment/postgresql/provisioning_specs.py`
3. `deployment/postgresql/ofarm_ed25519/native_evidence_provisioning_witness.json`
4. `kernel/tests/test_postgresql_provisioning_native_authority.py`
5. `conformance/temporal_contract_candidate_check.py`
6. `conformance/review_baseline_test_inventory.json`

The Phase A head changes only path 1. Paths 2 through 6 remain forbidden until
a complete live card names the already-created draft pull request and a later
exact same-task user message approves version 1.

Path 5 may change only the existing provisioning-spec source pin's byte length
and SHA-256. Path 6 is mechanical test-node inventory regeneration only. The
technical allowlist is therefore narrower than the maximum path envelope in
the live card even though both list the same paths.

Reviewers must not require:

- a PostgreSQL migration or accepted digest update;
- a change to native release validators, workflow, release assets, provider
  evidence, or current receipt semantics;
- a temporal classifier behavior or authority change;
- a security-audit or #192 change;
- implementation from #312 or #311; or
- deployment, release publication, or production evidence.

This pull request is a prerequisite for #312. It merges first. #312 must then
perform whatever exact-base amendment, reapproval, path audit, and hosted
verification its own stronger contract requires. This contract supplies no
authority for that later work.

## 12. Provisional design record

Not provisional.

The currentness/witness separation is the intended durable authority model:
verification implementation may evolve while an already admitted release
witness remains stable. A future change to release identity, build pins,
candidate evidence, platform artifacts, provider evidence, preservation
evidence, or witness bytes is a new database provisioning-authority decision,
not a reason to collapse the two roles again.

The task approval mechanism remains provisional pre-deployment authority under
the repository-wide workflow and must be replaced independently before
deployment. That procedural limitation does not make this technical split
temporary.

## 13. Traceability and verification

| Invariant | Owning change | Negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- |
| `NPW-001` | Bound loader retains current-receipt verification | Stale current receipt plus valid witness | Refusal before manifest/external work | Focused native-authority tests |
| `NPW-002` | New exact witness path and witness load | Missing, malformed, non-regular, or wrong-identity witness | Exact witness digest/document in fragment | Focused native-authority tests |
| `NPW-003` | Frozen bound authority object | Two receipts linked to different identities | One shared validated identity required | Focused loader tests |
| `NPW-004` | Manifest fragment uses witness after currentness gate | Current-only authority refresh changes manifest bytes | Structured before/after byte equality and accepted digest | Focused stability test plus existing provisioning digest test |
| `NPW-005` | Closed two-path loading with no fallback | Delete witness while current receipt remains valid | `ProvisioningSpecError`; no fallback call | Focused absence and substitution tests |
| `NPW-006` | Exact path exclusion of migrations/catalog files | Attempted digest or migration update | Old digest and all migration/catalog paths unchanged | Existing PostgreSQL suites plus exact path check |
| `NPW-007` | Two mechanically derived temporal pin literals | Any classifier semantic diff | Pin validates final source; classifier output unchanged | Exact pin diff plus temporal/package checks |
| `NPW-008` | Six-path allowlist and merge gate | Outside path or red hosted lane | Exact-head green checks and path subset | Git path comparison plus hosted conformance |

### 13.1 Required Phase A verification

Before the live card:

- `python3 conformance/ofarm_pkg_contract_check.py`;
- `git diff --check`;
- exact Phase A path check proving only this RFC changed;
- exact-head review of the complete RFC after its draft PR URL is bound; and
- confirmation that the reviewed base is still current main.

### 13.2 Required Phase B verification

Before merge:

- focused `test_postgresql_provisioning_native_authority.py` tests;
- existing provisioning digest and migration-set tests;
- structured byte comparison proving the tenant provisioning canonical
  manifest is unchanged from the reviewed base;
- exact assertion of the accepted tenant provisioning digest;
- negative current-receipt, witness-absence, witness-substitution, and
  identity-mismatch cases;
- audit-only independence tests;
- temporal candidate checker with unchanged public result;
- mechanical review-baseline inventory regeneration;
- `python3 conformance/ofarm_pkg_contract_check.py`;
- `git diff --check`;
- exact path comparison from the reviewed base through the exact head;
- exact diff proof that the temporal checker changed only its existing
  provisioning source pin literals; and
- complete hosted conformance at the exact head.

## 14. Open decisions and review disposition

There are no open architecture decisions in this proposed boundary.

- **Blockers:** the contract requires exact-head review after the draft PR URL
  is bound. Any demonstrated violation of `NPW-001` through `NPW-008` is a
  Blocker.
- **Follow-ups:** pull request #312 exact-base amendment and reapproval only as
  required by its own stronger contract; independently verifiable approval or
  signing before deployment.
- **Preferences:** none.

Once every invariant passes, the exact allowlist holds, complete hosted
conformance is green, no demonstrated in-scope Blocker remains, and approval is
still live, the approved workflow permits merging only the named pull request.

## 15. Pre-deployment decision workflow

This RFC grants no Phase B authority by authorship, commit, push, draft PR,
review, GitHub activity, or the generic `go` that authorized Phase A drafting.

The lawful sequence is:

1. publish this RFC alone in one new draft pull request from reviewed base
   `9c12c115bd29d9889234edd9e4c84377d9e332f8`;
2. bind that stable draft PR URL into this RFC;
3. rerun the package check, whitespace check, and exact RFC-only path check;
4. review the exact RFC-only head;
5. display one complete live decision card in this same Codex task naming that
   draft PR and the maximum six-path envelope; and
6. wait for a later task-user message whose entire visible text is exactly:

```text
I approve OFARM2 decision ISSUE174-NATIVE-EVIDENCE-PROVISIONING-WITNESS-EXECUTION-001 version 1.
```

Only that later exact same-task user message may authorize Phase B. Generic
approval, `go`, GitHub review, comment, reaction, merge instruction,
credentials, another task, AI text, tool output, or a summary of unavailable
task items never supplies approval.

After valid approval, the AI may implement only paths 2 through 6 in the same
named draft pull request, test, regenerate mechanical evidence, commit, push,
address in-boundary Blockers, rerun checks, mark ready, and merge only after
every gate passes. No additional confirmation is required while work remains
inside the approved envelope.

The future live card must state the decision identity and version, problem,
recommended decision, primary trust boundary, authority map, primary risk and
bound, permitted effects, non-effects, `NPW-001` through `NPW-008`, maximum
six-path envelope, named draft pull request, verification gates, reapproval
triggers, provisional posture, merge posture, and exact approval sentence.

A new decision version is required if the problem, recommended decision,
primary trust boundary, authority map, primary risk or bound, permitted effect,
non-effect, invariant, maximum path envelope, named pull request, irreversible
behavior, provisional posture, or merge posture changes. Closing the named PR
unmerged expires authority. Any later stop, cancel, withdraw, pause, or do-not-
merge message pauses work immediately.

Task messages remain approval authority. Any repository approval record is
AI-attested evidence only and never deployment authority.
