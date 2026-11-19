"""Read the bound farm's fixed Submit choice before allocating a save batch."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import psycopg

from .runtime_bundle import RuntimeBundleError
from .tenant_claim_write_guard import SelectedClaimCommand
from .tenant_command_runtime_bundle_selector import CommandRuntimeBundleSelectionRefused
from .tenant_runtime_bundle_evidence import (
    Connection, _DIGEST, _InvalidSelection, _SelectedBundle, _from_verified_values, _load_bundle,
    _read_selection_row, _require, _validate_component_subset,
)

_SELECTION_SQL = "SELECT * FROM ofarm.resolve_submit_operation_claim_runtime_bundle_selection()"
_SELECTION_ID = "ofarm.tenant-command-runtime-bundle-selection.submit-operation-claim.v0.1"
_COMMAND = ("SUBMIT_OPERATION_CLAIM", "ofarm.submission-command.operation-claim.v0.2", "0.2")
_CommandBinding = tuple[str, str, str, str]


@dataclass(frozen=True, slots=True)
class _SelectionBinding:
    """Projection of the independently pinned #430 selection document."""

    binding_id: str
    digest: str
    command: _CommandBinding
    required_component_closure: dict[str, object]


@dataclass(frozen=True, slots=True)
class _IssuedSubmitRule:
    """Guard-facing fields from the release identified by #431's issued tuple."""

    command: _CommandBinding
    action: str
    intent_profile: str
    body_profile: str
    contract_id: str
    contract_version: str
    contract_digest: str
    result_schema: str
    result_schema_digest: str


def _admitted_submit_bindings() -> tuple[_SelectionBinding, _IssuedSubmitRule]:
    # Release handoff: pin #430's original selection and consume #431's verified
    # tuple. Check their referenced contract, intent, body pointer and result
    # bytes against the consumer agreement before projecting these fields.
    # Both releases and that compatibility evidence are still outstanding.
    raise CommandRuntimeBundleSelectionRefused


@dataclass(frozen=True, slots=True, init=False)
class TrustedAssertOperationClaimRuntimeBundle(_SelectedBundle):
    rule: _IssuedSubmitRule
    selected_claim_command: SelectedClaimCommand

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise CommandRuntimeBundleSelectionRefused

    @property
    def command_binding_version(self) -> str:
        return self.rule.command[2]


def _is_digest(value: object) -> bool:
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def _verified_command(
    row: tuple[object, ...], tenant_id: UUID, selection: _SelectionBinding, rule: _IssuedSubmitRule,
) -> SelectedClaimCommand:
    command = rule.command
    _require(
        type(command) is tuple and len(command) == 4 and command[:3] == _COMMAND
        and _is_digest(command[3]) and selection.command == command
        and selection.binding_id == _SELECTION_ID and _is_digest(selection.digest)
        and row[2:7] == (selection.binding_id, selection.digest, command[0], command[1], command[3])
    )
    _require(
        rule.intent_profile == "EI_OPERATION_ASSERTION_V0_2"
        and rule.body_profile == "OPERATION_CLAIM_BODY_V0_2"
        and _is_digest(rule.contract_digest) and _is_digest(rule.result_schema_digest)
    )
    try:
        selected = SelectedClaimCommand(
            tenant_id, rule.action, row[9], rule.contract_id, rule.contract_version,
            rule.contract_digest, rule.result_schema, rule.result_schema_digest,
        )
    except ValueError as exc:
        raise _InvalidSelection from exc
    _require(selected.matches_operation_claim_contract())
    return selected


def _resolve_assert_operation_claim_runtime_bundle(
    connection: Connection, tenant_id: UUID,
) -> TrustedAssertOperationClaimRuntimeBundle:
    try:
        row = _read_selection_row(connection, _SELECTION_SQL, tenant_id)
        selection, rule = _admitted_submit_bindings()
        selected = _verified_command(row, tenant_id, selection, rule)
        bundle = _load_bundle(connection, tenant_id, selected.bundle_digest)
        _require(bundle.selected_tenant_ref in (None, row[1]))
        _validate_component_subset(selection.required_component_closure, bundle)
        return _from_verified_values(
            TrustedAssertOperationClaimRuntimeBundle, row, bundle, rule, selected,
        )
    except (_InvalidSelection, RuntimeBundleError, psycopg.Error):
        raise CommandRuntimeBundleSelectionRefused from None
