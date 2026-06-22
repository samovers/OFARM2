"""D4 — SI validator policy values are profile-owned.

Engineering tests, not named platform conformance. They pin the D4 boundary:
Kernel validators keep gate mechanics and order, while SI-specific validation
values and messages are loaded from profile policy content.
"""
from __future__ import annotations

import json
import uuid

from kernel import config, demo, profile_policy


def uid():
    return uuid.uuid4().hex[:8]


def _policy_doc():
    return json.loads(config.EVIDENCE_POLICY_PATH.read_text())


def _use_policy(monkeypatch, tmp_path, doc):
    path = tmp_path / f"validation_policy_{uid()}.json"
    path.write_text(json.dumps(doc))
    monkeypatch.setattr(config, "EVIDENCE_POLICY_PATH", path)
    return path


def _spray(pipeline, **kw):
    return pipeline.commit(demo.spray_submission(
        f"d4:{uid()}", erp_id=f"erp:d4.{uid()}", **kw))


def test_validation_policy_is_sourced_from_package_content():
    doc = _policy_doc()
    validation = profile_policy.validation_policy()
    assert validation == doc["validation"]
    assert validation["quantityAndUnit"]["unresolvedReasonCode"] == "UNIT_UNRESOLVED"
    assert validation["bindings"]["product"]["bindingRole"] == \
        "CROP_PROTECTION_PRODUCT"


def test_unresolved_dose_unit_uses_profile_validation_policy(
        pipeline, monkeypatch, tmp_path):
    doc = _policy_doc()
    quantity = doc["validation"]["quantityAndUnit"]
    quantity["unresolvedTitle"] = "Custom dose unit unresolved"
    quantity["unresolvedDetail"] = "custom unresolved dose detail"
    quantity["unresolvedRationale"] = "custom unresolved dose rationale"
    _use_policy(monkeypatch, tmp_path, doc)

    r = _spray(pipeline, confirm=True, unit_ref="scheme:bad:L")
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    problem = r["problems"][0]
    assert problem["reasonCode"] == "UNIT_UNRESOLVED"
    assert problem["title"] == "Custom dose unit unresolved"
    assert problem["detail"] == "custom unresolved dose detail"


def test_non_whole_extent_missing_bound_uses_profile_validation_policy(
        pipeline, monkeypatch, tmp_path):
    doc = _policy_doc()
    extent_policy = doc["validation"]["recordFields"]["nonWholeExtentBound"]
    extent_policy["missingTitle"] = "Custom extent bound missing"
    extent_policy["requiredLabel"] = "custom treated area"
    extent_policy["missingRationale"] = "custom extent rationale"
    _use_policy(monkeypatch, tmp_path, doc)

    sub = demo.spray_submission(f"d4-extent:{uid()}", erp_id=f"erp:d4.extent.{uid()}")
    sub["payload"]["executionExtent"] = {
        "extentClass": "PARTIAL_TARGET_SCOPE",
        "targetScope": {"scopeType": "FIELD", "scopeRef": demo.FIELD},
        "extentBasisStatus": "OPERATOR_SKETCH",
    }
    r = pipeline.commit(sub)
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    problem = r["problems"][0]
    assert problem["reasonCode"] == "EVIDENCE_INSUFFICIENT"
    assert problem["title"] == "Custom extent bound missing"
    assert "custom treated area" in problem["detail"]


def test_product_binding_review_uses_profile_validation_policy(
        pipeline, monkeypatch, tmp_path):
    doc = _policy_doc()
    product = doc["validation"]["bindings"]["product"]
    product["title"] = "Custom product binding review"
    product["detailTemplate"] = "custom product state: {state}"
    _use_policy(monkeypatch, tmp_path, doc)

    r = _spray(pipeline, confirm=True, binding_refs=[demo.CROP_BINDING])
    assert r["decisionOutcome"] == "REQUIRE_REVIEW"
    assert any(p["reasonCode"] == "PRODUCT_BINDING_UNRESOLVED"
               and p["title"] == "Custom product binding review"
               and p["detail"] == "custom product state: MISSING"
               for p in r["problems"])


def test_wrong_kind_binding_ref_uses_profile_validation_policy(
        pipeline, monkeypatch, tmp_path):
    doc = _policy_doc()
    wrong = doc["validation"]["bindings"]["wrongKindRef"]
    wrong["title"] = "Custom wrong-kind binding ref"
    wrong["detailTemplate"] = "custom wrong-kind refs: {refs}"
    _use_policy(monkeypatch, tmp_path, doc)

    r = _spray(pipeline, confirm=True, binding_refs=[demo.PHOTO_EVIDENCE])
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    problem = r["problems"][0]
    assert problem["reasonCode"] == "PRODUCT_BINDING_UNRESOLVED"
    assert problem["title"] == "Custom wrong-kind binding ref"
    assert "evidence:demo.spray.photo.1" in problem["detail"]


def test_malformed_validation_policy_fails_closed(pipeline, monkeypatch, tmp_path):
    doc = _policy_doc()
    doc["validation"]["quantityAndUnit"]["unresolvedReasonCode"] = \
        "NOT_A_REGISTERED_CODE"
    _use_policy(monkeypatch, tmp_path, doc)

    r = _spray(pipeline, confirm=True)
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert r["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
