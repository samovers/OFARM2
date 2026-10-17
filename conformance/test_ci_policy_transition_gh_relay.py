"""Fictional transport fixtures; no real credentials or provider calls."""

from __future__ import annotations

import http.client
import io
import json
import os
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from conformance.ci_policy_transition_gh_relay import (
    FrozenReleasePolicy,
    GhRelay,
    RelayError,
    RelayLimits,
    frozen_release_policy,
    _BoundedLines,
)


POLICY = FrozenReleasePolicy(
    "fictional/example", 123, "fixture-v1", "a" * 40, 77, ((101, 16), (102, 17))
)
API = "/repos/fictional/example"
QUOTA = [
    ("X-RateLimit-Resource", "core"),
    ("X-RateLimit-Limit", "1000"),
    ("X-RateLimit-Remaining", "900"),
    ("X-RateLimit-Reset", "2000000000"),
    ("X-RateLimit-Used", "100"),
]


class Response:
    def __init__(self, body=b"{}", status=200, headers=()):
        self.status = status
        self.reason = "OK" if status == 200 else "Fixture"
        self.body = io.BytesIO(body)
        self.headers = [
            ("Content-Length", str(len(body))),
            ("Content-Type", "application/json"),
            *QUOTA,
            *headers,
        ]

    def getheaders(self):
        return self.headers

    def read(self, n):
        return self.body.read(n)


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gh-test-", dir="/tmp")
        self.parent = Path(self.temp.name).resolve()
        self.events = []
        self.failures = []
        self.calls = []
        self.response = Response()
        self.connection_error = None
        outer = self

        class Connection:
            sock = None

            def __init__(self, host, port, *, context, timeout):
                outer.assertEqual(port, 443)
                outer.assertTrue(context.check_hostname)
                outer.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
                self.host = host
                if outer.connection_error:
                    raise outer.connection_error

            def request(self, method, target, body, headers):
                outer.calls.append((self.host, method, target, body, headers))

            def getresponse(self):
                return outer.response() if callable(outer.response) else outer.response

            def close(self):
                pass

        self.upstream = patch(
            "conformance.ci_policy_transition_gh_relay.http.client.HTTPSConnection",
            Connection,
        )
        self.upstream.start()
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.upstream.stop()
        self.temp.cleanup()

    def relay(self, **overrides):
        options = dict(
            max_requests=20,
            max_response_bytes=100000,
            lifetime_seconds=10,
            max_connections=4,
            io_timeout_seconds=0.5,
            drain_seconds=1,
        )
        options.update(overrides)
        return GhRelay(
            self.parent,
            POLICY,
            RelayLimits(**options),
            self.events.append,
            self.failures.append,
        )

    def prepare(self, relay):
        env = relay.environment({"GH_TOKEN": "fictional-token", "PATH": "/bin"})
        self.assertNotIn("GH_DEBUG", env)
        self.assertEqual(env["GH_CONFIG_DIR"], str(relay.config_directory))
        return env

    def request(
        self,
        relay,
        path=API,
        *,
        host="api.github.com",
        method="GET",
        body=b"",
        extra=b"",
    ):
        sock = socket.socket(socket.AF_UNIX)
        sock.settimeout(2)
        sock.connect(str(relay.socket_path))
        auth = (
            b"Authorization: token fictional-token\r\n"
            if host == "api.github.com"
            else b""
        )
        wire = (
            f"{method} {path} HTTP/1.1\r\nHost: {host}\r\n".encode()
            + auth
            + f"Content-Length: {len(body)}\r\n".encode()
            + extra
            + b"\r\n"
            + body
        )
        sock.sendall(wire)
        chunks = []
        try:
            while chunk := sock.recv(65536):
                chunks.append(chunk)
        except ConnectionResetError:
            pass
        finally:
            sock.close()
        return b"".join(chunks)

    def test_chunk_parser_partial_bytes_survive_terminal_failure(self):
        response = Response(b"unused")

        def incomplete(_amount):
            raise http.client.IncompleteRead(b"partial", 12)

        response.read = incomplete
        self.response = response
        with self.assertRaises(RelayError):
            with self.relay() as relay:
                self.prepare(relay)
                self.request(relay)
                relay.finish()
        completed = [event for event in self.events if event.phase == "completed"]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].response_bytes, 7)
        self.assertFalse(completed[0].complete)
        self.assertEqual(relay._response_bytes, 7)

    def test_complete_response_and_owned_cleanup(self):
        self.response = Response(b'{"fixture":true}')
        with self.relay() as relay:
            self.prepare(relay)
            directory = relay.directory
            self.assertEqual(os.stat(relay.config_directory).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(relay.socket_path).st_mode & 0o777, 0o600)
            result = self.request(relay)
            self.assertEqual(result.split(b"\r\n\r\n", 1)[1], b'{"fixture":true}')
            summary = relay.finish()
            self.assertEqual(summary.requests, 1)
        self.assertFalse(directory.exists())
        self.assertEqual(
            [e.phase for e in self.events], ["request", "response", "completed"]
        )
        self.assertTrue(self.events[-1].complete)
        self.assertEqual(self.events[-1].quota.resource, "core")
        self.assertIsNone(self.events[-1].quota.graphql_cost)
        self.assertEqual(self.failures, [])

    def test_account_before_dispatch_and_no_callback_secret(self):
        def account(event):
            if event.phase == "request":
                self.assertEqual(self.calls, [])
            self.assertNotIn("fictional-token", repr(event))
            self.events.append(event)

        with self.relay() as relay:
            relay._account = account
            self.prepare(relay)
            self.request(relay)
        self.assertEqual(len(self.calls), 1)

    def test_terminal_403_and_429_never_resume(self):
        for code in (403, 429):
            with self.subTest(code=code), self.assertRaises(RelayError):
                self.response = Response(b'{"message":"fixture"}', code)
                with self.relay() as relay:
                    self.prepare(relay)
                    result = self.request(relay)
                    self.assertIn(str(code).encode(), result)
                    self.assertEqual(relay.terminal_reason, "HTTP rate refusal")
                    count = len(self.calls)
                    with self.assertRaises(RelayError):
                        relay.check()
                    self.assertEqual(len(self.calls), count)

    def test_unknown_method_host_path_query_and_body_refuse(self):
        cases = [
            dict(method="CONNECT"),
            dict(host="other.invalid"),
            dict(path=API + "/issues"),
            dict(path=API + "?arbitrary=1"),
            dict(body=b"unexpected"),
            dict(path=API + "/../example"),
            dict(path=API + "/%2e%2e"),
            dict(host="api.github.com:443"),
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(RelayError):
                with self.relay() as relay:
                    self.prepare(relay)
                    before = len(self.calls)
                    self.request(relay, **case)
                    self.assertEqual(len(self.calls), before)

    def test_duplicate_or_hostile_headers_refuse(self):
        for extra in (
            b"Host: api.github.com\r\n",
            b"Cookie: fixture\r\n",
            b"Transfer-Encoding: chunked\r\n",
            b" X-Fixture: yes\r\n",
        ):
            with self.subTest(extra=extra), self.assertRaises(RelayError):
                with self.relay() as relay:
                    self.prepare(relay)
                    self.request(relay, extra=extra)
        self.assertEqual(self.calls, [])

    def test_credential_substitution_and_external_credential_refuse(self):
        with self.assertRaises(RelayError):
            with self.relay() as relay:
                self.prepare(relay)
                relay.environment({"GH_TOKEN": "different-fictional-token"})
        with self.assertRaises(RelayError):
            with self.relay() as relay:
                self.prepare(relay)
                self.request(
                    relay,
                    host="tuf-repo.github.com",
                    path="/4.root.json",
                    extra=b"Authorization: token fictional-token\r\n",
                )
        self.assertEqual(self.calls, [])

    def test_request_limit_is_atomic(self):
        with self.assertRaises(RelayError):
            with self.relay(max_requests=1) as relay:
                self.prepare(relay)
                self.request(relay)
                self.request(relay)
        self.assertEqual(len(self.calls), 1)

    def test_accounting_and_supervisor_failures_are_terminal(self):
        def refused(_):
            raise RuntimeError("untrusted detail must not escape")

        with self.assertRaises(RelayError):
            with self.relay() as relay:
                relay._account = refused
                relay._on_terminal = refused
                self.prepare(relay)
                self.request(relay)
                self.assertEqual(
                    relay.terminal_reason, "supervisor notification failed"
                )
        self.assertEqual(self.calls, [])

    def test_missing_or_changed_config_and_socket_refuse(self):
        for what in ("config", "socket", "mode", "extra"):
            with self.subTest(what=what), self.assertRaises(RelayError):
                with self.relay() as relay:
                    self.prepare(relay)
                    if what == "config":
                        (relay.config_directory / "config.yml").write_text(
                            "http_unix_socket: wrong\n"
                        )
                    elif what == "socket":
                        relay.socket_path.unlink()
                    elif what == "mode":
                        os.chmod(relay.config_directory / "config.yml", 0o644)
                    else:
                        (relay.config_directory / "hosts.yml").write_text("fictional")
                    relay.check()
        self.assertEqual(self.calls, [])

    def test_symlink_replacement_cannot_read_or_delete_target(self):
        target = self.parent / "not-owned"
        target.write_text("preserve fictional data")
        with self.assertRaises(RelayError):
            with self.relay() as relay:
                self.prepare(relay)
                config = relay.config_directory / "config.yml"
                config.unlink()
                config.symlink_to(target)
                relay.check()
        self.assertEqual(target.read_text(), "preserve fictional data")

    def test_no_traffic_cannot_accept_direct_fallback(self):
        with self.assertRaisesRegex(RelayError, "missing or incomplete relay traffic"):
            with self.relay() as relay:
                self.prepare(relay)
                relay.finish()

    def test_unsafe_environment_refuses_without_network(self):
        for key in (
            "HTTPS_PROXY",
            "SSL_CERT_FILE",
            "SSLKEYLOGFILE",
            "GH_DEBUG",
            "GH_CONFIG_DIR",
        ):
            with self.subTest(key=key), self.assertRaises(RelayError):
                with self.relay() as relay:
                    relay.environment({"GH_TOKEN": "fictional-token", key: "untrusted"})
        self.assertEqual(self.calls, [])

    def test_tls_failure_is_not_a_successful_response(self):
        self.connection_error = ssl.SSLCertVerificationError("fictional wrong identity")
        with self.assertRaises(RelayError):
            with self.relay() as relay:
                self.prepare(relay)
                self.request(relay)
        self.assertFalse(self.events[-1].complete)
        self.assertIsNone(self.events[-1].status)

    def test_missing_quota_unknown_status_and_body_limit_refuse(self):
        cases = [Response(), Response(status=201), Response(b"x" * 100)]
        cases[0].headers = [("Content-Length", "2")]
        for response in cases:
            with self.subTest(status=response.status), self.assertRaises(RelayError):
                self.response = response
                with self.relay(max_response_bytes=30) as relay:
                    self.prepare(relay)
                    self.request(relay)

    def test_attestation_discovery_does_not_enable_foreign_blob(self):
        path = (
            API
            + "/attestations/sha1:"
            + "a" * 40
            + "?per_page=100&predicate_type=release"
        )
        url = "https://tmaproduction.blob.core.windows.net/attestations/123/2026/01/01/1.json.sn"
        self.response = Response(
            json.dumps({"attestations": [{"bundle_url": url}]}).encode()
        )
        with self.relay() as relay:
            self.prepare(relay)
            self.request(relay, path)
            self.response = Response(b"fictional signed bytes")
            self.response.headers = [
                ("Content-Length", "22"),
                ("Content-Type", "application/octet-stream"),
            ]
            result = self.request(
                relay,
                host="tmaproduction.blob.core.windows.net",
                path="/attestations/123/2026/01/01/1.json.sn",
            )
            self.assertTrue(result.endswith(b"fictional signed bytes"))
        with self.assertRaises(RelayError):
            with self.relay() as relay:
                self.prepare(relay)
                self.request(
                    relay,
                    host="tmaproduction.blob.core.windows.net",
                    path="/attestations/124/2026/01/01/1.json.sn",
                )

    def test_redirect_is_not_followed_and_each_leg_is_charged(self):
        destination = "https://release-assets.githubusercontent.com/github-production-release-asset/123/12345678-1234-1234-1234-123456789abc?sig=fictional"
        self.response = Response(b"", 302, [("Location", destination)])
        with self.relay() as relay:
            self.prepare(relay)
            result = self.request(relay, API + "/releases/assets/101")
            self.assertIn(b"302", result)
            self.assertEqual(len(self.calls), 1)
            self.response = Response(b"1234567890123456")
            self.response.headers = [("Content-Length", "16")]
            self.request(
                relay,
                host="release-assets.githubusercontent.com",
                path=destination.split(".com", 1)[1],
            )
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(
            [e.bucket for e in self.events if e.phase == "request"], ["rest", "blob"]
        )
        self.assertNotIn("sig=", repr(self.events))

    def test_hostile_redirect_and_page_overrun_refuse(self):
        for location in (
            "http://release-assets.githubusercontent.com/bad",
            "https://other.invalid/a",
            "https://user:secret@release-assets.githubusercontent.com/a",
        ):
            with self.subTest(location=location), self.assertRaises(RelayError):
                self.response = Response(b"", 302, [("Location", location)])
                with self.relay() as relay:
                    self.prepare(relay)
                    self.request(relay, API + "/releases/assets/101")
        with self.assertRaises(RelayError):
            with self.relay(max_pages=1) as relay:
                self.prepare(relay)
                self.request(
                    relay,
                    API
                    + "/attestations/sha1:"
                    + "a" * 40
                    + "?per_page=100&predicate_type=release&page=2",
                )

    def test_graphql_has_exact_body_and_no_invented_point_cost(self):
        query = "query RepositoryReleaseByTag($name:String!,$owner:String!,$tagName:String!){repository(owner:$owner,name:$name){release(tagName:$tagName){databaseId,isDraft}}}"
        body = json.dumps(
            {
                "query": query,
                "variables": {
                    "owner": "fictional",
                    "name": "example",
                    "tagName": "fixture-v1",
                },
            }
        ).encode()
        self.response = Response(
            b'{"data":{"repository":{"release":{"databaseId":77,"isDraft":false}}}}'
        )
        self.response.headers = [
            (k, "graphql" if k == "X-RateLimit-Resource" else v)
            for k, v in self.response.headers
        ]
        with self.relay() as relay:
            self.prepare(relay)
            self.request(relay, "/graphql", method="POST", body=body)
        self.assertEqual(self.events[-1].quota.resource, "graphql")
        self.assertIsNone(self.events[-1].quota.graphql_cost)
        with self.assertRaises(RelayError):
            with self.relay() as relay:
                self.prepare(relay)
                self.request(
                    relay, "/graphql", method="POST", body=b'{"query":"mutation{}"}'
                )

    def test_graphql_http_200_error_or_incomplete_data_refuses(self):
        query = "query RepositoryReleaseByTag($name:String!,$owner:String!,$tagName:String!){repository(owner:$owner,name:$name){release(tagName:$tagName){databaseId,isDraft}}}"
        body = json.dumps(
            {
                "query": query,
                "variables": {
                    "owner": "fictional",
                    "name": "example",
                    "tagName": "fixture-v1",
                },
            }
        ).encode()
        for document in (
            {"errors": [{"type": "RATE_LIMITED"}]},
            {"data": None},
            {"data": {"repository": {"release": None}}},
        ):
            self.response = Response(json.dumps(document).encode())
            self.response.headers = [
                (k, "graphql" if k == "X-RateLimit-Resource" else v)
                for k, v in self.response.headers
            ]
            with self.assertRaises(RelayError):
                with self.relay() as relay:
                    self.prepare(relay)
                    self.request(relay, "/graphql", method="POST", body=body)
            self.assertFalse(self.events[-1].complete)

    def test_frozen_factory_uses_existing_validated_coordinates(self):
        policy = frozen_release_policy()
        self.assertEqual(policy.repository, "samovers/OFARM2")
        self.assertEqual(policy.repository_id, 1266697770)
        self.assertEqual(policy.release_id, 356509551)
        self.assertEqual([a[0] for a in policy.assets], [483077818, 483078228])

    def test_concurrent_requests_have_distinct_complete_identities(self):
        self.response = lambda: Response(b'{"fixture":true}')
        with self.relay() as relay:
            self.prepare(relay)
            workers = [
                threading.Thread(target=self.request, args=(relay,)) for _ in range(4)
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(2)
                self.assertFalse(worker.is_alive())
            self.assertEqual(relay.finish().requests, 4)
        for request_id in range(1, 5):
            events = [e for e in self.events if e.request_id == request_id]
            self.assertEqual(
                [e.phase for e in events], ["request", "response", "completed"]
            )
            self.assertTrue(events[-1].complete)

    def test_concurrency_limit_is_terminal_even_without_forwarded_request(self):
        with self.assertRaisesRegex(RelayError, "concurrency limit"):
            with self.relay(max_connections=1) as relay:
                self.prepare(relay)
                first = socket.socket(socket.AF_UNIX)
                second = socket.socket(socket.AF_UNIX)
                try:
                    first.connect(str(relay.socket_path))
                    deadline = time.monotonic() + 1
                    while not relay._active and time.monotonic() < deadline:
                        time.sleep(0.005)
                    second.connect(str(relay.socket_path))
                    second.settimeout(1)
                    self.assertEqual(second.recv(1), b"")
                finally:
                    first.close()
                    second.close()
        self.assertEqual(self.calls, [])

    def test_incomplete_response_is_recorded_and_never_accepted(self):
        self.response.headers[0] = ("Content-Length", "30")
        with self.assertRaisesRegex(RelayError, "incomplete response body"):
            with self.relay() as relay:
                self.prepare(relay)
                self.request(relay)
        self.assertEqual(self.events[-1].status, 200)
        self.assertEqual(self.events[-1].response_bytes, 2)
        self.assertFalse(self.events[-1].complete)

    def test_lifetime_and_cleanup_failure_are_terminal(self):
        with self.assertRaisesRegex(RelayError, "relay deadline"):
            with self.relay(lifetime_seconds=0.01) as relay:
                self.prepare(relay)
                time.sleep(0.03)
                relay.check()
        with self.assertRaisesRegex(RelayError, "relay cleanup failed"):
            with self.relay() as relay:
                self.prepare(relay)
                self.request(relay)
                with patch(
                    "conformance.ci_policy_transition_gh_relay.shutil.rmtree",
                    side_effect=OSError,
                ):
                    relay.__exit__(None, None, None)

    def test_response_status_header_and_json_ambiguity_refuse(self):
        variants = []
        response = Response()
        response.reason = "OK\r\nInjected: yes"
        variants.append(response)
        response = Response(headers=[("Content-Length", "2")])
        variants.append(response)
        response = Response(headers=[("X-RateLimit-Remaining", "899")])
        variants.append(response)
        variants.append(Response(b'{"fixture":true,"fixture":false}'))
        for response in variants:
            with self.subTest(), self.assertRaises(RelayError):
                self.response = response
                with self.relay() as relay:
                    self.prepare(relay)
                    self.request(relay)

    def test_completed_callback_failure_refuses_and_joins(self):
        with self.assertRaisesRegex(RelayError, "accounting refused"):
            with self.relay() as relay:

                def account(event):
                    if event.phase == "completed":
                        raise ValueError("fictional failure")
                    self.events.append(event)

                relay._account = account
                self.prepare(relay)
                self.request(relay)
        self.assertTrue(all(not worker.is_alive() for worker in relay._workers))

    def test_receive_time_framing_limit_and_setup_cleanup(self):
        stream = _BoundedLines(io.BytesIO(b"1234\r\n5678\r\n"), 8)
        self.assertEqual(stream.readline(), b"1234\r\n")
        with self.assertRaisesRegex(RelayError, "framing limit"):
            stream.readline()
        before = set(self.parent.iterdir())
        with patch(
            "conformance.ci_policy_transition_gh_relay.os.fsync", side_effect=OSError
        ):
            with self.assertRaisesRegex(RelayError, "relay setup failed"):
                self.relay().__enter__()
        self.assertEqual(set(self.parent.iterdir()), before)

    def test_known_complete_tuf_404_survives_downstream_close(self):
        self.response = Response(b"fictional missing next root", 404)
        with self.relay() as relay:
            self.prepare(relay)
            sock = socket.socket(socket.AF_UNIX)
            sock.connect(str(relay.socket_path))
            sock.sendall(
                b"GET /10.root.json HTTP/1.1\r\nHost: tuf-repo.github.com\r\n\r\n"
            )
            sock.close()
            deadline = time.monotonic() + 1
            while not relay._completed and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertEqual(relay.finish().requests, 1)
        self.assertEqual(self.events[-1].status, 404)
        self.assertTrue(self.events[-1].complete)

    def test_fixed_gh_headers_cannot_expand_authority(self):
        for extra in (
            b"GraphQL-Features: mutation\r\n",
            b"Referer: https://evil.example/\r\n",
        ):
            with self.subTest(), self.assertRaises(RelayError):
                with self.relay() as relay:
                    self.prepare(relay)
                    self.request(relay, extra=extra)


if __name__ == "__main__":
    unittest.main()
