"""A staged claim on a producer-bound lease must complete its one promotion."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from .tenant_claim_write_guard import CheckedClaimResult, SelectedClaimCommand

if TYPE_CHECKING:
    from .tenant_uow import GovernedWriteBatch, TenantBinding

TENANT_LOCAL_REF = re.compile(r"[A-Za-z0-9._:-]{1,255}")
SHA256_ID = re.compile(r"sha256:[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class PromotionInputs:
    tenant_id: UUID
    principal_ref: str
    binding_nonce: UUID
    batch_id: str
    full_xid: int
    request_id: str
    command: SelectedClaimCommand
    evidence_bytes: bytes


class BoundPromotionOperation(Protocol):
    def stage_and_verify_promotion(
        self, inputs: PromotionInputs, claim: CheckedClaimResult, batch: GovernedWriteBatch,
    ) -> tuple[str, str]: ...


class PromotionGuard:
    __slots__ = ("_operation", "_claim")

    def __init__(self, operation: BoundPromotionOperation | None) -> None:
        self._operation = operation
        self._claim: CheckedClaimResult | None = None

    def retain(self, claim: CheckedClaimResult, staged_command: SelectedClaimCommand) -> None:
        if self._operation is not None:
            if type(claim.command) is not SelectedClaimCommand or claim.command != staged_command:
                raise RuntimeError("checked claim differs from the staged command")
            self._claim = claim

    @property
    def outstanding(self) -> bool:
        return self._claim is not None

    def close(self) -> None:
        self._claim = None
        self._operation = None

    def promote(
        self, inputs: PromotionInputs, binding: TenantBinding, batch: GovernedWriteBatch | None,
        require_writable: Callable[[], None],
    ) -> tuple[str, str]:
        operation, claim = self._operation, self._claim
        if operation is None or claim is None or batch is None:
            raise RuntimeError("promotion requires an unused producer and a staged claim")
        # Consume dispatch before calling the producer. The claim stays outstanding.
        self._operation = None
        if type(inputs) is not PromotionInputs or (
            type(inputs.tenant_id) is not UUID or type(inputs.binding_nonce) is not UUID
            or type(inputs.principal_ref) is not str or type(inputs.batch_id) is not str
            or type(inputs.full_xid) is not int or type(inputs.request_id) is not str
            or type(inputs.command) is not SelectedClaimCommand or type(inputs.evidence_bytes) is not bytes
        ):
            raise RuntimeError("invalid promotion inputs")
        if (
            inputs.tenant_id != binding.tenant_id or inputs.principal_ref != binding.party_ref
            or inputs.binding_nonce != binding.capability_nonce or inputs.batch_id != batch.batch_id
            or inputs.full_xid != batch.full_xid or inputs.request_id != batch.request_id
            or inputs.command != claim.command or inputs.command.action != batch.operation
            or inputs.command.bundle_digest != batch.runtime_bundle_digest
        ):
            raise RuntimeError("promotion differs from its tenant transaction or staged claim")
        require_writable()
        result = operation.stage_and_verify_promotion(inputs, claim, batch)
        if type(result) is not tuple or len(result) != 2:
            raise RuntimeError("promotion did not return a checked trace binding")
        trace_id, digest = result
        if (
            type(trace_id) is not str or TENANT_LOCAL_REF.fullmatch(trace_id) is None
            or type(digest) is not str or SHA256_ID.fullmatch(digest) is None
        ):
            raise RuntimeError("promotion returned an invalid trace binding")
        require_writable()
        self._claim = None
        return result
