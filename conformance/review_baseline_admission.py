#!/usr/bin/env python3
"""Trusted dispatch and live admission for expensive review baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
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
PUBLICATION_TICKET_SCHEMA = "ofarm.review-baseline-publication-ticket.v1"
PUBLICATION_RECEIPT_SCHEMA = "ofarm.evidence-publication-receipt.v1"
GITHUB_API_VERSION = "2026-03-10"
GRAPHQL_COMMENT_PREFIX = "graphql:issue-comment:"
CONFORMANCE_WORKFLOW_PATH = ".github/workflows/conformance.yml"
GATE_WORKFLOW_PATH = ".github/workflows/review-baseline-gate.yml"
PUBLICATION_WORKFLOW_PATH = ".github/workflows/evidence-publication.yml"
PUBLICATION_TICKET_NAME = "evidence-publication-ticket"
PROVISIONAL_ARTIFACT_NAMES = (
    "conformance-provisional",
    "native-verifier-amd64-provisional",
    "native-verifier-arm64-provisional",
)
PUBLICATION_ARTIFACT_NAMES = (
    "review-baseline",
    "platform-mvp-evidence",
    "native-verifier-amd64",
    "native-verifier-arm64",
    "native-verifier-index",
)
SOURCE_ARTIFACT_MAX_BYTES = {
    "conformance-provisional": 512_000_000,
    "native-verifier-amd64-provisional": 1_650_000_000,
    "native-verifier-arm64-provisional": 1_650_000_000,
    PUBLICATION_TICKET_NAME: 1_000_000,
}
SOURCE_WORKFLOW_NAMES = {
    CONFORMANCE_WORKFLOW_PATH: "conformance",
    GATE_WORKFLOW_PATH: "reviewed-head baseline gate",
}
SOURCE_WORKFLOW_EVENTS = {
    CONFORMANCE_WORKFLOW_PATH: frozenset({"push"}),
    GATE_WORKFLOW_PATH: frozenset({"issue_comment", "pull_request_target"}),
}
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
FetchJson = Callable[[str], object]


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


@dataclass(frozen=True)
class ArtifactReference:
    """One immutable artifact bound to one exact source workflow run."""

    name: str
    artifact_id: int
    digest: str
    size: int
    source_run_id: int
    source_head_sha: str

    def evidence(self) -> JsonObject:
        return {
            "artifactId": self.artifact_id,
            "digest": self.digest,
            "name": self.name,
            "size": self.size,
            "sourceHeadSha": self.source_head_sha,
            "sourceRunId": self.source_run_id,
        }


@dataclass(frozen=True)
class PublicationSource:
    """Trusted identity of the completed producer workflow run."""

    repository: str
    run_id: int
    run_attempt: int
    event_name: str
    workflow_name: str
    workflow_path: str
    workflow_ref: str
    workflow_sha: str


@dataclass(frozen=True)
class PublicationPlan:
    """Authenticated decision about whether one source run may publish."""

    publish: bool
    reason: str
    source: PublicationSource
    artifacts: dict[str, ArtifactReference]


def _full_sha(value: object, field: str) -> str:
    if not isinstance(value, str) or FULL_SHA.fullmatch(value) is None:
        raise AdmissionError(f"{field} must be a full lowercase commit SHA")
    return value


def _sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise AdmissionError(f"{field} must be a SHA-256 digest")
    return value


def _normalized_sha256(value: object, field: str) -> str:
    if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
        value = f"sha256:{value}"
    return _sha256(value, field)


def _positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise AdmissionError(f"{field} must be a positive integer")
    return value


def _nonnegative_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise AdmissionError(f"{field} must be a non-negative integer")
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


def _array(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise AdmissionError(f"{field} must be an array")
    return cast(list[object], value)


def _canonical_json_bytes(value: JsonObject) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _workflow_ref(repository: str, workflow_path: str) -> str:
    return f"{repository}/{workflow_path}@refs/heads/main"


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
    live_pr = _object(
        fetch_json(f"/repos/{repository}/pulls/{pr_number}"),
        "live pull request",
    )
    if _positive_int(live_pr.get("number"), "live pull-request number") != pr_number:
        raise AdmissionError("live pull-request identity changed")
    if live_pr.get("state") != "open":
        raise AdmissionError("live pull request is not open")
    return live_pr


def _live_base_sha(
    repository: str,
    live_base: JsonObject,
    fetch_json: FetchJson,
) -> str:
    base_repository = _object(
        live_base.get("repo"), "live pull-request base repository"
    )
    if base_repository.get("full_name") != repository:
        raise AdmissionError("live pull-request base repository changed")
    base_branch = _text(live_base.get("ref"), "live pull-request base ref")
    base_ref_name = f"refs/heads/{base_branch}"
    base_ref_path = urllib.parse.quote(f"heads/{base_branch}", safe="/")
    base_ref = _object(
        fetch_json(f"/repos/{repository}/git/ref/{base_ref_path}"),
        "live pull-request base ref",
    )
    if base_ref.get("ref") != base_ref_name:
        raise AdmissionError("live pull-request base ref identity changed")
    base_object = _object(base_ref.get("object"), "live base ref object")
    if base_object.get("type") != "commit":
        raise AdmissionError("live pull-request base ref must target a commit")
    return _full_sha(base_object.get("sha"), "live pull-request base sha")


def _bound_merge(
    repository: str,
    live_pr: JsonObject,
    reviewed_head_sha: str,
    fetch_json: FetchJson,
) -> tuple[str, str]:
    pr_number = _positive_int(live_pr.get("number"), "live pull-request number")
    live_base = _object(live_pr.get("base"), "live pull-request base")
    base_sha = _live_base_sha(repository, live_base, fetch_json)
    merge_ref_name = f"refs/pull/{pr_number}/merge"
    merge_ref = _object(
        fetch_json(f"/repos/{repository}/git/ref/pull/{pr_number}/merge"),
        "live execution merge ref",
    )
    if merge_ref.get("ref") != merge_ref_name:
        raise AdmissionError("live execution merge ref identity changed")
    merge_object = _object(
        merge_ref.get("object"), "live execution merge ref object"
    )
    if merge_object.get("type") != "commit":
        raise AdmissionError("live execution merge ref must target a commit")
    execution_merge_sha = _full_sha(
        merge_object.get("sha"), "live execution merge sha"
    )
    merge_commit = _object(
        fetch_json(f"/repos/{repository}/git/commits/{execution_merge_sha}"),
        "live execution merge commit",
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
    live_comment = _object(
        fetch_json(f"/repos/{repository}/issues/comments/{comment_id}"),
        "live admission comment",
    )
    if _positive_int(live_comment.get("id"), "live comment id") != comment_id:
        raise AdmissionError("live admission-comment identity changed")
    if not str(live_comment.get("issue_url", "")).endswith(
        f"/repos/{repository}/issues/{pr_number}"
    ):
        raise AdmissionError("live admission comment belongs to another pull request")

    node_id = _text(live_comment.get("node_id"), "live comment node id")
    graph_comment = _object(
        fetch_json(f"{GRAPHQL_COMMENT_PREFIX}{node_id}"),
        "GraphQL admission comment",
    )
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


def _parsed_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise AdmissionError(f"{field} must be an ISO-8601 UTC timestamp") from exc
    if parsed.utcoffset() is None:
        raise AdmissionError(f"{field} must include a UTC offset")
    return parsed


def _ensure_no_live_revocation(
    admission: Admission,
    fetch_json: FetchJson,
) -> None:
    if admission.event_class != "ISSUE_COMMENT_ADMISSION":
        return
    if (
        admission.pull_request_number is None
        or admission.admission_comment_id is None
    ):
        raise AdmissionError("review admission has no live revocation identity")
    admitted_at = _parsed_timestamp(
        admission.review_updated_at,
        "admission update time",
    )
    page = 1
    while page <= 10:
        comments = _array(
            fetch_json(
                f"/repos/{admission.repository}/issues/"
                f"{admission.pull_request_number}/comments"
                f"?per_page=100&page={page}"
            ),
            "live pull-request comments",
        )
        for item in comments:
            comment = _object(item, "live pull-request comment")
            comment_id = _positive_int(comment.get("id"), "live comment id")
            if comment_id == admission.admission_comment_id:
                continue
            if comment.get("author_association") not in ALLOWED_ASSOCIATIONS:
                continue
            created_at = _timestamp(
                comment.get("created_at"),
                "live comment created_at",
            )
            if _parsed_timestamp(created_at, "live comment created_at") < admitted_at:
                continue
            revoked_head = _footer_head(
                comment.get("body"),
                REVOCATION_MARKER,
                "live revocation comment",
            )
            if revoked_head == admission.reviewed_head_sha:
                raise AdmissionError("live standing reviewer revocation is active")
        if len(comments) < 100:
            return
        page += 1
    raise AdmissionError("live revocation scan exceeded its bounded comment set")


def _artifact_references(
    *,
    repository: str,
    source_run_id: int,
    source_head_sha: str,
    expected_names: tuple[str, ...],
    fetch_json: FetchJson,
    allow_empty: bool = False,
) -> dict[str, ArtifactReference]:
    response = _object(
        fetch_json(
            f"/repos/{repository}/actions/runs/{source_run_id}/artifacts"
            "?per_page=100"
        ),
        "source-run artifact response",
    )
    artifacts = _array(response.get("artifacts"), "source-run artifacts")
    total_count = _nonnegative_int(
        response.get("total_count"),
        "source-run artifact count",
    )
    if total_count != len(artifacts) or total_count > 100:
        raise AdmissionError("source-run artifact inventory is incomplete")
    if total_count == 0:
        if allow_empty:
            return {}
        raise AdmissionError("source-run artifact names are not the exact inventory")
    references: dict[str, ArtifactReference] = {}
    artifact_ids: set[int] = set()
    for item in artifacts:
        artifact = _object(item, "source-run artifact")
        name = _text(artifact.get("name"), "source-run artifact name")
        if name not in expected_names or name not in SOURCE_ARTIFACT_MAX_BYTES:
            raise AdmissionError(
                "source-run artifact names are not the exact inventory"
            )
        if name in references:
            raise AdmissionError("source-run artifact name is duplicated")
        workflow_run = _object(
            artifact.get("workflow_run"),
            "source-run artifact workflow identity",
        )
        bound_run_id = _positive_int(
            workflow_run.get("id"),
            "artifact source run id",
        )
        bound_head_sha = _full_sha(
            workflow_run.get("head_sha"),
            "artifact source head sha",
        )
        if bound_run_id != source_run_id or bound_head_sha != source_head_sha:
            raise AdmissionError("artifact belongs to another source workflow run")
        if artifact.get("expired") is not False:
            raise AdmissionError("source-run artifact is expired")
        artifact_id = _positive_int(
            artifact.get("id"),
            "source-run artifact id",
        )
        if artifact_id in artifact_ids:
            raise AdmissionError("source-run artifact id is duplicated")
        artifact_ids.add(artifact_id)
        size = _positive_int(
            artifact.get("size_in_bytes"),
            "source-run artifact size",
        )
        if size > SOURCE_ARTIFACT_MAX_BYTES[name]:
            raise AdmissionError("source-run artifact exceeds its size limit")
        references[name] = ArtifactReference(
            name=name,
            artifact_id=artifact_id,
            digest=_sha256(
                artifact.get("digest"),
                "source-run artifact digest",
            ),
            size=size,
            source_run_id=bound_run_id,
            source_head_sha=bound_head_sha,
        )
    if set(references) != set(expected_names):
        raise AdmissionError("source-run artifact names are not the exact inventory")
    return references


def _publication_source_from_event(
    *,
    event_name: str,
    event: JsonObject,
    github_sha: str,
    workflow_sha: str,
    workflow_ref: str,
    repository: str,
    policy_sha: str,
    fetch_json: FetchJson,
) -> PublicationSource:
    if event_name != "workflow_run":
        raise AdmissionError("publication requires a workflow_run event")
    _event_repository(event, repository)
    if event.get("action") != "completed":
        raise AdmissionError("publication source workflow is not completed")
    trusted_policy_sha = _full_sha(policy_sha, "publication policy sha")
    if (
        _full_sha(github_sha, "publication GITHUB_SHA") != trusted_policy_sha
        or _full_sha(workflow_sha, "publication workflow sha")
        != trusted_policy_sha
    ):
        raise AdmissionError("publication workflow does not equal its policy commit")
    if workflow_ref != _workflow_ref(repository, PUBLICATION_WORKFLOW_PATH):
        raise AdmissionError("publication did not use the trusted main workflow")

    event_run = _object(event.get("workflow_run"), "workflow_run source")
    source_run_id = _positive_int(event_run.get("id"), "source run id")
    live_run = _object(
        fetch_json(f"/repos/{repository}/actions/runs/{source_run_id}"),
        "live source workflow run",
    )
    exact_fields = (
        "id",
        "run_attempt",
        "event",
        "name",
        "path",
        "head_branch",
        "head_sha",
        "status",
        "conclusion",
        "workflow_id",
    )
    for field in exact_fields:
        if live_run.get(field) != event_run.get(field):
            raise AdmissionError(f"live source workflow {field} changed")
    source_path = _text(event_run.get("path"), "source workflow path")
    if source_path not in SOURCE_WORKFLOW_NAMES:
        raise AdmissionError("source workflow path is not an allowed producer")
    source_name = _text(event_run.get("name"), "source workflow name")
    if source_name != SOURCE_WORKFLOW_NAMES[source_path]:
        raise AdmissionError("source workflow name does not match its path")
    source_event = _text(event_run.get("event"), "source workflow event")
    if source_event not in SOURCE_WORKFLOW_EVENTS[source_path]:
        raise AdmissionError("source workflow event does not match its path")
    lifecycle_only = source_event == "pull_request_target"
    if (
        event_run.get("status") != "completed"
        or event_run.get("conclusion") != "success"
        or (
            not lifecycle_only
            and event_run.get("head_branch") != "main"
        )
        or (
            lifecycle_only
            and (
                not isinstance(event_run.get("head_branch"), str)
                or not event_run.get("head_branch")
            )
        )
    ):
        raise AdmissionError("source workflow run is not a successful trusted run")
    source_sha = _full_sha(event_run.get("head_sha"), "source workflow sha")
    if not lifecycle_only and source_sha != trusted_policy_sha:
        raise AdmissionError("source and publisher policy commits differ")
    source_run_attempt = _positive_int(
        event_run.get("run_attempt"),
        "source run attempt",
    )
    if source_run_attempt != 1:
        raise AdmissionError("source workflow rerun attempts are ambiguous")
    source_repository = _object(
        event_run.get("repository"),
        "source workflow repository",
    )
    head_repository = _object(
        event_run.get("head_repository"),
        "source workflow head repository",
    )
    if (
        source_repository.get("full_name") != repository
        or head_repository.get("full_name") != repository
    ):
        raise AdmissionError("source workflow belongs to another repository")
    return PublicationSource(
        repository=repository,
        run_id=source_run_id,
        run_attempt=source_run_attempt,
        event_name=source_event,
        workflow_name=source_name,
        workflow_path=source_path,
        workflow_ref=_workflow_ref(repository, source_path),
        workflow_sha=source_sha,
    )


def _publication_plan(
    *,
    event_name: str,
    event: JsonObject,
    github_sha: str,
    workflow_sha: str,
    workflow_ref: str,
    repository: str,
    policy_sha: str,
    fetch_json: FetchJson,
) -> PublicationPlan:
    """Classify authenticated completed runs without making absence an error."""

    source = _publication_source_from_event(
        event_name=event_name,
        event=event,
        github_sha=github_sha,
        workflow_sha=workflow_sha,
        workflow_ref=workflow_ref,
        repository=repository,
        policy_sha=policy_sha,
        fetch_json=fetch_json,
    )
    gate_source = source.workflow_path == GATE_WORKFLOW_PATH
    artifacts = _artifact_references(
        repository=repository,
        source_run_id=source.run_id,
        source_head_sha=source.workflow_sha,
        expected_names=(*PROVISIONAL_ARTIFACT_NAMES, PUBLICATION_TICKET_NAME),
        fetch_json=fetch_json,
        allow_empty=gate_source,
    )
    if source.event_name == "pull_request_target":
        if artifacts:
            raise AdmissionError(
                "pull-request lifecycle gate run unexpectedly produced artifacts"
            )
        return PublicationPlan(
            publish=False,
            reason="pull-request lifecycle gate produced no publication",
            source=source,
            artifacts={},
        )
    if gate_source and not artifacts:
        return PublicationPlan(
            publish=False,
            reason="gate comment produced no publication",
            source=source,
            artifacts={},
        )
    return PublicationPlan(
        publish=True,
        reason="exact publication inventory authenticated",
        source=source,
        artifacts=artifacts,
    )


def _publication_ticket_document(
    *,
    admission: Admission,
    source_run_id: int,
    source_run_attempt: int,
    source_workflow_ref: str,
    source_workflow_sha: str,
    provisional_artifacts: dict[str, ArtifactReference],
) -> JsonObject:
    expected_path = (
        CONFORMANCE_WORKFLOW_PATH
        if admission.event_class == "MAIN_PUSH"
        else GATE_WORKFLOW_PATH
    )
    if source_workflow_ref != _workflow_ref(admission.repository, expected_path):
        raise AdmissionError("publication handoff came from the wrong workflow")
    if _full_sha(source_workflow_sha, "source workflow sha") != admission.policy_sha:
        raise AdmissionError("publication handoff policy differs from admission")
    if set(provisional_artifacts) != set(PROVISIONAL_ARTIFACT_NAMES):
        raise AdmissionError("publication handoff artifact inventory is not exact")
    bound_source_run_attempt = _positive_int(
        source_run_attempt,
        "source run attempt",
    )
    if bound_source_run_attempt != 1:
        raise AdmissionError("source workflow rerun attempts are ambiguous")
    return {
        "admission": admission.evidence(),
        "provisionalArtifacts": [
            provisional_artifacts[name].evidence()
            for name in PROVISIONAL_ARTIFACT_NAMES
        ],
        "repository": admission.repository,
        "schemaVersion": PUBLICATION_TICKET_SCHEMA,
        "source": {
            "runAttempt": bound_source_run_attempt,
            "runId": _positive_int(source_run_id, "source run id"),
            "workflowRef": source_workflow_ref,
            "workflowSha": source_workflow_sha,
        },
    }


def _load_publication_ticket(path: Path) -> JsonObject:
    try:
        data = path.read_bytes()
        document = json.loads(data)
    except (OSError, json.JSONDecodeError) as exc:
        raise AdmissionError("publication ticket is not readable JSON") from exc
    ticket = _object(document, "publication ticket")
    if _canonical_json_bytes(ticket) != data:
        raise AdmissionError("publication ticket is not canonical JSON")
    if set(ticket) != {
        "admission",
        "provisionalArtifacts",
        "repository",
        "schemaVersion",
        "source",
    }:
        raise AdmissionError("publication ticket fields are not exact")
    if ticket.get("schemaVersion") != PUBLICATION_TICKET_SCHEMA:
        raise AdmissionError("publication ticket schema is not exact")
    return ticket


def _validate_publication_ticket(
    *,
    ticket: JsonObject,
    source: PublicationSource,
    artifacts: dict[str, ArtifactReference],
    fetch_json: FetchJson,
) -> Admission:
    if ticket.get("repository") != source.repository:
        raise AdmissionError("publication ticket repository differs")
    expected_source = {
        "runAttempt": source.run_attempt,
        "runId": source.run_id,
        "workflowRef": source.workflow_ref,
        "workflowSha": source.workflow_sha,
    }
    if ticket.get("source") != expected_source:
        raise AdmissionError("publication ticket source identity differs")
    expected_artifacts = [
        artifacts[name].evidence() for name in PROVISIONAL_ARTIFACT_NAMES
    ]
    if ticket.get("provisionalArtifacts") != expected_artifacts:
        raise AdmissionError("publication ticket artifact identities differ")
    admission_evidence = _object(ticket.get("admission"), "ticket admission")
    if admission_evidence.get("schemaVersion") != EVIDENCE_SCHEMA:
        raise AdmissionError("ticket admission schema is not exact")
    if source.event_name == "push":
        live_admission = Admission(
            True,
            "MAIN_PUSH",
            source.repository,
            None,
            None,
            source.workflow_sha,
            "",
            source.workflow_sha,
            source.workflow_sha,
            "",
            "MAIN_PUSH",
            "",
            "",
            "main-branch post-merge baseline",
        )
    else:
        pr_number = _positive_int(
            admission_evidence.get("pull_request_number"),
            "ticket pull-request number",
        )
        comment_id = _positive_int(
            admission_evidence.get("admission_comment_id"),
            "ticket admission-comment id",
        )
        live_admission = _comment_admission(
            repository=source.repository,
            pr_number=pr_number,
            comment_id=comment_id,
            policy_sha=source.workflow_sha,
            fetch_json=fetch_json,
        )
        _ensure_no_live_revocation(live_admission, fetch_json)
    if admission_evidence != live_admission.evidence():
        raise AdmissionError("publication ticket differs from live admission")
    return live_admission


def _publication_receipt_document(
    *,
    path: Path,
    ticket: JsonObject,
    admission: Admission,
    source: PublicationSource,
    source_artifacts: dict[str, ArtifactReference],
    publisher_workflow_ref: str,
    publisher_workflow_sha: str,
    publisher_run_id: int,
    publisher_run_attempt: int,
    fetch_json: FetchJson,
) -> JsonObject:
    if set(source_artifacts) != {
        *PROVISIONAL_ARTIFACT_NAMES,
        PUBLICATION_TICKET_NAME,
    }:
        raise AdmissionError("publication receipt source inventory is not exact")
    expected_publisher_ref = _workflow_ref(
        source.repository,
        PUBLICATION_WORKFLOW_PATH,
    )
    if publisher_workflow_ref != expected_publisher_ref:
        raise AdmissionError("publication receipt workflow ref is not trusted")
    publisher_sha = _full_sha(
        publisher_workflow_sha,
        "publisher workflow sha",
    )
    if publisher_sha != source.workflow_sha:
        raise AdmissionError("publisher and source policy commits differ")
    bound_publisher_run_id = _positive_int(
        publisher_run_id,
        "publisher run id",
    )
    bound_publisher_run_attempt = _positive_int(
        publisher_run_attempt,
        "publisher run attempt",
    )
    if bound_publisher_run_attempt != 1:
        raise AdmissionError("publisher workflow rerun attempts are ambiguous")
    publisher_run = _object(
        fetch_json(
            f"/repos/{source.repository}/actions/runs/{bound_publisher_run_id}"
        ),
        "live publisher workflow run",
    )
    publisher_repository = _object(
        publisher_run.get("repository"),
        "publisher workflow repository",
    )
    publisher_head_repository = _object(
        publisher_run.get("head_repository"),
        "publisher workflow head repository",
    )
    if (
        _positive_int(publisher_run.get("id"), "live publisher run id")
        != bound_publisher_run_id
        or _positive_int(
            publisher_run.get("run_attempt"),
            "live publisher run attempt",
        )
        != bound_publisher_run_attempt
        or publisher_run.get("event") != "workflow_run"
        or publisher_run.get("name") != "evidence-publication"
        or publisher_run.get("path") != PUBLICATION_WORKFLOW_PATH
        or publisher_run.get("head_branch") != "main"
        or _full_sha(
            publisher_run.get("head_sha"),
            "live publisher workflow sha",
        )
        != publisher_sha
        or publisher_run.get("status") != "in_progress"
        or publisher_run.get("conclusion") is not None
        or publisher_repository.get("full_name") != source.repository
        or publisher_head_repository.get("full_name") != source.repository
    ):
        raise AdmissionError("live publisher workflow identity differs")
    _positive_int(
        publisher_run.get("workflow_id"),
        "live publisher workflow id",
    )
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdmissionError("published artifact candidate is not readable JSON") from exc
    items = _array(candidate, "published artifact candidate")
    if len(items) != len(PUBLICATION_ARTIFACT_NAMES):
        raise AdmissionError("published artifact candidate count is not exact")
    observed: dict[str, JsonObject] = {}
    for item in items:
        proposed = _object(item, "published artifact candidate item")
        if set(proposed) != {"artifactId", "digest", "name"}:
            raise AdmissionError("published artifact candidate fields are not exact")
        name = _text(proposed.get("name"), "published artifact name")
        if name in observed:
            raise AdmissionError("published artifact name is duplicated")
        artifact_id_value = proposed.get("artifactId")
        artifact_id = (
            _positive_int_text(artifact_id_value, "published artifact id")
            if isinstance(artifact_id_value, str)
            else _positive_int(artifact_id_value, "published artifact id")
        )
        proposed_digest = _normalized_sha256(
            proposed.get("digest"),
            "published artifact digest",
        )
        live = _object(
            fetch_json(
                f"/repos/{source.repository}/actions/artifacts/{artifact_id}"
            ),
            "live published artifact",
        )
        live_workflow = _object(
            live.get("workflow_run"),
            "live published artifact workflow",
        )
        if (
            _positive_int(live.get("id"), "live published artifact id")
            != artifact_id
            or live.get("name") != name
            or _sha256(live.get("digest"), "live published artifact digest")
            != proposed_digest
            or live.get("expired") is not False
            or _positive_int(
                live_workflow.get("id"),
                "live publisher run id",
            )
            != bound_publisher_run_id
            or _full_sha(
                live_workflow.get("head_sha"),
                "live publisher workflow sha",
            )
            != publisher_sha
        ):
            raise AdmissionError("published artifact live identity differs")
        observed[name] = {
            "artifactId": artifact_id,
            "digest": proposed_digest,
            "name": name,
            "publisherRunId": bound_publisher_run_id,
            "size": _positive_int(
                live.get("size_in_bytes"),
                "live published artifact size",
            ),
        }
    if set(observed) != set(PUBLICATION_ARTIFACT_NAMES):
        raise AdmissionError("published artifact names are not exact")
    return {
        "admission": admission.evidence(),
        "artifacts": [observed[name] for name in PUBLICATION_ARTIFACT_NAMES],
        "publisher": {
            "runAttempt": bound_publisher_run_attempt,
            "runId": bound_publisher_run_id,
            "workflowRef": publisher_workflow_ref,
            "workflowSha": publisher_sha,
        },
        "repository": source.repository,
        "schemaVersion": PUBLICATION_RECEIPT_SCHEMA,
        "source": {
            **_object(ticket.get("source"), "publication ticket source"),
            "artifacts": [
                source_artifacts[name].evidence()
                for name in (*PROVISIONAL_ARTIFACT_NAMES, PUBLICATION_TICKET_NAME)
            ],
        },
    }


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

    def __call__(self, path: str) -> object:
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
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise AdmissionError("live GitHub admission read failed") from exc
        if not graphql:
            return payload
        response = _object(payload, "live GitHub response")
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


def _write_publication_output(
    path: Path,
    *,
    source: PublicationSource | None,
    artifacts: dict[str, ArtifactReference],
    admission: Admission | None = None,
    publish: bool = True,
    reason: str = "",
) -> None:
    aliases = {
        "conformance-provisional": "conformance",
        "native-verifier-amd64-provisional": "native_amd64",
        "native-verifier-arm64-provisional": "native_arm64",
        PUBLICATION_TICKET_NAME: "ticket",
    }
    values: dict[str, object] = {
        "publish": "true" if publish else "false",
        "publication_reason": reason,
    }
    for name, artifact in artifacts.items():
        alias = aliases[name]
        values[f"{alias}_artifact_id"] = artifact.artifact_id
        values[f"{alias}_artifact_digest"] = artifact.digest
        values[f"{alias}_artifact_size"] = artifact.size
    if source is not None:
        values.update(
            {
                "source_event_name": source.event_name,
                "source_run_attempt": source.run_attempt,
                "source_run_id": source.run_id,
                "source_workflow_ref": source.workflow_ref,
                "source_workflow_sha": source.workflow_sha,
            }
        )
    if admission is not None:
        values["publication_concurrency_group"] = (
            f"ofarm-pr-{admission.pull_request_number}"
            if admission.pull_request_number is not None
            else f"ofarm-main-publication-{source.run_id if source else 'unknown'}"
        )
        values["pull_request_number"] = admission.pull_request_number or ""
    _write_output(path, values)


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


def _write_canonical_json(path: Path, value: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json_bytes(value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--operation",
        choices=("admit", "gate", "handoff", "resolve", "publish"),
        required=True,
    )
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", type=Path, required=True)
    parser.add_argument("--github-sha", required=True)
    parser.add_argument("--workflow-sha", required=True)
    parser.add_argument("--workflow-ref", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--policy-sha", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path)
    parser.add_argument("--source-run-id", type=int)
    parser.add_argument("--source-run-attempt", type=int)
    parser.add_argument("--ticket-output", type=Path)
    parser.add_argument("--ticket", type=Path)
    parser.add_argument("--published-artifacts-input", type=Path)
    parser.add_argument("--publication-receipt-output", type=Path)
    parser.add_argument("--publisher-run-id", type=int)
    parser.add_argument("--publisher-run-attempt", type=int)
    args = parser.parse_args()

    event = json.loads(args.event_path.read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise AdmissionError("GitHub event payload must be an object")
    fetch_json: FetchJson | None = None
    if args.event_name == "issue_comment" or args.operation in {
        "handoff",
        "resolve",
        "publish",
    }:
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

    if args.operation in {"resolve", "publish"}:
        if fetch_json is None:
            raise AdmissionError("publication requires a live GitHub reader")
        plan = _publication_plan(
            event_name=args.event_name,
            event=cast(JsonObject, event),
            github_sha=args.github_sha,
            workflow_sha=args.workflow_sha,
            workflow_ref=args.workflow_ref,
            repository=args.repository,
            policy_sha=args.policy_sha,
            fetch_json=fetch_json,
        )
        source = plan.source
        artifacts = plan.artifacts
        if args.operation == "resolve":
            _write_publication_output(
                args.github_output,
                source=source,
                artifacts=artifacts,
                publish=plan.publish,
                reason=plan.reason,
            )
            print(
                "publication source resolved: "
                f"publish={str(plan.publish).lower()}; run={source.run_id}; "
                f"policy={source.workflow_sha}; reason={plan.reason}"
            )
            return 0
        if not plan.publish:
            raise AdmissionError("non-publication source cannot enter publication")
        if args.ticket is None:
            raise AdmissionError("publication validation requires a ticket")
        ticket = _load_publication_ticket(args.ticket)
        admission = _validate_publication_ticket(
            ticket=ticket,
            source=source,
            artifacts=artifacts,
            fetch_json=fetch_json,
        )
        _write_admission_output(args.github_output, admission)
        _write_publication_output(
            args.github_output,
            source=source,
            artifacts=artifacts,
            admission=admission,
            publish=True,
            reason=plan.reason,
        )
        if args.evidence_output is not None:
            _write_json(args.evidence_output, admission.evidence())
        receipt_arguments = (
            args.published_artifacts_input,
            args.publication_receipt_output,
            args.publisher_run_id,
            args.publisher_run_attempt,
        )
        if any(value is not None for value in receipt_arguments):
            if not all(value is not None for value in receipt_arguments):
                raise AdmissionError("publication receipt coordinates are incomplete")
            receipt = _publication_receipt_document(
                path=cast(Path, args.published_artifacts_input),
                ticket=ticket,
                admission=admission,
                source=source,
                source_artifacts=artifacts,
                publisher_workflow_ref=args.workflow_ref,
                publisher_workflow_sha=args.workflow_sha,
                publisher_run_id=cast(int, args.publisher_run_id),
                publisher_run_attempt=cast(int, args.publisher_run_attempt),
                fetch_json=fetch_json,
            )
            _write_canonical_json(
                cast(Path, args.publication_receipt_output),
                receipt,
            )
        print(
            "publication admission: "
            f"{admission.reason}; source-run={source.run_id}"
        )
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
    if args.operation == "handoff":
        if fetch_json is None:
            raise AdmissionError("publication handoff requires a live GitHub reader")
        if (
            args.source_run_id is None
            or args.source_run_attempt is None
            or args.ticket_output is None
        ):
            raise AdmissionError("publication handoff coordinates are required")
        if admission.event_class == "ISSUE_COMMENT_ADMISSION":
            _ensure_no_live_revocation(admission, fetch_json)
        source_path = (
            CONFORMANCE_WORKFLOW_PATH
            if args.event_name == "push"
            else GATE_WORKFLOW_PATH
        )
        source = PublicationSource(
            repository=args.repository,
            run_id=_positive_int(args.source_run_id, "source run id"),
            run_attempt=_positive_int(
                args.source_run_attempt,
                "source run attempt",
            ),
            event_name=args.event_name,
            workflow_name=SOURCE_WORKFLOW_NAMES[source_path],
            workflow_path=source_path,
            workflow_ref=args.workflow_ref,
            workflow_sha=args.workflow_sha,
        )
        artifacts = _artifact_references(
            repository=args.repository,
            source_run_id=source.run_id,
            source_head_sha=source.workflow_sha,
            expected_names=PROVISIONAL_ARTIFACT_NAMES,
            fetch_json=fetch_json,
        )
        ticket = _publication_ticket_document(
            admission=admission,
            source_run_id=source.run_id,
            source_run_attempt=source.run_attempt,
            source_workflow_ref=source.workflow_ref,
            source_workflow_sha=source.workflow_sha,
            provisional_artifacts=artifacts,
        )
        _write_canonical_json(args.ticket_output, ticket)
        _write_publication_output(
            args.github_output,
            source=source,
            artifacts=artifacts,
            admission=admission,
        )
        print(
            "publication handoff: exact provisional inventory; "
            f"source-run={source.run_id}"
        )
        return 0
    _write_admission_output(args.github_output, admission)
    if args.evidence_output is not None:
        _write_json(args.evidence_output, admission.evidence())
    print(f"baseline admission: {admission.reason}; policy={admission.policy_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
