# SI Profile Test Harness

Status: profile engineering-test harness. This directory does not change
runtime behavior, alter the root pytest command, write evidence, update
contracts, regenerate manifests, or claim Slovenia production readiness.

The active root test suite remains `python -m pytest kernel/tests/ -q`. Root
collection stubs keep these profile-local engineering assertions discoverable
until a later profile pytest command exists.

## Current Boundary

- `profile_test_harness.json` declares the profile-local engineering-test
  scaffold.
- `kernel/tests/profile_harness_bridge.py` is the root-owned bridge helper that
  can validate and enumerate this descriptor.
- D6b moves SI adapter/import engineering assertions here while root collection
  stubs keep `python -m pytest kernel/tests/ -q` working.
- D6c moves SI policy metadata engineering assertions here under the same
  root-bridge pattern.
- D6d-prep keeps SI binding assertions root-owned, but places shared fictional
  SI binding snapshot builders in `m2_si_binding_fixtures.py` as profile-local
  fixture support.
- No profile test is presented as platform MVP conformance evidence.
- No profile-local evidence writer exists.

Later PRs may add more test modules to the descriptor only if the root command
still discovers the intended coverage without changing evidence-writer
semantics.
