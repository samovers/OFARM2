"""The lifecycle has no ledger; these fixtures check the private adapter."""

from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from conformance.ci_policy_transition_execution import GhLifecycle, RELAY_ENV_KEYS
from conformance.ci_policy_transition_gh_relay import (
    FrozenReleasePolicy,
    RelayError,
    RelayEvent,
    RelayLimits,
    RelaySummary,
    QuotaFacts,
)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.frames, self.notifications = [], []
        self.reject = None
        self.cleanup_error = False
        self.cleaned = False
        outer = self

        class Relay:
            def __init__(self, directory, policy, limits, account, terminal):
                self.account, self.terminal = account, terminal

            def __enter__(self):
                return self

            def environment(self, base):
                return {
                    **base,
                    **dict(
                        zip(
                            RELAY_ENV_KEYS,
                            (
                                "/fictional/config",
                                "/fictional/cache",
                                "github.com",
                                "1",
                                "1",
                                "1",
                                "1",
                                "0",
                            ),
                        )
                    ),
                }

            def check(self):
                pass

            def finish(self):
                return RelaySummary(1, 20)

            def __exit__(self, *args):
                outer.cleaned = True
                if outer.cleanup_error:
                    raise RelayError("fictional cleanup failure")

        self.mock = patch("conformance.ci_policy_transition_execution.GhRelay", Relay)
        self.mock.start()

        def observe(frame):
            self.frames.append(frame)
            if frame["operation"] == "close":
                self.assertTrue(self.cleaned)
            return {
                "accepted": frame["operation"] != self.reject,
                "sequence": frame["sequence"],
            }

        self.lifecycle = GhLifecycle(
            Path("/fictional"),
            FrozenReleasePolicy(
                "fictional/example", 1, "fixture", "a" * 40, 2, ((3, 4), (5, 6))
            ),
            RelayLimits(20, 1000, 60),
            observe,
            self.notifications.append,
        )

    def tearDown(self):
        self.mock.stop()

    def event(self, phase, request_id=1, **overrides):
        values = dict(
            phase=phase,
            request_id=request_id,
            bucket="rest",
            method="GET",
            host="api.github.com",
            path="/repos/fictional/example",
        )
        values.update(overrides)
        return RelayEvent(**values)

    def test_credential_free_environment_and_cleanup_before_close(self):
        env = self.lifecycle.start({"GH_TOKEN": "fictional-secret", "PATH": "/bin"})
        self.assertEqual(set(env), set(RELAY_ENV_KEYS))
        self.lifecycle._account(self.event("request"))
        self.lifecycle._account(
            self.event(
                "response", status=200, quota=QuotaFacts("core", 100, 99, 2000000000, 1)
            )
        )
        self.lifecycle._account(
            self.event("completed", status=200, response_bytes=20, complete=True)
        )
        self.assertEqual(self.lifecycle.finish(), RelaySummary(1, 20))
        self.assertEqual(
            [f["operation"] for f in self.frames],
            ["open", "begin", "response", "end", "close"],
        )
        self.assertNotIn(
            "fictional-secret", repr(self.frames) + repr(self.lifecycle.__dict__)
        )
        with self.assertRaises(RelayError):
            self.lifecycle.check()

    def test_graphql_does_not_invent_point_cost(self):
        self.lifecycle.start({"GH_TOKEN": "fictional-secret"})
        self.lifecycle._account(
            self.event(
                "response",
                bucket="graphql",
                status=200,
                quota=QuotaFacts("graphql", 5000, 4998, 2000000000, 2),
            )
        )
        self.assertEqual(self.frames[-1]["quota"]["used"], 2)
        self.assertNotIn("cost", self.frames[-1]["quota"])
        self.lifecycle.abort()

    def test_concurrent_callbacks_have_one_sequence_and_unique_request_ids(self):
        self.lifecycle.start({"GH_TOKEN": "fictional-secret"})
        threads = [
            threading.Thread(
                target=self.lifecycle._account, args=(self.event("request", i),)
            )
            for i in range(1, 11)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(1)
            self.assertFalse(thread.is_alive())
        self.assertEqual([f["sequence"] for f in self.frames], list(range(11)))
        self.assertEqual(len({f["requestId"] for f in self.frames[1:]}), 10)
        self.lifecycle.abort()

    def test_unknown_cancel_stays_incomplete(self):
        self.lifecycle.start({"GH_TOKEN": "fictional-secret"})
        self.lifecycle._account(self.event("request"))
        self.lifecycle._account(
            self.event("completed", response_bytes=13, complete=False)
        )
        self.assertEqual(self.frames[-1]["operation"], "end")
        self.assertFalse(self.frames[-1]["complete"])
        self.assertEqual(self.frames[-1]["bytes"], 13)
        self.lifecycle.abort()

    def test_callback_failure_and_cleanup_failure_cannot_close(self):
        self.lifecycle.start({"GH_TOKEN": "fictional-secret"})
        self.reject = "begin"
        with self.assertRaises(RelayError):
            self.lifecycle._account(self.event("request"))
        with self.assertRaises(RelayError):
            self.lifecycle.finish()
        self.assertTrue(self.cleaned)
        self.assertNotIn("close", [f["operation"] for f in self.frames])

    def test_cleanup_error_refuses_and_notifies(self):
        self.lifecycle.start({"GH_TOKEN": "fictional-secret"})
        self.cleanup_error = True
        with self.assertRaises(RelayError):
            self.lifecycle.finish()
        self.assertTrue(self.notifications)
        self.assertNotIn("close", [f["operation"] for f in self.frames])

    def test_bucket_mapping_and_explicit_cost_only_when_observed(self):
        self.lifecycle.start({"GH_TOKEN": "fictional-secret"})
        for bucket, host, expected in [
            ("tuf", "tuf-repo.github.com", "tuf"),
            ("blob", "release-assets.githubusercontent.com", "download"),
            ("blob", "tmaproduction.blob.core.windows.net", "blob"),
        ]:
            self.lifecycle._account(self.event("request", bucket=bucket, host=host))
            self.assertEqual(self.frames[-1]["bucket"], expected)
        self.lifecycle._account(
            self.event(
                "response",
                bucket="graphql",
                status=200,
                quota=QuotaFacts("graphql", 5000, 4998, 2000000000, 2, 2),
            )
        )
        self.assertEqual(self.frames[-1]["quota"]["cost"], 2)
        self.lifecycle.abort()


if __name__ == "__main__":
    unittest.main()
