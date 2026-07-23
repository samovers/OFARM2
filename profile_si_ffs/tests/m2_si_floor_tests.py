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
from dataclasses import replace

import pytest

from kernel import config, policy, profile_policy, sufficiency
from profile_si_ffs.test_fixtures import demo


OPERATION_FLOOR_CHECKS = {
    "product-binding",
    "dose-unit",
    "parcel",
    "crop-binding",
    "operator",
    "event-time",
}


def uid():
    return uuid.uuid4().hex[:8]


def _spray(pipeline, **kw):
    return _commit_with_test_policy(pipeline, demo.spray_submission(
        f"p5:{uid()}", erp_id=f"erp:p5.{uid()}", **kw))


def _commit_with_test_policy(pipeline, sub):
    services = pipeline.runtime_services
    pipeline.runtime_services = replace(
        services,
        policy_provider=_TestPolicyProvider(services.descriptor),
    )
    try:
        return pipeline.commit(sub)
    finally:
        pipeline.runtime_services = services


class _TestPolicyProvider:
    """Test builder for profile-policy variants; never used by production."""

    def __init__(self, descriptor):
        self.descriptor = descriptor
        self.policy_ref = descriptor.evidence_policy_ref
        self.recognized_rule_refs = frozenset({
            descriptor.evidence_policy_ref,
            descriptor.profile_ref,
            descriptor.pack_ref,
            descriptor.code_binding_profile_ref,
        })

    def evidence_policy(self, supported_checks=None):
        return profile_policy.load_evidence_review_policy(supported_checks)

    def validation_policy(self):
        return profile_policy.validation_policy()


def _problem_titles(result):
    return [p.get("title", "") for p in result.get("problems", [])]


def _case_for_result(store, result):
    trace = store.get_payload(result["promotionTraceRef"])
    return store.get_payload(trace["evidenceSufficiencyCaseRef"])


def _valid_display(items):
    prefix = "rule:test.floor"
    floor_items = {}
    for item in items:
        floor_items[item] = {
            "ruleRef": f"{prefix}.{item}",
            "label": item.replace("-", " "),
        }
    if "product-binding" in floor_items:
        floor_items["product-binding"]["insufficiencyReasonCode"] = \
            "AMBIGUOUS_PRODUCT_ID"
        floor_items["product-binding"]["reviewReasonCode"] = \
            "PRODUCT_BINDING_UNRESOLVED"
    if "crop-binding" in floor_items:
        floor_items["crop-binding"]["reviewReasonCode"] = "IDENTITY_UNRESOLVED"
    return {
        "ruleRefPrefix": prefix,
        "operationFloorClaimStatement": "test profile operation floor statement",
        "operationFloorAllowRationale": "test profile floor satisfied",
        "hardMissingRationaleTemplate": "test hard missing: {missing}",
        "softMissingRationaleTemplate": "test soft missing: {missing}",
        "durableProofBundleLabel": "test durable proof bundle",
        "floorItems": floor_items,
    }


def _valid_validation():
    return {
        "quantityAndUnit": {
            "requireQuantityKindAndUnitCode": True,
            "unresolvedReasonCode": "UNIT_UNRESOLVED",
            "unresolvedTitle": "Dose unit unresolved",
            "unresolvedDetail": "the SI profile requires a UCUM unit code and quantity kind on every dose; unresolved units block promotion (BLOCK_PROMOTION)",
            "unresolvedRationale": "dose without resolved UCUM unit code",
            "implausibleDoseReviewReasonCode": "EVIDENCE_INSUFFICIENT",
            "implausibleDoseTitle": "Implausible dose",
            "implausibleDoseDetailTemplate": "dose value {value} is implausible; advisory flag raised and routed to advisor review, never a silent block",
        },
        "recordFields": {
            "nonWholeExtentBound": {
                "requiredLabel": "size treated",
                "missingReasonCode": "EVIDENCE_INSUFFICIENT",
                "missingTitle": "Partial extent unquantified",
                "missingDetailTemplate": "executionExtent.extentClass is {extentClass} but the carrier states no area, geometryRef, extentRef, or scopeExtentBasisRef; '{requiredLabel}' is a required SI record field, so the claim stays a draft rather than silently materializing as whole-scope (the reason-code registry has no extent-completeness code — see ERRATA E-004)",
                "missingRationale": "non-whole extent carries no quantified bound",
            }
        },
        "bindings": {
            "wrongKindRef": {
                "disposition": "REFUSE",
                "reasonCode": "PRODUCT_BINDING_UNRESOLVED",
                "title": "Binding ref is not a binding",
                "detailTemplate": "agronomicIdentityBindingRefs names {refs}, which do not resolve to AgronomicIdentityBinding records; a binding ref must be a governed binding, never another record kind",
            },
            "product": {
                "bindingRole": "CROP_PROTECTION_PRODUCT",
                "missingOrUnverifiedDisposition": "REVIEW",
                "reasonCode": "PRODUCT_BINDING_UNRESOLVED",
                "title": "Product binding unresolved",
                "detailTemplate": "product binding state is {state}; the record stays committable as a claim, promotion requires review (UNRESOLVED is explicit, never silent)",
            },
            "crop": {
                "bindingRole": "CROP_SPECIES",
                "missingDisposition": "REVIEW",
                "reasonCode": "IDENTITY_UNRESOLVED",
                "title": "Crop binding missing",
                "detail": "no EPPO crop binding is linked; the SI profile routes this to review",
            },
        },
    }


def _policy_doc(hard, soft, *, advisories=None, display=None, validation=None):
    return {
        "policyId": "policy:test.floor",
        "profileRef": "profile:test.floor",
        "operationFloor": {"hardItems": hard, "softItems": soft},
        "display": display or _valid_display([*hard, *soft]),
        "validation": validation or _valid_validation(),
        "advisories": advisories or {},
    }


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


def test_floor_display_metadata_is_sourced_from_package_content():
    display = profile_policy.operation_floor_display(
        supported_checks=OPERATION_FLOOR_CHECKS)
    doc = json.loads(config.EVIDENCE_POLICY_PATH.read_text())
    assert display == doc["display"]
    assert display["ruleRefPrefix"] == "rule:si.ffs.floor"
    assert profile_policy.floor_item_rule_ref(
        display, "product-binding") == "rule:si.ffs.floor.product-binding"


def test_explicit_build_case_from_checks_uses_supplied_policy_ref(store):
    display = _valid_display(["dose-unit"])

    case, _ = sufficiency.build_case_from_checks(
        store,
        demo.FARM,
        "assertion:p5.explicit.policy",
        "erp:p5.explicit.policy",
        {"dose-unit": True},
        ("dose-unit",),
        (),
        [demo.PHOTO_EVIDENCE],
        policy_ref="policy:test.explicit",
        display=display,
    )

    assert case["governingPolicyRefs"] == ["policy:test.explicit"]
    assert {arg["policyRef"] for arg in case["arguments"]} == {
        "policy:test.explicit"}


def test_explicit_floor_case_with_policy_does_not_read_config_floor(
        store, monkeypatch):
    def fail_config_floor(*_args, **_kwargs):
        raise AssertionError("config-backed floor loader was called")

    monkeypatch.setattr(
        profile_policy, "operation_floor_with_display", fail_config_floor)
    display = _valid_display(OPERATION_FLOOR_CHECKS)
    display["operationFloorClaimStatement"] = "explicit supplied floor statement"
    display["operationFloorAllowRationale"] = "explicit supplied floor allow"
    evidence_policy = _policy_doc(
        ["dose-unit", "operator", "event-time", "parcel"],
        ["product-binding", "crop-binding"],
        display=display,
    )
    sub = demo.spray_submission(
        f"p5-explicit-floor:{uid()}",
        erp_id=f"erp:p5.explicit.floor.{uid()}",
        confirm=True,
    )

    case, failures = sufficiency.build_floor_case_with_policy(
        store,
        sub,
        "OPERATION_CLAIM",
        demo.FARM,
        "assertion:p5.explicit.floor",
        "erp:p5.explicit.floor",
        evidence_policy=evidence_policy,
        policy_ref="policy:test.explicit-floor",
    )

    assert failures == []
    assert case["governingPolicyRefs"] == ["policy:test.explicit-floor"]
    assert {arg["policyRef"] for arg in case["arguments"]} == {
        "policy:test.explicit-floor"}
    assert case["claims"][0]["statement"] == "explicit supplied floor statement"
    assert case["outcome"]["rationale"] == "explicit supplied floor allow"


def test_explicit_compliance_floor_omitted_rule_refs_use_policy_ref_only(store):
    evidence_policy = _policy_doc([], [])
    sub = {
        "evidenceRefs": [demo.PHOTO_EVIDENCE],
        "payload": {"complianceClaim": {
            "statement": "fictional explicit compliance rule-ref test",
            "assertedStatus": "CLAIMED_COMPLIANT",
            "governingRuleRefs": [config.EVIDENCE_POLICY_REF],
            "subjectScopeRef": demo.FARM}},
    }

    case, _ = sufficiency.build_floor_case_with_policy(
        store,
        sub,
        "COMPLIANCE_ASSERTION",
        demo.FARM,
        "assertion:p5.explicit.compliance",
        None,
        evidence_policy=evidence_policy,
        policy_ref="policy:test.explicit-only",
    )

    governing = [
        arg for arg in case["arguments"]
        if arg["argumentId"].endswith(":governing-rules")
    ][0]
    assert governing["conclusion"] == "UNSUPPORTED"
    assert case["outcome"]["decision"] == "REFUSE"


def test_kernel_carries_no_si_floor_constants():
    # acceptance: kernel/ holds no SI-specific floor values after the move
    assert not hasattr(policy, "OPERATION_FLOOR_HARD_ITEMS")
    assert not hasattr(policy, "OPERATION_FLOOR_SOFT_ITEMS")


def test_clean_operation_claim_still_promotes(store, pipeline):
    # existing promotion behavior is unchanged for a clean claim
    assert _spray(pipeline, confirm=True)["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_clean_operation_claim_uses_profile_display_metadata(store, pipeline):
    display = profile_policy.operation_floor_display(
        supported_checks=OPERATION_FLOOR_CHECKS)
    r = _spray(pipeline, confirm=True)
    assert r["decisionOutcome"] == "PROMOTE_ACCEPTED"
    case = _case_for_result(store, r)
    assert case["claims"][0]["statement"] == \
        display["operationFloorClaimStatement"]
    assert case["outcome"]["rationale"] == \
        display["operationFloorAllowRationale"]
    refs = {a["ruleRef"] for a in case["arguments"]}
    assert "rule:si.ffs.floor.product-binding" in refs
    assert refs == {profile_policy.floor_item_rule_ref(display, item)
                    for item in OPERATION_FLOOR_CHECKS}


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


def test_missing_display_metadata_fails_closed(store, pipeline, monkeypatch, tmp_path):
    bad = tmp_path / "missing_display.json"
    bad.write_text(json.dumps({
        "policyId": "policy:test.missing-display",
        "operationFloor": {"hardItems": ["dose-unit"], "softItems": []},
        "advisories": {}}))
    monkeypatch.setattr(config, "EVIDENCE_POLICY_PATH", bad)
    r = _spray(pipeline, confirm=True)
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert r["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"


@pytest.mark.parametrize("variant", [
    "bad-template-field",
    "missing-floor-item",
    "extra-floor-item",
    "bad-prefix-grammar",
    "bad-rule-ref-scope",
    "bad-rule-ref-grammar",
    "bad-insufficiency-code",
    "bad-review-code",
], ids=[
    "bad-template-field",
    "missing-floor-item",
    "extra-floor-item",
    "bad-prefix-grammar",
    "bad-rule-ref-scope",
    "bad-rule-ref-grammar",
    "bad-insufficiency-code",
    "bad-review-code",
])
def test_malformed_display_metadata_fails_closed(
        store, pipeline, monkeypatch, tmp_path, variant):
    hard = ["dose-unit", "operator", "event-time", "parcel"]
    soft = ["product-binding", "crop-binding"]
    doc = _policy_doc(hard, soft)
    display = doc["display"]
    if variant == "bad-template-field":
        display["hardMissingRationaleTemplate"] = "missing {unknown}"
    elif variant == "missing-floor-item":
        display["floorItems"].pop("dose-unit")
    elif variant == "extra-floor-item":
        display["floorItems"]["banana"] = {
            "ruleRef": "rule:test.floor.banana",
            "label": "banana",
        }
    elif variant == "bad-prefix-grammar":
        display["ruleRefPrefix"] = "rule:test floor"
        for item, block in display["floorItems"].items():
            block["ruleRef"] = f"rule:test floor.{item}"
    elif variant == "bad-rule-ref-scope":
        display["floorItems"]["dose-unit"]["ruleRef"] = "rule:other.floor.dose-unit"
    elif variant == "bad-rule-ref-grammar":
        display["floorItems"]["dose-unit"]["ruleRef"] = "rule:test.floor.bad ref"
    elif variant == "bad-insufficiency-code":
        display["floorItems"]["product-binding"]["insufficiencyReasonCode"] = \
            "NOT_A_CASE_CODE"
    elif variant == "bad-review-code":
        display["floorItems"]["product-binding"]["reviewReasonCode"] = \
            "NOT_A_RUNTIME_CODE"
    bad = tmp_path / "bad_display.json"
    bad.write_text(json.dumps(doc))
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

    default = _commit_with_test_policy(pipeline, _no_crop_binding())
    assert default["decisionOutcome"] == "REQUIRE_REVIEW", \
        "crop-binding SOFT by default -> route to review"

    harder = tmp_path / "crop_hard_policy.json"
    harder.write_text(json.dumps({
        "policyId": "policy:test.crop-hard",
        "profileRef": "profile:test.crop-hard",
        "operationFloor": {
            "hardItems": ["dose-unit", "operator", "event-time", "parcel", "crop-binding"],
            "softItems": ["product-binding"]},
        "display": _valid_display(["dose-unit", "operator", "event-time", "parcel",
                                   "crop-binding", "product-binding"]),
        "validation": _valid_validation(),
        "advisories": {}}))
    monkeypatch.setattr(config, "EVIDENCE_POLICY_PATH", harder)
    refused = _commit_with_test_policy(pipeline, _no_crop_binding())
    assert refused["decisionOutcome"] == "RETAIN_DRAFT", \
        "crop-binding HARD in the package policy -> refuse, not route"
    assert refused["problems"][0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"


def test_display_metadata_changes_case_text_without_changing_decision(
        store, pipeline, monkeypatch, tmp_path):
    hard = ["dose-unit", "operator", "event-time", "parcel"]
    soft = ["product-binding", "crop-binding"]
    display = _valid_display([*hard, *soft])
    display["operationFloorClaimStatement"] = "custom profile-owned floor statement"
    display["operationFloorAllowRationale"] = "custom profile-owned allow rationale"
    doc = _policy_doc(hard, soft, display=display)
    path = tmp_path / "custom_display.json"
    path.write_text(json.dumps(doc))
    monkeypatch.setattr(config, "EVIDENCE_POLICY_PATH", path)

    r = _spray(pipeline, confirm=True)
    assert r["decisionOutcome"] == "PROMOTE_ACCEPTED"
    case = _case_for_result(store, r)
    assert case["claims"][0]["statement"] == "custom profile-owned floor statement"
    assert case["outcome"]["rationale"] == "custom profile-owned allow rationale"
    assert {a["ruleRef"] for a in case["arguments"]} == {
        profile_policy.floor_item_rule_ref(display, item)
        for item in OPERATION_FLOOR_CHECKS}


def test_compliance_assertion_fallback_rule_refs_remain_unchanged(store, pipeline):
    statement = "fictional demo: compliance fallback trace regression"
    r = pipeline.commit({
        "commitClass": "COMPLIANCE_ASSERTION",
        "actingPartyRef": demo.FARMER,
        "farmRef": demo.FARM,
        "idempotencyKey": f"p5-compliance-fallback:{uid()}",
        "eventTime": "2026-06-10T09:00:00Z",
        "evidenceRefs": [demo.PHOTO_EVIDENCE],
        "payload": {"complianceClaim": {
            "statement": statement,
            "assertedStatus": "CLAIMED_COMPLIANT",
            "governingRuleRefs": [config.EVIDENCE_POLICY_REF],
            "subjectScopeRef": demo.FARM}},
        "confirmAccept": True,
    })
    assert r["decisionOutcome"] == "REQUIRE_REVIEW"
    case = _case_for_result(store, r)
    assert case["claims"][0]["statement"] == statement
    assert {a["ruleRef"] for a in case["arguments"]} == {
        "rule:si.ffs.floor.claim-statement",
        "rule:si.ffs.floor.asserted-status",
        "rule:si.ffs.floor.governing-rules",
        "rule:si.ffs.floor.subject-resolves",
        "rule:si.ffs.floor.evidence-bundle",
    }


def test_queue_acceptance_fallback_outputs_remain_unchanged(store, pipeline):
    queued = pipeline.commit(demo.spray_submission(
        f"p5-acceptance-fallback:{uid()}", erp_id=f"erp:p5.accept.{uid()}",
        confirm=False))
    assert queued["decisionOutcome"] == "RETAIN_DRAFT"
    accepted = pipeline.commit({
        "commitClass": "GOVERNANCE_DECISION",
        "actingPartyRef": demo.FARMER,
        "farmRef": demo.FARM,
        "idempotencyKey": f"p5-acceptance-review:{uid()}",
        "decisionTime": "2026-06-10T10:00:00Z",
        "reviewTargetAssertionRef": queued["emittedAssertionRecordRefs"][0],
        "reviewRationale": "self-review of a routine operation claim meeting the floor",
    })
    assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED"
    case = _case_for_result(store, accepted)
    assert case["claims"][0]["statement"] == \
        "this operation claim meets the SI record-keeping evidence floor"
    assert case["outcome"]["rationale"] == "all SI evidence-floor items satisfied"
    assert {a["ruleRef"] for a in case["arguments"]} == {
        "rule:si.ffs.floor.durable-evidence",
        "rule:si.ffs.floor.route-reasons-resolved",
    }


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


def test_explicit_operation_advisories_with_policy_does_not_read_config(
        store, monkeypatch):
    def fail_config_advisories():
        raise AssertionError("config-backed advisory loader was called")

    monkeypatch.setattr(profile_policy, "advisory_rules", fail_config_advisories)
    broad = _broad_product_binding(store)
    sub = demo.spray_submission(
        f"p5-explicit-advisory:{uid()}",
        erp_id=f"erp:p5.explicit.advisory.{uid()}",
        confirm=True,
        binding_refs=[broad, demo.CROP_BINDING],
    )
    evidence_policy = _policy_doc(
        ["dose-unit", "operator", "event-time", "parcel"],
        ["product-binding", "crop-binding"],
        advisories={
            "authorisationMismatch": {
                "enabled": True,
                "exactMappingRequired": True,
            }
        },
    )

    problems = sufficiency.operation_advisories_with_policy(
        store, sub, evidence_policy)

    assert any(p["title"] == "Authorisation-mismatch advisory"
               for p in problems)


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
        "profileRef": "profile:test.bad-advisories",
        "operationFloor": {"hardItems": ["dose-unit"], "softItems": []},
        "display": _valid_display(["dose-unit"]),
        "validation": _valid_validation(),
        "advisories": None}))
    monkeypatch.setattr(config, "EVIDENCE_POLICY_PATH", bad)
    r = _spray(pipeline, confirm=True)
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert r["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"


@pytest.mark.parametrize("policy_doc", [
    {"operationFloor": {"hardItems": ["banana"], "softItems": []}},
    {"operationFloor": {"hardItems": ["dose-unit"], "softItems": ["dose-unit"]}},
    {"operationFloor": {"hardItems": [42], "softItems": []}},
    _policy_doc(["dose-unit"], [], advisories={"authorisationMismatch": None}),
    _policy_doc(["dose-unit"], [], advisories={"doseRange": {"min": "x"}}),
    _policy_doc(["dose-unit"], [], advisories={"doseRange": {"min": 100, "max": 1}}),
], ids=["unknown-item", "hard-soft-overlap", "non-string-item",
        "null-advisory-block", "non-numeric-dose", "unordered-dose"])
def test_malformed_policy_variants_fail_closed(store, pipeline, monkeypatch, tmp_path, policy_doc):
    # every malformed shape the kernel later indexes/compares fails CLOSED at load
    # (governed PROFILE_NOT_ACTIVE), never a raw KeyError / AttributeError / compare
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(policy_doc))
    monkeypatch.setattr(config, "EVIDENCE_POLICY_PATH", bad)
    r = _spray(pipeline, confirm=True)
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert r["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"


def test_advisory_warning_survives_idempotency_replay(store, pipeline):
    # the result warning is the ONLY implemented advisory surface (durable records
    # deferred, E-006), so a matching replay must carry the advisory forward — not
    # silently drop it for just the replay-info note
    sub = demo.spray_submission(f"p5-replay:{uid()}", erp_id=f"erp:p5.replay.{uid()}",
                                confirm=True, dose_value=250.0)
    first = pipeline.commit(sub)
    assert first["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert "Dose-range advisory" in _problem_titles(first)
    # the SAME submission (same idempotency key + payload digest) -> matching replay
    replay = pipeline.commit(sub)
    assert replay["decisionOutcome"] == "REPLAY_REUSED_RESULT"
    titles = _problem_titles(replay)
    assert "Replay reused earlier result" in titles, "the replay-info note is preserved"
    assert "Dose-range advisory" in titles, "the original advisory survives the replay"


# Durable Advisory-Twin record (PassportView _advisory_flags) is DEFERRED — see
# the module docstring + ERRATA E-006. No passport-durability test here by design.
