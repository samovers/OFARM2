"""Commit Ingress storage on the #436 lease. Production source composition belongs to #178."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from ._pending_claim_ingress_sources import verify_original_ingress_sources
from ._pending_claim_promotion_readback import _MATCHED_CLAIM, _claim_parameters
from ._pending_claim_promotion_trace import _GateReferences, _pending_gates, _readback_pending_claim_promotion
from ._pending_claim_schemas import PROMOTION_TRACE_SCHEMA_DIGEST, validate_document
from .runtime_bundle import canonical_json_bytes, sha256_bytes

if TYPE_CHECKING:
    from psycopg import Connection

    from .tenant_claim_write_guard import CheckedClaimResult
    from .tenant_promotion_guard import PromotionInputs
    from .tenant_uow import GovernedWriteBatch


@dataclass(frozen=True, slots=True)
class _PromotionSources:
    """Independent owner's bindings for one admitted NEW_REQUEST on this lease.

    The fixed resolver must establish the request's actor, scope and intent,
    the governed event and its classification, selected rule and consumable
    authorization, gate eligibility and the checked domain result. It refuses
    a missing or foreign source. Only the isolated test composes a resolver.
    """

    checked_claim: CheckedClaimResult
    assertion_jcs: bytes
    request_bytes_sha256: str
    envelope_bytes: bytes
    envelope_bytes_sha256: str
    admitted_idempotency_key: str
    classified_family: str
    gate_references: _GateReferences


_INSERT_PROMOTION = f"""
    WITH staged AS ({_MATCHED_CLAIM}),
    trace AS (
        INSERT INTO ofarm.kernel_record (
            tenant_id, batch_id, runtime_bundle_digest, record_id, record_kind, lane,
            schema_digest, payload, payload_digest
        )
        SELECT tenant_id, batch_id, runtime_bundle_digest, %(trace_id)s, 'ofarm.promotiontrace.v0.1',
               'canonical', %(trace_schema)s, pg_catalog.convert_from(%(trace_bytes)s, 'UTF8')::pg_catalog.jsonb,
               %(trace_digest)s
          FROM staged
        RETURNING tenant_id, batch_id, record_id
    )
    INSERT INTO ofarm.kernel_edge (tenant_id, batch_id, edge_kind, src_record_id, dst_record_id)
    SELECT trace.tenant_id, trace.batch_id, 'PROMOTION_EMITS', trace.record_id, staged.record_id
      FROM trace JOIN staged USING (tenant_id, batch_id)
    RETURNING src_record_id, dst_record_id
"""


class _PendingClaimPromotion:
    def __init__(
        self, connection: Connection, resolve_sources: Callable[[GovernedWriteBatch], _PromotionSources],
    ) -> None:
        self._connection = connection
        self._resolve_sources = resolve_sources

    def stage_and_verify_promotion(
        self, inputs: PromotionInputs, claim: CheckedClaimResult, batch: GovernedWriteBatch,
    ) -> tuple[str, str]:
        sources = self._resolve_sources(batch)
        if sources.checked_claim != claim:
            raise ValueError("promotion sources differ from the staged claim or its validation bindings")
        assertion_id = sources.checked_claim.assertion_id
        params = _claim_parameters(batch, claim, assertion_id, sources.assertion_jcs)
        original = {
            "request_bytes": inputs.evidence_bytes,
            "envelope_bytes": sources.envelope_bytes,
            "request_bytes_sha256": sources.request_bytes_sha256,
            "envelope_bytes_sha256": sources.envelope_bytes_sha256,
            "admitted_idempotency_key": sources.admitted_idempotency_key,
            "classified_family": sources.classified_family,
        }
        event_id = verify_original_ingress_sources(batch_request_id=batch.request_id, **original)
        refs = sources.gate_references
        trace_id = f"promtrace:{uuid4()}"
        trace = {
            "schemaVersion": "ofarm.promotiontrace.v0.1", "promotionTraceId": trace_id,
            "requestId": batch.request_id, "evaluatedAt": datetime.now(UTC).isoformat(),
            "semanticEventRef": event_id, "primaryEventFamily": sources.classified_family,
            "commitClass": "OPERATION_CLAIM", "idempotencyKey": sources.admitted_idempotency_key,
            "idempotencyDisposition": "NEW_REQUEST", "finalOutcome": "REQUIRE_REVIEW",
            "traceSummary": "The submitted operation claim requires review.",
            "authorizationDecisionResultRef": refs.authorization_result,
            "emittedAssertionRecordRefs": [assertion_id],
            "gateSequence": [
                {"gate": gate, "outcome": outcome, "relatedArtifactRefs": list(bindings)}
                for gate, outcome, bindings in _pending_gates(refs, claim)
            ],
        }
        if refs.sufficiency_case is not None:
            trace["evidenceSufficiencyCaseRef"] = refs.sufficiency_case
        validate_document("ofarm.promotiontrace.v0.1", trace)
        trace_bytes = canonical_json_bytes(trace)
        with self._connection.cursor() as cursor:
            edge = cursor.execute(_INSERT_PROMOTION, {
                **params, "trace_id": trace_id, "trace_schema": PROMOTION_TRACE_SCHEMA_DIGEST,
                "trace_bytes": trace_bytes, "trace_digest": sha256_bytes(trace_bytes),
            }).fetchone()
            if edge != (trace_id, assertion_id):
                raise ValueError("promotion did not link its staged pending claim")
            return _readback_pending_claim_promotion(
                cursor, batch=batch, claim=claim, authorized_assertion_id=assertion_id,
                assertion_jcs=sources.assertion_jcs, trace_id=trace_id, expected_trace_bytes=trace_bytes,
                gate_references=refs, **original,
            )
