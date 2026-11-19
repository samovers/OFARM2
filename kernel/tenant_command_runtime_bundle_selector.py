"""Tenant-bound read of the fixed Save draft RuntimeBundle selection."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import jsonschema
import psycopg

from .runtime_bundle import (
    RuntimeBundle, RuntimeBundleError, canonical_json_bytes, sha256_bytes, strict_json_document,
)
from .tenant_runtime_bundle_evidence import (
    Connection, _BATCH_ID, _MAX_KNOWLEDGE_POSITION, _TENANT_REF, _InvalidSelection,
    _SelectedBundle, _from_verified_values, _load_bundle, _read_selection_row, _require, _validate_component_subset,
)

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_BINDING_DIR = _PACKAGE_ROOT / "contracts/candidates/temporal_runtime_bundle_selection"
_SELECTION_SCHEMA_PATH = _BINDING_DIR / "OFARM_TenantCommandRuntimeBundleSelectionBinding_schema_v0_1.json"
_SELECTION_BINDING_PATH = _BINDING_DIR / "OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json"
_SELECTION_SCHEMA_BYTES = 17_252
_SELECTION_SCHEMA_DIGEST = (
    "sha256:56604a52465ffc027382e99dea96f2c9bc1bd2479cbaff30dec6bd39c08e6b3d"
)
_SELECTION_BINDING_FILE_BYTES = 15_993
_SELECTION_BINDING_FILE_DIGEST = (
    "sha256:1500ffbbfdf11207a6657848fce12618347f767578e55dc070bb282dc5775aac"
)
_SELECTION_BINDING_CANONICAL_BYTES = 13_287
_SELECTION_BINDING_CANONICAL_DIGEST = (
    "sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f"
)
_SELECTION_BINDING_ID = (
    "ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1"
)
_COMMAND_ID = "COMMIT_OPERATION_CLAIM_DRAFT"
_COMMAND_BINDING_ID = (
    "ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1"
)
_COMMAND_BINDING_DIGEST = (
    "sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1"
)
_REFUSAL_OUTCOME = "RUNTIME_BUNDLE_SELECTION_REFUSED_NO_WRITE"
_SELECTION_SQL = (
    "SELECT * FROM "
    "ofarm.resolve_commit_operation_claim_draft_runtime_bundle_selection()"
)


class CommandRuntimeBundleSelectionRefused(RuntimeError):
    """One deliberately opaque internal refusal."""

    outcome = _REFUSAL_OUTCOME
    def __init__(self) -> None:
        super().__init__(_REFUSAL_OUTCOME)

def _read_pinned(path: Path, length: int, digest: str) -> bytes:
    value = path.read_bytes()
    _require(type(value) is bytes and len(value) == length and sha256_bytes(value) == digest)
    return value

def _fixed_binding() -> dict[str, object]:
    schema_bytes = _read_pinned(
        _SELECTION_SCHEMA_PATH, _SELECTION_SCHEMA_BYTES, _SELECTION_SCHEMA_DIGEST
    )
    binding_bytes = _read_pinned(
        _SELECTION_BINDING_PATH,
        _SELECTION_BINDING_FILE_BYTES,
        _SELECTION_BINDING_FILE_DIGEST,
    )
    schema, _schema_canonical = strict_json_document(schema_bytes, "selection schema")
    binding, canonical = strict_json_document(binding_bytes, "selection binding")
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    ).validate(binding)
    _require(
        len(canonical) == _SELECTION_BINDING_CANONICAL_BYTES
        and sha256_bytes(canonical) == _SELECTION_BINDING_CANONICAL_DIGEST
        and canonical_json_bytes(binding) == canonical
        and binding.get("bindingId") == _SELECTION_BINDING_ID
        and binding.get("command")
        == {
            "commandId": _COMMAND_ID,
            "commandBindingId": _COMMAND_BINDING_ID,
            "commandBindingCanonicalDigest": _COMMAND_BINDING_DIGEST,
        }
    )
    return binding

def _fixed_text(value: object, expected: str) -> str:
    _require(type(value) is str and value == expected)
    return value

def _selection_authority(
    connection: Connection, tenant_id: UUID
) -> tuple[object, ...]:
    row = _read_selection_row(connection, _SELECTION_SQL, tenant_id)
    _fixed_text(row[2], _SELECTION_BINDING_ID)
    _fixed_text(row[3], _SELECTION_BINDING_CANONICAL_DIGEST)
    _fixed_text(row[4], _COMMAND_ID)
    _fixed_text(row[5], _COMMAND_BINDING_ID)
    _fixed_text(row[6], _COMMAND_BINDING_DIGEST)
    return row

def _validate_closure(binding: dict[str, object], bundle: RuntimeBundle) -> None:
    _validate_component_subset(binding.get("requiredComponentClosure"), bundle, expected_count=16)

def _validate_result(value: "TrustedCommandRuntimeBundle") -> None:
    _require(type(value.tenant_id) is UUID and value.tenant_id.int != 0)
    _require(
        type(value.tenant_ref) is str
        and _TENANT_REF.fullmatch(value.tenant_ref) is not None
    )
    _fixed_text(value.selection_binding_id, _SELECTION_BINDING_ID)
    _fixed_text(
        value.selection_binding_canonical_digest, _SELECTION_BINDING_CANONICAL_DIGEST
    )
    _fixed_text(value.command_id, _COMMAND_ID)
    _fixed_text(value.command_binding_id, _COMMAND_BINDING_ID)
    _fixed_text(value.command_binding_canonical_digest, _COMMAND_BINDING_DIGEST)
    _require(
        type(value.selection_batch_id) is str
        and _BATCH_ID.fullmatch(value.selection_batch_id) is not None
    )
    _require(
        type(value.selection_knowledge_position) is int
        and type(value.selection_knowledge_cut) is int
        and 1 <= value.selection_knowledge_position
        <= value.selection_knowledge_cut
        <= _MAX_KNOWLEDGE_POSITION
    )
    _require(type(value.runtime_bundle) is RuntimeBundle)
    verified = RuntimeBundle(
        components=value.runtime_bundle.components,
        canonical_document_bytes=value.runtime_bundle.canonical_document_bytes,
        digest=value.runtime_bundle.digest,
    )
    _require(verified.selected_tenant_ref in (None, value.tenant_ref))
    _validate_closure(_fixed_binding(), verified)

@dataclass(frozen=True, slots=True, init=False)
class TrustedCommandRuntimeBundle(_SelectedBundle):
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise CommandRuntimeBundleSelectionRefused from None

    @classmethod
    def _create(
        cls, authority: tuple[object, ...], bundle: RuntimeBundle
    ) -> "TrustedCommandRuntimeBundle":
        value = _from_verified_values(cls, authority, bundle)
        _validate_result(value)
        return value

def _resolve_commit_operation_claim_draft_runtime_bundle(
    connection: Connection,
    tenant_id: UUID,
) -> TrustedCommandRuntimeBundle:
    try:
        authority = _selection_authority(connection, tenant_id)
        bundle = _load_bundle(connection, tenant_id, authority[9])
        return TrustedCommandRuntimeBundle._create(authority, bundle)
    except CommandRuntimeBundleSelectionRefused:
        raise
    except (
        _InvalidSelection,
        OSError,
        psycopg.Error,
        RuntimeBundleError,
        jsonschema.exceptions.SchemaError,
        jsonschema.exceptions.ValidationError,
    ):
        raise CommandRuntimeBundleSelectionRefused from None

__all__ = ("CommandRuntimeBundleSelectionRefused", "TrustedCommandRuntimeBundle")
