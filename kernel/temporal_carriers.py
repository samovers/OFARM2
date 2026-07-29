"""Inactive pure valid-time carrier selection for one intervention binding.

This module is deliberately absent from production and legacy runtime import
closures.  It implements only the reviewed
``ofarm.temporal-carrier-selection.intervention.v0.1`` candidate.  Callers
provide source records; they never provide or override contract, matrix, row,
selector, field-path, or window-meaning authority.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final


BINDING_SCHEMA_VERSION: Final = (
    "ofarm.temporal-carrier-selection-binding.v0.1"
)
BINDING_ID: Final = "ofarm.temporal-carrier-selection.intervention.v0.1"
BINDING_ARTIFACT_DIGEST: Final = (
    "sha256:9886aace0670b6a83f17cd33cbc67aa62fafcfd0ea873faed9194c2aaa07efe5"
)
COORDINATE_SCHEMA_VERSION: Final = "ofarm.temporal-coordinate.v0.1"
COORDINATE_SCHEMA_DIGEST: Final = (
    "sha256:b81e4c7b0aacebb11ff8bf0d186cdb36150fade31180552b46f7be9e13c551eb"
)
CARRIER_MATRIX_ID: Final = "ofarm.temporal-carrier-matrix.adr0002.v0.1"
CARRIER_MATRIX_DIGEST: Final = (
    "sha256:7cb26513b5abdbcadecaf6f9b47d874a742ba8fa05a332c9130deebe449d7fc6"
)
CARRIER_MATRIX_ROW_ID: Final = "INTERVENTION_EVENT"
ENVELOPE_SCHEMA_VERSION: Final = "ofarm.semanticeventenvelope.v0.1"
ENVELOPE_SCHEMA_DIGEST: Final = (
    "sha256:75662a6c4952a62b7e8f8e9de99c23c98899c692914a98ba4b752873f48bd1a4"
)
EXECUTION_SCHEMA_VERSION: Final = "ofarm.executionrecordpayload.v0.1"
EXECUTION_SCHEMA_DIGEST: Final = (
    "sha256:ca62f01d056794ee588d55c3f5df652fc039124b76af5631d417714bc7059ff0"
)
EVENT_OCCURRENCE: Final = "EVENT_OCCURRENCE"
STATE_OVERLAP: Final = "STATE_OVERLAP"

_UTC_INSTANT = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"(\.[0-9]{1,6})?Z$"
)


class TemporalCarrierError(ValueError):
    """The source records cannot satisfy the reviewed carrier binding."""


@dataclass(frozen=True, slots=True)
class CarrierBindingIdentity:
    binding_schema_version: str = BINDING_SCHEMA_VERSION
    binding_id: str = BINDING_ID
    binding_artifact_digest: str = BINDING_ARTIFACT_DIGEST
    coordinate_schema_version: str = COORDINATE_SCHEMA_VERSION
    coordinate_schema_digest: str = COORDINATE_SCHEMA_DIGEST
    carrier_matrix_id: str = CARRIER_MATRIX_ID
    carrier_matrix_digest: str = CARRIER_MATRIX_DIGEST
    carrier_matrix_row_id: str = CARRIER_MATRIX_ROW_ID
    envelope_schema_version: str = ENVELOPE_SCHEMA_VERSION
    envelope_schema_digest: str = ENVELOPE_SCHEMA_DIGEST
    execution_schema_version: str = EXECUTION_SCHEMA_VERSION
    execution_schema_digest: str = EXECUTION_SCHEMA_DIGEST


INTERVENTION_BINDING: Final = CarrierBindingIdentity()


@dataclass(frozen=True, slots=True)
class StrictUtcInstant:
    text: str
    _instant: datetime = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.text) is not str or _UTC_INSTANT.fullmatch(self.text) is None:
            raise TemporalCarrierError("instant is not canonical UTC")
        try:
            instant = datetime.fromisoformat(self.text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TemporalCarrierError("instant is not a real UTC instant") from exc
        object.__setattr__(self, "_instant", instant)

    @property
    def instant(self) -> datetime:
        return self._instant


@dataclass(frozen=True, slots=True)
class BoundedHalfOpenInterval:
    start: StrictUtcInstant
    end: StrictUtcInstant

    def __post_init__(self) -> None:
        if (
            type(self.start) is not StrictUtcInstant
            or type(self.end) is not StrictUtcInstant
        ):
            raise TemporalCarrierError(
                "half-open interval bounds must be strict UTC instants"
            )
        if self.end.instant <= self.start.instant:
            raise TemporalCarrierError(
                "half-open interval must be non-empty and ordered"
            )


@dataclass(frozen=True, slots=True)
class InterventionValidTime:
    occurrence: StrictUtcInstant
    execution_interval: BoundedHalfOpenInterval

    def __post_init__(self) -> None:
        if type(self.occurrence) is not StrictUtcInstant:
            raise TemporalCarrierError(
                "intervention occurrence must be a strict UTC instant"
            )
        if type(self.execution_interval) is not BoundedHalfOpenInterval:
            raise TemporalCarrierError(
                "intervention execution must be a bounded half-open interval"
            )

    @property
    def binding(self) -> CarrierBindingIdentity:
        return INTERVENTION_BINDING

    @property
    def occurrence_window_meaning(self) -> str:
        return EVENT_OCCURRENCE

    @property
    def execution_window_meaning(self) -> str:
        return STATE_OVERLAP


def _object(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise TemporalCarrierError(f"{label} must be an object")
    return value


def _exact(value: object, expected: str, label: str) -> None:
    if type(value) is not str or value != expected:
        raise TemporalCarrierError(f"{label} differs from the reviewed binding")


def _instant(value: object, label: str) -> StrictUtcInstant:
    try:
        return StrictUtcInstant(value)  # type: ignore[arg-type]
    except TemporalCarrierError as exc:
        raise TemporalCarrierError(f"{label} {exc}") from exc


def select_intervention_valid_time(
    envelope: dict[str, object],
    execution_payload: dict[str, object],
) -> InterventionValidTime:
    """Select both reviewed intervention carriers or refuse without a result."""
    envelope_object = _object(envelope, "SemanticEventEnvelope")
    payload_object = _object(execution_payload, "ExecutionRecordPayload")

    _exact(
        envelope_object.get("schemaVersion"),
        ENVELOPE_SCHEMA_VERSION,
        "SemanticEventEnvelope schemaVersion",
    )
    _exact(
        envelope_object.get("primaryEventFamily"),
        "InterventionEvent",
        "SemanticEventEnvelope primaryEventFamily",
    )
    _exact(
        payload_object.get("schemaVersion"),
        EXECUTION_SCHEMA_VERSION,
        "ExecutionRecordPayload schemaVersion",
    )
    _exact(
        payload_object.get("recordClass"),
        "OPERATION_CLAIM",
        "ExecutionRecordPayload recordClass",
    )

    time_semantics = _object(
        envelope_object.get("timeSemantics"),
        "SemanticEventEnvelope timeSemantics",
    )
    if "effectiveFrom" in time_semantics or "effectiveUntil" in time_semantics:
        raise TemporalCarrierError(
            "envelope effective bounds are unsupported by this binding"
        )
    occurrence = _instant(
        time_semantics.get("eventTime"),
        "SemanticEventEnvelope eventTime",
    )

    interval = _object(
        payload_object.get("effectiveTimeInterval"),
        "ExecutionRecordPayload effectiveTimeInterval",
    )
    _exact(
        interval.get("timeBasis"),
        "EXECUTION_INTERVAL",
        "ExecutionRecordPayload effectiveTimeInterval timeBasis",
    )
    execution_interval = BoundedHalfOpenInterval(
        _instant(
            interval.get("start"),
            "ExecutionRecordPayload effectiveTimeInterval start",
        ),
        _instant(
            interval.get("end"),
            "ExecutionRecordPayload effectiveTimeInterval end",
        ),
    )
    return InterventionValidTime(occurrence, execution_interval)


def event_in_window(
    event: StrictUtcInstant,
    window: BoundedHalfOpenInterval,
) -> bool:
    if type(event) is not StrictUtcInstant:
        raise TemporalCarrierError("event must be a strict UTC instant")
    if type(window) is not BoundedHalfOpenInterval:
        raise TemporalCarrierError("window must be a bounded half-open interval")
    return window.start.instant <= event.instant < window.end.instant


def state_at(
    interval: BoundedHalfOpenInterval,
    valid_at: StrictUtcInstant,
) -> bool:
    if type(interval) is not BoundedHalfOpenInterval:
        raise TemporalCarrierError("state must be a bounded half-open interval")
    if type(valid_at) is not StrictUtcInstant:
        raise TemporalCarrierError("valid_at must be a strict UTC instant")
    return interval.start.instant <= valid_at.instant < interval.end.instant


def state_overlaps(
    interval: BoundedHalfOpenInterval,
    window: BoundedHalfOpenInterval,
) -> bool:
    if (
        type(interval) is not BoundedHalfOpenInterval
        or type(window) is not BoundedHalfOpenInterval
    ):
        raise TemporalCarrierError(
            "state and window must be bounded half-open intervals"
        )
    return (
        interval.start.instant < window.end.instant
        and window.start.instant < interval.end.instant
    )
