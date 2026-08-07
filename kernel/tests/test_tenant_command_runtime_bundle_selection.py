"""Closed adapter tests for tenant command RuntimeBundle selection."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus

import conformance.rewrite_architecture_check as architecture
import deployment.postgresql.tenant_command_runtime_bundle_selection as selection
from kernel.runtime_bundle import (
    Canonicalization,
    ContentPlacement,
    RuntimeBundle,
    RuntimeComponent,
    RuntimeComponentRole,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
BINDING_PATH = (
    PACKAGE_ROOT / "contracts/candidates/temporal_runtime_bundle_selection/"
    "OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json"
)


def _valid_bundle() -> RuntimeBundle:
    binding = json.loads(BINDING_PATH.read_bytes())
    components = []
    for row in binding["requiredComponentClosure"]["components"]:
        components.append(
            RuntimeComponent.from_selected_bytes(
                role=RuntimeComponentRole(row["role"]),
                logical_ref=row["identity"],
                canonicalization=Canonicalization(row["canonicalization"]),
                placement=ContentPlacement(row["placement"]),
                selected_bytes=(PACKAGE_ROOT / row["sourcePath"]).read_bytes(),
            )
        )
    return RuntimeBundle.create(components)


class _Cursor:
    def __init__(self, rows: list[object]):
        self._rows = iter(rows)

    def fetchone(self) -> object | None:
        return next(self._rows, None)


class _Connection:
    def __init__(
        self,
        rows: list[object] | None = None,
        *,
        status: TransactionStatus = TransactionStatus.INTRANS,
        failure: Exception | None = None,
    ) -> None:
        self.info = SimpleNamespace(transaction_status=status)
        self.rows = rows or []
        self.failure = failure
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, statement: str, parameters: tuple[str, ...]) -> _Cursor:
        self.calls.append((statement, parameters))
        if self.failure is not None:
            raise self.failure
        return _Cursor(self.rows)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_exact_fixed_closure_is_valid_and_caller_cannot_select_authority() -> None:
    bundle = _valid_bundle()

    assert (
        selection.validate_commit_operation_claim_draft_runtime_bundle(bundle)
        == bundle.digest
    )
    assert tuple(
        inspect.signature(
            selection.activate_commit_operation_claim_draft_runtime_bundle_selection
        ).parameters
    ) == ("connection", "runtime_bundle")
    assert (
        "tenant"
        not in inspect.signature(
            selection.activate_commit_operation_claim_draft_runtime_bundle_selection
        ).parameters
    )
    assert (
        "principal"
        not in inspect.signature(
            selection.activate_commit_operation_claim_draft_runtime_bundle_selection
        ).parameters
    )


def test_missing_command_required_component_refuses_before_sql() -> None:
    bundle = _valid_bundle()
    incomplete = RuntimeBundle.create(
        component
        for component in bundle.components
        if component.logical_ref != "contract:ofarm.runtimeproblem.v0.1"
    )
    connection = _Connection()

    with pytest.raises(
        selection.TenantCommandRuntimeBundleSelectionError,
        match="command-required component differs",
    ):
        selection.activate_commit_operation_claim_draft_runtime_bundle_selection(
            connection, incomplete
        )

    assert connection.calls == []
    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_pinned_binding_byte_change_refuses_before_sql(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed = tmp_path / "changed-selection-binding.json"
    changed.write_bytes(BINDING_PATH.read_bytes() + b" ")
    monkeypatch.setattr(selection, "_SELECTION_BINDING_PATH", changed)
    connection = _Connection()

    with pytest.raises(
        selection.TenantCommandRuntimeBundleSelectionError,
        match="binding bytes differ",
    ):
        selection.activate_commit_operation_claim_draft_runtime_bundle_selection(
            connection, _valid_bundle()
        )

    assert connection.calls == []
    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_activation_passes_only_digest_and_commits_one_exact_result() -> None:
    bundle = _valid_bundle()
    connection = _Connection(
        [
            (
                "selection-batch:3d49af8e-cd73-4d8a-98af-31f8ff8ac361",
                7,
                bundle.digest,
            )
        ]
    )

    result = selection.activate_commit_operation_claim_draft_runtime_bundle_selection(
        connection, bundle
    )

    assert connection.calls == [(selection._ACTIVATION_SQL, (bundle.digest,))]
    assert result == selection.TenantCommandRuntimeBundleSelection(
        selection_batch_id=("selection-batch:3d49af8e-cd73-4d8a-98af-31f8ff8ac361"),
        selection_knowledge_position=7,
        runtime_bundle_digest=bundle.digest,
    )
    assert connection.commits == 1
    assert connection.rollbacks == 0


@pytest.mark.parametrize(
    "rows",
    (
        [],
        [("selection-batch:not-a-uuid", 7, "sha256:" + "a" * 64)],
        [
            (
                "selection-batch:3d49af8e-cd73-4d8a-98af-31f8ff8ac361",
                0,
                "sha256:" + "a" * 64,
            )
        ],
        [
            (
                "selection-batch:3d49af8e-cd73-4d8a-98af-31f8ff8ac361",
                7,
                "sha256:" + "a" * 64,
            ),
            ("unexpected", 8, "sha256:" + "b" * 64),
        ],
    ),
)
def test_invalid_database_result_rolls_back(rows: list[object]) -> None:
    connection = _Connection(rows)

    with pytest.raises(selection.TenantCommandRuntimeBundleSelectionError):
        selection.activate_commit_operation_claim_draft_runtime_bundle_selection(
            connection, _valid_bundle()
        )

    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_database_refusal_rolls_back_without_translation() -> None:
    refusal = RuntimeError("database refusal")
    connection = _Connection(failure=refusal)

    with pytest.raises(RuntimeError, match="database refusal") as raised:
        selection.activate_commit_operation_claim_draft_runtime_bundle_selection(
            connection, _valid_bundle()
        )

    assert raised.value is refusal
    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_unbound_connection_refuses_without_sql_or_transaction_end() -> None:
    connection = _Connection(status=TransactionStatus.IDLE)

    with pytest.raises(
        selection.TenantCommandRuntimeBundleSelectionError,
        match="already bound active transaction",
    ):
        selection.activate_commit_operation_claim_draft_runtime_bundle_selection(
            connection, _valid_bundle()
        )

    assert connection.calls == []
    assert connection.commits == 0
    assert connection.rollbacks == 0


def test_adapter_is_absent_from_production_and_legacy_import_closures() -> None:
    snapshot = architecture.build_python_source_snapshot(PACKAGE_ROOT)
    module = "deployment.postgresql.tenant_command_runtime_bundle_selection"

    assert module not in snapshot.production_reachability
    assert module not in snapshot.legacy_reachability
