from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from conformance import temporal_contract_candidate_check as temporal


PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _coordinate_schema() -> dict:
    return json.loads(
        temporal.COORDINATE_SCHEMA_PATH.read_text(encoding="utf-8")
    )


def _coordinate_validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(
        _coordinate_schema(),
        format_checker=jsonschema.FormatChecker(),
    )


def _carrier_schema() -> dict:
    return json.loads(temporal.CARRIER_SCHEMA_PATH.read_text(encoding="utf-8"))


def _carrier_matrix() -> dict:
    return json.loads(temporal.CARRIER_MATRIX_PATH.read_text(encoding="utf-8"))


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


def test_candidate_schemas_and_carrier_matrix_are_full_draft_2020_12_valid():
    coordinate_schema = _coordinate_schema()
    carrier_schema = _carrier_schema()
    carrier_matrix = _carrier_matrix()

    jsonschema.Draft202012Validator.check_schema(coordinate_schema)
    jsonschema.Draft202012Validator.check_schema(carrier_schema)
    jsonschema.Draft202012Validator(carrier_schema).validate(carrier_matrix)
    temporal.validate_carrier_matrix(carrier_matrix)


def test_point_and_window_coordinates_validate_against_schema_and_semantics():
    point = _coordinate()
    window = copy.deepcopy(point)
    window["validCut"] = {
        "cutType": "WINDOW",
        "windowStart": "2026-01-01T00:00:00Z",
        "windowEnd": "2027-01-01T00:00:00Z",
    }
    window["knowledgeCut"]["position"] = temporal.MAX_KNOWLEDGE_POSITION

    for value in (point, window):
        _coordinate_validator().validate(value)
        temporal.validate_temporal_coordinate(value)


@pytest.mark.parametrize(
    "vector",
    temporal.REFUSAL_VECTORS,
    ids=lambda vector: vector.vector_id,
)
def test_shared_temporal_refusal_vectors(vector):
    value = copy.deepcopy(vector.value)
    with pytest.raises(
        temporal.TemporalCandidateError,
        match=vector.expected_error,
    ):
        vector.validator(value)
    if vector.schema_must_refuse:
        assert list(_coordinate_validator().iter_errors(value))


def test_load_bearing_coordinate_schema_definitions_are_pinned():
    mutations = (
        lambda schema: schema["$defs"]["pointValidCut"].update(
            {"additionalProperties": True}
        ),
        lambda schema: schema["$defs"]["windowValidCut"]["properties"][
            "cutType"
        ].update({"const": "Window"}),
        lambda schema: schema["$defs"]["validCut"]["oneOf"].pop(),
        lambda schema: schema["$defs"]["validInterval"]["required"].clear(),
    )

    for mutation in mutations:
        schema = _coordinate_schema()
        mutation(schema)
        with pytest.raises(temporal.TemporalCandidateError):
            temporal.validate_coordinate_schema_shape(schema)


def test_carrier_matrix_schema_and_adr_rows_are_pinned():
    carrier_schema = _carrier_schema()
    carrier_schema["$defs"]["carrierMatrixRow"]["properties"]["rowId"][
        "enum"
    ].pop()
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="carrierMatrixRow definition differs",
    ):
        temporal.validate_carrier_schema_shape(carrier_schema)

    carrier_matrix = _carrier_matrix()
    carrier_matrix["rows"][0]["rowId"] = carrier_matrix["rows"][1]["rowId"]
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="row identities differ",
    ):
        temporal.validate_carrier_matrix(carrier_matrix)

    carrier_matrix = _carrier_matrix()
    carrier_matrix["rows"][0][
        "authoritativeValidTimeCarrierRule"
    ] = "invented carrier"
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="differs from ADR 0002",
    ):
        temporal.validate_carrier_matrix(carrier_matrix)


def test_candidate_does_not_enter_runtime_or_production_activation_inputs():
    runtime_catalog = json.loads(
        temporal.RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")
    )
    temporal.validate_non_activation(runtime_catalog)
    assert all(
        path.startswith("contracts/candidates/")
        for path in temporal.CANDIDATE_RELATIVE_PATHS
    )

    mutated_catalog = copy.deepcopy(runtime_catalog)
    mutated_catalog["components"].append(
        {
            "logicalRef": "untrusted:alias",
            "relativePath": temporal.CARRIER_MATRIX_RELATIVE_PATH,
            "mediaType": "application/json",
        }
    )
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="runtime component",
    ):
        temporal.validate_non_activation(mutated_catalog)

    activation_markers = (
        temporal.CONTRACT_VERSION,
        temporal.CARRIER_SCHEMA_VERSION,
        temporal.CARRIER_MATRIX_ID,
        *temporal.CANDIDATE_RELATIVE_PATHS,
    )
    for path in (
        temporal.ACTIVE_ARTIFACT_SET_PATH,
        temporal.CAPABILITY_MANIFEST_PATH,
    ):
        active_text = path.read_text(encoding="utf-8")
        assert all(marker not in active_text for marker in activation_markers)


def test_candidate_paths_are_not_frozen_or_active_contract_directories():
    for relative_path in temporal.CANDIDATE_RELATIVE_PATHS:
        path = PACKAGE_ROOT / relative_path
        assert path.is_file()
        assert not relative_path.startswith(
            ("contracts/kernel/", "contracts/core/", "contracts/platform/")
        )
