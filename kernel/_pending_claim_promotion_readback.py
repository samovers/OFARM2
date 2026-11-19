"""Compare staged promotion rows with the producer's independently checked inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._pending_claim_schemas import PROMOTION_TRACE_SCHEMA_DIGEST
from .runtime_bundle import canonical_json_bytes, sha256_bytes

if TYPE_CHECKING:
    from psycopg import Cursor

    from .tenant_claim_write_guard import CheckedClaimResult
    from .tenant_uow import GovernedWriteBatch


# Read every trace in this batch and every edge leaving it. Filtering to the
# expected trace or destination here could hide a second, unexpected output.
# A deferred check also allows edges from non-trace sources until finalization.
_STORED_PROMOTION = """
    SELECT trace.record_id, trace.payload_digest, trace.payload,
           trace.schema_digest, trace.lane, trace.runtime_bundle_digest,
           trace.batch_full_xid::pg_catalog.text,
           edge.edge_kind, edge.dst_record_id, edge.batch_id,
           edge.batch_full_xid::pg_catalog.text
      FROM ofarm.governed_write_batch AS batch
      JOIN ofarm.kernel_record AS claim
        ON claim.tenant_id = batch.tenant_id AND claim.batch_id = batch.batch_id
       AND claim.batch_full_xid = batch.full_xid
       AND claim.runtime_bundle_digest = batch.runtime_bundle_digest
      JOIN ofarm.kernel_record AS trace
        ON trace.tenant_id = batch.tenant_id AND trace.batch_id = batch.batch_id
       AND trace.record_kind = 'ofarm.promotiontrace.v0.1'
      LEFT JOIN ofarm.kernel_edge AS edge
        ON edge.tenant_id = trace.tenant_id AND edge.src_record_id = trace.record_id
     WHERE batch.tenant_id = ofarm.current_tenant_id()
       AND batch.tenant_id = %(tenant)s AND batch.batch_id = %(batch)s
       AND batch.full_xid = pg_catalog.pg_current_xact_id()
       AND batch.full_xid = %(xid)s::pg_catalog.xid8
       AND batch.runtime_bundle_digest = %(bundle)s
       AND batch.request_id = %(request)s
       AND batch.authenticated_principal_ref = ofarm.current_authenticated_principal_ref()
       AND batch.authenticated_principal_ref = %(principal)s
       AND batch.governed_operation = 'ASSERT_OPERATION_CLAIM'
       AND NOT EXISTS (
           SELECT 1 FROM ofarm.kernel_edge AS unexpected
            WHERE unexpected.tenant_id = batch.tenant_id AND unexpected.batch_id = batch.batch_id
              AND unexpected.edge_kind = 'PROMOTION_EMITS' AND unexpected.src_record_id <> %(trace_id)s
       )
       AND claim.record_id = %(assertion)s
       AND claim.record_kind = 'ofarm.assertionrecord.v0.2'
       AND claim.lane = 'canonical' AND claim.schema_digest = %(schema)s
       AND claim.payload_digest = %(assertion_digest)s
       AND claim.payload ->> 'schemaVersion' = claim.record_kind
       AND claim.payload -> 'assertionRecordId' = pg_catalog.to_jsonb(claim.record_id::pg_catalog.text)
       AND claim.payload ->> 'assertionType' = 'OPERATION_CLAIM_ASSERTION'
       AND claim.payload ->> 'claimState' = 'PENDING_REVIEW'
       AND claim.payload = pg_catalog.convert_from(%(assertion_bytes)s, 'UTF8')::pg_catalog.jsonb
     LIMIT 2
"""


def _read_stored_promotion(
    cursor: Cursor,
    *,
    batch: GovernedWriteBatch,
    claim: CheckedClaimResult,
    authorized_assertion_id: str,
    assertion_jcs: bytes,
    trace_id: str,
    expected_trace_bytes: bytes,
) -> tuple[str, str]:
    """Read on the original transaction. The domain owner supplies the verified JCS bytes."""
    if (
        authorized_assertion_id != claim.assertion_id
        or sha256_bytes(assertion_jcs) != claim.assertion_digest
        or claim.command.result_schema != "ofarm.assertionrecord.v0.2"
        or claim.command.action != "ASSERT_OPERATION_CLAIM"
        or claim.command.contract_id != "ofarm.protectedeffect.assertionrecord.submit.v0.1"
        or claim.command.contract_version != "0.1"
        or batch.operation != claim.command.action
        or batch.tenant_id != claim.command.tenant_id
        or batch.runtime_bundle_digest != claim.command.bundle_digest
    ):
        raise ValueError("pending assertion differs from the expected binding")
    xid = str(batch.full_xid)
    rows = cursor.execute(_STORED_PROMOTION, {
        "tenant": batch.tenant_id, "batch": batch.batch_id, "xid": xid,
        "request": batch.request_id, "principal": batch.authenticated_principal_ref,
        "bundle": batch.runtime_bundle_digest, "assertion": authorized_assertion_id,
        "schema": claim.command.result_schema_digest, "assertion_digest": claim.assertion_digest,
        "assertion_bytes": assertion_jcs, "trace_id": trace_id,
    }).fetchall()
    if len(rows) != 1:
        raise ValueError("expected exactly one stored promotion and edge")
    stored_id, stored_digest, payload, *metadata = rows[0]
    if (
        stored_id != trace_id
        or stored_digest != sha256_bytes(expected_trace_bytes)
        or metadata != [
            PROMOTION_TRACE_SCHEMA_DIGEST, "canonical", batch.runtime_bundle_digest, xid,
            "PROMOTION_EMITS", authorized_assertion_id, batch.batch_id, xid,
        ]
        or type(payload) is not dict
        or payload.get("schemaVersion") != "ofarm.promotiontrace.v0.1"
        or payload.get("promotionTraceId") != trace_id
        or payload.get("requestId") != batch.request_id
        or payload.get("emittedAssertionRecordRefs") != [authorized_assertion_id]
        or canonical_json_bytes(payload) != expected_trace_bytes
    ):
        raise ValueError("stored promotion differs from its checked trace or edge")
    return stored_id, stored_digest
