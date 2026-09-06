"""Focused unit evidence for the fixed production RuntimeBundle selector."""
from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

import kernel.tenant_command_runtime_bundle_selector as selector
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
TENANT_REF = "tenant:selector-unit"
BATCH_ID = "selection-batch:3d49af8e-cd73-4d8a-98af-31f8ff8ac361"


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
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, bundle: RuntimeBundle) -> None:
        self.tenant_id = uuid4()
        self.calls = []
        self.failure = None
        self.failure_at = None
        self.selection_rows = [
            (
                self.tenant_id,
                TENANT_REF,
                selector._SELECTION_BINDING_ID,
                selector._SELECTION_BINDING_CANONICAL_DIGEST,
                selector._COMMAND_ID,
                selector._COMMAND_BINDING_ID,
                selector._COMMAND_BINDING_DIGEST,
                BATCH_ID,
                4,
                bundle.digest,
                7,
            )
        ]
        self.bundle_rows = [
            (
                self.tenant_id,
                bundle.digest,
                bundle.bundle_ref,
                bundle.canonical_document_bytes,
                len(bundle.canonical_document_bytes),
            )
        ]
        self.membership_rows = []
        self.content_rows = []
        for component in bundle.components:
            is_global = component.placement is ContentPlacement.GLOBAL
            self.membership_rows.append(
                (
                    self.tenant_id,
                    bundle.digest,
                    component.role.value,
                    component.logical_ref,
                    component.canonicalization.value,
                    component.placement.value,
                    component.content_digest if is_global else None,
                    None if is_global else component.content_digest,
                    component.byte_length,
                )
            )
            self.content_rows.append(
                (
                    component.role.value,
                    component.logical_ref,
                    component.canonical_bytes if is_global else None,
                    None if is_global else component.canonical_bytes,
                )
            )

    def execute(self, statement, parameters=()):
        self.calls.append((statement, parameters))
        if self.failure is not None and (
            self.failure_at is None or len(self.calls) == self.failure_at + 1
        ):
            raise self.failure
        if statement == selector._SELECTION_SQL:
            return _Cursor(self.selection_rows)
        if statement == selector._BUNDLE_SQL:
            return _Cursor(self.bundle_rows)
        if statement == selector._MEMBERSHIP_SQL:
            return _Cursor(self.membership_rows)
        if statement == selector._CONTENT_SQL:
            return _Cursor(self.content_rows)
        raise AssertionError("selector issued an unknown statement")


def _resolve(connection: _Connection):
    return selector._resolve_commit_operation_claim_draft_runtime_bundle(
        connection, connection.tenant_id
    )


def _assert_opaque_refusal(connection: _Connection) -> None:
    with pytest.raises(selector.CommandRuntimeBundleSelectionRefused) as raised:
        _resolve(connection)
    assert raised.value.outcome == "RUNTIME_BUNDLE_SELECTION_REFUSED_NO_WRITE"
    assert str(raised.value) == "RUNTIME_BUNDLE_SELECTION_REFUSED_NO_WRITE"
    assert raised.value.__cause__ is None
    assert vars(raised.value) == {}


def test_exact_selection_reconstructs_one_immutable_trusted_result() -> None:
    expected = _valid_bundle()
    connection = _Connection(expected)

    result = _resolve(connection)

    assert result.tenant_id == connection.tenant_id
    assert result.tenant_ref == TENANT_REF
    assert result.selection_binding_id == selector._SELECTION_BINDING_ID
    assert result.selection_binding_canonical_digest == (
        selector._SELECTION_BINDING_CANONICAL_DIGEST
    )
    assert result.command_id == selector._COMMAND_ID
    assert result.command_binding_id == selector._COMMAND_BINDING_ID
    assert result.command_binding_canonical_digest == selector._COMMAND_BINDING_DIGEST
    assert result.selection_batch_id == BATCH_ID
    assert (result.selection_knowledge_position, result.selection_knowledge_cut) == (
        4,
        7,
    )
    assert result.runtime_bundle == expected
    assert result.runtime_bundle_digest == expected.digest
    assert result.runtime_bundle_document == expected.canonical_document_bytes
    assert [call[1] for call in connection.calls] == [
        (),
        (connection.tenant_id, expected.digest),
        (connection.tenant_id, expected.digest),
        (connection.tenant_id, expected.digest),
    ]
    assert all(
        token not in " ".join(statement.upper().split())
        for statement, _parameters in connection.calls
        for token in ("INSERT ", "UPDATE ", "DELETE ", "LOCK ", "NOTIFY ")
    )
    with pytest.raises(FrozenInstanceError):
        result.tenant_ref = "tenant:changed"


def test_success_carrier_has_exact_fields_and_no_public_constructor() -> None:
    assert tuple(field.name for field in fields(selector.TrustedCommandRuntimeBundle)) == (
        "tenant_id",
        "tenant_ref",
        "selection_binding_id",
        "selection_binding_canonical_digest",
        "command_id",
        "command_binding_id",
        "command_binding_canonical_digest",
        "selection_batch_id",
        "selection_knowledge_position",
        "selection_knowledge_cut",
        "runtime_bundle",
    )
    assert not hasattr(_resolve(_Connection(_valid_bundle())), "__dict__")
    with pytest.raises(selector.CommandRuntimeBundleSelectionRefused):
        selector.TrustedCommandRuntimeBundle()


@pytest.mark.parametrize(
    ("index", "value"),
    (
        (0, uuid4()),
        (1, ":tenant-bad"),
        (2, "other-selection-binding"),
        (3, "sha256:" + "0" * 64),
        (4, "OTHER_COMMAND"),
        (5, "other-command-binding"),
        (6, "sha256:" + "0" * 64),
        (7, "selection-batch:not-a-uuid"),
        (8, 0),
        (8, True),
        (9, "not-a-digest"),
        (10, 3),
        (10, 9_007_199_254_740_992),
    ),
)
def test_selection_authority_substitution_refuses(index, value) -> None:
    connection = _Connection(_valid_bundle())
    changed = list(connection.selection_rows[0])
    changed[index] = value
    connection.selection_rows = [tuple(changed)]
    _assert_opaque_refusal(connection)
    assert len(connection.calls) == 1


@pytest.mark.parametrize("row_count", (0, 2))
def test_absent_or_ambiguous_selection_refuses_without_retry(row_count) -> None:
    connection = _Connection(_valid_bundle())
    connection.selection_rows = connection.selection_rows * row_count
    _assert_opaque_refusal(connection)
    assert len(connection.calls) == 1


def test_tenant_reference_uses_the_exact_database_ascii_id_boundary() -> None:
    for tenant_ref in ("a", "tenant/selector#unit", "a" * 1024):
        connection = _Connection(_valid_bundle())
        changed = list(connection.selection_rows[0])
        changed[1] = tenant_ref
        connection.selection_rows = [tuple(changed)]
        assert _resolve(connection).tenant_ref == tenant_ref

    for tenant_ref in ("", ":tenant", "a" * 1025, "tenant-ä"):
        connection = _Connection(_valid_bundle())
        changed = list(connection.selection_rows[0])
        changed[1] = tenant_ref
        connection.selection_rows = [tuple(changed)]
        _assert_opaque_refusal(connection)


@pytest.mark.parametrize(
    ("index", "value"),
    (
        (0, uuid4()),
        (1, "sha256:" + "0" * 64),
        (2, "runtimebundle:sha256:" + "0" * 64),
        (3, b"{}"),
        (4, -1),
        (4, True),
    ),
)
def test_bundle_authority_substitution_refuses(index, value) -> None:
    connection = _Connection(_valid_bundle())
    changed = list(connection.bundle_rows[0])
    changed[index] = value
    connection.bundle_rows = [tuple(changed)]
    _assert_opaque_refusal(connection)


def test_empty_duplicate_oversized_and_malformed_membership_refuse() -> None:
    for mutation in ("empty", "duplicate", "too-many", "oversized", "role"):
        connection = _Connection(_valid_bundle())
        if mutation == "empty":
            connection.membership_rows = []
        elif mutation == "duplicate":
            connection.membership_rows.insert(1, connection.membership_rows[0])
        elif mutation == "too-many":
            connection.membership_rows = [connection.membership_rows[0]] * 4097
        else:
            changed = list(connection.membership_rows[0])
            if mutation == "oversized":
                changed[8] = 134_217_729
            else:
                changed[2] = "UNKNOWN_ROLE"
            connection.membership_rows[0] = tuple(changed)
        _assert_opaque_refusal(connection)
        assert not any(call[0] == selector._CONTENT_SQL for call in connection.calls)


@pytest.mark.parametrize("mutation", ("missing", "wrong-bytes", "two-sources", "order"))
def test_missing_or_unequal_retained_content_refuses(mutation) -> None:
    connection = _Connection(_valid_bundle())
    if mutation == "missing":
        connection.content_rows.pop()
    elif mutation == "wrong-bytes":
        changed = list(connection.content_rows[0])
        changed[2] = b"changed"
        connection.content_rows[0] = tuple(changed)
    elif mutation == "two-sources":
        changed = list(connection.content_rows[0])
        changed[3] = changed[2]
        connection.content_rows[0] = tuple(changed)
    else:
        connection.content_rows[0], connection.content_rows[1] = (
            connection.content_rows[1],
            connection.content_rows[0],
        )
    _assert_opaque_refusal(connection)


def test_incomplete_command_closure_refuses_but_valid_extra_is_inert() -> None:
    base = _valid_bundle()
    incomplete = RuntimeBundle.create(
        component
        for component in base.components
        if component.logical_ref != "contract:ofarm.runtimeproblem.v0.1"
    )
    _assert_opaque_refusal(_Connection(incomplete))

    extra = RuntimeComponent.from_selected_bytes(
        role=RuntimeComponentRole.REFERENCE_SOURCE,
        logical_ref="test:selector-unrelated-extra",
        canonicalization=Canonicalization.EXACT_BYTES,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=b"unrelated-extra",
    )
    extended = RuntimeBundle.create((*base.components, extra))
    result = _resolve(_Connection(extended))
    assert result.runtime_bundle == extended


@pytest.mark.parametrize("artifact", ("binding", "schema"))
def test_changed_pinned_artifact_refuses(
    artifact,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / f"changed-{artifact}.json"
    source = (
        selector._SELECTION_BINDING_PATH
        if artifact == "binding"
        else selector._SELECTION_SCHEMA_PATH
    )
    target.write_bytes(source.read_bytes() + b" ")
    monkeypatch.setattr(
        selector,
        "_SELECTION_BINDING_PATH" if artifact == "binding" else "_SELECTION_SCHEMA_PATH",
        target,
    )
    _assert_opaque_refusal(_Connection(_valid_bundle()))


@pytest.mark.parametrize(
    "failure_at",
    range(4),
    ids=("selection", "bundle", "membership", "content"),
)
def test_database_errors_normalize_at_every_read(failure_at: int) -> None:
    connection = _Connection(_valid_bundle())
    connection.failure = psycopg.OperationalError("sensitive database detail")
    connection.failure_at = failure_at
    _assert_opaque_refusal(connection)


def test_programming_failures_propagate() -> None:
    connection = _Connection(_valid_bundle())
    failure = AssertionError("programming defect")
    connection.failure = failure
    with pytest.raises(AssertionError) as raised:
        _resolve(connection)
    assert raised.value is failure


def test_private_resolver_accepts_only_connection_and_bound_tenant() -> None:
    assert tuple(
        inspect.signature(
            selector._resolve_commit_operation_claim_draft_runtime_bundle
        ).parameters
    ) == ("connection", "tenant_id")
    assert selector.__all__ == (
        "CommandRuntimeBundleSelectionRefused",
        "TrustedCommandRuntimeBundle",
    )
