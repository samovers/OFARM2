"""Typed orchestration over the database-owned principal lifecycle."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

import psycopg

from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TENANT_CAPABILITY_PARTY_RECORD_KIND,
)

from .authentication import VerifiedIdentity
from .principal import _digest, _time

ConnectionFactory = Callable[[], psycopg.Connection[tuple[object, ...]]]

class PrincipalTransitionKind(str, Enum):
    ACTIVATE = "ACTIVATE"
    REVOKE = "REVOKE"
    EXPIRE = "EXPIRE"
    SUPERSEDE = "SUPERSEDE"

class PrincipalControlError(RuntimeError):
    pass

class PrincipalControlUnavailable(PrincipalControlError):
    pass

class TransitionRefused(PrincipalControlError):
    def __init__(self, act_id: UUID) -> None:
        self.act_id = act_id
        super().__init__(f"principal transition refused ({act_id})")

class TransitionOutcomeUnknown(PrincipalControlError):
    def __init__(self, act_id: UUID) -> None:
        self.act_id = act_id
        super().__init__(f"principal transition outcome is unknown ({act_id})")

@dataclass(frozen=True, slots=True)
class PrincipalBindingCandidate:
    binding_version_id: UUID
    tenant_id: UUID
    tenant_registration_digest: str
    party_ref: str
    party_record_id: str
    party_schema_digest: str
    party_payload_digest: str
    valid_from: datetime
    valid_until: datetime
    predecessor_version_id: UUID | None = None

@dataclass(frozen=True, slots=True)
class PrincipalBindingTransitionRequest:
    identity: VerifiedIdentity
    act_id: UUID
    kind: PrincipalTransitionKind
    stream_sequence: int
    expected_head_id: UUID | None
    expected_head_digest: str | None
    active_binding_version_id: UUID | None
    active_binding_version_digest: str | None
    candidate: PrincipalBindingCandidate | None
    effective_at: datetime
    decided_at: datetime
    accountable_control_ref: str
    reason: str

@dataclass(frozen=True, slots=True)
class PrincipalBindingTransitionResult:
    act_id: UUID
    act_digest: str

@dataclass(frozen=True, slots=True)
class _TransitionValues:
    binding_version_id: UUID
    binding_version_digest: str
    candidate_version_id: UUID | None
    candidate_version_digest: str | None

def _valid_uuid(value: UUID | None) -> bool:
    return type(value) is UUID and value.int != 0

def _validate_scalar_shape(request: PrincipalBindingTransitionRequest) -> None:
    candidate = request.candidate
    if candidate is not None and type(candidate) is not PrincipalBindingCandidate:
        raise PrincipalControlError("principal transition candidate is invalid")
    digests = (
        request.expected_head_digest,
        request.active_binding_version_digest,
        candidate.tenant_registration_digest if candidate else None,
        candidate.party_schema_digest if candidate else None,
        candidate.party_payload_digest if candidate else None,
    )
    times = (
        request.effective_at,
        request.decided_at,
        candidate.valid_from if candidate else None,
        candidate.valid_until if candidate else None,
    )
    try:
        for digest in digests:
            if digest is not None:
                _digest(digest, "principal transition digest")
        for value in times:
            if value is not None:
                _time(value, "principal transition timestamp")
    except ValueError as exc:
        raise PrincipalControlError(
            "principal transition scalar is invalid"
        ) from exc

def _validate_request(request: PrincipalBindingTransitionRequest) -> None:
    if (
        type(request) is not PrincipalBindingTransitionRequest
        or not _valid_uuid(request.act_id)
        or type(request.kind) is not PrincipalTransitionKind
        or request.identity.equality_policy != OIDC_ISSUER_EQUALITY_POLICY
        or type(request.stream_sequence) is not int
        or request.stream_sequence < 1
    ):
        raise PrincipalControlError("principal transition request is invalid")
    _validate_scalar_shape(request)
    has_head = _valid_uuid(request.expected_head_id)
    if has_head != (request.expected_head_digest is not None):
        raise PrincipalControlError("principal lifecycle head is partial")
    has_active = _valid_uuid(request.active_binding_version_id)
    if has_active != (request.active_binding_version_digest is not None):
        raise PrincipalControlError("principal active binding is partial")
    if request.kind is PrincipalTransitionKind.ACTIVATE:
        valid_shape = (
            not has_head
            and not has_active
            and request.stream_sequence == 1
            and request.candidate is not None
            and request.candidate.predecessor_version_id is None
        )
    elif request.kind is PrincipalTransitionKind.SUPERSEDE:
        valid_shape = (
            has_head
            and has_active
            and request.stream_sequence > 1
            and request.candidate is not None
            and request.candidate.predecessor_version_id
            == request.active_binding_version_id
        )
    else:
        valid_shape = (
            has_head
            and has_active
            and request.stream_sequence > 1
            and request.candidate is None
        )
    if not valid_shape:
        raise PrincipalControlError("principal transition shape is invalid")

def _candidate_digest(
    connection: psycopg.Connection[tuple[object, ...]],
    identity: VerifiedIdentity,
    candidate: PrincipalBindingCandidate,
) -> str:
    row = connection.execute(
        """
        SELECT ofarm.compute_principal_binding_version_digest(
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s
        )
        """,
        (
            identity.equality_policy,
            identity.issuer,
            identity.subject,
            candidate.binding_version_id,
            candidate.tenant_id,
            candidate.tenant_registration_digest,
            candidate.party_ref,
            TENANT_CAPABILITY_PARTY_RECORD_KIND,
            candidate.party_record_id,
            candidate.party_schema_digest,
            candidate.party_payload_digest,
            "ACTIVE",
            candidate.valid_from,
            candidate.valid_until,
            candidate.predecessor_version_id,
        ),
    ).fetchone()
    if type(row) is not tuple or len(row) != 1 or type(row[0]) is not str:
        raise PrincipalControlError("binding digest result differs")
    return row[0]

def _transition_values(
    connection: psycopg.Connection[tuple[object, ...]],
    request: PrincipalBindingTransitionRequest,
) -> _TransitionValues:
    candidate_digest = (
        _candidate_digest(connection, request.identity, request.candidate)
        if request.candidate is not None
        else None
    )
    if request.kind is PrincipalTransitionKind.ACTIVATE:
        assert request.candidate is not None and candidate_digest is not None
        binding_id = request.candidate.binding_version_id
        binding_digest = candidate_digest
    else:
        assert request.active_binding_version_id is not None
        assert request.active_binding_version_digest is not None
        binding_id = request.active_binding_version_id
        binding_digest = request.active_binding_version_digest
    return _TransitionValues(
        binding_version_id=binding_id,
        binding_version_digest=binding_digest,
        candidate_version_id=(
            request.candidate.binding_version_id
            if request.candidate is not None
            else None
        ),
        candidate_version_digest=candidate_digest,
    )

def _act_digest(
    connection: psycopg.Connection[tuple[object, ...]],
    request: PrincipalBindingTransitionRequest,
    values: _TransitionValues,
) -> str:
    successor_id = (
        values.candidate_version_id
        if request.kind is PrincipalTransitionKind.SUPERSEDE
        else None
    )
    successor_digest = (
        values.candidate_version_digest
        if request.kind is PrincipalTransitionKind.SUPERSEDE
        else None
    )
    row = connection.execute(
        """
        SELECT ofarm.compute_principal_lifecycle_act_digest(
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            request.identity.equality_policy,
            request.identity.issuer,
            request.identity.subject,
            request.stream_sequence,
            request.act_id,
            request.kind.value,
            values.binding_version_id,
            values.binding_version_digest,
            request.expected_head_id,
            request.expected_head_digest,
            successor_id,
            successor_digest,
            request.effective_at,
            request.decided_at,
            request.accountable_control_ref,
            request.reason,
        ),
    ).fetchone()
    if type(row) is not tuple or len(row) != 1 or type(row[0]) is not str:
        raise PrincipalControlError("lifecycle digest result differs")
    return row[0]

def _transition_parameters(
    request: PrincipalBindingTransitionRequest,
    values: _TransitionValues,
    act_digest: str,
) -> tuple[object, ...]:
    candidate = request.candidate
    return (
        request.identity.equality_policy,
        request.identity.issuer,
        request.identity.subject,
        request.expected_head_id,
        request.expected_head_digest,
        request.act_id,
        act_digest,
        request.kind.value,
        values.binding_version_id,
        values.binding_version_digest,
        values.candidate_version_id,
        values.candidate_version_digest,
        candidate.tenant_id if candidate else None,
        candidate.tenant_registration_digest if candidate else None,
        candidate.party_ref if candidate else None,
        TENANT_CAPABILITY_PARTY_RECORD_KIND if candidate else None,
        candidate.party_record_id if candidate else None,
        candidate.party_schema_digest if candidate else None,
        candidate.party_payload_digest if candidate else None,
        "ACTIVE" if candidate else None,
        candidate.valid_from if candidate else None,
        candidate.valid_until if candidate else None,
        candidate.predecessor_version_id if candidate else None,
        request.effective_at,
        request.decided_at,
        request.accountable_control_ref,
        request.reason,
    )

class PrincipalBindingController:
    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def transition(
        self,
        request: PrincipalBindingTransitionRequest,
    ) -> PrincipalBindingTransitionResult:
        _validate_request(request)
        submitted = False
        try:
            with self._connection_factory() as connection:
                if connection.autocommit is not False:
                    raise PrincipalControlError(
                        "principal control requires autocommit=False"
                    )
                with connection.transaction():
                    values = _transition_values(connection, request)
                    act_digest = _act_digest(connection, request, values)
                    submitted = True
                    connection.execute(
                        """
                        SELECT ofarm.transition_principal_binding(
                            %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        _transition_parameters(request, values, act_digest),
                    )
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            if submitted:
                raise TransitionOutcomeUnknown(request.act_id) from exc
            raise PrincipalControlUnavailable(
                "principal control is unavailable"
            ) from exc
        except psycopg.Error as exc:
            raise TransitionRefused(request.act_id) from exc
        return PrincipalBindingTransitionResult(
            act_id=request.act_id,
            act_digest=act_digest,
        )
