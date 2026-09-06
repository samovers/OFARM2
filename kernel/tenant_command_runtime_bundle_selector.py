"""Tenant-bound read of one fixed command RuntimeBundle selection."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import jsonschema
import psycopg

from .runtime_bundle import (
    BUNDLE_SCHEMA_VERSION, Canonicalization, ContentPlacement, RuntimeBundle,
    RuntimeBundleError, RuntimeComponent, RuntimeComponentRole,
    canonical_json_bytes, sha256_bytes, strict_json_document,
)

Connection = psycopg.Connection[tuple[object, ...]]
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
_MAX_KNOWLEDGE_POSITION, _MAX_COMPONENTS = 9_007_199_254_740_991, 4_096
_MAX_COMPONENT_BYTES = 134_217_728
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_TENANT_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/#-]{0,1023}")
_BATCH_ID = re.compile(
    r"selection-batch:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)

_SELECTION_SQL = (
    "SELECT * FROM "
    "ofarm.resolve_commit_operation_claim_draft_runtime_bundle_selection()"
)
_BUNDLE_SQL = """
    SELECT tenant_id, bundle_digest::pg_catalog.text,
           bundle_ref::pg_catalog.text, canonical_bytes, byte_length
    FROM ofarm.runtime_bundle
    WHERE tenant_id = %s AND bundle_digest::pg_catalog.text = %s
"""
_MEMBERSHIP_SQL = """
    SELECT tenant_id, bundle_digest::pg_catalog.text, component_role,
           logical_ref::pg_catalog.text, canonicalization, content_placement,
           global_content_digest::pg_catalog.text,
           tenant_content_digest::pg_catalog.text, byte_length
    FROM ofarm.runtime_bundle_component
    WHERE tenant_id = %s AND bundle_digest::pg_catalog.text = %s
    ORDER BY component_role COLLATE pg_catalog."C",
             logical_ref::pg_catalog.text COLLATE pg_catalog."C"
"""
_CONTENT_SQL = """
    SELECT component.component_role, component.logical_ref::pg_catalog.text,
           global_blob.canonical_bytes, tenant_blob.canonical_bytes
    FROM ofarm.runtime_bundle_component AS component
    LEFT JOIN ofarm.runtime_content_blob AS global_blob
      ON global_blob.content_digest = component.global_content_digest
     AND global_blob.byte_length = component.byte_length
    LEFT JOIN ofarm.runtime_tenant_content_blob AS tenant_blob
      ON tenant_blob.tenant_id = component.tenant_id
     AND tenant_blob.content_digest = component.tenant_content_digest
     AND tenant_blob.byte_length = component.byte_length
    WHERE component.tenant_id = %s
      AND component.bundle_digest::pg_catalog.text = %s
    ORDER BY component.component_role COLLATE pg_catalog."C",
             component.logical_ref::pg_catalog.text COLLATE pg_catalog."C"
"""


class _InvalidSelection(RuntimeError):
    pass

class CommandRuntimeBundleSelectionRefused(RuntimeError):
    """One deliberately opaque internal refusal."""

    outcome = _REFUSAL_OUTCOME
    def __init__(self) -> None:
        super().__init__(_REFUSAL_OUTCOME)

def _require(condition: bool) -> None:
    if not condition:
        raise _InvalidSelection

def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()

def _read_pinned(path: Path, length: int, digest: str) -> bytes:
    value = path.read_bytes()
    _require(type(value) is bytes and len(value) == length and _sha256(value) == digest)
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
        and _sha256(canonical) == _SELECTION_BINDING_CANONICAL_DIGEST
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

def _rows(
    connection: Connection, statement: str, parameters: tuple[object, ...] = ()
) -> list[tuple[object, ...]]:
    rows = connection.execute(statement, parameters).fetchall()
    _require(type(rows) is list and all(type(row) is tuple for row in rows))
    return rows

def _one_row(
    connection: Connection, statement: str, parameters: tuple[object, ...] = ()
) -> tuple[object, ...]:
    rows = _rows(connection, statement, parameters)
    _require(len(rows) == 1)
    return rows[0]

def _fixed_text(value: object, expected: str) -> str:
    _require(type(value) is str and value == expected)
    return value

def _selection_authority(
    connection: Connection, tenant_id: UUID
) -> tuple[object, ...]:
    row = _one_row(connection, _SELECTION_SQL)
    _require(len(row) == 11 and type(tenant_id) is UUID and tenant_id.int != 0)
    _require(type(row[0]) is UUID and row[0] == tenant_id)
    _require(type(row[1]) is str and _TENANT_REF.fullmatch(row[1]) is not None)
    _fixed_text(row[2], _SELECTION_BINDING_ID)
    _fixed_text(row[3], _SELECTION_BINDING_CANONICAL_DIGEST)
    _fixed_text(row[4], _COMMAND_ID)
    _fixed_text(row[5], _COMMAND_BINDING_ID)
    _fixed_text(row[6], _COMMAND_BINDING_DIGEST)
    _require(type(row[7]) is str and _BATCH_ID.fullmatch(row[7]) is not None)
    _require(
        type(row[8]) is int
        and type(row[10]) is int
        and 1 <= row[8] <= row[10] <= _MAX_KNOWLEDGE_POSITION
    )
    _require(type(row[9]) is str and _DIGEST.fullmatch(row[9]) is not None)
    return row

@dataclass(frozen=True, slots=True)
class _Membership:
    role: RuntimeComponentRole
    logical_ref: str
    canonicalization: Canonicalization
    placement: ContentPlacement
    content_digest: str
    byte_length: int

    def identity_document(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "logicalRef": self.logical_ref,
            "canonicalization": self.canonicalization.value,
            "placement": self.placement.value,
            "contentDigest": self.content_digest,
            "byteLength": self.byte_length,
        }

def _membership(
    connection: Connection, tenant_id: UUID, digest: str
) -> tuple[_Membership, ...]:
    rows = _rows(connection, _MEMBERSHIP_SQL, (tenant_id, digest))
    _require(1 <= len(rows) <= _MAX_COMPONENTS)
    result: list[_Membership] = []
    total = 0
    previous: tuple[str, str] | None = None
    for row in rows:
        _require(len(row) == 9 and row[0] == tenant_id and row[1] == digest)
        _require(all(type(row[index]) is str for index in (2, 3, 4, 5)))
        try:
            role = RuntimeComponentRole(row[2])
            canonicalization = Canonicalization(row[4])
            placement = ContentPlacement(row[5])
        except ValueError as exc:
            raise _InvalidSelection from exc
        global_digest, tenant_digest, byte_length = row[6:]
        if placement is ContentPlacement.GLOBAL:
            chosen, other = global_digest, tenant_digest
        else:
            chosen, other = tenant_digest, global_digest
        _require(
            type(chosen) is str
            and _DIGEST.fullmatch(chosen) is not None
            and other is None
            and type(byte_length) is int
            and byte_length >= 0
        )
        key = (role.value, row[3])
        _require(previous is None or previous < key)
        previous = key
        total += byte_length
        _require(total <= _MAX_COMPONENT_BYTES)
        result.append(
            _Membership(role, row[3], canonicalization, placement, chosen, byte_length)
        )
    return tuple(result)

def _load_bundle(
    connection: Connection, tenant_id: UUID, digest: str
) -> RuntimeBundle:
    row = _one_row(connection, _BUNDLE_SQL, (tenant_id, digest))
    _require(len(row) == 5 and type(row[0]) is UUID and row[0] == tenant_id)
    _require(type(row[1]) is str and row[1] == digest)
    _require(type(row[2]) is str and row[2] == f"runtimebundle:{digest}")
    _require(type(row[3]) is bytes and type(row[4]) is int and row[4] == len(row[3]))
    _require(sha256_bytes(row[3]) == digest)
    membership = _membership(connection, tenant_id, digest)
    expected_document = canonical_json_bytes(
        {
            "schemaVersion": BUNDLE_SCHEMA_VERSION,
            "canonicalization": Canonicalization.CANONICAL_JSON.value,
            "components": [item.identity_document() for item in membership],
        }
    )
    _require(row[3] == expected_document)
    content_rows = _rows(connection, _CONTENT_SQL, (tenant_id, digest))
    _require(len(content_rows) == len(membership))
    components: list[RuntimeComponent] = []
    for item, content_row in zip(membership, content_rows, strict=True):
        _require(
            len(content_row) == 4
            and content_row[:2] == (item.role.value, item.logical_ref)
        )
        global_bytes, tenant_bytes = content_row[2:]
        if item.placement is ContentPlacement.GLOBAL:
            selected, other = global_bytes, tenant_bytes
        else:
            selected, other = tenant_bytes, global_bytes
        _require(
            type(selected) is bytes
            and other is None
            and len(selected) == item.byte_length
            and sha256_bytes(selected) == item.content_digest
        )
        components.append(
            RuntimeComponent.from_selected_bytes(
                role=item.role,
                logical_ref=item.logical_ref,
                canonicalization=item.canonicalization,
                placement=item.placement,
                selected_bytes=selected,
            )
        )
    bundle = RuntimeBundle.create(components)
    _require(bundle.digest == digest and bundle.canonical_document_bytes == row[3])
    return bundle

def _validate_closure(binding: dict[str, object], bundle: RuntimeBundle) -> None:
    closure = binding.get("requiredComponentClosure")
    rows = closure.get("components") if type(closure) is dict else None
    _require(
        type(rows) is list
        and closure.get("semantics") == "EXACT_COMMAND_REQUIRED_COMPONENT_SUBSET"
        and closure.get("componentCount") == 16
        and len(rows) == 16
    )
    selected = {(item.role.value, item.logical_ref): item for item in bundle.components}
    _require(len(selected) == len(bundle.components))
    required: set[tuple[str, str]] = set()
    for row in rows:
        _require(type(row) is dict)
        key = (row.get("role"), row.get("identity"))
        _require(all(type(value) is str for value in key) and key not in required)
        required.add(key)
    for row in rows:
        key = (row["role"], row["identity"])
        component = selected.get(key)
        _require(
            component is not None
            and component.canonicalization.value == row.get("canonicalization")
            and component.placement.value == row.get("placement")
            and component.byte_length == row.get("byteLength")
            and component.content_digest == row.get("contentDigest")
        )
        schema_identity = row.get("schemaIdentity")
        _require(
            schema_identity is None
            or type(schema_identity) is str
            and ("CONTRACT_SCHEMA", schema_identity) in required
        )

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
class TrustedCommandRuntimeBundle:
    tenant_id: UUID
    tenant_ref: str
    selection_binding_id: str
    selection_binding_canonical_digest: str
    command_id: str
    command_binding_id: str
    command_binding_canonical_digest: str
    selection_batch_id: str
    selection_knowledge_position: int
    selection_knowledge_cut: int
    runtime_bundle: RuntimeBundle
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise CommandRuntimeBundleSelectionRefused from None
    @property
    def runtime_bundle_digest(self) -> str:
        return self.runtime_bundle.digest
    @property
    def runtime_bundle_document(self) -> bytes:
        return self.runtime_bundle.canonical_document_bytes

    @classmethod
    def _create(
        cls, authority: tuple[object, ...], bundle: RuntimeBundle
    ) -> "TrustedCommandRuntimeBundle":
        value = object.__new__(cls)
        fields = (*authority[:9], authority[10], bundle)
        for name, item in zip(cls.__slots__, fields, strict=True):
            object.__setattr__(value, name, item)
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
