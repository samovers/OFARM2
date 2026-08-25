#!/usr/bin/env python3
"""Fail-closed live admission for expensive pull-request review baselines."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast


MARKER = "OFARM2_BASELINE_ADMISSION"
ALLOWED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
ALLOWED_REVIEW_STATES = frozenset({"APPROVED", "COMMENTED"})
FULL_SHA = re.compile(r"[0-9a-f]{40}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
JsonObject = dict[str, object]
FetchJson = Callable[[str], JsonObject]


class AdmissionError(ValueError):
    """The event attempted baseline admission but did not satisfy the gate."""


@dataclass(frozen=True)
class Admission:
    eligible: bool
    reviewed_head_sha: str
    policy_sha: str
    reason: str


def _full_sha(value: object, field: str) -> str:
    if not isinstance(value, str) or FULL_SHA.fullmatch(value) is None:
        raise AdmissionError(f"{field} must be a full lowercase commit SHA")
    return value


def _positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise AdmissionError(f"{field} must be a positive integer")
    return value


def _object(value: object, field: str) -> JsonObject:
    if not isinstance(value, dict):
        raise AdmissionError(f"{field} must be an object")
    return cast(JsonObject, value)


def _review_admission(
    event: JsonObject,
    repository: str,
    fetch_json: FetchJson,
    policy_sha: str,
) -> Admission:
    event_repository = _object(event.get("repository"), "event repository")
    if event_repository.get("full_name") != repository:
        raise AdmissionError("event repository does not equal configured repository")

    event_review = _object(event.get("review"), "event review")
    event_pr = _object(event.get("pull_request"), "event pull request")
    review_id = _positive_int(event_review.get("id"), "event review id")
    pr_number = _positive_int(event_pr.get("number"), "event pull-request number")

    live_pr = fetch_json(f"/repos/{repository}/pulls/{pr_number}")
    live_review = fetch_json(
        f"/repos/{repository}/pulls/{pr_number}/reviews/{review_id}"
    )
    if _positive_int(live_pr.get("number"), "live pull-request number") != pr_number:
        raise AdmissionError("live pull-request identity changed")
    if _positive_int(live_review.get("id"), "live review id") != review_id:
        raise AdmissionError("live review identity changed")

    event_review_sha = _full_sha(event_review.get("commit_id"), "event review commit")
    review_sha = _full_sha(live_review.get("commit_id"), "live review commit")
    if event_review_sha != review_sha:
        raise AdmissionError("event and live review commits differ")
    live_head = _object(live_pr.get("head"), "live pull-request head")
    head_sha = _full_sha(live_head.get("sha"), "live pull-request head sha")
    if review_sha != head_sha:
        raise AdmissionError("live review commit does not equal the live pull-request head")

    body = live_review.get("body")
    if not isinstance(body, str) or MARKER not in body:
        return Admission(False, "", policy_sha, "live review has no admission footer")

    state = live_review.get("state")
    if not isinstance(state, str) or state.upper() not in ALLOWED_REVIEW_STATES:
        raise AdmissionError("live admission requires a COMMENTED or APPROVED review")
    association = live_review.get("author_association")
    if association not in ALLOWED_ASSOCIATIONS:
        raise AdmissionError("live admission reviewer lacks repository standing")

    expected_footer = [MARKER, f"head={review_sha}", "blockers=0"]
    if body.rstrip().splitlines()[-3:] != expected_footer:
        raise AdmissionError("live admission footer is malformed or not final")

    return Admission(True, review_sha, policy_sha, "live exact-head zero-Blocker review")


def decide(
    event_name: str,
    event: JsonObject,
    github_sha: str,
    repository: str,
    policy_sha: str,
    fetch_json: FetchJson | None = None,
) -> Admission:
    """Return a live-reviewed target or refuse an attempted admission."""

    admitted_policy_sha = _full_sha(policy_sha, "admission policy sha")
    if REPOSITORY.fullmatch(repository) is None:
        raise AdmissionError("repository must be an owner/name coordinate")
    if event_name == "push":
        if event.get("ref") != "refs/heads/main":
            raise AdmissionError("automatic full baselines are limited to main")
        target_sha = _full_sha(github_sha, "GITHUB_SHA")
        if event.get("after") != target_sha:
            raise AdmissionError("push event target does not equal GITHUB_SHA")
        return Admission(
            True, target_sha, admitted_policy_sha, "main-branch post-merge baseline"
        )
    if event_name == "pull_request_review":
        if fetch_json is None:
            raise AdmissionError("live GitHub reader is required for review admission")
        return _review_admission(event, repository, fetch_json, admitted_policy_sha)
    raise AdmissionError(f"unsupported baseline event {event_name!r}")


class GitHubReader:
    """Minimal authenticated GitHub API reader with a fixed API version."""

    def __init__(self, api_url: str, token: str) -> None:
        if not api_url.startswith("https://") or not token:
            raise AdmissionError("GitHub API URL and token are required")
        self._api_url = api_url.rstrip("/")
        self._token = token

    def __call__(self, path: str) -> JsonObject:
        request = urllib.request.Request(
            f"{self._api_url}{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "ofarm2-review-baseline-admission",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise AdmissionError("live GitHub admission read failed") from exc
        return _object(payload, "live GitHub response")


def _write_output(path: Path, admission: Admission) -> None:
    if "\n" in admission.reason or "\r" in admission.reason:
        raise AdmissionError("admission reason must be one line")
    with path.open("a", encoding="utf-8") as output:
        output.write(f"eligible={'true' if admission.eligible else 'false'}\n")
        output.write(f"reviewed_head_sha={admission.reviewed_head_sha}\n")
        output.write(f"policy_sha={admission.policy_sha}\n")
        output.write(f"reason={admission.reason}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", type=Path, required=True)
    parser.add_argument("--github-sha", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--policy-sha", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()

    event = json.loads(args.event_path.read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise AdmissionError("GitHub event payload must be an object")
    fetch_json: FetchJson | None = None
    if args.event_name == "pull_request_review":
        fetch_json = GitHubReader(
            os.environ.get("GITHUB_API_URL", "https://api.github.com"),
            os.environ.get("GITHUB_TOKEN", ""),
        )
    admission = decide(
        args.event_name,
        cast(JsonObject, event),
        args.github_sha,
        args.repository,
        args.policy_sha,
        fetch_json,
    )
    _write_output(args.github_output, admission)
    print(f"baseline admission: {admission.reason}; policy={admission.policy_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
