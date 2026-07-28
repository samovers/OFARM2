from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from conformance import temporal_contract_candidate_check as temporal


PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _schema() -> dict:
    return json.loads(temporal.SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(
        _schema(),
        format_checker=jsonschema.FormatChecker(),
    )


def _coordinate() -> dict:
    return {
        "schemaVersion": temporal.CONTRACT_VERSION,
        "validCut": {
            "cutType": "POINT",
            "validAt": "2026-07-28T10:30:00.123456Z",
        },
        "knowledgeCut": {
            "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
            "position": 42,
        },
    }


def test_temporal_candidate_governance_is_complete_and_inactive():
    temporal.validate_candidate_governance()


def test_point_and_window_coordinates_validate_against_schema_and_semantics():
    point = _coordinate()
    window = copy.deepcopy(point)
    window["validCut"] = {
        "cutType": "WINDOW",
        "windowStart": "2026-01-01T00:00:00Z",
        "windowEnd": "2027-01-01T00:00:00Z",
    }
    window["knowledgeCut"]["position"] = 0

    for value in (point, window):
        _validator().validate(value)
        temporal.validate_temporal_coordinate(value)


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        (
            lambda value: value["validCut"].update(
                {"validAt": "2026-07-28T10:30:00"}
            ),
            "canonical UTC",
        ),
        (
            lambda value: value["validCut"].update(
                {"validAt": "2026-12-31T23:59:60Z"}
            ),
            "canonical UTC",
        ),
        (
            lambda value: value["validCut"].update(
                {"validAt": "2026-07-28T10:30:00.1234567Z"}
            ),
            "canonical UTC",
        ),
        (
            lambda value: value["validCut"].update(
                {"windowStart": "2026-01-01T00:00:00Z"}
            ),
            "unknown or missing fields",
        ),
        (
            lambda value: value["knowledgeCut"].update({"position": -1}),
            "outside int64",
        ),
        (
            lambda value: value["knowledgeCut"].update({"position": True}),
            "outside int64",
        ),
        (
            lambda value: value["knowledgeCut"].update(
                {"tenantId": "tenant:demo"}
            ),
            "not canonical",
        ),
        (
            lambda value: value.update({"asOf": "2026-07-28T10:30:00Z"}),
            "unknown or missing fields",
        ),
    ),
    ids=(
        "naive-time",
        "leap-second",
        "excess-fractional-precision",
        "mixed-point-window",
        "negative-position",
        "boolean-position",
        "tenant-alias",
        "unknown-coordinate-field",
    ),
)
def test_invalid_temporal_coordinates_refuse(mutation, error):
    value = _coordinate()
    mutation(value)

    with pytest.raises(temporal.TemporalCandidateError, match=error):
        temporal.validate_temporal_coordinate(value)
    assert list(_validator().iter_errors(value))


@pytest.mark.parametrize(
    "interval",
    (
        {
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-01-01T00:00:00Z",
        },
        {
            "validFrom": "2027-01-01T00:00:00Z",
            "validUntil": "2026-01-01T00:00:00Z",
        },
    ),
    ids=("empty", "reversed"),
)
def test_valid_interval_must_be_non_empty_and_half_open(interval):
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="non-empty and half-open",
    ):
        temporal.validate_valid_interval(interval)


def test_window_meaning_is_a_closed_per_step_vocabulary():
    temporal.validate_window_meaning("EVENT_OCCURRENCE")
    temporal.validate_window_meaning("STATE_OVERLAP")

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="closed vocabulary",
    ):
        temporal.validate_window_meaning("QUERY_WIDE")


def test_candidate_does_not_enter_runtime_or_active_profile_artifacts():
    candidate_path = temporal.SCHEMA_PATH.relative_to(PACKAGE_ROOT).as_posix()
    runtime_catalog = json.loads(
        temporal.RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")
    )
    assert candidate_path not in runtime_catalog["contractSchemas"]
    assert candidate_path.startswith("contracts/candidates/")

    for path in (
        temporal.ACTIVE_ARTIFACT_SET_PATH,
        temporal.CAPABILITY_MANIFEST_PATH,
    ):
        assert temporal.CONTRACT_VERSION not in path.read_text(encoding="utf-8")
