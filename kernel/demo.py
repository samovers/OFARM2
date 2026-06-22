"""Fictional demo onboarding (privacy rule 1, D14).

Every value here is fictional and format-true: KMG-MID 100000001 (9 digits),
GERK-PID 1000001 (7 digits), training card FFS-000001, party names are
obviously synthetic. No real person, holding, parcel, or document value
appears anywhere in this module — real farm documents are evidence held
farm-side only (AGENTS.md rule 1).

Substrate records (parties, grants, raw evidence, bindings) are bootstrapped
directly: they are not authoritative-listed kinds. The domain IDENTITIES
(Farm / Field / CropCycle / Equipment / AppliedResource), by contrast, are
committed through the full gate chain as STRUCTURE_ASSERTIONs carrying typed
identity payloads (M2 G1) — see onboard() — not bootstrapped directly. The
product binding references real *public register* data (REGSR product 1646
"ACCOUNT") — public product authorisation data is not personal data.
"""
from __future__ import annotations

from . import config
from .context import now_iso
from profile_si_ffs.test_fixtures import demo_records as si_demo_records

FARM = "farm:demo.kmetija.a"
FIELD = "field:demo.kmetija.a.gerk-1000001"
CYCLE = "cycle:demo.kmetija.a.vine-2026"
FARMER = "party:demo.farmer.one"
WORKER = "party:demo.worker.one"
ADVISOR = "party:demo.advisor.one"
INSPECTOR = "party:demo.inspector.one"
AGENT = "party:demo.software.agent"
SPRAYER = "equip:demo.sprayer.one"
APPLIED_RESOURCE = "resource:demo.account"
PRODUCT_BINDING = "binding:demo.product.account"
CROP_BINDING = "binding:demo.crop.vine"
PHOTO_EVIDENCE = "evidence:demo.spray.photo.1"
# a generic registration document — the durable evidence backing the onboarding
# structure assertions (fictional, format-true — no real document, no SI naming)
ONBOARDING_EVIDENCE = "evidence:demo.registration.1"
FARMER_GRANT = "grant:demo.farmer.one.full"
WORKER_DELEGATION = "deleg:demo.worker.one.spray"
INSPECTOR_SHARE = "share:demo.inspector.one.read"
REGSR_SNAPSHOT = config.SHIPPED_REGSR_SNAPSHOT_REF

VALID_FROM = "2026-01-01T00:00:00Z"
# Accepted Authority Action Matrix vocabulary only
# (reference/rfcs/OFARM_Authority_Action_Matrix_v0_1.md)
ACTION_CLASSES = [
    "OBSERVE_CREATE_OBSERVATION", "OBSERVE_ATTACH_EVIDENCE",
    "ASSERT_STRUCTURE", "ASSERT_OPERATION_CLAIM", "ASSERT_COMPLIANCE",
    "OUTPUT_APPROVE_DOCUMENT_ASSEMBLY", "OUTPUT_FILE_SUBMISSION_ASSEMBLY",
    "RECEIVE_READ_DATA",
]


def _substrate_demo_refs() -> si_demo_records.DemoRefs:
    return si_demo_records.DemoRefs(
        farm=FARM,
        farmer=FARMER,
        worker=WORKER,
        advisor=ADVISOR,
        inspector=INSPECTOR,
        agent=AGENT,
        product_binding=PRODUCT_BINDING,
        crop_binding=CROP_BINDING,
        photo_evidence=PHOTO_EVIDENCE,
        onboarding_evidence=ONBOARDING_EVIDENCE,
        farmer_grant=FARMER_GRANT,
        worker_delegation=WORKER_DELEGATION,
        inspector_share=INSPECTOR_SHARE,
        regsr_snapshot=REGSR_SNAPSHOT,
        valid_from=VALID_FROM,
        action_classes=ACTION_CLASSES,
    )


def substrate_records() -> list[dict]:
    return si_demo_records.substrate_records(
        recorded_at=now_iso(),
        refs=_substrate_demo_refs(),
        code_binding_profile_ref=config.CODE_BINDING_PROFILE_REF,
    )


# ---------------------------------------------------------------------------
# typed identity payloads (M2 G1) — generic Core shapes, no SI scheme bindings
# (KMG-MID / GERK / REGSR / FFS-NAPRAVE bindings are P4). Every value fictional
# and format-true (privacy rule 1, D14). Each builder accepts an explicit
# payload id so a revision can carry a NEW payload for the SAME identity.
# ---------------------------------------------------------------------------

def farm_identity_payload(payload_id: str = "farmpayload:demo.kmetija.a") -> dict:
    return {
        "schemaVersion": "ofarm.farmidentitypayload.v0.1",
        "farmidentitypayloadId": payload_id,
        "identityRecordRef": FARM,
        "recordedAt": now_iso(),
        "displayName": "Demo Kmetija A (fictional)",
        "operatorPartyRef": FARMER,
    }


def field_identity_payload(payload_id: str = "fieldpayload:demo.kmetija.a.field-1",
                           *, display_name: str = "Zgornja njiva (fictional demo field)",
                           area_value: float = 1.42) -> dict:
    return {
        "schemaVersion": "ofarm.fieldidentitypayload.v0.1",
        "fieldidentitypayloadId": payload_id,
        "identityRecordRef": FIELD,
        "recordedAt": now_iso(),
        "displayName": display_name,
        "parentFarmIdentityRef": FARM,
        "declaredArea": {"value": area_value, "unitCode": "har"},
    }


def cropcycle_identity_payload(payload_id: str = "cyclepayload:demo.kmetija.a.vine-2026",
                               *, auto_created: bool = True) -> dict:
    return {
        "schemaVersion": "ofarm.cropcycleidentitypayload.v0.1",
        "cropcycleidentitypayloadId": payload_id,
        "identityRecordRef": CYCLE,
        "recordedAt": now_iso(),
        "parentScopeRefs": [FIELD],
        "seasonLabel": "2026 (fictional demo season)",
        "cycleState": "ACTIVE",
        "autoCreated": auto_created,
    }


def equipment_identity_payload(payload_id: str = "equippayload:demo.sprayer.one") -> dict:
    return {
        "schemaVersion": "ofarm.equipmentidentitypayload.v0.1",
        "equipmentidentitypayloadId": payload_id,
        "identityRecordRef": SPRAYER,
        "recordedAt": now_iso(),
        "displayName": "Demo nahrbtna skropilnica (fictional sprayer)",
        "equipmentClass": "SPRAYER",
    }


def appliedresource_identity_payload(
        payload_id: str = "resourcepayload:demo.account") -> dict:
    return {
        "schemaVersion": "ofarm.appliedresourceidentitypayload.v0.1",
        "appliedresourceidentitypayloadId": payload_id,
        "identityRecordRef": APPLIED_RESOURCE,
        "recordedAt": now_iso(),
        "displayName": "ACCOUNT (fictional demo product identity)",
        "resourceClass": "PLANT_PROTECTION_PRODUCT",
    }


def structure_submission(payload: dict, *, idem_key: str,
                         actor_ref: str = FARMER, confirm: bool = True,
                         supersedes: str | None = None,
                         event_time: str = "2026-01-05T09:00:00Z",
                         evidence_refs: list[str] | None = None) -> dict:
    """A STRUCTURE_ASSERTION submission carrying a typed identity payload.

    Subject = the farm scope: the structural fact is anchored on the farm, and
    the precise identity (identityRecordRef) + attributes live in the carried
    payload. Generic over identity type — no scheme logic.
    """
    sub = {
        "commitClass": "STRUCTURE_ASSERTION",
        "ingressChannel": "MANUAL_UI",
        "actingPartyRef": actor_ref,
        "farmRef": FARM,
        "subjectType": "FARM",
        "subjectRef": FARM,
        "idempotencyKey": idem_key,
        "eventTime": event_time,
        "capturedAt": event_time,
        "payload": payload,
        "evidenceRefs": evidence_refs if evidence_refs is not None
                        else [ONBOARDING_EVIDENCE],
        "requestedPromotionTarget": "ACCEPTED_STRUCTURAL_STATE",
        "confirmAccept": confirm,
    }
    if supersedes:
        sub["supersedesConsequenceRef"] = supersedes
    return sub


def onboard(store) -> None:
    """Commit the demo farm's domain identities through the full gate chain as
    STRUCTURE_ASSERTIONs (M2 G1) — the IdentityRecords are created on
    acceptance, never bootstrapped. Idempotent and RESUMABLE: each missing
    identity is committed independently, so a partial prior run is completed
    rather than skipped. Order Farm -> Field -> CropCycle -> Equipment ->
    AppliedResource (a child's parent identity must already exist)."""
    plan = [
        (farm_identity_payload(), "onboard:demo:farm"),
        (field_identity_payload(), "onboard:demo:field"),
        (cropcycle_identity_payload(), "onboard:demo:cropcycle"),
        (equipment_identity_payload(), "onboard:demo:equipment"),
        (appliedresource_identity_payload(), "onboard:demo:appliedresource"),
    ]
    if all(store.record_exists(p["identityRecordRef"]) for p, _ in plan):
        return   # fully onboarded already
    from .gates import GatePipeline   # lazy import: avoids any module-load cycle
    pipe = GatePipeline(store)
    for payload, key in plan:
        if store.record_exists(payload["identityRecordRef"]):
            continue   # resume: this identity is already committed
        result = pipe.commit(structure_submission(payload, idem_key=key))
        if result["decisionOutcome"] != "PROMOTE_ACCEPTED":
            raise RuntimeError(
                f"demo onboarding failed at {key}: {result['decisionOutcome']} "
                f"{result.get('problems')}")


def bootstrap(store) -> None:
    for payload in substrate_records():
        contract = store.registry.get(payload["schemaVersion"])
        if store.record_exists(payload[contract.id_field]):
            continue
        with store.tx() as cur:
            store.insert_record(cur, payload)
    onboard(store)


def spray_payload(erp_id: str = "erp:demo.spray.0001", *,
                  actor_ref: str = FARMER,
                  event_start: str = "2026-06-10T07:30:00Z",
                  event_end: str = "2026-06-10T08:15:00Z",
                  binding_refs: list[str] | None = None,
                  evidence_refs: list[str] | None = None,
                  dose_value: float = 0.3,
                  unit_ref: str = "scheme:ucum:L/har") -> dict:
    """A complete, fictional ExecutionRecordPayload for one vine spray."""
    return {
        "schemaVersion": "ofarm.executionrecordpayload.v0.1",
        "executionRecordPayloadId": erp_id,
        "recordClass": "OPERATION_CLAIM",
        "recordState": "CLAIMED",
        "capturedAt": event_end,
        "subject": {"subjectType": "FIELD", "subjectRef": FIELD},
        "anchorScopes": [{"scopeType": "FARM", "scopeRef": FARM},
                         {"scopeType": "CROP_CYCLE", "scopeRef": CYCLE}],
        "effectiveTimeInterval": {"start": event_start, "end": event_end,
                                  "timeBasis": "EXECUTION_INTERVAL"},
        "actor": {"actorPartyRef": actor_ref, "roleAtCapture":
                  "FARMER" if actor_ref == FARMER else "OPERATOR"},
        "executionExtent": {"extentClass": "WHOLE_TARGET_SCOPE",
                            "targetScope": {"scopeType": "FIELD", "scopeRef": FIELD},
                            "extentBasisStatus": "DECLARED_WHOLE_SCOPE"},
        "actualAction": {"actionType": "APPLY_INPUT",
                         "actionLabel": "crop-protection spray (demo: ACCOUNT)",
                         "interventionKind": "CROP_PROTECTION"},
        "actualQuantityParameters": [{
            "parameterRole": "DOSE", "materialRole": "PRODUCT",
            "materialRef": PRODUCT_BINDING,
            "quantityKindRef": "scheme:qudt:VolumePerArea",
            "unitRef": unit_ref, "value": dose_value,
            "qualifier": "HUMAN_REPORTED"}],
        "equipment": {"equipmentRef": SPRAYER},
        "sourcePayload": {"sourceClass": "HUMAN_LOG",
                          "sourceSystemRef": "app:ofarm2.capture.demo",
                          "originalSemanticsRetained": True},
        "evidenceRefs": evidence_refs if evidence_refs is not None else [PHOTO_EVIDENCE],
        "promotionBoundary": {
            "targetTwin": "COMPLIANCE",
            "highConsequenceUse": "OPERATION_CLAIM_ONLY",
            "mustNotPromoteTo": ["CURRENT_STATE_DIRECTLY"],
            "stageSeparationStatement":
                "an operation claim is not an accepted execution (Kernel rule 4)"},
        "agronomicIdentityBindingRefs":
            binding_refs if binding_refs is not None else [PRODUCT_BINDING, CROP_BINDING],
        "agronomicCodeBindingProfileRef": config.CODE_BINDING_PROFILE_REF,
    }


def spray_submission(idem_key: str = "device-demo-1:q-0001", *,
                     actor_ref: str = FARMER, confirm: bool = True,
                     erp_id: str = "erp:demo.spray.0001",
                     channel: str = "MANUAL_UI", **payload_kwargs) -> dict:
    payload = spray_payload(erp_id, actor_ref=actor_ref, **payload_kwargs)
    return {
        "commitClass": "OPERATION_CLAIM",
        "ingressChannel": channel,
        "actingPartyRef": actor_ref,
        "farmRef": FARM,
        "subjectType": "FIELD",
        "subjectRef": FIELD,
        "idempotencyKey": idem_key,
        "eventTime": payload["effectiveTimeInterval"]["start"],
        "capturedAt": payload["capturedAt"],
        "payload": payload,
        "evidenceRefs": payload["evidenceRefs"],
        "requestedPromotionTarget": "ACCEPTED_EXECUTED_INTERVENTION_CONSEQUENCE",
        "confirmAccept": confirm,
    }
