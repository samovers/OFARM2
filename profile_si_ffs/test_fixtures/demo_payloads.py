"""Profile-local builders for active SI demo payloads.

D2c keeps `kernel.demo` as the compatibility facade, but moves construction of
typed identity payloads and operation demo payloads here. These helpers are
test/demo support only; they are not profile law, runtime adapters, contracts,
or conformance evidence.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoPayloadRefs:
    farm: str
    field: str
    cycle: str
    farmer: str
    sprayer: str
    applied_resource: str
    product_binding: str
    crop_binding: str
    photo_evidence: str
    onboarding_evidence: str
    code_binding_profile_ref: str


def refs_from_module(module, *, code_binding_profile_ref: str) -> DemoPayloadRefs:
    """Build `DemoPayloadRefs` from the current `kernel.demo` facade module."""
    return DemoPayloadRefs(
        farm=module.FARM,
        field=module.FIELD,
        cycle=module.CYCLE,
        farmer=module.FARMER,
        sprayer=module.SPRAYER,
        applied_resource=module.APPLIED_RESOURCE,
        product_binding=module.PRODUCT_BINDING,
        crop_binding=module.CROP_BINDING,
        photo_evidence=module.PHOTO_EVIDENCE,
        onboarding_evidence=module.ONBOARDING_EVIDENCE,
        code_binding_profile_ref=code_binding_profile_ref,
    )


def farm_identity_payload(
    *,
    payload_id: str,
    recorded_at: str,
    refs: DemoPayloadRefs,
) -> dict:
    return {
        "schemaVersion": "ofarm.farmidentitypayload.v0.1",
        "farmidentitypayloadId": payload_id,
        "identityRecordRef": refs.farm,
        "recordedAt": recorded_at,
        "displayName": "Demo Kmetija A (fictional)",
        "operatorPartyRef": refs.farmer,
    }


def field_identity_payload(
    *,
    payload_id: str,
    recorded_at: str,
    refs: DemoPayloadRefs,
    display_name: str,
    area_value: float,
) -> dict:
    return {
        "schemaVersion": "ofarm.fieldidentitypayload.v0.1",
        "fieldidentitypayloadId": payload_id,
        "identityRecordRef": refs.field,
        "recordedAt": recorded_at,
        "displayName": display_name,
        "parentFarmIdentityRef": refs.farm,
        "declaredArea": {"value": area_value, "unitCode": "har"},
    }


def cropcycle_identity_payload(
    *,
    payload_id: str,
    recorded_at: str,
    refs: DemoPayloadRefs,
    auto_created: bool,
) -> dict:
    return {
        "schemaVersion": "ofarm.cropcycleidentitypayload.v0.1",
        "cropcycleidentitypayloadId": payload_id,
        "identityRecordRef": refs.cycle,
        "recordedAt": recorded_at,
        "parentScopeRefs": [refs.field],
        "seasonLabel": "2026 (fictional demo season)",
        "cycleState": "ACTIVE",
        "autoCreated": auto_created,
    }


def equipment_identity_payload(
    *,
    payload_id: str,
    recorded_at: str,
    refs: DemoPayloadRefs,
) -> dict:
    return {
        "schemaVersion": "ofarm.equipmentidentitypayload.v0.1",
        "equipmentidentitypayloadId": payload_id,
        "identityRecordRef": refs.sprayer,
        "recordedAt": recorded_at,
        "displayName": "Demo nahrbtna skropilnica (fictional sprayer)",
        "equipmentClass": "SPRAYER",
    }


def appliedresource_identity_payload(
    *,
    payload_id: str,
    recorded_at: str,
    refs: DemoPayloadRefs,
) -> dict:
    return {
        "schemaVersion": "ofarm.appliedresourceidentitypayload.v0.1",
        "appliedresourceidentitypayloadId": payload_id,
        "identityRecordRef": refs.applied_resource,
        "recordedAt": recorded_at,
        "displayName": "ACCOUNT (fictional demo product identity)",
        "resourceClass": "PLANT_PROTECTION_PRODUCT",
    }


def structure_submission(
    payload: dict,
    *,
    idem_key: str,
    refs: DemoPayloadRefs,
    actor_ref: str,
    confirm: bool,
    supersedes: str | None,
    event_time: str,
    evidence_refs: list[str] | None,
) -> dict:
    sub = {
        "commitClass": "STRUCTURE_ASSERTION",
        "ingressChannel": "MANUAL_UI",
        "actingPartyRef": actor_ref,
        "farmRef": refs.farm,
        "subjectType": "FARM",
        "subjectRef": refs.farm,
        "idempotencyKey": idem_key,
        "eventTime": event_time,
        "capturedAt": event_time,
        "payload": payload,
        "evidenceRefs": (
            evidence_refs if evidence_refs is not None
            else [refs.onboarding_evidence]
        ),
        "requestedPromotionTarget": "ACCEPTED_STRUCTURAL_STATE",
        "confirmAccept": confirm,
    }
    if supersedes:
        sub["supersedesConsequenceRef"] = supersedes
    return sub


def spray_payload(
    *,
    erp_id: str,
    refs: DemoPayloadRefs,
    actor_ref: str,
    event_start: str = "2026-06-10T07:30:00Z",
    event_end: str = "2026-06-10T08:15:00Z",
    binding_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    dose_value: float = 0.3,
    unit_ref: str = "scheme:ucum:L/har",
) -> dict:
    return {
        "schemaVersion": "ofarm.executionrecordpayload.v0.1",
        "executionRecordPayloadId": erp_id,
        "recordClass": "OPERATION_CLAIM",
        "recordState": "CLAIMED",
        "capturedAt": event_end,
        "subject": {"subjectType": "FIELD", "subjectRef": refs.field},
        "anchorScopes": [{"scopeType": "FARM", "scopeRef": refs.farm},
                         {"scopeType": "CROP_CYCLE", "scopeRef": refs.cycle}],
        "effectiveTimeInterval": {"start": event_start, "end": event_end,
                                  "timeBasis": "EXECUTION_INTERVAL"},
        "actor": {"actorPartyRef": actor_ref, "roleAtCapture":
                  "FARMER" if actor_ref == refs.farmer else "OPERATOR"},
        "executionExtent": {"extentClass": "WHOLE_TARGET_SCOPE",
                            "targetScope": {"scopeType": "FIELD", "scopeRef": refs.field},
                            "extentBasisStatus": "DECLARED_WHOLE_SCOPE"},
        "actualAction": {"actionType": "APPLY_INPUT",
                         "actionLabel": "crop-protection spray (demo: ACCOUNT)",
                         "interventionKind": "CROP_PROTECTION"},
        "actualQuantityParameters": [{
            "parameterRole": "DOSE", "materialRole": "PRODUCT",
            "materialRef": refs.product_binding,
            "quantityKindRef": "scheme:qudt:VolumePerArea",
            "unitRef": unit_ref, "value": dose_value,
            "qualifier": "HUMAN_REPORTED"}],
        "equipment": {"equipmentRef": refs.sprayer},
        "sourcePayload": {"sourceClass": "HUMAN_LOG",
                          "sourceSystemRef": "app:ofarm2.capture.demo",
                          "originalSemanticsRetained": True},
        "evidenceRefs": evidence_refs if evidence_refs is not None else [refs.photo_evidence],
        "promotionBoundary": {
            "targetTwin": "COMPLIANCE",
            "highConsequenceUse": "OPERATION_CLAIM_ONLY",
            "mustNotPromoteTo": ["CURRENT_STATE_DIRECTLY"],
            "stageSeparationStatement":
                "an operation claim is not an accepted execution (Kernel rule 4)"},
        "agronomicIdentityBindingRefs":
            binding_refs if binding_refs is not None else [refs.product_binding, refs.crop_binding],
        "agronomicCodeBindingProfileRef": refs.code_binding_profile_ref,
    }


def spray_submission(
    *,
    idem_key: str,
    refs: DemoPayloadRefs,
    actor_ref: str,
    confirm: bool,
    erp_id: str,
    channel: str,
    payload_kwargs: dict,
) -> dict:
    payload = spray_payload(
        erp_id=erp_id,
        refs=refs,
        actor_ref=actor_ref,
        **payload_kwargs,
    )
    return {
        "commitClass": "OPERATION_CLAIM",
        "ingressChannel": channel,
        "actingPartyRef": actor_ref,
        "farmRef": refs.farm,
        "subjectType": "FIELD",
        "subjectRef": refs.field,
        "idempotencyKey": idem_key,
        "eventTime": payload["effectiveTimeInterval"]["start"],
        "capturedAt": payload["capturedAt"],
        "payload": payload,
        "evidenceRefs": payload["evidenceRefs"],
        "requestedPromotionTarget": "ACCEPTED_EXECUTED_INTERVENTION_CONSEQUENCE",
        "confirmAccept": confirm,
    }
