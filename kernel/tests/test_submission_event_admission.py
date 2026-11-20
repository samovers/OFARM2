"""Exercise admission and original-result readback against the adopted offline checker."""
from dataclasses import replace
from hashlib import sha256
import json
import shutil
from uuid import UUID

import pytest
import rfc8785

from kernel import _submission_event_admission as admission
from kernel import _submission_event_checker as checker

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


def _canonical_digest(raw):
    return "sha256:" + sha256(rfc8785.dumps(json.loads(raw))).hexdigest()


def _reference(ref, raw):
    return {"ref": ref, "digest": _canonical_digest(raw)}


def _case(*, tenant_id=UUID(int=17), request_id="request:submit", actor="party:submitter",
          event_kind="ASSOCIATED_WORLD_EVENT", event_digest=None, event_ref=None, proof_ref="proof:earlier",
          allow_reevaluation=False):
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
    # These are independently chosen fixture cases. Their families do not generalize to other submissions.
    if event_kind == "SUBMISSION_ACT":
        family, clause = "GovernanceEvent", "3.7"
        consequence = "A grower formally submitted an operation claim for field one."
        reason = "The described act files a claim for review."
    else:
        family, clause = "OccurrenceEvent", "3.3"
        consequence = "Overnight frost damaged plants in field one."
        reason = "The frost damage is a natural occurrence."
    case = {
        "caseId": "case:" + event_kind.lower(), "dominantSemanticConsequence": consequence,
        "subtype": {"presence": "ABSENT"}, "authoritativePrimaryFamily": family,
    }
    envelope = _json({
        "schemaVersion": "ofarm.semanticeventenvelope.v0.1", "semanticEventId": event_ref,
        "primaryEventFamily": family, "dominantSemanticConsequence": consequence,
        "anchorScopes": [scope], "subjectRefs": ["field:first"],
        "timeSemantics": {"eventTime": "2000-01-01T09:00:00Z", "recordTime": "2000-01-01T09:05:00Z"},
    })
    contract = {
        "ref": "ofarm.event-ingress.pre-verdict-classification.v0.1",
        "digest": "sha256:3f17e7aff4379f671a989d5e7aeb88c1a0bedea45861f453396179de62e7f4c1",
    }
    owner = "EVENT_INGRESS_CLASSIFICATION"
    profile_id = "profile:fixture"
    profile = _json({
        "schemaVersion": "ofarm.eventClassificationProfile.v0.1", "profileId": profile_id,
        "profileRevision": "revision:1", "contractBinding": contract, "ownerRole": owner,
        "selectionMethod": "EXACT_DOMINANT_CONSEQUENCE_AND_SUBTYPE",
        "cases": [{**case, "semanticSourceBinding": {
            "ref": "ofarm:event-grammar:v0.1",
            "digest": "sha256:47784169916b66fec510a7a95c86b19b5c222ef987c6d29c26f9a250632a61b3",
        }, "sourceClause": clause, "classificationReason": reason}],
        "limits": "Classification of the supplied event description only; no occurrence, acceptance, authority or runtime admission.",
    })
    bindings = {
        "ownerRole": owner, "contractBinding": contract,
        "classificationProfileBinding": _reference(profile_id, profile),
        "envelopeBinding": _reference(event_ref, envelope), "envelopeBytesSha256": sha256(envelope).hexdigest(),
        "ingressRequestBinding": _reference(request_id, request), "ingressRequestBytesSha256": sha256(request).hexdigest(),
        "productionMode": "PREEXISTING_PROOF", "reuseRule": "EXACT_ENVELOPE_REQUEST_PROFILE_CONTEXT_AND_PROOF",
    }
    milestone = "CLASSIFICATION_COMPLETE_BEFORE_DEPENDENT_VERDICT"
    modes = ["INITIAL_EVALUATION"]
    if allow_reevaluation:
        modes.append("EXACT_REEVALUATION")
    context_id = "context:" + proof_ref
    context = _json({
        **bindings, "schemaVersion": "ofarm.eventClassificationContext.v0.1", "contextId": context_id,
        "selectedCaseId": case["caseId"], "expectedCommitClass": "OPERATION_CLAIM", "expectedTargetScopes": [scope],
        "expectedProofId": proof_ref, "permittedUseModes": modes, "requiredMilestone": milestone,
        "inputRoles": ["PINNED_CONTRACT", "SELECTED_CLASSIFICATION_PROFILE", "FIXED_ENVELOPE",
                       "FIXED_INGRESS_REQUEST", "INDEPENDENT_OWNER_CONTEXT"],
    })
    proof = _json({
        **bindings, "schemaVersion": "ofarm.preVerdictEventClassificationProof.v0.1", "proofId": proof_ref,
        "ownerContextBinding": _reference(context_id, context), "completionMilestone": milestone,
        "classification": {**case, "commitClass": "OPERATION_CLAIM"},
    })
    selection = _ProofSelection(
        tenant_id=attempt.command.tenant_id, producer_ref="issuer:event", request_sha256=sha256(request).hexdigest(),
        intent_sha256=sha256(intent).hexdigest(), event_kind=event_kind, event_ref=event_ref,
        event_revision=event_ref + ":r1" if event_digest is None else None, event_digest=event_digest,
        envelope_sha256=sha256(envelope).hexdigest(), proof_ref=proof_ref,
        profile_sha256=sha256(profile).hexdigest(), context_sha256=sha256(context).hexdigest(),
        contract_sha256="ee79119ebf0b9a42ff790e9302d7b58afad478c74f9b484719007a3c0a162382",
        proof_digest=_canonical_digest(proof),
    )
    submission = _Submission(
        attempt=attempt, request_bytes=request, request_id=request_id, idempotency_key="retry:One",
        acting_party_ref=actor, acting_agent_ref=None, target_scopes=(("FIELD", "field:first"),),
        selection=selection,
    )
    source = _RetainedProof(
        selection=selection, production_mode="PREEXISTING_PROOF", envelope_bytes=envelope,
        proof_bytes=proof,
        context_bytes=context, profile_bytes=profile,
    )
    return submission, source


@pytest.mark.parametrize("event_kind", ["ASSOCIATED_WORLD_EVENT", "SUBMISSION_ACT"])
def test_matching_originals_pass_accepted_checker(event_kind):
    submission, source = _case(event_kind=event_kind)
    reads = []

    def read(proof_ref):
        reads.append(proof_ref)
        return source

    binding = _EventAdmission(submission, read).admit(submission.attempt)
    assert binding.attempt == submission.attempt and binding.selection == submission.selection
    assert binding.proof_sha256 == sha256(source.proof_bytes).hexdigest()
    assert binding.disposition == "CONDITIONAL_CONFORMANCE_PASS"
    assert binding.family == ("GovernanceEvent" if event_kind == "SUBMISSION_ACT" else "OccurrenceEvent")
    assert binding.commit_class == "OPERATION_CLAIM"
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


def test_content_digest_selects_only_its_original_envelope():
    _, original = _case()
    submission, source = _case(event_digest=_canonical_digest(original.envelope_bytes))
    assert _EventAdmission(submission, lambda ref: source).admit(submission.attempt).selection == source.selection
    wrong, source = _case(event_digest="sha256:" + "7" * 64)
    with pytest.raises(ValueError):
        _EventAdmission(wrong, lambda ref: source).admit(wrong.attempt)


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


def test_two_mib_checker_limit_excludes_original_effect_intent():
    submission, source = _case()
    intent = submission.attempt.intent_bytes.ljust(2 * 1024 * 1024 + 1)
    attempt = replace(submission.attempt, intent_bytes=intent)
    selection = replace(submission.selection, intent_sha256=sha256(intent).hexdigest())
    submission = replace(submission, attempt=attempt, selection=selection)
    source = replace(source, selection=selection)
    assert _EventAdmission(submission, lambda ref: source).admit(attempt).attempt == attempt


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


@pytest.mark.parametrize("allow_reevaluation", [False, True])
def test_readback_uses_recorded_result_and_original_use_permission(monkeypatch, allow_reevaluation):
    submission, source = _case(allow_reevaluation=allow_reevaluation)
    modes = []
    verify = admission._verify_classification

    def observe(*args):
        modes.append(args[-1])
        return verify(*args)

    monkeypatch.setattr(admission, "_verify_classification", observe)
    attempt = submission.attempt
    recorded = _EventAdmission(submission, lambda ref: source).admit(attempt)
    fresh = _EventAdmission(submission, lambda ref: source)
    assert fresh.readback(attempt, recorded) == fresh.readback(attempt, recorded) == recorded
    assert modes == ["INITIAL_EVALUATION"]
    if allow_reevaluation:
        assert fresh.readback(attempt, recorded, reevaluate=True) == recorded
        assert modes == ["INITIAL_EVALUATION", "EXACT_REEVALUATION"]
    else:
        with pytest.raises(ValueError, match="original context forbids exact reevaluation"):
            fresh.readback(attempt, recorded, reevaluate=True)
        assert modes == ["INITIAL_EVALUATION"]


@pytest.mark.parametrize("field,changed", [
    ("disposition", "CONDITIONAL_CONFORMANCE_FAIL"), ("family", "EvidenceEvent"),
    ("commit_class", "NOTE"), ("proof_sha256", "0" * 64), ("request_id", "request:different"),
])
def test_readback_rejects_changed_recorded_result(field, changed):
    submission, source = _case()
    op = _EventAdmission(submission, lambda ref: source)
    recorded = op.admit(submission.attempt)
    with pytest.raises(ValueError, match="recorded event admission differs"):
        op.readback(submission.attempt, replace(recorded, **{field: changed}))


def test_readback_rejects_changed_proof_octets_or_different_attempt():
    submission, source = _case()
    recorded = _EventAdmission(submission, lambda ref: source).admit(submission.attempt)
    reserialized = replace(source, proof_bytes=source.proof_bytes + b" ")
    op = _EventAdmission(submission, lambda ref: reserialized)
    with pytest.raises(ValueError, match="recorded event admission differs"):
        op.readback(submission.attempt, recorded)
    with pytest.raises(ValueError, match="recorded event admission differs"):
        op.readback(replace(submission.attempt, batch_id="batch:other"), recorded)
    equal_valued_float = replace(recorded.attempt, full_xid=float(recorded.attempt.full_xid))
    with pytest.raises(ValueError, match="recorded event admission differs"):
        op.readback(submission.attempt, replace(recorded, attempt=equal_valued_float))


def test_genuine_checker_refuses_selected_but_invalid_proof():
    submission, source = _case()
    proof = json.loads(source.proof_bytes)
    proof["classification"]["authoritativePrimaryFamily"] = "MaterialEvent"
    raw = _json(proof)
    selection = replace(source.selection, proof_digest=_canonical_digest(raw))
    submission = replace(submission, selection=selection)
    source = replace(source, selection=selection, proof_bytes=raw)
    with pytest.raises(ValueError, match="event classification did not pass"):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)


def test_checker_unavailable_when_accepted_source_is_missing(monkeypatch, tmp_path):
    submission, source = _case()
    monkeypatch.setattr(checker, "_PACKAGE", tmp_path)
    with pytest.raises(RuntimeError, match="accepted Event Ingress checker unavailable"):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)


@pytest.mark.parametrize("member", [
    "verify_event_proof.py", "report_contract.py", "schemas/report.schema.json",
    "sources/event-grammar.md", "dependency-manifest.json",
])
def test_changed_package_member_prevents_admission(monkeypatch, tmp_path, member):
    submission, source = _case()
    package = tmp_path / "copy"
    shutil.copytree(checker._PACKAGE, package)
    with (package / member).open("ab") as changed:
        changed.write(b" ")
    monkeypatch.setattr(checker, "_PACKAGE", package)
    with pytest.raises(RuntimeError, match="accepted Event Ingress checker unavailable"):
        _EventAdmission(submission, lambda ref: source).admit(submission.attempt)
