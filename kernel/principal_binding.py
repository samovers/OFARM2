"""Immutable OIDC principal-binding resolution and control-plane orchestration.

The authentication resolver reconstructs authority with #174's fold function
and reads the exact immutable version it names.  The controller mutates state
only through #174's digest and expected-head functions; it contains no direct
table DML and never treats the disposable current projection as authority.
"""
from __future__ import annotations

import re
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Protocol, final
from uuid import UUID, uuid4

from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TENANT_CAPABILITY_PARTY_RECORD_KIND,
    TenantCapabilityContractError,
    validate_binder_audience,
    validate_oidc_issuer,
)

from .auth_oidc import (
    AuthenticationStartupError,
    OidcError,
    PreBindingOutcome,
    VerifiedOidcIdentity,
)


_SHA256_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_SUBJECT = re.compile(r"^[!-~]{1,255}$")
_ASCII_ID = re.compile(r"^[A-Za-z0-9._:-]{1,255}$")
_BINDING_INTEGRITY_SQLSTATE = "PT001"


def _is_aware_datetime(value: object) -> bool:
    if type(value) is not datetime or value.tzinfo is None:
        return False
    try:
        return value.utcoffset() is not None
    except Exception:
        return False


class ExecutableConnection(Protocol):
    def execute(self, query: str, params: object = None) -> object: ...


ConnectionFactory = Callable[[], AbstractContextManager[ExecutableConnection]]


@dataclass(frozen=True, slots=True)
class PrincipalBindingAuthority:
    equality_policy: str
    issuer: str
    subject: str
    binding_version_id: UUID
    binding_version_digest: str
    lifecycle_head_id: UUID
    lifecycle_head_digest: str
    tenant_id: UUID
    tenant_registration_digest: str
    party_ref: str
    party_record_kind: str
    party_record_id: str
    party_schema_digest: str
    party_payload_digest: str
    party_state: str
    valid_from: datetime
    valid_until: datetime


@final
class PostgreSQLPrincipalBindingResolver:
    """Resolve through the fixed production credential boundary."""

    _RESOLVE_SQL = """
        SELECT *
          FROM ofarm.resolve_principal_binding_authority(%s, %s, %s)
    """
    _HEALTH_SQL = """
        SELECT ofarm.check_principal_binding_resolution_dependencies()
    """

    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory
        self._initialized = False
        self._audience: str | None = None

    def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = False
        try:
            with self._connection_factory() as connection:
                rows = connection.execute(self._HEALTH_SQL).fetchall()
            if (
                len(rows) != 1
                or type(rows[0]) is not tuple
                or len(rows[0]) != 1
            ):
                raise ValueError(
                    "principal-binding audience result is not exact"
                )
            audience = validate_binder_audience(rows[0][0])
            if self._audience is not None and audience != self._audience:
                raise ValueError("principal-binding audience changed")
        except Exception as exc:
            raise AuthenticationStartupError(
                "principal-binding immutable read path is unavailable"
            ) from exc
        self._audience = audience
        self._initialized = True

    @property
    def audience(self) -> str:
        """Return the PostgreSQL-pinned binder audience after initialization."""

        if not self._initialized or self._audience is None:
            raise AuthenticationStartupError(
                "principal-binding resolver is not initialized"
            )
        return self._audience

    def resolve(self, identity: VerifiedOidcIdentity) -> PrincipalBindingAuthority:
        if not self._initialized:
            raise OidcError(
                PreBindingOutcome.BINDING_UNAVAILABLE,
                internal_detail="principal-binding resolver is not initialized",
            )
        if identity.equality_policy != OIDC_ISSUER_EQUALITY_POLICY:
            raise OidcError(
                PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
                internal_detail="principal equality policy differs",
            )
        params = (
            identity.equality_policy,
            identity.issuer,
            identity.subject,
        )
        try:
            with self._connection_factory() as connection:
                rows = connection.execute(self._RESOLVE_SQL, params).fetchall()
        except Exception as exc:
            outcome = (
                PreBindingOutcome.BINDING_INTEGRITY_REFUSED
                if getattr(exc, "sqlstate", None)
                == _BINDING_INTEGRITY_SQLSTATE
                else PreBindingOutcome.BINDING_UNAVAILABLE
            )
            raise OidcError(
                outcome,
                internal_detail=(
                    "principal-binding authority integrity refused"
                    if outcome
                    is PreBindingOutcome.BINDING_INTEGRITY_REFUSED
                    else "principal-binding authority read failed"
                ),
            ) from exc
        if not rows:
            raise OidcError(
                PreBindingOutcome.PRINCIPAL_UNBOUND,
                internal_detail="principal has no active immutable binding",
            )
        if len(rows) != 1:
            raise OidcError(
                PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
                internal_detail="principal binding is ambiguous",
            )
        row = rows[0]
        if len(row) != 18 or row[17] is not True:
            raise OidcError(
                PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
                internal_detail="principal binding digest differs",
            )
        try:
            authority = PrincipalBindingAuthority(*row[:17])
            _validate_authority(authority, identity)
        except OidcError:
            raise
        except Exception as exc:
            raise OidcError(
                PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
                internal_detail="principal binding immutable facts are malformed",
            ) from exc
        return authority


def _validate_authority(
    authority: PrincipalBindingAuthority, identity: VerifiedOidcIdentity
) -> None:
    if (
        authority.equality_policy != OIDC_ISSUER_EQUALITY_POLICY
        or authority.equality_policy != identity.equality_policy
        or authority.issuer != identity.issuer
        or authority.subject != identity.subject
        or authority.party_record_kind != TENANT_CAPABILITY_PARTY_RECORD_KIND
        or authority.party_record_id != authority.party_ref
        or authority.party_state != "ACTIVE"
        or not _ASCII_ID.fullmatch(authority.party_ref)
        or type(authority.binding_version_id) is not UUID
        or authority.binding_version_id.int == 0
        or type(authority.lifecycle_head_id) is not UUID
        or authority.lifecycle_head_id.int == 0
        or type(authority.tenant_id) is not UUID
        or authority.tenant_id.int == 0
        or not _is_aware_datetime(authority.valid_from)
        or not _is_aware_datetime(authority.valid_until)
        or not authority.valid_from < authority.valid_until
        or any(
            type(value) is not str or _SHA256_ID.fullmatch(value) is None
            for value in (
                authority.binding_version_digest,
                authority.lifecycle_head_digest,
                authority.tenant_registration_digest,
                authority.party_schema_digest,
                authority.party_payload_digest,
            )
        )
    ):
        raise OidcError(
            PreBindingOutcome.BINDING_INTEGRITY_REFUSED,
            internal_detail="principal binding immutable facts differ",
        )


class PrincipalBindingAct(str, Enum):
    ACTIVATE = "ACTIVATE"
    REVOKE = "REVOKE"
    EXPIRE = "EXPIRE"
    SUPERSEDE = "SUPERSEDE"


@dataclass(frozen=True, slots=True)
class BindingLifecycleHead:
    stream_sequence: int
    act_id: UUID
    act_digest: str
    current_state: str
    binding_version_id: UUID | None
    binding_version_digest: str | None


@dataclass(frozen=True, slots=True)
class BindingVersionCandidate:
    binding_version_id: UUID
    tenant_id: UUID
    tenant_registration_digest: str
    party_ref: str
    party_record_kind: str
    party_record_id: str
    party_schema_digest: str
    party_payload_digest: str
    party_state: str
    valid_from: datetime
    valid_until: datetime
    predecessor_version_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class BindingTransitionRequest:
    act_kind: PrincipalBindingAct
    issuer: str
    subject: str
    expected_head: BindingLifecycleHead | None
    effective_at: datetime
    decided_at: datetime
    accountable_control_ref: str
    reason: str
    current_binding_version_id: UUID | None = None
    current_binding_version_digest: str | None = None
    candidate: BindingVersionCandidate | None = None
    act_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class BindingTransitionReceipt:
    act_id: UUID
    act_digest: str
    act_kind: PrincipalBindingAct
    binding_version_id: UUID
    binding_version_digest: str
    candidate_version_id: UUID | None
    candidate_version_digest: str | None


class PrincipalBindingControlError(RuntimeError):
    """Closed control-plane refusal; database exception text is not exposed."""


class PrincipalBindingControlOutcomeUnknown(PrincipalBindingControlError):
    """A transition may have committed and must be reconciled by act ID."""

    def __init__(self, act_id: UUID):
        self.act_id = act_id
        super().__init__(
            "principal binding transition outcome is unknown; "
            f"reconcile act {act_id}"
        )


class PrincipalBindingControlPlane:
    """Invoke only #174's hardened control functions with expected-head data."""

    _VERSION_DIGEST_SQL = """
        SELECT ofarm.compute_principal_binding_version_digest(
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s
        )
    """
    _ACT_DIGEST_SQL = """
        SELECT ofarm.compute_principal_lifecycle_act_digest(
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
    """
    _TRANSITION_SQL = """
        SELECT ofarm.transition_principal_binding(
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """

    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def transition(self, request: BindingTransitionRequest) -> BindingTransitionReceipt:
        _validate_transition_request(request)
        expected = request.expected_head
        candidate = request.candidate
        act_id = request.act_id or uuid4()
        if act_id.int == 0:
            raise PrincipalBindingControlError("principal binding transition refused")
        transition_executed = False
        try:
            with self._connection_factory() as connection:
                candidate_digest = (
                    self._candidate_digest(connection, request, candidate)
                    if candidate is not None
                    else None
                )
                if candidate_digest is not None and (
                    type(candidate_digest) is not str
                    or _SHA256_ID.fullmatch(candidate_digest) is None
                ):
                    raise PrincipalBindingControlError(
                        "principal binding transition refused"
                    )
                if request.act_kind is PrincipalBindingAct.ACTIVATE:
                    assert candidate is not None and candidate_digest is not None
                    binding_version_id = candidate.binding_version_id
                    binding_version_digest = candidate_digest
                    successor_id = None
                    successor_digest = None
                else:
                    assert request.current_binding_version_id is not None
                    assert request.current_binding_version_digest is not None
                    binding_version_id = request.current_binding_version_id
                    binding_version_digest = request.current_binding_version_digest
                    successor_id = (
                        candidate.binding_version_id if candidate is not None else None
                    )
                    successor_digest = candidate_digest
                stream_sequence = 1 if expected is None else expected.stream_sequence + 1
                act_digest = connection.execute(
                    self._ACT_DIGEST_SQL,
                    (
                        OIDC_ISSUER_EQUALITY_POLICY,
                        request.issuer,
                        request.subject,
                        stream_sequence,
                        act_id,
                        request.act_kind.value,
                        binding_version_id,
                        binding_version_digest,
                        expected.act_id if expected else None,
                        expected.act_digest if expected else None,
                        successor_id,
                        successor_digest,
                        request.effective_at,
                        request.decided_at,
                        request.accountable_control_ref,
                        request.reason,
                    ),
                ).fetchone()[0]
                if (
                    type(act_digest) is not str
                    or _SHA256_ID.fullmatch(act_digest) is None
                ):
                    raise PrincipalBindingControlError(
                        "principal binding transition refused"
                    )
                transition_candidate_id = (
                    candidate.binding_version_id if candidate is not None else None
                )
                connection.execute(
                    self._TRANSITION_SQL,
                    (
                        OIDC_ISSUER_EQUALITY_POLICY,
                        request.issuer,
                        request.subject,
                        expected.act_id if expected else None,
                        expected.act_digest if expected else None,
                        act_id,
                        act_digest,
                        request.act_kind.value,
                        binding_version_id,
                        binding_version_digest,
                        transition_candidate_id,
                        candidate_digest,
                        candidate.tenant_id if candidate else None,
                        candidate.tenant_registration_digest if candidate else None,
                        candidate.party_ref if candidate else None,
                        candidate.party_record_kind if candidate else None,
                        candidate.party_record_id if candidate else None,
                        candidate.party_schema_digest if candidate else None,
                        candidate.party_payload_digest if candidate else None,
                        candidate.party_state if candidate else None,
                        candidate.valid_from if candidate else None,
                        candidate.valid_until if candidate else None,
                        candidate.predecessor_version_id if candidate else None,
                        request.effective_at,
                        request.decided_at,
                        request.accountable_control_ref,
                        request.reason,
                    ),
                ).fetchone()
                transition_executed = True
        except PrincipalBindingControlError:
            raise
        except Exception as exc:
            if transition_executed:
                raise PrincipalBindingControlOutcomeUnknown(act_id) from exc
            raise PrincipalBindingControlError(
                "principal binding transition refused"
            ) from exc
        except BaseException as exc:
            if transition_executed:
                raise PrincipalBindingControlOutcomeUnknown(act_id) from exc
            raise
        return BindingTransitionReceipt(
            act_id=act_id,
            act_digest=act_digest,
            act_kind=request.act_kind,
            binding_version_id=binding_version_id,
            binding_version_digest=binding_version_digest,
            candidate_version_id=transition_candidate_id,
            candidate_version_digest=candidate_digest,
        )

    def _candidate_digest(
        self,
        connection: ExecutableConnection,
        request: BindingTransitionRequest,
        candidate: BindingVersionCandidate,
    ) -> str:
        return connection.execute(
            self._VERSION_DIGEST_SQL,
            (
                OIDC_ISSUER_EQUALITY_POLICY,
                request.issuer,
                request.subject,
                candidate.binding_version_id,
                candidate.tenant_id,
                candidate.tenant_registration_digest,
                candidate.party_ref,
                candidate.party_record_kind,
                candidate.party_record_id,
                candidate.party_schema_digest,
                candidate.party_payload_digest,
                candidate.party_state,
                candidate.valid_from,
                candidate.valid_until,
                candidate.predecessor_version_id,
            ),
        ).fetchone()[0]


def _validate_transition_request(request: BindingTransitionRequest) -> None:
    if (
        type(request) is not BindingTransitionRequest
        or type(request.act_kind) is not PrincipalBindingAct
    ):
        raise PrincipalBindingControlError("principal binding transition refused")
    try:
        validate_oidc_issuer(request.issuer)
    except TenantCapabilityContractError as exc:
        raise PrincipalBindingControlError("principal binding transition refused") from exc
    if (
        type(request.subject) is not str
        or _SUBJECT.fullmatch(request.subject) is None
        or type(request.accountable_control_ref) is not str
        or _ASCII_ID.fullmatch(request.accountable_control_ref) is None
        or type(request.reason) is not str
        or _ASCII_ID.fullmatch(request.reason) is None
        or not _is_aware_datetime(request.effective_at)
        or not _is_aware_datetime(request.decided_at)
        or request.effective_at > request.decided_at
    ):
        raise PrincipalBindingControlError("principal binding transition refused")
    expected = request.expected_head
    if expected is not None and (
        type(expected) is not BindingLifecycleHead
        or type(expected.stream_sequence) is not int
        or expected.stream_sequence < 1
        or type(expected.act_id) is not UUID
        or expected.act_id.int == 0
        or type(expected.act_digest) is not str
        or _SHA256_ID.fullmatch(expected.act_digest) is None
        or expected.current_state not in ("ACTIVE", "INACTIVE")
        or (expected.binding_version_id is None)
        != (expected.binding_version_digest is None)
        or (
            expected.binding_version_id is not None
            and (
                type(expected.binding_version_id) is not UUID
                or expected.binding_version_id.int == 0
                or type(expected.binding_version_digest) is not str
                or _SHA256_ID.fullmatch(expected.binding_version_digest) is None
            )
        )
    ):
        raise PrincipalBindingControlError("principal binding transition refused")
    candidate = request.candidate
    if candidate is not None and type(candidate) is not BindingVersionCandidate:
        raise PrincipalBindingControlError("principal binding transition refused")
    if request.act_id is not None and (
        type(request.act_id) is not UUID or request.act_id.int == 0
    ):
        raise PrincipalBindingControlError("principal binding transition refused")
    if request.act_kind is PrincipalBindingAct.ACTIVATE:
        if (
            (expected is not None and expected.current_state != "INACTIVE")
            or candidate is None
            or request.current_binding_version_id is not None
            or request.current_binding_version_digest is not None
        ):
            raise PrincipalBindingControlError("principal binding transition refused")
    elif request.act_kind is PrincipalBindingAct.SUPERSEDE:
        if expected is None or candidate is None:
            raise PrincipalBindingControlError("principal binding transition refused")
    elif candidate is not None or expected is None:
        raise PrincipalBindingControlError("principal binding transition refused")
    if request.act_kind is not PrincipalBindingAct.ACTIVATE:
        if (
            request.current_binding_version_id is None
            or request.current_binding_version_digest is None
            or type(request.current_binding_version_id) is not UUID
            or request.current_binding_version_id.int == 0
            or type(request.current_binding_version_digest) is not str
            or _SHA256_ID.fullmatch(request.current_binding_version_digest) is None
            or expected is None
            or expected.current_state != "ACTIVE"
            or expected.binding_version_id != request.current_binding_version_id
            or expected.binding_version_digest != request.current_binding_version_digest
        ):
            raise PrincipalBindingControlError("principal binding transition refused")
    if candidate is not None:
        if (
            type(candidate.binding_version_id) is not UUID
            or candidate.binding_version_id.int == 0
            or type(candidate.tenant_id) is not UUID
            or candidate.tenant_id.int == 0
            or type(candidate.party_ref) is not str
            or type(candidate.party_record_kind) is not str
            or type(candidate.party_record_id) is not str
            or type(candidate.party_state) is not str
            or candidate.party_record_kind != TENANT_CAPABILITY_PARTY_RECORD_KIND
            or candidate.party_record_id != candidate.party_ref
            or candidate.party_state != "ACTIVE"
            or _ASCII_ID.fullmatch(candidate.party_ref) is None
            or not _is_aware_datetime(candidate.valid_from)
            or not _is_aware_datetime(candidate.valid_until)
            or not candidate.valid_from < candidate.valid_until
            or any(
                type(value) is not str or _SHA256_ID.fullmatch(value) is None
                for value in (
                    candidate.tenant_registration_digest,
                    candidate.party_schema_digest,
                    candidate.party_payload_digest,
                )
            )
            or (
                candidate.predecessor_version_id is not None
                and type(candidate.predecessor_version_id) is not UUID
            )
        ):
            raise PrincipalBindingControlError("principal binding transition refused")
        if request.act_kind is PrincipalBindingAct.ACTIVATE:
            if expected is None and candidate.predecessor_version_id is not None:
                raise PrincipalBindingControlError("principal binding transition refused")
        elif candidate.predecessor_version_id != request.current_binding_version_id:
            raise PrincipalBindingControlError("principal binding transition refused")


__all__ = [
    "BindingLifecycleHead",
    "BindingTransitionReceipt",
    "BindingTransitionRequest",
    "BindingVersionCandidate",
    "PostgreSQLPrincipalBindingResolver",
    "PrincipalBindingAct",
    "PrincipalBindingAuthority",
    "PrincipalBindingControlError",
    "PrincipalBindingControlOutcomeUnknown",
    "PrincipalBindingControlPlane",
]
