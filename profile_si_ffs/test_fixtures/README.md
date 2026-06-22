# SI Test Fixtures

Status: profile-local test/demo fixture support only. This package does not
define SI profile law, runtime behavior, contracts, generated manifests,
conformance evidence, or platform capability.

`demo_refs.py` is the D2a compatibility mirror for current `kernel.demo`
reference values. It intentionally aliases the existing `kernel.demo` values so
this step creates no payload, id, bootstrap, evidence, authority, review,
currentness, or materialization behavior change.

`demo_records.py` is the D2b substrate-record builder. `kernel.demo` remains the
public compatibility facade and delegates to this helper without changing record
ids, payload fields, bootstrap behavior, or evidence grounding.

`demo_payloads.py` is the D2c typed identity and operation payload builder.
`kernel.demo` remains the public compatibility facade and delegates to this
helper without changing payload ids, field names, defaults, or decision
outcomes.

`demo.py` is the D2d profile-local fixture facade used by moved SI profile
engineering tests. It keeps the same `demo.*` call shape for tests while
leaving `kernel.demo` as the public compatibility facade for root callers and
examples.

Later D2 steps may move fixture construction behind profile-local helpers while
keeping `kernel.demo` as the compatibility facade until root callers are safely
migrated.
