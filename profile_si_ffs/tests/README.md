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
  can validate and enumerate this descriptor. Its regression tests also require
  every declared profile test module to have a root collection bridge.
- D6b moves SI adapter/import engineering assertions here while root collection
  stubs keep `python -m pytest kernel/tests/ -q` working.
- D6c moves SI policy metadata engineering assertions here under the same
  root-bridge pattern.
- D6d keeps active-runtime SI binding integration checks root-owned, but moves
  SI binding wrapper assertions into `m2_si_binding_wrapper_tests.py` and shared
  fictional snapshot builders into `m2_si_binding_fixtures.py`.
- D6d also keeps generic adapter/import lock mechanics root-owned, but moves
  active SI output lock assertions into `m2_si_output_lock_tests.py`.
- D2a adds profile-local demo fixture ref mirrors in
  `profile_si_ffs/test_fixtures/demo_refs.py` while keeping `kernel.demo` as the
  compatibility source.
- D2b moves SI substrate record construction behind
  `profile_si_ffs/test_fixtures/demo_records.py` while keeping
  `kernel.demo.substrate_records()` as the compatibility facade.
- D2c moves SI demo payload builders behind
  `profile_si_ffs/test_fixtures/demo_payloads.py` while keeping `kernel.demo`
  public functions as the compatibility facade.
- No profile test is presented as platform MVP conformance evidence.
- No profile-local evidence writer exists.

Later PRs may add more test modules to the descriptor only if the root command
still discovers the intended coverage without changing evidence-writer
semantics.
