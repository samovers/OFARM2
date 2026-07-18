"""M2 P3 — SI FFSNaprave sprayer-inspection import + Equipment-identity evidence.

Engineering tests, NOT part of the named conformance suite. They pin the SI
FFSNaprave adapter riding the generic G2 import + the store-backed reference-data
cache, and its G1 integration: a yearly delimited file imports as a dated
FFSNaprave ReferenceSnapshot AND its inspections persist store-backed as a
candidate; startup RuntimeBundle selection, not import timing, determines which
cache rows runtime loaders may activate. Pure register laws use explicit
``register_artifact`` setup; evidence writers run only against a semantically
complete bundle-selected test store. A farm sprayer matches by the composite
sticker key (StevilkaZnaka + VeljavnostZnaka); a match CAPTURES a
REGISTRY_EXTRACT EvidenceRecord whose id populates
EquipmentIdentityPayload.inspectionEvidenceRefs on an Equipment identity committed
through G1; no match → the equipment is recorded WITHOUT inspection evidence
(advisory, never a silent pass-as-compliant); failed/conflicting/partial imports
are governed refusals. Far-future (2099) candidates stay inactive under the base
test bundle; positive writer tests derive and persist a bundle that explicitly
selects them. All sticker, machine, and inspection values are fictional and
format-true (D14).
"""
from __future__ import annotations

import json
import threading
import uuid
from contextlib import contextmanager

import psycopg
import psycopg.conninfo
from psycopg import sql

from kernel import demo as kernel_demo
from kernel.contracts import sha256_of
from kernel.gates import GatePipeline
from kernel.profiles.si_ffs import ffsnaprave_adapter as ffsn
from kernel.profiles.si_ffs.ffsnaprave_adapter import FFSNAPRAVE_DATA_FAMILY, FFSNapraveRegister
from kernel.runtime_bundle import (
    Canonicalization,
    ContentPlacement,
    RuntimeBundle,
    RuntimeComponent,
    RuntimeComponentRole,
    canonical_json_bytes,
)
from kernel.store import Store
from profile_si_ffs.test_fixtures import demo


def uid():
    return uuid.uuid4().hex[:8]


def sticker_num():
    """A fictional, format-true 6-digit inspection-sticker number."""
    return str(uuid.uuid4().int)[:6]


def _inspection(*, sticker, validity, conformance="DA", **extra):
    base = {
        "NapravaID": f"N{uid()[:6]}", "StatusNaprave": "aktivna",
        "SkladnostNaprave": "DA", "StevilkaZnaka": sticker, "VeljavnostZnaka": validity,
        "VrstaNaprave": "nahrbtna skropilnica (fictional)", "Izdelovalec": "Test Maker d.o.o.",
        "TipNaprave": "FIKTIV-100", "SerijskaStevilka": f"SN{uid()[:6]}",
        "PregledID": f"P{uid()[:6]}", "LetoPregleda": "2025",
        "DatumPregleda": "2025-06-15", "SkladnostObPregledu": conformance,
    }
    base.update(extra)
    return base


def _fixture_artifact(*, file_date, inspections=None):
    insp = inspections if inspections is not None else [
        _inspection(sticker=sticker_num(), validity="2027-12-31")]
    return {
        "snapshotKind": "SI_UVHVVR_FFS_NAPRAVE_PARSE",
        "fileDate": file_date,
        "canonicalVersionLabel": f"ffsnaprave-fixture-{file_date}",
        "keyFieldsPresent": True,
        "attributesAvailable": list(ffsn.RETAINED_FIELDS),
        "inspectionCount": len(insp),
        "inspections": insp,
        "rowProblems": [],
        "inputs": [{"file": "fixture-ffsnaprave.txt", "digest": f"sha256:{uid()}cafe"}],
    }


def _equipment_payload(equip_ref, payload_id, *, inspection_refs=None):
    p = {
        "schemaVersion": "ofarm.equipmentidentitypayload.v0.1",
        "equipmentidentitypayloadId": payload_id,
        "identityRecordRef": equip_ref,
        "recordedAt": demo.now_iso(),
        "displayName": "Fiktivna skropilnica (fictional sprayer)",
        "equipmentClass": "SPRAYER",
        "ownerPartyRef": demo.FARMER,
    }
    if inspection_refs is not None:
        p["inspectionEvidenceRefs"] = inspection_refs
    return p


def _data_row(store, sid):
    return next((r for r in store.reference_data(FFSNAPRAVE_DATA_FAMILY)
                 if r["snapshot_ref"] == sid), None)


def _governed_import_refusals(store):
    with store.conn.cursor() as cur:
        cur.execute(
            "SELECT outcome, reason_code, related_refs FROM kernel_gate_log "
            "WHERE gate = 'GOVERNED_IMPORT' AND outcome = 'REFUSED' ORDER BY entry_id")
        return cur.fetchall()


def _replace_json_component(component, document):
    return RuntimeComponent.from_selected_bytes(
        role=component.role,
        logical_ref=component.logical_ref,
        canonicalization=component.canonicalization,
        placement=component.placement,
        selected_bytes=canonical_json_bytes(document),
    )


def _bundle_selecting_ffsnaprave(source_store, artifacts):
    """Derive a complete, semantically valid bundle selecting test vintages."""
    selections = []
    for artifact in artifacts:
        file_date = artifact["fileDate"]
        sid = f"{ffsn.FFSNAPRAVE_SNAPSHOT_PREFIX}.{file_date}"
        artifact_ref = f"artifact:test.ffsnaprave.{file_date}.json"
        source_bytes = canonical_json_bytes(artifact)
        imported = ffsn.import_ffsnaprave_snapshot(
            source_store, artifact, source_artifact_ref=artifact_ref)
        assert imported["imported"] is True and imported["snapshotRef"] == sid
        snapshot_document = source_store.get_record(sid)["payload"]
        selections.append(
            (sid, artifact_ref, artifact, source_bytes, snapshot_document))

    selected_refs = [selection[0] for selection in selections]
    components = []
    for component in source_store.runtime_bundle.components:
        if component.role is RuntimeComponentRole.PROFILE_INSTANCE:
            document = json.loads(component.canonical_bytes)
            if document.get("schemaVersion") == "ofarm.activeartifactset.v0.1":
                document["activeArtifactRefs"] = [
                    *document["activeArtifactRefs"], *selected_refs]
                component = _replace_json_component(component, document)
            elif document.get("schemaVersion") == "ofarm.contextsnapshot.v0.1":
                document["referenceSnapshotRefs"] = [
                    *document["referenceSnapshotRefs"], *selected_refs]
                component = _replace_json_component(component, document)
        components.append(component)

    for sid, artifact_ref, _artifact, source_bytes, snapshot_document in selections:
        components.extend((
            RuntimeComponent.from_selected_bytes(
                role=RuntimeComponentRole.REFERENCE_SOURCE,
                logical_ref=artifact_ref,
                canonicalization=Canonicalization.EXACT_BYTES,
                placement=ContentPlacement.GLOBAL,
                selected_bytes=source_bytes,
            ),
            RuntimeComponent.from_selected_bytes(
                role=RuntimeComponentRole.REFERENCE_SNAPSHOT,
                logical_ref=sid,
                canonicalization=Canonicalization.CANONICAL_JSON,
                placement=ContentPlacement.GLOBAL,
                selected_bytes=canonical_json_bytes(snapshot_document),
            ),
        ))
    return RuntimeBundle.create(components), selections


@contextmanager
def _selected_ffsnaprave_store(source_store, *artifacts):
    bundle, selections = _bundle_selecting_ffsnaprave(source_store, artifacts)
    params = psycopg.conninfo.conninfo_to_dict(source_store.dsn)
    dbname = f"ofarm_ffs_selected_{uuid.uuid4().hex[:10]}"
    admin_params = dict(params)
    admin_params["dbname"] = "postgres"
    admin_dsn = psycopg.conninfo.make_conninfo(**admin_params)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    params["dbname"] = dbname
    selected = Store(
        dsn=psycopg.conninfo.make_conninfo(**params),
        tenant_ref=source_store.tenant_ref,
        runtime_bundle=bundle,
        active_descriptor=source_store.active_descriptor,
    )
    try:
        selected.migrate()
        # Seed the canonical activation spine from the bundle itself. Loading the
        # checked-in files would reintroduce the base ActiveArtifactSet/Context
        # bytes and make this fixture only superficially selected.
        with selected.tx() as cur:
            for component in bundle.components:
                if component.role in {
                    RuntimeComponentRole.PROFILE_INSTANCE,
                    RuntimeComponentRole.REFERENCE_SNAPSHOT,
                }:
                    selected.insert_record(cur, json.loads(component.canonical_bytes))
        kernel_demo.bootstrap(selected)
        snapshot_refs = []
        for sid, artifact_ref, artifact, _source_bytes, _snapshot in selections:
            result = ffsn.import_ffsnaprave_snapshot(
                selected, artifact, source_artifact_ref=artifact_ref)
            assert result["imported"] is True and result["snapshotRef"] == sid
            assert sid in selected.selected_reference_snapshot_refs
            snapshot_refs.append(sid)
        yield selected, snapshot_refs
    finally:
        selected.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))


def _writer_state(store):
    tables = (
        "kernel_record", "kernel_edge", "kernel_gate_log", "kernel_idempotency",
        "derived_materialization", "derived_dependency_index",
        "reference_snapshot_data", "runtime_trace", "export_artifact",
    )
    return tuple(
        store.conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
        for table in tables
    )


# ---------------------------------------------------------------------------
# (1) import writes a dated FFSNaprave ReferenceSnapshot + a store-backed data row
# ---------------------------------------------------------------------------

def test_p3_import_writes_snapshot_and_store_backed_data(store):
    sticker = sticker_num()
    art = _fixture_artifact(file_date="2099-09-30",
                            inspections=[_inspection(sticker=sticker, validity="2027-12-31")])
    result = ffsn.import_ffsnaprave_snapshot(store, art, source_artifact_ref="archive:fixture.ffsnaprave.zip")
    assert result["imported"] is True
    sid = result["snapshotRef"]
    assert sid == f"{ffsn.FFSNAPRAVE_SNAPSHOT_PREFIX}.2099-09-30"
    p = store.get_record(sid)["payload"]
    assert p["effectiveFrom"] == "2099-09-30T00:00:00Z"
    assert p["issuingAuthorityRef"] == "party:si.uvhvvr"
    assert ffsn.FFSNAPRAVE_SOURCE_SURFACE in p["sourceArtifactRefs"]
    row = _data_row(store, sid)
    assert row is not None and row["payload"]["inspections"][0]["StevilkaZnaka"] == sticker
    # A governed import persists an auditable candidate. It cannot change runtime
    # authority under the already-active bundle.
    assert sid not in store.selected_reference_snapshot_refs
    runtime_register = FFSNapraveRegister()
    runtime_register.load_from_store(store)
    assert runtime_register.match(sid, sticker, validity="2027-12-31") is None


# ---------------------------------------------------------------------------
# (2) a farm sprayer matches by the composite sticker key (StevilkaZnaka + Veljavnost)
# ---------------------------------------------------------------------------

def test_p3_register_matches_sticker_composite():
    sticker = sticker_num()
    art = _fixture_artifact(file_date="2099-09-29",
                            inspections=[_inspection(sticker=sticker, validity="2027-12-31")])
    sid = f"{ffsn.FFSNAPRAVE_SNAPSHOT_PREFIX}.2099-09-29"
    reg = FFSNapraveRegister()
    reg.register_artifact(sid, art)
    # exact composite match
    m = reg.match(sid, sticker, validity="2027-12-31")
    assert m is not None and m["SkladnostObPregledu"] == "DA"
    # sticker alone matches when the validity window is unambiguous
    assert reg.match(sid, sticker) is not None
    # an unknown sticker / wrong validity -> None (never fabricated)
    assert reg.match(sid, "0000000", validity="2027-12-31") is None
    assert reg.match(sid, sticker, validity="1999-01-01") is None


# ---------------------------------------------------------------------------
# (3) a sticker match CAPTURES inspection evidence and the Equipment identity
#     commits through G1 carrying it (with a non-tautological control)
# ---------------------------------------------------------------------------

def test_p3_sticker_match_attaches_inspection_evidence_to_equipment(store):
    sticker, validity = sticker_num(), "2027-12-31"
    art = _fixture_artifact(file_date="2099-09-01",
                            inspections=[_inspection(sticker=sticker, validity=validity)])
    with _selected_ffsnaprave_store(store, art) as (selected, snapshot_refs):
        sid = snapshot_refs[0]
        r = ffsn.attach_inspection_evidence(
            selected, sid, sticker, validity=validity,
            captured_by=demo.FARMER, farm_ref=demo.FARM)
        assert r["attached"] is True and r["disposition"] == "CAPTURED"
        eid = r["evidenceRef"]
        ev = selected.get_record(eid)
        assert ev is not None and ev["record_kind"] == "ofarm.evidencerecord.v0.1"
        assert ev["payload"]["evidenceClass"] == "REGISTRY_EXTRACT"
        assert ev["payload"]["rawAssetRef"] == sid
        # capturedAt is the register vintage the extract was taken from, not 'now'
        assert ev["payload"]["capturedAt"] == "2099-09-01T00:00:00Z"
        # evidence is scoped to the farm (HB1) and the digest verifies rawAssetRef (HB2)
        assert ev["payload"]["anchorScopes"] == [
            {"scopeType": "FARM", "scopeRef": demo.FARM}]
        assert ev["payload"]["rawAssetDigest"] == sha256_of(selected.get_record(
            ev["payload"]["rawAssetRef"])["payload"]), \
            "digest must recompute from rawAssetRef"
        # the Equipment identity commits through G1 carrying the inspection evidence
        pipeline = GatePipeline(selected)
        s = uid()
        payload = _equipment_payload(
            f"equip:m2p3.{s}", f"equippayload:m2p3.{s}", inspection_refs=[eid])
        result = pipeline.commit(
            demo.structure_submission(payload, idem_key=f"m2p3-ev:{s}"))
        assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
        assert result["inForceResultCategory"] == "ACCEPTED_STRUCTURAL_STATE"
        # CONTROL (non-tautology): a fabricated inspection ref does NOT resolve to
        # an EvidenceRecord, so G1 must NOT accept it.
        s2 = uid()
        bogus = _equipment_payload(
            f"equip:m2p3b.{s2}", f"equippayload:m2p3b.{s2}",
            inspection_refs=["evidence:si.ffs-naprave.does-not-exist"])
        bad = pipeline.commit(
            demo.structure_submission(bogus, idem_key=f"m2p3-bad:{s2}"))
        assert bad["decisionOutcome"] != "PROMOTE_ACCEPTED"


# ---------------------------------------------------------------------------
# (4) no match -> the equipment is recorded WITHOUT inspection evidence (advisory,
#     never a silent pass-as-compliant)
# ---------------------------------------------------------------------------

def test_p3_no_match_equipment_recorded_without_inspection_evidence(store):
    art = _fixture_artifact(file_date="2099-09-02",
                            inspections=[_inspection(sticker=sticker_num(), validity="2027-12-31")])
    with _selected_ffsnaprave_store(store, art) as (selected, snapshot_refs):
        sid = snapshot_refs[0]
        nm = ffsn.attach_inspection_evidence(
            selected, sid, "0000000", validity="2027-12-31",
            captured_by=demo.FARMER, farm_ref=demo.FARM)
        assert nm["attached"] is False
        assert nm["disposition"] == "NO_MATCH" and nm["evidenceRef"] is None
        s = uid()
        payload = _equipment_payload(
            f"equip:m2p3n.{s}", f"equippayload:m2p3n.{s}")  # no inspection refs
        result = GatePipeline(selected).commit(
            demo.structure_submission(payload, idem_key=f"m2p3-noev:{s}"))
        assert result["decisionOutcome"] == "PROMOTE_ACCEPTED", \
            "equipment without an inspection match is still recorded — advisory, not blocked"


def test_p3_unauthorized_capture_refuses_no_evidence(store):
    # PR #14 hostile B1: evidence capture is AUTHORITY-GATED. A party without
    # OBSERVE_ATTACH_EVIDENCE on the farm (or a nonexistent party) is refused, and
    # NO EvidenceRecord is created.
    sticker, validity = sticker_num(), "2027-12-31"
    art = _fixture_artifact(file_date="2099-06-01",
                            inspections=[_inspection(sticker=sticker, validity=validity)])
    with _selected_ffsnaprave_store(store, art) as (selected, snapshot_refs):
        sid = snapshot_refs[0]
        vintage = sid.split(f"{ffsn.FFSNAPRAVE_SNAPSHOT_PREFIX}.", 1)[-1]
        eid = f"evidence:si.ffs-naprave.{vintage}.{sticker}.{validity}"
        # INSPECTOR is recorded but holds no grant -> AUTHORITY_DENIED.
        r = ffsn.attach_inspection_evidence(
            selected, sid, sticker, validity=validity,
            captured_by=demo.INSPECTOR, farm_ref=demo.FARM)
        assert r["attached"] is False and r["disposition"] == "UNAUTHORIZED"
        assert r["evidenceRef"] is None
        assert r["problem"]["reasonCode"] == "AUTHORITY_DENIED"
        assert selected.get_record(eid) is None, \
            "unauthorized capture must create no EvidenceRecord"
        # A nonexistent acting party is likewise refused, still with no record.
        r2 = ffsn.attach_inspection_evidence(
            selected, sid, sticker, validity=validity,
            captured_by="party:does.not.exist", farm_ref=demo.FARM)
        assert r2["attached"] is False and r2["disposition"] == "UNAUTHORIZED"
        assert selected.get_record(eid) is None
        # The authorised holder can then capture it (the gate is not a blanket deny).
        ok = ffsn.attach_inspection_evidence(
            selected, sid, sticker, validity=validity,
            captured_by=demo.FARMER, farm_ref=demo.FARM)
        assert ok["attached"] is True
        assert selected.get_record(ok["evidenceRef"]) is not None


def test_p3_unselected_snapshot_cannot_bypass_bundle_selection(store):
    sticker, validity = sticker_num(), "2027-12-31"
    art = _fixture_artifact(file_date="2099-05-01",
                            inspections=[_inspection(sticker=sticker, validity=validity)])
    sid = ffsn.import_ffsnaprave_snapshot(store, art)["snapshotRef"]
    assert sid not in store.selected_reference_snapshot_refs
    before = _writer_state(store)

    refused = ffsn.attach_inspection_evidence(
        store, sid, sticker, validity=validity,
        captured_by=demo.FARMER, farm_ref=demo.FARM)

    assert refused["attached"] is False and refused["evidenceRef"] is None
    assert refused["disposition"] == "SNAPSHOT_NOT_SELECTED"
    assert refused["problem"]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"
    assert _writer_state(store) == before, \
        "selection refusal must precede lookup, authority evaluation, and all writes"

    # Selection alone is insufficient: a selected reference from another family
    # is also refused before lookup or authority evaluation can influence the writer.
    wrong_family = next(
        ref for ref in store.selected_reference_snapshot_refs
        if ref.startswith("referencesnapshot:si.mkgp.gerk-layer"))
    before_wrong_family = _writer_state(store)
    wrong = ffsn.attach_inspection_evidence(
        store, wrong_family, sticker, validity=validity,
        captured_by=demo.FARMER, farm_ref=demo.FARM)
    assert wrong["attached"] is False and wrong["evidenceRef"] is None
    assert wrong["disposition"] == "SNAPSHOT_NOT_SELECTED"
    assert wrong["problem"]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"
    assert _writer_state(store) == before_wrong_family


def test_p3_attach_inspection_evidence_is_idempotent(store):
    sticker, validity = sticker_num(), "2027-12-31"
    art = _fixture_artifact(file_date="2099-09-03",
                            inspections=[_inspection(sticker=sticker, validity=validity)])
    with _selected_ffsnaprave_store(store, art) as (selected, snapshot_refs):
        sid = snapshot_refs[0]
        a = ffsn.attach_inspection_evidence(
            selected, sid, sticker, validity=validity,
            captured_by=demo.FARMER, farm_ref=demo.FARM)
        b = ffsn.attach_inspection_evidence(
            selected, sid, sticker, validity=validity,
            captured_by=demo.FARMER, farm_ref=demo.FARM)
        assert a["evidenceRef"] == b["evidenceRef"]
        assert a["evidenceRef"] is not None
        assert a["disposition"] == "CAPTURED"
        assert b["disposition"] == "ALREADY_CAPTURED"
        assert selected.get_record(a["evidenceRef"]) is not None


def test_p3_evidence_id_is_snapshot_scoped_no_cross_vintage_reuse(store):
    # PR #14 B1: a LATER register vintage with the SAME sticker/validity but
    # different inspection detail must NOT reuse the older vintage's evidence —
    # the EvidenceRecord is snapshot-specific (capturedAt / rawAssetRef / provenance)
    sticker, validity = sticker_num(), "2027-12-31"
    a = _fixture_artifact(file_date="2099-07-10", inspections=[
        _inspection(sticker=sticker, validity=validity, conformance="DA", DatumPregleda="2025-01-01")])
    b = _fixture_artifact(file_date="2099-07-20", inspections=[
        _inspection(sticker=sticker, validity=validity, conformance="NE", DatumPregleda="2026-01-01")])
    with _selected_ffsnaprave_store(store, a, b) as (selected, snapshot_refs):
        sid_a, sid_b = snapshot_refs
        eid_a = ffsn.attach_inspection_evidence(
            selected, sid_a, sticker, validity=validity,
            captured_by=demo.FARMER, farm_ref=demo.FARM)["evidenceRef"]
        eid_b = ffsn.attach_inspection_evidence(
            selected, sid_b, sticker, validity=validity,
            captured_by=demo.FARMER, farm_ref=demo.FARM)["evidenceRef"]
        assert eid_a != eid_b, \
            "evidence id must be snapshot-scoped — no cross-vintage reuse"
        # Each evidence record points at its own snapshot vintage, not a stale one.
        assert selected.get_record(eid_a)["payload"]["rawAssetRef"] == sid_a
        assert selected.get_record(eid_b)["payload"]["rawAssetRef"] == sid_b
        assert selected.get_record(eid_a)["payload"]["capturedAt"] == \
            "2099-07-10T00:00:00Z"
        assert selected.get_record(eid_b)["payload"]["capturedAt"] == \
            "2099-07-20T00:00:00Z"


def test_p3_attach_inspection_evidence_is_race_safe(store):
    # PR #14 B2: the existence check is INSIDE the single-writer advisory-locked
    # transaction, so two concurrent callers (separate connections) serialize and
    # the loser returns the winner's committed record idempotently — never a
    # duplicate-key error. With the broken pre-lock check this races and crashes.
    sticker, validity = sticker_num(), "2027-12-31"
    art = _fixture_artifact(file_date="2099-07-01",
                            inspections=[_inspection(sticker=sticker, validity=validity)])
    with _selected_ffsnaprave_store(store, art) as (selected, snapshot_refs):
        sid = snapshot_refs[0]
        barrier = threading.Barrier(2)
        results, errors = [], []

        def worker():
            worker_store = Store(
                dsn=selected.dsn,
                tenant_ref=selected.tenant_ref,
                runtime_bundle=selected.runtime_bundle,
                active_descriptor=selected.active_descriptor,
            )
            try:
                barrier.wait(timeout=10)        # both contend on attach together
                results.append(ffsn.attach_inspection_evidence(
                    worker_store, sid, sticker, validity=validity,
                    captured_by=demo.FARMER, farm_ref=demo.FARM)["evidenceRef"])
            except Exception as exc:            # noqa: BLE001
                errors.append(repr(exc))
            finally:
                worker_store.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        assert not errors, \
            f"idempotent attach must not raise under concurrency: {errors}"
        assert len(results) == 2
        assert results[0] == results[1] and results[0] is not None
        assert selected.get_record(results[0]) is not None


# ---------------------------------------------------------------------------
# (5) governed refusals: no vintage / no sticker columns / partial / no inspections
# ---------------------------------------------------------------------------

def test_p3_import_with_no_file_date_refuses_governed(store):
    before = _governed_import_refusals(store)
    art = _fixture_artifact(file_date="2099-08-01")
    art["fileDate"] = None
    result = ffsn.import_ffsnaprave_snapshot(store, art)
    assert result["imported"] is False and result["snapshotRef"] is None
    assert result["disposition"] == "NO_FILE_DATE"
    p = result["problem"]
    assert p["schemaVersion"] == "ofarm.runtimeproblem.v0.1"
    assert p["reasonCode"] == "SOURCE_FIDELITY_LOSS"
    after = _governed_import_refusals(store)
    assert len(after) == len(before) + 1 and after[-1]["related_refs"] is None


def test_p3_import_with_no_sticker_columns_refuses_governed(store):
    art = _fixture_artifact(file_date="2099-08-02")
    art["keyFieldsPresent"] = False
    result = ffsn.import_ffsnaprave_snapshot(store, art)
    assert result["imported"] is False and result["disposition"] == "NO_STICKER_FIELD"
    assert result["problem"]["reasonCode"] == "SOURCE_FIDELITY_LOSS"
    assert store.get_record(f"{ffsn.FFSNAPRAVE_SNAPSHOT_PREFIX}.2099-08-02") is None


def test_p3_partial_parse_refuses_at_import(store):
    art = _fixture_artifact(file_date="2099-08-03")
    art["rowProblems"] = [{"row": 2, "problem": "short row: fewer columns than header"}]
    result = ffsn.import_ffsnaprave_snapshot(store, art)
    assert result["imported"] is False and result["disposition"] == "PARTIAL_PARSE"
    assert result["problem"]["reasonCode"] == "SOURCE_FIDELITY_LOSS"
    assert _data_row(store, f"{ffsn.FFSNAPRAVE_SNAPSHOT_PREFIX}.2099-08-03") is None


def test_p3_no_inspections_refuses_governed(store):
    art = _fixture_artifact(file_date="2099-08-04", inspections=[])
    result = ffsn.import_ffsnaprave_snapshot(store, art)
    assert result["imported"] is False and result["disposition"] == "NO_INSPECTIONS"


# ---------------------------------------------------------------------------
# (6) conflicting composite key refuses; identical idempotent; changed -> conflict
# ---------------------------------------------------------------------------

def test_p3_conflicting_inspection_refuses_import(store):
    before = _governed_import_refusals(store)
    sticker, validity = sticker_num(), "2027-12-31"
    # SAME (sticker, validity) composite, DIFFERENT conformance -> conflict
    art = _fixture_artifact(file_date="2099-08-05", inspections=[
        _inspection(sticker=sticker, validity=validity, conformance="DA"),
        _inspection(sticker=sticker, validity=validity, conformance="NE")])
    result = ffsn.import_ffsnaprave_snapshot(store, art)
    assert result["imported"] is False and result["disposition"] == "CONFLICTING_INSPECTION"
    assert result["problem"]["reasonCode"] == "SOURCE_FIDELITY_LOSS"
    after = _governed_import_refusals(store)
    assert len(after) == len(before) + 1
    assert store.get_record(f"{ffsn.FFSNAPRAVE_SNAPSHOT_PREFIX}.2099-08-05") is None


def test_p3_same_sticker_different_validity_is_not_a_conflict(store):
    # a sticker re-inspected in a later cycle (different VeljavnostZnaka) is NOT a
    # conflict — two distinct inspection records, each keyed by its composite
    sticker = sticker_num()
    art = _fixture_artifact(file_date="2099-08-06", inspections=[
        _inspection(sticker=sticker, validity="2025-12-31"),
        _inspection(sticker=sticker, validity="2027-12-31")])
    result = ffsn.import_ffsnaprave_snapshot(store, art)
    assert result["imported"] is True
    reg = FFSNapraveRegister()
    reg.register_artifact(result["snapshotRef"], art)
    assert reg.match(result["snapshotRef"], sticker, validity="2025-12-31") is not None
    assert reg.match(result["snapshotRef"], sticker, validity="2027-12-31") is not None
    # sticker alone is now ambiguous (two validity windows) -> None
    assert reg.match(result["snapshotRef"], sticker) is None


def test_p3_identical_reimport_is_idempotent(store):
    art = _fixture_artifact(file_date="2099-08-07")
    a = ffsn.import_ffsnaprave_snapshot(store, art)
    b = ffsn.import_ffsnaprave_snapshot(store, art)
    assert a["imported"] is True and b["disposition"] == "ALREADY_IMPORTED"
    rows = [r for r in store.reference_data(FFSNAPRAVE_DATA_FAMILY)
            if r["snapshot_ref"] == a["snapshotRef"]]
    assert len(rows) == 1


def test_p3_changed_content_same_vintage_refuses_as_conflict(store):
    sticker = sticker_num()
    a1 = _fixture_artifact(file_date="2099-08-08",
                           inspections=[_inspection(sticker=sticker, validity="2027-12-31", conformance="DA")])
    a1["inputs"] = [{"file": "f.txt", "digest": "sha256:sharedinput"}]
    a2 = _fixture_artifact(file_date="2099-08-08",
                           inspections=[_inspection(sticker=sticker, validity="2027-12-31", conformance="DA")])
    a2["inputs"] = [{"file": "f.txt", "digest": "sha256:sharedinput"}]
    a2["inspections"][0]["DatumPregleda"] = "2025-09-09"   # changed inspection detail
    first = ffsn.import_ffsnaprave_snapshot(store, a1)
    assert first["imported"] is True
    second = ffsn.import_ffsnaprave_snapshot(store, a2)
    assert second["imported"] is False and second["disposition"] == "CONFLICT"
    assert second["problem"]["reasonCode"] == "DUPLICATE_IMPORT_AMBIGUOUS"


# ---------------------------------------------------------------------------
# parser (semicolon-delimited TXT) + cadence
# ---------------------------------------------------------------------------

def test_p3_parse_ffsnaprave_txt(tmp_path):
    txt = tmp_path / "ffsnaprave.txt"
    txt.write_text(
        '"NapravaID";"StevilkaZnaka";"VeljavnostZnaka";"DatumPregleda";"SkladnostObPregledu"\n'
        '"N100001";"123456";"2027-12-31";"2025-06-15";"DA"\n'
        '"N100002";"234567";"2026-12-31";"2024-05-10";"NE"\n',
        encoding="utf-8")
    art = ffsn.parse_ffsnaprave_file(txt, file_date="2099-08-09")
    assert art["keyFieldsPresent"] is True
    assert art["inspectionCount"] == 2
    assert art["inspections"][0]["StevilkaZnaka"] == "123456"
    assert art["inspections"][0]["VeljavnostZnaka"] == "2027-12-31"
    assert art["inspections"][1]["SkladnostObPregledu"] == "NE"
    assert art["inputs"][0]["digest"].startswith("sha256:")
    assert art["fileDate"] == "2099-08-09"


def test_p3_parse_skips_ragged_rows_without_crashing(tmp_path):
    txt = tmp_path / "ragged.txt"
    txt.write_text(
        '"NapravaID";"StevilkaZnaka";"VeljavnostZnaka";"DatumPregleda";"SkladnostObPregledu"\n'
        '"N100001";"123456";"2027-12-31";"2025-06-15";"DA"\n'
        '"N100002";"234567"\n',                       # short row
        encoding="utf-8")
    art = ffsn.parse_ffsnaprave_file(txt, file_date="2099-08-10")
    assert art["inspectionCount"] == 1
    assert len(art["rowProblems"]) == 1


def test_p3_parse_flags_misaligned_interior_drop_row(tmp_path):
    # the official file is fixed-width with non-retained fields INTERIOR to the
    # key (e.g. owner municipality). A row that drops an interior field stays
    # WIDER than the narrowest-needed retained index but shifts every later column
    # — the key would read the wrong cell. The guard checks width against the
    # header, so the misaligned row is flagged (PARTIAL_PARSE), never mis-keyed.
    txt = tmp_path / "shifted.txt"
    txt.write_text(
        '"NapravaID";"ObcinaStalnegaBivaliscaLastnika";"StevilkaZnaka";'
        '"VeljavnostZnaka";"SkladnostObPregledu";"StatRegijaMestaPregleda"\n'
        '"N100001";"Ljubljana (fictional)";"123456";"2027-12-31";"DA";"SI-REGIJA"\n'  # full width 6
        '"N100002";"234567";"2026-12-31";"DA";"SI-REGIJA"\n',                          # interior drop -> 5
        encoding="utf-8")
    art = ffsn.parse_ffsnaprave_file(txt, file_date="2099-08-11")
    assert art["inspectionCount"] == 1, "only the well-formed row parses"
    assert art["inspections"][0]["StevilkaZnaka"] == "123456"
    assert len(art["rowProblems"]) == 1, "the misaligned interior-drop row is flagged, not mis-keyed"


def test_p3_blank_validity_refuses_partial_parse(store, tmp_path):
    # PR #14 hostile B3: the composite key is StevilkaZnaka + VeljavnostZnaka. A row
    # with a blank VeljavnostZnaka must be flagged (rowProblems -> PARTIAL_PARSE),
    # never indexed/captured as sticker-only evidence.
    txt = tmp_path / "blank-validity.txt"
    txt.write_text(
        '"NapravaID";"StevilkaZnaka";"VeljavnostZnaka";"DatumPregleda";"SkladnostObPregledu"\n'
        '"N100001";"123456";"";"2025-06-15";"DA"\n',     # blank VeljavnostZnaka
        encoding="utf-8")
    art = ffsn.parse_ffsnaprave_file(txt, file_date="2099-06-02")
    assert art["inspectionCount"] == 0, "a row missing the validity component is not indexed"
    assert len(art["rowProblems"]) == 1
    result = ffsn.import_ffsnaprave_snapshot(store, art)
    assert result["imported"] is False and result["disposition"] == "PARTIAL_PARSE"
    assert result["problem"]["reasonCode"] == "SOURCE_FIDELITY_LOSS"
    assert store.get_record(f"{ffsn.FFSNAPRAVE_SNAPSHOT_PREFIX}.2099-06-02") is None


def test_p3_annual_cadence_is_declared(store):
    assert ffsn.FFSNAPRAVE_CADENCE["period"] == "ANNUAL"
    assert ffsn.FFSNAPRAVE_CADENCE["liveIntegration"] is False
