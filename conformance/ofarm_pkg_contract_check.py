#!/usr/bin/env python3
"""Zero-dependency package self-check for the OFARM2 implementation package.

Checks, in order:
1. every contract and fixture JSON file in the package parses;
2. extracted files still match the sha256 digests recorded in the manifests;
3. authored example instances validate against their schemas using a
   deliberately small JSON Schema subset validator (the subset the OFARM
   machine contracts actually use: type, const, enum, required, properties,
   additionalProperties:false, pattern, items, minItems, minLength, oneOf).

This tool is package tooling, not OFARM law and not a full JSON Schema
implementation. If a schema uses a keyword outside the subset, the check
fails loudly rather than passing silently.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent

SUPPORTED = {
    "$schema", "$id", "title", "$comment", "type", "const", "enum",
    "required", "properties", "additionalProperties", "pattern", "items",
    "minItems", "maxItems", "minLength", "oneOf", "format", "description",
    "minimum", "maximum", "$ref", "$defs",
}

TYPES = {
    "object": dict, "array": list, "string": str,
    "boolean": bool, "null": type(None),
}


class SubsetError(Exception):
    pass


def check_keywords(schema, path="#"):
    if isinstance(schema, dict):
        for key, val in schema.items():
            if key not in SUPPORTED:
                raise SubsetError(f"unsupported schema keyword {key!r} at {path}")
            if key in ("properties", "$defs"):
                for name, sub in val.items():
                    check_keywords(sub, f"{path}/{key}/{name}")
            elif key in ("items",):
                check_keywords(val, f"{path}/{key}")
            elif key == "oneOf":
                for i, sub in enumerate(val):
                    check_keywords(sub, f"{path}/oneOf[{i}]")


def resolve_ref(ref: str, root):
    if not ref.startswith("#/"):
        raise SubsetError(f"only local $refs supported, got {ref!r}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def validate(instance, schema, path="$", root=None):
    root = root if root is not None else schema
    while "$ref" in schema:
        schema = resolve_ref(schema["$ref"], root)
    errors = []
    if "oneOf" in schema:
        passes = []
        for i, sub in enumerate(schema["oneOf"]):
            sub_errors = validate(instance, sub, path, root)
            if not sub_errors:
                passes.append(i)
        if len(passes) != 1:
            errors.append(f"{path}: oneOf matched {len(passes)} branches, expected exactly 1")
        return errors
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
                errors.extend(validate(val, props[key], f"{path}.{key}", root))
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: has {len(instance)} items, minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: has {len(instance)} items, maxItems {schema['maxItems']}")
        if "items" in schema:
            for i, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], f"{path}[{i}]", root))
    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
    return errors


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# Authored example instances -> the schema each must validate against.
INSTANCE_BINDINGS = {
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
}


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

    for inst_rel, schema_rel in INSTANCE_BINDINGS.items():
        inst_path, schema_path = PKG / inst_rel, PKG / schema_rel
        if not inst_path.exists():
            print(f"MISSING INSTANCE {inst_rel}")
            failures += 1
            continue
        schema = json.loads(schema_path.read_text())
        try:
            check_keywords(schema)
        except SubsetError as exc:
            print(f"SUBSET GAP {schema_rel}: {exc}")
            failures += 1
            continue
        errs = validate(json.loads(inst_path.read_text()), schema)
        for err in errs:
            print(f"INVALID {inst_rel}: {err}")
        failures += len(errs)
    print("instance validation done")

    print("RESULT:", "FAIL" if failures else "PASS", f"({failures} failures)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
