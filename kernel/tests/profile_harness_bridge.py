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
DEFAULT_DESCRIPTOR = (
    PACKAGE_ROOT
    / "profile_si_ffs"
    / "tests"
    / "profile_test_harness.json"
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
) -> ProfileTestHarness:
    """Load and validate a profile-local engineering-test descriptor."""
    path = descriptor_path.resolve()
    doc = json.loads(path.read_text(encoding="utf-8"))

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
    _expect(doc.get("profilePackage") == "profile_si_ffs",
            "profilePackage must be profile_si_ffs")
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
    for module_name in modules:
        _expect(isinstance(module_name, str) and module_name,
                "test module names must be non-empty strings")
        _expect(module_name.startswith("profile_si_ffs.tests."),
                "test modules must stay under profile_si_ffs.tests")

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
