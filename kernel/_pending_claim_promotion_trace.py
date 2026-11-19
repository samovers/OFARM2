"""Read back pending promotion evidence. Source admission belongs to its owners."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._pending_claim_ingress_sources import verify_original_ingress_sources
from ._pending_claim_promotion_readback import _read_stored_promotion
from ._pending_claim_schemas import validate_document
from .runtime_bundle import strict_json_document

if TYPE_CHECKING:
    from psycopg import Cursor

    from .tenant_claim_write_guard import CheckedClaimResult
    from .tenant_uow import GovernedWriteBatch


@dataclass(frozen=True, slots=True)
class _GateReferences:
    """Values to compare with the wire trace, never a gate verdict or an admission."""

    request_binding: str
    classification_proof: str
    normalization_outcome: str
    authorization_result: str
    authorization_trace: str
    selected_rule_binding: str
    applicability_decision: str
    profile_context: str
    applicability_outcome: str
    sufficiency_basis: str
    sufficiency_case: str | None
    sufficiency_outcome: str


def _check_gate_references(trace: dict, refs: _GateReferences, claim: CheckedClaimResult) -> None:
    """Check where owner dispositions and references appear in the pending trace."""
    if trace.get("authorizationDecisionResultRef") != refs.authorization_result:
        raise ValueError("promotion trace names a different authorization result")

    sufficiency_refs = {refs.sufficiency_basis}
    if refs.sufficiency_case is None:
        if refs.sufficiency_outcome != "NOT_APPLICABLE" or "evidenceSufficiencyCaseRef" in trace:
            raise ValueError("promotion trace differs from its sufficiency exemption")
    else:
        if (
            refs.sufficiency_outcome not in {"ALLOW", "REQUIRE_REVIEW"}
            or trace.get("evidenceSufficiencyCaseRef") != refs.sufficiency_case
        ):
            raise ValueError("promotion trace names a different sufficiency case")
        sufficiency_refs.add(refs.sufficiency_case)

    normalization = {refs.request_binding, refs.classification_proof}
    authority = {refs.authorization_result, refs.authorization_trace, refs.selected_rule_binding}
    if len(normalization) != 2 or len(authority) != 3:
        raise ValueError("distinct promotion sources have the same reference")
    expected = (
        ("INGRESS_NORMALIZATION", refs.normalization_outcome, normalization),
        ("AUTHORITY", "ALLOW", authority),
        ("VALIDATION", "PASS", {claim.validation_trace_ref}),
        ("PACK_PROFILE_APPLICABILITY", refs.applicability_outcome, {refs.applicability_decision, refs.profile_context}),
        ("EVIDENCE_SUFFICIENCY", refs.sufficiency_outcome, sufficiency_refs),
        ("REVIEW_PROMOTION", "REQUIRE_REVIEW", {claim.assertion_id}),
    )
    for entry, (gate, outcome, bindings) in zip(trace["gateSequence"], expected, strict=True):
        actual = entry.get("relatedArtifactRefs", [])
        if (
            entry["gate"] != gate or entry["outcome"] != outcome
            or len(actual) != len(bindings) or set(actual) != bindings
        ):
            raise ValueError(f"promotion trace differs from the evidence at {gate}")


def _readback_pending_claim_promotion(
    cursor: Cursor,
    *,
    batch: GovernedWriteBatch,
    claim: CheckedClaimResult,
    authorized_assertion_id: str,
    assertion_jcs: bytes,
    trace_id: str,
    expected_trace_bytes: bytes,
    request_bytes: bytes,
    envelope_bytes: bytes,
    request_bytes_sha256: str,
    envelope_bytes_sha256: str,
    admitted_idempotency_key: str,
    classified_family: str,
    gate_references: _GateReferences,
) -> tuple[str, str]:
    """Compare sources and stored rows on the original lease, without issuing a write.

    The guarded producer must independently verify the original attempt, classified
    event, rule and all gate decisions before using this readback. Equality alone
    cannot establish that any of those sources authorized a promotion.
    """
    event_id = verify_original_ingress_sources(
        request_bytes, envelope_bytes,
        request_bytes_sha256=request_bytes_sha256,
        envelope_bytes_sha256=envelope_bytes_sha256,
        batch_request_id=batch.request_id,
        admitted_idempotency_key=admitted_idempotency_key,
        classified_family=classified_family,
    )
    trace, canonical = strict_json_document(expected_trace_bytes, "pending claim promotion trace")
    validate_document("ofarm.promotiontrace.v0.1", trace)
    if (
        trace["promotionTraceId"] != trace_id or trace["requestId"] != batch.request_id
        or trace["semanticEventRef"] != event_id or trace["primaryEventFamily"] != classified_family
        or trace["idempotencyKey"] != admitted_idempotency_key or trace["commitClass"] != "OPERATION_CLAIM"
        or trace["idempotencyDisposition"] != "NEW_REQUEST" or trace["finalOutcome"] != "REQUIRE_REVIEW"
        or trace.get("emittedAssertionRecordRefs") != [authorized_assertion_id]
        or claim.assertion_id != authorized_assertion_id
    ):
        raise ValueError("trace differs from the pending submission")
    if trace.keys() & {
        "replayOfRequestId", "inForceResultCategory", "materializationResultRef",
        "emittedReviewDecisionRefs", "emittedAcceptedConsequenceRefs",
    }:
        raise ValueError("trace contains effects outside pending review")
    _check_gate_references(trace, gate_references, claim)
    return _read_stored_promotion(
        cursor, batch=batch, claim=claim, authorized_assertion_id=authorized_assertion_id,
        assertion_jcs=assertion_jcs, trace_id=trace_id, expected_trace_bytes=canonical,
    )
