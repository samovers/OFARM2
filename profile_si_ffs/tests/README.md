# SI Profile Test Harness Scaffold

Status: scaffold only. This directory does not move existing tests, change
runtime behavior, alter the root pytest command, write evidence, update
contracts, regenerate manifests, or claim Slovenia production readiness.

The active root test suite remains `python -m pytest kernel/tests/ -q`. This
directory only creates a profile-local landing zone for later SI engineering
tests after the D6/D7 boundaries are ready.

## Current Boundary

- `profile_test_harness.json` declares the profile-local engineering-test
  scaffold.
- `kernel/tests/profile_harness_bridge.py` is the root-owned bridge helper that
  can validate and enumerate this descriptor.
- No tests are moved here in D6a.
- No profile test is presented as platform MVP conformance evidence.
- No profile-local evidence writer exists in D6a.

Later PRs may add test modules to the descriptor only if the root command still
discovers the intended coverage without changing evidence-writer semantics.
