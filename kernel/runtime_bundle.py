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
import base64
import hashlib
import importlib.metadata
import json
import locale
import os
import platform
import re
import sys
import sysconfig
import time
from dataclasses import InitVar, dataclass
from pathlib import Path
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
_OBSERVED_ENVIRONMENT_REF = "environment:observed-runtime.v1"
_OBSERVED_DATABASE_REF = "environment:observed-postgresql.v1"
_PROFILE_ROUTE_SELECTION_REF = "profile-route-selection:active"


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
    current_observed = observed_runtime_environment_component()
    if actual.get(observed_key) != current_observed:
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


def observed_runtime_environment_component() -> RuntimeComponent:
    """Bind the bundle to the interpreter and installed distribution bytes."""
    distributions = []
    for distribution in importlib.metadata.distributions():
        raw_name = distribution.metadata.get("Name")
        if not raw_name:
            continue
        name = re.sub(r"[-_.]+", "-", raw_name).lower()
        files = []
        for relative in sorted(distribution.files or (), key=lambda item: str(item)):
            path = Path(distribution.locate_file(relative))
            if not path.is_file():
                raise RuntimeBundleError(
                    f"installed distribution file is missing: {name}/{relative}")
            exact = path.read_bytes()
            recorded_hash = getattr(relative, "hash", None)
            if recorded_hash is not None:
                try:
                    recorded = base64.urlsafe_b64decode(
                        recorded_hash.value + "=" * (-len(recorded_hash.value) % 4))
                    observed_hash = hashlib.new(recorded_hash.mode, exact).digest()
                except (ValueError, TypeError) as exc:
                    raise RuntimeBundleError(
                        f"installed distribution hash metadata is invalid: "
                        f"{name}/{relative}") from exc
                if observed_hash != recorded:
                    raise RuntimeBundleError(
                        f"installed distribution bytes differ from RECORD: "
                        f"{name}/{relative}")
            files.append({
                "path": str(relative).replace("\\", "/"),
                "contentDigest": sha256_bytes(exact),
                "byteLength": len(exact),
            })
        distributions.append({
            "name": name,
            "version": distribution.version,
            "files": files,
        })
    distributions.sort(key=lambda item: item["name"])
    names = [item["name"] for item in distributions]
    if len(names) != len(set(names)):
        raise RuntimeBundleError(
            "multiple installed distributions normalize to the same name")
    executable = Path(sys.executable).resolve(strict=True).read_bytes()
    document = {
        "schemaVersion": "ofarm.runtime-environment-observation.local.v1",
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "cacheTag": sys.implementation.cache_tag,
            "soabi": sysconfig.get_config_var("SOABI"),
            "optimizationLevel": sys.flags.optimize,
            "hashSeedEnvironment": os.environ.get("PYTHONHASHSEED"),
            "executableDigest": sha256_bytes(executable),
            "executableByteLength": len(executable),
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
        },
        "distributions": distributions,
    }
    canonical = canonical_json(document).encode("utf-8")
    return RuntimeComponent(
        role="RUNTIME_ENVIRONMENT_OBSERVED",
        logical_ref=_OBSERVED_ENVIRONMENT_REF,
        repository_path="runtime-observed/environment-v1",
        canonicalization=JSON_CANONICALIZATION,
        content_digest=sha256_bytes(canonical),
        canonical_bytes=canonical,
        placement=GLOBAL_CONTENT_PLACEMENT,
    )


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
        "intervalStyle", "searchPath", "standardConformingStrings",
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


def assert_runtime_environment_compatible(bundle: "RuntimeBundle") -> dict[str, Any]:
    """Fail closed when observed execution differs from the retained baseline."""
    observed_component = bundle.component(
        "RUNTIME_ENVIRONMENT_OBSERVED", _OBSERVED_ENVIRONMENT_REF)
    current_component = observed_runtime_environment_component()
    if observed_component != current_component:
        raise RuntimeBundleError(
            "observed interpreter or installed distribution bytes changed after selection")
    observed = bundle.json_component(
        "RUNTIME_ENVIRONMENT_OBSERVED", _OBSERVED_ENVIRONMENT_REF)
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
    return required


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
    _live_selection_proof: InitVar[object | None] = None

    def __post_init__(self, _live_selection_proof) -> None:
        if self.construction_mode not in {"LIVE_CURRENT", "PERSISTED_AUDIT"}:
            raise RuntimeBundleError("RuntimeBundle construction mode is unverified")
        if ((self.construction_mode == "LIVE_CURRENT")
                != (_live_selection_proof is _LIVE_SELECTION_PROOF)):
            raise RuntimeBundleError(
                "RuntimeBundle live-selection provenance is unverified")
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

    add_component(observed_runtime_environment_component())
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
        _live_selection_proof=_live_selection_proof,
    )


def _build_live_runtime_bundle(descriptor, **kwargs) -> RuntimeBundle:
    """Internal startup path: mark only the under-lock selection as live."""
    if kwargs.get("_database_environment") is None:
        raise RuntimeBundleError(
            "live RuntimeBundle selection requires a PostgreSQL environment observation")
    return build_runtime_bundle(
        descriptor,
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
