"""Bounded, externally selected CI policy; never an ordinary admission event.

Original Codex messages are authenticated by the isolated operator, outside CI.
This module checks their technical projection, not independent human identity.
All live observations use the actual transition event and fail closed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import signal
import threading
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

# Imports are selected from the T-owned checkout, never the invocation cwd.
_TRUSTED_ROOT = Path(__file__).resolve().parents[1]
if str(_TRUSTED_ROOT) not in sys.path[:1]:
    sys.path.insert(0, str(_TRUSTED_ROOT))

try:
    from conformance import review_baseline_admission as ordinary
except ModuleNotFoundError:
    import review_baseline_admission as ordinary

ROOT_FILE = "conformance/ci_policy_transition_root.json"
EVENT_CLASS = "CI_POLICY_TRANSITION"
POLICY_SCHEMA = "ofarm.ci-policy-transition-root.v1"
GRANT_SCHEMA = "ofarm.ci-policy-transition-grant.v1"
MARKERS = {
    "admission": "OFARM2_CI_TRANSITION_ADMISSION_V1",
    "source": "OFARM2_CI_TRANSITION_SOURCE_BINDING_V1",
    "publisher": "OFARM2_CI_TRANSITION_PUBLISHER_BINDING_V1",
    "revocation": "OFARM2_CI_TRANSITION_REVOCATION_V1",
}
WORKFLOWS = {
    "source": (".github/workflows/ci-policy-transition-source.yml", "OFARM2 temporary policy source v1"),
    "publisher": (".github/workflows/ci-policy-transition-publication.yml", "OFARM2 temporary policy publication v1"),
}
PRODUCER_NAMES = {"conformance", "native verifier (amd64)", "native verifier (arm64)"}
PUBLISHER_NAMES = {"derive and publish authoritative evidence"}
LIFECYCLE_TYPES = {
    "ClosedEvent", "ReopenedEvent", "HeadRefDeletedEvent", "HeadRefRestoredEvent",
    "HeadRefForcePushedEvent", "BaseRefChangedEvent", "BaseRefDeletedEvent", "BaseRefForcePushedEvent",
}
try:
    from conformance import ci_policy_transition_tools as tool_policy
    from conformance import ci_policy_transition_coverage as coverage
except ModuleNotFoundError:
    import ci_policy_transition_tools as tool_policy
    import ci_policy_transition_coverage as coverage

# One accounting authority is shared by the API adapter and tool supervisor.
TransitionError = tool_policy.TransitionError
RequestBudget = tool_policy.RequestBudget
POOL_LIMITS = tool_policy.POOL_LIMITS
TOOL_ALLOCATIONS = tool_policy.TOOL_ALLOCATIONS
PHASE_JOBS = tool_policy.PHASE_JOBS
PUBLISHER_PHASES = frozenset(k for k, v in PHASE_JOBS.items() if v in {
    "publisher-gate", "source-admission", "publish", "publisher-guard", "seal", "external-acceptance"
})


def canonical_json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(value):
    payload = value if isinstance(value, bytes) else canonical_json(value)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _object(value, label):
    if not isinstance(value, dict):
        raise TransitionError(f"{label} must be an object")
    return value


def _keys(value, keys, label):
    _object(value, label)
    if set(value) != set(keys):
        raise TransitionError(f"{label} has missing or unknown fields")
    return value


def _integer(value, label, minimum=1):
    if type(value) is not int or value < minimum:
        raise TransitionError(f"{label} must be an integer >= {minimum}")
    return value


def _text(value, label, limit=512):
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise TransitionError(f"{label} must be bounded single-line text")
    return value


def _sha(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise TransitionError(f"{label} must be a full Git SHA")
    return value


def _digest(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise TransitionError(f"{label} must be a SHA256 digest")
    return value


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z", value):
        raise TransitionError("timestamp must be explicit UTC")
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise TransitionError("invalid timestamp") from exc


def utcnow():
    return datetime.now(timezone.utc)


def decode_json(payload):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise TransitionError("duplicate JSON field")
            result[k] = v
        return result
    try:
        value = json.loads(payload, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(TransitionError("non-finite JSON")))
    except (ValueError, UnicodeError) as exc:
        raise TransitionError("invalid finite JSON") from exc
    return value


def validate_policy(policy):
    _keys(policy, {"schemaVersion", "repository", "operatorId", "consumerPullRequest", "transitionPullRequest", "baseSha", "campaign", "closure", "coverageDigest", "requestPlan"}, "root policy")
    if policy["schemaVersion"] != POLICY_SCHEMA or policy["transitionPullRequest"] != 417 or policy["consumerPullRequest"] not in (413, 411):
        raise TransitionError("root is outside the approved transition")
    repo = _keys(policy["repository"], {"name", "id"}, "root repository")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", _text(repo["name"], "repository")):
        raise TransitionError("invalid repository")
    _integer(repo["id"], "repository ID")
    _integer(policy["operatorId"], "operator ID")
    _sha(policy["baseSha"], "base SHA")
    campaign = _keys(policy["campaign"], {"id", "notBefore", "sunset"}, "campaign")
    _text(campaign["id"], "campaign ID")
    duration = timestamp(campaign["sunset"]) - timestamp(campaign["notBefore"])
    if not timedelta(0) < duration <= timedelta(days=7):
        raise TransitionError("campaign exceeds seven days")
    _object(policy["closure"], "closure declarations")
    if policy["coverageDigest"] != coverage.coverage_digest():
        raise TransitionError("coverage differs from the fixed version-4 declaration")
    expected = {"periodSeconds": 120, "sweepDeadlineSeconds": 15,
                "periodicREST": 15, "periodicGraphQL": 5,
                "pools": {k: list(v) for k, v in POOL_LIMITS.items()},
                "toolAllocations": {k: list(v) for k, v in TOOL_ALLOCATIONS.items()},
                "sharedMargin": [75, 75]}
    if policy["requestPlan"] != expected:
        raise TransitionError("request plan differs from the fixed reviewed allocations")
    return policy


def validate_grant(policy, grant, *, now=None):
    validate_policy(policy)
    _keys(grant, {"schemaVersion", "grantId", "repository", "repositoryId", "operatorId", "transitionPullRequest", "consumerPr", "rootSha", "rootTree", "closureDigest", "coverageDigest", "baseSha", "headSha", "mergeSha", "decision", "consumerDecision", "review", "campaignId", "notBefore", "expiresAt", "sourceRef", "publisherRef", "journal"}, "grant")
    if grant["schemaVersion"] != GRANT_SCHEMA:
        raise TransitionError("unsupported grant schema")
    for k in ("rootSha", "rootTree", "baseSha", "headSha", "mergeSha"):
        _sha(grant[k], k)
    _digest(grant["closureDigest"], "closure digest")
    if grant["coverageDigest"] != policy["coverageDigest"]:
        raise TransitionError("grant changes the fixed coverage declaration")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{7,63}", _text(grant["grantId"], "grant ID")):
        raise TransitionError("invalid unique grant ID")
    fixed = {"repository": policy["repository"]["name"], "repositoryId": policy["repository"]["id"], "operatorId": policy["operatorId"], "transitionPullRequest": 417, "consumerPr": policy["consumerPullRequest"], "baseSha": policy["baseSha"], "campaignId": policy["campaign"]["id"]}
    if any(grant[k] != v or isinstance(grant[k], bool) for k, v in fixed.items()):
        raise TransitionError("grant does not match the externally selected root")
    start, end = timestamp(grant["notBefore"]), timestamp(grant["expiresAt"])
    if not timedelta(0) < end-start <= timedelta(hours=24) or start < timestamp(policy["campaign"]["notBefore"]) or end > timestamp(policy["campaign"]["sunset"]):
        raise TransitionError("grant lifetime exceeds campaign/24-hour bounds")
    if now is not None and not start <= now < end:
        raise TransitionError("grant expired or not yet active")
    for role in ("source", "publisher"):
        if grant[role+"Ref"] != f"refs/heads/ofarm-ci-transition/{role}/{grant['grantId']}":
            raise TransitionError("grant activation ref is not exact")
    for key in ("decision", "consumerDecision"):
        decision = _keys(grant[key], {"id", "version", "cardRef", "approvalRef", "threadId"}, key)
        for k in ("id", "cardRef", "approvalRef", "threadId"):
            _text(decision[k], k)
        _integer(decision["version"], "decision version")
    if grant["decision"]["id"] != "OFARM2-CI-POLICY-TRANSITION-001" or grant["decision"]["version"] != 4:
        raise TransitionError("root semantic decision does not match version 4")
    if grant["decision"]["threadId"] != grant["consumerDecision"]["threadId"]:
        raise TransitionError("authority must remain in the coordinating task")
    review = _keys(grant["review"], {"rootReviewRef", "consumerReviewRef"}, "review")
    for v in review.values():
        _text(v, "review reference")
    journal = _keys(grant["journal"], {"genesisDigest", "formatVersion"}, "journal")
    _digest(journal["genesisDigest"], "journal genesis")
    if journal["formatVersion"] != 1:
        raise TransitionError("unsupported journal format")
    return grant


def activation_approval_text(grant, packet_digest):
    _digest(packet_digest, "packet digest")
    return (f"I authorize OFARM2 CI transition grant {grant['grantId']} under packet {packet_digest} "
            f"using root {grant['rootSha']} for PR #{grant['consumerPr']} at head {grant['headSha']}, "
            f"base {grant['baseSha']} and merge {grant['mergeSha']}, until {grant['expiresAt']}, "
            "for one source and one publisher, attempt 1 only. Merge remains separate.")


def verify_original_authority(projection, grant):
    """Validate externally retrieved original-message projection, never a receipt.

    The isolated caller MUST retrieve originals; self-attested JSON is not a
    human authentication mechanism. CI deliberately does not invoke this.
    """
    names = ("decisionCard", "decisionApproval", "consumerCard", "consumerApproval", "activationPacket", "activationApproval")
    _keys(projection, {"schemaVersion", "threadId", *names}, "original authority projection")
    if projection["schemaVersion"] != "ofarm.ci-policy-transition-original-authority.v1" or projection["threadId"] != grant["decision"]["threadId"]:
        raise TransitionError("original authority task/schema differs")
    ids = set()
    for name in names:
        item = _keys(projection[name], {"id", "order", "role", "text"}, name)
        _text(item["id"], "original message reference")
        _integer(item["order"], "message order", 0)
        if item["id"] in ids or not isinstance(item["text"], str) or not item["text"]:
            raise TransitionError("missing/duplicate original message")
        ids.add(item["id"])
        role = "user" if name.endswith("Approval") else "assistant"
        if item["role"] != role:
            raise TransitionError("original message has the wrong author role")
    for prefix, decision, pr in (("decision", grant["decision"], 417), ("consumer", grant["consumerDecision"], grant["consumerPr"])):
        card, approval = projection[prefix+"Card"], projection[prefix+"Approval"]
        if card["id"] != decision["cardRef"] or approval["id"] != decision["approvalRef"] or card["order"] >= approval["order"]:
            raise TransitionError("original card/approval ordering or binding differs")
        expected = f"I approve OFARM2 decision {decision['id']} version {decision['version']}."
        if approval["text"] != expected or decision["id"] not in card["text"] or f"#{pr}" not in card["text"]:
            raise TransitionError("original semantic approval/card does not match")
    packet, approval = projection["activationPacket"], projection["activationApproval"]
    if packet["order"] <= max(projection["decisionApproval"]["order"], projection["consumerApproval"]["order"]) or approval["order"] <= packet["order"]:
        raise TransitionError("activation must follow both semantic approvals")
    for value in (grant["rootSha"], grant["headSha"], grant["baseSha"], grant["mergeSha"], grant["expiresAt"], grant["grantId"], digest(grant), grant["journal"]["genesisDigest"], grant["coverageDigest"]):
        if value not in packet["text"]:
            raise TransitionError("activation packet omits a frozen coordinate")
    if approval["text"] != activation_approval_text(grant, digest(packet["text"].encode())):
        raise TransitionError("original exact-root activation approval differs")
    return {"purpose": "ORIGINAL_AUTHORITY_PROJECTION_CHECKED", "threadId": projection["threadId"], "messageRefs": {n: projection[n]["id"] for n in names}, "grantDigest": digest(grant), "independentHumanAuthentication": False}


def record_body(role, payload, prose=""):
    if role not in MARKERS:
        raise TransitionError("unknown record role")
    prefix = prose.rstrip() + "\n\n" if prose else ""
    return prefix + MARKERS[role] + "\n" + canonical_json(payload).decode().rstrip("\n") + "\n"


def parse_record(body, role):
    if not isinstance(body, str) or len(body.encode()) > 60_000:
        raise TransitionError("record body absent or too large")
    marker = MARKERS[role]
    match = re.search(r"(?:\A|\n)"+re.escape(marker)+r"\n([^\r\n]+)\n?\Z", body)
    if match is None:
        return None
    return _object(decode_json(match.group(1)), "record footer")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None




class _BoundedResponse:
    """Preserve response bytes while latching incomplete/oversize transfers."""
    def __init__(self, response, budget, label, limit, request_id, *, completion=False):
        self._response, self._budget, self._label = response, budget, label
        self._request_id, self._completion = request_id, completion
        self._closed = False
        self.status, self.headers = response.status, response.headers
        self._limit, self._read, self._complete = limit, 0, False
        raw = self.headers.get("Content-Length")
        self._length = None
        if raw is not None:
            if not re.fullmatch(r"[0-9]+", str(raw)) or int(raw) > limit:
                self.close()
                budget.fail("invalid or excessive response length")
                raise TransitionError("invalid or excessive response length")
            self._length = int(raw)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _value, _traceback):
        self.close()
        if exc_type is None and not self._complete:
            self._budget.fail("response not completely consumed")
            raise TransitionError("response not completely consumed")

    def geturl(self):
        return self._response.geturl()

    def read(self, amount=-1):
        self._check_deadline()
        try:
            data = self._response.read(amount)
        except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
            partial = getattr(exc, "partial", b"")
            if isinstance(partial, bytes):
                self._read += len(partial)
                self._budget.charge_transport(self._label, requests=0, bytes=len(partial), completion=True)
            self._budget.fail("response body unavailable")
            raise TransitionError("response body unavailable") from exc
        self._read += len(data)
        self._budget.charge_transport(self._label, requests=0, bytes=len(data), completion=True)
        if self._read > self._limit or (self._length is not None and self._read > self._length):
            self._budget.fail("response byte bound exceeded")
            raise TransitionError("response byte bound exceeded")
        if amount < 0 or len(data) < amount or (self._length is not None and self._read == self._length):
            if self._length is not None and self._read != self._length:
                self._budget.fail("response body incomplete")
                raise TransitionError("response body incomplete")
            self._complete = True
        self._check_deadline()
        return data

    def _check_deadline(self):
        if not self._completion:
            self._budget.remaining_timeout()
        elif self._budget.deadline is not None and self._budget.monotonic() >= self._budget.deadline:
            raise TransitionError("complete response deadline exceeded")

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self._response.close()
            finally:
                self._budget.record_outcome(self._request_id, status=self.status, complete=self._complete)


class ApiReader:
    def __init__(self, token, *, budget, api_url="https://api.github.com", opener=None):
        if api_url != "https://api.github.com" or not isinstance(token, str) or not token:
            raise TransitionError("fixed authenticated GitHub API and token required")
        self.api_url, self.token, self.budget = api_url, token, budget
        # No ambient HTTP(S) proxy may receive the workflow credential.
        self._opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()).open

    @contextmanager
    def pool(self, name):
        self.budget.limits(name)
        previous = self.budget.current_pool
        self.budget.current_pool = name
        try:
            yield self
        finally:
            self.budget.current_pool = previous

    def _request(self, path, *, data=None, method="GET"):
        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or any(ord(c) < 32 for c in path):
            raise TransitionError("invalid API path")
        return urllib.request.Request(self.api_url+path, data=data, method=method, headers={
            "Accept": "application/vnd.github+json", "Authorization": "Bearer "+self.token,
            "Content-Type": "application/json", "User-Agent": "ofarm2-ci-policy-transition",
            "X-GitHub-Api-Version": ordinary.GITHUB_API_VERSION,
        })

    def _drain(self, response, label, request_id, *, capture=False):
        # Failure is already latched before draining an error. This can only
        # finish an existing request; it never permits another dispatch.
        payload = bytearray() if capture else None
        with _BoundedResponse(response, self.budget, label, 16_777_216,
                              request_id, completion=True) as observed:
            while chunk := observed.read(65536):
                if payload is not None:
                    if len(payload) + len(chunk) > 4_000_000:
                        payload = None
                    else:
                        payload.extend(chunk)
        return None if payload is None else bytes(payload)

    def _open(self, request, timeout, *, artifact=False, absence=False, completion=False):
        url = urllib.parse.urlsplit(request.full_url)
        if url.scheme != "https" or url.username or url.password or url.fragment or url.port not in (None, 443):
            raise TransitionError("unsafe response URL")
        api = url.netloc == "api.github.com"
        if not api and (not artifact or request.get_header("Authorization")):
            raise TransitionError("source response must remain on authenticated API origin")
        if api and request.get_header("Authorization") != "Bearer " + self.token:
            raise TransitionError("API request changes the selected credential")
        graphql = api and url.path == "/graphql"
        # Every HTTP attempt is charged before dispatch, including failures.
        request_id = uuid.uuid4().hex
        label = ("api-graphql" if graphql else "api-rest" if api else "artifact-blob") + ":" + request_id
        self.budget.assert_healthy()
        if api:
            self.budget.begin_primary(request_id, "GraphQL" if graphql else "REST", label)
            request._transition_primary_id = request_id
        self.budget.charge_transport(label, requests=1, bytes=len(request.data or b""))
        if graphql:
            request._transition_graphql_settlement = "pending"
        try:
            response = self._opener(request, timeout=self.budget.remaining_timeout(timeout))
        except urllib.error.HTTPError as exc:
            permitted = (artifact and api and exc.code in (301, 302, 303, 307, 308)
                         or absence and api and exc.code == 404 and not graphql)
            if not permitted:
                self.budget.fail("HTTP request refused")
            try:
                if api and not graphql:
                    self._quota_headers(exc.headers, "REST", request_id=request_id, completion=not permitted)
            finally:
                payload = self._drain(exc, label, request_id, capture=graphql)
                if graphql and payload is not None:
                    self._settle_graphql_document(_object(decode_json(payload), "GraphQL response"), request)
            if permitted:
                if exc.code == 404:
                    raise
                return exc
            raise TransitionError("HTTP request refused; attempt cannot retry") from exc
        except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
            self.budget.record_outcome(request_id, status=None, complete=False)
            self.budget.fail("authoritative read unavailable")
            raise TransitionError("authoritative read unavailable") from exc
        if getattr(response, "status", None) not in (200, 202):
            self.budget.fail("unexpected HTTP response status")
            payload = self._drain(response, label, request_id, capture=graphql)
            if graphql and payload is not None:
                self._settle_graphql_document(_object(decode_json(payload), "GraphQL response"), request)
            raise TransitionError("unexpected HTTP response status")
        if api and not graphql:
            try:
                self._quota_headers(response.headers, "REST", request_id=request_id)
            except Exception:
                self._drain(response, label, request_id)
                raise
        if response.geturl() != request.full_url:
            self.budget.fail("transport followed an unobserved redirect")
            self._drain(response, label, request_id)
            raise TransitionError("transport followed an unobserved redirect")
        return _BoundedResponse(response, self.budget, label,
                                1_650_000_000 if artifact else 16_777_216, request_id,
                                completion=completion)

    def response(self, request, timeout=20):
        """Accounted no-redirect opener for unchanged authenticated source reads."""
        return self._open(request, timeout)

    def artifact_response(self, request, timeout=60):
        """Only the authenticated artifact endpoint may select a signed HTTPS URL."""
        url = urllib.parse.urlsplit(request.full_url)
        if url.netloc != "api.github.com" or not re.fullmatch(
                r"/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/artifacts/[1-9][0-9]*/zip", url.path
        ) or url.query or request.get_method() != "GET":
            raise TransitionError("download did not start at an exact artifact API endpoint")
        result = self._open(request, timeout, artifact=True)
        if not isinstance(result, urllib.error.HTTPError):
            return result
        try:
            location = result.headers.get("Location")
            destination = urllib.parse.urlsplit(location or "")
            if (destination.scheme != "https" or not destination.hostname or destination.username
                    or destination.password or destination.fragment or destination.port not in (None, 443)
                    or destination.netloc == "api.github.com"):
                raise TransitionError("artifact redirect has no safe signed HTTPS destination")
        finally:
            result.close()
        # Credentials are deliberately omitted. Never persist or echo the signed URL.
        return self._open(urllib.request.Request(location, headers={"User-Agent": "ofarm2-ci-policy-transition"}),
                          timeout, artifact=True)

    def _quota_headers(self, headers, bucket, *, request_id, completion=False):
        try:
            if headers.get("X-RateLimit-Resource") != "core":
                raise ValueError("unexpected primary resource")
            raw = {k: headers["X-RateLimit-"+k] for k in ("Remaining", "Reset", "Limit")}
            if any(not re.fullmatch(r"[0-9]+", str(value)) for value in raw.values()):
                raise ValueError("invalid quota")
            values = {k: int(value) for k, value in raw.items()}
            if not completion:
                self.budget.observe_quota(bucket, remaining=values["Remaining"], reset=values["Reset"],
                    limit=values["Limit"], request_id=request_id)
            else:
                self.budget._quota(bucket, remaining=values["Remaining"], reset=values["Reset"], limit=values["Limit"])
        except (ValueError, TypeError, KeyError) as exc:
            self.budget.fail("provider quota unavailable")
            raise TransitionError("provider quota unavailable") from exc

    def _json(self, request, *, completion=False):
        try:
            with self._open(request, 20, completion=completion) as response:
                if response.status != 200:
                    raise TransitionError("unexpected API response status")
                payload = response.read(4_000_001)
            if not completion:
                self.budget.remaining_timeout()
            if len(payload) > 4_000_000:
                raise TransitionError("API response exceeds bounded page")
            return decode_json(payload)
        except Exception:
            self.budget.fail("required API response unavailable")
            raise

    def __call__(self, path):
        return self._json(self._request(path))

    def _settle_graphql_document(self, response, request):
        if getattr(request, "_transition_graphql_settlement", None) != "pending":
            raise TransitionError("GraphQL settlement is not pending")
        data = _object(response.get("data"), "GraphQL data")
        quota = _object(data.get("rateLimit"), "GraphQL quota")
        cost = _integer(quota.get("cost"), "GraphQL cost")
        # A returned cost is independent of GraphQL errors or another failed
        # request. Record it before validating the remaining quota facts.
        request._transition_graphql_settlement = "known"
        try:
            self.budget.charge("GraphQL", cost-1, "actual GraphQL points", completion=True,
                               request_id=request._transition_primary_id)
        finally:
            with self.budget._transaction() as state:
                self.budget._trace(state, {"bucket": "GraphQL", "costMode": "actual",
                    "actualCost": cost, "chargedBound": cost})
        self.budget.observe_quota("GraphQL", remaining=quota.get("remaining"),
            reset=int(timestamp(quota.get("resetAt")).timestamp()), limit=quota.get("limit"), completion=True,
            request_id=request._transition_primary_id)
        return data

    def graphql(self, query, variables):
        request = self._request("/graphql", data=canonical_json({"query": query, "variables": variables}), method="POST")
        try:
            response = _object(self._json(request, completion=True), "GraphQL response")
            if response.get("errors") is not None:
                self.budget.fail("GraphQL required facts unavailable")
            data = self._settle_graphql_document(response, request)
            self.budget.assert_healthy()
            return data
        except Exception:
            if getattr(request, "_transition_graphql_settlement", None) == "pending":
                request._transition_graphql_settlement = "unknown"
                self.budget.record_unknown_graphql_cost()
            self.budget.fail("GraphQL required facts unavailable")
            raise

    def absent_ref(self, path):
        try:
            with self._open(self._request(path), 20, absence=True) as response:
                response.read(4_000_001)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                exc.close()
                return
            raise TransitionError("ref absence cannot be authenticated") from exc
        raise TransitionError("publisher ref exists before its binding")

    def cancel_own_run(self, repository, run_id, authenticated_run_id):
        if run_id != authenticated_run_id or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise TransitionError("guard may cancel only its authenticated current run")
        _integer(run_id, "cancel run ID")
        with self.pool("shared-tools"):
            request = self._request(f"/repos/{repository}/actions/runs/{run_id}/cancel", method="POST")
            with self.response(request, timeout=5) as response:
                if response.status != 202:
                    raise TransitionError("own-run cancellation refused")
                response.read(4_000_001)

    def jobs(self, repository, run_id):
        result, identities = [], set()
        total = None
        for page in range(1, 4):
            data = _object(self(f"/repos/{repository}/actions/runs/{run_id}/attempts/1/jobs?per_page=100&page={page}"), "jobs")
            jobs = data.get("jobs")
            observed = _integer(data.get("total_count"), "jobs total", 0)
            if total is not None and total != observed:
                raise TransitionError("jobs total changed during pagination")
            total = observed
            if not isinstance(jobs, list) or len(jobs) > 100:
                raise TransitionError("invalid jobs page")
            for job in jobs:
                _object(job, "job")
                identity = _integer(job.get("id"), "job ID")
                if identity in identities or job.get("run_id") != run_id or job.get("run_attempt") != 1:
                    raise TransitionError("duplicate/foreign job")
                identities.add(identity)
                result.append(job)
            if len(result) == total:
                return result
            if len(result) > total or len(jobs) < 100:
                raise TransitionError("incomplete jobs page")
        raise TransitionError("jobs pagination exceeds bounded complete scan")


def make_reader(phase, policy=None, token=None, api_url="https://api.github.com", budget_path=None, environment=None):
    if phase not in PHASE_JOBS:
        raise TransitionError("unknown phase")
    if policy is not None:
        validate_policy(policy)
    job = PHASE_JOBS[phase]
    environment = os.environ if environment is None else environment
    if environment.get("GITHUB_ACTIONS") == "true":
        tool_policy.assert_supervisor(environment, job)
        if budget_path is None:
            budget_path = tool_policy.default_budget_path(environment, job)
    return ApiReader(token or environment.get("OFARM_ADMISSION_TOKEN", ""), budget=RequestBudget(job, path=budget_path), api_url=api_url)


GRAPH_QUERY = """
query TransitionFacts($ids:[ID!]!, $owner:String!, $name:String!, $number:Int!, $since:DateTime!, $after:String) {
  nodes(ids:$ids) { ... on IssueComment {
    databaseId body authorAssociation createdAt updatedAt lastEditedAt isMinimized
    author { ... on User { databaseId } }
    issue { number repository { nameWithOwner databaseId } }
  } }
  repository(owner:$owner,name:$name) {
    databaseId nameWithOwner
    pullRequest(number:$number) {
      number state headRefOid baseRefOid baseRefName
      timelineItems(first:100,after:$after,since:$since,itemTypes:[CLOSED_EVENT,REOPENED_EVENT,HEAD_REF_DELETED_EVENT,HEAD_REF_RESTORED_EVENT,HEAD_REF_FORCE_PUSHED_EVENT,BASE_REF_CHANGED_EVENT,BASE_REF_DELETED_EVENT,BASE_REF_FORCE_PUSHED_EVENT]) {
        filteredCount pageInfo { hasNextPage endCursor }
        nodes {
          __typename
          ... on ClosedEvent { id createdAt }
          ... on ReopenedEvent { id createdAt }
          ... on HeadRefDeletedEvent { id createdAt }
          ... on HeadRefRestoredEvent { id createdAt }
          ... on HeadRefForcePushedEvent { id createdAt }
          ... on BaseRefChangedEvent { id createdAt }
          ... on BaseRefDeletedEvent { id createdAt }
          ... on BaseRefForcePushedEvent { id createdAt }
        }
      }
    }
  }
  rateLimit { cost limit remaining resetAt }
}
"""


class BindingPending(TransitionError):
    """Only cheap gate discovery may wait for a first binding."""


def _comments(reader, repository, number):
    result, seen = [], set()
    for page in range(1, 4):
        comments = reader(f"/repos/{repository}/issues/{number}/comments?per_page=100&page={page}")
        if not isinstance(comments, list) or len(comments) > 100:
            raise TransitionError("incomplete comment page")
        for item in comments:
            _object(item, "comment")
            identity = _integer(item.get("id"), "comment ID")
            if identity in seen:
                raise TransitionError("duplicate comment during pagination")
            seen.add(identity)
            result.append(item)
        if len(comments) < 100:
            return result
    raise TransitionError("comment pagination exceeds complete bounded scan")


def _record_set(comments, grant_id):
    found = {}
    for comment in comments:
        for role in ("admission", "source", "publisher"):
            payload = parse_record(comment.get("body"), role)
            if payload is None:
                continue
            candidate_id = payload.get("grantId") if role != "admission" else _object(payload.get("grant"), "admission grant").get("grantId")
            if candidate_id != grant_id:
                continue
            if role in found:
                raise TransitionError("duplicate grant binding or admission")
            found[role] = (comment, payload)
    return found


def _comment_identity(comment, grant, *, now):
    _integer(comment.get("id"), "comment ID")
    _text(comment.get("node_id"), "comment node ID")
    expected_url = f"https://api.github.com/repos/{grant['repository']}/issues/{grant['consumerPr']}"
    if comment.get("issue_url") != expected_url:
        raise TransitionError("comment belongs to another PR")
    if comment.get("author_association") not in ordinary.ALLOWED_ASSOCIATIONS or _object(comment.get("user"), "comment author").get("id") != grant["operatorId"]:
        raise TransitionError("comment author is not the root-pinned standing operator")
    created = timestamp(comment.get("created_at"))
    if comment.get("created_at") != comment.get("updated_at") or not timestamp(grant["notBefore"]) <= created <= now:
        raise TransitionError("record edited, premature or future-dated")
    return {"id": comment["id"], "digest": digest(comment["body"].encode())}


def _graph_facts(reader, grant, comments, since, now):
    owner, name = grant["repository"].split("/")
    cursor, seen = None, set()
    for _ in range(3):
        facts = reader.graphql(GRAPH_QUERY, {"ids": [c["node_id"] for c in comments], "owner": owner, "name": name, "number": grant["consumerPr"], "since": since, "after": cursor})
        nodes = facts.get("nodes")
        if not isinstance(nodes, list) or len(nodes) != len(comments):
            raise TransitionError("GraphQL comment facts incomplete")
        for rest, graph in zip(comments, nodes):
            _object(graph, "GraphQL comment")
            expected = {"databaseId": rest["id"], "body": rest["body"], "authorAssociation": rest["author_association"], "createdAt": rest["created_at"], "updatedAt": rest["updated_at"], "lastEditedAt": None, "isMinimized": False}
            if any(graph.get(k) != v for k, v in expected.items()):
                raise TransitionError("edited/minimized/mismatched GraphQL comment")
            if _object(graph.get("author"), "GraphQL author").get("databaseId") != grant["operatorId"]:
                raise TransitionError("GraphQL operator identity differs")
            issue = _object(graph.get("issue"), "GraphQL issue")
            repo = _object(issue.get("repository"), "GraphQL comment repository")
            if issue.get("number") != grant["consumerPr"] or repo.get("nameWithOwner") != grant["repository"] or repo.get("databaseId") != grant["repositoryId"]:
                raise TransitionError("GraphQL comment repository/PR differs")
        repo = _object(facts.get("repository"), "GraphQL repository")
        if repo.get("databaseId") != grant["repositoryId"] or repo.get("nameWithOwner") != grant["repository"]:
            raise TransitionError("GraphQL repository identity differs")
        pr = _object(repo.get("pullRequest"), "GraphQL PR")
        if any(pr.get(k) != v for k, v in {"number": grant["consumerPr"], "state": "OPEN", "headRefOid": grant["headSha"], "baseRefOid": grant["baseSha"], "baseRefName": "main"}.items()):
            raise TransitionError("GraphQL and REST live PR facts differ")
        timeline = _object(pr.get("timelineItems"), "PR lifecycle")
        events = timeline.get("nodes")
        # totalCount includes unrelated timeline history despite these filters.
        # Only an empty, complete first page may pass; every event below revokes.
        total = _integer(timeline.get("filteredCount"), "timeline filtered count", 0)
        if not isinstance(events, list) or len(events) > 100:
            raise TransitionError("incomplete lifecycle page")
        for event in events:
            _object(event, "lifecycle event")
            identity = _text(event.get("id"), "lifecycle event ID")
            if identity in seen or event.get("__typename") not in LIFECYCLE_TYPES:
                raise TransitionError("duplicate or unknown lifecycle event")
            seen.add(identity)
            created = timestamp(event.get("createdAt"))
            if not timestamp(since) <= created <= now:
                raise TransitionError("lifecycle timestamp inconsistent")
            # Every member of this closed query is a revoking transition.
            raise TransitionError("PR lifecycle changed after transition admission")
        info = _object(timeline.get("pageInfo"), "lifecycle pagination")
        if info.get("hasNextPage") is False:
            if len(seen) != total:
                raise TransitionError("lifecycle scan omitted events")
            return
        if info.get("hasNextPage") is not True or not events or not info.get("endCursor") or info["endCursor"] == cursor:
            raise TransitionError("lifecycle pagination is incomplete")
        cursor = info["endCursor"]
    raise TransitionError("lifecycle page/cost budget exceeded")


def _live_pr(reader, grant):
    repository, number = grant["repository"], grant["consumerPr"]
    pr = _object(reader(f"/repos/{repository}/pulls/{number}"), "live PR")
    if pr.get("number") != number or pr.get("state") != "open" or pr.get("merged") is True:
        raise TransitionError("consumer PR is not open/unmerged")
    for side, expected in (("head", grant["headSha"]), ("base", grant["baseSha"])):
        item = _object(pr.get(side), side)
        repo = _object(item.get("repo"), side+" repository")
        if item.get("sha") != expected or repo.get("full_name") != repository or repo.get("id") != grant["repositoryId"]:
            raise TransitionError("consumer head/base/repository drift")
    if pr["base"].get("ref") != "main":
        raise TransitionError("consumer base is not main")
    for ref, expected in (("heads/main", grant["baseSha"]), (f"pull/{number}/merge", grant["mergeSha"])):
        _check_ref(reader, grant, ref, expected)
    commit = _object(reader(f"/repos/{repository}/git/commits/{grant['mergeSha']}"), "execution merge")
    if commit.get("sha") != grant["mergeSha"] or ordinary._parent_shas(commit) != [grant["baseSha"], grant["headSha"]]:
        raise TransitionError("execution merge does not bind the exact parents")


def _check_ref(reader, grant, ref, expected):
    obj = _object(reader(f"/repos/{grant['repository']}/git/ref/{ref}"), "live ref")
    target = _object(obj.get("object"), "ref target")
    if obj.get("ref") != "refs/"+ref or target.get("type") != "commit" or target.get("sha") != expected:
        raise TransitionError("observed ref drift permanently revokes this use")


def _run(reader, grant, role, identity, *, completed):
    _keys(identity, {"runId", "runAttempt"}, role+" run identity")
    run_id = _integer(identity["runId"], "run ID")
    if type(identity["runAttempt"]) is not int or identity["runAttempt"] != 1:
        raise TransitionError("workflow rerun is forbidden")
    run = _object(reader(f"/repos/{grant['repository']}/actions/runs/{run_id}"), "live run")
    path, name = WORKFLOWS[role]
    expected = {"id": run_id, "run_attempt": 1, "event": "push", "path": path, "name": name, "head_sha": grant["rootSha"], "head_branch": grant[role+"Ref"].removeprefix("refs/heads/")}
    if any(run.get(k) != v for k, v in expected.items()):
        raise TransitionError("run has wrong workflow/ref/root/attempt identity")
    repo = _object(run.get("repository"), "run repository")
    if repo.get("id") != grant["repositoryId"] or repo.get("full_name") != grant["repository"]:
        raise TransitionError("run belongs to another repository")
    for key in ("actor", "triggering_actor"):
        if _object(run.get(key), key).get("id") != grant["operatorId"]:
            raise TransitionError("run actor differs from root-pinned operator")
    if completed and (run.get("status") != "completed" or run.get("conclusion") != "success"):
        raise TransitionError("whole run has not completed successfully")
    if not completed and (run.get("status") != "in_progress" or run.get("conclusion") is not None):
        raise TransitionError("current governed run is not in progress")
    if timestamp(run.get("created_at")) < timestamp(grant["notBefore"]):
        raise TransitionError("run predates the grant")
    normalized = {"runId": run_id, "runAttempt": 1, "workflowRef": f"{grant['repository']}/{path}@{grant[role+'Ref']}", "workflowSha": grant["rootSha"], "eventName": "push", "workflowPath": path, "workflowName": name}
    return run, normalized


def _event_identity(grant, role, event, context, run):
    _object(event, "push event")
    _object(context, "job context")
    repo = _object(event.get("repository"), "push repository")
    sender = _object(event.get("sender"), "push sender")
    expected = {"created": True, "deleted": False, "forced": False, "before": "0"*40, "after": grant["rootSha"], "ref": grant[role+"Ref"]}
    if any(event.get(k) != v or type(event.get(k)) is not type(v) for k, v in expected.items()) or repo.get("id") != grant["repositoryId"] or repo.get("full_name") != grant["repository"] or sender.get("id") != grant["operatorId"]:
        raise TransitionError("push was not a new operator-created exact-root ref")
    values = {"eventName": "push", "sha": grant["rootSha"], "workflowSha": grant["rootSha"], "workflowRef": f"{grant['repository']}/{WORKFLOWS[role][0]}@{grant[role+'Ref']}", "repository": grant["repository"], "repositoryId": grant["repositoryId"], "runId": run["id"], "runAttempt": 1, "actorId": grant["operatorId"], "ref": grant[role+"Ref"]}
    if any(context.get(k) != v for k, v in values.items()):
        raise TransitionError("job context and authenticated provider identity differ")


def _validate_live(policy, grant, reader, *, phase, now=None, event=None, job_context=None, expected_bindings=None):
    if phase not in PHASE_JOBS:
        raise TransitionError("unknown governed phase")
    now = now or utcnow()
    validate_grant(policy, grant, now=now)
    publisher_phase = phase in PUBLISHER_PHASES
    comments = _comments(reader, grant["repository"], grant["consumerPr"])
    records = _record_set(comments, grant["grantId"])
    required = {"admission", "source", "publisher"} if publisher_phase else {"admission", "source"}
    if set(records) != required:
        raise TransitionError("missing, unexpected or previously deleted bound record")
    authenticated = {}
    identities = {}
    for role in sorted(required):
        old, payload = records[role]
        _comment_identity(old, grant, now=now)
        comment = _object(reader(f"/repos/{grant['repository']}/issues/comments/{old['id']}"), "bound record")
        # Endpoint-specific author profiles are presentation, not authority.
        # Both representations must independently name the root-pinned user ID.
        for k in ("id", "node_id", "body", "created_at", "updated_at", "author_association", "issue_url"):
            if comment.get(k) != old.get(k):
                raise TransitionError("record changed between scan and exact fetch")
        identities[role] = _comment_identity(comment, grant, now=now)
        authenticated[role] = comment
        records[role] = (comment, payload)
    admission_payload = _keys(records["admission"][1], {"grant", "grantDigest"}, "admission footer")
    if admission_payload["grant"] != grant or admission_payload["grantDigest"] != digest(grant):
        raise TransitionError("admission changes the frozen technical grant")
    admitted_at = timestamp(authenticated["admission"]["created_at"])
    for comment in comments:
        if comment.get("author_association") not in ordinary.ALLOWED_ASSOCIATIONS:
            continue
        if timestamp(comment.get("created_at")) < admitted_at:
            continue
        revoked = parse_record(comment.get("body"), "revocation")
        if revoked is not None and revoked.get("grantId") == grant["grantId"]:
            raise TransitionError("standing reviewer revoked transition grant")
        if ordinary._footer_head(comment.get("body"), ordinary.REVOCATION_MARKER, "revocation") == grant["headSha"]:
            raise TransitionError("existing exact-head revocation vetoes transition")
    _live_pr(reader, grant)
    _check_ref(reader, grant, grant["sourceRef"].removeprefix("refs/"), grant["rootSha"])
    if publisher_phase:
        _check_ref(reader, grant, grant["publisherRef"].removeprefix("refs/"), grant["rootSha"])
    else:
        reader.absent_ref(f"/repos/{grant['repository']}/git/ref/{grant['publisherRef'].removeprefix('refs/')}")
    runs, normalized = {}, {}
    for role in ("source", "publisher") if publisher_phase else ("source",):
        payload = records[role][1]
        fields = {"grantId", "grantDigest", "rootSha", "admission", role}
        if role == "publisher":
            fields |= {"source", "sourceBinding", "ticket"}
        _keys(payload, fields, role+" binding")
        if payload["grantId"] != grant["grantId"] or payload["grantDigest"] != digest(grant) or payload["rootSha"] != grant["rootSha"] or payload["admission"] != identities["admission"]:
            raise TransitionError("binding changes grant/root/admission")
        if role == "publisher":
            if payload["source"] != records["source"][1]["source"] or payload["sourceBinding"] != identities["source"]:
                raise TransitionError("publisher binding selects a different source")
            _keys(payload["ticket"], {"id", "digest"}, "bound ticket")
            _integer(payload["ticket"]["id"], "ticket ID")
            _digest(payload["ticket"]["digest"], "ticket digest")
        completed = (role == "source" and publisher_phase) or phase == "external-acceptance"
        runs[role], normalized[role] = _run(reader, grant, role, payload[role], completed=completed)
        run_created = timestamp(runs[role]["created_at"])
        bound_at = timestamp(authenticated[role]["created_at"])
        if not admitted_at <= run_created <= bound_at <= run_created + timedelta(minutes=5):
            raise TransitionError("binding is late or precedes its exact run")
    if publisher_phase and normalized["source"]["runId"] == normalized["publisher"]["runId"]:
        raise TransitionError("source and publisher must be separate runs")
    current_role = "publisher" if publisher_phase else "source"
    if event is not None or job_context is not None:
        _event_identity(grant, current_role, event, job_context, runs[current_role])
    elif phase != "external-acceptance" and os.environ.get("GITHUB_ACTIONS") == "true":
        raise TransitionError("CI requires authenticated event and job context")
    _graph_facts(reader, grant, [authenticated[r] for r in sorted(required)], authenticated["admission"]["created_at"], now)
    bindings = {"admission": identities["admission"], "sourceBinding": identities["source"], "publisherBinding": identities.get("publisher")}
    if expected_bindings is not None and bindings != expected_bindings:
        raise TransitionError("bound IDs/digests changed after their first observation")
    admission = ordinary.Admission(True, EVENT_CLASS, grant["repository"], grant["consumerPr"], identities["admission"]["id"], grant["headSha"], grant["baseSha"], grant["mergeSha"], grant["rootSha"], identities["admission"]["digest"], "ACTIVE_UNEDITED", authenticated["admission"]["updated_at"], authenticated["admission"]["author_association"], "externally selected single-use CI transition")
    result = {k: grant[k] for k in ("rootSha", "rootTree", "closureDigest", "coverageDigest", "baseSha", "headSha", "mergeSha", "consumerPr", "grantId")}
    result.update(grantDigest=digest(grant), **bindings, source=normalized["source"], publisher=normalized.get("publisher"), admissionEvidence=admission.evidence())
    if publisher_phase:
        result["ticket"] = records["publisher"][1]["ticket"]
    return result


@contextmanager
def sweep_deadline(reader, *, scheduled_at=None, wall_clock=utcnow):
    """One wall-clock deadline includes DNS, bodies, parsing and pagination."""
    budget = reader.budget
    previous = budget.deadline
    owns_alarm, prior_handler = False, None
    try:
        allowance = 15 if scheduled_at is None else 15 - (wall_clock().timestamp() - scheduled_at)
        if allowance <= 0 or allowance > 15:
            raise TransitionError("scheduled sweep deadline is unavailable or expired")
        deadline = budget.monotonic() + allowance
        budget.deadline = min(previous, deadline) if previous is not None else deadline
        # A socket timeout cannot bound DNS or a slowly trickling body. The
        # supported Unix CLI also uses one absolute main-thread timer. Nested
        # checks retain the earlier timer, including failure-path cancellation.
        if isinstance(reader, ApiReader):
            if threading.current_thread() is not threading.main_thread():
                raise TransitionError("authority sweep requires the supervised main thread")
            prior_timer = signal.getitimer(signal.ITIMER_REAL)
            owns_alarm = prior_timer == (0.0, 0.0)
            if not owns_alarm and previous is None:
                raise TransitionError("authority sweep cannot replace an ambient timer")
        if owns_alarm:
            timeout = budget.deadline - budget.monotonic()
            if timeout <= 0:
                raise TransitionError("complete authority sweep deadline exceeded")
            prior_handler = signal.getsignal(signal.SIGALRM)
            def expired(_signum, _frame):
                raise TransitionError("complete authority sweep deadline exceeded")
            signal.signal(signal.SIGALRM, expired)
            signal.setitimer(signal.ITIMER_REAL, min(allowance, timeout))
        budget.assert_healthy()
        yield
        budget.remaining_timeout()
    except Exception:
        budget.fail("complete authority sweep refused")
        raise
    finally:
        if owns_alarm and prior_handler is not None:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, prior_handler)
        budget.deadline = previous


def validate_live(policy, grant, reader, *, phase, now=None, event=None, job_context=None, expected_bindings=None):
    with sweep_deadline(reader):
        return _validate_live(policy, grant, reader, phase=phase, now=now,
            event=event, job_context=job_context, expected_bindings=expected_bindings)


def _binding_projection(live):
    return {key: live[key] for key in ("admission", "sourceBinding", "publisherBinding")}


def _typed_bindings(value, *, publisher):
    _keys(value, {"admission", "sourceBinding", "publisherBinding"}, "immutable bindings")
    for key, item in value.items():
        if key == "publisherBinding" and not publisher:
            if item is not None:
                raise TransitionError("source job cannot accept a publisher binding")
            continue
        _keys(item, {"id", "digest"}, "bound record identity")
        _integer(item["id"], "bound comment ID")
        _digest(item["digest"], "bound comment digest")
    return value


def _job_context(args, environment):
    def positive(name):
        value = environment.get(name, "")
        if not re.fullmatch(r"[1-9][0-9]*", value):
            raise TransitionError("required provider job identity is missing")
        return int(value)
    return {"eventName": args.event_name, "sha": args.github_sha,
        "workflowSha": args.workflow_sha, "workflowRef": args.workflow_ref,
        "repository": args.repository, "repositoryId": positive("GITHUB_REPOSITORY_ID"),
        "runId": positive("GITHUB_RUN_ID"), "runAttempt": positive("GITHUB_RUN_ATTEMPT"),
        "actorId": positive("GITHUB_ACTOR_ID"), "ref": environment.get("GITHUB_REF")}


def _read_object(path, label, *, limit=60_000):
    path = Path(path)
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode) or path.is_symlink() or path.stat().st_size > limit:
        raise TransitionError(label + " is not a bounded regular file")
    return _object(decode_json(path.read_bytes()), label)


def authenticate_policy_checkout(checkout, policy, grant):
    """Recompute the declared closure from selected T, never from a receipt."""
    try:
        from conformance import ci_policy_transition_operator as operator
        from conformance import ci_policy_transition_workflows as workflows
    except ModuleNotFoundError:
        import ci_policy_transition_operator as operator
        import ci_policy_transition_workflows as workflows
    checkout = Path(checkout).resolve()
    if _read_object(checkout / ROOT_FILE, "selected policy manifest", limit=1_000_000) != policy:
        raise TransitionError("selected policy manifest changed")
    validate_grant(policy, grant)
    closure = operator.create_policy_closure(checkout, grant["rootSha"], grant["baseSha"], policy["closure"])
    result = operator.verify_policy_closure(checkout, closure, grant["rootSha"], grant["baseSha"],
        grant["closureDigest"], expected_tree=grant["rootTree"])
    # Exact generated workflow bytes are an independent closed-transform check.
    workflows.check_parity(
        (checkout / workflows.SOURCE_INPUT).read_bytes(),
        (checkout / workflows.PUBLICATION_INPUT).read_bytes(),
        (checkout / workflows.SOURCE_OUTPUT).read_bytes(),
        (checkout / workflows.PUBLICATION_OUTPUT).read_bytes(),
        consumer_pr=policy["consumerPullRequest"], policy_root=checkout)
    return result


def discover_binding(policy, reader, *, role, event, job_context, clock=utcnow, sleep=time.sleep):
    """Only an absent first binding may wait; every observed fact is immutable."""
    if role not in WORKFLOWS:
        raise TransitionError("unknown binding role")
    validate_policy(policy)
    root = _sha(job_context.get("workflowSha"), "workflow root")
    prefix = f"refs/heads/ofarm-ci-transition/{role}/"
    ref = _text(event.get("ref"), "activation ref")
    if not ref.startswith(prefix):
        raise TransitionError("activation event is outside the selected role")
    grant_id = ref.removeprefix(prefix)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{7,63}", grant_id):
        raise TransitionError("invalid activation grant ID")
    # This observation fixes the provider clock/window and cancellation owner;
    # a candidate-supplied grant or comment cannot choose the current run.
    run_id = _integer(job_context.get("runId"), "current run ID")
    run = _object(reader(f"/repos/{policy['repository']['name']}/actions/runs/{run_id}"), "gate run")
    created = timestamp(run.get("created_at"))
    deadline = created + timedelta(minutes=5)
    initial = {"id": run_id, "run_attempt": 1, "event": "push", "path": WORKFLOWS[role][0],
        "name": WORKFLOWS[role][1], "head_sha": root, "head_branch": ref.removeprefix("refs/heads/")}
    if any(run.get(key) != value for key, value in initial.items()):
        raise TransitionError("gate run does not match the exact provider push")
    if (_object(run.get("repository"), "gate repository").get("id") != policy["repository"]["id"]
            or run["repository"].get("full_name") != policy["repository"]["name"]
            or any(_object(run.get(key), key).get("id") != policy["operatorId"] for key in ("actor", "triggering_actor"))):
        raise TransitionError("gate run has a different authenticated owner")
    frozen, grant, calls = {}, None, 0
    while True:
        now = clock()
        if now < created or now > deadline or calls >= 21:
            raise TransitionError("first binding did not arrive within the bounded gate")
        # Every discovery page spends one of the same 21 requests. Pagination
        # is never an uncharged extension or an incomplete absence proof.
        comments, seen = [], set()
        for page in range(1, 4):
            if calls >= 21:
                raise TransitionError("binding discovery exhausted its bounded page allowance")
            items = reader(f"/repos/{policy['repository']['name']}/issues/{policy['consumerPullRequest']}/comments?per_page=100&page={page}")
            calls += 1
            if not isinstance(items, list) or len(items) > 100:
                raise TransitionError("binding discovery has an invalid complete page")
            for item in items:
                _object(item, "discovery comment")
                identity = _integer(item.get("id"), "discovery comment ID")
                if identity in seen:
                    raise TransitionError("binding discovery repeated a comment")
                seen.add(identity)
                comments.append(item)
            if len(items) < 100:
                break
        else:
            raise TransitionError("binding discovery cannot prove a complete bounded scan")
        observed_at = clock()
        if not now <= observed_at <= deadline:
            raise TransitionError("first binding did not arrive within the bounded gate")
        # A binding may be created while the complete scan is in flight. Judge
        # its timestamp at observation, without extending discovery or expiry.
        now = observed_at
        records = _record_set(comments, grant_id)
        if "admission" not in records:
            raise TransitionError("source admission must predate activation and remain present")
        candidate = _keys(records["admission"][1], {"grant", "grantDigest"}, "admission footer")
        current = candidate["grant"]
        validate_grant(policy, current, now=now)
        if candidate["grantDigest"] != digest(current) or current["rootSha"] != root or current[role+"Ref"] != ref:
            raise TransitionError("discovered grant differs from exact selected root/ref")
        if grant is not None and current != grant:
            raise TransitionError("grant changed during discovery")
        grant = current
        _event_identity(grant, role, event, job_context, run)
        if timestamp(records["admission"][0].get("created_at")) > created:
            raise TransitionError("admission was created after activation")
        observed = {name: _comment_identity(comment, grant, now=now)
                    for name, (comment, _payload) in records.items()}
        if any(observed.get(name) != identity for name, identity in frozen.items()):
            raise TransitionError("previously observed binding disappeared or changed")
        frozen.update(observed)
        required = {"admission", "source"} if role == "source" else {"admission", "source", "publisher"}
        if set(records) - required:
            raise TransitionError("future binding exists before its permitted stage")
        if set(records) == required:
            phase = "source-gate" if role == "source" else "publisher-gate"
            live = validate_live(policy, grant, reader, phase=phase, now=now, event=event,
                                 job_context=job_context)
            if any(live[{"admission": "admission", "source": "sourceBinding", "publisher": "publisherBinding"}[name]] != identity
                   for name, identity in frozen.items()):
                raise TransitionError("binding changed between discovery and full gate")
            return grant, live
        remaining = (deadline-clock()).total_seconds()
        if remaining <= 0:
            raise TransitionError("binding window expired")
        sleep(min(15, remaining))


_SOURCE_JOBS = frozenset({"source-gate", "conformance", "native-amd64", "native-arm64", "source-guard", "handoff"})
_PUBLISHER_JOBS = frozenset({"publisher-gate", "source-admission", "publish", "publisher-guard", "seal"})


def require_quota_headroom(reader, grant, phase, *, now=None, guard_complete=False, completed_tick=None):
    """Check affordability of remaining work; a snapshot reserves no capacity."""
    now = (now or utcnow()).timestamp()
    job = PHASE_JOBS[phase]
    first_tick = math.ceil(now/120)*120
    if completed_tick is not None:
        # Only run_guard supplies this fact, after its complete live/job sweep.
        # Its current isolated pool must own that tick. Neither a sibling's
        # ledger nor a provider remaining-counter delta establishes completion.
        if (job not in {"source-guard", "publisher-guard"} or reader.budget.job != job
                or type(completed_tick) is not int or completed_tick % 120
                or not 0 <= now-completed_tick < 15
                or reader.budget.current_pool != f"periodic:{completed_tick}"
                or f"periodic:{completed_tick}" not in reader.budget.used):
            raise TransitionError("completed tick must belong to this guard's current full sweep")
        first_tick = max(first_tick, completed_tick+120)
    if job == "external-acceptance":
        future = {"external-acceptance"}
    elif job == "source-gate":
        future = set(_SOURCE_JOBS | _PUBLISHER_JOBS)
    elif job in {"conformance", "native-amd64", "native-arm64", "source-guard"}:
        future = set((_SOURCE_JOBS - {"source-gate"}) | _PUBLISHER_JOBS)
    elif job == "handoff":
        future = {"handoff", *_PUBLISHER_JOBS}
    elif job == "publisher-gate":
        future = set(_PUBLISHER_JOBS)
    elif job == "source-admission":
        future = set(_PUBLISHER_JOBS - {"publisher-gate"})
    elif job in {"publish", "publisher-guard"}:
        future = {"publish", "publisher-guard", "seal"}
    elif job == "seal":
        future = {"seal"}
    else:
        raise TransitionError("phase has no approved request forecast")
    if guard_complete:
        if job == "source-guard":
            future = {"handoff", *_PUBLISHER_JOBS}
        elif job == "publisher-guard":
            future = {"seal"}
        else:
            raise TransitionError("only a completed guard may exclude guarded work")
    future.add("external-acceptance")
    remaining = [0, 0]
    for future_job in future:
        limits = TOOL_ALLOCATIONS["external-acceptance"] if future_job == "external-acceptance" else tuple(
            POOL_LIMITS[future_job][index] + TOOL_ALLOCATIONS[future_job][index] for index in (0, 1))
        for index in (0, 1):
            remaining[index] += limits[index]
    if "publish" in future:
        remaining[0] += POOL_LIMITS["source-reader"][0]
    # Only this reader's actually charged work is locally knowable. Other jobs'
    # unused allowance is never counted as a saving or a new token bucket.
    for pool, spent in reader.budget.used.items():
        if (job in future and pool in {job, "shared-tools"}) or (pool == "source-reader" and "publish" in future):
            remaining = [max(0, remaining[index]-spent[index]) for index in (0, 1)]
    periodic = bool(future & {"source-guard", "publisher-guard"})
    return reader.budget.require_headroom(future_rest=remaining[0]+75, future_graphql=remaining[1]+75,
        first_tick=first_tick if periodic else None,
        periodic_end=min(timestamp(grant["expiresAt"]).timestamp(), now+3600) if periodic else None)


def _producer_state(reader, grant, live, role):
    run_id = live[role]["runId"]
    jobs = reader.jobs(grant["repository"], run_id)
    required = PRODUCER_NAMES if role == "source" else PUBLISHER_NAMES
    expected = (PRODUCER_NAMES | {"live exact-head review admission", "source guard", "seal exact provisional publication handoff"}
                if role == "source" else PUBLISHER_NAMES | {"bind the one publisher attempt",
                "authenticate exact producer run and publication ticket", "publisher guard",
                "seal transition publication on a fresh trusted runner"})
    names = [job.get("name") for job in jobs]
    if (len(names) != len(set(names)) or not required <= set(names)
            or not set(names) <= expected):
        raise TransitionError("expected guarded job inventory is absent, extra or duplicated")
    completed = True
    for job in jobs:
        if job["name"] not in required:
            continue
        if job.get("status") == "completed":
            if job.get("conclusion") != "success":
                raise TransitionError("required producer failed, skipped or cancelled")
        elif job.get("status") in {"queued", "waiting", "pending", "in_progress"} and job.get("conclusion") is None:
            completed = False
        else:
            raise TransitionError("producer state is unknown")
    return completed


def run_guard(policy, grant, reader, *, phase, event, job_context, expected_bindings,
              clock=utcnow, monotonic=time.monotonic, sleep=time.sleep):
    if phase not in {"source-guard", "publisher-guard"}:
        raise TransitionError("only isolated guard jobs may run the guard")
    role = "source" if phase == "source-guard" else "publisher"
    started = monotonic()
    duration = 135*60 if role == "source" else 60*60
    authenticated_id = None
    next_tick = None
    try:
        while True:
            now = clock()
            if monotonic()-started >= duration or now >= timestamp(grant["expiresAt"]):
                raise TransitionError("guard reached its fixed timeout or grant expiry")
            periodic = next_tick is not None
            if periodic:
                # A late wakeup may not replace a missed required sweep with a
                # catch-up burst. Subsecond scheduler resolution is explicit.
                if now.timestamp() - next_tick >= 1:
                    raise TransitionError("guard missed its globally aligned scheduled sweep")
                pool = f"periodic:{int(next_tick)}"
            else:
                pool = PHASE_JOBS[phase]
            with reader.pool(pool), sweep_deadline(reader, scheduled_at=next_tick if periodic else None, wall_clock=clock):
                live = validate_live(policy, grant, reader, phase=phase, now=now,
                    event=event, job_context=job_context, expected_bindings=expected_bindings)
                authenticated_id = live[role]["runId"]
                if authenticated_id != job_context["runId"]:
                    raise TransitionError("guard provider run differs from its job context")
                complete = _producer_state(reader, grant, live, role)
                require_quota_headroom(reader, grant, phase, now=clock(), guard_complete=complete,
                    completed_tick=int(next_tick) if periodic else None)
            if complete:
                # Completion always earns its own fresh nonperiodic full sweep;
                # neither the initial nor a periodic snapshot substitutes for it.
                with reader.pool(PHASE_JOBS[phase]), sweep_deadline(reader):
                    final = validate_live(policy, grant, reader, phase=phase, now=clock(),
                        event=event, job_context=job_context, expected_bindings=expected_bindings)
                    if not _producer_state(reader, grant, final, role):
                        raise TransitionError("producer completion changed before final guard check")
                    require_quota_headroom(reader, grant, phase, now=clock(), guard_complete=True)
                return final
            next_tick = (math.floor(now.timestamp()/120)+1)*120
            # If a full sweep crossed its next required tick, fail before sleep.
            if clock().timestamp() >= next_tick:
                raise TransitionError("complete sweep missed the next global tick")
            delay = min(next_tick-clock().timestamp(),
                        (timestamp(grant["expiresAt"])-clock()).total_seconds(),
                        duration-(monotonic()-started))
            if delay <= 0:
                raise TransitionError("guard cannot reach its next required observation")
            sleep(delay)
    except Exception:
        # Cancellation can only target the ID already authenticated from this
        # guard's provider record. Failure to cancel never restores authority.
        try:
            with reader.budget.cancellation(), reader.pool("shared-tools"), sweep_deadline(reader):
                if authenticated_id is None:
                    run, identity = _run(reader, grant, role,
                        {"runId": job_context["runId"], "runAttempt": 1}, completed=False)
                    _event_identity(grant, role, event, job_context, run)
                    authenticated_id = identity["runId"]
                reader.cancel_own_run(grant["repository"], authenticated_id, job_context["runId"])
        except Exception:
            pass
        reader.budget.fail("guard permanently refused")
        raise


def _admission_outputs(grant, live):
    evidence = live["admissionEvidence"]
    return {"eligible": "true", "pull_request_number": grant["consumerPr"],
        "admission_comment_id": live["admission"]["id"], "reviewed_head_sha": grant["headSha"],
        "base_sha": grant["baseSha"], "execution_merge_sha": grant["mergeSha"],
        "policy_sha": grant["rootSha"], "review_body_sha256": live["admission"]["digest"],
        "review_state": "ACTIVE_UNEDITED", "review_updated_at": evidence["review_updated_at"],
        "reviewer_association": evidence["reviewer_association"], "reason": "exact single-use transition admitted",
        "transition_grant": canonical_json(grant).decode().strip(),
        "transition_bindings": canonical_json(_binding_projection(live)).decode().strip()}


def execute(args, *, environment=None, reader=None, checkout=None, clock=utcnow, sleep=time.sleep):
    permitted = {
        "admit": {"source-gate", "publisher-gate", "conformance", "native-amd64", "native-arm64", "handoff-start"},
        "guard": {"source-guard", "publisher-guard"},
        "resolve": {"source-admission-resolve", "publisher-resolve", "seal-resolve"},
        "publish": {"source-admission", "publisher-start", "prepublish", "preindex", "seal-start"},
        "handoff": {"handoff"}, "seal": {"seal"},
    }
    if args.phase not in permitted.get(args.operation, set()):
        raise TransitionError("operation does not belong to this fixed workflow phase")
    environment = os.environ if environment is None else environment
    checkout = Path(checkout) if checkout is not None else Path(__file__).resolve().parents[1]
    policy = validate_policy(_read_object(checkout / ROOT_FILE, "root manifest", limit=1_000_000))
    if args.policy_sha != args.workflow_sha or args.github_sha != args.workflow_sha:
        raise TransitionError("event and workflow must select the same immutable policy")
    _sha(args.policy_sha, "selected policy SHA")
    if args.repository != policy["repository"]["name"]:
        raise TransitionError("job repository differs from root")
    event = _read_object(args.event_path, "push event", limit=1_000_000)
    context = _job_context(args, environment)
    if args.event_name != "push" or context["runAttempt"] != 1:
        raise TransitionError("transition executes only its original push attempt")
    args.event, args.job_context = event, context
    reader = reader or make_reader(args.phase, policy, api_url=environment.get("GITHUB_API_URL", "https://api.github.com"), environment=environment)
    job = PHASE_JOBS[args.phase]
    if environment.get("GITHUB_ACTIONS") == "true":
        tool_policy.assert_supervisor(environment, job)
    try:
        gate = args.phase in {"source-gate", "publisher-gate"}
        if gate:
            if args.grant_json is not None or args.bindings_json is not None or args.operation != "admit":
                raise TransitionError("binding gates cannot accept candidate grant inputs")
            role = "source" if args.phase == "source-gate" else "publisher"
            grant, live = discover_binding(policy, reader, role=role, event=event,
                                          job_context=context, clock=clock, sleep=sleep)
            bindings = _binding_projection(live)
        else:
            if args.grant_json is None or args.bindings_json is None:
                raise TransitionError("governed phase requires immutable gate outputs")
            if len(args.grant_json.encode()) > 60_000 or len(args.bindings_json.encode()) > 4096:
                raise TransitionError("gate output exceeds typed bound")
            grant = validate_grant(policy, decode_json(args.grant_json), now=clock())
            bindings = _typed_bindings(decode_json(args.bindings_json), publisher=args.phase in PUBLISHER_PHASES)
            live = None
        if grant["rootSha"] != args.policy_sha:
            raise TransitionError("grant selected another root")
        authenticate_policy_checkout(checkout, policy, grant)
        if args.operation == "guard":
            live = run_guard(policy, grant, reader, phase=args.phase, event=event,
                job_context=context, expected_bindings=bindings, clock=clock, sleep=sleep)
            result = live
        elif args.operation == "admit":
            if not gate:
                live = validate_live(policy, grant, reader, phase=args.phase, now=clock(),
                    event=event, job_context=context, expected_bindings=bindings)
            require_quota_headroom(reader, grant, args.phase, now=clock())
            result = live
        elif args.operation in {"resolve", "publish", "handoff", "seal"}:
            try:
                from conformance import ci_policy_transition_publication as publication
            except ModuleNotFoundError:
                import ci_policy_transition_publication as publication
            # Publication adapters retain the same immutable bindings at every
            # recheck and invoke the original substantive validators themselves.
            args.transition_bindings = bindings
            result = publication.run_operation(args, policy=policy, grant=grant, reader=reader)
            if args.operation != "resolve":
                require_quota_headroom(reader, grant, args.phase, now=clock())
        else:
            raise TransitionError("operation is not permitted by the core")
        authenticate_policy_checkout(checkout, policy, grant)
        reader.budget.assert_healthy()
        if environment.get("GITHUB_ACTIONS") == "true":
            tool_policy.assert_supervisor(environment, job)
        if args.operation in {"admit", "guard"}:
            if args.github_output is not None:
                ordinary._write_output(args.github_output, _admission_outputs(grant, live))
            if args.evidence_output is not None:
                args.evidence_output.write_bytes(canonical_json(live["admissionEvidence"]))
        return result
    except Exception:
        reader.budget.fail("governed operation permanently refused")
        raise


def _refusal_diagnostic(exc):
    """Allowlisted locations/statuses and typed quota facts, never arbitrary text."""
    names = ("ci_policy_transition.py", "ci_policy_transition_tools.py",
             "ci_policy_transition_operator.py", "ci_policy_transition_workflows.py",
             "ci_policy_transition_publication.py")
    allowed = {str(_TRUSTED_ROOT / "conformance" / name): name for name in names}
    locations, statuses, seen = [], [], set()
    quota_window = None
    for _ in range(8):
        if exc is None or id(exc) in seen:
            break
        seen.add(id(exc))
        if quota_window is None and type(exc) is tool_policy.QuotaWindowError:
            quota_window = tool_policy.QuotaWindowError.diagnostic(exc)
        if isinstance(exc, urllib.error.HTTPError):
            status = exc.code
            if type(status) is int and 100 <= status <= 599 and status not in statuses:
                statuses.append(status)
        frame = exc.__traceback__
        for _ in range(32):
            if frame is None:
                break
            name = allowed.get(os.path.abspath(frame.tb_frame.f_code.co_filename))
            if name is not None and type(frame.tb_lineno) is int and 0 < frame.tb_lineno <= 100_000:
                locations.append({"file": name, "line": frame.tb_lineno})
            frame = frame.tb_next
        exc = exc.__cause__ if exc.__cause__ is not None else (
            None if exc.__suppress_context__ else exc.__context__)
    result = {"schemaVersion": "ofarm.ci-transition-refusal-diagnostic.v1",
              "locations": locations[-12:], "httpStatus": statuses}
    if quota_window is not None:
        result["quotaWindow"] = quota_window
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", choices=("admit", "guard", "resolve", "publish", "handoff", "seal"), required=True)
    parser.add_argument("--phase", choices=tuple(PHASE_JOBS), required=True)
    for name in ("event-name", "github-sha", "workflow-sha", "workflow-ref", "repository", "policy-sha"):
        parser.add_argument("--"+name, required=True)
    parser.add_argument("--event-path", type=Path, required=True)
    for name in ("github-output", "evidence-output", "ticket-output", "ticket", "published-artifacts-input", "publication-receipt-output"):
        parser.add_argument("--"+name, type=Path)
    for name in ("source-run-id", "source-run-attempt", "publisher-run-id", "publisher-run-attempt"):
        parser.add_argument("--"+name, type=int)
    parser.add_argument("--grant-json")
    parser.add_argument("--bindings-json")
    args = parser.parse_args(argv)
    try:
        execute(args)
    except (TransitionError, ValueError, OSError) as exc:
        # Runtime messages describe policy conditions, never provider bodies or
        # arbitrary exception text that could contain credentials/signed URLs.
        print("CI policy transition refused; no authority output accepted", file=sys.stderr)
        try:
            print("CI policy transition diagnostic: " + json.dumps(_refusal_diagnostic(exc),
                sort_keys=True, separators=(",", ":")), file=sys.stderr)
        except Exception:
            # Diagnostics cannot replace the original refusal, even when a
            # malformed exception or unavailable stderr prevents formatting.
            pass
        return 1
    print("CI policy transition: authenticated bounded operation complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
