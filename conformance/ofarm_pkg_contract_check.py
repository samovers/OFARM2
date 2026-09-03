#!/usr/bin/env python3
"""Zero-dependency package self-check for the OFARM2 implementation package.

Checks, in order:
1. every contract and fixture JSON file in the package parses;
2. extracted files still match the sha256 digests recorded in the manifests;
3. authored example instances validate against their schemas using a
   deliberately small JSON Schema subset validator (the subset the OFARM
   machine contracts actually use: type, const, enum, required, properties,
   Boolean additionalProperties, pattern, items, item/length bounds, oneOf,
   local references, date-time format, and numeric bounds).
4. the non-default temporal-governance coordinate, carrier matrix,
   intervention carrier-selection, governed-command, and RuntimeBundle carrier
   candidates satisfy their semantic and non-activation contracts; and
5. rewritten trust-boundary modules satisfy their architecture and size gates.

This tool is package tooling, not OFARM law and not a full JSON Schema
implementation. If a schema uses a keyword outside the subset, the check
fails loudly rather than passing silently.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent

ANNOTATION_KEYWORDS = frozenset({
    "$schema", "$id", "title", "$comment", "description",
})
APPLICATOR_KEYWORDS = frozenset({
    "$ref", "$defs", "properties", "items", "oneOf",
})
ASSERTION_KEYWORDS = frozenset({
    "type", "const", "enum", "required", "additionalProperties", "pattern",
    "minItems", "maxItems", "minLength", "format", "minimum", "maximum",
})
SUPPORTED_KEYWORDS = (
    ANNOTATION_KEYWORDS | APPLICATOR_KEYWORDS | ASSERTION_KEYWORDS
)
SUPPORTED_TYPES = frozenset({
    "object", "array", "string", "number", "integer", "boolean", "null",
})
SUPPORTED_FORMATS = frozenset({"date-time"})

TYPES = {
    "object": dict, "array": list, "string": str,
    "boolean": bool, "null": type(None),
}


class SubsetError(Exception):
    pass


def _schema_path(path: str, part: object) -> str:
    escaped = str(part).replace("~", "~0").replace("/", "~1")
    return f"{path}/{escaped}"


def _json_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _non_negative_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _decode_pointer_part(part: str, *, ref: str) -> str:
    if "%" in part or re.search(r"~(?:[^01]|$)", part):
        raise SubsetError(f"malformed local $ref {ref!r}")
    return part.replace("~1", "/").replace("~0", "~")


def resolve_ref(ref: str, root, *, path: str = "#"):
    if not isinstance(ref, str) or (ref != "#" and not ref.startswith("#/")):
        raise SubsetError(f"only local JSON Pointer $refs supported at {path}, got {ref!r}")
    if ref == "#":
        return root
    node = root
    for part in ref[2:].split("/"):
        decoded = _decode_pointer_part(part, ref=ref)
        if not isinstance(node, dict) or decoded not in node:
            raise SubsetError(f"unresolved local $ref {ref!r} at {path}")
        node = node[decoded]
    return node


def _check_schema_subset(schema, *, root, path: str, ref_stack: tuple[str, ...]):
    if not isinstance(schema, dict):
        raise SubsetError(f"schema at {path} must be an object")

    for key in schema:
        if key not in SUPPORTED_KEYWORDS:
            raise SubsetError(f"unsupported schema keyword {key!r} at {path}")

    if "type" in schema:
        value = schema["type"]
        if not isinstance(value, str) or value not in SUPPORTED_TYPES:
            raise SubsetError(f"unsupported type {value!r} at {path}/type")
    if "enum" in schema:
        value = schema["enum"]
        if not isinstance(value, list) or not value:
            raise SubsetError(f"enum at {path}/enum must be a non-empty list")
    if "required" in schema:
        value = schema["required"]
        if (not isinstance(value, list)
                or any(not isinstance(item, str) for item in value)
                or len(value) != len(set(value))):
            raise SubsetError(
                f"required at {path}/required must be a list of unique strings"
            )
    for keyword in ("properties", "$defs"):
        if keyword not in schema:
            continue
        value = schema[keyword]
        if not isinstance(value, dict):
            raise SubsetError(f"{keyword} at {path}/{keyword} must be an object")
        for name, subschema in value.items():
            _check_schema_subset(
                subschema,
                root=root,
                path=_schema_path(f"{path}/{keyword}", name),
                ref_stack=ref_stack,
            )
    if "items" in schema:
        _check_schema_subset(
            schema["items"], root=root, path=f"{path}/items", ref_stack=ref_stack
        )
    if "oneOf" in schema:
        value = schema["oneOf"]
        if not isinstance(value, list) or not value:
            raise SubsetError(f"oneOf at {path}/oneOf must be a non-empty list")
        for index, subschema in enumerate(value):
            _check_schema_subset(
                subschema,
                root=root,
                path=f"{path}/oneOf/{index}",
                ref_stack=ref_stack,
            )
    if "pattern" in schema:
        value = schema["pattern"]
        if not isinstance(value, str):
            raise SubsetError(f"pattern at {path}/pattern must be a string")
        try:
            re.compile(value)
        except re.error as exc:
            raise SubsetError(f"invalid pattern at {path}/pattern: {exc}") from exc
    for keyword in ("minItems", "maxItems", "minLength"):
        if keyword in schema and not _non_negative_integer(schema[keyword]):
            raise SubsetError(
                f"{keyword} at {path}/{keyword} must be a non-negative integer"
            )
    for keyword in ("minimum", "maximum"):
        if keyword in schema and not _json_number(schema[keyword]):
            raise SubsetError(
                f"{keyword} at {path}/{keyword} must be a JSON number"
            )
    if "format" in schema:
        value = schema["format"]
        if not isinstance(value, str) or value not in SUPPORTED_FORMATS:
            raise SubsetError(f"unsupported format {value!r} at {path}/format")
    if ("additionalProperties" in schema
            and not isinstance(schema["additionalProperties"], bool)):
        raise SubsetError(
            f"additionalProperties at {path}/additionalProperties must be Boolean"
        )
    if "$ref" in schema:
        ref = schema["$ref"]
        target = resolve_ref(ref, root, path=f"{path}/$ref")
        if ref in ref_stack:
            chain = " -> ".join((*ref_stack, ref))
            raise SubsetError(f"cyclic local $ref at {path}/$ref: {chain}")
        _check_schema_subset(
            target,
            root=root,
            path=f"{path}/$ref({ref})",
            ref_stack=(*ref_stack, ref),
        )


def check_keywords(schema, path="#"):
    """Fail closed unless *schema* uses only supported keyword forms."""
    _check_schema_subset(schema, root=schema, path=path, ref_stack=())


_RFC3339_DATE_TIME = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt]"
    r"(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?"
    r"(?:[Zz]|([+-])(\d{2}):(\d{2}))$"
)


def _is_rfc3339_datetime(value: str) -> bool:
    match = _RFC3339_DATE_TIME.fullmatch(value)
    if match is None:
        return False
    year, month, day, hour, minute, second, _, offset_hour, offset_minute = (
        match.groups()
    )
    try:
        date(int(year), int(month), int(day))
    except ValueError:
        return False
    if int(hour) > 23 or int(minute) > 59 or int(second) > 59:
        return False
    return not offset_hour or (
        int(offset_hour) <= 23 and int(offset_minute) <= 59
    )


def validate(instance, schema, path="$", root=None, _ref_stack=()):
    root = root if root is not None else schema
    errors = []
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref in _ref_stack:
            chain = " -> ".join((*_ref_stack, ref))
            raise SubsetError(f"cyclic local $ref while validating {path}: {chain}")
        target = resolve_ref(ref, root, path="$ref")
        errors.extend(validate(
            instance, target, path, root, (*_ref_stack, ref)
        ))
    if "oneOf" in schema:
        passes = []
        for i, sub in enumerate(schema["oneOf"]):
            sub_errors = validate(instance, sub, path, root, _ref_stack)
            if not sub_errors:
                passes.append(i)
        if len(passes) != 1:
            errors.append(f"{path}: oneOf matched {len(passes)} branches, expected exactly 1")
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value {instance!r} not in enum")
    if "type" in schema:
        expected = schema["type"]
        if expected == "number":
            ok = isinstance(instance, (int, float)) and not isinstance(instance, bool)
        elif expected == "integer":
            ok = isinstance(instance, int) and not isinstance(instance, bool)
        else:
            ok = isinstance(instance, TYPES[expected])
        if not ok:
            errors.append(f"{path}: expected type {expected}, got {type(instance).__name__}")
            return errors
    if _json_number(instance):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(
                f"{path}: value {instance!r} is below minimum {schema['minimum']!r}"
            )
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(
                f"{path}: value {instance!r} is above maximum {schema['maximum']!r}"
            )
    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required property {req!r}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(f"{path}: additional property {key!r} not allowed")
        for key, val in instance.items():
            if key in props:
                errors.extend(validate(
                    val, props[key], f"{path}.{key}", root, _ref_stack
                ))
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: has {len(instance)} items, minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: has {len(instance)} items, maxItems {schema['maxItems']}")
        if "items" in schema:
            for i, item in enumerate(instance):
                errors.extend(validate(
                    item, schema["items"], f"{path}[{i}]", root, _ref_stack
                ))
    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if (schema.get("format") == "date-time"
                and not _is_rfc3339_datetime(instance)):
            errors.append(f"{path}: {instance!r} is not a valid format date-time")
    return errors


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# Authored example instances -> the schema each must validate against.
INSTANCE_BINDINGS = {
    "contracts/candidates/temporal_runtime_bundle_carrier/"
    "OFARM_TemporalGovernanceRuntimeBundleCarrier_candidate_v0_1.json":
        "contracts/candidates/temporal_runtime_bundle_carrier/"
        "OFARM_TemporalGovernanceRuntimeBundleCarrierBinding_schema_v0_1.json",
    "contracts/candidates/temporal_governed_command/"
    "OFARM_OperationClaimDraftTemporalCommand_candidate_v0_1.json":
        "contracts/candidates/temporal_governed_command/"
        "OFARM_TemporalGovernedCommandBinding_schema_v0_1.json",
    "contracts/candidates/temporal_carrier_selection/"
    "OFARM_InterventionValidTimeCarrierSelection_candidate_v0_1.json":
        "contracts/candidates/temporal_carrier_selection/"
        "OFARM_TemporalCarrierSelectionBinding_schema_v0_1.json",
    "profile_si_ffs/OFARM_PackActivationSet_example_si_ffs_pilot_v0_1.json":
        "contracts/platform/OFARM_PackActivationSet_schema_v0_1.json",
    "profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json":
        "contracts/platform/OFARM_ActiveArtifactSet_schema_v0_1.json",
    "profile_si_ffs/OFARM_ContextSnapshot_example_si_ffs_pilot_compliance_v0_1.json":
        "contracts/kernel/OFARM_ContextSnapshot_schema_v0_1.json",
    "profile_si_ffs/OFARM_AgronomicCodeBindingProfile_si_ffs_v0_1.json":
        "contracts/core/OFARM_AgronomicCodeBindingProfile_schema_v0_1.json",
    "profile_si_ffs/OFARM_ReferenceSnapshot_example_si_uvhvvr_ffs_reg_2026-06-11.json":
        "contracts/core/OFARM_ReferenceSnapshot_schema_v0_1.json",
    "profile_si_ffs/OFARM_ReferenceSnapshot_example_si_gerk_layer_2025-06-30.json":
        "contracts/core/OFARM_ReferenceSnapshot_schema_v0_1.json",
    # M1 deliverables (M1_BRIEF tasks 6-7). The two QuerySpecification
    # artifacts are deliberately NOT bound here: their schema uses allOf/
    # if/then/default, outside this validator's declared keyword subset
    # (it would fail loudly with SUBSET GAP) — they are fully validated by
    # kernel/tests/test_conformance.py with a complete 2020-12 validator.
    "profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json":
        "contracts/platform/OFARM_Capability_Manifest_schema_v0_1.json",
    "profile_si_ffs/views/OFARM_QueryPlanIR_si_ffs_spray_register_passportview_v0_1.json":
        "contracts/platform/OFARM_QueryPlanIR_schema_v0_1.json",
    "profile_si_ffs/views/OFARM_QueryPlanIR_si_ffs_inspection_register_documentassembly_v0_1.json":
        "contracts/platform/OFARM_QueryPlanIR_schema_v0_1.json",
}


def check_instance_bindings() -> int:
    """Validate authored instance bindings and return their failure count."""
    failures = 0
    for inst_rel, schema_rel in INSTANCE_BINDINGS.items():
        inst_path, schema_path = PKG / inst_rel, PKG / schema_rel
        if not inst_path.exists():
            print(f"MISSING INSTANCE {inst_rel}")
            failures += 1
            continue
        schema = json.loads(schema_path.read_text())
        try:
            check_keywords(schema)
            errors = validate(json.loads(inst_path.read_text()), schema)
        except SubsetError as exc:
            print(f"SUBSET GAP {schema_rel}: {exc}")
            failures += 1
            continue
        for error in errors:
            print(f"INVALID {inst_rel}: {error}")
        failures += len(errors)
    return failures


def main() -> int:
    failures = 0

    for jf in sorted(PKG.rglob("*.json")):
        try:
            json.loads(jf.read_text())
        except json.JSONDecodeError as exc:
            print(f"PARSE FAIL {jf.relative_to(PKG)}: {exc}")
            failures += 1
    print("parse check done")

    for manifest_rel in ("contracts/CONTRACTS_MANIFEST.json", "reference/REFERENCE_MANIFEST.json"):
        manifest = json.loads((PKG / manifest_rel).read_text())
        entries = manifest.get("entries", []) + manifest.get("fixtureEntries", [])
        for entry in entries:
            if entry.get("status") == "NEW_CANDIDATE":
                continue
            target = PKG / entry["packagePath"]
            if not target.exists():
                print(f"MISSING {entry['packagePath']}")
                failures += 1
            elif "sha256" in entry and sha256(target) != entry["sha256"]:
                print(f"DIGEST DRIFT {entry['packagePath']}")
                failures += 1
    print("digest check done")

    failures += check_instance_bindings()
    print("instance validation done")

    temporal_candidate = subprocess.run(
        [
            sys.executable,
            str(PKG / "conformance/temporal_contract_candidate_check.py"),
        ],
        check=False,
    )
    if temporal_candidate.returncode != 0:
        failures += 1
    print("temporal candidate check done")

    temporal_decision_log = subprocess.run(
        [
            sys.executable,
            str(PKG / "conformance/temporal_decision_log_check.py"),
        ],
        check=False,
    )
    if temporal_decision_log.returncode != 0:
        failures += 1
    print("temporal decision log check done")

    architecture = subprocess.run(
        [sys.executable, str(PKG / "conformance/rewrite_architecture_check.py")],
        check=False,
    )
    if architecture.returncode != 0:
        failures += 1
    print("architecture check done")

    print("RESULT:", "FAIL" if failures else "PASS", f"({failures} failures)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
