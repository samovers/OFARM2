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
import threading
import uuid

from kernel.adapters import ImportRunner, ParseResult
from kernel.context import now_iso
from kernel.runtime_activation import complete_store_startup
from kernel.store import Store, _SINGLE_WRITER_LOCK_KEY
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
    with store.conn.cursor() as cur:
        cur.execute(
            "SELECT outcome, reason_code FROM kernel_gate_log "
            "WHERE gate = 'GOVERNED_IMPORT' AND related_refs @> %s ORDER BY entry_id",
            (json.dumps([snapshot_id]),))
        return cur.fetchall()


def test_g2_import_success_writes_dated_snapshot(store):
    sid = f"referencesnapshot:fixture.demo.{uid()}"
    result = ImportRunner(store).run_import(
        ParseResult(ok=True, sourceDigest="sha256-fixturecafe",
                    artifactRef="artifact:fixture.demo.json", recordCount=42),
        _meta(sid))
    assert result["imported"] is True and result["snapshotRef"] == sid
    row = store.get_record(sid)
    assert row is not None and row["record_kind"] == "ofarm.referencesnapshot.v0.1"
    p = row["payload"]
    assert p["effectiveFrom"] == "2026-05-01T00:00:00Z"
    assert "digest:sha256-fixturecafe" in p["sourceArtifactRefs"]
    assert "artifact:fixture.demo.json" in p["sourceArtifactRefs"]
    log = _import_log(store, sid)
    assert log and log[-1]["outcome"] == "IMPORTED"


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
    first = runner.run_import(ParseResult(ok=True, sourceDigest="sha256-aaa"), _meta(sid))
    assert first["imported"] is True
    original = store.get_record(sid)["payload_sha256"]
    conflict = runner.run_import(
        ParseResult(ok=True, sourceDigest="sha256-bbb"),
        _meta(sid, effective="2026-09-09T00:00:00Z"))
    assert conflict["imported"] is False
    assert conflict["problem"]["reasonCode"] == "DUPLICATE_IMPORT_AMBIGUOUS"
    assert store.get_record(sid)["payload_sha256"] == original, "append-only: unchanged"


def test_g2_idempotent_reimport_reused(store):
    sid = f"referencesnapshot:fixture.idem.{uid()}"
    runner = ImportRunner(store)
    a = runner.run_import(ParseResult(ok=True, sourceDigest="sha256-ccc"), _meta(sid))
    b = runner.run_import(ParseResult(ok=True, sourceDigest="sha256-ccc"), _meta(sid))
    assert a["imported"] is True and b["imported"] is True
    assert b["disposition"] == "ALREADY_IMPORTED"
    assert store.get_record(sid) is not None


def test_g2_single_writer_lock_is_mutually_exclusive(store):
    # two independent connections: while A holds the serialized-write lock, B
    # cannot acquire it; once A releases (at commit), B can.
    a = Store(
        dsn=store.dsn,
        tenant_ref=store.tenant_ref,
        runtime_bundle=store.runtime_bundle,
        active_descriptor=store.active_descriptor,
    )
    b = Store(
        dsn=store.dsn,
        tenant_ref=store.tenant_ref,
        runtime_bundle=store.runtime_bundle,
        active_descriptor=store.active_descriptor,
    )
    try:
        complete_store_startup(a)
        complete_store_startup(b)
        with b.conn.cursor() as cb:
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
    outcomes, errors = [], []
    barrier = threading.Barrier(2)

    def worker(i):
        s = Store(
            dsn=store.dsn,
            tenant_ref=store.tenant_ref,
            runtime_bundle=store.runtime_bundle,
            active_descriptor=store.active_descriptor,
        )
        try:
            complete_store_startup(s)
            pipe = GatePipeline(s)
            sub = demo.structure_submission(
                {"schemaVersion": "ofarm.fieldidentitypayload.v0.1",
                 "fieldidentitypayloadId": f"fp:m2g2race.{i}.{uid()}",
                 "identityRecordRef": field_ref, "recordedAt": now_iso(),
                 "displayName": "race field (fictional)",
                 "parentFarmIdentityRef": demo.FARM,
                 "declaredArea": {"value": 1.0, "unitCode": "har"}},
                idem_key=f"m2g2race:{i}:{uid()}")
            barrier.wait(timeout=10)
            outcomes.append(pipe.commit(sub))
        except Exception as exc:   # any crash is a test failure
            errors.append(repr(exc))
        finally:
            s.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    assert not errors, f"no writer may crash ungoverned: {errors}"
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
