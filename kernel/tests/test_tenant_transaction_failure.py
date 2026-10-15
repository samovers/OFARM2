"""Finite failure/control-flow seams; real rollback evidence lives in runtime tests."""
from __future__ import annotations

import asyncio

import pytest
from psycopg.pq import TransactionStatus

import kernel.tenant_uow as owner
from kernel.principal import AuthenticatedPrincipal
from kernel.tenant_command_runtime_bundle_selector import (
    CommandRuntimeBundleSelectionRefused,
)
from kernel.tenant_uow import (
    GovernedBatchRequest, TenantBoundaryError, TenantBoundaryOutcome,
    TenantUnitOfWorkManager,
)
from kernel.tests import test_tenant_uow as support
from kernel.tests._signing_support import IDENTITY, principal_authority


REQUEST = GovernedBatchRequest(
    "batch-transaction-failure", "TEST_OPERATION", "request-transaction-failure",
    "sha256:" + "7" * 64,
)


class _Pool(support._Pool):
    def __init__(self, connection, *, return_error=None):
        super().__init__(connection)
        self.acquired = []
        self.return_attempts = []
        self.return_error = return_error

    def getconn(self, *, timeout):
        connection = super().getconn(timeout=timeout)
        self.acquired.append(connection)
        return connection

    def putconn(self, connection):
        self.return_attempts.append(connection)
        if self.return_error is not None:
            raise self.return_error
        super().putconn(connection)


class _UnreadableInfo:
    def __init__(self, error, *, once=False):
        self.error = error
        self.once = once
        self.reads = 0
        self.status = TransactionStatus.INTRANS

    @property
    def transaction_status(self):
        self.reads += 1
        if not self.once or self.reads == 1:
            raise self.error
        return self.status

    @transaction_status.setter
    def transaction_status(self, value):
        self.status = value


@pytest.fixture
def principal():
    return AuthenticatedPrincipal(IDENTITY, principal_authority())


@pytest.fixture(autouse=True)
def no_physical_observer(monkeypatch):
    def unexpected_observer(*_args):
        pytest.fail("ordinary failure started a physical observer")

    monkeypatch.setattr(owner, "observe_physical_outcome", unexpected_observer)


def _assert_one_original_return(pool, connection):
    assert pool.acquired == [connection]
    assert pool.return_attempts == [connection]
    assert ("COMMIT", ()) not in connection.events


@pytest.mark.parametrize("cached", (False, True), ids=("uncalled", "cached"))
@pytest.mark.parametrize(
    "error_type", (RuntimeError, KeyboardInterrupt, SystemExit, asyncio.CancelledError),
)
def test_tf03_tf04_caught_allocator_failure_is_terminal(
    principal, monkeypatch, cached, error_type,
):
    connection = support._Connection(principal)
    pool = _Pool(connection)
    manager = TenantUnitOfWorkManager(pool, support._Minter())
    failure = error_type("allocator failure")
    allocations, resolutions = [], []
    selected = support._trusted_token()

    def allocate(*args):
        allocations.append(args)
        connection.info.transaction_status = TransactionStatus.INERROR
        raise failure

    def resolve(*args):
        resolutions.append(args)
        return selected

    monkeypatch.setattr(owner, "_allocate_governed_batch", allocate)
    monkeypatch.setattr(owner, "_resolve_commit_operation_claim_draft_runtime_bundle", resolve)
    with pytest.raises(TenantBoundaryError) as failed:
        with manager.unit_of_work(principal) as unit:
            if cached:
                assert unit.resolve_commit_operation_claim_draft_runtime_bundle() is selected
            with pytest.raises(error_type) as raised:
                unit.begin_batch(REQUEST)
            assert raised.value is failure
            assert unit.batch is None
            # A declared driver-state seam cannot rehabilitate application failure.
            connection.info.transaction_status = TransactionStatus.INTRANS
            with pytest.raises(RuntimeError, match="rollback-only"):
                unit.begin_batch(REQUEST)
            with pytest.raises(RuntimeError, match="rollback-only"):
                unit.begin_batch(object())
            for _attempt in range(2):
                with pytest.raises(CommandRuntimeBundleSelectionRefused):
                    unit.resolve_commit_operation_claim_draft_runtime_bundle()

    assert failed.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert failed.value.physical_observation is None
    assert len(allocations) == 1
    assert len(resolutions) == int(cached)
    assert connection.events[-1] == ("ROLLBACK", ())
    assert pool.returned == [connection]
    _assert_one_original_return(pool, connection)
    with pytest.raises(RuntimeError, match="closed"):
        unit.resolve_commit_operation_claim_draft_runtime_bundle()


@pytest.mark.parametrize("source", ("allocator", "body"))
@pytest.mark.parametrize("rollback_fails", (False, True))
@pytest.mark.parametrize(
    "error_type", (RuntimeError, KeyboardInterrupt, SystemExit, asyncio.CancelledError),
)
def test_tf04_escaping_error_identity_survives_ordinary_rollback_failure(
    principal, monkeypatch, source, rollback_fails, error_type,
):
    connection = support._Connection(
        principal, rollback_error=OSError("rollback failed") if rollback_fails else None,
    )
    pool = _Pool(connection)
    failure = error_type("original failure")

    def allocate(*_args):
        raise failure

    monkeypatch.setattr(owner, "_allocate_governed_batch", allocate)
    with pytest.raises(error_type) as raised:
        with TenantUnitOfWorkManager(pool, support._Minter()).unit_of_work(principal) as unit:
            if source == "allocator":
                unit.begin_batch(REQUEST)
            raise failure

    assert raised.value is failure
    assert connection.closed is rollback_fails
    assert pool.returned == [connection]
    _assert_one_original_return(pool, connection)


@pytest.mark.parametrize("status", tuple(TransactionStatus), ids=lambda value: value.name)
def test_tf07_state_gate_closes_facade_before_classifying(principal, status):
    connection = support._Connection(principal)
    pool = _Pool(connection)
    manager = TenantUnitOfWorkManager(pool, support._Minter())
    context = manager.unit_of_work(principal)
    unit = context.__enter__()

    class ClosedFacadeInfo:
        def __init__(self):
            self.status = status

        @property
        def transaction_status(self):
            with pytest.raises(RuntimeError, match="closed"):
                unit._require_active()
            return self.status

        @transaction_status.setter
        def transaction_status(self, value):
            self.status = value

    connection.info = ClosedFacadeInfo()

    if status is TransactionStatus.INTRANS:
        assert context.__exit__(None, None, None) is False
        assert connection.events[-1] == ("COMMIT", ())
        assert connection.events.count(("COMMIT", ())) == 1
    else:
        with pytest.raises(TenantBoundaryError) as failed:
            context.__exit__(None, None, None)
        expected = (
            TenantBoundaryOutcome.TRANSACTION_FAILED
            if status is TransactionStatus.INERROR
            else TenantBoundaryOutcome.FINALIZATION_UNKNOWN
        )
        assert failed.value.outcome is expected
        assert failed.value.physical_observation is None
        assert connection.closed is (status is not TransactionStatus.INERROR)
        assert (("ROLLBACK", ()) in connection.events) is (status is TransactionStatus.INERROR)
        _assert_one_original_return(pool, connection)
    assert pool.returned == [connection]
    with pytest.raises(RuntimeError, match="closed"):
        unit.begin_batch(REQUEST)


def test_tf07_unreadable_state_discards_without_commit_or_observer(principal):
    connection = support._Connection(principal)
    pool = _Pool(connection)
    with pytest.raises(TenantBoundaryError) as failed:
        with TenantUnitOfWorkManager(pool, support._Minter()).unit_of_work(principal):
            connection.info = _UnreadableInfo(OSError("status unavailable"))

    assert failed.value.outcome is TenantBoundaryOutcome.FINALIZATION_UNKNOWN
    assert failed.value.physical_observation is None
    assert connection.closed
    assert ("ROLLBACK", ()) not in connection.events
    _assert_one_original_return(pool, connection)


@pytest.mark.parametrize("error_type", (KeyboardInterrupt, SystemExit, asyncio.CancelledError))
def test_tf07_state_read_process_control_preserves_identity(principal, error_type):
    connection = support._Connection(principal)
    pool = _Pool(connection)
    failure = error_type("status interrupted")
    with pytest.raises(error_type) as raised:
        with TenantUnitOfWorkManager(pool, support._Minter()).unit_of_work(principal):
            connection.info = _UnreadableInfo(failure, once=True)

    assert raised.value is failure
    assert connection.closed
    assert pool.returned == [connection]
    _assert_one_original_return(pool, connection)


@pytest.mark.parametrize("poisoned", (False, True), ids=("inerror", "rollback-only"))
@pytest.mark.parametrize(
    ("rollback_fails", "close_fails", "return_fails"),
    ((False, False, False), (True, False, False), (True, True, False),
     (False, False, True), (True, True, True)),
)
def test_tf05_known_failure_survives_ordinary_cleanup_errors(
    principal, monkeypatch, poisoned, rollback_fails, close_fails, return_fails,
):
    connection = support._Connection(
        principal, batch_position=0,
        rollback_error=OSError("rollback unavailable") if rollback_fails else None,
    )
    pool = _Pool(connection, return_error=OSError("return unavailable") if return_fails else None)
    if close_fails:
        def close():
            connection.events.append(("CLOSE", ()))
            raise OSError("close unavailable")
        monkeypatch.setattr(connection, "close", close)

    with pytest.raises(TenantBoundaryError) as failed:
        with TenantUnitOfWorkManager(pool, support._Minter()).unit_of_work(principal) as unit:
            if poisoned:
                with pytest.raises(RuntimeError, match="knowledge position"):
                    unit.begin_batch(REQUEST)
                connection.info.transaction_status = TransactionStatus.UNKNOWN
            else:
                connection.info.transaction_status = TransactionStatus.INERROR

    assert failed.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert failed.value.physical_observation is None
    assert connection.events.count(("ROLLBACK", ())) == 1
    assert (("CLOSE", ()) in connection.events) is rollback_fails
    assert pool.returned == ([] if return_fails else [connection])
    # Failed return records an attempt only; it does not prove recovered capacity.
    _assert_one_original_return(pool, connection)


@pytest.mark.parametrize("stage", ("rollback", "close", "return"))
@pytest.mark.parametrize("error_type", (KeyboardInterrupt, SystemExit, asyncio.CancelledError))
def test_tf05_cleanup_process_control_keeps_existing_precedence(
    principal, monkeypatch, stage, error_type,
):
    failure = error_type("cleanup interrupted")
    connection = support._Connection(
        principal, rollback_error=(
            failure if stage == "rollback" else OSError("rollback failed")
            if stage == "close" else None
        ),
    )
    pool = _Pool(connection, return_error=failure if stage == "return" else None)
    if stage == "close":
        actual_close = connection.close

        def interrupt_close_once():
            monkeypatch.setattr(connection, "close", actual_close)
            raise failure

        monkeypatch.setattr(connection, "close", interrupt_close_once)
    with pytest.raises(error_type) as raised:
        with TenantUnitOfWorkManager(pool, support._Minter()).unit_of_work(principal):
            connection.info.transaction_status = TransactionStatus.INERROR

    assert raised.value is failure
    assert pool.returned == ([] if stage == "return" else [connection])
    _assert_one_original_return(pool, connection)


def test_tf07_rollback_only_remains_known_when_status_is_unreadable(principal):
    connection = support._Connection(principal, batch_position=0)
    pool = _Pool(connection)
    with pytest.raises(TenantBoundaryError) as failed:
        with TenantUnitOfWorkManager(pool, support._Minter()).unit_of_work(principal) as unit:
            with pytest.raises(RuntimeError, match="knowledge position"):
                unit.begin_batch(REQUEST)
            connection.info = _UnreadableInfo(OSError("status unavailable"))

    assert failed.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert failed.value.physical_observation is None
    assert connection.closed
    _assert_one_original_return(pool, connection)


def test_tf08_wrong_type_and_duplicate_guards_preserve_valid_batch(principal):
    connection = support._Connection(principal)
    pool = _Pool(connection)
    with TenantUnitOfWorkManager(pool, support._Minter()).unit_of_work(principal) as unit:
        with pytest.raises(RuntimeError, match="already exists"):
            unit.begin_batch(object())
        batch = unit.begin_batch(REQUEST)
        with pytest.raises(RuntimeError, match="already exists"):
            unit.begin_batch(REQUEST)
        with pytest.raises(RuntimeError, match="already exists"):
            unit.begin_batch(object())
        assert unit.batch is batch
        assert batch.batch_id == REQUEST.batch_id
        assert batch.request_id == REQUEST.request_id
        assert batch.runtime_bundle_digest == REQUEST.runtime_bundle_digest

    assert connection.events.count(("COMMIT", ())) == 1
    assert ("ROLLBACK", ()) not in connection.events
    assert pool.acquired == pool.return_attempts == pool.returned == [connection]
    assert unit.batch is batch
    with pytest.raises(RuntimeError, match="closed"):
        unit.begin_batch(REQUEST)
