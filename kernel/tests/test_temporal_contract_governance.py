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


def _selection_schema() -> dict:
    return json.loads(
        temporal.SELECTION_SCHEMA_PATH.read_text(encoding="utf-8")
    )


def _selection_binding() -> dict:
    return json.loads(
        temporal.SELECTION_BINDING_PATH.read_text(encoding="utf-8")
    )


def _command_schema() -> dict:
    return json.loads(
        temporal.COMMAND_SCHEMA_PATH.read_text(encoding="utf-8")
    )


def _command_binding() -> dict:
    return json.loads(
        temporal.COMMAND_BINDING_PATH.read_text(encoding="utf-8")
    )


def _runtime_bundle_carrier_schema() -> dict:
    return json.loads(
        temporal.RUNTIME_BUNDLE_CARRIER_SCHEMA_PATH.read_text(
            encoding="utf-8"
        )
    )


def _runtime_bundle_carrier_binding() -> dict:
    return json.loads(
        temporal.RUNTIME_BUNDLE_CARRIER_BINDING_PATH.read_text(
            encoding="utf-8"
        )
    )


def _runtime_bundle_selection_schema() -> dict:
    return json.loads(
        temporal.RUNTIME_BUNDLE_SELECTION_SCHEMA_PATH.read_text(
            encoding="utf-8"
        )
    )


def _runtime_bundle_selection_binding() -> dict:
    return json.loads(
        temporal.RUNTIME_BUNDLE_SELECTION_BINDING_PATH.read_text(
            encoding="utf-8"
        )
    )


def _promotion_schema() -> dict:
    return json.loads(
        temporal.PROMOTION_SCHEMA_PATH.read_text(encoding="utf-8")
    )


def _promotion_binding() -> dict:
    return json.loads(
        temporal.PROMOTION_BINDING_PATH.read_text(encoding="utf-8")
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


def test_temporal_card_errata_trace_is_pinned():
    errata = temporal.ERRATA_PATH.read_text(encoding="utf-8")
    temporal.validate_temporal_card_errata_trace(errata)


@pytest.mark.parametrize(
    "marker",
    temporal.TEMPORAL_CARD_ERRATA_REQUIRED_MARKERS,
)
def test_temporal_card_errata_trace_rejects_modified_marker(marker: str):
    errata = temporal.ERRATA_PATH.read_text(encoding="utf-8")
    assert marker in errata

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="temporal decision-card ERRATA trace markers differ",
    ):
        temporal.validate_temporal_card_errata_trace(
            errata.replace(marker, "tampered", 1)
        )


@pytest.mark.parametrize(
    "mutation",
    ("removed", "duplicate", "spaced_duplicate", "gutted"),
)
def test_temporal_card_errata_trace_rejects_structural_mutation(
    mutation: str,
):
    errata = temporal.ERRATA_PATH.read_text(encoding="utf-8")
    row = next(
        line
        for line in errata.splitlines()
        if temporal._markdown_table_row_identity(line)
        == temporal.TEMPORAL_CARD_ERRATA_ROW_ID
    )
    mutations = {
        "removed": errata.replace(f"{row}\n", "", 1),
        "duplicate": f"{errata}\n{row}\n",
        "spaced_duplicate": (
            f"{errata}\n"
            f"{row.replace('| E-009 |', '|  E-009  |', 1)}\n"
        ),
        "gutted": errata.replace(
            row,
            "| E-009 | x | x | x | x | "
            f"{temporal.TEMPORAL_CARD_ERRATA_CARD_DIGEST} "
            "withdrawn permanently |",
            1,
        ),
    }
    expected_error = (
        "trace markers differ"
        if mutation == "gutted"
        else "row identity differs"
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match=expected_error,
    ):
        temporal.validate_temporal_card_errata_trace(mutations[mutation])


def test_candidate_governance_wires_temporal_card_errata_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    errata = temporal.ERRATA_PATH.read_text(encoding="utf-8")
    row = next(
        line
        for line in errata.splitlines()
        if temporal._markdown_table_row_identity(line)
        == temporal.TEMPORAL_CARD_ERRATA_ROW_ID
    )
    tampered_errata_path = tmp_path / "ERRATA.md"
    tampered_errata_path.write_text(
        errata.replace(f"{row}\n", "", 1),
        encoding="utf-8",
    )

    with monkeypatch.context() as errata_patch:
        errata_patch.setattr(
            temporal,
            "ERRATA_PATH",
            tampered_errata_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="temporal decision-card ERRATA row identity differs",
        ):
            temporal.validate_candidate_governance()


def test_candidate_schemas_and_instances_are_full_draft_2020_12_valid():
    coordinate_schema = _coordinate_schema()
    carrier_schema = _carrier_schema()
    carrier_matrix = _carrier_matrix()
    selection_schema = _selection_schema()
    selection_binding = _selection_binding()
    command_schema = _command_schema()
    command_binding = _command_binding()
    runtime_bundle_carrier_schema = _runtime_bundle_carrier_schema()
    runtime_bundle_carrier_binding = _runtime_bundle_carrier_binding()
    runtime_bundle_selection_schema = _runtime_bundle_selection_schema()
    runtime_bundle_selection_binding = _runtime_bundle_selection_binding()
    promotion_schema = _promotion_schema()
    promotion_binding = _promotion_binding()

    jsonschema.Draft202012Validator.check_schema(coordinate_schema)
    jsonschema.Draft202012Validator.check_schema(carrier_schema)
    jsonschema.Draft202012Validator.check_schema(selection_schema)
    jsonschema.Draft202012Validator.check_schema(command_schema)
    jsonschema.Draft202012Validator.check_schema(
        runtime_bundle_carrier_schema
    )
    jsonschema.Draft202012Validator.check_schema(
        runtime_bundle_selection_schema
    )
    jsonschema.Draft202012Validator.check_schema(promotion_schema)
    jsonschema.Draft202012Validator(carrier_schema).validate(carrier_matrix)
    jsonschema.Draft202012Validator(selection_schema).validate(
        selection_binding
    )
    jsonschema.Draft202012Validator(command_schema).validate(command_binding)
    jsonschema.Draft202012Validator(
        runtime_bundle_carrier_schema
    ).validate(runtime_bundle_carrier_binding)
    jsonschema.Draft202012Validator(
        runtime_bundle_selection_schema
    ).validate(runtime_bundle_selection_binding)
    jsonschema.Draft202012Validator(promotion_schema).validate(
        promotion_binding
    )
    temporal.validate_carrier_matrix(carrier_matrix)
    temporal.validate_selection_schema_shape(selection_schema)
    temporal.validate_selection_binding(selection_binding)
    temporal.validate_command_schema_shape(command_schema, command_binding)
    temporal.validate_command_binding(command_binding)
    temporal.validate_runtime_bundle_carrier_schema_shape(
        runtime_bundle_carrier_schema,
        runtime_bundle_carrier_binding,
    )
    temporal.validate_runtime_bundle_carrier_binding(
        runtime_bundle_carrier_binding
    )
    temporal.validate_runtime_bundle_selection_schema_shape(
        runtime_bundle_selection_schema,
        runtime_bundle_selection_binding,
    )
    temporal.validate_runtime_bundle_selection_binding(
        runtime_bundle_selection_binding
    )
    temporal.validate_promotion_schema_shape(
        promotion_schema,
        promotion_binding,
    )
    temporal.validate_promotion_binding(promotion_binding)
    temporal.validate_promotion_dependency_consistency()


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


def test_temporal_governed_command_is_exact_and_cannot_be_activated_by_mutation():
    schema = _command_schema()
    validator = jsonschema.Draft202012Validator(schema)

    mutations = (
        (
            lambda value: value["command"].update(
                {"routePosture": "OPEN"}
            ),
            "specialization differs",
        ),
        (
            lambda value: value["command"].update(
                {"promotionOutcome": "PROMOTE_ACCEPTED"}
            ),
            "specialization differs",
        ),
        (
            lambda value: value.update(
                {"identityAuthority": "CALLER_SELECTED"}
            ),
            "identity differs",
        ),
        (
            lambda value: value["durableBatch"][
                "newlyWrittenAllowedOutcomes"
            ].append("PROMOTE_ACCEPTED"),
            "batch policy differs",
        ),
        (
            lambda value: value["implementationStops"].clear(),
            "stop conditions differ",
        ),
    )
    for mutation, expected_error in mutations:
        binding = _command_binding()
        mutation(binding)
        assert list(validator.iter_errors(binding))
        with pytest.raises(
            temporal.TemporalCandidateError,
            match=expected_error,
        ):
            temporal.validate_command_binding(binding)


def test_runtime_bundle_carrier_is_closed_eligibility_not_required_closure():
    schema = _runtime_bundle_carrier_schema()
    validator = jsonschema.Draft202012Validator(schema)
    mutations = (
        (
            lambda value: value["componentVocabulary"].update(
                {"role": "REFERENCE_SOURCE"}
            ),
            "component vocabulary differs",
        ),
        (
            lambda value: value["allowedIdentities"].append(
                copy.deepcopy(value["allowedIdentities"][0])
            ),
            "allowed identity set differs",
        ),
        (
            # The binding's allowed set is exact even though no RuntimeBundle
            # or role use is required to contain every allowed identity.
            lambda value: value["allowedIdentities"].pop(),
            "allowed identity set differs",
        ),
        (
            lambda value: value["allowedIdentities"][0].update(
                {
                    "canonicalInstanceDigest": value["allowedIdentities"][0][
                        "instanceFileDigest"
                    ]
                }
            ),
            "allowed identity set differs",
        ),
        (
            lambda value: value["closureAuthority"].update(
                {"everyRuntimeBundleRequiresAllAllowedIdentities": True}
            ),
            "component closure authority differs",
        ),
        (
            lambda value: value["closureAuthority"].update(
                {"everyRoleUseRequiresAllAllowedIdentities": True}
            ),
            "component closure authority differs",
        ),
        (
            lambda value: value["candidateIsolation"].update(
                {"runtimeBundleMembership": "SUPPORTED"}
            ),
            "carrier binding differs",
        ),
        (
            lambda value: value["schemaRelationship"].update(
                {"sameRuntimeBundleRequiredWhenInstanceIsUsed": False}
            ),
            "carrier binding differs",
        ),
        (
            lambda value: value["forbiddenContentClasses"].pop(),
            "carrier binding differs",
        ),
        (
            lambda value: value["implementationStops"].clear(),
            "carrier binding differs",
        ),
    )
    for mutation, expected_error in mutations:
        binding = _runtime_bundle_carrier_binding()
        mutation(binding)
        assert list(validator.iter_errors(binding))
        with pytest.raises(
            temporal.TemporalCandidateError,
            match=expected_error,
        ):
            temporal.validate_runtime_bundle_carrier_binding(binding)


def test_tenant_command_runtime_bundle_selection_is_exact_and_inactive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    schema = _runtime_bundle_selection_schema()
    binding = _runtime_bundle_selection_binding()
    validator = jsonschema.Draft202012Validator(schema)

    assert (
        binding["requiredComponentClosure"]["components"]
        == temporal._expected_runtime_bundle_selection_components()
    )
    mutations = (
        (
            lambda value: value["selectionSource"].update(
                {"callerSelectable": True}
            ),
            "source differs",
        ),
        (
            lambda value: value["selectionSource"].update(
                {"lookupKey": ["request.tenantId", "request.bindingId"]}
            ),
            "source differs",
        ),
        (
            lambda value: value["selectionRecord"][
                "authorityBearingFields"
            ].remove("selectionKnowledgePosition"),
            "record authority differs",
        ),
        (
            lambda value: value["selectionRecord"]["stateTransitions"][1].update(
                {"effect": "REPLACE"}
            ),
            "state transitions differ",
        ),
        (
            lambda value: value["resolution"].update(
                {"before": "AFTER_COMMAND_ADMISSION"}
            ),
            "resolution differs",
        ),
        (
            lambda value: value["resolution"].update(
                {"refusalWrites": "ONE_BATCH"}
            ),
            "resolution differs",
        ),
        (
            lambda value: value["governancePrerequisite"].update(
                {"relationship": "REQUIRED_ROLE_MEMBER"}
            ),
            "prerequisite differs",
        ),
        (
            lambda value: value["requiredComponentClosure"][
                "components"
            ].pop(),
            "closure differs",
        ),
        (
            lambda value: value["requiredComponentClosure"]["components"][
                0
            ].update({"role": "REFERENCE_SOURCE"}),
            "closure differs",
        ),
        (
            lambda value: value["requiredComponentClosure"]["components"][
                -1
            ].update({"contentDigest": "sha256:" + ("0" * 64)}),
            "closure differs",
        ),
        (
            lambda value: value["requiredComponentClosure"].update(
                {"unrelatedComponentAuthority": "COMMAND_ADMISSION"}
            ),
            "closure differs",
        ),
        (
            lambda value: value["trustedAuthorities"].pop(),
            "authority map differs",
        ),
        (
            lambda value: value["invariants"].remove(
                "TCRS-017_SELECTION_REFUSAL_IS_NO_WRITE"
            ),
            "invariants differ",
        ),
        (
            lambda value: value["negativeCases"].remove(
                "SELECTION_CHANGES_DURING_COMMAND"
            ),
            "stops differ",
        ),
        (
            lambda value: value["unsupported"].remove(
                "HOT_RELOAD_UPGRADE_SUPERSESSION_OR_ROLLBACK"
            ),
            "stops differ",
        ),
        (
            lambda value: value["implementationStops"].remove(
                "NO_REVIEWED_SELECTION_REFUSAL_PUBLIC_REASON_MAPPING"
            ),
            "stops differ",
        ),
        (
            lambda value: value["implementationStops"].clear(),
            "stops differ",
        ),
    )
    for mutation, expected_error in mutations:
        mutated = copy.deepcopy(binding)
        mutation(mutated)
        assert list(validator.iter_errors(mutated))
        with pytest.raises(
            temporal.TemporalCandidateError,
            match=expected_error,
        ):
            temporal.validate_runtime_bundle_selection_binding(mutated)

    tampered_binding = copy.deepcopy(binding)
    tampered_binding["trustedAuthorities"][1]["separateFrom"].remove(
        "AUTHORIZER"
    )
    tampered_binding_path = tmp_path / "selection-binding.json"
    tampered_binding_path.write_text(
        json.dumps(tampered_binding, indent=2) + "\n",
        encoding="utf-8",
    )
    with monkeypatch.context() as digest_patch:
        digest_patch.setattr(
            temporal,
            "RUNTIME_BUNDLE_SELECTION_BINDING_PATH",
            tampered_binding_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="binding digest differs",
        ):
            temporal.validate_runtime_bundle_selection_binding(
                tampered_binding
            )

    tampered_schema = copy.deepcopy(schema)
    tampered_schema["$comment"] = "tampered"
    tampered_schema_path = tmp_path / "selection-schema.json"
    tampered_schema_path.write_text(
        json.dumps(tampered_schema, indent=2) + "\n",
        encoding="utf-8",
    )
    with monkeypatch.context() as digest_patch:
        digest_patch.setattr(
            temporal,
            "RUNTIME_BUNDLE_SELECTION_SCHEMA_PATH",
            tampered_schema_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="schema digest differs",
        ):
            temporal.validate_runtime_bundle_selection_binding(binding)


def test_temporal_promotion_contract_is_atomic_exact_and_has_no_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    schema = _promotion_schema()
    binding = _promotion_binding()
    validator = jsonschema.Draft202012Validator(schema)

    assert (
        binding["subjectSet"]["subjects"]
        == temporal._expected_promotion_subjects()
    )
    assert binding["promotionMeaning"] == {
        "sourceLifecycleState": "CANDIDATE_INACTIVE",
        "targetLifecycleState": "GOVERNED_INACTIVE",
        "effect": "EXTERNAL_LIFECYCLE_CLASSIFICATION_ONLY",
        "embeddedStatusMeaning": "IMMUTABLE_CREATION_STATE_ATTESTATION",
        "effectiveLifecycleAuthority": (
            "REVIEWED_PROMOTION_DECISION_AND_CURRENTNESS_TRACE"
        ),
        "currentDefaultPromotion": False,
        "runtimeActivation": False,
        "productionReadiness": False,
    }
    mutations = (
        (
            lambda value: value.update({"status": "GOVERNED_INACTIVE"}),
            "identity differs",
        ),
        (
            lambda value: value["subjectSet"]["subjects"].pop(),
            "subject set differs",
        ),
        (
            lambda value: value["subjectSet"]["subjects"].append(
                copy.deepcopy(value["subjectSet"]["subjects"][0])
            ),
            "subject set differs",
        ),
        (
            lambda value: value["subjectSet"]["subjects"].reverse(),
            "subject set differs",
        ),
        (
            lambda value: value["subjectSet"]["subjects"][0].update(
                {"repositoryFileDigest": "sha256:" + ("0" * 64)}
            ),
            "subject set differs",
        ),
        (
            lambda value: value["subjectSet"].update(
                {"partialPromotion": "ALLOW_PARTIAL"}
            ),
            "subject set differs",
        ),
        (
            lambda value: value["decisionContract"]["allowedOutcomes"].append(
                "PROMOTE_ACTIVE"
            ),
            "decision authority differs",
        ),
        (
            lambda value: value["decisionContract"].update(
                {"humanGoverned": False}
            ),
            "decision authority differs",
        ),
        (
            lambda value: value["decisionContract"].update(
                {"contractApprovalIsPromotion": True}
            ),
            "decision authority differs",
        ),
        (
            lambda value: value["decisionContract"].update(
                {"callerSelectable": True}
            ),
            "decision authority differs",
        ),
        (
            lambda value: value["dependencyConsistency"].update(
                {"selectorMatrixRowId": "ASSERTION_RECORD"}
            ),
            "binding differs",
        ),
        (
            lambda value: value["authoritySeparation"].update(
                {"runtimeAuthoritiesUnchanged": False}
            ),
            "binding differs",
        ),
        (
            lambda value: value["invariants"].remove(
                "TGP-003_ATOMIC_DECISION"
            ),
            "invariants or negative cases differ",
        ),
        (
            lambda value: value["negativeCases"].remove(
                "POSITIVE_DECISION_STRONGER_THAN_GOVERNED_INACTIVE"
            ),
            "invariants or negative cases differ",
        ),
        (
            lambda value: value["promotionMeaning"].update(
                {"targetLifecycleState": "CURRENT_DEFAULT"}
            ),
            "binding differs",
        ),
        (
            lambda value: value["unsupported"].remove(
                "CURRENT_DEFAULT_PROMOTION"
            ),
            "binding differs",
        ),
        (
            lambda value: value["implementationStops"].clear(),
            "binding differs",
        ),
        (
            lambda value: value.update({"callerDecision": "PROMOTE"}),
            "unknown fields",
        ),
        (
            lambda value: value.pop("authoritySeparation"),
            "missing fields",
        ),
    )
    for mutation, expected_error in mutations:
        mutated = copy.deepcopy(binding)
        mutation(mutated)
        assert list(validator.iter_errors(mutated))
        with pytest.raises(
            temporal.TemporalCandidateError,
            match=expected_error,
        ):
            temporal.validate_promotion_binding(mutated)

    schema_mutations = (
        (
            lambda value: value.update(
                {"$id": "https://example.invalid/promotion"}
            ),
            "schema shape differs",
        ),
        (
            lambda value: value.update({"title": "Unreviewed promotion"}),
            "schema shape differs",
        ),
        (
            lambda value: value["const"].update(
                {"status": "GOVERNED_INACTIVE"}
            ),
            "schema shape differs",
        ),
        (
            lambda value: value.update({"$comment": "inactive"}),
            "schema posture differs",
        ),
    )
    for mutation, expected_error in schema_mutations:
        mutated_schema = copy.deepcopy(schema)
        mutation(mutated_schema)
        with pytest.raises(
            temporal.TemporalCandidateError,
            match=expected_error,
        ):
            temporal.validate_promotion_schema_shape(
                mutated_schema,
                binding,
            )

    promotion_rfc = temporal.PROMOTION_RFC_PATH.read_text(encoding="utf-8")
    rfc_mutations = (
        promotion_rfc.replace(
            "TGP-003 — Atomic decision.",
            "TGP-003 — Deleted atomic decision.",
            1,
        ),
        promotion_rfc.replace("9504", "9999", 1),
        promotion_rfc.replace("## Required negative cases", "", 1),
    )
    for index, mutated_rfc in enumerate(rfc_mutations):
        mutated_rfc_path = tmp_path / f"promotion-rfc-{index}.md"
        mutated_rfc_path.write_text(mutated_rfc, encoding="utf-8")
        with monkeypatch.context() as rfc_patch:
            rfc_patch.setattr(
                temporal,
                "PROMOTION_RFC_PATH",
                mutated_rfc_path,
            )
            with pytest.raises(
                temporal.TemporalCandidateError,
                match="RFC digest differs",
            ):
                temporal._assert_promotion_rfc_digest()

    tampered_selector = _selection_binding()
    tampered_selector["carrierMatrix"]["rowId"] = "ASSERTION_RECORD"
    tampered_selector_path = tmp_path / "tampered-selector.json"
    tampered_selector_path.write_text(
        json.dumps(tampered_selector, indent=2) + "\n",
        encoding="utf-8",
    )
    with monkeypatch.context() as dependency_patch:
        dependency_patch.setattr(
            temporal,
            "SELECTION_BINDING_PATH",
            tampered_selector_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="exact matrix dependency",
        ):
            temporal.validate_promotion_dependency_consistency()

    malformed_command = _command_binding()
    malformed_command["prerequisites"] = "caller-selected"
    malformed_command_path = tmp_path / "malformed-command.json"
    malformed_command_path.write_text(
        json.dumps(malformed_command, indent=2) + "\n",
        encoding="utf-8",
    )
    with monkeypatch.context() as dependency_patch:
        dependency_patch.setattr(
            temporal,
            "COMMAND_BINDING_PATH",
            malformed_command_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="prerequisites are malformed",
        ):
            temporal.validate_promotion_dependency_consistency()

    tampered_command = _command_binding()
    for prerequisite in tampered_command["prerequisites"]:
        if prerequisite["role"] == "INTERVENTION_VALID_TIME_SELECTION":
            prerequisite["identity"] = "caller-selected"
    tampered_command_path = tmp_path / "tampered-command.json"
    tampered_command_path.write_text(
        json.dumps(tampered_command, indent=2) + "\n",
        encoding="utf-8",
    )
    with monkeypatch.context() as dependency_patch:
        dependency_patch.setattr(
            temporal,
            "COMMAND_BINDING_PATH",
            tampered_command_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="exact selector dependency",
        ):
            temporal.validate_promotion_dependency_consistency()

    temporal.validate_promotion_dependency_consistency()


@pytest.mark.parametrize(
    "model_text",
    ("# temporal role absent\n", temporal.RUNTIME_BUNDLE_CARRIER_ROLE),
    ids=("role-absent", "role-in-model"),
)
def test_runtime_bundle_role_posture_allows_absent_or_model_only_role(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_text: str,
):
    model_path = tmp_path / "runtime_bundle.py"
    model_path.write_text(model_text, encoding="utf-8")
    repository_path = tmp_path / "runtime_bundle_repository.py"
    repository_path.write_text("# role absent\n", encoding="utf-8")
    schema_path = tmp_path / "schema.sql"
    schema_path.write_text("-- role absent\n", encoding="utf-8")
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "0001.sql").write_text("-- role absent\n", encoding="utf-8")

    monkeypatch.setattr(temporal, "RUNTIME_BUNDLE_MODEL_PATH", model_path)
    monkeypatch.setattr(
        temporal,
        "RUNTIME_BUNDLE_ROLE_FORBIDDEN_AUTHORITY_PATHS",
        (repository_path, schema_path),
    )
    monkeypatch.setattr(temporal, "TENANT_MIGRATIONS_PATH", migration_dir)

    temporal.validate_runtime_bundle_carrier_role_posture()


def test_runtime_bundle_role_posture_pins_model_admission_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    with monkeypatch.context() as candidate_patch:
        candidate_patch.setattr(
            temporal,
            "RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_PATH",
            tmp_path / "missing-model-admission-rfc.md",
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="model-admission authority is missing",
        ):
            temporal.validate_runtime_bundle_carrier_role_posture()

    authority_bytes = temporal.RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_PATH.read_bytes()
    wrong_length_path = tmp_path / "wrong-length-model-admission-rfc.md"
    wrong_length_path.write_bytes(authority_bytes + b"\n")
    with monkeypatch.context() as candidate_patch:
        candidate_patch.setattr(
            temporal,
            "RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_PATH",
            wrong_length_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="authority byte length differs",
        ):
            temporal.validate_runtime_bundle_carrier_role_posture()

    wrong_digest_path = tmp_path / "wrong-digest-model-admission-rfc.md"
    changed_bytes = b"!" + authority_bytes[1:]
    assert len(changed_bytes) == len(authority_bytes)
    wrong_digest_path.write_bytes(changed_bytes)
    with monkeypatch.context() as candidate_patch:
        candidate_patch.setattr(
            temporal,
            "RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_PATH",
            wrong_digest_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="authority digest differs",
        ):
            temporal.validate_runtime_bundle_carrier_role_posture()


@pytest.mark.parametrize(
    "forbidden_authority",
    ("repository", "schema"),
)
def test_runtime_bundle_role_posture_refuses_each_fixed_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    forbidden_authority: str,
):
    model_path = tmp_path / "runtime_bundle.py"
    model_path.write_text(
        temporal.RUNTIME_BUNDLE_CARRIER_ROLE,
        encoding="utf-8",
    )
    repository_path = tmp_path / "runtime_bundle_repository.py"
    schema_path = tmp_path / "schema.sql"
    for path, authority in (
        (repository_path, "repository"),
        (schema_path, "schema"),
    ):
        path.write_text(
            temporal.RUNTIME_BUNDLE_CARRIER_ROLE
            if authority == forbidden_authority
            else "role absent",
            encoding="utf-8",
        )
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "0001.sql").write_text("-- role absent\n", encoding="utf-8")

    monkeypatch.setattr(temporal, "RUNTIME_BUNDLE_MODEL_PATH", model_path)
    monkeypatch.setattr(
        temporal,
        "RUNTIME_BUNDLE_ROLE_FORBIDDEN_AUTHORITY_PATHS",
        (repository_path, schema_path),
    )
    monkeypatch.setattr(temporal, "TENANT_MIGRATIONS_PATH", migration_dir)

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="explicitly forbidden RuntimeBundle authority",
    ):
        temporal.validate_runtime_bundle_carrier_role_posture()


def test_runtime_bundle_role_posture_refuses_migration_authority_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    model_path = tmp_path / "runtime_bundle.py"
    model_path.write_text(
        temporal.RUNTIME_BUNDLE_CARRIER_ROLE,
        encoding="utf-8",
    )
    repository_path = tmp_path / "runtime_bundle_repository.py"
    repository_path.write_text("# role absent\n", encoding="utf-8")
    schema_path = tmp_path / "schema.sql"
    schema_path.write_text("-- role absent\n", encoding="utf-8")
    monkeypatch.setattr(temporal, "RUNTIME_BUNDLE_MODEL_PATH", model_path)
    monkeypatch.setattr(
        temporal,
        "RUNTIME_BUNDLE_ROLE_FORBIDDEN_AUTHORITY_PATHS",
        (repository_path, schema_path),
    )

    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "0001.sql").write_text(
        temporal.RUNTIME_BUNDLE_CARRIER_ROLE,
        encoding="utf-8",
    )
    monkeypatch.setattr(temporal, "TENANT_MIGRATIONS_PATH", migration_dir)
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="explicitly forbidden RuntimeBundle authority",
    ):
        temporal.validate_runtime_bundle_carrier_role_posture()

    empty_migration_dir = tmp_path / "empty-migrations"
    empty_migration_dir.mkdir()
    monkeypatch.setattr(
        temporal,
        "TENANT_MIGRATIONS_PATH",
        empty_migration_dir,
    )
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="migration authority set is empty",
    ):
        temporal.validate_runtime_bundle_carrier_role_posture()

    monkeypatch.setattr(
        temporal,
        "TENANT_MIGRATIONS_PATH",
        tmp_path / "missing-migrations",
    )
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="migration authority directory is missing",
    ):
        temporal.validate_runtime_bundle_carrier_role_posture()


def test_temporal_candidates_and_role_do_not_enter_active_catalog():
    runtime_catalog = json.loads(
        temporal.RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")
    )
    temporal.validate_non_activation(runtime_catalog)
    assert all(
        path.startswith("contracts/candidates/")
        for path in temporal.CANDIDATE_RELATIVE_PATHS
    )

    contract_catalog = copy.deepcopy(runtime_catalog)
    contract_catalog["contractSchemas"].append(
        temporal.CARRIER_SCHEMA_RELATIVE_PATH
    )
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="RuntimeBundle contracts",
    ):
        temporal.validate_non_activation(contract_catalog)

    mutated_catalog = copy.deepcopy(runtime_catalog)
    mutated_catalog["components"].append(
        {
            "role": "REFERENCE_SOURCE",
            "logicalRef": "candidate:temporal-matrix",
            "path": temporal.CARRIER_MATRIX_RELATIVE_PATH,
            "canonicalization": "EXACT_BYTES_V1",
            "placement": "GLOBAL_IMMUTABLE_CONTENT",
        }
    )
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="runtime component",
    ):
        temporal.validate_non_activation(mutated_catalog)

    role_catalog = copy.deepcopy(runtime_catalog)
    role_catalog["components"].append(
        {
            "logicalRef": "untrusted:temporal-role",
            "relativePath": "kernel/untrusted-temporal-role.json",
            "role": temporal.RUNTIME_BUNDLE_CARRIER_ROLE,
        }
    )
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="active RuntimeBundle catalog",
    ):
        temporal.validate_non_activation(role_catalog)


@pytest.mark.parametrize(
    ("path_attribute", "label"),
    (
        ("ACTIVE_ARTIFACT_SET_PATH", "ActiveArtifactSet"),
        ("CAPABILITY_MANIFEST_PATH", "Capability Manifest"),
    ),
    ids=("active-artifact-set", "capability-manifest"),
)
def test_active_temporal_activation_inputs_refuse_each_exact_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path_attribute: str,
    label: str,
):
    active_path = tmp_path / f"{path_attribute}.json"
    active_path.write_text(
        temporal.RUNTIME_BUNDLE_CARRIER_ROLE,
        encoding="utf-8",
    )
    monkeypatch.setattr(temporal, path_attribute, active_path)

    with pytest.raises(temporal.TemporalCandidateError, match=label):
        temporal.validate_active_temporal_activation_inputs()


def test_active_temporal_activation_inputs_remain_clear():
    temporal.validate_active_temporal_activation_inputs()


def test_candidate_paths_are_not_frozen_or_active_contract_directories():
    for relative_path in temporal.CANDIDATE_RELATIVE_PATHS:
        path = PACKAGE_ROOT / relative_path
        assert path.is_file()
        assert not relative_path.startswith(
            ("contracts/kernel/", "contracts/core/", "contracts/platform/")
        )
