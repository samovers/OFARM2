"""One private, durable accounting authority for transition API and tools.

This file is also embedded verbatim before checkout, so it uses only the
standard library. It does not confer evidence authority. A live supervisor,
complete observations, and successful cleanup are prerequisites to acceptance.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import importlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
import types
import uuid


class TransitionError(RuntimeError):
    """A refused transition; arbitrary provider text is never retained."""


class QuotaWindowError(TransitionError):
    """Carry bounded facts when the selected primary limit changes."""

    def __init__(self, bucket, previous, *, remaining, reset, limit):
        super().__init__("contradictory quota window")
        self._quota_facts = (bucket, previous["remaining"], previous["reset"],
                             previous["limit"], remaining, reset, limit)

    def diagnostic(self):
        # Validate again at the logging boundary. Oversize or malformed facts
        # omit this optional detail; they never change the original refusal.
        facts = self._quota_facts
        if (type(facts) is not tuple or len(facts) != 7
                or type(facts[0]) is not str or facts[0] not in ("REST", "GraphQL")
                or any(type(value) is not int or not 0 <= value < 10 ** 13 for value in facts[1:])):
            return None
        previous, incoming = (dict(zip(("remaining", "reset", "limit"), values))
                              for values in (facts[1:4], facts[4:7]))
        if any(not 0 <= item["remaining"] <= item["limit"] or item["limit"] < 1000
               or item["reset"] == 0 for item in (previous, incoming)):
            return None
        reset_regressed = incoming["reset"] < previous["reset"]
        limit_changed = incoming["limit"] != previous["limit"]
        if not reset_regressed and not limit_changed:
            return None
        return {"reason": "QUOTA_WINDOW_CONTRADICTION", "bucket": facts[0],
                "resetRegressed": reset_regressed, "limitChanged": limit_changed,
                "previous": previous, "incoming": incoming}


POOL_LIMITS = {
    "source-gate": (40, 10), "conformance": (16, 4),
    "native-amd64": (16, 4), "native-arm64": (16, 4),
    "source-guard": (30, 10), "handoff": (34, 10),
    "publisher-gate": (36, 10), "source-admission": (19, 5),
    "publisher-guard": (30, 10), "publish": (45, 15),
    "seal": (40, 15), "source-reader": (12, 0),
}
# A complete generated-path trace must justify these disjoint shares before
# activation. They preserve the reviewed aggregate of 116 REST / 103 points.
TOOL_ALLOCATIONS = {
    "source-gate": (4, 4), "conformance": (20, 40),
    "native-amd64": (4, 4), "native-arm64": (4, 4),
    "source-guard": (2, 2), "handoff": (4, 8),
    "publisher-gate": (4, 4), "source-admission": (4, 8),
    "publish": (8, 8), "publisher-guard": (2, 2), "seal": (4, 9),
    "external-acceptance": (56, 10),
}
PHASE_JOBS = {
    "source-gate": "source-gate", "conformance": "conformance",
    "native-amd64": "native-amd64", "native-arm64": "native-arm64",
    "source-guard": "source-guard", "handoff-start": "handoff",
    "handoff": "handoff", "handoff-preupload": "handoff",
    "publisher-gate": "publisher-gate", "source-admission-resolve": "source-admission",
    "source-admission": "source-admission", "publisher-start": "publish",
    "prepublish": "publish", "preindex": "publish", "publisher-resolve": "publish",
    "publisher-guard": "publisher-guard", "seal-resolve": "seal",
    "seal-start": "seal", "seal": "seal", "seal-preupload": "seal",
    "external-acceptance": "external-acceptance", "download": "publish",
}
TRANSPORT_REQUEST_LIMIT = 2048
TRANSPORT_BYTE_LIMIT = 16 * 1024 ** 3
TRACE_LIMIT = 20000
FRAME_LIMIT = 8192
JOB_LIFETIMES = {
    "source-gate": 300, "conformance": 3600, "native-amd64": 7200,
    "native-arm64": 7200, "source-guard": 8100, "handoff": 600,
    "publisher-gate": 300, "source-admission": 600, "publish": 2700,
    "publisher-guard": 3600, "seal": 600, "external-acceptance": 7200,
}
LIFETIME_SECONDS = max(JOB_LIFETIMES.values())
ASSET_ENV = {"tools.py": "OFARM_TRANSITION_TOOLS_SHA256",
             "node.cjs": "OFARM_TRANSITION_NODE_SHA256",
             "execution.py": "OFARM_TRANSITION_EXECUTION_SHA256",
             "gh_relay.py": "OFARM_TRANSITION_GH_RELAY_SHA256",
             "curl.py": "OFARM_TRANSITION_CURL_SHA256"}
_FLAGS = os.O_NOFOLLOW | os.O_CLOEXEC
_ENV_KEYS = (
    "OFARM_TRANSITION_TOOLS_DIRECTORY", "OFARM_TRANSITION_TOOLS_NONCE",
    "OFARM_TRANSITION_TOOLS_JOB", "OFARM_TRANSITION_TOOLS_SUPERVISOR",
)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def decode(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise TransitionError("duplicate control field")
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError) as exc:
        raise TransitionError("invalid control data") from exc


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise TransitionError("invalid integer fact")
    return value


def private_directory(path):
    path = Path(path)
    metadata = path.lstat()
    if (not path.is_absolute() or path.resolve() != path
            or not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700):
        raise TransitionError("private directory custody failed")
    return path


def private_file(path, *, limit=4 * 1024 * 1024):
    with os.fdopen(os.open(path, os.O_RDONLY | _FLAGS), "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1 or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_size > limit):
            raise TransitionError("private file custody failed")
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise TransitionError("private file size exceeded")
    return value


def write_new(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _FLAGS, 0o600), "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def atomic_write(path, data):
    temporary = path.with_name(path.name + "." + secrets.token_hex(8))
    try:
        write_new(temporary, data)
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | _FLAGS)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


class RequestBudget:
    """Disjoint fixed pools, serialised across the API CLI and tool process.

    A terminal failure is monotonic. An attempted overrun is recorded rather
    than being hidden by a check before increment. The cancellation context
    permits at most two additional REST requests, still within its owned pool.
    """
    def __init__(self, job, *, path=None, monotonic=time.monotonic, clock=time.time):
        if job not in TOOL_ALLOCATIONS and job != "external-acceptance":
            raise TransitionError("unknown request-budget job")
        self.job, self.path = job, Path(path) if path is not None else None
        self.monotonic, self.clock = monotonic, clock
        self.deadline = None
        self.current_pool = "shared-tools" if job == "external-acceptance" else job
        self._cancellation = False
        self._state = {"schema": 2, "job": job, "used": {}, "quota": {},
                       "quotaConstraints": {}, "primaryRequests": {}, "clock": 0,
                       "trace": [], "transport": {"requests": 0, "bytes": 0},
                       "failed": False, "cancellationRequests": 0}
        if self.path is not None:
            private_directory(self.path.parent)
            lock = self.path.with_suffix(self.path.suffix + ".lock")
            new_lock = False
            try:
                write_new(lock, b"")
                new_lock = True
            except FileExistsError:
                private_file(lock, limit=0)
            self._lock_identity = self._identity(lock)
            with self._transaction(create=new_lock):
                pass

    @staticmethod
    def _identity(path):
        info = path.lstat()
        return info.st_dev, info.st_ino

    @contextmanager
    def _transaction(self, *, create=False):
        if self.path is None:
            yield self._state
            return
        private_directory(self.path.parent)
        lock = self.path.with_suffix(self.path.suffix + ".lock")
        if self._identity(lock) != self._lock_identity:
            raise TransitionError("accounting lock changed")
        descriptor = os.open(lock, os.O_RDWR | _FLAGS)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino) != self._lock_identity:
                raise TransitionError("accounting lock changed")
            try:
                state = decode(private_file(self.path))
            except FileNotFoundError:
                if not create:
                    raise TransitionError("accounting state disappeared") from None
                state = self._state
            self._validate(state)
            self._state = state
            try:
                yield state
            finally:
                atomic_write(self.path, canonical(state))
        finally:
            os.close(descriptor)

    def _validate(self, state):
        if (not isinstance(state, dict) or set(state) != set(self._state)
                or state["schema"] != 2 or state["job"] != self.job
                or type(state["failed"]) is not bool
                or not isinstance(state["used"], dict)
                or not isinstance(state["quota"], dict)
                or not isinstance(state["trace"], list) or len(state["trace"]) > TRACE_LIMIT):
            raise TransitionError("invalid accounting state")
        for pool, counts in state["used"].items():
            limits = self.limits(pool)
            if not isinstance(counts, list) or len(counts) != 2:
                raise TransitionError("invalid accounting counts")
            for index, count in enumerate(counts):
                integer(count)
                if count > limits[index] and not state["failed"]:
                    raise TransitionError("unlatched accounting overrun")
        if set(state["transport"]) != {"requests", "bytes"}:
            raise TransitionError("invalid transport counts")
        for count in state["transport"].values():
            integer(count)
        integer(state["cancellationRequests"])
        for bucket, quota in state["quota"].items():
            self._quota(bucket, **quota, check_time=False)
        if (not isinstance(state["quotaConstraints"], dict)
                or set(state["quotaConstraints"]) != set(state["quota"])
                or not isinstance(state["primaryRequests"], dict)
                or len(state["primaryRequests"]) > TRANSPORT_REQUEST_LIMIT):
            raise TransitionError("invalid primary observation state")
        self._time(state["clock"])
        count = 0
        for bucket, constraints in state["quotaConstraints"].items():
            if not isinstance(constraints, list) or not constraints:
                raise TransitionError("missing primary constraints")
            resets = []
            for item in constraints:
                if not isinstance(item, dict) or set(item) != {"reset", "capacity"}:
                    raise TransitionError("invalid primary constraint")
                resets.append(integer(item["reset"], 1))
                integer(item["capacity"])
                if item["capacity"] > state["quota"][bucket]["limit"] + self._charged(state, bucket):
                    raise TransitionError("primary constraint exceeds observed capacity")
            if resets != sorted(set(resets)):
                raise TransitionError("duplicated or unordered primary constraints")
            count += len(constraints)
        if count > TRANSPORT_REQUEST_LIMIT:
            raise TransitionError("primary constraint bound exceeded")
        for identity, request in state["primaryRequests"].items():
            self._request_identity(identity)
            if (not isinstance(request, dict) or set(request) != {
                    "bucket", "startedAt", "settledBefore", "cost", "observed", "complete"}
                    or request["bucket"] not in ("REST", "GraphQL")
                    or type(request["observed"]) is not bool or type(request["complete"]) is not bool
                    or request["observed"] and request["complete"]):
                raise TransitionError("invalid primary request association")
            self._time(request["startedAt"])
            if request["startedAt"] > state["clock"]:
                raise TransitionError("future primary request association")
            integer(request["settledBefore"])
            integer(request["cost"])
        for bucket in ("REST", "GraphQL"):
            total = self._charged(state, bucket)
            pending = sum(r["cost"] for r in state["primaryRequests"].values() if r["bucket"] == bucket)
            if pending > total or any(r["settledBefore"] > total for r in state["primaryRequests"].values()
                                      if r["bucket"] == bucket):
                raise TransitionError("primary cost association exceeds ledger")

    @staticmethod
    def _time(value):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise TransitionError("invalid trusted clock")
        return value

    def _clock(self, state):
        try:
            now = self._time(self.clock())
        except TransitionError:
            state["failed"] = True
            raise
        if now < state["clock"]:
            state["failed"] = True
            raise TransitionError("trusted clock moved backwards")
        state["clock"] = now
        return now

    @staticmethod
    def _request_identity(identity):
        if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{32}(?::[1-9][0-9]*)?", identity):
            raise TransitionError("invalid primary request identity")

    @staticmethod
    def _charged(state, bucket):
        index = 0 if bucket == "REST" else 1
        return sum(counts[index] for counts in state["used"].values())

    def _snapshot(self, key):
        with self._transaction() as state:
            return decode(canonical(state[key]))

    @property
    def used(self):
        return self._snapshot("used")

    @property
    def quota(self):
        # Raw last observations are witnesses for the tool GraphQL cost proof,
        # never a synthesized window or the headroom authority.
        return self._snapshot("quota")

    @property
    def quota_constraints(self):
        with self._transaction() as state:
            return {bucket: [{"remaining": item["capacity"] - self._charged(state, bucket),
                              "reset": item["reset"], "limit": state["quota"][bucket]["limit"]}
                             for item in constraints]
                    for bucket, constraints in state["quotaConstraints"].items()}

    @property
    def trace(self):
        return self._snapshot("trace")

    def limits(self, pool):
        if self.job == "external-acceptance":
            return TOOL_ALLOCATIONS[self.job]
        if pool == "shared-tools":
            return TOOL_ALLOCATIONS[self.job]
        if pool == "source-reader" and self.job == "publish":
            return POOL_LIMITS[pool]
        if pool == self.job:
            return POOL_LIMITS[pool]
        if (isinstance(pool, str) and re.fullmatch(r"periodic:[0-9]+", pool)
                and self.job in ("source-guard", "publisher-guard")):
            return (15, 5)
        raise TransitionError("job cannot spend another job's pool")

    def _healthy(self, state):
        if state["failed"] and not self._cancellation:
            raise TransitionError("transition permanently refused")
        if self.deadline is not None and self.monotonic() >= self.deadline:
            state["failed"] = True
            raise TransitionError("complete sweep deadline exceeded")

    def assert_healthy(self):
        with self._transaction() as state:
            self._healthy(state)

    def fail(self, _reason):
        # Reasons from callers can contain provider text. Retain no such text.
        with self._transaction() as state:
            state["failed"] = True

    def remaining_timeout(self, requested=20):
        self.assert_healthy()
        if requested <= 0:
            raise TransitionError("invalid request timeout")
        remaining = requested if self.deadline is None else min(requested, self.deadline - self.monotonic())
        if remaining <= 0:
            self.fail("complete sweep deadline exceeded")
            raise TransitionError("complete sweep deadline exceeded")
        return remaining

    def _trace(self, state, item):
        if len(state["trace"]) >= TRACE_LIMIT:
            state["failed"] = True
            raise TransitionError("accounting trace bound exceeded")
        state["trace"].append(item)

    def record_outcome(self, request_id, *, status, complete):
        if (not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}(?::[1-9][0-9]*)?", request_id)
                or (status is not None and (type(status) is not int or not 100 <= status <= 599))
                or type(complete) is not bool):
            self.fail("invalid outcome")
            raise TransitionError("invalid outcome")
        with self._transaction() as state:
            self._trace(state, {"requestId": request_id, "status": status, "complete": complete})
            request = state["primaryRequests"].get(request_id)
            if request is not None and complete:
                request["complete"] = True
                if request["observed"]:
                    del state["primaryRequests"][request_id]
            if status is None or not complete:
                state["failed"] = True

    def record_unknown_graphql_cost(self):
        with self._transaction() as state:
            self._trace(state, {"bucket": "GraphQL", "costMode": "unknown",
                                "actualCost": None, "chargedBound": None})
            state["failed"] = True

    def charge(self, bucket, cost, label, *, completion=False, request_id=None):
        integer(cost)
        if bucket not in ("REST", "GraphQL"):
            raise TransitionError("unknown primary bucket")
        with self._transaction() as state:
            self._charge(state, bucket, cost, label, completion=completion, request_id=request_id)

    def _charge(self, state, bucket, cost, label, *, completion=False, request_id=None):
        if request_id is not None:
            request = state["primaryRequests"].get(request_id)
            if request is None or request["bucket"] != bucket or request["observed"]:
                state["failed"] = True
                raise TransitionError("primary charge lacks request association")
        if not completion:
            self._healthy(state)
        if self._cancellation and cost:
            if bucket != "REST" or self.current_pool != "shared-tools":
                raise TransitionError("invalid cancellation accounting")
            state["cancellationRequests"] += cost
            if state["cancellationRequests"] > 2:
                state["failed"] = True
                raise TransitionError("cancellation allowance exceeded")
        index = 0 if bucket == "REST" else 1
        pool = "shared-tools" if self.job == "external-acceptance" else self.current_pool
        counts = state["used"].setdefault(pool, [0, 0])
        counts[index] += cost
        if request_id is not None:
            request["cost"] += cost
        self._trace(state, {"pool": pool, "bucket": bucket, "cost": cost,
                            "labelDigest": hashlib.sha256(str(label).encode()).hexdigest()})
        if counts[index] > self.limits(pool)[index]:
            state["failed"] = True
            raise TransitionError("owned request allowance exceeded")

    def begin_primary(self, request_id, bucket, label):
        self._request_identity(request_id)
        if bucket not in ("REST", "GraphQL"):
            raise TransitionError("unknown primary bucket")
        with self._transaction() as state:
            self._healthy(state)
            if request_id in state["primaryRequests"] or len(state["primaryRequests"]) >= TRANSPORT_REQUEST_LIMIT:
                state["failed"] = True
                raise TransitionError("primary request association bound exceeded")
            pending = sum(r["cost"] for r in state["primaryRequests"].values() if r["bucket"] == bucket)
            state["primaryRequests"][request_id] = {
                "bucket": bucket, "startedAt": self._clock(state),
                "settledBefore": self._charged(state, bucket) - pending,
                "cost": 0, "observed": False, "complete": False}
            self._charge(state, bucket, 1, label, request_id=request_id)

    def charge_transport(self, label, *, requests=1, bytes=0, completion=False):
        integer(requests)
        integer(bytes)
        with self._transaction() as state:
            # Completion/cancellation bytes must remain counted after failure.
            state["transport"]["requests"] += requests
            state["transport"]["bytes"] += bytes
            self._trace(state, {"transport": hashlib.sha256(str(label).encode()).hexdigest(),
                                "requests": requests, "bytes": bytes})
            if (state["transport"]["requests"] > TRANSPORT_REQUEST_LIMIT
                    or state["transport"]["bytes"] > TRANSPORT_BYTE_LIMIT):
                state["failed"] = True
                raise TransitionError("transport allowance exceeded")
            if not completion:
                self._healthy(state)

    def _quota(self, bucket, *, remaining, reset, limit, check_time=True):
        if bucket not in ("REST", "GraphQL"):
            raise TransitionError("unknown primary quota")
        for value in (remaining, reset, limit):
            integer(value)
        if (not 0 <= remaining <= limit or limit < 1000
                or (check_time and reset <= self.clock())):
            raise TransitionError("unknown or contradictory primary quota")

    def observe_quota(self, bucket, *, remaining, reset, limit, completion=False, request_id=None):
        try:
            self._quota(bucket, remaining=remaining, reset=reset, limit=limit)
        except TransitionError:
            self.fail("unknown quota")
            raise
        with self._transaction() as state:
            if not completion:
                self._healthy(state)
            now = self._clock(state)
            request = state["primaryRequests"].get(request_id)
            if (request is None or request["bucket"] != bucket or request["observed"]
                    or request["startedAt"] > now):
                state["failed"] = True
                raise TransitionError("quota lacks its primary request association")
            previous = state["quota"].get(bucket)
            if previous and limit != previous["limit"]:
                state["failed"] = True
                raise QuotaWindowError(bucket, previous, remaining=remaining, reset=reset, limit=limit)
            # Only a valid response to a fresh post-expiry request retires an
            # old constraint. A different reset never supplies renewal credit.
            constraints = {item["reset"]: item["capacity"] for item in state["quotaConstraints"].get(bucket, [])
                           if item["reset"] > request["startedAt"]}
            capacity = remaining + request["settledBefore"]
            constraints[reset] = min(capacity, constraints.get(reset, capacity))
            count = len(constraints) + sum(len(items) for name, items in state["quotaConstraints"].items() if name != bucket)
            if count > TRANSPORT_REQUEST_LIMIT:
                state["failed"] = True
                raise TransitionError("primary constraint bound exceeded")
            state["quotaConstraints"][bucket] = [{"reset": end, "capacity": value} for end, value in sorted(constraints.items())]
            state["quota"][bucket] = {"remaining": remaining, "reset": reset, "limit": limit}
            request["observed"] = True
            if request["complete"]:
                del state["primaryRequests"][request_id]

    def require_headroom(self, *, future_rest, future_graphql, first_tick=None, periodic_end=None):
        with self._transaction() as state:
            self._healthy(state)
            now = self._clock(state)
            if first_tick is not None and (type(first_tick) is not int or first_tick % 120
                                           or periodic_end is None or self._time(periodic_end) < now):
                raise TransitionError("invalid periodic headroom horizon")
            result = {}
            for bucket, required in (("REST", future_rest), ("GraphQL", future_graphql)):
                integer(required)
                constraints = state["quotaConstraints"].get(bucket)
                if not constraints:
                    state["failed"] = True
                    raise TransitionError("insufficient current-window primary quota")
                result[bucket] = required
                for item in constraints:
                    demand = required
                    if first_tick is not None:
                        end = min(item["reset"], periodic_end)
                        ticks = max(0, min(31, math.floor(end / 120) - first_tick // 120 + 1))
                        demand += ticks * (15 if bucket == "REST" else 5)
                    result[bucket] = max(result[bucket], demand)
                    if item["reset"] <= now or item["capacity"] - self._charged(state, bucket) < demand:
                        state["failed"] = True
                        raise TransitionError("insufficient current-window primary quota")
            return result

    @contextmanager
    def cancellation(self):
        if self.job not in ("source-guard", "publisher-guard") or self._cancellation:
            raise TransitionError("invalid cancellation owner")
        previous_deadline = self.deadline
        self._cancellation = True
        self.deadline = self.monotonic() + 15
        try:
            yield self
        finally:
            self._cancellation = False
            self.deadline = previous_deadline


def _control(environment):
    if any(not environment.get(name) for name in _ENV_KEYS):
        raise TransitionError("missing live tool controls")
    directory = private_directory(Path(environment[_ENV_KEYS[0]]))
    if environment[_ENV_KEYS[3]] != str(directory / "tools.py"):
        raise TransitionError("changed supervisor selection")
    config = decode(private_file(directory / "config.json", limit=8192))
    if (config.get("schema") != 1 or config.get("job") != environment[_ENV_KEYS[2]]
            or not hmac.compare_digest(str(config.get("nonce", "")), environment[_ENV_KEYS[1]])
            or config.get("directory") != str(directory)):
        raise TransitionError("changed supervisor binding")
    if set(config.get("digests", {})) != set(ASSET_ENV):
        raise TransitionError("incomplete bootstrap closure")
    for name in ASSET_ENV:
        if hashlib.sha256(private_file(directory / name, limit=1024 * 1024)).hexdigest() != config["digests"][name]:
            raise TransitionError("changed trusted tool bytes")
    info = (directory / "control.sock").lstat()
    if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise TransitionError("changed supervisor listener")
    return directory, config


def _exchange(directory, frame):
    payload = canonical(frame)
    if len(payload) > FRAME_LIMIT:
        raise TransitionError("control frame too large")
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(35 if frame.get("operation") in {"finish", "gh-finish", "curl-finish"} else 10)
        client.connect(str(directory / "control.sock"))
        client.sendall(payload)
        answer = bytearray()
        while not answer.endswith(b"\n"):
            chunk = client.recv(FRAME_LIMIT + 1 - len(answer))
            if not chunk:
                raise TransitionError("missing supervisor disposition")
            answer.extend(chunk)
            if len(answer) > FRAME_LIMIT:
                raise TransitionError("oversized supervisor disposition")
    reply = decode(answer)
    if not isinstance(reply, dict) or reply.get("accepted") is not True:
        raise TransitionError("supervisor permanently refused")
    return reply


def assert_supervisor(environment, job):
    directory, config = _control(environment)
    if config["job"] != job:
        raise TransitionError("supervisor belongs to another job")
    _exchange(directory, {"schema": 1, "nonce": config["nonce"], "operation": "ping"})
    return directory


def default_budget_path(environment, job):
    directory = assert_supervisor(environment, job)
    return directory / "ledger.json"


def _route(frame):
    method, host, path, bucket = (frame.get(key) for key in ("method", "host", "path", "bucket"))
    if (method not in {"GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"}
            or not isinstance(host, str) or len(host) > 255
            or not re.fullmatch(r"[a-z0-9.-]+", host)
            or not isinstance(path, str) or not path.startswith("/")
            or len(path) > 2048 or re.search(r"[\x00-\x20\x7f?#]", path)):
        raise TransitionError("unknown tool route")
    expected = None
    if host == "api.github.com":
        expected = "GraphQL" if path == "/graphql" and method == "POST" else "REST"
    elif host == "github.com" and re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:info/refs|git-upload-pack)", path):
        expected = "Git"
    elif host.endswith(".actions.githubusercontent.com") and method == "POST":
        expected = "runtime"
    elif host.endswith(".blob.core.windows.net"):
        expected = "blob"
    elif host in {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com", "codeload.github.com"}:
        expected = "download"
    if expected != bucket:
        raise TransitionError("unaccounted tool transport")
    return bucket


class Supervisor:
    """Live per-job disposition; records are private and never evidence inputs."""
    def __init__(self, directory, config):
        self.directory, self.config = directory, config
        self.config_bytes = private_file(directory / "config.json", limit=8192)
        self.budget = RequestBudget(config["job"], path=directory / "ledger.json")
        self.budget.current_pool = "shared-tools"
        self.clients = {}
        self.started = time.monotonic()
        self.stopping = False
        self._lock = threading.RLock()
        self.gh = None
        self.curl = None
        self._gh_selected = False
        self._curl_selected = set()

    def _custody(self, *, completion=False):
        environment = dict(zip(_ENV_KEYS, (str(self.directory), self.config["nonce"],
                                          self.config["job"], str(self.directory / "tools.py"))))
        _control(environment)
        if private_file(self.directory / "config.json", limit=8192) != self.config_bytes:
            raise TransitionError("changed supervisor configuration")
        if time.monotonic() - self.started > JOB_LIFETIMES[self.config["job"]]:
            self.budget.fail("supervisor lifetime exceeded")
            if not completion:
                raise TransitionError("supervisor lifetime exceeded")

    def _module(self, name):
        self._custody()
        if __package__:
            return importlib.import_module(".ci_policy_transition_" + name, __package__)
        # Only the exact five authenticated bootstrap assets are in this root.
        if str(self.directory) not in sys.path:
            sys.path.insert(0, str(self.directory))
        return importlib.import_module(name)

    def _observe_owned(self, kind, frame):
        return self.accept({"schema": 1, "nonce": self.config["nonce"], **frame}, trusted_kind=kind)

    def _policy(self, root):
        """Load only authenticated T bytes through the unchanged native factory."""
        root = Path(root)
        if not root.is_absolute() or root.resolve(strict=True) != root:
            raise TransitionError("invalid trusted policy root")
        environment = {"PATH": "/usr/bin:/bin", "HOME": str(self.directory),
                       "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                       "GIT_CONFIG_COUNT": "0", "GIT_TERMINAL_PROMPT": "0"}
        def git(*args):
            result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c",
                "core.fsmonitor=false", "-C", str(root), *args], env=environment,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=10, check=True)
            return result.stdout
        if git("rev-parse", "HEAD").decode().strip() != self.config["rootSha"]:
            raise TransitionError("wrong trusted policy commit")
        paths = ("deployment/postgresql/native_release_identity.py",
                 "deployment/postgresql/ofarm_ed25519/native_release_identity.json",
                 "deployment/postgresql/ofarm_ed25519/native_evidence_receipt.json")
        verified = {}
        for relative in paths:
            path = root / relative
            if path.resolve(strict=True) != path or not path.is_file():
                raise TransitionError("changed native policy custody")
            data = path.read_bytes()
            if len(data) > 2 * 1024 ** 2 or data != git("show", self.config["rootSha"] + ":" + relative):
                raise TransitionError("changed native policy bytes")
            verified[relative] = data
        # Execute the already authenticated source bytes, never a cached pyc.
        module = types.ModuleType("_ofarm_transition_frozen_native_identity")
        module.__file__ = str(root / paths[0])
        sys.modules[module.__name__] = module
        try:
            exec(compile(verified[paths[0]], module.__file__, "exec"), module.__dict__)
            return self._module("gh_relay").frozen_release_policy(identity_module=module)
        finally:
            sys.modules.pop(module.__name__, None)

    def lifecycle(self, frame):
        operation = frame.get("operation")
        try:
            self._custody()
            base = {"schema", "nonce", "operation"}
            extras = {"gh-start": {"policyRoot", "token"}, "gh-check": set(), "gh-finish": set(),
                      "curl-start": {"name"}, "curl-finish": set(), "finish": set()}
            if (set(frame) != base | extras[operation] or frame["schema"] != 1
                    or not isinstance(frame["nonce"], str)
                    or not hmac.compare_digest(frame["nonce"], self.config["nonce"])):
                raise TransitionError("invalid lifecycle binding")
            if operation == "finish":
                # Stop admission first, then drain/abort without the observation
                # lock so every worker can settle bytes into the one ledger.
                self.stopping = True
                self.abort_lifecycles()
                with self._lock:
                    self.budget.assert_healthy()
                    if any(not c["closed"] for c in self.clients.values()):
                        raise TransitionError("tool process lacks final disposition")
                return {"accepted": True}
            if operation == "gh-finish":
                if self.gh is None:
                    raise TransitionError("gh lifecycle unavailable")
                selected, self.gh = self.gh, None
                selected.finish()
            elif operation == "curl-finish":
                if self.curl is None:
                    raise TransitionError("curl lifecycle unavailable")
                selected, self.curl = self.curl, None
                selected.finish()
            else:
                self.budget.assert_healthy()
                if operation == "gh-start":
                    if self.config["job"] != "conformance" or self._gh_selected:
                        raise TransitionError("unowned gh lifecycle")
                    self._gh_selected = True
                    relay = self._module("gh_relay")
                    policy = self._policy(frame["policyRoot"])
                    self.gh = self._module("execution").GhLifecycle(self.directory, policy,
                        relay.RelayLimits(max_requests=128, max_response_bytes=2 * 1024 ** 3,
                            lifetime_seconds=min(3600, JOB_LIFETIMES[self.config["job"]])),
                        lambda item: self._observe_owned("gh", item), self.budget.fail)
                    values = self.gh.start({"GH_TOKEN": frame["token"]})
                    return {"accepted": True, "environment": values}
                if operation == "gh-check":
                    if self.gh is None:
                        raise TransitionError("gh lifecycle unavailable")
                    self.gh.check()
                elif operation == "curl-start":
                    name = frame["name"]
                    allowed = {"conformance": {"buildx-amd64", "gh-amd64"},
                               "native-amd64": {"buildx-amd64"}, "native-arm64": {"buildx-arm64"}}
                    if (name not in allowed.get(self.config["job"], set()) or name in self._curl_selected
                            or self.curl is not None):
                        raise TransitionError("unowned curl lifecycle")
                    self._curl_selected.add(name)
                    self.curl = self._module("curl").CurlLifecycle(self.directory, name,
                        lambda item: self._observe_owned("curl", item), self.budget.fail)
                    return {"accepted": True, "environment": self.curl.start()}
            self.budget.assert_healthy()
            return {"accepted": True}
        except BaseException:
            self.budget.fail("tool lifecycle refused")
            if operation == "finish":
                self.stopping = True
            self.abort_lifecycles()
            return {"accepted": False, "reason": "terminal-refusal"}

    def abort_lifecycles(self):
        for name in ("gh", "curl"):
            selected = getattr(self, name)
            if selected is not None:
                setattr(self, name, None)
                try:
                    selected.abort()
                except BaseException:
                    self.budget.fail("tool lifecycle cleanup refused")

    def accept(self, frame, *, trusted_kind=None):
        # Relay drain must not hold this lock: its workers settle their final
        # observations through this same serialized accounting authority.
        if isinstance(frame, dict) and frame.get("operation") in {
                "gh-start", "gh-check", "gh-finish", "curl-start", "curl-finish", "finish"}:
            return self.lifecycle(frame)
        with self._lock:
            return self._accept(frame, trusted_kind=trusted_kind)

    def _accept(self, frame, *, trusted_kind=None):
        try:
            self._custody(completion=isinstance(frame, dict) and frame.get("operation") in {"response", "end", "close"})
            if (not isinstance(frame, dict) or frame.get("schema") != 1
                    or not isinstance(frame.get("nonce"), str)
                    or not hmac.compare_digest(frame["nonce"], self.config["nonce"])):
                raise TransitionError("invalid control binding")
            operation = frame.get("operation")
            if operation in ("ping", "check", "finish"):
                if set(frame) != {"schema", "nonce", "operation"}:
                    raise TransitionError("unknown control fields")
                self.budget.assert_healthy()
                if operation != "ping" and any(not client["closed"] for client in self.clients.values()):
                    raise TransitionError("tool process lacks final disposition")
                if operation == "finish":
                    self.stopping = True
                return {"accepted": True}
            allowed = {"schema", "nonce", "processId", "sequence", "operation"}
            extras = {"open": {"kind", "pid", "ppid"},
                      "begin": {"requestId", "method", "host", "path", "bucket"},
                      "response": {"requestId", "status", "quota"},
                      "end": {"requestId", "bytes", "complete"},
                      "fatal": {"reason"}, "close": set()}
            if operation not in extras or set(frame) != allowed | extras[operation]:
                raise TransitionError("unknown observation shape")
            process_id = frame["processId"]
            if not isinstance(process_id, str) or str(uuid.UUID(process_id)) != process_id:
                raise TransitionError("invalid observer identity")
            sequence = integer(frame["sequence"])
            client = self.clients.get(process_id)
            if operation == "open":
                if (client or sequence != 0 or frame["kind"] != (trusted_kind or "node") or len(self.clients) >= 128):
                    raise TransitionError("invalid observer opening")
                integer(frame["pid"], 1)
                integer(frame["ppid"], 1)
                os.kill(frame["pid"], 0)
                client = {"sequence": 0, "pid": frame["pid"], "kind": frame["kind"],
                          "closed": False, "requests": {}}
                self.clients[process_id] = client
            elif not client or client["closed"] or sequence != client["sequence"] + 1:
                raise TransitionError("missing or reordered tool observation")
            client["sequence"] = sequence
            if operation == "begin":
                request_id = frame["requestId"]
                if (not isinstance(request_id, str) or not re.fullmatch(re.escape(process_id) + r":[1-9][0-9]*", request_id)
                        or request_id in client["requests"] or len(client["requests"]) >= 512):
                    raise TransitionError("invalid request association")
                bucket = frame["bucket"] if trusted_kind == "gh" and frame["bucket"] == "tuf" else _route(frame)
                if bucket == "GraphQL" and client["kind"] != "gh":
                    raise TransitionError("unenumerated observer GraphQL operation")
                # Install the association before any charge can refuse; a
                # failed or already dispatched request still needs settlement.
                client["requests"][request_id] = {"bucket": bucket, "response": False,
                    "ended": False, "status": None, "priorQuota": self.budget.quota.get(bucket)}
                self.budget.charge_transport(bucket)
                if bucket in ("REST", "GraphQL"):
                    self.budget.begin_primary(request_id.replace("-", ""), bucket, "tool request")
            elif operation in ("response", "end"):
                request = client["requests"].get(frame["requestId"])
                if request is None or request["ended"]:
                    raise TransitionError("unknown request disposition")
                if operation == "response":
                    status = integer(frame["status"], 200)
                    if request["response"] or status > 599:
                        raise TransitionError("invalid response observation")
                    request["response"] = True
                    request["status"] = status
                    if status in (403, 429):
                        # Refuse immediately, then retain independently known
                        # quota/cost for this already-started request.
                        self.budget.fail("provider refused tool request")
                    if request["bucket"] in ("REST", "GraphQL"):
                        self._observe_primary(request["bucket"], frame["quota"], request["priorQuota"],
                                              request_id=frame["requestId"].replace("-", ""))
                    elif frame["quota"] is not None:
                        raise TransitionError("unknown applicable quota")
                else:
                    request["ended"] = True
                    if request["bucket"] == "GraphQL" and not request["response"]:
                        self.budget.record_unknown_graphql_cost()
                    self.budget.charge_transport(request["bucket"], requests=0,
                        bytes=integer(frame["bytes"]), completion=True)
                    self.budget.record_outcome(frame["requestId"].replace("-", ""),
                        status=request["status"], complete=frame["complete"] is True and request["response"])
                    if not request["response"] or frame["complete"] is not True:
                        raise TransitionError("incomplete tool response")
            elif operation == "fatal":
                raise TransitionError("tool observer refused")
            elif operation == "close":
                if any(not request["ended"] for request in client["requests"].values()):
                    raise TransitionError("tool process has unfinished requests")
                client["closed"] = True
            self.budget.assert_healthy()
            return {"accepted": True, "sequence": sequence}
        except (TransitionError, OSError, ValueError, KeyError, TypeError):
            self.budget.fail("invalid supervisor observation")
            if isinstance(frame, dict) and frame.get("operation") == "finish":
                self.stopping = True
            return {"accepted": False, "reason": "terminal-refusal"}

    def _observe_primary(self, bucket, quota, prior=None, *, request_id=None):
        known = False
        try:
            if (not isinstance(quota, dict) or quota.get("bucket") != bucket
                    or not {"bucket", "remaining", "reset", "limit"} <= set(quota)
                    or set(quota) - {"bucket", "remaining", "reset", "limit", "used", "cost"}):
                raise TransitionError("missing applicable primary quota")
            if bucket == "GraphQL":
                # Same-window absolute used is only a conservative bound, never
                # this request's attributed cost or a snapshot difference.
                if "cost" in quota:
                    cost = integer(quota["cost"], 1)
                else:
                    # Expiry prevents current headroom, but does not erase a
                    # known bound for an already-started same-window request.
                    self.budget._quota(bucket, remaining=quota["remaining"],
                        reset=quota["reset"], limit=quota["limit"], check_time=False)
                    used = integer(quota.get("used"), 1)
                    if (prior is None or quota["reset"] != prior["reset"]
                            or quota["limit"] != prior["limit"]
                            or used != quota["limit"] - quota["remaining"]):
                        raise TransitionError("GraphQL point cost unavailable")
                    cost = used
                known = True
                try:
                    self.budget.charge(bucket, cost - 1, "conservative tool GraphQL points", completion=True,
                                       request_id=request_id)
                finally:
                    with self.budget._transaction() as state:
                        self.budget._trace(state, {"bucket": bucket,
                            "costMode": "actual" if "cost" in quota else "absolute-used-upper-bound",
                            "actualCost": quota.get("cost"), "chargedBound": cost,
                            "responseUsed": quota.get("used"), "reset": quota["reset"],
                            "limit": quota["limit"], "responseRemaining": quota["remaining"]})
            self.budget.observe_quota(bucket, remaining=quota["remaining"], reset=quota["reset"],
                limit=quota["limit"], completion=True, request_id=request_id)
        except (TransitionError, ValueError, KeyError, TypeError):
            if bucket == "GraphQL" and not known:
                self.budget.record_unknown_graphql_cost()
            self.budget.fail("required primary quota unavailable")
            raise


def serve(directory):
    config = decode(private_file(directory / "config.json", limit=8192))
    supervisor = Supervisor(directory, config)
    listener = directory / "control.sock"
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(str(listener))
        os.chmod(listener, 0o600)
        server.listen(8)
        server.settimeout(1)
        try:
            while not supervisor.stopping:
                if time.monotonic() - supervisor.started > JOB_LIFETIMES[config["job"]]:
                    supervisor.budget.fail("supervisor lifetime exceeded")
                    break
                try:
                    connection, _ = server.accept()
                except TimeoutError:
                    continue
                with connection:
                    connection.settimeout(5)
                    data = bytearray()
                    try:
                        while not data.endswith(b"\n") and len(data) <= FRAME_LIMIT:
                            part = connection.recv(FRAME_LIMIT + 1 - len(data))
                            if not part:
                                raise TransitionError("partial observer frame")
                            data.extend(part)
                        if len(data) > FRAME_LIMIT:
                            raise TransitionError("oversized observer frame")
                        reply = supervisor.accept(decode(data))
                    except (TransitionError, OSError):
                        supervisor.budget.fail("observer control failed")
                        reply = {"accepted": False, "reason": "terminal-refusal"}
                    try:
                        connection.sendall(canonical(reply))
                    except OSError:
                        supervisor.budget.fail("disposition was not delivered")
        finally:
            supervisor.abort_lifecycles()
            listener.unlink(missing_ok=True)
    # Keep only a private completion digest, never a reusable acceptance flag.
    write_new(directory / "stopped.json", canonical({"pid": os.getpid(), "failed": supervisor.budget._snapshot("failed")}))


def start(args):
    directory = private_directory(Path(args.directory))
    if set(path.name for path in directory.iterdir()) != set(ASSET_ENV):
        raise TransitionError("bootstrap directory is not fresh")
    if (args.job not in TOOL_ALLOCATIONS or args.run_attempt != 1
            or args.run_id <= 0 or not re.fullmatch(r"[0-9a-f]{40}", args.root_sha)):
        raise TransitionError("invalid supervisor job binding")
    digests = {name: hashlib.sha256(private_file(directory / name, limit=1024 * 1024)).hexdigest()
               for name in ASSET_ENV}
    if any(os.environ.get(key) != digests[name] for name, key in ASSET_ENV.items()):
        raise TransitionError("bootstrap byte authentication failed")
    if Path(__file__).resolve() != directory / "tools.py":
        raise TransitionError("supervisor was not selected by bootstrap")
    config = {"schema": 1, "directory": str(directory), "nonce": secrets.token_hex(32),
              "job": args.job, "runId": args.run_id, "runAttempt": 1,
              "rootSha": args.root_sha, "digests": digests}
    write_new(directory / "config.json", canonical(config))
    RequestBudget(args.job, path=directory / "ledger.json")
    # Dynamic imports must not add bytecode files to the closed cleanup root.
    # The child has its own interpreter flags and a sanitized environment.
    process = subprocess.Popen([sys.executable, "-I", "-S", "-B", str(directory / "tools.py"), "serve", "--directory", str(directory), "--await-start"],
                               stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               env={"PATH": "/usr/bin:/bin", "HOME": str(directory), "LANG": "C.UTF-8"},
                               start_new_session=True, close_fds=True)
    try:
        write_new(directory / "process.json", canonical({"pid": process.pid,
                  "identity": _process_identity(process.pid)}))
        process.stdin.write(b"G")
        process.stdin.close()
        environment = dict(zip(_ENV_KEYS, (str(directory), config["nonce"], args.job, str(directory / "tools.py"))))
        for _ in range(100):
            if process.poll() is not None:
                raise TransitionError("supervisor failed to start")
            try:
                _control(environment)
                _exchange(directory, {"schema": 1, "nonce": config["nonce"], "operation": "ping"})
                break
            except (TransitionError, OSError):
                time.sleep(0.05)
        else:
            raise TransitionError("supervisor startup deadline exceeded")
        _write_environment(args.github_env, environment)
    except BaseException:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        else:
            process.wait()
        (directory / "control.sock").unlink(missing_ok=True)
        raise


def _write_environment(path, values):
    if any(not re.fullmatch(r"[A-Z][A-Z0-9_]+", key) or not isinstance(value, str)
           or any(c in value for c in "\r\n\x00") for key, value in values.items()):
        raise TransitionError("invalid typed environment")
    with open(path, "a", encoding="utf-8") as output:
        output.write("".join(key + "=" + value + "\n" for key, value in values.items()))
        output.flush()


def _process_identity(pid):
    integer(pid, 1)
    # A pid alone is not sufficient authority to signal a later unrelated task.
    if sys.platform == "linux":
        proc = Path("/proc") / str(pid)
        data = (proc / "stat").read_text().rsplit(") ", 1)[1].split()
        if data[0] == "Z":
            raise ProcessLookupError()
        return {"start": data[19], "command": hashlib.sha256((proc / "cmdline").read_bytes()).hexdigest()}
    result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "lstart=", "-o", "command="],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=2)
    if result.returncode or not result.stdout.strip() or b"<defunct>" in result.stdout:
        raise ProcessLookupError()
    return {"ps": hashlib.sha256(result.stdout).hexdigest()}


def _stop_process(process):
    pid = integer(process["pid"], 1)
    for signum in (signal.SIGTERM, signal.SIGKILL):
        try:
            if _process_identity(pid) != process["identity"]:
                raise TransitionError("supervisor process identity changed")
            os.kill(pid, signum)
        except (ProcessLookupError, FileNotFoundError):
            return
        for _ in range(100):
            try:
                if _process_identity(pid) != process["identity"]:
                    raise TransitionError("supervisor process identity changed")
            except (ProcessLookupError, FileNotFoundError):
                return
            time.sleep(0.02)
    raise TransitionError("supervisor did not stop")


def cleanup_start(directory):
    directory = private_directory(directory)
    for name, key in ASSET_ENV.items():
        digest = hashlib.sha256(private_file(directory / name, limit=1024 ** 2)).hexdigest()
        if os.environ.get(key) != digest:
            raise TransitionError("startup cleanup byte authentication failed")
    process_path = directory / "process.json"
    if process_path.exists():
        _stop_process(decode(private_file(process_path, limit=2048)))
    # Before durable process registration the child is blocked on stdin. The
    # failed client's death/pipe close makes it exit without starting a listener.
    elif (directory / "control.sock").exists():
        raise TransitionError("unregistered supervisor listener")
    (directory / "control.sock").unlink(missing_ok=True)


def finish(environment):
    directory = private_directory(Path(environment[_ENV_KEYS[0]]))
    config = decode(private_file(directory / "config.json", limit=8192))
    if (config.get("directory") != str(directory) or not hmac.compare_digest(
            str(config.get("nonce", "")), environment[_ENV_KEYS[1]])):
        raise TransitionError("cleanup binding changed")
    failed = False
    try:
        _control(environment)
        _exchange(directory, {"schema": 1, "nonce": config["nonce"], "operation": "finish"})
    except (TransitionError, OSError):
        failed = True
    process = decode(private_file(directory / "process.json", limit=2048))
    for _ in range(100):
        if (directory / "stopped.json").exists():
            break
        time.sleep(0.05)
    else:
        failed = True
        _stop_process(process)
    if (directory / "stopped.json").exists():
        stopped = decode(private_file(directory / "stopped.json", limit=1024))
        if stopped != {"pid": process["pid"], "failed": False}:
            failed = True
    # A stopped marker is written immediately before process exit. Verify it
    # actually exits before deleting any bytes it may still be using.
    _stop_process(process)
    expected = set(ASSET_ENV) | {"config.json", "ledger.json", "ledger.json.lock", "process.json", "stopped.json", "control.sock"}
    if set(path.name for path in directory.iterdir()) - expected:
        raise TransitionError("unowned cleanup paths")
    for path in directory.iterdir():
        if path.is_symlink() or path.is_dir():
            raise TransitionError("changed cleanup custody")
        path.unlink()
    directory.rmdir()
    if failed:
        raise TransitionError("tool cleanup cannot establish success")


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    boot = sub.add_parser("start")
    boot.add_argument("--directory", required=True)
    boot.add_argument("--job", required=True)
    boot.add_argument("--run-id", type=int, required=True)
    boot.add_argument("--run-attempt", type=int, required=True)
    boot.add_argument("--root-sha", required=True)
    boot.add_argument("--github-env", required=True)
    daemon = sub.add_parser("serve")
    daemon.add_argument("--directory", required=True)
    daemon.add_argument("--await-start", action="store_true")
    cleanup = sub.add_parser("cleanup-start")
    cleanup.add_argument("--directory", required=True)
    for name in ("gh-start", "curl-start"):
        selected = sub.add_parser(name)
        if name == "gh-start":
            selected.add_argument("--policy-root", required=True)
        else:
            selected.add_argument("--name", required=True)
        outputs = selected.add_mutually_exclusive_group(required=True)
        outputs.add_argument("--github-env")
        outputs.add_argument("--github-output")
    for name in ("gh-check", "gh-finish", "curl-finish"):
        sub.add_parser(name)
    rpc = sub.add_parser("rpc")
    rpc.add_argument("--control")
    sub.add_parser("check")
    sub.add_parser("finish")
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            start(args)
        elif args.command == "serve":
            if args.await_start and sys.stdin.buffer.read(1) != b"G":
                return 1
            serve(private_directory(Path(args.directory)))
        elif args.command == "cleanup-start":
            cleanup_start(Path(args.directory))
        elif args.command == "rpc":
            directory, _ = _control(os.environ)
            if args.control and args.control != str(directory):
                raise TransitionError("changed observer control path")
            frame = decode(sys.stdin.buffer.read(FRAME_LIMIT + 1))
            result = _exchange(directory, frame)
            sys.stdout.buffer.write(canonical(result))
        elif args.command == "check":
            directory, config = _control(os.environ)
            _exchange(directory, {"schema": 1, "nonce": config["nonce"], "operation": "check"})
        elif args.command.startswith(("gh-", "curl-")):
            directory, config = _control(os.environ)
            frame = {"schema": 1, "nonce": config["nonce"], "operation": args.command}
            if args.command == "gh-start":
                token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
                if (not token or (os.environ.get("GH_TOKEN") and os.environ.get("GITHUB_TOKEN")
                                  and os.environ["GH_TOKEN"] != os.environ["GITHUB_TOKEN"])):
                    raise TransitionError("ambiguous gh credential")
                frame.update(policyRoot=args.policy_root, token=token)
            elif args.command == "curl-start":
                frame["name"] = args.name
            reply = _exchange(directory, frame)
            if args.command.endswith("-start"):
                values = reply.get("environment")
                keys = ({"CURL_HOME"} if args.command == "curl-start" else {
                    "GH_CONFIG_DIR", "GH_CACHE_DIR", "GH_HOST", "GH_PROMPT_DISABLED",
                    "GH_NO_UPDATE_NOTIFIER", "GH_NO_EXTENSION_UPDATE_NOTIFIER", "NO_COLOR", "CLICOLOR"})
                if not isinstance(values, dict) or set(values) != keys:
                    raise TransitionError("unknown lifecycle environment")
                _write_environment(args.github_env or args.github_output, values)
        else:
            finish(os.environ)
    except (TransitionError, OSError, ValueError, KeyError, TypeError):
        print("transition tool controls refused", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
