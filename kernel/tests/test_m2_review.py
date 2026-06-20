"""M2 G5 — the REJECT (G5-2) and CONTEST (G5-4) review verbs.

Engineering tests, NOT part of the named conformance suite. They pin the
settled review/dispute semantics (docs/REVIEW_DISPUTE_SEMANTICS.md, D20 + D21):
REJECT of a queued assertion is the append-only mirror of acceptance minus the
consequence (a ReviewDecision REVIEW_REJECT_OR_CONTEST / REJECTED + a REVIEW
edge, no consequence, RETAIN_DRAFT, terminal, no materialization touched);
CONTEST of an ALREADY IN-FORCE consequence appends a ReviewDecision (CONTESTED)
+ a DISPUTE edge, emits no consequence, stales dependent materializations (D12),
qualifies disputeStatus, and refuses a high-consequence freeze — resolved only by
a superseding CORRECTION. Both are authorized by the DISTINCT
REVIEW_REJECT_OR_CONTEST action. All identifiers fictional and format-true
(privacy rule 1).
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from kernel import context, demo
from kernel.api import create_app


def uid():
    return uuid.uuid4().hex[:8]


def _client(store):
    # shim mode: the X-Acting-Party header is the transport principal (the
    # binding contract is identical to OIDC — UNSUPPORTED_SURFACES.md)
    return TestClient(create_app(store, oidc=None))


def _hdr(party):
    return {"x-acting-party": party}


def _queue_op(pipeline, actor=demo.FARMER):
    """A queued routine operation claim (PENDING_REVIEW), asserted by `actor`."""
    r = pipeline.commit(demo.spray_submission(
        f"rej:{uid()}", erp_id=f"erp:rej.{uid()}", actor_ref=actor, confirm=False))
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    return r["emittedAssertionRecordRefs"][0]


def _reject(client, target, *, party=demo.ADVISOR, rationale="advisor declines: "
            "the claim is not supportable on the evidence presented",
            evidence=None, key=None):
    body = {"farmRef": demo.FARM, "assertionRef": target, "rationale": rationale}
    if evidence is not None:
        body["evidenceRefs"] = evidence
    if key is not None:
        body["idempotencyKey"] = key
    return client.post("/review/reject", json=body, headers=_hdr(party))


# ---------------------------------------------------------------------------
# the core decline: append-only ReviewDecision, no consequence, terminal
# ---------------------------------------------------------------------------

def test_reject_appends_decline_no_consequence(store, pipeline):
    client = _client(store)
    target = _queue_op(pipeline)
    before = len(store.find_by_kind("ofarm.acceptedeventconsequence.v0.1"))

    r = _reject(client, target)
    assert r.status_code == 200
    body = r.json()
    assert body["decisionOutcome"] == "RETAIN_DRAFT"
    assert "emittedAcceptedConsequenceRefs" not in body, "a decline promotes nothing"
    review_id = body["emittedReviewDecisionRefs"][0]

    review = store.get_record(review_id)["payload"]
    assert review["reviewAction"] == "REVIEW_REJECT_OR_CONTEST"
    assert review["decisionOutcomeState"] == "REJECTED"
    assert review["decidedByPartyRef"] == demo.ADVISOR
    assert review["reviewedArtifactRef"] == target
    assert review["notes"].startswith("rejection:")
    assert "resultingAcceptedConsequenceRefs" not in review

    # append-only: the queued assertion is NEVER edited; its terminal REJECTED
    # disposition is derived from the new REVIEW edge
    assert store.get_record(target)["payload"]["claimState"] == "PENDING_REVIEW"
    review_edges = [e["dst_record_id"] for e in store.edges_from(target, "REVIEW")]
    assert review_edges == [review_id]
    # no consequence emitted -> no materialization basis member created
    assert len(store.find_by_kind("ofarm.acceptedeventconsequence.v0.1")) == before


def test_reject_leaves_pending_queue(store, pipeline, outputs):
    client = _client(store)
    target = _queue_op(pipeline)
    # before the decision it is a pending exception on the farm
    assert target in {p["assertionRef"] for p in outputs._pending_claims(demo.FARM)}
    assert _reject(client, target).json()["decisionOutcome"] == "RETAIN_DRAFT"
    # after the decline the REVIEW-edge filter removes it from the queue, and it
    # never appears in force (no consequence was emitted)
    assert target not in {p["assertionRef"] for p in outputs._pending_claims(demo.FARM)}


# ---------------------------------------------------------------------------
# authority: the DISTINCT, non-inheriting REVIEW_REJECT_OR_CONTEST action
# ---------------------------------------------------------------------------

def test_reject_requires_distinct_reject_authority(store, pipeline):
    client = _client(store)
    target = _queue_op(pipeline)
    # the FARMER holds REVIEW_ACCEPT but NOT REVIEW_REJECT_OR_CONTEST (NO_INHERIT)
    r = _reject(client, target, party=demo.FARMER)
    assert r.status_code == 200
    body = r.json()
    assert body["decisionOutcome"] == "DENY"
    assert body["problems"][0]["reasonCode"] == "AUTHORITY_DENIED"
    # the target was NOT decided — no REVIEW edge, still acceptable
    assert store.edges_from(target, "REVIEW") == []


# ---------------------------------------------------------------------------
# terminality: a decided target refuses any later review
# ---------------------------------------------------------------------------

def test_reject_is_terminal_for_the_target(store, pipeline):
    client = _client(store)
    target = _queue_op(pipeline)
    assert _reject(client, target).json()["decisionOutcome"] == "RETAIN_DRAFT"

    # a later ACCEPT of the rejected target is refused (already reviewed)
    later_accept = client.post("/review/accept",
                               json={"farmRef": demo.FARM, "assertionRef": target,
                                     "rationale": "trying to accept after rejection"},
                               headers=_hdr(demo.ADVISOR))
    aj = later_accept.json()
    assert aj["decisionOutcome"] == "RETAIN_DRAFT"
    assert aj["problems"][0]["reasonCode"] == "SUPERSEDED_RECORD_USED"
    # a second REJECT is likewise refused
    again = _reject(client, target)
    assert again.json()["problems"][0]["reasonCode"] == "SUPERSEDED_RECORD_USED"


def test_accept_then_reject_is_refused(store, pipeline):
    client = _client(store)
    target = _queue_op(pipeline)
    # the farmer self-accepts the routine op claim (lawful, D8) -> in force
    acc = client.post("/review/accept",
                      json={"farmRef": demo.FARM, "assertionRef": target,
                            "rationale": "self-review of a routine op claim (D8)"},
                      headers=_hdr(demo.FARMER))
    assert acc.json()["decisionOutcome"] == "PROMOTE_ACCEPTED"
    # the advisor cannot then reject an already-accepted claim
    r = _reject(client, target)
    assert r.json()["decisionOutcome"] == "RETAIN_DRAFT"
    assert r.json()["problems"][0]["reasonCode"] == "SUPERSEDED_RECORD_USED"


# ---------------------------------------------------------------------------
# validation: rationale required; target validity; evidence validated if given
# ---------------------------------------------------------------------------

def test_reject_requires_nonempty_rationale(store, pipeline):
    client = _client(store)
    target = _queue_op(pipeline)
    r = _reject(client, target, rationale="   ")
    body = r.json()
    assert body["decisionOutcome"] == "RETAIN_DRAFT"
    assert body["problems"][0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"
    assert store.edges_from(target, "REVIEW") == [], "a refused reject decides nothing"


def test_reject_target_must_resolve_to_an_assertion(store, pipeline):
    client = _client(store)
    # a ref that resolves to a non-assertion record (the farm party) is refused
    r = _reject(client, demo.FARMER)
    assert r.json()["problems"][0]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"


def test_reject_supplied_evidence_is_validated(store, pipeline):
    client = _client(store)
    target = _queue_op(pipeline)
    # an unresolved / wrong-kind evidence ref refuses the rejection
    r = _reject(client, target, evidence=["evidence:does.not.exist"])
    assert r.json()["problems"][0]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"
    assert store.edges_from(target, "REVIEW") == []


def test_reject_with_valid_evidence_succeeds(store, pipeline):
    client = _client(store)
    target = _queue_op(pipeline)
    r = _reject(client, target, evidence=[demo.PHOTO_EVIDENCE])
    assert r.json()["decisionOutcome"] == "RETAIN_DRAFT"
    review_id = r.json()["emittedReviewDecisionRefs"][0]
    review = store.get_record(review_id)["payload"]
    assert review["evidenceRefs"] == [demo.PHOTO_EVIDENCE]
    # the EVIDENCE edge is written only for the validated ref
    ev = [e["dst_record_id"] for e in store.edges_from(review_id, "EVIDENCE")]
    assert ev == [demo.PHOTO_EVIDENCE]


# ---------------------------------------------------------------------------
# fail-closed verb: CONTEST deferred; mismatched pair; unknown action
# ---------------------------------------------------------------------------

def _governance(pipeline, target, *, action=None, outcome=None, party=demo.ADVISOR):
    sub = {
        "commitClass": "GOVERNANCE_DECISION", "actingPartyRef": party,
        "farmRef": demo.FARM, "idempotencyKey": f"gov:{uid()}",
        "decisionTime": context.now_iso(),
        "reviewTargetAssertionRef": target,
        "reviewRationale": "a stated rationale for the governance decision",
    }
    if action is not None:
        sub["reviewAction"] = action
    if outcome is not None:
        sub["decisionOutcomeState"] = outcome
    return pipeline.commit(sub)


def test_contested_outcome_routes_to_contest_not_reject(store, pipeline):
    # G5-4: a CONTESTED outcome no longer refuses-as-unsupported (that was the
    # G5-2 forward guard) — it routes to the CONTEST branch, which targets a
    # consequence; aiming it at a queued ASSERTION is a wrong-kind refusal (never
    # silently handled as a reject).
    target = _queue_op(pipeline)
    r = _governance(pipeline, target,
                    action="REVIEW_REJECT_OR_CONTEST", outcome="CONTESTED")
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert r["problems"][0]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"
    assert store.edges_from(target, "REVIEW") == [] and store.edges_from(target, "DISPUTE") == []


def test_mismatched_action_outcome_is_refused(store, pipeline):
    target = _queue_op(pipeline)
    # the accept verb with a non-accept outcome is a governed refusal
    r = _governance(pipeline, target, action="REVIEW_ACCEPT", outcome="REJECTED")
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert r["problems"][0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"
    assert store.edges_from(target, "REVIEW") == []


def test_unrecognized_review_action_is_default_denied(store, pipeline):
    target = _queue_op(pipeline)
    for action in ("REVIEW_SUPERSEDE", "REVIEW_REQUEST", "TOTALLY_BOGUS"):
        r = _governance(pipeline, target, action=action, outcome="REJECTED")
        assert r["decisionOutcome"] == "DENY", f"{action} must default-deny"
        assert r["problems"][0]["reasonCode"] == "AUTHORITY_DENIED"
    assert store.edges_from(target, "REVIEW") == [], "no unwired verb decides anything"


# ---------------------------------------------------------------------------
# receipt / reachability (D3): the decline rides the normal trace machinery
# ---------------------------------------------------------------------------

def test_reject_decision_is_reachable_as_a_receipt(store, pipeline):
    client = _client(store)
    target = _queue_op(pipeline)
    body = _reject(client, target).json()
    review_id = body["emittedReviewDecisionRefs"][0]
    trace = store.get_record(body["promotionTraceRef"])["payload"]
    assert review_id in trace["emittedReviewDecisionRefs"]
    assert "emittedAcceptedConsequenceRefs" not in trace
    emits = [e["dst_record_id"]
             for e in store.edges_from(trace["promotionTraceId"], "PROMOTION_EMITS")]
    assert review_id in emits


# ---------------------------------------------------------------------------
# a rejected queued correction retires nothing (the prior stays in force)
# ---------------------------------------------------------------------------

def test_reject_of_queued_correction_abandons_supersession_intent(store, pipeline):
    client = _client(store)
    # an accepted routine op claim establishes an in-force consequence C1
    first = pipeline.commit(demo.spray_submission(
        f"corr-base:{uid()}", erp_id=f"erp:corr.base.{uid()}", confirm=True))
    assert first["decisionOutcome"] == "PROMOTE_ACCEPTED"
    c1 = first["emittedAcceptedConsequenceRefs"][0]
    # a queued CORRECTION intends to supersede C1 (LINEAGE_SUPERSEDES_INTENT)
    corr = demo.spray_submission(f"corr:{uid()}", erp_id=f"erp:corr.{uid()}",
                                 confirm=False)
    corr["supersedesConsequenceRef"] = c1
    queued = pipeline.commit(corr)
    correction = queued["emittedAssertionRecordRefs"][0]
    assert store.edges_from(correction, "LINEAGE_SUPERSEDES_INTENT")[0]["dst_record_id"] == c1

    # rejecting the correction retires nothing: C1 stays in force, the intent is
    # abandoned (never applied as a LINEAGE_SUPERSEDES), the intent edge survives
    assert _reject(client, correction).json()["decisionOutcome"] == "RETAIN_DRAFT"
    assert not store.is_superseded(c1), "the prior consequence stays in force"
    assert store.edges_to(c1, "LINEAGE_SUPERSEDES") == [], "no supersession applied"
    assert store.edges_from(correction, "LINEAGE_SUPERSEDES_INTENT"), \
        "the abandoned intent survives in history (append-only)"


# ---------------------------------------------------------------------------
# PR #18 review B1: a PRESENT-but-invalid reviewAction never falls through to
# accept (only an ABSENT field is the legacy REVIEW_ACCEPT default)
# ---------------------------------------------------------------------------

def test_present_but_invalid_review_action_never_accepts(store, pipeline):
    target = _queue_op(pipeline)
    base = {
        "commitClass": "GOVERNANCE_DECISION", "actingPartyRef": demo.ADVISOR,
        "farmRef": demo.FARM, "decisionTime": context.now_iso(),
        "reviewTargetAssertionRef": target,
        "reviewRationale": "a stated rationale",
    }
    # present falsey / non-string / unrecognized values must all refuse (default
    # deny), never be truthiness-coerced to accept
    for bad in ("", None, False, 0, [], "review_accept", "GARBAGE", 123):
        sub = dict(base, idempotencyKey=f"badact:{uid()}", reviewAction=bad)
        # decisionOutcomeState absent -> would be the dangerous "accept" path if
        # the verb were coerced; it must not be
        r = pipeline.commit(sub)
        assert r["decisionOutcome"] == "DENY", f"reviewAction={bad!r} must not accept"
        assert r["problems"][0]["reasonCode"] == "AUTHORITY_DENIED"
    # an absent reviewAction is still the legacy accept default (unchanged)
    assert store.edges_from(target, "REVIEW") == [], "no invalid verb decided anything"
    ok = pipeline.commit(dict(base, idempotencyKey=f"absent:{uid()}"))
    assert ok["decisionOutcome"] == "PROMOTE_ACCEPTED"  # absent -> accept


# ---------------------------------------------------------------------------
# PR #18 review B2: REJECT does not inherit the acceptance evidence-overcome
# guard — a NEEDS_EVIDENCE-routed claim is rejectable with no reviewer evidence,
# emits the ReviewDecision only, inserts no acceptance sufficiency case, and
# promotes nothing
# ---------------------------------------------------------------------------

CASE_KIND = "ofarm.evidencesufficiencycase.v0.2"
CONSEQ_KIND = "ofarm.acceptedeventconsequence.v0.1"


def test_reject_of_needs_evidence_claim_needs_no_reviewer_evidence(store, pipeline):
    client = _client(store)
    # a claim ROUTED for NEEDS_EVIDENCE (unverifiable actor attribution) — an
    # 'approve anyway' accept without new evidence would refuse
    stranger = f"party:rej.stranger.{uid()}"
    with store.tx() as cur:
        store.insert_record(cur, {
            "schemaVersion": "ofarm.party.v0.1", "partyId": stranger,
            "partyClass": "NATURAL_PERSON",
            "displayName": "Reject Stranger (fictional)",
            "partyState": "ACTIVE", "recordedAt": context.now_iso()})
    routed = demo.spray_submission(f"rej-ne:{uid()}", erp_id=f"erp:rej.ne.{uid()}")
    routed["payload"]["actor"]["actorPartyRef"] = stranger
    res = pipeline.commit(routed)
    assert res["decisionOutcome"] == "REQUIRE_REVIEW"
    target = res["emittedAssertionRecordRefs"][0]

    cases_before = len(store.find_by_kind(CASE_KIND))
    conseq_before = len(store.find_by_kind(CONSEQ_KIND))

    # the reviewer DECLINES with NO new evidence — this must SUCCEED
    r = _reject(client, target,
                rationale="the actor attribution cannot be verified; declined")
    body = r.json()
    assert body["decisionOutcome"] == "RETAIN_DRAFT"
    review = store.get_record(body["emittedReviewDecisionRefs"][0])["payload"]
    assert review["decisionOutcomeState"] == "REJECTED"
    assert "evidenceRefs" not in review, "no reviewer evidence was required"
    # no NEW acceptance sufficiency case inserted; the queue-time case is untouched
    assert len(store.find_by_kind(CASE_KIND)) == cases_before
    # nothing promoted -> no materialization basis member
    assert len(store.find_by_kind(CONSEQ_KIND)) == conseq_before


def test_present_but_invalid_decision_outcome_never_accepts(store, pipeline):
    # PR #18 re-review: the accept verb with a PRESENT-but-invalid
    # decisionOutcomeState (incl. explicit null) must refuse, never route as a
    # legacy accept — only an ABSENT outcome is the accept default.
    target = _queue_op(pipeline)
    base = {
        "commitClass": "GOVERNANCE_DECISION", "actingPartyRef": demo.ADVISOR,
        "farmRef": demo.FARM, "decisionTime": context.now_iso(),
        "reviewTargetAssertionRef": target, "reviewRationale": "a stated rationale",
        "reviewAction": "REVIEW_ACCEPT",
    }
    for bad in (None, "", False, 0, [], "ACCEPT", "accepted", "REJECTED"):
        sub = dict(base, idempotencyKey=f"badout:{uid()}", decisionOutcomeState=bad)
        r = pipeline.commit(sub)
        assert r["decisionOutcome"] == "RETAIN_DRAFT", \
            f"decisionOutcomeState={bad!r} must not accept"
        assert r["problems"][0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"
    assert store.edges_from(target, "REVIEW") == [], "no invalid outcome decided anything"
    # ABSENT outcome (key omitted) is still the legacy accept default
    ok = pipeline.commit(dict(base, idempotencyKey=f"absout:{uid()}"))
    assert ok["decisionOutcome"] == "PROMOTE_ACCEPTED"


# ---------------------------------------------------------------------------
# M2 G5-4 — the CONTEST verb (dispute against an in-force consequence)
# ---------------------------------------------------------------------------

def _inforce_consequence(pipeline, *, idem=None):
    """A self-accepted routine spray -> an in-force AcceptedEventConsequence."""
    r = pipeline.commit(demo.spray_submission(
        idem or f"contest-base:{uid()}", erp_id=f"erp:contest.{uid()}", confirm=True))
    assert r["decisionOutcome"] == "PROMOTE_ACCEPTED"
    return r["emittedAcceptedConsequenceRefs"][0]


def _contest(client, consequence, *, party=demo.ADVISOR,
             rationale="advisor disputes: the recorded application conflicts with "
             "the field evidence", evidence=None, key=None):
    body = {"farmRef": demo.FARM, "consequenceRef": consequence, "rationale": rationale}
    if evidence is not None:
        body["evidenceRefs"] = evidence
    if key is not None:
        body["idempotencyKey"] = key
    return client.post("/review/contest", json=body, headers=_hdr(party))


WINDOW = ("2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z")


def test_contest_flags_inforce_consequence_no_new_consequence(store, pipeline):
    client = _client(store)
    c1 = _inforce_consequence(pipeline)
    before = len(store.find_by_kind("ofarm.acceptedeventconsequence.v0.1"))
    r = _contest(client, c1)
    assert r.status_code == 200
    body = r.json()
    assert body["decisionOutcome"] == "RETAIN_DRAFT"
    assert "emittedAcceptedConsequenceRefs" not in body, "a contest promotes nothing"
    review = store.get_record(body["emittedReviewDecisionRefs"][0])["payload"]
    assert review["reviewAction"] == "REVIEW_REJECT_OR_CONTEST"
    assert review["decisionOutcomeState"] == "CONTESTED"
    assert review["reviewedArtifactFamily"] == "ACCEPTED_EVENT_CONSEQUENCE"
    assert review["reviewedArtifactRef"] == c1
    assert review["notes"].startswith("dispute:")
    # a DISPUTE edge marks the consequence; it is never edited and STAYS in force
    disputes = [e["dst_record_id"] for e in store.edges_from(c1, "DISPUTE")]
    assert disputes == [review["reviewDecisionId"]]
    assert store.get_record(c1)["payload"]["inForceState"] == "IN_FORCE"
    assert not store.is_superseded(c1)
    assert len(store.find_by_kind("ofarm.acceptedeventconsequence.v0.1")) == before


def test_contest_requires_distinct_reject_authority(store, pipeline):
    client = _client(store)
    c1 = _inforce_consequence(pipeline)
    # the FARMER holds REVIEW_ACCEPT but NOT REVIEW_REJECT_OR_CONTEST
    r = _contest(client, c1, party=demo.FARMER)
    assert r.json()["decisionOutcome"] == "DENY"
    assert r.json()["problems"][0]["reasonCode"] == "AUTHORITY_DENIED"
    assert store.edges_from(c1, "DISPUTE") == []


def test_contest_validity_guards(store, pipeline):
    client = _client(store)
    c1 = _inforce_consequence(pipeline)
    # wrong-kind target: a queued assertion, not a consequence
    queued = _queue_op(pipeline)
    assert _contest(client, queued).json()["problems"][0]["reasonCode"] \
        == "EVIDENCE_REFERENCE_UNAVAILABLE"
    # empty rationale
    assert _contest(client, c1, rationale="   ").json()["problems"][0]["reasonCode"] \
        == "EVIDENCE_INSUFFICIENT"
    # unresolved evidence ref
    assert _contest(client, c1, evidence=["evidence:nope"]).json()["problems"][0]["reasonCode"] \
        == "EVIDENCE_REFERENCE_UNAVAILABLE"
    assert store.edges_from(c1, "DISPUTE") == [], "no refused attempt disputed anything"
    # a successful contest, then a double-contest is refused
    assert _contest(client, c1).json()["decisionOutcome"] == "RETAIN_DRAFT"
    assert _contest(client, c1).json()["problems"][0]["reasonCode"] == "SUPERSEDED_RECORD_USED"


def test_contest_stales_and_qualifies_passport_disputed_basis(fresh_env):
    # fresh DB: a passport's disputeStatus is farm-GLOBAL, so this must not see
    # disputes other tests opened on the shared session farm
    store, pipeline, outputs = fresh_env
    client = _client(store)
    c1 = _inforce_consequence(pipeline)
    # a clean farm reads disputeStatus NONE — computed, not assumed (M4 over-claim closed)
    fresh = outputs.passport_view(demo.FARM, demo.FARMER)
    assert fresh["body"]["freshness"] == "FRESH"
    assert fresh["qualification"]["disputeStatus"] == "NONE"

    assert _contest(client, c1).json()["decisionOutcome"] == "RETAIN_DRAFT"

    # freshness axis: the dependent materialization was staled on contest
    stale = outputs.passport_view(demo.FARM, demo.FARMER, allow_recompute=False)
    assert stale["body"]["freshness"] != "FRESH"
    # dispute axis: after recompute the read is FRESH again yet disputed. The
    # register directly presents the disputed spray consequence as an entry, so
    # it qualifies OPEN_DISPUTE (a basis-only dispute would be DISPUTED_BASIS).
    after = outputs.passport_view(demo.FARM, demo.FARMER)
    assert after["body"]["freshness"] == "FRESH"
    assert after["qualification"]["disputeStatus"] == "OPEN_DISPUTE"
    assert after["qualification"]["stalenessClass"] == "FRESH"


def test_freeze_refuses_on_disputed_basis(fresh_env):
    store, pipeline, outputs = fresh_env
    client = _client(store)
    c1 = _inforce_consequence(pipeline)
    clean = outputs.freeze_inspection_register(demo.FARM, demo.FARMER, *WINDOW)
    assert clean["refused"] is False, "a clean basis freezes"
    assert _contest(client, c1).json()["decisionOutcome"] == "RETAIN_DRAFT"
    # the freeze refuses on the DISPUTE axis even though it recomputes FRESH
    disputed = outputs.freeze_inspection_register(demo.FARM, demo.FARMER, *WINDOW)
    assert disputed["refused"] is True
    assert disputed["problem"]["reasonCode"] == "DISPUTE_OPEN"


def test_contest_resolution_by_correction_derives_corrected(fresh_env):
    store, pipeline, outputs = fresh_env
    client = _client(store)
    c1 = _inforce_consequence(pipeline)
    assert _contest(client, c1).json()["decisionOutcome"] == "RETAIN_DRAFT"
    assert outputs.passport_view(demo.FARM, demo.FARMER)["qualification"]["disputeStatus"] \
        == "OPEN_DISPUTE"
    # a CORRECTION supersedes c1 -> c2 in force, c1 leaves force
    corr = demo.spray_submission(f"contest-corr:{uid()}",
                                 erp_id=f"erp:contest.corr.{uid()}", confirm=True)
    corr["supersedesConsequenceRef"] = c1
    cr = pipeline.commit(corr)
    assert cr["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert store.is_superseded(c1), "the corrected predecessor left force"
    # the current read derives CORRECTED by walking c2 -> c1 lineage + c1's DISPUTE edge
    after = outputs.passport_view(demo.FARM, demo.FARMER)
    assert after["qualification"]["disputeStatus"] == "CORRECTED"
    # and the freeze no longer refuses (the dispute is resolved)
    assert outputs.freeze_inspection_register(demo.FARM, demo.FARMER, *WINDOW)["refused"] is False


def test_contest_decision_is_reachable_as_a_receipt(store, pipeline):
    client = _client(store)
    c1 = _inforce_consequence(pipeline)
    body = _contest(client, c1).json()
    review_id = body["emittedReviewDecisionRefs"][0]
    trace = store.get_record(body["promotionTraceRef"])["payload"]
    assert review_id in trace["emittedReviewDecisionRefs"]
    emits = [e["dst_record_id"]
             for e in store.edges_from(trace["promotionTraceId"], "PROMOTION_EMITS")]
    assert review_id in emits
