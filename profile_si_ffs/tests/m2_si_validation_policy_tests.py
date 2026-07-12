"""D4 — SI validator policy values are profile-owned.

Engineering tests, not named platform conformance. They pin the D4 boundary:
Kernel validators keep gate mechanics and order, while SI-specific validation
values and messages are loaded from profile policy content.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import replace

import pytest

from kernel import config, profile_policy, validators
from kernel.contracts import canonical_json
from kernel.runtime_bundle import sha256_bytes
from profile_si_ffs.test_fixtures import demo


def uid():
    return uuid.uuid4().hex[:8]


def _policy_doc():
    return json.loads(config.EVIDENCE_POLICY_PATH.read_text())


def _runtime_bundle_with_policy(base, doc):
    """Return an audit bundle whose retained policy bytes are ``doc``.

    Governed pipelines seal their policy provider at construction. Policy
    variants therefore have to exist before provider construction; mutating a
    config path or the module-level validator sequence afterwards is not a
    valid runtime seam.
    """
    canonical = canonical_json(doc).encode("utf-8")
    original = base.component("PROFILE_POLICY", base.descriptor.evidence_policy_ref)
    replacement = replace(
        original,
        canonical_bytes=canonical,
        content_digest=sha256_bytes(canonical),
    )
    components = tuple(
        replacement if item is original else item
        for item in base.components
    )
    document = json.loads(base.canonical_document_bytes)
    document["components"] = [item.identity_document() for item in components]
    canonical_document = canonical_json(document).encode("utf-8")
    digest = sha256_bytes(canonical_document)
    return replace(
        base,
        digest=digest,
        bundle_ref=f"runtimebundle:{digest}",
        canonical_document_bytes=canonical_document,
        components=components,
        construction_mode="PERSISTED_AUDIT",
        _selection_environment_seal=None,
    )


def _policy_provider(pipeline, doc):
    bundle = _runtime_bundle_with_policy(pipeline.runtime_bundle, doc)
    return profile_policy.DescriptorPolicyProvider(
        pipeline.active_profile,
        runtime_bundle=bundle,
    )


class _FakeValidationContext:
    def __init__(self, store, sub, commit_class="OPERATION_CLAIM"):
        self.store = store
        self.sub = sub
        self.commit_class = commit_class
        self.farm_ref = demo.FARM
        self.gate_sequence = []
        self.review_route_reasons = []

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
        pipeline):
    doc = _policy_doc()
    quantity = doc["validation"]["quantityAndUnit"]
    quantity["unresolvedTitle"] = "Custom dose unit unresolved"
    quantity["unresolvedDetail"] = "custom unresolved dose detail"
    quantity["unresolvedRationale"] = "custom unresolved dose rationale"
    validation = _policy_provider(pipeline, doc).validation_policy()

    sub = demo.spray_submission(
        f"d4:{uid()}", erp_id=f"erp:d4.{uid()}",
        confirm=True, unit_ref="scheme:bad:L")
    ctx = _FakeValidationContext(pipeline.store, sub)
    refusal = validators.CarrierSemanticsValidator(validation).run(ctx)

    assert refusal is not None
    problem = refusal.problems[0]
    assert problem["reasonCode"] == "UNIT_UNRESOLVED"
    assert problem["title"] == "Custom dose unit unresolved"
    assert problem["detail"] == "custom unresolved dose detail"


def test_explicit_validator_policy_injection_uses_supplied_subdocument(
        pipeline):
    doc = _policy_doc()
    doc["validation"]["quantityAndUnit"]["unresolvedTitle"] = \
        "Explicit dose unit unresolved"
    doc["validation"]["quantityAndUnit"]["unresolvedDetail"] = \
        "explicit unresolved dose detail"
    doc["validation"]["recordFields"]["nonWholeExtentBound"]["missingTitle"] = \
        "Explicit extent bound missing"
    doc["validation"]["recordFields"]["nonWholeExtentBound"]["requiredLabel"] = \
        "explicit treated area"
    doc["validation"]["bindings"]["product"]["title"] = \
        "Explicit product binding review"
    doc["validation"]["bindings"]["product"]["detailTemplate"] = \
        "explicit product state: {state}"
    validation = _policy_provider(pipeline, doc).validation_policy()

    bad_unit = demo.spray_submission(
        f"d4-explicit-unit:{uid()}",
        erp_id=f"erp:d4.explicit.unit.{uid()}",
        confirm=True,
        unit_ref="scheme:bad:L",
    )
    unit_ctx = _FakeValidationContext(pipeline.store, bad_unit)
    unit_refusal = validators.CarrierSemanticsValidator(validation).run(unit_ctx)
    assert unit_refusal is not None
    assert unit_refusal.problems[0]["title"] == "Explicit dose unit unresolved"

    partial = demo.spray_submission(
        f"d4-explicit-extent:{uid()}",
        erp_id=f"erp:d4.explicit.extent.{uid()}",
    )
    partial["payload"]["executionExtent"] = {
        "extentClass": "PARTIAL_TARGET_SCOPE",
        "targetScope": {"scopeType": "FIELD", "scopeRef": demo.FIELD},
        "extentBasisStatus": "OPERATOR_SKETCH",
    }
    extent_ctx = _FakeValidationContext(pipeline.store, partial)
    extent_refusal = validators.ExecutionExtentValidator(validation).run(extent_ctx)
    assert extent_refusal is not None
    assert extent_refusal.problems[0]["title"] == "Explicit extent bound missing"
    assert "explicit treated area" in extent_refusal.problems[0]["detail"]

    missing_product = demo.spray_submission(
        f"d4-explicit-product:{uid()}",
        erp_id=f"erp:d4.explicit.product.{uid()}",
        confirm=True,
        binding_refs=[demo.CROP_BINDING],
    )
    product_ctx = _FakeValidationContext(pipeline.store, missing_product)
    assert validators.CodeBindingValidator(validation).run(product_ctx) is None
    assert any(p["title"] == "Explicit product binding review"
               and p["detail"] == "explicit product state: MISSING"
               for p in product_ctx.review_route_reasons)


def test_malformed_explicit_validator_policy_fails_closed(
        store):
    ctx = _FakeValidationContext(store, demo.spray_submission(
        f"d4-explicit-malformed:{uid()}",
        erp_id=f"erp:d4.explicit.malformed.{uid()}",
        confirm=True,
    ))

    refusal = validators.CarrierSemanticsValidator(None).run(ctx)

    assert refusal is not None
    problem = refusal.problems[0]
    assert problem["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert "explicit validation policy must be a JSON object" in problem["detail"]


def test_full_evidence_policy_doc_as_validator_policy_fails_closed(
        store):
    ctx = _FakeValidationContext(store, demo.spray_submission(
        f"d4-explicit-full-doc:{uid()}",
        erp_id=f"erp:d4.explicit.full-doc.{uid()}",
        confirm=True,
    ))

    refusal = validators.CarrierSemanticsValidator(_policy_doc()).run(ctx)

    assert refusal is not None
    problem = refusal.problems[0]
    assert problem["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert "quantityAndUnit" in problem["detail"]


def test_non_whole_extent_missing_bound_uses_profile_validation_policy(
        pipeline):
    doc = _policy_doc()
    extent_policy = doc["validation"]["recordFields"]["nonWholeExtentBound"]
    extent_policy["missingTitle"] = "Custom extent bound missing"
    extent_policy["requiredLabel"] = "custom treated area"
    extent_policy["missingRationale"] = "custom extent rationale"
    validation = _policy_provider(pipeline, doc).validation_policy()

    sub = demo.spray_submission(f"d4-extent:{uid()}", erp_id=f"erp:d4.extent.{uid()}")
    sub["payload"]["executionExtent"] = {
        "extentClass": "PARTIAL_TARGET_SCOPE",
        "targetScope": {"scopeType": "FIELD", "scopeRef": demo.FIELD},
        "extentBasisStatus": "OPERATOR_SKETCH",
    }
    ctx = _FakeValidationContext(pipeline.store, sub)
    refusal = validators.ExecutionExtentValidator(validation).run(ctx)

    assert refusal is not None
    problem = refusal.problems[0]
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
    ctx = _FakeValidationContext(
        store, sub, commit_class="COMPLIANCE_ASSERTION")

    refusal = validators.ComplianceClaimValidator(
        recognized_rule_refs=set()).run(ctx)

    assert refusal is not None
    assert refusal.problems[0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"
    assert "unknown" in refusal.problems[0]["detail"]


def test_product_binding_review_uses_profile_validation_policy(
        pipeline):
    doc = _policy_doc()
    product = doc["validation"]["bindings"]["product"]
    product["title"] = "Custom product binding review"
    product["detailTemplate"] = "custom product state: {state}"
    validation = _policy_provider(pipeline, doc).validation_policy()

    sub = demo.spray_submission(
        f"d4-product:{uid()}", erp_id=f"erp:d4.product.{uid()}",
        confirm=True, binding_refs=[demo.CROP_BINDING])
    ctx = _FakeValidationContext(pipeline.store, sub)
    assert validators.CodeBindingValidator(validation).run(ctx) is None
    assert any(p["reasonCode"] == "PRODUCT_BINDING_UNRESOLVED"
               and p["title"] == "Custom product binding review"
               and p["detail"] == "custom product state: MISSING"
               for p in ctx.review_route_reasons)


def test_wrong_kind_binding_ref_uses_profile_validation_policy(
        pipeline):
    doc = _policy_doc()
    wrong = doc["validation"]["bindings"]["wrongKindRef"]
    wrong["title"] = "Custom wrong-kind binding ref"
    wrong["detailTemplate"] = "custom wrong-kind refs: {refs}"
    validation = _policy_provider(pipeline, doc).validation_policy()

    sub = demo.spray_submission(
        f"d4-wrong-kind:{uid()}", erp_id=f"erp:d4.wrong-kind.{uid()}",
        confirm=True, binding_refs=[demo.PHOTO_EVIDENCE])
    ctx = _FakeValidationContext(pipeline.store, sub)
    refusal = validators.CodeBindingValidator(validation).run(ctx)

    assert refusal is not None
    problem = refusal.problems[0]
    assert problem["reasonCode"] == "PRODUCT_BINDING_UNRESOLVED"
    assert problem["title"] == "Custom wrong-kind binding ref"
    assert "evidence:demo.spray.photo.1" in problem["detail"]


def test_wrong_kind_binding_ref_review_disposition_fails_closed(
        pipeline):
    doc = _policy_doc()
    doc["validation"]["bindings"]["wrongKindRef"]["disposition"] = "REVIEW"

    with pytest.raises(profile_policy.ProfilePolicyError,
                       match="wrongKindRef.disposition must be REFUSE"):
        _policy_provider(pipeline, doc).validation_policy()


def test_product_binding_role_must_stay_product_specific(
        pipeline):
    doc = _policy_doc()
    doc["validation"]["bindings"]["product"]["bindingRole"] = "CROP_SPECIES"

    with pytest.raises(profile_policy.ProfilePolicyError,
                       match="product.bindingRole must be CROP_PROTECTION_PRODUCT"):
        _policy_provider(pipeline, doc).validation_policy()


def test_crop_binding_role_must_stay_crop_specific(
        pipeline):
    doc = _policy_doc()
    doc["validation"]["bindings"]["crop"]["bindingRole"] = "CROP_PROTECTION_PRODUCT"

    with pytest.raises(profile_policy.ProfilePolicyError,
                       match="crop.bindingRole must be CROP_SPECIES"):
        _policy_provider(pipeline, doc).validation_policy()


def test_unknown_validation_policy_key_fails_closed(
        pipeline):
    doc = _policy_doc()
    doc["validation"]["quantityAndUnit"]["extraSofteningKey"] = True

    with pytest.raises(profile_policy.ProfilePolicyError, match="unsupported key"):
        _policy_provider(pipeline, doc).validation_policy()


def test_malformed_validation_policy_fails_closed(pipeline):
    doc = _policy_doc()
    doc["validation"]["quantityAndUnit"]["unresolvedReasonCode"] = \
        "NOT_A_REGISTERED_CODE"

    with pytest.raises(profile_policy.ProfilePolicyError,
                       match="not a registered reason code"):
        _policy_provider(pipeline, doc).validation_policy()
