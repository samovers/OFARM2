"""D6d — SI binding wrapper profile engineering tests.

These tests pin SI profile wrapper behavior over the generic G3 resolver. The
root-owned `kernel/tests/test_m2_si_bindings.py` keeps the active-runtime binding
integration checks that exercise promotion and evidence attachment.
"""
from __future__ import annotations

import uuid

from kernel import demo
from kernel.context import ProductRegister
from kernel.profiles.si_ffs import ffsnaprave_adapter as ffsn
from kernel.profiles.si_ffs import si_bindings as sib
from kernel.profiles.si_ffs.ffsnaprave_adapter import FFSNapraveRegister
from kernel.profiles.si_ffs.gerk_adapter import GerkLayer
from kernel.verification import CONFIRM, REFUSE, REVIEW
from profile_si_ffs.tests.m2_si_binding_fixtures import (
    import_ffsnaprave_snapshot,
    import_gerk_snapshot,
    import_regsr_snapshot,
    uid,
)


__all__ = [
    "test_p4_regsr_product_authorisation_is_identity_grade",
    "test_p4_regsr_unknown_product_routes_to_review_unresolved",
    "test_p4_gerk_parcel_is_locator_only_review",
    "test_p4_ffsnaprave_equipment_is_locator_only_review",
    "test_p4_ffsnaprave_composite_key_validity_recorded_not_collapsed",
    "test_p4_ffsnaprave_no_match_records_no_fabricated_validity",
    "test_p4_kmg_mid_holding_is_unresolved_advisory",
    "test_p4_ffs_izkaznica_operator_is_unresolved_advisory",
    "test_p4_no_in_force_snapshot_yields_unresolved_committable_binding",
    "test_p4_only_identity_grade_confirm_yields_verified",
    "test_p4_verified_regsr_binding_records_scheme_version",
    "test_p4_ffsnaprave_ambiguous_sticker_surfaces_multiple_candidates",
]


def test_p4_regsr_product_authorisation_is_identity_grade(store):
    decision = f"U9{uid()[:4]}-50/26/1"
    import_regsr_snapshot(store, "2099-04-01", decision)
    pr = ProductRegister()
    pr.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, pr, decision,
                                              "input:demo.account", created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2099-04-01T12:00:00Z")
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
    import_regsr_snapshot(store, "2099-04-02", f"U9{uid()[:4]}-50/26/known")
    pr = ProductRegister()
    pr.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, pr, "U00000-00/00/0",
                                              "input:demo.unknown", created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2099-04-02T12:00:00Z")
        store.insert_record(cur, r["binding"])
    assert r["verdict"] == REVIEW, "an unconfirmable product never becomes identity"
    b = r["binding"]
    assert b["bindingState"] == "PROVISIONAL"
    assert b["bindingValue"]["mappingRelation"] == "UNRESOLVED"
    assert b["promotionBoundary"]["maySupportPromotion"] is False
    assert b["promotionBoundary"]["highConsequenceUse"] == "REVIEW_REQUIRED"


def test_p4_gerk_parcel_is_locator_only_review(store):
    pid = str(uuid.uuid4().int)[:7]
    import_gerk_snapshot(store, "2099-04-03", pid)
    layer = GerkLayer()
    layer.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_parcel(store, cur, layer, pid, "field:demo.f1",
                               created_by=demo.FARMER, evidence_ref=demo.ONBOARDING_EVIDENCE,
                               as_of="2099-04-03T12:00:00Z")
        store.insert_record(cur, r["binding"])
    assert r["verdict"] == REVIEW and r["grade"] == "LOCATOR"
    b = r["binding"]
    assert b["bindingState"] == "PROVISIONAL"
    assert b["bindingValue"]["mappingRelation"] == "LOCAL_ONLY"
    assert b["promotionBoundary"]["maySupportPromotion"] is False
    assert r["advisory"] and "locator-only" in r["advisory"]


def test_p4_ffsnaprave_equipment_is_locator_only_review(store):
    sticker, validity = str(uuid.uuid4().int)[:6], "2027-12-31"
    import_ffsnaprave_snapshot(store, "2099-04-04", sticker, validity)
    reg = FFSNapraveRegister()
    reg.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_equipment(store, cur, reg, sticker, "equip:demo.sprayer",
                                  created_by=demo.FARMER, evidence_ref=demo.ONBOARDING_EVIDENCE,
                                  validity=validity, as_of="2099-04-04T12:00:00Z")
        store.insert_record(cur, r["binding"])
    assert r["verdict"] == REVIEW and r["grade"] == "LOCATOR"
    b = r["binding"]
    assert b["bindingState"] == "PROVISIONAL"
    assert b["bindingValue"]["mappingRelation"] == "LOCAL_ONLY"
    assert b["promotionBoundary"]["maySupportPromotion"] is False
    assert validity in b["bindingValue"]["notes"]
    assert r["trace"]["datesObserved"]["statusEffectiveUntil"] == f"{validity}T00:00:00Z"


def test_p4_ffsnaprave_composite_key_validity_recorded_not_collapsed(store):
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
    assert r1["resolvedValidity"] == "2025-12-31T00:00:00Z"
    assert r2["resolvedValidity"] == "2027-12-31T00:00:00Z"
    assert "2025-12-31" in r1["binding"]["bindingValue"]["notes"]
    assert "2027-12-31" in r2["binding"]["bindingValue"]["notes"]
    assert r1["trace"]["datesObserved"]["statusEffectiveUntil"] != \
        r2["trace"]["datesObserved"]["statusEffectiveUntil"], "not collapsed to one validity"


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
    assert r["verdict"] == REVIEW and r["grade"] != "LOCATOR"
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
    pr = ProductRegister()
    pr.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, pr, "U12345-50/20/1",
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
    decision = f"U9{uid()[:4]}-50/26/9"
    import_regsr_snapshot(store, "2099-04-05", decision)
    pr = ProductRegister()
    pr.load_from_store(store)
    with store.serialized_tx() as cur:
        confirmed = sib.resolve_product_authorisation(store, cur, pr, decision,
                                                      "input:x", created_by=demo.FARMER,
                                                      evidence_ref=demo.ONBOARDING_EVIDENCE,
                                                      as_of="2099-04-05T12:00:00Z")
    holding = sib.resolve_holding(store, "100000002", "farm:y", evidence_ref=demo.ONBOARDING_EVIDENCE,
                                  created_by=demo.FARMER)
    assert confirmed["binding"]["bindingState"] == "VERIFIED"
    assert holding["binding"]["bindingState"] != "VERIFIED"
    for r in (confirmed, holding):
        assert r["binding"]["promotionBoundary"]["mustNotPromoteTo"] == ["OFARM_CORE_MEANING"]


def test_p4_verified_regsr_binding_records_scheme_version(store):
    decision = f"U9{uid()[:4]}-50/26/v"
    import_regsr_snapshot(store, "2099-04-10", decision)
    pr = ProductRegister()
    pr.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, pr, decision, "resource:v",
                                              created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2099-04-10T12:00:00Z")
        store.insert_record(cur, r["binding"])
    b = r["binding"]
    assert b["bindingState"] == "VERIFIED" and b["promotionBoundary"]["maySupportPromotion"] is True
    sv = b["externalScheme"].get("schemeVersion")
    assert sv and "2099-04-10" in sv, "VERIFIED binding must record the register vintage as schemeVersion"


def test_p4_ffsnaprave_ambiguous_sticker_surfaces_multiple_candidates(store):
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
    t = r["trace"]
    assert r["verdict"] == REVIEW
    assert t["candidateCount"] == 2 and t["statusObserved"] == "MULTIPLE_CANDIDATES"
    assert t["discrepancies"] and "disambiguate" in t["discrepancies"][0]["note"]
    with store.serialized_tx() as cur:
        r2 = sib.resolve_equipment(store, cur, reg, "0000000", "equip:absent", created_by=demo.FARMER,
                                   evidence_ref=demo.ONBOARDING_EVIDENCE, validity=None,
                                   as_of="2099-04-13T12:00:00Z")
    assert r2["trace"]["candidateCount"] == 0 and r2["trace"]["statusObserved"] == "NOT_FOUND"
