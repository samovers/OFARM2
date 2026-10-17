"""Real curl against a fictional local TLS release redirect; no provider reads."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import pytest
from conformance import ci_policy_transition_curl as curl


@contextmanager
def fixture(status=200, truncated=False):
    with tempfile.TemporaryDirectory(prefix="of-curl-", dir="/tmp") as temp:
        root = Path(temp).resolve()
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=github.com",
                "-addext",
                "subjectAltName=DNS:github.com,DNS:release-assets.githubusercontent.com",
                "-keyout",
                str(root / "key.pem"),
                "-out",
                str(root / "cert.pem"),
            ],
            check=True,
            capture_output=True,
        )
        calls = []

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                calls.append((self.headers["Host"], self.path))
                if len(calls) == 1:
                    self.send_response(302)
                    self.send_header(
                        "Location",
                        "https://release-assets.githubusercontent.com/github-production-release-asset/fixture?sig=DO-NOT-RETAIN",
                    )
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                else:
                    self.send_response(status)
                    self.send_header("Content-Length", "20" if truncated else "7")
                    self.send_header("Set-Cookie", "one=1")
                    self.send_header("Set-Cookie", "two=2")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(b"payload")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(root / "cert.pem", root / "key.pem")
        server.socket = context.wrap_socket(server.socket, server_side=True)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield root, server.server_port, calls
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)


def run(root, port, status=200, *, tamper=False, name="gh-amd64"):
    frames, failures = [], []

    def observe(frame):
        frames.append(frame)
        if frame["operation"] == "response" and frame["status"] in (403, 429):
            return {"accepted": False}
        return {"accepted": True, "sequence": frame["sequence"]}

    lifecycle = curl.CurlLifecycle(root, name, observe, failures.append)
    environment = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    environment.update(lifecycle.start())
    if tamper:
        (lifecycle.directory / ".curlrc").write_text("")
    command = command_for(root, port, name=name)
    result = subprocess.run(command, env=environment, capture_output=True, timeout=10)
    return lifecycle, frames, failures, result


def command_for(root, port, *, name="gh-amd64"):
    return [
        shutil.which("curl"),
        "--fail",
        "--location",
        "--proto",
        "=https",
        "--tlsv1.2",
        "--retry",
        "0",
        "--silent",
        "--show-error",
        "--cacert",
        str(root / "cert.pem"),
        "--connect-to",
        f"github.com:443:127.0.0.1:{port}",
        "--connect-to",
        f"release-assets.githubusercontent.com:443:127.0.0.1:{port}",
        "--output",
        str(root / "download"),
        curl.URLS[name],
    ]


def test_actual_curl_redirect_status_bytes_and_cleanup():
    with fixture() as (root, port, calls):
        lifecycle, frames, failures, result = run(root, port)
        assert result.returncode == 0, result.stderr
        lifecycle.finish()
        assert len(calls) == 2
        assert [f["status"] for f in frames if f["operation"] == "response"] == [
            302,
            200,
        ]
        assert [
            (f["bytes"], f["complete"]) for f in frames if f["operation"] == "end"
        ] == [(0, True), (7, True)]
        assert not failures and not lifecycle.directory.exists()
        assert "DO-NOT-RETAIN" not in repr(frames)


@pytest.mark.parametrize("status", [403, 429])
def test_actual_curl_first_refusal_is_incomplete_and_cleanup(status):
    with fixture(status=status) as (root, port, calls):
        lifecycle, frames, failures, result = run(root, port)
        assert result.returncode != 0
        with pytest.raises(curl.CurlError):
            lifecycle.finish()
        assert failures and not lifecycle.directory.exists()
        assert [f["complete"] for f in frames if f["operation"] == "end"] == [
            True,
            False,
        ]
        assert len(calls) == 2


def test_actual_curl_truncated_body_cannot_succeed():
    with fixture(truncated=True) as (root, port, calls):
        lifecycle, frames, failures, result = run(root, port)
        assert result.returncode != 0
        with pytest.raises(curl.CurlError):
            lifecycle.finish()
        assert failures and not lifecycle.directory.exists()
        assert frames[-1]["operation"] == "end" and not frames[-1]["complete"]
        assert frames[-1]["bytes"] == 7


def test_real_daemon_owns_curl_observer_and_counts_redirect_legs():
    from conformance.test_ci_policy_transition_tools import _running_supervisor
    from conformance import ci_policy_transition_tools as tools

    with (
        fixture() as (root, port, calls),
        _running_supervisor() as (control, config, environment),
    ):
        base = {"schema": 1, "nonce": config["nonce"]}
        selected = tools._exchange(
            control, {**base, "operation": "curl-start", "name": "gh-amd64"}
        )
        result = subprocess.run(
            command_for(root, port),
            env={**environment, **selected["environment"]},
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        tools._exchange(control, {**base, "operation": "curl-finish"})
        tools._exchange(control, {**base, "operation": "check"})
        ledger = tools.decode(tools.private_file(control / "ledger.json"))
        assert ledger["transport"] == {"requests": 2, "bytes": 7}
        assert not ledger["used"] and not ledger["failed"]
        assert not (control / "curl-gh-amd64").exists()
