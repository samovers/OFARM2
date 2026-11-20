"""Capture/import conversion and independent readback for a fictional manual claim.

Only fixture composition has the producer and revision store. A bound reader
can inspect one revision. Production capture retention and access are separate.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from threading import Lock
from uuid import UUID

import jsonschema

from .runtime_bundle import RuntimeBundleError, strict_json_document

MANUAL_MAPPING = "manual-operation-claim.v1"
_OPERATION = "ASSERT_OPERATION_CLAIM"
_NORMALIZED = "NORMALIZED_DRAFT"
_SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "contracts/kernel/OFARM_CommitIngressRequest_schema_v0_1.json"
)
_SCHEMA_SHA256 = "397ec3a61ed572b14f9916bc9e7b316ff48150c743c6b7aa2eab94a3be3e8ffc"
_WIRE_ID = re.compile(r"[A-Za-z0-9._:-]+")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class CaptureSelection:
    """Owner-selected revision and submission context, outside the caller's JSON."""

    tenant_id: UUID
    party_ref: str
    capture_id: str
    revision: int
    mapping_ref: str
    operation: str
    request_id: str
    ingested_at: str
    target_scopes: tuple[tuple[str, str], ...]
    event_ref: str
    caller_key: str
    agent_ref: str | None = None

    def __post_init__(self) -> None:
        # These form the immutable store address and trusted scope snapshot.
        if (
            type(self.tenant_id) is not UUID
            or type(self.capture_id) is not str
            or not _WIRE_ID.fullmatch(self.capture_id)
            or type(self.revision) is not int
            or self.revision < 1
        ):
            raise ValueError("invalid capture revision")
        if type(self.target_scopes) is not tuple or any(
            type(scope) is not tuple
            or len(scope) != 2
            or any(type(part) is not str for part in scope)
            for scope in self.target_scopes
        ):
            raise ValueError("invalid capture scope selection")
        if not all(
            type(value) is str
            for value in (
                self.mapping_ref,
                self.operation,
                self.request_id,
                self.ingested_at,
                self.event_ref,
                self.party_ref,
                self.caller_key,
            )
        ) or (self.agent_ref is not None and type(self.agent_ref) is not str):
            raise ValueError("invalid capture selection")

    @property
    def key(self) -> tuple[UUID, str, int]:
        return self.tenant_id, self.capture_id, self.revision

    @property
    def reference(self) -> str:
        return (
            f"capture-normalization:{self.tenant_id}:{self.capture_id}:{self.revision}"
        )


@dataclass(frozen=True, slots=True)
class ConversionRecord:
    selection: CaptureSelection
    reference: str
    capture_sha256: str
    request_sha256: str | None
    disposition: str


@dataclass(frozen=True, slots=True)
class NormalizationEvidence:
    reference: str
    capture_bytes: bytes
    request_bytes: bytes
    disposition: str


def _envelope(selection: CaptureSelection) -> dict:
    return {
        "schemaVersion": "ofarm.commitingressrequest.v0.1",
        "ingressChannel": "MANUAL_UI",
        "commitClass": "OPERATION_CLAIM",
        "requestId": selection.request_id,
        "ingestedAt": selection.ingested_at,
    }


def _mapped_fields(selection: CaptureSelection) -> Iterator[tuple[str, str, object]]:
    """Capture field, wire field, and the independently selected value."""
    yield "partyRef", "actingPartyRef", selection.party_ref
    yield (
        "scopes",
        "targetScopes",
        [{"scopeType": kind, "scopeRef": ref} for kind, ref in selection.target_scopes],
    )
    yield "eventRef", "semanticEventRef", selection.event_ref
    yield "callerKey", "idempotencyKey", selection.caller_key
    if selection.agent_ref is not None:
        yield "agentRef", "actingAgentRef", selection.agent_ref


def _matches(
    selection: CaptureSelection,
    capture: dict,
    request: dict,
    validator: jsonschema.Draft202012Validator,
) -> bool:
    if (
        selection.mapping_ref != MANUAL_MAPPING
        or selection.operation != _OPERATION
        or capture.get("operation") != selection.operation
    ):
        return False
    # JSON Schema's end anchor also matches before a final newline in Python.
    identifiers = [
        selection.caller_key,
        selection.request_id,
        selection.party_ref,
        selection.event_ref,
    ]
    identifiers.extend(ref for _, ref in selection.target_scopes)
    if selection.agent_ref is not None:
        identifiers.append(selection.agent_ref)
    if not all(_WIRE_ID.fullmatch(value) for value in identifiers):
        return False
    fields = list(_mapped_fields(selection))
    fixed = _envelope(selection)
    source_keys = {"operation"} | {source for source, _, _ in fields}
    wire_keys = fixed.keys() | {wire for _, wire, _ in fields}
    if capture.keys() != source_keys or request.keys() != wire_keys:
        return False
    return (
        all(
            capture[source] == expected == request[wire]
            for source, wire, expected in fields
        )
        and all(request[key] == value for key, value in fixed.items())
        and validator.is_valid(request)
    )


class ManualCaptureFixture:
    """Owner-side, in-memory fixture. Never installed in production composition."""

    def __init__(self) -> None:
        schema = _SCHEMA.read_bytes()
        if _digest(schema) != _SCHEMA_SHA256:
            raise ValueError(
                "capture request schema differs from the reviewed contract"
            )
        checker = jsonschema.FormatChecker()
        if "date-time" not in checker.checkers:
            raise ValueError("capture request date-time validator unavailable")
        self._validator = jsonschema.Draft202012Validator(
            json.loads(schema), format_checker=checker
        )
        self._lock = Lock()
        self._selections: dict[tuple, CaptureSelection] = {}
        self._captures: dict[tuple, bytes] = {}
        self._requests: dict[tuple, bytes] = {}
        self._records: dict[tuple, ConversionRecord] = {}

    def bind(self, selection: CaptureSelection, capture_bytes: bytes) -> None:
        """Seed an independently selected source once, without accepting evidence."""
        if type(capture_bytes) is not bytes:
            raise ValueError("original capture must be bytes")
        key = selection.key
        with self._lock:
            if key in self._selections:
                if (
                    self._selections[key] != selection
                    or self._captures.get(key) != capture_bytes
                ):
                    raise ValueError("conflicting capture revision")
                return
            self._selections[key] = selection
            self._captures[key] = capture_bytes

    def normalizer(self, selection: CaptureSelection) -> _ManualNormalizer:
        return _ManualNormalizer(self, selection)

    def reader(self, selection: CaptureSelection) -> _CaptureReader:
        return _CaptureReader(
            selection, partial(self._snapshot, selection), self._validator
        )

    def _snapshot(self, selection: CaptureSelection):
        key = selection.key
        with self._lock:
            if self._selections.get(key) != selection:
                return None
            return (
                self._records.get(key),
                self._captures.get(key),
                self._requests.get(key),
            )


@dataclass(frozen=True, slots=True)
class _ManualNormalizer:
    _owner: ManualCaptureFixture
    selection: CaptureSelection

    def convert(self) -> ConversionRecord:
        owner = self._owner
        key = self.selection.key
        with owner._lock:
            if (
                owner._selections.get(key) != self.selection
                or key not in owner._captures
            ):
                raise ValueError("selected capture revision unavailable")
            if key in owner._records:
                raise ValueError("capture revision already normalized")
            raw = owner._captures[key]
            request_bytes = None
            disposition = "REFUSED"
            try:
                capture, _ = strict_json_document(raw, "original capture")
                request = _envelope(self.selection)
                for source, wire, _ in _mapped_fields(self.selection):
                    if source in capture:
                        request[wire] = capture[source]
                request_bytes = json.dumps(request, separators=(",", ":")).encode(
                    "ascii"
                )
                emitted, _ = strict_json_document(request_bytes, "emitted request")
                if _matches(self.selection, capture, emitted, owner._validator):
                    disposition = _NORMALIZED
            except (RuntimeBundleError, RecursionError):
                pass  # Preserve the refusal and any bytes already emitted.
            record = ConversionRecord(
                self.selection,
                self.selection.reference,
                _digest(raw),
                _digest(request_bytes) if request_bytes is not None else None,
                disposition,
            )
            if request_bytes is not None:
                owner._requests[key] = request_bytes
            owner._records[key] = record
            return record


@dataclass(frozen=True, slots=True)
class _CaptureReader:
    selection: CaptureSelection
    _snapshot: Callable[
        [],
        tuple[ConversionRecord | None, bytes | None, bytes | None] | None,
    ]
    _validator: jsonschema.Draft202012Validator

    def read(self, reference: str) -> NormalizationEvidence | None:
        """Return one complete original and disposition, or zero passing references."""
        if type(reference) is not str or reference != self.selection.reference:
            return None
        snapshot = self._snapshot()
        if snapshot is None:
            return None
        record, raw, original = snapshot
        if (
            type(record) is not ConversionRecord
            or record.selection != self.selection
            or record.reference != reference
            or record.disposition != _NORMALIZED
            or type(raw) is not bytes
            or type(original) is not bytes
            or record.capture_sha256 != _digest(raw)
            or record.request_sha256 != _digest(original)
        ):
            return None
        try:
            capture, _ = strict_json_document(raw, "original capture")
            request, _ = strict_json_document(original, "original request")
            if not _matches(self.selection, capture, request, self._validator):
                return None
        except (RuntimeBundleError, RecursionError):
            return None
        return NormalizationEvidence(reference, raw, original, record.disposition)
