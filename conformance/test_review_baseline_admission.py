#!/usr/bin/env python3
"""Zero-dependency tests for the live expensive-baseline admission gate."""

from __future__ import annotations

import unittest

from conformance.review_baseline_admission import AdmissionError, MARKER, decide


SHA = "a" * 40
NEXT_SHA = "b" * 40
POLICY_SHA = "c" * 40
REPOSITORY = "samovers/OFARM2"
PR_NUMBER = 335
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
    state: str = "COMMENTED",
    association: str = "OWNER",
):
    responses = {
        f"/repos/{REPOSITORY}/pulls/{PR_NUMBER}": {
            "number": PR_NUMBER,
            "head": {"sha": head_sha},
        },
        f"/repos/{REPOSITORY}/pulls/{PR_NUMBER}/reviews/{REVIEW_ID}": {
            "id": REVIEW_ID,
            "body": body,
            "commit_id": review_sha,
            "state": state,
            "author_association": association,
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

    def test_ordinary_live_review_does_not_admit(self) -> None:
        admission = decide_review(event(), live_reader(body="Blockers: 1"))
        self.assertFalse(admission.eligible)
        self.assertEqual(admission.reviewed_head_sha, "")

    def test_live_exact_head_zero_blocker_review_is_eligible(self) -> None:
        admission = decide_review(event(), live_reader(body=footer()))
        self.assertTrue(admission.eligible)
        self.assertEqual(admission.reviewed_head_sha, SHA)

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
