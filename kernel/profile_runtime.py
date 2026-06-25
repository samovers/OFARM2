"""Active profile runtime selection and descriptor loading.

This is configuration resolution only. The descriptor is profile/package
content, not a canonical contract and not OFARM Core law. Tenant or demo binding
stays outside the required descriptor.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
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

ROUTE_STATUS_ACTIVE = "ACTIVE"
ROUTE_STATUS_DRAFT = "DRAFT"
ROUTE_STATUS_RETIRED = "RETIRED"
ROUTE_STATUS_REVOKED = "REVOKED"
_ROUTE_STATUSES = {
    ROUTE_STATUS_ACTIVE,
    ROUTE_STATUS_DRAFT,
    ROUTE_STATUS_RETIRED,
    ROUTE_STATUS_REVOKED,
}

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
class ProfileDescriptorCandidate:
    package_name: str
    profile_root: Path
    descriptor_path: Path
    descriptor: ProfileRuntimeDescriptor
    enabled: bool


@dataclass(frozen=True)
class ProfileDescriptorRegistry:
    package_root: Path
    discoverable_package_names: tuple[str, ...]
    descriptor_candidates: tuple[ProfileDescriptorCandidate, ...]
    enabled_package_names: tuple[str, ...]

    def candidate_for(self, package_name: str) -> ProfileDescriptorCandidate | None:
        for candidate in self.descriptor_candidates:
            if candidate.package_name == package_name:
                return candidate
        return None


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


@dataclass(frozen=True)
class ProfileRouteRecord:
    route_id: str
    tenant_ref: str
    farm_ref: str
    profile_package_name: str
    profile_ref: str
    pack_ref: str
    pack_activation_set_ref: str
    active_artifact_set_ref: str
    descriptor_identity: str | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    status: str = ROUTE_STATUS_ACTIVE


@dataclass(frozen=True)
class ProfileRouteResolution:
    route: ProfileRouteRecord
    candidate: ProfileDescriptorCandidate
    descriptor: ProfileRuntimeDescriptor
    effective_time: datetime | None


PRECONDITION_INVALID_PACKAGE_NAME = "INVALID_PACKAGE_NAME"
PRECONDITION_NO_DESCRIPTOR_CANDIDATE = "NO_DESCRIPTOR_CANDIDATE"
PRECONDITION_PACKAGE_NOT_ENABLED = "PACKAGE_NOT_ENABLED"
PRECONDITION_PACKAGE_NOT_SELECTED = "PACKAGE_NOT_SELECTED"
PRECONDITION_POLICY_NOT_LOADABLE = "POLICY_NOT_LOADABLE"
PRECONDITION_MISSING_RUNTIME_ADAPTER_SUPPORT = "MISSING_RUNTIME_ADAPTER_SUPPORT"
PRECONDITION_MISSING_PROFILE_HARNESS_COVERAGE = "MISSING_PROFILE_HARNESS_COVERAGE"
PRECONDITION_MISSING_PROFILE_EXECUTED_EVIDENCE_LANE = (
    "MISSING_PROFILE_EXECUTED_EVIDENCE_LANE"
)
PRECONDITION_MISSING_MANIFEST_GROUNDING = "MISSING_MANIFEST_GROUNDING"
_PRECONDITION_BLOCKER_ORDER = (
    PRECONDITION_INVALID_PACKAGE_NAME,
    PRECONDITION_NO_DESCRIPTOR_CANDIDATE,
    PRECONDITION_PACKAGE_NOT_ENABLED,
    PRECONDITION_PACKAGE_NOT_SELECTED,
    PRECONDITION_POLICY_NOT_LOADABLE,
    PRECONDITION_MISSING_RUNTIME_ADAPTER_SUPPORT,
    PRECONDITION_MISSING_PROFILE_HARNESS_COVERAGE,
    PRECONDITION_MISSING_PROFILE_EXECUTED_EVIDENCE_LANE,
    PRECONDITION_MISSING_MANIFEST_GROUNDING,
)


@dataclass(frozen=True)
class ProfileRuntimeSurfaceInventory:
    """Explicit, non-discovering surface facts for MP7.5 precondition checks.

    The sets are checker inputs only. They are not evidence, manifest grounding,
    or runtime discovery by themselves.
    """

    adapter_supported_package_names: frozenset[str] = frozenset()
    harness_covered_package_names: frozenset[str] = frozenset()
    profile_executed_evidence_lane_package_names: frozenset[str] = frozenset()
    generated_or_verified_manifest_grounding_package_names: frozenset[str] = (
        frozenset()
    )

    def __post_init__(self) -> None:
        for field_name in (
            "adapter_supported_package_names",
            "harness_covered_package_names",
            "profile_executed_evidence_lane_package_names",
            "generated_or_verified_manifest_grounding_package_names",
        ):
            object.__setattr__(
                self,
                field_name,
                _inventory_package_name_set(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True)
class ProfileRuntimePreconditionResult:
    package_name: str
    preconditions_satisfied: bool
    blocking_reason_codes: tuple[str, ...]


def resolve_active_descriptor(
    active_descriptor=None,
    *,
    allow_config_default: bool,
) -> ProfileRuntimeDescriptor:
    """Resolve an active runtime descriptor with an explicit config fallback.

    `profile_runtime` is imported by `kernel.config`, so config must be imported
    lazily only when the compatibility fallback is deliberately requested.
    """
    if active_descriptor is not None:
        return active_descriptor
    if not allow_config_default:
        raise ProfileRuntimeError("active runtime descriptor is required")
    from . import config
    return config.ACTIVE_PROFILE


def profile_runtime_descriptor_identity(
    descriptor: ProfileRuntimeDescriptor,
) -> str:
    """Deterministic identity for route-to-descriptor pinning.

    The identity intentionally combines the descriptor's profile-local path and
    its current bytes. Package names and refs remain necessary route fields, but
    the digest prevents a route from silently tracking changed descriptor
    content when the route chose to pin an identity.
    """
    try:
        profile_root = descriptor.profile_root.resolve()
        descriptor_path = descriptor.descriptor_path.resolve(strict=True)
        rel = descriptor_path.relative_to(profile_root)
        digest = hashlib.sha256(descriptor_path.read_bytes()).hexdigest()
    except (AttributeError, OSError, ValueError) as exc:
        raise ProfileRuntimeError("profile runtime descriptor identity is unavailable") from exc
    return f"{descriptor.profile_root.name}/{rel.as_posix()}#{digest}"


def evaluate_profile_runtime_preconditions(
    registry: ProfileDescriptorRegistry,
    package_name: str,
    selected_package_names: Sequence[str],
    surface_inventory: ProfileRuntimeSurfaceInventory,
    *,
    policy_supported_checks: Sequence[str] | None = None,
) -> ProfileRuntimePreconditionResult:
    """Evaluate explicit MP7.5 candidate-runtime preconditions.

    This is a passive checker over an already-loaded descriptor registry and
    caller-supplied surface inventory. A satisfied result is checker-relative
    only: it does not activate the package, write evidence, generate manifests,
    or create a capability claim.
    """
    if not isinstance(registry, ProfileDescriptorRegistry):
        raise ProfileRuntimeError(
            "profile runtime preconditions require a descriptor registry")
    if not isinstance(surface_inventory, ProfileRuntimeSurfaceInventory):
        raise ProfileRuntimeError(
            "surface_inventory must be a ProfileRuntimeSurfaceInventory")

    result_name = package_name if isinstance(package_name, str) else repr(package_name)
    try:
        _validate_profile_package_name(package_name)
    except ProfileRuntimeError:
        return _precondition_result(
            result_name,
            [PRECONDITION_INVALID_PACKAGE_NAME],
        )

    selected = _profile_package_names_allow_empty(selected_package_names)
    candidate = registry.candidate_for(package_name)
    if candidate is None:
        return _precondition_result(
            package_name,
            [PRECONDITION_NO_DESCRIPTOR_CANDIDATE],
        )

    blockers: list[str] = []
    if not candidate.enabled:
        blockers.append(PRECONDITION_PACKAGE_NOT_ENABLED)
    if package_name not in selected:
        blockers.append(PRECONDITION_PACKAGE_NOT_SELECTED)

    try:
        from . import profile_policy
        profile_policy.DescriptorPolicyProvider(
            candidate.descriptor,
        ).evidence_policy(supported_checks=policy_supported_checks)
    except profile_policy.ProfilePolicyError:
        blockers.append(PRECONDITION_POLICY_NOT_LOADABLE)

    if package_name not in surface_inventory.adapter_supported_package_names:
        blockers.append(PRECONDITION_MISSING_RUNTIME_ADAPTER_SUPPORT)
    if package_name not in surface_inventory.harness_covered_package_names:
        blockers.append(PRECONDITION_MISSING_PROFILE_HARNESS_COVERAGE)
    if package_name not in (
        surface_inventory.profile_executed_evidence_lane_package_names
    ):
        blockers.append(PRECONDITION_MISSING_PROFILE_EXECUTED_EVIDENCE_LANE)
    if package_name not in (
        surface_inventory.generated_or_verified_manifest_grounding_package_names
    ):
        blockers.append(PRECONDITION_MISSING_MANIFEST_GROUNDING)

    return _precondition_result(package_name, blockers)


def resolve_profile_route(
    registry: ProfileDescriptorRegistry,
    selected_profile_package_names: Sequence[str],
    route_records: Sequence[ProfileRouteRecord],
    *,
    tenant_ref: str,
    farm_ref: str,
    effective_time: datetime | None = None,
) -> ProfileRouteResolution:
    """Resolve one active route for a governed tenant/farm context.

    MP7.1 deliberately keeps all inputs explicit. This function does not read
    environment variables, `kernel.config`, or navigation/design artifacts.
    """
    if not isinstance(registry, ProfileDescriptorRegistry):
        raise ProfileRuntimeError("profile route resolution requires a descriptor registry")
    selected = set(_profile_package_names(selected_profile_package_names))
    routes = _profile_route_records(route_records)
    _validate_ref(tenant_ref, "tenant_ref")
    _validate_ref(farm_ref, "farm_ref")
    _validate_route_time(effective_time, "effective_time")

    matches = [
        route for route in routes
        if _route_matches_context(
            route,
            tenant_ref=tenant_ref,
            farm_ref=farm_ref,
            effective_time=effective_time,
        )
    ]
    if not matches:
        raise ProfileRuntimeError(
            "no active profile route for tenant/farm/effective-time context")
    if len(matches) != 1:
        raise ProfileRuntimeError(
            "multiple active overlapping profile routes for "
            "tenant/farm/effective-time context")

    route = matches[0]
    candidate = registry.candidate_for(route.profile_package_name)
    if candidate is None:
        raise ProfileRuntimeError(
            f"profile route {route.route_id!r} targets package "
            f"{route.profile_package_name!r} with no {DESCRIPTOR_FILENAME}; "
            "design-only profile slices are not active runtime profiles")
    if not candidate.enabled:
        raise ProfileRuntimeError(
            f"profile route {route.route_id!r} targets package "
            f"{route.profile_package_name!r} that is not enabled for this runtime")
    if route.profile_package_name not in selected:
        raise ProfileRuntimeError(
            f"profile route {route.route_id!r} targets package "
            f"{route.profile_package_name!r} that is not selected for this runtime")

    descriptor = candidate.descriptor
    _assert_route_matches_descriptor(route, descriptor)
    return ProfileRouteResolution(
        route=route,
        candidate=candidate,
        descriptor=descriptor,
        effective_time=effective_time,
    )


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
    if allowed_profile_package_names is None:
        raise ProfileRuntimeError(
            "active profile package selection requires an explicit enabled "
            "profile package allow-list")
    registry = load_profile_descriptor_registry(
        package_root,
        allowed_profile_package_names=allowed_profile_package_names,
    )
    names = _profile_package_names(profile_package_names)
    if registry.enabled_package_names:
        rejected = sorted(name for name in names if name not in registry.enabled_package_names)
        if rejected:
            raise ProfileRuntimeError(
                "active profile package selection includes package(s) not "
                f"enabled for this runtime: {rejected}")
    if len(names) != 1:
        raise ProfileRuntimeError(
            "MP1 active profile selection supports exactly one active profile "
            f"package; got {list(names)!r}")

    candidates = []
    for name in names:
        _validate_profile_package_name(name)
        candidate = registry.candidate_for(name)
        if candidate is None:
            raise ProfileRuntimeError(
                f"active profile package {name!r} has no {DESCRIPTOR_FILENAME}; "
                "design-only profile slices are not active runtime profiles")
        candidates.append(candidate)

    return ActiveProfileSelection(
        package_root=registry.package_root,
        profile_package_names=names,
        profile_roots=tuple(candidate.profile_root for candidate in candidates),
        descriptors=tuple(candidate.descriptor for candidate in candidates),
    )


def load_profile_descriptor_registry(
    package_root: Path,
    allowed_profile_package_names: Sequence[str] | None = None,
) -> ProfileDescriptorRegistry:
    """Discover descriptor-bearing profile packages without activating them."""
    root = package_root.resolve()
    if not root.is_dir():
        raise ProfileRuntimeError(f"package root is not a directory: {package_root}")

    allowed = (_profile_package_names(allowed_profile_package_names)
               if allowed_profile_package_names is not None else ())
    discoverable = _discoverable_profile_packages(root)
    candidates = []
    for package_name, profile_root in discoverable:
        descriptor_path = profile_root / DESCRIPTOR_FILENAME
        if not descriptor_path.exists() and not descriptor_path.is_symlink():
            continue
        try:
            resolved_descriptor_path = descriptor_path.resolve(strict=True)
            resolved_descriptor_path.relative_to(profile_root)
        except (OSError, ValueError) as exc:
            raise ProfileRuntimeError(
                f"profile runtime descriptor for {package_name!r} escapes "
                "the profile root") from exc
        if not resolved_descriptor_path.is_file():
            raise ProfileRuntimeError(
                f"profile runtime descriptor for {package_name!r} is not a file")
        descriptor = load_profile_runtime_descriptor(
            profile_root,
            descriptor_path=resolved_descriptor_path,
        )
        candidates.append(ProfileDescriptorCandidate(
            package_name=package_name,
            profile_root=profile_root,
            descriptor_path=resolved_descriptor_path,
            descriptor=descriptor,
            enabled=(package_name in allowed),
        ))
    _reject_duplicate_descriptor_refs(tuple(candidates))
    return ProfileDescriptorRegistry(
        package_root=root,
        discoverable_package_names=tuple(name for name, _ in discoverable),
        descriptor_candidates=tuple(candidates),
        enabled_package_names=allowed,
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


def _discoverable_profile_packages(package_root: Path) -> tuple[tuple[str, Path], ...]:
    packages = []
    seen_names: set[str] = set()
    seen_roots: set[Path] = set()
    for child in sorted(package_root.iterdir(), key=lambda path: path.name):
        if not child.is_dir():
            continue
        name = child.name
        if not name.startswith("profile_"):
            continue
        _validate_profile_package_name(name)
        try:
            resolved = child.resolve()
            resolved.relative_to(package_root)
        except (OSError, ValueError) as exc:
            raise ProfileRuntimeError(
                f"discoverable profile package escapes the package root: {name!r}") from exc
        if name in seen_names or resolved in seen_roots:
            raise ProfileRuntimeError(
                f"duplicate discoverable profile package after normalization: {name!r}")
        seen_names.add(name)
        seen_roots.add(resolved)
        packages.append((name, resolved))
    return tuple(packages)


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
    for name in names:
        _validate_profile_package_name(name)
    return names


def _profile_package_names_allow_empty(
    profile_package_names: Sequence[str],
) -> frozenset[str]:
    if profile_package_names is None or isinstance(profile_package_names, str):
        raise ProfileRuntimeError("profile package names must be a sequence")
    try:
        names = tuple(profile_package_names)
    except TypeError as exc:
        raise ProfileRuntimeError("profile package names must be a sequence") from exc
    if not all(isinstance(name, str) for name in names):
        raise ProfileRuntimeError("profile package names must be strings")
    if len(names) != len(set(names)):
        raise ProfileRuntimeError("profile package names contain duplicates")
    for name in names:
        _validate_profile_package_name(name)
    return frozenset(names)


def _inventory_package_name_set(value: Any, field: str) -> frozenset[str]:
    if isinstance(value, (str, bytes)) or not isinstance(
        value,
        (set, frozenset, tuple, list),
    ):
        raise ProfileRuntimeError(
            f"{field} must be a set, frozenset, tuple, or list of package names")
    names = tuple(value)
    if not all(isinstance(name, str) for name in names):
        raise ProfileRuntimeError(f"{field} must contain only strings")
    if len(names) != len(set(names)):
        raise ProfileRuntimeError(f"{field} contains duplicate package names")
    for name in names:
        _validate_profile_package_name(name)
    return frozenset(names)


def _precondition_result(
    package_name: str,
    blockers: Sequence[str],
) -> ProfileRuntimePreconditionResult:
    blocker_set = set(blockers)
    ordered = tuple(
        blocker for blocker in _PRECONDITION_BLOCKER_ORDER
        if blocker in blocker_set
    )
    return ProfileRuntimePreconditionResult(
        package_name=package_name,
        preconditions_satisfied=not ordered,
        blocking_reason_codes=ordered,
    )


def _profile_route_records(
    route_records: Sequence[ProfileRouteRecord],
) -> tuple[ProfileRouteRecord, ...]:
    if route_records is None or isinstance(route_records, (str, bytes)):
        raise ProfileRuntimeError("profile route records must be a sequence")
    try:
        routes = tuple(route_records)
    except TypeError as exc:
        raise ProfileRuntimeError("profile route records must be a sequence") from exc
    for route in routes:
        _validate_profile_route_record(route)
    return routes


def _validate_profile_route_record(route: ProfileRouteRecord) -> None:
    if not isinstance(route, ProfileRouteRecord):
        raise ProfileRuntimeError("profile route records must be ProfileRouteRecord values")
    _validate_ref(route.route_id, "route.route_id")
    _validate_ref(route.tenant_ref, "route.tenant_ref")
    _validate_ref(route.farm_ref, "route.farm_ref")
    _validate_profile_package_name(route.profile_package_name)
    _validate_ref(route.profile_ref, "route.profile_ref")
    _validate_ref(route.pack_ref, "route.pack_ref")
    _validate_ref(route.pack_activation_set_ref, "route.pack_activation_set_ref")
    _validate_ref(route.active_artifact_set_ref, "route.active_artifact_set_ref")
    if route.descriptor_identity is not None:
        if not isinstance(route.descriptor_identity, str) or not route.descriptor_identity:
            raise ProfileRuntimeError("route.descriptor_identity must be a non-empty string")
    if route.status not in _ROUTE_STATUSES:
        raise ProfileRuntimeError(
            f"profile route status must be one of {sorted(_ROUTE_STATUSES)}")
    _validate_route_time(route.effective_from, "route.effective_from")
    _validate_route_time(route.effective_until, "route.effective_until")
    if (route.effective_from is not None and route.effective_until is not None
            and route.effective_from >= route.effective_until):
        raise ProfileRuntimeError(
            "profile route effective_from must be earlier than effective_until")


def _validate_route_time(value: datetime | None, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, datetime):
        raise ProfileRuntimeError(f"{field} must be a datetime or None")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProfileRuntimeError(f"{field} must be timezone-aware")


def _route_matches_context(
    route: ProfileRouteRecord,
    *,
    tenant_ref: str,
    farm_ref: str,
    effective_time: datetime | None,
) -> bool:
    if route.status != ROUTE_STATUS_ACTIVE:
        return False
    if route.tenant_ref != tenant_ref or route.farm_ref != farm_ref:
        return False
    if effective_time is None:
        return route.effective_from is None and route.effective_until is None
    if route.effective_from is not None and route.effective_from > effective_time:
        return False
    if route.effective_until is not None and effective_time >= route.effective_until:
        return False
    return True


def _assert_route_matches_descriptor(
    route: ProfileRouteRecord,
    descriptor: ProfileRuntimeDescriptor,
) -> None:
    expected = {
        "profile_ref": descriptor.profile_ref,
        "pack_ref": descriptor.pack_ref,
        "pack_activation_set_ref": descriptor.pack_activation_set_ref,
        "active_artifact_set_ref": descriptor.active_artifact_set_ref,
    }
    for field, value in expected.items():
        if getattr(route, field) != value:
            raise ProfileRuntimeError(
                f"profile route {route.route_id!r} {field} does not match "
                "the routed descriptor")
    if route.descriptor_identity is not None:
        actual = profile_runtime_descriptor_identity(descriptor)
        if route.descriptor_identity != actual:
            raise ProfileRuntimeError(
                f"profile route {route.route_id!r} descriptor identity does "
                "not match the routed descriptor")


def _validate_profile_package_name(package_name: str) -> None:
    if not isinstance(package_name, str) or not package_name:
        raise ProfileRuntimeError("active profile package name must not be empty")
    path = Path(package_name)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
        raise ProfileRuntimeError(
            "active profile package names must be simple repository-local "
            f"directory names: {package_name!r}")
    if not package_name.startswith("profile_"):
        raise ProfileRuntimeError(
            f"active profile package must be a profile_* directory: {package_name!r}")


def _reject_duplicate_descriptor_refs(
    candidates: tuple[ProfileDescriptorCandidate, ...],
) -> None:
    fields = (
        "profile_ref",
        "pack_ref",
        "pack_activation_set_ref",
        "active_artifact_set_ref",
        "context_snapshot_id_prefix",
        "code_binding_profile_ref",
        "evidence_policy_ref",
    )
    for field in fields:
        seen: dict[str, str] = {}
        for candidate in candidates:
            value = getattr(candidate.descriptor, field)
            if value in seen:
                raise ProfileRuntimeError(
                    f"duplicate {field} {value!r} in descriptor candidates "
                    f"{seen[value]!r} and {candidate.package_name!r}")
            seen[value] = candidate.package_name


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
