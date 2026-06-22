"""Profile-local builders for active SI demo substrate records.

D2b keeps `kernel.demo` as the compatibility facade, but moves construction of
the SI-shaped substrate records here. These helpers are test/demo support only;
they are not profile law, runtime adapters, contracts, or conformance evidence.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoRefs:
    farm: str
    farmer: str
    worker: str
    advisor: str
    inspector: str
    agent: str
    product_binding: str
    crop_binding: str
    photo_evidence: str
    onboarding_evidence: str
    farmer_grant: str
    worker_delegation: str
    inspector_share: str
    regsr_snapshot: str
    valid_from: str
    action_classes: list[str]


def refs_from_module(module) -> DemoRefs:
    """Build `DemoRefs` from the current `kernel.demo` compatibility module."""
    return DemoRefs(
        farm=module.FARM,
        farmer=module.FARMER,
        worker=module.WORKER,
        advisor=module.ADVISOR,
        inspector=module.INSPECTOR,
        agent=module.AGENT,
        product_binding=module.PRODUCT_BINDING,
        crop_binding=module.CROP_BINDING,
        photo_evidence=module.PHOTO_EVIDENCE,
        onboarding_evidence=module.ONBOARDING_EVIDENCE,
        farmer_grant=module.FARMER_GRANT,
        worker_delegation=module.WORKER_DELEGATION,
        inspector_share=module.INSPECTOR_SHARE,
        regsr_snapshot=module.REGSR_SNAPSHOT,
        valid_from=module.VALID_FROM,
        action_classes=module.ACTION_CLASSES,
    )


def substrate_records(
    *,
    recorded_at: str,
    refs: DemoRefs,
    code_binding_profile_ref: str,
) -> list[dict]:
    t = recorded_at
    farm_scope = {"scopeType": "FARM", "scopeRef": refs.farm}
    return [
        {"schemaVersion": "ofarm.party.v0.1", "partyId": refs.farmer,
         "partyClass": "NATURAL_PERSON", "displayName": "Demo Farmer One (fictional)",
         "registeredIdentifiers": [
             {"scheme": "SI:KMG-MID", "value": "100000001"},
             {"scheme": "SI:FFS-IZKAZNICA", "value": "FFS-000001"}],
         "partyState": "ACTIVE", "recordedAt": t},
        {"schemaVersion": "ofarm.party.v0.1", "partyId": refs.worker,
         "partyClass": "NATURAL_PERSON", "displayName": "Demo Family Worker (fictional)",
         "registeredIdentifiers": [{"scheme": "SI:FFS-IZKAZNICA", "value": "FFS-000002"}],
         "partyState": "ACTIVE", "recordedAt": t},
        {"schemaVersion": "ofarm.party.v0.1", "partyId": refs.advisor,
         "partyClass": "NATURAL_PERSON", "displayName": "Demo Advisor (fictional)",
         "partyState": "ACTIVE", "recordedAt": t},
        {"schemaVersion": "ofarm.party.v0.1", "partyId": refs.inspector,
         "partyClass": "PUBLIC_BODY", "displayName": "Demo Inspectorate (fictional)",
         "partyState": "ACTIVE", "recordedAt": t},
        {"schemaVersion": "ofarm.party.v0.1", "partyId": refs.agent,
         "partyClass": "SOFTWARE_AGENT", "displayName": "Demo Capture Agent (fictional)",
         "partyState": "ACTIVE", "recordedAt": t},

        {"schemaVersion": "ofarm.roleassignment.v0.1",
         "roleAssignmentId": "role:demo.farmer.one.holder",
         "partyRef": refs.farmer, "roleType": "FARMER",
         "anchorScopes": [farm_scope], "validFrom": refs.valid_from},

        {"schemaVersion": "ofarm.authoritygrant.v0.1",
         "authorityGrantId": refs.farmer_grant,
         "grantedByPartyRef": refs.farmer,
         "grantTarget": {"targetKind": "PARTY", "targetRef": refs.farmer},
         "targetScope": farm_scope,
         "authorityActionClasses": refs.action_classes,
         "validFrom": refs.valid_from,
         "inheritanceMode": "DESCENDANT_SCOPES",
         "grantState": "ACTIVE",
         "purpose": "holding farmer: pilot action set on own farm, accepted "
                    "Action Matrix vocabulary"},

        {"schemaVersion": "ofarm.authoritygrant.v0.1",
         "authorityGrantId": "grant:demo.farmer.one.review",
         "grantedByPartyRef": refs.farmer,
         "grantTarget": {"targetKind": "PARTY", "targetRef": refs.farmer},
         "targetScope": farm_scope,
         "authorityActionClasses": ["REVIEW_ACCEPT"],
         "validFrom": refs.valid_from,
         "inheritanceMode": "NO_INHERIT",
         "grantState": "ACTIVE",
         "purpose": "self-review of routine operation claims on own farm (D8)"},

        {"schemaVersion": "ofarm.authoritygrant.v0.1",
         "authorityGrantId": "grant:demo.advisor.one.review",
         "grantedByPartyRef": refs.farmer,
         "grantTarget": {"targetKind": "PARTY", "targetRef": refs.advisor},
         "targetScope": farm_scope,
         "authorityActionClasses": ["REVIEW_ACCEPT", "REVIEW_REJECT_OR_CONTEST",
                                    "RECEIVE_READ_DATA"],
         "validFrom": refs.valid_from,
         "inheritanceMode": "NO_INHERIT",
         "grantState": "ACTIVE",
         "purpose": "advisor reviews queue exceptions and non-routine claims — "
                    "accepts or rejects (D8: self-review covers routine operation "
                    "claims only)"},

        {"schemaVersion": "ofarm.delegationgrant.v0.1",
         "delegationGrantId": refs.worker_delegation,
         "delegatingPartyRef": refs.farmer, "delegatePartyRef": refs.worker,
         "sourceAuthorityGrantRefs": [refs.farmer_grant],
         "targetScope": farm_scope,
         "authorityActionClasses": ["ASSERT_OPERATION_CLAIM", "OBSERVE_ATTACH_EVIDENCE"],
         "validFrom": refs.valid_from,
         "inheritanceMode": "DESCENDANT_SCOPES",
         "delegationState": "ACTIVE",
         "purpose": "family worker sprays under delegation (D4)"},

        {"schemaVersion": "ofarm.sharinggrant.v0.1",
         "sharingGrantId": refs.inspector_share,
         "grantorPartyRef": refs.farmer, "granteePartyRef": refs.inspector,
         "sharedArtifactFamily": "PASSPORT_VIEW",
         "sharedArtifactRef": "view:si.ffs.spray-register.passportview.v0_1",
         "targetScope": farm_scope,
         "validFrom": refs.valid_from,
         "deliveryMode": "VIEW_ONLY",
         "sharingState": "ACTIVE",
         "purpose": "read-only inspector access (optional path)"},

        {"schemaVersion": "ofarm.evidencerecord.v0.1",
         "evidenceRecordId": refs.photo_evidence,
         "evidenceClass": "PHOTO",
         "capturedAt": "2026-06-10T07:40:00Z", "recordedAt": t,
         "capturedByPartyRef": refs.farmer,
         "anchorScopes": [farm_scope],
         "rawAssetRef": "asset:demo.photo.0001",
         "rawAssetDigest": "sha256:" + "ab" * 32,
         "mediaType": "image/jpeg",
         "evidenceState": "CAPTURED",
         "notes": "fictional demo photo evidence"},

        {"schemaVersion": "ofarm.evidencerecord.v0.1",
         "evidenceRecordId": refs.onboarding_evidence,
         "evidenceClass": "REGISTRY_EXTRACT",
         "capturedAt": refs.valid_from, "recordedAt": t,
         "capturedByPartyRef": refs.farmer,
         "anchorScopes": [farm_scope],
         "rawAssetRef": "asset:demo.registration.0001",
         "rawAssetDigest": "sha256:" + "cd" * 32,
         "mediaType": "application/pdf",
         "evidenceState": "CAPTURED",
         "notes": "fictional registration document backing onboarding structure "
                  "assertions (no real holding/parcel values)"},

        {"schemaVersion": "ofarm.agronomicidentitybinding.v0.1",
         "agronomicIdentityBindingId": refs.product_binding,
         "bindingRole": "CROP_PROTECTION_PRODUCT",
         "bindingState": "VERIFIED",
         "createdAt": t, "createdByPartyRef": refs.farmer,
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
         "referenceSnapshotRefs": [refs.regsr_snapshot],
         "promotionBoundary": {
             "highConsequenceUse": "ALLOWED_WHEN_PROFILE_AND_EVIDENCE_PASS",
             "maySupportPromotion": True,
             "mustNotPromoteTo": ["OFARM_CORE_MEANING"]}},

        {"schemaVersion": "ofarm.externalregistryverificationtrace.v0.1",
         "externalRegistryVerificationTraceId": "trace:demo.regver.account",
         "profileRef": code_binding_profile_ref,
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
         "snapshotRefs": [refs.regsr_snapshot],
         "registryAvailability": "AVAILABLE",
         "discrepancies": [],
         "finalOutcome": "PASS",
         "highConsequenceUse": "ALLOWED_WHEN_PASS",
         "downstreamOutputDisposition": "PASSPORTVIEW_ALLOWED"},

        {"schemaVersion": "ofarm.agronomicidentitybinding.v0.1",
         "agronomicIdentityBindingId": refs.crop_binding,
         "bindingRole": "CROP_SPECIES",
         "bindingState": "VERIFIED",
         "createdAt": t, "createdByPartyRef": refs.farmer,
         "localSubject": {"subjectType": "CROP", "subjectRef": "crop:demo.vine"},
         "externalScheme": {"schemeRef": "scheme:eppo",
                            "schemeRole": "CODE_BINDING",
                            "issuerRef": "party:eppo"},
         "bindingValue": {"capturedLabel": "vinska trta (fictional demo cycle)",
                          "code": "VITVI",
                          "mappingRelation": "EXACT"},
         "evidenceRefs": [refs.photo_evidence],
         "promotionBoundary": {
             "highConsequenceUse": "ALLOWED_WHEN_PROFILE_AND_EVIDENCE_PASS",
             "maySupportPromotion": True,
             "mustNotPromoteTo": ["OFARM_CORE_MEANING"]}},
    ]
