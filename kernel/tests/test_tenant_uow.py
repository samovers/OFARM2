"""Focused transaction-ownership tests for the tenant UnitOfWork."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from psycopg.pq import TransactionStatus

from kernel.principal import AuthenticatedPrincipal
from kernel.tenant_uow import (
    GovernedBatchRequest,
    TenantBoundaryError,
    TenantBoundaryOutcome,
    TenantUnitOfWorkManager,
)
from kernel.tenant_capability_issuer import CapabilityMintError
from kernel.tests._signing_support import (
    AUDIENCE,
    IDENTITY,
    KID,
    principal_authority,
)


class _Cursor:
    def __init__(self, row=None, *, rowcount=1):
        self._row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self._row

    def fetchall(self):
        return [] if self._row is None else [self._row]


class _Info:
    def __init__(self):
        self.transaction_status = TransactionStatus.IDLE


def _binding_row(principal, *, subject=None):
    authority = principal.authority
    return (
        authority.equality_policy,
        authority.issuer,
        subject or authority.subject,
        authority.binding_version_id,
        authority.binding_version_digest,
        authority.lifecycle_head_id,
        authority.lifecycle_head_digest,
        authority.tenant_id,
        authority.tenant_registration_digest,
        authority.party_ref,
        authority.party_record_kind,
        authority.party_record_id,
        authority.party_schema_digest,
        authority.party_payload_digest,
        KID,
        uuid4(),
        "sha256:" + "9" * 64,
        uuid4(),
        datetime.now(timezone.utc),
    )


class _Connection:
    def __init__(
        self,
        principal,
        *,
        context_row=None,
        commit_error=None,
        rollback_error=None,
        batch_position=1,
    ):
        self.info = _Info()
        self.closed = False
        self.events = []
        self._principal = principal
        self._context_row = context_row or _binding_row(principal)
        self._commit_error = commit_error
        self._rollback_error = rollback_error
        self._batch_position = batch_position

    def execute(self, query, parameters=()):
        compact = " ".join(query.split())
        self.events.append((compact, parameters))
        if compact.startswith("BEGIN"):
            self.info.transaction_status = TransactionStatus.INTRANS
            return _Cursor()
        if "create_tenant_challenge" in compact:
            return _Cursor((uuid4(), AUDIENCE))
        if "bind_tenant_capability" in compact:
            return _Cursor((None,))
        if "current_tenant_context" in compact:
            return _Cursor(self._context_row)
        if compact.startswith("INSERT INTO ofarm.governed_write_batch"):
            authority = self._principal.authority
            return _Cursor(
                (
                    authority.tenant_id,
                    parameters[1],
                    "42",
                    authority.party_ref,
                    parameters[3],
                    parameters[4],
                    parameters[5],
                    self._batch_position,
                    datetime.now(timezone.utc),
                )
            )
        return _Cursor((self._principal.authority.tenant_id,))

    def commit(self):
        self.events.append(("COMMIT", ()))
        if self._commit_error is not None:
            raise self._commit_error
        self.info.transaction_status = TransactionStatus.IDLE

    def rollback(self):
        self.events.append(("ROLLBACK", ()))
        if self._rollback_error is not None:
            raise self._rollback_error
        self.info.transaction_status = TransactionStatus.IDLE

    def close(self):
        self.events.append(("CLOSE", ()))
        self.closed = True
        self.info.transaction_status = TransactionStatus.UNKNOWN

    @contextmanager
    def transaction(self):
        self.events.append(("SAVEPOINT", ()))
        try:
            yield
        except BaseException:
            self.events.append(("ROLLBACK TO SAVEPOINT", ()))
            raise
        else:
            self.events.append(("RELEASE SAVEPOINT", ()))


class _Pool:
    def __init__(self, connection):
        self.connection = connection
        self.returned = []

    def getconn(self, *, timeout):
        assert timeout == 5.0
        return self.connection

    def putconn(self, connection):
        self.returned.append(connection)

    def open(self, *, wait, timeout):
        assert (wait, timeout) == (True, 5.0)

    def close(self, *, timeout=5.0):
        assert timeout == 5.0


class _Minter:
    def __init__(self, error=None):
        self.challenges = []
        self.authorities = []
        self._error = error

    def mint(self, identity, authority, challenge):
        assert identity == IDENTITY
        assert authority.subject == identity.subject
        self.authorities.append(authority)
        self.challenges.append(challenge)
        if self._error is not None:
            raise self._error
        return "signed-capability"


@pytest.fixture
def principal():
    return AuthenticatedPrincipal(IDENTITY, principal_authority())


def test_tenant_boundary_outcomes_are_exact_and_unique():
    expected = (
        "UNAVAILABLE",
        "CAPABILITY_REFUSED",
        "BINDING_REFUSED",
        "FINALIZATION_UNKNOWN",
    )
    assert tuple(TenantBoundaryOutcome.__members__) == expected
    assert tuple(outcome.value for outcome in TenantBoundaryOutcome) == expected


def test_unit_of_work_binds_allocates_one_batch_and_commits(principal):
    connection = _Connection(principal)
    pool = _Pool(connection)
    minter = _Minter()
    manager = TenantUnitOfWorkManager(pool, minter)
    request = GovernedBatchRequest(
        "batch-01",
        "TEST_OPERATION",
        "request-01",
        "sha256:" + "7" * 64,
    )

    with manager.unit_of_work(principal) as unit:
        assert unit.binding.tenant_id == principal.authority.tenant_id
        assert minter.challenges[0].audience == AUDIENCE
        with unit.savepoint():
            with pytest.raises(RuntimeError, match="outer transaction"):
                unit.begin_batch(request)
        batch = unit.begin_batch(request)
        assert batch.full_xid == 42
        assert batch.knowledge_position == 1
        assert batch.authenticated_principal_ref == principal.authority.party_ref
        with pytest.raises(RuntimeError, match="already exists"):
            unit.begin_batch(request)
        with unit.savepoint():
            assert unit.fetch_one("SELECT tenant") == (
                principal.authority.tenant_id,
            )

    assert connection.events[-1] == ("COMMIT", ())
    assert not any(
        "take_tenant_write_lock" in query
        for query, _parameters in connection.events
    )
    assert pool.returned == [connection]
    with pytest.raises(RuntimeError, match="closed"):
        unit.fetch_one("SELECT tenant")


@pytest.mark.parametrize(
    "batch_position",
    (0, -1, 9_007_199_254_740_992, True, "1"),
)
def test_unit_of_work_refuses_invalid_database_knowledge_position(
    principal,
    batch_position,
):
    connection = _Connection(principal, batch_position=batch_position)
    manager = TenantUnitOfWorkManager(_Pool(connection), _Minter())

    with pytest.raises(
        RuntimeError,
        match="governed batch knowledge position differs",
    ):
        with manager.unit_of_work(principal) as unit:
            unit.begin_batch(
                GovernedBatchRequest(
                    "batch-invalid-position",
                    "TEST_OPERATION",
                    "request-invalid-position",
                    "sha256:" + "7" * 64,
                )
            )

    assert ("ROLLBACK", ()) in connection.events


@pytest.mark.parametrize(
    ("rollback_error", "connection_closed"),
    ((None, False), (OSError("rollback reply lost"), True)),
    ids=("rollback-succeeds", "rollback-fails"),
)
def test_capability_refusal_rolls_back_or_discards_without_binding(
    principal,
    rollback_error,
    connection_closed,
):
    connection = _Connection(principal, rollback_error=rollback_error)
    pool = _Pool(connection)
    minter = _Minter(CapabilityMintError("sensitive signing refusal"))
    manager = TenantUnitOfWorkManager(pool, minter)

    with pytest.raises(TenantBoundaryError) as raised:
        with manager.unit_of_work(principal):
            pytest.fail("capability refusal exposed a UnitOfWork")

    assert raised.value.outcome is TenantBoundaryOutcome.CAPABILITY_REFUSED
    assert str(raised.value) == "tenant boundary refused (CAPABILITY_REFUSED)"
    queries = tuple(query for query, _parameters in connection.events)
    assert not any("bind_tenant_capability" in query for query in queries)
    assert not any("current_tenant_context" in query for query in queries)
    assert connection.closed is connection_closed
    assert pool.returned == [connection]


def test_binding_mismatch_is_one_closed_outcome_and_rolls_back(principal):
    connection = _Connection(
        principal,
        context_row=_binding_row(principal, subject="subject:substitution"),
    )
    manager = TenantUnitOfWorkManager(_Pool(connection), _Minter())

    with pytest.raises(TenantBoundaryError) as raised:
        with manager.unit_of_work(principal):
            pytest.fail("mismatched binding was exposed")

    assert raised.value.outcome is TenantBoundaryOutcome.BINDING_REFUSED
    assert connection.events[-1] == ("ROLLBACK", ())


def test_operation_exception_rolls_back_and_preserves_exception(principal):
    connection = _Connection(principal)
    manager = TenantUnitOfWorkManager(_Pool(connection), _Minter())
    failure = RuntimeError("operation refused")

    with pytest.raises(RuntimeError) as raised:
        with manager.unit_of_work(principal):
            raise failure

    assert raised.value is failure
    assert connection.events[-1] == ("ROLLBACK", ())


def test_cancellation_rolls_back_before_pool_return(principal):
    connection = _Connection(principal)
    manager = TenantUnitOfWorkManager(_Pool(connection), _Minter())

    with pytest.raises(asyncio.CancelledError):
        with manager.unit_of_work(principal):
            raise asyncio.CancelledError

    assert connection.events[-1] == ("ROLLBACK", ())


def test_ambiguous_commit_discards_connection(principal):
    connection = _Connection(principal, commit_error=OSError("lost reply"))
    pool = _Pool(connection)
    manager = TenantUnitOfWorkManager(pool, _Minter())

    with pytest.raises(TenantBoundaryError) as raised:
        with manager.unit_of_work(principal):
            pass

    assert raised.value.outcome is TenantBoundaryOutcome.FINALIZATION_UNKNOWN
    assert connection.closed
    assert pool.returned == [connection]


def test_non_idle_checkout_is_discarded_without_binding(principal):
    connection = _Connection(principal)
    connection.info.transaction_status = TransactionStatus.INTRANS
    pool = _Pool(connection)
    manager = TenantUnitOfWorkManager(pool, _Minter())

    with pytest.raises(TenantBoundaryError) as raised:
        with manager.unit_of_work(principal):
            pytest.fail("non-idle connection was exposed")

    assert raised.value.outcome is TenantBoundaryOutcome.UNAVAILABLE
    assert connection.closed
    assert pool.returned == [connection]


def test_repository_surface_cannot_issue_transaction_control(principal):
    connection = _Connection(principal)
    manager = TenantUnitOfWorkManager(_Pool(connection), _Minter())

    with pytest.raises(ValueError, match="belongs to the UnitOfWork"):
        with manager.unit_of_work(principal) as unit:
            unit.execute("COMMIT")

    assert connection.events[-1] == ("ROLLBACK", ())
