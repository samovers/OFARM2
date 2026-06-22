"""M2 P4 — SI binding active-runtime integration tests.

Engineering tests, NOT part of the named conformance suite. The SI profile
wrapper assertions live in
`profile_si_ffs.tests.m2_si_binding_wrapper_tests` and are imported here so the
root pytest command keeps discovering the same coverage. This root-owned file
keeps promotion-facing integration checks for binding attachment, subject
matching, and fake evidence refusal.
"""
from __future__ import annotations

from kernel import demo
from kernel.context import ProductRegister
from kernel.profiles.si_ffs import si_bindings as sib
from kernel.verification import REFUSE
from profile_si_ffs.tests.m2_si_binding_fixtures import (
    import_regsr_snapshot,
    uid,
)
from profile_si_ffs.tests.m2_si_binding_wrapper_tests import *  # noqa: F401,F403


def test_p4_resolved_binding_attaches_to_committed_appliedresource_identity(store, pipeline):
    # The binding subject and committed identity must match before an identity
    # binding can support promotion.
    decision = f"U9{uid()[:4]}-50/26/e"
    import_regsr_snapshot(store, "2099-04-06", decision)
    pr = ProductRegister()
    pr.load_from_store(store)
    s = uid()
    ar_ref = f"resource:m2p4.{s}"
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, pr, decision, ar_ref,
                                              created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2099-04-06T12:00:00Z")
        store.insert_record(cur, r["binding"])
    assert r["binding"]["localSubject"]["subjectRef"] == ar_ref
    bid = r["binding"]["agronomicIdentityBindingId"]
    payload = {
        "schemaVersion": "ofarm.appliedresourceidentitypayload.v0.1",
        "appliedresourceidentitypayloadId": f"resourcepayload:m2p4.{s}",
        "identityRecordRef": ar_ref,
        "recordedAt": demo.now_iso(),
        "displayName": "FIKTIV (fictional resource identity)",
        "resourceClass": "PLANT_PROTECTION_PRODUCT",
        "identityBindingRefs": [bid],
    }
    result = pipeline.commit(demo.structure_submission(payload, idem_key=f"m2p4-bind:{s}"))
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_p4_binding_for_a_different_subject_does_not_promote(store, pipeline):
    # A binding whose localSubject differs from the committed identity must not
    # attach or promote.
    decision = f"U9{uid()[:4]}-50/26/m"
    import_regsr_snapshot(store, "2099-04-07", decision)
    pr = ProductRegister()
    pr.load_from_store(store)
    s = uid()
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, pr, decision, f"resource:OTHER.{s}",
                                              created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2099-04-07T12:00:00Z")
        store.insert_record(cur, r["binding"])
    bid = r["binding"]["agronomicIdentityBindingId"]
    payload = {
        "schemaVersion": "ofarm.appliedresourceidentitypayload.v0.1",
        "appliedresourceidentitypayloadId": f"resourcepayload:m2p4mm.{s}",
        "identityRecordRef": f"resource:m2p4mm.{s}",
        "recordedAt": demo.now_iso(),
        "displayName": "FIKTIV mismatch (fictional)",
        "resourceClass": "PLANT_PROTECTION_PRODUCT",
        "identityBindingRefs": [bid],
    }
    result = pipeline.commit(demo.structure_submission(payload, idem_key=f"m2p4-mm:{s}"))
    assert result["decisionOutcome"] != "PROMOTE_ACCEPTED", \
        "a binding for another subject must not attach to a different committed identity"


def test_p4_fake_evidence_ref_produces_no_binding(store):
    # A binding may not cite fabricated captured evidence. A ref that does not
    # resolve to an EvidenceRecord yields no attachable binding.
    decision = f"U9{uid()[:4]}-50/26/f"
    import_regsr_snapshot(store, "2099-04-11", decision)
    pr = ProductRegister()
    pr.load_from_store(store)
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, pr, decision, "resource:f",
                                              created_by=demo.FARMER,
                                              evidence_ref="evidence:does-not-exist",
                                              as_of="2099-04-11T12:00:00Z")
    assert r["binding"] is None and r["verdict"] == REFUSE
    assert r["problem"]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"

    h = sib.resolve_holding(store, "100000003", "farm:f", evidence_ref="evidence:nope",
                            created_by=demo.FARMER)
    assert h["binding"] is None and h["problem"]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"

    sid = import_regsr_snapshot(store, "2099-04-12", f"U9{uid()[:4]}-50/26/x")
    h2 = sib.resolve_holding(store, "100000004", "farm:f2", evidence_ref=sid, created_by=demo.FARMER)
    assert h2["binding"] is None
