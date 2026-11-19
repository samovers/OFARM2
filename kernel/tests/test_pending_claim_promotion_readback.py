"""Ordinary-role readback of fixture ledger rows, without a producer or domain verdict."""

from dataclasses import replace
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from kernel._pending_claim_promotion_trace import _readback_pending_claim_promotion
from kernel._pending_claim_schemas import PROMOTION_TRACE_SCHEMA_DIGEST
from kernel.runtime_bundle import canonical_json_bytes, sha256_bytes
from kernel.tenant_claim_write_guard import CheckedClaimResult, SelectedClaimCommand
from kernel.tests._physical_outcome_support import request
from kernel.tests.test_pending_claim_promotion_trace import _trace_fixture
from kernel.tests.test_physical_outcome_runtime import harness as harness, role as role
from kernel.tests.postgresql_tenant_support import tenant_target as tenant_target
from kernel.tests.test_postgresql_tenant_migration import authority as authority, capability_key as capability_key


class _RollBackFixture(Exception):
    pass


@pytest.fixture
def staged(harness, authority, tenant_target, role):
    """Keep every fixture graph provisional, including intentionally inconsistent rows."""
    with pytest.raises(_RollBackFixture):
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            batch = unit.begin_batch(replace(request(authority), operation="ASSERT_OPERATION_CLAIM"))
            connection = harness.pool.acquired[-1]
            with connection.cursor() as cursor:
                yield cursor, batch
            raise _RollBackFixture
    with psycopg.connect(tenant_target.role_dsn(role)) as observer:
        harness.manager._bind(observer, harness.principal)
        assert observer.execute(
            "SELECT record_id FROM ofarm.kernel_record WHERE record_id = %s", (authority.party_ref,),
        ).fetchall() == [(authority.party_ref,)]
        assert observer.execute(
            """SELECT (SELECT count(*) FROM ofarm.kernel_record WHERE batch_id = %s),
                      (SELECT count(*) FROM ofarm.kernel_edge WHERE batch_id = %s)""",
            (batch.batch_id, batch.batch_id),
        ).fetchone() == (0, 0)


def _record(cursor, batch, record_id, kind, schema, payload, digest, lane="canonical"):
    cursor.execute(
        """INSERT INTO ofarm.kernel_record (
            tenant_id, batch_id, runtime_bundle_digest, record_id, record_kind, lane,
            schema_digest, payload, payload_digest
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (batch.tenant_id, batch.batch_id, batch.runtime_bundle_digest, record_id,
         kind, lane, schema, Jsonb(payload), digest),
    )


def _edge(cursor, batch, edge_kind, source="fixture-trace", target="fixture-claim"):
    cursor.execute(
        """INSERT INTO ofarm.kernel_edge
               (tenant_id, batch_id, edge_kind, src_record_id, dst_record_id)
           VALUES (%s, %s, %s, %s, %s)""",
        (batch.tenant_id, batch.batch_id, edge_kind, source, target),
    )


@pytest.mark.parametrize("case", (
    "matching", "missing-edge", "extra-edge", "extra-trace", "stored-schema",
    "stored-lane", "wrong-state", "stored-claim-content", "wrong-emitted-ref",
    "stored-trace-content", "authorized-id", "wrong-xid", "foreign-tenant",
    "assertion-digest", "contract-id", "contract-version",
    "wrong-disposition", "different-family", "extra-effect", "second-promotion-edge",
))
def test_staged_graph_must_equal_the_expected_bindings(staged, case):
    cursor, batch = staged
    claim_id, trace_id = "fixture-claim", "fixture-trace"
    claim_kind, trace_kind = "ofarm.assertionrecord.v0.2", "ofarm.promotiontrace.v0.1"
    fixture_digest = sha256_bytes(b"readback fixture schema")
    command = SelectedClaimCommand(
        batch.tenant_id, batch.operation, batch.runtime_bundle_digest,
        "ofarm.protectedeffect.assertionrecord.submit.v0.1", "0.1", fixture_digest,
        claim_kind, fixture_digest,
    )
    # The ASCII-keyed, integer-only assertion projection has known JCS bytes.
    # Real assertion bytes and their domain validation come from #422.
    claim = {
        "assertionBody": {"quantity": 1}, "assertionRecordId": claim_id,
        "assertionType": "OPERATION_CLAIM_ASSERTION", "claimState": "PENDING_REVIEW",
        "schemaVersion": claim_kind,
    }
    assertion_bytes = canonical_json_bytes(claim)
    result = CheckedClaimResult(
        command, claim_id, sha256_bytes(assertion_bytes), "fixture-validation",
        fixture_digest, "fixture-domain-payload", fixture_digest,
    )
    trace, source_kwargs = _trace_fixture(batch.request_id, claim_id, result.validation_trace_ref, trace_id)
    if case == "wrong-emitted-ref":
        trace["emittedAssertionRecordRefs"] = [trace_id]
    if case == "wrong-disposition":
        trace["idempotencyDisposition"] = "NOT_EVALUATED"
    if case == "different-family":
        trace["primaryEventFamily"] = "EvidenceEvent"
    if case == "extra-effect":
        trace["emittedAcceptedConsequenceRefs"] = ["unexpected-consequence"]
    trace_bytes = canonical_json_bytes(trace)
    trace_digest = sha256_bytes(trace_bytes)
    if case == "wrong-state":
        claim["claimState"] = "ACCEPTED"
        assertion_bytes = canonical_json_bytes(claim)
        result = replace(result, assertion_digest=sha256_bytes(assertion_bytes))
    if case == "stored-claim-content":
        # Python object equality would mistake the boolean for the number.
        claim["assertionBody"] = {"quantity": True}
    if case == "stored-trace-content":
        trace["requestId"] = "different-request"
    _record(cursor, batch, claim_id, claim_kind, fixture_digest, claim, result.assertion_digest)
    _record(
        cursor, batch, trace_id, trace_kind,
        fixture_digest if case == "stored-schema" else PROMOTION_TRACE_SCHEMA_DIGEST,
        trace, trace_digest, lane="draft" if case == "stored-lane" else "canonical",
    )
    if case != "missing-edge":
        _edge(cursor, batch, "PROMOTION_EMITS")
    if case == "extra-edge":
        _edge(cursor, batch, "EVIDENCE")
    if case == "second-promotion-edge":
        source, target = "unrelated-source", "unrelated-target"
        for record_id in (source, target):
            payload = {"recordId": record_id}
            _record(cursor, batch, record_id, "ofarm.derivedtest.v0.1", fixture_digest,
                    payload, sha256_bytes(canonical_json_bytes(payload)))
        _edge(cursor, batch, "PROMOTION_EMITS", source, target)
    if case == "extra-trace":
        _record(cursor, batch, "unused-fixture-trace", trace_kind,
                PROMOTION_TRACE_SCHEMA_DIGEST, trace, trace_digest)
    if case == "wrong-xid":
        batch = replace(batch, full_xid=batch.full_xid + 1)
    if case == "foreign-tenant":
        batch = replace(batch, tenant_id=uuid4())
        result = replace(result, command=replace(command, tenant_id=batch.tenant_id))
    if case == "assertion-digest":
        result = replace(result, assertion_digest=fixture_digest)
    if case == "contract-id":
        result = replace(result, command=replace(command, contract_id="other-contract"))
    if case == "contract-version":
        result = replace(result, command=replace(command, contract_version="0.2"))
    args = {
        "batch": batch, "claim": result, "assertion_jcs": assertion_bytes,
        "authorized_assertion_id": "other" if case == "authorized-id" else claim_id,
        "trace_id": trace_id, "expected_trace_bytes": trace_bytes,
    }
    if case == "matching":
        assert _readback_pending_claim_promotion(cursor, **args, **source_kwargs) == (trace_id, trace_digest)
    else:
        with pytest.raises(ValueError):
            _readback_pending_claim_promotion(cursor, **args, **source_kwargs)
