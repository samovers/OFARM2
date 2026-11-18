"""One checked claim operation on the owning thread and tenant transaction."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from threading import current_thread
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SelectedClaimCommand:
    tenant_id: UUID
    action: str
    bundle_digest: str
    contract_id: str
    contract_version: str
    contract_digest: str
    result_schema: str
    result_schema_digest: str

    def __post_init__(self) -> None:
        fields = (self.action, self.contract_id, self.contract_version, self.result_schema)
        digests = (self.bundle_digest, self.contract_digest, self.result_schema_digest)
        if type(self.tenant_id) is not UUID or any(type(value) is not str for value in fields):
            raise ValueError("invalid claim command binding")
        if any(
            type(value) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", value)
            for value in digests
        ):
            raise ValueError("invalid claim command digest")


@dataclass(frozen=True, slots=True)
class ClaimWriteAttempt:
    command: SelectedClaimCommand
    binding_nonce: UUID
    batch_id: str
    full_xid: int
    intent_bytes: bytes


@dataclass(frozen=True, slots=True)
class CheckedClaimResult:
    command: SelectedClaimCommand
    assertion_id: str
    assertion_digest: str
    validation_trace_ref: str
    validation_trace_digest: str
    domain_payload_ref: str
    domain_payload_digest: str


class BoundClaimOperation(Protocol):
    def selected_claim_command(self) -> SelectedClaimCommand | None: ...

    def stage_and_verify_operation_claim(self, attempt: ClaimWriteAttempt) -> CheckedClaimResult: ...


class ClaimWriteGuard:
    __slots__ = ("_operation", "_owner")

    def __init__(self, operation: BoundClaimOperation | None) -> None:
        self._operation = operation
        self._owner = current_thread()

    def require_owner(self) -> None:
        if current_thread() is not self._owner:
            raise RuntimeError("claim write is on a different thread")

    def close(self) -> None:
        self._operation = None

    def stage(
        self, attempt: ClaimWriteAttempt, tenant_id: UUID, binding_nonce: UUID,
        batch_id: str, full_xid: int, action: str, bundle_digest: str,
        require_writable: Callable[[], None],
    ) -> CheckedClaimResult:
        operation = self._operation
        if operation is None:
            raise RuntimeError("claim write is unavailable or already used")
        # Consume before calling the projection or writer, including on re-entry.
        self._operation = None
        selected = operation.selected_claim_command()
        if type(selected) is not SelectedClaimCommand or type(attempt) is not ClaimWriteAttempt:
            raise RuntimeError("claim write lacks a bound command or attempt")
        if (
            type(attempt.command) is not SelectedClaimCommand
            or type(attempt.binding_nonce) is not UUID or type(attempt.batch_id) is not str
            or type(attempt.full_xid) is not int or type(attempt.intent_bytes) is not bytes
        ):
            raise RuntimeError("claim write has invalid attempt fields")
        if (attempt.command, attempt.binding_nonce, attempt.batch_id, attempt.full_xid) != (
            selected, binding_nonce, batch_id, full_xid,
        ) or (selected.tenant_id, selected.action, selected.bundle_digest) != (tenant_id, action, bundle_digest):
            raise RuntimeError("claim write differs from its transaction or selected command")
        if (selected.action, selected.contract_id, selected.contract_version, selected.result_schema) != (
            "ASSERT_OPERATION_CLAIM", "ofarm.protectedeffect.assertionrecord.submit.v0.1",
            "0.1", "ofarm.assertionrecord.v0.2",
        ):
            raise RuntimeError("selected command cannot stage an operation claim")
        require_writable()
        result = operation.stage_and_verify_operation_claim(attempt)
        require_writable()
        if type(result) is not CheckedClaimResult:
            raise RuntimeError("claim write did not return a checked result")
        return result
