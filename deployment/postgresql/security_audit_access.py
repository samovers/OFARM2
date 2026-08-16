"""Shared validation for bounded security-audit access pages.

This module owns only protocol-neutral immutable values, hostile carrier
validation, descending-page validation, and canonical event documents.  SQL,
connections, access purposes, protocol limits, output schemas, roles, and
approval state remain owned by their respective reader or export modules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

from deployment.postgresql.audit_contract import (
    ACCESS_INTENT_EXPIRY_SECONDS,
    CORRELATION_HMAC_DOMAIN,
    CORRELATION_HMAC_KNOWN_KEY_VERSIONS,
    CORRELATION_HMAC_LENGTH_BYTES,
    EVENT_FORMAT_IDENTITY,
    PURGE_BATCH_ROWS,
    REDACTION_POLICY_IDENTITY,
    RETENTION_POLICY_IDENTITY,
    RETENTION_SECONDS,
    SECURITY_AUDIT_CONTRACT,
)


_CURSOR_PATTERN = re.compile(
    r"\A"
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z)"
    r"/"
    r"(?P<event_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12})"
    r"\Z"
)
_CLOSED_TOKEN = re.compile(r"\A[A-Z][A-Z0-9_]*\Z")
_PRETENANT_PAIRS = frozenset(
    (entry.producer, entry.component)
    for entry in SECURITY_AUDIT_CONTRACT.reason_matrix
)
_EVENT_KINDS = frozenset(SECURITY_AUDIT_CONTRACT.event_kinds)
_ACCESS_PROTOCOLS = {
    (protocol.purpose_identity, protocol.function_identity): (
        protocol.result_limit.max_rows,
        protocol.result_limit.max_bytes,
    )
    for protocol in SECURITY_AUDIT_CONTRACT.access_protocols
}
_INTERVAL_EVENT_KINDS = frozenset(
    {"AUDIT_GAP", "OVERFLOW_STARTED", "OVERFLOW_ENDED"}
)
_SECURITY_OPERATIONS_PRODUCER = "SECURITY_OPERATIONS_V1"
_AUDIT_CONTROL_COMPONENT = "AUDIT_CONTROL"
_AUDIT_RETENTION_COMPONENT = "AUDIT_RETENTION"


def _utc_timestamp(value: object) -> datetime:
    if type(value) is not datetime:
        raise ValueError("security-audit timestamp is invalid")
    try:
        offset = value.utcoffset()
        if offset is None:
            raise ValueError("security-audit timestamp is naive")
        return value.astimezone(timezone.utc)
    except (OverflowError, TypeError, ValueError):
        raise ValueError("security-audit timestamp is invalid") from None


def _uuid(value: object) -> UUID:
    if type(value) is not UUID or value.int == 0:
        raise ValueError("security-audit UUID is invalid")
    return value


def _integer(
    value: object,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if type(value) is not int:
        raise ValueError("security-audit integer is invalid")
    if minimum is not None and value < minimum:
        raise ValueError("security-audit integer is below its bound")
    if maximum is not None and value > maximum:
        raise ValueError("security-audit integer exceeds its bound")
    return value


def _bytes(value: object, length: int) -> bytes:
    if type(value) is not bytes or len(value) != length:
        raise ValueError("security-audit digest is invalid")
    return value


def _closed_token(value: object, *, maximum_bytes: int = 64) -> str:
    if (
        type(value) is not str
        or len(value) > maximum_bytes
        or _CLOSED_TOKEN.fullmatch(value) is None
    ):
        raise ValueError("security-audit token is invalid")
    return value


def security_audit_timestamp_text(value: datetime) -> str:
    """Render one already-normalized timestamp in the accepted wire form."""

    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class SecurityAuditAccessCursor:
    """One immutable normalized descending-page cursor."""

    observed_at: datetime
    event_id: UUID

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _utc_timestamp(self.observed_at))
        _uuid(self.event_id)

    def render(self) -> str:
        return f"{security_audit_timestamp_text(self.observed_at)}/{self.event_id}"

    @classmethod
    def parse(cls, value: object) -> SecurityAuditAccessCursor:
        if type(value) is not str:
            raise ValueError("security-audit cursor is invalid")
        matched = _CURSOR_PATTERN.fullmatch(value)
        if matched is None:
            raise ValueError("security-audit cursor is noncanonical")
        try:
            observed_at = datetime.strptime(
                matched.group("timestamp"), "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=timezone.utc)
            event_id = UUID(matched.group("event_id"))
        except (ValueError, OverflowError):
            raise ValueError("security-audit cursor is invalid") from None
        cursor = cls(observed_at=observed_at, event_id=event_id)
        if cursor.render() != value:
            raise ValueError("security-audit cursor is noncanonical")
        return cursor


@dataclass(frozen=True, slots=True)
class SecurityAuditAccessIntent:
    """The exact validated result of one committed access-intent function."""

    access_event_id: UUID
    data_cut: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class SecurityAuditEventReport:
    """One validated immutable 30-field database event carrier."""

    event_id: UUID
    observed_at: datetime
    purge_after: datetime
    event_kind: str
    producer: str
    component: str
    reason: str | None
    correlation_hmac_domain: str | None
    correlation_hmac_key_version: int | None
    correlation_hmac_value: bytes | None
    event_format_identity: str
    redaction_policy_identity: str
    retention_policy_identity: str
    append_input_fingerprint: bytes
    access_purpose: str | None
    access_function_identity: str | None
    access_data_cut: datetime | None
    access_cursor_observed_at: datetime | None
    access_cursor_event_id: UUID | None
    access_max_rows: int | None
    access_max_bytes: int | None
    access_expires_at: datetime | None
    retention_cutoff: datetime | None
    retention_deleted_count: int | None
    interval_start: datetime | None
    interval_end: datetime | None
    interval_event_count: int | None
    interval_count_unknown: bool | None
    affected_producer: str | None
    affected_component: str | None


def security_audit_cursor_values(
    cursor: SecurityAuditAccessCursor | None,
) -> tuple[datetime | None, UUID | None]:
    """Return the immutable database cursor pair without reinterpretation."""

    if cursor is None:
        return None, None
    return cursor.observed_at, cursor.event_id


def validate_security_audit_access_intent(
    row: object,
    second_row: object,
) -> SecurityAuditAccessIntent:
    """Validate exactly one three-field committed-intent result."""

    if type(row) is not tuple or len(row) != 3 or second_row is not None:
        raise ValueError("security-audit access-intent shape is invalid")
    access_event_id, data_cut, expires_at = row
    validated_id = _uuid(access_event_id)
    normalized_cut = _utc_timestamp(data_cut)
    normalized_expiry = _utc_timestamp(expires_at)
    if normalized_expiry != normalized_cut + timedelta(
        seconds=ACCESS_INTENT_EXPIRY_SECONDS
    ):
        raise ValueError("security-audit access-intent duration is invalid")
    return SecurityAuditAccessIntent(
        access_event_id=validated_id,
        data_cut=normalized_cut,
        expires_at=normalized_expiry,
    )


def _validated_access_fields(
    event_kind: str,
    values: tuple[object, ...],
) -> tuple[
    str | None,
    str | None,
    datetime | None,
    datetime | None,
    UUID | None,
    int | None,
    int | None,
    datetime | None,
]:
    (
        purpose,
        function_identity,
        data_cut,
        cursor_observed_at,
        cursor_event_id,
        max_rows,
        max_bytes,
        expires_at,
    ) = values
    if event_kind != "AUDIT_ACCESS":
        if any(value is not None for value in values):
            raise ValueError("non-access event has access fields")
        return (None, None, None, None, None, None, None, None)

    if type(purpose) is not str or type(function_identity) is not str:
        raise ValueError("access protocol identity is invalid")
    limits = _ACCESS_PROTOCOLS.get((purpose, function_identity))
    if limits is None:
        raise ValueError("access protocol identity is unknown")
    validated_rows = _integer(max_rows, minimum=1, maximum=limits[0])
    validated_bytes = _integer(max_bytes, minimum=1, maximum=limits[1])
    normalized_cut = _utc_timestamp(data_cut)
    normalized_expiry = _utc_timestamp(expires_at)
    if normalized_expiry != normalized_cut + timedelta(
        seconds=ACCESS_INTENT_EXPIRY_SECONDS
    ):
        raise ValueError("access event expiry is invalid")
    if (cursor_observed_at is None) != (cursor_event_id is None):
        raise ValueError("access event cursor is incomplete")
    if cursor_observed_at is None:
        normalized_cursor_at = None
        validated_cursor_id = None
    else:
        normalized_cursor_at = _utc_timestamp(cursor_observed_at)
        validated_cursor_id = _uuid(cursor_event_id)
    return (
        purpose,
        function_identity,
        normalized_cut,
        normalized_cursor_at,
        validated_cursor_id,
        validated_rows,
        validated_bytes,
        normalized_expiry,
    )


def _validated_retention_fields(
    event_kind: str,
    cutoff: object,
    deleted_count: object,
) -> tuple[datetime | None, int | None]:
    if event_kind != "AUDIT_RETENTION":
        if cutoff is not None or deleted_count is not None:
            raise ValueError("non-retention event has retention fields")
        return None, None
    return (
        _utc_timestamp(cutoff),
        _integer(deleted_count, minimum=0, maximum=PURGE_BATCH_ROWS),
    )


def _validated_interval_fields(
    event_kind: str,
    values: tuple[object, ...],
) -> tuple[
    datetime | None,
    datetime | None,
    int | None,
    bool | None,
    str | None,
    str | None,
]:
    (
        interval_start,
        interval_end,
        event_count,
        count_unknown,
        affected_producer,
        affected_component,
    ) = values
    if event_kind not in _INTERVAL_EVENT_KINDS:
        if any(value is not None for value in values):
            raise ValueError("non-interval event has interval fields")
        return None, None, None, None, None, None

    normalized_start = _utc_timestamp(interval_start)
    normalized_end = _utc_timestamp(interval_end)
    if normalized_start >= normalized_end or type(count_unknown) is not bool:
        raise ValueError("security-audit interval is invalid")

    if event_kind == "OVERFLOW_STARTED":
        if count_unknown is not False or event_count is not None:
            raise ValueError("overflow-start count posture is invalid")
        validated_count = None
    elif count_unknown:
        if event_count is not None:
            raise ValueError("unknown interval count must be absent")
        validated_count = None
    else:
        validated_count = _integer(event_count, minimum=0)

    if event_kind == "AUDIT_GAP":
        if affected_producer is not None or affected_component is not None:
            raise ValueError("audit gap has affected attribution")
        validated_producer = None
        validated_component = None
    else:
        if (affected_producer, affected_component) not in _PRETENANT_PAIRS:
            raise ValueError("overflow attribution is invalid")
        validated_producer = cast(str, affected_producer)
        validated_component = cast(str, affected_component)

    return (
        normalized_start,
        normalized_end,
        validated_count,
        count_unknown,
        validated_producer,
        validated_component,
    )


def _validated_event(
    row: object,
    *,
    intent: SecurityAuditAccessIntent,
    input_cursor: SecurityAuditAccessCursor | None,
    previous_key: tuple[datetime, int] | None,
) -> tuple[SecurityAuditEventReport, tuple[datetime, int]]:
    if type(row) is not tuple or len(row) != 30:
        raise ValueError("security-audit event carrier shape is invalid")
    (
        event_id,
        observed_at,
        purge_after,
        event_kind,
        producer,
        component,
        reason,
        hmac_domain,
        hmac_key_version,
        hmac_value,
        event_format_identity,
        redaction_policy_identity,
        retention_policy_identity,
        append_input_fingerprint,
        access_purpose,
        access_function_identity,
        access_data_cut,
        access_cursor_observed_at,
        access_cursor_event_id,
        access_max_rows,
        access_max_bytes,
        access_expires_at,
        retention_cutoff,
        retention_deleted_count,
        interval_start,
        interval_end,
        interval_event_count,
        interval_count_unknown,
        affected_producer,
        affected_component,
    ) = row

    validated_id = _uuid(event_id)
    normalized_observed_at = _utc_timestamp(observed_at)
    normalized_purge_after = _utc_timestamp(purge_after)
    if (
        normalized_purge_after
        != normalized_observed_at + timedelta(seconds=RETENTION_SECONDS)
        or normalized_purge_after <= intent.expires_at
        or normalized_observed_at > intent.data_cut
    ):
        raise ValueError("security-audit event time bounds are invalid")
    if type(event_kind) is not str or event_kind not in _EVENT_KINDS:
        raise ValueError("security-audit event kind is invalid")

    if event_kind == "PRE_TENANT_FAILURE":
        if (producer, component) not in _PRETENANT_PAIRS:
            raise ValueError("pre-tenant producer attribution is invalid")
        validated_producer = cast(str, producer)
        validated_component = cast(str, component)
        validated_reason = _closed_token(reason)
        if hmac_domain != CORRELATION_HMAC_DOMAIN:
            raise ValueError("correlation HMAC domain is invalid")
        validated_hmac_version = _integer(hmac_key_version)
        if validated_hmac_version not in CORRELATION_HMAC_KNOWN_KEY_VERSIONS:
            raise ValueError("correlation HMAC key version is unknown")
        validated_hmac = _bytes(hmac_value, CORRELATION_HMAC_LENGTH_BYTES)
        validated_hmac_domain = CORRELATION_HMAC_DOMAIN
    else:
        if any(
            value is not None
            for value in (reason, hmac_domain, hmac_key_version, hmac_value)
        ):
            raise ValueError("maintenance event has pre-tenant fields")
        if event_kind == "AUDIT_RETENTION":
            expected_component = _AUDIT_RETENTION_COMPONENT
        else:
            expected_component = _AUDIT_CONTROL_COMPONENT
        if (
            producer != _SECURITY_OPERATIONS_PRODUCER
            or component != expected_component
        ):
            raise ValueError("maintenance event attribution is invalid")
        validated_producer = _SECURITY_OPERATIONS_PRODUCER
        validated_component = expected_component
        validated_reason = None
        validated_hmac_domain = None
        validated_hmac_version = None
        validated_hmac = None

    if (
        event_format_identity != EVENT_FORMAT_IDENTITY
        or redaction_policy_identity != REDACTION_POLICY_IDENTITY
        or retention_policy_identity != RETENTION_POLICY_IDENTITY
    ):
        raise ValueError("security-audit event policy identity is invalid")
    validated_fingerprint = _bytes(
        append_input_fingerprint,
        SECURITY_AUDIT_CONTRACT.append_input_fingerprint.length_bytes,
    )

    access_fields = _validated_access_fields(
        event_kind,
        (
            access_purpose,
            access_function_identity,
            access_data_cut,
            access_cursor_observed_at,
            access_cursor_event_id,
            access_max_rows,
            access_max_bytes,
            access_expires_at,
        ),
    )
    retention_fields = _validated_retention_fields(
        event_kind,
        retention_cutoff,
        retention_deleted_count,
    )
    interval_fields = _validated_interval_fields(
        event_kind,
        (
            interval_start,
            interval_end,
            interval_event_count,
            interval_count_unknown,
            affected_producer,
            affected_component,
        ),
    )

    key = (normalized_observed_at, validated_id.int)
    if previous_key is not None and key >= previous_key:
        raise ValueError("security-audit page ordering is invalid")
    if input_cursor is not None and key >= (
        input_cursor.observed_at,
        input_cursor.event_id.int,
    ):
        raise ValueError("security-audit row is outside the cursor")

    return (
        SecurityAuditEventReport(
            event_id=validated_id,
            observed_at=normalized_observed_at,
            purge_after=normalized_purge_after,
            event_kind=event_kind,
            producer=validated_producer,
            component=validated_component,
            reason=validated_reason,
            correlation_hmac_domain=validated_hmac_domain,
            correlation_hmac_key_version=validated_hmac_version,
            correlation_hmac_value=validated_hmac,
            event_format_identity=EVENT_FORMAT_IDENTITY,
            redaction_policy_identity=REDACTION_POLICY_IDENTITY,
            retention_policy_identity=RETENTION_POLICY_IDENTITY,
            append_input_fingerprint=validated_fingerprint,
            access_purpose=access_fields[0],
            access_function_identity=access_fields[1],
            access_data_cut=access_fields[2],
            access_cursor_observed_at=access_fields[3],
            access_cursor_event_id=access_fields[4],
            access_max_rows=access_fields[5],
            access_max_bytes=access_fields[6],
            access_expires_at=access_fields[7],
            retention_cutoff=retention_fields[0],
            retention_deleted_count=retention_fields[1],
            interval_start=interval_fields[0],
            interval_end=interval_fields[1],
            interval_event_count=interval_fields[2],
            interval_count_unknown=interval_fields[3],
            affected_producer=interval_fields[4],
            affected_component=interval_fields[5],
        ),
        key,
    )


def validate_security_audit_event_page(
    rows: object,
    *,
    intent: SecurityAuditAccessIntent,
    input_cursor: SecurityAuditAccessCursor | None,
    maximum_rows: int,
) -> tuple[
    tuple[SecurityAuditEventReport, ...],
    SecurityAuditAccessCursor | None,
]:
    """Validate one fixed-bounded descending page and derive its final cursor."""

    if type(rows) is not list or len(rows) > maximum_rows:
        raise ValueError("security-audit result row bound is invalid")
    events: list[SecurityAuditEventReport] = []
    previous_key: tuple[datetime, int] | None = None
    for row in rows:
        event, previous_key = _validated_event(
            row,
            intent=intent,
            input_cursor=input_cursor,
            previous_key=previous_key,
        )
        events.append(event)
    validated_events = tuple(events)
    next_cursor = (
        None
        if not validated_events
        else SecurityAuditAccessCursor(
            observed_at=validated_events[-1].observed_at,
            event_id=validated_events[-1].event_id,
        )
    )
    return validated_events, next_cursor


def _optional_timestamp(value: datetime | None) -> str | None:
    return None if value is None else security_audit_timestamp_text(value)


def _optional_uuid(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def security_audit_event_document(
    event: SecurityAuditEventReport,
) -> dict[str, object]:
    """Return the accepted canonical document for one validated event."""

    return {
        "accessCursorEventId": _optional_uuid(event.access_cursor_event_id),
        "accessCursorObservedAt": _optional_timestamp(
            event.access_cursor_observed_at
        ),
        "accessDataCut": _optional_timestamp(event.access_data_cut),
        "accessExpiresAt": _optional_timestamp(event.access_expires_at),
        "accessFunctionIdentity": event.access_function_identity,
        "accessMaxBytes": (
            None if event.access_max_bytes is None else str(event.access_max_bytes)
        ),
        "accessMaxRows": event.access_max_rows,
        "accessPurpose": event.access_purpose,
        "affectedComponent": event.affected_component,
        "affectedProducer": event.affected_producer,
        "appendInputFingerprint": event.append_input_fingerprint.hex(),
        "component": event.component,
        "correlationHmacDomain": event.correlation_hmac_domain,
        "correlationHmacKeyVersion": event.correlation_hmac_key_version,
        "correlationHmacValue": (
            None
            if event.correlation_hmac_value is None
            else event.correlation_hmac_value.hex()
        ),
        "eventFormatIdentity": event.event_format_identity,
        "eventId": str(event.event_id),
        "eventKind": event.event_kind,
        "intervalCountUnknown": event.interval_count_unknown,
        "intervalEnd": _optional_timestamp(event.interval_end),
        "intervalEventCount": (
            None
            if event.interval_event_count is None
            else str(event.interval_event_count)
        ),
        "intervalStart": _optional_timestamp(event.interval_start),
        "observedAt": security_audit_timestamp_text(event.observed_at),
        "producer": event.producer,
        "purgeAfter": security_audit_timestamp_text(event.purge_after),
        "reason": event.reason,
        "redactionPolicyIdentity": event.redaction_policy_identity,
        "retentionCutoff": _optional_timestamp(event.retention_cutoff),
        "retentionDeletedCount": (
            None
            if event.retention_deleted_count is None
            else str(event.retention_deleted_count)
        ),
        "retentionPolicyIdentity": event.retention_policy_identity,
    }


__all__ = (
    "SecurityAuditAccessCursor",
    "SecurityAuditAccessIntent",
    "SecurityAuditEventReport",
    "security_audit_cursor_values",
    "security_audit_event_document",
    "security_audit_timestamp_text",
    "validate_security_audit_access_intent",
    "validate_security_audit_event_page",
)
