"""Source-binding refusal tests independent of the unaccepted classification checker."""
from dataclasses import replace
from hashlib import sha256
import json
from uuid import UUID

import pytest

from kernel._submission_event_admission import (
    _EventAdmission,
    _ProofSelection,
    _RetainedProof,
    _Submission,
)
from kernel.tenant_claim_write_guard import ClaimWriteAttempt
from kernel.tests.test_postgresql_tenant_claim_write_guard import _command


def _json(document):
    return json.dumps(document, separators=(",", ":")).encode("utf-8")


def _original_intent(event_kind="ASSOCIATED_WORLD_EVENT", *, event_digest=None):
    intent = {"effectSubject": {"subjectRef": "assertion:proposed"}, "subject": {"subjectRef": "field:first"}}
    if event_kind == "ASSOCIATED_WORLD_EVENT":
        selector = {"revisionRef": "event:field:r1"} if event_digest is None else {"digest": event_digest}
        intent["associatedSemanticEventBinding"] = {"ref": "event:field", **selector}
    return _json(intent)


def _case(*, tenant_id=UUID(int=17), request_id="request:submit", actor="party:submitter",
          event_kind="ASSOCIATED_WORLD_EVENT", event_digest=None, event_ref=None, proof_ref="proof:earlier"):
    intent = _original_intent(event_kind, event_digest=event_digest)
    attempt = ClaimWriteAttempt(
        _command(tenant_id, "sha256:" + "1" * 64), UUID(int=42), "batch:one", 99, intent,
    )
    if event_ref is None:
        event_ref = "event:field" if event_kind == "ASSOCIATED_WORLD_EVENT" else "event:submission"
    scope = {"scopeType": "FIELD", "scopeRef": "field:first"}
    request = _json({
        "schemaVersion": "ofarm.commitingressrequest.v0.1", "requestId": request_id,
        "ingestedAt": "2000-01-01T10:00:00Z", "ingressChannel": "MANUAL_UI",
        "actingPartyRef": actor, "commitClass": "OPERATION_CLAIM", "semanticEventRef": event_ref,
        "targetScopes": [scope], "idempotencyKey": "retry:One",
    })
    envelope = _json({
        "schemaVersion": "ofarm.semanticeventenvelope.v0.1", "semanticEventId": event_ref,
        "primaryEventFamily": "OccurrenceEvent",
        "dominantSemanticConsequence": ("A fictional operation claim was submitted." if event_kind == "SUBMISSION_ACT"
                                        else "A fictional occurrence was reported."),
        "anchorScopes": [scope], "subjectRefs": ["field:first"],
        "timeSemantics": {"eventTime": "2000-01-01T09:00:00Z", "recordTime": "2000-01-01T09:05:00Z"},
    })
    context = _json({"productionMode": "PREEXISTING_PROOF", "expectedProofId": proof_ref})
    profile = _json({"profileId": "profile:fixture"})
    # Simple ASCII strings in lexical key order give this fictional value known canonical bytes.
    proof = _json({"productionMode": "PREEXISTING_PROOF", "proofId": proof_ref})
    selection = _ProofSelection(
        tenant_id=attempt.command.tenant_id, producer_ref="issuer:event", request_sha256=sha256(request).hexdigest(),
        intent_sha256=sha256(intent).hexdigest(), event_kind=event_kind, event_ref=event_ref,
        event_revision=event_ref + ":r1" if event_digest is None else None, event_digest=event_digest,
        envelope_sha256=sha256(envelope).hexdigest(), proof_ref=proof_ref,
        profile_sha256=sha256(profile).hexdigest(), context_sha256=sha256(context).hexdigest(),
        contract_sha256=sha256(b"fictional contract selection").hexdigest(),
        proof_digest="sha256:" + sha256(proof).hexdigest(),
    )
    submission = _Submission(
        attempt=attempt, request_bytes=request, request_id=request_id, idempotency_key="retry:One",
        acting_party_ref=actor, acting_agent_ref=None, target_scopes=(("FIELD", "field:first"),),
        selection=selection,
    )
    # These two documents exercise the source checks only. No fixture supplies a checker result.
    source = _RetainedProof(
        selection=selection, production_mode="PREEXISTING_PROOF", envelope_bytes=envelope,
        proof_bytes=proof,
        context_bytes=context, profile_bytes=profile,
    )
    return submission, source


@pytest.mark.parametrize("event_kind", ["ASSOCIATED_WORLD_EVENT", "SUBMISSION_ACT"])
def test_matching_originals_still_require_accepted_checker(event_kind):
    submission, source = _case(event_kind=event_kind)
    reads = []

    def read(proof_ref):
        reads.append(proof_ref)
        return source

    with pytest.raises(RuntimeError, match="accepted Event Ingress checker unavailable"):
        _EventAdmission(submission, read).admit(submission.attempt)
    assert reads == ["proof:earlier"]


@pytest.mark.parametrize("component,change", [
    ("binding_nonce", UUID(int=43)), ("full_xid", 100), ("batch_id", "batch:two"),
    ("intent_bytes", b'{"effectSubject":{"subjectRef":"assertion:other"}}'),
])
def test_other_attempt_cannot_read_even_with_same_proof_ref(component, change):
    submission, _ = _case()
    other = replace(submission.attempt, **{component: change})

    def unexpected_read(ref):
        pytest.fail(f"refused attempt read {ref}")

    with pytest.raises(ValueError):
        _EventAdmission(submission, unexpected_read).admit(other)


@pytest.mark.parametrize("component,change", [
    ("tenant_id", UUID(int=18)), ("producer_ref", "issuer:other"), ("proof_ref", "proof:other"),
    ("event_revision", "event:field:r2"), ("intent_sha256", "1" * 64), ("contract_sha256", "2" * 64),
    ("proof_digest", "sha256:" + "3" * 64),
])
def test_wrong_retained_provenance_refuses(component, change):
    submission, source = _case()
    other = replace(source, selection=replace(source.selection, **{component: change}))
    with pytest.raises(ValueError):
        _EventAdmission(submission, lambda ref: other).admit(submission.attempt)


@pytest.mark.parametrize("original", ["request_bytes", "envelope_bytes", "context_bytes", "profile_bytes"])
def test_equivalent_json_cannot_replace_original_octets(original):
    submission, source = _case()
    if original == "request_bytes":
        submission = replace(submission, request_bytes=submission.request_bytes + b" ")
    else:
        source = replace(source, **{original: getattr(source, original) + b" "})
    with pytest.raises(ValueError):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)


@pytest.mark.parametrize("field,value", [
    ("requestId", "request:other"), ("idempotencyKey", "retry:one"), ("actingPartyRef", "party:other"),
    ("actingAgentRef", "agent:unbound"), ("semanticEventRef", "event:other"), ("commitClass", "NOTE"),
    ("targetScopes", [{"scopeType": "FIELD", "scopeRef": "field:other"}]),
])
def test_matching_raw_pin_alone_cannot_bind_changed_request_fields(field, value):
    submission, source = _case()
    request = _json({**json.loads(submission.request_bytes), field: value})
    selection = replace(submission.selection, request_sha256=sha256(request).hexdigest())
    submission = replace(submission, selection=selection, request_bytes=request)
    source = replace(source, selection=selection)
    with pytest.raises(ValueError):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)


@pytest.mark.parametrize("timing_source", ["production_mode", "proof_bytes", "context_bytes"])
def test_validation_time_proof_cannot_enter_preexisting_path(timing_source):
    submission, source = _case()
    mode = "VALIDATION_PHASE_PROOF"
    value = mode
    if timing_source != "production_mode":
        value = _json({**json.loads(getattr(source, timing_source)), "productionMode": mode})
    if timing_source == "context_bytes":
        selection = replace(submission.selection, context_sha256=sha256(value).hexdigest())
        submission = replace(submission, selection=selection)
        source = replace(source, selection=selection)
    source = replace(source, **{timing_source: value})
    with pytest.raises(ValueError):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)


@pytest.mark.parametrize("component,id_field", [("proof_bytes", "proofId"), ("context_bytes", "expectedProofId")])
def test_proof_and_context_must_name_the_selected_proof(component, id_field):
    submission, source = _case()
    raw = _json({**json.loads(getattr(source, component)), id_field: "proof:other"})
    if component == "context_bytes":
        selection = replace(submission.selection, context_sha256=sha256(raw).hexdigest())
        submission = replace(submission, selection=selection)
        source = replace(source, selection=selection)
    source = replace(source, **{component: raw})
    with pytest.raises(ValueError):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)


def test_world_event_and_submission_act_cannot_trade_sources():
    submission, source = _case()
    # Align the intent digest but keep the independent source bound to a world event.
    raw = _original_intent("SUBMISSION_ACT")
    selection = replace(submission.selection, intent_sha256=sha256(raw).hexdigest())
    submission = replace(submission, attempt=replace(submission.attempt, intent_bytes=raw), selection=selection)
    source = replace(source, selection=selection)
    with pytest.raises(ValueError):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)


def test_world_event_revision_must_match_the_intent():
    submission, source = _case()
    selection = replace(submission.selection, event_revision="event:field:r2")
    submission = replace(submission, selection=selection)
    source = replace(source, selection=selection)
    with pytest.raises(ValueError):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)


def test_digest_selected_world_event_still_requires_checker():
    # The owner's content digest and the original envelope's raw hash are separate bindings.
    submission, source = _case(event_digest="sha256:" + "7" * 64)
    with pytest.raises(RuntimeError, match="accepted Event Ingress checker unavailable"):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)


@pytest.mark.parametrize("change", [
    {"event_revision": None}, {"event_digest": "sha256:" + "7" * 64},
])
def test_event_requires_exactly_one_immutable_selector(change):
    submission, source = _case()
    selection = replace(submission.selection, **change)
    submission = replace(submission, selection=selection)
    source = replace(source, selection=selection)
    with pytest.raises(ValueError):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)


def test_selected_original_cannot_exceed_two_mib():
    submission, source = _case()
    oversized = source.profile_bytes.ljust(2 * 1024 * 1024 + 1)
    selection = replace(submission.selection, profile_sha256=sha256(oversized).hexdigest())
    submission = replace(submission, selection=selection)
    source = replace(source, selection=selection, profile_bytes=oversized)
    with pytest.raises(ValueError):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)


def test_matching_effect_intent_larger_than_two_mib_still_requires_checker():
    submission, source = _case()
    intent = submission.attempt.intent_bytes.ljust(2 * 1024 * 1024 + 1)
    attempt = replace(submission.attempt, intent_bytes=intent)
    selection = replace(submission.selection, intent_sha256=sha256(intent).hexdigest())
    submission = replace(submission, attempt=attempt, selection=selection)
    source = replace(source, selection=selection)
    with pytest.raises(RuntimeError, match="accepted Event Ingress checker unavailable"):
        _EventAdmission(submission, lambda ref: source).admit(attempt)


def test_selected_profile_cannot_exceed_allowed_nesting():
    submission, source = _case()
    deep = b'{"fixture":' + b'[' * 65 + b'0' + b']' * 65 + b'}'
    selection = replace(submission.selection, profile_sha256=sha256(deep).hexdigest())
    submission = replace(submission, selection=selection)
    source = replace(source, selection=selection, profile_bytes=deep)
    with pytest.raises(ValueError):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)


@pytest.mark.parametrize("field,value", [
    ("contract_sha256", None), ("context_sha256", "A" * 64), ("profile_sha256", "sha256:" + "3" * 64),
    ("proof_digest", "b" * 64),
])
def test_matching_malformed_pins_never_reach_checker(field, value):
    submission, source = _case()
    selection = replace(submission.selection, **{field: value})
    submission = replace(submission, selection=selection)
    source = replace(source, selection=selection)
    with pytest.raises(ValueError):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)
