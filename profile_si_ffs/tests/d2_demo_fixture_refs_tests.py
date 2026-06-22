"""D2a — SI demo fixture refs are available profile-locally.

Engineering tests only. They prove the new profile-local fixture support mirrors
the existing `kernel.demo` refs without moving `kernel/demo.py` or changing
payload behavior.
"""
from __future__ import annotations

from kernel import demo
from profile_si_ffs.test_fixtures import demo_refs


__all__ = [
    "test_d2_demo_refs_mirror_kernel_demo_compatibility_names",
    "test_d2_demo_refs_remain_fixture_support_not_profile_law",
]


def test_d2_demo_refs_mirror_kernel_demo_compatibility_names():
    assert demo_refs.DEMO_REF_NAMES == (
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

    mirrored = demo_refs.as_mapping()
    for name in demo_refs.DEMO_REF_NAMES:
        assert mirrored[name] == getattr(demo, name)


def test_d2_demo_refs_remain_fixture_support_not_profile_law():
    mirrored = demo_refs.as_mapping()

    assert mirrored["FARM"].startswith("farm:demo.")
    assert mirrored["FARMER"].startswith("party:demo.")
    assert mirrored["PHOTO_EVIDENCE"].startswith("evidence:demo.")
    assert "ASSERT_OPERATION_CLAIM" in mirrored["ACTION_CLASSES"]
