"""Closed control adapter for one tenant command RuntimeBundle selection.

This module is not imported by application or worker runtime code.  It accepts
an already validated production ``RuntimeBundle`` and an already tenant-bound
selection-control transaction, authenticates the fixed reviewed binding, and
passes only the complete RuntimeBundle digest to PostgreSQL.

Binding: ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
from psycopg.pq import TransactionStatus

from kernel.runtime_bundle import (
    RuntimeBundle,
    RuntimeBundleError,
    canonical_json_bytes,
    strict_json_document,
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_SELECTION_SCHEMA_PATH = (
    _PACKAGE_ROOT / "contracts/candidates/temporal_runtime_bundle_selection/"
    "OFARM_TenantCommandRuntimeBundleSelectionBinding_schema_v0_1.json"
)
_SELECTION_BINDING_PATH = (
    _PACKAGE_ROOT / "contracts/candidates/temporal_runtime_bundle_selection/"
    "OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json"
)
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
_ACTIVATION_SQL = (
    "SELECT selection_batch_id, selection_knowledge_position, "
    "runtime_bundle_digest FROM "
    "ofarm.activate_commit_operation_claim_draft_runtime_bundle_selection(%s)"
)
_BATCH_ID = re.compile(
    r"^selection-batch:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_MAX_KNOWLEDGE_POSITION = 9_007_199_254_740_991


class TenantCommandRuntimeBundleSelectionError(RuntimeError):
    """The fixed binding, bundle closure, transaction, or result was refused."""


@dataclass(frozen=True, slots=True)
class TenantCommandRuntimeBundleSelection:
    """The immutable selection returned by the closed database transition."""

    selection_batch_id: str
    selection_knowledge_position: int
    runtime_bundle_digest: str


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _read_pinned(path: Path, byte_length: int, digest: str, label: str) -> bytes:
    try:
        value = path.read_bytes()
    except OSError as exc:
        raise TenantCommandRuntimeBundleSelectionError(
            f"{label} is unavailable"
        ) from exc
    if len(value) != byte_length or _sha256(value) != digest:
        raise TenantCommandRuntimeBundleSelectionError(f"{label} bytes differ")
    return value


def _fixed_binding() -> dict[str, Any]:
    schema_bytes = _read_pinned(
        _SELECTION_SCHEMA_PATH,
        _SELECTION_SCHEMA_BYTES,
        _SELECTION_SCHEMA_DIGEST,
        "tenant command selection schema",
    )
    binding_bytes = _read_pinned(
        _SELECTION_BINDING_PATH,
        _SELECTION_BINDING_FILE_BYTES,
        _SELECTION_BINDING_FILE_DIGEST,
        "tenant command selection binding",
    )
    try:
        schema, _schema_canonical = strict_json_document(
            schema_bytes, "tenant command selection schema"
        )
        binding, binding_canonical = strict_json_document(
            binding_bytes, "tenant command selection binding"
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(
            schema,
            format_checker=jsonschema.FormatChecker(),
        ).validate(binding)
    except (RuntimeBundleError, jsonschema.exceptions.SchemaError) as exc:
        raise TenantCommandRuntimeBundleSelectionError(
            "tenant command selection schema is invalid"
        ) from exc
    except jsonschema.exceptions.ValidationError as exc:
        raise TenantCommandRuntimeBundleSelectionError(
            "tenant command selection binding fails its schema"
        ) from exc

    if (
        len(binding_canonical) != _SELECTION_BINDING_CANONICAL_BYTES
        or _sha256(binding_canonical) != _SELECTION_BINDING_CANONICAL_DIGEST
        or canonical_json_bytes(binding) != binding_canonical
        or binding.get("bindingId") != _SELECTION_BINDING_ID
        or binding.get("command")
        != {
            "commandId": _COMMAND_ID,
            "commandBindingId": _COMMAND_BINDING_ID,
            "commandBindingCanonicalDigest": _COMMAND_BINDING_DIGEST,
        }
    ):
        raise TenantCommandRuntimeBundleSelectionError(
            "tenant command selection binding authority differs"
        )
    return binding


def validate_commit_operation_claim_draft_runtime_bundle(
    runtime_bundle: RuntimeBundle,
) -> str:
    """Return the digest only after exact fixed-binding closure validation."""

    binding = _fixed_binding()
    if type(runtime_bundle) is not RuntimeBundle:
        raise TenantCommandRuntimeBundleSelectionError(
            "selection requires one validated production RuntimeBundle"
        )
    try:
        verified_bundle = RuntimeBundle(
            components=runtime_bundle.components,
            canonical_document_bytes=runtime_bundle.canonical_document_bytes,
            digest=runtime_bundle.digest,
        )
    except RuntimeBundleError as exc:
        raise TenantCommandRuntimeBundleSelectionError(
            "selected RuntimeBundle model is invalid"
        ) from exc

    closure = binding.get("requiredComponentClosure")
    rows = closure.get("components") if type(closure) is dict else None
    if type(rows) is not list or closure.get("componentCount") != 16 or len(rows) != 16:
        raise TenantCommandRuntimeBundleSelectionError(
            "tenant command selection component closure differs"
        )

    selected = {
        (component.role.value, component.logical_ref): component
        for component in verified_bundle.components
    }
    if len(selected) != len(verified_bundle.components):
        raise TenantCommandRuntimeBundleSelectionError(
            "selected RuntimeBundle component identity is ambiguous"
        )
    required: set[tuple[str, str]] = set()
    for row in rows:
        if type(row) is not dict:
            raise TenantCommandRuntimeBundleSelectionError(
                "tenant command selection component row is invalid"
            )
        key = (row.get("role"), row.get("identity"))
        if not all(type(value) is str for value in key) or key in required:
            raise TenantCommandRuntimeBundleSelectionError(
                "tenant command selection component identity differs"
            )
        required.add(key)
        component = selected.get(key)
        if component is None or (
            component.canonicalization.value != row.get("canonicalization")
            or component.placement.value != row.get("placement")
            or component.byte_length != row.get("byteLength")
            or component.content_digest != row.get("contentDigest")
        ):
            raise TenantCommandRuntimeBundleSelectionError(
                "selected RuntimeBundle command-required component differs"
            )
        schema_identity = row.get("schemaIdentity")
        if schema_identity is not None and (
            type(schema_identity) is not str
            or ("CONTRACT_SCHEMA", schema_identity) not in required
            and ("CONTRACT_SCHEMA", schema_identity)
            not in {
                (item.get("role"), item.get("identity"))
                for item in rows
                if type(item) is dict
            }
        ):
            raise TenantCommandRuntimeBundleSelectionError(
                "temporal governance schema relationship differs"
            )

    return verified_bundle.digest


def activate_commit_operation_claim_draft_runtime_bundle_selection(
    connection: Any,
    runtime_bundle: RuntimeBundle,
) -> TenantCommandRuntimeBundleSelection:
    """Execute one closed transition and immediately end the bound transaction."""

    try:
        status = connection.info.transaction_status
    except AttributeError as exc:
        raise TenantCommandRuntimeBundleSelectionError(
            "selection requires a PostgreSQL connection"
        ) from exc
    if status != TransactionStatus.INTRANS:
        raise TenantCommandRuntimeBundleSelectionError(
            "selection requires an already bound active transaction"
        )

    try:
        digest = validate_commit_operation_claim_draft_runtime_bundle(runtime_bundle)
        cursor = connection.execute(_ACTIVATION_SQL, (digest,))
        row = cursor.fetchone()
        if row is None or cursor.fetchone() is not None:
            raise TenantCommandRuntimeBundleSelectionError(
                "selection activation returned an invalid row count"
            )
        if isinstance(row, dict):
            values = (
                row["selection_batch_id"],
                row["selection_knowledge_position"],
                row["runtime_bundle_digest"],
            )
        else:
            values = tuple(row)
        if len(values) != 3:
            raise TenantCommandRuntimeBundleSelectionError(
                "selection activation returned an invalid shape"
            )
        batch_id, position, returned_digest = values
        if (
            type(batch_id) is not str
            or _BATCH_ID.fullmatch(batch_id) is None
            or type(position) is not int
            or isinstance(position, bool)
            or not 1 <= position <= _MAX_KNOWLEDGE_POSITION
            or returned_digest != digest
        ):
            raise TenantCommandRuntimeBundleSelectionError(
                "selection activation returned invalid authority"
            )
        result = TenantCommandRuntimeBundleSelection(
            selection_batch_id=batch_id,
            selection_knowledge_position=position,
            runtime_bundle_digest=returned_digest,
        )
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
