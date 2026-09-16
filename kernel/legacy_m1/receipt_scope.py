"""Bounded legacy receipt provenance; current read permission is decided elsewhere."""
from __future__ import annotations

from dataclasses import dataclass

from .. import policy


RESULT = "ofarm.commitingressresult.v0.1"
TRACE = "ofarm.promotiontrace.v0.1"
REQUEST = "ofarm.commitingressrequest.v0.1"
EVENT = "ofarm.semanticeventenvelope.v0.1"
AUTH_RESULT = "ofarm.authorizationdecisionresult.v0.1"
AUTH_REQUEST = "ofarm.authorizationdecisionrequest.v0.1"
RECEIPT_KINDS = frozenset((RESULT, TRACE))
_EMISSIONS = (
    "emittedAssertionRecordRefs", "emittedReviewDecisionRefs",
    "emittedAcceptedConsequenceRefs",
)


class _Unresolved(Exception):
    pass


def _require(condition):
    if not condition:
        raise _Unresolved


def _text(value):
    _require(isinstance(value, str) and bool(value.strip()))
    return value


def _receipt(row):
    return (_text(row["tenant_ref"]), _text(row["runtime_bundle_digest"]))


def _checked(store, row, kind, reference, receipt=None):
    _require(isinstance(row, dict) and row["record_kind"] == kind)
    payload = row["payload"]
    _require(isinstance(payload, dict) and payload["schemaVersion"] == kind)
    _require(row["record_id"] == reference
             == payload[store.registry.get(kind).id_field])
    _require(_receipt(row)[0] == store.tenant_ref)
    if receipt is not None:
        _require(_receipt(row) == receipt)
    return row


def _load(store, reference, kind, receipt=None):
    return _checked(store, store.get_record(_text(reference)), kind, reference, receipt)


def _scopes(payload, field):
    scopes = payload[field]
    _require(isinstance(scopes, list) and bool(scopes))
    for scope in scopes:
        _require(isinstance(scope, dict))
        _text(scope["scopeType"])
        _text(scope["scopeRef"])
    return scopes


def _farm(scopes):
    farms = {s["scopeRef"] for s in scopes if s["scopeType"] == "FARM"}
    _require(len(farms) <= 1)
    return next(iter(farms), None)


@dataclass(frozen=True)
class _Attempt:
    trace: dict
    request: dict
    event: dict
    receipt: tuple[str, str]
    event_receipt: tuple[str, str]
    result: dict | None


def _attempt(store, row):
    kind = row["record_kind"]
    _require(kind in RECEIPT_KINDS)
    _checked(store, row, kind, _text(row["record_id"]))
    result = row["payload"] if kind == RESULT else None
    trace_row = (_load(store, result["promotionTraceRef"], TRACE, _receipt(row))
                 if result is not None else row)
    trace = trace_row["payload"]
    receipt = _receipt(trace_row)
    request = _load(store, trace["requestId"], REQUEST, receipt)["payload"]
    event_row = _load(store, trace["semanticEventRef"], EVENT)
    event = event_row["payload"]
    _require(request["semanticEventRef"] == trace["semanticEventRef"])
    _require(request["commitClass"] == trace["commitClass"])
    _require(event["primaryEventFamily"] == trace["primaryEventFamily"])
    _require(_text(request["idempotencyKey"]) == trace["idempotencyKey"])
    if result is not None:
        for field in ("requestId", "semanticEventRef", "commitClass",
                      "primaryEventFamily", "idempotencyDisposition"):
            _require(result[field] == trace[field])
        _require(result["decisionOutcome"] == trace["finalOutcome"])
        _require(result.get("replayOfRequestId") == trace.get("replayOfRequestId"))
        if trace["idempotencyDisposition"] == "NEW_REQUEST":
            for field in _EMISSIONS:
                _require(result.get(field, []) == trace.get(field, []))
    _scopes(request, "targetScopes")
    _scopes(event, "anchorScopes")
    return _Attempt(trace, request, event, receipt, _receipt(event_row), result)


def _ordinary_farm(store, attempt):
    trace, request, event = attempt.trace, attempt.request, attempt.event
    _require(trace["idempotencyDisposition"] == "NEW_REQUEST")
    _require("replayOfRequestId" not in trace)
    _require(attempt.event_receipt == attempt.receipt)
    _require(request["targetScopes"] == event["anchorScopes"])
    farm = _farm(event["anchorScopes"])
    auth_result = auth_request = None
    if "authorizationDecisionResultRef" in trace:
        auth_result = _load(store, trace["authorizationDecisionResultRef"],
                            AUTH_RESULT, attempt.receipt)["payload"]
        auth_request = _load(store, auth_result["requestId"],
                             AUTH_REQUEST, attempt.receipt)["payload"]
        target = auth_request["target"]
        _require(isinstance(target, dict) and isinstance(target["scope"], dict))
        _require(target["scope"]["scopeType"] == "FARM")
        evaluated_farm = _text(target["scope"]["scopeRef"])
        _require(farm is None or farm == evaluated_farm)
    if farm is not None:
        return farm
    _require(trace["commitClass"] in ("OPERATION_CLAIM", "OBSERVATION_ASSERTION"))
    _require(all(s["scopeType"] == "FIELD" for s in event["anchorScopes"]))
    _require(auth_result is not None and auth_request is not None)
    action = policy.COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS[trace["commitClass"]]
    _require(auth_request["actingPartyRef"] == request["actingPartyRef"])
    _require(auth_request["actionClass"] == auth_result["requestedActionClass"] == action)
    _require(auth_request["actionStage"] == auth_result["actionStage"] == "PROMOTION")
    _require(auth_result["decisionOutcome"] == "ALLOW"
             and auth_result["finalActionPermitted"] is True)
    gates = trace["gateSequence"]
    _require(isinstance(gates, list) and all(isinstance(g, dict) for g in gates))
    authority = [(i, g) for i, g in enumerate(gates) if g.get("gate") == "AUTHORITY"]
    validation = [(i, g) for i, g in enumerate(gates) if g.get("gate") == "VALIDATION"]
    _require(len(authority) == 1 and bool(validation))
    index, gate = authority[0]
    # Successful registry rechecks precede validation completion, not refusal.
    completion = next((g for _, g in validation
                       if g.get("outcome") != "REGISTRY_REVERIFIED"), {})
    _require(gate["outcome"] == "ALLOW" and validation[0][0] > index
             and completion.get("outcome") == "PASS")
    refs = gate["relatedArtifactRefs"]
    _require(isinstance(refs, list) and auth_result["resultId"] in refs
             and auth_request["requestId"] in refs)
    return evaluated_farm


def _original(store, attempt):
    trace, request = attempt.trace, attempt.request
    # Read the existing tenant-bound index; do not open a new transaction owner.
    with store.conn.cursor() as cursor:
        entry = store.idempotency_lookup(cursor, trace["idempotencyKey"])
    _require(isinstance(entry, dict))
    _require(entry["idempotency_key"] == trace["idempotencyKey"])
    _require(entry["request_id"] == trace["replayOfRequestId"] != request["requestId"])
    original = _attempt(store, _load(store, entry["result_record_id"], RESULT,
                                     _receipt(entry)))
    _require(original.trace["idempotencyDisposition"] == "NEW_REQUEST")
    _require(original.request["requestId"] == entry["request_id"])
    _require(original.request["idempotencyKey"] == entry["idempotency_key"])
    _require(_text(original.request["sourcePayloadDigest"])
             == _text(entry["source_payload_digest"]))
    for field in ("semanticEventRef", "commitClass", "primaryEventFamily"):
        _require(trace[field] == original.trace[field])
    return original


def receipt_farm_scopes(store, row) -> list[str] | None:
    """Resolve only these two receipt roots, or deny; never evaluate permission."""
    try:
        attempt = _attempt(store, row)
        disposition = attempt.trace["idempotencyDisposition"]
        if disposition == "NEW_REQUEST":
            return [_ordinary_farm(store, attempt)]
        _require(disposition in ("REPLAY_MATCH_REUSED_RESULT", "CONFLICTING_REPLAY_BLOCKED"))
        original = _original(store, attempt)
        farm = _ordinary_farm(store, original)
        if disposition == "REPLAY_MATCH_REUSED_RESULT":
            _require(attempt.trace["finalOutcome"] == "REPLAY_REUSED_RESULT")
            _require(attempt.receipt == original.receipt)
            _require(_text(attempt.request["sourcePayloadDigest"])
                     == original.request["sourcePayloadDigest"])
            _require(attempt.request["targetScopes"] == original.request["targetScopes"])
            # ReplayWriter carries reused emissions on the result only. A trace
            # root has no reverse result link and needs no invented lookup.
            if attempt.result is not None:
                for field in _EMISSIONS:
                    _require(attempt.result.get(field, []) == original.trace.get(field, []))
        else:
            _require(attempt.trace["finalOutcome"] == "DENY")
            _require(_farm(original.event["anchorScopes"]) == farm
                     == _farm(attempt.request["targetScopes"]))
        return [farm]
    except (_Unresolved, KeyError, TypeError):
        return None
