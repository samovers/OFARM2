"""Private observation of the four unchanged, public curl downloads.

curl retains HTTPS ownership. A private config selects bounded in-memory trace
and completion pipes; no URL query, header, body or credential is persisted.
This is observation, not a proxy or an alternate downloader.
"""
from __future__ import annotations

import os
import re
import select
import shutil
import stat
import threading
import time
import uuid
from urllib.parse import urlsplit


class CurlError(RuntimeError):
    pass


URLS = {
    "buildx-amd64": "https://github.com/docker/buildx/releases/download/v0.34.1/buildx-v0.34.1.linux-amd64",
    "buildx-arm64": "https://github.com/docker/buildx/releases/download/v0.34.1/buildx-v0.34.1.linux-arm64",
    "gh-amd64": "https://github.com/cli/cli/releases/download/v2.96.0/gh_2.96.0_linux_amd64.tar.gz",
}
MAX_BYTES = 128 * 1024 ** 2
MAX_TRACE_BYTES = 1024 * 1024 ** 2
MAX_SECONDS = 600


class CurlLifecycle:
    def __init__(self, parent, name, observe, on_terminal):
        if name not in URLS:
            raise CurlError("unknown curl operation")
        self.parent, self.name = parent, name
        self.observe, self.on_terminal = observe, on_terminal
        self.process = str(uuid.uuid4())
        self.sequence = -1
        self.requests = []
        self.current = None
        self.expected = URLS[name]
        self.failed = False
        self.closed = False
        self.done = threading.Event()
        self.stop = threading.Event()
        self._lock = threading.RLock()
        self.block = None
        self.total = 0
        self.trace_bytes = 0
        self._buffers = {"trace": bytearray(), "result": bytearray()}

    def _send(self, operation, **fields):
        self.sequence += 1
        reply = self.observe({"processId": self.process, "sequence": self.sequence,
                              "operation": operation, **fields})
        if not reply.get("accepted") or reply.get("sequence") != self.sequence:
            raise CurlError("curl observation refused")

    def _fail(self):
        self.failed = True
        self.on_terminal("curl observer refused")

    def start(self):
        self.directory = self.parent / ("curl-" + self.name)
        try:
            self.directory.mkdir(mode=0o700)
            self.identity = self.directory.stat()
            self.fds = {}
            for name in ("trace", "result"):
                path = self.directory / name
                os.mkfifo(path, 0o600)
                # Keep a private writer open so no transient EOF can be mistaken
                # for completion before curl has opened its trace.
                self.fds[name] = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_NOFOLLOW)
            self.config = (f'trace = "{self.directory / "trace"}"\n'
                f'write-out = "%output{{{self.directory / "result"}}}%{{exitcode}} %{{response_code}} %{{num_redirects}} %{{size_download}}\\n"\n').encode()
            config = self.directory / ".curlrc"
            with os.fdopen(os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
                stream.write(self.config)
            self.identities = {p.name: p.lstat() for p in self.directory.iterdir()}
            self._send("open", kind="curl", pid=os.getpid(), ppid=os.getppid())
            self.started = time.monotonic()
            self.worker = threading.Thread(target=self._read, daemon=True)
            self.worker.start()
            return {"CURL_HOME": str(self.directory)}
        except BaseException:
            self.abort()
            raise

    def _custody(self):
        info = self.directory.lstat()
        if ((info.st_dev, info.st_ino) != (self.identity.st_dev, self.identity.st_ino)
                or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700
                or self.directory.resolve() != self.directory
                or set(os.listdir(self.directory)) != {".curlrc", "trace", "result"}):
            raise CurlError("curl custody changed")
        for name, expected in self.identities.items():
            item = (self.directory / name).lstat()
            if ((item.st_dev, item.st_ino) != (expected.st_dev, expected.st_ino)
                    or item.st_uid != os.getuid() or stat.S_IMODE(item.st_mode) != 0o600):
                raise CurlError("curl custody changed")
        if (self.directory / ".curlrc").read_bytes() != self.config:
            raise CurlError("curl configuration changed")

    def _read(self):
        try:
            while not self.stop.is_set():
                self._custody()
                if time.monotonic() - self.started > MAX_SECONDS:
                    raise CurlError("curl deadline")
                readable, _, _ = select.select(list(self.fds.values()), [], [], 0.05)
                for name in ("trace", "result"):
                    if self.fds[name] not in readable:
                        continue
                    data = os.read(self.fds[name], 65536)
                    self.trace_bytes += len(data)
                    if self.trace_bytes > MAX_TRACE_BYTES:
                        raise CurlError("curl trace bound")
                    self._buffers[name].extend(data)
                    while b"\n" in self._buffers[name]:
                        line, _, remainder = self._buffers[name].partition(b"\n")
                        self._buffers[name] = bytearray(remainder)
                        if name == "trace":
                            self.line(bytes(line))
                        else:
                            if self.done.is_set() or not re.fullmatch(rb"[0-9]+ [0-9]{3} [0-9]+ [0-9]+", line):
                                raise CurlError("invalid curl completion")
                            self.result = tuple(map(int, line.split()))
                            self.done.set()
                    if len(self._buffers[name]) > 65536:
                        raise CurlError("curl line bound")
        except BaseException:
            self._fail()
            # A stopped reader must not leave the canonical curl process
            # blocked writing an unread trace. Closing both owned pipe ends
            # makes the writer fail; acceptance remains permanently refused.
            for name, fd in self.fds.items():
                if fd >= 0:
                    os.close(fd)
                    self.fds[name] = -1
            self.done.set()

    def line(self, line):
        if self.block is not None:
            match = re.fullmatch(rb"([0-9a-fA-F]{4,}): (.*)", line)
            if not match or int(match[1], 16) != self.block["offset"]:
                raise CurlError("incomplete curl trace block")
            count = min(16, self.block["size"] - self.block["offset"])
            raw = match[2][:count * 3].strip().split()
            if len(raw) != count or any(not re.fullmatch(rb"[0-9a-fA-F]{2}", v) for v in raw):
                raise CurlError("invalid curl trace bytes")
            if self.block["capture"]:
                self.block["data"].extend(bytes(int(v, 16) for v in raw))
            self.block["offset"] += count
            if self.block["offset"] == self.block["size"]:
                selected, self.block = self.block, None
                if selected["capture"]:
                    self._header(selected["kind"], bytes(selected["data"]))
            return
        if line.startswith(b"== Info:"):
            return
        match = re.fullmatch(rb"((?:=>|<=) (?:Send|Recv) (?:header|data|SSL data)), ([0-9]+) bytes \(0x[0-9a-fA-F]+\)", line)
        if not match:
            raise CurlError("unknown curl trace event")
        kind, size = match[1].decode(), int(match[2])
        capture = kind in {"=> Send header", "<= Recv header"}
        if size > 1024 * 1024 or (capture and size > 32768):
            raise CurlError("curl trace block bound")
        if kind == "<= Recv data":
            if self.current is None or self.current["status"] is None:
                raise CurlError("unassociated curl body")
            self.current["bytes"] += size
            self.total += size
            if self.total > MAX_BYTES:
                raise CurlError("curl byte bound")
        if size:
            self.block = {"kind": kind, "size": size, "offset": 0, "capture": capture, "data": bytearray()}

    def _settle(self, complete):
        if self.current is not None and not self.current["ended"]:
            self.current["ended"] = True
            self._send("end", requestId=self.current["id"], bytes=self.current["bytes"], complete=complete)

    def _header(self, kind, raw):
        if kind == "=> Send header":
            if self.current is not None:
                if self.current["status"] not in (301, 302, 303, 307, 308) or not self.current["headersDone"]:
                    raise CurlError("unexpected curl repeat")
                length = self.current["headers"].get("content-length")
                if length is None or not length.isdigit() or int(length) != self.current["bytes"]:
                    raise CurlError("incomplete curl redirect body")
                self._settle(True)
            try:
                lines = raw.decode("ascii").split("\r\n")
                method, target, protocol = lines[0].split(" ")
                headers = dict(line.split(":", 1) for line in lines[1:] if line)
                host = next(value.strip() for key, value in headers.items() if key.lower() == "host")
            except (ValueError, UnicodeError, StopIteration):
                raise CurlError("invalid curl request") from None
            expected = urlsplit(self.expected)
            exact_target = expected.path + (("?" + expected.query) if expected.query else "")
            if (method != "GET" or protocol not in ("HTTP/1.1", "HTTP/2", "HTTP/3")
                    or host != expected.netloc or target != exact_target
                    or any(key.lower() in {"authorization", "proxy-authorization"} for key in headers)
                    or len(self.requests) >= 10):
                raise CurlError("unknown curl route")
            request_id = self.process + ":" + str(len(self.requests) + 1)
            self.current = {"id": request_id, "status": None, "bytes": 0, "headers": {}, "headersDone": False, "ended": False}
            self.requests.append(self.current)
            self._send("begin", requestId=request_id, method="GET", host=host,
                       path=expected.path, bucket="download")
        else:
            if self.current is None:
                raise CurlError("unassociated curl response")
            text = raw.decode("ascii")
            if text.startswith("HTTP/"):
                match = re.fullmatch(r"HTTP/(?:1\.[01]|2|3) ([2-5][0-9]{2})(?: [^\r\n]*)?\r\n", text)
                if not match or self.current["status"] is not None:
                    raise CurlError("invalid curl status")
                self.current["status"] = int(match[1])
                self._send("response", requestId=self.current["id"], status=self.current["status"], quota=None)
            elif text == "\r\n":
                self.current["headersDone"] = True
                location = self.current["headers"].get("location")
                if self.current["status"] in (301, 302, 303, 307, 308):
                    parsed = urlsplit(location or "")
                    if (parsed.scheme != "https" or parsed.netloc != "release-assets.githubusercontent.com"
                            or parsed.username or parsed.password or parsed.fragment or not parsed.path.startswith("/github-production-release-asset/")):
                        raise CurlError("unknown curl redirect")
                    self.expected = location
                elif self.current["status"] != 200 or location:
                    raise CurlError("curl failed status")
            else:
                key, value = text.rstrip("\r\n").split(":", 1)
                key = key.lower()
                if key in {"content-length", "location", "transfer-encoding"}:
                    if key in self.current["headers"]:
                        raise CurlError("ambiguous curl header")
                    self.current["headers"][key] = value.strip()

    def finish(self):
        try:
            if not self.done.wait(5):
                raise CurlError("missing curl completion")
            # Drain trace data already in the other pipe before checking totals.
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and (self.block or self._buffers["trace"] or select.select([self.fds["trace"]], [], [], 0)[0]):
                time.sleep(0.01)
            self.stop.set()
            self.worker.join(timeout=2)
            self._custody()
            if (self.failed or self.worker.is_alive() or not self.requests or self.block
                    or any(self._buffers.values()) or not hasattr(self, "result")):
                raise CurlError("incomplete curl disposition")
            code, status, redirects, size = self.result
            if (code != 0 or status != 200 or redirects != len(self.requests) - 1
                    or self.current["status"] != status or not self.current["headersDone"]
                    or size > self.current["bytes"]):
                raise CurlError("failed curl completion")
            length = self.current["headers"].get("content-length")
            if length is not None and (not length.isdigit() or int(length) != self.current["bytes"] or size != int(length)):
                raise CurlError("incomplete curl body")
            self._settle(True)
            self._cleanup()
            self._send("close")
        except BaseException:
            self.abort()
            raise CurlError("curl lifecycle refused") from None

    def _cleanup(self):
        if self.closed:
            return
        self.stop.set()
        if hasattr(self, "worker"):
            self.worker.join(timeout=2)
            if self.worker.is_alive():
                raise CurlError("curl worker did not stop")
        for fd in getattr(self, "fds", {}).values():
            if fd >= 0:
                os.close(fd)
        self.fds = {}
        if hasattr(self, "identity"):
            info = self.directory.lstat()
            if (info.st_dev, info.st_ino) != (self.identity.st_dev, self.identity.st_ino):
                raise CurlError("curl cleanup custody changed")
            if set(os.listdir(self.directory)) - {".curlrc", "trace", "result"}:
                raise CurlError("unowned curl cleanup paths")
            shutil.rmtree(self.directory)
        self.closed = True

    def abort(self):
        self._fail()
        self.stop.set()
        if hasattr(self, "worker"):
            self.worker.join(timeout=2)
        try:
            self._settle(False)
        except BaseException:
            pass
        self._cleanup()
