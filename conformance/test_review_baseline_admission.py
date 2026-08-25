#!/usr/bin/env python3
"""Zero-dependency tests for the live expensive-baseline admission gate."""

from __future__ import annotations

import unittest

from conformance.review_baseline_admission import (
    EVIDENCE_SCHEMA,
    AdmissionError,
    MARKER,
    decide,
)


SHA = "a" * 40
NEXT_SHA = "b" * 40
BASE_SHA = "c" * 40
MERGE_SHA = "d" * 40
POLICY_SHA = "e" * 40
REPOSITORY = "samovers/OFARM2"
PR_NUMBER = 336
REVIEW_ID = 12345


def event(*, review_sha: str = SHA) -> dict[str, object]:
    return {
        "repository": {"full_name": REPOSITORY},
        "review": {"id": REVIEW_ID, "commit_id": review_sha},
        "pull_request": {"number": PR_NUMBER},
    }


def footer(sha: str = SHA) -> str:
    return f"Review complete.\n\n{MARKER}\nhead={sha}\nblockers=0\n"


def live_reader(
    *,
    body: str,
    review_sha: str = SHA,
    head_sha: str = SHA,
    base_sha: str = BASE_SHA,
    merge_sha: str = MERGE_SHA,
    merge_parents: list[str] | None = None,
    state: str = "COMMENTED",
    association: str = "OWNER",
):
    parent_shas = merge_parents or [base_sha, head_sha]
    responses = {
        f"/repos/{REPOSITORY}/pulls/{PR_NUMBER}": {
            "number": PR_NUMBER,
            "head": {"sha": head_sha},
            "base": {"sha": base_sha},
            "merge_commit_sha": merge_sha,
        },
        f"/repos/{REPOSITORY}/pulls/{PR_NUMBER}/reviews/{REVIEW_ID}": {
            "id": REVIEW_ID,
            "body": body,
            "commit_id": review_sha,
            "state": state,
            "author_association": association,
        },
        f"/repos/{REPOSITORY}/git/commits/{merge_sha}": {
            "sha": merge_sha,
            "parents": [{"sha": value} for value in parent_shas],
        },
    }
    return responses.__getitem__


def decide_review(event_payload, reader):
    return decide(
        "pull_request_review",
        event_payload,
        NEXT_SHA,
        REPOSITORY,
        POLICY_SHA,
        reader,
    )


class AdmissionTests(unittest.TestCase):
    def test_main_push_is_eligible_and_carries_policy(self) -> None:
        admission = decide(
            "push",
            {"ref": "refs/heads/main", "after": SHA},
            SHA,
            REPOSITORY,
            POLICY_SHA,
        )
        self.assertTrue(admission.eligible)
        self.assertEqual(admission.reviewed_head_sha, SHA)
        self.assertEqual(admission.execution_merge_sha, SHA)
        self.assertEqual(admission.policy_sha, POLICY_SHA)

    def test_non_main_push_refuses(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "limited to main"):
            decide(
                "push",
                {"ref": "refs/heads/topic", "after": SHA},
                SHA,
                REPOSITORY,
                POLICY_SHA,
            )

    def test_pull_request_target_synchronize_revokes_without_admission(self) -> None:
        admission = decide(
            "pull_request_target",
            {
                "action": "synchronize",
                "repository": {"full_name": REPOSITORY},
                "pull_request": {"number": PR_NUMBER},
            },
            NEXT_SHA,
            REPOSITORY,
            POLICY_SHA,
        )
        self.assertFalse(admission.eligible)
        self.assertEqual(admission.event_class, "PULL_REQUEST_REVOCATION")
        self.assertEqual(admission.pull_request_number, PR_NUMBER)

    def test_unconfigured_pull_request_action_refuses(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "revocation action"):
            decide(
                "pull_request_target",
                {
                    "action": "labeled",
                    "repository": {"full_name": REPOSITORY},
                    "pull_request": {"number": PR_NUMBER},
                },
                NEXT_SHA,
                REPOSITORY,
                POLICY_SHA,
            )

    def test_activation_pull_request_event_is_also_ineligible(self) -> None:
        admission = decide(
            "pull_request",
            {
                "action": "opened",
                "repository": {"full_name": REPOSITORY},
                "pull_request": {"number": PR_NUMBER},
            },
            NEXT_SHA,
            REPOSITORY,
            POLICY_SHA,
        )
        self.assertFalse(admission.eligible)

    def test_ordinary_live_review_does_not_admit(self) -> None:
        admission = decide_review(event(), live_reader(body="Blockers: 1"))
        self.assertFalse(admission.eligible)
        self.assertEqual(admission.reviewed_head_sha, "")

    def test_live_review_binds_head_base_and_execution_merge(self) -> None:
        admission = decide_review(event(), live_reader(body=footer()))
        self.assertTrue(admission.eligible)
        self.assertEqual(admission.reviewed_head_sha, SHA)
        self.assertEqual(admission.base_sha, BASE_SHA)
        self.assertEqual(admission.execution_merge_sha, MERGE_SHA)
        self.assertEqual(admission.pull_request_number, PR_NUMBER)
        self.assertEqual(admission.review_id, REVIEW_ID)

    def test_evidence_records_both_coordinates_and_policy(self) -> None:
        evidence = decide_review(event(), live_reader(body=footer())).evidence()
        self.assertEqual(evidence["schemaVersion"], EVIDENCE_SCHEMA)
        self.assertEqual(evidence["reviewed_head_sha"], SHA)
        self.assertEqual(evidence["base_sha"], BASE_SHA)
        self.assertEqual(evidence["execution_merge_sha"], MERGE_SHA)
        self.assertEqual(evidence["policy_sha"], POLICY_SHA)

    def test_new_live_head_invalidates_old_review_event(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "live pull-request head"):
            decide_review(event(), live_reader(body=footer(), head_sha=NEXT_SHA))

    def test_live_review_edit_removing_footer_revokes_admission(self) -> None:
        admission = decide_review(
            event(), live_reader(body="Review edited; admission withdrawn.")
        )
        self.assertFalse(admission.eligible)

    def test_dismissed_live_review_refuses(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "COMMENTED or APPROVED"):
            decide_review(event(), live_reader(body=footer(), state="DISMISSED"))

    def test_footer_must_be_final_and_exact(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "malformed or not final"):
            decide_review(
                event(), live_reader(body=footer() + "Later qualification\n")
            )

    def test_footer_sha_must_match_review_commit(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "malformed or not final"):
            decide_review(event(), live_reader(body=footer(NEXT_SHA)))

    def test_event_and_live_review_commit_must_match(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "event and live review commits"):
            decide_review(event(review_sha=NEXT_SHA), live_reader(body=footer()))

    def test_reviewer_requires_repository_standing(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "repository standing"):
            decide_review(
                event(), live_reader(body=footer(), association="CONTRIBUTOR")
            )

    def test_execution_merge_must_bind_base_and_head(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "parents do not bind"):
            decide_review(
                event(),
                live_reader(body=footer(), merge_parents=[BASE_SHA, NEXT_SHA]),
            )

    def test_execution_merge_must_have_exactly_two_parents(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "parents do not bind"):
            decide_review(
                event(), live_reader(body=footer(), merge_parents=[BASE_SHA])
            )

    def test_live_reader_is_mandatory(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "live GitHub reader"):
            decide(
                "pull_request_review",
                event(),
                NEXT_SHA,
                REPOSITORY,
                POLICY_SHA,
            )


if __name__ == "__main__":
    unittest.main()
