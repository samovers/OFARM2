"""One checked-out PostgreSQL transaction for one verified tenant."""
from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol
from uuid import RFC_4122, UUID

import psycopg
from psycopg.pq import TransactionStatus
from psycopg_pool import ConnectionPool

from .authentication import VerifiedIdentity
from .principal import AuthenticatedPrincipal, PrincipalAuthority
from .tenant_capability_issuer import CapabilityMintError, TenantChallenge

_ASCII_ID = re.compile(r"[A-Za-z0-9._:-]{1,255}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_KID = re.compile(r"[A-Za-z0-9_-]{43}")
_TRANSACTION_CONTROL = re.compile(
    r"\s*(?:BEGIN|COMMIT|END|ROLLBACK|ABORT|SAVEPOINT|RELEASE)\b",
    re.IGNORECASE,
)
_POOL_MIN_SIZE = 1
_POOL_MAX_SIZE = 8
_POOL_WAIT_SECONDS = 5.0
_POOL_MAX_WAITING = 32
_MAX_KNOWLEDGE_POSITION = 9_007_199_254_740_991

Connection = psycopg.Connection[tuple[object, ...]]
Row = tuple[object, ...]


class CapabilityMinter(Protocol):
    def mint(
        self,
        identity: VerifiedIdentity,
        authority: PrincipalAuthority,
        challenge: TenantChallenge,
    ) -> str: ...


class TenantBoundaryOutcome(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    CAPABILITY_REFUSED = "CAPABILITY_REFUSED"
    BINDING_REFUSED = "BINDING_REFUSED"
    FINALIZATION_UNKNOWN = "FINALIZATION_UNKNOWN"


class TenantBoundaryError(RuntimeError):
    def __init__(self, outcome: TenantBoundaryOutcome) -> None:
        self.outcome = outcome
        super().__init__(f"tenant boundary refused ({outcome.value})")


class TenantUnitOfWorkStartupError(RuntimeError):
    pass


def _uuid(value: object, label: str, *, version_four: bool = False) -> UUID:
    if type(value) is not UUID or value.int == 0:
        raise ValueError(f"{label} is invalid")
    if version_four and (value.version != 4 or value.variant != RFC_4122):
        raise ValueError(f"{label} is invalid")
    return value


def _digest(value: object, label: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{label} is invalid")
    return value


def _time(value: object, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} is invalid")
    return value


def _authority_values(authority: PrincipalAuthority) -> tuple[object, ...]:
    return (
        authority.equality_policy,
        authority.issuer,
        authority.subject,
        authority.binding_version_id,
        authority.binding_version_digest,
        authority.lifecycle_head_id,
        authority.lifecycle_head_digest,
        authority.tenant_id,
        authority.tenant_registration_digest,
        authority.party_ref,
        authority.party_record_kind,
        authority.party_record_id,
        authority.party_schema_digest,
        authority.party_payload_digest,
    )


@dataclass(frozen=True, slots=True)
class TenantBinding:
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
    capability_key_id: str
    capability_key_lifecycle_head_id: UUID
    capability_key_lifecycle_head_digest: str
    capability_nonce: UUID
    bound_at: datetime

    @classmethod
    def from_database_row(
        cls,
        row: Row,
        principal: AuthenticatedPrincipal,
    ) -> TenantBinding:
        if len(row) != 19 or row[:14] != _authority_values(principal.authority):
            raise ValueError("tenant binding authority differs")
        key_id, key_head_id, key_head_digest, nonce, bound_at = row[14:]
        if type(key_id) is not str or _KID.fullmatch(key_id) is None:
            raise ValueError("tenant binding key is invalid")
        return cls(
            equality_policy=principal.authority.equality_policy,
            issuer=principal.authority.issuer,
            subject=principal.authority.subject,
            binding_version_id=principal.authority.binding_version_id,
            binding_version_digest=principal.authority.binding_version_digest,
            lifecycle_head_id=principal.authority.lifecycle_head_id,
            lifecycle_head_digest=principal.authority.lifecycle_head_digest,
            tenant_id=principal.authority.tenant_id,
            tenant_registration_digest=principal.authority.tenant_registration_digest,
            party_ref=principal.authority.party_ref,
            party_record_kind=principal.authority.party_record_kind,
            party_record_id=principal.authority.party_record_id,
            party_schema_digest=principal.authority.party_schema_digest,
            party_payload_digest=principal.authority.party_payload_digest,
            capability_key_id=key_id,
            capability_key_lifecycle_head_id=_uuid(key_head_id, "key lifecycle head"),
            capability_key_lifecycle_head_digest=_digest(
                key_head_digest, "key lifecycle digest"
            ),
            capability_nonce=_uuid(nonce, "capability nonce", version_four=True),
            bound_at=_time(bound_at, "bound at"),
        )


@dataclass(frozen=True, slots=True)
class GovernedBatchRequest:
    batch_id: str
    operation: str
    request_id: str
    runtime_bundle_digest: str

    def __post_init__(self) -> None:
        values = (self.batch_id, self.operation, self.request_id)
        if any(
            type(value) is not str or _ASCII_ID.fullmatch(value) is None
            for value in values
        ):
            raise ValueError("governed batch identifier is invalid")
        _digest(self.runtime_bundle_digest, "runtime bundle digest")


@dataclass(frozen=True, slots=True)
class GovernedWriteBatch:
    tenant_id: UUID
    batch_id: str
    full_xid: int
    authenticated_principal_ref: str
    operation: str
    request_id: str
    runtime_bundle_digest: str
    knowledge_position: int
    created_at: datetime


class TenantUnitOfWork:
    def __init__(self, connection: Connection, binding: TenantBinding) -> None:
        self._connection = connection
        self.binding = binding
        self._active = True
        self._batch: GovernedWriteBatch | None = None
        self._savepoint_depth = 0

    @property
    def batch(self) -> GovernedWriteBatch | None:
        return self._batch

    def _require_active(self) -> None:
        if not self._active:
            raise RuntimeError("tenant UnitOfWork is closed")

    def _finish(self) -> None:
        self._active = False

    def _query(self, query: str, parameters: tuple[object, ...]) -> psycopg.Cursor[Row]:
        self._require_active()
        if type(query) is not str or _TRANSACTION_CONTROL.match(query):
            raise ValueError("transaction control belongs to the UnitOfWork")
        return self._connection.execute(query, parameters)

    def execute(self, query: str, parameters: tuple[object, ...] = ()) -> int:
        return self._query(query, parameters).rowcount

    def fetch_one(
        self,
        query: str,
        parameters: tuple[object, ...] = (),
    ) -> Row | None:
        return self._query(query, parameters).fetchone()

    def fetch_all(
        self,
        query: str,
        parameters: tuple[object, ...] = (),
    ) -> list[Row]:
        return self._query(query, parameters).fetchall()

    @contextmanager
    def savepoint(self) -> Iterator[None]:
        self._require_active()
        self._savepoint_depth += 1
        try:
            with self._connection.transaction():
                yield
        finally:
            self._savepoint_depth -= 1

    def begin_batch(self, request: GovernedBatchRequest) -> GovernedWriteBatch:
        self._require_active()
        if self._savepoint_depth:
            raise RuntimeError("governed batch belongs to the outer transaction")
        if type(request) is not GovernedBatchRequest or self._batch is not None:
            raise RuntimeError("governed batch already exists")
        row = self._connection.execute(
            """
            INSERT INTO ofarm.governed_write_batch (
                tenant_id, batch_id, authenticated_principal_ref,
                governed_operation, request_id, runtime_bundle_digest
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING tenant_id, batch_id, full_xid::pg_catalog.text,
                      authenticated_principal_ref, governed_operation,
                      request_id, runtime_bundle_digest,
                      knowledge_position, created_at
            """,
            (
                self.binding.tenant_id,
                request.batch_id,
                self.binding.party_ref,
                request.operation,
                request.request_id,
                request.runtime_bundle_digest,
            ),
        ).fetchone()
        if row is None or len(row) != 9:
            raise RuntimeError("governed batch allocation failed")
        expected = (
            self.binding.tenant_id,
            request.batch_id,
            self.binding.party_ref,
            request.operation,
            request.request_id,
            request.runtime_bundle_digest,
        )
        if (row[0], row[1], *row[3:7]) != expected:
            raise RuntimeError("governed batch authority differs")
        full_xid = int(row[2])
        if full_xid <= 0:
            raise RuntimeError("governed batch transaction differs")
        knowledge_position = row[7]
        if (
            type(knowledge_position) is not int
            or knowledge_position < 1
            or knowledge_position > _MAX_KNOWLEDGE_POSITION
        ):
            raise RuntimeError("governed batch knowledge position differs")
        self._batch = GovernedWriteBatch(
            tenant_id=_uuid(row[0], "batch tenant"),
            batch_id=request.batch_id,
            full_xid=full_xid,
            authenticated_principal_ref=self.binding.party_ref,
            operation=request.operation,
            request_id=request.request_id,
            runtime_bundle_digest=request.runtime_bundle_digest,
            knowledge_position=knowledge_position,
            created_at=_time(row[8], "batch creation time"),
        )
        return self._batch


def create_tenant_connection_pool(dsn: str) -> ConnectionPool:
    return ConnectionPool(
        dsn,
        kwargs={"autocommit": False},
        min_size=_POOL_MIN_SIZE,
        max_size=_POOL_MAX_SIZE,
        open=False,
        check=ConnectionPool.check_connection,
        timeout=_POOL_WAIT_SECONDS,
        max_waiting=_POOL_MAX_WAITING,
        name="ofarm-tenant",
    )


def _idle(connection: Connection) -> bool:
    try:
        return connection.info.transaction_status == TransactionStatus.IDLE
    except Exception:
        return False


def _discard(connection: Connection) -> None:
    with suppress(Exception):
        connection.close()


def _rollback_or_discard(connection: Connection) -> None:
    try:
        connection.rollback()
    except Exception:
        _discard(connection)
    if not _idle(connection):
        _discard(connection)


class TenantUnitOfWorkManager:
    def __init__(self, pool: ConnectionPool, minter: CapabilityMinter) -> None:
        self._pool = pool
        self._minter = minter

    def initialize(self) -> None:
        try:
            self._pool.open(wait=True, timeout=_POOL_WAIT_SECONDS)
        except Exception as exc:
            with suppress(Exception):
                self._pool.close()
            raise TenantUnitOfWorkStartupError(
                "tenant connection pool is unavailable"
            ) from exc

    def close(self) -> None:
        self._pool.close(timeout=_POOL_WAIT_SECONDS)

    def _bind(
        self,
        connection: Connection,
        principal: AuthenticatedPrincipal,
    ) -> TenantBinding:
        challenge_row = connection.execute(
            "SELECT * FROM ofarm.create_tenant_challenge()"
        ).fetchone()
        if challenge_row is None or len(challenge_row) != 2:
            raise ValueError("tenant challenge row shape differs")
        challenge = TenantChallenge(
            challenge_id=_uuid(challenge_row[0], "challenge id"),
            audience=challenge_row[1],
        )
        capability = self._minter.mint(
            principal.identity, principal.authority, challenge
        )
        connection.execute(
            "SELECT ofarm.bind_tenant_capability(%s)",
            (capability,),
        )
        context = connection.execute(
            "SELECT * FROM ofarm.current_tenant_context()"
        ).fetchone()
        if context is None:
            raise ValueError("tenant binding context is absent")
        return TenantBinding.from_database_row(context, principal)

    @contextmanager
    def unit_of_work(
        self,
        principal: AuthenticatedPrincipal,
    ) -> Iterator[TenantUnitOfWork]:
        try:
            connection = self._pool.getconn(timeout=_POOL_WAIT_SECONDS)
        except Exception:
            raise TenantBoundaryError(TenantBoundaryOutcome.UNAVAILABLE) from None
        try:
            yield from self._run(connection, principal)
        finally:
            if not _idle(connection):
                _discard(connection)
            self._pool.putconn(connection)

    def _run(
        self,
        connection: Connection,
        principal: AuthenticatedPrincipal,
    ) -> Iterator[TenantUnitOfWork]:
        if not _idle(connection):
            _discard(connection)
            raise TenantBoundaryError(TenantBoundaryOutcome.UNAVAILABLE)
        try:
            connection.execute("BEGIN ISOLATION LEVEL READ COMMITTED")
            binding = self._bind(connection, principal)
        except CapabilityMintError:
            _rollback_or_discard(connection)
            raise TenantBoundaryError(
                TenantBoundaryOutcome.CAPABILITY_REFUSED
            ) from None
        except (psycopg.Error, TypeError, ValueError):
            _rollback_or_discard(connection)
            raise TenantBoundaryError(
                TenantBoundaryOutcome.BINDING_REFUSED
            ) from None
        unit = TenantUnitOfWork(connection, binding)
        try:
            yield unit
        except BaseException:
            unit._finish()
            _rollback_or_discard(connection)
            raise
        unit._finish()
        try:
            connection.commit()
        except Exception:
            _discard(connection)
            raise TenantBoundaryError(
                TenantBoundaryOutcome.FINALIZATION_UNKNOWN
            ) from None
        if not _idle(connection):
            _discard(connection)
            raise TenantBoundaryError(
                TenantBoundaryOutcome.FINALIZATION_UNKNOWN
            )
