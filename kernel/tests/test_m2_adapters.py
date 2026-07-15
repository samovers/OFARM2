"""M2 G2 — governed adapter / import mechanism (+ single-writer serialization).

Engineering tests, NOT part of the named conformance suite. They pin: a parsed
source imports as a dated ReferenceSnapshot via the generic runner; a
failed/partial parse writes a refusal and no snapshot; conflicting vs idempotent
re-import; the single-writer advisory lock serializes writers; and two concurrent
first STRUCTURE_ASSERTIONs for one identity resolve to exactly one governed
winner with no ungoverned crash (the H1 hardening folded into G2). A generic
FIXTURE scheme only — no REGSR/GERK/FFSNaprave literals (those are P1–P3). All
data fictional and format-true (privacy rule 1).
"""
from __future__ import annotations

import json
import sys
import threading
import uuid

import pytest

from kernel import store as store_module
from kernel.adapters import ImportRunner, ParseResult
from kernel.context import now_iso
from kernel.contracts import ContractViolation, sha256_of
from kernel.store import (
    Store,
    _SINGLE_WRITER_LOCK_KEY,
)
from profile_si_ffs.tests.m2_si_output_lock_tests import *  # noqa: F401,F403


def uid():
    return uuid.uuid4().hex[:10]


def _meta(snapshot_id, *, effective="2026-05-01T00:00:00Z", label="fixture.parse.v1"):
    """A generic FIXTURE reference scheme — deliberately not REGSR/GERK."""
    return {
        "referenceSnapshotId": snapshot_id,
        "referenceClass": "CODE_LIST",
        "domain": "fixture reference source (test)",
        "issuingAuthorityRef": "party:fixture.authority",
        "jurisdictionRef": "jurisdiction:FIXTURE",
        "canonicalVersionLabel": label,
        "effectiveFrom": effective,
        "sourceArtifactRefs": ["surface:fixture.test.source"],
        "notes": "fictional fixture snapshot (test)",
    }


def _import_log(store, snapshot_id):
    with Store._raw_connection(store).cursor() as cur:
        cur.execute(
            "SELECT outcome, reason_code, related_refs FROM kernel_gate_log "
            "WHERE gate = 'GOVERNED_IMPORT' AND related_refs @> %s ORDER BY entry_id",
            (json.dumps([snapshot_id]),))
        return cur.fetchall()


def _reference_data_rows(store, snapshot_id, data_family):
    return [
        row for row in store.reference_data(data_family)
        if row["snapshot_ref"] == snapshot_id
    ]


def _parse(label, *, count=1, artifact_ref=None):
    records = {"fixtureSource": label}
    return ParseResult(
        ok=True,
        sourceDigest=sha256_of(records),
        artifactRef=artifact_ref,
        recordCount=count,
        records=records,
    )


def test_g2_import_success_writes_dated_snapshot(store):
    sid = f"referencesnapshot:fixture.demo.{uid()}"
    result = ImportRunner(store).run_import(
        _parse("fixture-success", count=42), _meta(sid),
        data_family="fixture.test.data")
    assert result["imported"] is True and result["snapshotRef"] == sid
    row = store.get_record(sid)
    assert row is not None and row["record_kind"] == "ofarm.referencesnapshot.v0.1"
    p = row["payload"]
    assert p["effectiveFrom"] == "2026-05-01T00:00:00Z"
    assert f"digest:{sha256_of({'fixtureSource': 'fixture-success'})}" in \
        p["sourceArtifactRefs"]
    assert not any(ref.startswith("artifact:") for ref in p["sourceArtifactRefs"])
    log = _import_log(store, sid)
    assert log and log[-1]["outcome"] == "IMPORTED"


def test_g2_behavioral_records_cannot_split_import_snapshot_identity(store):
    sid_a = f"referencesnapshot:fixture.behavior-a.{uid()}"
    sid_b = f"referencesnapshot:fixture.behavior-b.{uid()}"
    snapshot_meta = _meta(sid_a)
    hostile_callbacks = []

    class BehavioralRecords(dict):
        def items(self):
            hostile_callbacks.append("items")
            snapshot_meta["referenceSnapshotId"] = sid_b
            return dict.items(self)

    retained_records = {"fixtureSource": "behavioral-records"}
    parse_result = ParseResult(
        ok=True,
        sourceDigest=sha256_of(retained_records),
        recordCount=1,
        records=BehavioralRecords(retained_records),
    )

    with pytest.raises(ContractViolation, match="exact built-in JSON"):
        ImportRunner(store).run_import(
            parse_result, snapshot_meta, data_family="fixture.test.behavior")

    assert hostile_callbacks == [], "input capture must not dispatch dict.items"
    assert snapshot_meta["referenceSnapshotId"] == sid_a
    for snapshot_id in (sid_a, sid_b):
        assert store.get_record(snapshot_id) is None
        assert _reference_data_rows(
            store, snapshot_id, "fixture.test.behavior") == []
        assert _import_log(store, snapshot_id) == []


def test_g2_nested_behavioral_snapshot_metadata_is_rejected_before_execution(store):
    sid = f"referencesnapshot:fixture.behavior-meta.{uid()}"
    hostile_callbacks = []

    class BehavioralRefs(list):
        def __iter__(self):
            hostile_callbacks.append("iter")
            raise AssertionError("behavioral metadata iteration must stay unreachable")

    snapshot_meta = _meta(sid)
    snapshot_meta["sourceArtifactRefs"] = BehavioralRefs(
        ["surface:fixture.test.source"])

    with pytest.raises(ContractViolation, match="exact built-in JSON"):
        ImportRunner(store).run_import(
            _parse("behavioral-metadata"), snapshot_meta,
            data_family="fixture.test.behavior-meta")

    assert hostile_callbacks == [], "input capture must not dispatch list iteration"
    assert store.get_record(sid) is None
    assert _reference_data_rows(
        store, sid, "fixture.test.behavior-meta") == []
    assert _import_log(store, sid) == []


def test_g2_post_capture_input_mutation_cannot_diverge_import_chain(store):
    sid_a = f"referencesnapshot:fixture.capture-a.{uid()}"
    sid_b = f"referencesnapshot:fixture.capture-b.{uid()}"
    data_family = "fixture.test.post-capture"
    retained_records = {"fixtureSource": {"state": "before"}}
    retained_digest = sha256_of(retained_records)

    def import_after_capture_mutation():
        records = {"fixtureSource": {"state": "before"}}
        snapshot_meta = _meta(sid_a)
        mutation_points = []
        release_mutator = threading.Event()
        mutation_done = threading.Event()
        mutation_errors = []

        def mutate_caller_input():
            try:
                if not release_mutator.wait(timeout=30):
                    raise AssertionError("post-capture trace did not release mutator")
                records["fixtureSource"]["state"] = "after"
                snapshot_meta["referenceSnapshotId"] = sid_b
            except Exception as exc:  # deterministic worker failure is test data
                mutation_errors.append(repr(exc))
            finally:
                mutation_done.set()

        worker = threading.Thread(target=mutate_caller_input)
        worker.start()

        def mutate_after_capture(frame, event, _arg):
            if (event == "line"
                    and frame.f_code is ImportRunner.run_import.__code__
                    and "captured" in frame.f_locals
                    and not mutation_points):
                release_mutator.set()
                assert mutation_done.wait(timeout=30), \
                    "concurrent input mutation did not finish"
                mutation_points.append(frame.f_lineno)
                # No tracing remains active when validation or the governed
                # transaction begins; this hook only selects the exact seam.
                sys.settrace(None)
                return None
            return mutate_after_capture

        previous_trace = sys.gettrace()
        sys.settrace(mutate_after_capture)
        try:
            result = ImportRunner(store).run_import(
                ParseResult(
                    ok=True,
                    sourceDigest=retained_digest,
                    recordCount=1,
                    records=records,
                ),
                snapshot_meta,
                data_family=data_family,
            )
        finally:
            release_mutator.set()
            worker.join(timeout=30)
            sys.settrace(previous_trace)
        assert not worker.is_alive()
        assert mutation_errors == []
        assert mutation_points, "trace did not reach the post-capture seam"
        assert records == {"fixtureSource": {"state": "after"}}
        assert snapshot_meta["referenceSnapshotId"] == sid_b
        return result

    first = import_after_capture_mutation()
    assert first == {
        "imported": True,
        "snapshotRef": sid_a,
        "disposition": "IMPORTED",
        "problem": None,
    }

    snapshot_row = store.get_record(sid_a)
    assert snapshot_row is not None
    assert snapshot_row["payload"]["referenceSnapshotId"] == sid_a
    data_rows = _reference_data_rows(store, sid_a, data_family)
    assert len(data_rows) == 1
    data_row = data_rows[0]
    assert data_row["payload"] == retained_records
    assert data_row["source_digest"] == retained_digest
    assert data_row["payload_sha256"] == retained_digest
    assert sha256_of(data_row["payload"]) == retained_digest
    import_log = _import_log(store, sid_a)
    assert import_log[-1]["outcome"] == "IMPORTED"
    assert sid_a in import_log[-1]["related_refs"]
    assert f"digest:{retained_digest}" in import_log[-1]["related_refs"]
    assert store.get_record(sid_b) is None
    assert _reference_data_rows(store, sid_b, data_family) == []
    assert _import_log(store, sid_b) == []

    replay = import_after_capture_mutation()
    assert replay == {
        "imported": True,
        "snapshotRef": sid_a,
        "disposition": "ALREADY_IMPORTED",
        "problem": None,
    }
    replay_rows = _reference_data_rows(store, sid_a, data_family)
    assert len(replay_rows) == 1
    assert replay_rows[0]["payload"] == retained_records
    assert replay_rows[0]["source_digest"] == retained_digest
    assert replay_rows[0]["payload_sha256"] == retained_digest
    replay_log = _import_log(store, sid_a)
    assert replay_log[-1]["outcome"] == "REPLAY_REUSED"
    assert replay_log[-1]["related_refs"] == [sid_a]
    assert store.get_record(sid_b) is None
    assert _reference_data_rows(store, sid_b, data_family) == []
    assert _import_log(store, sid_b) == []


def test_g2_store_reference_data_snapshots_before_jsonb_and_digest(store, monkeypatch):
    data_family = "fixture.test.direct-capture"
    mismatch_sid = f"referencesnapshot:fixture.direct-mismatch.{uid()}"
    payload = {"fixtureSource": {"state": "before"}}
    retained_digest = sha256_of(payload)

    with pytest.raises(ContractViolation, match="source digest"):
        with store.serialized_tx() as cur:
            store.insert_reference_data(
                cur,
                mismatch_sid,
                data_family,
                payload,
                source_digest=sha256_of({"fixtureSource": {"state": "other"}}),
            )
    assert _reference_data_rows(store, mismatch_sid, data_family) == []

    sid = f"referencesnapshot:fixture.direct-capture.{uid()}"
    live_hash_calls = []
    release_mutator = threading.Event()
    mutation_done = threading.Event()
    mutation_errors = []

    def forbidden_live_hash(*args, **kwargs):
        live_hash_calls.append((args, kwargs))
        raise AssertionError("live store.sha256_of dispatch must stay unreachable")

    def mutate_caller_payload():
        try:
            if not release_mutator.wait(timeout=30):
                raise AssertionError("Jsonb boundary did not release mutator")
            payload["fixtureSource"]["state"] = "after"
        except Exception as exc:  # deterministic worker failure is test data
            mutation_errors.append(repr(exc))
        finally:
            mutation_done.set()

    original_jsonb = store_module.Jsonb

    def jsonb_after_concurrent_mutation(value):
        assert value is not payload, "Jsonb must receive the private Store snapshot"
        release_mutator.set()
        assert mutation_done.wait(timeout=30), \
            "concurrent caller-payload mutation did not finish"
        return original_jsonb(value)

    worker = threading.Thread(target=mutate_caller_payload)
    worker.start()

    try:
        with store.serialized_tx() as cur:
            # Restore live bindings before transaction exit. The Store must use
            # its retained snapshot+digest helper and pass only that private
            # value across the delayed Jsonb boundary.
            with monkeypatch.context() as patch:
                patch.setattr(store_module, "sha256_of", forbidden_live_hash)
                patch.setattr(store_module, "Jsonb", jsonb_after_concurrent_mutation)
                store.insert_reference_data(
                    cur,
                    sid,
                    data_family,
                    payload,
                    source_digest=retained_digest,
                )
    finally:
        release_mutator.set()
        worker.join(timeout=30)

    assert not worker.is_alive()
    assert mutation_errors == []
    assert live_hash_calls == []
    assert payload == {"fixtureSource": {"state": "after"}}
    rows = _reference_data_rows(store, sid, data_family)
    assert len(rows) == 1
    row = rows[0]
    assert row["payload"] == {"fixtureSource": {"state": "before"}}
    assert row["source_digest"] == retained_digest
    assert row["payload_sha256"] == retained_digest
    assert sha256_of(row["payload"]) == retained_digest


def test_g2_parse_failure_writes_no_snapshot(store):
    sid = f"referencesnapshot:fixture.fail.{uid()}"
    result = ImportRunner(store).run_import(
        ParseResult(ok=False, error="parser crashed mid-file"), _meta(sid))
    assert result["imported"] is False
    assert result["problem"]["reasonCode"] == "SOURCE_FIDELITY_LOSS"
    assert store.get_record(sid) is None, "a failed parse must write no snapshot"
    log = _import_log(store, sid)
    assert log and log[-1]["outcome"] == "REFUSED" \
        and log[-1]["reason_code"] == "SOURCE_FIDELITY_LOSS"


def test_g2_conflicting_reimport_refused(store):
    sid = f"referencesnapshot:fixture.conf.{uid()}"
    runner = ImportRunner(store)
    first = runner.run_import(
        _parse("conflict-a"), _meta(sid), data_family="fixture.test.data")
    assert first["imported"] is True
    original = store.get_record(sid)["payload_sha256"]
    conflict = runner.run_import(
        _parse("conflict-b"),
        _meta(sid, effective="2026-09-09T00:00:00Z"),
        data_family="fixture.test.data")
    assert conflict["imported"] is False
    assert conflict["problem"]["reasonCode"] == "DUPLICATE_IMPORT_AMBIGUOUS"
    assert store.get_record(sid)["payload_sha256"] == original, "append-only: unchanged"


def test_g2_idempotent_reimport_reused(store):
    sid = f"referencesnapshot:fixture.idem.{uid()}"
    runner = ImportRunner(store)
    a = runner.run_import(
        _parse("idempotent"), _meta(sid), data_family="fixture.test.data")
    b = runner.run_import(
        _parse("idempotent"), _meta(sid), data_family="fixture.test.data")
    assert a["imported"] is True and b["imported"] is True
    assert b["disposition"] == "ALREADY_IMPORTED"
    assert store.get_record(sid) is not None


def test_g2_unretained_artifact_ref_refuses_without_poisoning_restart(store):
    sid = f"referencesnapshot:fixture.unretained.{uid()}"
    result = ImportRunner(store).run_import(
        _parse("unretained", artifact_ref="artifact:fixture.raw.json"),
        _meta(sid), data_family="fixture.test.data")
    assert result["imported"] is False
    assert result["disposition"] == "SOURCE_NOT_RETAINED"
    assert store.get_record(sid) is None


def test_g2_single_writer_lock_is_mutually_exclusive(store):
    # two independent connections: while A holds the serialized-write lock, B
    # cannot acquire it; once A releases (at commit), B can.
    a, b = Store(), Store()
    try:
        with Store._raw_connection(b).cursor() as cb:
            with a.serialized_tx():
                cb.execute("SELECT pg_try_advisory_lock(%s)", (_SINGLE_WRITER_LOCK_KEY,))
                assert cb.fetchone()["pg_try_advisory_lock"] is False, \
                    "B must not acquire the single-writer lock while A holds it"
            cb.execute("SELECT pg_try_advisory_lock(%s)", (_SINGLE_WRITER_LOCK_KEY,))
            assert cb.fetchone()["pg_try_advisory_lock"] is True
            cb.execute("SELECT pg_advisory_unlock(%s)", (_SINGLE_WRITER_LOCK_KEY,))
    finally:
        a.close()
        b.close()


def test_g2_concurrent_first_structure_assertions_one_governed_winner(store):
    # H1: two concurrent first STRUCTURE_ASSERTIONs for the SAME new identity.
    # The single-writer lock serializes them — exactly one promotes; the other
    # sees the now-in-force identity and refuses governably (D18
    # CORRECTION_REQUIRED), never an ungoverned UniqueViolation, never two in-force.
    from kernel.gates import GatePipeline
    from kernel import demo
    field_ref = f"field:m2g2race.{uid()}"
    outcomes, errors = [None, None], [None, None]
    done = [threading.Event(), threading.Event()]
    barrier = threading.Barrier(2)
    worker_inputs = []
    threads = []

    def worker(i, pipe, sub):
        try:
            barrier.wait(timeout=300)
            outcomes[i] = pipe.commit(sub)
        except Exception as exc:   # any crash is a test failure
            errors[i] = repr(exc)
        finally:
            done[i].set()

    try:
        # Runtime selection is intentionally expensive and itself serialized.
        # Complete it before the raced section so this test measures concurrent
        # commits, not whether two cold bootstraps fit an arbitrary wall clock.
        for i in range(2):
            s = Store()
            worker_inputs.append(s)
            from kernel import context
            context.bootstrap(s)
            pipe = GatePipeline(s)
            sub = demo.structure_submission(
                {"schemaVersion": "ofarm.fieldidentitypayload.v0.1",
                 "fieldidentitypayloadId": f"fp:m2g2race.{i}.{uid()}",
                 "identityRecordRef": field_ref, "recordedAt": now_iso(),
                 "displayName": "race field (fictional)",
                 "parentFarmIdentityRef": demo.FARM,
                 "declaredArea": {"value": 1.0, "unitCode": "har"}},
                idem_key=f"m2g2race:{i}:{uid()}")
            threads.append(threading.Thread(
                target=worker, args=(i, pipe, sub)))
        for thread in threads:
            thread.start()
        for i, completed in enumerate(done):
            assert completed.wait(timeout=300), \
                f"concurrent structure writer {i} did not complete"
        for thread in threads:
            thread.join(timeout=10)
        assert not any(thread.is_alive() for thread in threads), \
            "all concurrent structure writers must terminate"
    finally:
        for thread in threads:
            thread.join(timeout=10)
        for worker_store in worker_inputs:
            worker_store.close()

    assert errors == [None, None], f"no writer may crash ungoverned: {errors}"
    decisions = sorted(o["decisionOutcome"] for o in outcomes)
    assert decisions == ["PROMOTE_ACCEPTED", "RETAIN_DRAFT"], decisions
    loser = [o for o in outcomes if o["decisionOutcome"] == "RETAIN_DRAFT"][0]
    assert loser["problems"][0]["reasonCode"] == "CORRECTION_REQUIRED"
    ids = [r for r in store.find_by_kind("ofarm.identityrecord.v0.1")
           if r["record_id"] == field_ref]
    assert len(ids) == 1, "exactly one durable IdentityRecord for the contested id"
    n = 0
    for r in store.in_force_consequences(demo.FARM):
        e = store.edges_from(r["payload"]["sourceEventRef"], "STRUCTURE_PAYLOAD")
        if e and (pp := store.get_payload(e[0]["dst_record_id"])) \
                and pp["identityRecordRef"] == field_ref:
            n += 1
    assert n == 1, "exactly one in-force structural consequence for the contested id"
