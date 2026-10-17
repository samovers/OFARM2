"""In-process gh lifecycle adapter for the one trusted tool supervisor.

The supervisor authenticates this module, the relay and selected T before
construction. ``observe`` is a private direct method, never an RPC route that
allows a Node observer to claim gh authority. Only the supervisor owns budgets,
credential selection, process termination and the final workflow disposition.
"""
from __future__ import annotations

import os
from pathlib import Path
import threading
from typing import Callable, Mapping
import uuid

if __package__:
    from .ci_policy_transition_gh_relay import (
        FrozenReleasePolicy, GhRelay, RelayError, RelayEvent, RelayLimits, RelaySummary,
    )
else:  # Exact embedded sibling modules, authenticated by the bootstrap.
    from gh_relay import (
        FrozenReleasePolicy, GhRelay, RelayError, RelayEvent, RelayLimits, RelaySummary,
    )


RELAY_ENV_KEYS = (
    "GH_CONFIG_DIR", "GH_CACHE_DIR", "GH_HOST", "GH_PROMPT_DISABLED",
    "GH_NO_UPDATE_NOTIFIER", "GH_NO_EXTENSION_UPDATE_NOTIFIER", "NO_COLOR", "CLICOLOR",
)


class GhLifecycle:
    def __init__(self, directory: Path, policy: FrozenReleasePolicy, limits: RelayLimits,
                 observe: Callable[[dict], dict], on_terminal: Callable[[str], None]) -> None:
        self._observe, self._notify = observe, on_terminal
        self._lock = threading.RLock()
        self._process_id = str(uuid.uuid4())
        self._sequence = -1
        self._started = False
        self._finished = False
        self._failed = False
        self._entered = False
        self._summary: RelaySummary | None = None
        self._environment: dict[str, str] | None = None
        self._relay = GhRelay(directory, policy, limits, self._account, self._terminal)

    def _send(self, operation: str, **fields: object) -> None:
        # One total callback order even when upstream responses race. The owning
        # supervisor adds its own schema/nonce for the existing ledger protocol.
        with self._lock:
            self._sequence += 1
            frame = {"processId": self._process_id, "sequence": self._sequence,
                     "operation": operation, **fields}
            try:
                result = self._observe(frame)
                if (not isinstance(result, dict) or result.get("accepted") is not True
                        or result.get("sequence") != self._sequence):
                    raise RelayError("gh observation refused")
            except BaseException:
                self._failed = True
                raise RelayError("gh observation refused") from None

    def _terminal(self, _reason: str) -> None:
        with self._lock:
            first = not self._failed
            self._failed = True
        if first:
            try:
                self._send("fatal", reason="gh relay refused")
            except RelayError:
                pass
        # Always notify, including when the accounting callback itself failed.
        self._notify("gh relay refused")

    def _account(self, event: RelayEvent) -> None:
        request_id = self._process_id + ":" + str(event.request_id)
        if event.phase == "request":
            bucket = {"rest": "REST", "graphql": "GraphQL", "tuf": "tuf",
                      "blob": "download" if event.host == "release-assets.githubusercontent.com" else "blob"}[event.bucket]
            self._send("begin", requestId=request_id, method=event.method, host=event.host,
                       path=event.path, bucket=bucket)
        elif event.phase == "response":
            quota = None
            if event.quota is not None:
                facts = event.quota
                quota = {"bucket": "GraphQL" if event.bucket == "graphql" else "REST",
                         "remaining": facts.remaining, "reset": facts.reset,
                         "limit": facts.limit, "used": facts.used}
                if facts.graphql_cost is not None:
                    quota["cost"] = facts.graphql_cost
            self._send("response", requestId=request_id, status=event.status, quota=quota)
        elif event.phase == "completed":
            self._send("end", requestId=request_id, bytes=event.request_bytes + event.response_bytes,
                       complete=event.complete)
        else:
            self._terminal("unknown relay event")
            raise RelayError("unknown gh observation")

    def start(self, environment: Mapping[str, str]) -> dict[str, str]:
        if self._started or self._finished:
            raise RelayError("gh lifecycle already selected")
        self._started = True
        try:
            self._send("open", kind="gh", pid=os.getpid(), ppid=os.getppid())
            self._relay.__enter__()
            self._entered = True
            selected = self._relay.environment(environment)
            # Never put credentials or caller-controlled values into RPC replies,
            # GITHUB_ENV, configuration, summaries or lifecycle instance state.
            self._environment = {key: selected[key] for key in RELAY_ENV_KEYS}
            self.check()
            return dict(self._environment)
        except BaseException:
            self.abort()
            raise

    def check(self) -> None:
        if not self._started or self._finished or self._failed:
            raise RelayError("gh lifecycle unavailable")
        self._relay.check()

    def finish(self) -> RelaySummary:
        if not self._started or self._finished:
            raise RelayError("gh lifecycle unavailable")
        try:
            summary = self._relay.finish()
            # Cleanup is part of success; the existing supervisor must never
            # see a closed observer while a relay worker/configuration remains.
            self._relay.__exit__(None, None, None)
            self._entered = False
            if self._failed:
                raise RelayError("gh lifecycle refused")
            self._send("close")
            self._summary = summary
            self._finished = True
            self._environment = None
            return summary
        except BaseException:
            self.abort()
            raise

    def abort(self) -> None:
        self._failed = True
        try:
            if self._entered:
                self._relay.__exit__(RuntimeError, RuntimeError("owning operation failed"), None)
        finally:
            self._entered = False
            self._environment = None
            self._finished = True
            self._notify("gh lifecycle refused")
