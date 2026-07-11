#!/usr/bin/env python3
"""Generate or verify the code-owned RuntimeBundle component lock.

Normal runtime startup only verifies ``kernel/runtime_bundle.lock.json``.  This
tool is the explicit maintenance path when runtime-consumed repository content
changes.  Its catalog is deterministic and fails on duplicate paths or
role/logical-ref identities before it writes anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "kernel" / "runtime_bundle.lock.json"
LOCK_VERSION = "ofarm.runtime-bundle-component-lock.local.v2"
JSON_CANONICALIZATION = "OFARM_CANONICAL_JSON_V1"
RAW_CANONICALIZATION = "EXACT_BYTES_V1"
GLOBAL_CONTENT_PLACEMENT = "GLOBAL_IMMUTABLE_CONTENT"
TENANT_CONTENT_PLACEMENT = "TENANT_RUNTIME_SELECTION"

_TENANT_PROFILE_INSTANCE_KINDS = {
    "ofarm.activeartifactset.v0.1",
    "ofarm.packactivationset.v0.1",
    "ofarm.contextsnapshot.v0.1",
}
_GLOBAL_PROFILE_INSTANCE_KINDS = {
    "ofarm.agronomiccodebindingprofile.v0.1",
}


class CatalogError(RuntimeError):
    pass


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str):
    raise CatalogError(f"non-finite JSON number {value!r} is forbidden")


def _json(path: Path) -> dict:
    try:
        text = path.read_bytes().decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        raise CatalogError(f"catalog JSON is not strict UTF-8: {path}") from exc
    if text.startswith("\ufeff"):
        raise CatalogError(f"catalog JSON must not contain a UTF-8 BOM: {path}")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
        )
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except CatalogError:
        raise
    except (UnicodeError, ValueError, TypeError) as exc:
        raise CatalogError(f"catalog JSON is malformed: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CatalogError(f"catalog JSON must be an object: {path}")
    return value


def _canonical_bytes(path: Path, canonicalization: str) -> bytes:
    if canonicalization == RAW_CANONICALIZATION:
        return path.read_bytes()
    return json.dumps(
        _json(path), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _placement(role: str, canonicalization: str, canonical: bytes) -> str:
    if role in {
            "PROFILE_DESCRIPTOR", "QUERY_PLAN", "REFERENCE_DATA", "TENANT_BINDING"}:
        if role == "TENANT_BINDING":
            payload = json.loads(canonical, object_pairs_hook=_reject_duplicate_keys)
            if (payload.get("schemaVersion") !=
                    "ofarm.runtime-tenant-binding.local.v1"
                    or not isinstance(payload.get("tenantRef"), str)
                    or not payload["tenantRef"]):
                raise CatalogError("runtime tenant binding is malformed")
        return TENANT_CONTENT_PLACEMENT
    if role not in {"PROFILE_INSTANCE", "ACTIVE_MANIFEST"}:
        return GLOBAL_CONTENT_PLACEMENT
    if canonicalization != JSON_CANONICALIZATION:
        raise CatalogError(f"placement-bearing role {role!r} must be canonical JSON")
    try:
        payload = json.loads(canonical, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, ValueError) as exc:
        raise CatalogError(f"placement-bearing role {role!r} is malformed") from exc
    kind = payload.get("schemaVersion") if isinstance(payload, dict) else None
    if role == "ACTIVE_MANIFEST":
        if (kind != "ofarm.capabilitymanifest.v0.1"
                or (payload.get("deploymentScope") or {}).get("scopeType") != "TENANT"):
            raise CatalogError(
                "the active capability manifest must remain explicit tenant state")
        return TENANT_CONTENT_PLACEMENT
    if kind in _TENANT_PROFILE_INSTANCE_KINDS:
        return TENANT_CONTENT_PLACEMENT
    if kind in _GLOBAL_PROFILE_INSTANCE_KINDS:
        return GLOBAL_CONTENT_PLACEMENT
    raise CatalogError(
        f"profile instance kind {kind!r} has no reviewed RuntimeBundle placement")


def _profile_instance_ref(payload: dict, path: Path) -> str:
    for key in (
        "activeArtifactSetId",
        "packActivationSetId",
        "agronomicCodeBindingProfileId",
        "contextSnapshotId",
        "referenceSnapshotId",
        "manifestId",
    ):
        if isinstance(payload.get(key), str) and payload[key]:
            return payload[key]
    raise CatalogError(f"profile instance has no known identity: {path}")


def build_catalog() -> dict:
    entries: list[dict] = []

    def add(role: str, logical_ref: str, relative: Path,
            canonicalization: str) -> None:
        path = ROOT / relative
        if not path.is_file():
            raise CatalogError(f"catalog path is absent: {relative}")
        canonical = _canonical_bytes(path, canonicalization)
        entries.append({
            "role": role,
            "logicalRef": logical_ref,
            "path": relative.as_posix(),
            "canonicalization": canonicalization,
            "sha256": "sha256:" + hashlib.sha256(canonical).hexdigest(),
            "placement": _placement(role, canonicalization, canonical),
        })

    descriptor_path = Path("profile_si_ffs/runtime_profile_descriptor.json")
    descriptor = _json(ROOT / descriptor_path)
    add("PROFILE_DESCRIPTOR", descriptor["profileRef"], descriptor_path,
        JSON_CANONICALIZATION)

    policy_path = descriptor_path.parent / descriptor["evidencePolicyPath"]
    policy = _json(ROOT / policy_path)
    add("PROFILE_POLICY", policy["policyId"], policy_path,
        JSON_CANONICALIZATION)

    tenant_binding_path = Path("profile_si_ffs/runtime_tenant_binding.json")
    add("TENANT_BINDING", "tenant-binding:active", tenant_binding_path,
        JSON_CANONICALIZATION)

    for filename in descriptor["profileInstanceFiles"]:
        relative = descriptor_path.parent / filename
        payload = _json(ROOT / relative)
        role = ("REFERENCE_SNAPSHOT" if "referenceSnapshotId" in payload
                else "PROFILE_INSTANCE")
        add(role, _profile_instance_ref(payload, relative), relative,
            JSON_CANONICALIZATION)

    manifest_path = Path(
        "profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json")
    manifest = _json(ROOT / manifest_path)
    add("ACTIVE_MANIFEST", manifest["manifestId"], manifest_path,
        JSON_CANONICALIZATION)

    # All four authored executable query/view plans are runtime selection
    # inputs. VIEWS.md is explanatory documentation and is intentionally not.
    for path in sorted((ROOT / "profile_si_ffs" / "views").glob("*.json")):
        relative = path.relative_to(ROOT)
        payload = _json(path)
        if payload.get("schemaVersion") == "ofarm.queryspec.v0.1":
            add("QUERY_SPECIFICATION", payload["queryId"], relative,
                JSON_CANONICALIZATION)
        elif payload.get("schemaVersion") == "ofarm.queryplanir.v0.1":
            add("QUERY_PLAN", payload["planId"], relative,
                JSON_CANONICALIZATION)
        else:
            raise CatalogError(f"unknown executable view artifact: {relative}")

    for path in sorted((ROOT / "contracts").rglob("*.json")):
        relative = path.relative_to(ROOT)
        payload = _json(path)
        schema_version = (
            (payload.get("properties") or {}).get("schemaVersion") or {}
        ).get("const")
        if schema_version:
            role, logical_ref = "CONTRACT_SCHEMA", f"contract:{schema_version}"
        elif path.name == "CONTRACTS_MANIFEST.json":
            role, logical_ref = "CONTRACT_MANIFEST", "manifest:contracts"
        else:
            role = "CONTRACT_METADATA"
            logical_ref = f"contract-file:{relative.as_posix()}"
        # ContractRegistry records the SHA-256 of the exact schema file bytes.
        # The RuntimeBundle must pin the same bytes, including whitespace, so a
        # schema_hash can never drift while the bundle digest stays unchanged.
        add(role, logical_ref, relative, RAW_CANONICALIZATION)

    for path in sorted((ROOT / "kernel").rglob("*.py")):
        relative = path.relative_to(ROOT)
        if "tests" in relative.parts or "__pycache__" in relative.parts:
            continue
        if relative == Path("kernel/demo.py"):
            continue
        add("RUNTIME_CODE", f"python:{relative.as_posix()}", relative,
            RAW_CANONICALIZATION)
    add("RUNTIME_SCHEMA", "sql:kernel/schema.sql", Path("kernel/schema.sql"),
        RAW_CANONICALIZATION)

    for relative in (
        Path("tooling/regsr_snapshot/parse_regsr.py"),
        Path("tooling/gerk_roundtrip/gerk_roundtrip.py"),
    ):
        add("PARSER_CODE", f"python:{relative.as_posix()}", relative,
            RAW_CANONICALIZATION)
    add(
        "RUNTIME_CATALOG_CODE",
        "python:tooling/runtime_bundle_lock.py",
        Path("tooling/runtime_bundle_lock.py"),
        RAW_CANONICALIZATION,
    )

    for relative in (
        Path(".python-version"),
        Path("requirements-review-baseline.lock"),
        Path("requirements-review-pip.lock"),
        Path("conformance/review_baseline_config.json"),
    ):
        add(
            "RUNTIME_ENVIRONMENT",
            f"environment:{relative.as_posix()}",
            relative,
            JSON_CANONICALIZATION if relative.suffix == ".json"
            else RAW_CANONICALIZATION,
        )

    for filename in descriptor["profileInstanceFiles"]:
        snapshot_path = descriptor_path.parent / filename
        snapshot = _json(ROOT / snapshot_path)
        for ref in snapshot.get("sourceArtifactRefs", []):
            if isinstance(ref, str) and ref.startswith("artifact:"):
                name = ref.split(":", 1)[1]
                add("REFERENCE_SOURCE", ref,
                    descriptor_path.parent / "examples" / name,
                    RAW_CANONICALIZATION)

    identities = [(entry["role"], entry["logicalRef"]) for entry in entries]
    duplicate_identities = sorted({item for item in identities
                                   if identities.count(item) > 1})
    paths = [entry["path"] for entry in entries]
    duplicate_paths = sorted({item for item in paths if paths.count(item) > 1})
    if duplicate_identities:
        raise CatalogError(f"duplicate catalog identities: {duplicate_identities}")
    if duplicate_paths:
        raise CatalogError(f"duplicate catalog paths: {duplicate_paths}")

    entries.sort(key=lambda entry: (entry["role"], entry["logicalRef"]))
    return {"lockVersion": LOCK_VERSION, "components": entries}


def canonical_lock_bytes(document: dict) -> bytes:
    return (json.dumps(
        document, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def verify_lock_bytes(actual: bytes, expected_document: dict) -> None:
    """Reject missing, extra, duplicate, non-canonical, or stale lock entries."""
    try:
        document = json.loads(actual, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, ValueError) as exc:
        raise CatalogError(f"runtime bundle lock is malformed: {exc}") from exc
    if not isinstance(document, dict) or set(document) != {"lockVersion", "components"}:
        raise CatalogError("runtime bundle lock has unknown or missing top-level fields")
    if document.get("lockVersion") != LOCK_VERSION:
        raise CatalogError("runtime bundle lock version is unsupported")
    entries = document.get("components")
    if not isinstance(entries, list):
        raise CatalogError("runtime bundle lock components must be a list")
    try:
        identities = [(entry["role"], entry["logicalRef"]) for entry in entries]
        paths = [entry["path"] for entry in entries]
    except (KeyError, TypeError) as exc:
        raise CatalogError("runtime bundle lock component entry is malformed") from exc
    if len(identities) != len(set(identities)):
        raise CatalogError("runtime bundle lock has duplicate component identities")
    if len(paths) != len(set(paths)):
        raise CatalogError("runtime bundle lock has duplicate component paths")
    expected_entries = expected_document["components"]
    expected_identities = {
        (entry["role"], entry["logicalRef"]) for entry in expected_entries
    }
    actual_identities = set(identities)
    missing = sorted(expected_identities - actual_identities)
    extra = sorted(actual_identities - expected_identities)
    if missing or extra:
        raise CatalogError(
            f"runtime bundle lock catalog differs: missing={missing}, extra={extra}")
    expected_paths = {entry["path"] for entry in expected_entries}
    actual_paths = set(paths)
    if expected_paths != actual_paths:
        raise CatalogError(
            f"runtime bundle lock paths differ: "
            f"missing={sorted(expected_paths - actual_paths)}, "
            f"extra={sorted(actual_paths - expected_paths)}")
    if actual != canonical_lock_bytes(expected_document):
        raise CatalogError(
            "runtime bundle lock content digest/order/format is stale or non-canonical")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write", action="store_true",
        help="replace the lock after explicit review of runtime content changes",
    )
    args = parser.parse_args()
    expected_document = build_catalog()
    expected = canonical_lock_bytes(expected_document)
    if args.write:
        LOCK_PATH.write_bytes(expected)
        print(f"wrote {LOCK_PATH.relative_to(ROOT)}")
        return 0
    try:
        actual = LOCK_PATH.read_bytes()
    except OSError as exc:
        raise SystemExit(f"runtime bundle lock is absent: {exc}") from exc
    try:
        verify_lock_bytes(actual, expected_document)
    except CatalogError as exc:
        raise SystemExit(
            "runtime bundle lock is stale, incomplete, or non-canonical; "
            "review the catalog diff and run tooling/runtime_bundle_lock.py --write; "
            f"detail: {exc}") from exc
    print(f"verified {len(expected_document['components'])} runtime components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
