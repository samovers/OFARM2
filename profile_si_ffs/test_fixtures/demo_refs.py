"""Compatibility mirror for active SI demo fixture references.

D2a keeps `kernel.demo` as the source of public imports and aliases the current
values here so profile-local tests can start depending on profile-local fixture
support without changing any payloads or runtime behavior.
"""
from __future__ import annotations

from kernel import demo as _demo


DEMO_REF_NAMES = (
    "FARM",
    "FIELD",
    "CYCLE",
    "FARMER",
    "WORKER",
    "ADVISOR",
    "INSPECTOR",
    "AGENT",
    "SPRAYER",
    "APPLIED_RESOURCE",
    "PRODUCT_BINDING",
    "CROP_BINDING",
    "PHOTO_EVIDENCE",
    "ONBOARDING_EVIDENCE",
    "FARMER_GRANT",
    "WORKER_DELEGATION",
    "INSPECTOR_SHARE",
    "REGSR_SNAPSHOT",
    "VALID_FROM",
    "ACTION_CLASSES",
)
__all__ = DEMO_REF_NAMES + ("DEMO_REF_NAMES", "as_mapping")

FARM = _demo.FARM
FIELD = _demo.FIELD
CYCLE = _demo.CYCLE
FARMER = _demo.FARMER
WORKER = _demo.WORKER
ADVISOR = _demo.ADVISOR
INSPECTOR = _demo.INSPECTOR
AGENT = _demo.AGENT
SPRAYER = _demo.SPRAYER
APPLIED_RESOURCE = _demo.APPLIED_RESOURCE
PRODUCT_BINDING = _demo.PRODUCT_BINDING
CROP_BINDING = _demo.CROP_BINDING
PHOTO_EVIDENCE = _demo.PHOTO_EVIDENCE
ONBOARDING_EVIDENCE = _demo.ONBOARDING_EVIDENCE
FARMER_GRANT = _demo.FARMER_GRANT
WORKER_DELEGATION = _demo.WORKER_DELEGATION
INSPECTOR_SHARE = _demo.INSPECTOR_SHARE
REGSR_SNAPSHOT = _demo.REGSR_SNAPSHOT
VALID_FROM = _demo.VALID_FROM
ACTION_CLASSES = _demo.ACTION_CLASSES


def as_mapping() -> dict[str, object]:
    """Return the mirrored demo refs keyed by compatibility name."""
    return {name: globals()[name] for name in DEMO_REF_NAMES}
