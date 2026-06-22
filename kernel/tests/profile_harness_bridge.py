"""Root bridge helper for profile-local engineering test harnesses.

This module is intentionally not a pytest test module. D6a adds the bridge
helper and profile descriptor without changing collection, test count, or
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

    _expect(doc.get("artifactKind") == "profile_test_harness_scaffold",
            "artifactKind must be profile_test_harness_scaffold")
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

    modules = doc.get("testModules")
    _expect(isinstance(modules, list), "testModules must be a list")
    for module_name in modules:
        _expect(isinstance(module_name, str) and module_name,
                "test module names must be non-empty strings")
        _expect(module_name.startswith("profile_si_ffs.tests."),
                "test modules must stay under profile_si_ffs.tests")

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
