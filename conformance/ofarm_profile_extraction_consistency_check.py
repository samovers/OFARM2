#!/usr/bin/env python3
"""Consistency guard for SI profile extraction inventory/status docs.

This is repository tooling, not OFARM law, not a runtime profile loader, and
not the future L5 country-term allowlist. It catches drift between the
profile-local extraction README, the navigation-only index, the current
contract-comment audit state, and the certification non-claim language.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
EXTRACTION_DIR = PKG / "profile_si_ffs" / "extraction_inventory"
README = EXTRACTION_DIR / "README.md"
NAV_INDEX = EXTRACTION_DIR / "profile_navigation_index.json"
CERT_PLAN = EXTRACTION_DIR / "core_country_neutrality_certification_plan.md"
ALLOWLIST_PLAN = EXTRACTION_DIR / "core_country_term_audit_allowlist_plan.md"
INITIAL_REVIEW = EXTRACTION_DIR / "core_country_term_audit_initial_review.md"


def rel(path: Path) -> str:
    return str(path.relative_to(PKG))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def markdown_files_listed_in_readme() -> set[str]:
    """Return backticked inventory paths from the README Files section."""
    text = read(README)
    in_files = False
    listed: set[str] = set()
    for line in text.splitlines():
        if line.strip() == "## Files":
            in_files = True
            continue
        if in_files and line.startswith("## "):
            break
        if not in_files:
            continue
        match = re.match(r"- `([^`]+)`", line)
        if not match:
            continue
        name = match.group(1)
        if "/" in name:
            listed.add(name)
        else:
            listed.add(f"profile_si_ffs/extraction_inventory/{name}")
    return listed


def check_readme_and_navigation_index(failures: list[str]) -> None:
    index = json.loads(read(NAV_INDEX))
    entries = index.get("entries", [])
    entry_paths = {entry.get("path") for entry in entries}

    readme_paths = markdown_files_listed_in_readme()
    missing_from_index = sorted(readme_paths - entry_paths)
    if missing_from_index:
        failures.append(
            "README files missing from profile_navigation_index.json: "
            + ", ".join(missing_from_index)
        )

    for entry in entries:
        path = entry.get("path")
        if not isinstance(path, str):
            failures.append("navigation index entry missing string path")
            continue
        if not (PKG / path).exists():
            failures.append(f"navigation index path does not exist: {path}")

    expected_flags = {
        "navigationOnly": True,
        "capabilityClaim": False,
        "runtimeSupport": False,
    }
    for key, expected in expected_flags.items():
        actual = index.get(key)
        if actual is not expected:
            failures.append(
                f"profile_navigation_index.json {key} is {actual!r}, "
                f"expected {expected!r}"
            )

    boundary_text = " ".join(
        [
            str(index.get("artifactKind", "")),
            str(index.get("schemaVersion", "")),
            str(index.get("machineVisibleBoundary", {}).get("label", "")),
            str(index.get("proseBoundary", "")),
        ]
    ).lower()
    for required in ("navigation", "not a manifest", "not runtime support"):
        if required not in boundary_text:
            failures.append(
                "profile_navigation_index.json boundary text missing "
                f"{required!r}"
            )


def check_navigation_index_not_runtime_consumed(failures: list[str]) -> None:
    """Keep the JSON index out of kernel/runtime consumption paths."""
    forbidden = ("profile_navigation_index", "profile_navigation_index.json")
    for path in sorted((PKG / "kernel").rglob("*.py")):
        text = read(path)
        for needle in forbidden:
            if needle in text:
                failures.append(
                    f"{rel(path)} references {needle}; navigation index must "
                    "not feed runtime or manifest code"
                )


def check_contract_core_seed_terms(failures: list[str]) -> None:
    pattern = re.compile(r"KMG-MID|GERK")
    contract_dir = PKG / "contracts" / "core"
    for path in sorted(contract_dir.rglob("*")):
        if not path.is_file():
            continue
        text = read(path)
        if pattern.search(text):
            failures.append(f"{rel(path)} still contains KMG-MID/GERK")


def check_certification_plan_not_stale(failures: list[str]) -> None:
    text = read(CERT_PLAN)
    stale_snippets = (
        "Contract comments mentioning KMG-MID/GERK | SI examples may remain",
        "`contracts/**` | `CONTRACT_COMMENT_REVIEW`",
    )
    for snippet in stale_snippets:
        if snippet in text:
            failures.append(
                "core_country_neutrality_certification_plan.md retains stale "
                f"blocker text: {snippet}"
            )

    required_snippets = (
        "Current status is below L5",
        "not proof that the end state has been reached",
        "whole-Core country/profile neutrality is already certified",
        "Closed Or Historical Blockers",
        "former KMG-MID/GERK comments were neutralized",
    )
    for snippet in required_snippets:
        if snippet not in text:
            failures.append(
                "core_country_neutrality_certification_plan.md missing "
                f"required non-claim or closed-blocker wording: {snippet}"
            )


def check_audit_docs_keep_nonclaim_language(failures: list[str]) -> None:
    allowlist_text = read(ALLOWLIST_PLAN)
    initial_text = read(INITIAL_REVIEW)

    allowlist_required = (
        "does not implement a\nmachine guard",
        "scan remains informational",
        "enforcing L5 machine guard",
    )
    for snippet in allowlist_required:
        if snippet not in allowlist_text:
            failures.append(
                "core_country_term_audit_allowlist_plan.md missing "
                f"non-claim wording: {snippet}"
            )

    initial_required = (
        "This is not the L5 machine guard",
        "not a line-level allowlist",
        "proof of Core certification",
        "below L5 until every remaining hit is\n  reviewed",
    )
    for snippet in initial_required:
        if snippet not in initial_text:
            failures.append(
                "core_country_term_audit_initial_review.md missing "
                f"non-claim wording: {snippet}"
            )


def main() -> int:
    failures: list[str] = []

    check_readme_and_navigation_index(failures)
    print("extraction README/navigation index check done")

    check_navigation_index_not_runtime_consumed(failures)
    print("navigation index runtime-consumption check done")

    check_contract_core_seed_terms(failures)
    print("contracts/core seed-term check done")

    check_certification_plan_not_stale(failures)
    print("certification plan drift check done")

    check_audit_docs_keep_nonclaim_language(failures)
    print("audit non-claim wording check done")

    for failure in failures:
        print(f"FAIL {failure}")
    print("RESULT:", "FAIL" if failures else "PASS", f"({len(failures)} failures)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
