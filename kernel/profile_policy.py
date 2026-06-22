"""Generic loader for the active profile's evidence-review policy (M2 P5).

The SI evidence FLOOR (which named checks are hard vs soft), its display
metadata, and the advisory rules are PROFILE / PACKAGE content, not generic
Kernel/Core law — the kernel provides the generic, Core-payload-shaped check
logic (kernel/sufficiency.py) and reads profile-owned policy data from the
active profile through this loader. Per the M2 mechanism-boundary stop rule, no
Slovenia-specific floor value lives in kernel/*.py; it lives in the profile
policy file (config.EVIDENCE_POLICY_PATH) and is read here.

Fail closed: a missing or malformed policy raises ProfilePolicyError, which the
gate turns into a governed RuntimeProblem (never a silent permissive default,
never a crash). The policy is read fresh per call so the active profile's policy
file is authoritative — changing it changes behavior without touching kernel/.
"""
from __future__ import annotations

import json
import string

from . import config
from .problems import REGISTERED_REASON_CODES


INSUFFICIENCY_REASON_CODES = frozenset({
    "MISSING_REQUIRED_EVIDENCE",
    "MISSING_NORMALIZED_INTERPRETATION",
    "MISSING_PROVENANCE_LINK",
    "CHAIN_OF_CUSTODY_PARTIAL",
    "CHAIN_OF_CUSTODY_UNKNOWN",
    "BASIS_NOT_RETAINED",
    "CONFLICTING_EVIDENCE",
    "ATTESTATION_AUTHORITY_MISSING",
    "AMBIGUOUS_PRODUCT_ID",
    "TIMESTAMP_INCOMPLETE",
    "SOURCE_QUALITY_LOW",
    "MACHINE_RECORD_PARTIAL",
    "HUMAN_MACHINE_CONFLICT",
    "LATE_EVIDENCE_POST_OUTPUT",
    "LATE_EVIDENCE_POST_SUBMISSION",
})

DISPLAY_TEXT_FIELDS = (
    "ruleRefPrefix",
    "operationFloorClaimStatement",
    "operationFloorAllowRationale",
    "hardMissingRationaleTemplate",
    "softMissingRationaleTemplate",
    "durableProofBundleLabel",
)
DISPLAY_TEMPLATE_FIELDS = frozenset({"missing"})


class ProfilePolicyError(Exception):
    """The active profile's evidence-review policy is missing or malformed —
    the floor cannot be evaluated, so the commit must fail closed."""


def _require_text(obj: dict, key: str, where: str) -> str:
    val = obj.get(key)
    if not isinstance(val, str) or not val.strip():
        raise ProfilePolicyError(f"{where}.{key} must be a non-empty string")
    return val


def _validate_template(label: str, template: str) -> None:
    try:
        parsed = list(string.Formatter().parse(template))
    except ValueError as exc:
        raise ProfilePolicyError(f"display.{label} has malformed template braces") from exc
    fields = {field for _, field, _, _ in parsed if field}
    unknown = fields - DISPLAY_TEMPLATE_FIELDS
    if unknown:
        raise ProfilePolicyError(
            f"display.{label} uses unsupported template field(s) {sorted(unknown)}")


def _validate_display(doc: dict, floor_items: set[str]) -> None:
    display = doc.get("display")
    if not isinstance(display, dict):
        raise ProfilePolicyError(
            "evidence-review policy lacks a display metadata object")
    for key in DISPLAY_TEXT_FIELDS:
        _require_text(display, key, "display")

    prefix = display["ruleRefPrefix"]
    if not prefix.startswith("rule:"):
        raise ProfilePolicyError("display.ruleRefPrefix must start with 'rule:'")
    if prefix.endswith("."):
        raise ProfilePolicyError("display.ruleRefPrefix must not end with '.'")
    _validate_template("hardMissingRationaleTemplate",
                       display["hardMissingRationaleTemplate"])
    _validate_template("softMissingRationaleTemplate",
                       display["softMissingRationaleTemplate"])

    items = display.get("floorItems")
    if not isinstance(items, dict):
        raise ProfilePolicyError("display.floorItems must be a JSON object")
    missing = floor_items - set(items)
    extra = set(items) - floor_items
    if missing:
        raise ProfilePolicyError(
            f"display.floorItems lacks metadata for floor item(s) {sorted(missing)}")
    if extra:
        raise ProfilePolicyError(
            f"display.floorItems names non-floor item(s) {sorted(extra)}")

    for name, block in items.items():
        if not isinstance(block, dict):
            raise ProfilePolicyError(f"display.floorItems.{name} must be a JSON object")
        _require_text(block, "label", f"display.floorItems.{name}")
        rule_ref = block.get("ruleRef")
        if rule_ref is not None:
            if not isinstance(rule_ref, str) or not rule_ref.strip():
                raise ProfilePolicyError(
                    f"display.floorItems.{name}.ruleRef must be a non-empty string")
            if not rule_ref.startswith(prefix + "."):
                raise ProfilePolicyError(
                    f"display.floorItems.{name}.ruleRef must be under {prefix!r}")
        for key, allowed in (
            ("insufficiencyReasonCode", INSUFFICIENCY_REASON_CODES),
            ("reviewReasonCode", REGISTERED_REASON_CODES),
        ):
            val = block.get(key)
            if val is not None and (not isinstance(val, str) or val not in allowed):
                raise ProfilePolicyError(
                    f"display.floorItems.{name}.{key} is not a registered code")


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
    _validate_display(doc, set(hard) | set(soft))

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


def operation_floor_with_display(supported_checks=None) -> tuple[tuple[str, ...],
                                                                 tuple[str, ...], dict]:
    """The active profile's OPERATION_CLAIM floor plus its display metadata.
    Display strings and rule refs are profile/package content; the kernel uses
    them without treating them as Core law."""
    doc = load_evidence_review_policy(supported_checks)
    floor = doc["operationFloor"]
    return tuple(floor["hardItems"]), tuple(floor["softItems"]), doc["display"]


def operation_floor_display(supported_checks=None) -> dict:
    """Profile-owned display metadata for OPERATION_CLAIM sufficiency cases."""
    return load_evidence_review_policy(supported_checks)["display"]


def floor_item_rule_ref(display: dict, item: str) -> str:
    """Rule ref for a floor item, using an explicit item ref when present."""
    block = display["floorItems"].get(item, {})
    return block.get("ruleRef") or f"{display['ruleRefPrefix']}.{item}"


def floor_item_insufficiency_reason_code(display: dict, item: str) -> str | None:
    """Optional EvidenceSufficiencyCase insufficiency code for a floor item."""
    return display["floorItems"].get(item, {}).get("insufficiencyReasonCode")


def floor_item_review_reason_code(display: dict, item: str) -> str | None:
    """Optional RuntimeProblem reason code for a review-routed floor item."""
    return display["floorItems"].get(item, {}).get("reviewReasonCode")


def format_display_template(display: dict, template_key: str, *, missing: list[str]) -> str:
    """Render a validated profile display template."""
    return display[template_key].format(missing=missing)


def advisory_rules() -> dict:
    """The active profile's advisory rules (authorisationMismatch, doseRange).
    Empty mapping when the policy declares none."""
    return load_evidence_review_policy().get("advisories", {})
