"""Stable, content-addressed runtime selection for issue #171.
Bundles contain explicit selected content: canonical JSON or exact raw bytes.
Absolute paths and process observations never enter stable identity.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


BUNDLE_SCHEMA_VERSION = "ofarm.runtime-bundle.local.v1"
COMPONENT_CATALOG_VERSION = "ofarm.runtime-component-catalog.local.v1"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_LOGICAL_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,1023}$")
_TENANT_REF_RE = re.compile(r"^[A-Za-z0-9._:-]{1,255}$")


class RuntimeBundleError(RuntimeError):
    """Selected runtime content is missing, malformed, or inconsistent."""


class RuntimeComponentRole(str, Enum):
    PROFILE_DESCRIPTOR = "PROFILE_DESCRIPTOR"
    ACTIVE_MANIFEST = "ACTIVE_MANIFEST"
    PROFILE_INSTANCE = "PROFILE_INSTANCE"
    PROFILE_POLICY = "PROFILE_POLICY"
    QUERY_SPECIFICATION = "QUERY_SPECIFICATION"
    QUERY_PLAN = "QUERY_PLAN"
    CONTRACT_SCHEMA = "CONTRACT_SCHEMA"
    VALIDATOR_SOURCE = "VALIDATOR_SOURCE"
    ADAPTER_SOURCE = "ADAPTER_SOURCE"
    QUERY_OUTPUT_SOURCE = "QUERY_OUTPUT_SOURCE"
    REFERENCE_SNAPSHOT = "REFERENCE_SNAPSHOT"
    REFERENCE_SOURCE = "REFERENCE_SOURCE"
    RUNTIME_SCHEMA = "RUNTIME_SCHEMA"
    RELEASE_MANIFEST = "RELEASE_MANIFEST"


class Canonicalization(str, Enum):
    CANONICAL_JSON = "OFARM_CANONICAL_JSON_V1"
    EXACT_BYTES = "EXACT_BYTES_V1"


class ContentPlacement(str, Enum):
    GLOBAL = "GLOBAL_IMMUTABLE_CONTENT"
    TENANT = "TENANT_RUNTIME_SELECTION"


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
    RuntimeComponentRole.RUNTIME_SCHEMA,
})
_ACTIVE_REF_ROLES = {
    "contract": RuntimeComponentRole.CONTRACT_SCHEMA,
    "queryspec": RuntimeComponentRole.QUERY_SPECIFICATION,
    "queryplan": RuntimeComponentRole.QUERY_PLAN,
    "policy": RuntimeComponentRole.PROFILE_POLICY,
    "codebindingprofile": RuntimeComponentRole.PROFILE_INSTANCE,
    "referencesnapshot": RuntimeComponentRole.REFERENCE_SNAPSHOT,
    "manifest": RuntimeComponentRole.ACTIVE_MANIFEST,
}
_CONTRACT_REGISTRY_DIRECTORIES = (
    "contracts/kernel",
    "contracts/core",
    "contracts/platform",
    "contracts/drafts_reference/explainable_current_state_evidence",
)


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
    try:
        return json.dumps(
            value,
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


def _require_relative_path(value: str, label: str) -> None:
    if type(value) is not str or not value or "\\" in value:
        raise RuntimeBundleError(f"{label} must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if (path.is_absolute() or str(path) != value
            or any(part in {"", ".", ".."} for part in path.parts)):
        raise RuntimeBundleError(f"{label} must be a normalized relative path")


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
        if self.canonicalization is Canonicalization.CANONICAL_JSON:
            _document, canonical = strict_json_document(
                self.canonical_bytes, f"component {self.logical_ref!r}"
            )
            if canonical != self.canonical_bytes:
                raise RuntimeBundleError(
                    f"component {self.logical_ref!r} bytes are not canonical JSON"
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
    expected_content_digest: str | None = None

    def __post_init__(self) -> None:
        if type(self.role) is not RuntimeComponentRole:
            raise RuntimeBundleError("component spec role is invalid")
        if type(self.canonicalization) is not Canonicalization:
            raise RuntimeBundleError("component spec canonicalization is invalid")
        if type(self.placement) is not ContentPlacement:
            raise RuntimeBundleError("component spec placement is invalid")
        _require_logical_ref(self.logical_ref, "component spec logical ref")
        _require_relative_path(self.relative_path, "component spec path")
        if self.expected_content_digest is not None:
            _require_digest(self.expected_content_digest, "expected component digest")

    @classmethod
    def from_document(cls, value: Any, index: int) -> "RuntimeComponentSpec":
        if type(value) is not dict:
            raise RuntimeBundleError(f"component catalog entry {index} must be an object")
        required = {"role", "logicalRef", "path", "canonicalization", "placement"}
        allowed = required | {"expectedContentDigest"}
        if set(value) - allowed or not required.issubset(value):
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
                expected_content_digest=value.get("expectedContentDigest"),
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeBundleError(
                f"component catalog entry {index} uses an unknown vocabulary value"
            ) from exc


@dataclass(frozen=True, slots=True)
class RuntimeBundle:
    tenant_ref: str
    components: tuple[RuntimeComponent, ...]
    canonical_document_bytes: bytes
    digest: str

    def __post_init__(self) -> None:
        if type(self.tenant_ref) is not str or not _TENANT_REF_RE.fullmatch(self.tenant_ref):
            raise RuntimeBundleError("RuntimeBundle tenant ref is malformed")
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
        _document, canonical = strict_json_document(
            self.canonical_document_bytes, "RuntimeBundle document"
        )
        expected = canonical_json_bytes(self.identity_document())
        if (
            canonical != self.canonical_document_bytes
            or self.canonical_document_bytes != expected
        ):
            raise RuntimeBundleError(
                "RuntimeBundle document is not the exact canonical component identity"
            )

    @classmethod
    def create(
        cls,
        tenant_ref: str,
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
            tenant_ref=tenant_ref,
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
        return cls(
            root,
            [
                RuntimeComponentSpec.from_document(value, index)
                for index, value in enumerate(document["components"])
            ],
            document["contractSchemas"],
            require_profile_descriptor=True,
        )

    def build(self, tenant_ref: str) -> RuntimeBundle:
        self._validate_contract_registry_closure()
        components = [self._component_from_spec(spec) for spec in self.component_specs]
        components.extend(
            self._contract_schema_component(path)
            for path in self.contract_schema_paths
        )
        self._validate_profile_descriptor_closure(tenant_ref, components)
        return RuntimeBundle.create(tenant_ref, components)

    def _component_from_spec(self, spec: RuntimeComponentSpec) -> RuntimeComponent:
        raw = self._read_path(
            self.package_root,
            spec.relative_path,
            f"{spec.role.value} component {spec.logical_ref!r}",
        )
        document = None
        if spec.role in _EXACT_GLOBAL_COMPONENT_ROLES:
            if (
                spec.canonicalization is not Canonicalization.EXACT_BYTES
                or spec.placement is not ContentPlacement.GLOBAL
            ):
                raise RuntimeBundleError(
                    f"{spec.role.value} must use exact bytes and global placement")
        else:
            if (
                spec.role not in _JSON_COMPONENT_RULES
                and spec.role is not RuntimeComponentRole.PROFILE_INSTANCE
            ):
                raise RuntimeBundleError(
                    f"{spec.role.value} is not valid in explicit component entries")
            if spec.canonicalization is not Canonicalization.CANONICAL_JSON:
                raise RuntimeBundleError(
                    f"{spec.role.value} must use canonical JSON")
            document, _canonical = strict_json_document(
                raw, f"selected component {spec.logical_ref!r}")
            self._validate_intrinsic_identity(spec, document)
        component = RuntimeComponent.from_selected_bytes(
            role=spec.role,
            logical_ref=spec.logical_ref,
            canonicalization=spec.canonicalization,
            placement=spec.placement,
            selected_bytes=raw,
        )
        if (spec.expected_content_digest is not None
                and component.content_digest != spec.expected_content_digest):
            raise RuntimeBundleError(
                f"selected component {spec.logical_ref!r} digest is "
                f"{component.content_digest}, expected {spec.expected_content_digest}"
            )
        return component

    @staticmethod
    def _validate_intrinsic_identity(
        spec: RuntimeComponentSpec,
        document: dict[str, Any],
    ) -> None:
        if spec.role is RuntimeComponentRole.PROFILE_INSTANCE:
            schema_version = document.get("schemaVersion")
            rule = _PROFILE_INSTANCE_RULES.get(schema_version)
            if rule is None:
                raise RuntimeBundleError(
                    f"selected profile instance {spec.logical_ref!r} has an "
                    f"unsupported schemaVersion {schema_version!r}"
                )
            identity_field, placement = rule
        else:
            version_field, version, identity_field, placement = (
                _JSON_COMPONENT_RULES[spec.role]
            )
            if version_field is not None and document.get(version_field) != version:
                raise RuntimeBundleError(
                    f"selected {spec.role.value} has an unsupported {version_field}"
                )
        if spec.placement is not placement:
            raise RuntimeBundleError(
                f"selected {spec.role.value} has invalid content placement"
            )
        if document.get(identity_field) != spec.logical_ref:
            raise RuntimeBundleError(
                f"selected component {spec.logical_ref!r} does not declare "
                f"{identity_field}={spec.logical_ref!r}"
            )

    def _validate_profile_descriptor_closure(
        self,
        tenant_ref: str,
        components: list[RuntimeComponent],
    ) -> None:
        descriptor_specs = tuple(
            spec for spec in self.component_specs
            if spec.role is RuntimeComponentRole.PROFILE_DESCRIPTOR
        )
        if not descriptor_specs:
            if self.require_profile_descriptor:
                raise RuntimeBundleError(
                    "production component catalog requires one profile descriptor")
            active_roles = {
                RuntimeComponentRole.ACTIVE_MANIFEST,
                RuntimeComponentRole.PROFILE_INSTANCE,
                RuntimeComponentRole.QUERY_SPECIFICATION,
                RuntimeComponentRole.QUERY_PLAN,
                RuntimeComponentRole.REFERENCE_SNAPSHOT,
            }
            if any(spec.role in active_roles for spec in self.component_specs):
                raise RuntimeBundleError(
                    "active profile components require one profile descriptor")
            return
        if len(descriptor_specs) != 1:
            raise RuntimeBundleError("RuntimeBundle selects multiple profile descriptors")
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

        policy_specs = tuple(
            spec for spec in self.component_specs
            if spec.role is RuntimeComponentRole.PROFILE_POLICY
        )
        if len(policy_specs) != 1:
            raise RuntimeBundleError(
                "active profile descriptor requires exactly one profile policy component")
        policy_spec = policy_specs[0]
        policy_path = self.package_root.joinpath(
            *PurePosixPath(policy_spec.relative_path).parts
        ).resolve(strict=True)
        if (
            policy_path != descriptor.evidence_policy_path
            or policy_spec.logical_ref != descriptor.evidence_policy_ref
            or descriptor_spec.logical_ref != descriptor.profile_ref
        ):
            raise RuntimeBundleError(
                "component catalog does not retain the descriptor-selected policy/profile")
        self._validate_active_selection(tenant_ref, components, descriptor)

    def _validate_active_selection(
        self,
        tenant_ref: str,
        components: list[RuntimeComponent],
        descriptor: Any,
    ) -> None:
        documents = {}
        for component in components:
            if component.canonicalization is Canonicalization.CANONICAL_JSON:
                document, _canonical = strict_json_document(
                    component.canonical_bytes, component.logical_ref)
                documents[(component.role, component.logical_ref)] = document

        active_set = documents.get((
            RuntimeComponentRole.PROFILE_INSTANCE,
            descriptor.active_artifact_set_ref,
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
        output_sources = sum(
            component.role is RuntimeComponentRole.QUERY_OUTPUT_SOURCE
            for component in components
        )
        for ref in active_refs:
            prefix = ref.split(":", 1)[0]
            if prefix == "view":
                if output_sources != 1:
                    raise RuntimeBundleError(
                        "active view refs require one query-output source component")
                continue
            expected_role = _ACTIVE_REF_ROLES.get(prefix)
            if expected_role is None or (expected_role, ref) not in selected:
                raise RuntimeBundleError(
                    f"active artifact ref {ref!r} has no retained component")

        required_active_refs = {
            component.logical_ref
            for component in components
            if component.role in {
                RuntimeComponentRole.ACTIVE_MANIFEST,
                RuntimeComponentRole.PROFILE_POLICY,
                RuntimeComponentRole.QUERY_SPECIFICATION,
                RuntimeComponentRole.QUERY_PLAN,
                RuntimeComponentRole.REFERENCE_SNAPSHOT,
            }
        }
        required_active_refs.add(descriptor.code_binding_profile_ref)
        if not required_active_refs.issubset(active_refs):
            raise RuntimeBundleError(
                "component catalog and ActiveArtifactSet selection are not exact")

        artifact_source_refs = set()
        for (role, _ref), document in documents.items():
            if role is RuntimeComponentRole.REFERENCE_SNAPSHOT:
                source_refs = document.get("sourceArtifactRefs", [])
                if type(source_refs) is not list or any(
                    type(ref) is not str for ref in source_refs
                ):
                    raise RuntimeBundleError("ReferenceSnapshot source refs are malformed")
                artifact_source_refs.update(
                    ref for ref in source_refs
                    if ref.startswith("artifact:")
                )
        selected_artifact_sources = {
            component.logical_ref for component in components
            if component.role is RuntimeComponentRole.REFERENCE_SOURCE
            and component.logical_ref.startswith("artifact:")
        }
        if selected_artifact_sources != artifact_source_refs:
            raise RuntimeBundleError(
                "artifact source refs do not exactly match retained reference sources")
        examples_root = (descriptor.profile_root / "examples").resolve(strict=True)
        for spec in self.component_specs:
            if (
                spec.role is RuntimeComponentRole.REFERENCE_SOURCE
                and spec.logical_ref.startswith("artifact:")
            ):
                artifact_name = spec.logical_ref.split(":", 1)[1]
                _require_relative_path(artifact_name, "reference source artifact name")
                expected_path = (examples_root / artifact_name).resolve(strict=True)
                try:
                    expected_path.relative_to(examples_root)
                except ValueError as exc:
                    raise RuntimeBundleError(
                        "reference source artifact escapes profile examples") from exc
                selected_path = (self.package_root / spec.relative_path).resolve(strict=True)
                if selected_path != expected_path:
                    raise RuntimeBundleError(
                        "reference source path does not match its artifact ref")

        tenant_scoped = [
            (documents[(RuntimeComponentRole.PROFILE_INSTANCE,
                        descriptor.pack_activation_set_ref)], "targetScope"),
            (active_set, "deploymentScope"),
        ]
        manifests = [
            document for (role, _ref), document in documents.items()
            if role is RuntimeComponentRole.ACTIVE_MANIFEST
        ]
        if len(manifests) != 1:
            raise RuntimeBundleError("active selection requires one capability manifest")
        tenant_scoped.append((manifests[0], "deploymentScope"))
        for document, field in tenant_scoped:
            scope = document.get(field)
            if (
                type(scope) is not dict
                or scope.get("scopeType") != "TENANT"
                or scope.get("scopeRef") != tenant_ref
            ):
                raise RuntimeBundleError(
                    f"selected {field} does not match RuntimeBundle tenant_ref")

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
        snapshot_refs = {
            ref for role, ref in documents
            if role is RuntimeComponentRole.REFERENCE_SNAPSHOT
        }
        for document in context_documents.values():
            expected_lists = {
                "sourcePackActivationSetRefs": [descriptor.pack_activation_set_ref],
                "activePackRefs": [descriptor.pack_ref],
                "activeProfileRefs": [descriptor.profile_ref],
                "evidencePolicyRefs": [descriptor.evidence_policy_ref],
            }
            context_snapshot_refs = document.get("referenceSnapshotRefs")
            if (
                document.get("activeArtifactSetRef")
                != descriptor.active_artifact_set_ref
                or any(document.get(field) != value
                       for field, value in expected_lists.items())
                or type(context_snapshot_refs) is not list
                or any(type(ref) is not str for ref in context_snapshot_refs)
                or set(context_snapshot_refs) != snapshot_refs
            ):
                raise RuntimeBundleError(
                    "ContextSnapshot basis does not match retained active selection")
            tenant_refs = [
                scope.get("scopeRef") for scope in document.get("anchorScopes", [])
                if type(scope) is dict and scope.get("scopeType") == "TENANT"
            ]
            if tenant_refs != [tenant_ref]:
                raise RuntimeBundleError(
                    "ContextSnapshot tenant anchor does not match tenant_ref")
        for (role, ref), document in documents.items():
            if role is RuntimeComponentRole.QUERY_PLAN:
                target = document.get("normalizedTarget")
                if (
                    document.get("sourceQuerySpecificationId") not in query_refs
                    or type(target) is not dict
                    or target.get("contextSnapshotRef") not in context_documents
                ):
                    raise RuntimeBundleError(
                        f"query plan {ref!r} has an unretained selection input")

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
                schema_version = (
                    document.get("properties", {}).get("schemaVersion", {}).get("const")
                )
                if schema_version:
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
        document, _canonical = strict_json_document(raw, f"contract schema {relative_path!r}")
        schema_version = (
            document.get("properties", {}).get("schemaVersion", {}).get("const")
        )
        if type(schema_version) is not str or not schema_version:
            raise RuntimeBundleError(
                f"contract schema {relative_path!r} has no schemaVersion const"
            )
        return RuntimeComponent.from_selected_bytes(
            role=RuntimeComponentRole.CONTRACT_SCHEMA,
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
