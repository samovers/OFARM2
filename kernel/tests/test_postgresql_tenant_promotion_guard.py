"""Transaction-owner acceptance using signed ordinary tenants and disposable markers."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import replace
from uuid import uuid4

import psycopg
import pytest
from psycopg.pq import TransactionStatus

from kernel.runtime_bundle import sha256_bytes
from kernel.tenant_promotion_guard import PromotionInputs
from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome
from kernel.tests._physical_outcome_support import lose_commit_reply
from kernel.tests.test_postgresql_tenant_claim_write_guard import (
    MarkerManager, _attempt, authority as authority, calls as calls, capability_key as capability_key,
    harness as harness, marker_table as marker_table, role as role, tenant_target as tenant_target,
)


def _trace_id(batch):
    return ("trace-" + batch.batch_id).ljust(255, "x")


def _markers(batch, claim):
    return [claim.assertion_id, _trace_id(batch), "link-" + batch.batch_id]


def _check_rows(connection, batch, backend_pid, markers):
    """None means the batch and all its markers must be absent."""
    assert connection.execute(
        "SELECT batch_id, full_xid::text FROM ofarm.governed_write_batch WHERE batch_id = %s",
        (batch.batch_id,),
    ).fetchall() == ([] if markers is None else [(batch.batch_id, str(batch.full_xid))])
    stored = connection.execute(
        """SELECT marker_id, backend_pid, full_xid::text FROM claim_guard_fixture.marker
             WHERE batch_id = %s ORDER BY marker_id""",
        (batch.batch_id,),
    ).fetchall()
    assert stored == [(marker, backend_pid, str(batch.full_xid)) for marker in sorted(markers or [])]


@pytest.fixture
def observe(tenant_target, role, harness):
    def check(batch, markers):
        with psycopg.connect(tenant_target.role_dsn(role)) as reader:
            binding = harness.manager._bind(reader, harness.principal)
            assert binding.tenant_id == batch.tenant_id and binding.party_ref == batch.authenticated_principal_ref
            assert reader.execute("SELECT session_user").fetchone() == (role,)
            writer_pid = harness.manager.allocation[0]
            assert reader.info.backend_pid != writer_pid
            assert reader.execute(
                "SELECT marker_id FROM claim_guard_fixture.marker WHERE marker_id = 'visible-control'"
            ).fetchall() == [("visible-control",)]
            _check_rows(reader, batch, writer_pid, markers)
            reader.rollback()
    return check


class MarkerProducer:
    def __init__(self, manager, connection, binding):
        self.manager = manager
        self.connection = connection
        self.binding = binding

    def stage_and_verify_promotion(self, inputs, claim, batch):
        manager = self.manager
        manager.promotions.append(inputs)
        assert claim is manager.checked_claim
        assert batch is manager.original_batch
        assert inputs.binding_nonce == self.binding.capability_nonce
        row = self.connection.execute(
            """SELECT session_user, ofarm.current_tenant_id(), ofarm.current_authenticated_principal_ref(),
                      pg_backend_pid(), pg_current_xact_id()::text"""
        ).fetchone()
        assert row == (manager.role, batch.tenant_id, batch.authenticated_principal_ref, *manager.allocation)
        _check_rows(self.connection, batch, row[3], [claim.assertion_id])
        if manager.promotion_mode == "input-refusal":
            raise ValueError("fixture refused input")
        trace = _trace_id(batch)
        self.connection.execute(
            "INSERT INTO claim_guard_fixture.marker(marker_id, batch_id) VALUES (%s, %s), (%s, %s)",
            (trace, batch.batch_id, "link-" + batch.batch_id, batch.batch_id),
        )
        _check_rows(self.connection, batch, row[3], _markers(batch, claim))
        if manager.promotion_mode == "sql-error":
            self.connection.execute(
                "INSERT INTO claim_guard_fixture.marker(marker_id, batch_id) VALUES (%s, %s)",
                (trace, batch.batch_id),
            )
        if manager.promotion_mode == "reentry":
            manager.reenter()
        if manager.promotion_failure is not None:
            raise manager.promotion_failure
        if manager.promotion_mode == "bad-return":
            return manager.bad_return
        return trace, sha256_bytes(inputs.evidence_bytes)


class PromotionManager(MarkerManager):
    def _bind_promotion_operation(self, connection, binding):
        if self.promotion_enabled:
            return MarkerProducer(self, connection, binding)
        return super()._bind_promotion_operation(connection, binding)


@pytest.fixture
def marker_manager_type():
    return PromotionManager


@pytest.fixture(autouse=True)
def promotion_fixture(harness, role):
    manager = harness.manager
    manager.role = role
    manager.promotion_mode = "success"
    manager.promotion_failure = None
    manager.promotion_enabled = True
    manager.promotions = []


def _inputs(unit, attempt):
    batch = unit.batch
    return PromotionInputs(
        tenant_id=batch.tenant_id, principal_ref=batch.authenticated_principal_ref,
        binding_nonce=attempt.binding_nonce, batch_id=batch.batch_id, full_xid=batch.full_xid,
        request_id=batch.request_id, command=attempt.command, evidence_bytes=b"fixture evidence",
    )


def _stage(unit, harness, authority):
    manager = harness.manager
    attempt = _attempt(unit, authority)
    manager.original_batch = unit.batch
    manager.checked_claim = unit.stage_operation_claim(attempt)
    writer = harness.pool.acquired[-1]
    assert writer.info.backend_pid == manager.allocation[0]
    assert writer.execute("SELECT session_user, ofarm.current_tenant_id()").fetchone() == (
        manager.role, unit.batch.tenant_id,
    )
    _check_rows(writer, unit.batch, writer.info.backend_pid, [manager.checked_claim.assertion_id])
    return _inputs(unit, attempt)


def _assert_failed(failure, calls, observe, batch):
    assert failure.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert calls["commit"] == [] and len(calls["rollback"]) == 1
    observe(batch, None)


@pytest.mark.parametrize("path", ["skipped", "caught-pre-call"])
def test_staged_claim_requires_checked_promotion(harness, authority, observe, calls, path):
    def broken_inputs():
        raise ValueError("fixture argument error")
    with pytest.raises(TenantBoundaryError) as failure:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            _stage(unit, harness, authority)
            if path == "caught-pre-call":
                with pytest.raises(ValueError, match="argument error"):
                    unit.promote_pending_claim(broken_inputs())
            assert harness.pool.acquired[-1].info.transaction_status is TransactionStatus.INTRANS
            assert harness.manager.promotions == []
            observe(unit.batch, None)
    _assert_failed(failure, calls, observe, unit.batch)


@pytest.mark.parametrize("stage", [True, False], ids=["unbound-claim", "bound-without-claim"])
def test_no_promotion_obligation(harness, authority, observe, calls, stage):
    harness.manager.promotion_enabled = not stage
    with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
        if stage:
            _stage(unit, harness, authority)
        else:
            _attempt(unit, authority)
        observe(unit.batch, None)
    assert harness.manager.promotions == [] and len(calls["commit"]) == 1
    observe(unit.batch, [harness.manager.checked_claim.assertion_id] if stage else [])


@pytest.mark.parametrize("finish", ["commit", "caller-rollback", "lost-reply"])
def test_checked_promotion_remains_provisional(harness, authority, observe, calls, monkeypatch, finish):
    if finish == "lost-reply":
        native_commits = lose_commit_reply(monkeypatch, harness)
        outcome = pytest.raises(TenantBoundaryError)
    elif finish == "caller-rollback":
        outcome = pytest.raises(ValueError, match="rollback after promotion")
    else:
        outcome = nullcontext()
    with outcome as error:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            inputs = _stage(unit, harness, authority)
            assert unit.promote_pending_claim(inputs) == (_trace_id(unit.batch), sha256_bytes(inputs.evidence_bytes))
            observe(unit.batch, None)
            if finish == "caller-rollback":
                raise ValueError("rollback after promotion")
    if finish == "lost-reply":
        assert error.value.outcome is TenantBoundaryOutcome.FINALIZATION_UNKNOWN
        assert len(native_commits) == 1
    assert harness.manager.promotions == [inputs] and len(calls["commit"]) == int(finish != "caller-rollback")
    observe(unit.batch, None if finish == "caller-rollback" else _markers(unit.batch, harness.manager.checked_claim))


@pytest.mark.parametrize("mode", ["input-refusal", "readback-error", "process-control", "sql-error", "savepoint"])
def test_caught_promotion_error_is_terminal(harness, authority, observe, calls, mode):
    manager = harness.manager
    manager.promotion_mode = "sql-error" if mode == "savepoint" else mode
    sql_error = manager.promotion_mode == "sql-error"
    if mode == "readback-error":
        manager.promotion_failure = ValueError("failed fixture readback")
    if mode == "process-control":
        manager.promotion_failure = KeyboardInterrupt("interrupted fixture readback")
    expected = psycopg.errors.UniqueViolation if sql_error else ValueError
    if manager.promotion_failure is not None:
        expected = type(manager.promotion_failure)
    with pytest.raises(TenantBoundaryError) as failure:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            inputs = _stage(unit, harness, authority)
            writer = harness.pool.acquired[-1]
            if mode == "savepoint":
                writer.execute("SAVEPOINT before_promotion")
            with pytest.raises(expected) as caught:
                unit.promote_pending_claim(inputs)
            if manager.promotion_failure is not None:
                assert caught.value is manager.promotion_failure
            assert writer.info.transaction_status is (TransactionStatus.INERROR if sql_error else TransactionStatus.INTRANS)
            if mode == "savepoint":
                writer.execute("ROLLBACK TO SAVEPOINT before_promotion")
                writer.execute("RELEASE SAVEPOINT before_promotion")
                assert writer.info.transaction_status is TransactionStatus.INTRANS
            if writer.info.transaction_status is TransactionStatus.INTRANS:
                ids = [manager.checked_claim.assertion_id] if mode in {"input-refusal", "savepoint"} else _markers(unit.batch, manager.checked_claim)
                _check_rows(writer, unit.batch, writer.info.backend_pid, ids)
            with pytest.raises(RuntimeError, match="rollback-only"):
                unit.promote_pending_claim(inputs)
            observe(unit.batch, None)
    assert manager.promotions == [inputs]
    _assert_failed(failure, calls, observe, unit.batch)


class TupleSubclass(tuple):
    pass


class StringSubclass(str):
    pass


_DIGEST = "sha256:" + "a" * 64


@pytest.mark.parametrize("result", [
    pytest.param(["trace", _DIGEST], id="list"),
    pytest.param(TupleSubclass(("trace", _DIGEST)), id="tuple-subclass"),
    pytest.param(("trace",), id="one-element"),
    pytest.param(("trace", _DIGEST, "extra"), id="three-elements"),
    pytest.param((1, _DIGEST), id="non-string-id"),
    pytest.param((StringSubclass("trace"), _DIGEST), id="id-subclass"),
    pytest.param(("trace", StringSubclass(_DIGEST)), id="digest-subclass"),
    pytest.param(("", _DIGEST), id="empty-id"),
    pytest.param(("x" * 256, _DIGEST), id="oversize-id"),
    pytest.param(("trace/invalid", _DIGEST), id="invalid-ascii-id"),
    pytest.param(("trace", "a" * 64), id="bare-digest"),
    pytest.param(("trace", "sha256:" + "A" * 64), id="uppercase-digest"),
])
def test_invalid_producer_return_after_readback_rolls_back(harness, authority, observe, calls, result):
    manager = harness.manager
    manager.promotion_mode = "bad-return"
    manager.bad_return = result
    with pytest.raises(TenantBoundaryError) as failure:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            inputs = _stage(unit, harness, authority)
            with pytest.raises(RuntimeError):
                unit.promote_pending_claim(inputs)
            writer = harness.pool.acquired[-1]
            assert writer.info.transaction_status is TransactionStatus.INTRANS
            _check_rows(writer, unit.batch, writer.info.backend_pid, _markers(unit.batch, manager.checked_claim))
            observe(unit.batch, None)
    assert manager.promotions == [inputs]
    _assert_failed(failure, calls, observe, unit.batch)


@pytest.mark.parametrize("field,value", [
    ("tenant_id", uuid4()), ("principal_ref", "other-principal"), ("binding_nonce", uuid4()),
    ("request_id", "other-request"), ("batch_id", "other-batch"), ("full_xid", -1),
    ("full_xid", True), ("evidence_bytes", "not-bytes"),
    ("action", "ANOTHER_ACTION"), ("bundle_digest", "sha256:" + "f" * 64),
    ("contract_digest", "sha256:" + "9" * 64),
])
def test_mismatched_binding_never_dispatches(harness, authority, observe, calls, field, value):
    with pytest.raises(TenantBoundaryError) as failure:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            inputs = _stage(unit, harness, authority)
            if field in {"action", "bundle_digest", "contract_digest"}:
                changed = replace(inputs, command=replace(inputs.command, **{field: value}))
            else:
                changed = replace(inputs, **{field: value})
            with pytest.raises(RuntimeError):
                unit.promote_pending_claim(changed)
            observe(unit.batch, None)
    assert harness.manager.promotions == []
    _assert_failed(failure, calls, observe, unit.batch)


@pytest.mark.parametrize("mode", ["early", "unavailable", "duplicate", "reentry"])
def test_caught_order_or_single_use_violation_is_terminal(harness, authority, observe, calls, mode):
    manager = harness.manager
    manager.promotion_enabled = mode != "unavailable"
    with pytest.raises(TenantBoundaryError) as failure:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            inputs = _inputs(unit, _attempt(unit, authority)) if mode == "early" else _stage(unit, harness, authority)
            if mode == "duplicate":
                unit.promote_pending_claim(inputs)
            if mode == "reentry":
                manager.promotion_mode = "reentry"

                def caught_reentry():
                    with pytest.raises(RuntimeError):
                        unit.promote_pending_claim(inputs)

                manager.reenter = caught_reentry
            with pytest.raises(RuntimeError):
                unit.promote_pending_claim(inputs)
            observe(unit.batch, None)
    assert len(manager.promotions) == int(mode in {"duplicate", "reentry"})
    _assert_failed(failure, calls, observe, unit.batch)


def test_checked_stage_from_other_command_cannot_arm_promotion(harness, authority, observe, calls, monkeypatch):
    manager = harness.manager
    with pytest.raises(TenantBoundaryError) as failure:
        with harness.runtime.tenant_unit_of_work(harness.principal) as unit:
            attempt = _attempt(unit, authority)
            stage = manager.operation.stage_and_verify_operation_claim

            def wrong_staged_command(attempt):
                result = stage(attempt)
                return replace(result, command=replace(result.command, action="ANOTHER_ACTION"))

            monkeypatch.setattr(manager.operation, "stage_and_verify_operation_claim", wrong_staged_command)
            with pytest.raises(RuntimeError):
                unit.stage_operation_claim(attempt)
            with pytest.raises(RuntimeError, match="rollback-only"):
                unit.promote_pending_claim(_inputs(unit, attempt))
            observe(unit.batch, None)
    assert manager.promotions == []
    _assert_failed(failure, calls, observe, unit.batch)


def test_stale_and_foreign_calls_leave_new_owner_healthy(harness, authority, observe, calls):
    with harness.runtime.tenant_unit_of_work(harness.principal) as old:
        original_backend = harness.pool.acquired[-1].info.backend_pid
    with harness.runtime.tenant_unit_of_work(harness.principal) as live:
        inputs = _stage(live, harness, authority)
        assert harness.pool.acquired[-1].info.backend_pid == original_backend
        with pytest.raises(RuntimeError, match="closed"):
            old.promote_pending_claim(inputs)
        with ThreadPoolExecutor(1) as pool:
            with pytest.raises(RuntimeError, match="thread"):
                pool.submit(live.promote_pending_claim, inputs).result(timeout=5)
        assert harness.manager.promotions == []
        assert live.promote_pending_claim(inputs) == (_trace_id(live.batch), sha256_bytes(inputs.evidence_bytes))
        observe(live.batch, None)
    assert len(calls["commit"]) == 2 and harness.manager.promotions == [inputs]
    observe(live.batch, _markers(live.batch, harness.manager.checked_claim))
