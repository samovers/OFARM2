"""M2 G1 — governed structure-identity commit path (incl. D17 / D18).

Engineering tests, NOT part of the named conformance suite (conftest only
records test_conformance.py into the evidence file). They pin the G1 behavior
and the PR-#9 steward decisions:
  * Farm/Field/CropCycle/Equipment/AppliedResource committed through the gate
    chain as STRUCTURE_ASSERTIONs carrying typed identity payloads ->
    ACCEPTED_STRUCTURAL_STATE; an identity registry materializing the current
    payload per identity from in-force structural consequences.
  * D17 — bounded self-acceptance: only farm-owned setup identities, only with
    semantic validation + REVIEW_ACCEPT authority; anything else routes to a
    distinct reviewer.
  * D18 — a re-assertion of an existing identity must explicitly supersede that
    identity's current structural consequence (never silent latest-wins).
All data is fictional and format-true (privacy rule 1, D14). No SI bindings (P4).
"""
from __future__ import annotations

import uuid

from kernel import config, demo, policy
from kernel.context import now_iso


def uid() -> str:
    return uuid.uuid4().hex[:10]


DEMO_IDENTITIES = {
    demo.FARM: "FARM",
    demo.FIELD: "FIELD",
    demo.CYCLE: "CROP_CYCLE",
    demo.SPRAYER: "EQUIPMENT",
    demo.APPLIED_RESOURCE: "APPLIED_RESOURCE",
}


def _field_payload(identity_ref: str, *, payload_id: str, area: float = 1.0,
                   parent: str = demo.FARM) -> dict:
    return {
        "schemaVersion": "ofarm.fieldidentitypayload.v0.1",
        "fieldidentitypayloadId": payload_id,
        "identityRecordRef": identity_ref,
        "recordedAt": now_iso(),
        "displayName": "M2 test field (fictional)",
        "parentFarmIdentityRef": parent,
        "declaredArea": {"value": area, "unitCode": "har"},
    }


def _registry(store, materializer, farm_ref=demo.FARM) -> dict:
    with store.tx() as cur:
        return materializer.materialize_identity_registry(cur, farm_ref)


def _entries(reg) -> dict:
    return {e["identityRecordRef"]: e for e in reg["currentState"]["identities"]}


def _structural_consequence_by_identity(store, farm_ref=demo.FARM) -> dict:
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


def _count_in_force_structural(store, identity_ref, farm_ref=demo.FARM) -> int:
    n = 0
    for row in store.in_force_consequences(farm_ref):
        e = store.edges_from(row["payload"]["sourceEventRef"], "STRUCTURE_PAYLOAD")
        if e and (p := store.get_payload(e[0]["dst_record_id"])) \
                and p["identityRecordRef"] == identity_ref:
            n += 1
    return n


def _inject_conflicting_structural_state(store):
    """Fabricate a throwaway farm whose single identity has TWO in-force
    structural consequences — the conflict D18 normally prevents (e.g. the H1
    concurrent-write race). Clearly synthetic and isolated on its own farm so it
    never pollutes the demo farm's registry. Records are fully reachable
    (PROMOTION_EMITS + a PROMOTE_ACCEPTED trace) so global invariants still hold."""
    s = uid()
    farm, field, event = f"farm:m2conf.{s}", f"field:m2conf.{s}", f"event:m2conf.{s}"
    review, trace = f"review:m2conf.{s}", f"promtrace:m2conf.{s}"
    c1, c2 = f"conseq:m2conf.{s}.a", f"conseq:m2conf.{s}.b"
    t = now_iso()
    anchors = [{"scopeType": "FARM", "scopeRef": farm}]
    with store.tx() as cur:
        store.insert_record(cur, {
            "schemaVersion": "ofarm.semanticeventenvelope.v0.1", "semanticEventId": event,
            "primaryEventFamily": "StructureEvent",
            "dominantSemanticConsequence": "fabricated conflict (test)",
            "anchorScopes": anchors, "subjectRefs": [farm],
            "timeSemantics": {"eventTime": t, "recordTime": t}})
        store.insert_record(cur, {
            "schemaVersion": "ofarm.fieldidentitypayload.v0.1",
            "fieldidentitypayloadId": f"fp:m2conf.{s}", "identityRecordRef": field,
            "recordedAt": t, "displayName": "conflict field (fictional)",
            "parentFarmIdentityRef": farm, "declaredArea": {"value": 1.0, "unitCode": "har"}})
        store.add_edge(cur, "STRUCTURE_PAYLOAD", event, f"fp:m2conf.{s}")
        store.insert_record(cur, {
            "schemaVersion": "ofarm.reviewdecision.v0.1", "reviewDecisionId": review,
            "reviewedArtifactFamily": "ASSERTION_RECORD", "reviewedArtifactRef": event,
            "reviewAction": "REVIEW_ACCEPT", "anchorScopes": anchors,
            "decidedByPartyRef": demo.FARMER, "decidedAt": t,
            "decisionOutcomeState": "ACCEPTED", "notes": "fabricated test review"})
        for cid in (c1, c2):
            store.insert_record(cur, {
                "schemaVersion": "ofarm.acceptedeventconsequence.v0.1",
                "acceptedEventConsequenceId": cid, "consequenceType": "STATE_CHANGE_ACCEPTED",
                "sourceEventRef": event, "acceptedByReviewDecisionRef": review,
                "subject": {"subjectType": "FARM", "subjectRef": farm},
                "anchorScopes": anchors, "acceptedAt": t, "inForceState": "IN_FORCE"})
        store.insert_record(cur, {
            "schemaVersion": "ofarm.promotiontrace.v0.1", "promotionTraceId": trace,
            "requestId": f"cir:m2conf.{s}", "evaluatedAt": t, "semanticEventRef": event,
            "commitClass": "STRUCTURE_ASSERTION", "primaryEventFamily": "StructureEvent",
            "idempotencyKey": f"cir:m2conf.{s}", "idempotencyDisposition": "NEW_REQUEST",
            "gateSequence": [{"gate": "REVIEW_PROMOTION", "outcome": "PROMOTE_ACCEPTED"}],
            "finalOutcome": "PROMOTE_ACCEPTED", "traceSummary": "fabricated conflict (test)",
            "emittedReviewDecisionRefs": [review], "emittedAcceptedConsequenceRefs": [c1, c2]})
        for ref in (event, review, c1, c2):
            store.add_edge(cur, "PROMOTION_EMITS", trace, ref)
    return farm, field


def test_g1_registry_conflict_marks_materialization_invalid(store, materializer):
    """H2 (hostile re-review): an unresolved structural conflict is NOT fresh
    current state — the registry surfaces the conflict AND marks the
    materialization INVALID (snapshot + derived row + return), never FRESH."""
    farm, field = _inject_conflicting_structural_state(store)
    with store.tx() as cur:
        reg = materializer.materialize_identity_registry(cur, farm)
    assert reg["freshness"] == "INVALID"
    assert reg["currentState"]["conflictCount"] >= 1
    entries = {e["identityRecordRef"]: e for e in reg["currentState"]["identities"]}
    assert entries[field].get("conflict") is True
    with store.conn.cursor() as cur:
        cur.execute("SELECT freshness FROM derived_materialization "
                    "WHERE key_digest = %s AND superseded_by IS NULL", (reg["keyDigest"],))
        assert cur.fetchone()["freshness"] == "INVALID"


def _accept(pipeline, assertion_ref, *, key):
    return pipeline.commit({
        "commitClass": "GOVERNANCE_DECISION", "ingressChannel": "MANUAL_UI",
        "actingPartyRef": demo.ADVISOR, "farmRef": demo.FARM,
        "idempotencyKey": key, "decisionTime": now_iso(),
        "reviewTargetAssertionRef": assertion_ref,
        "reviewRationale": "advisor review of a queued structure assertion (synthetic, D13)",
    })


# ---------------------------------------------------------------------------
# onboarding via committed structure assertions (D17 #2)
# ---------------------------------------------------------------------------

def test_g1_demo_identities_were_committed_not_bootstrapped(store):
    """Each demo identity is a real IdentityRecord created on the commit path
    (createdByAssertionRecordRef set), reachable from an in-force structural
    consequence — never a direct bootstrap. currentPayloadRef is intentionally
    absent (the registry, not the append-only IdentityRecord, is the source of
    the current payload)."""
    by_identity = _structural_consequence_by_identity(store)
    for identity_ref, expected_type in DEMO_IDENTITIES.items():
        row = store.get_record(identity_ref)
        assert row is not None and row["record_kind"] == "ofarm.identityrecord.v0.1"
        ident = row["payload"]
        assert ident["identityType"] == expected_type
        assert ident.get("createdByAssertionRecordRef"), \
            f"{identity_ref} has no creating assertion (bootstrapped?)"
        assert "currentPayloadRef" not in ident, \
            "IdentityRecord must not claim a current payload it cannot keep current"
        assert identity_ref in by_identity, f"{identity_ref}: no in-force structural consequence"
        c = by_identity[identity_ref]
        assert c["consequenceType"] == "STATE_CHANGE_ACCEPTED"
        assert len(store.edges_to(c["acceptedEventConsequenceId"], "PROMOTION_EMITS")) == 1


def test_g1_registry_materializes_current_payload_per_type(store, materializer):
    """The identity registry materializes the current typed payload per identity
    from in-force structural consequences — all five demo types, no conflicts."""
    reg = _registry(store, materializer)
    state = reg["currentState"]
    assert state["stateKind"] == "ofarm.identity-registry.v0_1" and state["derived"] is True
    assert state["conflictCount"] == 0
    entries = _entries(reg)
    for identity_ref, expected_type in DEMO_IDENTITIES.items():
        assert identity_ref in entries
        e = entries[identity_ref]
        assert e["identityType"] == expected_type and e["lifecycleState"] == "ACTIVE"
        payload = e["currentPayload"]
        assert payload["identityRecordRef"] == identity_ref
        assert policy.STRUCTURE_PAYLOAD_IDENTITY_TYPE[payload["schemaVersion"]] == expected_type
    assert reg["basisRef"] and reg["snapshotRef"]


# ---------------------------------------------------------------------------
# D17 #1 — a valid farm-owned structure assertion self-accepts
# ---------------------------------------------------------------------------

def test_g1_valid_structure_self_accepts_and_creates_identity(pipeline, store, materializer):
    suffix = uid()
    field_ref = f"field:m2.{suffix}"
    result = pipeline.commit(demo.structure_submission(
        _field_payload(field_ref, payload_id=f"fp:m2.{suffix}", area=0.8),
        idem_key=f"m2-fresh:{suffix}"))
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert result["inForceResultCategory"] == "ACCEPTED_STRUCTURAL_STATE"
    ident = store.get_payload(field_ref)
    assert ident["identityType"] == "FIELD"
    assert ident["anchorScopes"] == [{"scopeType": "FARM", "scopeRef": demo.FARM}]
    entries = _entries(_registry(store, materializer))
    assert entries[field_ref]["currentPayload"]["declaredArea"]["value"] == 0.8


# ---------------------------------------------------------------------------
# D17 #3 — off-farm / dangling / mismatched payload refs refuse governably
# ---------------------------------------------------------------------------

def test_g1_off_farm_parent_ref_refuses(pipeline):
    suffix = uid()
    payload = _field_payload(f"field:m2off.{suffix}", payload_id=f"fp:m2off.{suffix}",
                             parent="farm:some.other.holding")
    result = pipeline.commit(demo.structure_submission(payload, idem_key=f"m2-off:{suffix}"))
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "SCOPE_NOT_AUTHORIZED"


def test_g1_dangling_payload_evidence_ref_refuses(pipeline):
    suffix = uid()
    payload = _field_payload(f"field:m2dang.{suffix}", payload_id=f"fp:m2dang.{suffix}")
    payload["geometryEvidenceRef"] = f"evidence:does-not-exist.{suffix}"
    result = pipeline.commit(demo.structure_submission(payload, idem_key=f"m2-dang:{suffix}"))
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# D17 #4 / D18 #4 — existing identity of the wrong type refuses
# ---------------------------------------------------------------------------

def test_g1_existing_identity_wrong_type_refuses(pipeline):
    # a Field payload whose identityRecordRef names the demo SPRAYER (EQUIPMENT)
    suffix = uid()
    payload = _field_payload(demo.SPRAYER, payload_id=f"fp:m2wt.{suffix}")
    result = pipeline.commit(demo.structure_submission(payload, idem_key=f"m2-wt:{suffix}"))
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "IDENTITY_UNRESOLVED"


# ---------------------------------------------------------------------------
# D17 #5 / D18 #1 — re-assert an existing identity WITHOUT supersession
# ---------------------------------------------------------------------------

def test_g1_reassert_existing_without_supersession_retains_draft(pipeline, store, materializer):
    before = _entries(_registry(store, materializer))[demo.FIELD]["currentPayloadRef"]
    result = pipeline.commit(demo.structure_submission(
        _field_payload(demo.FIELD, payload_id=f"fp:m2re.{uid()}", area=99.0),
        idem_key=f"m2-re:{uid()}"))
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "CORRECTION_REQUIRED"
    assert not result.get("emittedAcceptedConsequenceRefs")
    # the demo field's current payload is unchanged (no silent latest-wins)
    after = _entries(_registry(store, materializer))[demo.FIELD]["currentPayloadRef"]
    assert after == before


# ---------------------------------------------------------------------------
# D18 #2 / #5 — supersede with the correct ref updates current, stales, no conflict
# ---------------------------------------------------------------------------

def test_g1_supersede_updates_current_preserves_prior_and_stales(pipeline, store, materializer):
    suffix = uid()
    field_ref = f"field:m2sup.{suffix}"
    p1 = f"fp:m2sup.{suffix}.v1"
    first = pipeline.commit(demo.structure_submission(
        _field_payload(field_ref, payload_id=p1, area=1.0), idem_key=f"m2-sa:{suffix}"))
    assert first["decisionOutcome"] == "PROMOTE_ACCEPTED"
    c1 = first["emittedAcceptedConsequenceRefs"][0]

    reg1 = _registry(store, materializer)
    key_digest = reg1["keyDigest"]
    assert _entries(reg1)[field_ref]["currentPayload"]["declaredArea"]["value"] == 1.0

    p2 = f"fp:m2sup.{suffix}.v2"
    second = pipeline.commit(demo.structure_submission(
        _field_payload(field_ref, payload_id=p2, area=2.0),
        idem_key=f"m2-sb:{suffix}", supersedes=c1))
    assert second["decisionOutcome"] == "PROMOTE_ACCEPTED"
    c2 = second["emittedAcceptedConsequenceRefs"][0]

    # D12: the live registry materialization is staled by the supersession
    with store.conn.cursor() as cur:
        cur.execute("SELECT freshness FROM derived_materialization "
                    "WHERE key_digest = %s AND superseded_by IS NULL", (key_digest,))
        assert cur.fetchone()["freshness"] == "STALE"

    assert store.record_exists(p1) and store.record_exists(c1)  # append-only
    in_force = {r["record_id"] for r in store.in_force_consequences(demo.FARM)}
    assert c1 not in in_force and c2 in in_force

    reg2 = _registry(store, materializer)
    entries2 = _entries(reg2)
    assert entries2[field_ref]["currentPayload"]["declaredArea"]["value"] == 2.0
    assert entries2[field_ref]["currentPayloadRef"] == p2
    assert "conflict" not in entries2[field_ref]      # never two competing payloads
    assert reg2["currentState"]["conflictCount"] == 0
    ids = [r["record_id"] for r in store.find_by_kind("ofarm.identityrecord.v0.1")
           if r["record_id"] == field_ref]
    assert len(ids) == 1   # revision did not duplicate the IdentityRecord


# ---------------------------------------------------------------------------
# D18 #3 — supersedesConsequenceRef pointing at ANOTHER identity refuses
# ---------------------------------------------------------------------------

def test_g1_supersede_other_identitys_consequence_refuses(pipeline):
    sa, sb = uid(), uid()
    fa, fb = f"field:m2xa.{sa}", f"field:m2xb.{sb}"
    ra = pipeline.commit(demo.structure_submission(
        _field_payload(fa, payload_id=f"fp:m2xa.{sa}"), idem_key=f"m2-xa:{sa}"))
    rb = pipeline.commit(demo.structure_submission(
        _field_payload(fb, payload_id=f"fp:m2xb.{sb}"), idem_key=f"m2-xb:{sb}"))
    ca = ra["emittedAcceptedConsequenceRefs"][0]
    cb = rb["emittedAcceptedConsequenceRefs"][0]
    assert ca and cb
    # re-assert fa but name fb's consequence as the supersession target
    result = pipeline.commit(demo.structure_submission(
        _field_payload(fa, payload_id=f"fp:m2xa.{sa}.v2", area=3.0),
        idem_key=f"m2-xc:{uid()}", supersedes=cb))
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "SUPERSEDED_RECORD_USED"


# ---------------------------------------------------------------------------
# D17 #6 — a QUEUED structure supersession, accepted by a distinct reviewer,
# emits LINEAGE_SUPERSEDES and updates the registry
# ---------------------------------------------------------------------------

def test_g1_queued_structure_supersession_preserves_lineage(pipeline, store, materializer):
    suffix = uid()
    field_ref = f"field:m2q.{suffix}"
    first = pipeline.commit(demo.structure_submission(
        _field_payload(field_ref, payload_id=f"fp:m2q.{suffix}.v1", area=1.0),
        idem_key=f"m2-qa:{suffix}"))
    c1 = first["emittedAcceptedConsequenceRefs"][0]

    # farmer queues the correction (confirm=False) instead of self-accepting
    pending = pipeline.commit(demo.structure_submission(
        _field_payload(field_ref, payload_id=f"fp:m2q.{suffix}.v2", area=2.0),
        idem_key=f"m2-qb:{suffix}", supersedes=c1, confirm=False))
    assert pending["decisionOutcome"] == "RETAIN_DRAFT"
    pending_assertion = pending["emittedAssertionRecordRefs"][0]

    # a DISTINCT reviewer (advisor) accepts the queued correction
    accept = pipeline.commit({
        "commitClass": "GOVERNANCE_DECISION", "ingressChannel": "MANUAL_UI",
        "actingPartyRef": demo.ADVISOR, "farmRef": demo.FARM,
        "idempotencyKey": f"m2-qacc:{suffix}", "decisionTime": now_iso(),
        "reviewTargetAssertionRef": pending_assertion,
        "reviewRationale": "advisor accepts the queued field correction (synthetic actor, D13)",
    })
    assert accept["decisionOutcome"] == "PROMOTE_ACCEPTED"
    c2 = accept["emittedAcceptedConsequenceRefs"][0]

    # lineage preserved: the prior consequence leaves force, the new one carries it
    assert store.edges_to(c1, "LINEAGE_SUPERSEDES"), "queued acceptance must emit LINEAGE_SUPERSEDES"
    in_force = {r["record_id"] for r in store.in_force_consequences(demo.FARM)}
    assert c1 not in in_force and c2 in in_force
    entries = _entries(_registry(store, materializer))
    assert entries[field_ref]["currentPayload"]["declaredArea"]["value"] == 2.0
    assert "conflict" not in entries[field_ref]


# ---------------------------------------------------------------------------
# acceptance-time D18 re-validation (PR #9 re-review TOCTOU blockers): the world
# can change between queuing and acceptance — the accept must re-check, never
# silently create a second in-force structural consequence
# ---------------------------------------------------------------------------

def test_g1_stale_queued_creation_refused_after_identity_gains_state(pipeline, store):
    """Queue a creation (no supersedes); then the identity gains in-force state
    by another commit; accepting the now-stale queued creation must refuse
    (D18), not create a second in-force consequence."""
    s = uid()
    field_ref = f"field:m2tt.{s}"
    pending = pipeline.commit(demo.structure_submission(
        _field_payload(field_ref, payload_id=f"fp:m2tt.{s}.v1", area=1.0),
        idem_key=f"m2-tt-a:{s}", confirm=False))
    assert pending["decisionOutcome"] == "RETAIN_DRAFT"
    a1 = pending["emittedAssertionRecordRefs"][0]

    promoted = pipeline.commit(demo.structure_submission(
        _field_payload(field_ref, payload_id=f"fp:m2tt.{s}.v2", area=2.0),
        idem_key=f"m2-tt-b:{s}"))
    assert promoted["decisionOutcome"] == "PROMOTE_ACCEPTED"

    accept = _accept(pipeline, a1, key=f"m2-tt-acc:{s}")
    assert accept["decisionOutcome"] == "RETAIN_DRAFT"
    assert accept["problems"][0]["reasonCode"] == "CORRECTION_REQUIRED"
    assert _count_in_force_structural(store, field_ref) == 1


def test_g1_racing_queued_corrections_second_accept_refused(pipeline, store):
    """Two queued corrections both naming C1; accepting the first supersedes C1;
    accepting the second (whose target is no longer current) must refuse, never
    create a second in-force consequence (D18 / no silent latest-wins)."""
    s = uid()
    field_ref = f"field:m2race.{s}"
    first = pipeline.commit(demo.structure_submission(
        _field_payload(field_ref, payload_id=f"fp:m2race.{s}.v1", area=1.0),
        idem_key=f"m2-r-a:{s}"))
    c1 = first["emittedAcceptedConsequenceRefs"][0]

    p2 = pipeline.commit(demo.structure_submission(
        _field_payload(field_ref, payload_id=f"fp:m2race.{s}.v2", area=2.0),
        idem_key=f"m2-r-b:{s}", supersedes=c1, confirm=False))
    p3 = pipeline.commit(demo.structure_submission(
        _field_payload(field_ref, payload_id=f"fp:m2race.{s}.v3", area=3.0),
        idem_key=f"m2-r-c:{s}", supersedes=c1, confirm=False))
    a2 = p2["emittedAssertionRecordRefs"][0]
    a3 = p3["emittedAssertionRecordRefs"][0]

    acc2 = _accept(pipeline, a2, key=f"m2-r-acc2:{s}")
    assert acc2["decisionOutcome"] == "PROMOTE_ACCEPTED"
    acc3 = _accept(pipeline, a3, key=f"m2-r-acc3:{s}")
    assert acc3["decisionOutcome"] == "RETAIN_DRAFT"
    assert acc3["problems"][0]["reasonCode"] == "SUPERSEDED_RECORD_USED"
    assert _count_in_force_structural(store, field_ref) == 1


# ---------------------------------------------------------------------------
# D17 #8 — self-acceptance needs REVIEW_ACCEPT: a structure-only holder cannot
# self-promote (it routes to review instead)
# ---------------------------------------------------------------------------

def test_g1_structure_holder_without_review_accept_cannot_self_promote(pipeline, store):
    suffix = uid()
    structurer = f"party:m2s.{suffix}"
    with store.tx() as cur:
        store.insert_record(cur, {
            "schemaVersion": "ofarm.party.v0.1", "partyId": structurer,
            "partyClass": "NATURAL_PERSON", "displayName": "M2 Structurer (fictional)",
            "partyState": "ACTIVE", "recordedAt": now_iso()})
        store.insert_record(cur, {
            "schemaVersion": "ofarm.authoritygrant.v0.1",
            "authorityGrantId": f"grant:m2s.{suffix}",
            "grantedByPartyRef": demo.FARMER,
            "grantTarget": {"targetKind": "PARTY", "targetRef": structurer},
            "targetScope": {"scopeType": "FARM", "scopeRef": demo.FARM},
            "authorityActionClasses": ["ASSERT_STRUCTURE"],
            "validFrom": demo.VALID_FROM, "inheritanceMode": "DESCENDANT_SCOPES",
            "grantState": "ACTIVE", "purpose": "structure-only, no REVIEW_ACCEPT (D17 test)"})
    field_ref = f"field:m2s.{suffix}"
    result = pipeline.commit(demo.structure_submission(
        _field_payload(field_ref, payload_id=f"fp:m2s.{suffix}"),
        idem_key=f"m2-s:{suffix}", actor_ref=structurer))
    assert result["decisionOutcome"] == "REQUIRE_REVIEW", \
        "a structure holder without REVIEW_ACCEPT must not self-promote (D17)"
    assert store.get_record(field_ref) is None   # not promoted -> no identity created


# ---------------------------------------------------------------------------
# D17 #7 — compliance self-review remains blocked/routed exactly as before
# ---------------------------------------------------------------------------

def test_g1_compliance_self_review_still_routes(pipeline):
    suffix = uid()
    result = pipeline.commit({
        "commitClass": "COMPLIANCE_ASSERTION", "ingressChannel": "MANUAL_UI",
        "actingPartyRef": demo.FARMER, "farmRef": demo.FARM,
        "idempotencyKey": f"m2-comp:{suffix}", "eventTime": "2026-06-10T07:30:00Z",
        "evidenceRefs": [demo.PHOTO_EVIDENCE], "confirmAccept": True,
        "requestedPromotionTarget": "COMPLIANCE_FACT",
        "payload": {
            "complianceClaim": {
                "statement": "fictional self-claim (must not self-promote)",
                "assertedStatus": "CLAIMED_COMPLIANT",
                "governingRuleRefs": [config.EVIDENCE_POLICY_REF],
                "subjectScopeRef": demo.FARM}},
    })
    assert result["decisionOutcome"] != "PROMOTE_ACCEPTED", \
        "compliance assertions must never self-promote (D8 unchanged)"


# ---------------------------------------------------------------------------
# refusals: absent / malformed / wrong-kind carrier; wrong-kind subject
# ---------------------------------------------------------------------------

def _valid_farm_placeholder() -> dict:
    s = uid()
    return {
        "schemaVersion": "ofarm.farmidentitypayload.v0.1",
        "farmidentitypayloadId": f"fp:m2ph.{s}",
        "identityRecordRef": f"farm:m2ph.{s}",
        "recordedAt": now_iso(),
        "displayName": "M2 placeholder farm (fictional)",
        "operatorPartyRef": demo.FARMER,
    }


def test_g1_absent_payload_refuses(pipeline):
    sub = demo.structure_submission(_valid_farm_placeholder(), idem_key=f"m2-abs:{uid()}")
    del sub["payload"]
    result = pipeline.commit(sub)
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"
    assert not result.get("emittedAcceptedConsequenceRefs")


def test_g1_malformed_payload_refuses(pipeline):
    bad = {"schemaVersion": "ofarm.fieldidentitypayload.v0.1",
           "fieldidentitypayloadId": "fp:m2bad"}
    result = pipeline.commit(demo.structure_submission(bad, idem_key=f"m2-mal:{uid()}"))
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"


def test_g1_wrong_kind_carrier_refuses(pipeline):
    not_identity = {
        "schemaVersion": "ofarm.evidencerecord.v0.1",
        "evidenceRecordId": f"evidence:m2wk.{uid()}",
        "evidenceClass": "DOCUMENT", "capturedAt": now_iso(), "recordedAt": now_iso(),
        "capturedByPartyRef": demo.FARMER, "rawAssetRef": "asset:m2wk",
        "rawAssetDigest": "sha256:" + "ef" * 32, "evidenceState": "CAPTURED"}
    result = pipeline.commit(demo.structure_submission(not_identity, idem_key=f"m2-wk:{uid()}"))
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"


def test_g1_wrong_kind_subject_refuses_without_crash(pipeline):
    sub = demo.structure_submission(_valid_farm_placeholder(), idem_key=f"m2-subj:{uid()}")
    sub["subjectType"] = "OTHER"
    sub["subjectRef"] = "thing:not-an-identity"
    result = pipeline.commit(sub)
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "IDENTITY_UNRESOLVED"
