"""Observation transport and pre-yield failure histories for the tenant UOW."""
from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.pq import TransactionStatus

from kernel.principal import AuthenticatedPrincipal
from kernel.tenant_capability_issuer import TenantChallenge
from kernel.tenant_uow import (
    TenantBoundaryError,
    TenantBoundaryOutcome,
    TenantUnitOfWorkManager,
)
from kernel.tests._signing_support import AUDIENCE, IDENTITY, principal_authority
from kernel.tests.test_tenant_uow import _Connection, _Cursor, _Minter, _Pool


_CREATE = "SELECT * FROM ofarm.create_tenant_challenge()"
_OBSERVE = "SELECT * FROM ofarm.current_tenant_challenge()"
_BIND = "SELECT ofarm.bind_tenant_capability(%s)"
_CONTEXT = "SELECT * FROM ofarm.current_tenant_context()"
_DEFAULT = object()


class _FailingCursor:
    def __init__(self, connection):
        self._connection = connection

    def fetchone(self):
        self._connection.fail_observation()


class _ObservationConnection(_Connection):
    def __init__(
        self,
        principal,
        *,
        created_row=_DEFAULT,
        observed_row=_DEFAULT,
        failure=None,
        failure_stage=None,
        rollback_error=None,
    ):
        super().__init__(principal, rollback_error=rollback_error)
        self.created_row = created_row
        self.observed_row = observed_row
        self.failure = failure
        self.failure_stage = failure_stage

    def fail_observation(self):
        if isinstance(self.failure, psycopg.Error):
            self.info.transaction_status = TransactionStatus.INERROR
        raise self.failure

    def execute(self, query, parameters=()):
        cursor = super().execute(query, parameters)
        compact = " ".join(query.split())
        if compact == _CREATE and self.created_row is not _DEFAULT:
            return _Cursor(self.created_row)
        if compact == _OBSERVE:
            if self.failure_stage == "execute":
                self.fail_observation()
            if self.failure_stage == "fetch":
                return _FailingCursor(self)
            if self.observed_row is not _DEFAULT:
                return _Cursor(self.observed_row)
        return cursor


class _RecordingPool(_Pool):
    def __init__(self, connection):
        super().__init__(connection)
        self.checkouts = []
        self.return_states = []

    def getconn(self, *, timeout):
        connection = super().getconn(timeout=timeout)
        self.checkouts.append(connection)
        connection.events.append(("CHECKOUT", ()))
        return connection

    def putconn(self, connection):
        self.return_states.append(
            (connection.info.transaction_status, connection.closed)
        )
        connection.events.append(("POOL_RETURN", ()))
        super().putconn(connection)


class _RecordingMinter(_Minter):
    def __init__(self, connection, error=None):
        super().__init__(error)
        self.connection = connection

    def mint(self, identity, authority, challenge):
        assert self.connection.info.transaction_status is TransactionStatus.INTRANS
        self.connection.events.append(("MINT", (challenge,)))
        return super().mint(identity, authority, challenge)


@pytest.fixture
def principal():
    return AuthenticatedPrincipal(IDENTITY, principal_authority())


def _queries(connection):
    return [query for query, _parameters in connection.events]


def test_observation_and_mint_use_one_transaction_and_immutable_exact_value(principal):
    connection = _ObservationConnection(principal)
    pool = _RecordingPool(connection)
    minter = _RecordingMinter(connection)
    manager = TenantUnitOfWorkManager(pool, minter)

    with manager.unit_of_work(principal) as unit:
        connection.events.append(("YIELD", ()))
        assert unit.binding.tenant_id == principal.authority.tenant_id
        assert pool.checkouts == [connection]
        assert len(minter.challenges) == 1
        challenge = minter.challenges[0]
        assert type(challenge) is TenantChallenge
        assert challenge.challenge_id == connection._challenge_id
        assert challenge.audience == AUDIENCE
        assert challenge.created_at_us == connection._challenge_created_at_us
        for name, replacement in (
            ("challenge_id", uuid4()),
            ("audience", "replacement-audience"),
            ("created_at_us", challenge.created_at_us + 1),
        ):
            with pytest.raises(FrozenInstanceError):
                setattr(challenge, name, replacement)
            with pytest.raises(FrozenInstanceError):
                delattr(challenge, name)

    assert _queries(connection) == [
        "CHECKOUT", "BEGIN ISOLATION LEVEL READ COMMITTED", _CREATE, _OBSERVE,
        "MINT", _BIND, _CONTEXT, "YIELD", "COMMIT", "POOL_RETURN",
    ]
    assert pool.returned == [connection]
    assert pool.return_states == [(TransactionStatus.IDLE, False)]


@pytest.mark.parametrize(
    ("side", "row"),
    (
        ("created", None),
        ("created", ()),
        ("created", (uuid4(),)),
        ("created", (uuid4(), AUDIENCE, "extra")),
        ("created", ("00000000-0000-4000-8000-000000000001", AUDIENCE)),
        ("created", (UUID(int=0), AUDIENCE)),
        ("observed", None),
        ("observed", ()),
        ("observed", (uuid4(),)),
        ("observed", (uuid4(), 1_788_000_000_000_123, "extra")),
        ("observed", ("00000000-0000-4000-8000-000000000001", 123)),
        ("observed", (UUID(int=0), 123)),
        ("observed", (uuid4(), 1_788_000_000_000_123)),
    ),
    ids=(
        "creator-absent", "creator-empty", "creator-short", "creator-extra",
        "creator-uuid-string", "creator-zero-uuid", "observer-absent",
        "observer-empty", "observer-short", "observer-extra",
        "observer-uuid-string", "observer-zero-uuid", "observer-other-uuid",
    ),
)
def test_malformed_or_misjoined_rows_refuse_before_mint_and_binding(principal, side, row):
    connection = _ObservationConnection(principal, **{f"{side}_row": row})
    pool = _RecordingPool(connection)
    minter = _RecordingMinter(connection)
    manager = TenantUnitOfWorkManager(pool, minter)

    with pytest.raises(TenantBoundaryError) as raised:
        with manager.unit_of_work(principal):
            pytest.fail("invalid challenge metadata exposed a UnitOfWork")

    assert raised.value.outcome is TenantBoundaryOutcome.BINDING_REFUSED
    assert str(raised.value) == "tenant boundary refused (BINDING_REFUSED)"
    assert minter.challenges == []
    assert _queries(connection) == [
        "CHECKOUT", "BEGIN ISOLATION LEVEL READ COMMITTED", _CREATE, _OBSERVE,
        "ROLLBACK", "POOL_RETURN",
    ]
    assert pool.returned == [connection]
    assert pool.return_states == [(TransactionStatus.IDLE, False)]


@pytest.mark.parametrize("stage", ("execute", "fetch"))
@pytest.mark.parametrize(
    "failure_type", (psycopg.errors.QueryCanceled, psycopg.DatabaseError),
    ids=("statement-cancelled", "database-error"),
)
@pytest.mark.parametrize("rollback_fails", (False, True), ids=("rollback", "discard"))
def test_observer_sql_failure_rolls_back_or_discards_before_pool_return(
    principal, stage, failure_type, rollback_fails,
):
    rollback_error = OSError("rollback reply lost") if rollback_fails else None
    connection = _ObservationConnection(
        principal, failure=failure_type("observer query failed"),
        failure_stage=stage, rollback_error=rollback_error,
    )
    pool = _RecordingPool(connection)
    minter = _RecordingMinter(connection)
    manager = TenantUnitOfWorkManager(pool, minter)

    with pytest.raises(TenantBoundaryError) as raised:
        with manager.unit_of_work(principal):
            pytest.fail("observer failure exposed a UnitOfWork")

    assert raised.value.outcome is TenantBoundaryOutcome.BINDING_REFUSED
    assert minter.challenges == []
    queries = _queries(connection)
    assert queries[:5] == [
        "CHECKOUT", "BEGIN ISOLATION LEVEL READ COMMITTED", _CREATE, _OBSERVE,
        "ROLLBACK",
    ]
    assert queries[-1] == "POOL_RETURN"
    assert set(queries[5:-1]) == ({"CLOSE"} if rollback_fails else set())
    status = TransactionStatus.UNKNOWN if rollback_fails else TransactionStatus.IDLE
    assert pool.return_states == [(status, rollback_fails)]
    assert pool.returned == [connection]


@pytest.mark.parametrize("stage", ("execute", "fetch", "mint"))
@pytest.mark.parametrize(
    "failure_type", (asyncio.CancelledError, KeyboardInterrupt),
    ids=("task-cancelled", "keyboard-interrupt"),
)
def test_pre_yield_cancellation_discards_transaction_before_pool_return(
    principal, stage, failure_type,
):
    failure = failure_type("cancel before yielding tenant transaction")
    connection = _ObservationConnection(
        principal, failure=failure, failure_stage=stage,
    )
    pool = _RecordingPool(connection)
    minter = _RecordingMinter(connection, failure if stage == "mint" else None)
    manager = TenantUnitOfWorkManager(pool, minter)

    with pytest.raises(failure_type) as raised:
        with manager.unit_of_work(principal):
            pytest.fail("cancelled admission exposed a UnitOfWork")

    assert raised.value is failure
    expected = [
        "CHECKOUT", "BEGIN ISOLATION LEVEL READ COMMITTED", _CREATE, _OBSERVE,
    ]
    if stage == "mint":
        expected.append("MINT")
    assert _queries(connection) == [*expected, "CLOSE", "POOL_RETURN"]
    assert len(minter.challenges) == (1 if stage == "mint" else 0)
    assert pool.returned == [connection]
    assert pool.return_states == [(TransactionStatus.UNKNOWN, True)]


def test_new_transaction_after_observer_refusal_uses_fresh_challenge(principal):
    connection = _ObservationConnection(
        principal, failure=psycopg.errors.QueryCanceled("observation cancelled"),
        failure_stage="fetch",
    )
    pool = _RecordingPool(connection)
    minter = _RecordingMinter(connection)
    manager = TenantUnitOfWorkManager(pool, minter)

    with pytest.raises(TenantBoundaryError):
        with manager.unit_of_work(principal):
            pytest.fail("failed observation exposed a UnitOfWork")
    previous_id = connection._challenge_id
    assert _queries(connection).count(_CREATE) == 1
    assert minter.challenges == []
    connection.failure_stage = None
    connection._challenge_created_at_us += 123

    with manager.unit_of_work(principal):
        challenge = minter.challenges[0]
        assert challenge.challenge_id != previous_id
        assert challenge.challenge_id == connection._challenge_id
        assert challenge.created_at_us == connection._challenge_created_at_us

    assert _queries(connection).count(_CREATE) == 2
    assert _queries(connection).count(_OBSERVE) == 2
    assert _queries(connection).count(_BIND) == 1
    assert pool.returned == [connection, connection]
    assert pool.return_states == [(TransactionStatus.IDLE, False)] * 2
