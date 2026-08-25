#!/usr/bin/env python3
"""Zero-dependency tests for the expensive-baseline admission gate."""

from __future__ import annotations

import unittest

from conformance.review_baseline_admission import AdmissionError, MARKER, decide


SHA = "a" * 40
NEXT_SHA = "b" * 40


def review_event(
    *,
    body: str,
    review_sha: str = SHA,
    head_sha: str = SHA,
    state: str = "commented",
    association: str = "OWNER",
) -> dict[str, object]:
    return {
        "review": {
            "body": body,
            "commit_id": review_sha,
            "state": state,
            "author_association": association,
        },
        "pull_request": {"head": {"sha": head_sha}},
    }


def footer(sha: str = SHA) -> str:
    return f"Review complete.\n\n{MARKER}\nhead={sha}\nblockers=0\n"


class AdmissionTests(unittest.TestCase):
    def test_main_push_is_eligible(self) -> None:
        admission = decide(
            "push", {"ref": "refs/heads/main", "after": SHA}, SHA
        )
        self.assertTrue(admission.eligible)
        self.assertEqual(admission.target_sha, SHA)

    def test_non_main_push_refuses(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "limited to main"):
            decide("push", {"ref": "refs/heads/topic", "after": SHA}, SHA)

    def test_ordinary_review_does_not_start_baseline(self) -> None:
        admission = decide(
            "pull_request_review",
            review_event(body="Blockers: 1"),
            NEXT_SHA,
        )
        self.assertFalse(admission.eligible)
        self.assertEqual(admission.target_sha, "")

    def test_exact_head_zero_blocker_review_is_eligible(self) -> None:
        admission = decide(
            "pull_request_review", review_event(body=footer()), NEXT_SHA
        )
        self.assertTrue(admission.eligible)
        self.assertEqual(admission.target_sha, SHA)

    def test_new_head_invalidates_old_review(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "current pull-request head"):
            decide(
                "pull_request_review",
                review_event(body=footer(), head_sha=NEXT_SHA),
                NEXT_SHA,
            )

    def test_footer_must_be_final_and_exact(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "malformed or not final"):
            decide(
                "pull_request_review",
                review_event(body=footer() + "Later qualification\n"),
                NEXT_SHA,
            )

    def test_footer_sha_must_match_review_commit(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "malformed or not final"):
            decide(
                "pull_request_review",
                review_event(body=footer(NEXT_SHA)),
                NEXT_SHA,
            )

    def test_changes_requested_review_refuses(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "COMMENTED or APPROVED"):
            decide(
                "pull_request_review",
                review_event(body=footer(), state="changes_requested"),
                NEXT_SHA,
            )

    def test_reviewer_requires_repository_standing(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "repository standing"):
            decide(
                "pull_request_review",
                review_event(body=footer(), association="NONE"),
                NEXT_SHA,
            )


if __name__ == "__main__":
    unittest.main()
