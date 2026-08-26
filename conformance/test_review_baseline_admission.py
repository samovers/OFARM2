#!/usr/bin/env python3
"""Zero-dependency tests for trusted expensive-baseline admission."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from conformance.review_baseline_admission import (
    ADMISSION_MARKER,
    EVIDENCE_SCHEMA,
    GRAPHQL_COMMENT_PREFIX,
    GATE_WORKFLOW_PATH,
    PROVISIONAL_ARTIFACT_NAMES,
    PUBLICATION_ARTIFACT_NAMES,
    PUBLICATION_RECEIPT_SCHEMA,
    PUBLICATION_TICKET_NAME,
    PUBLICATION_WORKFLOW_PATH,
    REVOCATION_MARKER,
    ArtifactReference,
    AdmissionError,
    _artifact_references,
    _publication_receipt_document,
    _publication_source_from_event,
    _publication_ticket_document,
    _validate_publication_ticket,
    decide,
    gate_decision,
)


HEAD_SHA = "a" * 40
NEXT_SHA = "b" * 40
BASE_SHA = "c" * 40
MERGE_SHA = "d" * 40
POLICY_SHA = "e" * 40
REPOSITORY = "samovers/OFARM2"
PR_NUMBER = 336
COMMENT_ID = 12345
COMMENT_NODE_ID = "IC_kwDOExample"
CREATED_AT = "2026-08-26T08:00:00Z"
REVOCATION_AT = "2026-08-26T09:00:00Z"
SOURCE_RUN_ID = 987654321
SOURCE_RUN_ATTEMPT = 1
PUBLISHER_RUN_ID = 123456789
PUBLISHER_RUN_ATTEMPT = 1
GATE_WORKFLOW_REF = (
    f"{REPOSITORY}/.github/workflows/review-baseline-gate.yml@refs/heads/main"
)
CONFORMANCE_WORKFLOW_REF = (
    f"{REPOSITORY}/.github/workflows/conformance.yml@refs/heads/main"
)
PUBLICATION_WORKFLOW_REF = (
    f"{REPOSITORY}/{PUBLICATION_WORKFLOW_PATH}@refs/heads/main"
)


def workflow_job_section(workflow: str, job_name: str) -> str:
    marker = f"\n  {job_name}:\n"
    if marker not in workflow:
        raise AssertionError(f"workflow job is missing: {job_name}")
    section = workflow.split(marker, 1)[1]
    next_job = re.search(r"\n  [a-zA-Z0-9_-]+:\n", section)
    return section if next_job is None else section[: next_job.start()]


def admission_body(head_sha: str = HEAD_SHA) -> str:
    return (
        "Exact-head review complete.\n\n"
        f"{ADMISSION_MARKER}\n"
        f"head={head_sha}\n"
        "blockers=0\n"
    )


def revocation_body(head_sha: str = HEAD_SHA) -> str:
    return f"Admission withdrawn.\n\n{REVOCATION_MARKER}\nhead={head_sha}\n"


def issue_comment_event(
    *,
    action: str = "created",
    body: str | None = None,
    association: str = "OWNER",
    prior_body: str | None = None,
    pull_request: bool = True,
) -> dict[str, object]:
    event: dict[str, object] = {
        "action": action,
        "repository": {"full_name": REPOSITORY},
        "issue": {
            "number": PR_NUMBER,
            **({"pull_request": {"url": "unused"}} if pull_request else {}),
        },
        "comment": {
            "id": COMMENT_ID,
            "body": admission_body() if body is None else body,
            "author_association": association,
        },
    }
    if prior_body is not None:
        event["changes"] = {"body": {"from": prior_body}}
    return event


def pull_request_target_event(action: str = "synchronize") -> dict[str, object]:
    return {
        "action": action,
        "repository": {"full_name": REPOSITORY},
        "pull_request": {"number": PR_NUMBER},
    }


def live_reader(
    *,
    body: str | None = None,
    head_sha: str = HEAD_SHA,
    base_sha: str = BASE_SHA,
    merge_sha: object = MERGE_SHA,
    merge_parents: list[str] | None = None,
    association: str = "OWNER",
    created_at: str = CREATED_AT,
    updated_at: str = CREATED_AT,
    last_edited_at: str | None = None,
    minimized: bool = False,
):
    comment_body = admission_body() if body is None else body
    parent_shas = merge_parents or [base_sha, head_sha]
    responses = {
        f"/repos/{REPOSITORY}/pulls/{PR_NUMBER}": {
            "number": PR_NUMBER,
            "state": "open",
            "head": {"sha": head_sha},
            "base": {"sha": base_sha},
            "merge_commit_sha": merge_sha,
        },
        f"/repos/{REPOSITORY}/issues/comments/{COMMENT_ID}": {
            "id": COMMENT_ID,
            "node_id": COMMENT_NODE_ID,
            "issue_url": (
                f"https://api.github.com/repos/{REPOSITORY}/issues/{PR_NUMBER}"
            ),
            "body": comment_body,
            "author_association": association,
            "created_at": created_at,
            "updated_at": updated_at,
        },
        f"{GRAPHQL_COMMENT_PREFIX}{COMMENT_NODE_ID}": {
            "databaseId": COMMENT_ID,
            "body": comment_body,
            "authorAssociation": association,
            "createdAt": created_at,
            "updatedAt": updated_at,
            "lastEditedAt": last_edited_at,
            "isMinimized": minimized,
            "issue": {
                "number": PR_NUMBER,
                "repository": {"nameWithOwner": REPOSITORY},
            },
        },
        f"/repos/{REPOSITORY}/git/commits/{MERGE_SHA}": {
            "sha": MERGE_SHA,
            "parents": [{"sha": value} for value in parent_shas],
        },
    }
    return responses.__getitem__


def source_run() -> dict[str, object]:
    return {
        "id": SOURCE_RUN_ID,
        "run_attempt": SOURCE_RUN_ATTEMPT,
        "event": "issue_comment",
        "name": "reviewed-head baseline gate",
        "path": GATE_WORKFLOW_PATH,
        "head_branch": "main",
        "head_sha": POLICY_SHA,
        "status": "completed",
        "conclusion": "success",
        "workflow_id": 123456,
        "repository": {"full_name": REPOSITORY},
        "head_repository": {"full_name": REPOSITORY},
    }


def workflow_run_event() -> dict[str, object]:
    return {
        "action": "completed",
        "repository": {"full_name": REPOSITORY},
        "workflow_run": source_run(),
    }


def artifact_document(
    name: str,
    artifact_id: int,
    digest_character: str,
) -> dict[str, object]:
    return {
        "id": artifact_id,
        "name": name,
        "size_in_bytes": 1000 + artifact_id,
        "expired": False,
        "digest": "sha256:" + digest_character * 64,
        "workflow_run": {"id": SOURCE_RUN_ID, "head_sha": POLICY_SHA},
    }


def published_artifact_document(
    name: str,
    artifact_id: int,
    digest_character: str,
    *,
    publisher_run_id: int = PUBLISHER_RUN_ID,
) -> dict[str, object]:
    return {
        "id": artifact_id,
        "name": name,
        "size_in_bytes": 2000 + artifact_id,
        "expired": False,
        "digest": "sha256:" + digest_character * 64,
        "workflow_run": {
            "id": publisher_run_id,
            "head_sha": POLICY_SHA,
        },
    }


def publisher_run() -> dict[str, object]:
    return {
        "id": PUBLISHER_RUN_ID,
        "run_attempt": PUBLISHER_RUN_ATTEMPT,
        "event": "workflow_run",
        "name": "evidence-publication",
        "path": PUBLICATION_WORKFLOW_PATH,
        "head_branch": "main",
        "head_sha": POLICY_SHA,
        "status": "in_progress",
        "conclusion": None,
        "workflow_id": 654321,
        "repository": {"full_name": REPOSITORY},
        "head_repository": {"full_name": REPOSITORY},
    }


def source_artifact_documents(
    *,
    extra_name: str | None = None,
) -> list[dict[str, object]]:
    names = [*PROVISIONAL_ARTIFACT_NAMES, PUBLICATION_TICKET_NAME]
    if extra_name is not None:
        names.append(extra_name)
    return [
        artifact_document(name, index + 1, format(index + 1, "x"))
        for index, name in enumerate(names)
    ]


def publication_reader(
    *,
    artifacts: list[dict[str, object]] | None = None,
    revocation: bool = False,
    live_run_mutation: tuple[str, object] | None = None,
):
    base_reader = live_reader()
    run = source_run()
    if live_run_mutation is not None:
        run[live_run_mutation[0]] = live_run_mutation[1]
    source_artifacts = (
        source_artifact_documents() if artifacts is None else artifacts
    )
    comments: list[dict[str, object]] = []
    if revocation:
        comments.append(
            {
                "id": COMMENT_ID + 1,
                "body": revocation_body(),
                "author_association": "OWNER",
                "created_at": REVOCATION_AT,
            }
        )
    responses: dict[str, object] = {
        f"/repos/{REPOSITORY}/actions/runs/{SOURCE_RUN_ID}": run,
        (
            f"/repos/{REPOSITORY}/actions/runs/{SOURCE_RUN_ID}/artifacts"
            "?per_page=100"
        ): {
            "total_count": len(source_artifacts),
            "artifacts": source_artifacts,
        },
        (
            f"/repos/{REPOSITORY}/issues/{PR_NUMBER}/comments"
            "?per_page=100&page=1"
        ): comments,
    }

    def read(path: str):
        if path in responses:
            return responses[path]
        return base_reader(path)

    return read


def publication_receipt_reader(
    *,
    publisher_run_mutation: tuple[str, object] | None = None,
    artifact_run_id: int = PUBLISHER_RUN_ID,
):
    base_reader = publication_reader()
    live_publisher_run = publisher_run()
    if publisher_run_mutation is not None:
        live_publisher_run[publisher_run_mutation[0]] = publisher_run_mutation[1]
    documents = [
        published_artifact_document(
            name,
            101 + index,
            format(10 + index, "x"),
            publisher_run_id=artifact_run_id,
        )
        for index, name in enumerate(PUBLICATION_ARTIFACT_NAMES)
    ]
    responses: dict[str, object] = {
        f"/repos/{REPOSITORY}/actions/runs/{PUBLISHER_RUN_ID}": (
            live_publisher_run
        ),
        **{
            f"/repos/{REPOSITORY}/actions/artifacts/{document['id']}": document
            for document in documents
        },
    }

    def read(path: str):
        if path in responses:
            return responses[path]
        return base_reader(path)

    return read, documents


def admitted_gate(**reader_options: object):
    return gate_decision(
        "issue_comment",
        issue_comment_event(),
        REPOSITORY,
        POLICY_SHA,
        live_reader(**reader_options),
    )


def decide_call(
    inputs: dict[str, str],
    reader=None,
    workflow_sha=POLICY_SHA,
    workflow_ref=GATE_WORKFLOW_REF,
    event_payload=None,
):
    return decide(
        "issue_comment",
        issue_comment_event() if event_payload is None else event_payload,
        POLICY_SHA,
        workflow_sha,
        workflow_ref,
        REPOSITORY,
        POLICY_SHA,
        inputs,
        live_reader() if reader is None else reader,
    )


class GateDecisionTests(unittest.TestCase):
    def test_created_standing_admission_dispatches_exact_coordinates(self) -> None:
        decision = admitted_gate()
        self.assertTrue(decision.dispatch)
        self.assertEqual(decision.mode, "admit")
        self.assertEqual(decision.pull_request_number, PR_NUMBER)
        self.assertEqual(decision.admission_comment_id, COMMENT_ID)
        self.assertEqual(decision.inputs["reviewed_head_sha"], HEAD_SHA)
        self.assertEqual(decision.inputs["base_sha"], BASE_SHA)
        self.assertEqual(decision.inputs["execution_merge_sha"], MERGE_SHA)
        self.assertEqual(decision.inputs["policy_sha"], POLICY_SHA)

    def test_public_commenter_cannot_enter_shared_dispatch(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(association="CONTRIBUTOR"),
            REPOSITORY,
            POLICY_SHA,
            lambda _: self.fail("public comments must not cause live reads"),
        )
        self.assertFalse(decision.dispatch)
        self.assertEqual(decision.mode, "ignore")

    def test_ordinary_standing_comment_is_ignored(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(body="Looks good, but this is not admission."),
            REPOSITORY,
            POLICY_SHA,
        )
        self.assertFalse(decision.dispatch)

    def test_created_explicit_revocation_dispatches_revocation(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(body=revocation_body()),
            REPOSITORY,
            POLICY_SHA,
            live_reader(),
        )
        self.assertTrue(decision.dispatch)
        self.assertEqual(decision.mode, "revoke")
        self.assertEqual(
            decision.inputs["revocation_reason"],
            "explicit-standing-reviewer-revocation",
        )

    def test_edit_of_admission_is_revocation_only(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(
                action="edited",
                body="Admission text changed.",
                prior_body=admission_body(),
            ),
            REPOSITORY,
            POLICY_SHA,
            live_reader(),
        )
        self.assertTrue(decision.dispatch)
        self.assertEqual(decision.mode, "revoke")
        self.assertEqual(
            decision.inputs["revocation_reason"], "admission-comment-edited"
        )

    def test_deletion_of_admission_is_revocation_only(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(action="deleted", body=admission_body()),
            REPOSITORY,
            POLICY_SHA,
            live_reader(),
        )
        self.assertTrue(decision.dispatch)
        self.assertEqual(decision.mode, "revoke")

    def test_ordinary_edit_is_ignored(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(
                action="edited",
                body="New ordinary text.",
                prior_body="Old ordinary text.",
            ),
            REPOSITORY,
            POLICY_SHA,
            live_reader(),
        )
        self.assertFalse(decision.dispatch)

    def test_old_head_admission_edit_cannot_cancel_newer_work(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(
                action="edited",
                body="Admission text changed.",
                prior_body=admission_body(),
            ),
            REPOSITORY,
            POLICY_SHA,
            live_reader(head_sha=NEXT_SHA),
        )
        self.assertFalse(decision.dispatch)
        self.assertIn("older head", decision.reason)

    def test_pull_request_state_transition_uses_revocation_concurrency(self) -> None:
        decision = gate_decision(
            "pull_request_target",
            pull_request_target_event(),
            REPOSITORY,
            POLICY_SHA,
        )
        self.assertFalse(decision.dispatch)
        self.assertEqual(decision.mode, "state-revocation")
        self.assertEqual(decision.pull_request_number, PR_NUMBER)

    def test_non_pull_request_issue_comment_is_ignored(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(pull_request=False),
            REPOSITORY,
            POLICY_SHA,
        )
        self.assertFalse(decision.dispatch)


class ExecutorAdmissionTests(unittest.TestCase):
    def test_main_push_is_bound_to_workflow_and_policy_sha(self) -> None:
        event = {
            "ref": "refs/heads/main",
            "after": HEAD_SHA,
            "repository": {"full_name": REPOSITORY},
        }
        admission = decide(
            "push",
            event,
            HEAD_SHA,
            HEAD_SHA,
            CONFORMANCE_WORKFLOW_REF,
            REPOSITORY,
            HEAD_SHA,
        )
        self.assertTrue(admission.eligible)
        self.assertEqual(admission.event_class, "MAIN_PUSH")
        self.assertEqual(admission.execution_merge_sha, HEAD_SHA)

    def test_dispatch_revalidates_live_admission(self) -> None:
        admission = decide_call(admitted_gate().inputs)
        self.assertTrue(admission.eligible)
        self.assertEqual(admission.pull_request_number, PR_NUMBER)
        self.assertEqual(admission.admission_comment_id, COMMENT_ID)
        self.assertEqual(admission.reviewed_head_sha, HEAD_SHA)
        self.assertEqual(admission.execution_merge_sha, MERGE_SHA)

    def test_evidence_binds_body_digest_state_and_update_time(self) -> None:
        evidence = decide_call(admitted_gate().inputs).evidence()
        expected_digest = "sha256:" + hashlib.sha256(
            admission_body().encode("utf-8")
        ).hexdigest()
        self.assertEqual(evidence["schemaVersion"], EVIDENCE_SCHEMA)
        self.assertEqual(evidence["review_body_sha256"], expected_digest)
        self.assertEqual(evidence["review_state"], "ACTIVE_UNEDITED")
        self.assertEqual(evidence["review_updated_at"], CREATED_AT)
        self.assertEqual(evidence["reviewer_association"], "OWNER")

    def test_edited_live_comment_cannot_admit(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "edited comment cannot admit"):
            admitted_gate(last_edited_at="2026-08-26T08:00:00Z")

    def test_closed_pull_request_cannot_admit(self) -> None:
        responses = live_reader()

        def reader(path: str):
            value = responses(path)
            if path == f"/repos/{REPOSITORY}/pulls/{PR_NUMBER}":
                return {**value, "state": "closed"}
            return value

        with self.assertRaisesRegex(AdmissionError, "not open"):
            gate_decision(
                "issue_comment",
                issue_comment_event(),
                REPOSITORY,
                POLICY_SHA,
                reader,
            )

    def test_minimized_live_comment_cannot_admit(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "minimized comment"):
            admitted_gate(minimized=True)

    def test_admission_footer_is_byte_exact(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "gate footer is malformed"):
            gate_decision(
                "issue_comment",
                issue_comment_event(body=admission_body().rstrip() + " "),
                REPOSITORY,
                POLICY_SHA,
                live_reader(body=admission_body().rstrip() + " "),
            )

    def test_new_live_head_invalidates_dispatch(self) -> None:
        inputs = admitted_gate().inputs
        reader = live_reader(head_sha=NEXT_SHA, body=admission_body())
        with self.assertRaisesRegex(AdmissionError, "does not equal the live"):
            decide_call(inputs, reader)

    def test_coordinate_mismatch_invalidates_dispatch(self) -> None:
        inputs = dict(admitted_gate().inputs)
        inputs["execution_merge_sha"] = NEXT_SHA
        with self.assertRaisesRegex(AdmissionError, "differs from the live gate"):
            decide_call(inputs)

    def test_metadata_mismatch_invalidates_dispatch(self) -> None:
        inputs = dict(admitted_gate().inputs)
        inputs["review_metadata"] = (
            '{"association":"OWNER","state":"ACTIVE_UNEDITED",'
            '"updated_at":"2026-08-26T08:00:01Z"}'
        )
        with self.assertRaisesRegex(AdmissionError, "differs from the live gate"):
            decide_call(inputs)

    def test_workflow_sha_must_equal_trusted_policy_sha(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "workflow does not equal"):
            decide_call(admitted_gate().inputs, workflow_sha=NEXT_SHA)

    def test_caller_must_be_the_main_branch_gate(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "trusted main-branch gate"):
            decide_call(admitted_gate().inputs, workflow_ref="untrusted/workflow")

    def test_null_execution_merge_refuses_admission(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "full lowercase commit SHA"):
            admitted_gate(merge_sha=None)

    def test_execution_merge_parents_bind_live_base_and_head(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "parents do not bind"):
            admitted_gate(merge_parents=[BASE_SHA, NEXT_SHA])

    def test_revocation_dispatch_is_cleanly_ineligible(self) -> None:
        revocation = gate_decision(
            "issue_comment",
            issue_comment_event(body=revocation_body()),
            REPOSITORY,
            POLICY_SHA,
            live_reader(),
        )
        admission = decide_call(
            revocation.inputs,
            reader=live_reader(),
            event_payload=issue_comment_event(body=revocation_body()),
        )
        self.assertFalse(admission.eligible)
        self.assertEqual(admission.event_class, "TRUSTED_REVOCATION")
        self.assertEqual(admission.review_state, "REVOKED")

    def test_admission_edit_call_is_cleanly_ineligible(self) -> None:
        event = issue_comment_event(
            action="edited",
            body="Admission text changed.",
            prior_body=admission_body(),
        )
        revocation = gate_decision(
            "issue_comment",
            event,
            REPOSITORY,
            POLICY_SHA,
            live_reader(),
        )
        admission = decide_call(
            revocation.inputs,
            reader=live_reader(),
            event_payload=event,
        )
        self.assertFalse(admission.eligible)
        self.assertEqual(admission.reason, "admission-comment-edited")


class PublicationAdmissionTests(unittest.TestCase):
    def resolve(self, reader=None):
        live = publication_reader() if reader is None else reader
        source = _publication_source_from_event(
            event_name="workflow_run",
            event=workflow_run_event(),
            github_sha=POLICY_SHA,
            workflow_sha=POLICY_SHA,
            workflow_ref=PUBLICATION_WORKFLOW_REF,
            repository=REPOSITORY,
            policy_sha=POLICY_SHA,
            fetch_json=live,
        )
        artifacts = _artifact_references(
            repository=REPOSITORY,
            source_run_id=SOURCE_RUN_ID,
            source_head_sha=POLICY_SHA,
            expected_names=(*PROVISIONAL_ARTIFACT_NAMES, PUBLICATION_TICKET_NAME),
            fetch_json=live,
        )
        return live, source, artifacts

    def ticket(self, artifacts: dict[str, ArtifactReference]):
        admission = decide_call(admitted_gate().inputs)
        return _publication_ticket_document(
            admission=admission,
            source_run_id=SOURCE_RUN_ID,
            source_run_attempt=SOURCE_RUN_ATTEMPT,
            source_workflow_ref=GATE_WORKFLOW_REF,
            source_workflow_sha=POLICY_SHA,
            provisional_artifacts={
                name: artifacts[name] for name in PROVISIONAL_ARTIFACT_NAMES
            },
        )

    def test_exact_source_run_and_artifact_identities_revalidate_live(self) -> None:
        reader, source, artifacts = self.resolve()
        admission = _validate_publication_ticket(
            ticket=self.ticket(artifacts),
            source=source,
            artifacts=artifacts,
            fetch_json=reader,
        )

        self.assertTrue(admission.eligible)
        self.assertEqual(admission.reviewed_head_sha, HEAD_SHA)
        self.assertEqual(admission.execution_merge_sha, MERGE_SHA)

    def test_source_run_rejects_live_identity_change(self) -> None:
        reader = publication_reader(live_run_mutation=("run_attempt", 2))

        with self.assertRaisesRegex(AdmissionError, "run_attempt changed"):
            self.resolve(reader)

    def test_source_run_refuses_attempt_ambiguous_rerun(self) -> None:
        event = workflow_run_event()
        event_run = event["workflow_run"]
        assert isinstance(event_run, dict)
        event_run["run_attempt"] = 2
        reader = publication_reader(live_run_mutation=("run_attempt", 2))

        with self.assertRaisesRegex(AdmissionError, "rerun attempts are ambiguous"):
            _publication_source_from_event(
                event_name="workflow_run",
                event=event,
                github_sha=POLICY_SHA,
                workflow_sha=POLICY_SHA,
                workflow_ref=PUBLICATION_WORKFLOW_REF,
                repository=REPOSITORY,
                policy_sha=POLICY_SHA,
                fetch_json=reader,
            )

    def test_source_inventory_rejects_established_name_pre_squat(self) -> None:
        reader = publication_reader(
            artifacts=source_artifact_documents(extra_name="review-baseline")
        )

        with self.assertRaisesRegex(AdmissionError, "names are not the exact"):
            self.resolve(reader)

    def test_source_inventory_rejects_admitted_index_fabrication(self) -> None:
        reader = publication_reader(
            artifacts=source_artifact_documents(
                extra_name="native-verifier-index-provisional"
            )
        )

        with self.assertRaisesRegex(AdmissionError, "names are not the exact"):
            self.resolve(reader)

    def test_source_inventory_rejects_oversized_untrusted_artifact(self) -> None:
        artifacts = source_artifact_documents()
        artifacts[0]["size_in_bytes"] = 512_000_001
        reader = publication_reader(artifacts=artifacts)

        with self.assertRaisesRegex(AdmissionError, "exceeds its size limit"):
            self.resolve(reader)

    def test_ticket_rejects_changed_provisional_artifact_digest(self) -> None:
        reader, source, artifacts = self.resolve()
        ticket = self.ticket(artifacts)
        ticket_artifacts = ticket["provisionalArtifacts"]
        assert isinstance(ticket_artifacts, list)
        first = ticket_artifacts[0]
        assert isinstance(first, dict)
        first["digest"] = "sha256:" + "f" * 64

        with self.assertRaisesRegex(AdmissionError, "artifact identities differ"):
            _validate_publication_ticket(
                ticket=ticket,
                source=source,
                artifacts=artifacts,
                fetch_json=reader,
            )

    def test_live_standing_revocation_refuses_publication(self) -> None:
        initial_reader, _, initial_artifacts = self.resolve()
        ticket = self.ticket(initial_artifacts)
        reader, source, artifacts = self.resolve(
            publication_reader(revocation=True)
        )
        del initial_reader

        with self.assertRaisesRegex(AdmissionError, "revocation is active"):
            _validate_publication_ticket(
                ticket=ticket,
                source=source,
                artifacts=artifacts,
                fetch_json=reader,
            )

    def test_receipt_binds_source_publisher_and_exact_artifact_identities(
        self,
    ) -> None:
        reader, published = publication_receipt_reader()
        _, source, source_artifacts = self.resolve(reader)
        ticket = self.ticket(source_artifacts)
        admission = _validate_publication_ticket(
            ticket=ticket,
            source=source,
            artifacts=source_artifacts,
            fetch_json=reader,
        )
        candidate = [
            {
                "artifactId": item["id"],
                "digest": str(item["digest"]).removeprefix("sha256:"),
                "name": item["name"],
            }
            for item in published
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(candidate), encoding="utf-8")
            receipt = _publication_receipt_document(
                path=path,
                ticket=ticket,
                admission=admission,
                source=source,
                source_artifacts=source_artifacts,
                publisher_workflow_ref=PUBLICATION_WORKFLOW_REF,
                publisher_workflow_sha=POLICY_SHA,
                publisher_run_id=PUBLISHER_RUN_ID,
                publisher_run_attempt=PUBLISHER_RUN_ATTEMPT,
                fetch_json=reader,
            )

        self.assertEqual(receipt["schemaVersion"], PUBLICATION_RECEIPT_SCHEMA)
        self.assertEqual(receipt["publisher"]["runId"], PUBLISHER_RUN_ID)
        self.assertEqual(
            [item["name"] for item in receipt["artifacts"]],
            list(PUBLICATION_ARTIFACT_NAMES),
        )
        self.assertEqual(
            [item["name"] for item in receipt["source"]["artifacts"]],
            [*PROVISIONAL_ARTIFACT_NAMES, PUBLICATION_TICKET_NAME],
        )

    def test_receipt_rejects_artifact_from_another_publisher_run(self) -> None:
        reader, published = publication_receipt_reader(
            artifact_run_id=PUBLISHER_RUN_ID + 1
        )
        _, source, source_artifacts = self.resolve(reader)
        ticket = self.ticket(source_artifacts)
        admission = _validate_publication_ticket(
            ticket=ticket,
            source=source,
            artifacts=source_artifacts,
            fetch_json=reader,
        )
        candidate = [
            {
                "artifactId": item["id"],
                "digest": item["digest"],
                "name": item["name"],
            }
            for item in published
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(candidate), encoding="utf-8")
            with self.assertRaisesRegex(
                AdmissionError,
                "published artifact live identity differs",
            ):
                _publication_receipt_document(
                    path=path,
                    ticket=ticket,
                    admission=admission,
                    source=source,
                    source_artifacts=source_artifacts,
                    publisher_workflow_ref=PUBLICATION_WORKFLOW_REF,
                    publisher_workflow_sha=POLICY_SHA,
                    publisher_run_id=PUBLISHER_RUN_ID,
                    publisher_run_attempt=PUBLISHER_RUN_ATTEMPT,
                    fetch_json=reader,
                )

    def test_receipt_refuses_attempt_ambiguous_publisher_rerun(self) -> None:
        reader, _ = publication_receipt_reader()
        _, source, source_artifacts = self.resolve(reader)
        ticket = self.ticket(source_artifacts)
        admission = _validate_publication_ticket(
            ticket=ticket,
            source=source,
            artifacts=source_artifacts,
            fetch_json=reader,
        )

        with self.assertRaisesRegex(AdmissionError, "rerun attempts are ambiguous"):
            _publication_receipt_document(
                path=Path("unused-after-attempt-refusal.json"),
                ticket=ticket,
                admission=admission,
                source=source,
                source_artifacts=source_artifacts,
                publisher_workflow_ref=PUBLICATION_WORKFLOW_REF,
                publisher_workflow_sha=POLICY_SHA,
                publisher_run_id=PUBLISHER_RUN_ID,
                publisher_run_attempt=2,
                fetch_json=reader,
            )


class WorkflowPolicyTests(unittest.TestCase):
    def test_default_branch_gate_never_checks_out_pull_request_code(self) -> None:
        workflow = Path(".github/workflows/review-baseline-gate.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("  issue_comment:\n", workflow)
        self.assertIn("  pull_request_target:\n", workflow)
        self.assertIn("ref: ${{ github.workflow_sha }}", workflow)
        self.assertIn("uses: ./.github/workflows/conformance.yml", workflow)
        execute = workflow.split("\n  execute:\n", 1)[1]
        self.assertIn(
            "group: ofarm-pr-${{ needs.gate.outputs.pull_request_number }}",
            execute,
        )
        self.assertIn("cancel-in-progress: true", execute)
        self.assertIn("ofarm-gate-comment-", workflow)
        self.assertIn("ofarm-pr-{0}", workflow)
        self.assertNotIn("actions: write", workflow)
        self.assertNotIn("/dispatches", workflow)
        self.assertNotIn("github.event.pull_request.head", workflow)
        self.assertNotIn("github.head_ref", workflow)

    def test_executor_has_only_trusted_dispatch_and_main_triggers(self) -> None:
        workflow = Path(".github/workflows/conformance.yml").read_text(
            encoding="utf-8"
        )
        trigger = workflow.split("permissions: {}", 1)[0]
        self.assertIn("  push:\n", trigger)
        self.assertIn("  workflow_call:\n", trigger)
        self.assertNotIn("pull_request_target", trigger)
        self.assertNotIn("pull_request_review", trigger)
        self.assertNotIn("workflow_dispatch", trigger)
        inputs = trigger.split("    inputs:\n", 1)[1]
        names = re.findall(r"^      ([a-z0-9_]+):$", inputs, re.MULTILINE)
        self.assertEqual(len(names), 10)
        self.assertIn("review_metadata", names)
        self.assertIn(
            "OFARM_BASELINE_ADMISSION_POLICY_SHA: ${{ github.workflow_sha }}",
            workflow,
        )

    def test_untrusted_jobs_upload_only_provisional_artifacts(self) -> None:
        source_workflow = Path(".github/workflows/conformance.yml").read_text(
            encoding="utf-8"
        )
        producers = {
            "conformance": "name: conformance-provisional\n",
            "native-verifier": (
                "name: native-verifier-${{ matrix.architecture }}-provisional\n"
            ),
        }
        authoritative_names = (
            "name: review-baseline\n",
            "name: platform-mvp-evidence\n",
            "name: native-verifier-amd64\n",
            "name: native-verifier-arm64\n",
            "name: native-verifier-index\n",
            "name: evidence-publication-receipt\n",
        )
        for job_name, provisional_name in producers.items():
            section = workflow_job_section(source_workflow, job_name)
            self.assertIn(provisional_name, section)
            for authoritative_name in authoritative_names:
                self.assertNotIn(authoritative_name, section)

        self.assertNotIn("\n  native-verifier-index:\n", source_workflow)
        self.assertNotIn("compose-index", source_workflow)
        self.assertNotIn("prepare-release-identity", source_workflow)
        handoff = workflow_job_section(source_workflow, "publication-handoff")
        self.assertIn(
            "needs: [baseline-admission, conformance, native-verifier]",
            handoff,
        )
        self.assertIn("--operation handoff", handoff)
        self.assertIn("name: evidence-publication-ticket\n", handoff)
        self.assertNotIn(
            "ref: ${{ needs.baseline-admission.outputs.execution_merge_sha }}",
            handoff,
        )
        self.assertIn("git -C .publication-policy diff --exit-code", handoff)
        self.assertIn("--porcelain=v1 --untracked-files=all", handoff)
        self.assertEqual(handoff.count("actions/upload-artifact@"), 1)

    def test_cross_run_publisher_never_executes_admitted_code(self) -> None:
        workflow = Path(".github/workflows/evidence-publication.yml").read_text(
            encoding="utf-8"
        )
        trigger = workflow.split("permissions: {}", 1)[0]
        self.assertIn("  workflow_run:\n", trigger)
        self.assertIn("      - conformance\n", trigger)
        self.assertIn("      - reviewed-head baseline gate\n", trigger)
        self.assertNotIn("workflow_dispatch", trigger)
        self.assertNotIn("pull_request", trigger)
        self.assertNotIn("push:", trigger)
        self.assertIn("Refuse attempt-ambiguous publisher reruns", workflow)
        self.assertIn('test "$GITHUB_RUN_ATTEMPT" = 1', workflow)

        source_admission = workflow_job_section(workflow, "source-admission")
        publisher = workflow_job_section(workflow, "publish")
        for section in (source_admission, publisher):
            self.assertIn("runs-on: ubuntu-24.04", section)
            self.assertIn(
                "ref: ${{ env.OFARM_PUBLICATION_POLICY_SHA }}",
                section,
            )
            self.assertNotIn("actions/setup-python", section)
            self.assertNotIn("GITHUB_PATH", section)
            self.assertNotIn("GITHUB_ENV", section)
            self.assertNotIn("uses: ./", section)
            self.assertNotIn(
                "ref: ${{ steps.publisher-start.outputs.execution_merge_sha }}",
                section,
            )
            self.assertIn("git -C .publication-policy diff --exit-code", section)
            self.assertIn("--porcelain=v1 --untracked-files=all", section)

        downloads = workflow.split("uses: actions/download-artifact@")[1:]
        self.assertEqual(len(downloads), 7)
        for download in downloads:
            step = download.split("\n      - ", 1)[0]
            self.assertIn("artifact-ids:", step)
            self.assertIn("github-token:", step)
            self.assertIn("repository:", step)
            self.assertIn("run-id:", step)

        self.assertEqual(publisher.count("collect-oci"), 2)
        self.assertIn("compose-index", publisher)
        self.assertIn("prepare-release-identity", publisher)
        self.assertIn(
            "steps.upload-native-amd64.outputs.artifact-id",
            publisher,
        )
        self.assertIn(
            "steps.upload-native-arm64.outputs.artifact-id",
            publisher,
        )
        self.assertIn("--published-artifacts-input", publisher)
        self.assertIn("--publication-receipt-output", publisher)
        self.assertIn("--publisher-run-id", publisher)
        self.assertIn("--publisher-run-attempt", publisher)
        self.assertIn(
            "group: ${{ needs.source-admission.outputs."
            "publication_concurrency_group }}",
            publisher,
        )

    def test_authoritative_names_belong_only_to_cross_run_publisher(self) -> None:
        source_workflow = Path(".github/workflows/conformance.yml").read_text(
            encoding="utf-8"
        )
        publication_workflow = Path(
            ".github/workflows/evidence-publication.yml"
        ).read_text(
            encoding="utf-8"
        )
        authoritative_names = (
            "review-baseline",
            "platform-mvp-evidence",
            "native-verifier-amd64",
            "native-verifier-arm64",
            "native-verifier-index",
            "evidence-publication-receipt",
        )
        for artifact_name in authoritative_names:
            source_matches = re.findall(
                rf"^\s+name: {re.escape(artifact_name)}$",
                source_workflow,
                re.MULTILINE,
            )
            publisher_matches = re.findall(
                rf"^\s+name: {re.escape(artifact_name)}$",
                publication_workflow,
                re.MULTILINE,
            )
            self.assertEqual(source_matches, [])
            self.assertEqual(len(publisher_matches), 1)

        self.assertEqual(
            source_workflow.count("name: conformance-provisional\n"),
            1,
        )
        self.assertEqual(
            source_workflow.count(
                "name: native-verifier-${{ matrix.architecture }}-provisional\n"
            ),
            1,
        )
        self.assertEqual(
            source_workflow.count("name: evidence-publication-ticket\n"),
            1,
        )
        receipt_position = publication_workflow.index(
            "name: evidence-publication-receipt\n"
        )
        for name in authoritative_names[:-1]:
            self.assertLess(
                publication_workflow.index(f"name: {name}\n"),
                receipt_position,
            )


if __name__ == "__main__":
    unittest.main()
