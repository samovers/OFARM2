"""M2 P3 — SI FFSNaprave sprayer-inspection import + Equipment-identity evidence.

Engineering tests, NOT part of the named conformance suite. They pin the SI
FFSNaprave adapter riding the generic G2 import + the store-backed reference-data
cache, and its G1 integration: a yearly delimited file imports as a dated
FFSNaprave ReferenceSnapshot AND its inspections persist store-backed; a farm
sprayer matches by the composite sticker key (StevilkaZnaka + VeljavnostZnaka);
a match CAPTURES a REGISTRY_EXTRACT EvidenceRecord whose id populates
EquipmentIdentityPayload.inspectionEvidenceRefs on an Equipment identity committed
through G1; no match → the equipment is recorded WITHOUT inspection evidence
(advisory, never a silent pass-as-compliant); failed/conflicting/partial imports
are governed refusals. Far-future (2099) vintages keep fixtures out of NOW-current
resolution. All sticker / machine / inspection values fictional and format-true (D14).
"""
from __future__ import annotations

import uuid

from kernel import demo
from kernel.profiles.si_ffs import ffsnaprave_adapter as ffsn
from kernel.profiles.si_ffs.ffsnaprave_adapter import FFSNAPRAVE_DATA_FAMILY, FFSNapraveRegister


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


# ---------------------------------------------------------------------------
# (2) a farm sprayer matches by the composite sticker key (StevilkaZnaka + Veljavnost)
# ---------------------------------------------------------------------------

def test_p3_register_matches_sticker_composite(store):
    sticker = sticker_num()
    art = _fixture_artifact(file_date="2099-09-29",
                            inspections=[_inspection(sticker=sticker, validity="2027-12-31")])
    sid = ffsn.import_ffsnaprave_snapshot(store, art)["snapshotRef"]
    reg = FFSNapraveRegister()
    reg.load_from_store(store)
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

def test_p3_sticker_match_attaches_inspection_evidence_to_equipment(store, pipeline):
    sticker, validity = sticker_num(), "2027-12-31"
    art = _fixture_artifact(file_date="2099-09-01",
                            inspections=[_inspection(sticker=sticker, validity=validity)])
    sid = ffsn.import_ffsnaprave_snapshot(store, art)["snapshotRef"]
    reg = FFSNapraveRegister()
    reg.load_from_store(store)
    eid = ffsn.attach_inspection_evidence(store, reg, sid, sticker, validity=validity,
                                          captured_by=demo.FARMER)
    assert eid is not None
    ev = store.get_record(eid)
    assert ev is not None and ev["record_kind"] == "ofarm.evidencerecord.v0.1"
    assert ev["payload"]["evidenceClass"] == "REGISTRY_EXTRACT"
    assert ev["payload"]["rawAssetRef"] == sid
    # capturedAt is the register vintage the extract was taken from, not 'now'
    assert ev["payload"]["capturedAt"] == "2099-09-01T00:00:00Z"
    # the Equipment identity commits through G1 carrying the inspection evidence
    s = uid()
    payload = _equipment_payload(f"equip:m2p3.{s}", f"equippayload:m2p3.{s}", inspection_refs=[eid])
    result = pipeline.commit(demo.structure_submission(payload, idem_key=f"m2p3-ev:{s}"))
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert result["inForceResultCategory"] == "ACCEPTED_STRUCTURAL_STATE"
    # CONTROL (non-tautology): a fabricated inspection ref does NOT resolve to an
    # EvidenceRecord, so G1 must NOT accept it — proving the matched ref is what
    # makes the accept meaningful, not a no-op field
    s2 = uid()
    bogus = _equipment_payload(f"equip:m2p3b.{s2}", f"equippayload:m2p3b.{s2}",
                               inspection_refs=["evidence:si.ffs-naprave.does-not-exist"])
    bad = pipeline.commit(demo.structure_submission(bogus, idem_key=f"m2p3-bad:{s2}"))
    assert bad["decisionOutcome"] != "PROMOTE_ACCEPTED"


# ---------------------------------------------------------------------------
# (4) no match -> the equipment is recorded WITHOUT inspection evidence (advisory,
#     never a silent pass-as-compliant)
# ---------------------------------------------------------------------------

def test_p3_no_match_equipment_recorded_without_inspection_evidence(store, pipeline):
    art = _fixture_artifact(file_date="2099-09-02",
                            inspections=[_inspection(sticker=sticker_num(), validity="2027-12-31")])
    sid = ffsn.import_ffsnaprave_snapshot(store, art)["snapshotRef"]
    reg = FFSNapraveRegister()
    reg.load_from_store(store)
    assert ffsn.attach_inspection_evidence(store, reg, sid, "0000000", validity="2027-12-31",
                                           captured_by=demo.FARMER) is None
    s = uid()
    payload = _equipment_payload(f"equip:m2p3n.{s}", f"equippayload:m2p3n.{s}")  # no inspection refs
    result = pipeline.commit(demo.structure_submission(payload, idem_key=f"m2p3-noev:{s}"))
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED", \
        "equipment without an inspection match is still recorded — advisory, not blocked"


def test_p3_attach_inspection_evidence_is_idempotent(store):
    sticker, validity = sticker_num(), "2027-12-31"
    art = _fixture_artifact(file_date="2099-09-03",
                            inspections=[_inspection(sticker=sticker, validity=validity)])
    sid = ffsn.import_ffsnaprave_snapshot(store, art)["snapshotRef"]
    reg = FFSNapraveRegister()
    reg.load_from_store(store)
    a = ffsn.attach_inspection_evidence(store, reg, sid, sticker, validity=validity, captured_by=demo.FARMER)
    b = ffsn.attach_inspection_evidence(store, reg, sid, sticker, validity=validity, captured_by=demo.FARMER)
    assert a == b and a is not None
    assert store.get_record(a) is not None  # exactly one EvidenceRecord, no PK conflict


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
    reg.load_from_store(store)
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


def test_p3_annual_cadence_is_declared(store):
    assert ffsn.FFSNAPRAVE_CADENCE["period"] == "ANNUAL"
    assert ffsn.FFSNAPRAVE_CADENCE["liveIntegration"] is False
