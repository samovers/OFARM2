# OFARM2 RuntimeBundle Contract-Schema Version Extraction — Phase A Contract v0.1

**Status:** proposed Phase A contract; documentation-only, unapproved, and
without implementation effect

**Contract identity:**
`ofarm.runtime-bundle-contract-schema-version-extraction.issue176.v0.1`

**Date:** 2026-07-31

**Primary implementation ticket:** #176

**Base commit:** `9daeb98c0691df97325245e9aa5fc5da6d933124`

**Primary trust boundary:** fail-closed extraction of one contract identity
from exact schema bytes admitted by the active RuntimeBundle model

**Intended future Phase B PR boundary:** `kernel/runtime_bundle.py`,
`kernel/tests/test_runtime_bundle.py`, and mechanically required test inventory
updates only

## 1. Problem and goal

The active RuntimeBundle model derives a `CONTRACT_SCHEMA` component's logical
identity only from:

```text
properties.schemaVersion.const
```

The reviewed temporal governed-command schema declares its whole allowed
document through a top-level `const` object and therefore carries its version
at:

```text
const.schemaVersion
```

The exact schema is consequently refused by the supported
`RuntimeComponent.from_selected_bytes(...)` construction path even when its
bytes, role, logical reference, canonicalization, and placement are otherwise
correct.

This contract fixes the complete closed extraction rule needed before the
temporal RuntimeBundle model-admission boundary may begin:

1. accept exactly one of the two reviewed declaration forms;
2. derive one non-empty string version only from the exact parsed schema bytes;
3. refuse missing, malformed, duplicate, or conflicting declarations; and
4. require the component logical reference to equal
   `contract:<extracted-version>`.

This contract does not implement that rule.

## 2. Learning value

The boundary proves that two legitimate JSON Schema declaration styles can
share one small, fail-closed RuntimeBundle identity rule without allowing file
names, caller data, catalog metadata, or lifecycle status to become contract
identity authority.

It removes the demonstrated blocker that currently makes the third temporal
governance identity impossible to retain with its exact schema.

## 3. Non-goals

This contract does not:

- change `RuntimeComponentRole` or admit
  `TEMPORAL_GOVERNANCE_ARTIFACT`;
- admit, activate, publish, select, or execute any temporal identity;
- add a schema, candidate artifact, manifest entry, digest, or ERRATA entry;
- change the `ContractRegistry`, active contract directories, catalog,
  publisher, package loader, or RuntimeBundle contents;
- perform complete JSON Schema meta-schema validation or instance validation;
- infer a version from `$id`, `title`, file name, path, caller logical
  reference, catalog metadata, or schema instance data;
- support `allOf`, `$ref`, `enum`, `default`, annotations, or any third
  schema-version declaration form;
- change database storage, migrations, repositories, tenant selection,
  profiles, `RuntimeBundle` selection, `RuntimeBundleBuilder` custody, routes,
  commands, materialization, reads, historical or WINDOW behavior, outputs, or
  #192;
- change frozen active contracts or candidate schema bytes; or
- open the production semantic surface.

## 4. Trust model

### Protected assets

- the truthful relationship between exact retained schema bytes, extracted
  schema version, and `contract:<version>` logical reference;
- RuntimeBundle component and bundle digests derived from those exact bytes;
- separation between `CONTRACT_SCHEMA` and `DRAFT_CONTRACT_SCHEMA` lanes; and
- the production-versus-legacy firewall and closed production semantic
  surface.

### Trusted components

- `strict_json_document(...)` for strict object parsing and duplicate-key
  refusal;
- one `_contract_schema_version(...)` extraction authority;
- `RuntimeComponent` construction for role, canonicalization, placement,
  digest, and logical-reference validation; and
- `RuntimeBundle.create(...)` for cross-lane duplicate refusal.

### Untrusted inputs

- all selected schema bytes;
- a caller- or catalog-supplied logical reference;
- component specifications and relative paths before their normal validation;
- malformed JSON Schema objects; and
- either supported declaration location before extraction succeeds.

### Excluded compromise capabilities

Arbitrary in-process mutation, private-field mutation, compromised Python or
third-party dependencies, concurrent filesystem mutation during one builder
operation, compromised repository or publisher custody, and operator
compromise are outside this boundary. A separately governed publisher still
decides which already validated components enter a bundle.

Local source substitution before construction is in scope only as untrusted
selected bytes: it must pass strict parsing, extraction, logical-reference
equality, and digest derivation. This boundary does not decide whether a
particular contract identity is lifecycle-current or allowed in a particular
bundle.

## 5. Authority map

- The exact parsed schema bytes are the sole source of the schema version.
- `_contract_schema_version(...)` is the sole extraction rule for supported
  RuntimeBundle contract-schema construction paths.
- `properties.schemaVersion.const` owns the version only when the property
  declaration form is the single present form.
- `const.schemaVersion` owns the version only when the whole-document
  declaration form is the single present form.
- `RuntimeComponent` owns equality between the extracted version and the
  supplied `contract:<version>` logical reference.
- The selected exact bytes own the component digest and byte length.
- The component role owns whether the schema is in the active or draft lane;
  version extraction does not choose or change that lane.
- `RuntimeBundle.create(...)` retains authority over duplicate schema versions
  across lanes.
- `ContractRegistry`, component catalog, publisher, and lifecycle governance
  retain their existing separate authorities. None may override extraction.

The direct property lookup currently duplicated in
`RuntimeBundleBuilder._validate_contract_registry_closure(...)` is not a second
authority. Future Phase B must route that supported builder path through
`_contract_schema_version(...)`.

## 6. State machine and ordering

The future extraction path has one linear state machine:

```text
SELECTED_EXACT_BYTES
  -> STRICT_JSON_OBJECT
  -> EXACTLY_ONE_SUPPORTED_DECLARATION
  -> NON_EMPTY_STRING_VERSION
  -> MATCHING_CONTRACT_LOGICAL_REF
  -> IMMUTABLE_COMPONENT
```

Any failed transition produces `RuntimeBundleError` and no component.

A property declaration is present when `properties` is an object containing a
`schemaVersion` key. Its value must be an object containing one non-empty
string at its `const` key for extraction. A whole-document declaration is
present when the schema has a top-level `const` key. Its value must be an
object containing one non-empty string at its `schemaVersion` key for
extraction.
If either present form is malformed, extraction refuses even when the other
form is valid. Other fields inside either object remain JSON Schema content and
are not interpreted by this extraction rule.

Validation order is fixed:

1. require selected bytes, a contract-schema role, exact-byte
   canonicalization, global placement, and a bounded logical reference;
2. derive and verify the digest from the unchanged selected bytes;
3. parse one strict JSON object from those bytes;
4. inspect both reviewed declaration locations;
5. require exactly one present declaration;
6. require its value to be a non-empty built-in string;
7. require the supplied logical reference to equal
   `contract:<extracted-version>`;
8. construct the immutable component.

`RuntimeBundleBuilder` must use the same extraction authority when discovering
and constructing contract-schema components. Validation completes before the
component can enter `RuntimeBundle.create(...)`; refusal cannot create a
partial component or bundle.

There is no database transaction or external side effect in this boundary.
The selected `bytes` value is the time-of-check/time-of-use snapshot for direct
construction. Concurrent filesystem mutation during builder construction is
explicitly outside the trust model and is not redesigned here.

## 7. Invariants and acceptance criteria

- **RBCSVE-001 — Closed declaration vocabulary.** The only supported locations
  are `properties.schemaVersion.const` and `const.schemaVersion`.
- **RBCSVE-002 — Exactly one declaration.** Exactly one supported location is
  present. Two declarations are refused even when their strings are equal.
- **RBCSVE-003 — One bounded kind.** The extracted version is a non-empty
  built-in string accepted by the existing bounded logical-reference rule.
- **RBCSVE-004 — Bytes are authority.** No path, file name, `$id`, title,
  caller value, catalog field, or instance document may supply or override the
  version.
- **RBCSVE-005 — Logical reference equality.** Admission succeeds only when
  `logical_ref == "contract:" + extracted_version`.
- **RBCSVE-006 — One extraction rule.** Direct component construction,
  component validation, and builder contract-schema discovery use the same
  extraction function.
- **RBCSVE-007 — Lane neutrality.** The rule is identical for
  `CONTRACT_SCHEMA` and `DRAFT_CONTRACT_SCHEMA`; extraction neither chooses a
  lane nor permits one version in both lanes.
- **RBCSVE-008 — Atomic refusal.** Malformed, missing, duplicate, conflicting,
  or mismatched input raises `RuntimeBundleError` before a component or bundle
  exists.
- **RBCSVE-009 — No lifecycle effect.** Successful extraction alone does not
  admit an identity to a closed role, publish or select a bundle, activate a
  contract, or open any production behavior.

## 8. Production-reachable negative cases

Each case starts at `RuntimeComponent.from_selected_bytes(...)` or
`RuntimeBundleBuilder`:

| Invariant | Counterexample | Required result |
| --- | --- | --- |
| RBCSVE-001 | version appears only in `$id`, `enum`, `default`, `allOf`, or a third location | refuse |
| RBCSVE-002 | both reviewed locations exist with equal strings | refuse duplicate declaration |
| RBCSVE-002 | both reviewed locations exist with different strings | refuse conflicting declaration |
| RBCSVE-003 | the sole value is absent, empty, `null`, boolean, number, array, or object | refuse |
| RBCSVE-004 | file name or supplied logical reference names a version absent from the bytes | refuse |
| RBCSVE-005 | bytes declare `v0.1` while the logical reference names `v0.2` | refuse |
| RBCSVE-006 | builder discovery sees a top-level-`const` schema that direct construction accepts | both paths must accept through the same rule |
| RBCSVE-007 | the same version is selected once in each schema lane | existing cross-lane duplicate refusal remains |
| RBCSVE-008 | duplicate JSON keys, non-object JSON, or malformed JSON reaches either entry point | refuse before construction |
| RBCSVE-009 | a valid top-level-`const` schema is supplied without any separately admitted component role or bundle-selection authority | extraction creates no activation or runtime effect |

## 9. Proposed architecture and smallest change

Future Phase B may make one coherent model change:

1. make `_contract_schema_version(...)` inspect the two explicit locations,
   require exactly one present declaration, and return one non-empty built-in
   string;
2. replace the direct property lookup in
   `RuntimeBundleBuilder._validate_contract_registry_closure(...)` with that
   helper; and
3. add focused tests around direct construction and builder construction.

No new type, registry, configuration, compatibility mode, optional behavior,
or temporal special case is needed. The helper remains private because it owns
one RuntimeBundle model rule, not a public extension surface.

## 10. Elegance audit

- Sources of schema-version truth after Phase B: one, the exact parsed schema
  bytes.
- Authoritative extraction transitions: one,
  `_contract_schema_version(...)`.
- Supported declaration forms: two closed syntax forms with no fallback.
- New abstractions: none.
- New mutable state: none.
- Compatibility surfaces: none.
- Deletable duplication: the builder's direct
  `properties.schemaVersion.const` lookup.

A clean rewrite of the RuntimeBundle model is not justified. Replacing one
duplicate lookup and extending one small helper is clearer and safer.

## 11. Pull request boundary

This Phase A PR changes only this RFC.

After explicit approval, one Phase B PR may change only:

- `kernel/runtime_bundle.py`;
- `kernel/tests/test_runtime_bundle.py`; and
- mechanically required test inventory or baseline metadata.

The primary trust boundary remains contract-schema identity extraction. Tests
and mechanical inventory updates may travel with it; temporal role admission,
catalog publication, persistence, selection, command integration, output, and
#192 work may not.

The temporal RuntimeBundle model-admission contract
`ofarm.temporal-governance-runtime-bundle-model-admission.issue176.v0.1`
depends on the future Phase B implementation of this contract. Its Phase B
must not begin until that implementation is merged.

Reviewers must not require this PR to add temporal identities, schemas,
RuntimeBundle roles, active components, migrations, runtime integration, or
output behavior.

## 12. Provisional design record

Not provisional.

The vocabulary is deliberately closed. Supporting another declaration form
requires a new reviewed contract rather than an extension hook.

## 13. Traceability and verification

| Invariant | Owning model function/type | Supported construction path | Required negative test | Acceptance evidence | Smallest verification |
| --- | --- | --- | --- | --- | --- |
| RBCSVE-001 | `_contract_schema_version` | direct and builder | unlisted declaration locations refuse | focused unit cases | `pytest -q kernel/tests/test_runtime_bundle.py -k contract_schema_version` |
| RBCSVE-002 | `_contract_schema_version` | direct and builder | equal duplicate and conflicting declarations refuse | focused unit cases | same focused pytest |
| RBCSVE-003 | `_contract_schema_version` | direct and builder | missing, empty, and non-string values refuse | focused unit cases | same focused pytest |
| RBCSVE-004 | `_contract_schema_version` | direct and builder | path, `$id`, and caller values cannot substitute | focused unit cases | same focused pytest |
| RBCSVE-005 | `_validate_runtime_component_semantics` and `RuntimeComponent` | `RuntimeComponent.from_selected_bytes` | wrong logical reference refuses | focused unit case | same focused pytest |
| RBCSVE-006 | `_contract_schema_version` and `RuntimeBundleBuilder._validate_contract_registry_closure` | direct and builder | no entry-point disagreement | paired acceptance/refusal cases | same focused pytest |
| RBCSVE-007 | `RuntimeComponentRole` and `RuntimeBundle.create` | direct bundle and builder | same version across lanes refuses | existing cross-lane tests plus regression | same focused pytest |
| RBCSVE-008 | `strict_json_document`, `RuntimeComponent` | direct and builder | malformed, duplicate-key, and non-object inputs refuse atomically | focused unit cases | same focused pytest |
| RBCSVE-009 | unchanged role/catalog/selection authorities | all supported construction paths | extraction alone has no temporal activation path | diff and closed-role assertions | `python3 conformance/ofarm_pkg_contract_check.py` |

Phase A verification is:

- inspect the exact current model and both reviewed schema forms;
- prove the document changes no active authority;
- run `git diff --check`; and
- run `python3 conformance/ofarm_pkg_contract_check.py`.

Future Phase B verification is:

- the focused test command in the table;
- the complete `kernel/tests/test_runtime_bundle.py` module;
- `python3 conformance/ofarm_pkg_contract_check.py`; and
- `git diff --check`.

## 14. Open decisions and review disposition

### Closed decisions

- Both reviewed declaration forms are supported.
- Exactly one form may be present; equal duplicates are still refused.
- The same rule governs both existing contract-schema lanes.
- `$id` and all external metadata remain non-authoritative.
- The builder's duplicate lookup is removed rather than retained as a fallback.

### Open decisions

None.

### Review disposition

- Blockers: none known in this proposed prerequisite contract.
- Follow-ups: the separate temporal RuntimeBundle model-admission contract and
  its future implementation.
- Preferences: none.

### Merge stop rule

This Phase A contract must not merge as approved or begin Phase B until the
designated architect explicitly approves this exact contract after review.

After approval, the future Phase B PR must not merge until every invariant in
the traceability table has acceptance evidence and no demonstrated Blocker
remains. New ideas, Preferences, and out-of-boundary hardening become
Follow-ups and do not expand that PR.

## Stop conditions

Stop and propose a separate boundary before:

1. changing `ContractRegistry` or active schema directories;
2. adding a RuntimeBundle role or admitted identity;
3. changing catalog, publisher, persistence, repository, or selection custody;
4. adding temporal runtime selection or governed-command integration;
5. changing schema or candidate artifact bytes;
6. adding routes, materialization, reads, historical or WINDOW execution,
   qualification, receipts, or outputs;
7. importing or modifying the legacy semantic surface; or
8. changing #192 behavior.

The production semantic surface remains closed.
