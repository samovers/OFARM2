#!/usr/bin/env python3
"""Fail-closed admission for expensive pull-request review baselines."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


MARKER = "OFARM2_BASELINE_ADMISSION"
ALLOWED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
ALLOWED_REVIEW_STATES = frozenset({"APPROVED", "COMMENTED"})
FULL_SHA = re.compile(r"[0-9a-f]{40}")


class AdmissionError(ValueError):
    """The event attempted baseline admission but did not satisfy the gate."""


@dataclass(frozen=True)
class Admission:
    eligible: bool
    target_sha: str
    reason: str


def _full_sha(value: object, field: str) -> str:
    if not isinstance(value, str) or FULL_SHA.fullmatch(value) is None:
        raise AdmissionError(f"{field} must be a full lowercase commit SHA")
    return value


def _review_admission(event: dict[str, object]) -> Admission:
    review = event.get("review")
    pull_request = event.get("pull_request")
    if not isinstance(review, dict) or not isinstance(pull_request, dict):
        raise AdmissionError("review event is missing review or pull-request data")

    body = review.get("body")
    if not isinstance(body, str) or MARKER not in body:
        return Admission(False, "", "review has no baseline admission footer")

    review_sha = _full_sha(review.get("commit_id"), "review commit_id")
    head = pull_request.get("head")
    if not isinstance(head, dict):
        raise AdmissionError("review event is missing the pull-request head")
    head_sha = _full_sha(head.get("sha"), "pull-request head sha")
    if review_sha != head_sha:
        raise AdmissionError("review commit does not equal the current pull-request head")

    state = review.get("state")
    if not isinstance(state, str) or state.upper() not in ALLOWED_REVIEW_STATES:
        raise AdmissionError("baseline admission requires a COMMENTED or APPROVED review")

    association = review.get("author_association")
    if association not in ALLOWED_ASSOCIATIONS:
        raise AdmissionError("baseline admission reviewer lacks repository standing")

    expected_footer = [MARKER, f"head={review_sha}", "blockers=0"]
    body_lines = body.rstrip().splitlines()
    if body_lines[-3:] != expected_footer:
        raise AdmissionError("baseline admission footer is malformed or not final")

    return Admission(True, review_sha, "exact-head zero-Blocker review")


def decide(event_name: str, event: dict[str, object], github_sha: str) -> Admission:
    """Return the reviewed target or refuse an attempted admission."""

    if event_name == "push":
        if event.get("ref") != "refs/heads/main":
            raise AdmissionError("automatic full baselines are limited to main")
        target_sha = _full_sha(github_sha, "GITHUB_SHA")
        if event.get("after") != target_sha:
            raise AdmissionError("push event target does not equal GITHUB_SHA")
        return Admission(True, target_sha, "main-branch post-merge baseline")
    if event_name == "pull_request_review":
        return _review_admission(event)
    raise AdmissionError(f"unsupported baseline event {event_name!r}")


def _write_output(path: Path, admission: Admission) -> None:
    if "\n" in admission.reason or "\r" in admission.reason:
        raise AdmissionError("admission reason must be one line")
    with path.open("a", encoding="utf-8") as output:
        output.write(f"eligible={'true' if admission.eligible else 'false'}\n")
        output.write(f"target_sha={admission.target_sha}\n")
        output.write(f"reason={admission.reason}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", type=Path, required=True)
    parser.add_argument("--github-sha", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()

    event = json.loads(args.event_path.read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise AdmissionError("GitHub event payload must be an object")
    admission = decide(args.event_name, event, args.github_sha)
    _write_output(args.github_output, admission)
    print(f"baseline admission: {admission.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
