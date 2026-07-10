"""Deterministic all-test inventory and outcome writer for issue #168.

The historical platform evidence hook intentionally covers only root
conformance call phases.  This plugin is separate: it inventories every item,
records setup/call/teardown outcomes, and preserves the original callable
module behind root star-import bridges.  It omits durations, terminal output,
absolute paths, and timestamps so two clean runs can be compared byte for
byte.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest


SCHEMA_VERSION = "ofarm.review-baseline-pytest-results.v1"
_COLLECTED: list[dict[str, Any]] = []
_DESELECTED: list[dict[str, Any]] = []
_SEEN_NODEIDS: set[str] = set()
_REPORTS: dict[str, list[dict[str, str]]] = {}
_COLLECTION_ERRORS: list[dict[str, str]] = []
_WARNINGS: set[tuple[str, str, str, str]] = set()


def pytest_addoption(parser):
    group = parser.getgroup("review-baseline")
    group.addoption(
        "--review-baseline-results",
        action="store",
        default=None,
        help="write deterministic complete-test inventory JSON to this path",
    )


def _relative_source(item) -> str | None:
    try:
        source = inspect.getsourcefile(item.obj)
    except (AttributeError, OSError, TypeError):
        source = None
    if not source:
        return None
    try:
        return Path(source).resolve().relative_to(
            Path(item.config.rootpath).resolve()
        ).as_posix()
    except (OSError, ValueError):
        return None


def _entry(item) -> dict[str, Any]:
    obj = getattr(item, "obj", None)
    source_module = getattr(obj, "__module__", None)
    if not source_module:
        source_module = getattr(getattr(item, "module", None), "__name__", None)
    return {
        "nodeid": item.nodeid.replace("\\", "/"),
        "sourceModule": source_module,
        "sourcePath": _relative_source(item),
    }


def pytest_itemcollected(item):
    entry = _entry(item)
    if not entry["sourceModule"] or not entry["sourcePath"]:
        _COLLECTION_ERRORS.append({
            "collector": entry["nodeid"],
            "outcome": "missing-source-mapping",
        })
    if entry["nodeid"] in _SEEN_NODEIDS:
        _COLLECTION_ERRORS.append({
            "collector": entry["nodeid"],
            "outcome": "duplicate-nodeid",
        })
    _SEEN_NODEIDS.add(entry["nodeid"])
    _COLLECTED.append(entry)


def pytest_deselected(items):
    for item in items:
        entry = _entry(item)
        _DESELECTED.append(entry)


def pytest_collectreport(report):
    if report.failed:
        _COLLECTION_ERRORS.append({
            "collector": report.nodeid.replace("\\", "/"),
            "outcome": "failed",
        })


def pytest_runtest_logreport(report):
    if report.when not in {"setup", "call", "teardown"}:
        return
    phase: dict[str, str] = {
        "phase": report.when,
        "outcome": report.outcome,
    }
    if getattr(report, "wasxfail", None):
        phase["expectedFailure"] = str(report.wasxfail)
        phase["classification"] = (
            "xfailed" if report.outcome == "skipped" else "xpassed"
        )
    if report.outcome == "skipped":
        longrepr = getattr(report, "longrepr", None)
        if isinstance(longrepr, tuple) and len(longrepr) == 3:
            phase["reason"] = str(longrepr[2])
    _REPORTS.setdefault(report.nodeid.replace("\\", "/"), []).append(phase)


def pytest_warning_recorded(warning_message, when, nodeid, location):
    del location  # absolute site-package paths are deliberately not evidence
    _WARNINGS.add((
        (nodeid or "").replace("\\", "/"),
        when,
        warning_message.category.__name__,
        str(warning_message.message),
    ))


def _terminal_outcome(phases: list[dict[str, str]]) -> str:
    if any(
        phase["outcome"] == "failed" and phase["phase"] in {"setup", "teardown"}
        for phase in phases
    ):
        return "error"
    if any(phase.get("classification") == "xpassed" for phase in phases):
        return "xpassed"
    if any(phase.get("classification") == "xfailed" for phase in phases):
        return "xfailed"
    if any(
        phase["outcome"] == "failed" and phase["phase"] == "call"
        for phase in phases
    ):
        return "failed"
    if any(phase["outcome"] == "skipped" for phase in phases):
        return "skipped"
    if any(
        phase["phase"] == "call" and phase["outcome"] == "passed"
        for phase in phases
    ):
        return "passed"
    return "unavailable"


def _sorted_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(entries, key=lambda entry: (
        entry["nodeid"], entry.get("sourceModule") or "", entry.get("sourcePath") or ""
    ))


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    output_value = session.config.getoption("--review-baseline-results")
    if not output_value:
        return

    selected_entries = [_entry(item) for item in session.items]
    selected = {entry["nodeid"]: entry for entry in selected_entries}
    if len(selected) != len(selected_entries):
        _COLLECTION_ERRORS.append({
            "collector": "session.items",
            "outcome": "duplicate-selected-nodeid",
        })
    outcomes: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    counts = {
        "passed": 0,
        "failed": 0,
        "error": 0,
        "xfailed": 0,
        "xpassed": 0,
    }
    for nodeid in sorted(selected):
        phases = _REPORTS.get(nodeid, [])
        outcome = _terminal_outcome(phases)
        result = {
            **selected[nodeid],
            "outcome": outcome,
            "phases": phases,
        }
        outcomes.append(result)
        if outcome in counts:
            counts[outcome] += 1
        elif outcome == "skipped":
            reasons = [phase["reason"] for phase in phases if phase.get("reason")]
            skipped.append({
                **selected[nodeid],
                "reason": reasons[0] if reasons else "pytest skip",
            })
        else:
            unavailable.append({
                **selected[nodeid],
                "reason": (
                    "collection-only" if session.config.option.collectonly
                    else "selected test did not reach a terminal call outcome"
                ),
            })

    warnings = [
        {"nodeid": nodeid, "when": when, "category": category, "message": message}
        for nodeid, when, category, message in sorted(_WARNINGS)
    ]
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "collection": {
            "collected": _sorted_entries(_COLLECTED),
            "selected": _sorted_entries(selected_entries),
            "deselected": _sorted_entries(_DESELECTED),
            "errors": sorted(
                _COLLECTION_ERRORS,
                key=lambda entry: (entry["collector"], entry["outcome"]),
            ),
        },
        "execution": {
            "outcomes": outcomes,
            "skipped": skipped,
            "unavailable": unavailable,
        },
        "warnings": warnings,
        "summary": {
            "collected": len(_COLLECTED),
            "selected": len(selected_entries),
            **counts,
            "skipped": len(skipped),
            "deselected": len(_DESELECTED),
            "unavailable": len(unavailable),
            "collectionErrors": len(_COLLECTION_ERRORS),
            "warnings": len(warnings),
            "pytestExitStatus": int(exitstatus),
        },
    }
    output = Path(output_value)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
