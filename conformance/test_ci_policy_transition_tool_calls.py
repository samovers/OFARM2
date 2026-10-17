"""Offline HTTPS tracing of actual pinned CI tools, never hosted evidence.

Run this file with --bundle-directory pointing at authenticated downloaded tool
bundles. No real credential is read or transmitted. The TLS peer is a fresh
loopback fixture, while the unmodified Action executes its real request/retry
and artifact ZIP paths. Traces report bucket origins separately; an Actions
runtime-token request is not a GITHUB_TOKEN REST/GraphQL observation.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
import unittest
import urllib.parse
import zipfile


UPLOAD_COMMIT = "b7c566a772e6b6bfb58ed0dc250532a479d7789f"
UPLOAD_BUNDLE_SHA256 = "0ab64518113c41b9bcb26c5e64310d67c8e41ff2dc4f0971a498447d8e626679"
UPLOAD_SOURCE = f"https://raw.githubusercontent.com/actions/upload-artifact/{UPLOAD_COMMIT}/dist/upload/index.js"
_PAYLOAD = b"fictional complete artifact data\n"
# Diagnostic only: this is never emitted into the generated workflows. The
# experiment checks whether an outer Node transport observer can stop retries
# while the exact pinned Action bundle remains unchanged.
_OBSERVER = """import http from 'node:http';
import https from 'node:https';
for (const transport of [http, https]) {
  const request = transport.request;
  transport.request = function (...args) {
    const pending = Reflect.apply(request, this, args);
    pending.prependOnceListener('response', response => {
      if (response.statusCode === 403 || response.statusCode === 429) {
        process.stderr.write('terminal-observer-refusal:' + response.statusCode + '\\n');
        process.exit(86);
      }
    });
    return pending;
  };
}
"""


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _fake_runtime_token() -> str:
    def encode(value: dict) -> str:
        return base64.urlsafe_b64encode(_json(value)).rstrip(b"=").decode()
    return ".".join((encode({"alg": "none"}), encode({
        "scp": "Actions.Results:11111111-1111-4111-8111-111111111111:22222222-2222-4222-8222-222222222222",
    }), "fictional-signature"))


class _Fixture(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, certificate: Path, key: Path, first_status: int):
        super().__init__(("127.0.0.1", 0), _Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, key)
        self.socket = context.wrap_socket(self.socket, server_side=True)
        self.first_status = first_status
        self.calls: list[dict] = []
        self.blocks: dict[str, bytes] = {}
        self.archive: bytes | None = None
        self.finalized: dict | None = None
        self.errors: list[str] = []

    @property
    def origin(self) -> str:
        return f"https://127.0.0.1:{self.server_port}"


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:
        return

    def _body(self) -> bytes:
        if self.headers.get("Transfer-Encoding") == "chunked":
            result = bytearray()
            while True:
                size = int(self.rfile.readline().strip().split(b";")[0], 16)
                if size == 0:
                    if self.rfile.readline() != b"\r\n":
                        raise ValueError("unexpected chunk trailers")
                    return bytes(result)
                result.extend(self.rfile.read(size))
                if self.rfile.read(2) != b"\r\n":
                    raise ValueError("malformed chunk")
        return self.rfile.read(int(self.headers.get("Content-Length", "0")))

    def _reply(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("x-ms-request-id", "33333333-3333-4333-8333-333333333333")
        self.send_header("x-ms-version", "2025-01-05")
        self.send_header("ETag", '"fictional-etag"')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        server = self.server
        body = json.loads(self._body())
        action = self.path.rsplit("/", 1)[-1]
        status = server.first_status if action == "CreateArtifact" and not server.calls else 200
        server.calls.append({"method": "POST", "path": self.path, "status": status,
                             "bucket": "actions-runtime-token", "body": body})
        if self.headers.get("Authorization") != "Bearer " + _fake_runtime_token():
            server.errors.append("runtime credential differs from fictional fixture token")
            self._reply(401, _json({"msg": "fixture authentication refused"}))
        elif status != 200:
            self._reply(status, _json({"msg": "fictional rate-limit or permission refusal"}))
        elif action == "CreateArtifact":
            self._reply(200, _json({"ok": True, "signedUploadUrl": (
                server.origin + "/fixture-account/fixture-container/fixture-artifact?sig=fictional"
            )}))
        elif action == "FinalizeArtifact":
            server.finalized = body
            if server.archive is None:
                server.errors.append("finalized before a complete uploaded archive")
            self._reply(200, _json({"ok": True, "artifactId": "42"}))
        else:
            server.errors.append("unexpected runtime API call")
            self._reply(400, _json({"msg": "unexpected call"}))

    def do_PUT(self) -> None:
        server = self.server
        body = self._body()
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        server.calls.append({"method": "PUT", "path": self.path, "status": 201,
                             "bucket": "artifact-blob-storage", "bytes": len(body)})
        if query.get("comp") == ["block"] and len(query.get("blockid", [])) == 1:
            server.blocks[query["blockid"][0]] = body
        elif query.get("comp") == ["blocklist"]:
            from xml.etree import ElementTree
            block_ids = [element.text for element in ElementTree.fromstring(body)]
            if set(block_ids) != set(server.blocks) or len(block_ids) != len(server.blocks):
                server.errors.append("uploaded block list is incomplete")
            server.archive = b"".join(server.blocks[key] for key in block_ids)
        else:
            server.errors.append("unexpected blob operation")
        self._reply(201, b"", "application/xml")


@contextmanager
def _fixture(directory: Path, first_status: int):
    certificate, key = directory / "cert.pem", directory / "key.pem"
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(key), "-out", str(certificate), "-days", "2",
        "-subj", "/CN=localhost", "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost",
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    server = _Fixture(certificate, key, first_status)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, certificate
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def trace_upload(bundle: Path, node: str, *, first_status: int,
                 observer: bool = False) -> dict:
    """Execute the exact Action bundle against complete fictional HTTPS responses."""
    if hashlib.sha256(bundle.read_bytes()).hexdigest() != UPLOAD_BUNDLE_SHA256:
        raise ValueError("upload Action bundle differs from the pinned source")
    if first_status not in (200, 403, 429):
        raise ValueError("unsupported fixture response")
    with tempfile.TemporaryDirectory(prefix="ofarm-tool-calls-") as temporary:
        root = Path(temporary)
        data = root / "fixture.txt"
        data.write_bytes(_PAYLOAD)
        output = root / "outputs"
        output.touch()
        with _fixture(root, first_status) as (server, certificate):
            # Build an isolated environment. No caller credential, network
            # proxy, Node preload, or user Action setting is inherited.
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "NODE_EXTRA_CA_CERTS": str(certificate),
                "ACTIONS_RUNTIME_TOKEN": _fake_runtime_token(),
                "ACTIONS_RESULTS_URL": server.origin,
                "GITHUB_SERVER_URL": "https://github.com",
                "GITHUB_REPOSITORY": "fictional/example",
                "GITHUB_RUN_ID": "41",
                "GITHUB_WORKSPACE": str(root),
                "GITHUB_OUTPUT": str(output),
                "RUNNER_TEMP": str(root),
                "INPUT_NAME": "fictional-trace-artifact",
                "INPUT_PATH": str(data),
                "INPUT_IF-NO-FILES-FOUND": "error",
                "INPUT_RETENTION-DAYS": "14",
                "INPUT_COMPRESSION-LEVEL": "6",
                "INPUT_OVERWRITE": "false",
                "INPUT_INCLUDE-HIDDEN-FILES": "true",
                "NO_PROXY": "127.0.0.1,localhost",
            }
            if observer:
                encoded = base64.b64encode(_OBSERVER.encode()).decode()
                env["NODE_OPTIONS"] = "--import=data:text/javascript;base64," + encoded
            result = subprocess.run([node, str(bundle)], env=env, cwd=root,
                                    capture_output=True, text=True, timeout=45)
        if server.errors:
            raise AssertionError(server.errors)
        complete = False
        if result.returncode == 0:
            if server.archive is None or server.finalized is None:
                raise AssertionError("successful Action did not complete an artifact")
            with zipfile.ZipFile(io.BytesIO(server.archive)) as archive:
                if archive.namelist() != ["fixture.txt"] or archive.read("fixture.txt") != _PAYLOAD:
                    raise AssertionError("actual uploaded archive differs from complete fixture data")
            finalized_digest = server.finalized.get("hash")
            expected_digest = "sha256:" + hashlib.sha256(server.archive).hexdigest()
            if finalized_digest != expected_digest or int(server.finalized["size"]) != len(server.archive):
                raise AssertionError("actual Action finalized inconsistent archive bytes")
            if "artifact-id" not in output.read_text() or "42" not in output.read_text():
                raise AssertionError("successful Action omitted artifact output identity")
            complete = True
        return {
            "tool": "actions/upload-artifact", "commit": UPLOAD_COMMIT,
            "bundleSha256": UPLOAD_BUNDLE_SHA256, "source": UPLOAD_SOURCE,
            "node": subprocess.check_output([node, "--version"], text=True).strip(),
            "firstStatus": first_status, "exitCode": result.returncode,
            "diagnosticObserver": observer,
            "observerSha256": hashlib.sha256(_OBSERVER.encode()).hexdigest() if observer else None,
            "completeArtifact": complete, "calls": server.calls,
            "diagnostics": [line for line in (result.stdout + result.stderr).splitlines()
                            if line.startswith(("::error::", "Attempt ", "terminal-observer-refusal:"))],
            "restRequests": 0, "graphqlPoints": 0,
            "runtimeRequests": sum(call["bucket"] == "actions-runtime-token" for call in server.calls),
            "blobRequests": sum(call["bucket"] == "artifact-blob-storage" for call in server.calls),
            "g25RateLimitRefusal": first_status != 429 or not complete,
        }


class ToolTraceHarnessTests(unittest.TestCase):
    def test_wrong_bundle_refuses_before_execution_or_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "upload.js"
            path.write_text("throw new Error('must never execute');\n")
            with self.assertRaisesRegex(ValueError, "differs from the pinned source"):
                trace_upload(path, "must-not-execute", first_status=200)

    def test_fixture_runtime_identity_is_explicitly_fictional(self) -> None:
        payload = _fake_runtime_token().split(".")[1]
        document = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        self.assertEqual(document["scp"].split(":")[0], "Actions.Results")
        self.assertTrue(_fake_runtime_token().endswith(".fictional-signature"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-directory", type=Path, required=True)
    parser.add_argument("--node", default="node")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-observer", action="store_true",
                        help="isolated correction experiment; never production behavior")
    args = parser.parse_args(argv)
    reports = [trace_upload(args.bundle_directory / "upload.js", args.node, first_status=status,
                            observer=args.diagnostic_observer)
               for status in (200, 403, 429)]
    result = {"schemaVersion": "ofarm.ci-policy-transition-tool-trace.v1", "hostedEvidence": False,
              "scope": "actual pinned upload Action; other Actions/CLI not established by this trace",
              "traces": reports, "positiveFixtureComplete": reports[0]["completeArtifact"],
              "completeG25Established": False,
              "testedRateLimitRuleSatisfied": reports[0]["completeArtifact"] and all(
                  report["g25RateLimitRefusal"] for report in reports)}
    args.output.write_bytes(_json(result) + b"\n")
    print(json.dumps({"report": str(args.output), "completeG25Established": False,
                      "testedRateLimitRuleSatisfied": result["testedRateLimitRuleSatisfied"],
                      "traces": [{key: report[key] for key in (
                          "firstStatus", "exitCode", "completeArtifact", "runtimeRequests", "blobRequests",
                      )} for report in reports]}, sort_keys=True))
    return 0 if result["testedRateLimitRuleSatisfied"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
