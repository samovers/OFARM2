"""M2 P4 — SI bindings: the five SI schemes bound to committed identities via
AgronomicIdentityBinding, resolved through the GENERIC G3 ReferenceResolver.

Engineering tests, NOT part of the named conformance suite. They pin the SI
binding wrappers (kernel/profiles/si_ffs/si_bindings.py): REGSR product
authorisation is identity-grade (CONFIRM -> VERIFIED); GERK parcel and FFSNaprave
sticker are locator-only (REVIEW -> PROVISIONAL/LOCAL_ONLY); KMG-MID holding and
FFS-IZKAZNICA operator card have no register and resolve UNRESOLVED + advisory
(PROVISIONAL/UNRESOLVED), committable as draft but promotion requires review. The
wrappers drive the generic resolver (no per-scheme branch in the kernel) and
normalise LookupResult enums. All identifiers fictional and format-true (D14).
"""
from __future__ import annotations

import uuid

from kernel import demo
from kernel.profiles.si_ffs import regsr_adapter as regsr
from kernel.profiles.si_ffs import gerk_adapter as gerk
from kernel.profiles.si_ffs import ffsnaprave_adapter as ffsn
from kernel.profiles.si_ffs import si_bindings as sib
from kernel.profiles.si_ffs.gerk_adapter import GerkLayer
from kernel.profiles.si_ffs.ffsnaprave_adapter import FFSNapraveRegister
from kernel.context import ProductRegister
from kernel.verification import CONFIRM, REFUSE, REVIEW


def uid():
    return uuid.uuid4().hex[:8]


def _regsr_snapshot(store, register_day, decision):
    art = {
        "snapshotKind": "SI_UVHVVR_FFS_REG_HTML_PARSE", "registerDay": register_day,
        "sourceUrl": regsr.REGSR_SOURCE_URL, "productCount": 1,
        "products": [{"regsrCode": "9001", "name": "FIKTIV (fictional)",
                      "registrationValidUntil": "2028-08-15"}],
        "productDetails": [{"name": "FIKTIV (fictional)", "decisions": [
            {"decisionType": "Registracija", "decisionNumber": decision,
             "issued": "2026-01-01", "validUntil": "2028-08-15"}]}],
        "rowProblems": [], "inputs": [{"file": "f.html", "digest": f"sha256:{uid()}cafe"}]}
    return regsr.import_regsr_snapshot(store, art)["snapshotRef"]


def _gerk_snapshot(store, layer_date, pid):
    art = {
        "snapshotKind": "SI_MKGP_GERK_LAYER_PARSE", "layerDate": layer_date,
        "canonicalVersionLabel": f"gerk-{layer_date}", "pidField": "GERK_PID",
        "attributesAvailable": ["GERK_PID", "RABA_ID", "AREA", "OPIS_RABE"],
        "featureCount": 1, "rowProblems": [],
        "features": [{"gerkPid": pid, "rabaId": "1300", "area": "0.5",
                      "opisRabe": "trajni travnik (fictional)"}],
        "inputs": [{"file": "f.csv", "digest": f"sha256:{uid()}cafe"}]}
    return gerk.import_gerk_snapshot(store, art)["snapshotRef"]


def _ffsn_snapshot(store, file_date, sticker, validity):
    art = {
        "snapshotKind": "SI_UVHVVR_FFS_NAPRAVE_PARSE", "fileDate": file_date,
        "canonicalVersionLabel": f"ffsn-{file_date}", "keyFieldsPresent": True,
        "attributesAvailable": list(ffsn.RETAINED_FIELDS), "inspectionCount": 1,
        "rowProblems": [],
        "inspections": [{"NapravaID": f"N{uid()[:5]}", "StevilkaZnaka": sticker,
                         "VeljavnostZnaka": validity, "DatumPregleda": "2025-06-15",
                         "SkladnostObPregledu": "DA"}],
        "inputs": [{"file": "f.txt", "digest": f"sha256:{uid()}cafe"}]}
    return ffsn.import_ffsnaprave_snapshot(store, art)["snapshotRef"]


# ---------------------------------------------------------------------------
# (1) REGSR product authorisation -> IDENTITY-grade CONFIRM -> VERIFIED/EXACT
# ---------------------------------------------------------------------------

def test_p4_regsr_product_authorisation_is_identity_grade(store):
    decision = f"U9{uid()[:4]}-50/26/1"
    _regsr_snapshot(store, "2099-04-01", decision)
    pr = ProductRegister()
    pr.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, pr, decision,
                                              "input:demo.account", created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2099-04-01T12:00:00Z")
        store.insert_record(cur, r["binding"])   # contract-valid persist
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
    _regsr_snapshot(store, "2099-04-02", f"U9{uid()[:4]}-50/26/known")
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


# ---------------------------------------------------------------------------
# (2) GERK parcel + FFSNaprave sticker -> LOCATOR-only -> REVIEW -> PROVISIONAL
# ---------------------------------------------------------------------------

def test_p4_gerk_parcel_is_locator_only_review(store):
    pid = str(uuid.uuid4().int)[:7]
    _gerk_snapshot(store, "2099-04-03", pid)
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
    _ffsn_snapshot(store, "2099-04-04", sticker, validity)
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


# ---------------------------------------------------------------------------
# (3) KMG-MID holding + FFS-IZKAZNICA operator -> NO register -> UNRESOLVED advisory
# ---------------------------------------------------------------------------

def test_p4_kmg_mid_holding_is_unresolved_advisory(store):
    r = sib.resolve_holding("100000001", "farm:demo.kmetija.a",
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
    r = sib.resolve_operator("IZK-000123", "party:demo.farmer.one",
                             evidence_ref=demo.ONBOARDING_EVIDENCE, created_by=demo.FARMER)
    assert r["verdict"] == "UNRESOLVED" and r["advisory"] and "FFS-IZKAZNICA" in r["advisory"]
    b = r["binding"]
    assert b["bindingState"] == "PROVISIONAL"
    assert b["bindingValue"]["mappingRelation"] == "UNRESOLVED"
    assert b["externalScheme"]["schemeRef"] == "scheme:si.ffs-izkaznica"
    with store.serialized_tx() as cur:
        store.insert_record(cur, b)
    assert store.get_record(b["agronomicIdentityBindingId"]) is not None


# ---------------------------------------------------------------------------
# (4) every binding is contract-valid; free text never becomes identity (D6)
# ---------------------------------------------------------------------------

def test_p4_resolved_binding_attaches_to_committed_appliedresource_identity(store, pipeline):
    # the "bound to committed identities" loop, end-to-end: a resolved REGSR binding
    # attaches to a committed AppliedResource identity via identityBindingRefs (G1
    # validates the ref resolves to an AgronomicIdentityBinding); a fabricated ref
    # does NOT accept (control: proves the ref is validated, not a no-op field).
    decision = f"U9{uid()[:4]}-50/26/e"
    _regsr_snapshot(store, "2099-04-06", decision)
    pr = ProductRegister()
    pr.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, pr, decision, "input:m2p4.e",
                                              created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2099-04-06T12:00:00Z")
        store.insert_record(cur, r["binding"])
    bid = r["binding"]["agronomicIdentityBindingId"]
    s = uid()
    payload = {
        "schemaVersion": "ofarm.appliedresourceidentitypayload.v0.1",
        "appliedresourceidentitypayloadId": f"resourcepayload:m2p4.{s}",
        "identityRecordRef": f"input:m2p4.{s}",
        "recordedAt": demo.now_iso(),
        "displayName": "FIKTIV (fictional resource identity)",
        "resourceClass": "PLANT_PROTECTION_PRODUCT",
        "identityBindingRefs": [bid]}
    result = pipeline.commit(demo.structure_submission(payload, idem_key=f"m2p4-bind:{s}"))
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    s2 = uid()
    bogus = {**payload, "appliedresourceidentitypayloadId": f"resourcepayload:m2p4b.{s2}",
             "identityRecordRef": f"input:m2p4b.{s2}", "identityBindingRefs": ["binding:does-not-exist"]}
    bad = pipeline.commit(demo.structure_submission(bogus, idem_key=f"m2p4-bad:{s2}"))
    assert bad["decisionOutcome"] != "PROMOTE_ACCEPTED"


def test_p4_no_in_force_snapshot_yields_unresolved_committable_binding(store):
    # with NO in-force snapshot at resolution time (as_of before the shipped vintage),
    # verify REFUSEs; the binding is still UNRESOLVED + contract-valid — it cites the
    # captured-identifier evidence (no empty evidence set), committable as a draft.
    pr = ProductRegister()
    pr.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, pr, "U12345-50/20/1",
                                              "input:demo.early", created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2020-01-01T00:00:00Z")
        store.insert_record(cur, r["binding"])   # must be contract-valid
    assert r["verdict"] == REFUSE
    b = r["binding"]
    assert b["bindingState"] == "PROVISIONAL"
    assert b["bindingValue"]["mappingRelation"] == "UNRESOLVED"
    assert b["evidenceRefs"] == [demo.ONBOARDING_EVIDENCE]   # no trace -> captured evidence only
    assert b["promotionBoundary"]["maySupportPromotion"] is False


def test_p4_only_identity_grade_confirm_yields_verified(store):
    # the binding-state ladder: ONLY an identity-grade G3 CONFIRM (REGSR) yields
    # VERIFIED + maySupportPromotion; everything else is PROVISIONAL and review-bound
    decision = f"U9{uid()[:4]}-50/26/9"
    _regsr_snapshot(store, "2099-04-05", decision)
    pr = ProductRegister()
    pr.load_from_store(store)
    with store.serialized_tx() as cur:
        confirmed = sib.resolve_product_authorisation(store, cur, pr, decision,
                                                      "input:x", created_by=demo.FARMER,
                                                      evidence_ref=demo.ONBOARDING_EVIDENCE,
                                                      as_of="2099-04-05T12:00:00Z")
    holding = sib.resolve_holding("100000002", "farm:y", evidence_ref=demo.ONBOARDING_EVIDENCE,
                                  created_by=demo.FARMER)
    assert confirmed["binding"]["bindingState"] == "VERIFIED"
    assert holding["binding"]["bindingState"] != "VERIFIED"
    # neither may mutate Core meaning
    for r in (confirmed, holding):
        assert r["binding"]["promotionBoundary"]["mustNotPromoteTo"] == ["OFARM_CORE_MEANING"]
