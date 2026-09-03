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
    ],
)
def test_date_time_matches_locked_full_validator(value: str, valid: bool) -> None:
    assert FULL_DATE_TIME_VALIDATOR.is_valid(value) is valid
    assert (not _errors(value, DATE_TIME_SCHEMA)) is valid


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


def test_every_bound_instance_still_validates() -> None:
    for instance_rel, schema_rel in checker.INSTANCE_BINDINGS.items():
        instance = json.loads((PACKAGE_ROOT / instance_rel).read_text(encoding="utf-8"))
        schema = json.loads((PACKAGE_ROOT / schema_rel).read_text(encoding="utf-8"))
        assert not _errors(instance, schema), instance_rel


def test_bound_pack_activation_set_rejects_invalid_evaluated_at() -> None:
    instance_rel = "profile_si_ffs/OFARM_PackActivationSet_example_si_ffs_pilot_v0_1.json"
    schema_rel = "contracts/platform/OFARM_PackActivationSet_schema_v0_1.json"
    instance = json.loads((PACKAGE_ROOT / instance_rel).read_text(encoding="utf-8"))
    schema = json.loads((PACKAGE_ROOT / schema_rel).read_text(encoding="utf-8"))
    instance["evaluatedAt"] = "not-a-date"
    assert any("$.evaluatedAt" in error for error in _errors(instance, schema))


def test_child_process_reports_invalid_bound_date_time(tmp_path: Path) -> None:
    (tmp_path / "schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "required": ["evaluatedAt"],
                "properties": {
                    "evaluatedAt": {"type": "string", "format": "date-time"}
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "instance.json").write_text(
        json.dumps({"evaluatedAt": "not-a-date"}),
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
    assert "format date-time" in process.stdout
    assert checker.PKG == PACKAGE_ROOT


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
