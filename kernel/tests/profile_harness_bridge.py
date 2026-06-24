"""Root bridge helper for profile-local engineering test harnesses.

This module is intentionally not a pytest test module. D6a adds the bridge
helper and profile descriptor without moving profile tests or changing
conformance evidence writer semantics.
"""
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Iterable


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
HARNESS_DESCRIPTOR_FILENAME = "profile_test_harness.json"
DEFAULT_PROFILE_PACKAGE = "profile_si_ffs"
DEFAULT_DESCRIPTOR = (
    PACKAGE_ROOT
    / DEFAULT_PROFILE_PACKAGE
    / "tests"
    / HARNESS_DESCRIPTOR_FILENAME
)
EXPECTED_SCHEMA_VERSION = "profile_test_harness_v0_1"
EXPECTED_ROOT_BRIDGE = "kernel/tests/profile_harness_bridge.py"
EXPECTED_DESCRIPTOR_KEYS = frozenset({
    "artifactKind",
    "schemaVersion",
    "profilePackage",
    "engineeringTestsOnly",
    "platformConformance",
    "executedEvidence",
    "evidenceWriter",
    "rootBridge",
    "testModules",
    "notes",
})


class ProfileHarnessBridgeError(ValueError):
    """Raised when a profile test harness descriptor is unsafe or malformed."""


@dataclass(frozen=True)
class ProfileTestHarness:
    profile_package: str
    descriptor_path: Path
    test_modules: tuple[str, ...]


def load_profile_harness_descriptor(
    descriptor_path: Path = DEFAULT_DESCRIPTOR,
    *,
    package_root: Path = PACKAGE_ROOT,
) -> ProfileTestHarness:
    """Load and validate a profile-local engineering-test descriptor."""
    path, profile_package = _resolve_descriptor_path(
        descriptor_path,
        package_root=package_root,
    )
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileHarnessBridgeError(
            f"harness descriptor unreadable at {path}: {exc}") from exc

    _expect(isinstance(doc, dict), "descriptor must be a JSON object")
    keys = set(doc)
    unknown = sorted(keys - EXPECTED_DESCRIPTOR_KEYS)
    missing = sorted(EXPECTED_DESCRIPTOR_KEYS - keys)
    _expect(not unknown, f"unknown top-level key(s): {', '.join(unknown)}")
    _expect(not missing, f"missing top-level key(s): {', '.join(missing)}")
    _expect(doc.get("artifactKind") == "profile_test_harness_scaffold",
            "artifactKind must be profile_test_harness_scaffold")
    _expect(doc.get("schemaVersion") == EXPECTED_SCHEMA_VERSION,
            f"schemaVersion must be {EXPECTED_SCHEMA_VERSION}")
    _expect(doc.get("profilePackage") == profile_package,
            f"profilePackage must be {profile_package}")
    _expect(doc.get("engineeringTestsOnly") is True,
            "engineeringTestsOnly must be true")
    _expect(doc.get("platformConformance") is False,
            "platformConformance must be false")
    _expect(doc.get("executedEvidence") is False,
            "executedEvidence must be false")
    _expect(doc.get("evidenceWriter") is None,
            "evidenceWriter must be null")
    _expect(doc.get("rootBridge") == EXPECTED_ROOT_BRIDGE,
            f"rootBridge must be {EXPECTED_ROOT_BRIDGE}")

    modules = doc.get("testModules")
    _expect(isinstance(modules, list), "testModules must be a list")
    seen_modules: set[str] = set()
    for module_name in modules:
        _expect(isinstance(module_name, str) and module_name,
                "test module names must be non-empty strings")
        _expect(module_name.startswith(f"{profile_package}.tests."),
                f"test modules must stay under {profile_package}.tests")
        _expect(module_name not in seen_modules,
                f"duplicate test module {module_name}")
        seen_modules.add(module_name)

    notes = doc.get("notes")
    _expect(isinstance(notes, list), "notes must be a list")
    for note in notes:
        _expect(isinstance(note, str) and note,
                "notes must contain non-empty strings")

    return ProfileTestHarness(
        profile_package=doc["profilePackage"],
        descriptor_path=path,
        test_modules=tuple(modules),
    )


def discover_profile_harness_descriptors(
    package_root: Path = PACKAGE_ROOT,
) -> tuple[ProfileTestHarness, ...]:
    """Discover profile-local engineering-test harness descriptors.

    Discovery is deliberately narrow: immediate `profile_*` children only, with
    descriptorless packages omitted. A descriptor-bearing package must validate
    fail-closed, so a malformed harness cannot disappear silently.
    """
    root = _resolve_package_root(package_root)
    harnesses: list[ProfileTestHarness] = []
    seen_modules: dict[str, str] = {}
    for profile_dir in sorted(root.iterdir(), key=lambda p: p.name):
        if not profile_dir.is_dir() or not profile_dir.name.startswith("profile_"):
            continue
        descriptor = profile_dir / "tests" / HARNESS_DESCRIPTOR_FILENAME
        if not descriptor.exists() and not descriptor.is_symlink():
            continue
        harness = load_profile_harness_descriptor(
            descriptor,
            package_root=root,
        )
        for module_name in harness.test_modules:
            prior_package = seen_modules.get(module_name)
            _expect(
                prior_package is None,
                f"duplicate test module {module_name} across "
                f"{prior_package} and {harness.profile_package}",
            )
            seen_modules[module_name] = harness.profile_package
        harnesses.append(harness)
    return tuple(harnesses)


def iter_profile_test_modules(
    harness: ProfileTestHarness | None = None,
) -> Iterable[ModuleType]:
    """Import profile-local test modules declared by the descriptor."""
    selected = harness or load_profile_harness_descriptor()
    for module_name in selected.test_modules:
        yield importlib.import_module(module_name)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise ProfileHarnessBridgeError(message)


def _resolve_package_root(package_root: Path) -> Path:
    try:
        return Path(package_root).resolve(strict=True)
    except OSError as exc:
        raise ProfileHarnessBridgeError(
            f"package root {package_root} is unavailable: {exc}") from exc


def _resolve_descriptor_path(
    descriptor_path: Path,
    *,
    package_root: Path,
) -> tuple[Path, str]:
    raw_path = Path(descriptor_path)
    _expect(
        raw_path.name == HARNESS_DESCRIPTOR_FILENAME,
        f"descriptor file name must be {HARNESS_DESCRIPTOR_FILENAME}",
    )
    _expect(
        raw_path.parent.name == "tests",
        "descriptor parent directory must be tests",
    )
    profile_dir = raw_path.parent.parent
    _expect(
        profile_dir.name.startswith("profile_"),
        "profile directory must start with profile_",
    )
    root = _resolve_package_root(package_root)
    try:
        resolved_profile_dir = profile_dir.resolve(strict=True)
        resolved_descriptor = raw_path.resolve(strict=True)
    except OSError as exc:
        raise ProfileHarnessBridgeError(
            f"harness descriptor path unavailable: {exc}") from exc
    _expect(
        resolved_profile_dir.parent == root,
        "profile directory must be an immediate child of package root",
    )
    try:
        resolved_descriptor.relative_to(resolved_profile_dir)
    except ValueError as exc:
        raise ProfileHarnessBridgeError(
            "harness descriptor escapes the profile directory") from exc
    return resolved_descriptor, resolved_profile_dir.name
