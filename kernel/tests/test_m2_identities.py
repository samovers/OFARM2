"""M2 G1 — governed structure-identity commit path.

Engineering tests, NOT part of the named conformance suite (conftest only
records test_conformance.py into the evidence file). They pin the G1 behavior:
Farm / Field / CropCycle / Equipment / AppliedResource identities committed
through the full gate chain as STRUCTURE_ASSERTIONs carrying typed identity
payloads -> ACCEPTED_STRUCTURAL_STATE consequences; an identity registry that
materializes the CURRENT payload per identity from in-force structural
consequences; supersession that updates the current payload without editing
the prior record (D12 staling). All data is fictional and format-true
(privacy rule 1, D14). Generic over identity type — no SI scheme bindings (P4).
"""
from __future__ import annotations

import uuid

from kernel import demo, policy
from kernel.context import now_iso


def uid() -> str:
    return uuid.uuid4().hex[:10]


# the five durable identity types G1 commits, and the payload kind for each
DEMO_IDENTITIES = {
    demo.FARM: "FARM",
    demo.FIELD: "FIELD",
    demo.CYCLE: "CROP_CYCLE",
    demo.SPRAYER: "EQUIPMENT",
    demo.APPLIED_RESOURCE: "APPLIED_RESOURCE",
}


def _structural_consequence_by_identity(store, farm_ref: str) -> dict:
    """identityRecordRef -> its in-force structural consequence payload, via
    the in-force consequence -> sourceEvent -> STRUCTURE_PAYLOAD -> payload
    join the identity registry uses."""
    out: dict[str, dict] = {}
    for row in store.in_force_consequences(farm_ref):
        c = row["payload"]
        edges = store.edges_from(c["sourceEventRef"], "STRUCTURE_PAYLOAD")
        if not edges:
            continue
        payload = store.get_payload(edges[0]["dst_record_id"])
        if payload:
            out[payload["identityRecordRef"]] = c
    return out


def _registry(store, materializer, farm_ref=demo.FARM) -> dict:
    with store.tx() as cur:
        return materializer.materialize_identity_registry(cur, farm_ref)


# ---------------------------------------------------------------------------
# the demo farm is onboarded purely via committed structure assertions
# ---------------------------------------------------------------------------

def test_g1_demo_identities_were_committed_not_bootstrapped(store):
    """Each demo identity is a real IdentityRecord created on the commit path
    (currentPayloadRef + createdByAssertionRecordRef set), reachable from an
    in-force STATE_CHANGE_ACCEPTED structural consequence — never a direct
    bootstrap insert (G1 acceptance)."""
    by_identity = _structural_consequence_by_identity(store, demo.FARM)
    for identity_ref, expected_type in DEMO_IDENTITIES.items():
        row = store.get_record(identity_ref)
        assert row is not None, f"{identity_ref} identity missing"
        assert row["record_kind"] == "ofarm.identityrecord.v0.1"
        ident = row["payload"]
        assert ident["identityType"] == expected_type
        # provenance of the commit path, not a bootstrap insert
        assert ident.get("createdByAssertionRecordRef"), \
            f"{identity_ref} has no creating assertion (was it bootstrapped?)"
        assert ident.get("currentPayloadRef"), f"{identity_ref} has no payload ref"
        # an in-force structural consequence, properly promoted
        assert identity_ref in by_identity, \
            f"{identity_ref} has no in-force structural consequence"
        c = by_identity[identity_ref]
        assert c["consequenceType"] == "STATE_CHANGE_ACCEPTED"
        emits = store.edges_to(c["acceptedEventConsequenceId"], "PROMOTION_EMITS")
        assert len(emits) == 1, "structural consequence must be reachable from one trace"


def test_g1_identity_registry_materializes_current_payload_per_type(store, materializer):
    """The identity registry materializes the current typed payload per
    identity from in-force structural consequences — all five demo types, each
    with its right identityType and a payload carrying the matching kind."""
    reg = _registry(store, materializer)
    state = reg["currentState"]
    assert state["stateKind"] == "ofarm.identity-registry.v0_1"
    assert state["derived"] is True
    entries = {e["identityRecordRef"]: e for e in state["identities"]}
    for identity_ref, expected_type in DEMO_IDENTITIES.items():
        assert identity_ref in entries, f"{identity_ref} absent from registry"
        e = entries[identity_ref]
        assert e["identityType"] == expected_type
        assert e["lifecycleState"] == "ACTIVE"
        payload = e["currentPayload"]
        assert payload["identityRecordRef"] == identity_ref
        assert policy.STRUCTURE_PAYLOAD_IDENTITY_TYPE[payload["schemaVersion"]] \
            == expected_type
    # the registry materialization carries its receipts (Kernel rule 5)
    assert reg["basisRef"] and reg["snapshotRef"]


# ---------------------------------------------------------------------------
# a fresh structure assertion passes the full gate chain (generic, per type)
# ---------------------------------------------------------------------------

def test_g1_fresh_structure_assertion_accepts_and_creates_identity(pipeline, store,
                                                                    materializer):
    """A live STRUCTURE_ASSERTION carrying a typed payload passes the chain,
    writes an ACCEPTED_STRUCTURAL_STATE consequence, creates the IdentityRecord
    (anchored on the farm), and surfaces in the registry — generic over type,
    no scheme logic."""
    suffix = uid()
    field_ref = f"field:m2.{suffix}"
    payload = {
        "schemaVersion": "ofarm.fieldidentitypayload.v0.1",
        "fieldidentitypayloadId": f"fieldpayload:m2.{suffix}",
        "identityRecordRef": field_ref,
        "recordedAt": now_iso(),
        "displayName": "M2 test field (fictional)",
        "parentFarmIdentityRef": demo.FARM,
        "declaredArea": {"value": 0.8, "unitCode": "har"},
    }
    result = pipeline.commit(demo.structure_submission(
        payload, idem_key=f"m2-fresh:{suffix}"))
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert result["inForceResultCategory"] == "ACCEPTED_STRUCTURAL_STATE"

    ident = store.get_payload(field_ref)
    assert ident is not None and ident["identityType"] == "FIELD"
    assert ident["anchorScopes"] == [{"scopeType": "FARM", "scopeRef": demo.FARM}]
    assert ident["currentPayloadRef"] == f"fieldpayload:m2.{suffix}"

    reg = _registry(store, materializer)
    entries = {e["identityRecordRef"]: e for e in reg["currentState"]["identities"]}
    assert field_ref in entries
    assert entries[field_ref]["currentPayload"]["declaredArea"]["value"] == 0.8


# ---------------------------------------------------------------------------
# supersession: current payload updates, prior survives, dependents stale (D12)
# ---------------------------------------------------------------------------

def test_g1_supersede_field_payload_updates_current_and_stales_materialization(
        pipeline, store, materializer):
    suffix = uid()
    field_ref = f"field:m2super.{suffix}"

    def field_payload(payload_id, area):
        return {
            "schemaVersion": "ofarm.fieldidentitypayload.v0.1",
            "fieldidentitypayloadId": payload_id,
            "identityRecordRef": field_ref,
            "recordedAt": now_iso(),
            "displayName": "M2 supersede field (fictional)",
            "parentFarmIdentityRef": demo.FARM,
            "declaredArea": {"value": area, "unitCode": "har"},
        }

    p1_id = f"fieldpayload:m2super.{suffix}.v1"
    first = pipeline.commit(demo.structure_submission(
        field_payload(p1_id, 1.0), idem_key=f"m2-super-a:{suffix}"))
    assert first["decisionOutcome"] == "PROMOTE_ACCEPTED"
    c1 = first["emittedAcceptedConsequenceRefs"][0]

    # materialize the registry, then supersede; the registry must stale (D12)
    reg1 = _registry(store, materializer)
    key_digest = reg1["keyDigest"]
    entries1 = {e["identityRecordRef"]: e for e in reg1["currentState"]["identities"]}
    assert entries1[field_ref]["currentPayload"]["declaredArea"]["value"] == 1.0

    p2_id = f"fieldpayload:m2super.{suffix}.v2"
    correction = demo.structure_submission(
        field_payload(p2_id, 2.0), idem_key=f"m2-super-b:{suffix}", supersedes=c1)
    second = pipeline.commit(correction)
    assert second["decisionOutcome"] == "PROMOTE_ACCEPTED"
    c2 = second["emittedAcceptedConsequenceRefs"][0]

    # basis-set invalidation: the live registry materialization is now STALE
    with store.conn.cursor() as cur:
        cur.execute(
            "SELECT freshness FROM derived_materialization "
            "WHERE key_digest = %s AND superseded_by IS NULL", (key_digest,))
        assert cur.fetchone()["freshness"] == "STALE", \
            "superseding a structural consequence must stale the identity registry"

    # current payload updates; the prior payload and consequence both survive
    assert store.record_exists(p1_id), "prior payload must survive (append-only)"
    assert store.record_exists(c1), "prior consequence must survive (append-only)"
    in_force = {r["record_id"] for r in store.in_force_consequences(demo.FARM)}
    assert c1 not in in_force and c2 in in_force

    reg2 = _registry(store, materializer)
    entries2 = {e["identityRecordRef"]: e for e in reg2["currentState"]["identities"]}
    assert entries2[field_ref]["currentPayload"]["declaredArea"]["value"] == 2.0
    assert entries2[field_ref]["currentPayloadRef"] == p2_id
    # exactly one IdentityRecord for the field — revision did not duplicate it
    fields = [r for r in store.find_by_kind("ofarm.identityrecord.v0.1")
              if r["record_id"] == field_ref]
    assert len(fields) == 1


# ---------------------------------------------------------------------------
# refusals: malformed / absent / wrong-kind carrier, wrong-kind subject —
# governed, never a crash, draft retained
# ---------------------------------------------------------------------------

def test_g1_absent_payload_refuses_governably(pipeline, store):
    sub = demo.structure_submission(farm_identity_payload_placeholder(),
                                    idem_key=f"m2-absent:{uid()}")
    del sub["payload"]
    result = pipeline.commit(sub)
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"
    # draft retained, no consequence promoted
    assert not result.get("emittedAcceptedConsequenceRefs")


def test_g1_malformed_payload_refuses_governably(pipeline):
    # a structure carrier missing required identity-payload fields
    bad = {"schemaVersion": "ofarm.fieldidentitypayload.v0.1",
           "fieldidentitypayloadId": "fieldpayload:m2bad"}
    result = pipeline.commit(demo.structure_submission(
        bad, idem_key=f"m2-malformed:{uid()}"))
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"


def test_g1_wrong_kind_carrier_refuses(pipeline):
    # a real, valid contract record that is NOT an identity payload
    not_identity = {
        "schemaVersion": "ofarm.evidencerecord.v0.1",
        "evidenceRecordId": f"evidence:m2wrong.{uid()}",
        "evidenceClass": "DOCUMENT", "capturedAt": now_iso(), "recordedAt": now_iso(),
        "capturedByPartyRef": demo.FARMER, "rawAssetRef": "asset:m2wrong",
        "rawAssetDigest": "sha256:" + "ef" * 32, "evidenceState": "CAPTURED"}
    result = pipeline.commit(demo.structure_submission(
        not_identity, idem_key=f"m2-wrongkind:{uid()}"))
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"


def test_g1_wrong_kind_subject_refuses_without_crash(pipeline):
    sub = demo.structure_submission(farm_identity_payload_placeholder(),
                                    idem_key=f"m2-subj:{uid()}")
    sub["subjectType"] = "OTHER"   # not a promotable consequence subject type
    sub["subjectRef"] = "thing:not-an-identity"
    result = pipeline.commit(sub)
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "IDENTITY_UNRESOLVED"


def farm_identity_payload_placeholder() -> dict:
    """A schema-valid identity payload for a fresh farm id, used where the
    refusal under test is NOT about the payload itself (so it must be valid)."""
    s = uid()
    return {
        "schemaVersion": "ofarm.farmidentitypayload.v0.1",
        "farmidentitypayloadId": f"farmpayload:m2ph.{s}",
        "identityRecordRef": f"farm:m2ph.{s}",
        "recordedAt": now_iso(),
        "displayName": "M2 placeholder farm (fictional)",
        "operatorPartyRef": demo.FARMER,
    }
