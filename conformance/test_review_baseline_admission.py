#!/usr/bin/env python3
"""Zero-dependency tests for trusted expensive-baseline admission."""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

from conformance.review_baseline_admission import (
    ADMISSION_MARKER,
    EVIDENCE_SCHEMA,
    REVOCATION_MARKER,
    GRAPHQL_COMMENT_PREFIX,
    AdmissionError,
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
GATE_WORKFLOW_REF = (
    f"{REPOSITORY}/.github/workflows/review-baseline-gate.yml@refs/heads/main"
)
CONFORMANCE_WORKFLOW_REF = (
    f"{REPOSITORY}/.github/workflows/conformance.yml@refs/heads/main"
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
        workflow = Path(".github/workflows/conformance.yml").read_text(
            encoding="utf-8"
        )
        producers = {
            "conformance": "name: conformance-provisional\n",
            "native-verifier": (
                "name: native-verifier-${{ matrix.architecture }}-provisional\n"
            ),
            "native-verifier-index": "name: native-verifier-index-provisional\n",
        }
        authoritative_names = (
            "name: review-baseline\n",
            "name: platform-mvp-evidence\n",
            "name: native-verifier-${{ matrix.architecture }}\n",
            "name: native-verifier-index\n",
        )
        for job_name, provisional_name in producers.items():
            section = workflow_job_section(workflow, job_name)
            self.assertIn(provisional_name, section)
            self.assertNotIn("id: final-admission", section)
            self.assertNotIn("id: success-artifact-proof", section)
            for authoritative_name in authoritative_names:
                self.assertNotIn(authoritative_name, section)

    def test_authoritative_publishers_use_fresh_runners(self) -> None:
        workflow = Path(".github/workflows/conformance.yml").read_text(
            encoding="utf-8"
        )
        publishers = {
            "conformance-publisher": "conformance",
            "native-verifier-publisher": "native-verifier",
            "native-verifier-index-publisher": "native-verifier-index",
        }
        for publisher, producer in publishers.items():
            section = workflow_job_section(workflow, publisher)
            self.assertIn(f"needs.{producer}.result == 'success'", section)
            self.assertEqual(section.count("--operation admit"), 2)
            self.assertIn(
                "ref: ${{ env.OFARM_BASELINE_ADMISSION_POLICY_SHA }}", section
            )
            self.assertNotIn(
                "ref: ${{ needs.baseline-admission.outputs.execution_merge_sha }}",
                section,
            )
            self.assertNotIn("actions/setup-python", section)
            self.assertNotIn("GITHUB_PATH", section)
            self.assertNotIn("GITHUB_ENV", section)
            self.assertIn("actions/download-artifact@", section)
            self.assertIn("producer supplied an untrusted admission receipt", section)
            self.assertIn("id: publisher-start-admission", section)
            self.assertIn("id: final-admission", section)
            self.assertIn("id: success-artifact-proof", section)
            self.assertIn(
                "steps.success-artifact-proof.outcome == 'success'", section
            )

        index_producer = workflow_job_section(workflow, "native-verifier-index")
        self.assertIn(
            "needs: [baseline-admission, native-verifier-publisher]",
            index_producer,
        )

    def test_normal_artifact_names_are_owned_by_publishers(self) -> None:
        workflow = Path(".github/workflows/conformance.yml").read_text(
            encoding="utf-8"
        )
        owners = {
            "review-baseline": "conformance-publisher",
            "platform-mvp-evidence": "conformance-publisher",
            "native-verifier-${{ matrix.architecture }}": (
                "native-verifier-publisher"
            ),
            "native-verifier-index": "native-verifier-index-publisher",
        }
        for artifact_name, publisher in owners.items():
            matches = re.findall(
                rf"^\s+name: {re.escape(artifact_name)}$", workflow, re.MULTILINE
            )
            self.assertEqual(len(matches), 1)
            section = workflow_job_section(workflow, publisher)
            self.assertIn(f"name: {artifact_name}\n", section)

        self.assertIn("review-baseline-admission-failure", workflow)
        self.assertIn(
            "native-verifier-${{ matrix.architecture }}-admission-failure",
            workflow,
        )
        self.assertIn("native-verifier-index-admission-failure", workflow)


if __name__ == "__main__":
    unittest.main()
