"""D6d — SI binding wrapper profile engineering tests.

These tests pin SI profile wrapper behavior over the generic G3 resolver. The
root-owned `kernel/tests/test_m2_si_bindings.py` keeps the active-runtime binding
integration checks that exercise promotion and evidence attachment.
"""
from __future__ import annotations

import uuid

from kernel import context
from kernel.profiles.si_ffs import ffsnaprave_adapter as ffsn
from kernel.profiles.si_ffs import si_bindings as sib
from kernel.profiles.si_ffs.ffsnaprave_adapter import FFSNapraveRegister
from kernel.profiles.si_ffs.gerk_adapter import GerkLayer
from kernel.verification import CONFIRM, REFUSE, REVIEW
from profile_si_ffs.test_fixtures import demo
from profile_si_ffs.tests.m2_si_binding_fixtures import (
    import_ffsnaprave_snapshot,
    import_gerk_snapshot,
    uid,
)


__all__ = [
    "test_p4_regsr_product_authorisation_is_identity_grade",
    "test_p4_regsr_unknown_product_routes_to_review_unresolved",
    "test_p4_unselected_gerk_candidate_is_not_activated",
    "test_p4_unselected_ffsnaprave_candidate_is_not_activated",
    "test_p4_unselected_ffsnaprave_validities_remain_inactive",
    "test_p4_ffsnaprave_no_match_records_no_fabricated_validity",
    "test_p4_kmg_mid_holding_is_unresolved_advisory",
    "test_p4_ffs_izkaznica_operator_is_unresolved_advisory",
    "test_p4_no_in_force_snapshot_yields_unresolved_committable_binding",
    "test_p4_only_identity_grade_confirm_yields_verified",
    "test_p4_verified_regsr_binding_records_scheme_version",
    "test_p4_unselected_ffsnaprave_ambiguity_remains_inactive",
]


def test_p4_regsr_product_authorisation_is_identity_grade(store):
    decision = "U34330-50/23/16"
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, decision,
                                              "input:demo.account", created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2026-06-12T12:00:00Z")
        store.insert_record(cur, r["binding"])
    assert r["verdict"] == CONFIRM
    b = r["binding"]
    assert b["bindingState"] == "VERIFIED"
    assert b["bindingValue"]["mappingRelation"] == "EXACT"
    assert b["bindingValue"]["registrationRef"] == decision
    assert b["promotionBoundary"]["maySupportPromotion"] is True
    assert b["promotionBoundary"]["highConsequenceUse"] == "ALLOWED_WHEN_PROFILE_AND_EVIDENCE_PASS"
    assert b["evidenceRefs"], "a confirmed binding cites its verification trace"
    assert store.get_record(b["agronomicIdentityBindingId"])["record_kind"] == "ofarm.agronomicidentitybinding.v0.1"


def test_p4_regsr_unknown_product_routes_to_review_unresolved(store):
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, "U00000-00/00/0",
                                              "input:demo.unknown", created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2026-06-12T12:00:00Z")
        store.insert_record(cur, r["binding"])
    assert r["verdict"] == REVIEW, "an unconfirmable product never becomes identity"
    b = r["binding"]
    assert b["bindingState"] == "PROVISIONAL"
    assert b["bindingValue"]["mappingRelation"] == "UNRESOLVED"
    assert b["promotionBoundary"]["maySupportPromotion"] is False
    assert b["promotionBoundary"]["highConsequenceUse"] == "REVIEW_REQUIRED"


def test_p4_unselected_gerk_candidate_is_not_activated(store):
    pid = str(uuid.uuid4().int)[:7]
    candidate = import_gerk_snapshot(store, "2099-04-03", pid)
    layer = GerkLayer()
    layer.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_parcel(store, cur, layer, pid, "field:demo.f1",
                               created_by=demo.FARMER, evidence_ref=demo.ONBOARDING_EVIDENCE,
                               as_of="2099-04-03T12:00:00Z")
        store.insert_record(cur, r["binding"])
    assert r["verdict"] == REVIEW and r["grade"] != "LOCATOR"
    b = r["binding"]
    assert b["bindingState"] == "PROVISIONAL"
    assert b["bindingValue"]["mappingRelation"] == "UNRESOLVED"
    assert b["promotionBoundary"]["maySupportPromotion"] is False
    selected = context.current_reference_snapshot(store, context.GERK_SNAPSHOT_PREFIX)
    assert r["trace"]["snapshotRefs"] == [selected["referenceSnapshotId"]]
    assert candidate not in r["trace"]["snapshotRefs"]


def test_p4_unselected_ffsnaprave_candidate_is_not_activated(store):
    sticker, validity = str(uuid.uuid4().int)[:6], "2027-12-31"
    import_ffsnaprave_snapshot(store, "2099-04-04", sticker, validity)
    reg = FFSNapraveRegister()
    reg.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_equipment(store, cur, reg, sticker, "equip:demo.sprayer",
                                  created_by=demo.FARMER, evidence_ref=demo.ONBOARDING_EVIDENCE,
                                  validity=validity, as_of="2099-04-04T12:00:00Z")
        store.insert_record(cur, r["binding"])
    assert r["verdict"] == REFUSE and r["grade"] != "LOCATOR"
    b = r["binding"]
    assert b["bindingState"] == "PROVISIONAL"
    assert b["bindingValue"]["mappingRelation"] == "UNRESOLVED"
    assert b["promotionBoundary"]["maySupportPromotion"] is False
    assert r["trace"] is None


def test_p4_unselected_ffsnaprave_validities_remain_inactive(store):
    sticker = str(uuid.uuid4().int)[:6]
    art = {
        "snapshotKind": "SI_UVHVVR_FFS_NAPRAVE_PARSE", "fileDate": "2099-04-08",
        "canonicalVersionLabel": "ffsn-multi", "keyFieldsPresent": True,
        "attributesAvailable": list(ffsn.RETAINED_FIELDS), "inspectionCount": 2, "rowProblems": [],
        "inspections": [
            {"NapravaID": f"N{uid()[:5]}", "StevilkaZnaka": sticker, "VeljavnostZnaka": "2025-12-31",
             "DatumPregleda": "2023-06-15", "SkladnostObPregledu": "DA"},
            {"NapravaID": f"N{uid()[:5]}", "StevilkaZnaka": sticker, "VeljavnostZnaka": "2027-12-31",
             "DatumPregleda": "2025-06-15", "SkladnostObPregledu": "DA"}],
        "inputs": [{"file": "f.txt", "digest": f"sha256:{uid()}cafe"}]}
    ffsn.import_ffsnaprave_snapshot(store, art)
    reg = FFSNapraveRegister()
    reg.load_from_store(store)
    with store.serialized_tx() as cur:
        r1 = sib.resolve_equipment(store, cur, reg, sticker, "equip:e", created_by=demo.FARMER,
                                   evidence_ref=demo.ONBOARDING_EVIDENCE, validity="2025-12-31",
                                   as_of="2099-04-08T12:00:00Z")
        r2 = sib.resolve_equipment(store, cur, reg, sticker, "equip:e", created_by=demo.FARMER,
                                   evidence_ref=demo.ONBOARDING_EVIDENCE, validity="2027-12-31",
                                   as_of="2099-04-08T12:00:00Z")
    assert r1["verdict"] == r2["verdict"] == REFUSE
    assert r1["resolvedValidity"] is r2["resolvedValidity"] is None
    assert r1["trace"] is r2["trace"] is None


def test_p4_ffsnaprave_no_match_records_no_fabricated_validity(store):
    import_ffsnaprave_snapshot(
        store, "2099-04-09", str(uuid.uuid4().int)[:6], "2027-12-31")
    reg = FFSNapraveRegister()
    reg.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_equipment(store, cur, reg, "0000000", "equip:none",
                                  created_by=demo.FARMER, evidence_ref=demo.ONBOARDING_EVIDENCE,
                                  as_of="2099-04-09T12:00:00Z")
        store.insert_record(cur, r["binding"])
    assert r["verdict"] == REFUSE and r["grade"] != "LOCATOR"
    notes = r["binding"]["bindingValue"]["notes"]
    assert "None" not in notes and "unresolved" in notes
    assert r["binding"]["bindingValue"]["mappingRelation"] == "UNRESOLVED"


def test_p4_kmg_mid_holding_is_unresolved_advisory(store):
    r = sib.resolve_holding(store, "100000001", "farm:demo.kmetija.a",
                            evidence_ref=demo.ONBOARDING_EVIDENCE, created_by=demo.FARMER)
    assert r["verdict"] == "UNRESOLVED" and r["advisory"] and "no KMG-MID" in r["advisory"]
    b = r["binding"]
    assert b["bindingState"] == "PROVISIONAL"
    assert b["bindingValue"]["mappingRelation"] == "UNRESOLVED"
    assert b["promotionBoundary"]["maySupportPromotion"] is False
    assert b["externalScheme"]["schemeRef"] == "scheme:si.kmg-mid"
    with store.serialized_tx() as cur:
        store.insert_record(cur, b)
    assert store.get_record(b["agronomicIdentityBindingId"]) is not None


def test_p4_ffs_izkaznica_operator_is_unresolved_advisory(store):
    r = sib.resolve_operator(store, "IZK-000123", "party:demo.farmer.one",
                             evidence_ref=demo.ONBOARDING_EVIDENCE, created_by=demo.FARMER)
    assert r["verdict"] == "UNRESOLVED" and r["advisory"] and "FFS-IZKAZNICA" in r["advisory"]
    b = r["binding"]
    assert b["bindingState"] == "PROVISIONAL"
    assert b["bindingValue"]["mappingRelation"] == "UNRESOLVED"
    assert b["externalScheme"]["schemeRef"] == "scheme:si.ffs-izkaznica"
    with store.serialized_tx() as cur:
        store.insert_record(cur, b)
    assert store.get_record(b["agronomicIdentityBindingId"]) is not None


def test_p4_no_in_force_snapshot_yields_unresolved_committable_binding(store):
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, "U12345-50/20/1",
                                              "input:demo.early", created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2020-01-01T00:00:00Z")
        store.insert_record(cur, r["binding"])
    assert r["verdict"] == REFUSE
    b = r["binding"]
    assert b["bindingState"] == "PROVISIONAL"
    assert b["bindingValue"]["mappingRelation"] == "UNRESOLVED"
    assert b["evidenceRefs"] == [demo.ONBOARDING_EVIDENCE]
    assert b["promotionBoundary"]["maySupportPromotion"] is False


def test_p4_only_identity_grade_confirm_yields_verified(store):
    decision = "U34330-50/23/16"
    with store.serialized_tx() as cur:
        confirmed = sib.resolve_product_authorisation(store, cur, decision,
                                                      "input:x", created_by=demo.FARMER,
                                                      evidence_ref=demo.ONBOARDING_EVIDENCE,
                                                      as_of="2026-06-12T12:00:00Z")
    holding = sib.resolve_holding(store, "100000002", "farm:y", evidence_ref=demo.ONBOARDING_EVIDENCE,
                                  created_by=demo.FARMER)
    assert confirmed["binding"]["bindingState"] == "VERIFIED"
    assert holding["binding"]["bindingState"] != "VERIFIED"
    for r in (confirmed, holding):
        assert r["binding"]["promotionBoundary"]["mustNotPromoteTo"] == ["OFARM_CORE_MEANING"]


def test_p4_verified_regsr_binding_records_scheme_version(store):
    decision = "U34330-50/23/16"
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, decision, "resource:v",
                                              created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2026-06-12T12:00:00Z")
        store.insert_record(cur, r["binding"])
    b = r["binding"]
    assert b["bindingState"] == "VERIFIED" and b["promotionBoundary"]["maySupportPromotion"] is True
    sv = b["externalScheme"].get("schemeVersion")
    selected = context.current_reference_snapshot(store, context.REGSR_SNAPSHOT_PREFIX)
    assert sv == selected["canonicalVersionLabel"], \
        "VERIFIED binding must record the selected register vintage as schemeVersion"


def test_p4_unselected_ffsnaprave_ambiguity_remains_inactive(store):
    sticker = str(uuid.uuid4().int)[:6]
    art = {
        "snapshotKind": "SI_UVHVVR_FFS_NAPRAVE_PARSE", "fileDate": "2099-04-13",
        "canonicalVersionLabel": "ffsn-amb", "keyFieldsPresent": True,
        "attributesAvailable": list(ffsn.RETAINED_FIELDS), "inspectionCount": 2, "rowProblems": [],
        "inspections": [
            {"NapravaID": f"N{uid()[:5]}", "StevilkaZnaka": sticker, "VeljavnostZnaka": "2025-12-31",
             "DatumPregleda": "2023-06-15", "SkladnostObPregledu": "DA"},
            {"NapravaID": f"N{uid()[:5]}", "StevilkaZnaka": sticker, "VeljavnostZnaka": "2027-12-31",
             "DatumPregleda": "2025-06-15", "SkladnostObPregledu": "DA"}],
        "inputs": [{"file": "f.txt", "digest": f"sha256:{uid()}cafe"}]}
    ffsn.import_ffsnaprave_snapshot(store, art)
    reg = FFSNapraveRegister()
    reg.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_equipment(store, cur, reg, sticker, "equip:amb", created_by=demo.FARMER,
                                  evidence_ref=demo.ONBOARDING_EVIDENCE, validity=None,
                                  as_of="2099-04-13T12:00:00Z")
    assert r["verdict"] == REFUSE
    assert r["trace"] is None
    with store.serialized_tx() as cur:
        r2 = sib.resolve_equipment(store, cur, reg, "0000000", "equip:absent", created_by=demo.FARMER,
                                   evidence_ref=demo.ONBOARDING_EVIDENCE, validity=None,
                                   as_of="2099-04-13T12:00:00Z")
    assert r2["verdict"] == REFUSE
    assert r2["trace"] is None
