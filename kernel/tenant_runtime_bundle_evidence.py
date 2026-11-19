"""Shared verification of governed selection rows and sealed tenant bundles."""
from __future__ import annotations

import re
from dataclasses import dataclass, fields
from typing import TypeVar
from uuid import UUID

import psycopg

from .runtime_bundle import (
    BUNDLE_SCHEMA_VERSION, Canonicalization, ContentPlacement, RuntimeBundle,
    RuntimeComponent, RuntimeComponentRole, canonical_json_bytes, sha256_bytes,
)

Connection = psycopg.Connection[tuple[object, ...]]
_MAX_KNOWLEDGE_POSITION, _MAX_COMPONENTS = 9_007_199_254_740_991, 4_096
_MAX_COMPONENT_BYTES = 134_217_728
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_TENANT_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/#-]{0,1023}")
_BATCH_ID = re.compile(
    r"selection-batch:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}"
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

def _require(condition: bool) -> None:
    if not condition:
        raise _InvalidSelection

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

def _read_selection_row(
    connection: Connection, statement: str, tenant_id: UUID
) -> tuple[object, ...]:
    row = _one_row(connection, statement)
    _require(len(row) == 11 and type(tenant_id) is UUID and tenant_id.int != 0)
    _require(type(row[0]) is UUID and row[0] == tenant_id)
    _require(type(row[1]) is str and _TENANT_REF.fullmatch(row[1]) is not None)
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

def _validate_component_subset(
    closure: object, bundle: RuntimeBundle, *, expected_count: int | None = None
) -> None:
    rows = closure.get("components") if type(closure) is dict else None
    _require(
        type(rows) is list
        and closure.get("semantics") == "EXACT_COMMAND_REQUIRED_COMPONENT_SUBSET"
        and type(closure.get("componentCount")) is int
        and closure["componentCount"] == len(rows)
        and 1 <= len(rows) <= _MAX_COMPONENTS
        and (expected_count is None or len(rows) == expected_count)
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
            and type(row.get("byteLength")) is int
            and component.byte_length == row["byteLength"]
            and component.content_digest == row.get("contentDigest")
        )
        schema_identity = row.get("schemaIdentity")
        _require(
            schema_identity is None
            or type(schema_identity) is str
            and ("CONTRACT_SCHEMA", schema_identity) in required
        )


@dataclass(frozen=True, slots=True, init=False)
class _SelectedBundle:
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

    @property
    def runtime_bundle_digest(self) -> str:
        return self.runtime_bundle.digest

    @property
    def runtime_bundle_document(self) -> bytes:
        return self.runtime_bundle.canonical_document_bytes


_Result = TypeVar("_Result", bound=_SelectedBundle)


def _from_verified_values(
    result_type: type[_Result], row: tuple[object, ...], bundle: RuntimeBundle, *details: object,
) -> _Result:
    value = object.__new__(result_type)
    values = (*row[:9], row[10], bundle, *details)
    for field, item in zip(fields(result_type), values, strict=True):
        object.__setattr__(value, field.name, item)
    return value
