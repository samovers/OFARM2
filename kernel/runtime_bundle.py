"""Stable, content-addressed runtime selection for issue #171.
Bundles contain explicit selected content: canonical JSON or exact raw bytes.
Absolute paths and process observations never enter stable identity.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, DecimalException
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import jsonschema


BUNDLE_SCHEMA_VERSION = "ofarm.runtime-bundle.local.v1"
COMPONENT_CATALOG_VERSION = "ofarm.runtime-component-catalog.local.v1"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_LOGICAL_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,1023}$")
_TENANT_REF_RE = re.compile(r"^tenant:[A-Za-z0-9._:-]{1,248}$")
_CONTEXT_SCOPE_REF_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
# CPython's minimum enabled integer-string conversion limit is 640 digits.
# This is the largest bound that parsing and encoding can always honor.
_MAX_CANONICAL_INTEGER_DIGITS = 640
_MAX_CANONICAL_INTEGER_MAGNITUDE = 10 ** _MAX_CANONICAL_INTEGER_DIGITS
_CANONICAL_INTEGER_LIMIT_ERROR = (
    "JSON integer exceeds the canonical limit of "
    f"{_MAX_CANONICAL_INTEGER_DIGITS} decimal digits"
)
_CANONICAL_OBJECT_KEY_ERROR = "JSON object keys must be strings"
_CANONICAL_CYCLE_ERROR = "canonical JSON value must not contain cycles"
_CANONICAL_CONTAINER_IDENTITY_ERROR = (
    "canonical JSON container identity was reused inconsistently"
)
_CONTEXT_SCOPE_TYPES = frozenset({
    "FARM",
    "SITE",
    "FIELD",
    "ZONE",
    "CROP_CYCLE",
    "LOT",
    "FACILITY",
    "OPERATION",
    "DEPLOYMENT",
    "TENANT",
})


class RuntimeBundleError(RuntimeError):
    """Selected runtime content is missing, malformed, or inconsistent."""


class RuntimeComponentRole(str, Enum):
    PROFILE_DESCRIPTOR = "PROFILE_DESCRIPTOR"
    ACTIVE_MANIFEST = "ACTIVE_MANIFEST"
    PROFILE_INSTANCE = "PROFILE_INSTANCE"
    PROFILE_POLICY = "PROFILE_POLICY"
    QUERY_SPECIFICATION = "QUERY_SPECIFICATION"
    QUERY_PLAN = "QUERY_PLAN"
    VIEW_BINDING = "VIEW_BINDING"
    CONTRACT_SCHEMA = "CONTRACT_SCHEMA"
    DRAFT_CONTRACT_SCHEMA = "DRAFT_CONTRACT_SCHEMA"
    VALIDATOR_SOURCE = "VALIDATOR_SOURCE"
    ADAPTER_SOURCE = "ADAPTER_SOURCE"
    QUERY_OUTPUT_SOURCE = "QUERY_OUTPUT_SOURCE"
    REFERENCE_SNAPSHOT = "REFERENCE_SNAPSHOT"
    REFERENCE_SOURCE = "REFERENCE_SOURCE"
    TEMPORAL_GOVERNANCE_ARTIFACT = "TEMPORAL_GOVERNANCE_ARTIFACT"


class Canonicalization(str, Enum):
    CANONICAL_JSON = "OFARM_CANONICAL_JSON_V1"
    EXACT_BYTES = "EXACT_BYTES_V1"


class ContentPlacement(str, Enum):
    GLOBAL = "GLOBAL_IMMUTABLE_CONTENT"
    TENANT = "TENANT_RUNTIME_SELECTION"


@dataclass(frozen=True, slots=True)
class _TemporalGovernanceArtifactRule:
    logical_ref: str
    schema_version: str
    identity_field: str
    canonical_byte_length: int
    content_digest: str
    schema_logical_ref: str
    schema_byte_length: int
    schema_content_digest: str


_TEMPORAL_GOVERNANCE_ARTIFACT_RULES = (
    _TemporalGovernanceArtifactRule(
        logical_ref="ofarm.temporal-carrier-matrix.adr0002.v0.1",
        schema_version="ofarm.temporal-carrier-matrix.v0.1",
        identity_field="matrixId",
        canonical_byte_length=9504,
        content_digest=(
            "sha256:c404c0cd1e08f389664b5381c2c038cf65bac9a3b725fc2b1882990636eb179b"
        ),
        schema_logical_ref="contract:ofarm.temporal-carrier-matrix.v0.1",
        schema_byte_length=3088,
        schema_content_digest=(
            "sha256:cdb5c09ec033cc3b4de1dea9eb383c499045d8a3bfc5b80fd7abeab579a566ed"
        ),
    ),
    _TemporalGovernanceArtifactRule(
        logical_ref="ofarm.temporal-carrier-selection.intervention.v0.1",
        schema_version="ofarm.temporal-carrier-selection-binding.v0.1",
        identity_field="bindingId",
        canonical_byte_length=1814,
        content_digest=(
            "sha256:373a5f402ad077039946c1dfe7b972e4382d3c6a6805fbf0b271e4a0bc729bf1"
        ),
        schema_logical_ref=(
            "contract:ofarm.temporal-carrier-selection-binding.v0.1"
        ),
        schema_byte_length=3340,
        schema_content_digest=(
            "sha256:d252420507393d1d9816a0f20549faa8cf67c94bd1e2c10a3c509aadf4f3800a"
        ),
    ),
    _TemporalGovernanceArtifactRule(
        logical_ref=(
            "ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1"
        ),
        schema_version="ofarm.temporal-governed-command-binding.v0.1",
        identity_field="bindingId",
        canonical_byte_length=9614,
        content_digest=(
            "sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1"
        ),
        schema_logical_ref=(
            "contract:ofarm.temporal-governed-command-binding.v0.1"
        ),
        schema_byte_length=13132,
        schema_content_digest=(
            "sha256:afda003df90e2787cfdc97f5561e3e5b098177a5add91556af2e935a3b9711db"
        ),
    ),
)


_JSON_COMPONENT_RULES = {
    RuntimeComponentRole.PROFILE_DESCRIPTOR: (
        "descriptorVersion", "ofarm.profile-runtime-descriptor.local.v0_1",
        "profileRef", ContentPlacement.TENANT,
    ),
    RuntimeComponentRole.PROFILE_POLICY: (
        None, None, "policyId", ContentPlacement.GLOBAL,
    ),
    RuntimeComponentRole.REFERENCE_SNAPSHOT: (
        "schemaVersion", "ofarm.referencesnapshot.v0.1",
        "referenceSnapshotId", ContentPlacement.GLOBAL,
    ),
    RuntimeComponentRole.ACTIVE_MANIFEST: (
        "schemaVersion", "ofarm.capabilitymanifest.v0.1",
        "manifestId", ContentPlacement.TENANT,
    ),
    RuntimeComponentRole.QUERY_SPECIFICATION: (
        "schemaVersion", "ofarm.queryspec.v0.1",
        "queryId", ContentPlacement.GLOBAL,
    ),
    RuntimeComponentRole.QUERY_PLAN: (
        "schemaVersion", "ofarm.queryplanir.v0.1",
        "planId", ContentPlacement.TENANT,
    ),
    RuntimeComponentRole.VIEW_BINDING: (
        "schemaVersion", "ofarm.runtime-view-binding.local.v1",
        "viewRef", ContentPlacement.GLOBAL,
    ),
}
_PROFILE_INSTANCE_RULES = {
    "ofarm.agronomiccodebindingprofile.v0.1": (
        "agronomicCodeBindingProfileId", ContentPlacement.GLOBAL),
    "ofarm.packactivationset.v0.1": (
        "packActivationSetId", ContentPlacement.TENANT),
    "ofarm.activeartifactset.v0.1": (
        "activeArtifactSetId", ContentPlacement.TENANT),
    "ofarm.contextsnapshot.v0.1": (
        "contextSnapshotId", ContentPlacement.TENANT),
}
_EXACT_GLOBAL_COMPONENT_ROLES = frozenset({
    RuntimeComponentRole.REFERENCE_SOURCE,
    RuntimeComponentRole.VALIDATOR_SOURCE,
    RuntimeComponentRole.ADAPTER_SOURCE,
    RuntimeComponentRole.QUERY_OUTPUT_SOURCE,
})
_ACTIVE_REF_ROLES = {
    "queryspec": RuntimeComponentRole.QUERY_SPECIFICATION,
    "queryplan": RuntimeComponentRole.QUERY_PLAN,
    "view": RuntimeComponentRole.VIEW_BINDING,
    "policy": RuntimeComponentRole.PROFILE_POLICY,
    "codebindingprofile": RuntimeComponentRole.PROFILE_INSTANCE,
    "referencesnapshot": RuntimeComponentRole.REFERENCE_SNAPSHOT,
    "manifest": RuntimeComponentRole.ACTIVE_MANIFEST,
}
_DRAFT_CONTRACT_DIRECTORY = (
    "contracts/drafts_reference/explainable_current_state_evidence"
)
_CONTRACT_REGISTRY_DIRECTORIES = (
    "contracts/kernel",
    "contracts/core",
    "contracts/platform",
    _DRAFT_CONTRACT_DIRECTORY,
)
_CONTRACT_SCHEMA_ROLES = frozenset({
    RuntimeComponentRole.CONTRACT_SCHEMA,
    RuntimeComponentRole.DRAFT_CONTRACT_SCHEMA,
})
_VIEW_BINDING_FIELDS = {
    "schemaVersion",
    "viewRef",
    "querySpecificationRef",
    "queryPlanRef",
    "queryOutputSourceRef",
}


def sha256_bytes(value: bytes) -> str:
    if type(value) is not bytes:
        raise TypeError("sha256 input must be bytes")
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeBundleError(f"JSON contains duplicate key {key!r}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise RuntimeBundleError(f"JSON contains non-finite number {value}")


def _parse_canonical_int(token: str) -> int:
    """Accept integers within one process-independent decimal digit bound."""
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > _MAX_CANONICAL_INTEGER_DIGITS:
        raise RuntimeBundleError(_CANONICAL_INTEGER_LIMIT_ERROR)
    try:
        return int(token)
    except ValueError as exc:
        raise RuntimeBundleError(
            "JSON integer is outside the canonical numeric profile"
        ) from exc


def _canonical_json_snapshot(value: Any) -> Any:
    """Capture one built-in JSON view while enforcing the numeric profile."""
    memo: dict[int, tuple[Any, Any]] = {}
    active_containers: set[int] = set()

    def cached_container(item: Any) -> Any | None:
        cached = memo.get(id(item))
        if cached is None:
            return None
        original, normalized = cached
        if original is not item:
            raise RuntimeBundleError(_CANONICAL_CONTAINER_IDENTITY_ERROR)
        return normalized

    def normalize(item: Any) -> Any:
        if item is None or type(item) is bool:
            return item
        if isinstance(item, str):
            return str.__str__(item)
        if isinstance(item, int):
            normalized = int.__int__(item)
            if int.__abs__(normalized) >= _MAX_CANONICAL_INTEGER_MAGNITUDE:
                raise RuntimeBundleError(_CANONICAL_INTEGER_LIMIT_ERROR)
            return normalized
        if isinstance(item, float):
            return float.__float__(item)

        if isinstance(item, dict):
            container_id = id(item)
            if container_id in active_containers:
                raise RuntimeBundleError(_CANONICAL_CYCLE_ERROR)
            cached = cached_container(item)
            if cached is not None:
                return cached

            normalized_object: dict[str, Any] = {}
            memo[container_id] = (item, normalized_object)
            active_containers.add(container_id)
            try:
                for key, child in item.items():
                    if not isinstance(key, str):
                        raise RuntimeBundleError(_CANONICAL_OBJECT_KEY_ERROR)
                    normalized_key = str.__str__(key)
                    if normalized_key in normalized_object:
                        raise RuntimeBundleError(
                            f"JSON contains duplicate key {normalized_key!r}"
                        )
                    normalized_object[normalized_key] = normalize(child)
            finally:
                active_containers.remove(container_id)
            return normalized_object

        if isinstance(item, (list, tuple)):
            container_id = id(item)
            if container_id in active_containers:
                raise RuntimeBundleError(_CANONICAL_CYCLE_ERROR)
            cached = cached_container(item)
            if cached is not None:
                return cached

            normalized_array: list[Any] = []
            memo[container_id] = (item, normalized_array)
            active_containers.add(container_id)
            try:
                normalized_array.extend(normalize(child) for child in item)
            finally:
                active_containers.remove(container_id)
            return normalized_array

        raise RuntimeBundleError("document is outside canonical JSON")

    try:
        return normalize(value)
    except RuntimeBundleError:
        raise
    except MemoryError:
        raise
    except Exception as exc:
        raise RuntimeBundleError("document is outside canonical JSON") from exc


def _parse_canonical_float(token: str) -> float:
    """Accept finite binary64 values only when canonical encoding preserves value."""
    value = float(token)
    try:
        canonical_token = json.dumps(value, allow_nan=False)
    except (OverflowError, ValueError) as exc:
        raise RuntimeBundleError(
            f"JSON number {token} is outside the canonical numeric profile"
        ) from exc
    try:
        source_decimal = Decimal(token)
        canonical_decimal = Decimal(canonical_token)
    except DecimalException as exc:
        raise RuntimeBundleError(
            f"JSON number {token} is outside the canonical numeric profile"
        ) from exc
    if source_decimal != canonical_decimal:
        raise RuntimeBundleError(
            f"JSON number {token} is not preserved by the canonical numeric profile"
        )
    return value


def strict_json_document(raw: bytes, label: str) -> tuple[dict[str, Any], bytes]:
    """Decode one JSON object and return its deterministic canonical bytes."""
    if type(raw) is not bytes:
        raise RuntimeBundleError(f"{label} must be bytes")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise RuntimeBundleError(f"{label} must not contain a UTF-8 BOM")
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_int=_parse_canonical_int,
            parse_float=_parse_canonical_float,
            parse_constant=_reject_nonfinite,
        )
    except RuntimeBundleError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeBundleError(f"{label} is not strict UTF-8 JSON: {exc}") from exc
    if type(value) is not dict:
        raise RuntimeBundleError(f"{label} must be a JSON object")
    try:
        canonical = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (UnicodeEncodeError, ValueError) as exc:
        raise RuntimeBundleError(
            f"{label} contains a value outside canonical JSON"
        ) from exc
    return value, canonical


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    """Encode a trusted in-memory document using the bundle JSON profile."""
    if type(value) is not dict:
        raise RuntimeBundleError("canonical JSON value must be an object")
    snapshot = _canonical_json_snapshot(value)
    try:
        return json.dumps(
            snapshot,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (UnicodeEncodeError, ValueError) as exc:
        raise RuntimeBundleError("document is outside canonical JSON") from exc


def _require_digest(value: str, label: str) -> None:
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise RuntimeBundleError(f"{label} must be a full lowercase SHA-256")


def _require_logical_ref(value: str, label: str) -> None:
    if type(value) is not str or not _LOGICAL_REF_RE.fullmatch(value):
        raise RuntimeBundleError(f"{label} is not a bounded runtime logical ref")


def require_tenant_ref(value: object, label: str = "tenant ref") -> str:
    """Return one closed, bounded tenant reference or refuse it."""
    if type(value) is not str or _TENANT_REF_RE.fullmatch(value) is None:
        raise RuntimeBundleError(
            f"{label} must be tenant: followed by 1 to 248 ref characters"
        )
    return value


def _require_relative_path(value: str, label: str) -> None:
    if type(value) is not str or not value or "\\" in value:
        raise RuntimeBundleError(f"{label} must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if (path.is_absolute() or str(path) != value
            or any(part in {"", ".", ".."} for part in path.parts)):
        raise RuntimeBundleError(f"{label} must be a normalized relative path")


def _contract_schema_version_forms(
    document: dict[str, Any],
) -> tuple[bool, bool]:
    properties = document.get("properties")
    return (
        type(properties) is dict and "schemaVersion" in properties,
        "const" in document,
    )


def _contract_schema_version(document: dict[str, Any], label: str) -> str:
    property_form_present, whole_document_form_present = (
        _contract_schema_version_forms(document)
    )
    if property_form_present and whole_document_form_present:
        raise RuntimeBundleError(
            f"{label} declares schemaVersion const more than once"
        )
    if not property_form_present and not whole_document_form_present:
        raise RuntimeBundleError(f"{label} has no schemaVersion const")

    if property_form_present:
        schema_property = document["properties"]["schemaVersion"]
        if type(schema_property) is not dict or "const" not in schema_property:
            raise RuntimeBundleError(
                f"{label} has malformed properties.schemaVersion.const"
            )
        schema_version = schema_property["const"]
        location = "properties.schemaVersion.const"
    else:
        whole_document = document["const"]
        if type(whole_document) is not dict or "schemaVersion" not in whole_document:
            raise RuntimeBundleError(
                f"{label} has malformed const.schemaVersion"
            )
        schema_version = whole_document["schemaVersion"]
        location = "const.schemaVersion"

    if type(schema_version) is not str or not schema_version:
        raise RuntimeBundleError(f"{label} has malformed {location}")
    return schema_version


def _temporal_governance_rule(
    logical_ref: str,
) -> _TemporalGovernanceArtifactRule | None:
    return next(
        (
            rule for rule in _TEMPORAL_GOVERNANCE_ARTIFACT_RULES
            if rule.logical_ref == logical_ref
        ),
        None,
    )


def _matches_temporal_governance_reservation(
    logical_ref: str,
    content_digest: str,
) -> bool:
    return any(
        rule.logical_ref == logical_ref or rule.content_digest == content_digest
        for rule in _TEMPORAL_GOVERNANCE_ARTIFACT_RULES
    )


def _validate_temporal_governance_component(
    *,
    logical_ref: str,
    canonicalization: Canonicalization,
    placement: ContentPlacement,
    canonical_bytes: bytes,
    content_digest: str,
    document: dict[str, Any] | None,
) -> None:
    if (
        canonicalization is not Canonicalization.CANONICAL_JSON
        or placement is not ContentPlacement.GLOBAL
        or document is None
    ):
        raise RuntimeBundleError(
            "TEMPORAL_GOVERNANCE_ARTIFACT must use canonical JSON "
            "and global placement"
        )
    rule = _temporal_governance_rule(logical_ref)
    if rule is None:
        raise RuntimeBundleError(
            f"temporal governance identity {logical_ref!r} is not admitted"
        )
    if document.get("schemaVersion") != rule.schema_version:
        raise RuntimeBundleError(
            f"temporal governance component {logical_ref!r} schemaVersion differs"
        )
    if document.get(rule.identity_field) != logical_ref:
        raise RuntimeBundleError(
            f"temporal governance component {logical_ref!r} "
            f"does not declare {rule.identity_field}"
        )
    if (
        len(canonical_bytes) != rule.canonical_byte_length
        or content_digest != rule.content_digest
    ):
        raise RuntimeBundleError(
            f"temporal governance component {logical_ref!r} bytes differ"
        )


def _validate_runtime_component_semantics(
    *,
    role: RuntimeComponentRole,
    logical_ref: str,
    canonicalization: Canonicalization,
    placement: ContentPlacement,
    canonical_bytes: bytes,
    document: dict[str, Any] | None,
) -> None:
    content_digest = sha256_bytes(canonical_bytes)
    if (
        role is not RuntimeComponentRole.TEMPORAL_GOVERNANCE_ARTIFACT
        and _matches_temporal_governance_reservation(
            logical_ref, content_digest
        )
    ):
        raise RuntimeBundleError(
            "reserved temporal governance identity or digest requires "
            "TEMPORAL_GOVERNANCE_ARTIFACT"
        )
    if role is RuntimeComponentRole.TEMPORAL_GOVERNANCE_ARTIFACT:
        _validate_temporal_governance_component(
            logical_ref=logical_ref,
            canonicalization=canonicalization,
            placement=placement,
            canonical_bytes=canonical_bytes,
            content_digest=content_digest,
            document=document,
        )
        return

    if role in _EXACT_GLOBAL_COMPONENT_ROLES:
        if (
            canonicalization is not Canonicalization.EXACT_BYTES
            or placement is not ContentPlacement.GLOBAL
        ):
            raise RuntimeBundleError(
                f"{role.value} must use exact bytes and global placement"
            )
        return

    if role in _CONTRACT_SCHEMA_ROLES:
        if (
            canonicalization is not Canonicalization.EXACT_BYTES
            or placement is not ContentPlacement.GLOBAL
        ):
            raise RuntimeBundleError(
                f"{role.value} must use exact bytes and global placement"
            )
        document, _canonical = strict_json_document(
            canonical_bytes, f"contract component {logical_ref!r}"
        )
        schema_version = _contract_schema_version(
            document, f"contract component {logical_ref!r}"
        )
        if logical_ref != f"contract:{schema_version}":
            raise RuntimeBundleError(
                f"contract component {logical_ref!r} does not declare its logical ref"
            )
        return

    if (
        role not in _JSON_COMPONENT_RULES
        and role is not RuntimeComponentRole.PROFILE_INSTANCE
    ):
        raise RuntimeBundleError(f"{role.value} has no runtime component semantics")
    if canonicalization is not Canonicalization.CANONICAL_JSON:
        raise RuntimeBundleError(f"{role.value} must use canonical JSON")
    if document is None:
        raise RuntimeBundleError(f"{role.value} must contain a JSON object")

    if role is RuntimeComponentRole.PROFILE_INSTANCE:
        schema_version = document.get("schemaVersion")
        rule = _PROFILE_INSTANCE_RULES.get(schema_version)
        if rule is None:
            raise RuntimeBundleError(
                f"selected profile instance {logical_ref!r} has an "
                f"unsupported schemaVersion {schema_version!r}"
            )
        identity_field, required_placement = rule
    else:
        version_field, version, identity_field, required_placement = (
            _JSON_COMPONENT_RULES[role]
        )
        if version_field is not None and document.get(version_field) != version:
            raise RuntimeBundleError(
                f"selected {role.value} has an unsupported {version_field}"
            )
        if (
            role is RuntimeComponentRole.VIEW_BINDING
            and set(document) != _VIEW_BINDING_FIELDS
        ):
            raise RuntimeBundleError(
                f"selected view binding {logical_ref!r} has an invalid shape"
            )
    if placement is not required_placement:
        raise RuntimeBundleError(
            f"selected {role.value} has invalid content placement"
        )
    if document.get(identity_field) != logical_ref:
        raise RuntimeBundleError(
            f"selected component {logical_ref!r} does not declare "
            f"{identity_field}={logical_ref!r}"
        )


@dataclass(frozen=True, slots=True)
class RuntimeComponent:
    role: RuntimeComponentRole
    logical_ref: str
    canonicalization: Canonicalization
    placement: ContentPlacement
    canonical_bytes: bytes
    content_digest: str

    def __post_init__(self) -> None:
        if type(self.role) is not RuntimeComponentRole:
            raise RuntimeBundleError("runtime component role is outside the closed vocabulary")
        if type(self.canonicalization) is not Canonicalization:
            raise RuntimeBundleError("runtime component canonicalization is invalid")
        if type(self.placement) is not ContentPlacement:
            raise RuntimeBundleError("runtime component placement is invalid")
        _require_logical_ref(self.logical_ref, "runtime component logical ref")
        if type(self.canonical_bytes) is not bytes:
            raise RuntimeBundleError("runtime component canonical bytes must be bytes")
        _require_digest(self.content_digest, "runtime component digest")
        if sha256_bytes(self.canonical_bytes) != self.content_digest:
            raise RuntimeBundleError(
                f"runtime component {self.logical_ref!r} digest does not match its bytes"
            )
        document = None
        if self.canonicalization is Canonicalization.CANONICAL_JSON:
            document, canonical = strict_json_document(
                self.canonical_bytes, f"component {self.logical_ref!r}"
            )
            if canonical != self.canonical_bytes:
                raise RuntimeBundleError(
                    f"component {self.logical_ref!r} bytes are not canonical JSON"
                )
        _validate_runtime_component_semantics(
            role=self.role,
            logical_ref=self.logical_ref,
            canonicalization=self.canonicalization,
            placement=self.placement,
            canonical_bytes=self.canonical_bytes,
            document=document,
        )

    @classmethod
    def from_selected_bytes(
        cls,
        *,
        role: RuntimeComponentRole,
        logical_ref: str,
        canonicalization: Canonicalization,
        placement: ContentPlacement,
        selected_bytes: bytes,
    ) -> "RuntimeComponent":
        if canonicalization is Canonicalization.CANONICAL_JSON:
            _document, canonical = strict_json_document(
                selected_bytes, f"selected component {logical_ref!r}"
            )
        elif canonicalization is Canonicalization.EXACT_BYTES:
            if type(selected_bytes) is not bytes:
                raise RuntimeBundleError(
                    f"selected component {logical_ref!r} must be bytes"
                )
            canonical = selected_bytes
        else:
            raise RuntimeBundleError("unknown component canonicalization")
        return cls(
            role=role,
            logical_ref=logical_ref,
            canonicalization=canonicalization,
            placement=placement,
            canonical_bytes=canonical,
            content_digest=sha256_bytes(canonical),
        )

    @property
    def byte_length(self) -> int:
        return len(self.canonical_bytes)

    def identity_document(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "logicalRef": self.logical_ref,
            "canonicalization": self.canonicalization.value,
            "placement": self.placement.value,
            "contentDigest": self.content_digest,
            "byteLength": self.byte_length,
        }


@dataclass(frozen=True, slots=True)
class RuntimeComponentSpec:
    role: RuntimeComponentRole
    logical_ref: str
    relative_path: str
    canonicalization: Canonicalization
    placement: ContentPlacement

    def __post_init__(self) -> None:
        if type(self.role) is not RuntimeComponentRole:
            raise RuntimeBundleError("component spec role is invalid")
        if type(self.canonicalization) is not Canonicalization:
            raise RuntimeBundleError("component spec canonicalization is invalid")
        if type(self.placement) is not ContentPlacement:
            raise RuntimeBundleError("component spec placement is invalid")
        _require_logical_ref(self.logical_ref, "component spec logical ref")
        _require_relative_path(self.relative_path, "component spec path")

    @classmethod
    def from_document(cls, value: Any, index: int) -> "RuntimeComponentSpec":
        if type(value) is not dict:
            raise RuntimeBundleError(f"component catalog entry {index} must be an object")
        required = {"role", "logicalRef", "path", "canonicalization", "placement"}
        if set(value) != required:
            raise RuntimeBundleError(
                f"component catalog entry {index} has unknown or missing fields"
            )
        try:
            return cls(
                role=RuntimeComponentRole(value["role"]),
                logical_ref=value["logicalRef"],
                relative_path=value["path"],
                canonicalization=Canonicalization(value["canonicalization"]),
                placement=ContentPlacement(value["placement"]),
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeBundleError(
                f"component catalog entry {index} uses an unknown vocabulary value"
            ) from exc


def _canonical_component_documents(
    components: tuple[RuntimeComponent, ...],
) -> dict[tuple[RuntimeComponentRole, str], dict[str, Any]]:
    documents = {}
    for component in components:
        if component.canonicalization is Canonicalization.CANONICAL_JSON:
            document, _canonical = strict_json_document(
                component.canonical_bytes, component.logical_ref
            )
            documents[(component.role, component.logical_ref)] = document
    return documents


def _validate_temporal_governance_components(
    components: tuple[RuntimeComponent, ...],
) -> None:
    temporal_components = tuple(
        component for component in components
        if component.role is RuntimeComponentRole.TEMPORAL_GOVERNANCE_ARTIFACT
    )
    if not temporal_components:
        return
    contract_components = {
        component.logical_ref: component for component in components
        if component.role is RuntimeComponentRole.CONTRACT_SCHEMA
    }
    for component in temporal_components:
        rule = _temporal_governance_rule(component.logical_ref)
        if rule is None:  # pragma: no cover - component validation owns this state
            raise RuntimeBundleError(
                f"temporal governance identity {component.logical_ref!r} is not admitted"
            )
        schema_component = contract_components.get(rule.schema_logical_ref)
        if schema_component is None:
            raise RuntimeBundleError(
                f"temporal governance component {component.logical_ref!r} "
                f"requires {rule.schema_logical_ref!r} in CONTRACT_SCHEMA"
            )
        if (
            schema_component.byte_length != rule.schema_byte_length
            or schema_component.content_digest != rule.schema_content_digest
        ):
            raise RuntimeBundleError(
                f"temporal governance schema {rule.schema_logical_ref!r} bytes differ"
            )
        schema, _canonical = strict_json_document(
            schema_component.canonical_bytes,
            f"temporal governance schema {rule.schema_logical_ref!r}",
        )
        if _contract_schema_version(
            schema, f"temporal governance schema {rule.schema_logical_ref!r}"
        ) != rule.schema_version:
            raise RuntimeBundleError(
                f"temporal governance schema {rule.schema_logical_ref!r} "
                "version differs"
            )
        instance, _canonical = strict_json_document(
            component.canonical_bytes,
            f"temporal governance component {component.logical_ref!r}",
        )
        try:
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.Draft202012Validator(
                schema,
                format_checker=jsonschema.FormatChecker(),
            ).validate(instance)
        except jsonschema.exceptions.SchemaError as exc:
            raise RuntimeBundleError(
                f"temporal governance schema {rule.schema_logical_ref!r} is invalid"
            ) from exc
        except jsonschema.exceptions.ValidationError as exc:
            raise RuntimeBundleError(
                f"temporal governance component {component.logical_ref!r} "
                "fails its retained schema"
            ) from exc


def _validate_runtime_bundle_semantics(
    components: tuple[RuntimeComponent, ...],
) -> str | None:
    contract_refs = [
        component.logical_ref for component in components
        if component.role in _CONTRACT_SCHEMA_ROLES
    ]
    if len(contract_refs) != len(set(contract_refs)):
        raise RuntimeBundleError(
            "contract schemaVersion is selected more than once across lanes"
        )
    _validate_temporal_governance_components(components)
    descriptor_components = tuple(
        component for component in components
        if component.role is RuntimeComponentRole.PROFILE_DESCRIPTOR
    )
    if not descriptor_components:
        active_roles = {
            RuntimeComponentRole.ACTIVE_MANIFEST,
            RuntimeComponentRole.PROFILE_INSTANCE,
            RuntimeComponentRole.QUERY_SPECIFICATION,
            RuntimeComponentRole.QUERY_PLAN,
            RuntimeComponentRole.VIEW_BINDING,
            RuntimeComponentRole.REFERENCE_SNAPSHOT,
        }
        if any(component.role in active_roles for component in components):
            raise RuntimeBundleError(
                "active profile components require one profile descriptor"
            )
        return None
    if len(descriptor_components) != 1:
        raise RuntimeBundleError("RuntimeBundle selects multiple profile descriptors")

    documents = _canonical_component_documents(components)
    descriptor_component = descriptor_components[0]
    descriptor = documents[(
        RuntimeComponentRole.PROFILE_DESCRIPTOR,
        descriptor_component.logical_ref,
    )]
    profile_documents = [
        document for (role, _ref), document in documents.items()
        if role in {
            RuntimeComponentRole.PROFILE_INSTANCE,
            RuntimeComponentRole.REFERENCE_SNAPSHOT,
        }
    ]
    from .profile_runtime import (
        ProfileRuntimeError,
        validate_profile_runtime_selection_documents,
    )
    try:
        validate_profile_runtime_selection_documents(
            descriptor, profile_documents
        )
    except ProfileRuntimeError as exc:
        raise RuntimeBundleError(
            f"selected profile runtime is inconsistent: {exc}"
        ) from exc

    policy_refs = [
        component.logical_ref for component in components
        if component.role is RuntimeComponentRole.PROFILE_POLICY
    ]
    if policy_refs != [descriptor["evidencePolicyRef"]]:
        raise RuntimeBundleError(
            "active profile descriptor requires its exact profile policy component"
        )
    return _validate_active_selection(components, documents, descriptor)


def _validate_active_selection(
    components: tuple[RuntimeComponent, ...],
    documents: dict[tuple[RuntimeComponentRole, str], dict[str, Any]],
    descriptor: dict[str, Any],
) -> str:
    profile_ref = descriptor["profileRef"]
    pack_ref = descriptor["packRef"]
    pack_activation_ref = descriptor["packActivationSetRef"]
    active_artifact_ref = descriptor["activeArtifactSetRef"]
    code_binding_ref = descriptor["codeBindingProfileRef"]
    evidence_policy_ref = descriptor["evidencePolicyRef"]

    active_set = documents.get((
        RuntimeComponentRole.PROFILE_INSTANCE,
        active_artifact_ref,
    ))
    if active_set is None:
        raise RuntimeBundleError("descriptor-selected ActiveArtifactSet is not retained")
    active_refs = active_set.get("activeArtifactRefs")
    if type(active_refs) is not list or any(
        type(ref) is not str for ref in active_refs
    ):
        raise RuntimeBundleError("ActiveArtifactSet activeArtifactRefs are malformed")
    if len(active_refs) != len(set(active_refs)):
        raise RuntimeBundleError("ActiveArtifactSet activeArtifactRefs are malformed")

    selected = {(component.role, component.logical_ref) for component in components}
    for ref in active_refs:
        prefix = ref.split(":", 1)[0]
        if prefix == "contract":
            retained = (RuntimeComponentRole.CONTRACT_SCHEMA, ref) in selected
        else:
            expected_role = _ACTIVE_REF_ROLES.get(prefix)
            retained = expected_role is not None and (expected_role, ref) in selected
        if not retained:
            raise RuntimeBundleError(
                f"active artifact ref {ref!r} has no retained component "
                "eligible for activation"
            )

    required_active_refs = {
        component.logical_ref
        for component in components
        if component.role in {
            RuntimeComponentRole.ACTIVE_MANIFEST,
            RuntimeComponentRole.PROFILE_POLICY,
            RuntimeComponentRole.QUERY_SPECIFICATION,
            RuntimeComponentRole.QUERY_PLAN,
            RuntimeComponentRole.VIEW_BINDING,
            RuntimeComponentRole.REFERENCE_SNAPSHOT,
        }
    }
    required_active_refs.add(code_binding_ref)
    if not required_active_refs.issubset(active_refs):
        raise RuntimeBundleError(
            "component catalog and ActiveArtifactSet selection are not exact"
        )

    artifact_source_refs: set[str] = set()
    reference_documents: list[tuple[str, dict[str, Any]]] = []
    for (role, logical_ref), document in documents.items():
        if role is RuntimeComponentRole.REFERENCE_SNAPSHOT:
            source_refs = document.get("sourceArtifactRefs", [])
            if type(source_refs) is not list or any(
                type(ref) is not str for ref in source_refs
            ):
                raise RuntimeBundleError("ReferenceSnapshot source refs are malformed")
            reference_documents.append((logical_ref, document))
            artifact_source_refs.update(
                ref for ref in source_refs if ref.startswith("artifact:")
            )
    selected_artifact_sources = {
        component.logical_ref: component for component in components
        if component.role is RuntimeComponentRole.REFERENCE_SOURCE
        and component.logical_ref.startswith("artifact:")
    }
    if set(selected_artifact_sources) != artifact_source_refs:
        raise RuntimeBundleError(
            "artifact source refs do not exactly match retained reference sources"
        )
    for logical_ref, document in reference_documents:
        source_refs = document["sourceArtifactRefs"]
        selected_artifacts = {
            ref for ref in source_refs if ref.startswith("artifact:")
        }
        expected_digests = {
            f"digest:{selected_artifact_sources[ref].content_digest}"
            for ref in selected_artifacts
        }
        observed_digests = {
            ref for ref in source_refs if ref.startswith("digest:")
        }
        if observed_digests != expected_digests:
            raise RuntimeBundleError(
                f"ReferenceSnapshot {logical_ref!r} does not exactly bind "
                "its retained source bytes"
            )

    required_source_roles = {
        RuntimeComponentRole.VALIDATOR_SOURCE,
        RuntimeComponentRole.ADAPTER_SOURCE,
        RuntimeComponentRole.QUERY_OUTPUT_SOURCE,
    }
    selected_source_roles = {component.role for component in components}
    if not required_source_roles.issubset(selected_source_roles):
        raise RuntimeBundleError(
            "decision-bearing runtime source selection is incomplete"
        )

    pack_activation_set = documents.get((
        RuntimeComponentRole.PROFILE_INSTANCE,
        pack_activation_ref,
    ))
    if pack_activation_set is None:
        raise RuntimeBundleError(
            "descriptor-selected PackActivationSet is not retained"
        )
    manifests = [
        document for (role, _ref), document in documents.items()
        if role is RuntimeComponentRole.ACTIVE_MANIFEST
    ]
    if len(manifests) != 1:
        raise RuntimeBundleError("active selection requires one capability manifest")
    manifest = manifests[0]
    registry_relation = manifest.get("registryRelation")
    capability_sections = manifest.get("capabilitySections")
    pack_support = (
        capability_sections.get("packSupport")
        if type(capability_sections) is dict else None
    )
    artifact_support = (
        capability_sections.get("artifactSupport")
        if type(capability_sections) is dict else None
    )
    supported_artifact_types = (
        artifact_support.get("supportedArtifactTypes")
        if type(artifact_support) is dict else None
    )
    if (
        type(supported_artifact_types) is not list
        or not supported_artifact_types
        or any(type(kind) is not str for kind in supported_artifact_types)
        or len(supported_artifact_types) != len(set(supported_artifact_types))
    ):
        raise RuntimeBundleError(
            "capability manifest supported artifact types are malformed"
        )
    retained_contract_refs = {
        component.logical_ref for component in components
        if component.role is RuntimeComponentRole.CONTRACT_SCHEMA
    }
    if not {
        f"contract:{kind}" for kind in supported_artifact_types
    }.issubset(retained_contract_refs):
        raise RuntimeBundleError(
            "capability manifest supported artifact type is not retained "
            "as a canonical contract"
        )
    if (
        type(registry_relation) is not dict
        or registry_relation.get("activeArtifactSetRef") != active_artifact_ref
        or registry_relation.get("artifactRegistryRef")
        != active_set.get("artifactRegistryRef")
        or type(pack_support) is not dict
        or pack_support.get("activePackRefs") != [pack_ref]
        or pack_support.get("activeProfileRefs") != [profile_ref]
    ):
        raise RuntimeBundleError(
            "capability manifest does not match selected deployment identity"
        )

    selected_tenant_refs: list[str] = []
    for document, field in (
        (pack_activation_set, "targetScope"),
        (active_set, "deploymentScope"),
        (manifest, "deploymentScope"),
    ):
        scope = document.get(field)
        if type(scope) is not dict or scope.get("scopeType") != "TENANT":
            raise RuntimeBundleError(f"selected {field} is not a tenant scope")
        selected_tenant_refs.append(require_tenant_ref(
            scope.get("scopeRef"), f"selected {field} tenant scope"
        ))

    query_refs = {
        ref for role, ref in documents
        if role is RuntimeComponentRole.QUERY_SPECIFICATION
    }
    context_documents = {
        ref: document for (role, ref), document in documents.items()
        if (
            role is RuntimeComponentRole.PROFILE_INSTANCE
            and document.get("schemaVersion") == "ofarm.contextsnapshot.v0.1"
        )
    }
    selected_profile_instances = {
        ref for role, ref in documents
        if role is RuntimeComponentRole.PROFILE_INSTANCE
    }
    expected_profile_instances = {
        pack_activation_ref,
        active_artifact_ref,
        code_binding_ref,
        *context_documents,
    }
    if selected_profile_instances != expected_profile_instances:
        raise RuntimeBundleError("selected profile instance closure is not exact")
    snapshot_refs = {
        ref for role, ref in documents
        if role is RuntimeComponentRole.REFERENCE_SNAPSHOT
    }
    view_bindings = {
        ref: document for (role, ref), document in documents.items()
        if role is RuntimeComponentRole.VIEW_BINDING
    }
    selected_query_plans = {
        ref for role, ref in documents
        if role is RuntimeComponentRole.QUERY_PLAN
    }
    selected_output_sources = {
        component.logical_ref for component in components
        if component.role is RuntimeComponentRole.QUERY_OUTPUT_SOURCE
    }
    mapped_query_specs: set[str] = set()
    mapped_query_plans: set[str] = set()
    mapped_output_sources: set[str] = set()
    for view_ref, binding in view_bindings.items():
        query_spec_ref = binding.get("querySpecificationRef")
        query_plan_ref = binding.get("queryPlanRef")
        output_source_ref = binding.get("queryOutputSourceRef")
        for value, label in (
            (query_spec_ref, "querySpecificationRef"),
            (query_plan_ref, "queryPlanRef"),
            (output_source_ref, "queryOutputSourceRef"),
        ):
            _require_logical_ref(value, f"view binding {view_ref!r} {label}")
        plan = documents.get((RuntimeComponentRole.QUERY_PLAN, query_plan_ref))
        if (
            query_spec_ref not in query_refs
            or output_source_ref not in selected_output_sources
            or plan is None
            or plan.get("sourceQuerySpecificationId") != query_spec_ref
        ):
            raise RuntimeBundleError(
                f"view binding {view_ref!r} does not exactly retain its "
                "query specification, plan, and output source"
            )
        mapped_query_specs.add(query_spec_ref)
        mapped_query_plans.add(query_plan_ref)
        mapped_output_sources.add(output_source_ref)
    if (
        mapped_query_specs != query_refs
        or mapped_query_plans != selected_query_plans
        or mapped_output_sources != selected_output_sources
    ):
        raise RuntimeBundleError(
            "view bindings do not exactly cover selected query artifacts"
        )

    for document in context_documents.values():
        expected_lists = {
            "sourcePackActivationSetRefs": [pack_activation_ref],
            "activePackRefs": [pack_ref],
            "activeProfileRefs": [profile_ref],
            "evidencePolicyRefs": [evidence_policy_ref],
        }
        context_snapshot_refs = document.get("referenceSnapshotRefs")
        if (
            document.get("activeArtifactSetRef") != active_artifact_ref
            or any(
                document.get(field) != value
                for field, value in expected_lists.items()
            )
            or type(context_snapshot_refs) is not list
            or any(type(ref) is not str for ref in context_snapshot_refs)
            or set(context_snapshot_refs) != snapshot_refs
        ):
            raise RuntimeBundleError(
                "ContextSnapshot basis does not match retained active selection"
            )
        anchor_scopes = document.get("anchorScopes")
        if (
            type(anchor_scopes) is not list
            or not anchor_scopes
            or any(
                type(scope) is not dict
                or set(scope) != {"scopeType", "scopeRef"}
                or type(scope.get("scopeType")) is not str
                or scope.get("scopeType") not in _CONTEXT_SCOPE_TYPES
                or type(scope.get("scopeRef")) is not str
                or _CONTEXT_SCOPE_REF_RE.fullmatch(scope["scopeRef"]) is None
                for scope in anchor_scopes
            )
        ):
            raise RuntimeBundleError(
                "ContextSnapshot anchorScopes are malformed"
            )
        tenant_refs = [
            scope["scopeRef"] for scope in anchor_scopes
            if scope["scopeType"] == "TENANT"
        ]
        if len(tenant_refs) != 1:
            raise RuntimeBundleError(
                "ContextSnapshot must declare exactly one tenant anchor"
            )
        selected_tenant_refs.append(require_tenant_ref(
            tenant_refs[0], "ContextSnapshot tenant anchor"
        ))
    if len(set(selected_tenant_refs)) != 1:
        raise RuntimeBundleError(
            "selected tenant scopes do not identify one tenant"
        )

    for (role, ref), document in documents.items():
        if role is RuntimeComponentRole.QUERY_PLAN:
            target = document.get("normalizedTarget")
            context_ref = (
                target.get("contextSnapshotRef")
                if type(target) is dict else None
            )
            if (
                document.get("sourceQuerySpecificationId") not in query_refs
                or context_ref not in context_documents
            ):
                raise RuntimeBundleError(
                    f"query plan {ref!r} has an unretained selection input"
                )
    return selected_tenant_refs[0]


@dataclass(frozen=True, slots=True)
class RuntimeBundle:
    """Stable selected content; process-local activation observations live elsewhere."""

    components: tuple[RuntimeComponent, ...]
    canonical_document_bytes: bytes
    digest: str
    selected_tenant_ref: str | None = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if type(self.components) is not tuple or not self.components:
            raise RuntimeBundleError("RuntimeBundle requires an immutable component tuple")
        if any(type(component) is not RuntimeComponent for component in self.components):
            raise RuntimeBundleError("RuntimeBundle contains a non-component value")
        ordered = tuple(sorted(
            self.components, key=lambda item: (item.role.value, item.logical_ref)
        ))
        if self.components != ordered:
            raise RuntimeBundleError("RuntimeBundle components are not canonically ordered")
        keys = [(item.role.value, item.logical_ref) for item in self.components]
        if len(keys) != len(set(keys)):
            raise RuntimeBundleError("RuntimeBundle contains duplicate component identities")
        if type(self.canonical_document_bytes) is not bytes:
            raise RuntimeBundleError("RuntimeBundle canonical document must be bytes")
        _require_digest(self.digest, "RuntimeBundle digest")
        if sha256_bytes(self.canonical_document_bytes) != self.digest:
            raise RuntimeBundleError("RuntimeBundle digest does not match its document")
        expected = canonical_json_bytes(self.identity_document())
        if self.canonical_document_bytes != expected:
            raise RuntimeBundleError(
                "RuntimeBundle document is not the exact canonical component identity"
            )
        object.__setattr__(
            self,
            "selected_tenant_ref",
            _validate_runtime_bundle_semantics(self.components),
        )

    @classmethod
    def create(
        cls,
        components: Iterable[RuntimeComponent],
    ) -> "RuntimeBundle":
        try:
            selected = tuple(components)
        except TypeError as exc:
            raise RuntimeBundleError(
                "RuntimeBundle components must be an iterable of RuntimeComponents"
            ) from exc
        if any(type(component) is not RuntimeComponent for component in selected):
            raise RuntimeBundleError("RuntimeBundle contains a non-component value")
        ordered = tuple(sorted(
            selected, key=lambda item: (item.role.value, item.logical_ref)
        ))
        document = {
            "schemaVersion": BUNDLE_SCHEMA_VERSION,
            "canonicalization": Canonicalization.CANONICAL_JSON.value,
            "components": [item.identity_document() for item in ordered],
        }
        canonical = canonical_json_bytes(document)
        return cls(
            components=ordered,
            canonical_document_bytes=canonical,
            digest=sha256_bytes(canonical),
        )

    @property
    def bundle_ref(self) -> str:
        return f"runtimebundle:{self.digest}"

    def identity_document(self) -> dict[str, Any]:
        return {
            "schemaVersion": BUNDLE_SCHEMA_VERSION,
            "canonicalization": Canonicalization.CANONICAL_JSON.value,
            "components": [item.identity_document() for item in self.components],
        }

    def component(
        self, role: RuntimeComponentRole, logical_ref: str
    ) -> RuntimeComponent:
        matches = [
            item for item in self.components
            if item.role is role and item.logical_ref == logical_ref
        ]
        if len(matches) != 1:
            raise RuntimeBundleError(
                f"bundle expected one {role.value} component {logical_ref!r}; "
                f"found {len(matches)}"
            )
        return matches[0]


class RuntimeBundleBuilder:
    """Build one bundle from an explicit, reviewed component catalog."""

    def __init__(
        self,
        package_root: Path,
        component_specs: Iterable[RuntimeComponentSpec],
        contract_schema_paths: Iterable[str] = (),
        *,
        require_profile_descriptor: bool = False,
    ) -> None:
        root = Path(package_root)
        try:
            self.package_root = root.resolve(strict=True)
        except OSError as exc:
            raise RuntimeBundleError(f"package root is unavailable: {root}") from exc
        if not self.package_root.is_dir():
            raise RuntimeBundleError("package root must be a directory")
        self.component_specs = tuple(component_specs)
        self.contract_schema_paths = tuple(contract_schema_paths)
        self.require_profile_descriptor = require_profile_descriptor
        if not self.component_specs and not self.contract_schema_paths:
            raise RuntimeBundleError("RuntimeBundleBuilder has no selected components")
        for index, path in enumerate(self.contract_schema_paths):
            _require_relative_path(path, f"contract schema path {index}")

    @classmethod
    def from_manifest(
        cls,
        package_root: Path,
        manifest_path: str = "kernel/runtime_bundle_components.json",
    ) -> "RuntimeBundleBuilder":
        _require_relative_path(manifest_path, "component catalog path")
        unresolved_root = Path(package_root)
        try:
            root = unresolved_root.resolve(strict=True)
        except OSError as exc:
            raise RuntimeBundleError(
                f"package root is unavailable: {unresolved_root}"
            ) from exc
        raw = cls._read_path(root, manifest_path, "component catalog")
        document, _canonical = strict_json_document(raw, "component catalog")
        if set(document) != {"manifestVersion", "components", "contractSchemas"}:
            raise RuntimeBundleError("component catalog has unknown or missing fields")
        if document["manifestVersion"] != COMPONENT_CATALOG_VERSION:
            raise RuntimeBundleError("component catalog version is unsupported")
        if type(document["components"]) is not list:
            raise RuntimeBundleError("component catalog components must be a list")
        if type(document["contractSchemas"]) is not list or any(
            type(path) is not str for path in document["contractSchemas"]
        ):
            raise RuntimeBundleError("component catalog contractSchemas must be strings")
        component_specs = [
            RuntimeComponentSpec.from_document(value, index)
            for index, value in enumerate(document["components"])
        ]
        if any(
            spec.role is RuntimeComponentRole.TEMPORAL_GOVERNANCE_ARTIFACT
            for spec in component_specs
        ):
            raise RuntimeBundleError(
                "component catalog cannot select temporal governance artifacts"
            )
        return cls(
            root,
            component_specs,
            document["contractSchemas"],
            require_profile_descriptor=True,
        )

    def build(self) -> RuntimeBundle:
        self._validate_contract_registry_closure()
        components = [self._component_from_spec(spec) for spec in self.component_specs]
        components.extend(
            self._contract_schema_component(path)
            for path in self.contract_schema_paths
        )
        bundle = RuntimeBundle.create(components)
        self._validate_profile_descriptor_paths()
        return bundle

    def _component_from_spec(self, spec: RuntimeComponentSpec) -> RuntimeComponent:
        raw = self._read_path(
            self.package_root,
            spec.relative_path,
            f"{spec.role.value} component {spec.logical_ref!r}",
        )
        if (
            spec.role not in _EXACT_GLOBAL_COMPONENT_ROLES
            and spec.role not in _JSON_COMPONENT_RULES
            and spec.role is not RuntimeComponentRole.PROFILE_INSTANCE
            and spec.role is not RuntimeComponentRole.TEMPORAL_GOVERNANCE_ARTIFACT
        ):
            raise RuntimeBundleError(
                f"{spec.role.value} is not valid in explicit component entries"
            )
        return RuntimeComponent.from_selected_bytes(
            role=spec.role,
            logical_ref=spec.logical_ref,
            canonicalization=spec.canonicalization,
            placement=spec.placement,
            selected_bytes=raw,
        )

    def _validate_profile_descriptor_paths(self) -> None:
        descriptor_specs = tuple(
            spec for spec in self.component_specs
            if spec.role is RuntimeComponentRole.PROFILE_DESCRIPTOR
        )
        if not descriptor_specs:
            if self.require_profile_descriptor:
                raise RuntimeBundleError(
                    "production component catalog requires one profile descriptor")
            return
        descriptor_spec = descriptor_specs[0]
        descriptor_path = self.package_root.joinpath(
            *PurePosixPath(descriptor_spec.relative_path).parts
        )
        from .profile_runtime import (
            ProfileRuntimeError,
            load_profile_runtime_descriptor,
        )
        try:
            descriptor = load_profile_runtime_descriptor(
                descriptor_path.parent, descriptor_path=descriptor_path
            )
        except ProfileRuntimeError as exc:
            raise RuntimeBundleError(
                f"selected profile descriptor is inconsistent: {exc}"
            ) from exc

        declared_instance_paths = set(descriptor.profile_instance_paths)
        catalog_instance_paths = {
            self.package_root.joinpath(
                *PurePosixPath(spec.relative_path).parts
            ).resolve(strict=True)
            for spec in self.component_specs
            if spec.role in {
                RuntimeComponentRole.PROFILE_INSTANCE,
                RuntimeComponentRole.REFERENCE_SNAPSHOT,
            }
        }
        if catalog_instance_paths != declared_instance_paths:
            raise RuntimeBundleError(
                "component catalog does not exactly retain profileInstanceFiles")

        policy_spec = next(
            spec for spec in self.component_specs
            if spec.role is RuntimeComponentRole.PROFILE_POLICY
        )
        policy_path = self.package_root.joinpath(
            *PurePosixPath(policy_spec.relative_path).parts
        ).resolve(strict=True)
        if policy_path != descriptor.evidence_policy_path:
            raise RuntimeBundleError(
                "component catalog does not retain the "
                "descriptor-selected policy path"
            )

        examples_root = (descriptor.profile_root / "examples").resolve(strict=True)
        for spec in self.component_specs:
            if (
                spec.role is RuntimeComponentRole.REFERENCE_SOURCE
                and spec.logical_ref.startswith("artifact:")
            ):
                artifact_name = spec.logical_ref.split(":", 1)[1]
                _require_relative_path(
                    artifact_name, "reference source artifact name"
                )
                expected_path = (examples_root / artifact_name).resolve(strict=True)
                try:
                    expected_path.relative_to(examples_root)
                except ValueError as exc:
                    raise RuntimeBundleError(
                        "reference source artifact escapes profile examples"
                    ) from exc
                selected_path = (
                    self.package_root / spec.relative_path
                ).resolve(strict=True)
                if selected_path != expected_path:
                    raise RuntimeBundleError(
                        "reference source path does not match its artifact ref"
                    )

    def _validate_contract_registry_closure(self) -> None:
        if not (self.package_root / "contracts").is_dir():
            return
        loaded_paths: set[str] = set()
        for relative_directory in _CONTRACT_REGISTRY_DIRECTORIES:
            directory = self.package_root / relative_directory
            if not directory.is_dir():
                raise RuntimeBundleError(
                    f"contract registry directory is unavailable: {relative_directory}")
            for path in directory.glob("*.json"):
                relative_path = path.relative_to(self.package_root).as_posix()
                raw = self._read_path(
                    self.package_root, relative_path, "contract registry schema")
                document, _canonical = strict_json_document(
                    raw, f"contract registry schema {relative_path!r}")
                # Registry directories also contain non-schema metadata JSON.
                if not any(_contract_schema_version_forms(document)):
                    continue
                _contract_schema_version(
                    document, f"contract registry schema {relative_path!r}"
                )
                loaded_paths.add(relative_path)
        selected_paths = set(self.contract_schema_paths)
        if (
            len(selected_paths) != len(self.contract_schema_paths)
            or selected_paths != loaded_paths
        ):
            raise RuntimeBundleError(
                "component catalog does not exactly retain ContractRegistry schemas")

    def _contract_schema_component(self, relative_path: str) -> RuntimeComponent:
        raw = self._read_path(
            self.package_root, relative_path, f"contract schema {relative_path!r}"
        )
        document, _canonical = strict_json_document(
            raw, f"contract schema {relative_path!r}"
        )
        schema_version = _contract_schema_version(
            document, f"contract schema {relative_path!r}"
        )
        return RuntimeComponent.from_selected_bytes(
            role=(
                RuntimeComponentRole.DRAFT_CONTRACT_SCHEMA
                if relative_path.startswith(_DRAFT_CONTRACT_DIRECTORY + "/")
                else RuntimeComponentRole.CONTRACT_SCHEMA
            ),
            logical_ref=f"contract:{schema_version}",
            canonicalization=Canonicalization.EXACT_BYTES,
            placement=ContentPlacement.GLOBAL,
            selected_bytes=raw,
        )

    @staticmethod
    def _read_path(root: Path, relative_path: str, label: str) -> bytes:
        _require_relative_path(relative_path, f"{label} path")
        candidate = root.joinpath(*PurePosixPath(relative_path).parts)
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise RuntimeBundleError(
                f"{label} is missing or escapes the package root: {relative_path}"
            ) from exc
        if not resolved.is_file():
            raise RuntimeBundleError(f"{label} is not a regular file: {relative_path}")
        try:
            return resolved.read_bytes()
        except OSError as exc:
            raise RuntimeBundleError(
                f"{label} could not be read: {relative_path}"
            ) from exc
