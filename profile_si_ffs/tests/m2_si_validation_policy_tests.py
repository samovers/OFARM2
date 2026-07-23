"""D4 — SI validator policy values are profile-owned.

Engineering tests, not named platform conformance. They pin the D4 boundary:
Kernel validators keep gate mechanics and order, while SI-specific validation
values and messages are loaded from profile policy content.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import replace

from kernel import config, profile_policy, validators
from profile_si_ffs.test_fixtures import demo


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
    return _commit_with_test_policy(pipeline, demo.spray_submission(
        f"d4:{uid()}", erp_id=f"erp:d4.{uid()}", **kw))


def _commit_with_test_policy(pipeline, sub):
    services = pipeline.runtime_services
    if isinstance(
        services.policy_provider,
        _ExplicitValidationPolicyProvider,
    ):
        return pipeline.commit(sub)
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

    def __init__(self, descriptor, validation=None):
        self.descriptor = descriptor
        self.policy_ref = descriptor.evidence_policy_ref
        self.recognized_rule_refs = frozenset({
            descriptor.evidence_policy_ref,
            descriptor.profile_ref,
            descriptor.pack_ref,
            descriptor.code_binding_profile_ref,
        })
        self._validation = validation

    def evidence_policy(self, supported_checks=None):
        return profile_policy.load_evidence_review_policy(supported_checks)

    def validation_policy(self):
        if self._validation is not None:
            return self._validation
        return profile_policy.validation_policy()


class _ExplicitValidationPolicyProvider(_TestPolicyProvider):
    def validation_policy(self):
        return self._validation


def _use_explicit_operation_validation(
        pipeline, monkeypatch, validation):
    services = pipeline.runtime_services
    monkeypatch.setattr(
        pipeline,
        "runtime_services",
        replace(
            services,
            policy_provider=_ExplicitValidationPolicyProvider(
                services.descriptor,
                validation,
            ),
        ),
    )


class _FakeValidationContext:
    def __init__(self, store, sub, commit_class="COMPLIANCE_ASSERTION"):
        self.store = store
        self.sub = sub
        self.commit_class = commit_class
        self.farm_ref = demo.FARM
        self.gate_sequence = []

    def log(self, gate, outcome, *, reason_code=None, rationale=None, refs=None):
        self.gate_sequence.append({
            "gate": gate,
            "outcome": outcome,
            "reasonCode": reason_code,
            "rationale": rationale,
            "relatedArtifactRefs": refs,
        })


def test_validation_policy_is_sourced_from_package_content():
    doc = _policy_doc()
    validation = profile_policy.validation_policy()
    assert validation == doc["validation"]
    assert validation["quantityAndUnit"]["unresolvedReasonCode"] == "UNIT_UNRESOLVED"
    assert validation["bindings"]["product"]["bindingRole"] == \
        "CROP_PROTECTION_PRODUCT"


def test_explicit_descriptor_policy_loader_matches_config_wrapper():
    explicit = profile_policy.load_evidence_review_policy_for_descriptor(
        config.ACTIVE_PROFILE)
    implicit = profile_policy.load_evidence_review_policy()

    assert explicit == implicit == _policy_doc()


def test_descriptor_backed_policy_helpers_match_config_wrappers():
    active = config.ACTIVE_PROFILE

    assert profile_policy.validation_policy_for_descriptor(active) == \
        profile_policy.validation_policy()
    assert profile_policy.operation_floor_for_descriptor(active) == \
        profile_policy.operation_floor()
    assert profile_policy.operation_floor_with_display_for_descriptor(active) == \
        profile_policy.operation_floor_with_display()
    assert profile_policy.operation_floor_display_for_descriptor(active) == \
        profile_policy.operation_floor_display()
    assert profile_policy.advisory_rules_for_descriptor(active) == \
        profile_policy.advisory_rules()


def test_explicit_policy_path_rejects_symlink_escape(tmp_path):
    profile_root = tmp_path / "profile_si_ffs"
    profile_root.mkdir()
    outside_policy = tmp_path / "outside_policy.json"
    outside_policy.write_text(json.dumps(_policy_doc()))
    link = profile_root / "policy_link.json"
    link.symlink_to(outside_policy)

    try:
        profile_policy.load_evidence_review_policy_from_path(
            link,
            profile_root=profile_root,
        )
    except profile_policy.ProfilePolicyError as exc:
        assert "escapes the active profile root" in str(exc)
    else:
        raise AssertionError("symlinked policy escape was accepted")


def test_descriptor_policy_loader_rejects_policy_id_mismatch(tmp_path):
    doc = _policy_doc()
    doc["policyId"] = "policy:test.mismatched"
    path = tmp_path / "evidence_review_policy_v0_1.json"
    path.write_text(json.dumps(doc))
    descriptor = replace(
        config.ACTIVE_PROFILE,
        profile_root=tmp_path,
        evidence_policy_path=path,
    )

    try:
        profile_policy.load_evidence_review_policy_for_descriptor(descriptor)
    except profile_policy.ProfilePolicyError as exc:
        assert "does not match expected policy ref" in str(exc)
    else:
        raise AssertionError("mismatched descriptor policy id was accepted")


def test_explicit_policy_path_preserves_unsupported_floor_item_validation(tmp_path):
    doc = _policy_doc()
    doc["operationFloor"]["hardItems"] = [
        *doc["operationFloor"]["hardItems"],
        "unsupported-floor-item",
    ]
    display_items = doc["display"]["floorItems"]
    display_items["unsupported-floor-item"] = {
        "label": "Unsupported floor item",
        "ruleRef": "rule:si.ffs.floor.unsupported-floor-item",
    }
    path = tmp_path / "unsupported_floor_item.json"
    path.write_text(json.dumps(doc))

    try:
        profile_policy.load_evidence_review_policy_from_path(
            path,
            supported_checks={"dose-unit"},
        )
    except profile_policy.ProfilePolicyError as exc:
        assert "unsupported floor item" in str(exc)
    else:
        raise AssertionError("unsupported floor item was accepted")


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


def test_explicit_validator_policy_injection_uses_supplied_subdocument(
        pipeline, monkeypatch):
    validation = _policy_doc()["validation"]
    validation["quantityAndUnit"]["unresolvedTitle"] = \
        "Explicit dose unit unresolved"
    validation["quantityAndUnit"]["unresolvedDetail"] = \
        "explicit unresolved dose detail"
    validation["recordFields"]["nonWholeExtentBound"]["missingTitle"] = \
        "Explicit extent bound missing"
    validation["recordFields"]["nonWholeExtentBound"]["requiredLabel"] = \
        "explicit treated area"
    validation["bindings"]["product"]["title"] = \
        "Explicit product binding review"
    validation["bindings"]["product"]["detailTemplate"] = \
        "explicit product state: {state}"
    _use_explicit_operation_validation(pipeline, monkeypatch, validation)

    def fail_config_policy():
        raise profile_policy.ProfilePolicyError(
            "config-backed validation policy was called")

    monkeypatch.setattr(profile_policy, "validation_policy", fail_config_policy)

    bad_unit = _spray(pipeline, confirm=True, unit_ref="scheme:bad:L")
    assert bad_unit["decisionOutcome"] == "RETAIN_DRAFT"
    assert bad_unit["problems"][0]["title"] == "Explicit dose unit unresolved"

    partial = demo.spray_submission(
        f"d4-explicit-extent:{uid()}",
        erp_id=f"erp:d4.explicit.extent.{uid()}",
    )
    partial["payload"]["executionExtent"] = {
        "extentClass": "PARTIAL_TARGET_SCOPE",
        "targetScope": {"scopeType": "FIELD", "scopeRef": demo.FIELD},
        "extentBasisStatus": "OPERATOR_SKETCH",
    }
    extent = _commit_with_test_policy(pipeline, partial)
    assert extent["decisionOutcome"] == "RETAIN_DRAFT"
    assert extent["problems"][0]["title"] == "Explicit extent bound missing"
    assert "explicit treated area" in extent["problems"][0]["detail"]

    missing_product = _spray(
        pipeline,
        confirm=True,
        binding_refs=[demo.CROP_BINDING],
    )
    assert missing_product["decisionOutcome"] == "REQUIRE_REVIEW"
    assert any(p["title"] == "Explicit product binding review"
               and p["detail"] == "explicit product state: MISSING"
               for p in missing_product["problems"])


def test_malformed_explicit_validator_policy_fails_closed(
        pipeline, monkeypatch):
    _use_explicit_operation_validation(pipeline, monkeypatch, None)

    r = _spray(pipeline, confirm=True)

    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    problem = r["problems"][0]
    assert problem["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert "explicit validation policy must be a JSON object" in problem["detail"]


def test_full_evidence_policy_doc_as_validator_policy_fails_closed(
        pipeline, monkeypatch):
    _use_explicit_operation_validation(pipeline, monkeypatch, _policy_doc())

    r = _spray(pipeline, confirm=True)

    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    problem = r["problems"][0]
    assert problem["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert "quantityAndUnit" in problem["detail"]


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
    r = _commit_with_test_policy(pipeline, sub)
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    problem = r["problems"][0]
    assert problem["reasonCode"] == "EVIDENCE_INSUFFICIENT"
    assert problem["title"] == "Custom extent bound missing"
    assert "custom treated area" in problem["detail"]


def test_compliance_validator_empty_recognized_refs_does_not_fallback(store):
    sub = {"payload": {"complianceClaim": {
        "statement": "fictional explicit empty recognized-rule set test",
        "assertedStatus": "CLAIMED_COMPLIANT",
        "governingRuleRefs": [config.EVIDENCE_POLICY_REF],
        "subjectScopeRef": demo.FARM,
    }}}
    ctx = _FakeValidationContext(store, sub)

    refusal = validators.ComplianceClaimValidator(
        recognized_rule_refs=set()).run(ctx)

    assert refusal is not None
    assert refusal.problems[0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"
    assert "unknown" in refusal.problems[0]["detail"]


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


def test_wrong_kind_binding_ref_review_disposition_fails_closed(
        pipeline, monkeypatch, tmp_path):
    doc = _policy_doc()
    doc["validation"]["bindings"]["wrongKindRef"]["disposition"] = "REVIEW"
    _use_policy(monkeypatch, tmp_path, doc)

    r = _spray(pipeline, confirm=True, binding_refs=[demo.PHOTO_EVIDENCE])
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    problem = r["problems"][0]
    assert problem["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert "wrongKindRef.disposition must be REFUSE" in problem["detail"]


def test_product_binding_role_must_stay_product_specific(
        pipeline, monkeypatch, tmp_path):
    doc = _policy_doc()
    doc["validation"]["bindings"]["product"]["bindingRole"] = "CROP_SPECIES"
    _use_policy(monkeypatch, tmp_path, doc)

    r = _spray(pipeline, confirm=True)
    problem = r["problems"][0]
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert problem["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert "product.bindingRole must be CROP_PROTECTION_PRODUCT" in problem["detail"]


def test_crop_binding_role_must_stay_crop_specific(
        pipeline, monkeypatch, tmp_path):
    doc = _policy_doc()
    doc["validation"]["bindings"]["crop"]["bindingRole"] = "CROP_PROTECTION_PRODUCT"
    _use_policy(monkeypatch, tmp_path, doc)

    r = _spray(pipeline, confirm=True)
    problem = r["problems"][0]
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert problem["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert "crop.bindingRole must be CROP_SPECIES" in problem["detail"]


def test_unknown_validation_policy_key_fails_closed(
        pipeline, monkeypatch, tmp_path):
    doc = _policy_doc()
    doc["validation"]["quantityAndUnit"]["extraSofteningKey"] = True
    _use_policy(monkeypatch, tmp_path, doc)

    r = _spray(pipeline, confirm=True)
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    problem = r["problems"][0]
    assert problem["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert "unsupported key" in problem["detail"]


def test_malformed_validation_policy_fails_closed(pipeline, monkeypatch, tmp_path):
    doc = _policy_doc()
    doc["validation"]["quantityAndUnit"]["unresolvedReasonCode"] = \
        "NOT_A_REGISTERED_CODE"
    _use_policy(monkeypatch, tmp_path, doc)

    r = _spray(pipeline, confirm=True)
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert r["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
