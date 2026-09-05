"""Focused transaction-ownership tests for the tenant UnitOfWork."""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from psycopg.pq import TransactionStatus

import kernel.tenant_uow as tenant_uow_module
from kernel.principal import AuthenticatedPrincipal
from kernel.tenant_command_runtime_bundle_selector import (
    CommandRuntimeBundleSelectionRefused,
    TrustedCommandRuntimeBundle,
)
from kernel.tenant_uow import (
    GovernedBatchRequest,
    TenantBoundaryError,
    TenantBoundaryOutcome,
    TenantUnitOfWork,
    TenantUnitOfWorkManager,
    _reset_tenant_connection,
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


class _ResetConnection:
    def __init__(self, *, error=None, restore_error=None):
        self.info = _Info()
        self._autocommit = False
        self.autocommit_assignments = []
        self.events = []
        self._error = error
        self._restore_error = restore_error

    @property
    def autocommit(self):
        return self._autocommit

    @autocommit.setter
    def autocommit(self, value):
        self.autocommit_assignments.append(value)
        if (
            value is False
            and self._autocommit is True
            and self._restore_error is not None
        ):
            raise self._restore_error
        self._autocommit = value

    def execute(self, query, *, prepare):
        self.events.append((query, prepare, self.autocommit))
        if self._error is not None:
            raise self._error
        return _Cursor()


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
        replacement = replace(unit.binding, tenant_id=uuid4())
        with pytest.raises(AttributeError):
            unit.binding = replacement
        with pytest.raises(AttributeError):
            del unit.binding
        assert unit.binding.tenant_id == principal.authority.tenant_id
        assert minter.challenges[0].audience == AUDIENCE
        batch = unit.begin_batch(request)
        assert batch.full_xid == 42
        assert batch.knowledge_position == 1
        assert batch.authenticated_principal_ref == principal.authority.party_ref
        with pytest.raises(RuntimeError, match="already exists"):
            unit.begin_batch(request)

    assert connection.events[-1] == ("COMMIT", ())
    assert not any(
        "take_tenant_write_lock" in query
        for query, _parameters in connection.events
    )
    assert pool.returned == [connection]
    with pytest.raises(RuntimeError, match="closed"):
        unit.begin_batch(request)
    with pytest.raises(RuntimeError, match="closed"):
        unit._TenantUnitOfWork__allocate_batch(request)


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


def test_sql_surface_is_absent_and_later_refusal_rolls_back(principal):
    connection = _Connection(principal)
    manager = TenantUnitOfWorkManager(_Pool(connection), _Minter())
    request = GovernedBatchRequest(
        "batch-hostile-sql",
        "TEST_OPERATION",
        "request-hostile-sql",
        "sha256:" + "7" * 64,
    )
    hostile_sql = (
        "/* repository operation */ COMMIT",
        "-- repository operation\nROLLBACK",
        "PREPARE TRANSACTION 'uow_escape'",
        "SET SESSION statement_timeout = 0",
        "SELECT pg_advisory_lock(42)",
    )

    assert {
        "execute",
        "fetch_one",
        "fetch_all",
        "savepoint",
    }.isdisjoint(TenantUnitOfWork.__dict__)

    with pytest.raises(RuntimeError, match="later governed stage refused"):
        with manager.unit_of_work(principal) as unit:
            assert {name for name in dir(unit) if not name.startswith("_")} == {
                "batch",
                "begin_batch",
                "binding",
                "resolve_commit_operation_claim_draft_runtime_bundle",
            }
            assert not hasattr(unit, "__dict__")
            assert not hasattr(unit, "_connection")
            unit.begin_batch(request)
            for query in hostile_sql:
                with pytest.raises(AttributeError):
                    getattr(unit, "execute")(query)
            raise RuntimeError("later governed stage refused")

    executed = tuple(query for query, _parameters in connection.events)
    assert all(query not in executed for query in hostile_sql)
    assert connection.events[-1] == ("ROLLBACK", ())


def _trusted_token() -> TrustedCommandRuntimeBundle:
    return object.__new__(TrustedCommandRuntimeBundle)


def test_runtime_bundle_resolution_is_cached_by_identity_and_closes(
    principal,
    monkeypatch,
):
    connection = _Connection(principal)
    manager = TenantUnitOfWorkManager(_Pool(connection), _Minter())
    expected = _trusted_token()
    calls = []

    def resolve(_connection, tenant_id):
        calls.append(tenant_id)
        return expected

    monkeypatch.setattr(
        tenant_uow_module,
        "_resolve_commit_operation_claim_draft_runtime_bundle",
        resolve,
    )
    with manager.unit_of_work(principal) as unit:
        first = unit.resolve_commit_operation_claim_draft_runtime_bundle()
        second = unit.resolve_commit_operation_claim_draft_runtime_bundle()
        assert first is expected and second is first

    assert calls == [principal.authority.tenant_id]
    assert connection.events[-1] == ("COMMIT", ())
    with pytest.raises(RuntimeError, match="closed"):
        unit.resolve_commit_operation_claim_draft_runtime_bundle()


def test_caught_selector_refusal_is_terminal_and_forces_rollback(
    principal,
    monkeypatch,
):
    connection = _Connection(principal)
    manager = TenantUnitOfWorkManager(_Pool(connection), _Minter())
    calls = []

    def refuse(_connection, tenant_id):
        calls.append(tenant_id)
        raise CommandRuntimeBundleSelectionRefused

    monkeypatch.setattr(
        tenant_uow_module,
        "_resolve_commit_operation_claim_draft_runtime_bundle",
        refuse,
    )
    with manager.unit_of_work(principal) as unit:
        for _attempt in range(2):
            with pytest.raises(CommandRuntimeBundleSelectionRefused) as raised:
                unit.resolve_commit_operation_claim_draft_runtime_bundle()
            assert raised.value.outcome == (
                "RUNTIME_BUNDLE_SELECTION_REFUSED_NO_WRITE"
            )
            assert raised.value.__cause__ is None
        with pytest.raises(RuntimeError, match="rollback-only"):
            unit.begin_batch(
                GovernedBatchRequest(
                    "batch-fallback",
                    "TEST_OPERATION",
                    "request-fallback",
                    "sha256:" + "7" * 64,
                )
            )

    assert calls == [principal.authority.tenant_id]
    assert connection.events[-1] == ("ROLLBACK", ())


def test_caught_unexpected_selector_failure_still_forces_rollback(
    principal,
    monkeypatch,
):
    connection = _Connection(principal)
    manager = TenantUnitOfWorkManager(_Pool(connection), _Minter())
    failure = KeyboardInterrupt()

    def crash(_connection, _tenant_id):
        raise failure

    monkeypatch.setattr(
        tenant_uow_module,
        "_resolve_commit_operation_claim_draft_runtime_bundle",
        crash,
    )
    with manager.unit_of_work(principal) as unit:
        with pytest.raises(KeyboardInterrupt) as raised:
            unit.resolve_commit_operation_claim_draft_runtime_bundle()
        assert raised.value is failure

    assert connection.events[-1] == ("ROLLBACK", ())


def test_resolver_after_batch_and_reentrant_resolution_refuse(
    principal,
    monkeypatch,
):
    connection = _Connection(principal)
    manager = TenantUnitOfWorkManager(_Pool(connection), _Minter())
    unit_holder = []

    def reenter(_connection, _tenant_id):
        return unit_holder[0].resolve_commit_operation_claim_draft_runtime_bundle()

    monkeypatch.setattr(
        tenant_uow_module,
        "_resolve_commit_operation_claim_draft_runtime_bundle",
        reenter,
    )
    with manager.unit_of_work(principal) as unit:
        unit_holder.append(unit)
        with pytest.raises(CommandRuntimeBundleSelectionRefused):
            unit.resolve_commit_operation_claim_draft_runtime_bundle()
    assert connection.events[-1] == ("ROLLBACK", ())

    connection = _Connection(principal)
    manager = TenantUnitOfWorkManager(_Pool(connection), _Minter())
    with manager.unit_of_work(principal) as unit:
        unit.begin_batch(
            GovernedBatchRequest(
                "batch-before-selector",
                "TEST_OPERATION",
                "request-before-selector",
                "sha256:" + "7" * 64,
            )
        )
        with pytest.raises(CommandRuntimeBundleSelectionRefused):
            unit.resolve_commit_operation_claim_draft_runtime_bundle()
    assert connection.events[-1] == ("ROLLBACK", ())


def test_pool_reset_discards_all_session_state_outside_a_transaction():
    connection = _ResetConnection()

    _reset_tenant_connection(connection)

    assert connection.events == [("DISCARD ALL", False, True)]
    assert connection.autocommit is False
    assert connection.info.transaction_status == TransactionStatus.IDLE


def test_pool_reset_failure_is_not_hidden_and_restores_client_mode():
    failure = OSError("reset reply lost")
    connection = _ResetConnection(error=failure)

    with pytest.raises(OSError) as raised:
        _reset_tenant_connection(connection)

    assert raised.value is failure
    assert connection.events == [("DISCARD ALL", False, True)]
    assert connection.autocommit is False


def test_pool_reset_preserves_failure_when_client_mode_restore_also_fails():
    reset_failure = OSError("reset reply lost")
    restore_failure = RuntimeError("client mode restore refused")
    connection = _ResetConnection(
        error=reset_failure,
        restore_error=restore_failure,
    )

    with pytest.raises(OSError) as raised:
        _reset_tenant_connection(connection)

    assert raised.value is reset_failure
    assert connection.autocommit_assignments == [True, False]
    assert connection.autocommit is True


@pytest.mark.parametrize(
    ("transaction_status", "autocommit"),
    (
        (TransactionStatus.INTRANS, False),
        (TransactionStatus.IDLE, True),
    ),
    ids=("transaction-active", "autocommit-enabled"),
)
def test_pool_reset_refuses_an_invalid_starting_state(
    transaction_status,
    autocommit,
):
    connection = _ResetConnection()
    connection.info.transaction_status = transaction_status
    connection.autocommit = autocommit

    with pytest.raises(RuntimeError, match="not resettable"):
        _reset_tenant_connection(connection)

    assert connection.events == []
