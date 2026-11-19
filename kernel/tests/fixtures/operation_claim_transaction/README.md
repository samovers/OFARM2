# Replay a test operation claim from its tenant transaction

The test submits one fictional typed intent for storage observation. Its proposed pending assertion ID is `assertion:fictional:performed_interval`. The database capture is scoped to this test attempt. It records the proposed insert and leaves the tenant ledger with zero new batches, records and edges. The command is `SUBMIT_OPERATION_CLAIM` and the verifier action is `ASSERT_OPERATION_CLAIM`.

## Inputs selected before the database attempt

`selection.json` names every input role, logical reference, revision, original SHA-256 and JSON value digest. `originals.zip` stores each original once under its byte hash. Two uses of the same record keep their separate roles. The collection code pins the selection itself. It reads the original bytes back from PostgreSQL and gives them to the checker through its base64 transport. The authorization decision and assertion-act fixture have separate source histories.

| Material | Source and limits |
| --- | --- |
| Typed intent, proposed result and authorization | The domain owner's saved `complete-verifier/checks/authorization-source-cases/basis-1-party` construction case supplies the typed roots and original authorization arguments. The original transport file `original-owner-inputs.json` had SHA-256 `b18e754eb3254f7cb60206614dad8a529316ad3ad942ef849b4570361d945991`. The case uses the fictional natural-person Party model. All nested source, schema, profile, context and evidence byte strings are preserved. The selected authorization checker manifest is `4a3a50451b6ce64c9c336b4d7bbe15aebddd799f85e73862d2cf4263ef20023c`. [Authorization owner](https://github.com/samovers/OFARM/tree/b1bf4f56fbdff604e9f5610cc29e8b3e9b31a224/04_implementation_and_conformance/conformance_runners/canonical_success_path) |
| Cited measurements | The two original JSON documents from the assertion-act owner's `fixtures/source-measurements` match the two immutable measurement bindings in the selected intent. They are included in the protected citation membership query. Suitability for the claim belongs to the domain owner. [Assertion-act fixtures](https://github.com/samovers/OFARM/tree/3a51d046ebf823e0faa4252e9c37ccfa182036f3/04_implementation_and_conformance/examples_and_fixtures/fixtures/assertion_act_evidence) |
| Transaction profile and time policy | The two opaque original inputs from the protected-state owner's `assert_operation_claim-initial` fixture are retained. The test supplies its own start observations, policy, proof and snapshot for the actual PostgreSQL attempt. Its controller selects a 60-second test window. [Storage checker](https://github.com/samovers/OFARM/tree/538d04075881b885ed370d14326acfab7aaf429e/04_implementation_and_conformance/conformance_runners/preverdict_protected_state_evidence) |
| Assertion act | The selected typed intent has raw SHA-256 `3a3e25a8c90ea12ab3acab995707b380286b9238f9f4c2f4e2bd3d1faf14bf83` and the accountable Party is `party:natural`. The independently saved `act-schema-closure-cases/active-schema/act-inputs.json` belongs to a different intent and Party. Its bytes are in `unmatched-act.zip` solely for the rejection check. The case records a missing act. The frozen assertion-act checker manifest selected by #47 is `5acded8b6468dc11688d54b259a6e51aae8adaaa528e54a6d1ec1f32463878a5`. |

## Run the capture

Use the repository's disposable PostgreSQL service with the verifier extension and server version `17.10 (Debian 17.10-1.pgdg13+1)`. This was exercised on tenant migration 12. Set `OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN` to that disposable service. The tests provision their own tenant database and ordinary roles. Start with a new temporary directory for pytest.

```sh
capture_root=$(mktemp -d)
python -m pytest -q -p no:cacheprovider --basetemp "$capture_root" \
  'kernel/tests/test_postgresql_operation_claim_evidence.py::test_capture_one_submission[ofarm_app]'
capture_dir=$(dirname "$(find "$capture_root" -name attempt-selection.json -print -quit)")
```

The output contains the original `intent.json`, `proposed.json`, `owner-inputs.json`, the test controller's exact `attempt-selection.json` and an `observation.json` recording its raw hash, the four artifact hashes, lease and transaction identifiers, missing sources and ledger deltas. The selector records the ticket and role identities before acquiring any storage proof. A separate connection reads the sealed bytes by that ticket only after successful finalization. A failed, aborted or unknown attempt cannot release a handoff.

Run the full test module to exercise both application and worker roles. The three writer tests use PostgreSQL's blocker PID, then observe each writer proceed after release. Every participating writer acquires the conflicting guard before it changes a source, an absent ID or set membership. The controller holds the selected guards before the tenant transaction begins. The bound backend acquires them before the controller releases them and rechecks the versions before finalization. These observations cover the fixture's selected keys under `READ COMMITTED`.

## Replay the exact captured bytes

Use the public verifier at `a343920df53a7a85aecd6ec910c644fe245f5dc6` and its pinned external runtime. Set `OFARM47` to that checkout and `OFARM47_EXTERNAL` to the external directory described by its owner. The verifier checks its interpreter, five owner packages and dependency manifests. [Verifier setup](https://github.com/samovers/OFARM/blob/a343920df53a7a85aecd6ec910c644fe245f5dc6/03_machine_contracts/drafts_non_default/assertion_record_submission/complete_typed/README.md)

```sh
python -B "$OFARM47/04_implementation_and_conformance/conformance_runners/complete_typed_assertion/ofarm_assertion_record_domain.py" verify \
  --action ASSERT_OPERATION_CLAIM --external "$OFARM47_EXTERNAL" \
  --intent "$capture_dir/intent.json" --result "$capture_dir/proposed.json" \
  --owner-inputs "$capture_dir/owner-inputs.json" > "$capture_dir/domain-report.json"
```

The selected authorization passes and the storage checker returns `CONDITIONAL_CONFORMANCE_PASS`. The domain verdict is `FAIL`. It reports 19 unresolved read occurrences across nine references. The assertion act and the domain owner's independently pinned evaluation selection are also unavailable for this input. #47's current incomplete verifier returns an empty validation payload. Its diagnostic source trace describes the checks that ran. #432 still needs the domain owner's passing payload and protected-effect validation trace.

Next, obtain a paired test assertion act and authorization issued for the same intent, plus the domain owner's selected source revisions. Repeat the capture through the same storage interface.
