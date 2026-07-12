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
import builtins
import dis
import functools
import hashlib
import io
import importlib.machinery
import importlib.metadata
import json
import locale
import math
import os
import operator
import platform
import re
import stat
import sys
import sysconfig
import time
import types
import zipfile
from dataclasses import InitVar, dataclass, field, fields as dataclass_fields, \
    is_dataclass, replace
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .contracts import canonical_json

BUNDLE_VERSION = "ofarm.runtime-bundle.local.v3"
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
_OBSERVED_ENVIRONMENT_REF = "environment:stable-runtime.v4"
_DECISION_SEMANTICS_REF = "environment:stable-decision-semantics.v1"
_OBSERVED_DATABASE_REF = "environment:observed-postgresql.v1"
_PROFILE_ROUTE_SELECTION_REF = "profile-route-selection:active"
_MISSING = object()


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
    decision_semantics: tuple[tuple[Any, ...], ...]
    decision_callable_anchors: tuple[tuple[types.FunctionType, types.CodeType], ...]
    decision_semantics_canonical: bytes
    pycache_prefix: str | None
    project_root: str


class RuntimeBundleError(RuntimeError):
    """Bundle content is absent, mutable, inconsistent, or unverifiable."""


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


class _FrozenRuntimeMapping(Mapping):
    """Closed immutable mapping that never delegates to a caller dictionary."""

    __slots__ = ("__items",)

    def __init__(self, items: tuple[tuple[object, object], ...]):
        if type(items) is not tuple or any(
                type(item) is not tuple or len(item) != 2 for item in items):
            raise TypeError("frozen runtime mapping requires exact item tuples")
        object.__setattr__(self, "_FrozenRuntimeMapping__items", items)

    def __setattr__(self, _name, _value):
        raise AttributeError("frozen runtime mapping is immutable")

    def __delattr__(self, _name):
        raise AttributeError("frozen runtime mapping cannot be deleted")

    def __getitem__(self, key):
        for retained_key, value in self.__items:
            if type(key) is type(retained_key) and key == retained_key:
                return value
        raise KeyError(key)

    def __iter__(self):
        return (item[0] for item in self.__items)

    def __len__(self):
        return len(self.__items)

    def __eq__(self, other):
        return (type(other) is _FrozenRuntimeMapping
                and _runtime_cache_state(self) == _runtime_cache_state(other))


def _freeze_runtime_cache(value):
    """Recursively freeze lookup state retained for one runtime lifetime.

    Runtime lookup indexes are intentionally private, but private dictionaries
    are still writable by any in-process collaborator. Mapping proxies, tuples,
    and frozensets make both indexes and retained JSON records immutable after
    preload instead of relying on callers to leave them alone.
    """
    if type(value) is dict:
        return _FrozenRuntimeMapping(tuple(
            (_freeze_runtime_cache(key), _freeze_runtime_cache(item))
            for key, item in value.items()
        ))
    if type(value) in {list, tuple}:
        return tuple(_freeze_runtime_cache(item) for item in value)
    if type(value) in {set, frozenset}:
        return frozenset(_freeze_runtime_cache(item) for item in value)
    if type(value) not in {type(None), bool, int, float, str, bytes}:
        raise RuntimeBundleError(
            f"runtime cache value has unsupported mutable type {type(value)!r}")
    return value


def _runtime_cache_state(value):
    """Return an exact primitive state; reject substituted behavioral values."""
    if type(value) is _FrozenRuntimeMapping:
        items = object.__getattribute__(
            value, "_FrozenRuntimeMapping__items")
        if type(items) is not tuple:
            raise RuntimeBundleError("frozen runtime mapping item state changed")
        return (
            "MAPPING",
            tuple(
                (_runtime_cache_state(key), _runtime_cache_state(item))
                for key, item in items
            ),
        )
    if type(value) is tuple:
        return ("TUPLE", tuple(_runtime_cache_state(item) for item in value))
    if type(value) is frozenset:
        states = [_runtime_cache_state(item) for item in value]
        return ("FROZENSET", tuple(sorted(states, key=repr)))
    if type(value) in {type(None), bool, int, float, str, bytes}:
        return (type(value).__name__, value)
    raise RuntimeBundleError(
        f"runtime cache contains substituted type {type(value)!r}")


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


def _mark_store_runtime_integrity_violation(store) -> None:
    """Make a caught runtime-integrity failure rollback-only.

    ``runtime_bundle`` cannot import ``Store`` without a cycle, so it invokes
    the exact class-defined one-way latch marker when present.  An integrity
    failure must still poison the active transaction when the caller catches
    the exception and restores the mutated state.
    """
    try:
        latch = object.__getattribute__(store, "_active_transaction_integrity")
        if latch is not None:
            object.__setattr__(
                latch, "_TransactionIntegrityLatch__poisoned", True)
    except Exception:
        # A malformed/non-Store consumer is rejected by the original check.
        # Never replace that useful error with a best-effort poison error.
        return


def _require_store_runtime_bundle(store, bundle, consumer: str) -> None:
    """Implement the exact Store/bundle comparison."""
    if bundle is None:
        raise RuntimeBundleError(
            f"{consumer} requires an explicit verified RuntimeBundle")
    try:
        bound = store.runtime_bundle
    except Exception as exc:
        raise RuntimeBundleError(
            f"{consumer} requires a Store bound to a verified RuntimeBundle") from exc
    if (bound is not bundle
            or bound.digest != bundle.digest
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


def require_store_runtime_bundle(store, bundle, consumer: str) -> None:
    """Prevent service evaluation under bytes different from Store receipts.

    A failure observed inside a governed transaction is sticky: restoring the
    mutated object and catching ``RuntimeBundleError`` cannot make that
    transaction eligible to commit.
    """
    try:
        _require_store_runtime_bundle(store, bundle, consumer)
    except RuntimeBundleError:
        _mark_store_runtime_integrity_violation(store)
        raise


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
    semantics_key = ("RUNTIME_ENVIRONMENT_OBSERVED", _DECISION_SEMANTICS_REF)
    database_key = ("RUNTIME_DATABASE_OBSERVED", _OBSERVED_DATABASE_REF)
    current_observed = observed_runtime_environment_component(
        package_root, bundle.components)
    selected_observed = actual.get(observed_key)
    if (selected_observed is None
            or selected_observed.repository_path != "runtime-observed/environment-v4"
            or selected_observed.canonicalization != JSON_CANONICALIZATION
            or selected_observed.placement != GLOBAL_CONTENT_PLACEMENT):
        raise RuntimeBundleError(
            "live RuntimeBundle environment observation provenance is invalid")
    current_environment = _strict_json_value(
        current_observed.canonical_bytes, "current runtime environment observation")
    selected_environment = _strict_json_value(
        selected_observed.canonical_bytes, "selected runtime environment observation")
    _validate_stable_runtime_environment_document(
        current_environment, bundle.components)
    _validate_stable_runtime_environment_document(
        selected_environment, bundle.components)
    if current_environment != selected_environment:
        raise RuntimeBundleError(
            "live RuntimeBundle does not match the currently observed runtime environment")
    current_semantics = observed_decision_semantics_component(package_root)
    selected_semantics = actual.get(semantics_key)
    if (selected_semantics is None
            or selected_semantics.repository_path !=
            "runtime-observed/decision-semantics-v1"
            or selected_semantics.canonicalization != JSON_CANONICALIZATION
            or selected_semantics.placement != GLOBAL_CONTENT_PLACEMENT):
        raise RuntimeBundleError(
            "live RuntimeBundle decision semantics provenance is invalid")
    selected_semantics_document = _strict_json_value(
        selected_semantics.canonical_bytes,
        "selected stable decision semantics identity")
    _validate_stable_decision_semantics_document(selected_semantics_document)
    if current_semantics != selected_semantics:
        raise RuntimeBundleError(
            "live RuntimeBundle does not match current decision semantics")
    if bundle.construction_mode == "LIVE_CURRENT" and database_key not in actual:
        raise RuntimeBundleError(
            "live RuntimeBundle omits its PostgreSQL environment observation")
    for key in sorted(set(actual) - set(expected)):
        component = actual[key]
        if key in {observed_key, semantics_key}:
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
        if (type(self.role) is not str
                or type(self.logical_ref) is not str
                or type(self.repository_path) is not str
                or type(self.canonicalization) is not str
                or type(self.content_digest) is not str
                or type(self.canonical_bytes) is not bytes
                or type(self.placement) is not str
                or not self.role or not self.logical_ref
                or not self.repository_path):
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
            or isinstance(entry.get("byteLength"), bool)
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


_NAMESPACE_MODULE_METADATA = {
    "__name__", "__doc__", "__package__", "__loader__", "__spec__",
    "__path__", "__file__", "__cached__", "__builtins__",
}


def _namespace_module_state_is_closed(name: str, module: object) -> bool:
    """Permit namespace metadata and exact imported child modules only."""
    if type(module) is not types.ModuleType:
        return False
    spec = getattr(module, "__spec__", None)
    package_paths = tuple(getattr(module, "__path__", ()))
    spec_paths = tuple(getattr(spec, "submodule_search_locations", ()) or ())
    if (type(spec) is not importlib.machinery.ModuleSpec
            or module.__name__ != name
            or getattr(module, "__package__", None) != name
            or getattr(module, "__doc__", None) is not None
            or getattr(module, "__file__", None) is not None
            or getattr(module, "__cached__", None) is not None
            or spec.name != name
            or spec.parent != name
            or spec.origin is not None
            or spec.has_location
            or module.__loader__ is not spec.loader
            or type(spec.loader) is not importlib.machinery.NamespaceLoader
            or not package_paths
            or package_paths != spec_paths):
        return False
    for attribute, value in vars(module).items():
        if attribute in _NAMESPACE_MODULE_METADATA:
            continue
        if (type(value) is not types.ModuleType
                or value.__name__ != f"{name}.{attribute}"
                or sys.modules.get(value.__name__) is not value):
            return False
    return True


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


_MAPPING_PROXY_TYPE = type(MappingProxyType({}))
_METHODCALLER_TYPE = type(operator.methodcaller("_ofarm_semantic_probe"))
_DECISION_DATA_ROOTS = (
    ("kernel.policy", (
        "COMMIT_CLASS_TO_FAMILY", "COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS",
        "COMMIT_CLASS_TO_ASSERTION_TYPE", "COMMIT_CLASS_TO_PROMOTION_TARGET",
        "PROMOTION_TARGET_TO_CONSEQUENCE_TYPE", "ACCEPTANCE_BY_ASSERTION_TYPE",
        "NON_COMMIT_ACTION_CLASSES", "REVIEW_ACTION_AUTHORITY", "ABSENT",
        "SELF_ACCEPTABLE_ASSERTION_TYPES", "CONSEQUENCE_SUBJECT_TYPES",
        "STRUCTURE_PAYLOAD_IDENTITY_TYPE", "STRUCTURE_PAYLOAD_REF_FIELDS",
        "STRUCTURE_REF_CATEGORY_KIND", "NON_COMMITABLE_SCOPE_TYPES",
        "NON_WHOLE_EXTENT_CLASSES", "ALLOWED_EXTENT_BOUND_KINDS",
        "EXTENT_CARRIER_USABLE_STATES", "EXTENT_CARRIER_DRIVEN_PROMOTIONS",
        "NON_PROMOTING_RETAIN_REASONS", "NON_PROMOTING_DEFAULT_REASON",
        "EVENT_TIME_PLAUSIBILITY_PAST_DAYS",
        "EVENT_TIME_PLAUSIBILITY_FUTURE_HOURS", "DOSE_SANITY_MAX",
        "UCUM_SCHEME_PREFIX", "COMPLIANCE_ASSERTED_STATUSES",
        "NEEDS_EVIDENCE_CODES", "ROUTE_REASON_TO_INSUFFICIENCY",
        "ROUTE_REASON_INSUFFICIENCY_DEFAULT", "USE_CLASS_TO_CANONICAL",
        "FRESHNESS_USE_POLICY",
    )),
    ("kernel.authority", ("_FARM_DESCENDANTS",)),
    ("kernel.contracts", ("_ID_FIELDS",)),
    ("kernel.profile_policy", (
        "INSUFFICIENCY_REASON_CODES", "DISPLAY_TEXT_FIELDS",
        "DISPLAY_TEMPLATE_FIELDS", "RULE_REF_RE", "VALIDATION_DISPOSITIONS",
        "PRODUCT_VALIDATION_BINDING_ROLE", "CROP_VALIDATION_BINDING_ROLE",
    )),
    ("kernel.sufficiency", ("BINDING_KIND", "OPERATION_FLOOR_CHECKS")),
    ("kernel.materializer", (
        "MATERIALIZATION_POLICY_REF", "RESULT_SHAPE_FAMILY",
        "IDENTITY_REGISTRY_SHAPE_FAMILY", "INVALIDATION_TRACE_KIND",
        "_TRIGGER_TO_RESULT_FAMILY", "RUNTIME_VERSION", "_USE_CLASS_MAP",
    )),
    ("kernel.context", (
        "PROFILE_INSTANCE_FILES", "SI_REGSR_FAMILY_ID", "SI_GERK_FAMILY_ID",
        "SI_REFERENCE_BINDINGS", "REGSR_SNAPSHOT_PREFIX", "GERK_SNAPSHOT_PREFIX",
        "REGSR_DATA_FAMILY", "_ACTIVE_PROFILE_REQUIRED_FIELDS",
    )),
    ("kernel.problems", ("REGISTERED_REASON_CODES",)),
    ("kernel.validators", ("_CONFIG_BACKED_POLICY",)),
)
_DECISION_FUNCTION_ROOTS = (
    ("re", ("_compile",)),
    ("rfc3339_validator", ("validate_rfc3339",)),
    ("kernel.policy", (
        "review_branch", "structure_self_acceptable", "is_resolved_ucum_unit",
        "revocation_disposition", "effective_freshness_requirement",
        "freshness_satisfied", "reuse_reason_summary",
    )),
    ("kernel.authority", ("_parse_dt", "_time_valid", "_revocation_effective")),
    ("kernel.validators", (
        "_refusal", "_validation_policy_refusal", "_validation_policy_or_refusal",
        "_assert_contained", "_assert_parent_scope_contained",
        "_in_force_structural_consequences_for", "_structure_target_identity",
        "_verified_product_binding", "_carrier_admits_bound",
        "_descriptor_recognized_rule_refs",
        "_operation_sequence_for_validation_policy",
    )),
    ("kernel.profile_policy", (
        "_require_text", "_validate_template", "_validate_rule_ref",
        "_require_bool", "_require_reason_code", "_require_disposition",
        "_require_object", "_reject_unknown_keys", "_validate_display",
        "_validate_validation_policy", "_validated_evidence_review_policy",
        "floor_item_rule_ref", "floor_item_insufficiency_reason_code",
        "floor_item_review_reason_code", "format_display_template",
        "format_validation_template",
    )),
    ("kernel.sufficiency", (
        "durable_evidence", "resolved_bindings", "recover_compliance_claim",
        "route_reasons_for", "build_case_from_checks", "build_floor_case",
        "build_floor_case_with_policy", "operation_advisories",
        "operation_advisories_with_policy", "build_acceptance_case",
        "amend_case_for_routing",
    )),
    ("kernel.emission", ("submission_evidence_refs",)),
    ("kernel.problems", ("runtime_problem",)),
    ("kernel.context", (
        "_build_runtime_bundle_for_bootstrap", "bootstrap_for_descriptor",
        "bootstrap",
    )),
    ("kernel.runtime_bundle", (
        "require_store_runtime_bundle", "require_current_runtime_catalog",
        "_require_decision_semantics", "require_runtime_environment_seal",
        "assert_runtime_environment_compatible",
    )),
)
_DECISION_CLASS_ROOTS = (
    ("kernel.contracts", ("Contract", "ContractRegistry")),
    ("kernel.authority", ("AuthorityDecision", "AuthorityEvaluator")),
    ("kernel.gates", ("GatePipeline",)),
    ("kernel.stages", (
        "GatePass", "GateRefusal", "GateReplay", "GateContext",
        "IngressNormalizer", "AuthorityGate", "EnvelopePersist",
        "ProfileApplicabilityGate", "EvidenceSufficiencyGate",
        "ReviewPromotionGate", "MaterializationGate",
    )),
    ("kernel.validators", (
        "TemporalConformanceValidator", "PromotionTargetValidator",
        "ScopeContainmentValidator", "SupersessionValidator",
        "GovernanceAcceptanceValidator", "ComplianceClaimValidator",
        "StructureCarrierValidator", "StructureSemanticsValidator",
        "CarrierSchemaValidator", "CarrierSemanticsValidator",
        "ExecutionExtentValidator", "ReferenceResolutionValidator",
        "ActorAttributionValidator", "CodeBindingValidator",
        "RegistryReverificationValidator", "CarrierStore", "ValidationGate",
    )),
    ("kernel.profile_policy", ("DescriptorPolicyProvider",)),
    ("kernel.emission", (
        "PromotionEmitter", "PromotionTraceWriter", "ReplayWriter")),
    ("kernel.context", (
        "SIReferenceBindings", "ProductRegister", "ContextAssembler")),
    ("kernel.materializer", ("Materializer",)),
    ("kernel.store", ("Store",)),
    ("kernel.runtime_bundle", (
        "RuntimeEnvironmentSeal", "RuntimeComponent",
        "SelectedReferenceIdentity", "RuntimeBundle",
    )),
)
_DECISION_OPTIONAL_FUNCTION_ROOTS = (
    ("kernel.profiles.si_ffs.si_bindings", (
        "_evidence_ok", "_evidence_refused", "_scheme_version", "_binding",
        "_locator_lookup", "resolve_product_authorisation", "resolve_parcel",
        "_ffsnaprave_lookup", "resolve_equipment", "_unresolved",
        "resolve_holding", "resolve_operator",
    )),
    ("kernel.profiles.si_ffs.regsr_adapter", (
        "import_regsr_snapshot", "regsr_lookup",
        "verify_product_authorisation",
    )),
    ("kernel.profiles.si_ffs.gerk_adapter", ("import_gerk_snapshot",)),
    ("kernel.profiles.si_ffs.ffsnaprave_adapter", (
        "import_ffsnaprave_snapshot", "attach_inspection_evidence",
    )),
)
_DECISION_OPTIONAL_CLASS_ROOTS = (
    ("kernel.views", ("OutputGenerator",)),
    ("kernel.adapters", ("ParseResult", "ImportRunner")),
    ("kernel.auth_oidc", ("OidcError", "OidcConfig")),
    ("kernel.profiles.si_ffs.gerk_adapter", ("GerkLayer",)),
    ("kernel.profiles.si_ffs.ffsnaprave_adapter", ("FFSNapraveRegister",)),
)
_DECISION_SEQUENCE_ROOTS = (
    ("kernel.gates", "CHAIN"),
    ("kernel.validators", "COMMON_SEQUENCE"),
    ("kernel.validators", "OPERATION_SEQUENCE"),
)


def _decision_semantic_root_module_names() -> tuple[str, ...]:
    """Return the complete declared module inventory that must be preloaded.

    Semantic capture is intentionally import-free: a missing required module
    is an integrity error, and an optional root is sealed only when its module
    was selected before activation.  Bootstrap therefore uses this inventory
    to make that selection explicit and deterministic before constructing the
    RuntimeBundle.
    """
    root_groups = (
        _DECISION_DATA_ROOTS,
        _DECISION_FUNCTION_ROOTS,
        _DECISION_CLASS_ROOTS,
        _DECISION_OPTIONAL_FUNCTION_ROOTS,
        _DECISION_OPTIONAL_CLASS_ROOTS,
        _DECISION_SEQUENCE_ROOTS,
    )
    return tuple(sorted({
        module_name
        for group in root_groups
        for module_name, _names in group
    }))


_DECISION_EXTERNAL_MODULE_PREFIXES = (
    "calendar", "copy", "jsonschema", "referencing", "rpds",
    "rfc3339_validator", "idna",
)
_PROCESS_LOCAL_DECISION_MODULES = {"os", "threading"}


def _stable_decision_namespace(module_name: str) -> bool:
    if module_name in _PROCESS_LOCAL_DECISION_MODULES:
        return False
    if (module_name == "kernel" or module_name.startswith("kernel.")
            or any(module_name == prefix or module_name.startswith(prefix + ".")
                   for prefix in _DECISION_EXTERNAL_MODULE_PREFIXES)):
        return True
    # Mutable Python helper code remains decision semantics even when it lives
    # in the standard library or a locked wheel.  Follow every already-loaded
    # source-backed helper reachable from a declared root; native/builtin
    # objects have immutable executable bytes and are retained by exact object
    # identity instead.
    module = sys.modules.get(module_name)
    if type(module) is not types.ModuleType:
        return False
    origin = getattr(module, "__file__", None)
    return isinstance(origin, str) and Path(origin).suffix in {".py", ".pyw"}


_RE_PURGE = re.purge
_RE_PURGE_CODE = re.purge.__code__


def _prepare_decision_semantic_caches() -> None:
    """Reset derived caches whose contents must never become decision input."""
    if (re.purge is not _RE_PURGE
            or _RE_PURGE.__code__ is not _RE_PURGE_CODE):
        raise RuntimeBundleError("regex cache reset semantics changed after import")
    for name in ("_cache", "_cache2"):
        cache = vars(re).get(name, _MISSING)
        if cache is not _MISSING and type(cache) is not dict:
            raise RuntimeBundleError("regex cache structure is not exact")
    _RE_PURGE()
    if any(vars(re).get(name) for name in ("_cache", "_cache2")):
        raise RuntimeBundleError("regex cache reset did not produce an empty cache")


def _freeze_semantic_value(value: Any, active: set[int] | None = None) -> tuple:
    """Copy declared semantic state while retaining exact container identity."""
    if active is None:
        active = set()
    if value is None or type(value) in {bool, int, str, bytes}:
        return ("SCALAR", type(value), value)
    if type(value) is float:
        if not math.isfinite(value):
            label = "NAN" if math.isnan(value) else (
                "POSITIVE_INFINITY" if value > 0 else "NEGATIVE_INFINITY")
            return ("NONFINITE_FLOAT", float, label)
        return ("SCALAR", float, value)
    if isinstance(value, Path):
        return ("PATH", type(value), value, str(value))
    if isinstance(value, re.Pattern):
        return ("REGEX", type(value), value, value.pattern, value.flags)
    if type(value) is _METHODCALLER_TYPE:
        reduced = value.__reduce__()
        return (
            "METHODCALLER", type(value), value,
            _freeze_semantic_value(reduced[1], active),
        )
    if type(value) is types.FunctionType:
        return ("CALLABLE", value, _semantic_function_state(value))
    if isinstance(value, Mapping):
        marker = id(value)
        if marker in active:
            raise RuntimeBundleError("decision semantics contain a mapping cycle")
        active.add(marker)
        try:
            items = sorted(
                value.items(),
                key=lambda item: (
                    type(item[0]).__module__, type(item[0]).__qualname__,
                    repr(item[0]),
                ),
            )
            return (
                "MAPPING", type(value), value,
                tuple((_freeze_semantic_value(key, active),
                       _freeze_semantic_value(item, active))
                      for key, item in items),
            )
        finally:
            active.remove(marker)
    if type(value) in {list, tuple}:
        marker = id(value)
        if marker in active:
            raise RuntimeBundleError("decision semantics contain a sequence cycle")
        active.add(marker)
        try:
            return (
                "SEQUENCE", type(value), value,
                tuple(_freeze_semantic_value(item, active) for item in value),
            )
        finally:
            active.remove(marker)
    if type(value) in {set, frozenset}:
        marker = id(value)
        if marker in active:
            raise RuntimeBundleError("decision semantics contain a set cycle")
        active.add(marker)
        try:
            ordered = sorted(
                value,
                key=lambda item: (
                    type(item).__module__, type(item).__qualname__, repr(item)),
            )
            return (
                "SET", type(value), value,
                tuple(_freeze_semantic_value(item, active) for item in ordered),
            )
        finally:
            active.remove(marker)
    if isinstance(value, (type, types.ModuleType)):
        return ("IDENTITY", value)
    object_fields: list[tuple[str, Any]] = []
    if is_dataclass(value):
        object_fields.extend(
            (item.name, getattr(value, item.name))
            for item in dataclass_fields(value)
        )
    else:
        namespace = getattr(value, "__dict__", None)
        if isinstance(namespace, Mapping):
            object_fields.extend(
                (name, item) for name, item in namespace.items()
                if isinstance(name, str)
            )
        slots = {
            name
            for class_object in type(value).__mro__
            for name in (
                (class_object.__slots__,)
                if isinstance(getattr(class_object, "__slots__", ()), str)
                else getattr(class_object, "__slots__", ())
            )
            if isinstance(name, str) and name not in {"__dict__", "__weakref__"}
        }
        known = {name for name, _item in object_fields}
        object_fields.extend(
            (name, getattr(value, name))
            for name in sorted(slots - known)
            if hasattr(value, name)
        )
    if object_fields:
        marker = id(value)
        if marker in active:
            raise RuntimeBundleError("decision semantics contain an object cycle")
        active.add(marker)
        try:
            return (
                "OBJECT", type(value), value,
                tuple(
                    (name, _freeze_semantic_value(item, active))
                    for name, item in sorted(object_fields)
                ),
            )
        finally:
            active.remove(marker)
    return ("IDENTITY", value)


def _same_semantic_value(
        current: tuple,
        prior: tuple,
        *,
        require_container_identity: bool = True,
) -> bool:
    if current[0] != prior[0]:
        return False
    if current[0] == "NONFINITE_FLOAT":
        return current[1:] == prior[1:]
    if current[0] == "SCALAR":
        return current[1] is prior[1] and current[2] == prior[2]
    if current[0] == "IDENTITY":
        return current[1] is prior[1]
    if current[0] == "PATH":
        return (current[1] is prior[1]
                and (not require_container_identity
                     or current[2] is prior[2])
                and current[3] == prior[3])
    if current[0] == "REGEX":
        return (current[1] is prior[1]
                and (not require_container_identity
                     or current[2] is prior[2])
                and current[3:] == prior[3:])
    if current[0] == "METHODCALLER":
        return (current[1] is prior[1] and current[2] is prior[2]
                and _same_semantic_value(
                    current[3], prior[3], require_container_identity=False))
    if current[0] == "CALLABLE":
        return (current[1] is prior[1]
                and _same_semantic_function(current[2], prior[2]))
    if (current[1] is not prior[1]
            or (require_container_identity and current[2] is not prior[2])):
        return False
    if len(current[3]) != len(prior[3]):
        return False
    if current[0] == "MAPPING":
        return all(
            _same_semantic_value(
                current_key, prior_key,
                require_container_identity=require_container_identity)
            and _same_semantic_value(
                current_value, prior_value,
                require_container_identity=require_container_identity)
            for (current_key, current_value), (prior_key, prior_value)
            in zip(current[3], prior[3])
        )
    if current[0] == "OBJECT":
        return all(
            current_name == prior_name
            and _same_semantic_value(
                current_value, prior_value,
                require_container_identity=require_container_identity)
            for (current_name, current_value), (prior_name, prior_value)
            in zip(current[3], prior[3])
        )
    return all(
        _same_semantic_value(
            current_item, prior_item,
            require_container_identity=require_container_identity)
        for current_item, prior_item in zip(current[3], prior[3])
    )


def _semantic_function_state(function: object) -> tuple:
    if type(function) is not types.FunctionType:
        return ("IDENTITY", function)
    closure = function.__closure__ or ()
    return (
        "FUNCTION", function, function.__code__,
        function.__defaults__, _freeze_semantic_value(function.__defaults__),
        function.__kwdefaults__, _freeze_semantic_value(function.__kwdefaults__),
        tuple((cell, _freeze_semantic_value(cell.cell_contents)) for cell in closure),
        function.__annotations__, _freeze_semantic_value(function.__annotations__),
        function.__dict__, _freeze_semantic_value(function.__dict__),
        function.__module__, function.__name__, function.__qualname__,
    )


def _same_semantic_function(current: tuple, prior: tuple) -> bool:
    if current[0] != prior[0]:
        return False
    if current[0] == "IDENTITY":
        return current[1] is prior[1]
    if any(current[index] is not prior[index] for index in (1, 2, 3, 5, 8, 10)):
        return False
    if not all(_same_semantic_value(current[index], prior[index])
               for index in (4, 6, 9, 11)):
        return False
    if current[12:] != prior[12:]:
        return False
    if len(current[7]) != len(prior[7]):
        return False
    return all(
        current_cell is prior_cell
        and _same_semantic_value(current_value, prior_value)
        for (current_cell, current_value), (prior_cell, prior_value)
        in zip(current[7], prior[7])
    )


def _semantic_descriptor_functions(descriptor: object) -> tuple[tuple[str, object], ...]:
    if type(descriptor) is types.FunctionType:
        return (("function", descriptor),)
    if type(descriptor) in {classmethod, staticmethod}:
        return (("descriptor", descriptor.__func__),)
    if type(descriptor) is property:
        return tuple(
            (name, function) for name, function in (
                ("get", descriptor.fget), ("set", descriptor.fset),
                ("delete", descriptor.fdel),
            ) if function is not None
        )
    return ()


def _semantic_class_state(class_object: type) -> tuple:
    descriptors = []
    data = []
    for name, descriptor in sorted(vars(class_object).items()):
        functions = _semantic_descriptor_functions(descriptor)
        if functions:
            descriptors.append((
                name,
                descriptor,
                tuple((kind, _semantic_function_state(function))
                      for kind, function in functions),
            ))
        elif not name.startswith("__"):
            data.append((
                name, descriptor, _freeze_semantic_value(descriptor)))
    base_states = tuple(
        (base, _semantic_class_state(base))
        for base in class_object.__bases__
        if _stable_decision_namespace(base.__module__)
    )
    return (
        class_object, tuple(class_object.__mro__), tuple(descriptors),
        tuple(data), class_object.__module__, class_object.__name__,
        class_object.__qualname__, base_states,
    )


def _same_semantic_class(current: tuple, prior: tuple) -> bool:
    if current[0] is not prior[0] or len(current[1]) != len(prior[1]):
        return False
    if any(current_item is not prior_item
           for current_item, prior_item in zip(current[1], prior[1])):
        return False
    if len(current[2]) != len(prior[2]):
        return False
    for current_entry, prior_entry in zip(current[2], prior[2]):
        if (current_entry[0] != prior_entry[0]
                or current_entry[1] is not prior_entry[1]
                or len(current_entry[2]) != len(prior_entry[2])):
            return False
        for (current_kind, current_function), (prior_kind, prior_function) in zip(
                current_entry[2], prior_entry[2]):
            if (current_kind != prior_kind
                    or not _same_semantic_function(
                        current_function, prior_function)):
                return False
    if len(current[3]) != len(prior[3]):
        return False
    for current_entry, prior_entry in zip(current[3], prior[3]):
        if (current_entry[0] != prior_entry[0]
                or current_entry[1] is not prior_entry[1]
                or not _same_semantic_value(
                    current_entry[2], prior_entry[2])):
            return False
    if current[4:7] != prior[4:7] or len(current[7]) != len(prior[7]):
        return False
    return all(
        current_base is prior_base
        and _same_semantic_class(current_state, prior_state)
        for (current_base, current_state), (prior_base, prior_state)
        in zip(current[7], prior[7])
    )


def _semantic_sequence_state(sequence: object) -> tuple:
    if type(sequence) is not tuple:
        raise RuntimeBundleError("decision dispatch sequence is not an exact tuple")
    items = []
    for item in sequence:
        namespace = getattr(item, "__dict__", None)
        items.append((
            item,
            type(item),
            namespace,
            _freeze_semantic_value(namespace),
            _semantic_class_state(type(item)),
        ))
    return (sequence, tuple(items))


def _same_semantic_sequence(current: tuple, prior: tuple) -> bool:
    if current[0] is not prior[0] or len(current[1]) != len(prior[1]):
        return False
    for current_item, prior_item in zip(current[1], prior[1]):
        if any(current_item[index] is not prior_item[index]
               for index in (0, 1, 2)):
            return False
        if (not _same_semantic_value(current_item[3], prior_item[3])
                or not _same_semantic_class(current_item[4], prior_item[4])):
            return False
    return True


def _decision_semantic_module(module_name: str) -> types.ModuleType:
    module = sys.modules.get(module_name)
    if type(module) is not types.ModuleType:
        raise RuntimeBundleError(
            f"decision semantic module was not preloaded: {module_name}")
    return module


def _semantic_binding_state(
        value: object, owner: types.ModuleType | None = None) -> tuple:
    if value is _MISSING:
        return ("ABSENT",)
    if type(value) is types.ModuleType:
        return ("MODULE", value, value.__name__)
    if type(value) is types.FunctionType:
        return ("FUNCTION", _semantic_function_state(value))
    if isinstance(value, type):
        return ("CLASS", _semantic_class_state(value))
    if owner is not None and not _stable_decision_namespace(owner.__name__):
        return ("IDENTITY_DATA", value, type(value))
    return ("DATA", _freeze_semantic_value(value))


def _same_semantic_binding(current: tuple, prior: tuple) -> bool:
    if current[0] != prior[0]:
        return False
    if current[0] == "ABSENT":
        return True
    if current[0] == "MODULE":
        return current[1] is prior[1] and current[2] == prior[2]
    if current[0] == "FUNCTION":
        return _same_semantic_function(current[1], prior[1])
    if current[0] == "CLASS":
        return _same_semantic_class(current[1], prior[1])
    if current[0] == "IDENTITY_DATA":
        return current[1] is prior[1] and current[2] is prior[2]
    return _same_semantic_value(current[1], prior[1])


def _nested_code_objects(code: types.CodeType) -> tuple[types.CodeType, ...]:
    nested = [code]
    for constant in code.co_consts:
        if isinstance(constant, types.CodeType):
            nested.extend(_nested_code_objects(constant))
    return tuple(nested)


def _semantic_module_import_name(module: types.ModuleType) -> str:
    """Return the live ``sys.modules`` key, not a mutable display name.

    CPython's frozen ``_collections_abc`` deliberately reports
    ``module.__name__ == 'collections.abc'`` even though its real import key
    (and ``__spec__.name``) is ``_collections_abc``.  Runtime lifetime checks
    must retain the actual import-table binding or a clean capture rejects
    itself immediately.
    """
    spec = getattr(module, "__spec__", None)
    spec_name = getattr(spec, "name", None)
    if type(spec_name) is str:
        return spec_name
    names = sorted(
        name for name, selected in sys.modules.items()
        if selected is module
    )
    if not names:
        raise RuntimeBundleError(
            "decision semantic module has no live import-table binding")
    return names[0]


def _semantic_function_module(function: types.FunctionType) -> types.ModuleType | None:
    module_name = function.__globals__.get("__name__")
    module = sys.modules.get(module_name)
    if type(module) is types.ModuleType and vars(module) is function.__globals__:
        return module
    for candidate in sys.modules.values():
        if (type(candidate) is types.ModuleType
                and vars(candidate) is function.__globals__):
            return candidate
    return None


def _referenced_module_attributes(
        function: types.FunctionType,
) -> tuple[tuple[types.ModuleType, str], ...]:
    """Return immediate module attributes loaded by this function's bytecode."""
    references: dict[tuple[str, str], tuple[types.ModuleType, str]] = {}
    namespace = function.__globals__
    for code in _nested_code_objects(function.__code__):
        instructions = tuple(dis.get_instructions(code))
        for index, instruction in enumerate(instructions):
            if instruction.opname != "LOAD_GLOBAL":
                continue
            owner = namespace.get(instruction.argval)
            for following in instructions[index + 1:]:
                if (following.opname not in {"LOAD_ATTR", "LOAD_METHOD"}
                        or not isinstance(following.argval, str)):
                    break
                if type(owner) is types.ModuleType:
                    key = (
                        _semantic_module_import_name(owner), following.argval)
                    references[key] = (owner, following.argval)
                try:
                    owner = getattr(owner, following.argval)
                except (AttributeError, TypeError):
                    break
    return tuple(references[key] for key in sorted(references))


def _semantic_class_functions(class_state: tuple) -> tuple[types.FunctionType, ...]:
    direct = tuple(
        function_state[1]
        for _name, _descriptor, functions in class_state[2]
        for _kind, function_state in functions
        if function_state[0] == "FUNCTION"
    )
    inherited = tuple(
        function
        for _base, base_state in class_state[7]
        for function in _semantic_class_functions(base_state)
    )
    return direct + inherited


def _capture_decision_semantics() -> tuple[tuple[Any, ...], ...]:
    """Capture declared roots plus their exact runtime global-binding closure."""
    _prepare_decision_semantic_caches()
    entries: list[tuple[Any, ...]] = []
    explicit: set[tuple[int, str]] = set()
    pending_functions: list[types.FunctionType] = []
    pending_classes: list[type] = []
    pending_identity_classes: list[type] = []

    def append_entry(kind, label, module, name, value, state) -> None:
        entries.append((
            kind, label, module, _semantic_module_import_name(module),
            name, value, state,
        ))
        explicit.add((id(module), name))

    def enqueue_function(function: object) -> None:
        if (type(function) is types.FunctionType
                and _semantic_function_module(function) is not None):
            pending_functions.append(function)

    def enqueue_class(class_object: object) -> None:
        if (isinstance(class_object, type)
                and _stable_decision_namespace(class_object.__module__)):
            pending_classes.append(class_object)

    def enqueue_identity_class(class_object: object) -> None:
        """Capture a reached class body without expanding every helper global.

        Exact class objects stored inside semantic data (notably psycopg's
        private adapter registry) are executable choices. Their complete class
        state, bases, descriptors, and callable states must be sealed. Following
        every global referenced by every third-party method, however, pulls in
        non-decision logging registries and other cyclic process state. The
        class state already retains each method/default/data callable exactly;
        ordinary declared function/class roots continue to receive the full
        transitive global-binding walk.
        """
        if (isinstance(class_object, type)
                and _stable_decision_namespace(class_object.__module__)):
            pending_identity_classes.append(class_object)

    def enqueue_value_state(state: tuple) -> None:
        kind = state[0]
        if kind == "CALLABLE":
            enqueue_function(state[1])
        elif kind == "MAPPING":
            for key_state, value_state in state[3]:
                enqueue_value_state(key_state)
                enqueue_value_state(value_state)
        elif kind in {"SEQUENCE", "SET"}:
            for item_state in state[3]:
                enqueue_value_state(item_state)
        elif kind == "OBJECT":
            enqueue_class(state[1])
            for _name, item_state in state[3]:
                enqueue_value_state(item_state)
        elif kind == "METHODCALLER":
            enqueue_value_state(state[3])
        elif kind == "IDENTITY":
            value = state[1]
            if isinstance(value, type):
                enqueue_identity_class(value)

    def enqueue_function_state(state: tuple) -> None:
        if state[0] != "FUNCTION":
            return
        for value_state in (state[4], state[6], state[9], state[11]):
            enqueue_value_state(value_state)
        for _cell, value_state in state[7]:
            enqueue_value_state(value_state)

    def enqueue_class_state(state: tuple) -> None:
        for function in _semantic_class_functions(state):
            enqueue_function(function)
        for _name, _value, value_state in state[3]:
            enqueue_value_state(value_state)
        for _base, base_state in state[7]:
            enqueue_class_state(base_state)

    for module_name, names in _DECISION_DATA_ROOTS:
        module = _decision_semantic_module(module_name)
        for name in names:
            value = vars(module).get(name, _MISSING)
            if value is _MISSING:
                raise RuntimeBundleError(
                    f"decision semantic data root is absent: {module_name}.{name}")
            state = _freeze_semantic_value(value)
            append_entry(
                "DATA", f"{module_name}.{name}", module, name, value,
                state,
            )
            enqueue_value_state(state)
    for module_name, names in _DECISION_FUNCTION_ROOTS:
        module = _decision_semantic_module(module_name)
        for name in names:
            function = vars(module).get(name, _MISSING)
            if type(function) is not types.FunctionType:
                raise RuntimeBundleError(
                    f"decision semantic function is absent: {module_name}.{name}")
            state = _semantic_function_state(function)
            append_entry(
                "FUNCTION", f"{module_name}.{name}", module, name, function,
                state,
            )
            enqueue_function(function)
    for module_name, names in _DECISION_OPTIONAL_FUNCTION_ROOTS:
        module = sys.modules.get(module_name)
        if module is None:
            continue
        if type(module) is not types.ModuleType:
            raise RuntimeBundleError(
                f"optional decision semantic module is malformed: {module_name}")
        for name in names:
            function = vars(module).get(name, _MISSING)
            if type(function) is not types.FunctionType:
                raise RuntimeBundleError(
                    f"decision semantic function is absent: {module_name}.{name}")
            state = _semantic_function_state(function)
            append_entry(
                "FUNCTION", f"{module_name}.{name}", module, name, function,
                state,
            )
            enqueue_function(function)
    for module_name, names in _DECISION_CLASS_ROOTS:
        module = _decision_semantic_module(module_name)
        for name in names:
            class_object = vars(module).get(name, _MISSING)
            if not isinstance(class_object, type):
                raise RuntimeBundleError(
                    f"decision semantic class is absent: {module_name}.{name}")
            state = _semantic_class_state(class_object)
            append_entry(
                "CLASS", f"{module_name}.{name}", module, name, class_object,
                state,
            )
            enqueue_class_state(state)
    for module_name, names in _DECISION_OPTIONAL_CLASS_ROOTS:
        module = sys.modules.get(module_name)
        if module is None:
            continue
        if type(module) is not types.ModuleType:
            raise RuntimeBundleError(
                f"optional decision semantic module is malformed: {module_name}")
        for name in names:
            class_object = vars(module).get(name, _MISSING)
            if not isinstance(class_object, type):
                raise RuntimeBundleError(
                    f"decision semantic class is absent: {module_name}.{name}")
            state = _semantic_class_state(class_object)
            append_entry(
                "CLASS", f"{module_name}.{name}", module, name, class_object,
                state,
            )
            enqueue_class_state(state)
    for module_name, name in _DECISION_SEQUENCE_ROOTS:
        module = _decision_semantic_module(module_name)
        sequence = vars(module).get(name, _MISSING)
        state = _semantic_sequence_state(sequence)
        append_entry(
            "SEQUENCE", f"{module_name}.{name}", module, name, sequence,
            state,
        )
        for item in state[1]:
            enqueue_value_state(item[3])
            enqueue_class_state(item[4])

    captured_functions: set[int] = set()
    captured_classes: set[int] = set()
    captured_identity_classes: set[int] = set()
    while pending_functions or pending_classes or pending_identity_classes:
        if pending_identity_classes:
            class_object = pending_identity_classes.pop()
            if id(class_object) in captured_identity_classes:
                continue
            captured_identity_classes.add(id(class_object))
            module = sys.modules.get(class_object.__module__)
            if type(module) is not types.ModuleType:
                raise RuntimeBundleError(
                    "decision semantic identity class module disappeared while "
                    f"sealing: {class_object.__module__}."
                    f"{class_object.__qualname__}")
            name = class_object.__name__
            key = (id(module), name)
            if vars(module).get(name) is class_object and key not in explicit:
                append_entry(
                    "BINDING",
                    f"{_semantic_module_import_name(module)}.{name}",
                    module, name, class_object,
                    ("CLASS", _semantic_class_state(class_object)),
                )
            elif vars(module).get(name) is not class_object:
                # Psycopg creates exact adapter classes dynamically and keeps
                # them only inside its adapter maps.  Their ``__module__`` and
                # ``__name__`` describe provenance but do not create a module
                # binding, so a binding-only seal would silently omit their
                # mutable class bodies.  Retain the object itself and compare
                # its complete class state for the runtime lifetime.
                label_bytes = canonical_json({
                    "module": class_object.__module__,
                    "name": class_object.__name__,
                    "qualname": class_object.__qualname__,
                }).encode("utf-8")
                entries.append((
                    "IDENTITY_CLASS",
                    "identity_class.class_" +
                    hashlib.sha256(label_bytes).hexdigest(),
                    module,
                    _semantic_module_import_name(module),
                    name,
                    class_object,
                    _semantic_class_state(class_object),
                ))
            continue
        if pending_classes:
            class_object = pending_classes.pop()
            if id(class_object) in captured_classes:
                continue
            captured_classes.add(id(class_object))
            module = sys.modules.get(class_object.__module__)
            if type(module) is not types.ModuleType:
                raise RuntimeBundleError(
                    "decision semantic class module disappeared while sealing: "
                    f"{class_object.__module__}.{class_object.__qualname__}")
            name = class_object.__name__
            key = (id(module), name)
            if vars(module).get(name) is class_object and key not in explicit:
                state = _semantic_class_state(class_object)
                append_entry(
                    "BINDING",
                    f"{_semantic_module_import_name(module)}.{name}",
                    module, name,
                    class_object, ("CLASS", state),
                )
                enqueue_class_state(state)
            continue
        function = pending_functions.pop()
        if id(function) in captured_functions:
            continue
        captured_functions.add(id(function))
        module = _semantic_function_module(function)
        if module is None or not _stable_decision_namespace(module.__name__):
            continue
        enqueue_function_state(_semantic_function_state(function))
        namespace = function.__globals__
        referenced_names = sorted({
            name
            for code in _nested_code_objects(function.__code__)
            for name in code.co_names
        })
        bindings = [
            (module, name) if name in namespace else (builtins, name)
            for name in referenced_names
            if name in namespace or name in vars(builtins)
        ]
        bindings.extend(_referenced_module_attributes(function))
        for owner, name in bindings:
            key = (id(owner), name)
            namespace = vars(owner)
            present = name in namespace
            value = namespace[name] if present else _MISSING
            if key not in explicit:
                state = _semantic_binding_state(value, owner)
                append_entry(
                    "BINDING",
                    f"{_semantic_module_import_name(owner)}.{name}",
                    owner, name,
                    value, state,
                )
                if state[0] == "CLASS":
                    enqueue_class_state(state[1])
                elif state[0] == "DATA":
                    enqueue_value_state(state[1])
            if type(value) is types.FunctionType:
                enqueue_function(value)
            elif (isinstance(value, type)
                  and _stable_decision_namespace(value.__module__)):
                enqueue_class_state(_semantic_class_state(value))
    return tuple(sorted(entries, key=lambda item: (item[1], item[0])))


def _require_decision_semantics(
        selected: tuple[tuple[Any, ...], ...]) -> None:
    _prepare_decision_semantic_caches()
    for (kind, label, module, module_name, name, original,
         prior_state) in selected:
        if sys.modules.get(module_name) is not module:
            raise RuntimeBundleError(
                f"decision semantic module changed after activation: {label}")
        if kind == "IDENTITY_CLASS":
            if not _same_semantic_class(
                    _semantic_class_state(original), prior_state):
                raise RuntimeBundleError(
                    "decision semantic state changed after activation: "
                    f"{label}")
            continue
        current = vars(module).get(name, _MISSING)
        if current is not original:
            raise RuntimeBundleError(
                f"decision semantic root changed after activation: {label}")
        if kind == "DATA":
            matches = _same_semantic_value(
                _freeze_semantic_value(current), prior_state)
        elif kind == "FUNCTION":
            matches = _same_semantic_function(
                _semantic_function_state(current), prior_state)
        elif kind == "CLASS":
            matches = _same_semantic_class(
                _semantic_class_state(current), prior_state)
        elif kind == "SEQUENCE":
            matches = _same_semantic_sequence(
                _semantic_sequence_state(current), prior_state)
        elif kind == "BINDING":
            matches = _same_semantic_binding(
                _semantic_binding_state(current, module), prior_state)
        else:
            raise RuntimeBundleError(
                f"unknown decision semantic seal entry: {kind!r}")
        if not matches:
            raise RuntimeBundleError(
                f"decision semantic state changed after activation: {label}")


def _semantic_type_label(value: type) -> str:
    return f"{value.__module__}.{value.__qualname__}"


def _stable_semantic_path(raw: str, package_root: Path) -> str:
    path = Path(raw)
    if not path.is_absolute():
        return "RELATIVE_PATH/" + PurePosixPath(path.as_posix()).as_posix()
    try:
        relative = path.relative_to(package_root)
    except ValueError as exc:
        raise RuntimeBundleError(
            f"decision semantics contain a host path outside the package: {raw!r}") \
            from exc
    return _join_stable_locator(
        "PROJECT_ROOT", PurePosixPath(relative.as_posix()))


def _stable_frozen_semantic_value(state: tuple, package_root: Path) -> Any:
    kind = state[0]
    if kind == "SCALAR":
        value = state[2]
        if isinstance(value, bytes):
            return {
                "kind": "BYTES", "contentDigest": sha256_bytes(value),
                "byteLength": len(value),
            }
        return {
            "kind": _semantic_type_label(state[1]),
            "value": value,
        }
    if kind == "NONFINITE_FLOAT":
        return {"kind": "builtins.float", "nonFiniteValue": state[2]}
    if kind == "IDENTITY":
        value = state[1]
        if isinstance(value, type):
            return {"kind": "CLASS_REF", "ref": _semantic_type_label(value)}
        if type(value) is types.FunctionType:
            return {
                "kind": "FUNCTION_REF",
                "ref": f"{value.__module__}.{value.__qualname__}",
            }
        if callable(value):
            return {
                "kind": "CALLABLE_REF",
                "module": getattr(value, "__module__", None),
                "qualname": (
                    getattr(value, "__qualname__", None)
                    or getattr(value, "__name__", None)
                ),
                "type": _semantic_type_label(type(value)),
            }
        return {"kind": "OBJECT_REF", "type": _semantic_type_label(type(value))}
    if kind == "PATH":
        return {
            "kind": "PATH", "type": _semantic_type_label(state[1]),
            "locator": _stable_semantic_path(state[3], package_root),
        }
    if kind == "REGEX":
        pattern = state[3]
        stable_pattern = (
            {"kind": "BYTES", "contentDigest": sha256_bytes(pattern),
             "byteLength": len(pattern)}
            if isinstance(pattern, bytes) else pattern
        )
        return {
            "kind": "REGEX", "type": _semantic_type_label(state[1]),
            "pattern": stable_pattern, "flags": state[4],
        }
    if kind == "METHODCALLER":
        return {
            "kind": "METHODCALLER",
            "arguments": _stable_frozen_semantic_value(
                state[3], package_root),
        }
    if kind == "CALLABLE":
        return _stable_semantic_function_state(state[2], package_root)
    if kind == "MAPPING":
        return {
            "kind": "MAPPING", "type": _semantic_type_label(state[1]),
            "entries": [{
                "key": _stable_frozen_semantic_value(key, package_root),
                "value": _stable_frozen_semantic_value(value, package_root),
            } for key, value in state[3]],
        }
    if kind in {"SEQUENCE", "SET"}:
        values = [
            _stable_frozen_semantic_value(item, package_root)
            for item in state[3]
        ]
        if kind == "SET":
            values.sort(key=canonical_json)
        return {
            "kind": kind, "type": _semantic_type_label(state[1]),
            "values": values,
        }
    if kind == "OBJECT":
        return {
            "kind": "OBJECT", "type": _semantic_type_label(state[1]),
            "fields": [{
                "name": name,
                "value": _stable_frozen_semantic_value(value, package_root),
            } for name, value in state[3]],
        }
    raise RuntimeBundleError(f"unsupported frozen semantic value: {kind!r}")


def _stable_code_constant(value: Any, package_root: Path) -> Any:
    if isinstance(value, types.CodeType):
        return {"kind": "CODE", "value": _stable_code_document(value, package_root)}
    if value is Ellipsis:
        return {"kind": "ELLIPSIS"}
    if isinstance(value, complex):
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise RuntimeBundleError("decision bytecode contains non-finite complex data")
        return {"kind": "COMPLEX", "real": value.real, "imag": value.imag}
    return _stable_frozen_semantic_value(
        _freeze_semantic_value(value), package_root)


def _stable_code_document(code: types.CodeType, package_root: Path) -> dict[str, Any]:
    attrs_hash = (
        code.co_name == "__hash__"
        and code.co_filename.startswith("<attrs generated methods ")
    )
    instruction_bytes = code.co_code
    if attrs_hash:
        instruction_bytes = canonical_json([{
            "opname": instruction.opname,
            "argument": (
                "ATTRS_HASH_SALT"
                if (instruction.opname == "LOAD_CONST"
                    and isinstance(instruction.arg, int)
                    and isinstance(code.co_consts[instruction.arg], int))
                else instruction.arg
            ),
        } for instruction in dis.get_instructions(code)]).encode("utf-8")
    constants = []
    for value in code.co_consts:
        stable_value = (
            {"kind": "ATTRS_HASH_SALT"}
            if attrs_hash and isinstance(value, int)
            else _stable_code_constant(value, package_root)
        )
        # attrs can emit both the randomized salt and its folded negation in
        # ``co_consts`` even though only one is loaded.  Their count therefore
        # varies with PYTHONHASHSEED; one marker retains the semantic fact that
        # an attrs salt participates without retaining that process accident.
        if not (attrs_hash and stable_value in constants):
            constants.append(stable_value)
    return {
        "name": code.co_name,
        "qualname": code.co_qualname,
        "argCount": code.co_argcount,
        "positionalOnlyArgCount": code.co_posonlyargcount,
        "keywordOnlyArgCount": code.co_kwonlyargcount,
        "localCount": code.co_nlocals,
        "stackSize": code.co_stacksize,
        "flags": code.co_flags,
        "instructionDigest": sha256_bytes(instruction_bytes),
        "exceptionTableDigest": sha256_bytes(code.co_exceptiontable),
        "constants": constants,
        "names": list(code.co_names),
        "variableNames": list(code.co_varnames),
        "freeVariables": list(code.co_freevars),
        "cellVariables": list(code.co_cellvars),
    }


def _stable_semantic_function_state(
        state: tuple, package_root: Path) -> dict[str, Any]:
    if state[0] != "FUNCTION":
        value = state[1]
        return {
            "kind": "CALLABLE_REF",
            "ref": f"{type(value).__module__}.{type(value).__qualname__}",
        }
    return {
        "kind": "FUNCTION",
        "module": state[12],
        "name": state[13],
        "qualname": state[14],
        "code": _stable_code_document(state[2], package_root),
        "defaults": _stable_frozen_semantic_value(state[4], package_root),
        "keywordDefaults": _stable_frozen_semantic_value(state[6], package_root),
        "closure": [
            _stable_frozen_semantic_value(value, package_root)
            for _cell, value in state[7]
        ],
        "annotations": _stable_frozen_semantic_value(state[9], package_root),
        "attributes": _stable_frozen_semantic_value(state[11], package_root),
    }


def _stable_semantic_class_state(
        state: tuple, package_root: Path) -> dict[str, Any]:
    return {
        "kind": "CLASS",
        "module": state[4],
        "name": state[5],
        "qualname": state[6],
        "mro": [_semantic_type_label(item) for item in state[1]],
        "bases": [
            _stable_semantic_class_state(base_state, package_root)
            for _base, base_state in state[7]
        ],
        "descriptors": [{
            "name": name,
            "kind": _semantic_type_label(type(descriptor)),
            "functions": [{
                "kind": function_kind,
                "state": _stable_semantic_function_state(
                    function_state, package_root),
            } for function_kind, function_state in functions],
        } for name, descriptor, functions in state[2]],
        "data": [{
            "name": name,
            "state": _stable_frozen_semantic_value(value_state, package_root),
        } for name, _value, value_state in state[3]],
    }


def _stable_semantic_sequence_state(
        state: tuple, package_root: Path) -> dict[str, Any]:
    return {
        "kind": "DISPATCH_SEQUENCE",
        "items": [{
            "class": _semantic_type_label(item[1]),
            "state": _stable_frozen_semantic_value(item[3], package_root),
            "classState": _stable_semantic_class_state(item[4], package_root),
        } for item in state[1]],
    }


def _stable_semantic_binding_state(
        state: tuple,
        package_root: Path,
        owner: types.ModuleType,
        name: str,
) -> dict[str, Any]:
    if state[0] == "ABSENT":
        return {"kind": "ABSENT"}
    if (name == "__file__" and state[0] == "DATA"
            and state[1][0] == "SCALAR"
            and state[1][1] is str):
        identity = {"kind": "MODULE_FILE", "module": owner.__name__}
        if owner.__name__ == "kernel" or owner.__name__.startswith("kernel."):
            raw_path = Path(state[1][2])
            try:
                relative = raw_path.relative_to(package_root)
            except ValueError:
                try:
                    kernel_index = len(raw_path.parts) - 1 \
                        - tuple(reversed(raw_path.parts)).index("kernel")
                except ValueError as exc:
                    raise RuntimeBundleError(
                        "kernel decision module file has no project-relative "
                        f"identity: {state[1][2]!r}") from exc
                relative = Path(*raw_path.parts[kernel_index:])
            identity["locator"] = _join_stable_locator(
                "PROJECT_ROOT", PurePosixPath(relative.as_posix()))
        return identity
    if state[0] == "MODULE":
        return {"kind": "MODULE", "name": state[2]}
    if state[0] == "FUNCTION":
        function_state = state[1]
        return _stable_semantic_function_state(function_state, package_root)
    if state[0] == "CLASS":
        class_state = state[1]
        if _stable_decision_namespace(class_state[4]):
            return _stable_semantic_class_state(class_state, package_root)
        return {
            "kind": "EXTERNAL_CLASS_REF",
            "module": class_state[4],
            "qualname": class_state[6],
        }
    if state[0] == "IDENTITY_DATA":
        value = state[1]
        if callable(value):
            return {
                "kind": "EXTERNAL_CALLABLE_REF",
                "ownerModule": owner.__name__,
                "callableModule": getattr(value, "__module__", None),
                "callableQualname": (
                    getattr(value, "__qualname__", None)
                    or getattr(value, "__name__", None)
                ),
                "type": _semantic_type_label(state[2]),
            }
        return {
            "kind": "EXTERNAL_DATA_REF",
            "module": owner.__name__,
            "type": _semantic_type_label(state[2]),
        }
    return _stable_frozen_semantic_value(state[1], package_root)


def _stable_originless_module_value(value: object, package_root: Path) -> Any:
    if type(value) is types.ModuleType:
        return {"kind": "MODULE_REF", "name": value.__name__}
    if isinstance(value, type):
        module_name = getattr(value, "__module__", None)
        qualname = getattr(value, "__qualname__", None)
        if (isinstance(module_name, str)
                and isinstance(qualname, str)
                and _stable_decision_namespace(module_name)):
            return _stable_semantic_class_state(
                _semantic_class_state(value), package_root)

        def safe_class_ref(class_object: object) -> dict[str, Any]:
            return {
                "module": (
                    getattr(class_object, "__module__", None)
                    if isinstance(getattr(class_object, "__module__", None), str)
                    else None
                ),
                "name": (
                    getattr(class_object, "__name__", None)
                    if isinstance(getattr(class_object, "__name__", None), str)
                    else None
                ),
                "qualname": (
                    getattr(class_object, "__qualname__", None)
                    if isinstance(getattr(class_object, "__qualname__", None), str)
                    else None
                ),
            }

        return {
            "kind": "NATIVE_CLASS_REF",
            **safe_class_ref(value),
            "metaclass": safe_class_ref(type(value)),
            "attributes": [{
                "name": name,
                "type": safe_class_ref(type(descriptor)),
                "callable": ({
                    "module": getattr(descriptor, "__module__", None),
                    "qualname": (
                        getattr(descriptor, "__qualname__", None)
                        or getattr(descriptor, "__name__", None)
                    ),
                } if callable(descriptor)
                    and isinstance(getattr(descriptor, "__module__", None), str)
                    and isinstance((
                        getattr(descriptor, "__qualname__", None)
                        or getattr(descriptor, "__name__", None)), str)
                    else None),
            } for name, descriptor in sorted(vars(value).items())],
        }
    if type(value) is types.FunctionType:
        return _stable_semantic_function_state(
            _semantic_function_state(value), package_root)
    return _stable_frozen_semantic_value(
        _freeze_semantic_value(value), package_root)


def _originless_module_state_digest(
        name: str, module: object, package_root: Path) -> str:
    """Bind behavior/data on namespace and retained-parent auxiliary modules."""
    spec = getattr(module, "__spec__", None)
    state = {
        "name": getattr(module, "__name__", None),
        "package": getattr(module, "__package__", None),
        "documentation": getattr(module, "__doc__", None),
        "fileIsAbsent": getattr(module, "__file__", None) is None,
        "cachedIsAbsent": getattr(module, "__cached__", None) is None,
        "spec": (
            None if spec is None else {
                "name": getattr(spec, "name", None),
                "parent": getattr(spec, "parent", None),
                "origin": getattr(spec, "origin", None),
                "hasLocation": getattr(spec, "has_location", None),
                "loader": (
                    None if getattr(spec, "loader", None) is None else
                    _semantic_type_label(type(spec.loader))
                ),
            }
        ),
        "loader": (
            None if getattr(module, "__loader__", None) is None else
            _semantic_type_label(type(module.__loader__))
        ),
        "attributes": [],
    }
    for attribute, value in sorted(vars(module).items()):
        if attribute in _NAMESPACE_MODULE_METADATA:
            continue
        state["attributes"].append({
            "name": attribute,
            "value": _stable_originless_module_value(value, package_root),
        })
    canonical = canonical_json(state).encode("utf-8")
    return sha256_bytes(canonical)


def _decision_semantic_callable_anchors(
        selected: tuple[tuple[Any, ...], ...],
) -> tuple[tuple[types.FunctionType, types.CodeType], ...]:
    anchors: dict[int, tuple[types.FunctionType, types.CodeType]] = {}

    def add_value(state: tuple) -> None:
        if state[0] == "CALLABLE":
            add_function(state[2])
        elif state[0] == "MAPPING":
            for key, value in state[3]:
                add_value(key)
                add_value(value)
        elif state[0] in {"SEQUENCE", "SET"}:
            for value in state[3]:
                add_value(value)
        elif state[0] == "OBJECT":
            for _name, value in state[3]:
                add_value(value)

    def add_function(state: tuple) -> None:
        if state[0] == "FUNCTION":
            anchors[id(state[1])] = (state[1], state[2])
            for value in (state[4], state[6], state[9], state[11]):
                add_value(value)
            for _cell, value in state[7]:
                add_value(value)

    def add_class(state: tuple) -> None:
        for _name, _descriptor, functions in state[2]:
            for _kind, function_state in functions:
                add_function(function_state)
        for _name, _value, value_state in state[3]:
            add_value(value_state)
        for _base, base_state in state[7]:
            add_class(base_state)

    for kind, _label, _module, _module_name, _name, _original, state in selected:
        if kind == "FUNCTION":
            add_function(state)
        elif kind == "DATA":
            add_value(state)
        elif kind == "CLASS":
            add_class(state)
        elif kind == "SEQUENCE":
            for item in state[1]:
                add_value(item[3])
                add_class(item[4])
        elif kind == "BINDING":
            if state[0] == "FUNCTION":
                add_function(state[1])
            elif state[0] == "CLASS":
                add_class(state[1])
            elif state[0] == "DATA":
                add_value(state[1])
        elif kind == "IDENTITY_CLASS":
            add_class(state)
    return tuple(anchors[key] for key in sorted(anchors))


_STABLE_DECISION_SEMANTICS_SCHEMA = \
    "ofarm.runtime-decision-semantics-identity.local.v1"
_STABLE_DECISION_SEMANTICS_LABEL_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+"
)


def _stable_decision_semantics_document(
        selected: tuple[tuple[Any, ...], ...], package_root: Path,
) -> dict[str, Any]:
    entries = []
    identity_class_states: dict[str, bytes] = {}
    for kind, label, module, _module_name, name, _original, state in selected:
        if kind == "DATA":
            stable_state = _stable_frozen_semantic_value(state, package_root)
        elif kind == "FUNCTION":
            stable_state = _stable_semantic_function_state(state, package_root)
        elif kind == "CLASS":
            stable_state = _stable_semantic_class_state(state, package_root)
        elif kind == "SEQUENCE":
            stable_state = _stable_semantic_sequence_state(state, package_root)
        elif kind == "BINDING":
            stable_state = _stable_semantic_binding_state(
                state, package_root, module, name)
        elif kind == "IDENTITY_CLASS":
            stable_state = _stable_semantic_class_state(state, package_root)
        else:
            raise RuntimeBundleError(
                f"unsupported stable decision semantic entry: {kind!r}")
        stable_bytes = canonical_json(stable_state).encode("utf-8")
        if kind == "IDENTITY_CLASS":
            # The stable label contains no process identity.  Equal generated
            # classes collapse to one semantic identity, while unequal states
            # receive different labels.  As everywhere else in RuntimeBundle,
            # digest reuse is accepted only after exact byte equality.
            label = "identity_class.class_" + \
                hashlib.sha256(stable_bytes).hexdigest()
            retained = identity_class_states.get(label)
            if retained is not None:
                if retained != stable_bytes:
                    raise RuntimeBundleError(
                        "decision identity-class digest collision")
                continue
            identity_class_states[label] = stable_bytes
        entries.append({
            "kind": kind,
            "label": label,
            "stateDigest": sha256_bytes(stable_bytes),
        })
    entries.sort(key=lambda entry: (entry["label"], entry["kind"]))
    document = {
        "schemaVersion": _STABLE_DECISION_SEMANTICS_SCHEMA,
        "entries": entries,
    }
    _validate_stable_decision_semantics_document(document)
    return document


def _validate_stable_decision_semantics_document(document: Any) -> None:
    if (not isinstance(document, dict)
            or set(document) != {"schemaVersion", "entries"}
            or document.get("schemaVersion") != _STABLE_DECISION_SEMANTICS_SCHEMA
            or not isinstance(document.get("entries"), list)
            or not document["entries"]):
        raise RuntimeBundleError("stable decision semantics identity is malformed")
    identities = []
    for entry in document["entries"]:
        if (not isinstance(entry, dict)
                or set(entry) != {"kind", "label", "stateDigest"}
                or entry.get("kind") not in {
                    "DATA", "FUNCTION", "CLASS", "SEQUENCE", "BINDING",
                    "IDENTITY_CLASS"}
                or not isinstance(entry.get("label"), str)
                or not _STABLE_DECISION_SEMANTICS_LABEL_RE.fullmatch(
                    entry["label"])
                or not isinstance(entry.get("stateDigest"), str)
                or not _SHA256_RE.fullmatch(entry["stateDigest"])):
            raise RuntimeBundleError(
                "stable decision semantics entry is malformed")
        identities.append((entry["label"], entry["kind"]))
    if identities != sorted(identities) or len(identities) != len(set(identities)):
        raise RuntimeBundleError(
            "stable decision semantics inventory is not canonical")
    try:
        canonical_json(document)
    except (TypeError, ValueError) as exc:
        raise RuntimeBundleError(
            "stable decision semantics identity is not canonical JSON") from exc


_DECISION_RECEIPT_IMPLEMENTATION_ANCHORS = tuple(
    (function, function.__code__)
    for function in (
        _freeze_semantic_value,
        _same_semantic_value,
        _prepare_decision_semantic_caches,
        _semantic_function_state,
        _same_semantic_function,
        _semantic_class_state,
        _same_semantic_class,
        _capture_decision_semantics,
        _require_decision_semantics,
        _stable_frozen_semantic_value,
        _stable_code_document,
        _stable_semantic_function_state,
        _stable_semantic_class_state,
        _stable_semantic_binding_state,
        _decision_semantic_callable_anchors,
        _stable_decision_semantics_document,
        _validate_stable_decision_semantics_document,
    )
)


def _require_decision_receipt_implementation() -> None:
    """Require the import-time code anchors that construct semantic receipts."""
    if (_require_decision_receipt_implementation.__code__ is not
            _DECISION_RECEIPT_GUARD_CODE
            or globals().get("_require_decision_receipt_implementation") is not
            _require_decision_receipt_implementation
            or any(
            function.__code__ is not code
            or function.__globals__.get(function.__name__) is not function
            for function, code in _DECISION_RECEIPT_IMPLEMENTATION_ANCHORS)):
        raise RuntimeBundleError(
            "decision semantics receipt implementation changed after import")


_DECISION_RECEIPT_GUARD_CODE = _require_decision_receipt_implementation.__code__


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
            elif (namespace_paths
                  and _namespace_module_state_is_closed(name, module)
                  and all(
                    any(path == root or path.startswith(root + os.sep)
                        for root in dependency_roots)
                    or any(component_path.startswith(path + os.sep)
                           for component_path in project_files)
                    or (trusted_test_harness
                        and _test_harness_namespace_path(
                            package_root, Path(path)))
                    for path in namespace_paths)):
                entry["classification"] = "RETAINED_NAMESPACE"
            else:
                entry["classification"] = "UNKNOWN"
        if entry["classification"] in {
                "RETAINED_NAMESPACE", "REVIEWED_NATIVE_AUXILIARY"}:
            entry["originlessStateDigest"] = \
                _originless_module_state_digest(name, module, package_root)
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
        "flags", "pycachePrefix", "pycachePrefixExists",
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
            "ofarm.runtime-environment-observation.local.v4"
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
            or isinstance(document["python"].get("executableByteLength"), bool)
            or document["python"]["executableByteLength"] <= 0
            or any(not isinstance(document["python"].get(key), str)
                   or not document["python"][key]
                   for key in ("implementation", "version", "cacheTag"))
            or (document["python"].get("soabi") is not None
                and not isinstance(document["python"]["soabi"], str))
            or not isinstance(document["python"].get("optimizationLevel"), int)
            or isinstance(document["python"]["optimizationLevel"], bool)
            or (document["python"].get("hashSeedEnvironment") is not None
                and not isinstance(
                    document["python"]["hashSeedEnvironment"], str))
            or (document["python"].get("pycachePrefix") is not None
                and not isinstance(document["python"]["pycachePrefix"], str))
            or (document["python"].get("pycachePrefixExists") is not None
                and type(document["python"].get("pycachePrefixExists")) is not bool)
            or type(document["python"]["flags"].get("safePath")) is not bool
            or any(not isinstance(document["python"]["flags"].get(key), int)
                   or isinstance(document["python"]["flags"][key], bool)
                   for key in flag_keys - {"safePath"})
            or not isinstance(document["importPosture"].get("projectRoot"), str)
            or not Path(document["importPosture"]["projectRoot"]).is_absolute()
            or set(document["importPosture"].get("ambientEnvironment", {})) !=
            set(_AMBIENT_IMPORT_ENVIRONMENT)
            or any(value is not None and not isinstance(value, str)
                   for value in document["importPosture"]
                   ["ambientEnvironment"].values())
            or not isinstance(document["importPosture"].get(
                "startupCustomizationModules"), list)
            or any(not isinstance(name, str) or not name
                   for name in document["importPosture"]
                   ["startupCustomizationModules"])
            or document["importPosture"]["startupCustomizationModules"] !=
            sorted(set(document["importPosture"]
                       ["startupCustomizationModules"]))):
        raise RuntimeBundleError("Python runtime identity fields are malformed")

    process = document.get("process")
    native_loader_environment = (
        process.get("nativeLoaderEnvironment") if isinstance(process, dict) else None)
    locale_environment = (
        process.get("localeEnvironment") if isinstance(process, dict) else None)
    locale_categories = (
        process.get("localeCategories") if isinstance(process, dict) else None)
    if (not isinstance(document.get("platform"), dict)
            or set(document["platform"]) != {"operatingSystem", "machine"}
            or any(not isinstance(value, str) or not value
                   for value in document["platform"].values())
            or not isinstance(process, dict)
            or set(process) != {
                "localeEnvironment", "localeCategories", "timezoneEnvironment",
                "timezoneNames", "utcOffsetSeconds", "nativeLoaderEnvironment",
            }
            or not isinstance(locale_environment, dict)
            or set(locale_environment) != {"LANG", "LC_ALL"}
            or any(value is not None and not isinstance(value, str)
                   for value in locale_environment.values())
            or not isinstance(locale_categories, dict)
            or set(locale_categories) != {
                "collate", "ctype", "monetary", "numeric", "time"}
            or any(not isinstance(value, str) or not value
                   for value in locale_categories.values())
            or (process.get("timezoneEnvironment") is not None
                and not isinstance(process["timezoneEnvironment"], str))
            or not isinstance(process.get("timezoneNames"), list)
            or not process["timezoneNames"]
            or any(not isinstance(value, str)
                   for value in process["timezoneNames"])
            or not isinstance(process.get("utcOffsetSeconds"), int)
            or isinstance(process["utcOffsetSeconds"], bool)
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
                   or not isinstance(item.get("index"), int)
                   or isinstance(item.get("index"), bool)
                   or item.get("index") != index
                   or item.get("classification") not in {
                       "PINNED_RUNTIME_IMAGE_ROOT", "LOCKED_DEPENDENCY_ROOT",
                       "REVIEWED_PROJECT_ROOT", "UNKNOWN"}
                   or not isinstance(item.get("path"), str)
                   or not Path(item["path"]).is_absolute()
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
        "retainedParent", "originlessStateDigest",
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
        originless = module.get("classification") in {
            "RETAINED_NAMESPACE", "REVIEWED_NATIVE_AUXILIARY"}
        if (("originlessStateDigest" in module) != originless
                or (originless and (
                    type(module["originlessStateDigest"]) is not str
                    or not _SHA256_RE.fullmatch(
                        module["originlessStateDigest"])))):
            raise RuntimeBundleError(
                "loaded originless module state identity is malformed")
        if "contentDigest" in module and (
                not isinstance(module["contentDigest"], str)
                or not _SHA256_RE.fullmatch(module["contentDigest"])
                or not isinstance(module.get("byteLength"), int)
                or isinstance(module.get("byteLength"), bool)
                or module["byteLength"] < 0):
            raise RuntimeBundleError("loaded Python module content identity is malformed")
        if (("contentDigest" in module) != ("byteLength" in module)):
            raise RuntimeBundleError(
                "loaded Python module content identity is incomplete")
        retained = module.get("retainedComponent")
        if retained is not None and (
                not isinstance(retained, dict)
                or set(retained) != {"role", "logicalRef"}
                or any(not isinstance(value, str) or not value
                       for value in retained.values())):
            raise RuntimeBundleError(
                "loaded Python module retained component is malformed")
        owners = module.get("distributions")
        if owners is not None and (
                not isinstance(owners, list)
                or owners != sorted(set(owners))
                or any(not isinstance(owner, str) or not owner
                       for owner in owners)):
            raise RuntimeBundleError(
                "loaded Python module distribution ownership is malformed")
        parent = module.get("retainedParent")
        if parent is not None and (
                not isinstance(parent, dict)
                or set(parent) != {"name", "origin"}
                or any(not isinstance(value, str) or not value
                       for value in parent.values())
                or not Path(parent["origin"]).is_absolute()):
            raise RuntimeBundleError(
                "loaded Python module retained parent is malformed")
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
                    or isinstance(item.get("byteLength"), bool)
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
                or isinstance(layer.get("byteLength"), bool)
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
                or not isinstance(entry.get("inode"), int)
                or isinstance(entry.get("inode"), bool)
                or entry["inode"] <= 0
                or not _SHA256_RE.fullmatch(entry.get("contentDigest", ""))
                or not isinstance(entry.get("byteLength"), int)
                or isinstance(entry.get("byteLength"), bool)
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
                or isinstance(distribution.get("wheelArchiveByteLength"), bool)
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
        "schemaVersion": "ofarm.runtime-environment-observation.local.v4",
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
            "pycachePrefixExists": (
                Path(sys.pycache_prefix).exists()
                if isinstance(sys.pycache_prefix, str) else None
            ),
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


_STABLE_ENVIRONMENT_SCHEMA = "ofarm.runtime-environment-identity.local.v4"
_STABLE_LOCATOR_RE = re.compile(
    r"^(?P<root>PROJECT_ROOT|PINNED_IMAGE_ROOTFS|"
    r"PINNED_IMAGE_FILE\[sha256:[0-9a-f]{64}\]|"
    r"LOCKED_WHEEL_ROOT\[sha256:[0-9a-f]{64}\]|"
    r"PINNED_IMAGE_ROOT\[sha256:[0-9a-f]{64}\])"
    r"(?P<suffix>(?:/[^/\\\x00]+)*)$"
)


def _stable_root_locator(kind: str, identity: dict[str, Any]) -> str:
    canonical = canonical_json(identity).encode("utf-8")
    return f"{kind}[{sha256_bytes(canonical)}]"


def _join_stable_locator(root: str, relative: PurePosixPath) -> str:
    if relative == PurePosixPath("."):
        return root
    if (relative.is_absolute()
            or any(part in {"", ".", ".."}
                   or "\\" in part
                   or any(ord(character) < 32 for character in part)
                   for part in relative.parts)):
        raise RuntimeBundleError(
            f"runtime identity has an unsafe relative locator: {relative!s}")
    return root + "/" + relative.as_posix()


def _stable_locator_parts(locator: object) -> tuple[str, str] | None:
    if not isinstance(locator, str):
        return None
    match = _STABLE_LOCATOR_RE.fullmatch(locator)
    if match is None:
        return None
    suffix = match.group("suffix")
    parts = suffix[1:].split("/") if suffix else []
    if any(part in {"", ".", ".."}
           or any(ord(character) < 32 for character in part)
           for part in parts):
        return None
    return match.group("root"), suffix[1:] if suffix else ""


def _stable_locator_root(locator: object) -> str | None:
    parts = _stable_locator_parts(locator)
    return parts[0] if parts is not None else None


def _project_stable_runtime_environment_document(
        live_document: Mapping[str, Any],
        retained_components: Iterable[RuntimeComponent],
) -> dict[str, Any]:
    """Project one exact process observation onto a relocatable identity."""
    _validate_runtime_environment_document(live_document)
    retained_components = tuple(retained_components)
    image_manifest = _runtime_image_manifest(retained_components)
    document = copy.deepcopy(live_document)
    imports = document["importPosture"]
    project_root = Path(imports["projectRoot"])

    distributions_by_root: dict[str, list[dict[str, str]]] = {}
    for distribution in document["distributions"]:
        distributions_by_root.setdefault(distribution["root"], []).append({
            "name": distribution["name"],
            "wheelArchiveDigest": distribution["wheelArchiveDigest"],
        })
    dependency_roots = {
        raw_root: _stable_root_locator(
            "LOCKED_WHEEL_ROOT",
            {"distributions": sorted(members, key=lambda item: item["name"])},
        )
        for raw_root, members in distributions_by_root.items()
    }

    standard_roots = {}
    for root in document["standardRuntime"]["roots"]:
        identity = {
            "directories": root["directories"],
            "files": [{
                "relativePath": item["path"],
                "contentDigest": item["contentDigest"],
                "byteLength": item["byteLength"],
            } for item in root["files"]],
        }
        standard_roots[root["path"]] = _stable_root_locator(
            "PINNED_IMAGE_ROOT", identity)

    standalone_runtime_files: dict[str, str] = {}
    standard = document["standardRuntime"]
    for kind, entries in (
            ("ARCHIVE", standard["archives"]),
            ("SHARED_LIBRARY", (
                [standard["sharedLibrary"]]
                if standard["sharedLibrary"] is not None else []))):
        for entry in entries:
            standalone_runtime_files[entry["resolvedPath"]] = \
                _stable_root_locator("PINNED_IMAGE_FILE", {
                    "kind": kind,
                    "contentDigest": entry["contentDigest"],
                    "byteLength": entry["byteLength"],
                })

    _manifest_standard, manifest_native = \
        _retained_runtime_image_maps(image_manifest)
    del _manifest_standard
    manifest_loader = {
        entry["path"]: (entry["contentDigest"], entry["byteLength"])
        for entry in image_manifest["python"]["loaderConfigurationFiles"]
    }
    retained_rootfs_files = {**manifest_native, **manifest_loader}
    retained_absent_paths = set(
        image_manifest["python"]["requiredAbsentPaths"])

    def locate(
            raw_path: str,
            *,
            expected_identity: tuple[str, int] | None = None,
            allow_absent: bool = False,
    ) -> str:
        path = Path(raw_path)
        if not path.is_absolute():
            raise RuntimeBundleError(
                f"physical runtime path is not absolute: {raw_path!r}")
        # The retained wheel environment lives below the checkout in CI, so
        # match the more specific owned roots before PROJECT_ROOT.
        for raw_root, locator in sorted(
                dependency_roots.items(), key=lambda item: len(item[0]), reverse=True):
            try:
                relative = path.relative_to(Path(raw_root))
            except ValueError:
                continue
            return _join_stable_locator(locator, PurePosixPath(relative.as_posix()))
        for raw_root, locator in sorted(
                standard_roots.items(), key=lambda item: len(item[0]), reverse=True):
            try:
                relative = path.relative_to(Path(raw_root))
            except ValueError:
                continue
            return _join_stable_locator(locator, PurePosixPath(relative.as_posix()))
        for raw_root, locator in sorted(
                standalone_runtime_files.items(),
                key=lambda item: len(item[0]), reverse=True):
            try:
                relative = path.relative_to(Path(raw_root))
            except ValueError:
                continue
            return _join_stable_locator(
                locator, PurePosixPath(relative.as_posix()))
        try:
            relative = path.relative_to(project_root)
        except ValueError:
            relative = None
        if relative is not None:
            return _join_stable_locator(
                "PROJECT_ROOT", PurePosixPath(relative.as_posix()))
        retained_identity = retained_rootfs_files.get(raw_path)
        if (retained_identity is None
                and not (allow_absent and raw_path in retained_absent_paths)):
            raise RuntimeBundleError(
                "runtime identity path is outside every retained root or "
                f"pinned-image inventory: {raw_path!r}")
        if (expected_identity is not None
                and retained_identity != expected_identity):
            raise RuntimeBundleError(
                "runtime identity path differs from its retained pinned-image "
                f"content: {raw_path!r}")
        return _join_stable_locator(
            "PINNED_IMAGE_ROOTFS",
            PurePosixPath(path.relative_to(path.anchor).as_posix()),
        )

    stable_modules = []
    for module in imports["actualModules"]:
        stable = {
            "name": module["name"],
            "loader": module["loader"],
            "classification": module["classification"],
            "originLocator": module["origin"],
            "packageSearchLocators": [
                locate(path) for path in module["packageSearchPaths"]],
            "specSearchLocators": [
                locate(path) for path in module["specSearchPaths"]],
        }
        origin = module["origin"]
        if isinstance(origin, str) and origin not in {"built-in", "frozen"}:
            stable["originLocator"] = locate(origin)
        for key in (
                "contentDigest", "byteLength", "retainedComponent", "distributions",
                "originlessStateDigest"):
            if key in module:
                stable[key] = copy.deepcopy(module[key])
        if "retainedParent" in module:
            stable["retainedParent"] = {
                "name": module["retainedParent"]["name"],
                "originLocator": locate(module["retainedParent"]["origin"]),
            }
        stable_modules.append(stable)

    stable_standard_roots = []
    for root in document["standardRuntime"]["roots"]:
        stable_standard_roots.append({
            "rootLocator": standard_roots[root["path"]],
            "directories": root["directories"],
            "files": [{
                "relativePath": item["path"],
                "contentDigest": item["contentDigest"],
                "byteLength": item["byteLength"],
            } for item in root["files"]],
        })
    stable_standard_roots.sort(key=lambda item: item["rootLocator"])

    def stable_file(entry: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "originLocator": locate(entry["resolvedPath"]),
            "contentDigest": entry["contentDigest"],
            "byteLength": entry["byteLength"],
        }

    stable_archives = [stable_file(item) for item in standard["archives"]]
    stable_archives.sort(key=lambda item: item["originLocator"])
    stable_standard = {
        "roots": stable_standard_roots,
        "archives": stable_archives,
        "sharedLibrary": (
            stable_file(standard["sharedLibrary"])
            if standard["sharedLibrary"] is not None else None
        ),
    }

    stable_distributions = []
    for distribution in document["distributions"]:
        stable_distributions.append({
            "name": distribution["name"],
            "version": distribution["version"],
            "wheelArchiveDigest": distribution["wheelArchiveDigest"],
            "wheelArchiveByteLength": distribution["wheelArchiveByteLength"],
            "rootLocator": dependency_roots[distribution["root"]],
            "files": [{
                "relativePath": item["path"],
                "contentDigest": item["contentDigest"],
                "byteLength": item["byteLength"],
            } for item in distribution["files"]],
        })

    native = document["nativeRuntime"]
    stable_native_images = [{
        "originLocator": locate(
            item["resolvedPath"],
            expected_identity=(item["contentDigest"], item["byteLength"]),
        ),
        "contentDigest": item["contentDigest"],
        "byteLength": item["byteLength"],
        "classification": item["classification"],
        "distributions": item["distributions"],
    } for item in native["actualNativeImages"]]
    stable_native_images.sort(key=lambda item: (
        item["originLocator"], item["contentDigest"], item["classification"]))
    stable_loader_files = [{
        "originLocator": locate(
            item["path"],
            expected_identity=(item["contentDigest"], item["byteLength"]),
        ),
        "contentDigest": item["contentDigest"],
        "byteLength": item["byteLength"],
    } for item in native["loaderConfiguration"]["files"]]
    stable_loader_files.sort(key=lambda item: item["originLocator"])

    python = copy.deepcopy(document["python"])
    pycache_prefix = python.pop("pycachePrefix")
    pycache_prefix_exists = python.pop("pycachePrefixExists")
    python["bytecodeCachePolicy"] = (
        "ABSENT_ISOLATED_PREFIX"
        if isinstance(pycache_prefix, str) and pycache_prefix
        and pycache_prefix_exists is False
        else "UNSATISFIED"
    )
    process = copy.deepcopy(document["process"])
    loader_environment = process.pop("nativeLoaderEnvironment")
    process["nativeLoaderEnvironmentPolicy"] = (
        "FORBIDDEN_AND_ABSENT" if not loader_environment else "UNSATISFIED")
    ambient = imports["ambientEnvironment"]
    customization = imports["startupCustomizationModules"]
    stable_imports = {
        "projectRoot": "PROJECT_ROOT",
        "ambientEnvironmentPolicy": {
            "forbiddenNames": sorted(ambient),
            "status": (
                "ABSENT" if all(value is None for value in ambient.values())
                else "PRESENT"
            ),
        },
        "startupCustomizationPolicy": (
            "FORBIDDEN_AND_ABSENT" if not customization else "UNSATISFIED"),
        "dependencyRoots": sorted(set(dependency_roots.values())),
        "sysPath": [{
            "index": item["index"],
            "rootLocator": locate(item["path"]),
            "classification": item["classification"],
        } for item in imports["sysPath"]],
        "metaPath": copy.deepcopy(imports["metaPath"]),
        "pathHooks": copy.deepcopy(imports["pathHooks"]),
        "pathImporterCachePolicy": "EXACT_PROCESS_LOCAL_ACTIVATION_SEAL",
        "actualModules": stable_modules,
    }
    stable_native = {
        "imageIdentity": copy.deepcopy(native["imageIdentity"]),
        "containerBoundary": (
            "PINNED_READ_ONLY_IMAGE"
            if native["containerMarkerPresent"] and native["imageFilesReadOnly"]
            else "UNSATISFIED"
        ),
        "loaderConfiguration": {
            "files": stable_loader_files,
            "requiredAbsentLocators": sorted(
                locate(path, allow_absent=True) for path in
                native["loaderConfiguration"]["absentPaths"]),
        },
        "kernelExecutableMappingPolicy": "VDSO_VSYSCALL_ONLY",
        "actualNativeImages": stable_native_images,
    }
    stable = {
        "schemaVersion": _STABLE_ENVIRONMENT_SCHEMA,
        "python": python,
        "platform": copy.deepcopy(document["platform"]),
        "process": process,
        "importIdentity": stable_imports,
        "standardRuntime": stable_standard,
        "nativeRuntime": stable_native,
        "distributions": stable_distributions,
    }
    _validate_stable_runtime_environment_document(
        stable, retained_components)
    return stable


def _stable_runtime_environment_document(
        live_document: Mapping[str, Any],
        retained_components: Iterable[RuntimeComponent],
) -> dict[str, Any]:
    """Return a stable identity, normalizing malformed raw input failures."""
    try:
        return _project_stable_runtime_environment_document(
            live_document, retained_components)
    except RuntimeBundleError:
        raise
    except (AttributeError, LookupError, TypeError, ValueError) as exc:
        raise RuntimeBundleError(
            "Python runtime environment observation is malformed") from exc


def _validate_stable_runtime_environment_document(
        document: Any,
        retained_components: Iterable[RuntimeComponent],
) -> None:
    """Validate the relocatable identity persisted in a RuntimeBundle."""
    retained_components = tuple(retained_components)
    image_manifest = _runtime_image_manifest(retained_components)

    def malformed(label: str) -> None:
        raise RuntimeBundleError(f"stable runtime {label} is malformed")

    def exact_mapping(value: Any, keys: set[str], label: str) -> dict:
        if not isinstance(value, dict) or set(value) != keys:
            malformed(label)
        return value

    def nonempty_text(value: Any) -> bool:
        return isinstance(value, str) and bool(value)

    def valid_digest(value: Any) -> bool:
        return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))

    def relative_identity(value: Any) -> bool:
        if (not nonempty_text(value) or "\\" in value
                or any(ord(character) < 32 for character in value)):
            return False
        path = PurePosixPath(value)
        return (not path.is_absolute()
                and path.as_posix() == value
                and all(part not in {"", ".", ".."} for part in path.parts))

    locators: list[str] = []

    def locator(value: Any, label: str) -> str:
        root = _stable_locator_root(value)
        if root is None:
            malformed(label)
        locators.append(value)
        return root

    def digest_file(value: Any, label: str) -> dict:
        entry = exact_mapping(
            value, {"originLocator", "contentDigest", "byteLength"}, label)
        locator(entry["originLocator"], f"{label} locator")
        if (not valid_digest(entry["contentDigest"])
                or not isinstance(entry["byteLength"], int)
                or isinstance(entry["byteLength"], bool)
                or entry["byteLength"] < 0):
            malformed(label)
        return entry

    top = exact_mapping(document, {
        "schemaVersion", "python", "platform", "process", "importIdentity",
        "standardRuntime", "nativeRuntime", "distributions",
    }, "identity")
    if top["schemaVersion"] != _STABLE_ENVIRONMENT_SCHEMA:
        malformed("identity version")

    python = exact_mapping(top["python"], {
        "implementation", "version", "cacheTag", "soabi", "optimizationLevel",
        "hashSeedEnvironment", "executableDigest", "executableByteLength",
        "flags", "bytecodeCachePolicy",
    }, "Python identity")
    flags = exact_mapping(python["flags"], {
        "isolated", "ignoreEnvironment", "noSite", "noUserSite", "safePath",
        "dontWriteBytecode", "hashRandomization", "optimizationLevel",
    }, "Python flag identity")
    if (any(not nonempty_text(python[key]) for key in (
            "implementation", "version", "cacheTag"))
            or (python["soabi"] is not None and not nonempty_text(python["soabi"]))
            or (python["hashSeedEnvironment"] is not None
                and not isinstance(python["hashSeedEnvironment"], str))
            or not isinstance(python["optimizationLevel"], int)
            or isinstance(python["optimizationLevel"], bool)
            or not valid_digest(python.get("executableDigest"))
            or not isinstance(python["executableByteLength"], int)
            or isinstance(python["executableByteLength"], bool)
            or python["executableByteLength"] <= 0
            or not isinstance(python["bytecodeCachePolicy"], str)
            or python["bytecodeCachePolicy"] not in {
                "ABSENT_ISOLATED_PREFIX", "UNSATISFIED"}
            or type(flags["safePath"]) is not bool
            or any(not isinstance(flags[key], int) or isinstance(flags[key], bool)
                   for key in set(flags) - {"safePath"})):
        malformed("Python identity")

    platform_identity = exact_mapping(
        top["platform"], {"operatingSystem", "machine"}, "platform identity")
    if any(not nonempty_text(value) for value in platform_identity.values()):
        malformed("platform identity")

    process = exact_mapping(top["process"], {
        "localeEnvironment", "localeCategories", "timezoneEnvironment",
        "timezoneNames", "utcOffsetSeconds", "nativeLoaderEnvironmentPolicy",
    }, "process identity")
    locale_environment = exact_mapping(
        process["localeEnvironment"], {"LANG", "LC_ALL"},
        "locale environment identity")
    locale_categories = exact_mapping(process["localeCategories"], {
        "collate", "ctype", "monetary", "numeric", "time",
    }, "locale category identity")
    if (any(value is not None and not isinstance(value, str)
            for value in locale_environment.values())
            or any(not isinstance(value, str)
                   for value in locale_categories.values())
            or (process["timezoneEnvironment"] is not None
                and not isinstance(process["timezoneEnvironment"], str))
            or not isinstance(process["timezoneNames"], list)
            or not process["timezoneNames"]
            or any(not isinstance(value, str) for value in process["timezoneNames"])
            or not isinstance(process["utcOffsetSeconds"], int)
            or isinstance(process["utcOffsetSeconds"], bool)
            or not isinstance(process["nativeLoaderEnvironmentPolicy"], str)
            or process["nativeLoaderEnvironmentPolicy"] not in {
                "FORBIDDEN_AND_ABSENT", "UNSATISFIED"}):
        malformed("process identity")

    imports = exact_mapping(top["importIdentity"], {
        "projectRoot", "ambientEnvironmentPolicy", "startupCustomizationPolicy",
        "dependencyRoots", "sysPath", "metaPath", "pathHooks",
        "pathImporterCachePolicy", "actualModules",
    }, "import identity")
    ambient = exact_mapping(imports["ambientEnvironmentPolicy"], {
        "forbiddenNames", "status",
    }, "ambient import policy")
    if (imports["projectRoot"] != "PROJECT_ROOT"
            or imports["pathImporterCachePolicy"] !=
            "EXACT_PROCESS_LOCAL_ACTIVATION_SEAL"
            or not isinstance(imports["startupCustomizationPolicy"], str)
            or imports["startupCustomizationPolicy"] not in {
                "FORBIDDEN_AND_ABSENT", "UNSATISFIED"}
            or ambient["forbiddenNames"] != sorted(_AMBIENT_IMPORT_ENVIRONMENT)
            or not isinstance(ambient["status"], str)
            or ambient["status"] not in {"ABSENT", "PRESENT"}):
        malformed("import policy identity")

    provider_keys = {
        "objectKind", "providerModule", "providerQualname",
        "typeModule", "typeQualname",
    }
    for field_name in ("metaPath", "pathHooks"):
        providers = imports[field_name]
        if not isinstance(providers, list) or not providers:
            malformed(f"{field_name} identity")
        for provider in providers:
            provider = exact_mapping(
                provider, provider_keys, f"{field_name} provider identity")
            if (not isinstance(provider["objectKind"], str)
                    or provider["objectKind"] not in {
                        "CLASS", "FUNCTION", "INSTANCE"}
                    or any(not nonempty_text(provider[key])
                           for key in provider_keys - {"objectKind"})):
                malformed(f"{field_name} provider identity")

    distributions = top["distributions"]
    if not isinstance(distributions, list):
        malformed("distribution identity")
    distribution_names = []
    distribution_roots: dict[str, list[dict[str, str]]] = {}
    distribution_files: dict[str, tuple[str, int, set[str]]] = {}
    for distribution in distributions:
        distribution = exact_mapping(distribution, {
            "name", "version", "wheelArchiveDigest", "wheelArchiveByteLength",
            "rootLocator", "files",
        }, "distribution identity")
        root = locator(distribution["rootLocator"], "distribution root locator")
        if (not root.startswith("LOCKED_WHEEL_ROOT[")
                or not nonempty_text(distribution["name"])
                or not nonempty_text(distribution["version"])
                or not valid_digest(distribution["wheelArchiveDigest"])
                or not isinstance(distribution["wheelArchiveByteLength"], int)
                or isinstance(distribution["wheelArchiveByteLength"], bool)
                or distribution["wheelArchiveByteLength"] <= 0
                or not isinstance(distribution["files"], list)):
            malformed("distribution identity")
        file_names = []
        for item in distribution["files"]:
            item = exact_mapping(item, {
                "relativePath", "contentDigest", "byteLength",
            }, "distribution file identity")
            if (not relative_identity(item["relativePath"])
                    or not valid_digest(item["contentDigest"])
                    or not isinstance(item["byteLength"], int)
                    or isinstance(item["byteLength"], bool)
                    or item["byteLength"] < 0):
                malformed("distribution file identity")
            file_names.append(item["relativePath"])
            file_locator = _join_stable_locator(
                distribution["rootLocator"],
                PurePosixPath(item["relativePath"]),
            )
            prior = distribution_files.get(file_locator)
            identity = (item["contentDigest"], item["byteLength"])
            if prior is not None and prior[:2] != identity:
                malformed("distribution shared-file identity")
            distribution_files[file_locator] = (
                *identity,
                {*(prior[2] if prior is not None else set()),
                 distribution["name"]},
            )
        if file_names != sorted(set(file_names)):
            malformed("distribution file inventory")
        distribution_names.append(distribution["name"])
        distribution_roots.setdefault(distribution["rootLocator"], []).append({
            "name": distribution["name"],
            "wheelArchiveDigest": distribution["wheelArchiveDigest"],
        })
    if distribution_names != sorted(set(distribution_names)):
        malformed("distribution inventory")
    for root, members in distribution_roots.items():
        expected = _stable_root_locator(
            "LOCKED_WHEEL_ROOT",
            {"distributions": sorted(members, key=lambda item: item["name"])},
        )
        if root != expected:
            malformed("distribution root content identity")
    dependency_roots = imports["dependencyRoots"]
    if (not isinstance(dependency_roots, list)
            or dependency_roots != sorted(distribution_roots)
            or any(locator(item, "dependency root locator") != item
                   for item in dependency_roots)):
        malformed("dependency root inventory")

    standard = exact_mapping(top["standardRuntime"], {
        "roots", "archives", "sharedLibrary",
    }, "standard runtime identity")
    if not isinstance(standard["roots"], list):
        malformed("standard runtime root inventory")
    standard_roots = []
    standard_files: dict[str, tuple[str, int]] = {}
    for root in standard["roots"]:
        root = exact_mapping(root, {
            "rootLocator", "directories", "files",
        }, "standard runtime root identity")
        root_locator = locator(
            root["rootLocator"], "standard runtime root locator")
        if (not root_locator.startswith("PINNED_IMAGE_ROOT[")
                or not isinstance(root["directories"], list)
                or any(not relative_identity(item) for item in root["directories"])
                or root["directories"] != sorted(set(root["directories"]))
                or not isinstance(root["files"], list)):
            malformed("standard runtime root identity")
        file_names = []
        for item in root["files"]:
            item = exact_mapping(item, {
                "relativePath", "contentDigest", "byteLength",
            }, "standard runtime file identity")
            if (not relative_identity(item["relativePath"])
                    or not valid_digest(item["contentDigest"])
                    or not isinstance(item["byteLength"], int)
                    or isinstance(item["byteLength"], bool)
                    or item["byteLength"] < 0):
                malformed("standard runtime file identity")
            file_names.append(item["relativePath"])
            standard_files[_join_stable_locator(
                root["rootLocator"], PurePosixPath(item["relativePath"]),
            )] = (item["contentDigest"], item["byteLength"])
        if file_names != sorted(set(file_names)):
            malformed("standard runtime file inventory")
        expected = _stable_root_locator("PINNED_IMAGE_ROOT", {
            "directories": root["directories"],
            "files": root["files"],
        })
        if root["rootLocator"] != expected:
            malformed("standard runtime root content identity")
        standard_roots.append(root["rootLocator"])
    if standard_roots != sorted(set(standard_roots)):
        malformed("standard runtime root inventory")
    if not isinstance(standard["archives"], list):
        malformed("standard runtime archive inventory")
    standalone_files: dict[str, tuple[str, int]] = {}

    def standalone_file(value: Any, label: str, kind: str) -> dict:
        entry = digest_file(value, label)
        expected = _stable_root_locator("PINNED_IMAGE_FILE", {
            "kind": kind,
            "contentDigest": entry["contentDigest"],
            "byteLength": entry["byteLength"],
        })
        if entry["originLocator"] != expected:
            malformed(f"{label} content locator")
        prior = standalone_files.get(expected)
        identity = (entry["contentDigest"], entry["byteLength"])
        if prior is not None and prior != identity:
            malformed("standalone runtime file inventory")
        standalone_files[expected] = identity
        return entry

    archive_locators = [
        standalone_file(
            item, "standard runtime archive identity", "ARCHIVE")
        ["originLocator"]
        for item in standard["archives"]
    ]
    if archive_locators != sorted(set(archive_locators)):
        malformed("standard runtime archive inventory")
    if standard["sharedLibrary"] is not None:
        standalone_file(
            standard["sharedLibrary"],
            "standard shared-library identity",
            "SHARED_LIBRARY",
        )

    path_entries = imports["sysPath"]
    if not isinstance(path_entries, list):
        malformed("sys.path identity")
    path_classes = {
        "PINNED_RUNTIME_IMAGE_ROOT", "LOCKED_DEPENDENCY_ROOT",
        "REVIEWED_PROJECT_ROOT",
    }
    for index, item in enumerate(path_entries):
        item = exact_mapping(
            item, {"index", "rootLocator", "classification"},
            "sys.path entry identity")
        root = locator(item["rootLocator"], "sys.path root locator")
        if (not isinstance(item["index"], int)
                or isinstance(item["index"], bool)
                or item["index"] != index
                or not isinstance(item["classification"], str)
                or item["classification"] not in path_classes):
            malformed("sys.path entry identity")
        if (item["classification"] == "REVIEWED_PROJECT_ROOT"
                and item["rootLocator"] != "PROJECT_ROOT"):
            malformed("project sys.path identity")
        if (item["classification"] == "LOCKED_DEPENDENCY_ROOT"
                and item["rootLocator"] not in distribution_roots):
            malformed("dependency sys.path identity")
        if (item["classification"] == "PINNED_RUNTIME_IMAGE_ROOT"
                and root not in standard_roots):
            malformed("runtime-image sys.path identity")

    project_components = {
        (component.role, component.logical_ref): component
        for component in retained_components
        if component.role in {
            "RUNTIME_CODE", "RUNTIME_CATALOG_CODE", "PARSER_CODE"}
        and component.repository_path.endswith(".py")
    }
    project_component_paths = {
        component.repository_path for component in project_components.values()
    }

    def reviewed_project_path(relative: str, *, exact_file: bool) -> bool:
        if relative in project_component_paths:
            return True
        if not exact_file and any(
                path.startswith(relative + "/")
                for path in project_component_paths):
            return True
        for prefix in _PROJECT_TEST_PATHS:
            if prefix.endswith("/"):
                base = prefix.rstrip("/")
                if relative == base or relative.startswith(prefix):
                    return True
            elif relative == prefix:
                return True
        if not exact_file and relative in _PROJECT_TEST_NAMESPACE_PATHS:
            return True
        return False

    modules = imports["actualModules"]
    if not isinstance(modules, list):
        malformed("module inventory")
    module_names = []
    module_classes = {
        "BUILT_IN", "FROZEN", "RETAINED_PROJECT_COMPONENT",
        "RETAINED_DISTRIBUTION_FILE", "PINNED_RUNTIME_IMAGE_FILE",
        "NON_RUNTIME_TEST_HARNESS", "RETAINED_NAMESPACE",
        "REVIEWED_NATIVE_AUXILIARY",
    }
    base_module_keys = {
        "name", "loader", "classification", "originLocator",
        "packageSearchLocators", "specSearchLocators",
    }
    optional_module_keys = {
        "contentDigest", "byteLength", "retainedComponent", "distributions",
        "retainedParent", "originlessStateDigest",
    }
    for module in modules:
        if (not isinstance(module, dict)
                or not base_module_keys <= set(module)
                or set(module) - base_module_keys - optional_module_keys):
            malformed("module identity")
        if (not nonempty_text(module["name"])
                or (module["loader"] is not None
                    and not nonempty_text(module["loader"]))
                or not isinstance(module["classification"], str)
                or module["classification"] not in module_classes
                or not isinstance(module["packageSearchLocators"], list)
                or not isinstance(module["specSearchLocators"], list)):
            malformed("module identity")
        for field_name in ("packageSearchLocators", "specSearchLocators"):
            values = module[field_name]
            for value in values:
                locator(value, "module search locator")
            if len(values) != len(set(values)):
                malformed("module search locator inventory")
        origin = module["originLocator"]
        if origin is not None and not isinstance(origin, str):
            malformed("module origin locator")
        origin_root = None
        if origin not in {None, "built-in", "frozen"}:
            origin_root = locator(origin, "module origin locator")
        if (("contentDigest" in module) != ("byteLength" in module)
                or ("contentDigest" in module
                    and (not valid_digest(module["contentDigest"])
                         or not isinstance(module["byteLength"], int)
                         or isinstance(module["byteLength"], bool)
                         or module["byteLength"] < 0))):
            malformed("module content identity")
        retained = module.get("retainedComponent")
        if retained is not None:
            retained = exact_mapping(
                retained, {"role", "logicalRef"},
                "retained module component identity")
            if any(not nonempty_text(value) for value in retained.values()):
                malformed("retained module component identity")
        owners = module.get("distributions")
        if owners is not None and (
                not isinstance(owners, list)
                or any(not nonempty_text(owner) for owner in owners)
                or owners != sorted(set(owners))
                or any(owner not in distribution_names for owner in owners)):
            malformed("module distribution ownership")
        parent = module.get("retainedParent")
        parent_origin = None
        if parent is not None:
            parent = exact_mapping(parent, {
                "name", "originLocator",
            }, "module retained-parent identity")
            if not nonempty_text(parent["name"]):
                malformed("module retained-parent identity")
            locator(parent["originLocator"], "module retained-parent locator")
            parent_origin = parent["originLocator"]
        classification = module["classification"]
        originless_state = module.get("originlessStateDigest")
        content_identity = (
            (module["contentDigest"], module["byteLength"])
            if "contentDigest" in module else None)
        distribution_identity = (
            distribution_files.get(origin) if isinstance(origin, str) else None)
        standard_identity = (
            standard_files.get(origin) if isinstance(origin, str) else None)
        retained_component = (
            project_components.get((
                retained["role"], retained["logicalRef"]))
            if retained is not None else None)
        origin_parts = _stable_locator_parts(origin)
        namespace_locators = [
            *module["packageSearchLocators"], *module["specSearchLocators"]]
        namespace_suffix = module["name"].replace(".", "/")
        namespace_paths_match = all(
            (parts := _stable_locator_parts(value)) is not None
            and bool(parts[1])
            and (parts[1] == namespace_suffix
                 or parts[1].endswith("/" + namespace_suffix))
            for value in namespace_locators
        )
        if ((classification == "BUILT_IN" and origin != "built-in")
                or (classification == "FROZEN" and origin != "frozen")
                or (classification in {
                    "RETAINED_NAMESPACE", "REVIEWED_NATIVE_AUXILIARY"}
                    and origin is not None)
                or (classification == "RETAINED_NAMESPACE"
                    and (not module["packageSearchLocators"]
                         or module["packageSearchLocators"] !=
                         module["specSearchLocators"]
                         or not namespace_paths_match))
                or ((originless_state is not None) !=
                    (classification in {
                        "RETAINED_NAMESPACE", "REVIEWED_NATIVE_AUXILIARY"}))
                or (originless_state is not None
                    and not valid_digest(originless_state))
                or (classification == "RETAINED_PROJECT_COMPONENT"
                    and (origin_root != "PROJECT_ROOT" or retained is None
                         or content_identity is None
                         or retained_component is None
                         or origin_parts is None
                         or origin_parts[1] !=
                         retained_component.repository_path
                         or content_identity != (
                             retained_component.content_digest,
                             len(retained_component.canonical_bytes))))
                or (classification == "NON_RUNTIME_TEST_HARNESS"
                    and (origin_root != "PROJECT_ROOT"
                         or origin_parts is None
                         or not reviewed_project_path(
                             origin_parts[1], exact_file=True)))
                or (classification == "RETAINED_DISTRIBUTION_FILE"
                    and (origin_root not in distribution_roots or not owners
                         or distribution_identity is None
                         or content_identity != distribution_identity[:2]
                         or owners != sorted(distribution_identity[2])))
                or (classification == "PINNED_RUNTIME_IMAGE_FILE"
                    and (origin_root not in standard_roots
                         or standard_identity is None
                         or content_identity != standard_identity))
                or (classification == "REVIEWED_NATIVE_AUXILIARY"
                    and (parent is None
                         or _REVIEWED_ORIGINLESS_AUXILIARY_MODULES.get(
                             module["name"]) != parent["name"]
                         or (parent_origin not in distribution_files
                             and parent_origin not in standard_files
                             and not (
                                 _stable_locator_root(parent_origin)
                                 == "PROJECT_ROOT"
                                 and _stable_locator_parts(parent_origin)
                                 is not None
                                 and reviewed_project_path(
                                     _stable_locator_parts(parent_origin)[1],
                                     exact_file=True)))))
                or ((retained is not None)
                    != (classification == "RETAINED_PROJECT_COMPONENT"))
                or ((owners is not None)
                    != (classification == "RETAINED_DISTRIBUTION_FILE"))):
            malformed("module classification identity")
        module_names.append(module["name"])
    if module_names != sorted(set(module_names)):
        malformed("module inventory")
    modules_by_name = {module["name"]: module for module in modules}
    for module in modules:
        if module["classification"] != "REVIEWED_NATIVE_AUXILIARY":
            continue
        parent = module["retainedParent"]
        parent_module = modules_by_name.get(parent["name"])
        if (parent_module is None
                or parent_module["classification"] not in {
                    "RETAINED_PROJECT_COMPONENT",
                    "RETAINED_DISTRIBUTION_FILE",
                    "PINNED_RUNTIME_IMAGE_FILE",
                    "NON_RUNTIME_TEST_HARNESS",
                }
                or parent_module["originLocator"] != parent["originLocator"]):
            malformed("module retained-parent identity")

    native = exact_mapping(top["nativeRuntime"], {
        "imageIdentity", "containerBoundary", "loaderConfiguration",
        "kernelExecutableMappingPolicy", "actualNativeImages",
    }, "native runtime identity")
    image = exact_mapping(native["imageIdentity"], {
        "reference", "indexDigest", "platform", "platformManifestDigest",
        "configDigest", "layers",
    }, "runtime image identity")
    if (not nonempty_text(image["reference"])
            or image["platform"] != "linux/amd64"
            or any(not valid_digest(image[key]) for key in (
                "indexDigest", "platformManifestDigest", "configDigest"))
            or not isinstance(image["layers"], list)
            or not image["layers"]):
        malformed("runtime image identity")
    if image != image_manifest["image"]:
        malformed("runtime image retained identity")
    for layer in image["layers"]:
        layer = exact_mapping(
            layer, {"digest", "byteLength"}, "runtime image layer identity")
        if (not valid_digest(layer["digest"])
                or not isinstance(layer["byteLength"], int)
                or isinstance(layer["byteLength"], bool)
                or layer["byteLength"] <= 0):
            malformed("runtime image layer identity")
    if (not isinstance(native["containerBoundary"], str)
            or native["containerBoundary"] not in {
            "PINNED_READ_ONLY_IMAGE", "UNSATISFIED"}
            or native["kernelExecutableMappingPolicy"] != "VDSO_VSYSCALL_ONLY"):
        malformed("native runtime policy identity")
    loader = exact_mapping(native["loaderConfiguration"], {
        "files", "requiredAbsentLocators",
    }, "native loader identity")
    if (not isinstance(loader["files"], list)
            or not isinstance(loader["requiredAbsentLocators"], list)):
        malformed("native loader identity")
    loader_locators = [
        digest_file(item, "native loader file identity")["originLocator"]
        for item in loader["files"]
    ]
    absent_locators = loader["requiredAbsentLocators"]
    for item in absent_locators:
        locator(item, "required-absent native locator")
    if (loader_locators != sorted(set(loader_locators))
            or absent_locators != sorted(set(absent_locators))):
        malformed("native loader inventory")
    images = native["actualNativeImages"]
    if not isinstance(images, list):
        malformed("native image inventory")
    native_order = []
    for item in images:
        item = exact_mapping(item, {
            "originLocator", "contentDigest", "byteLength", "classification",
            "distributions",
        }, "native image identity")
        origin_root = locator(item["originLocator"], "native image locator")
        if (not valid_digest(item["contentDigest"])
                or not isinstance(item["byteLength"], int)
                or isinstance(item["byteLength"], bool)
                or item["byteLength"] <= 0
                or not isinstance(item["classification"], str)
                or item["classification"] not in {
                    "PINNED_RUNTIME_IMAGE_FILE", "RETAINED_DISTRIBUTION_FILE",
                }
                or not isinstance(item["distributions"], list)
                or any(not nonempty_text(owner)
                       for owner in item["distributions"])
                or item["distributions"] != sorted(set(item["distributions"]))
                or any(owner not in distribution_names
                       for owner in item["distributions"])
                or (item["classification"] != "RETAINED_DISTRIBUTION_FILE"
                    and item["distributions"])
                or (item["classification"] == "RETAINED_DISTRIBUTION_FILE"
                    and (origin_root not in distribution_roots
                         or not item["distributions"]
                         or item["originLocator"] not in distribution_files
                         or (item["contentDigest"], item["byteLength"])
                         != distribution_files[item["originLocator"]][:2]
                         or item["distributions"] != sorted(
                             distribution_files[item["originLocator"]][2])))
                or (item["classification"] == "PINNED_RUNTIME_IMAGE_FILE"
                    and (item["distributions"]
                         or origin_root not in {
                             *standard_roots, *standalone_files,
                             "PINNED_IMAGE_ROOTFS"}
                         or (origin_root in standard_roots
                             and ((item["contentDigest"], item["byteLength"])
                                  != standard_files.get(
                                      item["originLocator"])))
                         or (origin_root in standalone_files
                             and ((item["contentDigest"], item["byteLength"])
                                  != standalone_files.get(
                                      item["originLocator"])))))):
            malformed("native image identity")
        native_order.append((
            item["originLocator"], item["contentDigest"], item["classification"]))
    if native_order != sorted(set(native_order)):
        malformed("native image inventory")

    manifest_rootfs_files: dict[str, tuple[str, int]] = {}

    def retained_rootfs_locator(path: str) -> str:
        physical = Path(path)
        return _join_stable_locator(
            "PINNED_IMAGE_ROOTFS",
            PurePosixPath(physical.relative_to(physical.anchor).as_posix()),
        )

    manifest_python = image_manifest["python"]
    manifest_entries = [
        manifest_python["executable"],
        manifest_python["sharedLibrary"],
        *manifest_python["nativeFiles"],
        *manifest_python["loaderConfigurationFiles"],
        *manifest_python["requiredExecutables"],
        *(entry
          for root in manifest_python["standardLibraryRoots"]
          for entry in root["files"]),
    ]
    for entry in manifest_entries:
        retained_locator = retained_rootfs_locator(entry["path"])
        identity = (entry["contentDigest"], entry["byteLength"])
        prior = manifest_rootfs_files.get(retained_locator)
        if prior is not None and prior != identity:
            malformed("retained runtime image file inventory")
        manifest_rootfs_files[retained_locator] = identity
    manifest_absent_locators = {
        retained_rootfs_locator(path)
        for path in manifest_python["requiredAbsentPaths"]
    }
    expected_loader_files = sorted(({
        "originLocator": retained_rootfs_locator(entry["path"]),
        "contentDigest": entry["contentDigest"],
        "byteLength": entry["byteLength"],
    } for entry in manifest_python["loaderConfigurationFiles"]),
        key=lambda entry: entry["originLocator"])
    expected_absent_locators = sorted(manifest_absent_locators)
    if native["containerBoundary"] == "PINNED_READ_ONLY_IMAGE":
        if (loader["files"] != expected_loader_files
                or absent_locators != expected_absent_locators
                or not images):
            malformed("retained native runtime inventory")
    elif loader["files"] or absent_locators or images:
        malformed("unsatisfied native runtime inventory")

    for entry in loader["files"]:
        if (_stable_locator_root(entry["originLocator"])
                == "PINNED_IMAGE_ROOTFS"
                and manifest_rootfs_files.get(entry["originLocator"]) != (
                    entry["contentDigest"], entry["byteLength"])):
            malformed("native loader retained-file identity")
    for entry in images:
        if (_stable_locator_root(entry["originLocator"])
                == "PINNED_IMAGE_ROOTFS"
                and manifest_rootfs_files.get(entry["originLocator"]) != (
                    entry["contentDigest"], entry["byteLength"])):
            malformed("native retained-image file identity")
    if any(item not in manifest_absent_locators for item in absent_locators):
        malformed("native required-absence retained identity")

    declared_roots = {
        "PROJECT_ROOT", "PINNED_IMAGE_ROOTFS",
        *distribution_roots, *standard_roots, *standalone_files,
    }

    def inventory_contains_path(
            value: str,
            inventory: Mapping[str, object],
    ) -> bool:
        parts = _stable_locator_parts(value)
        if parts is None:
            return False
        root, suffix = parts
        if not suffix:
            return True
        for retained in inventory:
            retained_parts = _stable_locator_parts(retained)
            if retained_parts is None or retained_parts[0] != root:
                continue
            retained_suffix = retained_parts[1]
            if retained_suffix == suffix \
                    or retained_suffix.startswith(suffix + "/"):
                return True
        return False

    for item in locators:
        parts = _stable_locator_parts(item)
        if parts is None or parts[0] not in declared_roots:
            malformed("locator closure")
        root = parts[0]
        if (root in distribution_roots
                and not inventory_contains_path(item, distribution_files)):
            malformed("distribution locator inventory closure")
        if (root in standard_roots
                and not inventory_contains_path(item, standard_files)):
            malformed("standard runtime locator inventory closure")
        if (root == "PINNED_IMAGE_ROOTFS"
                and item not in manifest_rootfs_files
                and item not in manifest_absent_locators):
            malformed("pinned-image rootfs locator inventory closure")
        if (root == "PROJECT_ROOT" and parts[1]
                and not reviewed_project_path(
                    parts[1], exact_file=False)):
            malformed("project locator inventory closure")
        if root in standalone_files and parts[1]:
            malformed("standalone runtime file locator closure")

    forbidden_keys = {
        "path", "resolvedPath", "root", "origin", "device", "inode",
        "pycachePrefix", "pycachePrefixExists", "pathImporterCache",
        "kernelExecutableMappings",
    }

    def inspect(value: Any) -> None:
        if isinstance(value, dict):
            if forbidden_keys.intersection(value):
                raise RuntimeBundleError(
                    "stable runtime identity contains a process-local field")
            for key, item in value.items():
                if not isinstance(key, str):
                    malformed("identity key")
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)
        elif isinstance(value, str) and value.startswith("/"):
            raise RuntimeBundleError(
                "stable runtime identity contains an absolute physical path")

    inspect(document)
    try:
        canonical_json(document)
    except (TypeError, ValueError) as exc:
        raise RuntimeBundleError(
            "stable runtime identity is not canonical JSON") from exc


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
    retained_components: Iterable[RuntimeComponent] | None = None,
) -> RuntimeComponent:
    """Bind the bundle to flags, paths, imported origins, and runtime bytes."""
    package_root = (package_root or Path(__file__).resolve().parents[1]).resolve()
    if retained_components is None:
        retained_components = _locked_components(package_root)
    retained_components = tuple(retained_components)
    return _runtime_environment_component_from_document(
        _runtime_environment_document(package_root, retained_components),
        retained_components,
    )


def _runtime_environment_component_from_document(
    document: dict[str, Any],
    retained_components: Iterable[RuntimeComponent],
) -> RuntimeComponent:
    _validate_runtime_environment_document(document)
    stable = _stable_runtime_environment_document(
        document, retained_components)
    canonical = canonical_json(stable).encode("utf-8")
    return RuntimeComponent(
        role="RUNTIME_ENVIRONMENT_OBSERVED",
        logical_ref=_OBSERVED_ENVIRONMENT_REF,
        repository_path="runtime-observed/environment-v4",
        canonicalization=JSON_CANONICALIZATION,
        content_digest=sha256_bytes(canonical),
        canonical_bytes=canonical,
        placement=GLOBAL_CONTENT_PLACEMENT,
    )


def _decision_semantics_component_from_canonical(
        canonical: bytes,
) -> RuntimeComponent:
    document = _strict_json_value(
        canonical, "stable decision semantics identity")
    _validate_stable_decision_semantics_document(document)
    if canonical_json(document).encode("utf-8") != canonical:
        raise RuntimeBundleError(
            "stable decision semantics identity is not canonical")
    return RuntimeComponent(
        role="RUNTIME_ENVIRONMENT_OBSERVED",
        logical_ref=_DECISION_SEMANTICS_REF,
        repository_path="runtime-observed/decision-semantics-v1",
        canonicalization=JSON_CANONICALIZATION,
        content_digest=sha256_bytes(canonical),
        canonical_bytes=canonical,
        placement=GLOBAL_CONTENT_PLACEMENT,
    )


def observed_decision_semantics_component(
        package_root: Path,
) -> RuntimeComponent:
    _require_decision_receipt_implementation()
    selected = _capture_decision_semantics()
    canonical = canonical_json(_stable_decision_semantics_document(
        selected, package_root.resolve())).encode("utf-8")
    _require_decision_receipt_implementation()
    return _decision_semantics_component_from_canonical(canonical)


def _module_origin_stat_signature(module: object) -> tuple[Any, ...]:
    spec = getattr(module, "__spec__", None)
    origin = getattr(spec, "origin", None) or getattr(module, "__file__", None)
    package_paths, spec_paths = _module_search_paths(module)
    module_name = getattr(module, "__name__", None)
    originless_state = None
    originless_object_anchors: tuple[tuple[str, object], ...] = ()
    if (isinstance(module_name, str)
            and origin is None
            and (package_paths
                 or module_name in _REVIEWED_ORIGINLESS_AUXILIARY_MODULES)):
        if package_paths and not _namespace_module_state_is_closed(
                module_name, module):
            raise RuntimeBundleError(
                f"originless namespace module state changed: {module_name}")
        originless_state = _originless_module_state_digest(
            module_name, module, Path(__file__).resolve().parents[1])
        originless_object_anchors = tuple(
            (name, value) for name, value in sorted(vars(module).items())
            if name not in _NAMESPACE_MODULE_METADATA
            and type(value) is types.ModuleType
        )
    import_state = (
        module_name,
        getattr(module, "__package__", None),
        spec,
        getattr(spec, "name", None),
        getattr(spec, "parent", None),
        getattr(spec, "origin", None),
        getattr(spec, "has_location", None),
        getattr(spec, "cached", None),
        getattr(module, "__file__", None),
        getattr(module, "__cached__", None),
        tuple(package_paths), tuple(spec_paths),
        getattr(module, "__path__", None),
        getattr(spec, "submodule_search_locations", None),
        getattr(module, "__loader__", None),
        getattr(spec, "loader", None),
        originless_state,
        originless_object_anchors,
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
    _require_decision_receipt_implementation()
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
    decision_semantics = _capture_decision_semantics()
    decision_semantics_canonical = canonical_json(
        _stable_decision_semantics_document(
            decision_semantics,
            Path(document["importPosture"]["projectRoot"]),
        )
    ).encode("utf-8")
    _require_decision_receipt_implementation()
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
        decision_semantics=decision_semantics,
        decision_callable_anchors=_decision_semantic_callable_anchors(
            decision_semantics),
        decision_semantics_canonical=decision_semantics_canonical,
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
    _require_runtime_bundle_integrity(bundle)
    _require_runtime_environment_seal_integrity(bundle, seal)
    if type(seal) is not RuntimeEnvironmentSeal or seal.bundle_digest != bundle.digest:
        raise RuntimeBundleError(
            "runtime environment seal does not belong to this RuntimeBundle")
    if tuple(sorted(_python_flags_document().items())) != seal.flags:
        raise RuntimeBundleError("live Python import flags changed after activation")
    _require_decision_semantics(seal.decision_semantics)
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
    _validate_stable_runtime_environment_document(observed, bundle.components)
    if _stable_runtime_environment_document(
            current_document, bundle.components) != observed:
        raise RuntimeBundleError(
            "observed interpreter, import posture, or runtime bytes changed after selection")
    selected_semantics = bundle.component(
        "RUNTIME_ENVIRONMENT_OBSERVED", _DECISION_SEMANTICS_REF)
    _validate_stable_decision_semantics_document(_strict_json_value(
        selected_semantics.canonical_bytes,
        "selected stable decision semantics identity"))
    if observed_decision_semantics_component(package_root) != selected_semantics:
        raise RuntimeBundleError(
            "observed decision semantics changed after RuntimeBundle selection")
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
    if _stable_runtime_environment_document(
            final_document, bundle.components) != observed:
        raise RuntimeBundleError(
            "Python runtime identity changed while activation was being sealed")
    seal = bundle._selection_environment_seal
    if type(seal) is not RuntimeEnvironmentSeal:
        raise RuntimeBundleError(
            "live RuntimeBundle has no selection-time runtime environment seal")
    if seal.decision_semantics_canonical != selected_semantics.canonical_bytes:
        raise RuntimeBundleError(
            "live RuntimeBundle decision semantics receipt differs from its seal")
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
        if (type(self.family_id) is not str
                or type(self.snapshot_ref) is not str
                or type(self.snapshot_payload_digest) is not str
                or type(self.source_identities) is not tuple
                or type(self.source_byte_status) is not str
                or type(self.unavailable_source_identities) is not tuple
                or (self.data_family is not None
                    and type(self.data_family) is not str)
                or (self.data_payload_digest is not None
                    and type(self.data_payload_digest) is not str)
                or (self.source_digest is not None
                    and type(self.source_digest) is not str)):
            raise RuntimeBundleError(
                "selected-reference identity field types are malformed")
        if self.source_byte_status not in {"LOCKED", "PROVENANCE_LOCATOR_ONLY"}:
            raise RuntimeBundleError("unknown selected-reference source byte status")
        if (not isinstance(self.family_id, str) or not self.family_id
                or not isinstance(self.snapshot_ref, str) or not self.snapshot_ref
                or any(type(ref) is not str or not ref
                       for ref in self.source_identities)
                or any(type(ref) is not str or not ref
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
        if (type(self.digest) is not str
                or type(self.bundle_ref) is not str
                or type(self.canonical_document_bytes) is not bytes
                or type(self.components) is not tuple
                or type(self.selected_references) is not tuple
                or type(self.construction_mode) is not str):
            raise RuntimeBundleError("RuntimeBundle field types are not immutable")
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
        _validate_stable_runtime_environment_document(
            _strict_json_value(
                environment_component.canonical_bytes,
                "RuntimeBundle Python environment observation"),
            self.components,
        )
        semantics_component = component_map.get(
            ("RUNTIME_ENVIRONMENT_OBSERVED", _DECISION_SEMANTICS_REF))
        if (semantics_component is None
                or semantics_component.repository_path !=
                "runtime-observed/decision-semantics-v1"):
            raise RuntimeBundleError(
                "RuntimeBundle has no stable decision semantics identity")
        _validate_stable_decision_semantics_document(_strict_json_value(
            semantics_component.canonical_bytes,
            "RuntimeBundle decision semantics identity"))
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


def _require_runtime_bundle_integrity(bundle: object) -> None:
    """Re-run immutable bundle/component validation at every decision boundary."""
    if type(bundle) is not RuntimeBundle:
        raise RuntimeBundleError("governed runtime requires an exact RuntimeBundle")
    bundle_fields = {item.name for item in dataclass_fields(RuntimeBundle)}
    if set(vars(bundle)) != bundle_fields:
        raise RuntimeBundleError("RuntimeBundle instance state is not closed")
    for component in bundle.components:
        if (type(component) is not RuntimeComponent
                or set(vars(component)) != {
                    item.name for item in dataclass_fields(RuntimeComponent)}):
            raise RuntimeBundleError("RuntimeBundle component instance state is not closed")
        RuntimeComponent.__post_init__(component)
    for reference in bundle.selected_references:
        if (type(reference) is not SelectedReferenceIdentity
                or set(vars(reference)) != {
                    item.name for item in dataclass_fields(
                        SelectedReferenceIdentity)}):
            raise RuntimeBundleError(
                "RuntimeBundle selected-reference instance state is not closed")
        SelectedReferenceIdentity.__post_init__(reference)
    proof = (
        _LIVE_SELECTION_PROOF
        if bundle.construction_mode == "LIVE_CURRENT" else None)
    RuntimeBundle.__post_init__(bundle, proof)


def _require_runtime_environment_seal_integrity(
        bundle: RuntimeBundle,
        seal: RuntimeEnvironmentSeal,
) -> None:
    """Cross-check a mutable Python dataclass seal against retained bytes."""
    tuple_fields = (
        seal.flags, seal.ambient, seal.native_loader_environment,
        seal.native_runtime_stat, seal.customization, seal.sys_path,
        seal.meta_path, seal.path_hooks, seal.meta_path_objects,
        seal.path_hook_objects, seal.path_importer_cache,
        seal.path_importer_cache_objects, seal.import_callable_state,
        seal.modules, seal.decision_semantics, seal.decision_callable_anchors,
    )
    if (type(seal) is not RuntimeEnvironmentSeal
            or set(vars(seal)) != {
                item.name for item in dataclass_fields(RuntimeEnvironmentSeal)}
            or type(seal.bundle_digest) is not str
            or type(seal.native_runtime) is not str
            or any(type(value) is not tuple for value in tuple_fields)
            or type(seal.decision_semantics_canonical) is not bytes
            or type(seal.project_root) is not str
            or (seal.pycache_prefix is not None
                and type(seal.pycache_prefix) is not str)
            or any(type(entry) is not tuple or len(entry) != 7
                   or type(entry[3]) is not str
                   for entry in seal.decision_semantics)
            or any(type(entry) is not tuple or len(entry) != 2
                   or type(entry[0]) is not types.FunctionType
                   or type(entry[1]) is not types.CodeType
                   for entry in seal.decision_callable_anchors)
            or seal.bundle_digest != bundle.digest
            or not seal.decision_semantics):
        raise RuntimeBundleError(
            "runtime environment seal structure differs from its RuntimeBundle")
    _require_decision_receipt_implementation()
    stable = canonical_json(_stable_decision_semantics_document(
        seal.decision_semantics, Path(seal.project_root))).encode("utf-8")
    selected = RuntimeBundle.component(
        bundle, "RUNTIME_ENVIRONMENT_OBSERVED", _DECISION_SEMANTICS_REF)
    if (stable != seal.decision_semantics_canonical
            or stable != selected.canonical_bytes):
        raise RuntimeBundleError(
            "runtime environment seal semantics differ from retained bytes")
    expected_anchors = _decision_semantic_callable_anchors(
        seal.decision_semantics)
    if (len(expected_anchors) != len(seal.decision_callable_anchors)
            or any(
                current_function is not selected_function
                or current_code is not selected_code
                for (current_function, current_code),
                (selected_function, selected_code)
                in zip(expected_anchors, seal.decision_callable_anchors))):
        raise RuntimeBundleError(
            "runtime environment seal callable anchors are incomplete")


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
            _observed_python_environment, tuple(component_map.values())))
    else:
        add_component(observed_runtime_environment_component(
            package_root, tuple(component_map.values())))
    if _selection_environment_seal is not None:
        _require_decision_semantics(
            _selection_environment_seal.decision_semantics)
        add_component(_decision_semantics_component_from_canonical(
            _selection_environment_seal.decision_semantics_canonical))
    else:
        add_component(observed_decision_semantics_component(package_root))
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
