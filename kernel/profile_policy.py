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


def load_evidence_review_policy(supported_checks=None) -> dict:
    """The active profile's evidence-review policy document, FULLY validated, or
    raise ProfilePolicyError. Validation is exhaustive on purpose: every shape the
    kernel later indexes/compares is checked here so no malformed policy can crash
    downstream (a missing/malformed policy must fail CLOSED, never crash). If
    `supported_checks` (the kernel's generic floor-check vocabulary) is given,
    every floor item must be one of them — an unknown item like "banana" cannot
    silently pass and KeyError in the sufficiency builder."""
    path = config.EVIDENCE_POLICY_PATH
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ProfilePolicyError(
            f"evidence-review policy unreadable at {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ProfilePolicyError("evidence-review policy is not a JSON object")

    floor = doc.get("operationFloor")
    if not isinstance(floor, dict):
        raise ProfilePolicyError("evidence-review policy lacks an operationFloor object")
    hard, soft = floor.get("hardItems"), floor.get("softItems")
    if not isinstance(hard, list) or not isinstance(soft, list):
        raise ProfilePolicyError("operationFloor.hardItems / softItems must be lists")
    if not all(isinstance(i, str) for i in (*hard, *soft)):
        raise ProfilePolicyError("operationFloor items must be strings")
    overlap = set(hard) & set(soft)
    if overlap:
        raise ProfilePolicyError(
            f"operationFloor items appear in BOTH hard and soft: {sorted(overlap)}")
    if supported_checks is not None:
        unknown = (set(hard) | set(soft)) - set(supported_checks)
        if unknown:
            raise ProfilePolicyError(
                f"operationFloor names unsupported floor item(s) {sorted(unknown)}; "
                f"the kernel supports {sorted(supported_checks)}")

    # a PRESENT-but-non-dict advisories block (incl. JSON null) is malformed; each
    # named rule block must also be a dict, and doseRange bounds numeric + ordered
    advisories = doc.get("advisories", {})
    if not isinstance(advisories, dict):
        raise ProfilePolicyError(
            "evidence-review policy 'advisories' must be a JSON object when present")
    for name in ("authorisationMismatch", "doseRange"):
        block = advisories.get(name, {})
        if not isinstance(block, dict):
            raise ProfilePolicyError(f"advisories.{name} must be a JSON object when present")
    dose = advisories.get("doseRange", {})
    lo, hi = dose.get("min"), dose.get("max")
    for label, val in (("min", lo), ("max", hi)):
        if val is not None and (isinstance(val, bool) or not isinstance(val, (int, float))):
            raise ProfilePolicyError(
                f"advisories.doseRange.{label} must be a number when present")
    if lo is not None and hi is not None and lo > hi:
        raise ProfilePolicyError(f"advisories.doseRange.min ({lo}) exceeds max ({hi})")
    return doc


def operation_floor(supported_checks=None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The active profile's OPERATION_CLAIM evidence floor as (hardItems,
    softItems) — sourced from package content, never a kernel constant. Pass the
    kernel's generic check vocabulary as `supported_checks` so an unknown floor
    item fails closed at load rather than KeyError-ing in the sufficiency builder."""
    floor = load_evidence_review_policy(supported_checks)["operationFloor"]
    return tuple(floor["hardItems"]), tuple(floor["softItems"])


def advisory_rules() -> dict:
    """The active profile's advisory rules (authorisationMismatch, doseRange).
    Empty mapping when the policy declares none."""
    return load_evidence_review_policy().get("advisories", {})
