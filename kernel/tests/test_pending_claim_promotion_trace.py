"""Wire correspondence controls. The fictional references confer no authority."""
from dataclasses import replace
from hashlib import sha256
import json
from uuid import UUID

import pytest

from kernel._pending_claim_promotion_trace import _GateReferences, _check_gate_references
from kernel.tenant_claim_write_guard import CheckedClaimResult, SelectedClaimCommand
from kernel.tests.test_pending_claim_ingress_sources import _sources


def _trace_fixture(request_id, claim_id, validation_ref, trace_id):
    sources = _sources()
    sources.pop("batch_request_id")
    request = json.loads(sources["request_bytes"])
    request["requestId"] = request_id
    sources["request_bytes"] = json.dumps(request).encode()
    sources["request_bytes_sha256"] = sha256(sources["request_bytes"]).hexdigest()
    refs = _GateReferences(
        request_binding="original:request", classification_proof="proof:event",
        normalization_outcome="NORMALIZED_DRAFT", authorization_result="decision:allow",
        authorization_trace="trace:authority", selected_rule_binding="rule:revision",
        applicability_decision="decision:applicability", profile_context="context:profile",
        applicability_outcome="APPLICABLE", sufficiency_basis="decision:sufficiency",
        sufficiency_case="case:sufficiency", sufficiency_outcome="ALLOW",
    )
    # Assemble the fixture independently of the checker's field placement.
    gates = (
        ("INGRESS_NORMALIZATION", "NORMALIZED_DRAFT", ["original:request", "proof:event"]),
        ("AUTHORITY", "ALLOW", ["decision:allow", "trace:authority", "rule:revision"]),
        ("VALIDATION", "PASS", [validation_ref]),
        ("PACK_PROFILE_APPLICABILITY", "APPLICABLE", ["decision:applicability", "context:profile"]),
        ("EVIDENCE_SUFFICIENCY", "ALLOW", ["decision:sufficiency", "case:sufficiency"]),
        ("REVIEW_PROMOTION", "REQUIRE_REVIEW", [claim_id]),
    )
    trace = {
        "schemaVersion": "ofarm.promotiontrace.v0.1", "promotionTraceId": trace_id,
        "requestId": request_id, "evaluatedAt": "2000-01-01T12:12:00Z",
        "semanticEventRef": request["semanticEventRef"], "primaryEventFamily": sources["classified_family"],
        "commitClass": "OPERATION_CLAIM", "idempotencyKey": request["idempotencyKey"],
        "idempotencyDisposition": "NEW_REQUEST", "finalOutcome": "REQUIRE_REVIEW",
        "traceSummary": "The fictional claim is pending review.",
        "authorizationDecisionResultRef": "decision:allow", "evidenceSufficiencyCaseRef": "case:sufficiency",
        "emittedAssertionRecordRefs": [claim_id],
        "gateSequence": [
            {"gate": gate, "outcome": outcome, "relatedArtifactRefs": bindings}
            for gate, outcome, bindings in gates
        ],
    }
    return trace, {**sources, "gate_references": refs}


@pytest.fixture
def case():
    digest = "sha256:" + "1" * 64
    selected = SelectedClaimCommand(
        UUID(int=1), "ASSERT_OPERATION_CLAIM", digest,
        "ofarm.protectedeffect.assertionrecord.submit.v0.1", "0.1", digest,
        "ofarm.assertionrecord.v0.2", digest,
    )
    claim = CheckedClaimResult(selected, "claim:test", digest, "trace:validation", digest, "payload:test", digest)
    trace, sources = _trace_fixture("request:test", claim.assertion_id, claim.validation_trace_ref, "trace:test")
    return trace, sources["gate_references"], claim


@pytest.mark.parametrize("gate", range(6))
def test_other_artifact_or_outcome_in_any_gate_is_refused(case, gate):
    trace, refs, claim = case
    entry = trace["gateSequence"][gate]
    entry["relatedArtifactRefs"].append("foreign:ref")
    with pytest.raises(ValueError):
        _check_gate_references(trace, refs, claim)
    entry["relatedArtifactRefs"].pop()
    entry["outcome"] = "DENY"
    with pytest.raises(ValueError):
        _check_gate_references(trace, refs, claim)


def test_exemption_requires_its_own_basis_and_absent_case(case):
    trace, refs, claim = case
    refs = replace(refs, sufficiency_outcome="NOT_APPLICABLE", sufficiency_case=None)
    trace["gateSequence"][4].update(outcome="NOT_APPLICABLE", relatedArtifactRefs=[refs.sufficiency_basis])
    with pytest.raises(ValueError):
        _check_gate_references(trace, refs, claim)
    del trace["evidenceSufficiencyCaseRef"]
    _check_gate_references(trace, refs, claim)
    trace["gateSequence"][4]["relatedArtifactRefs"].clear()
    with pytest.raises(ValueError):
        _check_gate_references(trace, refs, claim)


@pytest.mark.parametrize("field", ["authorizationDecisionResultRef", "evidenceSufficiencyCaseRef"])
def test_top_level_binding_must_agree_with_its_gate(case, field):
    trace, refs, claim = case
    trace[field] = "other:source"
    with pytest.raises(ValueError):
        _check_gate_references(trace, refs, claim)


@pytest.mark.parametrize("outcome", ["REFUSE", "UNVERIFIED", "NOT_APPLICABLE"])
def test_applicable_case_cannot_refuse_or_silently_skip_the_submission(case, outcome):
    trace, refs, claim = case
    trace["gateSequence"][4]["outcome"] = outcome
    with pytest.raises(ValueError):
        _check_gate_references(trace, replace(refs, sufficiency_outcome=outcome), claim)


def test_preserves_evidence_owners_review_disposition(case):
    trace, refs, claim = case
    trace["gateSequence"][4]["outcome"] = "REQUIRE_REVIEW"
    _check_gate_references(trace, replace(refs, sufficiency_outcome="REQUIRE_REVIEW"), claim)


def test_original_request_and_classification_reference_different_artifacts(case):
    trace, refs, claim = case
    trace["gateSequence"][0]["relatedArtifactRefs"] = [refs.request_binding]
    with pytest.raises(ValueError, match="same reference"):
        _check_gate_references(trace, replace(refs, classification_proof=refs.request_binding), claim)


def test_gate_swap_omission_and_repetition_are_refused(case):
    trace, refs, claim = case
    gates = trace["gateSequence"]
    for wrong in ([gates[1], gates[0], *gates[2:]], gates[:-1], [*gates, gates[-1]]):
        with pytest.raises(ValueError):
            _check_gate_references({**trace, "gateSequence": wrong}, refs, claim)


@pytest.mark.parametrize(("gate_index", "field", "disposition"), [
    (0, "normalization_outcome", "DENY"),
    (3, "applicability_outcome", "UNVERIFIED"),
])
def test_refused_owner_disposition_cannot_route_to_pending_review(case, gate_index, field, disposition):
    trace, refs, claim = case
    trace["gateSequence"][gate_index]["outcome"] = disposition
    with pytest.raises(ValueError):
        _check_gate_references(trace, replace(refs, **{field: disposition}), claim)
