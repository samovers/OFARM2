"""T-owned, bounded transport for the unchanged pinned GitHub CLI.

Only ``frozen_release_policy`` is used by workflow integration. A policy is
trusted code, never a document supplied by a producer. This module does not
wrap gh, inspect its output, create credentials, follow redirects, or decide
publication authority. The owning supervisor must terminate its children on
``on_terminal`` and accept only after ``finish`` and successful context exit.
"""
from __future__ import annotations

from dataclasses import dataclass
import gzip
import hmac
import http.client
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import stat
import tempfile
import threading
import time
from typing import Callable, Literal, Mapping
from urllib.parse import parse_qsl, urlsplit


class RelayError(RuntimeError):
    """A fixed, non-sensitive terminal reason; never includes provider data."""


@dataclass(frozen=True)
class QuotaFacts:
    resource: str
    limit: int
    remaining: int
    reset: int
    used: int
    graphql_cost: int | None = None


@dataclass(frozen=True)
class RelayEvent:
    phase: Literal["request", "response", "completed"]
    request_id: int
    bucket: Literal["rest", "graphql", "tuf", "blob"]
    method: str
    host: str
    path: str
    status: int | None = None
    request_bytes: int = 0
    response_bytes: int = 0
    quota: QuotaFacts | None = None
    complete: bool = False


@dataclass(frozen=True)
class RelayLimits:
    max_requests: int
    max_response_bytes: int
    lifetime_seconds: float
    max_connections: int = 4
    max_header_bytes: int = 32768
    max_request_bytes: int = 8192
    max_metadata_bytes: int = 2 * 1024 * 1024
    io_timeout_seconds: float = 10
    drain_seconds: float = 15
    max_pages: int = 8

    def __post_init__(self) -> None:
        integers = (self.max_requests, self.max_response_bytes, self.max_connections,
                    self.max_header_bytes, self.max_request_bytes,
                    self.max_metadata_bytes, self.max_pages)
        if any(type(v) is not int or v <= 0 for v in integers):
            raise RelayError("invalid relay limits")
        if (self.max_requests > 1000 or self.max_connections > 16
                or self.max_header_bytes > 65536 or self.max_request_bytes > 65536
                or self.max_metadata_bytes > 8 * 1024 * 1024 or self.max_pages > 100
                or self.max_response_bytes > 8 * 1024 ** 3):
            raise RelayError("invalid relay limits")
        if not (0 < self.io_timeout_seconds <= self.drain_seconds <= 60
                and 0 < self.lifetime_seconds <= 7200):
            raise RelayError("invalid relay limits")


@dataclass(frozen=True)
class FrozenReleasePolicy:
    repository: str
    repository_id: int
    tag: str
    tag_sha: str
    release_id: int
    # Exact (provider asset id, byte size) pairs from the frozen receipt.
    assets: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if (not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", self.repository)
                or type(self.repository_id) is not int or self.repository_id <= 0
                or not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", self.tag)
                or not re.fullmatch(r"[0-9a-f]{40}", self.tag_sha)
                or type(self.release_id) is not int or self.release_id <= 0
                or len(self.assets) != 2 or len({a[0] for a in self.assets}) != 2
                or any(type(i) is not int or type(n) is not int or i <= 0 or n <= 0
                       for i, n in self.assets)):
            raise RelayError("invalid frozen release policy")


def frozen_release_policy(*, identity_module=None) -> FrozenReleasePolicy:
    """Derive coordinates through the existing frozen native validators."""
    if identity_module is None:
        from deployment.postgresql import native_release_identity as identity_module
    identity = identity_module.load_native_release_identity()
    receipt = identity_module.load_native_evidence_receipt(release_identity=identity)
    if receipt.status != "frozen":
        raise RelayError("native receipt is not frozen")
    metadata = receipt.document["preservation"]["providerVerification"]["metadata"]
    repository, release = metadata["repository"], metadata["release"]
    return FrozenReleasePolicy(repository["name"], repository["id"], release["tagName"],
                               release["peeledTagCommit"], release["id"],
                               tuple((a["id"], a["size"]) for a in release["assets"]))


@dataclass(frozen=True)
class RelaySummary:
    requests: int
    response_bytes: int


_UNSAFE_ENV = frozenset({
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "SSLKEYLOGFILE", "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE", "GIT_SSL_CAINFO", "GIT_SSL_CAPATH", "GH_DEBUG", "DEBUG",
    "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_FORCE_TTY",
})
_REQUEST_HEADERS = frozenset({
    "host", "authorization", "accept", "accept-encoding", "content-type",
    "content-length", "user-agent", "x-github-api-version", "connection", "time-zone",
    "graphql-features", "referer",
})
_HOP_HEADERS = frozenset({"connection", "keep-alive", "transfer-encoding", "trailer"})
_SIGNED_QUERY_KEYS = frozenset({
    "sp", "sv", "sr", "spr", "se", "st", "skoid", "sktid", "skt", "ske", "sks",
    "skv", "sig", "jwt", "rscd", "rsct", "response-content-disposition",
    "response-content-type",
})
_GQL = ("queryRepositoryReleaseByTag($name:String!$owner:String!$tagName:String!)"
        "{repository(owner:$ownername:$name){release(tagName:$tagName){databaseIdisDraft}}}")


def _json(data: bytes) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise RelayError("ambiguous response metadata")
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        raise RelayError("invalid response metadata") from None


def _same_file(path: Path, expected: os.stat_result, mode: int, kind: str) -> bool:
    try:
        observed = path.lstat()
        return (observed.st_dev, observed.st_ino, observed.st_uid,
                stat.S_IMODE(observed.st_mode)) == (
                    expected.st_dev, expected.st_ino, os.getuid(), mode) and (
                        stat.S_ISDIR(observed.st_mode) if kind == "directory" else
                        stat.S_ISSOCK(observed.st_mode) if kind == "socket" else
                        stat.S_ISREG(observed.st_mode))
    except OSError:
        return False


class _BoundedLines:
    """Bound status/header/chunk-framing lines while http.client reads them."""
    def __init__(self, stream: object, maximum: int) -> None:
        self._stream, self._remaining = stream, maximum

    def readline(self, size: int = -1) -> bytes:
        size = min(size, self._remaining + 1) if size >= 0 else self._remaining + 1
        line = self._stream.readline(size)
        self._remaining -= len(line)
        if self._remaining < 0:
            raise RelayError("response framing limit")
        return line

    def __getattr__(self, name: str) -> object:
        return getattr(self._stream, name)


class _BoundedResponse(http.client.HTTPResponse):
    def __init__(self, *args: object, line_limit: int, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fp = _BoundedLines(self.fp, line_limit)


class GhRelay:
    def __init__(self, work_directory: Path, policy: FrozenReleasePolicy,
                 limits: RelayLimits, account: Callable[[RelayEvent], None],
                 on_terminal: Callable[[str], None]) -> None:
        self.work_directory, self.policy, self.limits = work_directory, policy, limits
        self._account, self._on_terminal = account, on_terminal
        self._lock = threading.RLock()
        self._terminal: str | None = None
        self._closed = False
        self._finishing = False
        self._started = False
        self._credential: str | None = None
        self._active: set[socket.socket] = set()
        self._upstream: set[http.client.HTTPSConnection] = set()
        self._workers: list[threading.Thread] = []
        self._requests = 0
        self._completed = 0
        self._response_bytes = 0
        self._expected_urls: dict[str, tuple[str, int]] = {}
        self._server_stop = threading.Event()
        self._slots = threading.BoundedSemaphore(limits.max_connections)

    @property
    def terminal_reason(self) -> str | None:
        with self._lock:
            return self._terminal

    def _fail(self, reason: str) -> None:
        with self._lock:
            first = self._terminal is None
            if first:
                self._terminal = reason
        if first:
            try:
                self._on_terminal(reason)
            except BaseException:
                # Failure notification never removes the permanent latch.
                with self._lock:
                    self._terminal = "supervisor notification failed"

    def __enter__(self) -> GhRelay:
        try:
            return self._open()
        except BaseException as exc:
            if self._started and not self._closed:
                if hasattr(self, "_listener"):
                    self._listener.close()
                if (hasattr(self, "_directory_stat")
                        and _same_file(self.directory, self._directory_stat, 0o700, "directory")):
                    try:
                        shutil.rmtree(self.directory)
                    except OSError:
                        self._fail("relay cleanup failed")
                self._closed = True
            if isinstance(exc, RelayError):
                raise
            self._fail("relay setup failed")
            raise RelayError("relay setup failed") from None

    def _open(self) -> GhRelay:
        if self._started:
            raise RelayError("relay already started")
        if any(os.environ.get(k) for k in _UNSAFE_ENV):
            raise RelayError("unsafe relay environment")
        parent = self.work_directory
        if (not parent.is_absolute() or parent.resolve(strict=True) != parent
                or not parent.is_dir() or len(os.fsencode(parent)) > 65):
            raise RelayError("unsafe relay parent")
        self._started = True
        self._start_time = time.monotonic()
        self.directory = Path(tempfile.mkdtemp(prefix="ofarm-gh-", dir=parent))
        os.chmod(self.directory, 0o700)
        self._directory_stat = self.directory.lstat()
        self.config_directory = self.directory / "c"
        self.config_directory.mkdir(mode=0o700)
        self._config_directory_stat = self.config_directory.lstat()
        self.socket_path = self.directory / "s"
        self._config_path = self.config_directory / "config.yml"
        # v2.96.0's MultiAccount migration otherwise rewrites even a hostless
        # configuration. Start at its exact schema version, keeping custody
        # byte-for-byte immutable throughout the retained commands.
        self._config_bytes = ("version: 1\nhttp_unix_socket: "
                              + json.dumps(str(self.socket_path)) + "\n").encode()
        fd = os.open(self._config_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            if os.write(fd, self._config_bytes) != len(self._config_bytes):
                raise RelayError("incomplete relay configuration")
            os.fsync(fd)
        finally:
            os.close(fd)
        self._config_stat = self._config_path.lstat()
        self._listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            # No caller-supplied CA, context, transport or proxy is accepted.
            self._tls = ssl.create_default_context()
            if (not self._tls.check_hostname or self._tls.verify_mode != ssl.CERT_REQUIRED
                    or not self._tls.get_ca_certs()):
                raise RelayError("ordinary TLS trust unavailable")
            self._listener.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o600)
            self._socket_stat = self.socket_path.lstat()
            self._listener.listen(self.limits.max_connections)
            self._listener.settimeout(0.05)
            self._server = threading.Thread(target=self._serve, daemon=True)
            self._server.start()
            self.check()
            return self
        except BaseException:
            self._listener.close()
            shutil.rmtree(self.directory)
            self._closed = True
            raise

    def environment(self, base: Mapping[str, str]) -> dict[str, str]:
        self.check()
        if (any(base.get(k) for k in _UNSAFE_ENV)
                or base.get("GH_HOST", "github.com") != "github.com"
                or base.get("GH_CONFIG_DIR")):
            self._fail("unsafe child environment")
            raise RelayError("unsafe child environment")
        token = base.get("GH_TOKEN") or base.get("GITHUB_TOKEN")
        if (not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token)
                or (base.get("GH_TOKEN") and base.get("GITHUB_TOKEN")
                    and base["GH_TOKEN"] != base["GITHUB_TOKEN"])):
            self._fail("credential unavailable or ambiguous")
            raise RelayError("credential unavailable or ambiguous")
        with self._lock:
            if self._credential is not None and not hmac.compare_digest(self._credential, token):
                self._fail("credential substitution")
                raise RelayError("credential substitution")
            self._credential = token
        result = dict(base)
        result.update(GH_CONFIG_DIR=str(self.config_directory), GH_HOST="github.com",
                      GH_CACHE_DIR=str(self.directory / "cache"), GH_PROMPT_DISABLED="1",
                      GH_NO_UPDATE_NOTIFIER="1", GH_NO_EXTENSION_UPDATE_NOTIFIER="1",
                      NO_COLOR="1", CLICOLOR="0")
        for name in _UNSAFE_ENV:
            result.pop(name, None)
        return result

    def check(self) -> None:
        self._check()

    def _check(self, *, allow_finishing: bool = False) -> None:
        with self._lock:
            if not self._started or self._closed or (self._finishing and not allow_finishing):
                raise RelayError("relay is not active")
            if self._terminal:
                raise RelayError(self._terminal)
            if time.monotonic() - self._start_time > self.limits.lifetime_seconds:
                self._fail("relay deadline")
                raise RelayError("relay deadline")
            valid = (_same_file(self.directory, self._directory_stat, 0o700, "directory")
                     and _same_file(self.config_directory, self._config_directory_stat, 0o700, "directory")
                     and _same_file(self._config_path, self._config_stat, 0o600, "file")
                     and _same_file(self.socket_path, self._socket_stat, 0o600, "socket")
                     and (self._listener.fileno() >= 0
                          or (allow_finishing and self._finishing
                              and self._server_stop.is_set())))
            try:
                if valid:
                    fd = os.open(self._config_path, os.O_RDONLY | os.O_NOFOLLOW)
                    try:
                        current = os.fstat(fd)
                        valid = ((current.st_dev, current.st_ino) ==
                                 (self._config_stat.st_dev, self._config_stat.st_ino)
                                 and os.read(fd, len(self._config_bytes) + 1) == self._config_bytes
                                 and set(os.listdir(self.config_directory)) == {"config.yml"})
                    finally:
                        os.close(fd)
            except OSError:
                valid = False
            if not valid:
                self._fail("relay custody changed")
                raise RelayError("relay custody changed")

    def _serve(self) -> None:
        try:
            while not self._server_stop.is_set():
                self.check()
                try:
                    client, _ = self._listener.accept()
                except socket.timeout:
                    continue
                if not self._slots.acquire(blocking=False):
                    client.close()
                    self._fail("relay concurrency limit")
                    continue
                client.settimeout(self.limits.io_timeout_seconds)
                with self._lock:
                    self._active.add(client)
                    worker = threading.Thread(target=self._handle, args=(client,), daemon=True)
                    self._workers.append(worker)
                worker.start()
        except (RelayError, OSError):
            if not self._server_stop.is_set():
                self._fail("relay listener stopped")
        except BaseException:
            self._fail("relay listener failed")

    def _emit(self, event: RelayEvent) -> None:
        try:
            self._account(event)
        except BaseException:
            self._fail("relay accounting refused")
            raise RelayError("relay accounting refused") from None

    def _read_request(self, client: socket.socket) -> tuple[str, str, str, dict[str, str], bytes, int]:
        stream = client.makefile("rb")
        try:
            raw = bytearray()
            while not raw.endswith(b"\r\n\r\n"):
                line = stream.readline(self.limits.max_header_bytes + 1 - len(raw))
                if not line or not line.endswith(b"\r\n"):
                    raise RelayError("incomplete request headers")
                raw.extend(line)
                if len(raw) >= self.limits.max_header_bytes:
                    raise RelayError("request header limit")
            lines = bytes(raw).decode("ascii").split("\r\n")
            fields = lines[0].split(" ")
            if len(fields) != 3 or fields[0] not in ("GET", "POST") or fields[2] != "HTTP/1.1":
                raise RelayError("unexpected request line")
            method, target, _ = fields
            if len(target) > 8192 or not target.startswith("/") or target.startswith("//"):
                raise RelayError("unexpected request target")
            headers: dict[str, str] = {}
            for line in lines[1:-2]:
                if ":" not in line or line[0].isspace():
                    raise RelayError("invalid request header")
                name, value = line.split(":", 1)
                name, value = name.lower(), value.strip(" ")
                if (name not in _REQUEST_HEADERS or name in headers
                        or any(ord(c) < 32 or ord(c) > 126 for c in value)):
                    raise RelayError("unexpected request header")
                headers[name] = value
            host = headers.get("host", "")
            length = headers.get("content-length", "0")
            if not re.fullmatch(r"0|[1-9][0-9]{0,5}", length):
                raise RelayError("invalid request length")
            n = int(length)
            if n > self.limits.max_request_bytes or (method == "GET" and n):
                raise RelayError("request body limit")
            body = stream.read(n)
            if len(body) != n:
                raise RelayError("incomplete request body")
            if "graphql-features" in headers and not (
                    host == "api.github.com" and method == "POST" and target == "/graphql"
                    and headers["graphql-features"] == "merge_queue"):
                raise RelayError("unexpected GraphQL feature")
            if "referer" in headers and not (
                    host == "release-assets.githubusercontent.com" and method == "GET"
                    and headers["referer"] in {
                        "https://api.github.com/repos/" + self.policy.repository
                        + "/releases/assets/" + str(asset_id)
                        for asset_id, _ in self.policy.assets}):
                raise RelayError("unexpected redirect origin")
            if host == "api.github.com":
                value = headers.get("authorization", "")
                token = self._credential
                if token is None or not any(hmac.compare_digest(value, p + token)
                                             for p in ("token ", "Bearer ")):
                    raise RelayError("credential mismatch")
            elif "authorization" in headers:
                raise RelayError("credential destination refused")
            return method, host, target, headers, body, len(raw) + n
        except (UnicodeError, ValueError):
            raise RelayError("invalid request encoding") from None
        finally:
            stream.close()

    def _route(self, method: str, host: str, target: str, body: bytes) -> tuple[str, int]:
        url = urlsplit(target)
        if (url.scheme or url.netloc or url.fragment or "\\" in target or "%" in url.path
                or ".." in url.path or any(ord(c) < 33 or ord(c) > 126 for c in target)):
            raise RelayError("request route refused")
        path = url.path
        prefix = "/repos/" + self.policy.repository
        if host == "api.github.com":
            if path == "/graphql" and method == "POST" and not url.query:
                data = _json(body)
                owner, name = self.policy.repository.split("/")
                if (not isinstance(data, dict) or set(data) != {"query", "variables"}
                        or data["variables"] != {"owner": owner, "name": name, "tagName": self.policy.tag}
                        or not isinstance(data["query"], str)
                        or re.sub(r"[\s,]", "", data["query"]) != _GQL):
                    raise RelayError("GraphQL body refused")
                return "graphql", self.limits.max_metadata_bytes
            if method != "GET" or body:
                raise RelayError("request method refused")
            fixed = {prefix, "/meta", prefix + "/immutable-releases",
                     prefix + "/releases/tags/" + self.policy.tag,
                     prefix + "/releases/" + str(self.policy.release_id),
                     prefix + "/commits/" + self.policy.tag,
                     prefix + "/git/ref/tags/" + self.policy.tag}
            if path in fixed and not url.query:
                return "rest", self.limits.max_metadata_bytes
            for asset_id, size in self.policy.assets:
                if path == prefix + "/releases/assets/" + str(asset_id) and not url.query:
                    return "rest", max(size, self.limits.max_metadata_bytes)
            if path == prefix + "/attestations/sha1:" + self.policy.tag_sha:
                pairs = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True)
                query = dict(pairs)
                if (len(query) != len(pairs) or not {"per_page", "predicate_type"} <= set(query)
                        or set(query) - {"per_page", "predicate_type", "page"}
                        or query["per_page"] != "100" or query["predicate_type"] != "release"
                        or not re.fullmatch(r"[1-9][0-9]*", query.get("page", "1"))
                        or not 1 <= int(query.get("page", "1")) <= self.limits.max_pages):
                    raise RelayError("attestation page refused")
                return "rest", self.limits.max_metadata_bytes
        elif method == "GET" and not body:
            if host == "tuf-repo.github.com" and not url.query:
                if (re.fullmatch(r"/(?:[1-9][0-9]{0,3}\.(?:root|snapshot|targets)|timestamp)\.json", path)
                        or re.fullmatch(r"/targets/[0-9a-f]{64}\.trusted_root\.json", path)):
                    return "tuf", self.limits.max_metadata_bytes
            with self._lock:
                selected = self._expected_urls.get("https://" + host + target)
            if selected:
                return selected
        raise RelayError("request route refused")

    def _destination(self, raw: str, kind: str, maximum: int) -> str:
        if len(raw) > 8192 or any(ord(c) < 33 or ord(c) > 126 for c in raw):
            raise RelayError("destination refused")
        parsed = urlsplit(raw)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment
                or parsed.port not in (None, 443) or parsed.netloc != parsed.hostname
                or "%" in parsed.path or ".." in parsed.path or "\\" in raw):
            raise RelayError("destination refused")
        if kind == "attestation":
            valid = (parsed.hostname == "tmaproduction.blob.core.windows.net"
                     and re.fullmatch(r"/attestations/" + str(self.policy.repository_id)
                                      + r"/[0-9]{4}/[0-9]{2}/[0-9]{2}/[0-9]+\.json\.sn", parsed.path))
        else:
            valid = (parsed.hostname == "release-assets.githubusercontent.com"
                     and re.fullmatch(r"/github-production-release-asset/" + str(self.policy.repository_id)
                                      + r"/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", parsed.path))
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        if (not valid or len(dict(pairs)) != len(pairs)
                or any(k not in _SIGNED_QUERY_KEYS or not v for k, v in pairs)):
            raise RelayError("destination refused")
        with self._lock:
            if len(self._expected_urls) >= self.limits.max_requests:
                raise RelayError("destination limit")
            self._expected_urls[raw] = ("blob", maximum)
        return raw

    def _quota(self, headers: Mapping[str, str], bucket: str) -> QuotaFacts | None:
        if bucket not in ("rest", "graphql"):
            return None
        values = []
        for key in ("limit", "remaining", "reset", "used"):
            raw = headers.get("x-ratelimit-" + key, "")
            if not re.fullmatch(r"0|[1-9][0-9]{0,12}", raw):
                raise RelayError("primary quota unavailable")
            values.append(int(raw))
        resource = headers.get("x-ratelimit-resource", "")
        expected = "graphql" if bucket == "graphql" else "core"
        limit, remaining, reset, used = values
        if (resource != expected or not limit or remaining > limit or used > limit
                or used + remaining != limit or not reset):
            raise RelayError("primary quota contradictory")
        return QuotaFacts(resource, limit, remaining, reset, used)

    def _handle(self, client: socket.socket) -> None:
        event: RelayEvent | None = None
        upstream: http.client.HTTPSConnection | None = None
        status_code = None
        quota = None
        received = 0
        complete = False
        try:
            self.check()
            method, host, target, headers, body, request_bytes = self._read_request(client)
            bucket, maximum = self._route(method, host, target, body)
            with self._lock:
                self.check()
                if self._requests >= self.limits.max_requests:
                    raise RelayError("request limit")
                self._requests += 1
                event = RelayEvent("request", self._requests, bucket, method, host,
                                   urlsplit(target).path, request_bytes=request_bytes)
                self._emit(event)
                self.check()
            upstream = http.client.HTTPSConnection(host, 443, context=self._tls,
                                                    timeout=self.limits.io_timeout_seconds)
            upstream.response_class = lambda *args, **kwargs: _BoundedResponse(
                *args, line_limit=self.limits.max_header_bytes, **kwargs)
            with self._lock:
                self._upstream.add(upstream)
                self.check()
                upstream.request(method, target, body=body or None,
                                 headers={k: v for k, v in headers.items() if k != "connection"})
            response = upstream.getresponse()
            status_code = response.status
            if (type(status_code) is not int or not isinstance(response.reason, str)
                    or any(ord(c) < 32 or ord(c) > 126 for c in response.reason)):
                raise RelayError("invalid response status")
            raw_headers = response.getheaders()
            if sum(len(k) + len(v) + 4 for k, v in raw_headers) > self.limits.max_header_bytes:
                raise RelayError("response header limit")
            response_headers: dict[str, str] = {}
            for key, value in raw_headers:
                key = key.lower()
                if (not re.fullmatch(r"[!#$%&'*+.^_`|~0-9a-z-]+", key)
                        or any(ord(c) < 32 or ord(c) > 126 for c in value)):
                    raise RelayError("invalid response header")
                if key in response_headers and key in {
                    "content-length", "transfer-encoding", "content-encoding", "location",
                    "content-type", "link", "x-ratelimit-limit", "x-ratelimit-remaining",
                    "x-ratelimit-reset", "x-ratelimit-used", "x-ratelimit-resource"}:
                    raise RelayError("ambiguous response header")
                response_headers[key] = value
            if ("content-length" in response_headers and "transfer-encoding" in response_headers
                    or response_headers.get("transfer-encoding", "chunked") != "chunked"
                    or any(k in response_headers for k in ("proxy-authenticate", "proxy-authorization", "upgrade"))):
                raise RelayError("unexpected response framing")
            raw_length = response_headers.get("content-length")
            if raw_length is not None and (not re.fullmatch(r"0|[1-9][0-9]*", raw_length)
                                           or int(raw_length) > maximum):
                raise RelayError("response body limit")
            if status_code in (403, 429):
                self._fail("HTTP rate refusal")
            quota = self._quota(response_headers, bucket)
            self._emit(RelayEvent("response", event.request_id, bucket, method, host, event.path,
                                  status_code, request_bytes, quota=quota))
            if status_code not in (200, 302, 404, 403, 429):
                raise RelayError("unexpected response status")
            if status_code == 404 and not (bucket == "tuf" and event.path.endswith(".root.json")):
                raise RelayError("unexpected missing response")
            if status_code == 302:
                match = re.fullmatch(r"/repos/" + re.escape(self.policy.repository)
                                     + r"/releases/assets/([0-9]+)", event.path)
                if not match or bucket != "rest":
                    raise RelayError("redirect refused")
                size = dict(self.policy.assets).get(int(match[1]))
                if size is None:
                    raise RelayError("redirect refused")
                self._destination(response_headers.get("location", ""), "asset", size)
            elif "location" in response_headers:
                raise RelayError("unexpected redirect header")
            # Buffer bounded metadata and error outcomes before exposing their
            # headers. gh deliberately closes a missing next TUF root after
            # reading its 404 status; we still observe the complete upstream
            # response. Unknown upstream cancellation remains terminal.
            buffered = maximum <= self.limits.max_metadata_bytes or status_code != 200
            if buffered:
                maximum = min(maximum, self.limits.max_metadata_bytes)
            header_block = bytearray(f"HTTP/1.1 {status_code} {response.reason}\r\n".encode("ascii"))
            for key, value in raw_headers:
                if key.lower() not in _HOP_HEADERS:
                    header_block.extend((key + ": " + value + "\r\n").encode("ascii"))
            header_block.extend(b"Connection: close\r\n\r\n")
            if not buffered:
                client.sendall(header_block)
            metadata = bytearray()
            capture = status_code == 200 and bucket in ("rest", "graphql", "tuf") and maximum <= self.limits.max_metadata_bytes
            while True:
                if time.monotonic() - self._start_time > self.limits.lifetime_seconds:
                    raise RelayError("relay deadline")
                try:
                    chunk = response.read(min(65536, maximum + 1 - received))
                except http.client.IncompleteRead as incomplete:
                    # The parser may already have received part of a chunk.
                    # Retain those bytes even though no successful body exists.
                    partial = incomplete.partial
                    if not isinstance(partial, bytes):
                        raise RelayError("unknown partial response") from None
                    received += len(partial)
                    with self._lock:
                        self._response_bytes += len(partial)
                    raise RelayError("incomplete response body") from None
                if not chunk:
                    break
                received += len(chunk)
                with self._lock:
                    self._response_bytes += len(chunk)
                    if received > maximum or self._response_bytes > self.limits.max_response_bytes:
                        raise RelayError("response byte limit")
                if buffered:
                    metadata.extend(chunk)
                else:
                    client.sendall(chunk)
            if raw_length is not None and received != int(raw_length):
                raise RelayError("incomplete response body")
            if capture:
                data = bytes(metadata)
                encoding = response_headers.get("content-encoding", "identity")
                if encoding == "gzip":
                    with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
                        data = compressed.read(self.limits.max_metadata_bytes + 1)
                elif encoding != "identity":
                    raise RelayError("metadata encoding refused")
                if len(data) > self.limits.max_metadata_bytes:
                    raise RelayError("metadata expansion limit")
                document = _json(data)
                if "/attestations/" in event.path:
                    if not isinstance(document, dict) or not isinstance(document.get("attestations"), list):
                        raise RelayError("invalid attestation metadata")
                    for item in document["attestations"]:
                        if not isinstance(item, dict):
                            raise RelayError("invalid attestation metadata")
                        if item.get("bundle_url"):
                            self._destination(item["bundle_url"], "attestation", self.limits.max_metadata_bytes)
                if bucket == "graphql":
                    if (not isinstance(document, dict) or document.get("errors")
                            or not isinstance(document.get("data"), dict)
                            or not isinstance(document["data"].get("repository"), dict)
                            or not isinstance(document["data"]["repository"].get("release"), dict)
                            or type(document["data"]["repository"]["release"].get("databaseId")) is not int
                            or type(document["data"]["repository"]["release"].get("isDraft")) is not bool):
                        raise RelayError("incomplete or failed GraphQL response")
                    data_part = document.get("data")
                    rate = data_part.get("rateLimit") if isinstance(data_part, dict) else None
                    if isinstance(rate, dict) and type(rate.get("cost")) is int and rate["cost"] >= 0:
                        quota = QuotaFacts(quota.resource, quota.limit, quota.remaining, quota.reset, quota.used, rate["cost"])
            complete = True
            if buffered:
                try:
                    client.sendall(header_block)
                    client.sendall(bytes(metadata))
                except (BrokenPipeError, ConnectionResetError):
                    # Complete describes the upstream outcome. The caller's
                    # exit and genuine stderr still require independent checks.
                    pass
        except RelayError as exc:
            self._fail(str(exc))
        except (OSError, http.client.HTTPException, ValueError, TypeError, UnicodeError, RecursionError):
            self._fail("incomplete or invalid transport")
        except BaseException:
            self._fail("relay worker failed")
        finally:
            if event is not None:
                try:
                    self._emit(RelayEvent("completed", event.request_id, event.bucket, event.method,
                                          event.host, event.path, status_code, event.request_bytes,
                                          received, quota, complete))
                except RelayError:
                    pass
                with self._lock:
                    self._completed += 1
            if upstream is not None:
                upstream.close()
            client.close()
            with self._lock:
                self._active.discard(client)
                self._upstream.discard(upstream)
            self._slots.release()

    def finish(self) -> RelaySummary:
        with self._lock:
            if self._closed or not self._started:
                raise RelayError("relay is not active")
            if not self._finishing:
                try:
                    self.check()
                except RelayError:
                    pass
                self._finishing = True
                self._server_stop.set()
                self._listener.close()
        deadline = time.monotonic() + self.limits.drain_seconds
        self._server.join(timeout=max(0, deadline - time.monotonic()))
        for worker in self._workers:
            worker.join(timeout=max(0, deadline - time.monotonic()))
        if self._server.is_alive() or any(w.is_alive() for w in self._workers):
            self._fail("incomplete relay drain")
            self._close_connections()
            close_deadline = time.monotonic() + self.limits.io_timeout_seconds
            for worker in self._workers:
                worker.join(timeout=max(0, close_deadline - time.monotonic()))
        try:
            self._check(allow_finishing=True)
        except RelayError:
            pass
        if not self._requests or self._requests != self._completed:
            self._fail("missing or incomplete relay traffic")
        if any(w.is_alive() for w in self._workers):
            self._fail("relay worker did not terminate")
        if self._terminal:
            raise RelayError(self._terminal)
        return RelaySummary(self._requests, self._response_bytes)

    def _close_connections(self) -> None:
        with self._lock:
            sockets = list(self._active) + [c.sock for c in self._upstream if c.sock]
        for connection in sockets:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        error: RelayError | None = None
        try:
            if exc is not None:
                self._fail("owning operation failed")
                self._close_connections()
            self.finish()
        except RelayError as failure:
            error = failure
        finally:
            self._credential = None
            self._expected_urls.clear()
            if _same_file(self.directory, self._directory_stat, 0o700, "directory"):
                try:
                    shutil.rmtree(self.directory)
                except OSError:
                    self._fail("relay cleanup failed")
                    error = RelayError("relay cleanup failed")
            else:
                self._fail("relay cleanup custody changed")
                error = RelayError("relay cleanup custody changed")
            self._closed = True
        if error is not None and exc is None:
            raise error
