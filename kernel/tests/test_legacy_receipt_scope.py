"""R01–R05: real legacy HTTP receipts, fictional data and disposable databases.

No stored-link substitutions are used here. Defensive graph fixtures and
cross-bundle/base-history coverage live in their separately named tests.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from kernel import demo
from kernel.context import now_iso
from kernel.legacy_m1.api import create_test_app
from kernel.tests.test_correction_authorization import _grant, _post
from kernel.tests.test_observation_eligibility import _observation
from kernel.tests.test_review_confirmation import _commit
from kernel.tests.test_self_review_eligibility import _compliance


FARM = {"scopeType": "FARM", "scopeRef": demo.FARM}
FIELD = {"scopeType": "FIELD", "scopeRef": demo.FIELD}
CLASSES = ("OPERATION_CLAIM", "OBSERVATION_ASSERTION")


def _id(prefix):
    return f"{prefix}:receipt-scope.{uuid4().hex[:12]}"


@pytest.fixture
def env(fresh_env):
    store, pipeline, outputs = fresh_env
    with TestClient(create_test_app(store, oidc=None)) as client:
        yield SimpleNamespace(store=store, pipeline=pipeline,
                              outputs=outputs, client=client)


def _submission(commit_class, scopes=None):
    submission = (demo.spray_submission(_id("commit"), erp_id=_id("erp"))
                  if commit_class == "OPERATION_CLAIM" else _observation())
    submission["targetScopes"] = deepcopy([FIELD] if scopes is None else scopes)
    return submission


def _roots(result):
    return result["resultId"], result["promotionTraceRef"]


def _read(env, result, status=200, actor=demo.FARMER):
    for record_id in _roots(result):
        before = env.store.get_record(record_id)
        response = env.client.get(f"/records/{record_id}",
                                  headers={"x-acting-party": actor})
        assert response.status_code == status, response.text
        if status == 200:
            body = response.json()
            assert body["recordId"] == record_id
            assert body["payload"] == before["payload"]
            assert body["payloadSha256"] == before["payload_sha256"]
            assert body["runtimeBundleDigest"] == before["runtime_bundle_digest"]
        else:
            assert response.json()["detail"]["reasonCode"] == "PERMISSION_REDACTED"
            assert "payload" not in response.json()
        assert env.store.get_record(record_id) == before


def _gates(env, result):
    return [(entry["gate"], entry["outcome"]) for entry in
            env.store.get_payload(result["promotionTraceRef"])["gateSequence"]]


def _party(store):
    actor = _id("party")
    with store.tx() as cursor:
        store.insert_record(cursor, {
            "schemaVersion": "ofarm.party.v0.1", "partyId": actor,
            "partyClass": "NATURAL_PERSON", "partyState": "ACTIVE",
            "displayName": "Fictional receipt reader", "recordedAt": now_iso(),
        })
    return actor


@pytest.mark.parametrize("commit_class", CLASSES)
def test_field_receipts_and_matching_retries_require_current_farm_permission(
        env, commit_class):
    submission = _submission(commit_class)
    original = _commit(env, submission)
    expected = "PROMOTE_ACCEPTED" if commit_class == "OPERATION_CLAIM" else "RETAIN_DRAFT"
    assert original["decisionOutcome"] == expected
    assert ("AUTHORITY", "ALLOW") in _gates(env, original)
    assert ("VALIDATION", "PASS") in _gates(env, original)
    replay = _commit(env, submission)
    assert replay["idempotencyDisposition"] == "REPLAY_MATCH_REUSED_RESULT"
    assert replay["replayOfRequestId"] == original["requestId"]
    assert set(_roots(replay)).isdisjoint(_roots(original))
    wrong_farm_reader = _party(env.store)
    _grant(env.store, wrong_farm_reader, ["RECEIVE_READ_DATA"], targetScope={
        "scopeType": "FARM", "scopeRef": "farm:receipt-scope.other"})
    for result in (original, replay):
        _read(env, result)
        _read(env, result, 403, demo.AGENT)
        _read(env, result, 403, wrong_farm_reader)


def test_registry_reverified_field_receipts_and_matching_retries_remain_readable(env):
    submission = _submission("OPERATION_CLAIM")
    family = env.pipeline.runtime_services.registry_reference_family
    # The real selected provider rechecks the seeded binding against its current
    # bundle. No replacement provider, snapshot or stored trace is installed.
    submission["capturedAgainstSnapshotRef"] = family.snapshot_prefix + ".fictional-previous"
    original = _commit(env, submission)
    assert original["decisionOutcome"] == "PROMOTE_ACCEPTED"
    gates = _gates(env, original)
    assert gates.index(("AUTHORITY", "ALLOW")) < gates.index(
        ("VALIDATION", "REGISTRY_REVERIFIED")) < gates.index(("VALIDATION", "PASS"))
    replay = _commit(env, submission)
    assert replay["idempotencyDisposition"] == "REPLAY_MATCH_REUSED_RESULT"
    assert replay["replayOfRequestId"] == original["requestId"]
    assert set(_roots(replay)).isdisjoint(_roots(original))
    wrong_farm_reader = _party(env.store)
    _grant(env.store, wrong_farm_reader, ["RECEIVE_READ_DATA"], targetScope={
        "scopeType": "FARM", "scopeRef": "farm:receipt-scope.other"})
    for result in (original, replay):
        _read(env, result)
        _read(env, result, 403, demo.AGENT)
        _read(env, result, 403, wrong_farm_reader)


@pytest.mark.parametrize("commit_class", CLASSES)
@pytest.mark.parametrize("failure", ("authority", "validation", "evidence"))
def test_field_refusal_reads_depend_on_recorded_validation_pass(env, commit_class, failure):
    submission = _submission(commit_class)
    if failure == "authority":
        submission["actingPartyRef"] = demo.ADVISOR
    elif failure == "validation":
        submission["subjectRef"] = "field:receipt-scope.missing"
    else:
        submission["evidenceRefs"] = []
        if commit_class == "OPERATION_CLAIM":
            # Nonempty/resolving carrier refs pass validation, but a Party is
            # not durable evidence at the subsequent sufficiency gate.
            submission["payload"]["evidenceRefs"] = [demo.FARMER]
    result = _commit(env, submission)
    assert result["decisionOutcome"] != "PROMOTE_ACCEPTED"
    assert (("VALIDATION", "PASS") in _gates(env, result)) == (failure == "evidence")
    if failure == "evidence":
        assert ("EVIDENCE_SUFFICIENCY", "INSUFFICIENT") in _gates(env, result)
    _read(env, result, 200 if failure == "evidence" else 403)


def test_field_carrier_conflict_after_validation_pass_remains_readable(env):
    submission = _submission("OPERATION_CLAIM")
    original = _commit(env, submission)
    assert original["decisionOutcome"] == "PROMOTE_ACCEPTED"
    changed = deepcopy(submission)
    changed["idempotencyKey"] = _id("commit")
    changed["payload"]["actualQuantityParameters"][0]["value"] = 0.4
    result = _commit(env, changed)
    gates = _gates(env, result)
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert gates.index(("VALIDATION", "PASS")) < gates.index(("VALIDATION", "FAIL_CARRIER"))
    _read(env, result)


@pytest.mark.parametrize("commit_class", CLASSES)
@pytest.mark.parametrize("farm_hint", (False, True))
def test_field_conflict_cannot_gain_access_by_adding_a_farm_hint(env, commit_class, farm_hint):
    submission = _submission(commit_class)
    original = _commit(env, submission)
    changed = deepcopy(submission)
    changed["confirmAccept"] = False
    if farm_hint:
        changed["targetScopes"] = [FARM, FIELD]
    conflict = _commit(env, changed)
    assert conflict["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
    assert conflict["decisionOutcome"] == "DENY"
    _read(env, original)
    _read(env, conflict, 403)


@pytest.mark.parametrize("scopes", ("omitted", [], [FARM], [FARM, FIELD]))
def test_explicit_and_default_farm_original_replay_and_early_refusal_controls(env, scopes):
    submission = _submission("OPERATION_CLAIM", [] if scopes == "omitted" else scopes)
    if scopes == "omitted":
        del submission["targetScopes"]
    original = _commit(env, submission)
    replay = _commit(env, submission)
    assert replay["idempotencyDisposition"] == "REPLAY_MATCH_REUSED_RESULT"
    refused = deepcopy(submission)
    refused["idempotencyKey"] = _id("commit")
    refused["actingPartyRef"] = demo.ADVISOR
    refusal = _commit(env, refused)
    assert ("VALIDATION", "PASS") not in _gates(env, refusal)
    for result in (original, replay, refusal):
        _read(env, result)


@pytest.mark.parametrize("commit_class", CLASSES)
def test_ordinary_mixed_farm_receipts_deny_even_with_both_read_grants(env, commit_class):
    other_scope = {"scopeType": "FARM", "scopeRef": _id("farm")}
    _grant(env.store, demo.FARMER, ["RECEIVE_READ_DATA"], targetScope=other_scope)
    for scope in (FARM, other_scope):
        assert env.outputs.authority.evaluate_read(
            requesting_party_ref=demo.FARMER, farm_ref=scope["scopeRef"],
            artifact_family="OTHER").allowed
    scopes = [FARM, other_scope]
    result = _commit(env, _submission(commit_class, scopes))
    assert result["idempotencyDisposition"] == "NEW_REQUEST"
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert ("AUTHORITY", "ALLOW") in _gates(env, result)
    assert env.store.get_payload(result["requestId"])["targetScopes"] == scopes
    assert env.store.get_payload(result["semanticEventRef"])["anchorScopes"] == scopes
    _read(env, result, 403)


@pytest.mark.parametrize("attempt_scope", ("same-farm", "field-only", "other-farm"))
def test_explicit_farm_conflicts_require_consistent_farms_on_both_attempts(env, attempt_scope):
    submission = _submission("OPERATION_CLAIM", [FARM, FIELD])
    original = _commit(env, submission)
    changed = deepcopy(submission)
    changed["confirmAccept"] = False
    if attempt_scope == "field-only":
        changed["targetScopes"] = [FIELD]
    elif attempt_scope == "other-farm":
        other_farm = "farm:receipt-scope.other"
        changed["farmRef"] = other_farm
        changed["targetScopes"] = [{"scopeType": "FARM", "scopeRef": other_farm}]
        _grant(env.store, demo.FARMER, ["RECEIVE_READ_DATA"],
               targetScope={"scopeType": "FARM", "scopeRef": other_farm})
    conflict = _commit(env, changed)
    assert conflict["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
    assert conflict["decisionOutcome"] == "DENY"
    _read(env, original)
    _read(env, conflict, 200 if attempt_scope == "same-farm" else 403)


@pytest.mark.parametrize("commit_class", CLASSES)
@pytest.mark.parametrize("permission", ("direct", "sharing"))
def test_completed_revocation_denies_next_original_and_replay_read(env, commit_class, permission):
    submission = _submission(commit_class)
    original = _commit(env, submission)
    replay = _commit(env, submission)
    reader = _party(env.store)
    if permission == "direct":
        grant = _grant(env.store, reader, ["RECEIVE_READ_DATA"])
        family = "AUTHORITY_GRANT"
    else:
        grant, family = _id("share"), "SHARING_GRANT"
        with env.store.tx() as cursor:
            env.store.insert_record(cursor, {
                "schemaVersion": "ofarm.sharinggrant.v0.1", "sharingGrantId": grant,
                "grantorPartyRef": demo.FARMER, "granteePartyRef": reader,
                "sharedArtifactFamily": "OTHER", "sharedArtifactRef": original["resultId"],
                "targetScope": FARM, "validFrom": demo.VALID_FROM,
                "deliveryMode": "VIEW_ONLY", "sharingState": "ACTIVE",
            })
    for result in (original, replay):
        _read(env, result, actor=reader)
    with env.store.tx() as cursor:
        env.store.insert_record(cursor, {
            "schemaVersion": "ofarm.revocationdecision.v0.1",
            "revocationDecisionId": _id("revoke"),
            "revokesArtifactFamily": family, "revokesArtifactRef": grant,
            "decidedByPartyRef": demo.FARMER, "decidedAt": now_iso(),
            "effectiveFrom": demo.VALID_FROM, "revocationMode": "TERMINATE",
            "targetScope": FARM,
        })
    for result in (original, replay):
        _read(env, result, 403, reader)


@pytest.mark.parametrize("case", (
    "compliance", "structure", "note", "hypothesis", "evidence", "advisory",
    "queued-operation", "accept", "reject", "contest",
))
def test_other_classes_and_review_verbs_keep_farm_read_permissions(env, case):
    if case == "compliance":
        result = _commit(env, _compliance())
    elif case == "structure":
        result = _commit(env, demo.structure_submission(
            demo.field_identity_payload(_id("fieldpayload")), idem_key=_id("commit")))
    elif case in ("note", "hypothesis", "evidence", "advisory"):
        result = _commit(env, {
            "commitClass": {"note": "NOTE", "hypothesis": "HYPOTHESIS_ASSERTION",
                            "evidence": "EVIDENCE_RECORD", "advisory": "ADVISORY_OUTPUT"}[case],
            "actingPartyRef": demo.FARMER, "farmRef": demo.FARM,
            "idempotencyKey": _id("commit"), "eventTime": now_iso(),
        })
    else:
        pending = _commit(env, demo.spray_submission(
            _id("commit"), erp_id=_id("erp"), confirm=case == "contest"))
        if case == "queued-operation":
            result = pending
        else:
            target = ({"consequenceRef": pending["emittedAcceptedConsequenceRefs"][0]}
                      if case == "contest" else
                      {"assertionRef": pending["emittedAssertionRecordRefs"][0]})
            result = _post(env, f"/review/{case}", {
                "farmRef": demo.FARM, **target,
                "rationale": "Fictional receipt permission control",
                "idempotencyKey": _id(case),
            }, demo.ADVISOR)
            assert result["emittedReviewDecisionRefs"], result
    for reader, status in ((demo.FARMER, 200), (demo.ADVISOR, 200),
                           (demo.INSPECTOR, 403), (demo.AGENT, 403)):
        _read(env, result, status, reader)
