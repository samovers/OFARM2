"""Submit selection lifecycle on a real unit using isolated reader results."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from kernel import tenant_uow
from kernel.tenant_command_runtime_bundle_selector import CommandRuntimeBundleSelectionRefused
from kernel.tenant_submit_runtime_bundle_selector import TrustedAssertOperationClaimRuntimeBundle
from kernel.tenant_uow import (
    GovernedBatchRequest, TenantBoundaryError, TenantBoundaryOutcome, TenantUnitOfWorkManager,
)
from kernel.tests.test_tenant_uow import (
    _Connection, _Minter, _Pool, _trusted_token, principal as principal,
)


def _submit_token():
    # The unit only holds this opaque value. Verifier tests exercise its construction.
    return object.__new__(TrustedAssertOperationClaimRuntimeBundle)


@pytest.fixture
def readers(monkeypatch):
    submit = Mock(side_effect=lambda *_: _submit_token())
    draft = Mock(side_effect=lambda *_: _trusted_token())
    monkeypatch.setattr(tenant_uow, "_resolve_assert_operation_claim_runtime_bundle", submit)
    monkeypatch.setattr(tenant_uow, "_resolve_commit_operation_claim_draft_runtime_bundle", draft)
    return submit, draft


@pytest.fixture
def lease(principal):
    connection = _Connection(principal)
    return TenantUnitOfWorkManager(_Pool(connection), _Minter()), connection


REQUEST = GovernedBatchRequest(
    "batch-submit", "ASSERT_OPERATION_CLAIM", "request-submit", "sha256:" + "7" * 64,
)


def test_submit_cached_only_on_this_lease_even_when_backend_reused(principal, lease, readers, monkeypatch):
    manager, connection = lease
    submit, draft = readers
    original_allocator = tenant_uow._allocate_governed_batch

    def allocate(*args):
        assert unit._selected_assert_operation_claim_runtime_bundle() is selected
        return original_allocator(*args)

    monkeypatch.setattr(tenant_uow, "_allocate_governed_batch", allocate)
    with manager.unit_of_work(principal) as unit:
        assert unit._selected_assert_operation_claim_runtime_bundle() is None
        selected = unit.resolve_assert_operation_claim_runtime_bundle()
        event_count = len(connection.events)
        assert unit.resolve_assert_operation_claim_runtime_bundle() is selected
        assert unit._selected_assert_operation_claim_runtime_bundle() is selected
        assert len(connection.events) == event_count
        submit.assert_called_once_with(connection, unit.binding.tenant_id)
        unit.begin_batch(REQUEST)
        event_count = len(connection.events)
        assert unit._selected_assert_operation_claim_runtime_bundle() is selected
        assert len(connection.events) == event_count

    with manager.unit_of_work(principal) as fresh:
        assert unit._selected_assert_operation_claim_runtime_bundle() is None
        with pytest.raises(RuntimeError, match="closed"):
            unit.resolve_assert_operation_claim_runtime_bundle()
        assert fresh._selected_assert_operation_claim_runtime_bundle() is None
        assert fresh.resolve_assert_operation_claim_runtime_bundle() is not selected
    assert submit.call_count == 2
    draft.assert_not_called()


@pytest.mark.parametrize("submit_first", (False, True))
def test_switching_commands_refuses_without_second_read(principal, lease, readers, submit_first):
    manager, connection = lease
    submit, draft = readers
    with pytest.raises(TenantBoundaryError) as failed:
        with manager.unit_of_work(principal) as unit:
            if submit_first:
                unit.resolve_assert_operation_claim_runtime_bundle()
                switch = unit.resolve_commit_operation_claim_draft_runtime_bundle
            else:
                unit.resolve_commit_operation_claim_draft_runtime_bundle()
                assert unit._selected_assert_operation_claim_runtime_bundle() is None
                switch = unit.resolve_assert_operation_claim_runtime_bundle
            with pytest.raises(CommandRuntimeBundleSelectionRefused):
                switch()
            assert unit._selected_assert_operation_claim_runtime_bundle() is None
            with pytest.raises(RuntimeError, match="rollback-only"):
                unit.begin_batch(REQUEST)
            assert unit.batch is None
    assert (submit.call_count, draft.call_count) == ((1, 0) if submit_first else (0, 1))
    assert failed.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert connection.events[-1] == ("ROLLBACK", ())


@pytest.mark.parametrize("resolved_first", (False, True))
def test_submit_after_batch_refuses_without_reader(principal, lease, readers, resolved_first):
    manager, connection = lease
    submit, _ = readers
    with pytest.raises(TenantBoundaryError) as failed:
        with manager.unit_of_work(principal) as unit:
            if resolved_first:
                unit.resolve_assert_operation_claim_runtime_bundle()
            unit.begin_batch(REQUEST)
            with pytest.raises(CommandRuntimeBundleSelectionRefused):
                unit.resolve_assert_operation_claim_runtime_bundle()
            assert unit._selected_assert_operation_claim_runtime_bundle() is None
    assert submit.call_count == int(resolved_first)
    assert failed.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    assert connection.events[-1] == ("ROLLBACK", ())


def test_submit_ignores_foreign_thread_without_affecting_owning_unit(principal, lease, readers):
    manager, _ = lease
    submit, _ = readers
    with manager.unit_of_work(principal) as unit, ThreadPoolExecutor(max_workers=1) as thread:
        with pytest.raises(CommandRuntimeBundleSelectionRefused):
            thread.submit(unit.resolve_assert_operation_claim_runtime_bundle).result()
        submit.assert_not_called()
        selected = unit.resolve_assert_operation_claim_runtime_bundle()
        assert thread.submit(unit._selected_assert_operation_claim_runtime_bundle).result() is None
        with pytest.raises(CommandRuntimeBundleSelectionRefused):
            thread.submit(unit.resolve_assert_operation_claim_runtime_bundle).result()
        assert unit.resolve_assert_operation_claim_runtime_bundle() is selected
    assert submit.call_count == 1


def test_another_failure_hides_a_previously_verified_choice(principal, lease, readers):
    manager, _ = lease
    submit, _ = readers
    with pytest.raises(TenantBoundaryError) as failed:
        with manager.unit_of_work(principal) as unit:
            unit.resolve_assert_operation_claim_runtime_bundle()
            with pytest.raises(RuntimeError, match="requires an active governed batch"):
                unit.stage_operation_claim(None)
            assert unit._selected_assert_operation_claim_runtime_bundle() is None
            with pytest.raises(CommandRuntimeBundleSelectionRefused):
                unit.resolve_assert_operation_claim_runtime_bundle()
    assert submit.call_count == 1
    assert failed.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED


@pytest.mark.parametrize("during_read", ("submit-again", "try-draft", "allocate", "latch"))
def test_submit_publishes_only_after_rechecking_unit_state(principal, lease, readers, during_read):
    manager, connection = lease
    submit, draft = readers
    with pytest.raises(TenantBoundaryError) as failed:
        with manager.unit_of_work(principal) as unit:
            def resolve(_connection, _tenant):
                assert unit._selected_assert_operation_claim_runtime_bundle() is None
                if during_read == "allocate":
                    unit.begin_batch(REQUEST)
                elif during_read == "latch":
                    with pytest.raises(RuntimeError, match="requires an active governed batch"):
                        unit.stage_operation_claim(None)
                else:
                    with pytest.raises(CommandRuntimeBundleSelectionRefused):
                        if during_read == "try-draft":
                            unit.resolve_commit_operation_claim_draft_runtime_bundle()
                        else:
                            unit.resolve_assert_operation_claim_runtime_bundle()
                return _submit_token()

            submit.side_effect = resolve
            with pytest.raises(CommandRuntimeBundleSelectionRefused):
                unit.resolve_assert_operation_claim_runtime_bundle()
            assert unit._selected_assert_operation_claim_runtime_bundle() is None
            with pytest.raises(RuntimeError, match="rollback-only"):
                unit.begin_batch(REQUEST)
    assert failed.value.outcome is TenantBoundaryOutcome.TRANSACTION_FAILED
    submit.assert_called_once()
    draft.assert_not_called()
    assert connection.events[-1] == ("ROLLBACK", ())
