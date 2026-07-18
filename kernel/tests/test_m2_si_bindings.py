"""M2 P4 — SI binding active-runtime integration tests.

Engineering tests, NOT part of the named conformance suite. The SI profile
wrapper assertions live in
`profile_si_ffs.tests.m2_si_binding_wrapper_tests` and are imported here so the
root pytest command keeps discovering the same coverage. This root-owned file
keeps promotion-facing integration checks for binding attachment, subject
matching, and fake evidence refusal.
"""
from __future__ import annotations

from dataclasses import replace

from kernel import config, context, demo
from kernel.context import ProductRegister
from kernel.profiles.si_ffs.ffsnaprave_adapter import VALIDITY_FIELD
from kernel.profiles.si_ffs import si_bindings as sib
from kernel.verification import REFUSE
from profile_si_ffs.tests.m2_si_binding_fixtures import (
    import_regsr_snapshot,
    uid,
)
from profile_si_ffs.tests.m2_si_binding_wrapper_tests import *  # noqa: F401,F403


def test_p4_store_bound_resolvers_use_alternate_descriptor_selection():
    """Store-bound SI traces use the descriptor, never module-global selection."""
    decision = "U99999-50/26/alternate"
    artifact = {
        "products": [],
        "productDetails": [{
            "name": "FIKTIV alternate descriptor product",
            "decisions": [{
                "decisionType": "Registracija",
                "decisionNumber": decision,
                "issued": "2026-01-01",
                "validUntil": "2028-12-31",
            }],
        }],
    }

    alternate_profile_ref = "codebindingprofile:si.ffs.alternate.v0_1"
    alternate_regsr_prefix = "referencesnapshot:si.alternate.ffs-reg"
    alternate_gerk_prefix = "referencesnapshot:si.alternate.gerk-layer"
    alternate_ffs_prefix = "referencesnapshot:si.alternate.ffs-naprave"
    alternate_regsr_family = "si.alternate.ffs-reg"
    alternate_ffs_family = "si.alternate.ffs-naprave"
    alternate_regsr_snapshot = f"{alternate_regsr_prefix}.2026-06-11"
    alternate_gerk_snapshot = f"{alternate_gerk_prefix}.2025-06-30"
    ffs_snapshot = f"{alternate_ffs_prefix}.2026-01-01"
    alternate_source_ref = "artifact:alternate-regsr.json"

    families = []
    for family in config.ACTIVE_PROFILE.reference_families:
        if family.family_id == context.SI_REGSR_FAMILY_ID:
            family = replace(
                family,
                snapshot_prefix=alternate_regsr_prefix,
                data_family=alternate_regsr_family,
                shipped_snapshot_ref=alternate_regsr_snapshot,
            )
        elif family.family_id == context.SI_GERK_FAMILY_ID:
            family = replace(
                family,
                snapshot_prefix=alternate_gerk_prefix,
                shipped_snapshot_ref=alternate_gerk_snapshot,
            )
        elif family.family_id == context.SI_FFSNAPRAVE_FAMILY_ID:
            family = replace(
                family,
                snapshot_prefix=alternate_ffs_prefix,
                data_family=alternate_ffs_family,
            )
        families.append(family)
    descriptor = replace(
        config.ACTIVE_PROFILE,
        code_binding_profile_ref=alternate_profile_ref,
        reference_families=tuple(families),
    )
    bindings = context.SIReferenceBindings.from_runtime_descriptor(descriptor)
    assert bindings.regsr_data_family == alternate_regsr_family
    assert bindings.ffsnaprave_data_family == alternate_ffs_family

    snapshots = {
        alternate_regsr_snapshot: {
            "referenceSnapshotId": alternate_regsr_snapshot,
            "effectiveFrom": "2026-06-11T00:00:00Z",
            "canonicalVersionLabel": "alternate-regsr",
            "sourceArtifactRefs": [alternate_source_ref],
        },
        alternate_gerk_snapshot: {
            "referenceSnapshotId": alternate_gerk_snapshot,
            "effectiveFrom": "2025-06-30T00:00:00Z",
            "canonicalVersionLabel": "alternate-gerk",
            "sourceArtifactRefs": ["surface:alternate-gerk"],
        },
        ffs_snapshot: {
            "referenceSnapshotId": ffs_snapshot,
            "effectiveFrom": "2026-01-01T00:00:00Z",
            "canonicalVersionLabel": "alternate-profile-ffs",
            "sourceArtifactRefs": ["surface:alternate-ffs"],
        },
    }

    class AlternateStore:
        active_descriptor = descriptor
        selected_reference_snapshot_refs = frozenset(snapshots)

        def __init__(self):
            self.selected_source_families = []
            self.traces = []

        def get_record(self, ref):
            if ref == demo.ONBOARDING_EVIDENCE:
                return {"record_kind": "ofarm.evidencerecord.v0.1", "payload": {}}
            payload = snapshots.get(ref)
            return {"record_kind": "ofarm.referencesnapshot.v0.1", "payload": payload} \
                if payload else None

        def find_by_kind(self, kind):
            assert kind == "ofarm.referencesnapshot.v0.1"
            return [{"payload": payload} for payload in snapshots.values()]

        def selected_reference_source_data(self, snapshot_family):
            self.selected_source_families.append(snapshot_family)
            sources = {
                alternate_regsr_prefix: (
                    alternate_regsr_snapshot,
                    artifact,
                ),
                alternate_gerk_prefix: (
                    alternate_gerk_snapshot,
                    {"features": [{"gerkPid": "123"}]},
                ),
                alternate_ffs_prefix: (
                    ffs_snapshot,
                    {"inspections": [{
                        "StevilkaZnaka": "ALT-123",
                        VALIDITY_FIELD: "2027-12-31",
                    }]},
                ),
            }
            snapshot_ref, payload = sources[snapshot_family]
            return [{
                "snapshot_ref": snapshot_ref,
                "artifact_ref": f"artifact:{snapshot_family}",
                "source_digest": "sha256:" + "a" * 64,
                "payload": payload,
            }]

        def insert_record(self, _cur, payload):
            self.traces.append(payload)

    store = AlternateStore()
    with_product = sib.resolve_product_authorisation(
        store,
        object(),
        decision,
        "resource:alternate.product",
        created_by=demo.FARMER,
        evidence_ref=demo.ONBOARDING_EVIDENCE,
        as_of="2026-06-12T12:00:00Z",
    )
    parcel = sib.resolve_parcel(
        store,
        object(),
        "123",
        "field:alternate",
        created_by=demo.FARMER,
        evidence_ref=demo.ONBOARDING_EVIDENCE,
        as_of="2026-06-12T12:00:00Z",
    )
    equipment = sib.resolve_equipment(
        store,
        object(),
        "ALT-123",
        "equipment:alternate",
        created_by=demo.FARMER,
        evidence_ref=demo.ONBOARDING_EVIDENCE,
        validity="2027-12-31",
        as_of="2026-06-12T12:00:00Z",
    )

    assert store.selected_source_families == [
        alternate_regsr_prefix,
        alternate_gerk_prefix,
        alternate_ffs_prefix,
    ]
    assert with_product["trace"]["profileRef"] == alternate_profile_ref
    assert with_product["trace"]["snapshotRefs"] == [alternate_regsr_snapshot]
    assert parcel["trace"]["profileRef"] == alternate_profile_ref
    assert parcel["trace"]["snapshotRefs"] == [alternate_gerk_snapshot]
    assert equipment["trace"]["profileRef"] == alternate_profile_ref
    assert equipment["trace"]["snapshotRefs"] == [ffs_snapshot]


def test_p4_resolved_binding_attaches_to_committed_appliedresource_identity(store, pipeline):
    # The binding subject and committed identity must match before an identity
    # binding can support promotion.
    decision = f"U9{uid()[:4]}-50/26/e"
    import_regsr_snapshot(store, "2099-04-06", decision)
    s = uid()
    ar_ref = f"resource:m2p4.{s}"
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, decision, ar_ref,
                                              created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2099-04-06T12:00:00Z")
        store.insert_record(cur, r["binding"])
    assert r["binding"]["localSubject"]["subjectRef"] == ar_ref
    bid = r["binding"]["agronomicIdentityBindingId"]
    payload = {
        "schemaVersion": "ofarm.appliedresourceidentitypayload.v0.1",
        "appliedresourceidentitypayloadId": f"resourcepayload:m2p4.{s}",
        "identityRecordRef": ar_ref,
        "recordedAt": demo.now_iso(),
        "displayName": "FIKTIV (fictional resource identity)",
        "resourceClass": "PLANT_PROTECTION_PRODUCT",
        "identityBindingRefs": [bid],
    }
    result = pipeline.commit(demo.structure_submission(payload, idem_key=f"m2p4-bind:{s}"))
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_p4_caller_fabricated_selected_register_cannot_mint_verified_binding(store):
    decision = f"U9{uid()[:4]}-99/99/x"
    selected = context.current_reference_snapshot(
        store,
        context.REGSR_SNAPSHOT_PREFIX,
        as_of="2026-06-12T12:00:00Z",
    )
    caller_register = ProductRegister()
    caller_register.register_artifact(
        selected["referenceSnapshotId"],
        {
            "products": [],
            "productDetails": [{
                "name": "FIKTIV (fabricated caller row)",
                "decisions": [{
                    "decisionType": "Registracija",
                    "decisionNumber": decision,
                    "issued": "2026-01-01",
                    "validUntil": "2028-08-15",
                }],
            }],
        },
    )
    assert caller_register.lookup_by_decision(
        selected["referenceSnapshotId"], decision
    ) is not None

    with store.serialized_tx() as cur:
        result = sib.resolve_product_authorisation(
            store,
            cur,
            decision,
            f"resource:fabricated.{uid()}",
            created_by=demo.FARMER,
            evidence_ref=demo.ONBOARDING_EVIDENCE,
            as_of="2026-06-12T12:00:00Z",
        )

    assert result["verdict"] != "CONFIRM"
    assert result["trace"]["snapshotRefs"] == [selected["referenceSnapshotId"]]
    assert result["trace"]["finalOutcome"] != "PASS"
    assert result["binding"]["bindingState"] != "VERIFIED"
    assert result["binding"]["promotionBoundary"]["maySupportPromotion"] is False


def test_p4_binding_for_a_different_subject_does_not_promote(store, pipeline):
    # A binding whose localSubject differs from the committed identity must not
    # attach or promote.
    decision = f"U9{uid()[:4]}-50/26/m"
    import_regsr_snapshot(store, "2099-04-07", decision)
    s = uid()
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, decision, f"resource:OTHER.{s}",
                                              created_by=demo.FARMER,
                                              evidence_ref=demo.ONBOARDING_EVIDENCE,
                                              as_of="2099-04-07T12:00:00Z")
        store.insert_record(cur, r["binding"])
    bid = r["binding"]["agronomicIdentityBindingId"]
    payload = {
        "schemaVersion": "ofarm.appliedresourceidentitypayload.v0.1",
        "appliedresourceidentitypayloadId": f"resourcepayload:m2p4mm.{s}",
        "identityRecordRef": f"resource:m2p4mm.{s}",
        "recordedAt": demo.now_iso(),
        "displayName": "FIKTIV mismatch (fictional)",
        "resourceClass": "PLANT_PROTECTION_PRODUCT",
        "identityBindingRefs": [bid],
    }
    result = pipeline.commit(demo.structure_submission(payload, idem_key=f"m2p4-mm:{s}"))
    assert result["decisionOutcome"] != "PROMOTE_ACCEPTED", \
        "a binding for another subject must not attach to a different committed identity"


def test_p4_fake_evidence_ref_produces_no_binding(store):
    # A binding may not cite fabricated captured evidence. A ref that does not
    # resolve to an EvidenceRecord yields no attachable binding.
    decision = f"U9{uid()[:4]}-50/26/f"
    import_regsr_snapshot(store, "2099-04-11", decision)
    with store.serialized_tx() as cur:
        r = sib.resolve_product_authorisation(store, cur, decision, "resource:f",
                                              created_by=demo.FARMER,
                                              evidence_ref="evidence:does-not-exist",
                                              as_of="2099-04-11T12:00:00Z")
    assert r["binding"] is None and r["verdict"] == REFUSE
    assert r["problem"]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"

    h = sib.resolve_holding(store, "100000003", "farm:f", evidence_ref="evidence:nope",
                            created_by=demo.FARMER)
    assert h["binding"] is None and h["problem"]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"

    sid = import_regsr_snapshot(store, "2099-04-12", f"U9{uid()[:4]}-50/26/x")
    h2 = sib.resolve_holding(store, "100000004", "farm:f2", evidence_ref=sid, created_by=demo.FARMER)
    assert h2["binding"] is None
