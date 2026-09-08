"""Legacy correction authorization (approved RFC v0.2, C01–C07/C09–C10).

The real HTTP/pipeline/store path distinguishes an inert correction request
from authority to retire accepted truth. Every actor and identity is fictional.
Graph corruption is confined to a disposable database; malformed scalar
provenance uses an explicitly identified Store read fault, never a SQL bypass.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import permutations
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from kernel import config, demo
from kernel.authority import AuthorityEvaluator
from kernel.context import now_iso
from kernel.contracts import canonical_json
from kernel.legacy_m1.api import create_test_app


FAMILIES = (
    "STRUCTURE_ASSERTION", "OPERATION_CLAIM",
    "OBSERVATION_ASSERTION", "COMPLIANCE_ASSERTION",
)
ASSERT_ACTIONS = (
    "ASSERT_STRUCTURE", "ASSERT_OPERATION_CLAIM",
    "OBSERVE_CREATE_OBSERVATION", "ASSERT_COMPLIANCE",
)
REVIEW_ACTIONS = ("REVIEW_ACCEPT", "REVIEW_SUPERSEDE", "REVIEW_REJECT_OR_CONTEST")
CONSEQUENCE_KIND = "ofarm.acceptedeventconsequence.v0.1"
REVIEW_KIND = "ofarm.reviewdecision.v0.1"


def _id(prefix):
    return f"{prefix}:correction-test.{uuid4().hex[:12]}"


def _grant(store, actor, actions, **fields):
    grant = _id("grant")
    with store.tx() as cur:
        store.insert_record(cur, {
            "schemaVersion": "ofarm.authoritygrant.v0.1",
            "authorityGrantId": grant, "grantedByPartyRef": demo.FARMER,
            "grantTarget": {"targetKind": "PARTY", "targetRef": actor},
            "targetScope": {"scopeType": "FARM", "scopeRef": demo.FARM},
            "authorityActionClasses": list(actions),
            "validFrom": demo.VALID_FROM, "inheritanceMode": "NO_INHERIT",
            "grantState": "ACTIVE", **fields,
        })
    return grant


def _actor(store, actions, *, party_class="NATURAL_PERSON"):
    actor = _id("party")
    with store.tx() as cur:
        store.insert_record(cur, {
            "schemaVersion": "ofarm.party.v0.1", "partyId": actor,
            "partyClass": party_class, "partyState": "ACTIVE",
            "displayName": "Fictional correction reviewer", "recordedAt": now_iso(),
        })
    _grant(store, actor, actions)
    return actor


@pytest.fixture
def env(fresh_env):
    store, pipeline, outputs = fresh_env
    with TestClient(create_test_app(store, oidc=None)) as client:
        yield SimpleNamespace(
            store=store, pipeline=pipeline, outputs=outputs, client=client,
            author=_actor(store, ASSERT_ACTIONS),
            accept_only=_actor(store, ("REVIEW_ACCEPT",)),
            reviewer=_actor(store, (*ASSERT_ACTIONS, *REVIEW_ACTIONS)),
        )


def _post(env, path, body, actor):
    response = env.client.post(path, json=body, headers={"x-acting-party": actor})
    assert response.status_code == 200, response.text
    return response.json()


def _commit(env, submission):
    return _post(env, "/commit", {"submission": submission}, submission["actingPartyRef"])


def _review(env, assertion, *, actor=None, key=None, **extra):
    return _post(env, "/review/accept", {
        "farmRef": demo.FARM, "assertionRef": assertion,
        "rationale": "Fictional reviewer checked the correction and evidence",
        "idempotencyKey": key or _id("accept"), **extra,
    }, actor or env.reviewer)


def _acceptance_submission(assertion, actor):
    # /review/accept creates a new decisionTime on each request. A replay test
    # uses /commit so that it actually resubmits identical semantic content.
    return {
        "commitClass": "GOVERNANCE_DECISION", "actingPartyRef": actor,
        "farmRef": demo.FARM, "idempotencyKey": _id("accept"),
        "decisionTime": now_iso(), "reviewTargetAssertionRef": assertion,
        "reviewRationale": "Fictional reviewer checked the correction and evidence",
    }


def _submission(family, actor):
    if family == "OPERATION_CLAIM":
        return demo.spray_submission(
            _id("commit"), erp_id=_id("erp"), actor_ref=actor, confirm=False)
    if family == "STRUCTURE_ASSERTION":
        payload = {
            "schemaVersion": "ofarm.fieldidentitypayload.v0.1",
            "fieldidentitypayloadId": _id("fieldpayload"),
            "identityRecordRef": _id("field"), "recordedAt": now_iso(),
            "displayName": "Fictional correction field",
            "parentFarmIdentityRef": demo.FARM,
            "declaredArea": {"value": 1.0, "unitCode": "har"},
        }
        return demo.structure_submission(
            payload, idem_key=_id("commit"), actor_ref=actor, confirm=False)
    sub = {
        "commitClass": family, "actingPartyRef": actor, "farmRef": demo.FARM,
        "subjectType": "FIELD", "subjectRef": demo.FIELD,
        "idempotencyKey": _id("commit"), "eventTime": "2026-06-10T09:00:00Z",
        "evidenceRefs": [demo.PHOTO_EVIDENCE], "confirmAccept": False,
    }
    if family == "COMPLIANCE_ASSERTION":
        sub["payload"] = {"complianceClaim": {
            "statement": "Fictional initial compliance claim",
            "assertedStatus": "CLAIMED_COMPLIANT",
            "governingRuleRefs": [config.EVIDENCE_POLICY_REF],
            "subjectScopeRef": demo.FIELD,
        }}
    return sub


def _correction(original, predecessor, *, actor=None, confirm=False):
    sub = deepcopy(original)
    sub.update(idempotencyKey=_id("correction"),
               supersedesConsequenceRef=predecessor, confirmAccept=confirm)
    if actor:
        sub["actingPartyRef"] = actor
    if sub["commitClass"] == "STRUCTURE_ASSERTION":
        sub["payload"]["fieldidentitypayloadId"] = _id("fieldpayload")
        sub["payload"]["declaredArea"]["value"] += 0.1
    elif sub["commitClass"] == "OPERATION_CLAIM":
        sub["payload"]["executionRecordPayloadId"] = _id("erp")
        sub["payload"]["actor"]["actorPartyRef"] = sub["actingPartyRef"]
    elif sub["commitClass"] == "COMPLIANCE_ASSERTION":
        sub["payload"]["complianceClaim"].update(
            statement="Fictional corrected claim on reviewed evidence",
            assertedStatus="CLAIMED_NON_COMPLIANT")
    return sub


def _queue(env, sub):
    result = _commit(env, sub)
    assert result["decisionOutcome"] in {"RETAIN_DRAFT", "REQUIRE_REVIEW"}, result
    assert not result.get("emittedAcceptedConsequenceRefs")
    assert len(result["emittedAssertionRecordRefs"]) == 1, result
    return result["emittedAssertionRecordRefs"][0]


def _original(env, family, *, direct=False):
    sub = _submission(family, env.reviewer if direct else env.author)
    if direct:
        sub["confirmAccept"] = True
        result = _commit(env, sub)
    else:
        result = _review(env, _queue(env, sub))
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED", result
    assert len(result["emittedAcceptedConsequenceRefs"]) == 1
    return sub, result["emittedAcceptedConsequenceRefs"][0]


def _truth(store):
    return (
        {row["record_id"] for row in store.find_by_kind(CONSEQUENCE_KIND)},
        {row["record_id"] for row in store.find_by_kind(REVIEW_KIND)
         if row["payload"]["decisionOutcomeState"] == "ACCEPTED"},
    )


def _refused(env, result, before, predecessor):
    assert result["decisionOutcome"] != "PROMOTE_ACCEPTED", result
    assert not result.get("emittedAcceptedConsequenceRefs"), result
    assert _truth(env.store) == before
    assert not env.store.is_superseded(predecessor)


def _assert_receipt(store, result):
    trace_ref = result["promotionTraceRef"]
    trace = store.get_payload(trace_ref)
    for key in ("emittedAssertionRecordRefs", "emittedReviewDecisionRefs",
                "emittedAcceptedConsequenceRefs"):
        assert trace.get(key, []) == result.get(key, [])
        for ref in result.get(key, []):
            assert [edge["src_record_id"] for edge in
                    store.edges_to(ref, "PROMOTION_EMITS")] == [trace_ref]
    return trace


def _retirement_receipt(store, result, actor, *, allowed):
    trace = _assert_receipt(store, result)
    refs = {ref for gate in trace["gateSequence"]
            for ref in gate.get("relatedArtifactRefs", [])}
    rows = [store.get_record(ref) for ref in refs]
    requests = [row["payload"] for row in rows if row and
                row["record_kind"] == "ofarm.authorizationdecisionrequest.v0.1"
                and row["payload"]["actionClass"] == "REVIEW_SUPERSEDE"]
    assert len(requests) == 1, trace
    request = requests[0]
    assert request["actingPartyRef"] == actor
    assert request["actionStage"] == "PROMOTION"
    assert request["target"]["scope"] == {"scopeType": "FARM", "scopeRef": demo.FARM}
    assert request["revocationCheckRequired"] is True
    results = [row["payload"] for row in rows if row and
               row["record_kind"] == "ofarm.authorizationdecisionresult.v0.1"
               and row["payload"]["requestId"] == request["requestId"]]
    assert len(results) == 1
    assert (results[0]["decisionOutcome"] == "ALLOW") is allowed
    assert results[0]["finalActionPermitted"] is allowed
    decision_trace = store.get_payload(results[0]["authorizationDecisionTraceRef"])
    assert decision_trace["requestedActionClass"] == "REVIEW_SUPERSEDE"
    assert decision_trace["actingPartyRef"] == actor
    return results[0]


@pytest.mark.parametrize("family", FAMILIES)
def test_each_family_retains_contest_then_authorized_correction(env, family):
    """C03/C05–C07/C10: the dispute consumer works for all four source families."""
    original, old = _original(env, family)
    old_bytes = deepcopy(env.store.get_record(old))
    contest = _post(env, "/review/contest", {
        "farmRef": demo.FARM, "consequenceRef": old,
        "rationale": "Fictional reviewer disputes the predecessor evidence",
        "idempotencyKey": _id("contest"),
    }, env.reviewer)
    assert not contest.get("emittedAcceptedConsequenceRefs")
    dispute = contest["emittedReviewDecisionRefs"][0]
    assert env.store.get_payload(dispute)["decisionOutcomeState"] == "CONTESTED"
    assert not env.store.is_superseded(old)

    correction = _correction(original, old)
    assertion = _queue(env, correction)  # author has no REVIEW_SUPERSEDE
    assert [e["dst_record_id"] for e in env.store.edges_from(
        assertion, "LINEAGE_SUPERSEDES_INTENT")] == [old]
    assert not env.store.is_superseded(old)
    before = _truth(env.store)
    denied = _review(env, assertion, actor=env.accept_only)
    _refused(env, denied, before, old)
    _retirement_receipt(env.store, denied, env.accept_only, allowed=False)
    assert env.store.edges_from(assertion, "REVIEW") == []

    acceptance = _acceptance_submission(assertion, env.reviewer)
    accepted = _commit(env, acceptance)
    assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED", accepted
    assert len(accepted["emittedAcceptedConsequenceRefs"]) == 1
    successor = accepted["emittedAcceptedConsequenceRefs"][0]
    assert [e["dst_record_id"] for e in env.store.edges_from(
        successor, "LINEAGE_SUPERSEDES")] == [old]
    assert env.store.is_superseded(old)
    assert env.store.get_record(old) == old_bytes
    assert env.store.get_payload(assertion)["claimState"] == "PENDING_REVIEW"
    assert env.outputs._lineage_has_dispute(successor)
    _retirement_receipt(env.store, accepted, env.reviewer, allowed=True)
    after = _truth(env.store)
    replay = _commit(env, acceptance)
    assert replay["decisionOutcome"] == "REPLAY_REUSED_RESULT", replay
    assert replay["emittedAcceptedConsequenceRefs"] == [successor]
    assert _truth(env.store) == after
    assert len(env.store.edges_to(successor, "PROMOTION_EMITS")) == 1

    # Accepted queued assertions are valid origins without mutating their claimState.
    third = _review(env, _queue(env, _correction(correction, successor)))
    assert third["decisionOutcome"] == "PROMOTE_ACCEPTED", third
    newest = third["emittedAcceptedConsequenceRefs"][0]
    assert env.outputs._lineage_has_dispute(newest)
    assert [e["dst_record_id"] for e in env.store.edges_from(
        newest, "LINEAGE_SUPERSEDES")] == [successor]
    _retirement_receipt(env.store, third, env.reviewer, allowed=True)


@pytest.mark.parametrize("family", ("STRUCTURE_ASSERTION", "OPERATION_CLAIM"))
def test_direct_correction_requires_both_actions_and_accepts_direct_origin(env, family):
    original, old = _original(env, family, direct=True)
    actor = _actor(env.store, (*ASSERT_ACTIONS, "REVIEW_ACCEPT"))
    before = _truth(env.store)
    denied = _commit(env, _correction(original, old, actor=actor, confirm=True))
    _refused(env, denied, before, old)
    _retirement_receipt(env.store, denied, actor, allowed=False)
    _grant(env.store, actor, ("REVIEW_SUPERSEDE",))
    accepted = _commit(env, _correction(original, old, actor=actor, confirm=True))
    assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED", accepted
    _retirement_receipt(env.store, accepted, actor, allowed=True)
    assert env.store.is_superseded(old)


@pytest.mark.parametrize("schema_version", ([], {}), ids=("list", "object"))
def test_structural_correction_refuses_unhashable_schema_version(env, schema_version):
    original, old = _original(env, "STRUCTURE_ASSERTION")
    old_row = deepcopy(env.store.get_record(old))
    correction = _correction(original, old, actor=env.reviewer)
    correction["payload"]["schemaVersion"] = schema_version
    before = _truth(env.store)
    refused = _commit(env, correction)
    _refused(env, refused, before, old)
    assert not refused.get("emittedAssertionRecordRefs"), refused
    trace = _assert_receipt(env.store, refused)
    assert trace["finalOutcome"] == refused["decisionOutcome"]
    assert any(gate["gate"] == "VALIDATION" and gate["outcome"].startswith("FAIL_")
               for gate in trace["gateSequence"])
    assert env.store.edges_to(old, "LINEAGE_SUPERSEDES_INTENT") == []
    assert env.store.edges_to(old, "LINEAGE_SUPERSEDES") == []
    assert env.store.get_record(old) == old_row


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("correct", (False, True), ids=("ordinary-acceptance", "correction-chain"))
def test_field_only_event_scopes_preserve_acceptance_and_correction(env, family, correct):
    """Contained field anchors remain immutable through both lawful queue paths."""
    original = _submission(family, env.author)
    original["targetScopes"] = [{"scopeType": "FIELD", "scopeRef": demo.FIELD}]
    assertion = _queue(env, original)
    event = env.store.edges_from(assertion, "EVENT_SOURCE")[0]["dst_record_id"]
    event_payload = env.store.get_payload(event)
    assert event_payload["anchorScopes"] == original["targetScopes"]
    event_bytes = canonical_json(event_payload).encode()
    accepted = _review(env, assertion)
    assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED", accepted
    old = accepted["emittedAcceptedConsequenceRefs"][0]
    assert env.store.get_payload(old)["sourceEventRef"] == event
    assert canonical_json(env.store.get_payload(event)).encode() == event_bytes
    _assert_receipt(env.store, accepted)
    if not correct:
        return

    old_row = deepcopy(env.store.get_record(old))
    contest = _post(env, "/review/contest", {
        "farmRef": demo.FARM, "consequenceRef": old,
        "rationale": "Fictional reviewer disputes this field-scoped source",
        "idempotencyKey": _id("contest"),
    }, env.reviewer)
    dispute = contest["emittedReviewDecisionRefs"][0]
    assert env.store.get_payload(dispute)["decisionOutcomeState"] == "CONTESTED"
    queued = _queue(env, _correction(original, old))
    queued_event = env.store.edges_from(queued, "EVENT_SOURCE")[0]["dst_record_id"]
    queued_bytes = canonical_json(env.store.get_payload(queued_event)).encode()
    assert env.store.get_payload(queued_event)["anchorScopes"] == original["targetScopes"]
    assert not env.store.is_superseded(old)
    corrected = _review(env, queued)
    assert corrected["decisionOutcome"] == "PROMOTE_ACCEPTED", corrected
    successor = corrected["emittedAcceptedConsequenceRefs"][0]
    assert env.store.get_payload(successor)["sourceEventRef"] == queued_event
    assert [edge["dst_record_id"] for edge in env.store.edges_from(
        successor, "LINEAGE_SUPERSEDES")] == [old]
    assert env.store.is_superseded(old)
    assert env.outputs._lineage_has_dispute(successor)
    assert env.store.get_record(old) == old_row
    assert canonical_json(env.store.get_payload(event)).encode() == event_bytes
    assert canonical_json(env.store.get_payload(queued_event)).encode() == queued_bytes
    _retirement_receipt(env.store, corrected, env.reviewer, allowed=True)


@pytest.mark.parametrize("target", [None, "", " ", False, 17, [], {}, "conseq:missing",
                                    demo.PHOTO_EVIDENCE])
def test_supplied_target_must_be_a_nonempty_visible_consequence(env, target):
    original, old = _original(env, "OPERATION_CLAIM")
    before = _truth(env.store)
    result = _commit(env, _correction(original, target, actor=env.reviewer))
    _refused(env, result, before, old)
    assert not result.get("emittedAssertionRecordRefs"), result


def test_another_tenants_consequence_is_unavailable_as_a_correction_target(env):
    """Reuse the existing isolated tenant-row fixture; do not change Store policy."""
    from kernel.tests.test_runtime_bundle_receipts import (
        _foreign_tenant_store, _seed_foreign_review_target,
    )

    original, old = _original(env, "OPERATION_CLAIM")
    foreign = _id("consequence")
    with _foreign_tenant_store(env.store, "correction") as (_, other):
        _seed_foreign_review_target(
            env.store, other, source_target=old, foreign_target=foreign,
            identity_field="acceptedEventConsequenceId",
            emitted_refs_field="emittedAcceptedConsequenceRefs")
        assert other.get_record(foreign) is not None
        assert env.store.get_record(foreign) is None
        before = _truth(env.store)
        refused = _commit(env, _correction(original, foreign, actor=env.reviewer))
        _refused(env, refused, before, old)
        assert not refused.get("emittedAssertionRecordRefs"), refused
        assert not other.is_superseded(foreign)


@pytest.mark.parametrize("old_family,new_family", list(permutations(FAMILIES, 2)))
def test_full_authority_does_not_allow_cross_family_intent(env, old_family, new_family):
    _, old = _original(env, old_family)
    correction = _submission(new_family, env.reviewer)
    correction["supersedesConsequenceRef"] = old
    if new_family in {"OBSERVATION_ASSERTION", "COMPLIANCE_ASSERTION"}:
        # In particular, structure and observation share STATE_CHANGE_ACCEPTED:
        # matching their outer subject still does not make the families compatible.
        subject = env.store.get_payload(old)["subject"]
        correction.update(subject)
        if new_family == "COMPLIANCE_ASSERTION":
            correction["payload"]["complianceClaim"]["subjectScopeRef"] = subject["subjectRef"]
    before = _truth(env.store)
    result = _commit(env, correction)
    _refused(env, result, before, old)
    assert not result.get("emittedAssertionRecordRefs"), result


@pytest.mark.parametrize("family", FAMILIES)
def test_full_authority_does_not_allow_different_subject_or_identity(env, family):
    original, old = _original(env, family)
    correction = _correction(original, old, actor=env.reviewer)
    if family == "STRUCTURE_ASSERTION":
        correction["payload"]["identityRecordRef"] = _id("field")
    else:
        correction.update(subjectType="FARM", subjectRef=demo.FARM)
        if family == "OPERATION_CLAIM":
            correction["payload"]["subject"] = {"subjectType": "FARM", "subjectRef": demo.FARM}
        elif family == "COMPLIANCE_ASSERTION":
            correction["payload"]["complianceClaim"]["subjectScopeRef"] = demo.FARM
    before = _truth(env.store)
    refused = _commit(env, correction)
    _refused(env, refused, before, old)
    assert not refused.get("emittedAssertionRecordRefs"), refused


@pytest.mark.parametrize("family", FAMILIES)
def test_queued_correction_rechecks_target_after_another_correction(env, family):
    original, old = _original(env, family)
    first = _queue(env, _correction(original, old))
    second = _queue(env, _correction(original, old))
    accepted = _review(env, first)
    assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED", accepted
    before = _truth(env.store)
    stale = _review(env, second)
    assert stale["decisionOutcome"] != "PROMOTE_ACCEPTED", stale
    assert _truth(env.store) == before
    assert env.store.edges_from(second, "REVIEW") == []
    assert len(env.store.edges_to(old, "LINEAGE_SUPERSEDES")) == 1


@pytest.mark.parametrize("location", ("origin-source", "queued-source", "queued-intent",
                                     "structure-payload", "compliance-claim",
                                     "queued-structure-payload", "queued-compliance-claim"))
def test_ambiguous_durable_relationships_refuse_without_first_edge_fallback(env, location):
    family = ("STRUCTURE_ASSERTION" if location.endswith("structure-payload") else
              "COMPLIANCE_ASSERTION" if location.endswith("compliance-claim") else "OPERATION_CLAIM")
    original, old = _original(env, family)
    assertion = _queue(env, _correction(original, old))
    old_payload = env.store.get_payload(old)
    old_review = env.store.get_payload(old_payload["acceptedByReviewDecisionRef"])
    if location == "origin-source":
        source, edge_type = old_review["reviewedArtifactRef"], "EVENT_SOURCE"
    elif location == "queued-source":
        source, edge_type = assertion, "EVENT_SOURCE"
    elif location == "queued-intent":
        source, edge_type = assertion, "LINEAGE_SUPERSEDES_INTENT"
    else:
        source = (env.store.edges_from(assertion, "EVENT_SOURCE")[0]["dst_record_id"]
                  if location.startswith("queued-") else old_payload["sourceEventRef"])
        edge_type = "STRUCTURE_PAYLOAD" if family == "STRUCTURE_ASSERTION" else "COMPLIANCE_CLAIM"
    destination = env.store.edges_from(source, edge_type)[0]["dst_record_id"]
    with env.store.tx() as cur:
        # Two copies are still ambiguous proof: deduplicating silently is forbidden.
        env.store.add_edge(cur, edge_type, source, destination)
    before = _truth(env.store)
    refused = _review(env, assertion)
    _refused(env, refused, before, old)
    assert env.store.edges_from(assertion, "REVIEW") == []


@pytest.mark.parametrize("fault", (
    "missing-review", "wrong-review-kind", "wrong-review-outcome", "wrong-review-target",
    "wrong-review-action", "wrong-assertion-subject",
    "wrong-assertion-kind", "wrong-assertion-family", "wrong-consequence-type",
    "event-reference-disagreement", "wrong-event-kind", "cross-farm", "not-in-force",
))
def test_malformed_origin_reads_fail_closed(env, monkeypatch, fault):
    """C04: inject one malformed Store read while exercising the HTTP acceptance path."""
    original, old = _original(env, "OPERATION_CLAIM")
    assertion = _queue(env, _correction(original, old))
    old_row = env.store.get_record(old)
    review_ref = old_row["payload"]["acceptedByReviewDecisionRef"]
    review_row = env.store.get_record(review_ref)
    assertion_ref = review_row["payload"]["reviewedArtifactRef"]
    event_ref = old_row["payload"]["sourceEventRef"]
    target = old if fault in {"wrong-consequence-type", "event-reference-disagreement",
                             "cross-farm", "not-in-force"} else (
        assertion_ref if fault.startswith("wrong-assertion") else
        event_ref if fault == "wrong-event-kind" else review_ref)
    poisoned = deepcopy(env.store.get_record(target))
    if fault == "missing-review":
        poisoned = None
    elif fault in {"wrong-review-kind", "wrong-assertion-kind", "wrong-event-kind"}:
        poisoned["record_kind"] = "ofarm.party.v0.1"
    elif fault == "wrong-review-outcome":
        poisoned["payload"]["decisionOutcomeState"] = "REJECTED"
    elif fault == "wrong-review-target":
        poisoned["payload"]["reviewedArtifactFamily"] = "ACCEPTED_EVENT_CONSEQUENCE"
    elif fault == "wrong-review-action":
        poisoned["payload"]["reviewAction"] = "REVIEW_REJECT_OR_CONTEST"
    elif fault == "wrong-assertion-subject":
        poisoned["payload"]["subject"] = {"subjectType": "FARM", "subjectRef": demo.FARM}
    elif fault == "wrong-assertion-family":
        poisoned["payload"]["assertionType"] = "COMPLIANCE_ASSERTION"
    elif fault == "wrong-consequence-type":
        poisoned["payload"]["consequenceType"] = "COMPLIANCE_STATUS_ACCEPTED"
    elif fault == "event-reference-disagreement":
        poisoned["payload"]["sourceEventRef"] = env.store.edges_from(
            assertion, "EVENT_SOURCE")[0]["dst_record_id"]
    elif fault == "cross-farm":
        poisoned["payload"]["anchorScopes"] = [{"scopeType": "FARM", "scopeRef": _id("farm")}]
    elif fault == "not-in-force":
        poisoned["payload"]["inForceState"] = "SUPERSEDED"
    read = env.store.get_record
    monkeypatch.setattr(env.store, "get_record", lambda ref: poisoned if ref == target else read(ref))
    before = _truth(env.store)
    result = _review(env, assertion)
    _refused(env, result, before, old)
    assert env.store.edges_from(assertion, "REVIEW") == []


@pytest.mark.parametrize("phase", ("accepted-origin", "queued-correction"))
@pytest.mark.parametrize("anchor_fault", (
    "foreign-farm", "foreign-field", "missing-type", "missing-ref",
    "non-object-scope", "empty-anchors", "mixed-farms", "mixed-fields",
))
def test_correction_source_event_refuses_cross_farm_anchors(
        env, monkeypatch, phase, anchor_fault):
    """Synthetic event-read fault; each anchor must prove its farm containment."""
    original, old = _original(env, "OPERATION_CLAIM")
    assertion = _queue(env, _correction(original, old))
    event = (env.store.get_payload(old)["sourceEventRef"] if phase == "accepted-origin"
             else env.store.edges_from(assertion, "EVENT_SOURCE")[0]["dst_record_id"])
    event_row = deepcopy(env.store.get_record(event))
    old_row = deepcopy(env.store.get_record(old))
    poisoned = deepcopy(event_row)
    foreign_farm, foreign_field = _id("farm"), _id("field")
    if anchor_fault in {"foreign-field", "mixed-fields"}:
        with env.store.tx() as cur:
            env.store.insert_record(cur, {
                "schemaVersion": "ofarm.identityrecord.v0.1",
                "identityRecordId": foreign_farm, "identityType": "FARM",
                "lifecycleState": "ACTIVE", "createdAt": now_iso(), "recordedAt": now_iso(),
            })
            env.store.insert_record(cur, {
                "schemaVersion": "ofarm.identityrecord.v0.1",
                "identityRecordId": foreign_field, "identityType": "FIELD",
                "lifecycleState": "ACTIVE", "createdAt": now_iso(), "recordedAt": now_iso(),
                "anchorScopes": [{"scopeType": "FARM", "scopeRef": foreign_farm}],
            })
    bad_scope = ({"scopeType": "FIELD", "scopeRef": foreign_field}
                 if anchor_fault in {"foreign-field", "mixed-fields"}
                 else {"scopeType": "FARM", "scopeRef": foreign_farm})
    if anchor_fault == "missing-type":
        bad_scope = {"scopeRef": demo.FIELD}
    elif anchor_fault == "missing-ref":
        bad_scope = {"scopeType": "FIELD"}
    elif anchor_fault == "non-object-scope":
        bad_scope = []
    scopes = [] if anchor_fault == "empty-anchors" else [bad_scope]
    if anchor_fault.startswith("mixed-"):
        scopes.insert(0, {"scopeType": "FARM", "scopeRef": demo.FARM})
    poisoned["payload"]["anchorScopes"] = scopes
    read = env.store.get_record
    before = _truth(env.store)
    with monkeypatch.context() as fault:
        fault.setattr(env.store, "get_record", lambda ref: poisoned if ref == event else read(ref))
        refused = _review(env, assertion)
    _refused(env, refused, before, old)
    if anchor_fault.startswith(("foreign-", "mixed-")):
        assert any(problem["reasonCode"] == "SCOPE_NOT_AUTHORIZED" for problem in refused["problems"])
    trace = _assert_receipt(env.store, refused)
    assert len([gate for gate in trace["gateSequence"]
                if gate["gate"] == "VALIDATION" and gate["outcome"].startswith("FAIL_")]) == 1
    assert env.store.edges_from(assertion, "REVIEW") == []
    assert env.store.get_record(event) == event_row
    assert env.store.get_record(old) == old_row


@pytest.mark.parametrize("family", ("STRUCTURE_ASSERTION", "COMPLIANCE_ASSERTION"))
@pytest.mark.parametrize("phase", ("accepted-origin", "queued-correction"))
@pytest.mark.parametrize("fault", ("missing", "wrong-kind", "wrong-subject"))
def test_required_correction_carrier_reads_must_prove_the_relationship(
        env, monkeypatch, family, phase, fault):
    """C04: explicit Store-read faults, not reachable arbitrary database writes."""
    original, old = _original(env, family)
    assertion = _queue(env, _correction(original, old))
    event = (env.store.get_payload(old)["sourceEventRef"] if phase == "accepted-origin"
             else env.store.edges_from(assertion, "EVENT_SOURCE")[0]["dst_record_id"])
    edge_type = "STRUCTURE_PAYLOAD" if family == "STRUCTURE_ASSERTION" else "COMPLIANCE_CLAIM"
    carrier = env.store.edges_from(event, edge_type)[0]["dst_record_id"]
    poisoned = deepcopy(env.store.get_record(carrier))
    if fault == "missing":
        poisoned = None
    elif fault == "wrong-kind":
        poisoned["record_kind"] = "ofarm.party.v0.1"
    elif family == "STRUCTURE_ASSERTION":
        poisoned["payload"]["identityRecordRef"] = demo.FARM
    else:
        poisoned["payload"]["subjectScopeRef"] = demo.FARM
    read = env.store.get_record
    monkeypatch.setattr(env.store, "get_record", lambda ref: poisoned if ref == carrier else read(ref))
    before = _truth(env.store)
    refused = _review(env, assertion)
    _refused(env, refused, before, old)
    assert env.store.edges_from(assertion, "REVIEW") == []


@pytest.mark.parametrize("phase", ("accepted-origin", "queued-correction"))
@pytest.mark.parametrize("fault", ("source-event", "farm-anchor"))
def test_compliance_carrier_provenance_must_agree(env, monkeypatch, phase, fault):
    original, old = _original(env, "COMPLIANCE_ASSERTION")
    assertion = _queue(env, _correction(original, old))
    event = (env.store.get_payload(old)["sourceEventRef"] if phase == "accepted-origin"
             else env.store.edges_from(assertion, "EVENT_SOURCE")[0]["dst_record_id"])
    carrier = env.store.edges_from(event, "COMPLIANCE_CLAIM")[0]["dst_record_id"]
    poisoned = deepcopy(env.store.get_record(carrier))
    if fault == "source-event":
        poisoned["payload"]["sourceEventRef"] = _id("event")
    else:
        poisoned["payload"]["anchorScopes"] = [{"scopeType": "FARM", "scopeRef": _id("farm")}]
    read = env.store.get_record
    monkeypatch.setattr(env.store, "get_record", lambda ref: poisoned if ref == carrier else read(ref))
    before = _truth(env.store)
    _refused(env, _review(env, assertion), before, old)
    assert env.store.edges_from(assertion, "REVIEW") == []


def test_queued_intent_cannot_retire_an_incompatible_target(env, monkeypatch):
    original, old = _original(env, "OPERATION_CLAIM")
    _, incompatible = _original(env, "STRUCTURE_ASSERTION")
    assertion = _queue(env, _correction(original, old))
    read_edges = env.store.edges_from
    poisoned = deepcopy(read_edges(assertion, "LINEAGE_SUPERSEDES_INTENT"))
    poisoned[0]["dst_record_id"] = incompatible
    monkeypatch.setattr(env.store, "edges_from", lambda ref, edge_type=None:
                        poisoned if (ref, edge_type) == (assertion, "LINEAGE_SUPERSEDES_INTENT")
                        else read_edges(ref, edge_type))
    before = _truth(env.store)
    _refused(env, _review(env, assertion), before, old)
    assert not env.store.is_superseded(incompatible)
    assert env.store.edges_from(assertion, "REVIEW") == []


def test_structure_requires_one_current_consequence_for_its_identity(env):
    """An explicit corrupt-graph fixture creates ambiguous current structure."""
    original, old = _original(env, "STRUCTURE_ASSERTION")
    assertion = _queue(env, _correction(original, old))
    duplicate = deepcopy(env.store.get_payload(old))
    other = duplicate["acceptedEventConsequenceId"] = _id("consequence")
    with env.store.tx() as cur:
        env.store.insert_record(cur, duplicate)
        trace = _id("trace")
        env.store.insert_record(cur, {
            "schemaVersion": "ofarm.promotiontrace.v0.1", "promotionTraceId": trace,
            "requestId": _id("request"), "evaluatedAt": now_iso(),
            "semanticEventRef": duplicate["sourceEventRef"],
            "commitClass": "STRUCTURE_ASSERTION", "primaryEventFamily": "StructureEvent",
            "idempotencyKey": _id("fixture"), "idempotencyDisposition": "NEW_REQUEST",
            "gateSequence": [{"gate": "REVIEW_PROMOTION", "outcome": "PROMOTE_ACCEPTED"}],
            "finalOutcome": "PROMOTE_ACCEPTED",
            "traceSummary": "Synthetic ambiguous-current-state fixture in a disposable database",
            "emittedAcceptedConsequenceRefs": [other],
        })
        env.store.add_edge(cur, "PROMOTION_EMITS", trace, other)
        for edge_type in ("EVENT_SOURCE", "REVIEW"):
            for edge in env.store.edges_from(old, edge_type):
                env.store.add_edge(cur, edge_type, other, edge["dst_record_id"])
    before = _truth(env.store)
    result = _review(env, assertion)
    _refused(env, result, before, old)
    assert result["problems"][0]["reasonCode"] == "CORRECTION_REQUIRED"
    assert not env.store.is_superseded(other)
    assert env.store.edges_from(assertion, "REVIEW") == []


@pytest.mark.parametrize("phase", ("incoming", "accepted-origin"))
def test_compliance_correction_requires_outer_and_claim_subject_agreement(env, phase):
    if phase == "accepted-origin":
        # Existing ordinary admission validates both scopes independently. Such
        # older accepted history cannot serve as ambiguous correction authority.
        original = _submission("COMPLIANCE_ASSERTION", env.author)
        original["payload"]["complianceClaim"]["subjectScopeRef"] = demo.FARM
        accepted = _review(env, _queue(env, original))
        assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED", accepted
        old = accepted["emittedAcceptedConsequenceRefs"][0]
    else:
        original, old = _original(env, "COMPLIANCE_ASSERTION")
    correction = _correction(original, old, actor=env.reviewer)
    correction["payload"]["complianceClaim"]["subjectScopeRef"] = (
        demo.FARM if phase == "incoming" else demo.FIELD)
    before = _truth(env.store)
    refused = _commit(env, correction)
    _refused(env, refused, before, old)
    assert not refused.get("emittedAssertionRecordRefs"), refused


def test_queued_compliance_uses_original_carrier_and_ignores_review_body_target(env):
    original, old = _original(env, "COMPLIANCE_ASSERTION")
    assertion = _queue(env, _correction(original, old))
    event = env.store.edges_from(assertion, "EVENT_SOURCE")[0]["dst_record_id"]
    carriers = env.store.edges_from(event, "COMPLIANCE_CLAIM")
    assert len(carriers) == 1
    stored_claim = deepcopy(env.store.get_payload(carriers[0]["dst_record_id"]))
    result = _review(env, assertion, supersedesConsequenceRef=demo.PHOTO_EVIDENCE,
                     payload={"complianceClaim": {"subjectScopeRef": demo.FARM}})
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED", result
    assert env.store.get_payload(carriers[0]["dst_record_id"]) == stored_claim
    successor = result["emittedAcceptedConsequenceRefs"][0]
    assert env.store.get_payload(successor)["subject"] == {
        "subjectType": "FIELD", "subjectRef": demo.FIELD}
    assert [e["dst_record_id"] for e in env.store.edges_from(
        successor, "LINEAGE_SUPERSEDES")] == [old]


@pytest.mark.parametrize("grant_state", ("missing", "expired", "revoked"))
def test_current_reviewer_retirement_grant_is_required(env, grant_state):
    original, old = _original(env, "OPERATION_CLAIM")
    # The author of this queued correction has retirement rights; the transport
    # reviewer must still prove their own current authority at admission.
    assertion = _queue(env, _correction(original, old, actor=env.reviewer))
    if grant_state == "expired":
        _grant(env.store, env.accept_only, ("REVIEW_SUPERSEDE",),
               validFrom="2020-01-01T00:00:00Z", validUntil="2020-02-01T00:00:00Z")
    elif grant_state == "revoked":
        grant = _grant(env.store, env.accept_only, ("REVIEW_SUPERSEDE",))
        with env.store.tx() as cur:
            env.store.insert_record(cur, {
                "schemaVersion": "ofarm.revocationdecision.v0.1",
                "revocationDecisionId": _id("revoke"),
                "revokesArtifactFamily": "AUTHORITY_GRANT", "revokesArtifactRef": grant,
                "decidedByPartyRef": demo.FARMER, "decidedAt": now_iso(),
                "effectiveFrom": demo.VALID_FROM, "revocationMode": "TERMINATE",
                "targetScope": {"scopeType": "FARM", "scopeRef": demo.FARM},
            })
    before = _truth(env.store)
    refused = _review(env, assertion, actor=env.accept_only, actingPartyRef=env.reviewer)
    _refused(env, refused, before, old)
    decision = _retirement_receipt(env.store, refused, env.accept_only, allowed=False)
    if grant_state == "revoked":
        assert decision["revocationResult"] == "ACTIVE_REVOCATION_FOUND"


def test_retirement_permission_does_not_substitute_for_acceptance_permission(env):
    original, old = _original(env, "OPERATION_CLAIM")
    assertion = _queue(env, _correction(original, old))
    actor = _actor(env.store, ("REVIEW_SUPERSEDE",))
    before = _truth(env.store)
    _refused(env, _review(env, assertion, actor=actor), before, old)
    assert env.store.edges_from(assertion, "REVIEW") == []


@pytest.mark.parametrize("queued", (False, True), ids=("direct", "queued"))
@pytest.mark.parametrize("actor_kind", ("software-party", "declared-agent", "assistance-only"))
def test_correction_preserves_existing_human_and_assistance_semantics(env, queued, actor_kind):
    original, old = _original(env, "OPERATION_CLAIM")
    actor = _actor(env.store, (*ASSERT_ACTIONS, *REVIEW_ACTIONS),
                   party_class="SOFTWARE_AGENT" if actor_kind == "software-party" else "NATURAL_PERSON")
    if queued:
        assertion = _queue(env, _correction(original, old))
        submission = _acceptance_submission(assertion, actor)
    else:
        submission = _correction(original, old, actor=actor, confirm=True)
    if actor_kind == "declared-agent":
        submission["actingAgentRef"] = _id("agent")
    if actor_kind == "assistance-only":
        submission["aiAssistance"] = {"assisted": True}
    before = _truth(env.store)
    result = _commit(env, submission)
    if actor_kind != "assistance-only":
        # The ordinary admission gate already owns this refusal. Do not weaken
        # it merely to force a nonhuman actor as far as the retirement gate.
        _refused(env, result, before, old)
        assert any(p["reasonCode"] == "HUMAN_APPROVAL_REQUIRED" for p in result["problems"])
        return
    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED", result
    _retirement_receipt(env.store, result, actor, allowed=True)
    trace = env.store.get_payload(result["promotionTraceRef"])
    refs = {ref for gate in trace["gateSequence"] for ref in gate.get("relatedArtifactRefs", [])}
    requests = [env.store.get_payload(ref) for ref in refs]
    retirement = [record for record in requests if record and
                  record.get("schemaVersion") == "ofarm.authorizationdecisionrequest.v0.1"
                  and record.get("actionClass") == "REVIEW_SUPERSEDE"]
    assert len(retirement) == 1
    assert retirement[0]["aiAssistance"] == submission["aiAssistance"]
    assert retirement[0]["nonHumanActor"] is False
    assert "actingAgentRef" not in retirement[0]


@pytest.mark.parametrize("queued", (False, True), ids=("direct", "queued"))
@pytest.mark.parametrize("outcome", ("DENY", "REQUIRE_REVIEW", "REQUIRE_HUMAN_APPROVAL"))
def test_every_non_allow_retirement_decision_refuses_emission(env, monkeypatch, queued, outcome):
    """C06 boundary probe: substitute only the retirement evaluator's output."""
    original, old = _original(env, "OPERATION_CLAIM")
    if queued:
        assertion = _queue(env, _correction(original, old))
        submission = _acceptance_submission(assertion, env.reviewer)
    else:
        submission = _correction(original, old, actor=env.reviewer, confirm=True)
    evaluate = AuthorityEvaluator.evaluate

    def retirement_outcome(evaluator, **kwargs):
        decision = evaluate(evaluator, **kwargs)
        if kwargs["action_class"] == "REVIEW_SUPERSEDE":
            assert decision.allowed, "the compatible control must have sufficient real authority"
            decision.outcome = outcome
            decision.result_payload.update(decisionOutcome=outcome, finalActionPermitted=False,
                                           humanApprovalRequired=outcome == "REQUIRE_HUMAN_APPROVAL")
            decision.trace_payload["decisionOutcome"] = outcome
        return decision

    monkeypatch.setattr(AuthorityEvaluator, "evaluate", retirement_outcome)
    before = _truth(env.store)
    refused = _commit(env, submission)
    _refused(env, refused, before, old)
    receipt = _retirement_receipt(env.store, refused, env.reviewer, allowed=False)
    assert receipt["decisionOutcome"] == outcome


def test_failed_successor_write_rolls_back_retirement_and_acceptance(env, monkeypatch):
    original, old = _original(env, "OPERATION_CLAIM")
    assertion = _queue(env, _correction(original, old))
    before = _truth(env.store)
    write = env.store.insert_record

    def fail_successor(cur, payload):
        if payload.get("schemaVersion") == CONSEQUENCE_KIND:
            raise RuntimeError("injected successor storage failure")
        return write(cur, payload)

    with monkeypatch.context() as fault:
        fault.setattr(env.store, "insert_record", fail_successor)
        with pytest.raises(RuntimeError, match="injected successor storage failure"):
            _review(env, assertion)
    assert _truth(env.store) == before
    assert not env.store.is_superseded(old)
    assert env.store.edges_from(assertion, "REVIEW") == []
    recovered = _review(env, assertion)
    assert recovered["decisionOutcome"] == "PROMOTE_ACCEPTED", recovered
    _retirement_receipt(env.store, recovered, env.reviewer, allowed=True)


@pytest.mark.parametrize("family", FAMILIES)
def test_rejection_still_closes_a_correction_without_retiring_truth(env, family):
    original, old = _original(env, family)
    assertion = _queue(env, _correction(original, old))
    actor = _actor(env.store, ("REVIEW_REJECT_OR_CONTEST",))
    before = _truth(env.store)
    result = _post(env, "/review/reject", {
        "farmRef": demo.FARM, "assertionRef": assertion,
        "rationale": "Fictional correction evidence does not support acceptance",
        "idempotencyKey": _id("reject"),
    }, actor)
    _refused(env, result, before, old)
    assert env.store.get_payload(result["emittedReviewDecisionRefs"][0])[
        "decisionOutcomeState"] == "REJECTED"
    assert env.store.get_payload(assertion)["claimState"] == "PENDING_REVIEW"
    assert [edge["dst_record_id"] for edge in env.store.edges_from(
        assertion, "LINEAGE_SUPERSEDES_INTENT")] == [old]


@pytest.mark.parametrize("commit_class", ("NOTE", "HYPOTHESIS_ASSERTION", "ADVISORY_OUTPUT"))
def test_nonpromoting_classes_cannot_record_supersession_intent(env, commit_class):
    _, old = _original(env, "OPERATION_CLAIM")
    sub = _submission(commit_class, env.reviewer)
    sub["supersedesConsequenceRef"] = old
    before = _truth(env.store)
    result = _commit(env, sub)
    _refused(env, result, before, old)
    assert not result.get("emittedAssertionRecordRefs"), result


@pytest.mark.parametrize("surface", ("standalone-review-verb", "correction-carrier"))
def test_authorized_corrections_do_not_enable_deferred_surfaces(env, surface):
    original, old = _original(env, "OPERATION_CLAIM")
    if surface == "standalone-review-verb":
        assertion = _queue(env, _correction(original, old))
        sub = _acceptance_submission(assertion, env.reviewer)
        sub["reviewAction"] = "REVIEW_SUPERSEDE"
    else:
        sub = _correction(original, old, actor=env.reviewer, confirm=True)
        sub["payload"]["recordClass"] = "CORRECTION"
    before = _truth(env.store)
    _refused(env, _commit(env, sub), before, old)


def test_new_current_bundle_correction_can_replace_older_accepted_history(env):
    # Reuse the established accepted-baseline bundle variant fixture, not a
    # handcrafted runtime that skips bundle selection or startup verification.
    from kernel.tests.test_runtime_bundle_receipts import _second_store

    original, old = _original(env, "OPERATION_CLAIM")
    pending = _queue(env, _correction(original, old))
    store_b = _second_store(env.store)
    try:
        with TestClient(create_test_app(store_b, oidc=None)) as client:
            current = SimpleNamespace(**(vars(env) | {"store": store_b, "client": client}))
            before = _truth(store_b)
            refused = _review(current, pending)
            _refused(current, refused, before, old)
            assert any(p["reasonCode"] == "PACK_CONFLICT" for p in refused["problems"])
            new_assertion = _queue(current, _correction(original, old))
            accepted = _review(current, new_assertion)
            assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED", accepted
            successor = accepted["emittedAcceptedConsequenceRefs"][0]
            assert store_b.get_record(old)["runtime_bundle_digest"] != store_b.runtime_bundle_digest
            assert store_b.get_record(successor)["runtime_bundle_digest"] == store_b.runtime_bundle_digest
            _retirement_receipt(store_b, accepted, env.reviewer, allowed=True)
    finally:
        store_b.close()
