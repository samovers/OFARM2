"""Active profile runtime selection and descriptor loading.

This is configuration resolution only. The descriptor is profile/package
content, not a canonical contract and not OFARM Core law. Tenant or demo binding
stays outside the required descriptor.
"""
from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DESCRIPTOR_FILENAME = "runtime_profile_descriptor.json"
DESCRIPTOR_VERSION = "ofarm.profile-runtime-descriptor.local.v0_1"

OMIT_FROM_CONTEXT = "OMIT_FROM_CONTEXT"
REFUSE_CONTEXT = "REFUSE_CONTEXT"
_MISSING_BEHAVIORS = {OMIT_FROM_CONTEXT, REFUSE_CONTEXT}

_REF_RE = re.compile(r"^[a-z][a-z0-9_-]*:[A-Za-z0-9._:-]+$")
_FAMILY_RE = re.compile(r"^[a-z][a-z0-9_.-]*$")

_DESCRIPTOR_KEYS = {
    "descriptorVersion",
    "profileRef",
    "packRef",
    "packActivationSetRef",
    "activeArtifactSetRef",
    "codeBindingProfileRef",
    "evidencePolicyRef",
    "evidencePolicyPath",
    "profileInstanceFiles",
    "referenceFamilies",
    "contextSnapshotIdPrefix",
}
_DESCRIPTOR_REQUIRED = _DESCRIPTOR_KEYS

_REFERENCE_FAMILY_KEYS = {
    "familyId",
    "snapshotPrefix",
    "dataFamily",
    "requiredForNowContext",
    "requiredForAsOfContext",
    "missingFamilyBehaviorNow",
    "missingFamilyBehaviorAsOf",
    "shippedSnapshotRef",
}
_REFERENCE_FAMILY_REQUIRED = {
    "familyId",
    "snapshotPrefix",
    "requiredForNowContext",
    "requiredForAsOfContext",
    "missingFamilyBehaviorNow",
    "missingFamilyBehaviorAsOf",
}


class ProfileRuntimeError(RuntimeError):
    """The active profile descriptor is missing, malformed, or incoherent."""


@dataclass(frozen=True)
class ReferenceFamily:
    family_id: str
    snapshot_prefix: str
    data_family: str | None
    required_for_now_context: bool
    required_for_as_of_context: bool
    missing_family_behavior_now: str
    missing_family_behavior_as_of: str
    shipped_snapshot_ref: str | None

    def missing_behavior(self, *, as_of: bool) -> str:
        return self.missing_family_behavior_as_of if as_of else self.missing_family_behavior_now


@dataclass(frozen=True)
class ProfileRuntimeDescriptor:
    profile_root: Path
    descriptor_path: Path
    descriptor_version: str
    profile_ref: str
    pack_ref: str
    pack_activation_set_ref: str
    active_artifact_set_ref: str
    code_binding_profile_ref: str
    evidence_policy_ref: str
    evidence_policy_path: Path
    profile_instance_files: tuple[str, ...]
    profile_instance_paths: tuple[Path, ...]
    reference_families: tuple[ReferenceFamily, ...]
    context_snapshot_id_prefix: str

    def reference_family(self, family_id: str) -> ReferenceFamily:
        for family in self.reference_families:
            if family.family_id == family_id:
                return family
        raise ProfileRuntimeError(f"active profile lacks reference family {family_id!r}")


@dataclass(frozen=True)
class ActiveProfileSelection:
    package_root: Path
    profile_package_names: tuple[str, ...]
    profile_roots: tuple[Path, ...]
    descriptors: tuple[ProfileRuntimeDescriptor, ...]

    @property
    def active_profile(self) -> ProfileRuntimeDescriptor:
        if len(self.descriptors) != 1:
            raise ProfileRuntimeError(
                "MP1 active profile selection supports exactly one active "
                f"profile package; got {len(self.descriptors)}")
        return self.descriptors[0]


def load_active_profile_selection(
    package_root: Path,
    profile_package_names: Sequence[str],
    *,
    allowed_profile_package_names: Sequence[str] | None = None,
) -> ActiveProfileSelection:
    """Resolve the configured active profile package selection, failing closed.

    MP1 makes active-profile selection explicit while preserving the current
    single-active-profile runtime. Multiple active profiles are a later loader,
    harness, evidence, and manifest problem, so this selector rejects them
    rather than pretending the rest of the runtime is multi-profile-ready.
    """
    root = package_root.resolve()
    if not root.is_dir():
        raise ProfileRuntimeError(f"package root is not a directory: {package_root}")
    names = _profile_package_names(profile_package_names)
    if allowed_profile_package_names is not None:
        allowed = set(_profile_package_names(allowed_profile_package_names))
        rejected = sorted(name for name in names if name not in allowed)
        if rejected:
            raise ProfileRuntimeError(
                "active profile package selection includes package(s) not "
                f"enabled for this runtime: {rejected}")
    if len(names) != 1:
        raise ProfileRuntimeError(
            "MP1 active profile selection supports exactly one active profile "
            f"package; got {list(names)!r}")

    profile_roots = tuple(_active_profile_root(root, name) for name in names)
    descriptors = tuple(load_profile_runtime_descriptor(profile_root)
                        for profile_root in profile_roots)
    return ActiveProfileSelection(
        package_root=root,
        profile_package_names=names,
        profile_roots=profile_roots,
        descriptors=descriptors,
    )


def load_profile_runtime_descriptor(
    profile_root: Path,
    descriptor_path: Path | None = None,
) -> ProfileRuntimeDescriptor:
    """Load and validate the active profile descriptor, failing closed."""
    root = profile_root.resolve()
    if not root.is_dir():
        raise ProfileRuntimeError(f"profile root is not a directory: {profile_root}")
    path = descriptor_path or (root / DESCRIPTOR_FILENAME)
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ProfileRuntimeError(f"profile runtime descriptor unreadable at {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ProfileRuntimeError("profile runtime descriptor must be a JSON object")

    _reject_unknown(doc, _DESCRIPTOR_KEYS, "descriptor")
    _require(doc, _DESCRIPTOR_REQUIRED, "descriptor")
    if doc["descriptorVersion"] != DESCRIPTOR_VERSION:
        raise ProfileRuntimeError(
            f"unsupported descriptorVersion {doc['descriptorVersion']!r}; "
            f"expected {DESCRIPTOR_VERSION!r}")

    for field in (
        "profileRef",
        "packRef",
        "packActivationSetRef",
        "activeArtifactSetRef",
        "codeBindingProfileRef",
        "evidencePolicyRef",
        "contextSnapshotIdPrefix",
    ):
        _validate_ref(doc[field], field)

    evidence_policy_path = _existing_profile_file(root, doc["evidencePolicyPath"], "evidencePolicyPath")
    profile_instance_files = _string_list(doc["profileInstanceFiles"], "profileInstanceFiles")
    if len(profile_instance_files) != len(set(profile_instance_files)):
        raise ProfileRuntimeError("profileInstanceFiles contains duplicate entries")
    profile_instance_paths = tuple(
        _existing_profile_file(root, rel, f"profileInstanceFiles[{i}]")
        for i, rel in enumerate(profile_instance_files)
    )

    families = _reference_families(doc["referenceFamilies"])
    _validate_policy_ref(evidence_policy_path, doc["evidencePolicyRef"])
    payloads = _load_profile_instance_payloads(
        profile_instance_files,
        profile_instance_paths,
    )
    _validate_active_spine(doc, payloads)
    _validate_shipped_reference_refs(families, payloads)

    return ProfileRuntimeDescriptor(
        profile_root=root,
        descriptor_path=path,
        descriptor_version=doc["descriptorVersion"],
        profile_ref=doc["profileRef"],
        pack_ref=doc["packRef"],
        pack_activation_set_ref=doc["packActivationSetRef"],
        active_artifact_set_ref=doc["activeArtifactSetRef"],
        code_binding_profile_ref=doc["codeBindingProfileRef"],
        evidence_policy_ref=doc["evidencePolicyRef"],
        evidence_policy_path=evidence_policy_path,
        profile_instance_files=tuple(profile_instance_files),
        profile_instance_paths=profile_instance_paths,
        reference_families=families,
        context_snapshot_id_prefix=doc["contextSnapshotIdPrefix"],
    )


def _profile_package_names(profile_package_names: Sequence[str]) -> tuple[str, ...]:
    if isinstance(profile_package_names, str):
        raise ProfileRuntimeError("active profile package selection must be a sequence")
    names = tuple(profile_package_names)
    if not names:
        raise ProfileRuntimeError("active profile package selection must not be empty")
    if not all(isinstance(name, str) for name in names):
        raise ProfileRuntimeError("active profile package names must be strings")
    if len(names) != len(set(names)):
        raise ProfileRuntimeError("active profile package selection contains duplicates")
    return names


def _active_profile_root(package_root: Path, package_name: str) -> Path:
    if not package_name:
        raise ProfileRuntimeError("active profile package name must not be empty")
    path = Path(package_name)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
        raise ProfileRuntimeError(
            "active profile package names must be simple repository-local "
            f"directory names: {package_name!r}")
    if not package_name.startswith("profile_"):
        raise ProfileRuntimeError(
            f"active profile package must be a profile_* directory: {package_name!r}")
    target = package_root / path
    try:
        resolved = target.resolve()
        resolved.relative_to(package_root)
    except (OSError, ValueError) as exc:
        raise ProfileRuntimeError(
            f"active profile package escapes the package root: {package_name!r}") from exc
    if not resolved.is_dir():
        raise ProfileRuntimeError(
            f"active profile package is not a directory: {package_name!r}")
    descriptor = resolved / DESCRIPTOR_FILENAME
    if not descriptor.is_file():
        raise ProfileRuntimeError(
            f"active profile package {package_name!r} has no "
            f"{DESCRIPTOR_FILENAME}; design-only profile slices are not active "
            "runtime profiles")
    return resolved


def _reject_unknown(doc: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(doc) - allowed)
    if unknown:
        raise ProfileRuntimeError(f"{label} contains unknown field(s): {unknown}")


def _require(doc: dict[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - set(doc))
    if missing:
        raise ProfileRuntimeError(f"{label} missing required field(s): {missing}")


def _validate_ref(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _REF_RE.fullmatch(value):
        raise ProfileRuntimeError(f"{field} is not a valid OFARM-style ref: {value!r}")
    return value


def _validate_family_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _FAMILY_RE.fullmatch(value):
        raise ProfileRuntimeError(f"{field} is not a valid reference family id: {value!r}")
    return value


def _existing_profile_file(root: Path, rel: Any, field: str) -> Path:
    if not isinstance(rel, str) or not rel:
        raise ProfileRuntimeError(f"{field} must be a non-empty relative path")
    path = Path(rel)
    if path.is_absolute():
        raise ProfileRuntimeError(f"{field} must not be an absolute path: {rel!r}")
    if ".." in path.parts:
        raise ProfileRuntimeError(f"{field} must not contain '..': {rel!r}")
    target = root / path
    try:
        resolved = target.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ProfileRuntimeError(f"{field} escapes the profile root: {rel!r}") from exc
    if not resolved.is_file():
        raise ProfileRuntimeError(f"{field} does not name an existing file: {rel!r}")
    return resolved


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(i, str) for i in value):
        raise ProfileRuntimeError(f"{field} must be a non-empty list of strings")
    return value


def _reference_families(value: Any) -> tuple[ReferenceFamily, ...]:
    if not isinstance(value, list) or not value:
        raise ProfileRuntimeError("referenceFamilies must be a non-empty list")
    families = []
    seen_ids: set[str] = set()
    seen_prefixes: set[str] = set()
    for i, item in enumerate(value):
        label = f"referenceFamilies[{i}]"
        if not isinstance(item, dict):
            raise ProfileRuntimeError(f"{label} must be an object")
        _reject_unknown(item, _REFERENCE_FAMILY_KEYS, label)
        _require(item, _REFERENCE_FAMILY_REQUIRED, label)
        family_id = _validate_family_id(item["familyId"], f"{label}.familyId")
        prefix = _validate_ref(item["snapshotPrefix"], f"{label}.snapshotPrefix")
        if family_id in seen_ids:
            raise ProfileRuntimeError(f"duplicate reference family id {family_id!r}")
        if prefix in seen_prefixes:
            raise ProfileRuntimeError(f"duplicate reference snapshot prefix {prefix!r}")
        seen_ids.add(family_id)
        seen_prefixes.add(prefix)
        data_family = item.get("dataFamily")
        if data_family is not None:
            _validate_family_id(data_family, f"{label}.dataFamily")
        required_now = _bool(item["requiredForNowContext"], f"{label}.requiredForNowContext")
        required_as_of = _bool(item["requiredForAsOfContext"], f"{label}.requiredForAsOfContext")
        behavior_now = _missing_behavior(item["missingFamilyBehaviorNow"],
                                         f"{label}.missingFamilyBehaviorNow")
        behavior_as_of = _missing_behavior(item["missingFamilyBehaviorAsOf"],
                                           f"{label}.missingFamilyBehaviorAsOf")
        _assert_required_behavior(required_now, behavior_now, f"{label}.NOW")
        _assert_required_behavior(required_as_of, behavior_as_of, f"{label}.AS_OF")
        shipped = item.get("shippedSnapshotRef")
        if shipped is not None:
            _validate_ref(shipped, f"{label}.shippedSnapshotRef")
            if not _matches_family(shipped, prefix):
                raise ProfileRuntimeError(
                    f"{label}.shippedSnapshotRef {shipped!r} does not match prefix {prefix!r}")
        families.append(ReferenceFamily(
            family_id=family_id,
            snapshot_prefix=prefix,
            data_family=data_family,
            required_for_now_context=required_now,
            required_for_as_of_context=required_as_of,
            missing_family_behavior_now=behavior_now,
            missing_family_behavior_as_of=behavior_as_of,
            shipped_snapshot_ref=shipped,
        ))
    return tuple(families)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ProfileRuntimeError(f"{field} must be a boolean")
    return value


def _missing_behavior(value: Any, field: str) -> str:
    if value not in _MISSING_BEHAVIORS:
        raise ProfileRuntimeError(f"{field} must be one of {sorted(_MISSING_BEHAVIORS)}")
    return value


def _assert_required_behavior(required: bool, behavior: str, field: str) -> None:
    expected = REFUSE_CONTEXT if required else OMIT_FROM_CONTEXT
    if behavior != expected:
        raise ProfileRuntimeError(
            f"{field} required flag and missing behavior disagree: "
            f"required={required!r}, behavior={behavior!r}, expected {expected!r}")


def _matches_family(snapshot_ref: str, prefix: str) -> bool:
    return snapshot_ref == prefix or snapshot_ref.startswith(prefix + ".")


def _validate_policy_ref(path: Path, expected_ref: str) -> None:
    try:
        policy = json.loads(path.read_text())
    except ValueError as exc:
        raise ProfileRuntimeError(f"evidence policy is not valid JSON: {path}") from exc
    if not isinstance(policy, dict) or policy.get("policyId") != expected_ref:
        raise ProfileRuntimeError(
            f"evidence policy {path} does not declare policyId {expected_ref!r}")


def _load_profile_instance_payloads(
    profile_instance_files: list[str],
    profile_instance_paths: tuple[Path, ...],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for rel, path in zip(profile_instance_files, profile_instance_paths):
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise ProfileRuntimeError(
                f"profile instance file {rel!r} unreadable or malformed: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise ProfileRuntimeError(
                f"profile instance file {rel!r} must be a JSON object")
        payloads.append(payload)
    return payloads


def _validate_active_spine(doc: dict[str, Any], payloads: list[dict[str, Any]]) -> None:
    activation = _payload_by_id(payloads, "packActivationSetId", doc["packActivationSetRef"])
    artifact = _payload_by_id(payloads, "activeArtifactSetId", doc["activeArtifactSetRef"])
    profile = _payload_by_id(payloads, "agronomicCodeBindingProfileId",
                             doc["codeBindingProfileRef"])

    if activation.get("activePackRefs") != [doc["packRef"]]:
        raise ProfileRuntimeError(
            "PackActivationSet must declare exactly one active pack matching packRef")
    if activation.get("activeProfileRefs") != [doc["profileRef"]]:
        raise ProfileRuntimeError(
            "PackActivationSet must declare exactly one active profile matching profileRef")
    if artifact.get("activePackRefs") != [doc["packRef"]]:
        raise ProfileRuntimeError(
            "ActiveArtifactSet must declare exactly one active pack matching packRef")
    if artifact.get("activeProfileRefs") != [doc["profileRef"]]:
        raise ProfileRuntimeError(
            "ActiveArtifactSet must declare exactly one active profile matching profileRef")
    if doc["packRef"] not in activation.get("activePackRefs", []):
        raise ProfileRuntimeError("packRef is not active in the PackActivationSet")
    if doc["profileRef"] not in activation.get("activeProfileRefs", []):
        raise ProfileRuntimeError("profileRef is not active in the PackActivationSet")
    if doc["packActivationSetRef"] not in artifact.get("sourcePackActivationSetRefs", []):
        raise ProfileRuntimeError("ActiveArtifactSet does not source the PackActivationSet")
    if set(artifact.get("activePackRefs", [])) != set(activation.get("activePackRefs", [])):
        raise ProfileRuntimeError("ActiveArtifactSet activePackRefs do not match PackActivationSet")
    if set(artifact.get("activeProfileRefs", [])) != set(activation.get("activeProfileRefs", [])):
        raise ProfileRuntimeError(
            "ActiveArtifactSet activeProfileRefs do not match PackActivationSet")
    if doc["codeBindingProfileRef"] not in artifact.get("activeArtifactRefs", []):
        raise ProfileRuntimeError("ActiveArtifactSet does not deploy the code-binding profile")
    if doc["evidencePolicyRef"] not in artifact.get("activeArtifactRefs", []):
        raise ProfileRuntimeError("ActiveArtifactSet does not deploy the evidence policy")
    if profile.get("profileState") != "ACTIVE":
        raise ProfileRuntimeError("code-binding profile is not ACTIVE")
    if (profile.get("profileScope") or {}).get("packRefs") != [doc["packRef"]]:
        raise ProfileRuntimeError(
            "code-binding profile profileScope.packRefs must match descriptor packRef")


def _payload_by_id(payloads: list[dict[str, Any]], id_field: str, expected: str) -> dict[str, Any]:
    matches = [p for p in payloads if p.get(id_field) == expected]
    if len(matches) != 1:
        raise ProfileRuntimeError(
            f"expected exactly one profile instance with {id_field}={expected!r}, "
            f"found {len(matches)}")
    return matches[0]


def _validate_shipped_reference_refs(
    families: tuple[ReferenceFamily, ...],
    payloads: list[dict[str, Any]],
) -> None:
    snapshots = {p.get("referenceSnapshotId") for p in payloads if p.get("referenceSnapshotId")}
    for family in families:
        if family.shipped_snapshot_ref and family.shipped_snapshot_ref not in snapshots:
            raise ProfileRuntimeError(
                f"shipped snapshot {family.shipped_snapshot_ref!r} for family "
                f"{family.family_id!r} is not in profileInstanceFiles")
