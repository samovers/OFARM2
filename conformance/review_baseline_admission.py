#!/usr/bin/env python3
"""Trusted dispatch and live admission for expensive review baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast


ADMISSION_MARKER = "OFARM2_BASELINE_ADMISSION"
REVOCATION_MARKER = "OFARM2_BASELINE_REVOCATION"
ALLOWED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
PULL_REQUEST_REVOCATION_ACTIONS = frozenset(
    {"opened", "reopened", "synchronize", "closed"}
)
FULL_SHA = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[^\r\n]+Z")
EVIDENCE_SCHEMA = "ofarm.review-baseline-admission.v2"
GRAPHQL_COMMENT_PREFIX = "graphql:issue-comment:"
CALL_INPUT_FIELDS = frozenset(
    {
        "mode",
        "pull_request_number",
        "admission_comment_id",
        "reviewed_head_sha",
        "base_sha",
        "execution_merge_sha",
        "policy_sha",
        "review_body_sha256",
        "review_metadata",
        "revocation_reason",
    }
)
GRAPHQL_COMMENT_QUERY = """
query AdmissionComment($id: ID!) {
  node(id: $id) {
    ... on IssueComment {
      databaseId
      body
      authorAssociation
      createdAt
      updatedAt
      lastEditedAt
      isMinimized
      issue {
        number
        repository { nameWithOwner }
      }
    }
  }
}
"""
JsonObject = dict[str, object]
FetchJson = Callable[[str], JsonObject]


class AdmissionError(ValueError):
    """An event attempted a gate transition that was not valid."""


@dataclass(frozen=True)
class Admission:
    eligible: bool
    event_class: str
    repository: str
    pull_request_number: int | None
    admission_comment_id: int | None
    reviewed_head_sha: str
    base_sha: str
    execution_merge_sha: str
    policy_sha: str
    review_body_sha256: str
    review_state: str
    review_updated_at: str
    reviewer_association: str
    reason: str

    def evidence(self) -> JsonObject:
        return {"schemaVersion": EVIDENCE_SCHEMA, **asdict(self)}


@dataclass(frozen=True)
class GateDecision:
    dispatch: bool
    mode: str
    pull_request_number: int | None
    admission_comment_id: int | None
    inputs: dict[str, str]
    reason: str


def _full_sha(value: object, field: str) -> str:
    if not isinstance(value, str) or FULL_SHA.fullmatch(value) is None:
        raise AdmissionError(f"{field} must be a full lowercase commit SHA")
    return value


def _sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise AdmissionError(f"{field} must be a SHA-256 digest")
    return value


def _positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise AdmissionError(f"{field} must be a positive integer")
    return value


def _positive_int_text(value: object, field: str) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise AdmissionError(f"{field} must be a positive integer string")
    return _positive_int(int(value), field)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or "\r" in value or "\n" in value:
        raise AdmissionError(f"{field} must be non-empty one-line text")
    return value


def _timestamp(value: object, field: str) -> str:
    text = _text(value, field)
    if TIMESTAMP.fullmatch(text) is None:
        raise AdmissionError(f"{field} must be a UTC timestamp")
    return text


def _object(value: object, field: str) -> JsonObject:
    if not isinstance(value, dict):
        raise AdmissionError(f"{field} must be an object")
    return cast(JsonObject, value)


def _body_digest(body: str) -> str:
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _footer_head(body: object, marker: str, field: str) -> str | None:
    if not isinstance(body, str):
        return None
    marker_index = body.rfind(marker)
    if marker_index < 0:
        return None
    if marker_index > 0 and body[marker_index - 1] != "\n":
        return None
    footer = body[marker_index:]
    suffix = "\nblockers=0" if marker == ADMISSION_MARKER else ""
    match = re.fullmatch(
        rf"{re.escape(marker)}\nhead=([0-9a-f]{{40}}){suffix}\n?",
        footer,
    )
    if match is None:
        raise AdmissionError(f"{field} gate footer is malformed")
    return _full_sha(match.group(1), f"{field} footer head")


def _parent_shas(commit: JsonObject) -> list[str]:
    parents = commit.get("parents")
    if not isinstance(parents, list):
        raise AdmissionError("live execution merge commit has no parent list")
    return [
        _full_sha(_object(parent, "merge parent").get("sha"), "merge parent sha")
        for parent in parents
    ]


def _event_repository(event: JsonObject, repository: str) -> JsonObject:
    event_repository = _object(event.get("repository"), "event repository")
    if event_repository.get("full_name") != repository:
        raise AdmissionError("event repository does not equal configured repository")
    return event_repository


def _live_pull_request(
    repository: str,
    pr_number: int,
    fetch_json: FetchJson,
) -> JsonObject:
    live_pr = fetch_json(f"/repos/{repository}/pulls/{pr_number}")
    if _positive_int(live_pr.get("number"), "live pull-request number") != pr_number:
        raise AdmissionError("live pull-request identity changed")
    if live_pr.get("state") != "open":
        raise AdmissionError("live pull request is not open")
    return live_pr


def _bound_merge(
    repository: str,
    live_pr: JsonObject,
    reviewed_head_sha: str,
    fetch_json: FetchJson,
) -> tuple[str, str]:
    live_base = _object(live_pr.get("base"), "live pull-request base")
    base_sha = _full_sha(live_base.get("sha"), "live pull-request base sha")
    execution_merge_sha = _full_sha(
        live_pr.get("merge_commit_sha"), "live execution merge sha"
    )
    merge_commit = fetch_json(
        f"/repos/{repository}/git/commits/{execution_merge_sha}"
    )
    if _full_sha(merge_commit.get("sha"), "live merge commit sha") != (
        execution_merge_sha
    ):
        raise AdmissionError("live merge commit identity changed")
    if _parent_shas(merge_commit) != [base_sha, reviewed_head_sha]:
        raise AdmissionError("execution merge parents do not bind live base and head")
    return base_sha, execution_merge_sha


def _comment_admission(
    *,
    repository: str,
    pr_number: int,
    comment_id: int,
    policy_sha: str,
    fetch_json: FetchJson,
    expected_body: str | None = None,
) -> Admission:
    live_pr = _live_pull_request(repository, pr_number, fetch_json)
    live_comment = fetch_json(f"/repos/{repository}/issues/comments/{comment_id}")
    if _positive_int(live_comment.get("id"), "live comment id") != comment_id:
        raise AdmissionError("live admission-comment identity changed")
    if not str(live_comment.get("issue_url", "")).endswith(
        f"/repos/{repository}/issues/{pr_number}"
    ):
        raise AdmissionError("live admission comment belongs to another pull request")

    node_id = _text(live_comment.get("node_id"), "live comment node id")
    graph_comment = fetch_json(f"{GRAPHQL_COMMENT_PREFIX}{node_id}")
    if _positive_int(
        graph_comment.get("databaseId"), "GraphQL comment database id"
    ) != comment_id:
        raise AdmissionError("GraphQL admission-comment identity changed")
    graph_issue = _object(graph_comment.get("issue"), "GraphQL comment issue")
    graph_repository = _object(
        graph_issue.get("repository"), "GraphQL comment repository"
    )
    if (
        _positive_int(graph_issue.get("number"), "GraphQL issue number")
        != pr_number
        or graph_repository.get("nameWithOwner") != repository
    ):
        raise AdmissionError("GraphQL admission comment belongs to another pull request")
    if graph_comment.get("lastEditedAt") is not None:
        raise AdmissionError("an edited comment cannot admit a baseline")
    if graph_comment.get("isMinimized") is not False:
        raise AdmissionError("a minimized comment cannot admit a baseline")

    association = live_comment.get("author_association")
    if association not in ALLOWED_ASSOCIATIONS:
        raise AdmissionError("live admission commenter lacks repository standing")
    body = live_comment.get("body")
    if not isinstance(body, str):
        raise AdmissionError("live admission comment has no body")
    if graph_comment.get("body") != body:
        raise AdmissionError("REST and GraphQL admission-comment bodies differ")
    if expected_body is not None and body != expected_body:
        raise AdmissionError("event and live admission-comment bodies differ")
    footer_head = _footer_head(body, ADMISSION_MARKER, "live comment")
    if footer_head is None:
        raise AdmissionError("live admission comment has no final admission footer")

    created_at = _timestamp(live_comment.get("created_at"), "comment created_at")
    updated_at = _timestamp(live_comment.get("updated_at"), "comment updated_at")
    if (
        _timestamp(graph_comment.get("createdAt"), "GraphQL comment createdAt")
        != created_at
        or _timestamp(graph_comment.get("updatedAt"), "GraphQL comment updatedAt")
        != updated_at
    ):
        raise AdmissionError("REST and GraphQL comment timestamps differ")
    if created_at != updated_at:
        raise AdmissionError("an edited comment cannot admit a baseline")
    if graph_comment.get("authorAssociation") != association:
        raise AdmissionError("REST and GraphQL commenter associations differ")

    live_head = _object(live_pr.get("head"), "live pull-request head")
    head_sha = _full_sha(live_head.get("sha"), "live pull-request head sha")
    if footer_head != head_sha:
        raise AdmissionError("admission footer does not equal the live pull-request head")
    base_sha, execution_merge_sha = _bound_merge(
        repository, live_pr, head_sha, fetch_json
    )
    return Admission(
        True,
        "ISSUE_COMMENT_ADMISSION",
        repository,
        pr_number,
        comment_id,
        head_sha,
        base_sha,
        execution_merge_sha,
        policy_sha,
        _body_digest(body),
        "ACTIVE_UNEDITED",
        updated_at,
        cast(str, association),
        "live unedited exact-head zero-Blocker admission comment",
    )


def _empty_inputs(
    *,
    mode: str,
    pr_number: int,
    policy_sha: str,
    comment_id: int | None,
    revocation_reason: str,
) -> dict[str, str]:
    return {
        "mode": mode,
        "pull_request_number": str(pr_number),
        "admission_comment_id": str(comment_id or ""),
        "reviewed_head_sha": "",
        "base_sha": "",
        "execution_merge_sha": "",
        "policy_sha": policy_sha,
        "review_body_sha256": "",
        "review_metadata": "",
        "revocation_reason": revocation_reason,
    }


def _admission_inputs(admission: Admission) -> dict[str, str]:
    if not admission.eligible or admission.pull_request_number is None:
        raise AdmissionError("only an eligible review can be dispatched")
    if admission.admission_comment_id is None:
        raise AdmissionError("review admission has no comment identity")
    return {
        "mode": "admit",
        "pull_request_number": str(admission.pull_request_number),
        "admission_comment_id": str(admission.admission_comment_id),
        "reviewed_head_sha": admission.reviewed_head_sha,
        "base_sha": admission.base_sha,
        "execution_merge_sha": admission.execution_merge_sha,
        "policy_sha": admission.policy_sha,
        "review_body_sha256": admission.review_body_sha256,
        "review_metadata": json.dumps(
            {
                "association": admission.reviewer_association,
                "state": admission.review_state,
                "updated_at": admission.review_updated_at,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        "revocation_reason": "",
    }


def _ignored_gate(reason: str) -> GateDecision:
    return GateDecision(False, "ignore", None, None, {}, reason)


def gate_decision(
    event_name: str,
    event: JsonObject,
    repository: str,
    policy_sha: str,
    fetch_json: FetchJson | None = None,
) -> GateDecision:
    """Return a trusted reusable-workflow decision without executing PR code."""

    admitted_policy_sha = _full_sha(policy_sha, "admission policy sha")
    if REPOSITORY.fullmatch(repository) is None:
        raise AdmissionError("repository must be an owner/name coordinate")
    _event_repository(event, repository)

    if event_name == "pull_request_target":
        action = event.get("action")
        if action not in PULL_REQUEST_REVOCATION_ACTIONS:
            raise AdmissionError("unsupported pull-request state action")
        event_pr = _object(event.get("pull_request"), "event pull request")
        pr_number = _positive_int(event_pr.get("number"), "pull-request number")
        return GateDecision(
            False,
            "state-revocation",
            pr_number,
            None,
            {},
            f"pull-request {action} cancels admitted work through trusted concurrency",
        )

    if event_name != "issue_comment":
        raise AdmissionError(f"unsupported gate event {event_name!r}")
    issue = _object(event.get("issue"), "event issue")
    if not isinstance(issue.get("pull_request"), dict):
        return _ignored_gate("issue comment is not attached to a pull request")
    pr_number = _positive_int(issue.get("number"), "event pull-request number")
    comment = _object(event.get("comment"), "event comment")
    comment_id = _positive_int(comment.get("id"), "event comment id")
    association = comment.get("author_association")
    action = event.get("action")

    if association not in ALLOWED_ASSOCIATIONS:
        return _ignored_gate("commenter lacks repository standing")
    if action == "created":
        body = comment.get("body")
        admission_head = _footer_head(body, ADMISSION_MARKER, "event comment")
        if admission_head is not None:
            if fetch_json is None:
                raise AdmissionError("live GitHub reader is required for admission")
            admission = _comment_admission(
                repository=repository,
                pr_number=pr_number,
                comment_id=comment_id,
                policy_sha=admitted_policy_sha,
                fetch_json=fetch_json,
                expected_body=cast(str, body),
            )
            return GateDecision(
                True,
                "admit",
                pr_number,
                comment_id,
                _admission_inputs(admission),
                admission.reason,
            )
        revocation_head = _footer_head(body, REVOCATION_MARKER, "event comment")
        if revocation_head is not None:
            if fetch_json is None:
                raise AdmissionError("live GitHub reader is required for revocation")
            live_pr = _live_pull_request(repository, pr_number, fetch_json)
            live_head = _object(live_pr.get("head"), "live pull-request head")
            if revocation_head != _full_sha(
                live_head.get("sha"), "live pull-request head sha"
            ):
                raise AdmissionError("revocation footer does not equal live head")
            inputs = _empty_inputs(
                mode="revoke",
                pr_number=pr_number,
                policy_sha=admitted_policy_sha,
                comment_id=comment_id,
                revocation_reason="explicit-standing-reviewer-revocation",
            )
            return GateDecision(
                True,
                "revoke",
                pr_number,
                comment_id,
                inputs,
                "standing reviewer explicitly revoked admission",
            )
        return _ignored_gate("standing comment has no gate footer")

    prior_body: object
    if action == "edited":
        changes = _object(event.get("changes"), "event changes")
        body_change = _object(changes.get("body"), "event body change")
        prior_body = body_change.get("from")
    elif action == "deleted":
        prior_body = comment.get("body")
    else:
        raise AdmissionError("unsupported issue-comment action")
    prior_head = _footer_head(prior_body, ADMISSION_MARKER, "prior comment")
    if prior_head is None:
        return _ignored_gate("edited or deleted comment was not an admission")
    if fetch_json is None:
        raise AdmissionError("live GitHub reader is required for revocation")
    live_pr = _live_pull_request(repository, pr_number, fetch_json)
    live_head = _object(live_pr.get("head"), "live pull-request head")
    if prior_head != _full_sha(live_head.get("sha"), "live pull-request head sha"):
        return _ignored_gate("edited or deleted admission belongs to an older head")
    inputs = _empty_inputs(
        mode="revoke",
        pr_number=pr_number,
        policy_sha=admitted_policy_sha,
        comment_id=comment_id,
        revocation_reason=f"admission-comment-{action}",
    )
    return GateDecision(
        True,
        "revoke",
        pr_number,
        comment_id,
        inputs,
        f"standing reviewer admission comment was {action}",
    )


def _workflow_call_admission(
    event_name: str,
    event: JsonObject,
    repository: str,
    policy_sha: str,
    workflow_sha: str,
    workflow_ref: str,
    call_inputs: JsonObject,
    fetch_json: FetchJson,
) -> Admission:
    _event_repository(event, repository)
    expected_workflow_ref = (
        f"{repository}/.github/workflows/"
        "review-baseline-gate.yml@refs/heads/main"
    )
    if workflow_ref != expected_workflow_ref:
        raise AdmissionError("executor caller is not the trusted main-branch gate")
    if _full_sha(workflow_sha, "workflow sha") != policy_sha:
        raise AdmissionError("executor workflow does not equal the gate policy")
    if set(call_inputs) != CALL_INPUT_FIELDS or not all(
        isinstance(value, str) for value in call_inputs.values()
    ):
        raise AdmissionError("executor call inputs are not exact strings")
    decision = gate_decision(
        event_name,
        event,
        repository,
        policy_sha,
        fetch_json,
    )
    if not decision.dispatch or call_inputs != decision.inputs:
        raise AdmissionError("executor call differs from the live gate decision")

    mode = call_inputs.get("mode")
    pr_number = _positive_int_text(
        call_inputs.get("pull_request_number"), "call pull-request number"
    )
    if mode == "revoke":
        reason = _text(call_inputs.get("revocation_reason"), "revocation reason")
        return Admission(
            False,
            "TRUSTED_REVOCATION",
            repository,
            pr_number,
            _positive_int_text(
                call_inputs.get("admission_comment_id"),
                "revocation comment id",
            ),
            "",
            "",
            "",
            policy_sha,
            "",
            "REVOKED",
            "",
            "",
            reason,
        )
    if mode != "admit":
        raise AdmissionError("workflow call mode is unsupported")

    comment_id = _positive_int_text(
        call_inputs.get("admission_comment_id"), "call admission-comment id"
    )
    reviewed_head_sha = _full_sha(
        call_inputs.get("reviewed_head_sha"), "call reviewed-head sha"
    )
    base_sha = _full_sha(call_inputs.get("base_sha"), "call base sha")
    execution_merge_sha = _full_sha(
        call_inputs.get("execution_merge_sha"), "call execution-merge sha"
    )
    if _full_sha(call_inputs.get("policy_sha"), "call policy sha") != policy_sha:
        raise AdmissionError("workflow call policy differs from live gate policy")
    body_digest = _sha256(
        call_inputs.get("review_body_sha256"), "call review-body digest"
    )
    metadata_value = call_inputs.get("review_metadata")
    if not isinstance(metadata_value, str):
        raise AdmissionError("call review metadata must be a JSON string")
    try:
        metadata = json.loads(metadata_value)
    except json.JSONDecodeError as exc:
        raise AdmissionError("call review metadata is not valid JSON") from exc
    metadata_object = _object(metadata, "call review metadata")
    if set(metadata_object) != {"association", "state", "updated_at"}:
        raise AdmissionError("call review metadata fields are not exact")
    association = metadata_object.get("association")
    if association not in ALLOWED_ASSOCIATIONS:
        raise AdmissionError("call reviewer lacks repository standing")
    if metadata_object.get("state") != "ACTIVE_UNEDITED":
        raise AdmissionError("call review state is not active and unedited")
    updated_at = _timestamp(metadata_object.get("updated_at"), "call updated_at")
    return Admission(
        True,
        "ISSUE_COMMENT_ADMISSION",
        repository,
        pr_number,
        comment_id,
        reviewed_head_sha,
        base_sha,
        execution_merge_sha,
        policy_sha,
        body_digest,
        "ACTIVE_UNEDITED",
        updated_at,
        cast(str, association),
        decision.reason,
    )


def decide(
    event_name: str,
    event: JsonObject,
    github_sha: str,
    workflow_sha: str,
    workflow_ref: str,
    repository: str,
    policy_sha: str,
    call_inputs: JsonObject | None = None,
    fetch_json: FetchJson | None = None,
) -> Admission:
    """Return a live-reviewed execution coordinate or refuse admission."""

    admitted_policy_sha = _full_sha(policy_sha, "admission policy sha")
    if REPOSITORY.fullmatch(repository) is None:
        raise AdmissionError("repository must be an owner/name coordinate")
    if event_name == "push":
        _event_repository(event, repository)
        if event.get("ref") != "refs/heads/main":
            raise AdmissionError("automatic full baselines are limited to main")
        target_sha = _full_sha(github_sha, "GITHUB_SHA")
        if event.get("after") != target_sha:
            raise AdmissionError("push event target does not equal GITHUB_SHA")
        if _full_sha(workflow_sha, "workflow sha") != target_sha:
            raise AdmissionError("main workflow does not equal the push target")
        if admitted_policy_sha != target_sha:
            raise AdmissionError("main admission policy does not equal the push target")
        expected_workflow_ref = (
            f"{repository}/.github/workflows/conformance.yml@refs/heads/main"
        )
        if workflow_ref != expected_workflow_ref:
            raise AdmissionError("main baseline did not use the main workflow")
        return Admission(
            True,
            "MAIN_PUSH",
            repository,
            None,
            None,
            target_sha,
            "",
            target_sha,
            admitted_policy_sha,
            "",
            "MAIN_PUSH",
            "",
            "",
            "main-branch post-merge baseline",
        )
    if event_name == "issue_comment":
        if fetch_json is None or call_inputs is None:
            raise AdmissionError("live reader and call inputs are required for admission")
        return _workflow_call_admission(
            event_name,
            event,
            repository,
            admitted_policy_sha,
            workflow_sha,
            workflow_ref,
            call_inputs,
            fetch_json,
        )
    raise AdmissionError(f"unsupported baseline event {event_name!r}")


class GitHubReader:
    """Minimal authenticated GitHub API reader with a fixed API version."""

    def __init__(self, api_url: str, token: str) -> None:
        if not api_url.startswith("https://") or not token:
            raise AdmissionError("GitHub API URL and token are required")
        self._api_url = api_url.rstrip("/")
        self._token = token

    def __call__(self, path: str) -> JsonObject:
        data: bytes | None = None
        method = "GET"
        url = f"{self._api_url}{path}"
        graphql = path.startswith(GRAPHQL_COMMENT_PREFIX)
        if graphql:
            node_id = _text(
                path.removeprefix(GRAPHQL_COMMENT_PREFIX),
                "GraphQL comment node id",
            )
            url = f"{self._api_url}/graphql"
            method = "POST"
            data = json.dumps(
                {
                    "query": GRAPHQL_COMMENT_QUERY,
                    "variables": {"id": node_id},
                }
            ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": "ofarm2-review-baseline-admission",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise AdmissionError("live GitHub admission read failed") from exc
        response = _object(payload, "live GitHub response")
        if not graphql:
            return response
        if response.get("errors") is not None:
            raise AdmissionError("live GitHub GraphQL admission read failed")
        graph_data = _object(response.get("data"), "GraphQL response data")
        return _object(graph_data.get("node"), "GraphQL admission comment")


def _write_output(path: Path, values: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as output:
        for key, value in values.items():
            text = str(value)
            if "\n" in text or "\r" in text:
                raise AdmissionError(f"output {key} must be one line")
            output.write(f"{key}={text}\n")


def _write_admission_output(path: Path, admission: Admission) -> None:
    _write_output(
        path,
        {
            "eligible": "true" if admission.eligible else "false",
            "pull_request_number": admission.pull_request_number or "",
            "admission_comment_id": admission.admission_comment_id or "",
            "reviewed_head_sha": admission.reviewed_head_sha,
            "base_sha": admission.base_sha,
            "execution_merge_sha": admission.execution_merge_sha,
            "policy_sha": admission.policy_sha,
            "review_body_sha256": admission.review_body_sha256,
            "review_state": admission.review_state,
            "review_updated_at": admission.review_updated_at,
            "reviewer_association": admission.reviewer_association,
            "reason": admission.reason,
        },
    )


def _write_gate_output(path: Path, decision: GateDecision) -> None:
    call_outputs = {
        field: decision.inputs.get(field, "")
        for field in sorted(CALL_INPUT_FIELDS)
    }
    _write_output(
        path,
        {
            **call_outputs,
            "dispatch": "true" if decision.dispatch else "false",
            "pull_request_number": decision.pull_request_number or "",
            "reason": decision.reason,
        },
    )


def _write_json(path: Path, value: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", choices=("admit", "gate"), required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", type=Path, required=True)
    parser.add_argument("--github-sha", required=True)
    parser.add_argument("--workflow-sha", required=True)
    parser.add_argument("--workflow-ref", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--policy-sha", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path)
    args = parser.parse_args()

    event = json.loads(args.event_path.read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise AdmissionError("GitHub event payload must be an object")
    fetch_json: FetchJson | None = None
    if args.event_name == "issue_comment":
        fetch_json = GitHubReader(
            os.environ.get("GITHUB_API_URL", "https://api.github.com"),
            os.environ.get("OFARM_ADMISSION_TOKEN", ""),
        )

    if args.operation == "gate":
        decision = gate_decision(
            args.event_name,
            cast(JsonObject, event),
            args.repository,
            args.policy_sha,
            fetch_json,
        )
        _write_gate_output(args.github_output, decision)
        print(f"baseline gate: {decision.reason}; policy={args.policy_sha}")
        return 0

    call_inputs: JsonObject | None = None
    if args.event_name == "issue_comment":
        raw_inputs = os.environ.get("OFARM_BASELINE_ADMISSION_INPUTS", "")
        try:
            parsed_inputs = json.loads(raw_inputs)
        except json.JSONDecodeError as exc:
            raise AdmissionError("reusable-workflow inputs are not valid JSON") from exc
        call_inputs = _object(parsed_inputs, "reusable-workflow inputs")
    admission = decide(
        args.event_name,
        cast(JsonObject, event),
        args.github_sha,
        args.workflow_sha,
        args.workflow_ref,
        args.repository,
        args.policy_sha,
        call_inputs,
        fetch_json,
    )
    _write_admission_output(args.github_output, admission)
    if args.evidence_output is not None:
        _write_json(args.evidence_output, admission.evidence())
    print(f"baseline admission: {admission.reason}; policy={admission.policy_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
