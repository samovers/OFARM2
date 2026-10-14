"""Explicit synthetic truth tables; not substitutes for actual-role controls."""
from __future__ import annotations

from dataclasses import astuple
from datetime import UTC, datetime
from uuid import UUID

import pytest

from kernel.tenant_physical_outcome import PhysicalObservation, _combine
from kernel.tenant_uow import GovernedWriteBatch


_BATCH = GovernedWriteBatch(
    UUID("00000000-0000-4000-8000-000000000001"), "fixture-batch", 123,
    "fixture-party", "PHYSICAL_TEST", "fixture-request", "sha256:" + "1" * 64,
    2, datetime(2026, 10, 14, tzinfo=UTC),
)
_ROW = (*astuple(_BATCH)[:2], str(_BATCH.full_xid), *astuple(_BATCH)[3:])


@pytest.mark.parametrize("raw", (None, "in progress", "committed", "aborted"))
@pytest.mark.parametrize("batch_kind", ("matching", "absent", "partial", "different", "duplicate"))
def test_ps12_complete_truth_table_keeps_physical_and_occurrence_distinct(raw, batch_kind):
    observation = PhysicalObservation(
        original_batch=_BATCH, raw_status=raw, status_received=True,
        physical_status="ABORTED" if raw == "aborted" else "UNKNOWN",
    )
    rows = {
        "matching": [_ROW], "absent": [], "partial": [_ROW[:-1]],
        "different": [(*_ROW[:7], _ROW[7] + 1, _ROW[8])],
        "duplicate": [_ROW, _ROW],
    }[batch_kind]
    actual = _combine(observation, rows)
    if batch_kind in ("different", "duplicate"):
        assert actual.physical_status == "UNKNOWN"
        assert actual.batch_observation == "CONFLICT"
        assert actual.integrity_problem == "BATCH_DIFFERS"
    elif batch_kind == "matching":
        assert actual.physical_status == ("UNKNOWN" if raw == "aborted" else "COMMITTED")
        assert actual.batch_observation == "MATCHING_COMMITTED"
        assert actual.integrity_problem == ("STATUS_CONFLICT" if raw == "aborted" else None)
    else:
        assert actual.physical_status == ("ABORTED" if raw == "aborted" else "UNKNOWN")
        assert actual.batch_observation == ("ABSENT_AT_OBSERVATION" if batch_kind == "absent" else "UNAVAILABLE")
    assert actual.original_batch is _BATCH
    assert actual.raw_status == raw and actual.status_received


@pytest.mark.parametrize("replacement", ([], {}, bytearray(b"mutable"), 1, None))
def test_ps12_malformed_complete_row_never_retains_mutable_evidence(replacement):
    observation = PhysicalObservation(original_batch=_BATCH, raw_status="committed", status_received=True)
    altered = (*_ROW[:1], replacement, *_ROW[2:])
    actual = _combine(observation, [altered])
    assert actual.physical_status == "UNKNOWN"
    assert actual.batch_observation == "UNAVAILABLE"
    assert actual.observed_batch is None
    assert actual.observer_failure == "BATCH_UNAVAILABLE"
