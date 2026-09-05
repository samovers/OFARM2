from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest

from conformance import ofarm_pkg_contract_check as checker


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DATE_TIME_SCHEMA = {"type": "string", "format": "date-time"}
FULL_DATE_TIME_VALIDATOR = jsonschema.Draft202012Validator(
    DATE_TIME_SCHEMA,
    format_checker=jsonschema.FormatChecker(),
)
ASSERTION_VIOLATIONS = {
    "type": ({"type": "string"}, 1),
    "const": ({"const": "expected"}, "actual"),
    "enum": ({"enum": ["expected"]}, "actual"),
    "required": ({"type": "object", "required": ["value"]}, {}),
    "additionalProperties": (
        {"type": "object", "additionalProperties": False},
        {"extra": True},
    ),
    "pattern": ({"type": "string", "pattern": "^[a-z]+$"}, "123"),
    "minItems": ({"type": "array", "minItems": 1}, []),
    "maxItems": ({"type": "array", "maxItems": 0}, [1]),
    "minLength": ({"type": "string", "minLength": 1}, ""),
    "format": (DATE_TIME_SCHEMA, "not-a-date"),
    "minimum": ({"type": "number", "minimum": 1}, 0),
    "maximum": ({"type": "number", "maximum": 0}, 1),
}
SUPPORTED_DIALECT = "https://json-schema.org/draft/2020-12/schema"
INTEGER_NUMBER_ONE_OF = {
    "oneOf": [{"type": "integer"}, {"type": "number"}],
}
NESTED_RESOURCE_SCHEMA = {
    "$schema": SUPPORTED_DIALECT,
    "$id": "https://example.test/root",
    "$defs": {"limit": {"type": "number", "minimum": 0}},
    "type": "object",
    "properties": {
        "value": {
            "$id": "https://example.test/inner",
            "$defs": {"limit": {"type": "number", "minimum": 100}},
            "$ref": "#/$defs/limit",
        }
    },
}
REVIEWED_MALFORMED_ROOT_IDENTIFIERS = (
    "https://example.test:abc/schema",
    "https://example.test/a[b]",
    "https://a@b@c/schema",
)
MALFORMED_ROOT_IDENTIFIER_EDGE_CASES = (
    "https://example.test:/schema",
    "https://example.test:80:90/schema",
    "https://[2001:db8::zz]/schema",
    "https://2001:db8::1/schema",
    "https://[2001:db8::1]suffix/schema",
    "https://example.test/schema?filter=[value]",
    "https://user[name]@example.test/schema",
    "https://[vG.bad]/schema",
    "https://[v1.]/schema",
)
SUPPORTED_ROOT_IDENTIFIER_CONTROLS = (
    "https://example.test:8443/schema",
    "https://example.test/a%5Bb%5D",
    "urn:example:test",
    "https://[2001:db8::1]/schema",
    "https://[2001:db8::1]:8443/schema",
    "https://user:password@example.test/schema",
    "https://example.test/schema?filter=a/b?c",
    "https://[v1.a:b]/schema",
    "https://example.test/schema#",
    "mailto:John.Doe@example.com",
)


def _errors(instance: object, schema: dict) -> list[str]:
    checker.check_keywords(schema)
    return checker.validate(instance, schema)


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("2026-09-03T10:26:33Z", True),
        ("2024-02-29T23:59:59.123+02:30", True),
        ("2026-09-03T00:00:00-00:00", True),
        ("not-a-date", False),
        ("2026-09-03T10:26:33", False),
        ("2025-02-29T10:26:33Z", False),
        ("2026-09-03T24:00:00Z", False),
        ("2026-09-03T10:60:00Z", False),
        ("2026-09-03T10:26:60Z", False),
        ("2026-09-03T10:26:33+24:00", False),
        ("2026-09-03T10:26:33+01:60", False),
        ("2026-09-03T10:26:33+0100", False),
        ("٢٠٢٦-٠٩-٠٣T١٠:٢٦:٣٣Z", False),
        ("२०२६-०९-०३T१०:२६:३३Z", False),
        ("２０２６-０９-０３T１０:２６:３３Z", False),
        # The locked validator accepts this because its regex uses a `$`
        # anchor. The package checker deliberately rejects the trailing data.
        ("2026-09-03T10:26:33Z\n", False),
    ],
)
def test_date_time_is_at_least_as_strict_as_locked_full_validator(
    value: str,
    valid: bool,
) -> None:
    subset_valid = not _errors(value, DATE_TIME_SCHEMA)
    assert subset_valid is valid
    assert not subset_valid or FULL_DATE_TIME_VALIDATOR.is_valid(value)


def test_every_declared_assertion_keyword_is_executable() -> None:
    assert set(ASSERTION_VIOLATIONS) == checker.ASSERTION_KEYWORDS
    for keyword, (schema, invalid_instance) in ASSERTION_VIOLATIONS.items():
        checker.check_keywords(schema)
        assert checker.validate(invalid_instance, schema), keyword


def test_every_declared_descriptive_annotation_keyword_is_inert() -> None:
    assert checker.ANNOTATION_KEYWORDS == {
        "title", "description", "$comment",
    }
    for keyword in checker.ANNOTATION_KEYWORDS:
        schema = {keyword: "anything"}
        checker.check_keywords(schema)
        assert not checker.validate("instance", schema), keyword


def test_supported_root_identification_and_dialect_declarations() -> None:
    schema = {
        "$schema": SUPPORTED_DIALECT,
        "$id": "https://example.test/root",
        "$defs": {"label": {"type": "string", "minLength": 1}},
        "$ref": "#/$defs/label",
        "pattern": "^[a-z]+$",
    }

    assert checker.IDENTIFICATION_KEYWORDS == {"$id", "$schema"}
    assert checker.SUPPORTED_DIALECT == SUPPORTED_DIALECT
    checker.check_keywords(schema)
    assert not checker.validate("valid", schema)


def test_root_identification_and_dialect_headers_remain_optional() -> None:
    schema = {"type": "string"}

    checker.check_keywords(schema)
    assert not checker.validate("valid", schema)


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("$schema", None),
        ("$schema", ""),
        ("$schema", "https://json-schema.org/draft/2019-09/schema"),
        ("$schema", [SUPPORTED_DIALECT]),
        ("$id", None),
        ("$id", ""),
        ("$id", "relative/root"),
        ("$id", "https://example.test/root#fragment"),
        ("$id", "https://example.test/invalid percent"),
        ("$id", "https://example.test/%ZZ"),
    ],
)
def test_unsupported_or_malformed_root_declarations_fail_closed(
    keyword: str,
    value: object,
) -> None:
    with pytest.raises(checker.SubsetError):
        checker.check_keywords({keyword: value})


@pytest.mark.parametrize("identifier", REVIEWED_MALFORMED_ROOT_IDENTIFIERS)
def test_reviewed_malformed_root_identifiers_fail_preflight(
    identifier: str,
) -> None:
    with pytest.raises(checker.SubsetError):
        checker.check_keywords({"$id": identifier, "type": "integer"})


@pytest.mark.parametrize("identifier", MALFORMED_ROOT_IDENTIFIER_EDGE_CASES)
def test_malformed_root_identifier_edge_cases_fail_preflight(
    identifier: str,
) -> None:
    with pytest.raises(checker.SubsetError):
        checker.check_keywords({"$id": identifier, "type": "integer"})


@pytest.mark.parametrize("identifier", SUPPORTED_ROOT_IDENTIFIER_CONTROLS)
def test_supported_root_identifier_controls_pass_preflight(
    identifier: str,
) -> None:
    checker.check_keywords({"$id": identifier, "type": "integer"})


@pytest.mark.parametrize(
    ("schema", "value", "valid"),
    [
        ({"type": "number", "minimum": 1}, 0, False),
        ({"type": "number", "minimum": 1}, 1, True),
        ({"type": "number", "minimum": 1}, 1.5, True),
        ({"type": "number", "maximum": 3}, 4, False),
        ({"type": "number", "maximum": 3}, 3, True),
        ({"type": "integer", "minimum": -1, "maximum": 1}, -1, True),
        ({"type": "integer", "minimum": -1, "maximum": 1}, 1, True),
        ({"type": "integer", "minimum": -1, "maximum": 1}, 2, False),
        ({"type": "number", "minimum": 0}, True, False),
        ({"type": "integer", "maximum": 1}, False, False),
    ],
)
def test_numeric_bounds(schema: dict, value: object, valid: bool) -> None:
    assert (not _errors(value, schema)) is valid


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        (1, True),
        (1.0, True),
        (0.0, True),
        (-2.0, True),
        (1.5, False),
        (True, False),
        (False, False),
        (float("nan"), False),
        (float("inf"), False),
        (float("-inf"), False),
    ],
)
def test_integer_type_uses_finite_mathematical_value(
    value: object,
    valid: bool,
) -> None:
    assert (not _errors(value, {"type": "integer"})) is valid


@pytest.mark.parametrize(
    ("value", "matching_branches"),
    [
        (1, 2),
        (1.0, 2),
        (1.5, 1),
        (True, 0),
    ],
)
def test_integer_and_number_one_of_counts_json_schema_matches(
    value: object,
    matching_branches: int,
) -> None:
    errors = _errors(value, INTEGER_NUMBER_ONE_OF)
    assert jsonschema.Draft202012Validator(INTEGER_NUMBER_ONE_OF).is_valid(value) is (
        matching_branches == 1
    )
    if matching_branches == 1:
        assert errors == []
    else:
        assert any(
            f"oneOf matched {matching_branches} branches" in error
            for error in errors
        )


def test_integral_exponent_notation_uses_integer_value_semantics(
    tmp_path: Path,
) -> None:
    instance_path = tmp_path / "instance.json"
    instance_path.write_text("1e0\n", encoding="utf-8")

    value = checker.load_json(instance_path)

    assert isinstance(value, float)
    assert not _errors(value, {"type": "integer"})
    assert any("matched 2 branches" in error for error in _errors(
        value, INTEGER_NUMBER_ONE_OF
    ))


def test_integer_semantics_apply_beneath_properties_and_local_refs() -> None:
    schema = {
        "$defs": {"numeric": INTEGER_NUMBER_ONE_OF},
        "type": "object",
        "properties": {"value": {"$ref": "#/$defs/numeric"}},
    }

    assert any("matched 2 branches" in error for error in _errors(
        {"value": 1.0}, schema
    ))
    assert not _errors({"value": 1.5}, schema)


def test_large_integer_does_not_require_float_conversion() -> None:
    value = 10**1000

    assert not _errors(value, {"type": "integer"})
    assert any("matched 2 branches" in error for error in _errors(
        value, INTEGER_NUMBER_ONE_OF
    ))


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "positive-infinity", "negative-infinity"],
)
def test_non_finite_float_is_not_a_json_number(value: float) -> None:
    assert any("expected type number" in error for error in _errors(
        value, {"type": "number"}
    ))


@pytest.mark.parametrize(
    ("schema", "value", "valid"),
    [
        ({"const": 1}, True, False),
        ({"enum": [0]}, False, False),
        ({"const": {"nested": 1}}, {"nested": True}, False),
        ({"const": [1, {"nested": 0}]}, [True, {"nested": False}], False),
        ({"const": 1}, 1.0, True),
        ({"enum": [1.0]}, 1, True),
    ],
)
def test_const_and_enum_use_json_equality(
    schema: dict,
    value: object,
    valid: bool,
) -> None:
    assert (not _errors(value, schema)) is valid


@pytest.mark.parametrize("value", [True, 1])
def test_one_of_distinguishes_boolean_and_numeric_constants(value: object) -> None:
    schema = {"oneOf": [{"const": True}, {"const": 1}]}
    assert not _errors(value, schema)


@pytest.mark.parametrize(
    ("schema", "value", "error_text"),
    [
        (
            {"oneOf": [{"const": "A"}, {"const": "B"}], "type": "object"},
            "A",
            "expected type object",
        ),
        (
            {"oneOf": [{"const": {}}, {"const": []}], "required": ["kind"]},
            {},
            "missing required property 'kind'",
        ),
        (
            {
                "oneOf": [{"required": ["kind"]}, {"required": ["other"]}],
                "properties": {"kind": {"const": "A"}},
            },
            {"kind": "B"},
            "expected const 'A'",
        ),
        (
            {"oneOf": [{"const": "A"}, {"const": "B"}], "const": "A"},
            "B",
            "expected const 'A'",
        ),
        (
            {"oneOf": [{"const": "A"}, {"const": "B"}], "pattern": "^A$"},
            "B",
            "does not match pattern",
        ),
    ],
)
def test_one_of_does_not_hide_sibling_assertions(
    schema: dict,
    value: object,
    error_text: str,
) -> None:
    errors = _errors(value, schema)
    assert any(error_text in error for error in errors)


def test_one_of_requires_exactly_one_matching_branch() -> None:
    schema = {"oneOf": [{"type": "number"}, {"minimum": 0}]}
    assert any("matched 2 branches" in error for error in _errors(1, schema))


def test_local_ref_and_its_sibling_assertion_are_both_applied() -> None:
    schema = {
        "$defs": {"bounded": {"type": "integer", "minimum": 1}},
        "$ref": "#/$defs/bounded",
        "maximum": 3,
    }
    assert not _errors(2, schema)
    assert any("minimum 1" in error for error in _errors(0, schema))
    assert any("maximum 3" in error for error in _errors(4, schema))


@pytest.mark.parametrize(
    "ref",
    ["#/$defs/missing", "#/$defs/bad~2token", "contracts/schema.json"],
)
def test_invalid_local_ref_fails_closed(ref: str) -> None:
    schema = {"$defs": {"valid": {"type": "string"}}, "$ref": ref}
    with pytest.raises(checker.SubsetError):
        checker.check_keywords(schema)


@pytest.mark.parametrize(
    "schema",
    [
        {"$ref": "#"},
        {"$defs": {"loop": {"$ref": "#/$defs/loop"}}, "$ref": "#/$defs/loop"},
        {
            "$defs": {
                "a": {"$ref": "#/$defs/b"},
                "b": {"$ref": "#/$defs/a"},
            },
            "$ref": "#/$defs/a",
        },
    ],
)
def test_local_ref_cycles_fail_closed(schema: dict) -> None:
    with pytest.raises(checker.SubsetError, match="cyclic"):
        checker.check_keywords(schema)


def test_local_ref_may_be_reused_on_independent_paths() -> None:
    schema = {
        "$defs": {"label": {"type": "string", "pattern": "^[A-Z]+$"}},
        "type": "object",
        "properties": {
            "first": {"$ref": "#/$defs/label"},
            "second": {"$ref": "#/$defs/label"},
        },
    }
    assert not _errors({"first": "A", "second": "B"}, schema)


def _schema_with_nested_declaration(location: str, keyword: str) -> dict:
    declaration = {
        keyword: (
            "https://example.test/inner"
            if keyword == "$id"
            else SUPPORTED_DIALECT
        )
    }
    if location == "$defs":
        return {"$defs": {"unused": declaration}}
    if location == "properties":
        return {"properties": {"value": declaration}}
    if location == "items":
        return {"items": declaration}
    if location == "oneOf":
        return {"oneOf": [{"const": "selected"}, declaration]}
    raise AssertionError(f"unknown schema-bearing location {location!r}")


@pytest.mark.parametrize("keyword", ["$id", "$schema"])
@pytest.mark.parametrize("location", ["$defs", "properties", "items", "oneOf"])
def test_nested_resources_and_dialects_fail_before_instance_evaluation(
    location: str,
    keyword: str,
) -> None:
    schema = _schema_with_nested_declaration(location, keyword)

    with pytest.raises(checker.SubsetError, match="nested"):
        checker.check_keywords(schema)


@pytest.mark.parametrize(
    ("schema", "instance"),
    [
        (
            {"const": {"$id": "literal", "$schema": "literal"}},
            {"$id": "literal", "$schema": "literal"},
        ),
        (
            {"enum": [{"$id": "literal", "$schema": "literal"}]},
            {"$id": "literal", "$schema": "literal"},
        ),
        (
            {
                "type": "object",
                "properties": {
                    "$id": {"type": "string"},
                    "$schema": {"type": "string"},
                },
            },
            {"$id": "instance value", "$schema": "instance value"},
        ),
    ],
    ids=["const-data", "enum-data", "property-names"],
)
def test_instance_valued_data_is_not_treated_as_a_schema_declaration(
    schema: dict,
    instance: object,
) -> None:
    assert not _errors(instance, schema)


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "string", "format": "email"},
        {"type": "object", "additionalProperties": {"type": "string"}},
        {"type": "string", "unknownAssertion": True},
        {"type": ["string", "null"]},
        {"type": "object", "required": "name"},
        {"type": "object", "properties": []},
        {"$defs": []},
        {"properties": {"name": True}},
        {"type": "array", "items": True},
        {"oneOf": []},
        {"oneOf": [True]},
        {"type": "string", "pattern": "["},
        {"type": "array", "minItems": -1},
        {"type": "array", "maxItems": False},
        {"type": "string", "minLength": -1},
        {"type": "number", "minimum": True},
        {"type": "string", "format": ["date-time"]},
        {"enum": []},
        True,
    ],
)
def test_unsupported_or_malformed_schema_forms_fail_closed(schema: object) -> None:
    with pytest.raises(checker.SubsetError):
        checker.check_keywords(schema)


def test_boolean_additional_properties_forms_are_explicit() -> None:
    closed = {
        "type": "object",
        "properties": {"known": {"type": "string"}},
        "additionalProperties": False,
    }
    opened = {**closed, "additionalProperties": True}
    value = {"known": "yes", "extra": "permitted only when open"}
    assert any("additional property 'extra'" in error for error in _errors(value, closed))
    assert not _errors(value, opened)


def _run_package_main(
    root: Path,
    schema: dict,
    instance: object,
) -> subprocess.CompletedProcess[str]:
    (root / "contracts").mkdir(parents=True)
    (root / "reference").mkdir()
    empty_manifest = json.dumps({"entries": [], "fixtureEntries": []})
    (root / "contracts/CONTRACTS_MANIFEST.json").write_text(
        empty_manifest,
        encoding="utf-8",
    )
    (root / "reference/REFERENCE_MANIFEST.json").write_text(
        empty_manifest,
        encoding="utf-8",
    )
    (root / "schema.json").write_text(
        json.dumps(schema, allow_nan=False),
        encoding="utf-8",
    )
    (root / "instance.json").write_text(
        json.dumps(instance, allow_nan=False),
        encoding="utf-8",
    )
    script = "\n".join(
        [
            "from pathlib import Path",
            "from types import SimpleNamespace",
            "from conformance import ofarm_pkg_contract_check as checker",
            f"checker.PKG = Path({str(root)!r})",
            "checker.INSTANCE_BINDINGS = {'instance.json': 'schema.json'}",
            "checker.subprocess.run = lambda *args, **kwargs: "
            "SimpleNamespace(returncode=0)",
            "raise SystemExit(checker.main())",
        ]
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=PACKAGE_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_every_bound_instance_still_validates() -> None:
    for instance_rel, schema_rel in checker.INSTANCE_BINDINGS.items():
        instance = checker.load_json(PACKAGE_ROOT / instance_rel)
        schema = checker.load_json(PACKAGE_ROOT / schema_rel)
        assert not _errors(instance, schema), instance_rel


def test_bound_pack_activation_set_rejects_invalid_evaluated_at() -> None:
    instance_rel = "profile_si_ffs/OFARM_PackActivationSet_example_si_ffs_pilot_v0_1.json"
    schema_rel = "contracts/platform/OFARM_PackActivationSet_schema_v0_1.json"
    instance = json.loads((PACKAGE_ROOT / instance_rel).read_text(encoding="utf-8"))
    schema = json.loads((PACKAGE_ROOT / schema_rel).read_text(encoding="utf-8"))
    instance["evaluatedAt"] = "not-a-date"
    assert any("$.evaluatedAt" in error for error in _errors(instance, schema))


def test_child_process_reports_invalid_bound_date_time(tmp_path: Path) -> None:
    schema = {
        "type": "object",
        "required": ["evaluatedAt"],
        "properties": {
            "evaluatedAt": {"type": "string", "format": "date-time"}
        },
    }
    process = _run_package_main(
        tmp_path,
        schema,
        {"evaluatedAt": "not-a-date"},
    )

    assert process.returncode != 0
    assert "INVALID instance.json" in process.stdout
    assert "format date-time" in process.stdout
    assert "RESULT: FAIL (1 failures)" in process.stdout
    assert checker.PKG == PACKAGE_ROOT


def test_child_main_rejects_integer_number_one_of_overlap(tmp_path: Path) -> None:
    invalid = _run_package_main(
        tmp_path / "integral",
        INTEGER_NUMBER_ONE_OF,
        1.0,
    )
    valid = _run_package_main(
        tmp_path / "fractional",
        {
            "$schema": SUPPORTED_DIALECT,
            "$id": "https://example.test/numeric",
            "$defs": {"numeric": INTEGER_NUMBER_ONE_OF},
            "$ref": "#/$defs/numeric",
        },
        1.5,
    )

    assert invalid.returncode != 0
    assert "INVALID instance.json" in invalid.stdout
    assert "oneOf matched 2 branches" in invalid.stdout
    assert "RESULT: FAIL (1 failures)" in invalid.stdout
    assert valid.returncode == 0, valid.stdout + valid.stderr
    assert "RESULT: PASS (0 failures)" in valid.stdout


@pytest.mark.parametrize("identifier", REVIEWED_MALFORMED_ROOT_IDENTIFIERS)
def test_child_main_rejects_reviewed_malformed_root_identifiers(
    tmp_path: Path,
    identifier: str,
) -> None:
    process = _run_package_main(
        tmp_path,
        {"$schema": SUPPORTED_DIALECT, "$id": identifier, "type": "integer"},
        1,
    )

    assert process.returncode != 0
    assert "SUBSET GAP schema.json" in process.stdout
    assert "root $id" in process.stdout
    assert "RESULT: FAIL (1 failures)" in process.stdout


@pytest.mark.parametrize("identifier", SUPPORTED_ROOT_IDENTIFIER_CONTROLS)
def test_child_main_accepts_supported_root_identifier_controls(
    tmp_path: Path,
    identifier: str,
) -> None:
    process = _run_package_main(
        tmp_path,
        {"$schema": SUPPORTED_DIALECT, "$id": identifier, "type": "integer"},
        1,
    )

    assert process.returncode == 0, process.stdout + process.stderr
    assert "RESULT: PASS (0 failures)" in process.stdout


@pytest.mark.parametrize(
    ("instance", "full_validator_valid"),
    [({"value": 1}, False), ({"value": 150}, True)],
    ids=["full-validator-invalid", "full-validator-valid"],
)
def test_child_main_refuses_nested_schema_resources_before_validation(
    tmp_path: Path,
    instance: dict,
    full_validator_valid: bool,
) -> None:
    process = _run_package_main(tmp_path, NESTED_RESOURCE_SCHEMA, instance)

    assert jsonschema.Draft202012Validator(NESTED_RESOURCE_SCHEMA).is_valid(instance) is (
        full_validator_valid
    )
    assert process.returncode != 0
    assert "SUBSET GAP schema.json" in process.stdout
    assert "nested $id" in process.stdout
    assert "RESULT: FAIL (1 failures)" in process.stdout


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_strict_json_loader_rejects_non_json_numbers(
    tmp_path: Path,
    constant: str,
) -> None:
    path = tmp_path / "non-json-number.json"
    path.write_text(constant, encoding="utf-8")
    with pytest.raises(checker.StrictJsonError):
        checker.load_json(path)


def test_child_process_rejects_bound_non_finite_number(tmp_path: Path) -> None:
    (tmp_path / "schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "required": ["value"],
                "properties": {
                    "value": {"type": "number", "minimum": 0, "maximum": 10}
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "instance.json").write_text(
        '{"value": NaN}',
        encoding="utf-8",
    )
    script = "\n".join(
        [
            "from pathlib import Path",
            "from conformance import ofarm_pkg_contract_check as checker",
            f"checker.PKG = Path({str(tmp_path)!r})",
            "checker.INSTANCE_BINDINGS = {'instance.json': 'schema.json'}",
            "raise SystemExit(1 if checker.check_instance_bindings() else 0)",
        ]
    )
    process = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PACKAGE_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode != 0
    assert "INVALID instance.json" in process.stdout
    assert "non-JSON numeric constant 'NaN'" in process.stdout
