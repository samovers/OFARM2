"""Generic loader for the active profile's evidence-review policy (M2 P5).

The SI evidence FLOOR (which named checks are hard vs soft) and the advisory
rules are PROFILE / PACKAGE content, not generic Kernel/Core law — the kernel
provides the generic, Core-payload-shaped check logic (kernel/sufficiency.py) and
reads the floor *composition* and advisory rules from the active profile through
this loader. Per the M2 mechanism-boundary stop rule, no Slovenia-specific floor
value lives in kernel/*.py; it lives in the profile policy file
(config.EVIDENCE_POLICY_PATH) and is read here.

Fail closed: a missing or malformed policy raises ProfilePolicyError, which the
gate turns into a governed RuntimeProblem (never a silent permissive default,
never a crash). The policy is read fresh per call so the active profile's policy
file is authoritative — changing it changes behavior without touching kernel/.
"""
from __future__ import annotations

import json

from . import config


class ProfilePolicyError(Exception):
    """The active profile's evidence-review policy is missing or malformed —
    the floor cannot be evaluated, so the commit must fail closed."""


def load_evidence_review_policy() -> dict:
    """The active profile's evidence-review policy document, or raise."""
    path = config.EVIDENCE_POLICY_PATH
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ProfilePolicyError(
            f"evidence-review policy unreadable at {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ProfilePolicyError("evidence-review policy is not a JSON object")
    floor = doc.get("operationFloor")
    if (not isinstance(floor, dict)
            or not isinstance(floor.get("hardItems"), list)
            or not isinstance(floor.get("softItems"), list)):
        raise ProfilePolicyError(
            "evidence-review policy lacks a valid operationFloor {hardItems, softItems}")
    # a PRESENT-but-non-dict advisories block is malformed (incl. JSON null) — fail
    # closed at load time rather than crash downstream in operation_advisories
    if "advisories" in doc and not isinstance(doc["advisories"], dict):
        raise ProfilePolicyError(
            "evidence-review policy 'advisories' must be a JSON object when present")
    return doc


def operation_floor() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The active profile's OPERATION_CLAIM evidence floor as (hardItems,
    softItems) — sourced from package content, never a kernel constant."""
    floor = load_evidence_review_policy()["operationFloor"]
    return tuple(floor["hardItems"]), tuple(floor["softItems"])


def advisory_rules() -> dict:
    """The active profile's advisory rules (authorisationMismatch, doseRange).
    Empty mapping when the policy declares none."""
    return load_evidence_review_policy().get("advisories", {})
