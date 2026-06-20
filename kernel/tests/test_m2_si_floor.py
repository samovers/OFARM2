"""M2 P5 — SI evidence floor as package content + non-blocking advisories.

Engineering tests, NOT part of the named conformance suite. They pin the P5
mechanism-boundary fix (the SI operation-claim evidence floor composition is
profile/package content, read generically by the kernel — no SI floor VALUE
lives in kernel/*.py) and the non-blocking advisory-twin warnings
(authorisation-mismatch, dose-range) raised on the commit result.

Durability note (honest reporting): the DURABLE Advisory-Twin record (a
trace-safe ADVISORY_OUTPUT surfaced in the passport) is DEFERRED — emitting it
inside the operation-claim commit would need a second PromotionTrace (the
reachability invariant has no advisory slot), an architectural change out of P5
scope. P5 ships the floor move + the immediate non-blocking result warning;
durable advisory emission is a recorded follow-up (ERRATA E-006). All
identifiers fictional and format-true (privacy rule 1).
"""
from __future__ import annotations

import json
import uuid

import pytest

from kernel import config, demo, policy, profile_policy


def uid():
    return uuid.uuid4().hex[:8]


def _spray(pipeline, **kw):
    return pipeline.commit(demo.spray_submission(
        f"p5:{uid()}", erp_id=f"erp:p5.{uid()}", **kw))


def _problem_titles(result):
    return [p.get("title", "") for p in result.get("problems", [])]


# ---------------------------------------------------------------------------
# Part A — the floor is package content, read generically (no kernel SI values)
# ---------------------------------------------------------------------------

def test_floor_is_sourced_from_package_content():
    hard, soft = profile_policy.operation_floor()
    doc = json.loads(config.EVIDENCE_POLICY_PATH.read_text())
    assert config.EVIDENCE_POLICY_PATH.parent.name == "profile_si_ffs"
    assert list(hard) == doc["operationFloor"]["hardItems"]
    assert list(soft) == doc["operationFloor"]["softItems"]
    # the SI values are the package's, not a kernel constant
    assert "dose-unit" in hard and "product-binding" in soft


def test_kernel_carries_no_si_floor_constants():
    # acceptance: kernel/ holds no SI-specific floor values after the move
    assert not hasattr(policy, "OPERATION_FLOOR_HARD_ITEMS")
    assert not hasattr(policy, "OPERATION_FLOOR_SOFT_ITEMS")


def test_clean_operation_claim_still_promotes(store, pipeline):
    # existing promotion behavior is unchanged for a clean claim
    assert _spray(pipeline, confirm=True)["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_missing_policy_fails_closed(store, pipeline, monkeypatch, tmp_path):
    # a missing floor policy must FAIL CLOSED (governed PROFILE_NOT_ACTIVE), never
    # crash and never silently permit
    monkeypatch.setattr(config, "EVIDENCE_POLICY_PATH", tmp_path / "absent.json")
    r = _spray(pipeline, confirm=True)
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert r["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"


def test_malformed_policy_fails_closed(store, pipeline, monkeypatch, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json")
    monkeypatch.setattr(config, "EVIDENCE_POLICY_PATH", bad)
    r = _spray(pipeline, confirm=True)
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert r["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"


def test_floor_composition_from_package_changes_behavior(store, pipeline, monkeypatch, tmp_path):
    # changing the PACKAGE floor changes behavior WITHOUT touching kernel/: a claim
    # missing its crop binding ROUTES TO REVIEW by default (crop-binding is SOFT),
    # but REFUSES under a package policy that makes crop-binding HARD. Same claim,
    # two package policies, two outcomes — the floor is sourced from the package.
    def _no_crop_binding():
        return demo.spray_submission(
            f"p5-nocrop:{uid()}", erp_id=f"erp:p5.nocrop.{uid()}",
            confirm=True, binding_refs=[demo.PRODUCT_BINDING])   # crop binding omitted

    default = pipeline.commit(_no_crop_binding())
    assert default["decisionOutcome"] == "REQUIRE_REVIEW", \
        "crop-binding SOFT by default -> route to review"

    harder = tmp_path / "crop_hard_policy.json"
    harder.write_text(json.dumps({
        "policyId": "policy:test.crop-hard",
        "operationFloor": {
            "hardItems": ["dose-unit", "operator", "event-time", "parcel", "crop-binding"],
            "softItems": ["product-binding"]},
        "advisories": {}}))
    monkeypatch.setattr(config, "EVIDENCE_POLICY_PATH", harder)
    refused = pipeline.commit(_no_crop_binding())
    assert refused["decisionOutcome"] == "RETAIN_DRAFT", \
        "crop-binding HARD in the package policy -> refuse, not route"
    assert refused["problems"][0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"


# ---------------------------------------------------------------------------
# Part B — non-blocking advisory-twin warnings (Step 3; durable record deferred)
# ---------------------------------------------------------------------------

def _broad_product_binding(store, state="VERIFIED"):
    """A CROP_PROTECTION_PRODUCT binding whose mapping is NON-exact (BROAD). When
    VERIFIED it meets the soft product-binding floor yet trips the
    authorisation-mismatch advisory; a non-VERIFIED state is an unresolved
    binding (soft-floor route), which must NOT raise the advisory."""
    bid = f"binding:p5.broad.{uid()}"
    from kernel import context
    with store.tx() as cur:
        store.insert_record(cur, {
            "schemaVersion": "ofarm.agronomicidentitybinding.v0.1",
            "agronomicIdentityBindingId": bid,
            "bindingRole": "CROP_PROTECTION_PRODUCT",
            "bindingState": state,
            "createdAt": context.now_iso(), "createdByPartyRef": demo.FARMER,
            "localSubject": {"subjectType": "PRODUCT_OR_INPUT",
                             "subjectRef": "input:p5.broad"},
            "externalScheme": {"schemeRef": "scheme:si.uvhvvr.ffs-reg",
                               "schemeRole": "CODE_BINDING", "issuerRef": "party:si.uvhvvr",
                               "jurisdiction": "SI", "schemeVersion": "register-day-2026-06-11"},
            "bindingValue": {"capturedLabel": "ACCOUNT", "code": "1646",
                             "registrationRef": "U34330-50/23/16",
                             "mappingRelation": "BROAD"},
            "evidenceRefs": ["trace:demo.regver.account"],
            "referenceSnapshotRefs": [demo.REGSR_SNAPSHOT],
            "promotionBoundary": {
                "highConsequenceUse": "ALLOWED_WHEN_PROFILE_AND_EVIDENCE_PASS",
                "maySupportPromotion": True,
                "mustNotPromoteTo": ["OFARM_CORE_MEANING"]}})
    return bid


def test_clean_claim_raises_no_advisory(store, pipeline):
    r = _spray(pipeline, confirm=True)   # EXACT demo binding, dose 0.3 in [0,100]
    assert r["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert not any("advisory" in t.lower() for t in _problem_titles(r))


def test_authorisation_mismatch_advisory_is_non_blocking(store, pipeline):
    broad = _broad_product_binding(store)
    r = _spray(pipeline, confirm=True, binding_refs=[broad, demo.CROP_BINDING])
    # the advisory NEVER blocks: a floor-meeting claim still promotes
    assert r["decisionOutcome"] == "PROMOTE_ACCEPTED"
    advisories = [p for p in r["problems"] if p["title"] == "Authorisation-mismatch advisory"]
    assert advisories and advisories[0]["severity"] == "WARNING"
    assert "not a compliance fact" in advisories[0]["detail"]


def test_dose_range_advisory_is_non_blocking(store, pipeline):
    r = _spray(pipeline, confirm=True, dose_value=250.0)   # > advisory max 100
    assert r["decisionOutcome"] == "PROMOTE_ACCEPTED"       # dose-unit is resolved; floor met
    advisories = [p for p in r["problems"] if p["title"] == "Dose-range advisory"]
    assert advisories and advisories[0]["severity"] == "WARNING"


def test_advisory_creates_no_consequence_or_compliance_fact(store, pipeline):
    conseq_before = len(store.find_by_kind("ofarm.acceptedeventconsequence.v0.1"))
    r = _spray(pipeline, confirm=True, dose_value=250.0)
    assert r["decisionOutcome"] == "PROMOTE_ACCEPTED"
    # exactly ONE consequence (the operation claim's own); the advisory adds none
    assert len(r["emittedAcceptedConsequenceRefs"]) == 1
    assert r["inForceResultCategory"] == "ACCEPTED_EXECUTED_INTERVENTION_CONSEQUENCE"
    assert len(store.find_by_kind("ofarm.acceptedeventconsequence.v0.1")) == conseq_before + 1
    # the advisory is a WARNING problem, never a COMPLIANCE_FACT consequence
    adv = [p for p in r["problems"] if p["title"] == "Dose-range advisory"][0]
    assert adv["severity"] == "WARNING"


def test_non_verified_binding_raises_no_authorisation_advisory(store, pipeline):
    # the authorisation-mismatch advisory fires only on a RESOLVED (VERIFIED)
    # product binding; an unresolved (PROVISIONAL) one is a soft-floor route to
    # review, not an advisory (no double-signal)
    prov = _broad_product_binding(store, state="PROVISIONAL")
    r = _spray(pipeline, confirm=True, binding_refs=[prov, demo.CROP_BINDING])
    assert r["decisionOutcome"] == "REQUIRE_REVIEW", "unresolved product binding -> soft route"
    assert not any(t == "Authorisation-mismatch advisory" for t in _problem_titles(r))


def test_malformed_advisories_fails_closed(store, pipeline, monkeypatch, tmp_path):
    # a present-but-non-dict advisories block is malformed -> fail closed at load
    # (the floor path refuses), never crash, never silently proceed
    bad = tmp_path / "null_advisories.json"
    bad.write_text(json.dumps({
        "policyId": "policy:test.bad-advisories",
        "operationFloor": {"hardItems": ["dose-unit"], "softItems": []},
        "advisories": None}))
    monkeypatch.setattr(config, "EVIDENCE_POLICY_PATH", bad)
    r = _spray(pipeline, confirm=True)
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert r["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"


# Durable Advisory-Twin record (PassportView _advisory_flags) is DEFERRED — see
# the module docstring + ERRATA E-006. No passport-durability test here by design.
