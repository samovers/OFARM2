"""Fictional demo onboarding (privacy rule 1, D14).

Every value here is fictional and format-true: KMG-MID 100000001 (9 digits),
GERK-PID 1000001 (7 digits), training card FFS-000001, party names are
obviously synthetic. No real person, holding, parcel, or document value
appears anywhere in this module — real farm documents are evidence held
farm-side only (AGENTS.md rule 1).

Substrate records (parties, identities, grants, raw evidence, bindings) are
bootstrapped directly: they are not authoritative-listed kinds, and pilot
onboarding through structure-assertion commits is the M2 path. The product
binding references real *public register* data (REGSR product 1646 "ACCOUNT")
— public product authorisation data is not personal data.
"""
from __future__ import annotations

from .context import now_iso

FARM = "farm:demo.kmetija.a"
FIELD = "field:demo.kmetija.a.gerk-1000001"
FARMER = "party:demo.farmer.one"
WORKER = "party:demo.worker.one"
ADVISOR = "party:demo.advisor.one"
INSPECTOR = "party:demo.inspector.one"
AGENT = "party:demo.software.agent"
SPRAYER = "equip:demo.sprayer.one"
PRODUCT_BINDING = "binding:demo.product.account"
CROP_BINDING = "binding:demo.crop.vine"
PHOTO_EVIDENCE = "evidence:demo.spray.photo.1"
FARMER_GRANT = "grant:demo.farmer.one.full"
WORKER_DELEGATION = "deleg:demo.worker.one.spray"
INSPECTOR_SHARE = "share:demo.inspector.one.read"
REGSR_SNAPSHOT = "referencesnapshot:si.uvhvvr.ffs-reg.2026-06-11"

VALID_FROM = "2026-01-01T00:00:00Z"
ACTION_CLASSES = [
    "COMMIT_OPERATION_CLAIM", "COMMIT_STRUCTURE_ASSERTION", "COMMIT_NOTE",
    "COMMIT_ADVISORY_OUTPUT", "COMMIT_COMPLIANCE_ASSERTION",
    "COMMIT_OBSERVATION_ASSERTION", "COMMIT_EVIDENCE_RECORD",
    "REVIEW_ACCEPT", "READ_REGISTER", "EXPORT_REGISTER", "FILE_SUBMISSION",
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

        {"schemaVersion": "ofarm.identityrecord.v0.1", "identityRecordId": FARM,
         "identityType": "FARM", "lifecycleState": "ACTIVE",
         "createdAt": t, "recordedAt": t},
        {"schemaVersion": "ofarm.identityrecord.v0.1", "identityRecordId": FIELD,
         "identityType": "FIELD", "lifecycleState": "ACTIVE",
         "createdAt": t, "recordedAt": t,
         "anchorScopes": [farm_scope]},
        {"schemaVersion": "ofarm.identityrecord.v0.1", "identityRecordId": SPRAYER,
         "identityType": "EQUIPMENT", "lifecycleState": "ACTIVE",
         "createdAt": t, "recordedAt": t,
         "anchorScopes": [farm_scope]},

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
         "purpose": "holding farmer: full pilot action set on own farm (D8 self-review)"},

        {"schemaVersion": "ofarm.authoritygrant.v0.1",
         "authorityGrantId": "grant:demo.advisor.one.review",
         "grantedByPartyRef": FARMER,
         "grantTarget": {"targetKind": "PARTY", "targetRef": ADVISOR},
         "targetScope": farm_scope,
         "authorityActionClasses": ["REVIEW_ACCEPT", "READ_REGISTER"],
         "validFrom": VALID_FROM,
         "inheritanceMode": "DESCENDANT_SCOPES",
         "grantState": "ACTIVE",
         "purpose": "advisor reviews queue exceptions and non-routine claims "
                    "(D8: self-review covers routine operation claims only)"},

        {"schemaVersion": "ofarm.delegationgrant.v0.1",
         "delegationGrantId": WORKER_DELEGATION,
         "delegatingPartyRef": FARMER, "delegatePartyRef": WORKER,
         "sourceAuthorityGrantRefs": [FARMER_GRANT],
         "targetScope": farm_scope,
         "authorityActionClasses": ["COMMIT_OPERATION_CLAIM", "COMMIT_EVIDENCE_RECORD"],
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
         "profileRef": "codebindingprofile:si.ffs.v0_1",
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


def bootstrap(store) -> None:
    for payload in substrate_records():
        contract = store.registry.get(payload["schemaVersion"])
        if store.record_exists(payload[contract.id_field]):
            continue
        with store.tx() as cur:
            store.insert_record(cur, payload)


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
        "anchorScopes": [{"scopeType": "FARM", "scopeRef": FARM}],
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
        "agronomicCodeBindingProfileRef": "codebindingprofile:si.ffs.v0_1",
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
