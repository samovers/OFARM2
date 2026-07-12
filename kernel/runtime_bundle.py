"""Immutable, content-addressed runtime selection (issue #171).

The RuntimeBundle is implementation metadata, not OFARM law or a promoted
machine contract.  It closes the gap between a descriptor ref and the bytes
that actually make a decision: profile content, executable validator/adapter
surfaces, query/output plans, and selected reference inputs.

Canonical JSON uses the same deterministic encoding as governed record
digests.  Executable source uses exact bytes.  Every identity is a full
SHA-256 and every digest reuse is followed by byte equality verification.
"""
from __future__ import annotations

import copy
import functools
import hashlib
import io
import importlib.machinery
import importlib.metadata
import json
import locale
import os
import platform
import re
import stat
import sys
import sysconfig
import time
import zipfile
from dataclasses import InitVar, dataclass, field, replace
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .contracts import canonical_json

BUNDLE_VERSION = "ofarm.runtime-bundle.local.v2"
LOCK_VERSION = "ofarm.runtime-bundle-component-lock.local.v2"
JSON_CANONICALIZATION = "OFARM_CANONICAL_JSON_V1"
RAW_CANONICALIZATION = "EXACT_BYTES_V1"
LOCK_FILENAME = "runtime_bundle.lock.json"
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

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_RUNTIME_COMPONENT_REF_RE = re.compile(r"^[A-Za-z0-9._:/#-]{1,1024}$")
_RUNTIME_COMPONENT_ROLES = {
    "ACTIVE_MANIFEST",
    "CONTRACT_MANIFEST",
    "CONTRACT_METADATA",
    "CONTRACT_SCHEMA",
    "PARSER_CODE",
    "PROFILE_DESCRIPTOR",
    "PROFILE_INSTANCE",
    "PROFILE_POLICY",
    "PROFILE_ROUTE_SELECTION",
    "QUERY_PLAN",
    "QUERY_SPECIFICATION",
    "REFERENCE_DATA",
    "REFERENCE_SNAPSHOT",
    "REFERENCE_SOURCE",
    "RUNTIME_CATALOG_CODE",
    "RUNTIME_CODE",
    "RUNTIME_DATABASE_OBSERVED",
    "RUNTIME_ENVIRONMENT",
    "RUNTIME_ENVIRONMENT_OBSERVED",
    "RUNTIME_SCHEMA",
    "TENANT_BINDING",
}
_LIVE_SELECTION_PROOF = object()
_OBSERVED_ENVIRONMENT_REF = "environment:observed-runtime.v3"
_OBSERVED_DATABASE_REF = "environment:observed-postgresql.v1"
_PROFILE_ROUTE_SELECTION_REF = "profile-route-selection:active"


@dataclass(frozen=True)
class RuntimeEnvironmentSeal:
    """Write-once process identity captured during atomic live activation."""

    bundle_digest: str
    flags: tuple[Any, ...]
    ambient: tuple[Any, ...]
    native_loader_environment: tuple[Any, ...]
    native_runtime: str
    native_runtime_stat: tuple[Any, ...]
    customization: tuple[str, ...]
    sys_path: tuple[Any, ...]
    sys_path_object: object
    meta_path: tuple[str, ...]
    path_hooks: tuple[str, ...]
    meta_path_container: object
    path_hooks_container: object
    meta_path_objects: tuple[object, ...]
    path_hook_objects: tuple[object, ...]
    path_importer_cache: tuple[str, ...]
    path_importer_cache_mapping: object
    path_importer_cache_objects: tuple[tuple[str, object, type, tuple[Any, ...]], ...]
    import_callable_state: tuple[tuple[Any, ...], ...]
    sys_modules_mapping: object
    modules: tuple[tuple[str, object, tuple[Any, ...]], ...]
    pycache_prefix: str | None
    project_root: str


class RuntimeBundleError(RuntimeError):
    """Bundle content is absent, mutable, inconsistent, or unverifiable."""


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _freeze_runtime_cache(value):
    """Recursively freeze lookup state retained for one runtime lifetime.

    Runtime lookup indexes are intentionally private, but private dictionaries
    are still writable by any in-process collaborator. Mapping proxies, tuples,
    and frozensets make both indexes and retained JSON records immutable after
    preload instead of relying on callers to leave them alone.
    """
    if isinstance(value, dict):
        return MappingProxyType({
            key: _freeze_runtime_cache(item) for key, item in value.items()
        })
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_runtime_cache(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_runtime_cache(item) for item in value)
    return value


def _copy_runtime_cache_value(value):
    """Return ordinary mutable containers without exposing frozen cache state."""
    if isinstance(value, Mapping):
        return {
            key: _copy_runtime_cache_value(item) for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_copy_runtime_cache_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return {_copy_runtime_cache_value(item) for item in value}
    return copy.deepcopy(value)


def require_store_runtime_bundle(store, bundle, consumer: str) -> None:
    """Prevent service evaluation under bytes different from Store receipts."""
    if bundle is None:
        raise RuntimeBundleError(
            f"{consumer} requires an explicit verified RuntimeBundle")
    try:
        bound = store.runtime_bundle
    except Exception as exc:
        raise RuntimeBundleError(
            f"{consumer} requires a Store bound to a verified RuntimeBundle") from exc
    if (bound.digest != bundle.digest
            or bundle.construction_mode != "LIVE_CURRENT"
            or bound.descriptor != bundle.descriptor
            or bound.canonical_document_bytes != bundle.canonical_document_bytes
            or bound.components != bundle.components
            or bound.selected_references != bundle.selected_references):
        raise RuntimeBundleError(
            f"{consumer} RuntimeBundle does not exactly match the Store bundle")
    seal = getattr(store, "_runtime_environment_seal", None)
    if not isinstance(seal, RuntimeEnvironmentSeal):
        raise RuntimeBundleError(
            f"{consumer} requires the Store's write-once runtime environment seal")
    require_runtime_environment_seal(bundle, seal, consumer)


def require_current_runtime_catalog(bundle, package_root: Path) -> None:
    """Prove all current code-owned bytes are present exactly before live bind."""
    try:
        from tooling.runtime_bundle_lock import ROOT as CATALOG_ROOT, build_catalog
    except ImportError as exc:
        raise RuntimeBundleError(
            f"runtime catalog verifier is unavailable: {exc}") from exc
    if Path(CATALOG_ROOT).resolve() != Path(package_root).resolve():
        raise RuntimeBundleError("runtime catalog verifier is rooted at another package")
    expected = {
        (entry["role"], entry["logicalRef"]): entry
        for entry in build_catalog()["components"]
    }
    actual = {(component.role, component.logical_ref): component
              for component in bundle.components}
    missing = sorted(set(expected) - set(actual))
    if missing:
        raise RuntimeBundleError(
            f"live RuntimeBundle omits current catalog components: {missing}")
    for key, entry in expected.items():
        component = actual[key]
        if (component.repository_path != entry["path"]
                or component.canonicalization != entry["canonicalization"]
                or component.placement != entry["placement"]
                or component.content_digest != entry["sha256"]):
            raise RuntimeBundleError(
                f"live RuntimeBundle component differs from current catalog: {key!r}")
    observed_key = ("RUNTIME_ENVIRONMENT_OBSERVED", _OBSERVED_ENVIRONMENT_REF)
    database_key = ("RUNTIME_DATABASE_OBSERVED", _OBSERVED_DATABASE_REF)
    current_observed = observed_runtime_environment_component(
        package_root, bundle.components)
    selected_observed = actual.get(observed_key)
    if (selected_observed is None
            or selected_observed.repository_path != "runtime-observed/environment-v3"
            or selected_observed.canonicalization != JSON_CANONICALIZATION
            or selected_observed.placement != GLOBAL_CONTENT_PLACEMENT):
        raise RuntimeBundleError(
            "live RuntimeBundle environment observation provenance is invalid")
    current_environment = _strict_json_value(
        current_observed.canonical_bytes, "current runtime environment observation")
    selected_environment = _strict_json_value(
        selected_observed.canonical_bytes, "selected runtime environment observation")
    _validate_runtime_environment_document(current_environment)
    _validate_runtime_environment_document(selected_environment)
    if current_environment != selected_environment:
        raise RuntimeBundleError(
            "live RuntimeBundle does not match the currently observed runtime environment")
    if bundle.construction_mode == "LIVE_CURRENT" and database_key not in actual:
        raise RuntimeBundleError(
            "live RuntimeBundle omits its PostgreSQL environment observation")
    for key in sorted(set(actual) - set(expected)):
        component = actual[key]
        if key == observed_key:
            continue
        if key == database_key:
            if (component.repository_path != "runtime-observed/postgresql-v1"
                    or component.canonicalization != JSON_CANONICALIZATION
                    or component.placement != GLOBAL_CONTENT_PLACEMENT):
                raise RuntimeBundleError(
                    "live RuntimeBundle PostgreSQL observation provenance is invalid")
            _validate_database_environment_document(
                _strict_json_value(
                    component.canonical_bytes,
                    "RuntimeBundle PostgreSQL environment observation"))
            continue
        if (component.placement != TENANT_CONTENT_PLACEMENT
                or component.canonicalization != JSON_CANONICALIZATION):
            raise RuntimeBundleError(
                f"live RuntimeBundle has an ungoverned extra component: {key!r}")
        if component.role == "PROFILE_INSTANCE":
            expected_path = f"database/profile-instance/{component.logical_ref}"
            payload = _strict_json_value(
                component.canonical_bytes,
                f"dynamic profile component {component.logical_ref!r}")
            if payload.get("schemaVersion") not in (
                    _TENANT_PROFILE_INSTANCE_KINDS | _GLOBAL_PROFILE_INSTANCE_KINDS):
                raise RuntimeBundleError(
                    f"dynamic profile component has unsupported kind: {key!r}")
        elif component.role == "PROFILE_ROUTE_SELECTION":
            expected_path = "runtime-selected/profile-route-selection"
            payload = _strict_json_value(
                component.canonical_bytes, "dynamic profile route selection")
            if payload.get("schemaVersion") != \
                    "ofarm.profile-route-selection.local.v1":
                raise RuntimeBundleError(
                    "dynamic profile route selection has an unsupported version")
        elif component.role == "REFERENCE_SNAPSHOT":
            expected_path = f"database/reference-snapshot/{component.logical_ref}"
            payload = _strict_json_value(
                component.canonical_bytes,
                f"dynamic reference component {component.logical_ref!r}")
            if payload.get("schemaVersion") != "ofarm.referencesnapshot.v0.1":
                raise RuntimeBundleError(
                    f"dynamic reference component has unsupported kind: {key!r}")
        elif component.role == "REFERENCE_DATA" and "#" in component.logical_ref:
            snapshot_ref, data_family = component.logical_ref.rsplit("#", 1)
            expected_path = f"database/reference-data/{snapshot_ref}/{data_family}"
        else:
            raise RuntimeBundleError(
                f"live RuntimeBundle has an ungoverned extra role: {key!r}")
        if component.repository_path != expected_path:
            raise RuntimeBundleError(
                f"live RuntimeBundle extra component provenance is invalid: {key!r}")


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeBundleError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str):
    raise RuntimeBundleError(f"non-finite JSON number {value!r} is forbidden")


def _strict_json_value(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8", errors="strict")
    except (AttributeError, UnicodeDecodeError) as exc:
        raise RuntimeBundleError(f"{label} is not strict UTF-8 JSON") from exc
    if text.startswith("\ufeff"):
        raise RuntimeBundleError(f"{label} must not contain a UTF-8 BOM")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
        )
        # Apply the shared non-finite/surrogate/type policy even when the
        # original spelling would otherwise parse on this interpreter.
        canonical_json(value)
    except RuntimeBundleError:
        raise
    except (UnicodeError, ValueError, TypeError) as exc:
        raise RuntimeBundleError(f"{label} is malformed JSON: {exc}") from exc
    return value


def strict_json_bytes(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise RuntimeBundleError(f"runtime component is unreadable at {path}: {exc}") from exc
    value = _strict_json_value(raw, f"runtime component at {path}")
    if not isinstance(value, dict):
        raise RuntimeBundleError(f"runtime JSON component must be an object: {path}")
    return canonical_json(value).encode("utf-8"), value


def _component_bytes(path: Path, canonicalization: str) -> bytes:
    if canonicalization == JSON_CANONICALIZATION:
        return strict_json_bytes(path)[0]
    if canonicalization == RAW_CANONICALIZATION:
        try:
            return path.read_bytes()
        except OSError as exc:
            raise RuntimeBundleError(f"runtime component is unreadable at {path}: {exc}") from exc
    raise RuntimeBundleError(f"unknown component canonicalization {canonicalization!r}")


def component_placement(
    role: str,
    canonicalization: str,
    canonical_bytes: bytes,
    repository_path: str = "",
) -> str:
    """Classify exact component bytes before they enter a storage carrier.

    The global carrier is reserved for tenant-neutral immutable content. Tenant
    activation/context fixtures and imported reference-data bytes remain in the
    tenant carrier even though the RuntimeBundle digest covers them together
    with the global execution content.
    """
    if (repository_path.startswith("database/")
            and role in {"PROFILE_INSTANCE", "REFERENCE_SNAPSHOT", "REFERENCE_DATA"}):
        return TENANT_CONTENT_PLACEMENT
    if role in {
            "PROFILE_DESCRIPTOR", "PROFILE_ROUTE_SELECTION", "QUERY_PLAN",
            "REFERENCE_DATA", "TENANT_BINDING"}:
        return TENANT_CONTENT_PLACEMENT
    if role not in {"PROFILE_INSTANCE", "ACTIVE_MANIFEST"}:
        return GLOBAL_CONTENT_PLACEMENT
    if canonicalization != JSON_CANONICALIZATION:
        raise RuntimeBundleError(
            f"placement-bearing component {role!r} must be canonical JSON")
    try:
        payload = _strict_json_value(canonical_bytes, f"placement-bearing {role}")
    except RuntimeBundleError as exc:
        raise RuntimeBundleError(
            f"placement-bearing component {role!r} is malformed") from exc
    if not isinstance(payload, dict):
        raise RuntimeBundleError(
            f"placement-bearing component {role!r} must be a JSON object")
    kind = payload.get("schemaVersion")
    if role == "ACTIVE_MANIFEST":
        if (kind != "ofarm.capabilitymanifest.v0.1"
                or (payload.get("deploymentScope") or {}).get("scopeType") != "TENANT"):
            raise RuntimeBundleError(
                "the active capability manifest must remain explicit tenant state")
        return TENANT_CONTENT_PLACEMENT
    if kind in _TENANT_PROFILE_INSTANCE_KINDS:
        return TENANT_CONTENT_PLACEMENT
    if kind in _GLOBAL_PROFILE_INSTANCE_KINDS:
        return GLOBAL_CONTENT_PLACEMENT
    raise RuntimeBundleError(
        f"profile instance kind {kind!r} has no reviewed RuntimeBundle placement")


def _validate_tenant_component_owner(
    component: "RuntimeComponent",
    tenant_ref: str,
) -> None:
    if component.placement != TENANT_CONTENT_PLACEMENT \
            or component.canonicalization != JSON_CANONICALIZATION:
        return
    payload = _strict_json_value(
        component.canonical_bytes, f"tenant component {component.logical_ref!r}")
    kind = payload.get("schemaVersion")
    if kind == "ofarm.runtime-tenant-binding.local.v1":
        if payload.get("tenantRef") != tenant_ref:
            raise RuntimeBundleError(
                f"tenant RuntimeBundle component {component.logical_ref!r} is not "
                f"owned exactly by {tenant_ref!r}")
        return
    if kind == "ofarm.profile-route-selection.local.v1":
        if payload.get("tenantRef") != tenant_ref:
            raise RuntimeBundleError(
                f"tenant RuntimeBundle component {component.logical_ref!r} is not "
                f"owned exactly by {tenant_ref!r}")
        return
    if kind == "ofarm.activeartifactset.v0.1":
        scopes = [payload.get("deploymentScope")]
    elif kind == "ofarm.packactivationset.v0.1":
        scopes = [payload.get("targetScope")]
    elif kind == "ofarm.contextsnapshot.v0.1":
        scopes = payload.get("anchorScopes", [])
    elif kind == "ofarm.capabilitymanifest.v0.1":
        scopes = [payload.get("deploymentScope")]
    else:
        return
    tenant_scopes = [scope for scope in scopes if isinstance(scope, dict)
                     and scope.get("scopeType") == "TENANT"]
    expected = {"scopeType": "TENANT", "scopeRef": tenant_ref}
    if tenant_scopes != [expected]:
        raise RuntimeBundleError(
            f"tenant RuntimeBundle component {component.logical_ref!r} is not "
            f"owned exactly by {tenant_ref!r}")


@dataclass(frozen=True)
class RuntimeComponent:
    role: str
    logical_ref: str
    repository_path: str
    canonicalization: str
    content_digest: str
    canonical_bytes: bytes
    placement: str = GLOBAL_CONTENT_PLACEMENT

    def __post_init__(self) -> None:
        if not self.role or not self.logical_ref or not self.repository_path:
            raise RuntimeBundleError("runtime component role/ref/path must be non-empty")
        if self.role not in _RUNTIME_COMPONENT_ROLES:
            raise RuntimeBundleError(
                f"runtime component role {self.role!r} is outside the closed vocabulary")
        if not _RUNTIME_COMPONENT_REF_RE.fullmatch(self.logical_ref):
            raise RuntimeBundleError(
                f"runtime component logical ref {self.logical_ref!r} is not "
                "RUNTIME_COMPONENT_REF_V1")
        if (not _RUNTIME_COMPONENT_REF_RE.fullmatch(self.repository_path)
                or self.repository_path.startswith("/")
                or "\\" in self.repository_path
                or any(part in {"", ".", ".."}
                       for part in self.repository_path.split("/"))):
            raise RuntimeBundleError(
                f"runtime component provenance {self.repository_path!r} is not a "
                "bounded relative RUNTIME_COMPONENT_REF_V1 path")
        if self.canonicalization not in {
                JSON_CANONICALIZATION, RAW_CANONICALIZATION}:
            raise RuntimeBundleError(
                f"runtime component {self.logical_ref!r} has unknown canonicalization")
        if self.canonicalization == JSON_CANONICALIZATION:
            try:
                value = _strict_json_value(
                    self.canonical_bytes,
                    f"runtime JSON component {self.logical_ref!r}")
            except RuntimeBundleError as exc:
                raise RuntimeBundleError(
                    f"runtime JSON component {self.logical_ref!r} is malformed") from exc
            if not isinstance(value, dict) \
                    or canonical_json(value).encode("utf-8") != self.canonical_bytes:
                raise RuntimeBundleError(
                    f"runtime JSON component {self.logical_ref!r} is not a canonical object")
        if not _SHA256_RE.fullmatch(self.content_digest):
            raise RuntimeBundleError(
                f"runtime component {self.logical_ref!r} lacks a full SHA-256")
        actual = sha256_bytes(self.canonical_bytes)
        if actual != self.content_digest:
            raise RuntimeBundleError(
                f"runtime component {self.logical_ref!r} digest mismatch: "
                f"declared {self.content_digest}, actual {actual}")
        expected_placement = component_placement(
            self.role, self.canonicalization, self.canonical_bytes,
            self.repository_path)
        if self.placement != expected_placement:
            raise RuntimeBundleError(
                f"runtime component {self.logical_ref!r} placement is "
                f"{self.placement!r}, expected {expected_placement!r}")

    def identity_document(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "logicalRef": self.logical_ref,
            "repositoryPath": self.repository_path,
            "canonicalization": self.canonicalization,
            "contentDigest": self.content_digest,
            "byteLength": len(self.canonical_bytes),
            "placement": self.placement,
        }


_AMBIENT_IMPORT_ENVIRONMENT = (
    "PYTHONCASEOK",
    "PYTHONEXECUTABLE",
    "PYTHONHASHSEED",
    "PYTHONHOME",
    "PYTHONINSPECT",
    "PYTHONMALLOC",
    "PYTHONPATH",
    "PYTHONPLATLIBDIR",
    "PYTHONPYCACHEPREFIX",
    "PYTHONSAFEPATH",
    "PYTHONSTARTUP",
    "PYTHONWARNINGS",
)
_NATIVE_LOADER_ENVIRONMENT_PREFIXES = ("LD_", "DYLD_")
_NATIVE_LOADER_ENVIRONMENT_EXACT = frozenset({"GLIBC_TUNABLES", "GCONV_PATH"})
_IMPORT_PROVIDER_METHODS = frozenset({
    "find_spec", "find_module", "create_module", "exec_module",
    "invalidate_caches", "path_hook", "_fill_cache", "get_code",
    "get_data", "path_stats", "set_data",
})
_PROJECT_TEST_PATHS = (
    "conformance/ofarm_profile_runtime_readiness_check.py",
    "conformance/review_baseline_pytest.py",
    "conformance/run_review_baseline.py",
    "kernel/demo.py",
    "kernel/tests/",
    "profile_si_ffs/test_fixtures/",
    "profile_si_ffs/tests/",
)
_PROJECT_TEST_NAMESPACE_PATHS = {"conformance", "profile_si_ffs"}
_REVIEWED_ORIGINLESS_AUXILIARY_MODULES = {
    # These module objects are created by an already pinned parent; they are
    # not independently resolved by Python's import machinery.
    "pyexpat.errors": "pyexpat",
    "pyexpat.model": "pyexpat",
    "typing.io": "typing",
    "typing.re": "typing",
    "cython_runtime": "psycopg_binary._psycopg",
    "_cython_3_2_4": "psycopg_binary._psycopg",
}


def _resolved_path(value: str | os.PathLike[str]) -> Path:
    return Path(value).expanduser().resolve(strict=False)


@functools.lru_cache(maxsize=65536)
def _sha256_for_unchanged_stat(
    path: str,
    device: int,
    inode: int,
    size: int,
    modified_ns: int,
    changed_ns: int,
) -> str:
    # All stat fields are intentional cache-key inputs. A byte replacement or
    # in-place rewrite changes at least ctime on the supported live platform;
    # unchanged files avoid repeated multi-megabyte scans during startup tests.
    del device, inode, size, modified_ns, changed_ns
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _file_content_identity(path: Path) -> tuple[str, int]:
    path = _resolved_path(path)
    stat = path.stat()
    if not path.is_file():
        raise RuntimeBundleError(f"runtime identity path is not a file: {path}")
    return _sha256_for_unchanged_stat(
        str(path), stat.st_dev, stat.st_ino, stat.st_size,
        stat.st_mtime_ns, stat.st_ctime_ns), stat.st_size


def _validate_runtime_image_file_entry(
    entry: Any,
    *,
    relative: bool = False,
) -> None:
    keys = {"path", "contentDigest", "byteLength"}
    if relative:
        keys.add("relativePath")
    if (not isinstance(entry, dict) or set(entry) != keys
            or not isinstance(entry.get("path"), str)
            or not Path(entry["path"]).is_absolute()
            or not _SHA256_RE.fullmatch(entry.get("contentDigest", ""))
            or not isinstance(entry.get("byteLength"), int)
            or entry["byteLength"] < 0):
        raise RuntimeBundleError("retained Python image file entry is malformed")
    if relative:
        value = entry.get("relativePath")
        path = PurePosixPath(value) if isinstance(value, str) else None
        if (path is None or not value or path.is_absolute()
                or any(part in {"", ".", ".."} for part in path.parts)):
            raise RuntimeBundleError(
                "retained Python standard-library relative path is malformed")


def _validate_runtime_image_manifest(document: Any) -> None:
    if (not isinstance(document, dict)
            or set(document) != {"schemaVersion", "image", "python"}
            or document.get("schemaVersion") !=
            "ofarm.python-runtime-image-manifest.local.v1"):
        raise RuntimeBundleError("retained Python runtime image manifest is malformed")
    image = document.get("image")
    if (not isinstance(image, dict)
            or set(image) != {
                "reference", "indexDigest", "platform",
                "platformManifestDigest", "configDigest", "layers",
            }
            or image.get("platform") != "linux/amd64"
            or not isinstance(image.get("reference"), str)
            or not image["reference"]
            or any(not _SHA256_RE.fullmatch(image.get(key, ""))
                   for key in (
                       "indexDigest", "platformManifestDigest", "configDigest"))
            or not isinstance(image.get("layers"), list)
            or not image["layers"]):
        raise RuntimeBundleError("retained Python runtime image identity is malformed")
    for layer in image["layers"]:
        if (not isinstance(layer, dict)
                or set(layer) != {"digest", "byteLength"}
                or not _SHA256_RE.fullmatch(layer.get("digest", ""))
                or not isinstance(layer.get("byteLength"), int)
                or layer["byteLength"] <= 0):
            raise RuntimeBundleError("retained Python runtime image layer is malformed")
    python = document.get("python")
    if (not isinstance(python, dict)
            or set(python) != {
                "version", "executable", "sharedLibrary",
                "standardLibraryRoots", "nativeFiles",
                "loaderConfigurationFiles", "requiredAbsentPaths",
                "requiredExecutables",
            }
            or not isinstance(python.get("version"), str)
            or not isinstance(python.get("standardLibraryRoots"), list)
            or not python["standardLibraryRoots"]):
        raise RuntimeBundleError("retained Python runtime file inventory is malformed")
    _validate_runtime_image_file_entry(python["executable"])
    _validate_runtime_image_file_entry(python["sharedLibrary"])
    for field_name in (
            "nativeFiles", "loaderConfigurationFiles", "requiredExecutables"):
        entries = python.get(field_name)
        if not isinstance(entries, list) or not entries:
            raise RuntimeBundleError(
                f"retained Python runtime {field_name} inventory is malformed")
        for entry in entries:
            _validate_runtime_image_file_entry(entry)
        paths = [entry["path"] for entry in entries]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise RuntimeBundleError(
                f"retained Python runtime {field_name} inventory is not canonical")
    absent = python.get("requiredAbsentPaths")
    if (not isinstance(absent, list) or absent != sorted(set(absent))
            or any(not isinstance(path, str) or not Path(path).is_absolute()
                   for path in absent)):
        raise RuntimeBundleError(
            "retained Python runtime required-absence inventory is malformed")
    root_paths = []
    for root in python["standardLibraryRoots"]:
        if (not isinstance(root, dict)
                or set(root) != {"path", "directories", "files"}
                or not isinstance(root.get("path"), str)
                or not Path(root["path"]).is_absolute()
                or not isinstance(root.get("directories"), list)
                or root["directories"] != sorted(set(root["directories"]))
                or any(not isinstance(path, str) or not path
                       for path in root["directories"])
                or not isinstance(root.get("files"), list)
                or not root["files"]):
            raise RuntimeBundleError(
                "retained Python standard-library root is malformed")
        file_paths = []
        for entry in root["files"]:
            _validate_runtime_image_file_entry(entry, relative=True)
            expected_path = Path(root["path"]) / entry["relativePath"]
            if str(expected_path) != entry["path"]:
                raise RuntimeBundleError(
                    "retained Python standard-library path is inconsistent")
            file_paths.append(entry["relativePath"])
        if file_paths != sorted(file_paths) or len(file_paths) != len(set(file_paths)):
            raise RuntimeBundleError(
                "retained Python standard-library file inventory is not canonical")
        root_paths.append(root["path"])
    if root_paths != sorted(set(root_paths)):
        raise RuntimeBundleError(
            "retained Python standard-library roots are not canonical")


def _runtime_image_manifest(
    retained_components: Iterable["RuntimeComponent"],
) -> dict[str, Any]:
    matches = [
        component for component in retained_components
        if component.role == "RUNTIME_ENVIRONMENT"
        and component.logical_ref ==
        "environment:conformance/python_runtime_image_manifest.json"
    ]
    if len(matches) != 1:
        raise RuntimeBundleError(
            "RuntimeBundle must retain exactly one Python image manifest")
    document = _strict_json_value(
        matches[0].canonical_bytes, "retained Python image manifest")
    _validate_runtime_image_manifest(document)
    return document


def _retained_runtime_image_maps(
    manifest: Mapping[str, Any],
) -> tuple[dict[str, tuple[str, int]], dict[str, tuple[str, int]]]:
    standard: dict[str, tuple[str, int]] = {}
    native: dict[str, tuple[str, int]] = {}

    def add(target, entry):
        identity = (entry["contentDigest"], entry["byteLength"])
        prior = target.get(entry["path"])
        if prior is not None and prior != identity:
            raise RuntimeBundleError(
                f"retained Python image disagrees about {entry['path']!r}")
        target[entry["path"]] = identity

    python = manifest["python"]
    for root in python["standardLibraryRoots"]:
        for entry in root["files"]:
            add(standard, entry)
            if entry["path"].endswith(tuple(importlib.machinery.EXTENSION_SUFFIXES)):
                add(native, entry)
    for entry in (
            python["executable"], python["sharedLibrary"],
            *python["nativeFiles"], *python["requiredExecutables"]):
        add(native, entry)
    return standard, native


def _runtime_locked_requirements(package_root: Path) -> dict[str, dict[str, Any]]:
    requirements: dict[str, dict[str, Any]] = {}
    pattern = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)")
    for filename in ("requirements-review-baseline.lock", "requirements-review-pip.lock"):
        pending = ""
        for physical in (package_root / filename).read_text(encoding="utf-8").splitlines():
            stripped = physical.strip()
            if not pending and (not stripped or stripped.startswith("#")):
                continue
            continued = stripped.endswith("\\")
            pending += stripped[:-1].strip() + " " if continued else stripped
            if continued:
                continue
            match = pattern.match(pending)
            hashes = tuple(sorted(set(re.findall(
                r"(?:^|\s)--hash=sha256:([0-9a-f]{64})(?=\s|$)", pending))))
            if match is None or not hashes:
                raise RuntimeBundleError(
                    f"retained requirement is not an exact hashed wheel: {pending!r}")
            raw_name, version = match.groups()
            name = re.sub(r"[-_.]+", "-", raw_name).lower()
            if name in requirements:
                raise RuntimeBundleError(f"duplicate locked distribution {name!r}")
            requirements[name] = {"version": version, "hashes": hashes}
            pending = ""
        if pending:
            raise RuntimeBundleError(f"unterminated retained requirement in {filename}")
    return requirements


def _runtime_wheel_destination(member: str, data_prefix: str) -> PurePosixPath | None:
    path = PurePosixPath(member)
    if (not member or member.startswith(("/", "\\")) or "\\" in member
            or any(part in {"", ".", ".."} for part in path.parts)):
        raise RuntimeBundleError(f"locked wheel contains unsafe path {member!r}")
    if path.parts[0] != data_prefix:
        return path
    if len(path.parts) < 3 or path.parts[1] not in {"purelib", "platlib"}:
        return None
    return PurePosixPath(*path.parts[2:])


@functools.lru_cache(maxsize=1)
def _cached_locked_wheel_inventory() -> dict[str, dict[str, Any]]:
    package_root = Path(__file__).resolve().parents[1]
    requirements = _runtime_locked_requirements(package_root)
    venv_root = Path(sys.executable).absolute().parent.parent
    wheelhouse = venv_root / ".ofarm-wheelhouse"
    if not wheelhouse.is_dir() or wheelhouse.is_symlink():
        raise RuntimeBundleError("retained RuntimeBundle wheelhouse is unavailable")
    inventory: dict[str, dict[str, Any]] = {}
    archives = sorted(wheelhouse.iterdir(), key=lambda path: path.name)
    if not archives or any(path.is_symlink() or not path.is_file()
                           or path.suffix != ".whl" for path in archives):
        raise RuntimeBundleError("retained RuntimeBundle wheelhouse is not closed")
    for archive in archives:
        archive_bytes = archive.read_bytes()
        archive_digest = hashlib.sha256(archive_bytes).hexdigest()
        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as wheel:
                members = [item for item in wheel.infolist() if not item.is_dir()]
                metadata_names = [
                    item.filename for item in members
                    if item.filename.count("/") == 1
                    and item.filename.endswith(".dist-info/METADATA")
                ]
                if len(metadata_names) != 1:
                    raise RuntimeBundleError(
                        f"locked wheel has ambiguous METADATA: {archive.name}")
                dist_info = metadata_names[0].split("/", 1)[0]
                data_prefix = dist_info.removesuffix(".dist-info") + ".data"
                metadata = wheel.read(metadata_names[0]).decode("utf-8", errors="strict")
                name_match = re.search(r"(?m)^Name:\s*([^\r\n]+)\s*$", metadata)
                version_match = re.search(r"(?m)^Version:\s*([^\r\n]+)\s*$", metadata)
                if name_match is None or version_match is None:
                    raise RuntimeBundleError(
                        f"locked wheel METADATA has no name/version: {archive.name}")
                name = re.sub(
                    r"[-_.]+", "-", name_match.group(1).strip()).lower()
                version = version_match.group(1).strip()
                requirement = requirements.get(name)
                if (requirement is None or version != requirement["version"]
                        or archive_digest not in requirement["hashes"]):
                    raise RuntimeBundleError(
                        f"wheel archive differs from retained lock: {name}=={version}")
                files: dict[str, tuple[str, int]] = {}
                for item in members:
                    destination = _runtime_wheel_destination(
                        item.filename, data_prefix)
                    if destination is None \
                            or destination == PurePosixPath(dist_info, "RECORD"):
                        continue
                    relative = destination.as_posix()
                    exact = wheel.read(item)
                    identity = (sha256_bytes(exact), len(exact))
                    if relative in files:
                        raise RuntimeBundleError(
                            f"locked wheel maps duplicate installed path {relative!r}")
                    files[relative] = identity
        except (OSError, UnicodeDecodeError, zipfile.BadZipFile, KeyError) as exc:
            raise RuntimeBundleError(f"locked wheel cannot be read: {archive}") from exc
        if name in inventory:
            raise RuntimeBundleError(f"multiple locked wheels normalize to {name!r}")
        inventory[name] = {
            "version": version,
            "wheelArchiveDigest": "sha256:" + archive_digest,
            "wheelArchiveByteLength": len(archive_bytes),
            "files": files,
        }
    if set(inventory) != set(requirements):
        raise RuntimeBundleError("locked wheelhouse distribution set is not exact")
    return inventory


@functools.lru_cache(maxsize=1)
def _cached_distribution_observation():
    wheel_inventory = _cached_locked_wheel_inventory()
    distributions = []
    file_owners: dict[str, list[str]] = {}
    dependency_roots: set[str] = set()
    for distribution in importlib.metadata.distributions():
        raw_name = distribution.metadata.get("Name")
        if not raw_name:
            raise RuntimeBundleError("an installed distribution has no canonical name")
        name = re.sub(r"[-_.]+", "-", raw_name).lower()
        retained = wheel_inventory.get(name)
        if retained is None or distribution.version != retained["version"]:
            raise RuntimeBundleError(
                f"installed distribution does not equal a locked wheel: {name!r}")
        root_path = _resolved_path(distribution.locate_file(""))
        root = str(root_path)
        dependency_roots.add(root)
        files = []
        for relative, expected_identity in sorted(retained["files"].items()):
            path = _resolved_path(root_path.joinpath(*PurePosixPath(relative).parts))
            if not path.is_file():
                raise RuntimeBundleError(
                    f"locked wheel file is missing from environment: {name}/{relative}")
            content_digest, byte_length = _file_content_identity(path)
            if (content_digest, byte_length) != expected_identity:
                raise RuntimeBundleError(
                    f"installed bytes differ from locked wheel: {name}/{relative}")
            resolved = str(path)
            file_owners.setdefault(resolved, []).append(name)
            files.append({
                "path": relative,
                "resolvedPath": resolved,
                "contentDigest": content_digest,
                "byteLength": byte_length,
            })
        distributions.append({
            "name": name,
            "version": distribution.version,
            "wheelArchiveDigest": retained["wheelArchiveDigest"],
            "wheelArchiveByteLength": retained["wheelArchiveByteLength"],
            "root": root,
            "files": files,
        })
    distributions.sort(key=lambda item: item["name"])
    names = [item["name"] for item in distributions]
    if len(names) != len(set(names)) or set(names) != set(wheel_inventory):
        raise RuntimeBundleError(
            "installed distribution set does not equal locked wheelhouse")
    for owners in file_owners.values():
        owners.sort()
    return distributions, file_owners, sorted(dependency_roots)


def _distribution_observation():
    distributions, file_owners, dependency_roots = \
        _cached_distribution_observation()
    return (copy.deepcopy(distributions), copy.deepcopy(file_owners),
            list(dependency_roots))


@functools.lru_cache(maxsize=1)
def _cached_standard_runtime_observation():
    raw_roots = {
        str(_resolved_path(value)) for value in (
            sysconfig.get_path("stdlib"), sysconfig.get_path("platstdlib"))
        if value and "site-packages" not in Path(value).parts
    }
    roots = []
    file_map: dict[str, dict[str, Any]] = {}
    for raw_root in sorted(raw_roots):
        root = Path(raw_root)
        if not root.is_dir():
            continue
        files = []
        retained_directories = []
        for directory, directories, filenames in os.walk(root):
            base = Path(directory)
            relative_base = base.relative_to(root)
            kept = []
            for name in sorted(directories):
                if name in {"__pycache__", "site-packages", "dist-packages"}:
                    continue
                unresolved = base / name
                if unresolved.is_symlink() or not unresolved.is_dir():
                    continue
                kept.append(name)
                retained_directories.append(
                    (relative_base / name).as_posix())
            directories[:] = kept
            for filename in sorted(filenames):
                unresolved = base / filename
                if unresolved.is_symlink():
                    continue
                path = _resolved_path(unresolved)
                if not path.is_file():
                    continue
                try:
                    relative = path.relative_to(root).as_posix()
                except ValueError as exc:
                    raise RuntimeBundleError(
                        f"standard-library file escapes its runtime root: {path}") from exc
                content_digest, byte_length = _file_content_identity(path)
                entry = {
                    "path": relative,
                    "resolvedPath": str(path),
                    "contentDigest": content_digest,
                    "byteLength": byte_length,
                }
                files.append(entry)
                file_map[str(path)] = entry
        files.sort(key=lambda item: item["path"])
        roots.append({
            "path": str(root),
            "directories": sorted(retained_directories),
            "files": files,
        })

    archives = []
    for raw in sys.path:
        path = _resolved_path(raw) if isinstance(raw, str) and raw else None
        if path is None or path.suffix != ".zip" or not path.is_file():
            continue
        content_digest, byte_length = _file_content_identity(path)
        entry = {
            "resolvedPath": str(path),
            "contentDigest": content_digest,
            "byteLength": byte_length,
        }
        archives.append(entry)
        file_map[str(path)] = entry

    shared_library = None
    library_directory = sysconfig.get_config_var("LIBDIR")
    library_name = sysconfig.get_config_var("LDLIBRARY")
    if library_directory and library_name:
        candidate = _resolved_path(Path(library_directory) / library_name)
        if candidate.is_file():
            content_digest, byte_length = _file_content_identity(candidate)
            shared_library = {
                "resolvedPath": str(candidate),
                "contentDigest": content_digest,
                "byteLength": byte_length,
            }
    return {
        "roots": roots,
        "archives": sorted(archives, key=lambda item: item["resolvedPath"]),
        "sharedLibrary": shared_library,
    }, file_map


def _standard_runtime_observation():
    standard_runtime, file_map = _cached_standard_runtime_observation()
    return copy.deepcopy(standard_runtime), copy.deepcopy(file_map)


def _native_loader_environment_observation() -> dict[str, str]:
    return {
        name: os.environ[name] for name in sorted(os.environ)
        if name in _NATIVE_LOADER_ENVIRONMENT_EXACT
        or name.startswith(_NATIVE_LOADER_ENVIRONMENT_PREFIXES)
    }


def _decode_proc_maps_path(value: str) -> str:
    def replace(match):
        character = chr(int(match.group(1), 8))
        if character == "\x00":
            raise RuntimeBundleError("executable mapping path contains NUL")
        return character

    return re.sub(r"\\([0-7]{3})", replace, value)


def _parse_executable_mappings(
    raw: str,
) -> tuple[list[tuple[str, int, int, int]], list[str]]:
    files: dict[str, tuple[int, int, int]] = {}
    kernel: set[str] = set()
    for line in raw.splitlines():
        fields = line.split(None, 5)
        if len(fields) < 5 or len(fields[1]) != 4:
            raise RuntimeBundleError("/proc/self/maps contains a malformed record")
        if "x" not in fields[1]:
            continue
        if len(fields) != 6:
            raise RuntimeBundleError("anonymous executable mapping is forbidden")
        pathname = _decode_proc_maps_path(fields[5])
        if pathname in {"[vdso]", "[vsyscall]"}:
            kernel.add(pathname)
            continue
        if (pathname.endswith(" (deleted)") or pathname.startswith(("[", "memfd:"))
                or not pathname.startswith("/")):
            raise RuntimeBundleError(
                f"unattributable executable mapping is forbidden: {pathname!r}")
        try:
            major_raw, minor_raw = fields[3].split(":", 1)
            identity = (int(major_raw, 16), int(minor_raw, 16), int(fields[4]))
        except (ValueError, TypeError) as exc:
            raise RuntimeBundleError(
                "executable mapping has malformed device/inode identity") from exc
        if identity[2] <= 0:
            raise RuntimeBundleError("executable file mapping has no inode identity")
        prior = files.get(pathname)
        if prior is not None and prior != identity:
            raise RuntimeBundleError(
                f"executable mapping path changed identity: {pathname!r}")
        files[pathname] = identity
    return (
        [(path, *files[path]) for path in sorted(files)],
        sorted(kernel),
    )


def _read_executable_mappings() -> tuple[list[tuple[str, int, int, int]], list[str]]:
    try:
        raw = Path("/proc/self/maps").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeBundleError("Linux executable mappings are unavailable") from exc
    return _parse_executable_mappings(raw)


def _path_is_read_only(path: Path) -> bool:
    try:
        return bool(os.statvfs(path).f_flag & os.ST_RDONLY)
    except OSError:
        return False


def _open_mapped_file(
    path: Path,
    major: int,
    minor: int,
    inode: int,
) -> tuple[int, os.stat_result]:
    flags = (os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
             | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeBundleError(
            f"executable mapping cannot be opened safely: {path}") from exc
    try:
        before = os.fstat(descriptor)
        if (not stat.S_ISREG(before.st_mode) or os.major(before.st_dev) != major
                or os.minor(before.st_dev) != minor
                or before.st_ino != inode):
            raise RuntimeBundleError(
                f"executable mapping no longer equals its open file: {path}")
        try:
            descriptor_target = Path(
                f"/proc/self/fd/{descriptor}").resolve(strict=True)
        except OSError as exc:
            raise RuntimeBundleError(
                f"executable mapping descriptor has no stable target: {path}") from exc
        if descriptor_target != path:
            raise RuntimeBundleError(
                f"executable mapping descriptor resolves elsewhere: {path}")
        return descriptor, before
    except BaseException:
        os.close(descriptor)
        raise


def _mapped_file_content_identity(
    path: Path,
    major: int,
    minor: int,
    inode: int,
) -> tuple[str, int]:
    descriptor, before = _open_mapped_file(path, major, minor, inode)
    try:
        digest = hashlib.sha256()
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
        after = os.fstat(descriptor)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if tuple(getattr(before, field) for field in fields) != \
                tuple(getattr(after, field) for field in fields):
            raise RuntimeBundleError(
                f"executable mapping file changed while hashing: {path}")
        return "sha256:" + digest.hexdigest(), before.st_size
    finally:
        os.close(descriptor)


def _native_runtime_observation(
    distributions: Iterable[Mapping[str, Any]],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    image = copy.deepcopy(manifest["image"])
    if platform.system() != "Linux":
        return {
            "imageIdentity": image,
            "containerMarkerPresent": False,
            "imageFilesReadOnly": False,
            "loaderConfiguration": {"files": [], "absentPaths": []},
            "kernelExecutableMappings": [],
            "actualNativeImages": [],
        }

    _standard_expected, image_expected = _retained_runtime_image_maps(manifest)
    distribution_expected: dict[str, tuple[str, int, list[str]]] = {}
    for distribution in distributions:
        for entry in distribution["files"]:
            identity = entry["resolvedPath"]
            prior = distribution_expected.get(identity)
            owners = sorted({*(prior[2] if prior else []), distribution["name"]})
            current = (entry["contentDigest"], entry["byteLength"])
            if prior is not None and prior[:2] != current:
                raise RuntimeBundleError(
                    f"retained wheels disagree about native path {identity!r}")
            distribution_expected[identity] = (*current, owners)

    before, kernel_mappings = _read_executable_mappings()
    actual = []
    for mapped_path, major, minor, inode in before:
        path = Path(mapped_path).resolve(strict=True)
        content_digest, byte_length = _mapped_file_content_identity(
            path, major, minor, inode)
        identity = (content_digest, byte_length)
        retained_image = image_expected.get(str(path))
        retained_distribution = distribution_expected.get(str(path))
        if retained_image == identity and _path_is_read_only(path):
            classification = "PINNED_RUNTIME_IMAGE_FILE"
            owners: list[str] = []
        elif (retained_distribution is not None
              and retained_distribution[:2] == identity):
            classification = "RETAINED_DISTRIBUTION_FILE"
            owners = retained_distribution[2]
        else:
            classification = "UNKNOWN"
            owners = []
        actual.append({
            "resolvedPath": str(path),
            "device": f"{major:x}:{minor:x}",
            "inode": inode,
            "contentDigest": content_digest,
            "byteLength": byte_length,
            "classification": classification,
            "distributions": owners,
        })
    actual.sort(key=lambda entry: entry["resolvedPath"])
    after, after_kernel = _read_executable_mappings()
    if after != before or after_kernel != kernel_mappings:
        raise RuntimeBundleError("executable mapping set changed while observing it")

    python = manifest["python"]
    loader_files = []
    for retained in python["loaderConfigurationFiles"]:
        path = Path(retained["path"])
        digest, length = _file_content_identity(path)
        loader_files.append({
            "path": str(path),
            "contentDigest": digest,
            "byteLength": length,
        })
    absent_paths = [
        path for path in python["requiredAbsentPaths"] if not Path(path).exists()
    ]
    all_image_paths = [
        *(Path(root["path"]) for root in python["standardLibraryRoots"]),
        *(Path(entry["path"]) for entry in (
            python["executable"], python["sharedLibrary"],
            *python["nativeFiles"], *python["loaderConfigurationFiles"],
            *python["requiredExecutables"])),
    ]
    return {
        "imageIdentity": image,
        "containerMarkerPresent": Path("/.dockerenv").exists(),
        "imageFilesReadOnly": all(
            path.exists() and _path_is_read_only(path) for path in all_image_paths),
        "loaderConfiguration": {
            "files": loader_files,
            "absentPaths": absent_paths,
        },
        "kernelExecutableMappings": kernel_mappings,
        "actualNativeImages": actual,
    }


def _native_runtime_stat_signature(
    native_runtime: Mapping[str, Any],
) -> tuple[Any, ...]:
    mappings, kernel_mappings = _read_executable_mappings()
    observed_mappings = []
    for raw_path, major, minor, inode in mappings:
        path = Path(raw_path).resolve(strict=True)
        descriptor, current = _open_mapped_file(path, major, minor, inode)
        try:
            observed_mappings.append((
                str(path), f"{major:x}:{minor:x}", inode,
                current.st_size, current.st_mtime_ns, current.st_ctime_ns,
            ))
        finally:
            os.close(descriptor)
    observed_mappings.sort()
    after_mappings, after_kernel = _read_executable_mappings()
    if after_mappings != mappings or after_kernel != kernel_mappings:
        raise RuntimeBundleError(
            "native executable mappings changed while checking their identity")
    selected = {
        (entry["resolvedPath"], entry["device"], entry["inode"])
        for entry in native_runtime["actualNativeImages"]
    }
    current_selected = {
        (path, device, inode)
        for path, device, inode, _size, _modified, _changed in observed_mappings
    }
    if selected != current_selected \
            or kernel_mappings != native_runtime["kernelExecutableMappings"]:
        added = sorted(current_selected - selected)
        removed = sorted(selected - current_selected)
        selected_kernel = native_runtime["kernelExecutableMappings"]
        raise RuntimeBundleError(
            "live native executable mappings changed after selection: "
            f"added={added[:5]!r}, removed={removed[:5]!r}, "
            f"kernelBefore={selected_kernel!r}, kernelAfter={kernel_mappings!r}")
    loader_stats = []
    for entry in native_runtime["loaderConfiguration"]["files"]:
        path = Path(entry["path"])
        current = path.stat()
        loader_stats.append((
            str(path), current.st_dev, current.st_ino, current.st_size,
            current.st_mtime_ns, current.st_ctime_ns,
        ))
    absent = tuple(
        (path, Path(path).exists())
        for path in native_runtime["loaderConfiguration"]["absentPaths"])
    if any(exists for _path, exists in absent):
        raise RuntimeBundleError("forbidden native loader configuration appeared")
    return (
        tuple(observed_mappings), tuple(sorted(loader_stats)), absent,
        bool(native_runtime["containerMarkerPresent"]),
        bool(native_runtime["imageFilesReadOnly"]),
    )


def _project_component_files(
    package_root: Path,
    retained_components: Iterable[RuntimeComponent],
) -> dict[str, RuntimeComponent]:
    return {
        str(_resolved_path(package_root / component.repository_path)): component
        for component in retained_components
        if component.role in {"RUNTIME_CODE", "RUNTIME_CATALOG_CODE", "PARSER_CODE"}
        and component.repository_path.endswith(".py")
    }


def _loader_name(module) -> str | None:
    loader = getattr(module, "__loader__", None)
    if loader is None:
        return None
    kind = type(loader)
    return f"{kind.__module__}.{kind.__qualname__}"


def _ordered_search_paths(value) -> list[str]:
    paths = []
    for raw in value or ():
        if not isinstance(raw, str) or not raw or not Path(raw).is_absolute():
            raise RuntimeBundleError(
                f"Python package search path is not filesystem-backed: {raw!r}")
        path = str(_resolved_path(raw))
        if raw != path:
            raise RuntimeBundleError(
                f"Python package search path is not canonical: {raw!r}")
        paths.append(path)
    if len(paths) != len(set(paths)):
        raise RuntimeBundleError("Python package search path contains duplicates")
    return paths


def _module_search_paths(module) -> tuple[list[str], list[str]]:
    spec = getattr(module, "__spec__", None)
    return (
        _ordered_search_paths(getattr(module, "__path__", None)),
        _ordered_search_paths(getattr(spec, "submodule_search_locations", None)),
    )


def _import_callable_observation(value) -> dict[str, str]:
    value_type = type(value)
    if isinstance(value, type):
        provider = value
        kind = "CLASS"
    elif (value_type.__module__ == "builtins"
          and value_type.__qualname__ in {"function", "builtin_function_or_method"}):
        provider = value
        kind = "FUNCTION"
    else:
        provider = value_type
        kind = "INSTANCE"
    provider_module = getattr(provider, "__module__", None)
    provider_qualname = getattr(provider, "__qualname__", None)
    if not isinstance(provider_module, str) or not isinstance(provider_qualname, str):
        raise RuntimeBundleError(
            f"Python import provider has no stable class/function identity: {value!r}")
    return {
        "objectKind": kind,
        "providerModule": provider_module,
        "providerQualname": provider_qualname,
        "typeModule": value_type.__module__,
        "typeQualname": value_type.__qualname__,
    }


def _import_infrastructure_observation() -> tuple[list[dict[str, str]],
                                                   list[dict[str, str]]]:
    return (
        [_import_callable_observation(value) for value in sys.meta_path],
        [_import_callable_observation(value) for value in sys.path_hooks],
    )


def _path_importer_cache_state() -> tuple[
        list[dict[str, Any]], dict[str, tuple[object, type]]]:
    """Return canonical provider metadata and exact live finder identities."""
    entries = []
    objects: dict[str, tuple[object, type]] = {}
    for raw_path, finder in tuple(sys.path_importer_cache.items()):
        if (not isinstance(raw_path, str) or not raw_path
                or not Path(raw_path).is_absolute()):
            raise RuntimeBundleError(
                f"Python path importer cache key is not absolute: {raw_path!r}")
        path = str(_resolved_path(raw_path))
        if raw_path != path:
            raise RuntimeBundleError(
                f"Python path importer cache key is not canonical: {raw_path!r}")
        if path in objects:
            raise RuntimeBundleError(
                f"Python path importer cache has duplicate resolved key {path!r}")
        provider = None if finder is None else _import_callable_observation(finder)
        entries.append({"path": path, "finder": provider})
        objects[path] = (finder, type(finder))
    entries.sort(key=lambda item: item["path"])
    return entries, objects


def _path_importer_cache_observation() -> list[dict[str, Any]]:
    return _path_importer_cache_state()[0]


def _file_finder_state(path: str, finder: object) -> tuple[Any, ...]:
    """Bind the mutable state of CPython's standard directory finder."""
    if type(finder) is not importlib.machinery.FileFinder:
        raise RuntimeBundleError(
            f"Python path importer cache has an unreviewed finder for {path!r}")
    finder_path = getattr(finder, "path", None)
    if not isinstance(finder_path, str) or finder_path != path:
        raise RuntimeBundleError(
            f"Python path importer cache finder path differs from key {path!r}")
    if _IMPORT_PROVIDER_METHODS.intersection(vars(finder)):
        raise RuntimeBundleError(
            f"Python path importer cache finder has an instance method override: {path!r}")
    expected_loaders = tuple(
        (suffix, loader)
        for loader, suffixes in (
            (importlib.machinery.ExtensionFileLoader,
             importlib.machinery.EXTENSION_SUFFIXES),
            (importlib.machinery.SourceFileLoader,
             importlib.machinery.SOURCE_SUFFIXES),
            (importlib.machinery.SourcelessFileLoader,
             importlib.machinery.BYTECODE_SUFFIXES),
        )
        for suffix in suffixes
    )
    loaders = tuple(getattr(finder, "_loaders", ()))
    path_cache = getattr(finder, "_path_cache", None)
    relaxed_cache = getattr(finder, "_relaxed_path_cache", None)
    path_mtime = getattr(finder, "_path_mtime", None)
    if (loaders != expected_loaders
            or type(path_cache) is not set
            or type(relaxed_cache) is not set
            or any(not isinstance(name, str) for name in path_cache)
            or any(not isinstance(name, str) for name in relaxed_cache)
            or not isinstance(path_mtime, (int, float))):
        raise RuntimeBundleError(
            f"Python path importer cache finder state is unreviewed for {path!r}")
    return (
        path,
        expected_loaders,
        path_mtime,
        tuple(sorted(path_cache)),
        tuple(sorted(relaxed_cache)),
    )


def _callable_seal_entry(label: str, value: object) -> tuple[Any, ...]:
    defaults = getattr(value, "__defaults__", None)
    kwdefaults = getattr(value, "__kwdefaults__", None)
    closure = getattr(value, "__closure__", None)
    return (
        label,
        value,
        getattr(value, "__code__", None),
        defaults,
        tuple(defaults or ()),
        kwdefaults,
        tuple(sorted((kwdefaults or {}).items())),
        tuple(cell.cell_contents for cell in (closure or ())),
    )


def _import_callable_seal_state() -> tuple[tuple[Any, ...], ...]:
    """Capture executable identities for the live import machinery."""
    entries: list[tuple[Any, ...]] = []

    def add_provider(prefix: str, provider: object) -> None:
        for method_name in sorted(_IMPORT_PROVIDER_METHODS):
            value = None
            for owner in getattr(provider, "__mro__", (provider,)):
                namespace = vars(owner)
                if method_name in namespace:
                    value = namespace[method_name]
                    break
            if isinstance(value, (classmethod, staticmethod)):
                value = value.__func__
            if value is not None:
                entries.append(_callable_seal_entry(
                    f"{prefix}.{method_name}", value))

    for index, provider in enumerate(sys.meta_path):
        if (not isinstance(provider, type)
                and hasattr(provider, "__dict__")
                and _IMPORT_PROVIDER_METHODS.intersection(vars(provider))):
            raise RuntimeBundleError(
                "live sys.meta_path provider has an instance method override: "
                f"index {index}")
        owner = provider if isinstance(provider, type) else type(provider)
        add_provider(f"metaPath[{index}]:{owner.__module__}.{owner.__qualname__}", owner)
    for index, hook in enumerate(sys.path_hooks):
        entries.append(_callable_seal_entry(f"pathHooks[{index}]", hook))
        if isinstance(hook, type):
            add_provider(f"pathHooks[{index}]:type", hook)

    fixed_providers = (
        importlib.machinery.BuiltinImporter,
        importlib.machinery.FrozenImporter,
        importlib.machinery.PathFinder,
        importlib.machinery.FileFinder,
        importlib.machinery.SourceFileLoader,
        importlib.machinery.SourcelessFileLoader,
        importlib.machinery.ExtensionFileLoader,
        importlib.machinery.NamespaceLoader,
    )
    for provider in fixed_providers:
        add_provider(f"fixed:{provider.__module__}.{provider.__qualname__}", provider)
    return tuple(entries)


def _same_callable_seal_entry(
        current: tuple[Any, ...], prior: tuple[Any, ...]) -> bool:
    if current[0] != prior[0] or any(
            current[index] is not prior[index] for index in (1, 2, 3, 5)):
        return False
    for current_values, prior_values in (
        (current[4], prior[4]),
        (current[7], prior[7]),
    ):
        if (len(current_values) != len(prior_values)
                or any(value is not prior_value for value, prior_value in
                       zip(current_values, prior_values))):
            return False
    current_kw, prior_kw = current[6], prior[6]
    return (
        len(current_kw) == len(prior_kw)
        and all(
            current_key == prior_key and current_value is prior_value
            for (current_key, current_value), (prior_key, prior_value)
            in zip(current_kw, prior_kw)
        )
    )


def _test_harness_path(package_root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(package_root).as_posix()
    except ValueError:
        return False
    return any(
        (relative == prefix.rstrip("/") or relative.startswith(prefix))
        if prefix.endswith("/") else relative == prefix
        for prefix in _PROJECT_TEST_PATHS)


def _test_harness_namespace_path(package_root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(package_root).as_posix()
    except ValueError:
        return False
    return (relative in _PROJECT_TEST_NAMESPACE_PATHS
            or _test_harness_path(package_root, path))


def _module_observation(
    package_root: Path,
    project_files: Mapping[str, RuntimeComponent],
    distribution_files: Mapping[str, list[str]],
    dependency_roots: Iterable[str],
    standard_files: Mapping[str, tuple[str, int]],
) -> list[dict[str, Any]]:
    dependency_roots = tuple(dependency_roots)
    pytest_module = sys.modules.get("pytest")
    pytest_origin = getattr(
        getattr(pytest_module, "__spec__", None), "origin", None) \
        or getattr(pytest_module, "__file__", None)
    trusted_test_harness = (
        isinstance(pytest_origin, str)
        and str(_resolved_path(pytest_origin)) in distribution_files)
    modules = []
    for name, module in sorted(sys.modules.items()):
        if module is None:
            continue
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None) or getattr(module, "__file__", None)
        loader = _loader_name(module)
        package_paths, spec_paths = _module_search_paths(module)
        entry: dict[str, Any] = {
            "name": name,
            "loader": loader,
            "packageSearchPaths": package_paths,
            "specSearchPaths": spec_paths,
        }
        if origin in {"built-in", "frozen"}:
            entry.update({
                "classification": origin.upper().replace("-", "_"),
                "origin": origin,
            })
        elif isinstance(origin, str) and origin:
            path = _resolved_path(origin)
            identity = _file_content_identity(path) if path.is_file() else None
            entry["origin"] = str(path)
            if path.suffix in {".pyc", ".pyo"} or "__pycache__" in path.parts:
                classification = "BYTECODE"
            elif str(path) in project_files:
                classification = "RETAINED_PROJECT_COMPONENT"
                component = project_files[str(path)]
                entry["retainedComponent"] = {
                    "role": component.role,
                    "logicalRef": component.logical_ref,
                }
            elif str(path) in distribution_files:
                classification = "RETAINED_DISTRIBUTION_FILE"
                entry["distributions"] = distribution_files[str(path)]
            elif (str(path) in standard_files
                  and identity == standard_files[str(path)]):
                classification = "PINNED_RUNTIME_IMAGE_FILE"
            elif trusted_test_harness and _test_harness_path(package_root, path):
                classification = "NON_RUNTIME_TEST_HARNESS"
            else:
                classification = "UNKNOWN"
            entry["classification"] = classification
            if identity is not None:
                entry["contentDigest"], entry["byteLength"] = identity
        else:
            namespace_paths = package_paths
            entry["origin"] = None
            retained_parent_name = \
                _REVIEWED_ORIGINLESS_AUXILIARY_MODULES.get(name)
            retained_parent = sys.modules.get(retained_parent_name) \
                if retained_parent_name else None
            retained_parent_origin = getattr(
                getattr(retained_parent, "__spec__", None), "origin", None) \
                or getattr(retained_parent, "__file__", None)
            retained_parent_path = (
                str(_resolved_path(retained_parent_origin))
                if isinstance(retained_parent_origin, str) else None)
            if retained_parent_path in distribution_files \
                    or retained_parent_path in standard_files \
                    or retained_parent_path in project_files:
                entry["classification"] = "REVIEWED_NATIVE_AUXILIARY"
                entry["retainedParent"] = {
                    "name": retained_parent_name,
                    "origin": retained_parent_path,
                }
            elif namespace_paths and all(
                    any(path == root or path.startswith(root + os.sep)
                        for root in dependency_roots)
                    or any(component_path.startswith(path + os.sep)
                           for component_path in project_files)
                    or (trusted_test_harness
                        and _test_harness_namespace_path(
                            package_root, Path(path)))
                    for path in namespace_paths):
                entry["classification"] = "RETAINED_NAMESPACE"
            else:
                entry["classification"] = "UNKNOWN"
        modules.append(entry)
    return modules


def _python_flags_document() -> dict[str, Any]:
    return {
        "isolated": sys.flags.isolated,
        "ignoreEnvironment": sys.flags.ignore_environment,
        "noSite": sys.flags.no_site,
        "noUserSite": sys.flags.no_user_site,
        "safePath": bool(getattr(sys.flags, "safe_path", False)),
        "dontWriteBytecode": sys.flags.dont_write_bytecode,
        "hashRandomization": sys.flags.hash_randomization,
        "optimizationLevel": sys.flags.optimize,
    }


def _sys_path_observation(
    package_root: Path,
    dependency_roots: Iterable[str],
    retained_standard_roots: Iterable[str],
) -> list[dict[str, Any]]:
    dependency_roots = set(dependency_roots)
    standard_roots = set(retained_standard_roots)
    entries = []
    for index, raw in enumerate(sys.path):
        if not isinstance(raw, str) or not raw:
            entries.append({"index": index, "path": raw, "classification": "UNKNOWN"})
            continue
        path = str(_resolved_path(raw))
        if raw != path:
            classification = "UNKNOWN"
        elif path == str(package_root):
            classification = "REVIEWED_PROJECT_ROOT"
        elif path in dependency_roots:
            classification = "LOCKED_DEPENDENCY_ROOT"
        elif any(path == root or path.startswith(root + os.sep)
                 for root in standard_roots):
            classification = "PINNED_RUNTIME_IMAGE_ROOT"
        else:
            classification = "UNKNOWN"
        entries.append({"index": index, "path": path, "classification": classification})
    return entries


def _validate_runtime_environment_document(document: Any) -> None:
    top_level = {
        "schemaVersion", "python", "platform", "process", "importPosture",
        "standardRuntime", "nativeRuntime", "distributions",
    }
    python_keys = {
        "implementation", "version", "cacheTag", "soabi", "optimizationLevel",
        "hashSeedEnvironment", "executableDigest", "executableByteLength",
        "flags", "pycachePrefix",
    }
    flag_keys = {
        "isolated", "ignoreEnvironment", "noSite", "noUserSite", "safePath",
        "dontWriteBytecode", "hashRandomization", "optimizationLevel",
    }
    import_keys = {
        "projectRoot", "ambientEnvironment", "startupCustomizationModules",
        "dependencyRoots", "sysPath", "metaPath", "pathHooks",
        "pathImporterCache", "actualModules",
    }
    if (not isinstance(document, dict) or set(document) != top_level
            or document.get("schemaVersion") !=
            "ofarm.runtime-environment-observation.local.v3"
            or not isinstance(document.get("python"), dict)
            or set(document["python"]) != python_keys
            or not isinstance(document["python"].get("flags"), dict)
            or set(document["python"]["flags"]) != flag_keys
            or not isinstance(document.get("importPosture"), dict)
            or set(document["importPosture"]) != import_keys):
        raise RuntimeBundleError("Python runtime environment observation is malformed")
    if (not isinstance(document["python"].get("executableDigest"), str)
            or not _SHA256_RE.fullmatch(
                document["python"].get("executableDigest", ""))
            or not isinstance(document["python"].get("executableByteLength"), int)
            or document["python"]["executableByteLength"] <= 0
            or not isinstance(document["importPosture"].get("projectRoot"), str)
            or not Path(document["importPosture"]["projectRoot"]).is_absolute()
            or set(document["importPosture"].get("ambientEnvironment", {})) !=
            set(_AMBIENT_IMPORT_ENVIRONMENT)
            or not isinstance(document["importPosture"].get(
                "startupCustomizationModules"), list)):
        raise RuntimeBundleError("Python runtime identity fields are malformed")

    process = document.get("process")
    native_loader_environment = (
        process.get("nativeLoaderEnvironment") if isinstance(process, dict) else None)
    if (not isinstance(document.get("platform"), dict)
            or set(document["platform"]) != {"operatingSystem", "machine"}
            or any(not isinstance(value, str) or not value
                   for value in document["platform"].values())
            or not isinstance(process, dict)
            or set(process) != {
                "localeEnvironment", "localeCategories", "timezoneEnvironment",
                "timezoneNames", "utcOffsetSeconds", "nativeLoaderEnvironment",
            }
            or not isinstance(native_loader_environment, dict)
            or any(not isinstance(name, str) or not isinstance(value, str)
                   or (name not in _NATIVE_LOADER_ENVIRONMENT_EXACT
                       and not name.startswith(
                           _NATIVE_LOADER_ENVIRONMENT_PREFIXES))
                   for name, value in native_loader_environment.items())):
        raise RuntimeBundleError("Python process environment observation is malformed")

    roots = document["importPosture"].get("dependencyRoots")
    path_entries = document["importPosture"].get("sysPath")
    modules = document["importPosture"].get("actualModules")
    if (not isinstance(roots, list) or roots != sorted(set(roots))
            or any(not isinstance(path, str) or not Path(path).is_absolute()
                   for path in roots)
            or not isinstance(path_entries, list)
            or any(not isinstance(item, dict)
                   or set(item) != {"index", "path", "classification"}
                   or item.get("index") != index
                   or item.get("classification") not in {
                       "PINNED_RUNTIME_IMAGE_ROOT", "LOCKED_DEPENDENCY_ROOT",
                       "REVIEWED_PROJECT_ROOT", "UNKNOWN"}
                   for index, item in enumerate(path_entries))
            or not isinstance(modules, list)):
        raise RuntimeBundleError("Python import path observation is malformed")
    module_classes = {
        "BUILT_IN", "FROZEN", "BYTECODE", "RETAINED_PROJECT_COMPONENT",
        "RETAINED_DISTRIBUTION_FILE", "PINNED_RUNTIME_IMAGE_FILE",
        "NON_RUNTIME_TEST_HARNESS", "UNKNOWN", "RETAINED_NAMESPACE",
        "REVIEWED_NATIVE_AUXILIARY",
    }
    allowed_module_keys = {
        "name", "loader", "classification", "origin", "packageSearchPaths",
        "specSearchPaths",
        "contentDigest", "byteLength", "retainedComponent", "distributions",
        "retainedParent",
    }
    module_names = []
    for module in modules:
        if (not isinstance(module, dict)
                or not {"name", "loader", "classification", "origin"} <= set(module)
                or not set(module) <= allowed_module_keys
                or not isinstance(module.get("name"), str)
                or module.get("classification") not in module_classes
                or module.get("loader") is not None
                and not isinstance(module.get("loader"), str)
                or module.get("origin") is not None
                and not isinstance(module.get("origin"), str)
                or not isinstance(module.get("packageSearchPaths"), list)
                or not isinstance(module.get("specSearchPaths"), list)
                or any(not isinstance(path, str) or not Path(path).is_absolute()
                       for path in module.get("packageSearchPaths", ()))
                or any(not isinstance(path, str) or not Path(path).is_absolute()
                       for path in module.get("specSearchPaths", ()))
                or len(module.get("packageSearchPaths", ())) !=
                len(set(module.get("packageSearchPaths", ())))
                or len(module.get("specSearchPaths", ())) !=
                len(set(module.get("specSearchPaths", ())))):
            raise RuntimeBundleError("loaded Python module observation is malformed")
        if "contentDigest" in module and (
                not isinstance(module["contentDigest"], str)
                or not _SHA256_RE.fullmatch(module["contentDigest"])
                or not isinstance(module.get("byteLength"), int)
                or module["byteLength"] < 0):
            raise RuntimeBundleError("loaded Python module content identity is malformed")
        module_names.append(module["name"])
    if module_names != sorted(module_names) or len(module_names) != len(set(module_names)):
        raise RuntimeBundleError("loaded Python module inventory is not canonical")

    import_provider_keys = {
        "objectKind", "providerModule", "providerQualname",
        "typeModule", "typeQualname",
    }

    def valid_import_provider(item: object) -> bool:
        return (
            isinstance(item, dict)
            and set(item) == import_provider_keys
            and item.get("objectKind") in {"CLASS", "FUNCTION", "INSTANCE"}
            and all(isinstance(item.get(key), str) and bool(item[key])
                    for key in import_provider_keys - {"objectKind"})
        )

    for field_name in ("metaPath", "pathHooks"):
        providers = document["importPosture"].get(field_name)
        if (not isinstance(providers, list) or not providers
                or any(not valid_import_provider(item) for item in providers)):
            raise RuntimeBundleError(
                f"Python import infrastructure {field_name!r} is malformed")

    importer_cache = document["importPosture"].get("pathImporterCache")
    if (not isinstance(importer_cache, list)
            or any(not isinstance(item, dict)
                   or set(item) != {"path", "finder"}
                   or not isinstance(item.get("path"), str)
                   or not Path(item["path"]).is_absolute()
                   or (item.get("finder") is not None
                       and not valid_import_provider(item["finder"]))
                   for item in importer_cache)):
        raise RuntimeBundleError("Python path importer cache observation is malformed")
    cache_paths = [item["path"] for item in importer_cache]
    if cache_paths != sorted(cache_paths) or len(cache_paths) != len(set(cache_paths)):
        raise RuntimeBundleError(
            "Python path importer cache observation is not canonical")

    def validate_files(files, expected_keys):
        if not isinstance(files, list):
            raise RuntimeBundleError("runtime file inventory is malformed")
        identities = []
        for item in files:
            if (not isinstance(item, dict) or set(item) != expected_keys
                    or not isinstance(item.get("contentDigest"), str)
                    or not _SHA256_RE.fullmatch(item.get("contentDigest", ""))
                    or not isinstance(item.get("byteLength"), int)
                    or item["byteLength"] < 0
                    or not isinstance(item.get("resolvedPath"), str)
                    or not Path(item["resolvedPath"]).is_absolute()):
                raise RuntimeBundleError("runtime file content identity is malformed")
            identities.append(item["resolvedPath"])
        if len(identities) != len(set(identities)):
            raise RuntimeBundleError("runtime file inventory contains duplicates")

    standard = document.get("standardRuntime")
    if (not isinstance(standard, dict)
            or set(standard) != {"roots", "archives", "sharedLibrary"}
            or not isinstance(standard["roots"], list)):
        raise RuntimeBundleError("standard Python runtime observation is malformed")
    standard_root_names = []
    for root in standard["roots"]:
        if (not isinstance(root, dict)
                or set(root) != {"path", "directories", "files"}
                or not isinstance(root.get("path"), str)
                or not Path(root["path"]).is_absolute()
                or not isinstance(root.get("directories"), list)
                or root["directories"] != sorted(set(root["directories"]))
                or any(not isinstance(path, str) or not path
                       for path in root["directories"])):
            raise RuntimeBundleError("standard Python runtime root is malformed")
        validate_files(
            root["files"], {"path", "resolvedPath", "contentDigest", "byteLength"})
        standard_root_names.append(root["path"])
    if standard_root_names != sorted(set(standard_root_names)):
        raise RuntimeBundleError("standard Python runtime roots are not canonical")
    validate_files(
        standard["archives"], {"resolvedPath", "contentDigest", "byteLength"})
    shared = standard["sharedLibrary"]
    if shared is not None:
        validate_files([shared], {"resolvedPath", "contentDigest", "byteLength"})

    native = document.get("nativeRuntime")
    if (not isinstance(native, dict)
            or set(native) != {
                "imageIdentity", "containerMarkerPresent", "imageFilesReadOnly",
                "loaderConfiguration", "kernelExecutableMappings",
                "actualNativeImages",
            }
            or not isinstance(native.get("imageIdentity"), dict)
            or not isinstance(native.get("containerMarkerPresent"), bool)
            or not isinstance(native.get("imageFilesReadOnly"), bool)
            or not isinstance(native.get("kernelExecutableMappings"), list)
            or native["kernelExecutableMappings"] !=
            sorted(set(native["kernelExecutableMappings"]))
            or any(item not in {"[vdso]", "[vsyscall]"}
                   for item in native["kernelExecutableMappings"])):
        raise RuntimeBundleError("native runtime observation is malformed")
    image = native["imageIdentity"]
    if (set(image) != {
            "reference", "indexDigest", "platform", "platformManifestDigest",
            "configDigest", "layers"}
            or not isinstance(image.get("reference"), str)
            or image.get("platform") != "linux/amd64"
            or any(not _SHA256_RE.fullmatch(image.get(key, ""))
                   for key in (
                       "indexDigest", "platformManifestDigest", "configDigest"))
            or not isinstance(image.get("layers"), list)
            or not image["layers"]):
        raise RuntimeBundleError("native runtime image identity is malformed")
    for layer in image["layers"]:
        if (not isinstance(layer, dict)
                or set(layer) != {"digest", "byteLength"}
                or not _SHA256_RE.fullmatch(layer.get("digest", ""))
                or not isinstance(layer.get("byteLength"), int)
                or layer["byteLength"] <= 0):
            raise RuntimeBundleError("native runtime image layer is malformed")
    loader = native.get("loaderConfiguration")
    if (not isinstance(loader, dict)
            or set(loader) != {"files", "absentPaths"}
            or not isinstance(loader.get("absentPaths"), list)
            or loader["absentPaths"] != sorted(set(loader["absentPaths"]))
            or any(not isinstance(path, str) or not Path(path).is_absolute()
                   for path in loader["absentPaths"])):
        raise RuntimeBundleError("native loader configuration observation is malformed")
    if not isinstance(loader.get("files"), list):
        raise RuntimeBundleError("native loader file observation is malformed")
    for entry in loader["files"]:
        _validate_runtime_image_file_entry(entry)
    loader_paths = [entry["path"] for entry in loader["files"]]
    if loader_paths != sorted(loader_paths) or len(loader_paths) != len(set(loader_paths)):
        raise RuntimeBundleError("native loader file observation is not canonical")
    images = native.get("actualNativeImages")
    native_keys = {
        "resolvedPath", "device", "inode", "contentDigest", "byteLength",
        "classification", "distributions",
    }
    if not isinstance(images, list):
        raise RuntimeBundleError("native executable image inventory is malformed")
    image_paths = []
    for entry in images:
        if (not isinstance(entry, dict) or set(entry) != native_keys
                or not isinstance(entry.get("resolvedPath"), str)
                or not Path(entry["resolvedPath"]).is_absolute()
                or not re.fullmatch(r"[0-9a-f]+:[0-9a-f]+", entry.get("device", ""))
                or not isinstance(entry.get("inode"), int) or entry["inode"] <= 0
                or not _SHA256_RE.fullmatch(entry.get("contentDigest", ""))
                or not isinstance(entry.get("byteLength"), int)
                or entry["byteLength"] <= 0
                or entry.get("classification") not in {
                    "PINNED_RUNTIME_IMAGE_FILE", "RETAINED_DISTRIBUTION_FILE",
                    "UNKNOWN",
                }
                or not isinstance(entry.get("distributions"), list)
                or entry["distributions"] != sorted(set(entry["distributions"]))):
            raise RuntimeBundleError("native executable image identity is malformed")
        image_paths.append(entry["resolvedPath"])
    if image_paths != sorted(image_paths) or len(image_paths) != len(set(image_paths)):
        raise RuntimeBundleError("native executable image inventory is not canonical")

    distributions = document.get("distributions")
    if not isinstance(distributions, list):
        raise RuntimeBundleError("Python distribution observation is malformed")
    distribution_names = []
    for distribution in distributions:
        if (not isinstance(distribution, dict)
                or set(distribution) != {
                    "name", "version", "wheelArchiveDigest",
                    "wheelArchiveByteLength", "root", "files",
                }
                or not all(isinstance(distribution.get(key), str)
                           for key in (
                               "name", "version", "wheelArchiveDigest", "root"))
                or not _SHA256_RE.fullmatch(distribution["wheelArchiveDigest"])
                or not isinstance(distribution.get("wheelArchiveByteLength"), int)
                or distribution["wheelArchiveByteLength"] <= 0):
            raise RuntimeBundleError("Python distribution identity is malformed")
        validate_files(
            distribution["files"],
            {"path", "resolvedPath", "contentDigest", "byteLength"})
        distribution_names.append(distribution["name"])
    if distribution_names != sorted(distribution_names) \
            or len(distribution_names) != len(set(distribution_names)):
        raise RuntimeBundleError("Python distribution inventory is not canonical")


def _runtime_environment_document(
    package_root: Path,
    retained_components: Iterable[RuntimeComponent],
) -> dict[str, Any]:
    package_root = package_root.resolve()
    distributions, distribution_files, dependency_roots = \
        _distribution_observation()
    standard_runtime, _observed_standard_files = _standard_runtime_observation()
    image_manifest = _runtime_image_manifest(retained_components)
    standard_files, _native_files = _retained_runtime_image_maps(image_manifest)
    project_files = _project_component_files(
        package_root, retained_components)
    executable_path = Path(sys.executable).resolve(strict=True)
    executable_digest, executable_length = _file_content_identity(executable_path)
    modules = _module_observation(
        package_root, project_files, distribution_files, dependency_roots,
        standard_files)
    meta_path, path_hooks = _import_infrastructure_observation()
    document = {
        "schemaVersion": "ofarm.runtime-environment-observation.local.v3",
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "cacheTag": sys.implementation.cache_tag,
            "soabi": sysconfig.get_config_var("SOABI"),
            "optimizationLevel": sys.flags.optimize,
            "hashSeedEnvironment": os.environ.get("PYTHONHASHSEED"),
            "executableDigest": executable_digest,
            "executableByteLength": executable_length,
            "flags": _python_flags_document(),
            "pycachePrefix": sys.pycache_prefix,
        },
        "platform": {
            "operatingSystem": platform.system(),
            "machine": platform.machine(),
        },
        "process": {
            "localeEnvironment": {
                "LANG": os.environ.get("LANG"),
                "LC_ALL": os.environ.get("LC_ALL"),
            },
            "localeCategories": {
                "collate": locale.setlocale(locale.LC_COLLATE, None),
                "ctype": locale.setlocale(locale.LC_CTYPE, None),
                "monetary": locale.setlocale(locale.LC_MONETARY, None),
                "numeric": locale.setlocale(locale.LC_NUMERIC, None),
                "time": locale.setlocale(locale.LC_TIME, None),
            },
            "timezoneEnvironment": os.environ.get("TZ"),
            "timezoneNames": list(time.tzname),
            "utcOffsetSeconds": -time.timezone,
            "nativeLoaderEnvironment":
                _native_loader_environment_observation(),
        },
        "importPosture": {
            "projectRoot": str(package_root),
            "ambientEnvironment": {
                name: os.environ.get(name) for name in _AMBIENT_IMPORT_ENVIRONMENT
            },
            "startupCustomizationModules": [
                name for name in ("sitecustomize", "usercustomize")
                if name in sys.modules
            ],
            "dependencyRoots": dependency_roots,
            "sysPath": _sys_path_observation(
                package_root, dependency_roots,
                [root["path"] for root in
                 image_manifest["python"]["standardLibraryRoots"]]),
            "metaPath": meta_path,
            "pathHooks": path_hooks,
            "pathImporterCache": _path_importer_cache_observation(),
            "actualModules": modules,
        },
        "standardRuntime": standard_runtime,
        "nativeRuntime": _native_runtime_observation(
            distributions, image_manifest),
        "distributions": distributions,
    }
    _validate_runtime_environment_document(document)
    return document


def _bytecode_or_customization_findings(
    package_root: Path,
    retained_components: Iterable[RuntimeComponent],
    dependency_roots: Iterable[str],
) -> list[str]:
    findings = []
    for component in retained_components:
        if component.role not in {
                "RUNTIME_CODE", "RUNTIME_CATALOG_CODE", "PARSER_CODE"} \
                or not component.repository_path.endswith(".py"):
            continue
        source = package_root / component.repository_path
        if source.with_suffix(".pyc").exists():
            findings.append(str(source.with_suffix(".pyc")))
        cache = source.parent / "__pycache__"
        if cache.is_dir() and any(cache.glob(source.stem + ".*.pyc")):
            findings.append(str(cache))
    for raw_root in dependency_roots:
        root = Path(raw_root)
        if not root.is_dir():
            findings.append(str(root))
            continue
        for directory, directories, filenames in os.walk(root):
            if "__pycache__" in directories:
                findings.append(str(Path(directory) / "__pycache__"))
                directories.remove("__pycache__")
            for filename in filenames:
                if (Path(filename).suffix.lower() in {".pyc", ".pyo", ".pth"}
                        or filename in {"sitecustomize.py", "usercustomize.py"}):
                    findings.append(str(Path(directory) / filename))
    return sorted(set(findings))


def _module_loader_is_reviewed(module: Mapping[str, Any]) -> bool:
    classification = module.get("classification")
    loader = module.get("loader")
    origin = module.get("origin")
    if classification in {"BUILT_IN", "FROZEN"}:
        return loader == "builtins.type"
    if classification == "REVIEWED_NATIVE_AUXILIARY":
        return loader is None
    if classification == "RETAINED_NAMESPACE":
        return loader in {None, "_frozen_importlib_external.NamespaceLoader"}
    if classification == "NON_RUNTIME_TEST_HARNESS":
        return loader in {
            "_frozen_importlib_external.SourceFileLoader",
            "_pytest.assertion.rewrite.AssertionRewritingHook",
        }
    if classification in {
            "RETAINED_PROJECT_COMPONENT", "RETAINED_DISTRIBUTION_FILE",
            "PINNED_RUNTIME_IMAGE_FILE"}:
        if not isinstance(origin, str):
            return False
        native = any(origin.endswith(suffix)
                     for suffix in importlib.machinery.EXTENSION_SUFFIXES)
        expected = ("_frozen_importlib_external.ExtensionFileLoader" if native
                    else "_frozen_importlib_external.SourceFileLoader")
        return loader == expected
    return False


def _require_reviewed_import_search_state(document: Mapping[str, Any]) -> None:
    modules = document["importPosture"]["actualModules"]
    for module in modules:
        package_paths = module["packageSearchPaths"]
        spec_paths = module["specSearchPaths"]
        if package_paths != spec_paths:
            raise RuntimeBundleError(
                f"loaded package {module['name']!r} has divergent __path__ and spec paths")
        if not package_paths:
            continue
        origin = module.get("origin")
        if isinstance(origin, str) and origin not in {"built-in", "frozen"}:
            expected = [str(_resolved_path(origin).parent)]
            if package_paths != expected:
                raise RuntimeBundleError(
                    f"loaded package {module['name']!r} search path does not equal "
                    "its retained origin directory")
        elif module["classification"] != "RETAINED_NAMESPACE":
            raise RuntimeBundleError(
                f"loaded module {module['name']!r} has unreviewed package search paths")

    by_name = {module["name"]: module for module in modules}
    permitted_provider_classes = {
        "BUILT_IN", "FROZEN", "RETAINED_PROJECT_COMPONENT",
        "RETAINED_DISTRIBUTION_FILE", "PINNED_RUNTIME_IMAGE_FILE",
    }
    for field_name in ("metaPath", "pathHooks"):
        providers = document["importPosture"][field_name]
        identities = [canonical_json(item) for item in providers]
        if len(identities) != len(set(identities)):
            raise RuntimeBundleError(
                f"live Python {field_name} contains duplicate provider identities")
        for provider in providers:
            owner = by_name.get(provider["providerModule"])
            if owner is None or owner["classification"] not in permitted_provider_classes:
                raise RuntimeBundleError(
                    f"live Python {field_name} provider is not retained: "
                    f"{provider['providerModule']}.{provider['providerQualname']}")

    if "pathImporterCache" not in document["importPosture"]:
        # Narrow unit seams may exercise package/provider validation without a
        # complete runtime-environment document. Full live documents are
        # schema-validated above and always include the cache observation.
        return
    cache_entries = document["importPosture"]["pathImporterCache"]
    live_entries, live_objects = _path_importer_cache_state()
    if cache_entries != live_entries:
        raise RuntimeBundleError(
            "live sys.path_importer_cache changed during runtime observation")
    search_roots = [Path(item["path"]) for item in
                    document["importPosture"].get("sysPath", [])]
    for entry in cache_entries:
        path = Path(entry["path"])
        if (not path.is_dir()
                or not any(path == root or path.is_relative_to(root)
                           for root in search_roots)):
            raise RuntimeBundleError(
                f"live sys.path_importer_cache key is outside retained roots: {path}")
        finder = live_objects[entry["path"]][0]
        _file_finder_state(entry["path"], finder)
        provider = entry["finder"]
        if provider is None:
            raise RuntimeBundleError(
                f"live sys.path_importer_cache has no retained finder for {path}")
        owner = by_name.get(provider["providerModule"])
        if owner is None or owner["classification"] not in permitted_provider_classes:
            raise RuntimeBundleError(
                "live sys.path_importer_cache provider is not retained: "
                f"{provider['providerModule']}.{provider['providerQualname']}")


def _require_runtime_image_matches_observation(
    document: Mapping[str, Any],
    retained_components: tuple[RuntimeComponent, ...],
) -> None:
    manifest = _runtime_image_manifest(retained_components)
    python_manifest = manifest["python"]
    native = document["nativeRuntime"]
    if (native["imageIdentity"] != manifest["image"]
            or not native["containerMarkerPresent"]
            or not native["imageFilesReadOnly"]):
        raise RuntimeBundleError(
            "live RuntimeBundle is not executing from the retained read-only image")
    if document["process"]["nativeLoaderEnvironment"]:
        raise RuntimeBundleError(
            "live RuntimeBundle forbids ambient native loader customization")
    if (Path(sys.executable).resolve(strict=True) !=
            Path(python_manifest["executable"]["path"])
            or (document["python"]["executableDigest"],
                document["python"]["executableByteLength"]) != (
                    python_manifest["executable"]["contentDigest"],
                    python_manifest["executable"]["byteLength"])):
        raise RuntimeBundleError(
            "live Python executable differs from the retained runtime image")

    actual_roots = document["standardRuntime"]["roots"]
    expected_roots = []
    for retained_root in python_manifest["standardLibraryRoots"]:
        expected_roots.append({
            "path": retained_root["path"],
            "directories": retained_root["directories"],
            "files": [{
                "path": entry["relativePath"],
                "resolvedPath": entry["path"],
                "contentDigest": entry["contentDigest"],
                "byteLength": entry["byteLength"],
            } for entry in retained_root["files"]],
        })
    retained_shared = python_manifest["sharedLibrary"]
    expected_shared = {
        "resolvedPath": retained_shared["path"],
        "contentDigest": retained_shared["contentDigest"],
        "byteLength": retained_shared["byteLength"],
    }
    if (actual_roots != expected_roots
            or document["standardRuntime"]["archives"] != []
            or document["standardRuntime"]["sharedLibrary"] != expected_shared):
        raise RuntimeBundleError(
            "live standard library differs from the retained runtime image manifest")

    loader = native["loaderConfiguration"]
    if (loader["files"] != python_manifest["loaderConfigurationFiles"]
            or loader["absentPaths"] != python_manifest["requiredAbsentPaths"]):
        raise RuntimeBundleError(
            "live native loader configuration differs from the retained image")
    invalid_native = [
        entry for entry in native["actualNativeImages"]
        if entry["classification"] == "UNKNOWN"
        or (entry["classification"] == "PINNED_RUNTIME_IMAGE_FILE"
            and entry["distributions"])
        or (entry["classification"] == "RETAINED_DISTRIBUTION_FILE"
            and not entry["distributions"])
    ]
    if not native["actualNativeImages"] or invalid_native:
        raise RuntimeBundleError(
            "live process has executable mappings outside the retained image/wheels: "
            f"{[entry['resolvedPath'] for entry in invalid_native[:5]]!r}")

    config_matches = [
        component for component in retained_components
        if component.role == "RUNTIME_ENVIRONMENT"
        and component.logical_ref ==
        "environment:conformance/review_baseline_config.json"
    ]
    if len(config_matches) != 1:
        raise RuntimeBundleError("retained runtime baseline config is not unique")
    config = _strict_json_value(
        config_matches[0].canonical_bytes, "retained runtime baseline config")
    required_image = (config.get("requiredEnvironment") or {}).get(
        "pythonRuntimeImage")
    expected_required_image = {
        "reference": manifest["image"]["reference"],
        "indexDigest": manifest["image"]["indexDigest"],
        "platform": manifest["image"]["platform"],
        "platformManifestDigest": manifest["image"]["platformManifestDigest"],
        "rootFilesystem": "READ_ONLY",
    }
    if required_image != expected_required_image:
        raise RuntimeBundleError(
            "retained baseline config and Python image manifest disagree")


def require_live_python_import_posture(
    package_root: Path,
    *,
    retained_components: Iterable[RuntimeComponent] | None = None,
) -> dict[str, Any]:
    """Refuse live binding unless imports are isolated, source-only, and owned."""
    package_root = package_root.resolve()
    if retained_components is None:
        retained_components = _locked_components(package_root)
    retained_components = tuple(retained_components)
    document = _runtime_environment_document(package_root, retained_components)
    flags = document["python"]["flags"]
    expected_flags = {
        "isolated": 1,
        "ignoreEnvironment": 1,
        "noSite": 1,
        "noUserSite": 1,
        "safePath": True,
        "dontWriteBytecode": 1,
        "hashRandomization": 1,
        "optimizationLevel": sys.flags.optimize,
    }
    if flags != expected_flags:
        raise RuntimeBundleError(
            "live RuntimeBundle requires actual python -I -B -S import flags")
    if any(value is not None for value in
           document["importPosture"]["ambientEnvironment"].values()):
        raise RuntimeBundleError(
            "live RuntimeBundle forbids ambient Python import customization")
    _require_runtime_image_matches_observation(document, retained_components)
    if document["importPosture"]["startupCustomizationModules"]:
        raise RuntimeBundleError(
            "live RuntimeBundle forbids sitecustomize/usercustomize")
    path_entries = document["importPosture"]["sysPath"]
    if any(item["classification"] == "UNKNOWN" for item in path_entries):
        raise RuntimeBundleError("live RuntimeBundle sys.path contains an unknown root")
    ranks = {
        "PINNED_RUNTIME_IMAGE_ROOT": 0,
        "LOCKED_DEPENDENCY_ROOT": 1,
        "REVIEWED_PROJECT_ROOT": 2,
    }
    observed_ranks = [ranks[item["classification"]] for item in path_entries]
    if (observed_ranks != sorted(observed_ranks)
            or len({item["path"] for item in path_entries}) != len(path_entries)
            or not path_entries
            or path_entries[-1]["classification"] != "REVIEWED_PROJECT_ROOT"):
        raise RuntimeBundleError("live RuntimeBundle sys.path is not the closed ordered path")
    cache_prefix = document["python"]["pycachePrefix"]
    if (not isinstance(cache_prefix, str) or not cache_prefix
            or Path(cache_prefix).exists()):
        raise RuntimeBundleError(
            "live RuntimeBundle requires an absent isolated bytecode-cache prefix")
    findings = _bytecode_or_customization_findings(
        package_root, retained_components,
        document["importPosture"]["dependencyRoots"])
    if findings:
        raise RuntimeBundleError(
            f"live RuntimeBundle found bytecode/customization files: {findings[:5]!r}")
    invalid_modules = [
        item for item in document["importPosture"]["actualModules"]
        if item["classification"] in {"UNKNOWN", "BYTECODE"}
    ]
    if invalid_modules:
        raise RuntimeBundleError(
            "live RuntimeBundle found imported code outside retained identities: "
            f"{[(item['name'], item['origin']) for item in invalid_modules[:5]]!r}")
    invalid_loaders = [
        item for item in document["importPosture"]["actualModules"]
        if not _module_loader_is_reviewed(item)
    ]
    if invalid_loaders:
        raise RuntimeBundleError(
            "live RuntimeBundle found an unreviewed Python module loader: "
            f"{[(item['name'], item['loader']) for item in invalid_loaders[:5]]!r}")
    _require_reviewed_import_search_state(document)
    component_by_identity = {
        (component.role, component.logical_ref): component
        for component in retained_components
    }
    distribution_inventory: dict[str, tuple[str, int, list[str]]] = {}
    for distribution in document["distributions"]:
        for retained_file in distribution["files"]:
            identity = retained_file["resolvedPath"]
            prior = distribution_inventory.get(identity)
            owners = sorted({*(prior[2] if prior else []), distribution["name"]})
            if prior is not None and prior[:2] != (
                    retained_file["contentDigest"], retained_file["byteLength"]):
                raise RuntimeBundleError(
                    f"retained distributions disagree about shared file {identity!r}")
            distribution_inventory[identity] = (
                retained_file["contentDigest"], retained_file["byteLength"], owners)
    standard_inventory, _native_inventory = _retained_runtime_image_maps(
        _runtime_image_manifest(retained_components))
    for module in document["importPosture"]["actualModules"]:
        retained = module.get("retainedComponent")
        classification = module["classification"]
        if retained is not None:
            component = component_by_identity.get(
                (retained.get("role"), retained.get("logicalRef")))
            if (component is None
                    or module.get("contentDigest") != component.content_digest
                    or module.get("byteLength") != len(component.canonical_bytes)):
                raise RuntimeBundleError(
                    f"loaded project module {module['name']!r} differs from retained code")
        elif classification == "RETAINED_DISTRIBUTION_FILE":
            retained_identity = distribution_inventory.get(module.get("origin"))
            if (retained_identity is None
                    or (module.get("contentDigest"), module.get("byteLength")) !=
                    retained_identity[:2]
                    or module.get("distributions") != retained_identity[2]):
                raise RuntimeBundleError(
                    f"loaded dependency module {module['name']!r} differs from "
                    "the retained distribution file")
        elif classification == "PINNED_RUNTIME_IMAGE_FILE":
            retained_identity = standard_inventory.get(module.get("origin"))
            if (retained_identity is None
                    or (module.get("contentDigest"), module.get("byteLength")) !=
                    retained_identity):
                raise RuntimeBundleError(
                    f"loaded standard module {module['name']!r} differs from "
                    "the retained Python image file")
    return document


def observed_runtime_environment_component(
    package_root: Path | None = None,
    retained_components: Iterable[RuntimeComponent] = (),
) -> RuntimeComponent:
    """Bind the bundle to flags, paths, imported origins, and runtime bytes."""
    package_root = (package_root or Path(__file__).resolve().parents[1]).resolve()
    return _runtime_environment_component_from_document(
        _runtime_environment_document(package_root, tuple(retained_components)))


def _runtime_environment_component_from_document(
    document: dict[str, Any],
) -> RuntimeComponent:
    _validate_runtime_environment_document(document)
    canonical = canonical_json(document).encode("utf-8")
    return RuntimeComponent(
        role="RUNTIME_ENVIRONMENT_OBSERVED",
        logical_ref=_OBSERVED_ENVIRONMENT_REF,
        repository_path="runtime-observed/environment-v3",
        canonicalization=JSON_CANONICALIZATION,
        content_digest=sha256_bytes(canonical),
        canonical_bytes=canonical,
        placement=GLOBAL_CONTENT_PLACEMENT,
    )


def _module_origin_stat_signature(module: object) -> tuple[Any, ...]:
    spec = getattr(module, "__spec__", None)
    origin = getattr(spec, "origin", None) or getattr(module, "__file__", None)
    package_paths, spec_paths = _module_search_paths(module)
    import_state = (
        tuple(package_paths), tuple(spec_paths),
        getattr(module, "__loader__", None),
        getattr(spec, "loader", None),
    )
    if not isinstance(origin, str) or origin in {"built-in", "frozen"}:
        return (origin, *import_state)
    path = _resolved_path(origin)
    try:
        stat = path.stat()
    except OSError:
        return (str(path), None, *import_state)
    return (
        str(path), stat.st_dev, stat.st_ino, stat.st_size,
        stat.st_mtime_ns, stat.st_ctime_ns,
        *import_state,
    )


def _loaded_module_objects() -> dict[str, tuple[object, tuple[Any, ...]]]:
    items = tuple(sys.modules.items())
    if any(not isinstance(name, str) or not name for name, _module in items):
        raise RuntimeBundleError("live sys.modules contains a non-string module key")
    return {
        name: (module, _module_origin_stat_signature(module))
        for name, module in items
    }


def _capture_runtime_environment_seal(
        bundle_digest: str, document: Mapping[str, Any],
) -> RuntimeEnvironmentSeal:
    if (type(sys.modules) is not dict
            or type(sys.path_importer_cache) is not dict
            or type(sys.path) is not list
            or type(sys.meta_path) is not list
            or type(sys.path_hooks) is not list):
        raise RuntimeBundleError(
            "live Python import containers do not have their exact built-in types")
    modules = _loaded_module_objects()
    observed_names = {
        item["name"] for item in document["importPosture"]["actualModules"]
    }
    loaded_names = {
        name for name, (module, _signature) in modules.items()
        if module is not None
    }
    if loaded_names != observed_names:
        raise RuntimeBundleError(
            "live sys.modules changed while the runtime environment was sealed")

    cache_document, cache_objects = _path_importer_cache_state()
    if cache_document != document["importPosture"]["pathImporterCache"]:
        raise RuntimeBundleError(
            "live sys.path_importer_cache changed while the runtime was sealed")
    sealed_cache = tuple(
        (path, finder, finder_type, _file_finder_state(path, finder))
        for path, (finder, finder_type) in sorted(cache_objects.items())
    )
    return RuntimeEnvironmentSeal(
        bundle_digest=bundle_digest,
        flags=tuple(sorted(document["python"]["flags"].items())),
        ambient=tuple(sorted(
            document["importPosture"]["ambientEnvironment"].items())),
        native_loader_environment=tuple(sorted(
            document["process"]["nativeLoaderEnvironment"].items())),
        native_runtime=canonical_json(document["nativeRuntime"]),
        native_runtime_stat=_native_runtime_stat_signature(
            document["nativeRuntime"]),
        customization=tuple(
            document["importPosture"]["startupCustomizationModules"]),
        sys_path=tuple(item["path"] for item in
                       document["importPosture"]["sysPath"]),
        sys_path_object=sys.path,
        meta_path=tuple(canonical_json(item) for item in
                        document["importPosture"]["metaPath"]),
        path_hooks=tuple(canonical_json(item) for item in
                         document["importPosture"]["pathHooks"]),
        meta_path_container=sys.meta_path,
        path_hooks_container=sys.path_hooks,
        meta_path_objects=tuple(sys.meta_path),
        path_hook_objects=tuple(sys.path_hooks),
        path_importer_cache=tuple(
            canonical_json(item) for item in cache_document),
        path_importer_cache_mapping=sys.path_importer_cache,
        path_importer_cache_objects=sealed_cache,
        import_callable_state=_import_callable_seal_state(),
        sys_modules_mapping=sys.modules,
        modules=tuple(
            (name, module, signature)
            for name, (module, signature) in sorted(modules.items())),
        pycache_prefix=document["python"]["pycachePrefix"],
        project_root=document["importPosture"]["projectRoot"],
    )


def _require_sealed_import_object_identities(
        seal: RuntimeEnvironmentSeal,
) -> dict[str, tuple[object, tuple[Any, ...]]]:
    current_callable_state = _import_callable_seal_state()
    if (len(current_callable_state) != len(seal.import_callable_state)
            or any(not _same_callable_seal_entry(current, prior)
                   for current, prior in
                   zip(current_callable_state, seal.import_callable_state))):
        raise RuntimeBundleError(
            "live Python import callable identity changed after activation")
    if sys.modules is not seal.sys_modules_mapping:
        raise RuntimeBundleError(
            "live sys.modules mapping identity changed after RuntimeBundle activation")
    loaded = _loaded_module_objects()
    verified = {
        name: (module, signature) for name, module, signature in seal.modules
    }
    added = sorted(set(loaded) - set(verified))
    removed = sorted(set(verified) - set(loaded))
    if added or removed:
        raise RuntimeBundleError(
            "live Python module set changed after RuntimeBundle activation: "
            f"added={added[:5]!r}, removed={removed[:5]!r}")
    replaced = sorted(
        name for name, prior in verified.items()
        if loaded[name][0] is not prior[0]
    )
    if replaced:
        raise RuntimeBundleError(
            "live Python module object replaced after RuntimeBundle activation: "
            f"{replaced[:5]!r}")

    if sys.path_importer_cache is not seal.path_importer_cache_mapping:
        raise RuntimeBundleError(
            "live sys.path_importer_cache mapping identity changed after activation")
    cache_document, cache_objects = _path_importer_cache_state()
    current_cache_document = tuple(
        canonical_json(item) for item in cache_document)
    if current_cache_document != seal.path_importer_cache:
        raise RuntimeBundleError(
            "live sys.path_importer_cache structure changed after activation")
    verified_cache = {
        path: (finder, finder_type, state)
        for path, finder, finder_type, state in seal.path_importer_cache_objects
    }
    if set(cache_objects) != set(verified_cache):
        raise RuntimeBundleError(
            "live sys.path_importer_cache key set changed after activation")
    for path, (finder, finder_type) in cache_objects.items():
        prior_finder, prior_type, prior_state = verified_cache[path]
        if finder is not prior_finder or finder_type is not prior_type:
            raise RuntimeBundleError(
                "live sys.path_importer_cache finder identity changed after activation: "
                f"{path!r}")
        if _file_finder_state(path, finder) != prior_state:
            raise RuntimeBundleError(
                "live sys.path_importer_cache finder state changed after activation: "
                f"{path!r}")
    return loaded


def _assert_live_import_growth_is_retained(
        bundle: "RuntimeBundle", seal: RuntimeEnvironmentSeal) -> None:
    """Require the activation-time module and importer sets without widening."""
    if type(seal) is not RuntimeEnvironmentSeal or seal.bundle_digest != bundle.digest:
        raise RuntimeBundleError(
            "runtime environment seal does not belong to this RuntimeBundle")
    if tuple(sorted(_python_flags_document().items())) != seal.flags:
        raise RuntimeBundleError("live Python import flags changed after activation")
    ambient = tuple(sorted(
        (name, os.environ.get(name)) for name in _AMBIENT_IMPORT_ENVIRONMENT))
    if ambient != seal.ambient:
        raise RuntimeBundleError(
            "ambient Python import customization changed after activation")
    native_loader_environment = tuple(sorted(
        _native_loader_environment_observation().items()))
    if native_loader_environment != seal.native_loader_environment:
        raise RuntimeBundleError(
            "ambient native loader customization changed after activation")
    customization = tuple(
        name for name in ("sitecustomize", "usercustomize") if name in sys.modules)
    if customization != seal.customization:
        raise RuntimeBundleError(
            "Python startup customization appeared after activation")
    if sys.path is not seal.sys_path_object:
        raise RuntimeBundleError(
            "live sys.path container identity changed after RuntimeBundle activation")
    current_path = tuple(sys.path)
    if current_path != seal.sys_path:
        raise RuntimeBundleError("live sys.path changed after RuntimeBundle activation")
    if sys.meta_path is not seal.meta_path_container:
        raise RuntimeBundleError(
            "live sys.meta_path container identity changed after activation")
    if sys.path_hooks is not seal.path_hooks_container:
        raise RuntimeBundleError(
            "live sys.path_hooks container identity changed after activation")
    current_meta, current_hooks = _import_infrastructure_observation()
    if tuple(canonical_json(item) for item in current_meta) != seal.meta_path:
        raise RuntimeBundleError("live sys.meta_path changed after RuntimeBundle activation")
    if tuple(canonical_json(item) for item in current_hooks) != seal.path_hooks:
        raise RuntimeBundleError("live sys.path_hooks changed after RuntimeBundle activation")
    if (len(sys.meta_path) != len(seal.meta_path_objects)
            or any(current is not selected for current, selected in
                   zip(sys.meta_path, seal.meta_path_objects))):
        raise RuntimeBundleError(
            "live sys.meta_path provider identity changed after RuntimeBundle activation")
    if (len(sys.path_hooks) != len(seal.path_hook_objects)
            or any(current is not selected for current, selected in
                   zip(sys.path_hooks, seal.path_hook_objects))):
        raise RuntimeBundleError(
            "live sys.path_hooks provider identity changed after RuntimeBundle activation")
    if (sys.pycache_prefix != seal.pycache_prefix
            or not isinstance(sys.pycache_prefix, str)
            or Path(sys.pycache_prefix).exists()):
        raise RuntimeBundleError(
            "live bytecode cache posture changed after RuntimeBundle activation")

    if _native_runtime_stat_signature(
            json.loads(seal.native_runtime)) != seal.native_runtime_stat:
        raise RuntimeBundleError(
            "live native executable mappings changed after RuntimeBundle activation")

    loaded = _require_sealed_import_object_identities(seal)
    verified = {
        name: (module, signature) for name, module, signature in seal.modules
    }
    changed = sorted(
        name for name, prior in verified.items()
        if loaded[name][1] != prior[1]
    )
    if changed:
        raise RuntimeBundleError(
            "live Python module state changed after RuntimeBundle activation: "
            f"{changed[:5]!r}")


def require_runtime_environment_seal(
        bundle: "RuntimeBundle", seal: RuntimeEnvironmentSeal,
        consumer: str = "governed decision",
) -> None:
    """Validate one Store-owned, write-once activation seal."""
    try:
        _assert_live_import_growth_is_retained(bundle, seal)
    except RuntimeBundleError as exc:
        raise RuntimeBundleError(f"{consumer} import posture is invalid: {exc}") from exc


def _validate_database_environment_document(document: Any) -> None:
    if not isinstance(document, dict) or set(document) != {
            "schemaVersion", "server", "database", "session", "extensions"}:
        raise RuntimeBundleError("PostgreSQL environment observation is malformed")
    if document.get("schemaVersion") != \
            "ofarm.runtime-database-observation.local.v1":
        raise RuntimeBundleError("PostgreSQL environment observation version is invalid")
    expected_server = {"version", "versionNumber", "normalizedVersion"}
    expected_database = {
        "encoding", "localeProvider", "collation", "ctype",
        "locale", "icuRules", "collationVersion",
    }
    expected_session = {
        "currentUser", "sessionUser", "timezone", "dateStyle",
        "intervalStyle", "searchPath", "sessionReplicationRole",
        "transactionIsolation", "standardConformingStrings",
        "extraFloatDigits", "byteaOutput",
    }
    if (not isinstance(document.get("server"), dict)
            or set(document["server"]) != expected_server
            or not all(isinstance(document["server"].get(key), str)
                       for key in expected_server)
            or not isinstance(document.get("database"), dict)
            or set(document["database"]) != expected_database
            or not isinstance(document.get("session"), dict)
            or set(document["session"]) != expected_session
            or not all(isinstance(document["session"].get(key), str)
                       for key in expected_session)
            or not isinstance(document.get("extensions"), list)):
        raise RuntimeBundleError("PostgreSQL environment observation fields are malformed")
    for field_name, value in document["database"].items():
        if value is not None and not isinstance(value, str):
            raise RuntimeBundleError(
                f"PostgreSQL database observation {field_name!r} is malformed")
    for extension in document["extensions"]:
        if (not isinstance(extension, dict)
                or set(extension) != {"name", "version"}
                or not all(isinstance(value, str) for value in extension.values())):
            raise RuntimeBundleError("PostgreSQL extension observation is malformed")
    names = [extension["name"] for extension in document["extensions"]]
    if names != sorted(names) or len(names) != len(set(names)):
        raise RuntimeBundleError("PostgreSQL extension observation is not canonical")


def database_runtime_environment_component(document: dict[str, Any]) -> RuntimeComponent:
    """Canonicalize one transaction-local PostgreSQL environment observation."""
    _validate_database_environment_document(document)
    canonical = canonical_json(document).encode("utf-8")
    return RuntimeComponent(
        role="RUNTIME_DATABASE_OBSERVED",
        logical_ref=_OBSERVED_DATABASE_REF,
        repository_path="runtime-observed/postgresql-v1",
        canonicalization=JSON_CANONICALIZATION,
        content_digest=sha256_bytes(canonical),
        canonical_bytes=canonical,
        placement=GLOBAL_CONTENT_PLACEMENT,
    )


def _locked_distribution_versions(lock_bytes: bytes) -> dict[str, str]:
    try:
        text = lock_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise RuntimeBundleError("retained dependency lock is not UTF-8") from exc
    versions = {}
    pattern = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)")
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        name, version = match.groups()
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        if normalized in versions:
            raise RuntimeBundleError(
                f"duplicate retained dependency lock entry {normalized!r}")
        versions[normalized] = version
    if not versions:
        raise RuntimeBundleError("retained dependency lock contains no distributions")
    return versions


def assert_runtime_environment_compatible(
        bundle: "RuntimeBundle",
) -> tuple[dict[str, Any], RuntimeEnvironmentSeal]:
    """Validate activation and return its requirement document and frozen seal."""
    package_root = Path(bundle.descriptor.profile_root).resolve().parent
    current_document = require_live_python_import_posture(
        package_root, retained_components=bundle.components)
    observed = bundle.json_component(
        "RUNTIME_ENVIRONMENT_OBSERVED", _OBSERVED_ENVIRONMENT_REF)
    _validate_runtime_environment_document(observed)
    if current_document != observed:
        raise RuntimeBundleError(
            "observed interpreter, import posture, or runtime bytes changed after selection")
    config_doc = bundle.json_component(
        "RUNTIME_ENVIRONMENT", "environment:conformance/review_baseline_config.json")
    required = config_doc.get("requiredEnvironment")
    if not isinstance(required, dict):
        raise RuntimeBundleError("retained runtime baseline has no requiredEnvironment")
    retained_python_version = bundle.component(
        "RUNTIME_ENVIRONMENT", "environment:.python-version"
    ).canonical_bytes.decode("utf-8", errors="strict").strip()
    if retained_python_version != required.get("pythonVersion"):
        raise RuntimeBundleError(
            "retained .python-version and runtime baseline disagree")
    expected_python = {
        "implementation": required.get("pythonImplementation"),
        "version": required.get("pythonVersion"),
        "optimizationLevel": required.get("pythonOptimizationLevel"),
    }
    actual_python = observed["python"]
    for field_name, expected in expected_python.items():
        if actual_python.get(field_name) != expected:
            raise RuntimeBundleError(
                f"observed Python {field_name} {actual_python.get(field_name)!r} "
                f"does not equal retained requirement {expected!r}")
    if (observed["platform"].get("operatingSystem")
            != required.get("operatingSystem")
            or observed["platform"].get("machine") != required.get("machine")):
        raise RuntimeBundleError(
            "observed operating system or machine differs from retained requirement")
    if actual_python.get("hashSeedEnvironment") != required.get("pythonHashSeed"):
        raise RuntimeBundleError(
            "observed PYTHONHASHSEED differs from retained requirement")
    process = observed.get("process") or {}
    locale_environment = process.get("localeEnvironment") or {}
    if (locale_environment.get("LANG") != required.get("locale")
            or locale_environment.get("LC_ALL") != required.get("locale")):
        raise RuntimeBundleError(
            "observed process locale environment differs from retained requirement")
    if (process.get("timezoneEnvironment") != required.get("timezone")
            or process.get("utcOffsetSeconds") != 0
            or not process.get("timezoneNames")
            or process["timezoneNames"][0] not in {"UTC", "GMT"}):
        raise RuntimeBundleError(
            "observed process timezone differs from retained requirement")
    expected_distributions = {}
    for logical_ref in (
        "environment:requirements-review-baseline.lock",
        "environment:requirements-review-pip.lock",
    ):
        component = bundle.component("RUNTIME_ENVIRONMENT", logical_ref)
        for name, version in _locked_distribution_versions(
                component.canonical_bytes).items():
            if name in expected_distributions:
                raise RuntimeBundleError(
                    f"distribution {name!r} appears in multiple retained locks")
            expected_distributions[name] = version
    actual_distributions = {
        item["name"]: item["version"] for item in observed["distributions"]}
    if actual_distributions != expected_distributions:
        raise RuntimeBundleError(
            "installed distribution set/versions differ from retained locks")
    final_document = require_live_python_import_posture(
        package_root, retained_components=bundle.components)
    if final_document != observed:
        raise RuntimeBundleError(
            "Python runtime identity changed while activation was being sealed")
    seal = bundle._selection_environment_seal
    if type(seal) is not RuntimeEnvironmentSeal:
        raise RuntimeBundleError(
            "live RuntimeBundle has no selection-time runtime environment seal")
    require_runtime_environment_seal(
        bundle, seal, "RuntimeBundle activation")
    return required, seal


@dataclass(frozen=True)
class SelectedReferenceIdentity:
    family_id: str
    snapshot_ref: str
    snapshot_payload_digest: str
    source_identities: tuple[str, ...]
    source_byte_status: str
    unavailable_source_identities: tuple[str, ...] = ()
    data_family: str | None = None
    data_payload_digest: str | None = None
    source_digest: str | None = None

    def __post_init__(self) -> None:
        if self.source_byte_status not in {"LOCKED", "PROVENANCE_LOCATOR_ONLY"}:
            raise RuntimeBundleError("unknown selected-reference source byte status")
        if (not isinstance(self.family_id, str) or not self.family_id
                or not isinstance(self.snapshot_ref, str) or not self.snapshot_ref
                or any(not isinstance(ref, str) or not ref
                       for ref in self.source_identities)
                or any(not isinstance(ref, str) or not ref
                       for ref in self.unavailable_source_identities)):
            raise RuntimeBundleError("selected-reference identities are malformed")
        if (len(self.source_identities) != len(set(self.source_identities))
                or len(self.unavailable_source_identities) !=
                len(set(self.unavailable_source_identities))):
            raise RuntimeBundleError("selected-reference identities contain duplicates")
        if any(not ref.startswith(("archive:", "surface:"))
               for ref in self.unavailable_source_identities):
            raise RuntimeBundleError(
                "unretained reference identities must be closed non-content locators")
        if self.data_family is not None \
                and (not isinstance(self.data_family, str) or not self.data_family):
            raise RuntimeBundleError("selected-reference data family is malformed")
        for label, digest in (
            ("snapshot payload", self.snapshot_payload_digest),
            ("reference data", self.data_payload_digest),
            ("reference source", self.source_digest),
        ):
            if digest is not None and not _SHA256_RE.fullmatch(digest):
                raise RuntimeBundleError(
                    f"{label} identity for {self.snapshot_ref!r} is not a full SHA-256")
        has_data_family = self.data_family is not None
        if has_data_family != (self.data_payload_digest is not None) \
                or has_data_family != (self.source_digest is not None):
            raise RuntimeBundleError(
                f"selected reference {self.snapshot_ref!r} has an incomplete "
                "reference-data identity")

    def identity_document(self) -> dict[str, Any]:
        return {key: value for key, value in {
            "familyId": self.family_id,
            "snapshotRef": self.snapshot_ref,
            "snapshotPayloadDigest": self.snapshot_payload_digest,
            "sourceIdentities": list(self.source_identities),
            "sourceByteStatus": self.source_byte_status,
            "unavailableSourceIdentities": list(self.unavailable_source_identities),
            "dataFamily": self.data_family,
            "dataPayloadDigest": self.data_payload_digest,
            "sourceDigest": self.source_digest,
        }.items() if value is not None}


@dataclass(frozen=True)
class RuntimeBundle:
    descriptor: Any
    digest: str
    bundle_ref: str
    canonical_document_bytes: bytes
    components: tuple[RuntimeComponent, ...]
    selected_references: tuple[SelectedReferenceIdentity, ...]
    construction_mode: str
    _selection_environment_seal: RuntimeEnvironmentSeal | None = field(
        default=None, repr=False, compare=False)
    _live_selection_proof: InitVar[object | None] = None

    def __post_init__(self, _live_selection_proof) -> None:
        if self.construction_mode not in {"LIVE_CURRENT", "PERSISTED_AUDIT"}:
            raise RuntimeBundleError("RuntimeBundle construction mode is unverified")
        if ((self.construction_mode == "LIVE_CURRENT")
                != (_live_selection_proof is _LIVE_SELECTION_PROOF)):
            raise RuntimeBundleError(
                "RuntimeBundle live-selection provenance is unverified")
        if self.construction_mode == "LIVE_CURRENT":
            if (type(self._selection_environment_seal) is not RuntimeEnvironmentSeal
                    or self._selection_environment_seal.bundle_digest != self.digest):
                raise RuntimeBundleError(
                    "live RuntimeBundle lacks its exact selection-time import seal")
        elif self._selection_environment_seal is not None:
            raise RuntimeBundleError(
                "persisted-audit RuntimeBundle cannot carry a live import seal")
        if not _SHA256_RE.fullmatch(self.digest):
            raise RuntimeBundleError("RuntimeBundle digest must be a full SHA-256")
        if self.bundle_ref != f"runtimebundle:{self.digest}":
            raise RuntimeBundleError("RuntimeBundle ref does not match its digest")
        actual = sha256_bytes(self.canonical_document_bytes)
        if actual != self.digest:
            raise RuntimeBundleError(
                f"RuntimeBundle digest mismatch: declared {self.digest}, actual {actual}")
        try:
            document = _strict_json_value(
                self.canonical_document_bytes, "RuntimeBundle document")
        except RuntimeBundleError as exc:
            raise RuntimeBundleError("RuntimeBundle document bytes are malformed") from exc
        if not isinstance(document, dict):
            raise RuntimeBundleError("RuntimeBundle document must be an object")
        if set(document) != {
                "schemaVersion", "canonicalization", "tenantRef", "profileRef",
                "packRef", "components", "selectedReferenceIdentities"}:
            raise RuntimeBundleError(
                "RuntimeBundle document has unknown or missing fields")
        if canonical_json(document).encode("utf-8") != self.canonical_document_bytes:
            raise RuntimeBundleError("RuntimeBundle document bytes are not canonical")
        if document.get("schemaVersion") != BUNDLE_VERSION \
                or document.get("canonicalization") != JSON_CANONICALIZATION \
                or not isinstance(document.get("tenantRef"), str) \
                or not document.get("tenantRef") \
                or document.get("profileRef") != self.descriptor.profile_ref \
                or document.get("packRef") != self.descriptor.pack_ref:
            raise RuntimeBundleError(
                "RuntimeBundle document identity does not match its descriptor")
        if document.get("components") != [
                component.identity_document() for component in self.components]:
            raise RuntimeBundleError(
                "RuntimeBundle document component inventory does not equal the object")
        if document.get("selectedReferenceIdentities") != [
                reference.identity_document() for reference in self.selected_references]:
            raise RuntimeBundleError(
                "RuntimeBundle document selected references do not equal the object")
        keys = [(component.role, component.logical_ref) for component in self.components]
        if len(keys) != len(set(keys)):
            raise RuntimeBundleError("RuntimeBundle contains duplicate component role/ref entries")
        for component in self.components:
            _validate_tenant_component_owner(component, document["tenantRef"])
        descriptor_components = [component for component in self.components
                                 if component.role == "PROFILE_DESCRIPTOR"
                                 and component.logical_ref == self.descriptor.profile_ref]
        if len(descriptor_components) != 1:
            raise RuntimeBundleError(
                "RuntimeBundle lacks exactly one retained profile descriptor")
        _assert_descriptor_matches_component(
            self.descriptor,
            descriptor_components[0],
            document["profileRef"],
            document["packRef"],
        )
        reference_ids = [reference.snapshot_ref for reference in self.selected_references]
        if len(reference_ids) != len(set(reference_ids)):
            raise RuntimeBundleError("RuntimeBundle contains duplicate selected references")
        component_map = {(component.role, component.logical_ref): component
                         for component in self.components}
        environment_component = component_map.get(
            ("RUNTIME_ENVIRONMENT_OBSERVED", _OBSERVED_ENVIRONMENT_REF))
        if environment_component is None:
            raise RuntimeBundleError(
                "RuntimeBundle has no closed Python environment observation")
        _validate_runtime_environment_document(_strict_json_value(
            environment_component.canonical_bytes,
            "RuntimeBundle Python environment observation"))
        snapshot_components = {
            logical_ref for role, logical_ref in component_map
            if role == "REFERENCE_SNAPSHOT"
        }
        if snapshot_components != set(reference_ids):
            raise RuntimeBundleError(
                "RuntimeBundle selected-reference and snapshot-component sets differ")
        selected_data_components = set()
        referenced_source_components = set()
        for reference in self.selected_references:
            snapshot = component_map[("REFERENCE_SNAPSHOT", reference.snapshot_ref)]
            if snapshot.content_digest != reference.snapshot_payload_digest:
                raise RuntimeBundleError(
                    f"selected snapshot identity drift for {reference.snapshot_ref!r}")
            try:
                snapshot_payload = _strict_json_value(
                    snapshot.canonical_bytes,
                    f"selected snapshot {reference.snapshot_ref!r}")
            except RuntimeBundleError as exc:
                raise RuntimeBundleError(
                    f"selected snapshot bytes are malformed for "
                    f"{reference.snapshot_ref!r}") from exc
            if (snapshot_payload.get("referenceSnapshotId") != reference.snapshot_ref
                    or tuple(snapshot_payload.get("sourceArtifactRefs", []))
                    != reference.source_identities):
                raise RuntimeBundleError(
                    f"selected snapshot provenance identity drift for "
                    f"{reference.snapshot_ref!r}")
            expected_unavailable = tuple(
                ref for ref in reference.source_identities
                if not (isinstance(ref, str) and (
                    ref.startswith("artifact:") or ref.startswith("digest:")))
            )
            if reference.unavailable_source_identities != expected_unavailable:
                raise RuntimeBundleError(
                    f"selected snapshot unavailable-source identity drift for "
                    f"{reference.snapshot_ref!r}")
            if reference.family_id != _family_for_snapshot(
                    self.descriptor, reference.snapshot_ref):
                raise RuntimeBundleError(
                    f"selected snapshot family identity drift for "
                    f"{reference.snapshot_ref!r}")
            declared_family = self.descriptor.reference_family(reference.family_id)
            if (reference.data_family is not None
                    and reference.data_family != declared_family.data_family):
                raise RuntimeBundleError(
                    f"selected snapshot data-family identity drift for "
                    f"{reference.snapshot_ref!r}")
            artifact_refs = {
                ref for ref in reference.source_identities
                if isinstance(ref, str) and ref.startswith("artifact:")
            }
            digest_refs = {
                ref for ref in reference.source_identities
                if isinstance(ref, str) and ref.startswith("digest:")
            }
            paired_digest_refs = set()
            for artifact_ref in artifact_refs:
                source = component_map.get(("REFERENCE_SOURCE", artifact_ref))
                if source is None or f"digest:{source.content_digest}" not in \
                        reference.source_identities:
                    raise RuntimeBundleError(
                        f"selected source bytes/identity are incomplete for {artifact_ref!r}")
                referenced_source_components.add(artifact_ref)
                paired_digest_refs.add(f"digest:{source.content_digest}")
            if reference.data_family is not None:
                data_ref = f"{reference.snapshot_ref}#{reference.data_family}"
                data = component_map.get(("REFERENCE_DATA", data_ref))
                if (data is None or reference.source_byte_status != "LOCKED"
                        or data.content_digest != reference.data_payload_digest
                        or reference.source_digest != data.content_digest
                        or f"digest:{reference.source_digest}" not in
                        reference.source_identities):
                    raise RuntimeBundleError(
                        f"selected reference data/source identity is incomplete for "
                        f"{reference.snapshot_ref!r}")
                selected_data_components.add(data_ref)
                paired_digest_refs.add(f"digest:{reference.source_digest}")
            elif reference.source_byte_status == "LOCKED" and not artifact_refs:
                raise RuntimeBundleError(
                    f"selected reference {reference.snapshot_ref!r} claims locked "
                    "source bytes but has no retained source/data component")
            elif reference.source_byte_status == "PROVENANCE_LOCATOR_ONLY" \
                    and artifact_refs:
                raise RuntimeBundleError(
                    f"locator-only reference {reference.snapshot_ref!r} names a "
                    "retained source artifact")
            if digest_refs != paired_digest_refs:
                raise RuntimeBundleError(
                    f"selected reference {reference.snapshot_ref!r} has an unpaired "
                    "or missing digest source identity")
        actual_data_components = {
            logical_ref for role, logical_ref in component_map if role == "REFERENCE_DATA"
        }
        if actual_data_components != selected_data_components:
            raise RuntimeBundleError(
                "RuntimeBundle selected-reference data component set is not exact")
        actual_source_components = {
            logical_ref for role, logical_ref in component_map if role == "REFERENCE_SOURCE"
        }
        if actual_source_components != referenced_source_components:
            raise RuntimeBundleError(
                "RuntimeBundle selected-reference source component set is not exact")

    @property
    def policy_ref(self) -> str:
        return self.descriptor.evidence_policy_ref

    @property
    def tenant_ref(self) -> str:
        return _strict_json_value(
            self.canonical_document_bytes, "RuntimeBundle document")["tenantRef"]

    def component(self, role: str, logical_ref: str) -> RuntimeComponent:
        matches = [component for component in self.components
                   if component.role == role and component.logical_ref == logical_ref]
        if len(matches) != 1:
            raise RuntimeBundleError(
                f"RuntimeBundle expected one {role!r} component {logical_ref!r}; "
                f"found {len(matches)}")
        return matches[0]

    def json_component(self, role: str, logical_ref: str) -> dict[str, Any]:
        component = self.component(role, logical_ref)
        if component.canonicalization != JSON_CANONICALIZATION:
            raise RuntimeBundleError(f"component {logical_ref!r} is not canonical JSON")
        return copy.deepcopy(_strict_json_value(
            component.canonical_bytes,
            f"runtime JSON component {logical_ref!r}"))

    def policy_document(self) -> dict[str, Any]:
        return self.json_component("PROFILE_POLICY", self.descriptor.evidence_policy_ref)

    def reference_payload(self, snapshot_ref: str) -> dict[str, Any]:
        return self.json_component("REFERENCE_SNAPSHOT", snapshot_ref)

    def selected_reference(self, snapshot_ref: str) -> SelectedReferenceIdentity:
        matches = [reference for reference in self.selected_references
                   if reference.snapshot_ref == snapshot_ref]
        if len(matches) != 1:
            raise RuntimeBundleError(
                f"RuntimeBundle expected one selected reference {snapshot_ref!r}; "
                f"found {len(matches)}")
        return matches[0]

    def reference_data_payload(
        self,
        snapshot_ref: str,
        data_family: str,
    ) -> dict[str, Any]:
        """Return only retained, digest-verified data selected into this bundle.

        A locator-only ReferenceSnapshot is useful context provenance, but it
        is never a lookup surface.  Consumers must cross this method so absent
        retained source/data bytes fail closed instead of becoming an empty or
        live-filesystem lookup.
        """
        reference = self.selected_reference(snapshot_ref)
        if (reference.source_byte_status != "LOCKED"
                or reference.data_family != data_family
                or reference.data_payload_digest is None
                or reference.source_digest is None):
            raise RuntimeBundleError(
                f"selected reference {snapshot_ref!r} has no governed retained "
                f"{data_family!r} source/data bytes")
        component = self.component(
            "REFERENCE_DATA", f"{snapshot_ref}#{data_family}")
        if component.content_digest != reference.data_payload_digest:
            raise RuntimeBundleError(
                f"selected reference data identity drift for {snapshot_ref!r}")
        return self.json_component("REFERENCE_DATA", component.logical_ref)

    @property
    def reference_payloads(self):
        return MappingProxyType({
            reference.snapshot_ref: self.reference_payload(reference.snapshot_ref)
            for reference in self.selected_references
        })


def _repository_relative(package_root: Path, path: Path) -> str:
    try:
        resolved = path.resolve(strict=True)
        return resolved.relative_to(package_root.resolve(strict=True)).as_posix()
    except (OSError, ValueError) as exc:
        raise RuntimeBundleError(f"runtime component escapes package root: {path}") from exc


def _component_from_path(
    package_root: Path,
    *,
    role: str,
    logical_ref: str,
    path: Path,
    canonicalization: str,
    expected_digest: str | None = None,
    expected_placement: str | None = None,
) -> RuntimeComponent:
    relative = _repository_relative(package_root, path)
    canonical = _component_bytes(path, canonicalization)
    actual = sha256_bytes(canonical)
    placement = component_placement(
        role, canonicalization, canonical, relative)
    if expected_digest is not None:
        if not _SHA256_RE.fullmatch(expected_digest):
            raise RuntimeBundleError(
                f"component lock entry {logical_ref!r} lacks a full SHA-256")
        if actual != expected_digest:
            raise RuntimeBundleError(
                f"component lock mismatch for {logical_ref!r}: "
                f"expected {expected_digest}, actual {actual}")
    if expected_placement is not None and placement != expected_placement:
        raise RuntimeBundleError(
            f"component lock placement mismatch for {logical_ref!r}: "
            f"expected {expected_placement}, actual {placement}")
    return RuntimeComponent(
        role=role,
        logical_ref=logical_ref,
        repository_path=relative,
        canonicalization=canonicalization,
        content_digest=actual,
        canonical_bytes=canonical,
        placement=placement,
    )


def _profile_instance_ref(payload: dict[str, Any], path: Path) -> str:
    for key in (
        "activeArtifactSetId",
        "packActivationSetId",
        "agronomicCodeBindingProfileId",
        "contextSnapshotId",
        "referenceSnapshotId",
        "manifestId",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    raise RuntimeBundleError(f"profile instance at {path} has no recognized identifier")


def _family_for_snapshot(descriptor, snapshot_ref: str) -> str:
    matches = [family.family_id for family in descriptor.reference_families
               if snapshot_ref == family.snapshot_prefix
               or snapshot_ref.startswith(family.snapshot_prefix + ".")]
    if len(matches) != 1:
        raise RuntimeBundleError(
            f"selected ReferenceSnapshot {snapshot_ref!r} maps to {len(matches)} families")
    return matches[0]


def _profile_spine_in_descriptor_lineage(
    descriptor,
    payload: dict[str, Any],
    deployed_code_binding_refs: set[str],
    tenant_ref: str,
) -> bool:
    kind = payload.get("schemaVersion")
    scope_field = {
        "ofarm.activeartifactset.v0.1": "deploymentScope",
        "ofarm.packactivationset.v0.1": "targetScope",
    }.get(kind)
    if scope_field is not None:
        scope = payload.get(scope_field)
        return (payload.get("activePackRefs") == [descriptor.pack_ref]
                and payload.get("activeProfileRefs") == [descriptor.profile_ref]
                and scope == {"scopeType": "TENANT", "scopeRef": tenant_ref})
    if kind == "ofarm.agronomiccodebindingprofile.v0.1":
        profile_scope = payload.get("profileScope")
        pack_refs = (profile_scope.get("packRefs")
                     if isinstance(profile_scope, dict) else None)
        return (isinstance(pack_refs, list)
                and all(isinstance(ref, str) for ref in pack_refs)
                and descriptor.pack_ref in pack_refs
                and payload.get("agronomicCodeBindingProfileId")
                in deployed_code_binding_refs)
    return False


def _validate_selected_spine_scopes(instance_payloads, tenant_ref: str) -> None:
    """Every retained deployment/activation belongs to this runtime tenant."""
    for logical_ref, (payload, _path) in instance_payloads.items():
        kind = payload.get("schemaVersion")
        scope_field = {
            "ofarm.activeartifactset.v0.1": "deploymentScope",
            "ofarm.packactivationset.v0.1": "targetScope",
        }.get(kind)
        if scope_field is None:
            continue
        expected = {"scopeType": "TENANT", "scopeRef": tenant_ref}
        if payload.get(scope_field) != expected:
            raise RuntimeBundleError(
                f"selected profile spine {logical_ref!r} is not scoped exactly "
                f"to runtime tenant {tenant_ref!r}")


def _validate_artifact_ref_list(
    active_refs,
    component_map,
    *,
    require_all_authored: bool,
) -> None:
    if not isinstance(active_refs, list) or any(
            not isinstance(ref, str) or not ref for ref in active_refs):
        raise RuntimeBundleError("ActiveArtifactSet activeArtifactRefs is malformed")
    if len(active_refs) != len(set(active_refs)):
        raise RuntimeBundleError("ActiveArtifactSet contains duplicate activeArtifactRefs")

    direct_roles = {
        "contract:": "CONTRACT_SCHEMA",
        "queryspec:": "QUERY_SPECIFICATION",
        "queryplan:": "QUERY_PLAN",
        "policy:": "PROFILE_POLICY",
        "codebindingprofile:": "PROFILE_INSTANCE",
        "referencesnapshot:": "REFERENCE_SNAPSHOT",
        "manifest:": "ACTIVE_MANIFEST",
    }
    selected = set(active_refs)
    view_output_modes = {
        "view:si.ffs.spray-register.passportview.v0_1": "PASSPORT_VIEW",
        "view:si.ffs.inspection-register.documentassembly.v0_1":
            "DOCUMENT_ASSEMBLY_INPUT",
    }
    for ref in active_refs:
        if ref.startswith("view:"):
            suffix = ref.split(":", 1)[1]
            query_ref = "queryspec:" + suffix
            plan_ref = "queryplan:" + suffix
            if (("QUERY_SPECIFICATION", query_ref) not in component_map
                    or ("QUERY_PLAN", plan_ref) not in component_map
                    or query_ref not in selected
                    or plan_ref not in selected
                    or ("RUNTIME_CODE", "python:kernel/views.py") not in component_map):
                raise RuntimeBundleError(
                    f"active view ref {ref!r} lacks its exact query specification, "
                    "query plan, or locked output implementation")
            try:
                plan = _strict_json_value(
                    component_map[("QUERY_PLAN", plan_ref)].canonical_bytes,
                    f"query plan {plan_ref!r}")
            except RuntimeBundleError as exc:
                raise RuntimeBundleError(
                    f"active view ref {ref!r} has a malformed query plan") from exc
            expected_mode = view_output_modes.get(ref)
            if (expected_mode is None
                    or plan.get("sourceQuerySpecificationId") != query_ref
                    or (plan.get("outputAssembly") or {}).get("mode") != expected_mode):
                raise RuntimeBundleError(
                    f"active view ref {ref!r} query plan does not target its exact "
                    "query specification and output implementation mode")
            continue
        role = next((candidate_role for prefix, candidate_role in direct_roles.items()
                     if ref.startswith(prefix)), None)
        if role is None or (role, ref) not in component_map:
            raise RuntimeBundleError(
                f"active artifact ref {ref!r} has no exact RuntimeBundle component")

    if require_all_authored:
        # Authored executable artifacts in the current lock are selection-bearing,
        # not a silent superset: every one must be named by the current AAS.
        for role in ("QUERY_SPECIFICATION", "QUERY_PLAN", "ACTIVE_MANIFEST"):
            locked_refs = {logical_ref for component_role, logical_ref in component_map
                           if component_role == role}
            if not locked_refs <= selected:
                raise RuntimeBundleError(
                    f"locked {role} component is absent from activeArtifactRefs: "
                    f"{sorted(locked_refs - selected)}")


def _validate_active_artifact_refs(descriptor, instance_payloads, component_map) -> None:
    try:
        current = instance_payloads[descriptor.active_artifact_set_ref][0]
    except (KeyError, TypeError) as exc:
        raise RuntimeBundleError(
            "selected ActiveArtifactSet cannot be resolved from profile instances") from exc
    for logical_ref, (payload, _path) in instance_payloads.items():
        if payload.get("schemaVersion") != "ofarm.activeartifactset.v0.1":
            continue
        _validate_artifact_ref_list(
            payload.get("activeArtifactRefs"), component_map,
            require_all_authored=logical_ref == descriptor.active_artifact_set_ref,
        )
        sources = payload.get("sourcePackActivationSetRefs")
        if not isinstance(sources, list) or not sources or any(
                ("PROFILE_INSTANCE", source) not in component_map for source in sources):
            raise RuntimeBundleError(
                f"ActiveArtifactSet {logical_ref!r} has no retained source activation set")
    if current.get("activeArtifactSetId") != descriptor.active_artifact_set_ref:
        raise RuntimeBundleError("descriptor current ActiveArtifactSet identity drift")


def _validate_historical_artifact_origin(
    payload: dict[str, Any],
    current_components: Mapping[tuple[str, str], RuntimeComponent],
    origin_bundle: RuntimeBundle,
) -> None:
    """Refuse stable artifact refs whose bytes changed since their origin bundle.

    Historical code-binding and reference instances are themselves retained in
    the new bundle.  Code-owned stable refs, however, must still denote the same
    exact component bytes as when the historical ActiveArtifactSet was written;
    otherwise AS_OF would silently reinterpret old deployment metadata under
    today's implementation.
    """
    if (payload.get("activePackRefs") != [origin_bundle.descriptor.pack_ref]
            or payload.get("activeProfileRefs") != [origin_bundle.descriptor.profile_ref]):
        raise RuntimeBundleError(
            "historical ActiveArtifactSet lineage does not match its originating "
            "RuntimeBundle descriptor")
    origin_components = {
        (component.role, component.logical_ref): component
        for component in origin_bundle.components
    }
    stable = {
        "contract:": "CONTRACT_SCHEMA",
        "queryspec:": "QUERY_SPECIFICATION",
        "queryplan:": "QUERY_PLAN",
        "policy:": "PROFILE_POLICY",
        "manifest:": "ACTIVE_MANIFEST",
    }
    identities: set[tuple[str, str]] = set()
    for ref in payload.get("activeArtifactRefs", []):
        if not isinstance(ref, str):
            continue
        if ref.startswith("view:"):
            suffix = ref.split(":", 1)[1]
            identities.update({
                ("QUERY_SPECIFICATION", f"queryspec:{suffix}"),
                ("QUERY_PLAN", f"queryplan:{suffix}"),
                ("RUNTIME_CODE", "python:kernel/views.py"),
            })
            continue
        for prefix, role in stable.items():
            if ref.startswith(prefix):
                identities.add((role, ref))
                break
    for identity in sorted(identities):
        current = current_components.get(identity)
        origin = origin_components.get(identity)
        if current is None or origin is None or current != origin:
            raise RuntimeBundleError(
                f"historical ActiveArtifactSet stable ref {identity[1]!r} does not "
                "resolve to byte-identical components in its originating RuntimeBundle")


def _locked_components(package_root: Path) -> list[RuntimeComponent]:
    lock_path = package_root / "kernel" / LOCK_FILENAME
    try:
        from tooling.runtime_bundle_lock import (
            ROOT as CATALOG_ROOT,
            CatalogError,
            build_catalog,
            verify_lock_bytes,
        )
    except ImportError as exc:
        raise RuntimeBundleError(
            f"runtime component catalog verifier is unavailable: {exc}") from exc
    try:
        if Path(CATALOG_ROOT).resolve() != Path(package_root).resolve():
            raise CatalogError(
                "runtime catalog verifier is rooted at a different package tree")
        verify_lock_bytes(lock_path.read_bytes(), build_catalog())
    except (OSError, CatalogError) as exc:
        raise RuntimeBundleError(
            f"runtime component lock does not exactly match the code-owned catalog: {exc}"
        ) from exc
    _, lock = strict_json_bytes(lock_path)
    if lock.get("lockVersion") != LOCK_VERSION:
        raise RuntimeBundleError(
            f"unsupported runtime component lock version {lock.get('lockVersion')!r}")
    entries = lock.get("components")
    if not isinstance(entries, list) or not entries:
        raise RuntimeBundleError("runtime component lock must contain components")
    components = []
    seen = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {
            "role", "logicalRef", "path", "canonicalization", "sha256", "placement"
        }:
            raise RuntimeBundleError(f"malformed runtime component lock entry {index}")
        key = (entry["role"], entry["logicalRef"])
        if key in seen:
            raise RuntimeBundleError(f"duplicate runtime component lock entry {key!r}")
        seen.add(key)
        components.append(_component_from_path(
            package_root,
            role=entry["role"],
            logical_ref=entry["logicalRef"],
            path=package_root / entry["path"],
            canonicalization=entry["canonicalization"],
            expected_digest=entry["sha256"],
            expected_placement=entry["placement"],
        ))
    return components


def build_runtime_bundle(
    descriptor,
    *,
    additional_profile_payloads: Iterable[dict[str, Any]] = (),
    profile_origin_bundles: Mapping[str, RuntimeBundle] | None = None,
    additional_reference_payloads: Iterable[dict[str, Any]] = (),
    reference_data: Iterable[dict[str, Any]] = (),
    tenant_ref: str | None = None,
    _database_environment: dict[str, Any] | None = None,
    _profile_route_selection: dict[str, Any] | None = None,
    _observed_python_environment: dict[str, Any] | None = None,
    _selection_environment_seal: RuntimeEnvironmentSeal | None = None,
    _live_selection_proof: object | None = None,
) -> RuntimeBundle:
    """Build one immutable bundle from an explicit descriptor and trusted lock.

    `additional_reference_payloads` and `reference_data` are selected before
    construction (normally at startup under the bootstrap transaction).  A live
    bundle never consults them again; a changed selection requires a new bundle.
    """
    if tenant_ref is None:
        from . import config
        tenant_ref = config.TENANT_REF
    if not isinstance(tenant_ref, str) or not tenant_ref:
        raise RuntimeBundleError("runtime tenant ref must be non-empty")
    if _live_selection_proof not in {None, _LIVE_SELECTION_PROOF}:
        raise RuntimeBundleError("unknown RuntimeBundle live-selection authority")
    if ((_live_selection_proof is _LIVE_SELECTION_PROOF)
            != (type(_selection_environment_seal) is RuntimeEnvironmentSeal)):
        raise RuntimeBundleError(
            "live RuntimeBundle selection requires its exact import seal")
    profile_origin_bundles = profile_origin_bundles or {}
    package_root = Path(descriptor.profile_root).resolve().parent
    locked = _locked_components(package_root)
    component_map = {
        (component.role, component.logical_ref): component
        for component in locked
    }
    locked_keys = set(component_map)

    def add_component(component: RuntimeComponent) -> None:
        key = (component.role, component.logical_ref)
        prior = component_map.get(key)
        if prior is None:
            component_map[key] = component
            return
        if prior != component:
            raise RuntimeBundleError(
                f"locked runtime component {component.role}/{component.logical_ref} "
                "does not equal the selected canonical bytes")

    if _observed_python_environment is not None:
        if _live_selection_proof is not _LIVE_SELECTION_PROOF:
            raise RuntimeBundleError(
                "only live startup may supply a preverified Python environment")
        add_component(_runtime_environment_component_from_document(
            _observed_python_environment))
    else:
        add_component(observed_runtime_environment_component(
            package_root, tuple(component_map.values())))
    if _database_environment is not None:
        add_component(database_runtime_environment_component(
            _database_environment))
    if _profile_route_selection is not None:
        route_bytes = canonical_json(_profile_route_selection).encode("utf-8")
        add_component(RuntimeComponent(
            role="PROFILE_ROUTE_SELECTION",
            logical_ref=_PROFILE_ROUTE_SELECTION_REF,
            repository_path="runtime-selected/profile-route-selection",
            canonicalization=JSON_CANONICALIZATION,
            content_digest=sha256_bytes(route_bytes),
            canonical_bytes=route_bytes,
            placement=TENANT_CONTENT_PLACEMENT,
        ))

    add_component(_component_from_path(
        package_root,
        role="PROFILE_DESCRIPTOR",
        logical_ref=descriptor.profile_ref,
        path=descriptor.descriptor_path,
        canonicalization=JSON_CANONICALIZATION,
    ))
    add_component(_component_from_path(
        package_root,
        role="PROFILE_POLICY",
        logical_ref=descriptor.evidence_policy_ref,
        path=descriptor.evidence_policy_path,
        canonicalization=JSON_CANONICALIZATION,
    ))
    _assert_descriptor_matches_component(
        descriptor,
        component_map[("PROFILE_DESCRIPTOR", descriptor.profile_ref)],
        descriptor.profile_ref,
        descriptor.pack_ref,
    )

    instance_payloads: dict[str, tuple[dict[str, Any], Path]] = {}
    for path in descriptor.profile_instance_paths:
        canonical, payload = strict_json_bytes(Path(path))
        logical_ref = _profile_instance_ref(payload, Path(path))
        if logical_ref in instance_payloads:
            raise RuntimeBundleError(f"duplicate profile instance identifier {logical_ref!r}")
        instance_payloads[logical_ref] = (payload, Path(path))
        role = ("REFERENCE_SNAPSHOT" if "referenceSnapshotId" in payload
                else "PROFILE_INSTANCE")
        add_component(RuntimeComponent(
            role=role,
            logical_ref=logical_ref,
            repository_path=_repository_relative(package_root, Path(path)),
            canonicalization=JSON_CANONICALIZATION,
            content_digest=sha256_bytes(canonical),
            canonical_bytes=canonical,
            placement=component_placement(role, JSON_CANONICALIZATION, canonical),
        ))

    required_locked = {
        ("PROFILE_DESCRIPTOR", descriptor.profile_ref),
        ("PROFILE_POLICY", descriptor.evidence_policy_ref),
        *(("REFERENCE_SNAPSHOT" if "referenceSnapshotId" in payload
            else "PROFILE_INSTANCE", ref)
          for ref, (payload, _path) in instance_payloads.items()),
    }
    missing_locked = sorted(required_locked - locked_keys)
    if missing_locked:
        raise RuntimeBundleError(
            f"runtime component lock omits selected profile content: {missing_locked}")

    profile_history = list(additional_profile_payloads)
    deployed_code_binding_refs = {descriptor.code_binding_profile_ref}
    for payload in profile_history:
        if (isinstance(payload, dict)
                and payload.get("schemaVersion") == "ofarm.activeartifactset.v0.1"
                and payload.get("activePackRefs") == [descriptor.pack_ref]
                and payload.get("activeProfileRefs") == [descriptor.profile_ref]
                and payload.get("deploymentScope") == {
                    "scopeType": "TENANT", "scopeRef": tenant_ref}):
            deployed_code_binding_refs.update(
                ref for ref in payload.get("activeArtifactRefs", [])
                if isinstance(ref, str) and ref.startswith("codebindingprofile:"))

    for payload in profile_history:
        if not isinstance(payload, dict) or payload.get("schemaVersion") not in {
            "ofarm.activeartifactset.v0.1",
            "ofarm.packactivationset.v0.1",
            "ofarm.agronomiccodebindingprofile.v0.1",
        }:
            raise RuntimeBundleError(
                "additional selected profile spine row has an unsupported contract")
        logical_ref = _profile_instance_ref(payload, Path("database/profile-instance"))
        canonical = canonical_json(payload).encode("utf-8")
        prior = instance_payloads.get(logical_ref)
        if prior is not None:
            prior_component = component_map.get(("PROFILE_INSTANCE", logical_ref))
            if (prior_component is not None
                    and prior_component.placement == GLOBAL_CONTENT_PLACEMENT):
                raise RuntimeBundleError(
                    f"tenant-origin profile instance {logical_ref!r} collides with "
                    "an already selected global package identity")
            if canonical_json(prior[0]).encode("utf-8") != canonical:
                raise RuntimeBundleError(
                    f"profile instance identifier {logical_ref!r} is reused for "
                    "different canonical content")
            if (payload.get("schemaVersion") == "ofarm.activeartifactset.v0.1"
                    and _profile_spine_in_descriptor_lineage(
                        descriptor, payload, deployed_code_binding_refs, tenant_ref)):
                origin_bundle = profile_origin_bundles.get(logical_ref)
                if origin_bundle is None:
                    raise RuntimeBundleError(
                        f"ActiveArtifactSet {logical_ref!r} has no verified "
                        "originating RuntimeBundle")
                _validate_historical_artifact_origin(
                    payload, component_map, origin_bundle)
            continue
        if not _profile_spine_in_descriptor_lineage(
                descriptor, payload, deployed_code_binding_refs, tenant_ref):
            continue
        instance_payloads[logical_ref] = (
            copy.deepcopy(payload), Path(f"database/profile-instance/{logical_ref}"))
        add_component(RuntimeComponent(
            role="PROFILE_INSTANCE",
            logical_ref=logical_ref,
            repository_path=f"database/profile-instance/{logical_ref}",
            canonicalization=JSON_CANONICALIZATION,
            content_digest=sha256_bytes(canonical),
            canonical_bytes=canonical,
            placement=component_placement(
                "PROFILE_INSTANCE", JSON_CANONICALIZATION, canonical,
                f"database/profile-instance/{logical_ref}"),
        ))

        if payload.get("schemaVersion") == "ofarm.activeartifactset.v0.1":
            origin_bundle = profile_origin_bundles.get(logical_ref)
            if origin_bundle is None:
                raise RuntimeBundleError(
                    f"historical ActiveArtifactSet {logical_ref!r} has no verified "
                    "originating RuntimeBundle")
            _validate_historical_artifact_origin(
                payload, component_map, origin_bundle)

    selected_payloads = {
        ref: payload for ref, (payload, _path) in instance_payloads.items()
        if payload.get("schemaVersion") == "ofarm.referencesnapshot.v0.1"
    }
    family_prefixes = tuple(
        family.snapshot_prefix for family in descriptor.reference_families)
    for payload in additional_reference_payloads:
        if not isinstance(payload, dict) or payload.get("schemaVersion") != \
                "ofarm.referencesnapshot.v0.1":
            raise RuntimeBundleError("additional selected reference is not a ReferenceSnapshot")
        ref = payload.get("referenceSnapshotId")
        if not isinstance(ref, str) or not any(
                ref == prefix or ref.startswith(prefix + ".")
                for prefix in family_prefixes):
            # Store records outside this descriptor's declared reference
            # families are not selected runtime inputs for this bundle.
            continue
        canonical = canonical_json(payload).encode("utf-8")
        prior = selected_payloads.get(ref)
        if prior is not None:
            raise RuntimeBundleError(
                f"tenant-origin ReferenceSnapshot identifier {ref!r} collides with "
                "an already selected package identity")
        selected_payloads[ref] = copy.deepcopy(payload)
        if ref not in instance_payloads:
            add_component(RuntimeComponent(
                role="REFERENCE_SNAPSHOT",
                logical_ref=ref,
                repository_path=f"database/reference-snapshot/{ref}",
                canonicalization=JSON_CANONICALIZATION,
                content_digest=sha256_bytes(canonical),
                canonical_bytes=canonical,
                placement=TENANT_CONTENT_PLACEMENT,
            ))

    data_by_ref: dict[tuple[str, str], dict[str, Any]] = {}
    for row in reference_data:
        snapshot_ref = row.get("snapshot_ref")
        family = row.get("data_family")
        payload = row.get("payload")
        if snapshot_ref not in selected_payloads:
            continue
        if not isinstance(family, str) or not isinstance(payload, dict):
            raise RuntimeBundleError("selected reference-data row is malformed")
        canonical = canonical_json(payload).encode("utf-8")
        actual = sha256_bytes(canonical)
        if row.get("payload_sha256") != actual:
            raise RuntimeBundleError(
                f"reference data {snapshot_ref!r}/{family!r} payload digest mismatch")
        source_digest = row.get("source_digest")
        if source_digest is None or not _SHA256_RE.fullmatch(source_digest):
            raise RuntimeBundleError(
                f"reference data {snapshot_ref!r}/{family!r} has no full source digest")
        if source_digest != actual:
            raise RuntimeBundleError(
                f"reference data {snapshot_ref!r}/{family!r} does not retain the "
                "exact canonical bytes named by its source digest")
        key = (snapshot_ref, family)
        if key in data_by_ref:
            raise RuntimeBundleError(f"duplicate selected reference-data identity {key!r}")
        data_by_ref[key] = row
        add_component(RuntimeComponent(
            role="REFERENCE_DATA",
            logical_ref=f"{snapshot_ref}#{family}",
            repository_path=f"database/reference-data/{snapshot_ref}/{family}",
            canonicalization=JSON_CANONICALIZATION,
            content_digest=actual,
            canonical_bytes=canonical,
            placement=TENANT_CONTENT_PLACEMENT,
        ))

    _validate_selected_spine_scopes(instance_payloads, tenant_ref)
    _validate_active_artifact_refs(descriptor, instance_payloads, component_map)

    selected_references = []
    for snapshot_ref, payload in sorted(selected_payloads.items()):
        canonical = canonical_json(payload).encode("utf-8")
        source_refs = tuple(payload.get("sourceArtifactRefs", []))
        artifact_refs = [ref for ref in source_refs
                         if isinstance(ref, str) and ref.startswith("artifact:")]
        digest_refs = {ref for ref in source_refs
                       if isinstance(ref, str) and ref.startswith("digest:")}
        paired_digest_refs = set()
        for artifact_ref in artifact_refs:
            source_component = component_map.get(("REFERENCE_SOURCE", artifact_ref))
            if source_component is None:
                raise RuntimeBundleError(
                    f"selected source artifact {artifact_ref!r} has no locked bytes")
            expected_ref = f"digest:{source_component.content_digest}"
            if expected_ref not in source_refs:
                raise RuntimeBundleError(
                    f"selected source artifact {artifact_ref!r} is not paired with "
                    f"its full content identity {expected_ref!r}")
            paired_digest_refs.add(expected_ref)
        rows = [(family, row) for (ref, family), row in data_by_ref.items()
                if ref == snapshot_ref]
        if len(rows) > 1:
            raise RuntimeBundleError(
                f"ReferenceSnapshot {snapshot_ref!r} has multiple selected data families")
        family_row = rows[0] if rows else None
        if family_row:
            expected_source_ref = f"digest:{family_row[1]['source_digest']}"
            if expected_source_ref not in source_refs:
                raise RuntimeBundleError(
                    f"selected reference data {snapshot_ref!r}/{family_row[0]!r} "
                    f"is not paired with its source identity {expected_source_ref!r}")
            paired_digest_refs.add(expected_source_ref)
        if digest_refs != paired_digest_refs:
            raise RuntimeBundleError(
                f"selected ReferenceSnapshot {snapshot_ref!r} contains an unpaired "
                "or missing digest source identity")
        selected_references.append(SelectedReferenceIdentity(
            family_id=_family_for_snapshot(descriptor, snapshot_ref),
            snapshot_ref=snapshot_ref,
            snapshot_payload_digest=sha256_bytes(canonical),
            source_identities=source_refs,
            source_byte_status=("LOCKED" if artifact_refs or family_row
                                else "PROVENANCE_LOCATOR_ONLY"),
            unavailable_source_identities=tuple(
                ref for ref in source_refs
                if not (isinstance(ref, str) and (
                    ref.startswith("artifact:") or ref.startswith("digest:")))
            ),
            data_family=family_row[0] if family_row else None,
            data_payload_digest=(family_row[1]["payload_sha256"] if family_row else None),
            source_digest=(family_row[1].get("source_digest") if family_row else None),
        ))

    ordered_components = tuple(sorted(
        component_map.values(), key=lambda component: (component.role, component.logical_ref)))
    bundle_document = {
        "schemaVersion": BUNDLE_VERSION,
        "canonicalization": JSON_CANONICALIZATION,
        "tenantRef": tenant_ref,
        "profileRef": descriptor.profile_ref,
        "packRef": descriptor.pack_ref,
        "components": [component.identity_document() for component in ordered_components],
        "selectedReferenceIdentities": [
            reference.identity_document() for reference in selected_references
        ],
    }
    canonical_document = canonical_json(bundle_document).encode("utf-8")
    digest = sha256_bytes(canonical_document)
    selection_environment_seal = (
        replace(_selection_environment_seal, bundle_digest=digest)
        if _selection_environment_seal is not None else None
    )
    return RuntimeBundle(
        descriptor=descriptor,
        digest=digest,
        bundle_ref=f"runtimebundle:{digest}",
        canonical_document_bytes=canonical_document,
        components=ordered_components,
        selected_references=tuple(selected_references),
        construction_mode=(
            "LIVE_CURRENT" if _live_selection_proof is _LIVE_SELECTION_PROOF
            else "PERSISTED_AUDIT"),
        _selection_environment_seal=selection_environment_seal,
        _live_selection_proof=_live_selection_proof,
    )


def _build_live_runtime_bundle(descriptor, **kwargs) -> RuntimeBundle:
    """Internal startup path: mark only the under-lock selection as live."""
    if kwargs.get("_database_environment") is None:
        raise RuntimeBundleError(
            "live RuntimeBundle selection requires a PostgreSQL environment observation")
    if "_observed_python_environment" in kwargs:
        raise RuntimeBundleError(
            "caller-supplied Python environment observations are forbidden")
    package_root = Path(descriptor.profile_root).resolve().parent
    observed_python_environment = require_live_python_import_posture(package_root)
    selection_environment_seal = _capture_runtime_environment_seal(
        "", observed_python_environment)
    return build_runtime_bundle(
        descriptor,
        _observed_python_environment=observed_python_environment,
        _selection_environment_seal=selection_environment_seal,
        _live_selection_proof=_LIVE_SELECTION_PROOF,
        **kwargs,
    )


def runtime_bundle_from_persisted(
    descriptor=None,
    *,
    expected_digest: str,
    canonical_document_bytes: bytes,
    components: Iterable[RuntimeComponent],
    package_root: Path | None = None,
) -> RuntimeBundle:
    """Cold-load a bundle from immutable persisted bytes and verify everything."""
    try:
        document = _strict_json_value(
            canonical_document_bytes, "persisted RuntimeBundle document")
    except RuntimeBundleError as exc:
        raise RuntimeBundleError("persisted RuntimeBundle document is malformed") from exc
    if not isinstance(document, dict):
        raise RuntimeBundleError("persisted RuntimeBundle document must be an object")
    if canonical_json(document).encode("utf-8") != canonical_document_bytes:
        raise RuntimeBundleError("persisted RuntimeBundle document is not canonical")
    if set(document) != {
        "schemaVersion", "canonicalization", "tenantRef", "profileRef", "packRef",
        "components", "selectedReferenceIdentities",
    }:
        raise RuntimeBundleError("persisted RuntimeBundle document has unknown/missing fields")
    if document.get("schemaVersion") != BUNDLE_VERSION:
        raise RuntimeBundleError("persisted RuntimeBundle version is unsupported")
    if document.get("canonicalization") != JSON_CANONICALIZATION:
        raise RuntimeBundleError("persisted RuntimeBundle canonicalization is unsupported")
    if not _SHA256_RE.fullmatch(expected_digest):
        raise RuntimeBundleError("expected persisted RuntimeBundle digest is malformed")
    actual_digest = sha256_bytes(canonical_document_bytes)
    if actual_digest != expected_digest:
        raise RuntimeBundleError(
            f"persisted RuntimeBundle key/digest mismatch: expected {expected_digest}, "
            f"actual {actual_digest}")
    components = tuple(components)
    identities = [(component.role, component.logical_ref) for component in components]
    if len(identities) != len(set(identities)):
        raise RuntimeBundleError(
            "persisted RuntimeBundle supplied duplicate component identities")
    by_identity = {(component.role, component.logical_ref): component
                   for component in components}
    component_entries = document.get("components", [])
    if (not isinstance(component_entries, list)
            or any(not isinstance(entry, dict)
                   or set(entry) != {
                       "role", "logicalRef", "repositoryPath", "canonicalization",
                       "contentDigest", "byteLength", "placement"}
                   for entry in component_entries)):
        raise RuntimeBundleError("persisted RuntimeBundle component inventory is malformed")
    expected = {(entry["role"], entry["logicalRef"]): entry
                for entry in component_entries}
    if len(expected) != len(component_entries):
        raise RuntimeBundleError("persisted RuntimeBundle component inventory has duplicates")
    if set(by_identity) != set(expected):
        raise RuntimeBundleError("persisted RuntimeBundle component inventory is incomplete")
    for key, entry in expected.items():
        component = by_identity[key]
        if component.identity_document() != entry:
            raise RuntimeBundleError(
                f"persisted RuntimeBundle component identity mismatch for {key!r}")
    descriptor_component = by_identity.get(("PROFILE_DESCRIPTOR", document["profileRef"]))
    if descriptor_component is None:
        raise RuntimeBundleError("persisted RuntimeBundle lacks its profile descriptor")
    if descriptor is None:
        descriptor = descriptor_from_retained_component(
            descriptor_component,
            package_root=package_root or Path("."),
        )
    _assert_descriptor_matches_component(
        descriptor, descriptor_component, document["profileRef"], document["packRef"])

    reference_entries = document.get("selectedReferenceIdentities", [])
    if (not isinstance(reference_entries, list)
            or any(not isinstance(entry, dict) for entry in reference_entries)):
        raise RuntimeBundleError("persisted selected-reference inventory is malformed")
    allowed_reference_fields = {
        "familyId", "snapshotRef", "snapshotPayloadDigest", "sourceIdentities",
        "sourceByteStatus", "unavailableSourceIdentities", "dataFamily",
        "dataPayloadDigest", "sourceDigest",
    }
    required_reference_fields = {
        "familyId", "snapshotRef", "snapshotPayloadDigest", "sourceIdentities",
        "sourceByteStatus", "unavailableSourceIdentities",
    }
    if any(not required_reference_fields <= set(entry)
           or not set(entry) <= allowed_reference_fields
           for entry in reference_entries):
        raise RuntimeBundleError("persisted selected-reference entry is malformed")
    try:
        references = tuple(SelectedReferenceIdentity(
            family_id=entry["familyId"],
            snapshot_ref=entry["snapshotRef"],
            snapshot_payload_digest=entry["snapshotPayloadDigest"],
            source_identities=tuple(entry.get("sourceIdentities", [])),
            source_byte_status=entry["sourceByteStatus"],
            unavailable_source_identities=tuple(
                entry.get("unavailableSourceIdentities", [])),
            data_family=entry.get("dataFamily"),
            data_payload_digest=entry.get("dataPayloadDigest"),
            source_digest=entry.get("sourceDigest"),
        ) for entry in reference_entries)
    except (KeyError, TypeError) as exc:
        raise RuntimeBundleError(
            "persisted selected-reference entry is malformed") from exc
    return RuntimeBundle(
        descriptor=descriptor,
        digest=expected_digest,
        bundle_ref=f"runtimebundle:{expected_digest}",
        canonical_document_bytes=canonical_document_bytes,
        components=tuple(sorted(by_identity.values(), key=lambda c: (c.role, c.logical_ref))),
        selected_references=references,
        construction_mode="PERSISTED_AUDIT",
    )


def _assert_descriptor_matches_component(
    descriptor,
    component: RuntimeComponent,
    profile_ref: str,
    pack_ref: str,
) -> None:
    """Prove a caller descriptor is the retained descriptor, without live I/O."""
    if component.canonicalization != JSON_CANONICALIZATION:
        raise RuntimeBundleError("persisted profile descriptor is not canonical JSON")
    try:
        payload = _strict_json_value(
            component.canonical_bytes, "persisted profile descriptor")
    except RuntimeBundleError as exc:
        raise RuntimeBundleError("persisted profile descriptor bytes are malformed") from exc
    scalar_fields = {
        "descriptorVersion": descriptor.descriptor_version,
        "profileRef": descriptor.profile_ref,
        "packRef": descriptor.pack_ref,
        "packActivationSetRef": descriptor.pack_activation_set_ref,
        "activeArtifactSetRef": descriptor.active_artifact_set_ref,
        "codeBindingProfileRef": descriptor.code_binding_profile_ref,
        "evidencePolicyRef": descriptor.evidence_policy_ref,
        "contextSnapshotIdPrefix": descriptor.context_snapshot_id_prefix,
    }
    if any(payload.get(key) != value for key, value in scalar_fields.items()):
        raise RuntimeBundleError(
            "caller descriptor does not match retained PROFILE_DESCRIPTOR bytes")
    if descriptor.profile_ref != profile_ref or descriptor.pack_ref != pack_ref:
        raise RuntimeBundleError(
            "caller descriptor does not match persisted RuntimeBundle identity")
    if tuple(payload.get("profileInstanceFiles", [])) != descriptor.profile_instance_files:
        raise RuntimeBundleError(
            "caller descriptor profile-instance selection does not match retained bytes")
    try:
        policy_relative = descriptor.evidence_policy_path.resolve().relative_to(
            descriptor.profile_root.resolve()).as_posix()
        descriptor_relative = descriptor.descriptor_path.resolve().relative_to(
            descriptor.profile_root.resolve().parent).as_posix()
    except ValueError as exc:
        raise RuntimeBundleError("caller descriptor paths escape the package root") from exc
    if payload.get("evidencePolicyPath") != policy_relative:
        raise RuntimeBundleError(
            "caller descriptor policy path does not match retained bytes")
    if component.repository_path != descriptor_relative:
        raise RuntimeBundleError(
            "caller descriptor repository path does not match retained component")
    retained_families = payload.get("referenceFamilies", [])
    if not isinstance(retained_families, list) \
            or len(retained_families) != len(descriptor.reference_families):
        raise RuntimeBundleError(
            "caller descriptor reference-family selection does not match retained bytes")
    for retained, family in zip(retained_families, descriptor.reference_families):
        expected_family = {
            "familyId": family.family_id,
            "snapshotPrefix": family.snapshot_prefix,
            "dataFamily": family.data_family,
            "requiredForNowContext": family.required_for_now_context,
            "requiredForAsOfContext": family.required_for_as_of_context,
            "missingFamilyBehaviorNow": family.missing_family_behavior_now,
            "missingFamilyBehaviorAsOf": family.missing_family_behavior_as_of,
            "shippedSnapshotRef": family.shipped_snapshot_ref,
            "includeInContext": family.include_in_context,
        }
        if any((retained.get(key, True) if key == "includeInContext"
                else retained.get(key)) != value
               for key, value in expected_family.items()):
            raise RuntimeBundleError(
                "caller descriptor reference-family selection does not match "
                "retained PROFILE_DESCRIPTOR bytes")


def descriptor_from_retained_component(
    component: RuntimeComponent,
    *,
    package_root: Path,
):
    """Reconstruct a descriptor value from retained bytes without live reads."""
    from .profile_runtime import ProfileRuntimeDescriptor, ReferenceFamily

    if component.role != "PROFILE_DESCRIPTOR" \
            or component.canonicalization != JSON_CANONICALIZATION:
        raise RuntimeBundleError("retained descriptor component is malformed")
    try:
        payload = _strict_json_value(
            component.canonical_bytes, "retained profile descriptor")
    except RuntimeBundleError as exc:
        raise RuntimeBundleError("retained descriptor bytes are malformed") from exc
    descriptor_path = Path(package_root).resolve() / component.repository_path
    profile_root = descriptor_path.parent
    try:
        families = tuple(ReferenceFamily(
            family_id=item["familyId"],
            snapshot_prefix=item["snapshotPrefix"],
            data_family=item.get("dataFamily"),
            required_for_now_context=item["requiredForNowContext"],
            required_for_as_of_context=item["requiredForAsOfContext"],
            missing_family_behavior_now=item["missingFamilyBehaviorNow"],
            missing_family_behavior_as_of=item["missingFamilyBehaviorAsOf"],
            shipped_snapshot_ref=item.get("shippedSnapshotRef"),
            include_in_context=item.get("includeInContext", True),
        ) for item in payload["referenceFamilies"])
        instance_files = tuple(payload["profileInstanceFiles"])
        descriptor = ProfileRuntimeDescriptor(
            profile_root=profile_root,
            descriptor_path=descriptor_path,
            descriptor_version=payload["descriptorVersion"],
            profile_ref=payload["profileRef"],
            pack_ref=payload["packRef"],
            pack_activation_set_ref=payload["packActivationSetRef"],
            active_artifact_set_ref=payload["activeArtifactSetRef"],
            code_binding_profile_ref=payload["codeBindingProfileRef"],
            evidence_policy_ref=payload["evidencePolicyRef"],
            evidence_policy_path=profile_root / payload["evidencePolicyPath"],
            profile_instance_files=instance_files,
            profile_instance_paths=tuple(profile_root / name for name in instance_files),
            reference_families=families,
            context_snapshot_id_prefix=payload["contextSnapshotIdPrefix"],
        )
    except (KeyError, TypeError) as exc:
        raise RuntimeBundleError(
            f"retained profile descriptor is incomplete: {exc}") from exc
    _assert_descriptor_matches_component(
        descriptor, component, descriptor.profile_ref, descriptor.pack_ref)
    return descriptor
