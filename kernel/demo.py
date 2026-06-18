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
# the farmer's eRKG / registration printout, the durable evidence backing the
# onboarding structure assertions (fictional, format-true — no real document)
ONBOARDING_EVIDENCE = "evidence:demo.rkg.izpis.1"
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


def substrate_records() -> list[dict]:
    t = now_iso()
    farm_scope = {"scopeType": "FARM", "scopeRef": FARM}
    return [
        {"schemaVersion": "ofarm.party.v0.1", "partyId": FARMER,
         "partyClass": "NATURAL_PERSON", "displayName": "Demo Farmer One (fictional)",
         "registeredIdentifiers": [
             {"scheme": "SI:KMG-MID", "value": "100000001"},
             {"scheme": "SI:FFS-IZKAZNICA", "value": "FFS-000001"}],
         "partyState": "ACTIVE", "recordedAt": t},
        {"schemaVersion": "ofarm.party.v0.1", "partyId": WORKER,
         "partyClass": "NATURAL_PERSON", "displayName": "Demo Family Worker (fictional)",
         "registeredIdentifiers": [{"scheme": "SI:FFS-IZKAZNICA", "value": "FFS-000002"}],
         "partyState": "ACTIVE", "recordedAt": t},
        {"schemaVersion": "ofarm.party.v0.1", "partyId": ADVISOR,
         "partyClass": "NATURAL_PERSON", "displayName": "Demo Advisor (fictional)",
         "partyState": "ACTIVE", "recordedAt": t},
        {"schemaVersion": "ofarm.party.v0.1", "partyId": INSPECTOR,
         "partyClass": "PUBLIC_BODY", "displayName": "Demo Inspectorate (fictional)",
         "partyState": "ACTIVE", "recordedAt": t},
        {"schemaVersion": "ofarm.party.v0.1", "partyId": AGENT,
         "partyClass": "SOFTWARE_AGENT", "displayName": "Demo Capture Agent (fictional)",
         "partyState": "ACTIVE", "recordedAt": t},

        # NOTE: the Farm / Field / CropCycle / Equipment / AppliedResource
        # IdentityRecords are NO LONGER bootstrapped here — they are committed
        # through the gate chain as STRUCTURE_ASSERTIONs carrying typed identity
        # payloads (see onboard() below). Parties, grants, evidence, and code
        # bindings remain substrate (not authoritative-listed kinds).

        {"schemaVersion": "ofarm.roleassignment.v0.1",
         "roleAssignmentId": "role:demo.farmer.one.holder",
         "partyRef": FARMER, "roleType": "FARMER",
         "anchorScopes": [farm_scope], "validFrom": VALID_FROM},

        {"schemaVersion": "ofarm.authoritygrant.v0.1",
         "authorityGrantId": FARMER_GRANT,
         "grantedByPartyRef": FARMER,
         "grantTarget": {"targetKind": "PARTY", "targetRef": FARMER},
         "targetScope": farm_scope,
         "authorityActionClasses": ACTION_CLASSES,
         "validFrom": VALID_FROM,
         "inheritanceMode": "DESCENDANT_SCOPES",
         "grantState": "ACTIVE",
         "purpose": "holding farmer: pilot action set on own farm, accepted "
                    "Action Matrix vocabulary"},

        # REVIEW_ACCEPT is a separate grant per the matrix's posture for
        # govern/decide actions (NO_INHERIT default, not delegable) — the
        # D8 self-review act on the farmer's own farm, exact scope only
        {"schemaVersion": "ofarm.authoritygrant.v0.1",
         "authorityGrantId": "grant:demo.farmer.one.review",
         "grantedByPartyRef": FARMER,
         "grantTarget": {"targetKind": "PARTY", "targetRef": FARMER},
         "targetScope": farm_scope,
         "authorityActionClasses": ["REVIEW_ACCEPT"],
         "validFrom": VALID_FROM,
         "inheritanceMode": "NO_INHERIT",
         "grantState": "ACTIVE",
         "purpose": "self-review of routine operation claims on own farm (D8)"},

        {"schemaVersion": "ofarm.authoritygrant.v0.1",
         "authorityGrantId": "grant:demo.advisor.one.review",
         "grantedByPartyRef": FARMER,
         "grantTarget": {"targetKind": "PARTY", "targetRef": ADVISOR},
         "targetScope": farm_scope,
         "authorityActionClasses": ["REVIEW_ACCEPT", "RECEIVE_READ_DATA"],
         "validFrom": VALID_FROM,
         "inheritanceMode": "NO_INHERIT",
         "grantState": "ACTIVE",
         "purpose": "advisor reviews queue exceptions and non-routine claims "
                    "(D8: self-review covers routine operation claims only)"},

        {"schemaVersion": "ofarm.delegationgrant.v0.1",
         "delegationGrantId": WORKER_DELEGATION,
         "delegatingPartyRef": FARMER, "delegatePartyRef": WORKER,
         "sourceAuthorityGrantRefs": [FARMER_GRANT],
         "targetScope": farm_scope,
         "authorityActionClasses": ["ASSERT_OPERATION_CLAIM", "OBSERVE_ATTACH_EVIDENCE"],
         "validFrom": VALID_FROM,
         "inheritanceMode": "DESCENDANT_SCOPES",
         "delegationState": "ACTIVE",
         "purpose": "family worker sprays under delegation (D4)"},

        {"schemaVersion": "ofarm.sharinggrant.v0.1",
         "sharingGrantId": INSPECTOR_SHARE,
         "grantorPartyRef": FARMER, "granteePartyRef": INSPECTOR,
         "sharedArtifactFamily": "PASSPORT_VIEW",
         "sharedArtifactRef": "view:si.ffs.spray-register.passportview.v0_1",
         "targetScope": farm_scope,
         "validFrom": VALID_FROM,
         "deliveryMode": "VIEW_ONLY",
         "sharingState": "ACTIVE",
         "purpose": "read-only inspector access (optional path)"},

        {"schemaVersion": "ofarm.evidencerecord.v0.1",
         "evidenceRecordId": PHOTO_EVIDENCE,
         "evidenceClass": "PHOTO",
         "capturedAt": "2026-06-10T07:40:00Z", "recordedAt": t,
         "capturedByPartyRef": FARMER,
         "anchorScopes": [farm_scope],
         "rawAssetRef": "asset:demo.photo.0001",
         "rawAssetDigest": "sha256:" + "ab" * 32,
         "mediaType": "image/jpeg",
         "evidenceState": "CAPTURED",
         "notes": "fictional demo photo evidence"},

        {"schemaVersion": "ofarm.evidencerecord.v0.1",
         "evidenceRecordId": ONBOARDING_EVIDENCE,
         "evidenceClass": "REGISTRY_EXTRACT",
         "capturedAt": VALID_FROM, "recordedAt": t,
         "capturedByPartyRef": FARMER,
         "anchorScopes": [farm_scope],
         "rawAssetRef": "asset:demo.rkg.izpis.0001",
         "rawAssetDigest": "sha256:" + "cd" * 32,
         "mediaType": "application/pdf",
         "evidenceState": "CAPTURED",
         "notes": "fictional eRKG/registration printout backing onboarding "
                  "structure assertions (no real holding/parcel values)"},

        {"schemaVersion": "ofarm.agronomicidentitybinding.v0.1",
         "agronomicIdentityBindingId": PRODUCT_BINDING,
         "bindingRole": "CROP_PROTECTION_PRODUCT",
         "bindingState": "VERIFIED",
         "createdAt": t, "createdByPartyRef": FARMER,
         "localSubject": {"subjectType": "PRODUCT_OR_INPUT",
                          "subjectRef": "input:demo.account"},
         "externalScheme": {"schemeRef": "scheme:si.uvhvvr.ffs-reg",
                            "schemeRole": "CODE_BINDING",
                            "issuerRef": "party:si.uvhvvr",
                            "jurisdiction": "SI",
                            "schemeVersion": "register-day-2026-06-11"},
         "bindingValue": {"capturedLabel": "ACCOUNT",
                          "code": "1646",
                          "registrationRef": "U34330-50/23/16",
                          "mappingRelation": "EXACT"},
         "evidenceRefs": ["trace:demo.regver.account"],
         "referenceSnapshotRefs": [REGSR_SNAPSHOT],
         "promotionBoundary": {
             "highConsequenceUse": "ALLOWED_WHEN_PROFILE_AND_EVIDENCE_PASS",
             "maySupportPromotion": True,
             "mustNotPromoteTo": ["OFARM_CORE_MEANING"]}},

        {"schemaVersion": "ofarm.externalregistryverificationtrace.v0.1",
         "externalRegistryVerificationTraceId": "trace:demo.regver.account",
         "profileRef": config.CODE_BINDING_PROFILE_REF,
         "verificationPurpose": "PRODUCT_AUTHORISATION_IDENTITY",
         "createdAt": t,
         "traceAuthorityRef": "party:si.uvhvvr",
         "traceJurisdictionRef": "jurisdiction:SI",
         "lookupSurface": "OTHER",
         "queryInputs": {"freeTextInput": "ACCOUNT",
                         "sourceQueryRef": "surface:spletni2.furs.gov.si.FFS.REGSR"},
         "candidateCount": 1,
         "selectedExternalId": {"externalId": "U34330-50/23/16",
                                "externalIdRole": "AUTHORISATION_NUMBER"},
         "selectionRationale": "single exact trade-name match in the cached snapshot; "
                               "primary key = stevilka odlocbe + validity dates (D9)",
         "statusObserved": "AUTHORISED",
         "datesObserved": {"accessedAt": t,
                           "statusEffectiveUntil": "2027-08-15T00:00:00Z"},
         "snapshotRefs": [REGSR_SNAPSHOT],
         "registryAvailability": "AVAILABLE",
         "discrepancies": [],
         "finalOutcome": "PASS",
         "highConsequenceUse": "ALLOWED_WHEN_PASS",
         "downstreamOutputDisposition": "PASSPORTVIEW_ALLOWED"},

        {"schemaVersion": "ofarm.agronomicidentitybinding.v0.1",
         "agronomicIdentityBindingId": CROP_BINDING,
         "bindingRole": "CROP_SPECIES",
         "bindingState": "VERIFIED",
         "createdAt": t, "createdByPartyRef": FARMER,
         "localSubject": {"subjectType": "CROP", "subjectRef": "crop:demo.vine"},
         "externalScheme": {"schemeRef": "scheme:eppo",
                            "schemeRole": "CODE_BINDING",
                            "issuerRef": "party:eppo"},
         "bindingValue": {"capturedLabel": "vinska trta (fictional demo cycle)",
                          "code": "VITVI",
                          "mappingRelation": "EXACT"},
         "evidenceRefs": [PHOTO_EVIDENCE],
         "promotionBoundary": {
             "highConsequenceUse": "ALLOWED_WHEN_PROFILE_AND_EVIDENCE_PASS",
             "maySupportPromotion": True,
             "mustNotPromoteTo": ["OFARM_CORE_MEANING"]}},
    ]


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
    acceptance, never bootstrapped. Idempotent: a no-op once the Farm identity
    exists. Order Farm -> Field -> CropCycle -> Equipment -> AppliedResource."""
    if store.record_exists(FARM):
        return
    from .gates import GatePipeline   # lazy import: avoids any module-load cycle
    pipe = GatePipeline(store)
    plan = [
        (farm_identity_payload(), "onboard:demo:farm"),
        (field_identity_payload(), "onboard:demo:field"),
        (cropcycle_identity_payload(), "onboard:demo:cropcycle"),
        (equipment_identity_payload(), "onboard:demo:equipment"),
        (appliedresource_identity_payload(), "onboard:demo:appliedresource"),
    ]
    for payload, key in plan:
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
