"""Bounded client for the isolated pre-tenant security-audit append API."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import MappingProxyType
from uuid import UUID, uuid4

import psycopg

from deployment.postgresql.audit_contract import (
    SECURITY_AUDIT_CONTRACT,
    ProducerReasonSpec,
)

from .security_audit import (
    CorrelationHmac,
    OverflowAuditAppend,
    OverflowBucket,
    SecurityAuditAppend,
    SecurityAuditOutcomeUnknown,
    SecurityAuditRefused,
    SecurityAuditUnavailable,
    StoredAuditAppend,
)


Connection = psycopg.Connection[tuple[object, ...]]
ConnectionFactory = Callable[[], Connection]
_READ_COMMITTED = "SET TRANSACTION ISOLATION LEVEL READ COMMITTED"
_SESSION_USER = "SELECT SESSION_USER::text"
_APPEND = """
    SELECT *
    FROM ofarm_security.append_pretenant_failure(%s, %s, %s, %s, %s)
"""
_PRODUCTION_CONNECTION_PARAMETERS = MappingProxyType(
    {
        "connect_timeout": 5,
        "options": "-c statement_timeout=2000 -c lock_timeout=250",
    }
)


def production_audit_connection_factory(dsn: str) -> ConnectionFactory:
    """Create direct producer connections with the fixed request-time policy."""
    def connect() -> Connection:
        return psycopg.connect(dsn, **_PRODUCTION_CONNECTION_PARAMETERS)
    return connect


def _aware_time(value: object) -> datetime | None:
    if (
        type(value) is datetime
        and value.tzinfo is not None
        and value.utcoffset() is not None
    ):
        return value
    return None


def _require_session_user(
    connection: Connection,
    producer: ProducerReasonSpec,
) -> None:
    cursor = connection.execute(_SESSION_USER)
    row = cursor.fetchone()
    duplicate = cursor.fetchone()
    if row != (producer.session_user,) or duplicate is not None:
        raise SecurityAuditUnavailable()


def _overflow_bucket(
    result: SecurityAuditAppend | None,
) -> OverflowBucket | None:
    if isinstance(result, OverflowAuditAppend):
        return result.bucket
    return None


def _map_result(
    row: object,
    duplicate: object,
    event_id: UUID,
    producer: ProducerReasonSpec,
) -> SecurityAuditAppend:
    if type(row) is not tuple or len(row) != 6 or duplicate is not None:
        raise SecurityAuditUnavailable()
    (
        stored_event_id,
        observed_at,
        purge_after,
        stored_individually,
        overflow_bucket_start,
        count_unknown,
    ) = row
    if (
        stored_individually is True
        and stored_event_id == event_id
        and (observed := _aware_time(observed_at)) is not None
        and (purge := _aware_time(purge_after)) is not None
        and overflow_bucket_start is None
        and count_unknown is False
    ):
        return StoredAuditAppend(event_id, observed, purge)
    if (
        stored_individually is False
        and stored_event_id is None
        and observed_at is None
        and purge_after is None
        and (bucket_start := _aware_time(overflow_bucket_start)) is not None
        and type(count_unknown) is bool
    ):
        return OverflowAuditAppend(
            event_id,
            OverflowBucket(
                producer.producer,
                producer.component,
                bucket_start,
            ),
            count_unknown,
        )
    raise SecurityAuditUnavailable()


class PreTenantAuditClient:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        producer: ProducerReasonSpec,
    ) -> None:
        if (
            type(producer) is not ProducerReasonSpec
            or producer not in SECURITY_AUDIT_CONTRACT.reason_matrix
        ):
            raise ValueError("security-audit producer registration is invalid")
        self._connection_factory = connection_factory
        self._producer = producer

    def _append_once(
        self,
        event_id: UUID,
        parameters: tuple[object, ...],
    ) -> SecurityAuditAppend:
        submitted = False
        result: SecurityAuditAppend | None = None
        try:
            with self._connection_factory() as connection:
                if connection.autocommit is not False:
                    raise SecurityAuditUnavailable()
                with connection.transaction():
                    connection.execute(_READ_COMMITTED)
                    _require_session_user(connection, self._producer)
                    submitted = True
                    cursor = connection.execute(_APPEND, parameters)
                    result = _map_result(
                        cursor.fetchone(),
                        cursor.fetchone(),
                        event_id,
                        self._producer,
                    )
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            if submitted:
                raise SecurityAuditOutcomeUnknown(
                    event_id,
                    _overflow_bucket(result),
                ) from exc
            raise SecurityAuditUnavailable() from exc
        except psycopg.Error as exc:
            if submitted:
                raise SecurityAuditRefused() from exc
            raise SecurityAuditUnavailable() from exc
        if result is None:
            raise SecurityAuditUnavailable()
        return result

    def append(
        self,
        reason: str,
        correlation_hmac: CorrelationHmac,
    ) -> SecurityAuditAppend:
        if (
            reason not in self._producer.reasons
            or type(correlation_hmac) is not CorrelationHmac
        ):
            raise ValueError("security-audit append input is invalid")
        event_id = uuid4()
        hmac_policy = SECURITY_AUDIT_CONTRACT.correlation_hmac
        parameters = (
            event_id,
            reason,
            correlation_hmac.value,
            hmac_policy.domain,
            correlation_hmac.key_version,
        )
        try:
            return self._append_once(event_id, parameters)
        except SecurityAuditOutcomeUnknown as first:
            possible_bucket = first.possible_overflow_bucket
        try:
            return self._append_once(event_id, parameters)
        except SecurityAuditOutcomeUnknown as second:
            possible_bucket = second.possible_overflow_bucket or possible_bucket
            raise SecurityAuditOutcomeUnknown(
                event_id,
                possible_bucket,
            ) from second.__cause__
        except SecurityAuditUnavailable as exc:
            raise SecurityAuditOutcomeUnknown(
                event_id,
                possible_bucket,
            ) from exc
        except SecurityAuditRefused as exc:
            raise SecurityAuditOutcomeUnknown(
                event_id,
                possible_bucket,
            ) from exc
