"""Fictional complete provider observations exercise the actual transition core."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import urllib.error
import urllib.parse
from unittest import mock

import pytest

from conformance import ci_policy_transition as transition


NOW = datetime(2030, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def policy_and_grant():
    policy = {"schemaVersion": transition.POLICY_SCHEMA,
        "repository": {"name": "fictional-farm/transition-fixture", "id": 9100},
        "operatorId": 9200, "consumerPullRequest": 413, "transitionPullRequest": 417,
        "baseSha": "2" * 40, "campaign": {"id": "fictional-campaign",
            "notBefore": "2030-01-01T00:00:00Z", "sunset": "2030-01-07T00:00:00Z"},
        "closure": {}, "coverageDigest": transition.coverage.coverage_digest(), "requestPlan": {"periodSeconds": 120, "sweepDeadlineSeconds": 15,
            "periodicREST": 15, "periodicGraphQL": 5,
            "pools": {key: list(value) for key, value in transition.POOL_LIMITS.items()},
            "toolAllocations": {key: list(value) for key, value in transition.TOOL_ALLOCATIONS.items()},
            "sharedMargin": [75, 75]}}
    decision = {"id": "OFARM2-CI-POLICY-TRANSITION-001", "version": 4,
        "cardRef": "fictional-decision-card", "approvalRef": "fictional-decision-approval",
        "threadId": "fictional-task"}
    grant = {"schemaVersion": transition.GRANT_SCHEMA, "grantId": "fictional-grant",
        "repository": policy["repository"]["name"], "repositoryId": 9100, "operatorId": 9200,
        "transitionPullRequest": 417, "consumerPr": 413,
        "rootSha": "1" * 40, "rootTree": "5" * 40, "closureDigest": "sha256:" + "6" * 64,
        "coverageDigest": transition.coverage.coverage_digest(),
        "baseSha": "2" * 40, "headSha": "3" * 40, "mergeSha": "4" * 40,
        "decision": decision, "consumerDecision": {**decision, "id": "FICTIONAL-CONSUMER-001",
            "version": 1, "cardRef": "fictional-consumer-card", "approvalRef": "fictional-consumer-approval"},
        "review": {"rootReviewRef": "fictional-root-review", "consumerReviewRef": "fictional-consumer-review"},
        "campaignId": "fictional-campaign", "notBefore": "2030-01-01T00:00:00Z",
        "expiresAt": "2030-01-02T00:00:00Z",
        "sourceRef": "refs/heads/ofarm-ci-transition/source/fictional-grant",
        "publisherRef": "refs/heads/ofarm-ci-transition/publisher/fictional-grant",
        "journal": {"genesisDigest": "sha256:" + "7" * 64, "formatVersion": 1}}
    return policy, grant


class Response(io.BytesIO):
    def __init__(self, url, payload, headers, status=200):
        super().__init__(payload)
        self.status, self.headers, self.url = status, headers, url
        self.headers.setdefault("Content-Length", str(len(payload)))

    def geturl(self):
        return self.url


class Provider:
    def __init__(self, *, publisher=False):
        self.policy, self.grant = policy_and_grant()
        self.now = NOW
        self.publisher = publisher
        self.calls, self.rest, self.points = [], 0, 0
        self.graph_cost = 1
        self.rest_remaining, self.graph_remaining = 1000, 1000
        self.reset = int((NOW+timedelta(hours=1)).timestamp())
        self.fail_status = None
        self.fault = None
        self.producers_complete = True
        self.cancelled = []
        self.comments = []
        admission = self.comment(101, "admission", {"grant": self.grant, "grantDigest": transition.digest(self.grant)}, 0)
        self.comments.append(admission)
        self.comments.append(self.comment(102, "source", {"grantId": self.grant["grantId"],
            "grantDigest": transition.digest(self.grant), "rootSha": self.grant["rootSha"],
            "admission": self.identity(admission), "source": {"runId": 201, "runAttempt": 1}}, 2))
        if publisher:
            self.comments.append(self.comment(103, "publisher", {"grantId": self.grant["grantId"],
                "grantDigest": transition.digest(self.grant), "rootSha": self.grant["rootSha"],
                "admission": self.identity(admission), "source": {"runId": 201, "runAttempt": 1},
                "sourceBinding": self.identity(self.comments[1]), "publisher": {"runId": 202, "runAttempt": 1},
                "ticket": {"id": 301, "digest": "sha256:" + "8" * 64}}, 4))
        self.event, self.context = self.push("publisher" if publisher else "source")

    def comment(self, identity, role, payload, second):
        return {"id": identity, "node_id": "fictional-comment-" + str(identity),
            "body": transition.record_body(role, payload),
            "created_at": stamp(NOW-timedelta(seconds=10-second)),
            "updated_at": stamp(NOW-timedelta(seconds=10-second)), "author_association": "OWNER",
            "user": {"id": 9200}, "issue_url": f"https://api.github.com/repos/{self.grant['repository']}/issues/413"}

    @staticmethod
    def identity(comment):
        return {"id": comment["id"], "digest": transition.digest(comment["body"].encode())}

    def bindings(self):
        return {"admission": self.identity(self.comments[0]), "sourceBinding": self.identity(self.comments[1]),
            "publisherBinding": self.identity(self.comments[2]) if self.publisher else None}

    def push(self, role):
        grant = self.grant
        event = {"created": True, "deleted": False, "forced": False, "before": "0" * 40,
            "after": grant["rootSha"], "ref": grant[role+"Ref"],
            "repository": {"id": 9100, "full_name": grant["repository"]}, "sender": {"id": 9200}}
        context = {"eventName": "push", "sha": grant["rootSha"], "workflowSha": grant["rootSha"],
            "workflowRef": f"{grant['repository']}/{transition.WORKFLOWS[role][0]}@{grant[role+'Ref']}",
            "repository": grant["repository"], "repositoryId": 9100, "runId": 201 if role == "source" else 202,
            "runAttempt": 1, "actorId": 9200, "ref": grant[role+"Ref"]}
        return event, context

    def run(self, role):
        return {"id": 201 if role == "source" else 202, "run_attempt": 1, "event": "push",
            "path": transition.WORKFLOWS[role][0], "name": transition.WORKFLOWS[role][1],
            "head_sha": self.grant["rootSha"], "head_branch": self.grant[role+"Ref"].removeprefix("refs/heads/"),
            "repository": {"id": 9100, "full_name": self.grant["repository"]},
            "actor": {"id": 9200}, "triggering_actor": {"id": 9200},
            "status": "completed" if self.publisher and role == "source" else "in_progress",
            "conclusion": "success" if self.publisher and role == "source" else None,
            "created_at": "2030-01-01T00:00:01Z" if role == "source" else "2030-01-01T00:00:03Z"}

    def jobs(self, role):
        names = (["live exact-head review admission", "conformance", "native verifier (amd64)",
            "native verifier (arm64)", "source guard", "seal exact provisional publication handoff"] if role == "source"
            else ["bind the one publisher attempt", "authenticate exact producer run and publication ticket",
                "derive and publish authoritative evidence", "publisher guard", "seal transition publication on a fresh trusted runner"])
        required = transition.PRODUCER_NAMES if role == "source" else transition.PUBLISHER_NAMES
        return {"total_count": len(names), "jobs": [{"id": 1000+index, "name": name,
            "run_id": 201 if role == "source" else 202, "run_attempt": 1,
            "status": "completed" if name in required and self.producers_complete else "in_progress",
            "conclusion": "success" if name in required and self.producers_complete else None}
            for index, name in enumerate(names)]}

    def graph(self, variables):
        grant = self.grant
        nodes = []
        for identity in variables["ids"]:
            comment = next(c for c in self.comments if c["node_id"] == identity)
            nodes.append({"databaseId": comment["id"], "body": comment["body"],
                "authorAssociation": comment["author_association"], "createdAt": comment["created_at"],
                "updatedAt": comment["updated_at"], "lastEditedAt": None, "isMinimized": False,
                "author": {"databaseId": 9200}, "issue": {"number": 413,
                    "repository": {"nameWithOwner": grant["repository"], "databaseId": 9100}}})
        return {"nodes": nodes, "repository": {"databaseId": 9100, "nameWithOwner": grant["repository"],
            "pullRequest": {"number": 413, "state": "OPEN", "headRefOid": grant["headSha"],
                "baseRefOid": grant["baseSha"], "baseRefName": "main", "timelineItems": {"totalCount": 0,
                    "nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}},
            "rateLimit": {"cost": self.graph_cost, "limit": 1000,
                "remaining": self.graph_remaining-self.points, "resetAt": stamp(datetime.fromtimestamp(self.reset, timezone.utc))}}

    def opener(self, request, timeout):
        assert timeout > 0
        url = urllib.parse.urlsplit(request.full_url)
        path = url.path.removeprefix("/repos/" + self.grant["repository"])
        self.calls.append((request.get_method(), path, url.query))
        if path == "/graphql":
            self.points += self.graph_cost
        else:
            self.rest += 1
        headers = {"X-RateLimit-Remaining": str(self.rest_remaining-self.rest),
            "X-RateLimit-Reset": str(self.reset), "X-RateLimit-Limit": "1000"}
        if self.fail_status is not None:
            raise urllib.error.HTTPError(request.full_url, self.fail_status, "fictional failure", headers, io.BytesIO(b""))
        if path == "/graphql":
            body = {"data": self.graph(json.loads(request.data)["variables"])}
        elif path == "/issues/413/comments":
            page = int(urllib.parse.parse_qs(url.query).get("page", ["1"])[0])
            body = self.comments[(page-1)*100:page*100]
        elif path.startswith("/issues/comments/"):
            body = next(c for c in self.comments if c["id"] == int(path.rsplit("/", 1)[1]))
        elif path == "/pulls/413":
            body = {"number": 413, "state": "open", "merged": False, **{side: {
                "sha": self.grant[side+"Sha"], "repo": {"id": 9100, "full_name": self.grant["repository"]},
                "ref": "main" if side == "base" else "fictional-candidate"} for side in ("head", "base")}}
        elif path.startswith("/git/ref/"):
            ref = path.removeprefix("/git/ref/")
            if ref == self.grant["publisherRef"].removeprefix("refs/") and not self.publisher:
                raise urllib.error.HTTPError(request.full_url, 404, "absent", headers, io.BytesIO(b""))
            sha = self.grant["baseSha"] if ref == "heads/main" else self.grant["mergeSha"] if ref == "pull/413/merge" else self.grant["rootSha"]
            body = {"ref": "refs/"+ref, "object": {"type": "commit", "sha": sha}}
        elif path.startswith("/git/commits/"):
            body = {"sha": self.grant["mergeSha"], "parents": [{"sha": self.grant["baseSha"]}, {"sha": self.grant["headSha"]}]}
        elif path.endswith("/cancel"):
            self.cancelled.append(int(path.split("/")[3]))
            return Response(request.full_url, b"", headers, status=202)
        elif path.endswith("/jobs"):
            body = self.jobs("source" if "/201/" in path else "publisher")
        elif path.startswith("/actions/runs/"):
            body = self.run("source" if path.endswith("/201") else "publisher")
        else:
            raise AssertionError("unexpected fictional API path: " + path)
        body = copy.deepcopy(body)
        if self.fault is not None:
            self.fault(path, body)
        return Response(request.full_url, transition.canonical_json(body), headers)

    def reader(self, phase):
        budget = transition.RequestBudget(transition.PHASE_JOBS[phase], clock=lambda: self.now.timestamp())
        return transition.ApiReader("fictional-workflow-token", budget=budget, opener=self.opener)


def validate(provider, phase):
    reader = provider.reader(phase)
    result = transition.validate_live(provider.policy, provider.grant, reader, phase=phase,
        now=provider.now, event=provider.event, job_context=provider.context,
        expected_bindings=provider.bindings())
    return result, reader


@pytest.mark.parametrize("publisher,phase,calls", [(False, "source-gate", 10), (True, "publisher-gate", 12)])
def test_complete_live_positive_records_every_actual_primary_request(publisher, phase, calls):
    provider = Provider(publisher=publisher)
    result, reader = validate(provider, phase)
    assert result["admissionEvidence"]["event_class"] == transition.EVENT_CLASS
    assert result["source"]["workflowSha"] == provider.grant["rootSha"]
    assert provider.rest == calls
    assert provider.points == 1
    assert reader.budget.used[transition.PHASE_JOBS[phase]] == [calls, 1]
    required = transition.require_quota_headroom(reader, provider.grant, phase, now=provider.now)
    assert required["REST"] <= 990


@pytest.mark.parametrize("mutation,message", [
    (lambda p: p.grant["decision"].update(version=3), "version 4"),
    (lambda p: p.comments[0].update(updated_at="2030-01-01T00:00:01Z"), "edited"),
    (lambda p: p.comments[0]["user"].update(id=9999), "operator"),
    (lambda p: p.comments.append(copy.deepcopy(p.comments[0])), "duplicate comment"),
    (lambda p: p.event.update(forced=True), "new operator-created"),
    (lambda p: p.context.update(runAttempt=2), "job context"),
    (lambda p: p.comments.pop(1), "missing"),
    (lambda p: p.comments[0].update(author_association="NONE"), "operator"),
])
def test_single_fault_reaches_intended_live_refusal(mutation, message):
    provider = Provider()
    bindings = provider.bindings()
    mutation(provider)
    with pytest.raises(transition.TransitionError, match=message):
        transition.validate_live(provider.policy, provider.grant, provider.reader("source-gate"), phase="source-gate",
            now=provider.now, event=provider.event, job_context=provider.context, expected_bindings=bindings)


@pytest.mark.parametrize("kind", ["transition", "ordinary", "lifecycle", "minimized", "base", "parents", "actor", "run-attempt", "graph-cost"])
def test_each_revocation_and_provenance_fault_refuses_its_real_observation(kind):
    provider = Provider()
    if kind == "transition":
        provider.comments.append(provider.comment(109, "revocation", {"grantId": provider.grant["grantId"]}, 5))
        message = "reviewer revoked"
    elif kind == "ordinary":
        item = provider.comment(109, "revocation", {}, 5)
        item["body"] = ordinary_body = f"OFARM2_BASELINE_REVOCATION\nhead={provider.grant['headSha']}\n"
        assert ordinary_body
        provider.comments.append(item)
        message = "exact-head revocation"
    else:
        def fault(path, body):
            if kind == "lifecycle" and path == "/graphql":
                body["data"]["repository"]["pullRequest"]["timelineItems"] = {"totalCount": 1,
                    "nodes": [{"__typename": "ReopenedEvent", "id": "fictional-reopen", "createdAt": "2030-01-01T00:00:05Z"}],
                    "pageInfo": {"hasNextPage": False, "endCursor": None}}
            if kind == "minimized" and path == "/graphql":
                body["data"]["nodes"][0]["isMinimized"] = True
            if kind == "base" and path == "/pulls/413":
                body["base"]["sha"] = "9" * 40
            if kind == "parents" and path.startswith("/git/commits/"):
                body["parents"].reverse()
            if kind == "actor" and path == "/actions/runs/201":
                body["triggering_actor"]["id"] = 9999
            if kind == "run-attempt" and path == "/actions/runs/201":
                body["run_attempt"] = 2
        provider.fault = fault
        if kind == "graph-cost":
            provider.graph_cost = 11
        message = {"lifecycle": "lifecycle changed", "minimized": "minimized",
            "base": "drift", "parents": "parents", "actor": "actor", "run-attempt": "attempt",
            "graph-cost": "pool|limit|budget|exceed"}[kind]
    with pytest.raises(transition.TransitionError, match=message):
        validate(provider, "source-gate")


@pytest.mark.parametrize("status", [403, 429, 500])
def test_first_network_failure_latches_even_if_next_response_would_succeed(status):
    provider = Provider()
    reader = provider.reader("source-gate")
    provider.fail_status = status
    with pytest.raises(transition.TransitionError):
        reader("/repos/fictional-farm/transition-fixture/pulls/413")
    provider.fail_status = None
    with pytest.raises(transition.TransitionError):
        reader("/repos/fictional-farm/transition-fixture/pulls/413")
    assert len(provider.calls) == 1


def test_actual_low_quota_refuses_after_complete_positive_observations():
    provider = Provider()
    provider.rest_remaining = 200
    _result, reader = validate(provider, "source-gate")
    with pytest.raises(transition.TransitionError, match="quota|headroom"):
        transition.require_quota_headroom(reader, provider.grant, "source-gate", now=provider.now)


def test_binding_discovery_never_rebinds_an_observed_admission():
    provider = Provider()
    source = provider.comments.pop()
    reader = provider.reader("source-gate")
    waits = []
    def sleep(seconds):
        waits.append(seconds)
        provider.now += timedelta(seconds=seconds)
        provider.comments[0]["body"] += "edited"
        provider.comments.append(source)
    with pytest.raises(transition.TransitionError, match="admission|changed"):
        transition.discover_binding(provider.policy, reader, role="source", event=provider.event,
            job_context=provider.context, clock=lambda: provider.now, sleep=sleep)
    assert waits == [15]


def test_binding_discovery_positive_waits_once_then_performs_complete_gate():
    provider = Provider()
    source = provider.comments.pop()
    reader = provider.reader("source-gate")
    def sleep(seconds):
        provider.now += timedelta(seconds=seconds)
        provider.comments.append(source)
    grant, live = transition.discover_binding(provider.policy, reader, role="source", event=provider.event,
        job_context=provider.context, clock=lambda: provider.now, sleep=sleep)
    assert grant == provider.grant
    assert live["source"]["runId"] == 201
    assert provider.rest == 13
    assert provider.points == 1


def test_binding_discovery_expires_without_starting_a_producer():
    provider = Provider()
    provider.comments.pop()
    reader = provider.reader("source-gate")
    waits = []
    def sleep(seconds):
        waits.append(seconds)
        provider.now += timedelta(seconds=seconds)
    with pytest.raises(transition.TransitionError, match="binding.*(bounded|expired)|window expired"):
        transition.discover_binding(provider.policy, reader, role="source", event=provider.event,
            job_context=provider.context, clock=lambda: provider.now, sleep=sleep)
    assert len([call for call in provider.calls if call[1] == "/issues/413/comments"]) <= 21
    assert provider.now <= datetime(2030, 1, 1, 0, 5, 1, tzinfo=timezone.utc)
    assert provider.points == 0


@pytest.mark.parametrize("publisher", [False, True])
def test_guard_positive_uses_two_complete_sweeps_and_no_dependent_job_cycle(publisher):
    provider = Provider(publisher=publisher)
    phase = "publisher-guard" if publisher else "source-guard"
    reader = provider.reader(phase)
    result = transition.run_guard(provider.policy, provider.grant, reader, phase=phase,
        event=provider.event, job_context=provider.context, expected_bindings=provider.bindings(),
        clock=lambda: provider.now, sleep=lambda _seconds: pytest.fail("completed producer must not wait for dependent seal"))
    assert result["grantId"] == provider.grant["grantId"]
    assert provider.rest == (26 if publisher else 22)
    assert provider.points == 2
    assert not provider.cancelled


def test_guard_tick_is_global_across_source_and_publisher_start_positions():
    for publisher in (False, True):
        provider = Provider(publisher=publisher)
        phase = "publisher-guard" if publisher else "source-guard"
        provider.now = NOW.replace(minute=1, second=10)
        provider.producers_complete = False
        reader = provider.reader(phase)
        waits = []
        def sleep(seconds):
            waits.append(seconds)
            provider.now += timedelta(seconds=seconds)
            provider.producers_complete = True
        transition.run_guard(provider.policy, provider.grant, reader, phase=phase,
            event=provider.event, job_context=provider.context, expected_bindings=provider.bindings(),
            clock=lambda: provider.now, sleep=sleep)
        assert waits == [50]
        periodic = [key for key in reader.budget.used if key.startswith("periodic:")]
        assert periodic == ["periodic:" + str(int(NOW.replace(minute=2, second=0).timestamp()))]


@pytest.mark.parametrize("kind", ["missing", "skipped", "missed-tick", "expired", "cancel-fails"])
def test_guard_terminal_fault_blocks_handoff_and_only_cancels_its_own_run(kind):
    provider = Provider()
    provider.producers_complete = False
    reader = provider.reader("source-guard")
    def fault(path, body):
        if path.endswith("/jobs") and kind == "missing":
            body["jobs"].pop(2)
            body["total_count"] -= 1
        if path.endswith("/jobs") and kind == "skipped":
            body["jobs"][1].update(status="completed", conclusion="skipped")
    provider.fault = fault
    def sleep(seconds):
        provider.now += timedelta(seconds=seconds + (2 if kind == "missed-tick" else 0))
        if kind == "expired":
            provider.now = transition.timestamp(provider.grant["expiresAt"])
        if kind == "cancel-fails":
            provider.fail_status = 403
    with pytest.raises(transition.TransitionError):
        transition.run_guard(provider.policy, provider.grant, reader, phase="source-guard",
            event=provider.event, job_context=provider.context, expected_bindings=provider.bindings(),
            clock=lambda: provider.now, sleep=sleep)
    assert set(provider.cancelled) <= {201}
    with pytest.raises(transition.TransitionError):
        reader.budget.assert_healthy()


def test_exact_original_v4_approval_is_required_without_whitespace_aliases():
    _policy, grant = policy_and_grant()
    projection = {"schemaVersion": "ofarm.ci-policy-transition-original-authority.v1", "threadId": "fictional-task"}
    for index, prefix in enumerate(("decision", "consumer")):
        decision = grant["decision" if prefix == "decision" else "consumerDecision"]
        projection[prefix+"Card"] = {"id": decision["cardRef"], "order": index*2,
            "role": "assistant", "text": f"Decision {decision['id']} for #{417 if prefix == 'decision' else 413}."}
        projection[prefix+"Approval"] = {"id": decision["approvalRef"], "order": index*2+1,
            "role": "user", "text": f"I approve OFARM2 decision {decision['id']} version {decision['version']}."}
    packet_text = " ".join([grant[key] for key in ("rootSha", "headSha", "baseSha", "mergeSha", "expiresAt", "grantId")]
        + [transition.digest(grant), grant["journal"]["genesisDigest"], grant["coverageDigest"]])
    projection["activationPacket"] = {"id": "fictional-packet", "order": 4, "role": "assistant", "text": packet_text}
    projection["activationApproval"] = {"id": "fictional-grant-approval", "order": 5, "role": "user",
        "text": transition.activation_approval_text(grant, transition.digest(packet_text.encode()))}
    assert transition.verify_original_authority(projection, grant)["independentHumanAuthentication"] is False
    projection["decisionApproval"]["text"] += "\n"
    with pytest.raises(transition.TransitionError, match="approval/card"):
        transition.verify_original_authority(projection, grant)


def test_dispatch_rejects_cross_phase_operation_before_reading_candidate_inputs():
    args = argparse.Namespace(operation="seal", phase="source-gate")
    with pytest.raises(transition.TransitionError, match="fixed workflow phase"):
        transition.execute(args, environment={})


def test_actual_core_cli_path_emits_only_frozen_typed_inputs_after_final_checks(tmp_path):
    provider = Provider()
    checkout = tmp_path / "trusted"
    (checkout / "conformance").mkdir(parents=True)
    (checkout / transition.ROOT_FILE).write_bytes(transition.canonical_json(provider.policy))
    event_path = tmp_path / "event.json"
    event_path.write_bytes(transition.canonical_json(provider.event))
    output = tmp_path / "outputs"
    args = argparse.Namespace(operation="admit", phase="source-gate", grant_json=None, bindings_json=None,
        event_name="push", event_path=event_path, github_sha=provider.grant["rootSha"],
        workflow_sha=provider.grant["rootSha"], policy_sha=provider.grant["rootSha"],
        workflow_ref=provider.context["workflowRef"], repository=provider.grant["repository"],
        github_output=output, evidence_output=tmp_path / "evidence.json")
    environment = {"GITHUB_REPOSITORY_ID": "9100", "GITHUB_RUN_ID": "201", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_ACTOR_ID": "9200", "GITHUB_REF": provider.grant["sourceRef"]}
    # Root/tree/closure integrity has independent real-Git controls in the
    # operator suite. This test isolates CLI orchestration around that contract;
    # live API, grant, comment, lifecycle, cost and output validators are real.
    with mock.patch.object(transition, "authenticate_policy_checkout", return_value={}) as authenticate:
        transition.execute(args, environment=environment, checkout=checkout,
            reader=provider.reader("source-gate"), clock=lambda: provider.now)
    assert authenticate.call_count == 2
    outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert outputs["eligible"] == "true"
    assert json.loads(outputs["transition_grant"]) == provider.grant
    assert json.loads(outputs["transition_bindings"]) == provider.bindings()
    assert outputs["policy_sha"] == provider.grant["rootSha"]
    assert provider.rest == 12


def test_final_root_reauthentication_failure_emits_no_success_output(tmp_path):
    provider = Provider()
    checkout = tmp_path / "trusted"
    (checkout / "conformance").mkdir(parents=True)
    (checkout / transition.ROOT_FILE).write_bytes(transition.canonical_json(provider.policy))
    event_path = tmp_path / "event.json"
    event_path.write_bytes(transition.canonical_json(provider.event))
    args = argparse.Namespace(operation="admit", phase="conformance",
        grant_json=json.dumps(provider.grant), bindings_json=json.dumps(provider.bindings()),
        event_name="push", event_path=event_path, github_sha=provider.grant["rootSha"],
        workflow_sha=provider.grant["rootSha"], policy_sha=provider.grant["rootSha"],
        workflow_ref=provider.context["workflowRef"], repository=provider.grant["repository"],
        github_output=tmp_path / "outputs", evidence_output=None)
    environment = {"GITHUB_REPOSITORY_ID": "9100", "GITHUB_RUN_ID": "201", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_ACTOR_ID": "9200", "GITHUB_REF": provider.grant["sourceRef"]}
    with mock.patch.object(transition, "authenticate_policy_checkout",
            side_effect=[{}, transition.TransitionError("checkout changed")]):
        with pytest.raises(transition.TransitionError, match="checkout changed"):
            transition.execute(args, environment=environment, checkout=checkout,
                reader=provider.reader("conformance"), clock=lambda: provider.now)
    assert not args.github_output.exists()


def test_expected_binding_mutation_after_gate_refuses_before_handoff():
    provider = Provider()
    bindings = provider.bindings()
    provider.comments[1]["id"] = 999
    with pytest.raises(transition.TransitionError, match="IDs/digests changed"):
        transition.validate_live(provider.policy, provider.grant, provider.reader("handoff-start"),
            phase="handoff-start", now=provider.now, event=provider.event, job_context=provider.context,
            expected_bindings=bindings)


def test_absolute_sweep_deadline_covers_body_parsing_and_whole_scan():
    provider = Provider()
    reader = provider.reader("source-gate")
    times = iter([0.0, 0.0, 16.0])
    reader.budget.monotonic = lambda: next(times, 16.0)
    with pytest.raises(transition.TransitionError, match="deadline"):
        transition.validate_live(provider.policy, provider.grant, reader, phase="source-gate",
            now=provider.now, event=provider.event, job_context=provider.context)


def test_artifact_redirect_charges_external_transport_without_spending_primary_rest_twice():
    provider = Provider()
    calls = []
    payload = b"fictional archive payload"
    headers = {"X-RateLimit-Remaining": "999", "X-RateLimit-Reset": str(provider.reset), "X-RateLimit-Limit": "1000"}
    def open_request(request, timeout):
        calls.append(request)
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 302, "redirect",
                {**headers, "Location": "https://fictional.blob.core.windows.net/artifact?fictional-signature"}, io.BytesIO(b""))
        assert request.get_header("Authorization") is None
        return Response(request.full_url, payload, {})
    reader = transition.ApiReader("fictional-workflow-token", budget=transition.RequestBudget("publish", clock=lambda: provider.now.timestamp()), opener=open_request)
    with reader.artifact_response(reader._request("/repos/fictional-farm/transition-fixture/actions/artifacts/301/zip")) as response:
        assert response.read() == payload
    assert reader.budget.used["publish"] == [1, 0]
    assert len(calls) == 2


def test_authenticated_source_reader_refuses_even_https_redirect():
    provider = Provider()
    def open_request(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 302, "redirect",
            {"X-RateLimit-Remaining": "999", "X-RateLimit-Reset": str(provider.reset), "X-RateLimit-Limit": "1000",
             "Location": "https://fictional.blob.core.windows.net/input"}, io.BytesIO(b""))
    reader = transition.ApiReader("fictional-workflow-token", budget=transition.RequestBudget("publish", clock=lambda: provider.now.timestamp()), opener=open_request)
    with pytest.raises(transition.TransitionError, match="HTTP request refused"):
        reader.response(reader._request("/repos/fictional-farm/transition-fixture/git/blobs/" + "1" * 40))


@pytest.mark.parametrize("publisher", [False, True])
def test_guard_does_not_require_dependent_job_to_have_been_scheduled(publisher):
    provider = Provider(publisher=publisher)
    phase = "publisher-guard" if publisher else "source-guard"
    dependent = "seal transition publication on a fresh trusted runner" if publisher else "seal exact provisional publication handoff"
    def fault(path, body):
        if path.endswith("/jobs"):
            body["jobs"] = [job for job in body["jobs"] if job["name"] != dependent]
            body["total_count"] = len(body["jobs"])
    provider.fault = fault
    transition.run_guard(provider.policy, provider.grant, provider.reader(phase), phase=phase,
        event=provider.event, job_context=provider.context, expected_bindings=provider.bindings(),
        clock=lambda: provider.now)


def test_unknown_job_cannot_join_the_guarded_inventory():
    provider = Provider()
    def fault(path, body):
        if path.endswith("/jobs"):
            body["jobs"][-1]["name"] = "fictional unapproved job"
    provider.fault = fault
    with pytest.raises(transition.TransitionError, match="job inventory"):
        transition.run_guard(provider.policy, provider.grant, provider.reader("source-guard"), phase="source-guard",
            event=provider.event, job_context=provider.context, expected_bindings=provider.bindings(),
            clock=lambda: provider.now)


def test_incomplete_response_body_is_terminal_even_when_json_looks_valid():
    provider = Provider()
    def open_request(request, timeout):
        return Response(request.full_url, b"{}", {"Content-Length": "3", "X-RateLimit-Remaining": "999",
            "X-RateLimit-Reset": str(provider.reset), "X-RateLimit-Limit": "1000"})
    reader = transition.ApiReader("fictional-workflow-token", budget=transition.RequestBudget("source-gate", clock=lambda: provider.now.timestamp()), opener=open_request)
    with pytest.raises(transition.TransitionError, match="body incomplete"):
        reader("/repos/fictional-farm/transition-fixture/pulls/413")
    with pytest.raises(transition.TransitionError):
        reader.budget.assert_healthy()


def test_primary_quota_headers_are_required_on_negative_absence_proof():
    provider = Provider()
    def open_request(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "absent", {}, io.BytesIO(b""))
    reader = transition.ApiReader("fictional-workflow-token", budget=transition.RequestBudget("source-gate", clock=lambda: provider.now.timestamp()), opener=open_request)
    with pytest.raises(transition.TransitionError, match="quota unavailable"):
        reader.absent_ref("/repos/fictional-farm/transition-fixture/git/ref/heads/fictional")


def test_transport_redirect_that_bypasses_accounting_is_terminal():
    provider = Provider()
    def open_request(request, timeout):
        return Response("https://api.github.com/other", b"{}", {"X-RateLimit-Remaining": "999",
            "X-RateLimit-Reset": str(provider.reset), "X-RateLimit-Limit": "1000"})
    reader = transition.ApiReader("fictional-workflow-token", budget=transition.RequestBudget("source-gate", clock=lambda: provider.now.timestamp()), opener=open_request)
    with pytest.raises(transition.TransitionError, match="unobserved redirect"):
        reader("/repos/fictional-farm/transition-fixture/pulls/413")


def test_binding_discovery_and_gate_charge_every_complete_comment_page():
    provider = Provider()
    for number in range(150):
        item = provider.comment(1000+number, "revocation", {"grantId": "unrelated-fictional-grant"}, 0)
        item["body"] = "Fictional ordinary comment."
        provider.comments.append(item)
    reader = provider.reader("source-gate")
    _grant, live = transition.discover_binding(provider.policy, reader, role="source", event=provider.event,
        job_context=provider.context, clock=lambda: provider.now)
    assert live["admission"]["id"] == 101
    assert provider.rest == 14
    assert provider.points == 1
    pages = [query for _method, path, query in provider.calls if path == "/issues/413/comments"]
    assert pages == ["per_page=100&page=1", "per_page=100&page=2"] * 2


def test_unfinished_comment_pagination_refuses_before_any_authority_output():
    provider = Provider()
    for number in range(298):
        item = provider.comment(1000+number, "revocation", {"grantId": "unrelated-fictional-grant"}, 0)
        item["body"] = "Fictional ordinary comment."
        provider.comments.append(item)
    reader = provider.reader("source-gate")
    with pytest.raises(transition.TransitionError, match="complete bounded scan"):
        transition.discover_binding(provider.policy, reader, role="source", event=provider.event,
            job_context=provider.context, clock=lambda: provider.now)
    assert provider.rest == 4
    assert provider.points == 0


def test_quota_forecast_does_not_assume_a_reset_or_ignore_background_consumption():
    provider = Provider()
    _live, reader = validate(provider, "source-gate")
    baseline = transition.require_quota_headroom(reader, provider.grant, "source-gate", now=provider.now)
    assert baseline["REST"] == 965  # 450 unspent pools - 10 reads + 30 ticks*15 +75.
    reader.budget.observe_quota("REST", remaining=baseline["REST"]-1, reset=provider.reset, limit=1000)
    with pytest.raises(transition.TransitionError, match="headroom|quota"):
        transition.require_quota_headroom(reader, provider.grant, "source-gate", now=provider.now)


def test_final_guard_forecast_excludes_only_provider_proved_finished_work():
    provider = Provider()
    _live, reader = validate(provider, "source-guard")
    active = transition.require_quota_headroom(reader, provider.grant, "source-guard", now=provider.now)
    complete = transition.require_quota_headroom(reader, provider.grant, "source-guard", now=provider.now, guard_complete=True)
    assert complete["REST"] < active["REST"]
    assert complete["GraphQL"] < active["GraphQL"]


@pytest.mark.parametrize("status", [403, 429, 503])
def test_protected_error_body_is_fully_accounted_after_terminal_status_without_retention(status):
    provider = Provider()
    payload = b"fictional-sensitive-error-body" * 3000
    calls = []
    def opener(request, timeout):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, status, "fictional", {
            "Content-Length": str(len(payload)), "X-RateLimit-Remaining": "999",
            "X-RateLimit-Reset": str(provider.reset), "X-RateLimit-Limit": "1000"}, io.BytesIO(payload))
    budget = transition.RequestBudget("source-gate", clock=lambda: provider.now.timestamp())
    reader = transition.ApiReader("fictional-token", budget=budget, opener=opener)
    for _ in range(2):
        with pytest.raises(transition.TransitionError):
            reader("/repos/fictional-farm/transition-fixture/pulls/413")
    assert len(calls) == 1
    assert budget._snapshot("transport") == {"requests": 1, "bytes": len(payload)}
    outcomes = [item for item in budget.trace if "requestId" in item]
    assert len(outcomes) == 1 and outcomes[0]["status"] == status and outcomes[0]["complete"]
    assert "fictional-sensitive" not in json.dumps(budget.trace)


def test_protected_incomplete_read_accounts_partial_bytes_and_unknown_outcome():
    import http.client
    provider = Provider()
    class Truncated(Response):
        def read(self, _amount=-1):
            raise http.client.IncompleteRead(b"partial", 20)
    reader = transition.ApiReader("fictional-token", budget=transition.RequestBudget("source-gate",
        clock=lambda: provider.now.timestamp()), opener=lambda request, timeout: Truncated(request.full_url,
            b"", {"Content-Length": "27", "X-RateLimit-Remaining": "999",
                "X-RateLimit-Reset": str(provider.reset), "X-RateLimit-Limit": "1000"}))
    with pytest.raises(transition.TransitionError, match="body unavailable"):
        reader("/repos/fictional-farm/transition-fixture/pulls/413")
    assert reader.budget._snapshot("transport")["bytes"] == 7
    outcome = next(item for item in reader.budget.trace if "requestId" in item)
    assert outcome["complete"] is False and outcome["status"] == 200


def test_coverage_is_fixed_by_selected_code_and_cannot_be_widened_by_inputs():
    policy, grant = policy_and_grant()
    original = transition.coverage.coverage_digest()
    value = transition.coverage.declaration()
    value["protected"] = {}
    assert transition.coverage.coverage_digest() == original
    assert transition.coverage.declaration()["protected"]
    for candidate_policy, candidate_grant in (({**policy, "coverageDigest": "sha256:"+"0"*64}, grant),
            (policy, {**grant, "coverageDigest": "sha256:"+"0"*64})):
        with pytest.raises(transition.TransitionError, match="coverage"):
            transition.validate_grant(candidate_policy, candidate_grant)
    assert "universal-first-403-or-429-refusal" in transition.coverage.declaration()["notEstablished"]
