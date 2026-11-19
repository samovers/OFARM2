"""Real claim, trace and edge rows under the signed tenant manager.

The fixture owns the claim operation and independently selected source facts.
Commit Ingress runs its real producer through the production promotion guard.
"""
from contextlib import nullcontext
from dataclasses import replace
from hashlib import sha256
import json

import psycopg
import pytest
from psycopg.pq import TransactionStatus

from kernel import _pending_claim_promotion as promotion
from kernel import _pending_claim_promotion_trace as trace_checks
from kernel._pending_claim_schemas import PROMOTION_TRACE_SCHEMA_DIGEST, validate_document
from kernel.runtime_bundle import canonical_json_bytes, sha256_bytes
from kernel.tenant_claim_write_guard import CheckedClaimResult, ClaimWriteAttempt
from kernel.tenant_promotion_guard import PromotionInputs
from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome, TenantUnitOfWorkManager
from kernel.tests._physical_outcome_support import physical_harness, request
from kernel.tests.postgresql_tenant_support import tenant_target as tenant_target
from kernel.tests.test_pending_claim_promotion_readback import _edge, _record
from kernel.tests.test_pending_claim_promotion_trace import _trace_fixture
from kernel.tests.test_physical_outcome_runtime import role as role
from kernel.tests.test_postgresql_tenant_claim_write_guard import _command
from kernel.tests.test_postgresql_tenant_migration import authority as authority, capability_key as capability_key
from kernel.tests.test_tenant_transaction_failure_runtime import calls as calls


_CLAIM = "ofarm.assertionrecord.v0.2"
_TRACE = "ofarm.promotiontrace.v0.1"
_EVENT = "ofarm.semanticeventenvelope.v0.1"
_EVENT_SCHEMA = "sha256:75662a6c4952a62b7e8f8e9de99c23c98899c692914a98ba4b752873f48bd1a4"
# Draft assertion schema pinned by #422 for its isolated writer tests.
_CLAIM_SCHEMA = "sha256:3a7044086a2b0a226109ac00b361332503d77b07efd602b29402662515b67f1e"


def _assertion(authority, claim_id):
    window = {"profile": "INTENDED_WINDOW", "start": "2000-01-02T10:00:00Z", "end": "2000-01-02T11:00:00Z"}
    return {
        "schemaVersion": _CLAIM, "assertionRecordId": claim_id, "assertionType": "OPERATION_CLAIM_ASSERTION",
        "subject": {"subjectType": "FIELD", "subjectRef": "field:test", "subjectPosture": "EXISTING_SUBJECT",
                    "revisionRef": "field:test:r1"},
        "anchorScopes": [{"scopeType": "FIELD", "scopeRef": "field:test", "revisionRef": "field:test:r1"}],
        "assertedByPartyRef": authority.party_ref, "assertedAt": "2000-01-01T12:10:00Z",
        "assertionActPosture": "TRUSTED_ONLINE_SUBMISSION", "subjectTime": window,
        "assertionBody": {"assertionPosture": "INITIAL", "claimText": "A fictional operation is planned.",
                          "allegesSoftwareAgentPerformance": False, "temporalBasis": {"sourceKind": "BODY_TIME", "time": window}},
        "evidenceBindings": [{"ref": "evidence:fixture", "revisionRef": "evidence:fixture:r1"}],
        "operationClaimContext": {"claimPosture": "INTENDED", "performedByPartyRef": authority.party_ref},
        "claimState": "PENDING_REVIEW",
    }


class _FixtureClaim:
    """Supply #422's checked return from the real assertion row on this lease."""

    def __init__(self, manager, connection):
        self.manager = manager
        self.connection = connection

    def selected_claim_command(self):
        return self.manager.sources.checked_claim.command

    def stage_and_verify_operation_claim(self, attempt):
        result = self.manager.sources.checked_claim
        assert attempt.intent_bytes == self.manager.sources.assertion_jcs
        with self.connection.cursor() as cursor:
            _record(cursor, self.manager.batch, result.assertion_id, _CLAIM, result.command.result_schema_digest,
                    json.loads(attempt.intent_bytes), result.assertion_digest)
            row = cursor.execute(
                """SELECT record_id, payload, payload_digest, batch_full_xid::text
                     FROM ofarm.kernel_record WHERE batch_id = %s AND record_kind = %s""",
                (attempt.batch_id, _CLAIM),
            ).fetchone()
        assert row == (result.assertion_id, json.loads(attempt.intent_bytes), result.assertion_digest, str(attempt.full_xid))
        return result


def _check_committed_event(connection, manager):
    rows = connection.execute(
        """SELECT event.payload, event.payload_digest, event.schema_digest, edge.src_record_id
             FROM ofarm.kernel_record event JOIN ofarm.kernel_edge edge
               ON edge.tenant_id = event.tenant_id AND edge.dst_record_id = event.record_id
              AND edge.batch_id = event.batch_id AND edge.batch_full_xid = event.batch_full_xid
            WHERE event.record_kind = %s AND event.record_id = %s AND edge.edge_kind = 'PROMOTION_EMITS'""",
        (_EVENT, manager.event["semanticEventId"]),
    ).fetchall()
    assert rows == [(manager.event, sha256_bytes(canonical_json_bytes(manager.event)), _EVENT_SCHEMA, manager.source_trace)]
    return rows[0][0]


class _FixtureManager(TenantUnitOfWorkManager):
    def _bind_claim_operation(self, connection, binding):
        return _FixtureClaim(self, connection)

    def _bind_promotion_operation(self, connection, binding):
        def resolve_sources(batch):
            assert (binding.tenant_id, binding.party_ref, self.authored.request_id) == (
                batch.tenant_id, batch.authenticated_principal_ref, batch.request_id,
            )
            stored = _check_committed_event(connection, self)
            original = self.sources.envelope_bytes
            if (original != self.admitted_envelope_bytes
                    or sha256(original).hexdigest() != self.sources.envelope_bytes_sha256
                    or canonical_json_bytes(json.loads(original)) != canonical_json_bytes(stored)):
                raise ValueError("fixture Event Ingress binding differs from the governed original")
            return self.sources
        return promotion._PendingClaimPromotion(connection, resolve_sources)


@pytest.fixture
def harness(tenant_target, authority, capability_key, tmp_path, role):
    with physical_harness(tenant_target, authority, capability_key, tmp_path, role, manager_type=_FixtureManager) as value:
        manager = value.manager
        manager.authored = replace(request(authority, "claim"), operation="ASSERT_OPERATION_CLAIM")
        request_id = manager.authored.request_id
        assertion_id = "claim:" + request_id
        assertion_jcs = canonical_json_bytes(_assertion(authority, assertion_id))
        selected = replace(_command(authority.tenant_id, authority.runtime_bundle_digest), result_schema_digest=_CLAIM_SCHEMA)
        checked = CheckedClaimResult(
            selected, assertion_id, sha256_bytes(assertion_jcs),
            "validation:" + request_id, sha256_bytes(b"fixture validation"),
            "domain:" + request_id, sha256_bytes(b"fixture domain payload"),
        )
        _, originals = _trace_fixture(request_id, assertion_id, checked.validation_trace_ref, "unused")
        manager.event = json.loads(originals["envelope_bytes"])
        event_id = "event:" + request_id
        manager.event.update(semanticEventId=event_id, subjectRefs=["field:test"])
        manager.source_trace = "event-origin:" + request_id
        ingress = json.loads(originals["request_bytes"])
        ingress.update(actingPartyRef=authority.party_ref, semanticEventRef=event_id, idempotencyKey="key:" + request_id)
        manager.request_bytes = json.dumps(ingress, indent=2).encode()
        envelope_bytes = manager.admitted_envelope_bytes = json.dumps(manager.event, indent=2).encode()
        manager.sources = promotion._PromotionSources(
            checked_claim=checked, assertion_jcs=assertion_jcs, envelope_bytes=envelope_bytes,
            request_bytes_sha256=sha256(manager.request_bytes).hexdigest(),
            envelope_bytes_sha256=sha256(envelope_bytes).hexdigest(),
            admitted_idempotency_key=ingress["idempotencyKey"], classified_family=manager.event["primaryEventFamily"],
            gate_references=originals["gate_references"],
        )
        # This distinct, committed event and its original edge are also the observer's visibility control.
        with value.runtime.tenant_unit_of_work(value.principal) as seed:
            batch = seed.begin_batch(request(authority, "earlier-event"))
            trace = {
                "schemaVersion": _TRACE, "promotionTraceId": manager.source_trace, "requestId": batch.request_id,
                "semanticEventRef": event_id, "evaluatedAt": "2000-01-01T12:09:00Z", "commitClass": "NOTE",
                "primaryEventFamily": manager.event["primaryEventFamily"], "idempotencyKey": "key:" + batch.request_id,
                "idempotencyDisposition": "NEW_REQUEST", "gateSequence": [{"gate": "REVIEW_PROMOTION", "outcome": "ALLOW"}],
                "finalOutcome": "PROMOTE_ACCEPTED", "traceSummary": "Fictional prior event.",
            }
            validate_document(_TRACE, trace)
            with value.pool.acquired[-1].cursor() as cursor:
                _record(cursor, batch, event_id, _EVENT, _EVENT_SCHEMA, manager.event, sha256_bytes(canonical_json_bytes(manager.event)))
                _record(cursor, batch, manager.source_trace, _TRACE, PROMOTION_TRACE_SCHEMA_DIGEST,
                        trace, sha256_bytes(canonical_json_bytes(trace)))
                _edge(cursor, batch, "PROMOTION_EMITS", manager.source_trace, event_id)
        yield value


def _stage(unit, harness):
    manager = harness.manager
    batch = manager.batch = unit.begin_batch(manager.authored)
    claim = manager.sources.checked_claim
    attempt = ClaimWriteAttempt(claim.command, unit.binding.capability_nonce, batch.batch_id, batch.full_xid,
                                manager.sources.assertion_jcs)
    assert unit.stage_operation_claim(attempt) == claim
    return PromotionInputs(batch.tenant_id, batch.authenticated_principal_ref, attempt.binding_nonce,
                           batch.batch_id, batch.full_xid, batch.request_id, claim.command, manager.request_bytes)


def _check_batch(connection, manager, *, claim_visible, trace_binding):
    batch = manager.batch
    claim = manager.sources.checked_claim
    header = connection.execute(
        "SELECT full_xid::text, tenant_id, authenticated_principal_ref FROM ofarm.governed_write_batch WHERE batch_id = %s",
        (batch.batch_id,),
    ).fetchall()
    assert header == ([(str(batch.full_xid), batch.tenant_id, batch.authenticated_principal_ref)] if claim_visible else [])
    records = connection.execute(
        """SELECT record_kind, record_id, payload_digest, batch_full_xid::text, payload
             FROM ofarm.kernel_record WHERE batch_id = %s ORDER BY record_kind""", (batch.batch_id,),
    ).fetchall()
    expected = [(_CLAIM, claim.assertion_id, claim.assertion_digest)] if claim_visible else []
    edges = []
    if trace_binding is not None:
        trace_id, digest = trace_binding
        expected.append((_TRACE, trace_id, digest))
        edges = [("PROMOTION_EMITS", trace_id, claim.assertion_id, str(batch.full_xid))]
    assert [row[:3] for row in records] == expected
    for _, _, digest, xid, payload in records:
        assert xid == str(batch.full_xid) and digest == sha256_bytes(canonical_json_bytes(payload))
    if trace_binding is not None:
        trace = records[-1][-1]
        assert trace["semanticEventRef"] == manager.event["semanticEventId"]
        assert trace["emittedAssertionRecordRefs"] == [claim.assertion_id]
        assert trace["authorizationDecisionResultRef"] == manager.sources.gate_references.authorization_result
        assert trace["requestId"] == batch.request_id and trace["finalOutcome"] == "REQUIRE_REVIEW"
    assert connection.execute(
        """SELECT edge_kind, src_record_id, dst_record_id, batch_full_xid::text
             FROM ofarm.kernel_edge WHERE batch_id = %s""", (batch.batch_id,),
    ).fetchall() == edges


@pytest.fixture
def observe(harness, tenant_target, role):
    def check(claim_visible=False, trace_binding=None):
        with psycopg.connect(tenant_target.role_dsn(role)) as reader:
            binding = harness.manager._bind(reader, harness.principal)
            assert reader.info.backend_pid != harness.pool.acquired[-1].info.backend_pid
            assert reader.execute("SELECT session_user, ofarm.current_tenant_id()").fetchone() == (role, binding.tenant_id)
            assert binding.tenant_id == harness.manager.batch.tenant_id
            _check_committed_event(reader, harness.manager)
            _check_batch(reader, harness.manager, claim_visible=claim_visible, trace_binding=trace_binding)
            reader.rollback()
    return check


@pytest.mark.parametrize("rollback", [False, True], ids=["commit", "outer-rollback"])
def test_checked_producer_return_is_provisional(harness, observe, calls, rollback):
    completion = pytest.raises(ValueError, match="fixture outer rollback") if rollback else nullcontext()
    with completion:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            inputs = _stage(unit, harness)
            result = unit.promote_pending_claim(inputs)
            _check_batch(harness.pool.acquired[-1], harness.manager, claim_visible=True, trace_binding=result)
            observe()
            if rollback:
                raise ValueError("fixture outer rollback")
    assert len(calls["commit"]) == int(not rollback)
    observe(claim_visible=not rollback, trace_binding=None if rollback else result)


@pytest.mark.parametrize("failure", ["missing-classification", "python-readback", "sql-readback", "sql-savepoint"])
def test_caught_producer_refusal_rolls_back_real_graph(harness, role, observe, calls, monkeypatch, failure):
    manager = harness.manager
    sql_failure = failure.startswith("sql-")
    expected = {
        "missing-classification": ValueError, "python-readback": RuntimeError,
        "sql-readback": psycopg.errors.DivisionByZero, "sql-savepoint": psycopg.errors.DivisionByZero,
    }[failure]
    injected = RuntimeError("fixture readback interrupted")
    observed_proofs = []

    read_stored = trace_checks._read_stored_promotion

    def interrupt_readback(cursor, *, batch, trace_id, expected_trace_bytes, **kwargs):
        writer = harness.pool.acquired[-1]
        assert cursor.connection is writer
        assert cursor.execute("SELECT session_user, pg_current_xact_id()::text, pg_backend_pid()").fetchone() == (
            role, str(batch.full_xid), writer.info.backend_pid,
        )
        proof = (trace_id, sha256_bytes(expected_trace_bytes))
        assert read_stored(cursor, batch=batch, trace_id=trace_id, expected_trace_bytes=expected_trace_bytes, **kwargs) == proof
        assert writer.info.transaction_status is TransactionStatus.INTRANS
        _check_batch(writer, manager, claim_visible=True, trace_binding=proof)
        observed_proofs.append(proof)
        observe()
        if sql_failure:
            cursor.execute("SELECT 1 / 0")
        raise injected

    if failure == "missing-classification":
        manager.sources = replace(manager.sources, classified_family=None)
    else:
        monkeypatch.setattr(trace_checks, "_read_stored_promotion", interrupt_readback)

    with pytest.raises(TenantBoundaryError) as final:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            inputs = _stage(unit, harness)
            writer = harness.pool.acquired[-1]
            if failure == "sql-savepoint":
                writer.execute("SAVEPOINT before_promotion")
            with pytest.raises(expected) as error:
                unit.promote_pending_claim(inputs)
            if failure == "python-readback":
                assert error.value is injected
            assert len(observed_proofs) == int(failure != "missing-classification")
            assert writer.info.transaction_status is (TransactionStatus.INERROR if sql_failure else TransactionStatus.INTRANS)
            if failure == "sql-savepoint":
                writer.execute("ROLLBACK TO SAVEPOINT before_promotion")
                writer.execute("RELEASE SAVEPOINT before_promotion")
                assert writer.info.transaction_status is TransactionStatus.INTRANS
            if writer.info.transaction_status is TransactionStatus.INTRANS:
                proof = observed_proofs[0] if failure == "python-readback" else None
                _check_batch(writer, manager, claim_visible=True, trace_binding=proof)
            observe()
    assert final.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert calls["commit"] == [] and len(calls["rollback"]) == 1
    observe()


@pytest.mark.parametrize("changed", [
    "validation_trace_digest", "domain_payload_ref", "domain_payload_digest", "request-actor",
])
def test_different_checked_sources_refuse_before_proof_inserts(harness, calls, observe, changed):
    manager = harness.manager
    with pytest.raises(TenantBoundaryError) as final:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            inputs = _stage(unit, harness)
            if changed == "request-actor":
                substituted = json.loads(inputs.evidence_bytes)
                substituted["actingPartyRef"] = "party:other"
                inputs = replace(inputs, evidence_bytes=json.dumps(substituted, indent=2).encode())
            else:
                value = "domain:other" if changed == "domain_payload_ref" else sha256_bytes(b"other")
                expected = replace(manager.sources.checked_claim, **{changed: value})
                manager.sources = replace(manager.sources, checked_claim=expected)
            with pytest.raises(ValueError):
                unit.promote_pending_claim(inputs)
            writer = harness.pool.acquired[-1]
            assert writer.info.transaction_status is TransactionStatus.INTRANS
            _check_batch(writer, manager, claim_visible=True, trace_binding=None)
    assert final.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert calls["commit"] == [] and len(calls["rollback"]) == 1
    observe()


def test_edge_insert_conflict_rolls_back_staged_claim(harness, calls, observe):
    manager = harness.manager
    with pytest.raises(TenantBoundaryError) as final:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            inputs = _stage(unit, harness)
            writer = harness.pool.acquired[-1]
            with writer.cursor() as cursor:
                _edge(cursor, manager.batch, "PROMOTION_EMITS", manager.source_trace, manager.sources.checked_claim.assertion_id)
            with pytest.raises(psycopg.errors.UniqueViolation) as refused:
                unit.promote_pending_claim(inputs)
            assert refused.value.diag.constraint_name == "kernel_edge_promotion_destination_key"
            observe()
    assert final.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert calls["commit"] == [] and len(calls["rollback"]) == 1
    observe()


def test_second_promotion_call_rolls_back_first_checked_graph(harness, calls, observe):
    with pytest.raises(TenantBoundaryError) as final:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            inputs = _stage(unit, harness)
            checked = unit.promote_pending_claim(inputs)
            with pytest.raises(RuntimeError):
                unit.promote_pending_claim(inputs)
            _check_batch(harness.pool.acquired[-1], harness.manager, claim_visible=True, trace_binding=checked)
            observe()
    assert final.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert calls["commit"] == [] and len(calls["rollback"]) == 1
    observe()


def test_caught_real_readback_refusal_rolls_back_batch(harness, calls, observe):
    manager = harness.manager
    with pytest.raises(TenantBoundaryError) as final:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            inputs = _stage(unit, harness)
            writer = harness.pool.acquired[-1]
            claim = manager.sources.checked_claim
            extra_id = "extra:" + inputs.request_id
            extra, _ = _trace_fixture(inputs.request_id, claim.assertion_id, claim.validation_trace_ref, extra_id)
            with writer.cursor() as cursor:
                _record(cursor, manager.batch, extra_id, _TRACE, PROMOTION_TRACE_SCHEMA_DIGEST,
                        extra, sha256_bytes(canonical_json_bytes(extra)))
            with pytest.raises(ValueError, match="expected exactly one stored promotion and edge"):
                unit.promote_pending_claim(inputs)
            assert writer.info.transaction_status is TransactionStatus.INTRANS
            linked = writer.execute(
                """SELECT trace.record_id, edge.dst_record_id
                     FROM ofarm.kernel_record trace JOIN ofarm.kernel_edge edge
                       ON (edge.tenant_id, edge.batch_id, edge.src_record_id) =
                          (trace.tenant_id, trace.batch_id, trace.record_id)
                    WHERE trace.batch_id = %s AND trace.record_kind = %s AND edge.edge_kind = 'PROMOTION_EMITS'""",
                (inputs.batch_id, _TRACE),
            ).fetchall()
            assert len(linked) == 1
            assert linked[0][0] != extra_id and linked[0][1] == claim.assertion_id
            observe()
    assert final.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert calls["commit"] == [] and len(calls["rollback"]) == 1
    observe()
