from __future__ import annotations

import copy
import hashlib
import inspect
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import jsonschema
import pytest

from conformance import rewrite_architecture_check as architecture
from kernel import temporal_carriers as temporal


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
BINDING_SCHEMA_PATH = (
    PACKAGE_ROOT
    / "contracts/candidates/temporal_carrier_selection/"
    "OFARM_TemporalCarrierSelectionBinding_schema_v0_1.json"
)
BINDING_PATH = (
    PACKAGE_ROOT
    / "contracts/candidates/temporal_carrier_selection/"
    "OFARM_InterventionValidTimeCarrierSelection_candidate_v0_1.json"
)


def _envelope() -> dict[str, object]:
    return {
        "schemaVersion": temporal.ENVELOPE_SCHEMA_VERSION,
        "primaryEventFamily": "InterventionEvent",
        "timeSemantics": {
            "eventTime": "2026-07-28T10:30:00Z",
            "recordTime": "2026-07-28T10:31:00Z",
        },
    }


def _payload() -> dict[str, object]:
    return {
        "schemaVersion": temporal.EXECUTION_SCHEMA_VERSION,
        "recordClass": "OPERATION_CLAIM",
        "capturedAt": "2026-07-28T10:31:00Z",
        "effectiveTimeInterval": {
            "start": "2026-07-28T10:30:00Z",
            "end": "2026-07-28T11:00:00Z",
            "timeBasis": "EXECUTION_INTERVAL",
        },
    }


def _binding() -> dict[str, object]:
    return json.loads(BINDING_PATH.read_text(encoding="utf-8"))


def test_candidate_binding_is_full_draft_2020_12_valid():
    schema = json.loads(BINDING_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(_binding())


@pytest.mark.parametrize(
    "field",
    ["sourceContracts", "selectors", "unsupportedEnvelopeFields"],
)
def test_candidate_schema_pins_complete_authority_array(field: str):
    schema = json.loads(BINDING_SCHEMA_PATH.read_text(encoding="utf-8"))
    binding = _binding()
    values = binding[field]
    assert type(values) is list
    values[1] = copy.deepcopy(values[0])

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(binding)


def test_binding_identity_is_artifact_owned_and_api_is_closed():
    binding = _binding()
    identity = temporal.INTERVENTION_BINDING

    assert identity.binding_schema_version == binding["schemaVersion"]
    assert identity.binding_id == binding["bindingId"]
    assert identity.binding_artifact_digest == (
        f"sha256:{hashlib.sha256(BINDING_PATH.read_bytes()).hexdigest()}"
    )
    assert identity.coordinate_schema_version == binding["coordinateContract"][
        "schemaVersion"
    ]
    assert identity.coordinate_schema_digest == binding["coordinateContract"][
        "schemaDigest"
    ]
    assert identity.carrier_matrix_id == binding["carrierMatrix"]["matrixId"]
    assert identity.carrier_matrix_digest == binding["carrierMatrix"][
        "matrixDigest"
    ]
    assert identity.carrier_matrix_row_id == binding["carrierMatrix"]["rowId"]
    assert identity.envelope_schema_version == binding["sourceContracts"][0][
        "schemaVersion"
    ]
    assert identity.envelope_schema_digest == binding["sourceContracts"][0][
        "schemaDigest"
    ]
    assert identity.execution_schema_version == binding["sourceContracts"][1][
        "schemaVersion"
    ]
    assert identity.execution_schema_digest == binding["sourceContracts"][1][
        "schemaDigest"
    ]
    assert not hasattr(temporal, "CarrierBindingIdentity")
    with pytest.raises(TypeError):
        type(identity)(binding_id="caller-selected")
    assert list(inspect.signature(
        temporal.select_intervention_valid_time
    ).parameters) == ["envelope", "execution_payload"]

    with pytest.raises(TypeError):
        temporal.select_intervention_valid_time(
            _envelope(),
            _payload(),
            binding_id="caller-selected",  # type: ignore[call-arg]
        )


@pytest.mark.parametrize("source", ["envelope", "payload"])
def test_refuses_caller_source_contract_claims_that_differ(source: str):
    envelope = _envelope()
    payload = _payload()
    if source == "envelope":
        envelope["schemaVersion"] = "ofarm.semanticeventenvelope.v9.9"
    else:
        payload["schemaVersion"] = "ofarm.executionrecordpayload.v9.9"

    with pytest.raises(
        temporal.TemporalCarrierError,
        match="schemaVersion differs from the reviewed binding",
    ):
        temporal.select_intervention_valid_time(envelope, payload)


def test_selects_both_intervention_carriers_atomically():
    selected = temporal.select_intervention_valid_time(_envelope(), _payload())

    assert selected.binding is temporal.INTERVENTION_BINDING
    assert selected.occurrence.text == "2026-07-28T10:30:00Z"
    assert selected.execution_interval.start.text == "2026-07-28T10:30:00Z"
    assert selected.execution_interval.end.text == "2026-07-28T11:00:00Z"
    assert selected.occurrence_window_meaning == "EVENT_OCCURRENCE"
    assert selected.execution_window_meaning == "STATE_OVERLAP"

    with pytest.raises(FrozenInstanceError):
        selected.occurrence = temporal.StrictUtcInstant(  # type: ignore[misc]
            "2026-07-28T12:00:00Z"
        )


def test_instants_compare_by_temporal_value_not_lexical_form():
    short = temporal.StrictUtcInstant("2026-07-28T10:30:00Z")
    expanded = temporal.StrictUtcInstant("2026-07-28T10:30:00.000000Z")

    assert short.text != expanded.text
    assert short == expanded
    assert hash(short) == hash(expanded)

    envelope = _envelope()
    envelope["timeSemantics"]["eventTime"] = expanded.text
    assert temporal.select_intervention_valid_time(
        _envelope(), _payload()
    ) == temporal.select_intervention_valid_time(envelope, _payload())


@pytest.mark.parametrize(
    "value",
    [
        "2026-07-28T10:30:00",
        "2026-07-28T10:30:00+00:00",
        "2026-07-28T10:30:00-00:00",
        "2026-12-31T23:59:60Z",
        "2026-07-28T10:30:00.1234567Z",
        "2026-02-30T10:30:00Z",
    ],
)
def test_refuses_noncanonical_or_nonreal_instants(value: str):
    envelope = _envelope()
    envelope["timeSemantics"]["eventTime"] = value

    with pytest.raises(temporal.TemporalCarrierError):
        temporal.select_intervention_valid_time(envelope, _payload())


def test_missing_event_time_never_falls_back_to_secondary_times():
    envelope = _envelope()
    envelope["timeSemantics"].pop("eventTime")
    envelope["timeSemantics"]["assertionTime"] = "2026-07-28T10:29:00Z"

    with pytest.raises(
        temporal.TemporalCarrierError,
        match="eventTime",
    ):
        temporal.select_intervention_valid_time(envelope, _payload())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("family", "ObservationEvent", "primaryEventFamily"),
        ("recordClass", "CORRECTION", "recordClass"),
        ("timeBasis", "PLANNED_WINDOW", "timeBasis"),
        ("timeBasis", "UNKNOWN", "timeBasis"),
        ("timeBasis", None, "timeBasis"),
    ],
)
def test_refuses_unsupported_family_record_class_or_time_basis(
    field: str,
    value: object,
    message: str,
):
    envelope = _envelope()
    payload = _payload()
    if field == "family":
        envelope["primaryEventFamily"] = value
    elif field == "recordClass":
        payload["recordClass"] = value
    else:
        payload["effectiveTimeInterval"]["timeBasis"] = value

    with pytest.raises(temporal.TemporalCarrierError, match=message):
        temporal.select_intervention_valid_time(envelope, payload)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2026-07-28T10:30:00Z", "2026-07-28T10:30:00Z"),
        ("2026-07-28T11:00:00Z", "2026-07-28T10:30:00Z"),
    ],
)
def test_refuses_empty_or_reversed_execution_interval(
    start: str,
    end: str,
):
    payload = _payload()
    payload["effectiveTimeInterval"]["start"] = start
    payload["effectiveTimeInterval"]["end"] = end

    with pytest.raises(
        temporal.TemporalCarrierError,
        match="non-empty and ordered",
    ):
        temporal.select_intervention_valid_time(_envelope(), payload)


@pytest.mark.parametrize("field", ["effectiveFrom", "effectiveUntil"])
def test_refuses_unsupported_envelope_effective_bounds(field: str):
    envelope = _envelope()
    envelope["timeSemantics"][field] = "2026-07-28T10:30:00Z"

    with pytest.raises(
        temporal.TemporalCarrierError,
        match="effective bounds are unsupported",
    ):
        temporal.select_intervention_valid_time(envelope, _payload())


def test_half_open_boundary_predicates_are_explicit_and_adjacent():
    a = temporal.StrictUtcInstant("2026-07-28T10:00:00Z")
    b = temporal.StrictUtcInstant("2026-07-28T11:00:00Z")
    c = temporal.StrictUtcInstant("2026-07-28T12:00:00Z")
    first = temporal.BoundedHalfOpenInterval(a, b)
    second = temporal.BoundedHalfOpenInterval(b, c)

    assert temporal.event_in_window(a, first) is True
    assert temporal.event_in_window(b, first) is False
    assert temporal.event_in_window(b, second) is True
    assert temporal.state_at(first, b) is False
    assert temporal.state_overlaps(first, second) is False


def test_occurrence_and_execution_interval_are_independent():
    envelope = _envelope()
    envelope["timeSemantics"]["eventTime"] = "2020-01-01T00:00:00Z"

    selected = temporal.select_intervention_valid_time(envelope, _payload())

    assert temporal.event_in_window(
        selected.occurrence,
        selected.execution_interval,
    ) is False


def test_selection_is_deterministic_and_does_not_mutate_inputs():
    envelope = _envelope()
    payload = _payload()
    envelope_before = copy.deepcopy(envelope)
    payload_before = copy.deepcopy(payload)

    first = temporal.select_intervention_valid_time(envelope, payload)
    second = temporal.select_intervention_valid_time(envelope, payload)

    assert first == second
    assert envelope == envelope_before
    assert payload == payload_before


def test_selector_is_absent_from_production_and_legacy_import_closures():
    sources = architecture._module_sources(PACKAGE_ROOT)
    graph, _trees = architecture._import_graph(sources)

    assert "kernel.temporal_carriers" not in architecture._reachable_paths(
        graph,
        architecture.PRODUCTION_IMPORT_ROOTS,
    )
    assert "kernel.temporal_carriers" not in architecture._reachable_paths(
        graph,
        architecture.LEGACY_IMPORT_ROOTS,
    )


def test_selector_artifacts_are_absent_from_runtime_and_profile_activation():
    markers = (
        temporal.BINDING_SCHEMA_VERSION,
        temporal.BINDING_ID,
        BINDING_SCHEMA_PATH.relative_to(PACKAGE_ROOT).as_posix(),
        BINDING_PATH.relative_to(PACKAGE_ROOT).as_posix(),
    )
    for path in (
        PACKAGE_ROOT / "kernel/runtime_bundle_components.json",
        PACKAGE_ROOT
        / "profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json",
        PACKAGE_ROOT
        / "profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json",
    ):
        text = path.read_text(encoding="utf-8")
        assert all(marker not in text for marker in markers)
