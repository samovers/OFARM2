# SI Test Fixtures

Status: profile-local test/demo fixture support only. This package does not
define SI profile law, runtime behavior, contracts, generated manifests,
conformance evidence, or platform capability.

`demo_refs.py` is the D2a compatibility mirror for current `kernel.demo`
reference values. It intentionally aliases the existing `kernel.demo` values so
this step creates no payload, id, bootstrap, evidence, authority, review,
currentness, or materialization behavior change.

Later D2 steps may move fixture construction behind profile-local helpers while
keeping `kernel.demo` as the compatibility facade until root callers are safely
migrated.
